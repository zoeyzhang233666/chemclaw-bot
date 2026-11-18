#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_xlsx.py — data.json → 多工作表 Excel 工作簿（12 表，含实时公式）

工作表：
 00 封面与结论   01 产品属性     02 HS候选      03 法规依据
 04 单证要求     05 已上传文件   06 缺失资料    07 责任主体
 08 待确认事项   09 危险属性对照 10 税费测算    11 进度看板

用法：
    python scripts/render_xlsx.py examples/h2o2-kr-30/data.json -o out/dossier.xlsx
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import imrules as R  # noqa: E402

# ---------------------------------------------------------------- 样式
INK = "FF1C2327"
INK2 = "FF333A3F"
PAPER = "FFF4F2EC"
CARD = "FFFFFEFB"
HEAD = "FF1C2327"
COPPER = "FFA4552A"
LINE = "FFDFDBD0"
OK = "FF1E6B47"
OKBG = "FFE4F1E9"
WARN = "FF8F6212"
WARNBG = "FFF9EFD7"
BAD = "FFA3311F"
BADBG = "FFF9E4DF"
INFO = "FF2C5A86"
INFOBG = "FFE5EEF7"
GRAYBG = "FFECEEEC"

THIN = Side(style="thin", color=LINE)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_BODY = Font(name="微软雅黑", size=10, color=INK2)
F_SMALL = Font(name="微软雅黑", size=9, color="FF5B646A")
F_HEAD = Font(name="微软雅黑", size=10, bold=True, color="FFFFFFFF")
F_TITLE = Font(name="微软雅黑", size=16, bold=True, color=INK)
F_H2 = Font(name="微软雅黑", size=11, bold=True, color=COPPER)
F_MONO = Font(name="Consolas", size=9.5, color=INK2)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
FILL_HEAD = PatternFill("solid", fgColor=HEAD)


def sheet_title(ws, title, subtitle, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=title)
    c.font = F_TITLE
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c2 = ws.cell(row=2, column=1, value=subtitle)
    c2.font = F_SMALL
    c2.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[2].height = 26
    for col in range(1, ncol + 1):
        ws.cell(row=3, column=col).fill = PatternFill("solid", fgColor=COPPER)
    ws.row_dimensions[3].height = 2


def header(ws, row, cols, widths=None):
    for i, name in enumerate(cols, start=1):
        c = ws.cell(row=row, column=i, value=name)
        c.font = F_HEAD
        c.fill = FILL_HEAD
        c.alignment = CENTER
        c.border = BOX
    ws.row_dimensions[row].height = 28
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)
    ws.auto_filter.ref = f"A{row}:{get_column_letter(len(cols))}{row}"


def put(ws, row, values, fills=None, fonts=None, height=None, mono_cols=()):
    for i, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = F_MONO if i in mono_cols else F_BODY
        c.alignment = WRAP if i > 1 else Alignment(vertical="top", wrap_text=True)
        c.border = BOX
        if fills and i in fills:
            c.fill = PatternFill("solid", fgColor=fills[i])
        if fonts and i in fonts:
            c.font = fonts[i]
    if height:
        ws.row_dimensions[row].height = height


VERDICT_FILL = {"applies": BADBG, "conditional": WARNBG, "not_applies": OKBG, "pending": INFOBG}
STATUS_FILL = {"ok": OKBG, "partial": WARNBG, "missing": BADBG, "pending": INFOBG, "expired": BADBG, "na": GRAYBG}
PRI_FILL = {"P0": BADBG, "P1": WARNBG, "P2": INFOBG}


# ---------------------------------------------------------------- 各表
def sh_cover(wb, d, grade):
    ws = wb.create_sheet("00 封面与结论")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 96
    ws.column_dimensions["D"].width = 3

    r = 2
    ws.merge_cells(f"B{r}:C{r}")
    c = ws.cell(row=r, column=2, value="进口资料准备与合规核验底稿")
    c.font = Font(name="微软雅黑", size=19, bold=True, color=INK)
    ws.row_dimensions[r].height = 34
    r += 1
    ws.merge_cells(f"B{r}:C{r}")
    c = ws.cell(row=r, column=2, value=d["title"])
    c.font = Font(name="微软雅黑", size=12, color=COPPER, bold=True)
    c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[r].height = 34
    r += 2

    # 结论卡
    ws.merge_cells(f"B{r}:C{r}")
    c = ws.cell(row=r, column=2, value=f"总体结论：{grade['grade']} · {grade['grade_text']}")
    c.font = Font(name="微软雅黑", size=13, bold=True, color="FFFFFFFF")
    c.fill = PatternFill("solid", fgColor=(OK if grade["grade"] == "A" else WARN if grade["grade"] in ("B",) else BAD))
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[r].height = 28
    r += 1
    ws.merge_cells(f"B{r}:C{r}")
    c = ws.cell(row=r, column=2, value=d["assessment"]["one_liner"])
    c.font = F_BODY
    c.alignment = Alignment(wrap_text=True, vertical="top")
    c.fill = PatternFill("solid", fgColor=CARD)
    c.border = BOX
    ws.row_dimensions[r].height = 62
    r += 2

    meta_pairs = [
        ("记录编号", d["meta"]["record_id"]),
        ("基准日（as_of）", d["as_of"]),
        ("场景", d["meta"]["scene"]),
        ("整理 / 复核", d["meta"]["prepared_by"]),
        ("数据密级", d["meta"]["data_classification"]),
        ("方法论版本", d["meta"]["methodology_version"]),
        ("生成日期", d["meta"]["generated_at"]),
    ]
    ws.cell(row=r, column=2, value="一、底稿信息").font = F_H2
    r += 1
    for k, v in meta_pairs:
        ws.cell(row=r, column=2, value=k).font = F_SMALL
        c = ws.cell(row=r, column=3, value=v)
        c.font = F_BODY
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.cell(row=r, column=2).border = BOX
        c.border = BOX
        r += 1
    r += 1

    inp = d["inputs"]
    ws.cell(row=r, column=2, value="二、输入要素（任一变化须重跑）").font = F_H2
    r += 1
    ws.cell(row=r, column=2, value="要素").font = F_HEAD
    ws.cell(row=r, column=2).fill = FILL_HEAD
    ws.cell(row=r, column=3, value="取值").font = F_HEAD
    ws.cell(row=r, column=3).fill = FILL_HEAD
    r += 1
    for k, label in [("origin_country", "来源国家"), ("product_name_cn", "产品名称（中）"), ("product_name_en", "产品名称（英）"),
                     ("cas", "CAS"), ("concentration", "浓度/含量"), ("physical_form", "物理形态"), ("grade", "等级"),
                     ("usage", "用途"), ("packing", "包装"), ("package_type", "包装容器"), ("qty", "数量"),
                     ("transport_mode", "运输方式"), ("incoterm", "贸易术语"), ("pol_pod", "起运/目的港"),
                     ("supplier", "海外供应商"), ("importer", "进口企业")]:
        ws.cell(row=r, column=2, value=label).font = F_SMALL
        ws.cell(row=r, column=2).border = BOX
        c = ws.cell(row=r, column=3, value=inp.get(k, ""))
        c.font = F_BODY
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BOX
        r += 1
    r += 1

    ws.cell(row=r, column=2, value="三、结论分项").font = F_H2
    r += 1
    for k, v in d["assessment"]["verdict"].items():
        c1 = ws.cell(row=r, column=2, value=k)
        c1.font = Font(name="微软雅黑", size=10, bold=True, color=INK)
        c1.alignment = Alignment(vertical="top", wrap_text=True)
        c1.border = BOX
        c2 = ws.cell(row=r, column=3, value=v)
        c2.font = F_BODY
        c2.alignment = Alignment(wrap_text=True, vertical="top")
        c2.border = BOX
        ws.row_dimensions[r].height = max(30, 15 * (len(str(v)) // 52 + 1))
        r += 1
    r += 1

    ws.cell(row=r, column=2, value="四、结论口径（可以写 / 不能写）").font = F_H2
    r += 1
    ws.cell(row=r, column=2, value="可以写").font = F_HEAD
    ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=OK)
    ws.cell(row=r, column=3, value="不能写").font = F_HEAD
    ws.cell(row=r, column=3).fill = PatternFill("solid", fgColor=BAD)
    r += 1
    for a, b in d["assessment"]["statements"]:
        c1 = ws.cell(row=r, column=2, value=a)
        c1.font = F_BODY
        c1.alignment = WRAP
        c1.border = BOX
        c1.fill = PatternFill("solid", fgColor=OKBG)
        c2 = ws.cell(row=r, column=3, value=b)
        c2.font = F_BODY
        c2.alignment = WRAP
        c2.border = BOX
        c2.fill = PatternFill("solid", fgColor=BADBG)
        ws.row_dimensions[r].height = 34
        r += 1
    r += 1

    ws.merge_cells(f"B{r}:C{r}")
    c = ws.cell(row=r, column=2, value="免责声明：" + d["meta"].get("demo_notice", "") + " 本底稿是基于公开资料的准备性核验，不构成法律意见，也不替代海关、应急管理、公安等部门的实际认定。")
    c.font = F_SMALL
    c.alignment = Alignment(wrap_text=True, vertical="top")
    c.fill = PatternFill("solid", fgColor=GRAYBG)
    c.border = BOX
    ws.row_dimensions[r].height = 58


def sh_product(wb, d):
    ws = wb.create_sheet("01 产品属性")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "01 · 产品属性", "产品身份要素、组成与风险点。组成必须写到稳定剂——这是『过氧化氢的水溶液』能否成立的判断前提。", 6)
    r = 5
    ws.cell(row=r, column=1, value="身份判断").font = F_H2
    r += 1
    for k, v in [("身份结论", d["product_identity"]["identity_verdict"]),
                 ("一句话判断", d["product_identity"]["one_liner"])]:
        ws.cell(row=r, column=1, value=k).font = F_SMALL
        ws.cell(row=r, column=1).border = BOX
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        c = ws.cell(row=r, column=2, value=v)
        c.font = F_BODY
        c.alignment = WRAP
        c.border = BOX
        ws.row_dimensions[r].height = 46
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="组成（成分表）").font = F_H2
    r += 1
    header(ws, r, ["组分", "英文名", "CAS", "含量下限%", "含量上限%", "角色"],
           [30, 34, 16, 12, 12, 26])
    r += 1
    first = r
    for c in d["inputs"]["composition"]:
        put(ws, r, [c["name"], c.get("ename", ""), c.get("cas", ""), c["pct_min"], c["pct_max"], c.get("role", "")],
            mono_cols=(3,))
        r += 1
    put(ws, r, ["合计", "", "", f"=SUM(D{first}:D{r-1})", f"=SUM(E{first}:E{r-1})", ""],
        fonts={1: Font(name="微软雅黑", size=10, bold=True, color=INK)})
    for col in (4, 5):
        ws.cell(row=r, column=col).number_format = "0.000"
    ws.conditional_formatting.add(f"D{r}:E{r}",
        CellIsRule(operator="notBetween", formula=["99.99", "100.01"], fill=PatternFill("solid", fgColor=BADBG)))
    r += 2

    ws.cell(row=r, column=1, value="已确认要素").font = F_H2
    r += 1
    for x in d["product_identity"]["confirmed"]:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = ws.cell(row=r, column=1, value="✓  " + x)
        c.font = F_BODY
        c.alignment = WRAP
        c.border = BOX
        c.fill = PatternFill("solid", fgColor=OKBG)
        ws.row_dimensions[r].height = 26
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="仍未确认的要素").font = F_H2
    r += 1
    for x in d["product_identity"]["unconfirmed"]:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = ws.cell(row=r, column=1, value="?  " + x)
        c.font = F_BODY
        c.alignment = WRAP
        c.border = BOX
        c.fill = PatternFill("solid", fgColor=WARNBG)
        ws.row_dimensions[r].height = 26
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="身份风险点与处置").font = F_H2
    r += 1
    header(ws, r, ["风险点", "为什么是风险", "处置动作", "", "", ""], [30, 52, 52, 2, 2, 2])
    r += 1
    for x in d["product_identity"]["risk_points"]:
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
        put(ws, r, [x["item"], x["why"], x["action"]], height=52)
        r += 1


def sh_hs(wb, d):
    ws = wb.create_sheet("02 HS候选")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "02 · HS 编码候选与归类依据", "归类是一条推理链：章注/子目注释 → 品目条文 → 成立条件 → 不确定性。候选必须写出排名、置信度与推翻条件。", 8)
    r = 5
    header(ws, r, ["排名", "税则号列", "品目描述", "置信度", "归类依据", "成立条件", "不成立时去向", "来源"],
           [7, 18, 26, 10, 56, 46, 36, 12])
    r += 1
    for c in sorted(d["hs_candidates"], key=lambda x: x.get("rank", 9)):
        fill = {1: OKBG} if c.get("rank") == 1 else {}
        put(ws, r, [c.get("rank"), c["code"], c["desc"], c.get("confidence", ""), c["basis"],
                    c["tests"], c["alternatives"], c.get("source", "")], fills=fill, height=86, mono_cols=(2,))
        ws.cell(row=r, column=1).alignment = CENTER
        ws.cell(row=r, column=4).alignment = CENTER
        r += 1
    r += 1
    hv = d["hs_verdict"]
    ws.cell(row=r, column=1, value="归类结论").font = F_H2
    r += 1
    rows = [("推荐编码", hv["recommended"]), ("不确定性", hv["uncertainty"]),
            ("是否需要预裁定", hv["need_classification_ruling"]),
            ("规范申报要素（顺序）", " / ".join(hv["declaration_elements"])),
            ("填报示例", hv.get("declaration_example", "")),
            ("CIQ 扩展码", "\n".join(hv.get("ciq_codes", []))),
            ("CIQ 说明", hv.get("ciq_note", ""))]
    for k, v in rows:
        ws.cell(row=r, column=1, value=k).font = F_SMALL
        ws.cell(row=r, column=1).border = BOX
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        c = ws.cell(row=r, column=2, value=v)
        c.font = F_MONO if k in ("填报示例", "CIQ 扩展码", "推荐编码") else F_BODY
        c.alignment = WRAP
        c.border = BOX
        ws.row_dimensions[r].height = max(22, 13 * (len(str(v)) // 90 + 1))
        r += 1


def sh_regulation(wb, d):
    ws = wb.create_sheet("03 法规依据")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "03 · 监管事项与法规依据", "每条结论都带：判定四态 / 条文依据 / 适用条件 / 对本单影响 / 责任方 / 可回溯来源编号。『待核验』不等于『不适用』。", 10)
    r = 5
    header(ws, r, ["编号", "管理层", "监管事项", "判定", "结论", "依据（条文）", "来源编号",
                   "适用条件", "对本单的影响", "责任方", "置信"],
           [8, 15, 26, 12, 54, 52, 13, 40, 38, 18, 8])
    r += 1
    for x in d["regulation_checklist"]:
        v = x["verdict"]
        put(ws, r, [x["id"], x["layer"], x["item"], R.VERDICT_TEXT.get(v, v), x["conclusion"], x["basis"],
                    x.get("source", ""), x.get("condition", ""), x.get("impact", ""), x.get("owner", ""),
                    x.get("confidence", "")],
            fills={4: VERDICT_FILL.get(v, GRAYBG)}, height=80)
        ws.cell(row=r, column=1).alignment = CENTER
        ws.cell(row=r, column=4).alignment = CENTER
        ws.cell(row=r, column=7).alignment = CENTER
        r += 1
    n = r - 1
    r += 1
    ws.cell(row=r, column=3, value="判定分布（公式统计）").font = F_H2
    r += 1
    for i, (k, label) in enumerate([("applies", "适用"), ("conditional", "视条件适用"),
                                    ("pending", "待核验"), ("not_applies", "不适用")]):
        ws.cell(row=r + i, column=3, value=label).font = F_SMALL
        c = ws.cell(row=r + i, column=4, value=f'=COUNTIF($D$6:$D${n},"{label}")')
        c.font = Font(name="微软雅黑", size=10, bold=True, color=INK)
        c.alignment = CENTER
        c.border = BOX
        c.fill = PatternFill("solid", fgColor=VERDICT_FILL.get(k, GRAYBG))


def sh_docs(wb, d):
    ws = wb.create_sheet("04 单证要求")
    ws.sheet_view.showGridLines = False
    comp = R.doc_completeness(d["documents"])
    sheet_title(ws, "04 · 单证要求", f"共 {len(d['documents'])} 项，加权完备度 {comp['pct']}%（必须=3 / 视情形=1 / 建议=0.5）。『状态』列可下拉修改，进度看板自动汇总。", 11)
    r = 5
    header(ws, r, ["编号", "分组", "文件名称（中）", "文件名称（英）", "要求", "状态", "依据",
                   "必备关键字段", "当前问题", "责任主体", "关联上传件"],
           [8, 16, 32, 38, 9, 11, 34, 44, 44, 20, 12])
    r += 1
    first = r
    for x in d["documents"]:
        st = x["status"]
        put(ws, r, [x["id"], x["group"], x["name_cn"], x["name_en"], x["required"],
                    R.DOC_STATUS_TEXT.get(st, st), x["basis"], x.get("content_check", ""),
                    x.get("issue", ""), x["owner"], x.get("uploaded_id", "")],
            fills={6: STATUS_FILL.get(st, GRAYBG)}, height=52)
        ws.cell(row=r, column=1).alignment = CENTER
        ws.cell(row=r, column=5).alignment = CENTER
        ws.cell(row=r, column=6).alignment = CENTER
        r += 1
    last = r - 1
    dv = DataValidation(type="list", formula1='"' + ",".join(R.DOC_STATUS_TEXT[s] for s in R.DOC_STATUS) + '"',
                        allow_blank=False, showDropDown=False)
    dv.error = "请从下拉中选择状态"
    ws.add_data_validation(dv)
    dv.add(f"F{first}:F{last}")
    ws.conditional_formatting.add(f"F{first}:F{last}",
        FormulaRule(formula=[f'$F{first}="缺失"'], fill=PatternFill("solid", fgColor=BADBG),
                    font=Font(name="微软雅黑", size=10, bold=True, color=BAD)))
    ws.conditional_formatting.add(f"F{first}:F{last}",
        FormulaRule(formula=[f'$F{first}="不完整"'], fill=PatternFill("solid", fgColor=WARNBG)))
    ws.conditional_formatting.add(f"F{first}:F{last}",
        FormulaRule(formula=[f'$F{first}="齐备"'], fill=PatternFill("solid", fgColor=OKBG)))

    r += 1
    ws.cell(row=r, column=2, value="状态汇总").font = F_H2
    r += 1
    for i, s in enumerate(R.DOC_STATUS):
        ws.cell(row=r + i, column=2, value=R.DOC_STATUS_TEXT[s]).font = F_SMALL
        c = ws.cell(row=r + i, column=3, value=f'=COUNTIF($F${first}:$F${last},"{R.DOC_STATUS_TEXT[s]}")')
        c.font = Font(name="微软雅黑", size=10, bold=True, color=INK)
        c.alignment = CENTER
        c.border = BOX
        c.fill = PatternFill("solid", fgColor=STATUS_FILL.get(s, GRAYBG))
    ws.cell(row=r + len(R.DOC_STATUS), column=2, value="合计").font = Font(name="微软雅黑", size=10, bold=True)
    c = ws.cell(row=r + len(R.DOC_STATUS), column=3, value=f"=SUM(C{r}:C{r+len(R.DOC_STATUS)-1})")
    c.font = Font(name="微软雅黑", size=10, bold=True, color=INK)
    c.alignment = CENTER
    c.border = BOX


def sh_uploaded(wb, d):
    ws = wb.create_sheet("05 已上传文件")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "05 · 已上传文件检查", "每份上传件做三件事：字段提取 → 要件核对 → 交叉一致性。标『模拟』的文件仅用于演示，供应商名称/批号/金额均为虚构。", 9)
    r = 5
    ws.cell(row=r, column=1, value="一、文件清单与结论").font = F_H2
    r += 1
    header(ws, r, ["编号", "文件名", "类型", "语言", "是否模拟", "接收日期", "结论", "结论说明", "模拟声明"],
           [8, 40, 9, 8, 10, 13, 14, 56, 46])
    r += 1
    for u in d["uploaded"]:
        v = u["verdict"]
        put(ws, r, [u["id"], u["file"], u["type"], u["lang"], "是" if u.get("is_mock") else "否",
                    u["received"], R.UPLOAD_TEXT.get(v, v), u.get("verdict_note", ""), u.get("mock_note", "")],
            fills={7: STATUS_FILL.get({"usable": "ok", "usable_with_fix": "partial", "not_usable": "missing"}[v], GRAYBG)},
            height=44)
        for col in (1, 3, 4, 5, 6, 7):
            ws.cell(row=r, column=col).alignment = CENTER
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="二、字段提取").font = F_H2
    r += 1
    header(ws, r, ["文件编号", "字段", "提取值", "位置"], [12, 26, 72, 16])
    r += 1
    for u in d["uploaded"]:
        for e in u.get("extracted", []):
            put(ws, r, [u["id"], e["field"], e["value"], e.get("page_ref", "")], mono_cols=(3,))
            ws.cell(row=r, column=1).alignment = CENTER
            ws.cell(row=r, column=4).alignment = CENTER
            r += 1
    r += 1

    ws.cell(row=r, column=1, value="三、检查项").font = F_H2
    r += 1
    header(ws, r, ["检查项编号", "文件编号", "检查内容", "结果", "说明"], [14, 12, 40, 10, 76])
    r += 1
    sym = {"pass": "通过", "fail": "不通过", "warn": "存疑", "na": "不适用"}
    for u in d["uploaded"]:
        for c in u.get("checks", []):
            res = c["result"]
            put(ws, r, [c["id"], u["id"], c["item"], sym.get(res, res), c.get("note", "")],
                fills={4: STATUS_FILL.get({"pass": "ok", "fail": "missing", "warn": "partial", "na": "na"}[res], GRAYBG)})
            ws.cell(row=r, column=1).alignment = CENTER
            ws.cell(row=r, column=2).alignment = CENTER
            ws.cell(row=r, column=4).alignment = CENTER
            r += 1
    r += 1

    ws.cell(row=r, column=1, value="四、交叉一致性冲突").font = F_H2
    r += 1
    header(ws, r, ["等级", "问题", "明细", "处置"], [8, 26, 80, 56])
    r += 1
    for x in R.consistency_issues(d):
        put(ws, r, [x["level"], x["item"], x["detail"], x["fix"]],
            fills={1: BADBG if x["level"] == "高" else WARNBG}, height=40)
        ws.cell(row=r, column=1).alignment = CENTER
        r += 1


def sh_gaps(wb, d):
    ws = wb.create_sheet("06 缺失资料")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "06 · 缺失资料清单", "P0 = 不取得不得报关/不得使用；P1 = 影响税费、时效或质量；P2 = 档案完善。『已完成』列可勾选，进度看板实时汇总。", 9)
    r = 5
    header(ws, r, ["编号", "优先级", "缺失资料", "为什么必须", "怎么要（动作）", "关联单证",
                   "责任主体", "是否阻断", "已完成"], [8, 9, 40, 60, 52, 14, 18, 9, 9])
    r += 1
    first = r
    order = {"P0": 0, "P1": 1, "P2": 2}
    for g in sorted(d["gaps"], key=lambda x: (order.get(x["priority"], 9), x["id"])):
        put(ws, r, [g["id"], g["priority"], g["missing"], g["why"], g["ask"],
                    g.get("related_doc", ""), g["owner"], g.get("blocking", "否"), "☐"],
            fills={2: PRI_FILL.get(g["priority"], GRAYBG)}, height=52)
        for col in (1, 2, 6, 8, 9):
            ws.cell(row=r, column=col).alignment = CENTER
        r += 1
    last = r - 1
    dv = DataValidation(type="list", formula1='"☐,☑"', allow_blank=False, showDropDown=False)
    ws.add_data_validation(dv)
    dv.add(f"I{first}:I{last}")
    ws.conditional_formatting.add(f"I{first}:I{last}",
        FormulaRule(formula=[f'$I{first}="☑"'], fill=PatternFill("solid", fgColor=OKBG),
                    font=Font(name="微软雅黑", size=10, bold=True, color=OK)))
    ws.conditional_formatting.add(f"A{first}:H{last}",
        FormulaRule(formula=[f'$I{first}="☑"'], font=Font(name="微软雅黑", size=10, color="FF85908F", strike=True)))
    r += 1
    ws.cell(row=r, column=3, value="进度统计（公式）").font = F_H2
    r += 1
    stat = [("P0 总数", f'=COUNTIF($B${first}:$B${last},"P0")'),
            ("P0 已完成", f'=COUNTIFS($B${first}:$B${last},"P0",$I${first}:$I${last},"☑")'),
            ("全部总数", f"=COUNTA($A${first}:$A${last})"),
            ("全部已完成", f'=COUNTIF($I${first}:$I${last},"☑")'),
            ("完成率", f'=TEXT(IFERROR(COUNTIF($I${first}:$I${last},"☑")/COUNTA($A${first}:$A${last}),0),"0.0%")')]
    for k, v in stat:
        ws.cell(row=r, column=3, value=k).font = F_SMALL
        c = ws.cell(row=r, column=4, value=v)
        c.font = Font(name="微软雅黑", size=10, bold=True, color=INK)
        c.alignment = CENTER
        c.border = BOX
        r += 1


def sh_actors(wb, d):
    ws = wb.create_sheet("07 责任主体")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "07 · 责任主体与资料义务", "同一份资料由谁出、谁核对、谁留存，必须在签约前落纸，否则查验时互相推诿。", 5)
    r = 5
    header(ws, r, ["责任主体", "序号", "资料/动作义务", "说明", "关联单证"], [22, 7, 76, 56, 20])
    r += 1
    for a in d["responsibilities"]:
        related = [x["id"] for x in d["documents"] if R.norm_actor(x["owner"]) == R.norm_actor(a["actor"])]
        s = r
        for i, it in enumerate(a["items"], start=1):
            put(ws, r, [a["actor"] if i == 1 else "", i, it, a.get("notes", "") if i == 1 else "",
                        ", ".join(related) if i == 1 else ""])
            ws.cell(row=r, column=2).alignment = CENTER
            r += 1
        ws.merge_cells(start_row=s, start_column=1, end_row=r - 1, end_column=1)
        ws.merge_cells(start_row=s, start_column=4, end_row=r - 1, end_column=4)
        ws.merge_cells(start_row=s, start_column=5, end_row=r - 1, end_column=5)
        c = ws.cell(row=s, column=1)
        c.font = Font(name="微软雅黑", size=11, bold=True, color=INK)
        c.alignment = Alignment(vertical="center", wrap_text=True, horizontal="center")
        c.fill = PatternFill("solid", fgColor=PAPER)


def sh_confirm(wb, d):
    ws = wb.create_sheet("08 待确认事项")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "08 · 待确认事项", "这些问题不能由公开资料可靠回答。必须取得书面答复并归档；口头沟通不构成依据。", 9)
    r = 5
    header(ws, r, ["编号", "优先级", "事项", "为什么不能自判", "谁确认", "怎么核实",
                   "判断错的代价", "已确认", "答复要点"], [7, 9, 40, 56, 18, 44, 40, 9, 40])
    r += 1
    first = r
    sev = {"高": BADBG, "中": WARNBG, "低": INFOBG}
    for q in d["to_confirm"]:
        put(ws, r, [q["id"], q["severity"], q["topic"], q["why"], q["who"], q["how"],
                    q["impact_if_wrong"], "☐", ""],
            fills={2: sev.get(q["severity"], GRAYBG)}, height=56)
        for col in (1, 2, 8):
            ws.cell(row=r, column=col).alignment = CENTER
        r += 1
    last = r - 1
    dv = DataValidation(type="list", formula1='"☐,☑"', allow_blank=False, showDropDown=False)
    ws.add_data_validation(dv)
    dv.add(f"H{first}:H{last}")
    ws.conditional_formatting.add(f"H{first}:H{last}",
        FormulaRule(formula=[f'$H{first}="☑"'], fill=PatternFill("solid", fgColor=OKBG)))
    r += 1
    ws.cell(row=r, column=1, value="闭环统计").font = F_H2
    r += 1
    ws.cell(row=r, column=3, value="已闭环 / 总数").font = F_SMALL
    c = ws.cell(row=r, column=4, value=f'=COUNTIF($H${first}:$H${last},"☑")&" / "&COUNTA($A${first}:$A${last})')
    c.font = Font(name="微软雅黑", size=11, bold=True, color=INK)
    c.alignment = CENTER
    c.border = BOX
    ws.cell(row=r, column=5, value="高优先级未闭环").font = F_SMALL
    c2 = ws.cell(row=r, column=6,
                 value=f'=COUNTIFS($B${first}:$B${last},"高",$H${first}:$H${last},"☐")')
    c2.font = Font(name="微软雅黑", size=11, bold=True, color=BAD)
    c2.alignment = CENTER
    c2.border = BOX
    return dict(first=first, last=last, stat_row=r)


def sh_danger(wb, d):
    ws = wb.create_sheet("09 危险属性对照")
    ws.sheet_view.showGridLines = False
    dd = d["danger_distinction"]
    sheet_title(ws, "09 · 危险化学品 vs 危险货物（两套体系分开判）", dd["lead"], 5)
    r = 5
    ws.cell(row=r, column=1, value="一、两套分类对照").font = F_H2
    r += 1
    header(ws, r, ["维度", "危险化学品（中国安全生产监管）", "危险货物（运输）"], [26, 62, 62])
    r += 1
    ch, gd = dd["chemical"], dd["goods"]
    pairs = [
        ("监管体系", ch["regime"], gd["regime"]),
        ("本单适用性", R.VERDICT_TEXT.get(ch.get("applicable"), ch.get("applicable")),
         R.VERDICT_TEXT.get(gd.get("applicable"), gd.get("applicable"))),
        ("条目 / 编号", ch["entry"], f"{gd['un']} · {gd['cls']} · 次要危险 {gd.get('subsidiary', '')} · PG {gd['pg']}"),
        ("正确运输名称", "—", gd["proper_shipping_name"]),
        ("阈值", ch["threshold"], gd["threshold"]),
        ("后果", ch["consequence"], gd["consequence"]),
    ]
    for k, a, b in pairs:
        put(ws, r, [k, a, b], height=54)
        ws.cell(row=r, column=1).font = Font(name="微软雅黑", size=10, bold=True, color=INK)
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="二、浓度/形态 → 双轨结论矩阵").font = F_H2
    r += 1
    header(ws, r, ["浓度 / 形态", "危险化学品（目录）", "危险货物（运输）", "要点", ""], [34, 46, 42, 56, 2])
    r += 1
    for m in dd["matrix"]:
        if m is dd["matrix"][0] and "8%" in m["case"]:
            pass
        put(ws, r, [m["case"], m["chem"], m["goods"], m["note"]], height=48)
        ws.cell(row=r, column=1).font = Font(name="微软雅黑", size=10, bold=True, color=INK)
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="三、常见混淆（务必避免）").font = F_H2
    r += 1
    for x in dd["common_errors"]:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        c = ws.cell(row=r, column=1, value="✕  " + x)
        c.font = F_BODY
        c.alignment = WRAP
        c.border = BOX
        c.fill = PatternFill("solid", fgColor=BADBG)
        ws.row_dimensions[r].height = 30
        r += 1
    r += 1

    t = d["transport"]
    ws.cell(row=r, column=1, value="四、运输参数").font = F_H2
    r += 1
    for k, v in [("运输方式", t["mode"]), ("国际规则", t["regime_standard"]), ("国内国标", t["domestic_standard"]),
                 ("UN 编号", t["un"]), ("正确运输名称", t["proper_shipping_name_en"]), ("类别", t["class"]),
                 ("次要危险", t["subsidiary_risk"]), ("包装类别", t["packing_group"]),
                 ("类项标志", "、".join(t["labels"])), ("包装指令", t["packing_instruction"]),
                 ("EmS", t["emS"]),
                 ("隔离要求", "\n".join("• " + x for x in t["segregation"])),
                 ("积载要求", "\n".join("• " + x for x in t["stowage"])),
                 ("补充说明", "\n".join("• " + x for x in t["notes"]))]:
        ws.cell(row=r, column=1, value=k).font = F_SMALL
        ws.cell(row=r, column=1).border = BOX
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        c = ws.cell(row=r, column=2, value=v)
        c.font = F_MONO if k in ("UN 编号", "正确运输名称", "EmS") else F_BODY
        c.alignment = WRAP
        c.border = BOX
        ws.row_dimensions[r].height = max(20, 13 * (str(v).count("\n") + len(str(v)) // 96 + 1))
        r += 1
    r += 1

    lp = d["labels_packaging"]
    g = lp["ghs_label"]
    ws.cell(row=r, column=1, value="五、中文危险公示标签（GB 15258 / GB 30000）").font = F_H2
    r += 1
    for k, v in [("是否强制", g["required"]), ("语言", g["lang"]), ("依据标准", g["std"]),
                 ("象形图", "、".join(g["pictograms"])), ("信号词", g["signal_word"]),
                 ("危险性说明（H）", "\n".join("• " + x for x in g["h_statements"])),
                 ("防范说明（P）", "\n".join("• " + x for x in g["p_statements"])),
                 ("必备要素", "\n".join("• " + x for x in g["elements"])),
                 ("注意事项", g.get("note", ""))]:
        ws.cell(row=r, column=1, value=k).font = F_SMALL
        ws.cell(row=r, column=1).border = BOX
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        c = ws.cell(row=r, column=2, value=v)
        c.font = F_BODY
        c.alignment = WRAP
        c.border = BOX
        ws.row_dimensions[r].height = max(20, 13 * (str(v).count("\n") + len(str(v)) // 96 + 1))
        r += 1


def sh_tax(wb, d):
    ws = wb.create_sheet("10 税费测算")
    ws.sheet_view.showGridLines = False
    tr = d["tax_rates"]
    calc = d["calculation"]
    sheet_title(ws, f"10 · 进口税费测算（{tr['tariff_year']} 年税则）", "黄色底为可修改输入项，税额与合计为实时公式。汇率须替换为海关计征日实际汇率。", 6)
    r = 5
    ws.cell(row=r, column=1, value="一、税率").font = F_H2
    r += 1
    header(ws, r, ["项目", "税率", "说明", "", ""], [22, 14, 92, 2, 2])
    r += 1
    for k, v, note in [("税则号列", tr["hs"], "按归类结论"),
                       ("最惠国税率", tr["mfn"]["rate"], tr["mfn"]["note"]),
                       ("暂定税率", tr["provisional"]["rate"], tr["provisional"]["note"]),
                       ("普通税率", tr["general"]["rate"], tr["general"]["note"]),
                       ("进口环节增值税", tr["vat"]["rate"], tr["vat"]["note"]),
                       ("消费税", tr["consumption_tax"]["rate"], tr["consumption_tax"]["note"])]:
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
        put(ws, r, [k, v, note], height=32, mono_cols=(2,))
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="二、优惠税率（状态须核实）").font = F_H2
    r += 1
    header(ws, r, ["优惠安排", "页面显示税率", "状态", "适用条件", ""], [34, 16, 16, 78, 2])
    r += 1
    stmap = {"disputed": ("数据冲突·待核实", BADBG), "pending": ("待核验", WARNBG),
             "claimed": ("仅供应商声称", WARNBG), "verified": ("已核实", OKBG)}
    for f in tr["fta"]:
        txt, fill = stmap.get(f.get("status"), (f.get("status"), GRAYBG))
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
        put(ws, r, [f["scheme"], f["rate_hint"], txt, f["condition"]], fills={3: fill}, height=52)
        ws.cell(row=r, column=3).alignment = CENTER
        r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws.cell(row=r, column=1, value="⚠ " + tr["fta_note"])
    c.font = F_BODY
    c.alignment = WRAP
    c.fill = PatternFill("solid", fgColor=WARNBG)
    c.border = BOX
    ws.row_dimensions[r].height = 76
    r += 2

    ws.cell(row=r, column=1, value="三、税额试算（黄色为输入）").font = F_H2
    r += 1
    header(ws, r, ["项目", "数值", "单位", "公式说明", ""], [26, 20, 10, 84, 2])
    r += 1
    Y = PatternFill("solid", fgColor="FFFFF3CE")
    base = r
    rows = [
        ("CIF 金额（USD）", calc.get("cif_usd"), "USD", "货值 + 运费 + 保险费", True),
        ("汇率（USD/CNY）", calc.get("fx"), "CNY", "以海关计征日汇率为准", True),
        ("CIF 金额（CNY）", None, "CNY", "= USD × 汇率", False),
        ("关税税率", float(str(calc["duty_rate"]).rstrip("%")) / 100, "%", "默认取最惠国；若有证书改协定税率", True),
        ("关税额（CNY）", None, "CNY", "= CIF(CNY) × 关税税率", False),
        ("消费税（CNY）", 0, "CNY", "本商品不属应税消费品", True),
        ("增值税计税价格（CNY）", None, "CNY", "= CIF + 关税 + 消费税", False),
        ("增值税率", float(str(calc["vat_rate"]).rstrip("%")) / 100, "%", "标准税率", True),
        ("增值税额（CNY）", None, "CNY", "= 计税价格 × 增值税率", False),
        ("税费合计（CNY）", None, "CNY", "= 关税 + 消费税 + 增值税", False),
    ]
    idx = {}
    for i, (k, v, unit, note, editable) in enumerate(rows):
        rr = base + i
        idx[k] = rr
        c1 = ws.cell(row=rr, column=1, value=k)
        c1.font = Font(name="微软雅黑", size=10, bold=(not editable), color=INK if not editable else INK2)
        c1.border = BOX
        c1.alignment = Alignment(vertical="center")
        c2 = ws.cell(row=rr, column=2)
        if v is not None:
            c2.value = v
        c2.border = BOX
        c2.alignment = Alignment(horizontal="right", vertical="center")
        c2.font = Font(name="Consolas", size=10, bold=True, color=INK)
        if editable:
            c2.fill = Y
        if unit == "%":
            c2.number_format = "0.00%"
        else:
            c2.number_format = "#,##0.00"
        c3 = ws.cell(row=rr, column=3, value=unit)
        c3.font = F_SMALL
        c3.border = BOX
        c3.alignment = CENTER
        ws.merge_cells(start_row=rr, start_column=4, end_row=rr, end_column=5)
        c4 = ws.cell(row=rr, column=4, value=note)
        c4.font = F_SMALL
        c4.border = BOX
        c4.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[rr].height = 20

    ws.cell(row=idx["CIF 金额（CNY）"], column=2,
            value=f"=B{idx['CIF 金额（USD）']}*B{idx['汇率（USD/CNY）']}").number_format = "#,##0.00"
    ws.cell(row=idx["关税额（CNY）"], column=2,
            value=f"=B{idx['CIF 金额（CNY）']}*B{idx['关税税率']}").number_format = "#,##0.00"
    ws.cell(row=idx["增值税计税价格（CNY）"], column=2,
            value=f"=B{idx['CIF 金额（CNY）']}+B{idx['关税额（CNY）']}+B{idx['消费税（CNY）']}").number_format = "#,##0.00"
    ws.cell(row=idx["增值税额（CNY）"], column=2,
            value=f"=B{idx['增值税计税价格（CNY）']}*B{idx['增值税率']}").number_format = "#,##0.00"
    tot = ws.cell(row=idx["税费合计（CNY）"], column=2,
                  value=f"=B{idx['关税额（CNY）']}+B{idx['消费税（CNY）']}+B{idx['增值税额（CNY）']}")
    tot.font = Font(name="Consolas", size=12, bold=True, color=BAD)
    tot.fill = PatternFill("solid", fgColor=BADBG)

    r = base + len(rows) + 2
    ws.cell(row=r, column=1, value="四、情景对比（改 CIF 或税率即自动更新）").font = F_H2
    r += 1
    header(ws, r, ["情景", "关税率", "关税（CNY）", "增值税（CNY）", "税费合计（CNY）"], [30, 12, 18, 18, 18])
    r += 1
    first = r
    scen = [("最惠国 5.5%（无证书）", 0.055),
            ("中韩FTA 1.1%（待核实）", 0.011),
            ("零关税（若成立）", 0.0),
            ("普通税率 30%（最坏情形）", 0.30)]
    for name, rate in scen:
        ws.cell(row=r, column=1, value=name).font = F_BODY
        ws.cell(row=r, column=1).border = BOX
        c = ws.cell(row=r, column=2, value=rate)
        c.number_format = "0.00%"
        c.fill = Y
        c.border = BOX
        c.font = F_MONO
        ws.cell(row=r, column=3, value=f"=$B${idx['CIF 金额（CNY）']}*B{r}").number_format = "#,##0.00"
        ws.cell(row=r, column=4,
                value=f"=($B${idx['CIF 金额（CNY）']}+C{r})*$B${idx['增值税率']}").number_format = "#,##0.00"
        ws.cell(row=r, column=5, value=f"=C{r}+D{r}").number_format = "#,##0.00"
        for col in (3, 4, 5):
            cc = ws.cell(row=r, column=col)
            cc.font = Font(name="Consolas", size=10, color=INK2)
            cc.border = BOX
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c = ws.cell(row=r, column=1, value="说明：" + calc.get("note", "") + " " + tr.get("calc_note", ""))
    c.font = F_SMALL
    c.alignment = WRAP
    c.fill = PatternFill("solid", fgColor=GRAYBG)
    c.border = BOX
    ws.row_dimensions[r].height = 62


def sh_dashboard(wb, d, grade, meta=None):
    meta = meta or {}
    ws = wb.create_sheet("11 进度看板", 0)
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDEFGH", [3, 30, 16, 16, 4, 30, 16, 16]):
        ws.column_dimensions[col].width = w
    ws.merge_cells("B2:H2")
    c = ws.cell(row=2, column=2, value="进口资料进度看板")
    c.font = Font(name="微软雅黑", size=18, bold=True, color=INK)
    ws.row_dimensions[2].height = 30
    ws.merge_cells("B3:H3")
    c = ws.cell(row=3, column=2, value=f"{d['meta']['record_id']} · 基准日 {d['as_of']} · {d['inputs']['product_name_cn']} {d['inputs']['concentration']} · {d['inputs']['origin_country']} → 中国")
    c.font = F_SMALL

    r = 5
    ws.cell(row=r, column=2, value="一、关键指标").font = F_H2
    r += 1
    kpis = [("总体结论", f"{grade['grade']} · {grade['grade_text']}"),
            ("单证完备度", f"='04 单证要求'!C{0 or ''}")]
    # 直接写公式引用（表名含空格需引号）
    doc_last = 5 + len(d["documents"])
    gap_first = 6
    gap_last = gap_first + len(d["gaps"]) - 1
    items = [
        ("总体评级", f'{grade["grade"]} · {grade["grade_text"]}', OKBG),
        ("单证完备度（齐备/必须）", f"=COUNTIF('04 单证要求'!$F$6:$F${doc_last},\"齐备\")&\" / \"&COUNTIF('04 单证要求'!$E$6:$E${doc_last},\"必须\")", INFOBG),
        ("P0 缺口", f'=COUNTIF(\'06 缺失资料\'!$B${gap_first}:$B${gap_last},"P0")', BADBG),
        ("P0 已完成", f'=COUNTIFS(\'06 缺失资料\'!$B${gap_first}:$B${gap_last},"P0",\'06 缺失资料\'!$I${gap_first}:$I${gap_last},"☑")', OKBG),
        ("缺口完成率", f'=TEXT(IFERROR(COUNTIF(\'06 缺失资料\'!$I${gap_first}:$I${gap_last},"☑")/COUNTA(\'06 缺失资料\'!$A${gap_first}:$A${gap_last}),0),"0.0%")', INFOBG),
        ("待确认事项", f"='08 待确认事项'!D{meta.get('confirm_stat_row', 6 + len(d['to_confirm']) + 2)}", WARNBG),
        ("高优先级未闭环", f"='08 待确认事项'!F{meta.get('confirm_stat_row', 6 + len(d['to_confirm']) + 2)}", BADBG),
        ("监管事项总数", f"=COUNTA('03 法规依据'!$A$6:$A${5 + len(d['regulation_checklist'])})", GRAYBG),
    ]
    for k, v, fill in items:
        c1 = ws.cell(row=r, column=2, value=k)
        c1.font = F_SMALL
        c1.border = BOX
        c1.fill = PatternFill("solid", fgColor=PAPER)
        c2 = ws.cell(row=r, column=3, value=v)
        c2.font = Font(name="微软雅黑", size=13, bold=True, color=INK)
        c2.alignment = Alignment(horizontal="center", vertical="center")
        c2.border = BOX
        c2.fill = PatternFill("solid", fgColor=fill)
        ws.row_dimensions[r].height = 24
        r += 1
    r += 1

    ws.cell(row=r, column=2, value="二、单证状态分布").font = F_H2
    r += 1
    for s in R.DOC_STATUS:
        c1 = ws.cell(row=r, column=2, value=R.DOC_STATUS_TEXT[s])
        c1.font = F_SMALL
        c1.border = BOX
        c1.fill = PatternFill("solid", fgColor=STATUS_FILL.get(s, GRAYBG))
        c2 = ws.cell(row=r, column=3, value=f'=COUNTIF(\'04 单证要求\'!$F$6:$F${doc_last},"{R.DOC_STATUS_TEXT[s]}")')
        c2.font = Font(name="微软雅黑", size=11, bold=True, color=INK)
        c2.alignment = CENTER
        c2.border = BOX
        r += 1
    r += 1

    ws.cell(row=r, column=2, value="三、放行闸门").font = F_H2
    r += 1
    for g in grade["gates"]:
        fill = {"pass": OKBG, "fail": BADBG, "pending": WARNBG}[g["status"]]
        c1 = ws.cell(row=r, column=2, value=f"{g['code']} {g['name']}")
        c1.font = Font(name="微软雅黑", size=10, bold=True, color=INK)
        c1.border = BOX
        c2 = ws.cell(row=r, column=3, value={"pass": "通过", "fail": "未通过", "pending": "待确认"}[g["status"]])
        c2.font = Font(name="微软雅黑", size=10, bold=True, color=INK2)
        c2.alignment = CENTER
        c2.border = BOX
        c2.fill = PatternFill("solid", fgColor=fill)
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
        c3 = ws.cell(row=r, column=4, value=g["rule"])
        c3.font = F_SMALL
        c3.alignment = WRAP
        c3.border = BOX
        ws.row_dimensions[r].height = 30
        r += 1
    r += 1

    ws.cell(row=r, column=2, value="四、缺口按责任方分布").font = F_H2
    r += 1
    owners = sorted({g["owner"] for g in d["gaps"]})
    for o in owners:
        c1 = ws.cell(row=r, column=2, value=o)
        c1.font = F_SMALL
        c1.border = BOX
        c2 = ws.cell(row=r, column=3, value=f'=COUNTIF(\'06 缺失资料\'!$G${gap_first}:$G${gap_last},"{o}")')
        c2.font = Font(name="微软雅黑", size=11, bold=True, color=INK)
        c2.alignment = CENTER
        c2.border = BOX
        r += 1


def sh_sources(wb, d):
    ws = wb.create_sheet("12 法规来源")
    ws.sheet_view.showGridLines = False
    sheet_title(ws, "12 · 法规来源与查询日期", "每条结论都可回溯。A 级=官方一手；B 级=官方转载/政务数据库；C 级=行业平台，仅供交叉参考，不可作唯一依据。", 8)
    r = 5
    header(ws, r, ["编号", "级别", "类型", "标题", "发布机关", "日期", "效力状态", "查询日期"],
           [8, 7, 12, 60, 30, 30, 14, 13])
    r += 1
    tierfill = {"A": BADBG, "B": WARNBG, "C": GRAYBG}
    effmap = {"现行有效": OKBG, "部分替代": WARNBG, "已废止": BADBG, "未核实": GRAYBG}
    for s in d["sources"]:
        put(ws, r, [s["id"], s.get("tier", "C"), s.get("kind", ""), s["title"], s.get("publisher", ""),
                    s.get("date", ""), s.get("effective", ""), s.get("accessed", "")],
            fills={2: tierfill.get(s.get("tier"), GRAYBG), 7: effmap.get(s.get("effective"), GRAYBG)}, height=40)
        for col in (1, 2, 3, 7, 8):
            ws.cell(row=r, column=col).alignment = CENTER
        r += 1
    r += 1
    ws.cell(row=r, column=4, value="链接与支撑结论").font = F_H2
    r += 1
    header(ws, r, ["编号", "", "", "原文链接", "支撑了哪条结论", "", "", ""], [8, 7, 12, 60, 80, 4, 4, 4])
    r += 1
    for s in d["sources"]:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        ws.cell(row=r, column=1, value=s["id"]).alignment = CENTER
        ws.cell(row=r, column=1).border = BOX
        c = ws.cell(row=r, column=4, value=s["url"])
        c.font = Font(name="Consolas", size=8.5, color=INFO, underline="single")
        c.hyperlink = s["url"]
        c.alignment = WRAP
        c.border = BOX
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=8)
        c2 = ws.cell(row=r, column=5, value=s.get("supports", ""))
        c2.font = F_BODY
        c2.alignment = WRAP
        c2.border = BOX
        ws.row_dimensions[r].height = 42
        r += 1


def build(d: dict, out: str) -> str:
    grade = R.overall_grade(d)
    wb = Workbook()
    wb.remove(wb.active)
    sh_cover(wb, d, grade)
    sh_product(wb, d)
    sh_hs(wb, d)
    sh_regulation(wb, d)
    sh_docs(wb, d)
    sh_uploaded(wb, d)
    sh_gaps(wb, d)
    sh_actors(wb, d)
    confirm_meta = sh_confirm(wb, d)
    sh_danger(wb, d)
    sh_tax(wb, d)
    sh_sources(wb, d)
    sh_dashboard(wb, d, grade, confirm_meta)
    wb.active = 0
    wb.properties.title = d["title"]
    wb.properties.creator = d["meta"].get("prepared_by", "")
    wb.properties.subject = d["meta"].get("scene", "")
    wb.properties.description = d["meta"].get("demo_notice", "")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    with open(a.data, encoding="utf-8") as f:
        d = json.load(f)
    p = build(d, a.out)
    print("wrote", p)


if __name__ == "__main__":
    main()
