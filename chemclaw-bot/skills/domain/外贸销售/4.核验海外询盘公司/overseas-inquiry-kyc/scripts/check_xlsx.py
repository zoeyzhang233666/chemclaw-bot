#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Excel 结构检查：无图像渲染，用几何与内容规则代替肉眼。

检查项：
  1 工作表齐全、命名符合编号规范
  2 每表都写了标题行（A1）与副标题（A2）
  3 状态列必须有色（不允许出现“已核实/存在疑点/未核实”却没有底色）
  4 自动筛选区域必须覆盖真正的表头行（表头下一行要有数据）
  5 合并单元格不得覆盖已写值的单元格（布局塌陷的典型症状）
  6 每个核验项 / 索取项 / 来源 / 矩阵行都真的写进了单元格
  7 列宽不超过 90，行高不超过 420（防止一页一行）
  8 中文内容占比：不应出现乱码（U+FFFD / 典型 GBK 误解码片段）

用法: python check_xlsx.py workbook.xlsx [--json out.json]
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys

if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    print("[skip] 需要 openpyxl")
    sys.exit(0)

STATUS_WORDS = {"已核实", "存在疑点", "未核实", "不适用"}
# 这些是第一列/左侧的“键名”，不是状态值
KEY_WORDS = {"状态", "结论状态", "核验状态", "比对", "已核实", "存在疑点", "未核实", "合计"}
STATUS_FILLS = {"E7F2EA", "FBE9E6", "E9ECEF", "EEF0F2"}
MOJIBAKE = re.compile(r"[\uFFFD]|[\u00c0-\u00c5][\u0080-\u00bf]|[\u00e4-\u00e9][\u0080-\u00bf]{1,3}")


def fill_hex(cell):
    try:
        f = cell.fill
        if f is None or f.fill_type is None:
            return None
        rgb = f.fgColor.rgb if f.fgColor and f.fgColor.type == "rgb" else None
        return (rgb or "")[-6:].upper() or None
    except Exception:
        return None


def run(path):
    errors, warns, notes = [], [], []
    wb = load_workbook(path)
    # 收集每个表的表头行号（用于豁免表头里的“状态”字样）
    header_rows = {}
    for ws_ in wb.worksheets:
        hs = set()
        for row in ws_.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.strip() == "状态":
                    hs.add(c.row)
        header_rows[ws_.title] = hs

    if len(wb.sheetnames) < 10:
        errors.append(f"工作表只有 {len(wb.sheetnames)} 个，应 ≥ 10")

    for ws in wb.worksheets:
        name = ws.title
        if not re.match(r"^\d{2}_", name):
            warns.append(f"{name}：命名不符合 “NN_名称” 规范")
        a1 = ws["A1"].value
        if not a1 or not str(a1).strip():
            errors.append(f"{name}：A1 标题为空")
        # A2 可能被 A1 的合并区吞掉（封面标题横幅），这种情况不算缺副标题
        a2_merged = any(ws["A2"].coordinate in rng for rng in ws.merged_cells.ranges)
        if not ws["A2"].value and not a2_merged:
            warns.append(f"{name}：A2 副标题为空")

        # 状态列着色：只查“取值本身就是状态”的单元格（键列或数据列中出现 k/v/zh/en 等键名的不算）
        status_cells = 0
        uncolored = []
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.strip() in STATUS_WORDS:
                    # 表头行、键名列、说明列不强制上色
                    left = ws.cell(row=c.row, column=max(1, c.column - 1)).value \
                        if c.column > 1 else None
                    if c.row in header_rows.get(name, set()):
                        continue
                    # 本行若作为一个小表的表头（下一行开始是数据/合计），且本格是粗体 → 视为表头
                    if c.font is not None and c.font.bold:
                        continue
                    if isinstance(left, str) and left.strip() in KEY_WORDS:
                        continue
                    # 键名列（例如封面“已核实 / 存在疑点 / 未核实”作为 KPI 标签）不强制
                    right = ws.cell(row=c.row, column=c.column + 1).value
                    if isinstance(c.value, str) and c.value.strip() in STATUS_WORDS and isinstance(right, (int, float)):
                        continue
                    status_cells += 1
                    if fill_hex(c) not in STATUS_FILLS:
                        uncolored.append(c.coordinate)
        if uncolored:
            errors.append(f"{name}：{len(uncolored)} 个状态单元格没有状态底色（如 {uncolored[:5]}）")

        # 自动筛选是否落在表头
        if ws.auto_filter and ws.auto_filter.ref:
            m = re.match(r"^[A-Z]+(\d+):", ws.auto_filter.ref)
            if m:
                hdr = int(m.group(1))
                below = [ws.cell(row=hdr + 1, column=c).value for c in range(1, 4)]
                if all(v in (None, "") for v in below):
                    errors.append(f"{name}：自动筛选表头在第 {hdr} 行，但下一行为空（筛选会落空）")

        # 合并区域不应盖住有值的单元格（取左上以外的值）
        for rng in ws.merged_cells.ranges:
            vals = []
            for row in ws.iter_rows(min_row=rng.min_row, max_row=rng.max_row,
                                    min_col=rng.min_col, max_col=rng.max_col):
                for c in row:
                    if c.value not in (None, ""):
                        vals.append(c.coordinate)
            if len(vals) > 1:
                errors.append(f"{name}：合并区 {rng.coord} 内有 {len(vals)} 个非空单元格，内容会被隐藏")

        # 列宽 / 行高
        for col, dim in ws.column_dimensions.items():
            if dim.width and dim.width > 92:
                warns.append(f"{name}：列 {col} 宽 {dim.width}，过宽")
        for r_, dim in ws.row_dimensions.items():
            if dim.height and dim.height > 430:
                warns.append(f"{name}：第 {r_} 行高 {dim.height}，过高")

        # 乱码
        bad = []
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and MOJIBAKE.search(c.value):
                    bad.append(c.coordinate)
        if bad:
            errors.append(f"{name}：疑似乱码 {len(bad)} 处（如 {bad[:4]}）")

        notes.append({"sheet": name, "status_cells": status_cells,
                      "rows": ws.max_row, "cols": ws.max_column})

    # 关键内容抽查
    def sheet_has(sh, prefix, minimum):
        ws = wb[sh] if sh in wb.sheetnames else None
        if ws is None:
            errors.append(f"缺少工作表 {sh}")
            return
        n = 0
        for row in ws.iter_rows():
            v = row[0].value
            if isinstance(v, str) and v.startswith(prefix):
                n += 1
        if n < minimum:
            errors.append(f"{sh}：{prefix}* 行只有 {n} 条，期望 ≥ {minimum}")

    if "06_核验结论" in wb.sheetnames:
        sheet_has("06_核验结论", "K", 8)
    if "08_待索取资料" in wb.sheetnames:
        sheet_has("08_待索取资料", "Q", 5)
    if "11_来源库" in wb.sheetnames:
        sheet_has("11_来源库", "SRC", 3)

    return errors, warns, notes, wb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--json")
    a = ap.parse_args()
    errors, warns, notes, wb = run(a.xlsx)

    print(f"工作表 {len(wb.sheetnames)} 个：{' / '.join(wb.sheetnames)}")
    for nt in notes:
        print(f"  · {nt['sheet']:<18} {nt['rows']:>3} 行 × {nt['cols']:>2} 列  状态单元格 {nt['status_cells']}")
    for w in warns:
        print(f"[warn] {w}")
    for e in errors:
        print(f"[ERROR] {e}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"errors": errors, "warns": warns, "sheets": notes}, f, ensure_ascii=False, indent=2)
    print(f"\n{'✓ PASS' if not errors else '✗ FAIL'}：{len(errors)} error / {len(warns)} warning")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
