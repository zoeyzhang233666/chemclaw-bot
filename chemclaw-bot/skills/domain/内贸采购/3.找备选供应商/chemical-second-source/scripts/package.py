#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package the skill directory as a portable zip with UTF-8 filename flags.

Usage:
  python scripts/package.py . ../dist/chemical-second-source-skill.zip
  python scripts/package.py . dist/chemical-second-source-skill.zip
"""
from __future__ import annotations

import argparse
import os
import zipfile

SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "dist", "out", "node_modules"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=".")
    ap.add_argument("out", nargs="?", default="dist/chemical-second-source-skill.zip")
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    out = os.path.abspath(a.out)
    root = os.path.basename(src.rstrip(os.sep)) or "chemical-second-source"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if os.path.exists(out):
        os.remove(out)
    count = 0
    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for walk_root, dirs, files in os.walk(src):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            for fn in sorted(files):
                if fn in SKIP_FILES or fn.endswith(".pyc"):
                    continue
                full = os.path.join(walk_root, fn)
                if os.path.abspath(full) == out:
                    continue
                rel = os.path.relpath(full, src).replace(os.sep, "/")
                arc = f"{root}/{rel}"
                zi = zipfile.ZipInfo(arc)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o644 << 16
                if any(ord(ch) > 127 for ch in arc):
                    zi.flag_bits |= 0x800
                with open(full, "rb") as f:
                    z.writestr(zi, f.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
                count += 1
                total += os.path.getsize(full)
    with zipfile.ZipFile(out) as z:
        bad = [i.filename for i in z.infolist() if any(ord(ch) > 127 for ch in i.filename) and not (i.flag_bits & 0x800)]
    print(f"OK  {out}  {count} files  {total/1024:.0f} KB raw  {os.path.getsize(out)/1024:.0f} KB zip")
    print(f"{'OK' if not bad else 'ERROR'}  UTF-8 filename flag: {len(bad)} missing")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
