# -*- coding: utf-8 -*-
"""Inventory–Price Relationship Study — configurable, reproducible pipeline.

Reads
-----
  config.json                  study configuration (paths, thresholds, windows)
  <inventory>.csv              columns: asof, pub_ts, value[, region cols]
  <prices>.csv                 columns: date, spot, fut[, basis]

Writes
------
  panel_weekly.csv             per-week factors + forward outcomes
  res_pooled.csv               3 targets x N factors x 3 horizons, with HAC + BH-FDR
  res_groups_level.csv         level-quantile groups with bootstrap CI
  res_groups_wow.csv           week-over-week change groups
  res_groups_run.csv           consecutive-run groups
  res_yearly.csv               per-year stability
  res_placebo.csv              year-stratified placebo tests
  res_subsample.csv            non-overlapping / in-sample vs out-of-sample
  res_regime.csv               basis-regime split
  res_control.csv              collinearity-controlled regression
  summary.json                 headline numbers for the report

Usage
-----
  python pipeline.py --config examples/methanol-port-inventory/config.json
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import timedelta

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- stats core


def expanding_pct_rank(vals, min_obs=26):
    out = np.full(len(vals), np.nan)
    for i in range(len(vals)):
        hist = vals[:i]
        hist = hist[~np.isnan(hist)]
        if len(hist) >= min_obs and not np.isnan(vals[i]):
            out[i] = (hist < vals[i]).mean()
    return out


def expanding_z(vals, min_obs=26):
    out = np.full(len(vals), np.nan)
    for i in range(len(vals)):
        hist = vals[:i]
        hist = hist[~np.isnan(hist)]
        if len(hist) >= min_obs and not np.isnan(vals[i]):
            sd = hist.std(ddof=1)
            out[i] = (vals[i] - hist.mean()) / sd if sd > 0 else np.nan
    return out


def hac_ols(y, x, lag):
    from scipy import stats as st
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    XtXi = np.linalg.inv(X.T @ X)
    EX = e[:, None] * X
    meat = EX.T @ EX
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1.0)
        A = EX[k:].T @ EX[:-k]
        meat += w * (A + A.T)
    V = XtXi @ meat @ XtXi
    se = float(np.sqrt(max(V[1, 1], 0)))
    t = float(b[1] / se) if se > 0 else np.nan
    return float(b[0]), float(b[1]), se, t, 2 * st.t.sf(abs(t), max(len(y) - 2, 3))


def hac_multi(y, X, lag):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    XtXi = np.linalg.inv(X.T @ X)
    EX = e[:, None] * X
    meat = EX.T @ EX
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1.0)
        A = EX[k:].T @ EX[:-k]
        meat += w * (A + A.T)
    V = XtXi @ meat @ XtXi
    return b, np.sqrt(np.diag(V))


def newey_west_mean(x, lag):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 5:
        return (np.nan, np.nan, np.nan, n)
    mu = x.mean()
    e = x - mu
    var = (e @ e) / n
    for k in range(1, min(lag, n - 1) + 1):
        var += 2 * (1 - k / (lag + 1.0)) * (e[k:] @ e[:-k]) / n
    se = np.sqrt(max(var, 0) / n)
    return mu, se, (mu / se if se > 0 else np.nan), n


def block_bootstrap_ci(x, block, n_boot=2000, alpha=0.05, seed=7):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 8:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    block = max(1, min(block, n))
    nb = int(np.ceil(n / block))
    st = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n, nb)
        idx = np.concatenate([(s + np.arange(block)) % n for s in starts])[:n]
        st[b] = x[idx].mean()
    lo, hi = np.quantile(st, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def spearman(x, y):
    from scipy import stats as st
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 8:
        return np.nan, np.nan
    r, p = st.spearmanr(x[m], y[m])
    return float(r), float(p)


def describe(x, win, seed=7):
    from scipy import stats as st
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n == 0:
        return {"n": 0}
    mu, se, t, _ = newey_west_mean(x, max(win - 1, 1))
    lo, hi = block_bootstrap_ci(x, max(win, 1), seed=seed)
    return {"n": n, "mean": float(x.mean()), "median": float(np.median(x)),
            "std": float(x.std(ddof=1)) if n > 1 else np.nan,
            "p25": float(np.percentile(x, 25)), "p75": float(np.percentile(x, 75)),
            "min": float(x.min()), "max": float(x.max()),
            "ci_lo": lo, "ci_hi": hi, "se_hac": se, "t_hac": t,
            "p_hac": (2 * st.t.sf(abs(t), max(n - 1, 3)) if np.isfinite(t) else np.nan),
            "hit_up": float((x > 0).mean())}


def group_vs_rest(a, b, win):
    from scipy import stats as st
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    out = {"n_in": len(a), "n_out": len(b)}
    if len(a) < 5 or len(b) < 5:
        return out
    t, p = st.ttest_ind(a, b, equal_var=False)
    try:
        _, pu = st.mannwhitneyu(a, b, alternative="two-sided")
    except Exception:
        pu = np.nan
    out.update({"diff": float(a.mean() - b.mean()), "p_welch": float(p), "p_mwu": float(pu)})
    return out


def bh_fdr(p):
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
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


# --------------------------------------------------------------------------- stages


def canon_week_array(dates):
    """Map any as-of date to that week's canonical weekday (config: default 2 = Wednesday)."""
    wd = dates.dt.weekday
    delta = (wd - 2) % 7
    return dates - pd.to_timedelta(delta, unit="D")


def load_inputs(cfg):
    inv = pd.read_csv(cfg["inventory_csv"])
    for c in ("asof", "pub_ts"):
        inv[c] = pd.to_datetime(inv[c], errors="coerce")
    val_col = cfg.get("value_col", "value")
    inv = inv.rename(columns={val_col: "total"})
    inv = inv.dropna(subset=["asof", "pub_ts", "total"])
    inv["week"] = canon_week_array(inv["asof"])
    inv = inv.sort_values("pub_ts").drop_duplicates("week", keep="first")
    lo, hi = cfg.get("value_range", [1e-9, 1e9])
    inv = inv[(inv["total"] >= lo) & (inv["total"] <= hi)]
    inv = inv.sort_values("week").reset_index(drop=True)

    px = pd.read_csv(cfg["price_csv"])
    px["date"] = pd.to_datetime(px["date"])
    for c in ("spot", "fut"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px = px.dropna(subset=["spot", "fut"]).sort_values("date").drop_duplicates("date")
    if "basis" not in px:
        px["basis"] = px["spot"] - px["fut"]
    px["basis_rate"] = px["basis"] / px["fut"]
    return inv.reset_index(drop=True), px.reset_index(drop=True)


def build_factors(inv, min_obs=26):
    df = inv.copy()
    df["wow_chg"] = df["total"].diff()
    df["wow_pct"] = df["total"].pct_change()
    iso = df["week"].dt.isocalendar()
    df["iso_y"], df["iso_w"] = iso.year.astype(int), iso.week.astype(int)
    m = df.set_index(["iso_y", "iso_w"])["total"]
    df["ly"] = [m.get((y - 1, w), np.nan) for y, w in zip(df["iso_y"], df["iso_w"])]
    df["yoy"] = df["total"] / df["ly"] - 1
    df["w4_chg"] = df["total"] - df["total"].shift(4)
    df["lvl_pct"] = expanding_pct_rank(df["total"].to_numpy(float), min_obs)
    df["lvl_z"] = expanding_z(df["total"].to_numpy(float), min_obs)
    run = []
    for i in range(len(df)):
        if i == 0 or np.isnan(df["wow_chg"].iloc[i]):
            run.append(0)
            continue
        s = np.sign(df["wow_chg"].iloc[i])
        k, j = 1, i - 1
        while j >= 0 and not np.isnan(df["wow_chg"].iloc[j]) and np.sign(df["wow_chg"].iloc[j]) == s:
            k += 1
            j -= 1
        run.append(int(s * k))
    df["run_len"] = run
    return df


def attach_prices(fdf, px, horizons):
    dates = px["date"].to_numpy()
    rows = []
    for _, r in fdf.iterrows():
        i = int(np.searchsorted(dates, np.datetime64(pd.Timestamp(r["pub_ts"]).normalize())))
        if i >= len(px):
            continue
        b = px.iloc[i]
        rec = dict(r)
        rec.update({"px_base_date": b["date"], "spot0": b["spot"], "fut0": b["fut"], "basis0": b["basis"]})
        for h in horizons:
            j = i + h
            if j < len(px):
                e = px.iloc[j]
                rec["px_end_%d" % h] = e["date"]
                rec["fwd_spot_%d" % h] = e["spot"] / b["spot"] - 1
                rec["fwd_fut_%d" % h] = e["fut"] / b["fut"] - 1
                rec["fwd_basis_%d" % h] = e["basis"] - b["basis"]
            else:
                rec["px_end_%d" % h] = pd.NaT
                rec["fwd_spot_%d" % h] = np.nan
                rec["fwd_fut_%d" % h] = np.nan
                rec["fwd_basis_%d" % h] = np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def pooled_tests(panel, horizons, targets, factors):
    rows = []
    for h in horizons:
        for tcol, tlab, scale in targets:
            y = "%s_%d" % (tcol, h)
            for fcol, flab in factors:
                d = panel[[fcol, y]].dropna()
                if len(d) < 25:
                    continue
                rho, p = spearman(d[fcol], d[y])
                _, b, se, t, ph = hac_ols(d[y].to_numpy(float) * scale, d[fcol].to_numpy(float), lag=h)
                rows.append({"horizon_w": h, "target": tlab, "factor": flab, "factor_code": fcol,
                             "n_weeks": len(d), "spearman_rho": rho, "spearman_p": p,
                             "slope_per_unit": b, "hac_se": se, "hac_t": t, "hac_p": ph,
                             "eff_n": round(len(d) / h, 1)})
    df = pd.DataFrame(rows)
    df["q_bh"] = bh_fdr(df["spearman_p"])
    df["sig_raw"] = df["spearman_p"] < 0.05
    df["sig_bh"] = df["q_bh"] < 0.05
    return df


def groups(panel, horizons, targets, edges, wow_thr):
    out = {"level": [], "wow": [], "run": []}
    for h in horizons:
        for tcol, tlab, scale in targets:
            y = "%s_%d" % (tcol, h)
            # level
            d = panel[["lvl_pct", "week", y]].dropna().copy()
            if len(d) >= 30:
                d["g"] = np.select([d.lvl_pct < edges[0], d.lvl_pct < edges[1], d.lvl_pct < edges[2]],
                                   ["Q1 极低(<p%d)" % int(edges[0] * 100), "Q2 偏低", "Q3 偏高"],
                                   default="Q4 极高(>=p%d)" % int(edges[2] * 100))
                for g, sub in d.groupby("g"):
                    st = describe(sub[y] * scale, h)
                    vt = group_vs_rest(sub[y] * scale, d[d.g != g][y] * scale, h)
                    out["level"].append({"horizon_w": h, "target": tlab, "group": g, **st, **vt})
            # wow
            d = panel[["wow_chg", "week", y]].dropna().copy()
            if len(d) >= 30:
                t_ = wow_thr
                d["g"] = np.where(d.wow_chg <= -t_, "大幅去库(<=-%.0f)" % t_,
                                  np.where(d.wow_chg < 0, "小幅去库",
                                           np.where(d.wow_chg <= t_, "小幅累库", "大幅累库(>%.0f)" % t_)))
                for g, sub in d.groupby("g"):
                    st = describe(sub[y] * scale, h)
                    vt = group_vs_rest(sub[y] * scale, d[d.g != g][y] * scale, h)
                    out["wow"].append({"horizon_w": h, "target": tlab, "group": g, **st, **vt})
            # run
            d = panel[["run_len", "week", y]].dropna().copy()
            if len(d) >= 30:
                d["g"] = np.where(d.run_len <= -2, "连续≥2周去库",
                                  np.where(d.run_len >= 2, "连续≥2周累库", "其他"))
                for g, sub in d.groupby("g"):
                    st = describe(sub[y] * scale, h)
                    vt = group_vs_rest(sub[y] * scale, d[d.g != g][y] * scale, h)
                    out["run"].append({"horizon_w": h, "target": tlab, "group": g, **st, **vt})
    return {k: pd.DataFrame(v) for k, v in out.items()}


def yearly(panel, horizons, targets, edges):
    rows = []
    for h in horizons:
        for tcol, tlab, scale in targets:
            y = "%s_%d" % (tcol, h)
            d = panel[["lvl_pct", "wow_chg", "week", y]].dropna().copy()
            d["yr"] = d["week"].dt.year
            for yr, sub in d.groupby("yr"):
                hi = sub[sub.lvl_pct >= edges[2]]
                lo = sub[sub.lvl_pct < edges[0]]
                rl, _ = spearman(sub.lvl_pct, sub[y])
                rw, _ = spearman(sub.wow_chg, sub[y])
                rows.append({"year": int(yr), "horizon_w": h, "target": tlab, "n_weeks": len(sub),
                             "rho_level": rl, "mean_high": hi[y].mean() * scale if len(hi) else np.nan,
                             "n_high": len(hi), "mean_low": lo[y].mean() * scale if len(lo) else np.nan,
                             "n_low": len(lo),
                             "spread": (hi[y].mean() - lo[y].mean()) * scale if len(hi) and len(lo) else np.nan,
                             "rho_wow": rw})
    return pd.DataFrame(rows)


def placebo(panel, horizons, targets, runs=2000, seed=42):
    """Year-stratified circular-shift placebo for the run-length states."""
    rng = np.random.default_rng(seed)
    masks = {"连续≥2周去库": (panel["run_len"] <= -2).to_numpy(),
             "连续≥2周累库": (panel["run_len"] >= 2).to_numpy()}
    panel = panel.assign(yr=panel["week"].dt.year)
    groups_ix = panel.groupby("yr").indices
    rows = []
    for gname, m0 in masks.items():
        # only rows with a valid outcome are used per (group, target)
        for h in horizons:
            for tcol, tlab, scale in targets:
                y = "%s_%d" % (tcol, h)
                v = (panel[y] * scale).to_numpy(float)
                ok = ~np.isnan(v)
                if ok.sum() < 30:
                    continue
                idx_ok = np.where(ok)[0]
                sub_ix = {yr: np.array([i for i in ix if ok[i]]) for yr, ix in groups_ix.items()}
                sub_ix = {yr: ix for yr, ix in sub_ix.items() if len(ix) > 2}
                def stat(mm):
                    a = v[mm & ok]
                    b = v[~mm & ok]
                    if len(a) < 3 or len(b) < 3:
                        return np.nan
                    return a.mean() - b.mean()
                obs = stat(m0)
                if not np.isfinite(obs):
                    continue
                cnt = 0
                for _ in range(runs):
                    sh = np.zeros(len(panel), bool)
                    for yr, ix in sub_ix.items():
                        k = m0[ix]
                        sh[ix] = np.roll(k, rng.integers(1, len(ix)))
                    if abs(stat(sh)) >= abs(obs):
                        cnt += 1
                rows.append({"group": gname, "horizon_w": h, "target": tlab,
                             "diff": obs, "placebo_p": (cnt + 1) / (runs + 1),
                             "n_in": int((m0 & ok).sum())})
    return pd.DataFrame(rows)


def subsamples(panel, horizons, targets, is_end):
    rows = []
    p = panel.copy()
    for h in horizons:
        for tcol, tlab, scale in targets:
            y = "%s_%d" % (tcol, h)
            for tag, sub in [("重叠全长样本", p), ("非重叠子样本", p.iloc[::h]),
                             ("样本内", p[p.week <= pd.Timestamp(is_end)]),
                             ("样本外", p[p.week > pd.Timestamp(is_end)])]:
                d = sub[["lvl_pct", "wow_chg", y]].dropna()
                if len(d) < 15:
                    continue
                rl, pl = spearman(d.lvl_pct, d[y])
                rw, pw = spearman(d.wow_chg, d[y])
                rows.append({"horizon_w": h, "target": tlab, "sample": tag, "n": len(d),
                             "rho_level": rl, "p_level": pl, "rho_wow": rw, "p_wow": pw})
    return pd.DataFrame(rows)


def regime_split(panel, horizons, targets):
    rows = []
    p = panel.copy()
    p["regime"] = np.where(p["basis0"] > 0, "现货升水(basis>0)", "期货升水(basis<=0)")
    for h in horizons:
        for tcol, tlab, scale in targets:
            y = "%s_%d" % (tcol, h)
            for rg, sub in p.groupby("regime"):
                d = sub[["lvl_pct", "wow_chg", y]].dropna()
                if len(d) < 20:
                    continue
                rl, pl = spearman(d.lvl_pct, d[y])
                rw, pw = spearman(d.wow_chg, d[y])
                rows.append({"horizon_w": h, "target": tlab, "regime": rg, "n": len(d),
                             "rho_level": rl, "p_level": pl, "rho_wow": rw, "p_wow": pw})
    return pd.DataFrame(rows)


def control_reg(panel, horizons):
    p = panel.copy()
    p["basis_rate0"] = p["basis0"] / p["fut0"]
    rows = []
    for h in horizons:
        y = "fwd_spot_%d" % h
        d = p[["wow_pct", "basis_rate0", y]].dropna()
        if len(d) < 30:
            continue
        X = np.column_stack([np.ones(len(d)), d.wow_pct.to_numpy(float), d.basis_rate0.to_numpy(float)])
        b, se = hac_multi(d[y].to_numpy(float), X, h)
        rows.append({"h": h, "beta_wow_pct": b[1], "t_wow_pct": b[1] / se[1],
                     "beta_basis_rate": b[2], "t_basis_rate": b[2] / se[2], "n": len(d)})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    # resolve every relative path against the config file's own directory
    cfg_dir = os.path.dirname(os.path.abspath(a.config))
    for k in ("inventory_csv", "price_csv", "out_dir"):
        if k in cfg and cfg[k] and not os.path.isabs(cfg[k]):
            cfg[k] = os.path.normpath(os.path.join(cfg_dir, cfg[k]))
    out = cfg.get("out_dir", cfg_dir)
    os.makedirs(out, exist_ok=True)
    horizons = cfg.get("horizons", [1, 2, 4])
    targets = [(t[0], t[1], t[2]) for t in cfg.get("targets", [
        ["fwd_spot", "现货价格变化", 100.0],
        ["fwd_fut", "期货收益率", 100.0],
        ["fwd_basis", "基差变化", 1.0]])]
    factors = [(f[0], f[1]) for f in cfg.get("factors", [
        ["lvl_pct", "F1 库存水平（时点分位）"], ["total", "F2 库存绝对量"],
        ["wow_chg", "F3 周度变化"], ["wow_pct", "F4 周度变化率"],
        ["yoy", "F5 库存同比"], ["w4_chg", "F6 四周累计变化"]])]
    edges = cfg.get("level_edges", [0.2, 0.5, 0.8])
    wow_thr = cfg.get("wow_threshold", 3.0)

    inv, px = load_inputs(cfg)
    print("inventory weeks", len(inv), inv["week"].min().date(), "->", inv["week"].max().date())
    f = build_factors(inv, cfg.get("min_obs", 26))
    panel = attach_prices(f, px, horizons)
    panel.to_csv(os.path.join(out, "panel_weekly.csv"), index=False, encoding="utf-8-sig")
    print("panel", len(panel), "with 1W outcome", int(panel["fwd_spot_1"].notna().sum()))

    res = {"pooled": pooled_tests(panel, horizons, targets, factors)}
    g = groups(panel, horizons, targets, edges, wow_thr)
    res.update({"groups_" + k: v for k, v in g.items()})
    res["yearly"] = yearly(panel, horizons, targets, edges)
    res["placebo"] = placebo(panel, horizons, targets, runs=cfg.get("placebo_runs", 2000))
    res["subsample"] = subsamples(panel, horizons, targets, cfg.get("is_end", "2024-12-31"))
    res["regime"] = regime_split(panel, horizons, targets)
    res["control"] = control_reg(panel, horizons)
    for k, v in res.items():
        v.to_csv(os.path.join(out, "res_%s.csv" % k), index=False, encoding="utf-8-sig")
        print("%-14s %s" % (k, v.shape))

    summ = {
        "n_weeks": int(len(panel)),
        "start": panel["week"].min().strftime("%Y-%m-%d"),
        "end": panel["week"].max().strftime("%Y-%m-%d"),
        "n_tests": int(len(res["pooled"])),
        "n_sig_raw": int((res["pooled"]["spearman_p"] < 0.05).sum()),
        "n_sig_bh": int((res["pooled"]["q_bh"] < 0.05).sum()),
        "n_placebo_p01": int((res["placebo"]["placebo_p"] < 0.01).sum()),
        "n_placebo_tests": int(len(res["placebo"])),
    }
    json.dump(summ, open(os.path.join(out, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(summ)


if __name__ == "__main__":
    main()
