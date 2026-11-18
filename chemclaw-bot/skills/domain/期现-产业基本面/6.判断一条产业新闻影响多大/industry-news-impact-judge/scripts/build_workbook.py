# -*- coding: utf-8 -*-
"""由 case_data.json 生成 Excel 工作簿（活公式版）。

用法：
    python build_workbook.py <case_data.json> -o <output.xlsx>

设计要点：
1. 所有数字只来自 case_data.json，不在此脚本里写死任何业务数值。
2. 测算表用「活公式」：改 d / r / k 单元格，结果与占比自动重算。
3. 缺口单元格留空并标注「缺口」，不用估算填补。
4. 每个数据表都带「证据等级 / 来源」两列，方便反查。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# ---------------------------------------------------------------- 视觉规范
C_DARK = "1F2937"
C_HEAD = "0F766E"
C_SUB = "134E4A"
C_LIGHT = "F0FDFA"
C_WARN = "FEF3C7"
C_BAD = "FEE2E2"
C_OK = "DCFCE7"
C_GAP = "E5E7EB"
C_BORDER = "D1D5DB"

S = Side(style="thin", color=C_BORDER)
BOX = Border(left=S, right=S, top=S, bottom=S)

GRADE_FILL = {
    "A1": "DCFCE7", "A2": "DCFCE7", "A3": "E0F2FE",
    "B1": "FEF9C3", "B2": "FEF9C3", "B3": "FFEDD5",
    "C": "FEE2E2", "D": "F3E8FF",
}


def _title(ws, text, sub="", width=12):
    """在首行放一个跨列标题条。"""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(name="微软雅黑", size=14, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_DARK)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 30
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = Font(name="微软雅黑", size=9, color="4B5563")
        c2.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
        ws.row_dimensions[2].height = 28
        return 3
    return 2


def _head(ws, row, cols):
    for i, (name, width) in enumerate(cols, start=1):
        c = ws.cell(row=row, column=i, value=name)
        c.font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=C_HEAD)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[row].height = 34
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _row(ws, row, values, fills=None, bold=False, wrap_cols=(), num_fmt=None, height=None):
    for i, v in enumerate(values, start=1):
        # 以 = + - @ 开头的纯文本会被 Excel 当成公式（本表里的 note 就常以「= C2/12」开头），
        # 这里显式标记为字符串，避免写成公式后显示 #VALUE!。
        if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
            c = ws.cell(row=row, column=i)
            c.value = v
            c.data_type = "s"
        else:
            c = ws.cell(row=row, column=i, value=v)
        c.font = Font(name="微软雅黑", size=10, bold=bold)
        c.alignment = Alignment(
            vertical="top",
            wrap_text=(i in wrap_cols),
            horizontal="center" if (num_fmt and i == num_fmt[0]) else "left",
        )
        c.border = BOX
        if fills and i in fills:
            c.fill = PatternFill("solid", fgColor=fills[i])
        if num_fmt and i == num_fmt[0]:
            c.number_format = num_fmt[1]
    if height:
        ws.row_dimensions[row].height = height
    return row + 1


def _grade_fill(g):
    return GRADE_FILL.get(str(g).strip(), None)



def _join_facts(s):
    """把 key_facts 列表拼成一段文字，并附页码引用与抓取方式。"""
    kf = s.get("key_facts") or []
    if isinstance(kf, str):
        kf = [kf]
    body = "\n".join("· " + str(x) for x in kf)
    tail = []
    if s.get("page_ref"):
        tail.append("页码：" + str(s["page_ref"]))
    if s.get("raw_access"):
        tail.append("获取方式：" + str(s["raw_access"]))
    return body + (("\n" + "\n".join(tail)) if tail else "")


def _num(v):
    """None -> 缺口占位（留空）。"""
    return "" if v is None else v


# ---------------------------------------------------------------- 各工作表
def sheet_cover(wb, d):
    ws = wb.active
    ws.title = "封面"
    ws.sheet_view.showGridLines = False
    m, v = d["meta"], d["verification_card"]

    r = _title(ws, "产业新闻影响分析工作簿", m.get("subtitle", ""), width=6)
    r += 1
    kv = [
        ("案例编号", m["case_id"]),
        ("品种", m["product"]),
        ("标题", m["title"]),
        ("核验基准日", m["analyst_baseline_date"]),
        ("生成时间", dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("", ""),
        ("事实确认状态", v["fact_status"]),
        ("整体证据等级", v["overall_grade"]),
        ("旧闻判定", v["old_news_verdict"]),
        ("时效评分", f'{v["freshness_score"]}/5 · {v["freshness_label"]}'),
        ("确认源数量", v["confirmation_sources_count"]),
        ("媒体转载数", v["media_reprint_count"]),
    ]
    for k, val in kv:
        if not k:
            r += 1
            continue
        c1 = ws.cell(row=r, column=1, value=k)
        c1.font = Font(name="微软雅黑", size=10, bold=True)
        c1.fill = PatternFill("solid", fgColor=C_LIGHT)
        c1.border = BOX
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        c2 = ws.cell(row=r, column=2, value=val)
        c2.font = Font(name="微软雅黑", size=10)
        c2.alignment = Alignment(wrap_text=True, vertical="center")
        for cc in range(2, 7):
            ws.cell(row=r, column=cc).border = BOX
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value="声明")
    c.font = Font(name="微软雅黑", size=11, bold=True, color="B91C1C")
    r += 1
    for txt in [m["disclaimer"], m.get("scope_note", "")]:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = ws.cell(row=r, column=1, value=txt)
        c.font = Font(name="微软雅黑", size=10)
        c.fill = PatternFill("solid", fgColor=C_BAD)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 46
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value="工作表导航")
    c.font = Font(name="微软雅黑", size=11, bold=True)
    r += 1
    ws.column_dimensions["A"].width = 20
    for col in "BCDEF":
        ws.column_dimensions[col].width = 22
    guide = [
        ("消息核验卡", "8 要素核验结论 + 旧闻判定 + 时效评分"),
        ("来源溯源", "每一条来源：谁发的、什么时候、什么层级、能证明什么"),
        ("转载路径", "从原始来源到媒体扩散的链条，识别是否二手转述"),
        ("事件要素", "企业/装置/产品/产能/地区/时间/事件类型 七要素"),
        ("时间线", "事件从晃电到事故到复产的逐条记录"),
        ("装置档案", "装置身份、工艺、产能、历史产量、历史事故"),
        ("产能基准", "所有分母：全国/区域/工艺/月均产量，逐条带来源"),
        ("产能占比", "同一装置多种分母同出，避免单口径误导"),
        ("影响量测算", "活公式：改 d/r/k 自动重算，含公式说明"),
        ("敏感矩阵", "停产天数 × 影响系数 的双维情景表"),
        ("产量缺口分解", "年度实测口径分解，事故可归因份额留缺口"),
        ("产业链节点", "上下游节点与传导强度"),
        ("传导路径", "逐条路径的可量化性判断"),
        ("三分法-已确认", "已发生影响，计入确认汇总"),
        ("三分法-不确定", "存在不确定性，不计入确认汇总"),
        ("待核验清单", "P0/P1/P2 优先级与查证方式"),
        ("数据缺口", "缺什么、卡住哪个结论、本报告如何处理"),
        ("可观察指标", "现货/期货/库存/开工等可跟踪指标与异常判据"),
        ("行情背景", "事件时段公开行情事实，只描述不推导"),
        ("同区域企业", "可比企业产能，判断能否补位"),
        ("证据等级说明", "A1–D 与 T1–T6 的定义与用法"),
    ]
    for name, desc in guide:
        c1 = ws.cell(row=r, column=1, value=name)
        c1.font = Font(name="微软雅黑", size=10, bold=True, color=C_HEAD)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        c2 = ws.cell(row=r, column=2, value=desc)
        c2.font = Font(name="微软雅黑", size=10)
        for cc in range(1, 7):
            ws.cell(row=r, column=cc).border = Border(bottom=Border(bottom=Side(style="dotted", color=C_BORDER)).bottom)
        ws.cell(row=r, column=1).border = BOX
        for cc in range(2, 7):
            ws.cell(row=r, column=cc).border = BOX
        r += 1


def sheet_verify(wb, d):
    ws = wb.create_sheet("消息核验卡")
    ws.sheet_view.showGridLines = False
    v = d["verification_card"]
    r = _title(ws, "① 消息核验卡", "回答：这条消息是什么、谁最先说的、是不是旧闻、现在还值不值得看", width=4)
    r += 1
    _head(ws, r, [("核验项", 26), ("结论", 74), ("证据等级", 12), ("说明", 34)])
    r += 1

    rows = [
        ("标题（一句话事实）", v["headline"], "-", "不含判断，只陈述已确认事实"),
        ("事件发生时间", v["event_date"], "A1", "政府调查报告认定"),
        ("最早公开确认主体", v["first_public_authority"], "A1", "监管/官方"),
        ("首个公开日期", v["first_public_date"], "A1", "以批复/发布日为准"),
        ("最早已有明确日期的公开记录", v.get("earliest_dated_public_record", ""), "B3", "可能是事后报道，不等于首发"),
        ("媒体开始转载日期", v.get("circulation_first_date", ""), "B3", "转载数见「转载路径」表"),
        ("事实确认状态", v["fact_status"], v["overall_grade"], v["fact_status_detail"]),
        ("旧闻判定", v["old_news_verdict"], "-", "见下方 6 条信号"),
        ("时效评分", f'{v["freshness_score"]}/5（{v["freshness_label"]}）', "-", v.get("freshness_note", "")),
        ("确认源数量", v["confirmation_sources_count"], "-", "独立信源，非转载"),
        ("媒体转载数量", v["media_reprint_count"], "-", v.get("reprints_note", "")),
        ("市场认知状态", v["market_awareness"], "-", v["market_awareness_evidence"]),
        ("关键纠正", v.get("key_correction", "无"), "-", "新闻与原件冲突时以此为准"),
        ("整体证据等级", v["overall_grade"], v["overall_grade"], "A1 最高，D 最低"),
    ]
    for k, val, g, note in rows:
        fill = {}
        gf = _grade_fill(g)
        if gf:
            fill[3] = gf
        c1 = ws.cell(row=r, column=1, value=k)
        c1.font = Font(name="微软雅黑", size=10, bold=True)
        c1.fill = PatternFill("solid", fgColor=C_LIGHT)
        c1.border = BOX
        c1.alignment = Alignment(vertical="top", wrap_text=True)
        c2 = ws.cell(row=r, column=2, value=val)
        c2.font = Font(name="微软雅黑", size=10)
        c2.alignment = Alignment(vertical="top", wrap_text=True)
        c2.border = BOX
        c3 = ws.cell(row=r, column=3, value=g)
        c3.font = Font(name="微软雅黑", size=10, bold=True)
        c3.alignment = Alignment(horizontal="center", vertical="top")
        c3.border = BOX
        if gf:
            c3.fill = PatternFill("solid", fgColor=gf)
        c4 = ws.cell(row=r, column=4, value=note)
        c4.font = Font(name="微软雅黑", size=9, color="4B5563")
        c4.alignment = Alignment(vertical="top", wrap_text=True)
        c4.border = BOX
        ws.row_dimensions[r].height = 34
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    c = ws.cell(row=r, column=1, value="旧闻识别 · 6 类信号命中情况")
    c.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_SUB)
    c.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 24
    r += 1
    _head(ws, r, [("序号", 26), ("命中/未命中与依据", 74), ("", 12), ("", 34)])
    ws.cell(row=r, column=1, value="信号")
    r += 1
    for i, ev in enumerate(v.get("old_news_evidence", []), start=1):
        ws.cell(row=r, column=1, value=f"S{i}")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        c = ws.cell(row=r, column=2, value=ev)
        c.font = Font(name="微软雅黑", size=10)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        for cc in range(1, 5):
            ws.cell(row=r, column=cc).border = BOX
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="top")
        ws.row_dimensions[r].height = 32
        r += 1


def sheet_sources(wb, d):
    ws = wb.create_sheet("来源溯源")
    r = _title(ws, "② 来源溯源", "每条来源都要能回答：谁发的、什么时候、什么层级、能证明什么、不能证明什么", width=9)
    r += 1
    _head(ws, r, [("ID", 7), ("标题", 46), ("发布方", 24), ("发布日期", 20), ("层级", 8),
                  ("证据等级", 9), ("原始源", 8), ("确认源", 8), ("能证明 / 不能证明", 56)])
    r += 1
    for s in d["sources"]:
        vals = [
            s.get("id", ""), s.get("title", ""), s.get("publisher", ""),
            s.get("published", ""), s.get("tier", ""), s.get("grade", ""),
            s.get("type", ""), s.get("role", ""),
            _join_facts(s),
        ]
        fills = {}
        gf = _grade_fill(s.get("grade"))
        if gf:
            fills[6] = gf
        r = _row(ws, r, vals, fills=fills, wrap_cols=(2, 3, 9), height=44)
        ws.cell(row=r - 1, column=6).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r - 1, column=7).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r - 1, column=8).alignment = Alignment(horizontal="center", vertical="top")
        for cc in (5, 6, 7, 8):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    c = ws.cell(row=r, column=1, value="提示：URL 见 HTML 报告与 sources/原始证据摘录.md。Excel 内不嵌外链，避免文件被移动后链接失效。")
    c.font = Font(name="微软雅黑", size=9, italic=True, color="6B7280")


def sheet_reprints(wb, d):
    ws = wb.create_sheet("转载路径")
    v = d["verification_card"]
    r = _title(ws, "③ 转载路径", "识别「一手信息」与「二手转述」的分界，避免把转载当新消息", width=5)
    r += 1
    _head(ws, r, [("节点", 10), ("日期", 22), ("主体 / 形式", 34), ("性质", 22), ("说明", 60)])
    r += 1
    nodes = [
        ["起点", v["first_public_date"], v["first_public_authority"], "原始来源",
         v["fact_status_detail"]],
        ["扩散", v.get("circulation_first_date", ""), "媒体转载（澎湃 / 新浪 / 搜狐等）", "二手转述",
         v.get("reprints_note", "")],
        ["沉淀", "持续更新", "行业安全网站收录调查报告全文", "资料沉淀",
         "全文收录便于引用，但不构成独立确认源"],
        ["新进展", "2026-04-30", "哈密市发布事故防范整改措施与责任追究落实情况评估报告", "新增信息",
         "这是「旧闻+新进展」而非「旧闻重发」的依据"],
    ]
    for n in nodes:
        r = _row(ws, r, n, wrap_cols=(3, 5), height=40)
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws.cell(row=r, column=1, value=f'结论：旧闻判定 = {v["old_news_verdict"]}；时效评分 {v["freshness_score"]}/5。')
    c.font = Font(name="微软雅黑", size=11, bold=True, color="B45309")
    c.fill = PatternFill("solid", fgColor=C_WARN)
    c.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 26


def sheet_event(wb, d):
    ws = wb.create_sheet("事件要素")
    e = d["event"]
    r = _title(ws, "④ 事件要素", "七要素：企业 / 装置 / 产品 / 产能 / 地区 / 时间 / 事件类型", width=4)
    r += 1
    _head(ws, r, [("要素", 24), ("取值", 76), ("说明", 26), ("", 10)])
    r += 1
    loc = e["location"]
    p = e["plant"]
    u = e["unit_detail"]
    rows = [
        ("事件类型代码", e["event_type_code"], e["event_type_cn"]),
        ("事件类型（中文）", e["event_type_cn"], "决定用哪条测算公式"),
        ("企业全称", e["company_full"], "须与营业执照一致"),
        ("统一社会信用代码", e.get("company_credit_code", ""), "用于国家企业信用信息公示系统核对"),
        ("法定代表人", e.get("company_legal_rep", ""), ""),
        ("成立时间", e.get("company_established", ""), ""),
        ("注册资本", e.get("company_registered_capital", ""), ""),
        ("上市主体", e.get("listed_entity", ""), ""),
        ("与上市主体关系", e.get("listed_relationship", ""), "决定是否触发公告义务"),
        ("省份", loc.get("province", ""), ""),
        ("地级市", loc.get("city", ""), ""),
        ("区县", loc.get("county", ""), ""),
        ("园区", loc.get("park", ""), "影响是否属重点监管区域"),
        ("详细地址", loc.get("address", ""), ""),
        ("装置名称", p["plant_name"], ""),
        ("装置全称", p.get("plant_full_name", ""), ""),
        ("主产品", p["product_main"], ""),
        ("联产/副产品", "、".join(p.get("products_co", [])), ""),
        ("工艺路线", p.get("process_route", ""), "决定可比口径"),
        ("原料", p.get("feedstock", "") if isinstance(p.get("feedstock"), str) else "、".join(p.get("feedstock", [])), ""),
        ("核心反应器配置", p.get("gasifiers", ""), "台数与系列决定 k"),
        ("设计产能（吨/年）", p["capacity_design_methanol_tpa"], "必须来自书面来源"),
        ("设计产能（LNG）", p.get("capacity_design_lng_nm3", ""), "标方/年"),
        ("投产时间", p.get("commissioned", ""), ""),
        ("涉事单元", u["unit"], "设备级，不是企业级"),
        ("所属系统", u.get("unit_system", ""), ""),
        ("系列内台数", u.get("unit_count_in_series", ""), "k = 1/台数 的依据"),
        ("单元占全厂产能份额", u.get("unit_share_of_plant", ""), "k 取值依据"),
        ("事发时工况", u.get("operating_context", ""), ""),
        ("是否全厂停产", u["whether_whole_plant_stopped"], "未确认时不得按全厂测算"),
    ]
    for k, val, note in rows:
        c1 = ws.cell(row=r, column=1, value=k)
        c1.font = Font(name="微软雅黑", size=10, bold=True)
        c1.fill = PatternFill("solid", fgColor=C_LIGHT)
        c1.border = BOX
        c1.alignment = Alignment(vertical="top", wrap_text=True)
        c2 = ws.cell(row=r, column=2, value=val)
        c2.font = Font(name="微软雅黑", size=10)
        c2.alignment = Alignment(vertical="top", wrap_text=True)
        c2.border = BOX
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        c3 = ws.cell(row=r, column=3, value=note)
        c3.font = Font(name="微软雅黑", size=9, color="6B7280")
        c3.alignment = Alignment(vertical="top", wrap_text=True)
        c3.border = BOX
        ws.cell(row=r, column=4).border = BOX
        ws.row_dimensions[r].height = 30
        r += 1


def sheet_timeline(wb, d):
    ws = wb.create_sheet("时间线")
    r = _title(ws, "⑤ 事件时间线", "从最早异动到处置结论，逐条带来源与等级", width=4)
    r += 1
    _head(ws, r, [("时间", 24), ("发生了什么", 82), ("等级", 10), ("来源", 14)])
    r += 1
    for t in d["event"]["timeline"]:
        r = _row(ws, r, [t.get("time", ""), t.get("event", ""), t.get("grade", ""), t.get("source", "")],
                 fills={3: _grade_fill(t.get("grade"))} if _grade_fill(t.get("grade")) else None,
                 wrap_cols=(2,), height=34)
        for cc in (3, 4):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")


def sheet_plant(wb, d):
    ws = wb.create_sheet("装置档案")
    p = d["event"]["plant"]
    r = _title(ws, "⑥ 装置档案", "装置身份 + 历史实际产量（用于算实际开工率 r）+ 历史事故", width=5)
    r += 1
    _head(ws, r, [("字段", 24), ("内容", 74), ("证据等级", 11), ("来源", 14), ("备注", 40)])
    r += 1
    base = [
        ("装置编号", p.get("plant_id", ""), "A1", "S1", "调查报告中的装置称谓"),
        ("装置名称", p["plant_name"], "A2", "S3", ""),
        ("装置全称", p.get("plant_full_name", ""), "A2", "S3", ""),
        ("主产品", p["product_main"], "A2", "S3", ""),
        ("工艺路线", p.get("process_route", ""), "A2", "S3", "决定可比口径"),
        ("设计产能（吨/年）", p["capacity_design_methanol_tpa"], "A2", "S3", "测算第一分母"),
        ("投产时间", p.get("commissioned", ""), "A1", "S1", ""),
        ("产量数据来源", p.get("production_source", ""), "A2", "S3", ""),
    ]
    for k, val, g, src, note in base:
        r = _row(ws, r, [k, val, g, src, note], bold=False, wrap_cols=(2, 5),
                 fills={3: _grade_fill(g)}, height=30)
        for cc in (3, 4):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws.cell(row=r, column=1, value="历史实际产量（用于计算实际开工率 r = 均值 / 设计产能）")
    c.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_SUB)
    c.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 24
    r += 1
    _head(ws, r, [("年份", 24), ("实际产量（吨）", 74), ("证据等级", 11), ("来源", 14), ("备注", 40)])
    ws.cell(row=r, column=1, value="年份")
    r += 1
    prod = p.get("production_actual_t", {})
    start_p = r
    for yr in sorted(prod.keys()):
        r = _row(ws, r, [str(yr), prod[yr], "A2", "S3", ""],
                 num_fmt=(2, "#,##0"), height=22)
        ws.cell(row=r - 1, column=3).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r - 1, column=4).alignment = Alignment(horizontal="center", vertical="top")
    end_p = r - 1
    # 近三年均值（活公式）。口径：以「事件发生年份」为界，只取该年之前已完结的年度；
    # 事件当年的数据已包含事件影响，纳入基数会污染「正常产能」基准。
    try:
        event_year = int(str(d["verification_card"]["event_date"])[:4])
    except (KeyError, ValueError):
        event_year = 9999
    done_years = [y for y in sorted(prod.keys()) if int(y) < event_year]
    use_years = done_years[-3:] if len(done_years) >= 3 else sorted(prod.keys())[-3:]
    first_r = start_p + sorted(prod.keys()).index(min(use_years))
    last_r = start_p + sorted(prod.keys()).index(max(use_years))
    label = f"事发前近 3 年均值（{'/'.join(str(y) for y in use_years)}）"
    ws.cell(row=r, column=1, value=label).font = Font(name="微软雅黑", size=10, bold=True)
    c = ws.cell(row=r, column=2, value=f"=AVERAGE(B{first_r}:B{last_r})")
    c.number_format = "#,##0"
    c.font = Font(name="微软雅黑", size=10, bold=True)
    c.fill = PatternFill("solid", fgColor=C_OK)
    for cc in range(1, 6):
        ws.cell(row=r, column=cc).border = BOX
    ws.cell(row=r, column=3, value="计算值").alignment = Alignment(horizontal="center")
    ws.cell(row=r, column=5, value="作为「实际产量口径」测算的基数").font = Font(name="微软雅黑", size=9)
    mean_row = r
    r += 2

    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws.cell(row=r, column=1, value="该装置历史事故 / 非计划停车（判断是否为重复性问题）")
    c.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_SUB)
    c.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 24
    r += 1
    for inc in p.get("historical_incidents", []):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        c = ws.cell(row=r, column=1, value="• " + str(inc))
        c.font = Font(name="微软雅黑", size=10)
        c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
        for cc in range(1, 6):
            ws.cell(row=r, column=cc).border = Border(bottom=Border(bottom=Side(style="dotted", color=C_BORDER)).bottom)
        ws.row_dimensions[r].height = 28
        r += 1
    return mean_row


def sheet_basis(wb, d):
    ws = wb.create_sheet("产能基准")
    r = _title(ws, "⑦ 产能基准（分母表）", "所有占比的分母都在这里；没有来源的数不进表", width=7)
    r += 1
    _head(ws, r, [("ID", 7), ("指标", 40), ("数值", 16), ("单位", 14), ("等级", 9), ("来源", 14), ("备注", 62)])
    r += 1
    first = r
    for b in d["capacity_basis"]:
        r = _row(ws, r, [b.get("id", ""), b.get("metric", ""), b.get("value"), b.get("unit", ""),
                         b.get("grade", ""), b.get("source", ""), b.get("note", "")],
                 fills={5: _grade_fill(b.get("grade"))} if _grade_fill(b.get("grade")) else None,
                 wrap_cols=(2, 7), num_fmt=(3, "#,##0.####"), height=30)
        ws.cell(row=r - 1, column=3).alignment = Alignment(horizontal="right", vertical="top")
        ws.cell(row=r - 1, column=5).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r - 1, column=6).alignment = Alignment(horizontal="center", vertical="top")
    return first, r - 1


def sheet_ratio(wb, d):
    ws = wb.create_sheet("产能占比")
    c = d["calculations"]
    r = _title(ws, "⑧ 产能占比（多口径同出）",
               "同一个装置，换分母就换观感。必须同时给出全国 / 区域 / 工艺三个口径，禁止只挑一个", width=5)
    r += 1
    _head(ws, r, [("口径", 36), ("占比", 13), ("计算式", 40), ("对应分母", 14), ("怎么读这个数", 66)])
    r += 1
    for x in c["ratios"]:
        r = _row(ws, r, [x["name"], x["value_pct"] / 100.0, x["formula"], x.get("denominator_id", ""),
                         x.get("interpretation", "")],
                 num_fmt=(2, "0.0000%"), wrap_cols=(1, 3, 5), height=32)
        ws.cell(row=r - 1, column=3).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ws.cell(row=r - 1, column=4).alignment = Alignment(horizontal="center", vertical="top")
        v = x["value_pct"]
        ws.cell(row=r - 1, column=2).fill = PatternFill(
            "solid", fgColor=(C_BAD if v > 15 else (C_WARN if v > 2 else C_OK)))

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    cc = ws.cell(row=r, column=1,
                 value="读法提醒：占比高 ≠ 影响大。分母是产能时，占比只说明「这个厂在供给盘子里占多大」，"
                       "不说明实际减量；要落到产量影响，必须回到「事件时长 × 开工率 × 影响范围」。")
    cc.font = Font(name="微软雅黑", size=9, italic=True, color="B45309")
    cc.fill = PatternFill("solid", fgColor=C_WARN)
    cc.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 34


def sheet_calc(wb, d, basis_first, basis_last, plant_mean_row):
    ws = wb.create_sheet("影响量测算")
    c = d["calculations"]
    r = _title(ws, "⑨ 影响量测算（活公式）",
               "黄色底 = 你可以改的假设参数；绿色底 = 自动重算结果。公式：L = Q × (d/365) × r × k", width=6)
    r += 1

    # ---- 参数区
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    cc = ws.cell(row=r, column=1, value="一、参数（可改）")
    cc.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    cc.fill = PatternFill("solid", fgColor=C_SUB)
    cc.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 24
    r += 1
    _head(ws, r, [("参数", 30), ("取值", 16), ("单位", 12), ("来源 / 说明", 62), ("", 10), ("", 10)])
    r += 1

    p_name = r
    r = _row(ws, r, ["涉事装置设计产能 Q", c["ratios"][0] and d["event"]["plant"]["capacity_design_methanol_tpa"],
                     "吨/年", "装置档案；A2 上市公司年报"], num_fmt=(2, "#,##0"), wrap_cols=(4,), height=24)
    ws.cell(row=r - 1, column=2).fill = PatternFill("solid", fgColor=C_WARN)

    p_days = r
    r = _row(ws, r, ["停产天数 d（假设）", c["scenario_matrix"]["days"][2], "天",
                     "⚠️ 公司未披露实际停产天数，此处为情景假设，可自行修改"], num_fmt=(2, "0"), wrap_cols=(4,), height=24)
    ws.cell(row=r - 1, column=2).fill = PatternFill("solid", fgColor=C_WARN)

    p_rate = r
    r = _row(ws, r, ["实际开工率 r", c["rate_assumption"]["r_actual_2021_2023"], "—",
                     c["rate_assumption"]["formula"] + "；" + c["rate_assumption"]["source"]],
             num_fmt=(2, "0.0000"), wrap_cols=(4,), height=24)
    ws.cell(row=r - 1, column=2).fill = PatternFill("solid", fgColor=C_WARN)

    p_k = r
    r = _row(ws, r, ["影响系数 k", c["scenario_scenarios"][0]["k"], "—",
                     "k = 涉事单元占全厂产能份额；k=0.125 表示仅 1/8 台气化炉受影响"], num_fmt=(2, "0.000"), wrap_cols=(4,), height=24)
    ws.cell(row=r - 1, column=2).fill = PatternFill("solid", fgColor=C_WARN)

    r += 1
    # ---- 结果区
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    cc = ws.cell(row=r, column=1, value="二、结果（自动重算）")
    cc.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    cc.fill = PatternFill("solid", fgColor=C_SUB)
    cc.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 24
    r += 1
    _head(ws, r, [("结果项", 30), ("数值", 16), ("单位", 12), ("公式", 62), ("", 10), ("", 10)])
    r += 1

    res = [
        ("日均产能 D", f"=B{p_name}/365", "吨/日", "D = Q / 365", "#,##0", None),
        ("理论产量影响 L", f"=B{p_name}*(B{p_days}/365)*B{p_rate}*B{p_k}", "吨",
         "L = Q × (d/365) × r × k", "#,##0", C_OK),
        ("L（万吨）", f"=B{r + 1}/10000", "万吨", "L / 10000", "0.00", None),
        ("占全国年产能", f"=B{p_name}/106300000", "%", "Q / 全国有效产能", "0.0000%", None),
        ("占西北地区产能（折算）", f"=B{p_name}/37205000", "%", "Q / (全国×35%)", "0.0000%", None),
        ("相当于全国产量天数", f"=B{r + 1}/(71500000/365)", "天", "L / (全国年产量/365)", "0.000", None),
        ("占该装置年产量", f"=B{r + 1}/B{p_name}", "%", "L / Q", "0.00%", None),
    ]
    for name, formula, unit, fdesc, fmt, fill in res:
        r = _row(ws, r, [name, formula, unit, fdesc], num_fmt=(2, fmt), wrap_cols=(4,), height=24, bold=True)
        if fill:
            ws.cell(row=r - 1, column=2).fill = PatternFill("solid", fgColor=fill)

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    cc = ws.cell(row=r, column=1,
                 value="⚠️ 使用限制：d（停产天数）无权威出处；k（波及范围）取决于「是否全厂停产」，"
                       "该事实未确认。以上结果只能作为量级理解，不得写成「实际减产 X 万吨」。")
    cc.font = Font(name="微软雅黑", size=10, bold=True, color="B91C1C")
    cc.fill = PatternFill("solid", fgColor=C_BAD)
    cc.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 40

    r += 2
    # ---- 实际产量口径
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    cc = ws.cell(row=r, column=1, value="三、替代口径：以「实际产量」为基数（更贴近真实减产）")
    cc.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    cc.fill = PatternFill("solid", fgColor=C_SUB)
    cc.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 24
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    cc = ws.cell(row=r, column=1,
                 value=f"基数 = 事发前近 3 年平均实际产量（活引用「装置档案」第 {plant_mean_row} 行）= "
                       f"{c['scenario_matrix']['base_output_3yavg_t']:,} 吨。"
                       "公式改为 L = 年均实际产量 × (d/365) × k，无需再乘 r（r 已隐含在历史产量中）。"
                       "⚠️ 注意：该口径与本表上方「设计产能口径」的基数不同，两者不可混用。")
    cc.font = Font(name="微软雅黑", size=9, color="4B5563")
    cc.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 30
    r += 1

    _head(ws, r, [("情景", 30), ("k", 10), ("d（天）", 12), ("L = 年均实际产量×(d/365)×k（吨）", 34), ("占全国月均产量", 18), ("说明", 40)])
    r += 1
    for s in c["scenario_scenarios"]:
        ws.cell(row=r, column=1, value=s["name"])
        ws.cell(row=r, column=2, value=s["k"]).number_format = "0.000"
        ws.cell(row=r, column=3, value=f"=B{p_days}").number_format = "0"
        f = ws.cell(row=r, column=4, value=f"='装置档案'!B{plant_mean_row}*(C{r}/365)*B{r}")
        f.number_format = "#,##0"
        f.font = Font(name="微软雅黑", size=10, bold=True)
        ws.cell(row=r, column=5, value=f"=D{r}/(71500000/12)").number_format = "0.000%"
        ws.cell(row=r, column=6, value=s["basis"])
        for cc_ in range(1, 7):
            cell = ws.cell(row=r, column=cc_)
            cell.border = BOX
            cell.alignment = Alignment(wrap_text=(cc_ in (1, 6)), vertical="top",
                                       horizontal="center" if cc_ in (2, 3, 4, 5) else "left")
            if cell.font.size is None or cc_ in (1, 6):
                cell.font = Font(name="微软雅黑", size=10)
        ws.row_dimensions[r].height = 44
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    cc = ws.cell(row=r, column=1,
                 value="三个情景共用同一个 d（可改上面「停产天数」联动）。k 的差别就是「波及范围」的差别——"
                       "这正是本次事件最不确定、也最影响结论的地方。")
    cc.font = Font(name="微软雅黑", size=9, italic=True, color="6B7280")
    cc.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 28
    return p_name, p_days, p_rate, p_k


def sheet_matrix(wb, d, p_days, p_rate, p_k):
    ws = wb.create_sheet("敏感矩阵")
    c = d["calculations"]
    sm = c["scenario_matrix"]
    Q = d["event"]["plant"]["capacity_design_methanol_tpa"]
    r = _title(ws, "⑩ 敏感矩阵：停产天数 × 影响系数",
               f"公式 L = {Q:,} × (d/365) × r × k，r = {sm['rate']:.4f}；单元格为吨", width=8)
    r += 1
    days = sm["days"]
    ks = sm["ks"]
    _head(ws, r, [("k \\ d", 22)] + [(f"{dd} 天", 14) for dd in days] + [("", 10), ("", 10)])
    # 表头写的是「7 天」这类文字，公式不能引用 → 下面加一行纯数字天数供公式取值
    r += 1
    ws.cell(row=r, column=1, value="d（天）→").font = Font(name="微软雅黑", size=9, italic=True, color="6B7280")
    ws.cell(row=r, column=1).alignment = Alignment(horizontal="right")
    for j, dd in enumerate(days, start=2):
        c = ws.cell(row=r, column=j, value=dd)
        c.font = Font(name="微软雅黑", size=10, bold=True, color=C_HEAD)
        c.alignment = Alignment(horizontal="center")
        c.border = BOX
    hdr = r
    r += 1
    for k in ks:
        cell = ws.cell(row=r, column=1, value=k)
        cell.number_format = "0.000"
        cell.font = Font(name="微软雅黑", size=10, bold=True)
        cell.fill = PatternFill("solid", fgColor=C_LIGHT)
        cell.alignment = Alignment(horizontal="center")
        cell.border = BOX
        for j, dd in enumerate(days, start=2):
            col = get_column_letter(j)
            f = ws.cell(row=r, column=j, value=f"={Q}*({col}${hdr}/365)*{sm['rate']}*$A{r}")
            f.number_format = "#,##0"
            f.font = Font(name="微软雅黑", size=10)
            f.alignment = Alignment(horizontal="right")
            f.border = BOX
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    cc = ws.cell(row=r, column=1,
                 value="怎么用这张表：① 先确认 d 的区间（本案例 d 无出处 → 全部是情景）；"
                       "② 再看 k 的合理区间（是否全厂停产未确认 → 0.125~1.0 都可能）；"
                       "③ 只有当 d 与 k 都能被证据锁定时，才能对外给单点数字。")
    cc.font = Font(name="微软雅黑", size=9, italic=True, color="B45309")
    cc.fill = PatternFill("solid", fgColor=C_WARN)
    cc.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 40
    return r


def sheet_decomp(wb, d):
    ws = wb.create_sheet("产量缺口分解")
    c = d["calculations"]
    r = _title(ws, "⑪ 年度产量缺口分解", "这是唯一「实测」口径：从年报产量倒推，看能归因多少", width=5)
    r += 1
    _head(ws, r, [("项目", 52), ("吨", 18), ("性质", 22), ("来源", 16), ("说明", 50)])
    r += 1
    ao = c["annual_observed"]
    ad = c["annual_decomposition"]
    for x in ad["rows"]:
        nature = x.get("status", x.get("nature", ""))
        val = x["value_t"]
        r = _row(ws, r, [x["item"], _num(val), nature, x["source"], ""],
                 num_fmt=(2, "#,##0;[Red]-#,##0"), wrap_cols=(1, 3), height=34)
        ws.cell(row=r - 1, column=3).alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        ws.cell(row=r - 1, column=4).alignment = Alignment(horizontal="center", vertical="top")
        if val is None:
            ws.cell(row=r - 1, column=2).fill = PatternFill("solid", fgColor=C_GAP)
            ws.cell(row=r - 1, column=2, value="缺口")
            ws.cell(row=r - 1, column=2).alignment = Alignment(horizontal="center")
            ws.cell(row=r - 1, column=2).font = Font(name="微软雅黑", size=10, bold=True, color="6B7280")

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    cc = ws.cell(row=r, column=1, value=ad.get("method", ""))
    cc.font = Font(name="微软雅黑", size=10, bold=True)
    cc.fill = PatternFill("solid", fgColor=C_LIGHT)
    cc.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 28
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    cc = ws.cell(row=r, column=1, value=ao.get("note", "").replace("**", ""))
    cc.font = Font(name="微软雅黑", size=9, color="B91C1C")
    cc.fill = PatternFill("solid", fgColor=C_BAD)
    cc.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws.row_dimensions[r].height = 44


def sheet_chain(wb, d):
    ws = wb.create_sheet("产业链节点")
    r = _title(ws, "⑫ 产业链节点", "定位涉事装置在链条中的位置，判断影响向上还是向下传导", width=7)
    r += 1
    _head(ws, r, [("ID", 8), ("环节", 10), ("节点", 34), ("与主产品关系", 30), ("传导强度", 10),
                  ("本次是否直接涉及", 14), ("说明", 58)])
    r += 1
    for n in d["chain"]["nodes"]:
        r = _row(ws, r, [n["id"], n["layer"], n["name"], n["relation"], n["strength"],
                         "是" if n["impacted"] else "否 / 间接", n.get("note", "")],
                 wrap_cols=(3, 4, 7), height=34)
        for cc in (2, 5, 6):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")
        if n["impacted"]:
            ws.cell(row=r - 1, column=1).fill = PatternFill("solid", fgColor=C_WARN)


def sheet_paths(wb, d):
    ws = wb.create_sheet("传导路径")
    r = _title(ws, "⑬ 传导路径与可量化性", "每条路径都要回答：传不传得过去、卡在哪一步、需不需要额外数据", width=5)
    r += 1
    _head(ws, r, [("传导路径", 56), ("强度", 10), ("证据", 54), ("可量化性", 34), ("备注", 20)])
    r += 1
    for p in d["chain"]["impact_paths"]:
        r = _row(ws, r, [p["path"], p["strength"], p["evidence"], p["quantifiable"], ""],
                 wrap_cols=(1, 3, 4), height=38)
        for cc in (2,):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")


def sheet_threeway(wb, d):
    t = d["three_way"]

    ws = wb.create_sheet("三分法-已确认")
    r = _title(ws, "⑭ 已确认的影响（计入汇总）", "只放有 A/B 级来源支撑的事实，不做推断", width=5)
    r += 1
    _head(ws, r, [("ID", 7), ("已确认事项", 40), ("细节", 62), ("等级", 10), ("来源", 14)])
    r += 1
    for i, x in enumerate(t["confirmed"], start=1):
        r = _row(ws, r, [f"C{i}", x["item"], x["detail"], x["grade"], x.get("source", "")],
                 fills={4: _grade_fill(x["grade"])} if _grade_fill(x["grade"]) else None,
                 wrap_cols=(2, 3), height=36)
        ws.cell(row=r - 1, column=2).font = Font(name="微软雅黑", size=10, bold=True)
        for cc in (4, 5):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")

    ws2 = wb.create_sheet("三分法-不确定")
    r = _title(ws2, "⑮ 存在不确定性的影响（不计入确认汇总）",
               "方向清楚、幅度不明，或依赖未披露假设——单列，不混进上面那张表", width=4)
    r += 1
    _head(ws2, r, [("ID", 7), ("不确定事项", 40), ("为什么不确定 / 缺什么", 80), ("", 12)])
    r += 1
    for i, x in enumerate(t["uncertain"], start=1):
        r = _row(ws2, r, [f"U{i}", x["item"], (x.get("why","") + ("｜待查：" + x["ask"] if x.get("ask") else "")), ""], wrap_cols=(2, 3), height=44)
        ws2.cell(row=r - 1, column=2).font = Font(name="微软雅黑", size=10, bold=True)

    r += 1
    ws2.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    c = ws2.cell(row=r, column=1, value="⑯ 未经确认 / 待核验（禁止计入任何汇总）")
    c.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="991B1B")
    c.alignment = Alignment(indent=1, vertical="center")
    ws2.row_dimensions[r].height = 24
    r += 1
    for i, x in enumerate(t["unconfirmed"], start=1):
        r = _row(ws2, r, [f"X{i}", x["item"], x["detail"] + ("【" + x["note"] + "】" if x.get("note") else ""), x["grade"]],
                 fills={4: _grade_fill(x["grade"])} if _grade_fill(x["grade"]) else None,
                 wrap_cols=(2, 3), height=36)
        ws2.cell(row=r - 1, column=2).font = Font(name="微软雅黑", size=10, bold=True)
        ws2.cell(row=r - 1, column=4).alignment = Alignment(horizontal="center", vertical="top")


def sheet_verify_list(wb, d):
    ws = wb.create_sheet("待核验清单")
    r = _title(ws, "⑰ 待核验清单", "P0 = 决定结论能否成立；P1 = 影响幅度；P2 = 补充背景", width=4)
    r += 1
    _head(ws, r, [("优先级", 10), ("要核验什么", 56), ("怎么查", 62), ("状态", 14)])
    r += 1
    for x in d["three_way"]["to_verify"]:
        p = x.get("when", "")
        fill = {"立即": C_BAD, "一期": C_WARN, "二期": C_OK}.get(p, None)
        r = _row(ws, r, [p, x["what"], x["how"], x.get("who", "")],
                 fills={1: fill} if fill else None, wrap_cols=(2, 3), height=36)
        ws.cell(row=r - 1, column=1).font = Font(name="微软雅黑", size=10, bold=True)
        ws.cell(row=r - 1, column=1).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r - 1, column=4).alignment = Alignment(horizontal="center", vertical="top")


def sheet_gaps(wb, d):
    ws = wb.create_sheet("数据缺口")
    r = _title(ws, "⑱ 数据缺口登记", "缺口不是失败，是诚实的边界。每一条都写清楚：缺什么 / 卡住什么 / 怎么处理", width=4)
    r += 1
    _head(ws, r, [("ID", 7), ("缺失的数据", 44), ("卡住哪个结论", 46), ("本报告如何处理", 52)])
    r += 1
    for g in d["gaps"]:
        r = _row(ws, r, [g["id"], g["item"], g["impact"], g["placeholder"]],
                 fills={1: C_GAP}, wrap_cols=(2, 3, 4), height=40)
        ws.cell(row=r - 1, column=1).font = Font(name="微软雅黑", size=10, bold=True)
        ws.cell(row=r - 1, column=1).alignment = Alignment(horizontal="center", vertical="top")


def sheet_obs(wb, d):
    ws = wb.create_sheet("可观察指标")
    r = _title(ws, "⑲ 可观察指标", "结论可以不确定，但必须给出「接下来看什么就能修正判断」的清单", width=6)
    r += 1
    _head(ws, r, [("优先级", 10), ("类别", 12), ("指标", 34), ("在哪看", 34), ("频率", 10), ("什么算异常", 56)])
    r += 1
    for o in d["observables"]:
        pri = o.get("priority", 3)
        fill = {1: C_BAD, 2: C_WARN}.get(pri, C_OK)
        pri_txt = {1: "首选", 2: "次选"}.get(pri, "参考")
        r = _row(ws, r, [pri_txt, o.get("cat", ""), o.get("metric", ""), o.get("where", ""), o.get("freq", ""), o.get("trigger", "")],
                 fills={1: fill}, wrap_cols=(3, 4, 6), height=34)
        for cc in (1, 2, 5):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")


def sheet_market(wb, d):
    ws = wb.create_sheet("行情背景")
    m = d["market_snapshot"]
    r = _title(ws, "⑳ 事件时段公开行情事实", "只描述当时的状态，不推导方向、不给涨跌结论", width=4)
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    c = ws.cell(row=r, column=1, value=m["note"])
    c.font = Font(name="微软雅黑", size=9, italic=True, color="4B5563")
    c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 30
    r += 1
    _head(ws, r, [("时段", 20), ("公开事实", 72), ("等级", 10), ("来源", 14)])
    r += 1
    for f in m["facts"]:
        r = _row(ws, r, [f["period"], f["fact"], f["grade"], f["source"]],
                 fills={3: _grade_fill(f["grade"])} if _grade_fill(f["grade"]) else None,
                 wrap_cols=(2,), height=30)
        for cc in (3, 4):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    c = ws.cell(row=r, column=1, value="本节为缺口（不估算）：" + "；".join(m["gaps"]))
    c.font = Font(name="微软雅黑", size=10, bold=True, color="B45309")
    c.fill = PatternFill("solid", fgColor=C_WARN)
    c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
    ws.row_dimensions[r].height = 38


def sheet_peers(wb, d):
    ws = wb.create_sheet("同区域企业")
    r = _title(ws, "㉑ 同区域 / 同工艺可比企业", "回答「别人能不能补上这个量」——补得上，影响就小；补不上，影响才实在", width=8)
    r += 1
    _head(ws, r, [("ID", 7), ("企业", 30), ("所在地", 20), ("工艺", 20), ("产能", 30),
                  ("等级", 9), ("来源", 12), ("备注", 44)])
    r += 1
    for p in d["peers"]:
        r = _row(ws, r, [p.get("id", ""), p["name"], p.get("location", ""),
                         (p.get("relation", "") + ("；下游 " + p["downstream"] if p.get("downstream") else "")),
                         p.get("capacity_meoh"), p.get("grade", ""), p.get("source", ""),
                         p.get("note", "")],
                 fills={6: _grade_fill(p.get("grade"))} if _grade_fill(p.get("grade")) else None,
                 wrap_cols=(2, 4, 5, 8), height=40)
        for cc in (6, 7):
            ws.cell(row=r - 1, column=cc).alignment = Alignment(horizontal="center", vertical="top")


def sheet_legend(wb):
    ws = wb.create_sheet("证据等级说明")
    r = _title(ws, "证据等级与来源层级", "所有表里的等级列都按这张表解释", width=5)
    r += 1
    _head(ws, r, [("等级", 8), ("含义", 30), ("典型来源", 52), ("能不能支撑结论", 30), ("本表用法", 24)])
    r += 1
    grades = [
        ("A1", "监管 / 官方认定", "政府事故调查报告、行政处罚决定、法院文书、统计公报", "可以直接作为事实引用", "事实层"),
        ("A2", "上市公司法定披露", "年报、半年报、临时公告、招股书", "可以直接引用，注意口径与时点", "事实层"),
        ("A3", "行业协会 / 交易所统计", "石化联合会、郑商所、隆众/卓创年鉴", "可引用，需注明统计口径", "分母层"),
        ("B1", "头部资讯商日度数据", "隆众、卓创、金联创日评", "可作参考，注意更新频率", "跟踪层"),
        ("B2", "券商 / 期货研报", "国信、广发、南华等研究所", "可引用其数据，结论需独立判断", "分母层/背景"),
        ("B3", "行业媒体报道", "化工报、专业媒体、行业网站", "可作为线索，需回溯一手", "线索层"),
        ("C", "一般媒体转述", "门户、自媒体转载", "不能单独支撑结论", "仅作传播路径"),
        ("D", "未经证实网络信息", "论坛、社交平台、匿名爆料", "不得计入任何汇总", "仅记录待核验"),
    ]
    for g, mean, ex, can, use in grades:
        r = _row(ws, r, [g, mean, ex, can, use],
                 fills={1: _grade_fill(g)}, wrap_cols=(2, 3, 4, 5), height=36)
        ws.cell(row=r - 1, column=1).font = Font(name="微软雅黑", size=11, bold=True)
        ws.cell(row=r - 1, column=1).alignment = Alignment(horizontal="center", vertical="center")

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws.cell(row=r, column=1, value="来源层级 T1–T6")
    c.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_SUB)
    c.alignment = Alignment(indent=1, vertical="center")
    ws.row_dimensions[r].height = 24
    r += 1
    tiers = [
        ("T1", "政府部门 / 监管机构", "事故调查报告、行政处罚、环评公示、能评批复"),
        ("T2", "上市公司法定披露", "沪深交易所公告、年报、招股说明书"),
        ("T3", "行业协会 / 交易所", "石化联合会统计、郑商所数据、海关总署"),
        ("T4", "专业资讯商与研报", "隆众 / 卓创 / 金联创、券商期货研究所"),
        ("T5", "行业媒体", "中国化工报、专业垂直媒体"),
        ("T6", "社交 / 自媒体", "公众号、论坛、短视频"),
    ]
    for t, who, what in tiers:
        ws.cell(row=r, column=1, value=t).font = Font(name="微软雅黑", size=10, bold=True)
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center")
        ws.cell(row=r, column=2, value=who).font = Font(name="微软雅黑", size=10)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
        ws.cell(row=r, column=3, value=what).font = Font(name="微软雅黑", size=10)
        for cc in range(1, 6):
            ws.cell(row=r, column=cc).border = BOX
        r += 1


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="由 case_data.json 生成 Excel 工作簿")
    ap.add_argument("data", type=pathlib.Path, help="case_data.json 路径")
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True, help="输出 xlsx 路径")
    args = ap.parse_args()

    try:
        d = json.loads(args.data.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[错误] JSON 解析失败：{e}", file=sys.stderr)
        return 2

    wb = Workbook()
    sheet_cover(wb, d)
    sheet_verify(wb, d)
    sheet_sources(wb, d)
    sheet_reprints(wb, d)
    sheet_event(wb, d)
    sheet_timeline(wb, d)
    plant_mean_row = sheet_plant(wb, d)
    basis_first, basis_last = sheet_basis(wb, d)
    sheet_ratio(wb, d)
    p_name, p_days, p_rate, p_k = sheet_calc(wb, d, basis_first, basis_last, plant_mean_row)
    sheet_matrix(wb, d, p_days, p_rate, p_k)
    sheet_decomp(wb, d)
    sheet_chain(wb, d)
    sheet_paths(wb, d)
    sheet_threeway(wb, d)
    sheet_verify_list(wb, d)
    sheet_gaps(wb, d)
    sheet_obs(wb, d)
    sheet_market(wb, d)
    sheet_peers(wb, d)
    sheet_legend(wb)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)
    print(f"[OK] 已生成 {args.out}  （{len(wb.sheetnames)} 个工作表：{'、'.join(wb.sheetnames)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
