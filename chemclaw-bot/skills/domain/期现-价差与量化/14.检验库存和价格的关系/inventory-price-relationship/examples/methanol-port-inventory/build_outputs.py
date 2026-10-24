# -*- coding: utf-8 -*-
"""Build the methanol case report + workbook from the pipeline output."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))

from build_outputs import build_report, build_workbook  # noqa: E402

OUT = os.path.join(HERE, "output")
narrative = json.load(open(os.path.join(HERE, "narrative.json"), encoding="utf-8"))

build_workbook(OUT, narrative, os.path.join(OUT, "甲醇港口库存因子研究_数据工作簿.xlsx"))
build_report(OUT, narrative, os.path.join(OUT, "甲醇港口库存与价格关系研究报告.html"))
print("outputs written to", OUT)
for f in sorted(os.listdir(OUT)):
    print("  %-52s %8.1f KB" % (f, os.path.getsize(os.path.join(OUT, f)) / 1024))
