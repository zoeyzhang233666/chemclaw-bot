#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_xlsx.py — 生成「客户市场价核验」Excel 工作簿（含可复用公式）。

设计原则：
  * 客户报价、口径选择、已知费用放在「01_客户报价输入」，其余表用**公式引用**它。
  * 所有偏离计算都是 Excel 公式（不是算好的常数），销售改客户价后自动重算。
  * 市场报价、历史序列、来源都是数据行，可替换为同品种/同地区的其它数据。
  * 无法折算的地方用 IFERROR/IF 显示「无法直接折算」，不做推测。

用法：
  python scripts/build_xlsx.py build/data.json --out out/xxx.xlsx
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

# ---------------------------------------------------------------- 样式
NAVY = "1F4E79"
NAVY2 = "2F6FA8"
LT = "EAF1F8"
GREY = "F5F7FA"
HI = "FDF0EE"
LO = "EAF6F0"
MID = "FDF6E7"
BORDER = Border(*[Side(style="thin", color="D3D9E3")] * 4)

F_TITLE = Font(name="微软雅黑", size=15, bold=True, color=NAVY)
F_H2 = Font(name="微软雅黑", size=11.5, bold=True, color=NAVY)
F_TH = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
F_TD = Font(name="微软雅黑", size=10, color="17202E")
F_TD_B = Font(name="微软雅黑", size=10, bold=True, color="17202E")
F_SM = Font(name="微软雅黑", size=9, color="6B7684")
F_RED = Font(name="微软雅黑", size=10, bold=True, color="C0392B")
F_GREEN = Font(name="微软雅黑", size=10, bold=True, color="1E7A56")

FILL_TH = PatternFill("solid", fgColor=NAVY)
FILL_LT = PatternFill("solid", fgColor=LT)
FILL_GREY = PatternFill("solid", fgColor=GREY)
FILL_HI = PatternFill("solid", fgColor=HI)
FILL_LO = PatternFill("solid", fgColor=LO)
FILL_MID = PatternFill("solid", fgColor=MID)
FILL_INPUT = PatternFill("solid", fgColor="FFF9E6")

WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")

NUM = '#,##0'
NUM2 = '#,##0.00'
PCT = '+0.0%;-0.0%;0.0%'
PCT_A = '0.0%'


def hdr(ws, row, cols, widths=None):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = F_TH
        cell.fill = FILL_TH
        cell.alignment = CENTER
        cell.border = BORDER
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def title(ws, text, sub=None, span=8):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    c = ws.cell(row=1, column=1, value=text)
    c.font = F_TITLE
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = F_SM
        c2.alignment = WRAP
        ws.row_dimensions[2].height = 30


def put(ws, r, c, v, font=F_TD, fill=None, fmt=None, align=WRAP, border=True):
    cell = ws.cell(row=r, column=c, value=v)
    cell.font = font
    if fill:
        cell.fill = fill
    if fmt:
        cell.number_format = fmt
    cell.alignment = align
    if border:
        cell.border = BORDER
    return cell


def section(ws, r, text, span=8):
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=span)
    c = ws.cell(row=r, column=1, value=text)
    c.font = F_H2
    c.fill = FILL_LT
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[r].height = 22


# ---------------------------------------------------------------- 主构建
def build(data, out_path):
    meta = data["meta"]
    cust = data["customer"]
    mkt = data["market"]
    cmpres = data["comparison"]
    band = data.get("band_3m") or {}
    verdict = data["verdict"]
    history = data.get("history", [])
    spots = data.get("spot_all", [])
    regs = data.get("region_compare", [])
    reg_primary = data.get("region_primary", meta.get("region"))
    calibers = data.get("calibers", [])
    factors = data.get("factors", [])
    questions = data.get("questions", [])
    facts = data.get("facts", [])
    gaps = data.get("gaps", [])
    windows = data.get("windows", {})
    steps = data.get("steps", [])
    futs = data.get("futures") or {}

    wb = Workbook()

    # ============================================================ 00 封面与结论
    ws = wb.active
    ws.title = "00_封面与结论"
    title(ws, f"{meta.get('product','')} · {meta.get('region','')} 客户市场价核验",
          f"规格：{meta.get('spec','')}　|　地区口径：{meta.get('region_scope','')}　|　"
          f"基准日：{meta.get('base_date','')}　|　案例：{meta.get('case_id','')}", span=4)
    for i, w in enumerate([26, 46, 26, 46], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    r = 4
    if cust.get("is_simulated"):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        c = ws.cell(row=r, column=1, value="⚠ " + cust.get("simulation_disclaimer", ""))
        c.font = Font(name="微软雅黑", size=10, bold=True, color="7A5C14")
        c.fill = FILL_MID
        c.alignment = WRAP
        ws.row_dimensions[r].height = 34

    r = 6
    section(ws, r, "一、客户所述价格（原文与已识别信息）")
    r += 1
    rows = [
        ("客户原话", cust.get("raw_text", ""), "识别渠道", cust.get("channel", "—")),
        ("客户所述价格", (cust.get("stated_price"), NUM), "税费口径", C.norm_tax(cust.get("stated_tax"))),
        ("客户所述规格", cust.get("stated_spec", ""), "交付口径", C.norm_delivery(cust.get("stated_delivery"))),
        ("客户所述地区", cust.get("stated_region", ""), "付款方式", C.norm_payment(cust.get("stated_payment"))),
        ("采购数量", cust.get("stated_quantity", "未说明"), "价格取得日期", cust.get("stated_date", "未说明")),
    ]
    for a1, b1, c1, d1 in rows:
        put(ws, r, 1, a1, F_TD_B, FILL_GREY)
        if isinstance(b1, tuple):
            put(ws, r, 2, b1[0], F_TD, FILL_INPUT, b1[1])
        else:
            put(ws, r, 2, b1, F_TD)
        put(ws, r, 3, c1, F_TD_B, FILL_GREY)
        put(ws, r, 4, d1, F_TD)
        r += 1

    r += 1
    section(ws, r, "二、市场参考价格（同规格·同地区·同税费·同交付）")
    r += 1
    put(ws, r, 1, "市场参考区间", F_TD_B, FILL_LT)
    put(ws, r, 2, f"=IFERROR(IF('04_偏离计算'!C12=\"\",\"—\",'04_偏离计算'!C12),\"—\")", F_TD_B, FILL_LT)
    put(ws, r, 3, "报价日期", F_TD_B, FILL_LT)
    put(ws, r, 4, mkt.get("date") or "—", F_TD_B, FILL_LT)
    r += 1
    put(ws, r, 1, "数据来源", F_TD_B, FILL_GREY)
    put(ws, r, 2, mkt.get("source") or "—", F_TD)
    put(ws, r, 3, "口径", F_TD_B, FILL_GREY)
    put(ws, r, 4, f"{mkt.get('tax_label') or mkt.get('tax') or ''} · {mkt.get('delivery') or ''}")
    r += 1
    put(ws, r, 1, "原始链接", F_TD_B, FILL_GREY)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c = ws.cell(row=r, column=2, value=mkt.get("url") or "")
    c.hyperlink = mkt.get("url") or None
    c.font = Font(name="微软雅黑", size=9, color="1155CC", underline="single")
    c.alignment = WRAP
    r += 1
    put(ws, r, 1, "市场报价类型", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"{mkt.get('quote_type') or '—'}（置信度 {mkt.get('conf') or '—'}）")
    put(ws, r, 3, "近3月价格带", F_TD_B, FILL_GREY)
    put(ws, r, 4, f"{C.fmt_num(band.get('min'))} – {C.fmt_num(band.get('max'))} 元/吨（n={band.get('n','—')}）" if band else "样本不足")

    r += 2
    section(ws, r, "三、核验结论")
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    c = ws.cell(row=r, column=1, value=f"=IFERROR('04_偏离计算'!C34,\"—\")")
    c.font = Font(name="微软雅黑", size=13, bold=True, color="C0392B")
    c.fill = FILL_HI if verdict["code"] in ("high", "above_slight") else FILL_LO
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[r].height = 26
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    c = ws.cell(row=r, column=1, value="；".join(verdict.get("reasons", [])) + (
        "（口径提示：" + "；".join(verdict.get("caliber_missing", [])) + "，需客户确认后复核）"
        if verdict.get("caliber_missing") else ""))
    c.font = F_TD
    c.alignment = WRAP
    ws.row_dimensions[r].height = 52

    r += 2
    section(ws, r, "四、使用说明")
    r += 1
    tips = [
        "1. 先在「01_客户报价输入」里填客户价格、税费/交付口径、我方报价（与报价文件一致）；其它表会自动重算。",
        "2. 「03_市场报价与历史」是可替换的数据区：换品种/换地区时，按表头六项口径逐行替换即可，不要改「04_偏离计算」里的公式。",
        "3. 「04_偏离计算」所有偏离金额与比例都是公式，可鼠标点到单元格查看引用关系。",
        "4. 「08_数据缺口」列出拿不到的数据；在补上之前，不要给出比表内区间更细的结论。",
        "5. 本簿不提供报价建议、不提供让价幅度；沟通话术在「10_沟通事实要点」中仅是客观事实，需人工审核后使用。",
    ]
    for t in tips:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        c = ws.cell(row=r, column=1, value=t)
        c.font = F_TD
        c.alignment = WRAP
        r += 1
    ws.freeze_panes = "A4"

    # ============================================================ 01 客户报价输入
    ws = wb.create_sheet("01_客户报价输入")
    title(ws, "客户报价输入（黄色单元格为可修改项）",
          "口径不一致或缺失时，请在「推断口径」一栏说明来源；不要凭猜填写。", span=4)
    for i, w in enumerate([30, 45, 26, 52], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    hdr(ws, 4, ["字段", "值", "备注 / 口径", "说明"])
    r = 5
    fields = [
        ("客户所述价格", "PRICE", NUM, "必填。客户口头或微信里给出的数字，不要自行折算。"),
        ("单位", "元/吨", None, "若不是元/吨，请在上方注明换算关系，不要直接相乘。"),
        ("价差基准价（市场参考）", None, NUM, "默认取「市场参考口径」当日区间中值；也可手填。"),
        ("客户所述税费口径", C.norm_tax(cust.get("stated_tax")), None, "含税 / 不含税 / 未注明。必须与市场口径一致才能直接比。"),
        ("客户所述交付口径", C.norm_delivery(cust.get("stated_delivery")), None, "出厂 / 送到 / 库提。送到与出厂差运费。"),
        ("客户所述付款方式", C.norm_payment(cust.get("stated_payment")), None, "现金 / 承兑。承兑需贴现，不可默认等同现金。"),
        ("客户所述采购数量", cust.get("stated_quantity", "未说明"), None, "吨/月或单笔吨位，影响成交区间位置。"),
        ("客户所述取得日期", cust.get("stated_date", "未说明"), None, "客户说『现在才…』时，请他给出具体日期与来源。"),
        ("我方历史报价", cust.get("our_quote") or None, NUM, "选填。用于算『我方报价 vs 客户价』，不是建议价。"),
        ("我方报价税费口径", C.norm_tax(cust.get("our_quote_basis") or "未注明"), None, "选填。"),
        ("已知运费（元/吨）", None, NUM, "仅在客户为出厂、市场为送到时使用；没有就留空 → 显示无法直接折算。"),
        ("已知税率（增值税）", 0.13, PCT_A, "纯碱适用 13%；其它品种请按实际税率填写。换算系数自动算出。"),
        ("税费换算系数", "=1+B16", '0.0000', "含税 = 不含税 × (1+税率)；由公式得出，不要手改。"),
    ]
    for lab, val, fmt, note in fields:
        put(ws, r, 1, lab, F_TD_B, FILL_GREY)
        if lab == "客户所述价格":
            put(ws, r, 2, cust.get("stated_price"), F_TD_B, FILL_INPUT, NUM)  # B5
        elif lab == "单位":
            put(ws, r, 2, val, F_TD, FILL_INPUT)
        else:
            put(ws, r, 2, val, F_TD, FILL_INPUT, fmt)
        put(ws, r, 3, note if lab not in ("价差基准价（市场参考）",) else "公式引用 B25（市场区间中值）", F_SM)
        put(ws, r, 4, "", F_SM)
        r += 1
    # 修正：价差基准价引用 D12
    ws["B7"] = "=B25"
    ws["C7"] = "公式引用 B25（市场区间中值）"
    # 数据验证
    dv_tax = DataValidation(type="list", formula1='"含税,不含税,未注明"', allow_blank=True)
    dv_del = DataValidation(type="list", formula1='"出厂,送到,库提,未注明"', allow_blank=True)
    dv_pay = DataValidation(type="list", formula1='"现金,承兑,未注明"', allow_blank=True)
    for d, cell in ((dv_tax, "B8"), (dv_del, "B9"), (dv_pay, "B10")):
        ws.add_data_validation(d)
        d.add(ws[cell])

    r = 19
    section(ws, r, "市场参考口径（来自 03 表，或手工指定）", span=4)
    r += 1
    hdr(ws, r, ["项目", "值", "口径", "说明"])
    r += 1
    put(ws, r, 1, "市场税费口径", F_TD_B, FILL_GREY); put(ws, r, 2, C.norm_tax(mkt.get("tax")) or "含税", F_TD, FILL_INPUT)
    put(ws, r, 3, "参照行", F_SM); put(ws, r, 4, "必须与客户口径可比；不可比时在 04 表会显示口径提示", F_SM); r += 1
    put(ws, r, 1, "市场交付口径", F_TD_B, FILL_GREY); put(ws, r, 2, C.norm_delivery(mkt.get("delivery")) or "送到", F_TD, FILL_INPUT)
    put(ws, r, 3, "参照行", F_SM); put(ws, r, 4, "送到价含运费；出厂价不含运费", F_SM); r += 1
    put(ws, r, 1, "市场区间下沿", F_TD_B, FILL_GREY); put(ws, r, 2, mkt.get("low"), F_TD, FILL_INPUT, NUM)
    put(ws, r, 3, "元/吨", F_SM); put(ws, r, 4, "来自「03_市场报价与历史」所选行", F_SM); r += 1
    put(ws, r, 1, "市场区间上沿", F_TD_B, FILL_GREY); put(ws, r, 2, mkt.get("high"), F_TD, FILL_INPUT, NUM)
    put(ws, r, 3, "元/吨", F_SM); put(ws, r, 4, "", F_SM); r += 1
    put(ws, r, 1, "市场区间中值（公式）", F_TD_B, FILL_LT); put(ws, r, 2, "=AVERAGE(B23:B24)", F_TD_B, FILL_LT, NUM)
    put(ws, r, 3, "元/吨", F_SM); put(ws, r, 4, "=(下沿+上沿)/2，仅取同一来源的区间", F_SM); r += 1
    put(ws, r, 1, "报价日期", F_TD_B, FILL_GREY); put(ws, r, 2, mkt.get("date"), F_TD)
    put(ws, r, 3, "日期", F_SM); put(ws, r, 4, "客户价比对必须看日期", F_SM)

    # 01 表关键单元格位置：
    # B5 客户价  B8 客户税  B9 客户交付 B10 客户付款 B15 运费 B16 税率 B17 系数
    # B22 市场下沿 B23 市场上沿 B24 中值  B25 日期 B21 市场交付 B20 市场税
    ws.freeze_panes = "A5"

    # ============================================================ 02 口径对照
    ws = wb.create_sheet("02_口径对照")
    title(ws, "规格与交易口径对照（同口径优先）",
          "每一维度都问一句：客户说的和市场上报的，是不是同一个东西。", span=6)
    for i, w in enumerate([12, 30, 30, 12, 42, 30], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    hdr(ws, 4, ["维度", "客户所述", "市场口径", "是否一致", "对价格的影响", "需确认 / 动作"])
    r = 5
    for c in calibers:
        flag = c.get("diff_flag", "")
        fill = FILL_LO if flag == "一致" else (FILL_MID if flag == "信息缺失" else FILL_HI)
        put(ws, r, 1, c.get("dim"), F_TD_B, FILL_GREY)
        put(ws, r, 2, c.get("customer"), F_TD)
        put(ws, r, 3, c.get("market"), F_TD)
        put(ws, r, 4, flag, F_TD_B, fill, align=CENTER)
        put(ws, r, 5, c.get("impact"), F_TD)
        put(ws, r, 6, c.get("action"), F_TD)
        ws.row_dimensions[r].height = 34
        r += 1
    r += 1
    section(ws, r, "可能导致价格差异的因素（客观解释，不是话术）", span=6)
    r += 1
    hdr(ws, r, ["因素", "说明", "", "对价格的影响", "", ""])
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    r += 1
    for f in factors:
        put(ws, r, 1, f.get("k"), F_TD_B, FILL_GREY)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        put(ws, r, 2, f.get("v"), F_TD)
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        put(ws, r, 4, f.get("affects"), F_TD)
        ws.row_dimensions[r].height = 40
        r += 1
    ws.freeze_panes = "A5"

    # ============================================================ 03 市场报价与历史
    ws = wb.create_sheet("03_市场报价与历史")
    title(ws, "市场报价与历史序列（可替换的数据区）",
          "每条报价必须六项齐全：数值·规格·地区·税费·交付·日期·来源。缺一项只能放「08_数据缺口」。", span=12)
    widths = [13, 12, 12, 14, 14, 14, 8, 12, 13, 10, 26, 40]
    hdr(ws, 4, ["日期", "规格", "地区", "税费", "交付", "付款", "下沿", "上沿", "中值/主流价",
                "单位", "来源 / 类型", "原始链接（可点）"], widths)
    r = 5
    # 现货（含被排除的）
    for s in sorted(spots, key=lambda x: (x.get("date") or ""), reverse=True):
        lo, hi = s.get("low"), s.get("high")
        pt = s.get("point") if s.get("point") is not None else ((lo + hi) / 2 if lo and hi else lo)
        put(ws, r, 1, s.get("date"), align=CENTER)
        put(ws, r, 2, s.get("spec"))
        put(ws, r, 3, s.get("region"))
        put(ws, r, 4, s.get("tax_label") or s.get("tax"))
        put(ws, r, 5, s.get("delivery"))
        put(ws, r, 6, s.get("payment"))
        put(ws, r, 7, lo, fmt=NUM, align=RIGHT)
        put(ws, r, 8, hi, fmt=NUM, align=RIGHT)
        put(ws, r, 9, pt, fmt=NUM, align=RIGHT, font=F_TD_B)
        put(ws, r, 10, "元/吨", align=CENTER)
        src = f"{s.get('source')}（{s.get('quote_type')}，置信{s.get('conf')}）"
        if s.get("exclude_reason"):
            src += " ｜不可直接比较：" + s["exclude_reason"]
            for cc in range(1, 13):
                ws.cell(row=r, column=cc).fill = FILL_MID
        put(ws, r, 11, src)
        c = put(ws, r, 12, s.get("url"))
        c.hyperlink = s.get("url")
        c.font = Font(name="微软雅黑", size=9, color="1155CC", underline="single")
        ws.row_dimensions[r].height = 30
        r += 1
    spot_end = r - 1

    r += 1
    section(ws, r, "历史序列（同规格·同地区·同口径，按日期排序；走势与价格带以此为底）", span=12)
    r += 1
    hdr(ws, r, ["日期", "规格", "地区", "税费", "交付", "类型", "下沿", "上沿", "中值", "单位", "来源", "原始链接（可点）"], widths)
    hist_start = r + 1
    r += 1
    for h in history:
        put(ws, r, 1, h.get("date"), align=CENTER)
        put(ws, r, 2, h.get("spec"))
        put(ws, r, 3, h.get("region"))
        put(ws, r, 4, h.get("tax"))
        put(ws, r, 5, h.get("delivery"))
        put(ws, r, 6, h.get("kind"), align=CENTER)
        put(ws, r, 7, h.get("low"), fmt=NUM, align=RIGHT)
        put(ws, r, 8, h.get("high"), fmt=NUM, align=RIGHT)
        put(ws, r, 9, h.get("point"), fmt=NUM, align=RIGHT, font=F_TD_B)
        put(ws, r, 10, h.get("unit", "元/吨"), align=CENTER)
        put(ws, r, 11, h.get("source"))
        c = put(ws, r, 12, h.get("url"))
        c.hyperlink = h.get("url")
        c.font = Font(name="微软雅黑", size=9, color="1155CC", underline="single")
        r += 1
    hist_end = r - 1

    # 统计区（公式）
    r += 1
    section(ws, r, "序列统计（全部为公式，替换数据后自动更新）", span=12)
    r += 1
    stats = [
        ("样本数", f"=COUNT(I{hist_start}:I{hist_end})", NUM),
        ("近3月最高", f"=MAX(I{hist_start}:I{hist_end})", NUM),
        ("近3月最低", f"=MIN(I{hist_start}:I{hist_end})", NUM),
        ("近3月中值", f"=MEDIAN(I{hist_start}:I{hist_end})", NUM),
        ("近3月均值", f"=AVERAGE(I{hist_start}:I{hist_end})", NUM),
        ("最大波动幅度", f"=MAX(I{hist_start}:I{hist_end})-MIN(I{hist_start}:I{hist_end})", NUM),
    ]
    stat_pos = {}
    for lab, f_, fmt in stats:
        put(ws, r, 1, lab, F_TD_B, FILL_GREY)
        put(ws, r, 2, f_, F_TD_B, FILL_LT, fmt, RIGHT)
        stat_pos[lab] = f"B{r}"
        r += 1
    ws.freeze_panes = "A5"

    # ============================================================ 04 偏离计算（核心）
    ws = wb.create_sheet("04_偏离计算")
    title(ws, "价格偏离计算（全部为公式；改 01 表客户价即自动重算）",
          "公式口径：偏离金额 = 客户价 − 市场参考值；偏离比例 = 偏离金额 ÷ 市场参考值。", span=6)
    for i, w in enumerate([30, 20, 20, 16, 16, 52], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    IN = "'01_客户报价输入'"
    r = 4
    section(ws, r, "一、输入（引用 01 表）", span=6)
    r += 1
    hdr(ws, r, ["项目", "数值", "单位", "", "", "公式 / 说明"])
    r += 1
    base = r
    items = [
        ("客户所述价格", f"={IN}!B5", "元/吨", NUM, "直接引用 01!B5"),
        ("客户税费口径", f"={IN}!B8", "", None, "含税/不含税/未注明"),
        ("客户交付口径", f"={IN}!B9", "", None, "出厂/送到/库提"),
        ("市场税费口径", f"={IN}!B21", "", None, "参照 03 表"),
        ("市场交付口径", f"={IN}!B22", "", None, "参照 03 表"),
        ("市场区间下沿", f"={IN}!B23", "元/吨", NUM, "同日同口径"),
        ("市场区间上沿", f"={IN}!B24", "元/吨", NUM, "同日同口径"),
        ("市场参考值（中值）", f"={IN}!B25", "元/吨", NUM, "=(下沿+上沿)/2"),
        ("税率", f"={IN}!B16", "", PCT_A, "增值税"),
        ("已知运费", f"={IN}!B15", "元/吨", NUM, "出厂→送到时使用；空则无法折算"),
    ]
    cellmap = {}
    for lab, f_, unit, fmt, note in items:
        put(ws, r, 1, lab, F_TD_B, FILL_GREY)
        put(ws, r, 2, f_, F_TD_B, FILL_LT, fmt, RIGHT)
        put(ws, r, 3, unit, F_SM, align=CENTER)
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
        put(ws, r, 6, note, F_SM)
        cellmap[lab] = f"B{r}"
        r += 1
    P = cellmap["客户所述价格"]; CT = cellmap["客户税费口径"]; CD = cellmap["客户交付口径"]
    MT = cellmap["市场税费口径"]; MD = cellmap["市场交付口径"]
    LOW = cellmap["市场区间下沿"]; HIGH = cellmap["市场区间上沿"]; DOT = cellmap["市场参考值（中值）"]
    RATE = cellmap["税率"]; FR = cellmap["已知运费"]

    r += 1
    section(ws, r, "二、口径标准化（确定性换算，非推测）", span=6)
    r += 1
    hdr(ws, r, ["步骤", "数值", "说明", "", "", "公式"])
    r += 1
    # 税费换算：只有「客户明确不含税、市场含税」或「客户含税、市场不含税」才换算；
    # 「未注明」一律按市场税基直接比较，并在口径提示里标注风险（不擅自加税）。
    put(ws, r, 1, "客户价（换算到市场税基）", F_TD_B, FILL_GREY)
    put(ws, r, 2, (f'=IF(AND({CT}="不含税",{MT}="含税"),{P}*(1+{RATE}),'
                   f'IF(AND({CT}="含税",{MT}="不含税"),{P}/(1+{RATE}),{P}))'),
        F_TD_B, FILL_LT, NUM, RIGHT)
    put(ws, r, 3, "仅当两侧税基明确且不同才换算", F_SM)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
    put(ws, r, 6, "客户「未注明」时不加税、不减税，直接按市场税基比较，并在结论里标注口径风险", F_SM)
    ADJ = f"B{r}"
    r += 1
    put(ws, r, 1, "客户价（换算到市场交付口径）", F_TD_B, FILL_GREY)
    put(ws, r, 2, (f'=IF(AND({MD}="送到",{CD}="出厂"),IFERROR({ADJ}+{FR},{ADJ}),'
                   f'IF(AND({MD}="出厂",{CD}="送到"),IFERROR({ADJ}-{FR},{ADJ}),{ADJ}))'),
        F_TD_B, FILL_LT, NUM, RIGHT)
    put(ws, r, 3, "出厂+运费→送到；送到−运费→出厂；无运费则保持原值并提示", F_SM)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
    put(ws, r, 6, "运费为空时不做任何假设，04 结论区会显示「无法直接折算」", F_SM)
    FINAL = f"B{r}"
    r += 1
    # 是否可比较
    put(ws, r, 1, "口径是否可直接比较", F_TD_B, FILL_GREY)
    put(ws, r, 2, f'=IF(AND({MD}="送到",{CD}="出厂",{FR}=""),"无法直接折算（缺运费）","可比较（已按口径换算）")',
        F_TD_B, FILL_LT, None, CENTER)
    put(ws, r, 3, "条件", F_SM)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
    put(ws, r, 6, "只比较同税基、同交付口径的价格", F_SM)
    OK = f"B{r}"
    r += 2

    section(ws, r, "三、偏离金额与比例", span=6)
    r += 1
    hdr(ws, r, ["指标", "数值（元/吨 或 %）", "计算方法", "", "", "Excel 公式"])
    r += 1
    put(ws, r, 1, "① 偏离金额（相对中值）", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"={FINAL}-{DOT}", F_RED, FILL_HI, NUM, RIGHT)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    put(ws, r, 3, "客户价 − 市场参考值（正=客户更高）", F_TD)
    put(ws, r, 6, f"={FINAL}-{DOT}", F_SM)
    D1 = f"B{r}"; r += 1
    put(ws, r, 1, "② 偏离比例（相对中值）", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"=IFERROR({D1}/{DOT},\"\")", F_RED, FILL_HI, PCT, RIGHT)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    put(ws, r, 3, "偏离金额 ÷ 市场参考值", F_TD)
    put(ws, r, 6, f"=IFERROR({D1}/{DOT},\"\")", F_SM)
    P1 = f"B{r}"; r += 1
    put(ws, r, 1, "③ 相对区间上沿的金额", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"={FINAL}-{HIGH}", F_TD_B, FILL_LT, NUM, RIGHT)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    put(ws, r, 3, "客户价 − 上沿（>0 表示高于市场最高报价）", F_TD)
    put(ws, r, 6, f"={FINAL}-{HIGH}", F_SM)
    D2 = f"B{r}"; r += 1
    put(ws, r, 1, "④ 相对上沿的比例", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"=IFERROR({D2}/{HIGH},\"\")", F_TD_B, FILL_LT, PCT, RIGHT)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    put(ws, r, 3, "相对上沿金额 ÷ 上沿", F_TD)
    put(ws, r, 6, f"=IFERROR({D2}/{HIGH},\"\")", F_SM)
    P2 = f"B{r}"; r += 1
    put(ws, r, 1, "⑤ 相对区间下沿的金额", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"={FINAL}-{LOW}", F_TD_B, FILL_LT, NUM, RIGHT)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    put(ws, r, 3, "客户价 − 下沿（<0 表示低于市场最低报价）", F_TD)
    put(ws, r, 6, f"={FINAL}-{LOW}", F_SM)
    D3 = f"B{r}"; r += 1
    put(ws, r, 1, "⑥ 相对下沿的比例", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"=IFERROR({D3}/{LOW},\"\")", F_TD_B, FILL_LT, PCT, RIGHT)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    put(ws, r, 3, "相对下沿金额 ÷ 下沿", F_TD)
    put(ws, r, 6, f"=IFERROR({D3}/{LOW},\"\")", F_SM)
    r += 1
    put(ws, r, 1, "⑦ 是否落在市场区间内", F_TD_B, FILL_GREY)
    put(ws, r, 2, f'=IF({FINAL}={DOT},"待输入客户价",IF(AND({FINAL}>={LOW},{FINAL}<={HIGH}),"是","否"))',
        F_TD_B, FILL_LT, None, CENTER)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    put(ws, r, 3, "下沿 ≤ 客户价 ≤ 上沿 → 是", F_TD)
    INSIDE = f"B{r}"; r += 1
    put(ws, r, 1, "⑧ 区间半宽（判定尺度）", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"=({HIGH}-{LOW})/2", F_TD_B, FILL_LT, NUM, RIGHT)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    put(ws, r, 3, "半宽 = (上沿−下沿)/2，用作『明显』判定的自然尺度", F_TD)
    put(ws, r, 6, f"=({HIGH}-{LOW})/2", F_SM)
    HALF = f"B{r}"; r += 2

    section(ws, r, "四、判定（依据区间位置 + 近3月价格带，不用固定百分比阈值）", span=6)
    r += 1
    # 判定公式（与 scripts/assemble.py 的 classify() 同一规则）：
    #   ① 在 [下沿,上沿] 内 → 接近市场参考区间
    #   ② 区间外、距最近端点 ≤ 半宽 → 略高/略低
    #   ③ 区间外、距最近端点 >  半宽 → 明显偏高/明显偏低
    # 「明显」的尺子取自该报价自身的带宽，而不是固定的百分比。
    # 容差 0.01 元只用于抵消浮点误差（如区间中值 1125 恰好压线）。
    TOL = 0.01
    # 没有市场区间时（降级案例），必须先判「无法验证」，否则空单元格会被当成 0 而误判成偏低/偏高
    cond = (
        f'=IF(OR({LOW}="",{HIGH}="",NOT(ISNUMBER({LOW})),NOT(ISNUMBER({HIGH}))),'
        f'"无可靠市场数据，无法验证",'
        f'IF({OK}<>"可比较（已按口径换算）","口径不一致，暂时无法直接比较",'
        f'IF(AND({FINAL}>={LOW}-{TOL},{FINAL}<={HIGH}+{TOL}),"接近市场参考区间",'
        f'IF(ABS({FINAL}-IF({FINAL}>{HIGH},{HIGH},{LOW}))<={HALF}+{TOL},'
        f'IF({FINAL}>{HIGH},"略高于市场参考区间","略低于市场参考区间"),'
        f'IF({FINAL}>{HIGH},"明显偏高","明显偏低")))))'
    )
    put(ws, r, 1, "核验结论", F_TD_B, FILL_HI)
    put(ws, r, 2, cond, Font(name="微软雅黑", size=12, bold=True, color="C0392B"), FILL_HI, None, CENTER)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    ws.row_dimensions[r].height = 28
    VERD = f"B{r}"
    r += 1
    put(ws, r, 1, "判定规则", F_TD_B, FILL_GREY)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    put(ws, r, 2, "①客户价在[下沿,上沿]内→接近市场；②区间外但距最近端点 ≤ 半宽 → 略高/略低；"
                  "③距最近端点 > 半宽 → 明显偏高/明显偏低；④口径不可比 → 无法直接比较。"
                  "「明显」的尺度取自该市场报价自身的宽度，而不是人为设定的百分比。", F_SM)
    ws.row_dimensions[r].height = 42
    r += 1
    put(ws, r, 1, "口径提示", F_TD_B, FILL_GREY)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    put(ws, r, 2, "；".join(verdict.get("caliber_missing", [])) or "客户口径已明确", F_SM)
    r += 1
    put(ws, r, 1, "我方报价 vs 客户价", F_TD_B, FILL_GREY)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    put(ws, r, 2, f'=IF({IN}!B13="","未填写我方报价","我方报价 "&TEXT({IN}!B13,"#,##0")&" 元/吨，较客户价 "'
                  f'&TEXT({IN}!B13-{P},"+#,##0;-#,##0;0")&" 元/吨（"&TEXT(IFERROR(({IN}!B13-{P})/{P},0),"+0.0%;-0.0%")&"）")', F_SM)
    r += 2

    section(ws, r, "五、历史窗口对比（7天 / 30天 / 3个月）", span=6)
    r += 1
    hdr(ws, r, ["窗口", "起点日期", "起点价格", "最新价格", "变化", "变化比例"])
    r += 1
    for k, nm in (("7d", "近7天"), ("30d", "近30天"), ("90d", "近3个月")):
        w = windows.get(k)
        put(ws, r, 1, nm, F_TD_B, FILL_GREY)
        put(ws, r, 2, w["from_date"] if w else "—", align=CENTER)
        put(ws, r, 3, w["from_value"] if w else None, fmt=NUM, align=RIGHT)
        put(ws, r, 4, w["to_value"] if w else None, fmt=NUM, align=RIGHT)
        put(ws, r, 5, f"=D{r}-C{r}" if w else "—", F_TD_B, fmt=NUM, align=RIGHT)
        put(ws, r, 6, f"=IFERROR(E{r}/C{r},\"\")" if w else "—", F_TD_B, fmt=PCT, align=RIGHT)
        r += 1
    r += 1
    put(ws, r, 1, "客户价在历史中的位置", F_TD_B, FILL_GREY)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    hp = data.get("history_position")
    put(ws, r, 2, (f"历史序列区间 {C.fmt_num(hp['min'])}–{C.fmt_num(hp['max'])} 元/吨；客户价"
                   f"{'落在序列内' if hp['inside_history'] else '高于序列最高点 '+C.fmt_money(hp['above_max_by'])+' 元/吨'}"
                   f"（{C.fmt_pct_abs(hp['pct_above_max']) if not hp['inside_history'] else ''}）") if hp else "无历史数据", F_SM)
    ws.freeze_panes = "A5"

    # 记录给封面引用的行列
    # 封面 B 列引用：04!C12 并不存在，改为直接引用
    ws0 = wb["00_封面与结论"]
    # 重写封面市场区间单元格为直接引用
    for row in ws0.iter_rows(min_row=1, max_row=40, min_col=1, max_col=1):
        for c in row:
            if c.value == "市场参考区间":
                ws0.cell(row=c.row, column=2,
                         value=f'=TEXT(\'01_客户报价输入\'!B22,"#,##0")&" – "&TEXT(\'01_客户报价输入\'!B23,"#,##0")&" 元/吨"')
    for row in ws0.iter_rows(min_row=1, max_row=40, min_col=1, max_col=1):
        for c in row:
            if c.value == "市场参考区间":
                pass
    # 结论单元格指向 04 的结论
    for row in ws0.iter_rows(min_row=1, max_row=40, min_col=1, max_col=4):
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("=IFERROR('04_偏离计算'!C34"):
                ws0.cell(row=c.row, column=1, value=f"='04_偏离计算'!{VERD}")
                ws0.cell(row=c.row, column=1).font = Font(name="微软雅黑", size=13, bold=True, color="C0392B")
                ws0.cell(row=c.row, column=1).fill = FILL_HI
                ws0.cell(row=c.row, column=1).alignment = Alignment(vertical="center")

    # ============================================================ 05 历史走势数据
    ws = wb.create_sheet("05_历史走势数据")
    title(ws, "历史价格序列（供 Excel 折线图 / 复核任意一天）",
          "同一来源、同一口径的连续点；不同来源标注了口径差异，不做平均合并。", span=8)
    hdr(ws, 4, ["日期", "规格", "地区", "口径", "区间下沿", "区间上沿", "中值/主流价", "来源"],
        [13, 14, 12, 16, 12, 12, 14, 34])
    r = 5
    for h in history:
        put(ws, r, 1, h.get("date"), align=CENTER)
        put(ws, r, 2, h.get("spec"))
        put(ws, r, 3, h.get("region"))
        put(ws, r, 4, f"{h.get('tax')}·{h.get('delivery')}", align=CENTER)
        put(ws, r, 5, h.get("low"), fmt=NUM, align=RIGHT)
        put(ws, r, 6, h.get("high"), fmt=NUM, align=RIGHT)
        put(ws, r, 7, h.get("point"), fmt=NUM, align=RIGHT, font=F_TD_B)
        put(ws, r, 8, h.get("source"))
        r += 1
    last = r - 1
    r += 1
    section(ws, r, "辅助列：客户价在历史的什么位置", span=8)
    r += 1
    put(ws, r, 1, "客户价（引用01）", F_TD_B, FILL_GREY)
    put(ws, r, 2, f"='01_客户报价输入'!B5", F_TD_B, FILL_LT, NUM, RIGHT)
    r += 1
    put(ws, r, 1, "高于序列最高点？", F_TD_B, FILL_GREY)
    put(ws, r, 2, f'=IF(B{r-1}>MAX(G5:G{last}),"高于最高点 "&TEXT(B{r-1}-MAX(G5:G{last}),"#,##0")&" 元/吨","在序列范围内")', F_TD)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    ws.freeze_panes = "A5"

    # ============================================================ 06 区域对比
    ws = wb.create_sheet("06_区域对比")
    title(ws, "相邻地区价格对比（同为含税·送到口径）",
          "区域价差主要来自运距与供需结构；不能据此判断『某地市场更高/更低』。", span=9)
    hdr(ws, 4, ["地区", "下沿", "上沿", "中值", "税费", "交付", "日期", "较基准价差", "较基准比例"],
        [14, 11, 11, 11, 10, 10, 13, 14, 14])
    r = 5
    base_row = r
    put(ws, r, 1, f"{reg_primary}（基准）", F_TD_B, FILL_LT)
    put(ws, r, 2, f"='01_客户报价输入'!B24", F_TD_B, FILL_LT, NUM, RIGHT)
    put(ws, r, 3, f"='01_客户报价输入'!B24", F_TD_B, FILL_LT, NUM, RIGHT)
    put(ws, r, 4, f"=AVERAGE(B{r}:C{r})", F_TD_B, FILL_LT, NUM, RIGHT)
    put(ws, r, 5, f"='01_客户报价输入'!B22", align=CENTER)
    put(ws, r, 6, f"='01_客户报价输入'!B22", align=CENTER)
    put(ws, r, 7, mkt.get("date"), align=CENTER)
    put(ws, r, 8, 0, fmt=NUM, align=RIGHT)
    put(ws, r, 9, 0, fmt=PCT, align=RIGHT)
    r += 1
    for g in regs:
        put(ws, r, 1, g.get("region"), F_TD_B)
        put(ws, r, 2, g.get("low"), fmt=NUM, align=RIGHT)
        put(ws, r, 3, g.get("high"), fmt=NUM, align=RIGHT)
        put(ws, r, 4, f"=AVERAGE(B{r}:C{r})", fmt=NUM, align=RIGHT, font=F_TD_B)
        put(ws, r, 5, g.get("tax"), align=CENTER)
        put(ws, r, 6, g.get("delivery"), align=CENTER)
        put(ws, r, 7, g.get("date"), align=CENTER)
        put(ws, r, 8, f"=D{r}-D${base_row}", fmt=NUM, align=RIGHT)
        put(ws, r, 9, f"=IFERROR(H{r}/D${base_row},\"\")", fmt=PCT, align=RIGHT)
        put(ws, r, 10, g.get("comparability", ""), F_SM)
        r += 1
    ws.column_dimensions["J"].width = 46
    ws.column_dimensions[get_column_letter(10)].width = 46
    r += 1
    put(ws, r, 1, "可比性说明", F_TD_B, FILL_GREY)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=9)
    put(ws, r, 2, "各区域均为同规格、同税基、送到口径；日期相差 1-10 天的已在「日期」列标出。"
                  "跨区比价的前提是『同一客户、同一交付地』；运距不同时，价差不能直接当作报价依据。", F_SM)
    ws.row_dimensions[r].height = 40
    ws.freeze_panes = "A5"

    # ============================================================ 07 待确认问题
    ws = wb.create_sheet("07_待确认问题")
    title(ws, "需要向客户确认的问题清单",
          "按优先级排序；每条对应一个口径缺口。得到答复后回填到「客户答复」，再复核结论。", span=5)
    hdr(ws, 4, ["#", "优先级", "问题", "为什么要问", "客户答复（回填）"],
        [6, 10, 52, 40, 36])
    r = 5
    for i, q in enumerate(questions, 1):
        fill = FILL_HI if q.get("priority") == "高" else (FILL_MID if q.get("priority") == "中" else None)
        put(ws, r, 1, i, align=CENTER)
        put(ws, r, 2, q.get("priority"), F_TD_B, fill, align=CENTER)
        put(ws, r, 3, q.get("q"))
        put(ws, r, 4, q.get("why"), F_SM)
        put(ws, r, 5, "", FILL_INPUT)
        ws.row_dimensions[r].height = 34
        r += 1
    ws.freeze_panes = "A5"

    # ============================================================ 08 数据缺口
    ws = wb.create_sheet("08_数据缺口")
    title(ws, "数据缺口与研究边界",
          "缺口不是缺陷列表，而是『这份报告能走多远』的刻度。补上一条，结论才能细一分。", span=4)
    hdr(ws, 4, ["缺口项", "影响", "补法", "状态"], [40, 46, 46, 12])
    r = 5
    for g in gaps:
        put(ws, r, 1, g.get("item"), F_TD_B)
        put(ws, r, 2, g.get("impact"))
        put(ws, r, 3, g.get("fix"))
        put(ws, r, 4, "待补", F_TD_B, FILL_MID, align=CENTER)
        ws.row_dimensions[r].height = 34
        r += 1
    r += 1
    section(ws, r, "研究方法说明", span=4)
    r += 1
    for n in data.get("method_notes", []):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        put(ws, r, 1, "• " + n, F_TD)
        ws.row_dimensions[r].height = 34
        r += 1
    if futs:
        r += 1
        section(ws, r, "期货参考（仅说明税基差异，不作为现货参考价）", span=4)
        r += 1
        put(ws, r, 1, "说明", F_TD_B, FILL_GREY)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        put(ws, r, 2, futs.get("note", ""), F_SM)
        ws.row_dimensions[r].height = 40
        r += 1
        if futs.get("daily"):
            hdr(ws, r, ["日期", "收盘（元/吨）", "合约", "来源"])
            r += 1
            for d in futs["daily"]:
                put(ws, r, 1, d.get("date"), align=CENTER)
                put(ws, r, 2, d.get("close"), fmt=NUM, align=RIGHT)
                put(ws, r, 3, futs.get("contract"))
                put(ws, r, 4, futs.get("source"), F_SM)
                r += 1
    ws.freeze_panes = "A5"

    # ============================================================ 09 计算过程
    ws = wb.create_sheet("09_计算过程")
    title(ws, "计算过程（可复核）",
          "每个派生数字的公式、输入与结果；任何人可用同一来源复现。", span=5)
    hdr(ws, 4, ["#", "步骤", "公式", "输入", "结果"], [7, 30, 46, 46, 40])
    r = 5
    for s in steps:
        put(ws, r, 1, s.get("id"), align=CENTER)
        put(ws, r, 2, s.get("name"), F_TD_B)
        put(ws, r, 3, s.get("formula"), F_SM)
        inp = "；".join(f"{k}：{v}" for k, v in (s.get("inputs") or {}).items())
        put(ws, r, 4, inp, F_SM)
        res = "；".join(f"{k}：{v}" for k, v in (s.get("result") or {}).items())
        put(ws, r, 5, res, F_SM)
        ws.row_dimensions[r].height = 44
        r += 1
    ws.freeze_panes = "A5"

    # ============================================================ 10 沟通事实要点
    ws = wb.create_sheet("10_沟通事实要点")
    title(ws, "与客户沟通可引用的客观事实",
          "每条都有来源、日期、口径。引用时建议同时说明『这是市场报价区间，实际成交一单一议』。", span=6)
    hdr(ws, 4, ["#", "事实要点", "来源", "日期", "置信度", "备注"], [6, 62, 26, 13, 10, 36])
    r = 5
    for i, f in enumerate(facts, 1):
        put(ws, r, 1, i, align=CENTER)
        put(ws, r, 2, f.get("text"))
        put(ws, r, 3, f.get("src"), F_SM)
        put(ws, r, 4, f.get("date"), align=CENTER)
        put(ws, r, 5, f.get("conf"), F_TD_B, align=CENTER)
        put(ws, r, 6, f.get("note", ""), F_SM)
        ws.row_dimensions[r].height = 40
        r += 1

    r += 2
    section(ws, r, "沟通稿草稿（销售可直接改；内容只含已核实事实，不含价格承诺）", span=6)
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r + 10, end_column=6)
    c = ws.cell(row=r, column=1, value=_draft(data))
    c.font = Font(name="微软雅黑", size=10)
    c.alignment = WRAP
    c.border = BORDER
    ws.freeze_panes = "A5"

    # ============================================================ 11 数据来源清单
    ws = wb.create_sheet("11_数据来源清单")
    title(ws, "数据来源清单（逐条可追溯）",
          "点链接即可复核原始口径；二手引用已标注「未见表」。", span=7)
    hdr(ws, 4, ["#", "来源", "类型", "日期", "取用内容", "置信度", "链接"],
        [6, 30, 18, 13, 48, 10, 54])
    r = 5
    seen = set()
    n = 0
    for s in spots:
        key = (s.get("source"), s.get("date"), s.get("point"))
        if key in seen:
            continue
        seen.add(key); n += 1
        put(ws, r, 1, n, align=CENTER)
        put(ws, r, 2, s.get("source"))
        put(ws, r, 3, s.get("source_type"))
        put(ws, r, 4, s.get("date"), align=CENTER)
        put(ws, r, 5, f"{s.get('region')} {s.get('spec')} {s.get('low')}-{s.get('high')}（{s.get('tax_label') or s.get('tax')}·{s.get('delivery')}）", F_SM)
        put(ws, r, 6, s.get("conf"), align=CENTER)
        c = put(ws, r, 7, s.get("url"))
        c.hyperlink = s.get("url")
        c.font = Font(name="微软雅黑", size=9, color="1155CC", underline="single")
        r += 1
    for h in history:
        key = (h.get("source"), h.get("date"), h.get("point"))
        if key in seen:
            continue
        seen.add(key); n += 1
        put(ws, r, 1, n, align=CENTER)
        put(ws, r, 2, h.get("source"))
        put(ws, r, 3, h.get("kind", "日更区间"))
        put(ws, r, 4, h.get("date"), align=CENTER)
        put(ws, r, 5, f"{h.get('region')} {h.get('spec')} {h.get('low')}-{h.get('high')}（{h.get('tax')}·{h.get('delivery')}）", F_SM)
        put(ws, r, 6, "高", align=CENTER)
        c = put(ws, r, 7, h.get("url"))
        c.hyperlink = h.get("url")
        c.font = Font(name="微软雅黑", size=9, color="1155CC", underline="single")
        r += 1
    ws.freeze_panes = "A5"

    d = os.path.dirname(os.path.abspath(out_path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    wb.save(out_path)
    print(f"[build_xlsx] {out_path}  ({os.path.getsize(out_path)/1024:.0f} KB, {len(wb.sheetnames)} 张表)")
    return out_path


def _draft(data):
    m, c, cust = data["market"], data["comparison"], data["customer"]
    L = []
    L.append(f"您好，关于{data['meta'].get('product','')}的价格，我把公开市场行情同步给您，方便我们对齐口径：")
    L.append("")
    if m.get("low") is not None:
        L.append(f"1）{m.get('date')} {data['meta'].get('region')}市场{data['meta'].get('product')}报价为 "
                 f"{C.fmt_num(m['low'])}–{C.fmt_num(m['high'])} 元/吨（{m.get('tax')}、{m.get('delivery')}），来源：{m.get('source')}。")
    if c.get("pos") != "undecidable":
        L.append(f"2）您提到的价格与这个口径相比，差 {c['delta_to_dot']:+,.0f} 元/吨（约 {abs(c['pct_to_dot'])*100:.1f}%，"
                 f"以区间中值 {C.fmt_num(c['reference'])} 元/吨计）。")
    else:
        L.append("2）您提到的价格暂时无法直接对比，需要先确认税费和出厂/送到口径。")
    for i, f in enumerate(data.get("facts", [])[:3], 3):
        L.append(f"{i}）{f['text']}")
    L.append("")
    L.append("想请您确认：价格含税与否、是出厂还是送到、取得日期与来源、月用量与包装、付款账期。"
             "有了这些我按您的实际口径重新对一遍。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_json")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build(C.load_json(a.data_json), a.out)


if __name__ == "__main__":
    main()
