# -*- coding: utf-8 -*-
"""
analysis.py — 甲醇港口库存(周度变化) × 甲醇期货(周度收益率) 领先滞后分析
输出 build/result.json 供 HTML / Excel 生成器使用
"""
import json, math, os, sys, datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import leadlag as LL

OUT = HERE
S = json.load(open(os.path.join(OUT, "sample.json"), encoding="utf-8"))
rows = S["rows"]
n = len(rows)
dates = [r["stat"] for r in rows]
pubs = [r["pub"] for r in rows]

# ---------------- 变量定义 ----------------
dI = [r["dI"] if r["dI"] is not None else float("nan") for r in rows]          # 港口库存周度变化(万吨)
ret = [r["ret"] if r["ret"] is not None else float("nan") for r in rows]        # 披露当日收益(对数)
dI_pct = [r["dI_pct"] if r["dI_pct"] is not None else float("nan") for r in rows]
dI_float = [r["dI_float"] if r["dI_float"] is not None else float("nan") for r in rows]

MAXLAG = int(os.environ.get("MAXLAG", "12"))

# ---------------- 1) 主检验：Lag 全扫描 ----------------
main_scan = LL.lag_scan(dI, ret, MAXLAG)

# 早期偏差诊断：检验“披露当日残差收益”是否与 t 期库存变化相关（应≈0）
main_ret_simple = [r["ret_simple"] if r["ret_simple"] is not None else float("nan") for r in rows]
diag_same_day = LL.lag_scan(dI, main_ret_simple, 2)

# ---------------- 2) 阶段定义 ----------------
def mask_between(d0, d1):
    return [d0 <= d <= d1 for d in dates]

STAGES = [
    ("S1_去库升水期_2024Q4-2025Q1", "2024-10-23", "2025-03-31",
     "高库存、价格偏强震荡（2,240→2,700→2,480）：港口仍处累库/高库存阶段，基差承压但绝对价格上行"),
    ("S2_低波动磨底期_2025Q2-Q3", "2025-04-01", "2025-09-30",
     "价格在 2,200–2,400 窄幅磨底，库存自高位回落，供需双弱、市场对库存信息定价钝化"),
    ("S3_深度去库上涨期_2025Q4-2026Q1", "2025-10-01", "2026-03-31",
     "库存持续去化至历史低位，价格自 2,135 升至 3,229，低库存成为主交易逻辑"),
    ("S4_高位回调再上涨期_2026Q2-Q3", "2026-04-01", "2026-10-14",
     "价格先自高位回落至 2,428 再升至 3,260，地缘/进口扰动与 MTO 需求主导，库存频创新低"),
]
YEAR_GROUPS = [("2024", "2024-10-01", "2024-12-31"), ("2025", "2025-01-01", "2025-12-31"),
               ("2026", "2026-01-01", "2026-10-31")]

stage_scan, stage_meta = {}, []
for code, d0, d1, note in STAGES:
    m = mask_between(d0, d1)
    idx = [i for i, x in enumerate(m) if x]
    a = [dI[i] for i in idx]; b = [ret[i] for i in idx]
    stage_scan[code] = LL.lag_scan(a, b, MAXLAG)
    stage_meta.append({"code": code, "start": d0, "end": d1, "n_weeks": len(idx), "note": note,
                       "inv_start": rows[idx[0]]["total"], "inv_end": rows[idx[-1]]["total"],
                       "px_start": rows[idx[0]]["P_pub"], "px_end": rows[idx[-1]]["P_pub"]})

year_scan, year_meta = {}, []
for y, d0, d1 in YEAR_GROUPS:
    m = mask_between(d0, d1)
    idx = [i for i, x in enumerate(m) if x]
    a = [dI[i] for i in idx]; b = [ret[i] for i in idx]
    year_scan[y] = LL.lag_scan(a, b, MAXLAG)
    year_meta.append({"year": y, "n_weeks": len(idx), "start": dates[idx[0]], "end": dates[idx[-1]]})

# 半年分段（更长序列支撑稳定性）
HALF = []
cur = datetime.date(2024, 10, 1)
while cur < datetime.date(2026, 10, 1):
    if cur.month < 7:
        d0 = cur.replace(month=1, day=1); d1 = cur.replace(month=6, day=30)
        label = f"{cur.year}H1"
    else:
        d0 = cur.replace(month=7, day=1); d1 = cur.replace(month=12, day=31)
        label = f"{cur.year}H2"
    HALF.append((label, d0.isoformat(), d1.isoformat()))
    cur = (datetime.date(cur.year + 1, 1, 1) if cur.month >= 7 else datetime.date(cur.year, 7, 1))

half_scan = {}
for label, d0, d1 in HALF:
    idx = [i for i, d in enumerate(dates) if d0 <= d <= d1]
    if len(idx) < 15:
        continue
    half_scan[label] = LL.lag_scan([dI[i] for i in idx], [ret[i] for i in idx], MAXLAG)

# ---------------- 3) 变换稳健性（同一 Lag 网格，不同变换） ----------------
VARIANTS = {
    "D1_主设定_Δ库存(万吨)×披露日对数收益": (dI, ret),
    "D2_Δ库存百分比×披露日收益": (dI_pct, [r["ret_simple"] if r["ret_simple"] is not None else float("nan") for r in rows]),
    "D3_Δ库存(万吨)×可用周收益": (dI, [r["ret_avail"] if r["ret_avail"] is not None else float("nan") for r in rows]),
    "D4_库存水平×价格水平(伪回归对照)": ([r["total"] for r in rows], [r["P_pub"] for r in rows]),
    "D5_库存水平×披露日收益": ([r["total"] for r in rows], ret),
    "D6_Δ库存浮动比例×披露日收益": (dI_float, ret),
}
variant_scan = {k: LL.lag_scan(v[0], v[1], MAXLAG) for k, v in VARIANTS.items()}

# ---------------- 4) 对齐敏感性（伪造时点安慰剂） ----------------
# Shift = -1：库存提前 1 期可得（时间上不可能）；Shift = +1：晚 1 期才可得
def shift_scan(shift):
    a = [dI[t + shift] if 0 <= t + shift < n else float("nan") for t in range(n)]
    return LL.lag_scan(a, ret, MAXLAG)

shift_scans = {str(k): shift_scan(k) for k in (-2, -1, 0, 1, 2)}

# 朴素对齐（不使用真实发布日期，直接用统计期末周收盘）作为对照
naive_ret = []
for i, r in enumerate(rows):
    prevd = rows[i - 1]["stat_last_td"] if i > 0 else None
    naive_ret.append((math.log(r["P_pub"] / _p) if False else float("nan")))
# 直接用“该周最后交易日收盘 / 上一周最后交易日收盘”
fc = {r["stat"]: r["P_pub"] for r in rows}
naive_ret = [float("nan")]
for i in range(1, n):
    naive_ret.append(math.log(rows[i]["P_pub"] / rows[i - 1]["P_pub"]))
naive_scan = LL.lag_scan(dI, naive_ret, MAXLAG)

# ---------------- 5) 滚动相关 ----------------
WINDOW = 26
roll = {}
for L in (1, 2, 3, 0, -1):
    if L < -MAXLAG or L > MAXLAG:
        continue
    rc = LL.rolling_corr(dI, ret, L, WINDOW)
    roll[str(L)] = [{"end": dates[e], "r": (float(v) if not math.isnan(v) else None), "n": m} for e, v, m in rc]

# ---------------- 6) 领先滞后矩阵（A→B 与 B→A 对称检验） ----------------
matrix = []
for L in range(-MAXLAG, MAXLAG + 1):
    d = main_scan[L + MAXLAG]
    matrix.append({"lag": L, "r": d["r"], "n": d["n"], "p": d["p"], "t_nw": d["t_nw"], "p_nw": d["p_nw"],
                   "q_bh": d["q_bh"], "ci_lo": d["ci_lo"], "ci_hi": d["ci_hi"]})

# ---------------- 7) 预测回归 ----------------
# 7a 单因子：用 t 期库存变化预测 t+2 期收益（披露后 2 周可见信息）
y = [float("nan")] * n
x1 = [float("nan")] * n
x2 = [float("nan")] * n
for t in range(n - 2):
    y[t] = ret[t + 2]
    x1[t] = dI[t]
    x2[t] = dI[t + 1]
reg = LL.predictive_regression(y, [x1], 3)
reg_both = LL.predictive_regression(y, [x1, x2], 3)

# 7b 行业基本面多因子预测回归（全部使用 t 期或更早可得的披露值）
mto_path = os.path.join(os.path.dirname(HERE), "raw", "mto_parsed.json")
MTO = {}
if os.path.exists(mto_path):
    for r in json.load(open(mto_path, encoding="utf-8")):
        MTO[r["stat"]] = r["mto"]
mto_lvl, mto_chg = [], []
for r in rows:
    # 取披露日及之前最近一期 MTO（严格可得）
    cand = [k for k in MTO if k <= r["stat"]]
    v = MTO[max(cand)] if cand else float("nan")
    mto_lvl.append(v)
for i in range(n):
    mto_chg.append(mto_lvl[i] - mto_lvl[i - 1] if i > 0 else float("nan"))
spread = [r["total"] for r in rows]
# 与 t 期收益（Lag 0）与 t+1 期收益（Lag 1）分别回归
regressions = {}
for L in (0, 1, 2):
    ys = [float("nan")] * n
    for t in range(n):
        if t + L < n:
            ys[t] = ret[t + L]
    regressions[f"L{L}"] = {
        "inventory_only": LL.predictive_regression(ys, [dI, spread], 3),
        "inventory_plus_fundamental": LL.predictive_regression(ys, [dI, spread, mto_lvl, mto_chg], 3),
    }

# ---------------- 8) 单位根与自相关诊断 ----------------
def acf(z, k):
    z = np.array([v for v in z if not math.isnan(v)])
    z = z - z.mean()
    d = (z * z).sum()
    return float((z[k:] * z[:-k]).sum() / d) if d > 0 else float("nan")


def acf_series(z, kmax):
    return [acf(z, k) for k in range(1, kmax + 1)]


def ljung_box(z, kmax):
    z = np.array([v for v in z if not math.isnan(v)])
    nn = len(z)
    q = 0.0
    for k in range(1, kmax + 1):
        rk = acf(z, k)
        q += rk * rk / (nn - k)
    q *= nn * (nn + 2)
    from scipy import stats as sps
    return float(q), float(1 - sps.chi2.cdf(q, kmax))

def adf(z, lags=2):
    """增广 Dickey-Fuller：Δz_t = a + Σb_i Δz_{t-i} + γ z_{t-1}-bar + e_t，返回 γ 的 t 值"""
    z = np.array([v for v in z if not math.isnan(v)])
    d = np.diff(z)
    cols = [np.ones(len(d) - lags), z[lags:-1] - z[lags:-1].mean()]
    for i in range(1, lags + 1):
        cols.append(d[lags - i:len(d) - i])
    X = np.column_stack(cols)
    Y = d[lags:]
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ beta
    s2 = (resid @ resid) / (len(Y) - X.shape[1])
    XtX = np.linalg.inv(X.T @ X)
    t_stat = beta[1] / math.sqrt(s2 * XtX[1, 1])
    return float(t_stat)

diag = {
    "acf_dI": acf_series(dI, 8),
    "acf_ret": acf_series(ret, 8),
    "acf_inv": acf_series([r["total"] for r in rows], 8),
    "acf_px": acf_series([r["P_pub"] for r in rows], 8),
    "lb_dI_q8": ljung_box(dI, 8), "lb_ret_q8": ljung_box(ret, 8),
    "adf_dI_t": adf(dI), "adf_ret_t": adf(ret),
    "adf_inv_t": adf([r["total"] for r in rows]), "adf_px_t": adf([r["P_pub"] for r in rows]),
    "rho_dI": LL._acf1(dI), "rho_ret": LL._acf1(ret),
    "n_eff_dI_ret": n * (1 - LL._acf1(dI) * LL._acf1(ret)) / (1 + LL._acf1(dI) * LL._acf1(ret)),
    "ret_mean_pct": float(np.nanmean(ret) * 100), "ret_sd_pct": float(np.nanstd(ret, ddof=1) * 100),
    "dI_mean": float(np.nanmean(dI)), "dI_sd": float(np.nanstd(dI, ddof=1)),
}

# ---------------- 9) 发布时点诊断 ----------------
pub_hm = [r["pub_hm"] for r in rows]
pub_hours = [int(h[:2]) for h in pub_hm]
pub_weekdays = [datetime.date.fromisoformat(d).weekday() for d in dates]
from collections import Counter
pub_diag = {
    "hour_dist": dict(Counter(pub_hours)),
    "weekday_dist": dict(Counter(pub_weekdays)),
    "n_released_before_11": sum(1 for h in pub_hours if h < 11),
    "n_released_13_15": sum(1 for h in pub_hours if 13 <= h <= 15),
    "n_released_after_15": sum(1 for h in pub_hours if h > 15),
    "median_time": sorted(pub_hm)[len(pub_hm) // 2],
    "stat_is_pub_same_day": True,
}

# ---------------- 10) 汇总 ----------------
def clean(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            out[k] = None
        else:
            out[k] = v
    return out

result = {
    "meta": {
        "a_name": "甲醇港口库存周度变化 ΔI（万吨）",
        "b_name": "甲醇期货（MA主连）披露日周度收益率 r（%）",
        "start": dates[0], "end": dates[-1], "n": n, "maxlag": MAXLAG, "window": WINDOW,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    },
    "main_scan": [clean(d) for d in main_scan],
    "diag_same_day": [clean(d) for d in diag_same_day],
    "stages": stage_meta,
    "stage_scan": {k: [clean(d) for d in v] for k, v in stage_scan.items()},
    "years": year_meta,
    "year_scan": {k: [clean(d) for d in v] for k, v in year_scan.items()},
    "half_scan": {k: [clean(d) for d in v] for k, v in half_scan.items()},
    "variants": {k: [clean(d) for d in v] for k, v in variant_scan.items()},
    "shift_scan": {k: [clean(d) for d in v] for k, v in shift_scans.items()},
    "naive_scan": [clean(d) for d in naive_scan],
    "rolling": roll,
    "matrix": [clean(d) for d in matrix],
    "reg_single": clean(reg),
    "reg_both": clean(reg_both),
    "regressions": {k: {kk: clean(vv) for kk, vv in v.items()} for k, v in regressions.items()},
    "mto_series": [{"date": d, "mto": MTO.get(d)} for d in dates],
    "diag": clean(diag),
    "pub_diag": pub_diag,
}
json.dump(result, open(os.path.join(OUT, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------- 控制台速览 ----------------
print("n=%d  %s ~ %s" % (n, dates[0], dates[-1]))
print("\nLag 扫描（主设定）：lag  n  r  p  q_bh  q_bonf  t_nw  p_nw")
for d in main_scan:
    print("  %+3d %3d %+.3f %.3f %.3f %.3f %+.2f %.3f" % (d["lag"], d["n"], d["r"], d["p"], d["q_bh"], d["q_bonf"], d["t_nw"], d["p_nw"]))
print("\n变换稳健性（最强 |r| 的 lag）:")
for k, sc in variant_scan.items():
    b = LL.best_lags(sc, 1)[0]
    print("  %-40s lag=%+d r=%+.3f p=%.3f q_bh=%.3f n=%d" % (k, b["lag"], b["r"], b["p"], b["q_bh"], b["n"]))
print("\n阶段:")
for s in stage_meta:
    sc = stage_scan[s["code"]]
    b = LL.best_lags(sc, 1)[0]
    print("  %-34s n=%3d 最强 lag=%+d r=%+.3f p=%.3f q_bh=%.3f" % (s["code"], s["n_weeks"], b["lag"], b["r"], b["p"], b["q_bh"]))
print("\n逐年:")
for ym in year_meta:
    sc = year_scan[ym["year"]]
    b = LL.best_lags(sc, 1)[0]
    print("  %s n=%2d 最强 lag=%+d r=%+.3f p=%.3f q_bh=%.3f" % (ym["year"], ym["n_weeks"], b["lag"], b["r"], b["p"], b["q_bh"]))
print("\n伪造时点:")
for k, sc in shift_scans.items():
    b = LL.best_lags(sc, 1)[0]
    print("  shift=%+s 最强 lag=%+d r=%+.3f p=%.3f" % (k, b["lag"], b["r"], b["p"]))
print("\n诊断:", json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in diag.items() if not isinstance(v, list)}, ensure_ascii=False))
print("发布时点:", pub_diag)
print("回归(lag2):", result["reg_single"])
