# -*- coding: utf-8 -*-
"""event_study.py — 信号触发前后基差/期货的平均路径（event-time study）。

为什么需要它：均值差检验只回答"信号组和对照组事后 10 日的平均变化是否不同"，
但它无法回答最关键的前视问题——"差异是不是在信号出现之前就已经存在了"。
事件研究把 T0 设为 0，画出 T−20 … T+20 的累积变化：
  * 若 T0 之前（pre）两条路径已经分离 → 差异不是信号带来的，是选择效应/趋势延续；
  * 若 T0 之后（post）才分离 → 才谈得上"信号后走强"。

输出 build/event_study.json：
  { windows: [-20..20], basis: {signal:[...], control:[...]}, fut: {...},
    pre_post: {signal: {pre_mean, post_mean}, control: {...}}, n: {...} }

用法：
  python event_study.py --design build/research_design.formal.json \
      --inventory data/port_inventory_weekly.csv --price data/100ppi_sf.csv \
      --out build/event_study.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import study_engine as E  # noqa: E402


def avg_path(rows, market, key, lo=-20, hi=20):
    """对每一行按其 T0 对齐，返回每个事件时间点上的均值（缺失则跳过该点）。"""
    buckets = {k: [] for k in range(lo, hi + 1)}
    for r in rows:
        T0 = r["T0"]
        base = market.basis.get(T0) if key == "basis" else market.fut.get(T0)
        if base is None:
            continue
        for k in range(lo, hi + 1):
            Tk = market.shift(T0, k)
            if Tk is None:
                continue
            v = market.basis.get(Tk) if key == "basis" else market.fut.get(Tk)
            if v is None:
                continue
            buckets[k].append(v - base)
    return {k: (sum(v) / len(v) if v else None) for k, v in buckets.items()}, \
           {k: len(v) for k, v in buckets.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default="build/research_design.formal.json")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--price", required=True)
    ap.add_argument("--minute", default="")
    ap.add_argument("--out", default="build/event_study.json")
    a = ap.parse_args()
    design = E.load_design(a.design)
    market = E.Market(a.price, a.minute or None)
    inv = E.read_csv(a.inventory)
    rows, skip = E.build_panel(inv, market, design)
    sig = [r for r in rows if r["signal"]]
    ctl = [r for r in rows if not r["signal"]]

    res = {"meta": {"rows": len(rows), "n_signal": len(sig), "n_control": len(ctl),
                    "skipped": skip,
                    "note": "样本不足时曲线仅供参考，不构成结论；pre 与 post 对比用于识别选择效应。"}}
    for key in ("basis", "fut"):
        for label, group in (("signal", sig), ("control", ctl)):
            path, cnt = avg_path(group, market, key)
            res[f"{key}_{label}"] = path
            res[f"{key}_{label}_n"] = cnt
    # pre（−20…−1）与 post（+1…+10 / +20）的平均
    pp = {}
    for label, group in (("signal", sig), ("control", ctl)):
        path, _ = avg_path(group, market, "basis")
        def m(rng):
            v = [path[k] for k in rng if path.get(k) is not None]
            return sum(v) / len(v) if v else None
        pp[label] = {"pre_mean": m(range(-20, 0)), "post_mean_1_10": m(range(1, 11)),
                     "post_mean_11_20": m(range(11, 21)), "n": len(group)}
    res["pre_post"] = pp
    json.dump(res, open(a.out, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
    print(json.dumps({"n_signal": len(sig), "n_control": len(ctl), "pre_post": pp},
                     ensure_ascii=False, indent=1)[:1200])
    print("->", a.out)


if __name__ == "__main__":
    main()
