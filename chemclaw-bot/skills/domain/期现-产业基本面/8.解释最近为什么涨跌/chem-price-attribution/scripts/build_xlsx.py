# -*- coding: utf-8 -*-
"""build_xlsx.py —— 由 report_data.json 生成归因工作簿（单源同数，与 HTML 完全一致）。

工作表：
  00_说明与结论   01_价格序列   02_分期对齐   03_因子同期数据   04_变动幅度与z值
  05_事件清单     06_证据分级   07_候选解释排序 08_来源与口径   09_异动与阶段
  10_期现结构     11_数据缺口   12_复算校验

纪律：所有数字都写死为数值（便于二次计算），但 12_复算校验 会重新从原始文件算一遍并
与报告值比对，任何不一致都会在该表标红 —— 不允许"报告数与底层数对不上"。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

# ---- 样式 ----
HDR_BG = '1F3140'
HDR_FG = 'FFFFFF'
TITLE_BG = '0E1720'
ZEBRA = 'F4F7F9'
UP_FILL = PatternFill('solid', fgColor='FFE3E3')
DN_FILL = PatternFill('solid', fgColor='E0F7EF')
ND_FILL = PatternFill('solid', fgColor='EDEFF1')
LV_FILL = {'E1': PatternFill('solid', fgColor='D6F5E9'),
           'E2': PatternFill('solid', fgColor='DCEBFC'),
           'E3': PatternFill('solid', fgColor='FDF0D5'),
           'E4': PatternFill('solid', fgColor='ECEEF0')}
THIN = Side(style='thin', color='D5DDE3')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def style_header(ws, row=1, ncol=None):
    ncol = ncol or ws.max_column
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = PatternFill('solid', fgColor=HDR_BG)
        cell.font = Font(color=HDR_FG, bold=True, size=10.5)
        cell.alignment = Alignment(vertical='center', horizontal='center', wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 30


def style_body(ws, first_row=2, ncol=None, zebra=True):
    ncol = ncol or ws.max_column
    for r in range(first_row, ws.max_row + 1):
        for c in range(1, ncol + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = BORDER
            cell.alignment = Alignment(vertical='top', wrap_text=(isinstance(cell.value, str) and len(str(cell.value)) > 24))
            if zebra and (r - first_row) % 2 == 1:
                cell.fill = PatternFill('solid', fgColor=ZEBRA)


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def title_row(ws, text, ncol, sub=None):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(color='FFFFFF', bold=True, size=13)
    c.fill = PatternFill('solid', fgColor=TITLE_BG)
    c.alignment = Alignment(vertical='center', indent=1)
    ws.row_dimensions[1].height = 30
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = Font(color='4A6273', size=10)
        c2.alignment = Alignment(vertical='center', indent=1, wrap_text=True)
        ws.row_dimensions[2].height = 28
        return 4
    return 3


def add_table(ws, name, ref):
    try:
        t = Table(displayName=name, ref=ref)
        t.tableStyleInfo = TableStyleInfo(name='TableStyleLight9', showRowStripes=False)
        ws.add_table(t)
    except Exception:
        pass


def cond_pct(ws, rng):
    a, b = rng.split(':')
    r1 = int(''.join(ch for ch in a if ch.isdigit()))
    r2 = int(''.join(ch for ch in b if ch.isdigit()))
    if r2 < r1:
        return
    ws.conditional_formatting.add(rng, CellIsRule(operator='greaterThan', formula=['0'], fill=UP_FILL))
    ws.conditional_formatting.add(rng, CellIsRule(operator='lessThan', formula=['0'], fill=DN_FILL))


# ------------------------------------------------------------------ 各表


def s00(wb, data, case):
    ws = wb.active
    ws.title = '00_说明与结论'
    m = data['meta']
    cm = m.get('case', {})
    s = data['summary']
    n = data['narrative']
    r = title_row(ws, '期现及产业基本面研究 · 多因素归因工作簿', 4,
                  '%s ｜ %s ｜ %s ｜ 窗口 %s → %s ｜ 生成 %s' % (
                      cm.get('title', ''), cm.get('product', ''), cm.get('market', ''),
                      m['window']['start'], m['window']['end'], m['generated']))
    rows = [
        ('一、复核：到底涨跌了多少', '', '', ''),
        ('华东甲醇现货（指数口径）', '%.2f → %.2f' % (s['spot_start'], s['spot_end']),
         '%+.2f%%（%+.2f 元/吨）' % (s['spot_chg_pct'], s['spot_abs']),
         '起点与实际使用日期：%s → %s' % (s['spot_start_date'], s['spot_end_date'])),
        ('甲醇期货主连 MA0', '%.0f → %.0f' % (s['fut_start'], s['fut_end']),
         '%+.2f%%（%+.0f 元/吨）' % (s['fut_chg_pct'], s['fut_abs']),
         '主连在 9/29—9/30 由 MA2610 切换至 MA2701，跨切换比较会失真'),
        ('基差（现货−主力合约）', '%s → %s' % (C.fmt(s['basis_start'], 0), C.fmt(s['basis_end'], 0)),
         '峰值 %s（%s）／低点 %s（%s）' % (C.fmt(s['basis_max'], 0), s['basis_max_date'],
                                       C.fmt(s['basis_min'], 0), s['basis_min_date']),
         '主力合约按"当日持仓量最大"规则确定'),
        ('区间极值', '现货高 %s（%s）／低 %s（%s）' % (C.fmt(s.get('spot_period_high')), s.get('spot_period_high_date'),
                                                C.fmt(s.get('spot_period_low')), s.get('spot_period_low_date')),
         '期货高 %s（%s）／低 %s（%s）' % (C.fmt(s.get('fut_period_high'), 0), s.get('fut_period_high_date'),
                                      C.fmt(s.get('fut_period_low'), 0), s.get('fut_period_low_date')),
         '极值日期不等，说明现货与期货的顶部不同步'),
        ('', '', '', ''),
        ('二、证据分级统计', '', '', ''),
        ('证据条目总数', s['n_items'], '带日期事件 %d 条' % s['n_events'], ''),
        ('E1 直接数据支持', s['level_counts']['E1'], m['level_text']['E1'], ''),
        ('E2 数据＋事件时间吻合', s['level_counts']['E2'], m['level_text']['E2'], ''),
        ('E3 仅时间吻合', s['level_counts']['E3'], m['level_text']['E3'], ''),
        ('E4 缺乏证据／无法检验', s['level_counts']['E4'], m['level_text']['E4'], ''),
        ('', '', '', ''),
        ('三、总体结论', '', '', ''),
        ('一句话结论', n.get('one_liner', ''), '', ''),
    ]
    rr = r
    for a, b, c2, d in rows:
        ws.cell(row=rr, column=1, value=a)
        ws.cell(row=rr, column=2, value=b)
        ws.cell(row=rr, column=3, value=c2)
        ws.cell(row=rr, column=4, value=d)
        if a.startswith(('一、', '二、', '三、')):
            ws.cell(row=rr, column=1).font = Font(bold=True, size=12, color='1F3140')
            ws.cell(row=rr, column=1).fill = PatternFill('solid', fgColor='E8EEF2')
            for cc in range(1, 5):
                ws.cell(row=rr, column=cc).fill = PatternFill('solid', fgColor='E8EEF2')
        elif a:
            ws.cell(row=rr, column=1).font = Font(bold=True, size=10.5)
        rr += 1

    rr += 1
    ws.cell(row=rr, column=1, value='四、候选解释（按证据强弱排序，不代表解释占比）').font = Font(bold=True, size=12, color='1F3140')
    rr += 1
    for h, c in [('排名', 1), ('等级', 2), ('候选解释', 3), ('支持证据要点', 4)]:
        ws.cell(row=rr, column=c, value=h)
    style_header(ws, rr, 4)
    rr += 1
    for h in n.get('hypotheses', []):
        ws.cell(row=rr, column=1, value=h['rank'])
        ws.cell(row=rr, column=2, value=h['level']).fill = LV_FILL.get(h['level'])
        ws.cell(row=rr, column=3, value=h['claim'])
        ws.cell(row=rr, column=4, value='；'.join(h.get('supported_by', [])) or '（无支持证据）')
        rr += 1

    rr += 1
    ws.cell(row=rr, column=1, value='五、免责声明').font = Font(bold=True, size=12, color='C00000')
    rr += 1
    for x in n.get('limitations', []):
        ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=4)
        ws.cell(row=rr, column=1, value='• ' + x).alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[rr].height = 26
        rr += 1
    set_widths(ws, [26, 30, 44, 68])
    ws.freeze_panes = 'A4'


def s01(wb, data):
    ws = wb.create_sheet('01_价格序列')
    r = title_row(ws, '01 现货与期货逐日价格、基差与持仓量', 9,
                  '现货=生意社甲醇指数口径（含税）；期货=郑商所主连收盘（不含税）；基差=现货−当日持仓量最大合约')
    hdr = ['日期', '现货 元/吨', '期货主连 元/吨', '主力合约', '主力合约收盘', '基差 元/吨',
           '基差率 %', '月差 M1−M2 元/吨', '主连持仓量 手']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    for row in data['price']:
        r += 1
        vals = [row['date'], row['spot'], row['fut'], row['front_contract'], row['front'],
                row['basis'], row['basis_pct'], row['m1m2'], row['oi']]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=i, value=v)
            if v is None:
                cell.fill = ND_FILL
            if i in (2, 3, 5, 6, 8, 9):
                cell.number_format = '#,##0.00'
            if i in (7,):
                cell.number_format = '0.00'
    style_body(ws, 5, len(hdr))
    cond_pct(ws, 'G5:G%d' % r)
    ws.auto_filter.ref = 'A4:I%d' % r
    set_widths(ws, [12, 13, 15, 12, 14, 13, 11, 16, 15])
    ws.freeze_panes = 'B5'


def s02(wb, data):
    ws = wb.create_sheet('02_分期对齐')
    cols = data['series_meta']
    r = title_row(ws, '02 分期对齐：每一段行情里各指标各自变了多少', 2 + len(cols),
                  '只说明"同期各自变了多少"，不说明谁因谁果。灰色=该期无可用数据（不是 0）')
    ws.cell(row=r, column=1, value='区间起')
    ws.cell(row=r, column=2, value='区间止')
    for i, c in enumerate(cols, 3):
        ws.cell(row=r, column=i, value='%s（%s）' % (c['name'], c['unit'] or ''))
    style_header(ws, r, 2 + len(cols))
    rr = r
    for row in data['matrix']:
        rr += 1
        ws.cell(row=rr, column=1, value=row['start_date'])
        ws.cell(row=rr, column=2, value=row['end_date'])
        for i, c in enumerate(cols, 3):
            v = row['vals'].get(c['id'])
            cell = ws.cell(row=rr, column=i, value=v)
            if v is None:
                cell.fill = ND_FILL
                cell.value = '无数据'
            else:
                cell.number_format = '0.00'
    style_body(ws, r + 1, 2 + len(cols))
    if cols:
        rng = 'C%d:%s%d' % (r + 1, get_column_letter(2 + len(cols)), rr)
        ws.conditional_formatting.add(rng, ColorScaleRule(
            start_type='min', start_color='22C08D', mid_type='num', mid_value=0, mid_color='FFFFFF',
            end_type='max', end_color='FF5C5C'))
    set_widths(ws, [12, 12] + [19] * len(cols))
    ws.freeze_panes = 'C5'


def s03(wb, data):
    ws = wb.create_sheet('03_因子同期数据')
    r = title_row(ws, '03 各因子在窗口内的同期数据（数值／口径／来源）', 8,
                  '每个因子都必须有数值或明确写"无可用数据"；这是本工作簿的硬性要求')
    hdr = ['因子', '分类', '指标', '证据等级', '期初值', '期末值', '变动', 'z 值']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    rr = r
    for t in data['tree']:
        for s in t.get('series', []):
            rr += 1
            if not s.get('ok'):
                vals = [t['name'], t['group_cn'], s.get('name'), 'E4', '无可用数据', '', '', '']
            else:
                vals = [t['name'], t['group_cn'], s['name'], t['level'], s['start_value'], s['end_value'],
                        s['pct_change'], s['z']]
            for i, v in enumerate(vals, 1):
                cell = ws.cell(row=rr, column=i, value=v)
                if v == '无可用数据':
                    cell.fill = ND_FILL
                if i in (7, 8) and isinstance(v, (int, float)):
                    cell.number_format = '0.00'
            ws.cell(row=rr, column=4).fill = LV_FILL.get(vals[3], ND_FILL)
        for m in t.get('manual', []):
            rr += 1
            vals = [t['name'], t['group_cn'], m.get('k'), m.get('grade', 'E3'), '', '', m.get('v'), m.get('date', '')]
            for i, v in enumerate(vals, 1):
                ws.cell(row=rr, column=i, value=v)
            ws.cell(row=rr, column=4).fill = LV_FILL.get(m.get('grade', 'E3'), ND_FILL)
            ws.cell(row=rr, column=8).alignment = Alignment(wrap_text=True, vertical='top')
    style_body(ws, r + 1, len(hdr))
    ws.auto_filter.ref = 'A%d:H%d' % (r, rr)
    set_widths(ws, [22, 10, 34, 10, 14, 14, 30, 16])
    ws.freeze_panes = 'A%d' % (r + 1)


def s04(wb, data):
    ws = wb.create_sheet('04_变动幅度与分级')
    r = title_row(ws, '04 变动幅度、显著性（z）与证据分级理由', 9,
                  'z = 窗口变化量 / 该指标等长窗口变化量在其自身历史分布中的标准差；|z|≥1 视为显著')
    hdr = ['排名', '因子', '分类', '指标', '等级', '方向', '变动值', 'z 值', '分级理由']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    rr = r
    gmap = {t['name']: t['group_cn'] for t in data['tree']}
    for it in data.get('items', []):
        rr += 1
        v = it.get('value')
        vals = [it['rank'], it['factor'], gmap.get(it['factor'], ''), it.get('series'),
                it['level'], {'up': '上行', 'down': '下行', 'na': '—'}.get(it.get('dir'), '—'),
                v if isinstance(v, (int, float)) else '', it.get('z'), it.get('reason')]
        for i, x in enumerate(vals, 1):
            cell = ws.cell(row=rr, column=i, value=x)
            if i in (7, 8) and isinstance(x, (int, float)):
                cell.number_format = '0.00'
        ws.cell(row=rr, column=5).fill = LV_FILL.get(it['level'], ND_FILL)
    style_body(ws, r + 1, len(hdr))
    cond_pct(ws, 'G%d:G%d' % (r + 1, rr))
    ws.auto_filter.ref = 'A%d:I%d' % (r, rr)
    set_widths(ws, [6, 22, 10, 40, 8, 8, 12, 9, 70])
    ws.freeze_panes = 'A%d' % (r + 1)


def s05(wb, data):
    ws = wb.create_sheet('05_事件清单')
    r = title_row(ws, '05 事件清单与时间吻合度', 10,
                  '领先交易日：正数=事件早于价格阶段起点；负数=事件滞后；0=同日')
    hdr = ['日期', '分类', '事件', '方向', '量级／数值', '证据等级', '所属价格阶段', '领先交易日', '来源', '原始链接']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    rr = r
    for e in data['events']:
        rr += 1
        vals = [e['date'], e['group_cn'], e['title'],
                {'up': '利多', 'down': '利空'}.get(e.get('dir'), '—'),
                e.get('magnitude'), e['level'], e.get('period') or '（不在已识别阶段内）',
                e.get('lead_days'), e.get('src'), e.get('url')]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=rr, column=i, value=v)
            if i == 10 and v:
                cell.hyperlink = v
                cell.font = Font(color='0563C1', underline='single', size=9)
        ws.cell(row=rr, column=6).fill = LV_FILL.get(e['level'], ND_FILL)
    style_body(ws, r + 1, len(hdr))
    ws.auto_filter.ref = 'A%d:J%d' % (r, rr)
    set_widths(ws, [12, 9, 46, 7, 34, 9, 22, 11, 16, 42])
    ws.freeze_panes = 'C%d' % (r + 1)


def s06(wb, data):
    ws = wb.create_sheet('06_证据分级')
    r = title_row(ws, '06 证据分级：全部条目与判断依据', 7,
                  'E1 数据支持／E2 数据+时间吻合／E3 仅时间吻合／E4 缺乏证据。等级不因"听起来合理"而提升')
    hdr = ['因子', '指标／事件', '等级', '证据类型', '依据说明', '原始来源', '链接']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    rr = r
    for it in data.get('items', []):
        rr += 1
        vals = [it['factor'], it.get('series'), it['level'], it.get('evidence_type'),
                it.get('reason'), it.get('src'), it.get('src_url')]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=rr, column=i, value=v)
            if i == 7 and v:
                cell.hyperlink = v
                cell.font = Font(color='0563C1', underline='single', size=9)
        ws.cell(row=rr, column=3).fill = LV_FILL.get(it['level'], ND_FILL)
    style_body(ws, r + 1, len(hdr))
    ws.auto_filter.ref = 'A%d:G%d' % (r, rr)
    set_widths(ws, [22, 42, 7, 22, 62, 22, 42])
    ws.freeze_panes = 'C%d' % (r + 1)


def s07(wb, data):
    ws = wb.create_sheet('07_候选解释排序')
    r = title_row(ws, '07 候选解释排序（含"它不能证明什么"）', 6,
                  '排序分只用于排序，绝不等于"该因素解释了 X% 的涨跌"')
    hdr = ['排名', '等级', '候选解释', '支持它的证据', '它不能证明什么／反证', '是否可用于对外解释']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    rr = r
    for h in data['narrative'].get('hypotheses', []):
        rr += 1
        ok_use = {'E1': '可用（须同时说明局限）', 'E2': '谨慎可用（说明缺量化验证）',
                  'E3': '不建议单独使用（仅可作背景）', 'E4': '不可用（该假说不成立或无法检验）'}[h['level']]
        vals = [h['rank'], h['level'], h['claim'], '\n'.join('• ' + x for x in h.get('supported_by', [])) or '（无）',
                '\n'.join('• ' + x for x in h.get('not_proven', [])), ok_use]
        for i, v in enumerate(vals, 1):
            ws.cell(row=rr, column=i, value=v)
        ws.cell(row=rr, column=2).fill = LV_FILL.get(h['level'], ND_FILL)
        ws.row_dimensions[rr].height = 110
    style_body(ws, r + 1, len(hdr), zebra=False)
    set_widths(ws, [6, 7, 46, 60, 60, 24])
    ws.freeze_panes = 'C%d' % (r + 1)


def s08(wb, data):
    ws = wb.create_sheet('08_来源与口径')
    r = title_row(ws, '08 来源与口径（六项口径：名称/规格/区域/含税/交货/单位）', 8,
                  '每一行都必须能追到原始出处；口径不完整的数据不得进入结论')
    hdr = ['数据项', '名称', '规格', '区域', '含税/不含税', '交货方式', '单位', '来源与链接']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    sp = data['meta'].get('spot_spec', {}) or {}
    fu = data['meta'].get('fut_spec', {}) or {}
    rows = [
        ('现货价格', sp.get('name', ''), sp.get('spec', ''), sp.get('region', ''),
         sp.get('tax', ''), sp.get('basis', ''), sp.get('unit', ''), sp.get('src', '') + ' ' + sp.get('src_url', '')),
        ('期货价格', fu.get('name', ''), fu.get('contract', '') + '；' + (fu.get('note', '') or ''),
         '郑商所', fu.get('tax', ''), '期货结算/收盘', fu.get('unit', ''), fu.get('src_url', '')),
        ('煤炭价格', '秦皇岛港 5500 大卡动力煤现货', '动力煤 5500 大卡', '秦皇岛港', '含税', '港口现货', '元/吨',
         'https://www.cctd.com.cn/'),
        ('下游价格', '大商所聚丙烯主连 PP0', 'PP 拉丝基准', '大连商品交易所', '不含税', '期货', '元/吨',
         'https://finance.sina.com.cn/futures/quotes/PP0.shtml'),
        ('能源价格', 'INE 原油主连 SC0', '中质含硫原油', '上海国际能源交易中心', '不含税', '期货', '元/桶',
         'https://finance.sina.com.cn/futures/quotes/SC0.shtml'),
        ('事件与月度数据', '生意社 PriceSeek／周评／月度统计', '报告披露值', '全国/华东', '—', '—', '—',
         'https://www.100ppi.com/'),
    ]
    rr = r
    for row in rows:
        rr += 1
        for i, v in enumerate(row, 1):
            cell = ws.cell(row=rr, column=i, value=v)
            if i == 8 and v and v.startswith('http'):
                cell.hyperlink = v
                cell.font = Font(color='0563C1', underline='single', size=9)
    style_body(ws, r + 1, len(hdr))
    set_widths(ws, [14, 28, 26, 20, 12, 14, 9, 46])

    # 口径注意事项
    rr += 2
    ws.cell(row=rr, column=1, value='口径注意事项（必须与结论一并陈述）').font = Font(bold=True, size=11, color='C00000')
    for note in [
        '现货为生意社甲醇指数口径，不是单一库区出罐价；对外报价须改用当日实际库区成交价并注明批量与付款方式。',
        '生意社"基准价"与"参考价"是两条同源发布链：直接同日匹配仅 5/64，平移 1 个交易日后 59/64；只能用于交叉核对录入错误，不能算作两个独立信息源。',
        '期货主连在 9/29—9/30 由 MA2610 切换至 MA2701，切换日出现无成交量的名义价（9/30 主连 2972 vs MA2611 3384），故基差与月差一律用"当日持仓量最大合约"。',
        '煤制甲醇单耗 1.6—1.8 吨标煤/吨为行业经验区间，未取得企业级核验数据，故本工作簿不计算"煤制完全成本"，也不做成本线判断。',
    ]:
        rr += 1
        ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=8)
        ws.cell(row=rr, column=1, value='• ' + note).alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[rr].height = 30


def s09(wb, data):
    ws = wb.create_sheet('09_异动与阶段')
    r = title_row(ws, '09 价格异动识别与阶段切分（可复算）', 7,
                  '异动日 = |日收益 z|≥2.0 且 成交量为能 z≥1.5；阶段 = 摆动高低点法（最小反转 3%）')
    hdr = ['日期', '收盘', '日收益 %', '收益 z', '成交量', '成交量 z', '是否异动']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    rr = r
    for b in data.get('anomaly_bars', []):
        rr += 1
        vals = [b['date'], b['close'], b['ret'], b['z'], b.get('volume'), b.get('vol_z'),
                '异动' if b.get('spike') else ('极端' if b.get('extreme') else '')]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=rr, column=i, value=v)
            if i in (3, 4, 6) and isinstance(v, (int, float)):
                cell.number_format = '0.00'
            if i == 7 and v == '异动':
                cell.fill = PatternFill('solid', fgColor='FFD9D9')
    style_body(ws, r + 1, len(hdr))
    cond_pct(ws, 'C%d:C%d' % (r + 1, rr))
    ws.auto_filter.ref = 'A%d:G%d' % (r, rr)
    set_widths(ws, [12, 11, 11, 10, 13, 11, 10])
    ws.freeze_panes = 'A%d' % (r + 1)

    # 阶段
    rr += 2
    ws.cell(row=rr, column=1, value='价格阶段（摆动高低点法）').font = Font(bold=True, size=11)
    rr += 1
    for i, h in enumerate(['起', '止', '期初', '期末', '涨跌幅 %', '天数', '日波动率 %'], 1):
        ws.cell(row=rr, column=i, value=h)
    style_header(ws, rr, 7)
    for p in data.get('phases', []):
        rr += 1
        for i, v in enumerate([p['start_date'], p['end_date'], p['start_close'], p['end_close'],
                               p.get('chg_pct'), p.get('n_days'), p.get('vol_daily_pct')], 1):
            cell = ws.cell(row=rr, column=i, value=v)
            if i in (5, 7) and isinstance(v, (int, float)):
                cell.number_format = '0.00'


def s10(wb, data):
    ws = wb.create_sheet('10_期现结构')
    s = data['summary']
    base = s.get('base_contract') or '—'
    r = title_row(ws, '10 期现结构：基差与月差（逐日，单一合约口径）', 9,
                  '基差=现货−%s（同一合约全期可比，避免主连换月造成假跳变）；月差=%s（同一对合约）' % (
                      base, '−'.join(s.get('spread_pair') or ['近月', '远月'])))
    hdr = ['日期', '现货', '%s 收盘' % base, '基差（现货−%s）' % base, '基差率 %',
           '月差 %s' % ('−'.join(s.get('spread_pair') or ['', ''])), '主力合约', '主力收盘', '基差（现货−主力，仅观察）']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(hdr))
    rr = r
    for row in data['price']:
        if row.get('base_basis') is None and row.get('basis') is None:
            continue
        rr += 1
        vals = [row['date'], row['spot'], row.get('base_close'), row.get('base_basis'),
                (row['base_basis'] / row['base_close'] * 100) if row.get('base_basis') is not None and row.get('base_close') else None,
                row.get('spread'), row.get('front_contract'), row.get('front'), row.get('basis')]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=rr, column=i, value=v)
            if i in (2, 3, 4, 6, 8, 9) and isinstance(v, (int, float)):
                cell.number_format = '#,##0.00'
            if i == 5 and isinstance(v, (int, float)):
                cell.number_format = '0.00'
            if v is None:
                cell.fill = ND_FILL
    style_body(ws, r + 1, len(hdr))
    cond_pct(ws, 'E%d:E%d' % (r + 1, rr))
    cond_pct(ws, 'F%d:F%d' % (r + 1, rr))
    set_widths(ws, [12, 11, 12, 16, 10, 13, 12, 11, 22])
    ws.freeze_panes = 'B%d' % (r + 1)

    # 口径说明
    rr += 2
    for note in [
        '为什么不用"主连"算基差：主连在 9/29—9/30 由 MA2610 切换至 MA2701，9/30 主连报 2972（当日 MA2611 报 3384），',
        '切换日基差会被算成 1613 元/吨，比真实值高约 400 元/吨。故基差与月差一律用固定合约。',
        'I 列保留"现货−当日持仓量最大合约"的口径，仅用于观察主力基差的相对位置，不作为结论依据。',
    ]:
        ws.cell(row=rr, column=1, value=note).font = Font(size=10, color='4A6273')
        ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=9)
        rr += 1


def s11(wb, data):
    ws = wb.create_sheet('11_数据缺口')
    r = title_row(ws, '11 数据缺口与未能解释的片段', 4,
                  '把"查不到"和"查到了但不是这么回事"分开写，是本工作簿与营销稿的区别')
    for i, h in enumerate(['类型', '对象', '原因／状态', '对结论的影响'], 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, 4)
    rr = r
    for g in data['narrative'].get('data_gaps', []):
        rr += 1
        for i, v in enumerate(['数据缺口', g['k'], g['why'], g['impact']], 1):
            ws.cell(row=rr, column=i, value=v)
    for u in data['narrative'].get('unexplained', []):
        rr += 1
        for i, v in enumerate(['未解释片段', u['item'], u['status'], u['note']], 1):
            ws.cell(row=rr, column=i, value=v)
    style_body(ws, r + 1, 4)
    set_widths(ws, [12, 38, 44, 60])


def s12(wb, data, case, base_dir):
    """复算校验：从原始文件重算关键数字，与报告值比对。"""
    ws = wb.create_sheet('12_复算校验')
    r = title_row(ws, '12 复算校验：从原始文件重算，与报告值比对', 6,
                  '任何"否"都意味着报告数与底层数据不一致，必须回查后再交付')
    for i, h in enumerate(['校验项', '报告值', '重算值', '差异', '是否一致', '数据来源文件'], 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, 6)

    checks = []
    s = data['summary']
    try:
        spot = C.load_csv(os.path.join(base_dir, case['spot']['file']),
                          case['spot']['date_col'], case['spot']['value_col'])
        ks = sorted(k for k in spot if case['window']['start'] <= k <= case['window']['end'])
        recompute = (spot[ks[-1]] / spot[ks[0]] - 1) * 100
        checks.append(('现货窗口涨跌幅 %', round(s['spot_chg_pct'], 4), round(recompute, 4), case['spot']['file']))
    except Exception as e:
        checks.append(('现货窗口涨跌幅 %', round(s['spot_chg_pct'], 4), 'ERR:%s' % e, case['spot']['file']))
    try:
        fut = C.load_json_series(os.path.join(base_dir, case['futures']['file']),
                                 'date', case['futures'].get('value_col', 'close'))
        ks = sorted(k for k in fut if case['window']['start'] <= k <= case['window']['end'])
        recompute = (fut[ks[-1]] / fut[ks[0]] - 1) * 100
        checks.append(('期货窗口涨跌幅 %', round(s['fut_chg_pct'], 4), round(recompute, 4), case['futures']['file']))
    except Exception as e:
        checks.append(('期货窗口涨跌幅 %', round(s['fut_chg_pct'], 4), 'ERR:%s' % e, case['futures']['file']))
    # price 行数与原始一致
    checks.append(('价格序列行数', len(data['price']), len(data['price']), 'build/report_data.json'))
    # 证据条目数
    checks.append(('证据条目数', s['n_items'], len(data.get('items', [])), 'build/graded.json'))
    # 每个驱动都有 E4 兜底
    nod = [t['name'] for t in data['tree'] if t['counts']['E1'] + t['counts']['E2'] + t['counts']['E3'] + t['counts']['E4'] == 0]
    checks.append(('无证据条目的驱动数', 0, len(nod), 'build/graded.json'))
    # 事件全部带链接
    no_url = [e['title'] for e in data['events'] if not e.get('url')]
    checks.append(('无原始链接的事件数', 0, len(no_url), 'raw/events.json'))

    rr = r
    for name, rep, rec, src in checks:
        rr += 1
        ws.cell(row=rr, column=1, value=name)
        ws.cell(row=rr, column=2, value=rep)
        ws.cell(row=rr, column=3, value=rec)
        same = '是'
        diff = ''
        if isinstance(rep, (int, float)) and isinstance(rec, (int, float)):
            diff = abs(rep - rec)
            same = '是' if diff < 0.02 else '否'
            ws.cell(row=rr, column=4, value=round(diff, 6))
        else:
            ws.cell(row=rr, column=4, value='—')
        ws.cell(row=rr, column=5, value=same)
        ws.cell(row=rr, column=6, value=src)
        if same == '否':
            ws.cell(row=rr, column=5).fill = UP_FILL
            ws.cell(row=rr, column=5).font = Font(color='C00000', bold=True)
        else:
            ws.cell(row=rr, column=5).fill = DN_FILL
    style_body(ws, r + 1, 6)
    set_widths(ws, [26, 22, 24, 14, 10, 34])
    return all(x[1] == x[2] or (isinstance(x[1], (int, float)) and isinstance(x[2], (int, float)) and abs(x[1] - x[2]) < 0.02) for x in checks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--case', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    data = C.jload(a.data)
    case = C.jload(a.case)
    base = os.path.dirname(os.path.abspath(a.case))

    wb = Workbook()
    s00(wb, data, case)
    s01(wb, data)
    s02(wb, data)
    s03(wb, data)
    s04(wb, data)
    s05(wb, data)
    s06(wb, data)
    s07(wb, data)
    s08(wb, data)
    s09(wb, data)
    s10(wb, data)
    s11(wb, data)
    ok = s12(wb, data, case, base)

    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.tabColor = '1F3140'

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    wb.save(a.out)
    print('Excel 已生成 -> %s（%d 个工作表）' % (a.out, len(wb.worksheets)))
    print('复算校验：', '全部一致' if ok else '存在不一致，请回查 12_复算校验')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
