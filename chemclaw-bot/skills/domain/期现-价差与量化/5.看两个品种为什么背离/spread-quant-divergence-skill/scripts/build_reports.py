# -*- coding: utf-8 -*-
"""
build_reports.py — 由 result.json + narrative.json 生成 HTML 报告与 Excel 工作簿
用法：
  python build_reports.py --out ./out [--aname PP --bname LLDPE]
本脚本是 build_html.py / build_xlsx.py 的**参数化封装**，两者共用同一份 result.json。
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="含 result.json / narration.json / analysis_table.csv 的目录")
    ap.add_argument("--workdir", default=None, help="兼容旧脚本的 B 目录；默认等于 --out")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    need = ["result.json", "analysis_table.csv"]
    miss = [f for f in need if not os.path.exists(os.path.join(out, f))]
    if miss:
        raise SystemExit(f"缺少文件：{miss}。请先运行 run_pipeline.py，并补齐 narrative.json。")

    # build_html / build_xlsx 依赖模块级变量 B
    for name, fname in (("h", "build_html.py"), ("x", "build_xlsx.py")):
        mod = load_module(os.path.join(HERE, fname), f"bld_{name}")
        mod.B = out
        if hasattr(mod, "R"):
            mod.R = json.load(open(os.path.join(out, "result.json"), encoding="utf-8"))
        if hasattr(mod, "N"):
            mod.N = json.load(open(os.path.join(out, "narrative.json"), encoding="utf-8"))
        if hasattr(mod, "OUT"):
            mod.OUT = os.path.join(
                out, "PP_LLDPE_背离分析工作簿.xlsx"
                if "xlsx" in fname else "PP_LLDPE_背离诊断报告.html")
        for attr in ("T", "FUT_PP", "FUT_L", "SPP", "SLL"):
            if hasattr(mod, attr):
                import pandas as _pd
                csv_map = {"T": "analysis_table.csv", "FUT_PP": "fut_PP.csv",
                           "FUT_L": "fut_L.csv", "SPP": "spot_pp.csv", "SLL": "spot_lldpe_final.csv"}
                fp = os.path.join(out, csv_map[attr])
                if os.path.exists(fp):
                    setattr(mod, attr, _pd.read_csv(fp, parse_dates=["date"]))
        try:
            mod.main()
        except Exception as e:
            print(f"[{fname}] 失败：{e}")
            raise
    print("[build_reports] 完成")


if __name__ == "__main__":
    main()
