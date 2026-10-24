#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把整个 skill 目录打成 ZIP（跨 Agent 分发用）。

用法:
    python pack_skill.py [--skill-dir .] [--out overseas-inquiry-kyc.zip] [--with-example-outputs]

规则：
  - 顶层目录名固定为 overseas-inquiry-kyc/，解压后可整目录放进 skills/
  - 排除 __pycache__ / *.pyc / .DS_Store / 临时文件
  - 默认排除示例产物（体积大且可重建）；--with-example-outputs 才带上
  - 打包后逐条校验：必须包含 SKILL.md、references/、examples/、templates、脚本
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile

if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT_NAME = "overseas-inquiry-kyc"
SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "node_modules", ".pytest_cache"}
SKIP_EXT = {".pyc", ".pyo", ".tmp", ".log", ".swp"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}

REQUIRED = [
    "SKILL.md",
    "README.md",
    "AGENTS.md",
    "LICENSE",
    "CHANGELOG.md",
    "VERSION",
    "requirements.txt",
    "references/",
    "examples/README.md",
    "scripts/build_all.py",
    "scripts/build_html.py",
    "scripts/build_xlsx.py",
    "scripts/validate.py",
    "scripts/selfcheck.py",
    "scripts/pack_skill.py",
    "scripts/_common.py",
    "scripts/templates/report.html",
    "scripts/templates/style.css",
    "scripts/templates/app.js",
]


def collect(skill_dir, with_outputs):
    for root, dirs, files in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = os.path.relpath(root, skill_dir).replace("\\", "/")
        if rel_root == ".":
            rel_root = ""
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext in SKIP_EXT or f in SKIP_FILES or f.startswith("~$"):
                continue
            rel = f"{rel_root}/{f}" if rel_root else f
            # 示例产物：默认排除（可由 build_all.py 重建）
            if not with_outputs and re_label(rel).startswith("examples/") and (
                    rel.endswith(".html") or rel.endswith(".xlsx")):
                continue
            if rel.endswith(".zip"):
                continue
            yield rel, os.path.join(root, f)


def re_label(rel):
    return rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--out", default="")
    ap.add_argument("--with-example-outputs", action="store_true")
    a = ap.parse_args()

    skill_dir = os.path.abspath(a.skill_dir)
    out = a.out or os.path.join(os.path.dirname(skill_dir), f"{ROOT_NAME}.zip")
    version = "0.0.0"
    vp = os.path.join(skill_dir, "VERSION")
    if os.path.exists(vp):
        version = open(vp, encoding="utf-8").read().strip()

    files = list(collect(skill_dir, a.with_example_outputs))
    if not files:
        raise SystemExit("没有可打包的文件")

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, path in files:
            z.write(path, f"{ROOT_NAME}/{rel}")

    # 校验
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        bad = z.testzip()
    missing = [r for r in REQUIRED if not (r.endswith("/")
                                           and any(nm.startswith(f"{ROOT_NAME}/{r}") for nm in names)
                                           or f"{ROOT_NAME}/{r}" in names)]
    print(f"ZIP   {out}")
    print(f"版本  v{version}")
    print(f"文件  {len(names)} 个，{os.path.getsize(out) / 1024:.1f} KB")
    print(f"压缩校验 {bad or 'OK'}")
    if missing:
        print(f"[ERROR] 缺少必需条目：{missing}")
        return 1
    print("必需条目齐备：SKILL.md / README / AGENTS / references/ / examples/ / scripts / templates")
    print(f"解压后顶层目录：{ROOT_NAME}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
