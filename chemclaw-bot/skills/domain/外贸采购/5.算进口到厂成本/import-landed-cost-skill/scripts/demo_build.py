# -*- coding: utf-8 -*-
"""
demo_build.py — 构建演示模型（沙特 MEG → 宁波 → 苏州），并输出三口径对照、敏感性、校验。
所有"模拟"费用在此集中定义；真实数据由用户在上层(HTML/Excel)录入区覆盖。
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from landed_cost_engine import (LandedCostInput, land_cost, sensitivity,  # noqa: E402
                                INCOTERMS_2020)

# --------------------------------------------------------------------------------------
# 一、情景参数
# --------------------------------------------------------------------------------------
FX_MARKET = {"rate": 6.6807, "type": "市场参考汇率（ECB 参考汇率交叉）", "date": "2026-10-19",
             "source": "https://api.frankfurter.app/latest?from=USD&to=CNY（European Central Bank）；"
                       "交叉核对 exchangerate-api 2026-10-20 USD/CNY=6.69"}
FX_CUSTOMS = {"rate": None, "date": "2026-09-16", "source": "中国人民银行人民币汇率中间价（上月第三个星期三）"}

SAUDI_PORTS = ["朱拜勒 Al Jubail", "延布 Yanbu", "达曼 Dammam"]
MONTHLY_CAP_MT = 100_000  # 单月可拼池量（建模假设）

# 陆地段参数（公开核对口径）
TRUCK_RATE = 0.5          # 元/吨·公里（浙江单一窗口宁波港公示"拖车费 0.5 元/吨/公里 进口"）
DIST_NBO_SZ = 250         # 宁波北仑 → 苏州 公路里程（约）；标注为建模假设

# 各口径的境外报价（FOB 池化综合净价）
FOB_PRICE = 640.00        # USD/MT FOB 沙特港（建模假设，非实时报价）
FREIGHT_USD_MT = 45.00    # USD/MT 朱拜勒→宁波（建模假设）
INS_RATE_PER_MILLE = 0.55 # 保险费率 0.55‰（模拟）：保费 = (货值+运费) × 0.55‰ × 110%
CONTAINER_CAP = 62.5      # 25 个 40'ISO 罐 × 25.0 MT
FOB_PORT_CHARGES_CNY = 600     # 港杂（含 THC×25 + 港建 + 换单）建模
BROKER_CNY = 500               # 报关代理费（宁波公示 100–500 元/票，取上限）
WH_CNY = 3000                  # 仓储/堆存（第3~5天；免箱期内）建模
TRUCK_CNY = round(TRUCK_RATE * DIST_NBO_SZ * CONTAINER_CAP, 2)  # 7796.88

COMMON = dict(
    currency="USD", incoterm_version="2020",
    price_unit="MT", quantity_unit="MT", packing_included=True,
    product="工业级乙二醇", spec="≥99.9% 工业级", hs_code="29053100",
    origin_country="SA", destination_port="宁波港（CNNBO）",
    final_address="江苏省苏州市",
    containers_40=25, containers_20=0,
    fx_market_rate=FX_MARKET["rate"], fx_market_type=FX_MARKET["type"],
    fx_market_date=FX_MARKET["date"], fx_market_source=FX_MARKET["source"],
    fx_customs_rate=None, fx_customs_date=FX_CUSTOMS["date"], fx_customs_source=FX_CUSTOMS["source"],
    packing_extra=0.0, freight_includes_dest_thc=False,
    insurance_rate_pct=None, insurance_amount=None,
    port_charges_cny=FOB_PORT_CHARGES_CNY, customs_broker_cny=BROKER_CNY,
    inspection_cny=0.0, warehouse_cny=WH_CNY, warehouse_confirmed_none=False,
    inland_truck_cny=TRUCK_CNY, financing_cny=0.0,
    tariff_mfn_rate=0.055, tariff_interim_rate=None,
    tariff_agreement_rate=None, tariff_general_rate=0.30,
    applied_rate_type="MFN", origin_eligible=False,
    origin_certificate="", anti_dumping_rate=0.0,
    vat_rate=0.13, vat_deductible=True, consumption_tax_rate=0.0,
    duty_paid_by="buyer",
    scenario_label="沙特MEG→宁波→苏州 基准情景",
    scenario_is_simulation=True,
)

CASES = {
    "FOB 朱拜勒": dict(incoterm="FOB", incoterm_place="沙特朱拜勒 Al Jubail",
                     unit_price=FOB_PRICE, quantity=CONTAINER_CAP,
                     ocean_freight_per_mt=FREIGHT_USD_MT,
                     insurance_included=False,
                     insurance_amount=(round(CONTAINER_CAP * FOB_PRICE + CONTAINER_CAP * FREIGHT_USD_MT, 2)
                                       * INS_RATE_PER_MILLE / 1000 * 1.10)),
    "CFR 宁波": dict(incoterm="CFR", incoterm_place="中国宁波",
                    unit_price=FOB_PRICE + FREIGHT_USD_MT, quantity=CONTAINER_CAP,
                    ocean_freight_per_mt=None, insurance_included=False,
                    insurance_amount=round(CONTAINER_CAP * (FOB_PRICE + FREIGHT_USD_MT), 2)
                    * INS_RATE_PER_MILLE / 1000 * 1.10),
    "CIF 宁波": dict(incoterm="CIF", incoterm_place="中国宁波",
                    unit_price=FOB_PRICE + FREIGHT_USD_MT + 0.05, quantity=CONTAINER_CAP,
                    ocean_freight_per_mt=None, insurance_included=True, insurance_amount=None),
}


def build(case: str, **over) -> LandedCostInput:
    d = dict(COMMON); d.update(CASES[case]); d.update(over)
    return LandedCostInput.from_dict(d)


def summarize(name: str, res: dict) -> dict:
    s = res["summary"]
    return {
        "case": name,
        "status": res["status"],
        "rate_type": res["tax_rate"]["rate_type"],
        "rate": res["tax_rate"]["rate"],
        "customs_value_cny": res["lines"]["customs_value_cny"],
        "duty_cny": res["lines"]["duty_cny"],
        "vat_cash_cny": res["lines"]["import_vat_cash_cny"],
        "vat_credit_cny": res["lines"]["import_vat_input_credit_cny"],
        "cif_total_cny": s["cif_equivalent_total_cny"],
        "cif_per_ton_cny": s["cif_equivalent_per_ton_cny"],
        "cash_out_total_cny": s["cash_out_total_cny"],
        "final_cost_total_cny": s["final_cost_total_cny"],
        "landed_per_ton_cny": s["landed_cost_per_ton_cny"],
        "gaps": [g["label"] for g in res["gaps"]],
    }


if __name__ == "__main__":
    print("=" * 96)
    print("情景 A：海关计征汇率未录入（真实状态）")
    print("=" * 96)
    for c in CASES:
        r = land_cost(build(c))
        sm = summarize(c, r)
        print(json.dumps(sm, ensure_ascii=False, indent=1))

    print("=" * 96)
    print("情景 B：以 2026-10-20 最新公布中间价 6.7200 作占位（仅演示，明确标注）")
    print("=" * 96)
    for c in CASES:
        r = land_cost(build(c, fx_customs_rate=6.72))
        sm = summarize(c, r)
        print(json.dumps(sm, ensure_ascii=False, indent=1))
