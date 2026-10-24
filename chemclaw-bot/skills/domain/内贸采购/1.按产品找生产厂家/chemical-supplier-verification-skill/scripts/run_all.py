#!/usr/bin/env python3
"""Validate and build both Excel and HTML for a chemical supplier project.

Usage:
    python scripts/run_all.py path/to/project.json --outdir path/to/output
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_excel import build as build_excel  # noqa: E402
from build_html import build as build_html  # noqa: E402
from validate_project import load, validate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate + build Excel & HTML")
    ap.add_argument("project", type=Path)
    ap.add_argument("--outdir", type=Path, default=None)
    ap.add_argument("--strict", action="store_true", help="Treat validation warnings as errors")
    args = ap.parse_args()

    d = load(args.project)
    errors, warnings = validate(d, strict=args.strict)
    print(f"project: {args.project}")
    print(f"companies: {len(d.get('companies', []))}, plants: {sum(len(c.get('plants', [])) for c in d.get('companies', []))}, sources: {len(d.get('sources', []))}")
    print(f"validation: {len(errors)} errors, {len(warnings)} warnings")
    for e in errors:
        print(f"[ERROR] {e}")
    for w in warnings:
        print(f"[WARN]  {w}")
    if errors or (args.strict and warnings):
        print("RESULT: FAIL")
        return 1

    M = d["meta"]
    base = M.get("output_basename") or f"{M.get('product_short', '产品')}生产厂家核验池_{M.get('destination_short', '')}_{M.get('as_of', '')[:7].replace('-', '')}"
    outdir = args.outdir or (args.project.parent / "output")
    outdir.mkdir(parents=True, exist_ok=True)
    xlsx = outdir / f"{base}.xlsx"
    html = outdir / f"{base}.html"

    wb = build_excel(d)
    wb.save(xlsx)
    print(f"saved {xlsx}")

    build_html(d, html)
    print(f"saved {html}")
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
