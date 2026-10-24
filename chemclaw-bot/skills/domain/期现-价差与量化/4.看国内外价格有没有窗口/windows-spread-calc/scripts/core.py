# -*- coding: utf-8 -*-
"""内外价差 / 进口成本折算 —— 计算内核（单一事实源）。

本文件是整套 Skill 的「公式事实源」：
  * Python 侧（assemble / build_html / build_xlsx / validate / checkers）全部调用这里的函数；
  * JS 侧（scripts/assets/core.js）是逐行等价实现，用于 HTML 报告里的交互重算；
  * scripts/check_consistency.py 用随机参数对两侧做数值比对，偏差 > 1e-6 即判失败。

设计约束（违反即视为不是本 Skill 的输出）：
  1. 只做「成本 / 价差」折算，不产出任何交易指令、套利结论、方向判断；
  2. 每一个费用项都能追到 TERM_INCLUDES 里的贸易术语规则（含/不含），防止重复计费；
  3. 任何缺失参数一律走 gaps，不用「经验值」顶替；
  4. 历史序列里的运费 / 汇率 / 报价取对应时点的值，取不到就标记为 assumed_at_base 或 gap，
     绝不拿今天的运费冒充历史实际成本。

单位约定：除注明 USD 的原始报价外，所有金额均为 元/吨。

成本四层口径：
  CIF 折人民币  ->  import_cost()['cif']
  税费现金支出  ->  import_cost()['cash_out']
  可抵扣进口VAT ->  import_cost()['vat_credit']
  可比经济成本  ->  import_cost()['net_cash'] = landed_cash - vat_credit
"""
from __future__ import annotations

import re

ROUND = 6

# 贸易术语里「已经包含」的费用层（1=报价已含，对应参数一律按 0 计）
TERM_INCLUDES = {
    "EXW": dict(goods=1, inland_origin=0, export_clear=0, freight=0, insurance=0, discharge=0, inland_dest=0),
    "FCA": dict(goods=1, inland_origin=1, export_clear=1, freight=0, insurance=0, discharge=0, inland_dest=0),
    "FOB": dict(goods=1, inland_origin=1, export_clear=1, freight=0, insurance=0, discharge=0, inland_dest=0),
    "CFR": dict(goods=1, inland_origin=1, export_clear=1, freight=1, insurance=0, discharge=0, inland_dest=0),
    "CIF": dict(goods=1, inland_origin=1, export_clear=1, freight=1, insurance=1, discharge=0, inland_dest=0),
    "DAP": dict(goods=1, inland_origin=1, export_clear=1, freight=1, insurance=1, discharge=1, inland_dest=1),
}
TERM_ALIASES = {
    "": "CFR", "C&F": "CFR", "CNF": "CFR", "CFR中国": "CFR", "CIF中国": "CIF",
    "CFRCHINA": "CFR", "CIFCHINA": "CIF", "FAS": "FOB", "FOBCHINA": "FOB",
}
TERM_LABEL = {
    "EXW": "EXW 工厂交货", "FCA": "FCA 货交承运人", "FOB": "FOB 装运港船上交货",
    "CFR": "CFR 成本加运费（至中国主港）", "CIF": "CIF 成本加保险费加运费（至中国主港）",
    "DAP": "DAP 目的地交货",
}
# 术语已含的费用 -> (参数键, 中文名)，用于 check_terms 自检
TERM_GUARDED = {
    "freight": ("ocean_freight", "国际运费（海运）"),
    "insurance": ("insurance_rate_pct", "保险费率"),
    "inland_origin": ("inland_origin", "出口国内陆运费"),
    "export_clear": ("export_clear", "出口报关杂费"),
    "discharge": ("discharge_fee", "目的港卸货/港杂费"),
    "inland_dest": ("inland_dest", "进口国内陆运杂费"),
}


# ------------------------------------------------------------------ 基础工具
def fnum(v, default=None):
    if v is None or v == "" or v == "—" or v == "-":
        return default
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return default


def r6(x):
    if x is None:
        return None
    return float(format(float(x), "." + str(ROUND) + "f"))


def norm_term(t):
    k = (t or "").strip().upper().replace(" ", "")
    if k in TERM_ALIASES:
        return TERM_ALIASES[k]
    return k if k in TERM_INCLUDES else "CFR"


def parse_range(v):
    """'433-438' / '433' / 433.0 -> (low, high)"""
    if v is None or v == "":
        return None, None
    if isinstance(v, (int, float)):
        return float(v), float(v)
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(v).replace(",", ""))
    if not nums:
        return None, None
    lo = float(nums[0])
    hi = float(nums[1]) if len(nums) > 1 else lo
    return (lo, hi) if lo <= hi else (hi, lo)


def mid(lo, hi):
    if lo is None or hi is None:
        return None
    return (lo + hi) / 2.0


# ------------------------------------------------------------------ 1. 成本折算
def import_cost(p):
    """把一条海外报价折算成四层成本（元/吨）。

    参数键（与 HTML 交互参数、Excel「参数与输入」表一一对应）：
      price_quote, currency, term, fx_usdcny, purity, gross_weight_factor
      inland_origin, export_clear, ocean_freight
      insurance_rate(加成率,默认1.1), insurance_rate_pct(保险费率)
      discharge_fee, inland_dest, unload_fee
      duty_rate, other_tax_rate, vat_rate, vat_credit_ratio

    内地费用参数（discharge_fee/inland_dest/unload_fee）按「原币/吨」填：
    USD 报价时乘汇率，CNY 报价时视为人民币/吨。

    计费规则：
      * 凡术语已包含的费用层，参数一律按 0 计（自动去重，check_terms 会报冲突）；
      * 保险费只对「报价未含保险」的术语（EXW/FCA/FOB/CFR）计算：
            保险费 = (货值 + 出口端费用 + 国际运费) × 加成率 × 费率
      * 关税     = (CIF + 卸货费) × duty_rate
      * 其他税   = (CIF + 卸货费) × other_tax_rate
      * 增值税   = (CIF + 卸货费 + 关税) × vat_rate
      * 可抵扣VAT = 增值税 × vat_credit_ratio
      * landed_cash = CIF + 卸货 + 关税 + 其他税 + 增值税 + 进口内陆 + 损耗
      * net_cash    = landed_cash - 可抵扣VAT
      * unit_net    = net_cash / purity × gross_weight_factor
    """
    term = norm_term(p.get("term"))
    inc = TERM_INCLUDES[term]
    cur = (p.get("currency") or "USD").strip().upper()
    fx_in = fnum(p.get("fx_usdcny"), 0.0) or 0.0
    fx = fx_in if cur == "USD" else 1.0
    quote = fnum(p.get("price_quote"), 0.0) or 0.0
    purity = fnum(p.get("purity"), 1.0) or 1.0
    gross = fnum(p.get("gross_weight_factor"), 1.0) or 1.0

    def gate(flag):
        return 1.0 if inc[flag] else 0.0

    def v(key):
        return (fnum(p.get(key), 0.0) or 0.0) * fx

    goods_cny = quote * fx
    inland_o = v("inland_origin") * (1 - gate("inland_origin"))
    export_c = v("export_clear") * (1 - gate("export_clear"))
    freight = v("ocean_freight") * (1 - gate("freight"))
    ins_rate = fnum(p.get("insurance_rate_pct"), 0.0) or 0.0
    ins_mark = fnum(p.get("insurance_rate"), 1.1)
    ins_mark = 1.1 if ins_mark is None else ins_mark
    insurance = 0.0 if gate("insurance") else \
        (goods_cny + inland_o + export_c + freight) * ins_mark * ins_rate
    discharge = v("discharge_fee") * (1 - gate("discharge"))
    inland_d = v("inland_dest") * (1 - gate("inland_dest"))
    unload = v("unload_fee") * (1 - gate("inland_dest"))

    cif = goods_cny + inland_o + export_c + freight + insurance
    duty_rate = fnum(p.get("duty_rate"), 0.0) or 0.0
    other_rate = fnum(p.get("other_tax_rate"), 0.0) or 0.0
    vat_rate = fnum(p.get("vat_rate"), 0.13)
    vat_rate = 0.13 if vat_rate is None else vat_rate
    credit_ratio = fnum(p.get("vat_credit_ratio"), 1.0)
    credit_ratio = 1.0 if credit_ratio is None else max(0.0, min(1.0, credit_ratio))

    duty = (cif + discharge) * duty_rate
    other_tax = (cif + discharge) * other_rate
    vat = (cif + discharge + duty) * vat_rate
    vat_credit = vat * credit_ratio

    landed_cash = cif + discharge + duty + other_tax + vat + inland_d + unload
    net_cash = landed_cash - vat_credit
    cash_out = duty + other_tax + (vat - vat_credit)
    unit_net = net_cash / purity * gross

    return {
        "term": term,
        "term_label": TERM_LABEL.get(term, term),
        "currency": cur,
        "fx": r6(fx_in),
        "quote": r6(quote),
        "purity": r6(purity),
        "goods_cny": r6(goods_cny),
        "inland_origin": r6(inland_o),
        "export_clear": r6(export_c),
        "freight": r6(freight),
        "insurance": r6(insurance),
        "cif": r6(cif),
        "discharge": r6(discharge),
        "duty": r6(duty),
        "other_tax": r6(other_tax),
        "vat": r6(vat),
        "vat_credit": r6(vat_credit),
        "inland_dest": r6(inland_d),
        "unload": r6(unload),
        "landed_cash": r6(landed_cash),
        "cash_out": r6(cash_out),
        "net_cash": r6(net_cash),
        "unit_net": r6(unit_net),
        "taxable": r6(cif + discharge + duty),
        "vat_rate": vat_rate,
        "includes": inc,
    }


# ------------------------------------------------------------------ 2. 可比价格
def comparable_price(cfg, cost=None):
    """把国内报价折算到「送到基准地 + 含税」的可比口径。

    「送到/出厂」与「含税/未税」两套维度必须分别声明：
      dom_term_incl_freight=True 表示源报价已是送到基准地价，不再加运费；
      dom_tax='含税' / '不含税' 决定是否乘 (1+vat_rate)。
    国内现货通例：华东/张家港「送到主港、含税、现汇」。
    """
    vat_rate = fnum(cfg.get("vat_rate"), 0.13)
    vat_rate = 0.13 if vat_rate is None else vat_rate
    dom_quote = fnum(cfg.get("dom_quote"), 0.0) or 0.0
    tax = (cfg.get("dom_tax") or "含税").strip()
    add_freight = 0.0 if bool(cfg.get("dom_term_incl_freight")) else (fnum(cfg.get("dom_freight_to_bench"), 0.0) or 0.0)
    adj = fnum(cfg.get("dom_scale_adj"), 0.0) or 0.0
    if tax in ("不含税", "未税"):
        net_price = dom_quote + add_freight + adj
        gross_price = net_price * (1 + vat_rate)
    else:
        gross_price = dom_quote + add_freight + adj
        net_price = gross_price / (1 + vat_rate)
    out = {
        "dom_quote": r6(dom_quote),
        "dom_freight_added": r6(add_freight),
        "dom_adj": r6(adj),
        "dom_price": r6(gross_price),
        "dom_net_price": r6(net_price),
        "dom_vat_in": r6(gross_price - net_price),
        "tax": tax,
        "vat_rate": vat_rate,
    }
    if cost is not None:
        out["cif"] = cost["cif"]
        out["cif_incl_vat"] = r6(cost["cif"] * (1 + vat_rate))
        out["gap_vs_landed_cash"] = r6(gross_price - cost["landed_cash"])
        out["gap_vs_net_cash"] = r6(gross_price - cost["net_cash"])
        out["gap_vs_cif"] = r6(net_price - cost["cif"])
    return out


# ------------------------------------------------------------------ 3. 价差四口径
GAP_DEFS = [
    ("G1_cif_vs_domnet", "CIF 折人民币 vs 国内未税",
     "国内未税送到 − 进口 CIF 折人民币",
     "纯价格口径：两边都不含增值税，反映国际与国内价格本身的高低"),
    ("G2_landedcash_vs_domallin", "含税到岸 vs 国内含税送到",
     "国内含税送到 − 进口含税到岸 landed_cash",
     "现金口径：两边都含税，反映全部现金付出之差"),
    ("G3_netcash_vs_domallin", "经济成本 vs 国内含税送到",
     "国内含税送到 − 进口经济成本 net_cash",
     "经济口径：进口增值税按可抵扣处理后的真实可比成本"),
    ("G4_vatadj", "进项税抵扣调整后",
     "国内未税送到 − 进口经济成本",
     "税制口径：看价格差里有多少来自增值税抵扣权的估值差异"),
]


def gap_table(bid_px, cost, comp):
    """正式四口径（带公式与含义），报告与 Excel 共用。"""
    if bid_px is None or cost is None or comp is None:
        return []
    out = []
    for code, name, formula, meaning in GAP_DEFS:
        if code == "G1_cif_vs_domnet":
            val = r6(comp["dom_net_price"] - cost["cif"])
        elif code == "G2_landedcash_vs_domallin":
            val = r6(bid_px - cost["landed_cash"])
        elif code == "G3_netcash_vs_domallin":
            val = r6(bid_px - cost["net_cash"])
        else:
            val = r6(comp["dom_net_price"] - cost["net_cash"])
        out.append({"code": code, "name": name, "formula": formula, "meaning": meaning, "value": val})
    return out


# ------------------------------------------------------------------ 4. 归因分解
COST_KEYS = ["goods_cny", "inland_origin", "export_clear", "freight", "insurance",
             "discharge", "duty", "other_tax", "vat_net", "inland_dest", "unload"]
COST_LABEL = {
    "goods_cny": "货值（报价折人民币）", "inland_origin": "出口国内陆运费",
    "export_clear": "出口报关杂费", "freight": "国际海运费", "insurance": "保险费",
    "discharge": "目的港卸货费", "duty": "关税", "other_tax": "其他税",
    "vat_net": "增值税净额（不可抵扣部分）", "inland_dest": "进口国内陆运费",
    "unload": "损耗/装卸附加",
}


def normalized_cost(c):
    d = dict(c)
    d["vat_net"] = (c["vat"] or 0.0) - (c["vat_credit"] or 0.0)
    return d


def contribution(a, b):
    """两套参数之间的逐项差额（元/吨，正值=该项使价差变大）。

    约定：价差 = 国内价 − 进口成本；成本项上升 => 价差下降，故取负号。
    闭合检验：−Δnet_cash 应等于各分项之和，残差 > 1e-6 说明有项重复或漏计。
    """
    na, nb = normalized_cost(a), normalized_cost(b)
    parts = {k: r6(-(nb[k] - na[k])) for k in COST_KEYS}
    total = nb["net_cash"] - na["net_cash"]
    parts["_total_cost_change"] = r6(total)
    parts["_sum"] = r6(sum(parts[k] for k in COST_KEYS))
    parts["_closure"] = r6(-total - parts["_sum"])
    return parts


# ------------------------------------------------------------------ 5. 市场隐含
def implied_other_costs(bid_px, cif_cny, freight_cny, insurance_cny, discharge_cny):
    """市场隐含的「其余全部成本」（不含税）：
       残差 = 国内价 − CIF − 运费 − 保险 − 卸货
    = 关税 + 增值税净额 + 资金占用 + 损耗 + 通道价差 + 港口杂费。
    长期观测这个残差可与自建参数互相校验：残差突变先怀疑参数取错。
    """
    if bid_px is None or cif_cny is None:
        return None
    return r6(bid_px - cif_cny - (freight_cny or 0.0)
              - (insurance_cny or 0.0) - (discharge_cny or 0.0))


# ------------------------------------------------------------------ 6. 敏感性
SENS_KEY_MAP = {
    "freight": "ocean_freight",
    "fx": "fx_usdcny",
    "duty": "duty_rate",
    "vat": "vat_rate",
    "insurance_pct": "insurance_rate_pct",
    "credit": "vat_credit_ratio",
    "discharge": "discharge_fee",
    "inland_dest": "inland_dest",
    "price": "price_quote",
    "term": "term",
}


def sensitivity_one(base_params, key, values):
    """单参数敏感性：values = [(label, v), ...]；v 可为数值或术语字符串。"""
    base = import_cost(base_params)
    pkey = SENS_KEY_MAP.get(key, key)
    out = []
    for label, val in values:
        p = dict(base_params)
        p[pkey] = val
        res = import_cost(p)
        out.append({
            "key": key, "label": label, "value": val,
            "cif": res["cif"], "landed_cash": res["landed_cash"], "net_cash": res["net_cash"],
            "delta_vs_base": r6(res["net_cash"] - base["net_cash"]),
        })
    return out


# ------------------------------------------------------------------ 7. 口径守卫
def check_terms(p):
    term = norm_term(p.get("term"))
    inc = TERM_INCLUDES[term]
    issues = []
    for flag, (key, label) in TERM_GUARDED.items():
        if inc[flag]:
            val = fnum(p.get(key), 0.0) or 0.0
            if val > 0:
                issues.append({
                    "level": "error",
                    "code": "DOUBLE_COUNT_" + key.upper(),
                    "msg": "%s 报价已包含「%s」，参数里又填了 %.4g；为避免重复计费，该项已按 0 处理。"
                           "请把术语改成不含该项的口径，或删除该参数。" % (term, label, val),
                })
    return issues


def check_config(cfg):
    issues = []
    vat = fnum(cfg.get("vat_rate"), 0.13)
    if vat is None or not (0 <= vat < 1):
        issues.append({"level": "error", "code": "VAT_RANGE", "msg": "增值税率必须落在 [0,1)"})
    cr = fnum(cfg.get("vat_credit_ratio"), 1.0)
    if cr is None or not (0 <= cr <= 1):
        issues.append({"level": "error", "code": "CREDIT_RANGE", "msg": "可抵扣比例必须落在 [0,1]"})
    if (fnum(cfg.get("price_quote"), 0.0) or 0.0) <= 0:
        issues.append({"level": "error", "code": "QUOTE_POSITIVE", "msg": "海外报价必须为正"})
    cur = (cfg.get("currency") or "USD").upper()
    fx = fnum(cfg.get("fx_usdcny"), 0.0) or 0.0
    if cur == "USD" and not (4 <= fx <= 12):
        issues.append({"level": "error", "code": "FX_RANGE",
                       "msg": "USD/CNY=%.4f 不在 4~12 的合理区间，通不过自检" % fx})
    dq = fnum(cfg.get("dom_quote"), 0.0)
    if dq is None or dq == 0:
        issues.append({"level": "warn", "code": "DOM_QUOTE",
                       "msg": "国内现货价未填：价差全部为空，报告降级为只有成本折算"})
    return issues


# ------------------------------------------------------------------ 8. 序列工具
def series_prev(series, date_iso, max_stale_days=None):
    """取 <= date_iso 的最近一个值，返回 (value, value_date)；超龄返回 (None, None)。"""
    if not series:
        return None, None
    best = None
    for d in series:
        if d <= date_iso and (best is None or d > best):
            best = d
    if best is None:
        return None, None
    if max_stale_days is not None:
        import datetime as _dt
        a = _dt.date.fromisoformat(str(date_iso)[:10])
        b = _dt.date.fromisoformat(str(best)[:10])
        if (a - b).days > max_stale_days:
            return None, None
    return series[best], best


def change_stats(points, key="gap_net_cash"):
    """points: [{'date':..., key:...}]；返回首末/极值/均值统计。"""
    pts = [p for p in points if p.get(key) is not None]
    if len(pts) < 2:
        return None
    vals = [p[key] for p in pts]
    i_max = vals.index(max(vals))
    i_min = vals.index(min(vals))
    return {
        "n": len(pts),
        "start_date": pts[0]["date"], "start": r6(vals[0]),
        "end_date": pts[-1]["date"], "end": r6(vals[-1]),
        "change": r6(vals[-1] - vals[0]),
        "max": r6(max(vals)), "max_date": pts[i_max]["date"],
        "min": r6(min(vals)), "min_date": pts[i_min]["date"],
        "avg": r6(sum(vals) / len(vals)),
    }
