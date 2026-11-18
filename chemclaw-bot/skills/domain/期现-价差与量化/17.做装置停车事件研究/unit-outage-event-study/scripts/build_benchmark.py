# -*- coding: utf-8 -*-
"""build_benchmark.py — 用多个化工品主力合约构造“同等权化工期货指数”作为市场基准

为什么需要基准：
  “甲醇事件日之后涨了 3%”不等于“这件事让甲醇涨了 3%”。同期整个化工板块可能都在涨跌
  （成本端、宏观、地缘）。事件研究要做的是相对基准的异常收益：
      AR = R_target − (alpha + beta × R_benchmark)

基准构造（可复现、无外部依赖）：
  1. 对每个品种，用 build_prices 同样的规则重建主力连续（成交量最大 + 流动性门槛）；
  2. 把各品种主力日收益取通道内等权平均（只对“当日有交易”的品种求均值，
     缺失的品种不按 0 代入——那会低估板块波动）；
  3. 输出 date, close（指数化，起点=1000）, ret_pct, n_legs。

注意：这是一个“研究用自建基准”，不是交易所官方指数；报告中必须如实标注其成分与算法。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_prices as bp  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="包含各品种逐合约 JSON 的目录（<root>/<SYM>/*.json）")
    ap.add_argument("--legs", default="MA,L,PP,TA,EG,V")
    ap.add_argument("--out", required=True, help="输出 benchmark.csv 的路径")
    ap.add_argument("--min-volume", type=float, default=1000.0)
    ap.add_argument("--min-oi", type=float, default=5000.0)
    ap.add_argument("--min-ratio", type=float, default=0.02)
    args = ap.parse_args(argv)

    leg_rets: Dict[str, Dict[str, float]] = {}
    meta: List[dict] = []
    for sym in [s.strip().upper() for s in args.legs.split(",") if s.strip()]:
        d = os.path.join(args.root, sym)
        if not os.path.isdir(d):
            print(f"[skip] {sym}: 目录不存在")
            continue
        contracts = bp.load_contracts(d, sym)
        if not contracts:
            print(f"[skip] {sym}: 无合约数据")
            continue
        rows, _ = bp.build(contracts, args.min_volume, args.min_oi, args.min_ratio)
        rows = bp.add_adjusted(rows)
        rec: Dict[str, float] = {}
        for i in range(1, len(rows)):
            a, b = rows[i - 1], rows[i]
            if a["adj_close"] and b["adj_close"]:
                rec[b["date"]] = (b["adj_close"] / a["adj_close"] - 1) * 100
        leg_rets[sym] = rec
        meta.append({"symbol": sym, "contracts": len(contracts), "days": len(rows),
                     "start": rows[0]["date"], "end": rows[-1]["date"]})
        print(f"[leg] {sym}: {len(rows)} 天 {rows[0]['date']}~{rows[-1]['date']}")

    if not leg_rets:
        raise SystemExit("没有任何可用品种，无法构造基准")

    dates = sorted({d for rec in leg_rets.values() for d in rec})
    idx = 1000.0
    out_rows = []
    for d in dates:
        legs = [rec[d] for rec in leg_rets.values() if d in rec]
        if not legs:
            continue
        r = sum(legs) / len(legs)
        idx *= (1 + r / 100)
        out_rows.append({"date": d, "close": round(idx, 4), "ret_pct": round(r, 6), "n_legs": len(legs)})

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["date", "close", "ret_pct", "n_legs"])
        w.writeheader()
        w.writerows(out_rows)

    meta_path = os.path.splitext(args.out)[0] + "_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"index_type": "等权化工期货主力指数（研究用自建）",
                   "weighting": "等权，缺失腿按“不参与”处理（不当 0 代入）",
                   "base": 1000, "legs": meta,
                   "start": out_rows[0]["date"], "end": out_rows[-1]["date"],
                   "caveat": "自建基准，非交易所官方指数；成分与权重见本文件"},
                  f, ensure_ascii=False, indent=1)
    print(f"[OK] 基准 {len(out_rows)} 天 {out_rows[0]['date']}~{out_rows[-1]['date']} -> {args.out}")


if __name__ == "__main__":
    main()
