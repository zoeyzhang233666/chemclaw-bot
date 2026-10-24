#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_excel.py —— 海外供应市场研究 Skill 的 Excel 生成器

用法：
    python build_excel.py <data.json> <output.xlsx>

输出 12 个工作表：
    00_说明与口径 / 01_企业与生产主体 / 02_装置与产能 / 03_产能分层与口径 / 04_企业集中度
    05_原料与产业基础 / 06_出口年度 / 07_出口目的地 / 08_物流港口 / 09_政策监管
    10_供应事件 / 11_数据缺口 / 12_来源记录

设计原则：
    - 每个数字都带"口径 + 年份 + 来源ID"
    - 名义产能/实际产量/出口量/可供采购量分列，不互相推算
    - 缺失值写"数据缺口"并给出核实路径，不用 0 或估算填充
"""
import json, sys, os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.chart import BarChart, LineChart, Reference

# ---------- 样式 ----------
NAVY = "1F3864"; BLUE = "2E5C8A"; LIGHT = "D9E2F3"; GREY_C = "F2F2F2"
WARN_F = PatternFill("solid", fgColor="FFF2CC")
BAD_F = PatternFill("solid", fgColor="FCE4E4")
OK_F = PatternFill("solid", fgColor="E2EFDA")
ZEBRA_F = PatternFill("solid", fgColor="F7F9FC")
HEAD_F = PatternFill("solid", fgColor=NAVY)
SUB_F = PatternFill("solid", fgColor=LIGHT)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def style_header(ws, row, ncol, height=30):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEAD_F
        cell.font = Font(bold=True, color="FFFFFF", size=10.5)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = height

def style_body(ws, r0, r1, ncol, zebra=True):
    for r in range(r0, r1 + 1):
        for c in range(1, ncol + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = Font(size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = BORDER
            if zebra and (r - r0) % 2 == 1:
                cell.fill = ZEBRA_F

def set_widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

def title_row(ws, text, sub, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(bold=True, size=14, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=BLUE)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 26
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c2 = ws.cell(row=2, column=1, value=sub)
    c2.font = Font(size=9.5, italic=True, color="595959")
    c2.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[2].height = 18

def sheet(wb, name, title, sub, headers, widths, rows, freeze="A4", hrow=3):
    ws = wb.create_sheet(name)
    n = len(headers)
    title_row(ws, title, sub, max(n, 4))
    for i, h in enumerate(headers, 1):
        ws.cell(row=hrow, column=i, value=h)
    style_header(ws, hrow, n)
    for ri, row in enumerate(rows, start=hrow + 1):
        for ci, v in enumerate(row, start=1):
            ws.cell(row=ri, column=ci, value=v)
    style_body(ws, hrow + 1, hrow + len(rows), n)
    set_widths(ws, widths)
    ws.freeze_panes = freeze
    ws.auto_filter.ref = f"A{hrow}:{get_column_letter(n)}{hrow + len(rows)}"
    ws.sheet_view.showGridLines = False
    return ws

def build(data_path, out_path):
    D = json.load(open(data_path, encoding="utf-8"))
    M = D["meta"]
    wb = Workbook(); wb.remove(wb.active)
    plants = D["plants"]
    total_cap = sum(p["capacity_kt"] for p in plants)
    sites = D["sites"]
    east = sum(p["capacity_kt"] for p in plants if "波斯湾" in sites[p["site"]]["coast"])
    west = sum(p["capacity_kt"] for p in plants if "红海" in sites[p["site"]]["coast"])
    latest = D["trade"]["by_year"][-1]
    first = D["trade"]["by_year"][0]

    # ========== 00 说明与口径 ==========
    ws = wb.create_sheet("00_说明与口径")
    title_row(ws, f"{M['title']} · 数据工作簿", f"编制依据：海外供应市场研究 Skill v1.0 ｜ 研究基准日 {M['research_date']} ｜ 口径单位：{M['scale_note']}", 6)
    rows = [
        ("A. 报告定位", ""),
        ("研究对象", f"{M['country_cn']}（{M['country']}）— {M['product_cn']}（{M['product']}），HS {M['hs_code']}"),
        ("编制目的", M["prepared_for"]),
        ("重要时点说明", M["as_of_note"]),
        ("", ""),
        ("B. 四类口径（不可互相替代）", ""),
        ("① 名义设计产能", f"装置姓名牌（nameplate）能力，{total_cap} kt/a（12 套装置合计）。来源含公司年报、工程总包/技术许可公告、行业媒体检修名录三类，存在 ±5% 加总误差。"),
        ("② 实际产量", "沙特无逐企业 MEG 产量公开统计 → 【数据缺口】。不可用「产能×开工率」推算替代。"),
        ("③ 出口量", f"HS 2905.31 沙特申报出口，{latest['year']} 年 {latest['world_kt']} kt / {latest['world_musd']} 百万美元（UN Comtrade / WITS）。注意税号包含其他乙二醇。"),
        ("④ 可供采购量", "取决于长期合约结构、内部自用、流向偏好与通道可用性 → 【数据缺口】。不可用行业规模或出口量直接推算。"),
        ("", ""),
        ("C. 证据等级", ""),
        ("A 级", "官方年报 / 交易所公告 / 国家统计：可直接引用为事实"),
        ("B 级", "国际专业行业媒体（ICIS、Argus、MEES、OGJ、S&P Global、Reuters、CCFGroup）：装置级事实，可引用需注明报道方"),
        ("C 级", "行业数据库 / 第三方估算：仅作交叉参照"),
        ("D 级", "推算、推断或待核实：必须标注并给出核实路径"),
        ("", ""),
        ("D. 工作表索引", ""),
        ("01_企业与生产主体", "集团 vs 生产法人，股权结构、上市代码、接洽提示"),
        ("02_装置与产能", "逐套 MEG 装置：所在地、姓名牌产能、投产时间、证据等级、来源"),
        ("03_产能分层与口径", "名义产能按海岸/企业分层，并与第三方口径交叉核对"),
        ("04_企业集中度", "企业级份额、CR1/CR3/HHI、SABIC 体系合计"),
        ("05_原料与产业基础", "工艺路线与关键原料节点、配套、技术许可"),
        ("06_出口年度", "2021-2025 年出口总量/对华量/均价（含同比）"),
        ("07_出口目的地", "全部伙伴国逐年明细（178 条记录）"),
        ("08_物流港口", "出口港、至中国航线、船型、运保条件"),
        ("09_政策监管", "出口/原料/贸易救济/合规要求"),
        ("10_供应事件", "2011-2026 装置检修、通道中断、设施损毁时间线"),
        ("11_数据缺口", "无法核验项 + 核实路径 + 影响"),
        ("12_来源记录", "全部引用来源（标题/发布方/日期/URL/可信度/摘录）"),
    ]
    for i, (k, v) in enumerate(rows, start=4):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True, size=10, color=NAVY if k.endswith("）") is False else "000000")
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=6)
        c = ws.cell(row=i, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top"); c.font = Font(size=10)
        if k and not v:
            for cc in range(1, 7):
                ws.cell(row=i, column=cc).fill = SUB_F
            ws.cell(row=i, column=1).font = Font(bold=True, size=11, color=NAVY)
        if v:
            ws.row_dimensions[i].height = max(15, min(60, 14 * (len(v) // 60 + 1)))
    set_widths(ws, [26, 40, 40, 26, 26, 26])
    ws.sheet_view.showGridLines = False

    # ========== 01 企业与生产主体 ==========
    rows = []
    for c in D["companies"]:
        ps = [p for p in plants if p["company_id"] == c["id"]]
        cap = sum(p["capacity_kt"] for p in ps)
        rows.append([c["id"], c["name"], c["name_en"], c["type"], c["listed"], c["ownership"],
                     len(ps) if ps else 0,
                     cap if ps else "现无 MEG 装置",
                     f"{cap/total_cap*100:.1f}%" if ps else "—",
                     "、".join(sorted({sites[p["site"]]["name"].split(" ")[0] for p in ps})) if ps else "—",
                     c["note"], c["contact_hint"]])
    ws = sheet(wb, "01_企业与生产主体", "企业与生产主体核实",
               "区分「集团/控股平台」与「实际生产法人」：SABIC 不是装置持有者，MEG 产能由 SHARQ / YANPET / United / Yansab / Saudi Kayan 等法人持有；Sipchem、Tasnee 暂无 MEG 装置。",
               ["ID", "企业（中文/通称）", "英文名", "主体类型", "上市代码", "股权结构", "MEG 装置数",
                "MEG 名义产能 kt/a", "占全国", "所在工业城", "定位说明", "接洽提示"],
               [6, 34, 30, 18, 16, 30, 10, 15, 9, 16, 46, 40], rows)
    for r in range(4, 4 + len(rows)):
        v = ws.cell(row=r, column=8).value
        ws.cell(row=r, column=8).alignment = Alignment(horizontal="right")
        if isinstance(v, str):
            ws.cell(row=r, column=8).fill = PatternFill("solid", fgColor=GREY_C)

    # ========== 02 装置与产能 ==========
    rows = []
    for p in sorted(plants, key=lambda x: -x["capacity_kt"]):
        rows.append([p["id"], p["company"], p["company_id"], p["plant"],
                     sites[p["site"]]["name"], sites[p["site"]]["region"], sites[p["site"]]["coast"],
                     p["product"], p["capacity_kt"], f"{p['capacity_kt']/total_cap*100:.1f}%",
                     p["cap_basis"], p["startup"], p["evidence_level"],
                     p.get("conflict", ""), "是" if p.get("unverified") else "",
                     p["notes"], "、".join(p.get("source_ids", []))])
    ws = sheet(wb, "02_装置与产能", "MEG 装置与公开产能（逐套）",
               "名义设计产能（姓名牌）口径；每套装置单独一条记录，禁止把企业全部石化产品产能当作 MEG 产能。证据等级 A/B/C/D 见 00 说明。",
               ["装置ID", "生产法人", "企业ID", "装置/产线", "所在地", "省/地区", "海岸", "产品",
                "名义产能 kt/a", "占全国", "产能口径说明", "投产/商业化", "证据等级", "口径冲突",
                "待核实", "备注（检修/工艺/扩能）", "来源ID"],
               [8, 30, 8, 26, 26, 16, 10, 8, 13, 9, 46, 20, 9, 16, 8, 56, 20], rows)
    last = 3 + len(rows)
    ws.cell(row=last + 1, column=2, value="合计（姓名牌口径）").font = Font(bold=True)
    ws.cell(row=last + 1, column=9, value=f"=SUM(I4:I{last})").font = Font(bold=True)
    ws.cell(row=last + 1, column=9).number_format = "#,##0"
    for cc in range(1, 18):
        ws.cell(row=last + 1, column=cc).fill = SUB_F
        ws.cell(row=last + 1, column=cc).border = BORDER
    for r in range(4, last + 1):
        if ws.cell(row=r, column=15).value == "是":
            for cc in range(1, 18):
                ws.cell(row=r, column=cc).fill = WARN_F
        if ws.cell(row=r, column=14).value:
            ws.cell(row=r, column=14).fill = WARN_F
        if ws.cell(row=r, column=9).value:
            ws.cell(row=r, column=9).alignment = Alignment(horizontal="right")

    # ========== 03 产能分层与口径 ==========
    ws = wb.create_sheet("03_产能分层与口径")
    title_row(ws, "产能分层、海岸分布与第三方口径交叉核对",
              "名义产能只能与「同口径」的数字相加比较；本表把本报告核实口径与三份第三方/新闻口径并列，用于识别误差来源。", 6)
    hdr = ["层级", "口径/分组", "名义产能 kt/a", "占比", "第三方对照口径", "差异与说明"]
    for i, h in enumerate(hdr, 1):
        ws.cell(row=3, column=i, value=h)
    style_header(ws, 3, len(hdr))
    ly = D["capacity_summary"]
    rows = [
        ["全国", "本报告逐套核实合计（12 套）", total_cap, 1.0, ly["country_cross_check"].split("：")[1],
         "第三方口径略高，因部分第三方把 DEG/TEG 与闲置线一并计入"],
        ["东海岸", "朱拜勒（United 3 套 + SHARQ 4 套 + Kayan）", east, east / total_cap, ly["east_coast"]["cross_check"].split("：")[1],
         "本报告 SHARQ M1 为待核值(450kt)，若按第三方口径则高约 100–200 kt"],
        ["西海岸", "延布（YANPET 2 套 + Yansab）+ 拉比格（Petro Rabigh）", west, west / total_cap, ly["west_coast"]["cross_check"].split("：")[1],
         "本报告西海岸 2,200 kt 高于第三方 2,100 kt，差异来自 Yansab 700/770 与 Petro Rabigh 归属口径"],
    ]
    for r_i, r in enumerate(rows, start=4):
        for c_i, v in enumerate(r, 1):
            ws.cell(row=r_i, column=c_i, value=v)
    style_body(ws, 4, 6, len(hdr))
    for r in range(4, 7):
        ws.cell(row=r, column=3).alignment = Alignment(horizontal="right")
        ws.cell(row=r, column=4).number_format = "0.0%"
        ws.cell(row=r, column=4).alignment = Alignment(horizontal="right")
    # 口径梯度表
    ws.cell(row=9, column=1, value="四类口径的证据状态（不得互相推算）").font = Font(bold=True, size=11, color=NAVY)
    h2 = ["口径", "数值", "单位", "证据等级", "数据来源/状态", "是否可用于谈判"]
    for i, h in enumerate(h2, 1):
        ws.cell(row=10, column=i, value=h)
    style_header(ws, 10, len(h2))
    rows2 = [
        ["① 名义设计产能", total_cap, "kt/a", "A/B 混合", "12 套装置逐套核实（见 02 表）", "可作参考基数"],
        ["② 实际产量（全国）", "数据缺口", "kt", "—", "沙特无公开逐企业 MEG 产量", "不可"],
        ["② 实际产量（单点参考）", "24.7%（2026-04-15 开工率）", "%", "C", "CCFGroup 估算 S16", "仅作风险信号"],
        ["③ 出口量（2025）", latest["world_kt"], "kt", "A", "UN Comtrade / WITS S01", "可作分流判断"],
        ["③ 对华出口（2025）", latest["china_kt"], "kt", "A", "UN Comtrade / WITS S01", "可作目标量参照"],
        ["④ 可供采购量", "数据缺口", "kt", "—", "需企业访谈 + 发票/提单核验", "不可由①②③推算"],
    ]
    for r_i, r in enumerate(rows2, start=11):
        for c_i, v in enumerate(r, 1):
            ws.cell(row=r_i, column=c_i, value=v)
    style_body(ws, 11, 16, len(h2))
    for r in range(11, 17):
        if isinstance(ws.cell(row=r, column=2).value, str) and "缺口" in ws.cell(row=r, column=2).value:
            for cc in range(1, 7):
                ws.cell(row=r, column=cc).fill = BAD_F
        ws.cell(row=r, column=2).alignment = Alignment(horizontal="left")
    set_widths(ws, [30, 48, 18, 10, 46, 44])
    ws.sheet_view.showGridLines = False

    # ========== 04 企业集中度 ==========
    byc = sorted(D["concentration"]["by_company_2025_kt"], key=lambda x: -x["cap_kt"])
    rows = []
    cum = 0
    for i, c in enumerate(byc, 1):
        cum += c["cap_kt"]
        rows.append([i, c["company"], c["id"], c["cap_kt"], round(c["cap_kt"] / total_cap, 4),
                     round(cum / total_cap, 4), c["note"]])
    hhi = sum((r[3] / total_cap) ** 2 for r in rows) * 10000
    sabic = sum(r[3] for r in rows if r[2] in ("CO2", "CO3", "CO4", "CO5", "CO6"))
    ws = sheet(wb, "04_企业集中度", "生产与出口的企业集中程度",
               f"按生产法人计算（姓名牌产能口径，分母 {total_cap} kt/a）。CR1={rows[0][3]/total_cap*100:.1f}%，CR3={sum(r[3] for r in rows[:3])/total_cap*100:.1f}%，HHI={hhi:.0f}；SABIC 持股体系合计 {sabic} kt/a（{sabic/total_cap*100:.1f}%）。",
               ["排名", "生产法人", "企业ID", "名义产能 kt/a", "份额", "累计份额", "说明"],
               [6, 26, 8, 15, 10, 11, 46], rows)
    for r in range(4, 4 + len(rows)):
        ws.cell(row=r, column=5).number_format = "0.0%"; ws.cell(row=r, column=6).number_format = "0.0%"
        ws.cell(row=r, column=4).alignment = Alignment(horizontal="right")
    r0 = 5 + len(rows)
    extra = [("指标", "数值", "解读"),
             ("CR1", f"{rows[0][3]/total_cap*100:.1f}%", "第一大生产法人份额"),
             ("CR3", f"{sum(r[3] for r in rows[:3])/total_cap*100:.1f}%", "前三大合计"),
             ("HHI（生产法人级）", f"{hhi:.0f}", ">2500 视为高度集中"),
             ("SABIC 持股体系合计", f"{sabic/total_cap*100:.1f}%（{sabic} kt/a）", "统一销售平台加剧实际议价集中"),
             ("6 家生产法人", "100%", "无独立第三方法人进入 MEG 生产")]
    for i, (a, b, c) in enumerate(extra):
        ws.cell(row=r0 + i, column=1, value=a).font = Font(bold=True, size=10)
        ws.cell(row=r0 + i, column=2, value=b).alignment = Alignment(horizontal="right")
        ws.cell(row=r0 + i, column=3, value=c)
        if i == 0:
            for cc in range(1, 4):
                ws.cell(row=r0 + i, column=cc).fill = SUB_F
    # 图表
    ch = BarChart(); ch.type = "bar"; ch.title = "企业 MEG 名义产能（kt/a）"
    data = Reference(ws, min_col=4, min_row=3, max_row=3 + len(rows))
    cats = Reference(ws, min_col=2, min_row=4, max_row=3 + len(rows))
    ch.add_data(data, titles_from_data=True); ch.set_categories(cats)
    ch.height = 7; ch.width = 16; ch.legend = None
    ws.add_chart(ch, "I4")

    # ========== 05 原料与产业基础 ==========
    rows = [[f"F{i+1}", f["item"], f["role"], f["detail"], "、".join(f.get("source_ids", []))]
            for i, f in enumerate(D["feedstock"])]
    sheet(wb, "05_原料与产业基础", "原料来源与产业基础（按工艺路线组织）",
          "MEG 路线：乙烷/伴生气 → 蒸汽裂解制乙烯 → EO/EG 单元 → MEG；本表以工艺链为骨架，而不是按行业结构罗列。",
          ["ID", "环节/物料", "在链上的角色", "说明与证据", "来源ID"],
          [6, 24, 16, 92, 20], rows)

    # ========== 06 出口年度 ==========
    rows = []
    for i, y in enumerate(D["trade"]["by_year"]):
        pv = D["trade"]["by_year"][i - 1]["world_kt"] if i else None
        rows.append([y["year"], y["world_kt"], y["world_musd"],
                     round(y["world_kt"] / pv - 1, 4) if pv else "",
                     round(y["world_musd"] * 1e6 / (y["world_kt"] * 1e3)) if y["world_kt"] else "",
                     y["china_kt"], round(y["china_kt"] / y["world_kt"], 4),
                     y["china_musd"], round(y["china_musd"] * 1e6 / (y["china_kt"] * 1e3)) if y["china_kt"] else "",
                     round(y["china_kt"] / total_cap, 4),
                     "UN Comtrade / WITS（沙特申报）", "S01"])
    ws = sheet(wb, "06_出口年度", "出口规模与对华贸易（2021–2025）",
               f"HS 2905.31 沙特申报出口。{latest['year']} 年出口 {latest['world_kt']} kt，对华 {latest['china_kt']} kt（占 {latest['china_kt']/latest['world_kt']*100:.1f}%）。"
               f"「出口量/名义产能」列为比值参考，不是产量，也不代表可供采购量。",
               ["年份", "出口总量 kt", "出口额 百万美元", "总量同比", "出口均价 美元/吨",
                "对华出口 kt", "对华占比", "对华额 百万美元", "对华均价 美元/吨", "出口量/名义产能", "统计口径", "来源ID"],
               [8, 14, 16, 11, 14, 13, 10, 15, 14, 14, 26, 8], rows)
    for r in range(4, 4 + len(rows)):
        ws.cell(row=r, column=4).number_format = "0.0%"
        ws.cell(row=r, column=7).number_format = "0.0%"
        ws.cell(row=r, column=10).number_format = "0.0%"
        for c in (2, 3, 5, 6, 8, 9):
            ws.cell(row=r, column=c).number_format = "#,##0"
    ch = BarChart(); ch.title = "出口量与对华出口量（kt）"
    ch.add_data(Reference(ws, min_col=2, max_col=2, min_row=3, max_row=3 + len(rows)), titles_from_data=True)
    ch.add_data(Reference(ws, min_col=6, max_col=6, min_row=3, max_row=3 + len(rows)), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=4, max_row=3 + len(rows)))
    ch.height = 8; ch.width = 18; ws.add_chart(ch, "N4")

    # ========== 07 出口目的地 ==========
    rows = []
    for y in D["trade"]["by_year"]:
        for p in y["partners"]:
            rows.append([y["year"], p["p"], p["kt"], round(p["kt"] / y["world_kt"], 4),
                         "当年出口总量", y["world_kt"], "UN Comtrade / WITS", "S01"])
    ws = sheet(wb, "07_出口目的地", "主要出口目的地（各国逐年）",
               "仅为各年前 7–10 大目的地（完整 178 条伙伴-年记录见 data.json / WITS 原始页）。中国始终为第一大目的地且份额持续上升。",
               ["年份", "目的国/地区", "数量 kt", "占当年出口", "占基准", "当年出口总量 kt", "统计口径", "来源ID"],
               [8, 24, 12, 12, 14, 16, 26, 8], rows)
    for r in range(4, 4 + len(rows)):
        ws.cell(row=r, column=4).number_format = "0.0%"
        ws.cell(row=r, column=3).number_format = "#,##0"
        if ws.cell(row=r, column=2).value == "China":
            for cc in range(1, 9):
                ws.cell(row=r, column=cc).fill = OK_F

    # ========== 08 物流港口 ==========
    rows = []
    for p in D["logistics"]["ports"]:
        rows.append([p["id"], p["name"], p["coast"], p["role"], p["lat"], p["lng"], p["detail"], "、".join(p.get("source_ids", []))])
    ws = sheet(wb, "08_物流港口", "出口港口（第一部分）", "工业港与商业港分工；经纬度用于 HTML 地图定位。",
               ["ID", "港口", "海岸", "服务定位", "纬度", "经度", "基础设施与证据", "来源ID"],
               [6, 40, 10, 30, 9, 9, 78, 18], rows)
    r0 = 4 + len(rows) + 2
    ws.cell(row=r0 - 1, column=1, value="至中国主要港口的路线条件").font = Font(bold=True, size=11, color=NAVY)
    h2 = ["装货地", "航线（经）", "航程", "2026 年状态", "来源ID"]
    for i, h in enumerate(h2, 1):
        ws.cell(row=r0, column=i, value=h)
    style_header(ws, r0, len(h2))
    for i, r in enumerate(D["logistics"]["routes_to_china"], start=r0 + 1):
        for j, v in enumerate([r["from"], r["via"], r["normal_days"], r["status_2026"], "、".join(r["source_ids"])], 1):
            ws.cell(row=i, column=j, value=v)
    style_body(ws, r0 + 1, r0 + len(D["logistics"]["routes_to_china"]), len(h2))
    r1 = r0 + len(D["logistics"]["routes_to_china"]) + 2
    ws.cell(row=r1 - 1, column=1, value="船型与运保条件").font = Font(bold=True, size=11, color=NAVY)
    facts = [("典型船型", D["logistics"]["vessel"]["typical_dwt"]),
             ("单航次货量", D["logistics"]["vessel"]["cargo_per_voyage"]),
             ("运费序列", "【数据缺口】未取得可公开核验的分航线散水运价序列"),
             ("2026 年运保变化", D["logistics"]["freight_2026_evidence"]),
             ("中国目的港", "；".join(f"{x['port']}（{x['note']}）" for x in D["logistics"]["china_ports"]))]
    for i, (k, v) in enumerate(facts, start=r1):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True, size=10)
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=8)
        ws.cell(row=i, column=2, value=v).alignment = Alignment(wrap_text=True, vertical="top")

    # ========== 09 政策监管 ==========
    rows = [[p["id"], p["type"], p["title"], p["detail"], p["level"], "、".join(p.get("source_ids", [])) or "需官网复核"]
            for p in D["policy"]]
    sheet(wb, "09_政策监管", "与生产、出口有关的政策与监管要求",
          "分两类：出口国（沙特）制度条件 与 进口方（中国）+ 贸易救济/合规条件；标「需官网复核」的为常识性监管事实，签约前必须以官方最新公告核定。",
          ["ID", "类别", "事项", "内容与对采购的影响", "可核验度", "来源ID"],
          [6, 18, 32, 96, 18, 20], rows)

    # ========== 10 供应事件 ==========
    rows = [[e["id"], e["date"], e["title"], e["type"], e["impact"], e["detail"], "、".join(e.get("source_ids", []))]
            for e in D["events"]]
    ws = sheet(wb, "10_供应事件", "可能影响供应的公开事件时间线（2011–2026）",
               "含装置检修、装置故障、新增产能、通道中断、设施损毁、市场后果。2026 年事件集中且影响等级最高。",
               ["ID", "日期", "事件", "类型", "影响强度", "内容与依据", "来源ID"],
               [6, 14, 34, 14, 10, 96, 20], rows)
    for r in range(4, 4 + len(rows)):
        v = ws.cell(row=r, column=5).value
        if v in ("极高", "高"):
            ws.cell(row=r, column=5).fill = BAD_F
        elif v == "正向":
            ws.cell(row=r, column=5).fill = OK_F
        elif v == "中":
            ws.cell(row=r, column=5).fill = WARN_F

    # ========== 11 数据缺口 ==========
    rows = [[i + 1, u["item"], u["why"], u["how"], u["impact"]] for i, u in enumerate(D["unverified"])]
    sheet(wb, "11_数据缺口", "尚无法核实的数据与核实路径",
          "凡无法公开核实的数字，一律列为缺口并给出可执行的核实路径；不做填补式估算，不以行业规模倒推可供采购量。",
          ["#", "缺口项", "为什么无法确认", "核实路径", "对采购决策的影响"],
          [5, 34, 54, 46, 34], rows)

    # ========== 12 来源记录 ==========
    rows = []
    for s in D["sources"]:
        rows.append([s["id"], s["title"], s["publisher"], s["date"], s["type"], s["reliability"],
                     s["url"], s["note"]])
    ws = sheet(wb, "12_来源记录", "来源记录（可点击核验）",
               "每条来源保留标题、发布方、日期、类型、可信度与关键摘录；URL 可直接打开原文。",
               ["ID", "标题", "发布方", "日期", "类型", "可信度", "URL", "关键摘录（口径说明）"],
               [6, 56, 30, 22, 20, 10, 60, 82], rows)
    for r in range(4, 4 + len(rows)):
        c = ws.cell(row=r, column=7)
        if c.value:
            c.hyperlink = c.value
            c.font = Font(size=9.5, color="0563C1", underline="single")
        if ws.cell(row=r, column=6).value == "高":
            ws.cell(row=r, column=6).fill = OK_F

    # ---------- 合并单元格外边框 ----------
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from outline_merged import outline_all
        for _ws in wb.worksheets:
            outline_all(_ws)
    except ImportError:
        pass

    # ---------- 保存 ----------
    wb.properties.title = M["title"]
    wb.properties.subject = "海外供应市场研究"
    wb.properties.creator = "海外供应市场研究 Skill v1.0"
    wb.properties.description = M["as_of_note"]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    wb.save(out_path)
    print(f"[OK] Excel 已生成：{out_path}")
    print(f"     工作表：{len(wb.sheetnames)} 个 -> {', '.join(wb.sheetnames)}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(2)
    build(sys.argv[1], sys.argv[2])
