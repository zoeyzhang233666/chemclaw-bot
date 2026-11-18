# -*- coding: utf-8 -*-
"""一条命令出全套：input.json → .xlsx + .html"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import VERDICT_META, check_doc, load_doc  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="供应商真伪核验：生成 Excel + HTML")
    ap.add_argument("input", help="input.json 路径")
    ap.add_argument("-o", "--outdir", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--strict", action="store_true", help="把 warning 也当失败")
    ap.add_argument("--html-only", action="store_true", help="只出 HTML（无 openpyxl 时可用）")
    args = ap.parse_args()

    doc = load_doc(args.input)
    errors, warnings = check_doc(doc)
    for w in warnings:
        print("[warn] " + w)
    if errors:
        for err in errors:
            print("[error] " + err)
        print("\n[abort] 数据未通过校验，先修 input.json（见 references/schema.md）")
        return 2
    if args.strict and warnings:
        print("\n[abort] --strict：存在 warning，未通过")
        return 2

    os.makedirs(args.outdir, exist_ok=True)
    meta = doc["meta"]
    print("case: %s | %s | %s" % (meta.get("title"), meta.get("product"), meta.get("as_of")))

    made = []
    if not args.html_only:
        try:
            from build_xlsx import build as build_xlsx
        except ImportError:
            print("[warn] 没有 openpyxl，跳过 Excel：pip install openpyxl")
        else:
            made.append(build_xlsx(doc, args.outdir))

    from build_html import build as build_html
    made.append(build_html(doc, args.outdir))

    counts = {}
    for c in doc["cases"]:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
    brief = "｜".join("%s %d" % (k, counts[k]) for k in VERDICT_META if k in counts)
    print("\n结论分布：%s" % brief)
    print("交付：%s" % " , ".join(os.path.basename(p) for p in made))
    return 0


if __name__ == "__main__":
    sys.exit(main())
