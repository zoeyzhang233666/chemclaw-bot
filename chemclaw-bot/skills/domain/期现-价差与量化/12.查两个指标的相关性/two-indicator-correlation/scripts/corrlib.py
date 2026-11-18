# -*- coding: utf-8 -*-
"""
两指标相关性分析核心库（无第三方依赖，仅标准库；Excel/HTML 生成脚本与 CLI 共用）

设计要点
  1. 一切统计量都在“有效样本”上计算，N 不足时返回 None 而不是给出数字；
  2. Pearson / Spearman / 去趋势 / 一阶差分 / HAC(Newey-West) 标准差 / Fisher-z 置信区间 / t 检验 p 值全部自带实现；
  3. 滚动相关需要“最小有效样本数”门槛，窗口内有效配对不足即返回 None（不插值、不补数）；
  4. 提供伪相关诊断：趋势、自相关（有效样本量修正）、共同外部因素偏相关、滞后相关。
"""
from __future__ import annotations

import math
from statistics import NormalDist

ND = NormalDist()


# ------------------------------------------------------------------ 基础统计
def mean(xs):
    return sum(xs) / len(xs)


def variance(xs, ddof=1):
    n = len(xs)
    if n <= ddof:
        return None
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def sd(xs, ddof=1):
    v = variance(xs, ddof)
    return None if v is None else math.sqrt(v)


def pearson(x, y):
    """配对样本 Pearson r。要求 len(x)==len(y)>=3，且两端方差非零。"""
    n = len(x)
    if n < 3 or n != len(y):
        return None
    mx, my = mean(x), mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 1e-12 or syy <= 1e-12:
        return None
    return sxy / math.sqrt(sxx * syy)


def rank(xs):
    """平均秩（处理并列）。"""
    n = len(xs)
    order = sorted(range(n), key=lambda i: xs[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 3 or len(x) != len(y):
        return None
    return pearson(rank(x), rank(y))


def t_pvalue(t, df):
    """双侧 p 值：数值积分 t 分布（Student）。"""
    if df <= 0 or t is None:
        return None
    t = abs(t)
    # 用正则化不完全 Beta 的连分式实现
    x = df / (df + t * t)
    return _betainc(df / 2.0, 0.5, x)


def _betainc(a, b, x):
    """正则化不完全 Beta 函数 I_x(a,b)。"""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x)
    return 1 - math.exp(math.log(1 - x) * b + math.log(x) * a - lbeta) / b * _betacf(b, a, 1 - x)


def _betacf(a, b, x, itmax=300, eps=1e-12):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def corr_stats(x, y, hac_lags=0):
    """相关性的完整统计量：r、t、p、N、Fisher-z 95% CI；hac_lags>0 时给出 Newey-West 标准误。"""
    n = len(x)
    r = pearson(x, y)
    if r is None:
        return {'r': None, 'n': n}
    out = {'r': r, 'n': n, 'r2': r * r}
    if n > 2 and abs(r) < 1:
        t = r * math.sqrt((n - 2) / (1 - r * r))
        out['t'] = t
        out['p'] = t_pvalue(t, n - 2)
    elif abs(r) >= 1:
        out['t'] = float('inf')
        out['p'] = 0.0
    # Fisher z 95% CI
    z = math.atanh(max(min(r, 0.999999), -0.999999))
    se = 1.0 / math.sqrt(n - 3) if n > 3 else None
    if se:
        out['ci_lo'] = math.tanh(z - 1.959964 * se)
        out['ci_hi'] = math.tanh(z + 1.959964 * se)
    # HAC (Newey-West) 标准误
    if hac_lags and hac_lags > 0 and n > 4:
        out['hac_se'] = hac_se_corr(x, y, hac_lags)
        if out['hac_se']:
            out['hac_t'] = r / out['hac_se']
            out['hac_p'] = 2 * (1 - ND.cdf(abs(out['hac_t'])))
    return out


def hac_se_corr(x, y, lags):
    """相关性的 Newey-West HAC 标准误（对标准化序列的乘积做长期方差）。"""
    n = len(x)
    if n < lags + 3:
        return None
    mx, my = mean(x), mean(y)
    sx, sy = sd(x), sd(y)
    if not sx or not sy:
        return None
    ux = [(a - mx) / sx for a in x]
    uy = [(b - my) / sy for b in y]
    g = [ux[i] * uy[i] for i in range(n)]
    mg = mean(g)
    s = sum((v - mg) ** 2 for v in g) / n
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1.0)
        c = sum((g[i] - mg) * (g[i - L] - mg) for i in range(L, n)) / n
        s += 2 * w * c
    if s <= 0:
        return None
    return math.sqrt(s / n)


def linreg(x, y):
    """OLS: y = a + b x，返回 a、b、R²、残差。"""
    n = len(x)
    if n < 3:
        return None
    mx, my = mean(x), mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    if sxx <= 1e-12:
        return None
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    a = my - b * mx
    resid = [c - (a + b * xi) for xi, c in zip(x, y)]
    ss_res = sum(e * e for e in resid)
    ss_tot = sum((c - my) ** 2 for c in y)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None
    return {'intercept': a, 'slope': b, 'r2': r2, 'resid': resid}


def detrend(t, y):
    """去掉时间趋势（线性），返回残差。用于识别“共同趋势造成的伪相关”。"""
    fit = linreg(t, y)
    return None if fit is None else fit['resid']


def partial_corr(x, y, z):
    """控制共同因素 z 后的偏相关。"""
    if len(z) != len(x) or len(z) < 4:
        return None
    rx, ry = detrend(z, x), detrend(z, y)
    if not rx or not ry:
        return None
    return pearson(rx, ry)


def diff(xs):
    return [xs[i] - xs[i - 1] for i in range(1, len(xs))]


def pct_change(xs):
    out = []
    for i in range(1, len(xs)):
        if xs[i - 1] in (0, None):
            out.append(None)
        else:
            out.append((xs[i] - xs[i - 1]) / xs[i - 1] * 100.0)
    return out


def lag_corr(x, y, lag):
    """lag>0：x 领先 y（用 x[t] 对 y[t+lag]）。"""
    if lag == 0:
        return pearson(x, y)
    if lag > 0:
        a, b = x[:-lag], y[lag:]
    else:
        a, b = x[-lag:], y[:lag]
    return pearson(a, b)


# ------------------------------------------------------------------ 自相关与有效样本量
def autocorr(x, lag=1):
    n = len(x)
    if n <= lag + 2:
        return None
    m = mean(x)
    v = sum((a - m) ** 2 for a in x)
    if v <= 0:
        return None
    return sum((x[i] - m) * (x[i - lag] - m) for i in range(lag, n)) / v


def effective_n(x, y, max_lag=3):
    """考虑自相关后的有效样本量（Quenouille 近似）：n_eff = n (1-r1x r1y)/(1+r1x r1y)。"""
    n = len(x)
    r1x, r1y = autocorr(x, 1), autocorr(y, 1)
    if r1x is None or r1y is None:
        return n, r1x, r1y
    denom = 1 + r1x * r1y
    if denom <= 1e-6:
        return n, r1x, r1y
    neff = n * (1 - r1x * r1y) / denom
    return max(3.0, min(float(n), neff)), r1x, r1y


# ------------------------------------------------------------------ 对齐与滚动
def align(xs, ys, dates):
    """按日期对齐两序列，返回有效配对（同时非 None）。缺失值不插补，只剔除。"""
    px, py, pd = [], [], []
    for x, y, d in zip(xs, ys, dates):
        if x is None or y is None:
            continue
        px.append(x)
        py.append(y)
        pd.append(d)
    return px, py, pd


def rolling_corr(xs, ys, window, min_pairs=None):
    """滚动皮尔逊相关系数。窗口内有效配对 < min_pairs 时返回 None（不足不计算）。"""
    n = len(xs)
    min_pairs = min_pairs or max(5, int(round(window * 0.8)))
    out = [None] * n
    for t in range(n):
        lo = t - window + 1
        if lo < 0:
            continue
        wx = [v for v in xs[lo:t + 1] if v is not None]
        wy = [v for v in ys[lo:t + 1] if v is not None]
        # 只统计位置配对
        pair_x, pair_y = [], []
        for i in range(lo, t + 1):
            if xs[i] is not None and ys[i] is not None:
                pair_x.append(xs[i])
                pair_y.append(ys[i])
        if len(pair_x) < min_pairs:
            out[t] = None
            continue
        out[t] = pearson(pair_x, pair_y)
    return out


def window_stats(xs, ys, window, min_pairs=None):
    """滚动窗口里的有效配对数与 r，用于画图时标出“样本不足”的窗口。"""
    n = len(xs)
    min_pairs = min_pairs or max(5, int(round(window * 0.8)))
    pairs = [0] * n
    for t in range(n):
        lo = t - window + 1
        if lo < 0:
            continue
        pairs[t] = sum(1 for i in range(lo, t + 1) if xs[i] is not None and ys[i] is not None)
    r = rolling_corr(xs, ys, window, min_pairs)
    insufficient = [t for t in range(n) if window - 1 <= t and pairs[t] < min_pairs]
    return r, pairs, insufficient


# ------------------------------------------------------------------ 变换
def transform(series, kind, dates=None):
    """把原始序列变成指定形态。
    kind: 'level' 原值 | 'change' 一阶差分（绝对变化） | 'pct' 百分比变化% | 'chg_level_pct' 差分但用百分比原值...
    返回 (values, periods_used) —— 变换后前若干个点为 None（不填补）。
    """
    n = len(series)
    if kind == 'level':
        return list(series)
    if kind == 'change':
        out = [None]
        for i in range(1, n):
            a, b = series[i], series[i - 1]
            out.append(None if (a is None or b is None) else a - b)
        return out
    if kind == 'pct':
        out = [None]
        for i in range(1, n):
            a, b = series[i], series[i - 1]
            if a is None or b is None or b == 0:
                out.append(None)
            else:
                out.append((a - b) / b * 100.0)
        return out
    if kind == 'yoy':  # 同比（周度 52 周前）
        k = 52
        out = [None] * n
        for i in range(k, n):
            a, b = series[i], series[i - k]
            if a is None or b is None or b == 0:
                continue
            out[i] = (a - b) / b * 100.0
        return out
    raise ValueError('unknown transform: ' + kind)


# ------------------------------------------------------------------ 分阶段
def phase_split(dates, break_dates):
    """按给定断点日期把样本切成若干阶段，返回 [(label, [idx...]), ...]。"""
    bs = sorted(break_dates)
    phases = []
    start = 0
    labels = []
    prev = None
    for b in bs + [None]:
        if b is None:
            labels.append((prev, None))
        else:
            labels.append((prev, b))
        prev = b
    for lo, hi in labels:
        idx = [i for i, d in enumerate(dates) if (lo is None or d >= lo) and (hi is None or d < hi)]
        if idx:
            phases.append((f'{lo or "起"} ~ {hi or "止"}', idx))
    return phases


# ------------------------------------------------------------------ 报告用格式化
def fmt(v, nd=3):
    if v is None:
        return '—'
    if isinstance(v, float):
        return f'{v:.{nd}f}'
    return str(v)


def sig_mark(p):
    if p is None:
        return ''
    if p < 0.01:
        return '***'
    if p < 0.05:
        return '**'
    if p < 0.1:
        return '*'
    return ''
