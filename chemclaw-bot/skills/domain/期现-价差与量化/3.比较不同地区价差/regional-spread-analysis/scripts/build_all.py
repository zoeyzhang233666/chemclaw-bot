#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_all.py — 一条命令跑完全流程（导入 → 分析 → HTML → Excel → 双校验）

用法：
  # 用 DEMO 数据演示
  python scripts/build_all.py

  # 用自己的数据
  python scripts/build_all.py --prices my.csv
  python scripts/build_all.py --prices my.csv --csv-control my_exw.csv

  # 只重跑某一环
  python scripts/build_all.py --skip-check
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PY = sys.executable


def run(name, args, optional=False):
    print(f"\n{'='*66}\n▶ {name}\n{'='*66}")
    t0 = time.time()
    p = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if out:
        print(out)
    if err:
        print(err[-2000:], file=sys.stderr)
    dt = time.time() - t0
    ok = p.returncode == 0
    print(f"{'✅' if ok else '❌'} {name}  {dt:.1f}s  (exit {p.returncode})")
    if not ok and not optional:
        sys.exit(p.returncode)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", default=None, help="长表 CSV（date,region,price,caliber,unit,source,note）")
    ap.add_argument("--csv", default=None, help="已是宽表的主口径 CSV（跳过导入）")
    ap.add_argument("--csv-control", default=None, help="宽表对照口径 CSV")
    ap.add_argument("--caliber", default="DELIVERED")
    ap.add_argument("--caliber-control", default="EXW")
    ap.add_argument("--config", default="config/project.json")
    ap.add_argument("--events", default="config/events_fundamentals.json")
    ap.add_argument("--routes", default="config/routes.json")
    ap.add_argument("--align", default="weekly")
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--data-status", default=None, choices=[None, "REAL", "DEMO", "CLIENT"])
    ap.add_argument("--build-dir", default="build")
    ap.add_argument("--skip-check", action="store_true")
    a = ap.parse_args()

    bd = a.build_dir
    os.makedirs(bd, exist_ok=True)
    result = os.path.join(bd, "result.json")

    csv_main, csv_ctrl = a.csv, a.csv_control

    # ---- 1. 导入（可选）----
    if a.prices:
        run("导入用户数据", ["scripts/init_analysis.py", "--prices", a.prices,
                              "--config", a.config, "--out-dir", "data"])
        csv_main = os.path.join("data", f"prices_wide_{a.caliber.lower()}.csv")
        cand = os.path.join("data", f"prices_wide_{a.caliber_control.lower()}.csv")
        if os.path.exists(cand):
            csv_ctrl = cand
        print(f"  主口径宽表 → {csv_main}")
        if csv_ctrl:
            print(f"  对照口径宽表 → {csv_ctrl}")

    if not csv_main:
        csv_main = "data/demo_soda_ash_dense_delivered_weekly.csv"
        if not csv_ctrl:
            csv_ctrl = "data/demo_soda_ash_dense_exw_weekly.csv"
        print(f"\n未提供 --prices/--csv，使用 DEMO 数据：{csv_main}")

    status = a.data_status
    if status is None:
        status = "DEMO" if csv_main.startswith("data/demo_") else "CLIENT"

    # ---- 2. 分析 ----
    args = ["scripts/analyze.py", "--csv", csv_main, "--caliber", a.caliber,
            "--config", a.config, "--events", a.events, "--routes", a.routes,
            "--align", a.align, "--data-status", status, "--out", result]
    if csv_ctrl:
        args += ["--csv-control", csv_ctrl, "--caliber-control", a.caliber_control]
    if a.as_of:
        args += ["--as-of", a.as_of]
    run("主分析 → result.json", args)

    # ---- 3. 质检 ----
    run("数据质检", ["scripts/data_quality.py", "--result", result], optional=True)

    # ---- 4. HTML ----
    html = os.path.join(bd, "regional-spread-report.html")
    run("生成 HTML 报告", ["scripts/build_html.py", "--result", result, "--out", html])

    # ---- 5. Excel ----
    xlsx = os.path.join(bd, "workbook.xlsx")
    run("生成 Excel 工作簿", ["scripts/build_excel.py", "--result", result, "--out", xlsx])

    # ---- 6. 校验 ----
    html_ok = xlsx_ok = None
    if not a.skip_check:
        html_ok = run("HTML 浏览器校验", ["scripts/check_html.py", "--html", html, "--result", result],
                      optional=True)
        xlsx_ok = run("Excel 重算对账", ["scripts/verify_excel.py", "--xlsx", xlsx, "--result", result],
                      optional=True)

    # ---- 汇总 ----
    R = json.load(open(result, encoding="utf-8"))
    order = R["primary"]["region_order"]
    names = {r["id"]: r["name"] for r in R["meta"]["regions"]}
    print(f"\n{'='*66}\n📦 交付物\n{'='*66}")
    for f, label in ((html, "交互式 HTML 报告"), (xlsx, "Excel 工作簿（17 表）"),
                     (result, "分析结果 JSON")):
        if os.path.exists(f):
            print(f"  {label:22s} {f}   {os.path.getsize(f)/1024:.1f} KB")
    print(f"\n数据状态：{R['meta']['data_status']}")
    print("三地区最新价：")
    for r in order:
        ls = R["primary"]["level_stats"][r]
        print(f"  {names[r]:6s} {ls['current']:8.0f} 元/吨   1y 分位 {ls['pct_1y']}")
    print("价差（甲 − 乙）：")
    for p in R["primary"]["pairs"]:
        if p.get("n"):
            print(f"  {p['label']:14s} {p['current']:+8.0f}")
    if html_ok is not None:
        print(f"\n校验：HTML {'✅' if html_ok else '❌ 见上'} ｜ Excel {'✅' if xlsx_ok else '❌ 见上'}")
    print()


if __name__ == "__main__":
    main()
