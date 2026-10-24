#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inquiry.json → Excel 核验工作簿（多表、可筛选、可打印）。

用法:
    python build_xlsx.py inquiry.json out.xlsx
依赖: openpyxl>=3.1
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import datetime

import _common as C

if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.formatting.rule import CellIsRule, FormulaRule
except ImportError:  # pragma: no cover
    raise SystemExit("需要 openpyxl：pip install -r requirements.txt")

# ------------------------------------------------------------------ 主题
FONT_CN = "Microsoft YaHei"
C_INK = "10161C"
C_BRAND = "0E5B52"
C_BRAND_L = "E3F0ED"
C_LINE = "D8DCD8"
C_HEAD = "F0F1ED"
C_MUTED = "5B6875"

FILL = {
    "verified": PatternFill("solid", fgColor="E7F2EA"),
    "discrepancy": PatternFill("solid", fgColor="FBE9E6"),
    "unverified": PatternFill("solid", fgColor="E9ECEF"),
    "not_applicable": PatternFill("solid", fgColor="EEF0F2"),
}
FONT_STATUS = {
    "verified": Font(name=FONT_CN, size=10, color="1B6B3A", bold=True),
    "discrepancy": Font(name=FONT_CN, size=10, color="A8321F", bold=True),
    "unverified": Font(name=FONT_CN, size=10, color="424B55", bold=True),
    "not_applicable": Font(name=FONT_CN, size=10, color="5D6672", bold=True),
}
THIN = Side(style="thin", color=C_LINE)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP_TOP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
# 注意：PatternFill 不要跨单元格复用同一对象（openpyxl 会把它挂到多个 cell 上）
HEAD_FILL = PatternFill("solid", fgColor=C_HEAD)

STATUS_TXT = C.STATUS_LABEL
GRADE_TXT = {"A": "A 官方", "B": "B 独立", "C": "C 媒体", "D": "D 自述"}
SEV_TXT = {"high": "高", "medium": "中", "low": "低"}


def clean(v):
    """Openpyxl 不接受控制字符。"""
    if isinstance(v, str):
        return "".join(ch for ch in v if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return v


def title_block(ws, title, sub, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=title)
    c.font = Font(name=FONT_CN, size=15, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_BRAND)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c = ws.cell(row=2, column=1, value=sub)
    c.font = Font(name=FONT_CN, size=9.5, color=C_MUTED)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 20
    return 3


def header_row(ws, row, headers, widths=None, height=26, freeze=True, autofilter=True):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(name=FONT_CN, size=10, bold=True, color=C_INK)
        c.fill = HEAD_FILL
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[row].height = height
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
    if freeze:
        ws.freeze_panes = ws.cell(row=row + 1, column=1)
    if autofilter and not ws.auto_filter.ref:
        ws.auto_filter.ref = f"A{row}:{get_column_letter(len(headers))}{row}"
    return row


def write_rows(ws, start_row, rows, status_col=None, status_keys=None, center_cols=(), height=None):
    """status_col：需要按状态着色的列号（1-based）。
    status_keys：与 rows 平行的 ASCII 状态键列表（verified/discrepancy/...），
    必须传这个而不是从中文单元格文本反查——中文文本在非 UTF-8 环境里可能被破坏。"""
    r = start_row
    for idx, row in enumerate(rows):
        for ci, val in enumerate(row, 1):
            c = ws.cell(row=r, column=ci, value=clean(val))
            c.font = Font(name=FONT_CN, size=9.5, color=C_INK)
            c.alignment = CENTER if ci in center_cols else WRAP_TOP
            c.border = BORDER
        if status_col and status_keys and idx < len(status_keys):
            key = status_keys[idx]
            if key in FILL:
                cc = ws.cell(row=r, column=status_col)
                cc.fill = PatternFill("solid", fgColor=FILL[key].fgColor.rgb[-6:])
                cc.font = FONT_STATUS[key]
        if height:
            ws.row_dimensions[r].height = height
        r += 1
    return r


def status_cell(ws, row, col, status):
    """按状态给单个单元格上色（供非整行写入的表使用）。"""
    if status in FILL:
        c = ws.cell(row=row, column=col)
        c.fill = FILL[status]
        c.font = FONT_STATUS[status]


def add_legend(ws, row, ncol, extra=""):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
    c = ws.cell(row=row, column=1, value=extra)
    c.font = Font(name=FONT_CN, size=9, italic=True, color=C_MUTED)
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws.row_dimensions[row].height = 34


# ------------------------------------------------------------------ 各表

def sheet_cover(wb, D):
    ws = wb.active
    ws.title = "00_封面"
    ws.sheet_view.showGridLines = False
    M, S = D["meta"], D["stats"]
    ncol = 4
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 40

    ws.merge_cells("A1:D2")
    c = ws["A1"]
    c.value = ("[模拟] " if M.get("synthetic") else "") + M["title"]
    c.font = Font(name=FONT_CN, size=20, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_BRAND)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=2, wrap_text=True)
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 18

    ws.merge_cells("A3:D3")
    c = ws["A3"]
    c.value = M.get("subtitle") or ""
    c.font = Font(name=FONT_CN, size=11, color=C_BRAND)
    c.fill = PatternFill("solid", fgColor=C_BRAND_L)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=2)

    ws.merge_cells("A4:D4")
    c = ws["A4"]
    c.value = "本工作簿是单文件 HTML 交互报告的配套附件：五区块核验 / 证据来源 / 问题清单 / 下一步行动"
    c.font = Font(name=FONT_CN, size=9, color=C_MUTED)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=2)

    r = 5
    ws.cell(row=r, column=1, value="一句话结论").font = Font(name=FONT_CN, size=10, bold=True, color=C_BRAND)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c = ws.cell(row=r, column=2, value=S.get("verdict_line", ""))
    c.font = Font(name=FONT_CN, size=11.5, bold=True, color=C_INK)
    c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 30

    rows = [
        ("询盘编号", M.get("inquiry_id"), "核验基准日", M.get("as_of")),
        ("产品", M.get("product"), "规格", M.get("product_spec")),
        ("询盘数量", M.get("quantity"), "交付条款", M.get("incoterm")),
        ("包装", M.get("packaging"), "HS 编码", M.get("hs_code")),
        ("编制", M.get("prepared_by"), "数据性质", "模拟样例（虚构主体）" if M.get("synthetic") else "真实询盘"),
    ]
    r += 2
    ws.cell(row=r, column=1, value="询盘要素").font = Font(name=FONT_CN, size=12, bold=True, color=C_INK)
    r += 1
    for a, b, cc_, d in rows:
        for i, (k, v) in enumerate(((a, b), (cc_, d))):
            kc = ws.cell(row=r, column=1 + i * 2, value=k)
            kc.font = Font(name=FONT_CN, size=9.5, bold=True, color=C_MUTED)
            kc.fill = PatternFill("solid", fgColor=C_HEAD)
            kc.alignment = WRAP_TOP
            kc.border = BORDER
            vc = ws.cell(row=r, column=2 + i * 2, value=clean(v or "—"))
            vc.font = Font(name=FONT_CN, size=10, color=C_INK)
            vc.alignment = WRAP_TOP
            vc.border = BORDER
        ws.row_dimensions[r].height = 30
        r += 1

    # KPI
    r += 1
    ws.cell(row=r, column=1, value="核验 KPI").font = Font(name=FONT_CN, size=12, bold=True, color=C_INK)
    r += 1
    kpis = [
        ("核验项合计", S.get("checks_total", 0), "已核实", S["status"]["verified"]),
        ("存在疑点", S["status"]["discrepancy"], "未核实", S["status"]["unverified"]),
        ("公开来源", S.get("sources", 0), "资料索取项", sum(S["requests"].values())),
        ("行动项（未完成）", S.get("actions_open", 0), "风险条目", S.get("risks", 0)),
    ]
    for a, b, cc_, d in kpis:
        for i, (k, v) in enumerate(((a, b), (cc_, d))):
            kc = ws.cell(row=r, column=1 + i * 2, value=k)
            kc.font = Font(name=FONT_CN, size=9.5, bold=True, color=C_MUTED)
            kc.alignment = WRAP_TOP
            kc.border = BORDER
            vc = ws.cell(row=r, column=2 + i * 2, value=v)
            vc.font = Font(name=FONT_CN, size=16, bold=True, color=C_BRAND)
            vc.alignment = Alignment(horizontal="center", vertical="center")
            vc.border = BORDER
        ws.row_dimensions[r].height = 26
        r += 1

    # 区块成绩
    r += 1
    ws.cell(row=r, column=1, value="分区块统计").font = Font(name=FONT_CN, size=12, bold=True, color=C_INK)
    r += 1
    header_row(ws, r, ["区块", "名称", "已核实", "存在疑点", "未核实", "合计"])
    for i in (5, 6):
        ws.column_dimensions[get_column_letter(i)].width = 12
    r += 1
    for s in C.SECTIONS:
        cnt = S["section"].get(s["id"], {})
        vals = [s["id"], s["title"], cnt.get("verified", 0), cnt.get("discrepancy", 0), cnt.get("unverified", 0),
                sum(cnt.values())]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=ci, value=v)
            c.font = Font(name=FONT_CN, size=10)
            c.alignment = CENTER if ci > 2 else WRAP_TOP
            c.border = BORDER
        r += 1

    # 声明
    r += 1
    ws.cell(row=r, column=1, value="口径与声明").font = Font(name=FONT_CN, size=12, bold=True, color=C_INK)
    r += 1
    notes = [M.get("synthetic_note"), M.get("disclaimer")] + (D.get("boundaries") or [])
    for n in notes:
        if not n:
            continue
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        c = ws.cell(row=r, column=1, value="• " + clean(n))
        c.font = Font(name=FONT_CN, size=9, color=C_MUTED)
        c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
        ws.row_dimensions[r].height = max(18, 13 * (len(n) // 80 + 1))
        r += 1

    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return ws


def sheet_inquiry(wb, D):
    ws = wb.create_sheet("01_询盘原文")
    ws.sheet_view.showGridLines = False
    q = D["inquiry"]
    r = title_block(ws, "询盘原文与附件", f"{q.get('subject', '')}", 2)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 86

    meta = [("发件人", q.get("from")), ("发件人名/职位", q.get("from_name")), ("收件人", q.get("to")),
            ("时间", q.get("date")), ("Reply-To", q.get("reply_to"))]
    for k, v in meta:
        ws.cell(row=r, column=1, value=k).font = Font(name=FONT_CN, size=9.5, bold=True, color=C_MUTED)
        ws.cell(row=r, column=1).border = BORDER
        c = ws.cell(row=r, column=2, value=clean(v or "—"))
        c.font = Font(name=FONT_CN, size=10)
        c.alignment = WRAP_TOP
        c.border = BORDER
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="正文").font = Font(name=FONT_CN, size=11, bold=True)
    r += 1
    body = "\n".join(q.get("body_lines") or [])
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    c = ws.cell(row=r, column=1, value=clean(body))
    c.font = Font(name="Consolas", size=9.5, color=C_INK)
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    c.fill = PatternFill("solid", fgColor="FBFAF7")
    c.border = BORDER
    ws.row_dimensions[r].height = min(560, max(120, 13.5 * (body.count("\n") + 1)))
    r += 2

    notes = q.get("notes") or []
    if notes:
        ws.cell(row=r, column=1, value="初步观察").font = Font(name=FONT_CN, size=11, bold=True)
        r += 1
        for n in notes:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
            c = ws.cell(row=r, column=1, value="• " + clean(n))
            c.font = Font(name=FONT_CN, size=10)
            c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
            ws.row_dimensions[r].height = max(18, 14 * (len(n) // 90 + 1))
            r += 1

    atts = q.get("attachments") or []
    if atts:
        r += 1
        ws.cell(row=r, column=1, value="附件").font = Font(name=FONT_CN, size=11, bold=True)
        r += 1
        for i, a in enumerate(atts, 1):
            ws.cell(row=r, column=1, value=f"{i}. {a.get('name', '')}").font = Font(name=FONT_CN, size=10, bold=True)
            c = ws.cell(row=r, column=2, value=clean(a.get("note", "")))
            c.font = Font(name=FONT_CN, size=10, color=C_MUTED)
            c.alignment = WRAP_TOP
            ws.row_dimensions[r].height = max(18, 14 * (len(a.get("note", "")) // 90 + 1))
            r += 1
    return ws


def sheet_extract(wb, D):
    ws = wb.create_sheet("02_字段提取")
    r = title_block(ws, "询盘字段提取（照抄 + 标注出处，不做判断）",
                    "公司名 / 地址 / 网站 / 域名 / 邮箱 / 联系人 / 产品 —— 每项落到原文出处", 6)
    header_row(ws, r, ["编号", "字段", "提取值", "原文出处", "置信度", "备注 / 口径"], [8, 16, 34, 40, 10, 52])
    rows = [[e.get("id"), e.get("field"), e.get("value"), e.get("evidence"), e.get("confidence"), e.get("note", "")]
            for e in D["extraction"]]
    r2 = write_rows(ws, r + 1, rows, center_cols=(1, 5))
    add_legend(ws, r2 + 1, 6, "提示：提取只做“照抄 + 标注出处”。任何结论都写在 06_核验结论 里，不在此表。")
    return ws


def sheet_subject(wb, D):
    ws = wb.create_sheet("03_注册主体")
    ws.sheet_view.showGridLines = False
    s = D["subject"]
    r = title_block(ws, "注册主体识别", "名称 → 登记全称 → NIB/登记号 → KBLI；只有登记号相同才算同一主体", 3)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 78
    ws.column_dimensions["C"].width = 14

    header_row(ws, r, ["项目", "内容", "状态"])
    r += 1
    for row in s.get("summary_rows", []):
        vals = [row.get("k"), row.get("v"), "已核实" if row.get("verified") else "未核实"]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=ci, value=clean(v))
            c.font = Font(name=FONT_CN, size=9.5)
            c.alignment = CENTER if ci == 3 else WRAP_TOP
            c.border = BORDER
        key = "verified" if row.get("verified") else "unverified"
        ws.cell(row=r, column=3).fill = FILL[key]
        ws.cell(row=r, column=3).font = FONT_STATUS[key]
        ws.row_dimensions[r].height = 26
        r += 1

    for key, label in (("registry_check", "AHU 登记检索"), ("nib_oss", "NIB / OSS 检索"),
                       ("npwp_tax", "NPWP 税号"), ("customs_id", "海关进口商识别号")):
        obj = s.get(key) or {}
        if not obj:
            continue
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        c = ws.cell(row=r, column=1, value=f"◆ {label} · {obj.get('portal', '')}")
        c.font = Font(name=FONT_CN, size=11, bold=True, color=C_BRAND)
        c.fill = PatternFill("solid", fgColor=C_BRAND_L)
        c.alignment = Alignment(vertical="center", indent=1)
        ws.row_dimensions[r].height = 22
        r += 1
        for k, v in (("检索词", " / ".join(obj.get("search_terms") or [])), ("结果", obj.get("result")),
                     ("说明/边界", obj.get("result_note")), ("状态", STATUS_TXT.get(obj.get("status", "unverified")))):
            if not v:
                continue
            ws.cell(row=r, column=1, value=k).font = Font(name=FONT_CN, size=9.5, bold=True, color=C_MUTED)
            ws.cell(row=r, column=1).border = BORDER
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
            c = ws.cell(row=r, column=2, value=clean(v))
            c.font = Font(name=FONT_CN, size=9.5)
            c.alignment = WRAP_TOP
            c.border = BORDER
            ws.row_dimensions[r].height = max(18, 14 * (len(str(v)) // 78 + 1))
            r += 1

    ws.freeze_panes = "A4"
    return ws


def sheet_business(wb, D):
    ws = wb.create_sheet("04_业务相关性")
    b = D["business_fit"]
    r = title_block(ws, "业务相关性", b.get("headline", ""), 6)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value=clean(b.get("product_use", "")))
    c.font = Font(name=FONT_CN, size=10, color=C_MUTED)
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws.row_dimensions[r].height = 34
    r += 2

    ws.cell(row=r, column=1, value="KBLI / 业务分类对照").font = Font(name=FONT_CN, size=12, bold=True)
    r += 1
    header_row(ws, r, ["编号", "KBLI", "业务分类", "为何相关", "状态", "说明"], [8, 10, 34, 30, 12, 46],
               freeze=False)
    rows = [[k.get("id"), k.get("kode"), k.get("label"), k.get("why"), STATUS_TXT.get(k.get("status"), k.get("status")), k.get("note", "")]
            for k in b.get("keywords", [])]
    r = write_rows(ws, r + 1, rows, status_col=5, status_keys=[k.get("status") for k in b.get("keywords", [])],
                   center_cols=(1, 2, 5))

    r += 1
    ws.cell(row=r, column=1, value="需求量化（用量级判断采购规模是否合理）").font = Font(name=FONT_CN, size=12, bold=True)
    r += 1
    header_row(ws, r, ["指标", "数值", "说明"], freeze=False)
    r += 1
    for d in b.get("demand_math", []):
        ws.cell(row=r, column=1, value=clean(d.get("label"))).font = Font(name=FONT_CN, size=9.5, bold=True)
        ws.cell(row=r, column=2, value=clean(d.get("value"))).font = Font(name=FONT_CN, size=9.5)
        ws.cell(row=r, column=3, value=clean(d.get("note"))).font = Font(name=FONT_CN, size=9.5, color=C_MUTED)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
        for ci in (1, 2, 3):
            ws.cell(row=r, column=ci).alignment = WRAP_TOP
            ws.cell(row=r, column=ci).border = BORDER
        ws.row_dimensions[r].height = 30
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="业务信号（产品形态、规格、物流、身份）").font = Font(name=FONT_CN, size=12, bold=True)
    r += 1
    header_row(ws, r, ["编号", "信号", "状态", "强度", "说明"], freeze=False)
    r += 1
    for s in b.get("signals", []):
        vals = [s.get("id"), s.get("signal"), STATUS_TXT.get(s.get("status"), s.get("status")),
                SEV_TXT.get(s.get("strength"), s.get("strength")), s.get("note")]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=ci, value=clean(v))
            c.font = Font(name=FONT_CN, size=9.5)
            c.alignment = CENTER if ci in (1, 3, 4) else WRAP_TOP
            c.border = BORDER
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=6)
        k = s.get("status")
        if k in FILL:
            ws.cell(row=r, column=3).fill = PatternFill("solid", fgColor=FILL[k].fgColor.rgb[-6:])
            ws.cell(row=r, column=3).font = FONT_STATUS[k]
        ws.row_dimensions[r].height = 30
        r += 1
    return ws


def sheet_contact(wb, D):
    ws = wb.create_sheet("05_联系方式一致性")
    r = title_block(ws, "网站、域名与联系方式一致性矩阵",
                    "官网 / 域名 / 邮箱 / 地址 / 电话 —— 五项互相对照；只写“对不上什么”，不推断动机", 6)
    header_row(ws, r, ["编号", "核对项", "询盘中的说法", "另一来源的说法", "比对", "说明 / 下一步"],
               [8, 16, 36, 32, 12, 52])
    MM = {"same": "一致", "partial": "部分一致", "different": "不一致", "unknown": "无法比对", "misattribution": "疑似错配"}
    rows = [[m.get("id"), m.get("item"), m.get("claimed"), m.get("other"), MM.get(m.get("mismatch"), m.get("mismatch")), m.get("note")]
            for m in D.get("matrix", [])]
    r = write_rows(ws, r + 1, rows, center_cols=(1, 5))

    r += 1
    ws.cell(row=r, column=1, value="发信认证检查").font = Font(name=FONT_CN, size=12, bold=True)
    r += 1
    header_row(ws, r, ["项目", "观测值", "期望", "比对", "说明"])
    r += 1
    for e in D.get("email_auth", []):
        vals = [e.get("item"), e.get("observed"), e.get("expected"), MM.get(e.get("mismatch")), e.get("note")]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=ci, value=clean(v))
            c.font = Font(name=FONT_CN, size=9.5)
            c.alignment = CENTER if ci == 4 else WRAP_TOP
            c.border = BORDER
        ws.row_dimensions[r].height = 28
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="域名核验").font = Font(name=FONT_CN, size=12, bold=True)
    r += 1
    header_row(ws, r, ["域名", "TLD", "解析", "WHOIS", "官网抓取", "SSL / MX", "说明"])
    ws.column_dimensions[get_column_letter(7)].width = 60
    r += 1
    for d in D.get("domains", []):
        vals = [d.get("domain"), d.get("tld"), d.get("resolve"), d.get("whois"), d.get("website"),
                f"SSL: {d.get('ssl')} / MX: {d.get('mx')}", d.get("note")]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=ci, value=clean(v))
            c.font = Font(name=FONT_CN, size=9)
            c.alignment = WRAP_TOP
            c.border = BORDER
        ws.row_dimensions[r].height = 60
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="关联主体与错配排查").font = Font(name=FONT_CN, size=12, bold=True)
    r += 1
    header_row(ws, r, ["编号", "对象", "关系", "说明", "判定规则"])
    r += 1
    for l in D.get("linkage", []):
        vals = [l.get("id"), l.get("name"), l.get("relation"), l.get("detail"), l.get("rule")]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=ci, value=clean(v))
            c.font = Font(name=FONT_CN, size=9.5)
            c.alignment = WRAP_TOP
            c.border = BORDER
        ws.row_dimensions[r].height = 40
        r += 1
    return ws


def sheet_checks(wb, D):
    ws = wb.create_sheet("06_核验结论")
    r = title_block(ws, "核验结论（可筛选）",
                    "已核实 / 存在疑点 / 未核实 三分；每项都绑定来源与下一步资料。用筛选器看某一区块或某一状态。", 10)
    header_row(ws, r, ["编号", "区块", "核验项", "核验问题", "结论说明", "已核实的事实", "存在疑点",
                       "无法确认", "状态", "严重度", "来源", "下一步 / 边界"],
               [7, 7, 26, 34, 50, 30, 26, 30, 10, 8, 14, 40])
    rows = []
    for c in D["checks"]:
        sec = next((s for s in C.SECTIONS if s["id"] == c["section"]), {})
        rows.append([
            c["id"], f"{c['section']} {sec.get('title', '')}", c["title"], c["question"], c["finding"],
            "\n".join(c.get("verified_facts") or []) or "—",
            "\n".join(c.get("doubts") or []) or "—",
            "\n".join(c.get("unknowns") or []) or "—",
            STATUS_TXT[c["status"]],
            SEV_TXT.get(c["severity"], "") if c["status"] == "discrepancy" else "",
            ", ".join(c.get("source_ids") or []),
            (c.get("action") or "") + ("\n边界：" + c["boundary"] if c.get("boundary") else ""),
        ])
    r = write_rows(ws, r + 1, rows, status_col=9, status_keys=[c["status"] for c in D["checks"]],
                   center_cols=(1, 2, 9, 10, 11))
    add_legend(ws, r + 1, 12, "筛选提示：状态列＝已核实 / 存在疑点 / 未核实；严重度仅对“存在疑点”有意义。")

    # 条件格式：状态文字上用色（防止有人手工改状态却忘了配色）
    last = r
    dv = DataValidation(type="list", formula1='"已核实,存在疑点,未核实,不适用"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"I4:I{last}")
    return ws


def sheet_risks(wb, D):
    ws = wb.create_sheet("07_公开风险")
    r = title_block(ws, "公开风险信息",
                    "经营异常、诉讼、制裁、收汇路径 —— 每条写“看到什么 / 影响什么 / 做什么”", 7)
    header_row(ws, r, ["编号", "类别", "严重度", "状态", "事实（看到了什么）", "影响", "下一步动作", "来源"],
               [7, 12, 9, 10, 56, 34, 40, 14])
    sorted_risks = sorted(D.get("risks", []), key=lambda z: {"high": 0, "medium": 1, "low": 2}[z["severity"]])
    rows = [[x["id"], x["category"], SEV_TXT.get(x["severity"]), STATUS_TXT[x["status"]],
             x["fact"], x.get("impact", ""), x.get("action", ""), ", ".join(x.get("source_ids") or [])]
            for x in sorted_risks]
    r = write_rows(ws, r + 1, rows, status_col=4, status_keys=[x["status"] for x in sorted_risks],
                   center_cols=(1, 2, 3, 4, 8))
    add_legend(ws, r + 1, 8, "说明：“未核实”状态的风险＝尚未完成检索，不等于无风险；本表不给出任何概率性判断。")
    return ws


def sheet_requests(wb, D):
    ws = wb.create_sheet("08_待索取资料")
    r = title_block(ws, "待补充资料清单（可直接发给对方）",
                    "按“能否独立证明主体”排序：P0 先要，P1 并行，P2 报价后补", 7)
    header_row(ws, r, ["编号", "优先级", "类别", "需要什么（中文）", "English wording", "为什么需要", "来源", "是否已取得"],
               [7, 9, 9, 44, 54, 36, 12, 11])
    rows = [[q["id"], q["priority"], q.get("category", ""), q["zh"], q.get("en", ""), q.get("why", ""),
             ", ".join(q.get("source_ids") or []), ""] for q in D["requests"]]
    r = write_rows(ws, r + 1, rows, center_cols=(1, 2, 3, 7, 8))
    dv = DataValidation(type="list", formula1='"未取得,已索取待回,已收到,已核实"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"H{r - len(rows)}:H{r - 1}")
    for row in range(r - len(rows), r):
        ws.cell(row=row, column=2).font = Font(name=FONT_CN, size=9.5, bold=True,
                                              color="A8321F" if ws.cell(row=row, column=2).value == "P0" else C_INK)
    add_legend(ws, r + 1, 8, "用法：整列复制 English wording 发给对方；收到后在“是否已取得”列更新状态。")
    return ws


def sheet_actions(wb, D):
    ws = wb.create_sheet("09_行动清单")
    r = title_block(ws, "行动清单", "谁在什么时候做什么，产出可验收", 6)
    header_row(ws, r, ["编号", "时点", "动作", "具体细节", "责任人", "优先级", "状态"],
               [7, 10, 30, 66, 20, 9, 9])
    rows = [[a["id"], a.get("phase", ""), a.get("action", ""), a.get("detail", ""), a.get("owner", ""),
             a.get("priority", ""), "未开始" if a.get("status") == "open" else a.get("status", "")]
            for a in D.get("actions", [])]
    r = write_rows(ws, r + 1, rows, center_cols=(1, 2, 6, 7))
    dv = DataValidation(type="list", formula1='"未开始,进行中,已完成,已搁置"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"G{r - len(rows)}:G{r - 1}")
    return ws


def sheet_matrix_wide(wb, D):
    """一行一核验项 × 状态 + 区块的透视式汇总，方便按人分派。"""
    ws = wb.create_sheet("10_状态透视")
    r = title_block(ws, "状态透视（区块 × 状态）", "用于分派：哪个区块还有多少未核实", 7)
    header_row(ws, r, ["区块", "名称", "已核实", "存在疑点", "未核实", "合计", "完成度"])
    r += 1
    for s in C.SECTIONS:
        cnt = D["stats"]["section"].get(s["id"], {})
        total = sum(cnt.values())
        done = cnt.get("verified", 0)
        vals = [s["id"], s["title"], cnt.get("verified", 0), cnt.get("discrepancy", 0), cnt.get("unverified", 0),
                total, round(done / total, 3) if total else 0]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=ci, value=v)
            c.font = Font(name=FONT_CN, size=10)
            c.alignment = CENTER if ci > 2 else WRAP_TOP
            c.border = BORDER
        ws.cell(row=r, column=7).number_format = "0%"
        r += 1
    # 合计
    for ci, v in enumerate(["合计", "", D["stats"]["status"]["verified"], D["stats"]["status"]["discrepancy"],
                            D["stats"]["status"]["unverified"], D["stats"]["checks_total"], ""], 1):
        c = ws.cell(row=r, column=ci, value=v)
        c.font = Font(name=FONT_CN, size=10, bold=True)
        c.fill = PatternFill("solid", fgColor=C_HEAD)
        c.alignment = CENTER if ci > 2 else WRAP_TOP
        c.border = BORDER
    return ws


def sheet_sources(wb, D):
    ws = wb.create_sheet("11_来源库")
    r = title_block(ws, "来源库",
                    "A=官方登记/政府 · B=独立第三方或企业官网一手 · C=媒体/行业名录 · D=对方自述（不作证据）", 8)
    header_row(ws, r, ["编号", "等级", "类型", "名称", "机构", "日期", "检索日", "URL", "说明"],
               [8, 9, 14, 44, 30, 10, 11, 46, 50])
    rows = [[s["id"], GRADE_TXT.get(s["grade"], s["grade"]), s.get("kind", ""), s["name"], s.get("org", ""),
             s.get("date", ""), s.get("retrieved", ""), s.get("url", "") or "（无公开链接）", s.get("note", "")]
            for s in D["sources"]]
    r = write_rows(ws, r + 1, rows, center_cols=(1, 2, 3, 6, 7))
    # URL 超链接
    for row in range(4, 4 + len(rows)):
        c = ws.cell(row=row, column=8)
        if isinstance(c.value, str) and c.value.startswith("http"):
            c.hyperlink = c.value
            c.font = Font(name=FONT_CN, size=9, color="14746A", underline="single")
    return ws


def sheet_messages(wb, D):
    ws = wb.create_sheet("12_英文话术")
    r = title_block(ws, "向对方索取的英文消息草稿", "四段可直接复制的邮件；记得替换 [Your name] 等占位符", 3)
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 88
    for m in D.get("messages", []):
        r += 1
        ws.cell(row=r, column=1, value=m.get("id")).font = Font(name=FONT_CN, size=10, bold=True, color=C_BRAND)
        t = ws.cell(row=r, column=2, value=m.get("title"))
        t.font = Font(name=FONT_CN, size=11, bold=True)
        c = ws.cell(row=r, column=3, value=clean("用途：" + (m.get("purpose") or "")))
        c.font = Font(name=FONT_CN, size=9, color=C_MUTED)
        c.alignment = WRAP_TOP
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        r += 1
        body = m.get("body_en", "")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        c = ws.cell(row=r, column=1, value=clean(body))
        c.font = Font(name="Consolas", size=9.5)
        c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
        c.fill = PatternFill("solid", fgColor="FBFAF7")
        c.border = BORDER
        ws.row_dimensions[r].height = min(420, max(80, 13 * (body.count("\n") + 1)))
        r += 1
        notes = m.get("notes") or []
        if notes:
            ws.cell(row=r, column=2, value="写作要点").font = Font(name=FONT_CN, size=9, bold=True, color=C_MUTED)
            c = ws.cell(row=r, column=3, value=clean("；".join(notes)))
            c.font = Font(name=FONT_CN, size=9, color=C_MUTED)
            c.alignment = WRAP_TOP
            ws.row_dimensions[r].height = 30
            r += 1
    return ws


def sheet_method(wb, D):
    ws = wb.create_sheet("13_方法与边界")
    ws.sheet_view.showGridLines = False
    r = title_block(ws, "方法、口径与使用边界", "这一页是给复核人看的：为什么这样判、什么没做", 2)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 86

    blocks = [
        ("五区块核验框架", [
            "A 身份核验：AHU 登记 + NIB/OSS + NPWP + 海关识别号；名称逐字比对。",
            "B 业务相关性：主营/产品目录/经营活动 vs 询价产品；KBLI 分类对照。",
            "C 联系方式：官网 / 域名 / 企业邮箱 / 地址 / 电话 五项互相校验；SPF/DMARC 只作佐证。",
            "D 公开风险：经营异常、诉讼、制裁名单、负面报道、付款与账户路径。",
            "E 待补充资料：按“能否独立证明主体”排序，形成 P0/P1/P2 清单与英文话术。",
        ]),
        ("证据分级", [
            "A 级：官方登记与政府公示（AHU、OSS、海关、法院、制裁名单）。",
            "B 级：独立第三方或企业官网一手信息（官网 About/Contact、年报、协会会员、认证证书）。",
            "C 级：媒体转载、行业名录、社交平台（印尼语关键词检索）。",
            "D 级：对方自述（邮件、名片、公司介绍 PDF）—— 只能用于提取，不能作为结论。",
        ]),
        ("三条口径纪律", [
            "“未核实” ≠ “虚假”：公开渠道未覆盖是常态；查不到注册资料不能判为假企业。",
            "“存在疑点” = 具体可核对的矛盾（地址口径、规模口径、资料前置条件），不推断主观动机。",
            "同名/近似名企业严格隔离：只有登记号或 NIB 一致才允许合并信息。",
        ]),
        ("本报告不做的事", [
            "不给出任何“诈骗概率”或类似概率性判断。",
            "不以域名注册时间、网站新旧、邮箱后缀单独判断企业真伪。",
            "不替代法律尽调、资信评级、银行保函核查或现场审厂。",
            "不包含价格判断与授标建议。",
        ]),
    ]
    for title, items in blocks:
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        c = ws.cell(row=r, column=1, value=title)
        c.font = Font(name=FONT_CN, size=12, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=C_BRAND)
        c.alignment = Alignment(vertical="center", indent=1)
        ws.row_dimensions[r].height = 22
        r += 1
        for it in items:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
            c = ws.cell(row=r, column=1, value="• " + clean(it))
            c.font = Font(name=FONT_CN, size=10)
            c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
            ws.row_dimensions[r].height = max(18, 14 * (len(it) // 90 + 1))
            r += 1

    r += 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    c = ws.cell(row=r, column=1, value="免责声明")
    c.font = Font(name=FONT_CN, size=12, bold=True, color=C_INK)
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    c = ws.cell(row=r, column=1, value=clean(D["meta"].get("disclaimer", "")))
    c.font = Font(name=FONT_CN, size=9.5, color=C_MUTED)
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws.row_dimensions[r].height = 70
    return ws


# ------------------------------------------------------------------ 入口

def build(data_path, out_path):
    D = C.normalize(C.load_json(data_path))
    wb = Workbook()
    sheet_cover(wb, D)
    sheet_inquiry(wb, D)
    sheet_extract(wb, D)
    sheet_subject(wb, D)
    sheet_business(wb, D)
    sheet_contact(wb, D)
    sheet_checks(wb, D)
    sheet_risks(wb, D)
    sheet_requests(wb, D)
    sheet_actions(wb, D)
    sheet_matrix_wide(wb, D)
    sheet_sources(wb, D)
    sheet_messages(wb, D)
    sheet_method(wb, D)

    for ws in wb.worksheets:
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_margins.left = ws.page_margins.right = 0.4

    wb.properties.title = D["meta"].get("title", "海外询盘企业核验报告")
    wb.properties.subject = "询盘企业核验 / Inquiry KYC"
    wb.properties.creator = "overseas-inquiry-kyc skill"
    wb.properties.description = D["meta"].get("disclaimer", "")

    C.ensure_dir(os.path.dirname(os.path.abspath(out_path)) or ".")
    wb.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="生成 Excel 核验工作簿")
    ap.add_argument("data")
    ap.add_argument("out")
    a = ap.parse_args()
    p = build(a.data, a.out)
    print(f"[ok] XLSX  {p}  {os.path.getsize(p) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
