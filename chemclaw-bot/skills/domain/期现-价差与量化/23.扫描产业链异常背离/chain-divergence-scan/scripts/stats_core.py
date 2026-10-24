# -*- coding: utf-8 -*-
"""产业链异常背离扫描 —— 统计内核。

设计原则（与 references/02-统计指标与阈值.md 一一对应）：

1. 先对齐再统计：只在双方都有交易的日期上计算，绝不插补、不外推。
2. 区分两类相关性：
   - price-level correlation  价格水平相关（被共同趋势/通胀抬升，仅作背景）
   - return correlation       收益率相关（日度对数收益，主口径）
3. 标准化价格变化：Z_i = ln(P_t / P_{t0}) / (σ_ret * sqrt(n))，可跨品种比较(相当于"信息单位"波动)
4. 价差 / 比价偏离：均在对数空间计算，并做滚动 Z 与历史分位。
5. 多重检验：Bonferroni + BH-FDR + 置换抽样(pairwise bootstrap) 三重门控。
6. 只描述、不预测，不产出交易建议。

依赖：仅标准库 + math/statistics，便于在 Agent 环境里直接运行。
"""
import math
import random
from statistics import NormalDist

ND = NormalDist()

# ---------------------------------------------------------------------------
# 基础统计
# ---------------------------------------------------------------------------


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def stdev(xs, ddof=1):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((v - m) ** 2 for v in xs) / (n - ddof))


def pearson(xs, ys):
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    r = sxy / math.sqrt(sxx * syy)
    return max(-1.0, min(1.0, r))


def rank(vals):
    idx = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[idx[j + 1]] == vals[idx[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            out[idx[k]] = avg
        i = j + 1
    return out


def spearman(xs, ys):
    return pearson(rank(xs), rank(ys))


def corr_pvalue(r, n):
    """双侧 p 值（t 分布近似，df=n-2）。"""
    if r is None or n is None or n < 4:
        return None
    r = max(-0.999999, min(0.999999, r))
    df = n - 2
    t = abs(r) * math.sqrt(df / (1 - r * r))
    # 直接用 t 分布数值积分（已验证：t_p(2.228,10)=0.0500 等），不做正态近似
    return t_two_sided_p(t, df)


def t_two_sided_p(t, df):
    """t 分布双侧尾概率 = I_{df/(df+t²)}(df/2, 1/2)（正则化不完全 Beta，连分式，精度 ~1e-6）。"""
    t = abs(t)
    if t <= 0 or df <= 0:
        return 1.0
    return _betai(0.5 * df, 0.5, df / (df + t * t))


def _betacf(a, b, x):
    itermax, eps, fpmin = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > fpmin else fpmin)
    h = d
    for m in range(1, itermax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > fpmin else fpmin)
        c = 1.0 + aa / c
        c = c if abs(c) > fpmin else fpmin
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > fpmin else fpmin)
        c = 1.0 + aa / c
        c = c if abs(c) > fpmin else fpmin
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def _betai(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
           + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(lbt)
    if x < (a + 1.0) / (a + b + 2.0):
        val = bt * _betacf(a, b, x) / a
    else:
        val = 1.0 - bt * _betacf(b, a, 1.0 - x) / b
    return min(1.0, max(0.0, val))


def _lgamma(z):
    if z < 0.5:
        return math.log(math.pi / math.sin(math.pi * z)) - _lgamma(1 - z)
    z -= 1
    x = 0.99999999999980993
    coef = [676.5203681218851, -1259.1392167224028, 771.32342877765313,
            -176.61502916214059, 12.507343278686905, -0.13857109526572012,
            9.9843695780195716e-6, 1.5056327351493116e-7]
    for i, c in enumerate(coef):
        x += c / (z + i + 1)
    t = z + len(coef) - 0.5
    return 0.9189385332046727 + (z + 0.5) * math.log(t) - t + math.log(x)


def fisher_ci(r, n, z=1.959964):
    if r is None or n is None or n < 4:
        return None, None
    r = max(-0.9999, min(0.9999, r))
    f = math.atanh(r)
    se = 1 / math.sqrt(n - 3)
    return math.tanh(f - z * se), math.tanh(f + z * se)


def autocorr(xs, lag=1):
    if len(xs) <= lag + 2:
        return None
    a, b = xs[lag:], xs[:-lag]
    return pearson(a, b)


def eff_sample(r, rx, ry, n):
    """有效样本量 N_eff = n (1-ρxρy)/(1+ρxρy)（Bayley-Hammersley 简化式）。"""
    if None in (rx, ry) or rx * ry <= -0.999 or n is None:
        return n
    denom = 1 + rx * ry
    if denom <= 0:
        return n
    return max(4.0, n * (1 - rx * ry) / denom)


def percentile_of(value, dist):
    """value 在 dist(经验分布) 中的地位 → [0,100] 分位（并列取中点）。"""
    if not dist:
        return None
    less = sum(1 for v in dist if v < value)
    eq = sum(1 for v in dist if v == value)
    return (less + eq / 2.0) / len(dist) * 100.0


def quantile(sorted_vals, q):
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return sorted_vals[0]
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def two_sided_tail_from_z(z):
    return 2 * (1 - ND.cdf(abs(z)))


# ---------------------------------------------------------------------------
# 多重比较校正
# ---------------------------------------------------------------------------


def bonferroni(pvals, m=None):
    m = m or len(pvals)
    return [min(1.0, p * m) if p is not None else None for p in pvals]


def bh_fdr(pvals):
    """Benjamini-Hochberg 调整后的 q 值。"""
    items = [(p, i) for i, p in enumerate(pvals) if p is not None]
    m = len(pvals)
    items.sort()
    q = [None] * len(pvals)
    k = len(items)
    prev = 1.0
    for rank_i in range(k - 1, -1, -1):
        p, idx = items[rank_i]
        val = min(prev, p * m / (rank_i + 1))
        q[idx] = min(1.0, val)
        prev = val
    return q


# ---------------------------------------------------------------------------
# 置换抽样：在"配对层面"产生零分布
# ---------------------------------------------------------------------------


def permutation_null_corr(returns_a, returns_b, n_perm=2000, seed=20261020, block=None):
    """对 B 的收益序列做循环平移(循环 block shuffle)，得到 r 的零分布。

    循环平移保持了 B 自身的自相关结构，只破坏与 A 的当期对齐关系，
    是配对研究中控制"共同趋势"的最稳妥做法之一。
    """
    rnd = random.Random(seed)
    n = min(len(returns_a), len(returns_b))
    a, b = returns_a[-n:], returns_b[-n:]
    base = pearson(a, b)
    null = []
    for _ in range(n_perm):
        k = rnd.randrange(int(n * 0.1), int(n * 0.9)) if n > 40 else rnd.randrange(1, max(2, n - 1))
        bb = b[k:] + b[:k]
        r = pearson(a, bb)
        if r is not None:
            null.append(r)
    if base is None or not null:
        return dict(r=base, null_mean=None, null_sd=None, p_perm=None, n_perm=len(null))
    nm = mean(null)
    ns = stdev(null) if len(null) > 2 else None
    p = (sum(1 for v in null if abs(v - nm) >= abs(base - nm)) + 1) / (len(null) + 1)
    return dict(r=base, null_mean=nm, null_sd=ns, p_perm=p, n_perm=len(null),
                null_q05=quantile(sorted(null), 0.05), null_q95=quantile(sorted(null), 0.95))


# ---------------------------------------------------------------------------
# 滚动相关 与 变点
# ---------------------------------------------------------------------------


def rolling_corr(xs, ys, window):
    """返回与 xs 等长的列表，前 window-1 个为 None。"""
    out = [None] * len(xs)
    for i in range(window - 1, len(xs)):
        a = xs[i - window + 1:i + 1]
        b = ys[i - window + 1:i + 1]
        out[i] = pearson(a, b)
    return out


def rolling_z_long(series, window, min_obs=None):
    """对已经经过换月断点清洗的序列做滚动 z：（t 日）z 在 t-1 日前的窗口内计算，避免前视。"""
    min_obs = min_obs or max(20, window // 3)
    out = [None] * len(series)
    for i in range(len(series)):
        lo = max(0, i - window)
        hist = [v for v in series[lo:i] if v is not None]
        if len(hist) < min_obs or series[i] is None:
            continue
        m = mean(hist)
        s = stdev(hist)
        if s and s > 0:
            out[i] = (series[i] - m) / s
    return out


def run_length_at_end(flags):
    """从序列末尾往回数连续为 True 的天数。"""
    k = 0
    for v in reversed(flags):
        if v:
            k += 1
        else:
            break
    return k


# ---------------------------------------------------------------------------
# 主扫描
# ---------------------------------------------------------------------------

DEFAULTS = dict(
    window_mask=60,          # 滚动窗口（交易日）
    recent_windows=[5, 20, 60],   # 近期表现窗口
    daily_min_obs=30,        # 计算日度收益相关的最小样本
    rolling_min_obs_ratio=0.8,
    drop_threshold=0.45,     # 相关性"脱钩"阈值：|r_long_baseline| - r_recent >= 0.45
    z_threshold=2.0,         # 偏离阈值(|z|)
    persist_days=5,          # 持续性：连续 N 个交易日超阈值
    hist_min_days=250,       # 计算历史分位的最小样本
    perm_n=1200,
    seed=20261020,
)


def _log_returns(dates, closes):
    out = []
    for i in range(1, len(closes)):
        if closes[i] and closes[i - 1] and closes[i] > 0 and closes[i - 1] > 0:
            out.append((dates[i], math.log(closes[i] / closes[i - 1])))
    return out


def scan_pair(pa, pb, rel, params=None, series_meta=None):
    """对一对品种做完整扫描。

    pa/pb: dict(dates=[date_str], closes=[float], roll_dates=set(), segment_id=[int])
    """
    P = dict(DEFAULTS)
    if params:
        P.update(params)
    win = P['window_mask']

    # ---- 1. 对齐（日期交集）----
    ma = {d: (c, roll_dates, seg) for d, c, roll_dates, seg in
          zip(pa['dates'], pa['closes'], pa['roll_flag'], pa['seg'])}
    mb = {d: (c, roll_dates, seg) for d, c, roll_dates, seg in
          zip(pb['dates'], pb['closes'], pb['roll_flag'], pb['seg'])}
    common = sorted(set(ma) & set(mb))
    n_common = len(common)

    result = dict(code_a=rel['a'], code_b=rel['b'], rtype=rel['rtype'],
                  n_overlap=n_common,
                  first=common[0] if common else None,
                  last=common[-1] if common else None,
                  status='ok', notes=[])
    if n_common < 60:
        result['status'] = 'insufficient'
        result['notes'].append(f'可比重叠交易日仅 {n_common} 天，不足以做滚动相关与历史分位')
        return result

    # 换月断点：任一方在 t 或 t-1 发生主力换月则标记
    roll_set = set()
    for src in (pa['roll_dates'], pb['roll_dates']):
        roll_set |= set(src)
    common_idx = {d: i for i, d in enumerate(common)}

    # 连续区间（用于滚动窗口不跨断点）：seg=1 表示"跨换月跳空的收益"，扫描时整段排除
    seg_of = [pa['seg'][common_idx[d]] or pb['seg'][common_idx[d]] for d in common]

    ca = [ma[d][0] for d in common]
    cb = [mb[d][0] for d in common]

    # ---- 2. 对数收益（同日对齐，剔除换月跳空日，不插补）----
    r_dates, ra, rb = [], [], []
    for i in range(1, n_common):
        if seg_of[i]:
            continue
        if ca[i - 1] > 0 and cb[i - 1] > 0:
            r_dates.append(common[i])
            ra.append(math.log(ca[i] / ca[i - 1]))
            rb.append(math.log(cb[i] / cb[i - 1]))
    n_ret = len(ra)
    result['n_returns'] = n_ret
    result['n_roll_breaks'] = sum(1 for v in seg_of if v)
    result['excluded_roll_returns'] = sum(1 for v in seg_of if v)
    # 被剔除的换月/断档日（日期清单），供 Excel 明细表把这天收益置空，保证与内核一致
    result['excluded_roll_dates'] = [common[i] for i, v in enumerate(seg_of) if v]

    # ---- 3. 价格水平相关（背景口径）----
    r_level = pearson(ca, cb)
    r_level_s = spearman(ca, cb)
    result['r_level'] = r_level
    result['r_level_spearman'] = r_level_s
    result['r_level_p'] = corr_pvalue(r_level, n_common)

    # ---- 4. 日度收益率相关（主口径）----
    r_daily = pearson(ra, rb)
    result['r_daily'] = r_daily
    result['r_daily_spearman'] = spearman(ra, rb)
    result['r_daily_p'] = corr_pvalue(r_daily, n_ret)
    lo, hi = fisher_ci(r_daily, n_ret)
    result['r_daily_ci'] = [lo, hi]
    rax, rbx = autocorr(ra), autocorr(rb)
    result['acf_a'], result['acf_b'] = rax, rbx
    n_eff = eff_sample(r_daily, rax, rbx, n_ret)
    result['n_eff'] = n_eff
    result['r_daily_p_eff'] = corr_pvalue(r_daily, int(n_eff))

    # ---- 5. 窗口收益率相关（5/20/60 日窗口内，逐日收益率的 Pearson）----
    win_corr = {}
    for w in P['recent_windows']:
        if n_ret < w + 5:
            win_corr[w] = None
            continue
        win_corr[w] = pearson(ra[-w:], rb[-w:])
    result['window_corr'] = win_corr

    # ---- 6. 滚动相关（默认 60 日）+ 脱钩判定 ----
    rc = rolling_corr(ra, rb, win)
    result['roll_window'] = win
    valid_start = win - 1
    floor_r = P['drop_threshold']
    dropped = [None] * len(rc)
    for i, v in enumerate(rc):
        if v is None:
            continue
        dropped[i] = (abs(v) < max(0.2, result['r_daily'] - floor_r)) if result['r_daily'] is not None else None
    result['roll_corr_last'] = rc[-1]
    result['roll_corr_median'] = mean([v for v in rc if v is not None])
    hist_rc = [v for v in rc if v is not None]
    result['roll_corr_pct'] = percentile_of(rc[-1], hist_rc) if rc[-1] is not None else None
    # 相关系数变化幅度
    base_rc = result['roll_corr_median']
    result['corr_change'] = (rc[-1] - base_rc) if (rc[-1] is not None and base_rc is not None) else None
    # 脱钩持续天数（末尾）
    tail_flags = []
    for i in range(len(rc) - 1, -1, -1):
        if dropped[i] is None:
            break
        tail_flags.append(dropped[i])
    result['drop_run_days'] = run_length_at_end(list(reversed(tail_flags)))
    result['drop_run_days_trailing'] = run_length_at_end(tail_flags)

    # ---- 7. 标准化价格变化（可跨品种比较）----
    sd_a = stdev(ra) if n_ret > 30 else None
    sd_b = stdev(rb) if n_ret > 30 else None
    result['sigma_daily_a'], result['sigma_daily_b'] = sd_a, sd_b
    std_change = {}
    for w in P['recent_windows']:
        if len(ra) < w or not sd_a or not sd_b:
            std_change[w] = None
            continue
        cum_a = sum(ra[-w:])
        cum_b = sum(rb[-w:])
        std_change[w] = dict(
            a=cum_a, b=cum_b,
            a_std=cum_a / (sd_a * math.sqrt(w)),
            b_std=cum_b / (sd_b * math.sqrt(w)),
        )
    result['std_change'] = std_change

    # ---- 8. 比价与价差（对数价差，天然无量纲）----
    k = rel.get('k')
    # 仅当 ratio 系数存在时，价差 = ln(B) - ln(k A)；否则价差直接用 ln B - ln A 仅作背景
    spread_src = [math.log(cb[i]) - math.log(ca[i]) for i in range(n_common)]
    spread_lbl = '比价 ln(B/A)'
    if k:
        spread_src = [math.log(cb[i]) - math.log(k * ca[i]) for i in range(n_common)]
        spread_lbl = f'价差 ln(B) - ln({k}·A)'
    result['spread_label'] = spread_lbl

    # 滚动 z（用 t 日之前的窗口），断点处重置
    z = [None] * n_common
    min_obs = max(20, int(win * 0.6))
    for i in range(n_common):
        if seg_of[i]:
            continue
        lo_i = max(0, i - win)
        hist = [spread_src[j] for j in range(lo_i, i) if not seg_of[j]]
        if len(hist) >= min_obs:
            m = mean(hist)
            s = stdev(hist)
            if s and s > 1e-12:
                z[i] = (spread_src[i] - m) / s
    result['spread_last'] = spread_src[-1]
    result['spread_pct'] = percentile_of(spread_src[-1], spread_src)
    result['z_last'] = z[-1]
    z_hist = [v for v in z if v is not None]
    result['z_pct'] = percentile_of(z[-1], z_hist) if z[-1] is not None else None
    result['z_abs_max_hist'] = max(abs(v) for v in z_hist) if z_hist else None
    # 持续天数
    thr = P['z_threshold']
    flag = [None if v is None else abs(v) >= thr for v in z]
    result['z_run_days'] = run_length_at_end(flag)
    result['z_series'] = z
    result['spread_series'] = spread_src

    # 比价/价差变化（近期窗口）
    ratio_dev = {}
    for w in P['recent_windows']:
        if n_common > w:
            ratio_dev[w] = spread_src[-1] - spread_src[-1 - w]
    result['spread_change'] = ratio_dev
    result['ratio_last'] = cb[-1] / ca[-1] if ca[-1] else None

    # ---- 9. 数据质量：重叠覆盖 & 换月次数 ----
    span_days = len(common)
    result['overlap_ratio_vs_short'] = None
    if series_meta:
        na = series_meta.get(rel['a'], {}).get('n')
        nb = series_meta.get(rel['b'], {}).get('n')
        if na and nb:
            result['overlap_ratio_vs_short'] = span_days / min(na, nb)
    result['last_prices'] = dict(a=ca[-1], b=cb[-1], date=common[-1])
    result['common_dates'] = common
    result['ret_dates'] = r_dates
    result['ret_a'] = ra
    result['ret_b'] = rb
    result['roll_corr_series'] = rc
    result['dates'] = common
    result['close_a'] = ca
    result['close_b'] = cb
    return result


def judge_anomaly(res, P=None, n_tests=1):
    """把统计量转成"异常判定"。全部门槛写明，可复核。"""
    P = dict(DEFAULTS)
    if P and isinstance(P, dict):
        pass
    out = dict(n_tests=n_tests, checks=[])
    if res.get('status') != 'ok':
        return dict(verdict='数据不足', score=0, checks=[], reasons=['数据不足'], n_tests=n_tests)

    z = res.get('z_last')
    z_run = res.get('z_run_days') or 0
    rc_last = res.get('roll_corr_last')
    r_base = res.get('r_daily')
    corr_drop = None
    if rc_last is not None and r_base is not None:
        corr_drop = abs(r_base) - rc_last

    checks = []

    def add(name, passed, value, thr, note=''):
        checks.append(dict(name=name, passed=bool(passed), value=value, threshold=thr, note=note))

    add('价差/比价偏离阈值', z is not None and abs(z) >= DEFAULTS['z_threshold'],
        None if z is None else round(z, 3), f'|z| >= {DEFAULTS["z_threshold"]}')
    add('偏离持续性', z_run >= DEFAULTS['persist_days'], z_run,
        f'连续 >= {DEFAULTS["persist_days"]} 个交易日超阈值（当前 {z_run} 日）')
    p_bonf = None
    if res.get('r_daily_p') is not None:
        p_bonf = min(1.0, res['r_daily_p'] * n_tests)
    add('全期相关显著性(仅门控)', p_bonf is not None and p_bonf < 0.05, p_bonf, 'Bonferroni p < 0.05')
    add('近期相关性脱钩', corr_drop is not None and corr_drop >= DEFAULTS['drop_threshold'],
        None if corr_drop is None else round(corr_drop, 3), f'|r_all| - r_roll >= {DEFAULTS["drop_threshold"]}')

    n_pass = sum(1 for c in checks if c['passed'])
    # 评分：偏离程度(0-40) + 相关性变化(0-30) + 持续性(0-30)
    score = 0.0
    if z is not None:
        score += min(40.0, abs(z) / 3.0 * 40.0)
    if corr_drop is not None:
        score += max(0.0, min(30.0, corr_drop / 0.8 * 30.0))
    score += min(30.0, z_run / 20.0 * 30.0)

    if n_pass >= 3:
        verdict = '异常背离（候选）'
    elif n_pass == 2:
        verdict = '关注'
    elif n_pass == 1:
        verdict = '偏离但未达门槛'
    else:
        verdict = '正常'
    reasons = [c['name'] + ('✓' if c['passed'] else '✗') for c in checks]
    return dict(verdict=verdict, score=round(score, 1), checks=checks, reasons=reasons,
                n_tests=n_tests, corr_drop=corr_drop, p_bonf=p_bonf)
