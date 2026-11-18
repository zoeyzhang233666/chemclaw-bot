#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_engine.py — 出口报价计算引擎（FCA / FAS / FOB / CFR / CIF / CPT / CIP / DAP / DPU / DDP）

设计原则（与 SKILL.md 完全一致）：
1. 只算不猜：任何未输入的费率一律 None + status="missing"，不外推、不取行业惯例、不套用默认运费。
2. 单位统一：内部一律以「人民币元 / 吨」归一；总价 = 吨价 × 数量(吨)，装柜吨数单独给出。
3. 毛利可逆：毛利率（on selling price）与成本加成率（on cost）严格区分，互为反解。
4. 费用不重复：每条费用行只归入一个成本段，术语价 = 对应段之和。
5. 溯源：每条费用行带 source（user / forwarder_quote / rate_library / sim / pending）与 basis。

术语依据：Incoterms® 2020（ICC）。
  - CIF：保险最低为合同价值 × 110%，默认 ICC(C)（ICC 官方）。
  - CIF/CFR/FOB：风险在装运港货物装上船（on board）时转移。
  - CPT/CIP：风险在货交第一承运人时转移；CIP 要求保险至少 ICC(A)。
  - DAP/DPU/DDP：风险在目的地交付时转移；DDP 卖方承担进口关税，且可能需在进口国做税务登记。

用法：
  python calc_engine.py input.json [-o result.json] [--out-csv result.csv] [--sens freight|fx|gp] [--term CIF]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field, asdict, fields

VERSION = "1.0.0"

# ----------------------------------------------------------------------------
# 成本段与术语
# ----------------------------------------------------------------------------
# 成本段：固定顺序，代表「从工厂到目的地的费用链」中的一段。
SEGMENTS = [
    ("S1", "出厂基础", "出厂价（不含包装、不含出口环节费用）"),
    ("S2", "包装", "包装成本（吨价口径）"),
    ("S3", "内陆运输至起运港", "工厂→港口的内陆运费等"),
    ("S4", "出口港务及报关", "THC、报关、单证、码头作业、订舱等"),
    ("S5", "国际海运", "海运费（至目的港/目的地）"),
    ("S6", "海运保险", "保险费"),
    ("S7", "出口环节税费", "出口关税、其他出口税费（增值税退税单列，不进此段）"),
    ("S8", "其他出口费用", "结汇/银行费、检验、认证、配额、特殊包装等"),
    ("S9", "目的地及进口环节", "目的港费用、进口清关、进口关税/进口增值税（仅 D 组）"),
]

# 术语 → (含哪些成本段, 一句话说明, 风险转移点)
TERMS: dict[str, tuple[list[str], str, str]] = {
    "FCA": (["S1", "S2", "S3"], "货交承运人（卖方场所或指定点）；任何运输方式；出口清关由卖方负责",
            "货交买方指定承运人时（若在卖方场所，装上买方车辆后即为交付）"),
    "FAS": (["S1", "S2", "S3"], "船边交货（起运港）；卖方将货置于买方指定船舶旁",
            "货物置于船舶旁（alongside the vessel）时"),
    "FOB": (["S1", "S2", "S3", "S4"], "装运港船上交货；卖方承担至货物装上船为止的费用",
            "货物在装运港装上船（on board）时转移给买方"),
    "CFR": (["S1", "S2", "S3", "S4", "S5"], "成本加运费（目的港）；卖方付海运费，风险仍在装运港转移",
            "货物在装运港装上船（on board）时转移给买方"),
    "CIF": (["S1", "S2", "S3", "S4", "S5", "S6"], "成本、保险加运费（目的港）；卖方投保，最低合同价×110%，默认 ICC(C)",
            "货物在装运港装上船（on board）时转移给买方"),
    "CPT": (["S1", "S2", "S3", "S4", "S5"], "运费付至（指定目的地）；任何运输方式；卖方付主运费",
            "货交第一承运人时转移给买方"),
    "CIP": (["S1", "S2", "S3", "S4", "S5", "S6"], "运费加保险付至（指定目的地）；CIP 要求至少 ICC(A) 或同类条款",
            "货交第一承运人时转移给买方"),
    "DAP": (["S1", "S2", "S3", "S4", "S5", "S6", "S9"], "目的地交货（未卸货）；卖方承担运输风险至目的地",
            "货物在目的地（运输工具上，待卸）置于买方处置时转移"),
    "DPU": (["S1", "S2", "S3", "S4", "S5", "S6", "S9"], "目的地卸货后交货；卖方须在目的地完成卸货",
            "货物在目的地卸货完成、置于买方处置时转移"),
    "DDP": (["S1", "S2", "S3", "S4", "S5", "S6", "S9"], "完税后交货；卖方承担出口与进口清关、进口关税",
            "货物在目的地（已完成进口清关）置于买方处置时转移；卖方承担进口关税"),
}

# 术语 → 卖方必须自行提供的成本键（缺则术语价不可得）
TERM_REQUIRES = {
    "FCA": ["S1"], "FAS": ["S1", "S3"], "FOB": ["S5"],
    "CFR": [], "CIF": [], "CPT": [], "CIP": [],
    "DAP": ["DEST"], "DPU": ["DEST"], "DDP": ["DEST", "IMPORT_DUTY"],
}

# 需要目的地/进口环节成本的术语
TERMS_NEED_DEST = {"DAP", "DPU", "DDP"}


def _num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


# ----------------------------------------------------------------------------
# 数据结构
# ----------------------------------------------------------------------------
@dataclass
class QuoteInput:
    # —— 产品与数量 ——
    product_cn: str = ""
    product_en: str = ""
    spec: str = ""
    hs_code: str = ""
    quantity_mt: float | None = None
    unit: str = "吨"

    # —— 主体 ——
    factory_place: str = ""
    pol: str = ""
    pod: str = ""

    # —— 汇率 ——
    fx_to_cny: dict = field(default_factory=dict)
    quote_currency: str = "USD"

    # —— 成本（人民币元/吨，除非另注）——
    exw_cny_per_t: float | None = None
    packaging_cny_per_t: float | None = None
    inland_cny_per_t: float | None = None
    port_cny_per_t: float | None = None

    # 海运费：任选一种
    freight_usd_per_container: float | None = None
    container_load_mt: float | None = None
    freight_cny_per_t: float | None = None

    # 保险费：CIF 的百分比（如 0.3 表示 0.3%）
    insurance_rate_of_cif: float | None = None
    insurance_floor_cny: float | None = None   # 保单最低保费（整票），元

    export_tax_cny_per_t: float | None = None
    other_cny_per_t: float | None = None

    # 目的地/进口环节（仅 D 组）
    dest_port_cny_per_t: float | None = None
    import_duty_pct: float | None = None         # 进口关税按到岸价百分比
    import_vat_pct: float | None = None          # 进口增值税率（DDP 若承担）

    # —— 毛利 ——
    gp_mode: str = "margin_on_price"   # margin_on_price / markup_on_cost / manual_price
    gp_value: float | None = None
    manual_price_cny_per_t: float | None = None
    gp_basis_term: str = "FOB"

    # —— 贸易术语 ——
    terms_of_interest: list = field(default_factory=lambda: ["FOB", "CFR", "CIF"])

    # —— 退税（单列）——
    refund_enabled: bool = False
    refund_rate_pct: float | None = None
    vat_rate_pct: float = 13.0
    input_tax_included: bool = False   # 出厂成本是否为含税价（影响退税计税依据）

    # —— 价格小数位（报价展示口径，不改变内部精度）——
    price_decimals: int = 2


@dataclass
class Line:
    """一条费用行（人民币元/吨，缺失为 None）"""
    code: str
    name_cn: str
    name_en: str
    segment: str
    amount: float | None = None
    status: str = "missing"     # filled / missing / not_required / assumed(仅模拟)
    source: str = "pending"     # user / forwarder_quote / rate_library / sim / pending
    basis: str = ""
    liability: str = ""         # seller / buyer
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.amount is not None and self.status == "filled"

    def d(self):
        return asdict(self)


# ----------------------------------------------------------------------------
# 构建费用行
# ----------------------------------------------------------------------------
def build_lines(inp: QuoteInput) -> list[Line]:
    fx = inp.fx_to_cny or {}
    q = _num(inp.quantity_mt)
    usd_fx = fx.get("USD")
    lines: list[Line] = []

    # S1 出厂
    v = _num(inp.exw_cny_per_t)
    lines.append(Line("EXW", "出厂价（不含包装）", "Ex-works price excl. packaging", "S1", v,
                      "filled" if v is not None else "missing",
                      "user" if v is not None else "pending",
                      "用户输入，元/吨；不含包装、不含出口环节费用",
                      "seller"))

    # S2 包装
    v = _num(inp.packaging_cny_per_t)
    lines.append(Line("PKG", "包装成本", "Packaging cost", "S2", v,
                      "filled" if v is not None else "missing",
                      "user" if v is not None else "pending",
                      "用户输入，元/吨（袋装/吨袋/托盘等折算吨价）",
                      "seller"))

    # S3 内陆运输
    v = _num(inp.inland_cny_per_t)
    lines.append(Line("INLAND", "内陆运输（工厂→起运港）", "Inland haulage to port of shipment", "S3", v,
                      "filled" if v is not None else "missing",
                      "user" if v is not None else "pending",
                      "货代报价或用户输入，元/吨",
                      "seller（FCA 卖方场所交货除外）"))

    # S4 港口及报关
    v = _num(inp.port_cny_per_t)
    lines.append(Line("PORT", "港口及报关费用", "Export port charges & customs clearance", "S4", v,
                      "filled" if v is not None else "missing",
                      "user" if v is not None else "pending",
                      "货代报价或用户输入，元/吨（THC、报关、单证、码头作业等）",
                      "seller"))

    # S5 海运费
    f_usd = _num(inp.freight_usd_per_container)
    load = _num(inp.container_load_mt)
    f_cny = _num(inp.freight_cny_per_t)
    if f_cny is not None:
        lines.append(Line("FREIGHT", "海运费（起运港→目的港）", "Ocean freight to port of destination", "S5",
                          f_cny, "filled", "user", "用户输入，元/吨", "seller（CFR/CIF/CPT/CIP/D 组）"))
    elif f_usd is not None and usd_fx and load:
        val = f_usd * usd_fx / load
        lines.append(Line("FREIGHT", "海运费（起运港→目的港）", "Ocean freight to port of destination", "S5",
                          val, "filled", "forwarder_quote",
                          f"{f_usd:,.2f} USD/柜 × {usd_fx:.4f} ÷ {load:g} 吨/柜 = {val:,.2f} 元/吨",
                          "seller（CFR/CIF/CPT/CIP/D 组）"))
    else:
        why = "未提供货代报价"
        if f_usd is not None and not usd_fx:
            why = "有 USD/柜 报价但缺 USD 汇率"
        if f_usd is not None and not load:
            why = "有柜价但缺装柜吨数"
        lines.append(Line("FREIGHT", "海运费（起运港→目的港）", "Ocean freight to port of destination", "S5",
                          None, "missing", "pending", why, "seller（CFR/CIF/CPT/CIP/D 组）"))

    # S6 保险费（占位，用 CIF 自洽式在 compute 中求值）
    r = _num(inp.insurance_rate_of_cif)
    lines.append(Line("INSURANCE", "海运保险费", "Marine cargo insurance premium", "S6", None,
                      "filled" if r is not None else "missing",
                      "user" if r is not None else "pending",
                      "费率 × 投保金额（CIF×110%）；最低保费另按票分摊" if r is not None else "未提供保险费率",
                      "seller（CIF/CIP 必投；其他术语由买方投保）"))

    # S7 出口税
    v = _num(inp.export_tax_cny_per_t)
    lines.append(Line("EXPORT_TAX", "出口关税及其他出口税费", "Export duty & other export taxes", "S7", v,
                      "filled" if v is not None else "missing",
                      "user" if v is not None else "pending",
                      "用户输入，元/吨；增值税出口退税不在此列",
                      "seller"))

    # S8 其他
    v = _num(inp.other_cny_per_t)
    lines.append(Line("OTHER", "其他出口费用", "Other export costs", "S8", v,
                      "filled" if v is not None else "missing",
                      "user" if v is not None else "pending",
                      "用户输入，元/吨（结汇费、检验、认证、配额等）",
                      "seller"))

    # S9 目的地（仅 D 组需要）
    need_dest = any(t.upper() in TERMS_NEED_DEST for t in inp.terms_of_interest)
    v = _num(inp.dest_port_cny_per_t)
    lines.append(Line("DEST_PORT", "目的港费用 / 目的地交货费用", "Destination port & delivery charges", "S9", v,
                      "filled" if v is not None else ("missing" if need_dest else "not_required"),
                      "user" if v is not None else ("pending" if need_dest else "not_required"),
                      "DAP/DPU/DDP 卖方承担；F/C 组由买方承担、不计入卖方成本",
                      "seller（D 组）/ buyer（F/C 组）"))

    return lines


def _segsum(lines: list[Line], segs: list[str]) -> tuple[float | None, list[Line]]:
    sub = [l for l in lines if l.segment in segs]
    miss = [l for l in sub if not l.ok]
    if miss:
        return None, miss
    return sum(l.amount for l in sub), []


# ----------------------------------------------------------------------------
# 主计算
# ----------------------------------------------------------------------------
def _insurance_solution(cfr_cost: float | None, rate_pct: float | None,
                        floor_cny: float | None, q: float | None) -> tuple[float | None, str]:
    """
    保险费按 CIF 价为基础、投保金额为 CIF×110% 自洽求解：
        C = CFR + 1.10rC  =>  C = CFR / (1 - 1.10r)；保险费 = 1.10rC = CFR·1.10r/(1-1.10r)
    若保单有整票最低保费，则取 max(按费率算出的保费, 最低保费/吨)。
    """
    if cfr_cost is None or rate_pct is None:
        return None, "缺海运费或保险费率"
    r = rate_pct / 100.0
    if 1.10 * r >= 1:
        return None, "保险费率过高（≥90.9%），自洽式无解"
    ins = cfr_cost * (1.10 * r) / (1 - 1.10 * r)
    basis = f"CIF×110%×{rate_pct:.4f}% 自洽解 = {ins:.4f} 元/吨"
    if floor_cny is not None and q:
        floor_t = floor_cny / q
        if floor_t > ins:
            ins = floor_t
            basis = f"触发保单最低保费：{floor_cny:,.2f} 元 ÷ {q:g} 吨 = {floor_t:.4f} 元/吨"
    return ins, basis


def compute(inp: QuoteInput) -> dict:
    fx = inp.fx_to_cny or {}
    cur = (inp.quote_currency or "USD").upper()
    fx_rate = _num(fx.get(cur))
    q = _num(inp.quantity_mt)
    if q is not None and q <= 0:
        q = None

    lines = build_lines(inp)
    L = {l.code: l for l in lines}
    terms = [t.upper() for t in (inp.terms_of_interest or ["FOB", "CFR", "CIF"])]
    if inp.gp_basis_term:
        terms = list(dict.fromkeys([inp.gp_basis_term.upper()] + terms))

    seg = {code: _segsum(lines, [code]) for code, _n, _d in SEGMENTS}

    # —— 递推：FOB 成本 → CFR = FOB + 海运 → CIF = CFR + 保险（自洽）——
    fob_groups = ["S1", "S2", "S3", "S4", "S7", "S8"]
    fob_parts = {g: seg[g][0] for g in fob_groups}
    fob_missing = [l for g in fob_groups for l in seg[g][1]]
    fob_cost = None if any(v is None for v in fob_parts.values()) else sum(fob_parts.values())

    freight = seg["S5"][0]
    cfr_cost = None if (fob_cost is None or freight is None) else fob_cost + freight

    ins, ins_basis = _insurance_solution(cfr_cost, _num(inp.insurance_rate_of_cif),
                                         _num(inp.insurance_floor_cny), q)
    if ins is not None:
        L["INSURANCE"].amount = ins
        L["INSURANCE"].basis = ins_basis
        L["INSURANCE"].status = "filled"

    # S6 段金额以求解后的保险费为准（占位行同步更新）
    seg["S6"] = (ins, [] if ins is not None else ([L["INSURANCE"]] if L["INSURANCE"].status == "missing" else []))

    cif_cost = None if (cfr_cost is None or ins is None) else cfr_cost + ins

    # FCA（卖方场所交货）：出厂 + 包装 + 装车，不含 S3/S4
    fca_groups = ["S1", "S2"]
    fca_cost = None if any(seg[g][0] is None for g in fca_groups) else sum(seg[g][0] for g in fca_groups)

    # FAS：S1+S2+S3
    fas_cost = None if any(seg[g][0] is None for g in ["S1", "S2", "S3"]) else sum(seg[g][0] for g in ["S1", "S2", "S3"])

    # D 组：CFR + 保险 + 目的地费用 + 进口关税（按 CFR 或 CIF 百分比，显式给出才计）
    dest = seg["S9"][0]
    duty = None
    if _num(inp.import_duty_pct) is not None and cif_cost is not None:
        duty = cif_cost * _num(inp.import_duty_pct) / 100.0
    d_cost = None
    if cif_cost is not None and dest is not None:
        d_cost = cif_cost + dest + (duty or 0.0)

    base_costs = {
        "FCA": fca_cost, "FAS": fas_cost, "FOB": fob_cost, "CFR": cfr_cost, "CIF": cif_cost,
        "CPT": cfr_cost, "CIP": cif_cost,
        "DAP": d_cost, "DPU": d_cost, "DDP": d_cost,
    }

    # —— 毛利与报价 ——
    mode = inp.gp_mode
    gv = _num(inp.gp_value)
    gp = {}
    for t in terms:
        c = base_costs.get(t)
        pf = {"term": t, "cost_cny_per_t": c}
        if c is None:
            pf.update({"price_cny_per_t": None, "gp_cny_per_t": None, "margin": None,
                       "markup": None, "price_fx_per_t": None, "total_cny": None,
                       "total_fx": None, "gp_total_cny": None, "blocked_by": "成本不完整"})
            gp[t] = pf
            continue
        price = None
        if mode == "margin_on_price":
            if gv is not None and 0 <= gv < 1:
                price = c / (1 - gv)
        elif mode == "markup_on_cost":
            if gv is not None and gv > -1:
                price = c * (1 + gv)
        elif mode == "manual_price":
            price = _num(inp.manual_price_cny_per_t)
        if price is None or price <= 0:
            pf.update({"price_cny_per_t": None, "gp_cny_per_t": None, "margin": None,
                       "markup": None, "price_fx_per_t": None, "total_cny": None,
                       "total_fx": None, "gp_total_cny": None, "blocked_by": "毛利/价格未设定"})
            gp[t] = pf
            continue
        g = price - c
        dec = int(inp.price_decimals or 2)
        price_r = round(price, dec)
        g_r = price_r - c
        pf.update({
            "price_cny_per_t": price_r,
            "price_raw_cny_per_t": price,
            "gp_cny_per_t": g_r,
            "gp_on_raw_cny_per_t": g,
            "margin": (g_r / price_r) if mode != "manual_price" else (g_r / price_r),
            "markup": (g_r / c) if c else None,
            "price_fx_per_t": (round(price_r / fx_rate, 2) if fx_rate else None),
            "total_cny": (round(price_r * q, 2) if q else None),
            "total_fx": (round(price_r / fx_rate * q, 2) if (fx_rate and q) else None),
            "gp_total_cny": (round(g_r * q, 2) if q else None),
            "cost_total_cny": (round(c * q, 2) if q else None),
        })
        gp[t] = pf

    # —— 缺项清单 ——
    missing = [{"code": l.code, "name": l.name_cn, "segment": l.segment, "why": l.basis}
               for l in lines if l.status == "missing"]
    if q is None:
        missing.append({"code": "QTY", "name": "出口数量", "segment": "-", "why": "未提供（无法算总价）"})
    if fx_rate is None:
        missing.append({"code": "FX", "name": f"汇率 {cur}/CNY", "segment": "-", "why": "未提供（无法出外币价）"})

    # —— 退税（单列，不自动抵减）——
    refund = _refund(inp, fob_cost, q)

    # —— 一致性校验 ——
    warnings = []
    if L["EXPORT_TAX"].status == "missing":
        warnings.append("出口税费未填：按缺失处理（不自动按 0 计）。HS 2836200000（碳酸钠）出口关税为 0%（海关公示，见 references/03），但其他出口环节税费仍应由用户确认。")
    if L["INSURANCE"].status == "missing":
        warnings.append("保险费率未填：CIF 不可得；请取保险公司/货代报价，或以「模拟情景」录入并标注 SIMULATED。")
    if mode == "margin_on_price" and gv is not None and gv >= 0.9:
        warnings.append("毛利率 ≥ 90%：请确认是否误用了成本加成率口径。")
    if mode == "markup_on_cost" and gv is not None and gv >= 1:
        warnings.append("成本加成率 ≥ 100%：请确认口径（加成率基于成本，毛利率基于售价）。")
    if refund.get("enabled") and refund.get("refund_rate_pct") is None:
        warnings.append("已勾选退税但退税率为空：不得默认 13%，请按商品代码核对退税率。")

    return {
        "engine_version": VERSION,
        "input": {
            "product_cn": inp.product_cn, "product_en": inp.product_en, "spec": inp.spec,
            "hs_code": inp.hs_code, "quantity_mt": inp.quantity_mt, "unit": inp.unit,
            "factory_place": inp.factory_place, "pol": inp.pol, "pod": inp.pod,
            "currency": cur, "fx_rate": fx_rate, "gp_mode": mode, "gp_value": inp.gp_value,
            "gp_basis_term": (inp.gp_basis_term or "").upper(),
            "terms": terms,
        },
        "lines": [l.d() for l in lines],
        "segments": {c: {"name": n, "sum_cny_per_t": seg[c][0],
                         "missing": [l.code for l in seg[c][1]]} for c, n, _d in SEGMENTS},
        "terms": {t: {"segments": TERMS[t][0], "note": TERMS[t][1], "risk": TERMS[t][2],
                      "cost_cny_per_t": base_costs.get(t)} for t in TERMS},
        "quotes": gp,
        "missing": missing,
        "warnings": warnings,
        "refund": refund,
        "identity_checks": {
            "cfr_eq_fob_plus_freight": _chk(cfr_cost, None if fob_cost is None or freight is None else fob_cost + freight),
            "cif_eq_cfr_plus_insurance": _chk(cif_cost, None if cfr_cost is None or ins is None else cfr_cost + ins),
            "insurance_eq_110pct_cif_times_rate": _chk(
                ins, None if (cif_cost is None or inp.insurance_rate_of_cif is None)
                else cif_cost * 1.10 * inp.insurance_rate_of_cif / 100.0, tol=1e-6),
            # 测量口径恒等式（定义式，用于交叉验证）
            "check_margin_eq_gp_over_price": {t: _chk(
                gp[t]["margin"],
                (gp[t]["gp_cny_per_t"] / gp[t]["price_cny_per_t"]) if gp[t]["price_cny_per_t"] else None)
                for t in gp},
            "check_markup_eq_gp_over_cost": {t: _chk(
                gp[t]["markup"],
                (gp[t]["gp_cny_per_t"] / gp[t]["cost_cny_per_t"]) if gp[t]["cost_cny_per_t"] else None)
                for t in gp},
            # 毛利率与加成率必须满足：(1+加成率)(1-毛利率) = 1
            "check_margin_markup_relation": {t: _chk(
                None if (gp[t]["margin"] is None or gp[t]["markup"] is None) else
                (1 + gp[t]["markup"]) * (1 - gp[t]["margin"]), 1.0)
                for t in gp},
        },
    }


def _chk(a, b, tol=1e-9):
    if a is None or b is None:
        return {"ok": None}
    return {"ok": abs(a - b) <= max(tol, abs(a) * 1e-9), "a": a, "b": b}


def _refund(inp: QuoteInput, fob_cost: float | None, q: float | None) -> dict:
    """
    出口退税（单列）：依据 财政部 税务总局公告 2026 年第 11 号
      - 生产企业 免抵退：免抵退税额 = 出口离岸价(FOB) × 汇率 × 退税率
      - 外贸企业 免退税：应退税额 = 购进增值税专用发票金额 × 退税率
    本函数只算「理论退税额」，默认不计入报价成本；需用户显式确认口径。
    """
    out: dict = {"enabled": bool(inp.refund_enabled),
                 "note": "退税是现金流回收（通常滞后），不是当期成本；是否计入报价须由销售与财务确认。"}
    rate = _num(inp.refund_rate_pct)
    if not inp.refund_enabled:
        out["reason"] = "未启用"
        return out
    if fob_cost is None or q is None:
        out["reason"] = "FOB 成本或数量未就绪"
        return out
    if rate is None:
        out["reason"] = "退税率为空：不得默认 13%，需按商品代码核对退税率文库"
        return out
    vat = _num(inp.vat_rate_pct) or 13.0
    if inp.input_tax_included:
        base = fob_cost / (1 + vat / 100.0)
        out["input_tax_basis"] = f"出厂成本含 {vat:g}% 增值税 → 不含税 {base:,.2f} 元/吨"
    else:
        base = fob_cost
        out["input_tax_basis"] = "出厂成本为不含税价"
    out.update({
        "refund_rate_pct": rate,
        "refund_cny_per_t": round(base * rate / 100.0, 4),
        "refund_total_cny": round(base * rate / 100.0 * q, 2),
        "formula": "退税额 = 计税依据 × 退税率",
    })
    return out


# ----------------------------------------------------------------------------
# 敏感性
# ----------------------------------------------------------------------------
def sensitivity(inp: QuoteInput, kind: str, term: str = "CIF",
                pcts: list[float] | None = None) -> dict:
    pcts = pcts or [-20, -10, 0, 10, 20]
    rows = []
    for p in pcts:
        g = QuoteInput(**asdict(inp))
        if kind == "freight":
            if g.freight_cny_per_t is not None:
                g.freight_cny_per_t *= (1 + p / 100.0)
            elif g.freight_usd_per_container is not None:
                g.freight_usd_per_container *= (1 + p / 100.0)
            else:
                continue
        elif kind == "fx":
            g.fx_to_cny = {k: v * (1 + p / 100.0) for k, v in (g.fx_to_cny or {}).items()}
        elif kind == "gp":
            if g.gp_mode == "margin_on_price":
                g.gp_value = max(0.0, (g.gp_value or 0) + p / 100.0)
            else:
                g.gp_value = (g.gp_value or 0) * (1 + p / 100.0)
        else:
            raise ValueError(f"未知敏感性参数: {kind}")
        r = compute(g)
        qr = r["quotes"].get(term.upper(), {})
        rows.append({"pct": p, "price_cny_per_t": qr.get("price_cny_per_t"),
                     "price_fx_per_t": qr.get("price_fx_per_t"),
                     "margin": qr.get("margin"), "total_cny": qr.get("total_cny")})
    return {"param": kind, "term": term.upper(), "rows": rows}


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def load_input(path: str) -> QuoteInput:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    known = {f.name for f in fields(QuoteInput)}
    return QuoteInput(**{k: v for k, v in raw.items() if k in known})


def dump_csv(result: dict, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["成本段", "代码", "成本项", "英文", "金额(元/吨)", "状态", "来源", "依据", "承担方"])
        for l in result["lines"]:
            w.writerow([l["segment"], l["code"], l["name_cn"], l["name_en"],
                        "" if l["amount"] is None else round(l["amount"], 4),
                        l["status"], l["source"], l["basis"], l["liability"]])
        w.writerow([])
        w.writerow(["术语", "成本(元/吨)", "报价(元/吨)", "外币/吨", "毛利率", "加成率", "总价(CNY)", "总价(外币)"])
        for t, r in result["quotes"].items():
            w.writerow([t, _r(r["cost_cny_per_t"]), _r(r["price_cny_per_t"]), _r(r["price_fx_per_t"]),
                        "" if r["margin"] is None else f"{r['margin']*100:.4f}%",
                        "" if r["markup"] is None else f"{r['markup']*100:.4f}%",
                        _r(r["total_cny"]), _r(r["total_fx"])])


def _r(x):
    return "" if x is None else round(x, 4)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="出口报价计算引擎")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--out-csv", default="")
    ap.add_argument("--sens", default="", choices=["", "freight", "fx", "gp"])
    ap.add_argument("--term", default="CIF")
    a = ap.parse_args(argv)
    res = compute(load_input(a.input))
    if a.sens:
        res["sensitivity"] = sensitivity(load_input(a.input), a.sens, a.term)
    text = json.dumps(res, ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[ok] {a.out}")
    else:
        print(text)
    if a.out_csv:
        dump_csv(res, a.out_csv)
        print(f"[ok] {a.out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
