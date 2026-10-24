# -*- coding: utf-8 -*-
"""pipeline.py — 一键：数据自检 → 统计 → 出报告"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
for s in ("sample.py", "analysis.py", "build_html.py"):
    print(f"\n=== {s} ===")
    rc = subprocess.call([sys.executable, os.path.join(HERE, s)])
    if rc != 0:
        raise SystemExit(f"{s} 失败，rc={rc}")
print("\n[pipeline] 全部完成，产物见 out/")
