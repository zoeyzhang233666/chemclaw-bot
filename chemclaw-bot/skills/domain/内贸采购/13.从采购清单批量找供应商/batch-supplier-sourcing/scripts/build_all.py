#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键生成：Excel 报告 + 交互式 HTML 报告。

用法:
    python scripts/build_all.py examples/northeast-china-batch/project.json
    python scripts/build_all.py project.json --out-dir output --name 我的清单

输出:
    <out-dir>/<name>_批量寻源报告_YYYYMM.xlsx
    <out-dir>/<name>_批量寻源报告_YYYYMM.html
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lib_actions  # noqa: E402
import lib_common  # noqa: E402
import lib_model  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out-dir", default=None, help="默认 <project 所在目录>/output")
    ap.add_argument("--name", default=None, help="文件名前缀，默认取清单文件名")
    ap.add_argument("--no-excel", action="store_true")
    ap.add_argument("--no-html", action="store_true")
    args = ap.parse_args()

    project, assets = lib_model.load_project(args.project)
    calc = project["_calc"]

    # 自动生成询价/缺口/来源清单（若 project.json 未自带）
    actions, gaps, refs = lib_actions.build_actions(project)
    if not project.get("actions"):
        project["actions"] = actions
    if not project.get("gaps"):
        project["gaps"] = gaps
    if not project.get("references"):
        project["references"] = refs
    project["_meta"]["field_map"] = assets["field_map"]
    project["_hdr"] = project.get("hdr") or {}

    proj_dir = os.path.dirname(os.path.abspath(args.project))
    out_dir = args.out_dir or os.path.join(proj_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    ym = datetime.now().strftime("%Y%m")
    stem = args.name or os.path.splitext(os.path.basename(project["list"].get("source_file", "采购清单")))[0]
    stem = stem.replace("_simulated", "").replace("purchase_list", "").strip("_") or "批量寻源"
    base = os.path.join(out_dir, f"{stem}_批量寻源报告_{ym}")

    outs = []
    if not args.no_excel:
        from lib_excel import build_excel
        outs.append(build_excel(project, base + ".xlsx"))
    if not args.no_html:
        from lib_html import build_html
        outs.append(build_html(project, base + ".html"))

    print("生成完成：")
    for o in outs:
        print("  ", o, f"({os.path.getsize(o) / 1024:.0f} KB)")
    print(f"物料 {len(project['items'])} | 企业 {len(project['suppliers'])} | 证据 {len(project['evidence'])} | "
          f"关联 {len(project['links'])} | 多物料企业 {len(calc['multi'])} | 缺口 {len(project['gaps'])}")
    return outs


if __name__ == "__main__":
    main()
