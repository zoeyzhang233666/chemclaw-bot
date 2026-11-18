#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Excel 工作簿生成器：从 data/ 三表 + derived 生成 11 表工作簿。"""

import json
import os
import sys
from collections import Counter, defaultdict, OrderedDict
from datetime import datetime

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, Reference
    from openpyxl.worksheet.table import Table, TableStyleInfo
except ImportError:
    sys.exit("需要 openpyxl")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppctl as C

# ---------------------------------------------------------------- 样式
NAVY = "1F3864"
BLUE = "2E5C8A"
LIGHT = "DCE6F1"
GREY = "F2F2F2"
WARN = "FFF2CC"
RED = "F8CBAD"
GREEN = "E2EFDA"
ORANGE = "FCE4D6"

F_TITLE = Font(name="微软雅黑", size=16, bold=True, color="FFFFFF")
F_H = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
F_B = Font(name="微软雅黑", size=10)
F_BB = Font(name="微软雅黑", size=10, bold=True)
F_NOTE = Font(name="微软雅黑", size=9, italic=True, color="595959")
FILL_TITLE = PatternFill("solid", fgColor=NAVY)
FILL_H = PatternFill("solid", fgColor=BLUE)
FILL_L = PatternFill("solid", fgColor=LIGHT)
FILL_G = PatternFill("solid", fgColor=GREY)
FILL_W = PatternFill("solid", fgColor=WARN)
FILL_R = PatternFill("solid", fgColor=RED)
FILL_GR = PatternFill("solid", fgColor=GREEN)
FILL_O = PatternFill("solid", fgColor=ORANGE)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

GRADE_FILL = {"A": GREEN, "B": LIGHT, "C": WARN, "D": RED}


def title_row(ws, text, ncol, sub=None):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(1, 1, text)
    c.font = F_TITLE
    c.fill = FILL_TITLE
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 30
    r = 2
    if sub:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
        c = ws.cell(r, 1, sub)
        c.font = F_NOTE
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws.row_dimensions[r].height = 30
        r += 1
    return r


def header_row(ws, row, headers, widths=None):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row, j, h)
        c.font = F_H
        c.fill = FILL_H
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[row].height = 34
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(row + 1, 1)


def body(ws, row, values, fills=None, bold_cols=()):
    for j, v in enumerate(values, 1):
        c = ws.cell(row, j, v)
        c.font = F_BB if j in bold_cols else F_B
        c.alignment = WRAP
        c.border = BORDER
        if fills and fills.get(j):
            fv = fills[j]
            c.fill = fv if isinstance(fv, PatternFill) else PatternFill("solid", fgColor=fv)
    return row + 1


def asfill(v):
    return v if isinstance(v, PatternFill) else PatternFill("solid", fgColor=v)


# ---------------------------------------------------------------- 数据装载
def load(proj_dir):
    d = os.path.join(proj_dir, "data")
    projects = C.load_json(os.path.join(d, "projects.json"))
    progress = C.load_json(os.path.join(d, "progress.json"))["progress"]
    sources = {s["id"]: s for s in C.load_json(os.path.join(d, "sources.json"))["sources"]}
    cfg = C.load_json(os.path.join(d, "config.json"), {})
    return projects, progress, sources, cfg


def cap_of(p):
    return round(sum((u.get("capacity_wan") or 0) for u in p.get("units") or []), 2)


def sort_key_progress(r):
    mi = C.month_index(C.parse_date(r.get("fact_date")))
    return (mi if mi is not None else 0, r["progress_id"])


def latest_progress(rows):
    if not rows:
        return None
    return max(rows, key=sort_key_progress)


# ---------------------------------------------------------------- 各表
def prod_label(cfg):
    """从 config.product 取出用于文件名的产品简称，如 '聚丙烯(PP)' -> 'PP'。"""
    import re as _re
    raw = cfg.get("product", "产品")
    m = _re.search(r"[（(]([^）)]+)[）)]", raw)
    if m:
        return m.group(1).strip()
    return raw


def sheet_cover(wb, projects, progress, sources, cfg, plist):
    ws = wb.create_sheet("0.说明与口径")
    ws.sheet_view.showGridLines = False
    r = title_row(ws, "中国%s新增产能与项目跟踪台账" % cfg.get("product", "产品"), 2,
                  sub="数据截至 %s ｜ 项目 %d 个 ｜ 装置 %d 套 ｜ 进展事实 %d 条 ｜ 来源 %d 条 ｜ 制度：只追加不覆盖"
                       % (cfg.get("as_of", ""), len(projects),
                          sum(len(p.get("units") or []) for p in projects),
                          len(progress), len(sources)))
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 120

    def kv(k, v, fill=None):
        nonlocal r
        a = ws.cell(r, 1, k); a.font = F_BB; a.fill = FILL_G; a.border = BORDER
        a.alignment = Alignment(vertical="top", wrap_text=True)
        b = ws.cell(r, 2, v); b.font = F_B; b.alignment = WRAP; b.border = BORDER
        if fill:
            b.fill = PatternFill("solid", fgColor=fill)
        ws.row_dimensions[r].height = max(16, 13 * (len(str(v)) // 58 + 1))
        r += 1

    kv("产品与单位", "%s，产能单位统一为 %s（万吨/年）" % (cfg.get("product"), cfg.get("unit")))
    kv("跟踪对象", "① 最近 6-12 个月新披露（环评/备案/核准/开工）的 PP 项目；② 未来 1-2 年预计投产的在建项目；③ 计划投产日已过或临近、但工程进度存疑的项目")
    kv("现有产能基数", "%.1f 万吨/年（%s）" % (cfg["baseline_capacity_wan"], cfg["baseline_capacity_source"]),
       LIGHT)
    alt = "；".join("%s：%.1f 万吨（%s）" % (a["label"], a["value_wan"], a["note"])
                    for a in cfg.get("baseline_alternatives", []) if a["value_wan"] != cfg["baseline_capacity_wan"])
    kv("其他基数口径", alt + "。★不同口径的差异来自'是否把已规划未投产项目计入产能'，引用时必须标注来源与时点。")

    kv("【核心铁律】",
       "备案、环评、开工、建设中、计划投产 —— 一律不得认定为'已形成有效供应'。"
       "只有出现「试车/投产/产出合格品/达产/商业运营」且在最新进展中仍有证据支撑的装置，才可计入"
       "'已形成有效供应'。本表所有产能均标注产能状态，不同状态不合并求和作为供应量。", RED)
    kv("项目唯一编号", "PP-YYYY-NNN。一个编号 = 一个项目（业主 + 厂址 + 项目主体 + 产品）。"
                    "同一项目的多条生产线写入'装置编号'（PP-YYYY-NNN-U1/U2），"
                    "★绝不因为'一个项目有多条线'而拆成多个项目，也绝不因为'多条线合计一个数字'而重复登记。")
    kv("四条口径互斥", "已投产(actual) / 试车调试(trial) / 建设中(under construction) / 计划(仅批文)。"
                    "每一套装置在任一年度只能落在其中一类，因此四类相加 = 名义新增，不重复不遗漏。")
    kv("替代退出", "老旧装置关停、以新代旧的置换项目所对应的退出产能在'替代退出旧产能'列单列，"
                "净新增 = 名义新增 − 替代退出。置换项目在'项目性质'标注'置换'。")
    kv("预期投产时间制度", "首次预计（first_plan）写入后永不修改；每次获知新口径，追加一条变更记录到"
                     "'3.预计投产时间变更史'，同时更新最新预计（latest_plan）。任何一版计划都可以回溯。")
    kv("事实日与消息日", "事实发生的日期（fact_date）与消息发布的日期（msg_date）分开记录。"
                   "两者相差越大，说明信息滞后越严重，是判断'这条消息还能不能用'的关键。")
    kv("证据等级 A", "一手权威：企业公告/定期报告、生态环境部门环评批复与公示原文、政府核准或备案文件、企业官方发布")
    kv("证据等级 B", "一手转载或专业数据库：政府网站/权威媒体对一手文件的完整转述、金联创/卓创等专业机构数据库、券商研报")
    kv("证据等级 C", "二手行业资讯：化工网/搜狐号/微信公号等对项目的整理与转述，数字可能滞后或口径不一")
    kv("证据等级 D", "弱证据：百科、自媒体汇编、论坛帖子；仅用于线索定位，不单独支撑关键字段")
    kv("口径冲突处理", "当政府批复口径与行业统计口径不一致时（如镇海 30 万吨 vs 50 万吨、"
                  "中煤榆林 55 万吨 vs 2×30 万吨），不择一而录，而是并列两口径、取可审计的处理方式并标注'待核'。"
                  "见'7.口径冲突'表。")
    kv("重复披露处理", "见'8.剔除与重复披露'表：每条被剔除的记录都写明剔除理由与依据来源编号。"
                  "去重不是删掉，而是留痕——下一个人仍然能看到'为什么不算'。")
    kv("隐性供给缺口", "见'5.年度汇总'与'6.隐性供给缺口'：名义上当年计划投产、但工程证据不支持年内形成供应的产能。"
                  "这是把'计划'翻译成'供应'时最容易出错的地方。")
    kv("爬坡与开工率", cfg.get("ramp_up_discount", {}).get("note", ""))
    kv("★不做的换算", "本台账不把设计产能折算为年度产量。设计产能 × 开工率 = 产量，而开工率由价差驱动、"
                  "逐月变化，属于另一套跟踪体系。混在一起会得出看似精确、实则错误的供应增量。")

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    c = ws.cell(r, 1, "工作表索引")
    c.font = F_H; c.fill = FILL_H; c.alignment = CENTER
    r += 1
    index = [
        ("1.项目主表", "一个项目一行：业主、集团、地区、产品、产能、工艺、性质、阶段、产能状态、预计投产、延期、去重说明"),
        ("2.装置明细", "一套装置/一条生产线一行：分线产能、工艺归类、净新增口径（这是唯一做加总的口径单位）"),
        ("3.进展记录", "一条事实一行：阶段、事实日、消息日、证据等级、来源编号；按项目+时间排序"),
        ("3b.预计投产时间变更史", "每一次计划变化一行：变更前→变更后、变更类型、依据、来源"),
        ("4.来源登记", "每条来源一行：标题、发布方、URL、日期、类型、等级、备注（可点开回原文）"),
        ("5.年度汇总", "按年：已投产/试车/建设中/计划四类互斥 + 替代退出 + 净新增 + 占现有产能比 + 期末产能"),
        ("6.隐性供给缺口", "名义计划落在当年、但工程证据不支持的产能，逐项写明判定规则"),
        ("7.口径冲突", "同一项目不同来源给出的产能/时间不一致时，并列两口径并说明本表如何取值"),
        ("8.剔除与重复披露", "被排除在统计之外的记录及理由（归属错误、口径混算、产品误认、非新增、已投产等）"),
        ("9.地区分布", "按省份/区域汇总新增产能与装置数，并与区域现有产能占比对照"),
        ("10.工艺与路线", "按工艺路线汇总新增产能的边际影响"),
        ("11.自选跟踪", "需要盯的项目清单与跟踪要点（可自行增删）"),
        ("12.待补证清单", "明确'未检索到公开报道'的事项——这些空白本身就是研究结论"),
    ]
    for name, desc in index:
        a = ws.cell(r, 1, name); a.font = F_BB; a.border = BORDER
        b = ws.cell(r, 2, desc); b.font = F_B; b.alignment = WRAP; b.border = BORDER
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    c = ws.cell(r, 1, "口径分歧披露：2026 年 PP 新增产能的不同机构预测（同为行业资讯，结论不同，须并列引用）")
    c.font = F_H; c.fill = FILL_H; c.alignment = CENTER
    r += 1
    for j, h in enumerate(["来源", "统计范围", "数值(万吨/年)"], 1):
        c = ws.cell(r, j, h); c.font = F_BB; c.fill = FILL_L; c.border = BORDER; c.alignment = CENTER
    r += 1
    for f in cfg.get("new_capacity_forecast_divergence", []):
        ws.cell(r, 1, f["source"]).font = F_B
        ws.cell(r, 2, f["scope"]).font = F_B
        c = ws.cell(r, 3, f["value_wan"]); c.font = F_BB; c.number_format = "0.0"
        for j in (1, 2, 3):
            ws.cell(r, j).border = BORDER
            ws.cell(r, j).alignment = WRAP
        r += 1
    ws.cell(r, 1, "★本台账以'逐项目工程证据'为唯一依据，不用任何机构的预测总量倒推项目；"
                  "上表仅用于判断自己的逐项目加总与市场预期之间的位置关系。").font = F_NOTE
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    ws.cell(r, 1).alignment = WRAP
    ws.row_dimensions[r].height = 30
    return ws


def sheet_projects(wb, projects, progress, sources):
    ws = wb.create_sheet("1.项目主表")
    by = defaultdict(list)
    for x in progress:
        by[x["project_id"]].append(x)
    hdr = ["项目编号", "业主", "所属集团", "项目名称", "省份", "地市", "园区", "区域", "产品",
           "设计产能(万吨/年)", "装置套数", "工艺路线", "项目性质", "当前阶段", "产能状态",
           "首次披露", "首提预计投产", "最新预计投产", "是否延期", "延期月数",
           "实质放量年份", "投达产不确定性", "最新进展", "最新进展日期", "证据等级(最新)",
           "关注要点", "去重说明", "统计口径说明"]
    r = title_row(ws, "1. 项目主表（一个项目一行）",
                  len(hdr), "共 %d 个项目。'当前阶段'取最新一条有来源的进展事实，不凭计划推定。"
                            "'设计产能'为项目合计，分线产能见'2.装置明细'。" % len(projects))
    header_row(ws, r, hdr,
               [13, 30, 30, 40, 8, 14, 24, 8, 12, 12, 8, 10, 10, 11, 22, 11, 13, 13, 20, 9, 9, 50,
                46, 12, 8, 40, 46, 46])
    r += 1
    order = {"试车": 0, "中交": 1, "设备安装": 2, "建设": 3, "开工": 4, "核准": 5,
             "环评批复": 6, "环评受理": 7, "备案": 8, "拟建": 9, "投产": -1, "达产": -2, "运行": -3}
    porder = {"置换": 0, "新建": 1, "扩建": 2, "技改": 3}
    for p in sorted(projects, key=lambda x: (order.get(x["stage"], 9), -cap_of(x))):
        rows = by.get(p["project_id"], [])
        last = latest_progress(rows)
        y_plan = C.parse_date(p.get("latest_plan_date"))["year"]
        fills = {}
        st = p["stage"]
        if st in ("试车", "设备安装", "建设", "开工", "中交"):
            fills[15] = LIGHT
        if st in ("拟建", "备案", "环评受理", "环评批复", "核准"):
            fills[15] = WARN
        if p.get("delay_flag", "").startswith("是"):
            fills[19] = WARN
        r2 = body(ws, r, [
            p["project_id"], p["owner"], p["group"], p["project_name"], p["province"],
            p.get("city", ""), p.get("park", ""), C.region_of(p["province"]), p["product"],
            cap_of(p), len(p.get("units") or []), p.get("process", ""), p.get("nature", ""),
            st, C.cap_state(st), p.get("first_disclosed", ""), p.get("first_plan_date", ""),
            p.get("latest_plan_date", ""), p.get("delay_flag", ""), p.get("delay_months", ""),
            p.get("ramp_year", ""), p.get("uncertainty", ""),
            (last or {}).get("desc", ""), (last or {}).get("fact_date", ""),
            (last or {}).get("evidence_grade", ""), p.get("watch", ""),
            p.get("dup_note", ""), p.get("counting_note", ""),
        ], fills=fills, bold_cols=(1,))
        ws.cell(r2 - 1, 10).number_format = "0.0"
        ws.cell(r2 - 1, 25).fill = PatternFill(
            "solid", fgColor=GRADE_FILL.get((last or {}).get("evidence_grade", ""), "FFFFFF"))
        ws.row_dimensions[r2 - 1].height = 60
        r = r2
    ws.auto_filter.ref = "A%d:%s%d" % (4, get_column_letter(len(hdr)), r - 1)
    return ws


def sheet_units(wb, projects):
    ws = wb.create_sheet("2.装置明细")
    hdr = ["项目编号", "装置编号", "装置/生产线", "业主", "项目名称", "省份", "区域",
           "设计产能(万吨/年)", "工艺路线", "工艺归类", "项目性质", "装置状态", "产能状态",
           "首提预计投产", "最新预计投产", "置换/退出旧产能", "净新增(万吨/年)", "在统计中的处理"]
    r = title_row(ws, "2. 装置明细（一套装置 / 一条生产线一行）",
                  len(hdr), "共 %d 套。★这是唯一可以放心做加总的口径单位——"
                            "项目层面加总会因'多套装置共用设备'而重复计算。"
                            % sum(len(p.get("units") or []) for p in projects))
    header_row(ws, r, hdr, [13, 15, 40, 30, 36, 8, 8, 12, 10, 24, 10, 11, 22, 13, 13, 12, 12, 40])
    r += 1
    for p in projects:
        for u in p.get("units") or []:
            cap = u.get("capacity_wan") or 0
            repl = u.get("replace_wan") or 0
            note = "全额计入新增" if cap > 0 and repl == 0 and p["nature"] != "置换" else \
                   ("按净增量计入（置换）" if p["nature"] == "置换" else "全额计入新增")
            if cap == 0:
                note = "★产能未披露，不虚设数字，仅登记项目存在"
            r2 = body(ws, r, [
                p["project_id"], u["unit_id"], u.get("unit_name", ""), p["owner"], p["project_name"],
                p["province"], C.region_of(p["province"]), cap, p.get("process", ""),
                C.ROUTE_CLASS.get(p.get("process", ""), p.get("process", "")), p.get("nature", ""),
                p["stage"], C.cap_state(p["stage"]), p.get("first_plan_date", ""),
                p.get("latest_plan_date", ""), repl, cap - repl, note,
            ], fills={13: LIGHT if p["stage"] in ("试车", "设备安装", "中交") else None}, bold_cols=(2,))
            for j in (8, 16, 17):
                ws.cell(r2 - 1, j).number_format = "0.0"
            r = r2
    ws.auto_filter.ref = "A4:%s%d" % (get_column_letter(len(hdr)), r - 1)
    return ws


def sheet_progress(wb, projects, progress, sources):
    ws = wb.create_sheet("3.进展记录")
    hdr = ["项目编号", "序号", "进展编号", "业主", "项目名称", "省份", "阶段", "进展描述",
           "事实发生日期", "消息日期", "证据等级", "来源数", "来源编号", "来源标题", "来源URL", "备注"]
    r = title_row(ws, "3. 进展记录（一条事实一行；只追加，不覆盖）",
                  len(hdr), "共 %d 条。事实日 vs 消息日分开记录；无来源的记录不入表。"
                            "★历史记录一经写入不得修改，发现新事实就新增一条。" % len(progress))
    header_row(ws, r, hdr, [13, 6, 15, 28, 34, 8, 11, 70, 12, 12, 8, 7, 24, 50, 50, 40])
    r += 1
    by = defaultdict(list)
    for x in progress:
        by[x["project_id"]].append(x)
    for p in projects:
        rows = sorted(by.get(p["project_id"], []), key=sort_key_progress)
        for i, x in enumerate(rows, 1):
            srcs = [sources[s] for s in x.get("source_ids", []) if s in sources]
            r2 = body(ws, r, [
                p["project_id"], i, x["progress_id"], p["owner"], p["project_name"], p["province"],
                x.get("stage", ""), x.get("desc", ""), x.get("fact_date", ""), x.get("msg_date", ""),
                x.get("evidence_grade", ""), len(srcs), ";".join(x.get("source_ids", [])),
                " || ".join(s["title"] for s in srcs), " || ".join(s["url"] for s in srcs),
                x.get("note", ""),
            ], bold_cols=(3,))
            g = x.get("evidence_grade", "")
            ws.cell(r2 - 1, 11).fill = PatternFill("solid", fgColor=GRADE_FILL.get(g, "FFFFFF"))
            ws.cell(r2 - 1, 11).alignment = CENTER
            if x.get("plan_change"):
                for j in (7, 8):
                    ws.cell(r2 - 1, j).fill = PatternFill("solid", fgColor=ORANGE)
            ws.row_dimensions[r2 - 1].height = max(30, 13 * (len(x.get("desc", "")) // 34 + 1))
            r = r2
    ws.auto_filter.ref = "A4:%s%d" % (get_column_letter(len(hdr)), r - 1)
    return ws


def sheet_history(wb, projects, progress):
    ws = wb.create_sheet("3b.预计投产时间变更史")
    hdr = ["项目编号", "业主", "项目名称", "变更序号", "变更发生(事实日)", "消息日期",
           "变更类型", "变更前预计投产", "变更后预计投产", "依据描述", "来源编号", "证据等级", "解读"]
    r = title_row(ws, "3b. 预计投产时间变更史（追加式，永不覆盖）",
                  len(hdr), "每一次计划变化单独成行。'首次'= 项目第一次给出明确投产口径；"
                            "'延期/提前'= 相对上一版的变化；'明确到月/到年'= 精度提高，不一定代表时间真的变了。")
    header_row(ws, r, hdr, [13, 28, 36, 8, 14, 12, 12, 14, 14, 70, 24, 8, 40])
    r += 1
    by = defaultdict(list)
    for x in progress:
        if x.get("plan_change"):
            by[x["project_id"]].append(x)
    for p in projects:
        rows = sorted(by.get(p["project_id"], []), key=sort_key_progress)
        for i, x in enumerate(rows, 1):
            interp = ""
            ct = x.get("plan_change", "")
            if ct == "延期":
                interp = "★延期：需在正文中明确说明，并判断是工程原因还是市场原因"
            elif ct == "提前":
                interp = "提前：核实是否因并线、试车顺利或统计口径调整"
            elif ct == "首次":
                interp = "这是该项目最早的公开投产口径，作为'首次预计'的基准"
            elif ct in ("明确到月", "明确到年"):
                interp = "精度变化，比较时注意不要误判为延期"
            r2 = body(ws, r, [
                p["project_id"], p["owner"], p["project_name"], i, x.get("fact_date", ""),
                x.get("msg_date", ""), ct, x.get("plan_from", ""), x.get("plan_to", ""),
                x.get("desc", ""), ";".join(x.get("source_ids", [])), x.get("evidence_grade", ""), interp,
            ], fills={7: WARN if ct == "延期" else (GR_ if ct == "提前" else None)})
            r = r2
    ws.auto_filter.ref = "A4:%s%d" % (get_column_letter(len(hdr)), r - 1)
    return ws


GR_ = GREEN


def sheet_sources(wb, sources, projects, progress):
    ws = wb.create_sheet("4.来源登记")
    hdr = ["来源编号", "标题", "发布方", "发布日期", "来源类型", "证据等级", "被引用次数", "URL", "备注"]
    r = title_row(ws, "4. 来源登记（每条来源一行）",
                  len(hdr), "共 %d 条。项目与进展表只存来源编号，标题与 URL 在此集中维护，保证单一真相源。"
                            "'被引用次数'为 0 的来源说明已登记但尚未支撑任何事实。" % len(sources))
    header_row(ws, r, hdr, [11, 66, 26, 12, 20, 8, 9, 62, 70])
    r += 1
    use = Counter()
    for x in progress:
        for s in x.get("source_ids", []):
            use[s] += 1
    for sid in sorted(sources, key=lambda x: int(x.split("-")[1])):
        s = sources[sid]
        r2 = body(ws, r, [sid, s["title"], s.get("publisher", ""), s.get("date", ""),
                          s.get("type", ""), s.get("grade", ""), use.get(sid, 0),
                          s.get("url", ""), s.get("note", "")], bold_cols=(1,))
        ws.cell(r2 - 1, 6).fill = PatternFill("solid", fgColor=GRADE_FILL.get(s.get("grade", ""), "FFFFFF"))
        ws.cell(r2 - 1, 6).alignment = CENTER
        if s.get("url"):
            c = ws.cell(r2 - 1, 8)
            c.hyperlink = s["url"]
            c.font = Font(name="微软雅黑", size=9, color="0563C1", underline="single")
        ws.row_dimensions[r2 - 1].height = 34
        r = r2
    ws.auto_filter.ref = "A4:%s%d" % (get_column_letter(len(hdr)), r - 1)
    return ws


def sheet_yearly(wb, proj_dir, cfg, projects):
    ws = wb.create_sheet("5.年度汇总")
    rows = C.summary_yearly(proj_dir, projects, cfg)
    hdr = list(rows[0].keys()) if rows else ["年份"]
    r = title_row(ws, "5. 年度汇总（四类互斥口径 + 替代退出 + 净新增）",
                  len(hdr),
                  "基数：%.1f 万吨/年（%s）。★'已投产''试车调试''建设中''计划'四类互斥，"
                  "相加即名义新增；净新增 = 名义新增 − 替代退出。任何一套装置在同一年只归一类。"
                  % (cfg["baseline_capacity_wan"], cfg["baseline_capacity_source"]))
    header_row(ws, r, hdr, [10, 14, 14, 14, 16, 14, 18, 12, 16, 10, 10, 14, 14])
    r += 1
    for row in rows:
        vals = list(row.values())
        r2 = body(ws, r, vals, bold_cols=(1, 8))
        for j in (2, 3, 4, 5, 6, 7, 8, 9, 13):
            ws.cell(r2 - 1, j).number_format = "0.0"
            ws.cell(r2 - 1, j).alignment = Alignment(horizontal="right", vertical="center")
        ws.cell(r2 - 1, 1).alignment = CENTER
        if (row.get("试车/调试(万吨/年)") or 0) > 0:
            ws.cell(r2 - 1, 3).fill = PatternFill("solid", fgColor=BLUE if False else LIGHT)
        r = r2
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=13)
    c = ws.cell(r, 1, "读法：'已投产'是事实，'试车调试'是已开车但未稳定，'建设中'是已开工但未开车，"
                   "'计划'是只有批文或只有意向。把四类加起来当'供应'是这类研究最常见的错误——"
                   "它们对当年实际供应量的贡献完全不同。")
    c.font = F_NOTE
    c.alignment = WRAP
    ws.row_dimensions[r].height = 30

    # 图表
    if len(rows) >= 2:
        ch = BarChart()
        ch.type = "col"
        ch.grouping = "stacked"
        ch.overlap = 100
        ch.title = "PP 新增产能年度分布（按产能状态，万吨/年）"
        ch.y_axis.title = "万吨/年"
        data = Reference(ws, min_col=2, max_col=5, min_row=4, max_row=4 + len(rows))
        cats = Reference(ws, min_col=1, min_row=5, max_row=4 + len(rows))
        ch.add_data(data, titles_from_data=True)
        ch.set_categories(cats)
        ch.height = 9
        ch.width = 20
        ws.add_chart(ch, "A%d" % (r + 2))
    return ws


def sheet_deferred(wb, proj_dir, cfg, projects):
    ws = wb.create_sheet("6.隐性供给缺口")
    as_of_year = int(cfg.get("as_of", "2026")[:4])
    rows = C.deferred_capacity(projects, as_of_year)
    hdr = ["项目编号", "业主", "项目名称", "省份", "当前阶段", "产能(万吨/年)",
           "最新预计投产", "判定规则", "解读"]
    r = title_row(ws, "6. 隐性供给缺口：名义计划 vs 工程证据",
                  len(hdr),
                  "★这是本台账最有价值的一张表。市场普遍用'计划投产表'加总得出当年新增，"
                  "但其中相当一部分在工程上不可能在年内形成供应。判定规则是机械可审计的，不靠主观打分。")
    header_row(ws, r, hdr, [13, 28, 36, 8, 11, 12, 14, 50, 50])
    r += 1
    tot = 0
    for d in rows:
        tot += d["capacity_wan"]
        interp = ""
        if "R1" in "".join(d["reasons"]):
            interp = "已明确延期半年以上，其'最新预计投产'本身已不可信，须按下一阶段节点重估"
        elif "R2" in "".join(d["reasons"]):
            interp = "批文尚未转化为工程进度，本项目在当年形成供应的概率极低"
        else:
            interp = "主体仍在设备安装，从安装到出料通常需 6-12 个月，年内出料不成立"
        r2 = body(ws, r, [d["project_id"], d["owner"], d["project_name"], d["province"], d["stage"],
                          d["capacity_wan"], d["latest_plan_date"], "; ".join(d["reasons"]), interp],
                  fills={6: FILL_W}, bold_cols=(6,))
        ws.cell(r2 - 1, 6).number_format = "0.0"
        ws.row_dimensions[r2 - 1].height = 44
        r = r2
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    msg = ("合计隐性缺口：" + format(tot, ".1f") + " 万吨/年（" + str(len(rows)) + " 个项目）。"
           "结论表述建议：'名义计划 " + str(as_of_year) + " 年新增 X 万吨，其中约 "
           + format(tot, ".0f") + " 万吨在工程进度上不支持年内形成供应，实际可落地规模约 Y 万吨。'")
    c = ws.cell(r, 1, msg)
    c.font = Font(name="微软雅黑", size=11, bold=True, color="C00000")
    c.alignment = WRAP
    c.fill = PatternFill("solid", fgColor=RED)
    ws.row_dimensions[r].height = 40
    return ws, tot


def sheet_conflict(wb, projects):
    ws = wb.create_sheet("7.口径冲突")
    conflicts = []
    for p in projects:
        dn = p.get("dup_note", "")
        if "★" in dn or "口径" in dn:
            conflicts.append((p["project_id"], p["owner"], p["project_name"], cap_of(p), dn))
    hdr = ["项目编号", "业主", "项目名称", "本表采用产能(万吨/年)", "冲突情况与本表处理"]
    r = title_row(ws, "7. 口径冲突与处理", len(hdr),
                  "同一项目在不同来源中的产能/时间不一致时，不择一而录。下表并列冲突两方，"
                  "并写明本表的取法与待核事项。★标记为重点冲突。")
    header_row(ws, r, hdr, [13, 28, 40, 14, 120])
    r += 1
    for pid, owner, name, cap, dn in conflicts:
        r2 = body(ws, r, [pid, owner, name, cap, dn], bold_cols=(1,))
        ws.cell(r2 - 1, 4).number_format = "0.0"
        ws.row_dimensions[r2 - 1].height = max(40, 13 * (len(dn) // 56 + 1))
        r = r2
    ws.auto_filter.ref = "A4:E%d" % (r - 1)
    return ws


def sheet_excluded(wb, projects):
    ws = wb.create_sheet("8.剔除与重复披露")
    ex = projects.get("excluded", [])
    hdr = ["序号", "被剔除的记录", "剔除类型", "剔除理由与依据"]
    r = title_row(ws, "8. 剔除与重复披露（去重不是删除，是留痕）",
                  len(hdr), "共 %d 条。每条被排除在统计之外的记录都写明理由与来源编号，"
                            "使后来者能看到'为什么不算'，避免同一错误被反复引入。" % len(ex))
    header_row(ws, r, hdr, [6, 54, 22, 110])
    r += 1

    def typ(reason):
        for k in ["归属错误", "混算", "口径混算", "不含PP", "产品误认", "产能误记", "漏计",
                  "立项口径", "非新增", "已投产", "技改不增能", "无法证实", "口径冲突",
                  "产品性质", "未逐项披露"]:
            if k in reason:
                return k
        return "重复披露/口径不一致"

    for i, e in enumerate(ex, 1):
        t = typ(e["reason"])
        fill = RED if t in ("归属错误", "口径混算", "不含PP", "产品误认", "漏计") else WARN
        r2 = body(ws, r, [i, e["name"], t, e["reason"]], fills={3: fill})
        ws.row_dimensions[r2 - 1].height = max(34, 13 * (len(e["reason"]) // 52 + 1))
        r = r2
    return ws


def sheet_region(wb, proj_dir, cfg, projects):
    ws = wb.create_sheet("9.地区分布")
    rows = C.summary_region(proj_dir, projects, cfg)
    base = cfg["baseline_capacity_wan"]
    rb = cfg.get("region_baseline_2026", {})
    hdr = list(rows[0].keys()) + ["该省现有产能占比(行业口径)", "跟踪产能占全国现有产能", "跟踪/现有 倍数"]
    r = title_row(ws, "9. 地区分布", len(hdr),
                  "按省份汇总。'该省现有产能占比'取自卓创 2026-08-26 口径的区域结构，"
                  "与逐项目加总的跟踪产能对照，可看出哪些区域在被'加码'。")
    header_row(ws, r, hdr, [10, 8, 14, 14, 16, 18, 18, 10, 12, 18, 18, 12])
    r += 1
    for row in rows:
        tot_cap = row["跟踪产能合计(万吨/年)"]
        reg = row["区域"]
        share = rb.get(row["省份"], rb.get(reg, None))
        vals = list(row.values()) + [
            ("%.2f%%" % (share * 100)) if share else "未披露",
            "%.2f%%" % (tot_cap / base * 100),
            ("%.3f" % (tot_cap / (base * share))) if share else "—",
        ]
        r2 = body(ws, r, vals, bold_cols=(1, 6))
        for j in (3, 4, 5, 6, 7):
            ws.cell(r2 - 1, j).number_format = "0.0"
        r = r2
    tot = sum(x["跟踪产能合计(万吨/年)"] for x in rows)
    r2 = body(ws, r, ["合计", "", "", "", "", tot, "", "", "", "", "%.2f%%" % (tot / base * 100), ""],
              fills={1: LIGHT})
    ws.cell(r2 - 1, 6).number_format = "0.0"
    ws.cell(r2, 1).font = F_NOTE
    ws.cell(r2, 1, "注：'该省现有产能占比'为行业机构口径的区域结构，与本表逐项目加总口径不同，"
                   "仅作方向性对照，不可直接相除作精确结论。合计行 = 全部跟踪产能（含已投产对照样本）。")
    ws.merge_cells(start_row=r2, start_column=1, end_row=r2, end_column=12)
    return ws


def sheet_route(wb, projects, cfg):
    ws = wb.create_sheet("10.工艺与路线")
    agg = defaultdict(lambda: {"cap": 0.0, "units": 0, "projects": set(), "now": 0.0, "later": 0.0})
    for p in projects:
        k = C.ROUTE_CLASS.get(p.get("process", ""), p.get("process", "未披露"))
        for u in p.get("units") or []:
            c = u.get("capacity_wan") or 0
            agg[k]["cap"] += c
            agg[k]["units"] += 1
            agg[k]["projects"].add(p["project_id"])
            if p["stage"] in ("运行", "达产", "投产", "试车"):
                agg[k]["now"] += c
            else:
                agg[k]["later"] += c
    rb = cfg.get("route_baseline_2026", {})
    base_map = {"油制（炼化副产丙烯）": rb.get("oil", {}).get("capacity_wan"),
                "煤制（CTO/MTO/MTP）": rb.get("coal", {}).get("capacity_wan"),
                "丙烷脱氢（PDH）": rb.get("pdh", {}).get("capacity_wan")}
    hdr = ["工艺归类", "新增产能合计(万吨/年)", "其中已试车/投产", "其中未形成供应",
           "装置数", "项目数", "现有产能(行业口径)", "新增/现有", "边际影响解读"]
    r = title_row(ws, "10. 工艺路线结构与边际影响", len(hdr),
                  "把新增产能按路线拆开，才能判断'这一轮扩产在改变什么'——"
                  "是油头继续扩张，还是煤头/PDH 在抢占份额。")
    header_row(ws, r, hdr, [26, 16, 16, 16, 8, 8, 16, 10, 56])
    r += 1
    interp = {
        "油制（炼化副产丙烯）": "大型炼化一体化配套，成本锚定石脑油/原油，规模大、牌号全，是本轮扩产的主力",
        "煤制（CTO/MTO/MTP）": "成本锚定煤价，区域高度集中于西北（新疆、宁夏、陕西、内蒙古），产品外运半径是硬约束",
        "丙烷脱氢（PDH）": "成本锚定丙烷进口价（CP/ FEI），价差敏感度最高，历史上出现过'建成后择机开车'的情况",
        "外购丙烯聚合": "无自有丙烯，成本随行就市，抗周期能力最弱",
    }
    for k in sorted(agg, key=lambda x: -agg[x]["cap"]):
        a = agg[k]
        ex = base_map.get(k)
        r2 = body(ws, r, [k, round(a["cap"], 1), round(a["now"], 1), round(a["later"], 1),
                          a["units"], len(a["projects"]),
                          ex if ex else "未披露",
                          ("%.1f%%" % (a["cap"] / ex * 100)) if ex else "—",
                          interp.get(k, "")], bold_cols=(1, 2))
        for j in (2, 3, 4, 7):
            ws.cell(r2 - 1, j).number_format = "0.0"
        ws.row_dimensions[r2 - 1].height = 34
        r = r2
    return ws


def sheet_watch(wb, projects, progress, sources):
    ws = wb.create_sheet("11.自选跟踪")
    by = defaultdict(list)
    for x in progress:
        by[x["project_id"]].append(x)
    hdr = ["跟踪优先级", "项目编号", "业主", "项目", "省份", "产能(万吨/年)", "当前阶段",
           "最新进展", "为什么要盯", "跟踪要点", "下次核实动作"]
    r = title_row(ws, "11. 自选跟踪清单", len(hdr),
                  "按'对供应的边际影响 × 时间临近度'排序。★优先级 1 = 未来 6 个月内最可能改变平衡表的事。")
    header_row(ws, r, hdr, [10, 13, 26, 34, 8, 12, 11, 52, 46, 46, 34])
    r += 1
    watch = [
        ("1", "PP-P1-003", "华锦阿美100万吨若在12月试车，是2026年内最后一块大增量；且PP至今无独立中交通稿，尚无证据"),
        ("1", "PP-P1-008", "镇海5#PP'5月出合格品'目标是否达成无任何报道，是全库最大信息缺口（口径还差20万吨）"),
        ("1", "PP-P1-006", "荣信40万吨设备安装仅12%却报年底出产品，延期概率最高，会直接改变2027年平衡表"),
        ("1", "PP-P1-004", "宝丰公司口径12月下旬出合格乙烯丙烯，是年内确定性较高的增量"),
        ("2", "PP-P1-001", "古雷95万吨两条线已测试开车，11月全面投产；关注乙烯投料后能否稳定供料"),
        ("2", "PP-P1-002", "中煤榆林已出第一粒料，关注全流程负荷与商品量"),
        ("2", "PP-P1-007", "东明35万吨仅有行业口径的12月投产，无公司/政府侧确认"),
        ("2", "PP-P1-009", "利华益维远已建成但'择机试生产'，开车完全取决于价差——是PDH路线的风向标"),
        ("3", "PP-P3-005", "塔河炼化2027-09投料，新疆本地消纳与外运"),
        ("3", "PP-P3-002", "中海壳牌三期45万吨共聚PP，2027上半年，高端牌号对进口替代的影响"),
        ("3", "PP-P1-005", "宝丰C2-C5项目50万吨自2023年环评后无任何报道，需确认是否并入四期"),
        ("4", "PP-P3-013", "宁煤MTP技改70万吨是净增还是置换，直接决定西北供给净增量"),
        ("4", "PP-P3-001", "宝丰新疆3×65万吨是远期最大变量，但仅到环评公示"),
    ]
    actions = {
        "PP-P1-003": "查中石化/华锦阿美及盘锦市政府通稿，检索'聚丙烯 中交/试车'",
        "PP-P1-008": "查镇海炼化官网、中石化工程部，或直接联系确认5#PP开车结果",
        "PP-P1-006": "按月跟踪设备安装完成率，或查兖矿能源月度经营数据",
        "PP-P1-004": "跟踪宝丰能源公告与上证e互动答复（每月）",
        "PP-P1-001": "查福建省能化集团官网与漳州市发改委，确认全面投产时点",
        "PP-P1-002": "查中国化学五环/十六化建通稿，确认聚合线负荷",
        "PP-P1-007": "查东明石化集团官网与菏泽生态环境局",
        "PP-P1-009": "查维远股份定期报告与业绩说明会（每季）",
        "PP-P3-005": "查新疆生态环境厅环评批复与中石化工程进度",
        "PP-P3-002": "查中海壳牌官网与惠州市政府通稿",
        "PP-P1-005": "查宁东管委会生态环境局与宝丰年报在建工程明细",
        "PP-P3-013": "查国能宁煤公告与宁夏生态环境厅，确认原装置关停",
        "PP-P3-001": "查新疆生态环境厅环评受理/批复公示",
    }
    pmap = {p["project_id"]: p for p in projects}
    for pri, pid, why in watch:
        p = pmap.get(pid)
        if not p:
            continue
        last = latest_progress(by.get(pid, []))
        r2 = body(ws, r, [pri, pid, p["owner"], p["project_name"], p["province"], cap_of(p),
                          p["stage"], (last or {}).get("desc", "")[:90], why,
                          p.get("watch", ""), actions.get(pid, "")],
                  fills={1: RED if pri == "1" else (WARN if pri == "2" else LIGHT)}, bold_cols=(1,))
        ws.cell(r2 - 1, 6).number_format = "0.0"
        ws.row_dimensions[r2 - 1].height = 56
        r = r2
    return ws


def sheet_gaps(wb, projects, progress):
    ws = wb.create_sheet("12.待补证清单")
    hdr = ["序号", "项目编号", "项目", "待补证事项", "影响", "建议核实渠道"]
    r = title_row(ws, "12. 待补证清单（明确的'未检索到公开报道'）",
                  len(hdr), "★把'找不到'写下来，比假装找到更有价值。这些空白决定了本台账哪些结论必须打问号。")
    header_row(ws, r, hdr, [6, 13, 36, 70, 40, 40])
    r += 1
    gaps = [
        ("PP-P1-008", "5#PP 是否于 2026 年 5 月初产出合格产品（会议目标）", "若已达成本库低估约 40 万吨；若未达成则延期成立", "镇海炼化、中石化工程部、宁波市发改委"),
        ("PP-P1-008", "5#PP 究竟是 30 万吨还是 50 万吨", "直接影响 20 万吨的年度统计", "中石化/宁波市发改委核准原文全文"),
        ("PP-P1-007", "东明盛海 PP 试车/投产的任何公开报道", "唯一支撑'2026-12 投产'的是行业资讯", "东明石化官网、菏泽市生态环境局、中化三建"),
        ("PP-P1-006", "荣信化工 PP 试车/投产公开报道", "设备安装仅 12%，年底投产存疑", "兖矿能源公告、荣信化工官网、鄂尔多斯市政府"),
        ("PP-P1-004", "宝丰宁东四期 PP 装置试车报道", "公司仅称 12 月下旬出合格乙烯丙烯", "宝丰能源公告、上证 e 互动"),
        ("PP-P1-005", "宝丰 C2-C5 项目 50 万吨 PP 自 2023 环评后的任何进展", "50 万吨完全无进度证据", "宁东管委会、宝丰能源年报在建工程"),
        ("PP-P1-003", "华锦阿美 PP 装置单独的中交或试车通稿", "PP 进度全部靠整批机械竣工清单推断", "华锦阿美官网、盘锦市政府、中国化学各承建单位"),
        ("PP-P1-009", "利华益维远第二套 20 万吨 PP 是否实际建设", "按 40 万吨统计可能高估 20 万吨", "维远股份年报在建工程明细"),
        ("PP-P1-009", "维远第一套 PP 是否已开车出料", "公司口径为'择机试生产'", "维远股份公告、定期报告"),
        ("PP-P3-016", "广西石化 40 万吨 PP 装置是否已投产出料", "已按'投产（需补证）'处理", "广西石化官网、钦州市政府、中国石油新闻中心"),
        ("PP-P3-024", "中科炼化二期 PP 具体产能", "本库未设数字", "中科炼化环评报告书全文"),
        ("PP-P3-025", "内蒙古大路项目 80 万吨聚烯烃中 PP 的拆分", "本库未设数字", "中国石化环评受理公示全文"),
        ("PP-P3-001", "宝丰新疆 400 万吨项目是否有环评批复", "目前仅到环评第一次公示（C 级）+ 自媒体（D 级）", "新疆生态环境厅、准东开发区官网"),
        ("PP-P3-008", "茂名石化乙烯提质改造中原 PP 装置是否同步退出", "决定 50 万吨是净增还是置换", "茂名石化环评报告书、中国石化关停公告"),
        ("PP-P3-009", "扬子石化原 PP 装置是否同步退出", "决定 40 万吨是净增还是置换", "扬子石化环评报告书、中国石化关停公告"),
        ("PP-P3-013", "宁煤 MTP 技改中原装置退出量", "决定 70 万吨是净增还是置换", "国家能源集团公告、宁夏生态环境厅"),
        ("PP-P3-010", "福建永荣 80 万吨 PP 的投产时间", "本库用 2027-06 作工作假设，无来源", "永荣控股官网、福州市政府"),
        ("PP-P3-011", "上景新材 150 万吨 PP 是否分期/是否开工", "单位投资强度仅 0.235 亿元/万吨，异常低", "福建省生态环境厅环评批复全文"),
        ("PP-P3-015", "桐昆钦州项目是否停工或缩减", "原计划 2025-06 竣工，已延期 24 个月无报道", "桐昆股份公告、钦州市政府"),
        ("PP-P3-019", "乌石化 45 万吨 PP 装置实际开车时点", "'转入生产准备'不等于投产", "乌鲁木齐石化、中国石油新闻中心"),
        ("PP-P3-003", "大连石化老厂关停时点与 PP 退出量", "决定西中岛项目是净增还是置换", "中国石油公告、大连市政府"),
        ("PP-P3-026", "东华能源茂名二期是否启动", "150-200 万吨为规划口径", "东华能源公告、茂名市政府"),
    ]
    pmap = {p["project_id"]: p for p in projects}
    for i, (pid, what, impact, channel) in enumerate(gaps, 1):
        p = pmap.get(pid, {})
        r2 = body(ws, r, [i, pid, p.get("project_name", ""), what, impact, channel],
                  fills={4: WARN}, bold_cols=(4,))
        ws.row_dimensions[r2 - 1].height = 40
        r = r2
    return ws


# ---------------------------------------------------------------- 主入口
def build_excel(proj_dir):
    projects, progress, sources, cfg = load(proj_dir)
    plist = projects["projects"]
    wb = Workbook()
    wb.remove(wb.active)

    sheet_cover(wb, plist, progress, sources, cfg, plist)
    sheet_projects(wb, plist, progress, sources)
    sheet_units(wb, plist)
    sheet_progress(wb, plist, progress, sources)
    sheet_history(wb, plist, progress)
    sheet_sources(wb, sources, plist, progress)
    sheet_yearly(wb, proj_dir, cfg, plist)
    _, tot = sheet_deferred(wb, proj_dir, cfg, plist)
    sheet_conflict(wb, plist)
    sheet_excluded(wb, projects)
    sheet_region(wb, proj_dir, cfg, plist)
    sheet_route(wb, plist, cfg)
    sheet_watch(wb, plist, progress, sources)
    sheet_gaps(wb, plist, progress)

    out = os.path.join(proj_dir, "out")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "%s新增产能与项目跟踪台账_%s.xlsx"
                        % (prod_label(cfg), cfg.get("as_of", "").replace("-", "")))
    wb.save(path)

    # 每次生成都留一份数据快照，便于回溯"当时看到的是什么"
    try:
        import shutil
        snap = os.path.join(proj_dir, "snapshots")
        os.makedirs(snap, exist_ok=True)
        dest = os.path.join(snap, cfg.get("as_of", "").replace("-", "") or "latest")
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(os.path.join(proj_dir, "data"), dest,
                        ignore=shutil.ignore_patterns("geo_cn.json"))
    except Exception as e:  # 快照失败不阻断产出
        print("[WARN] 快照失败：%s" % e)
    return path


if __name__ == "__main__":
    print(build_excel(sys.argv[1] if len(sys.argv) > 1 else "."))
