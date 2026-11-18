# -*- coding: utf-8 -*-
"""analysis.py — 跑本案例统计，产出 out/result.json 与 out/analysis_table.csv"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "..", "scripts", "run_pipeline.py")
cmd = [sys.executable, os.path.abspath(S),
       "--a", os.path.join(HERE, "data", "pp.csv"),
       "--b", os.path.join(HERE, "data", "lldpe.csv"),
       "--aname", "PP", "--bname", "LLDPE",
       "--out", os.path.join(HERE, "out"),
       "--start", "2023-10-20"]
print(" ".join(cmd))
sys.exit(subprocess.call(cmd))
