# -*- coding: utf-8 -*-
"""
report_data.py —— 把引擎输出压缩成「报告可用」的紧凑数据
========================================================
引擎输出的 research_data.json 每行 84 个字段、2.7MB，不适合直接内嵌进 HTML。
本脚本把它裁剪成：
  meta / series（日度，紧凑数组）/ stats（全部统计）/ mapping / calendar / sources
并顺带算好「结论性事实」（conclusions），供报告与 Excel 复用。

用法：
  python report_data.py --data out/research_data.json --raw raw --out out/report_data.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

SERIES_FIELDS = [
    "date", "contract", "contract_month", "spot", "fut", "basis", "basis_ratio",
    "oi", "days_to_ltd", "basis_pct_lag", "n_hist", "group_lag", "regime",
    "point_in_time_known", "roll_day", "roll_new_next", "spread_next", "flags",
]
HORIZON_FIELDS = ["spot_ret", "fut_ret", "basis_ret", "basis_chg", "future_share",
                  "basis_pct_at", "group_at", "spot_ret_pit", "fut_ret_pit", "basis_ret_pit"]


def compact_series(rows):
    horizons = [5, 10, 20, 60, 120, 1]
    cols = list(SERIES_FIELDS)
    for h in horizons:
        for f in HORIZON_FIELDS:
            k = "%s_%d" % (f, h)
            if any(k in r for r in rows):
                cols.append(k)
    # 价格类字段保留全精度：基差率若先舍入到 6 位小数，
    # 再拿去算分位排名会制造“假并列”，使 Excel 复核与引擎差一位。
    exact = {"spot", "fut", "basis", "basis_ratio"}
    data = []
    for r in rows:
        data.append([r.get(c) if c in exact else _round(r.get(c)) for c in cols])
    return cols, data


def _round(v):
    if isinstance(v, float):
        return round(v, 6)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="out/research_data.json")
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--out", default="out/report_data.json")
    args = ap.parse_args()

    d = json.load(open(args.data, encoding="utf-8"))
    rows = d["series"]["main"]
    cols, data = compact_series(rows)
    out = {
        "meta": d["meta"],
        "stats": d["stats"],
        "mapping": d["mapping"],
        "calendar": d["calendar"],
        "bars": {"cols": cols, "rows": data},
    }
    # 现货来源样本
    spot_csv = os.path.join(args.raw, "spot_methanol_100ppi_benchmark.csv")
    if os.path.exists(spot_csv):
        import csv
        recs = list(csv.DictReader(open(spot_csv, encoding="utf-8-sig")))
        out["spot_samples"] = recs[:3] + recs[-2:]
        out["spot_meta"] = {"n": len(recs), "first": recs[0]["date"], "last": recs[-1]["date"]}
    for p in (os.path.join(args.raw, "_sources.json"),):
        if os.path.exists(p):
            out["fetch_meta"] = json.load(open(p, encoding="utf-8"))

    out["contracts_count"] = len(glob.glob(os.path.join(args.raw, "MA_MA*.json")))
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("[OK] %s  series=%d×%d  size=%.2fMB" % (
        args.out, len(data), len(cols), os.path.getsize(args.out) / 1048576))


if __name__ == "__main__":
    main()
