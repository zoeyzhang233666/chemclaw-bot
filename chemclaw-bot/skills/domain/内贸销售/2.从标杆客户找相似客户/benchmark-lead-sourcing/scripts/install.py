#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py —— 把本技能包安装到各 agent 的技能目录，或打包成可搬运 zip

用法
  python install.py                          # 等价 --target all
  python install.py --target claude          # ~/.claude/skills/benchmark-lead-sourcing
  python install.py --target dsh             # ~/.agents/skills/benchmark-lead-sourcing
  python install.py --target /path/to/skills # 自定义技能目录（装到 <path>/benchmark-lead-sourcing）
  python install.py --target all --no-examples   # 不复制 examples（包更小）
  python install.py --pack benchmark-lead-sourcing.zip
"""
import argparse
import os
import shutil
import sys
import zipfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
NAME = os.path.basename(PKG)
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "*.zip")


def copy_to(dest_root, with_examples=True):
    os.makedirs(dest_root, exist_ok=True)
    dest = os.path.join(dest_root, NAME)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    if with_examples:
        shutil.copytree(PKG, dest, ignore=IGNORE)
    else:
        os.makedirs(dest)
        for item in ("SKILL.md", "AGENTS.md", "README.md", "requirements.txt"):
            src = os.path.join(PKG, item)
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(dest, item))
        for sub in ("scripts", "references", "templates"):
            src = os.path.join(PKG, sub)
            if os.path.exists(src):
                shutil.copytree(src, os.path.join(dest, sub), ignore=IGNORE)
    return dest


def pack(zip_path, with_examples=True):
    zip_path = os.path.abspath(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PKG):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            if not with_examples and os.path.basename(root) == "examples":
                continue
            for f in files:
                if f.endswith((".pyc", ".zip")):
                    continue
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, os.path.dirname(PKG)))
    size = os.path.getsize(zip_path) / 1024
    print(f"OK 已打包 -> {zip_path}（{size:.0f} KB）")
    return zip_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="all",
                    help="all | claude | dsh | codex | <自定义技能目录>")
    ap.add_argument("--no-examples", action="store_true", help="不复制 examples")
    ap.add_argument("--pack", default="", help="生成 zip 包而不安装")
    args = ap.parse_args()
    we = not args.no_examples

    if args.pack:
        return 0 if pack(args.pack, we) else 1

    home = os.path.expanduser("~")
    targets = {
        "claude": os.path.join(home, ".claude", "skills"),
        "dsh": os.path.join(home, ".agents", "skills"),
        "codex": os.path.join(home, ".codex", "skills"),
    }
    installed = []
    if args.target == "all":
        for k in ("claude", "dsh"):
            installed.append(copy_to(targets[k], we))
    elif args.target in targets:
        installed.append(copy_to(targets[args.target], we))
    else:
        installed.append(copy_to(os.path.abspath(args.target), we))

    for p in installed:
        print(f"OK 已安装 -> {p}")
    print("\n接下来：")
    print("  1) 重启 agent（Claude Code / DSH 会读取 SKILL.md 的 frontmatter 自动注册技能）")
    print("  2) 依赖：pip install -r requirements.txt（仅出 Excel 需要 openpyxl）")
    print("  3) 自检：跑一遍 examples/soda-ash-huadong 的 "
          "merge_leads.py → build_workbook.py → make_html_report.py")
    print("  4) Codex / 其他读 AGENTS.md 的 agent：把包内 AGENTS.md 追加到项目 AGENTS.md，"
          "或在其中加一行指向 SKILL.md 的指针")
    return 0


if __name__ == "__main__":
    sys.exit(main())
