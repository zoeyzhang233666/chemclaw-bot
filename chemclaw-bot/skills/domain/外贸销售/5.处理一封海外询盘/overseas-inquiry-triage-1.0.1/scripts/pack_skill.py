# -*- coding: utf-8 -*-
"""pack_skill.py · 打成可发布的 ZIP

用法：
    python scripts/pack_skill.py                       # 打 ./（技能根）
    python scripts/pack_skill.py --root .. -o out.zip
    python scripts/pack_skill.py --no-examples         # 不带产物，只带 input/（体积小）

规则：
  - ZIP 内顶层目录名 = <技能名>-<版本>（如 overseas-inquiry-triage-1.0.0）
  - 文件名一律 UTF-8 + 通用标志位 0x800（Windows 资源管理器解压不乱码）
  - 排除 __pycache__ / *.pyc / .DS_Store / _test / 临时脚本 / 产物大文件（按 --no-examples）
  - 打包前自动跑 selfcheck.py --skill，FAIL 就不打包（--force 可跳过）
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(HERE, ".."))

SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "_test", "node_modules", ".pytest_cache"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
SKIP_PAT = re.compile(r"^(_patch\d*\.py|_t\d*\.py|_dbg\d*\.mjs|_check\.js|~\$.*)$")
# 示例里由脚本生成的产物（--no-examples 时不打）
GEN_PAT = re.compile(r"^(0[1-7][a-z]?_.*\.(json|md|html|xlsx|txt))$")


def version_of(root):
    p = os.path.join(root, "VERSION")
    if os.path.exists(p):
        return open(p, encoding="utf-8-sig").read().strip() or "0.0.0"
    return "0.0.0"


def skill_name(root):
    p = os.path.join(root, "SKILL.md")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8").read().split("\n")[:20]:
            if ln.startswith("name:"):
                return ln.split(":", 1)[1].strip()
    return os.path.basename(root)


def collect(root, no_examples):
    items = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        rel_base = os.path.relpath(base, root).replace("\\", "/")
        for f in sorted(files):
            if f in SKIP_FILES or SKIP_PAT.match(f):
                continue
            if no_examples and rel_base.startswith("examples/") and GEN_PAT.match(f):
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, root).replace("\\", "/")
            items.append((full, rel))
    return items


def write_zip(items, out, top):
    """手写 ZipInfo：文件名按 UTF-8 存，并置 0x800 通用标志位。"""
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for full, rel in items:
            arc = top + "/" + rel
            zi = zipfile.ZipInfo(arc, date_time=(2026, 10, 19, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                data = fh.read()
            # 文件名含非 ASCII → 置 UTF-8 标志位；纯 ASCII 不必置（保持兼容旧解压器）
            if any(ord(c) > 127 for c in arc):
                zi.flag_bits |= 0x800
            z.writestr(zi, data)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="打包技能 ZIP")
    ap.add_argument("--root", default=SKILL_ROOT)
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--no-examples", action="store_true", help="不打示例产物，只留 input/")
    ap.add_argument("--force", action="store_true", help="跳过 selfcheck")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    name, ver = skill_name(root), version_of(root)
    top = "%s-%s" % (name, ver)
    out = args.out or os.path.join(os.path.dirname(root), "%s-skill.zip" % name)

    if not args.force:
        r = subprocess.run([sys.executable, os.path.join(root, "scripts", "selfcheck.py"), "--skill", root],
                           capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        txt = (r.stdout or b"").decode("utf-8", "replace")
        print(txt)
        if r.returncode != 0:
            sys.stderr.write("[拒绝打包] selfcheck 未通过；修好再用 --force 跳过\n")
            return 1

    items = collect(root, args.no_examples)
    n = write_zip(items, out, top)
    size = os.path.getsize(out)
    print("[ok] %s" % out)
    print("     %s（%d 个文件，%.1f KB）" % (top + "/", n, size / 1024.0))
    # 自检：ZIP 能读、文件名不乱码
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
        names = z.namelist()
        cn = [x for x in names if any(ord(c) > 127 for c in x)]
        print("     ZIP 完整性：%s · 中文文件名 %d 个（UTF-8 标志位已置）"
              % ("OK" if bad is None else "损坏于 " + bad, len(cn)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
