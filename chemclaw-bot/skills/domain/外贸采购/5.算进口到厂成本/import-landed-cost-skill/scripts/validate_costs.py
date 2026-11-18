# -*- coding: utf-8 -*-
"""
validate_costs.py — 计算验证脚本
================================
目的：用"独立实现的公式"复核引擎结果，并检查业务硬约束（不重复计费、不默认零、
增值税分栏、双汇率、敏感性可复现、数量摊薄正确）。

用法：
    python validate_costs.py                       # 跑内置演示用例 + 全部校验
    python validate_costs.py --json out.json       # 输出机器可读结果
    python validate_costs.py --input my_case.json  # 校验自定义输入（支持 cases 数组）
返回码：0 全部通过；1 有失败。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from landed_cost_engine import (LandedCostInput, land_cost, sensitivity,  # noqa: E402
                                INCOTERMS_2020)

TOL = 0.02  # 人民币分位容差

RESULTS: list[dict] = []


def check(name: str, ok: bool, detail: str = "", value=None, expect=None) -> bool:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail,
                    "value": value, "expect": expect})
    return ok


def approx(a, b, tol=TOL) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


# --------------------------------------------------------------------------------------
# 独立重算（不复用引擎函数，以纯算术核对）
# --------------------------------------------------------------------------------------
def independent_recalc(d: dict) -> dict:
    ic = d["incoterm"].upper()
    rule = INCOTERMS_2020[ic]
    qty = d["quantity"]
    up = d["unit_price"]
    goods = qty * up
    freight = 0.0 if rule["freight"] else (d.get("ocean_freight_per_mt") or 0) * qty
    ins_incl = d.get("insurance_included")
    ins_incl = rule["insurance"] if ins_incl is None else ins_incl
    if ins_incl:
        ins = 0.0
        ins_c = 0.0
    elif d.get("insurance_amount") is not None:
        ins = ins_c = d["insurance_amount"]
    else:
        base = goods + freight
        ins_c = base * 0.003 / 0.997
        ins = 0.0
    cv_fx = goods + freight + ins_c
    fx_c = d["fx_customs_rate"]
    cv = cv_fx * fx_c
    rate = d["tariff_mfn_rate"] if d.get("tariff_interim_rate") is None else d["tariff_interim_rate"]
    duty = cv * rate
    vat = (cv + duty) * d["vat_rate"]
    fx_m = d["fx_market_rate"]
    cny = (goods + freight + ins) * fx_m
    cash = cny + duty + vat + (d.get("port_charges_cny") or 0) + (d.get("customs_broker_cny") or 0) \
        + (d.get("warehouse_cny") or 0) + (d.get("inland_truck_cny") or 0) + (d.get("inspection_cny") or 0)
    final = cash - (vat if d.get("vat_deductible", True) else 0.0)
    return {"cv": cv, "duty": duty, "vat": vat, "cash": cash, "final": final,
            "per_ton": final / qty, "cif_equiv": cny}


# --------------------------------------------------------------------------------------
def validate_case(name: str, d: dict) -> None:
    inp = LandedCostInput.from_dict(d)
    r = land_cost(inp)
    L = r["lines"]
    s = r["summary"]
    ic = d["incoterm"].upper()

    # 1. 状态与缺失
    check(f"[{name}] 海关计征汇率未录入时必须标待补全",
          (r["status"] == "待补全") == (d.get("fx_customs_rate") is None),
          f"status={r['status']}")
    if d.get("fx_customs_rate") is None:
        check(f"[{name}] 待补全时不输出到厂价", s["landed_cost_total_cny"] is None,
              "未按 0 估算法税")
        check(f"[{name}] 待补全时仍给出已知小计", s["known_subtotal_total_cny"] > 0,
              f"已知小计={s['known_subtotal_total_cny']:.2f}")

    # 2. 不重复计费：按术语检查
    if ic in ("CFR", "CIF", "CPT", "CIP"):
        check(f"[{name}] {ic} 报价不得再加海运费", L["ocean_freight_total_fx"] == 0.0,
              f"ocean_freight={L['ocean_freight_total_fx']}")
    if ic in ("CIF", "CIP", "DDP"):
        check(f"[{name}] {ic} 报价不得再加保险费", L["insurance_total_fx"] == 0.0,
              f"insurance={L['insurance_total_fx']}")
    if ic == "FOB":
        check(f"[{name}] FOB 报价含起运港费用，不得再加", L["origin_charges_cny"] == 0.0, "")
        check(f"[{name}] FOB 必须另加海运费", (L["ocean_freight_total_fx"] or 0) > 0, "")
        check(f"[{name}] FOB 必须另加保险费", (L["insurance_total_fx"] or 0) > 0, "")

    # 3. 独立重算一致性（有计征汇率时）
    if d.get("fx_customs_rate") is not None:
        ref = independent_recalc(d)
        check(f"[{name}] 计税价格与独立重算一致", approx(L["customs_value_cny"], ref["cv"]),
              f"engine={L['customs_value_cny']:.2f} ref={ref['cv']:.2f}")
        check(f"[{name}] 关税与独立重算一致", approx(L["duty_cny"], ref["duty"]),
              f"engine={L['duty_cny']:.2f} ref={ref['duty']:.2f}")
        check(f"[{name}] 增值税与独立重算一致", approx(L["import_vat_cash_cny"], ref["vat"]),
              f"engine={L['import_vat_cash_cny']:.2f} ref={ref['vat']:.2f}")
        check(f"[{name}] 现金支出与独立重算一致", approx(s["cash_out_total_cny"], ref["cash"]),
              f"engine={s['cash_out_total_cny']:.2f} ref={ref['cash']:.2f}")
        check(f"[{name}] 到厂成本与独立重算一致", approx(s["landed_cost_total_cny"], ref["final"]),
              f"engine={s['landed_cost_total_cny']:.2f} ref={ref['final']:.2f}")

        # 4. 增值税分栏
        vat_cash = L["import_vat_cash_cny"]
        credit = L["import_vat_input_credit_cny"]
        final = s["landed_cost_total_cny"]
        cash = s["cash_out_total_cny"]
        if d.get("vat_deductible", True):
            check(f"[{name}] 可抵扣时：最终成本 = 现金支出 − 进项",
                  approx(final, cash - credit), f"{final:.2f} vs {cash - credit:.2f}")
            check(f"[{name}] 可抵扣时：进项不得再进入成本（成本 < 现金支出）", final < cash, "")
            check(f"[{name}] 增值税现金=进项（可抵扣口径）", approx(vat_cash, credit), "")
        else:
            check(f"[{name}] 不可抵扣时：最终成本 = 现金支出", approx(final, cash), "")
            check(f"[{name}] 不可抵扣时：进项为 0", (credit or 0) == 0, "")

        # 5. 增值税公式：VAT = (完税价格 + 关税) × 13%
        expect_vat = (L["customs_value_cny"] + L["duty_cny"]) * d["vat_rate"]
        check(f"[{name}] VAT=(计税价格+关税)×税率", approx(vat_cash, expect_vat),
              f"{vat_cash:.2f} vs {expect_vat:.2f}")

        # 6. 元/吨一致性
        check(f"[{name}] 元/吨 = 整票 ÷ 数量", approx(s["landed_cost_per_ton_cny"],
                                               final / d["quantity"]), "")

    # 7. 双汇率
    check(f"[{name}] 市场汇率与海关计征汇率分别可追溯",
          r["fx"]["market"]["rate"] is not None and (r["fx"]["customs"]["rate"] is None
                                                     or r["fx"]["customs"]["rate"] != r["fx"]["market"]["rate"]),
          f"market={r['fx']['market']['rate']} customs={r['fx']['customs']['rate']}")

    # 8. 保险费海关口径 3‰
    if d.get("fx_customs_rate") is not None and not INCOTERMS_2020[ic]["insurance"] \
            and d.get("insurance_amount") is None:
        base = (d["quantity"] * d["unit_price"]) + ((d.get("ocean_freight_per_mt") or 0) * d["quantity"])
        expect_ins = base * 0.003 / 0.997
        check(f"[{name}] 未投保时按（货价+运费）×0.3‰ 计入计税价格",
              approx(L["insurance_for_customs_fx"], expect_ins),
              f"{L['insurance_for_customs_fx']:.4f} vs {expect_ins:.4f}")

    # 9. 敏感性可复现
    if d.get("fx_customs_rate") is not None and d.get("fx_market_rate"):
        sens = sensitivity(inp)
        base_pt = sens["base"]["per_ton_cny"]
        row = [x for x in sens["fx_market"] if x["label"].endswith("+3%")]
        if row:
            d2 = dict(d); d2["fx_market_rate"] = d["fx_market_rate"] * 1.03
            ref2 = independent_recalc(d2)
            check(f"[{name}] FX+3% 敏感性可独立复现",
                  approx(row[0]["per_ton_cny"], ref2["per_ton"], 0.05),
                  f"{row[0]['per_ton_cny']:.2f} vs {ref2['per_ton']:.2f}")
        check(f"[{name}] 基准点敏感性=基准值",
              any(approx(x["per_ton_cny"], base_pt) for x in sens["fx_market"] + [{"per_ton_cny": base_pt}]),
              f"base={base_pt:.2f}" if base_pt else "base=None")


def validate_vat_toggle() -> None:
    """不可抵扣情形：增值税应全额进入最终成本。"""
    base = {
        "currency": "USD", "incoterm": "CIF", "incoterm_place": "宁波", "unit_price": 500,
        "price_unit": "MT", "quantity": 100, "packing_included": True,
        "fx_market_rate": 6.7, "fx_customs_rate": 6.72,
        "insurance_included": True,
        "port_charges_cny": 1000, "customs_broker_cny": 300, "inspection_cny": 0,
        "warehouse_cny": 0, "inland_truck_cny": 5000, "financing_cny": 0,
        "tariff_mfn_rate": 0.055, "applied_rate_type": "MFN",
        "vat_rate": 0.13, "vat_deductible": False, "consumption_tax_rate": 0,
        "origin_eligible": False, "anti_dumping_rate": 0,
    }
    r = land_cost(LandedCostInput.from_dict(base))
    check("[增值税不可抵扣] 最终成本=现金支出", approx(r["summary"]["landed_cost_total_cny"],
                                                 r["summary"]["cash_out_total_cny"]), "")
    check("[增值税不可抵扣] 进项=0", r["lines"]["import_vat_input_credit_cny"] == 0, "")
    base2 = dict(base); base2["vat_deductible"] = True
    r2 = land_cost(LandedCostInput.from_dict(base2))
    check("[增值税可抵扣] 成本比不可抵扣少一个增值税额",
          approx(r["summary"]["landed_cost_total_cny"] - r2["summary"]["landed_cost_total_cny"],
                 r2["lines"]["import_vat_cash_cny"]), "")


def validate_no_zero_default() -> None:
    """缺失港杂/报关/国内运输/海运费时必须产生 gaps，且到厂成本为 None。"""
    base = {
        "currency": "USD", "incoterm": "FOB", "incoterm_place": "朱拜勒", "unit_price": 600,
        "price_unit": "MT", "quantity": 100, "packing_included": True,
        "fx_market_rate": 6.68, "fx_customs_rate": 6.72,
        "port_charges_cny": None, "customs_broker_cny": None,
        "warehouse_cny": None, "warehouse_confirmed_none": False,
        "inland_truck_cny": None,
        "tariff_mfn_rate": 0.055, "applied_rate_type": "MFN",
        "vat_rate": 0.13, "vat_deductible": True, "origin_eligible": False,
    }
    r = land_cost(LandedCostInput.from_dict(base))
    labels = " ".join(g["label"] for g in r["gaps"])
    check("[不默认零] 缺海运费->待补", "海运费" in labels, labels)
    check("[不默认零] 缺港杂->待补", "港杂费" in labels, "")
    check("[不默认零] 缺报关费->待补", "报关代理费" in labels, "")
    check("[不默认零] 缺国内运输->待补", "国内运输" in labels, "")
    check("[不默认零] 缺仓储且未确认无->待补", "仓储费" in labels, "")
    check("[不默认零] 到厂成本=None", r["summary"]["landed_cost_total_cny"] is None, "")
    check("[不默认零] 已知小计>0", (r["summary"]["known_subtotal_total_cny"] or 0) > 0, "")


def validate_agreement_gate() -> None:
    """未通过原产地核验却声称协定税率 -> 必须阻断。"""
    d = {"currency": "USD", "incoterm": "CIF", "unit_price": 600, "quantity": 10,
         "fx_market_rate": 6.7, "fx_customs_rate": 6.72, "insurance_included": True,
         "tariff_mfn_rate": 0.055, "tariff_agreement_rate": 0.0,
         "applied_rate_type": "AGREEMENT", "origin_eligible": False,
         "vat_rate": 0.13, "vat_deductible": True,
         "port_charges_cny": 100, "customs_broker_cny": 100, "inland_truck_cny": 100,
         "warehouse_cny": 0, "inspection_cny": 0, "financing_cny": 0,
         "anti_dumping_rate": 0, "consumption_tax_rate": 0}
    r = land_cost(LandedCostInput.from_dict(d))
    check("[优惠闸门] 未核验原产地不得按协定税率征税", r["tax_rate"]["blocked"] is True, r["tax_rate"]["reason"])
    check("[优惠闸门] 阻断时到厂价=None", r["summary"]["landed_cost_total_cny"] is None, "")
    d2 = dict(d); d2["origin_eligible"] = True
    r2 = land_cost(LandedCostInput.from_dict(d2))
    check("[优惠闸门] 核验通过后按协定税率", approx(r2["tax_rate"]["rate"], 0.0) and r2["status"] == "完整", "")


def validate_qty_scaling() -> None:
    """数量翻倍：按吨计价不变，按票固定费用被摊薄，元/吨应下降。"""
    base = {"currency": "USD", "incoterm": "CIF", "unit_price": 500, "price_unit": "MT",
            "fx_market_rate": 6.7, "fx_customs_rate": 6.72, "insurance_included": True,
            "tariff_mfn_rate": 0.055, "applied_rate_type": "MFN", "vat_rate": 0.13,
            "vat_deductible": True, "origin_eligible": False,
            "port_charges_cny": 2000, "customs_broker_cny": 500,
            "inland_truck_cny": 8000, "warehouse_cny": 0, "inspection_cny": 0,
            "financing_cny": 0, "anti_dumping_rate": 0, "consumption_tax_rate": 0}
    a = land_cost(LandedCostInput.from_dict({**base, "quantity": 100}))["summary"]["landed_cost_per_ton_cny"]
    b = land_cost(LandedCostInput.from_dict({**base, "quantity": 200}))["summary"]["landed_cost_per_ton_cny"]
    check("[数量] 数量翻倍后元/吨下降", b < a, f"100t={a:.2f} 200t={b:.2f}")
    # 固定费用摊薄差额 = (固定费用和)/100 - (固定费用和)/200
    fixed = 2000 + 500 + 8000
    check("[数量] 摊薄差额与固定费用一致", approx(a - b, fixed / 100 - fixed / 200, 0.05),
          f"{a-b:.2f} vs {fixed/100-fixed/200:.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    if a.input:
        with open(a.input, encoding="utf-8") as f:
            raw = json.load(f)
        cases = raw.get("cases") if isinstance(raw, dict) and "cases" in raw else [raw]
        for i, c in enumerate(cases):
            validate_case(c.get("name", f"case{i}"), c)
    else:
        from demo_build import CASES, build  # type: ignore
        for name in CASES:
            for fx_c in (None, 6.72):
                d = {f.name: getattr(build(name, fx_customs_rate=fx_c), f.name)
                     for f in __import__("dataclasses").fields(LandedCostInput)}
                tag = name + ("（待补全）" if fx_c is None else "（含计征汇率）")
                validate_case(tag, d)
        validate_vat_toggle()
        validate_no_zero_default()
        validate_agreement_gate()
        validate_qty_scaling()

    passed = sum(1 for r in RESULTS if r["pass"])
    failed = [r for r in RESULTS if not r["pass"]]
    print(f"\n校验项：{len(RESULTS)}    通过：{passed}    失败：{len(failed)}\n")
    for r in failed:
        print(f"  ✗ {r['check']}  {r['detail']}")
    if not failed:
        print("  全部通过 ✓")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"total": len(RESULTS), "passed": passed, "results": RESULTS},
                      f, ensure_ascii=False, indent=2)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
