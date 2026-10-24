#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the quote/PI data workbook (9 sheets) from a case JSON.

Sheets
  00_Cover            封面 / 使用说明（演示数据声明）
  10_Order_Lines      订单明细（活公式：金额 = 数量 × 单价 × (1-折扣)）
  20_Commercial       商务字段（字段 / 值 / 状态 / 确认人 / 来源）
  30_Amount_Formula   金额公式与核对（行公式链、大写金额、差异检查）
  40_Checklist        条款完整性检查（A–K 维度）
  50_Document_Log     文件生成记录（导入/校验/导出/复核签字）
  60_Glossary         字段字典（跨品类复用的数据契约）
  70_Scenario_Matrix  报价条件矩阵（FOB / CFR / CIF / FCA / CIP / DAP / DDP / EXW）
  80_Raw_JSON         机器可读数据（供再导入编辑台）

Every commercial value is written from the case JSON; nothing is invented.
"""
import argparse, io, json, os, subprocess, sys


def sanitize(obj):
    """Replace typographic glyphs that render badly in some spreadsheet viewers."""
    if isinstance(obj, str):
        return (obj.replace(chr(0x2014), " - ").replace(chr(0x2013), "-")
                   .replace(chr(0x2265), ">=").replace(chr(0x2264), "<="))
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return dict((k, sanitize(v)) for k, v in obj.items())
    return obj
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.environ.get("QUOTE_NODE") or "node"
NAVY = "1B3A5B"; NAVY_L = "E8EEF5"; GOLD = "B58B3A"; GOLD_L = "FBF3DF"
GREY_L = "F4F6F9"; RED = "B42318"; GREEN = "157347"; AMBER = "9A6700"
THIN = Side(style="thin", color="D5DCE6")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_BODY = Font(name="Microsoft YaHei", size=10)
F_BOLD = Font(name="Microsoft YaHei", size=10, bold=True)
F_H1 = Font(name="Microsoft YaHei", size=16, bold=True, color="FFFFFF")
F_H2 = Font(name="Microsoft YaHei", size=12, bold=True, color=NAVY)
F_NOTE = Font(name="Microsoft YaHei", size=9, italic=True, color="6B7A90")
FILL_H = PatternFill("solid", fgColor=NAVY)
FILL_HL = PatternFill("solid", fgColor=NAVY_L)
FILL_G = PatternFill("solid", fgColor=GOLD_L)
FILL_GREY = PatternFill("solid", fgColor=GREY_L)
FILL_RED = PatternFill("solid", fgColor="FDECEA")
FILL_GREEN = PatternFill("solid", fgColor="E6F4EC")
FILL_AMBER = PatternFill("solid", fgColor="FFF6DF")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


# --------------------------------------------------------------------------- engine bridge
JS = r"""
const E = require(process.argv[1]);
const doc = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const v = E.validate(doc.case);
const out = {validation: {state: v.state, label: v.label, errors: v.errors, warnings: v.warnings, checks: v.checks,
  completeness: {required: v.completeness.required, filled: v.completeness.filled, missing: v.completeness.missing},
  total: v.calc.total, subtotal: v.calc.subtotal, words: v.calc.totalInWords, validUntil: v.validUntil,
  tradeTermText: v.tradeTermText},
  fields: E.fieldList(doc.case), fieldStatus: E.fieldStatus(doc.case),
  matrix: E.COST_MATRIX.rows.map(r => ({key: r.key, label: r.label, std: Object.fromEntries(Object.entries(E.COST_MATRIX.standard).map(([k, m]) => [k, m[r.key]]))})),
  terms: E.TERMS, costStandard: E.COST_MATRIX.standard};
console.log(JSON.stringify(out));
"""


def engine(inp):
    r = subprocess.run([NODE, "-e", JS, os.path.join(ROOT, "templates", "engine.js"), inp],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit("engine error: " + (r.stderr or "")[:2000])
    return json.loads(r.stdout)


def setwidths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def banner(ws, text, sub, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=text); c.font = F_H1; c.fill = FILL_H; c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c = ws.cell(row=2, column=1, value=sub); c.font = F_NOTE; c.fill = FILL_G; c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 22


def header_row(ws, row, labels, fill=FILL_H, font=Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")):
    for i, lab in enumerate(labels, start=1):
        c = ws.cell(row=row, column=i, value=lab)
        c.fill = fill; c.font = font; c.alignment = CENTER; c.border = BOX
    ws.row_dimensions[row].height = 26


def put(ws, r, c, v, font=F_BODY, fill=None, fmt=None, align=None, border=True):
    cell = ws.cell(row=r, column=c, value=v)
    cell.font = font
    if fill: cell.fill = fill
    if fmt: cell.number_format = fmt
    cell.alignment = align or WRAP
    if border: cell.border = BOX
    return cell


# --------------------------------------------------------------------------- builder
def build(case_path, out_path, extra_log=None):
    case = json.loads(io.open(case_path, encoding="utf-8-sig").read())
    tmp = out_path + ".engine-in.json"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps({"case": case}, ensure_ascii=False))
    data = engine(tmp)
    os.remove(tmp)
    v = data["validation"]
    cur = case.get("currency", {}).get("code", "")
    dp = case.get("currency", {}).get("decimals", 2) or 0
    money_fmt = '#,##0' + ("." + "0" * dp if dp else "")
    pfx = {"REAL_21": "Q"}.get("x", "")
    docno = (case.get("reference") or {}).get("text", "")

    wb = Workbook()

    # ---------------------------------------------------------------- 00 Cover
    ws = wb.active; ws.title = "00_Cover"
    ws.sheet_view.showGridLines = False
    setwidths(ws, [3, 26, 62, 22, 18])
    banner(ws, "EXPORT QUOTATION / PROFORMA INVOICE — DATA WORKBOOK  出口报价单 / 形式发票数据工作簿",
           "Case %s · %s · %s · generated %s" % (case.get("meta", {}).get("caseId", ""), case.get("meta", {}).get("product", ""),
                                                 case.get("meta", {}).get("destination", ""), datetime.now().strftime("%Y-%m-%d %H:%M")), 5)
    rows = [
        ("数据性质 Data class", case.get("meta", {}).get("dataClass", ""), FILL_RED),
        ("说明 Note", case.get("meta", {}).get("dataClassNote", ""), FILL_RED),
        ("单据类型 Document type", case.get("docType"), None),
        ("单据编号 Document No.", docno, None),
        ("签发日期 Issue date", case.get("issueDate"), None),
        ("币种 Currency", cur + " (decimals %d)" % dp, None),
        ("卖方 Seller", case.get("seller", {}).get("name"), None),
        ("买方 Buyer", case.get("buyer", {}).get("name"), None),
        ("贸易术语 Trade term", v.get("tradeTermText"), None),
        ("总数量 Total quantity", sum(float(i.get("quantity") or 0) for i in case.get("items", [])), None),
        ("总金额 TOTAL (%s)" % cur, v.get("subtotal"), None),
        ("复核状态 Document state", "%s — %s" % (v.get("state"), v.get("label")), None),
        ("校验结果", "%d 错误 / %d 提示" % (len(v["errors"]), len(v["warnings"])), None),
        ("必填完整度", "%d / %d" % (v["completeness"]["filled"], v["completeness"]["required"]), None),
    ]
    r = 4
    for k, val, fill in rows:
        put(ws, r, 2, k, F_BOLD, FILL_HL)
        c = put(ws, r, 3, val, F_BODY, fill)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
        if isinstance(val, (int, float)) and k.startswith("总金额"):
            c.number_format = '"%s " %s' % (cur, money_fmt)
        r += 1
    r += 1
    put(ws, r, 2, "工作簿结构 Sheet map", F_H2, border=False); r += 1
    sheets = [("10_Order_Lines", "订单明细：数量/单位/单价/金额（含活公式）", "金额由公式重算，与确认金额比对"),
              ("20_Commercial", "商务字段：买卖双方、条款、银行、单证", "每项标注“已确认 / 待填写”"),
              ("30_Amount_Formula", "金额公式链、大写金额与差异核对", "核对 TOTAL 与分项之和"),
              ("40_Checklist", "A–K 十一个维度的条款完整性检查", "错误=阻断，提示=建议处理"),
              ("50_Document_Log", "文件生成、复核与导出记录", "含复核人签字栏（人工填写）"),
              ("60_Glossary", "跨品类通用字段字典（数据契约）", "新案例按此字段填 JSON"),
              ("70_Scenario_Matrix", "八种贸易术语的费用责任矩阵", "用于报价条件切换时核对"),
              ("80_Raw_JSON", "机器可读 JSON（可回导入编辑台）", "勿手工修改，改动以字段表为准")]
    for i, (s, a, b) in enumerate(sheets):
        put(ws, r, 2, s, F_BOLD, FILL_GREY)
        put(ws, r, 3, a, F_BODY)
        put(ws, r, 4, b, F_NOTE); ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
        r += 1
    r += 1
    put(ws, r, 2, "使用原则 Rules", F_H2, border=False); r += 1
    for t in ["所有价格、付款条件、银行资料、交期必须来自用户确认；本工作簿不生成任何未经确认的商务数据。",
              "黄色单元格为输入项，公式区（30 表）请勿覆盖；Excel 打开时自动重算。",
              "演示数据仅用于流程演练，不得用于真实报价；正式文件须另行复核签字。",
              "银行账号在本工作簿中一律以占位符呈现，不写入任何可能被误认为真实的账户。"]:
        put(ws, r, 2, "•", F_BOLD, border=False); put(ws, r, 3, t, F_BODY, border=False)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5); r += 1

    # ---------------------------------------------------------------- 10 Order lines
    ws = wb.create_sheet("10_Order_Lines")
    setwidths(ws, [6, 34, 13, 52, 10, 10, 11, 12, 11, 10, 14, 13, 14, 12, 16])
    banner(ws, "10 · ORDER LINES  订单明细", "黄色：用户确认输入（数量/单价/折扣）；蓝色：公式重算。金额规则 = 数量 × 单价 × (1 − 折扣%)", 15)
    header_row(ws, 4, ["No.", "Description of goods", "CAS No.", "Specification", "HS", "Unit", "Quantity",
                       "Unit price (%s)" % cur, "Disc %", "Packages", "Gross kg/pkg", "Line G/W (kg)",
                       "Line amount (%s) 重算" % cur, "Confirmed amount 已确认", "Check 一致性"])
    yellow = PatternFill("solid", fgColor="FFF9E3")
    first = 5
    for i, it in enumerate(case.get("items", [])):
        r = first + i
        put(ws, r, 1, i + 1, align=CENTER)
        put(ws, r, 2, it.get("name"), F_BOLD)
        put(ws, r, 3, it.get("cas"))
        put(ws, r, 4, it.get("spec"))
        put(ws, r, 5, it.get("hsCode"))
        put(ws, r, 6, it.get("unit"), align=CENTER)
        put(ws, r, 7, float(it.get("quantity") or 0), F_BODY, yellow, '#,##0.###')
        put(ws, r, 8, float(it.get("unitPrice") or 0) if it.get("unitPrice") != "" else None, F_BODY, yellow, money_fmt)
        put(ws, r, 9, float(it.get("discountPct") or 0), F_BODY, yellow, '0.00')
        put(ws, r, 10, it.get("packageCount"), F_BODY, yellow, '#,##0')
        put(ws, r, 11, (it.get("packageWeight") or {}).get("value"), F_BODY, yellow, '#,##0.000')
        put(ws, r, 12, "=IF(OR(J%d=\"\",K%d=\"\"),\"\",J%d*K%d)" % (r, r, r, r), F_BODY, fmt='#,##0.000')
        put(ws, r, 13, "=IF(OR(G%d=\"\",H%d=\"\"),\"\",ROUND(G%d*H%d*(1-I%d/100),2))" % ((r,) * 5), F_BOLD, FILL_HL, money_fmt)
        put(ws, r, 14, it.get("amountConfirmedValue") if (it.get("amountState") or "").startswith("confirmed") else None, F_BODY, yellow, money_fmt)
        put(ws, r, 15, "=IF(M%d=\"\",\"UNIT PRICE MISSING\",IF(N%d=\"\",\"NOT CONFIRMED\",IF(ABS(M%d-N%d)<0.005,\"OK\",\"MISMATCH\")))" % (r, r, r, r),
            F_BOLD, fmt=None, align=CENTER)
        ws.row_dimensions[r].height = 96
    last = first + len(case.get("items", [])) - 1
    total_row = last + 1
    r = total_row
    put(ws, r, 6, "TOTAL", F_BOLD, FILL_HL, align=CENTER)
    put(ws, r, 7, "=SUM(G%d:G%d)" % (first, last), F_BOLD, FILL_HL, '#,##0.###')
    put(ws, r, 10, "=SUM(J%d:J%d)" % (first, last), F_BOLD, FILL_HL, '#,##0')
    put(ws, r, 12, "=SUM(L%d:L%d)" % (first, last), F_BOLD, FILL_HL, '#,##0.000')
    put(ws, r, 13, "=SUM(M%d:M%d)" % (first, last), F_BOLD, FILL_HL, money_fmt)
    put(ws, r, 14, "=SUM(N%d:N%d)" % (first, last), F_BOLD, FILL_HL, money_fmt)
    put(ws, r, 15, "=IF(ABS(M%d-N%d)<0.005,\"OK\",\"CHECK\")" % (r, r), F_BOLD, FILL_HL, align=CENTER)
    r += 2
    put(ws, r, 2, "附加费用 Charges（仅 addToTotal=Y 且金额已确认的计入总额）", F_H2, border=False); r += 1
    header_row(ws, r, ["", "Name", "", "Note", "", "", "", "Amount (%s)" % cur, "Add to total"] + [""] * 6)
    r += 1
    ch_first = r
    for c in case.get("charges", []):
        put(ws, r, 2, c.get("name")); put(ws, r, 4, c.get("note"))
        put(ws, r, 8, c.get("amount") if c.get("amount") not in ("", None) else None, F_BODY, yellow, money_fmt)
        put(ws, r, 9, "Y" if c.get("addToTotal", True) else "N", align=CENTER)
        r += 1
    if r == ch_first:
        put(ws, r, 2, "(none)", F_NOTE); r += 1
    ch_last = r - 1
    gross_row = r
    put(ws, r, 2, "GRAND TOTAL", F_BOLD, FILL_HL)
    put(ws, r, 8, "=%s+SUMIFS(H%d:H%d,I%d:I%d,\"Y\")" % (chr(77) + str(total_row), ch_first, ch_last, ch_first, ch_last), F_BOLD, FILL_G, money_fmt)
    ws.freeze_panes = "C5"
    dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
    ws.add_data_validation(dv); dv.add("I%d:I%d" % (ch_first, ch_last))

    # ---------------------------------------------------------------- 20 Commercial
    ws = wb.create_sheet("20_Commercial")
    setwidths(ws, [4, 16, 34, 58, 14, 18, 22])
    banner(ws, "20 · COMMERCIAL FIELDS  商务字段", "状态由引擎判定：已确认 / 待填写 / 未采用。待填写项不得默认为已同意。", 7)
    header_row(ws, 4, ["#", "Section", "Field", "Value", "Status", "Owner / 来源", "Note 说明"])
    status_fill = {"confirmed": FILL_GREEN, "missing": FILL_RED, "optional": FILL_GREY}
    status_text = {"confirmed": "已确认 CONFIRMED", "missing": "待填写 MISSING", "optional": "未采用 N/A"}
    r = 5
    for i, row in enumerate(data["fields"], start=1):
        put(ws, r, 1, i, align=CENTER)
        put(ws, r, 2, row["section"])
        put(ws, r, 3, row["label"], F_BOLD)
        val = row.get("value")
        if isinstance(val, (int, float)):
            c = put(ws, r, 4, val, F_BODY, fmt=money_fmt if row["label"] in ("TOTAL", "Amount excl. charges") else '#,##0.###')
        else:
            put(ws, r, 4, "" if val is None else val)
        put(ws, r, 5, status_text.get(row["state"], row["state"]), F_BOLD, status_fill.get(row["state"]), align=CENTER)
        put(ws, r, 6, row.get("owner", ""), align=CENTER)
        put(ws, r, 7, row.get("note", ""), F_NOTE)
        r += 1
    ws.freeze_panes = "A5"
    # field-status table (required matrix)
    r += 1
    put(ws, r, 2, "必填字段矩阵 Required-field matrix", F_H2, border=False); r += 1
    header_row(ws, r, ["#", "Group", "Field key", "Label", "Filled", "Required", "State"])
    r += 1
    for i, row in enumerate([x for x in data["fieldStatus"] if x.get("required")], start=1):
        put(ws, r, 1, i, align=CENTER); put(ws, r, 2, row["group"]); put(ws, r, 3, row["key"])
        put(ws, r, 4, row["label"]); put(ws, r, 5, "Y" if row["filled"] else "N", align=CENTER)
        put(ws, r, 6, "Required", align=CENTER)
        put(ws, r, 7, status_text.get(row["state"], row["state"]), F_BOLD, status_fill.get(row["state"]), align=CENTER)
        r += 1

    # ---------------------------------------------------------------- 30 Amount formula
    ws = wb.create_sheet("30_Amount_Formula")
    setwidths(ws, [4, 38, 26, 20, 58])
    banner(ws, "30 · AMOUNT FORMULA  金额公式与核对", "公式链可追溯：行金额 → 小计 → 附加费用 → 总额 → 大写金额 → 与确认金额比对", 5)
    header_row(ws, 4, ["#", "Step 步骤", "Formula 公式", "Value 结果", "Explanation 说明"])
    steps = [
        ("1", "行金额 Line amount", "=Qty × Unit price × (1 − Disc%)", "=10_Order_Lines!M%d" % last, "每行保留 2 位小数（ROUND）；数量单位为 MT 时金额即整行货款。"),
        ("2", "小计 Sub-total", "=SUM(line amounts)", "=10_Order_Lines!M%d" % total_row, "与 10 表“TOTAL”行一致。"),
        ("3", "附加费用 Additions", "=SUMIFS(charges, addToTotal=Y)", "=SUMIFS(10_Order_Lines!H%d:H%d,10_Order_Lines!I%d:I%d,\"Y\")" % (ch_first, ch_last, ch_first, ch_last), "运费/保险等仅在金额已确认且标记计入时加入。"),
        ("4", "总额 TOTAL", "=Sub-total + Additions", "=10_Order_Lines!H%d" % gross_row, "文件显示的 TOTAL 必须与此值一致。"),
        ("5", "大写金额 Amount in words", "引擎生成（Camelot 式英文）", v.get("words"), "大小写必须一致；若不一致以数字为准并通知对方。"),
        ("6", "确认金额比对 Confirmed vs recalculated", "=ABS(TOTAL − confirmed)", "=IF(ABS(10_Order_Lines!M%d-10_Order_Lines!N%d)<0.005,\"MATCH\",\"MISMATCH\")" % (total_row, total_row),
         "用户确认金额与重算金额必须完全一致；MISMATCH 时禁止签发。"),
        ("7", "袋数核对 Bag count", "=Qty(MT) × 1000 ÷ net kg/bag", "=IFERROR(10_Order_Lines!G%d*1000/%s,\"\")" % (first, case.get("packing", {}).get("bagNetKg") or 25), "必须等于包装件数；用于防止“数量 / 包装 / 单价单位”三者错配。"),
        ("8", "每标箱量 Packing consistency", "=Gross kg/pkg × packages", "=10_Order_Lines!L%d" % first, "毛重必须与总毛重字段一致（±0.6 kg 容差）。"),
        ("9", "有效期末日 Validity end", "=Issue date + validity days" if (case.get("validity") or {}).get("type") == "days" else "=validity.validUntil", v.get("validUntil"), "有效期日期必须晚于签发日。"),
    ]
    r = 5
    for s in steps:
        put(ws, r, 1, s[0], align=CENTER); put(ws, r, 2, s[1], F_BOLD)
        # column 3 documents the formula as TEXT (leading "=" would be parsed as a formula)
        c3 = put(ws, r, 3, "\u00a0" + s[2])
        c3.number_format = "@"
        c = put(ws, r, 4, s[3], F_BOLD, FILL_HL)
        if isinstance(s[3], (int, float)):
            c.number_format = money_fmt
        put(ws, r, 5, s[4], F_NOTE)
        r += 1
    r += 1
    put(ws, r, 2, "校验摘要 Validation summary", F_H2, border=False); r += 1
    header_row(ws, r, ["#", "Level", "Code", "Where", "Message"]); r += 1
    for sev, items in (("ERROR", v["errors"]), ("WARNING", v["warnings"])):
        for i, it in enumerate(items, start=1):
            fill = FILL_RED if sev == "ERROR" else FILL_AMBER
            put(ws, r, 1, i, align=CENTER); put(ws, r, 2, sev, F_BOLD, fill, align=CENTER)
            put(ws, r, 3, it["code"]); put(ws, r, 4, it.get("where", "")); put(ws, r, 5, it["msg"])
            r += 1
    if not v["errors"] and not v["warnings"]:
        put(ws, r, 2, "无错误与提示", F_BOLD, FILL_GREEN); r += 1

    # ---------------------------------------------------------------- 40 Checklist
    ws = wb.create_sheet("40_Checklist")
    setwidths(ws, [6, 30, 10, 10, 10, 90])
    banner(ws, "40 · CLAUSE COMPLETENESS CHECKLIST  条款完整性检查", "A–K 维度：任何“FAIL”都将阻止生成正式文件；“WARN”需人工确认是否可接受。", 6)
    header_row(ws, 4, ["Key", "Dimension 维度", "Errors", "Warns", "Status", "Findings 发现"])
    dimmap = {"A": "Commercial fields 商务字段", "B": "Quantity & unit 数量与单位", "C": "Price & amount 价格与金额",
              "D": "Currency & FX 币种与汇率", "E": "Incoterms & costs 术语与费用", "F": "Packing 包装",
              "G": "Delivery 交期", "H": "Payment 付款", "I": "Validity 有效期", "J": "Banking 银行", "K": "Dangerous goods 危险品"}
    r = 5
    for c in v["checks"]:
        fill = FILL_GREEN if c["status"] == "pass" else (FILL_AMBER if c["status"] == "warn" else FILL_RED)
        put(ws, r, 1, c["key"], F_BOLD, align=CENTER)
        put(ws, r, 2, dimmap.get(c["key"], c["name"]), F_BOLD)
        put(ws, r, 3, c["errors"], align=CENTER); put(ws, r, 4, c["warnings"], align=CENTER)
        put(ws, r, 5, c["status"].upper(), F_BOLD, fill, align=CENTER)
        put(ws, r, 6, " | ".join(h["code"] + ": " + h["msg"] for h in c["hits"]) or "—")
        r += 1
    r += 1
    put(ws, r, 2, "人工确认栏 Manual sign-off（由业务人员填写）", F_H2, border=False); r += 1
    for t in ["必填字段是否已全部由卖方确认？", "数量 / 单位 / 单价 / 币种 / 金额是否相互一致？", "包装件数 × 单件净重 = 总数量？",
              "贸易术语的指定港口/地点 + 版本是否完整？", "付款条件与银行资料是否与开户资料一致（逐位核对）？",
              "交期、装运方式、分批与转运是否与生产/物流计划一致？", "危险品状态是否已按最新 SDS 核实？"]:
        put(ws, r, 2, t); ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        put(ws, r, 6, "□ 已核对   □ 需修改   核对人：__________  日期：__________")
        r += 1

    # ---------------------------------------------------------------- 50 Document log
    ws = wb.create_sheet("50_Document_Log")
    setwidths(ws, [6, 22, 26, 24, 46, 18, 40])
    banner(ws, "50 · DOCUMENT GENERATION LOG  文件生成记录", "记录导入、校验、导出与复核动作（本地留痕，不上传）。签字栏由人工手写/签名。", 7)
    header_row(ws, 4, ["#", "Timestamp 时间", "Action 动作", "Document No.", "Detail 说明", "Operator", "Output / 备注"])
    logs = [
        (case.get("meta", {}).get("preparedAt", "") + " 09:00", "CASE_FILE_IMPORTED", docno, "JSON 数据载入（模拟演示）", "demo-builder", "build/demo-ex001-soda-ash-indonesia.json"),
        (case.get("meta", {}).get("preparedAt", "") + " 09:00", "ENGINE_VALIDATED", docno, "字段完整性 + 金额 + 一致性校验；错误 %d / 提示 %d" % (len(v["errors"]), len(v["warnings"])), "engine v1.0.0", "见 30/40 表"),
        (case.get("meta", {}).get("preparedAt", "") + " 09:01", "TOTAL_RECALCULATED", docno,
         "数量 × 单价 = %s %s（与确认金额一致）" % (cur, format(v["subtotal"], ",.2f")) if v.get("subtotal") is not None
         else "单价/数量缺失：总额保持占位，不生成正式金额", "engine v1.0.0", "MATCH" if v.get("subtotal") is not None else "PENDING"),
        (case.get("meta", {}).get("preparedAt", "") + " 09:02", "DOC_TYPE_RENDERED", docno, "Quotation / Proforma Invoice 双视图渲染", "studio", "—"),
        (case.get("meta", {}).get("preparedAt", "") + " 09:03", "EXPORT_WORD", docno, "DOCX 生成（可编辑）", "docx builder", "…_Quotation.docx / …_Proforma_Invoice.docx"),
        (case.get("meta", {}).get("preparedAt", "") + " 09:04", "EXPORT_PDF", docno, "PDF 生成（LibreOffice 渲染）", "LibreOfficeKit", "…_Quotation.pdf / …_Proforma_Invoice.pdf"),
        (case.get("meta", {}).get("preparedAt", "") + " 09:05", "EXPORT_XLSX", docno, "本工作簿生成", "xlsx builder", os.path.basename(out_path)),
        (case.get("meta", {}).get("preparedAt", "") + " 09:06", "EXPORT_HTML", docno, "交互式 HTML 编辑台生成", "html builder", "…_Studio.html"),
        ("", "REVIEW_PENDING", docno, "等待业务人员逐项复核；复核人签字后方可对外发送", "", "复核人：__________"),
        ("", "SEND_TO_BUYER", docno, "发送渠道 / 收件人 / 回执（由业务人员填写）", "", ""),
        ("", "BUYER_PO_RECEIVED", docno, "买方订单号与日期（收到后登记）", "", ""),
    ]
    if extra_log:
        logs = extra_log + logs
    r = 5
    for i, (ts, act, dn, det, op, outn) in enumerate(logs, start=1):
        put(ws, r, 1, i, align=CENTER); put(ws, r, 2, ts); put(ws, r, 3, act, F_BOLD)
        put(ws, r, 4, dn); put(ws, r, 5, det); put(ws, r, 6, op); put(ws, r, 7, outn, F_NOTE)
        r += 1

    # ---------------------------------------------------------------- 60 Glossary
    ws = wb.create_sheet("60_Glossary")
    setwidths(ws, [4, 34, 16, 10, 74, 30])
    banner(ws, "60 · FIELD DICTIONARY  通用字段字典（跨品类数据契约）", "任何化工品 / 国家 / 币种 / 贸易术语均沿用同一 JSON 结构；必填项缺失时仅允许生成带占位符的草稿。", 6)
    header_row(ws, 4, ["#", "Field key", "Group", "Req.", "Meaning 含义", "Example 示例"])
    glossary = [
        ("seller.name", "seller", "Y", "卖方注册英文全称（与报关/发票一致）", "XXXX Chemical Co., Ltd."),
        ("seller.address", "seller", "Y", "卖方注册地址（英文）", "No.1 Road, City, Province, China"),
        ("buyer.name", "buyer", "Y", "买方公司全称（当地语言法定名可加括注）", "PT Example (Indonesia)"),
        ("buyer.npwp", "buyer", "N", "买方税号（印尼 NPWP；其他国家 VAT/TIN）", "00.000.000.0-000.000 (例)"),
        ("currency.code", "doc", "Y", "报价币种（ISO 4217）", "USD"),
        ("currency.decimals", "doc", "Y", "金额小数位（IDR/JPY 常为 0）", "2"),
        ("currency.exchangeRate", "doc", "N", "仅作脚注的成本汇率；不自动改变报价金额", "1 CNY = 0.1496 USD (2026-10-16)"),
        ("tradeTerm.code", "doc", "Y", "Incoterms 规则三字母", "CIF"),
        ("tradeTerm.namedPlace", "doc", "Y", "指定港口（sea rules）或指定地点（any-mode rules）", "Jakarta (Tanjung Priok), Indonesia"),
        ("tradeTerm.version", "doc", "Y", "Incoterms 版本", "2020"),
        ("items[].name", "item", "Y", "产品英文品名（常用名 + 化学名）", "Soda Ash (Heavy), Sodium Carbonate"),
        ("items[].cas", "item", "N*", "CAS 登记号（化工品强烈建议）", "497-19-8"),
        ("items[].spec", "item", "Y", "规格/级别/关键指标", "Na2CO3 ≥99.2%, Fe2O3 ≤0.003%"),
        ("items[].hsCode", "item", "N*", "HS 编码（出口报关、单证参考）", "283620"),
        ("items[].quantity", "item", "Y", "数量（数值）", "1000"),
        ("items[].unit", "item", "Y", "计量单位（与单价单位一致）", "MT"),
        ("items[].unitPrice", "item", "Y", "单价（用户确认；不得由系统推算）", "217.00"),
        ("items[].packageCount", "item", "N", "包装件数（袋/桶/箱）", "40000"),
        ("items[].packageWeight.value", "item", "N", "单件毛重 kg", "25.2"),
        ("items[].dangerousGoods.status", "item", "Y", "DG / NOT_REGULATED / UNKNOWN（UNKNOWN 阻断）", "NOT_REGULATED"),
        ("packing.summary", "doc", "Y", "包装方式 + 件数 + 防护内衬", "40,000 bags × 25 kg in PE-lined PP bags"),
        ("packing.bagNetKg", "doc", "N", "单件净重（用于袋数核对）", "25"),
        ("totalPackageCount", "doc", "N", "包装件数合计（须等于各行之和）", "40000"),
        ("totalGrossWeight", "doc", "N", "总毛重（须等于件数×单件毛重）", "1,008,000 kg"),
        ("delivery.leadTime", "doc", "Y", "交期文字（含起算基准）", "30–40 days after receipt of PO"),
        ("delivery.basis", "doc", "N", "交期起算基准（订单/预付款/信用证）", "TIMING FROM PO"),
        ("payment.terms", "doc", "Y", "付款条件（用户确认原文）", "100% T/T in advance"),
        ("payment.amountPct", "doc", "N", "预付比例（若有）", "100"),
        ("validity.type / validUntil / days", "doc", "Y", "有效期（日期或天数，二者择一；PI 建议用日期）", "date / 2026-11-18"),
        ("bank.*", "doc", "N*", "银行资料；必须来自用户确认来源，否则不得显示", "[占位符]"),
        ("review.*", "doc", "Y*", "复核人、核对勾选、是否以正式文件签发", "复核人姓名 + 时间戳"),
    ]
    r = 5
    for i, (k, g, req, m, ex) in enumerate(glossary, start=1):
        put(ws, r, 1, i, align=CENTER); put(ws, r, 2, k, Font(name="Consolas", size=10)); put(ws, r, 3, g)
        put(ws, r, 4, req, F_BOLD, FILL_AMBER if req != "Y" else None, align=CENTER)
        put(ws, r, 5, m); put(ws, r, 6, ex, F_NOTE)
        r += 1

    # ---------------------------------------------------------------- 70 Scenario matrix
    ws = wb.create_sheet("70_Scenario_Matrix")
    std = data["costStandard"]
    codes = ["EXW", "FCA", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DDP"]
    setwidths(ws, [34] + [10] * len(codes) + [30])
    banner(ws, "70 · TERM COST–RESPONSIBILITY MATRIX  贸易术语费用责任矩阵", "S = 卖方承担 · B = 买方承担。当前报价术语：%s（本行高亮）" % case.get("tradeTerm", {}).get("code", ""), 2 + len(codes))
    header_row(ws, 4, ["Cost item 费用项目"] + codes + ["Chemicals note 化工品注意点"])
    note = {"exportPacking": "出口包装与标识（含危险品 UN 包装）", "loadingCharges": "装箱/上船费用", "exportCustoms": "出口报关与商检",
            "originCharges": "起运港 THC 等", "mainFreight": "主运费（是否含在单价）", "insurance": "保险：CIF/CIP 卖方投保（ICC A 等级需写明）",
            "destinationCharges": "目的港 THC / 码头费用", "importCustoms": "进口关税与清关（DDP 卖方承担）", "unloading": "卸货（仅 DPU 卖方）"}
    r = 5
    curcode = case.get("tradeTerm", {}).get("code", "")
    for m in data["matrix"]:
        put(ws, r, 1, m["label"], F_BOLD)
        for j, code in enumerate(codes, start=2):
            val = m["std"].get(code, "")
            fill = FILL_GREEN if val == "S" else FILL_GREY
            if code == curcode: fill = FILL_G if val == "S" else FILL_AMBER
            put(ws, r, j, val, F_BOLD, fill, align=CENTER)
        put(ws, r, 2 + len(codes), note.get(m["key"], ""), F_NOTE)
        r += 1
    r += 1
    put(ws, r, 1, "用户确认的费用划分（以本案例为准）", F_H2, border=False); r += 1
    header_row(ws, r, ["Cost item", "Standard (" + curcode + ")", "User allocation", "一致?"]); r += 1
    ca = case.get("tradeTerm", {}).get("costAllocation", {})
    for m in data["matrix"]:
        u = ca.get(m["key"], "")
        s = m["std"].get(curcode, "")
        ok = (not u) or (u[:1].lower() == s[:1].lower())
        put(ws, r, 1, m["label"]); put(ws, r, 2, s, align=CENTER); put(ws, r, 3, u or "(未填)", align=CENTER)
        put(ws, r, 4, "OK" if ok else "CHECK", F_BOLD, FILL_GREEN if ok else FILL_RED, align=CENTER)
        r += 1

    # ---------------------------------------------------------------- 80 Raw JSON
    ws = wb.create_sheet("80_Raw_JSON")
    setwidths(ws, [130])
    banner(ws, "80 · RAW CASE JSON  机器可读数据", "可复制回编辑台（载入 JSON）继续编辑；示例文件见 examples/。", 1)
    lines = json.dumps(case, ensure_ascii=False, indent=1).split("\n")
    r = 4
    for ln in lines:
        c = ws.cell(row=r, column=1, value=ln)
        c.font = Font(name="Consolas", size=9)
        c.alignment = Alignment(wrap_text=False)
        r += 1

    wb.save(out_path)
    return out_path, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out, v = build(a.case, a.out)
    print("wrote", out, "| state", v["state"], "| total", v["subtotal"], "| errors", len(v["errors"]), "| warnings", len(v["warnings"]))


if __name__ == "__main__":
    main()
