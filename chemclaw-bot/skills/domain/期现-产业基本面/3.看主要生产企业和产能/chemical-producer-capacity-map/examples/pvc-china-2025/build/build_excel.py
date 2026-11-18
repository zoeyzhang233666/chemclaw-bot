#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_excel.py — 企业产能分布工作簿（xlsx）
表结构（顺序固定）：
  00_封面            01_口径与样本范围     02_核心结论
  03_集团汇总        04_法人汇总           05_基地清单
  06_装置明细        07_区域汇总(省)       08_区域汇总(市)
  09_工艺路线汇总     10_产品等级汇总       11_在建拟建项目
  12_新增净额还原     13_重复统计校验       14_汇总公式与溯源
  15_口径对比(交叉)   16_数据缺口           17_来源清单
  18_企业集团关系树
所有汇总单元格使用公式引用「06_装置明细」，保证口径切换在 Excel 内同源。
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pcd_model import (  # noqa: E402
    Aggregator, BASIS_ACTUAL, BASIS_CAPACITY, BASIS_DESIGN, BASIS_EFFECTIVE,
    BASIS_LABELS, CONFIDENCE_LABELS, DupChecker, PIPELINE_WEIGHTS, PROJECT_STAGE_LABELS,
    ROUTE_LABELS, STATUS_LABELS, Dataset, concentration_label, coverage, cr_n, hhi,
)

try:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, PieChart, Reference, Series
    from openpyxl.chart.label import DataLabelList
    from openpyxl.formatting.rule import ColorScaleRule, DataBarRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:  # pragma: no cover
    Workbook = None

# ---------------- 视觉规范 ----------------
NAVY = "0F1E33"
STEEL = "1C3557"
ACCENT = "2F80C7"
ORANGE = "E8622C"
BLUE = "2BA3D8"
PURPLE = "7B5AC4"
GOLD = "C99A2E"
GREY = "5A6A7D"
LIGHT = "EAF0F7"
ZEBRA = "F6F9FC"
RED = "C0392B"
AMBER = "B7791F"
GREEN = "1E7B52"

THIN = Side(style="thin", color="C9D6E5")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FILL = PatternFill("solid", fgColor=STEEL)
HEAD_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="微软雅黑", size=10, color="1A2636")
SMALL_FONT = Font(name="微软雅黑", size=9, color="4A5A6E")
TITLE_FONT = Font(name="微软雅黑", size=16, bold=True, color="0F1E33")
SUB_FONT = Font(name="微软雅黑", size=10, color="5A6A7D")
NUM_FMT = "#,##0.0"
PCT_FMT = "0.0%"


def _sheet(wb, name, title, subtitle=""):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws.row_dimensions[1].height = 24
    if subtitle:
        ws["A2"] = subtitle
        ws["A2"].font = SUB_FONT
    return ws


def _table(ws, start_row, headers, rows, widths=None, freeze=True,
           col_formats=None, wrap_cols=()):
    r0 = start_row
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=r0, column=j, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[r0].height = 30
    for i, row in enumerate(rows, start=1):
        for j, v in enumerate(row, start=1):
            c = ws.cell(row=r0 + i, column=j, value=v)
            c.font = BODY_FONT
            c.border = BORDER
            c.alignment = Alignment(vertical="top",
                                    wrap_text=(j in wrap_cols),
                                    horizontal="right" if (col_formats and col_formats.get(j) in (NUM_FMT, PCT_FMT)) else "left")
            if col_formats and j in col_formats:
                c.number_format = col_formats[j]
            if i % 2 == 0:
                c.fill = PatternFill("solid", fgColor=ZEBRA)
    if freeze:
        ws.freeze_panes = ws.cell(row=r0 + 1, column=1)
    if widths:
        for j, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(j)].width = w
    return r0 + len(rows)


def _note(ws, row, text, color=GREY):
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name="微软雅黑", size=9, italic=True, color=color)
    return row + 1


# ===========================================================================
def build(ds: Dataset, out_path: str, checker_findings=None):
    if Workbook is None:
        raise RuntimeError("需要 openpyxl：pip install openpyxl")
    wb = Workbook()
    wb.remove(wb.active)

    basis = BASIS_DESIGN
    A = Aggregator(ds, basis=basis)
    by_group = A.by_group()
    by_entity = A.by_entity()
    by_plant = A.by_plant()
    by_prov = A.by_province()
    by_city = A.by_city()
    by_route = A.by_route()
    total = A.total()

    prod = ds.product.get("name", "产品")
    short = ds.product.get("short", prod)
    year = ds.product.get("base_year", "")
    province_scope = ds.product.get("scope", "中国大陆")

    benchmarks = ds.benchmarks or []
    bench_design = None
    for b in benchmarks:
        if b.get("basis") == BASIS_DESIGN and b.get("metric") == "全国产能":
            bench_design = b
            break
    bench_total = bench_design.get("value") if bench_design else None
    cov = coverage(total, bench_total)

    # ---------------- 00 封面 ----------------
    ws = wb.create_sheet("00_封面")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 96
    ws.merge_cells("B2:C2")
    ws["B2"] = f"{prod} 主要生产企业与产能分布"
    ws["B2"].font = Font(name="微软雅黑", size=22, bold=True, color="0F1E33")
    ws.row_dimensions[2].height = 34
    ws.merge_cells("B3:C3")
    ws["B3"] = f"企业 → 集团 → 生产基地 → 装置 → 产品 五级可追溯数据包 · 统计口径：{BASIS_LABELS[basis]} · 数据年度 {year}"
    ws["B3"].font = Font(name="微软雅黑", size=11, color="2F80C7")
    ws.merge_cells("B4:C4")
    ws["B4"] = f"地域范围：{province_scope}　|　生成日期：{ds.meta.get('generated','')}　|　数据截止：{ds.meta.get('cutoff','')}"
    ws["B4"].font = SUB_FONT

    r = 6
    info = [
        ("品种", f"{prod}（{ds.product.get('cas','')}）"),
        ("统计基期", str(year)),
        ("样本范围", ds.meta.get("sample_scope", "")),
        ("样本规模", f"{len(ds.units)} 条装置记录 / {len(ds.plants)} 个生产基地 / {len(ds.entities)} 个法人主体 / {len(ds.groups)} 个集团"),
        ("样本产能合计", f"{total:,.1f} 万吨/年（{BASIS_LABELS[basis]}）"),
        ("全国口径参考", f"{bench_total:,.0f} 万吨/年" + (f"（{bench_design.get('source_org','')}，{bench_design.get('year','')}）" if bench_design else "") if bench_total else "未取得"),
        ("样本覆盖率", f"{cov}%" if cov else "无法计算"),
        ("覆盖提醒", ds.meta.get("coverage_warning", "")),
        ("数据缺口", f"{len(ds.gaps)} 项（见 16_数据缺口）"),
        ("来源数量", f"{len(ds.sources)} 条（见 17_来源清单）"),
    ]
    for k, v in info:
        ws.cell(row=r, column=2, value=k).font = Font(name="微软雅黑", size=10, bold=True, color="4A5A6E")
        c = ws.cell(row=r, column=3, value=v)
        c.font = Font(name="微软雅黑", size=10, color="1A2636")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 30 if len(str(v)) > 80 else 18
        r += 1

    r += 1
    ws.merge_cells(f"B{r}:C{r}")
    ws[f"B{r}"] = "阅读顺序与口径纪律"
    ws[f"B{r}"].font = Font(name="微软雅黑", size=12, bold=True, color=ORANGE)
    r += 1
    guides = [
        "1) 先读 01_口径与样本范围，确认本表统计的是「设计产能」还是其他口径；不同口径严禁相加。",
        "2) 06_装置明细是唯一事实层（装置级一行）。03/04/05/07/08/09/10 的合计均由该表筛选+求和得出，可在 14_汇总公式与溯源 核对。",
        "3) 集团合计已合并其全部下属法人产能，不得再把某子公司产能与集团合计相加。",
        "4) 样本合计 ≠ 全国产能；覆盖率见封面与 01 表，样本外企业未计入。",
        "5) 11_在建拟建项目是「增量」，不得与存量相加；置换退出产能已在 12_新增净额还原 中扣减。",
        "6) 13_重复统计校验 列出全部自动校验结果；ERROR 项必须在引用前处理。",
        "7) 所有产能记录附来源编号与可信等级（A/B/C/D），D 级不得单独作为结论依据。",
    ]
    for g in guides:
        ws.merge_cells(f"B{r}:C{r}")
        c = ws.cell(row=r, column=2, value=g)
        c.font = Font(name="微软雅黑", size=10, color="1A2636")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 30
        r += 1

    # ---------------- 01 口径与样本范围 ----------------
    ws = _sheet(wb, "01_口径与样本范围", "统计口径、样本范围与使用边界",
                "同一指标多套公开口径并列展示，不取平均；样本合计不等于全国总产能")
    headers = ["编号", "口径/口径项", "定义", "数值/说明", "单位", "数据年份", "来源编号", "可信度", "备注"]
    rows = [
        ["B01", "本表主口径", "所有汇总（03-10 表）默认使用的产能口径", "设计产能（铭牌/名义）", "万吨/年", year, "", "A",
         "与各公司年报「设计产能/产能」栏目口径一致"],
        ["B02", "有效产能口径", "扣除长期停产、限产、检修后的可用能力", "仅部分基地可得，见 06 表 basis 字段", "万吨/年", year, "", "B",
         "未取得行业统一口径，故不做有效产能全口径合计"],
        ["B03", "实际产量口径", "年度实际产出，用于计算开工率", "见 15_口径对比", "万吨/年", year, "", "A",
         "产量≠产能，禁止混用"],
    ]
    for b in benchmarks:
        rows.append([b.get("id", ""), b.get("metric", ""), b.get("definition", ""),
                     b.get("value"), b.get("unit", "万吨/年"), b.get("year", ""),
                     b.get("source_id", ""), b.get("confidence", "B"),
                     b.get("note", "")])
    last = _table(ws, 4, headers, rows,
                  widths=[8, 20, 44, 16, 10, 10, 12, 8, 52],
                  col_formats={4: "#,##0.0"}, wrap_cols=(3, 9))
    r = last + 2
    ws.cell(row=r, column=1, value="口径判定规则（行业统计口径是否包含联产/副产/长期停车/不同等级）").font = Font(name="微软雅黑", size=11, bold=True, color=ORANGE)
    r += 1
    rules = ds.notes.get("basis_rules", [])
    if not rules:
        rules = ["（未配置口径规则，请在 data bundle 的 notes.basis_rules 中补充）"]
    for t in rules:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
        c = ws.cell(row=r, column=1, value="• " + t)
        c.font = Font(name="微软雅黑", size=10, color="1A2636")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = max(16, 15 * (len(t) // 90 + 1))
        r += 1

    # ---------------- 02 核心结论 ----------------
    ws = _sheet(wb, "02_核心结论", "核心结论与数据摘要", "结论均由下方明细表计算，不含估算值")
    r = 4
    ws.cell(row=r, column=1, value="一、规模与集中度").font = Font(name="微软雅黑", size=11, bold=True, color=ORANGE)
    r += 1
    conc = [
        ("样本产能合计", f"{total:,.1f} 万吨/年", BASIS_LABELS[basis]),
        ("样本企业（法人）数", str(len(by_entity)), "个"),
        ("样本集团数", str(len([g for g in by_group if g != "__ungrouped__"])), "个"),
        ("样本基地数", str(len(by_plant)), "个"),
        ("全国总产能（参考）", f"{bench_total:,.0f}" if bench_total else "未取得", "万吨/年"),
        ("样本覆盖率", f"{cov}%" if cov else "无法计算", "样本合计/全国口径"),
        ("CR1（样本口径）", f"{cr_n(by_group.values(),1)}%", "最大集团份额"),
        ("CR3（样本口径）", f"{cr_n(by_group.values(),3)}%", ""),
        ("CR5（样本口径）", f"{cr_n(by_group.values(),5)}%", ""),
        ("CR10（样本口径）", f"{cr_n(by_group.values(),10)}%", ""),
        ("HHI（样本口径）", f"{hhi(by_group.values())}", concentration_label(hhi(by_group.values()))),
        ("CR5（法人口径）", f"{cr_n(by_entity.values(),5)}%", "以单一法人为单位"),
        ("HHI（法人口径）", f"{hhi(by_entity.values())}", concentration_label(hhi(by_entity.values()))),
    ]
    for k, v, n in conc:
        ws.cell(row=r, column=1, value=k).font = Font(name="微软雅黑", size=10, bold=True, color="4A5A6E")
        ws.cell(row=r, column=2, value=v).font = Font(name="微软雅黑", size=10, color="1A2636")
        ws.cell(row=r, column=3, value=n).font = SMALL_FONT
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="二、前十大集团").font = Font(name="微软雅黑", size=11, bold=True, color=ORANGE)
    r += 1
    top_groups = sorted([(k, v) for k, v in by_group.items() if k != "__ungrouped__"], key=lambda x: -x[1])[:10]
    gheaders = ["排名", "集团", "样本产能(万吨/年)", "占样本比", "折全国份额(参考)", "主要省份/区域"]
    wsr = r
    for j, h in enumerate(gheaders, start=1):
        c = ws.cell(row=wsr, column=j, value=h)
        c.fill = HEAD_FILL; c.font = HEAD_FONT; c.border = BORDER
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    for i, (gid, v) in enumerate(top_groups, start=1):
        g = ds.groups.get(gid)
        provs = sorted({ds.plants[p].province for e in ds.entities_of_group(gid)
                        for p in by_plant if ds.plants[p].entity_id == e.entity_id})
        vals = [i, g.short_name if g else gid, round(v, 1),
                v / total if total else None,
                (v / bench_total) if bench_total else None, "、".join(provs)]
        for j, val in enumerate(vals, start=1):
            c = ws.cell(row=wsr + i, column=j, value=val)
            c.font = BODY_FONT; c.border = BORDER
            if j == 3: c.number_format = NUM_FMT
            if j in (4, 5): c.number_format = PCT_FMT
    r = wsr + len(top_groups) + 2
    ws.cell(row=r, column=1, value="三、区域结构（省份 Top10）").font = Font(name="微软雅黑", size=11, bold=True, color=ORANGE)
    r += 1
    for j, h in enumerate(["排名", "省份", "样本产能(万吨/年)", "占样本比"], start=1):
        c = ws.cell(row=r, column=j, value=h); c.fill = HEAD_FILL; c.font = HEAD_FONT; c.border = BORDER
        c.alignment = Alignment(horizontal="center")
    for i, (pv, v) in enumerate(sorted(by_prov.items(), key=lambda x: -x[1])[:10], start=1):
        for j, val in enumerate([i, pv, round(v, 1), v / total if total else None], start=1):
            c = ws.cell(row=r + i, column=j, value=val); c.font = BODY_FONT; c.border = BORDER
            if j == 3: c.number_format = NUM_FMT
            if j == 4: c.number_format = PCT_FMT
    r += 12
    ws.cell(row=r, column=1, value="四、工艺结构").font = Font(name="微软雅黑", size=11, bold=True, color=ORANGE)
    r += 1
    for j, h in enumerate(["工艺路线", "样本产能(万吨/年)", "占样本比"], start=1):
        c = ws.cell(row=r, column=j, value=h); c.fill = HEAD_FILL; c.font = HEAD_FONT; c.border = BORDER
        c.alignment = Alignment(horizontal="center")
    for i, (k, v) in enumerate(sorted(by_route.items(), key=lambda x: -x[1]), start=1):
        for j, val in enumerate([ROUTE_LABELS.get(k, k), round(v, 1), v / total if total else None], start=1):
            c = ws.cell(row=r + i, column=j, value=val); c.font = BODY_FONT; c.border = BORDER
            if j == 2: c.number_format = NUM_FMT
            if j == 3: c.number_format = PCT_FMT
    for w, col in zip([8, 46, 20, 12, 18, 30], "ABCDEF"):
        ws.column_dimensions[col].width = w

    # ---------------- 03 集团汇总 ----------------
    ws = _sheet(wb, "03_集团汇总", f"集团级产能汇总（{BASIS_LABELS[basis]}）",
                "集团合计 = 其下全部法人全部基地全部装置之和；不得与子公司产能再相加")
    rows = []
    for gid, v in sorted(by_group.items(), key=lambda x: -x[1]):
        g = ds.groups.get(gid)
        if not g:
            rows.append(["—", "未归属集团", "", "", round(v, 1), "", "", "", 0, "", ""])
            continue
        ents = ds.entities_of_group(gid)
        plants = [p for e in ents for p in ds.plants_of_entity(e.entity_id)]
        provs = sorted({p.province for p in plants})
        routes: Dict[str, float] = {}
        for u in A.rows():
            p = ds.plants.get(u.plant_id)
            if p and p.entity_id in {e.entity_id for e in ents}:
                routes[u.route] = routes.get(u.route, 0) + (u.capacity or 0)
        route_txt = " / ".join(f"{ROUTE_LABELS.get(k,k)} {vv:.0f}" for k, vv in sorted(routes.items(), key=lambda x: -x[1]))
        rows.append([g.group_id, g.short_name, g.name, g.ultimate_controller + (f"（{g.group_type}）" if g.group_type else ""),
                     round(v, 1), len(ents), len(plants), "、".join(provs), None, route_txt, g.source_id])
    last = _table(ws, 4, ["集团ID", "集团简称", "集团全称", "实际控制人/性质", f"产能合计(万吨/年)",
                          "法人数", "基地数", "覆盖省份", "占样本比", "工艺构成(万吨)", "来源"],
                  rows, widths=[12, 22, 46, 30, 14, 8, 8, 34, 10, 40, 12],
                  col_formats={5: NUM_FMT, 9: PCT_FMT})
    # 用公式算占比，保证与合计同源
    tot_row = last + 2
    ws.cell(row=tot_row, column=2, value="样本合计").font = Font(name="微软雅黑", size=10, bold=True)
    ws.cell(row=tot_row, column=5, value=f"=SUM(E5:E{last})").number_format = NUM_FMT
    ws.cell(row=tot_row, column=5).font = Font(name="微软雅黑", size=10, bold=True)
    for i in range(5, last + 1):
        c = ws.cell(row=i, column=9)
        c.value = f"=IF($E${tot_row}=0,\"\",E{i}/$E${tot_row})"
        c.number_format = PCT_FMT
    r = tot_row + 2
    _note(ws, r, "说明：集团简称仅用于本报告可读性，法定主体见 04_法人汇总；同一集团内不同法人不得重复计入集团合计。")
    _note(ws, r + 1, "「占样本比」的分母是样本产能合计，不是全国产能；折全国份额请用 02 表的参考值自行换算并注明假设。")

    # ---------------- 04 法人汇总 ----------------
    ws = _sheet(wb, "04_法人汇总", f"法人（企业主体）级产能汇总（{BASIS_LABELS[basis]}）",
                "一个法人一行：法定全称、所属集团、统一社会信用代码、核验依据")
    rows = []
    for eid, v in sorted(by_entity.items(), key=lambda x: -x[1]):
        e = ds.entities.get(eid)
        if not e:
            continue
        g = ds.groups.get(e.group_id)
        plants = ds.plants_of_entity(eid)
        routes: Dict[str, float] = {}
        for u in A.rows():
            if ds.plants.get(u.plant_id) and ds.plants[u.plant_id].entity_id == eid:
                routes[u.route] = routes.get(u.route, 0) + (u.capacity or 0)
        rows.append([e.entity_id, e.name, e.short_name, g.short_name if g else "", e.stock_code,
                     e.ownership, e.unified_code, e.registered_address, round(v, 1),
                     len(plants), "、".join(f"{ROUTE_LABELS.get(k,k)}" for k in routes),
                     e.verified_by, e.source_id])
    last = _table(ws, 4, ["法人ID", "法定主体全称", "简称", "所属集团", "证券代码", "企业性质",
                          "统一社会信用代码", "注册地址", f"产能合计(万吨/年)", "基地数", "工艺",
                          "主体核验依据", "来源"],
                  rows, widths=[11, 46, 20, 18, 10, 10, 22, 40, 14, 8, 20, 34, 10],
                  col_formats={9: NUM_FMT})
    r = last + 2
    _note(ws, r, "法定主体全称以年报释义表/工商登记为准；简称不等于法定名称，不可直接用于合同或诉讼。")

    # ---------------- 05 基地清单 ----------------
    ws = _sheet(wb, "05_基地清单", "生产基地清单（Plant-level）",
                "一个厂区一行；集团→法人→基地→装置的四级归属在此显式列出")
    rows = []
    for p in sorted(ds.plants.values(), key=lambda x: -by_plant.get(x.plant_id, 0)):
        e = ds.entities.get(p.entity_id)
        g = ds.groups.get(e.group_id) if e else None
        us = [u for u in A.rows() if u.plant_id == p.plant_id]
        routes = sorted({ROUTE_LABELS.get(u.route, u.route) for u in ds.units_of_plant(p.plant_id)})
        rows.append([p.plant_id, p.name, p.name_full, p.province, p.city, p.district, p.park,
                     e.name if e else "", g.short_name if g else "", round(by_plant.get(p.plant_id, 0), 1),
                     len(us), " / ".join(routes), p.registered_address,
                     f"{p.lat:.4f},{p.lon:.4f}" if p.lat else "", p.coord_precision])
    last = _table(ws, 4, ["基地ID", "基地简称", "基地全称", "省", "市", "区县", "园区/位置",
                          "运营法人", "所属集团", f"产能(万吨/年)", "装置数", "工艺", "注册地址", "经纬度", "坐标精度"],
                  rows, widths=[11, 34, 40, 16, 12, 12, 28, 36, 16, 14, 8, 22, 40, 18, 10],
                  col_formats={10: NUM_FMT})
    r = last + 2
    _note(ws, r, "坐标精度 plant=厂址级、city=城市级、province=省中心（仅示意）；地图气泡面积对应产能，不代表厂区范围。")

    # ---------------- 06 装置明细（唯一事实层） ----------------
    ws = _sheet(wb, "06_装置明细", "装置级明细（唯一事实层 / Head of Truth）",
                "一行 = 一个装置的一条产能事实；全部汇总表均引用本表")
    rows = []
    for u in sorted(ds.units, key=lambda x: (x.plant_id, x.product, x.basis)):
        p = ds.plants.get(u.plant_id)
        e = ds.entities.get(p.entity_id) if p else None
        g = ds.groups.get(e.group_id) if e else None
        s = ds.sources.get(u.source_id)
        rows.append([u.uid, p.province if p else "", p.city if p else "", p.name if p else "",
                     e.name if e else "", g.short_name if g else "",
                     u.product, u.grade_class, ROUTE_LABELS.get(u.route, u.route), u.route_note,
                     BASIS_LABELS.get(u.basis, u.basis), u.capacity, u.capacity_note, u.capacity_year,
                     u.start_year, STATUS_LABELS.get(u.status, u.status), u.status_note,
                     ("是" if u.integrated_calcium_carbide else "否") if u.integrated_calcium_carbide is not None else "未知",
                     u.source_id, s.confidence if s else u.confidence,
                     s.title if s else "", s.url if s else "", s.date if s else ""])
    headers = ["装置ID", "省", "市", "基地", "运营法人", "集团", "产品/牌号", "产品等级", "工艺路线", "工艺备注",
               "产能口径", "产能(万吨/年)", "原文表述", "数据年份", "投产年份", "运行状态", "状态说明",
               "配套自产电石", "来源编号", "可信度", "来源标题", "来源URL", "来源日期"]
    last = _table(ws, 4, headers, rows,
                  widths=[11, 14, 12, 28, 34, 14, 22, 12, 14, 24, 12, 12, 40, 9, 9, 12, 26, 11, 9, 7, 44, 40, 11],
                  col_formats={12: NUM_FMT}, wrap_cols=(10, 13, 17, 21, 22))
    r = last + 2
    ws.cell(row=r, column=1, value=f"记录数：{len(rows)}").font = Font(name="微软雅黑", size=10, bold=True, color=ORANGE)
    ws.cell(row=r + 1, column=1, value="本表为全工作簿唯一事实层：03/04/05/07/08/09/10 表均为本表的筛选求和，公式见 14_汇总公式与溯源。").font = SMALL_FONT
    # 数据条
    if last > 4:
        ws.conditional_formatting.add(f"L5:L{last}",
                                      DataBarRule(start_type="num", start_value=0, end_type="max", color=ACCENT))
    ws.auto_filter.ref = f"A4:W{last}"

    # ---------------- 07 区域汇总（省） ----------------
    ws = _sheet(wb, "07_区域汇总(省)", "省级产能汇总", "按省加总；同时给出按工艺拆分与集团分布")
    rows = []
    for prov, v in sorted(by_prov.items(), key=lambda x: -x[1]):
        cities = [c for (p, c) in by_city if p == prov]
        route_d: Dict[str, float] = {}
        grp_d: Dict[str, float] = {}
        for u in A.rows():
            p = ds.plants.get(u.plant_id)
            if p and p.province == prov:
                route_d[u.route] = route_d.get(u.route, 0) + (u.capacity or 0)
                gg = ds.groups.get(ds.entities[p.entity_id].group_id) if ds.entities.get(p.entity_id) else None
                key = gg.short_name if gg else "未归属"
                grp_d[key] = grp_d.get(key, 0) + (u.capacity or 0)
        holders = sorted(grp_d.items(), key=lambda x: -x[1])
        rows.append([prov, round(v, 1), v / total if total else None,
                     round(route_d.get("carbide", 0), 1), round(route_d.get("ethylene", 0), 1),
                     round(route_d.get("mixed", 0), 1), round(route_d.get("unknown", 0), 1),
                     len(cities), len(grp_d),
                     "、".join(f"{k}({x:.0f})" for k, x in holders[:4])])
    last = _table(ws, 4, ["省份", "产能合计(万吨/年)", "占样本比", "电石法", "乙烯法", "混合", "未核实",
                          "城市数", "集团数", "主要集团(万吨/年)"],
                  rows, widths=[20, 14, 10, 11, 11, 9, 9, 8, 8, 52],
                  col_formats={2: NUM_FMT, 3: PCT_FMT, 4: NUM_FMT, 5: NUM_FMT, 6: NUM_FMT, 7: NUM_FMT})
    tot = last + 2
    ws.cell(row=tot, column=1, value="合计").font = Font(name="微软雅黑", size=10, bold=True)
    for col, letter in ((2, "B"), (4, "D"), (5, "E"), (6, "F"), (7, "G")):
        c = ws.cell(row=tot, column=col, value=f"=SUM({letter}5:{letter}{last})")
        c.number_format = NUM_FMT
        c.font = Font(name="微软雅黑", size=10, bold=True)
    r = tot + 2
    _note(ws, r, "同一省份内「电石法+乙烯法+混合+未核实」= 该省合计；跨省合计 = 样本合计，不得另加全国口径。")

    # ---------------- 08 区域汇总（市） ----------------
    ws = _sheet(wb, "08_区域汇总(市)", "市级产能汇总", "按(省,市)加总，用于判断产业集聚的城市节点")
    rows = []
    for (prov, city), v in sorted(by_city.items(), key=lambda x: -x[1]):
        plants = [pid for pid, pp in ds.plants.items() if pp.province == prov and pp.city == city]
        grps = sorted({(ds.groups[ds.entities[ds.plants[pid].entity_id].group_id].short_name
                        if ds.plants[pid].entity_id in ds.entities and
                        ds.entities[ds.plants[pid].entity_id].group_id in ds.groups else "未归属")
                       for pid in plants})
        routes = sorted({ROUTE_LABELS.get(u.route, u.route) for pid in plants for u in ds.units_of_plant(pid)})
        rows.append([prov, city, round(v, 1), v / total if total else None, len(plants), "、".join(grps), " / ".join(routes)])
    _table(ws, 4, ["省", "市", "产能合计(万吨/年)", "占样本比", "基地数", "涉及集团", "工艺"],
           rows, widths=[18, 18, 14, 10, 8, 40, 26], col_formats={3: NUM_FMT, 4: PCT_FMT})

    # ---------------- 09 工艺路线汇总 ----------------
    ws = _sheet(wb, "09_工艺路线汇总", "工艺路线产能汇总",
                "路线定义见 01 表；「未核实」单列，不并入任何一条路线")
    rows = []
    for route, v in sorted(by_route.items(), key=lambda x: -x[1]):
        holders: Dict[str, float] = {}
        provs: Dict[str, float] = {}
        for u in A.rows():
            if u.route != route:
                continue
            p = ds.plants.get(u.plant_id)
            if not p:
                continue
            e = ds.entities.get(p.entity_id)
            g = ds.groups.get(e.group_id) if e else None
            k = g.short_name if g else "未归属"
            holders[k] = holders.get(k, 0) + (u.capacity or 0)
            provs[p.province] = provs.get(p.province, 0) + (u.capacity or 0)
        top = sorted(holders.items(), key=lambda x: -x[1])
        rows.append([ROUTE_LABELS.get(route, route), route, round(v, 1), v / total if total else None,
                     len(holders), "、".join(f"{k}({x:.0f})" for k, x in top[:5]),
                     "、".join(f"{k}({x:.0f})" for k, x in sorted(provs.items(), key=lambda x: -x[1])[:5])])
    last = _table(ws, 4, ["工艺路线", "代码", "产能(万吨/年)", "占样本比", "集团数", "主要集团(万吨/年)", "主要省份(万吨/年)"],
                  rows, widths=[20, 12, 14, 10, 8, 56, 56], col_formats={3: NUM_FMT, 4: PCT_FMT})
    r = last + 2
    for i, t in enumerate(ds.notes.get("route_notes", [])):
        _note(ws, r + i, t)

    # ---------------- 10 产品等级汇总 ----------------
    ws = _sheet(wb, "10_产品等级汇总", "按产品/等级拆分",
                "不同等级（通用树脂/专用料/糊树脂）是否计入总数，取决于行业统计口径，见 01 表说明")
    grade_d: Dict[str, Dict[str, Any]] = {}
    for u in A.rows():
        key = u.grade_class or "未分级"
        d = grade_d.setdefault(key, {"cap": 0.0, "units": 0, "prods": set(), "holders": {}})
        d["cap"] += u.capacity or 0
        d["units"] += 1
        d["prods"].add(u.product)
        p = ds.plants.get(u.plant_id)
        if p and ds.entities.get(p.entity_id):
            e = ds.entities[p.entity_id]
            g = ds.groups.get(e.group_id)
            nm = g.short_name if g else "未归属"
            d["holders"][nm] = d["holders"].get(nm, 0) + (u.capacity or 0)
    rows = []
    for k, d in sorted(grade_d.items(), key=lambda x: -x[1]["cap"]):
        top = sorted(d["holders"].items(), key=lambda x: -x[1])[:5]
        rows.append([k, round(d["cap"], 1), d["cap"] / total if total else None, d["units"],
                     "、".join(sorted(d["prods"])), "、".join(f"{n}({v:.0f})" for n, v in top)])
    last = _table(ws, 4, ["产品等级/类别", "产能(万吨/年)", "占样本比", "装置条数", "涉及产品/牌号", "主要集团"],
                  rows, widths=[18, 14, 10, 10, 52, 56], col_formats={2: NUM_FMT, 3: PCT_FMT})
    r = last + 2
    _note(ws, r, "提示：若行业总产能口径「包含糊状树脂」，则通用树脂+糊树脂之和方可与全国口径对比；仅用通用树脂对比会低估。")

    # ---------------- 11 在建拟建项目 ----------------
    ws = _sheet(wb, "11_在建拟建项目", "在建 / 拟建 / 扩建 / 试车 / 新投产项目",
                "阶段判定以最新公开进展为准；不得把拟建当作存量")
    rows = []
    for pr in sorted(ds.projects, key=lambda x: (x.expected_year or 9999, x.project_id)):
        e = ds.entities.get(pr.entity_id)
        g = ds.groups.get(e.group_id) if e else None
        p = ds.plants.get(pr.plant_id)
        tl = "；".join(f"{t.get('date','')} {t.get('event','')}" for t in (pr.timeline or []))
        rows.append([pr.project_id, pr.name, e.name if e else "", g.short_name if g else "",
                     pr.province or (p.province if p else ""), pr.city or (p.city if p else ""),
                     ROUTE_LABELS.get(pr.route, pr.route), pr.capacity, pr.capacity_note,
                     PROJECT_STAGE_LABELS.get(pr.stage, pr.stage),
                     pr.expected_period or pr.expected_year, pr.retired_capacity, pr.replacement_note,
                     (pr.capacity - (pr.retired_capacity or 0)) if pr.capacity is not None else None,
                     pr.capex, " / ".join(pr.source_ids), pr.confidence, tl, pr.note])
    last = _table(ws, 4, ["项目ID", "项目名称", "建设单位(法人)", "集团", "省", "市", "工艺", "规模(万吨/年)",
                          "原文表述", "建设阶段", "预计投产", "置换退出(万吨/年)", "置换说明",
                          "净增(万吨/年)", "投资额", "来源", "可信度", "进展时间线", "备注"],
                  rows, widths=[10, 40, 34, 14, 14, 12, 14, 12, 30, 12, 12, 14, 34, 12, 16, 12, 7, 60, 40],
                  col_formats={8: NUM_FMT, 12: NUM_FMT, 14: NUM_FMT}, wrap_cols=(2, 9, 13, 18, 19))
    ws.auto_filter.ref = f"A4:S{last}"
    r = last + 2
    _note(ws, r, "净增 = 规模 − 置换退出。置换退出无法确认时留空（不估算），该行不计入净增合计。")

    # ---------------- 12 新增净额还原 ----------------
    ws = _sheet(wb, "12_新增净额还原", "新增产能的毛/净/加权还原",
                "毛新增 ≠ 净新增 ≠ 实际可增量；加权仅供情景参考，不用于官方口径")
    rows = []
    for st in PROJECT_STAGE_LABELS:
        items = [p for p in ds.projects if p.stage == st]
        if not items:
            continue
        gross = sum(p.capacity or 0 for p in items)
        retired = sum(p.retired_capacity or 0 for p in items)
        net = gross - retired
        w = PIPELINE_WEIGHTS.get(st)
        rows.append([PROJECT_STAGE_LABELS[st], st, len(items),
                     round(gross, 1) if gross else None,
                     round(retired, 1) if retired else None,
                     round(net, 1) if gross else None,
                     w, round(net * w, 1) if (w and gross) else None,
                     "、".join(p.project_id for p in items)])
    last = _table(ws, 4, ["建设阶段", "代码", "项目数", "毛新增(万吨/年)", "置换退出(万吨/年)",
                          "净新增(万吨/年)", "确定性权重", "加权可增量(情景)", "项目ID"],
                  rows, widths=[16, 14, 8, 14, 14, 14, 12, 16, 40],
                  col_formats={4: NUM_FMT, 5: NUM_FMT, 6: NUM_FMT, 8: NUM_FMT})
    r = last + 2
    ws.cell(row=r, column=1, value="说明").font = Font(name="微软雅黑", size=10, bold=True, color=ORANGE)
    notes = [
        "① 毛新增 = Σ项目规模，未扣减任何退出产能；不得直接称为「产能将增加 X 万吨」。",
        "② 净新增 = 毛新增 − 置换/等量替代退出产能；仅当置换说明与退出产能均有来源时才可信。",
        "③ 加权可增量 = 净新增 × 确定性权重，是情景值而非预测；权重按阶段设定（在建 0.85、试车 0.95、环评 0.45、备案 0.25、拟建 0.10）。",
        "④ 存量与增量严禁相加；本表仅反映未来供给增量。",
    ]
    for i, t in enumerate(notes):
        _note(ws, r + 1 + i, t)

    # ---------------- 13 重复统计校验 ----------------
    ws = _sheet(wb, "13_重复统计校验", "重复统计与口径一致性自动校验",
                "规则 R1–R14；ERROR 必须在引用数据前处理，WARN 需在报告中说明")
    findings = checker_findings or DupChecker(ds).run()
    sev_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    rows = [[f.rule, f.severity, f.subject, f.message, f.fix]
            for f in sorted(findings, key=lambda x: (sev_order.get(x.severity, 9), x.rule))]
    last = _table(ws, 4, ["规则", "级别", "对象", "校验信息", "处理建议"], rows,
                  widths=[8, 9, 26, 86, 54], wrap_cols=(3, 4, 5))
    # 分级着色
    for i in range(5, last + 1):
        sev = ws.cell(row=i, column=2).value
        color = {"ERROR": RED, "WARN": AMBER, "INFO": ACCENT}.get(sev, GREY)
        c = ws.cell(row=i, column=2)
        c.font = Font(name="微软雅黑", size=9, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=color)
        c.alignment = Alignment(horizontal="center")
    r = last + 2
    n_err = sum(1 for f in findings if f.severity == "ERROR")
    n_warn = sum(1 for f in findings if f.severity == "WARN")
    n_info = sum(1 for f in findings if f.severity == "INFO")
    ws.cell(row=r, column=1, value=f"校验结果：ERROR {n_err} 项 / WARN {n_warn} 项 / INFO {n_info} 项").font = Font(
        name="微软雅黑", size=10, bold=True, color=(RED if n_err else GREEN))
    _note(ws, r + 1, "规则定义见 references/去重校验规则.md；R4 重复装置、R6 来源缺失、R11 置换未扣减是最常见的三类翻车点。")

    # ---------------- 14 汇总公式与溯源 ----------------
    ws = _sheet(wb, "14_汇总公式与溯源", "汇总公式与加成溯源",
                "每一条产能最终被计入哪些汇总项，可逐行核对，避免重复计入")
    trace = A.trace()
    rows = [[t["uid"], t["plant"], t["province"], t["city"], t["entity"], t["group"],
             ROUTE_LABELS.get(t["route"], t["route"]), t["basis"], t["capacity"],
             f"=SUMIFS('06_装置明细'!$L$5:$L$2000,'06_装置明细'!$D$5:$D$2000,\"{t['plant']}\")",
             "集团汇总", "省级汇总", "工艺汇总"]
            for t in trace]
    last = _table(ws, 4, ["装置ID", "基地", "省", "市", "法人", "集团", "工艺", "口径", "产能(万吨/年)",
                          "同基地合计(校验)", "计入集团", "计入省份", "计入工艺"],
                  rows, widths=[11, 26, 14, 12, 34, 14, 14, 10, 12, 14, 11, 11, 11],
                  col_formats={9: NUM_FMT, 10: NUM_FMT})
    r = last + 2
    fml = [
        ("集团产能合计", "=SUMIFS(06_装置明细!L:L, 06_装置明细!F:F, <集团简称>, 06_装置明细!K:K, <口径>)",
         "按集团简称+口径双条件求和；同一装置只落在一个集团下"),
        ("法人产能合计", "=SUMIFS(06_装置明细!L:L, 06_装置明细!E:E, <法人全称>, 06_装置明细!K:K, <口径>)",
         "法人是集团与基地之间的唯一桥梁"),
        ("省级产能合计", "=SUMIFS(06_装置明细!L:L, 06_装置明细!B:B, <省>, 06_装置明细!K:K, <口径>)", ""),
        ("工艺产能合计", "=SUMIFS(06_装置明细!L:L, 06_装置明细!I:I, <工艺>, 06_装置明细!K:K, <口径>)", ""),
        ("CR5（集团）", "=SUMPRODUCT(LARGE(集团合计,{1;2;3;4;5}))/SUM(集团合计)", "分子分母必须同口径同范围"),
        ("HHI（集团）", "=SUMPRODUCT((集团合计/SUM(集团合计)*100)^2)", "0–10000，<1000 分散"),
        ("样本覆盖率", "=样本合计/全国口径合计", "全国口径须有来源并注明年份"),
        ("净新增", "=毛新增−置换退出", "任何一项未知则该行净增为空，不估算"),
    ]
    ws.cell(row=r, column=1, value="标准汇总公式").font = Font(name="微软雅黑", size=11, bold=True, color=ORANGE)
    _table(ws, r + 1, ["汇总项", "公式", "要点"], [[a, b, c] for a, b, c in fml],
           widths=[18, 86, 54], freeze=False)

    # ---------------- 15 口径对比 ----------------
    ws = _sheet(wb, "15_口径对比", "不同产能口径对比（禁止相加）",
                "同一批装置在不同口径下的数值；缺口如实留空，不做折算")
    rows = []
    for u in sorted(ds.units, key=lambda x: (x.plant_id, x.product)):
        same = [x for x in ds.units if x.plant_id == u.plant_id and x.product == u.product]
        d = next((x.capacity for x in same if x.basis == BASIS_DESIGN), None)
        eff = next((x.capacity for x in same if x.basis == BASIS_EFFECTIVE), None)
        act = next((x.capacity for x in same if x.basis == BASIS_ACTUAL), None)
        if u.basis != BASIS_DESIGN and not (eff or act):
            continue
        p = ds.plants.get(u.plant_id)
        rows.append([u.uid, p.name if p else u.plant_id, u.product, d, eff, act,
                     (eff / d) if (d and eff) else None, (act / d) if (d and act) else None])
    last = _table(ws, 4, ["装置ID", "基地", "产品/牌号", "设计产能", "有效产能", "实际产量/核定",
                          "有效/设计", "实际/设计"],
                  rows, widths=[11, 28, 22, 12, 12, 14, 11, 11],
                  col_formats={4: NUM_FMT, 5: NUM_FMT, 6: NUM_FMT, 7: PCT_FMT, 8: PCT_FMT})
    r = last + 2
    _note(ws, r, "空白 = 该口径未公开取得（数据缺口），不做任何换算或外推。参见 16_数据缺口。")

    # ---------------- 16 数据缺口 ----------------
    ws = _sheet(wb, "16_数据缺口", "数据缺口清单", "缺口如实登记；禁止用行业均值/邻近年份/比例外推补齐")
    rows = [[g.get("id", ""), g.get("item", ""), g.get("affects", ""), g.get("status", ""),
             g.get("how_to_fill", ""), g.get("priority", "")] for g in ds.gaps]
    if not rows:
        rows = [["G-00", "未登记缺口", "", "", "", ""]]
    _table(ws, 4, ["编号", "缺口项", "影响范围", "当前状态", "补齐方式", "优先级"], rows,
           widths=[9, 44, 34, 20, 60, 9], wrap_cols=(2, 3, 5))

    # ---------------- 17 来源清单 ----------------
    ws = _sheet(wb, "17_来源清单", "数据来源清单", "A 一手 / B 权威二手 / C 一般二手 / D 未核实")
    rows = [[s.source_id, s.pub_type, s.title, s.org, s.date, s.confidence,
             CONFIDENCE_LABELS.get(s.confidence, ""), s.url, s.note] for s in ds.sources.values()]
    last = _table(ws, 4, ["编号", "类型", "标题", "发布机构", "日期", "等级", "等级说明", "URL", "备注"],
                  rows, widths=[9, 12, 60, 26, 11, 7, 14, 60, 40], wrap_cols=(3, 8, 9))
    for i in range(5, last + 1):
        lv = ws.cell(row=i, column=6).value
        c = ws.cell(row=i, column=6)
        c.font = Font(name="微软雅黑", size=9, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor={"A": GREEN, "B": ACCENT, "C": GOLD, "D": RED}.get(lv, GREY))
        c.alignment = Alignment(horizontal="center")

    # ---------------- 18 企业集团关系树 ----------------
    ws = _sheet(wb, "18_企业集团关系树", "集团 → 法人 → 基地 → 装置 关系树",
                "用于人工核对层级归属，防止集团合计与子公司产能重复计算")
    rows = []
    for g in sorted(ds.groups.values(), key=lambda x: -by_group.get(x.group_id, 0)):
        rows.append(["L1 集团", g.name, g.ultimate_controller, "", "", "", round(by_group.get(g.group_id, 0), 1)])
        for e in ds.entities_of_group(g.group_id):
            rows.append(["　L2 法人", e.name, e.stock_code or "—", "", "", "", round(by_entity.get(e.entity_id, 0), 1)])
            for p in ds.plants_of_entity(e.entity_id):
                rows.append(["　　L3 基地", p.name, f"{p.province}{p.city}", "", "", "", round(by_plant.get(p.plant_id, 0), 1)])
                for u in ds.units_of_plant(p.plant_id):
                    rows.append(["　　　L4 装置", u.uid, ROUTE_LABELS.get(u.route, u.route),
                                 BASIS_LABELS.get(u.basis, u.basis), u.product,
                                 STATUS_LABELS.get(u.status, u.status), u.capacity])
    _table(ws, 4, ["层级", "名称", "说明/属性", "口径", "产品", "状态", "产能(万吨/年)"], rows,
           widths=[12, 46, 34, 12, 22, 12, 14], col_formats={7: NUM_FMT})
    r = len(rows) + 6
    _note(ws, r, "核对方法：Σ(L2) = L1；Σ(L3) = L2；Σ(L4) = L3。任一不成立即存在重复统计或漏录。")

    # 几个原生图表
    try:
        _add_charts(wb, ds, A, by_group, by_prov, by_route)
    except Exception:
        pass

    wb.save(out_path)
    return out_path


def _add_charts(wb, ds, A, by_group, by_prov, by_route):
    """在 07/03 表旁插入原生图表，方便在 Excel 里直接查看分布。"""
    # 省份柱状图放在 07 表
    ws = wb["07_区域汇总(省)"]
    n = min(len(by_prov), 15)
    ch = BarChart()
    ch.type = "bar"
    ch.title = "省级产能分布（样本口径）"
    ch.y_axis.title = "万吨/年"
    data = Reference(ws, min_col=2, min_row=4, max_row=4 + n)
    cats = Reference(ws, min_col=1, min_row=5, max_row=4 + n)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    ch.height = 12
    ch.width = 20
    ch.legend = None
    ws.add_chart(ch, "L4")

    # 工艺饼图放在 09 表
    ws = wb["09_工艺路线汇总"]
    n = len(by_route)
    ch2 = PieChart()
    ch2.title = "工艺路线产能占比（样本口径）"
    data = Reference(ws, min_col=3, min_row=4, max_row=4 + n)
    cats = Reference(ws, min_col=1, min_row=5, max_row=4 + n)
    ch2.add_data(data, titles_from_data=True)
    ch2.set_categories(cats)
    ch2.height = 10
    ch2.width = 16
    ch2.dataLabels = DataLabelList()
    ch2.dataLabels.showPercent = True
    ws.add_chart(ch2, "I4")

    # 集团柱状图放在 03 表
    ws = wb["03_集团汇总"]
    n = min(len([k for k in by_group if k != "__ungrouped__"]), 15)
    if n:
        ch3 = BarChart()
        ch3.type = "bar"
        ch3.title = "集团产能 Top15（样本口径）"
        ch3.y_axis.title = "万吨/年"
        data = Reference(ws, min_col=5, min_row=4, max_row=4 + n)
        cats = Reference(ws, min_col=2, min_row=5, max_row=4 + n)
        ch3.add_data(data, titles_from_data=True)
        ch3.set_categories(cats)
        ch3.height = 13
        ch3.width = 22
        ch3.legend = None
        ws.add_chart(ch3, "M4")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from pcd_model import load
    ds = load(a.data)
    print(build(ds, a.out, DupChecker(ds).run()))
