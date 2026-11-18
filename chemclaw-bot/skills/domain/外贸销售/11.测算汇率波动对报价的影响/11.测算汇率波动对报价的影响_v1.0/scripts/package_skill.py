# -*- coding: utf-8 -*-
"""package_skill.py —— 把 fx-risk 打包成可交付的 ZIP（技能目录结构）

用法:
    python scripts/package_skill.py --out "D:\\...\\11.测算汇率波动对报价的影响\\xxx.zip"
    python scripts/package_skill.py --out <zip> --dry-run     # 只列清单不打包

打包内容（保持技能目录形态）：
    SKILL.md
    README.md
    references/*.md
    examples/**（含 case.json、README.md、build/ 成品、shots/ 截图）
    scripts/**（含 templates/、assets/）
    data/safe_mid_raw.json          SAFE 原始数据留档（可回溯）
    build/fx_series.json            汇率序列
排除：__pycache__、.pyc、临时脚本（下划线开头）、旧日志。
"""
import argparse
import fnmatch
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "node_modules"}
EXCLUDE_FILES = ["*.pyc", "*.pyo", "_*.py", "_*.cjs", "*.tmp", "*.log", "*.bak"]


def is_excluded(rel_posix):
    parts = rel_posix.split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    name = parts[-1]
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_FILES)


def collect():
    items = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            if is_excluded(rel):
                continue
            # 跳过根目录下的临时探针 HTML
            if rel.startswith("_") :
                continue
            items.append((full, rel))
    items.sort(key=lambda x: x[1])
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prefix", default="11.测算汇率波动对报价的影响")
    a = ap.parse_args()

    items = collect()
    total = sum(os.path.getsize(f) for f, _ in items)
    print(f"将打包 {len(items)} 个文件，合计 {total / 1024 / 1024:.2f} MB\n")
    for _, rel in items:
        print("  ", rel)

    if a.dry_run:
        return 0

    out_path = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for full, rel in items:
            z.write(full, f"{a.prefix}/{rel}")
    size = os.path.getsize(out_path)
    print(f"\n✓ 写出 {out_path}  ({size / 1024 / 1024:.2f} MB)")

    # 完整性自检
    with zipfile.ZipFile(out_path) as z:
        bad = z.testzip()
        if bad:
            print(f"✗ ZIP 校验失败: {bad}")
            return 1
        names = z.namelist()
    need = ["SKILL.md", "README.md", "references/formulas.md",
            "examples/01-export-soda-ash-usd/case.json",
            "scripts/run_case.py", "scripts/build_xlsx.py"]
    miss = [n for n in need if f"{a.prefix}/{n}" not in names]
    if miss:
        print(f"✗ 缺少关键文件: {miss}")
        return 1
    htmls = [n for n in names if n.endswith(".html")]
    xlsxs = [n for n in names if n.endswith(".xlsx")]
    pngs = [n for n in names if n.endswith(".png")]
    print(f"✓ 校验通过：{len(names)} 个条目；HTML {len(htmls)} 个、Excel {len(xlsxs)} 个、截图 {len(pngs)} 张")
    return 0


if __name__ == "__main__":
    sys.exit(main())
