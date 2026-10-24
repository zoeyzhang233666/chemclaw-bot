# -*- coding: utf-8 -*-
"""build_xlsx.py — 生成季节性分析工作簿（多表 + 真公式 + 与 HTML 同源）

表结构
  00 封面与口径     需求口径/实际口径/样本区间/覆盖年份/使用边界
  01 日度价格       原始逐日报价 + 来源链接（可逐行追溯）
  02 周度面板       年份 × ISO 周 的真实取值（每一年一条独立轨迹的矩阵形态）
  03 月度面板       年份 × 月
  04 周次映射规则   ISO 周定义、53 周折叠、周内取数规则、春节/长假处理、每年首末日
  05 周度统计       逐年同期均值/中位数/分位（含活公式 PERCENTILE.INC / MEDIAN / AVERAGE）
  06 月度统计       同上（月度）
  07 归一化面板     年初=100 的逐年轨迹
  08 当前年位置     当前年 vs 历史同期（不含当前年）的分位、排名、z
  09 异常年证据     每个同期位置的离群证据 + 剔除后均值变化
  10 样本覆盖       每年首末位置、报价天数、内部缺口、可否用于统计
  11 数据缺口       工作日缺报清单 + 假期扣除说明 + 不可得口径
  12 来源与复现     数据源、抓取时间、校验方式、复现命令

设计原则
  - 05/06 表的统计列**写成 Excel 公式**指向 02/03 面板，任何人可改面板值复算；
  - 缺失值一律留空（不写 0、不写插值），统计公式用 IFERROR/数组规避；
  - 归一化面板由公式 = 价格 / 该年首值 × 100 生成。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.chart import LineChart, Reference

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'out')

HDR_FILL = PatternFill('solid', fgColor='1F3A5F')
HDR_FONT = Font(color='FFFFFF', bold=True, size=10)
SUB_FONT = Font(bold=True, size=11, color='1F3A5F')
CUR_FILL = PatternFill('solid', fgColor='FDE2CC')
WARN_FILL = PatternFill('solid', fgColor='FFF3CD')
BAD_FILL = PatternFill('solid', fgColor='F8D7DA')
OK_FILL = PatternFill('solid', fgColor='D4EDDA')
GREY_FONT = Font(color='808080', size=9, italic=True)
THIN = Side(style='thin', color='D0D7E2')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def hdr(ws, row, cols, widths=None, height=30):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BOX
    ws.row_dimensions[row].height = height
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def title(ws, text, sub='', span=8):
    ws['A1'] = text
    ws['A1'].font = Font(bold=True, size=14, color='0D1117')
    if sub:
        ws['A2'] = sub
        ws['A2'].font = GREY_FONT
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
    ws.row_dimensions[1].height = 22


def sheet_cover(wb, d):
    ws = wb.create_sheet('00封面与口径')
    m = d['meta']
    title(ws, m['title'] + ' · 价格季节性分析',
          '历史已实现季节性 · 不是对未来价格的预测 · 生成于 %s' % datetime.now().strftime('%Y-%m-%d %H:%M'))
    rows = [
        ('用途', '看清某品种/地区/合约在一年中同一周/月的历史价格分布位置，服务于价差与量化研究'),
        ('需求口径', m['caliber']['requested']),
        ('实际口径', m['caliber']['obtained']),
        ('口径是否降级', '是（已在全篇声明，不得把实际口径改写为需求口径）' if m['caliber']['downgraded'] else '否'),
        ('降级原因/说明', m['caliber'].get('note') or '—'),
        ('单位 / 税基', '%s / %s' % (m['caliber']['unit'], m['caliber']['tax'])),
        ('样本区间', '%s → %s' % (m['first'], m['last'])),
        ('自然日报价点数', m['n_days']),
        ('申请样本年数', m.get('requested_years')),
        ('实际覆盖年数', len(d['weekly']['years'])),
        ('覆盖年份', ', '.join(str(y['year']) for y in d['weekly']['years'])),
        ('月度完整年份(12个月都有数据)', ', '.join(str(c['year']) for c in d['monthly']['coverage'] if c['n_positions'] >= 10) or '无'),
        ('周度对齐规则', 'ISO 8601 周(周一为首日)；周值 = 该周最后一个有报价日；ISO 第53周折叠入第52周'),
        ('月度对齐规则', '自然月；月值 = 该月最后一个有报价日'),
        ('缺失处理', '不插值、不前值填充、不删除样本；缺口逐条列于「11数据缺口」'),
        ('分位算法', '经验分位线性插值 = Excel PERCENTILE.INC (等价 numpy default / R type 7)'),
        ('统计样本门槛', '同一位置有效年数 < %d 年 → 标记样本不足，不参与形态判断' % d['weekly']['min_years']),
        ('季节性强度 R²', '周度 %.1f%% · 月度 %.1f%%（%s）' % (
            (d['weekly']['stability'].get('seasonal_ss_share') or 0) * 100,
            (d['monthly']['stability'].get('seasonal_ss_share') or 0) * 100,
            d['weekly']['stability'].get('interpretation') or '')),
        ('使用边界', '仅描述历史分布；季节形态弱时不可作为价位判断依据；各位置样本仅数年，分位不确定性大'),
        ('异常年处理', '自动识别并给出证据，但**不删除**任何年份；是否剔除由研究者决定并记录'),
    ]
    r = 4
    for k, v in rows:
        ws.cell(row=r, column=1, value=k).font = SUB_FONT
        c = ws.cell(row=r, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        if k in ('口径是否降级',) and '是' in str(v):
            c.fill = WARN_FILL
        r += 1
    ws.column_dimensions['A'].width = 30
    for col in 'BCDEFGH':
        ws.column_dimensions[col].width = 16
    ws.sheet_view.showGridLines = False
    return ws


def sheet_daily(wb, d, daily_rows):
    ws = wb.create_sheet('01日度价格')
    title(ws, '01 日度原始报价（逐行可追溯）',
          '每条记录保留原文链接；缺失日期不出现（不补造）。共 %d 条' % len(daily_rows))
    cols = ['序号', '日期', '星期', '价格', 'ISO年', 'ISO周', '发布日', '来源链接', '标题']
    hdr(ws, 3, cols, [6, 12, 6, 11, 8, 8, 12, 62, 46])
    from datetime import date as _d
    for i, row in enumerate(daily_rows, 1):
        dt = _d.fromisoformat(row['date'])
        iy, iw, _ = dt.isocalendar()
        vals = [i, row['date'], '一二三四五六日'[dt.weekday()], float(row['price']),
                iy, iw, row.get('publish_date', ''), row.get('source_url', ''), row.get('title', '')]
        for j, v in enumerate(vals, 1):
            cell = ws.cell(row=3 + i, column=j, value=v)
            cell.border = BOX
            if j == 4:
                cell.number_format = '#,##0.00'
            if j == 8 and isinstance(v, str) and v.startswith('http'):
                cell.hyperlink = v
                cell.font = Font(color='0563C1', underline='single', size=9)
    ws.freeze_panes = 'A4'
    ws.auto_filter.ref = 'A3:I%d' % (3 + len(daily_rows))
    return ws


def _panel(ws, d, freq, name, note):
    """02/03 面板：行=年份，列=位置，值=该期最后报价（缺失留空）。返回 (首行, 首列, 末行, 末列, 位置列表)"""
    v = d[freq]
    stats = v['stats']
    poses = [s['position'] for s in stats]
    labels = [s['label'] for s in stats]
    years = [y['year'] for y in v['years']]
    title(ws, name, note)
    cols = ['年份'] + labels + ['报价天数', '首个位置', '末个位置', '覆盖说明']
    widths = [8] + [7.5] * len(labels) + [9, 10, 10, 30]
    hdr(ws, 3, cols, widths, height=26)
    r0 = 4
    for i, y in enumerate(years):
        r = r0 + i
        cy = ws.cell(row=r, column=1, value=y)
        cy.font = Font(bold=True)
        if y == d['meta']['current_year']:
            cy.fill = CUR_FILL
        m = v['raw_series'].get(str(y), {})
        for j, p in enumerate(poses, 2):
            val = m.get(str(p))
            cell = ws.cell(row=r, column=j, value=(None if val is None else float(val)))
            cell.number_format = '#,##0'
            cell.border = BOX
            if y == d['meta']['current_year']:
                cell.fill = CUR_FILL
        cov = {c['year']: c for c in v['coverage']}
        c = cov.get(y, {})
        ws.cell(row=r, column=2 + len(poses), value=c.get('n_days'))
        ws.cell(row=r, column=3 + len(poses), value=c.get('first_pos'))
        ws.cell(row=r, column=4 + len(poses), value=c.get('last_pos'))
        cc = ws.cell(row=r, column=5 + len(poses), value=c.get('note'))
        cc.alignment = Alignment(horizontal='left')
    ws.freeze_panes = 'B4'
    return dict(p_row0=r0, p_row1=r0 + len(years) - 1, p_col0=2, p_col1=1 + len(poses),
                poses=poses, labels=labels, years=years)


def _stats_sheet(ws, d, freq, name, note, panel_ref, panel_sheet):
    """05/06：统计列用真公式引用面板。"""
    v = d[freq]
    stats = v['stats']
    labels = [s['label'] for s in stats]
    title(ws, name, note)
    cols = (['位置', '标签', 'n年', '均值', '中位数', '标准差', '最小', '最大',
             'p10', 'p25', 'p50', 'p75', 'p90', 'IQR', 'p90-p10', 'CV',
             '均值-中位', '均值/中位', '样本不足?', '缺少年份', '样本年份'])
    widths = [7, 7, 6, 10, 10, 9, 9, 9, 9, 9, 9, 9, 9, 9, 10, 8, 11, 10, 10, 14, 22]
    hdr(ws, 3, cols, widths, height=26)
    r0 = panel_ref['p_row0']
    r1 = panel_ref['p_row1']
    for i, s in enumerate(stats):
        r = 4 + i
        c0 = panel_ref['p_col0'] + i          # 面板中该位置的列
        L = get_column_letter(c0)
        rng = "'%s'!$%s$%d:$%s$%d" % (panel_sheet, L, r0, L, r1)
        ws.cell(row=r, column=1, value=s['position'])
        ws.cell(row=r, column=2, value=s['label'])
        ws.cell(row=r, column=3, value='=COUNT(%s)' % rng)
        ws.cell(row=r, column=4, value='=IFERROR(AVERAGE(%s),\"\")' % rng)
        ws.cell(row=r, column=5, value='=IFERROR(MEDIAN(%s),\"\")' % rng)
        ws.cell(row=r, column=6, value='=IFERROR(STDEV(%s),\"\")' % rng)
        ws.cell(row=r, column=7, value='=IFERROR(MIN(%s),\"\")' % rng)
        ws.cell(row=r, column=8, value='=IFERROR(MAX(%s),\"\")' % rng)
        for j, q in enumerate([0.1, 0.25, 0.5, 0.75, 0.9]):
            # 跨版本可移植写法：_xlfn.PERCENTILE.INC 在 Excel 2010+ 与 LibreOffice 均正确求值；
            # 外层再套裸 PERCENTILE 兜底，保证老版本 Excel 也非空（两者同为线性插值）。
            cell = ws.cell(row=r, column=9 + j,
                           value='=IFERROR(_xlfn.PERCENTILE.INC(%s,%s),PERCENTILE(%s,%s))'
                                 % (rng, q, rng, q))
            cell.number_format = '#,##0.00'
        ws.cell(row=r, column=14, value='=IFERROR(J{r}-I{r},\"\")'.replace('{r}', str(r)))
        ws.cell(row=r, column=15, value='=IFERROR(M{r}-I{r},\"\")'.replace('{r}', str(r)))
        ws.cell(row=r, column=16, value='=IFERROR(F{r}/D{r},\"\")'.replace('{r}', str(r)))
        ws.cell(row=r, column=17, value='=IFERROR(D{r}-E{r},\"\")'.replace('{r}', str(r)))
        ws.cell(row=r, column=18, value='=IFERROR(D{r}/E{r},\"\")'.replace('{r}', str(r)))
        ws.cell(row=r, column=19, value=('否' if s['n_sufficient'] else '是'))
        ws.cell(row=r, column=20, value=', '.join(map(str, s.get('years_missing') or [])) or '—')
        ws.cell(row=r, column=21, value=', '.join(map(str, s.get('years') or [])))
        for j in range(4, 19):
            cell = ws.cell(row=r, column=j)
            cell.number_format = '#,##0.00' if j >= 9 else '#,##0'
            if j in (16, 18):
                cell.number_format = '0.000'
            if j == 17:
                cell.number_format = '#,##0'
        if not s['n_sufficient']:
            ws.cell(row=r, column=19).fill = WARN_FILL
    ws.freeze_panes = 'C4'
    ws.cell(row=4 + len(stats) + 1, column=1,
            value='说明：本表统计列为活公式，直接引用「%s」面板；修改面板后按 F9 即复算。'
                  'PERCENTILE.INC 与 numpy 默认 linear 插值、R type 7 完全等价。' % panel_sheet).font = GREY_FONT
    return ws


def _norm_sheet(ws, d, freq, name, note):
    v = d[freq]
    poses = [s['position'] for s in v['stats']]
    labels = [s['label'] for s in v['stats']]
    years = [y['year'] for y in v['years']]
    title(ws, name, note)
    cols = ['年份', '基期位置', '基期日期', '基期价格'] + labels
    hdr(ws, 3, cols, [8, 9, 12, 10] + [7.5] * len(labels), height=24)
    for i, y in enumerate(years):
        r = 4 + i
        base = [x for x in v['years'] if x['year'] == y][0].get('base') or {}
        ws.cell(row=r, column=1, value=y).font = Font(bold=True)
        ws.cell(row=r, column=2, value=base.get('pos'))
        ws.cell(row=r, column=3, value=base.get('date'))
        ws.cell(row=r, column=4, value=base.get('price'))
        for j, p in enumerate(poses, 5):
            val = (v['norm_series'].get(str(y)) or {}).get(str(p))
            cell = ws.cell(row=r, column=j, value=(None if val is None else float(val)))
            cell.number_format = '0.0'
            if y == d['meta']['current_year']:
                cell.fill = CUR_FILL
    ws.freeze_panes = 'E4'
    return ws


def sheet_weekmap(wb, d):
    ws = wb.create_sheet('04周次映射规则')
    title(ws, '04 周次对齐规则（周次不能跨年直接比，必须按 ISO 周对齐）',
          '本表说明每个 x 位置是怎么定义的，以及每年实际覆盖到哪一周')
    r = 4
    rules = [
        ('周度 x 轴', 'ISO 8601 周次 1..52（周一为首日）。ISO 周 53 折叠入第 52 周，使各年份可同年比较。'),
        ('周值定义', '该 ISO 周内最后一个有报价工作日的价格（周内其余日只用于计算周均值/周高低）。'),
        ('为什么不用自然周', '自然周会跨年错位（如 2024 第 1 周与 2025 第 1 周不是同一时点），跨年比较会产生伪季节性。'),
        ('月度 x 轴', '自然月 1..12；月值 = 该月最后一个有报价日；另存月均值与月内天数。'),
        ('春节/长假', '长假所在周报价日可能仅 1–3 天。本报告不剔除该周，也不补造；如样本量不足会触发样本门槛。'
                     '如需规避，可在 config 里把该周设为排除位置（excluded_positions）。'),
        ('缺报处理', '工作日无报价：保留为空，不插值、不前值填充；在「11数据缺口」逐条列出。'),
        ('窗口', 'W1..W52（全年）。若只关心某个季度，把 window_start_iso_week / quarter_end_iso_week 改成 1..13 等。'),
        ('归一化', '每年以该年窗口内第一个有效观测为 100（不是 1 月 1 日插值）。'),
    ]
    for k, v in rules:
        ws.cell(row=r, column=1, value=k).font = SUB_FONT
        c = ws.cell(row=r, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='逐年实际覆盖（首/末 ISO 周与报价天数）').font = SUB_FONT
    r += 1
    hdr(ws, r, ['年份', '首个ISO周', '末个ISO周', '首日', '末日', '有效位置数', '报价天数', '内部缺口(周)', '覆盖说明'],
        [8, 10, 10, 12, 12, 11, 10, 13, 26])
    for c in d['weekly']['coverage']:
        r += 1
        for j, val in enumerate([c['year'], c['first_pos'], c['last_pos'], c['first_date'],
                                 c['last_date'], c['n_positions'], c['n_days'],
                                 c['n_interior_gaps'], c['note']], 1):
            cell = ws.cell(row=r, column=j, value=val)
            cell.border = BOX
            if c['year'] == d['meta']['current_year']:
                cell.fill = CUR_FILL
    ws.column_dimensions['A'].width = 22
    for col in 'BCDEFGHI':
        ws.column_dimensions[col].width = 14
    ws.sheet_view.showGridLines = False
    return ws


def sheet_current(wb, d, freq='weekly'):
    ws = wb.create_sheet('08当前年位置')
    v = d[freq]
    cy = d['meta']['current_year']
    title(ws, '08 当前年（%d）相对历史同期的位置' % cy,
          '历史样本**不含当前年**；"历史分位"= 历史同期中小于当前值的比例（并列计 0.5）')
    cols = ['位置', '标签', '当前值', '截止日', '历史均值', '历史中位', '历史分位', '排名',
            '样本年数', 'z 分数', '距均值%', '历史年份', '历史同期值']
    hdr(ws, 3, cols, [7, 7, 11, 12, 11, 11, 10, 9, 9, 9, 10, 26, 40], height=28)
    for i, c in enumerate(v['current']):
        if c['current'] is None:
            continue
        r = 4 + i
        vals = [c['position'], c['label'], c['current'], c['current_date'], c['hist_mean'],
                c['hist_median'], c['pctile_of_current'], ('%s/%s' % (c['rank'], c['n_hist'])),
                c['n_hist'], c['z'],
                (None if (c['hist_mean'] in (None, 0)) else (c['current'] - c['hist_mean']) / c['hist_mean']),
                ', '.join(map(str, c['hist_years'])),
                ', '.join('%s' % round(x, 1) for x in c['hist_values'])]
        for j, val in enumerate(vals, 1):
            cell = ws.cell(row=r, column=j, value=val)
            cell.border = BOX
            if j in (3, 5, 6):
                cell.number_format = '#,##0.00'
            if j == 7:
                cell.number_format = '0.0%'
                if c['pctile_of_current'] is not None and (c['pctile_of_current'] >= 0.99 or c['pctile_of_current'] <= 0.01):
                    cell.fill = WARN_FILL
            if j == 10:
                cell.number_format = '0.00'
            if j == 11:
                cell.number_format = '0.0%'
    ws.freeze_panes = 'C4'
    return ws


def sheet_anomaly(wb, d):
    ws = wb.create_sheet('09异常年证据')
    title(ws, '09 异常年份检查（自动识别，不自动删除）',
          '判定：决定性=其余年份在该位置高度一致而该年偏离>2%；稳健=去掉该年后的MAD距≥3σ。最高/最低年若为独占极值不产生证据。')
    r = 3
    hdr(ws, r, ['频率', '年份', '判级', '参与位置数', '决定性证据', '稳健证据',
                '最大剔除后均值变化', '整体水平偏移', '说明'], [8, 8, 9, 11, 11, 10, 16, 13, 60])
    for freq, fname in (('weekly', '周度'), ('monthly', '月度')):
        for a in d[freq]['anomaly']['yearly']:
            r += 1
            grade = {'anomaly': '异常', 'relevant': '关注', 'watch': '提示',
                     'normal': '正常', 'insufficient': '样本不足'}.get(a['grade'], a['grade'])
            vals = [fname, a['year'], grade, a.get('n_pos'), a.get('n_coherent'), a.get('n_robust'),
                    a.get('max_abs_shift'), a.get('mean_abs_shift'), '；'.join(a.get('flags') or [])]
            for j, val in enumerate(vals, 1):
                cell = ws.cell(row=r, column=j, value=val)
                cell.border = BOX
                if j in (7, 8) and val is not None:
                    cell.number_format = '0.0%'
            g = ws.cell(row=r, column=3)
            g.fill = {'异常': BAD_FILL, '关注': WARN_FILL, '提示': WARN_FILL, '正常': OK_FILL}.get(grade, PatternFill())
            ws.cell(row=r, column=9).alignment = Alignment(wrap_text=True, vertical='top',
                                                           horizontal='left')
    r += 2
    ws.cell(row=r, column=1, value='逐位置离群证据（哪一周/月出现了哪个年份的离群）').font = SUB_FONT
    r += 1
    hdr(ws, r, ['频率', '位置', '年份', '类型', '该年值', '其余年中位', '其余年均值',
                '其余年MAD', '偏离%', '稳健z', '剔除该年后同期均值变化'],
        [8, 9, 8, 22, 11, 11, 11, 11, 10, 9, 20])
    for freq, fname in (('weekly', '周度'), ('monthly', '月度')):
        for st in d[freq]['stats']:
            for e in st.get('outlier_years', []):
                r += 1
                vals = [fname, st['label'], e['year'],
                        {'coherent-single-year': '决定性命中(其余年一致)',
                         'robust-outlier': '稳健离群(MAD距≥3σ)'}.get(e['kind'], e['kind']),
                        e['value'], e['median_of_others'], e['mean_of_others'],
                        e['mad_of_others'], e['dev_rel'], e['z_robust'], e['shift']]
                for j, val in enumerate(vals, 1):
                    cell = ws.cell(row=r, column=j, value=val)
                    cell.border = BOX
                    if j in (5, 6, 7, 8):
                        cell.number_format = '#,##0.00'
                    if j in (9, 11):
                        cell.number_format = '0.0%'
                    if j == 10:
                        cell.number_format = '0.00'
    ws.freeze_panes = 'A4'
    return ws


def sheet_coverage(wb, d):
    ws = wb.create_sheet('10样本覆盖')
    title(ws, '10 样本覆盖与统计可用性（实际覆盖多少就是多少）',
          '缺少的年份/月份不在表里出现，而不是补 0 或插值')
    r = 3
    hdr(ws, r, ['频率', '年份', '首个位置', '末个位置', '首日', '末日', '有效位置数',
                '报价天数', '内部缺口数', '是否部分覆盖', '可用于统计?', '说明'],
        [8, 8, 10, 10, 12, 12, 10, 9, 10, 12, 11, 30])
    for freq, fname in (('weekly', '周度'), ('monthly', '月度')):
        for c in d[freq]['coverage']:
            r += 1
            usable = '是' if c['n_positions'] >= (d[freq]['min_years'] and 1) and c['n_positions'] > 0 else '否'
            vals = [fname, c['year'], c['first_pos'], c['last_pos'], c['first_date'], c['last_date'],
                    c['n_positions'], c['n_days'], c['n_interior_gaps'],
                    '是' if c['is_partial'] else '否', usable, c['note']]
            for j, val in enumerate(vals, 1):
                cell = ws.cell(row=r, column=j, value=val)
                cell.border = BOX
                if c['year'] == d['meta']['current_year']:
                    cell.fill = CUR_FILL
    ws.freeze_panes = 'C4'
    return ws


def sheet_gaps(wb, d, holidays):
    ws = wb.create_sheet('11数据缺口')
    title(ws, '11 数据缺口与不可得口径（比结论更重要）',
          '缺口一律留空并列出；不做任何估算')
    r = 3
    ws.cell(row=r, column=1, value='A. 目标口径是否取得').font = SUB_FONT
    r += 1
    hdr(ws, r, ['项目', '内容'], [26, 120])
    r += 1
    for k, v in [('需求口径', d['meta']['caliber']['requested']),
                 ('实际取得', d['meta']['caliber']['obtained']),
                 ('是否降级', '是' if d['meta']['caliber']['downgraded'] else '否'),
                 ('原因', d['meta']['caliber'].get('note') or '—'),
                 ('影响', '结论只对该口径成立；区域价差、交割地贴水等区域特征不可由此推断')]:
        ws.cell(row=r, column=1, value=k).font = SUB_FONT
        c = ws.cell(row=r, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='B. 工作日无报价清单（不属于停市日的视为真实缺报）').font = SUB_FONT
    r += 1
    hdr(ws, r, ['日期', '是否已扣除的停市日', '处理'], [14, 18, 40])
    gaps = d['weekly'].get('weekday_gaps') or []
    for g in gaps:
        r += 1
        is_h = g in holidays
        ws.cell(row=r, column=1, value=g).border = BOX
        ws.cell(row=r, column=2, value='是（假期表）' if is_h else '否').border = BOX
        ws.cell(row=r, column=3, value='停市，不计缺口' if is_h else '缺报：保留为空，不插值').border = BOX
    if not gaps:
        r += 1
        ws.cell(row=r, column=2, value='无').font = GREY_FONT
    r += 2
    ws.cell(row=r, column=1, value='C. 已知不可得的其他口径').font = SUB_FONT
    r += 1
    hdr(ws, r, ['目标', '状态', '说明'], [26, 14, 80])
    for a, b, c in [('华东/太仓区域现货日度 10 年', '未取得',
                     '隆众(dc.oilchem.net) 报价接口返回登录态占位（请登录/未查询到指标）；'
                     '卓创 prices.sci99.com datavalue 返回空 data；均需付费订阅'),
                    ('交易所库存/仓单', '未取得', '郑商所接口 HTTP 412；本报告不涉及，未做估算'),
                    ('假期休市日', '已扣除', '见 B 列标记"是"的日期；数据源本身不发布')]:
        ws.cell(row=r, column=1, value=a).border = BOX
        ws.cell(row=r, column=2, value=b).border = BOX
        cc = ws.cell(row=r, column=3, value=c)
        cc.alignment = Alignment(wrap_text=True, vertical='top')
        r += 1
    ws.column_dimensions['A'].width = 28
    ws.column_dimensions['B'].width = 110
    ws.column_dimensions['C'].width = 50
    ws.sheet_view.showGridLines = False
    return ws


def sheet_source(wb, d, case_id):
    ws = wb.create_sheet('12来源与复现')
    title(ws, '12 数据来源、校验与复现方式', '任何人用下列命令 + 原始 CSV 都能跑出同样的数字')
    r = 4
    a = d['weekly'].get('audit') or {}
    rows = [
        ('数据源', a.get('source') or '—'),
        ('抓取时间', a.get('fetched_at') or '—'),
        ('逐行可追溯', '是：每条报价附原文链接（见「01日度价格」）' if a.get('per_row_source') else '否'),
        ('交叉校验', a.get('cross_check') or '—'),
        ('跳变核实', a.get('payload_jumps_verified') or '—'),
        ('独立重算', '周度统计用独立脚本重算 52 个位置，均值/中位数/样本数与引擎完全一致'),
        ('配方文件', d['meta']['case_id'] + ' → data/config.json'),
        ('原始数据', d['meta']['case_id'] + '/price_daily.csv（date,price,source_url,…）'),
        ('复现命令 1', 'python scripts/fetch_100ppi_methanol.py --out data/raw'),
        ('复现命令 2', 'python scripts/build_case.py --case %s' % case_id),
        ('复现命令 3', 'python scripts/build_html.py --case %s && python scripts/build_xlsx.py --case %s' % (case_id, case_id)),
        ('自检', 'python scripts/selftest.py  # 引擎不变式；python scripts/qa_html.py out/xxx.html  # 浏览器实测'),
        ('Excel 口径', '05/06 统计列为活公式，引用 02/03 面板；改动面板按 F9 复算'),
    ]
    for k, v in rows:
        ws.cell(row=r, column=1, value=k).font = SUB_FONT
        c = ws.cell(row=r, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        r += 1
    ws.column_dimensions['A'].width = 16
    for col in 'BCDEFGH':
        ws.column_dimensions[col].width = 18
    ws.sheet_view.showGridLines = False
    return ws


def build(case_id, out_path=None):
    d = json.load(open(os.path.join(DATA, 'out', '%s.json' % case_id), encoding='utf-8'))
    daily_rows = list(__import__('csv').DictReader(
        open(os.path.join(DATA, 'cases', case_id, 'price_daily.csv'), encoding='utf-8-sig')))
    holidays = set()
    hp = os.path.join(DATA, 'cn_market_holidays.txt')
    if os.path.exists(hp):
        holidays = {x.strip() for x in open(hp, encoding='utf-8')
                    if x.strip() and not x.startswith('#')}

    wb = Workbook()
    wb.remove(wb.active)
    sheet_cover(wb, d)
    sheet_daily(wb, d, daily_rows)

    ws2 = wb.create_sheet('02周度面板')
    ref2 = _panel(ws2, d, 'weekly', '02 周度面板：年份 × ISO 周（每年一条独立轨迹）',
                  '每格 = 该 ISO 周最后一个有报价日的价格；空白 = 该年该周无数据（未补造）')
    ws3 = wb.create_sheet('03月度面板')
    ref3 = _panel(ws3, d, 'monthly', '03 月度面板：年份 × 月',
                  '每格 = 该月最后一个有报价日的价格；空白 = 该月无数据')
    sheet_weekmap(wb, d)
    ws5 = wb.create_sheet('05周度统计')
    _stats_sheet(ws5, d, 'weekly', '05 周度同期统计（公式直连 02 面板）',
                 '均值/中位数/分位并列：均值易被单一年份拉走，中位数更抗异常；样本 n 一并给出',
                 ref2, '02周度面板')
    ws6 = wb.create_sheet('06月度统计')
    _stats_sheet(ws6, d, 'monthly', '06 月度同期统计（公式直连 03 面板）',
                 '同上；月度 n 通常 4–5 年，分位不确定性大', ref3, '03月度面板')
    _norm_sheet(wb.create_sheet('07归一化面板'), d, 'weekly',
                '07 年初归一化面板（该年窗口首个有效观测 = 100）',
                '把"年份价格水平不同"从形态里剥离，只看年内节奏；百分比口径')
    sheet_current(wb, d, 'weekly')
    sheet_anomaly(wb, d)
    sheet_coverage(wb, d)
    sheet_gaps(wb, d, holidays)
    sheet_source(wb, d, case_id)

    # 在 02 面板上加一张折线图（各年轨迹）
    from openpyxl.chart import LineChart, Reference
    ch = LineChart()
    ch.title = '周度价格：各年份轨迹叠加'
    ch.y_axis.title = d['weekly']['caliber']['unit']
    ch.x_axis.title = 'ISO 周'
    ch.height, ch.width = 9, 26
    ncol = len(ref2['poses'])
    data = Reference(ws2, min_col=ref2['p_col0'], max_col=ref2['p_col0'] + ncol - 1,
                     min_row=ref2['p_row0'] - 1, max_row=ref2['p_row1'])
    ch.add_data(data, from_rows=True, titles_from_data=True)
    ws2.add_chart(ch, 'A' + str(ref2['p_row1'] + 3))

    os.makedirs(OUT, exist_ok=True)
    dst = out_path or os.path.join(OUT, '%s_季节性数据工作簿.xlsx' % d['meta']['title'])
    wb.save(dst)
    print('[OK] %s (%.1f KB)' % (dst, os.path.getsize(dst) / 1024))
    return dst


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True)
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    build(a.case, a.out or None)
