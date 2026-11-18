# -*- coding: utf-8 -*-
"""build_html.py — 由 out/result.json + narrative.json 生成单文件交互报告"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "..", "scripts", "build_reports.py")
sys.exit(subprocess.call([sys.executable, os.path.abspath(S), "--out", os.path.join(HERE, "out")]))
