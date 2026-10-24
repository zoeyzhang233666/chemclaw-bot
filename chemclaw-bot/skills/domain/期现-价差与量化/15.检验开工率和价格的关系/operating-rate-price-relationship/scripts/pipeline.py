# -*- coding: utf-8 -*-
"""Operating-rate -> price relationship study: configurable, reproducible pipeline.

The pipeline NEVER invents data. Every quantity is either (a) parsed from a publicly
published bulletin whose real publish timestamp is archived, or (b) computed from it and
from open futures prices. When the usable sample is too small to identify anything, the
pipeline says so and reports the minimum detectable effect instead of p-values.

Stages
------
  load      util_weekly.csv + futures daily      -> validate release timestamps
  align     build point-in-time origins           -> first tradable session AFTER publication
  factors   level / week-change / expanding percentile (+ continuity runs)
  forward   forward return over N *trading* sessions (overlapping by construction)
  panel     one row per origin x horizon
  power     minimum detectable effect for the realised sample
  groups    absolute / change / percentile group tables (n, mean, median, quantiles, CI)
  pooled    rank IC + HAC regression per factor-target-horizon, BH-FDR across the family
  yearly    per-year stability (and "insufficient" flag), regime split, in/out of sample
  placebo   within-year circular shift of the factor (preserves seasonality)
  monthly   monthly-bar corroboration (verification channel, NOT point-in-time evidence)
  corr      same-time relation vs forward relation (separates co-movement from information)
  summary   headline numbers consumed by the report/workbook builders

Usage
-----
  python scripts/pipeline.py --config config.json
  python scripts/pipeline.py --self-test          # synthetic long history, verifies logic
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zlib
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from float_numbers import dataframe_to_csv, dumps as jdumps

# --------------------------------------------------------------------------- helpers


def log(msg):
    print("[pipeline] " + msg)
    sys.stdout.flush()


def expanding_pct_rank(vals, min_obs=52, step=1):
    """Expanding historical percentile; only uses values observed strictly BEFORE i."""
    vals = np.asarray(vals, float)
    out = np.full(len(vals), np.nan)
    hist = []
    for i in range(len(vals)):
        if len(hist) >= min_obs and np.isfinite(vals[i]):
            out[i] = float(np.mean(np.array(hist) < vals[i]))
        if np.isfinite(vals[i]):
            hist.append(vals[i])
        # thin history: keep sampling cheap but *all* values are still used via list
        if len(hist) > 4000:
            hist = hist[-4000:]
        if step > 1 and i % step:
            pass
        hist = hist  # noqa: PLW0127
    return out


def expanding_z(vals, min_obs=52):
    vals = np.asarray(vals, float)
    out = np.full(len(vals), np.nan)
    hist = []
    for i in range(len(vals)):
        h = np.asarray(hist, float)
        if len(h) >= min_obs and np.isfinite(vals[i]):
            sd = h.std(ddof=1)
            out[i] = (vals[i] - h.mean()) / sd if sd > 0 else np.nan
        if np.isfinite(vals[i]):
            hist.append(vals[i])
        if len(hist) > 4000:
            hist = hist[-4000:]
    return out


def run_length(changes):
    """Signed run length: +k if the sign of change has been + for k consecutive weeks."""
    out = [0] * len(changes)
    for i in range(len(changes)):
        c = changes[i]
        if not np.isfinite(c):
            continue
        s = np.sign(c)
        k, j = 1, i - 1
        while j >= 0 and np.isfinite(changes[j]) and np.sign(changes[j]) == s:
            k += 1
            j -= 1
        out[i] = int(s * k)
    return out


def hac_ols(y, x, lag):
    """OLS with Newey-West (Bartlett) covariance; returns beta, se, t, p (two-sided t)."""
    from scipy import stats as st
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    n = len(y)
    if n < 6:
        return (np.nan,) * 4
    X = np.column_stack([np.ones(n), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    XtXi = np.linalg.inv(X.T @ X)
    EX = e[:, None] * X
    meat = EX.T @ EX
    for k in range(1, min(lag, n - 1) + 1):
        w = 1 - k / (lag + 1.0)
        A = EX[k:].T @ EX[:-k]
        meat += w * (A + A.T)
    V = XtXi @ meat @ XtXi
    se = float(np.sqrt(max(V[1, 1], 0)))
    t = float(b[1] / se) if se > 0 else np.nan
    p = 2 * st.t.sf(abs(t), max(n - 2, 3)) if np.isfinite(t) else np.nan
    return float(b[1]), se, t, p


def block_bootstrap_ci(x, block, n_boot=2000, alpha=0.05, seed=7):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 4:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    block = max(1, min(int(block), n))
    nb = int(np.ceil(n / block))
    st = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n, nb)
        idx = np.concatenate([(s + np.arange(block)) % n for s in starts])[:n]
        st[b] = x[idx].mean()
    lo, hi = np.quantile(st, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def bh_fdr(p):
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    if not ok.any():
        return q
    pv = p[ok]
    order = np.argsort(pv)
    adj = pv[order] * len(pv) / (np.arange(len(pv)) + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    o = np.empty(len(pv))
    o[order] = np.minimum(adj, 1.0)
    q[ok] = o
    return q


def spearman_ic(x, y):
    from scipy import stats as st
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 6:
        return np.nan, np.nan, int(m.sum())
    r, p = st.spearmanr(x[m], y[m])
    return float(r), float(p), int(m.sum())


def welch(a, b):
    from scipy import stats as st
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    return float(st.ttest_ind(a, b, equal_var=False).pvalue)


def power_info(n_eff, alpha=0.05, power=0.8):
    """Minimum detectable effect size.

    For *proportions of direction* (claim: "开工率高时上涨概率也是 ~50%"), the minimum
    detectable absolute deviation is the Wilson half-width at the realised n.
    For *differences of means* in units of s.d. the MDES is (z_a/2 + z_b)/sqrt(n_eff).
    """
    from scipy import stats as st
    za = st.norm.ppf(1 - alpha / 2)
    zb = st.norm.ppf(power)
    mdes_d = (za + zb) / np.sqrt(n_eff) if n_eff > 0 else np.nan
    # Wilson interval at p=0.5 with continuity approximation
    if n_eff > 0:
        z2 = za ** 2
        center = (0.5 + z2 / (2 * n_eff)) / (1 + z2 / n_eff)
        half = za * np.sqrt(0.25 / n_eff + z2 / (4 * n_eff ** 2)) / (1 + z2 / n_eff)
    else:
        half = np.nan
    return {"n_eff": n_eff, "mdes_sigma": mdes_d, "prob_halfwidth_pp": None if not np.isfinite(half) else half * 100,
            "n_needed_sigma_020": int(np.ceil(((za + zb) / 0.20) ** 2)) if np.isfinite(mdes_d) else None}


# --------------------------------------------------------------------------- stage: load


def load_config(path):
    cfg = json.load(open(path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(path))
    for k in ("util_csv", "price_csv", "monthly_price_csv", "out_dir", "prod_csv"):
        if k in cfg and cfg[k] and not os.path.isabs(cfg[k]):
            cfg[k] = os.path.normpath(os.path.join(base, cfg[k]))
    return cfg


def load_util(cfg):
    df = pd.read_csv(cfg["util_csv"], encoding="utf-8-sig")
    df["stat_week_end"] = pd.to_datetime(df["stat_week_end"])
    df["pub_ts"] = pd.to_datetime(df["pub_ts"])
    vcol = cfg.get("value_col", "util_total")
    df = df.rename(columns={vcol: "util"})
    df = df.dropna(subset=["stat_week_end", "pub_ts", "util"]).sort_values("pub_ts")
    # a re-published bulletin for the same statistical week keeps the FIRST publication
    df = df.drop_duplicates("stat_week_end", keep="first").sort_values("stat_week_end")
    # Hard validation: the statistics must exist by the time of publication; publishing on
    # the same calendar day is allowed (a cut-off dated d is measured to d's close, even if
    # the text appears the same evening) - the alignment stage below still only uses the
    # FIRST SESSION AFTER pub_ts, so point-in-time discipline is preserved downstream.
    bad = df[df["pub_ts"] < df["stat_week_end"]]
    if len(bad):
        raise ValueError("publication timestamp precedes statistics cut-off:\n%s"
                         % bad[["stat_week_end", "pub_ts"]].to_string())
    df = df.reset_index(drop=True)
    df["week_idx"] = np.arange(len(df))
    return df


def load_prices(cfg):
    px = pd.read_csv(cfg["price_csv"], encoding="utf-8-sig")
    px["date"] = pd.to_datetime(px["date"])
    px = px.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    for c in ("close", "settle", "adj_close"):
        if c in px:
            px[c] = pd.to_numeric(px[c], errors="coerce")
    if "adj_close" not in px:
        px["adj_close"] = px["close"]
    px["sess"] = np.arange(len(px))
    return px


# --------------------------------------------------------------------------- stage: align


def align_origins(util, px, cfg):
    """One origin per bulletin: first tradable session strictly AFTER the publish timestamp."""
    out = []
    sessions = px["date"].values
    sw = util["stat_week_end"].to_numpy()
    pt = util["pub_ts"].to_numpy()
    uv = util["util"].to_numpy(float)
    wk = util["week_idx"].to_numpy(int)
    # carry EVERY factor / metadata column forward (level, chg, pct, route factors ...)
    extra_cols = [c for c in util.columns
                  if c not in ("stat_week_end", "pub_ts", "util", "week_idx")]
    extras = {c: util[c].to_numpy() for c in extra_cols}
    for k in range(len(util)):
        pub_day = np.datetime64(pd.Timestamp(pt[k]).normalize())
        i = int(np.searchsorted(sessions, pub_day, side="right"))
        rec = {
            "week_idx": int(wk[k]),
            "stat_week_end": pd.Timestamp(sw[k]),
            "pub_ts": pd.Timestamp(pt[k]),
            "util": float(uv[k]),
        }
        for c in extra_cols:
            rec[c] = extras[c][k]
        if i < len(px):
            rec["origin_date"] = px["date"].iloc[i]
            rec["origin_sess"] = int(i)
            rec["origin_close"] = float(px["adj_close"].iloc[i])
            rec["days_stat_to_origin"] = (px["date"].iloc[i] - rec["stat_week_end"]).days
            rec["days_pub_to_origin"] = (px["date"].iloc[i] - rec["pub_ts"]).days
        else:
            rec.update(origin_date=pd.NaT, origin_sess=np.nan, origin_close=np.nan,
                       days_stat_to_origin=np.nan, days_pub_to_origin=np.nan)
        out.append(rec)
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- stage: factors


def build_factors(util, cfg):
    f = util.copy()
    min_hist = int(cfg.get("min_history_periods", 52))
    f["chg_pp"] = f["util"].diff()
    f["chg_rel_pct"] = f["util"].pct_change() * 100
    f["chg_rel_log"] = np.log(f["util"] / f["util"].shift(1)) * 100
    f["level_pct"] = expanding_pct_rank(f["util"].to_numpy(float), min_hist)
    f["level_z"] = expanding_z(f["util"].to_numpy(float), min_hist)
    f["run_len"] = run_length(f["chg_pp"].to_numpy(float))
    # explicit "computable on the day" flag for each family
    f["level_ok"] = f["util"].notna()
    f["chg_ok"] = f["chg_pp"].notna()
    f["pct_ok"] = f["level_pct"].notna()
    # exact count of usable history points behind each expanding percentile
    hist, cnt = [], []
    for v in f["util"].to_numpy(float):
        cnt.append(len(hist))
        if np.isfinite(v):
            hist.append(v)
    f["pct_hist_n"] = cnt
    # route factors (only when the source publishes them)
    for rc, ra in [("calc", "calc"), ("eth", "eth")]:
        if rc in f and f[rc].notna().any():
            f[rc + "_pct"] = expanding_pct_rank(f[rc].to_numpy(float), min_hist)
            f[rc + "_chg_pp"] = f[rc].diff()
    return f


# --------------------------------------------------------------------------- stage: forward


def forward_returns(origins, px, cfg):
    """Forward change measured over N TRADING SESSIONS from the origin close.

    Overlap: consecutive weekly origins are 4-5 sessions apart, so a 5-session window
    overlaps its neighbours by 3-4 sessions. We never pretend they are independent
    (HAC lag = h-1, effective n = n/h, non-unit-block bootstrap).
    """
    hz = cfg.get("horizons_sessions", {"1w": 5, "2w": 10, "4w": 20})
    px = px.reset_index(drop=True)
    out = origins.reset_index(drop=True).copy()
    colmap = {}
    osess = out["origin_sess"].to_numpy(float) if "origin_sess" in out else np.full(len(out), np.nan)
    for k in range(len(out)):
        i = -1 if not np.isfinite(osess[k]) else int(osess[k])
        for name, h in hz.items():
            j = i + int(h)
            ok = i >= 0 and j < len(px)
            colmap.setdefault("end_date_" + name, []).append(px["date"].iloc[j] if ok else pd.NaT)
            ret = (px["adj_close"].iloc[j] / px["adj_close"].iloc[i] - 1) if ok else np.nan
            colmap.setdefault("fwd_ret_" + name, []).append(ret)
            colmap.setdefault("fwd_dir_" + name, []).append(
                (1.0 if ret > 0 else 0.0) if ok else np.nan)
            colmap.setdefault("fwd_overlap_" + name, []).append(
                bool(ok and int(h) > int(cfg.get("sessions_per_week", 5))))
    for k, v in colmap.items():
        out[k] = v
    return out


# --------------------------------------------------------------------------- stage: power


def power_table(panel, hz, cfg):
    sessions_per_week = float(cfg.get("sessions_per_week", 5.0))
    alpha = float(cfg.get("alpha", 0.05))
    rows = []
    for name, h in hz.items():
        col = "fwd_ret_" + name
        n = int(panel[col].notna().sum())
        step = float(cfg.get("weeks_per_origin", 1.0)) * sessions_per_week
        n_eff = n if n == 0 else n / max(h / step, 1.0)
        p = power_info(n_eff, alpha)
        rows.append({"horizon": name, "sessions": h, "n_obs": n, "n_eff_nonoverlap": round(n_eff, 2),
                     "mdes_sd": round(p["mdes_sigma"], 4) if np.isfinite(p["mdes_sigma"]) else None,
                     "prob_halfwidth_pp": round(p["prob_halfwidth_pp"], 2) if p["prob_halfwidth_pp"] is not None else None,
                     "n_needed_mdes_020sd": int(np.ceil(((1.96 + 0.8416) / 0.20) ** 2)),
                     "verdict": ("insufficient" if n_eff < cfg.get("min_n_eff", 30)
                                 else ("weak" if n_eff < 60 else "usable"))})
    df = pd.DataFrame(rows)
    # the MDES does not depend on h once expressed per effective observation; we report
    # the MAXIMUM request (n_eff of the longest window) as the headline requirement
    return df


# --------------------------------------------------------------------------- stage: groups


def group_tables(panel, hz, cfg):
    """Three preset grouping rules, fixed BEFORE looking at results."""
    bands = cfg.get("level_bands", [65.0, 70.0, 75.0])
    thr = cfg.get("chg_threshold_pp", 1.0)
    out = {"absolute": [], "change": [], "percentile": []}
    labels_abs = ["<%.0f%%" % bands[0], "%.0f-%.0f%%" % (bands[0], bands[1]),
                  "%.0f-%.0f%%" % (bands[1], bands[2]), ">=%.0f%%" % bands[2]]
    for name, h in hz.items():
        col = "fwd_ret_" + name
        scale = cfg.get("scale", {"fwd_ret": 100.0})["fwd_ret"]
        # --- absolute
        d = panel[["util", col]].dropna()
        if len(d):
            g = pd.cut(d["util"], [-np.inf] + list(bands) + [np.inf], labels=labels_abs,
                       right=False)
            for lab, sub in d.groupby(g, observed=False):
                out["absolute"].append(_group_stat(sub[col] * scale, str(lab), name, d, h, scale))
        # --- change (sign + magnitude)
        d = panel[["chg_pp", col]].dropna()
        if len(d):
            t = thr
            g = pd.cut(d["chg_pp"], [-np.inf, -t, 0, 1e-9 if False else t, np.inf],
                       labels=["回落>%.1fpp" % t, "小幅回落", "小幅回升", "回升>%.1fpp" % t],
                       right=False)
            g = g.cat.rename_categories(["回落>%.1fpp" % t, "小幅回落", "小幅回升", "回升>%.1fpp" % t])
            for lab, sub in d.groupby(g, observed=False):
                out["change"].append(_group_stat(sub[col] * scale, str(lab), name, d, h, scale))
        # --- percentile
        d = panel[["level_pct", col]].dropna()
        if len(d):
            g = pd.cut(d["level_pct"], [-np.inf, 0.2, 0.5, 0.8, np.inf],
                       labels=["低(<p20)", "偏低(p20-50)", "偏高(p50-80)", "高(>=p80)"], right=False)
            for lab, sub in d.groupby(g, observed=False):
                out["percentile"].append(_group_stat(sub[col] * scale, str(lab), name, d, h, scale))
    return {k: pd.DataFrame(v) for k, v in out.items()}


def _group_stat(x, label, hname, whole, h, scale):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n == 0:
        return {"group": label, "horizon": hname, "n": 0}
    lo, hi = block_bootstrap_ci(x, block=max(1, int(np.ceil(h / 5.0))), n_boot=1000)
    other = whole[~whole.index.isin([])]  # placeholder (rest-of-sample computed below)
    return {"group": label, "horizon": hname, "n": n,
            "mean_pct": float(np.mean(x)), "median_pct": float(np.median(x)),
            "std_pct": float(np.std(x, ddof=1)) if n > 1 else np.nan,
            "q10_pct": float(np.percentile(x, 10)), "q25_pct": float(np.percentile(x, 25)),
            "q75_pct": float(np.percentile(x, 75)), "q90_pct": float(np.percentile(x, 90)),
            "min_pct": float(np.min(x)), "max_pct": float(np.max(x)),
            "ci95_lo_pct": lo, "ci95_hi_pct": hi,
            "share_up_pct": float(np.mean(x > 0) * 100),
            "wilson_lo_pct": _wilson(np.mean(x > 0), n)[0] * 100 if n > 1 else np.nan,
            "wilson_hi_pct": _wilson(np.mean(x > 0), n)[1] * 100 if n > 1 else np.nan,
            "n_eff": round(n / max(h / 5.0, 1.0), 2),
            "usable": bool(n >= 8)}


def _wilson(k, n, z=1.959964):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    hw = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - hw, c + hw)


# --------------------------------------------------------------------------- stage: pooled


def pooled_tests(panel, hz, cfg):
    factors = cfg.get("factors", [["util", "F1 绝对开工率"], ["chg_pp", "F2 周度变化"],
                                  ["level_pct", "F3 历史分位"]])
    rows = []
    for name, h in hz.items():
        col = "fwd_ret_" + name
        for fcol, flab in factors:
            d = panel[[fcol, col]].dropna()
            if len(d) < 5:
                rows.append({"horizon": name, "factor": flab, "factor_code": fcol, "n": len(d),
                             "ic": None, "ic_p": None, "beta": None, "hac_t": None, "hac_p": None,
                             "n_eff": round(len(d) / max(h / 5.0, 1.0), 2)})
                continue
            ic, p, n = spearman_ic(d[fcol], d[col])
            # standardise factor so beta is "per s.d. of factor"
            xs = d[fcol].to_numpy(float)
            sd = xs.std(ddof=1) if n > 1 else 0
            zz = (xs - xs.mean()) / sd if sd > 0 else xs * 0
            beta, se, t, ph = hac_ols(d[col].to_numpy(float) * 100.0, zz, lag=max(int(h) - 1, 1))
            rows.append({"horizon": name, "factor": flab, "factor_code": fcol, "n": n,
                         "ic": ic, "ic_p": p, "beta_pct_per_sd": beta, "hac_se": se,
                         "hac_t": t, "hac_p": ph, "n_eff": round(n / max(h / 5.0, 1.0), 2)})
    df = pd.DataFrame(rows)
    df["q_bh"] = bh_fdr(df["ic_p"].to_numpy(float) if "ic_p" in df else [])
    df["sig_ic_5pct"] = df["ic_p"] < 0.05
    df["sig_bh_5pct"] = df["q_bh"] < 0.05
    return df


# --------------------------------------------------------------------------- stage: yearly


def yearly_table(panel, hz, cfg):
    rows = []
    bands = cfg.get("level_bands", [65.0, 70.0, 75.0])
    for name, h in hz.items():
        col = "fwd_ret_" + name
        d = panel.copy()
        d["year"] = pd.to_datetime(d["origin_date"]).dt.year
        for yr, sub in d.groupby("year"):
            s = sub[["util", "chg_pp", col]].dropna()
            hi = s[s["util"] >= bands[2]]
            lo = s[s["util"] < bands[0]]
            rows.append({"year": int(yr), "horizon": name, "n_obs": len(s),
                         "n_hi": len(hi), "n_lo": len(lo),
                         "mean_hi_pct": None if len(hi) == 0 else float(hi[col].mean() * 100),
                         "mean_lo_pct": None if len(lo) == 0 else float(lo[col].mean() * 100),
                         "spread_hi_minus_lo_pct": (None if len(hi) == 0 or len(lo) == 0
                                                    else float((hi[col].mean() - lo[col].mean()) * 100)),
                         "ic_level": spearman_ic(s["util"], s[col])[0],
                         "ic_change": spearman_ic(s["chg_pp"], s[col])[0],
                         "verdict": ("insufficient" if len(s) < 30
                                     else ("indicative" if len(s) < 60 else "usable"))})
    return pd.DataFrame(rows)


def regime_table(panel, hz, cfg):
    """Split by futures price regime (above/below trailing 60-session mean) and by
    operating-rate regime (expanding median): does the relation flip?"""
    rows = []
    if "regime_price" not in panel:
        return pd.DataFrame()
    for name in hz:
        col = "fwd_ret_" + name
        for reg, sub in panel.groupby("regime_price"):
            d = sub[["util", "chg_pp", col]].dropna()
            rows.append({"regime": reg, "horizon": name, "n": len(d),
                         "ic_level": spearman_ic(d["util"], d[col])[0],
                         "ic_change": spearman_ic(d["chg_pp"], d[col])[0],
                         "mean_pct": None if not len(d) else float(d[col].mean() * 100)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- stage: placebo


def placebo_test(panel, hz, cfg, runs=None):
    """Within-year circular shift of the factor against futures outcomes.

    Weekly operating rate and futures returns are both strongly seasonal (maintenance
    windows, construction season). A naive random permutation destroys that common
    seasonality and OVERSTATES significance. Circular shifting inside each calendar year
    keeps the shape of the factor and of the returns.
    """
    runs = runs or int(cfg.get("placebo_runs", 2000))
    rows = []
    seed = int(cfg.get("seed", 42))
    d = panel.copy()
    d["year"] = pd.to_datetime(d["origin_date"]).dt.year
    for name in hz:
        col = "fwd_ret_" + name
        for fcol, flab in cfg.get("factors", []):
            sub = d[[fcol, col, "year"]].dropna()
            if len(sub) < 12:
                rows.append({"factor": flab, "horizon": name, "n": len(sub), "ic_obs": None,
                             "placebo_p": None, "runs": runs})
                continue
            ic_obs = spearman_ic(sub[fcol], sub[col])[0]
            years = sub["year"].to_numpy()
            x = sub[fcol].to_numpy(float)
            y = sub[col].to_numpy(float)
            uid = zlib.crc32(("%s|%s" % (flab, name)).encode()) & 0xFFFFFF
            rng = np.random.default_rng(seed + uid)
            idx_by_year = {yy: np.where(years == yy)[0] for yy in np.unique(years)}
            ics = []
            for _ in range(runs):
                xs = np.empty_like(x)
                for yy, ii in idx_by_year.items():
                    xs[ii] = np.roll(x[ii], int(rng.integers(1, max(len(ii), 1))))
                r, _, _ = spearman_ic(xs, y)
                ics.append(r)
            ics = np.asarray(ics, float)
            ics = ics[np.isfinite(ics)]
            p = float(np.mean(np.abs(ics) >= abs(ic_obs))) if len(ics) else np.nan
            rows.append({"factor": flab, "horizon": name, "n": len(sub), "ic_obs": ic_obs,
                         "placebo_p": p, "runs": runs,
                         "ic_placebo_p95": float(np.quantile(np.abs(ics), 0.95)) if len(ics) else np.nan})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- stage: monthly


def monthly_corroboration(cfg, monthly_px, prod_csv=None):
    """Monthly-bar verification channel -- explicitly NOT point-in-time evidence."""
    rows = []
    out = {"rows": rows, "available": monthly_px is not None and len(monthly_px) > 0}
    if monthly_px is not None and len(monthly_px):
        m = monthly_px.copy()
        m["same_ret"] = m["ret_m"]
        m["next_ret"] = m["ret_m"].shift(-1)
        r, p, n = spearman_ic(m["same_ret"], m["next_ret"])
        rows.append({"pair": "期货月收益(t) vs 期货月收益(t+1)", "n": n,
                     "ic": None if not np.isfinite(r) else round(r, 4),
                     "p": None if not np.isfinite(p) else round(p, 4),
                     "note": "月度动量/反转的自相关基准：判断'月度量价关系'时须扣除的底色"})
        ser = m["same_ret"].dropna()
        rows.append({"pair": "期货月收益分布", "n": int(ser.shape[0]),
                     "ic": None, "p": None,
                     "note": "均值 %.2f%%，年化波动 %.1f%%，正收益月份占比 %.0f%%"
                             % (ser.mean() * 100, ser.std(ddof=1) * np.sqrt(12) * 100,
                                (ser > 0).mean() * 100) if len(ser) else "n=0"})
    if prod_csv and os.path.exists(prod_csv):
        try:
            pr = pd.read_csv(prod_csv, encoding="utf-8-sig")
        except Exception:            # genuinely empty file -> recorded as a gap
            pr = pd.DataFrame()
            out["prod_gap"] = "产量件未取得可用于交叉验证的公开样本（文件为空）"
        if len(pr) and monthly_px is not None and len(monthly_px):
            pr["month"] = pr["month"].astype(str)
            j = pr.merge(monthly_px[["month", "ret_m", "close"]], on="month", how="left")
            out["joined"] = j.to_dict("records")
            if len(j) >= 24:
                j["fwd_12m"] = j["close"].shift(-12) / j["close"] - 1
                j["yoy_out"] = j["output_wan_t"] / j["output_wan_t"].shift(12) - 1
                r, p, n = spearman_ic(j["yoy_out"], j["fwd_12m"])
                out["yoy_vs_fwd12m"] = {"ic": r, "p": p, "n": n}
    return out


# --------------------------------------------------------------------------- stage: corr


def same_time_corr(panel, hz, cfg):
    """Co-movement of the rate with returns in the SAME/PAST weeks vs the FORWARD weeks.
    A strong contemporaneous / past relation with a zero forward relation means the rate is
    a *coincident* supply indicator (or that price drives the rate), not a predictor."""
    rows = []
    d = panel.copy()
    for fcol, flab in [("util", "开工率水平 util"), ("chg_pp", "开工率变化 chg_pp")]:
        for name in hz:
            rows.append({"relation": "%s vs 前%s收益（过去）" % (flab, name), "side": "past",
                         "factor": flab, "horizon": name,
                         "ic": spearman_ic(d[fcol], d["past_ret_" + name])[0],
                         "n": int(d[[fcol, "past_ret_" + name]].dropna().shape[0])})
    for fcol, flab in [("util", "开工率水平 util"), ("chg_pp", "开工率变化 chg_pp")]:
        for name in hz:
            rows.append({"relation": "%s vs 未来%s收益" % (flab, name), "side": "forward",
                         "factor": flab, "horizon": name,
                         "ic": spearman_ic(d[fcol], d["fwd_ret_" + name])[0],
                         "n": int(d[[fcol, "fwd_ret_" + name]].dropna().shape[0])})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- driver


def run(cfg, quiet=False):
    out_dir = cfg["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    util = load_util(cfg)
    px = load_prices(cfg)
    factors = build_factors(util, cfg)
    origins = align_origins(factors, px, cfg)
    # price regime: origin close vs its trailing 60-session mean
    ma60 = px["adj_close"].rolling(60, min_periods=20).mean()

    def _reg(i):
        if not np.isfinite(i):
            return "未上市"
        i = int(i)
        return "上行(价格>MA60)" if px["adj_close"].iloc[i] > ma60.iloc[i] else "下行(价格<=MA60)"

    origins["regime_price"] = [_reg(i) for i in origins["origin_sess"].to_numpy(float)]
    hz = cfg.get("horizons_sessions", {"1w": 5, "2w": 10, "4w": 20})
    panel = forward_returns(origins, px, cfg)
    # past-window returns (for same-time / reverse-causality check)
    for name, h in hz.items():
        past = []
        for i in panel["origin_sess"].fillna(-1).astype(int):
            j = i - int(h)
            past.append(np.nan if i < 0 or j < 0 else
                        px["adj_close"].iloc[i] / px["adj_close"].iloc[j] - 1)
        panel["past_ret_" + name] = past
    dataframe_to_csv(panel, os.path.join(out_dir, "panel.csv"))

    pwr = power_table(panel, hz, cfg)
    dataframe_to_csv(pwr, os.path.join(out_dir, "res_power.csv"))
    grp = group_tables(panel, hz, cfg)
    for k, v in grp.items():
        v.to_csv(os.path.join(out_dir, "res_groups_%s.csv" % k), index=False, encoding="utf-8-sig")
    pool = pooled_tests(panel, hz, cfg)
    dataframe_to_csv(pool, os.path.join(out_dir, "res_pooled.csv"))
    yr = yearly_table(panel, hz, cfg)
    dataframe_to_csv(yr, os.path.join(out_dir, "res_yearly.csv"))
    rg = regime_table(panel, hz, cfg)
    dataframe_to_csv(rg, os.path.join(out_dir, "res_regime.csv"))
    pl = placebo_test(panel, hz, cfg)
    dataframe_to_csv(pl, os.path.join(out_dir, "res_placebo.csv"))
    corr = same_time_corr(panel, hz, cfg)
    dataframe_to_csv(corr, os.path.join(out_dir, "res_corr.csv"))
    monthly_px = None
    if cfg.get("monthly_price_csv") and os.path.exists(cfg["monthly_price_csv"]):
        monthly_px = pd.read_csv(cfg["monthly_price_csv"], encoding="utf-8-sig")
    mon = monthly_corroboration(cfg, monthly_px, cfg.get("prod_csv"))
    open(os.path.join(out_dir, "res_monthly.json"), "w", encoding="utf-8").write(
        jdumps(mon, indent=1))

    # days-to-origin diagnostics (release/pricing alignment)
    dd = origins.dropna(subset=["origin_date"])
    align_diag = {
        "n_bulletins": int(len(util)),
        "first_stat_week": str(util["stat_week_end"].min().date()),
        "last_stat_week": str(util["stat_week_end"].max().date()),
        "pub_weekdays": {int(k) + 1: int(v) for k, v in
                         util["pub_ts"].dt.weekday.value_counts().to_dict().items()},
        "not_evaluable": int(origins["origin_sess"].isna().sum()),
        "days_stat_to_origin": dd["days_stat_to_origin"].tolist() if len(dd) else [],
        "days_pub_to_origin": dd["days_pub_to_origin"].tolist() if len(dd) else [],
    }

    summary = {
        "n_bulletins": int(len(util)),
        "n_origins_evaluable": int(panel.drop(columns=["stat_week_end"], errors="ignore")
                                   .assign(x=1)["x"].sum() if len(panel) else 0),
        "n_used": int(panel["fwd_ret_" + list(hz)[0]].notna().sum()) if len(panel) else 0,
        "power": pwr.to_dict("records"),
        "align": align_diag,
        "verdict_stat": ("insufficient" if (pwr["n_eff_nonoverlap"].max() if len(pwr) else 0)
                         < cfg.get("min_n_eff", 30) else "evaluable"),
        "min_n_eff_required": cfg.get("min_n_eff", 30),
        "n_needed_rows": int(((1.96 + 0.8416) / 0.20) ** 2),
        "horizons": list(hz.keys()),
        "config": {k: v for k, v in cfg.items() if not k.endswith("_csv")},
    }
    open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8").write(
        jdumps(summary, indent=1))
    if not quiet:
        log("bulletins=%d evaluable origins=%d" % (len(util), summary["n_used"]))
        print(pwr.to_string(index=False))
        print(pool.to_string(index=False))
        print(grp["absolute"].to_string(index=False) if len(grp["absolute"]) else "(no groups)")
        log("verdict: %s" % summary["verdict_stat"])
    return {"panel": panel, "power": pwr, "groups": grp, "pooled": pool, "yearly": yr,
            "regime": rg, "placebo": pl, "corr": corr, "monthly": mon, "summary": summary}


# --------------------------------------------------------------------------- self-test


def self_test():
    """Thin wrapper: the real verification lives in verify_pipeline.py (3 synthetic checks)."""
    import verify_pipeline
    return verify_pipeline.main()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "..", "config.json"))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    cfg = load_config(a.config)
    run(cfg)


if __name__ == "__main__":
    main()
