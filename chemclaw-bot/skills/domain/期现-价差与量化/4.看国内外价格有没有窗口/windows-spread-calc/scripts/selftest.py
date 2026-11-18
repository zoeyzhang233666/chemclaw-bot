# -*- coding: utf-8 -*-
"""自检：不依赖任何外部数据，用合成参数验证内核的财务恒等式与边界行为。

与 check_consistency.py 的分工：
  * check_consistency.py 证明「Python 内核 ≡ 浏览器内核」；
  * selftest.py 证明「内核本身算得对」——恒等式闭合、术语屏蔽生效、
    价差四口径之间的解析关系成立、边界输入不产生 NaN/负成本。

用法：
    python scripts/selftest.py
退出码 0 = 全部通过。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print("[%s] %s%s" % (" OK " if cond else "FAIL", name, ("  " + detail) if detail else ""))


def close(a, b, tol=1e-9):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


BASE = dict(
    price_quote=700.0, currency="USD", term="CFR", fx_usdcny=7.0,
    purity=1.0, gross_weight_factor=1.0,
    inland_origin=5.0, export_clear=2.0, ocean_freight=45.0,
    insurance_rate=1.1, insurance_rate_pct=0.0015, discharge_fee=12.0,
    inland_dest=60.0, unload_fee=8.0,
    duty_rate=0.055, other_tax_rate=0.0,
    vat_rate=0.13, vat_credit_ratio=1.0,
)
DOM = dict(dom_quote=6000.0, dom_tax="含税", dom_term_incl_freight=True,
           dom_freight_to_bench=0.0, dom_scale_adj=0.0, vat_rate=0.13)


def run(p=None, d=None):
    p = dict(BASE, **(p or {}))
    c = core.import_cost(p)
    comp = core.comparable_price(dict(DOM, **(d or {})), c)
    return p, c, comp, core.gap_table(DOM["dom_quote"], c, comp)


print("=" * 68)
print("selftest：内核恒等式与边界行为")
print("=" * 68)

# ---------- 1. 术语屏蔽 ----------
p, c, comp, gaps = run({"term": "CFR", "ocean_freight": 45.0})
check("CFR 报价下海运费被置零（防重复计费）", close(c["freight"], 0.0), "freight=%s" % c["freight"])
check("CFR 含运费字段标记为已含", bool(c["includes"]["freight"]) is True,
      "includes.freight=%r" % c["includes"]["freight"])
check("CFR 不含保险字段标记为未含", bool(c["includes"]["insurance"]) is False)
p2, c2, _, _ = run({"term": "FOB", "ocean_freight": 45.0})
check("FOB 报价下海运费正常计入", close(c2["freight"], 45.0 * 7.0), "freight=%.2f" % c2["freight"])
p3, c3, _, _ = run({"term": "CIF", "insurance_rate_pct": 0.0015})
check("CIF 报价下保险费被置零", close(c3["insurance"], 0.0))
p4, c4, _, _ = run({"term": "CFR", "insurance_rate_pct": 0.0015})
check("CFR 报价下保险费照计", c4["insurance"] > 0, "insurance=%.2f" % c4["insurance"])
issues = core.check_terms({"term": "CFR", "ocean_freight": 30.0})
check("术语冲突能被拦截", any(i["level"] == "error" for i in issues), str(issues[:1]))

# ---------- 2. 成本分层恒等式 ----------
p, c, comp, gaps = run()
check("CIF = 货值+出口内陆+出口报关+运费+保险",
      close(c["cif"], c["goods_cny"] + c["inland_origin"] + c["export_clear"]
            + c["freight"] + c["insurance"]))
check("landed_cash 分项闭合",
      close(c["landed_cash"], c["cif"] + c["discharge"] + c["duty"] + c["other_tax"]
            + c["vat"] + c["inland_dest"] + c["unload"]))
check("net_cash = landed_cash − vat_credit", close(c["net_cash"], c["landed_cash"] - c["vat_credit"]))
check("vat_credit = vat × 可抵扣比例", close(c["vat_credit"], c["vat"] * BASE["vat_credit_ratio"]))
check("cash_out = 关税+其他税+不可抵扣VAT",
      close(c["cash_out"], c["duty"] + c["other_tax"] + (c["vat"] - c["vat_credit"])))
check("关税 = (CIF+卸货)×税率", close(c["duty"], (c["cif"] + c["discharge"]) * BASE["duty_rate"]))
check("卸货费按原币乘汇率（USD 报价）",
      close(c["discharge"], BASE["discharge_fee"] * BASE["fx_usdcny"]),
      "discharge=%.2f" % c["discharge"])
check("增值税 = (CIF+卸货+关税)×税率",
      close(c["vat"], (c["cif"] + c["discharge"] + c["duty"]) * BASE["vat_rate"], 1e-6),
      "vat=%.6f vs %.6f" % (c["vat"],
                            (c["cif"] + c["discharge"] + c["duty"]) * BASE["vat_rate"]))
check("CIF ≥ 货值（成本只增不减）", c["cif"] >= c["goods_cny"])
check("net_cash ≤ landed_cash", c["net_cash"] <= c["landed_cash"] + 1e-9)

# ---------- 3. 价差四口径解析关系 ----------
g = {x["code"]: x["value"] for x in gaps}
check("G1 = 国内未税 − CIF", close(g["G1_cif_vs_domnet"], comp["dom_net_price"] - c["cif"]))
check("G2 = 国内含税 − landed_cash",
      close(g["G2_landedcash_vs_domallin"], comp["dom_price"] - c["landed_cash"]))
check("G3 = 国内含税 − net_cash", close(g["G3_netcash_vs_domallin"], comp["dom_price"] - c["net_cash"]))
check("G4 = 国内未税 − net_cash", close(g["G4_vatadj"], comp["dom_net_price"] - c["net_cash"]))
# G3 − G1 = 国内价内增值税 −（净成本 − CIF 的其余成本项）
check("G3 − G1 可由税制与费用差解析解释",
      close(g["G3_netcash_vs_domallin"] - g["G1_cif_vs_domnet"],
            (comp["dom_price"] - comp["dom_net_price"]) - (c["net_cash"] - c["cif"]), 1e-6),
      "Δ=%.6f" % (g["G3_netcash_vs_domallin"] - g["G1_cif_vs_domnet"]))

# ---------- 4. 边界 ----------
p0, c0, comp0, gaps0 = run({"price_quote": 0.0, "duty_rate": 0.0, "ocean_freight": 0.0,
                            "insurance_rate_pct": 0.0, "discharge_fee": 0.0,
                            "inland_origin": 0.0, "export_clear": 0.0,
                            "inland_dest": 0.0, "unload_fee": 0.0, "term": "FOB"})
check("全零报价不产生 NaN", c0["net_cash"] == 0.0
      and not any((v != v) for v in c0.values() if isinstance(v, float)))
p1, c1, _, _ = run({"vat_credit_ratio": 0.0})
check("可抵扣 0% 时 net_cash = landed_cash", close(c1["net_cash"], c1["landed_cash"]))
p2, c2, _, _ = run({"purity": 0.995, "gross_weight_factor": 1.002})
check("折纯成本 = net/purity×gross", close(c2["unit_net"], c2["net_cash"] / 0.995 * 1.002, 1e-6))
p3, c3, _, _ = run({"currency": "CNY", "fx_usdcny": 1.0})
check("人民币报价时汇率按 1 处理", close(c3["goods_cny"], 700.0))
bad = core.check_config({"term": "XYZ", "price_quote": -5.0, "fx_usdcny": 0.0})
check("非法术语/负报价/零汇率被识别", len(bad) > 0, "%d 条" % len(bad))

# ---------- 5. 历史取值不得插值 ----------
ser = {"2026-01-05": 7.1, "2026-01-20": 6.9}
v, dd = core.series_prev(ser, "2026-01-25", 3)
check("超过新鲜度窗口不取旧值", v is None and dd is None, "got=%s@%s" % (v, dd))
v, dd = core.series_prev(ser, "2026-01-25", 7)
check("恰在新鲜度边界内可取", close(v, 6.9) and dd == "2026-01-20", "got=%s@%s" % (v, dd))
v, dd = core.series_prev(ser, "2026-01-25", 30)
check("窗口内取最近前一值", close(v, 6.9) and dd == "2026-01-20")

print("-" * 68)
print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
if FAIL:
    for n, det in FAIL:
        print("  失败：%s %s" % (n, det))
sys.exit(1 if FAIL else 0)
