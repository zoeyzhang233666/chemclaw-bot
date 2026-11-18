# -*- coding: utf-8 -*-
"""data.json -> 13 表工作簿（openpyxl）。表结构固定，内容全部来自 data.json。

用法：
  python build_xlsx.py data.json --out out/纯碱-全国行情与销售事实.xlsx

设计：每一张表都允许“缺数据”，缺的地方写缺口、写补齐路径，不留空白格，
       也不拿估算值填充。所有数字与 HTML 同源，天然一致。
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, Reference

# ---------------------------------------------------------------- 主题
INK, NAVY, NAVY2 = '1A2233', '1F3A5F', '2A4A72'
AMBER, AMBER_L = 'C8892B', 'FDF3DF'
GREEN, GREEN_L = '1E7A54', 'E8F5EF'
RED, RED_L = 'B23A48', 'FCEDEF'
GREY, GREY_L, LINE, WHITE = '6B7A90', 'F4F6F9', 'D8DEE8', 'FFFFFF'
FONT = '微软雅黑'
MONO = 'Consolas'

TITLE_F = Font(name=FONT, size=16, bold=True, color=INK)
SUB_F = Font(name=FONT, size=9.5, color=GREY)
H_F = Font(name=FONT, size=10, bold=True, color=WHITE)
BODY_F = Font(name=FONT, size=10, color=INK)
BODY_B = Font(name=FONT, size=10, bold=True, color=INK)
SMALL_F = Font(name=FONT, size=9, color=GREY)
NUM_F = Font(name=MONO, size=10, color=INK)
NUM_B = Font(name=MONO, size=10.5, bold=True, color=INK)
LINK_F = Font(name=FONT, size=9, color='1F4E8C', underline='single')

THIN = Side(style='thin', color=LINE)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FILL_HEAD = PatternFill('solid', fgColor=NAVY)
FILL_ZEBRA = PatternFill('solid', fgColor=GREY_L)
FILL_AMBER = PatternFill('solid', fgColor=AMBER_L)
FILL_GREEN = PatternFill('solid', fgColor=GREEN_L)
FILL_RED = PatternFill('solid', fgColor=RED_L)
FILL_W = PatternFill('solid', fgColor=WHITE)

wr = Alignment(horizontal='left', vertical='center', wrap_text=True)
wc = Alignment(horizontal='center', vertical='center', wrap_text=True)
wrn = Alignment(horizontal='right', vertical='center')

BANNED = ['预计涨', '预计跌', '看涨', '看跌', '抄底', '必涨', '必跌', '稳赚']


class Book:
    def __init__(self, D):
        self.D = D
        self.M = D['meta']
        self.wb = Workbook()
        self.wb.remove(self.wb.active)
        self.warn = []

    # ------------------------------------------------------------ 基础件
    def sheet(self, name, tab=NAVY):
        ws = self.wb.create_sheet(name)
        ws.sheet_properties.tabColor = tab
        ws.sheet_view.showGridLines = False
        ws.sheet_view.zoomScale = 90
        ws.freeze_panes = 'A3'
        return ws

    def banner(self, ws, title, sub, ncol, h1=36, h2=32):
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        c = ws.cell(row=1, column=1, value=title)
        c.font, c.fill = TITLE_F, FILL_W
        c.alignment = Alignment(horizontal='left', vertical='center', indent=1)
        ws.row_dimensions[1].height = h1
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        c = ws.cell(row=2, column=1, value=sub)
        c.font, c.fill = SUB_F, FILL_W
        c.alignment = Alignment(horizontal='left', vertical='center', indent=1, wrap_text=True)
        ws.row_dimensions[2].height = h2

    def header(self, ws, row, cols, widths, height=30):
        for i, (nm, w) in enumerate(zip(cols, widths), start=1):
            c = ws.cell(row=row, column=i, value=nm)
            c.font, c.fill, c.alignment, c.border = H_F, FILL_HEAD, wc, BOX
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[row].height = height

    def put(self, ws, row, vals, fills=None, fonts=None, aligns=None, fmt=None, zebra=False, heights=None, widths=None):
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=i, value=v)
            c.font = (fonts[i - 1] if fonts and i - 1 < len(fonts) and fonts[i - 1] else BODY_F)
            c.alignment = (aligns[i - 1] if aligns and i - 1 < len(aligns) and aligns[i - 1] else wr)
            c.border = BOX
            if fills and i - 1 < len(fills) and fills[i - 1]:
                c.fill = fills[i - 1]
            elif zebra:
                c.fill = FILL_ZEBRA
            if fmt and i - 1 < len(fmt) and fmt[i - 1]:
                c.number_format = fmt[i - 1]
        for v in vals:
            for b in common.banned_hits(v):
                self.warn.append('第 %d 行出现方向性表述「%s」：%s' % (row, b, common.clip(v, 40)))
        if heights or widths:
            self.auto_height(ws, row, vals, widths)
        return row

    def auto_height(self, ws, row, vals, widths):
        if not widths:
            return
        lines = 1
        for t, w in zip(vals, widths):
            if t is None:
                continue
            s = str(t)
            per = max(6, (w - 1) * 1.05)
            lines = max(lines, int(common.cjk_width(s) / per) + 1 + s.count('\n'))
        ws.row_dimensions[row].height = min(150, max(16, lines * 15))

    def note(self, ws, row, text, ncol, height=None, color=GREY, fill=None, bold=False):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
        c = ws.cell(row=row, column=1, value=text)
        c.font = Font(name=FONT, size=9.5, color=color, bold=bold)
        c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True, indent=1)
        if fill:
            c.fill = fill
        if height:
            ws.row_dimensions[row].height = height
        for b in common.banned_hits(text):
            self.warn.append('说明行出现方向性表述「%s」' % b)
        return row

    def band(self, ws, row, text, ncol, color, height=26):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
        c = ws.cell(row=row, column=1, value=text)
        c.font = Font(name=FONT, size=11, bold=True, color=WHITE)
        c.fill = PatternFill('solid', fgColor=color)
        c.alignment = Alignment(horizontal='left', vertical='center', indent=1)
        ws.row_dimensions[row].height = height
        return row

    # ------------------------------------------------------------ 00 封面与结论
    def s00(self):
        D, M = self.D, self.M
        ws = self.sheet('00_封面与结论', AMBER)
        widths = [22, 30, 18, 12, 40, 24]
        self.banner(ws, '%s · 行情与销售事实工作簿' % M['product'],
                    '产品：%s ｜ 重点市场：%s ｜ 数据截至 %s ｜ 只陈述已发生事实，不预测后市'
                    % (M['product'], M['region'], M['asof']), 6, 40)
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

        r = 4
        self.band(ws, r, '一句话结论（只描述现状，不含判断）', 6, AMBER)
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = ws.cell(row=r, column=1, value=D.get('summary') or '数据不足，尚未形成可陈述的结论。')
        c.font = Font(name=FONT, size=10, color=INK)
        c.fill = FILL_AMBER
        c.alignment = Alignment(wrap_text=True, vertical='center', indent=1)
        ws.row_dimensions[r].height = max(46, 16 * (common.cjk_width(D.get('summary') or '') // 150 + 1))
        r += 2

        self.header(ws, r, ['指标', '数值', '口径 / 日期', '方向', '来源', '备注'], widths)
        r += 1
        cards = self._cards()
        for i, row in enumerate(cards):
            d = row[3]
            fill_d = FILL_GREEN if d in ('低位', '倒挂', '双弱', '下行', '↓') else (
                FILL_RED if d in ('高位', '上行', '↑', '回升') else None)
            self.put(ws, r, list(row),
                     fills=[None, None, None, fill_d, None, None],
                     fonts=[BODY_B, NUM_B, BODY_F, BODY_B, BODY_F, SMALL_F],
                     fmt=[None, '@', None, None, None, None], zebra=(i % 2 == 1),
                     widths=widths)
            r += 1

        r += 1
        self.band(ws, r, '⚠ 使用前必读', 6, RED)
        r += 1
        readme = list(D.get('caveats') or [])
        if not readme:
            readme = ['所有数字均标注日期与来源；引用前请核对当日实盘。']
        for t in readme:
            self.note(ws, r, '· ' + t, 6, height=max(30, 15 * (common.cjk_width(t) // 110 + 1)), color=RED)
            r += 1
        return '00_封面与结论'

    def _cards(self):
        D, M = self.D, self.M
        a, L, w1, w3 = D.get('anchor'), D.get('last') or {}, D['win'].get('1y'), D['win'].get('3y')
        out = []
        if a:
            out.append(['现货锚', '%s %s' % (common.fmt(a['value']), a.get('unit') or M['unit']),
                        '%s · %s' % (a.get('date'), a.get('basis') or ''), '—',
                        a.get('src') or '', a.get('note') or ''])
        else:
            out.append(['现货锚', '缺口', '未提供带六项口径的现货', '缺口', '—', '见 12 表'])
        if L.get('close') is not None:
            d7 = (D['chg'].get('7d') or {}).get('pct')
            out.append(['期货主连', '%s %s' % (common.fmt(L['close']), M['unit']),
                        '%s 收盘 · %s %s' % (L.get('date'), M.get('exchange', ''), M.get('contract', '')),
                        '↑' if (L.get('pct') or 0) > 0 else '↓' if (L.get('pct') or 0) < 0 else '—',
                        '行情接口（东方财富）', '不含税；7日 %s' % common.pct(d7)])
        else:
            out.append(['期货主连', '缺口', '无连续序列', '缺口', '—', '该品种可能无场内期货'])
        for k, lbl in [('7d', '近 7 日'), ('30d', '近 30 日'), ('90d', '近 90 日'), ('1y', '近 1 年'), ('3y', '近 3 年')]:
            c = D['chg'].get(k)
            if c:
                out.append([lbl + '涨跌', common.pct(c['pct']), '对比 %s（%s）' % (c['from_date'], common.fmt(c['from_close'])),
                            '↓' if c['pct'] < 0 else '↑', '同上', '基准日逐条列于 04 表'])
        if w1:
            out.append(['近 1 年分位', '%s%%' % common.fmt(w1['pct_rank'], 1), '区间 %s–%s' % (common.fmt(w1['low']), common.fmt(w1['high'])),
                        '低位' if w1['pct_rank'] < 20 else '中性', '同上（%d 个交易日）' % w1['n'],
                        '区间位置 %s%%' % common.fmt(w1['pos_in_range'], 1)])
        if w3:
            out.append(['近 3 年分位', '%s%%' % common.fmt(w3['pct_rank'], 1), '区间 %s–%s' % (common.fmt(w3['low']), common.fmt(w3['high'])),
                        '低位' if w3['pct_rank'] < 20 else '中性', '同上（%d 个交易日）' % w3['n'],
                        '区间位置 %s%%' % common.fmt(w3['pos_in_range'], 1)])
        mg = [m for m in (D.get('margins') or []) if m.get('routes')]
        if mg:
            m = mg[-1]
            rv = m['routes']
            txt = ' / '.join('%s %s' % (k, common.fmt_trim(v)) for k, v in rv.items())
            neg = [k for k, v in rv.items() if v < 0]
            out.append(['工艺毛利', txt, m.get('date'), '倒挂' if neg else '—',
                        m.get('src', ''), '毛利口径，非现金流利润' + ('；%s 为负' % '、'.join(neg) if neg else '')])
        for b in (D.get('balance') or [])[:4]:
            out.append([b.get('k', ''), str(b.get('v', '')), b.get('date', ''), '—', b.get('src', ''), b.get('prev', '')])
        if D.get('spreads'):
            rows = sorted(D['spreads'], key=lambda x: x['mid'])
            lo, hi = rows[0], rows[-1]
            out.append(['区域价差', '%s %s' % (common.fmt(hi['mid'] - lo['mid']), M['unit']),
                        rows[0]['date'], '—', '见 05 表',
                        '%s %s ↔ %s %s' % (lo['region'], common.fmt(lo['mid']), hi['region'], common.fmt(hi['mid']))])
        else:
            out.append(['区域价差', '缺口', '缺少同日同规格的多地区报价', '缺口', '—', '跨日期相减会制造假价差'])
        out.append(['事件数 / 缺口数', '%d / %d' % (len(D.get('events') or []), len(D.get('gaps') or [])),
                    M['asof'], '—', '见 09 / 12 表', '缺口必须随交付一起说明'])
        return out

    # ------------------------------------------------------------ 01 现货
    def s01(self):
        D, M = self.D, self.M
        ws = self.sheet('01_当前现货价', NAVY)
        widths = [12, 24, 26, 12, 12, 12, 14, 16, 12, 8, 58]
        self.banner(ws, '当前现货价格（逐条口径）',
                    '规格、地区、含税、提货方式、数据日期、来源六项齐全才入表；单点与区间分列，不混算。数据截至 %s。' % M['asof'], 11)
        self.header(ws, 3, ['地区 / 市场', '细分', '规格', '价格下限\n(%s)' % M['unit'], '价格上限', '中值',
                            '含税', '提货方式', '数据日期', '完整度', '来源 / 备注'], widths)
        ws.freeze_panes = 'A4'
        r = 4
        if not D['spots']:
            self.note(ws, r, '缺口：未提供任何现货报价。没有现货就无法回答“当前价是多少”，只能给期货价。'
                             '补齐方式见 references/data-contract.md 的 spot 字段。', 11, 40, color=RED, fill=FILL_RED)
            return '01_当前现货价'
        for i, s in enumerate(D['spots']):
            mid = round((s['lo'] + s['hi']) / 2, 1)
            vals = [s['region'], s['sub'], s['product'], s['lo'], s['hi'], mid, s['tax'], s['basis'],
                    s['date'], s['conf'], (s['note'] + ' ｜ ' + s['src']).strip(' ｜')]
            fills = [None] * 10 + [FILL_AMBER if s['conf'] == '中' else (FILL_RED if s['conf'] == '缺口' else None)]
            self.put(ws, r, vals, fills=fills,
                     fonts=[BODY_B, BODY_F, BODY_F, NUM_F, NUM_F, NUM_B, BODY_F, BODY_F, NUM_F, BODY_B, SMALL_F],
                     aligns=[wr, wr, wr, wrn, wrn, wrn, wc, wr, wc, wc, wr],
                     fmt=[None, None, None, '#,##0', '#,##0', '#,##0.0', None, None, '@', None, None],
                     zebra=(i % 2 == 1), widths=widths)
            r += 1
        r += 1
        if D.get('last', {}).get('close') is not None:
            self.note(ws, r, '期货对照（不可与上表现货直接相减）：%s %s %s %s，%s 收盘，不含税、含交割成本；'
                             '折算含税约 %s（×1.13），仍与现货差交割、仓储、区域升贴水。'
                      % (M.get('exchange', ''), M.get('contract', ''), common.fmt(D['last']['close']), M['unit'],
                         D['last']['date'], common.fmt(D['last']['close'] * 1.13)), 11, 44)
            r += 2
        single = [s for s in D['spots'] if s['single']]
        if single:
            self.note(ws, r, '口径提示：表内 %d 条为单点报价（原文未给区间），占 %d 条中的 %d 条；'
                             '与区间报价混比会放大或缩小价差，引用时必须注明。'
                      % (len(single), len(D['spots']), len(single)), 11, 34, color=AMBER, fill=FILL_AMBER)
        return '01_当前现货价'

    # ------------------------------------------------------------ 02 日线
    def s02(self):
        D, M = self.D, self.M
        ws = self.sheet('02_期货日线', NAVY2)
        widths = [13, 11, 11, 11, 11, 14, 20, 11]
        allw = D['series'].get('all_w') or []
        self.banner(ws, '%s日线（%s %s）' % (M['product'], M.get('exchange', ''), M.get('contract', '')),
                    '连续序列，便于复核任意一天的涨跌。不含税、含交割成本。样本 %s ~ %s；'
                    '本表为周线聚合（日线原始数据在 raw/*_daily.json），供快速核对与画图。'
                    % (allw[0][0] if allw else '—', allw[-1][0] if allw else '—'), 8)
        self.header(ws, 3, ['日期(周)', '开盘', '收盘', '最高', '最低', '距今日数', '按周涨跌%', '备注'], widths)
        ws.freeze_panes = 'A4'
        r = 4
        if not allw:
            self.note(ws, r, '缺口：没有价格序列。走势、分位、异常波动三块都做不了；不要用新闻里的零散价格拼序列。', 8, 34, color=RED, fill=FILL_RED)
            return '02_期货日线'
        prev = None
        for i, x in enumerate(allw):
            pct = None if prev is None else round((x[2] / prev - 1) * 100, 2)
            prev = x[2]
            self.put(ws, r, [x[0], x[1], x[2], x[4], x[3], None, pct, None],
                     fonts=[BODY_F, NUM_F, NUM_B, NUM_F, NUM_F, NUM_F, NUM_F, SMALL_F],
                     aligns=[wc, wrn, wrn, wrn, wrn, wrn, wrn, wr],
                     fmt=[None, '#,##0', '#,##0', '#,##0', '#,##0', '#,##0', '0.00', None],
                     zebra=(i % 2 == 1),
                     fills=[None, None, FILL_RED if (pct or 0) > 0 else (FILL_GREEN if (pct or 0) < 0 else None), None, None, None, None, None])
            r += 1
        ws.auto_filter.ref = 'A3:H%d' % (r - 1)
        ch = LineChart()
        ch.title = '%s 周收盘价（%s，不含税）' % (M['product'], M['unit'])
        ch.style, ch.height, ch.width = 2, 11, 26
        ch.y_axis.title = M['unit']
        data = Reference(ws, min_col=3, min_row=3, max_row=r - 1)
        cats = Reference(ws, min_col=1, min_row=4, max_row=r - 1)
        ch.add_data(data, titles_from_data=True)
        ch.set_categories(cats)
        ch.y_axis.majorGridlines = None
        ch.legend = None
        ws.add_chart(ch, 'J4')
        return '02_期货日线'

    # ------------------------------------------------------------ 03 走势底表
    def s03(self):
        D, M = self.D, self.M
        ws = self.sheet('03_走势图表底表', NAVY2)
        widths = [13, 12, 13, 13, 16]
        self.banner(ws, '走势图表底表（近一年日 + 月度）',
                    '左：近一年日线收盘；右：全样本月度 OHLC 与均价。可直接在 Excel 里重画图。', 9)
        self.header(ws, 3, ['日期', '收盘价', None, None, None], widths)
        for j, nm in enumerate(['月份', '月均价', '月最高', '月最低'], start=6):
            ws.column_dimensions[get_column_letter(j)].width = 13
            c = ws.cell(row=3, column=j, value=nm)
            c.font, c.fill, c.alignment, c.border = H_F, FILL_HEAD, wc, BOX
        ws.column_dimensions['F'].width = 11
        y1 = D['series'].get('1y') or []
        r = 4
        for i, x in enumerate(y1):
            self.put(ws, r, [x[0], x[2], None, None, None],
                     fonts=[BODY_F, NUM_B, NUM_F, NUM_F, NUM_F], aligns=[wc, wrn, wrn, wrn, wrn],
                     fmt=[None, '#,##0', None, None, None], zebra=(i % 2 == 1))
            r += 1
        # 月度 OHLC 从 all_w 聚合（周线 -> 月）
        months = {}
        for x in (D['series'].get('all_w') or []):
            months.setdefault(x[0][:7], []).append(x)
        mr = 4
        for m in sorted(months):
            v = months[m]
            hi = max(x[4] for x in v)
            lo = min(x[3] for x in v)
            avg = round(sum(x[2] for x in v) / len(v), 1)
            for j, val in enumerate([m, avg, hi, lo], start=6):
                c = ws.cell(row=mr, column=j, value=val)
                c.font = NUM_B if j == 7 else (BODY_F if j == 6 else NUM_F)
                c.alignment = wc if j == 6 else wrn
                c.border = BOX
                c.number_format = '#,##0.0' if j == 7 else ('@' if j == 6 else '#,##0')
                if (mr - 4) % 2:
                    c.fill = FILL_ZEBRA
            mr += 1
        if y1:
            ch = LineChart()
            ch.title = '%s 收盘价（近一年，%s，不含税）' % (M['product'], M['unit'])
            ch.style, ch.height, ch.width = 2, 11, 26
            ch.y_axis.title = M['unit']
            ch.add_data(Reference(ws, min_col=2, min_row=3, max_row=r - 1), titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=1, min_row=4, max_row=r - 1))
            ch.y_axis.majorGridlines = None
            ch.legend = None
            ws.add_chart(ch, 'H4')
        return '03_走势图表底表'

    # ------------------------------------------------------------ 04 涨跌与分位
    def s04(self):
        D, M = self.D, self.M
        ws = self.sheet('04_涨跌幅与分位', GREEN)
        widths = [12, 13, 12, 12, 15, 11, 62]
        self.banner(ws, '涨跌幅与历史分位',
                    '全部按“区间首日收盘 → %s 收盘”计算，基准日逐条列出；分位为区间内收盘价低于当前价的天数占比。' % M['asof'], 7)
        self.header(ws, 3, ['区间', '起点日期', '起点收盘', '终点收盘', '绝对变动(%s)' % M['unit'], '涨跌幅', '同期发生了什么（事实层）'], widths)
        r = 4
        label = {'7d': '7 天', '30d': '30 天', '90d': '90 天', '1y': '1 年', '3y': '3 年'}
        for i, k in enumerate(['7d', '30d', '90d', '1y', '3y']):
            c = D['chg'].get(k)
            if not c:
                self.put(ws, r, [label[k], '数据不足', None, None, None, None, '该窗口内样本不足，不插值'],
                         fills=[None, FILL_RED, None, None, None, None, None], zebra=(i % 2 == 1), widths=widths)
                r += 1
                continue
            near = [e for e in D['events'] if e.get('date') and c['from_date'] <= e['date'] <= D['last']['date']]
            near.sort(key=lambda e: e['date'], reverse=True)
            why = '；'.join(e['title'] for e in near[:2]) or '该区间内无可引用事件'
            self.put(ws, r, [label[k], c['from_date'], c['from_close'], D['last']['close'], c['abs'],
                             c['pct'] / 100, why],
                     fonts=[BODY_B, BODY_F, NUM_F, NUM_F, NUM_B, NUM_B, BODY_F],
                     aligns=[wc, wc, wrn, wrn, wrn, wc, wr],
                     fmt=[None, '@', '#,##0', '#,##0', '+#,##0.0;-#,##0.0', '+0.00%;-0.00%', None],
                     fills=[None, None, None, None, FILL_GREEN if c['abs'] < 0 else FILL_RED, FILL_GREEN if c['pct'] < 0 else FILL_RED, None],
                     zebra=(i % 2 == 1), widths=widths)
            ws.cell(row=r, column=6).font = Font(name=MONO, size=11, bold=True,
                                                color=GREEN if c['pct'] < 0 else RED)
            r += 1

        r += 1
        self.header(ws, r, ['窗口', '起始日', '样本(交易日)', '区间最低', '区间最高', '均值', '中位数', '当前分位', '区间位置'],
                    [16, 13, 14, 12, 12, 12, 12, 12, 12])
        r += 1
        for i, k in enumerate(['1y', '3y', '5y']):
            w = D['win'].get(k)
            if not w:
                continue
            self.put(ws, r, [{'1y': '近 1 年', '3y': '近 3 年', '5y': '近 5 年'}[k], w['start'], w['n'],
                             w['low'], w['high'], w['mean'], w['median'], w['pct_rank'] / 100, w['pos_in_range'] / 100],
                     fonts=[BODY_B, BODY_F, NUM_F, NUM_B, NUM_B, NUM_F, NUM_F, NUM_B, NUM_F],
                     aligns=[wc, wc, wrn, wrn, wrn, wrn, wrn, wc, wc],
                     fmt=[None, '@', '#,##0', '#,##0', '#,##0', '#,##0.0', '#,##0.0', '0.0%', '0.0%'],
                     fills=[None, None, None, FILL_GREEN, FILL_RED, None, None, FILL_GREEN, FILL_GREEN],
                     zebra=(i % 2 == 1))
            r += 1

        r += 1
        if D.get('peak') and D.get('trough') and D.get('drawdown'):
            self.note(ws, r, '样本极值：最高 %s %s（%s）；最低 %s %s（%s）。当前价较样本高点回撤 %s，'
                             '距样本低点 %s %s（%s）。样本 = %s %s，%s 至 %s。'
                      % (common.fmt(D['peak']['value']), M['unit'], D['peak']['date'],
                         common.fmt(D['trough']['value']), M['unit'], D['trough']['date'],
                         common.pct(D['drawdown']['from_peak'], 1),
                         common.fmt(D['drawdown']['above_low_abs']), M['unit'],
                         common.pct(D['drawdown']['above_low_pct'], 1),
                         M.get('exchange', ''), M.get('contract', ''),
                         (D['series'].get('all_w') or [['—']])[0][0], (D['series'].get('all_w') or [['—']])[-1][0]),
                      9, 44)
        return '04_涨跌幅与分位'

    # ------------------------------------------------------------ 05 区域价差
    def s05(self):
        D, M = self.D, self.M
        ws = self.sheet('05_区域价差', AMBER)
        widths = [10, 26, 12, 12, 12, 15, 16, 10, 52]
        base = (D['spreads'][0]['base_region'] if D['spreads'] else '基准')
        self.banner(ws, '主要区域价差（同日同规格）',
                    '口径：同一天、同一规格、统一含税；以 %s 中值为基准。不同日期相减会制造假价差，本表不做。' % base, 9)
        self.header(ws, 3, ['区域', '细分市场', '价格下限', '价格上限', '中值', '较%s(%s)' % (base, M['unit']),
                            '提货方式', '含税', '价差主因 / 来源'], widths)
        r = 4
        if not D['spreads']:
            self.note(ws, r, '缺口：缺少“同日 + 同规格”的多地区报价，无法计算真实价差。补齐方式：'
                             '① 找同一期资讯里的分区域报价；② 向 2–3 家不同区域贸易商询同一规格同日价格。', 9, 40,
                      color=RED, fill=FILL_RED)
            return '05_区域价差'
        for i, s in enumerate(sorted(D['spreads'], key=lambda x: x['mid'])):
            d = s['diff_vs_base']
            self.put(ws, r, [s['region'], s['sub'], s['lo'], s['hi'], s['mid'], d, s['basis'], s['tax'],
                             (s['driver'] + ' ｜ ' + s['src']).strip(' ｜')],
                     fonts=[BODY_B, BODY_F, NUM_F, NUM_F, NUM_B, NUM_B, BODY_F, BODY_F, BODY_F],
                     aligns=[wc, wr, wrn, wrn, wrn, wrn, wr, wc, wr],
                     fmt=[None, None, '#,##0', '#,##0', '#,##0.0', '+#,##0.0;-#,##0.0', None, None, None],
                     fills=[None, None, None, None, None, FILL_GREEN if d < 0 else FILL_RED, None, None, None],
                     zebra=(i % 2 == 1), widths=widths)
            r += 1
        r += 1
        self.note(ws, r, '读法：价差主要是运费、包装与区域供需，不是质量差。与客户谈“为什么你们贵”时，先拆'
                         '出厂/送到、含税/不含税、包装、运费四项，再谈价格。单点报价与区间中值混比会夸大价差。', 9, 44)
        r += 2
        ch = BarChart()
        ch.type, ch.style = 'bar', 10
        ch.title = '区域中值价（%s，%s）' % (M['unit'], D['spreads'][0]['date'])
        ch.height, ch.width = 8, 20
        rows = sorted(D['spreads'], key=lambda x: x['mid'])
        ch.add_data(Reference(ws, min_col=5, min_row=3, max_row=3 + len(rows)), titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=4, max_row=3 + len(rows)))
        ch.legend = None
        ws.add_chart(ch, 'A%d' % (r + 1))
        return '05_区域价差'

    # ------------------------------------------------------------ 06 成本毛利
    def s06(self):
        D, M = self.D, self.M
        ws = self.sheet('06_成本与毛利', RED)
        mg = D.get('margins') or []
        routes = []
        for m in mg:
            for k in (m.get('routes') or {}):
                if k not in routes:
                    routes.append(k)
        ncol = 4 + len(routes) + 2
        widths = [13] + [15] * len(routes) + [12, 46, 46]
        self.banner(ws, '成本结构与工艺路线毛利',
                    '成本不是售价，用于判断“价格-成本倒挂”与减产动机。只收录有明确来源的时点，不插值。'
                    '路线名称由 research.json 决定（如氨碱/联碱/天然气制/煤制气），本表不预设工艺。', ncol)
        self.header(ws, 3, ['日期'] + [r + '毛利' for r in routes] + ['数据单位', '口径 / 说明', '来源'], widths)
        r = 4
        if not mg or not routes:
            self.note(ws, r, '缺口：没有分工艺路线的毛利/成本数据。要判断“亏损为什么还不减产”必须补这一块；'
                             '拿不到就留空，不要用行业均值顶替。', ncol, 34, color=RED, fill=FILL_RED)
            return '06_成本与毛利'
        for i, m in enumerate(mg):
            rv = m.get('routes') or {}
            vals = [m.get('date')] + [rv.get(k) for k in routes] + [M['unit'], '毛利润（非现金流利润）；负值=亏损', m.get('src', '')]
            fonts = [BODY_F] + [NUM_B] * len(routes) + [BODY_F, BODY_F, SMALL_F]
            aligns = [wc] + [wrn] * len(routes) + [wc, wr, wr]
            fmts = [None] + ['+#,##0.0;-#,##0.0'] * len(routes) + [None, None, None]
            fills = [None] + [FILL_GREEN if (rv.get(k) or 0) < 0 else FILL_RED for k in routes] + [None, None, None]
            self.put(ws, r, vals, fonts=fonts, aligns=aligns, fmt=fmts, fills=fills,
                     zebra=(i % 2 == 1), widths=widths)
            r += 1

        r += 1
        self.header(ws, r, ['成本参考线', '数值', '单位', '日期', '来源', '落在哪个区间内'], [16, 12, 10, 12, 46, 34])
        r += 1
        for c in D.get('cost_lines') or []:
            inside = [k for k, w in D['win'].items() if w['low'] <= c['value'] <= w['high']]
            self.put(ws, r, [c['name'], c['value'], M['unit'], c.get('date'), c.get('src', ''),
                             '、'.join(inside) if inside else '高于所有窗口区间上限'],
                     fonts=[BODY_F, NUM_B, BODY_F, BODY_F, SMALL_F, BODY_F],
                     aligns=[wr, wrn, wc, wc, wr, wr], fmt=[None, '#,##0', None, None, None, None],
                     zebra=(r % 2 == 1))
            r += 1
        if not D.get('cost_lines'):
            self.note(ws, r, '缺口：未提供成本参考线（各工艺路线的完全成本），分位条上无法标出“价格 vs 成本”的位置。', 6, 30, color=RED)
            r += 1
        r += 1
        self.note(ws, r, '关键矛盾（事实层）：若部分工艺路线已出现负毛利而开工仍高，通常是停车重启成本与固定成本分摊使企业选择“以量补价”；'
                         '这是“价格在低位、供给却不缩”的常见解释，必须用 08 表的开工率与库存验证，不能只凭毛利推断。', 6, 46)
        return '06_成本与毛利'

    # ------------------------------------------------------------ 07 上游
    def s07(self):
        D = self.D
        ws = self.sheet('07_上游原料', AMBER)
        widths = [22, 12, 12, 22, 12, 8, 52, 46]
        self.banner(ws, '上游原料与成本传导',
                    '只列取得数字或明确来源的品种；拿不到的标“缺口”，不编区间、不给近似值。', 8)
        self.header(ws, 3, ['品种', '最新价', '单位', '变动', '日期', '方向', '传导逻辑', '来源 / 缺口说明'], widths)
        r = 4
        ups = D.get('upstream') or []
        for i, x in enumerate(ups):
            fill = FILL_RED if x.get('direction') == 'up' else (FILL_GREEN if x.get('direction') == 'down' else FILL_AMBER)
            self.put(ws, r, [x.get('name'), x.get('value') if x.get('value') is not None else '缺口',
                             x.get('unit', ''), x.get('chg', ''), x.get('date', ''),
                             {'up': '涨', 'down': '跌'}.get(x.get('direction'), '缺口'),
                             x.get('logic', ''), x.get('src', '')],
                     fonts=[BODY_B, NUM_B if x.get('value') is not None else BODY_F, BODY_F, BODY_B, BODY_F, BODY_B, BODY_F, SMALL_F],
                     aligns=[wr, wrn, wc, wc, wc, wc, wr, wr],
                     fmt=[None, '#,##0.00', None, None, None, None, None, None],
                     fills=[None, None, None, fill if x.get('value') is not None else None, None, None, None, None],
                     zebra=(i % 2 == 1), widths=widths)
            r += 1
        hint = (D.get('chain_hints') or {}).get('up') or []
        missing = [h for h in hint if not any(h in (x.get('name') or '') for x in ups)]
        if missing:
            self.put(ws, r, ['本品种常见上游（未取数）', '缺口', '', '—', '', '缺口',
                             '这些是研究阶段必须找到替代或补齐的品种', '补齐顺序见 references/research-playbook.md'],
                     fonts=[BODY_B, BODY_F, BODY_F, BODY_F, BODY_F, BODY_B, BODY_F, SMALL_F],
                     aligns=[wr, wrn, wc, wc, wc, wc, wr, wr],
                     fills=[None, FILL_RED, None, None, None, FILL_RED, None, None], widths=widths)
            ws.row_dimensions[r].height = 30
            r += 1
            for h in missing:
                self.put(ws, r, [h, '缺口', '', '—', '', '缺口', '未取得可引用报价', '—'],
                         fonts=[BODY_F, BODY_F, BODY_F, BODY_F, BODY_F, BODY_B, BODY_F, SMALL_F],
                         aligns=[wr, wrn, wc, wc, wc, wc, wr, wr], fills=[None, FILL_RED, None, None, None, FILL_RED, None, None])
                r += 1
        r += 1
        self.note(ws, r, '缺口说明：若原盐、合成氨、氯化铵等没有当期报价，就无法量化“原料每涨 100 元/吨 → 成本涨多少”。'
                         '行业报告常只作定性描述（如“原盐支撑成本”），不能替代数字；宁可留缺口。', 8, 40)
        return '07_上游原料'

    # ------------------------------------------------------------ 08 下游
    def s08(self):
        D, M = self.D, self.M
        ws = self.sheet('08_下游需求', GREEN)
        widths = [24, 12, 12, 24, 12, 8, 52, 46]
        self.banner(ws, '主要下游产品、开工与供需',
                    '下游开工率是本品种需求的先行指标；数字来自行业报告，逐条标注日期与统计范围。', 8)
        self.header(ws, 3, ['下游品种', '最新值', '单位', '变动 / 开工', '日期', '方向', '传导逻辑', '来源 / 缺口说明'], widths)
        r = 4
        dns = D.get('downstream') or []
        for i, x in enumerate(dns):
            fill = FILL_GREEN if x.get('direction') == 'down' else (FILL_RED if x.get('direction') == 'up' else FILL_AMBER)
            self.put(ws, r, [x.get('name'), x.get('value') if x.get('value') is not None else '缺口',
                             x.get('unit', ''), x.get('chg', ''), x.get('date', ''),
                             {'up': '涨', 'down': '跌'}.get(x.get('direction'), '缺口'),
                             x.get('logic', ''), x.get('src', '')],
                     fonts=[BODY_B, NUM_B if x.get('value') is not None else BODY_F, BODY_F, BODY_B, BODY_F, BODY_B, BODY_F, SMALL_F],
                     aligns=[wr, wrn, wc, wc, wc, wc, wr, wr],
                     fmt=[None, '#,##0.00', None, None, None, None, None, None],
                     fills=[None, None, None, fill if x.get('value') is not None else None, None, None, None, None],
                     zebra=(i % 2 == 1), widths=widths)
            r += 1
        hint = (D.get('chain_hints') or {}).get('down') or []
        missing = [h for h in hint if not any(h in (x.get('name') or '') for x in dns)]
        if missing:
            self.put(ws, r, ['本品种常见下游（未取数）', '缺口', '', '—', '', '缺口',
                             '需求端缺失会导致“只看供给”的片面结论', '补齐顺序见 references/research-playbook.md'],
                     fonts=[BODY_B, BODY_F, BODY_F, BODY_F, BODY_F, BODY_B, BODY_F, SMALL_F],
                     aligns=[wr, wrn, wc, wc, wc, wc, wr, wr],
                     fills=[None, FILL_RED, None, None, None, FILL_RED, None, None], widths=widths)
            r += 1

        r += 1
        self.header(ws, r, ['供需指标', '最新值', '单位', '日期', '变化 / 说明', '来源'], [26, 16, 10, 14, 46, 50])
        r += 1
        for i, b in enumerate(D.get('balance') or []):
            self.put(ws, r, [b.get('k'), b.get('v'), b.get('unit', ''), b.get('date'), b.get('prev'), b.get('src')],
                     fonts=[BODY_B, NUM_B, BODY_F, BODY_F, BODY_F, SMALL_F],
                     aligns=[wr, wrn, wc, wc, wr, wr], zebra=(i % 2 == 1))
            r += 1
        if not (D.get('balance') or []):
            self.note(ws, r, '缺口：没有供需与库存指标（开工率、周产量、厂库、进出口）。'
                             '没有这组数据就无法解释“价格下跌但供给是否收缩”。', 6, 30, color=RED, fill=FILL_RED)
            r += 1
        r += 1
        self.note(ws, r, '口径冲突提示：同一指标若出现两个口径（例如厂库 179 万吨 vs 167 万吨），必须并列并标注来源与日期，'
                         '不可混用或直接算环比。', 6, 34, color=AMBER, fill=FILL_AMBER)
        return '08_下游需求'

    # ------------------------------------------------------------ 09 事件
    def s09(self):
        D, M = self.D, self.M
        ws = self.sheet('09_事件时间线', AMBER)
        widths = [12, 8, 40, 14, 20, 70, 46]
        self.banner(ws, '事件时间线（与行情对齐）',
                    '只放能被来源支撑的事件；未能公开归因的异常波动单列在表尾，只列数据不写原因。', 7)
        self.header(ws, 3, ['日期', '类型', '事件', '当时价位(%s)' % M['unit'], '影响', '细节', '来源'], widths)
        r = 4
        if not (D.get('events') or []):
            self.note(ws, r, '缺口：没有事件时间线。价格波动一定会被客户追问“为什么”，没有事件就答不上来。', 7, 30, color=RED, fill=FILL_RED)
            r += 1
        for i, e in enumerate(sorted(D.get('events') or [], key=lambda x: x.get('date') or '')):
            imp = e.get('impact') or ''
            fill = FILL_GREEN if '利空' in imp else (FILL_RED if '利多' in imp else None)
            self.put(ws, r, [e.get('date'), e.get('tag'), e.get('title'), e.get('price_ref'), imp,
                             e.get('detail'), e.get('src')],
                     fonts=[BODY_F, BODY_B, BODY_B, NUM_B, BODY_B, BODY_F, SMALL_F],
                     aligns=[wc, wc, wr, wrn, wc, wr, wr], fmt=[None, None, None, '#,##0', None, None, None],
                     fills=[None, None, None, None, fill, None, None], zebra=(i % 2 == 1), widths=widths)
            r += 1

        un = [a for a in D.get('anomalies') or [] if not a.get('event')]
        if un:
            r += 1
            self.band(ws, r, '近一年 ≥%s%% 的异常波动中，以下未能找到公开归因（只列数据，不臆测原因）：' % M.get('anomaly_pct', 3.5), 7, RED)
            r += 1
            for i, a in enumerate(un):
                self.put(ws, r, [a['d'], '异常',
                                 '单日涨跌 %s（收盘 %s %s）' % (common.pct(a['pct']), common.fmt(a['c']), M['unit']),
                                 a['c'], '未归因',
                                 '未取得可引用的公开解释；建议以行业资讯快讯或当日持仓数据补证',
                                 '未取得可靠来源'],
                         fonts=[BODY_F, BODY_B, BODY_F, NUM_B, BODY_B, BODY_F, SMALL_F],
                         aligns=[wc, wc, wr, wrn, wc, wr, wr], fmt=[None, None, None, '#,##0', None, None, None],
                         zebra=(i % 2 == 1))
                r += 1
        return '09_事件时间线'

    # ------------------------------------------------------------ 10 事实卡
    def s10(self):
        D = self.D
        ws = self.sheet('10_销售事实卡', GREEN)
        widths = [10, 22, 26, 66, 44, 34]
        self.banner(ws, '销售可用事实（与客户对话时的“硬信息”）',
                    '每条都能指回价格表或来源；只陈述已经发生的事实。', 6)
        self.header(ws, 3, ['类别', '事实', '数值', '说明', '可引用来源', '使用提示'], widths)
        r = 4
        facts = D.get('facts') or []
        for i, f in enumerate(facts):
            self.put(ws, r, [f.get('kind'), f.get('k'), f.get('v'), f.get('note'), f.get('src', ''), f.get('tip', '')],
                     fonts=[BODY_B, BODY_B, NUM_B, BODY_F, SMALL_F, BODY_F],
                     aligns=[wc, wr, wr, wr, wr, wr], zebra=(i % 2 == 1), widths=widths)
            r += 1
        if not facts:
            self.note(ws, r, '缺口：没有整理销售事实卡。事实卡是从“价格表 + 事件 + 供需”里提炼的对话弹药，'
                             '建议至少写 6 条（价格、涨跌、分位、成本、库存、下游开工）。', 6, 34, color=RED, fill=FILL_RED)
            r += 1
        r += 1
        self.band(ws, r, '客户常问的问题 · 建议回应（只给事实，不给判断）', 6, GREEN)
        r += 1
        talks = D.get('talk') or []
        if not talks:
            self.note(ws, r, '缺口：没有准备客户问答。建议覆盖：① 现在什么价 ② 还能不能便宜 ③ 什么时候是底 ④ 别人为什么更便宜 ⑤ 库存压力大不大。', 6, 30, color=RED)
            return '10_销售事实卡'
        for i, t in enumerate(talks):
            ws.cell(row=r, column=1, value=t.get('q')).font = BODY_B
            ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True, vertical='top')
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
            c = ws.cell(row=r, column=2, value=t.get('a'))
            c.font = BODY_F
            c.alignment = Alignment(wrap_text=True, vertical='top')
            for col in range(1, 7):
                ws.cell(row=r, column=col).border = BOX
                ws.cell(row=r, column=col).fill = FILL_ZEBRA if i % 2 else FILL_W
            self.auto_height(ws, r, [t.get('q'), t.get('a')], [22, 180])
            r += 1
        return '10_销售事实卡'

    # ------------------------------------------------------------ 11 话术
    def s11(self):
        D, M = self.D, self.M
        ws = self.sheet('11_话术模板', NAVY)
        widths = [22, 40, 22, 30]
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        self.banner(ws, '客户微信 / 邮件话术（自动带入行情）',
                    '改左侧变量即可；正文不含任何方向性判断。生成逻辑与 HTML 看板第 09 节一致。', 4)
        r = 4
        self.header(ws, r, ['变量', '值（可改）', '说明', ''], widths)
        r += 1
        a = D.get('anchor')
        q = (M.get('suggest_quote') or (round(a['value'] * 1.01) if a else ''))
        for i, (k, v, note) in enumerate([
                ('客户 / 联系人', '（填客户姓名与厂别）', '称呼会出现在首行'),
                ('我方报价（含税送到）', q, '只填数字'),
                ('随附条件', M.get('suggest_term') or '30 天账期，5 车起送', '账期、起订量、包装'),
                ('渠道', '微信 / 邮件 / 短句', '三种正文见下方')]):
            self.put(ws, r, [k, v, note, None], fonts=[BODY_B, BODY_F, SMALL_F, BODY_F],
                     aligns=[wr, wr, wr, wr], fills=[FILL_AMBER if i % 2 == 0 else FILL_W, None, None, None])
            r += 1

        r += 1
        self.band(ws, r, '正文素材（可直接拼进微信 / 邮件）', 4, NAVY)
        r += 1
        lines = self._msg_lines()
        for i, (k, v) in enumerate(lines):
            ws.cell(row=r, column=1, value=k).font = BODY_B
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
            c = ws.cell(row=r, column=2, value=v)
            c.font, c.alignment = BODY_F, Alignment(wrap_text=True, vertical='center')
            for col in range(1, 5):
                ws.cell(row=r, column=col).border = BOX
                ws.cell(row=r, column=col).fill = FILL_ZEBRA if i % 2 else FILL_W
            self.auto_height(ws, r, [k, v], [22, 92])
            r += 1

        r += 1
        self.band(ws, r, '完整微信示例（替换客户名 / 报价后即可发）', 4, GREEN)
        r += 1
        body = self._msg_body('（客户姓名）', q if q else '（报价）', M.get('suggest_term') or '')
        ws.merge_cells(start_row=r, start_column=1, end_row=r + 17, end_column=4)
        c = ws.cell(row=r, column=1, value=body)
        c.font, c.alignment = Font(name=FONT, size=10, color=INK), Alignment(wrap_text=True, vertical='top', indent=1)
        for rr in range(r, r + 18):
            for col in range(1, 5):
                ws.cell(row=rr, column=col).border = BOX
        r += 19
        self.note(ws, r, '合规提示：正文中不要出现方向性判断与收益承诺；价格方向是判断，不是事实。', 4, 30, color=AMBER)
        return '11_话术模板'

    def _msg_lines(self):
        D, M = self.D, self.M
        a, L, c = D.get('anchor'), D.get('last') or {}, D['chg']
        out = []
        if a:
            extra = ''
            if a.get('range_lo') and a.get('range_hi') and a['range_lo'] != a['range_hi']:
                extra = '；同期区间 %s–%s %s' % (common.fmt(a['range_lo']), common.fmt(a['range_hi']), a.get('unit') or M['unit'])
            out.append(('1）现货', '%s %s %s（%s，%s）%s。' % (a.get('label'), common.fmt(a['value']),
                                                           a.get('unit') or M['unit'], a.get('date'),
                                                           a.get('basis') or '口径见附件', extra)))
        if L.get('close') is not None:
            out.append(('2）期货', '%s %s %s（%s 收盘，不含税），近 7 日 %s、近 30 日 %s、近 1 年 %s。'
                        % (M.get('exchange', ''), M.get('contract', ''), common.fmt(L['close']), L.get('date'),
                           common.pct((c.get('7d') or {}).get('pct')), common.pct((c.get('30d') or {}).get('pct')),
                           common.pct((c.get('1y') or {}).get('pct')))))
        w1, w3 = D['win'].get('1y'), D['win'].get('3y')
        if w1:
            out.append(('3）位置', '近 1 年区间 %s–%s %s，当前处于 %s 分位%s。'
                        % (common.fmt(w1['low']), common.fmt(w1['high']), M['unit'],
                           common.pct(w1['pct_rank'], 1),
                           '；近 3 年分位 %s' % common.pct(w3['pct_rank'], 1) if w3 else '')))
        mg = [m for m in (D.get('margins') or []) if m.get('routes')]
        if mg:
            m = mg[-1]
            out.append(('4）成本', '%s %s（毛利口径）。' % (m['date'], '、'.join(
                '%s %s' % (k, common.fmt_trim(v)) for k, v in m['routes'].items()))))
        bal = (D.get('balance') or [])[:3]
        if bal:
            out.append(('5）供需', '；'.join('%s %s' % (b.get('k'), b.get('v')) for b in bal) + '。'))
        sp = sorted(D.get('spreads') or [], key=lambda x: x['mid'])
        if sp:
            out.append(('6）区域', '%s %s（%s，出厂与送到混用，价差含运费）。'
                        % ('、'.join('%s %s' % (s['region'], common.fmt(s['mid'])) for s in sp),
                           M['unit'], sp[0]['date'])))
        if not out:
            out.append(('（无可用素材）', '本次研究尚未取得可对外引用的价格与产业数据，请先按 12 表补齐缺口再生成话术。'))
        return out

    def _msg_body(self, cust, quote, term):
        M = self.M
        head = '%s，您好！\n\n把今天能核对的%s行情数据发您，不含任何涨跌预测，供您内部比价和排采购节奏用：\n\n' % (cust, M['product'])
        mid = '\n'.join('| %s | %s' % kv for kv in self._msg_lines())
        tail = '\n\n我方报价：%s 元/吨%s。\n\n如果方便，我想确认三件事：本月用量、到货节奏、以及你们现在执行的结算方式——我按这个给您算到厂全成本，而不是只比单价。\n\n说明：以上现货为公开渠道口径，最终以当日实盘询价为准；我只提供已发生的数据，不做后市判断。' % (
            quote, '（%s）' % term if term else '')
        return head + mid + tail

    # ------------------------------------------------------------ 12 缺口
    def s12(self):
        D, M = self.D, self.M
        ws = self.sheet('12_数据缺口与方法', RED)
        widths = [26, 12, 74, 56, 40]
        self.banner(ws, '数据缺口、口径与方法',
                    '没有缺口说明的行情报告通常意味着没查到东西。以下缺口直接影响“能不能报出当前现货价”。', 5)
        self.header(ws, 3, ['缺口项', '状态', '具体说明', '对销售的影响', '补齐路径'], widths)
        r = 4
        gaps = D.get('gaps') or []
        if not gaps:
            self.note(ws, r, '未登记缺口。请确认每个字段确有来源；若确实完整，保留这一行作为声明。', 5, 26, color=AMBER, fill=FILL_AMBER)
            r += 1
        for i, g in enumerate(gaps):
            st = g.get('status', '缺口')
            fill = FILL_RED if st == '缺口' else (FILL_AMBER if st == '口径冲突' else FILL_GREEN)
            self.put(ws, r, [g.get('item'), st, g.get('detail'), g.get('impact'), g.get('fix') or '—'],
                     fonts=[BODY_B, BODY_B, BODY_F, BODY_F, BODY_F],
                     aligns=[wr, wc, wr, wr, wr], fills=[None, fill, None, None, None],
                     zebra=(i % 2 == 1), widths=widths)
            r += 1

        r += 1
        self.header(ws, r, ['口径提醒', '说明'], [26, 160])
        r += 1
        for i, cv in enumerate(D.get('caveats') or ['无']):
            ws.cell(row=r, column=1, value='提醒 %d' % (i + 1)).font = BODY_B
            ws.cell(row=r, column=2, value=cv).font = BODY_F
            for col in (1, 2):
                ws.cell(row=r, column=col).border = BOX
                ws.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical='top')
                ws.cell(row=r, column=col).fill = FILL_ZEBRA if i % 2 else FILL_W
            self.auto_height(ws, r, ['', cv], [26, 160])
            r += 1

        r += 1
        self.header(ws, r, ['来源', '日期', '类型', '链接'], [56, 12, 14, 80])
        r += 1
        for i, s in enumerate(D.get('sources') or []):
            ws.cell(row=r, column=1, value=s.get('name')).font = BODY_F
            ws.cell(row=r, column=2, value=s.get('date')).font = BODY_F
            ws.cell(row=r, column=3, value=s.get('type')).font = BODY_F
            url = s.get('url') or ''
            c = ws.cell(row=r, column=4, value=url)
            if url:
                c.hyperlink = url
                c.font = LINK_F
            for col in range(1, 5):
                ws.cell(row=r, column=col).border = BOX
                ws.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical='center')
                if i % 2:
                    ws.cell(row=r, column=col).fill = FILL_ZEBRA
            self.auto_height(ws, r, [s.get('name'), '', '', url], widths)
            r += 1
        if not (D.get('sources') or []):
            self.note(ws, r, '缺口：没有来源清单。无来源的数字不能对外引用。', 4, 26, color=RED, fill=FILL_RED)
            r += 1

        r += 1
        self.note(ws, r, '生成说明：本工作簿由 research.json 经 assemble.py 派生（data.json）后生成，'
                         '与同批 HTML 看板同源；涨跌幅、分位、价差均由序列直接计算，未做插值或平滑。'
                         '期货序列来自东方财富公开行情接口，现货与产业数据来自 12 表所列来源。', 4, 46)
        return '12_数据缺口与方法'

    # ------------------------------------------------------------ 组装
    def build(self, out_path):
        self.s00(); self.s01(); self.s02(); self.s03(); self.s04(); self.s05(); self.s06()
        self.s07(); self.s08(); self.s09(); self.s10(); self.s11(); self.s12()
        self.wb.active = 0
        for ws in self.wb.worksheets:
            ws.sheet_view.showGridLines = False
        self.wb.save(out_path)
        return self.wb.sheetnames, self.warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    D = common.load_json(a.data)
    b = Book(D)
    names, warns = b.build(a.out)
    for w in warns[:20]:
        common.warn(w)
    common.ok('Excel 已生成 %s（%d 表，%.1f KB）' % (a.out, len(names), os.path.getsize(a.out) / 1024))
    print('  ' + ' | '.join(names))


if __name__ == '__main__':
    main()
