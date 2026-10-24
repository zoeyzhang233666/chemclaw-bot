#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_all.py — 一条命令跑完：校验 → 派生 → HTML → Excel → 自检。

用法：
  python scripts/build_all.py examples/01-重质纯碱-华东
  python scripts/build_all.py examples/01-xxx --skip-checks   # 只出文件，不跑 QA

产出（都写在案例目录下）：
  build/data.json                      全部派生指标（可复核）
  out/<产品>-<地区>_客户市场价核验报告.html
  out/<产品>-<地区>_客户市场价核验.xlsx

任何一步失败都会中止并打印原因，不会产出「看起来完整」的坏文件。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(script, *args):
    cmd = [PY, os.path.join(HERE, script), *args]
    print(f"\n$ {script} {' '.join(args)}")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.rstrip().split("\n"):
        if line.strip():
            print("  " + line)
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case_dir", help="案例目录（含 research.json）")
    ap.add_argument("--skip-checks", action="store_true")
    a = ap.parse_args()

    case = os.path.abspath(a.case_dir)
    research = os.path.join(case, "research.json")
    if not os.path.isfile(research):
        print(f"[x] 找不到 {research}")
        return 2

    build = os.path.join(case, "build")
    out = os.path.join(case, "out")
    os.makedirs(build, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    data = os.path.join(build, "data.json")

    steps = []
    rc = run("validate.py", research)
    steps.append(("数据契约校验", rc))
    if rc != 0:
        print("\n[x] 数据契约未通过，停止构建。先把 research.json 补齐再出报告。")
        return 1

    rc = run("assemble.py", research, "--out", data)
    steps.append(("派生指标计算", rc))
    if rc != 0:
        return 1

    # 输出文件名：产品-地区_客户市场价核验
    import common as C
    d = C.load_json(data)
    # 文件名里的地区去掉「地区」后缀，避免出现「华东地区地区」这类重复
    region = str(d["meta"]["region"]).replace("地区", "").replace("区域", "")
    stem = f"{d['meta']['product']}-{region}_客户市场价核验"
    html = os.path.join(out, stem + "_报告.html")
    xlsx = os.path.join(out, stem + ".xlsx")

    rc = run("build_html.py", data, "--out", html)
    steps.append(("HTML 报告", rc))
    if rc != 0:
        return 1
    rc = run("build_xlsx.py", data, "--out", xlsx)
    steps.append(("Excel 工作簿", rc))
    if rc != 0:
        return 1

    if not a.skip_checks:
        rc = run("check_html.py", html, data)
        steps.append(("HTML 自检", rc))
        rc2 = run("check_xlsx.py", xlsx, data)
        steps.append(("Excel 自检", rc2))
        if rc != 0 or rc2 != 0:
            print("\n[x] 自检未通过，请修好后重跑。")
            return 1

    print("\n== build_all 完成")
    for name, rc in steps:
        print(f"   {'OK ' if rc == 0 else 'FAIL'}  {name}")
    print(f"\n   HTML : {html}  ({os.path.getsize(html)/1024:.0f} KB)")
    print(f"   Excel: {xlsx}  ({os.path.getsize(xlsx)/1024:.0f} KB)")
    print(f"   data : {data}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
