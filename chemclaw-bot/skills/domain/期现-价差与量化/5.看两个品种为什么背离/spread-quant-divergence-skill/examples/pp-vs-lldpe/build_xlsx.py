# -*- coding: utf-8 -*-
"""build_xlsx.py — 生成 13 表工作簿（与 build_html 共用 build_reports 流程）"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "..", "scripts", "build_reports.py")
sys.exit(subprocess.call([sys.executable, os.path.abspath(S), "--out", os.path.join(HERE, "out")]))
