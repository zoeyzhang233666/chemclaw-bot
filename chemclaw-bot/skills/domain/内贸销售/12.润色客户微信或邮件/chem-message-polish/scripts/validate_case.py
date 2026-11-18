#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只做边界校验，不生成产物。

用法:
  python validate_case.py --case case.json [--json report.json]
退出码: 0 = 无 ERROR（可能有 WARN）；1 = 有 ERROR
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caselib as C  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="case.json 路径")
    ap.add_argument("--json", default="", help="把结果写成 JSON")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    case = C.load_case(args.case)
    problems = C.guard(case)
    err, warn = C.summarize(problems)
    st = C.stats(case)

    if not args.quiet:
        print("=" * 66)
        print("边界校验  %s" % os.path.basename(args.case))
        print("  产品 %s | 场景 %s | 渠道 %s" % (
            case["meta"].get("product"), case["meta"].get("scenario"), case["meta"].get("channel")))
        print("  事实 %d 条 | 审计 %d 行 | 占位符 %d 条 | 场景 %d 个 | 字数 A/B/C/D = %s" % (
            st["facts"], st["audit"], st["placeholders"], st["scenarios"],
            "/".join(str(st["words"][k]) for k in C.VERSION_KEYS)))
        print("=" * 66)
        if not problems:
            print("  未发现问题：数字、承诺、稀缺话术、禁语、占位符、审计覆盖全部通过。")
        for level, code, msg in problems:
            mark = "✗" if level == "ERROR" else "!"
            print("  %s [%s] %s" % (mark, code, msg))
        print("-" * 66)
        print("  结果: %d ERROR / %d WARN → %s" % (err, warn, "可生成产物" if err == 0 else "禁止交付"))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"errors": err, "warns": warn,
                       "problems": [{"level": l, "code": c, "msg": m} for l, c, m in problems],
                       "stats": st}, f, ensure_ascii=False, indent=2)
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
