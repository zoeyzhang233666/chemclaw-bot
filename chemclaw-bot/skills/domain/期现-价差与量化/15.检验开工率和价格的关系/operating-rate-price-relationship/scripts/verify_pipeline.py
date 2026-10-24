# -*- coding: utf-8 -*-
"""Verification of the pipeline's core statistics on synthetic data with a KNOWN truth.

Three checks (all must pass):
  T1  a true negative relation (lower rate -> HIGHER forward return) is recovered
  T2  a pure-noise factor produces (almost) no significant IC after BH-FDR
  T3  the forward window is measured AFTER the publish timestamp (alignment)
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pipeline as P  # noqa: E402


def synth(n_weeks=520, beta=-0.015, noise=0.02, seed=1):
    rng = np.random.default_rng(seed)
    sessions = pd.date_range("2019-01-02", periods=n_weeks * 5 + 40, freq="B")
    week_end = sessions[[i * 5 + 4 for i in range(n_weeks)]]
    util = 70 + 5 * np.sin(np.arange(n_weeks) / 26.0) + rng.normal(0.0, 1.5, n_weeks)
    u = pd.DataFrame({"stat_week_end": week_end, "pub_ts": week_end + pd.Timedelta(days=1),
                      "util_total": util})
    # the factor that drives returns is the *published* level, mapped on the calendar
    level = pd.Series(u.set_index("pub_ts")["util_total"]).reindex(sessions, method="ffill")
    z = (level - level.mean()) / level.std()
    ret = rng.normal(0.0, noise, len(sessions))
    # inject the truth: return at t+5 depends on the rate PUBLISHED at t. Vectorised on
    # purpose - in-place scalar += on a numpy buffer is not stable across numpy versions.
    z0 = z.to_numpy(float)
    z0 = np.where(np.isfinite(z0), z0, 0.0)
    ret = ret + np.concatenate([np.zeros(5), beta * z0[:-5]])
    assert not np.isnan(ret).any(), "synthetic returns must be finite"
    close = 5000 * np.exp(np.cumsum(ret))
    px = pd.DataFrame({"date": sessions, "close": close, "adj_close": close})
    return u, px


def run_case(u, px, tag):
    u.to_csv("_vt_u.csv", index=False)
    px.to_csv("_vt_p.csv", index=False)
    cfg = {"util_csv": "_vt_u.csv", "value_col": "util_total", "price_csv": "_vt_p.csv",
           "out_dir": os.path.join(HERE, "_vt_out"),
           "horizons_sessions": {"1w": 5, "4w": 20}, "level_bands": [65, 70, 75],
           "factors": [["util", "F1 水平"], ["chg_pp", "F2 变化"], ["level_pct", "F3 分位"]],
           "min_history_periods": 52, "placebo_runs": 200, "min_n_eff": 30, "seed": 42}
    res = P.run(cfg, quiet=True)
    for f in ("_vt_u.csv", "_vt_p.csv"):
        if os.path.exists(f):
            os.remove(f)
    return res


def main():
    ok = True

    # T1: true negative relation
    u, px = synth(beta=-0.015)
    res = run_case(u, px, "T1")
    d = res["panel"][["util", "fwd_ret_1w"]].dropna()
    ic1 = float(res["pooled"].set_index(["factor", "horizon"]).loc[("F1 水平", "1w"), "ic"])
    beta, se, t, p = P.hac_ols(d["fwd_ret_1w"] * 100, (d["util"] - d["util"].mean()) / d["util"].std(), 4)
    t1 = (ic1 < -0.15) and (p < 0.01) and (beta < -0.5)
    print("T1 recover true negative relation: IC=%+.3f beta=%.3f%%/sd HAC p=%.4g -> %s"
          % (ic1, beta, p, "PASS" if t1 else "FAIL"))
    ok &= t1

    # T2: pure noise factor must not survive BH
    rng = np.random.default_rng(7)
    u2, px2 = synth(beta=0.0, seed=11)
    u2["util_total"] = 70 + rng.normal(0.0, 2.0, len(u2))
    res2 = run_case(u2, px2, "T2")
    n_sig = int(res2["pooled"]["sig_bh_5pct"].sum())
    t2 = n_sig == 0
    print("T2 no false discovery on noise factor: BH-significant=%d/%d -> %s"
          % (n_sig, len(res2["pooled"]), "PASS" if t2 else "FAIL"))
    ok &= t2

    # T3: alignment -- origin strictly after publication, forward window length respected
    pan = res["panel"]
    dts = pd.to_datetime(pan["origin_date"])
    good = bool(((dts.dt.normalize() > pd.to_datetime(pan["pub_ts"]).dt.normalize()).all()))
    lens = (pd.to_datetime(pan["end_date_1w"]) - dts).dt.days
    t3 = good and bool(lens.dropna().between(5, 12).all())
    print("T3 origin after publication (all=%s), 5-session window spans %s calendar days -> %s"
          % (good, ("%d..%d" % (lens.min(), lens.max())) if lens.notna().any() else "n/a",
             "PASS" if t3 else "FAIL"))
    ok &= t3

    print("VERIFY", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
