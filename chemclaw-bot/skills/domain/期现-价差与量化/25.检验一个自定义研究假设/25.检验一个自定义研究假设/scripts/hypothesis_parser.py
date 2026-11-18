# -*- coding: utf-8 -*-
"""hypothesis_parser.py — 把中文自然语言研究假设解析成「可执行研究设计」。

设计原则（这是本 Skill 的核心约束）：
  1. 只做「可回溯的映射」：每个识别出的变量都带 evidence（命中的原词）与 confidence。
  2. 低置信度/多候选 → 不替用户拍板，写入 open_questions，等用户确认（approved=false）。
  3. 无法量化的金融/业务黑话（"走强""强势""利好"）一律拆解成可计算口径候选，
     并标注 chosen_reason，不默认"涨得多=走强"。
  4. 解析器不做任何统计，不接触数据；只产出研究设计草稿，供人审阅。

CLI:
  python hypothesis_parser.py --text "甲醇港口库存连续两周下降时，随后两周基差更容易走强" \
        --out design.json
  python hypothesis_parser.py --text ... --template methanol_port_inventory-basis
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- dictionaries
# 每个词条: (正则, 规范名, 说明, 默认指标口径, 是否需要用户确认)
VARIABLE_DICT = [
    # ---------------- 库存类
    (r"港口库存", "inventory_port", "中国甲醇样本港口库存（隆众口径，华东+华南样本库区）", "万吨，周度", False),
    (r"企业库存|厂库|生产企业库存", "inventory_producer", "甲醇生产企业库存（隆众口径）", "万吨，周度", True),
    (r"库存", "inventory", "库存（未指明口径，需确认港口/厂库/社会库存）", "万吨，周度", True),
    (r"到港|到港量|抵港|卸货", "arrivals", "周度进口/内贸到港量", "万吨，周度", True),
    (r"开工率|产能利用率|负荷", "operating_rate", "甲醇开工率 / 产能利用率", "%", False),
    (r"产量", "output", "甲醇周度产量", "万吨，周度", False),
    (r"进口(量)?", "imports", "甲醇进口量（海关月度）", "万吨，月度", True),
    (r"MTO|烯烃|cto|mto", "mto_operating", "MTO/烯烃装置开工率", "%", True),
    (r"利润|加工费|现金流", "margin", "甲醇生产/下游利润或加工费", "元/吨", True),
    # ---------------- 价格类
    (r"基差(率)?", "basis", "基差 = 现货 − 期货（默认主力/活跃合约）", "元/吨 或 %", False),
    (r"月差|近远月|1-5|05-09|9-1|跨期", "calendar_spread", "同品种不同交割月价差", "元/吨", True),
    (r"现货(价)?|出罐价|出厂价", "spot_price", "现货价格（区域口径需确认）", "元/吨", False),
    (r"期货(价)?|盘面|主力(合约)?", "fut_price", "期货主力/活跃合约价格", "元/吨", False),
    (r"区域价差|地区价差|华东.?华南", "regional_spread", "两地区现货价差", "元/吨", True),
    (r"内外盘|进口利润|进口盈亏|CFR", "import_parity", "进口成本 vs 内盘价差", "元/吨", True),
    (r"煤炭|动力煤|煤价|天然气", "cost_coal", "成本端价格（煤/气）", "元/吨", True),
    (r"原油|布伦特|Brent", "cost_oil", "原油价格", "美元/桶", True),
    (r"波动率", "volatility", "实现波动率/隐含波动率", "%", True),
    (r"持仓|持仓量|OI", "open_interest", "期货总持仓", "手", False),
]

# 观察对象候选（"走强/走弱/涨/跌/扩大/收敛"作用于什么）
TARGET_CANDIDATES = [
    ("basis_level", "基差水平（现货−期货，元/吨）", "基差绝对值变动"),
    ("basis_rate", "基差率（基差/期货价，%）", "相对口径，跨年份可比"),
    ("basis_change", "基差比前值的变化（元/吨）", "以周为单位的变化"),
    ("basis_rank", "基差的历史分位（滚动250日）", "对'强弱'最贴近的本意：相对历史位置"),
    ("fut_return", "期货收益率（%）", "不含现货的口径"),
    ("spot_return", "现货价格变化（元/吨）", "只看现货"),
]

DIRECTION_WORDS_UP = r"走强|变强|抬升|走阔|扩大|上涨|上升|走高|走扩|转正|修复|上涨|升高"
DIRECTION_WORDS_DOWN = r"走弱|变弱|收窄|缩小|下跌|下降|走低|收敛|转负|恶化|降低"

# 信号条件词
COND_DICT = [
    (r"连续\s*([两二三四五3-5])\s*(?:周|个?交易周)", "run_down", "连续k周"),
    (r"(下降|下滑|去库|减少|回落)", "direction_down", None),
    (r"(上升|累库|增加|上涨)", "direction_up", None),
    (r"超过?|大于|高于|不低于|突破", "threshold_op", ">"),
    (r"低于|小于|不及|跌破", "threshold_op", "<"),
    (r"分位|百分位|历史低位|历史高位", "quantile", None),
    (r"同比|环比", "compare", None),
]

HORIZON_PATTERNS = [
    (r"随后\s*([一两二三四1-4])\s*周", lambda m: 5 * _cn2int(m.group(1))),
    (r"([一两二三四1-4])\s*周(?:后|之内|内)", lambda m: 5 * _cn2int(m.group(1))),
    (r"([1-9]|10)\s*个?\s*交易日", lambda m: int(m.group(1))),
    (r"次日", lambda m: 1),
    (r"下个?月|一个月", lambda m: 21),
]

PRODUCT_MAP = {
    "甲醇": ("MA", "甲醇（郑商所 MA，华东/太仓现货）", "MA"),
    "纯碱": ("SA", "纯碱（郑商所 SA，重碱华东现货）", "SA"),
    "烧碱": ("SH", "烧碱（郑商所 SH，32%/50% 液碱需确认）", "SH"),
    "尿素": ("UR", "尿素（郑商所 UR，小颗粒主产区现货）", "UR"),
    "玻璃": ("FG", "浮法玻璃（郑商所 FG，5mm 大板主产区现货）", "FG"),
    "PTA": ("TA0", "PTA（郑商所 TA，华东现货）", "TA0"),
    "PVC": ("V", "PVC（大商所 V，电石法华东现货）", "V"),
    "聚丙烯": ("PP", "聚丙烯（大商所 PP，拉丝华东现货）", "PP"),
    "PP": ("PP", "聚丙烯（大商所 PP，拉丝华东现货）", "PP"),
    "乙二醇": ("EG", "乙二醇（大商所 EG，华东现货）", "EG"),
    "苯乙烯": ("EB", "苯乙烯（大商所 EB，华东现货）", "EB"),
    "碳酸锂": ("LC", "碳酸锂（广期所 LC，电池级现货）", "LC"),
    "液化气": ("PG", "LPG（大商所 PG，民用气华南/华东）", "PG"),
    "苯酐": (None, "苯酐（无期货，只能用现货价差/加工费）", None),
    "纯苯": (None, "纯苯（无期货，参考华东现货）", None),
    "双氧水": (None, "双氧水（无期货，区域现货）", None),
}

TEMPLATES = {
    "methanol_port_inventory-basis": {
        "name": "甲醇港口库存连续下行 × 基差走强",
        "product": "甲醇",
        "x_series": "中国甲醇样本港口库存（万吨，周度，隆众口径，样本=华东+华南港口库区）",
        "target": "basis_change",
        "signal": "连续两周去库（ΔI_t<0 且 ΔI_{t−1}<0）",
        "control": "非连续去库的全部其余周",
        "horizon_sessions": 10,
        "entry": "报告发布日14:00前已公布 → 当日收盘价（前视偏差审计项）",
    },
    "soda_ash_producer_inventory-basis": {
        "name": "纯碱厂库连续累库 × 基差走弱",
        "product": "纯碱",
        "x_series": "纯碱生产企业库存（万吨，周度）",
        "target": "basis_change",
        "signal": "连续两周累库",
        "control": "非连续累库周",
        "horizon_sessions": 5,
        "entry": "库存公布后首个交易日收盘",
    },
    "methanol_mto-basis": {
        "name": "甲醇 MTO 开工率跌破阈值 × 基差走弱",
        "product": "甲醇",
        "x_series": "MTO 行业开工率（%，周度）",
        "target": "basis_change",
        "signal": "开工率环比下降且低于历史 20% 分位",
        "control": "其余周",
        "horizon_sessions": 10,
        "entry": "公布后首个交易日收盘",
    },
}


def _cn2int(s):
    m = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
    return int(m.get(s, 0))


# --------------------------------------------------------------------------- parser
def parse(text, template=None):
    t = text.strip()
    found_vars = []
    for rx, key, desc, unit, need_confirm in VARIABLE_DICT:
        for m in re.finditer(rx, t, re.I):
            found_vars.append({"key": key, "desc": desc, "unit": unit, "evidence": m.group(0),
                               "pos": m.start(), "need_confirm": need_confirm})
    # keep first occurrence per key; drop the generic `inventory` key when a specific
    # inventory scope (port / producer) was matched at the same or adjacent position
    seen = {}
    for v in found_vars:
        seen.setdefault(v["key"], v)
    if "inventory" in seen and ({"inventory_port", "inventory_producer"} & set(seen)):
        seen.pop("inventory")
    vars_sorted = sorted(seen.values(), key=lambda x: x["pos"])

    product = None
    for k, (code, desc, sym) in PRODUCT_MAP.items():
        if k in t:
            product = {"key": k, "futures_code": code, "desc": desc, "symbol": sym}
            break

    # outcomes: direction words
    up = re.findall(DIRECTION_WORDS_UP, t)
    down = re.findall(DIRECTION_WORDS_DOWN, t)
    condition_runs = re.findall(r"连续\s*([两二三四五3-5])\s*(?:周|个?交易周)", t)

    horizons = []
    for rx, fn in HORIZON_PATTERNS:
        m = re.search(rx, t)
        if m:
            horizons.append({"evidence": m.group(0), "sessions": fn(m), "weeks": round(fn(m) / 5, 2)})

    # target selection: first price/level-ish vocabulary after a direction word.
    # "基差走强" is ambiguous — level vs rate vs rank — so mark need_confirm=True
    # unless the text itself says 基差率 / 基差分位.
    target = None
    for key, label, why in TARGET_CANDIDATES:
        kw = {"basis_level": r"基差(?!率)", "basis_rate": r"基差率", "basis_change": r"基差(?!率)",
              "basis_rank": r"基差分位", "fut_return": r"期货|盘面", "spot_return": r"现货"}[key]
        m = re.search(kw, t)
        if m:
            explicit = key in ("basis_rate", "basis_rank")
            target = {"key": key, "label": label, "evidence": m.group(0), "chosen_reason": why,
                      "need_confirm": (not explicit) and "基差" in t}
            break

    design = {
        "raw_text": text,
        "template": template,
        "product": product,
        "variables_detected": vars_sorted,
        "directions": {"up": up, "down": down},
        "run_length": _cn2int(condition_runs[0]) if condition_runs else None,
        "horizons": horizons,
        "target": target,
        "module": _guess_module(vars_sorted, target),
        "open_questions": [],
        "assumptions": [],
        "approved": False,
    }
    _fill_questions(design, t)
    if template and template in TEMPLATES:
        design["template_spec"] = TEMPLATES[template]
    return design


def _guess_module(vars_, target):
    keys = {v["key"] for v in vars_}
    if target and target["key"].startswith("basis"):
        return "basis_conditioned"
    if keys & {"inventory", "inventory_port", "inventory_producer"}:
        return "inventory_conditioned"
    return "custom"


def _fill_questions(d, t):
    q = d["open_questions"]
    if not d["product"]:
        q.append({"id": "Q1", "topic": "品种", "question": "假设没有指明品种，请确认品种（及其现货口径区域）。",
                  "options": ["甲醇", "纯碱", "尿素", "其他（请补充）"], "blocking": True})
    inv = next((v for v in d["variables_detected"] if v["key"].startswith("inventory")), None)
    if inv and inv["key"] == "inventory":
        q.append({"id": "Q2", "topic": "库存口径", "question": "库存指哪一个口径？港口样本库存 / 生产企业库存 / 社会库存汇总，三者的走向经常相反。",
                  "options": ["港口样本库存（隆众，万吨）", "生产企业库存（隆众，万吨）", "两者都要，分别检验"], "blocking": True})
    if d["run_length"]:
        d["assumptions"].append({
            "id": "A1", "text": f"“连续{d['run_length']}周”= 相邻两周的库存差均为严格的负值（ΔI_t<0 且 ΔI_{{t−1}}<0），"
                                "周间隔要求 5–10 天，停发/延发周的配对样本标记为缺口而不是插值。",
            "need_confirm": False})
    if not d["horizons"]:
        q.append({"id": "Q3", "topic": "观察窗口", "question": "“随后”指多久？未识别到明确窗口。",
                  "options": ["2 周（10 个交易日）", "1 周（5 个交易日）", "1 个月（21 个交易日）"], "blocking": True})
    if d["directions"]["up"]:
        q.append({"id": "Q4", "topic": "“走强”的定义", "question":
                  "“基差走强”在统计上对应哪一个口径？不同口径结论可能不同，请勾选主口径（其余作为敏感性分析）。",
                  "options": ["基差绝对变化 Δ(现货−期货) > 0（元/吨）",
                              "基差率上升（%）/ 基差历史分位上升",
                              "全部口径都检验，主口径以你勾选为准"], "blocking": True})
    q.append({"id": "Q5", "topic": "观察对象合约", "question": "基差用哪个期货合约计价？",
              "options": ["主力/活跃合约（接近可交易）", "近月合约（随交割日切换）", "固定合约（如 01/05/09）"], "blocking": False})
    q.append({"id": "Q6", "topic": "价格时点", "question": "库存报告通常在观察日 14:00 前后发布。入场价用报告日当日 15:00 收盘，还是次日收盘？",
              "options": ["当日收盘（需确认发布早于收盘，否则构成前视）", "次日收盘（更保守）"], "blocking": False})
    q.append({"id": "Q7", "topic": "样本范围", "question": "样本起止时间与是否剔除 2021–2022 极端行情阶段？",
              "options": ["全部可得样本自动确定", "指定起止日期", "剔除极端阶段并单列"], "blocking": False})
    q.append({"id": "Q8", "topic": "多口径与多重检验", "question": "预期会同时检验几个口径/窗口/子样本？需登记全部检验数用于 BH 校正。",
              "options": ["自动登记（推荐）", "只做主口径不做敏感性"], "blocking": False})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--template", default=None)
    ap.add_argument("--out", default="design_draft.json")
    a = ap.parse_args()
    d = parse(a.text, a.template)
    with open(a.out, "w", encoding="utf-8-sig") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(json.dumps(d, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
