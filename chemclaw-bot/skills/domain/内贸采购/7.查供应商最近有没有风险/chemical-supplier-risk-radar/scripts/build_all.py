# -*- coding: utf-8 -*-
"""Build both deliverables (Excel + self-contained HTML) from one data.json.

Usage:
    python build_all.py data.json --out out --name 纯碱-2026-10
    python build_all.py data.json --out out --name demo --pdf
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
PY = sys.executable


def run(script, *args):
    cmd = [PY, str(BASE / script), *map(str, args)]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", help="path to data.json")
    ap.add_argument("--out", default="out", help="output directory")
    ap.add_argument("--name", default=None, help="file stem; default = meta.title + period_tag")
    ap.add_argument("--pdf", action="store_true", help="also convert the xlsx to PDF if LibreOffice is available")
    args = ap.parse_args()

    data_path = Path(args.data).resolve()
    data = json.loads(data_path.read_text(encoding="utf-8"))
    meta = data["meta"]
    tag = meta.get("period_tag") or meta.get("query_date", "")[:7] or "report"
    name = args.name or f"{meta.get('title', meta.get('product', '供应商风险'))}_{tag}"
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    xlsx = out / f"{name}.xlsx"
    html = out / f"{name}.html"
    run("build_xlsx.py", data_path, xlsx)
    run("build_html.py", data_path, html)

    if args.pdf:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            print("! --pdf requested but LibreOffice/soffice was not found; skipped")
        else:
            print("+", soffice, "--headless --convert-to pdf", xlsx)
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out), str(xlsx)], check=True)

    print("\nDONE")
    print("html:", html)
    print("xlsx:", xlsx)
    print("next: python scripts/qa.py data.json <html> <xlsx>")


if __name__ == "__main__":
    main()
