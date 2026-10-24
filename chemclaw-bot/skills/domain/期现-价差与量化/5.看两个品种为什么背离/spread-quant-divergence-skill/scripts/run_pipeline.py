# -*- coding: utf-8 -*-
"""
run_pipeline.py — 双品种背离诊断 一键流水线
=============================================
用法：
  python run_pipeline.py --a data/pp.csv --b data/lldpe.csv \
      --aname PP --bname LLDPE --out ./out

输入 CSV 至少两列：date, price（多余列忽略）。也可用 --acol/--bcol 指定列名。
输出：
  out/result.json      全部统计结果（供下游复用）
  out/analysis_table.csv  逐日合并表
  out/report.html      交互式单文件报告
  out/workbook.xlsx    13 表工作簿

本脚本只做**统计描述**，不含任何因果推断。基本面部分需人工按
references/04-双边基本面核查清单.md 填写，写入 narrative.json 后由 build 脚本合并。
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from spread_core import (DivergenceRule, beta_alpha, corr_bundle, detect_divergences,
                         log_return, ratio_series, spread_series, standardize, window_stats)


def load_pair(pa, pb, acol, bcol):
    a = pd.read_csv(pa)
    b = pd.read_csv(pb)
    a.columns = [c.strip() for c in a.columns]
    b.columns = [c.strip() for c in b.columns]
    ac = acol or ("date" if "date" in a.columns else a.columns[0])
    bc = bcol or ("date" if "date" in b.columns else b.columns[0])
    av = [c for c in a.columns if c not in (ac, "date")][0]
    bv = [c for c in b.columns if c not in (bc, "date")][0]
    A = a[[ac, av]].copy(); A.columns = ["date", "A"]
    B = b[[bc, bv]].copy(); B.columns = ["date", "B"]
    for d in (A, B):
        d["date"] = pd.to_datetime(d["date"], errors="coerce")
        d.dropna(subset=["date"], inplace=True)
        d.drop_duplicates("date", keep="last", inplace=True)
    m = A.merge(B, on="date", how="inner").sort_values("date").reset_index(drop=True)
    m = m[(m.A > 0) & (m.B > 0)].reset_index(drop=True)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="A 品种 CSV")
    ap.add_argument("--b", required=True, help="B 品种 CSV")
    ap.add_argument("--acol"), ap.add_argument("--bcol")
    ap.add_argument("--aname", default="A")
    ap.add_argument("--bname", default="B")
    ap.add_argument("--out", default="./out")
    ap.add_argument("--start", default=None, help="可选：起始日期 YYYY-MM-DD")
    ap.add_argument("--end", default=None)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    m = load_pair(args.a, args.b, args.acol, args.bcol)
    if args.start:
        m = m[m.date >= pd.Timestamp(args.start)]
    if args.end:
        m = m[m.date <= pd.Timestamp(args.end)]
    m = m.reset_index(drop=True)
    if len(m) < 30:
        raise SystemExit(f"对齐后样本仅 {len(m)} 条，不足以做统计（需 >=30）")

    A, B = m.A, m.B
    m["A_n"] = standardize(A)
    m["B_n"] = standardize(B)
    m["spread"] = spread_series(A, B)
    m["ratio"] = ratio_series(A, B)
    m["r_a"] = log_return(A)
    m["r_b"] = log_return(B)

    cb = corr_bundle(A, B, m.r_a, m.r_b)
    res = {
        "meta": {
            "a_name": args.aname, "b_name": args.bname,
            "end_date": m.date.max().strftime("%Y-%m-%d"),
            "window": {"start": m.date.min().strftime("%Y-%m-%d"),
                       "end": m.date.max().strftime("%Y-%m-%d"), "n": len(m),
                       "label": f'{m.date.min():%Y-%m-%d} → {m.date.max():%Y-%m-%d}'},
            "disclaimer": "仅统计描述；相关性变化不等于因果。",
        },
        "series": {"dates": m.date.dt.strftime("%Y-%m-%d").tolist(),
                   "A": A.round(2).tolist(), "B": B.round(2).tolist()},
        "standardized": {"dates": m.date.dt.strftime("%Y-%m-%d").tolist(),
                         "A_n": m.A_n.round(2).tolist(), "B_n": m.B_n.round(2).tolist(),
                         "spread": m.spread.round(2).tolist(), "ratio": m.ratio.round(4).tolist()},
        "corr_full": cb,
        "stats": window_stats(A, B),
        "beta": beta_alpha(A, B),
    }

    rc = {}
    for w in (20, 60, 120):
        if len(m) < w + 2:
            continue
        rl = A.rolling(w).corr(B)
        rr = m.r_a.rolling(w).corr(m.r_b)
        rc[f"w{w}"] = {"dates": m.date.dt.strftime("%Y-%m-%d").tolist(),
                       "level": [None if pd.isna(v) else round(float(v), 4) for v in rl],
                       "ret": [None if pd.isna(v) else round(float(v), 4) for v in rr],
                       "band_ret": round(1.96 / math.sqrt(w - 3), 4)}
    res["rolling_corr"] = rc

    segs, rules = {}, []
    for ind in ("spread", "ratio"):
        for w in (20, 60):
            if len(m) < w * 2:
                continue
            r = DivergenceRule(indicator=ind, z_window=w, z_entry=1.5, z_exit=0.5, min_periods=5)
            s = detect_divergences(A, B, m.date, r)
            segs[f"{ind}_{w}"] = s
            rules.append({"indicator": ind, "z_window": w, "z_entry": 1.5,
                          "z_exit": 0.5, "min_periods": 5, "n_segments": len(s)})
    res["divergences"], res["rules"] = segs, rules

    wz = DivergenceRule(indicator="spread", z_window=20)
    mu = m.spread.rolling(wz.z_window, min_periods=max(5, wz.z_window // 2)).mean()
    sd = m.spread.rolling(wz.z_window, min_periods=max(5, wz.z_window // 2)).std()
    z = (m.spread - mu) / sd.replace(0, np.nan)
    res["z20"] = [None if pd.isna(v) else round(float(v), 3) for v in z]

    yr = []
    for y, g in m.groupby(m.date.dt.year):
        if len(g) < 30:
            continue
        yr.append({"year": int(y), "n": len(g),
                   "pp_ret": round(float(g.A.iloc[-1] / g.A.iloc[0] - 1) * 100, 2),
                   "l_ret": round(float(g.B.iloc[-1] / g.B.iloc[0] - 1) * 100, 2),
                   "level_corr": round(float(g.A.corr(g.B)), 3),
                   "ret_corr": round(float(g.r_a.corr(g.r_b)), 3),
                   "spread_avg": round(float(g.spread.mean()), 2),
                   "ratio_avg": round(float(g.ratio.mean()), 4)})
    res["by_year"] = yr

    # 逐日表
    t = m[["date", "A", "B", "A_n", "B_n", "spread", "ratio", "r_a", "r_b"]].copy()
    t["z20"] = z.values
    t["rc20_level"] = A.rolling(20).corr(B).values
    t["rc20_ret"] = m.r_a.rolling(20).corr(m.r_b).values
    t["rc60_ret"] = m.r_a.rolling(60).corr(m.r_b).values
    t.to_csv(os.path.join(args.out, "analysis_table.csv"), index=False,
             encoding="utf-8-sig", date_format="%Y-%m-%d")
    json.dump(res, open(os.path.join(args.out, "result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"[pipeline] {args.aname} vs {args.bname}: {len(m)} 个共同交易日 "
          f"({m.date.min():%Y-%m-%d} → {m.date.max():%Y-%m-%d})")
    print(f"[pipeline] 水平相关 {cb['level_pearson']:.4f} | 收益率相关 {cb['ret_pearson']:.4f}")
    print(f"[pipeline] 背离段数 " +
          ", ".join(f"{k}={len(v)}" for k, v in segs.items()))
    print(f"[pipeline] 结果已写入 {args.out}")
    print("[next] 按 references/04 填写 narrative.json，再运行 build_html.py / build_xlsx.py")


if __name__ == "__main__":
    main()
