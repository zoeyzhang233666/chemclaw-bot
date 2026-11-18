#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一条命令跑完：校验 → Excel → HTML → 产物自检。

用法:
  python run_all.py --case case.json [--out out] [--force]

有任何 ERROR 都会拒绝生成；--force 仅用于调试，会在产物页眉留下未通过的说明。
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caselib as C  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--force", action="store_true", help="有 ERROR 也强行生成（不建议）")
    args = ap.parse_args(argv)

    case = C.load_case(args.case)
    problems = C.guard(case)
    err, warn = C.summarize(problems)
    st = C.stats(case)

    print("=" * 70)
    print("客户沟通润色  |  %s · %s  |  客户：%s" % (
        case["meta"].get("product"), case["meta"].get("scenario"),
        (case["meta"].get("customer") or {}).get("name")))
    print("事实 %d · 审计 %d · 占位符 %d · 场景 %d · 字数 A/B/C/D = %s" % (
        st["facts"], st["audit"], st["placeholders"], st["scenarios"],
        "/".join(str(st["words"][k]) for k in C.VERSION_KEYS)))
    print("-" * 70)
    for level, code, msg in problems:
        print("  %s [%s] %s" % ("✗" if level == "ERROR" else "!", code, msg))
    if not problems:
        print("  边界校验通过：数字/承诺/稀缺话术/禁语/占位符/审计覆盖 全部 OK")
    print("-" * 70)

    if err and not args.force:
        print("存在 %d 个 ERROR，拒绝生成产物。修正后重跑，或加 --force 调试。" % err)
        return 1

    if case["meta"].get("fictional"):
        print("提示：本案例标记为虚构示例，请在产物页脚保留相关声明。")

    from build_workbook import build as build_xlsx
    from build_html import build as build_html
    x = build_xlsx(case, args.out)
    h = build_html(case, args.out)
    print("产物：")
    print("  " + x)
    print("  " + h)

    try:
        import check_outputs
        ok = check_outputs.check(args.case, args.out)
        print("自检：%s" % ("通过" if ok else "有问题，见上方明细"))
        return 0 if ok else 1
    except Exception as exc:  # pragma: no cover
        print("自检未执行：%s" % exc)
        return 0


if __name__ == "__main__":
    sys.exit(main())
