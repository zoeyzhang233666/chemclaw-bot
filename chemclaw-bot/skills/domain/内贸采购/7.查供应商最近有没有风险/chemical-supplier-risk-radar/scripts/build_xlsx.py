# -*- coding: utf-8 -*-
"""Build a supplier-risk Excel workbook from a data.json (product-agnostic).

Usage:
    python build_xlsx.py data.json [out.xlsx]
"""
import json
import re
import sys
import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference
from openpyxl.worksheet.page import PageMargins

from normalize import normalize

BASE = Path(__file__).resolve().parent
DATA_PATH = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BASE / "data.json"
DATA = normalize(json.loads(DATA_PATH.read_text(encoding="utf-8")))
META = DATA["meta"]
PRODUCT = META.get("product", "化工品")
PRODUCT_EN = META.get("product_en", "CHEMICAL").upper()
TITLE = META.get("title", f"{PRODUCT}供应商近期风险雷达")
FIN_PERIOD = META.get("financial_period", "本期")
PERIOD_TAG = META.get("period_tag") or META.get("query_date", "")[:7] or "report"
WINDOWS = META["windows"]
DEFAULT_KEY = META.get("window_default", "6m")
DEFAULT_WIN = WINDOWS[DEFAULT_KEY]
WIN_START = datetime.date.fromisoformat(DEFAULT_WIN["start"])
WIN_END = datetime.date.fromisoformat(DEFAULT_WIN["end"])
EVENTS = DATA["events"]
N_TOTAL = len(EVENTS)
N_DEFAULT = sum(1 for e in EVENTS if WIN_START <= datetime.date.fromisoformat(e["date"]) <= WIN_END)
N_OUT = N_TOTAL - N_DEFAULT
OUTSIDE_DATES = " / ".join(sorted({e["date"] for e in EVENTS if not (WIN_START <= datetime.date.fromisoformat(e["date"]) <= WIN_END)}))
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path.cwd() / f"{TITLE}_{PERIOD_TAG}.xlsx"

# ---------------------------------------------------------------- palette
NAVY = "17324D"
INK = "132A3A"
MUTED = "5A6B78"
PAPER = "F6F3EC"
CARD = "FFFDF8"
LINE = "D9D2C3"
TEAL = "0F766E"
AMBER = "A9761F"
RED = "A63A3A"
GREEN = "3F6B4A"
SLATE = "64798A"
INDIGO = "4F559C"

FONT_CN = "微软雅黑"

THIN = Side(style="thin", color=LINE)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

FILL_HEADER = PatternFill("solid", fgColor=NAVY)
FILL_SUB = PatternFill("solid", fgColor="EDE7DA")
FILL_CARD = PatternFill("solid", fgColor=CARD)
FILL_BAND = PatternFill("solid", fgColor="FBF8F0")
FILL_TOTAL = PatternFill("solid", fgColor="E9E2D2")

SEV_FILL = {
    "高": PatternFill("solid", fgColor="F3DADA"),
    "中": PatternFill("solid", fgColor="F9ECD2"),
    "低": PatternFill("solid", fgColor="E7EEF2"),
    "正向": PatternFill("solid", fgColor="E2EFE3"),
}
SEV_FONT = {
    "高": Font(name=FONT_CN, size=10, bold=True, color="8B1E1E"),
    "中": Font(name=FONT_CN, size=10, bold=True, color="7A4E12"),
    "低": Font(name=FONT_CN, size=10, bold=True, color="33556B"),
    "正向": Font(name=FONT_CN, size=10, bold=True, color="2F5A3A"),
}
RISK_FILL = {
    "高": PatternFill("solid", fgColor="F3DADA"),
    "中": PatternFill("solid", fgColor="FBEED3"),
    "中低": PatternFill("solid", fgColor="EAF0F3"),
    "低": PatternFill("solid", fgColor="E3F0E2"),
}
RISK_FONT = {
    "高": Font(name=FONT_CN, size=10, bold=True, color="8B1E1E"),
    "中": Font(name=FONT_CN, size=10, bold=True, color="7A4E12"),
    "中低": Font(name=FONT_CN, size=10, bold=True, color="33556B"),
    "低": Font(name=FONT_CN, size=10, bold=True, color="2F5A3A"),
}

CAT_ORDER = ["工商", "司法", "处罚", "安全环保", "经营动态"]


def cell(ws, row, col, value, *, bold=False, size=10, color=INK, fill=None,
         align="left", wrap=True, border=True, italic=False, name=FONT_CN):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(name=name, size=size, bold=bold, color=color, italic=italic)
    c.alignment = Alignment(horizontal=align, vertical="top" if wrap else "center", wrap_text=wrap)
    if fill:
        c.fill = fill
    if border:
        c.border = BORDER
    return c


def header_row(ws, row, headers, widths=None, height=30):
    for i, h in enumerate(headers, start=1):
        c = cell(ws, row, i, h, bold=True, size=10, color="FFFFFF", fill=FILL_HEADER, align="center", wrap=True)
        c.border = Border(left=Side(style="thin", color="2C4A63"),
                          right=Side(style="thin", color="2C4A63"),
                          top=Side(style="thin", color="2C4A63"),
                          bottom=Side(style="thin", color="2C4A63"))
    ws.row_dimensions[row].height = height
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def header_at(ws, row, start_col, headers, height=26):
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=start_col + i, value=h)
        c.font = Font(name=FONT_CN, size=10, bold=True, color="FFFFFF")
        c.fill = FILL_HEADER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(left=Side(style="thin", color="2C4A63"),
                          right=Side(style="thin", color="2C4A63"),
                          top=Side(style="thin", color="2C4A63"),
                          bottom=Side(style="thin", color="2C4A63"))
    ws.row_dimensions[row].height = height


def section(ws, row, text, span=8, start_col=1):
    c = ws.cell(row=row, column=start_col, value=text)
    c.font = Font(name=FONT_CN, size=13, bold=True, color=NAVY)
    c.alignment = Alignment(vertical="center")
    c.border = Border(bottom=Side(style="medium", color=NAVY))
    ws.merge_cells(start_row=row, start_column=start_col, end_row=row, end_column=start_col + span - 1)
    ws.row_dimensions[row].height = 26


def page_setup(ws, landscape=True, fit_width=1, print_area=None):
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = fit_width
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.35, right=0.35, top=0.45, bottom=0.45)
    if print_area:
        ws.print_area = print_area


wb = Workbook()
wb.properties.title = f"{TITLE}（{PERIOD_TAG}）"
wb.properties.subject = META.get("subtitle", "内贸采购 · 供应商准入与续约前的公开风险扫描")
wb.properties.creator = "采购风险雷达 · 公开信息检索"
wb.properties.keywords = f"{PRODUCT}, 供应商风险, 采购, 尽调, 行政处罚, 停产"

# =====================================================================
# 00 COVER
# =====================================================================
ws = wb.active
ws.title = "00_封面"
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = NAVY
for col, w in {"A": 2.5, "B": 26, "C": 40, "D": 40, "E": 2.5}.items():
    ws.column_dimensions[col].width = w

ws.merge_cells("B2:E2")
c = ws["B2"]
c.value = TITLE
c.font = Font(name=FONT_CN, size=30, bold=True, color=NAVY)
c.alignment = Alignment(vertical="center")
ws.row_dimensions[2].height = 44

ws.merge_cells("B3:E3")
c = ws["B3"]
c.value = META.get("subtitle", "内贸采购 · 供应商准入与续约前的公开风险扫描")
c.font = Font(name=FONT_CN, size=13, color=MUTED)
ws.row_dimensions[3].height = 24

ws.merge_cells("B4:E4")
c = ws["B4"]
c.value = f"SUPPLIER RISK SCAN  /  {PRODUCT_EN}  /  CHINA DOMESTIC PROCUREMENT"
c.font = Font(name="Georgia", size=9, color=TEAL, bold=True)
ws.row_dimensions[4].height = 20

for col in range(2, 6):
    ws.cell(row=5, column=col).fill = PatternFill("solid", fgColor=NAVY)
ws.row_dimensions[5].height = 3

section(ws, 7, "报告信息", span=4, start_col=2)

switch_labels = " / ".join(w["label"] for k, w in WINDOWS.items() if k != DEFAULT_KEY)
processes = "、".join(dict.fromkeys(
    p.strip() for s in DATA["suppliers"]
    for p in re.split(r"\s*[+＋/]\s*", str(s.get("process", "")))
    if p.strip()
))
supplier_names = "、".join(s["name"] for s in DATA["suppliers"])
event_total_text = f"{N_TOTAL} 条（{DEFAULT_WIN['label']}窗口内 {N_DEFAULT} 条"
event_total_text += f"；窗口外背景 {N_OUT} 条）" if N_OUT else "）"
meta = [
    ("查询产品", f"{META.get('product_full', PRODUCT)}，内贸采购"),
    ("查询日期", f"{META.get('query_time', META.get('query_date', ''))}（北京时间）"),
    ("默认窗口", f"{DEFAULT_WIN['label']}：{DEFAULT_WIN['start']} 至 {DEFAULT_WIN['end']}（可切换 {switch_labels}）"),
    ("供应商范围", f"{len(DATA['suppliers'])} 家：{supplier_names}"),
    ("事件总量", event_total_text),
    ("覆盖工艺", processes),
    ("信息渠道", META.get("channels", "公司公告 / 交易所 / 证监局 / 海关 / 主流财经媒体 / 行业资讯")),
    ("报告性质", META.get("nature", "公开信息桌面检索，辅助采购决策，不替代完整尽调")),
]
r = 8
for k, v in meta:
    cell(ws, r, 2, k, bold=True, color=NAVY, fill=FILL_SUB, border=False)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    cell(ws, r, 3, v, color=INK, border=False)
    ws.row_dimensions[r].height = 30
    r += 1

section(ws, 18, "图例：严重度与方向", span=4, start_col=2)
legend = [
    ("高", "可能影响交付/合规，需在 1—2 周内核实", SEV_FILL["高"], SEV_FONT["高"]),
    ("中", "值得关注，需纳入询价/合同条款", SEV_FILL["中"], SEV_FONT["中"]),
    ("低", "影响有限或常规事项，留痕即可", SEV_FILL["低"], SEV_FONT["低"]),
    ("正向", "公开变化对供应能力偏正面", SEV_FILL["正向"], SEV_FONT["正向"]),
]
r = 19
for level, desc, fill, font in legend:
    cell(ws, r, 2, level, bold=True, fill=fill, align="center")
    ws.cell(row=r, column=2).font = font
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    cell(ws, r, 3, desc, color=MUTED, border=False)
    ws.row_dimensions[r].height = 22
    r += 1

section(ws, 25, "阅读提示", span=4, start_col=2)
tips = [
    "1. 先看“01_风险总览”的风险等级与一句话结论，再进入“02_事件时间线”核对事实与来源。",
    "2. “未检索到公开风险事件”只代表本次公开渠道检索结果，不等于供应商没有风险；窗口外事项请切换到近 1 年。",
    "3. 每条事件都给出“采购关注点”和“待确认问题”，可直接用于询价、准入访谈或合同条款设计。",
    "4. 公开新闻不等于未来断供。本报告不做断供预测，只提示需要进一步确认的业务问题。",
]
r = 26
for t in tips:
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    c = ws.cell(row=r, column=2, value=t)
    c.font = Font(name=FONT_CN, size=10, color=INK)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r].height = 34
    r += 1

ws.merge_cells("B32:E35")
c = ws["B32"]
c.value = (f"免责声明：本报告基于截至 {META.get('query_date', '')} 的公开信息整理，仅供采购决策参考，不构成法律、财务或投资意见。"
          "公开信息可能存在滞后、遗漏或口径差异；“未检索到”不等于“无风险”。建议在准入或续约前补充现场审核、"
          "财务尽调、征信报告与合同条款设计。")
c.font = Font(name=FONT_CN, size=9, color="7A6A55", italic=True)
c.alignment = Alignment(wrap_text=True, vertical="top")
c.fill = PatternFill("solid", fgColor="F1EBDD")
c.border = BORDER
page_setup(ws, landscape=False)

# =====================================================================
# 01 OVERVIEW
# =====================================================================
ws = wb.create_sheet("01_风险总览")
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = RED

ws.merge_cells("A1:N1")
c = ws["A1"]
c.value = "供应商风险总览"
c.font = Font(name=FONT_CN, size=18, bold=True, color=NAVY)
ws.row_dimensions[1].height = 32
ws.merge_cells("A2:N2")
c = ws["A2"]
c.value = f"默认窗口：{DEFAULT_WIN['start']} 至 {DEFAULT_WIN['end']} ｜ 事件计数按“02_事件时间线”中落在窗口内的记录 ｜ 风险等级为采购视角的综合标签，不是信用评级"
c.font = Font(name=FONT_CN, size=9, color=MUTED)
ws.row_dimensions[2].height = 20

headers = ["序号", "供应商", "证券代码", "工艺路线", f"{PRODUCT}产能", "主要基地", "窗口内事件",
           "高", "中", "低", "风险等级", "风险标签", "最近事件日期", "最近事件", "一句话结论"]
widths = [5, 11, 10, 12, 22, 18, 10, 5, 5, 5, 8, 16, 12, 26, 53]
header_row(ws, 4, headers, widths, height=32)

win_start = WIN_START
win_end = WIN_END
events = DATA["events"]
for e in events:
    e["_date"] = datetime.date.fromisoformat(e["date"])
in_window = [e for e in events if win_start <= e["_date"] <= win_end]

supplier_stats = {}
for s in DATA["suppliers"]:
    evs = [e for e in in_window if e["supplier_id"] == s["id"]]
    evs_sorted = sorted(evs, key=lambda x: x["_date"], reverse=True)
    supplier_stats[s["id"]] = {
        "count": len(evs),
        "high": sum(1 for e in evs if e["severity"] == "高"),
        "mid": sum(1 for e in evs if e["severity"] == "中"),
        "low": sum(1 for e in evs if e["severity"] == "低"),
        "latest_date": evs_sorted[0]["date"] if evs_sorted else "—",
        "latest_title": evs_sorted[0]["title"] if evs_sorted else "未检索到公开风险事件",
    }

r = 5
for idx, s in enumerate(DATA["suppliers"], start=1):
    st = supplier_stats[s["id"]]
    band = FILL_BAND if idx % 2 == 0 else None
    cell(ws, r, 1, idx, align="center", fill=band)
    cell(ws, r, 2, s["name"], bold=True, fill=band)
    cell(ws, r, 3, s["code"], align="center", fill=band)
    cell(ws, r, 4, s["process"], fill=band)
    cell(ws, r, 5, s["capacity_short"], fill=band)
    cell(ws, r, 6, s["region"], fill=band)
    cell(ws, r, 7, st["count"], align="center", fill=band)
    cell(ws, r, 8, st["high"], align="center", fill=band)
    cell(ws, r, 9, st["mid"], align="center", fill=band)
    cell(ws, r, 10, st["low"], align="center", fill=band)
    c = cell(ws, r, 11, s["risk_level"], align="center", fill=RISK_FILL.get(s["risk_level"]))
    c.font = RISK_FONT.get(s["risk_level"], c.font)
    cell(ws, r, 12, s["risk_label"], fill=band)
    cell(ws, r, 13, st["latest_date"], align="center", fill=band)
    cell(ws, r, 14, st["latest_title"], fill=band)
    cell(ws, r, 15, s["conclusion"], fill=band)
    ws.row_dimensions[r].height = 58
    r += 1

cell(ws, r, 1, "合计", bold=True, fill=FILL_TOTAL, align="center")
cell(ws, r, 2, f"{len(DATA['suppliers'])} 家", bold=True, fill=FILL_TOTAL)
for col in range(3, 7):
    cell(ws, r, col, "", fill=FILL_TOTAL)
cell(ws, r, 7, len(in_window), bold=True, fill=FILL_TOTAL, align="center")
cell(ws, r, 8, sum(1 for e in in_window if e["severity"] == "高"), bold=True, fill=FILL_TOTAL, align="center")
cell(ws, r, 9, sum(1 for e in in_window if e["severity"] == "中"), bold=True, fill=FILL_TOTAL, align="center")
cell(ws, r, 10, sum(1 for e in in_window if e["severity"] == "低"), bold=True, fill=FILL_TOTAL, align="center")
for col in range(11, 16):
    cell(ws, r, col, "", fill=FILL_TOTAL)
ws.row_dimensions[r].height = 24

ws.freeze_panes = "C5"
ws.auto_filter.ref = f"A4:O{r-1}"
page_setup(ws, print_area=f"A1:O{r}")

# =====================================================================
# 02 TIMELINE
# =====================================================================
ws = wb.create_sheet("02_事件时间线")
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = AMBER

ws.merge_cells("A1:O1")
c = ws["A1"]
c.value = "风险事件时间线（按日期倒序）"
c.font = Font(name=FONT_CN, size=18, bold=True, color=NAVY)
ws.row_dimensions[1].height = 32
ws.merge_cells("A2:O2")
c = ws["A2"]
c.value = (f"共 {N_TOTAL} 条：{DEFAULT_WIN['label']}窗口内 {N_DEFAULT} 条"
           + (f"，窗口外背景 {N_OUT} 条（{OUTSIDE_DATES}）" if N_OUT else "")
           + "。点击“原文链接”可直接打开来源；证据等级 A/B/C 见“07_方法与口径”。")
c.font = Font(name=FONT_CN, size=9, color=MUTED)
ws.row_dimensions[2].height = 22

headers = ["编号", "发生日期", "供应商", "分类", "严重度", "方向", "事件标题",
           "事实摘要", "采购关注点", "待确认问题", "来源", "来源类型", "来源日期", "原文链接", "证据"]
widths = [12, 11, 10, 8, 6, 6, 32, 54, 37, 40, 24, 12, 11, 12, 5]
header_row(ws, 4, headers, widths, height=32)

events_sorted = sorted(events, key=lambda x: x["_date"], reverse=True)
r = 5
for idx, e in enumerate(events_sorted):
    band = FILL_BAND if idx % 2 else None
    cell(ws, r, 1, e["id"], align="center", fill=band)
    c = cell(ws, r, 2, e["_date"], align="center", fill=band)
    c.number_format = "yyyy-mm-dd"
    cell(ws, r, 3, e["supplier"], bold=True, fill=band)
    cell(ws, r, 4, e["category"], align="center", fill=band)
    c = cell(ws, r, 5, e["severity"], align="center", fill=SEV_FILL.get(e["severity"]))
    c.font = SEV_FONT.get(e["severity"], c.font)
    cell(ws, r, 6, e["direction"], align="center", fill=band)
    cell(ws, r, 7, e["title"], bold=True, fill=band, size=9)
    cell(ws, r, 8, e["fact"], fill=band, size=9)
    cell(ws, r, 9, e["why"], fill=band, size=9)
    qs = "\n".join(f"{i+1}. {q}" for i, q in enumerate(e["questions"]))
    cell(ws, r, 10, qs, fill=band, size=9)
    cell(ws, r, 11, e["source"], fill=band)
    cell(ws, r, 12, e["source_type"], fill=band, align="center")
    cell(ws, r, 13, e["source_date"], align="center", fill=band)
    c = cell(ws, r, 14, "打开原文", fill=band, align="center", color="1F5C99", bold=True)
    c.hyperlink = e["url"]
    c.font = Font(name=FONT_CN, size=9, color="1F5C99", underline="single", bold=True)
    cell(ws, r, 15, e["evidence"], align="center", fill=band, bold=True)
    ws.row_dimensions[r].height = 165
    r += 1

ws.freeze_panes = "D5"
ws.auto_filter.ref = f"A4:O{r-1}"
page_setup(ws, print_area=f"A1:O{r}")

# =====================================================================
# 03 SUMMARY
# =====================================================================
ws = wb.create_sheet("03_分类汇总")
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = TEAL
for col, w in {"A": 2, "B": 14, "C": 10, "D": 10, "E": 10, "F": 10, "G": 3,
               "H": 12, "I": 8, "J": 8, "K": 8, "L": 8, "M": 8, "N": 8}.items():
    ws.column_dimensions[col].width = w

ws.merge_cells("B2:F2")
c = ws["B2"]
c.value = "分类汇总"
c.font = Font(name=FONT_CN, size=18, bold=True, color=NAVY)
ws.row_dimensions[2].height = 30
ws.merge_cells("B3:F3")
c = ws["B3"]
c.value = f"统计口径：仅计 {WIN_START} 至 {WIN_END} 的 {N_DEFAULT} 条事件；正向事件计入“低”"
c.font = Font(name=FONT_CN, size=9, color=MUTED)

section(ws, 5, "按风险分类 × 严重度", span=6, start_col=2)
header_at(ws, 6, 2, ["分类", "高", "中", "低", "合计", "占比"])

row = 7
cat_counts = {}
for cat in CAT_ORDER:
    evs = [e for e in in_window if e["category"] == cat]
    cat_counts[cat] = len(evs)
    cell(ws, row, 2, cat, bold=True)
    cell(ws, row, 3, sum(1 for e in evs if e["severity"] == "高"), align="center")
    cell(ws, row, 4, sum(1 for e in evs if e["severity"] == "中"), align="center")
    cell(ws, row, 5, sum(1 for e in evs if e["severity"] == "低"), align="center")
    cell(ws, row, 6, len(evs), bold=True, align="center")
    cell(ws, row, 7, f"{len(evs)/len(in_window):.0%}" if in_window else "0%", align="center")
    ws.row_dimensions[row].height = 22
    row += 1
cell(ws, row, 2, "合计", bold=True, fill=FILL_TOTAL)
cell(ws, row, 3, sum(1 for e in in_window if e["severity"] == "高"), bold=True, align="center", fill=FILL_TOTAL)
cell(ws, row, 4, sum(1 for e in in_window if e["severity"] == "中"), bold=True, align="center", fill=FILL_TOTAL)
cell(ws, row, 5, sum(1 for e in in_window if e["severity"] == "低"), bold=True, align="center", fill=FILL_TOTAL)
cell(ws, row, 6, len(in_window), bold=True, align="center", fill=FILL_TOTAL)
cell(ws, row, 7, "100%", bold=True, align="center", fill=FILL_TOTAL)
ws.row_dimensions[row].height = 24

cell(ws, 6, 9, "分类", bold=True, color="FFFFFF", fill=FILL_HEADER, align="center")
cell(ws, 6, 10, "事件数", bold=True, color="FFFFFF", fill=FILL_HEADER, align="center")
for i, cat in enumerate(CAT_ORDER):
    cell(ws, 7 + i, 9, cat)
    cell(ws, 7 + i, 10, cat_counts[cat], align="center")

chart = BarChart()
chart.type = "bar"
chart.style = 10
chart.title = "事件分类分布"
chart.y_axis.title = "事件数"
data = Reference(ws, min_col=10, min_row=6, max_row=6 + len(CAT_ORDER))
cats = Reference(ws, min_col=9, min_row=7, max_row=6 + len(CAT_ORDER))
chart.add_data(data, titles_from_data=True)
chart.set_categories(cats)
chart.legend = None
chart.height = 7.2
chart.width = 12.5
chart.gapWidth = 55
ws.add_chart(chart, "I13")

section(ws, 14, "按供应商 × 分类", span=7, start_col=2)
header_at(ws, 15, 2, ["供应商", "工商", "司法", "处罚", "安全环保", "经营动态", "合计"])

row = 16
for s in DATA["suppliers"]:
    cell(ws, row, 2, s["name"], bold=True)
    for j, cat in enumerate(CAT_ORDER):
        n = sum(1 for e in in_window if e["supplier_id"] == s["id"] and e["category"] == cat)
        cell(ws, row, 3 + j, n if n else "—", align="center")
    cell(ws, row, 7, supplier_stats[s["id"]]["count"], bold=True, align="center")
    ws.row_dimensions[row].height = 22
    row += 1
cell(ws, row, 2, "合计", bold=True, fill=FILL_TOTAL)
for j, cat in enumerate(CAT_ORDER):
    cell(ws, row, 3 + j, cat_counts[cat], bold=True, align="center", fill=FILL_TOTAL)
cell(ws, row, 7, len(in_window), bold=True, align="center", fill=FILL_TOTAL)

section(ws, row + 1, "读法", span=7, start_col=2)
high_events = [e for e in in_window if e["severity"] == "高"]
top_share = round(cat_counts.get("经营动态", 0) / len(in_window) * 100) if in_window else 0
notes = [
    f"• 窗口内共 {len(in_window)} 条：经营动态 {cat_counts.get('经营动态', 0)} 条（{top_share}%）、工商 {cat_counts.get('工商', 0)} 条、司法 {cat_counts.get('司法', 0)} 条、处罚 {cat_counts.get('处罚', 0)} 条、安全环保 {cat_counts.get('安全环保', 0)} 条。",
    (f"• 高优先级 {len(high_events)} 条；代表性事件：{high_events[0]['supplier']} — {high_events[0]['title']}。" if high_events
     else "• 窗口内未检索到高优先级事件；仍建议按注册地补查信用中国与地方处罚公示。"),
    "• “未检索到”不等于“没有”：信用中国、裁判文书网、执行信息公开网与地方应急/生态环境部门需按供应商注册地补查。",
    "• 经营动态类多为检修/减量、业绩与项目进展，对交付节奏最敏感，也最容易在公开渠道滞后；以厂家书面排产为准。",
]
r = row + 2
for n in notes:
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
    c = ws.cell(row=r, column=2, value=n)
    c.font = Font(name=FONT_CN, size=9.5, color=INK)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r].height = 30
    r += 1

page_setup(ws, print_area=f"A1:N{r-1}")

# =====================================================================
# 04 PROFILES
# =====================================================================
ws = wb.create_sheet("04_供应商画像")
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = INDIGO

ws.merge_cells("A1:N1")
c = ws["A1"]
c.value = "供应商画像"
c.font = Font(name=FONT_CN, size=18, bold=True, color=NAVY)
ws.row_dimensions[1].height = 32
ws.merge_cells("A2:N2")
c = ws["A2"]
c.value = f"产能与财务数据来自公司公告/官网；{FIN_PERIOD} 数据按披露口径；“未披露”表示未公开"
c.font = Font(name=FONT_CN, size=9, color=MUTED)

headers = ["序号", "供应商", "公司全称", "证券代码", "市场", "主要基地", "工艺路线",
           f"{PRODUCT}产能", f"{FIN_PERIOD} 营收", f"{FIN_PERIOD} 净利", "净利同比", "风险等级", "风险标签", "结论 / 覆盖说明"]
widths = [5, 11, 30, 10, 10, 20, 13, 30, 11, 11, 10, 8, 16, 60]
header_row(ws, 4, headers, widths, height=34)

r = 5
for idx, s in enumerate(DATA["suppliers"], start=1):
    band = FILL_BAND if idx % 2 == 0 else None
    cell(ws, r, 1, idx, align="center", fill=band)
    cell(ws, r, 2, s["name"], bold=True, fill=band)
    cell(ws, r, 3, s["full_name"], fill=band)
    cell(ws, r, 4, s["code"], align="center", fill=band)
    cell(ws, r, 5, s["market"], fill=band)
    cell(ws, r, 6, s["region"], fill=band)
    cell(ws, r, 7, s["process"], fill=band)
    cell(ws, r, 8, s["capacity"], fill=band)
    cell(ws, r, 9, s.get("revenue", s.get("h1_revenue", "未披露")), align="center", fill=band)
    cell(ws, r, 10, s.get("profit", s.get("h1_profit", "未披露")), align="center", fill=band)
    cell(ws, r, 11, s["profit_yoy"], align="center", fill=band)
    c = cell(ws, r, 12, s["risk_level"], align="center", fill=RISK_FILL.get(s["risk_level"]))
    c.font = RISK_FONT.get(s["risk_level"], c.font)
    cell(ws, r, 13, s["risk_label"], fill=band)
    cell(ws, r, 14, s["conclusion"] + "\n覆盖：" + s["coverage"], fill=band)
    ws.row_dimensions[r].height = 78
    r += 1

ws.freeze_panes = "C5"
ws.auto_filter.ref = f"A4:N{r-1}"
page_setup(ws, print_area=f"A1:N{r}")

# =====================================================================
# 05 QUESTIONS
# =====================================================================
ws = wb.create_sheet("05_待核实清单")
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = "8B5E3C"

ws.merge_cells("A1:I1")
c = ws["A1"]
c.value = "待核实问题清单"
c.font = Font(name=FONT_CN, size=18, bold=True, color=NAVY)
ws.row_dimensions[1].height = 32
ws.merge_cells("A2:I2")
c = ws["A2"]
c.value = "可直接复制到询价函、准入访谈提纲或合同附件；优先级 P1 建议 5 个工作日内确认"
c.font = Font(name=FONT_CN, size=9, color=MUTED)

headers = ["序号", "供应商", "关联事件", "优先级", "待确认问题", "为什么值得问", "建议动作", "建议责任部门", "建议完成"]
widths = [5, 11, 11, 7, 52, 46, 32, 14, 11]
header_row(ws, 4, headers, widths, height=30)

PRIO = {"高": "P1", "中": "P2", "低": "P3"}
PRIO_FILL = {
    "P1": PatternFill("solid", fgColor="F3DADA"),
    "P2": PatternFill("solid", fgColor="F9ECD2"),
    "P3": PatternFill("solid", fgColor="E7EEF2"),
}
RESP = {
    "安全环保": "采购 + 质量",
    "处罚": "采购 + 法务",
    "司法": "采购 + 法务",
    "经营动态": "采购 + 财务",
    "工商": "采购",
}
_q = datetime.date.fromisoformat(META.get("query_date", datetime.date.today().isoformat()))
DUE = {
    "P1": (_q + datetime.timedelta(days=5)).isoformat(),
    "P2": (_q + datetime.timedelta(days=15)).isoformat(),
    "P3": (_q + datetime.timedelta(days=26)).isoformat(),
}

r = 5
n = 1
for e in events_sorted:
    prio = PRIO[e["severity"]]
    for q in e["questions"]:
        cell(ws, r, 1, n, align="center")
        cell(ws, r, 2, e["supplier"], bold=True)
        cell(ws, r, 3, e["id"], align="center")
        c = cell(ws, r, 4, prio, align="center", fill=PRIO_FILL[prio])
        c.font = Font(name=FONT_CN, size=9, bold=True,
                      color={"P1": "8B1E1E", "P2": "7A4E12", "P3": "33556B"}[prio])
        cell(ws, r, 5, q)
        why = e["why"]
        if len(why) > 110:
            why = why[:108] + "…"
        cell(ws, r, 6, why)
        cell(ws, r, 7, e["action"])
        cell(ws, r, 8, RESP.get(e["category"], "采购"), align="center")
        cell(ws, r, 9, DUE[prio], align="center")
        ws.row_dimensions[r].height = 64
        r += 1
        n += 1

ws.freeze_panes = "D5"
ws.auto_filter.ref = f"A4:I{r-1}"
page_setup(ws, print_area=f"A1:I{r}")

# =====================================================================
# 06 SOURCES
# =====================================================================
ws = wb.create_sheet("06_来源清单")
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = "1F5C99"

ws.merge_cells("A1:H1")
c = ws["A1"]
c.value = "来源清单"
c.font = Font(name=FONT_CN, size=18, bold=True, color=NAVY)
ws.row_dimensions[1].height = 32
ws.merge_cells("A2:H2")
c = ws["A2"]
c.value = "按事件出现顺序登记；A=公告/政府原文，B=主流财经媒体，C=行业资讯/期货研究"
c.font = Font(name=FONT_CN, size=9, color=MUTED)

headers = ["序号", "来源 / 标题", "来源类型", "发布方（推断）", "日期", "链接", "证据", "用于事件"]
widths = [5, 44, 14, 22, 11, 60, 6, 30]
header_row(ws, 4, headers, widths, height=30)

r = 5
for i, e in enumerate(events_sorted, start=1):
    cell(ws, r, 1, i, align="center")
    cell(ws, r, 2, e["source"])
    cell(ws, r, 3, e["source_type"], align="center")
    cell(ws, r, 4, e["source"].split("/")[-1].strip() if "/" in e["source"] else e["source"][:18])
    cell(ws, r, 5, e["source_date"], align="center")
    c = cell(ws, r, 6, e["url"], color="1F5C99")
    c.hyperlink = e["url"]
    c.font = Font(name="Consolas", size=8, color="1F5C99", underline="single")
    cell(ws, r, 7, e["evidence"], align="center", bold=True)
    cell(ws, r, 8, f"{e['id']} / {e['title']}")
    ws.row_dimensions[r].height = 34
    r += 1

ws.freeze_panes = "C5"
ws.auto_filter.ref = f"A4:H{r-1}"
page_setup(ws, print_area=f"A1:H{r}")

# =====================================================================
# 07 METHOD
# =====================================================================
ws = wb.create_sheet("07_方法与口径")
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = SLATE
ws.column_dimensions["A"].width = 3
ws.column_dimensions["B"].width = 26
ws.column_dimensions["C"].width = 92
ws.column_dimensions["D"].width = 10
ws.merge_cells("B2:C2")
c = ws["B2"]
c.value = "方法与口径"
c.font = Font(name=FONT_CN, size=18, bold=True, color=NAVY)
ws.row_dimensions[2].height = 32

r = 4
section(ws, r, "1. 检索范围", span=3, start_col=2)
r += 1
for t in DATA["method"]["scope"]:
    cell(ws, r, 2, "•", align="center", border=False)
    cell(ws, r, 3, t, border=False)
    ws.row_dimensions[r].height = 26
    r += 1

r += 1
section(ws, r, "2. 证据分级", span=3, start_col=2)
r += 1
for item in DATA["method"]["evidence_levels"]:
    cell(ws, r, 2, f"{item['level']}（{item['label']}）", bold=True, color=NAVY)
    cell(ws, r, 3, item["desc"])
    ws.row_dimensions[r].height = 24
    r += 1

r += 1
section(ws, r, "3. 检索式（示例）", span=3, start_col=2)
r += 1
for q in DATA["method"]["search_queries"]:
    cell(ws, r, 2, "检索式", color=MUTED)
    cell(ws, r, 3, q)
    ws.row_dimensions[r].height = 24
    r += 1

r += 1
section(ws, r, "4. 已知局限", span=3, start_col=2)
r += 1
for t in DATA["method"]["limits"]:
    cell(ws, r, 2, "局限", color=MUTED)
    cell(ws, r, 3, t)
    ws.row_dimensions[r].height = 38
    r += 1

r += 1
section(ws, r, "5. 分类覆盖检查", span=4, start_col=2)
r += 1
header_at(ws, r, 2, ["类别", "检索结论与说明", "关注度"], height=22)
r += 1
LEVEL_COLOR = {"高": "8B1E1E", "中": "7A4E12", "低": "2F5A3A", "待复核": "6B5A3E", "—": "6E7F8C"}
for item in DATA["coverage_check"]:
    cell(ws, r, 2, item["cat"], bold=True, color=NAVY)
    cell(ws, r, 3, f"{item['status']}。{item['note']}", size=9)
    cell(ws, r, 4, item["level"], align="center", bold=True, size=9,
         color=LEVEL_COLOR.get(item["level"], MUTED))
    ws.row_dimensions[r].height = 50
    r += 1

r += 1
section(ws, r, "6. 免责声明", span=3, start_col=2)
r += 1
ws.merge_cells(start_row=r, start_column=2, end_row=r + 3, end_column=3)
c = ws.cell(row=r, column=2, value=DATA["method"]["disclaimer"])
c.font = Font(name=FONT_CN, size=9.5, color="7A6A55", italic=True)
c.alignment = Alignment(wrap_text=True, vertical="top")
c.fill = PatternFill("solid", fgColor="F1EBDD")
c.border = BORDER
page_setup(ws, landscape=True, print_area=f"A1:D{r+4}")

# =====================================================================
# 08 INDUSTRY
# =====================================================================
ws = wb.create_sheet("08_行业背景")
ws.sheet_view.showGridLines = False
ws.sheet_properties.tabColor = "6E8B74"
for col, w in {"A": 2, "B": 6, "C": 86, "D": 36, "E": 11}.items():
    ws.column_dimensions[col].width = w

ws.merge_cells("B2:E2")
c = ws["B2"]
c.value = f"行业背景：{META.get('industry_title', PRODUCT + '供需与检修')}"
c.font = Font(name=FONT_CN, size=18, bold=True, color=NAVY)
ws.row_dimensions[2].height = 32
ws.merge_cells("B3:E3")
c = ws["B3"]
c.value = "用于解释“为什么同一时间多家供应商都在检修/减量”，不构成价格预测"
c.font = Font(name=FONT_CN, size=9, color=MUTED)

header_at(ws, 5, 2, ["#", "观察", "来源", "日期"], height=28)

r = 6
for i, item in enumerate(DATA["industry"], start=1):
    cell(ws, r, 2, i, align="center")
    cell(ws, r, 3, item["text"])
    cell(ws, r, 4, item["source"])
    cell(ws, r, 5, item["date"], align="center")
    ws.row_dimensions[r].height = 62
    r += 1

section(ws, r + 1, "对采购的含义", span=4, start_col=2)
meanings = [
    "1. 检修/减量是行业性动作，不宜把单家供应商的检修直接解读为个体经营恶化；但要区分“计划检修”与“证照/事故导致的停产”。",
    "2. 在行业普遍亏损阶段，报价异常低或账期异常宽松的供应商，反而需要多问一句现金流与履约保障。",
    "3. 对交付敏感的生产线，建议同时锁定 2 家不同工艺路线的供应商（天然碱/联碱/氨碱），降低单点停产影响。",
    "4. 本页只提供行业背景，不替代对单个供应商的合同、产能、库存与物流核验。",
]
r += 2
for t in meanings:
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    c = ws.cell(row=r, column=2, value=t)
    c.font = Font(name=FONT_CN, size=9.5, color=INK)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r].height = 30
    r += 1

page_setup(ws, print_area=f"A1:E{r}")

wb.save(OUT)
print(f"saved: {OUT}")
print(f"sheets: {wb.sheetnames}")
print(f"events: {len(events)} total, {len(in_window)} in 6m window")
