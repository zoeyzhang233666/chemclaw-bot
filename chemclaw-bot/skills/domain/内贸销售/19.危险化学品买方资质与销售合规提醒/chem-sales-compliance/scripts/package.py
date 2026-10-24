# -*- coding: utf-8 -*-
"""把 skill 目录打包成可移植 zip。

用法:
    python scripts/package.py [--out ../../chem-sales-compliance-skill.zip]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if p.name in SKIP_FILES or p.suffix == ".pyc":
            continue
        yield p, rel


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "chem-sales-compliance-skill.zip"))
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    files = list(iter_files(ROOT))
    out.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out, "w", ZIP_DEFLATED, compresslevel=9) as z:
        for p, rel in files:
            z.write(p, Path(ROOT.name) / rel)
    size = out.stat().st_size / 1024
    print(f"OK  {out}  {len(files)} files  {size:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
