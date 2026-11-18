# -*- coding: utf-8 -*-
"""
season.py —— 库存季节性统计核心
==================================
输入：build_cache.py 产出的 cache 目录（a_sample.pkl / b_sample.pkl）+ config.json
输出：seasonal.json（HTML / Excel 生成器的唯一数据契约）+ 若干 CSV

方法（公式逐条见 references/03-方法论与公式.md）
------------------------------------------------------------------
1. 周次对齐：ISO 周年 + ISO 周次 = 季节坐标（跨年周归入其 ISO 年）。
2. 频率核验：相邻两期间隔中位数与最大值；间隔 > 10 天记缺报周。
3. 口径核验：单位、覆盖范围、统计机构、样本起始、披露变化、官方增减额与表格差分的差异。
4. 季节形态：ln(I_t) = a_year + f(week) + e_t，f 为周次的 3 阶多项式（去规模）；
   对 2026 留出做样本外检验，同时给出水平法对照。
5. 周次分布：过去 N 年（剔除本年）同周次的均值/中位数/分位带，样本不足则标记。
6. 当前分位：当期值在过去 N 年同周次样本中的历史分位；另给“去季节分位”。
7. 累去库：4/12/26 周累计变化（吨位与百分比）、连续累/去库周数、历史同期分位。
8. 样本变化：披露状态月度时间线、覆盖偏差（华南占比）按年漂移、断点/异常段敏感性场景。
9. 异常年份：按年汇总去季节残差。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# 与数据层共享的替代值定义（唯一来源，避免 Excel 与 HTML 各算一遍）
from build_cache import add_east_from_port, share_ref_south


# ----------------------------------------------------------------------------- 工具
def _f(x, nd=3):
    """安全转 float 并四舍五入；无效值返回 None（JSON 里就是 null）。"""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return round(v, nd)


def _pct_rank(value, arr):
    """历史分位（中位数插值）：严格小于的比例 + 0.5×相等比例，返回 (分位, 样本数)。"""
    arr = np.asarray([a for a in arr if a is not None and isinstance(a, (int, float))
                      and np.isfinite(a)], dtype=float)
    if not len(arr) or value is None or not np.isfinite(value):
        return None, 0
    below = float((arr < value).sum())
    equal = float((arr == value).sum())
    return round(100.0 * (below + 0.5 * equal) / len(arr), 1), int(len(arr))


def _q(arr, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    arr = np.asarray([a for a in arr if a is not None and isinstance(a, (int, float))
                      and np.isfinite(a)], dtype=float)
    if not len(arr):
        return {f"p{int(q * 100)}": None for q in qs}
    return {f"p{int(q * 100)}": round(float(np.quantile(arr, q)), 2) for q in qs}


def _clean(vals):
    return [float(v) for v in vals if v is not None and isinstance(v, (int, float)) and np.isfinite(v)]


# ----------------------------------------------------------------------------- 季节拟合
def _fourier(wk, K):
    """周次 w 的傅里叶设计矩阵：常数项 + K 组 sin/cos（周期 52 周）。"""
    wk = np.asarray(wk, dtype=float)
    cols = [np.ones_like(wk)]
    for k in range(1, K + 1):
        cols += [np.sin(2 * np.pi * k * wk / 52.0), np.cos(2 * np.pi * k * wk / 52.0)]
    return np.column_stack(cols)


def fit_seasonal(panel: pd.DataFrame, value_col: str, K: int = 2, log_space: bool = True, ma_win: int = 53):
    """
    季节分解（乘法式，对数空间）：  ln I_t = trend_t + f(week_t) + e_t
      trend_t —— 以 52 周中心化移动平均估计（吸收产能扩张、格局切换等慢变量）
      f(week) —— 周次的傅里叶调和项（K=2，正负两个半年的主波 + 次波），
                 对“去向趋势的偏离”做最小二乘；端点处用日历周均值兜底，
                 因此当前周的季节基准仍然可用（不外推多项式）。
      e_t     —— 去季节残差，用于异常检测。
    返回 (含 deseason / resid 的面板, [trend_coef, K], R²)。
    """
    d = panel.dropna(subset=[value_col]).copy().sort_values("asof").reset_index(drop=True)
    if d.empty:
        return None, None, None
    v = d[value_col].astype(float)
    if log_space and (v <= 0).any():
        log_space = False
    ln = np.log(v) if log_space else v
    s = pd.Series(ln.values, index=pd.to_datetime(d["asof"]))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    # 52 周中心化移动平均：两侧都缺时用单侧兜底（端点不足则用可得的尾部/首部均值）
    ma = s.rolling(ma_win, center=True, min_periods=max(8, ma_win // 4)).mean()
    ma = ma.bfill().ffill()
    dev = (s - ma).rename("dev")
    wk = pd.Series(d["iso_week"].astype(float).values, index=s.index).reindex(dev.index)
    m = dev.notna() & wk.notna()
    beta, _, _, _ = np.linalg.lstsq(_fourier(wk[m].values, K), dev[m].values, rcond=None)
    f = _fourier(wk.values, K) @ beta
    resid = dev.values - f
    pred = ma.values + f
    d["trend"] = np.exp(ma.values) if log_space else ma.values
    d["season_factor"] = np.exp(f) if log_space else f
    d["deseason"] = np.exp(pred) if log_space else pred
    d["resid"] = resid
    d["fit"] = d["deseason"]
    ss_tot = float(((dev[m].values - dev[m].values.mean()) ** 2).sum())
    ss_res = float((resid[m.values] ** 2).sum())
    r2 = round(1 - ss_res / ss_tot, 3) if ss_tot > 0 else None
    # 季节强度：季节效应本身的振幅（峰谷差，%）
    ff = _fourier(np.arange(1, 53), K) @ beta
    amp = float((np.exp(ff.max() - ff.min()) - 1) * 100) if log_space else None
    return d, {"K": K, "ma_win": ma_win, "beta": [_f(b, 6) for b in beta], "amp_pct": _f(amp, 1)}, r2


# ----------------------------------------------------------------------------- 主流程
def run(cache_dir: Path, cfg: dict, out_dir: Path):
    a = pd.read_pickle(cache_dir / "a_sample.pkl")
    b_path = cache_dir / "b_sample.pkl"
    b = pd.read_pickle(b_path) if b_path.exists() else pd.DataFrame()
    out_dir.mkdir(parents=True, exist_ok=True)

    asof = pd.Timestamp(cfg["asof"])
    primary_key = cfg.get("primary_metric_key", "east")
    g = cfg.get("guardrails", {})
    yrs = int(g.get("default_sample_years", 5))

    a["asof"] = pd.to_datetime(a["asof"])
    a = a.sort_values("asof").reset_index(drop=True)
    a["season_year"] = a["asof"].dt.isocalendar().year.astype(int)
    a["iso_week"] = a["asof"].dt.isocalendar().week.astype(int)
    cur_year = int(asof.isocalendar().year)
    cur_wk = int(asof.isocalendar().week)
    # 只保留“实际有数据”的历史年：样本从年中开始的话，机械减年份会带出空年份
    _have = set(int(y) for y in a["season_year"].unique())
    hist_years = [y for y in (cur_year - k for k in range(1, yrs + 1)) if y in _have]
    n_hist_years = len(hist_years)
    # 只保留截至日及之前的记录（防止未来数据泄漏）
    a = a[a["asof"] <= asof].reset_index(drop=True)

    # ---------------- 1. 数据完整性 ----------------
    gaps = a["asof"].diff().dt.days.dropna()
    integrity = {
        "n_weeks": int(len(a)),
        "start": a["asof"].min().strftime("%Y-%m-%d"),
        "end": a["asof"].max().strftime("%Y-%m-%d"),
        "gap_median_days": _f(gaps.median(), 1),
        "gap_max_days": _f(gaps.max(), 1),
        "missing_weeks": int(a["week_missing"].sum()),
        "missing_list": [x.strftime("%Y-%m-%d") for x in a.loc[a["week_missing"], "asof"]],
        "freq_ok": bool(float(gaps.max()) <= float(g.get("min_freq_weekly_max_gap_days", 10))),
        "span_years": _f((a["asof"].max() - a["asof"].min()).days / 365.25, 2),
    }

    # ---------------- 2. 口径核验 ----------------
    meth = {str(k): int(v) for k, v in a["east_method"].value_counts(dropna=False).items()}
    dis = a[a["east_dchg_gap"].abs() > 0.05] if "east_dchg_gap" in a else a.iloc[0:0]
    calib = {
        "metric_key": primary_key,
        "metric_label": cfg["metrics"][primary_key]["label"],
        "unit": cfg["unit"],
        "issuer": cfg["issuer"],
        "carrier": cfg["carrier"],
        "frequency": cfg["frequency"],
        "inventory_class": cfg["metrics"][primary_key]["inventory_class"],
        "calendar": cfg["metrics"][primary_key]["calendar"],
        "coverage_regions": cfg.get("regions", {}),
        "value_methods": meth,
        "east_available": int(a["east"].notna().sum()),
        "east_available_last": (a.loc[a["east"].notna(), "asof"].max().strftime("%Y-%m-%d")
                                if a["east"].notna().any() else None),
        "est_weeks": int((a["east_method"] == "east_estimated").sum()),
        "est_max_chain": _f(pd.to_numeric(a["east_chain"], errors="coerce").max(), 0),
        "official_chg_weeks": int(a["is_chg_official"].sum()),
        "table_chg_weeks": int(a["east_dchg_table"].notna().sum()),
        "chg_discrepancy_weeks": int(len(dis)),
        "chg_discrepancy_detail": [
            {"asof": r["asof"].strftime("%Y-%m-%d"),
             "chg_official": _f(r["east_dchg_ev"], 2),
             "chg_table": _f(r["east_dchg_table"], 2),
             "diff": _f(r["east_dchg_gap"], 2)}
            for _, r in dis.iterrows()],
        "region_split_weeks": int(a["ev_region_split"].sum()),
        "region_split_last": (a.loc[a["ev_region_split"], "asof"].max().strftime("%Y-%m-%d")
                              if a["ev_region_split"].any() else None),
        "prov_full_weeks": int(a["prov_full"].sum()),
        # 源数据自洽性缺陷登记：原文总量与表格合计不一致的期数（不静默抹平，报告中披露）
        "total_mismatch_weeks": int((a.get("ev_total_diff", pd.Series(dtype=float)).abs() > 0.02).sum())
        if "ev_total_diff" in a.columns else 0,
        "total_mismatch_detail": [
            {"asof": r["asof"].strftime("%Y-%m-%d"), "ev_total": _f(r["ev_total"], 2),
             "table_total": _f(r["port_total"], 2), "diff": _f(r["ev_total_diff"], 2)}
            for _, r in a[a.get("ev_total_diff", pd.Series(index=a.index, dtype=float)).abs() > 0.02].iterrows()
        ] if "ev_total_diff" in a.columns else [],
        "b_sample": {"n": int(len(b)),
                     "start": (b["asof"].min().strftime("%Y-%m-%d") if len(b) else None),
                     "end": (b["asof"].max().strftime("%Y-%m-%d") if len(b) else None)},
    }

    # ---------------- 3. 全国港口 → 华东 的水平替代（缺失期定位用） ----------------
    # east_from_port 与 share_ref_south 由 build_cache 统一计算并落盘，
    # 保证 Excel 与 HTML 使用完全相同的替代值定义（避免两处各算一遍）。
    a["east"] = pd.to_numeric(a["east"], errors="coerce")
    if "east_from_port" not in a.columns:
        a = add_east_from_port(a)
    share_ref = float(a.attrs.get("share_ref_south") or share_ref_south(a))

    # ---------------- 4. 季节拟合 ----------------
    panel = a[(a["season_year"] <= cur_year) & (a["season_year"] > cur_year - yrs - 1)]
    fit, coef, r2 = fit_seasonal(panel, "east", K=2, log_space=True)
    fit_lvl, coef_lvl, r2_lvl = fit_seasonal(panel, "east", K=2, log_space=False)
    season_series = None
    if fit is not None:
        season_series = {
            "asof": [x.strftime("%Y-%m-%d") for x in fit["asof"]],
            "value": [_f(v, 2) for v in fit["east"]],
            "fit": [_f(v, 2) for v in fit["deseason"]],
            "trend": [_f(v, 2) for v in fit["trend"]],
            "season_factor": [_f(v, 4) for v in fit["season_factor"]],
            "resid_pct": [_f(100 * v, 2) for v in fit["resid"]],
            "year": [int(v) for v in fit["season_year"]],
            "week": [int(v) for v in fit["iso_week"]],
        }
    # 样本外检验（留一年）：用其余年份估计趋势+季节形状，预测被留出年份的相对偏离
    oos = None
    if fit is not None:
        errs = []
        pv = panel.dropna(subset=["east"]).copy()
        pv["east"] = pd.to_numeric(pv["east"], errors="coerce")
        for yy in sorted(pv["season_year"].unique()):
            te = pv[pv["season_year"] == yy]
            if len(te) < 8:
                continue
            tr = pv[pv["season_year"] != yy]
            mm_, _, _ = fit_seasonal(tr, "east", K=2, log_space=True)
            if mm_ is None or "season_factor" not in mm_:
                continue
            fmap = dict(zip(mm_["iso_week"].astype(int), mm_["season_factor"]))
            vals = pd.to_numeric(te["east"], errors="coerce")
            # 只在“水平值可得”的周次上检验；缺失期不得进入误差统计
            mask = vals.notna() & (vals > 0)
            if mask.sum() < 8:
                continue
            anchor = float(vals[mask].mean()) / float(np.mean(
                [fmap.get(int(x), 1.0) for x in te.loc[mask, "iso_week"]]))
            for wk_, v_ in zip(te.loc[mask, "iso_week"], vals[mask]):
                pred = anchor * fmap.get(int(wk_), 1.0)
                if pred and np.isfinite(pred):
                    errs.append(abs(pred - v_) / v_)
        errs = [e for e in errs if np.isfinite(e)]
        if errs:
            oos = {"n": int(len(errs)), "mape_log": _f(100 * float(np.mean(errs)), 1), "preferred": "log"}

    # ---------------- 5. 周次分布（剔除本年），按指标分别统计 ----------------
    hist = a[(a["season_year"] < cur_year) & (a["season_year"] >= cur_year - yrs)]

    def week_dist(metric):
        out = {}
        if metric not in hist:
            return out
        for wk in range(1, 54):
            sub = hist[hist["iso_week"] == wk]
            vals = _clean(sub[metric].tolist())
            if not vals:
                continue
            q = _q(vals)
            q.update({
                "week": wk, "n": len(vals), "mean": _f(np.mean(vals), 2), "median": _f(np.median(vals), 2),
                "sd": _f(np.std(vals, ddof=1), 3) if len(vals) > 1 else None,
                "years": [int(y) for y in sub.loc[sub[metric].notna(), "season_year"]],
                "insufficient": bool(len(vals) < int(g.get("min_sample_years", 4))),
                "values": {int(y): _f(v, 2) for y, v in zip(sub["season_year"], sub[metric]) if pd.notna(v)},
            })
            out[wk] = q
        return out

    weeks = week_dist("east")
    weeks_by_metric = {k: week_dist(k) for k in ("east", "port_total", "east_from_port", "jiangsu", "zhejiang")}

    # ---------------- 6. 当前值 / 分位 ----------------
    def current_block(metric, label, note="", tol=1):
        if metric not in a:
            return None
        rows = a[["asof", "iso_week", metric]].dropna()
        if rows.empty:
            return None
        last = rows.iloc[-1]
        wk = int(last["iso_week"])
        wks = [wk - 1, wk, wk + 1] if tol else [wk]
        hist_wk = _clean(hist.loc[hist["iso_week"].isin(wks), metric].tolist())
        hist_same = _clean(hist.loc[hist["iso_week"] == wk, metric].tolist())
        val = float(last[metric])
        pct, nref = _pct_rank(val, hist_wk)
        blk = {
            "metric": metric, "label": label, "note": note,
            "asof": last["asof"].strftime("%Y-%m-%d"), "iso_week": wk, "value": _f(val, 2),
            "hist_mean": _f(np.mean(hist_wk), 2) if hist_wk else None,
            "hist_median": _f(np.median(hist_wk), 2) if hist_wk else None,
            "hist_min": _f(np.min(hist_wk), 2) if hist_wk else None,
            "hist_max": _f(np.max(hist_wk), 2) if hist_wk else None,
            "band": _q(hist_wk) if hist_wk else {},
            "band_same_week": _q(hist_same) if hist_same else {},
            "n_hist": nref, "pct_rank": pct,
            "vs_mean": _f(val - np.mean(hist_wk), 2) if hist_wk else None,
            "vs_mean_pct": _f(100 * (val / np.mean(hist_wk) - 1), 1) if hist_wk else None,
            "yoy": None, "yoy_pct": None,
            "chg4w": None, "chg4w_pct": None, "chg12w": None, "chg12w_pct": None,
            "run_len": None, "run_label": None,
        }
        ly = _clean(a.loc[(a["season_year"] == cur_year - 1) &
                          a["iso_week"].isin([wk - 1, wk, wk + 1]) & (a["iso_week"] != wk), metric].tolist())
        if not ly:
            ly = _clean(a.loc[(a["season_year"] == cur_year - 1) & (a["iso_week"] == wk), metric].tolist())
        if ly:
            blk["yoy"] = _f(val - ly[0], 2)
            blk["yoy_pct"] = _f(100 * (val / ly[0] - 1), 1)
        # 连续累/去库状态与幅度：水平缺失时仍然可用（基于官方增减额）
        chg_only = a.loc[a["asof"] <= last["asof"], "east_dchg"].dropna()
        run, prev = 0, 0
        for v in chg_only.tolist():
            if not v:
                run, prev = 0, 0
                continue
            s = 1 if v > 0 else -1
            run = run + s if s == prev else s
            prev = s
        blk["run_len"] = int(run)
        blk["run_label"] = "连续累库" if run > 0 else ("连续去库" if run < 0 else "持平/断档")
        for span in (4, 12):
            if len(chg_only) >= span:
                blk[f"cum{span}w_chg"] = _f(float(chg_only.tail(span).sum()), 2)
        for span in (4, 12):
            if len(rows) > span:
                prev = float(rows[metric].iloc[-1 - span])
                blk[f"chg{span}w"] = _f(val - prev, 2)
                blk[f"chg{span}w_pct"] = _f(100 * (val / prev - 1), 1)
            else:
                blk[f"chg{span}w"] = None
                blk[f"chg{span}w_pct"] = None
        # 去季节分位：用季节模型把“当前值 / 当前季节基准”换算成残差，
        # 再放到历史同期（±1 周）残差分布中定位——这是“扣掉季节性之后还剩多少偏离”的度量。
        if fit is not None and metric == "east":
            fa = fit.dropna(subset=["east"])
            if len(fa):
                cur_res = float(fa["resid"].iloc[-1])
                same_dev = _clean(fa.loc[fa["iso_week"].isin(wks) & (fa["season_year"] < cur_year), "resid"].tolist())
                all_dev = _clean(fa.loc[fa["season_year"] < cur_year, "resid"].tolist())
                pr_dev, n_dev = _pct_rank(cur_res, same_dev)
                blk["deseason_resid_pct"] = _f(100 * cur_res, 1)
                blk["deseason_base"] = _f(float(fa["deseason"].iloc[-1]), 2)
                blk["pct_rank_deseason"] = pr_dev
                blk["n_hist_deseason"] = n_dev
                blk["band_deseason_pct"] = {k: _f(100 * v, 1) for k, v in _q(same_dev).items()}
                blk["share_hist_z2"] = _f(100 * float(np.mean(np.abs(np.array(all_dev)) > 2 * np.std(all_dev))), 1)
        return blk

    cur_east = current_block("east", "华东港口库存（江苏+浙江）", "主口径")
    cur_port = current_block("port_total", "全国港口库存（华东+华南）", "对照口径：含华南，规模不可与华东直接比较")
    cur_est = current_block("east_from_port", "华东（全国港口 × 近期华东占比换算）", "水平替代，非公布值")
    cur_js = current_block("jiangsu", "江苏港口库存", "华东分省，与浙江相加即华东")
    cur_zj = current_block("zhejiang", "浙江港口库存", "华东分省，与江苏相加即华东")

    # 华东增减额累计（水平缺失期唯一可用度量）
    chg_rows = a[["asof", "east_dchg"]].dropna()
    cum = {}
    for span in (1, 4, 12, 26, 52):
        cum[f"cum{span}w"] = _f(float(chg_rows["east_dchg"].tail(span).sum()), 2) if len(chg_rows) >= span else None
    # 同期历史对照：过去 N 年同一 ISO 周次的 4 周累计
    a["east_c4"] = a["east_dchg"].rolling(4).sum()
    a["east_c12"] = a["east_dchg"].rolling(12).sum()
    hist_c4, hist_c12 = [], []
    for yy in hist_years:
        sub = a[(a["season_year"] == yy) & a["iso_week"].isin([cur_wk - 1, cur_wk, cur_wk + 1])]
        hist_c4.extend(_clean(sub["east_c4"].tolist()))
        hist_c12.extend(_clean(sub["east_c12"].tolist()))

    # ---------------- 7. 累去库速度 / 连续状态 ----------------
    seq = a[["asof", "east_dchg", "is_chg_official", "east_method"]].copy()
    runs, run, prev_sign = [], 0, 0
    for _, r in seq.iterrows():
        v = r["east_dchg"]
        if v is None or not isinstance(v, (int, float)) or not np.isfinite(v) or v == 0:
            run = 0
            prev_sign = 0
        else:
            s = 1 if v > 0 else -1
            run = run + s if s == prev_sign else s
            prev_sign = s
        runs.append(run)
    seq["run"] = runs
    last_run = int(seq["run"].iloc[-1]) if len(seq) else 0
    speed = {
        "last_week_chg": _f(seq["east_dchg"].iloc[-1], 2) if len(seq) else None,
        "last_week_date": seq["asof"].iloc[-1].strftime("%Y-%m-%d") if len(seq) else None,
        "run_len": last_run,
        "run_label": "连续累库" if last_run > 0 else ("连续去库" if last_run < 0 else "持平/断档"),
        "cum1w": cum.get("cum1w"), "cum4w": cum.get("cum4w"), "cum12w": cum.get("cum12w"),
        "cum26w": cum.get("cum26w"), "cum52w": cum.get("cum52w"),
        "cum4w_pct_rank": _pct_rank(cum.get("cum4w"), hist_c4)[0],
        "cum12w_pct_rank": _pct_rank(cum.get("cum12w"), hist_c12)[0],
        "cum4w_hist_mean": _f(np.mean(hist_c4), 2) if hist_c4 else None,
        "cum4w_hist_band": _q(hist_c4) if hist_c4 else {},
        "cum12w_hist_mean": _f(np.mean(hist_c12), 2) if hist_c12 else None,
        "cum12w_hist_band": _q(hist_c12) if hist_c12 else {},
        "avg_abs_4w": _f(float(seq["east_dchg"].tail(4).abs().mean()), 2) if len(seq) >= 4 else None,
        "avg_abs_12w": _f(float(seq["east_dchg"].tail(12).abs().mean()), 2) if len(seq) >= 12 else None,
        "recent": [{"asof": r["asof"].strftime("%Y-%m-%d"), "chg": _f(r["east_dchg"], 2),
                    "official": bool(r["is_chg_official"]), "run": int(r["run"]),
                    "method": r["east_method"]} for _, r in seq.tail(14).iterrows()],
        "hist_chg_vol": _f(float(seq["east_dchg"].abs().median()), 2),
    }

    # ---------------- 8. 样本变化检验 ----------------
    a["month"] = a["asof"].dt.to_period("M").astype(str)
    disc = (a.groupby("month")
            .agg(n=("asof", "size"),
                 region_split=("ev_region_split", "sum"),
                 prov_full=("prov_full", "sum"),
                 east_tbl=("east_tbl", lambda s: int(s.notna().sum())),
                 official=("is_chg_official", "sum"))
            .reset_index())
    disc = disc.astype({c: int for c in ("n", "region_split", "prov_full", "east_tbl", "official")})

    both = a.dropna(subset=["east", "port_total"]).copy()
    both["south_share"] = (both["port_total"] - both["east"]) / both["port_total"]
    both["year"] = both["asof"].dt.year
    bias = (both.groupby("year")["south_share"]
            .agg(n="size", median="median", min="min", max="max").reset_index())
    bias_out = [{"year": int(r["year"]), "n": int(r["n"]), "median": _f(r["median"], 3),
                 "min": _f(r["min"], 3), "max": _f(r["max"], 3)} for _, r in bias.iterrows()]

    ex = (cfg.get("exception_windows") or [{}])[0]
    scen = []

    def add_scen(name, sub, metric="east"):
        vals = _clean(sub[metric].tolist())
        if vals:
            scen.append({"scenario": name, "n": len(vals), "mean": _f(np.mean(vals), 2),
                         "median": _f(np.median(vals), 2), "min": _f(np.min(vals), 2),
                         "max": _f(np.max(vals), 2)})

    base = a[(a["season_year"] < cur_year)]
    add_scen("全部可得周次（历史 N 年）", base)
    if ex.get("start"):
        keep = base[~((base["asof"] >= pd.Timestamp(ex["start"])) & (base["asof"] <= pd.Timestamp(ex["end"])))]
        add_scen(f"剔除异常段：{ex['name']}", keep)
    add_scen("仅近 2 个完整年", base[base["season_year"] >= cur_year - 2])
    add_scen("仅逐地区完整披露的周次", base[base["prov_full"]])
    if primary_key != "port_total":
        pass
    if len(b) and "east_proxy" not in b:
        bb = b.copy()
        bb["east_proxy"] = bb[["jiangsu", "zhejiang"]].sum(axis=1, min_count=2)
        add_scen("B 样本（2016-08~2018-05 回溯加总）", bb, "east_proxy")

    # ---------------- 9. 异常年份 ----------------
    anom = []
    if fit is not None:
        for yy, sub in fit.groupby("season_year"):
            sd = float(sub["resid"].std())
            z = sub["resid"] / sd if sd else sub["resid"] * np.nan
            imax = sub["resid"].abs().idxmax()
            anom.append({
                "year": int(yy), "n": int(len(sub)),
                "mean_dev_pct": _f(100 * sub["resid"].mean(), 1),
                "sd_dev_pct": _f(100 * sd, 1),
                "share_z2": _f(100 * float((z.abs() > 2).mean()), 1),
                "max_dev_week": int(sub.loc[imax, "iso_week"]),
                "max_dev_pct": _f(100 * float(sub.loc[imax, "resid"]), 1),
                "min": _f(sub["east"].min(), 2), "max": _f(sub["east"].max(), 2),
            })

    # ---------------- 10. 年度曲线 / 月度分布 ----------------
    curves = []
    curve_metrics = ("east", "port_total", "east_from_port", "jiangsu", "zhejiang")
    for yy, sub in a.groupby("season_year"):
        item = {
            "year": int(yy),
            "weeks": [int(w) for w in sub["iso_week"]],
            "chg": [_f(v, 2) for v in sub["east_dchg"]],
            "has_level": bool(sub["east"].notna().any()),
        }
        for mk in curve_metrics:
            item[mk] = [_f(v, 2) for v in sub[mk]] if mk in sub else []
        curves.append(item)
    mm = a[a["east"].notna() & (a["season_year"] < cur_year)].copy()
    mm["month"] = mm["asof"].dt.month
    month_stats = {}
    for mo, sub in mm.groupby("month"):
        vals = _clean(sub["east"].tolist())
        if vals:
            q = _q(vals)
            q.update({"month": int(mo), "n": len(vals), "mean": _f(np.mean(vals), 2),
                      "median": _f(np.median(vals), 2)})
            month_stats[int(mo)] = q
    # 月度曲线：各年 × 各自然月均值（供“月度频率”切换使用；注意按自然月，不按 ISO 周归属）
    # 注意：必须用精确列名，不能用 sub[mk] 的前缀匹配（"east" 会误匹配 "east_from_port"）
    a["cal_month"] = a["asof"].dt.month
    month_curves = []
    for yy, sub in a.groupby("season_year"):
        item = {"year": int(yy), "months": list(range(1, 13))}
        for mk in curve_metrics:
            col = sub[mk] if mk in sub.columns else None
            row = []
            for mo in range(1, 13):
                if col is None:
                    row.append(None)
                    continue
                s = col[sub["cal_month"] == mo]
                row.append(_f(s.mean(), 2) if s.notna().any() else None)
            item[mk] = row
        month_curves.append(item)

    pivot = a.pivot_table(index="iso_week", columns="season_year", values="east", aggfunc="last")

    out = {
        "meta": {
            "title": f"{cfg['product']} · {cfg['metric_name']} 季节性研究",
            "asof": asof.strftime("%Y-%m-%d"), "run_date": cfg.get("run_date"),
            "product": cfg["product"], "unit": cfg["unit"], "frequency": cfg["frequency"],
            "issuer": cfg["issuer"], "carrier": cfg["carrier"], "primary_metric": primary_key,
            "sample_years": yrs, "hist_years": hist_years, "cur_year": cur_year, "cur_week": cur_wk,
        },
        "integrity": integrity,
        "calibration": calib,
        "season_fit": {
            "r2": r2, "r2_level": r2_lvl, "model": coef, "model_level": coef_lvl,
            "oos": oos, "series": season_series,
            "sample_years_used": [int(y) for y in sorted(hist["season_year"].unique())],
            "log_space": True, "season_amp_pct": (coef or {}).get("amp_pct"),
        },
        "weeks": {str(k): v for k, v in sorted(weeks.items())},
        "weeks_by_metric": {mk: {str(k): v for k, v in sorted(mv.items())} for mk, mv in weeks_by_metric.items()},
        "month_stats": {str(k): v for k, v in sorted(month_stats.items())},
        "current": {"east": cur_east, "port_total": cur_port, "east_from_port": cur_est, "jiangsu": cur_js, "zhejiang": cur_zj},
        "level_missing": {"from": (a.loc[a["east"].notna(), "asof"].max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                          if a["east"].notna().any() else None,
                          "weeks": int((a["asof"] > a.loc[a["east"].notna(), "asof"].max()).sum())
                          if a["east"].notna().any() else 0,
                          "share_ref_south": _f(share_ref, 3)},
        "curves_month": month_curves,
        "speed": speed,
        "disclosure": {"monthly": json.loads(disc.to_json(orient="records", force_ascii=False)),
                       "region_split_last": calib["region_split_last"],
                       "east_level_last": calib["east_available_last"]},
        "coverage_bias": {"share_ref": _f(share_ref, 3), "by_year": bias_out},
        "scenarios": scen,
        "anomaly_years": anom,
        "curves": curves,
        "breakpoints": cfg.get("breakpoints", []),
        "exception_windows": cfg.get("exception_windows", []),
        "guardrails": g,
        "weekly_matrix": {
            "weeks": [int(i) for i in pivot.index],
            "years": [int(c) for c in pivot.columns],
            "values": [[_f(v, 2) if pd.notna(v) else None for v in pivot.loc[w]] for w in pivot.index],
        },
    }
    (out_dir / "seasonal.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    pd.DataFrame(weeks.values()).to_csv(out_dir / "seasonal_week.csv", index=False, encoding="utf-8-sig")
    pivot.reset_index().to_csv(out_dir / "weekly_matrix.csv", index=False, encoding="utf-8-sig")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    o = run(Path(args.cache), cfg, Path(args.out))
    ce = o["current"]["east"] or {}
    print(json.dumps({
        "r2": o["season_fit"]["r2"], "oos": o["season_fit"]["oos"],
        "east_current": {k: ce.get(k) for k in ("asof", "value", "pct_rank", "n_hist", "chg4w", "chg12w")},
        "speed": {k: o["speed"][k] for k in ("run_len", "cum4w", "cum12w", "cum4w_pct_rank")},
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()



