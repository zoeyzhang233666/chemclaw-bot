#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command build: validate data.json → Excel + self-contained HTML.

Usage:
  python build_all.py data.json outdir [--prefix 产品名]

Outputs (Chinese filenames are fine):
  <prefix>_第二供应源备选池_对比工作簿_<asof>.xlsx
  <prefix>_第二供应源备选池_对比工作台_<asof>.html
  build_report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime

import common
import validate
import build_html
import build_xlsx


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("outdir")
    ap.add_argument("--prefix", default="")
    a = ap.parse_args()

    raw = common.load(a.data)
    D = common.normalize(raw)
    errors, warnings = validate.check(D)
    for w in warnings:
        print("[WARN ]", w)
    if errors:
        for e in errors:
            print("[ERROR]", e)
        sys.exit("数据校验未通过，未生成文件。")

    M = D["meta"]
    os.makedirs(a.outdir, exist_ok=True)
    prefix = common.safe_name(a.prefix or M.get("product_short") or M.get("product") or "化工品")
    asof = common.safe_name(M.get("asof") or datetime.now().strftime("%Y-%m-%d"))
    xlsx_name = f"{prefix}_第二供应源备选池_对比工作簿_{asof}.xlsx"
    html_name = f"{prefix}_第二供应源备选池_对比工作台_{asof}.html"
    xlsx_path = os.path.join(a.outdir, xlsx_name)
    html_path = os.path.join(a.outdir, html_name)

    build_xlsx.build(a.data, xlsx_path)
    build_html.build(a.data, html_path, xlsx_name)
    report = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "data": os.path.abspath(a.data),
        "asof": M.get("asof"),
        "product": M.get("product"),
        "counts": common.counts(D),
        "outputs": [
            {"file": os.path.basename(html_path), "bytes": os.path.getsize(html_path), "sha256": sha(html_path)},
            {"file": os.path.basename(xlsx_path), "bytes": os.path.getsize(xlsx_path), "sha256": sha(xlsx_path)},
        ],
        "warnings": warnings,
    }
    with open(os.path.join(a.outdir, "build_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"OK  HTML  {html_path}  {os.path.getsize(html_path)/1024:.1f} KB")
    print(f"OK  XLSX  {xlsx_path}  {os.path.getsize(xlsx_path)/1024:.1f} KB")
    print(f"OK  report {os.path.join(a.outdir, 'build_report.json')}")


if __name__ == "__main__":
    main()
