# -*- coding: utf-8 -*-
"""
selftest.py — 用合成数据验证核心不变量
=====================================
不依赖任何外部数据；每个测试都对应 SKILL.md 里的一条硬规则。

    python scripts/selftest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analog_lib as AL  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OK, FAIL = "  PASS", "  FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print((OK if cond else FAIL) + f"  {name}" + (f"  [{detail}]" if detail else ""))


# --------------------------------------------------------------------------- #
def t_no_lookahead():
    """规则 R1：历史时点的标准化值不能因为未来数据加入而改变。"""
    idx = pd.date_range("2020-01-01", periods=300, freq="7D")
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(0, 1, 300).cumsum(), index=idx)
    full = AL.standardize(x, "rolling_z", lookback=52, min_obs=26)
    cut = 200
    part = AL.standardize(x.iloc[:cut], "rolling_z", lookback=52, min_obs=26)
    # 截断点之前的值必须完全一致
    same = np.allclose(full.iloc[:cut].dropna().values, part.dropna().values, atol=1e-12)
    check("无未来函数：截断后历史 z 值不变", same)
    # 且从截断点往后确实新增了值
    check("截断后仍有新值（说明测试有效）", full.notna().sum() > part.notna().sum())


def t_min_obs():
    """规则：样本不足不出值，不硬算。"""
    idx = pd.date_range("2020-01-01", periods=30, freq="7D")
    x = pd.Series(np.arange(30.0), index=idx)
    z = AL.standardize(x, "rolling_z", lookback=52, min_obs=26)
    check("min_obs 之前全部为 NaN", z.iloc[:25].isna().all())
    check("达到 min_obs 后开始出值", z.iloc[25:].notna().any())


def t_no_impute():
    """规则：缺失必须保持 NaN，不能被填成 0 或前值。"""
    idx = pd.date_range("2020-01-01", periods=120, freq="7D")
    x = pd.Series(np.sin(np.arange(120) / 5.0), index=idx)
    x.iloc[60:70] = np.nan
    z = AL.standardize(x, "rolling_z", lookback=52, min_obs=26)
    check("原始缺失处标准化后仍为 NaN", z.iloc[60:70].isna().all())
    check("缺失两侧有值", z.iloc[59] == z.iloc[59] and z.iloc[70] == z.iloc[70])


def t_clip():
    idx = pd.date_range("2020-01-01", periods=200, freq="7D")
    x = pd.Series(np.r_[np.zeros(100), np.zeros(99), 1e6], index=idx)
    z = AL.standardize(x, "rolling_z", lookback=52, min_obs=26, clip=3.0)
    check("极端值被截断在 ±3", abs(z.iloc[-1]) <= 3.0 + 1e-9, f"z={z.iloc[-1]:.3f}")


def _fake_panel(n=400, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-03", periods=n, freq="7D")
    a = pd.Series(rng.normal(0, 1, n).cumsum(), index=idx)
    b = pd.Series(rng.normal(0, 1, n).cumsum(), index=idx)
    df = pd.DataFrame({"a": a, "b": b}, index=idx)
    return df


def t_dedup():
    """规则：相邻日期不能占满名次。"""
    df = _fake_panel()
    asof = df.index[-1]
    p = AL.SearchParams(asof=asof.date().isoformat(),
                        history_start=df.index[0].date().isoformat(),
                        window_weeks=1, top_n=5, min_gap_weeks=8,
                        method="mae", weights={"a": 1.0, "b": 1.0},
                        lag_at_least_days=21)
    res = AL.search_analogs(df, df, p)
    sel = res["selected"]
    dates = sorted(sel["date"].tolist())
    gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    ok = all(g >= 8 * 7 for g in gaps) if gaps else True
    check("去重：命中窗口两两间隔 ≥ min_gap", ok, f"gaps={gaps}")

    # 未去重时确实存在更近的候选
    cands = res["candidates"]["date"].tolist()
    near = sum(1 for d in cands[:5]
               if min(abs((d - s).days) for s in dates) < 8 * 7)
    check("去重前确实有相邻候选（说明去重真的在起作用）", near > 0, f"near={near}")


def t_lag():
    """规则：历史窗口必须早于当前观察日 ≥ lag_days。"""
    df = _fake_panel()
    asof = df.index[-1]
    p = AL.SearchParams(asof=asof.date().isoformat(),
                        history_start=df.index[0].date().isoformat(),
                        window_weeks=1, top_n=5, min_gap_weeks=4,
                        method="mae", weights={"a": 1.0, "b": 1.0},
                        lag_at_least_days=60)
    res = AL.search_analogs(df, df, p)
    dmin = min((asof - d).days for d in res["selected"]["date"]) if len(res["selected"]) else 999
    check("硬间隔：所有历史窗口早于观察日 ≥ lag_days", dmin >= 60, f"min_gap_days={dmin}")


def t_coverage_gate():
    """规则：历史时点覆盖率不足必须被剔除（严格模式）。"""
    df = _fake_panel()
    df["c"] = np.nan
    df.loc[df.index[-30:], "c"] = np.arange(30.0)   # 只有最近 30 期有值
    asof = df.index[-1]
    w = {"a": 1.0, "b": 1.0, "c": 3.0}             # c 权重很高
    p_strict = AL.SearchParams(asof=asof.date().isoformat(),
                               history_start=df.index[0].date().isoformat(),
                               window_weeks=1, top_n=5, min_gap_weeks=4,
                               method="mae", weights=dict(w),
                               hist_z_required=True, min_hist_z_cover=0.9,
                               min_sign_match=0.0, lag_at_least_days=7)
    res_s = AL.search_analogs(df, df, p_strict)
    covers = res_s["candidates"]["hist_z_cover"].tolist() if len(res_s["candidates"]) else []
    check("严格模式：所有候选覆盖率 ≥ 0.9", all(c >= 0.9 - 1e-9 for c in covers),
          f"n={len(covers)}, min={min(covers) if covers else 'na'}")

    p_loose = AL.SearchParams(asof=asof.date().isoformat(),
                              history_start=df.index[0].date().isoformat(),
                              window_weeks=1, top_n=5, min_gap_weeks=4,
                              method="mae", weights=dict(w),
                              hist_z_required=False, min_sign_match=0.0,
                              lag_at_least_days=7)
    res_l = AL.search_analogs(df, df, p_loose)
    check("放宽模式候选数 ≥ 严格模式（确实放宽了）",
          res_l["n_candidates"] >= res_s["n_candidates"],
          f"loose={res_l['n_candidates']} strict={res_s['n_candidates']}")


def t_sign_match():
    """规则：同向指标占比过低应被剔除。"""
    df = _fake_panel()
    asof = df.index[-1]
    p = AL.SearchParams(asof=asof.date().isoformat(),
                        history_start=df.index[0].date().isoformat(),
                        window_weeks=1, top_n=5, min_gap_weeks=4,
                        method="mae", weights={"a": 1.0, "b": 1.0},
                        min_sign_match=1.0, lag_at_least_days=7)
    res = AL.search_analogs(df, df, p)
    sm = res["candidates"]["sign_match"].tolist() if len(res["candidates"]) else []
    check("同向门槛生效：所有候选 sign_match ≥ 1.0",
          all(x >= 1.0 - 1e-9 for x in sm), f"n={len(sm)}")


def t_similarity_bounds():
    """相似度必须落在 [0,1]，且完全一致时为 1。"""
    z = np.array([0.5, -1.0, 2.0, 0.0])
    w = np.array([1.0, 1.0, 1.0, 1.0])
    for m in ["mae", "rmse", "cosine"]:
        d, sim, we = AL.weighted_distance(z, z, w, m)
        check(f"{m}: 与自身相似度为 1", abs(sim - 1.0) < 1e-9, f"sim={sim:.6f}")
        d2, sim2, _ = AL.weighted_distance(np.array([3.0, -3.0, 3.0, -3.0]),
                                           np.array([-3.0, 3.0, -3.0, 3.0]), w, m)
        check(f"{m}: 完全相反时相似度 ∈ [0,1]", 0 <= sim2 <= 1, f"sim={sim2:.4f}")


def t_missing_renorm():
    """一端缺失时按有效权重重新归一，不能算成 0 偏离。"""
    a = np.array([1.0, np.nan, 1.0])
    b = np.array([1.0, 5.0, 1.0])
    w = np.array([1.0, 1.0, 1.0])
    d, sim, we = AL.weighted_distance(a, b, w, "mae")
    check("缺失项被跳过而非算作偏离", abs(sim - 1.0) < 1e-9, f"sim={sim:.6f}, we={we}")
    check("有效权重只统计两端都有值的项", abs(we - 2.0) < 1e-9, f"we={we}")


def t_forward():
    """后续表现：取观察日之后 1/3 个日历月的最近交易日。"""
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    raw = pd.DataFrame({"p": np.arange(400.0)}, index=idx)
    r = AL.forward_performance(idx, raw, pd.Timestamp("2020-03-01"),
                               ["p"], (1, 3), window_days=5)
    f1 = r.get("1m") or {}
    check("1M 有结果", bool(f1), str(f1.get("end")))
    if f1:
        check("1M 结束日约为起始日 +1 个月",
              abs((pd.Timestamp(f1["end"]) - pd.Timestamp(f1["start"])).days - 30) <= 3,
              f"{f1['start']} → {f1['end']}")
        check("价格变化为正（构造的单调序列）", f1.get("p_pct", 0) > 0,
              f"pct={f1.get('p_pct')}")
    # 观察日太靠近样本末端 → 3M 应为空
    r2 = AL.forward_performance(idx, raw, pd.Timestamp(idx[-5]), ["p"], (1, 3), window_days=5)
    check("样本末端附近不出 3M（不硬算）", r2.get("3m") is None)


def t_regime_cluster():
    """同一段行情的多个窗口应聚成同一轮。"""
    sel = pd.DataFrame({"date": pd.to_datetime([
        "2020-01-08", "2020-03-04", "2020-04-01",   # 相近
        "2021-06-02"])})                             # 隔很久
    ids = AL._regime_cluster(sel, gap_days=8 * 7)
    check("行情轮次：相近窗口归为同一轮", ids[0] == ids[1] == ids[2], str(ids))
    check("行情轮次：远期窗口单独成轮", ids[3] != ids[0], str(ids))


def main():
    print("=" * 60)
    print("historical-analog-search · 自测")
    print("=" * 60)
    for fn in [t_no_lookahead, t_min_obs, t_no_impute, t_clip, t_dedup, t_lag,
               t_coverage_gate, t_sign_match, t_similarity_bounds,
               t_missing_renorm, t_forward, t_regime_cluster]:
        print(f"\n[{fn.__name__}] {fn.__doc__.strip() if fn.__doc__ else ''}")
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            check(f"{fn.__name__} 抛出异常", False, str(e))

    n = len(results)
    bad = [r for r in results if not r[1]]
    print("\n" + "=" * 60)
    print(f"共 {n} 项检查，通过 {n - len(bad)}，失败 {len(bad)}")
    if bad:
        for name, _, detail in bad:
            print(f"  FAIL: {name} {detail}")
        sys.exit(1)
    print("全部通过。")


if __name__ == "__main__":
    main()
