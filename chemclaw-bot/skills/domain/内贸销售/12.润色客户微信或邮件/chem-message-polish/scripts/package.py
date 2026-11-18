#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 skill 打包成一个可拷走的 zip（排除产物、缓存、旧包）。

用法:
  python scripts/package.py [--out chem-message-polish-skill.zip] [--with-outputs]
默认不含 examples/*/out（产物 100KB 上下，按需生成即可）。
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode"}
SKIP_EXT = {".pyc", ".pyo", ".zip", ".log"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(ROOT),
                                                  "chem-message-polish-skill.zip"))
    ap.add_argument("--with-outputs", action="store_true", help="连生成的 xlsx/html 一起打包")
    args = ap.parse_args(argv)

    count = 0
    if os.path.exists(args.out):
        os.remove(args.out)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            rel = os.path.relpath(base, ROOT)
            if not args.with_outputs and os.path.basename(base) == "out":
                continue
            for f in sorted(files):
                if os.path.splitext(f)[1].lower() in SKIP_EXT:
                    continue
                full = os.path.join(base, f)
                arc = os.path.normpath(os.path.join("chem-message-polish",
                                                    os.path.relpath(full, ROOT)))
                z.write(full, arc.replace(os.sep, "/"))
                count += 1
    size = os.path.getsize(args.out)
    print("已打包 %d 个文件 → %s（%.1f KB）" % (count, args.out, size / 1024.0))
    print("解压后直接放进目标 agent 的 skills 目录，或按 README 的四种方式挂载。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
