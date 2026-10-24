# -*- coding: utf-8 -*-
"""把本 skill 打成 zip（UTF-8 文件名标志位正确，跨平台解压不乱码）。

用法：python scripts/pack_skill.py [-o out.zip]
默认输出到 skill 目录的上一级：chem-supplier-verification-skill.zip
"""
import argparse
import os
import zipfile

SKIP_DIRS = {"__pycache__", ".git", ".idea"}
NAME = "chem-supplier-verification"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.dirname(here)
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=os.path.join(os.path.dirname(src), NAME + "-skill.zip"))
    a = ap.parse_args()

    if os.path.exists(a.out):
        os.remove(a.out)

    n = 0
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in sorted(files):
                if fn.endswith(".pyc") or fn.endswith(".zip"):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, src).replace(os.sep, "/")
                z.write(full, NAME + "/" + rel)
                n += 1

    print("[ok] %s: %d files, %.0f KB" % (a.out, n, os.path.getsize(a.out) / 1024))
    with zipfile.ZipFile(a.out) as z:
        bad = [i.filename for i in z.infolist()
               if any(ord(ch) > 127 for ch in i.filename) and not (i.flag_bits & 0x800)]
        print("[%s] 非 ASCII 文件名缺少 UTF-8 标志位: %d" % ("ok" if not bad else "error", len(bad)))


if __name__ == "__main__":
    main()
