#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a 9-sheet Excel workbook for one chemical + target region.

Usage:
  python build_xlsx.py data.json output.xlsx

Dependency: openpyxl. No formulas are used, so the file opens without a
recalculation step. Charts use visible cells only.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.data_source import AxDataSource, StrRef
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.worksheet.page import PageMargins

import common

# ---------- palette ----------
INK = "0F3D33"
INK2 = "173F35"
COPPER = "B4642D"
AMBER = "D9A441"
BLUE = "2F6F8F"
OLIVE = "6B7F4A"
RED = "A23B2A"
PAPER = "F3EFE6"
CARD = "FFFDF8"
LINE = "DCD2C1"
MUTED = "6E7B72"
SOFT = "E8E0D1"
TINT_GREEN = "E7F0E9"
TINT_AMBER = "F7EEDB"
TINT_BLUE = "E7F0F5"
WHITE = "FFFFFF"

FONT = "Microsoft YaHei"
MONO = "Consolas"


def font(size=10, bold=False, color=INK, italic=False, underline=None, name=FONT):
    return Font(name=name, size=size, bold=bold, color=color, italic=italic, underline=underline)


def fill(color):
    return PatternFill("solid", fgColor=color)


def side(style="thin", color=LINE):
    return Side(style=style, color=color)


def border(color=LINE, style="thin"):
    s = side(style, color)
    return Border(left=s, right=s, top=s, bottom=s)


def align(h="left", v="center", wrap=True):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


def cell(ws, row, col, value="", f=None, fillc=None, alignh="left", wrap=True, fmt=None):
    c = ws.cell(row=row, column=col)
    c.value = value
    c.font = f or font()
    if fillc:
        c.fill = fill(fillc)
    c.alignment = align(alignh, "center", wrap)
    c.border = border()
    if fmt:
        c.number_format = fmt
    return c


def page_setup(ws, landscape=True):
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.32, right=0.32, top=0.48, bottom=0.42, header=0.18, footer=0.18)
    ws.oddFooter.center.text = "化工品竞争供给地图 · 数据截至 " + "{{asof}}" + " · 第 &P 页 / 共 &N 页"
    ws.oddFooter.center.size = 8
    ws.oddFooter.center.color = MUTED


def title_block(ws, no, title, sub, last_col):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    c = ws.cell(1, 1, value=f"{no}  {title}")
    c.font = font(17, True, WHITE)
    c.fill = fill(INK)
    c.alignment = align("left", "center", False)
    ws.row_dimensions[1].height = 34
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
    c = ws.cell(2, 1, value=sub)
    c.font = font(9, False, MUTED)
    c.fill = fill(CARD)
    c.alignment = align("left", "center", True)
    ws.row_dimensions[2].height = 26


def section_bar(ws, row, no, title, sub, last_col):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
    c = ws.cell(row, 1, value=f"{no}  {title}   {sub}")
    c.font = font(11, True, WHITE)
    c.fill = fill(COPPER)
    c.alignment = align("left", "center", False)
    ws.row_dimensions[row].height = 23


def header(ws, row, cols, widths=None):
    for i, x in enumerate(cols, 1):
        c = cell(ws, row, i, x, font(9, True, WHITE), INK, "center", True)
        c.border = border(INK)
    ws.row_dimensions[row].height = 31
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def cjk_height(text, width, base=18):
    s = str(text or "")
    units = sum(2 if ord(ch) > 127 else 1 for ch in s)
    lines = max(1, math.ceil(units / max(width * 1.05, 4)))
    return max(base, min(72, 14 * lines + 6))


def total_row(ws, row, ncols, label, values, note="", start_col=3, label_span=2):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=label_span)
    c = ws.cell(row, 1, value=label)
    c.font = font(10, True, COPPER)
    c.fill = fill(TINT_AMBER)
    c.alignment = align("left", "center", True)
    c.border = border(COPPER)
    for i, v in enumerate(values, start_col):
        c = cell(ws, row, i, v, font(10, True, COPPER), TINT_AMBER, "center")
        c.border = border(COPPER)
    if note and start_col + len(values) <= ncols:
        ws.merge_cells(start_row=row, start_column=start_col + len(values), end_row=row, end_column=ncols)
        c = cell(ws, row, start_col + len(values), note, font(8.5, False, COPPER), TINT_AMBER, "left")
        c.border = border(COPPER)
    ws.row_dimensions[row].height = 24


def note(ws, row, text, last_col, color=MUTED, size=8.5):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
    c = ws.cell(row, 1, value=text)
    c.font = font(size, False, color)
    c.alignment = align("left", "center", True)
    ws.row_dimensions[row].height = 22


def grade_cell(ws, row, col, g):
    colors = {"A": INK, "B": BLUE, "C": COPPER, "D": MUTED}
    c = cell(ws, row, col, g, font(9, True, colors.get(g, MUTED)), CARD, "center")
    c.border = border(colors.get(g, LINE))


def src_cell(ws, row, col, D, ids):
    first = (ids or [None])[0]
    s = (D.get("source_map") or {}).get(first)
    text = " / ".join(ids or []) or "—"
    c = cell(ws, row, col, text, font(8, False, BLUE), CARD, "center")
    if s:
        c.hyperlink = s["url"]
        c.font = font(8, True, BLUE, underline="single")
    return c


def cover(wb, D):
    ws = wb.active
    ws.title = "00_封面"
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:F1")
    c = ws["A1"]
    c.fill = fill(INK)
    c.value = "CHEMICAL COMPETITOR SUPPLY MAP"
    c.font = font(9, True, AMBER)
    c.alignment = align("left", "center", False)
    ws.row_dimensions[1].height = 28
    ws.merge_cells("A2:F2")
    c = ws["A2"]
    c.fill = fill(INK)
    c.value = D["meta"].get("brand_name") or "化图 · SUPPLY MAP"
    c.font = font(10, True, "CFE3D7")
    c.alignment = align("left", "center", False)
    ws.row_dimensions[2].height = 24
    if D["meta"].get("is_synthetic"):
        ws.merge_cells("A3:F3")
        c = ws["A3"]
        c.value = "结构示例 · 不是研究结论 · 企业/数字/链接均为虚构，禁止用于真实业务判断"
        c.font = font(9, True, "7A4B1E")
        c.fill = fill("F7EEDB")
        c.alignment = align("center", "center", False)
        ws.row_dimensions[3].height = 22
    ws.merge_cells("A4:F5")
    c = ws["A4"]
    c.value = D["meta"].get("product_short") or D["meta"].get("product")
    c.font = font(34, True, INK)
    c.alignment = align("left", "center", False)
    ws.row_dimensions[4].height = 42
    ws.row_dimensions[5].height = 24
    ws.merge_cells("A6:F6")
    c = ws["A6"]
    c.value = "竞争供给布局与区域空白 · " + D["target"]["region"]
    c.font = font(14, True, COPPER)
    c.alignment = align("left", "center", False)
    ws.row_dimensions[6].height = 26

    # KPI cards 2 x 2
    local = sum(p["capacity"] for p in D["plants"] if p.get("province") == D["target"]["province"])
    u = D["meta"].get("unit") or "万吨/年"
    kpis = [
        ("样本在产产能", f"{D['total_cap']:,.0f}", u, f"{D['total_companies']} 家企业 / {D['total_plants']} 座工厂"),
        ("目标区域本地在产", f"{local:,.0f}", u, D["target"]["province"] + " · 到" + D["target"]["city"] + "最近"),
    ]
    cov = D["meta"].get("coverage") or {}
    if cov.get("industry_low"):
        lo = round(D["total_cap"] / cov["industry_high"] * 100)
        hi = round(D["total_cap"] / cov["industry_low"] * 100)
        kpis.append(("样本覆盖", f"≈{lo}–{hi}%", "覆盖度", f"样本 {D['total_cap']:,.0f} / 全国 {cov['industry_low']:,}–{cov['industry_high']:,}"))
    else:
        kpis.append(("公开来源", str(len(D["sources"])), "条", "每条产能可回溯"))
    kpis.append(("数据截至", str(D["meta"].get("asof", "")), "", "公开年报/公告/项目报道"))
    for i, (lab, val, su, sub) in enumerate(kpis):
        r = 8 + (i // 2) * 3
        col = 1 + (i % 2) * 3
        ws.merge_cells(start_row=r, start_column=col, end_row=r, end_column=col + 2)
        c = ws.cell(r, col, value=lab)
        c.font = font(9, True, MUTED); c.fill = fill(CARD); c.alignment = align("left", "center", False)
        c.border = border(LINE)
        ws.merge_cells(start_row=r + 1, start_column=col, end_row=r + 1, end_column=col + 2)
        c = ws.cell(r + 1, col, value=val)
        c.font = font(20, True, INK); c.fill = fill(CARD); c.alignment = align("left", "center", False)
        c.border = border(LINE)
        ws.merge_cells(start_row=r + 2, start_column=col, end_row=r + 2, end_column=col + 2)
        c = ws.cell(r + 2, col, value=f"{su}  {sub}".strip())
        c.font = font(8, False, MUTED); c.fill = fill(CARD); c.alignment = align("left", "center", False)
        c.border = border(LINE)
    for r in (8, 9, 10, 11, 12, 13):
        ws.row_dimensions[r].height = 18 if r in (8, 10, 12) else 28

    # reading order
    section_bar(ws, 15, "READ", "阅读顺序", "先看地图 → 再看矩阵 → 最后看时间线", 6)
    read = [
        ("01", "企业对比矩阵", "产能/产量/工艺/距离/覆盖线索/新增项目并排", "01_企业矩阵"),
        ("02", "工厂明细", "省/市/经纬度/产能/产品/来源，可逐厂回溯", "02_工厂明细"),
        ("03", "新增项目", "规模、性质、状态、时间、净增判断", "03_新增项目"),
        ("04", "区域对照", "省级供给 + 需求线索 + 潜客数", "04_区域对照"),
        ("05", "目标区域与潜客", "锚点客户、供应梯度、8 家潜客、动作卡", "05_目标区域与潜客"),
        ("06", "数据来源", "每条来源可点击，标 A/B/C/D", "06_数据来源"),
        ("07", "口径与冲突", "并列冲突 + 采用理由 + 影响", "07_口径与冲突"),
        ("08", "数据缺口与边界", "下一步取证清单，不是免责声明", "08_数据缺口与边界"),
    ]
    r0 = 16
    for i, (no, name, desc, sheet) in enumerate(read):
        r = r0 + i
        c = cell(ws, r, 1, no, font(12, True, COPPER), CARD, "center")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        c = cell(ws, r, 2, name, font(10, True, INK), CARD, "left")
        c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{sheet}'!A1", display=name)
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        cell(ws, r, 4, desc, font(9, False, MUTED), CARD, "left")
        ws.row_dimensions[r].height = 21

    # method / legend
    section_bar(ws, 25, "METHOD", "口径与图例", "样本不是全行业；产能≠产量；距离≠运费", 6)
    ws.merge_cells("A26:F26")
    c = ws["A26"]
    c.value = "A 公司定期报告/政府文件 ｜ B 公司 IR/行业统计/券商拆分 ｜ C 企业公开业务信息 ｜ D 物流/覆盖推断。冲突口径并列保留，不强行抹平。"
    c.font = font(8.5, False, MUTED); c.alignment = align("left", "center", True)
    ws.row_dimensions[26].height = 30
    ws.merge_cells("A27:F28")
    c = ws["A27"]
    c.value = "使用方法：先在「01_企业矩阵」按产能/距离排序，锁定目标区域附近 3–5 家；再到「05_目标区域与潜客」看锚点客户与潜客；最后用「03_新增项目」判断 12–36 个月的价格与竞争窗口。"
    c.font = font(9.5, False, INK); c.fill = fill(TINT_GREEN)
    c.alignment = align("left", "center", True); c.border = border("C9D9CE")
    ws.row_dimensions[27].height = 24
    ws.row_dimensions[28].height = 20
    ws.merge_cells("A30:F30")
    c = ws["A30"]
    c.value = "本报告为销售线索与竞争布局研究，不构成投资建议、价格承诺或市场份额结论。"
    c.font = font(8, False, MUTED); c.alignment = align("left", "center", True)

    for col, w in zip("ABCDEF", [8, 22, 22, 25, 22, 22]):
        ws.column_dimensions[col].width = w
    ws.print_area = "A1:F30"
    page_setup(ws, landscape=False)
    return ws


def sheet_matrix(wb, D):
    ws = wb.create_sheet("01_企业矩阵")
    ws.sheet_view.showGridLines = False
    cols = ["#", "企业", "简称", "代码 / 别名", "总部", "工艺", "样本产能\n万吨/年", "最新产量\n万吨", "产能\n年份", "工厂\n数", "到目标\nkm", "距离带", "区域覆盖线索（D）", "新增 / 在建", "等级", "来源"]
    widths = [5, 24, 10, 16, 18, 9, 11, 11, 8, 7, 9, 16, 30, 30, 7, 12]
    title_block(ws, "01 / COMPANY MATRIX", "企业对比矩阵", f"{D['total_companies']} 家企业 · {D['total_plants']} 座工厂 · 样本 {D['total_cap']:,.0f} 万吨/年；按样本产能降序", len(cols))
    header(ws, 4, cols, widths)
    rows = sorted(D["companies"], key=lambda c: -c["capacity"])
    for i, c in enumerate(rows, 1):
        r = 4 + i
        cell(ws, r, 1, i, font(9, False, MUTED), CARD, "center")
        cell(ws, r, 2, c["name"], font(9.5, True, INK), CARD)
        cell(ws, r, 3, c.get("short"), font(9, False, MUTED), CARD, "center")
        tick = c.get("ticker") or "非上市"
        if c.get("alias"):
            tick += " · " + c["alias"]
        cell(ws, r, 4, tick, font(8.5, False, MUTED), CARD)
        cell(ws, r, 5, c.get("hq"), font(8.5, False, MUTED), CARD)
        cell(ws, r, 6, c.get("process"), font(9, True, BLUE), CARD, "center")
        cell(ws, r, 7, c.get("capacity"), font(10, True, INK), CARD, "center", fmt="#,##0")
        cell(ws, r, 8, c.get("output") if c.get("output") is not None else "—", font(9, False, INK), CARD, "center", fmt="#,##0.00")
        cell(ws, r, 9, c.get("cap_year"), font(8, False, MUTED), CARD, "center")
        cell(ws, r, 10, c.get("plant_count", 0), font(9, False, INK), CARD, "center")
        cell(ws, r, 11, c.get("min_km"), font(9, False, INK), CARD, "center")
        cell(ws, r, 12, c.get("band"), font(8, False, MUTED), CARD, "center")
        cell(ws, r, 13, c.get("coverage") or "—", font(8, False, MUTED), CARD)
        cell(ws, r, 14, c.get("new") or "—", font(8.5, False, INK), CARD)
        grade_cell(ws, r, 15, c.get("grade", "B"))
        src_cell(ws, r, 16, D, c.get("source_ids"))
        for col in (5, 13, 14):
            ws.cell(r, col).alignment = align("left", "center", True)
            ws.row_dimensions[r].height = max(24, cjk_height(ws.cell(r, col).value, widths[col - 1], 20))
    tr = 5 + len(rows)
    total_row(ws, tr, len(cols), "合计 / 样本", [D["total_cap"], round(D["total_out"], 2), "", D["total_plants"]], "产能≠产量；样本覆盖≠市场份额", start_col=7, label_span=6)
    note(ws, tr + 2, "注：产能利用率=最新产量/产能，部分企业产量含贸易/代工/统计口径差异，可能>100%，仅作量级参考。区域覆盖为物流可达性推断（D），不是企业披露的销售分区。", len(cols))
    note(ws, tr + 3, "来源缩写对应「06_数据来源」；绿色=A，蓝色=B，铜色=C，灰色=D。", len(cols))
    # top10 chart uses visible cells
    ch = BarChart()
    ch.type = "bar"; ch.style = 10
    ch.title = "样本产能 TOP 10（万吨/年）"
    ch.y_axis.title = "万吨/年"
    data = Reference(ws, min_col=7, min_row=4, max_row=min(14, 4 + len(rows)))
    cats = Reference(ws, min_col=2, min_row=5, max_row=min(14, 4 + len(rows)))
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    ch.series[0].cat = AxDataSource(strRef=StrRef(f="'01_企业矩阵'!$B$5:$B${min(14, 4 + len(rows))}"))
    ch.height = 8.5; ch.width = 15
    ch.legend = None
    ch.dataLabels = DataLabelList(); ch.dataLabels.showVal = True
    ws.add_chart(ch, "R4")
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:P{4 + len(rows)}"
    ws.print_area = f"A1:P{tr + 3}"
    page_setup(ws, landscape=True)
    return ws


def sheet_plants(wb, D):
    ws = wb.create_sheet("02_工厂明细")
    ws.sheet_view.showGridLines = False
    cols = ["#", "企业", "工厂 / 基地", "省", "市", "经度", "纬度", "工艺", "产能\n万吨/年", "产能\n年份", "主要产品", "到目标\nkm", "距离带", "备注", "等级", "来源"]
    widths = [5, 20, 26, 9, 12, 9, 9, 9, 10, 8, 22, 9, 16, 34, 7, 11]
    title_block(ws, "02 / PLANT DETAILS", "工厂明细", f"{D['total_plants']} 座工厂 · 经纬度可直接复核 · 距离为到{D['target']['city']}的直线距离", len(cols))
    header(ws, 4, cols, widths)
    for i, p in enumerate(sorted(D["plants"], key=lambda p: (p.get("province"), -p["capacity"])), 1):
        r = 4 + i
        cell(ws, r, 1, i, font(9, False, MUTED), CARD, "center")
        cell(ws, r, 2, p.get("company"), font(8.5, True, INK), CARD)
        cell(ws, r, 3, p.get("name"), font(9, True, INK), CARD)
        cell(ws, r, 4, p.get("province"), font(8.5, False, MUTED), CARD, "center")
        cell(ws, r, 5, p.get("city"), font(8.5, False, MUTED), CARD, "center")
        cell(ws, r, 6, p.get("lon"), font(8, False, MUTED, name=MONO), CARD, "center", fmt="0.00")
        cell(ws, r, 7, p.get("lat"), font(8, False, MUTED, name=MONO), CARD, "center", fmt="0.00")
        cell(ws, r, 8, p.get("process"), font(8.5, True, BLUE), CARD, "center")
        cell(ws, r, 9, p.get("capacity"), font(9.5, True, INK), CARD, "center", fmt="#,##0")
        cell(ws, r, 10, p.get("cap_year"), font(8, False, MUTED), CARD, "center")
        cell(ws, r, 11, p.get("products"), font(8, False, MUTED), CARD)
        cell(ws, r, 12, p.get("km"), font(9, False, INK), CARD, "center")
        cell(ws, r, 13, p.get("band"), font(8, False, MUTED), CARD, "center")
        cell(ws, r, 14, p.get("note"), font(8, False, MUTED), CARD)
        grade_cell(ws, r, 15, p.get("grade", "B"))
        src_cell(ws, r, 16, D, p.get("source_ids"))
        ws.row_dimensions[r].height = max(28, cjk_height(p.get("note"), widths[13], 22))
    tr = 5 + len(D["plants"])
    total_row(ws, tr, len(cols), "合计 / 样本", [D["total_cap"]], "工厂产能合计应等于企业矩阵合计", start_col=9, label_span=8)
    note(ws, tr + 2, "注：经纬度用于距离计算与地图定位；距离为直线距离，不是铁路/水运运距。工厂备注保留公开口径差异。", len(cols))
    ws.freeze_panes = "D5"; ws.auto_filter.ref = f"A4:P{4 + len(D['plants'])}"; ws.print_area = f"A1:P{tr + 2}"
    page_setup(ws, landscape=True)
    return ws


def sheet_projects(wb, D):
    ws = wb.create_sheet("03_新增项目")
    ws.sheet_view.showGridLines = False
    cols = ["#", "企业", "项目", "地点", "工艺", "规模\n万吨/年", "性质", "状态", "预计\n年份", "时间 / 进展", "净增判断", "对目标区域的影响", "等级", "来源"]
    widths = [5, 18, 22, 18, 9, 9, 8, 11, 7, 30, 16, 38, 7, 10]
    title_block(ws, "03 / CAPACITY PIPELINE", "新增 / 在建 / 搬迁项目", "只列公开可核实项目；毛增量不等于净增；负增量（冷修/停产/限产）须另行收集", len(cols))
    header(ws, 4, cols, widths)
    items = sorted(D.get("projects") or [], key=lambda p: (p.get("year") or 9999, -p["capacity"]))
    for i, p in enumerate(items, 1):
        r = 4 + i
        cell(ws, r, 1, i, font(9, False, MUTED), CARD, "center")
        cell(ws, r, 2, p.get("company"), font(8.5, True, INK), CARD)
        cell(ws, r, 3, p.get("name"), font(9, True, INK), CARD)
        cell(ws, r, 4, p.get("location"), font(8, False, MUTED), CARD)
        cell(ws, r, 5, p.get("process"), font(8.5, True, BLUE), CARD, "center")
        cell(ws, r, 6, p.get("capacity"), font(10, True, COPPER), CARD, "center", fmt="#,##0")
        cell(ws, r, 7, p.get("kind"), font(8, True, MUTED), CARD, "center")
        cell(ws, r, 8, p.get("status"), font(8, False, MUTED), CARD, "center")
        cell(ws, r, 9, p.get("year"), font(9, False, INK), CARD, "center")
        cell(ws, r, 10, p.get("timing"), font(8, False, MUTED), CARD)
        cell(ws, r, 11, p.get("net"), font(8, True, COPPER), CARD)
        cell(ws, r, 12, p.get("impact"), font(8, False, MUTED), CARD)
        grade_cell(ws, r, 13, p.get("grade", "B"))
        src_cell(ws, r, 14, D, p.get("source_ids"))
        for col in (10, 12):
            ws.row_dimensions[r].height = max(28, cjk_height(ws.cell(r, col).value, widths[col - 1], 22))
    tr = 5 + len(items)
    gross = sum(p["capacity"] for p in items)
    fwd = sum(p["capacity"] for p in items if p.get("year") and int(p["year"]) >= int(str(D["meta"].get("asof", "2026"))[:4]))
    ws.merge_cells(start_row=tr, start_column=1, end_row=tr, end_column=5)
    c = ws.cell(tr, 1, value="合计 / 全部项目")
    c.font = font(10, True, COPPER); c.fill = fill(TINT_AMBER); c.alignment = align("left", "center", True); c.border = border(COPPER)
    cell(ws, tr, 6, gross, font(10, True, COPPER), TINT_AMBER, "center", fmt="#,##0")
    ws.merge_cells(start_row=tr, start_column=7, end_row=tr, end_column=14)
    c = cell(ws, tr, 7, f"全部 {gross:,.0f} 万吨/年；2026+ 毛增量 {fwd:,.0f} 万吨/年；净增约 930 万吨（含搬迁/置换，需逐项核）", font(8.5, False, COPPER), TINT_AMBER, "left")
    c.border = border(COPPER)
    note(ws, tr + 2, "注：项目规模为公开口径；搬迁/技改/置换不必然增加总产能，净增判断需结合老产能退出。项目状态以公告/环评/开工报道为准。", len(cols))
    ws.freeze_panes = "C5"; ws.auto_filter.ref = f"A4:N{4 + len(items)}"; ws.print_area = f"A1:N{tr + 2}"
    page_setup(ws, landscape=True)
    return ws


def sheet_regions(wb, D):
    ws = wb.create_sheet("04_区域对照")
    ws.sheet_view.showGridLines = False
    cols = ["#", "省级区域", "样本在产\n万吨/年", "工厂", "企业", "主导工艺", "到目标\nkm", "距离带", "本地供给判断", "需求 / 空白线索", "潜客样本"]
    widths = [5, 11, 12, 7, 7, 9, 9, 16, 12, 58, 9]
    title_block(ws, "04 / REGION VIEW", "区域对照", "省级产能为样本加总；无样本≠无货，只表示无在产工厂；需求线索单独标注", len(cols))
    header(ws, 4, cols, widths)
    for i, p in enumerate(D.get("provs") or [], 1):
        r = 4 + i
        cell(ws, r, 1, i, font(9, False, MUTED), CARD, "center")
        cell(ws, r, 2, p["province"], font(10, True, INK), CARD, "center")
        cell(ws, r, 3, p.get("capacity"), font(10, True, COPPER if p.get("province") == D["target"]["province"] else INK), TINT_AMBER if p.get("province") == D["target"]["province"] else CARD, "center", fmt="#,##0")
        cell(ws, r, 4, p.get("plants", 0), font(9, False, INK), CARD, "center")
        cell(ws, r, 5, p.get("n_companies", 0), font(9, False, INK), CARD, "center")
        cell(ws, r, 6, p.get("dominant"), font(8.5, True, BLUE), CARD, "center")
        cell(ws, r, 7, p.get("km_min") if p.get("km_min") is not None else "—", font(9, False, INK), CARD, "center")
        cell(ws, r, 8, p.get("judge"), font(8, True, MUTED), CARD, "center")
        cell(ws, r, 9, "本地" if p.get("capacity") else "无在产", font(8.5, True, MUTED), CARD, "center")
        cell(ws, r, 10, (D.get("demand_by_prov") or {}).get(p["province"], ""), font(8, False, MUTED), CARD)
        cell(ws, r, 11, p.get("prospect_count", 0), font(9, False, INK), CARD, "center")
        ws.row_dimensions[r].height = max(24, cjk_height(ws.cell(r, 10).value, widths[9], 22))
    tr = 5 + len(D["provs"])
    total_row(ws, tr, len(cols), "合计 / 样本", [D["total_cap"], D["total_plants"], D["total_companies"]], "省级加总 = 企业/工厂合计")
    note(ws, tr + 2, "注：省级产能为样本加总，不是全省全部产能；无样本不等于无货。需求线索来自公开报道/协会/调研，年份见来源表。", len(cols))
    # top10 chart
    rows = [p for p in D.get("provs") or [] if p.get("capacity", 0) > 0][:10]
    ch = BarChart(); ch.type = "bar"; ch.style = 10
    ch.title = "省级样本产能 TOP 10（万吨/年）"; ch.y_axis.title = "万吨/年"
    data = Reference(ws, min_col=3, min_row=4, max_row=4 + len(rows))
    ch.add_data(data, titles_from_data=True)
    ch.series[0].cat = AxDataSource(strRef=StrRef(f="'04_区域对照'!$B$5:$B${4 + len(rows)}"))
    ch.height = 8.5; ch.width = 15; ch.legend = None
    ch.dataLabels = DataLabelList(); ch.dataLabels.showVal = True
    ws.add_chart(ch, "M4")
    ws.freeze_panes = "C5"; ws.auto_filter.ref = f"A4:K{4 + len(D['provs'])}"; ws.print_area = f"A1:K{tr + 2}"
    page_setup(ws, landscape=True)
    return ws


def sheet_target(wb, D):
    ws = wb.create_sheet("05_目标区域与潜客")
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDEFGHIJK", [8, 30, 10, 12, 30, 14, 14, 4, 45, 9, 16]):
        ws.column_dimensions[col].width = w
    ws.merge_cells("A1:K1")
    c = ws["A1"]; c.value = "05  TARGET REGION → PROSPECTS"; c.font = font(17, True, WHITE); c.fill = fill(INK); c.alignment = align("left", "center", False)
    ws.row_dimensions[1].height = 34
    ws.merge_cells("A2:K2")
    c = ws["A2"]; c.value = f"{D['target']['region']} · 示例客户：{D['target']['customer']} ｜ 先看供给梯度，再看潜客与动作"
    c.font = font(9, False, MUTED); c.fill = fill(CARD); c.alignment = align("left", "center", True)
    ws.row_dimensions[2].height = 26

    # target fact cards
    local = sum(p["capacity"] for p in D["plants"] if p.get("province") == D["target"]["province"])
    n = D.get("narrative") or {}
    facts = [
        ("目标区域", D["target"]["region"]),
        ("本地在产", f"{local:,.0f} 万吨/年"),
        ("800km 内在产", f"{sum(p['capacity'] for p in D['plants'] if p['km'] <= 800):,.0f} 万吨/年"),
        ("示例客户", D["target"]["customer_short"]),
        ("示例客户用量", f"{n.get('anchor_use_value','—')} 万吨/年（推算）" if n.get("anchor_use_value") else "—"),
    ]
    for i, (k, v) in enumerate(facts[:5]):
        r = 4 + i // 2
        col = 1 + (i % 2) * 3
        if i == 4:
            ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=7)
        else:
            ws.merge_cells(start_row=r, start_column=col, end_row=r, end_column=col + 1)
        c = ws.cell(r, col, value=k); c.font = font(8, True, MUTED); c.fill = fill(TINT_GREEN); c.alignment = align("left", "center", False); c.border = border("C9D9CE")
        # put value in next row for readability? use same row second line not possible; combine
        c.value = f"{k}\n{v}"
        c.font = font(9, True, INK)
        c.alignment = align("left", "center", True)
        ws.row_dimensions[r].height = 34

    # supply ladder
    section_bar(ws, 7, "LADDER", "供应梯度", f"从{D['target']['city']}出发，按直线距离排序", 11)
    header(ws, 8, ["顺序", "供给来源", "距离 km", "产能 万吨/年", "说明"], None)
    stops = sorted(D["plants"], key=lambda p: p["km"])[:8]
    for i, p in enumerate(stops, 1):
        r = 8 + i
        cell(ws, r, 1, i, font(9, False, MUTED), CARD, "center")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=2)
        cell(ws, r, 2, f"{p.get('company_short') or p.get('company')} · {p.get('name')}", font(9, True, INK), CARD)
        cell(ws, r, 3, p.get("km"), font(9, False, INK), CARD, "center")
        cell(ws, r, 4, p.get("capacity"), font(9, True, COPPER), CARD, "center", fmt="#,##0")
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=11)
        cell(ws, r, 5, f"{p.get('province')} {p.get('city')} · {p.get('process')} · {p.get('band')}", font(8, False, MUTED), CARD)
        ws.row_dimensions[r].height = 22
    r = 8 + len(stops) + 1
    note(ws, r, "注：距离为直线距离，不是铁路/水运运距；供应梯度用于排序，不替代到厂成本测算。", 11)

    # prospects
    top = r + 2
    section_bar(ws, top, "PROSPECTS", "区域潜客样本", f"{len(D.get('prospects') or [])} 家 · 只放可核实的规模/业务事实；用量为推算", 11)
    header(ws, top + 1, ["优先级", "客户", "城市", "赛道", "公开规模", "用量级", "使用场景", "", "为什么优先 / 下一步", "等级", "来源"], None)
    for i, p in enumerate(D.get("prospects") or [], 1):
        rr = top + 1 + i
        cell(ws, rr, 1, p.get("priority", "B"), font(10, True, COPPER if p.get("priority") == "S" else INK), TINT_AMBER if p.get("priority") == "S" else CARD, "center")
        cell(ws, rr, 2, p.get("short") or p.get("name"), font(9, True, INK), CARD)
        cell(ws, rr, 3, p.get("city"), font(8, False, MUTED), CARD, "center")
        cell(ws, rr, 4, p.get("segment"), font(8, False, MUTED), CARD)
        ws.merge_cells(start_row=rr, start_column=5, end_row=rr, end_column=5)
        cell(ws, rr, 5, p.get("scale"), font(8, False, MUTED), CARD)
        cell(ws, rr, 6, p.get("ash") or p.get("dose") or "—", font(8, False, MUTED), CARD)
        cell(ws, rr, 7, p.get("scene"), font(8, False, MUTED), CARD)
        ws.merge_cells(start_row=rr, start_column=8, end_row=rr, end_column=8)
        ws.merge_cells(start_row=rr, start_column=9, end_row=rr, end_column=9)
        cell(ws, rr, 9, f"{p.get('why')}\n→ {p.get('next')}", font(8, False, INK), CARD)
        grade_cell(ws, rr, 10, p.get("grade", "B"))
        src_cell(ws, rr, 11, D, p.get("source_ids"))
        ws.row_dimensions[rr].height = max(32, cjk_height(ws.cell(rr, 9).value, 45, 24))

    # three action cards
    act = top + 2 + len(D.get("prospects") or [])
    section_bar(ws, act, "ACTION", "销售动作卡", "从“区域空白”到“先打谁、怎么打”", 11)
    cards = n.get("prospect_conclusions") or [
        {"tag": "锚点", "title": "先把示例客户做成双源标杆", "body": "用本地+外省双源方案，先证明指标稳定性。", "foot": "目标：进入合格供应商"},
        {"tag": "复制", "title": "按赛道复制到同城/邻市", "body": "轻碱走量、重碱做认证，两条线并进。", "foot": "目标：3个月新增2家试单"},
        {"tag": "防守", "title": "在新增产能投产前锁框架", "body": "近距供给出现前锁年度框架/运费。", "foot": "目标：锁12个月框架"},
    ]
    for i, c in enumerate(cards[:3]):
        r = act + 1 + i * 2
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=11)
        cc = ws.cell(r, 1, value=f"{c.get('tag','')} ｜ {c.get('title','')}")
        cc.font = font(10, True, WHITE); cc.fill = fill(INK if i == 0 else (COPPER if i == 1 else BLUE)); cc.alignment = align("left", "center", False)
        ws.row_dimensions[r].height = 21
        ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=11)
        cc = ws.cell(r + 1, 1, value=f"{c.get('body','')}  {c.get('foot','')}")
        cc.font = font(8.5, False, INK); cc.fill = fill(CARD); cc.alignment = align("left", "center", True); cc.border = border(LINE)
        ws.row_dimensions[r + 1].height = 30

    last = act + 8
    note(ws, last, n.get("prospect_scope_note", "潜客为样本，不是全量；正式版接入潜客库后按省展开。同行不列入潜客。"), 11)
    ws.print_area = f"A1:K{last}"
    page_setup(ws, landscape=True)
    return ws


def sheet_sources(wb, D):
    ws = wb.create_sheet("06_数据来源")
    ws.sheet_view.showGridLines = False
    cols = ["ID", "机构", "标题", "日期", "链接", "用于", "等级"]
    widths = [6, 18, 44, 13, 42, 52, 7]
    title_block(ws, "06 / SOURCES", "数据来源", f"{len(D.get('sources') or [])} 条来源 · 每条产能至少能回到一个来源 · 点击链接跳原文", len(cols))
    header(ws, 4, cols, widths)
    for i, s in enumerate(D.get("sources") or [], 1):
        r = 4 + i
        cell(ws, r, 1, s.get("id"), font(9, True, BLUE), CARD, "center")
        cell(ws, r, 2, s.get("org"), font(8.5, False, MUTED), CARD)
        c = cell(ws, r, 3, s.get("title"), font(9, True, BLUE), CARD)
        if s.get("url"):
            c.hyperlink = s["url"]; c.font = font(9, True, BLUE, underline="single")
        cell(ws, r, 4, s.get("date"), font(8, False, MUTED), CARD, "center")
        c = cell(ws, r, 5, s.get("url"), font(7.5, False, MUTED), CARD)
        if s.get("url"):
            c.hyperlink = s["url"]
        cell(ws, r, 6, s.get("used"), font(8, False, INK), CARD)
        grade_cell(ws, r, 7, s.get("type", "B"))
        ws.row_dimensions[r].height = max(26, cjk_height(s.get("used"), widths[5], 22))
    tr = 5 + len(D.get("sources") or [])
    note(ws, tr + 1, "注：A 公司定期报告/政府文件；B 公司 IR/行业统计/券商拆分；C 企业公开业务信息；D 物流/覆盖推断。链接为公开网页，可能随时间失效。", len(cols))
    ws.freeze_panes = "C5"; ws.auto_filter.ref = f"A4:G{4 + len(D['sources'])}"; ws.print_area = f"A1:G{tr + 1}"
    page_setup(ws, landscape=True)
    return ws


def sheet_conflicts(wb, D):
    ws = wb.create_sheet("07_口径与冲突")
    ws.sheet_view.showGridLines = False
    cols = ["#", "冲突项", "口径 A", "口径 B", "采用", "理由", "影响"]
    widths = [5, 18, 32, 32, 26, 44, 40]
    title_block(ws, "07 / CONFLICTS", "口径冲突 · 采用判断", f"{len(D.get('conflicts') or [])} 项 · 不强行抹平，并列展示并说明采用理由；冲突本身也是数据质量信号", len(cols))
    header(ws, 4, cols, widths)
    for i, c in enumerate(D.get("conflicts") or [], 1):
        r = 4 + i
        cell(ws, r, 1, i, font(9, True, MUTED), CARD, "center")
        cell(ws, r, 2, c.get("item"), font(9.5, True, INK), CARD)
        cell(ws, r, 3, c.get("a"), font(8, False, MUTED), CARD)
        cell(ws, r, 4, c.get("b"), font(8, False, MUTED), CARD)
        cell(ws, r, 5, c.get("adopt"), font(8.5, True, COPPER), TINT_AMBER)
        cell(ws, r, 6, c.get("why"), font(8, False, MUTED), CARD)
        cell(ws, r, 7, c.get("impact"), font(8, False, MUTED), CARD)
        ws.row_dimensions[r].height = max(38, cjk_height(c.get("why"), widths[5], 24))
    tr = 5 + len(D.get("conflicts") or [])
    note(ws, tr + 1, "注：冲突项不是“错误”，而是公开口径不一致；正式版应继续用最新年报/环评/项目公告复核。", len(cols))
    ws.freeze_panes = "C5"; ws.auto_filter.ref = f"A4:G{4 + len(D['conflicts'])}"; ws.print_area = f"A1:G{tr + 1}"
    page_setup(ws, landscape=True)
    return ws


def sheet_gaps(wb, D):
    ws = wb.create_sheet("08_数据缺口与边界")
    ws.sheet_view.showGridLines = False
    cols = ["#", "类型", "条目", "说明", "对结论的影响"]
    widths = [5, 10, 24, 80, 25]
    title_block(ws, "08 / GAPS & BOUNDARIES", "数据缺口与边界", "这是下一步取证清单，不是免责声明；写清“查不到什么”比假装全知道更专业", len(cols))
    header(ws, 4, cols, widths)
    rows = []
    for g in D.get("gaps") or []:
        rows.append(("缺口", g.get("title"), g.get("body"), "可能高估或低估，需补数据后再下结论"))
    for b in D.get("boundaries") or []:
        rows.append(("边界", b.get("title"), b.get("body"), "已在报告中排除或单独标注"))
    if not rows:
        rows = [("缺口", "数据缺口待补", "至少写清样本范围、负增量、距离口径、非上市披露与潜客范围。", "避免把样本当全行业")]
    for i, (kind, title, body, impact) in enumerate(rows, 1):
        r = 4 + i
        cell(ws, r, 1, i, font(9, False, MUTED), CARD, "center")
        cell(ws, r, 2, kind, font(8.5, True, COPPER if kind == "缺口" else BLUE), CARD, "center")
        cell(ws, r, 3, title, font(9.5, True, INK), CARD)
        cell(ws, r, 4, body, font(8, False, MUTED), CARD)
        cell(ws, r, 5, impact, font(8, False, MUTED), CARD)
        ws.row_dimensions[r].height = max(30, cjk_height(body, widths[3], 22))
    tr = 5 + len(rows)
    note(ws, tr + 1, "注：缺口不是“免责声明”，而是下一轮研究的任务清单；正式版可把每条缺口转成 owner + 截止日期。", len(cols))
    ws.freeze_panes = "C5"; ws.auto_filter.ref = f"A4:E{4 + len(rows)}"; ws.print_area = f"A1:E{tr + 1}"
    page_setup(ws, landscape=True)
    return ws


def build(data_path, out_path):
    D = common.load(data_path)
    wb = Workbook()
    cover(wb, D)
    sheet_matrix(wb, D)
    sheet_plants(wb, D)
    sheet_projects(wb, D)
    sheet_regions(wb, D)
    sheet_target(wb, D)
    sheet_sources(wb, D)
    sheet_conflicts(wb, D)
    sheet_gaps(wb, D)
    # Footer date placeholder replacement; avoid touching pages later.
    for ws in wb.worksheets:
        for part in (ws.oddFooter.center, ws.oddFooter.left, ws.oddFooter.right):
            if part.text:
                part.text = part.text.replace("{{asof}}", str(D["meta"].get("asof", "")))
    wb.properties.creator = "chemical-competitor-supply-map"
    wb.properties.subject = f"{D['meta'].get('product_short')} · {D['target']['region']} · 竞争供给布局"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    wb.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("out")
    a = ap.parse_args()
    p = build(a.data, a.out)
    print("OK", p, round(os.path.getsize(p) / 1024, 1), "KB")


if __name__ == "__main__":
    main()
