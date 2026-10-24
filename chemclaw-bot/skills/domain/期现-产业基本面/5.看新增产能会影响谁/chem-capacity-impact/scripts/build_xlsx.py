#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chem-capacity-impact · Excel 工作簿生成（openpyxl）

13 张表，覆盖：口径 / 事实核验 / 现有产能基准 / 原料单耗 / 相对规模 / 产量情景 /
月度爬坡 / 原料需求 / 受影响对象 / 区域格局 / 结论分类 / 待核实 / 来源。

公式纪律：
- 参数单元格浅黄底（可改），公式单元格白底。
- 派生值全部写成 Excel 公式，改参数即重算，不是固化数字。
- 公式列旁加批注，写明含义与假设。
"""

from __future__ import annotations

import datetime
import os
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# ---------------- 样式 ----------------
C_DEEP = '1F3864'
C_MAIN = '2E5C9A'
C_HEAD = 'D9E2F3'
C_PARAM = 'FFF2CC'      # 参数：可改
C_FORMULA = 'FFFFFF'    # 公式：勿手改
C_FACT = 'E2EFDA'       # 事实
C_CALC = 'DDEBF7'       # 计算
C_SCEN = 'FCE4D6'       # 情景
C_WARN = 'FFE699'
C_GREY = 'F2F2F2'

THIN = Side(style='thin', color='BFBFBF')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

T_TITLE = Font(name='微软雅黑', size=15, bold=True, color='FFFFFF')
T_SUB = Font(name='微软雅黑', size=10, color='595959')
T_HEAD = Font(name='微软雅黑', size=10, bold=True, color='1F3864')
T_BODY = Font(name='微软雅黑', size=10)
T_SMALL = Font(name='微软雅黑', size=9, color='404040')
T_BOLD = Font(name='微软雅黑', size=10, bold=True)

F_TITLE = PatternFill('solid', fgColor=C_DEEP)
F_HEAD = PatternFill('solid', fgColor=C_HEAD)
F_PARAM = PatternFill('solid', fgColor=C_PARAM)
F_FORMULA = PatternFill('solid', fgColor=C_FORMULA)
F_FACT = PatternFill('solid', fgColor=C_FACT)
F_CALC = PatternFill('solid', fgColor=C_CALC)
F_SCEN = PatternFill('solid', fgColor=C_SCEN)
F_WARN = PatternFill('solid', fgColor=C_WARN)
F_GREY = PatternFill('solid', fgColor=C_GREY)

AL_WRAP = Alignment(wrap_text=True, vertical='top')
AL_CENTER = Alignment(horizontal='center', vertical='center')


def _t(value_t: float, digits: int = 2) -> str:
    return f'{_f(value_t) / 10000:.{digits}f}'


def _f(v: Any, default: float = 0.0) -> float:
    """安全转 float。"""
    if v is None or v == '':
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _w(ws, width_map: Dict[str, float]):
    for col, w in width_map.items():
        ws.column_dimensions[col].width = w


def title_row(ws, row: int, text: str, ncols: int = 10, sub: str = '') -> int:
    """写标题条，返回下一行号。"""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = T_TITLE
    c.fill = F_TITLE
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[row].height = 30
    row += 1
    if sub:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
        c = ws.cell(row=row, column=1, value=sub)
        c.font = T_SUB
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[row].height = max(18, 15 * (1 + len(sub) // max(1, ncols * 14)))
        row += 1
    return row


def header_row(ws, row: int, headers: List[str], fill: PatternFill = F_HEAD) -> int:
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = T_HEAD
        c.fill = fill
        c.border = BORDER
        c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
    ws.row_dimensions[row].height = 30
    return row + 1


def body_cell(ws, row: int, col: int, value: Any, fill: Optional[PatternFill] = None,
              fmt: Optional[str] = None, bold: bool = False, align: Optional[Alignment] = None,
              note: str = '') -> None:
    c = ws.cell(row=row, column=col, value=value)
    c.font = T_BOLD if bold else T_BODY
    c.border = BORDER
    c.alignment = align or AL_WRAP
    if fill:
        c.fill = fill
    if fmt:
        c.number_format = fmt
    if note:
        c.comment = Comment(note, 'chem-capacity-impact', width=320, height=110)


# --------------------------------------------------------------------------
# 主构建
# --------------------------------------------------------------------------

def build(data: Dict[str, Any], out_path: str) -> str:
    meta = data.get('meta') or {}
    proj = data.get('project') or {}
    shares = data.get('shares') or []
    coef = data.get('coefficients') or {}
    coef_rng = data.get('coefficients_range') or {}
    scenarios = data.get('scenarios') or []
    regional = data.get('regional') or {}
    stakeholders = data.get('stakeholders') or []
    conclusions = data.get('conclusions') or {}
    ucs = data.get('unit_consumption') or []
    assumptions = data.get('assumptions') or {}
    inputs = data.get('inputs') or {}

    wb = Workbook()
    product = meta.get('product', '本产品')
    cap_kt = inputs.get('capacity_10kt', 0)
    simulated = bool(meta.get('simulated'))

    # 记录跨表引用位置
    sheet_ref: Dict[str, Dict[str, str]] = {}

    _sheet_cover(wb, data, sheet_ref)
    _sheet_project(wb, data, sheet_ref)
    _sheet_bases(wb, data, sheet_ref)
    _sheet_uc(wb, data, sheet_ref)
    _sheet_share(wb, data, sheet_ref)
    _sheet_scenarios(wb, data, sheet_ref)
    _sheet_ramp(wb, data, sheet_ref)
    _sheet_materials(wb, data, sheet_ref)
    _sheet_stakeholders(wb, data, sheet_ref)
    _sheet_regional(wb, data, sheet_ref)
    _sheet_conclusions(wb, data, sheet_ref)
    _sheet_gaps(wb, data, sheet_ref)
    _sheet_sources(wb, data, sheet_ref)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    wb.save(out_path)
    return out_path


# --------------------------------------------------------------------------
# 00 封面
# --------------------------------------------------------------------------

def _sheet_cover(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.active
    ws.title = '00_封面与口径'
    ws.sheet_view.showGridLines = False
    meta = data.get('meta') or {}
    proj = data.get('project') or {}
    inputs = data.get('inputs') or {}

    ws.merge_cells('A1:F1')
    c = ws['A1']
    c.value = meta.get('title') or '新增产能影响研究报告'
    c.font = Font(name='微软雅黑', size=18, bold=True, color='FFFFFF')
    c.fill = F_TITLE
    c.alignment = Alignment(horizontal='left', vertical='center', indent=1)
    ws.row_dimensions[1].height = 44

    r = 2
    if meta.get('simulated'):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = ws.cell(row=r, column=1,
                    value='⚠ 模拟输入：' + (meta.get('simulated_note') or
                                          '本工作簿中的项目主体、存在性与进度为研究用模拟输入，非真实项目。'
                                          '现有产能、单耗、下游结构等背景数据取自公开来源并已标注。'))
        c.font = Font(name='微软雅黑', size=10, bold=True, color='9C0006')
        c.fill = PatternFill('solid', fgColor='FFC7CE')
        c.alignment = Alignment(wrap_text=True, vertical='center')
        ws.row_dimensions[r].height = 40
        r += 1

    r += 1
    rows = [
        ('产品', meta.get('product', ''), '工艺', meta.get('process', '')),
        ('项目名称', proj.get('name', ''), '业主', proj.get('owner', '')),
        ('建设地点', _loc(proj), '项目阶段', proj.get('stage', '')),
        ('设计产能', f"{inputs.get('capacity_10kt', 0)} 万吨/年", '产能口径', proj.get('capacity_scope', '')),
        ('计划投产', f"{inputs.get('start_year')} 年 {inputs.get('start_month')} 月", '数据截止日', meta.get('asof', '')),
        ('编制', meta.get('analyst', ''), '版本', meta.get('version', 'v1.0')),
    ]
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value='一、报告基本信息')
    c.font = Font(name='微软雅黑', size=11, bold=True, color=C_MAIN)
    r += 1
    for k1, v1, k2, v2 in rows:
        c = ws.cell(row=r, column=1, value=k1); c.font = T_HEAD; c.fill = F_HEAD; c.border = BORDER
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        c = ws.cell(row=r, column=2, value=v1); c.font = T_BODY; c.border = BORDER; c.alignment = AL_WRAP
        c = ws.cell(row=r, column=4, value=k2); c.font = T_HEAD; c.fill = F_HEAD; c.border = BORDER
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=6)
        c = ws.cell(row=r, column=5, value=v2); c.font = T_BODY; c.border = BORDER; c.alignment = AL_WRAP
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value='二、度量口径（三条铁律）')
    c.font = Font(name='微软雅黑', size=11, bold=True, color=C_MAIN)
    r += 1
    rules = [
        ('铁律 1', '首年产量 ≠ 设计产能。投产首年产量 = Σ 月度(设计产能/12 × 稳定开工率 × 爬坡负荷)，'
                   '必须按投产月份与爬坡曲线积分，不得把全年设计产能当作首年实际增量。'),
        ('铁律 2', '分子分母口径必须一致。新增产能（公称能力）÷ 现有产能（公称能力），且分母绑定年份与区域边界；'
                   '不可用产量当分母。'),
        ('铁律 3', '三类结论物理分离。本工作簿用底色区分：绿色=已确认事实，蓝色=有依据的计算，橙色=基于假设的情景。'
                   '情景结论不得与事实混写。'),
    ]
    for k, v in rules:
        c = ws.cell(row=r, column=1, value=k); c.font = T_BOLD; c.border = BORDER
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        c = ws.cell(row=r, column=2, value=v); c.font = T_BODY; c.border = BORDER; c.alignment = AL_WRAP
        ws.row_dimensions[r].height = 46
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value='三、图例')
    c.font = Font(name='微软雅黑', size=11, bold=True, color=C_MAIN)
    r += 1
    legend = [
        (F_FACT, '已确认事实', '来自官方/行业权威来源，可点开复核'),
        (F_CALC, '有依据的计算', '公式可由审阅者复算，输入均为事实或明确标注的假设'),
        (F_SCEN, '基于假设的情景', '依赖投产月/开工率/爬坡/单耗假设，参数可改'),
        (F_PARAM, '参数单元格（可改）', '改这里，下游公式自动重算'),
        (F_FORMULA, '公式单元格（勿手改）', '由脚本生成，手改会破坏一致性'),
    ]
    for fill, name, desc in legend:
        c = ws.cell(row=r, column=1, value=''); c.fill = fill; c.border = BORDER
        c = ws.cell(row=r, column=2, value=name); c.font = T_BOLD; c.border = BORDER
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
        c = ws.cell(row=r, column=3, value=desc); c.font = T_BODY; c.alignment = AL_WRAP; c.border = BORDER
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1,
                value='四、免责声明：本工作簿不构成价格预测。所有"影响"均以机制与量级表达（占产能比、原料需求量、'
                      '区域自给率变化），不输出涨跌方向。缺失数据一律标为缺口，不做插值或估算。')
    c.font = T_SMALL
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.row_dimensions[r].height = 46

    _w(ws, {'A': 14, 'B': 26, 'C': 26, 'D': 16, 'E': 26, 'F': 26})


def _loc(proj: Dict[str, Any]) -> str:
    loc = proj.get('location') or {}
    parts = [loc.get('province', ''), loc.get('city', ''), loc.get('district', ''), loc.get('park', '')]
    return ''.join([p for p in parts if p]) or '未注明'


# --------------------------------------------------------------------------
# 01 项目事实核验
# --------------------------------------------------------------------------

def _sheet_project(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('01_项目事实核验')
    proj = data.get('project') or {}
    conf = proj.get('phase_confidence') or {}
    ws.sheet_view.showGridLines = False
    r = title_row(ws, 1, '一、项目事实核验卡', 7,
                  '七项必核字段 + 证据等级。E1 一手官方 / E2 行业权威媒体 / E3 综合媒体 / E4 机构口径 / E5 待确认')
    hdr = ['必核字段', '核实内容', '证据等级', '来源', 'URL', '公告/抓取日期', '备注']
    r = header_row(ws, r, hdr)

    loc = proj.get('location') or {}
    sp = proj.get('startup_plan') or {}
    detail_map = {d.get('k'): d for d in (proj.get('detail') or [])}

    rows = [
        ('项目业主', proj.get('owner', ''), conf.get('owner', 'E5'), '', '', '', proj.get('owner_note', '')),
        ('建设地点', _loc(proj), conf.get('location', 'E5'), '', '', '', ''),
        ('产品与牌号', proj.get('product_spec', ''), conf.get('product', 'E5'), '', '', '', ''),
        ('设计产能', f"{proj.get('design_capacity_t', 0) / 10000:.1f} 万吨/年（{proj.get('capacity_scope', '')}）",
         conf.get('design_capacity', 'E5'), proj.get('capacity_source', ''),
         proj.get('capacity_url', ''), proj.get('capacity_date', ''), ''),
        ('工艺路线', proj.get('process_route', ''), conf.get('process', 'E5'), '', '', '', ''),
        ('项目阶段', proj.get('stage', ''), conf.get('stage', 'E5'), '', '', '', proj.get('stage_note', '')),
        ('预计投产时间', sp.get('text', ''), conf.get('startup', 'E5'), '', '', sp.get('announce_date', ''), ''),
    ]
    for k, v, lv, src, url, dt, note in rows:
        d = detail_map.get(k) or {}
        ev = d.get('evidence') or {}
        body_cell(ws, r, 1, k, F_FACT, bold=True)
        body_cell(ws, r, 2, v or d.get('v', ''), F_FACT)
        body_cell(ws, r, 3, lv or ev.get('level', 'E5'), _ev_fill(lv), align=AL_CENTER, bold=True)
        body_cell(ws, r, 4, src or ev.get('source', '') or '未核实', F_FACT)
        u = url or ev.get('url', '')
        body_cell(ws, r, 5, u or '未核实', F_FACT)
        if u:
            ws.cell(row=r, column=5).hyperlink = u
            ws.cell(row=r, column=5).font = Font(name='微软雅黑', size=9, color='0563C1', underline='single')
        body_cell(ws, r, 6, dt or ev.get('date', ''), F_FACT)
        body_cell(ws, r, 7, note, F_FACT)
        r += 1

    r += 1
    r = title_row(ws, r, '二、补充信息', 7, '')
    for k, v in (proj.get('supplement') or {}).items():
        body_cell(ws, r, 1, k, F_FACT, bold=True)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
        body_cell(ws, r, 2, v, F_FACT)
        r += 1

    r += 1
    r = title_row(ws, r, '三、核验结论', 7, '')
    for line in (proj.get('verdict') or []):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        body_cell(ws, r, 1, line, F_FACT)
        ws.row_dimensions[r].height = 32
        r += 1

    _w(ws, {'A': 16, 'B': 44, 'C': 11, 'D': 30, 'E': 34, 'F': 15, 'G': 26})
    ws.freeze_panes = 'A4'


def _ev_fill(level: Optional[str]) -> PatternFill:
    return {
        'E1': PatternFill('solid', fgColor='C6EFCE'),
        'E2': PatternFill('solid', fgColor='DDEBF7'),
        'E3': PatternFill('solid', fgColor='FFF2CC'),
        'E4': PatternFill('solid', fgColor='FCE4D6'),
        'E5': PatternFill('solid', fgColor='FFC7CE'),
    }.get(level or 'E5', PatternFill('solid', fgColor='FFC7CE'))


# --------------------------------------------------------------------------
# 02 现有产能基准
# --------------------------------------------------------------------------

def _sheet_bases(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('02_现有产能基准')
    ws.sheet_view.showGridLines = False
    meta = data.get('meta') or {}
    shares = data.get('shares') or []
    r = title_row(ws, 1, '二、现有产能基准（占比的分母）', 9,
                  '每组分母都要绑定"口径 + 年份 + 区域边界"。替代口径用于敏感性，不可与主口径混用。')
    r = header_row(ws, r, ['分母键', '口径名称', '数值（万吨/年）', '数值（吨/年）', '年份',
                           '口径说明', '证据等级', '来源', '备注'])
    start = r
    for s in shares:
        body_cell(ws, r, 1, s.get('key'), F_FACT)
        body_cell(ws, r, 2, s.get('label'), F_FACT)
        body_cell(ws, r, 3, f'=D{r}/10000', F_FORMULA, fmt='#,##0.0',
                  note='公式：吨/年 ÷ 10000 = 万吨/年')
        body_cell(ws, r, 4, s.get('base_t'), F_FACT, fmt='#,##0')
        body_cell(ws, r, 5, s.get('year'), F_FACT, align=AL_CENTER)
        body_cell(ws, r, 6, s.get('scope'), F_FACT)
        body_cell(ws, r, 7, s.get('level'), _ev_fill(s.get('level')), align=AL_CENTER)
        body_cell(ws, r, 8, s.get('source'), F_FACT)
        body_cell(ws, r, 9, s.get('note'), F_FACT)
        r += 1
    ref['bases'] = {'first': start, 'last': r - 1}
    ws.freeze_panes = 'A4'
    _w(ws, {'A': 14, 'B': 20, 'C': 16, 'D': 16, 'E': 8, 'F': 36, 'G': 10, 'H': 30, 'I': 30})


# --------------------------------------------------------------------------
# 03 原料单耗
# --------------------------------------------------------------------------

def _sheet_uc(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('03_原料单耗')
    ws.sheet_view.showGridLines = False
    ucs = data.get('unit_consumption') or []
    coef = data.get('coefficients') or {}
    r = title_row(ws, 1, '三、原料单耗（含证据等级与依据等级）', 11,
                  'C1 工程值（环评/可研）/ C2 区间中值 / C3 化学计量下限 / C4 情景假设。'
                  'C3 只能做"最低不可能低于"的校验，不能当实际单耗。')
    r = header_row(ws, r, ['单耗键', '从', '到', '单耗值(t/t)', '依据等级', '区间下限', '区间上限',
                           '纯度', '实际系数(单耗/纯度)', '证据等级', '来源与说明'])
    start = r
    for u in ucs:
        ev = u.get('evidence') or {}
        rng = u.get('range') or []
        body_cell(ws, r, 1, u.get('key'), F_FACT)
        body_cell(ws, r, 2, u.get('from', ''), F_FACT)
        body_cell(ws, r, 3, u.get('to', ''), F_FACT)
        body_cell(ws, r, 4, u.get('value'), F_PARAM, fmt='0.000',
                  note='参数：来自环评/可研或行业报道；标 C4 时请按情景调整')
        body_cell(ws, r, 5, u.get('basis', ''), F_FACT, align=AL_CENTER)
        body_cell(ws, r, 6, rng[0] if len(rng) == 2 else None, F_FACT, fmt='0.000')
        body_cell(ws, r, 7, rng[1] if len(rng) == 2 else None, F_FACT, fmt='0.000')
        body_cell(ws, r, 8, u.get('purity', 1.0), F_PARAM, fmt='0.00',
                  note='参数：原料纯度，需求按"单耗/纯度"折算为实物采购量')
        body_cell(ws, r, 9, f'=D{r}/H{r}', F_FORMULA, fmt='0.0000',
                  note='公式：单耗 ÷ 纯度 = 每吨产品所需实物原料系数')
        body_cell(ws, r, 10, ev.get('level', 'E5'), _ev_fill(ev.get('level')), align=AL_CENTER)
        src = ev.get('source', '')
        if ev.get('url'):
            src = f"{src}\n{ev.get('url')}" + (f"  时间: {ev.get('date')}" if ev.get('date') else '')
        body_cell(ws, r, 11, src or u.get('note', ''), F_FACT)
        r += 1
    ref['uc'] = {'first': start, 'last': r - 1}

    # 连乘结果
    r += 1
    r = title_row(ws, r, '四、单耗连乘结果（链上乘积）', 11,
                  '原料需求系数 = Π(单耗 / 纯度)，按工艺链顺序连乘。中间体外购的链不产生对上游的新增需求。')
    r = header_row(ws, r, ['原料/节点', '连乘系数(t/t)', '区间下限', '区间上限', '是否本项目自建',
                           '链上构成', '', '', '', '', ''])
    crng = data.get('coefficients_range') or {}
    for name, c in coef.items():
        rr = crng.get(name) or {}
        body_cell(ws, r, 1, name, F_CALC, bold=True)
        body_cell(ws, r, 2, c.get('coefficient'), F_CALC, fmt='0.0000')
        body_cell(ws, r, 3, rr.get('low'), F_CALC, fmt='0.0000')
        body_cell(ws, r, 4, rr.get('high'), F_CALC, fmt='0.0000')
        body_cell(ws, r, 5, '是' if c.get('on_site', True) else '否（外购）', F_CALC, align=AL_CENTER)
        parts = ' × '.join(f"{p.get('key')}({p.get('value')}/{p.get('purity')})" for p in c.get('parts', []))
        ws.merge_cells(start_row=r, start_column=6, end_row=r, end_column=11)
        body_cell(ws, r, 6, parts or '—', F_CALC)
        r += 1

    ws.freeze_panes = 'A4'
    _w(ws, {'A': 26, 'B': 12, 'C': 12, 'D': 14, 'E': 11, 'F': 11, 'G': 11, 'H': 8, 'I': 18, 'J': 9, 'K': 46})


# --------------------------------------------------------------------------
# 04 产能相对规模
# --------------------------------------------------------------------------

def _sheet_share(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('04_产能相对规模')
    ws.sheet_view.showGridLines = False
    shares = data.get('shares') or []
    inputs = data.get('inputs') or {}
    capacity_kt = _f(inputs.get('capacity_10kt'))
    r = title_row(ws, 1, '四、新增产能的相对规模', 9,
                  '同一新增产能，分母不同结论完全不同。六组分母全部列出，每项给出"档位"与"含义"，而非只给百分比。')
    r = header_row(ws, r, ['分母', '新增产能(万吨)', '分母(万吨)', '占比(%)', '档位',
                           '年份', '口径', '证据', '含义'])
    start = r
    for s in shares:
        body_cell(ws, r, 1, s.get('label'), F_CALC)
        body_cell(ws, r, 2, round(capacity_kt, 2), F_CALC, fmt='#,##0.0',
                  note='工程参数：设计产能（万吨/年），来自 project.design_capacity_t')
        if s.get('base_t'):
            body_cell(ws, r, 3, round(s['base_t'] / 10000, 2), F_CALC, fmt='#,##0.0',
                      note='分母（万吨/年），口径见 02_现有产能基准')
            body_cell(ws, r, 4, f'=B{r}/C{r}*100', F_FORMULA, fmt='0.00',
                      note='公式：新增产能 ÷ 分母 × 100 = 占比(%)')
        else:
            body_cell(ws, r, 3, None, F_CALC, fmt='#,##0.0')
            body_cell(ws, r, 4, None, F_CALC, note='分母缺失，占比不可计算')
        body_cell(ws, r, 5, s.get('tier'), _tier_fill(s.get('tier')), align=AL_CENTER, bold=True)
        body_cell(ws, r, 6, s.get('year'), F_CALC, align=AL_CENTER)
        body_cell(ws, r, 7, s.get('scope'), F_CALC)
        body_cell(ws, r, 8, s.get('level'), _ev_fill(s.get('level')), align=AL_CENTER)
        body_cell(ws, r, 9, _share_meaning(s), F_CALC)
        r += 1

    r += 1
    r = title_row(ws, r, '五、口径冲突与替代分母', 9,
                  '当来源对同一分母给出不同数值时，两套口径都列出并各算一次占比，不择其一。'
                  '以下替代口径来自 capacity_bases[].value_t_alt；分子统一引用上方主口径表的 B 列。')
    r = header_row(ws, r, ['分母', '替代口径说明', '替代分母(万吨)', '替代占比(%)', '差异(百分点)', '', '', '', ''])
    alt_i = 0
    for i, s in enumerate(shares):
        if s.get('share_alt_pct') is None:
            continue
        alt_t = s.get('base_t_alt')
        main_row = start + i          # 主口径表中该分母所在行（不是替代表行号）
        body_cell(ws, r, 1, s.get('label'), F_CALC)
        body_cell(ws, r, 2, s.get('alt_label') or '替代口径', F_CALC)
        if alt_t:
            body_cell(ws, r, 3, round(alt_t / 10000, 2), F_CALC, fmt='#,##0.0',
                      note='替代口径分母（万吨/年）；分子见 04 表主口径列的 B 列')
            # 分子必须引用"新增产能"，不能用 B{r}（该列此处是文本说明）
            body_cell(ws, r, 4, f'=$B${main_row}/C{r}*100', F_FORMULA, fmt='0.00',
                      note=f'公式：新增产能($B${main_row}) ÷ 替代分母 × 100')
            body_cell(ws, r, 5, f'=D{r}-$D${main_row}', F_FORMULA, fmt='0.00',
                      note=f'替代口径占比 − 主口径占比($D${main_row})')
        else:
            body_cell(ws, r, 3, None, F_CALC, fmt='#,##0.0')
            body_cell(ws, r, 4, s.get('share_alt_pct'), F_CALC, fmt='0.00')
            body_cell(ws, r, 5, f'=D{r}-$D${main_row}', F_FORMULA, fmt='0.00',
                      note=f'替代口径占比 − 主口径占比($D${main_row})')
        r += 1
        alt_i += 1
    if alt_i == 0:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
        body_cell(ws, r, 1, '数据中未提供替代口径（capacity_bases[].value_t_alt 全为空）。'
                            '若来源对分母存在冲突，建议补充替代口径后重出。', F_GREY)
        r += 1

    ws.freeze_panes = 'A4'
    _w(ws, {'A': 18, 'B': 15, 'C': 15, 'D': 12, 'E': 11, 'F': 8, 'G': 30, 'H': 7, 'I': 46})


def _tier_fill(t: Optional[str]) -> PatternFill:
    return {
        '可以忽略': PatternFill('solid', fgColor='F2F2F2'),
        '边际': PatternFill('solid', fgColor='FFF2CC'),
        '温和': PatternFill('solid', fgColor='FFF2CC'),
        '显著': PatternFill('solid', fgColor='FCE4D6'),
        '明显': PatternFill('solid', fgColor='FCE4D6'),
        '重大': PatternFill('solid', fgColor='F8CBAD'),
        '结构性': PatternFill('solid', fgColor='FFC7CE'),
        '洗牌级': PatternFill('solid', fgColor='FFC7CE'),
        '高': PatternFill('solid', fgColor='FFC7CE'),
        '中': PatternFill('solid', fgColor='FCE4D6'),
        '低': PatternFill('solid', fgColor='F2F2F2'),
    }.get(t or '', PatternFill('solid', fgColor='F2F2F2'))


def _share_meaning(s: Dict[str, Any]) -> str:
    key = s.get('key')
    pct = s.get('share_pct')
    if pct is None:
        return '分母缺失，无法计算占比。'
    if key == 'national':
        return f'对全国供需平衡的影响：{s.get("tier")}（约占 {pct:.2f}%）。'
    if key == 'regional':
        return f'区域一次性冲击强度：{s.get("tier")}（约占区域产能 {pct:.2f}%）。'
    if key == 'radius':
        return f'与竞争半径内同行的直接竞争强度：{s.get("tier")}（约占 {pct:.2f}%）。'
    if key == 'consumption':
        return f'相对全国需求量的边际影响：{s.get("tier")}（约占 {pct:.2f}%）。'
    return f'补充口径：{s.get("tier")}（{pct:.2f}%）。'


# --------------------------------------------------------------------------
# 05 产量情景
# --------------------------------------------------------------------------

def _sheet_scenarios(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('05_产量情景')
    ws.sheet_view.showGridLines = False
    scenarios = data.get('scenarios') or []
    inputs = data.get('inputs') or {}
    capacity_t = inputs.get('capacity_t', 0)
    r = title_row(ws, 1, '五、产量情景（首年 vs 稳态 vs 上限）', 13,
                  '关键纪律：投产首年产量 = Σ月度(设计产能/12 × 稳定开工率 × 爬坡负荷)。'
                  '把设计产能直接当首年增量，会系统性高估 40%–60%。')
    r = header_row(ws, r, ['情景', '类型', '开车年', '开车月', '当年可产月数', '稳定开工率(%)',
                           '爬坡模型', '爬坡月数', '首年产量(万吨)', '占设计产能(%)',
                           '稳定运行年产量(万吨)', '满负荷上限(万吨)', '说明'])
    start = r
    for i, s in enumerate(scenarios):
        p = s.get('production') or {}
        body_cell(ws, r, 1, s.get('id'), F_SCEN, bold=True)
        body_cell(ws, r, 2, s.get('kind'), F_SCEN, align=AL_CENTER)
        body_cell(ws, r, 3, s.get('start_year'), F_PARAM, align=AL_CENTER)
        body_cell(ws, r, 4, s.get('start_month'), F_PARAM, align=AL_CENTER)
        body_cell(ws, r, 5, f'=12-D{r}+1', F_FORMULA, align=AL_CENTER,
                  note='公式：12 − 开车月 + 1 = 投产当年可产月数（未计跨年情况）')
        body_cell(ws, r, 6, round(s.get('steady_lf', 0) * 100, 2), F_PARAM, fmt='0.0')
        body_cell(ws, r, 7, s.get('ramp_model'), F_PARAM, align=AL_CENTER)
        body_cell(ws, r, 8, s.get('ramp_months'), F_PARAM, align=AL_CENTER)
        # 首年产量引用 06 月度明细的合计
        body_cell(ws, r, 9, p.get('first_year_output_t', 0) / 10000, F_SCEN, fmt='#,##0.00',
                  note='引自 06_月度爬坡明细 的首年合计（万吨）')
        body_cell(ws, r, 10, f'=I{r}/{"K"}{r}*100' if False else round(p.get('first_year_ratio', 0) * 100, 2),
                  F_SCEN, fmt='0.0',
                  note='首年产量 ÷ 设计产能 × 100')
        body_cell(ws, r, 11, p.get('steady_output_t', 0) / 10000, F_SCEN, fmt='#,##0.00',
                  note='稳态年产量 = 设计产能 × 稳定开工率（万吨）')
        body_cell(ws, r, 12, p.get('full_output_t', 0) / 10000, F_SCEN, fmt='#,##0.00',
                  note='理论上限 = 设计产能本身（仅供校验，现实中不出现）')
        body_cell(ws, r, 13, s.get('note', ''), F_SCEN)
        r += 1

    r += 1
    r = title_row(ws, r, '六、按自然年汇总（前三年）', 13, '跨年积分：开车在 Q4 时首年产量可能只有 2–3 个月。')
    years = sorted({y['year'] for s in scenarios for y in (s.get('production') or {}).get('by_year', [])})
    hdr = ['情景'] + [f'{y} 年(万吨)' for y in years]
    r = header_row(ws, r, hdr)
    for s in scenarios:
        body_cell(ws, r, 1, s.get('id'), F_SCEN, bold=True)
        for j, y in enumerate(years, start=2):
            row_y = next((x for x in (s.get('production') or {}).get('by_year', []) if x['year'] == y), None)
            body_cell(ws, r, j, (row_y['output_t'] / 10000) if row_y else 0, F_SCEN, fmt='#,##0.00')
        r += 1

    ws.freeze_panes = 'A4'
    _w(ws, {'A': 8, 'B': 9, 'C': 8, 'D': 8, 'E': 12, 'F': 12, 'G': 11, 'H': 9,
            'I': 14, 'J': 13, 'K': 17, 'L': 15, 'M': 40})


# --------------------------------------------------------------------------
# 06 月度爬坡明细
# --------------------------------------------------------------------------

def _sheet_ramp(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('06_月度爬坡明细')
    ws.sheet_view.showGridLines = False
    scenarios = data.get('scenarios') or []
    inputs = data.get('inputs') or {}
    capacity_t = inputs.get('capacity_t', 0)
    r = title_row(ws, 1, '六、月度爬坡明细（自开车月起 36 个月）', 8,
                  '负荷率 = 爬坡模型负荷 × 稳定开工率；月产量 = 设计产能/12 × 负荷率。'
                  '本表是 05/07 的计算底座。')
    r = header_row(ws, r, ['情景', '序列月序 k', '自然年', '月份', '爬坡模型负荷', '综合负荷',
                           '月产量(吨)', '月产量(万吨)'])
    for s in scenarios:
        p = s.get('production') or {}
        for m in p.get('series', []):
            body_cell(ws, r, 1, s.get('id'), F_GREY, align=AL_CENTER)
            body_cell(ws, r, 2, m['k'], F_GREY, align=AL_CENTER)
            body_cell(ws, r, 3, m['year'], F_GREY, align=AL_CENTER)
            body_cell(ws, r, 4, m['month'], F_GREY, align=AL_CENTER)
            body_cell(ws, r, 5, m['ramp'], F_GREY, fmt='0.0%')
            body_cell(ws, r, 6, m['load'], F_GREY, fmt='0.0%')
            body_cell(ws, r, 7, round(capacity_t / 12 * m['load'], 2), F_FORMULA, fmt='#,##0',
                      note='公式：设计产能/12 × 综合负荷')
            body_cell(ws, r, 8, f'=G{r}/10000', F_FORMULA, fmt='#,##0.00')
            r += 1
    ws.auto_filter.ref = f'A3:H{r-1}'
    ws.freeze_panes = 'A4'
    _w(ws, {'A': 8, 'B': 11, 'C': 10, 'D': 8, 'E': 13, 'F': 11, 'G': 16, 'H': 14})


# --------------------------------------------------------------------------
# 07 原料需求测算
# --------------------------------------------------------------------------

def _sheet_materials(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('07_原料需求测算')
    ws.sheet_view.showGridLines = False
    scenarios = data.get('scenarios') or []
    coef = data.get('coefficients') or {}
    r = title_row(ws, 1, '七、上游原料需求测算', 9,
                  '原料需求 = 产量 × 连乘系数。三档并列：投产首年实际需求 / 稳定运行年需求 / 满负荷上限需求。'
                  '首年需求才是真正冲击市场的量。')
    r = header_row(ws, r, ['情景', '原料/节点', '连乘系数(t/t)', '首年产量(万吨)',
                           '首年原料需求(万吨)', '稳态产量(万吨)', '稳态原料需求(万吨)',
                           '满负荷原料需求(万吨)', '是否本项目自建'])
    for s in scenarios:
        p = s.get('production') or {}
        y1 = p.get('first_year_output_t', 0) / 10000
        st = p.get('steady_output_t', 0) / 10000
        fl = p.get('full_output_t', 0) / 10000
        mats_y1 = {m['material']: m for m in (s.get('materials_first_year') or [])}
        for name, c in coef.items():
            k = c['coefficient']
            body_cell(ws, r, 1, s.get('id'), F_SCEN, bold=True)
            body_cell(ws, r, 2, name, F_SCEN)
            body_cell(ws, r, 3, k, F_SCEN, fmt='0.0000', note='引自 03_原料单耗 连乘结果')
            body_cell(ws, r, 4, y1, F_SCEN, fmt='#,##0.00')
            body_cell(ws, r, 5, f'=C{r}*D{r}', F_FORMULA, fmt='#,##0.00',
                      note='公式：连乘系数 × 首年产量 = 首年原料需求（万吨）')
            body_cell(ws, r, 6, st, F_SCEN, fmt='#,##0.00')
            body_cell(ws, r, 7, f'=C{r}*F{r}', F_FORMULA, fmt='#,##0.00',
                      note='公式：连乘系数 × 稳态产量 = 稳定年原料需求（万吨）')
            body_cell(ws, r, 8, f'=C{r}*{fl}', F_FORMULA, fmt='#,##0.00',
                      note='公式：连乘系数 × 满负荷产量（理论上限）')
            body_cell(ws, r, 9, '是' if c.get('on_site', True) else '否（外购中间体）', F_SCEN, align=AL_CENTER)
            r += 1

    # 单耗敏感性
    r += 1
    r = title_row(ws, r, '八、单耗敏感性（±5% / ±10%）', 9,
                  '若结论只在单耗精确到 ±2% 时成立，则该结论不稳健。')
    r = header_row(ws, r, ['原料', '基准系数', '-10%', '-5%', '+5%', '+10%',
                           '稳态需求 -10%(万吨)', '稳态需求基准(万吨)', '稳态需求 +10%(万吨)'])
    base_scn = scenarios[0] if scenarios else {}
    st = (base_scn.get('production') or {}).get('steady_output_t', 0) / 10000
    for name, c in coef.items():
        k = c['coefficient']
        body_cell(ws, r, 1, name, F_CALC, bold=True)
        body_cell(ws, r, 2, k, F_CALC, fmt='0.0000')
        for j, f in zip((3, 4, 5, 6), (0.9, 0.95, 1.05, 1.1)):
            body_cell(ws, r, j, f'=B{r}*{f}', F_FORMULA, fmt='0.0000')
        body_cell(ws, r, 7, f'=C{r}*{st}', F_FORMULA, fmt='#,##0.00')
        body_cell(ws, r, 8, f'=B{r}*{st}', F_FORMULA, fmt='#,##0.00')
        body_cell(ws, r, 9, f'=F{r}*{st}', F_FORMULA, fmt='#,##0.00')
        r += 1

    ws.freeze_panes = 'A4'
    _w(ws, {'A': 26, 'B': 18, 'C': 14, 'D': 14, 'E': 17, 'F': 15, 'G': 17, 'H': 18, 'I': 16})


# --------------------------------------------------------------------------
# 08 受影响对象
# --------------------------------------------------------------------------

def _sheet_stakeholders(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('08_受影响对象')
    ws.sheet_view.showGridLines = False
    sts = data.get('stakeholders') or []
    r = title_row(ws, 1, '八、受影响对象与影响强度', 11,
                  '影响强度 = 100 × (0.35·体量对数压缩 + 0.25·传导 + 0.20·时滞 + 0.20·证据确定性)。'
                  '分档只是提示，不是结论；权重见 references/impact-pathway.md。')
    r = header_row(ws, r, ['类型', '企业/节点', '所在区域', '产能(万吨/年)', '相关量(万吨)',
                           '市场分母(万吨)', '体量占比(%)', '传导', '时滞', '确定性',
                           '影响强度'])
    for s in sts:
        imp = s.get('impact') or {}
        body_cell(ws, r, 1, _type_cn(s.get('type')), F_CALC)
        body_cell(ws, r, 2, s.get('name'), F_CALC, bold=True)
        body_cell(ws, r, 3, s.get('region', ''), F_CALC)
        body_cell(ws, r, 4, (s.get('capacity_t') or 0) / 10000, F_CALC, fmt='#,##0.0')
        body_cell(ws, r, 5, (s.get('volume_basis_t') or 0) / 10000, F_CALC, fmt='#,##0.00')
        body_cell(ws, r, 6, (s.get('market_t') or 0) / 10000, F_CALC, fmt='#,##0.0')
        body_cell(ws, r, 7, f'=IF(F{r}=0,"",E{r}/F{r}*100)', F_FORMULA, fmt='0.00',
                  note='公式：相关量 ÷ 市场分母 × 100')
        p = imp.get('parts') or {}
        body_cell(ws, r, 8, p.get('transmission'), F_CALC, fmt='0.00')
        body_cell(ws, r, 9, p.get('lag'), F_CALC, fmt='0.00')
        body_cell(ws, r, 10, p.get('certainty'), F_CALC, fmt='0.00')
        body_cell(ws, r, 11, imp.get('score'), _tier_fill({'高': '结构性', '中': '明显', '低': '温和'}.get(imp.get('tier'))),
                  fmt='0.0', bold=True, align=AL_CENTER,
                  note='综合影响强度 0–100')
        r += 1

    r += 1
    r = title_row(ws, r, '九、影响机制说明', 11, '')
    r = header_row(ws, r, ['企业/节点', '影响机制', '证据等级', '来源', '', '', '', '', '', '', ''])
    for s in sts:
        ev = s.get('evidence') or {}
        body_cell(ws, r, 1, s.get('name'), F_CALC, bold=True)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        body_cell(ws, r, 2, s.get('note', ''), F_CALC)
        body_cell(ws, r, 5, ev.get('level', 'E5'), _ev_fill(ev.get('level')), align=AL_CENTER)
        ws.merge_cells(start_row=r, start_column=6, end_row=r, end_column=11)
        body_cell(ws, r, 6, ev.get('source', ''), F_CALC)
        ws.row_dimensions[r].height = 34
        r += 1

    ws.freeze_panes = 'A4'
    _w(ws, {'A': 12, 'B': 22, 'C': 12, 'D': 13, 'E': 12, 'F': 13, 'G': 12,
            'H': 8, 'I': 8, 'J': 9, 'K': 10})


def _type_cn(t: Optional[str]) -> str:
    return {
        'upstream': '上游原料', 'competitor': '同区域同行', 'downstream': '下游用户',
        'logistics': '物流仓储', 'byproduct': '副产物', 'policy': '政策准入',
    }.get(t or '', t or '—')


# --------------------------------------------------------------------------
# 09 区域供应格局
# --------------------------------------------------------------------------

def _sheet_regional(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('09_区域供应格局')
    ws.sheet_view.showGridLines = False
    reg = data.get('regional') or {}
    r = title_row(ws, 1, '九、区域供应格局与竞争半径', 8,
                  '自给率 = 区域产能 ÷ 区域需求。<1 净输入，≈1 基本平衡，>1 净输出。只描述机制，不预测价格。')
    r = header_row(ws, r, ['指标', '数值', '单位', '说明（含机制）'])
    rows = [
        ('区域', reg.get('region', ''), '', '区域边界：' + '、'.join(reg.get('provinces') or [])),
        ('区域现有产能', (reg.get('regional_capacity_t') or 0) / 10000, '万吨/年', '分母口径见 02_现有产能基准'),
        ('区域表观需求', (reg.get('regional_demand_t') or 0) / 10000, '万吨/年', '用于计算自给率'),
        ('本项目新增产能', (reg.get('new_capacity_t') or 0) / 10000, '万吨/年', '设计中（一期）产能'),
        ('同区域在建合计', (reg.get('pipeline_t') or 0) / 10000, '万吨/年', '避免只看单项目低估区域供给增量'),
        ('区域供给增量(含在建)', (reg.get('regional_supply_increase_t') or 0) / 10000, '万吨/年', '本项目 + 同区域在建'),
        ('区域供给增量率(%)', reg.get('regional_supply_increase_pct'), '%', '供给增量 ÷ 区域现有产能'),
        ('本项目占区域产能(%)', reg.get('new_capacity_share_pct'), '%', '单项目口径'),
        ('自给率(前)', reg.get('self_sufficiency_before'), '倍', reg.get('flow_before', '')),
        ('自给率(后)', reg.get('self_sufficiency_after'), '倍', reg.get('flow_after', '')),
        ('自给率变化(百分点)', reg.get('ss_delta_pct'), 'pct', ''),
        ('机制说明', reg.get('mechanism', ''), '', '只描述机制，不预测价格'),
    ]
    for k, v, u, d in rows:
        body_cell(ws, r, 1, k, F_CALC, bold=True)
        if isinstance(v, (int, float)):
            body_cell(ws, r, 2, round(v, 2), F_CALC, fmt='#,##0.00')
            body_cell(ws, r, 3, u, F_CALC, align=AL_CENTER)
            body_cell(ws, r, 4, d, F_CALC)
        else:
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
            body_cell(ws, r, 2, v, F_CALC)
        ws.row_dimensions[r].height = 30
        r += 1

    r += 1
    r = title_row(ws, r, '十、竞争半径内同行（按距离排序）', 8,
                  '距离由厂址经纬度 haversine 计算；未给坐标者为来源原文距离。')
    r = header_row(ws, r, ['企业', '省份', '距本项目(km)', '产能(万吨/年)', '距离分档', '证据', '来源', ''])
    for n in reg.get('neighbors') or []:
        d = n.get('distance_km') or 0
        band = '≤100' if d <= 100 else ('100–300' if d <= 300 else ('300–500' if d <= 500 else ('500–1000' if d <= 1000 else '>1000')))
        body_cell(ws, r, 1, n.get('name'), F_CALC)
        body_cell(ws, r, 2, n.get('province', ''), F_CALC)
        body_cell(ws, r, 3, d, F_CALC, fmt='#,##0.0')
        body_cell(ws, r, 4, (n.get('capacity_t') or 0) / 10000, F_CALC, fmt='#,##0.0')
        body_cell(ws, r, 5, band + ' km', F_CALC, align=AL_CENTER)
        body_cell(ws, r, 6, n.get('level', ''), _ev_fill(n.get('level')), align=AL_CENTER)
        ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=8)
        body_cell(ws, r, 7, n.get('source', ''), F_CALC)
        r += 1

    r += 1
    r = title_row(ws, r, '十一、距离分档汇总', 8, '')
    r = header_row(ws, r, ['距离分档', '企业家数', '产能合计(万吨)', '占本项目(%)', '成员', '', '', ''])
    for b in reg.get('radius_bands') or []:
        body_cell(ws, r, 1, b.get('band'), F_CALC)
        body_cell(ws, r, 2, b.get('count'), F_CALC, align=AL_CENTER)
        body_cell(ws, r, 3, (b.get('capacity_t') or 0) / 10000, F_CALC, fmt='#,##0.0')
        body_cell(ws, r, 4, b.get('share_pct'), F_CALC, fmt='0.00')
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=8)
        body_cell(ws, r, 5, '、'.join(b.get('members') or []), F_CALC)
        r += 1

    _w(ws, {'A': 22, 'B': 16, 'C': 14, 'D': 16, 'E': 14, 'F': 12, 'G': 30, 'H': 14})


# --------------------------------------------------------------------------
# 10 结论分类
# --------------------------------------------------------------------------

def _sheet_conclusions(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('10_结论分类')
    ws.sheet_view.showGridLines = False
    con = data.get('conclusions') or {}
    r = title_row(ws, 1, '十、结论分类：事实 / 计算 / 情景', 6,
                  '三类结论必须物理分离。情景结论不得与事实混写在同一句中。')
    blocks = [
        ('A. 已确认事实', 'facts', F_FACT, '有 E1/E2 出处的项目事实'),
        ('B. 有依据的计算', 'calc', F_CALC, '公式 + 输入均来自事实；审阅者可复算'),
        ('C. 基于假设的情景', 'scenarios', F_SCEN, '依赖投产月/开工率/爬坡/单耗假设；参数可改'),
    ]
    for title, key, fill, desc in blocks:
        r = title_row(ws, r, title, 6, desc)
        items = con.get(key) or []
        if key == 'facts':
            r = header_row(ws, r, ['事实', '证据', '来源', '日期', '', ''])
            for it in items:
                body_cell(ws, r, 1, it.get('text'), fill)
                body_cell(ws, r, 2, it.get('level', ''), fill, align=AL_CENTER)
                body_cell(ws, r, 3, it.get('source', ''), fill)
                body_cell(ws, r, 4, it.get('date', ''), fill)
                r += 1
        elif key == 'calc':
            r = header_row(ws, r, ['计算结果', '计算依据', '输入证据', '', '', ''])
            for it in items:
                body_cell(ws, r, 1, it.get('text'), fill)
                ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
                body_cell(ws, r, 2, it.get('basis', ''), fill)
                body_cell(ws, r, 4, it.get('level', ''), fill, align=AL_CENTER)
                r += 1
        else:
            r = header_row(ws, r, ['情景', '类型', '结论（含假设参数）', '', '', ''])
            for it in items:
                body_cell(ws, r, 1, it.get('scenario'), fill, bold=True)
                body_cell(ws, r, 2, it.get('kind', ''), fill, align=AL_CENTER)
                ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
                body_cell(ws, r, 3, it.get('text'), fill)
                ws.row_dimensions[r].height = 32
                r += 1
        r += 1

    _w(ws, {'A': 30, 'B': 22, 'C': 34, 'D': 14, 'E': 12, 'F': 20})


# --------------------------------------------------------------------------
# 11 待核实
# --------------------------------------------------------------------------

def _sheet_gaps(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('11_待核实事项')
    ws.sheet_view.showGridLines = False
    gaps = data.get('gaps') or []
    r = title_row(ws, 1, '十一、还需核实的事项（八项必查）', 7,
                  '缺口不影响"已确认事实"，但直接决定情景参数的置信度。每一项都要写清"影响哪一步计算"与"补齐路径"。')
    r = header_row(ws, r, ['类别', '待核实事项', '影响哪一步计算', '补齐路径', '优先级', '责任方', '当前状态'])
    for g in gaps:
        pr = g.get('priority', '中')
        body_cell(ws, r, 1, g.get('category', ''), F_WARN)
        body_cell(ws, r, 2, g.get('item', ''), F_WARN)
        body_cell(ws, r, 3, g.get('impact', ''), F_WARN)
        body_cell(ws, r, 4, g.get('plan', ''), F_WARN)
        body_cell(ws, r, 5, pr, PatternFill('solid', fgColor='FFC7CE' if pr == '高' else 'FFF2CC'),
                  align=AL_CENTER, bold=True)
        body_cell(ws, r, 6, g.get('owner', ''), F_WARN)
        body_cell(ws, r, 7, g.get('status', '未核实'), F_WARN)
        ws.row_dimensions[r].height = 44
        r += 1
    ws.freeze_panes = 'A4'
    _w(ws, {'A': 12, 'B': 30, 'C': 28, 'D': 34, 'E': 8, 'F': 12, 'G': 14})


# --------------------------------------------------------------------------
# 12 来源
# --------------------------------------------------------------------------

def _sheet_sources(wb: Workbook, data: Dict[str, Any], ref: Dict) -> None:
    ws = wb.create_sheet('12_来源清单')
    ws.sheet_view.showGridLines = False
    srcs = data.get('sources') or []
    r = title_row(ws, 1, '十二、来源清单', 6,
                  '每条来源都应有可点开的 URL。标"未核实"的条目在报告中不得被当作事实引用。')
    r = header_row(ws, r, ['序号', '来源名称', '类型', '日期', 'URL', '用于哪一项'])
    for i, s in enumerate(srcs, start=1):
        body_cell(ws, r, 1, i, F_FACT, align=AL_CENTER)
        body_cell(ws, r, 2, s.get('name', ''), F_FACT)
        body_cell(ws, r, 3, s.get('type', ''), F_FACT, align=AL_CENTER)
        body_cell(ws, r, 4, s.get('date', ''), F_FACT, align=AL_CENTER)
        u = s.get('url') or '未核实'
        body_cell(ws, r, 5, u, F_FACT)
        if u.startswith('http'):
            ws.cell(row=r, column=5).hyperlink = u
            ws.cell(row=r, column=5).font = Font(name='微软雅黑', size=9, color='0563C1', underline='single')
        body_cell(ws, r, 6, s.get('used_for', ''), F_FACT)
        r += 1
    ws.freeze_panes = 'A4'
    _w(ws, {'A': 6, 'B': 40, 'C': 12, 'D': 12, 'E': 56, 'F': 30})


if __name__ == '__main__':
    import argparse
    import json
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from compute import compute_all

    ap = argparse.ArgumentParser()
    ap.add_argument('project_json')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    with open(a.project_json, 'r', encoding='utf-8-sig') as fh:
        pj = json.load(fh)
    print(build(compute_all(pj), a.out))
