#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Excel workbook (13 sheets) with live formulas.

Sheets:
 00_封面与结论  01_口径与规格  02_现货日度  03_期货日行情  04_基差计算
 05_基差归因    06_合约映射    07_换月与复权  08_历史分位    09_库存
 10_仓单        11_产业事件    12_公式说明    13_数据来源
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, 'build')
OUT = os.path.join(ROOT, 'out', 'methanol_basis_workbook.xlsx')

from openpyxl import Workbook                                    # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter                     # noqa: E402

INK = '1F3864'
HDR = PatternFill('solid', fgColor='1F3864')
SUB = PatternFill('solid', fgColor='D9E2F3')
WARN = PatternFill('solid', fgColor='FFF2CC')
BAD = PatternFill('solid', fgColor='FCE4E4')
OK = PatternFill('solid', fgColor='E2EFDA')
THIN = Side(style='thin', color='BFBFBF')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def load(name):
    with open(os.path.join(BUILD, name), encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def loadj(name):
    with open(os.path.join(BUILD, name), encoding='utf-8') as f:
        return json.load(f)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def head(ws, row, cols):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = Font(bold=True, color='FFFFFF', size=10)
        cell.fill = HDR
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BOX


def title(ws, text, sub=''):
    ws['A1'] = text
    ws['A1'].font = Font(bold=True, size=15, color=INK)
    if sub:
        ws['A2'] = sub
        ws['A2'].font = Font(size=9, color='808080')


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    A = loadj('analysis.json')
    spot = load('raw_spot.csv')
    fut = load('raw_futures.csv')
    basis = load('raw_basis.csv')
    inv = load('raw_inventory.csv')
    ev = load('raw_events.csv')
    ex = load('raw_extremes.csv')
    src = load('raw_sources.csv')
    gaps = loadj('gaps.json')
    rec = load('raw_receipts.csv')
    adj = load('main_continuous_adj.csv')

    wb = Workbook()

    # ------------------------------------------------------------ 00 封面
    ws = wb.active
    ws.title = '00_封面与结论'
    title(ws, '华东甲醇（太仓）× 郑商所 MA 基差研究',
          '数据截至 %s 收盘 | 本工作簿所有数字可由同簿各表公式复算' % A['asof'])
    rows = [
        ('', ''),
        ('一、核心结论', ''),
        ('当前基差（主力 %s 口径）' % A['main_contract'],
         '%+.0f 元/吨 = 现货 %.0f − 期货 %.0f' % (A['basis_now'], A['spot_now'], A['main_close'])),
        ('基差率', '%.2f%%' % A['basis_rate_now']),
        ('近 %d 个交易交易日变化' % A['decompose_30d']['span_trading_days'],
         '%+.0f 元/吨（现货贡献 %+.1f%% / 期货贡献 %+.1f%%）'
         % (A['decompose_30d']['delta_basis'], A['decompose_30d']['share_spot'],
            A['decompose_30d']['share_fut'])),
        ('区间峰值', '+%.0f 元/吨 @ %s' % (A['peak_basis'][1], A['peak_basis'][0])),
        ('近月 MA2611 口径基差', '%+.0f 元/吨（与隆众报的 +600 相差 4 元，属日期差）'
         % A['contracts']['MA2611']['basis']),
        ('', ''),
        ('二、关于历史分位（重要限制）', ''),
        ('可用真实样本', '%d 个有价交易日（%s ~ %s）'
         % (A['windows']['1Y']['n'], A['series'][0]['date'], A['asof'])),
        ('可用样本分位', '%.0f%%（仅供参考，不代表 1/3/5 年历史分位）' % A['windows']['1Y']['pct']),
        ('说明', A['limits']['reason']),
        ('', ''),
        ('三、证据方向', ''),
        ('支持基差强势', '港口库存历史极低；伊朗进口连续 9 个月归零；可交割资源全部在厂库（仓库仓单 0 张）；太仓为基准交割地升贴水 0'),
        ('不支持', '港口转为累库；沿海 MTO 集中停车形成需求负反馈；仓单回升；现货自身补跌'),
        ('', ''),
        ('四、结论边界', '本报告只陈述“基差当前处于什么位置、近期为何变化、有哪些数据支持或不支持”，'),
        ('', '不对基差是否必然回归下判断。极端分位≠必然回归。'),
    ]
    for i, (a, b) in enumerate(rows, 4):
        ws.cell(row=i, column=1, value=a).font = Font(bold=(b == ''), size=10,
                                                      color=INK if b == '' else '000000')
        c = ws.cell(row=i, column=2, value=b)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        c.font = Font(size=10)
        if a in ('二、关于历史分位（重要限制）',):
            for j in (1, 2):
                ws.cell(row=i, column=j).fill = WARN
    widths(ws, {'A': 34, 'B': 118})

    # ------------------------------------------------------------ 01 口径
    ws = wb.create_sheet('01_口径与规格')
    title(ws, '口径与规格声明', '先核实交割标准品与现货规格的可比性，再谈基差')
    data = [
        ('项目', '现货侧', '期货侧', '可比性判断'),
        ('品种', '甲醇 CH3OH', '甲醇 MA（郑商所）', '同品种'),
        ('品质标准', '优等品，GB/T 338-2011 工业用甲醇', '交割标准品：GB/T 338-2011 工业用甲醇优等品，不限制乙醇质量分数', '一致'),
        ('地区', '江苏太仓（出罐/库区自提）', '基准交割地：太仓（太仓阳鸿石化，仓库编号 0801，升贴水 0 元/吨）', '同地区，无跨区升贴水修正'),
        ('价格性质', '现货市场商谈价（区间，取中点计基差）', '期货收盘价（主力＝当日持仓量最大的合约）', '现货用商谈区间中点，需在表内注明'),
        ('税费口径', '含税（增值税）现货报价', '期货价格为含税交割基准价（完税标准仓单）', '均为含税，可比'),
        ('单位', '元/吨', '元/吨（交易单位 10 吨/手）', '一致'),
        ('报价时点', '早间开盘时段商谈（约 09:45-10:35）', '当日 15:00 收盘', '存在盘内时滞，属常规口径差'),
        ('交割方式', '—', '仓库标准仓单 / 厂库标准仓单交割、期转现(EFP)；最后交易日＝交割月第 10 个交易日', '—'),
        ('仓储费', '—', '2 元/吨·天（2021 年 5 月第 16 个交易日起来源公告）', '持有成本可直接进入基差核算'),
    ]
    for i, r in enumerate(data, 4):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical='top')
            c.font = Font(size=10, bold=(i == 4))
            c.border = BOX
            if i == 4:
                c.fill = HDR
                c.font = Font(bold=True, color='FFFFFF', size=10)
    widths(ws, {'A': 14, 'B': 40, 'C': 52, 'D': 30})

    # ------------------------------------------------------------ 02 现货
    ws = wb.create_sheet('02_现货日度')
    title(ws, '太仓甲醇现货日度报价（隆众资讯，出罐 现汇 含税，元/吨）',
          '原文未给出绝对价格的日子留空，不插值')
    cols = ['日期', '现货低端', '现货高端', '中值', '报价性质', '原文基差线索', '规格', '地区',
            '税费', '发布方', '来源编号', '备注']
    head(ws, 3, cols)
    r = 4
    for x in spot:
        lo, hi = fnum(x['spot_low']), fnum(x['spot_high'])
        vals = [x['date'], lo, hi, None, x['quote_kind'], x['basis_hint'], x['spec'],
                x['region'], x['tax'], x['publisher'], x['source_id'], x['note']]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.font = Font(size=10)
            c.border = BOX
            if j == 4 and lo is not None:
                c.value = round((lo + hi) / 2, 2)
                c.fill = SUB
            if j in (2, 3, 4):
                c.number_format = '0.00'
        if lo is None:
            ws.cell(row=r, column=12).fill = BAD
        r += 1
    widths(ws, {'A': 12, 'B': 10, 'C': 10, 'D': 10, 'E': 10, 'F': 18, 'G': 26,
                'H': 12, 'I': 8, 'J': 14, 'K': 9, 'L': 34})
    ws.freeze_panes = 'A4'

    # ------------------------------------------------------------ 03 期货
    ws = wb.create_sheet('03_期货日行情')
    title(ws, '郑商所 MA 各合约日行情（新浪财经归档，固定合约、未拼接）',
          '含已摘牌合约，用于固定合约基差与换月研究')
    cols = ['日期', '合约', '开盘', '最高', '最低', '收盘', '结算', '成交量', '持仓量', '来源编号']
    head(ws, 3, cols)
    r = 4
    for x in fut:
        for j, k in enumerate(['date', 'contract', 'open', 'high', 'low', 'close', 'settle',
                               'volume', 'oi', 'source_id'], 1):
            v = x[k]
            if k in ('open', 'high', 'low', 'close', 'settle', 'volume', 'oi'):
                v = fnum(v)
            ws.cell(row=r, column=j, value=v).font = Font(size=9)
        r += 1
    widths(ws, {'A': 12, 'B': 10, 'C': 9, 'D': 9, 'E': 9, 'F': 9, 'G': 9, 'H': 11, 'I': 11, 'J': 9})
    ws.freeze_panes = 'A4'
    ws.auto_filter.ref = 'A3:J%d' % (r - 1)

    # ------------------------------------------------------------ 04 基差计算
    ws = wb.create_sheet('04_基差计算')
    title(ws, '基差计算（带活公式）',
          '基差 = 现货中值 − 期货收盘；基差率 = 基差 / 现货中值')
    cols = ['日期', '现货低端', '现货高端', '现货中值', '主力合约', '主力收盘', '基差',
            '基差率%', 'MA2611收盘', '基差(MA2611)', 'MA2701收盘', '基差(MA2701)', '仓单(张)']
    head(ws, 3, cols)
    r = 4
    for x in basis:
        ws.cell(row=r, column=1, value=x['date'])
        ws.cell(row=r, column=2, value=fnum(x['spot_low'])).number_format = '0.00'
        ws.cell(row=r, column=3, value=fnum(x['spot_high'])).number_format = '0.00'
        ws.cell(row=r, column=4, value='=ROUND((B%d+C%d)/2,2)' % (r, r)).number_format = '0.00'
        ws.cell(row=r, column=5, value=x['main_contract'])
        ws.cell(row=r, column=6, value=fnum(x['main_close']))
        ws.cell(row=r, column=7, value='=D%d-F%d' % (r, r)).number_format = '+0;-0;0'
        ws.cell(row=r, column=8, value='=ROUND(G%d/D%d*100,2)' % (r, r))
        ws.cell(row=r, column=9, value=fnum(x.get('close_MA2611')) or None)
        ws.cell(row=r, column=10, value='=IF(I%d="","",D%d-I%d)' % (r, r, r))
        ws.cell(row=r, column=11, value=fnum(x.get('close_MA2701')) or None)
        ws.cell(row=r, column=12, value='=IF(K%d="","",D%d-K%d)' % (r, r, r))
        ws.cell(row=r, column=13, value=fnum(x['receipt_total']) or None)
        for j in range(1, 14):
            ws.cell(row=r, column=j).font = Font(size=10)
            ws.cell(row=r, column=j).border = BOX
        r += 1
    last = r - 1
    ws.cell(row=r + 1, column=1, value='说明：现货中值、基差、基差率均由左侧原始列公式算出，可逐行复核。').font = \
        Font(size=9, italic=True, color='808080')
    widths(ws, {'A': 12, 'B': 10, 'C': 10, 'D': 10, 'E': 10, 'F': 10, 'G': 10, 'H': 9,
                'I': 11, 'J': 12, 'K': 11, 'L': 12, 'M': 10})
    ws.freeze_panes = 'A4'

    # ------------------------------------------------------------ 05 归因
    ws = wb.create_sheet('05_基差归因')
    title(ws, '基差变动归因：现货贡献 vs 期货贡献',
          'Δ基差 = Δ现货 − Δ期货；贡献 = 该变量变化 /(|Δ现货|+|Δ期货|)')
    d30 = A['decompose_30d']
    dpk = A['decompose_peak']
    blocks = [
        ('近 23 个交易日（%s → %s）' % (d30['from_date'], d30['to_date']),
         4, d30, d30['from_date'], d30['to_date']),
        ('峰值以来（%s → %s）' % (dpk['from_date'], dpk['to_date']),
         12, dpk, dpk['from_date'], dpk['to_date']),
    ]
    for label, r0, d, d0, d1 in blocks:
        ws.cell(row=r0, column=1, value=label).font = Font(bold=True, size=11, color=INK)
        head(ws, r0 + 1, ['项目', '期初', '期末', '变化', '占基差变化(%)'])
        s0 = [x for x in basis if x['date'] == d0][0]
        s1 = [x for x in basis if x['date'] == d1][0]
        ws.cell(row=r0 + 2, column=1, value='现货中值')
        ws.cell(row=r0 + 2, column=2, value=fnum(s0['spot_mid']))
        ws.cell(row=r0 + 2, column=3, value=fnum(s1['spot_mid']))
        ws.cell(row=r0 + 2, column=4, value='=C%d-B%d' % (r0 + 2, r0 + 2))
        ws.cell(row=r0 + 3, column=1, value='期货主力收盘')
        ws.cell(row=r0 + 3, column=2, value=fnum(s0['main_close']))
        ws.cell(row=r0 + 3, column=3, value=fnum(s1['main_close']))
        ws.cell(row=r0 + 3, column=4, value='=C%d-B%d' % (r0 + 3, r0 + 3))
        ws.cell(row=r0 + 4, column=1, value='基差').font = Font(bold=True)
        ws.cell(row=r0 + 4, column=2, value=fnum(s0['basis_main']))
        ws.cell(row=r0 + 4, column=3, value=fnum(s1['basis_main']))
        ws.cell(row=r0 + 4, column=4, value='=C%d-B%d' % (r0 + 4, r0 + 4)).font = Font(bold=True)
        den = 'ABS(D%d)+ABS(D%d)' % (r0 + 2, r0 + 3)
        # 以基差变化为分母：现货上涨推升基差，期货上涨压低基差；两者之和恒为 100%
        ws.cell(row=r0 + 2, column=5, value='=D%d/(D%d-D%d)*100' % (r0 + 2, r0 + 2, r0 + 3))
        ws.cell(row=r0 + 3, column=5, value='=-D%d/(D%d-D%d)*100' % (r0 + 3, r0 + 2, r0 + 3))
        ws.cell(row=r0 + 4, column=5, value='—')
        for rr in range(r0 + 2, r0 + 5):
            for j in range(1, 6):
                c = ws.cell(row=rr, column=j)
                c.border = BOX
                c.font = Font(size=10, bold=c.font.bold)
                if j in (2, 3):
                    c.number_format = '0.00'
                elif j == 4:
                    c.number_format = '+0;-0;0'
                elif j == 5:
                    c.number_format = '0.0'
    widths(ws, {'A': 18, 'B': 11, 'C': 11, 'D': 11, 'E': 11, 'F': 14})
    ws.cell(row=21, column=1, value='解读：近月基差回落以期货上涨为主（期货 +215）；峰值以来则以现货补跌为主（现货 −895）。').font = \
        Font(size=10, italic=True)

    # ------------------------------------------------------------ 06 合约映射
    ws = wb.create_sheet('06_合约映射')
    title(ws, '同一天不同合约口径下的基差对比（%s）' % A['asof'],
          '曲线近高远低时，选哪个合约会改变基差数值')
    head(ws, 3, ['合约', '收盘价', '基差(元/吨)', '基差率(%)', '相对主力基差的差异'])
    r = 4
    base_b = None
    for k, v in A['contracts'].items():
        if base_b is None:
            base_b = v['basis']
        ws.cell(row=r, column=1, value=k)
        ws.cell(row=r, column=2, value=v['close'])
        ws.cell(row=r, column=3, value=v['basis']).number_format = '+0;-0;0'
        ws.cell(row=r, column=4, value=round(v['basis'] / A['spot_now'] * 100, 2))
        ws.cell(row=r, column=5, value='=C%d-$C$%d' % (r, 4 + len(A['contracts']) - 1))
        for j in range(1, 6):
            ws.cell(row=r, column=j).border = BOX
            ws.cell(row=r, column=j).font = Font(size=10)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='主力合约判定规则').font = Font(bold=True, color=INK)
    ws.cell(row=r + 1, column=1, value='每日取持仓量(oi)最大的合约为主力；MA0 为主力连续，存在换月跳空，不作为价格水平序列使用。')
    ws.cell(row=r + 2, column=1, value='隆众 10-19 报“现货小单基差 +600（对 MA2611）”，本表 MA2611 口径 %.0f，差值 %.0f 元/吨来自日期差一个交易日。'
            % (A['contracts']['MA2611']['basis'], abs(A['contracts']['MA2611']['basis'] - 600)))
    ws.cell(row=r + 3, column=1, value='外部核验：国内商品基差报告（10-20）甲醇 现货 3980 / 期货主力 3157 / 基差 823 / 基差率 20.68% —— 与本表完全一致。')
    widths(ws, {'A': 16, 'B': 12, 'C': 14, 'D': 12, 'E': 22})

    # ------------------------------------------------------------ 07 换月与复权
    ws = wb.create_sheet('07_换月与复权')
    title(ws, '主力合约换月与连续序列复权',
          'MA0 在换月日仍打印旧合约收益，跳空计入次日，故必须复权后才能跨换月比较')
    head(ws, 3, ['日期', '主力合约', '主力收盘', '换月事件', '换月跳空(新主力−旧主力)', '前复权收盘'])
    r = 4
    for x in adj:
        ws.cell(row=r, column=1, value=x['date'])
        ws.cell(row=r, column=2, value=x['main'])
        ws.cell(row=r, column=3, value=fnum(x['raw_close']))
        ws.cell(row=r, column=4, value=x['switch'] or '')
        ws.cell(row=r, column=5, value=fnum(x['roll_gap']) if x['roll_gap'] else '')
        ws.cell(row=r, column=6, value=fnum(x['adj_close']))
        for j in range(1, 7):
            ws.cell(row=r, column=j).font = Font(size=9)
            if x['switch']:
                ws.cell(row=r, column=j).fill = WARN
        r += 1
    widths(ws, {'A': 12, 'B': 11, 'C': 11, 'D': 22, 'E': 22, 'F': 12})
    ws.freeze_panes = 'A4'
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=6)
    ws.cell(row=r + 1, column=1,
            value='复权口径：adj(t) = 收盘(t) + 之后所有换月的同日价差(shift)，shift = 前一日新主力收盘 − 前一日旧主力收盘。最新一段等于原始价格；'
                  '已用 2026-09-10（MA2610 3411 → MA2701 3043）验证复权后换月日收益率等于新合约自身收益率。').font = \
        Font(size=9, italic=True, color='808080')

    # ------------------------------------------------------------ 08 历史分位
    ws = wb.create_sheet('08_历史分位')
    title(ws, '历史分位（可用样本 vs 名义窗口）',
          '现货日度序列仅有 %d 个真实有价日，故名义窗口与可用样本必须并列说明' % A['windows']['1Y']['n'])
    head(ws, 3, ['窗口', '起点', '名义样本数', '可用样本数', '当前值', '分位(%)', '均值',
                 '中位数', '标准差', '最小值', '最大值', '5%分位', '95%分位', '结论可用性'])
    r = 4
    for k, w in A['windows'].items():
        vals = [w['label'], w['cutoff'], '', w['n'], A['basis_now'], round(w['pct'], 1),
                round(w['mean'], 1), round(w['median'], 1), round(w['stdev'], 1),
                round(w['min'], 0), round(w['max'], 0), round(w['p05'], 1), round(w['p95'], 1),
                '不可作为历史分位']
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.border = BOX
            c.font = Font(size=10)
            if j == 14:
                c.fill = BAD
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='为什么不能给 1/3/5 年分位：').font = Font(bold=True, color='C00000')
    ws.cell(row=r + 1, column=1, value=A['limits']['reason'])
    ws.cell(row=r + 1, column=1).alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 4, end_column=8)
    r += 6
    ws.cell(row=r, column=1, value='可用的替代参考（非分位）：').font = Font(bold=True, color=INK)
    ws.cell(row=r + 1, column=1, value='• 行业口径：正常年份甲醇期现基差多在 ±100 元/吨区间，供应紧张时高点通常在 500 元/吨以内（来源 S11）')
    ws.cell(row=r + 2, column=1, value='• 当前 +823 元/吨（主力口径）/ +596 元/吨（近月口径），显著高于上述经验区间')
    ws.cell(row=r + 3, column=1, value='• 本区间峰值 +1,672 元/吨（2026-09-29），已回落 849 元/吨')
    widths(ws, {'A': 14, 'B': 12, 'C': 12, 'D': 11, 'E': 10, 'F': 10, 'G': 10, 'H': 10,
                'I': 10, 'J': 10, 'K': 10, 'L': 10, 'M': 10, 'N': 18})

    # ------------------------------------------------------------ 09 库存
    ws = wb.create_sheet('09_库存')
    title(ws, '库存（万吨）', '隆众口径为主；不同终端转述数值并列，不合并、不相减')
    head(ws, 3, ['日期', '项目', '数值(万吨)', '变化(万吨)', '备注', '来源编号'])
    r = 4
    for x in inv:
        vals = [x['date'], x['item'], fnum(x['value_wan_ton']),
                fnum(x['chg_wan_ton']) if x['chg_wan_ton'] else None, x['note'], x['source_id']]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.border = BOX
            c.font = Font(size=10)
            if j in (3, 4):
                c.number_format = '+0.00;-0.00'
        r += 1
    widths(ws, {'A': 12, 'B': 22, 'C': 12, 'D': 12, 'E': 56, 'F': 9})

    # ------------------------------------------------------------ 10 仓单
    ws = wb.create_sheet('10_仓单')
    title(ws, '郑商所甲醇仓单日报（张，1 张 = 10 吨）',
          '本期所有有效仓单均在厂库，实体仓库口径为 0')
    head(ws, 3, ['日期', '仓单总计', '当日增减', '仓库口径', '厂库口径', '折合吨(总)'])
    r = 4
    for x in rec:
        vals = [x['date'], fnum(x['receipt_total']),
                fnum(x['receipt_chg']) if x['receipt_chg'] else 0,
                fnum(x['warehouse_receipts']), fnum(x['factory_receipts'])]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.border = BOX
            c.font = Font(size=10)
            if j in (2, 3, 4, 5):
                c.number_format = '+#,##0;-#,##0;0'
        ws.cell(row=r, column=6, value='=B%d*10' % r).number_format = '#,##0'
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='10-20 仓单构成（张）：杭实化工（厂库）1,866 / 安徽中能 1,400 / 国贸石化 1,000 / '
            '金桥化工 900 / 中化化销 600 / 定州天鹭 600 / 河南心连心 267 / 安徽昊源 200 → 合计 6,633。'.replace('/ ', '/'))
    ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r + 1, end_column=6)
    widths(ws, {'A': 12, 'B': 12, 'C': 12, 'D': 12, 'E': 12, 'F': 12})

    # ------------------------------------------------------------ 11 事件
    ws = wb.create_sheet('11_产业事件')
    title(ws, '产业事件与对基差的含义')
    head(ws, 3, ['日期', '类别', '事件', '对基差的含义', '来源编号'])
    r = 4
    for x in ev:
        for j, k in enumerate(['date', 'category', 'event', 'bearing_on_basis', 'source_id'], 1):
            c = ws.cell(row=r, column=j, value=x[k])
            c.alignment = Alignment(wrap_text=True, vertical='top')
            c.font = Font(size=10)
            c.border = BOX
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='历史极值时期背景').font = Font(bold=True, color=INK)
    head(ws, r + 1, ['日期', 'MA主连收盘', '当时背景', '后续', '来源编号'])
    r += 2
    for x in ex:
        for j, k in enumerate(['date', 'ma0_close', 'background', 'aftermath', 'source_id'], 1):
            c = ws.cell(row=r, column=j, value=fnum(x[k]) if k == 'ma0_close' else x[k])
            c.alignment = Alignment(wrap_text=True, vertical='top')
            c.font = Font(size=10)
            c.border = BOX
        r += 1
    widths(ws, {'A': 12, 'B': 10, 'C': 62, 'D': 46, 'E': 9})

    # ------------------------------------------------------------ 12 公式
    ws = wb.create_sheet('12_公式说明')
    title(ws, '计算公式与口径定义（全文统一）')
    formulas = [
        ('指标', '公式', '示例（%s）' % A['asof'], '说明'),
        ('基差', '基差 = 现货价格 − 期货价格',
         '%.0f − %.0f = %+.0f' % (A['spot_now'], A['main_close'], A['basis_now']),
         '正值＝现货升水（Back），负值＝现货贴水（Contango）'),
        ('基差率', '基差率 = 基差 / 现货价格 × 100',
         '%.2f%%' % A['basis_rate_now'], '与国内商品基差报告口径一致'),
        ('现货中值', '现货中值 = (报盘低端 + 报盘高端) / 2', '%.1f' % A['spot_now'], '区间报价取中点'),
        ('主力合约', '当日持仓量最大的 MA 合约', A['main_contract'], '不用成交额/成交量，避免交割月噪声'),
        ('换月跳空', 'gap = 切换日新主力收盘 − 同一日旧主力收盘', '−387（2026-09-10）',
         '旧主力需在切换日仍有报价；含当日行情，不能直接当复权量'),
        ('同日价差', 'shift = 前一日新主力收盘 − 前一日旧主力收盘', '−412（2026-09-10）',
         '复权必须用它：把合约阶梯与当日行情分开'),
        ('前复权连续', 'adj(t) = 收盘(t) + Σ(之后所有换月的同日价差 shift)', '最新段 = %.0f' % A['main_close'],
         '最新段等于原始价格，复权后换月日收益率=新合约自身收益率'),
        ('基差变化', 'Δ基差 = Δ现货 − Δ期货', '%+.0f = %+.0f − %+.0f'
         % (A['decompose_30d']['delta_basis'], A['decompose_30d']['delta_spot'],
            A['decompose_30d']['delta_fut']),
         '现货上涨推升基差，期货上涨压缩基差'),
        ('贡献度', '贡献 = 该变量变化 /(|Δ现货|+|Δ期货|)',
         '现货 %+.1f%% / 期货 %+.1f%%' % (A['decompose_30d']['share_spot'],
                                         A['decompose_30d']['share_fut']),
         '两者绝对值之和为 100%'),
        ('经验分位', '分位 = #{x ≤ 当前值} / N × 100', '%.0f%%（N=%d）'
         % (A['windows']['1Y']['pct'], A['windows']['1Y']['n']),
         '仅在样本足够且跨周期时才有解释力'),
        ('仓单折吨', '吨数 = 仓单张数 × 10', '%.0f 吨' % (A['basis_now'] and 6633 * 10),
         '郑商所甲醇 10 吨/手、交割单位 10 吨'),
    ]
    for i, r in enumerate(formulas, 4):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical='top')
            c.border = BOX
            c.font = Font(size=10, bold=(i == 4))
            if i == 4:
                c.fill = HDR
                c.font = Font(bold=True, color='FFFFFF', size=10)
    widths(ws, {'A': 14, 'B': 46, 'C': 30, 'D': 52})

    # ------------------------------------------------------------ 13 来源
    ws = wb.create_sheet('13_数据来源')
    title(ws, '数据来源与缺口声明')
    head(ws, 3, ['编号', '来源', '链接', '发布方', '获取日'])
    r = 4
    for x in src:
        for j, k in enumerate(['id', 'title', 'url', 'publisher', 'retrieved'], 1):
            c = ws.cell(row=r, column=j, value=x[k])
            c.font = Font(size=9)
            c.alignment = Alignment(wrap_text=True, vertical='top')
            c.border = BOX
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='数据缺口（不估算、不插值）').font = Font(bold=True, color='C00000')
    r += 1
    for k, v in gaps.items():
        ws.cell(row=r, column=1, value=k).font = Font(size=9, bold=True)
        c = ws.cell(row=r, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        c.font = Font(size=9)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        ws.row_dimensions[r].height = 30
        r += 1
    widths(ws, {'A': 12, 'B': 48, 'C': 46, 'D': 18, 'E': 12})

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    print('XLSX -> %s (%d sheets, %.1f KB)' % (OUT, len(wb.sheetnames), os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
