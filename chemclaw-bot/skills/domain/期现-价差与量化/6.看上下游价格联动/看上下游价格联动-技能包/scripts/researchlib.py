# -*- coding: utf-8 -*-
"""
researchlib.py —— 上下游价格联动的纯标准库统计内核（无 numpy / scipy 依赖）

提供
  Pearson / Spearman / Fisher-z CI / t 检验 / 有效样本量 N_eff / Newey-West HAC
  滚动相关（带最小样本量保护）
  领先滞后交叉相关（lead-lag cross-correlation）
  Granger 因果检验（双向，滞后 p）
  分位数与历史分位
  阶段统计、背离/跟随状态机
  加工价差与单耗敏感度

红线
  - 任何窗口有效样本 < 最小样本数时返回 None，并给出 'insufficient' 标记，绝不返回一个数。
  - 所有相关结果都附带 N、p、CI，不单独丢一个 r 出去。
"""
import math
from bisect import bisect_left, bisect_right
from itertools import accumulate

# ---------- 基础分布 ----------


def _betacf(a, b, x, max_iter=300, eps=3e-16):
    """不完全 Beta 函数的连分式（Lentz 法）"""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
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


def betainc(a, b, x):
    """正则化不完全 Beta 函数 I_x(a,b)"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t, df):
    """t 分布上尾概率 P(T > t)"""
    if df <= 0:
        return float('nan')
    x = df / (df + t * t)
    p = 0.5 * betainc(df / 2.0, 0.5, x)
    return p if t >= 0 else 1.0 - p


def t_two_sided_p(t, df):
    return 2.0 * t_sf(abs(t), df)


def t_ppf(q, df):
    """t 分布分位数（双侧置信区间用），二分法"""
    if q <= 0.5:
        return -t_ppf(1 - q, df)
    lo, hi = 0.0, 60.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_sf(mid, df) > 1.0 - q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ---------- 描述统计 ----------


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def var(xs, ddof=1):
    n = len(xs)
    if n <= ddof:
        return None
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def stdev(xs, ddof=1):
    v = var(xs, ddof=ddof)
    return None if v is None else math.sqrt(v)


def pearson(xs, ys):
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _rank(xs):
    """平均秩（处理并列）"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    if len(xs) < 3:
        return None
    return pearson(_rank(xs), _rank(ys))


def fisher_ci(r, n, alpha=0.05):
    """Fisher z 变换的 95% 置信区间"""
    if r is None or n < 4 or abs(r) >= 1:
        return None
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    zc = 1.959963984540054
    lo, hi = z - zc * se, z + zc * se
    return (math.tanh(lo), math.tanh(hi))


def autocorr(xs, lag=1):
    n = len(xs)
    if n <= lag + 2:
        return None
    return pearson(xs[:-lag], xs[lag:])


def n_eff(n, rho_x, rho_y):
    """有效样本量：N_eff = n(1 - ρxρy) / (1 + ρxρy)（Pyper & Peterman 1998）"""
    if rho_x is None or rho_y is None:
        return float(n)
    denom = 1.0 + rho_x * rho_y
    if denom <= 1e-9:
        return float(n)
    return n * (1.0 - rho_x * rho_y) / denom


def corr_full(xs, ys, hac_lags=5):
    """完整相关输出：r, n, p, ci, spearman, n_eff, p_eff"""
    n = len(xs)
    r = pearson(xs, ys)
    if r is None:
        return {'r': None, 'n': n, 'note': 'insufficient or zero variance'}
    df = n - 2
    t = r * math.sqrt(df / max(1e-12, 1 - r * r))
    p = t_two_sided_p(t, df) if abs(r) < 1 else 0.0
    out = {
        'r': round(r, 4),
        'n': n,
        'p': p,
        'ci95': [round(fisher_ci(r, n)[0], 4), round(fisher_ci(r, n)[1], 4)] if n > 4 else None,
        'spearman': round(spearman(xs, ys), 4) if n > 3 else None,
        'r2': round(r * r, 4),
    }
    rx, ry = autocorr(xs), autocorr(ys)
    if rx is not None and ry is not None:
        ne = n_eff(n, rx, ry)
        df_e = max(1.0, ne - 2)
        te = r * math.sqrt(df_e / max(1e-12, 1 - r * r))
        out.update({
            'rho_x': round(rx, 4), 'rho_y': round(ry, 4),
            'n_eff': round(ne, 1),
            'p_eff': t_two_sided_p(te, df_e) if abs(r) < 1 else 0.0,
        })
    if hac_lags and n > hac_lags + 4:
        out['hac'] = newey_west_ols(xs, ys, lags=hac_lags)
    return out


def newey_west_ols(xs, ys, lags=5):
    """简单 OLS: y = a + b*x，返回 b 与 HAC 标准误、HAC p"""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - a - b * x for x, y in zip(xs, ys)]
    # HAC（Bartlett 核）
    S = sum((x - mx) ** 2 * e * e for x, e in zip(xs, resid))
    for L in range(1, min(lags, n - 2) + 1):
        w = 1.0 - L / (lags + 1.0)
        for t in range(L, n):
            S += w * ((xs[t] - mx) * (xs[t - L] - mx) * resid[t] * resid[t - L]
                      + (xs[t - L] - mx) * (xs[t] - mx) * resid[t - L] * resid[t])
    var_b = S / (sxx * sxx)
    se = math.sqrt(var_b) if var_b > 0 else None
    if se is None:
        return None
    tstat = b / se
    df = n - 2
    return {
        'slope': round(b, 6), 'intercept': round(a, 4),
        'se_hac': round(se, 6), 't': round(tstat, 3),
        'p_hac': t_two_sided_p(tstat, df), 'lags': lags,
    }


# ---------- 滚动 / 交叉相关 ----------


def rolling_corr_series(xs, ys, window, min_obs=None):
    """滚动 Pearson r；窗口有效样本 < min_obs 时返回 (end, None, n)，绝不补数。"""
    min_obs = min_obs if min_obs is not None else max(5, int(window * 0.8))
    out = []
    for end in range(len(xs)):
        s = end - window + 1
        if s < 0:
            out.append((end, None, 0))
            continue
        sx, sy = xs[s:end + 1], ys[s:end + 1]
        n = len(sx)
        if n < min_obs:
            out.append((end, None, n))
            continue
        out.append((end, pearson(sx, sy), n))
    return out


def cross_correlation(xs, ys, maxlag, transform=None):
    """
    corr(x_t, y_{t+k})  k ∈ [-maxlag, maxlag]
    k>0 表示 X(上游) 领先 Y(下游) k 期
    返回 [{lag, r, n}]，样本不足置 None。
    """
    out = []
    n = len(xs)
    for k in range(-maxlag, maxlag + 1):
        if k >= 0:
            a, b = xs[:n - k], ys[k:]
        else:
            a, b = xs[-k:], ys[:n + k]
        if len(a) < 10:
            out.append({'lag': k, 'r': None, 'n': len(a)})
            continue
        out.append({'lag': k, 'r': round(pearson(a, b), 4) if pearson(a, b) is not None else None, 'n': len(a)})
    return out


def granger_test(y, x, p=1):
    """
    Granger: x 是否 Granger-导致 y（控制 y 自身滞后）。
    返回 F 统计量、p、样本量。需至少 p+3 有效样本。
    """
    n = len(y)
    if n < p + 5:
        return {'note': 'insufficient'}
    rows = []
    for t in range(p, n):
        rows.append((y[t], [y[t - i] for i in range(1, p + 1)], [x[t - i] for i in range(1, p + 1)]))
    yy = [r[0] for r in rows]
    # 受限模型：仅 y 的滞后
    def ols(cols):
        m = len(yy)
        # 正规方程（小 p 直接高斯消元）
        k = len(cols[0])
        X = [[1.0] + c for c in cols]
        XtX = [[sum(X[i][r] * X[i][c] for i in range(m)) for c in range(k + 1)] for r in range(k + 1)]
        Xty = [sum(X[i][r] * yy[i] for i in range(m)) for r in range(k + 1)]
        beta = _solve(XtX, Xty)
        if beta is None:
            return None
        resid = [yy[i] - sum(beta[r] * X[i][r] for r in range(k + 1)) for i in range(m)]
        rss = sum(e * e for e in resid)
        return rss, beta, m, k
    r_unr = ols([r[1] + r[2] for r in rows])
    r_res = ols([r[1] for r in rows])
    if r_unr is None or r_res is None:
        return {'note': 'singular'}
    rss_u, _, m, k_u = r_unr
    rss_r, _, _, k_r = r_res
    q = k_u - k_r
    df2 = m - k_u - 1
    if df2 <= 0 or rss_u <= 0:
        return {'note': 'degenerate'}
    F = ((rss_r - rss_u) / q) / (rss_u / df2)
    # F 分布上尾 ~ 用 Beta 关系
    p_val = betainc(df2 / 2.0, q / 2.0, df2 / (df2 + q * F)) if F > 0 else 1.0
    return {'F': round(F, 4), 'p': p_val, 'n': m, 'lag': p}


def _solve(A, b):
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        for j in range(c, n + 1):
            M[c][j] /= pv
        for r in range(n):
            if r == c:
                continue
            f = M[r][c]
            if f == 0:
                continue
            for j in range(c, n + 1):
                M[r][j] -= f * M[c][j]
    return [M[i][n] for i in range(n)]


# ---------- 分位 ----------


def quantile(sorted_xs, q):
    """线性插值分位数（与 Excel PERCENTILE.INC 一致）"""
    n = len(sorted_xs)
    if n == 0:
        return None
    if n == 1:
        return sorted_xs[0]
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * frac


def pct_rank(sorted_xs, v):
    """v 在样本中的历史分位（0-100，<=v 的占比）"""
    if not sorted_xs:
        return None
    i = bisect_right(sorted_xs, v)
    return 100.0 * i / len(sorted_xs)


def expanding_rank(values):
    """每个点相对其之前所有点（含自身）的历史分位，避免未来函数"""
    out = []
    hist = []
    for v in values:
        hist.append(v)
        hist.sort()
        out.append(round(pct_rank(hist, v), 1))
    return out


# ---------- 传导状态机 ----------


def transmission_states(px, pta, window=20, px_thr=0.03, agree=0.5):
    """
    定义「跟随 / 背离」：
      上游 k 期内涨幅 |Δpx| >= px_thr，观察下游同期变化与上游方向是否一致。
      agree: 下游同向幅度至少为上游的 agree 倍才算「跟上」，否则「弱跟随」。
    返回每个点的状态序列（只用于报告叙述，不做交易信号）。
    """
    states = []
    for i in range(len(px)):
        if i < window:
            states.append(None)
            continue
        dpx = px[i] / px[i - window] - 1
        dpta = pta[i] / pta[i - window] - 1
        if abs(dpx) < px_thr:
            states.append('flat')
            continue
        same_dir = (dpx > 0) == (dpta > 0)
        ratio = dpta / dpx if dpx != 0 else None
        if same_dir and ratio >= agree:
            states.append('follow')
        elif same_dir:
            states.append('weak')
        else:
            states.append('diverge')
    return states


def find_diverge_runs(states, dates, min_len=5, gap=5):
    """
    从逐日状态里切出「背离区间」。

    states 是逐日判定的（每次看 window 个观测的累计涨跌），所以真实的一段背离
    通常表现为「几个 diverge 日 + 中间夹一两个 weak/flat + 又几个 diverge 日」。
    因此这里做两件事：
      1. gap <= gap 的非背离日视为同一段内的噪声，不打断；
      2. 合并后长度 >= min_len 才算一段。
    min_len 默认 5（约一周），gap 默认 5；两个参数写进报告，保证可复现。
    """
    runs = []
    start = None
    last_hit = None
    for i, s in enumerate(states):
        if s == 'diverge':
            if start is None:
                start = i
            last_hit = i
        elif start is not None and last_hit is not None and i - last_hit > gap:
            if last_hit - start + 1 >= min_len:
                runs.append((start, last_hit))
            start = None
            last_hit = None
    if start is not None and last_hit is not None:
        if last_hit - start + 1 >= min_len:
            runs.append((start, last_hit))
    out = []
    for s, e in runs:
        out.append({'start_idx': s, 'end_idx': e, 'start': dates[s], 'end': dates[e],
                    'n_days': e - s + 1})
    return out

def process_spread(pta_price, px_price, coef=0.655, other_cost=0.0):
    """理论加工价差 = PTA - coef*PX - 其他辅料成本"""
    return pta_price - coef * px_price - other_cost
