# -*- coding: utf-8 -*-
"""
run_all.py —— 一键跑完整流程
============================
步骤：
  1) （可选）抓取原始数据  fetch_data.py
  2) 计算引擎            basis_core.py   → research_data.json + basis_daily.csv
  3) 压缩为报告数据      report_data.py  → report_data.json
  4) 生成交互报告        build_html.py   → 报告.html（单文件自包含）
  5) 生成 Excel          build_xlsx.py   → 数据表.xlsx（13 表，含真公式）
  6) 自检                tests/test_statistics.py

用法（在 skill 根目录）：
  python scripts/run_all.py --case examples/methanol-east-china           # 用已有原始数据
  python scripts/run_all.py --case examples/methanol-east-china --fetch   # 先抓数据（需联网）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(script, args, cwd=None):
    cmd = [sys.executable, os.path.join(HERE, script)] + args
    print("\n>>> " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd or ROOT)
    if r.returncode != 0:
        raise SystemExit("步骤失败: %s (exit %d)" % (script, r.returncode))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="examples/methanol-east-china")
    ap.add_argument("--fetch", action="store_true", help="先从网络抓取原始数据")
    ap.add_argument("--html-name", default="报告.html")
    ap.add_argument("--xlsx-name", default="数据表.xlsx")
    a = ap.parse_args()

    case = os.path.abspath(os.path.join(ROOT, a.case))
    raw = os.path.join(case, "raw")
    out = os.path.join(case, "out")
    os.makedirs(out, exist_ok=True)

    if a.fetch:
        run("fetch_data.py", ["--raw", raw])

    run("basis_core.py", ["--raw", raw, "--out", out])
    run("report_data.py", ["--data", os.path.join(out, "research_data.json"),
                           "--raw", raw, "--out", os.path.join(out, "report_data.json")])
    html = os.path.join(out, a.html_name)
    xlsx = os.path.join(out, a.xlsx_name)
    run("build_html.py", ["--data", os.path.join(out, "report_data.json"),
                          "--template", os.path.join(ROOT, "templates", "report_template.html"),
                          "--out", html])
    run("build_xlsx.py", ["--data", os.path.join(out, "report_data.json"), "--out", xlsx])

    print("\n>>> 自检")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "test_statistics.py"),
                        "--out", out, "--xlsx", xlsx, "--html", html], cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit("自检未通过")
    print("\n全部完成：\n  %s\n  %s" % (html, xlsx))


if __name__ == "__main__":
    main()
