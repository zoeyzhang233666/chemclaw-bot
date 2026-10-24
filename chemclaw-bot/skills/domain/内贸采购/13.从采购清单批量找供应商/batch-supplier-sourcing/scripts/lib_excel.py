# -*- coding: utf-8 -*-
"""构建 Excel 报告：12 个工作表。"""
from __future__ import annotations

import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from lib_common import shanghai_now

INK = "1F2A37"
ACCENT = "0F766E"
WARN = "B45309"
DANGER = "B91C1C"
MUTED = "6B7280"
HEAD_FILL = "0F766E"
HEAD_FONT = "FFFFFF"

FILL = {
    "head": PatternFill("solid", fgColor=HEAD_FILL),
    "sim": PatternFill("solid", fgColor="FEF3C7"),
    "soft": PatternFill("solid", fgColor="E6F4F1"),
    "ok": PatternFill("solid", fgColor="D1FAE5"),
    "warn": PatternFill("solid", fgColor="FEF3C7"),
    "bad": PatternFill("solid", fgColor="FEE2E2"),
    "none": PatternFill("solid", fgColor="F3F4F6"),
    "direct": PatternFill("solid", fgColor="059669"),
    "partial": PatternFill("solid", fgColor="A3E635"),
    "disclose": PatternFill("solid", fgColor="FDE68A"),
    "dist": PatternFill("solid", fgColor="FBCFE8"),
    "partial_spec": PatternFill("solid", fgColor="A3E635"),
    "dist_only": PatternFill("solid", fgColor="FBCFE8"),
    "not_listed": PatternFill("solid", fgColor="E5E7EB"),
}
THIN = Side(style="thin", color="D1D5DB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _w(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _title(ws, row, text, sub=None, span=8):
    ws.cell(row=row, column=1, value=text).font = Font(size=15, bold=True, color=INK)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    ws.row_dimensions[row].height = 26
    if sub:
        c = ws.cell(row=row + 1, column=1, value=sub)
        c.font = Font(size=9, color=MUTED)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=row + 1, start_column=1, end_row=row + 1, end_column=span)
        ws.row_dimensions[row + 1].height = 30
    return row + (2 if sub else 1)


def _head(ws, row, cols):
    for i, name in enumerate(cols, start=1):
        c = ws.cell(row=row, column=i, value=name)
        c.font = Font(bold=True, color=HEAD_FONT, size=9.5)
        c.fill = FILL["head"]
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[row].height = 30
    return row + 1


def _row(ws, row, values, fills=None, wrap_cols=(), bold_cols=()):
    for i, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.border = BORDER
        c.font = Font(size=9, bold=(i in bold_cols))
        c.alignment = Alignment(vertical="top", wrap_text=(i in wrap_cols),
                                horizontal=("left" if isinstance(v, str) else "right"))
        if fills and i - 1 < len(fills) and fills[i - 1]:
            c.fill = FILL[fills[i - 1]]
    return row + 1


def _link_cell(ws, row, col, url, text=None):
    c = ws.cell(row=row, column=col)
    if url:
        c.value = text or url
        c.hyperlink = url
        c.font = Font(size=8.5, color="1D4ED8", underline="single")
    else:
        c.value = text or "（无链接）"
        c.font = Font(size=8.5, color=DANGER)
    c.alignment = Alignment(wrap_text=True, vertical="top")


# ============================================================ 00 封面
def sheet_cover(wb, p, calc):
    ws = wb.active
    ws.title = "00_封面"
    ws.sheet_view.showGridLines = False
    _w(ws, [26, 20, 20, 20, 20, 16, 16, 14])
    ws.merge_cells("A1:H1")
    ws["A1"] = "批量采购清单寻源报告"
    ws["A1"].font = Font(size=24, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=ACCENT)
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 46
    ws.merge_cells("A2:H2")
    ws["A2"] = p["meta"]["title"]
    ws["A2"].font = Font(size=13, bold=True, color=INK)
    ws["A2"].alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[2].height = 28
    ws.merge_cells("A3:H3")
    ws["A3"] = "【模拟采购清单】× 【真实可核验公开企业信息】 · 企业结论均附来源链接与原文引用"
    ws["A3"].font = Font(size=10, color=WARN, bold=True)
    ws["A3"].fill = FILL["sim"]
    ws["A3"].alignment = Alignment(indent=1, vertical="center")

    meta = [("采购方", p["meta"].get("buyer", "")), ("交付地", p["meta"].get("delivery_point", "")),
            ("清单文件", p["list"].get("source_file", "")),
            ("工作表 / 表头行", f"{p['list'].get('sheet','')} / 第 {p['list'].get('header_row','?')} 行"),
            ("数据截止", p["meta"].get("as_of", "")), ("生成时间", shanghai_now().strftime("%Y-%m-%d %H:%M")),
            ("是否接受贸易商", "是" if p["meta"].get("accept_trader") else "否（仅作线索）"),
            ("报告版本", p["meta"].get("version", "v1.0"))]
    r = 5
    for k, v in meta:
        ws.cell(row=r, column=1, value=k).font = Font(size=9, bold=True, color=MUTED)
        c = ws.cell(row=r, column=2, value=v)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        c.font = Font(size=9.5, color=INK)
        c.alignment = Alignment(vertical="center")
        r += 1

    items = p["items"]
    n_man = len([s for s in p["suppliers"] if s["identity"] in ("S", "P")])
    n_adv = sum(1 for x in calc["item_side"].values() if x["degree_adv"] >= 2)
    n_single = sum(1 for x in calc["item_side"].values() if x["degree_adv"] == 1)
    n_zero = sum(1 for x in calc["item_side"].values() if x["degree_adv"] == 0)
    n_multi = len(calc["multi"])
    n_amb = len(p.get("ambiguities", []))
    n_haz = sum(1 for i in items if "第" in (i.get("hazard") or ""))
    cards = [("物料行数", len(items), "含异常行"), ("候选企业", len(p["suppliers"]), f"厂家口径 {n_man}"),
             ("≥2 家厂家可直供", n_adv, "可直接比价"), ("仅 1 家厂家", n_single, "单一来源风险"),
             ("无厂家覆盖", n_zero, "需补检索"), ("跨物料企业", n_multi, "可打包谈判"),
             ("待确认事项", n_amb, "见 02 表"), ("涉危化品物料", n_haz, "见 09 表")]
    r = 14
    for i, (label, val, note) in enumerate(cards):
        col = 1 + (i % 4) * 2
        if i and i % 4 == 0:
            r += 3
        ws.cell(row=r, column=col, value=label).font = Font(size=9, color=MUTED, bold=True)
        ws.merge_cells(start_row=r, start_column=col, end_row=r, end_column=col + 1)
        ws.cell(row=r + 1, column=col, value=val).font = Font(size=22, bold=True, color=ACCENT)
        ws.cell(row=r + 2, column=col, value=note).font = Font(size=8.5, color=MUTED)
        ws.merge_cells(start_row=r + 2, start_column=col, end_row=r + 2, end_column=col + 1)
        for rr in range(r, r + 3):
            for cc in range(col, col + 2):
                ws.cell(row=rr, column=cc).fill = FILL["soft"]

    r += 4
    ws.cell(row=r, column=1, value="结论摘要").font = Font(size=11, bold=True, color=ACCENT)
    r += 1
    for line in p["meta"].get("headline", []):
        c = ws.cell(row=r, column=1, value="• " + line)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        c.font = Font(size=9.5, color=INK)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 34
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="阅读顺序").font = Font(size=11, bold=True, color=ACCENT)
    r += 1
    order = [("01", "物料标准化表", "清单 → 标准名/CAS/浓度/单位，异常行高亮"),
             ("02", "待确认事项", "不可自动识别的歧义，按 P0/P1/P2 排序"),
             ("03", "候选供应商表", "企业身份（厂家/贸易商）、覆盖物料、可靠性"),
             ("04 / 05", "双向匹配矩阵", "物料→企业、企业→物料两个视角"),
             ("06", "多物料覆盖企业", "可一次谈拢多料的厂家与覆盖比"),
             ("07", "稀缺物料与风险", "厂家不足/规格特殊/无覆盖的物料"),
             ("08", "证据明细", "原文引用 + 链接 + 日期 + 等级"),
             ("09", "危险属性与监管", "危险类别、许可要求、储运提示"),
             ("10", "询价与资质核验清单", "可直接派工的 RFQ 与核验动作"),
             ("11 / 12", "来源库与方法", "全部来源 + 字段映射与口径")]
    for code, name, desc in order:
        ws.cell(row=r, column=1, value=f"{code} {name}").font = Font(size=9, bold=True, color=INK)
        c = ws.cell(row=r, column=2, value=desc)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        c.font = Font(size=9, color=MUTED)
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(row=r, column=1, value="重要声明：本表不含报价、联系人、银行账户与统一社会信用代码；企业产能数据均来自公开披露，"
                                      "不代表其愿以何种价格供货。清单为模拟数据，仅用于演示方法。任何“可供应”结论都须经 COA、样品与合同验证。")
    c.font = Font(size=8.5, color=DANGER)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r].height = 42


# ============================================================ 01 物料标准化表
def sheet_items(wb, p, calc):
    ws = wb.create_sheet("01_物料标准化表")
    ws.sheet_view.showGridLines = False
    _w(ws, [7, 20, 12, 12, 12, 14, 8, 9, 7, 9, 7, 10, 24, 14, 30, 8, 8, 40])
    r = _title(ws, 1, "01 物料标准化表",
               "清单每行 → 标准名 + CAS + 形态/浓度 + 数量单位 + 状态。状态非“正常”的行必须先解决（见 02 表），不进入比价。", 18)
    cols = ["物料码", "清单原始品名", "标准名称", "英文名", "CAS", "形态/规格", "纯度%", "数量", "单位",
            "年用量", "行号", "状态", "危险属性", "包装", "技术要求（清单原文）", "候选数", "厂家数", "备注/问题"]
    r = _head(ws, r, cols)
    st = {"ok": ("ok", "正常"), "ambiguous": ("warn", "歧义"), "conflict": ("bad", "CAS冲突"),
          "unrecognized": ("bad", "未识别"), "blocked": ("bad", "阻塞")}
    r0 = r
    for it in p["items"]:
        x = calc["item_side"].get(it["code"], {})
        f = st.get(it.get("status", "ok"), ("ok", it.get("status", "")))
        vals = [it["code"], it.get("raw_name", ""), it.get("name", ""), it.get("en", ""), it.get("cas", ""),
                it.get("form", ""), it.get("purity"), it.get("qty"), it.get("unit", ""), it.get("qty_annual"),
                it.get("source_row"), f[1], it.get("hazard", ""), it.get("packing", ""), it.get("spec", ""),
                x.get("candidate_count", 0), x.get("degree_adv", 0),
                "；".join(it.get("issues", [])) or it.get("notes", "")]
        fills = [None] * 18
        fills[11] = f[0]
        d = x.get("degree_adv", 0)
        fills[16] = "bad" if d == 0 else ("warn" if d == 1 else "ok")
        r = _row(ws, r, vals, fills=fills, wrap_cols=(2, 3, 13, 15, 18), bold_cols=(1,))
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A{r0 - 1}:R{r - 1}"


# ============================================================ 02 待确认事项
def sheet_ambiguities(wb, p, calc):
    ws = wb.create_sheet("02_待确认事项")
    ws.sheet_view.showGridLines = False
    _w(ws, [8, 8, 7, 18, 12, 12, 52, 44, 10, 10, 20])
    r = _title(ws, 1, "02 待确认事项（不猜测，只提问）",
               "P0=阻塞（缺此信息无法寻源/比价）；P1=影响规格或价格；P2=不影响寻源但需归档。每条写明“问谁、问什么、为什么问、多久要回”。", 11)
    cols = ["编号", "优先级", "物料码", "清单原品名", "问题类型", "标准名（暂定）", "需要确认的问题",
            "判断依据 / 为什么必须问", "负责人", "状态", "建议回复时限"]
    r = _head(ws, r, cols)
    tmap = {"ambiguous": "名称多义", "conflict": "CAS 冲突", "unrecognized": "无法识别",
            "blocked": "数量/单位阻塞", "ok": "信息补全"}
    for a in sorted(p.get("ambiguities", []),
                    key=lambda x: ({"P0": 0, "P1": 1, "P2": 2}.get(x.get("level"), 3), x.get("id", ""))):
        it = next((i for i in p["items"] if i["code"] == a.get("code")), {})
        q = a.get("question", "")
        extra = a.get("extra") or []
        if extra:
            q = q + "\n" + "\n".join("· " + e for e in extra)
        vals = [a.get("id"), a.get("level"), a.get("code", ""), a.get("row", ""), tmap.get(a.get("type"), ""),
                it.get("name", ""), q, a.get("detail", ""), a.get("owner", "采购方"),
                a.get("status", "待确认"), "P0:1 工作日 / P1:3 工作日 / P2:5 工作日"]
        fills = [None] * 11
        fills[1] = "bad" if a.get("level") == "P0" else ("warn" if a.get("level") == "P1" else "none")
        r = _row(ws, r, vals, fills=fills, wrap_cols=(4, 7, 8), bold_cols=(2,))
    ws.freeze_panes = "D5"


# ============================================================ 03 候选供应商表
def sheet_suppliers(wb, p, calc):
    ws = wb.create_sheet("03_候选供应商表")
    ws.sheet_view.showGridLines = False
    _w(ws, [6, 32, 14, 9, 7, 42, 8, 8, 8, 8, 8, 8, 9, 26, 34])
    r = _title(ws, 1, "03 候选供应商表（严格区分厂家与贸易商）",
               "身份 S/P=生产型厂家；G=集团内生产主体；T=贸易商；U=未证实。★可靠性 = 覆盖度分 × 身份权重，只用于排序，不等于商务评分。", 15)
    cols = ["编号", "企业名称", "简称", "身份", "省份", "身份判定依据", "覆盖", "厂家", "可达", "厂家可达",
            "部分规", "贸易商", "★可靠性", "角色/装置", "备注与风险"]
    r = _head(ws, r, cols)
    idn = {"S": "生产厂家", "P": "生产厂家", "G": "集团内生产", "T": "贸易商", "I": "集成商", "U": "未证实"}
    for i, row in enumerate(calc["supplier_rank"], start=1):
        s = next(x for x in p["suppliers"] if x["id"] == row["supplier_id"])
        vals = [f"S{i:02d}", s["name"], s["short"], idn.get(s["identity"], ""), s.get("province", ""),
                s.get("identity_note", ""), row["current"], row["adv_current"], row["achievable"],
                row.get("adv_achievable", 0), row["partial_current"], row["trader_current"],
                row["avg_reliability"] if row["avg_reliability"] is not None else "—",
                "、".join(s.get("roles", [])), s.get("notes", "")]
        fills = [None] * 15
        fills[3] = "ok" if s["identity"] in ("S", "P", "G") else ("warn" if s["identity"] == "T" else "none")
        fills[6] = "ok" if row["current"] >= 2 else ("warn" if row["current"] == 1 else "bad")
        r = _row(ws, r, vals, fills=fills, wrap_cols=(2, 6, 14, 15), bold_cols=(2,))
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:O{r - 1}"


# ============================================================ 04 物料→供应商矩阵
def sheet_matrix_item(wb, p, calc):
    ws = wb.create_sheet("04_物料→供应商矩阵")
    ws.sheet_view.showGridLines = False
    sups = [x["supplier_id"] for x in calc["supplier_rank"]]
    short = {s["id"]: s["short"] for s in p["suppliers"]}
    _w(ws, [7, 22] + [10] * len(sups) + [7, 7, 22])
    r = _title(ws, 1, "04 物料 → 供应商 矩阵",
                "● 已证实可直供 ｜ ◐ 规格/形态待确认 ｜ ○ 有披露待核实 ｜ ◆ 仅贸易分销 ｜ ✕ 明确不做 ｜ 空白 未评估。每格的依据都在 08 表。", 4 + len(sups))
    cols = ["物料码", "物料"] + [short[s] for s in sups] + ["候选", "厂家", "风险判定"]
    r = _head(ws, r, cols)
    colmap = {}
    for i, s in enumerate(sups, start=3):
        c = ws.cell(row=r - 1, column=i)
        c.alignment = Alignment(text_rotation=90, horizontal="center", vertical="bottom")
        colmap[s] = i
    ws.row_dimensions[r - 1].height = 52
    sym = {"direct": "●", "partial_spec": "◐", "disclose": "○", "dist_only": "◆", "not_listed": "✕"}
    for it in p["items"]:
        x = calc["item_side"][it["code"]]
        vals = [it["code"], it["name"] + (("·" + it["form"]) if it.get("form") else "")] + [""] * len(sups)
        vals += [x["candidate_count"], x["degree_adv"], x["gap_label"]]
        r = _row(ws, r, vals, wrap_cols=(2,), bold_cols=(1,))
        for ln in p["links"]:
            if ln["item_code"] != it["code"] or not ln.get("_deg"):
                continue
            key = ln["coverage"] if ln["_deg"]["achievable"] else "not_listed"
            col = colmap.get(ln["supplier_id"])
            if not col:
                continue
            c = ws.cell(row=r - 1, column=col, value=sym.get(key, ""))
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = Font(size=11, bold=True, color="FFFFFF" if key == "direct" else INK)
            c.fill = FILL.get(key, FILL["none"])
    lr = r + 1
    ws.cell(row=lr, column=1, value="图例").font = Font(size=9, bold=True, color=MUTED)
    for j, (k, label) in enumerate([("direct", "● 已证实可直供"), ("partial_spec", "◐ 规格待确认"),
                                    ("disclose", "○ 有披露待核"), ("dist_only", "◆ 仅贸易分销"),
                                    ("not_listed", "✕ 明确不做")]):
        c = ws.cell(row=lr, column=2 + j, value=label)
        c.font = Font(size=8.5)
        c.fill = FILL[k]
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.freeze_panes = "C5"


# ============================================================ 05 供应商→物料矩阵
def sheet_matrix_supplier(wb, p, calc):
    ws = wb.create_sheet("05_供应商→物料矩阵")
    ws.sheet_view.showGridLines = False
    items = p["items"]
    _w(ws, [5, 30, 9] + [7] * len(items) + [8, 8, 8])
    r = _title(ws, 1, "05 供应商 → 物料 矩阵（同一张表的转置视角）",
               "行=企业，列=物料。回答“这家能不能一次谈下全部需求”。", 4 + len(items))
    cols = ["#", "企业", "身份"] + [i["code"] for i in items] + ["当前覆盖", "可达覆盖", "覆盖比"]
    r = _head(ws, r, cols)
    for i, it in enumerate(items, start=4):
        c = ws.cell(row=r - 1, column=i)
        c.value = it["code"]
        c.alignment = Alignment(text_rotation=90, horizontal="center", vertical="bottom")
    ws.row_dimensions[r - 1].height = 44
    sym = {"direct": "●", "partial_spec": "◐", "disclose": "○", "dist_only": "◆", "not_listed": "✕"}
    idn = {"S": "厂家", "P": "厂家", "G": "集团", "T": "贸易商", "I": "集成商", "U": "未证实"}
    for n, row in enumerate(calc["supplier_rank"], start=1):
        s = next(x for x in p["suppliers"] if x["id"] == row["supplier_id"])
        vals = [n, s["name"], idn.get(s["identity"], "")] + [""] * len(items)
        vals += [row["current"], row["achievable"], f"{row['coverage_ratio']:.0f}%"]
        r = _row(ws, r, vals, wrap_cols=(2,))
        for ln in p["links"]:
            if ln["supplier_id"] != s["id"] or not ln.get("_deg"):
                continue
            idx = next((k for k, it in enumerate(items) if it["code"] == ln["item_code"]), None)
            if idx is None:
                continue
            key = ln["coverage"] if ln["_deg"]["achievable"] else "not_listed"
            c = ws.cell(row=r - 1, column=4 + idx, value=sym.get(key, ""))
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = Font(size=11, bold=True, color="FFFFFF" if key == "direct" else INK)
            c.fill = FILL.get(key, FILL["none"])
    ws.freeze_panes = "D5"


# ============================================================ 06 多物料覆盖
def sheet_multi(wb, p, calc):
    ws = wb.create_sheet("06_多物料覆盖企业")
    ws.sheet_view.showGridLines = False
    _w(ws, [5, 26, 9, 8, 8, 8, 44, 44, 32])
    r = _title(ws, 1, "06 可同时供应多种物料的企业（打包谈判对象）",
               "覆盖 ≥2 个清单物料即列为跨品种候选。同一物料的不同浓度/形态行按不同物料计（生产线、包装、许可可能不同）。", 9)
    cols = ["#", "企业", "身份", "当前覆盖", "可达覆盖", "覆盖比", "已证实覆盖的物料", "可达的物料（含待确认）", "谈判要点"]
    r = _head(ws, r, cols)
    lbl = {i["code"]: f"{i['code']} {i['name']}{('·' + i['form']) if i.get('form') else ''}" for i in p["items"]}
    idn = {"S": "厂家", "P": "厂家", "G": "集团", "T": "贸易商", "I": "集成商", "U": "未证实"}
    for n, m in enumerate(calc["multi"], start=1):
        cur = "、".join(lbl.get(c, c) for c in m["covered_items"])
        ach = "、".join(lbl.get(c, c) for c in m["achievable_items"])
        tip = ("多料同框询价，争取合并发运与阶梯量价；" if m["current_count"] >= 2 else "")
        tip += "不同物料可能分属不同生产装置/子公司，签约主体须逐一确认。"
        vals = [n, m["name"], idn.get(m["identity"], ""), m["current_count"], m["achievable_count"],
                f"{m['coverage_ratio']:.1f}%", cur, ach, tip]
        r = _row(ws, r, vals, fills=[None] * 6 + ["ok", None, None], wrap_cols=(2, 7, 8, 9), bold_cols=(2,))
    ws.freeze_panes = "C5"


# ============================================================ 07 稀缺物料
def sheet_scarce(wb, p, calc):
    ws = wb.create_sheet("07_稀缺物料与风险")
    ws.sheet_view.showGridLines = False
    _w(ws, [7, 22, 8, 8, 8, 8, 10, 18, 46])
    r = _title(ws, 1, "07 稀缺物料 / 特殊规格 / 风险物料",
               "按厂家数升序。注意：“无厂家覆盖”= 本报告本轮没查出可核验厂家，不等于市场上没有该产品。", 9)
    cols = ["物料码", "物料", "候选", "厂家", "可达", "贸易商", "等级", "风险类型", "已掌握的可达企业（含待确认）"]
    r = _head(ws, r, cols)
    order = {"无厂家覆盖": 0, "厂家单一/不足": 1, "规格或证据不足": 2}
    for x in sorted(calc["scarce"], key=lambda y: (order.get(y["gap_label"], 9), y["degree_adv"])):
        it = next((i for i in p["items"] if i["code"] == x["item_code"]), {})
        names = "、".join(x.get("adv_achievable_names", [])) or "—"
        r = _row(ws, r, [x["item_code"], it.get("name", "") + (("·" + it["form"]) if it.get("form") else ""),
                         x["candidate_count"], x["degree_adv"], x["degree_adv_achievable"], x["trader_degree"],
                         x.get("severity", ""), x["gap_label"], names],
                 fills=[None, None, None, ("bad" if x["degree_adv"] == 0 else ("warn" if x["degree_adv"] == 1 else "ok")),
                        None, None, None, None, None],
                 wrap_cols=(2, 9), bold_cols=(1,))
    ws.freeze_panes = "C5"


# ============================================================ 08 证据明细
def sheet_evidence(wb, p, calc):
    ws = wb.create_sheet("08_证据明细")
    ws.sheet_view.showGridLines = False
    _w(ws, [10, 6, 18, 30, 34, 62, 44, 40, 11, 16])
    r = _title(ws, 1, "08 证据明细（逐条可回溯）",
               "A=第三方权威/许可批文；a=企业法定披露原件；B=官方或交易所；C=媒体/第三方；D=无链接自述；E=推断。quote 为原文摘录，不改写原意。", 10)
    cols = ["证据ID", "等级", "评级含义", "来源机构", "文件/页面主题", "原文引用", "对结论的作用", "链接", "日期", "关联物料"]
    r = _head(ws, r, cols)
    g = {"A": "权威库/许可", "a": "法定披露原件", "B": "官方/交易所", "C": "媒体/第三方", "D": "无链接自述", "E": "推断"}
    for ev in p["evidence"]:
        vals = [ev["id"], ev["grade"], g.get(ev["grade"], ""), ev.get("org", ""), ev.get("topic", ""),
                ev.get("quote", ""), ev.get("detail", ""), "", ev.get("date", ""),
                "、".join(ev.get("items", [])) or "（企业级）"]
        r = _row(ws, r, vals,
                 fills=[None, ("ok" if ev["grade"] in "Aa" else ("warn" if ev["grade"] in "BC" else "none"))] + [None] * 8,
                 wrap_cols=(5, 6, 7), bold_cols=(2,))
        _link_cell(ws, r - 1, 8, ev.get("url", ""))
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:J{r - 1}"


# ============================================================ 09 危险属性
def sheet_hazard(wb, p, calc):
    ws = wb.create_sheet("09_危险属性与监管")
    ws.sheet_view.showGridLines = False
    _w(ws, [7, 22, 12, 26, 14, 34, 20, 40])
    r = _title(ws, 1, "09 危险属性与特殊监管要求",
               "危险类别取标准化字典（GB 12268 口径），清单原文单列保留。剧毒/易制爆/易制毒等管制需按现行名录逐条核对，本表只提示方向。", 8)
    cols = ["物料码", "物料", "CAS", "危险属性（字典口径）", "清单写法", "许可/资质要求", "包装与储存", "询价必问"]
    r = _head(ws, r, cols)
    for it in p["items"]:
        hz = it.get("hazard") or "（未标注）"
        haz = "第" in hz
        lic = ("危险化学品生产许可证（厂家）/经营许可证（贸易商）；危险货物道路运输资质与押运" if haz
               else "一般工业品，按企业资质与合同条款")
        r = _row(ws, r, [it["code"], it["name"], it.get("cas", ""), hz, it.get("hazard_raw", ""), lic,
                         it.get("packing", "") or "—",
                         ("索取 MSDS(16 节)/COA/危包证/储运温度与保质期" if haz else "索取 MSDS、COA、执行标准")],
                 fills=[None, None, None, ("bad" if haz else "ok"), None, None, None, None],
                 wrap_cols=(4, 6, 8), bold_cols=(1,))


# ============================================================ 10 询价与核验
def sheet_actions(wb, p, calc):
    ws = wb.create_sheet("10_询价与资质核验清单")
    ws.sheet_view.showGridLines = False
    _w(ws, [8, 8, 30, 14, 52, 34, 14, 10])
    r = _title(ws, 1, "10 询价与资质核验清单（可直接派工）",
               "Q 行 = 按供应商打包的询价单；G 行 = 按物料补齐来源的检索/核验任务。", 8)
    cols = ["编号", "优先级", "对象", "类型", "要问的问题 / 要核的材料", "交付物与判定标准", "时限", "状态"]
    r = _head(ws, r, cols)
    for a in p.get("actions", []):
        r = _row(ws, r, [a["id"], a.get("priority", "P1"), a.get("supplier", ""), "询价包 Q",
                         "；".join(a.get("actions", [])) + f"\n涉及物料：{'、'.join(a.get('items', []))}",
                         "回传盖章报价单 + COA + 许可证扫描件", a.get("deadline", ""), "待发出"],
                 fills=[None, "warn", None, None, None, None, None, None], wrap_cols=(3, 5, 6))
    for gp in p.get("gaps", []):
        r = _row(ws, r, [gp["id"], gp.get("severity", "P1"), gp.get("item", ""), f"缺口 {gp.get('type','')}",
                         "；".join(gp.get("actions", [])), "新增可核验厂家 ≥1 家，或书面确认仅有贸易商渠道",
                         "T+10 工作日", "待执行"],
                 fills=[None, ("bad" if gp.get("severity") == "P0" else "warn"), None, None, None, None, None, None],
                 wrap_cols=(3, 5, 6))
    ws.freeze_panes = "C5"


# ============================================================ 11 来源库
def sheet_refs(wb, p, calc):
    ws = wb.create_sheet("11_来源库")
    ws.sheet_view.showGridLines = False
    _w(ws, [10, 6, 30, 44, 11, 54, 46])
    r = _title(ws, 1, "11 来源库（可点击回溯）", "按证据等级降序；D 级（无链接）单独标注，不得单独支撑企业结论。", 7)
    cols = ["证据ID", "等级", "来源机构", "主题", "日期", "链接", "摘录开头"]
    r = _head(ws, r, cols)
    order = {"A": 0, "a": 1, "B": 2, "C": 3, "D": 4, "E": 5}
    for ev in sorted(p["evidence"], key=lambda e: (order.get(e["grade"], 9), e["id"])):
        r = _row(ws, r, [ev["id"], ev["grade"], ev.get("org", ""), ev.get("topic", ""), ev.get("date", ""), "",
                         (ev.get("quote") or "")[:70]], wrap_cols=(4, 7))
        _link_cell(ws, r - 1, 6, ev.get("url", ""))
    ws.freeze_panes = "C5"


# ============================================================ 12 方法与字段映射
def sheet_method(wb, p, calc):
    ws = wb.create_sheet("12_方法与字段映射")
    ws.sheet_view.showGridLines = False
    _w(ws, [22, 54, 62])
    r = _title(ws, 1, "12 方法与字段映射", "这一页让别人能复算：字段怎么映射、单位怎么折算、覆盖度怎么打分、可靠性怎么排序。", 3)
    r = _head(ws, r, ["项目", "取值", "说明"])
    rows = [
        ("清单文件", p["list"].get("source_file", ""), "PDF/图片需先转表并人工核对表头"),
        ("工作表 / 表头行", f"{p['list'].get('sheet','')} / 第 {p['list'].get('header_row','?')} 行",
         "自动检测表头：命中字段别名最多的一行"),
        ("列映射", "；".join(f"{k}→{v}" for k, v in (p.get("_hdr") or {}).items()) or "见 project.json 的 hdr",
         "别名表见 assets/field-map.json"),
        ("单位折算", "t / m³ 为基准；kg→t ×0.001；L→m³ ×0.001；桶/袋/车需给出净重",
         "无法折算的不参与比价，进 02 表"),
        ("CAS 校验", "校验位 = Σ 各位×(位数−位置) mod 10", "校验失败一律 P0，禁止“自动纠正”后静默通过"),
        ("身份分级", "S 生产厂家 / P 部分生产 / G 集团内生产主体 / T 贸易商 / I 综合集成 / U 未证实",
         "只有 S/P/G 计入厂家覆盖；T 单列；U 不进候选池"),
        ("覆盖度分级", "direct 直接可产该品规 / partial_spec 有产品线但规格待确认 / disclose 有披露待核 / dist_only 仅分销 / not_listed 明确不做",
         "direct 需 A/a/B 级证据且品规对得上；推断证据最高给到 partial_spec 或 disclose"),
        ("可靠性排序", "覆盖度分(100/45/40/60/0) × 身份权重(S 1.0 / P 0.6 / G 0.5 / T 0.4 / I 0.5 / U 0.1)",
         "只用于同屏排序，不替代价格/账期/服务评分"),
        ("稀缺判定", "厂家数=0 → 无厂家覆盖；≤2 → 厂家单一；direct<2 → 规格或证据不足",
         "阈值见 assets/rules.json 的 scarcity_thresholds"),
        ("跨品种覆盖比", "企业覆盖的清单物料行数 ÷ 清单总行数", "同一物料不同浓度按不同物料计"),
        ("不做什么", "不静默补 CAS、不把官网罗列当产能、不把贸易商当厂家、不给报价与联系人",
         "目标是可审计的候选池，不是拍脑袋的推荐"),
    ]
    for k, v, note in rows:
        r = _row(ws, r, [k, v, note], wrap_cols=(2, 3), bold_cols=(1,))
    r += 1
    ws.cell(row=r, column=1, value="字段别名全表（对照客户自己的清单表头）").font = Font(bold=True, size=10, color=ACCENT)
    r += 1
    r = _head(ws, r, ["标准字段", "可识别表头写法", "备注"])
    for key, aliases in (calc.get("field_aliases") or {}).items():
        r = _row(ws, r, [key, "、".join(aliases) if isinstance(aliases, list) else str(aliases), ""], wrap_cols=(2,))


def build_excel(project, out_path):
    p = project
    calc = p["_calc"]
    wb = Workbook()
    sheet_cover(wb, p, calc)
    sheet_items(wb, p, calc)
    sheet_ambiguities(wb, p, calc)
    sheet_suppliers(wb, p, calc)
    sheet_matrix_item(wb, p, calc)
    sheet_matrix_supplier(wb, p, calc)
    sheet_multi(wb, p, calc)
    sheet_scarce(wb, p, calc)
    sheet_evidence(wb, p, calc)
    sheet_hazard(wb, p, calc)
    sheet_actions(wb, p, calc)
    sheet_refs(wb, p, calc)
    sheet_method(wb, p, calc)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    return out_path
