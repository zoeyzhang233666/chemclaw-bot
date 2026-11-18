#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_data.py — 生成 DEMO 拟真数据（三地区重质纯碱周度价格，两种口径）

⚠️ 产出是 DEMO 拟真数据：按【已核实的真实价格骨架】与真实行业口径构造，
   用于演示全流程与所有交付物形态。**不是真实市场报价，不得用于交易、报价或对外引用。**
   拿到真实数据后，用 scripts/init_analysis.py 导入 CSV 重跑即可。

锚点全部来自已核实来源（见 config/project.json 的 sources）：
  · 2023-07-24 重碱现货低点 2175；2023-08-25 重碱均价 3023（百川）
  · 2023-09-01 华北重碱 3200 / 华东 3150 / 华中 3150 / 西北 3000
  · 2024-07-31 沙河纯碱现货均价 1900；2024-11 沙河重碱约 1500
  · 2024 年卓创重碱主流终端均价 1953（-29.6%）
  · 2025-06 末 华北 1350 / 华东 1300 / 华中 1300（隆众大区价）
  · 2025-07 沙河重碱低端 1190；重碱交割库 1260、送到沙河 1280
  · 2025-09-11 全国重碱主流 1279；2025-12-31 生意社重碱基准价 1225.71
  · 2025 沙河重碱年均价 1275；'2025 重碱区间 860—1450'

两种口径：
  DELIVERED（主口径，送到价）——三地区同为送到价，可直接相减
  EXW（对照口径，厂提出厂价）——= 送到价 − 该地区到消费地的内含运费

用法：
  python scripts/make_data.py --out-dir data --seed 20240101
"""
import argparse
import csv
import json
import os
import random
from datetime import date, timedelta

REGIONS = ["SD", "HB", "JS"]

# 全国重碱价格骨架（元/吨，含税，送到口径的全国中枢）
# 与已核实锚点对齐，DEMO 用。
ANCHORS = [
    ("2023-01-06", 2780.0),
    ("2023-02-17", 2760.0),
    ("2023-03-31", 2760.0),
    ("2023-04-28", 2350.0),
    ("2023-05-19", 2040.0),
    ("2023-06-16", 2050.0),
    ("2023-07-24", 2180.0),
    ("2023-07-28", 2280.0),
    ("2023-08-25", 3023.0),
    ("2023-09-01", 3160.0),
    ("2023-10-20", 2680.0),
    ("2023-11-10", 2540.0),
    ("2023-12-08", 2720.0),
    ("2023-12-29", 2620.0),
    ("2024-01-26", 2380.0),
    ("2024-02-23", 2220.0),
    ("2024-03-22", 2010.0),
    ("2024-04-19", 2020.0),
    ("2024-05-24", 2140.0),
    ("2024-06-21", 2140.0),
    ("2024-07-31", 1900.0),
    ("2024-08-16", 1860.0),
    ("2024-09-13", 1720.0),
    ("2024-09-27", 1660.0),
    ("2024-10-25", 1560.0),
    ("2024-11-15", 1500.0),
    ("2024-12-20", 1440.0),
    ("2025-01-17", 1440.0),
    ("2025-02-14", 1470.0),
    ("2025-03-14", 1470.0),
    ("2025-04-11", 1400.0),
    ("2025-05-09", 1410.0),
    ("2025-06-27", 1317.0),
    ("2025-07-18", 1230.0),
    ("2025-08-01", 1290.0),
    ("2025-08-29", 1260.0),
    ("2025-09-12", 1279.0),
    ("2025-10-24", 1410.0),
    ("2025-11-21", 1420.0),
    ("2025-12-26", 1340.0),
]

# 区域基准溢价（送到价口径，相对全国中枢）
BASE_PREMIUM_DELIVERED = {"SD": +22.0, "HB": -40.0, "JS": +18.0}

# 各区“送到价中含的内含运费”（元/吨）——仅用于生成 EXW 对照口径
# 山东：潍坊厂 → 潍坊/淄博下游，短途；河北：唐山厂 → 沙河到货；江苏：本地厂 → 连云港/徐州下游
EMBEDDED_FREIGHT = {"SD": 45.0, "HB": 72.0, "JS": 55.0}

# 区域冲击（相对全国中枢的叠加，元/吨）。正=该地区相对抬价。
SHOCKS = [
    ("2023-07-15", "2023-09-15", "HB", +35.0),   # 旺季华北最紧（3200 为华北高点）
    ("2023-07-15", "2023-09-15", "SD", +8.0),
    ("2023-07-15", "2023-09-15", "JS", -12.0),
    ("2024-03-01", "2024-06-30", "JS", +40.0),   # 江苏上半年检修，需外省调入
    ("2024-03-01", "2024-06-30", "SD", +6.0),
    ("2024-09-01", "2024-11-30", "HB", -50.0),   # 沙河玻璃冷修，河北需求走弱
    ("2024-10-01", "2024-12-20", "JS", +18.0),
    ("2025-02-01", "2025-04-30", "SD", +10.0),   # 春节运力紧张
    ("2025-02-01", "2025-04-30", "JS", -8.0),
    ("2025-06-01", "2025-08-31", "JS", +32.0),   # 光伏需求结构性变化，江苏集聚度高
    ("2025-06-01", "2025-08-31", "HB", -18.0),
    ("2025-09-01", "2025-12-31", "JS", +36.0),   # 连云港新厂达产前，本地仍偏紧
    ("2025-09-01", "2025-12-31", "SD", +12.0),
    ("2025-11-01", "2025-12-31", "HB", -22.0),   # 沙河燃煤线集中停产，上海需求下降
    ("2025-10-20", "2025-11-30", "SD", +6.0),
]


def interp_anchor(d: date) -> float:
    pts = [(date.fromisoformat(a), v) for a, v in ANCHORS]
    if d <= pts[0][0]:
        return pts[0][1]
    if d >= pts[-1][0]:
        return pts[-1][1]
    for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
        if d0 <= d <= d1:
            w = (d - d0).days / max(1, (d1 - d0).days)
            w = w * w * (3 - 2 * w)
            return v0 + (v1 - v0) * w
    return pts[-1][1]


def seasonal(d: date) -> float:
    return float({1: -4, 2: -2, 3: 8, 4: 10, 5: 9, 6: 2, 7: -3, 8: -5,
                  9: 7, 10: 8, 11: -3, 12: -6}.get(d.month, 0))


def shock_at(d: date, region: str) -> float:
    total = 0.0
    for s, e, r, delta in SHOCKS:
        if r == region and date.fromisoformat(s) <= d <= date.fromisoformat(e):
            total += delta
    return total


def weekly_dates(start: str, end: str):
    d = date.fromisoformat(start)
    out = []
    while d.weekday() != 4:      # 周五
        d += timedelta(days=1)
    endd = date.fromisoformat(end)
    while d <= endd:
        out.append(d)
        d += timedelta(days=7)
    return out


def build(seed: int):
    rng = random.Random(seed)
    dates = weekly_dates("2023-01-01", "2025-12-31")
    n = len(dates)

    noise = 0.0
    natv = []
    for d in dates:
        noise = 0.82 * noise + rng.gauss(0, 9.0)
        natv.append(interp_anchor(d) + seasonal(d) + noise)

    delivered = {}
    for r in REGIONS:
        dev = 0.0
        vals = []
        for i, d in enumerate(dates):
            target = shock_at(d, r)
            dev = dev + 0.22 * (target - dev) + rng.gauss(0, 4.2) * 0.6
            vals.append(natv[i] + BASE_PREMIUM_DELIVERED[r] + dev)
        delivered[r] = vals

    exw = {r: [delivered[r][i] - EMBEDDED_FREIGHT[r] for i in range(n)] for r in REGIONS}

    def materialize(src):
        rows = []
        for i, d in enumerate(dates):
            row = {"date": d.isoformat()}
            for r in REGIONS:
                row[r] = float(round(src[r][i] / 5.0) * 5)
            rows.append(row)
        return rows

    rows_d = materialize(delivered)
    rows_x = materialize(exw)

    # 缺口注入（模拟真实停报）：不插值，留空
    gap_spec = [("2023-10-20", "SD"), ("2024-02-09", "JS"),
                ("2024-12-20", "HB"), ("2025-05-02", "JS")]
    gaps = []
    for gd, gr in gap_spec:
        for row in rows_d:
            if row["date"] == gd and row[gr] is not None:
                gaps.append({"date": gd, "region": gr, "caliber": "DELIVERED", "old": row[gr]})
                row[gr] = None
    # 出厂价口径：另注入两个缺口，检验两套口径的对齐结果不同
    for gd, gr in [("2023-06-16", "HB"), ("2025-08-15", "SD")]:
        for row in rows_x:
            if row["date"] == gd and row[gr] is not None:
                gaps.append({"date": gd, "region": gr, "caliber": "EXW", "old": row[gr]})
                row[gr] = None
    return rows_d, rows_x, gaps


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["date"] + REGIONS)
        for r in rows:
            w.writerow([r["date"]] + ["" if r[k] is None else f"{r[k]:.0f}" for k in REGIONS])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--seed", type=int, default=20240101)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    rows_d, rows_x, gaps = build(a.seed)
    p_d = os.path.join(a.out_dir, "demo_soda_ash_dense_delivered_weekly.csv")
    p_x = os.path.join(a.out_dir, "demo_soda_ash_dense_exw_weekly.csv")
    write_csv(p_d, rows_d)
    write_csv(p_x, rows_x)

    meta = {
        "product": "重质纯碱",
        "spec": "GB/T 210-2022 II 类优等品，Na2CO3 >= 99.2%（干基）",
        "unit": "元/吨",
        "frequency": "weekly",
        "rows": len(rows_d),
        "start": rows_d[0]["date"],
        "end": rows_d[-1]["date"],
        "data_status": "DEMO",
        "seed": a.seed,
        "calibers": {
            "DELIVERED": {"file": os.path.basename(p_d), "desc": "送到价（主口径），含 13% 增值税、现汇"},
            "EXW": {"file": os.path.basename(p_x), "desc": "厂提出厂价（对照口径），含 13% 增值税、现汇",
                    "embedded_freight": EMBEDDED_FREIGHT},
        },
        "anchors_used": [{"date": d, "value": v} for d, v in ANCHORS],
        "injected_gaps": gaps,
        "note": "DEMO 拟真数据：锚点取自已核实的真实价格报道，中间路径为构造值。非真实报价，不得用于交易或对外引用。",
    }
    with open(os.path.join(a.out_dir, "demo_data_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[make_data] {p_d}  rows={len(rows_d)}  {meta['start']}~{meta['end']}")
    print(f"[make_data] {p_x}  (EXW 对照口径)")
    print(f"[make_data] 注入缺口: {[(g['date'], g['region'], g['caliber']) for g in gaps]}")


if __name__ == "__main__":
    main()
