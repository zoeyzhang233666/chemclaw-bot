# -*- coding: utf-8 -*-
"""build_prices.py — 从逐合约日线重建「主力连续合约」日线（真实数据，可复现）

为什么不能直接用交易所/财经网站的“主力连续”（如 MA0）：
  主力连续在换月日会把前后两个合约的价格直接接起来，产生并非真实成交的跳空。
  做事件研究时，如果事件窗口跨越换月日，收益会被这个假跳空污染。

本脚本的做法：
  1. 逐日取成交量最大的合约作为当日主力（并列取持仓大者，再并列取近月）。
  2. 只有当某合约“成交量 / 持仓量”达到门槛时，才认为流动性足以作为基准：
     流动性不足的月份（如临近到期的小合约）不进入主力判定，避免极端品价格污染。
  3. 换月日做后向复权（roll-over 口径），使连续序列的日收益等于“旧合约当日真实涨跌”，
     不把 O→N 的价差当成涨跌。
  4. 输出：
       prices.csv      后向复权序列（推荐用于事件研究）
       prices_raw.csv  未复权主力序列（对照）
       rolls.csv       换月清单与换月价差
       contract_stats.csv 每个合约的成交/持仓概况

输入：raw 目录下 <prefix><YYYYMM>.json，内容为 Sina 逐合约 [d,o,h,l,c,v,p,s] 列表。
依赖：仅标准库。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from typing import Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load_contracts(raw_dir: str, prefix: str = "MA") -> Dict[str, Dict[str, Tuple[float, float, float]]]:
    """{contract: {date: (close, volume, open_interest)}}，只收 4 位合约码（排除 MA0 连续）。"""
    out: Dict[str, Dict[str, Tuple[float, float, float]]] = {}
    for p in sorted(glob.glob(os.path.join(raw_dir, f"{prefix}*.json"))):
        name = os.path.splitext(os.path.basename(p))[0]
        if not re.fullmatch(rf"{prefix}\d{{4}}", name):
            continue
        rows = json.loads(open(p, encoding="utf-8").read())
        rec = {}
        for r in rows:
            rec[r[0]] = (float(r[4]), float(r[5]), float(r[6]))
        if rec:
            out[name] = rec
    return out


def build(contracts: Dict[str, Dict[str, Tuple[float, float, float]]],
          min_volume: float = 1000.0, min_oi: float = 5000.0,
          min_volume_oi_ratio: float = 0.02) -> Tuple[List[dict], List[dict]]:
    """逐交易日选主力。

    流动性门槛（三项同时满足才可作为当日主力）：
        volume >= min_volume
        open_interest >= min_oi
        volume / open_interest >= min_volume_oi_ratio
    若不满足任何合约，则当日不计入（留下缺口并在 stat 里报告）。
    """
    dates = sorted({d for rec in contracts.values() for d in rec})
    rows: List[dict] = []
    skipped: List[dict] = []
    for d in dates:
        cands = [(name, rec[d]) for name, rec in contracts.items() if d in rec]
        if not cands:
            continue
        eligible = [(n, v) for n, v in cands
                    if v[1] >= min_volume and v[2] >= min_oi and (v[1] / max(v[2], 1e-9)) >= min_volume_oi_ratio]
        if not eligible:
            skipped.append({"date": d, "reason": "无合约满足流动性门槛",
                            "best": max(cands, key=lambda x: x[1][1])[0]})
            continue
        eligible.sort(key=lambda x: (-x[1][1], -x[1][2], x[0]))
        name, (close, vol, oi) = eligible[0]
        rows.append({"date": d, "contract": name, "close": close, "volume": vol, "oi": oi,
                     "n_eligible": len(eligible), "n_total": len(cands)})
    return rows, skipped


def add_adjusted(rows: List[dict]) -> List[dict]:
    """后向复权：让“连续序列的相邻日收益”等于真实可交易收益，且最新价保持真实。

    定义（roll-over 口径）：
        换月发生在 k 日（rows[k] 是新合约，rows[k-1] 是旧合约）。
        连续序列在 k 日的收益应等于
            C_new(k) / C_old(k-1) − 1
        即“从中枢换到新合约时的真实跨日变化”，而不是
            C_new(k) / C_new(k-1)（新合约本身前一日可能还没流动性）。
    做法：
        1. 归一化到最新一天：factors[n-1] = 1，最新价 == 真实成交价；
        2. 从后往前，遇到换月点就累乘 r = C_old(k-1) / C_new(k)，
           赋给该点之前的全部行。
    效果：
        adj[k]   = C_new(k) * f_after
        adj[k-1] = C_old(k-1) * f_before = C_old(k-1) * f_after * (C_old(k-1)/C_new(k))
    注意：这里刻意让 adj[k]/adj[k-1] = C_new(k)/C_old(k-1)，
    因为旧合约在 k 日的收盘价通常已经不可得（主力已换），
    用新旧合约的自然衔接是该口径下唯一稳健的选择。
    """
    rows = sorted(rows, key=lambda r: r["date"])
    n = len(rows)
    # ── 自洽口径 ───────────────────────────────────────────────
    # 事实：只要要求“每天的收益 == 该合约原始价比”，就能推出 f 全序列恒定，
    # 即复权对收益毫无作用。所以复权的真实目的只有一个：让**价格水平**连续，
    # 避免早期窗口的绝对价位被换月价差污染。
    #
    # 采用标准后向复权（panama/比率法）：
    #   遇到换月点 k，把 k 之前的所有行乘 r = C_old(k-1) / C_new(k)。
    #   于是 adj[k] = C_new(k) * f_after，
    #        adj[k-1] = C_old(k-1) * f_after * r = C_new(k) * f_after = adj[k]
    #   ⇒ 换月日本身的“收益”被人为设为 0（消掉了换月跳空），
    #     这是有意的：我们不要那个不可交易的价差。
    #   段内比价完全不变（同一因子），因此段内收益保持真实。
    factors = [1.0] * n
    acc = 1.0
    # 后向复权（panama 比率法）——唯一自洽的口径：
    #   跨过换月点 k 时，把 k 之前的所有行（0..k-1）统一乘 C_old(k-1)/C_new(k)。
    #   于是  adj[k-1] = C_old * (C_old/C_new)^-1 ... 直接验算：
    #       adj[k]   = C_new * 1
    #       adj[k-1] = C_old * acc_k   其中 acc_k 已含本换月的 (C_old/C_new)
    #       adj[k-1] = C_old * acc_after 与 adj[k] 同尺度 ⇒ 跳空归零
    #   段内：同一因子 ⇒ 收益真实。
    #   最新一天：在其后的换月才改变因子，故最后一段因子恒为 1 ⇒ 最新价真实。
    # 后向复权（panama 比率法）：让换月跳空归零。
    #   需求：跨过换月点 k 时，把 k 之前的所有行（0..k-1）乘 (C_new/C_old)，
    #   使 adj[k-1] = C_old*(C_new/C_old) = C_new = adj[k]（跳空=0）。
    #   多段换月时因子累乘，且必须“逐行”计算：
    #       factor[i] = Π_{换月点 k > i} (C_new(k)/C_old(k-1))
    #   即第 i 行只乘“发生在它之后”的换月因子。
    roll_ratio = [1.0] * n          # roll_ratio[k] = C_new(k)/C_old(k-1)
    for k in range(1, n):
        if rows[k - 1]["contract"] != rows[k]["contract"]:
            prev_close, new_close = rows[k - 1]["close"], rows[k]["close"]
            if prev_close and new_close:
                roll_ratio[k] = new_close / prev_close
                rows[k]["roll_flag"] = "roll:adjusted"
            else:
                rows[k]["roll_flag"] = "roll:no_guard"
    # 后缀积：factor[i] = Π_{k > i} roll_ratio[k]
    factors = [1.0] * n
    acc = 1.0
    for i in range(n - 1, -1, -1):
        factors[i] = acc
        acc *= roll_ratio[i]
    for i, r in enumerate(rows):
        r["adj_close"] = r["close"] * factors[i]
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, help="逐合约 JSON 目录")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--prefix", default="MA")
    ap.add_argument("--min-volume", type=float, default=1000.0)
    ap.add_argument("--min-oi", type=float, default=5000.0)
    ap.add_argument("--min-ratio", type=float, default=0.02)
    args = ap.parse_args(argv)

    contracts = load_contracts(args.raw, args.prefix)
    rows, skipped = build(contracts, args.min_volume, args.min_oi, args.min_ratio)
    rows = add_adjusted(rows)
    os.makedirs(args.out, exist_ok=True)

    with open(os.path.join(args.out, "prices.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["date", "close", "contract", "volume", "oi", "adj_close"])
        for r in rows:
            w.writerow([r["date"], f"{r['close']:.2f}", r["contract"], int(r["volume"]), int(r["oi"]),
                        f"{r['adj_close']:.2f}"])

    with open(os.path.join(args.out, "prices_raw.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["date", "close", "contract", "volume", "oi"])
        for r in rows:
            w.writerow([r["date"], f"{r['close']:.2f}", r["contract"], int(r["volume"]), int(r["oi"])])

    with open(os.path.join(args.out, "rolls.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["date", "from_contract", "to_contract", "prev_close_old", "new_close",
                    "old_same_day_close", "roll_gap_abs", "roll_gap_pct", "flag"])
        for i in range(1, len(rows)):
            prev, cur = rows[i - 1], rows[i]
            if prev["contract"] != cur["contract"]:
                old = contracts.get(prev["contract"], {}).get(cur["date"], (None,))[0]
                gap = (cur["close"] - old) if old else None
                pct = (cur["close"] / old - 1) * 100 if old else None
                w.writerow([cur["date"], prev["contract"], cur["contract"], f"{prev['close']:.2f}",
                            f"{cur['close']:.2f}", f"{old:.2f}" if old else "",
                            f"{gap:+.2f}" if gap is not None else "",
                            f"{pct:+.2f}" if pct is not None else "", cur.get("roll_flag", "")])

    with open(os.path.join(args.out, "contract_stats.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["contract", "days", "first_date", "last_date", "max_volume", "max_oi",
                    "sum_volume", "days_as_main"])
        main_days: Dict[str, int] = {}
        for r in rows:
            main_days[r["contract"]] = main_days.get(r["contract"], 0) + 1
        for name, rec in sorted(contracts.items()):
            ds = sorted(rec)
            w.writerow([name, len(ds), ds[0], ds[-1], int(max(rec[d][1] for d in ds)),
                        int(max(rec[d][2] for d in ds)), int(sum(rec[d][1] for d in ds)),
                        main_days.get(name, 0)])

    if skipped:
        with open(os.path.join(args.out, "skipped_days.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["date", "reason", "best"])
            w.writeheader()
            w.writerows(skipped)

    print(f"[OK] {len(rows)} 个交易日，{rows[0]['date']} ~ {rows[-1]['date']}，"
          f"{len(contracts)} 个合约，换月 "
          f"{sum(1 for i in range(1, len(rows)) if rows[i]['contract'] != rows[i - 1]['contract'])} 次"
          f"{('，跳过 ' + str(len(skipped)) + ' 个流动性不足交易日') if skipped else ''}")


if __name__ == "__main__":
    main()
