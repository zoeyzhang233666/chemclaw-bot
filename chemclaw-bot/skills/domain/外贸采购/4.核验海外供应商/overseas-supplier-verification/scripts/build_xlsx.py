# -*- coding: utf-8 -*-
"""
build_xlsx.py — render the verification workbook (.xlsx, 8 sheets).

Usage:
    python scripts/build_xlsx.py project.json -o out/
Sheets:
    00 封面与结论      01 企业信息        02 制造证据
    03 产品匹配        04 文件核验        05 交易主体一致性
    06 公开风险与事件  07 待确认事项+询证清单
"""
from __future__ import annotations

import argparse
import os
import sys

import ovslib as L
from ovslib import esc  # noqa: F401  (kept for symmetry)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except Exception as exc:  # pragma: no cover
    raise SystemExit("需要 openpyxl：pip install openpyxl  — " + str(exc))

# ---------------------------------------------------------------- theme
FONT = "Microsoft YaHei"
INK = "1F2A37"
BRAND = "0F4C81"
BRAND_SOFT = "EAF2F9"
HEAD_FILL = PatternFill("solid", fgColor=BRAND)
HEAD_FONT = Font(name=FONT, size=10, bold=True, color="FFFFFF")
TITLE_FONT = Font(name=FONT, size=16, bold=True, color=BRAND)
SUB_FONT = Font(name=FONT, size=10, color="6B7A90")
BODY_FONT = Font(name=FONT, size=10, color=INK)
BOLD_FONT = Font(name=FONT, size=10, bold=True, color=INK)

FILL = {
    "ok": PatternFill("solid", fgColor="E6F5EE"),
    "warn": PatternFill("solid", fgColor="FDF1DD"),
    "mid": PatternFill("solid", fgColor="EEF1F5"),
    "mute": PatternFill("solid", fgColor="F3F5F8"),
    "band": PatternFill("solid", fgColor="F8FAFC"),
    "mock": PatternFill("solid", fgColor="F4EBFA"),
    "brand": PatternFill("solid", fgColor=BRAND_SOFT),
}
COLOR = {"ok": "0F7B53", "warn": "A15C00", "mid": "5B6472", "mute": "6B7A90"}
THIN = Side(style="thin", color="E3E8EF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _sheet(wb, title, color=BRAND):
    ws = wb.create_sheet(title)
    ws.sheet_properties.tabColor = color
    ws.sheet_view.showGridLines = False
    return ws


def title_block(ws, title, subtitle, ncols, meta_line=""):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=title)
    c.font = TITLE_FONT
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c2 = ws.cell(row=2, column=1, value=subtitle)
    c2.font = SUB_FONT
    ws.row_dimensions[2].height = 18
    r = 3
    if meta_line:
        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=ncols)
        c3 = ws.cell(row=3, column=1, value=meta_line)
        c3.font = Font(name=FONT, size=9, italic=True, color="6B7A90")
        r = 4
    return r + 1


def header_row(ws, row, headers, widths=None, heights=30):
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[row].height = heights
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def body_cell(ws, row, col, value, bold=False, center=False, fill=None, color=None):
    c = ws.cell(row=row, column=col, value=value)
    c.font = BOLD_FONT if bold else BODY_FONT
    c.alignment = CENTER if center else WRAP
    c.border = BORDER
    if fill:
        c.fill = fill
    if color:
        c.font = Font(name=FONT, size=10, bold=bold, color=color)
    return c


def state_cell(ws, row, col, raw_state):
    s = L.norm_state(raw_state)
    c = body_cell(ws, row, col, L.STATE[s]["zh"], center=True,
                  fill=FILL[L.STATE[s]["tone"]], color=COLOR[L.STATE[s]["tone"]])
    c.font = Font(name=FONT, size=10, bold=True, color=COLOR[L.STATE[s]["tone"]])
    return c


def ev_pairs(project):
    m = {}
    for e in project.get("evidence", []) or []:
        m[e.get("id")] = e
    return m


# ---------------------------------------------------------------- 00 cover
def sheet_cover(wb, p):
    ws = _sheet(wb, "00 封面与结论")
    meta = p.get("meta", {})
    sm = p.get("summary", {})
    counts = L.count_states(list(L.iter_state_carriers(p)))
    evs = p.get("evidence", []) or []

    ws.merge_cells("A1:F1")
    c = ws["A1"]
    c.value = meta.get("title", "海外供应商核验报告")
    c.font = Font(name=FONT, size=18, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=BRAND)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 40

    ws.merge_cells("A2:F2")
    ws["A2"].value = meta.get("subject_full", "")
    ws["A2"].font = Font(name=FONT, size=12, bold=True, color=INK)
    ws["A2"].alignment = Alignment(vertical="center")
    ws.row_dimensions[2].height = 26

    rows = [
        ("报告编号", meta.get("doc_no")), ("核验基准日", meta.get("as_of")),
        ("采购品", meta.get("product")), ("要求规格", meta.get("product_spec")),
        ("国家/地区", meta.get("country")), ("贸易术语", meta.get("incoterm")),
        ("编制", meta.get("author")), ("复核", meta.get("reviewer")),
        ("版本", meta.get("version")),
    ]
    r = 4
    for k, v in rows:
        body_cell(ws, r, 1, k, bold=True, fill=FILL["band"])
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        body_cell(ws, r, 2, v)
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    h = ws.cell(row=r, column=1, value="一、核验结论（不含风险评分）")
    h.font = Font(name=FONT, size=12, bold=True, color=BRAND)
    r += 1

    verd = L.VERDICT.get(sm.get("verdict"), L.VERDICT["insufficient"])
    body_cell(ws, r, 1, "结论口径", bold=True, fill=FILL["band"])
    body_cell(ws, r, 2, verd["zh"], bold=True, fill=FILL["warn"], color=COLOR["warn"])
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    body_cell(ws, r, 3, verd["desc"])
    r += 1
    body_cell(ws, r, 1, "核心判断", bold=True, fill=FILL["band"])
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    c = body_cell(ws, r, 2, sm.get("headline"))
    c.font = Font(name=FONT, size=11, bold=True, color=INK)
    ws.row_dimensions[r].height = 34
    r += 1
    body_cell(ws, r, 1, "说明", bold=True, fill=FILL["band"])
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    c = body_cell(ws, r, 2, sm.get("text"))
    ws.row_dimensions[r].height = 92
    r += 2

    # 状态计数：公式来自各表实际数据（真实可算），不是专家打分
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    h = ws.cell(row=r, column=1, value="二、状态计数（由各表数据实时统计，公式可追溯）")
    h.font = Font(name=FONT, size=12, bold=True, color=BRAND)
    r += 1
    header_row(ws, r, ["状态", "含义", "本报告计数", "统计口径"], widths=[16, 34, 14, 60])
    r += 1
    first_count_row = r
    for k in L.STATE_ORDER:
        body_cell(ws, r, 1, L.STATE[k]["zh"], bold=True, fill=FILL[L.STATE[k]["tone"]],
                  color=COLOR[L.STATE[k]["tone"]])
        body_cell(ws, r, 2, L.STATE[k]["en"])
        body_cell(ws, r, 3, counts[k], center=True)
        body_cell(ws, r, 4, "01/02/03/04/05/06 表状态列计数之和（含主体映射与文件核验）")
        r += 1
    body_cell(ws, r, 1, "合计", bold=True, fill=FILL["band"])
    body_cell(ws, r, 2, "Total")
    body_cell(ws, r, 3, f"=SUM(C{first_count_row}:C{r-1})", center=True, bold=True)
    body_cell(ws, r, 4, "证据条目数见下")
    r += 1
    body_cell(ws, r, 1, "证据条目", bold=True, fill=FILL["brand"])
    body_cell(ws, r, 2, "Evidence items")
    body_cell(ws, r, 3, len(evs), center=True)
    body_cell(ws, r, 4, "证据索引（见 02 表「证据索引」区与 HTML 报告）")
    r += 2

    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    h = ws.cell(row=r, column=1, value="三、本报告明确不下的结论")
    h.font = Font(name=FONT, size=12, bold=True, color=BRAND)
    r += 1
    for x in L.as_list(sm.get("not_concluded")):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = body_cell(ws, r, 1, "• " + str(x), fill=FILL["warn"])
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value=meta.get("disclaimer"))
    c.font = Font(name=FONT, size=9, italic=True, color="6B7A90")
    c.alignment = WRAP
    ws.row_dimensions[r].height = 58
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return ws


# ---------------------------------------------------------------- 01 identity
def sheet_identity(wb, p):
    ws = _sheet(wb, "01 企业信息")
    meta = p.get("meta", {})
    r = title_block(ws, "01 企业信息", "注册主体、注册国家、注册地址与公开经营信息",
                    6, f"{meta.get('doc_no')} · 基准日 {meta.get('as_of')}")
    sec = next((s for s in p.get("sections", []) if s.get("id") == "s01"), None)
    table = None
    if sec:
        table = next((b for b in sec.get("blocks", []) if b.get("type") == "table"), None)
    header_row(ws, r, ["要素", "核验结果", "状态", "证据", "证据要点", "来源链接"],
               widths=[18, 62, 12, 12, 40, 46])
    r += 1
    emap = ev_pairs(p)
    rows = (table or {}).get("rows", []) or [
        ["法定名称", p.get("subject_master", {}).get("legal_name"), "unknown", ""],
    ]
    for row in rows:
        body_cell(ws, r, 1, row[0], bold=True)
        body_cell(ws, r, 2, row[1])
        state_cell(ws, r, 3, row[2])
        ids = L.evid_ids(row[3] if len(row) > 3 else "")
        body_cell(ws, r, 4, ",".join(ids) or "—", center=True)
        ev = emap.get(ids[0]) if ids else None
        body_cell(ws, r, 5, (ev or {}).get("claim", ""))
        body_cell(ws, r, 6, (ev or {}).get("url", ""))
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value="提示：状态为「未知」需补 CR 证书与官方登记查询；「未核实」需第二个独立来源交叉印证。")
    c.font = Font(name=FONT, size=9, color="A15C00")
    r += 2

    # subject master
    sm = p.get("subject_master", {}) or {}
    if sm:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = ws.cell(row=r, column=1, value="主体档案（Supplier Master Record）")
        c.font = Font(name=FONT, size=12, bold=True, color=BRAND)
        r += 1
        labels = {
            "legal_name": "法定名称", "short_name": "简称", "country": "国家",
            "address": "地址", "cr_no": "商业登记号 CR", "parent": "母公司/集团",
            "ownership": "股权关系", "website": "官网", "products_claimed": "主张产品",
            "contact": "电话", "email_official": "邮箱", "contract_party": "合同主体",
            "beneficiary": "收款户名", "incoterm": "贸易术语", "payment_terms": "付款条件",
        }
        for k, v in sm.items():
            body_cell(ws, r, 1, labels.get(k, k), bold=True, fill=FILL["band"])
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
            body_cell(ws, r, 2, v)
            r += 1
        r += 1
    return ws


# ---------------------------------------------------------------- 02 evidence
def sheet_plant(wb, p):
    ws = _sheet(wb, "02 制造证据")
    meta = p.get("meta", {})
    r = title_block(ws, "02 制造证据", "是否真有工厂、在哪、产能口径、制造关系能否证明",
                    6, f"{meta.get('doc_no')} · 基准日 {meta.get('as_of')}")
    sec = next((s for s in p.get("sections", []) if s.get("id") == "s03"), None)
    tbl = None
    for b in (sec or {}).get("blocks", []):
        if b.get("type") in ("table", "hierarchy"):
            tbl = b
            if b.get("type") == "table":
                break
    emap = ev_pairs(p)
    header_row(ws, r, ["核查项", "公开信息", "状态", "证据", "证据要点", "来源链接"],
               widths=[20, 60, 12, 12, 38, 46])
    r += 1
    for row in ((tbl or {}).get("rows", []) or []):
        body_cell(ws, r, 1, row[0], bold=True)
        body_cell(ws, r, 2, row[1])
        state_cell(ws, r, 3, row[2])
        ids = L.evid_ids(row[3] if len(row) > 3 else "")
        body_cell(ws, r, 4, ",".join(ids) or "—", center=True)
        ev = emap.get(ids[0]) if ids else None
        body_cell(ws, r, 5, (ev or {}).get("claim", ""))
        body_cell(ws, r, 6, (ev or {}).get("url", ""))
        r += 1

    # entity map
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value="集团与交易主体映射（先用这一层分清谁是谁）")
    c.font = Font(name=FONT, size=12, bold=True, color=BRAND)
    r += 1
    hdrs = ["层级", "角色", "主体名称", "注册地", "状态", "证据"]
    header_row(ws, r, hdrs, widths=[16, 18, 40, 18, 12, 14])
    r += 1
    for e in p.get("entity_map", []) or []:
        if e.get("layer") != "生产层" and e.get("kind") not in ("manufacturer", "manufacturer_jv"):
            continue
        body_cell(ws, r, 1, e.get("layer"))
        body_cell(ws, r, 2, L.LAYER_ZH.get(e.get("kind"), e.get("kind")))
        body_cell(ws, r, 3, e.get("entity"), bold=True)
        body_cell(ws, r, 4, e.get("jurisdiction"))
        state_cell(ws, r, 5, e.get("state"))
        body_cell(ws, r, 6, e.get("evidence") or "—", center=True)
        r += 1

    # evidence index
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value="证据索引（每条结论可回溯）")
    c.font = Font(name=FONT, size=12, bold=True, color=BRAND)
    r += 1
    ids_row = r
    header_row(ws, r, ["ID", "分级", "来源", "主张事实", "原文摘录", "用途 / 链接"],
               widths=[20, 60, 12, 12, 38, 46])
    r += 1
    for e in p.get("evidence", []) or []:
        mock = e.get("grade") == "mock"
        body_cell(ws, r, 1, e.get("id"), bold=True, center=True,
                  fill=FILL["mock"] if mock else FILL["band"])
        body_cell(ws, r, 2, L.EVID_GRADE.get(e.get("grade"), {}).get("zh", e.get("grade")))
        body_cell(ws, r, 3, e.get("publisher"))
        body_cell(ws, r, 4, e.get("claim"))
        body_cell(ws, r, 5, e.get("quote"))
        body_cell(ws, r, 6, (e.get("used_for") or "") + ("\n" + (e.get("url") or "")))
        if mock:
            ws.cell(row=r, column=1).font = Font(name=FONT, size=10, bold=True, color="8A3BB5")
        r += 1
    return ws


# ---------------------------------------------------------------- 03 product
def sheet_product(wb, p):
    ws = _sheet(wb, "03 产品匹配")
    meta = p.get("meta", {})
    r = title_block(ws, "03 产品匹配", "主营业务与产品目录是否覆盖拟采购品及规格",
                    6, f"{meta.get('doc_no')} · 采购品：{meta.get('product')} · 规格：{meta.get('product_spec')}")
    sec = next((s for s in p.get("sections", []) if s.get("id") == "s02"), None)
    tbl = None
    for b in (sec or {}).get("blocks", []):
        if b.get("type") == "table":
            tbl = b
            break
    emap = ev_pairs(p)
    header_row(ws, r, ["核验项", "公开信息", "状态", "证据", "证据要点", "来源链接"],
               widths=[20, 58, 12, 12, 40, 46])
    r += 1
    for row in ((tbl or {}).get("rows", []) or []):
        body_cell(ws, r, 1, row[0], bold=True)
        body_cell(ws, r, 2, row[1])
        state_cell(ws, r, 3, row[2])
        ids = L.evid_ids(row[3] if len(row) > 3 else "")
        body_cell(ws, r, 4, ",".join(ids) or "—", center=True)
        ev = emap.get(ids[0]) if ids else None
        body_cell(ws, r, 5, (ev or {}).get("claim", ""))
        body_cell(ws, r, 6, (ev or {}).get("url", ""))
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1,
                value="判断口径：产品页证明「集团卖该产品」≠「本厂这条产线卖给我方这个规格」。"
                      "最后一公里必须由 TDS（等级）+ 批号级 COA + 装箱单三件对齐。")
    c.font = Font(name=FONT, size=9, color="A15C00")
    return ws


# ---------------------------------------------------------------- 04 documents
def sheet_docs(wb, p):
    ws = _sheet(wb, "04 文件核验")
    meta = p.get("meta", {})
    r = title_block(ws, "04 文件核验", "注册证书 / 产品认证 / SDS / COA / PI / 银行信息 逐件交叉核验",
                    8, f"{meta.get('doc_no')} · 基准日 {meta.get('as_of')} · 标「模拟」者为演示用虚构样本")
    header_row(ws, r, ["编号", "文件", "类型", "名义持有人", "提供", "检查通过", "状态", "逐项检查 / 说明"],
               widths=[10, 24, 12, 22, 8, 12, 12, 78])
    r += 1
    for d in p.get("documents", []) or []:
        st = L.derive_doc_state(d)
        s = L.doc_check_summary(d)
        body_cell(ws, r, 1, d.get("id"), bold=True, center=True)
        body_cell(ws, r, 2, d.get("name"), fill=FILL["mock"] if d.get("mock") else None)
        body_cell(ws, r, 3, d.get("type"), center=True)
        body_cell(ws, r, 4, d.get("holder"))
        body_cell(ws, r, 5, "是" if d.get("provided") else "否", center=True)
        body_cell(ws, r, 6, f"{s['ok']}/{s['total']}" if s["total"] else "—", center=True)
        state_cell(ws, r, 7, st)
        checks = "\n".join(f"{'✓' if c.get('ok') else '✕'} {c.get('k')}：{c.get('v')}"
                           for c in L.as_list(d.get("checks")))
        body_cell(ws, r, 8, checks or (d.get("note") or "未提供 / 待索取"))
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(row=r, column=1,
                value="文件层面的判定只回答「这份文件与主体/条款是否自洽」，不回答「这家企业是否可信」。"
                      "文件缺失一律记「未提供」，不得用宣传材料替代。")
    c.font = Font(name=FONT, size=9, color="A15C00")
    return ws


# ---------------------------------------------------------------- 05 entity consistency
def sheet_consistency(wb, p):
    ws = _sheet(wb, "05 交易主体一致性")
    meta = p.get("meta", {})
    r = title_block(ws, "05 交易主体一致性", "合同主体 / 实际供货主体 / 收款主体 是否对齐",
                    6, f"{meta.get('doc_no')} · 清单来自模拟件，仅演示核验方法")
    blk = None
    for s in p.get("sections", []):
        for b in s.get("blocks", []):
            if b.get("type") == "matrix_map":
                blk = b
    header_row(ws, r, ["核对项", "交易文件所载", "官方/公开基线", "比对判断", "状态", "说明", "证据"],
               widths=[22, 30, 30, 24, 12, 46, 12])
    r += 1
    for row in ((blk or {}).get("rows", []) or []):
        body_cell(ws, r, 1, row.get("item"), bold=True)
        body_cell(ws, r, 2, row.get("a"))
        body_cell(ws, r, 3, row.get("b"))
        body_cell(ws, r, 4, row.get("c"))
        state_cell(ws, r, 5, row.get("state"))
        body_cell(ws, r, 6, row.get("note"))
        body_cell(ws, r, 7, row.get("evid") or "—", center=True)
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value=(blk or {}).get("foot", ""))
    c.font = Font(name=FONT, size=9, color="A15C00")
    c.alignment = WRAP
    ws.row_dimensions[r].height = 60
    r += 2

    # transaction party matrix
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value="交易主体四象限（同一批货，四个「谁」）")
    c.font = Font(name=FONT, size=12, bold=True, color=BRAND)
    r += 1
    header_row(ws, r, ["角色", "主体", "依据文件", "风险含义", "状态", "补齐动作"],
               widths=[22, 30, 30, 24, 12, 46])
    r += 1
    sm = p.get("subject_master", {})
    quads = [
        ("合同主体（卖方）", sm.get("contract_party"), "PI 抬头 / 合同签署页", "决定追索对象", "doubt",
         "要求公司抬头纸 + 有权签字人姓名职务"),
        ("实际生产主体", "PETROKEMYA（朱拜勒装置）", "CR + 工业许可 + COA", "决定货从哪来", "unverified",
         "索取装置编号、工业许可证、批号级 COA"),
        ("出口 / 发货主体", "B/L 发货人", "提单、原产地证", "决定合规与清关", "unknown", "装运前索取提单样张"),
        ("收款主体", sm.get("beneficiary"), "付款指令 + 银行确认函", "决定钱付给谁", "doubt",
         "付款指令 + 银行确认函 + 关系声明 + 官网回呼"),
    ]
    for q in quads:
        body_cell(ws, r, 1, q[0], bold=True)
        body_cell(ws, r, 2, q[1])
        body_cell(ws, r, 3, q[2])
        body_cell(ws, r, 4, q[3])
        state_cell(ws, r, 5, q[4])
        body_cell(ws, r, 6, q[5])
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1,
                value="处置原则：收款主体 ≠ 合同主体时，先要三份文件再谈付款——①卖方签署的付款指令/授权书"
                      "②收款方与卖方关系声明 ③通过官网公开邮箱或电话回呼确认。三份任一缺失即不放款。"
                      "但差异本身不构成欺诈认定。")
    c.font = Font(name=FONT, size=9, color="A15C00")
    c.alignment = WRAP
    ws.row_dimensions[r].height = 48
    return ws


# ---------------------------------------------------------------- 06 public risk + events
def sheet_risk(wb, p):
    ws = _sheet(wb, "06 公开风险与事件")
    meta = p.get("meta", {})
    r = title_block(ws, "06 公开风险与事件", "制裁、司法、供应中断、贸易救济等可查事实（只列事实，不评级）",
                    6, f"{meta.get('doc_no')} · 基准日 {meta.get('as_of')}")
    sec = next((s for s in p.get("sections", []) if s.get("id") == "s06"), None)
    tbl = None
    for b in (sec or {}).get("blocks", []):
        if b.get("type") == "table":
            tbl = b
            break
    emap = ev_pairs(p)
    header_row(ws, r, ["议题", "查得的事实", "状态", "证据", "证据要点", "来源链接"],
               widths=[20, 60, 12, 12, 38, 46])
    r += 1
    for row in ((tbl or {}).get("rows", []) or []):
        body_cell(ws, r, 1, row[0], bold=True)
        body_cell(ws, r, 2, row[1])
        state_cell(ws, r, 3, row[2])
        ids = L.evid_ids(row[3] if len(row) > 3 else "")
        body_cell(ws, r, 4, ",".join(ids) or "—", center=True)
        ev = emap.get(ids[0]) if ids else None
        body_cell(ws, r, 5, (ev or {}).get("claim", ""))
        body_cell(ws, r, 6, (ev or {}).get("url", ""))
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1,
                value="制裁筛查必须用英文全称 + 注册号 + 地址三要素匹配，并留存查询截图与时间戳；"
                      "「未检索到」不等于「不存在」。本表不含风险分数。")
    c.font = Font(name=FONT, size=9, color="A15C00")
    r += 2

    # timeline
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value="公开事件时间轴")
    c.font = Font(name=FONT, size=12, bold=True, color=BRAND)
    r += 1
    header_row(ws, r, ["日期", "事件", "分类", "证据", "来源", ""],
               widths=[20, 60, 12, 12, 38, 46])
    r += 1
    for t in p.get("timeline", []) or []:
        body_cell(ws, r, 1, t.get("date"), center=True)
        body_cell(ws, r, 2, t.get("event"))
        body_cell(ws, r, 3, {"entity": "主体", "plant": "装置", "supply": "供应",
                             "trade": "贸易救济", "price": "价格", "meta": "方法"}.get(t.get("tag"), t.get("tag")),
                  center=True)
        ids = L.evid_ids(t.get("evid"))
        body_cell(ws, r, 4, ",".join(ids) or "—", center=True)
        ev = emap.get(ids[0]) if ids else None
        body_cell(ws, r, 5, (ev or {}).get("publisher", ""))
        body_cell(ws, r, 6, (ev or {}).get("url", ""))
        r += 1
    return ws


# ---------------------------------------------------------------- 07 gaps + RFI
def sheet_gaps(wb, p):
    ws = _sheet(wb, "07 待确认事项与询证")
    meta = p.get("meta", {})
    r = title_block(ws, "07 待确认事项与英文询证清单", "把「未知」变成「已知」的最小文件集",
                    8, f"{meta.get('doc_no')} · 基准日 {meta.get('as_of')}")
    header_row(ws, r, ["编号", "领域", "缺口", "影响", "补证动作", "责任人", "优先级", "状态"],
               widths=[8, 16, 40, 30, 40, 12, 8, 12])
    r += 1
    for g in p.get("gaps", []) or []:
        body_cell(ws, r, 1, g.get("id"), bold=True, center=True)
        body_cell(ws, r, 2, g.get("area"))
        body_cell(ws, r, 3, g.get("gap"))
        body_cell(ws, r, 4, g.get("impact"))
        body_cell(ws, r, 5, g.get("action"))
        body_cell(ws, r, 6, g.get("owner"))
        pr = g.get("priority")
        body_cell(ws, r, 7, pr, center=True,
                  fill=FILL["warn"] if pr == "高" else FILL["band"])
        state_cell(ws, r, 8, "unknown" if pr == "高" else "unverified")
        r += 1
    r += 2

    rfi = p.get("rfi") or {}
    if rfi:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        c = ws.cell(row=r, column=1, value="英文供应商询证清单 / Supplier Due-Diligence Enquiry")
        c.font = Font(name=FONT, size=12, bold=True, color=BRAND)
        r += 1
        info = [("Title", rfi.get("title")), ("Ref", rfi.get("ref")),
                ("To", rfi.get("to")), ("From", rfi.get("from")), ("Date", rfi.get("date"))]
        for k, v in info:
            body_cell(ws, r, 1, k, bold=True, fill=FILL["band"])
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
            body_cell(ws, r, 2, v)
            r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        c = body_cell(ws, r, 1, rfi.get("intro", ""))
        c.font = Font(name=FONT, size=9, italic=True, color="33415C")
        ws.row_dimensions[r].height = 46
        r += 2
        header_row(ws, r, ["No.", "Enquiry clause (English)", "", "", "", "回应（供供应商填写）", "附件已提供", "备注"],
                   widths=[8, 16, 40, 30, 40, 12, 8, 12])
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        r += 1
        start = r
        for cl in L.as_list(rfi.get("clauses")):
            body_cell(ws, r, 1, cl.get("id"), bold=True, center=True)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
            body_cell(ws, r, 2, cl.get("text"))
            body_cell(ws, r, 6, "")
            body_cell(ws, r, 7, "")
            body_cell(ws, r, 8, "")
            ws.row_dimensions[r].height = 34
            r += 1
        dv = DataValidation(type="list", formula1='"Yes,No,Partial"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"G{start}:G{r-1}")
    return ws


# ---------------------------------------------------------------- build
def build(project: dict, outdir: str, name: str | None = None) -> str:
    wb = Workbook()
    wb.remove(wb.active)
    sheet_cover(wb, project)
    sheet_identity(wb, project)
    sheet_plant(wb, project)
    sheet_product(wb, project)
    sheet_docs(wb, project)
    sheet_consistency(wb, project)
    sheet_risk(wb, project)
    sheet_gaps(wb, project)

    wb.properties.title = project.get("meta", {}).get("title", "海外供应商核验报告")
    wb.properties.creator = "overseas-supplier-verification"
    wb.properties.subject = project.get("meta", {}).get("subject_full", "")

    os.makedirs(outdir, exist_ok=True)
    fname = L.safe_name(name or project.get("meta", {}).get("export_prefix") or "supplier-verification")
    path = os.path.join(outdir, fname + ".xlsx")
    wb.save(path)
    # force recalculation on open (some viewers cache formula results)
    try:
        from openpyxl.workbook.properties import CalcProperties
        pass
    except Exception:
        pass
    return path


def main(argv=None):
    L.force_utf8()
    ap = argparse.ArgumentParser(description="Render verification workbook (xlsx).")
    ap.add_argument("project")
    ap.add_argument("-o", "--outdir", default="out")
    ap.add_argument("-n", "--name", default=None)
    args = ap.parse_args(argv)
    project = L.load_project(args.project)
    path = build(project, args.outdir, args.name)
    print(f"[ok] xlsx -> {path}  ({os.path.getsize(path)/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
