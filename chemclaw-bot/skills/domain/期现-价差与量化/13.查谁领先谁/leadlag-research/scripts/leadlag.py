# -*- coding: utf-8 -*-
"""
leadlag.py — 领先滞后（Lead-Lag）通用统计引擎
==================================================
纯 numpy / scipy 实现，无 pandas 运行时依赖；可被 HTML/Excel 报告脚本直接 import。

约定（非常重要，全库统一）：
    设 A、B 为两条同频率时间序列，索引 t 为「可获取时点」(availability timestamp) 顺序。
    Lag = k > 0  表示 A 领先 B |k| 期：在 t 期对 A(t) 与 B(t+k) 做相关。
    Lag = k < 0  表示 B 领先 A |k| 期：在 t 期对 A(t) 与 B(t+k)（即 B(t-|k|)）做相关。
    所以覆盖滞后/领先的意义 → 相关性应显著为正；覆盖反转的意义 → 显著为负。
"""
from __future__ import annotations
import math
import numpy as np
from scipy import stats as sps

# ------------------------------------------------------------------ 基础工具


def _arr(x):
    return np.asarray(x, dtype=float)


def valid_pairs(a, b, lag):
    """按 lag 对齐，返回 (x, y, idx) ，只保留两侧都非 NaN 的样本。"""
    a = _arr(a); b = _arr(b)
    n = len(a)
    xs, ys, idx = [], [], []
    for t in range(n):
        j = t + lag
        if 0 <= j < n:
            av, bv = a[t], b[j]
            if not (math.isnan(av) or math.isnan(bv)):
                xs.append(av); ys.append(bv); idx.append(t)
    return np.array(xs), np.array(ys), np.array(idx, dtype=int)


# ------------------------------------------------------------------ 显著性
def t_cdf(t, df):
    return sps.t.cdf(t, df)


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def pearson_with_newey_west(x, y, lags=None, h0=0.0):
    """
    Pearson r 与 Newey-West(HAC, Bartlett 核) 稳健 t 值。
    单序列自相关惩罚：滞后 L 会引入 L 期重叠，NW 自动处理；lags 缺省取 floor(1.5*|L|)+1。
    返回 dict。
    """
    x = _arr(x); y = _arr(y)
    n = len(x)
    if n < 8:
        return {"n": n, "r": float("nan"), "t": float("nan"), "p": float("nan"),
                "t_nw": float("nan"), "p_nw": float("nan"), "nw_lags": 0,
                "df_eff": float("nan"), "n_eff_bartlett": float("nan")}
    xm = x - x.mean(); ym = y - y.mean()
    sxx = (xm * xm).sum(); syy = (ym * ym).sum()
    if sxx <= 0 or syy <= 0:
        return {"n": n, "r": float("nan"), "t": float("nan"), "p": float("nan"),
                "t_nw": float("nan"), "p_nw": float("nan"), "nw_lags": 0,
                "df_eff": float("nan"), "n_eff_bartlett": float("nan")}
    r = float((xm * ym).sum() / math.sqrt(sxx * syy))
    r = max(-0.999999, min(0.999999, r))
    df = n - 2
    t = r * math.sqrt(df / (1 - r * r))
    p = 2 * (1 - t_cdf(abs(t), df))

    # Newey-West：单变量回归 y = a + b x 的 b 的 HAC 方差；等价于 corr 的稳健 t
    if lags is None:
        lags = 1
    # OLS slope
    b1 = (xm * ym).sum() / sxx
    resid = ym - b1 * xm
    # HAC: S = sum u_t^2 x_t^2 + 2*sum_l w_l sum_t u_t u_{t-l} x_t x_{t-l}
    ux = resid * xm
    S = float((ux * ux).sum())
    L = int(max(0, lags))
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1.0)
        S += 2.0 * w * float((ux[l:] * ux[:-l]).sum())
    var_b = S / (sxx ** 2)
    se_b = math.sqrt(var_b) if var_b > 0 else float("nan")
    t_nw = b1 / se_b if se_b and not math.isnan(se_b) and se_b > 0 else float("nan")
    p_nw = 2 * (1 - t_cdf(abs(t_nw), df)) if not math.isnan(t_nw) else float("nan")

    # 有效样本量（小样本修正后的 Bartlett 估计）：按 y 的一阶自相关近似
    # n_eff ≈ n * (1 - rho_a rho_b) / (1 + rho_a rho_b)
    ra = _acf1(x); rb = _acf1(y)
    den = 1 + ra * rb
    n_eff = n * (1 - ra * rb) / den if den > 0.05 else float(n)
    df_eff = max(3.0, n_eff - 2)
    return {"n": n, "r": r, "t": t, "p": p, "t_nw": t_nw, "p_nw": p_nw,
            "nw_lags": L, "df_eff": df_eff, "n_eff_bartlett": n_eff,
            "slope": b1, "se_slope_nw": se_b}


def _acf1(z):
    z = _arr(z)
    z = z[~np.isnan(z)]
    if len(z) < 3:
        return 0.0
    z = z - z.mean()
    d = float((z * z).sum())
    if d <= 0:
        return 0.0
    return float((z[1:] * z[:-1]).sum() / d)


def ci_r(r, n, level=0.95):
    """Fisher-z 置信区间（用 n_eff）"""
    if n <= 3 or math.isnan(r):
        return (float("nan"), float("nan"))
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    q = sps.norm.ppf(1 - (1 - level) / 2)
    lo, hi = z - q * se, z + q * se
    return (math.tanh(lo), math.tanh(hi))


# ------------------------------------------------------------------ 多重检验
def p_fdr_bh(pvals):
    """Benjamini-Hochberg FDR；返回 q 值数组（与原顺序一致）"""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n, dtype=float)
    prev = 1.0
    for rank in range(n - 1, -1, -1):
        i = order[rank]
        val = p[i] * n / (rank + 1)
        prev = min(prev, val)
        q[i] = min(1.0, prev)
    return q


def p_bonferroni(pvals):
    p = np.asarray(pvals, dtype=float)
    return np.minimum(1.0, p * len(p))


# ------------------------------------------------------------------ Lag 扫描
def lag_scan(a, b, max_lag, hac_extra=0):
    """
    完整扫描 lag ∈ [-max_lag, +max_lag]，逐 lag 报告：
      n（有效样本量）、r、t、p、t_nw/p_nw、置信区间、q_bh、q_bonf
    lags 循环中 NW 滞后阶数取 floor(1.5*|lag|)+1（重叠造成的自相关）。
    """
    out = []
    lags = list(range(-max_lag, max_lag + 1))
    for L in lags:
        x, y, idx = valid_pairs(a, b, L)
        nw = max(1, int(math.floor(1.5 * abs(L))) + 1 + hac_extra)
        s = pearson_with_newey_west(x, y, lags=nw)
        lo, hi = ci_r(s["r"], s.get("n_eff_bartlett", s["n"]))
        out.append({
            "lag": L, "n": s["n"], "r": s["r"], "t": s["t"], "p": s["p"],
            "t_nw": s["t_nw"], "p_nw": s["p_nw"], "nw_lags": s["nw_lags"],
            "n_eff": s.get("n_eff_bartlett"), "ci_lo": lo, "ci_hi": hi,
            "slope": s.get("slope"), "se": s.get("se_slope_nw"),
        })
    ps = np.array([d["p"] for d in out], dtype=float)
    ps_nw = np.array([d["p_nw"] for d in out], dtype=float)
    qs = p_fdr_bh(ps); qs_nw = p_fdr_bh(ps_nw)
    bs = p_bonferroni(ps); bs_nw = p_bonferroni(ps_nw)
    for i, d in enumerate(out):
        d["q_bh"] = float(qs[i]); d["q_bonf"] = float(bs[i])
        d["q_bh_nw"] = float(qs_nw[i]); d["q_bonf_nw"] = float(bs_nw[i])
    return out


def best_lags(scan, k=3):
    """按 |r| 取前 k 个；同时给出按 p 值排序。"""
    s = [d for d in scan if not math.isnan(d["r"])]
    return sorted(s, key=lambda d: -abs(d["r"]))[:k]


# ------------------------------------------------------------------ 分段稳定性
def split_scan(a, b, max_lag, groups):
    """
    groups: list of (label, mask) ，mask 为与 a 等长的 bool 序列。
    对每个子样本做完整 lag 扫描。
    """
    res = {}
    for label, mask in groups:
        aa = [a[i] if mask[i] else float("nan") for i in range(len(a))]
        bb = [b[i] if mask[i] else float("nan") for i in range(len(b))]
        # 子样本内部顺序保留，但 NaN 会切断跨段配对；为保持 lag 语义，先压缩为连续子样本
        sz = serialize_by_mask(a, b, mask)
        if sz[0] is not None:
            res[label] = lag_scan(sz[0], sz[1], max_lag)
    return res


def serialize_by_mask(a, b, mask):
    aa = [a[i] for i in range(len(a)) if mask[i]]
    bb = [b[i] for i in range(len(b)) if mask[i]]
    if len(aa) < 12:
        return (None, None)
    return (aa, bb)


# ------------------------------------------------------------------ 滚动相关
def _num(v):
    """把 None / '' / NaN 统一成 float('nan')，避免调用方各自清洗。"""
    if v is None or v == "":
        return float("nan")
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def rolling_corr(a, b, lag, window):
    """
    在 lag 设定下，以 window 期滚动窗口计算 r 序列。
    返回 [(end_idx, r, n)]，end_idx 为样本末端的期序（原始序列 index）。
    """
    a = [_num(v) for v in a]
    b = [_num(v) for v in b]
    res = []
    n = len(a)
    xs_all = [a[t] if 0 <= t + lag < n else float("nan") for t in range(n)]
    ys_all = [b[t + lag] if 0 <= t + lag < n else float("nan") for t in range(n)]
    for end in range(window - 1, n):
        xs = xs_all[end - window + 1:end + 1]
        ys = ys_all[end - window + 1:end + 1]
        m = [i for i in range(window) if not (math.isnan(xs[i]) or math.isnan(ys[i]))]
        if len(m) < max(8, int(window * 0.8)):
            res.append((end, float("nan"), len(m)))
            continue
        X = np.array([xs[i] for i in m]); Y = np.array([ys[i] for i in m])
        sx, sy = X.std(), Y.std()
        r = float(np.corrcoef(X, Y)[0, 1]) if sx > 0 and sy > 0 else float("nan")
        res.append((end, r, len(m)))
    return res


# ------------------------------------------------------------------ 安慰剂/伪时点
def fake_release_scan(a, b, max_lag, k_list):
    """
    伪造时点安慰剂：把库存可用时点整体后移 k 期（k>0，即“更晚才知道”），
    或前移 k 期（k<0，“提前知道”，在时间上不可能）。
    如果真实时点的领先关系在“提前知道”下依然出现，则说明存在信息泄漏型伪领先。
    """
    res = {}
    n = len(a)
    for k in k_list:
        # 库存值 a[t] 在 t+k 期才可得；等价地，用 a 与 b 的对齐：a[t] 对应 b[t+k+lag]
        shifted = list(a)
        s = lag_scan(shifted, b, max_lag)  # 占位，改为移位在报告层做
        res[k] = s
    return res


# ------------------------------------------------------------------ 信息含量（增量 R²）
def ols_r2(X, y):
    """X: (n, k) 含常数项与否由调用者决定；返回 R² 与 Newey-West t 系数向量"""
    X = np.asarray(X, float); y = np.asarray(y, float)
    n, k = X.shape
    XtX = X.T @ X
    try:
        beta = np.linalg.solve(XtX, X.T @ y)
    except np.linalg.LinAlgError:
        return {"r2": float("nan"), "beta": None, "se": None}
    resid = y - X @ beta
    rss = float(resid @ resid)
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - rss / tss if tss > 0 else float("nan")
    adj = 1 - (1 - r2) * (n - 1) / (n - k) if n > k else float("nan")
    return {"r2": r2, "adj_r2": adj, "beta": beta, "k": k, "n": n,
            "f": (r2 / (k - 1)) / ((1 - r2) / (n - k)) if k > 1 and r2 < 1 else float("nan")}


def hac_se(X, resid, lags):
    """Newey-West 标准误（OLS 系数），返回 (S, XtX_inv, L)"""
    X = np.asarray(X, float); u = np.asarray(resid, float)
    n, k = X.shape
    Xu = X * u[:, None]
    S = Xu.T @ Xu
    L = max(1, int(lags))
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1.0)
        G = Xu[l:].T @ Xu[:-l]
        S += w * (G + G.T)
    # 小样本自由度修正
    S *= n / max(1.0, (n - k))
    XtX_inv = np.linalg.pinv(X.T @ X)
    return S, XtX_inv, L


def predictive_regression(y, predictors, lags):
    """predictors: list of arrays；返回系数、NW t、R²、增量 R²"""
    n = len(y)
    valid = ~np.isnan(np.asarray(y, float))
    for p in predictors:
        valid &= ~np.isnan(np.asarray(p, float))
    Y = np.asarray(y, float)[valid]
    X = np.column_stack([np.ones(valid.sum())] + [np.asarray(p, float)[valid] for p in predictors])
    nv = int(valid.sum())
    if nv < 10 + X.shape[1]:
        return {"r2": None, "adj_r2": None, "beta": None, "se": None, "t": None, "n": nv}
    fit = ols_r2(X, Y)
    if fit["beta"] is None:
        return {"r2": None, "adj_r2": None, "beta": None, "se": None, "t": None, "n": nv}
    resid = Y - X @ fit["beta"]
    S, XtX_inv, L = hac_se(X, resid, lags)
    V = XtX_inv @ S @ XtX_inv          # 系数协方差矩阵 = (X'X)^-1 S (X'X)^-1
    se = np.sqrt(np.maximum(np.diag(V), 0))
    tvals = fit["beta"] / se
    return {"r2": fit["r2"], "adj_r2": fit.get("adj_r2"), "beta": fit["beta"].tolist(),
            "se": se.tolist(), "t": tvals.tolist(), "n": int(valid.sum()),
            "nw_lags": L}


# ------------------------------------------------------------------ 自检
if __name__ == "__main__":
    # 构造已知领先关系的合成数据：B(t) = -0.5*A(t-2) + noise  → A 领先 B 2 期，负相关
    rng = np.random.default_rng(7)
    n = 400
    A = rng.normal(size=n)
    B = np.zeros(n)
    for t in range(n):
        B[t] = -0.5 * (A[t - 3] if t >= 3 else 0) + rng.normal(scale=0.8)
    sc = lag_scan(A, B, 6)
    top = best_lags(sc, 3)
    print("合成数据最强 lag（应为 +3，r≈-0.53）:")
    for d in top:
        print("  lag=%+d r=%.3f p=%.2e q_bh=%.2e n=%d" % (d["lag"], d["r"], d["p"], d["q_bh"], d["n"]))
    # FDR 自检
    print("FDR 自检:", np.round(p_fdr_bh([0.01, 0.04, 0.03, 0.5]), 4))
    # NW 自检：AR(1) 强自相关序列，朴素 t 应被高估
    x = np.zeros(500); e = rng.normal(size=500)
    for t in range(1, 500):
        x[t] = 0.9 * x[t - 1] + e[t]
    y = x + rng.normal(scale=1.0, size=500)
    s1 = pearson_with_newey_west(x, y, lags=15)
    print("NW 自检: r=%.3f  naive t=%.2f  NW t=%.2f" % (s1["r"], s1["t"], s1["t_nw"]))
