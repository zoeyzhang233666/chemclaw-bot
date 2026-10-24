"""把合同审查结果生成为 Excel 工作簿（通用，不依赖具体合同模板）。

用法:
    python build_review_xlsx.py --dir <案例目录> --out <输出.xlsx> [--author "…"]

工作表:
  00 使用说明与边界   审查口径、证据规则、缺失标记规则、业务/法律边界、版本
  01 条款索引         条款ID/章节/条号/页码/原文全文/风险编号/覆盖标记
  02 风险事项总表     36 列齐全：主题/类型/严重度/写了什么/缺什么/业务影响/后果/法规/办理人
  03 原文引用         每条风险的原文逐字摘录（可核对）
  04 法规标准核对     名称/适用点/状态/核验依据/来源链接/核对日期
  05 待确认清单       按风险拆到 法务/采购/供应商 三张
  06 采购待办         内部采购：优先级、经办、截止、状态
  07 法务待办
  08 供应商问题清单   可直接作为函件附件的表格
  09 统计           主题/类型/严重度分布 + 量级测算
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from common import excerpt, load_case, validate_case

INK = "0F3D5C"
GOLD = "F59E0B"
HEAD_FILL = PatternFill("solid", fgColor=INK)
BAND_FILL = PatternFill("solid", fgColor="F1F5F9")
WARN_FILL = PatternFill("solid", fgColor="FEF3C7")
MAIN_FILL = PatternFill("solid", fgColor="FFF7ED")
THIN = Side(style="thin", color="D6DEE6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
SEV_FILL = {5: "B91C1C", 4: "EA580C", 3: "FCD34D", 2: "BBF7D0", 1: "DBEAFE"}
SEV_FONT = {5: "FFFFFF", 4: "FFFFFF", 3: "7C2D12", 2: "14532D", 1: "1E3A8A"}
SEV_LABEL = {5: "极高", 4: "高", 3: "中", 2: "低", 1: "提示"}
OWNER_LABEL = {"legal": "法务", "procurement": "采购", "supplier": "供应商"}
PRI_FILL = {"高": "B91C1C", "中": "D97706", "低": "64748B"}

FINDING_COLS = [
    ("风险编号", 10), ("主题", 10), ("风险类型", 11), ("严重度(1-5)", 12), ("严重度", 8),
    ("风险标题", 46), ("引用条款ID", 18), ("条款编号", 26), ("页码", 7), ("原文位置", 22),
    ("合同写了什么", 58), ("未约定/未写清的内容", 50), ("业务风险与可能后果", 58),
    ("可能后果（分条）", 50), ("涉及法规/标准", 30), ("需确认事项（分条）", 50),
    ("建议办理部门", 20), ("待确认问题数", 10), ("状态", 12), ("备注", 24),
]


def style_header(ws, ncols: int, row: int = 1, height: float = 30) -> None:
    ws.row_dimensions[row].height = height
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEAD_FILL
        cell.font = Font(bold=True, color="FFFFFF", size=10, name="Microsoft YaHei")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def title_block(ws, title: str, sub: str, ncols: int) -> int:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=title)
    c.font = Font(bold=True, size=15, color="FFFFFF", name="Microsoft YaHei")
    c.fill = PatternFill("solid", fgColor=INK)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 32
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c = ws.cell(row=2, column=1, value=sub)
    c.font = Font(size=9.5, color="475569", name="Microsoft YaHei")
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 30
    return 3


def body_cell(cell, size: float = 9.5, wrap: bool = True, fill: str | None = None) -> None:
    cell.font = Font(size=size, name="Microsoft YaHei")
    cell.alignment = Alignment(vertical="top", wrap_text=wrap)
    cell.border = BORDER
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)


def add_status_dv(ws, first_row: int, last_row: int, col: int) -> None:
    dv = DataValidation(type="list", formula1='"待处理,已确认,待供应商回复,已解决,不适用"', allow_blank=True, showDropDown=False)
    dv.error = "请从下拉列表中选择状态"
    dv.prompt = "选择处理状态"
    ws.add_data_validation(dv)
    dv.add(f"{get_column_letter(col)}{first_row}:{get_column_letter(col)}{last_row}")


def sheet_guide(wb: Workbook, contract: dict, review: dict) -> None:
    ws = wb.create_sheet("00 使用说明与边界")
    ws.sheet_properties.tabColor = INK
    ws.sheet_view.showGridLines = False
    meta = contract.get("contract_meta", {})
    rm = review.get("review_meta", {})
    wb_widths = [26, 110]
    for i, w in enumerate(wb_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    rows: list[tuple[str, str]] = [
        ("文件性质", "业务审查提示（Business Review Notice），不是法律意见，不替代律师或法务的合同审查。"),
        ("合同名称", meta.get("title", "")),
        ("合同编号", meta.get("contract_no", "")),
        ("我方身份", meta.get("review_as", "")),
        ("供应商", meta.get("supplier", "")),
        ("签订日期", meta.get("sign_date", "")),
        ("审查日期", rm.get("review_date", "")),
        ("审查人", rm.get("reviewer", "")),
        ("合同状态", rm.get("signed", "")),
        ("审查范围", rm.get("review_scope", "")),
        ("数据截止", rm.get("data_cutoff", "") + "；法规/标准适用性核对日期 " + rm.get("law_check_date", "")),
        ("演示属性", "本工作簿所审合同为「虚构演示合同」：双方名称、金额、条款均为演示编写，不对应任何真实交易。" if contract.get("demo") else "真实合同"),
        ("", ""),
        ("【证据规则 1】逐字引用", "「原文引用」页的每一段都从合同文本逐字摘录，并在「条款索引」页提供全文；不得改写、拼接或推测原文。"),
        ("【证据规则 2】定位锚点", "每条风险必须带 条款ID + 条款编号 + 页码；找不到原文的发现不允许进入总表，只能写进「未覆盖/负结果」。"),
        ("【证据规则 3】缺失标记", "风险类型「缺失」表示合同中未见该约定。缺失只陈述「没有写」，不得推测合同「应该写什么」即视为已约定。"),
        ("【证据规则 4】业务影响", "业务影响必须落到「我方角色（买方/卖方）+ 标的物特性（危化品、大宗液体、散装、季节波动）+ 量级测算」，禁止空泛表述。"),
        ("【证据规则 5】法规适用性", "法规/标准必须核对现行状态与实施日期，标注来源与核对日期；不适用的不应列入，过期版本必须提示。"),
        ("【证据规则 6】不替当事人做决定", "只列待确认事项与建议办理人，不替采购/法务做最终商务或法律决定。"),
        ("", ""),
        ("业务提醒与法律意见的边界", "本工作簿说明「合同写了什么 / 哪些没写 / 可能产生什么业务后果 / 该找谁确认」。不评价条款效力，不给「有效/无效」「能赢/不能赢」的结论。"),
        ("必须由法务/律师判断的事项", "违约责任上限的效力、不可抗力条款的解释、质量异议期与免责条款的效力、仲裁条款效力与机构名称、最低采购承诺的认定、诉讼时效与证据保管。"),
        ("必须由业务部门判断的事项", "价格与调价机制是否可接受、预付款与押金规模是否可承受、供应保障与替代方案、进度与库存安排。"),
        ("必须向供应商核实的事项", "资质证照、承运方与罐体适装、批次检验报告与 SDS、押金与空桶返还、收款账户。"),
        ("", ""),
        ("交付物清单", "01 条款索引｜02 风险事项总表｜03 原文引用｜04 法规标准核对｜05 待确认清单｜06 采购待办｜07 法务待办｜08 供应商问题清单｜09 统计"),
        ("配套交付", "交互式 HTML 审查页面（原文 × 风险双栏、主题筛选、点击定位、处理状态与备注）；提交给供应商的问题清单可作为函件附件。"),
    ]
    r = title_block(ws, "合同风险审查 · 使用说明与审查边界", "本工作簿由 Skill「检查采购合同风险点」生成；所有结论可追溯到合同条款页码。", 2)
    for k, v in rows:
        ws.cell(row=r, column=1, value=k).font = Font(bold=True, size=10, name="Microsoft YaHei", color="0F3D5C" if k else "000000")
        ws.cell(row=r, column=1).alignment = Alignment(vertical="top", wrap_text=True)
        c = ws.cell(row=r, column=2, value=v)
        c.font = Font(size=9.5, name="Microsoft YaHei")
        c.alignment = Alignment(vertical="top", wrap_text=True)
        if k.startswith("【") or "边界" in k:
            ws.cell(row=r, column=1).fill = WARN_FILL
            c.fill = WARN_FILL
        ws.row_dimensions[r].height = max(16, 14 * (len(str(v)) // 60 + 1))
        r += 1
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=2)
    c = ws.cell(row=r + 1, column=1, value="免责声明：" + rm.get("disclaimer", ""))
    c.font = Font(size=9.5, color="881337", name="Microsoft YaHei")
    c.fill = PatternFill("solid", fgColor="FFF1F2")
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r + 1].height = 48


def sheet_index(wb: Workbook, contract: dict, review: dict) -> None:
    ws = wb.create_sheet("01 条款索引")
    ws.sheet_properties.tabColor = "155E75"
    clauses = contract["clauses"]
    secs = {s["id"]: s for s in contract["sections"]}
    hits: dict[str, list[str]] = {}
    for f in review["findings"]:
        for cid in f["clause_ids"]:
            hits.setdefault(cid, []).append(f["id"])
    cols = [("条款ID", 10), ("章节", 22), ("条款编号", 24), ("页码", 7), ("原文位置", 20),
            ("合同原文（逐字）", 95), ("关联风险", 22), ("被风险覆盖", 11)]
    r = title_block(ws, "01 条款索引 · 全文锚点", "条款ID 是本工作簿唯一的定位键；其余工作表的所有引用都能回到这里。", len(cols))
    for i, (h, w) in enumerate(cols, start=1):
        ws.cell(row=r, column=i, value=h)
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(cols), r)
    r += 1
    for c in clauses:
        sec = secs.get(c["sec"], {})
        vals = [c["id"], f'{sec.get("no","")} {sec.get("title","")}', c["no"], c["page"], c.get("page_line", ""),
                c["text"], ", ".join(sorted(hits.get(c["id"], []))) or "—", "是" if c["id"] in hits else "否"]
        for i, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            body_cell(cell)
            if i == 6:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        if c["id"] in hits:
            ws.cell(row=r, column=1).fill = WARN_FILL
        ws.row_dimensions[r].height = max(18, 13 * (len(c["text"]) // 55 + 1))
        r += 1
    ws.freeze_panes = ws.cell(row=4, column=1)
    ws.auto_filter.ref = f"A3:{get_column_letter(len(cols))}{r-1}"


def sheet_findings(wb: Workbook, contract: dict, review: dict) -> None:
    ws = wb.create_sheet("02 风险事项总表")
    ws.sheet_properties.tabColor = "B91C1C"
    clauses = {c["id"]: c for c in contract["clauses"]}
    topic_name = {t["id"]: t["name"] for t in review["topics"]}
    roles = review.get("roles", {})
    conf_count = Counter()
    for owner, items in review.get("confirmations", {}).items():
        for q in items:
            conf_count[q["finding_id"]] += 1
    r = title_block(ws, "02 风险事项总表", "逐条：写了什么 / 缺什么 / 业务后果 / 法规标准 / 办理部门 / 待确认问题数 / 处理状态。按严重度降序排列。", len(FINDING_COLS))
    for i, (h, w) in enumerate(FINDING_COLS, start=1):
        ws.cell(row=r, column=i, value=h)
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(FINDING_COLS), r, 34)
    first = r + 1
    r += 1
    order = sorted(review["findings"], key=lambda f: (-f["severity"], f["id"]))
    for f in order:
        cids = f["clause_ids"]
        owners = "、".join(roles.get(o, OWNER_LABEL.get(o, o)) for o in f.get("owner", []))
        vals = [
            f["id"], topic_name.get(f["topic"], f["topic"]), f["kind"], f["severity"], SEV_LABEL.get(f["severity"], ""),
            f["title"], ", ".join(cids), "; ".join(clauses[c]["no"] for c in cids if c in clauses),
            ", ".join(str(clauses[c]["page"]) for c in cids if c in clauses),
            "; ".join(clauses[c].get("page_line", "") for c in cids if c in clauses),
            f["what_written"], f.get("what_missing", ""), f["business_impact"],
            "\n".join(f"{i+1}. {x}" for i, x in enumerate(f.get("consequences", []))),
            ", ".join(f.get("law_refs", [])),
            "\n".join(f"{i+1}. {x}" for i, x in enumerate(f["to_confirm"])),
            owners, conf_count.get(f["id"], 0), "待处理", "",
        ]
        for i, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            body_cell(cell)
        ws.cell(row=r, column=1).font = Font(bold=True, size=9.5, name="Consolas", color="0F3D5C")
        ws.cell(row=r, column=6).font = Font(bold=True, size=9.5, name="Microsoft YaHei")
        sev_cell = ws.cell(row=r, column=5)
        sev_cell.fill = PatternFill("solid", fgColor=SEV_FILL[f["severity"]])
        sev_cell.font = Font(bold=True, size=9.5, color=SEV_FONT[f["severity"]], name="Microsoft YaHei")
        sev_cell.alignment = Alignment(horizontal="center", vertical="center")
        if f["kind"] == "缺失":
            ws.cell(row=r, column=3).fill = WARN_FILL
        ws.row_dimensions[r].height = 96
        r += 1
    last = r - 1
    add_status_dv(ws, first, last, 19)
    ws.freeze_panes = ws.cell(row=first, column=2)
    ws.auto_filter.ref = f"A{r-len(order)}:{get_column_letter(len(FINDING_COLS))}{last}"
    ws.conditional_formatting.add(f"D{first}:D{last}", ColorScaleRule(start_type="num", start_value=1, start_color="BBF7D0",
                                                                      mid_type="num", mid_value=3, mid_color="FCD34D",
                                                                      end_type="num", end_value=5, end_color="B91C1C"))


def sheet_quotes(wb: Workbook, contract: dict, review: dict) -> None:
    ws = wb.create_sheet("03 原文引用")
    ws.sheet_properties.tabColor = "7C3AED"
    clauses = {c["id"]: c for c in contract["clauses"]}
    topic_name = {t["id"]: t["name"] for t in review["topics"]}
    cols = [("风险编号", 10), ("主题", 10), ("引用条款ID", 12), ("条款编号", 22), ("页码", 7),
            ("原文位置", 20), ("原文摘录（逐字，不得改写）", 105), ("原文全文长度", 12)]
    r = title_block(ws, "03 原文引用 · 可核对的证据链", "每一段引用都可与「01 条款索引」中的全文比对；摘录过长时以「……」结尾，未做任何改写。", len(cols))
    for i, (h, w) in enumerate(cols, start=1):
        ws.cell(row=r, column=i, value=h)
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(cols), r)
    r += 1
    for f in sorted(review["findings"], key=lambda x: (-x["severity"], x["id"])):
        for cid in f["clause_ids"]:
            if cid not in clauses:
                continue
            c = clauses[cid]
            vals = [f["id"], topic_name.get(f["topic"], ""), cid, c["no"], c["page"], c.get("page_line", ""),
                    excerpt(c["text"], 300), len(c["text"])]
            for i, v in enumerate(vals, start=1):
                body_cell(ws.cell(row=r, column=i, value=v))
            ws.cell(row=r, column=7).fill = PatternFill("solid", fgColor="F8FAFC")
            ws.row_dimensions[r].height = max(18, 13 * (len(vals[6]) // 70 + 1))
            r += 1
    ws.freeze_panes = ws.cell(row=4, column=1)
    ws.auto_filter.ref = f"A3:{get_column_letter(len(cols))}{r-1}"


def sheet_laws(wb: Workbook, review: dict) -> None:
    ws = wb.create_sheet("04 法规标准核对")
    ws.sheet_properties.tabColor = "0E7490"
    cols = [("序号", 6), ("法规/标准", 46), ("适用点", 34), ("核验状态", 26), ("核验依据（来源+日期）", 60),
            ("与本合同的关联", 40), ("来源链接", 52), ("核对日期", 12), ("是否需签约前再核", 14)]
    r = title_block(ws, "04 法规标准适用性核对", "只回答「是否存在、是否现行、与本合同的关联点」，不据此对合同效力下结论。", len(cols))
    for i, (h, w) in enumerate(cols, start=1):
        ws.cell(row=r, column=i, value=h)
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(cols), r)
    r += 1
    check_date = review.get("review_meta", {}).get("law_check_date", date.today().isoformat())
    for i, x in enumerate(review.get("legal_refs", []), start=1):
        need = "否" if ("现行" in x["status"] and "未逐" not in x["status_basis"] and "修订动态" not in x["status_basis"]) else "是"
        vals = [i, x["name"], x["scope"], x["status"], x["status_basis"], x["relevance"], x["url"], check_date, need]
        for j, v in enumerate(vals, start=1):
            body_cell(ws.cell(row=r, column=j, value=v))
        st = ws.cell(row=r, column=4)
        ok = "现行" in x["status"] and "废止" not in x["status"]
        st.fill = PatternFill("solid", fgColor="DCFCE7" if ok else "FEF3C7")
        link = ws.cell(row=r, column=7)
        link.hyperlink = x["url"]
        link.font = Font(size=9, color="0B5CAD", underline="single", name="Microsoft YaHei")
        if need == "是":
            ws.cell(row=r, column=9).fill = WARN_FILL
        ws.row_dimensions[r].height = 46
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(cols))
    c = ws.cell(row=r, column=1, value="提示：强制性与推荐性标准（GB 与 GB/T）、行政法规与部门规章的效力层级不同；本合同是否须适用某项标准、标准更新后旧合同如何处理，属法律判断，请由法务确认。")
    c.font = Font(size=9, italic=True, color="881337", name="Microsoft YaHei")
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r].height = 32


def sheet_confirmations(wb: Workbook, contract: dict, review: dict) -> None:
    ws = wb.create_sheet("05 待确认清单")
    ws.sheet_properties.tabColor = "D97706"
    clauses = {c["id"]: c for c in contract["clauses"]}
    fmap = {f["id"]: f for f in review["findings"]}
    cols = [("编号", 7), ("类别", 12), ("办理人", 10), ("优先级", 8), ("关联风险", 10), ("风险标题", 46),
            ("需要确认的问题", 78), ("引用条款", 20), ("页码", 10), ("建议动作", 16), ("状态", 12)]
    r = title_block(ws, "05 待确认清单（合并视图）", "同一问题按办理方拆到 06/07/08 三张可执行清单；本页用于总览与筛选。", len(cols))
    for i, (h, w) in enumerate(cols, start=1):
        ws.cell(row=r, column=i, value=h)
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(cols), r)
    first = r + 1
    r += 1
    n = 0
    for owner, items in review.get("confirmations", {}).items():
        for q in sorted(items, key=lambda x: {"高": 0, "中": 1, "低": 2}[x["priority"]]):
            f = fmap[q["finding_id"]]
            n += 1
            vals = [f"Q{n:02d}", OWNER_LABEL.get(owner, owner), OWNER_LABEL.get(owner, owner), q["priority"],
                    f["id"], f["title"], q["question"], ", ".join(f["clause_ids"]),
                    ", ".join(str(clauses[c]["page"]) for c in f["clause_ids"] if c in clauses),
                    "发函确认" if owner == "supplier" else ("提交法务意见" if owner == "legal" else "内部决策"), "待处理"]
            for i, v in enumerate(vals, start=1):
                body_cell(ws.cell(row=r, column=i, value=v))
            pr = ws.cell(row=r, column=4)
            pr.fill = PatternFill("solid", fgColor=PRI_FILL[q["priority"]])
            pr.font = Font(bold=True, size=9.5, color="FFFFFF", name="Microsoft YaHei")
            pr.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[r].height = 34
            r += 1
    add_status_dv(ws, first, r - 1, 11)
    ws.freeze_panes = ws.cell(row=4, column=3)
    ws.auto_filter.ref = f"A3:{get_column_letter(len(cols))}{r-1}"


def sheet_owner(wb: Workbook, contract: dict, review: dict, owner: str, sheet_name: str, tab: str, intro: str) -> None:
    ws = wb.create_sheet(sheet_name)
    ws.sheet_properties.tabColor = tab
    clauses = {c["id"]: c for c in contract["clauses"]}
    fmap = {f["id"]: f for f in review["findings"]}
    items = sorted(review["confirmations"].get(owner, []), key=lambda x: {"高": 0, "中": 1, "低": 2}[x["priority"]])
    cols = [("序号", 6), ("优先级", 8), ("关联风险", 10), ("风险标题", 44), ("需要确认的问题", 74),
            ("引用条款", 22), ("页码", 10), ("经办人", 12), ("要求完成日期", 14), ("状态", 12), ("处理结果 / 依据文件", 40)]
    r = title_block(ws, sheet_name, intro, len(cols))
    for i, (h, w) in enumerate(cols, start=1):
        ws.cell(row=r, column=i, value=h)
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(cols), r)
    first = r + 1
    r += 1
    for i, q in enumerate(items, start=1):
        f = fmap[q["finding_id"]]
        vals = [i, q["priority"], f["id"], f["title"], q["question"], ", ".join(f["clause_ids"]),
                ", ".join(str(clauses[c]["page"]) for c in f["clause_ids"] if c in clauses), "", "", "待处理", ""]
        for j, v in enumerate(vals, start=1):
            body_cell(ws.cell(row=r, column=j, value=v))
        pr = ws.cell(row=r, column=2)
        pr.fill = PatternFill("solid", fgColor=PRI_FILL[q["priority"]])
        pr.font = Font(bold=True, size=9.5, color="FFFFFF", name="Microsoft YaHei")
        pr.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[r].height = 38
        r += 1
    # 汇总
    r += 1
    ws.cell(row=r, column=3, value="合计").font = Font(bold=True, name="Microsoft YaHei", size=10)
    ws.cell(row=r, column=4, value=f"{len(items)} 项（高 {sum(1 for q in items if q['priority']=='高')} / 中 {sum(1 for q in items if q['priority']=='中')} / 低 {sum(1 for q in items if q['priority']=='低')}）")
    add_status_dv(ws, first, first + len(items) - 1, 10)
    ws.freeze_panes = ws.cell(row=4, column=1)


def sheet_stats(wb: Workbook, contract: dict, review: dict, stats: dict) -> None:
    ws = wb.create_sheet("09 统计")
    ws.sheet_properties.tabColor = "334155"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 4
    ws.column_dimensions["D"].width = 34
    ws.column_dimensions["E"].width = 60
    r = title_block(ws, "09 统计与量级测算", "分布统计与金额测算；测算口径均来自合同原文数字，仅说明量级，不构成损失预测。", 5)
    r += 1
    ws.cell(row=r, column=1, value="按主题").font = Font(bold=True, size=11, color=INK, name="Microsoft YaHei")
    ws.cell(row=r, column=4, value="按风险类型").font = Font(bold=True, size=11, color=INK, name="Microsoft YaHei")
    ws.cell(row=r, column=5, value="说明").font = Font(bold=True, size=11, color=INK, name="Microsoft YaHei")
    r += 1
    topics = review["topics"]
    kinds = list(stats["kind"].items())
    sev = stats["severity"]
    maxrows = max(len(topics), len(kinds))
    for i in range(maxrows):
        if i < len(topics):
            t = topics[i]
            ws.cell(row=r + i, column=1, value=t["name"])
            ws.cell(row=r + i, column=2, value=stats["topic"].get(t["id"], 0))
        if i < len(kinds):
            ws.cell(row=r + i, column=4, value=kinds[i][0])
            ws.cell(row=r + i, column=5, value=kinds[i][1])
    for rr in range(r, r + maxrows):
        for cc in (1, 2, 4, 5):
            c = ws.cell(row=rr, column=cc)
            c.border = BORDER
            c.font = Font(size=9.5, name="Microsoft YaHei")
            c.alignment = Alignment(horizontal="center" if cc in (2, 5) else "left", vertical="center")
    r = r + maxrows + 1
    ws.cell(row=r, column=1, value="按严重度").font = Font(bold=True, size=11, color=INK, name="Microsoft YaHei")
    r += 1
    for k in (5, 4, 3, 2, 1):
        if sev.get(k):
            ws.cell(row=r, column=1, value=f"{SEV_LABEL[k]}（{k}）")
            ws.cell(row=r, column=2, value=sev[k]).alignment = Alignment(horizontal="center")
            ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=SEV_FILL[k])
            ws.cell(row=r, column=1).font = Font(size=9.5, bold=True, color=SEV_FONT[k], name="Microsoft YaHei")
            r += 1
    r += 1
    calc = review.get("summary", {}).get("calc_basis", {})
    if calc:
        ws.cell(row=r, column=1, value="量级测算").font = Font(bold=True, size=11, color=INK, name="Microsoft YaHei")
        r += 1
        pairs = [
            ("年度吨量", calc.get("annual_tonnage"), "按合同 1.1 条"),
            ("含税单价（元/吨）", calc.get("unit_price"), "按合同 4.1 条"),
            ("合同总额（元）", calc.get("contract_value"), "吨量 × 单价（合同原文数字）"),
            ("责任上限 5%（元）", calc.get("liability_cap_5pct"), "按合同 7.4 条责任上限比例测算"),
            ("浓度差 2% 对应有效 NaOH（吨）", (calc.get("annual_tonnage") or 0) * 0.02, "2,000 吨 × (32%-30%)，用于说明浓度口径差异的量级"),
            ("浓度差对应货款（元）", (calc.get("annual_tonnage") or 0) * 0.02 * (calc.get("unit_price") or 0), "同上，按本次单价折算"),
            ("吨桶押金规模（元）", 2000 * 300, "按 1,000 kg/桶包装 2,000 吨 × 300 元/只测算（合同未约定只数）"),
            ("甲方逾期付款日违约金（元/日）", round((calc.get("contract_value") or 0) * 0.001), "按 5.2 条 0.1%/日 × 合同总额"),
        ]
        for k, v, note in pairs:
            ws.cell(row=r, column=1, value=k).font = Font(size=9.5, name="Microsoft YaHei")
            c = ws.cell(row=r, column=2, value=v)
            c.number_format = "#,##0"
            c.font = Font(size=10, bold=True, color=INK, name="Microsoft YaHei")
            c.alignment = Alignment(horizontal="right")
            n = ws.cell(row=r, column=3, value=note)
            ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
            n.font = Font(size=9, color="64748B", name="Microsoft YaHei")
            for cc in range(1, 6):
                ws.cell(row=r, column=cc).border = BORDER
            r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        c = ws.cell(row=r, column=1, value=calc.get("note", ""))
        c.font = Font(size=9, italic=True, color="881337", name="Microsoft YaHei")
        c.alignment = Alignment(wrap_text=True)
        ws.row_dimensions[r].height = 30
    r += 2
    uncovered = stats.get("uncovered", [])
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws.cell(row=r, column=1, value=("未被任何风险条目引用的条款：" + (", ".join(uncovered) if uncovered else "无（全部条款均已覆盖）")))
    c.font = Font(size=9, color="475569", name="Microsoft YaHei")


def build(case_dir: Path, out: Path, author: str = "检查采购合同风险点 Skill") -> dict:
    case = load_case(case_dir)
    contract, review = case["contract"], case["review"]
    check = validate_case(contract, review)
    if check["errors"]:
        raise SystemExit("数据校验失败:\n  " + "\n  ".join(check["errors"]))
    wb = Workbook()
    wb.remove(wb.active)
    sheet_guide(wb, contract, review)
    sheet_index(wb, contract, review)
    sheet_findings(wb, contract, review)
    sheet_quotes(wb, contract, review)
    sheet_laws(wb, review)
    sheet_confirmations(wb, contract, review)
    sheet_owner(wb, contract, review, "procurement", "06 采购待办", "1D4ED8",
                "内部采购负责：商务谈判、供应保障、订单与审批管控、供应商资质收集。")
    sheet_owner(wb, contract, review, "legal", "07 法务待办", "9333EA",
                "提交法务/律师：条款效力、责任分配、不可抗力与争议解决。本表是问题提交单，不是法律意见。")
    sheet_owner(wb, contract, review, "supplier", "08 供应商问题清单", "0F766E",
                "可直接作为函件/会议附件的供应商确认清单；确认结果需书面回签，作为合同附件或补充协议依据。")
    sheet_stats(wb, contract, review, check["stats"])
    wb.properties.creator = author
    wb.properties.title = f'{contract["contract_meta"].get("title", "")} · 合同风险审查'
    wb.properties.subject = "业务审查提示，不构成法律意见"
    wb.properties.keywords = "内贸采购,合同审查,风险点,条款索引"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return {"out": str(out), "sheets": wb.sheetnames, "findings": len(review["findings"]), "warnings": check["warnings"]}


def main() -> None:
    ap = argparse.ArgumentParser(description="生成合同审查 Excel 工作簿")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--author", default="检查采购合同风险点 Skill")
    a = ap.parse_args()
    info = build(Path(a.dir), Path(a.out), a.author)
    print(json.dumps({"ok": True, **info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
