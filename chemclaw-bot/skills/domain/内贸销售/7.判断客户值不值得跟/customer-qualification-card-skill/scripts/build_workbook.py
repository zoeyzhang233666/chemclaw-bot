# -*- coding: utf-8 -*-
"""
build_workbook.py —— 由 data.json 生成《客户多维判断卡》Excel 工作簿。

用法:
    python build_workbook.py <data.json> <out.xlsx>

依赖: 仅 openpyxl（无需 LibreOffice）。公式写入后会同步写入缓存值，
任何 Excel/WPS 打开即显示排序分；同时设置 fullCalcOnLoad，改动权重会立即重算。
"""
import json
import os
import shutil
import sys
import zipfile
from xml.etree import ElementTree as ET

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = lambda t: "{%s}%s" % (NS_MAIN, t)

FONT = "微软雅黑"
NAVY, ACC = "16325C", "1E56C8"
LIGHT, INPUT = "EAF1FC", "FFF6D6"
LINE = "D8E0EE"
thin = Side(style="thin", color=LINE)
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

DEFAULT_RUBRIC = {
    "match":   "高：窑炉/产线用户且采购公开；中：用途对口但准入门槛不明；低：规格不对口或仅用替代品",
    "demand":  "高：年需求≥20 万吨；中：5–20 万吨；低：<5 万吨",
    "capacity":"高：产线满开且盈利；中：部分冷修/改造降量；低：大面积停产",
    "scale":   "高：龙头、盈利、评级好；中：中型上市但亏损；低：小微/信息不透明",
    "region":  "高：≤600km 且运费<25%货值；中：600–1200km；低：>1200km 或海外",
    "chance":  "高：6 个月内有投产/招标；中：12 个月内有；低：无明确节点",
    "risk":    "高：连亏+长账期；中：信息不透明；低：盈利稳定+付款好（分数越低风险越大）",
}


def F(sz=10.5, b=False, c="22314B", i=False):
    return Font(name=FONT, size=sz, bold=b, color=c, italic=i)


def fill(h):
    return PatternFill("solid", fgColor=h)


def hdr(cell, text=None, size=10.5):
    if text is not None:
        cell.value = text
    cell.font = F(size, True, "FFFFFF")
    cell.fill = fill(NAVY)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER


def body(cell, text=None, wrap=True, align="left", size=10, color="22314B", bold=False):
    if text is not None:
        cell.value = text
    cell.font = F(size, bold, color)
    cell.alignment = Alignment(horizontal=align, vertical="top", wrap_text=wrap)
    cell.border = BORDER


def title_bar(ws, text, last_col, sub=None):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    c = ws.cell(row=1, column=1, value=text)
    c.font = F(15, True, "FFFFFF")
    c.fill = fill(NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 32
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = F(9.5, False, "5B6A82", True)
        c2.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
        ws.row_dimensions[2].height = 30


def section(ws, row, text, last_col):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
    c = ws.cell(row=row, column=1, value=text)
    c.font = F(11, True, NAVY)
    c.fill = fill(LIGHT)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 22


def color_level(cell, level):
    if level.startswith("高"):
        cell.fill = fill("E2F5E9"); cell.font = F(10, True, "0F7B3F")
    elif level.startswith("低"):
        cell.fill = fill("FDE7E4"); cell.font = F(10, True, "B42318")
    else:
        cell.fill = fill("FDF0D3"); cell.font = F(10, True, "9A5B00")


def para(ws, row, text, last_col=8, bold=False, size=10.5, color="22314B", height=None, fillc=None):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = F(size, bold, color)
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    if fillc:
        cell.fill = fill(fillc)
    if height:
        ws.row_dimensions[row].height = height


# ---------------- 缓存值写入 ----------------
def patch_cache(path, values_by_sheet):
    """values_by_sheet: {sheet_name: {ref: numeric}}"""
    tmp = path + ".tmp"
    shutil.copy(path, tmp)
    zin = zipfile.ZipFile(tmp, "r")
    wb = ET.fromstring(zin.read("xl/workbook.xml"))
    rels = ET.fromstring(zin.read("xl/_rels/workbook.xml.rels"))
    rid2t = {r.get("Id"): r.get("Target") for r in rels}
    name2file = {}
    for sh in wb.iter(A("sheet")):
        tgt = rid2t.get(sh.get("{%s}id" % NS_REL))
        if tgt:
            tgt = tgt.lstrip("/")
            name2file[sh.get("name")] = tgt if tgt.startswith("xl/") else "xl/" + tgt
    ET.register_namespace("", NS_MAIN)
    ET.register_namespace("r", NS_REL)
    files = {}
    for name, vals in values_by_sheet.items():
        f = name2file.get(name)
        if not f:
            continue
        root = ET.fromstring(zin.read(f))
        for c in root.iter(A("c")):
            ref = c.get("r")
            if ref in vals and c.find(A("f")) is not None:
                v = c.find(A("v"))
                if v is None:
                    v = ET.SubElement(c, A("v"))
                val = vals[ref]
                v.text = repr(float(val)) if isinstance(val, float) else str(val)
        files[f] = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    # 打开时强制重算
    wbroot = ET.fromstring(zin.read("xl/workbook.xml"))
    calc = wbroot.find(A("calcPr"))
    if calc is None:
        calc = ET.SubElement(wbroot, A("calcPr"))
    calc.set("calcId", "0")
    calc.set("fullCalcOnLoad", "1")
    files["xl/workbook.xml"] = ET.tostring(wbroot, encoding="UTF-8", xml_declaration=True)
    out = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        out.writestr(item, files.get(item.filename, zin.read(item.filename)))
    out.close()
    zin.close()
    os.remove(tmp)


# ---------------- 主体 ----------------
def build(data, out_path):
    meta = data["meta"]
    dims = data["dimensions"]
    custs = data["customers"]
    presets = data.get("presets") or [{"key": "even", "name": "均衡", "weights": {d["key"]: 1 for d in dims}}]
    market = data.get("market", [])
    th = meta.get("thresholds", {"high": 75, "mid": 55})
    ndim = len(dims)
    rat0 = 9                      # 评级起始列 I
    sc0 = rat0 + ndim             # 分值起始列
    tot_col = sc0 + ndim          # 排序参考分列
    sig_col = tot_col + 1         # 最强信号列

    wb = Workbook()

    # ---------- 1 总览 ----------
    ws = wb.active
    ws.title = "客户判断总览"
    ws.sheet_view.showGridLines = False
    title_bar(ws, meta["title"] + " · 客户准入总览", sig_col,
              "销售产品：%s　|　卖家：%s　|　判断时点：%s　|　排序参考分仅用于决定跟进顺序，不是评级、不代表成交概率。"
              % (meta["product"], meta["seller"], meta["as_of"]))
    HEAD = ["排名", "客户名称", "证券代码", "所在地/基地", "距发货地", "年需求估算", "年采购额估算", "建议动作"]
    HEAD += [d["name"] for d in dims] + [d["name"] + "分" for d in dims] + ["排序参考分", "最强积极信号"]
    for j, h in enumerate(HEAD, 1):
        hdr(ws.cell(row=4, column=j), h)
    ws.row_dimensions[4].height = 34

    for i, c in enumerate(custs):
        r = 5 + i
        ws.cell(row=r, column=1).value = "=RANK(%s%d,$%s$5:$%s$%d)" % (
            get_column_letter(tot_col), r, get_column_letter(tot_col), get_column_letter(tot_col), 4 + len(custs))
        ws.cell(row=r, column=2, value=c["name"])
        ws.cell(row=r, column=3, value=c.get("code", ""))
        ws.cell(row=r, column=4, value=c.get("location", ""))
        ws.cell(row=r, column=5, value=c.get("distance", ""))
        ws.cell(row=r, column=6, value=c.get("demand", ""))
        ws.cell(row=r, column=7, value=c.get("spend", ""))
        ws.cell(row=r, column=8, value=c.get("action", ""))
        for k, d in enumerate(dims):
            cell = ws.cell(row=r, column=rat0 + k, value=c["dims"][d["key"]]["level"])
            color_level(cell, c["dims"][d["key"]]["level"])
            ws.cell(row=r, column=sc0 + k, value=c["dims"][d["key"]]["score"])
        ws.cell(row=r, column=tot_col).value = "=SUMPRODUCT(%s%d:%s%d,'权重与排序'!$B$5:$%s$5)/SUM('权重与排序'!$B$5:$%s$5)" % (
            get_column_letter(sc0), r, get_column_letter(sc0 + ndim - 1), r,
            get_column_letter(1 + ndim), get_column_letter(1 + ndim))
        ws.cell(row=r, column=sig_col, value=c.get("best", ""))
        for j in range(1, sig_col + 1):
            cell = ws.cell(row=r, column=j)
            body(cell)
            if j == 1:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = F(12, True, NAVY)
            if j in (rat0,): pass
            if rat0 <= j < rat0 + ndim:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            if j in (5, 6, 7):
                cell.font = F(9.5, False, "4B5D7C")
            if sc0 <= j < sc0 + ndim:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = F(10, False, "3B4A63")
            if j == 2:
                cell.font = F(10.5, True, "1A2946")
            if j == sig_col:
                cell.font = F(9.5, False, "4B5D7C")
        ws.cell(row=r, column=tot_col).number_format = "0.0"
        ws.cell(row=r, column=tot_col).font = F(12, True, ACC)
        ws.row_dimensions[r].height = 96

    widths = {"A": 6, "B": 18, "C": 13, "D": 30, "E": 24, "F": 24, "G": 14, "H": 44}
    for k in range(ndim):
        widths[get_column_letter(rat0 + k)] = 9
        widths[get_column_letter(sc0 + k)] = 8
    widths[get_column_letter(tot_col)] = 11
    widths[get_column_letter(sig_col)] = 44
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "C5"
    note = 4 + len(custs) + 2
    ws.merge_cells(start_row=note, start_column=1, end_row=note, end_column=sig_col)
    c = ws.cell(row=note, column=1,
                value="注：评级阈值 高≥%d / 中%d–%d / 低<%d；分数是事实→排序的映射，看到「低」时请优先读同行的「事实」列。需求/运费/距离为估算口径，成交前以客户确认数为准。"
                      % (th["high"], th["mid"], th["high"] - 1, th["mid"]))
    c.font = F(9, False, "7C8AA1", True)
    c.alignment = Alignment(wrap_text=True, vertical="center")

    # ---------- 2 七维判断明细 ----------
    ws2 = wb.create_sheet("七维判断明细")
    ws2.sheet_view.showGridLines = False
    title_bar(ws2, "七维判断明细 · 一客户一维度一行，事实与证据可追溯", 9,
              "「口径」标注估算/核实；来源对应本工作簿「数据来源」表。评级只是锚点，请以事实为准。")
    H2 = ["客户", "维度", "评级", "分值", "事实与依据", "口径", "证据来源", "来源链接", "来源日期"]
    for j, h in enumerate(H2, 1):
        hdr(ws2.cell(row=4, column=j), h)
    ws2.row_dimensions[4].height = 30
    r = 5
    for c in custs:
        for d in dims:
            x = c["dims"][d["key"]]
            ev = (x.get("evidence") or [{}])[0]
            ws2.cell(row=r, column=1, value=c["name"])
            ws2.cell(row=r, column=2, value=d["name"])
            ws2.cell(row=r, column=3, value=x["level"])
            ws2.cell(row=r, column=4, value=x["score"])
            ws2.cell(row=r, column=5, value=x["fact"])
            ws2.cell(row=r, column=6, value=x.get("basis", ""))
            ws2.cell(row=r, column=7, value=ev.get("label", ""))
            lc = ws2.cell(row=r, column=8, value="打开链接")
            if ev.get("url"):
                lc.hyperlink = ev["url"]
            lc.font = F(9.5, True, "2360D6")
            ws2.cell(row=r, column=9, value=ev.get("date", ""))
            for j in range(1, 10):
                cell = ws2.cell(row=r, column=j)
                body(cell)
                if j in (3, 4, 6, 9):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                if j == 3:
                    color_level(cell, x["level"])
                if j == 1:
                    cell.font = F(10, True, "1A2946")
                if j == 2:
                    cell.font = F(10, True, "3B4A63")
                if j == 8:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
            ws2.row_dimensions[r].height = 66
            r += 1
    for col, w in {"A": 18, "B": 11, "C": 8, "D": 7, "E": 80, "F": 9, "G": 42, "H": 12, "I": 12}.items():
        ws2.column_dimensions[col].width = w
    ws2.freeze_panes = "B5"
    ws2.auto_filter.ref = "A4:I%d" % (r - 1)

    # ---------- 3 权重与排序 ----------
    ws3 = wb.create_sheet("权重与排序")
    ws3.sheet_view.showGridLines = False
    title_bar(ws3, "权重与排序 · 改黄色权重格，全表联动重排", 2 + ndim,
              "「当前权重」影响总览表与客户排名；「情景对比」仅演示不同权重下排序如何变化——事实不变，排序变。")
    section(ws3, 3, "A. 当前权重（可修改，0–5）", 2 + ndim)
    ws3.cell(row=4, column=1, value="权重项")
    for k, d in enumerate(dims):
        hdr(ws3.cell(row=4, column=2 + k), d["name"])
    hdr(ws3.cell(row=4, column=2 + ndim), "合计")
    ws3.cell(row=5, column=1, value="权重（可调）")
    for k in range(ndim):
        cell = ws3.cell(row=5, column=2 + k, value=1)
        body(cell, align="center")
        cell.fill = fill(INPUT)
        cell.font = F(11, True, ACC)
    ws3.cell(row=5, column=2 + ndim).value = "=SUM(B5:%s5)" % get_column_letter(1 + ndim)
    ws3.cell(row=5, column=2 + ndim).font = F(10, True, "3B4A63")
    ws3.cell(row=5, column=2 + ndim).alignment = Alignment(horizontal="center")
    ws3.row_dimensions[4].height = 26
    ws3.row_dimensions[5].height = 24
    dv = DataValidation(type="decimal", operator="between", formula1="0", formula2="5",
                        showErrorMessage=True, errorTitle="权重范围", error="请输入 0–5 的数字")
    ws3.add_data_validation(dv)
    dv.add("B5:%s5" % get_column_letter(1 + ndim))

    r_rank = 8
    section(ws3, 7, "B. 客户排序（当前权重）", 2 + ndim)
    for j, h in enumerate(["客户", "加权排序分", "排名"], 1):
        hdr(ws3.cell(row=r_rank, column=j), h)
    for i, c in enumerate(custs):
        r = r_rank + 1 + i
        ws3.cell(row=r, column=1, value=c["name"])
        ws3.cell(row=r, column=2).value = "=SUMPRODUCT('客户判断总览'!%s%d:%s%d,$B$5:$%s$5)/SUM($B$5:$%s$5)" % (
            get_column_letter(sc0), 5 + i, get_column_letter(sc0 + ndim - 1), 5 + i,
            get_column_letter(1 + ndim), get_column_letter(1 + ndim))
        ws3.cell(row=r, column=3).value = "=RANK(B%d,$B$%d:$B$%d)" % (r, r_rank + 1, r_rank + len(custs))
        for j in range(1, 4):
            cell = ws3.cell(row=r, column=j)
            body(cell, align="center" if j > 1 else "left")
            if j == 1:
                cell.font = F(10, True, "1A2946")
            if j == 2:
                cell.font = F(11, True, ACC)
                cell.number_format = "0.0"
            if j == 3:
                cell.font = F(11, True, NAVY)

    r_sc = r_rank + len(custs) + 4
    section(ws3, r_sc - 1, "C. 情景对比：不同权重下的排序（只演示，不改 A 区）", 1 + len(presets))
    for j, h in enumerate(["场景"] + [d["name"] for d in dims], 1):
        hdr(ws3.cell(row=r_sc, column=j), h)
    for i, p in enumerate(presets):
        r = r_sc + 1 + i
        ws3.cell(row=r, column=1, value=p["name"]).font = F(10, True, "1A2946")
        ws3.cell(row=r, column=1).border = BORDER
        for k, d in enumerate(dims):
            cell = ws3.cell(row=r, column=2 + k, value=p["weights"].get(d["key"], 1))
            body(cell, align="center")
            cell.font = F(10, False, "3B4A63")

    r_tab = r_sc + len(presets) + 2
    hdr(ws3.cell(row=r_tab, column=1), "客户")
    for s, p in enumerate(presets):
        hdr(ws3.cell(row=r_tab, column=2 + s), p["name"])
    for i, c in enumerate(custs):
        r = r_tab + 1 + i
        ws3.cell(row=r, column=1, value=c["name"]).font = F(10, True, "1A2946")
        ws3.cell(row=r, column=1).border = BORDER
        for s, p in enumerate(presets):
            cell = ws3.cell(row=r, column=2 + s)
            cell.value = "=SUMPRODUCT('客户判断总览'!%s%d:%s%d,$B$%d:$%s$%d)/SUM($B$%d:$%s$%d)" % (
                get_column_letter(sc0), 5 + i, get_column_letter(sc0 + ndim - 1), 5 + i,
                r_sc + 1 + s, get_column_letter(1 + ndim), r_sc + 1 + s,
                r_sc + 1 + s, get_column_letter(1 + ndim), r_sc + 1 + s)
            body(cell, align="center")
            cell.font = F(10.5, False, ACC)
            cell.number_format = "0.0"
    for col in ["A"]:
        ws3.column_dimensions[col].width = 18
    for k in range(2 + ndim):
        ws3.column_dimensions[get_column_letter(2 + k)].width = 10
    ws3.freeze_panes = "A6"

    # ---------- 4 待确认清单 ----------
    ws4 = wb.create_sheet("待确认清单")
    ws4.sheet_view.showGridLines = False
    title_bar(ws4, "待确认清单 · 问对了再投销售资源", 6,
              "每条问题都对应一个「影响哪个判断」：客户答不上来或含糊其辞，本身就是信号。")
    for j, h in enumerate(["序号", "客户", "优先级", "待确认事项", "为什么重要（影响哪个判断）", "建议对象/方式"], 1):
        hdr(ws4.cell(row=4, column=j), h)
    ws4.row_dimensions[4].height = 30
    pri_fill = {"P1": "FDE7E4", "P2": "FDF0D3", "P3": "E2F5E9", "P4": "EAF1FC"}
    n, r = 1, 5
    for c in custs:
        for a in c.get("asks", []):
            ws4.cell(row=r, column=1, value=n)
            ws4.cell(row=r, column=2, value=c["name"])
            p = c.get("priority", "P3")
            ws4.cell(row=r, column=3, value=p)
            ws4.cell(row=r, column=4, value=a["q"])
            ws4.cell(row=r, column=5, value="%s｜%s" % (a.get("dim", ""), a.get("why", "")))
            ws4.cell(row=r, column=6, value=a.get("who", ""))
            for j in range(1, 7):
                cell = ws4.cell(row=r, column=j)
                body(cell)
                if j in (1, 3):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                if j == 3:
                    cell.font = F(10, True)
                    cell.fill = fill(pri_fill.get(p, "EAF1FC"))
                if j == 1:
                    cell.font = F(9.5, False, "7C8AA1")
                if j == 2:
                    cell.font = F(10, True, "1A2946")
            ws4.row_dimensions[r].height = 52
            n += 1
            r += 1
    for col, w in {"A": 6, "B": 18, "C": 8, "D": 58, "E": 44, "F": 26}.items():
        ws4.column_dimensions[col].width = w
    ws4.freeze_panes = "A5"
    ws4.auto_filter.ref = "A4:F%d" % (r - 1)

    # ---------- 5 数据来源 ----------
    ws5 = wb.create_sheet("数据来源")
    ws5.sheet_view.showGridLines = False
    title_bar(ws5, "数据来源 · 每条事实可回溯到公开链接", 6,
              "来源类型：年报/半年报/公告/研报/政府函件/行业资讯/媒体/招标/报价。日期为发布日。")
    for j, h in enumerate(["编号", "所属", "类型", "来源名称", "链接", "日期"], 1):
        hdr(ws5.cell(row=4, column=j), h)
    ws5.row_dimensions[4].height = 28
    n, r = 1, 5
    for c in custs:
        for s in c.get("sources", []):
            ws5.cell(row=r, column=1, value="S%02d" % n)
            ws5.cell(row=r, column=2, value=c["name"])
            ws5.cell(row=r, column=3, value=s.get("type", ""))
            ws5.cell(row=r, column=4, value=s.get("label", ""))
            lc = ws5.cell(row=r, column=5, value="打开链接")
            if s.get("url"):
                lc.hyperlink = s["url"]
            lc.font = F(9.5, True, "2360D6")
            ws5.cell(row=r, column=6, value=s.get("date", ""))
            for j in range(1, 7):
                cell = ws5.cell(row=r, column=j)
                body(cell)
                if j in (1, 3, 6):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                if j == 2:
                    cell.font = F(10, True, "1A2946")
            ws5.row_dimensions[r].height = 40
            n += 1
            r += 1
    for s in market:
        if not s.get("url"):
            continue
        ws5.cell(row=r, column=1, value="M%02d" % n)
        ws5.cell(row=r, column=2, value="市场背景")
        ws5.cell(row=r, column=3, value="行情/报价")
        ws5.cell(row=r, column=4, value=s.get("metric", ""))
        lc = ws5.cell(row=r, column=5, value="打开链接")
        lc.hyperlink = s["url"]
        lc.font = F(9.5, True, "2360D6")
        ws5.cell(row=r, column=6, value=s.get("when", ""))
        for j in range(1, 7):
            cell = ws5.cell(row=r, column=j)
            body(cell)
            if j in (1, 3, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
        ws5.row_dimensions[r].height = 30
        n += 1
        r += 1
    for col, w in {"A": 8, "B": 18, "C": 10, "D": 46, "E": 12, "F": 12}.items():
        ws5.column_dimensions[col].width = w
    ws5.freeze_panes = "A5"
    ws5.auto_filter.ref = "A4:F%d" % (r - 1)

    # ---------- 6 市场背景 ----------
    ws6 = wb.create_sheet("市场背景")
    ws6.sheet_view.showGridLines = False
    title_bar(ws6, "市场背景 · 行情快照（%s）" % meta["as_of"], 5,
              "先确定市场处于买方还是卖方市场：这决定客户压价意愿、开工率假设与你的报价空间。")
    for j, h in enumerate(["指标", "数值", "时点", "来源", "链接"], 1):
        hdr(ws6.cell(row=4, column=j), h)
    ws6.row_dimensions[4].height = 28
    r = 5
    for s in market:
        ws6.cell(row=r, column=1, value=s.get("metric", ""))
        ws6.cell(row=r, column=2, value=s.get("value", ""))
        ws6.cell(row=r, column=3, value=s.get("when", ""))
        ws6.cell(row=r, column=4, value=s.get("source", ""))
        lc = ws6.cell(row=r, column=5, value="打开链接")
        if s.get("url"):
            lc.hyperlink = s["url"]
        lc.font = F(9.5, True, "2360D6")
        for j in range(1, 6):
            cell = ws6.cell(row=r, column=j)
            body(cell)
            if j in (3, 5):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            if j == 1:
                cell.font = F(10, True, "1A2946")
            if j == 2:
                cell.font = F(10.5, True, ACC)
        ws6.row_dimensions[r].height = 24
        r += 1
    for col, w in {"A": 24, "B": 24, "C": 12, "D": 20, "E": 12}.items():
        ws6.column_dimensions[col].width = w
    ws6.freeze_panes = "A5"

    # ---------- 7 阅读说明 ----------
    ws7 = wb.create_sheet("阅读说明")
    ws7.sheet_view.showGridLines = False
    title_bar(ws7, "阅读说明 · 方法与口径", 6,
              "这份工作簿回答一个问题：把有限的销售时间投给谁？它给出事实、评级与排序参考，最终判断权在你。")
    r = 4
    para(ws7, r, "一、怎么用（3 步）", bold=True, size=11, color=NAVY, height=22)
    r += 1
    for t in ["① 带入：把客户名称（或客户池）与销售产品填入——维度数据随之就位；",
              "② 看事实：逐维读「七维判断明细」，每个维度都有依据、口径（估算/核实）与来源链接；",
              "③ 定顺序：在「权重与排序」里调权重，用排序结果决定本周先打谁——但事实不因权重改变。"]:
        para(ws7, r, t, height=20)
        r += 1
    r += 1
    para(ws7, r, "二、维度定义", bold=True, size=11, color=NAVY, height=22)
    r += 1
    for j, h in enumerate(["维度", "看什么", "高 / 中 / 低锚点"], 1):
        hdr(ws7.cell(row=r, column=j), h)
    ws7.row_dimensions[r].height = 24
    r += 1
    for d in dims:
        rubric = d.get("rubric") or DEFAULT_RUBRIC.get(d["key"], "")
        vals = [d["name"], d.get("hint", ""), rubric]
        for j, v in enumerate(vals, 1):
            body(ws7.cell(row=r, column=j, value=v), size=9.5)
        ws7.row_dimensions[r].height = 36
        r += 1
    r += 1
    para(ws7, r, "三、评分与阈值", bold=True, size=11, color=NAVY, height=22)
    r += 1
    for t in ["维度分值 0–100 是「事实 → 排序」的映射：排序分 = Σ(维度分 × 权重) / Σ权重。",
              "评级阈值：高 ≥%d、中 %d–%d、低 <%d。评级只是快速锚点，请始终以「事实」列为准。" % (th["high"], th["mid"], th["high"] - 1, th["mid"]),
              "「不确定性」维度分数越低=风险越大（与其他维度方向相反），总览中以红色提示。"]:
        para(ws7, r, t, height=20)
        r += 1
    r += 1
    para(ws7, r, "四、估算口径（务必在成交前核实）", bold=True, size=11, color=NAVY, height=22)
    r += 1
    bullets = meta.get("estimate_bullets") or [
        "年需求量 ≈ 客户产能/熔量 × 单耗 × 年运行天数（单耗取该行业常用区间中值，见 references/scoring-rubric.md）；",
        "年采购额按现价估算（见「市场背景」表）；",
        "公路运费按 0.35–0.5 元/吨·公里估算，距离取地图公路里程近似值；",
        "客户产线/开工数据以最近一期财报、环评、行业产线动态为准，冷修/改造期需单独扣减。"]
    for t in bullets:
        para(ws7, r, t, height=20)
        r += 1
    r += 1
    para(ws7, r, "五、局限与免责", bold=True, size=11, color=NAVY, height=22)
    r += 1
    for t in ["本工作簿依据 %s 时点公开信息整理，实际采购量、价格与账期需向客户直接确认；" % meta["as_of"],
              "评分与排序是销售资源分配辅助工具，不构成投资、授信或采购建议；",
              "事实更新后请同步更新「七维判断明细」与来源日期，历史判断不应被当成永久结论。"]:
        para(ws7, r, t, height=20)
        r += 1
    for col, w in {"A": 16, "B": 34, "C": 60, "D": 18, "E": 18, "F": 18}.items():
        ws7.column_dimensions[col].width = w

    wb.save(out_path)

    # ---------- 缓存值 ----------
    def wsum(p):
        return sum(p["weights"].get(d["key"], 1) for d in dims)

    def score(c, p):
        s = sum(p["weights"].get(d["key"], 1) * c["dims"][d["key"]]["score"] for d in dims)
        return s / wsum(p)

    def sc_col(i, s):
        return get_column_letter(sc0 + i) + str(5 + s)

    vals = {}
    v1 = {}
    order = sorted(custs, key=lambda c: (-score(c, presets[0]), c["name"]))
    rank_of = {c["name"]: i + 1 for i, c in enumerate(order)}
    for i, c in enumerate(custs):
        v1["%s%d" % (get_column_letter(tot_col), 5 + i)] = score(c, presets[0])
        v1["A%d" % (5 + i)] = rank_of[c["name"]]
    vals["客户判断总览"] = v1

    v3 = {"%s5" % get_column_letter(1 + ndim + 1): float(wsum(presets[0]))}
    for i, c in enumerate(custs):
        v3["B%d" % (r_rank + 1 + i)] = score(c, presets[0])
        v3["C%d" % (r_rank + 1 + i)] = v1["A%d" % (5 + i)]
    for s, p in enumerate(presets):
        for i, c in enumerate(custs):
            v3["%s%d" % (get_column_letter(2 + s), r_tab + 1 + i)] = score(c, p)
    vals["权重与排序"] = v3
    patch_cache(out_path, vals)
    return out_path


def main():
    if len(sys.argv) < 3:
        print("用法: python build_workbook.py <data.json> <out.xlsx>")
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    out = os.path.abspath(sys.argv[2])
    build(data, out)
    print("OK ->", out)


if __name__ == "__main__":
    main()
