# -*- coding: utf-8 -*-
"""build_xlsx.py · 询盘处理工作簿（7 张表）

用法：
    python build_xlsx.py fields.json reply.json -o 询盘处理工作簿.xlsx [--brief 中文简报.md]

表结构：
    00 阅读说明      — 怎么用、模拟声明、不要做什么
    01 询盘概要      — 客户/产品/一页纸结论 + 报价闸门
    02 标准化字段    — 64 字段 × 8 类，缺失/歧义单元格填黄
    03 原始询盘      — 逐行原文（保留原语言）+ 行号，便于引用
    04 缺失与歧义    — 三桶分类 + 影响说明
    05 待确认问题    — 客户可发问句（≤6）+ 内部先确认
    06 英文回复草稿  — Subject + Body + 占位符清单
    07 证据与素材    — 每字段的原文依据（quote/来源/定位）
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except Exception as e:  # pragma: no cover
    sys.stderr.write("需要 openpyxl：%s\n" % e)
    raise

# ---------------- 样式 ----------------
NAVY = "0F3A5F"
BLUE = "1A7FD4"
INK = "16202E"
GREY = "EFEFEF"
AMBER_FILL = PatternFill("solid", fgColor="FFF2CC")
AMBER_INK = "8A5D0D"
RED_FILL = PatternFill("solid", fgColor="FCE4E1")
RED_INK = "B3372F"
VIOLET_FILL = PatternFill("solid", fgColor="EDE9FB")
VIOLET_INK = "5B4BB7"
GREEN_FILL = PatternFill("solid", fgColor="E4F3EA")
GREEN_INK = "1F7A52"
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
BAND_FILL = PatternFill("solid", fgColor="F7F9FC")
THIN = Side(style="thin", color="D8DFE8")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")

STATUS_STYLE = {
    "stated": (GREEN_FILL, GREEN_INK),
    "missing": (RED_FILL, RED_INK),
    "ambiguous": (AMBER_FILL, AMBER_INK),
    "assumed": (VIOLET_FILL, VIOLET_INK),
    "internal": (BAND_FILL, "455368"),
}
BUCKET_CN = {"A": "A 必确认（缺了不能报价）", "B": "B 可假设（须标注待确认）", "C": "C 我方内部定"}


def sheet_title(ws, text, sub="", width=8):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(bold=True, size=15, color="FFFFFF")
    c.fill = HEAD_FILL
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 30
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = Font(size=9.5, italic=True, color="55637A")
        c2.alignment = Alignment(vertical="center", indent=1, wrap_text=True)
        ws.row_dimensions[2].height = 24


def header_row(ws, row, headers, widths=None):
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 26
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def autofit_rows(ws, first_row, last_row, widths, min_h=15, max_h=140):
    for r in range(first_row, last_row + 1):
        lines = 1
        for ci, w in enumerate(widths, start=1):
            v = ws.cell(row=r, column=ci).value
            if not v:
                continue
            est = 0
            for seg in str(v).split("\n"):
                est += max(1, int(len(seg) * (2.0 if _has_cjk(seg) else 1.12) / max(w - 1, 6)) + 1)
            lines = max(lines, est)
        ws.row_dimensions[r].height = min(max(min_h, lines * 14.5), max_h)


def _has_cjk(s):
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


# ---------------- 各表 ----------------
def sheet_readme(wb, meta, fields):
    ws = wb.active
    ws.title = "00 阅读说明"
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "海外询盘处理工作簿 · 阅读说明",
                "overseas-inquiry-triage v%s ｜ 询盘号 %s ｜ 客户 %s ｜ 本文件所有客户信息取自询盘原文，"
                "客户没说的字段一律留空并标『缺失』，不做推测填充" % (C.VERSION, meta.get("inquiry_no", ""),
                                                             meta.get("customer", "")), width=6)
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 30
    ws.column_dimensions["D"].width = 78

    rows = [
        ("模拟声明", "本询盘为教学演示用模拟邮件，非真实客户来函", "warn"),
        ("先看哪张表", "01 询盘概要 → 02 标准化字段 → 05 待确认问题", "info"),
        ("颜色约定", "绿=客户已明确 ｜ 红=客户没提 ｜ 黄=有歧义待确认 ｜ 紫=我方假设 ｜ 灰=我方内部待定", "info"),
        ("不要做什么", "不要补价格、库存、船期、交期、付款条件；不要评分『真实性』或『成交可能性』", "warn"),
        ("报价闸门", "A 类（缺了不能报价）字段全部为『已明确』或『客户已确认』时，才能进入算价场景", "info"),
        ("占位符", "草稿里的 ‹KEY› 必须由对应责任人填实，未填不能发出（scripts/build_md.py --pack 会拦截）", "info"),
        ("下一步", "05 表的问题发客户 ｜ 02 表的字段包交给『算出口报价』｜ 客户公司名交给『核验海外询盘公司』", "info"),
    ]
    r = 4
    for tag, text, kind in rows:
        c = ws.cell(row=r, column=2, value=tag)
        c.font = Font(bold=True, size=10.5)
        c.alignment = TOP
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        t = ws.cell(row=r, column=3, value=text)
        t.alignment = WRAP
        t.font = Font(size=10.5)
        if kind == "warn":
            for col in (2, 3):
                ws.cell(row=r, column=col).fill = AMBER_FILL
            t.font = Font(size=10.5, color=AMBER_INK)
        ws.row_dimensions[r].height = 34 if len(text) < 60 else 48
        r += 1

    r += 1
    counts = C.field_counts(fields)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c = ws.cell(row=r, column=2, value="字段统计")
    c.font = Font(bold=True, size=11.5, color=NAVY)
    r += 1
    for k in ["stated", "missing", "ambiguous", "assumed", "internal"]:
        ws.cell(row=r, column=2, value=C.STATUS_LABEL.get(k, k)).alignment = TOP
        v = ws.cell(row=r, column=3, value=counts.get(k, 0))
        v.alignment = Alignment(horizontal="left", vertical="top")
        v.font = Font(bold=True, size=11)
        fill, ink = STATUS_STYLE[k]
        v.fill = fill
        v.font = Font(bold=True, size=11, color=ink)
        r += 1
    return ws


def sheet_overview(wb, meta, fields, can_quote, blocking, questions):
    ws = wb.create_sheet("01 询盘概要")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "① 询盘概要",
                "一句话结论：%s" % ("A 类字段已齐，可以进入算价环节（价格仍由我方决定）"
                                if can_quote else "A 类还缺 %d 项，本轮只做确认式回复，不报价" % len(blocking)),
                width=4)
    for i, w in enumerate([4, 24, 52, 34], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    def kv(r, k, v, style=None):
        a = ws.cell(row=r, column=2, value=k)
        a.font = Font(bold=True, size=10.5, color="33415A")
        a.alignment = TOP
        a.fill = BAND_FILL
        a.border = BOX
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        b = ws.cell(row=r, column=3, value=v if v not in (None, "") else "—")
        b.alignment = WRAP
        b.border = BOX
        b.font = Font(size=10.5)
        if style:
            fill, ink = style
            b.fill = fill
            b.font = Font(size=10.5, color=ink, bold=True)
        return r + 1

    def g(k):
        f = fields.get(k, {})
        return f.get("value") if f.get("status") == "stated" else ""

    r = 4
    r = kv(r, "询盘编号", meta.get("inquiry_no", ""))
    r = kv(r, "客户名称（原文）", meta.get("customer", ""))
    r = kv(r, "客户国家 / 地区", meta.get("customer_country", ""))
    r = kv(r, "联系人 / 职位", " / ".join([x for x in [g("contact_name"), g("contact_title")] if x]))
    r = kv(r, "邮箱 / 电话", " ｜ ".join([x for x in [g("contact_email"), g("contact_phone"), g("contact_mobile")] if x]))
    r = kv(r, "询盘日期", meta.get("inquiry_date", ""))
    r = kv(r, "邮件主题", meta.get("subject", ""))
    r += 1
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c = ws.cell(row=r, column=2, value="产品与商务")
    c.font = Font(bold=True, size=11.5, color=NAVY)
    r += 1
    r = kv(r, "产品（标准化）", g("product_std") or g("product_raw"))
    r = kv(r, "CAS / HS 候选", " ｜ ".join([x for x in [g("cas"), ("HS: " + g("hs_code")) if g("hs_code") else ""] if x]))
    r = kv(r, "关键规格", "；".join([x for x in [g("spec_purity"), g("spec_impurities"), g("spec_particle")] if x]))
    r = kv(r, "数量", "；".join([x for x in [g("qty_trial"), ("年用量 " + g("qty_annual")) if g("qty_annual") else ""] if x]))
    r = kv(r, "贸易术语 / 目的港", " ｜ ".join([x for x in [((g("incoterm") + " " + g("incoterm_place")).strip()), g("port_dest")] if x]))
    r = kv(r, "付款方式（客户原话）", g("payment"))
    r = kv(r, "包装", g("pack_std") or "客户未指定")
    r = kv(r, "要求的单证", "、".join([n for k, n in (("doc_coa", "COA"), ("doc_sds", "SDS"), ("doc_tds", "TDS"),
                                                    ("doc_coo", "COO"), ("doc_msds", "MSDS"), ("doc_iso", "ISO")) if g(k)]))
    r += 1
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c = ws.cell(row=r, column=2, value="报价闸门")
    c.font = Font(bold=True, size=11.5, color=NAVY)
    r += 1
    r = kv(r, "是否可报价", "可以（价格由我方报价环节填写）" if can_quote else "不可以",
           (GREEN_FILL, GREEN_INK) if can_quote else (RED_FILL, RED_INK))
    r = kv(r, "阻塞字段", "、".join(fields[k].get("label_cn", k) for k in blocking) if blocking else "无")
    r = kv(r, "本轮客户问题数", "%d 条（见 05 表）" % len(questions))
    r += 1
    ws.merge_cells(start_row=r, start_column=2, end_row=r+1, end_column=4)
    c = ws.cell(row=r, column=2, value="⚠ 本表不含任何价格、库存、船期、交期、付款或单证承诺。"
                                      "客户未提及的字段一律标『缺失』，不做推测；不对询盘真实性或成交可能性作任何评估。")
    c.alignment = WRAP
    c.font = Font(size=10, color=AMBER_INK)
    c.fill = AMBER_FILL
    ws.row_dimensions[r].height = 22
    ws.row_dimensions[r+1].height = 22
    return ws


def sheet_fields(wb, fields):
    ws = wb.create_sheet("02 标准化字段")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "② 标准化字段（8 类 · %d 项）" % len(fields),
                "黄色 = 有歧义待客户确认 ｜ 红色 = 客户未提及 ｜ 绿色 = 已明确。"
                "“原文依据”列是唯一可信来源；没有原文依据的就不用填。", width=9)
    widths = [4, 13, 22, 17, 34, 9, 15, 8, 40]
    header_row(ws, 3, ["#", "类别", "字段（中/英）", "状态", "客户给出的值 / 我方假设",
                       "所属桶", "影响报价", "置信度", "原文依据（客户原句）"], widths)
    r = 4
    for i, (k, f) in enumerate(fields.items(), start=1):
        st = f.get("status", "missing")
        if f.get("confirmed_by"):
            st = "stated"
        fill, ink = STATUS_STYLE.get(st, (None, INK))
        cat_cn = dict((c, cn) for c, cn, _ in C.CATEGORIES).get(f.get("cat"), f.get("cat", ""))
        vals = [
            i, cat_cn, "%s\n%s" % (f.get("label_cn", ""), f.get("label_en", "")),
            C.STATUS_LABEL.get(f.get("status", ""), f.get("status", "")),
            f.get("value") or (f.get("assume") and ("（我方假设）" + f["assume"])) or "客户未提及",
            f.get("bucket", ""), "是" if f.get("affects_quote") else "",
            {"high": "高", "medium": "中", "low": "低"}.get(f.get("confidence"), ""),
            f.get("quote", ""),
        ]
        for ci, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=ci, value=v if v != "" else None)
            c.border = BOX
            c.alignment = WRAP
            c.font = Font(size=10)
            if ci == 5:
                c.fill = fill
                c.font = Font(size=10, color=ink, bold=(st in ("missing", "ambiguous")))
            if ci == 4:
                c.font = Font(size=10, color=ink, bold=True)
            if ci == 9:
                c.font = Font(size=9.5, color="4A5A6F", italic=True)
        if f.get("note"):
            ws.cell(row=r, column=9, value=(f.get("quote") or "") + ("\n※ " + f["note"] if f.get("note") else ""))
        # 分类带底色（A/B/C）
        b = ws.cell(row=r, column=6)
        b.alignment = Alignment(horizontal="center", vertical="top")
        b.fill = {"A": PatternFill("solid", fgColor="E6F0FA"), "B": VIOLET_FILL, "C": GREEN_FILL}.get(f.get("bucket"), BAND_FILL)
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=8).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=7).alignment = Alignment(horizontal="center", vertical="top")
        r += 1
    ws.auto_filter.ref = "A3:I%d" % (r - 1)
    ws.freeze_panes = "D4"
    autofit_rows(ws, 4, r - 1, widths)
    return ws


def sheet_source(wb, snippets):
    ws = wb.create_sheet("03 原始询盘")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "③ 原始询盘（逐行保留原语言）",
                "行号与 HTML 审阅板一致，便于口头/书面引用“第 N 行”。不翻译、不改写、不润色客户原文。", width=4)
    widths = [7, 52, 28, 16]
    header_row(ws, 3, ["行号", "原文", "所属素材", "素材日期"], widths)
    r = 4
    for s in snippets:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        hd = ws.cell(row=r, column=1, value="素材 %s ｜ %s ｜ %s" % (s.get("id", ""), s.get("title", ""), s.get("date", "") or ""))
        hd.font = Font(bold=True, size=10, color="FFFFFF")
        hd.fill = PatternFill("solid", fgColor="4A6C8C")
        hd.alignment = Alignment(indent=1, vertical="center")
        ws.row_dimensions[r].height = 20
        r += 1
        for i, ln in enumerate(s.get("lines", []), start=1):
            ws.cell(row=r, column=1, value=i).alignment = Alignment(horizontal="center", vertical="top")
            ws.cell(row=r, column=1).font = Font(size=9, color="9AA6B6")
            c = ws.cell(row=r, column=2, value=ln)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.font = Font(name="Consolas", size=10)
            c2 = ws.cell(row=r, column=3, value=s.get("title", s.get("id", "")))
            c2.font = Font(size=9, color="7B8798")
            c2.alignment = TOP
            c3 = ws.cell(row=r, column=4, value=s.get("date", ""))
            c3.font = Font(size=9, color="7B8798")
            c3.alignment = TOP
            for ci in range(1, 5):
                ws.cell(row=r, column=ci).border = BOX
            r += 1
        # 素材分隔
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        sep = ws.cell(row=r, column=1, value="—— 以上为素材 %s 结束 ——" % s.get("id", ""))
        sep.font = Font(size=9, italic=True, color="9AA6B6")
        sep.alignment = Alignment(horizontal="center")
        r += 1
    return ws


def sheet_gaps(wb, fields):
    ws = wb.create_sheet("04 缺失与歧义")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "④ 缺失与歧义（缺口清单）",
                "三桶：A 缺了不能报价 ｜ B 可带我方假设先准备（邮件必须写明 our assumption、to be confirmed）｜ "
                "C 由我方内部先定，不问客户。", width=8)
    widths = [5, 13, 24, 22, 40, 34, 10, 8]
    header_row(ws, 3, ["#", "桶", "字段（中）", "状态", "客户原话 / 现值", "为什么要问 / 影响", "影响报价", "类别"], widths)
    r = 4
    n = 0
    for k, f in fields.items():
        st = f.get("status")
        if st in ("stated", "internal") and not f.get("confirmed_by"):
            continue
        if f.get("confirmed_by"):
            continue
        n += 1
        fill, ink = STATUS_STYLE.get(st, (None, INK))
        vals = [
            n, BUCKET_CN.get(f.get("bucket"), f.get("bucket", "")), f.get("label_cn", ""),
            C.STATUS_LABEL.get(st, st), f.get("quote") or f.get("value") or "—",
            f.get("note") or ("客户未提及" if st == "missing" else "客户表述不唯一"),
            "是" if f.get("affects_quote") else "", f.get("cat", ""),
        ]
        for ci, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=ci, value=v)
            c.border = BOX
            c.alignment = WRAP
            c.font = Font(size=10)
            if ci == 4:
                c.fill = fill
                c.font = Font(size=10, color=ink, bold=True)
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=8).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=7).alignment = Alignment(horizontal="center", vertical="top")
        r += 1
    if n == 0:
        ws.cell(row=4, column=3, value="没有缺口：A 类字段全部已明确，可进入算价环节。")
    ws.freeze_panes = "C4"
    autofit_rows(ws, 4, r - 1, widths)
    return ws


def sheet_questions(wb, questions, internal):
    ws = wb.create_sheet("05 待确认问题")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "⑤ 待确认问题（可直接复制进邮件）",
                "客户问题按优先级排序，最多 6 条——一次问太多客户不回。灰色区是我方内部要先确认的，不进客户邮件。", width=7)
    widths = [5, 60, 30, 40, 12, 14, 12]
    header_row(ws, 3, ["#", "英文问句（可直接复制）", "对应字段", "为什么问", "优先级", "客户是否已答", "行号依据"], widths)
    r = 4
    for i, q in enumerate(questions, start=1):
        vals = [i, q.get("question_en", ""), q.get("label_cn", ""), q.get("reason_cn", ""),
                "P1" if q.get("priority") == 1 else "P2", "", q.get("anchor", "客户未提及")]
        for ci, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=ci, value=v)
            c.border = BOX
            c.alignment = WRAP
            c.font = Font(size=10)
            if ci == 2:
                c.font = Font(size=10.5, color="123A5C")
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=6).fill = GREEN_FILL
        qc = ws.cell(row=r, column=6, value="☐ 未答")
        qc.alignment = Alignment(horizontal="center", vertical="top")
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    c = ws.cell(row=r, column=1, value="我方内部先确认（不要把这些问题问客户——它们是我们自己的决定或内部信息）")
    c.font = Font(bold=True, size=11, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="7B8798")
    c.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 22
    r += 1
    header_row(ws, r, ["#", "内部事项", "所属字段", "", "", "", ""], None)
    r += 1
    for i, it in enumerate(internal, start=1):
        ws.cell(row=r, column=1, value=i).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=1).border = BOX
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        c = ws.cell(row=r, column=2, value=it.get("label_cn", ""))
        c.alignment = WRAP
        c.font = Font(size=10)
        c.border = BOX
        c6 = ws.cell(row=r, column=6, value=it.get("desc", ""))
        c6.alignment = WRAP
        c6.font = Font(size=9.5, color="55637A")
        c6.border = BOX
        r += 1
    autofit_rows(ws, 4, r - 1, widths)
    return ws


def sheet_reply(wb, reply, fields):
    ws = wb.create_sheet("06 英文回复草稿")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "⑥ 英文回复草稿（%s · %s）" % (reply.get("template", ""), reply.get("tone", "")),
                "占位符 ‹KEY› 由对应责任人填实；未填实不得发出。本稿不含任何价格、库存、船期、交期、付款或单证承诺。", width=5)
    widths = [4, 104, 20, 30, 14]
    ws.column_dimensions["B"].width = 104
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 28
    ws.column_dimensions["E"].width = 14
    r = 4
    ws.cell(row=r, column=2, value="Subject:").font = Font(bold=True, size=11)
    ws.cell(row=r, column=3, value=reply.get("subject", "")).font = Font(size=11)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    r += 2
    for ln in (reply.get("body") or "").split("\n"):
        c = ws.cell(row=r, column=2, value=ln)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(size=10.5)
        if "‹" in ln:
            c.font = Font(size=10.5, color=AMBER_INK, bold=True)
            c.fill = AMBER_FILL
        ws.row_dimensions[r].height = 15 if ln.strip() else 8
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws.cell(row=r, column=1, value="占位符清单（发出一封邮件前必须全部填实）")
    c.font = Font(bold=True, size=11, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=BLUE)
    c.alignment = Alignment(indent=1, vertical="center")
    r += 1
    header_row(ws, r, ["#", "占位符", "含义", "由谁确认", "已填"], None)
    r += 1
    for i, p in enumerate(reply.get("placeholders", []), start=1):
        ws.cell(row=r, column=1, value=i).alignment = Alignment(horizontal="center", vertical="top")
        c2 = ws.cell(row=r, column=2, value="‹%s›" % p.get("key", ""))
        c2.font = Font(name="Consolas", size=10, color=AMBER_INK)
        c2.fill = AMBER_FILL
        ws.cell(row=r, column=3, value=p.get("label_cn", "")).font = Font(size=10)
        ws.cell(row=r, column=4, value=p.get("owner", "")).font = Font(size=10)
        ws.cell(row=r, column=5, value="☐").alignment = Alignment(horizontal="center")
        for ci in range(1, 6):
            ws.cell(row=r, column=ci).border = BOX
            if ci in (2, 3, 4):
                ws.cell(row=r, column=ci).alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    return ws


def sheet_evidence(wb, fields, snippets):
    ws = wb.create_sheet("07 证据与素材")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "⑦ 证据与素材（每个字段的出处）",
                "只有这一列有原句的字段才算“客户已明确”。没有原句 = 客户没说，不能填。", width=7)
    widths = [5, 22, 12, 44, 30, 12, 22]
    header_row(ws, 3, ["#", "字段", "状态", "客户原句（逐字）", "素材", "行号", "说明"], widths)
    r = 4
    n = 0
    for k, f in fields.items():
        if not f.get("quote"):
            continue
        n += 1
        pos = ""
        for s in snippets:
            for i, ln in enumerate(s.get("lines", []), start=1):
                if f["quote"].strip() and f["quote"].strip()[:40].lower() in ln.lower():
                    pos = str(i)
                    break
            if pos:
                break
        vals = [n, f.get("label_cn", ""), C.STATUS_LABEL.get(f.get("status", ""), ""), f.get("quote", ""),
                f.get("source_id", ""), pos, f.get("note", "")]
        for ci, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=ci, value=v)
            c.border = BOX
            c.alignment = WRAP
            c.font = Font(size=10)
            if ci == 4:
                c.font = Font(size=10, italic=True, color="33415A")
        fill, ink = STATUS_STYLE.get(f.get("status", "missing"), (None, INK))
        ws.cell(row=r, column=3).fill = fill
        ws.cell(row=r, column=3).font = Font(size=10, bold=True, color=ink)
        r += 1
    autofit_rows(ws, 4, r - 1, widths)
    return ws


def main():
    ap = argparse.ArgumentParser(description="生成询盘处理工作簿")
    ap.add_argument("fields")
    ap.add_argument("reply", nargs="?", default="")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    doc = C.load_json_stable(args.fields)
    reply = C.load_json(args.reply) if args.reply else {}
    meta = doc.get("meta", {})
    fields = doc.get("fields", {})
    snippets = doc.get("snippets", [])
    questions = doc.get("questions", [])
    internal = doc.get("internal_confirm", [])
    ok, blocking = C.can_quote(fields)

    wb = Workbook()
    sheet_readme(wb, meta, fields)
    sheet_overview(wb, meta, fields, ok, blocking, questions)
    sheet_fields(wb, fields)
    sheet_source(wb, snippets)
    sheet_gaps(wb, fields)
    sheet_questions(wb, questions, internal)
    if reply:
        sheet_reply(wb, reply, fields)
    sheet_evidence(wb, fields, snippets)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    wb.save(args.out)
    print("[ok] %s （%d 张表）" % (args.out, len(wb.sheetnames)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
