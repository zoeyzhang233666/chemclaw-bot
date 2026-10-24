# -*- coding: utf-8 -*-
"""data.json -> 采购版工作簿（openpyxl）。表结构固定，内容全部来自 data.json。

用法：
  python build_xlsx.py data.json --out out/<品种>-<地区>_原料行情底稿_采购.xlsx

设计：
  * 每一张表都允许“缺数据”：缺的地方写缺口、写补齐路径，不留空白格，也不拿估算值填充；
  * 所有数字与 HTML 同源（都来自 data.json），天然一致；
  * 表名与编号不绑定任何品种，换品种直接用。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, Reference

# ---------------------------------------------------------------- 主题
INK, NAVY = '1A2233', '1F3A5F'
AMBER, AMBER_L = 'C8892B', 'FDF3DF'
GREEN, GREEN_L = '1E7A54', 'E8F5EF'
RED, RED_L = 'B23A48', 'FCEDEF'
GREY, GREY_L, LINE, WHITE = '6B7A90', 'F4F6F9', 'D8DEE8', 'FFFFFF'
FONT, MONO = '微软雅黑', 'Consolas'

TITLE_F = Font(name=FONT, size=16, bold=True, color=INK)
SUB_F = Font(name=FONT, size=9.5, color=GREY)
H_F = Font(name=FONT, size=10, bold=True, color=WHITE)
BODY_F = Font(name=FONT, size=10, color=INK)
BODY_B = Font(name=FONT, size=10, bold=True, color=INK)
SMALL_F = Font(name=FONT, size=9, color=GREY)
NUM_F = Font(name=MONO, size=10, color=INK)
NUM_B = Font(name=MONO, size=10.5, bold=True, color=INK)

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

NUMF = '#,##0.00'
NUMF0 = '#,##0'


class Book:
    def __init__(self, D):
        self.D = D
        self.M = D['meta']
        self.U = self.M.get('unit') or '元/吨'
        self.wb = Workbook()
        self.wb.remove(self.wb.active)
        self.warn = []
        self.names = []

    # ------------------------------------------------------------ 基础件
    def sheet(self, name, tab=NAVY):
        ws = self.wb.create_sheet(name)
        ws.sheet_properties.tabColor = tab
        ws.sheet_view.showGridLines = False
        ws.sheet_view.zoomScale = 90
        ws.freeze_panes = 'A4'
        self.names.append(name)
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

    def header(self, ws, row, cols, widths, height=32):
        for i, (nm, w) in enumerate(zip(cols, widths), start=1):
            c = ws.cell(row=row, column=i, value=nm)
            c.font, c.fill, c.alignment, c.border = H_F, FILL_HEAD, wc, BOX
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[row].height = height

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
        ws.row_dimensions[row].height = min(160, max(16, lines * 15))

    def put(self, ws, row, vals, fills=None, fonts=None, aligns=None, fmt=None, zebra=False, widths=None):
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=i)
            try:
                c.value = v
            except AttributeError:
                continue  # 合并单元格的从属格不可写，值已在左上角
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
        if widths:
            self.auto_height(ws, row, vals, widths)
        return row + 1

    def note(self, ws, row, text, ncol, color=GREY, fill=None, bold=False, width=None):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
        c = ws.cell(row=row, column=1, value=text)
        c.font = Font(name=FONT, size=9.5, color=color, bold=bold)
        c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True, indent=1)
        if fill:
            c.fill = fill
        n = common.cjk_width(text)
        ws.row_dimensions[row].height = min(140, max(18, 15 * (n // (max(30, (width or 130))) + 1)))
        for b in common.banned_hits(text):
            self.warn.append('说明行出现方向性表述「%s」' % b)
        return row + 1

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
        D, M, U = self.D, self.M, self.U
        ws = self.sheet('00_封面与结论', AMBER)
        widths = [24, 34, 30, 12, 40, 26]
        self.banner(ws, '%s · 原料行情底稿（采购）' % M['product'],
                    '品种：%s ｜ 规格：%s ｜ 采购点：%s ｜ 数据截至 %s ｜ 只陈述已发生事实，不预测价格'
                    % (M['product'], M.get('spec') or '见报价表', M.get('region') or '全国', M['asof']), 6, 40)
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        r = 4
        self.band(ws, r, '一句话结论（只描述现状，不含判断）', 6, AMBER)
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        c = ws.cell(row=r, column=1, value=D.get('summary') or '数据不足，尚未形成可陈述的现状。')
        c.font = Font(name=FONT, size=10, color=INK)
        c.fill = FILL_AMBER
        c.alignment = Alignment(wrap_text=True, vertical='center', indent=1)
        ws.row_dimensions[r].height = max(46, 16 * (common.cjk_width(D.get('summary') or '') // 150 + 1))
        r += 2
        self.header(ws, r, ['指标', '数值', '口径 / 日期', '标记', '来源', '备注'], widths)
        r += 1
        for i, row in enumerate(self._cards()):
            mark = row[3]
            fill_d = FILL_RED if mark == '缺口' else (FILL_GREEN if mark == '可引用' else None)
            r = self.put(ws, r, list(row), fills=[None, None, None, fill_d, None, None],
                         fonts=[BODY_B, NUM_B, BODY_F, BODY_B, BODY_F, SMALL_F],
                         fmt=[None, NUMF, None, None, None, None], zebra=(i % 2 == 1), widths=widths)
        r += 1
        r = self.band(ws, r, '⚠ 使用前必读（口径提醒）', 6, RED)
        r += 1
        for t in (D.get('caveats') or ['所有数字均标注日期与来源；引用前请核对当日实盘。']):
            r = self.note(ws, r, '· ' + t, 6, color=RED, width=140)
        r += 1
        r = self.band(ws, r, '本工作簿阅读顺序', 6, NAVY)
        r += 1
        for t in ['01→03：先看价在哪、怎么走、现在处什么位置（采购第一问）',
                  '04→05：再看为什么——上游成本与下游需求，各自带工艺路线依据',
                  '06→08：谁在检修/复产/投产、库存与开工怎么变、哪些事件与价格变化同期',
                  '09→10：可以对外说的话（只含事实）、以及这份底稿还缺什么']:
            r = self.note(ws, r, t, 6, width=140)
        return ws

    def _cards(self):
        D, M, U = self.D, self.M, self.U
        a, p = D.get('anchor'), D.get('primary') or {}
        out = []
        if a:
            out.append(['当前价（锚）', a['value'],
                        '%s · %s · %s · %s %s' % (a.get('date'), a.get('tax') or '', a.get('basis') or '',
                                                  common.fmt(a['value']), a.get('unit') or U),
                        '可引用', a.get('src') or '', a.get('note') or ''])
        else:
            out.append(['当前价（锚）', '缺口', '未取得六项口径齐全的报价', '缺口', '—', '见 10 表'])
        w90 = (p.get('win') or {}).get('90')
        if w90:
            out.append(['近 90 天位置', '%.0f%% 分位' % w90['pct_rank'],
                        '区间 %s–%s（%d 个报价点）' % (common.fmt(w90['low']), common.fmt(w90['high']), w90['n']),
                        '可引用', '本工作簿自算（逐点，不插值）', '区间位置 %.0f%%' % (w90.get('pos_in_range') or 0)])
        else:
            out.append(['近 90 天位置', '缺口', '该采购点报价点 < 3', '缺口', '—', '见 03 表'])
        for k, lbl in ((7, '近 7 天'), (30, '近 30 天'), (90, '近 90 天'), (365, '近 1 年')):
            c = (D.get('chg') or {}).get(k)
            if c:
                out.append([lbl + '变动', common.pct(c['pct']),
                            '对比 %s（%s）' % (c['from_date'], common.fmt(c['from_mid'])),
                            '可引用', '自算（真实报价点 %d 个）' % c['n_between'],
                            '%+.1f %s · 实际 %d 天' % (c['abs'], U, c['exact_days'])])
        pr = D.get('procurement') or {}
        if pr.get('inventory_days') is not None:
            out.append(['库存可支撑', '%s 天' % common.fmt(pr['inventory_days']),
                        '至 %s（按锚价日推算）' % (pr.get('inventory_cover_to') or '—'),
                        '假设值' if '示例' in (pr.get('notes') or '') else '可引用',
                        'procurement.inventory_days', pr.get('usage_note') or ''])
        sp = [s for s in (D.get('spreads') or []) if s.get('is_source')]
        if sp:
            s0 = sp[0]
            out.append(['同期价差', '%+d %s' % (s0['diff_vs_base'], U),
                        '%s vs %s（%s）' % (s0['point'], s0['base_point'], s0['date']),
                        '可引用', s0.get('src') or '', '含运费与提货方式差异，不等于纯地区溢价'])
        cl = (D.get('cost_lines') or [])
        if cl:
            out.append(['成本参考', '%s %s' % (common.fmt(cl[0]['value']), U), '%s · %s' % (cl[0].get('date') or '', cl[0].get('name') or ''),
                        '可引用' if not cl[0].get('derived') else '派生值', cl[0].get('src') or '', cl[0].get('note') or ''])
        if (D.get('gaps') or []):
            g = D['gaps'][0]
            out.append(['最大缺口', g['item'], g.get('status') or '缺口', '缺口', '—', g.get('impact') or ''])
        return out

    # ------------------------------------------------------------ 01 现货报价
    def s01(self):
        D, M, U = self.D, self.M, self.U
        ws = self.sheet('01_现货报价明细', AMBER)
        cols = ['采购点', '所属区域', '层级', '规格 / 执行标准', '报价类型', '低', '高', '中值', '单位',
                '含税', '提货方式', '数据日期', '可信度', '备注', '来源']
        widths = [18, 12, 8, 26, 14, 10, 10, 10, 10, 10, 20, 12, 8, 40, 40]
        self.banner(ws, '01 · 现货报价明细（六项口径逐条）',
                    '每条必须回答：哪个点、什么规格、多少钱、含不含税、怎么提货、哪天、谁说的。缺一项即不可比。单位 %s' % U, 15)
        self.header(ws, 4, cols, widths, 44)
        r = 5
        qs = sorted(D.get('quotes') or [], key=lambda x: (x['date'], x['point']), reverse=True)
        if not qs:
            self.note(ws, r, '缺口：没有任何可用报价。补齐：按 references/data-standard.md 的六项口径补 1 条。', 15, color=RED)
            return ws
        for i, q in enumerate(qs):
            r = self.put(ws, r, [q['point'], q.get('region') or '', q.get('tier') or '', q['spec'], q.get('quote_kind') or '',
                                 q['lo'], (q['hi'] if q['hi'] != q['lo'] else None), q['mid'], q.get('unit') or U,
                                 q['tax'], q['basis'], q['date'], q.get('conf') or '',
                                 q.get('note') or '', q.get('src') or ''],
                         fonts=[BODY_B, BODY_F, SMALL_F, BODY_F, SMALL_F, NUM_B, NUM_F, NUM_F, SMALL_F,
                                BODY_F, BODY_F, BODY_F, BODY_F, SMALL_F, SMALL_F],
                         aligns=[wr, wc, wc, wr, wr, wrn, wrn, wrn, wc, wc, wr, wc, wc, wr, wr],
                         fmt=[None] * 5 + [NUMF, NUMF, NUMF, None] + [None] * 6, zebra=(i % 2 == 1), widths=widths)
        r += 1
        self.note(ws, r, '读法：厂商挂牌价是“报价”，不等于成交；竞拍成交价才是可验证成交；生意社基准价等指数口径是结算参考价，含调整系数，与罐区谈价不同口径。外币报价（CFR 等）不能与人民币价直接相减。', 15, width=200)
        return ws

    # ------------------------------------------------------------ 02 系列与走势
    def s02(self):
        D, M, U = self.D, self.M, self.U
        ws = self.sheet('02_报价序列与走势', '2A4A72')
        self.banner(ws, '02 · 报价序列（采购点分列）与走势图',
                    '只放真实报价点，不插值、不留空白日。同一采购点若同日有多个口径（如指数口径与成交口径），在 01 表分列，此表只取主口径。', 8)
        pts = D.get('points') or []
        if not pts:
            self.note(ws, 4, '缺口：没有报价序列，走势图与分位无法生成。', 8, color=RED)
            return ws
        r = 4
        first_data_row = None
        for pt in pts:
            s = D['series'].get(pt['point'])
            if not s:
                continue
            r = self.band(ws, r, '%s ｜ %d 个报价点 ｜ %s → %s ｜ %s' % (
                pt['point'], s['n'], s['start'], s['last']['d'],
                (s.get('meta') or {}).get('basis') or '口径见 01 表'), 6, '2A4A72')
            r += 1
            cols = ['日期', '低', '高', '中值', '单位', '来源']
            widths = [14, 12, 12, 12, 10, 60]
            self.header(ws, r, cols, widths)
            r += 1
            start_r = r
            for row in s['rows']:
                r = self.put(ws, r, [row['d'], row['lo'], (row['hi'] if row['hi'] != row['lo'] else None),
                                     row['mid'], U, row.get('src') or ''],
                             fonts=[BODY_F, NUM_F, NUM_F, NUM_B, SMALL_F, SMALL_F],
                             aligns=[wc, wrn, wrn, wrn, wc, wr],
                             fmt=[None, NUMF, NUMF, NUMF, None, None])
            end_r = r - 1
            if first_data_row is None:
                first_data_row = (pt['point'], start_r, end_r)
            r += 1
        if first_data_row:
            name, s1, s2 = first_data_row
            ch = LineChart()
            ch.title = '%s 报价中值走势（真实报价点）' % name
            ch.y_axis.title = U
            ch.x_axis.title = '日期'
            ch.height, ch.width = 9, 22
            data = Reference(ws, min_col=4, min_row=s1 - 1, max_row=s2)
            cats = Reference(ws, min_col=1, min_row=s1, max_row=s2)
            ch.add_data(data, titles_from_data=True)
            ch.set_categories(cats)
            ch.legend = None
            ws.add_chart(ch, 'H4')
        r_text = max(r, 5)
        self.note(ws, r_text, '说明：横轴只有真实报价日，折线并不代表每日行情；日期跳跃处不能读成“平稳”。分位与涨跌幅见 03 表。', 8, width=160)
        return ws

    # ------------------------------------------------------------ 03 涨跌与分位
    def s03(self):
        D, M, U = self.D, self.M, self.U
        ws = self.sheet('03_区间涨跌与分位', AMBER)
        widths = [16, 12, 12, 12, 12, 12, 14, 10, 10, 10, 10]
        self.banner(ws, '03 · 区间涨跌与历史分位',
                    '基准日 = 该窗口内最后一个不晚于截止日的真实报价日；实际天数与期间报价点一并列出，样本薄的地方请勿当连续行情引用。', 11)
        r = 4
        r = self.band(ws, r, 'A. 区间涨跌', 11, AMBER)
        r += 1
        self.header(ws, r, ['采购点', '窗口', '基准日', '基准价', '当前日', '当前价', '变动', '涨跌幅',
                            '期间报价点', '实际天数', '单位'], widths)
        r += 1
        lbl = {7: '7 天', 30: '30 天', 90: '90 天', 365: '1 年', 1095: '3 年'}
        n_chg = 0
        for pt, s in (D.get('series') or {}).items():
            for k in sorted(s.get('chg') or {}, key=int):
                c = s['chg'][k]
                r = self.put(ws, r, [pt, lbl.get(int(k), str(k) + ' 天'), c['from_date'], c['from_mid'],
                                     s['last']['d'], c['mid'], c['abs'],
                                     (round(c['pct'] / 100, 6) if c['pct'] is not None else None),
                                     c['n_between'], c['exact_days'], U],
                             fonts=[BODY_B, BODY_F, BODY_F, NUM_F, BODY_F, NUM_F, NUM_F, NUM_B, NUM_F, NUM_F, SMALL_F],
                             aligns=[wr, wc, wc, wrn, wc, wrn, wrn, wrn, wrn, wrn, wc],
                             fmt=[None, None, None, NUMF, None, NUMF, NUMF, '0.00%', NUMF0, NUMF0, None],
                             fills=[None] * 6 + [FILL_GREEN if c['abs'] < 0 else FILL_RED, None, None, None, None])
                n_chg += 1
        if not n_chg:
            r = self.note(ws, r, '缺口：报价点不足，无法形成区间涨跌。', 11, color=RED)
        r += 1
        r = self.band(ws, r, 'B. 历史区间与分位', 11, AMBER)
        r += 1
        self.header(ws, r, ['采购点', '窗口', '样本', '起始日', '低点', '低点日期', '高点', '高点日期',
                            '中位数', '当前分位', '区间位置'], widths)
        r += 1
        n_win = 0
        for pt, s in (D.get('series') or {}).items():
            for k in sorted(s.get('win') or {}, key=int):
                w = s['win'][k]
                r = self.put(ws, r, [pt, lbl.get(int(k), str(k) + ' 天'), w['n'], w['start'], w['low'], w['low_date'],
                                     w['high'], w['high_date'], w['median'],
                                     w['pct_rank'] / 100, (w['pos_in_range'] or 0) / 100],
                             fonts=[BODY_B, BODY_F, NUM_F, BODY_F, NUM_F, BODY_F, NUM_F, BODY_F, NUM_F, NUM_B, NUM_F],
                             aligns=[wr, wc, wrn, wc, wrn, wc, wrn, wc, wrn, wrn, wrn],
                             fmt=[None, None, NUMF0, None, NUMF, None, NUMF, None, NUMF, '0.0%', '0%'])
                n_win += 1
        if not n_win:
            r = self.note(ws, r, '缺口：窗口内报价点 < 3，分位不计算（不用估算值凑）。', 11, color=RED)
        r += 1
        self.note(ws, r, '分位 = 窗口内低于当前价的报价点占比；区间位置 = (当前价−低点)/(高点−低点)。两者都是“这几次报价的范围”，不是连续行情统计量。', 11, width=170)
        return ws

    # ------------------------------------------------------------ 04 区域价差
    def s04(self):
        D, M, U = self.D, self.M, self.U
        ws = self.sheet('04_区域价差', '2A4A72')
        widths = [12, 20, 20, 12, 12, 14, 20, 12, 40, 40]
        self.banner(ws, '04 · 区域价差（只在同日比）',
                    '跨日期相减得到的是时间差，不是地区差。价差里含运费、仓储、升贴水与提货方式差异，别当成“纯地区溢价”。', 10)
        r = 4
        self.header(ws, r, ['日期', '采购点', '基准点', '该点中值', '基准中值', '差（该点−基准）',
                            '提货方式', '货源属性', '备注', '来源'], widths)
        r += 1
        sps = D.get('spreads') or []
        if not sps:
            r = self.note(ws, r, '缺口：没有同日多采购点报价，无法判断调货空间。补齐：对 2–3 个区域同日询价，或从同一期资讯取多区域同日报价。', 10, color=RED)
        for i, s in enumerate(sps):
            r = self.put(ws, r, [s['date'], s['point'], s['base_point'], s['mid'], s['base_mid'],
                                 s['diff_vs_base'], s['basis'], '当前货源' if s.get('is_source') else '备选',
                                 s.get('note') or '', s.get('src') or ''],
                         fonts=[BODY_F, BODY_B, BODY_F, NUM_F, NUM_F, NUM_B, BODY_F, BODY_F, SMALL_F, SMALL_F],
                         aligns=[wc, wr, wr, wrn, wrn, wrn, wr, wc, wr, wr],
                         fmt=[None, None, None, NUMF, NUMF, NUMF, None, None, None, None],
                         fills=[None] * 5 + [FILL_GREEN if s['diff_vs_base'] < 0 else FILL_RED] + [None] * 4,
                         zebra=(i % 2 == 1), widths=widths)
        r += 1
        for g in (D.get('spread_groups') or []):
            r = self.band(ws, r, '价差走势：%s（基准 %s）' % (g['name'], g['base']), 10, '2A4A72')
            r += 1
            pts = list(g['series'].keys())
            self.header(ws, r, ['日期'] + pts, [12] + [14] * (len(pts)), 28)
            r += 1
            cats = sorted({x['d'] for p in pts for x in g['series'][p]})
            s1 = r
            for d in cats:
                vals = [d] + [next((x['mid'] for x in g['series'][p] if x['d'] == d), None) for p in pts]
                r = self.put(ws, r, vals, fonts=[BODY_F] + [NUM_F] * len(pts),
                             aligns=[wc] + [wrn] * len(pts), fmt=[None] + [NUMF] * len(pts))
            s2 = r - 1
            if len(pts) >= 2 and s2 > s1:
                ch = LineChart()
                ch.title = g['name']
                ch.y_axis.title = g.get('unit') or U
                ch.height, ch.width = 9, 20
                ch.add_data(Reference(ws, min_col=2, max_col=1 + len(pts), min_row=s1 - 1, max_row=s2), titles_from_data=True)
                ch.set_categories(Reference(ws, min_col=1, min_row=s1, max_row=s2))
                ws.add_chart(ch, 'J%d' % max(4, s1))
            r += 1
            if g.get('note') or g.get('src'):
                r = self.note(ws, r, (g.get('note') or '') + ' 来源：' + (g.get('src') or ''), 10, width=170)
            r += 1
        return ws

    # ------------------------------------------------------------ 05 成本
    def s05(self):
        D, M, U = self.D, self.M, self.U
        ws = self.sheet('05_上游成本拆解', AMBER)
        widths = [26, 18, 12, 10, 12, 12, 12, 12, 50, 44]
        self.banner(ws, '05 · 上游成本：单耗 × 单价 = 每吨原料成本',
                    '单耗必须来自公开工艺参数或企业披露；拿不到加工费就不合计。完全成本、现金成本、原料成本三种口径不能混用。', 10)
        r = 4
        r = self.band(ws, r, 'A. 上游原料价格（成本项）', 10, AMBER)
        r += 1
        self.header(ws, r, ['上游品种', '角色', '数值', '单位', '变化', '日期', '单耗', '影响方向',
                            '传导逻辑', '来源'], widths)
        r += 1
        ups = (D.get('chain') or {}).get('upstream') or []
        dir_cn = {'up': '抬升成本', 'down': '压低成本', 'gap': '缺口', 'flat': '持平/未知'}
        for i, x in enumerate(ups):
            val = x.get('value')
            rng = ''
            if val is None and x.get('range_lo') is not None:
                rng = '%s–%s' % (common.fmt(x['range_lo']), common.fmt(x['range_hi']))
            r = self.put(ws, r, [x['name'], x.get('role') or '', val if val is not None else (rng or '缺口'),
                                 x.get('unit') or '', x.get('chg') or '', x.get('date') or '',
                                 x.get('ratio') or '', dir_cn.get(x.get('direction'), ''),
                                 x.get('logic') or '', x.get('src') or ''],
                         fonts=[BODY_B, BODY_F, NUM_B, SMALL_F, SMALL_F, BODY_F, SMALL_F, BODY_F, SMALL_F, SMALL_F],
                         aligns=[wr, wr, wrn, wc, wr, wc, wr, wc, wr, wr],
                         fmt=[None, None, NUMF, None, None, None, None, None, None, None],
                         fills=[None] * 7 + ([FILL_RED if x.get('direction') == 'up' else
                                              FILL_GREEN if x.get('direction') == 'down' else FILL_AMBER]
                                             if x.get('direction') else [None])[:1] + [None] * 2,
                         zebra=(i % 2 == 1), widths=widths)
        r += 1
        r = self.band(ws, r, 'B. 成本线（用于判断报价在成本之上还是之下）', 10, AMBER)
        r += 1
        self.header(ws, r, ['成本口径', '工艺路线', '数值', '单位', '日期', '类型', '是否派生', '说明', '来源', ''], widths)
        r += 1
        cls = D.get('cost_lines') or []
        if not cls:
            r = self.note(ws, r, '缺口：没有成本数字。补齐：从企业公告、期货公司成本模型或当地煤价/气价自行折算（单耗需注明来源）。', 10, color=RED)
        for i, c in enumerate(cls):
            r = self.put(ws, r, [c['name'], c.get('route') or '', c['value'], U, c.get('date') or '',
                                 c.get('type') or '', '派生值' if c.get('derived') else '原始披露',
                                 c.get('note') or '', c.get('src') or '', ''],
                         fonts=[BODY_B, BODY_F, NUM_B, SMALL_F, BODY_F, BODY_F, BODY_F, SMALL_F, SMALL_F, BODY_F],
                         aligns=[wr, wc, wrn, wc, wc, wc, wc, wr, wr, wr],
                         fmt=[None, None, NUMF, None, None, None, None, None, None, None],
                         fills=[None] * 6 + ([FILL_AMBER] if c.get('derived') else [None]), zebra=(i % 2 == 1), widths=widths)
        r += 1
        r = self.band(ws, r, 'C. 工艺路线单耗表（原料成本 = 单耗 × 单价）', 10, AMBER)
        r += 1
        self.header(ws, r, ['工艺路线', '原料/加工项', '单耗数量', '单耗单位', '单价', '每吨成本', '日期',
                            '路线合计', '说明', '来源'], widths)
        r += 1
        rc = D.get('route_costs') or []
        if not rc:
            r = self.note(ws, r, '缺口：未提供任何工艺路线单耗（routes）。补齐：按 references/chain-mapping.md 列出主要路线的单耗与当期原料价。', 10, color=RED)
        for rt in rc:
            s0 = r
            for ln in rt['lines']:
                r = self.put(ws, r, [rt['name'], ln['item'], ln.get('qty'), ln.get('unit') or '',
                                     ln.get('price'), ln.get('cost'), ln.get('date') or '',
                                     '', '', ln.get('src') or ''],
                             fonts=[BODY_B, BODY_F, NUM_F, SMALL_F, NUM_F, NUM_F, BODY_F, NUM_B, SMALL_F, SMALL_F],
                             aligns=[wr, wr, wrn, wc, wrn, wrn, wc, wrn, wr, wr],
                             fmt=[None, None, NUMF, None, NUMF, NUMF, None, NUMF, None, None])
            rng = 'A%d:H%d' % (s0, r - 1)
            if r - 1 > s0:
                ws.merge_cells('A%d:A%d' % (s0, r - 1))
            if rt.get('total') is not None:
                ws.cell(row=s0, column=8, value=rt['total']).number_format = NUMF
                ws.cell(row=s0, column=8).font = NUM_B
            else:
                ws.cell(row=s0, column=8, value='分项不全，未合计').font = SMALL_F
            r = self.note(ws, r, rt.get('note') or '（无说明）', 10, width=170)
            r = self.note(ws, r, '来源：' + (rt.get('src') or '未标注'), 10, width=170)
        return ws

    # ------------------------------------------------------------ 06 下游需求
    def s06(self):
        D, M = self.D, self.M
        ws = self.sheet('06_下游需求与开工', '2A4A72')
        widths = [26, 18, 12, 16, 40, 16, 12, 46, 44]
        self.banner(ws, '06 · 下游需求与开工',
                    '下游只列按工艺路线成立的需求项；开工率与产品价格都带日期。缺口留空并说明补齐方式，不估算。', 9)
        r = 4
        self.header(ws, r, ['下游品种/环节', '角色', '数值', '单位', '变化', '单耗', '日期', '传导逻辑', '来源'], widths)
        r += 1
        dns = (D.get('chain') or {}).get('downstream') or []
        dir_cn = {'up': '改善需求', 'down': '拖累需求', 'gap': '缺口', 'flat': '持平/未知'}
        if not dns:
            r = self.note(ws, r, '缺口：没有下游数据。补齐：按 references/chain-mapping.md 列出主要下游路线及其开工率/产品价格。', 9, color=RED)
        for i, x in enumerate(dns):
            val = x.get('value')
            disp = val if val is not None else ((('%s–%s' % (common.fmt(x['range_lo']), common.fmt(x['range_hi'])))
                                                if x.get('range_lo') is not None else '缺口'))
            r = self.put(ws, r, [x['name'], x.get('role') or '', disp, x.get('unit') or '', x.get('chg') or '',
                                 x.get('ratio') or '', x.get('date') or '', x.get('logic') or '', x.get('src') or ''],
                         fonts=[BODY_B, BODY_F, NUM_B, SMALL_F, SMALL_F, SMALL_F, BODY_F, SMALL_F, SMALL_F],
                         aligns=[wr, wr, wrn, wc, wr, wr, wc, wr, wr],
                         fmt=[None, None, NUMF, None, None, None, None, None, None],
                         fills=[FILL_GREEN if x.get('direction') == 'down' else FILL_RED if x.get('direction') == 'up' else None],
                         zebra=(i % 2 == 1), widths=widths)
        r += 1
        r = self.band(ws, r, '产业链断点自证（凭什么说这两者是上下游）', 9, '2A4A72')
        r += 1
        self.header(ws, r, ['关系', '从', '到', '单耗', '占比/规模', '工艺依据', '核对结论', '来源', ''], widths)
        r += 1
        pf = D.get('chain_proof') or []
        if not pf:
            r = self.note(ws, r, '缺口：没有断点自证表。补齐：每一环给出工艺依据（反应/分离路线）与占比，否则可能把无关品种算成上下游。', 9, color=RED)
        for i, p in enumerate(pf):
            r = self.put(ws, r, [p['relation'], p['from'], p['to'], p.get('ratio') or '', p.get('share') or '',
                                 p.get('evidence') or '', '通过' if p.get('checked') else '未通过（数字不可外引）',
                                 p.get('src') or '', ''],
                         fonts=[BODY_F, BODY_B, BODY_B, SMALL_F, SMALL_F, SMALL_F, BODY_B, SMALL_F, BODY_F],
                         aligns=[wc, wr, wr, wr, wr, wr, wc, wr, wr],
                         fills=[None] * 6 + ([FILL_RED if not p.get('checked') else FILL_GREEN]) + [None, None],
                         zebra=(i % 2 == 1), widths=widths)
        return ws

    # ------------------------------------------------------------ 07 供需库存
    def s07(self):
        D, M = self.D, self.M
        ws = self.sheet('07_供给库存与开工', '2A4A72')
        widths = [34, 22, 12, 34, 34, 46]
        self.banner(ws, '07 · 供给、库存与开工',
                    '同一指标两个口径时分列两条，不可相加、不可互相替代。这一节回答“为什么贵/为什么跌”。', 6)
        r = 4
        self.header(ws, r, ['指标', '数值', '日期', '环比/前值', '口径与样本', '来源'], widths)
        r += 1
        b = D.get('balance') or []
        if not b:
            r = self.note(ws, r, '缺口：没有库存/开工数据。补齐：港口库存、工厂库存、待发订单、开工率、周产量、进口量、到港量。', 6, color=RED)
        for i, x in enumerate(b):
            r = self.put(ws, r, [x['k'], x['v'], x['date'], x['prev'] or '', x.get('scope') or '', x.get('src') or ''],
                         fonts=[BODY_B, NUM_B, BODY_F, BODY_F, SMALL_F, SMALL_F],
                         aligns=[wr, wrn, wc, wr, wr, wr], zebra=(i % 2 == 1), widths=widths)
        return ws

    # ------------------------------------------------------------ 08 事件时间线
    def s08(self):
        D, M, U = self.D, self.M, self.U
        ws = self.sheet('08_事件时间线', AMBER)
        widths = [12, 10, 40, 12, 12, 46, 46, 12, 12, 40]
        self.banner(ws, '08 · 产业事件时间线（采购相关）',
                    '检修/复产/投产/库存/物流/政策/需求。每条标证据级别；同时给出“事件日”与“首个报价响应日”，不把先后说成因果。', 10)
        r = 4
        self.header(ws, r, ['事件日期', '类型', '事件', '对价格影响', '证据级别', '当时发生了什么',
                            '之后的变化', '首个报价响应日', '当日报价', '来源'], widths)
        r += 1
        evs = D.get('events') or []
        if not evs:
            r = self.note(ws, r, '缺口：没有已证实事件。补齐：按 references/event-verification.md 逐条核对来源级别。', 10, color=RED)
        for i, e in enumerate(evs):
            r = self.put(ws, r, [e['date'], e.get('tag') or '', e['title'], e.get('impact') or '',
                                 e.get('evidence') or '', e.get('detail') or '', e.get('after') or '',
                                 e.get('mark_d') or '', e.get('mark_price'), e.get('src') or ''],
                         fonts=[BODY_F, BODY_F, BODY_B, BODY_F, BODY_F, SMALL_F, SMALL_F, BODY_F, NUM_F, SMALL_F],
                         aligns=[wc, wc, wr, wc, wc, wr, wr, wc, wrn, wr],
                         fmt=[None, None, None, None, None, None, None, None, NUMF, None],
                         fills=[None] * 3 + ([FILL_GREEN if '利空' in (e.get('impact') or '')
                                              else FILL_RED if '利多' in (e.get('impact') or '') else None]) + [None] * 6,
                         zebra=(i % 2 == 1), widths=widths)
        r += 1
        rej = D.get('events_rejected') or []
        if rej:
            r = self.band(ws, r, '未采纳消息（仅传闻/待确认，未进入时间线）', 10, RED)
            r += 1
            self.header(ws, r, ['日期', '类型', '消息', '证据级别', '', '为什么没采纳', '', '', '', '来源'],
                        widths)
            r += 1
            for i, e in enumerate(rej):
                r = self.put(ws, r, [e['date'], e.get('tag') or '', e['title'], e.get('evidence') or '', '',
                                     e.get('detail') or '', '', '', '', e.get('src') or ''],
                             fonts=[BODY_F, BODY_F, BODY_F, BODY_B, BODY_F, SMALL_F, BODY_F, BODY_F, BODY_F, SMALL_F],
                             aligns=[wc, wc, wr, wc, wc, wr, wr, wr, wr, wr], zebra=(i % 2 == 1), widths=widths)
        return ws

    # ------------------------------------------------------------ 09 采购可用事实与话术
    def s09(self):
        D, M, U = self.D, self.M, self.U
        ws = self.sheet('09_可用事实与话术', GREEN)
        widths = [10, 16, 40, 46, 40, 70]
        self.banner(ws, '09 · 采购可用事实 与 供应商常见问答',
                    '每条事实都能回溯到来源；问答只含事实，不含方向判断。可直接复制到微信/邮件。', 6)
        r = 4
        r = self.band(ws, r, 'A. 可用事实（对外可引用）', 6, GREEN)
        r += 1
        self.header(ws, r, ['类别', '事实', '数值', '补充说明', '来源', ''], widths)
        r += 1
        fs = D.get('facts') or []
        if D.get('anchor'):
            a = D['anchor']
            r = self.put(ws, r, ['价格（锚）', '当前价（%s）' % (a.get('point') or ''), a['value'],
                                 '%s · %s · %s' % (a.get('date'), a.get('tax') or '', a.get('basis') or ''),
                                 a.get('src') or '', ''],
                         fonts=[BODY_F, BODY_B, BODY_B, SMALL_F, SMALL_F, BODY_F],
                         aligns=[wc, wr, wrn, wr, wr, wr], fmt=[None, None, NUMF, None, None, None], widths=widths)
        if not fs and not D.get('anchor'):
            r = self.note(ws, r, '缺口：没有登记可用事实。补齐：把 01–07 表里最该被引用的 8–12 条挑出来。', 6, color=RED)
        for i, f in enumerate(fs):
            r = self.put(ws, r, [f.get('kind') or '', f.get('k') or '', f.get('v') or '', f.get('note') or '',
                                 f.get('src') or '', ''],
                         fonts=[BODY_F, BODY_B, BODY_B, SMALL_F, SMALL_F, BODY_F],
                         aligns=[wc, wr, wr, wr, wr, wr], zebra=(i % 2 == 1), widths=widths)
        r += 1
        r = self.band(ws, r, 'B. 供应商常见问答（只含事实）', 6, GREEN)
        r += 1
        self.header(ws, r, ['#', '供应商可能问', '你可以这样答', '', '', ''], widths)
        r += 1
        tk = D.get('talk') or []
        if not tk:
            r = self.note(ws, r, '缺口：没有准备问答。补齐：把采购最常被问的 5–8 个问题写出来，答案只用事实。', 6, color=RED)
        for i, x in enumerate(tk):
            ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
            r = self.put(ws, r, [i + 1, x.get('q') or '', x.get('a') or '', '', '', ''],
                         fonts=[BODY_F, BODY_B, BODY_F, BODY_F, BODY_F, BODY_F],
                         aligns=[wc, wr, wr, wr, wr, wr], widths=[10, 16, 190])
        r += 1
        pr = D.get('procurement') or {}
        r = self.band(ws, r, 'C. 我方采购参数（库存/用量/商务条件）', 6, GREEN)
        r += 1
        for k, v in [('库存天数', pr.get('inventory_days')), ('库存可支撑至', pr.get('inventory_cover_to')),
                     ('月度用量（吨）', pr.get('monthly_usage')), ('补单频率', pr.get('purchase_frequency')),
                     ('当前货源点', '、'.join(pr.get('current_source_points') or [])),
                     ('商务条件', '；'.join(pr.get('contract_terms') or [])), ('说明', pr.get('notes'))]:
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
            r = self.put(ws, r, [k, v if v is not None else '未填', '', '', '', ''],
                         fonts=[BODY_B, BODY_F, BODY_F, BODY_F, BODY_F, BODY_F], aligns=[wc, wr, wr, wr, wr, wr])
        return ws

    # ------------------------------------------------------------ 10 缺口与来源
    def s10(self):
        D, M = self.D, self.M
        ws = self.sheet('10_缺口与来源', RED)
        widths = [30, 12, 56, 40, 40]
        self.banner(ws, '10 · 数据缺口、口径冲突与来源清单',
                    '缺口清单比结论更重要：它决定这份底稿能不能直接拿去做采购决策。', 5)
        r = 4
        r = self.band(ws, r, 'A. 数据缺口 / 口径冲突 / 待更新', 5, RED)
        r += 1
        self.header(ws, r, ['项目', '状态', '具体情况', '对采购的影响', '补齐路径'], widths)
        r += 1
        gs = D.get('gaps') or []
        if gs:
            self.note(ws, r, '缺口共 %d 条（状态：%s）。' % (len(gs), '、'.join(sorted({g.get('status') or '' for g in gs}))), 5, width=200)
            r += 1
        else:
            r = self.note(ws, r, '未登记缺口。如确实全部字段有来源，请保留一条说明；否则逐条补进 gaps。', 5)
        for i, g in enumerate(gs):
            f = FILL_RED if g.get('status') == '缺口' else (FILL_AMBER if g.get('status') == '口径冲突' else None)
            r = self.put(ws, r, [g['item'], g.get('status') or '', g.get('detail') or '', g.get('impact') or '',
                                 g.get('fix') or ''],
                         fonts=[BODY_B, BODY_B, BODY_F, SMALL_F, SMALL_F],
                         aligns=[wr, wc, wr, wr, wr], fills=[None, f, None, None, None],
                         zebra=(i % 2 == 1), widths=widths)
        r += 1
        r = self.band(ws, r, 'B. 来源清单', 5, NAVY)
        r += 1
        self.header(ws, r, ['来源名称', '日期', '类型', '链接', '备注'], widths)
        r += 1
        for i, s in enumerate(D.get('sources') or []):
            url = s.get('url') or ''
            r = self.put(ws, r, [s.get('name') or '', s.get('date') or '', s.get('type') or '', url, ''],
                         fonts=[BODY_F, BODY_F, BODY_F, SMALL_F, BODY_F], aligns=[wr, wc, wc, wr, wr],
                         zebra=(i % 2 == 1), widths=widths)
            if url.startswith('http'):
                c = ws.cell(row=r - 1, column=4)
                c.hyperlink = url
                c.font = Font(name=FONT, size=9, color='1F4E8C', underline='single')
        return ws

    # ------------------------------------------------------------ 99 方法与字段
    def s99(self):
        ws = self.sheet('99_方法与字段口径', GREY)
        widths = [30, 90]
        self.banner(ws, '99 · 方法与字段口径',
                    '这份工作簿是怎么算出来的、每个字段什么意思、哪些数不能互相运算。', 2)
        r = 4
        self.header(ws, r, ['项目', '说明'], widths)
        r += 1
        rows = [
            ('数据主线', '现货报价序列（采购点维度）。期货仅在 00 表作为对照，不参与首屏结论。'),
            ('【六项口径】', '每一条现货报价必须同时具备：采购点 point、规格 spec、含税 tax、提货方式 basis、日期 date、来源 src。缺一项即视为“不可比”。'),
            ('区间涨跌', '基准日 = 窗口起点之前在序列中的最后一个真实报价日；不插值、不取月初月初对齐。实际天数与期间报价点一并列出。'),
            ('历史分位', '窗口内报价中值 ≤ 当前价的个数 / 样本数。样本 < 3 不计算。它衡量“在这几次报价里算高还是低”，不是连续概率。'),
            ('区间位置', '(当前价 − 区间低点) / (高点 − 低点)。与分位不同，它反映离上下沿的距离。'),
            ('区域价差', '只在同一天比较两个采购点。价差里含运费、仓储、升贴水与提货方式差异，不能直接叫“地区溢价”。'),
            ('原料成本', '单耗 × 单价（单位统一到吨/千标方/千度）。单耗必须来自公开工艺参数或企业披露，并在“说明”列注明来源性质。'),
            ('完全/现金/原料成本', '三种口径不能混用，也不能相加。表内“类型”列已标注。'),
            ('库存口径', '不同资讯商的库存样本不同（如“港口总库存”与“社会库存”），表内分列并注明样本范围，禁止相加。'),
            ('事件证据级别', '公开报道（可回溯到媒体原文）> 机构观点（资讯商/期货公司研判）> 传闻（只进“未采纳消息”）> 待确认。'),
            ('先后与因果', '事件日期先于价格变化，只说明“同期发生”，不构成因果。表内同时给出事件日与首个报价响应日。'),
            ('禁止事项', '不预测价格、不给买卖时点建议、不编造数字、不把缺失值当 0、不把不同口径的数放进同一个减法。'),
        ]
        for i, (k, v) in enumerate(rows):
            r = self.put(ws, r, [k, v], fonts=[BODY_B, BODY_F], aligns=[wr, wr],
                         fills=[FILL_AMBER if k.startswith('【') or k == '禁止事项' else None, None],
                         zebra=(i % 2 == 1), widths=widths)
        return ws

    # ------------------------------------------------------------ 汇总
    def build(self, out_path):
        order = [self.s00, self.s01, self.s02, self.s03, self.s04, self.s05,
                 self.s06, self.s07, self.s08, self.s09, self.s10, self.s99]
        for fn in order:
            fn()
        # 封面挪到最前
        self.wb.move_sheet('00_封面与结论', offset=-(len(self.wb.sheetnames) - 1))
        for ws in self.wb.worksheets:
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.orientation = 'landscape'
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        self.wb.save(out_path)
        return {'path': out_path, 'sheets': self.wb.sheetnames, 'bytes': os.path.getsize(out_path),
                'warn': self.warn}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    D = common.load_json(a.data)
    r = Book(D).build(a.out)
    for w in r['warn']:
        common.warn(w)
    common.ok('Excel 已生成 %s（%.0f KB，%d 表）' % (r['path'], r['bytes'] / 1024, len(r['sheets'])))
    print('  ' + ' / '.join(r['sheets']))
    if r['warn']:
        sys.exit(1)


if __name__ == '__main__':
    main()
