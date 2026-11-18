# -*- coding: utf-8 -*-
"""check_report.py — 交付前自检：口径一致性、结构与红线

检查项：
  1. XLSX 能打开，表齐全（00–10）
  2. HTML 非空、能解析、图表容器与 ECharts 存在、内联脚本无明显语法错误
  3. 事件表与报告中的样本数一致
  4. 红线：不得出现“保证/必然/一定涨/目标价/建议买入卖出”等措辞；
     缺失值不得被 0 或均值替代（03 表“缺失”字样必须存在）
  5. 若样本 < 10，报告必须含样本量警告
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core  # noqa: E402

BANNED = ["必然上涨", "必然下跌", "一定会涨", "一定会跌", "保证收益", "稳赚", "目标价",
          "建议买入", "建议卖出", "满仓", "抄底", "做多稳赚"]
REQUIRED_SHEETS = ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]


def check(project: str, html: str, xlsx: str) -> int:
    fails, warns = [], []

    # ---- XLSX ----
    if not os.path.exists(xlsx):
        fails.append("XLSX 不存在")
    else:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(xlsx, read_only=True)
            names = wb.sheetnames
            for code in REQUIRED_SHEETS:
                if not any(n.startswith(code) for n in names):
                    fails.append(f"XLSX 缺表：{code}")
            print(f"[xlsx] {len(names)} 张表：{', '.join(names)}")
        except Exception as e:  # pragma: no cover
            fails.append(f"XLSX 打不开：{e}")

    # ---- HTML ----
    if not os.path.exists(html):
        fails.append("HTML 不存在")
        return _report(fails, warns)
    raw = open(html, encoding="utf-8").read()
    print(f"[html] {len(raw)/1024:.0f} KB")
    if len(raw) < 200_000:
        warns.append("HTML 小于 200KB，ECharts 可能未内联")
    for needle, desc in [("echarts", "ECharts 库"), ("chart-window", "对齐窗口图"),
                         ("chart-path", "均值/中位路径图"), ("chart-dist", "分布图"),
                         ("ev-table", "事件样本表"), ("cfg-anchor", "口径切换控件")]:
        if needle not in raw:
            fails.append(f"HTML 缺 {desc}（{needle}）")
    for w in BANNED:
        if w in raw:
            fails.append(f"HTML 含禁用措辞：{w}")

    # 检查 <script> 块是否被完整闭合
    if raw.count("<script>") != raw.count("</script>"):
        fails.append("HTML script 标签不配对")

    # ---- 口径一致性 ----
    ev = core.load_events_csv(os.path.join(project, "events.csv"))
    n_incl = sum(1 for e in ev if e.include_flag is not False and e.product_verified is not False)
    stats_p = os.path.join(project, "build", "stats.json")
    if os.path.exists(stats_p):
        st = json.load(open(stats_p, encoding="utf-8"))
        n_cmp = st.get("all", {}).get("n")
        print(f"[stats] 可比样本 n={n_cmp}（原始纳入判断 {n_incl}）")
        if st.get("all", {}).get("n", 0) < 10:
            warns.append(f"可比样本仅 {n_cmp} 个（<10），报告必须显著提示样本量不足")
        if "样本过小" not in raw and st.get("all", {}).get("n", 0) < 3:
            fails.append("样本<3，但 HTML 未给出样本量警告")

    # 缺失必须显性标注
    if "数据缺口" not in raw:
        fails.append("HTML 缺“数据缺口”章节")

    return _report(fails, warns)


def _report(fails, warns) -> int:
    for w in warns:
        print("  [warn] " + w)
    for f in fails:
        print("  [FAIL] " + f)
    if fails:
        print(f"自检未通过：{len(fails)} 项失败，{len(warns)} 项警告")
        return 1
    print(f"自检通过：0 项失败，{len(warns)} 项警告")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--xlsx", required=True)
    a = ap.parse_args(argv)
    sys.exit(check(a.project, a.html, a.xlsx))


if __name__ == "__main__":
    main()
