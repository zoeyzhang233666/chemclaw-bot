"""把外贸采购合同审查结果生成为 Excel 工作簿（通用，不依赖具体合同）。

用法:
    python build_review_xlsx.py --dir <案例目录> --out <输出.xlsx> [--author "…"]

工作表:
  00 使用说明与边界   文件性质、边界、证据规则、缺失标记规则、版本
  01 条款索引         条款ID/章节/编号/页码/位置/原文/中文对照/关联风险/是否覆盖
  02 风险事项总表     主题/类型/严重度/原文/中文解释/缺失/业务影响/后果/法规/办理人/状态/负责人/供应商反馈
  03 原文引用         每条风险的逐字引用（可核对），含引用是否逐字校验
  04 法规核对         名称/适用点/状态/核验依据/关联/来源/核对日期
  05 待确认清单       法务 / 采购 / 供应商 三张清单（中英对照）
  06 中英对照问题清单  可直接交给供应商的英文问题清单（中文原文 + English）
  07 条款修改建议草稿  以「澄清/修改要求」形式表述的建议条款方向（非最终条款）
  08 统计             主题/类型/严重度分布 + 量级测算
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from common import (KIND_ORDER, STATUSES, clause_locator, excerpt, load_case,
                    validate_case)

INK = "0F3D5C"
HEAD_FILL = PatternFill("solid", fgColor=INK)
WARN_FILL = PatternFill("solid", fgColor="FEF3C7")
RED_FILL = PatternFill("solid", fgColor="FEE2E2")
THIN = Side(style="thin", color="D6DEE6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
SEV_FILL = {5: "B91C1C", 4: "EA580C", 3: "FCD34D", 2: "BBF7D0", 1: "DBEAFE"}
SEV_FONT = {5: "FFFFFF", 4: "FFFFFF", 3: "7C2D12", 2: "14532D", 1: "1E3A8A"}
SEV_LABEL = {5: "极高", 4: "高", 3: "中", 2: "低", 1: "提示"}
KIND_FILL = {"缺失": "FEF3C7", "表述不清": "DBEAFE", "写了但对我方不利": "FEE2E2"}
PRI_FILL = {"高": "B91C1C", "中": "D97706", "低": "64748B"}
YH = "Microsoft YaHei"


def style_header(ws, ncols: int, row: int = 1, height: float = 30) -> None:
    ws.row_dimensions[row].height = height
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEAD_FILL
        cell.font = Font(bold=True, color="FFFFFF", size=9.5, name=YH)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def title_block(ws, title: str, sub: str, ncols: int) -> int:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=title)
    c.font = Font(bold=True, size=14, color="FFFFFF", name=YH)
    c.fill = PatternFill("solid", fgColor=INK)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c = ws.cell(row=2, column=1, value=sub)
    c.font = Font(size=9, color="475569", name=YH)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 28
    return 3


def body_cell(cell, size: float = 9, wrap: bool = True, fill: str | None = None, mono: bool = False) -> None:
    cell.font = Font(size=size, name="Consolas" if mono else YH)
    cell.alignment = Alignment(vertical="top", wrap_text=wrap)
    cell.border = BORDER
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)


def header_row(ws, cols: list[tuple[str, int]], r: int) -> None:
    for i, (h, w) in enumerate(cols, start=1):
        ws.cell(row=r, column=i, value=h)
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(cols), r, 32)


# ---------------------------------------------------------------------------
def sheet_guide(wb, contract, review):
    ws = wb.create_sheet("00 使用说明与边界")
    ws.sheet_properties.tabColor = INK
    ws.sheet_view.showGridLines = False
    meta, rm = contract["contract_meta"], review["review_meta"]
    for i, w in enumerate([30, 118], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    rows = [
        ("文件性质", "外贸采购合同业务审查提示（Business Review Notice）。不是法律意见，不替代律师或公司法务的审查。"),
        ("合同名称", meta.get("title", "")),
        ("合同编号", meta.get("contract_no", "")),
        ("我方身份", meta.get("review_as", "")),
        ("对方（供应商）", meta.get("supplier", "")),
        ("标的", str(meta.get("product", ""))),
        ("贸易术语", f'{meta.get("incoterms", {}).get("rule", "")} {meta.get("incoterms", {}).get("place", "")} Incoterms® {meta.get("incoterms", {}).get("year", "")}'),
        ("签订日期", meta.get("sign_date", "")),
        ("审查日期 / 法规核对日期", f'{rm.get("review_date", "")} / {rm.get("law_check_date", "")}'),
        ("合同状态", rm.get("signed", "")),
        ("审查范围", rm.get("review_scope", "")),
        ("演示属性", "本工作簿所审合同为「模拟合同」：双方名称、地址、金额、条款均为演示编写，不对应任何真实交易或主体。" if contract.get("demo") else "真实合同"),
        ("", ""),
        ("【规则1】逐字引用", "03 原文引用页每一段都取自合同原文，且由脚本硬校验为对应条款的逐字子串；不得改写、拼接或推测。"),
        ("【规则2】可定位", "每条风险必须带条款ID + 条款编号 + 页码，可在 01 条款索引页核对全文。"),
        ("【规则3】缺失即缺失", "风险类型「缺失」表示全文未见该约定。缺失只说明「没有写」，不推断「应该写什么」就等于已约定。"),
        ("【规则4】后果要落地", "业务影响须落到「中国买方/进口商角色 + 进口环节 + 量级」，含数字时必须写明测算口径。"),
        ("【规则5】法规须核适用", "法规/规则/标准注明现行状态、核验依据与核对日期；未核对项明确标注，正式签约前须复核权威渠道。"),
        ("【规则6】不给法律结论", "不评价条款有效/无效、不判断胜诉可能；仲裁地与准据法等须由法务/律师判断。"),
        ("", ""),
        ("商务审查可以做的", "说明合同写了什么、哪些没写、口径冲突在哪、可能产生的采购与进口业务后果、建议向谁确认什么；给出可执行的清单与英文澄清函草稿。"),
        ("必须由法务/律师判断的", "条款效力、违约责任上限可否突破、仲裁条款是否有效、合同解释规则、CISG 与准据法的适用、危险化学品的法律定性、承认与执行。"),
        ("必须由业务部门判断的", "预付款与担保的商业底线、开证与付款审批、供应保障与替代方案、检验周期与检测费用、报价与到厂成本。"),
        ("必须向供应商核实的", "实际生产商、资质证照、SDS 与规格版本、提单与保险安排、收款账户与担保安排。"),
        ("", ""),
        ("工作表清单", "01 条款索引｜02 风险事项总表｜03 原文引用｜04 法规核对｜05 待确认清单｜06 中英对照问题清单｜07 条款修改建议草稿｜08 统计"),
        ("配套交付", "交互式 HTML 审阅页（左原文 × 右中文解释/风险/待确认，可筛选、定位、填写负责人/状态/反馈，可导出中英对照 CSV 与英文澄清函）；中英对照合同 DOCX；英文澄清函 TXT。"),
    ]
    r = title_block(ws, "外贸采购合同审阅 · 使用说明与审查边界",
                    "本工作簿由 Skill「审阅外贸采购合同」生成；所有结论可追溯到合同条款与页码。", 2)
    for k, v in rows:
        a = ws.cell(row=r, column=1, value=k)
        a.font = Font(bold=True, size=9.5, name=YH, color=INK if k else "000000")
        a.alignment = Alignment(vertical="top", wrap_text=True)
        c = ws.cell(row=r, column=2, value=v)
        c.font = Font(size=9, name=YH)
        c.alignment = Alignment(vertical="top", wrap_text=True)
        if k.startswith("【") or "边界" in k or k in ("商务审查可以做的", "必须由法务/律师判断的"):
            a.fill = WARN_FILL
            c.fill = WARN_FILL
        ws.row_dimensions[r].height = max(15, 13 * (len(str(v)) // 62 + 1))
        r += 1
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=2)
    c = ws.cell(row=r + 1, column=1, value="免责声明：" + rm.get("disclaimer", ""))
    c.font = Font(size=9, color="881337", name=YH)
    c.fill = PatternFill("solid", fgColor="FFF1F2")
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r + 1].height = 60


def sheet_index(wb, contract, review):
    ws = wb.create_sheet("01 条款索引")
    ws.sheet_properties.tabColor = "155E75"
    secs = {s["id"]: s for s in contract["sections"]}
    hits: dict[str, list[str]] = {}
    for f in review["findings"]:
        hits.setdefault(f["id"], [])
        for cid in f["clause_ids"]:
            hits.setdefault(cid, []).append(f["id"])
    cols = [("条款ID", 10), ("章节", 20), ("条款编号", 18), ("页码", 6), ("原文位置", 18),
            ("合同原文（英文，逐字）", 88), ("中文对照", 60), ("关联风险", 20), ("是否被审查覆盖", 12)]
    r = title_block(ws, "01 条款索引 · 全文锚点", "条款ID 是本工作簿唯一定位键；其余各表的所有引用都可回到这一页核对全文。", len(cols))
    header_row(ws, cols, r)
    r += 1
    for c in contract["clauses"]:
        sec = secs.get(c["sec"], {})
        vals = [c["id"], f'{sec.get("no", "")} {sec.get("title", "")}', c["no"], c["page"],
                c.get("page_line", ""), c["text"], c.get("zh", ""),
                ", ".join(sorted(hits.get(c["id"], []))) or "—",
                "是" if hits.get(c["id"]) else ("—（附件行，见关联条款）" if c.get("kind") else "否")]
        for i, v in enumerate(vals, start=1):
            body_cell(ws.cell(row=r, column=i, value=v), mono=(i == 1))
        if hits.get(c["id"]):
            ws.cell(row=r, column=1).fill = WARN_FILL
        ws.row_dimensions[r].height = max(17, 12.5 * (max(len(c["text"]) / 62, len(c.get("zh", "")) / 42) + 1))
        r += 1
    ws.freeze_panes = ws.cell(row=4, column=1)
    ws.auto_filter.ref = f"A3:{get_column_letter(len(cols))}{r - 1}"


FINDING_COLS = [
    ("风险编号", 9), ("主题", 9), ("风险类型", 10), ("严重度", 7), ("严重度说明", 9),
    ("风险标题", 34), ("引用条款ID", 14), ("条款编号", 20), ("页码", 7), ("原文位置", 16),
    ("合同原文（逐字摘录）", 52), ("合同写了什么（中文解释）", 50), ("未约定 / 未写清晰的内容", 44),
    ("对中国买方的商务后果", 52), ("可能后果（分条）", 40), ("测算口径", 30), ("涉及法规/规则/标准", 26),
    ("需确认事项（分条）", 44), ("建议办理部门", 18), ("待确认问题数", 9),
    ("内部负责人", 12), ("处理状态", 12), ("供应商反馈", 26), ("备注", 20),
]


def sheet_findings(wb, contract, review):
    ws = wb.create_sheet("02 风险事项总表")
    ws.sheet_properties.tabColor = "B91C1C"
    clauses = {c["id"]: c for c in contract["clauses"]}
    topic_name = {t["id"]: t["name"] for t in review["topics"]}
    roles = review.get("roles", {})
    conf_count = Counter()
    for items in review.get("confirmations", {}).values():
        for q in items:
            conf_count[q["finding_id"]] += 1
    r = title_block(ws, "02 风险事项总表",
                    "逐条：原文 / 中文解释 / 缺失 / 商务后果 / 法规 / 办理人 / 状态。按「缺失→表述不清→对我方不利」再按严重度排序。"
                    "严重度 5=极高、4=高、3=中、2=低。", len(FINDING_COLS))
    header_row(ws, FINDING_COLS, r)
    first = r + 1
    r += 1
    order = sorted(review["findings"], key=lambda f: (KIND_ORDER[f["kind"]], -f["severity"], f["id"]))
    for f in order:
        cids = f["clause_ids"]
        q = f.get("quotes", [])
        quote_txt = "\n".join(f"「{x['text']}」" for x in q) if q else "（全文未见该事项约定）"
        owners = "、".join(roles.get(o, o) for o in f.get("owner", []))
        vals = [
            f["id"], topic_name.get(f["topic"], f["topic"]), f["kind"], f["severity"],
            SEV_LABEL.get(f["severity"], ""), f["title"], ", ".join(cids),
            "; ".join(clauses[c]["no"] for c in cids if c in clauses),
            ", ".join(str(clauses[c]["page"]) for c in cids if c in clauses),
            "; ".join(clauses[c].get("page_line", "") for c in cids if c in clauses),
            quote_txt, f["what_written"], f.get("what_missing", ""), f["business_impact"],
            "\n".join(f"{i + 1}. {x}" for i, x in enumerate(f.get("consequences", []))),
            f.get("impact_basis", ""), ", ".join(f.get("law_refs", [])),
            "\n".join(f"{i + 1}. {x}" for i, x in enumerate(f["to_confirm"])),
            owners, conf_count.get(f["id"], 0), f.get("owner_internal", ""),
            f.get("status", "待处理"), f.get("supplier_feedback", ""), "",
        ]
        for i, v in enumerate(vals, start=1):
            body_cell(ws.cell(row=r, column=i, value=v), mono=(i in (1, 7)))
        ws.cell(row=r, column=6).font = Font(bold=True, size=9, name=YH)
        sc = ws.cell(row=r, column=5)
        sc.fill = PatternFill("solid", fgColor=SEV_FILL[f["severity"]])
        sc.font = Font(bold=True, size=9, color=SEV_FONT[f["severity"]], name=YH)
        sc.alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=r, column=3).fill = PatternFill("solid", fgColor=KIND_FILL[f["kind"]])
        ws.cell(row=r, column=11).fill = PatternFill("solid", fgColor="F8FAFC")
        ws.row_dimensions[r].height = 88
        r += 1
    last = r - 1
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True, showDropDown=False)
    dv.prompt = "选择处理状态"
    dv.error = "请从下拉列表选择"
    ws.add_data_validation(dv)
    dv.add(f"V{first}:V{last}")
    ws.freeze_panes = ws.cell(row=first, column=2)
    ws.auto_filter.ref = f"A{first - 1}:{get_column_letter(len(FINDING_COLS))}{last}"
    ws.conditional_formatting.add(f"D{first}:D{last}", ColorScaleRule(
        start_type="num", start_value=1, start_color="BBF7D0",
        mid_type="num", mid_value=3, mid_color="FCD34D",
        end_type="num", end_value=5, end_color="B91C1C"))


def sheet_quotes(wb, contract, review):
    ws = wb.create_sheet("03 原文引用")
    ws.sheet_properties.tabColor = "7C3AED"
    clauses = {c["id"]: c for c in contract["clauses"]}
    topic_name = {t["id"]: t["name"] for t in review["topics"]}
    cols = [("风险编号", 9), ("主题", 9), ("引用条款ID", 11), ("条款编号", 20), ("页码", 6),
            ("原文位置", 17), ("原文（逐字，不得改写）", 95), ("中文对照", 55), ("逐字校验", 10)]
    r = title_block(ws, "03 原文引用 · 可核对的证据链",
                    "每段引用均可在「01 条款索引」核对全文；「逐字校验」= 已由脚本确认为对应条款原文的连续子串。", len(cols))
    header_row(ws, cols, r)
    r += 1
    for f in sorted(review["findings"], key=lambda x: (-x["severity"], x["id"])):
        for q in f.get("quotes", []):
            cid = q["clause_id"]
            c = clauses.get(cid)
            if not c:
                continue
            vals = [f["id"], topic_name.get(f["topic"], ""), cid, c["no"], c["page"],
                    c.get("page_line", ""), q["text"], c.get("zh", ""), "✔ 是"]
            for i, v in enumerate(vals, start=1):
                body_cell(ws.cell(row=r, column=i, value=v), mono=(i in (1, 3)))
            ws.cell(row=r, column=7).fill = PatternFill("solid", fgColor="F8FAFC")
            ws.cell(row=r, column=9).fill = PatternFill("solid", fgColor="DCFCE7")
            ws.row_dimensions[r].height = max(17, 12.5 * (max(len(q["text"]) / 66, len(c.get("zh", "")) / 40) + 1))
            r += 1
    # 无引用（缺失类）
    for f in review["findings"]:
        if not f.get("quotes"):
            vals = [f["id"], topic_name.get(f["topic"], ""), ", ".join(f["clause_ids"]),
                    "—", "—", "—", "（全文检索未见对应约定，故不引用原文；仅以条款锚点标注相关位置）", f.get("what_missing", ""), "— 不适用"]
            for i, v in enumerate(vals, start=1):
                body_cell(ws.cell(row=r, column=i, value=v), mono=(i in (1, 3)))
            ws.cell(row=r, column=7).fill = WARN_FILL
            ws.row_dimensions[r].height = 40
            r += 1
    ws.freeze_panes = ws.cell(row=4, column=1)
    ws.auto_filter.ref = f"A3:{get_column_letter(len(cols))}{r - 1}"


def sheet_laws(wb, review):
    ws = wb.create_sheet("04 法规核对")
    ws.sheet_properties.tabColor = "0E7490"
    cols = [("序号", 6), ("法规 / 规则 / 标准", 44), ("适用点", 30), ("核验状态", 20),
            ("核验依据（来源 + 核对日期）", 44), ("与本合同的关联", 48), ("来源链接", 40), ("核对日期", 12)]
    r = title_block(ws, "04 法规核对 · 适用性须由法务/合规确认",
                    "本表只说明「是否存在、是否现行、与本合同哪一条相关」，并注明核验依据；不据此对合同效力下结论。", len(cols))
    header_row(ws, cols, r)
    r += 1
    for i, x in enumerate(review.get("legal_refs", []), start=1):
        vals = [i, x["name"], x["scope"], x["status"], x["status_basis"], x["relevance"], x["url"],
                review["review_meta"].get("law_check_date", "")]
        for j, v in enumerate(vals, start=1):
            body_cell(ws.cell(row=r, column=j, value=v), mono=(j == 1))
        link = ws.cell(row=r, column=7)
        link.hyperlink = x["url"]
        link.font = Font(size=8.5, color="0B5CAD", underline="single", name=YH)
        if "现行" in x["status"]:
            ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor="DCFCE7")
        else:
            ws.cell(row=r, column=4).fill = WARN_FILL
        ws.row_dimensions[r].height = max(17, 12.5 * (len(x["status_basis"]) / 34 + 1))
        r += 1
    ws.freeze_panes = ws.cell(row=4, column=1)


OWNER_TITLE = {"legal": "公司法务", "procurement": "采购/进口", "supplier": "海外供应商"}
PRI_ORDER = {"高": 0, "中": 1, "低": 2}


def sheet_confirmations(wb, contract, review):
    ws = wb.create_sheet("05 待确认清单")
    ws.sheet_properties.tabColor = "B45309"
    fmap = {f["id"]: f for f in review["findings"]}
    clauses = {c["id"]: c for c in contract["clauses"]}
    cols = [("办理方", 11), ("风险编号", 9), ("优先级", 7), ("风险标题", 30), ("条款", 18),
            ("需要确认的问题", 54), ("经办人", 12), ("要求完成日", 12), ("状态", 12), ("回复/结论", 28)]
    r = title_block(ws, "05 待确认清单 · 法务 / 采购 / 供应商",
                    "同一批风险按「谁去办」拆分。供应商一栏只问事实、文件与承诺，可直接对外发送。", len(cols))
    header_row(ws, cols, r)
    first = r + 1
    r += 1
    order = ["legal", "procurement", "supplier"]
    for owner in order:
        items = review.get("confirmations", {}).get(owner, [])
        for q in sorted(items, key=lambda x: (PRI_ORDER[x["priority"]], x["finding_id"])):
            f = fmap[q["finding_id"]]
            vals = [OWNER_TITLE.get(owner, owner), f["id"], q["priority"], f["title"],
                    ", ".join(f"{clauses[c]['no']} P{clauses[c]['page']}" for c in f["clause_ids"] if c in clauses),
                    q["question"], "", "", "待处理", ""]
            for j, v in enumerate(vals, start=1):
                body_cell(ws.cell(row=r, column=j, value=v), mono=(j == 2))
            pc = ws.cell(row=r, column=3)
            pc.fill = PatternFill("solid", fgColor=PRI_FILL[q["priority"]])
            pc.font = Font(bold=True, size=9, color="FFFFFF", name=YH)
            pc.alignment = Alignment(horizontal="center", vertical="center")
            if owner == "supplier":
                ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor="E0F2FE")
            ws.row_dimensions[r].height = 34
            r += 1
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True, showDropDown=False)
    ws.add_data_validation(dv)
    dv.add(f"I{first}:I{r - 1}")
    ws.freeze_panes = ws.cell(row=first, column=1)
    ws.auto_filter.ref = f"A{first - 1}:{get_column_letter(len(cols))}{r - 1}"


def sheet_bilingual(wb, review):
    ws = wb.create_sheet("06 中英对照问题清单")
    ws.sheet_properties.tabColor = "1D4ED8"
    cols = [("序号", 6), ("风险编号", 9), ("优先级", 7), ("风险标题（中文）", 34),
            ("Risk issue (English)", 44), ("需确认事项（中文）", 40),
            ("Question to Supplier (English)", 56), ("状态", 10)]
    r = title_block(ws, "06 中英对照问题清单 · 可直接作为澄清函附件",
                    "英文列已按对外函件口径撰写（只问事实/文件/承诺，不含法律结论）；发出前由采购与法务确认。", len(cols))
    header_row(ws, cols, r)
    first = r + 1
    r += 1
    items = review.get("confirmations", {}).get("supplier", [])
    for i, q in enumerate(sorted(items, key=lambda x: (PRI_ORDER[x["priority"]], x["finding_id"])), start=1):
        f = {x["id"]: x for x in review["findings"]}[q["finding_id"]]
        vals = [i, f["id"], q["priority"], f["title"], f.get("title_en", ""), q["question"],
                q.get("question_en", ""), "待处理"]
        for j, v in enumerate(vals, start=1):
            body_cell(ws.cell(row=r, column=j, value=v), mono=(j == 2))
        pc = ws.cell(row=r, column=3)
        pc.fill = PatternFill("solid", fgColor=PRI_FILL[q["priority"]])
        pc.font = Font(bold=True, size=9, color="FFFFFF", name=YH)
        pc.alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=r, column=5).font = Font(size=9, name="Segoe UI", italic=False)
        ws.cell(row=r, column=7).font = Font(size=9, name="Segoe UI")
        ws.row_dimensions[r].height = 40
        r += 1
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True, showDropDown=False)
    ws.add_data_validation(dv)
    dv.add(f"H{first}:H{r - 1}")
    ws.freeze_panes = ws.cell(row=first, column=1)
    ws.auto_filter.ref = f"A{first - 1}:{get_column_letter(len(cols))}{r - 1}"


# 修改方向草稿：以「澄清/修改要求」表述，不写成最终条款，留给法务与谈判
AMEND = {
    "R01": ("确认能否以银行预付款保函（金额≥预付款、有效期至装运后 60 天）替代或补充第 8.1 条；明确预付款退还的触发情形与期限。", "删除或限定「non-refundable」表述。"),
    "R02": ("明确开证行（买方账户行）、通知行（卖方银行）、可用性、到期日与到期地、最迟装运日、最迟交单期。", "修正「issued at the Seller's bank」。"),
    "R03": ("统一尾款付款路径：信用证凭单付款 或 到货验收后电汇，二选一；并明确检验/验收的法律地位（索赔依据 vs 拒付依据）。", "删除冲突条款。"),
    "R04": ("将单据清单改为穷尽式；明确提单份数、抬头、通知方、运费标志，排除租船提单与货代提单。", "删除 (g) 兜底项。"),
    "R05": ("补充开证延误、改证/展期、银行费用分担、不符点处理时限。", "新增条款。"),
    "R06": ("以双方确认的固定规格（含数值与方法版本）替代「卖方标准规格」；规格变更须买方书面同意。", "修改第 2.1 条。"),
    "R07": ("补齐水分试验方法与色度/浊度限值；锁定 ASTM 标准版本年份。", "修改附件 1。"),
    "R08": ("CAS 号更正为 107-21-1；明确纯度基准（% m/m 或 mol%）。", "修改第 3.1 条与附件 1。"),
    "R09": ("异议期延长至卸货完毕并取样封存后 30 日内；起算点与延长机制明确；数量与质量分别设期。", "修改第 9.1 条。"),
    "R10": ("允许买方独立取样并共同封样；卖方 COA 仅作初步证据；两家机构结论冲突时的复议机制。", "修改第 2.2、9.1、9.3 条。"),
    "R11": ("约定目的港短量允差（如 0.5%）、赔偿口径与所需单据；明确破损/泄漏责任。", "新增条款。"),
    "R12": ("增加降价接受、退货、就地处置与解约条款；明确拒收货物滞港/罐租费用承担。", "修改第 9.2 条。"),
    "R13": ("约定取样主体、封样与留样期限（≥6 个月）、复检机构与费用分担。", "新增条款。"),
    "R14": ("风险转移按 Incoterms 2020 CIF 于装船时转移。", "修改第 10.1 条。"),
    "R15": ("所有权转移时点与风险转移衔接；明确目的港 THC 等费用归属。", "修改第 10.2 条。"),
    "R16": ("保险以买方为被保险人/受益人，升级 ICC(A) 或附加污染/混合条款，保单作为交单文件。", "修改第 10.3 条。"),
    "R17": ("以固定装运窗口 + 最迟装船日替代「收到预付款后 45 天」。", "修改第 6.1 条。"),
    "R18": ("转运需买方书面同意；提单须为全式非租船、可转让提单；装运前船期预确认。", "修改第 6.2、6.3 条。"),
    "R19": ("违约金提高到 0.1%/天、上限 10%；超过 30 天买方有权解约并收回预付款。", "修改第 11.1 条。"),
    "R20": ("责任上限提高至合同金额；增加欺诈/故意/造假等例外；滞期与仓储不作排除项。", "修改第 11.2 条。"),
    "R21": ("保密义务设期限与法定披露例外，并对称适用于卖方。", "修改第 11.3 条。"),
    "R22": ("删去商业性事由（市场价格、设备故障、原料短缺）；增加通知、证明与持续 60 天解约机制。", "修改第 12.1 条。"),
    "R23": ("仲裁地、仲裁庭人数、仲裁语言、临时措施受理法院明确；删除「准据法优先」兜底。", "修改第 13.1 条，须法务起草。"),
    "R24": ("删除或限定为「无争议款项」及指定法院。", "修改第 13.2 条。"),
    "R25": ("明确 CISG 适用或排除；增加调解前置与费用败诉方承担。", "修改第 13.1 条。"),
    "R26": ("中文文本为准（至少对仲裁协议与责任条款）；明确译文提供方与纠错机制。", "修改第 14.1 条。"),
    "R27": ("将卖方标准规格作为附件并入并锁定版本；明确书面技术文件构成附件。", "修改第 14.2 条。"),
    "R28": ("SDS 提交时点、GHS 版本、语言；中文安全标签由卖方提供；危险货物申报的书面确认。", "修改第 7.1、7.2 条。"),
    "R29": ("卖方在约定时限内配合提供办证材料；政策调整时的处理机制。", "修改第 7.2 条。"),
    "R30": ("写明实际生产商；增加出口管制/制裁/反商业贿赂声明与母公司担保。", "新增条款。"),
}


def sheet_amend(wb, review):
    ws = wb.create_sheet("07 条款修改建议草稿")
    ws.sheet_properties.tabColor = "9333EA"
    cols = [("风险编号", 9), ("严重度", 7), ("条款", 22), ("现状（合同原文摘要）", 50),
            ("澄清 / 修改要求（建议方向，非最终条款）", 56), ("修改方式", 30), ("法务确认", 12), ("谈判优先级", 12)]
    r = title_block(ws, "07 条款修改建议草稿",
                    "仅列出「需要对方澄清或修改的方向」，不是正式条款文本；最终措辞由法务/律师起草，商务条件由采购决定。", len(cols))
    header_row(ws, cols, r)
    r += 1
    fmap = {f["id"]: f for f in review["findings"]}
    for fid, (direction, how) in AMEND.items():
        f = fmap.get(fid)
        if not f:
            continue
        qs = f.get("quotes", [])
        current = excerpt(qs[0]["text"], 180) if qs else "（无对应约定）"
        vals = [fid, SEV_LABEL[f["severity"]], ", ".join(f["clause_ids"]), current, direction, how,
                "", "高" if f["severity"] >= 4 else ("中" if f["severity"] == 3 else "低")]
        for j, v in enumerate(vals, start=1):
            body_cell(ws.cell(row=r, column=j, value=v), mono=(j == 1))
        sc = ws.cell(row=r, column=2)
        sc.fill = PatternFill("solid", fgColor=SEV_FILL[f["severity"]])
        sc.font = Font(bold=True, size=9, color=SEV_FONT[f["severity"]], name=YH)
        sc.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[r].height = 52
        r += 1
    ws.freeze_panes = ws.cell(row=4, column=1)


def sheet_stats(wb, contract, review, stats):
    ws = wb.create_sheet("08 统计")
    ws.sheet_properties.tabColor = "64748B"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 50
    r = title_block(ws, "08 统计与量级测算", "分布统计由条目直接计数；金额测算口径见合同原文，仅用于量级说明。", 4)
    topic_name = {t["id"]: t["name"] for t in review["topics"]}

    def block(title, pairs, start_r):
        ws.cell(row=start_r, column=1, value=title).font = Font(bold=True, size=11, color=INK, name=YH)
        ws.cell(row=start_r, column=1).fill = PatternFill("solid", fgColor="E0F2FE")
        ws.merge_cells(start_row=start_r, start_column=1, end_row=start_r, end_column=2)
        rr = start_r + 1
        for k, v in pairs:
            a = ws.cell(row=rr, column=1, value=k)
            b = ws.cell(row=rr, column=2, value=v)
            for x in (a, b):
                body_cell(x)
            b.alignment = Alignment(horizontal="center", vertical="center")
            rr += 1
        return rr + 1

    r = block("严重度分布", [(SEV_LABEL[k], stats["severity"].get(k, 0)) for k in (5, 4, 3, 2, 1)], r)
    r = block("类型分布", [(k, stats["kind"].get(k, 0)) for k in KIND_ORDER], r)
    r = block("主题分布", [(topic_name[t["id"]], stats["topic"].get(t["id"], 0))
                          for t in review["topics"] if stats["topic"].get(t["id"])], r)

    cb = review["summary"].get("calc_basis", {})
    rows = [
        ("合同数量（公吨）", cb.get("quantity_mt")),
        ("单价（USD/公吨）", cb.get("unit_price_usd")),
        ("合同金额（USD）", cb.get("contract_value_usd")),
        ("预付款比例", cb.get("advance_pct")),
        ("预付款（USD）", cb.get("advance_usd")),
        ("尾款（USD）", cb.get("balance_usd")),
        ("卖方责任上限（USD）", cb.get("liability_cap_usd")),
        ("迟延违约金（USD/日）", cb.get("ld_per_day_usd")),
        ("违约金上限（USD）", cb.get("ld_cap_usd")),
    ]
    ws.cell(row=r, column=1, value="量级测算（依据合同原文数字）").font = Font(bold=True, size=11, color=INK, name=YH)
    ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor="E0F2FE")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    r += 1
    for k, v in rows:
        a = ws.cell(row=r, column=1, value=k)
        b = ws.cell(row=r, column=2, value=v)
        body_cell(a)
        body_cell(b)
        if isinstance(v, (int, float)):
            b.number_format = "0.00%" if "比例" in k or "pct" in k else ("#,##0" if v > 1000 else "0.00")
        b.alignment = Alignment(horizontal="right", vertical="center")
        r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r + 2, end_column=4)
    c = ws.cell(row=r, column=1, value="测算说明：" + cb.get("note", ""))
    c.font = Font(size=9, color="7C2D12", name=YH)
    c.fill = WARN_FILL
    c.alignment = Alignment(wrap_text=True, vertical="top")


def build(case_dir: Path, out: Path, author: str) -> dict:
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
    sheet_bilingual(wb, review)
    sheet_amend(wb, review)
    sheet_stats(wb, contract, review, check["stats"])
    wb.properties.creator = author
    wb.properties.title = f'{contract["contract_meta"].get("title", "")} · 外贸采购合同审阅'
    wb.properties.subject = "业务审查提示，不构成法律意见"
    wb.properties.keywords = "外贸采购,进口合同,合同审查,Incoterms,信用证,索赔,争议解决"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return {"out": str(out), "sheets": wb.sheetnames, "findings": len(review["findings"]),
            "warnings": check["warnings"]}


def main() -> None:
    ap = argparse.ArgumentParser(description="生成外贸采购合同审阅 Excel 工作簿")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--author", default="审阅外贸采购合同 Skill")
    a = ap.parse_args()
    info = build(Path(a.dir), Path(a.out), a.author)
    print(json.dumps({"ok": True, **info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
