# -*- coding: utf-8 -*-
"""
ratiolib.py — 比价统计内核（纯标准库，无第三方依赖）
================================================================
设计原则
--------
1. 只做**可复核的算术**，不做判断。任何"这是不是均值回归"的判断都不在本文件。
2. 分位必须基于**真实有效样本**逐点排序计算，绝不用 max/min 反推。
3. 缺失一律留空，不插值、不前向填充、不外推。
4. 所有窗口统计都同时返回 N；N 不足时返回 None 而非硬算。

历史分位的两种口径（本文件都实现，报告里必须写明用的哪一种）
--------------------------------------------------------------
* calendar  日历回溯口径：当前值 vs [end - period, end] 内的样本。
            注意：当前值本身就在样本里，极值期分位天然偏高。
* prior     前序样本口径（推荐用于"极不极端"的判断）：剔除最近 prior_days 个
            样本后再算分位，避免"用自己给自己打分"。
"""

import math

# --------------------------------------------------------------------------
# 基础统计
# --------------------------------------------------------------------------


def mean(xs):
    v = [x for x in xs if x is not None]
    if not v:
        return None
    return sum(v) / len(v)


def median(xs):
    s = sorted(x for x in xs if x is not None)
    n = len(s)
    if n == 0:
        return None
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0


def stdev(xs, ddof=1):
    v = [x for x in xs if x is not None]
    n = len(v)
    if n <= ddof:
        return None
    mu = sum(v) / n
    return math.sqrt(sum((x - mu) ** 2 for x in v) / (n - ddof))


def quantile(xs, q):
    """线性插值分位数，与 Excel PERCENTILE.INC 一致。"""
    s = sorted(x for x in xs if x is not None)
    if not s:
        return None
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def percentile_rank(xs, value):
    """
    经验分布分位：样本中 <= value 的比例（并列各算一半）* 100。
    这是"当前值处在历史什么位置"的标准算法，
    与"用 max/min 线性插值反推"完全不同——后者会被单一极值点带偏。
    """
    s = [x for x in xs if x is not None]
    n = len(s)
    if n == 0 or value is None:
        return {"pct": None, "n": 0, "ties": 0, "below": 0}
    below = sum(1 for x in s if x < value)
    ties = sum(1 for x in s if x == value)
    return {"pct": (below + 0.5 * ties) / n * 100.0, "n": n, "ties": ties, "below": below}


def decile_position(value, xs):
    r = percentile_rank(xs, value)
    if r["pct"] is None:
        return None
    return min(10, max(1, int(r["pct"] // 10) + 1))


def excess_vs_median(value, xs):
    """相对中位数的偏离（百分比），比价研究中比绝对差更直观。"""
    m = median(xs)
    if m is None or m == 0 or value is None:
        return None
    return (value / m - 1) * 100


# --------------------------------------------------------------------------
# 相关与回归（辅助量）
# --------------------------------------------------------------------------


def pearson(xs, ys):
    p = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(p)
    if n < 3:
        return None
    mx = sum(a for a, _ in p) / n
    my = sum(b for _, b in p) / n
    sxy = sum((a - mx) * (b - my) for a, b in p)
    sxx = sum((a - mx) ** 2 for a, _ in p)
    syy = sum((b - my) ** 2 for _, b in p)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def rankdata(xs):
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[idx[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    p = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(p) < 3:
        return None
    return pearson(rankdata([a for a, _ in p]), rankdata([b for _, b in p]))


def ols(y, x):
    """OLS y = a + b x → slope/intercept/r2/n。用于"跟涨系数"。"""
    p = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    n = len(p)
    if n < 3:
        return None
    mx = sum(a for a, _ in p) / n
    my = sum(b for _, b in p) / n
    sxy = sum((a - mx) * (b - my) for a, b in p)
    sxx = sum((a - mx) ** 2 for a, _ in p)
    syy = sum((b - my) ** 2 for _, b in p)
    if sxx <= 0:
        return None
    slope = sxy / sxx
    return {"slope": slope, "intercept": my - slope * mx,
            "r2": (sxy ** 2) / (sxx * syy) if syy > 0 else None, "n": n}


# --------------------------------------------------------------------------
# 比价构造
# --------------------------------------------------------------------------


def build_ratio(series_a, series_b):
    """
    A/B 逐点对齐；任一侧缺失 → 比价为 None（不补数）。
    输入 [(date, value|None)]，返回 [(date, a, b, ratio|None, a_miss, b_miss)]
    """
    amap = dict(series_a)
    bmap = dict(series_b)
    out = []
    for d in sorted(set(amap) | set(bmap)):
        a, b = amap.get(d), bmap.get(d)
        ratio = None if (a is None or b is None or b == 0) else a / b
        out.append((d, a, b, ratio, a is None, b is None))
    return out


def invert_ratio(rows):
    """
    由 A/B 生成 B/A：1/r，并把 a/b 两列对调。
    这样前端切换方向时不需要重新取数，且两侧价格标注始终与比价方向一致。
    """
    out = []
    for d, a, b, r, am, bm in rows:
        out.append((d, b, a, None if r is None else 1.0 / r, bm, am))
    return out


def valid_pairs(rows):
    return [r for r in rows if r[3] is not None]


# --------------------------------------------------------------------------
# 窗口统计
# --------------------------------------------------------------------------


def _slice(rows, start_date=None, end_date=None, ratio_idx=3):
    return [r for r in rows
            if r[ratio_idx] is not None
            and (start_date is None or r[0] >= start_date)
            and (end_date is None or r[0] <= end_date)]


def window_stats(rows, start_date=None, end_date=None, ratio_idx=3):
    """[start, end] 内比价的完整描述统计 + 当前分位。"""
    sub = _slice(rows, start_date, end_date, ratio_idx)
    if not sub:
        return {"n": 0, "start": None, "end": None, "pct_rank": None}
    vals = [r[ratio_idx] for r in sub]
    hi = max(sub, key=lambda r: r[ratio_idx])
    lo = min(sub, key=lambda r: r[ratio_idx])
    return {
        "n": len(vals),
        "start": sub[0][0], "end": sub[-1][0],
        "current": vals[-1], "last_date": sub[-1][0],
        "mean": mean(vals), "median": median(vals), "std": stdev(vals),
        "max": hi[ratio_idx], "max_date": hi[0],
        "min": lo[ratio_idx], "min_date": lo[0],
        "q10": quantile(vals, .1), "q25": quantile(vals, .25),
        "q75": quantile(vals, .75), "q90": quantile(vals, .9),
        "pct_rank": percentile_rank(vals, vals[-1])["pct"],
        "decile": decile_position(vals[-1], vals),
        "excess_median_pct": excess_vs_median(vals[-1], vals),
    }


def prior_sample_stats(rows, prior_days=20, start_date=None, end_date=None, ratio_idx=3):
    """前序样本口径：剔除最近 prior_days 个有效样本后再评估当前值的分位。"""
    sub = _slice(rows, start_date, end_date, ratio_idx)
    if len(sub) <= prior_days + 10:
        return {"n": 0, "pct_rank": None, "prior_days_removed": prior_days}
    cur = sub[-1][ratio_idx]
    base = sub[: len(sub) - prior_days]
    st = window_stats(base, ratio_idx=ratio_idx)
    prior_vals = [r[ratio_idx] for r in base]
    st["current"] = cur
    st["pct_rank"] = percentile_rank(prior_vals, cur)["pct"]
    st["prior_days_removed"] = prior_days
    return st


def rolling_percentile(rows, window=252, prior_days=0, ratio_idx=3):
    """滚动分位：每点 = 当日比价在 [i-window-prior, i-prior) 样本中的分位。样本不足返回 None。"""
    vals = [(r[0], r[ratio_idx]) for r in rows if r[ratio_idx] is not None]
    out = []
    for i, (d, v) in enumerate(vals):
        hi_i = i - prior_days
        lo_i = hi_i - window
        if hi_i <= 0 or lo_i < 0:
            out.append((d, None))
            continue
        sample = [x[1] for x in vals[lo_i:hi_i]]
        out.append((d, percentile_rank(sample, v)["pct"] if len(sample) >= max(20, window // 2) else None))
    return out


def rolling_mean(rows, window=252, ratio_idx=3):
    vals = [(r[0], r[ratio_idx]) for r in rows if r[ratio_idx] is not None]
    out, acc = [], []
    for d, v in vals:
        acc.append(v)
        if len(acc) > window:
            acc.pop(0)
        out.append((d, mean(acc) if len(acc) >= max(20, window // 2) else None))
    return out


# --------------------------------------------------------------------------
# 贡献分解：比价变化来自哪一边
# --------------------------------------------------------------------------


def contribution(rows, start_date, end_date, a_idx=1, b_idx=2):
    """
    r = A/B → ln r = lnA − lnB → Δln r = ΔlnA − ΔlnB

    share_a / share_b 是**绝对贡献份额**（|ΔlnA| 与 |ΔlnB| 各自占比），
    回答"这个比价变化是谁主导的"；sign 说明方向：
      ΔlnA > 0 推高 A/B，ΔlnB > 0 压低 A/B。
    """
    sub = [r for r in rows if r[3] is not None and start_date <= r[0] <= end_date]
    if len(sub) < 2:
        return None
    a0, a1 = sub[0][a_idx], sub[-1][a_idx]
    b0, b1 = sub[0][b_idx], sub[-1][b_idx]
    if not (a0 and a1 and b0 and b1):
        return None
    dla, dlb = math.log(a1 / a0), math.log(b1 / b0)
    dlr = dla - dlb
    acc = abs(dla) + abs(dlb)
    return {
        "start": sub[0][0], "end": sub[-1][0], "n": len(sub),
        "a_start": a0, "a_end": a1, "a_chg_pct": (a1 / a0 - 1) * 100,
        "b_start": b0, "b_end": b1, "b_chg_pct": (b1 / b0 - 1) * 100,
        "ratio_start": sub[0][3], "ratio_end": sub[-1][3],
        "ratio_chg_pct": (sub[-1][3] / sub[0][3] - 1) * 100,
        "log_a": dla, "log_b": dlb, "log_ratio": dlr,
        "share_a": (abs(dla) / acc * 100) if acc else None,
        "share_b": (abs(dlb) / acc * 100) if acc else None,
        # 符号化：对 Δlnr 的实际推动量
        "push_a": dla, "push_b": -dlb,
        "dominant": ("A" if abs(dla) >= abs(dlb) else "B") if acc else None,
    }


def daily_contribution(rows, a_idx=1, b_idx=2):
    """
    逐日贡献：每个交易日比价变动中 A、B 各贡献多少（对数百分点）。
    用于验证"比价变动到底是不是某一边单边推动"。
    """
    out = []
    prev = None
    for r in rows:
        if r[3] is None:
            prev = None
            continue
        if prev is not None:
            if r[a_idx] and prev[a_idx] and r[b_idx] and prev[b_idx]:
                da = math.log(r[a_idx] / prev[a_idx])
                db = math.log(r[b_idx] / prev[b_idx])
                out.append((r[0], da * 100, -db * 100, (da - db) * 100))
        prev = r
    return out


# --------------------------------------------------------------------------
# 异常点识别
# --------------------------------------------------------------------------


def detect_outliers(rows, window=60, z_thresh=2.5, ratio_idx=3):
    """
    稳健 z 分数（基于滚动中位数与 MAD）：z = 0.6745*(x−median)/MAD
    比均值/标准差更抗极值，适合比价这种有厚尾的序列。
    """
    vals = [(r[0], r[ratio_idx]) for r in rows if r[ratio_idx] is not None]
    out = []
    for i, (d, v) in enumerate(vals):
        if i < window:
            out.append((d, v, None, False))
            continue
        sample = [x[1] for x in vals[i - window:i]]
        med = median(sample)
        mad = median([abs(x - med) for x in sample])
        if not mad:
            out.append((d, v, None, False))
            continue
        z = 0.6745 * (v - med) / mad
        out.append((d, v, z, abs(z) > z_thresh))
    return out


def max_drawdown(rows, ratio_idx=3):
    """比价从高点最大回落：(回撤%, 高点日, 低点日, 高点值, 低点值)。"""
    peak = peak_d = None
    worst = None
    for r in rows:
        v = r[ratio_idx]
        if v is None:
            continue
        if peak is None or v > peak:
            peak, peak_d = v, r[0]
        dd = (v / peak - 1) * 100
        if worst is None or dd < worst[0]:
            worst = (dd, peak_d, r[0], peak, v)
    return worst


def change_metrics(rows, ratio_idx=3, lookbacks=(1, 5, 20, 60, 120, 250)):
    """最近变化：N 个交易日前的比价与当前比较。"""
    vals = [(r[0], r[ratio_idx]) for r in rows if r[ratio_idx] is not None]
    if not vals:
        return {}
    cur_d, cur_v = vals[-1]
    out = {"current": cur_v, "current_date": cur_d}
    for lb in lookbacks:
        if len(vals) > lb:
            prev_d, prev_v = vals[-1 - lb]
            out["d%d" % lb] = (cur_v / prev_v - 1) * 100
            out["d%d_date" % lb] = prev_d
        else:
            out["d%d" % lb] = None
    return out


def fmt(v, nd=4):
    return "—" if v is None else (("%." + str(nd) + "f") % v)


def date_offset(d, days=0, months=0, years=0):
    """轻量日期偏移（只用于窗口边界，不处理交易日历）。"""
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    y += years
    m += months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    dim = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
           31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    dd = min(dd, dim)
    out = "%04d-%02d-%02d" % (y, m, dd)
    if days:
        import datetime as _dt
        out = (_dt.date(y, m, dd) + _dt.timedelta(days=days)).isoformat()
    return out
