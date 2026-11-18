# -*- coding: utf-8 -*-
"""示例采购清单生成器：XLSX（含“填表说明”页与脏数据）+ CSV + JSON。

生成是确定性的：固定 seed、固定日期，重复运行结果一致。
用途：README 示例、QA 回归、演示“多种格式/多种复杂程度”的输入。
"""
from __future__ import annotations

import csv
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "examples", "purchase-lists", "northeast-china-plant"))

TITLE = "【模拟数据】东北某化工工厂 2027 年度大宗化工原料采购清单（仅用于寻源方法演示）"
SUBTITLE = ("说明：本清单由示例生成器造数，企业名、数量、用途均为虚构；CAS、危险属性、国标号为公开常识，"
            "不代表真实交易。请勿用于对外询价或审计。")

HEADERS = ["序号", "物料名称", "CAS号", "形态/规格", "技术要求", "数量", "单位", "年用量", "包装", "交付地点", "用途", "现有供应商", "备注"]

ROWS = [
    # —— 基线：8 个主料，规格清楚
    ["纯碱（重质）", "497-19-8", "重质", "GB/T 210 II 类优等品，主含量≥99.2%，铁(Fe)≤0.003%", 600, "吨", 7200, "1000kg 吨袋", "辽宁·大连", "玻璃窑炉配料", "某碱厂", "粉体罐车直送"],
    ["烧碱（32%液碱）", "1310-73-2", "32%液碱", "GB/T 209 一等品，NaOH≥32.0%，碳酸钠≤0.2%", 900, "吨", 10800, "槽罐车", "辽宁·大连", "清洗/净水/PH 调节", "", "冬季防冻需保温罐车"],
    ["氯化钙（二水片状）", "10043-52-4", "二水片状", "HG/T 2327 工业级，CaCl2≥74%", 450, "吨", 5400, "25kg 编织袋", "辽宁·大连", "融雪剂/干燥剂", "", "冬季旺季，需提前锁量"],
    ["过氧化氢 27.5%", "7722-84-1", "27.5%", "GB/T 1616 工业级，≥27.5%", 300, "吨", 3600, "槽罐车", "辽宁·大连", "漂白/氧化", "", "危化品，需具备运输资质方"],
    ["乙二醇（聚酯级）", "107-21-1", "聚酯级", "GB/T 4649 聚酯级，纯度≥99.9%", 240, "吨", 2880, "槽罐车", "辽宁·大连", "防冻液/中间体", "", ""],
    ["工业盐", "7647-14-5", "精制干盐", "GB/T 5462 精制工业盐一级，NaCl≥99.1%", 1200, "吨", 14400, "50kg 袋/散装", "辽宁·大连", "氯碱/融雪", "", "量大，建议多源"],
    ["双氧水35%", "7722-84-1", "35%", "≥35%", 120, "吨", 1440, "槽罐车", "辽宁·大连", "氧化/漂白", "", "与上一行同物质不同浓度"],
    ["氯化钙溶液32%", "10043-52-4", "32% 溶液", "CaCl2≥32%", 200, "吨", 2400, "槽罐车", "辽宁·大连", "融雪/除尘", "", "液体，需罐车"],
    ["片碱（99%）", "1310-73-2", "片碱 99%", "NaOH≥99%，片状", 60, "吨", 720, "25kg 袋", "辽宁·大连", "调节 PH", "", "片碱货源分散"],
    # —— 歧义/单位/缺失
    ["甘油", "", "99.5%", "", 8, "桶", 96, "250kg/桶", "辽宁·大连", "助剂", "", "桶数×净重换算，清单未填净重"],
    ["双氧水（50%）", "", "50%", "", 40, "吨", 480, "槽罐车", "辽宁·大连", "氧化", "", "浓度高，需专用槽罐"],
    ["烧碱（片碱）?", "", "", "", 30, "吨", 360, "25kg 袋", "辽宁·大连", "PH 调节", "", "品名带问号，与上一“片碱”可能是同一物料"],
    ["纯碱 99.2%", "", "轻质", "主含量 99.2%", 200, "-", 0, "散装", "辽宁·大连", "玻璃配料", "", "单位填“-”"],
    ["硫磺", "7704-34-9", "块状", "", 40, "吨", 480, "吨袋", "辽宁·大连", "制硫酸", "", ""],
    ["硫酸", "7664-93-9", "98%", "GB/T 534 工业级", 150, "吨", 1800, "槽罐车", "辽宁·大连", "中和/制盐", "", ""],
    ["柠檬酸", "77-92-9", "一水", "食品级", 20, "吨", 240, "25kg 袋", "辽宁·大连", "清洗", "", ""],
    ["硼砂", "1303-96-4", "十水", "", 15, "吨", 180, "25kg 袋", "辽宁·大连", "助熔", "", ""],
    # —— P0 级异常
    ["烧碱?碱?", "", "", "", 10, "吨", 120, "25kg 袋", "辽宁·大连", "清洗", "", "名称残缺"],
    ["乙二醇", "107-20-1", "", "", 60, "吨", 720, "槽罐车", "辽宁·大连", "防冻液", "", "CAS 疑似错写（校验位错误）"],
    ["重酸", "", "", "", 5, "吨", 60, "桶", "辽宁·大连", "中和", "", "非规范名称"],
    ["氯化钙", "", "散装", "", 0, "吨", 0, "", "辽宁·大连", "融雪", "", "数量为 0，是否为预估项"],
]


def _style_sheet(ws, title, subtitle, headers, n_cols, header_row_idx=3):
    thin = Side(style="thin", color="D0D7E2")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n_cols)
    ws.cell(row=1, column=1, value=title).font = Font(name="微软雅黑", size=14, bold=True, color="9A3412")
    ws.cell(row=2, column=1, value=subtitle).font = Font(name="微软雅黑", size=9, color="B45309")
    ws.cell(row=2, column=1).alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[2].height = 34
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=header_row_idx, column=c, value=headers[c - 1])
        cell.font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0F766E")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    return thin


def build_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "采购清单"
    thin = _style_sheet(ws, TITLE, SUBTITLE, HEADERS, len(HEADERS))
    for r_i, row in enumerate(ROWS, start=4):
        ws.cell(row=r_i, column=1, value=r_i - 3)
        for c_i, v in enumerate(row, start=2):
            cell = ws.cell(row=r_i, column=c_i, value=v)
            cell.font = Font(name="微软雅黑", size=9)
            cell.alignment = Alignment(vertical="center", wrap_text=c_i in (6, 13))
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if c_i in (6, 8) and isinstance(v, (int, float)):
                cell.number_format = "#,##0"
            if isinstance(v, str) and v.startswith(("?", "-")) or v == "":
                pass
    widths = [6, 20, 13, 12, 42, 9, 6, 10, 13, 11, 16, 12, 26]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B4"
    ws.sheet_view.showGridLines = False

    ws2 = wb.create_sheet("填表说明")
    notes = [
        ("字段", "填写要求", "示例"),
        ("物料名称", "优先使用行业通用名+形态/浓度；有歧义时同时给出 CAS", "烧碱（32%液碱）"),
        ("CAS号", "纯数字格式 xxxx-xx-x，不要带 CAS 前缀", "1310-73-2"),
        ("形态/规格", "浓度、品级、片/粉/液、是否有水合物", "二水片状"),
        ("技术要求", "执行标准、关键指标限值、检测方法", "GB/T 210 II 类优等品，Fe≤0.003%"),
        ("数量/单位", "数量必须是数字；单位统一到 吨/千克/立方米/万Nm3；不要用 '-'、'车'、'批'", "600 吨"),
        ("年用量", "年度合计用量，用于判断规模与供货保障能力", "7200"),
        ("包装", "吨袋/25kg 袋/槽罐车/IBC，影响运费与起订量", "1000kg 吨袋"),
        ("交付地点", "到厂地址或园区，至少到城市", "辽宁·大连"),
        ("用途", "决定规格优先级（如光伏玻璃级 vs 日用玻璃级）", "玻璃窑炉配料"),
        ("现有供应商", "可留空；用于评估切换风险", "某碱厂"),
        ("备注", "特殊要求：危运资质、冬季防冻、非标牌号等", "需具备危化品运输资质"),
        ("", "", ""),
        ("提示", "本文件为模拟数据；请勿把本清单的数据引用为真实采购需求。", ""),
        ("提示", "正常采购清单只需包含除示例外的列；缺失列会进入“待确认事项”，不会阻塞其余物料。", ""),
    ]
    for r_i, (a, b, c) in enumerate(notes, start=1):
        for c_i, v in enumerate((a, b, c), start=1):
            cell = ws2.cell(row=r_i, column=c_i, value=v)
            cell.font = Font(name="微软雅黑", size=10, bold=(r_i == 1), color="FFFFFF" if r_i == 1 else "1F2937")
            if r_i == 1:
                cell.fill = PatternFill("solid", fgColor="334155")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws2.column_dimensions["A"].width = 16
    ws2.column_dimensions["B"].width = 62
    ws2.column_dimensions["C"].width = 30
    ws2.sheet_view.showGridLines = False
    wb.save(path)


def build_csv(path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        for i, row in enumerate(ROWS, start=1):
            w.writerow([i] + row)


def build_json(path):
    data = {"_meta": {"title": TITLE, "subtitle": SUBTITLE, "simulated": True},
            "fields": HEADERS,
            "rows": []}
    for i, row in enumerate(ROWS, start=1):
        rec = {"序号": i}
        for h, v in zip(HEADERS[1:], row):
            rec[h] = v
        rec["批次"] = "B-2027Q1" if i <= 9 else "B-2027Q2"
        rec["采购地区"] = "华东"
        data["rows"].append(rec)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs(OUT, exist_ok=True)
    build_xlsx(os.path.join(OUT, "purchase_list_simulated.xlsx"))
    build_csv(os.path.join(OUT, "purchase_list_simulated.csv"))
    build_json(os.path.join(OUT, "purchase_list_simulated.json"))
    # 极简清单：只有名称/数量/单位，用于演示“稀疏字段”
    minimal = os.path.join(OUT, "purchase_list_minimal.csv")
    with open(minimal, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["品名", "数量", "单位"])
        for n, q, u in [("纯碱", 300, "吨"), ("液碱", 200, "吨"), ("氯化钙", 100, "吨"), ("乙二醇", 50, "吨")]:
            w.writerow([n, q, u])
    print("OK", OUT)


if __name__ == "__main__":
    main()
