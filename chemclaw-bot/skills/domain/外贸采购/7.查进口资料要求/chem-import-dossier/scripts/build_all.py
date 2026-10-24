#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_all.py — 一键构建：校验 → HTML → XLSX → 自检

用法：
    python scripts/build_all.py examples/h2o2-kr-30/data.json
    python scripts/build_all.py examples/h2o2-kr-30/data.json --outdir build/
退出码：0 全部通过；1 校验失败或自检失败
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(args, title):
    print(f"\n{'=' * 66}\n  {title}\n{'=' * 66}")
    r = subprocess.run([PY] + args, capture_output=False)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--outdir", default=None, help="默认与 data.json 同目录")
    ap.add_argument("--skip-check", action="store_true")
    a = ap.parse_args()

    data = os.path.abspath(a.data)
    if not os.path.exists(data):
        print(f"找不到 {data}")
        return 1
    outdir = a.outdir or os.path.dirname(data)
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(data))[0]
    html_out = os.path.join(outdir, "report.html" if stem == "data" else f"{stem}.report.html")
    xlsx_out = os.path.join(outdir, "dossier.xlsx")

    rc = run([os.path.join(HERE, "validate.py"), data], "① 硬纪律校验")
    if rc != 0:
        print("\n✗ 校验未通过，已中止（先修 data.json，再重新构建）")
        return 1

    rc = run([os.path.join(HERE, "render_html.py"), data, "-o", html_out], "② 渲染 HTML")
    if rc != 0:
        return 1
    rc = run([os.path.join(HERE, "render_xlsx.py"), data, "-o", xlsx_out], "③ 渲染 XLSX")
    if rc != 0:
        return 1

    if not a.skip_check:
        rc = run([os.path.join(HERE, "check_outputs.py"), html_out, xlsx_out], "④ 交付前自检")
        if rc != 0:
            print("\n✗ 自检未通过")
            return 1

    # 摘要
    with open(data, encoding="utf-8") as f:
        d = json.load(f)
    import imrules as R
    g = R.overall_grade(d)
    print(f"\n{'=' * 66}\n  构建完成\n{'=' * 66}")
    print(f"  HTML : {html_out}  ({os.path.getsize(html_out) / 1024:,.0f} KB)")
    print(f"  XLSX : {xlsx_out}  ({os.path.getsize(xlsx_out) / 1024:,.0f} KB)")
    print(f"  结论 : {g['grade']} · {g['grade_text']}")
    print(f"  单证 : 完备度 {g['doc_pct']}%   必须件缺失 {g['n_hard_missing']} 项")
    print(f"  闸门 : " + " / ".join(f"{x['code']}={x['status']}" for x in g["gates"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
