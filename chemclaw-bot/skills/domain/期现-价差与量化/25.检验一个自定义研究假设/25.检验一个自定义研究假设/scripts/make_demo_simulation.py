# -*- coding: utf-8 -*-
"""make_demo_simulation.py — 生成【明确标记为模拟】的演示数据，用来验证整套流程。

铁律
----
  * 每一行都带 data_status="SIMULATED"；页面/工作簿/结果里再标记一次。
  * 机制（DEMO-ONLY，写进 meta 便于审计）：
      库存 I_t = 88 + 季节项 + 0.6 × 上周冲击 + 本周冲击（冲击 ±0.5、±1.5 万吨交替抬价）
      期货 P_t = 2500 − 6 × (I_t − 88) + 噪声
      基差 B_t = 40 − 7 × (I_t − 88) + 噪声
    说明：在模拟世界里库存高↔现货紧，库存下行时基差整体走**弱**，与用户假设方向相反。
    但由于"连续两周下跌"多出现在库存回落到中枢附近，方向性信号被抵消，
    引擎通常得到"无显著差异"——这本身也是有用的演示：模拟数据显示，即使机制存在，
    定向假设在主窗口上也未必可识别。所有数字仍属 SIMULATED，不得作为结论。
    因此在模拟世界里「连续两周去库 → 期货走强 → 基差走弱」是构造出来的：
    主检验（基差走强）应当**不显著甚至反向**，这正是验证引擎"不被假设牵着走"的好用例。
  * 所有模拟运行的结果文件都写 data_status=SIMULATED，不得与真实结论混排。

Usage: python make_demo_simulation.py --weeks 208 --seed 20261020 --out data/demo_weekly.csv
"""
import argparse
import csv
import json
import math
import os
import random
import sys
from datetime import date, timedelta


def season(w):
    return 5.0 * math.sin(2 * math.pi * (w - 8) / 52.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=208)
    ap.add_argument("--start", default="2022-01-05")
    ap.add_argument("--seed", type=int, default=20261020)
    ap.add_argument("--out", default="data/demo_weekly.csv")
    ap.add_argument("--phi", type=float, default=0.80, help="库存 AR(1) 系数")
    ap.add_argument("--sigma", type=float, default=2.6, help="库存周度冲击（万吨）")
    ap.add_argument("--beta", type=float, default=6.0, help="库存偏离 1 万吨 → 期货价格反向变化（元/吨）")
    ap.add_argument("--basis-beta", type=float, default=7.0,
                    help="库存偏离 1 万吨 → 基差变化（元/吨）；正值表示库存下降时基差走弱")
    ap.add_argument("--basis-sd", type=float, default=4.0, help="基差噪声标准差")
    a = ap.parse_args()

    rng = random.Random(a.seed)
    W = a.weeks
    start = date.fromisoformat(a.start)
    inv, noise = [], 0.0
    dev = 0.0
    for i in range(W):
        wob = (start + timedelta(days=7 * i)).isocalendar()[1]
        shock = rng.choice([-0.5, 0.5, -1.5, 1.5]) + rng.gauss(0, 0.6)
        dev = 0.35 * dev + shock
        inv.append(round(88 + season(wob) + dev, 2))

    bn = 0.0
    rows = []
    for i in range(W):
        d = start + timedelta(days=7 * i)
        total = inv[i]
        offset = total - 88.0                       # 库存相对中枢的偏离
        pnoise = 0.4 * noise + rng.gauss(0, 18)
        noise = pnoise
        price = round(2500 - a.beta * offset + pnoise, 0)   # 库存低 → 价格高
        bn = 0.35 * bn + rng.gauss(0, a.basis_sd)
        basis = round(40 - a.basis_beta * offset + bn, 2)   # 库存低 → 基差低（走弱）
        east = round(total * 0.78, 2)
        south = round(total - east, 2)
        rows.append({
            "asof": d.isoformat(), "pub_ts": f"{d.isoformat()} 14:00",
            "total": total, "east": east, "south": south,
            "jiangsu": round(east * 0.72, 2), "zhejiang": round(east * 0.28, 2),
            "guangdong": round(south * 0.68, 2), "fujian": round(south * 0.32, 2),
            "spot": round(price + basis, 2), "near_fut": price, "near_basis": basis,
            "data_status": "SIMULATED", "url": "SIMULATED://no-source",
        })

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    meta = {"data_status": "SIMULATED", "generator": "make_demo_simulation.py",
            "seed": a.seed, "weeks": len(rows), "first": rows[0]["asof"], "last": rows[-1]["asof"],
            "params": {"inventory_decay": 0.35, "shock_set": [-1.5, -0.5, 0.5, 1.5],
                       "beta_price": a.beta, "basis_beta": a.basis_beta, "basis_sd": a.basis_sd},
            "mechanism": ("库存=季节+冲击驱动 AR(0.35)；期货=2500-beta×(库存-88)+噪声；"
                          "基差=40-basis_beta×(库存-88)+噪声。"
                          "注意：连续两周去库多发生在库存回落至中枢附近，因此主窗口上"
                          "『去库→基差走强』并不能被识别（演示结果通常不显著），"
                          "这正好说明模拟数据只能验证流程，不能当作结论。"),
            "warning": "全部数值由伪随机数生成，不代表任何真实市场；仅用于验证统计流程与页面渲染。"}
    json.dump(meta, open(os.path.splitext(a.out)[0] + ".meta.json", "w", encoding="utf-8-sig"),
              ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
