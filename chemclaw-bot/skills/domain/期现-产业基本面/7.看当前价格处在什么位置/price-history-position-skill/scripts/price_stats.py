# -*- coding: utf-8 -*-
"""历史价格位置统计核心（品种无关）。

设计原则（与 SKILL.md 的三条硬规矩一一对应）：

1. **分位必须是经验分位（empirical percentile）**，即「历史上有多少比例的观测日价格 <= 当前价」，
   用真实有效观测计数得出。**禁止**用 (当前价-最低)/(最高-最低) 冒充分位——那是区间位置，
   不是统计分位。本模块显式提供两种口径并分别命名，绝不混用：
     - percentile_rank_weak   = COUNTIF(<= x) / N          （含自身，小数位取中）
     - percentile_rank_strict = (COUNTIF(< x) + 0.5*COUNTIF(= x)) / N   （并列取半）
     - range_position         = (x - min) / (max - min)    （仅作区间位置，单独命名）
     对并列值极多的品种（现货逐日报价常见），三者差异很大，报告必须同时给出并说明。
2. **不做插值、不做外推、不补模拟价。** 缺的日期就是缺，进入 gaps。
3. **窗口按自然日历定义**（1y=365 天、3y=1095 天、5y=1826 天），
   并要求窗口内有效观测数达到最小样本门槛，否则该窗口标记为不可用于分位。
"""
import math
import datetime

MIN_OBS = 20          # 一个窗口至少要这么多有效观测才允许算分位
STALE_DAYS = 7        # 序列末日距基准日超过这么多天，视为「数据陈旧」


# ------------------------------------------------------------------ 基础
def parse_date(s):
    if isinstance(s, datetime.date):
        return s
    return datetime.date.fromisoformat(str(s)[:10])


def clean_series(rows, value_key="value", date_key="date", drop_nonpositive=True):
    """规整为 [(date, value)]，按日期升序；同日期重复取最后一条并记录冲突。"""
    seen = {}
    conflicts = []
    dropped = []
    for r in rows:
        try:
            d = parse_date(r[date_key])
            v = float(r[value_key])
        except (KeyError, TypeError, ValueError):
            dropped.append(r)
            continue
        if drop_nonpositive and (not math.isfinite(v) or v <= 0):
            dropped.append(r)
            continue
        if d in seen and abs(seen[d] - v) > 1e-9:
            conflicts.append({"date": d.isoformat(), "kept_last": v, "previous": seen[d]})
        seen[d] = v
    out = sorted(seen.items())
    return out, conflicts, dropped


def window_slice(series, asof, days):
    """自然日历窗口：(asof - days, asof]。"""
    lo = asof - datetime.timedelta(days=days)
    return [(d, v) for d, v in series if lo < d <= asof]


def available_span(series):
    if not series:
        return None
    return series[0][0], series[-1][0]


# ------------------------------------------------------------------ 分位
def empirical_percentile(values, x):
    """返回三种口径 + 计数明细。全部基于真实观测，不做任何插值。"""
    n = len(values)
    if n == 0:
        return None
    below = sum(1 for v in values if v < x)
    equal = sum(1 for v in values if v == x)
    above = sum(1 for v in values if v > x)
    pct_weak = (below + equal) / n * 100.0
    pct_strict = (below + 0.5 * equal) / n * 100.0
    return {
        "n": n,
        "below": below, "equal": equal, "above": above,
        "percentile_inclusive_pct": round(pct_weak, 2),
        "percentile_midrank_pct": round(pct_strict, 2),
        "pct_above": round(above / n * 100.0, 2),
    }


def ranged_position(values, x):
    """区间位置（非统计分位），单独命名以免被误用为分位。"""
    if not values:
        return None
    lo, hi = min(values), max(values)
    if hi <= lo:
        return None
    return round((x - lo) / (hi - lo) * 100.0, 2)


def quantile(values, q):
    """线性插值分位数（用于画分位带，非用于分位判定）。q in [0,1]."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


# ------------------------------------------------------------------ 描述统计
def describe(values):
    n = len(values)
    if n == 0:
        return None
    s = sorted(values)
    mean = sum(s) / n
    if n % 2:
        median = s[n // 2]
    else:
        median = (s[n // 2 - 1] + s[n // 2]) / 2.0
    var = sum((v - mean) ** 2 for v in s) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    return {
        "n": n,
        "min": round(s[0], 2), "max": round(s[-1], 2),
        "mean": round(mean, 2), "median": round(median, 2),
        "p10": round(quantile(s, 0.10), 2),
        "p25": round(quantile(s, 0.25), 2),
        "p75": round(quantile(s, 0.75), 2),
        "p90": round(quantile(s, 0.90), 2),
        "stdev": round(sd, 2),
        "cv_pct": round(sd / mean * 100.0, 2) if mean else None,
        "iqr": round(quantile(s, 0.75) - quantile(s, 0.25), 2),
    }


# ------------------------------------------------------------------ 变动与波动
def change_metrics(series, asof, days):
    """区间变动：需要窗口起点附近真实存在观测，找不到就返回 None（不插值）。"""
    w = window_slice(series, asof, days)
    if len(w) < 2:
        return None
    d0, v0 = w[0]
    d1, v1 = w[-1]
    return {
        "from": d0.isoformat(), "to": d1.isoformat(),
        "from_value": round(v0, 2), "to_value": round(v1, 2),
        "abs_change": round(v1 - v0, 2),
        "pct_change": round((v1 - v0) / v0 * 100.0, 2) if v0 else None,
        "obs": len(w),
    }


def daily_returns(series):
    out = []
    for (d0, v0), (d1, v1) in zip(series, series[1:]):
        if v0:
            out.append((d1, (v1 - v0) / v0 * 100.0, (d1 - d0).days))
    return out


def volatility_metrics(series, asof, days=365):
    """年化波动率：按真实自然日间隔折算，不假设等距。

    现货是"报价日"序列，间隔不均匀（周末节假日不报价），
    因此用「每自然日对数收益」的标准差 × sqrt(365) 年化。
    """
    w = window_slice(series, asof, days)
    if len(w) < 5:
        return None
    per_day = []
    for (d0, v0), (d1, v1) in zip(w, w[1:]):
        gap = (d1 - d0).days
        if gap <= 0 or v0 <= 0 or v1 <= 0:
            continue
        per_day.append(math.log(v1 / v0) / gap)
    if len(per_day) < 4:
        return None
    mu = sum(per_day) / len(per_day)
    var = sum((x - mu) ** 2 for x in per_day) / (len(per_day) - 1)
    sd_daily = math.sqrt(var)
    abs_ret = [abs(r) for _, r, _ in daily_returns(w)]
    big = [r for _, r, _ in daily_returns(w) if abs(r) >= 1.0]
    return {
        "window_days": days, "n": len(per_day),
        "ann_vol_pct": round(sd_daily * math.sqrt(365) * 100.0, 2),
        "mean_abs_daily_pct": round(sum(abs_ret) / len(abs_ret), 3) if abs_ret else None,
        "max_abs_daily_pct": round(max(abs_ret), 2) if abs_ret else None,
        "days_ge_1pct": len(big),
        "pct_days_ge_1pct": round(len(big) / len(abs_ret) * 100.0, 2) if abs_ret else None,
    }


def max_drawdown(series):
    peak = None
    best = 0.0
    when = None
    peak_date = None
    for d, v in series:
        if peak is None or v > peak:
            peak, peak_date = v, d
        if peak:
            dd = (v - peak) / peak * 100.0
            if dd < best:
                best, when = dd, (peak_date, d, v)
    if when is None:
        return None
    return {"mdd_pct": round(best, 2),
            "peak_date": when[0].isoformat(), "trough_date": when[1].isoformat(),
            "trough_value": round(when[2], 2)}


# ------------------------------------------------------------------ 季节性
def seasonality(series, min_year_obs=30):
    """按月聚合「同年同月」的均价与观测数——用于同期对比与季节性。

    只用真实观测；某年某月没有观测就不出现这个格子（不是 0）。
    """
    buckets = {}
    for d, v in series:
        buckets.setdefault((d.year, d.month), []).append(v)
    rows = []
    for (y, m), vals in sorted(buckets.items()):
        rows.append({
            "year": y, "month": m, "n": len(vals),
            "mean": round(sum(vals) / len(vals), 2),
            "min": round(min(vals), 2), "max": round(max(vals), 2),
            "first_date": None, "last_date": None,
        })
    # 同月跨年对比矩阵
    months = sorted({m for _, m in buckets})
    matrix = {}
    for m in months:
        matrix[m] = {y: b["mean"] for (y, mm), b in
                     [((y2, m2), {"mean": round(sum(v2) / len(v2), 2)})
                      for (y2, m2), v2 in buckets.items()] if mm == m}
    season_index = {}
    all_months = [b["mean"] for b in rows if b["n"] >= 15]
    overall = sum(all_months) / len(all_months) if all_months else None
    for m in months:
        vals = [b["mean"] for b in rows if b["month"] == m]
        if vals and overall:
            season_index[m] = round(sum(vals) / len(vals) / overall * 100.0, 2)
    return {"monthly": rows, "matrix": matrix, "season_index": season_index,
            "overall_month_mean": round(overall, 2) if overall else None}


# ------------------------------------------------------------------ 异常
def detect_anomalies(series, z_thresh=2.5, iqr_k=1.5, pct_thresh=3.0, baseline_days=365):
    """异常识别，三条独立判据，分别标注，不合并成一句"异常"。

    A. 水平异常：该点价格相对「滚动一年」中位数偏离超过 z_thresh 倍 MAD 稳健 z 分数
    B. 跳变异常：单日（相邻报价日）涨跌幅绝对值 >= pct_thresh%
    C. 分布异常：落在滚动窗口 Q1 - iqr_k*IQR 或 Q3 + iqr_k*IQR 之外
    """
    out = []
    for i, (d, v) in enumerate(series):
        lo = d - datetime.timedelta(days=baseline_days)
        base = [x for dd, x in series if lo < dd <= d]
        flags = []
        if len(base) >= MIN_OBS:
            med = quantile(base, 0.5)
            mad = quantile([abs(x - med) for x in base], 0.5)
            if mad > 0:
                rz = 0.6745 * (v - med) / mad
                if abs(rz) >= z_thresh:
                    flags.append({"rule": "level_mad", "score": round(rz, 2)})
            q1, q3 = quantile(base, 0.25), quantile(base, 0.75)
            iqr = q3 - q1
            if iqr > 0 and (v < q1 - iqr_k * iqr or v > q3 + iqr_k * iqr):
                flags.append({"rule": "iqr_fence"})
        if i:
            d0, v0 = series[i - 1]
            if v0:
                ch = (v - v0) / v0 * 100.0
                if abs(ch) >= pct_thresh:
                    flags.append({"rule": "jump", "pct": round(ch, 2),
                                  "from_date": d0.isoformat(), "from_value": round(v0, 2)})
        if flags:
            out.append({"date": d.isoformat(), "value": round(v, 2), "flags": flags})
    return out


# ------------------------------------------------------------------ 缺口
def find_gaps(series, asof, start=None, max_report=200):
    """找出「序列应有的交易日却没有任何报价」的空洞。

    现货报价通常只在工作日出现，因此这里以工作日为期望集合，
    连续缺失 >= 3 个工作日的段落才记为缺口（单日缺失多为节假日，单列计数）。
    """
    if not series:
        return {"runs": [], "single_missing": 0}
    start = start or series[0][0]
    have = {d for d, _ in series}
    runs = []
    cur = None
    singles = 0
    d = start
    while d <= asof:
        if d.weekday() < 5 and d not in have:
            if cur is None:
                cur = [d, d, 0]
            cur[1] = d
            cur[2] += 1
        else:
            if cur:
                (singles := singles + 1) if cur[2] == 1 else runs.append(
                    {"from": cur[0].isoformat(), "to": cur[1].isoformat(), "workdays": cur[2]})
                cur = None
        d += datetime.timedelta(days=1)
    if cur:
        if cur[2] == 1:
            singles += 1
        else:
            runs.append({"from": cur[0].isoformat(), "to": cur[1].isoformat(), "workdays": cur[2]})
    return {"runs": runs[:max_report], "single_missing": singles, "run_count": len(runs)}
