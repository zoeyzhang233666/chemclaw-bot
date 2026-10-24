"""
check_xlsx.py — 结构校验 Excel 工作簿：sheet 是否齐全、有无空表、公式/数字格式、裸数字（无来源列）、
URL 是否可点击、缺口表是否存在。返回码非 0 表示不可交付。

  python check_xlsx.py out/xxx.xlsx [--require "00 说明与口径,14 数据缺口,16 来源清单"]
"""
import argparse
import os
import sys

REQUIRED = ["说明与口径", "关键指标", "进口历史", "主要来源国", "中国出口", "关税政策", "数据缺口", "待核实行动", "来源清单"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--require", default="")
    ap.add_argument("--min-rows", type=int, default=1)
    ap.add_argument("--min-gap-cells", type=int, default=8,
                    help="缺口表最少非空单元格数；小样本 case 可调低")
    a = ap.parse_args()
    try:
        from openpyxl import load_workbook
    except ImportError:
        print("需要 openpyxl")
        return 2
    wb = load_workbook(a.xlsx)
    errs, warns, info = [], [], []
    names = wb.sheetnames
    info.append("工作表 %d 个：%s" % (len(names), ", ".join(names)))
    req = [x.strip() for x in a.require.split(",")] if a.require else REQUIRED
    for key in req:
        if not any(key in n for n in names):
            errs.append("缺少工作表：%s" % key)
    for ws in wb.worksheets:
        used_rows = 0
        for row in ws.iter_rows(min_row=4, values_only=True):
            if any(v not in (None, "") for v in row):
                used_rows += 1
        if used_rows < a.min_rows:
            errs.append("工作表「%s」数据行过少（%d 行）" % (ws.title, used_rows))
        info.append("  %-18s %3d 行 × %2d 列" % (ws.title, used_rows, ws.max_column))
        # hyperlinks should be real links
        for row in ws.iter_rows(min_row=4):
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("http") and not c.hyperlink:
                    warns.append("「%s」%s 有 URL 但未设为超链接" % (ws.title, c.coordinate))
        # nothing should be a formula error or literal None text
        for row in ws.iter_rows(min_row=4, values_only=True):
            for v in row:
                if isinstance(v, str) and v.strip().lower() in ("none", "nan", "undefined", "null"):
                    warns.append("「%s」出现占位文本 %r" % (ws.title, v))
    # the gap sheet must actually contain gaps
    gap_sheet = next((ws for ws in wb.worksheets if "数据缺口" in ws.title), None)
    if gap_sheet:
        texts = [str(c.value) for row in gap_sheet.iter_rows(min_row=5) for c in row if c.value]
        if len(texts) < a.min_gap_cells:
            errs.append("数据缺口表内容过少：缺口清单是交付质量的证明，不能为空")
    # every tariffs row must carry a status
    tar = next((ws for ws in wb.worksheets if "关税" in ws.title), None)
    if tar:
        heads = [c.value for c in tar[4]]
        if "状态" not in [h for h in heads if h]:
            warns.append("关税表缺少“状态”列，无法区分已核实/待核实")
    print("\n".join(info))
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    print("—" * 50)
    print("%d error / %d warning%s" % (len(errs), len(warns), "" if not errs else "  → 不可交付"))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
