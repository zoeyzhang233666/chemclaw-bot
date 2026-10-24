# -*- coding: utf-8 -*-
"""
landed_cost_engine.py — 进口到厂成本计算引擎（唯一计算口径）
================================================================
本文件是 HTML 计算器、Excel 工作簿与批量验证脚本的**唯一计算真相源**。
其余三端的所有公式都必须能在此复现；不一致即为缺陷。

核心原则
--------
1. Incoterms 2020 决定"哪些费用已经包含在报价中"，避免重复计费；
2. 未填 ≠ 0：缺失关键费用时输出 `status="待补全"`，并给出 gaps 清单；
3. 双汇率：市场参考汇率（购汇）与海关计征汇率（计税）分别使用；
4. 增值税分栏：现金支出 / 可抵扣进项税额 / 不可抵扣进入成本；
5. 所有派生值都可回溯到公式字符串（`formulas` 字段）。

用法
----
    from landed_cost_engine import LandedCostInput, land_cost
    res = land_cost(LandedCostInput.from_dict(data))
    res.to_json()
或命令行：
    python landed_cost_engine.py --input ../examples/case_cif_jea_ningbo.json --pretty
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
from dataclasses import dataclass, field
from typing import Any, Optional

# --------------------------------------------------------------------------------------
# 0. 常量：仅放"规则本身"，不放任何产品成本 / 运费
# --------------------------------------------------------------------------------------
INCOTERMS_2020: dict[str, dict[str, bool]] = {
    # seller_pays: export 出口报关费, freight 主运费, insurance 保险, duty 关税/进口清关, inland 目的港后内陆运输
    "EXW": dict(export=False, freight=False, insurance=False, duty=False, inland=False),
    "FCA": dict(export=True, freight=False, insurance=False, duty=False, inland=False),
    "FAS": dict(export=True, freight=False, insurance=False, duty=False, inland=False),
    "FOB": dict(export=True, freight=False, insurance=False, duty=False, inland=False),
    "CFR": dict(export=True, freight=True, insurance=False, duty=False, inland=False),
    "CIF": dict(export=True, freight=True, insurance=True, duty=False, inland=False),
    "CPT": dict(export=True, freight=True, insurance=False, duty=False, inland=False),
    "CIP": dict(export=True, freight=True, insurance=True, duty=False, inland=False),
    "DAP": dict(export=True, freight=True, insurance=False, duty=False, inland=True),
    "DPU": dict(export=True, freight=True, insurance=False, duty=False, inland=True),
    "DDP": dict(export=True, freight=True, insurance=True, duty=True, inland=True),
}

# FOB 及以前的术语 = 报价不含主运费
NO_FREIGHT_TERMS = {"EXW", "FCA", "FAS", "FOB"}
# 不含保险的术语
NO_INSURANCE_TERMS = {"EXW", "FCA", "FAS", "FOB", "CFR", "CPT", "DAP", "DPU"}

# 海关"保险费未发生或无法确定"的法定比例（213 号令第三十六条）
CUSTOMS_INSURANCE_RATE = 0.003

DEFAULT_THRESHOLDS = {"fx": 0.03, "freight": 0.20, "quantity": 0.50}


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _n(x: Any, default: Optional[float] = None) -> Optional[float]:
    """把输入规整成 float 或 None（空字符串/None/'待确认' -> None）。"""
    if x is None or x == "" or (isinstance(x, str) and x.strip() in ("", "-", "待确认", "TBC")):
        return default
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


# --------------------------------------------------------------------------------------
# 1. 输入模型
# --------------------------------------------------------------------------------------
@dataclass
class LandedCostInput:
    # 报价
    currency: str = "USD"
    incoterm: str = "FOB"
    incoterm_version: str = "2020"
    incoterm_place: str = ""
    unit_price: Optional[float] = None
    price_unit: str = "MT"          # MT | CONTAINER
    quantity: Optional[float] = None
    quantity_unit: str = "MT"
    packing_included: bool = True

    # 商品
    product: str = ""
    spec: str = ""
    hs_code: str = ""
    origin_country: str = ""
    destination_port: str = ""
    final_address: str = ""
    containers_20: int = 0
    containers_40: int = 0

    # 汇率
    fx_market_rate: Optional[float] = None
    fx_market_type: str = ""
    fx_market_date: str = ""
    fx_market_source: str = ""
    fx_customs_rate: Optional[float] = None
    fx_customs_date: str = ""
    fx_customs_source: str = ""

    # 境外 / 运费 / 保险（币种 = currency）
    origin_charges: Optional[float] = None        # 报价不含时另加
    export_clearance: Optional[float] = None      # 报价不含时另加
    packing_extra: Optional[float] = 0.0          # 包装另计
    ocean_freight_per_mt: Optional[float] = None
    ocean_freight_total: Optional[float] = None
    freight_includes_dest_thc: bool = False
    insurance_included: Optional[bool] = None     # None -> 按 Incoterms 推断
    insurance_rate_pct: Optional[float] = None
    insurance_amount: Optional[float] = None

    # 境内费用（CNY，整票）
    port_charges_cny: Optional[float] = None
    customs_broker_cny: Optional[float] = None
    inspection_cny: Optional[float] = 0.0
    warehouse_cny: Optional[float] = 0.0
    warehouse_confirmed_none: bool = True
    inland_truck_cny: Optional[float] = None
    financing_cny: Optional[float] = 0.0

    # 税费规则
    tariff_mfn_rate: Optional[float] = None
    tariff_interim_rate: Optional[float] = None
    tariff_agreement_rate: Optional[float] = None
    tariff_general_rate: Optional[float] = None
    applied_rate_type: str = "MFN"      # MFN | INTERIM | AGREEMENT | GENERAL
    origin_eligible: Optional[bool] = None
    origin_certificate: str = ""
    anti_dumping_rate: Optional[float] = 0.0
    vat_rate: Optional[float] = 0.13
    vat_deductible: bool = True
    consumption_tax_rate: Optional[float] = 0.0
    duty_paid_by: str = "buyer"          # buyer | seller

    # 情景参数
    scenario_label: str = ""
    scenario_is_simulation: bool = False

    # 元数据
    meta: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "LandedCostInput":
        known = {f.name for f in dataclasses.fields(LandedCostInput)}
        kw: dict[str, Any] = {}
        for k, v in d.items():
            if k in known:
                kw[k] = v
        # 关键数值字段统一清洗
        for k in ("unit_price", "quantity", "fx_market_rate", "fx_customs_rate",
                  "origin_charges", "export_clearance", "packing_extra",
                  "ocean_freight_per_mt", "ocean_freight_total",
                  "insurance_rate_pct", "insurance_amount",
                  "port_charges_cny", "customs_broker_cny", "inspection_cny",
                  "warehouse_cny", "inland_truck_cny", "financing_cny",
                  "tariff_mfn_rate", "tariff_interim_rate", "tariff_agreement_rate",
                  "tariff_general_rate", "anti_dumping_rate", "vat_rate",
                  "consumption_tax_rate"):
            if k in kw:
                kw[k] = _n(kw[k])
        if "incoterm" in kw:
            kw["incoterm"] = str(kw["incoterm"]).upper().strip()
        for k in ("origin_eligible", "insurance_included"):
            if k in kw and isinstance(kw[k], str):
                s = kw[k].strip().lower()
                kw[k] = True if s in ("true", "是", "yes", "y", "1") else (
                    False if s in ("false", "否", "no", "n", "0") else None)
        return LandedCostInput(**kw)


# --------------------------------------------------------------------------------------
# 2. 关税税率选择（《关税法》第十二、十三条）
# --------------------------------------------------------------------------------------
def select_tariff_rate(inp: LandedCostInput) -> dict[str, Any]:
    """
    按《关税法》第十二条、第十三条确定"实征关税税率"：
      - 适用最惠国税率且列有暂定税率 -> 用暂定税率
      - 适用协定税率且有暂定税率 -> 从低；协定高于 MFN 且无暂定 -> 用 MFN
      - 适用特惠税率且列有暂定税率 -> 从低（本引擎以 agreement 字段承载特惠）
      - 适用普通税率 -> 不适用暂定税率
    返回：rate / rate_type / reason / blocked
    """
    mfn = inp.tariff_mfn_rate
    interim = inp.tariff_interim_rate
    agr = inp.tariff_agreement_rate
    gen = inp.tariff_general_rate
    want = (inp.applied_rate_type or "MFN").upper()

    if inp.origin_eligible is False and want == "AGREEMENT":
        return {"rate": None, "rate_type": "待确认", "blocked": True,
                "reason": "声称适用协定税率但原产地资格未通过核验（4道闸门未全过），需回退至 MFN/暂定税率再计算。"}

    if want == "GENERAL":
        if gen is None:
            return {"rate": None, "rate_type": "待确认", "blocked": True, "reason": "普通税率未录入。"}
        return {"rate": gen, "rate_type": "普通税率", "blocked": False,
                "reason": "原产地不明或来自未享最惠国待遇的国家/地区，适用普通税率；普通税率不适用暂定税率。"}

    if want == "AGREEMENT":
        if agr is None:
            return {"rate": None, "rate_type": "待确认", "blocked": True,
                    "reason": "协定税率未录入或优惠资格未确认。"}
        if interim is not None:
            r = min(agr, interim)
            return {"rate": r, "rate_type": "协定税率/暂定税率从低", "blocked": False,
                    "reason": f"适用协定税率且有暂定税率，按《关税法》第十三条从低：min({agr:.4%}, {interim:.4%}) = {r:.4%}。"}
        if mfn is not None and mfn < agr:
            return {"rate": mfn, "rate_type": "最惠国税率", "blocked": False,
                    "reason": f"最惠国税率({mfn:.4%})低于协定税率({agr:.4%})且无暂定税率，按第十三条二款适用最惠国税率。"}
        return {"rate": agr, "rate_type": "协定税率", "blocked": False,
                "reason": "原产地符合协定规则且提供有效原产地证明，适用协定税率。"}

    # MFN / INTERIM
    if mfn is None:
        return {"rate": None, "rate_type": "待确认", "blocked": True, "reason": "最惠国税率未录入，无法计税。"}
    if interim is not None:
        return {"rate": interim, "rate_type": "暂定税率", "blocked": False,
                "reason": f"适用最惠国税率且列有暂定税率，按第十三条一款适用暂定税率 {interim:.4%}。"}
    return {"rate": mfn, "rate_type": "最惠国税率", "blocked": False,
            "reason": f"适用最惠国税率（无暂定税率）{mfn:.4%}。"}


# --------------------------------------------------------------------------------------
# 3. 主模型
# --------------------------------------------------------------------------------------
def land_cost(inp: LandedCostInput) -> dict[str, Any]:
    ic = inp.incoterm.upper()
    if ic not in INCOTERMS_2020:
        raise ValueError(f"不支持的贸易术语：{inp.incoterm}（Incoterms 2020 仅：{', '.join(INCOTERMS_2020)}）")
    rule = INCOTERMS_2020[ic]
    cur = inp.currency or "CNY"
    gaps: list[dict[str, Any]] = []
    formulas: dict[str, str] = {}
    notes: list[str] = []

    def gap(field_id: str, label: str, impact: str, how: str, blocking: bool = True):
        gaps.append({"field": field_id, "label": label, "impact": impact,
                     "how_to_fill": how, "blocking": blocking})

    # ---------------- 0. 汇率 ----------------
    fx_m, fx_c = inp.fx_market_rate, inp.fx_customs_rate
    if fx_m is None:
        gap("fx_market_rate", "市场参考汇率", "无法做购汇现金换算与汇率敏感性", "查银行牌价/公开牌价并注明类型与日期")
    if fx_c is None:
        gap("fx_customs_rate", "海关计征汇率",
            "无法计算关税与进口环节增值税（不得用市场汇率替代）",
            "取申报日对应日期的上月第三个星期三 PBOC 中间价")

    # ---------------- 1. 数量与货值 ----------------
    qty = inp.quantity
    up = inp.unit_price
    if qty is None:
        gap("quantity", "采购数量", "一切单价摊销无法计算", "填入吨数或柜数")
    if up is None:
        gap("unit_price", "供应商单价", "无法计算货值", "从 PI 录入")

    qty_ok = _is_num(qty) and qty > 0
    price_ok = _is_num(up) and up >= 0

    if price_ok and qty_ok:
        if inp.price_unit.upper() == "CONTAINER":
            goods_total_fx = up * qty
            goods_per_mt_fx = goods_total_fx / qty
        else:
            goods_per_mt_fx = up
            goods_total_fx = up * qty

    # ---------------- 2. Incoterms：哪些已含 ----------------
    included_map = {
        "export_clearance": rule["export"],
        "ocean_freight": rule["freight"],
        "insurance": rule["insurance"],
        "import_duty": rule["duty"],
        "inland_truck": rule["inland"],
    }
    # 起运港费用：FAS 及以上（EXW/FCA 不含装运港费用）
    included_map["origin_charges"] = ic not in ("EXW", "FCA")

    def eff(field_id: str, value: Optional[float], label: str, impact: str, how: str,
            blocking: bool = True, allow_zero_default: bool = False) -> Optional[float]:
        """已在报价中 -> 0（不重复计费）；未在报价中且未填 -> 待补；填了 -> 用填写值。"""
        if included_map.get(field_id):
            return 0.0
        if value is None:
            if allow_zero_default:
                return 0.0
            gap(field_id, label, impact, how, blocking)
            return None
        return value

    origin_ch = eff("origin_charges", inp.origin_charges, "起运港费用（报价未含）",
                    "低估到岸成本", "向供应商/货代索取起运港费用明细（USD）")
    export_cl = eff("export_clearance", inp.export_clearance, "出口侧费用（报价未含）",
                    "低估到岸成本", "向供应商索取出口报关/单证费用（USD）", blocking=False)

    # 海运费
    if rule["freight"]:
        ocean_total_fx = 0.0
    else:
        if inp.ocean_freight_total is not None:
            ocean_total_fx = inp.ocean_freight_total
        elif inp.ocean_freight_per_mt is not None and qty_ok:
            ocean_total_fx = inp.ocean_freight_per_mt * qty
        elif inp.ocean_freight_per_mt is not None and not qty_ok:
            ocean_total_fx = None
            gap("quantity", "采购数量", "无法把 USD/MT 换算成整票运费", "填入数量")
        else:
            ocean_total_fx = None
            gap("ocean_freight", "国际海运费（报价为 %s，未含海运）" % ic,
                "到岸成本、税费、到厂成本均无法完成", "向货代索取海运报价（USD/MT 或 USD/票）")

    # 保险费
    ins_incl = inp.insurance_included if inp.insurance_included is not None else rule["insurance"]
    ins_total_fx: Optional[float]
    ins_basis = ""
    if ins_incl:
        ins_total_fx = 0.0
        ins_basis = "报价已含（%s），不重复计入" % ic
    elif inp.insurance_amount is not None:
        ins_total_fx = inp.insurance_amount
        ins_basis = "按实际保费"
    elif inp.insurance_rate_pct is not None and goods_total_fx is not None and ocean_total_fx is not None:
        ins_total_fx = (goods_total_fx + ocean_total_fx) * inp.insurance_rate_pct / 100.0 * 1.10
        ins_basis = "按费率×110%投保金额（暂定）"
    else:
        ins_total_fx = None
        ins_basis = "未投保/保费未知 -> 海关按（货价+运费）×0.3‰ 计税"

    # 包装另计
    packing = inp.packing_extra if inp.packing_extra is not None else (0.0 if inp.packing_included else None)
    if packing is None:
        gap("packing_extra", "包装费", "漏计包装成本", "确认包装是否含在单价内")

    # ---------------- 3. 计税价格（CIF 基准，海关口径） ----------------
    customs_fx_inputs_ready = all(v is not None for v in
                                  (origin_ch, export_cl, packing, ocean_total_fx))
    insured_amount_fx: Optional[float] = None
    insurance_for_customs_fx: Optional[float] = None

    customs_value_fx: Optional[float] = None
    if goods_total_fx is not None and customs_fx_inputs_ready:
        base_fx = (goods_total_fx + (packing or 0) + (origin_ch or 0) + (export_cl or 0)
                   + (ocean_total_fx or 0))
        if ins_total_fx is not None:
            insurance_for_customs_fx = ins_total_fx
        else:
            # 海关口径（213号令第三十六条）：保险费无法确定或未实际发生时按（货价+运费）×0.3‰。
            # 为避免"0.3‰×(货价+运费+保费)"的递归，取 保费/(货价+运费) = r/(1-r), r=0.3‰
            insurance_for_customs_fx = base_fx * CUSTOMS_INSURANCE_RATE / (1 - CUSTOMS_INSURANCE_RATE)
        customs_value_fx = base_fx + insurance_for_customs_fx
        insured_amount_fx = customs_value_fx

    # ---------------- 4. 税费 ----------------
    tsel = select_tariff_rate(inp)
    rate_applied = tsel["rate"]
    ad_rate = inp.anti_dumping_rate or 0.0
    ct_rate = inp.consumption_tax_rate or 0.0
    vat_rate = inp.vat_rate
    if vat_rate is None:
        gap("vat_rate", "进口环节增值税率", "无法计算增值税", "按增值税税目注释查（一般货物13%）")

    duty_by_seller = (inp.duty_paid_by or "buyer").lower().startswith("seller") or ic == "DDP"
    if duty_by_seller:
        notes.append("报价为 DDP：关税与进口清关费用由卖方承担，不再由买方另付；但进口环节增值税通常仍由境内进口方（纳税人）缴纳，需在合同中明确。")

    taxes: dict[str, Optional[float]] = {}
    if customs_value_fx is None:
        taxes = {k: None for k in ("customs_value_fx", "customs_value_cny", "duty_cny",
                                   "anti_dumping_cny", "consumption_tax_cny", "vat_base_cny",
                                   "import_vat_cash_cny")}
    elif fx_c is None or rate_applied is None or vat_rate is None:
        taxes = {k: None for k in ("customs_value_fx", "customs_value_cny", "duty_cny",
                                   "anti_dumping_cny", "consumption_tax_cny", "vat_base_cny",
                                   "import_vat_cash_cny")}
        taxes["customs_value_fx"] = customs_value_fx
    else:
        cv_cny = customs_value_fx * fx_c
        duty = cv_cny * rate_applied
        if not duty_by_seller:
            pass
        ad = cv_cny * ad_rate
        if ct_rate and ct_rate > 0:
            ct_base = (cv_cny + duty) / (1 - ct_rate)
            ct = ct_base * ct_rate
        else:
            ct_base, ct = 0.0, 0.0
        vat_base = cv_cny + duty + ad + ct
        vat = vat_base * vat_rate
        taxes = {"customs_value_fx": customs_value_fx, "customs_value_cny": cv_cny,
                 "duty_cny": duty if not duty_by_seller else 0.0,
                 "duty_full_cny": duty,
                 "anti_dumping_cny": ad, "consumption_tax_cny": ct,
                 "consumption_tax_base_cny": ct_base,
                 "vat_base_cny": vat_base, "import_vat_cash_cny": vat}

    if duty_by_seller:
        if _is_num(taxes.get("duty_cny")):
            taxes["duty_note"] = "DDP：关税由卖方承担，买方现金支出不计此项（但仍列示以供核对完税价格）"

    # ---------------- 5. 境内费用 ----------------
    port_c = inp.port_charges_cny
    if port_c is None:
        gap("port_charges_cny", "港杂费", "港口作业/THC/换单等费用缺失，到厂成本不完整",
            "索取港区/货代报价（元/票）")
    elif inp.freight_includes_dest_thc and port_c > 0:
        notes.append("海运费报价已含目的港 THC，港杂费中如再次包含 THC 应扣除，请核对货代报价函。")

    broker = inp.customs_broker_cny
    if broker is None:
        gap("customs_broker_cny", "报关代理费", "报关服务成本缺失", "索取报关行报价（元/票）")

    wh = inp.warehouse_cny
    if wh is None and not inp.warehouse_confirmed_none:
        gap("warehouse_cny", "仓储费", "未确认是否有仓储，到厂成本不完整",
            "确认是否发生中转/滞港存储；确无则填 0 并注明")
    elif wh is None:
        wh = 0.0

    inland = eff("inland_truck", inp.inland_truck_cny, "国内运输费（港口→工厂）",
                 "到厂成本缺国内段，无法得到真实到厂价", "索取物流公司报价（元/票）")

    inspection = inp.inspection_cny if inp.inspection_cny is not None else 0.0
    financing = inp.financing_cny if inp.financing_cny is not None else 0.0

    # ---------------- 6. 汇总 ----------------
    vat_cash = taxes.get("import_vat_cash_cny")
    vat_credit = (vat_cash if (inp.vat_deductible and vat_cash is not None) else 0.0) \
        if vat_cash is not None else None
    vat_noncred = (vat_cash - vat_credit) if (vat_cash is not None and vat_credit is not None) else None

    procurement_bits = [goods_total_fx, packing, origin_ch, export_cl, ocean_total_fx,
                        ins_total_fx if ins_total_fx is not None else 0.0]
    procurement_fx_ok = all(v is not None for v in procurement_bits)

    def cny(fx_value: Optional[float], rate: Optional[float]) -> Optional[float]:
        if fx_value is None or rate is None:
            return None
        return fx_value * rate

    goods_cny_m = cny(goods_total_fx, fx_m)
    freight_cny_m = cny(ocean_total_fx, fx_m)
    ins_cny_m = cny(ins_total_fx, fx_m)
    packed_cny_m = cny(packing, fx_m) if packing is not None else None
    origin_cny_m = cny(origin_ch, fx_m) if origin_ch is not None else None
    export_cny_m = cny(export_cl, fx_m) if export_cl is not None else None

    # 到岸成本（采购/经济口径，不含关税与增值税）
    cif_equiv_fx = None
    if procurement_fx_ok:
        cif_equiv_fx = (goods_total_fx + (packing or 0) + (origin_ch or 0) + (export_cl or 0)
                        + ocean_total_fx + (ins_total_fx or 0))
    cif_equiv_cny_m = cny(cif_equiv_fx, fx_m)

    # 现金支出
    cash_known_parts = [goods_cny_m, freight_cny_m, ins_cny_m, packed_cny_m,
                        origin_cny_m, export_cny_m, taxes.get("duty_cny"),
                        taxes.get("anti_dumping_cny"), taxes.get("consumption_tax_cny"),
                        vat_cash,
                        port_c, broker, inspection, wh, inland, financing]
    cash_blank = [x for x in cash_known_parts if x is None]
    cash_out_cny = None if cash_blank else float(sum(cash_known_parts))  # type: ignore[arg-type]

    # 最终经济成本（= 现金支出 − 可抵扣进项）
    final_cost_cny = None
    if cash_out_cny is not None:
        final_cost_cny = cash_out_cny - (vat_credit or 0.0)

    # 已知小计（仅计算已知金额，用于"待补全"时的展示）
    known_parts = [x for x in cash_known_parts if x is not None]
    known_subtotal_cny = sum(known_parts)
    excluded_parts = {
        "货值": goods_cny_m, "海运费": freight_cny_m, "保险费": ins_cny_m,
        "包装另计": packed_cny_m, "起运港费用": origin_cny_m, "出口侧费用": export_cny_m,
        "关税": taxes.get("duty_cny"), "反倾销税": taxes.get("anti_dumping_cny"),
        "消费税": taxes.get("consumption_tax_cny"), "进口环节增值税": vat_cash,
        "港杂费": port_c, "报关代理费": broker, "检验费": inspection,
        "仓储费": wh, "国内运输": inland, "资金成本": financing,
    }
    missing_parts = [k for k, v in excluded_parts.items() if v is None]

    qty_for_ton = qty if qty_ok else None
    per_ton = (lambda v: (v / qty_for_ton) if (v is not None and qty_for_ton) else None)

    full_cost_status = "完整" if not gaps else "待补全"

    # ---------------- 7. 公式文本 ----------------
    formulas.update({
        "goods_total_fx": "数量 × 单价（单价为/MT时：单价×吨数）" if inp.price_unit.upper() != "CONTAINER"
        else "柜数 × 每柜单价",
        "customs_value_fx": "EXW货值 + 包装另计 + 起运港费用 + 出口侧费用 + 海运费 + 保险费"
                            "（保险费未确定时：以上不含保费之和 ÷ (1 − 0.3‰)）",
        "customs_value_cny": "计税价格(外币) × 海关计征汇率",
        "duty_cny": "计税价格(CNY) × 实征关税税率（不可抵扣，计入成本）",
        "vat_base_cny": "计税价格(CNY) + 关税 + 反倾销/反补贴税 + 消费税",
        "import_vat_cash_cny": "组成计税价格 × 进口环节增值税率",
        "cash_out_cny": "货值+运费+保险+包装+起运港+出口侧（均按市场汇率折人民币）+关税+消费税+增值税全款+港杂+报关+检验+仓储+国内运输+资金成本",
        "final_cost_cny": "现金支出 − 可抵扣进项税额（不可抵扣时等于现金支出）",
        "landed_per_ton": "整票到厂成本 ÷ 数量(吨)",
    })

    result: dict[str, Any] = {
        "status": full_cost_status,
        "gaps": gaps,
        "notes": notes,
        "scenario": {"label": inp.scenario_label, "is_simulation": inp.scenario_is_simulation},
        "input_echo": {
            "product": inp.product, "spec": inp.spec, "hs_code": inp.hs_code,
            "incoterm": f"{ic} {inp.incoterm_version}", "incoterm_place": inp.incoterm_place,
            "unit_price": inp.unit_price, "currency": cur,
            "quantity": inp.quantity, "quantity_unit": inp.quantity_unit,
            "origin_country": inp.origin_country,
            "destination_port": inp.destination_port, "final_address": inp.final_address,
        },
        "incoterm_scope": {
            "incoterm": ic,
            "seller_pays": rule,
            "included_in_price": [k for k, v in included_map.items() if v],
            "to_be_added_by_buyer": [k for k, v in included_map.items() if not v],
            "insurance_included_in_price": bool(ins_incl),
            "insurance_basis": ins_basis,
        },
        "fx": {
            "market": {"rate": fx_m, "type": inp.fx_market_type, "date": inp.fx_market_date,
                       "source": inp.fx_market_source},
            "customs": {"rate": fx_c, "date": inp.fx_customs_date, "source": inp.fx_customs_source},
            "gap": (fx_c - fx_m) if (fx_c is not None and fx_m is not None) else None,
        },
        "tax_rate": tsel,
        "lines": {
            "goods_total_fx": goods_total_fx, "goods_per_mt_fx": goods_per_mt_fx if qty_ok and price_ok else None,
            "packing_cny": None if packed_cny_m is None else packed_cny_m,
            "origin_charges_cny": origin_cny_m, "export_clearance_cny": export_cny_m,
            "ocean_freight_total_fx": ocean_total_fx, "ocean_freight_cny": freight_cny_m,
            "insurance_total_fx": ins_total_fx, "insurance_cny": ins_cny_m,
            "insurance_for_customs_fx": insurance_for_customs_fx if not (
                isinstance(insurance_for_customs_fx, float) and math.isnan(insurance_for_customs_fx)) else None,
            "customs_value_fx": taxes.get("customs_value_fx"),
            "customs_value_cny": taxes.get("customs_value_cny"),
            "duty_cny": taxes.get("duty_cny"),
            "anti_dumping_cny": taxes.get("anti_dumping_cny"),
            "consumption_tax_cny": taxes.get("consumption_tax_cny"),
            "vat_base_cny": taxes.get("vat_base_cny"),
            "import_vat_cash_cny": vat_cash,
            "import_vat_input_credit_cny": vat_credit,
            "import_vat_noncreditable_cny": vat_noncred,
            "port_charges_cny": port_c, "customs_broker_cny": broker,
            "inspection_cny": inspection, "warehouse_cny": wh,
            "inland_truck_cny": inland, "financing_cny": financing,
        },
        "summary": {
            "cif_equivalent_total_cny": cif_equiv_cny_m,
            "cif_equivalent_per_ton_cny": per_ton(cif_equiv_cny_m),
            "cash_out_total_cny": cash_out_cny,
            "cash_out_per_ton_cny": per_ton(cash_out_cny),
            "vat_credit_total_cny": vat_credit,
            "final_cost_total_cny": final_cost_cny,
            "final_cost_per_ton_cny": per_ton(final_cost_cny),
            "landed_cost_total_cny": final_cost_cny,
            "landed_cost_per_ton_cny": per_ton(final_cost_cny),
            "known_subtotal_total_cny": known_subtotal_cny,
            "known_subtotal_per_ton_cny": per_ton(known_subtotal_cny),
            "missing_parts": missing_parts,
            "vs_quote_per_ton_cny": (per_ton(final_cost_cny) - (up * fx_m)) if (
                per_ton(final_cost_cny) is not None and up is not None and fx_m is not None
                and inp.price_unit.upper() != "CONTAINER") else None,
            "status": full_cost_status,
        },
        "formulas": formulas,
        "tax_forms": {
            "customs_value_cny": taxes.get("customs_value_cny"),
            "duty_cny": taxes.get("duty_cny"),
            "consumption_tax_cny": taxes.get("consumption_tax_cny"),
            "consumption_tax_base_cny": taxes.get("consumption_tax_base_cny"),
            "vat_base_cny": taxes.get("vat_base_cny"),
            "vat_rate": vat_rate,
            "import_vat_cash_cny": vat_cash,
            "vat_deductible": inp.vat_deductible,
            "import_vat_input_credit_cny": vat_credit,
            "import_vat_noncreditable_cny": vat_noncred,
            "vat_credit_note": ("进项税额可抵扣：增值税只进现金支出与资金占用，不作为最终经济成本。"
                                if inp.vat_deductible else
                                "进项税额不可抵扣（小规模纳税人/用于免税或非应税用途）：增值税全额进入最终经济成本。"),
        },
    }
    return result


# --------------------------------------------------------------------------------------
# 4. 敏感性分析
# --------------------------------------------------------------------------------------
def _recalc_with(inp: LandedCostInput, **changes) -> LandedCostInput:
    d = {f.name: getattr(inp, f.name) for f in dataclasses.fields(inp)}
    d.update(changes)
    return LandedCostInput(**d)


def sensitivity(inp: LandedCostInput, base: Optional[dict[str, Any]] = None,
                fx_steps=(-0.03, 0.0, 0.03),
                freight_steps=(-0.20, -0.10, 0.0, 0.10, 0.20),
                qty_steps=(0.5, 0.75, 1.0, 1.5, 2.0),
                thresholds: Optional[dict[str, float]] = None) -> dict[str, Any]:
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    base = base or land_cost(inp)
    b_pt = base["summary"]["landed_cost_per_ton_cny"]
    b_tot = base["summary"]["landed_cost_total_cny"]

    def row(label, prob, note="") -> dict[str, Any]:
        r = _recalc_with(inp, **prob)
        m = land_cost(r)
        pt = m["summary"]["landed_cost_per_ton_cny"]
        tot = m["summary"]["landed_cost_total_cny"]
        return {
            "label": label,
            "per_ton_cny": pt, "total_cny": tot,
            "delta_per_ton_cny": (pt - b_pt) if (pt is not None and b_pt is not None) else None,
            "delta_pct": ((pt - b_pt) / b_pt) if (pt is not None and b_pt not in (None, 0)) else None,
            "delta_total_cny": (tot - b_tot) if (tot is not None and b_tot is not None) else None,
            "status": m["status"], "note": note,
        }

    fx_rows, fx_customs_rows, freight_rows, qty_rows = [], [], [], []
    if inp.fx_market_rate:
        for k in fx_steps:
            fx_rows.append(row(f"市场汇率 {k:+.0%}", {"fx_market_rate": inp.fx_market_rate * (1 + k)}))
    if inp.fx_customs_rate:
        for k in fx_steps:
            fx_customs_rows.append(row(f"海关计征汇率 {k:+.0%}", {"fx_customs_rate": inp.fx_customs_rate * (1 + k)}))
    if inp.ocean_freight_per_mt is not None and not INCOTERMS_2020[inp.incoterm]["freight"]:
        for k in freight_steps:
            freight_rows.append(row(f"海运费 {k:+.0%}", {"ocean_freight_per_mt": inp.ocean_freight_per_mt * (1 + k)}))
    elif inp.ocean_freight_total is not None and not INCOTERMS_2020[inp.incoterm]["freight"]:
        for k in freight_steps:
            freight_rows.append(row(f"海运费 {k:+.0%}", {"ocean_freight_total": inp.ocean_freight_total * (1 + k)}))
    if inp.quantity:
        for k in qty_steps:
            q = inp.quantity * k
            qty_rows.append(row(f"数量 ×{k:g}（{q:,.0f} 吨）", {"quantity": q}))

    # 弹性：汇率每变动 1% 对应的元/吨成本变动（取 ±3% 两端线性插值）
    fx_elast = None
    if fx_rows and b_pt:
        hi = [r for r in fx_rows if "+" in r["label"]]
        lo = [r for r in fx_rows if "-" in r["label"]]
        if hi and lo and hi[0]["delta_per_ton_cny"] is not None:
            fx_elast = (hi[0]["delta_per_ton_cny"] - lo[0]["delta_per_ton_cny"]) / (2 * 3.0)

    # 运费放大系数
    freight_mult = None
    r = inp.tariff_mfn_rate if base["tax_rate"]["rate_type"] in ("最惠国税率",) else base["tax_rate"]["rate"]
    vr = inp.vat_rate or 0
    if r is not None:
        # 运费放大：运费先被关税放大进入计税价格；可抵扣时增值税不进成本，不可抵扣时再乘 (1+VAT)
        freight_mult = (1 + r) if inp.vat_deductible else (1 + r) * (1 + vr)

    # 一维龙卷风
    storm = []
    for factor, rows in (("市场汇率", fx_rows), ("海关计征汇率", fx_customs_rows),
                         ("海运费", freight_rows), ("采购数量", qty_rows)):
        ds = [x["delta_per_ton_cny"] for x in rows if x["delta_per_ton_cny"] is not None]
        if ds:
            storm.append({"factor": factor, "low": min(ds), "high": max(ds),
                          "span": max(ds) - min(ds)})
    storm.sort(key=lambda x: -x["span"])

    return {
        "base": {"per_ton_cny": b_pt, "total_cny": b_tot, "status": base["status"]},
        "fx_market": fx_rows,
        "fx_customs": fx_customs_rows,
        "freight": freight_rows,
        "quantity": qty_rows,
        "fx_elasticity_per_1pct_cny": fx_elast,
        "freight_pass_through_to_cost": freight_mult,
        "tornado": storm,
        "thresholds": th,
        "notes": [
            "汇率敏感性按市场汇率与海关计征汇率各跑一次；两者对成本的作用路径不同：市场汇率影响货值/运费现金支出，海关计征汇率影响关税与增值税基数。",
            ("可抵扣情形下，市场汇率 +3% 的元/吨成本增幅 < 3%：因为进口环节增值税是可按市场汇率往返冲销的过桥资金，"
             "只有美元计价支出被关税放大的部分（约 1+关税率）才永久进入成本。"
             if inp.vat_deductible else
             "不可抵扣情形下，市场汇率对成本的影响被 (1+关税率)×(1+增值税率) 放大，弹性 > 1。"),
            "运费每变动 1 个单位，到厂成本变动 = 运费变动 × (1 + 关税率)（可抵扣时），因为运费还通过计税价格被关税放大，且增值税作为现金支出同步变动。",
            "数量变化影响按票/按柜计价费用的摊薄，不改变按吨计价项（海运费 USD/MT 保持）。",
        ],
    }


# --------------------------------------------------------------------------------------
# 5. 对比 FOB / CFR / CIF
# --------------------------------------------------------------------------------------
def compare_incoterms(base: dict[str, Any]) -> list[dict[str, Any]]:
    """在相同经济实质下比较三种术语：把同一票费用按术语重新归位。"""
    inp = LandedCostInput.from_dict(base)
    out = []
    for ic in ("FOB", "CFR", "CIF"):
        r = _recalc_with(inp, incoterm=ic)
        m = land_cost(r)
        out.append({
            "incoterm": ic,
            "per_ton_fx": m["input_echo"].get("unit_price"),
            "landed_per_ton_cny": m["summary"]["landed_cost_per_ton_cny"],
            "cash_out_per_ton_cny": m["summary"]["cash_out_per_ton_cny"],
            "status": m["status"],
            "gaps": [g["label"] for g in m["gaps"]],
        })
    return out


# --------------------------------------------------------------------------------------
# 6. 命令行
# --------------------------------------------------------------------------------------
def _deep_get(d: dict, path: str, default=None):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def from_flat_config(cfg: dict[str, Any]) -> LandedCostInput:
    """把 YAML/JSON 嵌套配置（见 references/templates/input_schema.yaml）转换为平铺输入。"""
    q = cfg.get("quote", {})
    g = cfg.get("goods", {})
    fx = cfg.get("fx", {})
    c = cfg.get("costs", {})
    t = cfg.get("tax", {})
    tp = t.get("tariff", {})
    pref = tp.get("preferential", {}) or {}
    ins = c.get("insurance", {}) or {}
    d = {
        "currency": cfg.get("currency", "USD"),
        "incoterm": q.get("incoterm", "FOB"), "incoterm_version": q.get("incoterm_version", "2020"),
        "incoterm_place": q.get("incoterm_place", ""),
        "unit_price": q.get("unit_price"), "price_unit": q.get("price_unit", "MT"),
        "quantity": q.get("quantity"), "quantity_unit": q.get("quantity_unit", "MT"),
        "packing_included": q.get("packing_included", True),
        "product": g.get("name", ""), "spec": str(g.get("spec", "")), "hs_code": str(g.get("hs_code", "")),
        "origin_country": g.get("origin_country", ""), "destination_port": g.get("destination_port", ""),
        "final_address": g.get("final_address", ""),
        "containers_20": g.get("containers_20", 0), "containers_40": g.get("containers_40", 0),
        "fx_market_rate": _deep_get(fx, "market.rate"), "fx_market_type": _deep_get(fx, "market.type", ""),
        "fx_market_date": _deep_get(fx, "market.date", ""), "fx_market_source": _deep_get(fx, "market.source", ""),
        "fx_customs_rate": _deep_get(fx, "customs.rate"), "fx_customs_date": _deep_get(fx, "customs.date", ""),
        "fx_customs_source": _deep_get(fx, "customs.source", ""),
        "origin_charges": c.get("origin_charges"), "export_clearance": c.get("export_clearance"),
        "packing_extra": c.get("packing_extra", 0.0),
        "ocean_freight_per_mt": c.get("ocean_freight_per_mt"),
        "ocean_freight_total": c.get("ocean_freight_total"),
        "freight_includes_dest_thc": c.get("freight_includes_dest_thc", False),
        "insurance_included": ins.get("included"), "insurance_rate_pct": ins.get("rate_pct"),
        "insurance_amount": ins.get("amount_usd"),
        "port_charges_cny": c.get("port_charges_cny"), "customs_broker_cny": c.get("customs_broker_cny"),
        "inspection_cny": c.get("inspection_cny"), "warehouse_cny": c.get("warehouse_cny"),
        "warehouse_confirmed_none": c.get("warehouse_confirmed_none", True),
        "inland_truck_cny": c.get("inland_truck_cny"), "financing_cny": c.get("financing_cny", 0.0),
        "tariff_mfn_rate": tp.get("mfn_rate"), "tariff_interim_rate": tp.get("interim_rate"),
        "tariff_agreement_rate": tp.get("agreement_rate"), "tariff_general_rate": tp.get("general_rate"),
        "applied_rate_type": tp.get("applied_rule", "MFN"),
        "origin_eligible": pref.get("eligible"), "origin_certificate": pref.get("origin_certificate") or "",
        "anti_dumping_rate": t.get("anti_dumping_rate", 0.0),
        "vat_rate": t.get("vat_rate", 0.13), "vat_deductible": t.get("vat_deductible", True),
        "consumption_tax_rate": t.get("consumption_tax_rate", 0.0),
        "duty_paid_by": t.get("duty_paid_by", "buyer"),
        "scenario_label": cfg.get("scenario_label", ""),
        "scenario_is_simulation": cfg.get("scenario_is_simulation", False),
    }
    return LandedCostInput.from_dict(d)


def main() -> int:
    ap = argparse.ArgumentParser(description="进口到厂成本计算引擎")
    ap.add_argument("--input", required=True, help="输入 JSON（嵌套 schema 或平铺字段均可）")
    ap.add_argument("--out", default="", help="输出 JSON 路径")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--sensitivity", action="store_true", help="同时输出敏感性分析")
    a = ap.parse_args()
    with open(a.input, encoding="utf-8") as f:
        raw = json.load(f)
    inp = from_flat_config(raw) if ("quote" in raw or "costs" in raw) else LandedCostInput.from_dict(raw)
    res = land_cost(inp)
    if a.sensitivity:
        res["sensitivity"] = sensitivity(inp, res)
    text = json.dumps(res, ensure_ascii=False, indent=2 if a.pretty else None, default=str)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    return 0 if res["status"] == "完整" else 2


if __name__ == "__main__":
    raise SystemExit(main())
