# -*- coding: utf-8 -*-
"""make_xlsx.py — 生成结构化 Excel 工作簿（品种池 / 现货期货 / 历史基差 / 分位 / 排名 / 状态 / 来源）

工作簿结构（13 个 sheet）
-------------------------
01_说明与口径        扫描口径、公式、边界与免责
02_极端排行榜        按品种内分位排序的榜单（含公式列：分位变化）
03_历史分位分布      每品种的 10 档分布 + 当前所处档位
04_数据覆盖核验      样本长度、有效日期、合约映射、交叉校验通过率
05_品种池            12 品种 + 排除品种及原因
06_现货期货快照      最新交易日：现货、期货、合约、基差
07_基差月表          每个品种的月度基差（末值/均值/样本数）
08_日度基差明细      全部日度基差（长表）
09_近1月变化         近一月基差与分位变化
10_极端品种聚焦      极端品种的口径、极值、换月披露、库存与事件
11_无法扫描品种      数据不足/口径不可比清单及原因
12_数据来源          逐条 URL 与抓取时间、指纹
13_口径字典          字段字典
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference, LineChart
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule

NAVY = '1F3864'
BLUE = '2E5C8A'
LIGHT = 'DCE6F1'
LIGHT2 = 'EEF3FA'
GREEN = 'C6EFCE'
RED = 'FFC7CE'
AMBER = 'FFEB9C'
GREY = 'F2F2F2'
THIN = Side(style='thin', color='BFBFBF')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _hdr(ws, row, values, widths=None, fill=NAVY):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(bold=True, color='FFFFFF', size=10.5, name='微软雅黑')
        c.fill = PatternFill('solid', fgColor=fill)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def _title(ws, text, sub='', ncol=8):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(bold=True, size=15, color='FFFFFF', name='微软雅黑')
    c.fill = PatternFill('solid', fgColor=NAVY)
    c.alignment = Alignment(horizontal='left', vertical='center', indent=1)
    ws.row_dimensions[1].height = 30
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = Font(size=9.5, color='404040', name='微软雅黑')
        c2.fill = PatternFill('solid', fgColor=LIGHT)
        c2.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True, indent=1)
        ws.row_dimensions[2].height = 30


def _flag_fill(flag):
    return {'低位极端': GREEN, '高位极端': RED, '常态': None}.get(flag)


def sheet_cover(wb, meta):
    ws = wb.create_sheet('01_说明与口径')
    _title(ws, '化工期货 · 极端基差扫描工作簿', '扫描口径、公式与边界 —— 所有数字均可按「数据来源」页 URL 复现', 6)
    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['B'].width = 110
    rows = [
        ('生成时间', meta['generated_at']),
        ('工具版本', 'basis_scan v%s' % meta['version']),
        ('品种池', '、'.join(meta['codes']) + '（共 %d 个）' % meta['pool_size']),
        ('可扫描品种', '%d 个' % meta['n_ok']),
        ('极端品种', '%d 个（阈值 ±%.0f%%）' % (meta['n_extreme'], meta['threshold'] * 100)),
        ('数据不足/不可比', '%d 个（详见 11_无法扫描品种）' % meta['n_insufficient']),
        ('历史窗口', '%d 年（以各品种数据最新可用日向前推）' % meta['window_years']),
        ('极端阈值', '±%.0f%%（低端 ≤ %.0f%% 分位，高端 ≥ %.0f%% 分位）' % (
            meta['threshold'] * 100, meta['threshold'] * 100, 100 - meta['threshold'] * 100)),
        ('最小样本要求', '%d 个有效交易日' % meta['min_obs']),
        ('近一月', '向前 %d 个有效交易日' % meta['change_window']),
        ('连续规则', meta['roll_rule']),
        ('基差定义', meta['basis_convention']),
        ('分位定义', meta['percentile_convention']),
        ('数据截至', meta['data_latest']),
    ]
    for i, (k, v) in enumerate(rows, start=4):
        a = ws.cell(row=i, column=1, value=k)
        a.font = Font(bold=True, size=10.5, name='微软雅黑')
        a.fill = PatternFill('solid', fgColor=LIGHT2)
        a.border = BORDER
        b = ws.cell(row=i, column=2, value=v)
        b.font = Font(size=10.5, name='微软雅黑')
        b.alignment = Alignment(wrap_text=True, vertical='center')
        b.border = BORDER
    r = len(rows) + 6
    notes = [
        '【重要边界·样本长度】' + (meta.get('sample_note', '') + meta.get('sample_warning', '') or
                             '见 04 页逐品种样本数。'),
        '【口径红线】1) 基差 = 现货基准价 − 期货收盘价，严格此符号；2) 分位只在「品种自身」历史分布内计算，'
        '不同产品的基差金额绝不可横向比较；3) 不做任何插值/前值填充，期货缺该交易日即不出基差。',
        '【增值税口径】现货为含税基准价、期货为不含税价，二者相减天然包含 13% 增值税项，'
        '因此高低绝对值不能与"无税基差"经验值直接对照，只看自身历史分位。',
        '【换月披露】主力连续在换月日存在价格跳空，会放大当日基差变化；窗口内换月次数与跳变已在 10 页披露，未做修正。',
        '【免责】分位只是历史位置描述，不构成多空信号；本表不提供任何交易建议。',
        '【可复现】数据指纹（SHA-256 前 16 位）记录在 04 页与 12 页，重抓后可核对。',
    ]
    for n in notes:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = ws.cell(row=r, column=1, value=n)
        c.font = Font(size=10, name='微软雅黑', color='7F3F00')
        c.fill = PatternFill('solid', fgColor='FFF4E5')
        c.alignment = Alignment(wrap_text=True, vertical='center', indent=1)
        ws.row_dimensions[r].height = 34
        r += 1


def sheet_ranking(wb, results, meta):
    ws = wb.create_sheet('02_极端排行榜')
    _title(ws, '极端基差排行榜（按品种自身历史分位排序）',
           '排序只用分位、不用基差金额；低位极端在前，其次高位极端，再常态。基差金额不可跨品种比较。', 14)
    cols = ['排名', '品种', '代码', '状态', '判定', '历史分位(%)', '中位秩分位(%)', '严格分位(%)',
            '当前基差(元/吨)', '基差占现货(%)', '近一月基差变化', '分位变化(pct)', '期货合约', '窗口样本数']
    _hdr(ws, 4, cols, [7, 12, 7, 10, 11, 12, 13, 12, 15, 13, 14, 13, 11, 11])
    r = 5
    for x in results:
        if x.get('status') != 'OK':
            continue
        vals = [x.get('rank', ''), x['name'], x['code'], '可扫描', x.get('flag', ''),
                x.get('pct_used', ''), x.get('pct_midrank', ''), x.get('pct_strict', ''),
                x.get('basis_yuan', ''), x.get('basis_pct_spot', ''), x.get('chg_1m', ''),
                x.get('pct_delta_1m', ''), x.get('current_contract', ''), x.get('n_obs', '')]
        for i, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=10, name='微软雅黑')
            if i in (1, 3, 6, 7, 8, 9, 10, 11, 12, 13, 14):
                c.alignment = Alignment(horizontal='center')
            if i in (6, 7, 8, 9, 10, 11, 12):
                c.number_format = '0.00'
        f = _flag_fill(x.get('flag'))
        if f:
            ws.cell(row=r, column=5).fill = PatternFill('solid', fgColor=f)
        r += 1
    n = r - 1
    # 条件格式：分位列色阶 + 数据条
    if n >= 5:
        ws.conditional_formatting.add('F5:F%d' % n, ColorScaleRule(
            start_type='num', start_value=0, start_color='63BE7B',
            mid_type='num', mid_value=50, mid_color='FFEB9C',
            end_type='num', end_value=100, end_color='F8696B'))
        ws.conditional_formatting.add('I5:I%d' % n, DataBarRule(start_type='min', end_type='max',
                                                                color='5B8CFF'))
    ws.freeze_panes = 'A5'
    # 小图
    ch = BarChart()
    ch.type = 'bar'
    ch.title = '历史分位（%）'
    ch.y_axis.title = '品种'
    ch.height, ch.width = 9, 14
    data = Reference(ws, min_col=6, min_row=4, max_row=n)
    cats = Reference(ws, min_col=2, min_row=5, max_row=n)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    ws.add_chart(ch, 'A%d' % (n + 3))


def sheet_distribution(wb, results):
    ws = wb.create_sheet('03_历史分位分布')
    _title(ws, '历史分位分布（每品种在自身历史中的位置）',
           '百分比 = 历史窗口内小于该日基差的天数占比；当前档位由 10% 分档得到。', 15)
    cols = ['品种', '代码', '当前分位(%)', '所处档位', 'P10', 'P25', 'P50', 'P75', 'P90',
            '均值', '标准差', '历史最低', '历史最高', '偏低/偏高', '样本数']
    _hdr(ws, 4, cols, [12, 7, 12, 12, 10, 10, 10, 10, 10, 10, 10, 11, 11, 12, 9])
    r = 5
    for x in results:
        if x.get('status') != 'OK':
            continue
        vals = [x['name'], x['code'], x.get('pct_used', ''), x.get('bucket', ''), x.get('q10', ''),
                x.get('q25', ''), x.get('q50', ''), x.get('q75', ''), x.get('q90', ''),
                x.get('mean', ''), x.get('std', ''), x.get('hist_min', ''), x.get('hist_max', ''),
                ('偏低' if float(x.get('pct_used', 50) or 50) < 50 else '偏高'), x.get('n_obs', '')]
        for i, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=10, name='微软雅黑')
            if i >= 3:
                c.number_format = '0.00'
                c.alignment = Alignment(horizontal='center')
        r += 1
    n = r - 1
    if n >= 5:
        ws.conditional_formatting.add('C5:C%d' % n, ColorScaleRule(
            start_type='num', start_value=0, start_color='63BE7B', mid_type='num', mid_value=50,
            mid_color='FFEB9C', end_type='num', end_value=100, end_color='F8696B'))
    ws.freeze_panes = 'C5'


def sheet_coverage(wb, cov, seen):
    ws = wb.create_sheet('04_数据覆盖核验')
    _title(ws, '数据覆盖核验（保证"不是只扫有结果的少数品种"）',
           '品种池全部列出；样本长度、有效日期、合约映射、交叉校验全部透明。', 14)
    cols = ['品种', '代码', '状态', '窗口样本数', '窗口起', '窗口止', '全序列天数',
            '现货起点', '现货终点', '期货起点', '期货终点', '当日合约映射',
            '交叉校验(我方=源站基差)通过率', '校验样本数']
    _hdr(ws, 4, cols, [12, 7, 11, 11, 12, 12, 11, 12, 12, 12, 12, 13, 22, 11])
    r = 5
    for c in cov:
        vals = [c.get('name', ''), c.get('code', ''), c.get('status', ''), c.get('n_obs', ''),
                c.get('window_start', ''), c.get('window_end', ''), c.get('matched', ''),
                c.get('spot_first', ''), c.get('spot_last', ''), c.get('fut_first', ''),
                c.get('fut_last', ''), c.get('current_contract', c.get('bucket', '')),
                (str(c.get('xcheck_rate')) + '%') if c.get('xcheck_rate') is not None else '—',
                c.get('xcheck_n', '')]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BORDER
            cell.font = Font(size=10, name='微软雅黑')
            if i >= 4:
                cell.alignment = Alignment(horizontal='center')
        if c.get('status') != 'OK':
            ws.cell(row=r, column=3).fill = PatternFill('solid', fgColor=AMBER)
        else:
            ws.cell(row=r, column=3).fill = PatternFill('solid', fgColor=GREEN)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='数据指纹（SHA-256 前16位）').font = Font(bold=True, size=10, name='微软雅黑')
    r += 1
    _hdr(ws, r, ['品种', '现货文件', '指纹', '期货文件', '指纹'], [12, 40, 20, 40, 20], fill=BLUE)
    r += 1
    for c in cov:
        for i, v in enumerate([c.get('code', ''), c.get('spot_file', ''), c.get('sha_spot', ''),
                               c.get('fut_file', ''), c.get('sha_fut', '')], 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BORDER
            cell.font = Font(size=9.5, name='Consolas')
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=14)
    cc = ws.cell(row=r, column=1, value='交叉校验口径：用生意社基差稿正文自带的三行公式（现货基准价、期货主力收盘价、基差），'
                                        '与「我方独立计算的 现货−期货」逐日比对，差值 ≤0.05 元/吨 记为一致。')
    cc.font = Font(size=9.5, name='微软雅黑', italic=True, color='595959')
    cc.alignment = Alignment(wrap_text=True, vertical='center')
    ws.row_dimensions[r].height = 28
    ws.freeze_panes = 'C5'


def sheet_pool(wb, pool, excluded):
    ws = wb.create_sheet('05_品种池')
    _title(ws, '品种池定义（逐品种现货基准与合约规则）',
           '现货基准、规格、地区、税基、交割品级、合约乘数、最后交易日规则全部显式声明。', 14)
    cols = ['品种', '代码', '交易所', '现货规格', '现货地区/口径', '现货税基', '交割品级',
            '交割区域', '单位', '合约乘数', '最小变动', '最后交易日规则', '生意社商品ID', '口径备注']
    _hdr(ws, 4, cols, [10, 7, 9, 22, 20, 9, 26, 26, 8, 9, 9, 30, 12, 52])
    r = 5
    for p in pool:
        vals = [p.get('name'), p.get('code'), p.get('exchange'), p.get('spot_spec'),
                p.get('spot_region'), p.get('spot_tax'), p.get('contract_spec'),
                p.get('futures_region'), p.get('unit'), p.get('multiplier'), p.get('tick'),
                p.get('last_trade_rule'), p.get('ppid'), p.get('note')]
        for i, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=9.5, name='微软雅黑')
            c.alignment = Alignment(wrap_text=True, vertical='top',
                                    horizontal='center' if i in (2, 3, 6, 9, 10, 11, 13) else 'left')
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='池内但按设计不予扫描的品种').font = Font(bold=True, size=11, color='C00000', name='微软雅黑')
    r += 1
    _hdr(ws, r, ['品种', '代码', '不纳入原因'], [10, 7, 90], fill=BLUE)
    r += 1
    for e in excluded:
        for i, v in enumerate([e['name'], e['code'], e['reason']], 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=9.5, name='微软雅黑')
            c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=8)
        r += 1
    ws.freeze_panes = 'C5'


def sheet_snapshot(wb, results):
    ws = wb.create_sheet('06_现货期货快照')
    _title(ws, '最新交易日现货 / 期货 / 基差快照',
           '所有价格带交易日期；现货为生意社基准价（含税），期货为当日主力合约收盘价。', 12)
    cols = ['品种', '代码', '交易日', '现货基准价', '期货收盘价', '基差(现货−期货)',
            '基差/现货(%)', '期货合约', '连续规则', '现货文章类型', '单位', '备注']
    _hdr(ws, 4, cols, [10, 7, 12, 13, 13, 16, 12, 11, 30, 14, 8, 40])
    r = 5
    for x in results:
        if x.get('status') != 'OK':
            continue
        vals = [x['name'], x['code'], x.get('date', ''), x.get('spot', ''), x.get('fut', ''),
                x.get('basis_yuan', ''), x.get('basis_pct_spot', ''), x.get('current_contract', ''),
                x.get('roll_rule', ''), '生意社基差稿(含现货基准价)', x.get('unit', '元/吨'),
                (x.get('spot_spec') or '') + '；' + (x.get('spot_region') or '')]
        for i, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=10, name='微软雅黑')
            if i in (4, 5, 6):
                c.number_format = '#,##0.00'
                c.alignment = Alignment(horizontal='right')
            elif i == 7:
                c.number_format = '0.00"%"'
                c.alignment = Alignment(horizontal='right')
            else:
                c.alignment = Alignment(wrap_text=True, vertical='center',
                                        horizontal='center' if i in (2, 3, 8, 10, 11) else 'left')
        r += 1
    ws.freeze_panes = 'C5'


def sheet_monthly(wb, details, results):
    ws = wb.create_sheet('07_基差月表')
    _title(ws, '月度基差（末值 / 均值 / 样本数）', '按自然月聚合；末值用于观察趋势，均值用于平滑。', 7)
    cols = ['品种', '代码', '月份', '样本数', '月内均值', '月末基差', '月末现货']
    _hdr(ws, 4, cols, [12, 7, 10, 8, 12, 12, 12])
    r = 5
    for x in results:
        if x.get('status') != 'OK':
            continue
        for m in (details.get(x['code'], {}) or {}).get('monthly', []):
            for i, v in enumerate([x['name'], x['code'], m['month'], m['n'], m['basis_mean'],
                                   m['basis_last'], m['spot_last']], 1):
                c = ws.cell(row=r, column=i, value=v)
                c.border = BORDER
                c.font = Font(size=9.5, name='微软雅黑')
                if i in (4,):
                    c.alignment = Alignment(horizontal='center')
                if i >= 5:
                    c.number_format = '#,##0.00'
            r += 1
    ws.freeze_panes = 'D5'
    ws.auto_filter.ref = 'A4:G%d' % (r - 1)


def sheet_daily(wb, details, results):
    ws = wb.create_sheet('08_日度基差明细')
    _title(ws, '日度基差明细（长表）', '每日一行：现货、期货、基差、当日对应合约、是否换月日。可直接透视/筛选。', 8)
    cols = ['品种', '代码', '交易日', '现货', '期货', '基差', '当日合约', '换月日']
    _hdr(ws, 4, cols, [10, 7, 12, 11, 11, 11, 11, 9])
    r = 5
    for x in results:
        if x.get('status') != 'OK':
            continue
        for d in (details.get(x['code'], {}) or {}).get('daily', []):
            for i, v in enumerate([x['name'], x['code'], d['date'], d['spot'], d['fut'],
                                   d['basis'], d['symbol'], '是' if d['is_roll'] else ''], 1):
                c = ws.cell(row=r, column=i, value=v)
                c.font = Font(size=9, name='微软雅黑')
                if i in (4, 5, 6):
                    c.number_format = '#,##0.00'
                if i in (2, 7, 8):
                    c.alignment = Alignment(horizontal='center')
            r += 1
    ws.freeze_panes = 'D5'
    ws.auto_filter.ref = 'A4:H%d' % (r - 1)


def sheet_change(wb, results):
    ws = wb.create_sheet('09_近1月变化')
    _title(ws, '近一月基差变化（现货 vs 期货分解）',
           '近一月 = 向前 21 个有效交易日；同时给出分位变化，判断"位置"是否移动。', 11)
    cols = ['品种', '代码', '基准日', '当前基差', '一月前基差', '基差变化', '当前分位(%)',
            '一月前分位(%)', '分位变化(pct)', '现货变化', '期货变化']
    _hdr(ws, 4, cols, [10, 7, 12, 11, 12, 11, 12, 13, 13, 11, 11])
    r = 5
    for x in results:
        if x.get('status') != 'OK':
            continue
        vals = [x['name'], x['code'], x.get('chg_1m_date', ''), x.get('basis_yuan', ''),
                x.get('basis_1m_ago', ''), x.get('chg_1m', ''), x.get('pct_used', ''),
                x.get('pct_1m_ago', ''), x.get('pct_delta_1m', ''), x.get('spot_chg_1m', ''),
                x.get('fut_chg_1m', '')]
        for i, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=10, name='微软雅黑')
            if i >= 4:
                c.number_format = '#,##0.00'
                c.alignment = Alignment(horizontal='right')
        for col in (6, 9, 10, 11):
            vv = ws.cell(row=r, column=col).value
            if isinstance(vv, (int, float)):
                ws.cell(row=r, column=col).font = Font(size=10, name='微软雅黑',
                                                       color='C00000' if vv > 0 else '00703C')
        r += 1
    n = r - 1
    if n >= 5:
        ws.conditional_formatting.add('F5:F%d' % n, ColorScaleRule(
            start_type='num', start_value=-500, start_color='63BE7B', mid_type='num', mid_value=0,
            mid_color='FFFFFF', end_type='num', end_value=500, end_color='F8696B'))
    ws.freeze_panes = 'C5'


def sheet_focus(wb, results, fund):
    ws = wb.create_sheet('10_极端品种聚焦')
    _title(ws, '极端品种聚焦（补充可获取的库存 / 仓单 / 供需变化）',
           '仅补充"实际取到"的数据；取不到即写「未获取」并说明原因，不做推测。', 9)
    cols = ['品种', '代码', '判定', '分位(%)', '当前基差', '历史极值区间', '换月跳变告警',
            '库存/仓单状态', '可获取的产业事件(近期)']
    _hdr(ws, 4, cols, [10, 7, 11, 9, 11, 22, 30, 26, 62])
    r = 5
    for x in results:
        if x.get('status') != 'OK' or not x.get('extreme'):
            continue
        f = (fund or {}).get(x['code'], {})
        evs = ' ∥ '.join('%s %s' % (e['date'], e['title']) for e in (f.get('events') or [])[:5]) or '未获取到检修/投产/库存类稿件'
        big = x.get('roll_jumps_big') or []
        rolltxt = ('；'.join('%s %s→%s 跳%s' % (b['date'], b['from_symbol'], b['to_symbol'], b['jump'])
                            for b in big[:3]) or '窗口内无≥30元/吨的换月跳变')
        vals = [x['name'], x['code'], x.get('flag', ''), x.get('pct_used', ''), x.get('basis_yuan', ''),
                '%s ~ %s' % (x.get('hist_min', ''), x.get('hist_max', '')),
                x.get('roll_count', ''), f.get('inv_status', '未获取'), evs]
        for i, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=9.5, name='微软雅黑')
            c.alignment = Alignment(wrap_text=True, vertical='top',
                                    horizontal='center' if i in (2, 3, 4, 8) else 'left')
            if i == 5:
                c.number_format = '#,##0.00'
        fl = _flag_fill(x.get('flag'))
        if fl:
            ws.cell(row=r, column=3).fill = PatternFill('solid', fgColor=fl)
        if rolltxt and '无' in rolltxt:
            ws.cell(row=r, column=7, value='换月 %s 次；%s' % (x.get('roll_count', 0), rolltxt))
        else:
            ws.cell(row=r, column=7, value='换月 %s 次；%s' % (x.get('roll_count', 0), rolltxt))
        ws.row_dimensions[r].height = 62
        r += 1
    if r == 5:
        ws.cell(row=5, column=1, value='本次扫描未出现极端品种').font = Font(size=10, name='微软雅黑', italic=True)
    ws.freeze_panes = 'C5'


def sheet_excluded(wb, results, excluded):
    ws = wb.create_sheet('11_无法扫描品种')
    _title(ws, '因数据不足 / 口径不一致而无法扫描的品种（必须披露）',
           '把"扫不到的"与"扫得到的"分开写清楚，避免只报有结果的品种。', 6)
    cols = ['品种', '代码', '类别', '原因', '已尝试的来源', '建议']
    _hdr(ws, 4, cols, [12, 8, 16, 60, 40, 40])
    r = 5
    for x in results:
        if x.get('status') == 'OK':
            continue
        reason = x.get('reason') or ''
        cat = '历史窗口样本不足' if '样本' in reason else '数据缺失'
        for i, v in enumerate([x['name'], x['code'], cat, reason,
                               '生意社 100ppi 商品栏目（基准价/基差稿）、新浪逐合约日线',
                               '扩大历史窗口或改用长期订阅数据（隆众/卓创）后再扫'], 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=9.5, name='微软雅黑')
            c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = 44
        r += 1
    for e in excluded:
        for i, v in enumerate([e['name'], e['code'], '口径不一致/无逐日序列', e['reason'],
                               '生意社商品栏目', '换用现货报价源或做单位/税基换算后纳入'], 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=9.5, name='微软雅黑')
            c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = 44
        r += 1


def sheet_sources(wb, results, meta):
    ws = wb.create_sheet('12_数据来源')
    _title(ws, '数据来源（逐条 URL，可用浏览器逐条核验）',
           '现货：生意社 100ppi 逐日文章；期货：新浪财经 InnerFuturesNewService 逐合约日线；抓取时间与指纹见下。', 7)
    cols = ['品种', '代码', '数据类型', '来源/接口', '覆盖区间', '样本数', '核验方式']
    _hdr(ws, 4, cols, [10, 7, 14, 62, 26, 9, 46])
    r = 5
    SOURCES = [
        ('现货基准价', 'https://www.100ppi.com/data/dlist-{ch}--{ppid}-{page}.html 商品栏目；正文含「现货基准价/期货主力合约收盘价」', 60),
        ('期货日线', 'https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/InnerFuturesNewService.getDailyKLine?symbol={prefix}{YYMM}', 60),
    ]
    for x in results:
        if x.get('status') != 'OK':
            continue
        ws.cell(row=r, column=1, value=x['name']).border = BORDER
        ws.cell(row=r, column=2, value=x['code']).border = BORDER
        vals = ['现货+基差稿', '生意社 100ppi 商品栏目 · 逐日「市场基差」稿（正文含现货基准价与期货主力合约）',
                '%s ~ %s' % (x.get('basis_first', ''), x.get('basis_last', '')),
                x.get('n_total_basis_days', ''),
                '与基差稿自带公式逐日比对，通过率 %s%%（n=%s）' % (
                    x.get('xcheck', {}).get('match_rate'), x.get('xcheck', {}).get('checked'))]
        for i, v in enumerate(vals, 3):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=9.5, name='微软雅黑')
            c.alignment = Alignment(wrap_text=True, vertical='top',
                                    horizontal='center' if i >= 6 else 'left')
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    c = ws.cell(row=r, column=1, value='抓取时间：%s　｜　工具版本 v%s　｜　窗口 %d 年　｜　阈值 ±%.0f%%　｜　样本最小 %d' % (
        meta['generated_at'], meta['version'], meta['window_years'], meta['threshold'] * 100,
        meta['min_obs']))
    c.font = Font(size=10, name='微软雅黑', bold=True)
    c.alignment = Alignment(wrap_text=True)
    r += 2
    ws.cell(row=r, column=1, value='字段字典见 13_口径字典；逐日明细见 08_日度基差明细（每行数据均可回查来源文章）。').font = \
        Font(size=9.5, name='微软雅黑', italic=True, color='595959')


def sheet_dict(wb):
    ws = wb.create_sheet('13_口径字典')
    _title(ws, '字段口径字典', '字段名 / 含义 / 计算方式', 3)
    _hdr(ws, 4, ['字段', '含义', '计算方式'], [22, 44, 74])
    rows = [
        ('基差', '现货基准价 − 期货收盘价', 'basis = spot − futures（同日对齐，不插值）'),
        ('历史分位(中位秩)', '该日基差在其自身历史窗口中的位置', '(严格小于数 + 0.5×相等数)/窗口样本数'),
        ('严格分位', '不含相等值的位置', '严格小于数/窗口样本数'),
        ('含当日分位', '经验CDF', '小于等于数/窗口样本数（最小值=0，最大值=1）'),
        ('判定', '极端与否', '中位秩 ≤ 低阈值 → 低位极端；≥ 1−阈值 → 高位极端；否则常态'),
        ('近一月变化', '基差绝对变化', '当前基差 − 21个有效交易日前基差'),
        ('分位变化', '位置变化', '当前分位 − 21个有效交易日前分位'),
        ('换月', '主力合约切换日', '持仓量最大合约发生变化；当日基差跳变≥30元/吨单独告警'),
        ('交叉校验通过率', '独立复算与源站一致性', '|我方基差 − 源站基差稿数值| ≤ 0.05 元/吨 为一致'),
        ('样本不足判定', '不参与排名', '窗口内有效交易日 < 最小样本要求（默认120）'),
    ]
    r = 5
    for row in rows:
        for i, v in enumerate(row, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.font = Font(size=9.5, name='微软雅黑')
            c.alignment = Alignment(wrap_text=True, vertical='top',
                                    horizontal='center' if i == 1 else 'left')
        r += 1


def main(argv=None):
    ap = argparse.ArgumentParser(description='生成 Excel 工作簿')
    ap.add_argument('--result', default='out/scan_result.json')
    ap.add_argument('--fund', default='out/fundamentals.json')
    ap.add_argument('--out', default='out/化工极端基差扫描_数据工作簿.xlsx')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    with open(a.result, encoding='utf-8') as f:
        obj = json.load(f)
    fund = {}
    if os.path.exists(a.fund):
        with open(a.fund, encoding='utf-8') as f:
            fund = json.load(f)
    meta = obj['meta']
    results = obj['results']
    cov = obj['coverage']
    details = obj.get('details', {})
    pool = obj.get('pool', [])
    excluded = obj.get('excluded', [])
    # 排行榜顺序：rank 优先
    results = sorted(results, key=lambda r: (r.get('rank') in ('', None), r.get('rank') or 999))

    wb = Workbook()
    wb.remove(wb.active)
    sheet_cover(wb, meta)
    sheet_ranking(wb, results, meta)
    sheet_distribution(wb, results)
    sheet_coverage(wb, cov, None)
    sheet_pool(wb, pool, excluded)
    sheet_snapshot(wb, results)
    sheet_monthly(wb, details, results)
    sheet_daily(wb, details, results)
    sheet_change(wb, results)
    sheet_focus(wb, results, fund)
    sheet_excluded(wb, results, excluded)
    sheet_sources(wb, results, meta)
    sheet_dict(wb)
    wb.properties.title = '化工极端基差扫描'
    wb.properties.creator = 'basis_scan v%s' % meta['version']
    wb.properties.description = meta['basis_convention']
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    wb.save(a.out)
    print('[xlsx] %s  %.1f KB  sheets=%d' % (a.out, os.path.getsize(a.out) / 1024, len(wb.sheetnames)))


if __name__ == '__main__':
    main()
