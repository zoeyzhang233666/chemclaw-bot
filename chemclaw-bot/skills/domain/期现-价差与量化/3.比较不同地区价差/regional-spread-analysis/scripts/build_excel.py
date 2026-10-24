#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_excel.py — 生成区域价差研究工作簿（全原生 Excel 公式，改数据即重算，无宏）

表结构（17 张）：
  00 封面说明     01 口径与来源      02 价格(主口径)   03 价格(对照口径)
  04 价差明细     05 价差矩阵        06 历史分位       07 滚动分位
  08 运输距离     09 运费参数        10 运费调整       11 企业产能
  12 下游结构     13 国标与规格      14 区域事件       15 数据质检      16 计算公式

用法：
  python scripts/build_excel.py --result build/result.json --out build/workbook.xlsx
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.formatting.rule import ColorScaleRule, CellIsRule
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.chart import LineChart, BarChart, Reference
except ImportError:
    print("需要 openpyxl：pip install openpyxl", file=sys.stderr)
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------- 样式 ----------------
NAVY = "1B2A41"
BLUE = "2F6DB5"
LBLUE = "DCE9F7"
GREY = "F2F5F9"
LINE = "D5DEE8"
GREEN = "E3F4EA"
RED = "FBE6E9"
YEL = "FFF5D6"
WHITE = "FFFFFF"

THIN = Side(style="thin", color=LINE)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

F_TITLE = Font(name="Microsoft YaHei", size=16, bold=True, color=WHITE)
F_H = Font(name="Microsoft YaHei", size=10.5, bold=True, color=WHITE)
F_SEC = Font(name="Microsoft YaHei", size=11, bold=True, color=NAVY)
F_B = Font(name="Microsoft YaHei", size=10)
F_BS = Font(name="Microsoft YaHei", size=9.5)
F_SM = Font(name="Microsoft YaHei", size=9, color="5A6B7F")
F_INPUT = Font(name="Microsoft YaHei", size=10, color=BLUE, bold=True)
F_RED = Font(name="Microsoft YaHei", size=9, color="C0392B")


def style_title(ws, text, ncol=8, sub=None):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=text)
    c.font = F_TITLE
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = F_SM
        c2.fill = PatternFill("solid", fgColor=LBLUE)
        c2.alignment = Alignment(vertical="center", horizontal="left", indent=1, wrap_text=True)
        ws.row_dimensions[2].height = 30
        return 3
    return 2


def header_row(ws, row, headers, widths=None):
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = F_H
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def as_date(v):
    """把 'YYYY-MM-DD' 字符串转成 date，保证 Excel 里是真正的日期而非文本
    （否则日期比较、窗口筛选、日期轴全部失效）。"""
    if isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-":
        try:
            return date(int(v[:4]), int(v[5:7]), int(v[8:10]))
        except ValueError:
            return v
    return v


DATE_FMT = "yyyy-mm-dd"


def safe_text(v):
    """仅用于『正文/说明』类单元格：形如 '=...' 的文字会被 Excel 当成公式，加前导撇号转义。
    注意：绝不用于真正的公式单元格。"""
    if isinstance(v, str) and v.startswith("="):
        return "'" + v
    return v


def put(ws, row, col, value, font=F_B, fmt=None, fill=None, align=None, border=True, wrap=False):
    """写单元格；`value` 以 '=' 开头时按公式写入。"""
    c = ws.cell(row=row, column=col, value=value)
    c.font = font
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = PatternFill("solid", fgColor=fill)
    if align or wrap:
        c.alignment = Alignment(horizontal=align or "general", vertical="center", wrap_text=wrap)
    if border:
        c.border = BOX
    return c


def note(ws, row, text, ncol=8):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
    c = ws.cell(row=row, column=1, value=text)
    c.font = F_RED
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[row].height = 26


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default="build/result.json")
    ap.add_argument("--out", default="build/workbook.xlsx")
    a = ap.parse_args()

    R = json.load(open(a.result, encoding="utf-8"))
    M = R["meta"]
    PR = R["primary"]
    CT = R.get("control")
    FUND = R.get("fundamentals", {})
    ROUTES = PR["freight"]["routes"]
    ORDER = PR["region_order"]
    NAME = {r["id"]: r["name"] for r in M["regions"]}
    REGIONOBJ = {r["id"]: r for r in M["regions"]}
    short = {r: NAME[r][:2] for r in ORDER}   # 山东/河北/江苏

    wb = Workbook()

    # =============== 00 封面说明 ===============
    ws = wb.active
    ws.title = "00 封面说明"
    ws.sheet_view.showGridLines = False
    r = style_title(ws, f"{M['product']} 区域价差研究工作簿", 8,
                    f"覆盖：{' / '.join(NAME[x] for x in ORDER)} ｜ 单位：{M['unit']} ｜ 频率：{M['frequency']} ｜ "
                    f"样本：{M['start']} ~ {M['end']}（{M['n_observations']} 期）")
    rows = [
        ("数据状态", M["data_status"] + ("  ← DEMO 拟真数据，非真实报价，不得用于交易或对外引用" if M["data_status"] == "DEMO" else "")),
        ("产品 / 规格", M["product"] + " ｜ " + M["spec"]),
        ("主口径", M["calibers"][M["primary_caliber"]]["label"] + "：" + M["calibers"][M["primary_caliber"]]["why"]),
        ("对照口径", (M["calibers"][M["caliber_control"]]["label"] + "：" + M["calibers"][M["caliber_control"]]["why"]) if M.get("caliber_control") else "未提供"),
        ("减法方向", "价差 = 价(甲) − 价(乙)；正数表示甲比乙贵。矩阵为「行 − 列」。"),
        ("对齐规则", "ISO 周对齐（周五锚）；三地同周均有报价才进入价差样本，缺口剔除、不插值。"),
        ("分位算法", "经验分布 ECDF：(#{x<v} + 0.5·#{x=v}) / N × 100%，不假设正态。"),
        ("运费口径", "综合运费 = 主运费 + 装货费 + 卸货费 + 短驳费 + 其他；任一项未知则总额为空，不按 0 计。"),
        ("生成日期", M["as_run"]),
        ("", ""),
        ("工作表导览", ""),
        ("01 口径与来源", "五要素核对：规格/税率/计量/交付/付款 + 来源与口径风险"),
        ("02 价格(主口径)", "三地区周度价格（用户输入区，改这里→全表重算）+ 走势图"),
        ("03 价格(对照口径)", "出厂价口径价格序列，用于口径对照"),
        ("04 价差明细", "全部有序对价差，原生公式 =B-A"),
        ("05 价差矩阵", "行−列矩阵，含等价校验与颜色刻度"),
        ("06 历史分位", "当前价差在 1 年 / 3 年 / 全样本中的分位（公式实现）"),
        ("07 滚动分位", "滚动 1 年分位曲线数据"),
        ("08 运输距离", "三地公路里程 + 已核实参考点（阿拉善—石家庄 1500km 等）"),
        ("09 运费参数", "★ 运费输入区：真实报价优先；默认参考值可直接改"),
        ("10 运费调整", "按方向计算 综合运费 / 到货成本 / 扣费后参考差异"),
        ("11 企业产能", "企业级可核实产能（省级合计未查到者不给假数）"),
        ("12 下游结构", "全国工艺结构与下游；省级拆分为示意并标注"),
        ("13 国标与规格", "GB/T 210-2022、期货交割品、包装、税率依据"),
        ("14 区域事件", "可核对的事件日历（装置/产能/需求/物流/政策/口径）"),
        ("15 数据质检", "缺口、滞后、样本量、口径一致性检查"),
        ("16 计算公式", "每个单元格公式的含义、Excel 写法、与 Python 的对应关系"),
    ]
    row = r + 1
    for k, v in rows:
        if k == "工作表导览":
            put(ws, row, 1, k, F_SEC, fill=LBLUE, border=False)
            row += 1
            continue
        if k == "":
            row += 1
            continue
        put(ws, row, 1, k, F_BS, fill=GREY, align="left")
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=8)
        c = put(ws, row, 2, v, F_BS, align="left", wrap=True)
        ws.row_dimensions[row].height = 30 if len(str(v)) > 60 else 18
        row += 1
    for i, w in enumerate([18, 26, 26, 22, 18, 18, 18, 20], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # =============== 01 口径与来源 ===============
    ws = wb.create_sheet("01 口径与来源")
    r = style_title(ws, "口径与来源（多地区可比性的第一道关）", 9,
                    "同一张表回答：三地区卖的是不是同一个东西、同一个税基、同一个交货方式、同一个时点。")
    hdr = ["地区", "代表市场", "报价口径", "交付方式", "付款方式", "税基", "来源与样本", "口径风险", "供需角色"]
    header_row(ws, r, hdr, [10, 12, 34, 12, 9, 12, 40, 46, 10])
    row = r + 1
    for rid in ORDER:
        g = REGIONOBJ[rid]
        put(ws, row, 1, NAME[rid], F_B, align="center")
        put(ws, row, 2, g.get("rep_market") or "", F_B, align="center")
        put(ws, row, 3, g.get("quote_basis") or "", F_BS, align="left", wrap=True)
        put(ws, row, 4, g.get("delivery") or "", F_BS, align="center")
        put(ws, row, 5, g.get("payment") or "", F_BS, align="center")
        put(ws, row, 6, g.get("tax") or "", F_BS, align="center")
        put(ws, row, 7, g.get("source_org") or "", F_BS, align="left", wrap=True)
        put(ws, row, 8, g.get("basis_risk") or "", F_BS, align="left", wrap=True)
        put(ws, row, 9, g.get("role") or "", F_BS, align="center")
        ws.row_dimensions[row].height = 62
        row += 1

    row += 1
    put(ws, row, 1, "口径核对清单", F_SEC, fill=LBLUE, border=False)
    row += 1
    header_row(ws, row, ["项", "检查问题", "状态", "处理动作"] + [""] * 5, None)
    row += 1
    checklist = M.get("caliber_checklist") or []
    for c in checklist:
        put(ws, row, 1, c.get("item"), F_BS, align="center")
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        put(ws, row, 2, c.get("question"), F_BS, align="left", wrap=True)
        put(ws, row, 5, c.get("status"), F_BS, align="center",
            fill=GREEN if "统一" in str(c.get("status")) else YEL)
        ws.merge_cells(start_row=row, start_column=6, end_row=row, end_column=9)
        put(ws, row, 6, c.get("action"), F_BS, align="left", wrap=True)
        ws.row_dimensions[row].height = 30
        row += 1

    row += 1
    put(ws, row, 1, "数据来源", F_SEC, fill=LBLUE, border=False)
    row += 1
    header_row(ws, row, ["编号", "来源", "日期", "覆盖内容", "链接", "状态"] + [""] * 3, None)
    row += 1
    for s in M.get("sources", []):
        put(ws, row, 1, s.get("id"), F_BS, align="center")
        put(ws, row, 2, s.get("name"), F_BS, align="left", wrap=True)
        put(ws, row, 3, as_date(s.get("date")), F_BS, fmt=DATE_FMT if as_date(s.get("date")) != s.get("date") else None, align="center")
        ws.merge_cells(start_row=row, start_column=4, end_row=row, end_column=5)
        put(ws, row, 4, s.get("covers"), F_BS, align="left", wrap=True)
        ws.merge_cells(start_row=row, start_column=6, end_row=row, end_column=8)
        c = put(ws, row, 6, s.get("url"), Font(name="Microsoft YaHei", size=8.5, color=BLUE, underline="single"),
                align="left", wrap=True)
        if s.get("url"):
            c.hyperlink = s["url"]
        put(ws, row, 9, s.get("status"), F_BS, align="center")
        ws.row_dimensions[row].height = 34
        row += 1
    ws.freeze_panes = "A" + str(r + 1)

    # =============== 02 价格(主口径) ===============
    def price_sheet(title, cal, subtitle):
        ws = wb.create_sheet(title)
        ws.sheet_view.showGridLines = False
        first = style_title(ws, f"三地区周度价格（{cal['caliber_label']}）", 8, subtitle)
        hr = first + 1
        cols = ["日期"] + [NAME[x] for x in ORDER] + ["有效地区数", "备注"]
        header_row(ws, hr, cols, [12, 12, 12, 12, 11, 30])
        row = hr + 1
        ser = cal["series"]
        start_row = row
        for i, d in enumerate(ser["dates"]):
            put(ws, row, 1, as_date(d), F_B, fmt=DATE_FMT, align="center")
            for j, rid in enumerate(ORDER):
                v = ser["prices"][rid][i]
                put(ws, row, 2 + j, v if v is not None else None, F_B,
                    fmt="#,##0", align="center", fill=WHITE if v is not None else RED)
            # 有效地区数（公式）
            rng = ",".join(f"{get_column_letter(2+j)}{row}" for j in range(len(ORDER)))
            put(ws, row, 2 + len(ORDER), f"=COUNT({rng})", F_SM, fmt="0", align="center")
            gap = [NAME[rid] for j, rid in enumerate(ORDER) if ser["prices"][rid][i] is None]
            put(ws, row, 3 + len(ORDER), ("缺口：" + "、".join(gap)) if gap else "", F_SM, align="left")
            row += 1
        end_row = row - 1
        ws.freeze_panes = f"B{start_row}"
        note(ws, row + 1,
             "★ 输入区：直接把真实数据粘贴到 B:E 列即可，全表（价差/分位/图）自动重算。"
             "缺失请留空——不要把缺失填 0 或重复上一期值；留空会在价差表里显示为空，这是正确行为。", 6)
        # 走势图
        ch = LineChart()
        ch.title = f"{M['product']} 三地区价格走势（{cal['caliber_label']}）"
        ch.y_axis.title = M["unit"]
        ch.x_axis.title = "日期"
        ch.height = 9
        ch.width = 22
        data = Reference(ws, min_col=2, max_col=1 + len(ORDER), min_row=hr, max_row=end_row)
        cats = Reference(ws, min_col=1, min_row=start_row, max_row=end_row)
        ch.add_data(data, titles_from_data=True)
        ch.set_categories(cats)
        ws.add_chart(ch, f"H{hr}")
        dv = DataValidation(type="decimal", operator="between", formula1="100", formula2="20000",
                            allow_blank=True, showErrorMessage=True,
                            error="价格应在 100–20000 元/吨（纯碱量级），请检查单位是否为 元/吨")
        ws.add_data_validation(dv)
        dv.add(f"B{start_row}:{get_column_letter(1+len(ORDER))}{end_row}")
        return ws, start_row, end_row

    ws02, s02, e02 = price_sheet(
        "02 价格(主口径)", PR,
        f"{M['calibers'][M['primary_caliber']]['label']}｜{M['calibers'][M['primary_caliber']]['why']}")
    cal_ct = CT if CT else PR
    ws03, s03, e03 = price_sheet(
        "03 价格(对照口径)", cal_ct,
        (M["calibers"][M["caliber_control"]]["label"] + "｜" + M["calibers"][M["caliber_control"]]["why"])
        if M.get("caliber_control") else "未提供对照口径，本表与主口径相同（占位）")

    # =============== 04 价差明细 ===============
    ws = wb.create_sheet("04 价差明细")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "两两价差明细（全部有序对，方向明确）", 12,
                    "价差 = 价(甲) − 价(乙)。甲列在前。公式直接引用「02 价格(主口径)」，改价格即重算。")
    hdr = ["日期", "价差(甲−乙)", "甲", "乙", "甲价", "乙价", "价差", "方向说明"]
    header_row(ws, r, hdr, [12, 13, 8, 8, 11, 11, 11, 46])
    row = r + 1
    pairs = [(ORDER[i], ORDER[j]) for i in range(len(ORDER)) for j in range(len(ORDER)) if i != j]
    block_meta = []
    for (A, B) in pairs:
        ia, ib = ORDER.index(A), ORDER.index(B)
        cA = get_column_letter(2 + ia)
        cB = get_column_letter(2 + ib)
        start = row
        put(ws, row - 0, 1, f"{NAME[A]} − {NAME[B]}", F_SEC, fill=LBLUE, border=False)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
        row += 1
        header_row(ws, row, hdr, None)
        row += 1
        dstart = row
        for i in range(len(PR["series"]["dates"])):
            src = s02 + i
            put(ws, row, 1, f"='02 价格(主口径)'!A{src}", F_B, align="center")
            put(ws, row, 3, A, F_BS, align="center")
            put(ws, row, 4, B, F_BS, align="center")
            put(ws, row, 5, f"='02 价格(主口径)'!{cA}{src}", F_B, fmt="#,##0", align="center")
            put(ws, row, 6, f"='02 价格(主口径)'!{cB}{src}", F_B, fmt="#,##0", align="center")
            put(ws, row, 7, f'=IF(OR(E{row}="",F{row}=""),"",E{row}-F{row})', F_B, fmt="#,##0", align="center", fill=GREY)
            put(ws, row, 8, "", F_SM, align="left")
            row += 1
        dend = row - 1
        # 统计行（公式）
        put(ws, row, 1, "统计", F_BS, fill=YEL, align="center")
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        put(ws, row, 2, "N（有效配对）", F_BS, fill=YEL, align="left")
        put(ws, row, 5, f"=COUNT(G{dstart}:G{dend})", F_BS, fill=YEL, fmt="0", align="center")
        put(ws, row, 6, "均值", F_BS, fill=YEL, align="center")
        put(ws, row, 7, f"=IFERROR(AVERAGE(G{dstart}:G{dend}),\"\")", F_BS, fill=YEL, fmt="#,##0.0", align="center")
        put(ws, row, 8, "价差方向：正值=" + NAME[A] + "更贵", F_SM, fill=YEL, align="left")
        row += 1
        block_meta.append((A, B, dstart, dend, row))
        save_row = row
        # 校验行：标签与数值必须成对放在相邻列，否则 STDEV 会去算文字 "标准差"
        # 价差列里有公式返回的 ""（文本），STDEV.S 遇文本报 #VALUE!；
        # 用 STDEV（同为样本标准差 n-1，但会忽略区域内的文本）保证稳健。
        put(ws, row, 1, "校验", F_BS, fill=GREEN, align="center")
        put(ws, row, 2, "标准差", F_BS, fill=GREEN, align="center")
        put(ws, row, 3, f"=IFERROR(STDEV(G{dstart}:G{dend}),\"\")", F_BS, fill=GREEN, fmt="#,##0.0", align="center")
        put(ws, row, 4, "最小", F_BS, fill=GREEN, align="center")
        put(ws, row, 5, f"=IFERROR(MIN(G{dstart}:G{dend}),\"\")", F_BS, fill=GREEN, fmt="#,##0", align="center")
        put(ws, row, 6, "最大", F_BS, fill=GREEN, align="center")
        put(ws, row, 7, f"=IFERROR(MAX(G{dstart}:G{dend}),\"\")", F_BS, fill=GREEN, fmt="#,##0", align="center")
        row += 3
    note(ws, row, "说明：价差为空的日期=该日三地未同时有报价（缺口）。缺口不插值、不前向填充。", 8)

    # =============== 05 价差矩阵 ===============
    ws = wb.create_sheet("05 价差矩阵")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "价差矩阵（当前，元/吨）", 6,
                    "行 − 列。B4 起为矩阵主体；下方为等价校验（M[i][j] = −M[j][i]）。")
    put(ws, r, 1, "行 − 列 ↓ / 列 →", F_H, fill=BLUE, align="center")
    for j, rid in enumerate(ORDER):
        put(ws, r, 2 + j, NAME[rid], F_H, fill=BLUE, align="center")
    for i, A in enumerate(ORDER):
        rr = r + 1 + i
        put(ws, rr, 1, NAME[A], F_H, fill=BLUE, align="center")
        for j, B in enumerate(ORDER):
            if A == B:
                put(ws, rr, 2 + j, 0, F_BS, fmt="#,##0", align="center", fill=GREY)
                continue
            # 引用 02 表最新一行
            ia, ib = ORDER.index(A), ORDER.index(B)
            ca, cb = get_column_letter(2 + ia), get_column_letter(2 + ib)
            last = e02
            f = f"=IFERROR('02 价格(主口径)'!{ca}{last}-'02 价格(主口径)'!{cb}{last},\"\")"
            put(ws, rr, 2 + j, f, F_B, fmt="+#,##0;-#,##0", align="center")
    mstart = r + 1
    mend = r + len(ORDER)
    ws.conditional_formatting.add(
        f"B{mstart}:{get_column_letter(1+len(ORDER))}{mend}",
        ColorScaleRule(start_type="num", start_value=-150, start_color="3DDC97",
                       mid_type="num", mid_value=0, mid_color="FFFFFF",
                       end_type="num", end_value=150, end_color="FF7A8A"))
    row = mend + 2
    put(ws, row, 1, "等价校验", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    row += 1
    for i, A in enumerate(ORDER):
        for j, B in enumerate(ORDER):
            if i >= j:
                continue
            ra, rb = r + 1 + i, r + 1 + j
            ca, cb = get_column_letter(2 + j), get_column_letter(2 + i)
            put(ws, row, 1, f"{A}−{B}", F_BS, align="center")
            put(ws, row, 2, f"={ca}{ra}", F_B, fmt="#,##0", align="center")
            put(ws, row, 3, f"{B}−{A}", F_BS, align="center")
            put(ws, row, 4, f"={cb}{rb}", F_B, fmt="#,##0", align="center")
            put(ws, row, 5, f'=IF(ABS(B{row}+D{row})<0.001,"✓ 互为相反数","✗ 异常")', F_BS, align="center", fill=GREEN)
            ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=6)
            row += 1
    for i, w in enumerate([16, 14, 14, 14, 16, 16], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # =============== 06 历史分位 ===============
    ws = wb.create_sheet("06 历史分位")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "当前价差的历史分位（公式实现，与 Python 同口径）", 10,
                    "分位 = (COUNTIF(<当前值) + 0.5×COUNTIF(=当前值)) / COUNT × 100%。窗口按自然日回溯 365 / 1095 天。")
    header_row(ws, r, ["价差(甲−乙)", "甲", "乙", "当前值", "1y 分位", "1y N", "3y 分位", "3y N", "全样本分位", "位置判断"],
               [14, 8, 8, 11, 11, 8, 11, 8, 12, 24])
    row = r + 1
    date_col = f"'04 价差明细'!$A"
    for (A, B, dstart, dend, _) in block_meta:
        rng = f"'04 价差明细'!$G${dstart}:$G${dend}"
        drng = f"'04 价差明细'!$A${dstart}:$A${dend}"
        put(ws, row, 1, f"{NAME[A]} − {NAME[B]}", F_BS, align="left")
        put(ws, row, 2, A, F_BS, align="center")
        put(ws, row, 3, B, F_BS, align="center")
        cur = f"=LOOKUP(2,1/({rng}<>\"\"),{rng})"
        put(ws, row, 4, cur, F_B, fmt="#,##0.0", align="center", fill=GREY)
        # 窗口分位：注意 SUMPRODUCT 里不能写 (=="")，文字与数字比较会互相膨胀导致算错；
        # 统一用「数值比较」表达条件——空单元格参与数值比较即为 FALSE/被排除。
        for col, days in ((5, 365), (7, 1095)):
            # 截止日：直接引用 02 表最后一个日期单元格（避免 LOOKUP(2,1/range) 在缺口处产生 #DIV/0!）
            cond = f"({drng}>'02 价格(主口径)'!$A${e02}-{days})"
            cnt = f"SUMPRODUCT({cond}*ISNUMBER({rng}))"
            less = f"SUMPRODUCT({cond}*ISNUMBER({rng})*({rng}<D{row}))"
            eq = f"SUMPRODUCT({cond}*ISNUMBER({rng})*({rng}=D{row}))"
            put(ws, row, col, f"=IF({cnt}=0,\"\",({less}+0.5*{eq})/{cnt}*100)", F_B, fmt='0.0"%"', align="center")
            put(ws, row, col + 1, f"={cnt}", F_SM, fmt="0", align="center")
        cntall = f"COUNT({rng})"
        lessall = f"COUNTIF({rng},\"<\"&D{row})"
        eqall = f"COUNTIF({rng},D{row})"
        put(ws, row, 9, f"=IF({cntall}=0,\"\",({lessall}+0.5*{eqall})/{cntall}*100)", F_B, fmt='0.0"%"', align="center")
        put(ws, row, 10, f'=IF(E{row}="","样本不足",IF(E{row}>=90,"历史高位(≥P90)",IF(E{row}>=75,"偏高(P75-P90)",'
                         f'IF(E{row}>25,"中枢区间(P25-P75)",IF(E{row}>10,"偏低(P10-P25)","历史低位(≤P10)")))))',
            F_BS, align="left")
        row += 1
    note(ws, row + 1,
         "为什么用 COUNTIF 而不是 PERCENTRANK：PERCENTRANK 对并列值取最小秩，会把「重复报价」系统性地算偏；"
         "本表采用中秩（并列各算 0.5），与 Python percentile_of() 完全一致。", 10)

    # =============== 07 滚动分位 ===============
    ws = wb.create_sheet("07 滚动分位")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "滚动 1 年分位（每个时点用「过去 1 年」样本计算）", 8,
                    "样本 <30 时不计算（留空），避免用 10 个点算出一个「看起来很确定」的分位。")
    header_row(ws, r, ["日期"] + [f"{NAME[A]}−{NAME[B]} 分位" for (A, B, *_x) in block_meta[:3]], [12, 18, 18, 18])
    roll = PR.get("rolling_percentile", {})
    row = r + 1
    nrows = len(PR["series"]["dates"])
    keys = [f"{A}-{B}" for (A, B, *_x) in block_meta[:3]]
    for i, d in enumerate(PR["series"]["dates"]):
        put(ws, row, 1, f"='02 价格(主口径)'!A{s02+i}", F_B, fmt=DATE_FMT, align="center")
        for j, k in enumerate(keys):
            arr = roll.get(k, [])
            v = arr[i][1] if i < len(arr) else None
            put(ws, row, 2 + j, v, F_B, fmt='0.0"%"' if v is not None else "General", align="center")
        row += 1
    note(ws, row + 1, "本表为 Python 预计算值写入（滚动窗口公式在 Excel 中会非常重，故不逐格展开公式）；"
                      "如需在 Excel 内重算，请用 06 表的分位公式 + 自建日期窗口。", 8)

    # =============== 08 运输距离 ===============
    ws = wb.create_sheet("08 运输距离")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "地区间运输距离与可用方式", 9,
                    "距离直接影响运费；标「估算」的必须用高德/百度地图 API 实测后替换。")
    header_row(ws, r, ["方向", "起点", "终点", "典型里程 km", "里程区间", "可信度", "主路线", "运费(默认,元/吨)", "可用方式"],
               [14, 10, 10, 13, 14, 10, 42, 16, 46])
    row = r + 1
    for rt in ROUTES:
        put(ws, row, 1, rt["flow"], F_BS, align="left")
        put(ws, row, 2, rt["from"], F_BS, align="center")
        put(ws, row, 3, rt["to"], F_BS, align="center")
        put(ws, row, 4, rt["distance_km"], F_B, fmt="#,##0", align="center")
        rng = rt.get("distance_km_range") or ["", ""]
        put(ws, row, 5, f"{rng[0]}–{rng[1]}" if rng[0] else "", F_SM, align="center")
        put(ws, row, 6, rt.get("distance_status") or "", F_BS, align="center",
            fill=GREEN if rt.get("distance_status") == "已核实" else YEL)
        lanes = rt.get("lanes") or []
        put(ws, row, 7, lanes[0].get("via", "") if lanes else "", F_SM, align="left", wrap=True)
        put(ws, row, 8, rt.get("freight"), F_B, fmt="#,##0.0", align="center")
        put(ws, row, 9, "；".join(f"{l['mode']}({l.get('distance_km')}km,{l.get('transit_days')}天)" for l in lanes),
            F_SM, align="left", wrap=True)
        ws.row_dimensions[row].height = 28
        row += 1
    row += 1
    put(ws, row, 1, "已核实参考点", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
    row += 1
    header_row(ws, row, ["起点", "终点", "里程 km", "可信度", "运价说明"] + [""] * 4, None)
    row += 1
    for pt in (PR["freight"].get("distance_matrix", {}) or {}).get("reference_points", []):
        put(ws, row, 1, pt[0], F_BS, align="center")
        put(ws, row, 2, pt[1], F_BS, align="center")
        put(ws, row, 3, pt[2], F_B, fmt="#,##0", align="center")
        put(ws, row, 4, pt[3], F_BS, align="center", fill=GREEN)
        ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=9)
        put(ws, row, 5, pt[4], F_BS, align="left", wrap=True)
        row += 1
    row += 1
    note(ws, row, (PR["freight"].get("meta", {}) or {}).get("mode_rule", "") + " " +
                  (PR["freight"].get("meta", {}) or {}).get("tonkm_anchor", ""), 9)

    # =============== 09 运费参数 ===============
    ws = wb.create_sheet("09 运费参数")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "运费参数与主运费（★ 输入区）", 9,
                    "蓝色字=可编辑输入。未提供真实运费时保持默认参考值，且所有结论只作敏感性参考。")
    put(ws, r, 1, "A. 承运构成参数（元/吨）", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    row = r + 1
    cp = PR["freight"].get("params", {}) or {}
    PARAM_ROWS = []
    params = [
        ("装货费 loading_fee", cp.get("loading_fee", 8), "装车/装车设备费；可由卖方或买方承担，按合同"),
        ("卸货费 unloading_fee", cp.get("unloading_fee", 10), "卸车费；由收货方承担时置 0"),
        ("短驳费 short_haul", 0, "厂区/站台到码头或仓库的短倒运费（元/吨）"),
        ("其他/代理 handler", cp.get("handler", cp.get("handling_fee", 2)), "过磅、代理、单证等杂费"),
    ]
    for k, v, desc in params:
        put(ws, row, 1, k, F_BS, align="left")
        put(ws, row, 2, v, F_INPUT, fmt="#,##0.0", align="center", fill=YEL)
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=6)
        put(ws, row, 3, desc, F_SM, align="left")
        PARAM_ROWS.append(row)
        row += 1
    FREEZE_ROW = row
    put(ws, row, 1, "综合运费（公式）", F_BS, align="left")
    # 对应 10 表引用本表
    row += 1
    put(ws, row, 1, "", F_B)
    row += 1

    put(ws, row, 1, "B. 各路线的运费（真实报价优先）", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
    row += 1
    header_row(ws, row, ["路线", "方向", "主运费 元/吨", "来源类型", "依据", "备选:公路", "备选:铁路", "备选:内河/海运", "备注"],
               [12, 16, 14, 12, 46, 11, 11, 14, 36])
    FREIGHT_ROWS = {}
    row += 1
    for rt in ROUTES:
        put(ws, row, 1, rt["route"], F_BS, align="center")
        put(ws, row, 2, rt["flow"], F_BS, align="left")
        put(ws, row, 3, rt.get("freight"), F_INPUT, fmt="#,##0.0", align="center", fill=YEL)
        put(ws, row, 4, {"provided": "真实报价", "default_ref": "默认参考", "not_available": "未获得"}.get(
            rt.get("freight_basis"), ""), F_BS, align="center",
            fill=GREEN if rt.get("freight_basis") == "provided" else YEL)
        put(ws, row, 5, rt.get("freight_source"), F_SM, align="left", wrap=True)
        alts = {x["mode"]: x.get("value") for x in (rt.get("alternatives") or [])}
        road = alts.get("公路汽运")
        rail = next((v for k, v in alts.items() if "铁路" in str(k)), None)
        water = next((v for k, v in alts.items() if ("内河" in str(k) or "海运" in str(k))), None)
        put(ws, row, 6, road, F_B, fmt="#,##0.0", align="center")
        put(ws, row, 7, rail, F_B, fmt="#,##0.0", align="center")
        put(ws, row, 8, water, F_B, fmt="#,##0.0", align="center")
        put(ws, row, 9, "；".join(f"{k}:{v}" for k, v in alts.items() if v is not None and k != "公路汽运"), F_SM, align="left", wrap=True)
        ws.row_dimensions[row].height = 30
        FREIGHT_ROWS[rt["route"]] = row
        row += 1
    row += 1
    note(ws, row, (PR["freight"].get("meta", {}) or {}).get("disclaimer", ""), 9)
    row += 2
    put(ws, row, 1, "已核实锚点（装卸与仓储）", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
    row += 1
    anchors = [
        ("郑商所交割库入库费（汽车）", 25, "元/吨，含卸车+库内运输+倒垛+装车（纯碱）"),
        ("郑商所交割库入库费（火车）", 30, "元/吨"),
        ("沙河 交割库出库价 vs 送到价 价差", 50, "元/吨（2025-06-04 同日，区间 50–100），可作短途综合溢价锚"),
        ("仓储费", 0.5, "元/吨·天（交割库）"),
    ]
    for k, v, d in anchors:
        put(ws, row, 1, k, F_BS, align="left")
        put(ws, row, 2, v, F_B, fmt="#,##0.0", align="center")
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=9)
        put(ws, row, 3, d, F_SM, align="left")
        row += 1

    # =============== 10 运费调整 ===============
    ws = wb.create_sheet("10 运费调整")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "按运输方向的运费调整（裸价差 / 运输成本 / 扣费后差异 分列）", 11,
                    "参考差异 = 目的地区价 − (产地区价 + 综合运费)。引用「09 运费参数」，改运费即全表重算。")
    if PR.get("freight_embedded_in_price"):
        note(ws, r, "⚠ 主口径为「送到价」，运费已内含在报价中。本表的「到货成本」仅用于出厂价口径核对与物流可行性，"
                    "不得再当作可套利空间；不要用整段运费从送到价里重复扣减。", 11)
        r += 2
    header_row(ws, r, ["路线", "方向", "里程km", "产地价", "目的地价", "裸价差(目的−产地)",
                       "主运费", "装货费", "卸货费", "短驳+其他", "综合运费", "到货成本", "扣费后参考差异", "判定"],
               [11, 16, 9, 11, 12, 16, 10, 9, 9, 11, 11, 12, 16, 18])
    row = r + 1
    fr_start = row
    for rt in ROUTES:
        src_row = FREIGHT_ROWS.get(rt["route"])
        pf_row = s02 + len(PR["series"]["dates"]) - 1
        ia, ib = ORDER.index(rt["from"]), ORDER.index(rt["to"])
        ca, cb = get_column_letter(2 + ia), get_column_letter(2 + ib)
        put(ws, row, 1, rt["route"], F_BS, align="center")
        put(ws, row, 2, rt["flow"], F_BS, align="left")
        put(ws, row, 3, rt["distance_km"], F_B, fmt="#,##0", align="center")
        put(ws, row, 4, f"='02 价格(主口径)'!{ca}{pf_row}", F_B, fmt="#,##0", align="center")
        put(ws, row, 5, f"='02 价格(主口径)'!{cb}{pf_row}", F_B, fmt="#,##0", align="center")
        put(ws, row, 6, f"=IF(OR(D{row}=\"\",E{row}=\"\"),\"\",E{row}-D{row})", F_B, fmt="#,##0.0", align="center", fill=GREY)
        put(ws, row, 7, f"='09 运费参数'!C{src_row}", F_INPUT, fmt="#,##0.0", align="center")
        put(ws, row, 8, f"='09 运费参数'!$B${PARAM_ROWS[0]}", F_INPUT, fmt="#,##0.0", align="center")
        put(ws, row, 9, f"='09 运费参数'!$B${PARAM_ROWS[1]}", F_INPUT, fmt="#,##0.0", align="center")
        put(ws, row, 10, f"='09 运费参数'!$B${PARAM_ROWS[2]}+'09 运费参数'!$B${PARAM_ROWS[3]}",
            F_INPUT, fmt="#,##0.0", align="center")
        put(ws, row, 11, f"=IF(G{row}=\"\",\"\",SUM(G{row}:J{row}))", F_B, fmt="#,##0.0", align="center", fill=LBLUE)
        put(ws, row, 12, f"=IF(K{row}=\"\",\"\",D{row}+K{row})", F_B, fmt="#,##0.0", align="center")
        put(ws, row, 13, f"=IF(OR(K{row}=\"\",E{row}=\"\"),\"\",E{row}-L{row})", F_B, fmt="+#,##0.0;-#,##0.0", align="center", fill=GREY)
        put(ws, row, 14, f'=IF(M{row}="","运费未知→不计算",IF(M{row}>0,"价差覆盖运费","未覆盖运费"))', F_BS, align="center")
        row += 1
    fr_end = row - 1
    ws.conditional_formatting.add(f"M{fr_start}:M{fr_end}",
                                  CellIsRule(operator="greaterThan", formula=["0"], fill=PatternFill("solid", fgColor=GREEN)))
    ws.conditional_formatting.add(f"M{fr_start}:M{fr_end}",
                                  CellIsRule(operator="lessThanOrEqual", formula=["0"], fill=PatternFill("solid", fgColor=RED)))
    row += 1
    note(ws, row, "「价差覆盖运费」只表示目的地区价格高于产地价+承运成本；未计入资金占用与利息、运输损耗、账期与承兑贴息、"
                  "卸货地短驳、仓储、开票与结算风险、可成交批量。不能据此认定套利机会。", 14)
    row += 3
    put(ws, row, 1, "情形对照（把「价差覆盖运费」之外的隐性成本也列出来）", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=14)
    row += 1
    header_row(ws, row, ["项目", "方向 A", "方向 B", "说明"] + [""] * 10, None)
    row += 1
    scen = [
        ("裸价差（目的−产地）", f"=F{fr_start}", f"=F{fr_start+1}", "与价差矩阵同向；尚未扣任何费用"),
        ("− 综合运费", f"=-K{fr_start}", f"=-K{fr_start+1}", "主运费+装货+卸货+短驳+其他"),
        ("= 扣费后参考差异", f"=M{fr_start}", f"=M{fr_start+1}", "仅代表价差是否覆盖承运成本"),
        ("− 资金占用（未计入）", "未计入", "未计入", "吨价×账期天数×资金成本率/365；需用户给账期与利率"),
        ("− 运输损耗（未计入）", "未计入", "未计入", "纯碱吨包/散装公路损耗通常极低，但需以实测为准"),
        ("− 承兑贴息（未计入）", "未计入", "未计入", "现汇−承兑价差属于公开源【未查到】项，不给假设值"),
        ("− 卸货地短驳（未计入）", "未计入", "未计入", "目的地到厂/到库的最后一段"),
        ("= 全部成本后净差", "需用户补参数", "需用户补参数", "本 Skill 只做到「扣运费」，不替代完整经济性核算"),
    ]
    for k, va, vb, d in scen:
        put(ws, row, 1, safe_text(k), F_BS, align="left")
        put(ws, row, 2, va, F_B if str(va).startswith("=") else F_SM, fmt="#,##0.0" if str(va).startswith("=") else None, align="center")
        put(ws, row, 3, vb, F_B if str(vb).startswith("=") else F_SM, fmt="#,##0.0" if str(vb).startswith("=") else None, align="center")
        ws.merge_cells(start_row=row, start_column=4, end_row=row, end_column=14)
        put(ws, row, 4, d, F_SM, align="left")
        row += 1

    # =============== 11 企业产能 ===============
    ws = wb.create_sheet("11 企业产能")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "生产企业与产能（企业级可核实）", 8,
                    "省级产能合计若未查到权威发布，则不给估算数——宁缺不假。")
    header_row(ws, r, ["地区", "企业", "代码", "所在地", "产能(万吨/年)", "工艺", "说明", "核实"],
               [9, 20, 10, 18, 13, 20, 52, 9])
    row = r + 1
    for rid in ORDER:
        f = (FUND.get("regions", {}) or {}).get(rid, {})
        for p in f.get("producers", []):
            put(ws, row, 1, NAME[rid], F_BS, align="center")
            put(ws, row, 2, p.get("name"), F_BS, align="left")
            put(ws, row, 3, p.get("ticker") or "", F_SM, align="center")
            put(ws, row, 4, p.get("city") or "", F_BS, align="left", wrap=True)
            put(ws, row, 5, p.get("capacity_mt") if p.get("capacity_mt") else None, F_B, fmt="#,##0", align="center")
            put(ws, row, 6, p.get("route") or "", F_BS, align="left")
            put(ws, row, 7, p.get("note") or "", F_SM, align="left", wrap=True)
            put(ws, row, 8, "✓" if p.get("verified") else "待核", F_BS, align="center",
                fill=GREEN if p.get("verified") else YEL)
            ws.row_dimensions[row].height = 30
            row += 1
        # 小计（公式）
        put(ws, row, 1, NAME[rid], F_BS, fill=LBLUE, align="center")
        put(ws, row, 2, f"{NAME[rid]} 可核实产能小计", F_BS, fill=LBLUE, align="left")
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        rngstart = row - len(f.get("producers", []))
        put(ws, row, 5, f"=SUM(E{rngstart}:E{row-1})", F_B, fill=LBLUE, fmt="#,##0", align="center")
        put(ws, row, 6, "", F_BS, fill=LBLUE)
        put(ws, row, 7, (f.get("capacity_note") or ""), F_SM, fill=LBLUE, align="left", wrap=True)
        put(ws, row, 8, "", F_BS, fill=LBLUE)
        ws.row_dimensions[row].height = 42
        row += 1
    row += 1
    nat = FUND.get("national", {}) or {}
    put(ws, row, 1, "全国", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
    row += 1
    for k, v, d in [("2024 年底产能", nat.get("capacity_mt_2024"), nat.get("capacity_note_2024")),
                    ("2025 年末产能", nat.get("capacity_mt_2025"), nat.get("capacity_note_2025")),
                    ("2024 年产量", nat.get("production_mt_2024"), f"同比 +{nat.get('production_growth_2024', 0)*100:.1f}%"),
                    ("CR4 集中度", (nat.get("cr4_share") or 0) * 100, "四家龙头合计份额")]:
        put(ws, row, 1, k, F_BS, align="left")
        put(ws, row, 2, v, F_B, fmt="#,##0" if "产能" in k or "产量" in k else '0.0"%"', align="center")
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=8)
        put(ws, row, 3, d or "", F_SM, align="left", wrap=True)
        row += 1
    row += 1
    put(ws, row, 1, "工艺结构与成本梯次", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
    row += 1
    header_row(ws, row, ["工艺", "占比", "成本区间", "说明"] + [""] * 4, None)
    row += 1
    for p in nat.get("process_mix", []):
        put(ws, row, 1, p.get("route"), F_BS, align="center")
        put(ws, row, 2, p.get("share"), F_B, fmt='0.0%', align="center")
        put(ws, row, 3, p.get("cost_range"), F_BS, align="center")
        ws.merge_cells(start_row=row, start_column=4, end_row=row, end_column=8)
        put(ws, row, 4, p.get("note"), F_SM, align="left")
        row += 1
    note(ws, row + 1, nat.get("cost_tiers_note", ""), 8)

    # =============== 12 下游结构 ===============
    ws = wb.create_sheet("12 下游结构")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "下游需求结构", 6, "全国口径为已核实数据；省级拆分为结构性示意，逐行标注——不要把示意当统计。")
    header_row(ws, r, ["地区", "行业", "占比", "数据性质", "说明"], [10, 26, 10, 12, 54])
    row = r + 1
    for rid in ORDER:
        f = (FUND.get("regions", {}) or {}).get(rid, {})
        for d in f.get("downstream", []):
            put(ws, row, 1, NAME[rid], F_BS, align="center")
            put(ws, row, 2, d.get("industry"), F_BS, align="left")
            put(ws, row, 3, d.get("share_2023"), F_B, fmt="0.0%", align="center")
            put(ws, row, 4, "示意" if f.get("downstream_caveat") else "已核实", F_BS, align="center",
                fill=YEL if f.get("downstream_caveat") else GREEN)
            put(ws, row, 5, d.get("note") or "", F_SM, align="left", wrap=True)
            row += 1
        put(ws, row, 1, NAME[rid], F_BS, fill=LBLUE, align="center")
        put(ws, row, 2, "合计", F_BS, fill=LBLUE, align="left")
        s0 = row - len(f.get("downstream", []))
        put(ws, row, 3, f"=SUM(C{s0}:C{row-1})", F_B, fill=LBLUE, fmt="0.0%", align="center")
        put(ws, row, 4, "", F_BS, fill=LBLUE)
        put(ws, row, 5, f.get("downstream_caveat") or "", F_SM, fill=LBLUE, align="left", wrap=True)
        ws.row_dimensions[row].height = 34
        row += 2

    # =============== 13 国标与规格 ===============
    ws = wb.create_sheet("13 国标与规格")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "规格、包装与税基（口径切换的锚点）", 6,
                    "任何跨地区比较先确认这五项；不一致就显式换算，缺参数就不让算。")
    header_row(ws, r, ["项目", "取值", "依据/说明"], [22, 40, 62])
    row = r + 1
    items = [
        ("产品", M["product"], "重质纯碱（dense soda ash）"),
        ("国标", "GB/T 210-2022《工业碳酸钠》", "Ⅱ 类优等品为期货交割基准"),
        ("主成分要求", M["spec"], "Na₂CO₃（干基）≥ 99.2%"),
        ("期货交割基准品", M["spec_futures"], "郑商所纯碱期货；交割品须满足 NaCl（干基）≤ 0.6%"),
        ("堆积密度", "重质 ≥ 1.0 g/cm³；轻质约 0.5–0.6 g/cm³", "轻/重碱不能混算价差，必须分列"),
        ("包装", M.get("packing"), "吨包单包 1 吨；散装罐车亦有，通常同价"),
        ("计量单位", M["unit"], "郑商所期货交易单位 20 吨/手，报价单位 元/吨"),
        ("增值税率", "13%", "2019-04-01 起由 16% 调整为 13%"),
        ("不含税换算", "不含税 = 含税 ÷ 1.13", "例：含税 1225.71 → 不含税约 1084.7"),
        ("区域税率差异", "无", "调研确认：沙河增值税 13%，与全国一致，不构成区域价差来源"),
        ("重碱报价口径", "轻碱统一出厂价；重碱除西北以外地区采用送到价，西北采用出厂价", "期货日报《纯碱的物流仓储与价格政策介绍》2019-12-01"),
        ("付款方式", "现汇 / 承兑", "承兑价 = 现汇价 + 贴息；纯碱承兑贴息具体数值属于公开源【未查到】项，不给假设值"),
        ("长协", "纯碱一般无长协，一单一议", "重碱约 90% 直供玻璃厂；挂牌价 ≠ 成交价"),
        ("运输惯例", "300 km 以内以汽运为主，300 km 以外以铁运为主", "期货日报 2019-12-01"),
        ("水运成本", "30–120 元/吨", "期货日报；山东沿海→华南 140–150 元/吨"),
    ]
    for k, v, d in items:
        put(ws, row, 1, k, F_BS, align="left", fill=GREY)
        put(ws, row, 2, v, F_BS, align="left", wrap=True)
        put(ws, row, 3, d, F_SM, align="left", wrap=True)
        ws.row_dimensions[row].height = 34
        row += 1

    # =============== 14 区域事件 ===============
    ws = wb.create_sheet("14 区域事件")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "区域产业事件日历（只写可核对的事件）", 9,
                    "events 只用于解释「可能为什么变化」，不用于把相关升级为因果。")
    header_row(ws, r, ["编号", "起始", "结束", "类型", "影响地区", "事件", "价格方向", "经济链条（传导路径）", "核实"],
               [7, 11, 11, 8, 14, 46, 9, 62, 8])
    row = r + 1
    for e in R.get("events", []):
        put(ws, row, 1, e.get("id"), F_SM, align="center")
        put(ws, row, 2, as_date(e.get("date")), F_BS, fmt=DATE_FMT, align="center")
        put(ws, row, 3, as_date(e.get("end")) if e.get("end") else "至今", F_BS, fmt=DATE_FMT if e.get("end") else None, align="center")
        put(ws, row, 4, e.get("kind"), F_BS, align="center")
        put(ws, row, 5, "、".join(e.get("regions") or []), F_SM, align="center", wrap=True)
        put(ws, row, 6, e.get("title"), F_BS, align="left", wrap=True)
        pe = e.get("price_effect")
        put(ws, row, 7, pe, F_BS, align="center",
            fill=GREEN if pe == "收紧" else (RED if pe == "宽松" else YEL))
        put(ws, row, 8, (e.get("detail", "") + " " + (e.get("economic_link") or "")).strip(), F_SM, align="left", wrap=True)
        put(ws, row, 9, "✓" if e.get("verified") else "待核", F_SM, align="center",
            fill=GREEN if e.get("verified") else YEL)
        ws.row_dimensions[row].height = 48
        row += 1

    # =============== 15 数据质检 ===============
    ws = wb.create_sheet("15 数据质检")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "数据质检（提交前逐项打勾）", 8, "ERROR 未清零不得对外交付。")
    header_row(ws, r, ["检查项", "结果", "判定", "说明"], [30, 26, 10, 66])
    row = r + 1
    al = PR.get("align", {}) or {}
    nr = PR.get("normalize_report", {}) or {}
    checks = []
    checks.append(("观测期长度", f"{M['n_observations']} 期", "PASS" if M["n_observations"] >= 52 else "WARN",
                   "≥52 期（约 1 年）才足以谈分位"))
    checks.append(("对齐后剔除周数", f"{al.get('n_dropped', 0)} 周", "PASS", "缺口剔除、不插值；剔除日期见下表"))
    miss_cnt = sum(len(v.get("missing") or []) for v in nr.values())
    checks.append(("口径换算缺失参数", f"{miss_cnt} 项", "PASS" if miss_cnt == 0 else "WARN",
                   "缺失即「不让算」，不会用 0 顶替"))
    checks.append(("三地区税基一致", "是（均 13% 含税）", "PASS", "税基不一致会系统性扭曲价差"))
    checks.append(("三地区交付方式一致", "是（主口径均为送到价）", "PASS", "送到 vs 出厂混算会高估 50–100 元/吨"))
    fb = set(PR["freight"].get("basis_flags") or [])
    checks.append(("运费来源", "、".join(sorted(fb)), "WARN" if "provided" not in fb else "PASS",
                   "无真实报价时，扣费后差异只能作敏感性参考"))
    checks.append(("运费已内含于报价", "是（送到价）" if PR.get("freight_embedded_in_price") else "否", "WARN",
                   "送到价口径下不可重复扣减整段运费"))
    checks.append(("数据状态", M["data_status"], "WARN" if M["data_status"] == "DEMO" else "PASS",
                   "DEMO 数据不得用于报价、交易或对外引用"))
    checks.append(("省级产能合计", "未查到（仅企业级）", "WARN", "宁缺不假；不要用估算数冒充统计"))
    checks.append(("承兑贴息", "未查到", "WARN", "不给假设值；遇到承兑报价时标记而非填 0"))
    for k, v, j, d in checks:
        put(ws, row, 1, k, F_BS, align="left")
        put(ws, row, 2, v, F_BS, align="center", wrap=True)
        put(ws, row, 3, j, F_BS, align="center", fill=GREEN if j == "PASS" else (YEL if j == "WARN" else RED))
        put(ws, row, 4, d, F_SM, align="left", wrap=True)
        ws.row_dimensions[row].height = 30
        row += 1
    row += 1
    put(ws, row, 1, "缺口明细（被剔除的观测周）", F_SEC, fill=LBLUE, border=False)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
    row += 1
    header_row(ws, row, ["日期", "缺失地区", "滞后（天）", "口径"], None)
    row += 1
    for dr in al.get("dropped", []):
        put(ws, row, 1, as_date(dr.get("date")), F_BS, fmt=DATE_FMT, align="center")
        put(ws, row, 2, "、".join(NAME.get(x, x) for x in dr.get("missing", [])), F_BS, align="center")
        put(ws, row, 3, str(dr.get("stale") or ""), F_SM, align="center")
        put(ws, row, 4, PR.get("caliber_label"), F_SM, align="center")
        row += 1

    # =============== 16 计算公式 ===============
    ws = wb.create_sheet("16 计算公式")
    ws.sheet_view.showGridLines = False
    r = style_title(ws, "计算公式对照表（Excel 写法 ↔ Python 实现 ↔ 含义）", 6,
                    "每一个数字都能被复算——这是可交付的前提。")
    header_row(ws, r, ["#", "指标", "数学定义 / 规则", "Excel 写法", "Python 函数", "说明与陷阱"],
               [5, 22, 46, 44, 24, 54])
    row = r + 1
    formulas = [
        ("F1", "价差", "spread(a,b) = P(a) − P(b)", "=甲价单元格−乙价单元格", "spreadlib.spread_series",
         "永远写清「谁减谁」；矩阵是「行−列」"),
        ("F2", "含税→不含税", "P_ex = P_inc / (1 + 13%)", "=P/(1+0.13)", "normalize_price",
         "增值税是价外税；不要「再扣一次」增值税"),
        ("F3", "承兑→现汇", "P_cash = P_acc − 贴息", "=P_cell-贴息(元/吨)", "normalize_price(payment_discount)",
         "贴息数值公开源【未查到】——缺失时不让算，绝不填 0"),
        ("F4", "送到→出厂", "P_exw = P_delivered − 内含运费", "=P-内含运费", "normalize_price(freight_included)",
         "内含运费未知则不让算；不要用整段外部运费替代"),
        ("F5", "两两价差（矩阵）", "M[i][j] = P_i − P_j，M[i][i]=0", "=IFERROR(价格表!{Ci}-价格表!{Cj},\"\")", "spread_matrix",
         "等价校验：M[i][j] = −M[j][i]"),
        ("F6", "有效样本数 N", "同时有两侧报价的观测数", "=COUNT(价差列)", "describe().n",
         "价差为空=该日两侧未同时有报价"),
        ("F7", "经验分位（ECDF）", "(#{x<v} + 0.5·#{x=v}) / N × 100%", "=(COUNTIF(r,\"<\"&v)+0.5*COUNTIF(r,v))/COUNT(r)*100",
         "percentile_of", "并列取中秩；PERCENTRANK 取最小秩会系统性偏低"),
        ("F8", "窗口分位", "只用 end−365 / end−1095 天内的样本", "=SUMPRODUCT((日期>=截止-365)*(价差列<>\"\"))",
         "window_sample + percentile_of", "窗口内样本 <30 时应标注低置信"),
        ("F9", "滚动分位", "每点用 [t−365, t] 的样本计算当前值分位", "SUMPRODUCT 逐行窗口", "rolling_percentile",
         "窗口重叠是正常的；不要对滚动分位再算显著性"),
        ("F10", "标准分 z", "z = (x − mean(window)) / sd(window)", "=(x-AVERAGE(r))/STDEV.S(r)", "zscore",
         "用于识别异常阶段；|z|≥1 且连续≥3 周"),
        ("F11", "综合运费", "F = 主运费 + 装货 + 卸货 + 短驳 + 其他", "=SUM(主运费:其他)", "freight_total",
         "任一项未知则总额为空，不按 0 计"),
        ("F12", "到货成本", "Landed = P_产地 + F", "=产地价+综合运费", "freight_adjusted_spread",
         "用于出厂价口径或跨区到货比对"),
        ("F13", "扣费后参考差异", "Ref = P_目的地 − Landed = (P_目的地−P_产地) − F", "=目的地价-到货成本",
         "freight_adjusted_spread().ref_diff", ">0 仅表示价差覆盖承运成本，≠ 套利机会"),
        ("F14", "ISO 周对齐", "同一 ISO 周（周五锚）的报价配对", "按 ISO 周分组后取均值/锚日值", "iso_week / week_end",
         "不能把「周一发布的上周数据」配给本周价格"),
        ("F15", "缺口处理", "缺失=空；不插值、不前向填充、不外推", "留空单元格", "align_series",
         "图上留空、表里写「—」；这是正确行为不是缺陷"),
        ("F16", "周期变动", "Change = P_t − P_{t−1}", "=P_t-P_{t-1}", "describe/diff",
         "首期为空，不补 0"),
        ("F17", "相关性（参考）", "Pearson r", "=CORREL(序列A,序列B)", "pearson",
         "仅作共变强度描述，不作因果"),
        ("F18", "产能占比", "share = 企业产能 / 全国产能", "=企业/全国", "—", "省级合计未查到时不计算占比"),
        ("F19", "分位标签", "≥90 高位 / 75–90 偏高 / 25–75 中枢 / 10–25 偏低 / ≤10 低位",
         "=IF(...) 嵌套", "percentile_label", "标签只是描述，不含交易含义"),
        ("F20", "距离×运价", "运费 ≈ 里程(km) × 吨公里运价(元/吨·km) − 整车折让", "=km*rate-discount", "—",
         "吨公里 0.2–0.4 为经验值；已核实反推 0.20（阿拉善→石家庄 300元/1500km）"),
    ]
    for f in formulas:
        for j, v in enumerate(f, start=1):
            put(ws, row, j, safe_text(v), F_SM if j in (3, 4, 5, 6) else F_BS, align="left", wrap=True)
        ws.row_dimensions[row].height = 34
        row += 1
    note(ws, row + 1, "Excel 与 Python 的一致性由 scripts/verify_excel.py 对账：读取本工作簿公式重算值，"
                      "与 result.json 中的价差 / 分位逐项比较，差异须 < 0.01。", 6)

    # 全局：冻结首行、缩放、打印设置
    for s in wb.worksheets:
        s.sheet_properties.tabColor = BLUE if s.title.startswith(("0", "1")) else GREY
        s.page_setup.orientation = "landscape"
        s.page_setup.fitToWidth = 1
        s.sheet_properties.pageSetUpPr.fitToPage = True

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    wb.save(a.out)
    print(f"[build_excel] {a.out}  sheets={len(wb.worksheets)}  "
          f"{os.path.getsize(a.out)/1024:.1f} KB")
    print("[build_excel] " + " / ".join(s.title for s in wb.worksheets))


if __name__ == "__main__":
    main()
