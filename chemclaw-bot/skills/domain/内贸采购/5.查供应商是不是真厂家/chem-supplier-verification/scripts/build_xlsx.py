# -*- coding: utf-8 -*-
"""生成供应商核验 Excel 工作簿（数据全部来自 input.json）"""
import math
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.formatting.rule import DataBarRule, FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import STRENGTH, VERDICT_META, VERDICT_RULES, load_doc

DIMENSIONS, CASES, MATERIALS, ONSITE, SOURCES = [], [], [], [], []
META, PROFILE = {}, {}
REPORT_ID = REPORT_DATE = PRODUCT = PRODUCT_SPEC = ""

NAVY = "0B1F33"
NAVY2 = "16324F"
GOLD = "B8892B"
GOLD_L = "FBF4E4"
GREEN = "0F7B5F"
GREEN_L = "EAF6F1"
AMBER = "B7791F"
AMBER_L = "FDF4E3"
RED = "B23A2E"
RED_L = "FBEDEA"
GRAY_L = "F2F5F8"
LINE = "E1E7ED"
ZEBRA = "F7F9FB"
INK = "16283C"
MUTED = "64748B"

THIN = Side(style="thin", color=LINE)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top", horizontal="left")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")

VERDICT_FILL = {
    "生产厂家": (GREEN_L, GREEN),
    "分装或复配": (AMBER_L, AMBER),
    "贸易经销": (RED_L, RED),
    "证据不足暂无法确认": (GRAY_L, "475569"),
}
STRENGTH_FILL = {3: ("EAF6F1", "0F7B5F", "●●● 强"), 2: ("FDF4E3", "B7791F", "●●○ 中"),
                 1: ("F2F5F8", "64748B", "●○○ 弱"), 0: ("F1F3F5", "94A3B8", "不计分")}


def solid(color):
    return PatternFill(start_color=color, end_color=color, fill_type="solid")


def title_block(ws, ncols, title, subtitle, meta):
    last = get_column_letter(ncols)
    ws.merge_cells(f"A1:{last}1")
    ws.merge_cells(f"A2:{last}2")
    ws.merge_cells(f"A3:{last}3")
    c = ws["A1"]
    c.value = title
    c.font = Font(name="微软雅黑", size=18, bold=True, color="FFFFFF")
    c.fill = solid(NAVY)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 44
    c2 = ws["A2"]
    c2.value = subtitle
    c2.font = Font(name="微软雅黑", size=10.5, color="475569")
    c2.fill = solid("FFFFFF")
    c2.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[2].height = 26
    c3 = ws["A3"]
    c3.value = meta
    c3.font = Font(name="Consolas", size=9, color="94A3B8")
    c3.fill = solid("FFFFFF")
    c3.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[3].height = 20


def header_row(ws, row, headers, widths, height=30):
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=row, column=i, value=h)
        cell.font = Font(name="微软雅黑", size=9.5, bold=True, color="FFFFFF")
        cell.fill = solid(NAVY2)
        cell.alignment = CENTER
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = height


def auto_height(ws, row, widths, minh=18, maxh=190):
    lines = 1
    for i, w in enumerate(widths, start=1):
        v = ws.cell(row=row, column=i).value
        if isinstance(v, str) and v and not v.startswith("="):
            per = max(5.0, w / 2.05)
            n = 0
            for seg in v.split("\n"):
                n += max(1, math.ceil(len(seg) / per))
            lines = max(lines, n)
    ws.row_dimensions[row].height = min(maxh, max(minh, lines * 14.2 + 5))


def body_row(ws, row, values, widths, zebra=False, center_cols=(), bold_cols=()):
    for i, v in enumerate(values, start=1):
        cell = ws.cell(row=row, column=i, value=v)
        cell.font = Font(name="微软雅黑", size=9.2, color=INK,
                         bold=(i in bold_cols))
        cell.alignment = CENTER if i in center_cols else WRAP
        cell.border = BORDER
        if zebra:
            cell.fill = solid(ZEBRA)
    auto_height(ws, row, widths)


def setup_sheet(ws, tab_color, freeze="A4", print_landscape=True):
    ws.sheet_properties.tabColor = tab_color
    ws.freeze_panes = freeze
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape" if print_landscape else "portrait"
    ws.page_setup.paperSize = 9  # A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.3
    ws.page_margins.top = ws.page_margins.bottom = 0.45


def build(doc, outdir=None):
    global DIMENSIONS, CASES, MATERIALS, ONSITE, SOURCES, META, PROFILE
    global REPORT_ID, REPORT_DATE, PRODUCT, PRODUCT_SPEC
    META = doc.get("meta", {})
    PROFILE = doc.get("product_profile", {})
    DIMENSIONS = doc.get("dimensions", [])
    CASES = doc.get("cases", [])
    MATERIALS = doc.get("materials", [])
    ONSITE = doc.get("onsite", [])
    SOURCES = doc.get("sources", [])
    REPORT_ID = META.get("report_id", "SV-001")
    REPORT_DATE = META.get("as_of", "")
    PRODUCT = META.get("product", "")
    PRODUCT_SPEC = META.get("product_spec", "")

    outdir = outdir or "."
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "%s.xlsx" % META.get("slug", "supplier-verification"))

    wb = Workbook()

    # ============================================================ 00 说明
    ws = wb.active
    ws.title = "00_说明"
    setup_sheet(ws, NAVY, freeze="A1")
    widths0 = [4, 22, 30, 30, 30, 22, 18, 14]
    for i, w in enumerate(widths0, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = f"供应商真伪核验工作簿 · {PRODUCT}"
    c.font = Font(name="微软雅黑", size=22, bold=True, color="FFFFFF")
    c.fill = solid(NAVY)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 56

    ws.merge_cells("A2:H2")
    c = ws["A2"]
    c.value = f"查供应商是不是真厂家：直接生产证据 / 间接业务证据 / 不构成证据 三分法 + 四类结论 + {len(MATERIALS)} 项索取清单"
    c.font = Font(name="微软雅黑", size=11, color="334155")
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[2].height = 28

    ws.merge_cells("A3:H3")
    c = ws["A3"]
    c.value = f"报告编号 {REPORT_ID}    产品 {PRODUCT}    规格 {PRODUCT_SPEC}    数据截止 {REPORT_DATE}    版本 v1.0"
    c.font = Font(name="Consolas", size=9, color="94A3B8")
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[3].height = 22

    case_brief = "、".join(f"{c['short']}（{c['verdict']}）" for c in CASES)
    regimes_brief = "；".join((PROFILE.get("regimes") or ["排污许可（对应行业类别）", "环评批复与验收", "项目备案/产能置换公示"])[:3])
    rows = [
        ("", ""),
        ("一、这份表解决什么问题", ""),
        ("", "内贸采购最怕把贸易商当厂家：报价、账期都谈成了，最后发现对方只是调货，质量、交期、发票主体全都对不上。"
             "本工作簿不靠“经营范围”和“厂家直销”下结论，而是把材料分成三组：能直接指向装置的硬证据、只能说明在做生意的旁证、以及最容易被误采信的材料。"),
        ("", f"{len(CASES)} 个案例演示同一套方法的不同落点：{case_brief}。"),
        ("", ""),
        ("二、五步使用法", ""),
        ("STEP 1", f"录入企业与产品：企业全名、统一社会信用代码、目标产品与规格（{PRODUCT_SPEC or PRODUCT}）。"),
        ("STEP 2", f"跑直接证据：{regimes_brief}；上市公司产量、非计划停产公告。"),
        ("STEP 3", "补间接证据：官网产品页、自营商城、交易所交割厂库、协会名录、原料采购、生产岗位招聘、专利、行业报道。"),
        ("STEP 4", "剔除伪证据：把营业执照经营范围、“厂家直销”、注册资本、可大量供货、单张照片单独归入“不构成证据”，不计分。"),
        ("STEP 5", "按 Q1→Q4 判定，输出四类结论之一；证据不足就写“暂无法确认”，并按 06 表发索取清单。"),
    ]
    r = 5
    for a, b in rows:
        ws.cell(row=r, column=1, value=None)
        if a.startswith("一、") or a.startswith("二、"):
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
            cell = ws.cell(row=r, column=1, value=a)
            cell.font = Font(name="微软雅黑", size=12, bold=True, color=NAVY)
            cell.fill = solid(GOLD_L)
            cell.alignment = Alignment(vertical="center", horizontal="left", indent=1)
            ws.row_dimensions[r].height = 28
        elif a:
            c1 = ws.cell(row=r, column=1, value=a)
            c1.font = Font(name="Consolas", size=10, bold=True, color=GOLD)
            c1.alignment = Alignment(vertical="top", horizontal="left", indent=1)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
            c2 = ws.cell(row=r, column=2, value=b)
            c2.font = Font(name="微软雅黑", size=9.6, color="334155")
            c2.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left", indent=1)
            ws.row_dimensions[r].height = max(20, 15 * math.ceil(len(b) / 92))
        elif b:
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
            c2 = ws.cell(row=r, column=2, value=b)
            c2.font = Font(name="微软雅黑", size=9.6, color="334155")
            c2.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left", indent=1)
            ws.row_dimensions[r].height = max(20, 15 * math.ceil(len(b) / 92))
        r += 1

    # 三分法表
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(row=r, column=1, value="三、证据三分法")
    c.font = Font(name="微软雅黑", size=12, bold=True, color=NAVY)
    c.fill = solid(GOLD_L)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[r].height = 28
    r += 1
    trip = [
        ("A 直接生产证据", "能独立指向“装置存在且在运行”", (PROFILE.get("regimes") or ["排污许可证（对应行业类别）"])[0] + "；环评批复与验收、项目备案/产能置换、上市公司产量、非计划停产公告", GREEN),
        ("B 间接业务证据", "说明在做这门生意，不能单独证明自产", "官网产品页、自营商城、交易所交割厂库、协会名录、原料采购、生产岗位招聘、专利、行业报道", NAVY2),
        ("C 不构成证据", "容易被误采信，采信会出错", "营业执照经营范围、“厂家直销”、注册资本、可大量供货、单张无定位照片、口头承诺", "94A3B8"),
    ]
    for name, use, items, color in trip:
        c1 = ws.cell(row=r, column=2, value=name)
        c1.font = Font(name="微软雅黑", size=10, bold=True, color=color)
        c1.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        c2 = ws.cell(row=r, column=3, value=use)
        c2.font = Font(name="微软雅黑", size=9.4, color="334155")
        c2.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=8)
        c3 = ws.cell(row=r, column=5, value=items)
        c3.font = Font(name="微软雅黑", size=9.2, color="475569")
        c3.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        for cc in range(1, 9):
            ws.cell(row=r, column=cc).border = BORDER
            ws.cell(row=r, column=cc).fill = solid("FBFCFD")
        ws.row_dimensions[r].height = 46
        r += 1

    # 判定规则
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(row=r, column=1, value="四、判定顺序（不能跳步）")
    c.font = Font(name="微软雅黑", size=12, bold=True, color=NAVY)
    c.fill = solid(GOLD_L)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[r].height = 28
    r += 1
    for i, h in enumerate(["", "步骤", "问题", "判定依据", "", "", "是 →", "否 →"], start=1):
        pass
    hdr = ["", "步骤", "问题", "判定依据（命中任一即可）", "", "", "是 →", "否 →"]
    for i, h in enumerate(hdr, start=1):
        cell = ws.cell(row=r, column=i, value=h if h else None)
        cell.font = Font(name="微软雅黑", size=9, bold=True, color="FFFFFF")
        cell.fill = solid(NAVY2)
        cell.alignment = CENTER
        cell.border = BORDER
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    ws.row_dimensions[r].height = 24
    r += 1
    for rule in VERDICT_RULES:
        ws.cell(row=r, column=1, value="")
        c1 = ws.cell(row=r, column=2, value=rule["step"])
        c1.font = Font(name="Consolas", size=9, bold=True, color=GOLD)
        c1.alignment = CENTER
        c2 = ws.cell(row=r, column=3, value=rule["question"])
        c2.font = Font(name="微软雅黑", size=9.2, bold=True, color=INK)
        c2.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        c3 = ws.cell(row=r, column=4, value=rule["detail"])
        c3.font = Font(name="微软雅黑", size=9, color="475569")
        c3.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        c4 = ws.cell(row=r, column=7, value=rule["yes"])
        c5 = ws.cell(row=r, column=8, value=rule["no"])
        for cc in (c4, c5):
            cc.font = Font(name="微软雅黑", size=9, color="334155")
            cc.alignment = CENTER
        for cc in range(1, 9):
            ws.cell(row=r, column=cc).border = BORDER
        ws.row_dimensions[r].height = 44
        r += 1

    # 四类结论
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(row=r, column=1, value="五、四类结论与含义")
    c.font = Font(name="微软雅黑", size=12, bold=True, color=NAVY)
    c.fill = solid(GOLD_L)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[r].height = 28
    r += 1
    for i, h in enumerate(["", "结论", "含义", "", "", "典型证据", "", ""], start=1):
        cell = ws.cell(row=r, column=i, value=h if h else None)
        cell.font = Font(name="微软雅黑", size=9, bold=True, color="FFFFFF")
        cell.fill = solid(NAVY2)
        cell.alignment = CENTER
        cell.border = BORDER
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    ws.merge_cells(start_row=r, start_column=6, end_row=r, end_column=8)
    r += 1
    ev_hint = {
        "生产厂家": "；".join((PROFILE.get("regimes") or [])[:2]) or "对应行业类别的许可 + 环评产能 + 公开产量",
        "分装或复配": "分装类许可/备案 + 后处理设备清单 + 外购成品发票",
        "贸易经销": "贸易商厂库/代理授权 + 无排污许可 + 背靠背发票",
        "证据不足暂无法确认": "仅有执照、报价单、无定位照片；既无硬证据也无贸易侧证",
    }
    verdict_rows = [(v, m["meaning"], ev_hint.get(v, "")) for v, m in VERDICT_META.items()]
    for v, meaning, ev in verdict_rows:
        for cc in range(1, 9):
            ws.cell(row=r, column=cc).border = BORDER
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
        ws.merge_cells(start_row=r, start_column=6, end_row=r, end_column=8)
        c1 = ws.cell(row=r, column=2, value=v)
        fill, color = VERDICT_FILL[v]
        c1.font = Font(name="微软雅黑", size=9.4, bold=True, color=color)
        c1.fill = solid(fill)
        c1.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c2 = ws.cell(row=r, column=3, value=meaning)
        c2.font = Font(name="微软雅黑", size=9, color="334155")
        c2.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        c3 = ws.cell(row=r, column=6, value=ev)
        c3.font = Font(name="微软雅黑", size=8.8, color="475569")
        c3.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        ws.row_dimensions[r].height = 40
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(row=r, column=1,
                value="免责：本工作簿为采购尽调辅助工具，不构成法律意见；“证据充分度”衡量证据链完整度，不代表企业信用或产品质量。"
                      "脱敏样例不对应任何真实企业。数据截止 2026-10-19，正式签约前应重新核验许可与名单。")
    c.font = Font(name="微软雅黑", size=8.8, color="94A3B8")
    c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[r].height = 40

    # ============================================================ 01 核验总表
    ws = wb.create_sheet("01_核验总表")
    setup_sheet(ws, GREEN)
    h1 = ["序号", "企业名称", "产品 / 规格", "核验结论", "证据充分度", "置信度", "生产地址（公开）",
          "公开产能", "工艺路线", "直接证据", "间接证据", "排除项", "关键缺口 / 风险", "建议动作", "报告日期"]
    w1 = [5, 27, 22, 16, 9, 7, 30, 25, 15, 8, 8, 7, 38, 38, 11]
    title_block(ws, len(h1), "01 · 核验总表",
                f"{len(CASES)} 家供应商的核验结论与证据计数（{PRODUCT}）；计数列由 02/03/04 三张明细表自动汇总。",
                f"报告编号 {REPORT_ID}    数据截止 {REPORT_DATE}    ★ 可直接在空白行套用：填企业名 → 明细表打标签 → 计数与分数自动更新")
    header_row(ws, 4, h1, w1, height=34)

    total_row_05 = 5 + len(DIMENSIONS)
    for i, c in enumerate(CASES, start=1):
        row = 4 + i
        key_gap = c["gaps"][0] if c["gaps"] else ""
        score_col = get_column_letter(2 + i)
        vals = [i, c["company"], c["product"], c["verdict"], f"='05_评分模型'!{score_col}{total_row_05}",
                c["confidence"], c["addr"], c["capacity"], c["process"],
                f"=COUNTIFS('02_直接生产证据'!$B$4:$B$200,$B{row})",
                f"=COUNTIFS('03_间接业务证据'!$B$4:$B$200,$B{row})",
                f"=COUNTIFS('04_不构成证据'!$B$4:$B$200,$B{row})",
                key_gap, c["next_action"], REPORT_DATE]
        body_row(ws, row, vals, w1, zebra=(i % 2 == 0), center_cols=(1, 4, 5, 6, 10, 11, 12, 15), bold_cols=(2,))
        fill, color = VERDICT_FILL[c["verdict"]]
        vc = ws.cell(row=row, column=4)
        vc.fill = solid(fill)
        vc.font = Font(name="微软雅黑", size=9.2, bold=True, color=color)
        ws.cell(row=row, column=2).font = Font(name="微软雅黑", size=9.4, bold=True, color=INK)
        ws.cell(row=row, column=5).font = Font(name="Consolas", size=11, bold=True, color=NAVY)

    last = 4 + len(CASES)
    ws.auto_filter.ref = f"A4:O{last}"
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(VERDICT_META), allow_blank=True,
                        showDropDown=False)
    dv.error = "请选择四类结论之一"
    dv.errorTitle = "结论不规范"
    ws.add_data_validation(dv)
    dv.add(f"D5:D40")

    ws.conditional_formatting.add(f"D5:D40", FormulaRule(formula=['$D5="生产厂家"'], fill=solid(GREEN_L),
                                                         font=Font(color=GREEN, bold=True)))
    ws.conditional_formatting.add(f"D5:D40", FormulaRule(formula=['$D5="分装或复配"'], fill=solid(AMBER_L),
                                                         font=Font(color=AMBER, bold=True)))
    ws.conditional_formatting.add(f"D5:D40", FormulaRule(formula=['$D5="贸易经销"'], fill=solid(RED_L),
                                                         font=Font(color=RED, bold=True)))
    ws.conditional_formatting.add(f"D5:D40", FormulaRule(formula=['$D5="证据不足暂无法确认"'], fill=solid(GRAY_L),
                                                         font=Font(color="475569", bold=True)))
    ws.conditional_formatting.add(f"E5:E40", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100,
                                                         color="5B8DB8", showValue=True))
    ws.print_title_rows = "4:4"

    # ============================================================ 02 / 03 证据
    def evidence_sheet(name, tab, title, subtitle, groups):
        ws = wb.create_sheet(name)
        setup_sheet(ws, tab)
        h = ["证据编号", "企业名称", "证据类别", "证据名称", "证据内容 / 原文摘录", "来源机构",
             "来源链接", "发布 / 有效期", "证据强度", "采信理由（为什么算 / 为什么不算）", "对应结论"]
        w = [9, 24, 11, 30, 52, 24, 40, 13, 9, 44, 14]
        title_block(ws, len(h), title, subtitle, f"报告编号 {REPORT_ID}    数据截止 {REPORT_DATE}    证据强度：●●● 强 / ●●○ 中 / ●○○ 弱")
        header_row(ws, 4, h, w, height=34)
        r = 5
        n = 0
        for c in CASES:
            items = c[groups]
            for it in items:
                n += 1
                vals = [it["code"], c["company"], it.get("cat", "—"), it["title"], it.get("quote", ""),
                        it.get("source", "对方提供"), it.get("url", ""), it.get("date", "—"),
                        STRENGTH_FILL[it["strength"]][2], it["why"], c["verdict"]]
                body_row(ws, r, vals, w, zebra=(n % 2 == 0), center_cols=(1, 3, 9, 11))
                f, col, _ = STRENGTH_FILL[it["strength"]]
                sc = ws.cell(row=r, column=9)
                sc.fill = solid(f)
                sc.font = Font(name="微软雅黑", size=8.6, bold=True, color=col)
                ws.cell(row=r, column=1).font = Font(name="Consolas", size=9, bold=True, color=NAVY)
                ws.cell(row=r, column=10).font = Font(name="微软雅黑", size=8.8, color="475569")
                if it.get("url"):
                    uc = ws.cell(row=r, column=7)
                    uc.hyperlink = it["url"]
                    uc.font = Font(name="Consolas", size=8, color="0F5C8C", underline="single")
                ws.cell(row=r, column=11).font = Font(name="微软雅黑", size=8.6, color="475569")
                r += 1
        ws.auto_filter.ref = f"A4:K{r-1}"
        ws.print_title_rows = "4:4"
        return ws


    evidence_sheet("02_直接生产证据", GREEN, "02 · 直接生产证据",
                   "只有这一组能独立支撑“装置存在且在运行”。判定时只看 A 组；B 组用于交叉，C 组不计分。",
                   "direct")
    evidence_sheet("03_间接业务证据", NAVY2, "03 · 间接业务证据",
                   f"能证明“确实在做{PRODUCT}这门生意”，但不能单独证明自产，必须与 A 组联读。",
                   "indirect")

    # 04 不构成证据
    ws = wb.create_sheet("04_不构成证据")
    setup_sheet(ws, "94A3B8")
    h = ["编号", "企业名称", "材料 / 常见话术", "对方常见表述", "为什么不算证据", "正确用法 / 应换取的替代证据"]
    w = [8, 26, 30, 46, 56, 46]
    title_block(ws, len(h), "04 · 不构成证据（排除项）",
                "这些材料不是“没用”，而是“不能用来证明自产”。把它们单独归档，可以避免把贸易商误判成厂家。",
                f"报告编号 {REPORT_ID}    数据截止 {REPORT_DATE}    本表不计入证据充分度")
    header_row(ws, 4, h, w, height=34)
    r = 5
    n = 0
    for c in CASES:
        for it in c["excluded"]:
            n += 1
            vals = [it["code"], c["company"], it["title"], it.get("quote", ""), it["why"],
                    "见 06 表对应材料：排污许可 / 环评 / 磅单 / 发票 / 视频验厂"]
            body_row(ws, r, vals, w, zebra=(n % 2 == 0), center_cols=(1,))
            ws.cell(row=r, column=1).font = Font(name="Consolas", size=9, bold=True, color="94A3B8")
            ws.cell(row=r, column=3).font = Font(name="微软雅黑", size=9.2, bold=True, color="475569")
            r += 1
    ws.auto_filter.ref = f"A4:F{r-1}"
    ws.print_title_rows = "4:4"

    # ============================================================ 05 评分模型
    ws = wb.create_sheet("05_评分模型")
    setup_sheet(ws, GOLD, freeze="C4")
    ncase = len(CASES)
    last_col = 2 + ncase
    note_col = last_col + 1
    h = ["评分维度", "权重"] + [c["short"] for c in CASES] + ["评分要点"]
    w = [24, 8] + [max(11, min(18, 7 + len(c["short"]))) for c in CASES] + [62]
    title_block(ws, len(h), "05 · 证据充分度模型（100 分制）",
                f"分数衡量“证据链完整度”，不是真假概率。同一套权重，{ncase} 个案例横向可比；现场核验未完成时，该维度记 0 分。",
                f"报告编号 {REPORT_ID}    ★ 修改 02/03 明细后，本表与总表分数需重新计算（Excel 会自动重算）")
    header_row(ws, 4, h, w, height=32)
    for i, d in enumerate(DIMENSIONS):
        row = 5 + i
        vals = [d["name"], d["weight"]] + [c["dims"][i] for c in CASES] + [d["detail"]]
        body_row(ws, row, vals, w, zebra=(i % 2 == 1), center_cols=tuple(range(2, last_col + 1)), bold_cols=(1,))
        for col in range(3, last_col + 1):
            ws.cell(row=row, column=col).font = Font(name="Consolas", size=10.5, color=INK)
        ws.cell(row=row, column=2).font = Font(name="Consolas", size=9.5, color=MUTED)

    total_row = 5 + len(DIMENSIONS)
    dim_last = 4 + len(DIMENSIONS)
    ws.cell(row=total_row, column=1, value="证据充分度合计")
    ws.cell(row=total_row, column=2, value=f"=SUM(B5:B{dim_last})")
    for col in range(3, last_col + 1):
        L = get_column_letter(col)
        ws.cell(row=total_row, column=col, value=f"=SUM({L}5:{L}{dim_last})")
    ws.cell(row=total_row, column=note_col, value="≥70：可判生产厂家；40—69：需补证；<40：多为贸易/分装，或证据不足")
    for col in range(1, note_col + 1):
        cell = ws.cell(row=total_row, column=col)
        cell.border = BORDER
        cell.fill = solid(GOLD_L)
        cell.font = Font(name="微软雅黑", size=10, bold=True, color=NAVY)
        if col == 1 or col == note_col:
            cell.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True, indent=1)
        else:
            cell.alignment = CENTER
    ws.row_dimensions[total_row].height = 34
    for col in range(3, last_col + 1):
        ws.cell(row=total_row, column=col).font = Font(name="Consolas", size=12, bold=True, color=NAVY)

    concl_row = total_row + 1
    ws.cell(row=concl_row, column=1, value="判定结论")
    ws.cell(row=concl_row, column=2, value="—")
    for i, c in enumerate(CASES):
        cell = ws.cell(row=concl_row, column=3 + i, value=c["verdict"])
        fill, color = VERDICT_FILL[c["verdict"]]
        cell.fill = solid(fill)
        cell.font = Font(name="微软雅黑", size=8.8, bold=True, color=color)
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.cell(row=concl_row, column=note_col, value="结论由 Q1→Q4 规则决定，分数只作辅助与横向比较")
    for col in range(1, note_col + 1):
        ws.cell(row=concl_row, column=col).border = BORDER
        if col in (1, note_col):
            ws.cell(row=concl_row, column=col).font = Font(name="微软雅黑", size=9, bold=True, color=NAVY)
            ws.cell(row=concl_row, column=col).alignment = Alignment(wrap_text=True, vertical="center", horizontal="left", indent=1)
    ws.cell(row=concl_row, column=2).alignment = CENTER
    ws.row_dimensions[concl_row].height = 30

    # 说明块
    r = concl_row + 2
    notes = [
        ("评分口径", "强证据（●●●）指政府许可/备案、交易所或协会名录、上市公司审计披露、可复现第三方记录；"
                     "中证据（●●○）指可与第三方互证的企业官网信息、行业媒体、招聘/招标；弱证据（●○○）指自述宣传、单张照片、口头承诺。"),
        ("一票否决", "排污许可行业类别与目标产品不符、且无对应环评/备案 → 不可能是该产品生产厂，直接进入 Q3/Q4；"
                     "反之，只要有任一硬证据，也不能仅凭“没找到官网”否定其生产。"),
        ("现场权重", "现场与第三方核验占 10 分，未做就是 0 分。这不是扣分，而是提醒：线上证据再全，也不能替代一次不预约的视频验厂。"),
    ]
    for k, v in notes:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        c1 = ws.cell(row=r, column=1, value=k)
        c1.font = Font(name="微软雅黑", size=9.5, bold=True, color=GOLD)
        c1.alignment = Alignment(vertical="top", horizontal="left", indent=1)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=note_col)
        c2 = ws.cell(row=r, column=3, value=v)
        c2.font = Font(name="微软雅黑", size=9, color="475569")
        c2.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
        ws.row_dimensions[r].height = max(24, 14.5 * math.ceil(len(v) / 96))
        r += 1

    ws.conditional_formatting.add(f"C5:{get_column_letter(last_col)}{dim_last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=30,
                                                        color="C9A227", showValue=True))
    ws.print_title_rows = "4:4"

    # ============================================================ 06 待索取材料
    ws = wb.create_sheet("06_待索取材料")
    setup_sheet(ws, "2F5F8A")
    h = ["编号", "材料", "优先级", "核验目的", "关键看点", "索取话术", "适用场景", "状态"]
    w = [7, 32, 8, 24, 36, 50, 16, 12]
    title_block(ws, len(h), "06 · 待索取材料清单（12 项）",
                "P0 拿不到，不进入打款与长协；话术可直接复制给业务员。勾选“状态”即为已获取。",
                f"报告编号 {REPORT_ID}    数据截止 {REPORT_DATE}    优先级：P0 必取 / P1 视场景 / P2 合规参考")
    header_row(ws, 4, h, w, height=32)
    for i, m in enumerate(MATERIALS, start=1):
        row = 4 + i
        vals = [m["id"], m["name"], m["priority"], m["purpose"], m["look"], m["script"], m["scene"], "未获取"]
        body_row(ws, row, vals, w, zebra=(i % 2 == 0), center_cols=(1, 3, 8), bold_cols=(2,))
        pc = ws.cell(row=row, column=3)
        pc.font = Font(name="Consolas", size=9.5, bold=True,
                       color={"P0": RED, "P1": AMBER, "P2": MUTED}[m["priority"]])
        pc.fill = solid({"P0": RED_L, "P1": AMBER_L, "P2": GRAY_L}[m["priority"]])
        ws.cell(row=row, column=1).font = Font(name="Consolas", size=9, bold=True, color=NAVY)
    ws.auto_filter.ref = f"A4:H{4+len(MATERIALS)}"
    dv2 = DataValidation(type="list", formula1='"未获取,已获取,不适用"', allow_blank=True, showDropDown=False)
    ws.add_data_validation(dv2)
    dv2.add(f"H5:H20")
    ws.conditional_formatting.add("H5:H20", FormulaRule(formula=['$H5="已获取"'], fill=solid(GREEN_L),
                                                         font=Font(color=GREEN, bold=True)))
    ws.conditional_formatting.add("H5:H20", FormulaRule(formula=['$H5="未获取"'], fill=solid("FFF7E6"),
                                                         font=Font(color="B45309")))
    ws.print_title_rows = "4:4"

    # ============================================================ 07 现场验厂
    ws = wb.create_sheet("07_现场验厂")
    setup_sheet(ws, "0F7B5F")
    h = ["序号", "检查项", "核验方法", "合格标准", "常见造假信号", "权重"]
    w = [6, 20, 38, 42, 40, 8]
    title_block(ws, len(h), "07 · 现场 / 视频验厂脚本",
                "不预约、不剪辑、按顺序走：门牌 → 装置 → 原料 → 包装 → 地磅 → 中控 → 三废。",
                f"报告编号 {REPORT_ID}    数据截止 {REPORT_DATE}    建议全程录屏并保留时间戳")
    header_row(ws, 4, h, w, height=30)
    for i, o in enumerate(ONSITE, start=1):
        row = 4 + i
        body_row(ws, row, [i, o["item"], o["method"], o["pass"], o["fake"], 10], w,
                 zebra=(i % 2 == 0), center_cols=(1, 6), bold_cols=(2,))
        ws.cell(row=row, column=5).font = Font(name="微软雅黑", size=8.8, color=RED)
        ws.row_dimensions[row].height = max(42, ws.row_dimensions[row].height or 42)
    ws.print_title_rows = "4:4"

    # ============================================================ 08 案例对照
    ws = wb.create_sheet("08_案例对照")
    setup_sheet(ws, NAVY2)
    h = ["企业", "结论", "充分度", "直接", "间接", "排除", "关键硬证据", "关键缺口 / 下一步", "置信度"]
    w = [26, 15, 9, 7, 7, 7, 40, 44, 9]
    title_block(ws, len(h), f"08 · {len(CASES)} 个案例横向对照",
                "同一套方法，不同的证据结构，落点自然不同：有的能定“厂家”，有的只能定“贸易”，有的必须留白。",
                f"报告编号 {REPORT_ID}    数据截止 {REPORT_DATE}")
    header_row(ws, 4, h, w, height=30)
    for i, c in enumerate(CASES, start=1):
        row = 4 + i
        hard = "；".join([x["title"] for x in c["direct"][:3]]) or "无（0 条直接生产证据）"
        vals = [c["company"], c["verdict"], c["score"], len(c["direct"]), len(c["indirect"]), len(c["excluded"]),
                hard, c["next_action"], c["confidence"]]
        body_row(ws, row, vals, w, zebra=(i % 2 == 0), center_cols=(2, 3, 4, 5, 6, 9), bold_cols=(1,))
        fill, color = VERDICT_FILL[c["verdict"]]
        vc = ws.cell(row=row, column=2)
        vc.fill = solid(fill)
        vc.font = Font(name="微软雅黑", size=9, bold=True, color=color)
        ws.cell(row=row, column=3).font = Font(name="Consolas", size=12, bold=True, color=NAVY)
    ws.print_title_rows = "4:4"

    # ============================================================ 09 数据来源
    ws = wb.create_sheet("09_数据来源")
    setup_sheet(ws, "64748B")
    h = ["编号", "来源", "类型", "链接", "引用内容", "访问日期"]
    w = [7, 40, 12, 55, 50, 12]
    title_block(ws, len(h), "09 · 数据来源与可复核性",
                "只采信可公开复核的来源；企业官网信息标注为“自述”，须与许可/公告/交易所文件交叉。",
                f"报告编号 {REPORT_ID}    数据截止 {REPORT_DATE}    链接失效时，可按“机构 + 标题 + 日期”二次检索")
    header_row(ws, 4, h, w, height=30)
    for i, (sid, src, typ, url, quote) in enumerate(SOURCES, start=1):
        row = 4 + i
        body_row(ws, row, [sid, src, typ, url, quote, REPORT_DATE], w,
                 zebra=(i % 2 == 0), center_cols=(1, 3, 6))
        uc = ws.cell(row=row, column=4)
        uc.hyperlink = url
        uc.font = Font(name="Consolas", size=7.8, color="0F5C8C", underline="single")
        ws.cell(row=row, column=1).font = Font(name="Consolas", size=9, bold=True, color=NAVY)
    ws.auto_filter.ref = f"A4:F{4+len(SOURCES)}"
    ws.print_title_rows = "4:4"

    wb.properties.title = f"{META.get('title', '供应商真伪核验')}工作簿"
    wb.properties.subject = "供应商验厂 / 生产证据三分法"
    wb.properties.creator = "DSH 供应商核验台"
    wb.properties.description = "、".join(c["short"] for c in CASES)

    wb.calculation.fullCalcOnLoad = True
    wb.save(out)
    print("[ok] xlsx -> %s (%d bytes)" % (out, os.path.getsize(out)))
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="生成 Excel 核验工作簿")
    ap.add_argument("input", help="input.json")
    ap.add_argument("-o", "--outdir", default=".", help="输出目录")
    a = ap.parse_args()
    build(load_doc(a.input), a.outdir)
