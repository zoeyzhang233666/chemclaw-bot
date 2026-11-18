#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 12 表的工作簿（纯静态值，无公式，含筛选/冻结/色阶/图表）。

用法: python build_xlsx.py data.json out.xlsx
"""
import os
import sys

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import common

FONT = '微软雅黑'
TEAL = '0B6B5B'
TEAL_L = 'E7F3F0'
INK = '101828'
INK2 = '344054'
MUT = '667085'
LINE = 'E4E8EE'
ZEBRA = 'F7F9FA'
TIER_FILL = {'S': ('FDECE1', 'C2410C'), 'A': ('E2F2EF', '0F766E'),
             'B': ('E7EDFD', '1D4ED8'), 'C': ('EEF1F5', '8492A6')}
TYPE_FILL = {'生产': ('E8F1FF', '1A4D9E'), '贸易': ('F0ECFB', '5B3FA8'),
             '同行': ('FDEAEA', 'A02C2C'), '误判': ('F4F5F7', '5F6B7A')}
CONF_FILL = {'高': ('E2F2EF', '0A5A4D'), '中': ('FDF3E3', '8A5A08'), '低': ('F4F5F7', '68738A')}

THIN = Side(style='thin', color=LINE)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def sheet_base(ws, title, subtitle, ncol):
    ws.sheet_view.showGridLines = False
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=title)
    c.font = Font(name=FONT, size=15, bold=True, color=INK)
    c.alignment = Alignment(vertical='center')
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c = ws.cell(row=2, column=1, value=subtitle)
    c.font = Font(name=FONT, size=9.5, color=MUT)
    ws.row_dimensions[2].height = 18


def header_row(ws, row, headers, widths):
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(name=FONT, size=9.5, bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor=TEAL)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = BOX
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 30


def body(ws, row, values, aligns, zebra=False, tall=0):
    for i, (v, a) in enumerate(zip(values, aligns), start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(name=FONT, size=9.5, color=INK2)
        c.alignment = Alignment(horizontal=a, vertical='center', wrap_text=True)
        c.border = BOX
        if zebra:
            c.fill = PatternFill('solid', fgColor=ZEBRA)


def note_block(ws, row, lines, ncol, title=None):
    if title:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
        c = ws.cell(row=row, column=1, value=title)
        c.font = Font(name=FONT, size=11, bold=True, color=TEAL)
        ws.row_dimensions[row].height = 22
        row += 1
    for ln in lines:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
        c = ws.cell(row=row, column=1, value=ln)
        c.font = Font(name=FONT, size=9.5, color=INK2)
        c.alignment = Alignment(vertical='center', wrap_text=True)
        row += 1
    return row


def _textlen(v):
    s = str(v) if v is not None else ''
    return sum(2 if ord(ch) > 127 else 1 for ch in s)


def autofit(ws, start_row=5, min_h=16):
    widths = {}
    for k, dim in ws.column_dimensions.items():
        if dim.width:
            widths[k] = dim.width
    merged = set()
    for rng in ws.merged_cells.ranges:
        merged.add((rng.min_row, rng.min_col))
    for row in ws.iter_rows(min_row=start_row):
        lines = 1
        for c in row:
            if c.value is None:
                continue
            w = widths.get(c.column_letter, 12)
            if (c.row, c.column) in merged:
                w = sum(widths.get(get_column_letter(i), 12)
                        for i in range(c.column, c.column + 6))
            lines = max(lines, min(6, int(_textlen(c.value) / max(w - 1, 4)) + 1))
        ws.row_dimensions[row[0].row].height = max(min_h, 13.6 * lines + 4)


def build(data_path, out_path):
    D = common.load(data_path)
    M, S, N = D['meta'], D['summary'], D.get('narrative') or {}
    UNIT = M.get('demand_unit', '万吨/年')
    DL = M.get('demand_label', '需求量')
    cities, projs, cos = D['cities'], D['projects'], D['companies']
    lanes = {l['id']: l for l in D['lanes']}
    A = M.get('anchor') or {}
    sub = '%s · %s ｜ 数据截至 %s ｜ 需求量单位 %s ｜ 企业家数为估算，非工商统计' % (
        M['product'], M['region'], M['asof'], UNIT)

    wb = Workbook()

    # ---------------- 01 概览与结论 ----------------
    ws = wb.active
    ws.title = '01 概览与结论'
    sheet_base(ws, '%s · %s 区域市场研究' % (M['product'], M['region']), sub, 7)
    r = 4
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    c = ws.cell(row=r, column=1, value='一、这张表回答什么')
    c.font = Font(name=FONT, size=11.5, bold=True, color=TEAL)
    r += 1
    r = note_block(ws, r, [
        '1) 客户集中在哪些城市和化工园区，各有多少家潜在企业；2) 其中生产企业与贸易商各占多少；'
        '3) 主要下游行业是什么、为什么用这个产品；4) 代表企业是谁、中小企业藏在哪里；'
        '5) 最近有哪些新建/扩产/减产项目；6) 本地价格与区外差多少。最后给出走访优先级与路线。',
    ], 7)
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    c = ws.cell(row=r, column=1, value='二、关键指标')
    c.font = Font(name=FONT, size=11.5, bold=True, color=TEAL)
    r += 1
    kpi = [('潜在生产型企业', S['firms'], '家'), ('贸易 / 分销商', S['traders'], '家'),
           (DL + '（估算）', S['demand'], UNIT), ('覆盖城市', S['cities'], '个'),
           ('化工园区 / 集聚区', S.get('parks', 0), '个'),
           ('价格锚点', A.get('value', '—'), A.get('unit', '元/吨')),
           ('新建/扩产项目', len(projs), '个')]
    header_row(ws, r, ['指标', '数值', '单位', '', '', '', '说明'], [22, 14, 12, 6, 6, 6, 52])
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    r += 1
    for k, v, u in kpi:
        vals = [k, v, u, '', '', '', '']
        body(ws, r, vals, ['left', 'right', 'left', 'left', 'left', 'left', 'left'])
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        if isinstance(v, (int, float)):
            n = ws.cell(row=r, column=2)
            n.font = Font(name=FONT, size=10.5, bold=True, color=INK)
        r += 1
    r += 1
    r = note_block(ws, r, N.get('conclusions') or ['（未填写结论）'], 7, '三、结论与打法')
    r += 1
    r = note_block(ws, r, N.get('usage') or [], 7, '四、怎么用这张表')
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    c = ws.cell(row=r, column=1, value='五、目录（点击跳转）')
    c.font = Font(name=FONT, size=11.5, bold=True, color=TEAL)
    r += 1
    toc = [('01 概览与结论', '结论、指标与目录'), ('02 省级汇总', '%d 个省级单位的客户与需求' % len(D['provinces'])),
           ('03 城市明细', '%d 个城市排序与机会指数' % len(cities)),
           ('04 园区清单', '园区级客户池与扫园建议'),
           ('05 客户线索', '%d 家具名样本（含证据）' % len(cos)),
           ('06 中小集群', '无法具名但必须覆盖的客户池'),
           ('07 重点项目', '%d 个扩产/技改/减产' % len(projs)),
           ('08 价格对比', '区域价差与报价建议'),
           ('09 走访计划', '路线、天数与覆盖测算'),
           ('10 下游行业', '%d 条方向的用料逻辑' % len(D['lanes'])),
           ('11 同行与误判', '谁不是客户，别浪费行程'),
           ('12 方法与缺口', '口径、证据与负结果')]
    for i, (nm, desc) in enumerate(toc):
        row = r + i // 2
        col = 1 + (i % 2) * 4
        ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + 2)
        c = ws.cell(row=row, column=col, value='%s　—　%s' % (nm, desc))
        c.font = Font(name=FONT, size=9.5, color=TEAL, underline='single')
        c.hyperlink = "#'%s'!A1" % nm
        c.alignment = Alignment(vertical='center')
        ws.row_dimensions[row].height = 18
    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['G'].width = 52

    # ---------------- 02 省级汇总 ----------------
    ws = wb.create_sheet('02 省级汇总')
    sheet_base(ws, '省级汇总', sub + ' ｜ 判断列为「该省怎么打」', 7)
    hdr = ['省级单位', '城市数', '生产企业', '贸易商', DL, '占区域比重', '判断 / 打法']
    header_row(ws, 4, hdr, [16, 9, 11, 11, 12, 12, 86])
    r = 5
    for p in D['provinces']:
        body(ws, r, [p['prov'], p['cities'], p['firms'], p['traders'], round(p['demand'], 1),
                     round(p['demand'] / S['demand'], 3), p.get('judge', '')],
             ['left', 'center', 'right', 'right', 'right', 'right', 'left'], zebra=(r % 2 == 1))
        ws.cell(row=r, column=6).number_format = '0.0%'
        r += 1
    body(ws, r, ['合计', S['cities'], S['firms'], S['traders'], round(S['demand'], 1), 1, ''],
         ['left', 'center', 'right', 'right', 'right', 'right', 'left'])
    for i in range(1, 8):
        ws.cell(row=r, column=i).font = Font(name=FONT, size=9.5, bold=True, color=INK)
        ws.cell(row=r, column=i).fill = PatternFill('solid', fgColor=TEAL_L)
    ws.cell(row=r, column=6).number_format = '0.0%'
    ws.auto_filter.ref = 'A4:G%d' % (r - 1)
    ws.freeze_panes = 'A5'
    ch = BarChart()
    ch.type = 'bar'
    ch.title = '各省%s' % DL
    ch.height, ch.width = 7.5, 12
    data = Reference(ws, min_col=5, min_row=4, max_row=r - 1)
    cats = Reference(ws, min_col=1, min_row=5, max_row=r - 1)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    ch.legend = None
    ws.add_chart(ch, 'A%d' % (r + 2))
    autofit(ws, 5)

    # ---------------- 03 城市明细 ----------------
    ws = wb.create_sheet('03 城市明细')
    sheet_base(ws, '城市明细（按机会指数排序）',
               sub + ' ｜ 等级 S/A/B/C 由机会指数排名决定；建议天数=企业数/每日拜访数', 14)
    hdr = ['#', '城市', '省', '等级', '机会指数', '生产企业', '贸易商', DL,
           '单客户均值', '主导下游', '园区数', '项目增量', '建议天数', '一句话判断']
    header_row(ws, 4, hdr, [5, 14, 7, 6, 10, 11, 9, 10, 12, 16, 8, 11, 9, 74])
    r = 5
    for c in cities:
        top = c['inds'][0] if c['inds'] else {'name': '—', 'share': 0}
        body(ws, r, [c['rank'], c['city'], c['prov'], c['tier'], c['score'], c['firms'],
                     c['traders'], c['demand'], c['avg'],
                     '%s %d%%' % (top['name'], round(top['share'] * 100)),
                     len(c['parks']), c['proj_kt'], c['days'], c.get('note', '')],
             ['center', 'left', 'left', 'center', 'right', 'right', 'right', 'right',
              'right', 'left', 'center', 'right', 'center', 'left'], zebra=(r % 2 == 0))
        tf, tc = TIER_FILL[c['tier']]
        cell = ws.cell(row=r, column=4)
        cell.fill = PatternFill('solid', fgColor=tf)
        cell.font = Font(name=FONT, size=9.5, bold=True, color=tc)
        cell.alignment = Alignment(horizontal='center', vertical='center')
        r += 1
    last = r - 1
    ws.auto_filter.ref = 'A4:N%d' % last
    ws.freeze_panes = 'D5'
    for col in (5, 8, 13):
        L = get_column_letter(col)
        ws.conditional_formatting.add('%s5:%s%d' % (L, L, last),
                                      ColorScaleRule(start_type='min', start_color='FFFFFF',
                                                     mid_type='percentile', mid_value=50, mid_color='E2F2EF',
                                                     end_type='max', end_color='9DD3C6'))
    autofit(ws, 5)

    # ---------------- 04 园区清单 ----------------
    ws = wb.create_sheet('04 园区清单')
    sheet_base(ws, '园区 / 集聚区清单', sub + ' ｜ 扫园时按「园区 → 目标企业 → 门卫/园区管委会」顺序推进', 8)
    hdr = ['省', '城市', '园区 / 集聚区', '主导产业', '园内潜在家数', '代表企业', '城市等级', '扫园建议']
    header_row(ws, 4, hdr, [7, 14, 34, 26, 13, 40, 9, 56])
    r = 5
    for c in cities:
        for p in c['parks']:
            n = p.get('n') or 0
            if n >= 25:
                adv = '一天可跑完：先管委会拿企业名录，再按名录逐家拜访'
            elif n >= 10:
                adv = '半天：优先园内 3–5 家头部，其余留到第二轮'
            else:
                adv = '顺访：与邻园并线，不必专程'
            body(ws, r, [c['prov'], c['city'], p['name'], p.get('ind', ''), n,
                         p.get('firms', ''), c['tier'], adv],
                 ['left', 'left', 'left', 'left', 'center', 'left', 'center', 'left'], zebra=(r % 2 == 0))
            tf, tc = TIER_FILL[c['tier']]
            cell = ws.cell(row=r, column=7)
            cell.fill = PatternFill('solid', fgColor=tf)
            cell.font = Font(name=FONT, size=9.5, bold=True, color=tc)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            r += 1
    ws.auto_filter.ref = 'A4:H%d' % (r - 1)
    ws.freeze_panes = 'C5'
    autofit(ws, 5)

    # ---------------- 05 客户线索 ----------------
    ws = wb.create_sheet('05 客户线索')
    sheet_base(ws, '客户线索（具名样本，含同行与误判对照）',
               sub + ' ｜ 置信度：高=公告/年报/交易所/政府/协会可查；中=主体可查、用量为推算；低=主体未核实', 13)
    hdr = ['企业', '类型', '置信度', '省', '城市', '园区', '下游方向', '规模 / 定位',
           '年%s' % DL, '需求点（用什么、对什么敏感）', '对接部门', '首访动作', '证据来源']
    header_row(ws, 4, hdr, [30, 7, 7, 7, 13, 22, 14, 26, 11, 44, 12, 34, 40])
    order = {'生产': 0, '贸易': 1, '同行': 2, '误判': 3}
    conf_o = {'高': 0, '中': 1, '低': 2}
    r = 5
    for x in sorted(cos, key=lambda z: (order.get(z['type'], 9), conf_o.get(z['conf'], 9), -(z.get('kt') or 0))):
        body(ws, r, [x['name'], x['type'], x['conf'], x.get('prov', ''), x.get('city', ''),
                     x.get('park', ''), lanes.get(x.get('lane', ''), {}).get('name', '—'),
                     x.get('scale', ''), (x['kt'] if x.get('kt') is not None else '—'),
                     x.get('need', ''), x.get('who', ''), x.get('action', ''), x.get('src', '')],
             ['left', 'center', 'center', 'left', 'left', 'left', 'left', 'left',
              'right', 'left', 'left', 'left', 'left'], zebra=(r % 2 == 0))
        f1, c1 = TYPE_FILL.get(x['type'], ('F4F5F7', '5F6B7A'))
        f2, c2 = CONF_FILL.get(x['conf'], ('F4F5F7', '68738A'))
        for col, (f, cc) in ((2, (f1, c1)), (3, (f2, c2))):
            cell = ws.cell(row=r, column=col)
            cell.fill = PatternFill('solid', fgColor=f)
            cell.font = Font(name=FONT, size=9.5, bold=True, color=cc)
            cell.alignment = Alignment(horizontal='center', vertical='center')
        if isinstance(x.get('kt'), (int, float)):
            cell = ws.cell(row=r, column=9)
            cell.font = Font(name=FONT, size=9.5, bold=True, color=INK)
        r += 1
    ws.auto_filter.ref = 'A4:M%d' % (r - 1)
    ws.freeze_panes = 'B5'
    ws.conditional_formatting.add('I5:I%d' % (r - 1),
                                  ColorScaleRule(start_type='min', start_color='FFFFFF',
                                                 end_type='max', end_color='9DD3C6'))
    autofit(ws, 5)

    # ---------------- 06 中小集群 ----------------
    ws = wb.create_sheet('06 中小集群')
    sheet_base(ws, '中小企业集群（无法具名，但必须覆盖的客户池）',
               sub + ' ｜ 集群按「园区内家数」聚合；单家名字拿不到时，用数量口径 + 扫园替代', 7)
    hdr = ['城市', '园区 / 集聚区', '集群类型', '估算家数', '年%s合计' % DL, '城市等级', '打法']
    header_row(ws, 4, hdr, [14, 34, 26, 11, 13, 9, 66])
    r = 5
    groups = []
    for c in cities:
        for p in c['parks']:
            if (p.get('n') or 0) >= 8:
                groups.append((c, p))
    groups.sort(key=lambda g: -(g[1].get('n') or 0))
    for c, p in groups:
        share = (p.get('n') or 0) / c['firms'] if c['firms'] else 0
        kt = round(c['demand'] * share, 1)
        body(ws, r, [c['city'], p['name'], p.get('ind', ''), p.get('n'),
                     kt, c['tier'], N.get('cluster_advice', '先园区管委会拿名录，再按名录分组拜访')],
             ['left', 'left', 'left', 'center', 'right', 'center', 'left'], zebra=(r % 2 == 0))
        tf, tc = TIER_FILL[c['tier']]
        cell = ws.cell(row=r, column=6)
        cell.fill = PatternFill('solid', fgColor=tf)
        cell.font = Font(name=FONT, size=9.5, bold=True, color=tc)
        cell.alignment = Alignment(horizontal='center', vertical='center')
        r += 1
    ws.auto_filter.ref = 'A4:G%d' % (r - 1)
    ws.freeze_panes = 'C5'
    autofit(ws, 5)

    # ---------------- 07 重点项目 ----------------
    ws = wb.create_sheet('07 重点项目')
    sheet_base(ws, '新建 / 扩产 / 减产项目',
               sub + ' ｜ 正增量=新增需求，负增量=冷修/限产；两者都要看，否则会高估增量', 16)
    hdr = ['ID', '企业', '项目', '省', '城市', '类型', '产品', '规模', '投资', '状态',
           '开工', '投产/达产', '需求增量', '商用含义与接触时点', '置信度', '来源']
    header_row(ws, 4, hdr, [6, 22, 30, 7, 14, 12, 12, 16, 11, 18, 9, 13, 11, 52, 7, 34])
    r = 5
    for p in sorted(projs, key=lambda z: -(z.get('kt') or 0)):
        body(ws, r, [p.get('id'), p.get('co'), p.get('name'), p.get('prov'), p.get('city'),
                     p.get('type'), p.get('prod'), p.get('cap'), p.get('invest'), p.get('status'),
                     p.get('start'), p.get('ramp'),
                     ('+%s' % p['kt']) if (p.get('kt') or 0) > 0 else (p.get('kt') if p.get('kt') else '—'),
                     p.get('impact'), p.get('conf'), p.get('src')],
             ['center', 'left', 'left', 'left', 'left', 'center', 'left', 'left', 'left', 'left',
              'center', 'center', 'right', 'left', 'center', 'left'], zebra=(r % 2 == 0))
        kt = p.get('kt') or 0
        cell = ws.cell(row=r, column=13)
        cell.font = Font(name=FONT, size=9.5, bold=True, color='0F766E' if kt > 0 else ('A02C2C' if kt < 0 else '8492A6'))
        f2, c2 = CONF_FILL.get(p.get('conf'), ('F4F5F7', '68738A'))
        cell = ws.cell(row=r, column=15)
        cell.fill = PatternFill('solid', fgColor=f2)
        cell.font = Font(name=FONT, size=9.5, bold=True, color=c2)
        cell.alignment = Alignment(horizontal='center', vertical='center')
        r += 1
    ws.auto_filter.ref = 'A4:P%d' % (r - 1)
    ws.freeze_panes = 'C5'
    autofit(ws, 5)

    # ---------------- 08 价格对比 ----------------
    ws = wb.create_sheet('08 价格对比')
    sheet_base(ws, '价格水平与区域差异',
               sub + ' ｜ 锚点：%s %s %s（%s）；价差需换算成到厂价再比' % (
                   A.get('label', ''), A.get('value', ''), A.get('unit', ''), A.get('date', '')), 6)
    P = D.get('prices') or {}
    header_row(ws, 4, ['区域', '主流价（元/吨）', '与锚点价差', '价差原因', '', ''], [14, 15, 13, 70, 4, 4])
    r = 5
    base = A.get('value') or 0
    for pr in P.get('regions', []):
        diff = pr['v'] - base
        body(ws, r, [pr['name'], pr['v'], ('%+d' % diff) if diff else '—', pr.get('why', ''), '', ''],
             ['left', 'right', 'right', 'left', 'left', 'left'], zebra=(r % 2 == 0))
        if diff:
            cell = ws.cell(row=r, column=3)
            cell.font = Font(name=FONT, size=9.5, bold=True, color='A02C2C' if diff > 0 else '0F766E')
        r += 1
    r += 1
    r = note_block(ws, r, P.get('notes') or [], 6, '价格注释')
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws.cell(row=r, column=1, value='区域内部到厂价差异（以锚点为基准）')
    c.font = Font(name=FONT, size=11, bold=True, color=TEAL)
    r += 1
    header_row(ws, r, ['区域 / 城市', '到厂价区间（元/吨）', '议价空间', '原因与报价建议', '', ''], [16, 18, 11, 66, 4, 4])
    r += 1
    for it in P.get('internal', []):
        body(ws, r, [it['name'], it.get('range', ''), it.get('room', '—'),
                     (it.get('why', '') + ('　→ ' + it.get('advice', '') if it.get('advice') else '')), '', ''],
             ['left', 'left', 'center', 'left', 'left', 'left'], zebra=(r % 2 == 0))
        r += 1
    autofit(ws, 5)

    # ---------------- 09 走访计划 ----------------
    ws = wb.create_sheet('09 走访计划')
    S_cities = [c for c in cities if c['tier'] == 'S']
    A_cities = [c for c in cities if c['tier'] == 'A'][:8]
    days_s = sum(c['days'] for c in S_cities)
    days_a = sum(c['days'] for c in A_cities)
    sheet_base(ws, '走访优先级与路线',
               sub + ' ｜ 天数按每日 4 家测算（含园区内转场），跨城另计 0.5 天/次', 7)
    r = 4
    r = note_block(ws, r, [
        'S 级 %d 城合计 %d 天；A 级前 %d 城 %d 天。首轮建议只打 S 级的重点园区，按周分块，'
        '每次回程前把「已见、待见、需技术支援」三张清单交回。' % (len(S_cities), days_s, len(A_cities), days_a),
    ], 7)
    r += 1
    header_row(ws, r, ['优先级', '城市', '省', '生产企业家数', '单客户均值', '%s' % DL, '建议天数', '为什么先打这里'],
               [9, 14, 7, 13, 12, 11, 9, 74])
    r += 1
    for c in S_cities:
        body(ws, r, ['S%d' % c['rank'], c['city'], c['prov'], c['firms'], c['avg'], c['demand'],
                     c['days'], c.get('note', '')],
             ['center', 'left', 'left', 'right', 'right', 'right', 'center', 'left'], zebra=(r % 2 == 0))
        tf, tc = TIER_FILL['S']
        cell = ws.cell(row=r, column=1)
        cell.fill = PatternFill('solid', fgColor=tf)
        cell.font = Font(name=FONT, size=9.5, bold=True, color=tc)
        cell.alignment = Alignment(horizontal='center', vertical='center')
        r += 1
    for c in A_cities:
        body(ws, r, ['A', c['city'], c['prov'], c['firms'], c['avg'], c['demand'],
                     c['days'], c.get('note', '')],
             ['center', 'left', 'left', 'right', 'right', 'right', 'center', 'left'], zebra=(r % 2 == 0))
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    c = ws.cell(row=r, column=1, value='周计划（按地理串联，减少折返）')
    c.font = Font(name=FONT, size=11, bold=True, color=TEAL)
    r += 1
    header_row(ws, r, ['周次', '驻点', '路线', '重点客群', '这一周要拿到什么', '', ''], [8, 14, 34, 26, 60, 4, 4])
    r += 1
    for rt in D['route']:
        body(ws, r, [rt.get('week'), rt.get('base'), rt.get('seq'), rt.get('focus'), rt.get('why'), '', ''],
             ['center', 'left', 'left', 'left', 'left', 'left', 'left'], zebra=(r % 2 == 0))
        r += 1
    autofit(ws, 5)

    # ---------------- 10 下游行业 ----------------
    ws = wb.create_sheet('10 下游行业')
    sheet_base(ws, '下游行业结构', sub + ' ｜ 星级=单客户用量强度（5★ 千吨级以上/家）；占比为全国消费结构参考', 8)
    hdr = ['下游方向', '全国占比 %', '单耗', '强度', '用料逻辑', '对接部门', '切入话术', '常见误判']
    header_row(ws, 4, hdr, [16, 10, 20, 8, 56, 14, 40, 34])
    r = 5
    for l in D['lanes']:
        body(ws, r, [l['name'], l.get('share', ''), l.get('unit_txt', ''),
                     '★' * l['intensity'], l.get('logic', ''), l.get('who', ''),
                     l.get('hook', ''), l.get('misread', '')],
             ['left', 'center', 'left', 'center', 'left', 'left', 'left', 'left'], zebra=(r % 2 == 0))
        r += 1
    ws.auto_filter.ref = 'A4:H%d' % (r - 1)
    ws.freeze_panes = 'B5'
    pie = PieChart()
    pie.title = '区域%s下游结构' % DL
    pie.height, pie.width = 8, 11
    pie.add_data(Reference(ws, min_col=2, min_row=4, max_row=r - 1), titles_from_data=True)
    pie.set_categories(Reference(ws, min_col=1, min_row=5, max_row=r - 1))
    ws.add_chart(pie, 'J4')
    autofit(ws, 5)

    # ---------------- 11 同行与误判 ----------------
    ws = wb.create_sheet('11 同行与误判')
    peers = [x for x in cos if x['type'] == '同行']
    wrong = [x for x in cos if x['type'] == '误判']
    sheet_base(ws, '同行与误判：谁不是客户',
               sub + ' ｜ 同行自己也生产这个产品，价值在价格与情报；误判是「看起来像客户」的下游', 6)
    r = 4
    r = note_block(ws, r, N.get('peer_notes') or ['（未填写同行说明）'], 6, '一、同行（不产生销量）')
    r += 1
    if peers:
        header_row(ws, r, ['企业', '城市', '产能/定位', '对本品的含义', '', ''], [28, 14, 24, 66, 4, 4])
        r += 1
        for x in peers:
            body(ws, r, [x['name'], x.get('city', ''), x.get('scale', ''),
                         x.get('need', '') or x.get('action', ''), '', ''],
                 ['left', 'left', 'left', 'left', 'left', 'left'], zebra=(r % 2 == 0))
            r += 1
    r += 1
    r = note_block(ws, r, [N.get('misread_notes') or '（未填写误判说明）'], 6, '二、误判对照（下游但不消耗本品）')
    r += 1
    if wrong:
        header_row(ws, r, ['企业/类型', '城市', '为什么看起来像', '实际用什么', '', ''], [28, 14, 40, 40, 4, 4])
        r += 1
        for x in wrong:
            body(ws, r, [x['name'], x.get('city', ''), x.get('scale', ''), x.get('need', ''), '', ''],
                 ['left', 'left', 'left', 'left', 'left', 'left'], zebra=(r % 2 == 0))
            r += 1
    autofit(ws, 5)

    # ---------------- 12 方法与缺口 ----------------
    ws = wb.create_sheet('12 方法与缺口')
    sheet_base(ws, '口径、证据与已知缺口', sub, 6)
    r = 4
    r = note_block(ws, r, ['%s：%s' % (b['k'], b['v']) for b in (N.get('method') or [])], 6, '一、口径')
    r += 1
    r = note_block(ws, r, [
        '置信度分级：高 = 主体、产品、用量/产能均有公开来源可查（公告、年报、交易所问询、政府环评/备案、行业协会、价格机构）；'
        '中 = 主体可查但用量为按产能与单耗推算；低 = 主体未核实或来源为二手转述，拜访前必须先电话确认。'
    ], 6, '二、置信度怎么读')
    r += 1
    r = note_block(ws, r, N.get('gaps') or ['（未填写缺口）'], 6, '三、已知缺口与负结果')
    r += 1
    low = [x['name'] for x in cos if x['conf'] == '低']
    r = note_block(ws, r, [
        '本工作簿所有企业家数、需求量均为估算值，用于排序与配车配人，不可作为统计口径对外引用。',
        '若用于正式报价或授信，请以客户提供的月采购量、合同价与账期为准。',
        '低置信条目：%s' % ('、'.join(low) if low else '无'),
    ], 6, '四、使用边界')
    autofit(ws, 5)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    print('OK %s  %d sheets' % (out_path, len(wb.sheetnames)))
    return out_path


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'data.json',
          sys.argv[2] if len(sys.argv) > 2 else 'out/market.xlsx')
