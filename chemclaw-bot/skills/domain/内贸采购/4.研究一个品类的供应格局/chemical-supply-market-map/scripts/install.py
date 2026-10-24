#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py —— 把本技能包装到各 agent 的技能目录，或打包成可搬运 zip

用法
  python scripts/install.py                          # 等价 --target all（claude + dsh）
  python scripts/install.py --target claude          # ~/.claude/skills/
  python scripts/install.py --target dsh             # ~/.agents/skills/
  python scripts/install.py --target codex           # ~/.codex/skills/（配合 AGENTS.md 指针）
  python scripts/install.py --target /path/to/skills # 自定义（chemclaw / workbuddy / 项目内）
  python scripts/install.py --target all --no-examples   # 不带 examples（包更小）
  python scripts/install.py --pack chem-map.zip          # 只打包不安装
  python scripts/install.py --list                       # 看默认路径
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
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "*.zip", "data_bundle.json",
                                "_recalc*.xlsx")
KEEP_FLAT = ("SKILL.md", "AGENTS.md", "README.md", "requirements.txt", "LICENSE")
KEEP_DIRS = ("scripts", "assets", "references", "templates")


def home():
    return os.path.expanduser("~")


def targets():
    return {
        "claude": os.path.join(home(), ".claude", "skills"),
        "dsh": os.path.join(home(), ".agents", "skills"),
        "codex": os.path.join(home(), ".codex", "skills"),
    }


def copy_to(dest_root, with_examples=True):
    os.makedirs(dest_root, exist_ok=True)
    dest = os.path.join(dest_root, NAME)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    if with_examples:
        shutil.copytree(PKG, dest, ignore=IGNORE)
    else:
        os.makedirs(dest)
        for item in KEEP_FLAT:
            src = os.path.join(PKG, item)
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(dest, item))
        for sub in KEEP_DIRS:
            src = os.path.join(PKG, sub)
            if os.path.exists(src):
                shutil.copytree(src, os.path.join(dest, sub), ignore=IGNORE)
    return dest


def pack(zip_path, with_examples=True):
    zip_path = os.path.abspath(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PKG):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            rel = os.path.relpath(root, PKG)
            if not with_examples and rel.split(os.sep)[0] == "examples":
                continue
            for f in sorted(files):
                if f.endswith((".pyc", ".zip")) or f.startswith("_recalc"):
                    continue
                full = os.path.join(root, f)
                zf.write(full, os.path.join(NAME, os.path.relpath(full, PKG)))
    size = os.path.getsize(zip_path) / 1024
    print(f"OK 已打包 -> {zip_path}（{size:.0f} KB）")
    return zip_path


def main():
    ap = argparse.ArgumentParser(description="安装 chemical-supply-market-map 技能包")
    ap.add_argument("--target", default="all",
                    help="all | claude | dsh | codex | <自定义技能目录>")
    ap.add_argument("--no-examples", action="store_true", help="不复制 examples")
    ap.add_argument("--pack", default="", help="生成 zip 包而不安装")
    ap.add_argument("--list", action="store_true", help="打印默认安装路径")
    args = ap.parse_args()
    we = not args.no_examples
    t = targets()

    if args.list:
        print(f"技能名：{NAME}")
        for k, v in t.items():
            print(f"  {k:8s} {os.path.join(v, NAME)}")
        print(f"  自定义   python scripts/install.py --target <目录>")
        return 0

    if args.pack:
        pack(args.pack, we)
        return 0

    installed = []
    if args.target == "all":
        for k in ("claude", "dsh"):
            installed.append(copy_to(t[k], we))
    elif args.target in t:
        installed.append(copy_to(t[args.target], we))
    else:
        installed.append(copy_to(os.path.abspath(args.target), we))

    for p in installed:
        print(f"OK 已安装 -> {p}")
    print("\n接下来：")
    print("  1) Claude Code / DSH：重启 agent，SKILL.md 的 frontmatter 会被自动注册")
    print("  2) Codex / WorkBuddy：在 AGENTS.md 里加一行指向 SKILL.md，或直接追加包内 AGENTS.md")
    print("  3) 依赖：pip install -r requirements.txt（仅 Excel 需要 openpyxl）")
    print("  4) 自检：python scripts/build_all.py --dir examples/soda-ash-cn-2026 "
          "&& python scripts/check_project.py --dir examples/soda-ash-cn-2026")
    return 0


if __name__ == "__main__":
    sys.exit(main())
