# -*- coding: utf-8 -*-
"""交付前质量自检 —— 对照 SKILL.md §8 的 8 条硬约束。

用法：
    python self_check.py <case_data.json>
    python self_check.py <case_data.json> --strict    # 有 FAIL 时返回非 0

设计原则：只做「能不能机械判定」的检查。需要人来判断的（如表述是否越界）
用关键词启发式扫描并输出「待人工复核」，不假装能自动判对。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

OK, WARN, FAIL = "PASS", "WARN", "FAIL"
MARK = {OK: "[PASS]", WARN: "[WARN]", FAIL: "[FAIL]"}

# 价格方向性结论的危险措辞（命中即提示人工复核，不是自动失败）
PRICE_WORDS = [
    "预计上涨", "预计下跌", "将上涨", "将下跌", "看涨", "看空",
    "利好", "利空", "建议买入", "建议卖出", "目标价", "涨到", "跌到",
    "必然上涨", "必然下跌", "价格将",
]
# 把「计划/预计」写成既成事实的危险措辞
PLAN_AS_DONE = ["已投产", "已建成", "已开工", "已达产"]


class Result:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def add(self, status: str, name: str, detail: str) -> None:
        self.items.append((status, name, detail))

    def count(self, status: str) -> int:
        return sum(1 for s, _, _ in self.items if s == status)


def _walk_strings(obj, path=""):
    """遍历 JSON 里所有字符串，yield (path, text)。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


# ------------------------------------------------------------------ 检查项
def check_sources(r: Result, d: dict) -> None:
    """① 每个数字都有 source_id，且来源可追。"""
    srcs = d.get("sources", [])
    ids = {s.get("id") for s in srcs}
    if not srcs:
        r.add(FAIL, "来源表存在", "sources 为空，任何数字都无法追溯")
        return
    r.add(OK, "来源表存在", f"{len(srcs)} 条来源")

    no_url = [s.get("id") for s in srcs if not s.get("url")]
    if no_url:
        r.add(WARN, "来源 URL 完整性", f"以下来源无 URL：{no_url}（需在正文标注「未获取」）")
    else:
        r.add(OK, "来源 URL 完整性", "全部来源均有 URL 或已标注获取方式")

    # 来源引用的 id 必须真实存在
    dangling = set()
    for path, text in _walk_strings(d):
        for m in re.finditer(r"\bS(\d{1,2})\b", text):
            sid = "S" + m.group(1)
            if sid not in ids:
                dangling.add(f"{sid}（出现在 {path}）")
    if dangling:
        r.add(FAIL, "来源引用有效性", f"引用了不存在的来源：{sorted(dangling)[:5]}")
    else:
        r.add(OK, "来源引用有效性", "正文引用的 S* 编号均在来源表中")

    # 关键量化表必须带 grade/source
    for table, key in [("capacity_basis", "capacity_basis"),
                       ("calculations.ratios", None),
                       ("peers", "peers")]:
        rows = d.get(key, []) if key else d.get("calculations", {}).get("ratios", [])
        miss = [i for i, row in enumerate(rows)
                if not row.get("source") and not row.get("denominator_id") and not row.get("grade")]
        if miss:
            r.add(WARN, f"{table} 证据标注", f"第 {miss} 行缺少 source/grade 标注")
        else:
            r.add(OK, f"{table} 证据标注", f"{len(rows)} 行均有来源或等级")


def check_plan_vs_done(r: Result, d: dict) -> None:
    """② 没有把「预计/计划」写成「已投产/已停车」。"""
    hits = []
    for path, text in _walk_strings(d):
        for w in PLAN_AS_DONE:
            if w in text:
                # 前面出现「计划/预计/拟/将」但同句又出现既成事实词 → 可疑
                hits.append((path, w, text[:60]))
    if hits:
        r.add(WARN, "计划 vs 既成事实",
              f"{len(hits)} 处出现既成事实措辞，需人工确认不是把计划写成事实："
              + "；".join(f"{p}『{w}』" for p, w, _ in hits[:3]))
    else:
        r.add(OK, "计划 vs 既成事实", "未发现把计划写成既成事实的措辞")

    u = d.get("event", {}).get("unit_detail", {})
    wws = str(u.get("whether_whole_plant_stopped", ""))
    if not wws:
        r.add(FAIL, "停产范围明确性", "unit_detail.whether_whole_plant_stopped 缺失")
    elif any(k in wws for k in ("未确认", "部分确认", "已确认")):
        r.add(OK, "停产范围明确性", f"已明确表述：{wws[:40]}")
    else:
        r.add(WARN, "停产范围明确性", f"表述含糊，未写「已确认/未确认/部分确认」：{wws[:40]}")


def check_maintenance_vs_accident(r: Result, d: dict) -> None:
    """③ 计划检修与事故停车使用不同口径。"""
    et = d.get("event", {}).get("event_type_code", "")
    if not et:
        r.add(FAIL, "事件类型", "event_type_code 缺失")
        return
    r.add(OK, "事件类型", f"{et} / {d['event'].get('event_type_cn', '')}")

    k = d.get("calculations", {}).get("scenario_scenarios", [])
    if not k:
        r.add(WARN, "情景定义", "未定义影响系数 k 的情景")
    else:
        bases = [str(x.get("basis", "")) for x in k]
        has_assumption_note = any("假设" in b for b in bases)
        r.add(OK if has_assumption_note else WARN, "情景假设标注",
              f"{len(k)} 个情景；{'已' if has_assumption_note else '未'}标注假设性质")

    ann = d.get("calculations", {}).get("annual_decomposition", {})
    if ann:
        r.add(OK, "年度检修口径分离",
              "存在 annual_decomposition，检修因素与事故因素分列")


def check_assumptions_exposed(r: Result, d: dict) -> None:
    """④ 所有假设值单独列出、可被用户修改。"""
    c = d.get("calculations", {})
    ra = c.get("rate_assumption", {})
    need = {
        "开工率 r": ra.get("r_actual_2021_2023"),
        "影响系数 k": [x.get("k") for x in c.get("scenario_scenarios", [])],
        "情景天数 d": c.get("scenario_matrix", {}).get("days"),
        "开工率备选": ra.get("alternative_r"),
    }
    missing = [n for n, v in need.items() if not v]
    if missing:
        r.add(FAIL, "假设参数齐备", f"缺少：{missing}")
    else:
        r.add(OK, "假设参数齐备", "r / k / d / 备选 r 均已单列")

    ra_note = str(ra.get("formula", ""))
    if "=" in ra_note:
        r.add(OK, "r 的计算说明", ra_note[:70])
    else:
        r.add(WARN, "r 的计算说明", "rate_assumption.formula 未写明计算式")


def check_gaps_preserved(r: Result, d: dict) -> None:
    """⑤ 缺口显示「未获取」，不是 0 或估算值。"""
    gaps = d.get("gaps", [])
    if not gaps:
        r.add(WARN, "数据缺口登记", "gaps 为空——请确认真的没有缺口，而不是漏记")
    else:
        r.add(OK, "数据缺口登记", f"{len(gaps)} 条缺口已登记")

    bad = [g.get("id") for g in gaps
           if not g.get("item") or not g.get("impact") or not g.get("placeholder")]
    if bad:
        r.add(FAIL, "缺口三要素", f"以下缺口缺少「缺什么/卡住什么/如何处理」：{bad}")
    else:
        if gaps:
            r.add(OK, "缺口三要素", "每条缺口均写清 缺什么 / 卡住什么 / 如何处理")

    # 分解表里不确定的份额必须是 None 而不是 0
    rows = d.get("calculations", {}).get("annual_decomposition", {}).get("rows", [])
    fake_zero = [x.get("item") for x in rows
                 if x.get("value_t") == 0 and any(k in str(x.get("status", "")) for k in ("缺口", "未拆分", "未获取"))]
    if fake_zero:
        r.add(FAIL, "缺口未被填 0", f"以下项目以 0 冒充缺口：{fake_zero}")
    else:
        r.add(OK, "缺口未被填 0", "未发现用 0 冒充缺口")

    nulls = [x.get("item") for x in rows if x.get("value_t") is None]
    if nulls:
        r.add(OK, "缺口显式留白", f"{len(nulls)} 项显式留空：{nulls[:3]}")


def check_no_price_call(r: Result, d: dict) -> None:
    """⑥ 全文没有「预计上涨/下跌」类结论。"""
    hits = []
    for path, text in _walk_strings(d):
        for w in PRICE_WORDS:
            if w in text:
                # 「不提供价格涨跌结论」这类免责声明里的词不算
                if any(neg in text for neg in ("不提供", "不构成", "不给", "禁止", "不推导", "不做")):
                    continue
                hits.append((path, w))
    if hits:
        r.add(FAIL, "价格方向性结论", f"命中 {len(hits)} 处，必须改写：{hits[:5]}")
    else:
        r.add(OK, "价格方向性结论", "未发现「预计上涨/下跌」类表述")

    disc = d.get("meta", {}).get("disclaimer", "")
    if any(k in disc for k in ("不", "不构成")):
        r.add(OK, "免责声明", "已声明不提供价格结论/不构成投资建议")
    else:
        r.add(WARN, "免责声明", "meta.disclaimer 未明确声明不提供价格结论")

    ms = d.get("market_snapshot", {})
    if ms.get("note") and ("不" in str(ms["note"])):
        r.add(OK, "行情章节约束", str(ms["note"])[:70])
    else:
        r.add(WARN, "行情章节约束", "market_snapshot.note 未写明「只描述不推导」")


def check_unconfirmed_isolated(r: Result, d: dict) -> None:
    """⑦ 未经确认的事件没有计入确认影响汇总。"""
    t = d.get("three_way", {})
    for key, label in [("confirmed", "已确认"), ("uncertain", "不确定"),
                       ("unconfirmed", "未确认"), ("to_verify", "待核验")]:
        if not isinstance(t.get(key), list):
            r.add(FAIL, f"三分法-{label}", f"three_way.{key} 缺失或不是数组")
    if all(isinstance(t.get(k), list) for k in ("confirmed", "uncertain", "unconfirmed", "to_verify")):
        r.add(OK, "三分法结构", "已确认 / 不确定 / 未确认 / 待核验 四类齐备")

    # 已确认项必须都有 A/B 级证据
    weak = [x.get("item") for x in t.get("confirmed", [])
            if not str(x.get("grade", "")).startswith(("A", "B"))]
    if weak:
        r.add(FAIL, "已确认项证据等级", f"进入「已确认」但等级不足 A/B：{weak}")
    else:
        r.add(OK, "已确认项证据等级", "全部为 A/B 级")

    # 未确认项不得为 A 级（否则应移到已确认）
    over = [x.get("item") for x in t.get("unconfirmed", [])
            if str(x.get("grade", "")).startswith("A")]
    if over:
        r.add(WARN, "未确认项等级自洽", f"未确认项却是 A 级，是否应归入已确认：{over}")
    else:
        r.add(OK, "未确认项等级自洽", "未确认项均为低等级来源")


def check_old_news_evidence(r: Result, d: dict) -> None:
    """⑧ 旧闻判定有明确证据链。"""
    v = d.get("verification_card", {})
    verdict = v.get("old_news_verdict", "")
    ev = v.get("old_news_evidence", [])
    if not verdict:
        r.add(FAIL, "旧闻判定", "old_news_verdict 缺失")
    elif verdict not in ("旧闻重发", "旧闻+新进展", "新消息", "待定"):
        r.add(WARN, "旧闻判定", f"取值不在枚举内：{verdict}")
    else:
        r.add(OK, "旧闻判定", verdict)

    if len(ev) < 3:
        r.add(FAIL, "旧闻证据链", f"仅 {len(ev)} 条证据，至少需要 3 条才能支撑判定")
    else:
        r.add(OK, "旧闻证据链", f"{len(ev)} 条信号已逐条陈述")

    fs = v.get("freshness_score")
    if isinstance(fs, (int, float)) and 0 <= fs <= 5:
        r.add(OK, "时效评分", f"{fs}/5 · {v.get('freshness_label', '')}")
    else:
        r.add(FAIL, "时效评分", f"freshness_score 缺失或越界：{fs}")

    for f in ("first_public_authority", "first_public_date", "fact_status"):
        if not v.get(f):
            r.add(FAIL, "核验卡必填项", f"缺少 {f}")
    if all(v.get(f) for f in ("first_public_authority", "first_public_date", "fact_status")):
        r.add(OK, "核验卡必填项", "首发主体 / 首发日期 / 事实状态 均齐备")


def check_observables(r: Result, d: dict) -> None:
    """附加：可观察指标是否可执行。"""
    obs = d.get("observables", [])
    if len(obs) < 3:
        r.add(FAIL, "可观察指标", f"仅 {len(obs)} 条，至少 3 条")
        return
    incomplete = [o.get("metric") or o.get("indicator") for o in obs
                  if not (o.get("where") and o.get("trigger") and o.get("freq"))]
    if incomplete:
        r.add(WARN, "可观察指标可执行性", f"以下指标缺少「在哪看/频率/异常判据」：{incomplete[:3]}")
    else:
        r.add(OK, "可观察指标可执行性", f"{len(obs)} 条指标均写明 在哪看 / 频率 / 异常判据")

    first = [o for o in obs if o.get("priority") == 1]
    if first:
        r.add(OK, "首选指标", f"{len(first)} 条首选指标")
    else:
        r.add(WARN, "首选指标", "未标注 priority=1 的首选指标")


# ------------------------------------------------------------------ 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="案例数据交付前自检")
    ap.add_argument("data", type=pathlib.Path)
    ap.add_argument("--strict", action="store_true", help="有 FAIL 时返回非 0")
    args = ap.parse_args()

    try:
        d = json.loads(args.data.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON 解析失败：{e}")
        return 2

    r = Result()
    checks = [
        ("① 来源可追溯", check_sources),
        ("② 计划 vs 既成事实", check_plan_vs_done),
        ("③ 检修口径 vs 事故口径", check_maintenance_vs_accident),
        ("④ 假设显性化", check_assumptions_exposed),
        ("⑤ 缺口保留", check_gaps_preserved),
        ("⑥ 不给价格方向", check_no_price_call),
        ("⑦ 未确认项隔离", check_unconfirmed_isolated),
        ("⑧ 旧闻证据链", check_old_news_evidence),
        ("⑨ 可观察指标", check_observables),
    ]
    for title, fn in checks:
        r.add(OK, "", "")  # 占位分隔，稍后过滤
        r.items.pop()
        print(f"\n=== {title} ===")
        before = len(r.items)
        fn(r, d)
        for status, name, detail in r.items[before:]:
            print(f"  {MARK[status]} {name}：{detail}")

    n_ok, n_warn, n_fail = r.count(OK), r.count(WARN), r.count(FAIL)
    print("\n" + "=" * 64)
    print(f"合计 {len(r.items)} 项检查：PASS {n_ok} / WARN {n_warn} / FAIL {n_fail}")
    if n_fail:
        print("\n必须修复（FAIL）：")
        for status, name, detail in r.items:
            if status == FAIL:
                print(f"  - {name}：{detail}")
    if n_warn:
        print("\n建议复核（WARN）：")
        for status, name, detail in r.items:
            if status == WARN:
                print(f"  - {name}：{detail}")
    if not n_fail:
        print("\n结论：硬约束全部通过，可以交付。")
    return 1 if (args.strict and n_fail) else 0


if __name__ == "__main__":
    raise SystemExit(main())
