# -*- coding: utf-8 -*-
"""
pack_zip.py —— 打包 Skill 为可分发 ZIP
========================================
只打包运行必需文件：SKILL.md / references / examples / scripts /
以及案例数据与已生成的交付物（可选 --with-output）。
排除缓存中间件（*.pkl、__pycache__）与临时文件。

用法：
    python scripts/pack_zip.py                       # 默认输出到 dist/
    python scripts/pack_zip.py --with-output         # 附带 out/ 下的成品
    python scripts/pack_zip.py --out D:/xxx.zip
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "查库存季节性"

INCLUDE_DIRS = ["references", "examples", "scripts", "data"]
INCLUDE_FILES = ["SKILL.md"]
EXCLUDE_NAMES = {"__pycache__", ".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".pkl", ".tmp", ".log"}
EXCLUDE_PREFIX = (".", "~$", "_")


def wanted(p: Path, with_output: bool) -> bool:
    rel = p.relative_to(ROOT)
    parts = set(rel.parts)
    if parts & EXCLUDE_NAMES:
        return False
    if p.suffix.lower() in EXCLUDE_SUFFIX:
        return False
    if p.name.startswith(EXCLUDE_PREFIX):
        return False
    top = rel.parts[0]
    if top == "dist":
        return False
    if top == "out":
        return with_output
    return top in INCLUDE_DIRS or rel.name in INCLUDE_FILES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--with-output", action="store_true", help="把 out/ 下的报告与工作簿也打包")
    args = ap.parse_args()

    out = Path(args.out) if args.out else ROOT / "dist" / f"{SKILL_NAME}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    files = [p for p in ROOT.rglob("*") if p.is_file() and wanted(p, args.with_output)]
    files.sort(key=lambda p: str(p))

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            rel = p.relative_to(ROOT)
            z.write(p, arcname=str(Path(SKILL_NAME) / rel))

    total = out.stat().st_size / 1024 / 1024
    print(f"wrote {out}  ({len(files)} files, {total:.2f} MB)")
    for p in files:
        print("  +", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
