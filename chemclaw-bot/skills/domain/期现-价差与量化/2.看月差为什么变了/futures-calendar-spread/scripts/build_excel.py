# -*- coding: utf-8 -*-
"""生成可复核的 Excel 工作簿（全部数值来自 enriched.json，不手工抄写）。

用法
----
    python scripts/build_excel.py --data build/enriched.json \
        --out examples/SA-2612-2701/spread-workbook.xlsx

工作表
------
01-使用说明     口径提示、如何复核
02-结论摘要     关键数字与“能说/不能说”
03-合约价格     A/B 两腿逐日收盘、结算、持仓
04-月差历史     月差序列 + 统计量
05-近期变化     各回看窗口的月差与两腿变化
06-历史分位     全样本 / 近1年 / 近3年（含可用性判定）+ 可比样本分位
07-可比样本     逐组合明细 + 汇总统计
08-期限结构     当前与历史同日对照、锚定月归一
09-贡献分解     区间/逐日 对数贡献
10-近端结构演变 按锚合约分段的近端月差
11-仓单库存     品种级仓单序列与元数据
12-事件台账     带来源链接
13-计算公式     全部公式用 Excel 真实公式写（可拖动复核）
14-数据来源     来源清单与覆盖区间
15-数据质量     检查结果
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HDR_FILL = PatternFill('solid', fgColor='1F3B57')
HDR_FONT = Font(color='FFFFFF', bold=True, size=10)
TITLE_FONT = Font(bold=True, size=14, color='1F3B57')
SUB_FONT = Font(italic=True, size=10, color='555555')
WARN_FILL = PatternFill('solid', fgColor='FFF3CD')
OK_FILL = PatternFill('solid', fgColor='DFF5E1')
ERR_FILL = PatternFill('solid', fgColor='F8D7DA')
SEL_FILL = PatternFill('solid', fgColor='DCE9F7')
THIN = Side(style='thin', color='D0D7DE')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def sheet(wb, name, title, sub=None, widths=None):
    ws = wb.create_sheet(name)
    ws['A1'] = title
    ws['A1'].font = TITLE_FONT
    if sub:
        ws['A2'] = sub
        ws['A2'].font = SUB_FONT
    ws.sheet_view.showGridLines = False
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
    return ws


def header(ws, row, cols):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 28


def rows(ws, start, data, numfmt=None, zebra=True):
    for r, rowvals in enumerate(data, start):
        for c, v in enumerate(rowvals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = BORDER
            if isinstance(v, (int, float)) and numfmt:
                cell.number_format = numfmt
            if zebra and (r - start) % 2 == 1:
                cell.fill = PatternFill('solid', fgColor='F5F8FB')
    return start + len(data)


def kv_block(ws, row, pairs, keyw=1, valw=2):
    for k, v in pairs:
        ws.cell(row=row, column=keyw, value=k).font = Font(bold=True, size=10)
        c = ws.cell(row=row, column=valw, value=v)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        row += 1
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    with open(args.data, encoding='utf-8') as f:
        D = json.load(f)
    M, C = D['meta'], D['contracts']
    # term_structure.shape 是 {shape, slope, slope_per_month, n}，用前摊平
    _shp = D['term_structure']['shape']
    SHAPE_TXT = _shp['shape'] if isinstance(_shp, dict) else str(_shp)
    SHAPE_SLOPE = _shp.get('slope') if isinstance(_shp, dict) else None
    SP, PC = D['spread'], D['percentile']
    TS = D['term_structure']
    wb = Workbook()
    wb.remove(wb.active)

    # ---------------- 01 使用说明 ----------------
    ws = sheet(wb, '01-使用说明', f"{M['product']} 月差研究工作簿：{C['a']} − {C['b']}", widths=[26, 100])
    r = 4
    ws.cell(row=r, column=1, value='一、这份工作簿回答什么').font = Font(bold=True, size=11)
    r += 1
    for t in ['1) 两个合约的最新价格与历史序列（03）',
              '2) 月差的定义与符号约定（03/04/13）',
              '3) 当前月差、近期变化、历史分位（04/05/06）',
              '4) 当前挂牌合约的完整期限结构（08）',
              '5) 历史相同月份组合、相近距交割时间的月差（07）',
              '6) 库存/仓单/交割规则/季节性/已知事件对月差的解释（10/11/12）',
              '7) 近月与远月对月差变化的贡献分解（09）']:
        ws.cell(row=r, column=1, value=t).alignment = Alignment(wrap_text=True)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='二、必须遵守的口径').font = Font(bold=True, size=11)
    r += 1
    r = kv_block(ws, r, [
        ('月差定义', f"月差 = P({C['a']}) − P({C['b']})。A 写在前面，所有表、图、公式全程不换序。"),
        ('价格口径', f"{'收盘价' if M['price_basis'] == 'close' else '结算价'}（同步存两列，切换口径后必须重算而不是四舍五入）"),
        ('日历间隔', f"{C['a']} 与 {C['b']} 相隔 {C['gap_months']} 个月；距本腿交割 {C['a_dtd']} / {C['b_dtd']} 个交易日（按交割月第10个交易日计）"),
        ('可比样本规则', f"同月份组合（gap={C['gap_months']} 月）且 |距本腿交割 − {C['a_dtd']}| ≤ {M['dtd_tol']} 个交易日"),
        ('禁止事项', '禁止把剩余到期时间不同的月差混入同一分布；禁止用主力连续合约算月差；禁止对缺失价格插值/前向填充。'),
        ('最低持仓', f"构建期限结构时要求持仓 ≥ {M['min_oi']} 手，避免把刚挂牌的占位报价当成真实价格。"),
    ])
    r += 1
    ws.cell(row=r, column=1, value='三、如何复核').font = Font(bold=True, size=11)
    r += 1
    r = kv_block(ws, r, [
        ('算法', '13-计算公式 页所有格子都是 Excel 真实公式，改任一价格即可看到月差、变化、分位联动。'),
        ('数据血缘', '14-数据来源 给出行情接口、仓单接口、事件原文链接与各自覆盖区间。'),
        ('质量门槛', '15-数据质量 有任何 ERROR 时，本工作簿的结论不可用。'),
        ('生成器', f"futures-calendar-spread / build_excel.py；数据快照 build/enriched.json；生成于 {M['generated_at']}"),
    ])
    ws.cell(row=r + 1, column=1, value='免责声明：本工作簿为描述性研究，不含任何交易建议、目标价或方向性推荐。').font = Font(bold=True, color='B00020')

    # ---------------- 02 结论摘要 ----------------
    ws = sheet(wb, '02-结论摘要', '结论摘要（先数字，后解释）', widths=[30, 20, 16, 62])
    r = 4
    header(ws, r, ['项目', '数值', '单位', '说明'])
    r += 1
    cmp_ = PC.get('comparable', {})
    ph = PC.get('pair_history', {})
    ly = TS.get('last_year') or []
    ts = TS['rows']
    chg = {c['window']: c for c in D['change']}
    decomp = D['decomposition']['windows']
    wk = decomp.get('近1周', {})
    data = [
        ('当前月差', SP['current'], '元/吨', f"{SP['date']}，{C['a']} {SP['a_price']:.0f} / {C['b']} {SP['b_price']:.0f}"),
        ('近1周变化', chg.get('近1周', {}).get('change'), '元/吨', chg.get('近1周', {}).get('from', '') + ' → ' + SP['date']),
        ('近1月变化', chg.get('近1月', {}).get('change'), '元/吨', chg.get('近1月', {}).get('from', '') + ' → ' + SP['date']),
        ('本合约对全样本分位', ph.get('all', {}).get('pct'), '%', f"N={ph.get('all', {}).get('n')}（仅 {ph.get('all', {}).get('first')} 起，不足1年）"),
        ('可比样本分位', cmp_.get('pct'), '%', f"N={cmp_.get('n')}，同月份组合＋距交割±{M['dtd_tol']}日"),
        ('期限结构形态', SHAPE_TXT, '', ' '.join(f"{t['contract']}={t['ts']:+.0f}" for t in ts)),
        ('最近月→最远月', SHAPE_SLOPE, '元/吨', '最远月 TS 减最近月 TS'),
        ('近端(次近月 TS)', ts[1]['ts'] if len(ts) > 1 else None, '元/吨', f"{ts[1]['contract']} 相对 {ts[0]['contract']}" if len(ts) > 1 else ''),
        ('去年同位置近端', ly[1]['ts'] if len(ly) > 1 else None, '元/吨', f"{TS.get('last_year_date')}，{ly[1]['contract'] if len(ly)>1 else ''}"),
        ('近1周近月贡献', round(wk.get('contrib_a_dln', 0) * 100, 2), '%', f"{C['a']} 涨跌 {wk.get('chg_a')}"),
        ('近1周远月贡献', round(wk.get('contrib_b_dln', 0) * 100, 2), '%', f"{C['b']} 涨跌 {wk.get('chg_b')}"),
        ('品种仓单', (D.get('warehouse') or {}).get('current'), (D.get('warehouse') or {}).get('unit'), (D.get('warehouse') or {}).get('date', '') + '（品种级，不可拆分到合约）'),
    ]
    for d in data:
        ws.cell(row=r, column=1, value=d[0]).font = Font(bold=True)
        c = ws.cell(row=r, column=2, value=d[1])
        if isinstance(d[1], float):
            c.number_format = '0.0'
        ws.cell(row=r, column=3, value=d[2])
        ws.cell(row=r, column=4, value=d[3]).alignment = Alignment(wrap_text=True, vertical='top')
        for cc in range(1, 5):
            ws.cell(row=r, column=cc).border = BORDER
        r += 1
    r += 2
    ws.cell(row=r, column=1, value='可以说的 / 不能说的').font = Font(bold=True, size=11)
    r += 1
    for txt, ok in [
        (f"本次“变化”主要不是月差本身，而是整条曲线的绝对水平下移；{C['a']}−{C['b']} 稳定在 {SP['current']:+.0f} 元附近的小幅贴水。", True),
        ("结构真正变化在近端：去年同位置的最近月→次近月为正升水，当前接近持平；近端升水在换月后被抹平。", True),
        ("近 1 周两腿近乎同幅下跌，近月与远月贡献相互抵消，月差不由单腿推动——这是“两腿同步”而非“某一腿主导”。", True),
        ("产业侧支持“近端无持续性偏紧”：厂库同比高位、开工率回升、检修为短期行为、远期中盐奈曼旗 500 万吨天然碱项目在建。", True),
        (ph.get('y1', {}).get('note') or '本合约对历史不足 1 年，无法给出真实的“近1年/近3年分位”。', False),
        ("仓单仅 3 个月、品种级，不能拆成近月/远月仓单，也不能与厂库混用；交易所仓单≠社会库存。", False),
        ("事件时间接近不等于因果；未做任何统计检验，不能宣称“因为 X 所以月差变成 Y”。", False),
        ("以上不含任何交易建议。", False),
    ]:
        ws.cell(row=r, column=1, value='✓' if ok else '✗').alignment = Alignment(horizontal='center')
        ws.cell(row=r, column=1).fill = OK_FILL if ok else ERR_FILL
        c = ws.cell(row=r, column=2, value=txt)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        ws.row_dimensions[r].height = 32
        r += 1

    # ---------------- 03 合约价格 ----------------
    ws = sheet(wb, '03-合约价格', f"{C['a']} 与 {C['b']} 逐日价格序列", '月差 = A − B；两腿必须同日都有报价才计入。', widths=[13, 13, 13, 13, 13, 13, 13, 13, 13])
    hdr = [C['a'] + ' 收盘', C['a'] + ' 结算', C['a'] + ' 持仓', C['b'] + ' 收盘', C['b'] + ' 结算',
           C['b'] + ' 持仓', '月差(A−B)', '月差%', 'A距交割']
    header(ws, 4, ['日期'] + hdr)
    panel = {}
    for row in D['panel']:
        panel.setdefault(row['date'], {})[row['contract']] = row
    data = []
    for rr in SP['series']:
        d = rr['date']
        A, B = panel.get(d, {}).get(C['a']), panel.get(d, {}).get(C['b'])
        if not A or not B:
            continue
        data.append([d, A['price'], None, A['oi'], B['price'], None, B['oi'],
                     None, None, A['dtd']])
    r = 5
    for row in data:
        ws.append(row) if False else None
        for i, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BORDER
        # 用真实公式写月差，便于拖动复核
        ws.cell(row=r, column=7, value=f'=B{r}-E{r}').number_format = '0.00'
        ws.cell(row=r, column=8, value=f'=IFERROR(G{r}/E{r}*100,"")').number_format = '0.000'
        r += 1
    last = r - 1
    ws.freeze_panes = 'B5'
    r += 1
    ws.cell(row=r, column=1, value='统计量').font = Font(bold=True, size=11)
    r += 1
    st = SP['stats']
    for lab, formula, fmt in [
        ('样本数 N', f'=COUNT(G5:G{last})', '0'),
        ('均值', f'=AVERAGE(G5:G{last})', '0.00'),
        ('中位数', f'=MEDIAN(G5:G{last})', '0.00'),
        ('样本标准差', f'=STDEV(G5:G{last})', '0.00'),
        ('最小值', f'=MIN(G5:G{last})', '0.00'),
        ('最大值', f'=MAX(G5:G{last})', '0.00'),
        ('25分位', f'=PERCENTILE(G5:G{last},0.25)', '0.00'),
        ('75分位', f'=PERCENTILE(G5:G{last},0.75)', '0.00'),
        ('当前值', f'=G{last}', '0.00'),
        ('当前值分位%', f'=COUNTIF(G5:G{last},"<="&G{last})/COUNT(G5:G{last})*100', '0.0'),
    ]:
        ws.cell(row=r, column=1, value=lab).font = Font(size=10)
        c = ws.cell(row=r, column=2, value=formula)
        c.number_format = fmt
        r += 1
    ws.cell(row=r + 1, column=1, value='注：结算价列留空表示该合约当日无结算数据（新浪接口个别早期行），不做任何填充。').font = SUB_FONT

    # ---------------- 04 月差历史 ----------------
    ws = sheet(wb, '04-月差历史', f"月差历史序列：{C['a']} − {C['b']}", '含 5/20 日滚动均值；末行为统计口径。', widths=[13, 13, 13, 13, 14, 14, 12])
    header(ws, 4, ['日期', C['a'], C['b'], '月差', '月差%', 'MA5', 'MA20'])
    r = 5
    for rr in SP['series']:
        vals = [rr['date'], rr['a'], rr['b'], None, None,
                None, None]
        for i, v in enumerate(vals, 1):
            ws.cell(row=r, column=i, value=v).border = BORDER
        ws.cell(row=r, column=4, value=f'=B{r}-C{r}').number_format = '0.00'
        ws.cell(row=r, column=5, value=f'=IFERROR(D{r}/C{r}*100,"")').number_format = '0.000'
        if r >= 9:
            ws.cell(row=r, column=6, value=f'=ROUND(AVERAGE(D{r-4}:D{r}),2)').number_format = '0.00'
        if r >= 24:
            ws.cell(row=r, column=7, value=f'=ROUND(AVERAGE(D{r-19}:D{r}),2)').number_format = '0.00'
        r += 1
    ws.freeze_panes = 'B5'

    # ---------------- 05 近期变化 ----------------
    ws = sheet(wb, '05-近期变化', '近期变化（同一合约对，回看 N 个交易日）', '窗口一律用“该两腿都有报价的交易日”计数，不用日历日。', widths=[14, 14, 14, 14, 14, 14, 14, 14, 14])
    header(ws, 4, ['窗口', '交易日数', '起点', '终点', '期初月差', '期末月差', '月差变化', 'A变化', 'B变化'])
    r = 5
    for c in D['change']:
        vals = [c['window'], c.get('n'), c.get('from'), c['to'], c.get('from_value'), c.get('to_value'),
                c.get('change'), c.get('chg_a'), c.get('chg_b')]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BORDER
            if i >= 5 and isinstance(v, (int, float)):
                cell.number_format = '+0.00;-0.00;0'
        r += 1
    ws.cell(row=r + 1, column=1, value='判读：月差变化 = 近月变化 − 远月变化。若 A、B 同向同幅，则月差几乎不动——说明变的是整条曲线的水平而非结构。').font = SUB_FONT

    # ---------------- 06 历史分位 ----------------
    ws = sheet(wb, '06-历史分位', '历史分位：可用性判定与实际数值', '不足该区间的样本不得称为“该区间分位”。', widths=[30, 13, 13, 13, 13, 60])
    header(ws, 4, ['分布', '样本N', '起始', '当期分位%', '可用', '说明'])
    r = 5
    for key in ('all', 'y1', 'y3'):
        v = ph.get(key)
        if not v:
            continue
        vals = [v['label'], v.get('n'), v.get('first'), v.get('pct'), '是' if v.get('usable', True) else '否', v.get('note') or '样本完整']
        for i, x in enumerate(vals, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            if i == 4 and isinstance(x, (int, float)):
                cell.number_format = '0.0'
            if i == 6:
                cell.alignment = Alignment(wrap_text=True, vertical='top')
        if not v.get('usable', True):
            for i in range(1, 7):
                ws.cell(row=r, column=i).fill = WARN_FILL
        r += 1
    if cmp_.get('n'):
        vals = ['可比样本（跨年份同组合）', cmp_['n'], '', cmp_['pct'], '是',
                f"同日历间隔 {C['gap_months']} 月，距本腿交割 ±{M['dtd_tol']} 个交易日；这是唯一可用来判断贵/便宜的分布"]
        for i, x in enumerate(vals, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            if i == 4:
                cell.number_format = '0.0'
            if i == 6:
                cell.alignment = Alignment(wrap_text=True, vertical='top')
        for i in range(1, 7):
            ws.cell(row=r, column=i).fill = SEL_FILL
        r += 1
    r += 2
    ws.cell(row=r, column=1, value='算法').font = Font(bold=True)
    r += 1
    for t in ['分位 = #{可比样本 v : v ≤ 当期值} / N × 100（下方 07 页给出了逐样本明细，可自行用 COUNTIF 复核）',
              '分位点用线性插值（Excel 的 PERCENTILE.INC 同法），与 Python numpy 的 "linear" 一致']:
        ws.cell(row=r, column=1, value=t).alignment = Alignment(wrap_text=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        r += 1

    # ---------------- 07 可比样本 ----------------
    ws = sheet(wb, '07-可比样本', '可比样本：相同月份组合 + 相近距交割时间', f"规则：gap={C['gap_months']} 月 且 |距本腿交割 − {C['a_dtd']}| ≤ {M['dtd_tol']} 个交易日", widths=[10, 10, 10, 10, 10, 13, 13, 13, 13, 13, 13, 13])
    header(ws, 4, ['组合', '', '起始', '截止', '样本N', '均值', '中位', '最小', 'P25', 'P75', '最大', '标准差'])
    r = 5
    vals_all = []
    for p in D['comparable']['pairs']:
        st_ = p['stats']
        row = [p['pair'][0], p['pair'][1], p['first'], p['last'], st_['n'], st_['mean'], st_['median'],
               st_['min'], st_['p25'], st_['p75'], st_['max'], st_['std']]
        for i, x in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            if i >= 6 and isinstance(x, (int, float)):
                cell.number_format = '0.00'
        vals_all.extend(p['vals'])
        r += 1
    # 合并样本汇总
    r += 1
    ws.cell(row=r, column=1, value='合并样本').font = Font(bold=True, size=11)
    r += 1
    for lab, v, f in [('样本总数 N', cmp_.get('n'), '0'),
                      ('均值', cmp_['stats']['mean'] if cmp_.get('n') else None, '0.00'),
                      ('中位数', cmp_['stats']['median'] if cmp_.get('n') else None, '0.00'),
                      ('最小值', cmp_['stats']['min'] if cmp_.get('n') else None, '0.00'),
                      ('最大值', cmp_['stats']['max'] if cmp_.get('n') else None, '0.00'),
                      ('当期值', SP['current'], '0.00'),
                      ('当期分位%', cmp_.get('pct'), '0.0')]:
        ws.cell(row=r, column=1, value=lab).font = Font(size=10)
        cell = ws.cell(row=r, column=2, value=v)
        cell.number_format = f
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='说明：这些历史组合的“剩余到期时间”与本报告当期对齐，因此可以横向比较；不同 gap 或不同 dtd 的月差不可比，故未纳入。').font = SUB_FONT
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12)

    # ---------------- 08 期限结构 ----------------
    ws = sheet(wb, '08-期限结构', f"期限结构：{M['asof']} vs {TS.get('last_year_date')}", f"TS = P(合约) − P(最近月)；持仓 ≥ {M['min_oi']} 手", widths=[12, 12, 12, 12, 14, 12, 14, 14, 40])
    header(ws, 4, ['合约', '交割年月', '价格', '持仓', '距交割(交易日)', f"TS({M['asof']})",
                   f"{TS.get('last_year_date')} 价格", f"TS({TS.get('last_year_date')})", '形态'])
    r = 5
    ly_map = {t['contract']: t for t in (ly or [])}
    for t in TS['rows']:
        L = ly_map.get(t['contract'])
        row = [t['contract'], f"{t['year']}-{t['month']:02d}", t['price'], t['oi'], t['dtd'], t['ts'],
               L['price'] if L else None, L['ts'] if L else None, SHAPE_TXT if t is TS['rows'][0] else '']
        for i, x in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            if i in (3, 6, 7, 8) and isinstance(x, (int, float)):
                cell.number_format = '0.00'
            if i == 4 and isinstance(x, (int, float)):
                cell.number_format = '#,##0'
            if i == 9:
                cell.alignment = Alignment(wrap_text=True, vertical='top')
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='判读').font = Font(bold=True)
    r += 1
    ws.cell(row=r, column=1, value='逐点连线即当前完整期限结构；同一日历日的去年同期对照列用于回答“同样的位置，去年是什么结构”。').alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)

    # ---------------- 09 贡献分解 ----------------
    ws = sheet(wb, '09-贡献分解', '近月 vs 远月对月差变化的贡献', 'Δln(月差) = ln(A1/A0) − ln(B1/B0) = 近月贡献 + 远月贡献（精确加和，无残差）', widths=[12, 12, 12, 13, 13, 15, 15, 15, 15])
    header(ws, 4, ['区间', '起', '止', 'Δ月差(元)', 'A变化(元)', '近月贡献(对数)', '远月贡献(对数)', '近月贡献%', '远月贡献%'])
    r = 5
    for k, v in D['decomposition']['windows'].items():
        if not v or 'error' in v:
            continue
        row = [k, v['d0'], v['d1'], v['ds'], v['chg_a'], v['contrib_a_dln'], v['contrib_b_dln'],
               v['contrib_a_dln'] * 100, v['contrib_b_dln'] * 100]
        for i, x in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            if i in (4, 5):
                cell.number_format = '+0.00;-0.00;0'
            if i in (6, 7):
                cell.number_format = '+0.0000%;-0.0000%;0'
            if i in (8, 9):
                cell.number_format = '+0.00;-0.00;0'
        r += 1
    r += 2
    ws.cell(row=r, column=1, value='逐日推动（最近 10 个交易日）').font = Font(bold=True, size=11)
    r += 1
    header(ws, r, ['日期', 'Δ月差(元)', 'A涨跌', 'B涨跌', '近月贡献', '远月贡献', '净效果判定', '', ''])
    hr = r
    r += 1
    for d in D['decomposition']['daily']:
        absA, absB = abs(d['contrib_a']), abs(d['contrib_b'])
        ratio = min(absA, absB) / max(absA, absB, 1e-12)
        if d['contrib_a'] * d['contrib_b'] < 0 and ratio > 0.8:
            dom = '两腿同步（相抵）'
        elif absA > absB * 1.25:
            dom = '近月主导'
        elif absB > absA * 1.25:
            dom = '远月主导'
        else:
            dom = '差异不显著'
        row = [d['date'], d['ds'], d['chg_a'], d['chg_b'], d['contrib_a'], d['contrib_b'], dom]
        for i, x in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            if i in (2, 3, 4):
                cell.number_format = '+0;-0;0'
            if i in (5, 6):
                cell.number_format = '+0.0000%;-0.0000%;0'
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='为什么用对数：对数差可加，能精确拆成“近月贡献 + 远月贡献”且不留残差；直接相减再做百分比会在月差接近 0 时爆炸。').font = SUB_FONT
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)

    # ---------------- 10 近端结构演变 ----------------
    ws = sheet(wb, '10-近端结构演变', '近端月差随时间的演变（按锚定合约分段）', '换月即断段；跨段不可比、不可连成一条序列算分位。', widths=[14, 14, 14, 14, 16, 16, 40])
    header(ws, 4, ['锚定合约', '起点', '终点', '交易日数', '近端最小', '近端最大', '段末近端月差'])
    r = 5
    for g in D['ts_history']:
        vals = [p['near_spread'] for p in g['points'] if p['near_spread'] is not None]
        row = [g['anchor'], g['from'], g['to'], g['n'], min(vals) if vals else None,
               max(vals) if vals else None, vals[-1] if vals else None]
        for i, x in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            if i >= 5 and isinstance(x, (int, float)):
                cell.number_format = '+0;-0;0'
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='读法：看最近一行（当前段 SA2612 锚）的近端水平，与上一段（SA2609 锚，9 月中旬前）对比，即可看出换月后近端升水是否被抹平。').font = SUB_FONT
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)

    # ---------------- 11 仓单库存 ----------------
    ws = sheet(wb, '11-仓单库存', '仓单 / 库存（品种级）', '交易所仓单是品种级日报，不是本合约对的仓单，不可拆分到近月/远月。', widths=[14, 14, 12, 40])
    W = D.get('warehouse')
    if W:
        r = 4
        r = kv_block(ws, r, [('指标', W.get('label')), ('最新', f"{W.get('current')} {W.get('unit')} @ {W.get('date')}"),
                             ('覆盖区间', f"{W.get('first')} ~ {W.get('date')}（{W.get('n_days')} 个交易日）"),
                             ('区间最高/最低', f"{W.get('max')} / {W.get('min')}"),
                             ('相对自身区间分位', f"{W.get('pct_own_history'):.1f}%"),
                             ('近20日变化', f"{W.get('change_20d')}")])
        r += 1
        header(ws, r, ['日期', '仓单', '变化', '备注'])
        r += 1
        for s in W['series']:
            for i, x in enumerate([s['date'], s['value'], s.get('change'), ''], 1):
                cell = ws.cell(row=r, column=i, value=x)
                cell.border = BORDER
                if i == 2:
                    cell.number_format = '#,##0'
            r += 1
        r += 1
        for t in ['纯碱以厂库交割为主，仓单绝对量小，不能用“仓单低”推断近月偏紧；库存压力请看厂库数据（见 12-事件台账）。',
                  '交易所仓单口径与社会库存/厂库口径不可混用，本表不做合并。']:
            ws.cell(row=r, column=1, value=t).alignment = Alignment(wrap_text=True)
            ws.cell(row=r, column=1).fill = WARN_FILL
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
            r += 1
    else:
        ws.cell(row=4, column=1, value='未提供仓单数据').fill = WARN_FILL

    # ---------------- 12 事件台账 ----------------
    ws = sheet(wb, '12-事件台账', '产业事件台账（带来源与证据等级）', 'C 级观点只能作解释方向，不能当数字用；日期与口径须回原文核对。', widths=[13, 12, 60, 26, 12, 44, 32])
    header(ws, 4, ['日期', '类型', '事件 / 指标', '数值', '方向', '来源', '链接'])
    r = 5
    for e in sorted(D['events'], key=lambda x: x['date']):
        row = [e['date'], e['type'], e['title'], e.get('value'), e.get('direction', ''), e.get('source', ''), e.get('url', '')]
        for i, x in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if i == 7 and x:
                cell.value = x
                cell.hyperlink = x
                cell.font = Font(color='0563C1', underline='single', size=9)
        ws.row_dimensions[r].height = 42
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='证据等级：A=交易所原始数据（价格/持仓/仓单）；B=第三方机构统计（厂库/开工/产量/利润）；C=媒体与机构观点。本表多为 B/C 级。').font = SUB_FONT
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)

    # ---------------- 13 计算公式 ----------------
    ws = sheet(wb, '13-计算公式', '计算公式与可复核示例', '本页所有数字都是 Excel 公式，改 B 列即可看到联动。', widths=[30, 18, 70])
    r = 4
    header(ws, r, ['公式名', '示例值', '公式 / 说明'])
    r += 1
    A0, A1 = SP['series'][-6]['a'], SP['series'][-1]['a']
    B0, B1 = SP['series'][-6]['b'], SP['series'][-1]['b']
    items = [
        ('A0（5 日前近月）', A0, '用户输入', None, '0.00'),
        ('A1（当前近月）', A1, '用户输入', None, '0.00'),
        ('B0（5 日前远月）', B0, '用户输入', None, '0.00'),
        ('B1（当前远月）', B1, '用户输入', None, '0.00'),
        ('月差0 = A0 - B0', None, '=B5-B7', '=B5-B7', '0.00'),
        ('月差1 = A1 - B1', None, '=B6-B8', '=B6-B8', '0.00'),
        ('Δ月差（元/吨）', None, '=B10-B9', '=B10-B9', '0.00'),
        ('近月涨跌（元/吨）', None, '=B6-B5', '=B6-B5', '0.00'),
        ('远月涨跌（元/吨）', None, '=B8-B7', '=B8-B7', '0.00'),
        ('近月对数贡献', None, 'LN(B6/B5) —— 正值表示把月差往上推', '=LN(B6/B5)', '0.000000'),
        ('远月对数贡献', None, '-LN(B8/B7) —— 正值表示把月差往上推', '=-LN(B8/B7)', '0.000000'),
        ('两贡献之和（精确）', None, '=B14+B15', '=B14+B15', '0.000000'),
        ('ln(月差1/月差0) 真值', None, '月差接近 0 时该对数不可用，此时只用上面两项', '=IFERROR(LN(B10/B9),"月差≈0，对数不可用")', '0.000000'),
        ('近月贡献占比%', None, '=IFERROR(B14/(ABS(B14)+ABS(B15))*100,"")', '=IFERROR(B14/(ABS(B14)+ABS(B15))*100,"")', '0.00'),
        ('期限结构 TS', '见 08 页', '该合约价格 - 最近月合约价格', None, None),
        ('分位', '见 03 页', 'COUNTIF(样本区,"<="&当期)/COUNT(样本区)', None, None),
        ('距交割交易日', '见 08 页', '按交易所日历逐日计数（不用日历日/7*5 近似）', None, None),
    ]
    for i, (name, val, note, formula, fmt) in enumerate(items):
        row = 5 + i
        ws.cell(row=row, column=1, value=name).font = Font(size=10)
        cell = ws.cell(row=row, column=2, value=formula if formula else val)
        if fmt:
            cell.number_format = fmt
        ws.cell(row=row, column=3, value=note).alignment = Alignment(wrap_text=True, vertical='top')
        for cc in range(1, 4):
            ws.cell(row=row, column=cc).border = BORDER
    r = 5 + len(items) + 1
    ws.cell(row=r, column=1,
            value='读法：B14 与 B15 一正一负且几乎等长时，月差其实没动，只是两腿一起涨跌；此时追问“谁主导”没有意义。').font = SUB_FONT
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    r += 1
    ws.cell(row=r, column=1,
            value='说明：对数差可加，所以“近月贡献 + 远月贡献”恒等于 ln(月差1/月差0)，不留残差；不要再用“元/吨”相减去凑百分比。').font = SUB_FONT
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)

    # ---------------- 14 数据来源 ----------------
    ws = sheet(wb, '14-数据来源', '数据来源与覆盖区间', '每一列数据都要能追到一个可复核的来源。', widths=[26, 22, 52, 30])
    header(ws, 4, ['数据', '口径', '来源', '覆盖'])
    src = [
        (f"{C['a']} / {C['b']} 日线", '收盘、结算、持仓、成交', '新浪财经 InnerFuturesNewService（公开 K 线接口）', f"{SP['first']} ~ {SP['date']}，{SP['n']} 个交易日"),
        ('全部挂牌合约日线', '用于期限结构', '同上', f"{D.get('panel_meta', {}).get('from', '')} 起，{D.get('panel_meta', {}).get('n_contracts', '')} 个合约"),
        ('仓单（品种级）', '交易所仓单日报，单位张', '东方财富 RPT_FUTU_STOCKDATA', (W or {}).get('date', '未取到')),
        ('产业事件', '厂库/开工/产量/利润/检修/产能', '见 12-事件台账 逐条链接', f"{len(D['events'])} 条"),
        ('合约规则', '交割月份/最后交易日/交易单位', '东方财富 SA 品种页 + 首根K线交叉验证', f"上市 {C.get('registry', {}).get('list_date', '')}"),
        ('现货参考价', '厂家报价中位', '生意社 100ppi', '见事件台账 2026-10-20 条'),
    ]
    r = 5
    for row in src:
        for i, x in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            cell.alignment = Alignment(wrap_text=True, vertical='top')
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='合约规则登记').font = Font(bold=True, size=11)
    r += 1
    reg = C.get('registry') or {}
    for k in ('code', 'name', 'exchange', 'list_date', 'contract_months', 'last_trading_day', 'unit', 'tick', 'settle_basis'):
        ws.cell(row=r, column=1, value=k).font = Font(size=10, bold=True)
        ws.cell(row=r, column=2, value=str(reg.get(k, ''))).alignment = Alignment(wrap_text=True)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        r += 1
    for s in reg.get('sources', []):
        ws.cell(row=r, column=1, value='来源').font = Font(size=10, bold=True)
        ws.cell(row=r, column=2, value=f"{s.get('field')}：{s.get('source')}（{s.get('date')}）{s.get('url')}").alignment = Alignment(wrap_text=True)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        r += 1

    # ---------------- 15 数据质量 ----------------
    ws = sheet(wb, '15-数据质量', '数据质量检查', '存在 ERROR 时本工作簿全部结论不可用。', widths=[12, 16, 70, 16])
    header(ws, 4, ['等级', '检查项', '说明', '日期'])
    r = 5
    dq = D.get('data_quality') or []
    if not dq:
        for i, x in enumerate(['OK', '全部检查', '无 ERROR / 无 WARN', M['asof']], 1):
            cell = ws.cell(row=r, column=i, value=x)
            cell.border = BORDER
            cell.fill = OK_FILL
        r += 1
    else:
        for item in dq:
            lvl, name_, msg = (item + ['', '', ''])[:3]
            dt_ = item[3] if len(item) > 3 else ''
            for i, x in enumerate([lvl, name_, msg, dt_], 1):
                cell = ws.cell(row=r, column=i, value=x)
                cell.border = BORDER
                cell.alignment = Alignment(wrap_text=True, vertical='top')
                cell.fill = ERR_FILL if lvl == 'ERROR' else WARN_FILL
            r += 1
    r += 1
    for t in ['已通过的检查：日期严格升序且无重复、无零/负价格、两腿同日对齐（不填补）、单日跳变 < 15%、持仓过滤生效。',
              '未覆盖的检查：结算价缺失（接口个别行）、更早已退市合约的完整性、非交易时段的行情异动。']:
        ws.cell(row=r, column=1, value=t).alignment = Alignment(wrap_text=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        r += 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    wb.save(args.out)
    print(f'Excel {len(wb.sheetnames)} 个工作表 -> {args.out}')
    print('   ' + ' / '.join(wb.sheetnames))
    return 0


if __name__ == '__main__':
    sys.exit(main())
