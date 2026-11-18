#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按模拟采购清单，自动生成项目数据骨架（物料行来自解析结果，供应商/证据/链路需人工调研补全）。

用法:
    python scripts/make_project.py examples/purchase-lists/northeast-china-plant/purchase_list_simulated.xlsx \
        --out examples/northeast-china-batch/project.json

生成后请补齐 suppliers / evidence / links / actions，并运行 validate_project.py。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_common  # noqa: E402
import lib_ingest  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list_file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="采购清单批量寻源")
    ap.add_argument("--buyer", default="")
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--header-row", type=int, default=None)
    args = ap.parse_args()

    assets = lib_common.load_assets()
    proj = {"list": {"path": os.path.abspath(args.list_file), "sheet": args.sheet, "header_row": args.header_row}}
    res = lib_ingest.normalize_list(proj, lib_common.MaterialsDict(assets["materials"]), assets["field_map"], assets["rules"])

    items = []
    for it in res["items"]:
        rec = {k: it.get(k) for k in (
            "code", "raw_name", "name", "en", "aliases", "cas", "form", "spec", "purity", "unit", "unit_raw",
            "qty", "qty_annual", "packing", "delivery", "application", "supplier", "hazard", "hazard_ref",
            "status", "issues", "notes")}
        items.append(rec)

    out = {
        "meta": {"title": args.title, "buyer": args.buyer, "as_of": lib_common.shanghai_now().strftime("%Y-%m-%d"),
                 "sources_scope": ["上市公司定期报告（巨潮/上交所）", "政府监管文件", "企业官网", "交易所公告"]},
        "list": {"source_file": os.path.basename(args.list_file), "sheet": res["sheet"], "header_row": res["header_row"],
                 "simulated": True, "note": "由 make_project.py 生成，需要人工确认不可自动识别的字段"},
        "items": items,
        "ambiguities": res["ambiguities"],
        "suppliers": [],
        "evidence": [],
        "links": [],
        "actions": [],
        "gaps": [],
        "references": [],
    }
    lib_common.write_json(args.out, out)
    print(f"OK items={len(items)} ambiguities={len(res['ambiguities'])} -> {args.out}")
    for a in res["ambiguities"]:
        print("  ", a["id"], a["level"], a["row"], "|", a["question"])
    print("未映射列:", res["parse_notes"])


if __name__ == "__main__":
    main()
