# -*- coding: utf-8 -*-
"""只校验 input.json，不生成文件。"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import check_doc, load_doc  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="校验 input.json")
    ap.add_argument("input")
    ap.add_argument("--strict", action="store_true", help="warning 也算失败")
    a = ap.parse_args()

    doc = load_doc(a.input)
    errors, warnings = check_doc(doc)
    for w in warnings:
        print("[warn] " + w)
    for err in errors:
        print("[error] " + err)

    ncase = len(doc.get("cases", []))
    nev = sum(len(c.get("direct", [])) + len(c.get("indirect", [])) + len(c.get("excluded", []))
              for c in doc.get("cases", []))
    print("\n[%s] %d 个案例 / %d 条证据 / %d 项材料 / %d 条来源"
          % ("pass" if not errors else "fail", ncase, nev,
             len(doc.get("materials", [])), len(doc.get("sources", []))))
    if errors:
        return 1
    if a.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
