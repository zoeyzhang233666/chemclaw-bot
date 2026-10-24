#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command build: data.json -> HTML + XLSX + build_report.json.

Usage:
  python build_all.py data.json ./output [--name 纯碱_广东江门_竞争供给地图]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

import build_html
import build_xlsx
import common
import validate


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|]+', "_", str(s or "")).strip(" .")
    return s or "chemical-supply-map"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("outdir")
    ap.add_argument("--name", default="")
    a = ap.parse_args()

    raw = common.load_raw(a.data)
    D = common.build(raw)
    errors, warnings = validate.check(D)
    if errors:
        for x in errors:
            print("[ERROR]", x, file=sys.stderr)
        raise SystemExit("data validation failed; fix errors before building")
    for x in warnings:
        print("[WARN ]", x, file=sys.stderr)

    os.makedirs(a.outdir, exist_ok=True)
    M = D["meta"]
    base = a.name or f"{M.get('product_short') or M.get('product')}_{M.get('province')}{M.get('city')}_竞争供给地图"
    base = safe_name(base)
    html_path = os.path.join(a.outdir, base + ".html")
    xlsx_path = os.path.join(a.outdir, base + ".xlsx")
    xlsx_name = os.path.basename(xlsx_path)

    build_html.build(a.data, html_path, xlsx_name=xlsx_name)
    build_xlsx.build(a.data, xlsx_path)

    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "data": os.path.basename(a.data),
        "product": M.get("product"),
        "region": M.get("region"),
        "asof": M.get("asof"),
        "companies": D["total_companies"],
        "plants": D["total_plants"],
        "sample_capacity": D["total_cap"],
        "sample_output": D["total_out"],
        "sources": len(D.get("sources") or []),
        "conflicts": len(D.get("conflicts") or []),
        "gaps": len(D.get("gaps") or []),
        "boundaries": len(D.get("boundaries") or []),
        "projects": len(D.get("projects") or []),
        "prospects": len(D.get("prospects") or []),
        "warnings": warnings,
        "html": {"path": os.path.basename(html_path), "bytes": os.path.getsize(html_path), "sha256": sha(html_path)},
        "xlsx": {"path": os.path.basename(xlsx_path), "bytes": os.path.getsize(xlsx_path), "sha256": sha(xlsx_path)},
    }
    rp = os.path.join(a.outdir, "build_report.json")
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"OK  HTML  {html_path}  {report['html']['bytes']/1024/1024:.2f} MB")
    print(f"OK  XLSX  {xlsx_path}  {report['xlsx']['bytes']/1024:.1f} KB")
    print(f"OK  REPORT {rp}")
    print(f"    {D['total_companies']} companies / {D['total_plants']} plants / {D['total_cap']:,.0f} t sample / {len(D.get('sources') or [])} sources")


if __name__ == "__main__":
    main()
