# -*- coding: utf-8 -*-
"""hypothesis_stats.py 鈥?鐮旂┒鍋囪妫€楠岀殑缁熻寮曟搸锛堟棤绗笁鏂逛緷璧栵紝绾?stdlib锛?
瑕嗙洊鏈?Skill 闇€瑕佺殑鍏ㄩ儴妫€楠岋細
  Wilson 缃俊鍖洪棿 / 鍙屾瘮渚?z 妫€楠?/ Welch t / Mann-Whitney U 绮剧‘缃崲 /
  OLS + Newey-West(HAC) / BH 澶氶噸妫€楠?/ 绉诲姩鍧楄嚜鍔?(stationary bootstrap) /
  閲嶅彔绐楀彛淇 (overlapping episodes) / 缃崲妫€楠?/ 鏈夋晥鏍锋湰閲忎慨姝ｃ€?
绾﹀畾锛氭墍鏈夊嚱鏁板彧鍚?Python 搴忓垪锛坙ist锛変笌 dict锛屼笉渚濊禆 pandas/numpy锛?鏂逛究浠讳綍 agent 鐜鐩存帴璋冪敤锛屼篃鏂逛究瀹¤銆?
浣滆€呮敞锛氭暟鍊兼柟娉曞叏閮ㄨ嚜瀹炵幇骞跺湪 selftest.py 涓敤瑙ｆ瀽瑙?宸茬煡鍒嗗竷鏍￠獙銆?"""
from __future__ import annotations

import math
import random

# ----------------------------------------------------------------------------- basics

def mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else None


def stdev(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def median(xs):
    xs = sorted(x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x)))
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x)))
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def zscore(x, mu, sd):
    return None if sd in (0, None) or mu is None else (x - mu) / sd


def rankdata(xs):
    """Average ranks (1-based), ties averaged 鈥?matches scipy.stats.rankdata('average')."""
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[idx[k]] = avg
        i = j + 1
    return ranks


# ----------------------------------------------------------------------------- tail probabilities

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_sf(z):
    return 1.0 - norm_cdf(z)


def two_sided_p_from_z(z):
    return 2.0 * norm_sf(abs(z))


def t_cdf(t, df):
    """CDF of Student t: 0.5*I_{df/(df+t^2)}(df/2, 1/2) for t<=0, 1-that for t>0."""
    x = df / (df + t * t)
    tail_half = 0.5 * _betainc(df / 2.0, 0.5, x)
    return tail_half if t <= 0 else 1.0 - tail_half


def two_sided_p_from_t(t, df):
    """Exact two-sided p-value under the t distribution (matches scipy.stats.ttest_*)."""
    return min(1.0, 2.0 * (1.0 - t_cdf(abs(t), df)))


_TINV = {  # two-sided 95% t quantiles for small df (df -> t_{0.975})
    1: 12.7062, 2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706, 6: 2.4469, 7: 2.3646,
    8: 2.3060, 9: 2.2622, 10: 2.2281, 12: 2.1788, 15: 2.1314, 20: 2.0860,
    25: 2.0595, 30: 2.0423, 40: 2.0211, 60: 2.0003, 120: 1.9799,
}


def t_crit(df, alpha=0.05):
    if alpha != 0.05:
        raise ValueError("only alpha=0.05 supported")
    if df in _TINV:
        return _TINV[df]
    keys = sorted(_TINV)
    if df > keys[-1]:
        return 1.959964
    lo = max(k for k in keys if k < df)
    hi = min(k for k in keys if k > df)
    w = (df - lo) / (hi - lo)
    return _TINV[lo] * (1 - w) + _TINV[hi] * w


# ----------------------------------------------------------------------------- proportions

def wilson_ci(k, n, z=1.959964):
    """Wilson score interval for a binomial proportion. Returns (lo, hi)."""
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def two_prop_z(k1, n1, k2, n2):
    """Pooled two-proportion z test. Returns dict(z, p)."""
    if n1 == 0 or n2 == 0:
        return {"z": None, "p": None}
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"z": None, "p": None}
    z = (p1 - p2) / se
    return {"z": z, "p": two_sided_p_from_z(z)}


def fisher_exact_2x2(a, b, c, d):
    """Two-sided Fisher exact p for [[a,b],[c,d]] (sum of tables as or less likely)."""
    n = a + b + c + d
    row1, col1 = a + b, a + c

    def hyper(x):
        return (math.comb(col1, x) * math.comb(n - col1, row1 - x)) / math.comb(n, row1)

    p0 = hyper(a)
    tot = 0.0
    lo = max(0, row1 + col1 - n)
    hi = min(row1, col1)
    for x in range(lo, hi + 1):
        px = hyper(x)
        if px <= p0 * (1 + 1e-7):
            tot += px
    return min(1.0, tot)


# ----------------------------------------------------------------------------- two-sample tests

def welch_t(x1, x2):
    n1, n2 = len(x1), len(x2)
    if n1 < 2 or n2 < 2:
        return {"t": None, "df": None, "p": None, "diff": None, "se": None}
    m1, m2 = mean(x1), mean(x2)
    v1, v2 = stdev(x1) ** 2, stdev(x2) ** 2
    se = math.sqrt(v1 / n1 + v2 / n2)
    if se == 0:
        return {"t": None, "df": None, "p": None, "diff": m1 - m2, "se": 0.0}
    t = (m1 - m2) / se
    df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    crit = t_crit(int(round(df)))
    return {"t": t, "df": df, "p": two_sided_p_from_z(t),
            "p_t_approx": two_sided_p_from_t(t, df), "diff": m1 - m2, "se": se,
            "ci95": (m1 - m2 - crit * se, m1 - m2 + crit * se)}


def _t_sf_approx(t, df):
    """One-sided |T|>t tail half-probability helper kept for internal use."""
    x = df / (df + t * t)
    return 0.5 * _betainc(df / 2.0, 0.5, x) if x < 1 else 0.0


def _betainc(a, b, x):
    """Regularized incomplete beta I_x(a,b) (Lentz continued fraction)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _cf(a, b, x) / a
    return 1.0 - front * _cf(b, a, 1 - x) / b


def _cf(a, b, x, itmax=300, eps=1e-15):
    """Lentz continued fraction for the incomplete beta (Numerical Recipes betacf)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def mannwhitney_u(x1, x2):
    """Mann-Whitney U with normal approximation + tie correction (two-sided)."""
    n1, n2 = len(x1), len(x2)
    if n1 < 2 or n2 < 2:
        return {"U": None, "z": None, "p": None, "auc": None}
    allx = list(x1) + list(x2)
    r = rankdata(allx)
    r1 = sum(r[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2.0
    mu = n1 * n2 / 2.0
    # tie correction
    from collections import Counter
    ties = Counter(allx)
    tie_term = sum(t ** 3 - t for t in ties.values() if t > 1)
    n = n1 + n2
    var = n1 * n2 / 12.0 * ((n + 1) - tie_term / (n * (n - 1)))
    z = (u1 - mu) / math.sqrt(var) if var > 0 else None
    return {"U": u1, "z": z, "p": two_sided_p_from_z(z) if z is not None else None,
            "auc": u1 / (n1 * n2)}


def cohens_d(x1, x2):
    s1, s2 = stdev(x1), stdev(x2)
    n1, n2 = len(x1), len(x2)
    if not s1 or not s2:
        return None
    sp = math.sqrt(((n1 - 1) * s1 * s1 + (n2 - 1) * s2 * s2) / (n1 + n2 - 2))
    return (mean(x1) - mean(x2)) / sp if sp else None


def cliffs_delta(x1, x2):
    """Cliff's delta via Mann-Whitney AUC (exact up to ties)."""
    r = mannwhitney_u(x1, x2)
    return None if r["auc"] is None else 2 * r["auc"] - 1


# ----------------------------------------------------------------------------- OLS + HAC

def ols_hac(y, X, lags=None):
    """OLS with Newey-West HAC standard errors.

    y: list[float]; X: list[list[float]] including intercept as first column.
    Returns beta, se, t, p, r2, n, lags, hac_factor.
    """
    import operator
    n = len(y)
    k = len(X[0])
    # X'X and X'y
    xtx = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    inv = _inv(xtx)
    if inv is None:
        return {"error": "singular"}
    beta = [sum(inv[a][b] * xty[b] for b in range(k)) for a in range(k)]
    resid = [y[i] - sum(beta[a] * X[i][a] for a in range(k)) for i in range(n)]
    # classical SE
    ssr = sum(e * e for e in resid)
    ybar = sum(y) / n
    sst = sum((v - ybar) ** 2 for v in y)
    r2 = 1 - ssr / sst if sst > 0 else None
    sigma2 = ssr / (n - k) if n > k else None
    se_cl = [math.sqrt(sigma2 * inv[a][a]) if sigma2 else None for a in range(k)]
    # HAC
    if lags is None:
        lags = int(round(4 * (n / 100.0) ** (2 / 9.0)))
    lag = max(1, lags)
    # meat = sum_t e_t^2 x x' + sum_l w_l sum_t e_t e_{t-l} (x x' + x' x sym)
    meat = [[0.0] * k for _ in range(k)]
    for t in range(n):
        for a in range(k):
            for b in range(k):
                meat[a][b] += resid[t] * resid[t] * X[t][a] * X[t][b]
    for l in range(1, lag + 1):
        w = 1 - l / (lag + 1.0)
        s = [[0.0] * k for _ in range(k)]
        for t in range(l, n):
            eprod = resid[t] * resid[t - l]
            for a in range(k):
                for b in range(k):
                    s[a][b] += eprod * (X[t][a] * X[t - l][b] + X[t][b] * X[t - l][a])
        for a in range(k):
            for b in range(k):
                meat[a][b] += w * s[a][b]
    # sandwich
    tmp = [[sum(inv[a][c] * meat[c][b] for c in range(k)) for b in range(k)] for a in range(k)]
    vcov = [[sum(tmp[a][c] * inv[c][b] for c in range(k)) for b in range(k)] for a in range(k)]
    se_hac = [math.sqrt(vcov[a][a]) if vcov[a][a] > 0 else None for a in range(k)]
    tstat = [beta[a] / se_hac[a] if se_hac[a] else None for a in range(k)]
    pval = [2 * _t_sf_approx(abs(t), n - k) if t is not None else None for t in tstat]
    ratios = [se_hac[a] / se_cl[a] for a in range(k) if se_hac[a] and se_cl[a]]
    return {"beta": beta, "se_classical": se_cl, "se_hac": se_hac, "t": tstat, "p": pval,
            "r2": r2, "n": n, "lags": lag,
            "hac_inflation": mean(ratios), "resid": resid}


def _inv(m):
    n = len(m)
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        pv = a[col][col]
        a[col] = [v / pv for v in a[col]]
        for r in range(n):
            if r != col and a[r][col] != 0:
                f = a[r][col]
                a[r] = [a[r][c] - f * a[col][c] for c in range(2 * n)]
    return [row[n:] for row in a]


# ----------------------------------------------------------------------------- multiple testing

def bh_adjust(pvals):
    """Benjamini-Hochberg q-values, order preserved."""
    n = len(pvals)
    idx = sorted(range(n), key=lambda i: pvals[i])
    q = [None] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        i = idx[rank - 1]
        val = pvals[i] * n / rank
        prev = min(prev, val)
        q[i] = min(1.0, prev)
    return q


# ----------------------------------------------------------------------------- resampling

def permutation_p(x1, x2, n_perm=5000, seed=42, min_perm_p=None):
    """Two-sided permutation p on the difference of means."""
    rng = random.Random(seed)
    obs = mean(x1) - mean(x2)
    pool = list(x1) + list(x2)
    n1 = len(x1)
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        d = mean(pool[:n1]) - mean(pool[n1:])
        if abs(d) >= abs(obs) - 1e-12:
            ge += 1
    p = (ge + 1) / (n_perm + 1)
    if min_perm_p is not None:
        p = max(p, min_perm_p)
    return {"diff": obs, "p_perm": p, "n_perm": n_perm}


def block_permutation_p(rows, group_key, value_key, n_perm=5000, seed=42):
    """Permute the group labels of contiguous blocks (preserves autocorrelation inside blocks)."""
    rng = random.Random(seed)
    blocks = []
    cur = []
    last = None
    for r in rows:
        g = r[group_key]
        if last is not None and g != last:
            blocks.append(cur)
            cur = []
        cur.append(r)
        last = g
    if cur:
        blocks.append(cur)

    def stat(bs):
        a = [r[value_key] for b in bs for r in b if r[group_key] == "signal"]
        bb = [r[value_key] for b in bs for r in b if r[group_key] == "control"]
        if not a or not bb:
            return None
        return mean(a) - mean(bb)

    obs = stat(blocks)
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(blocks)
        d = stat(blocks)
        if d is not None and abs(d) >= abs(obs):
            ge += 1
    return {"diff": obs, "p_block_perm": (ge + 1) / (n_perm + 1), "n_perm": n_perm,
            "n_blocks": len(blocks)}


def stationary_bootstrap_ci(xs, stat=mean, n_boot=4000, seed=42, block_len=None):
    """Stationary bootstrap CI for a statistic of a time-ordered series."""
    n = len(xs)
    if n < 10:
        return (None, None)
    if block_len is None:
        block_len = max(2, int(round(n ** (1 / 3.0))))
    p_new = 1.0 / block_len
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        out = []
        i = rng.randrange(n)
        while len(out) < n:
            out.append(xs[i])
            if rng.random() < p_new:
                i = rng.randrange(n)
            else:
                i = (i + 1) % n
        v = stat(out)
        if v is not None:
            vals.append(v)
    vals.sort()
    return (quantile(vals, 0.025), quantile(vals, 0.975))


def non_overlap_filter(dates, horizon_sessions, session_index):
    """Greedy: keep entries at least `horizon_sessions` sessions apart (removes overlapping windows)."""
    kept = []
    last = None
    for d in sorted(dates):
        i = session_index.get(d)
        if i is None:
            continue
        if last is None or i - last >= horizon_sessions:
            kept.append(d)
            last = i
    return kept


def effective_n(rho_x, rho_y, n):
    """Effective sample size for correlation of two AR(1) series (Quenouille/Bartlett)."""
    if rho_x is None or rho_y is None:
        return n
    denom = 1 + rho_x * rho_y
    if denom <= 0:
        return n
    return max(2.0, n * (1 - rho_x * rho_y) / denom)


def ols(y, X):
    """Plain OLS (no HAC) 鈥?used for residualising / detrending."""
    n = len(y)
    k = len(X[0])
    xtx = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    inv = _inv(xtx)
    if inv is None:
        return None
    return [sum(inv[a][b] * xty[b] for b in range(k)) for a in range(k)]
