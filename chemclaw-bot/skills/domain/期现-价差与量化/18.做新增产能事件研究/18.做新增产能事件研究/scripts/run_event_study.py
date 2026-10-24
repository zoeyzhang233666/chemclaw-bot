# -*- coding: utf-8 -*-
"""
run_event_study.py — 中国PP新增产能事件研究：主分析脚本

输入
----
data/events_pp.json                    事件库（已核实的分层日期）
data/raw/pp_futures_pp0_daily.csv      PP 主力连续日线（新浪 pp0）
data/raw/pp_spot_bench_100ppi.csv      生意社 PP(拉丝) 基准价（日度）
data/raw/pp_fundamentals.csv           库存/开工率/下游负荷（从官方经评文章抽取）

输出
----
out/analysis.json                     全部计算结果（供 HTML/Excel 使用）
out/event_level_paths.csv             逐事件逐跨度的路径数值
out/aggregate_stats.csv               分组汇总统计

方法论要点（与 SKILL.md 一致）
------------------------------
1. 事件分层：announce/record/eia/construction/mechanical/commissioning/startup/
   first_product/commercial/rampup 是**不同事件**，不合并统计。
2. 三个口径：
   cumulative = 后 k 期 − 前 1 期（含事件前漂移）
   abnormal   = cumulative − 同期"相对日历对齐"的市场平均变化（主口径）
   surprise   = cumulative − 事件前同长度前段变化（二阶差分）
3. 相对日历反事实：事件前第 k 个观测 → 事件后第 k 个观测，用全部事件的平均曲线做基准，
   最大程度抵消"同期其他项目也在投产"的污染。
4. 设计产能 ≠ 投产当天新增产量：用爬坡曲线换算实际增量。
5. 样本 < 3 时不给 t 值/显著性，一律标注 insufficient。
"""
import csv
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "build"))

import eventengine as EE  # noqa: E402

DATA = os.path.join(BASE, "data")
RAW = os.path.join(DATA, "raw")
OUT = os.path.join(BASE, "out")
os.makedirs(OUT, exist_ok=True)

HORIZONS = (20, 60, 120)


def load_series():
    smap = {}
    # 1) 期货
    fp = os.path.join(RAW, "pp_futures_pp0_daily.csv")
    fut = EE.load_price_csv(fp, name="PP主力连续(元/吨)", value_col="close")
    smap["futures"] = fut

    # 2) 现货：优先用长序列（生意社 100ppi 商品主力基差表 日快照，2019 起 1887 点）
    long_sp = os.path.join(RAW, "longhist", "pp_spot_long.csv")
    if os.path.exists(long_sp):
        dates, vals = [], []
        with open(long_sp, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    dates.append(r["date"])
                    vals.append(float(r["value"]))
                except Exception:
                    pass
        if len(vals) >= 50:
            # 口径：生意社 PP 现货价（page 未明示区域，不宣称"华东"）
            smap["spot_lasi"] = EE.Series("生意社PP现货价(100ppi基差表)", dates, vals,
                                          "D", "prev", "元/吨")

    # 2b) 生意社「PP(拉丝)/PP(纤维)基准价」—— 2026-04 起，作交叉验证序列
    sp = os.path.join(RAW, "pp_spot_bench_100ppi.csv")
    for spec, key, label in (("拉丝", "spot_bench_lasi", "生意社PP(拉丝)基准价"),
                             ("纤维", "spot_bench_fiber", "生意社PP(纤维)基准价")):
        if not os.path.exists(sp):
            continue
        dates, vals = [], []
        with open(sp, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r["spec"] == spec:
                    try:
                        dates.append(r["date"])
                        vals.append(float(r["price"]))
                    except Exception:
                        pass
        if len(vals) >= 2:
            smap[key] = EE.Series(label, dates, vals, "D", "prev", "元/吨")

    # 3) 基差（现货 − 期货）
    if "spot_lasi" in smap:
        smap["basis"] = smap["spot_lasi"].diff_series(smap["futures"], name="基差(现货-期货)")

    # 4) 基本面（库存/开工率）—— 优先使用逐点可溯源的独立数据集
    ext = {
        "pp_inventory_producer.csv": ("inventory", "PP生产企业库存(万吨,隆众)", "W", "万吨"),
        "pp_capacity_utilization.csv": ("operating", "PP产能利用率(%,隆众全样本)", "W", "%"),
        "pp_inventory_commercial.csv": ("inv_commercial", "PP商业库存总量(万吨)", "W", "万吨"),
        "pp_maintenance_loss.csv": ("maintenance", "PP装置检修损失量(万吨)", "W", "万吨"),
    }
    for fn, (key, label, freq, unit) in ext.items():
        p = os.path.join(RAW, fn)
        if not os.path.exists(p):
            continue
        ds, vs = [], []
        with open(p, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    ds.append(r["date"])
                    vs.append(float(r["value"]))
                except Exception:
                    pass
        if len(vs) >= 2:
            smap[key] = EE.Series(label, ds, vs, freq, "prev", unit)

    # 5) 从官方经评正文抽取的库存/开工率（补充稀疏点）
    fpath = os.path.join(RAW, "pp_fundamentals.csv")
    if os.path.exists(fpath):
        buckets = {}
        with open(fpath, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                buckets.setdefault(r["field"], []).append((r["pub_date"], float(r["value"])))
        for fld, pairs in buckets.items():
            if len(pairs) < 3:      # 单点序列无法做事件研究，直接丢弃
                continue
            name = {"inventory": "PP库存(经评抽取,万吨)", "operating": "PP开工率(经评抽取,%)",
                    "downstream": "下游负荷(%)", "spot_lasi": "拉丝基准价(文内)",
                    "weekly_out": "周均产量(万吨)"}.get(fld, fld)
            smap["txt_" + fld] = EE.Series(name, [p[0] for p in pairs], [p[1] for p in pairs],
                                           "W", "prev", "")
    return smap


def main():
    ev = json.load(open(os.path.join(DATA, "events_pp.json"), encoding="utf-8"))
    events = ev["events"]
    projects = {p["project_id"]: p for p in ev["projects"]}
    smap = load_series()
    print("series:", {k: str(v) for k, v in smap.items()})

    # 只用"正式投产类"事件作为反事实基准日期集（避免与预期类混算）
    startup_dates = sorted({e["date"] for e in events
                            if e["stage"] in EE.REALIZATION_STAGES})

    per_event, aggregate = EE.run_event_study(
        [e for e in events], smap, horizons=HORIZONS,
        counterfactual_events=startup_dates)

    # ---- 低频率序列（库存/开工率/检修）改用自然日窗口重算 ----
    SPARSE = {"inventory", "operating", "inv_commercial", "maintenance"}
    for r in per_event:
        for vk in list(r["vars"].keys()):
            if vk not in SPARSE or vk not in smap:
                continue
            byday = EE.compute_paths_by_days(smap[vk], r["date"], horizons=HORIZONS)
            # 自然日窗口没有"相对日历反事实"，超额变化留空（不虚构基准）
            for n in HORIZONS:
                if not isinstance(byday.get(n), dict):
                    continue
                cell = byday[n]
                # 窗口内观测 < 2 表示该事件根本不在该序列覆盖区间内 → 判为不可计算
                if (cell.get("obs_count") or 0) < 2:
                    cell["pct"] = None
                    cell["change"] = None
                    cell["surprise_pct"] = None
                cell["abnormal_pct"] = None
            r["vars"][vk + "_cal"] = byday
    # 用自然日窗口的稀疏变量重算汇总，并替换原 k-观测版
    sparse_keys = {vk + "_cal" for vk in SPARSE}
    per_event_sparse = [{"project_id": r["project_id"], "date": r["date"], "stage": r["stage"],
                         "vars": {k: v for k, v in r["vars"].items() if k in sparse_keys}}
                        for r in per_event]
    sparse_agg = EE.aggregate_events(per_event_sparse, HORIZONS)
    aggregate = [a for a in aggregate if a["var"] not in SPARSE] + sparse_agg

    # 补充：产能占比（用投产当年产能基数）
    cap = ev["meta"]["capacity_base_wt"]
    for r in per_event:
        p = projects.get(r["project_id"], {})
        yr = r["date"][:4]
        base = cap.get(yr)
        dv = p.get("design_capacity")
        r["capacity_base"] = base
        r["share_pct"] = (100.0 * dv / base) if (base and dv) else None
        # 投产当月实际增量（不把设计产能当当天产量）
        r["ramp_month0_wt"] = EE.incremental_output(dv, 0)
        r["ramp_month3_wt"] = EE.incremental_output(dv, 3)
        r["ramp_month6_wt"] = EE.incremental_output(dv, 6)
        r["ramp_12m_cum_wt"] = EE.cumulative_output(dv, 12)

    # 安慰剂检验（对正式投产事件 × 期货 60日）
    placebo = {}
    for vk in ("futures", "spot_lasi", "basis"):
        if vk not in smap:
            continue
        for h in HORIZONS:
            pt = EE.placebo_test(smap[vk], startup_dates, horizon=h, n_draw=400)
            placebo["%s@%d" % (vk, h)] = pt

    result = {
        "meta": ev["meta"],
        "series_info": {k: {"name": v.name, "n": len(v),
                            "start": EE.iso(v.dates[0]) if v.dates else None,
                            "end": EE.iso(v.dates[-1]) if v.dates else None,
                            "freq": v.freq, "unit": v.unit}
                        for k, v in smap.items()},
        "horizons": list(HORIZONS),
        "per_event": per_event,
        "aggregate": aggregate,
        "placebo": placebo,
        "startup_dates_used_for_counterfactual": startup_dates,
        "ramp_assumption": EE.RAMP_ASSUMPTION,
        "default_ramp": EE.DEFAULT_RAMP,
    }
    EE.dump_json(result, os.path.join(OUT, "analysis.json"))
    print("analysis.json written. per_event=%d aggregate=%d" % (len(per_event), len(aggregate)))

    # CSV 导出
    with open(os.path.join(OUT, "event_level_paths.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "project_id", "project_name", "region", "process",
                    "design_capacity_wt", "stage", "date", "var", "horizon",
                    "base_value", "post_value", "post_date",
                    "cumulative_pct", "market_rel_pct", "abnormal_pct",
                    "pre_pct", "surprise_pct", "share_pct", "concurrent_projects_120d"])
        for r in per_event:
            for vk, paths in r["vars"].items():
                if "_status" in paths:
                    w.writerow([r["event_id"], r["project_id"], r["project_name"], r["region"],
                                r["process"], r["design_capacity"], r["stage"], r["date"],
                                vk, "", "", "", "", "", "", "", "", r["share_pct"],
                                r["concurrent_projects_within_120d"]])
                    continue
                for h in HORIZONS:
                    p = paths.get(h, {})
                    w.writerow([r["event_id"], r["project_id"], r["project_name"], r["region"],
                                r["process"], r["design_capacity"], r["stage"], r["date"],
                                vk, h, p.get("base_value"), p.get("post_value"), p.get("post_date"),
                                p.get("pct"), p.get("market_rel_change"), p.get("abnormal_pct"),
                                p.get("pre_pct"), p.get("surprise_pct"), r["share_pct"],
                                r["concurrent_projects_within_120d"]])

    with open(os.path.join(OUT, "aggregate_stats.csv"), "w", newline="", encoding="utf-8-sig") as f:
        cols = ["var", "stage", "stage_label", "horizon", "n", "mean_pct", "median_pct", "sd_pct",
                "t_cum", "pos_share", "sign_p", "mean_abnormal", "t_abnormal",
                "mean_surprise", "t_surprise", "ci90_lo", "ci90_hi", "insufficient"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for a in aggregate:
            w.writerow({k: a.get(k) for k in cols})
    print("CSVs written.")
    return result


if __name__ == "__main__":
    main()
