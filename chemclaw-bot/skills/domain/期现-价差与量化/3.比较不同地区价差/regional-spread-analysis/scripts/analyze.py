#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze.py — 区域价差研究主分析（一条命令出全量 JSON，支持双口径对照）

流程：
  1) 读数据（宽表/长表自动判别，可同时给主口径与对照口径两个文件）
  2) 口径标准化（税基 / 付款 / 交付 / 单位 / 规格）—— 缺参数就"不让算"
  3) 时间对齐（exact / asof / weekly），缺口不插值
  4) 两两价差（有方向，全有序对）+ 价差矩阵
  5) 历史分位（1y / 3y，带 N 与极值）+ 滚动分位
  6) 运费调整（运费已内含于送到价时，自动告警"不可重复扣减"）
  7) 异常价差阶段识别 + 事件对照
  8) 区域基本面与物流

用法：
  python scripts/analyze.py --csv data/demo_soda_ash_dense_delivered_weekly.csv \
      --csv-control data/demo_soda_ash_dense_exw_weekly.csv \
      --config config --align weekly --windows 1y,3y --out build/result.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spreadlib as S  # noqa: E402


def load_json(p):
    if not p or not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_paths(a):
    if a.config and os.path.isdir(a.config):
        proj = os.path.join(a.config, "project.json")
        routes = a.routes or os.path.join(a.config, "routes.json")
        events = a.events or os.path.join(a.config, "events_fundamentals.json")
        return proj, routes, events
    return a.config, a.routes, a.events


def build_routes(cfg):
    out = {}
    for r in cfg.get("routes", []):
        lanes = r.get("lanes", [])
        main = lanes[0]["mode"] if lanes else "公路汽运"
        f_list = r.get("freight", [])
        sel = next((x for x in f_list if x.get("mode") == main), f_list[0] if f_list else None)
        val = None if (sel is None or sel.get("value") is None) else float(sel["value"])
        basis = "provided" if (sel and sel.get("basis") == "real_quote") else "default_ref"
        out[r["id"]] = {
            **r,
            "main_mode": main,
            "freight": val,
            "freight_basis": basis if val is not None else "not_available",
            "freight_source": (sel or {}).get("source", ""),
            "freight_date": (sel or {}).get("date", ""),
            "freight_alternatives": [
                {"mode": x.get("mode"), "value": x.get("value"), "basis": x.get("basis"),
                 "note": x.get("note", ""), "source": x.get("source", "")}
                for x in f_list
            ],
        }
    return out


def run_one_caliber(a, proj, routes_cfg, ev_cfg, csv_path, caliber_key):
    """对单个口径跑完整分析，返回 (core_result_addon, aligned)。"""
    P = proj.get("project", {})
    region_list = P.get("regions", [])
    regions_cfg = {r["id"]: r for r in region_list}
    region_order = [r["id"] for r in region_list]
    if a.regions:
        want = [x.strip() for x in a.regions.split(",") if x.strip()]
        unknown = [w for w in want if w not in regions_cfg]
        if unknown:
            raise SystemExit(f"未知地区 {unknown}，配置里只有 {region_order}")
        region_order = want
        region_list = [regions_cfg[x] for x in region_order]

    calibers = P.get("calibers", {})
    cal_def = calibers.get(caliber_key, {})
    product_cfg = dict(P.get("product_cfg", {}))
    product_cfg.setdefault("tax_rate", 0.13)

    target = {
        "tax_included": cal_def.get("tax_included", True),
        "payment": cal_def.get("payment", "现汇"),
        "delivery": cal_def.get("delivery", "DELIVERED"),
        "basis_adjust": 0.0,
    }

    rows, file_regions = S.load_prices(csv_path)
    missing = [r for r in region_order if r not in file_regions]
    if missing:
        raise SystemExit(f"{csv_path} 缺少地区列：{missing}；文件内地区 = {file_regions}")
    extra = [r for r in file_regions if r not in region_order]
    rows = [r for r in rows if r["region"] in region_order]

    norm_rows, norm_report = S.normalize_series(rows, regions_cfg, product_cfg, target)

    aligned = S.align_series(norm_rows, region_order, method=a.align,
                             max_staleness_days=a.max_staleness)
    if not aligned["dates"]:
        raise SystemExit(f"[{caliber_key}] 对齐后没有任何可用观测日 —— 检查各地区日期是否真的重叠")
    if len(aligned["dates"]) < 12:
        print(f"[analyze] ⚠️ [{caliber_key}] 仅 {len(aligned['dates'])} 个观测点，统计结论不可靠",
              file=sys.stderr)

    names = {r["id"]: r["name"] for r in region_list}
    pairs = S.directional_pairs(region_order)
    mat, mat_meta = S.spread_matrix(aligned, region_order, stat="last")
    mat_mean, _ = S.spread_matrix(aligned, region_order, stat="mean")

    pair_detail = []
    for a_reg, b_reg in pairs:
        s = S.spread_series(aligned, a_reg, b_reg)
        if not s:
            pair_detail.append({"pair": S.pair_key(a_reg, b_reg), "a": a_reg, "b": b_reg, "n": 0})
            continue
        vals = [x[3] for x in s]
        d = S.describe(vals)
        pair_detail.append({
            "pair": S.pair_key(a_reg, b_reg), "a": a_reg, "b": b_reg,
            "label": f"{names[a_reg]} - {names[b_reg]}",
            "direction": S.describe_direction(a_reg, b_reg, names),
            "n": d["n"], "current": round(vals[-1], 1), "last_date": S.iso(s[-1][0]),
            "desc": d,
        })

    windows = tuple(w.strip() for w in (a.windows or "1y,3y").split(",") if w.strip())
    as_of = S.parse_date(a.as_of) if a.as_of else None
    pct_tbl = S.percentile_table(aligned, pairs, windows=windows, as_of=as_of)
    for rec in pct_tbl:
        for w in windows:
            if w in rec.get("windows", {}):
                rec["windows"][w]["label"] = S.percentile_label(rec["windows"][w]["pct"])

    rolling = {}
    for a_reg, b_reg in pairs:
        s = S.spread_series(aligned, a_reg, b_reg)
        if not s:
            continue
        roll = S.rolling_percentile(s, window_days=365)
        rolling[S.pair_key(a_reg, b_reg)] = [[S.iso(d), None if v is None else round(v, 1), n]
                                             for d, v, n in roll]

    # 异常阶段
    events = ev_cfg.get("events", [])
    regimes = {}
    fund_regions = ev_cfg.get("fundamentals", {}).get("regions", {})
    for a_reg, b_reg in S.unordered_pairs(region_order):
        s = S.spread_series(aligned, a_reg, b_reg)
        regs = S.regime_scan(s)
        for rg in regs:
            rg["events"] = S.events_in_window(events, rg["start"], rg["end"])
            rg["region_snapshots"] = {}
            lo = aligned["dates"].index(S.parse_date(rg["start"]))
            hi = aligned["dates"].index(S.parse_date(rg["end"]))
            for reg in region_order:
                all_v = aligned["values"][reg]
                win = [v for v in all_v[lo:hi + 1] if v is not None]
                base_win = [v for v in all_v[max(0, lo - 52):lo] if v is not None]
                rg["region_snapshots"][reg] = {
                    "name": names[reg],
                    "mean": None if not win else round(S.mean(win), 1),
                    "change_vs_prior_yr": (None if (not win or not base_win)
                                           else round(S.mean(win) - S.mean(base_win), 1)),
                    "min": None if not win else round(min(win), 1),
                    "max": None if not win else round(max(win), 1),
                }
            rg["fundamentals"] = {
                reg: {
                    "capacity_mt": fund_regions.get(reg, {}).get("capacity_mt"),
                    "capacity_note": fund_regions.get(reg, {}).get("capacity_note"),
                    "producers": [{"name": p.get("name"), "capacity_mt": p.get("capacity_mt"),
                                   "route": p.get("route")}
                                  for p in fund_regions.get(reg, {}).get("producers", [])],
                    "surplus": fund_regions.get(reg, {}).get("surplus"),
                } for reg in region_order
            }
        regimes[S.pair_key(a_reg, b_reg)] = regs

    series = S.series_to_json(aligned, pairs)
    corr = {S.pair_key(x, y): S.pearson(aligned["values"][x], aligned["values"][y])
            for x, y in pairs}

    level_stats = {}
    last_d = aligned["dates"][-1]
    for reg in region_order:
        vals = aligned["values"][reg]
        st = S.describe(vals)
        st["current"] = round(vals[-1], 2) if vals[-1] is not None else None
        flat = [(d, None, None, v) for d, v in zip(aligned["dates"], vals) if v is not None]
        y1 = S.window_sample(flat, last_d, "1y")
        st["pct_1y"] = None if vals[-1] is None else round(S.percentile_of(vals[-1], y1), 1)
        st["pct_all"] = None if vals[-1] is None else round(S.percentile_of(vals[-1], [v for v in vals if v is not None]), 1)
        level_stats[reg] = st

    freight_rows = []
    embedded = bool(cal_def.get("freight_embedded"))
    for rid, rt in build_routes(routes_cfg).items():
        fr, to = rt.get("from"), rt.get("to")
        if fr not in aligned["values"] or to not in aligned["values"]:
            continue
        pf, pt = aligned["values"][fr][-1], aligned["values"][to][-1]
        if pf is None or pt is None:
            continue
        params = dict(routes_cfg.get("cost_params", {}))
        params["freight"] = rt.get("freight")
        params["short_haul"] = float(params.get("short_haul", 0.0) or 0.0)
        params["handler"] = float(params.get("handler", params.get("handling_fee", 0.0)) or 0.0)
        res = S.freight_adjusted_spread(pf, pt, rt, params)
        freight_rows.append({
            "route": rid, "from": fr, "to": to, "flow": rt.get("flow"),
            "distance_km": rt.get("distance_km"),
            "distance_km_range": rt.get("distance_km_range"),
            "distance_status": rt.get("distance_status"),
            "main_mode": rt.get("main_mode"),
            "lanes": rt.get("lanes", []),
            "freight": rt.get("freight"),
            "freight_basis": rt.get("freight_basis"),
            "freight_source": rt.get("freight_source"),
            "freight_date": rt.get("freight_date"),
            "alternatives": rt.get("freight_alternatives"),
            "result": res,
        })

    return {
        "caliber": caliber_key,
        "caliber_label": cal_def.get("label", caliber_key),
        "caliber_role": cal_def.get("role", ""),
        "target_caliber": target,
        "freight_embedded_in_price": embedded,
        "freight_embedded_warning": cal_def.get("freight_embedded_note", "") if embedded else "",
        "normalize_report": norm_report,
        "align": {
            "dropped": aligned["dropped"],
            "n_dropped": len(aligned["dropped"]),
            "n_used": len(aligned["dates"]),
            "max_staleness": {r: max([x for x in aligned["staleness"][r] if x is not None] or [0])
                              for r in region_order},
        },
        "series": series,
        "matrix": {"values": mat, "mean": mat_mean, "meta": mat_meta,
                   "regions": region_order, "date": S.iso(aligned["dates"][-1])},
        "pairs": pair_detail,
        "percentiles": pct_tbl,
        "windows": list(windows),
        "rolling_percentile": rolling,
        "correlation": corr,
        "level_stats": level_stats,
        "freight": {
            "mode": a.freight_mode,
            "params": {k: v for k, v in routes_cfg.get("cost_params", {}).items()
                       if k in ("loading_fee", "unloading_fee", "short_haul", "handler", "handling_fee")},
            "cost_params": routes_cfg.get("cost_params", {}),
            "routes": freight_rows,
            "basis_flags": sorted({x["freight_basis"] for x in freight_rows}),
            "distance_matrix": routes_cfg.get("distance_matrix", {}),
            "meta": routes_cfg.get("meta", {}),
        },
        "regimes": regimes,
        "n_obs": len(aligned["dates"]),
        "range": [S.iso(aligned["dates"][0]), S.iso(aligned["dates"][-1])],
        "names": names,
        "region_order": region_order,
    }


def main():
    ap = argparse.ArgumentParser(description="区域价差研究主分析")
    ap.add_argument("--csv", required=True, help="主口径数据（宽表或长表）")
    ap.add_argument("--csv-control", default=None, help="对照口径数据（可选）")
    ap.add_argument("--caliber", default="DELIVERED", help="主口径键（对应 config/project.json calibers）")
    ap.add_argument("--caliber-control", default="EXW", help="对照口径键")
    ap.add_argument("--config", default="config")
    ap.add_argument("--routes", default=None)
    ap.add_argument("--events", default=None)
    ap.add_argument("--align", default="weekly", choices=["exact", "asof", "weekly"])
    ap.add_argument("--max-staleness", type=int, default=None)
    ap.add_argument("--windows", default="1y,3y")
    ap.add_argument("--freight-mode", default="default", choices=["default", "manual", "none"])
    ap.add_argument("--freight-json", default=None)
    ap.add_argument("--regions", default=None)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--data-status", default=None, choices=["REAL", "DEMO", "CLIENT"])
    ap.add_argument("--out", default="build/result.json")
    a = ap.parse_args()

    proj_p, routes_p, events_p = resolve_paths(a)
    proj = load_json(proj_p)
    if not proj:
        raise SystemExit(f"读不到配置 {proj_p}")
    routes_cfg = load_json(routes_p)
    ev_cfg = load_json(events_p)
    P = proj.get("project", {})

    main_cal = run_one_caliber(a, proj, routes_cfg, ev_cfg, a.csv, a.caliber)
    ctrl = None
    if a.csv_control:
        ctrl = run_one_caliber(a, proj, routes_cfg, ev_cfg, a.csv_control, a.caliber_control)

    region_list = [r for r in P.get("regions", []) if r["id"] in main_cal["region_order"]]
    data_status = a.data_status or P.get("data_status", "DEMO")

    result = {
        "meta": {
            "product": P.get("product"), "product_en": P.get("product_en"),
            "spec": P.get("spec"), "spec_futures": P.get("spec_futures"),
            "packing": P.get("packing"), "unit": P.get("unit", "元/吨"),
            "frequency": P.get("frequency", "weekly"),
            "align_method": a.align,
            "data_status": data_status,
            "source_csv": os.path.basename(a.csv),
            "source_csv_control": os.path.basename(a.csv_control) if a.csv_control else None,
            "as_run": S.iso(date.today()),
            "as_of": main_cal["range"][1],
            "start": main_cal["range"][0], "end": main_cal["range"][1],
            "n_observations": main_cal["n_obs"],
            "n_observations_control": ctrl["n_obs"] if ctrl else None,
            "regions": [{
                "id": r["id"], "name": r["name"], "full_name": r.get("full_name", r["name"]),
                "rep_market": r.get("rep_market"), "lat": r.get("lat"), "lon": r.get("lon"),
                "role": r.get("role"),
                "quote_basis": r.get("quote_basis"), "quote_exw": r.get("quote_exw"),
                "delivery": r.get("delivery"), "payment": r.get("payment"), "tax": r.get("tax"),
                "source_org": r.get("source_org"), "exw_source": r.get("exw_source"),
                "basis_risk": r.get("basis_risk"),
            } for r in region_list],
            "windows": main_cal["windows"],
            "extra_regions_ignored": [],
            "hedge_online": P.get("hedge_online", False),
            "hedge_note": P.get("hedge_note", ""),
            "calibers": P.get("calibers", {}),
            "primary_caliber": a.caliber,
            "caliber_control": a.caliber_control if ctrl else None,
            "caliber_checklist": P.get("caliber_checklist", []),
            "known_gaps": P.get("known_gaps", []),
            "sources": P.get("sources", []),
            "mode_rule": routes_cfg.get("meta", {}).get("mode_rule", ""),
            "tonkm_anchor": routes_cfg.get("meta", {}).get("tonkm_anchor", ""),
            "delivered_caliber_note": routes_cfg.get("meta", {}).get("delivered_caliber_note", ""),
        },
        "primary": main_cal,
        "control": ctrl,
        "events": ev_cfg.get("events", []),
        "fundamentals": ev_cfg.get("fundamentals", {}),
    }

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1, default=str)

    names = main_cal["names"]
    order = main_cal["region_order"]
    print(f"[analyze] 主口径={main_cal['caliber_label']}  对齐={a.align}  "
          f"观测点={main_cal['n_obs']}  剔除={main_cal['align']['n_dropped']}  "
          f"{main_cal['range'][0]} ~ {main_cal['range'][1]}")
    if ctrl:
        print(f"[analyze] 对照口径={ctrl['caliber_label']}  观测点={ctrl['n_obs']}  "
              f"剔除={ctrl['align']['n_dropped']}")
    print(f"[analyze] 数据状态={data_status}")
    print("[analyze] 最新价格（主口径）：" + "  ".join(
        f"{names[r]}={main_cal['level_stats'][r]['current']}" for r in order))
    print("[analyze] 两两价差（主口径，当前）：")
    for pd_ in main_cal["pairs"]:
        if pd_.get("n"):
            d = pd_["desc"]
            print(f"    {pd_['label']:>10s} = {pd_['current']:>7.1f}  "
                  f"(N={pd_['n']}, 均值 {d['mean']:.1f}, 区间 {d['min']:.0f}~{d['max']:.0f})")
    print("[analyze] 历史分位（主口径）：")
    for rec in main_cal["percentiles"]:
        parts = [f"{w}={rec.get('windows',{}).get(w,{}).get('pct')}%(N={rec.get('windows',{}).get(w,{}).get('n')})"
                 for w in main_cal["windows"]]
        print(f"    {rec['pair']:>8s}  当前 {rec.get('current')}  " + "  ".join(parts))
    print("[analyze] 运费调整（主口径，注意内含运费告警）：")
    if main_cal["freight_embedded_in_price"]:
        print("    ⚠️ 主口径为送到价，运费已内含 → 本表仅为『到货成本』对照，不可当作可套利空间")
    for fr in main_cal["freight"]["routes"]:
        r = fr["result"]
        if r.get("ok"):
            print(f"    {fr['flow']:>10s}  {fr['distance_km']}km  运费[{fr['freight_basis']}] "
                  f"{r['freight_total']:.0f}/吨  扣费后差异={r['ref_diff']:+.0f}")
        else:
            print(f"    {fr['flow']:>10s}  运费未知 → 不计算")
    print(f"[analyze] → {a.out}")


if __name__ == "__main__":
    main()
