# -*- coding: utf-8 -*-
"""
build_xlsx.py — 由输入 JSON 生成含「自动重算公式」的出口报价工作簿

  python scripts/build_xlsx.py input.json -o 出口报价工作簿.xlsx [--simulated k1,k2]

关键点：
- 所有派生数字都是 **Excel 公式**，不是 Python 算好的常量；改任一项参数，全表联动。
- 缺失项单元格留空（黄色底），公式用 IF/IFERROR 包住，显示为「待查询」而不是 0 或 #VALUE!。
- 「03 费用明细」是唯一的录入区；其他表全部引用它，避免两处录入打架。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.chart import LineChart, Reference, BarChart

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from calc_engine import TERMS, VERSION  # noqa: E402

# ---------------------------------------------------------------- 样式
C_DARK = "0F1626"
C_HEAD = "1B2842"
C_ACC = "1F4E79"
C_INPUT = "FFF2CC"      # 待填（浅黄）
C_SIM = "E9D5FF"        # 模拟（浅紫）
C_CALC = "EAF1FB"       # 计算结果
C_OK = "D6F5E3"
C_WARN = "FFE8CC"
C_BAD = "FFD6D6"
C_GREY = "F2F4F7"

THIN = Side(style="thin", color="C9D4E3")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

F_TITLE = Font(name="Microsoft YaHei", size=15, bold=True, color="FFFFFF")
F_H2 = Font(name="Microsoft YaHei", size=11.5, bold=True, color="FFFFFF")
F_SEC = Font(name="Microsoft YaHei", size=10.5, bold=True, color=C_ACC)
F_TXT = Font(name="Microsoft YaHei", size=10)
F_B = Font(name="Microsoft YaHei", size=10, bold=True)
F_SM = Font(name="Microsoft YaHei", size=9, color="6B7C99")
F_MONO = Font(name="Consolas", size=9.5)

FILL_TITLE = PatternFill("solid", fgColor=C_DARK)
FILL_HEAD = PatternFill("solid", fgColor=C_HEAD)
FILL_SEC = PatternFill("solid", fgColor="DCE6F2")
FILL_INPUT = PatternFill("solid", fgColor=C_INPUT)
FILL_SIM = PatternFill("solid", fgColor=C_SIM)
FILL_CALC = PatternFill("solid", fgColor=C_CALC)
FILL_GREY = PatternFill("solid", fgColor=C_GREY)
FILL_OK = PatternFill("solid", fgColor=C_OK)

NUM2 = "#,##0.00"
NUM4 = "#,##0.0000"
PCT2 = "0.00%"
MONEY = "#,##0.00"


def title_bar(ws, text, sub, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=text)
    c.font = F_TITLE; c.fill = FILL_TITLE; c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 34
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c = ws.cell(row=2, column=1, value=sub)
    c.font = F_SM; c.fill = PatternFill("solid", fgColor="2A3A57"); c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 22


def head_row(ws, row, cols, widths=None):
    for i, v in enumerate(cols, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = F_H2; c.fill = FILL_HEAD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def section(ws, row, text, ncols):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = F_SEC; c.fill = FILL_SEC
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[row].height = 22


def _looks_like_formula(v: str) -> bool:
    """区分真正的 Excel 公式与「以 = 开头的说明文字」。

    规则（只做判定，不做改写）：
      1. 必须是 "=" 开头；
      2. 把 **单引号/双引号内部的文本** 剥掉之后，若仍含中文字符 → 说明文字；
      3. 形如 "=USD/柜 × 汇率" 这种用空格分隔的 "× ÷" 表达式 → 说明文字。
    """
    if not isinstance(v, str) or not v.startswith("=") or len(v) < 2:
        return False
    body = v[1:]
    if body.startswith(" "):
        return False
    # 去掉引号内文字（工作表名、字符串常量）
    stripped = []
    q = None
    for ch in body:
        if q:
            if ch == q:
                q = None
            continue
        if ch in ("\'", '"'):
            q = ch
            continue
        stripped.append(ch)
    outside = "".join(stripped)
    if any("\u4e00" <= ch <= "\u9fff" for ch in outside):
        return False
    if "\u00d7" in outside and " " in outside:   # × 带空格
        return False
    if "\u00f7" in outside and " " in outside:   # ÷ 带空格
        return False
    return True


def put(ws, row, col, value, fmt=None, font=F_TXT, fill=None, align=None, border=True, wrap=False):
    # 说明性文字若以 = 开头会被 Excel 当成公式（如 "=03!EXW" 这种示意写法），统一转成纯文本
    if isinstance(value, str) and value.startswith("=") and not _looks_like_formula(value):
        value = "'" + value
    c = ws.cell(row=row, column=col, value=value)
    c.font = font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if border: c.border = BOX
    c.alignment = Alignment(horizontal=align or ("left" if isinstance(value, str) and not str(value).startswith("=") else "right"),
                            vertical="center", wrap_text=wrap)
    return c


# ---------------------------------------------------------------- 主构建
def build(input_path: str, out_path: str, simulated: list[str]) -> dict:
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    I = {k: v for k, v in raw.items() if not k.startswith("_")}
    sim = set(simulated)
    today = dt.date.today().isoformat()

    wb = Workbook()

    # =========================================================== 01 基础参数
    ws = wb.active
    ws.title = "01 基础参数"
    ws.sheet_properties.tabColor = C_ACC
    title_bar(ws, "出口报价工作簿 · 01 基础参数", f"引擎 v{VERSION} · 生成于 {today} · 本表是唯一录入区之一（与 03 表同源录入）", 6)
    r = 4
    section(ws, r, "A. 贸易主体与货物", 6); r += 1
    head_row(ws, r, ["参数", "值", "单位", "说明", "", ""], [22, 30, 12, 58, 10, 10]); r += 1
    rows_a = [
        ("产品（中文）", I.get("product_cn", ""), "", "出口品名，与报关单/装箱单一致"),
        ("产品（英文）", I.get("product_en", ""), "", "报价单与提单英文品名"),
        ("规格", I.get("spec", ""), "", "客户验收指标原话；不自行换算"),
        ("HS 编码", I.get("hs_code", ""), "", "中国海关商品编码；决定退税率与监管条件"),
        ("工厂所在地", I.get("factory_place", ""), "", "内陆段起点"),
        ("起运港", I.get("pol", ""), "", "FOB 交货点 / CFR·CIF 装运港"),
        ("目的港", I.get("pod", ""), "", "CFR·CIF 运费计至该港"),
    ]
    for k, v, u, note in rows_a:
        put(ws, r, 1, k, font=F_B)
        put(ws, r, 2, v, fill=None)
        put(ws, r, 3, u, align="center")
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        put(ws, r, 4, note, font=F_SM, align="left", wrap=True)
        r += 1

    r += 1
    section(ws, r, "B. 数量与计量单位", 6); r += 1
    put(ws, r, 1, "出口数量", font=F_B)
    c = put(ws, r, 2, I.get("quantity_mt"), NUM4, fill=FILL_INPUT, align="right")
    put(ws, r, 3, "吨 (MT)", align="center")
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    put(ws, r, 4, "报价与成本的统一计价单位；如合同按吨/袋/托盘，请先折算成吨", font=F_SM, align="left", wrap=True)
    QTY = f"'01 基础参数'!$B${r}"
    put(ws, r + 1, 1, "进口国品名/编码（可选）", font=F_SM)
    put(ws, r + 1, 2, "", fill=FILL_INPUT)
    put(ws, r + 1, 3, "", align="center")
    ws.merge_cells(start_row=r + 1, start_column=4, end_row=r + 1, end_column=6)
    put(ws, r + 1, 4, "目的国 HS 可能不同（前 6 位衔接）；DDP 时用于查进口税率", font=F_SM, align="left", wrap=True)
    r += 3

    section(ws, r, "C. 汇率（由用户提供，系统不取实时牌价）", 6); r += 1
    head_row(ws, r, ["币种", "汇率 CNY/1外币", "用途", "", "", ""]); r += 1
    fx = I.get("fx_to_cny", {}) or {}
    FX_ROWS = {}
    cur = (I.get("quote_currency") or "USD").upper()
    for ccy in ["USD", "EUR", "IDR", "CNY"]:
        put(ws, r, 1, ccy, font=F_B)
        v = 1.0 if ccy == "CNY" else fx.get(ccy)
        put(ws, r, 2, v, NUM4 if ccy != "IDR" else "0.000000", fill=FILL_INPUT, align="right")
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
        note = "基准币种（人民币）" if ccy == "CNY" else "海运费计价 / 报价展示币种" if ccy == cur else "备用"
        put(ws, r, 3, note, font=F_SM, align="left")
        FX_ROWS[ccy] = r
        r += 1
    put(ws, r, 1, "报价币种", font=F_B)
    put(ws, r, 2, cur, fill=FILL_INPUT, align="center")
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "USD / EUR / IDR / CNY", font=F_SM, align="left")
    ROW_CUR = r
    CUR_CELL = f"'01 基础参数'!$B${r}"
    r += 1
    put(ws, r, 1, "报价汇率", font=F_B)
    S1R = "'01 基础参数'"
    fx_rng = f"{S1R}!$A${FX_ROWS['USD']}:$B${FX_ROWS['CNY']}"
    put(ws, r, 2, f'=IFERROR(VLOOKUP({CUR_CELL},{fx_rng},2,FALSE),"")',
        NUM4, fill=FILL_CALC, align="right")
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "= 按报价币种自动取上述汇率", font=F_SM, align="left")
    FX_CELL = f"'01 基础参数'!$B${r}"
    r += 2

    section(ws, r, "D. 毛利口径（毛利率与成本加成率必须区分）", 6); r += 1
    put(ws, r, 1, "毛利口径", font=F_B)
    MODE_DISP = {"margin_on_price": "毛利率（按售价）", "markup_on_cost": "成本加成率（按成本）", "manual_price": "直接定价"}
    cur_mode = MODE_DISP.get(I.get("gp_mode", "margin_on_price"), "毛利率（按售价）")
    put(ws, r, 2, cur_mode, fill=FILL_INPUT, align="center")
    dv = DataValidation(type="list", formula1='"毛利率（按售价）,成本加成率（按成本）,直接定价"', allow_blank=False)
    ws.add_data_validation(dv); dv.add(ws.cell(row=r, column=2))
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "毛利率 = 毛利÷售价；成本加成率 = 毛利÷成本。8% 毛利率 ≈ 8.70% 加成率，不可混用。", font=F_SM, align="left", wrap=True)
    ROW_MODE = r; r += 1
    put(ws, r, 1, "毛利数值", font=F_B)
    put(ws, r, 2, I.get("gp_value"), "0.00%", fill=FILL_INPUT, align="right")
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "毛利率/加成率填百分比；「直接定价」时本格忽略", font=F_SM, align="left")
    GP_CELL = f"'01 基础参数'!$B${r}"; r += 1
    put(ws, r, 1, "直接定价（¥/吨）", font=F_B)
    put(ws, r, 2, I.get("manual_price_cny_per_t"), NUM2, fill=FILL_INPUT, align="right")
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "仅当口径=「直接定价」时生效", font=F_SM, align="left")
    MANUAL_CELL = f"'01 基础参数'!$B${r}"; r += 1
    put(ws, r, 1, "毛利基准术语", font=F_B)
    put(ws, r, 2, (I.get("gp_basis_term") or "FOB").upper(), fill=FILL_INPUT, align="center")
    dv2 = DataValidation(type="list", formula1='"FCA,FAS,FOB,CFR,CIF,CPT,CIP,DAP,DPU,DDP"', allow_blank=False)
    ws.add_data_validation(dv2); dv2.add(ws.cell(row=r, column=2))
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "「目标毛利」是针对哪一个术语的价格而言——不写清，FOB 与 CIF 的毛利会被混算", font=F_SM, align="left", wrap=True)
    BASIS_CELL = f"'01 基础参数'!$B${r}"; r += 2

    section(ws, r, "E. 出口退税（单列，默认不抵减报价成本）", 6); r += 1
    put(ws, r, 1, "退税率", font=F_B)
    put(ws, r, 2, I.get("refund_rate_pct"), "0.0%", fill=FILL_INPUT, align="right")
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "须按商品代码核对退税率文库；系统不默认 13%", font=F_SM, align="left")
    REFUND_RATE = f"'01 基础参数'!$B${r}"; r += 1
    put(ws, r, 1, "增值税率", font=F_B)
    put(ws, r, 2, (I.get("vat_rate_pct") or 13) / 100, "0.0%", fill=FILL_INPUT, align="right")
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "出口货物适用税率（一般 13%）", font=F_SM, align="left")
    VAT_RATE = f"'01 基础参数'!$B${r}"; r += 1
    put(ws, r, 1, "出厂成本是否含税", font=F_B)
    put(ws, r, 2, "是" if I.get("input_tax_included") else "否", fill=FILL_INPUT, align="center")
    dv3 = DataValidation(type="list", formula1='"是,否"', allow_blank=False)
    ws.add_data_validation(dv3); dv3.add(ws.cell(row=r, column=2))
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    put(ws, r, 3, "影响退税计税依据：含税价需先除 (1+税率) 还原", font=F_SM, align="left")
    TAXINCL = f"'01 基础参数'!$B${r}"; r += 2

    ws.merge_cells(start_row=r, start_column=1, end_row=r + 3, end_column=6)
    c = ws.cell(row=r, column=1, value=(
        "⚠ 使用约定\n"
        "1) 本工作簿不提供市场价、参考运价、建议毛利或税费默认值；所有费率须由用户或货代/保险公司提供。\n"
        "2) 黄色单元格 = 待填写；紫色 = 模拟演示值（SIMULATED，非实时运价）；浅蓝 = 公式自动计算，请勿手改。\n"
        "3) 缺失项留空即可，公式会显示「待查询」，不会显示 0 或 #VALUE!。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)

    ws.freeze_panes = "A5"

    # =========================================================== 02 术语与口径
    ws2 = wb.create_sheet("02 术语与口径")
    ws2.sheet_properties.tabColor = "7C5CFF"
    title_bar(ws2, "Incoterms® 2020 · 费用与风险对照", "依据 ICC IncoTerms® 2020；分段口径与 03/05 表完全对应，避免重复计费", 8)
    r = 4
    head_row(ws2, r, ["术语", "名称", "卖方承担成本段", "风险转移点", "适用运输方式", "出口清关", "海运费", "保险费"],
             [8, 26, 26, 46, 18, 10, 10, 10]); r += 1
    rows = [
        ("EXW", "工厂交货", "无（仅 S1 出厂价）", "货物在卖方场所备妥时", "任何", "买方", "买方", "买方"),
        ("FCA", "货交承运人", "S1 S2 S3", "货交买方指定承运人时", "任何", "卖方", "买方", "买方"),
        ("FAS", "船边交货", "S1 S2 S3", "货物置于船边时", "海运/内河", "卖方", "买方", "买方"),
        ("FOB", "装运港船上交货", "S1 S2 S3 S4", "装运港装上船时", "海运/内河", "卖方", "买方", "买方"),
        ("CFR", "成本加运费", "S1 S2 S3 S4 S5", "装运港装上船时（≠目的地）", "海运/内河", "卖方", "卖方", "买方"),
        ("CIF", "成本保险加运费", "S1 S2 S3 S4 S5 S6", "装运港装上船时（≠目的地）", "海运/内河", "卖方", "卖方", "卖方(≥110%, ICC C)"),
        ("CPT", "运费付至", "S1 S2 S3 S4 S5", "货交第一承运人时", "任何", "卖方", "卖方", "买方"),
        ("CIP", "运费保险付至", "S1 S2 S3 S4 S5 S6", "货交第一承运人时", "任何", "卖方", "卖方", "卖方(≥110%, ICC A)"),
        ("DAP", "目的地交货", "…+S9 目的港费用", "目的地运输工具上待卸时", "任何", "卖方", "卖方", "卖方"),
        ("DPU", "目的地卸货后交货", "…+S9（含卸货）", "目的地卸货完成后", "任何", "卖方", "卖方", "卖方"),
        ("DDP", "完税后交货", "…+S9+进口关税", "目的地已清关、待卸时", "任何", "卖方", "卖方", "卖方"),
    ]
    for t in rows:
        for i, v in enumerate(t, start=1):
            c = put(ws2, r, i, v, font=F_B if i == 1 else F_TXT, align="center" if i in (1, 5, 6, 7, 8) else "left", wrap=True)
            if t[0] in ("FOB", "CFR", "CIF"):
                c.fill = PatternFill("solid", fgColor="EAF3FF")
        r += 1
    r += 1
    ws2.merge_cells(start_row=r, start_column=1, end_row=r + 5, end_column=8)
    c = ws2.cell(row=r, column=1, value=(
        "三条最常被搞错的规则\n"
        "① CIF/CFR 的风险转移 = 装运港货物装上船，不是到达目的港；运费/保险是「费用」，不是「风险」。\n"
        "② CIF 保险费按 CIF 价 × 110% 计，默认 ICC(C)；若客户要求 ICC(A) 或更高保额，需另算保费并改条款。\n"
        "③ FOB/CIF/CFR 只能用于海运或内河运输；集装箱出口到内陆点应改用 FCA/CPT/CIP/DAP。"))
    c.font = F_TXT; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)

    # =========================================================== 03 费用明细
    ws3 = wb.create_sheet("03 费用明细")
    ws3.sheet_properties.tabColor = "3EA6FF"
    title_bar(ws3, "03 费用明细（唯一录入区）", "每条费用行只归入一个成本段 → 术语价 = 对应段之和，杜绝重复计费", 9)
    r = 4
    head_row(ws3, r, ["成本段", "代码", "成本项", "录入口径", "数值", "单位", "状态", "依据/来源", "承担方"],
             [10, 13, 26, 20, 14, 12, 12, 46, 20]); r += 1

    def src_style(key):
        return FILL_SIM if key in sim else FILL_INPUT

    def line_row(seg, code, name, basis_txt, value, unit, source, liab, fmt=NUM2, note=""):
        nonlocal r
        put(ws3, r, 1, seg, font=F_MONO, align="center")
        put(ws3, r, 2, code, font=F_MONO, align="center")
        put(ws3, r, 3, name, font=F_B, wrap=True)
        put(ws3, r, 4, basis_txt, font=F_SM, wrap=True)
        fill = FILL_SIM if source == "sim" else FILL_INPUT
        put(ws3, r, 5, value, fmt, fill=fill, align="right")
        put(ws3, r, 6, unit, align="center")
        put(ws3, r, 7, f'=IF(E{r}="","待查询",IF(E{r}=0,"0","已填"))', font=F_SM, align="center", fill=FILL_CALC)
        put(ws3, r, 8, note or source, font=F_SM, wrap=True)
        put(ws3, r, 9, liab, font=F_SM, align="center")
        cell = f"'03 费用明细'!$E${r}"
        r += 1
        return cell, r - 1

    EXW_C, _ = line_row("S1", "EXW", "出厂价（不含包装）", "¥/吨", I.get("exw_cny_per_t"), "¥/t", "user", "卖方",
                        note="不含包装与出口环节费用")
    PKG_C, _ = line_row("S2", "PKG", "包装成本", "¥/吨", I.get("packaging_cny_per_t"), "¥/t", "user", "卖方",
                        note="袋装/吨袋/托盘折吨价")
    INL_C, _ = line_row("S3", "INLAND", "内陆运输（工厂→起运港）", "¥/吨", I.get("inland_cny_per_t"), "¥/t",
                        "sim" if "inland_cny_per_t" in sim else "user", "卖方", note="货代报价")
    PORT_C, _ = line_row("S4", "PORT", "港口及报关费用", "¥/吨", I.get("port_cny_per_t"), "¥/t",
                         "sim" if "port_cny_per_t" in sim else "user", "卖方", note="THC/报关/单证/码头作业")

    # 海运费（USD/柜 → ¥/t）
    put(ws3, r, 1, "S5", font=F_MONO, align="center")
    put(ws3, r, 2, "FRT-USD", font=F_MONO, align="center")
    put(ws3, r, 3, "海运费（柜价）", font=F_B)
    put(ws3, r, 4, "USD/柜", font=F_SM)
    put(ws3, r, 5, I.get("freight_usd_per_container"), NUM2,
        fill=FILL_SIM if "freight_usd_per_container" in sim else FILL_INPUT, align="right")
    put(ws3, r, 6, "USD/柜", align="center")
    put(ws3, r, 7, f'=IF(E{r}="","待查询","已填")', font=F_SM, align="center", fill=FILL_CALC)
    put(ws3, r, 8, "货代报价（若按吨报价，直接填下一行）", font=F_SM)
    put(ws3, r, 9, "卖方", font=F_SM, align="center")
    FRTUSD_R = r; r += 1
    FRTU = f"'03 费用明细'!$E${FRTUSD_R}"       # 柜价 USD（供本表及后续各表复用）

    put(ws3, r, 1, "S5", font=F_MONO, align="center")
    put(ws3, r, 2, "LOAD", font=F_MONO, align="center")
    put(ws3, r, 3, "装柜吨数", font=F_B)
    put(ws3, r, 4, "吨/柜", font=F_SM)
    put(ws3, r, 5, I.get("container_load_mt"), NUM4,
        fill=FILL_SIM if "container_load_mt" in sim else FILL_INPUT, align="right")
    put(ws3, r, 6, "t/柜", align="center")
    put(ws3, r, 7, f'=IF(E{r}="","待查询","已填")', font=F_SM, align="center", fill=FILL_CALC)
    put(ws3, r, 8, "必须来自实际装箱方案（含 VGM 上限），不按理论满载假设", font=F_SM, wrap=True)
    put(ws3, r, 9, "计算依据", font=F_SM, align="center")
    LOAD_R = r; r += 1

    put(ws3, r, 1, "S5", font=F_MONO, align="center")
    put(ws3, r, 2, "FREIGHT", font=F_MONO, align="center")
    put(ws3, r, 3, "海运费（折算 ¥/吨）", font=F_B)
    put(ws3, r, 4, "公式：柜价×汇率÷吨数", font=F_SM)
    put(ws3, r, 5,
        '=IF(OR(<<FRTU>>="",<<LOADU>>=""),"",<<FRTU>>*<<FX>>/<<LOADU>>)',
        NUM4, fill=FILL_CALC, align="right")
    put(ws3, r, 6, "¥/t", align="center")
    put(ws3, r, 7, f'=IF(ISNUMBER(E{r}),"已算","待查询")', font=F_SM, align="center", fill=FILL_CALC)
    put(ws3, r, 8, f"='03 费用明细'!$E${FRTUSD_R} × 报价汇率 ÷ '03 费用明细'!$E${LOAD_R}", font=F_SM)
    put(ws3, r, 9, "卖方", font=F_SM, align="center")
    FRT_C = f"'03 费用明细'!$E${r}"; r += 1

    # 保险费
    put(ws3, r, 1, "S6", font=F_MONO, align="center")
    put(ws3, r, 2, "INS-RATE", font=F_MONO, align="center")
    put(ws3, r, 3, "保险费率（占 CIF）", font=F_B)
    put(ws3, r, 4, "百分数（如 0.3 表示 0.3%）", font=F_SM, wrap=True)
    put(ws3, r, 5, I.get("insurance_rate_of_cif"), "0.0000%",
        fill=FILL_SIM if "insurance_rate_of_cif" in sim else FILL_INPUT, align="right")
    put(ws3, r, 6, "%", align="center")
    put(ws3, r, 7, f'=IF(E{r}="","待查询","已填")', font=F_SM, align="center", fill=FILL_CALC)
    put(ws3, r, 8, "保险公司报价；CIF 投保金额 = CIF × 110%", font=F_SM)
    put(ws3, r, 9, "卖方(CIF)", font=F_SM, align="center")
    INSRATE_R = r; r += 1

    put(ws3, r, 1, "S6", font=F_MONO, align="center")
    put(ws3, r, 2, "INS-FLOOR", font=F_MONO, align="center")
    put(ws3, r, 3, "保单最低保费（整票）", font=F_B)
    put(ws3, r, 4, "¥/票", font=F_SM)
    put(ws3, r, 5, I.get("insurance_floor_cny"), NUM2, fill=FILL_INPUT, align="right")
    put(ws3, r, 6, "¥", align="center")
    put(ws3, r, 7, f'=IF(E{r}="","待查询","已填")', font=F_SM, align="center", fill=FILL_CALC)
    put(ws3, r, 8, "可选：按费率算出的保费低于最低保费时，按最低保费分摊", font=F_SM, wrap=True)
    put(ws3, r, 9, "卖方(CIF)", font=F_SM, align="center")
    INSFLR_R = r; r += 1

    # 出口税费
    TAX_C, _ = line_row("S7", "EXPORT_TAX", "出口关税及其他出口税费", "¥/吨",
                        I.get("export_tax_cny_per_t"), "¥/t", "user", "卖方",
                        note="HS 2836200000 出口关税 0%（海关公示）；其他出口税费另计")
    OTH_C, _ = line_row("S8", "OTHER", "其他出口费用", "¥/吨", I.get("other_cny_per_t"), "¥/t", "user", "卖方",
                        note="结汇/银行费、检验、认证、配额等")
    DEST_C, _ = line_row("S9", "DEST_PORT", "目的港费用 / 目的地交货费用", "¥/吨", I.get("dest_port_cny_per_t"),
                         "¥/t", "user", "卖方(D组)/买方(F/C组)", note="仅 DAP/DPU/DDP 由卖方承担，F/C 组不计入")

    # 常用跨表引用常量（全部指向 03 费用明细），供 04/08/09/11 表复用
    INSC = f"'03 费用明细'!$E${INSRATE_R}"      # 保险费率
    LOADU = f"'03 费用明细'!$E${LOAD_R}"        # 装柜吨数
    INSFLR = f"'03 费用明细'!$E${INSFLR_R}"     # 最低保费

    # 03 表内先以占位符书写、再统一替换（避免前向引用问题）
    _sub = {"<<FRTU>>": FRTU, "<<LOADU>>": LOADU, "<<INSC>>": INSC,
            "<<INSFLR>>": INSFLR, "<<FX>>": FX_CELL}
    for _row in ws3.iter_rows(min_row=5, max_row=r + 6, min_col=5, max_col=5):
        for _c in _row:
            if isinstance(_c.value, str) and "<<" in _c.value:
                v = _c.value
                for _k, _v in _sub.items():
                    v = v.replace(_k, _v)
                _c.value = v

    put(ws3, r + 1, 1, "说明", font=F_SM)
    ws3.merge_cells(start_row=r + 1, start_column=2, end_row=r + 5, end_column=9)
    c = ws3.cell(row=r + 1, column=2, value=(
        "• 黄色=待填，紫色=SIMULATED 模拟值，浅蓝=公式。空单元格在后续表中显示「待查询」。\n"
        "• 海运费两种录入口径：柜价（USD/柜）+ 装柜吨数 → 自动折 ¥/t；或直接把 ¥/t 填到 FREIGHT 行（覆盖公式）。\n"
        "• 保险费在 04 表按 CIF 自洽式求解，原因见 04 表脚注：用 CFR×费率会系统性低估保费。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top")

    ws3.freeze_panes = "C5"

    # =========================================================== 04 术语成本
    ws4 = wb.create_sheet("04 术语成本")
    ws4.sheet_properties.tabColor = "22C98A"
    title_bar(ws4, "04 术语成本推导（公式驱动）", "从费用链逐层累加：FOB → CFR → CIF；保险费按 CIF×110% 自洽求解", 6)
    r = 4
    head_row(ws4, r, ["项目", "符号", "公式 / 说明", "金额（¥/吨）", "校验", ""], [30, 10, 46, 18, 20, 10]); r += 1

    def calc(name, sym, formula_txt, formula, fmt=NUM4, chk=None):
        nonlocal r
        put(ws4, r, 1, name, font=F_B)
        put(ws4, r, 2, sym, font=F_MONO, align="center")
        put(ws4, r, 3, formula_txt, font=F_SM, wrap=True)
        put(ws4, r, 4, formula, fmt, fill=FILL_CALC, align="right")
        if chk: put(ws4, r, 5, chk, font=F_SM, align="center")
        cell = f"'04 术语成本'!$D${r}"
        r += 1
        return cell

    section(ws4, r, "一、成本段合计", 6); r += 1
    S1 = calc("出厂价", "S1", "03 费用明细 · EXW", f"={EXW_C}")
    S2 = calc("包装", "S2", "03 费用明细 · PKG", f"={PKG_C}")
    S3 = calc("内陆运输", "S3", "03 费用明细 · INLAND", f"={INL_C}")
    S4 = calc("港口及报关", "S4", "03 费用明细 · PORT", f"={PORT_C}")
    S5 = calc("海运费", "S5", "=USD/柜 × 汇率 ÷ 装柜吨数", f"={FRT_C}")
    S7 = calc("出口税费", "S7", "03 费用明细 · EXPORT_TAX", f"={TAX_C}")
    S8 = calc("其他出口费用", "S8", "03 费用明细 · OTHER", f"={OTH_C}")
    # 保险费放在 S7/S8 之后：它需要 CFR（含 S7/S8）才能自洽求解
    r_ins = r
    put(ws4, r, 1, "保险费", font=F_B)
    put(ws4, r, 2, "S6", font=F_MONO, align="center")
    put(ws4, r, 3, "= CFR × 1.10r /(1 − 1.10r)，r=保险费率（自洽解）", font=F_SM, wrap=True)
    put(ws4, r, 4, f'=IF(OR({INSC}="",NOT(ISNUMBER({S5}))),"",'
                   f'IFERROR(MAX(({S5}+{S1}+{S2}+{S3}+{S4}+{S7}+{S8})'
                   f'*(1.1*({INSC}/100))/(1-1.1*({INSC}/100)),'
                   f'IFERROR(\'03 费用明细\'!$E${INSFLR_R}/{QTY},0)),""))', NUM4, fill=FILL_CALC, align="right")
    S6 = f"'04 术语成本'!$D${r}"; r += 1
    S9 = calc("目的地及进口环节", "S9", "03 费用明细 · DEST_PORT（仅 D 组）", f"={DEST_C}")
    r += 1

    section(ws4, r, "二、术语成本（费用不重复）", 6); r += 1
    FOB_C = calc("FOB 成本", "CFOB", "S1+S2+S3+S4+S7+S8",
                 f'=IFERROR({S1}+{S2}+{S3}+{S4}+{S7}+{S8},"")')
    CFR_C = calc("CFR 成本", "CCFR", "CFOB + S5", f'=IFERROR({FOB_C}+{S5},"")')
    CIF_C = calc("CIF 成本", "CCIF", "CCFR + S6", f'=IFERROR({CFR_C}+{S6},"")')
    FCA_C = calc("FCA 成本（卖方场所）", "CFCA", "S1+S2（出口清关费另计）", f'=IFERROR({S1}+{S2},"")')
    r += 1
    put(ws4, r, 1, "恒等式校验", font=F_B)
    ws4.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    put(ws4, r, 2, f'=IF(AND(ISNUMBER({CFR_C}),ISNUMBER({FOB_C}),ISNUMBER({S5})),'
                   f'IF(ABS({CFR_C}-({FOB_C}+{S5}))<0.000001,"✓ CFR = FOB + 运费","✗ CFR 校验失败"),"— 待补数据")',
        font=F_B, fill=FILL_OK, align="left")
    r += 1
    put(ws4, r, 1, "恒等式校验", font=F_B)
    ws4.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    put(ws4, r, 2, f'=IF(AND(ISNUMBER({CIF_C}),ISNUMBER({CFR_C}),ISNUMBER({S6})),'
                   f'IF(ABS({CIF_C}-({CFR_C}+{S6}))<0.000001,"✓ CIF = CFR + 保险费","✗ CIF 校验失败"),"— 待补数据")',
        font=F_B, fill=FILL_OK, align="left")
    r += 1
    put(ws4, r, 1, "恒等式校验", font=F_B)
    ws4.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    put(ws4, r, 2, f'=IF(AND(ISNUMBER({S6}),ISNUMBER(\'03 费用明细\'!$E${INSRATE_R})),'
                   f'IF(ABS({S6}-IFERROR({CIF_C}*1.1*\'03 费用明细\'!$E${INSRATE_R},0))<0.0001,"✓ 保险费 = CIF × 110% × 费率","✗ 保险费校验失败"),"— 待补数据")',
        font=F_B, fill=FILL_OK, align="left")
    r += 2
    ws4.merge_cells(start_row=r, start_column=1, end_row=r + 4, end_column=6)
    c = ws4.cell(row=r, column=1, value=(
        "为什么保险费不能用 CFR × 费率？\n"
        "CIF 条款下投保金额 = 合同价值（即 CIF 价）× 110%，而 CIF 价本身含保险费——这是一个方程而非一次乘法：\n"
        "    CCIF = CCFR + 1.10 × r × CCIF    ⇒    CCIF = CCFR / (1 − 1.10r)    保险费 = 1.10 r × CCIF\n"
        "若按 CFR × 费率，会系统性低估。r=0.3% 时，低估幅度约 0.33%；r 越高差距越大。\n"
        "注：本式假设保费基于整票 CIF 金额；若保单设有最低保费，则按 最低保费 ÷ 数量 分摊（MAX 已内置）。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws4.freeze_panes = "A5"

    # =========================================================== 05 FOB/CFR/CIF 报价
    ws5 = wb.create_sheet("05 FOB-CFR-CIF报价")
    ws5.sheet_properties.tabColor = "FFB020"
    title_bar(ws5, "05 三术语报价（人民币 + 外币）", "改 01/03 任一参数，本表自动重算；毛利口径与基准术语取自 01 表", 9)
    MODE_CELL = f"'01 基础参数'!$B${ROW_MODE}"   # 必须先定义，05 表公式要用
    r = 4
    head_row(ws5, r, ["术语", "成本 ¥/t", "毛利口径", "毛利率", "加成率", "单价 ¥/t", "单价外币/t",
                      "总报价外币", "毛利总额 ¥"], [10, 14, 20, 11, 11, 14, 14, 16, 14]); r += 1
    Q_CELL_R = r
    for t in ["FCA", "FOB", "CFR", "CIF"]:
        cost_ref = {"FCA": FCA_C, "FOB": FOB_C, "CFR": CFR_C, "CIF": CIF_C}[t]
        put(ws5, r, 1, t, font=F_B, align="center")
        put(ws5, r, 2, f'=IFERROR({cost_ref},"")', NUM4, fill=FILL_CALC)
        # 毛利口径：只有当本行术语 = 基准术语时才应用用户毛利，其余显示「按 FOB/CIF 换算」的等价
        put(ws5, r, 3, f'=IF({BASIS_CELL}=A{r},{MODE_CELL},"同口径派生")', font=F_SM, align="center", wrap=True)
        put(ws5, r, 6,
            f'=IF(NOT(ISNUMBER(B{r})),"",'
            f'IF({MODE_CELL}="直接定价",IF(ISNUMBER({MANUAL_CELL}),{MANUAL_CELL},""),'
            f'IF({GP_CELL}="","",'
            f'IF({MODE_CELL}="毛利率（按售价）",IFERROR(B{r}/(1-{GP_CELL}),""),'
            f'IFERROR(B{r}*(1+{GP_CELL}),"")))))', NUM2, fill=FILL_CALC)
        put(ws5, r, 4, f'=IF(OR(NOT(ISNUMBER(F{r})),F{r}=0),"",IF(NOT(ISNUMBER(B{r})),"",(F{r}-B{r})/F{r}))', PCT2, fill=FILL_CALC)
        put(ws5, r, 5, f'=IF(OR(NOT(ISNUMBER(F{r})),NOT(ISNUMBER(B{r})),B{r}=0),"",(F{r}-B{r})/B{r})', PCT2, fill=FILL_CALC)
        put(ws5, r, 7, f'=IF(OR(NOT(ISNUMBER(F{r})),NOT(ISNUMBER({FX_CELL}))),"",F{r}/{FX_CELL})', NUM2, fill=FILL_CALC)
        put(ws5, r, 8, f'=IF(OR(G{r}="",NOT(ISNUMBER({QTY}))),"",G{r}*{QTY})', MONEY, fill=FILL_CALC)
        put(ws5, r, 9, f'=IF(OR(NOT(ISNUMBER(F{r})),NOT(ISNUMBER(B{r})),NOT(ISNUMBER({QTY}))),"",(F{r}-B{r})*{QTY})',
            MONEY, fill=FILL_CALC)
        r += 1
    r += 1
    section(ws5, r, "数量与汇率（引用 01 表）", 9); r += 1
    put(ws5, r, 1, "数量(吨)", font=F_B); put(ws5, r, 2, f"={QTY}", NUM4, fill=FILL_CALC); r += 1
    put(ws5, r, 1, "报价币种", font=F_B); put(ws5, r, 2, f"={CUR_CELL}", align="center", fill=FILL_CALC); r += 1
    put(ws5, r, 1, "汇率", font=F_B); put(ws5, r, 2, f"={FX_CELL}", NUM4, fill=FILL_CALC); r += 1
    put(ws5, r, 1, "毛利基准术语", font=F_B); put(ws5, r, 2, f"={BASIS_CELL}", align="center", fill=FILL_CALC); r += 2
    ws5.merge_cells(start_row=r, start_column=1, end_row=r + 3, end_column=9)
    c = ws5.cell(row=r, column=1, value=(
        "读法：① 成本列来自 04 表；② 毛利只对「基准术语」那一行生效（01 表设定），其余术语按同一成本链派生；\n"
        "③ 若某术语成本为「待查询」（海运费/保险费缺失），该行单价与外币价都会留空——系统不会用 0 或估算值顶替。\n"
        "④ 「直接定价」模式下，四行都用同一个手工单价（你输入的价格，系统不评判高低）。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws5.freeze_panes = "A5"

    # =========================================================== 06 汇率换算
    ws6 = wb.create_sheet("06 汇率换算")
    ws6.sheet_properties.tabColor = "FFD166"
    title_bar(ws6, "06 汇率换算与外币报价", "由 01 表汇率驱动；可在此做多币种对照（汇率仍由你录入）", 7)
    r = 4
    head_row(ws6, r, ["币种", "汇率 CNY/1", "FOB 外币/t", "CFR 外币/t", "CIF 外币/t", "CIF 总额（外币）", "备注"],
             [10, 14, 14, 14, 14, 18, 34]); r += 1
    for ccy in ["USD", "EUR", "IDR"]:
        put(ws6, r, 1, ccy, font=F_B, align="center")
        put(ws6, r, 2, f"='01 基础参数'!$B${FX_ROWS[ccy]}", NUM4 if ccy != "IDR" else "0.000000", fill=FILL_CALC)
        r += 1
    # 用 05 表的行号绑定
    S5REF = "'05 FOB-CFR-CIF报价'"
    for i, ccy in enumerate(["USD", "EUR", "IDR"]):
        rr = 5 + i
        for j, col in enumerate(["C", "D", "E"]):
            row5 = Q_CELL_R + 1 + j
            src = f"{S5REF}!$F${row5}"
            put(ws6, rr, 3 + j,
                f'=IF(OR(NOT(ISNUMBER(B{rr})),NOT(ISNUMBER({src}))),"",{src}/B{rr})',
                NUM2, fill=FILL_CALC)
        put(ws6, rr, 6, f'=IF(OR(E{rr}="",NOT(ISNUMBER({QTY}))),"",E{rr}*{QTY})', MONEY, fill=FILL_CALC)
        put(ws6, rr, 7, "外币单价 = 人民币单价 ÷ 汇率" if ccy == "USD" else "", font=F_SM)
    r = 5 + 3 + 1
    ws6.merge_cells(start_row=r, start_column=1, end_row=r + 2, end_column=7)
    c = ws6.cell(row=r, column=1, value=(
        "换算口径：外币单价 = 人民币单价 ÷（CNY/1 外币）。汇率由 01 表提供，系统不取中间价或实时牌价。\n"
        "若实际结汇采用不同汇率（如远期锁汇价、银行买入价），请把该汇率填进 01 表，而不是事后手工改外币单价。\n"
        "IDR 小数位较多，建议同时保留人民币价与美元价，避免印尼盾报价尾差。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)

    # =========================================================== 07 毛利测算
    ws7 = wb.create_sheet("07 毛利测算")
    ws7.sheet_properties.tabColor = "C084FC"
    title_bar(ws7, "07 毛利与加价测算", "毛利率 vs 成本加成率：两种口径的换算与陷阱", 6)
    r = 4
    head_row(ws7, r, ["项目", "公式", "数值", "说明", "", ""], [26, 40, 14, 44, 8, 8]); r += 1
    put(ws7, r, 1, "基准术语", font=F_B); put(ws7, r, 2, "=01!毛利基准术语", font=F_SM)
    put(ws7, r, 3, f"={BASIS_CELL}", align="center", fill=FILL_CALC); BASIS7 = r; r += 1
    put(ws7, r, 1, "基准术语成本", font=F_B)
    put(ws7, r, 2, "=IF(基准=FOB, FOB成本, IF(基准=CFR, CFR成本, CIF成本))", font=F_SM)
    put(ws7, r, 3, f'=IFERROR(CHOOSE(MATCH($C${BASIS7},{{"FCA","FOB","CFR","CIF"}},0),{FCA_C},{FOB_C},{CFR_C},{CIF_C}),"")',
        NUM4, fill=FILL_CALC); COST7 = r; r += 1
    put(ws7, r, 1, "设定毛利（口径值）", font=F_B); put(ws7, r, 2, "=01!毛利数值", font=F_SM)
    put(ws7, r, 3, f"={GP_CELL}", PCT2, fill=FILL_CALC); GP7 = r; r += 1
    put(ws7, r, 1, "若为毛利率 → 售价", font=F_B); put(ws7, r, 2, "P = C / (1 − m)", font=F_SM)
    put(ws7, r, 3, f'=IF(NOT(ISNUMBER(C{COST7})),"",IFERROR(C{COST7}/(1-C{GP7}),""))', NUM2, fill=FILL_CALC)
    P_MARGIN = r; r += 1
    put(ws7, r, 1, "若为加成率 → 售价", font=F_B); put(ws7, r, 2, "P = C × (1 + k)", font=F_SM)
    put(ws7, r, 3, f'=IF(NOT(ISNUMBER(C{COST7})),"",C{COST7}*(1+C{GP7}))', NUM2, fill=FILL_CALC)
    P_MARKUP = r; r += 1
    put(ws7, r, 1, "当前口径下的售价", font=F_B); put(ws7, r, 2, "=05 表对应术语单价", font=F_SM)
    put(ws7, r, 3, f'=IFERROR(IF($C${BASIS7}="CIF",\'05 FOB-CFR-CIF报价\'!$F${Q_CELL_R+3},'
                   f'IF($C${BASIS7}="CFR",\'05 FOB-CFR-CIF报价\'!$F${Q_CELL_R+2},'
                   f'IF($C${BASIS7}="FOB",\'05 FOB-CFR-CIF报价\'!$F${Q_CELL_R+1},\'05 FOB-CFR-CIF报价\'!$F${Q_CELL_R}))),"")',
        NUM2, fill=FILL_CALC); P_NOW = r; r += 2
    section(ws7, r, "口径换算（同一个价格，两种表述）", 6); r += 1
    head_row(ws7, r, ["毛利率 m", "对应加成率 k = m/(1−m)", "加成率 k", "对应毛利率 m = k/(1+k)", "", ""]); r += 1
    for m in [0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30]:
        put(ws7, r, 1, m, PCT2, fill=FILL_INPUT)
        put(ws7, r, 2, f"=IF(OR(A{r}=\"\",A{r}>=1),\"\",A{r}/(1-A{r}))", PCT2, fill=FILL_CALC)
        put(ws7, r, 3, m, PCT2, fill=FILL_INPUT)
        put(ws7, r, 4, f"=IF(OR(C{r}=\"\",C{r}<=-1),\"\",C{r}/(1+C{r}))", PCT2, fill=FILL_CALC)
        r += 1
    r += 1
    put(ws7, r, 1, "校验", font=F_B)
    put(ws7, r, 2, "(1+加成率)(1−毛利率) 应 = 1")
    put(ws7, r, 3, f'=IF(NOT(ISNUMBER(C{P_NOW})),"",'
                   f'IFERROR((1+((C{P_NOW}-C{COST7})/C{COST7}))*(1-((C{P_NOW}-C{COST7})/C{P_NOW})),""))',
        "0.000000", fill=FILL_CALC)
    r += 2
    ws7.merge_cells(start_row=r, start_column=1, end_row=r + 3, end_column=6)
    c = ws7.cell(row=r, column=1, value=(
        "最常见的自伤：把「成本加成 8%」写成「毛利 8%」。C=100 时，加成 8% 售价 108，毛利率只有 7.41%；\n"
        "反过来，要拿到 8% 毛利率，售价必须是 100/(1−8%) = 108.70（加成 8.70%）。按加成 8% 报价，每吨少赚 0.70。\n"
        "谈「毛利几个点」时必须同时说清：① 哪种口径 ② 针对哪个术语（FOB 还是 CIF）③ 是否含退税。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws7.freeze_panes = "A5"

    # =========================================================== 08 敏感性分析
    ws8 = wb.create_sheet("08 敏感性分析")
    ws8.sheet_properties.tabColor = "FF5D6C"
    title_bar(ws8, "08 敏感性分析（运费 / 汇率 / 毛利）", "一维情景：其余参数不变。表格全为公式，改 03 表任意项后自动重算", 8)

    # 运费敏感性
    r = 4
    section(ws8, r, "A. 海运费变动 → 三术语成本与报价（其余不变）", 8); r += 1
    head_row(ws8, r, ["运费变动", "运费 ¥/t", "FOB 成本", "CFR 成本", "CIF 成本", "CIF 单价 ¥/t", "CIF 外币/t", "毛利率"],
             [12, 14, 14, 14, 14, 15, 15, 12]); r += 1
    FRT_START = r
    for p in [-20, -10, 0, 10, 20]:
        put(ws8, r, 1, p / 100, "+0%;-0%;0%", fill=FILL_INPUT, align="center")
        put(ws8, r, 2, f'=IF(NOT(ISNUMBER({S5})),"",{S5}*(1+A{r}))', NUM4, fill=FILL_CALC)
        put(ws8, r, 3, f'=IF(NOT(ISNUMBER({FOB_C})),"",{FOB_C})', NUM4, fill=FILL_CALC)
        put(ws8, r, 4, f'=IF(NOT(ISNUMBER({FOB_C})),"",{FOB_C}+{S5}*(1+A{r}))', NUM4, fill=FILL_CALC)
        put(ws8, r, 5,
             f'=IF(OR(NOT(ISNUMBER(D{r})),NOT(ISNUMBER({INSC}))),"",IFERROR(D{r}/(1-1.1*({INSC}/100)),""))',
            NUM4, fill=FILL_CALC)
        put(ws8, r, 6, f'=IF(NOT(ISNUMBER(E{r})),"",'
                       f'IF({MODE_CELL}="直接定价",IF(ISNUMBER({MANUAL_CELL}),{MANUAL_CELL},""),'
                       f'IF({GP_CELL}="","",IF({MODE_CELL}="毛利率（按售价）",IFERROR(E{r}/(1-{GP_CELL}),""),E{r}*(1+{GP_CELL})))))',
            NUM2, fill=FILL_CALC)
        put(ws8, r, 7, f'=IF(OR(NOT(ISNUMBER(F{r})),NOT(ISNUMBER({FX_CELL}))),"",F{r}/{FX_CELL})', NUM2, fill=FILL_CALC)
        put(ws8, r, 8, f'=IF(OR(NOT(ISNUMBER(F{r})),NOT(ISNUMBER(E{r})),F{r}=0),"",(F{r}-E{r})/F{r})', PCT2, fill=FILL_CALC)
        r += 1
    FRT_END = r - 1
    # 运费图
    ch = LineChart(); ch.title = "海运费变动 → CIF 单价"; ch.y_axis.title = "¥/t"; ch.x_axis.title = "运费变动"
    ch.height = 7.5; ch.width = 15
    data = Reference(ws8, min_col=6, min_row=FRT_START - 1, max_row=FRT_END)
    cats = Reference(ws8, min_col=1, min_row=FRT_START, max_row=FRT_END)
    ch.add_data(data, titles_from_data=True); ch.set_categories(cats)
    ws8.add_chart(ch, f"J{FRT_START - 1}")

    # 汇率敏感性
    r = FRT_END + 3
    section(ws8, r, "B. 汇率变动 → 外币单价（人民币成本不变，但外币计价运费/保费折人民币会变）", 8); r += 1
    head_row(ws8, r, ["汇率变动", "汇率 CNY", "CIF 成本 ¥/t", "CIF 单价 ¥/t", "CIF 外币/t", "外币总额", "", ""],
             [12, 14, 14, 14, 14, 16, 10, 10]); r += 1
    FX_START = r
    for p in [-10, -5, 0, 5, 10]:
        put(ws8, r, 1, p / 100, "+0%;-0%;0%", fill=FILL_INPUT, align="center")
        put(ws8, r, 2, f'=IF(NOT(ISNUMBER({FX_CELL})),"",{FX_CELL}*(1+A{r}))', NUM4, fill=FILL_CALC)
        # 外币运费折人民币：柜价 × 本行汇率 ÷ 吨数；再自洽求保险
        put(ws8, r, 3,
            f'=IF(OR(NOT(ISNUMBER(B{r})),NOT(ISNUMBER({FOB_C}))),"",'
            f'IFERROR(({FOB_C}+IFERROR({FRTU}*B{r}/{LOADU},0))/(1-IFERROR(1.1*({INSC}/100),0)),""))',
            NUM4, fill=FILL_CALC)
        put(ws8, r, 4, f'=IF(NOT(ISNUMBER(C{r})),"",'
                       f'IF({MODE_CELL}="直接定价",IF(ISNUMBER({MANUAL_CELL}),{MANUAL_CELL},""),'
                       f'IF({GP_CELL}="","",IF({MODE_CELL}="毛利率（按售价）",IFERROR(C{r}/(1-{GP_CELL}),""),C{r}*(1+{GP_CELL})))))',
            NUM2, fill=FILL_CALC)
        put(ws8, r, 5, f'=IF(OR(NOT(ISNUMBER(D{r})),NOT(ISNUMBER(B{r}))),"",D{r}/B{r})', NUM2, fill=FILL_CALC)
        put(ws8, r, 6, f'=IF(OR(E{r}="",NOT(ISNUMBER({QTY}))),"",E{r}*{QTY})', MONEY, fill=FILL_CALC)
        r += 1
    FX_END = r - 1
    ch2 = LineChart(); ch2.title = "汇率变动 → 外币单价"; ch2.y_axis.title = "外币/t"; ch2.x_axis.title = "汇率变动"
    ch2.height = 7.5; ch2.width = 15
    d2 = Reference(ws8, min_col=5, min_row=FX_START - 1, max_row=FX_END)
    c2 = Reference(ws8, min_col=1, min_row=FX_START, max_row=FX_END)
    ch2.add_data(d2, titles_from_data=True); ch2.set_categories(c2)
    ws8.add_chart(ch2, f"J{FX_START - 1}")

    # 毛利敏感性
    r = FX_END + 3
    section(ws8, r, "C. 目标毛利变动 → 报价（按当前口径）", 8); r += 1
    head_row(ws8, r, ["增长率", "毛利口径值", "FOB 单价", "CFR 单价", "CIF 单价", "CIF 外币/t", "毛利/吨", ""],
             [12, 14, 14, 14, 14, 14, 14, 10]); r += 1
    GP_START = r
    for dlt in [-0.03, -0.01, 0, 0.01, 0.03]:
        put(ws8, r, 1, dlt, "+0.00%;-0.00%;0.00%", fill=FILL_INPUT, align="center")
        put(ws8, r, 2, f'=IF({GP_CELL}="","",{GP_CELL}+A{r})', "0.00%", fill=FILL_CALC)
        for j, c_ref in enumerate([FOB_C, CFR_C, CIF_C]):
            # 结构：IF( OR(...), "", IF(直接定价, ..., IF(毛利率, C/(1-m), C*(1+k)) ) )
            put(ws8, r, 3 + j, f'=IF(OR(B{r}="",NOT(ISNUMBER({c_ref}))),"",'
                               f'IF({MODE_CELL}="直接定价",IF(ISNUMBER({MANUAL_CELL}),{MANUAL_CELL},""),'
                               f'IF({MODE_CELL}="毛利率（按售价）",IFERROR({c_ref}/(1-B{r}),""),{c_ref}*(1+B{r}))))',
                NUM2, fill=FILL_CALC)
        put(ws8, r, 6, f'=IF(OR(E{r}="",NOT(ISNUMBER({FX_CELL}))),"",E{r}/{FX_CELL})', NUM2, fill=FILL_CALC)
        put(ws8, r, 7, f'=IF(OR(E{r}="",NOT(ISNUMBER({CIF_C}))),"",E{r}-{CIF_C})', NUM2, fill=FILL_CALC)
        r += 1
    GP_END = r - 1
    ch3 = LineChart(); ch3.title = "毛利变动 → 三术语单价"; ch3.y_axis.title = "¥/t"; ch3.x_axis.title = "毛利率变动"
    ch3.height = 7.5; ch3.width = 15
    d3 = Reference(ws8, min_col=3, max_col=5, min_row=GP_START - 1, max_row=GP_END)
    c3 = Reference(ws8, min_col=1, min_row=GP_START, max_row=GP_END)
    ch3.add_data(d3, titles_from_data=True); ch3.set_categories(c3)
    ws8.add_chart(ch3, f"J{GP_START - 1}")

    r = GP_END + 3
    ws8.merge_cells(start_row=r, start_column=1, end_row=r + 2, end_column=8)
    c = ws8.cell(row=r, column=1, value=(
        "读法：A 表告诉你「运费涨 10%，CIF 单价要涨多少」（它还带动保险费同向变动，所以略高于 10%×运费占比）；\n"
        "B 表告诉你「人民币升值 5%，外币报价要降多少」——注意外币计价的运费折人民币成本也同步下降；\n"
        "C 表告诉你「毛利每加 1 个百分点，价格跳多少」——越接近 100% 毛利率，曲线越陡（1/(1−m) 放大）。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)

    # =========================================================== 09 多方案
    ws9 = wb.create_sheet("09 多方案比较")
    ws9.sheet_properties.tabColor = "3EA6FF"
    title_bar(ws9, "09 多方案比较", "方案 = 一组假设（运费/汇率/毛利口径）；灰底为录入，其余为公式派生", 10)
    r = 4
    head_row(ws9, r, ["方案", "说明", "运费系数", "汇率 CNY", "毛利口径", "毛利值",
                      "FOB ¥/t", "CFR ¥/t", "CIF ¥/t", "CIF 外币/t"], [16, 26, 11, 12, 20, 11, 12, 12, 12, 13])
    r += 1
    scens = [
        ("A", "基准：按 01/03 表当前值", 1, None, cur_mode, I.get("gp_value")),
        ("B", "运费上浮 30%", 1.3, None, cur_mode, I.get("gp_value")),
        ("C", "人民币升值（汇率 −5%）", 1, 0.95, cur_mode, I.get("gp_value")),
        ("D", "成本加成率口径（对照）", 1, None, "成本加成率（按成本）", I.get("gp_value")),
        ("E", "自定义", 1, None, cur_mode, I.get("gp_value")),
    ]
    for name, desc, kfr, kfx, mode, gv in scens:
        put(ws9, r, 1, name, font=F_B, align="center")
        put(ws9, r, 2, desc, font=F_SM, wrap=True)
        put(ws9, r, 3, kfr, "0.00", fill=FILL_INPUT, align="center")
        put(ws9, r, 4, f"=IFERROR({FX_CELL}*KFX,{FX_CELL})".replace("KFX", str(kfx if kfx else 1)) if kfx else f"={FX_CELL}",
            NUM4, fill=FILL_CALC)
        put(ws9, r, 5, mode, font=F_SM, align="center")
        put(ws9, r, 6, gv if gv is not None else "", "0.00%", fill=FILL_INPUT, align="center")
        # 成本：运费按系数调整，保险费随之
        put(ws9, r, 7, f'=IF(NOT(ISNUMBER({FOB_C})),"",{FOB_C})', NUM2, fill=FILL_CALC)
        put(ws9, r, 8, f'=IF(NOT(ISNUMBER({FOB_C})),"",{FOB_C}+IFERROR({S5},0)*C{r})', NUM2, fill=FILL_CALC)
        put(ws9, r, 9, f'=IF(OR(NOT(ISNUMBER(H{r})),NOT(ISNUMBER({INSC}))),"",IFERROR(H{r}/(1-1.1*({INSC}/100)),""))',
            NUM2, fill=FILL_CALC)
        put(ws9, r, 10, f'=IF(OR(NOT(ISNUMBER(I{r})),NOT(ISNUMBER(D{r}))),"",'
                        f'IF(E{r}="毛利率（按售价）",IFERROR(I{r}/(1-F{r})/D{r},""),I{r}*(1+F{r})/D{r}))',
            NUM2, fill=FILL_CALC)
        r += 1
    r += 1
    ws9.merge_cells(start_row=r, start_column=1, end_row=r + 2, end_column=10)
    c = ws9.cell(row=r, column=1, value=(
        "这些方案是「同一套成本链、不同假设」的算术对照，不是系统推荐方案。\n"
        "真实报价还需要你决定：是否锁汇、运费是否含滞期、是否需要报价有效期条款、客户要求 ICC(A) 时的额外保费。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)

    # =========================================================== 10 缺失与假设
    ws10 = wb.create_sheet("10 缺失与假设")
    ws10.sheet_properties.tabColor = "FFB020"
    title_bar(ws10, "10 缺失费用与假设清单", "这里列的每一项，都是「没有可靠依据、系统拒绝代填」的项目", 6)
    r = 4
    head_row(ws10, r, ["代码", "缺失项", "成本段", "为什么不能自动填", "补数来源", "状态"], [14, 24, 12, 46, 30, 14]); r += 1
    miss_rows = []
    chk = [
        ("FREIGHT", "海运费", "S5", I.get("freight_usd_per_container"), f"'03 费用明细'!$E${FRTUSD_R}",
         "运价随船期/箱型/货量波动，且是货代报价资产，不能跨航线外推", "货代书面报价（注明有效期）"),
        ("INSURANCE", "保险费率", "S6", I.get("insurance_rate_of_cif"), f"'03 费用明细'!$E${INSRATE_R}",
         "费率取决于航线、险别（ICC A/B/C）、免赔额与承运人，不同保司差异大", "保险公司/货代保险部报价"),
        ("INLAND", "内陆运输", "S3", I.get("inland_cny_per_t"), INL_C,
         "取决于起运地、车型、装载方式与是否含装车费", "承运人报价"),
        ("PORT", "港口及报关", "S4", I.get("port_cny_per_t"), PORT_C,
         "取决于港口/码头、THC、单证与报关代理费", "货代一票全含报价"),
        ("EXPORT_TAX", "出口税费", "S7", I.get("export_tax_cny_per_t"), TAX_C,
         "关税/出口环节税费以税则与申报要素为准", "海关税则、报关行确认"),
        ("OTHER", "其他出口费用", "S8", I.get("other_cny_per_t"), OTH_C,
         "检验/认证/结汇费按实际发生计", "银行、检验机构、认证机构"),
    ]
    for code, name, seg, val, cell, why, srctxt in chk:
        put(ws10, r, 1, code, font=F_MONO)
        put(ws10, r, 2, name, font=F_B)
        put(ws10, r, 3, seg, align="center", font=F_MONO)
        put(ws10, r, 4, why, font=F_SM, wrap=True)
        put(ws10, r, 5, srctxt, font=F_SM, wrap=True)
        put(ws10, r, 6, f'=IF({cell}="","待补","已提供")', font=F_B, align="center",
            fill=FILL_CALC if val is None else None)
        ws10.conditional_formatting.add(f"F{r}", CellIsRule(operator="equal", formula=['"待补"'],
                                                           fill=PatternFill("solid", fgColor=C_WARN)))
        miss_rows.append((code, val))
        r += 1
    r += 1
    section(ws10, r, "模拟值标注（SIMULATED · 非实时运价）", 6); r += 1
    head_row(ws10, r, ["字段", "模拟值", "用途", "必须在发给客户前替换为", "", ""]); r += 1
    simmap = {
        "freight_usd_per_container": ("海运费 USD/柜", I.get("freight_usd_per_container"), "演示完整计算流程", "货代书面报价"),
        "container_load_mt": ("装柜吨数", I.get("container_load_mt"), "把柜价折成吨价", "实际装箱方案"),
        "insurance_rate_of_cif": ("保险费率", I.get("insurance_rate_of_cif"), "演示 CIF 保险自洽求解", "保险公司费率"),
        "port_cny_per_t": ("港口及报关费", I.get("port_cny_per_t"), "演示港口段", "货代报价"),
        "inland_cny_per_t": ("内陆运输", I.get("inland_cny_per_t"), "演示内陆段", "承运人报价"),
    }
    for k in simulated:
        if k in simmap:
            nm, v, use, must = simmap[k]
            put(ws10, r, 1, nm, font=F_B); put(ws10, r, 2, v, NUM4, fill=FILL_SIM)
            put(ws10, r, 3, use, font=F_SM, wrap=True); ws10.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
            put(ws10, r, 4, must, font=F_SM, wrap=True); r += 1
    if not simulated:
        put(ws10, r, 1, "无", font=F_SM); r += 1

    # =========================================================== 11 公式与校验
    ws11 = wb.create_sheet("11 公式与校验")
    ws11.sheet_properties.tabColor = "6B7C99"
    title_bar(ws11, "11 全部计算公式与校验结果", "与 HTML 计算器、Python 引擎 calc_engine.py 同一套公式", 5)
    r = 4
    head_row(ws11, r, ["编号", "项目", "公式（Excel 等价写法）", "当前结果", "说明"], [8, 30, 62, 16, 40]); r += 1
    formulas = [
        ("F01", "海运费折吨价", "P_freight = USD/柜 × 汇率 ÷ 装柜吨数", S5, "外币计价段必须先折人民币"),
        ("F02", "保险费（CIF 自洽）", "P_ins = 1.10r × C_CIF = C_CFR × 1.10r /(1 − 1.10r)", S6, "r = 保险费率；默认 ICC(C)"),
        ("F03", "FOB 成本", "C_FOB = EXW + PKG + INLAND + PORT + TAX + OTHER", FOB_C, "到装运港上船为止"),
        ("F04", "CFR 成本", "C_CFR = C_FOB + P_freight", CFR_C, "卖方付运费，风险仍在装运港转移"),
        ("F05", "CIF 成本", "C_CIF = C_CFR + P_ins", CIF_C, "卖方投保"),
        ("F06", "毛利润", "GP = P − C", None, "毛利永远按售价口径计算"),
        ("F07", "毛利率", "m = GP / P", None, "按售价；P = C /(1−m)"),
        ("F08", "成本加成率", "k = GP / C", None, "按成本；P = C ×(1+k)"),
        ("F09", "两口径关系", "(1+k)(1−m) = 1", None, "k = m/(1−m)；m = k/(1+k)"),
        ("F10", "外币单价", "P_fx = P ÷ (CNY/1 外币)", None, "汇率由用户提供"),
        ("F11", "外币总额", "Total_fx = P_fx × 数量", None, ""),
        ("F12", "出口退税（参考）", "生产企业：离岸价 × 汇率 × 退税率；外贸企业：购进金额 × 退税率", None, "单列，不自动抵减成本"),
    ]
    frow = {}
    for code, name, fm, ref, note in formulas:
        put(ws11, r, 1, code, font=F_MONO, align="center")
        put(ws11, r, 2, name, font=F_B)
        put(ws11, r, 3, fm, font=F_MONO, wrap=True)
        if ref:
            put(ws11, r, 4, f"={ref}", NUM4, fill=FILL_CALC)
        else:
            put(ws11, r, 4, "", )
        put(ws11, r, 5, note, font=F_SM, wrap=True)
        frow[code] = r
        r += 1
    # 补上 F06-F12 的结果公式
    put(ws11, frow["F06"], 4, f'=IF(NOT(ISNUMBER({P_NOW})),"",{P_NOW}-{COST7})', NUM2, fill=FILL_CALC)
    put(ws11, frow["F07"], 4, f'=IF(NOT(ISNUMBER({P_NOW})),"",({P_NOW}-{COST7})/{P_NOW})', PCT2, fill=FILL_CALC)
    put(ws11, frow["F08"], 4, f'=IF(NOT(ISNUMBER({COST7})),"",({P_NOW}-{COST7})/{COST7})', PCT2, fill=FILL_CALC)
    put(ws11, frow["F09"], 4, f'=IF(NOT(ISNUMBER({P_NOW})),"",(1+({P_NOW}-{COST7})/{COST7})*(1-({P_NOW}-{COST7})/{P_NOW}))',
        "0.000000", fill=FILL_CALC)
    put(ws11, frow["F10"], 4, f"=IFERROR('05 FOB-CFR-CIF报价'!$G${Q_CELL_R+3},\"\")", NUM2, fill=FILL_CALC)
    put(ws11, frow["F11"], 4, f"=IFERROR('05 FOB-CFR-CIF报价'!$H${Q_CELL_R+3},\"\")", MONEY, fill=FILL_CALC)
    put(ws11, frow["F12"], 4,
        f'=IF(OR({REFUND_RATE}="",NOT(ISNUMBER({FOB_C})),NOT(ISNUMBER({QTY}))),"",'
        f'IF({TAXINCL}="是",{FOB_C}/(1+{VAT_RATE})*{REFUND_RATE}*{QTY},{FOB_C}*{REFUND_RATE}*{QTY}))',
        MONEY, fill=FILL_CALC)
    r += 1

    section(ws11, r, "校验面板", 5); r += 1
    head_row(ws11, r, ["编号", "校验项", "断言", "结果", "不通过怎么办"]); r += 1
    checks = [
        ("C1", "CFR = FOB + 运费", f'IF(ABS({CFR_C}-({FOB_C}+{S5}))<0.000001,"PASS","FAIL")', "检查 03 表海运费是否被重复计入"),
        ("C2", "CIF = CFR + 保险费", f'IF(ABS({CIF_C}-({CFR_C}+{S6}))<0.000001,"PASS","FAIL")', "检查保险费是否被重复或漏计"),
        ("C3", "保险费 = CIF×110%×费率",
         f'IF(ABS({S6}-{CIF_C}*1.1*({INSC}/100))<0.0001,"PASS","FAIL")',
         "检查保险费公式是否仍为自洽解"),
        ("C4", "(1+k)(1−m) = 1", f'IF(ABS((1+({P_NOW}-{COST7})/{COST7})*(1-({P_NOW}-{COST7})/{P_NOW})-1)<0.000001,"PASS","FAIL")',
         "检查毛利率与加成率口径是否混用"),
        ("C5", "数量已填", f'IF(ISNUMBER({QTY}),"PASS","FAIL")', "在 01 表填出口数量"),
        ("C6", "汇率已填", f'IF(AND(ISNUMBER({FX_CELL}),{FX_CELL}>0),"PASS","FAIL")', "在 01 表填报价币种汇率"),
        ("C7", "成本项完整（无待查询）", None, "在 03 表补齐 10 表所列项目"),
    ]
    for code, name, expr, fix in checks:
        put(ws11, r, 1, code, font=F_MONO, align="center")
        put(ws11, r, 2, name, font=F_B)
        if expr:
            put(ws11, r, 3, expr, font=F_MONO, wrap=True)
            put(ws11, r, 4, f"={expr}", font=F_B, align="center")
        else:
            put(ws11, r, 3, "COUNTBLANK(03 表 E 列关键行) = 0", font=F_MONO, wrap=True)
            S3R = "'03 费用明细'"
            put(ws11, r, 4,
                f'=IF(COUNTBLANK({S3R}!$E${FRTUSD_R})+COUNTBLANK({S3R}!$E${INSRATE_R})'
                f'+COUNTBLANK({S3R}!$E${LOAD_R})=0,"PASS","FAIL")',
                font=F_B, align="center")
        put(ws11, r, 5, fix, font=F_SM, wrap=True)
        ws11.conditional_formatting.add(f"D{r}", CellIsRule(operator="equal", formula=['"PASS"'],
                                                           fill=PatternFill("solid", fgColor=C_OK)))
        ws11.conditional_formatting.add(f"D{r}", CellIsRule(operator="equal", formula=['"FAIL"'],
                                                           fill=PatternFill("solid", fgColor=C_BAD)))
        r += 1
    r += 1
    ws11.merge_cells(start_row=r, start_column=1, end_row=r + 3, end_column=5)
    c = ws11.cell(row=r, column=1, value=(
        "本表公式与 HTML 计算器、scripts/calc_engine.py 完全同源；三处任何一处结果不一致，说明有人手改了中间值。\n"
        "Excel 重算方式：改 01 表汇率/毛利或 03 表任一费用 → 全表联动（含 05、06、08、09、11）。\n"
        "若某单元格显示「— 待补数据」或空白，请先看 10 表缺什么，不要用 0 顶替。"))
    c.font = F_SM; c.fill = FILL_GREY; c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)

    # =========================================================== 12 报价草稿
    ws12 = wb.create_sheet("12 报价草稿")
    ws12.sheet_properties.tabColor = "22C98A"
    title_bar(ws12, "12 英文报价草稿（需人工确认后发送）", "数字全部引用 05 表；灰底 CANNOT-SEND 区块必须删除或替换后才能外发", 6)
    r = 4
    put(ws12, r, 1, "Ref.", font=F_B); put(ws12, r, 2, f"=CONCATENATE(\"Q-\",TEXT(TODAY(),\"YYYYMMDD\"))", font=F_MONO)
    ws12.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4); r += 1
    put(ws12, r, 1, "Commodity", font=F_B); put(ws12, r, 2, I.get("product_en", "")); ws12.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4); r += 1
    put(ws12, r, 1, "HS Code", font=F_B); put(ws12, r, 2, I.get("hs_code", "")); r += 1
    put(ws12, r, 1, "Specification", font=F_B); put(ws12, r, 2, I.get("spec", "")); ws12.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4); r += 1
    put(ws12, r, 1, "Quantity", font=F_B); put(ws12, r, 2, f"={QTY}", NUM2); put(ws12, r, 3, "MT"); r += 1
    put(ws12, r, 1, "Loading port", font=F_B); put(ws12, r, 2, I.get("pol", "")); r += 1
    put(ws12, r, 1, "Destination", font=F_B); put(ws12, r, 2, I.get("pod", "")); r += 1
    r += 1
    head_row(ws12, r, ["Incoterms® 2020", "Unit price", "Currency", "Amount", "", ""]); r += 1
    for i, t in enumerate(["FOB", "CFR", "CIF"]):
        row5 = Q_CELL_R + i + 1
        put(ws12, r, 1, t, font=F_B, align="center")
        put(ws12, r, 2, f"='05 FOB-CFR-CIF报价'!$G${row5}", NUM2, fill=FILL_CALC)
        put(ws12, r, 3, f"={CUR_CELL}", align="center", fill=FILL_CALC)
        put(ws12, r, 4, f"='05 FOB-CFR-CIF报价'!$H${row5}", MONEY, fill=FILL_CALC)
        r += 1
    r += 1
    terms_lines = [
        "1. Price basis: Incoterms® 2020 as stated above.",
        "2. Risk transfer (FOB/CFR/CIF): when the goods are placed on board the vessel at the port of shipment.",
        "3. Insurance (CIF only): shall cover 110% of the invoice value, Institute Cargo Clauses (C) unless otherwise agreed. [CONFIRM required clauses with buyer]",
        "4. Payment: [TO BE CONFIRMED].",
        "5. Packing: [TO BE CONFIRMED].",
        "6. Shipment: [TO BE CONFIRMED].",
        "7. Validity: [TO BE CONFIRMED] — freight and exchange rate are the main moving parts.",
        "8. Origin: China. [Confirm whether a Certificate of Origin / preferential origin document is applicable]",
    ]
    for ln in terms_lines:
        ws12.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        put(ws12, r, 1, ln, font=F_TXT, align="left", wrap=True)
        r += 1
    ws12.merge_cells(start_row=r, start_column=1, end_row=r + 3, end_column=6)
    c = ws12.cell(row=r, column=1, value=(
        "INTERNAL NOTE — REMOVE BEFORE SENDING\n"
        "• 本报价由销售设定的成本、汇率、毛利口径计算，非系统推荐价。\n"
        "• 任何标记 SIMULATED 的运杂费/保险费必须替换为真实报价后重算（见 10 表）。\n"
        "• 出口关税、目的国进口关税与原产地优惠须单独核实，本表不自动假定为 0。"))
    c.font = Font(name="Microsoft YaHei", size=9, color="8A5A00")
    c.fill = PatternFill("solid", fgColor="FFF6E5")
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)

    # ---- 全局：网格线、冻结、打印
    for s in wb.worksheets:
        s.sheet_view.showGridLines = False
        s.page_setup.orientation = "landscape"
        s.page_setup.fitToWidth = 1
        s.sheet_properties.pageSetUpPr.fitToPage = True

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    wb.save(out_path)
    return {"out": out_path, "sheets": len(wb.worksheets), "simulated": sorted(sim)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成出口报价工作簿（含自动重算公式）")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", default="出口报价工作簿.xlsx")
    ap.add_argument("--simulated", default="")
    a = ap.parse_args(argv)
    sim = [s.strip() for s in a.simulated.split(",") if s.strip()]
    info = build(a.input, a.out, sim)
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
