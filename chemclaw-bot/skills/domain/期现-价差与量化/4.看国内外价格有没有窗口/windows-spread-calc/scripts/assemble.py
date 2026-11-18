# -*- coding: utf-8 -*-
"""把 research.json 组装成 data.json（HTML / Excel 的唯一数据源）。

用法：
    python scripts/assemble.py examples/01-meg-cfr-china-huadong/research.json --out build/data.json

原则（与 SKILL.md 硬规矩一一对应）：
  * 所有派生数字都在这里算（core.py 出公式结果），research.json 里不写派生值；
  * 历史序列每一行都要交代：价格来自哪天、汇率来自哪天、运费来自哪天 / 何种推断；
  * 任何取不到的项写进 gaps，不插值、不用近似值；
  * 输出四层成本、四口径价差、瀑布、归因、敏感性、情景对比与公式清单。
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import wio  # noqa: E402

VERSION = "1.0.0"


# ------------------------------------------------------------------ 序列取样
def as_series(items):
    """把 [{'date':..,'value':..}] 或 {'date': value} 统一成 {date: float}。"""
    out = {}
    if not items:
        return out
    if isinstance(items, dict):
        for k, v in items.items():
            if isinstance(v, dict):
                v = v.get("value")
            n = core.fnum(v)
            if n is not None:
                out[str(k)[:10]] = n
        return out
    for it in items:
        d = str(it.get("date") or it.get("d") or "")[:10]
        v = core.fnum(it.get("value", it.get("v", it.get("close", it.get("c")))))
        if d and v is not None:
            out[d] = v
    return out


def pick(series, date_iso, max_stale=None):
    return core.series_prev(series, date_iso, max_stale)


# ------------------------------------------------------------------ 参数
def base_params(res):
    cp = res.get("cost_params", {})
    ov = res.get("overseas", {})
    p = dict(cp)
    p["price_quote"] = core.mid(*core.parse_range(ov.get("price")))
    p["currency"] = ov.get("currency") or res["meta"].get("currency") or "USD"
    p["term"] = core.norm_term(ov.get("term"))
    p.setdefault("vat_rate", 0.13)
    p.setdefault("vat_credit_ratio", 1.0)
    p.setdefault("duty_rate", 0.0)
    p.setdefault("other_tax_rate", 0.0)
    p.setdefault("purity", 1.0)
    p.setdefault("gross_weight_factor", 1.0)
    p.setdefault("insurance_rate", 1.1)
    p.setdefault("insurance_rate_pct", 0.0)
    for k in ("inland_origin", "export_clear", "ocean_freight", "discharge_fee",
              "inland_dest", "unload_fee"):
        p.setdefault(k, 0.0)
    return p


def dom_cfg(res):
    d = res.get("domestic", {})
    return {
        "dom_quote": core.mid(*core.parse_range(d.get("price"))),
        "dom_tax": d.get("tax") or "含税",
        "dom_term_incl_freight": bool(d.get("term_incl_freight", True)),
        "dom_freight_to_bench": core.fnum(d.get("freight_to_bench"), 0.0) or 0.0,
        "dom_scale_adj": core.fnum(d.get("scale_adj"), 0.0) or 0.0,
        "vat_rate": core.fnum((res.get("cost_params") or {}).get("vat_rate"), 0.13) or 0.13,
    }


# ------------------------------------------------------------------ 瀑布
def build_waterfall(cost, comp):
    steps = [
        {"key": "goods_cny", "label": "海外报价折人民币", "value": cost["goods_cny"], "kind": "base",
         "formula": "报价 × 汇率"},
    ]
    for k, label, formula in [
        ("inland_origin", "出口国内陆运费", "参数"),
        ("export_clear", "出口报关杂费", "参数"),
        ("freight", "国际海运费", "运费 × 汇率"),
        ("insurance", "保险费（CIF 口径补足）", "(货值+出口费+运费) × 加成率 × 费率"),
    ]:
        steps.append({"key": k, "label": label, "value": cost[k], "kind": "cost", "formula": formula})
    steps.append({"key": "_cif", "label": "= CIF 折人民币", "value": cost["cif"], "kind": "subtotal",
                  "formula": "Σ 以上各项"})
    steps.append({"key": "discharge", "label": "目的港卸货/港杂", "value": cost["discharge"], "kind": "cost", "formula": "参数"})
    steps.append({"key": "duty", "label": "进口关税", "value": cost["duty"], "kind": "cost", "formula": "(CIF+卸货) × 关税率"})
    if cost["other_tax"]:
        steps.append({"key": "other_tax", "label": "其他税（反倾销等）", "value": cost["other_tax"], "kind": "cost",
                      "formula": "(CIF+卸货) × 其他税率"})
    steps.append({"key": "vat", "label": "进口增值税", "value": cost["vat"], "kind": "cost", "formula": "(CIF+卸货+关税) × VAT率"})
    steps.append({"key": "_landed", "label": "= 含税到岸 landed_cash", "value": cost["landed_cash"], "kind": "subtotal",
                  "formula": "Σ 以上各项（现金口径）"})
    steps.append({"key": "vat_credit", "label": "可抵扣进口增值税", "value": -cost["vat_credit"], "kind": "credit",
                  "formula": "VAT × 可抵扣比例"})
    steps.append({"key": "_net", "label": "= 可比经济成本 net_cash", "value": cost["net_cash"], "kind": "total",
                  "formula": "landed_cash − 可抵扣 VAT"})
    steps.append({"key": "_dom", "label": "国内可比送到价（含税）", "value": comp["dom_price"], "kind": "dom",
                  "formula": "国内报价（折算到送到基准地+含税）"})
    steps.append({"key": "_gap", "label": "= 经济口径价差 G3", "value": core.r6(comp["dom_price"] - cost["net_cash"]),
                  "kind": "gap", "formula": "国内可比价 − net_cash"})
    return steps


# ------------------------------------------------------------------ 归因
FACTOR_DEF = [
    ("ov_price", "海外报价（美元）", "quote"),
    ("fx", "汇率 USD/CNY", "fx"),
    ("freight", "海运费", "ocean_freight"),
    ("duty", "关税/税率", "duty_rate"),
    ("vat_credit", "增值税可抵扣比例", "vat_credit_ratio"),
    ("insurance", "保险费率", "insurance_rate_pct"),
    ("dom_price", "国内现货价", "dom_quote"),
]


def build_attribution(res, P0, C0, comp0):
    """本期 vs 对比期：逐项替换参数，得到 5 类因子对价差的贡献（Shapley 简化：逐项一次替换）。

    逐项替换的口径：以本期为起点，把对比期的某个参数换回本期值，看价差变化多少。
    所有因子贡献之和 + 残差 = 总价差变化，残差 > 1e-6 会写进 gap。
    """
    ovc = res.get("compare_quote") or {}
    cmp_dom = res.get("compare_dom") or {}
    base_date = res["meta"]["base_date"]
    cmp_date = None
    for cand in (ovc.get("date"), cmp_dom.get("date"), res["meta"].get("compare_date"),
                 res["meta"].get("window_start")):
        if cand and wio.parse_iso(cand) and wio.parse_iso(cand) < wio.parse_iso(base_date):
            cmp_date = cand
            break
    if not cmp_date:
        return {"available": False, "reason": "没有可比的历史时点（需要 compare_quote / compare_dom / compare_date 之一）"}

    fx_hist, fx_hist_d = pick(as_series(res.get("fx_history")), cmp_date)
    frt_res = (res.get("freight_history") or {})
    frt_hist, frt_hist_d = None, None
    if isinstance(frt_res, dict) and frt_res.get("monthly"):
        mkey = cmp_date[:7]
        cand = sorted([k for k in frt_res["monthly"] if k <= mkey])
        if cand:
            frt_hist = core.fnum(frt_res["monthly"][cand[-1]])
            frt_hist_d = cand[-1]
    frt_tag = "monthly_avg" if frt_hist is not None else "assumed_base"

    P_cmp = dict(P0)
    P_cmp["fx_usdcny"] = fx_hist if fx_hist is not None else P0.get("fx_usdcny")
    P_cmp["ocean_freight"] = frt_hist if frt_hist is not None else P0.get("ocean_freight")
    q_cmp = core.mid(*core.parse_range(ovc.get("price"))) if ovc.get("price") is not None else None
    P_cmp["price_quote"] = q_cmp if q_cmp is not None else P0.get("price_quote")
    if (ovc.get("term") or "").upper() in core.TERM_INCLUDES:
        P_cmp["term"] = core.norm_term(ovc["term"])
    cfg_cmp = dict(dom_cfg(res))
    d_cmp = core.mid(*core.parse_range(cmp_dom.get("price"))) if cmp_dom.get("price") is not None else None
    cfg_cmp["dom_quote"] = d_cmp if d_cmp is not None else cfg_cmp["dom_quote"]

    cost_cmp = core.import_cost(P_cmp)
    comp_cmp = core.comparable_price(cfg_cmp, cost_cmp)
    gaps_cmp = core.gap_table(cfg_cmp["dom_quote"], cost_cmp, comp_cmp)
    gap_cmp = {g["code"]: g["value"] for g in gaps_cmp}
    gap_now = {g["code"]: g["value"] for g in core.gap_table(cfg_cmp["dom_quote"], C0, comp0)}

    # 逐项替换（起点 = 对比期参数，终点 = 本期参数）
    items = []
    cur = dict(P_cmp)
    cur_cfg = dict(cfg_cmp)
    cur_cost = cost_cmp
    cur_comp = comp_cmp

    def gap_of(cost, comp):
        return core.r6(comp["dom_price"] - cost["net_cash"])

    start_gap = gap_of(cur_cost, cur_comp)

    # 1) 海外报价
    prev = gap_of(cur_cost, cur_comp)
    cur["price_quote"] = P0["price_quote"]
    cur_cost = core.import_cost(cur)
    cur_comp = core.comparable_price(cur_cfg, cur_cost)
    now = gap_of(cur_cost, cur_comp)
    items.append({"key": "ov_price", "label": "海外报价（美元）", "value": core.r6(now - prev),
                  "detail": "%s → %s USD/t" % (core.r6(P_cmp["price_quote"]), core.r6(P0["price_quote"]))})

    # 2) 汇率
    prev = gap_of(cur_cost, cur_comp)
    cur["fx_usdcny"] = P0.get("fx_usdcny")
    cur_cost = core.import_cost(cur)
    cur_comp = core.comparable_price(cur_cfg, cur_cost)
    now = gap_of(cur_cost, cur_comp)
    items.append({"key": "fx", "label": "汇率 USD/CNY", "value": core.r6(now - prev),
                  "detail": "%s → %s" % (core.r6(P_cmp["fx_usdcny"]), core.r6(P0.get("fx_usdcny")))})

    # 3) 海运费
    prev = gap_of(cur_cost, cur_comp)
    cur["ocean_freight"] = P0.get("ocean_freight")
    cur_cost = core.import_cost(cur)
    cur_comp = core.comparable_price(cur_cfg, cur_cost)
    now = gap_of(cur_cost, cur_comp)
    items.append({"key": "freight", "label": "海运费 USD/t", "value": core.r6(now - prev),
                  "detail": "%s → %s（%s）" % (core.r6(P_cmp["ocean_freight"]), core.r6(P0.get("ocean_freight")), frt_tag)})

    # 4) 税费 / 抵扣比例
    for key, label, pkey in (("duty", "关税/其他税率", "duty_rate"), ("vat_credit", "增值税可抵扣比例", "vat_credit_ratio"),
                             ("insurance", "保险费率", "insurance_rate_pct")):
        prev = gap_of(cur_cost, cur_comp)
        cur[pkey] = P0.get(pkey)
        cur_cost = core.import_cost(cur)
        cur_comp = core.comparable_price(cur_cfg, cur_cost)
        now = gap_of(cur_cost, cur_comp)
        items.append({"key": key, "label": label, "value": core.r6(now - prev),
                      "detail": "%s → %s" % (core.r6(P_cmp.get(pkey)), core.r6(P0.get(pkey)))})

    # 5) 国内现货
    prev = gap_of(cur_cost, cur_comp)
    cur_cfg["dom_quote"] = core.mid(*core.parse_range(res["domestic"].get("price")))
    cur_comp = core.comparable_price(cur_cfg, cur_cost)
    now = gap_of(cur_cost, cur_comp)
    items.append({"key": "dom_price", "label": "国内现货价", "value": core.r6(now - prev),
                  "detail": "%s → %s CNY/t" % (core.r6(cfg_cmp["dom_quote"]), core.r6(cur_cfg["dom_quote"]))})

    total = core.r6(now - start_gap)
    ssum = core.r6(sum(i["value"] for i in items))
    return {
        "available": True,
        "compare_date": cmp_date,
        "inputs": {
            "fx": fx_hist_d, "freight": frt_hist_d, "freight_source": frt_tag,
            "ov_price_date": ovc.get("date"), "dom_price_date": cmp_dom.get("date"),
            "ov_price": core.r6(P_cmp["price_quote"]), "dom_price": core.r6(cfg_cmp["dom_quote"]),
            "fx_value": core.r6(P_cmp["fx_usdcny"]), "freight_value": core.r6(P_cmp["ocean_freight"]),
        },
        "gaps_compare": gap_cmp,
        "gaps_now": gap_now,
        "start_gap": start_gap,
        "end_gap": core.r6(now),
        "total_change": total,
        "sum_of_factors": ssum,
        "residual": core.r6(total - ssum),
        "items": items,
        "cost_cmp": {k: cost_cmp[k] for k in ("cif", "landed_cash", "net_cash", "quote", "freight", "insurance", "duty", "vat", "vat_credit")},
        "cost_now": {k: C0[k] for k in ("cif", "landed_cash", "net_cash", "quote", "freight", "insurance", "duty", "vat", "vat_credit")},
    }


# ------------------------------------------------------------------ 敏感性
def build_sensitivity(res, P0, C0):
    """单参数灵敏度 + 运费×汇率二维矩阵。

    矩阵约定（与 HTML/Excel 表格一致）：行 = 运费，列 = 汇率；
    cells[i][j] 表示 运费=freight[i]、汇率=fx[j] 时的经济成本与 G3 价差。
    """
    sen = res.get("sensitivity") or {}
    items = {}
    specs = [
        ("price", "海外报价（USD/t）", sen.get("price")),
        ("freight", "海运费（USD/t）", sen.get("freight")),
        ("fx", "USD/CNY", sen.get("fx")),
        ("duty", "关税率", sen.get("duty")),
        ("vat", "进口增值税率", sen.get("vat")),
        ("insurance_pct", "保险费率", sen.get("insurance_pct")),
        ("credit", "可抵扣比例", sen.get("credit")),
        ("discharge", "目的港卸货费（USD/t）", sen.get("discharge")),
        ("inland_dest", "进口国内陆运费（元/t）", sen.get("inland_dest")),
        ("term", "贸易术语", sen.get("term")),
    ]
    for key, label, vals in specs:
        if not vals:
            continue
        pairs = [(str(v), v) for v in vals]
        items[key] = {"label": label, "rows": core.sensitivity_one(P0, key, pairs)}

    grid = sen.get("matrix") or {}
    fx_list = [core.fnum(v) for v in (grid.get("fx") or [])]
    frt_list = [core.fnum(v) for v in (grid.get("freight") or [])]
    matrix = {"fx": fx_list, "freight": frt_list, "cells": [], "rows_are": "freight",
              "cols_are": "fx"}
    dom = core.comparable_price(dom_cfg(res), C0)["dom_price"]
    for frt in frt_list:
        row = []
        for fx in fx_list:
            p = dict(P0)
            p["fx_usdcny"] = fx
            p["ocean_freight"] = frt
            r = core.import_cost(p)
            row.append({"fx": fx, "freight": frt, "net_cash": r["net_cash"],
                        "gap": core.r6(dom - r["net_cash"]),
                        "status": "ok" if abs(dom - r["net_cash"]) > 1e-9 else "zero"})
        matrix["cells"].append(row)
    return {"items": items, "matrix": matrix, "dom_price": dom,
            "base_net_cash": C0["net_cash"]}


# ------------------------------------------------------------------ 情景对比
def build_scenarios(res, P0, C0, comp0):
    out = []
    sc = res.get("scenarios") or {}
    for item in sc.get("rounds", []):
        p = dict(P0)
        for k, v in item.get("override", {}).items():
            p[k] = v
        r = core.import_cost(p)
        gap = core.r6(comp0["dom_price"] - r["net_cash"])
        out.append({
            "name": item["name"],
            "desc": item.get("desc", ""),
            "override": item.get("override", {}),
            "term": r["term"], "cif": r["cif"], "landed_cash": r["landed_cash"],
            "net_cash": r["net_cash"], "gap": gap,
            "delta_net": core.r6(r["net_cash"] - C0["net_cash"]),
        })
    # 市场隐含（国内价 vs CIF + 运费）
    imp = res.get("market_implied") or {}
    mi = []
    for row in imp.get("rows", []):
        bid = core.fnum(row.get("bid"))
        cif = core.fnum(row.get("cif_usd"))
        fx = core.fnum(row.get("fx"))
        frt = core.fnum(row.get("frt_usd"))
        if bid is None or cif is None or fx is None:
            continue
        cif_cny = core.r6(cif * fx)
        frt_cny = core.r6((frt or 0) * fx)
        mi.append({
            "date": row.get("date"), "bid": bid, "cif_usd": cif, "fx": fx, "frt_usd": frt,
            "cif_cny": cif_cny, "frt_cny": frt_cny,
            "residual": core.implied_other_costs(bid, cif_cny, frt_cny, 0, 0),
            "product": core.r6(cif_cny + frt_cny),
        })
    return {"rounds": out, "implied": mi, "implied_meta": imp.get("meta", {})}


# ------------------------------------------------------------------ 历史序列
def build_series(res, P0, dcfg):
    hist = res.get("history") or []
    fx_series = as_series(res.get("fx_history"))
    st = res.get("series_sources") or {}
    fx_stale = int(st.get("fx_max_stale_days") or 7)
    base_inc = core.TERM_INCLUDES[core.norm_term(P0.get("term"))]

    def inc_has(flag):
        return bool(base_inc.get(flag))
    rows = []
    for h in hist:
        d = str(h["date"])[:10]
        fx, fx_d = pick(fx_series, d, fx_stale)
        if fx is None:
            # 汇率缺失：按规则不插值，标 gap 并跳过本行
            rows.append({"date": d, "status": "gap", "reason": "汇率在该日 ±%d 天内无可用值" % fx_stale})
            continue
        ov = core.fnum(h.get("ov_usd"))
        dom = core.fnum(h.get("dom_cny"))
        frt = core.fnum(h.get("frt_usd"), 0.0) or 0.0
        tag = h.get("frt_source") or "assumed_base"
        if ov is None:
            rows.append({"date": d, "status": "gap", "reason": "该日无海外报价（报价为时点值需前向填充，未做近似）"})
            continue
        p = dict(P0)
        p["price_quote"] = ov
        p["fx_usdcny"] = fx
        p["ocean_freight"] = frt
        if h.get("term"):
            p["term"] = core.norm_term(h["term"])
        if h.get("duty_rate") is not None:
            p["duty_rate"] = core.fnum(h["duty_rate"])
        r = core.import_cost(p)
        cfg = dict(dcfg)
        cfg["dom_quote"] = dom if dom is not None else None
        cfg["vat_rate"] = p.get("vat_rate", 0.13)
        comp = core.comparable_price(cfg, r) if dom is not None else None
        # 市场隐含残差：报价为到岸价（CFR/CIF/DAP）时运费与保险已在其中，
        # 不得再从国内价里重复扣减，否则残差被系统性低估一份运费。
        def _resid(comp_, r_):
            if not comp_ or not r_:
                return None
            frt = 0.0 if inc_has("freight") else r_["freight"]
            ins = 0.0 if inc_has("insurance") else r_["insurance"]
            dis = 0.0 if inc_has("discharge") else r_["discharge"]
            return core.implied_other_costs(comp_["dom_price"], r_["cif"], frt, ins, dis)

        rows.append({
            "date": d, "status": "ok",
            "ov_usd": ov, "dom_cny": dom, "fx": fx, "frt_usd": frt,
            "fx_date": fx_d, "frt_source": tag, "note": h.get("note") or "",
            "ov_source": h.get("ov_source") or st.get("ov_default") or "",
            "dom_source": h.get("dom_source") or st.get("dom_default") or "",
            "cif": r["cif"], "insurance": r["insurance"],
            "landed_cash": r["landed_cash"], "vat": r["vat"], "vat_credit": r["vat_credit"],
            "net_cash": r["net_cash"],
            "dom_price": comp["dom_price"] if comp else None,
            "dom_net": comp["dom_net_price"] if comp else None,
            "gap_net_cash": core.r6(comp["dom_price"] - r["net_cash"]) if comp else None,
            "gap_landed_cash": core.r6(comp["dom_price"] - r["landed_cash"]) if comp else None,
            "gap_cif": core.r6(comp["dom_net_price"] - r["cif"]) if comp else None,
            "implied_other": _resid(comp, r),
        })
    ok_rows = [r for r in rows if r.get("status") == "ok"]
    return {
        "rows": rows,
        "n_ok": len(ok_rows),
        "stats": {
            "gap_net_cash": core.change_stats(ok_rows, "gap_net_cash"),
            "gap_cif": core.change_stats(ok_rows, "gap_cif"),
            "gap_landed_cash": core.change_stats(ok_rows, "gap_landed_cash"),
            "implied_other": core.change_stats(ok_rows, "implied_other"),
        },
        "per_ton_per_usd": None,
    }


# ------------------------------------------------------------------ 公式清单
def build_formulas(P0, cost):
    return [
        {"no": 1, "name": "货值折人民币", "formula": "货值_CNY = 报价 × 汇率（USD 报价）或 报价（CNY 报价）",
         "param": "price_quote × fx_usdcny", "value": cost["goods_cny"], "unit": "元/吨"},
        {"no": 2, "name": "保险费", "formula": "保险 = (货值 + 出口端费用 + 运费) × 加成率 × 费率",
         "param": "insurance_rate(加成) × insurance_rate_pct(费率)", "value": cost["insurance"], "unit": "元/吨"},
        {"no": 3, "name": "CIF 到岸价", "formula": "CIF = 货值 + 出口内陆 + 出口报关 + 运费 + 保险",
         "param": "Σ(1..2 及贸易术语项)", "value": cost["cif"], "unit": "元/吨"},
        {"no": 4, "name": "进口关税", "formula": "关税 = (CIF + 卸货费) × 关税率",
         "param": "duty_rate", "value": cost["duty"], "unit": "元/吨"},
        {"no": 5, "name": "进口增值税", "formula": "VAT = (CIF + 卸货费 + 关税) × 增值税率",
         "param": "vat_rate", "value": cost["vat"], "unit": "元/吨"},
        {"no": 6, "name": "可抵扣增值税", "formula": "可抵扣 VAT = VAT × 可抵扣比例",
         "param": "vat_credit_ratio", "value": cost["vat_credit"], "unit": "元/吨"},
        {"no": 7, "name": "含税到岸成本（现金口径）", "formula": "landed_cash = CIF + 卸货 + 关税 + 其他税 + VAT + 进口内陆 + 损耗",
         "param": "—", "value": cost["landed_cash"], "unit": "元/吨"},
        {"no": 8, "name": "可比经济成本", "formula": "net_cash = landed_cash − 可抵扣 VAT",
         "param": "—", "value": cost["net_cash"], "unit": "元/吨"},
        {"no": 9, "name": "折纯/毛净口径", "formula": "unit_net = net_cash ÷ 纯度 × 毛净比",
         "param": "purity × gross_weight_factor", "value": cost["unit_net"], "unit": "元/纯吨"},
        {"no": 10, "name": "四口径价差", "formula": "G1 = 国内未税 − CIF；G2 = 国内含税 − landed_cash；G3 = 国内含税 − net_cash；G4 = 国内未税 − net_cash",
         "param": "—", "value": None, "unit": "元/吨"},
        {"no": 11, "name": "市场隐含其余成本", "formula": "残差 = 国内价 − CIF − 运费 − 保险 − 卸货（不含税口径）",
         "param": "—", "value": None, "unit": "元/吨"},
        {"no": 12, "name": "归因分解", "formula": "Δ价差 = Σ(−Δ成本项) + Δ国内价；闭合残差须 < 1e-6",
         "param": "—", "value": None, "unit": "元/吨"},
    ]


# ------------------------------------------------------------------ 主流程
def assemble(res, out_path=None):
    meta = res["meta"]
    P0 = base_params(res)
    dcfg = dom_cfg(res)

    cost = core.import_cost(P0)
    comp = core.comparable_price(dcfg, cost)
    gaps_t = core.gap_table(dcfg["dom_quote"], cost, comp)
    gap_by_code = {g["code"]: g["value"] for g in gaps_t}

    waterfall = build_waterfall(cost, comp)
    attribution = build_attribution(res, P0, cost, comp)
    sensitivity = build_sensitivity(res, P0, cost)
    scenarios = build_scenarios(res, P0, cost, comp)
    series = build_series(res, P0, dcfg)

    # 元信息
    inc = core.TERM_INCLUDES[cost["term"]]
    meta_out = {
        "product": meta["product"],
        "product_code": meta.get("product_code") or "",
        "spec": meta["spec"],
        "quote_basis": meta["quote_basis"],
        "quote_region": meta["quote_region"],
        "quote_term": core.norm_term(P0["term"]),
        "quote_term_label": core.TERM_LABEL.get(core.norm_term(P0["term"])),
        "term_includes": inc,
        "term_includes_cn": {k: ("报价已含" if v else "报价不含") for k, v in inc.items()},
        "currency": P0["currency"],
        "dom_region": meta["dom_region"],
        "dom_basis": meta["dom_basis"],
        "hs_code": meta["hs_code"],
        "hs_desc": meta.get("hs_desc") or "",
        "base_date": meta["base_date"],
        "window": meta["window"],
        "window_start": meta.get("window_start") or "",
        "compare_date": attribution.get("compare_date") if attribution.get("available") else "",
        "unit": meta.get("unit") or "元/吨",
        "generated_at": meta.get("generated_at") or "",
        "author": meta.get("author") or "windows-spread-calc v" + VERSION,
        "title": meta.get("title") or "",
        "must_read": meta.get("must_read") or [],
        "focus": meta.get("focus") or [],
    }

    # 数据说明
    notes = {
        "fx": {
            "value": cost["fx"],
            "source": (res.get("series_sources") or {}).get("fx_name") or "汇率序列",
            "note": (res.get("fx_meta") or {}).get("note") or "",
        },
        "freight": {
            "value": P0.get("ocean_freight"),
            "source": ((res.get("cost_params") or {}).get("_src") or {}).get("ocean_freight")
                      or (res.get("freight_history") or {}).get("source") or "",
            "note": (res.get("freight_history") or {}).get("note") or "",
        },
    }

    # 主 KPI 健康检查
    gaps = list(res.get("gaps") or [])
    if series["n_ok"] and series["n_ok"] < 8:
        gaps.append({"item": "历史序列有效样本仅 %d 条" % series["n_ok"],
                     "impact": "价差曲线不足以判断\u300c窗口\u300d是否稳定存在",
                     "fix": "补充更多时点的海外报价（周度至少 1 个点）", "severity": "中",
                     "scope": "history"})
    if attribution.get("available") and abs(attribution.get("residual") or 0) > 1e-6:
        gaps.append({"item": "归因分解未闭合（残差 %s）" % attribution.get("residual"),
                     "impact": "各因子贡献之和不等于总变化", "fix": "检查是否漏计交互项",
                     "severity": "高", "scope": "attribution"})
    frt_actual = len([r for r in series["rows"] if r.get("frt_source") == "actual"])
    if series["n_ok"] and frt_actual == 0:
        gaps.append({"item": "历史运费没有逐时点的实际值，全部按月度均价或基准日假设处理",
                     "impact": "价差曲线中的成本部分含假设误差，方向可由运费假设解释",
                     "fix": "接入逐周运价指数（SCFI 相关航线 / 波罗的海指数 / 船司报价）", "severity": "高",
                     "scope": "freight"})

    data = {
        "meta": meta_out,
        "params": {k: v for k, v in P0.items()},
        "cost": cost,
        "domestic": comp,
        "gaps_table": gaps_t,
        "gap_map": gap_by_code,
        "waterfall": waterfall,
        "attribution": attribution,
        "sensitivity": sensitivity,
        "scenarios": scenarios,
        "series": series,
        "notes": notes,
        "compare_quote": res.get("compare_quote"),
        "compare_dom": res.get("compare_dom"),
        "sources": res.get("sources") or [],
        "gaps": gaps,
        "formulas": build_formulas(P0, cost),
        "disclaimers": res.get("disclaimers") or [],
        "version": VERSION,
    }
    if out_path:
        wio.dump_json(data, out_path)
    return data


def main():
    ap = argparse.ArgumentParser(description="research.json -> data.json")
    ap.add_argument("research")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    res = wio.load_json(args.research)
    errs, warns = wio.check_research(res)
    if errs and not args.out:
        wio.report((errs, warns), "assemble 前置校验")
        return
    data = assemble(res, args.out)
    c = data["cost"]
    print("CIF %.2f | landed_cash %.2f | vat_credit %.2f | net_cash %.2f" % (c["cif"], c["landed_cash"], c["vat_credit"], c["net_cash"]))
    for g in data["gaps_table"]:
        print("  %-28s %s" % (g["code"], wio.fmt_trim(g["value"])))
    print("序列有效 %d 条；缺口 %d 条" % (data["series"]["n_ok"], len(data["gaps"])))
    if args.out:
        wio.ok("写出 " + args.out)


if __name__ == "__main__":
    main()
