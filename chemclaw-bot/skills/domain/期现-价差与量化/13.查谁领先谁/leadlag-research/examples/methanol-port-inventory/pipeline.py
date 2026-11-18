# -*- coding: utf-8 -*-
"""
pipeline.py — 领先滞后研究端到端流程模板

复用方法：只改下面 CONFIG 区的路径与列名，其余无需改动。

输入要求（最关键的约定）：
  - 低位指标 A（如周度库存）：必须含「统计期」与「实际公布时间」两列
  - 高位指标 B（如期货日线）：必须含「日期」「收盘价」两列
  - 时间均为交易所时区（默认北京时间）；公布时刻决定 P_before 的取法

输出：
  build/result.json   全部分析结果（供 HTML / Excel 使用）
  build/sample.json   对齐后的研究样本

依赖：仅 numpy + scipy（见 leadlag.py）
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_kernel():
    """在自身目录、包根 scripts/、以及向上两级中查找 leadlag.py，便于本文件被复制到任意子目录。"""
    cands = [HERE, os.path.join(HERE, "..", "scripts"),
             os.path.join(HERE, "..", "..", "scripts"),
             os.path.join(HERE, ".."), os.path.join(HERE, "..", "..")]
    for c in cands:
        c = os.path.abspath(c)
        if os.path.isfile(os.path.join(c, "leadlag.py")):
            return c
    raise SystemExit("找不到 leadlag.py：请将 scripts/leadlag.py 放在 pipeline.py 同级或 ../scripts/ 下")


sys.path.insert(0, _find_kernel())
import leadlag as LL          # noqa: E402

# ============================ CONFIG 区 ============================
A_PATH = os.path.join(HERE, "data", "indicator_a.csv")   # 低位指标
B_PATH = os.path.join(HERE, "data", "indicator_b.csv")   # 高位指标
A_DATE_COL, A_PUB_COL, A_VAL_COL = "stat_date", "pub_time", "value"
B_DATE_COL, B_CLOSE_COL = "date", "close"
MAX_LAG = int(os.environ.get("MAXLAG", "12"))
ROLL_WINDOW = 26
# 市场阶段：按价格/库存路径客观切分；起止日与依据都要能写进报告
STAGES = [
    ("S1", "2024-10-23", "2025-03-31", "阶段一：按价格路径客观切分"),
    ("S2", "2025-04-01", "2025-09-30", "阶段二"),
    ("S3", "2025-10-01", "2026-03-31", "阶段三"),
    ("S4", "2026-04-01", "2026-10-14", "阶段四"),
]
# ==================================================================


def load_csv(p):
    import csv
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def adf_t(z):
    """ADF 含常数项的 t 统计量（5% 临界值约 -2.86）。非平稳则 t > -2.86。"""
    z = np.asarray([v for v in z if v is not None], float)
    z = z[~np.isnan(z)]
    d = np.diff(z)
    lags = 1
    X = np.column_stack([np.ones(len(d) - lags), z[lags:-1] - z.mean()]
                        + [d[lags - 1 - i:-1 - i] for i in range(lags)])
    Y = d[lags:]
    try:
        beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
        resid = Y - X @ beta
        s2 = (resid @ resid) / (len(Y) - X.shape[1])
        se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
        return float(beta[1] / se)
    except Exception:
        return None


def ljung_box(z, k=8):
    """Ljung-Box Q 统计量与 p 值（检验自相关）。"""
    from scipy import stats
    z = np.asarray([v for v in z if v is not None], float)
    z = z[~np.isnan(z)]
    n = len(z)
    zc = z - z.mean()
    den = float(zc @ zc)
    if den <= 0 or n <= k + 2:
        return [None, None]
    q = 0.0
    for i in range(1, k + 1):
        rk = float(zc[i:] @ zc[:-i]) / den
        q += rk * rk / (n - i)
    q *= n * (n + 2)
    return [float(q), float(1 - stats.chi2.cdf(q, k))]


def build_sample(a_rows, b_rows):
    """按 A 的真实公布时点对齐 B，构造无前视偏差的研究样本。"""
    bmap = {r[B_DATE_COL]: float(r[B_CLOSE_COL]) for r in b_rows}
    bdates = sorted(bmap)
    rows, prev_a = [], None
    for r in a_rows:
        stat = r[A_DATE_COL]
        pub = (r[A_PUB_COL] or "")[:19].replace("T", " ")
        val = float(r[A_VAL_COL])
        before = [d for d in bdates if d < stat]      # 公布前最后一个交易日
        if not before:
            continue
        p_prev = bmap[before[-1]]
        p_pub = bmap.get(stat, p_prev)                # 当日无交易则沿用前值
        dA = None if prev_a is None else val - prev_a
        dA_pct = None if not prev_a else (val - prev_a) / prev_a * 100
        rows.append({
            "stat": stat, "pub": pub, "pub_hm": pub[11:16], "A": val,
            "dA": dA, "dA_pct": dA_pct,
            "P_prev": p_prev, "P_pub": p_pub,
            "ret": float(np.log(p_pub / p_prev) * 100),
            "dA_float": None,
        })
        prev_a = val
    return rows


def main():
    bdir = os.path.join(HERE, "build")
    os.makedirs(bdir, exist_ok=True)
    rows = build_sample(load_csv(A_PATH), load_csv(B_PATH))
    n = len(rows)
    dates = [r["stat"] for r in rows]
    A = [r["dA"] for r in rows]
    B = [r["ret"] for r in rows]

    M = {"n": n, "start": dates[0], "end": dates[-1], "maxlag": MAX_LAG,
         "a_name": "指标A（低位，周度）", "b_name": "指标B（高位，收益）"}
    out = {"meta": M}

    # ---- 1. 主 Lag 扫描：全部 Lag，逐个报 n / r / p / NW / 多重检验 ----
    out["main_scan"] = LL.lag_scan(A, B, MAX_LAG)

    # ---- 2. 分段与逐年：各自独立做完整扫描 + 独立 FDR ----
    groups = [(s[0], [s[1] <= d <= s[2] for d in dates]) for s in STAGES]
    out["stage_scan"] = LL.split_scan(A, B, MAX_LAG, groups)
    years = sorted({d[:4] for d in dates})
    ygroups = [(y, [d[:4] == y for d in dates]) for y in years]
    out["year_scan"] = LL.split_scan(A, B, MAX_LAG, ygroups)
    out["years"] = [{"year": y, "n_weeks": sum(1 for d in dates if d[:4] == y)} for y in years]
    out["stages"] = [{"code": s[0], "start": s[1], "end": s[2],
                      "n_weeks": sum(1 for d in dates if s[1] <= d <= s[2]),
                      "note": s[3]} for s in STAGES]

    # ---- 3. 滚动相关 ----
    out["rolling"] = {str(k): LL.rolling_corr(A, B, k, ROLL_WINDOW) for k in (2, 1, 0, -1, -2)}

    # ---- 4. 安慰剂：伪造发布时点（提前/延后 s 期）----
    out["shift_scan"] = {str(s): LL.fake_release_scan(A, B, MAX_LAG, [s])
                         for s in (-2, -1, 0, 1, 2)}

    # ---- 5. 诊断 ----
    out["diag"] = {
        "adf_dA": adf_t(A), "adf_ret": adf_t(B),
        "rho_dA": LL._acf1(A), "rho_ret": LL._acf1(B),
        "lb_dA_q8": ljung_box(A, 8), "lb_ret_q8": ljung_box(B, 8),
    }

    jdump = lambda o, p: json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    jdump(out, os.path.join(bdir, "result.json"))
    jdump({"rows": rows}, os.path.join(bdir, "sample.json"))

    # ---- 6. 摘要：必须直说「有几个 Lag 通过多重检验」----
    sc = out["main_scan"]
    best = min(sc, key=lambda d: d["p"] if d["p"] is not None else 1)
    n_sig = sum(1 for d in sc if (d["q_bh"] or 1) < 0.05)
    print(f"n={n}  {dates[0]} ~ {dates[-1]}   Lag ∈ [{-MAX_LAG}, {MAX_LAG}]")
    print(f"最小未校正 p = {best['p']:.4f} @ Lag={best['lag']:+d}   FDR q = {best['q_bh']:.3f}")
    print(f"通过 FDR 校正的 Lag 数：{n_sig} / {len(sc)}")
    print("结论：" + ("存在候选领先关系，需稳定性复核" if n_sig else "未发现稳健领先关系"))


if __name__ == "__main__":
    main()
