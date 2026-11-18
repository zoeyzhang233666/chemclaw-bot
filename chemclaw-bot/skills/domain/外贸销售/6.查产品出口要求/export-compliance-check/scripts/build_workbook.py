# -*- coding: utf-8 -*-
"""build_workbook.py — 由 case.json 生成出口合规准备 Excel 工作簿（15 个工作表）

用法
----
python build_workbook.py <case.json> [--out 工作簿.xlsx]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# ---------------- 样式 ----------------
NAVY = "1F3864"
BLUE = "2E5C8A"
LIGHT = "EAF1F8"
ZEBRA = "F6F9FC"
GREY = "6B7280"

STATUS_FILL = {
    "已核实": ("E6F4EA", "1E7B34"),
    "待确认": ("FFF1E0", "B45309"),
    "参考信息": ("E8EFFB", "1D4ED8"),
    "不适用": ("F1F3F5", "6B7280"),
    "不触发": ("E6F4EA", "1E7B34"),
    "待取得": ("FFF1E0", "B45309"),
    "待准备": ("FFF1E0", "B45309"),
    "待确认是否办理": ("FFF1E0", "B45309"),
}

THIN = Side(style="thin", color="D5DCE4")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _font(size=10, bold=False, color="1B1B1B", name="微软雅黑"):
    return Font(name=name, size=size, bold=bold, color=color)


def title_block(ws, title, subtitle, width, extra=None):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    c = ws.cell(row=1, column=1, value=title)
    c.font = _font(15, True, "FFFFFF")
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
    c = ws.cell(row=2, column=1, value=subtitle)
    c.font = _font(9, False, "FFFFFF")
    c.fill = PatternFill("solid", fgColor=BLUE)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 22

    r = 3
    if extra:
        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=width)
        c = ws.cell(row=3, column=1, value=extra)
        c.font = _font(9, False, "8A5300")
        c.fill = PatternFill("solid", fgColor="FFF8E1")
        c.alignment = Alignment(vertical="center", horizontal="left", indent=1, wrap_text=True)
        ws.row_dimensions[3].height = 30
        r = 4
    return r + 1  # 表头所在行


def header_row(ws, row, headers, widths):
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = _font(10, True, "FFFFFF")
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 30
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def body_rows(ws, start_row, rows, wraps=(), status_col=None, heights=22):
    for r_i, rowvals in enumerate(rows):
        r = start_row + r_i
        for c_i, v in enumerate(rowvals, start=1):
            c = ws.cell(row=r, column=c_i, value=v)
            c.font = _font(9)
            c.alignment = Alignment(vertical="top", wrap_text=(c_i in wraps), horizontal="left")
            c.border = BORDER
            if r_i % 2 == 1:
                c.fill = PatternFill("solid", fgColor=ZEBRA)
        if status_col and len(rowvals) >= status_col:
            st = str(rowvals[status_col - 1])
            for key, (bg, fg) in STATUS_FILL.items():
                if st == key or (key in st and key in ("待确认", "待取得", "参考信息", "不适用", "不触发")):
                    cell = ws.cell(row=r, column=status_col)
                    cell.fill = PatternFill("solid", fgColor=bg)
                    cell.font = _font(9, True, fg)
                    break
        ws.row_dimensions[r].height = heights


def add_filter_and_finish(ws, header_row_no, last_row, last_col):
    ws.auto_filter.ref = f"A{header_row_no}:{get_column_letter(last_col)}{max(last_row, header_row_no)}"
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{header_row_no}:{header_row_no}"
    ws.oddFooter.center.text = "export-compliance-check | 合规准备清单，不构成法律意见 | &A - &P/&N"
    ws.oddFooter.center.size = 8


# ---------------- 各表 ----------------
def sheet_cover(wb, case, chk):
    ws = wb.active
    ws.title = "00_封面与说明"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 110
    meta = case["meta"]
    p = case["inputs"]["product"]

    ws.merge_cells("A1:B1")
    c = ws["A1"]
    c.value = "出口合规准备清单 · " + meta["title"]
    c.font = _font(17, True, "FFFFFF")
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 44

    s = chk["by_topic"]
    tot = sum(v["total"] for v in s.values())
    ver = sum(v["已核实"] for v in s.values())
    tbc = sum(v["待确认"] for v in s.values())
    rows = [
        ("案例编号", meta["case_id"]),
        ("交付基准日", f"{meta['prepared_on']}（本工作簿所有「核验日期」均以此为基准）"),
        ("产品", f"{p['name_cn']} / {p['name_en']}"),
        ("CAS / 浓度", f"{p['cas']} / {p['concentration']}"),
        ("用途", p["use"]),
        ("包装 / 数量", f"{p['packaging']}；{p['quantity']}"),
        ("航线", f"{p['origin']} → {p['destination']}（{p['transport_mode']}；{p['incoterm']}）"),
        ("", ""),
        ("核对条目总数", f"{tot} 条（{len(s)} 个主题）"),
        ("已核实", f"{ver} 条 —— 有官方来源、已按现行版本核对"),
        ("待确认 / 参考", f"{tbc} 条 + {tot - ver - tbc} 条参考 —— 不得据以下最终结论"),
        ("法规来源", f"{len(case['regs'])} 条，全部登记来源 URL 与核验日期"),
        ("待确认事项", f"{len(case['open_questions'])} 项，见「13_待确认事项」"),
        ("", ""),
        ("重要提示 1", "危险化学品管理属性 ≠ 危险货物运输分类。本工作簿在第 5、6 表中分别判定，不互相推导。"),
        ("重要提示 2", "本清单为出口准备工具，不构成法律意见，不替代报关行、货代、DG 安全顾问与专业律师的正式判定。"),
        ("重要提示 3", "凡标注「待确认」的结论，在取得官方原文或专业机构书面意见前不得对客户承诺或据此订舱。"),
    ]
    r = 3
    for k, v in rows:
        a = ws.cell(row=r, column=1, value=k)
        a.font = _font(9, True, GREY)
        a.alignment = Alignment(vertical="center", indent=1)
        b = ws.cell(row=r, column=2, value=v)
        b.font = _font(10, k.startswith("重要提示"), "B45309" if k.startswith("重要提示") else "1B1B1B")
        b.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        if k.startswith("重要提示"):
            for col in (1, 2):
                ws.cell(row=r, column=col).fill = PatternFill("solid", fgColor="FFF8E1")
        ws.row_dimensions[r].height = 26 if k.startswith("重要提示") else 20
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="工作表导航").font = _font(11, True, NAVY)
    r += 1
    for name, desc in SHEET_NAV:
        ws.cell(row=r, column=1, value=name).font = _font(9, True, BLUE)
        ws.cell(row=r, column=2, value=desc).font = _font(9)
        ws.cell(row=r, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        r += 1


SHEET_NAV = [
    ("01_产品身份", "CAS/EC、浓度、组成、稳定剂判定、身份核验结论"),
    ("02_HS候选", "HS 编码候选（中国 10 位 / 越南 8 位）、归类依据、置信度"),
    ("03_中国出口", "危化品目录、易制爆、定向易制毒、CCL、检验、报关监管条件、退税"),
    ("04_目的国进口", "越南 2026 新规体系、清关前申报、附录归属、资质、标签/SDS、关税"),
    ("05_运输危险属性", "UN 号、类别、PG、EmS、P504/IBC02、限量/例外数量（三方式）"),
    ("06_标签与包装", "GHS 危险性分类、危险货物标签、双语标签、包装相容性"),
    ("07_单证清单", "合同/发票/装箱单/运输单证/产地证/许可文件，含责任人与时点"),
    ("08_角色分工", "出口方、进口方、承运方、报关行、第三方 各自的准备事项"),
    ("09_法规索引", "全部法规来源、发布机构、生效日、状态、核验日期、URL"),
    ("10_时效性核查", "本轮换版/改版事项与影响（含越南化学品法整体换版）"),
    ("11_核验状态汇总", "按主题统计已核实/待确认/参考，作为交付前的转状态口径"),
    ("12_风险与常见误区", "容易误判的适用条件与应对"),
    ("13_待确认事项", "问题、原因、责任方、阻断条目、闭环条件"),
    ("14_核对清单", "可勾选的执行清单（打印用）"),
    ("15_填写样例", "如何把新案例填进 case.json 的最小示例"),
]


def sheet_identity(wb, case):
    ws = wb.create_sheet("01_产品身份")
    p = case["inputs"]["product"]
    rows = [
        ("产品中文名", p["name_cn"], "客户合同/COA 口径"),
        ("产品英文名", p["name_en"], "运输单证与 SDS 英文名"),
        ("CAS 号", p["cas"], "危险化学品目录 903 条目 / BAM 条目"),
        ("EC 号", p["ec"], "BAM DGG-Info"),
        ("UN-CAS 索引号", p["un_cas_index"], "BAM DGG-Info"),
        ("分子式", p["formula"], "—"),
        ("等级 / 浓度", f"{p['grade']} / {p['concentration']}", "以 COA 实测值确认"),
        ("组成", p["composition"], "稳定剂须如实列明"),
        ("用途", p["use"], "决定准入路径（食品用途会触发另一套要求）"),
        ("包装 / 数量", f"{p['packaging']}；{p['quantity']}", "决定危险货物包装指令"),
        ("出口国 → 目的国", f"{p['origin']} → {p['destination']}", "决定定向许可证与目的国法规版本"),
        ("运输方式", p["transport_mode"], "决定适用 IMDG / IATA / ADR"),
    ]
    h = title_block(ws, "01 · 产品身份核验", "先锁定身份与适用条件，再谈监管；任何字段不确定都不要进入后续判定", 3,
                    extra=case["identity"]["verdict"])
    header_row(ws, h, ["字段", "取值", "来源 / 口径"], [22, 58, 52])
    body_rows(ws, h + 1, rows, wraps=(2, 3))
    r = h + 1 + len(rows) + 2

    ws.cell(row=r, column=1, value="逐项核验").font = _font(12, True, NAVY)
    r += 1
    header_row(ws, r, ["核验项", "结论", "依据", "状态"], [22, 58, 52, 14])
    ws.freeze_panes = ws.cell(row=r + 1, column=1)
    data = [(x["item"], x["value"], x["source"], x["status"]) for x in case["identity"]["checks"]]
    body_rows(ws, r + 1, data, wraps=(2, 3), status_col=4)


def sheet_hs(wb, case):
    ws = wb.create_sheet("02_HS候选")
    h = title_block(ws, "02 · HS 编码候选", "候选不是结论：须由报关行/归类专业确认后方可写入报关单与发票", 8,
                    extra="归类依据以《税则》章注为准；第 28 章章注一(二)(四)是「水溶液+稳定剂」仍归 2847 的关键。")
    header_row(ws, h, ["排序", "中国 10 位", "越南 8 位（参考）", "商品名称", "归类依据", "置信度", "状态 / 适用条件", "备注"],
               [6, 16, 18, 30, 56, 22, 30, 40])
    rows = []
    for x in case["hs_candidates"]:
        rows.append((x["rank"], x["code_cn"], x.get("code_vn", "—"), x["name_cn"], x["basis"],
                     x["confidence"], x["status"], x.get("notes", "")))
    body_rows(ws, h + 1, rows, wraps=(4, 5, 7, 8), heights=64)
    add_filter_and_finish(ws, h, h + len(rows), 8)

    r = h + len(rows) + 3
    ws.cell(row=r, column=1, value="归类自查问题（逐条回答后再确认 HS）").font = _font(11, True, NAVY)
    qs = [
        "产品是否为「过氧化氢的水溶液」？是否只含稳定剂/惰性化学品？",
        "是否使用尿素固化？（影响 2847 品目描述，但仍在 2847）",
        "是否加入稳定剂之外的化学品，使产品改变一般用途？（可能改归 3824）",
        "是否零售包装？（28470000 规范申报「包装」栏须填零售/非零售）",
        "是否用于食品/食品添加剂？（影响 CIQ 分档与越南准入）",
        "目的国 8 位子目是否与中国 10 位对齐（如越南 2847.00.10 液态）？",
    ]
    for i, q in enumerate(qs, start=1):
        ws.cell(row=r + i, column=1, value=f"Q{i}").font = _font(9, True, BLUE)
        ws.merge_cells(start_row=r + i, start_column=2, end_row=r + i, end_column=8)
        c = ws.cell(row=r + i, column=2, value=q)
        c.font = _font(9)
        c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)


def _entry_sheet(wb, name, title, sub, entries, extra=None):
    ws = wb.create_sheet(name)
    h = title_block(ws, title, sub, 7, extra=extra)
    header_row(ws, h, ["编号", "事项", "结论 / 要求", "适用条件", "法规依据", "生效 / 适用时间", "状态"],
               [10, 30, 62, 44, 46, 20, 16])
    rows = [(e["id"], e["item"], e["finding"], e.get("condition", ""), e["reg"], e["effective"], e["status"])
            for e in entries]
    body_rows(ws, h + 1, rows, wraps=(2, 3, 4, 5), status_col=7, heights=72)
    add_filter_and_finish(ws, h, h + len(rows), 7)
    return ws, h + len(rows)


def sheet_cn(wb, case):
    ws, last = _entry_sheet(wb, "03_中国出口", "03 · 中国出口监管条件",
                            "危险化学品管理属性在此表判定；不得用本表结论推导 UN 号与包装类别",
                            case["cn_export"],
                            extra="重点：监管条件 G 是「定向」许可证，目的地才是适用条件；双氧水仅对缅甸/老挝/阿富汗需办证。")
    r = last + 3
    ws.cell(row=r, column=1, value="证据链接（可直接打开核对原文）").font = _font(11, True, NAVY)
    r += 1
    for e in case["cn_export"]:
        if e.get("evidence"):
            ws.cell(row=r, column=1, value=e["id"]).font = _font(9, True, BLUE)
            c = ws.cell(row=r, column=2, value=e["evidence"])
            c.font = _font(9, color="1D4ED8", name="Consolas")
            c.hyperlink = e["evidence"]
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
            r += 1


def sheet_vn(wb, case):
    ws, last = _entry_sheet(wb, "04_目的国进口", "04 · 目的国（越南）进口准入",
                            "越南化学品法规已于 2026-01-01 / 2026-01-17 整体换版，旧 113/2017 体系不再适用",
                            case["import_vn"],
                            extra="时效红线：凡引用 2026 年之前越南化学品法规的结论，一律视为失效，须重新核验。")
    r = last + 3
    ws.cell(row=r, column=1, value="越南 2026 版法规体系对照（旧 → 新）").font = _font(11, True, NAVY)
    r += 1
    header_row(ws, r, ["项目", "旧体系（2026 前）", "新体系（2026 起）", "生效日", "", "", ""], [22, 40, 46, 22, 6, 6, 6])
    pairs = [
        ("化学品法", "06/2007/QH12（2008-07-01）", "69/2025/QH15", "2026-01-01"),
        ("化学品名录", "Decree 113/2017/ND-CP 附件 I–V", "Nghị định 24/2026/NĐ-CP", "2026-01-17"),
        ("活动管理", "Decree 113/2017/ND-CP", "Nghị định 26/2026/NĐ-CP", "2026-01-17"),
        ("产业与安全安保", "—", "Nghị định 25/2026/NĐ-CP", "2026-01-17"),
        ("SDS / 标签 / 分类", "Circular 32/2017/TT-BCT（2026-01-17 失效）", "Thông tư 01/2026/TT-BCT", "2026-01-17"),
        ("产业与安全执行细则", "—", "Thông tư 02/2026/TT-BCT", "2026-01-17"),
    ]
    body_rows(ws, r + 1, pairs, wraps=(2, 3))
    return ws


def sheet_transport(wb, case):
    ws, last = _entry_sheet(wb, "05_运输危险属性", "05 · 危险货物运输分类与包装",
                            "本表结论仅回答「按危险货物怎么运」，不回答「是否属于危险化学品」",
                            case["transport"],
                            extra="本案例：UN 2014 / 类别 5.1（次要 8）/ PG II / EmS F-H·S-Q / 包装 P504、IBC02 / 大包装禁止。")
    r = last + 3
    ws.cell(row=r, column=1, value="UN 号分档对照表（按浓度，必须以 COA 实测质量分数判定）").font = _font(12, True, NAVY)
    r += 1
    header_row(ws, r, ["浓度（H2O2 w/w）", "UN 号", "类别（次要）", "包装类别", "本案例?", "", ""], [22, 16, 22, 16, 16, 6, 6])
    bands = [
        ("< 8%", "一般不作危险货物", "—", "—", ""),
        ("8% ≤ x < 20%（稳定化）", "UN 2984", "5.1", "III", ""),
        ("20% ≤ x ≤ 60%", "UN 2014", "5.1（8）", "II", "✔ 50% 适用"),
        ("> 60%", "UN 2014 条目（PG I）", "5.1（8）", "I", "需 DG 顾问逐条确认附属条目"),
    ]
    body_rows(ws, r + 1, bands, wraps=(1, 2), heights=26)
    r = r + 1 + len(bands) + 2

    ws.cell(row=r, column=1, value="三种运输方式的规则对照").font = _font(12, True, NAVY)
    r += 1
    header_row(ws, r, ["运输方式", "适用规则（现行版本）", "包装指令", "IBC / 罐柜", "限量 / 例外数量", "标签", "本项目"],
               [14, 36, 22, 26, 30, 16, 30])
    modes = [
        ("海运", "IMDG Code 42-24（2026-01-01 强制；43-26 预计 2027）", "P504（组合包装）", "IBC02；大包装禁止", "按 3.4 / 3.5 章（本案例不适用）", "5.1 + 8", "✔ 采用"),
        ("空运", "IATA DGR 67th（2026）", "客机 550 / 货机 554（20–40% 条目）", "—", "E2", "5.1 + 8", "50% 档存在禁止风险，默认不用"),
        ("陆运", "GB 6944 / JT/T 617；ADR 2025；越南 QCVN", "P504 / IBC02", "罐车 T7", "LQ 1 L；EQ E2（30 mL/500 mL）", "5.1 + 8", "未采用；如改陆运须重评"),
    ]
    body_rows(ws, r + 1, modes, wraps=(2, 5), heights=56)
    return ws


def sheet_label(wb, case):
    ws, last = _entry_sheet(wb, "06_标签与包装", "06 · 标签、包装与产品技术要求",
                            "危险化学品标签（GHS 公示）与危险货物标签（运输）是两套标签要求，通常需同时满足",
                            case["label_pkg"])
    return ws


def sheet_docs(wb, case):
    ws = wb.create_sheet("07_单证清单")
    h = title_block(ws, "07 · 单证清单", "按「谁出、什么时候出、现在是待准备还是待取得」归档；每张单据都要能追溯到责任方",
                    7, extra="勾选列供打印核对；「待取得」表示依赖第三方（实验室/海关/承运人/进口方）出具。")
    header_row(ws, h, ["编号", "类别", "单证名称", "出具 / 责任方", "时点", "状态", "说明与缺口"], [8, 14, 40, 22, 18, 16, 60])
    rows = [(d["id"], d["category"], d["name"], d["owner"], d["timing"], d["status"], d["note"])
            for d in case["documents"]]
    body_rows(ws, h + 1, rows, wraps=(3, 7), status_col=6, heights=34)
    add_filter_and_finish(ws, h, h + len(rows), 7)


def sheet_roles(wb, case):
    ws = wb.create_sheet("08_角色分工")
    h = title_block(ws, "08 · 按角色分工的准备事项", "把「谁在什么时候做什么」落到人；跨部门清单建议在项目启动会逐条认领", 4)
    header_row(ws, h, ["角色", "序号", "需准备 / 需确认的事项", "完成勾选"], [24, 8, 100, 12])
    rows = []
    for role in case["roles"]:
        for i, it in enumerate(role["items"], start=1):
            rows.append((role["role"], i, it, "☐"))
    body_rows(ws, h + 1, rows, wraps=(3,), heights=26)
    add_filter_and_finish(ws, h, h + len(rows), 4)


def sheet_regs(wb, case, chk):
    ws = wb.create_sheet("09_法规索引")
    h = title_block(ws, "09 · 法规索引与时效", "每条法规都登记来源 URL 与核验日期；超过 180 天未复核即需重新核验", 9,
                    extra=f"本轮核验基准日：{case['meta']['prepared_on']}。核验日期为「本条结论所依据的官方原文最后确认时间」。")
    header_row(ws, h, ["ID", "法域", "法规名称", "发布机构", "文号 / 版本", "生效日期", "状态", "核验日期", "覆盖条目", "来源 URL"],
               [6, 10, 46, 20, 22, 14, 22, 12, 22, 60])
    rows = [(r["id"], r["jurisdiction"], r["name"], r["issuer"], r["ref"], r["effective"], r["status"],
             r["verified_on"], r.get("relevance", ""), r["url"]) for r in case["regs"]]
    body_rows(ws, h + 1, rows, wraps=(3, 7, 9, 10), heights=38)
    for i in range(len(rows)):
        c = ws.cell(row=h + 1 + i, column=10)
        c.hyperlink = c.value
        c.font = _font(8, color="1D4ED8", name="Consolas")
    add_filter_and_finish(ws, h, h + len(rows), 10)


def sheet_timeliness(wb, case):
    ws = wb.create_sheet("10_时效性核查")
    h = title_block(ws, "10 · 法规时效性核查", "本表回答：这次判定基于哪一版法规？有没有刚换版、即将换版或被替代的情况？", 6,
                    extra="最典型风险：越南化学品法体系在 2026-01 / 2026-01-17 整体换版，沿用 113/2017 结论会直接出错。")
    header_row(ws, h, ["序号", "核查项", "变化内容", "对本次出口的影响", "是否已核实", "核查日期"], [6, 26, 56, 52, 12, 14])
    rows = [(i, t["item"], t["what_changed"], t["impact"], t["checked"], t["date"])
            for i, t in enumerate(case["timeliness"], start=1)]
    body_rows(ws, h + 1, rows, wraps=(2, 3, 4), heights=44)
    r = h + len(rows) + 3
    ws.cell(row=r, column=1, value="复核动作").font = _font(11, True, NAVY)
    acts = [
        "交付前：对每条法规打开来源 URL，确认页面上仍为现行版本（注意「失效」「已替代」标注）。",
        "交付前：确认运输规则版本（IMDG 每两年、IATA 每年、ADR 每年）与本次出运日期所属版本一致。",
        "交付前：确认目的国是否在 6 个月内换版或发布过渡期安排（越南 2026 年即为典型）。",
        "发货前：若距交付基准日超过 90 天，须重新核验本表全部条目。",
    ]
    for i, a in enumerate(acts, start=1):
        ws.merge_cells(start_row=r + i, start_column=1, end_row=r + i, end_column=6)
        c = ws.cell(row=r + i, column=1, value=f"☐ {a}")
        c.font = _font(9)
        c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        ws.row_dimensions[r + i].height = 22


def sheet_summary(wb, case, chk):
    ws = wb.create_sheet("11_核验状态汇总")
    h = title_block(ws, "11 · 核验状态汇总", "交付口径：只有「已核实」的结论可以直接对客户/报关使用；其余须挂在「待确认事项」上闭环", 5)
    header_row(ws, h, ["主题", "条目数", "已核实", "待确认 / 需确认", "参考 / 其他"], [26, 12, 12, 18, 14])
    rows = []
    for k, d in chk["by_topic"].items():
        rows.append((k, d["total"], d["已核实"], d["待确认"], d["参考"]))
    tot = [sum(r[i] for r in rows) for i in (1, 2, 3, 4)]
    rows.append(("合计", tot[0], tot[1], tot[2], tot[3]))
    body_rows(ws, h + 1, rows, heights=24)
    for c in range(1, 6):
        ws.cell(row=h + 1 + len(rows), column=c).font = _font(10, True, NAVY)
        ws.cell(row=h + 1 + len(rows), column=c).fill = PatternFill("solid", fgColor=LIGHT)

    r = h + len(rows) + 3
    header_row(ws, r, ["编号", "主题", "事项", "状态", "法规依据（摘）"], [10, 16, 56, 16, 50])
    ws.freeze_panes = ws.cell(row=r + 1, column=1)
    idx = {(e["id"]): e for k in ("cn_export", "import_vn", "transport", "label_pkg") for e in case[k]}
    rows2 = [(it["id"], it["topic"], idx[it["id"]]["item"], it["status"], idx[it["id"]]["reg"][:60]) for it in chk["items"]]
    body_rows(ws, r + 1, rows2, wraps=(3, 5), status_col=4, heights=30)


def sheet_risks(wb, case):
    ws = wb.create_sheet("12_风险与常见误区")
    h = title_block(ws, "12 · 风险与常见误区", "这些是同类业务中最容易出错的地方；逐条确认后才算真正做完「查出口要求」", 4)
    header_row(ws, h, ["序号", "误区 / 风险", "正确做法", "本次结论"], [6, 46, 60, 46])
    rows = [
        (1, "看到监管条件 G（两用物项和技术出口许可证-定向）就认为必须办证",
         "G 是「定向」许可证，只有目的地属于清单所列国家（缅/老/阿）才需申请；向越南出口无需，但须保留公告原文备查。",
         "商务部 2026年第40号 附件1第二部分第28项；越南不在其列。"),
        (2, "把《危险化学品目录》的类别当作危险货物包装类别",
         "危化品目录只回答「是否属危化品」；UN 号、类别、PG 来自运输规则（IMDG/IATA/ADR）并随浓度变化。",
         "危化品：目录 903；危险货物：UN2014 / 5.1(8) / PG II（两者独立成立）。"),
        (3, "沿用 2026 年前的越南法规（113/2017、32/2017）",
         "越南已整体换版：69/2025/QH15 于 2026-01-01 生效，24/25/26/2026 与 01/02/2026 于 2026-01-17 生效。",
         "全部越南结论按 2026 版重核；旧附件编号作废。"),
        (4, "用名义浓度或体积浓度判断 UN 号",
         "分类阈值按质量分数（w/w），须以 COA 实测值为准；边界浓度（接近 20% / 60%）要特别确认。",
         "50% 落在 20–60% 区间 → UN2014 PG II。"),
        (5, "把稳定剂之外的其他添加剂也算作「同一产品」",
         "应急管理部明确：稳定剂/惰性化学品之外的其他化学品，该溶液不再属于「过氧化氢的水溶液」，须另行鉴定。",
         "本案例仅含稳定剂（焦磷酸盐类），但须由技术部/实验室确认。"),
        (6, "以为 8% 以下也按危化品管理",
         "目录条目 903 的门槛是「含量>8%」；低于 8% 不在目录内（但运输规则另有一套 8% 门槛）。",
         "50% 明确在门槛之上。"),
        (7, "只做中文标签，越南端再补做",
         "出口端需中文危险公示标签与 SDS，越南端需越南语标签与 SDS；IBC 双语气泡标签可减少口岸争议。",
         "双标签方案，随批印刷。"),
        (8, "把 IBC 当普通包装订舱",
         "IBC 须为经 UN 认证的危险货物 IBC，具性能合格证与使用鉴定；大包装（LP）禁止。",
         "31H1/31HA1 等，需供应商性能证 + 海关使用鉴定。"),
        (9, "空运 50% 过氧化氢",
         "IATA 中 20–40% 与 >40–60% 条目的客机/货机许可不同，部分承运人直接禁运。",
         "本案例默认海运；空运须先取得 DGR 原文与承运人书面意见。"),
        (10, "未确认进口方资质就发货",
         "若过氧化氢在越南属「有条件化学品」，进口方必须持经营资格证。",
         "须在越南 24/2026 附录中确认归属，并向客户索取资格证。"),
        (11, "忽略食品用途风险",
         "同一 HS 下存在「用作食品添加剂」的 CIQ 分档；用途改变会触发食品安全准入。",
         "合同与发票写明「For industrial use only」。"),
        (12, "以为出口退税可以改善报价",
         "2847000000 观测到的出口退税率为 0%，不得计入收益。",
         "报价按零退税测算，财务复核。"),
    ]
    body_rows(ws, h + 1, rows, wraps=(2, 3, 4), heights=52)
    return ws


def sheet_openq(wb, case):
    ws = wb.create_sheet("13_待确认事项")
    h = title_block(ws, "13 · 待确认事项（未闭环清单）", "每项都要写明「为什么不能确定、谁来确认、确认后解除哪些条目」；确认结果回写到对应表的状态列",
                    7, extra="规则：无法取得官方原文或专业意见的，一律保留「待确认」，不做推定，不对客户作出承诺性表述。")
    header_row(ws, h, ["编号", "待确认问题", "为什么不能确定", "责任方", "解除后影响条目", "当前处理动作", "闭环状态"],
               [8, 52, 56, 24, 26, 40, 14])
    rows = []
    for q in case["open_questions"]:
        rows.append((q["id"], q["question"], q["why"], q["owner"], "、".join(q["blocks"]),
                     "取得官方原文/专业书面意见后，把对应条目状态改为「已核实」并注明来源", "未闭环"))
    body_rows(ws, h + 1, rows, wraps=(2, 3, 5, 6), heights=44)
    dv = DataValidation(type="list", formula1='"未闭环,已闭环,已升级"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"G{h + 1}:G{h + len(rows)}")
    for i in range(len(rows)):
        c = ws.cell(row=h + 1 + i, column=7)
        c.fill = PatternFill("solid", fgColor="FFF1E0")
        c.font = _font(9, True, "B45309")
    add_filter_and_finish(ws, h, h + len(rows), 7)


def sheet_checklist(wb, case):
    ws = wb.create_sheet("14_核对清单")
    h = title_block(ws, "14 · 出货前核对清单（打印用）", "按时间顺序勾选；任一「关键项」未勾选不得安排订舱或装运", 5)
    header_row(ws, h, ["阶段", "序号", "核对项", "是否关键", "勾选 / 证据编号"], [18, 8, 96, 12, 22])
    groups = [
        ("立项/报价前", [
            "锁定产品身份：CAS、浓度（w/w）、稳定剂、用途、包装规格（→01 表）",
            "确认 HS 候选并取得报关行/归类意见（→02 表）",
            "确认中国侧监管条件：危化品、易制爆、定向易制毒、CCL（→03 表）",
            "确认目的国法规版本与准入路径（→04 表、10 表）",
            "向客户报价前确认目的国税率与享惠路径（→04 表 VN-07）",
        ]),
        ("下单/合同", [
            "合同写明：用途限制（工业用/非食品）、包装、运输方式、标签语言、责任划分",
            "取得进口方资格证（如需）与书面用途声明",
            "确认进口方是否办理原产地证以享惠",
        ]),
        ("生产/包装", [
            "批次 COA 实测浓度确认落在 20–60% 区间",
            "IBC 供应商提供性能合格证与 UN 标记照片",
            "完成中/越双语标签印刷并经进口方书面确认",
            "完成中文 SDS 与越南语 SDS（16 项内容，运输信息一致）",
        ]),
        ("检验/报关", [
            "取得危险特性分类鉴别报告",
            "取得出境货物运输包装性能检验结果单",
            "灌装后取得出境危险货物运输包装使用鉴定结果单",
            "提交出口危险化学品生产企业符合性声明 + 稳定剂说明",
            "属地海关报检取得电子底账；口岸报关（2847000000 / CIQ 2847000000301）",
        ]),
        ("订舱/出运", [
            "提交 DGD（UN2014 / 5.1(8) / PG II / EmS F-H,S-Q）",
            "船公司书面确认接受 50% 过氧化氢 IBC",
            "确认目的港危险货物卸货与提离安排",
            "B/L、发票、装箱单信息交叉核对（含量、UN、HS、件数）",
        ]),
        ("目的国清关", [
            "进口方在 VN Single Window 完成申报并取得反馈",
            "越南语标签与 SDS 已随货或在海关可调取",
            "优惠税率申报所需原产地证书已签发",
        ]),
    ]
    rows = []
    n = 0
    for stage, items in groups:
        for it in items:
            n += 1
            rows.append((stage, n, it, "是" if stage in ("立项/报价前", "检验/报关", "订舱/出运") else "否", "☐"))
    body_rows(ws, h + 1, rows, wraps=(3,), heights=26)
    return ws


def sheet_sample(wb, case):
    ws = wb.create_sheet("15_填写样例")
    h = title_block(ws, "15 · 如何填一个新案例", "把本表字段填进 case.json，即可用同一套脚本生成同结构的 HTML 与 Excel", 4)
    header_row(ws, h, ["路径", "示例值", "说明", "必填"], [26, 62, 62, 8])
    rows = [
        ("meta.case_id", "EC-2026-002", "唯一编号，建议 年份+序号", "是"),
        ("inputs.product.cas", "7664-93-9", "CAS 号，逐条与目录核对", "是"),
        ("inputs.product.concentration", "98% (w/w)", "必须写明口径 w/w 或 w/v", "是"),
        ("inputs.product.use", "工业级（非食品）", "用途改变会改变准入路径", "是"),
        ("inputs.product.packaging", "IBC 1000 L", "决定危险货物包装指令", "是"),
        ("inputs.product.destination", "越南", "决定目的国法规版本与税率", "是"),
        ("inputs.product.transport_mode", "海运", "决定 IMDG/IATA/ADR 适用", "是"),
        ("hs_candidates[].basis", "第28章章注一…", "必须写归类依据，不能只写编码", "是"),
        ("cn_export[]", "见 03 表结构", "topic 固定为「中国出口」", "是"),
        ("import_vn[]", "见 04 表结构", "topic 固定为「目的国进口」", "是"),
        ("transport[]", "见 05 表结构", "topic 固定为「运输」；不得写危化品目录结论", "是"),
        ("label_pkg[]", "见 06 表结构", "topic 固定为「标签与包装」", "是"),
        ("regs[]", "19 条示例见 09 表", "每条须有 url 与 verified_on", "是"),
        ("open_questions[]", "见 13 表", "所有「待确认」条目的编号都必须在 blocks 中出现", "是"),
        ("timeliness[]", "见 10 表", "写明变化与影响", "是"),
    ]
    body_rows(ws, h + 1, rows, wraps=(2, 3), heights=30)
    r = h + len(rows) + 3
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    c = ws.cell(row=r, column=1, value="校验命令：python scripts/validators.py <case.json> --out checks.json  → 全部通过后再生成 HTML/Excel")
    c.font = _font(10, True, "B45309")
    c.fill = PatternFill("solid", fgColor="FFF8E1")
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[r].height = 26


def build(case_path: str, out_path: str, checks_path: str | None = None) -> str:
    case = json.loads(Path(case_path).read_text(encoding="utf-8"))
    if checks_path and Path(checks_path).exists():
        chk = json.loads(Path(checks_path).read_text(encoding="utf-8"))
    else:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from validators import run as vrun
        chk = vrun(case_path)

    wb = Workbook()
    sheet_cover(wb, case, chk)
    sheet_identity(wb, case)
    sheet_hs(wb, case)
    sheet_cn(wb, case)
    sheet_vn(wb, case)
    sheet_transport(wb, case)
    sheet_label(wb, case)
    sheet_docs(wb, case)
    sheet_roles(wb, case)
    sheet_regs(wb, case, chk)
    sheet_timeliness(wb, case)
    sheet_summary(wb, case, chk)
    sheet_risks(wb, case)
    sheet_openq(wb, case)
    sheet_checklist(wb, case)
    sheet_sample(wb, case)

    wb.properties.title = case["meta"]["title"]
    wb.properties.subject = "出口合规准备清单（不构成法律意见）"
    wb.properties.creator = "export-compliance-check skill"
    wb.properties.description = case["meta"]["assumption_notice"]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--out", default=None)
    ap.add_argument("--checks", default=None)
    a = ap.parse_args(argv)
    case = json.loads(Path(a.case).read_text(encoding="utf-8"))
    out = a.out or str(Path(a.case).parent / f"出口合规准备工作簿_{case['meta']['case_id']}.xlsx")
    print(build(a.case, out, a.checks))


if __name__ == "__main__":
    main()
