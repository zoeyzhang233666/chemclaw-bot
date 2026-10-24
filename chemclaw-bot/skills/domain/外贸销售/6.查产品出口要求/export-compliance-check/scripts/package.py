# -*- coding: utf-8 -*-
"""package.py — 把技能目录打包为可分发 ZIP

规则
----
- 只打白名单内容（SKILL/README/CHANGELOG/VERSION/references/scripts/examples/templates）
- 排除 __pycache__、*.pyc、preview/、office_checks.json 等中间产物
- 保留示例中的最终交付物（HTML/XLSX/case.json/checks.json）
- ZIP 内顶层目录名为技能名，便于直接解压使用

用法
----
python scripts/package.py [--root .] [--out dist/export-compliance-check-v1.0.0.zip]
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import zipfile
from pathlib import Path

INCLUDE_TOP = ["SKILL.md", "README.md", "CHANGELOG.md", "VERSION"]
INCLUDE_DIRS = ["references", "scripts", "examples", "templates"]

EXCLUDE_PATTERNS = [
    "__pycache__/*", "*.pyc", "*.pyo", ".DS_Store", "Thumbs.db",
    "preview/*", "preview",
    "*.tmp", "*.log", "~$*",
]

# 示例目录中允许的中间产物（保留，作为证据）
KEEP_IN_EXAMPLES = ["preview/interaction.json"]


def should_skip(rel: str) -> bool:
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat.rstrip("/*") + "/*") and pat.endswith("/*"):
            return True
    return False


def collect(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_TOP:
        p = root / name
        if p.exists():
            files.append(p)
    for d in INCLUDE_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, pat) for pat in EXCLUDE_PATTERNS):
                continue
            if "__pycache__" in rel:
                continue
            files.append(p)
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None)
    ap.add_argument("--name", default="export-compliance-check")
    ap.add_argument("--version", default=None)
    a = ap.parse_args(argv)

    root = Path(a.root).resolve()
    version = a.version or (root / "VERSION").read_text(encoding="utf-8").strip()
    out = Path(a.out) if a.out else root / "dist" / f"{a.name}-v{version}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    files = collect(root)
    total = sum(f.stat().st_size for f in files)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files:
            arc = f"{a.name}/{f.relative_to(root).as_posix()}"
            z.write(f, arc)

    print(json.dumps({
        "zip": str(out),
        "version": version,
        "files": len(files),
        "raw_bytes": total,
        "zip_bytes": out.stat().st_size,
        "entries": sorted(zipfile.ZipFile(out).namelist())[:5] + ["..."],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
