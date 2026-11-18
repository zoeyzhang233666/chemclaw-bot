#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_all.py — 一条命令跑完：合并数据 → 校验 → 生成 HTML → 生成 Excel

用法:
    python build_all.py                          # 用默认路径
    python build_all.py --data ../data --out ../output
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser(description="化工品产能分布报告一键构建")
    ap.add_argument("--data", default=os.path.join(HERE, "..", "data"), help="数据目录")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "output"), help="输出目录")
    ap.add_argument("--name", default="", help="文件名前缀（默认取 meta.title）")
    ap.add_argument("--skip-excel", action="store_true")
    ap.add_argument("--skip-html", action="store_true")
    a = ap.parse_args()

    data_dir = os.path.abspath(a.data)
    out_dir = os.path.abspath(a.out)
    os.makedirs(out_dir, exist_ok=True)

    from pcd_model import load, DupChecker, Aggregator

    final = os.path.join(data_dir, "final.json")
    if not os.path.exists(final):
        print(f"[1/4] final.json 不存在，先运行 assemble.py …")
        import assemble as asm
        asm.main()
    else:
        print(f"[1/4] 载入 {final}")

    print(f"[2/4] 载入并校验 …")
    ds = load(final)
    findings = DupChecker(ds).run()
    errs = [f for f in findings if f.severity == "ERROR"]
    warns = [f for f in findings if f.severity == "WARN"]
    print(f"      ERROR {len(errs)} / WARN {len(warns)} / 合计 {len(findings)}")
    if errs:
        print("      ⚠ 存在 ERROR，请先修复：")
        for f in errs[:10]:
            print(f"        {f.rule} {f.subject} {f.message}")
    agg = Aggregator(ds, basis="design")
    print(f"      样本设计产能合计 {agg.total():,.1f} 万吨/年（{len(agg.rows())} 条装置）")

    base = a.name or ds.product.get("short", "产品")
    year = ds.product.get("base_year", "")
    stamp = ds.meta.get("generated", "").replace("-", "")

    if not a.skip_html:
        print("[3/4] 生成 HTML …")
        from render_html import render
        checks = [{"rule": f.rule, "severity": f.severity, "subject": f.subject,
                   "message": f.message, "fix": f.fix} for f in findings]
        p = os.path.join(out_dir, f"{base}产能分布报告_{year}年_{stamp}.html")
        render(ds, p, checks)
        print(f"      → {p}  ({os.path.getsize(p)/1024:.0f} KB)")
    else:
        print("[3/4] 跳过 HTML")

    if not a.skip_excel:
        print("[4/4] 生成 Excel …")
        from build_excel import build
        p = os.path.join(out_dir, f"{base}企业产能明细表_{year}年_{stamp}.xlsx")
        build(ds, p, findings)
        print(f"      → {p}  ({os.path.getsize(p)/1024:.0f} KB)")
    else:
        print("[4/4] 跳过 Excel")

    print("\n完成。交付前请按 templates/checklist.md 逐项自检。")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
