# -*- coding: utf-8 -*-
"""Excel 验收：公式是活的 + LibreOffice 重算后与 build/data.json 逐窗口对账。

用法：python scripts/check_xlsx.py <工作簿.xlsx> [build/data.json]
先重算（推荐）：
    <managed-python> <plugin>/runtime/office-cli.py recalculate --input a.xlsx --output b.xlsx
然后把 b.xlsx 传给本脚本。若传的是未重算的文件，脚本会提示公式未被求值。
"""
import json
import os
import sys

from openpyxl import load_workbook

XLSX = sys.argv[1] if len(sys.argv) > 1 else "out/report.xlsx"
DATA = sys.argv[2] if len(sys.argv) > 2 else "build/data.json"
OUTDIR = os.path.dirname(os.path.abspath(XLSX)) or "."

D = json.load(open(DATA, encoding="utf-8"))
A = D["analysis"]["S1_mid"]

wb = load_workbook(XLSX, data_only=True)
lines = []
fails = []


def get(sheet, cell):
    try:
        return wb[sheet][cell].value
    except KeyError:
        return None


# ---- 00. 先扫全簿错误值（#NAME? #REF! #DIV/0! #VALUE! #N/A）
ERR = ("#NAME?", "#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NULL!", "#NUM!")
n_err = 0
for sname in wb.sheetnames:
    ws = wb[sname]
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value in ERR:
                n_err += 1
                if n_err <= 8:
                    lines.append("  ⚠ 错误值 %s!%s = %s" % (sname, c.coordinate, c.value))
lines.append("全簿错误值单元格 = %d" % n_err)
if n_err:
    fails.append("工作簿存在 %d 个错误值单元格（#NAME?/#REF! 等），公式未被正确求值" % n_err)

# ---- 04 表：逐窗口核对 n / min / max / median / 分位（行号按 A 列标签定位，不写死）
ws4 = wb["04 历史分位(公式)"]
label_row = {}
for rr in range(1, ws4.max_row + 1):
    v = ws4.cell(rr, 1).value
    if isinstance(v, str) and ("天" in v or "月" in v or "年" in v):
        for wk, lab in (("30", "近 30 天"), ("90", "近 3 个月"), ("365", "近 1 年"),
                        ("1095", "近 3 年"), ("1826", "近 5 年")):
            if v.strip() == lab:
                label_row[wk] = rr
for wk in ("30", "90", "365", "1095", "1826"):
    row = label_row.get(wk)
    if not row:
        fails.append("04 表找不到窗口行：%s" % wk)
        continue
    v = A["windows"].get(wk, {})
    n = get("04 历史分位(公式)", "D%d" % row)
    mn = get("04 历史分位(公式)", "E%d" % row)
    mx = get("04 历史分位(公式)", "F%d" % row)
    md = get("04 历史分位(公式)", "G%d" % row)
    pct = get("04 历史分位(公式)", "H%d" % row)
    mid = get("04 历史分位(公式)", "I%d" % row)
    pos = get("04 历史分位(公式)", "J%d" % row)
    if v.get("available"):
        st = v["stats"]; p = v["percentile"]
        exp = (v["n_obs"], st["min"], st["max"], st["median"],
               p["percentile_inclusive_pct"] / 100, p["percentile_midrank_pct"] / 100,
               v["range_position_pct"] / 100)
        got = (n, mn, mx, md, pct, mid, pos)
        try:
            ok = all(g is not None and e is not None and abs(float(g) - float(e)) < 5e-4
                     for g, e in zip(got, exp))
        except (TypeError, ValueError):
            ok = False
        lines.append("%ss n=%s min=%s max=%s med=%s pct=%s  %s"
                     % (wk, n, mn, mx, md, pct, "OK" if ok else "MISMATCH"))
        if not ok:
            fails.append("%ss 公式结果与 data.json 不一致：%s vs %s" % (wk, got, exp))
    else:
        ok = isinstance(pct, str) and "不足" in pct
        lines.append("%ss n=%s 分位=%r  %s" % (wk, n, pct, "OK(应不足)" if ok else "MISMATCH"))
        if not ok:
            fails.append("%ss 样本不足时未正确标注：%r" % (wk, pct))

# ---- 05 表：全样本 max/min 与均值
vals = [x["mid"] for x in D["series"]["S1"]["data"]]
alln = get("05 统计指标(公式)", "B5")
allmin = get("05 统计指标(公式)", "B6")
allmax = get("05 统计指标(公式)", "B7")
allmean = get("05 统计指标(公式)", "B8")
lines.append("05 全样本 n=%s min=%s max=%s mean=%s" % (alln, allmin, allmax, allmean))
if alln != len(vals):
    fails.append("05 全样本 n 不符：%s vs %d" % (alln, len(vals)))
if allmin is None or allmax is None or abs(float(allmin) - min(vals)) > 1e-6 \
        or abs(float(allmax) - max(vals)) > 1e-6:
    fails.append("05 全样本 min/max 不符")
if allmean is None or abs(float(allmean) - sum(vals) / len(vals)) > 1e-4:
    fails.append("05 全样本均值不符")

# ---- 07 表与 08 表的同年同月必须一致（行号按年份内容定位）
def find_year_row(wb_, sheet, year):
    ws_ = wb_[sheet]
    for rr in range(1, ws_.max_row + 1):
        if ws_.cell(rr, 1).value == year:
            return rr
    return None

LAST_YEAR = int(A["last_date"][:4])
LAST_MONTH = int(A["last_date"][5:7])
y7 = find_year_row(wb, "07 同期对比(公式)", LAST_YEAR)
y8 = find_year_row(wb, "08 季节性(公式)", LAST_YEAR)
v7 = wb["07 同期对比(公式)"].cell(y7, 1 + LAST_MONTH).value if y7 else None
v8 = wb["08 季节性(公式)"].cell(y8, 1 + LAST_MONTH).value if y8 else None
lines.append("07/08 表 %d 年 %d 月：%s / %s" % (LAST_YEAR, LAST_MONTH, v7, v8))
if v7 is not None and v8 is not None:
    if abs(float(v7) - float(v8)) > 1e-6:
        fails.append("07/08 表同年同月不一致：%s vs %s" % (v7, v8))

# ---- 关键单元格必须存的是公式，不是粘贴值
wb2 = load_workbook(XLSX, data_only=False)
pct_cell = wb2["04 历史分位(公式)"].cell(label_row.get("1095", 8), 8).value
lines.append("04 表 3 年分位单元格存储内容 = %s" % (pct_cell if isinstance(pct_cell, str) else "非公式!"))
if not (isinstance(pct_cell, str) and pct_cell.startswith("=")):
    fails.append("04 表分位列不是公式（客户改价格不会联动重算）")

e5 = wb2["02 原始序列(主)"]["E5"].value
lines.append("02 表中值列 E5 = %s" % e5)
if not (isinstance(e5, str) and e5.startswith("=")):
    fails.append("02 表中值列不是公式")

for cell in ("B6", "B7", "B8"):
    v = wb2["05 统计指标(公式)"][cell].value
    if not (isinstance(v, str) and str(v).startswith("=")):
        fails.append("05 表 %s 不是公式" % cell)

# ---- 工作簿结构
lines.append("工作表：%s" % " | ".join(wb.sheetnames))
if len(wb.sheetnames) < 12:
    fails.append("工作表数量过少：%d" % len(wb.sheetnames))

lines.append("")
lines.append("FAIL=%d" % len(fails))
lines.extend("  [FAIL] " + f for f in fails)
rep = os.path.join(OUTDIR, "qa_xlsx.txt")
open(rep, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
sys.exit(0 if not fails else 1)

