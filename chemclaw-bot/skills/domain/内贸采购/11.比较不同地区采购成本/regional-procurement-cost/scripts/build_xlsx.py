# -*- coding: utf-8 -*-
"""research.json -> Excel 成本模型（openpyxl，含活公式）

用法：
    python build_xlsx.py <案例目录> [--out 输出路径]

设计原则（与 SKILL.md 三条硬规矩一致）：
  · 运费、装卸费是「输入格」（浅黄底），留空即未知，下游公式用 IF 判空显示「待补」，
    绝不会把空格当成 0 去算出一个看似精确的到厂价。
  · 到厂成本、因素分解、汇总排名全部用真公式，改参数后在 Excel 里即时重算。
  · 不内置任何假设运价。
"""
import argparse
import json
import os
import re
import sys

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------- 主题
INK, NAVY, NAVY_L = '0F172A', '0F4C81', 'E8F1F9'
AMBER, AMBER_L = 'B45309', 'FFF7E0'
GREEN, GREEN_L = '047857', 'EAF7EF'
RED, RED_L = 'B91C1C', 'FDECEC'
GREY, GREY_L, LINE, WHITE = '64748B', 'F4F8FC', 'D6DEE7', 'FFFFFF'
FONT = '微软雅黑'
MONO = 'Consolas'

TITLE_F = Font(name=FONT, size=14, bold=True, color=WHITE)
SUB_F = Font(name=FONT, size=9, italic=True, color=GREY)
H_F = Font(name=FONT, size=10, bold=True, color=WHITE)
BODY_F = Font(name=FONT, size=10, color=INK)
BOLD_F = Font(name=FONT, size=10, bold=True, color=INK)
SMALL_F = Font(name=FONT, size=9, color=GREY)
NUM_F = Font(name=MONO, size=10, color=INK)
NUM_B = Font(name=MONO, size=10, bold=True, color=INK)
LINK_F = Font(name=FONT, size=9, color='1D6FB8', underline='single')

THIN = Side(style='thin', color=LINE)
MED = Side(style='medium', color=AMBER)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
INPUT_BOX = Border(left=MED, right=MED, top=MED, bottom=MED)

FILL_HEAD = PatternFill('solid', fgColor=NAVY)
FILL_TITLE = PatternFill('solid', fgColor=NAVY)
FILL_INPUT = PatternFill('solid', fgColor=AMBER_L)
FILL_CALC = PatternFill('solid', fgColor=GREY_L)
FILL_WARN = PatternFill('solid', fgColor='FFFDF6')
FILL_BAD = PatternFill('solid', fgColor=RED_L)
FILL_OK = PatternFill('solid', fgColor=GREEN_L)
FILL_REF = PatternFill('solid', fgColor=NAVY_L)

WRAP = Alignment(horizontal='left', vertical='top', wrap_text=True)
CTR = Alignment(horizontal='center', vertical='center', wrap_text=True)
RIGHT = Alignment(horizontal='right', vertical='center')

N0 = '#,##0'
N2 = '#,##0.00'
SIGN2 = '+#,##0.00;-#,##0.00;0'


def _title(ws, text, sub, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=text)
    c.font, c.fill = TITLE_F, FILL_TITLE
    c.alignment = Alignment(horizontal='left', vertical='center', indent=1)
    ws.row_dimensions[1].height = 30
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        s = ws.cell(row=2, column=1, value=sub)
        s.font = SUB_F
        s.alignment = Alignment(horizontal='left', vertical='center', indent=1, wrap_text=True)
        ws.row_dimensions[2].height = 28


def _head(ws, row, headers, widths=None):
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font, c.fill, c.alignment = H_F, FILL_HEAD, CTR
        c.border = Border(bottom=THIN)
    ws.row_dimensions[row].height = 32
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def _inp(c, fmt=None):
    c.fill, c.border, c.font = FILL_INPUT, INPUT_BOX, NUM_F
    if fmt:
        c.number_format = fmt


def _calc(c, fmt=None):
    c.fill, c.font = FILL_CALC, NUM_F
    if fmt:
        c.number_format = fmt


def _body(ws, row, ncol):
    for i in range(1, ncol + 1):
        c = ws.cell(row=row, column=i)
        # openpyxl 返回 StyleProxy，必须 copy 后才能回写
        if not (c.font and c.font.name):
            c.font = BODY_F
        if not c.alignment.horizontal:
            c.alignment = WRAP
        c.border = Border(bottom=Side(style='hair', color=LINE))


def _note(ws, row, ncol, text, rows=4):
    ws.merge_cells(start_row=row, start_column=1, end_row=row + rows - 1, end_column=ncol)
    c = ws.cell(row=row, column=1, value=text)
    c.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    c.font = SMALL_F
    c.fill = PatternFill('solid', fgColor='F8FAFC')


# ---------------------------------------------------------------- 主构建
def build(D, out):
    wb = Workbook()
    wb.remove(wb.active)

    meta = D.get('meta', {})
    req = D.get('request', {})
    prod = D.get('product', {})
    regions = D.get('regions', [])
    routes = {r['id']: r for r in D.get('routes', [])}
    quotes = {q['id']: q for q in D.get('quotes', [])}
    sources = {s['id']: s for s in D.get('sources', [])}
    cost = D.get('cost_params', {})
    ref_id = D.get('benchmark_region_id')

    # ============================ 0-说明
    ws = wb.create_sheet('0-说明')
    ws.sheet_view.showGridLines = False
    ws.column_dimensions['A'].width = 3
    ws.column_dimensions['B'].width = 24
    ws.column_dimensions['C'].width = 96
    _title(ws, '{0} · 区域采购成本模型'.format(req.get('product') or prod.get('name') or '产品'),
           '口径：含税人民币元/吨｜浅黄底=需你填写，灰蓝底=公式自动算｜留空一律表示「未知」，不是 0', 3)

    r = 4
    rows = [
        ('产品 / 规格', '{0}｜{1}'.format(req.get('product', ''), prod.get('spec', ''))),
        ('收货地', req.get('receipt_address', '')),
        ('采购数量（吨）', cost.get('qty')),
        ('价格口径', '含 {0}% 增值税，元/吨（净重）'.format(int((prod.get('tax') or {}).get('goods_vat', 0.13) * 100))),
        ('基准区域', next((x['name'] for x in regions if x['id'] == ref_id), '—')),
        ('生成时间', meta.get('generated_at', '')),
    ]
    for k, v in rows:
        ws.cell(row=r, column=2, value=k).font = BOLD_F
        c = ws.cell(row=r, column=3, value=v)
        c.font, c.alignment = BODY_F, Alignment(vertical='center')
        r += 1

    r += 1
    ws.cell(row=r, column=2, value='工作表导航').font = Font(name=FONT, size=11, bold=True, color=NAVY)
    r += 1
    nav = [
        ('1-参数', '采购数量、税率、装卸费单价。改这里，全表联动。'),
        ('2-价格口径', '各区域现货价、区间、交货方式、数据日、来源；含税与不含税并列。'),
        ('3-到厂成本', '逐区域填运费，自动算到厂单价与整单总额；运费留空显示「待补」。'),
        ('4-因素分解', '相对基准区域，把到厂差拆成 裸价差+运输差+装卸差，并校验是否闭合。'),
        ('5-线路与距离', '每条线路的起点/终点/可核验里程/高速方案/替代运输方式。'),
        ('6-历史价差', '同日同规格的分区价差序列与极差。'),
        ('7-缺口与假设', '缺哪些参数、为什么缺、补上会怎样。'),
        ('8-来源', '每个价格对应的原始出处与采集日。'),
    ]
    for a, b in nav:
        ws.cell(row=r, column=2, value=a).font = BOLD_F
        ws.cell(row=r, column=3, value=b).font = BODY_F
        r += 1

    r += 1
    ws.cell(row=r, column=2, value='三条硬规矩').font = Font(name=FONT, size=11, bold=True, color=RED)
    r += 1
    for t in D.get('gap_rules', []):
        c = ws.cell(row=r, column=3, value='· ' + t)
        c.font, c.alignment = BODY_F, WRAP
        ws.row_dimensions[r].height = 28
        r += 1

    # ============================ 1-参数
    ws = wb.create_sheet('1-参数')
    ws.sheet_view.showGridLines = False
    _title(ws, '采购参数（改这里，全表联动）',
           '浅黄底为输入项。装卸费留空 = 未知，下游显示「待补」而不是 0。', 4)
    _head(ws, 4, ['参数', '取值', '单位', '说明'], [26, 16, 12, 62])

    spec = [
        ('采购数量', cost.get('qty', 100), '吨', '100 吨约 3.2 车（13m 半挂按 31 吨/车）', N0),
        ('运费税率', cost.get('taxRate', 9), '%', '公路运输增值税 9%，一般纳税人可抵扣', N0),
        ('装车费', cost.get('loadingUnit'), '元/吨', '留空=未知；填 0 表示「已包含在车板价内」', N2),
        ('卸车费', cost.get('unloadingUnit'), '元/吨', '留空=未知', N2),
        ('检测/取样费', cost.get('inspectionUnit'), '元/吨', '留空=未知', N2),
        ('货物增值税率', 13, '%', '纯碱适用 13%', N0),
    ]
    for i, (k, v, u, d, fmt) in enumerate(spec):
        row = 5 + i
        ws.cell(row=row, column=1, value=k).font = BODY_F
        _inp(ws.cell(row=row, column=2, value=v), fmt)
        ws.cell(row=row, column=3, value=u).alignment = CTR
        ws.cell(row=row, column=4, value=d).alignment = WRAP
        ws.row_dimensions[row].height = 20
        _body(ws, row, 4)

    P_QTY = "'1-参数'!$B$5"
    P_LOAD = "'1-参数'!$B$7"
    P_UNLOAD = "'1-参数'!$B$8"
    P_GOODS = "'1-参数'!$B$10"

    ws.cell(row=13, column=1, value='提示').font = Font(name=FONT, size=10, bold=True, color=AMBER)
    ws.merge_cells(start_row=13, start_column=2, end_row=14, end_column=4)
    c = ws.cell(row=13, column=2, value=(
        '这里的装卸费是全线路统一值。若某条线路的装卸口径不同（例如自提货由卖方装车、'
        '送到货由买方卸车），请在「3-到厂成本」对应行的「装车元/吨、卸车元/吨」列单独填写覆盖。'))
    c.alignment, c.font = WRAP, SMALL_F

    # ============================ 2-价格口径
    ws = wb.create_sheet('2-价格口径')
    ws.sheet_view.showGridLines = False
    _title(ws, '各地区现货价格（统一口径后）',
           '同规格、同单位、同税费口径、同数据日。交货方式（送到/自提/出厂）不同，是不能直接比大小的关键原因。', 11)
    _head(ws, 4, ['区域', '市场归属', '规格', '交货方式', '价格下限', '价格上限', '取用值(含税)',
                  '不含税(元/吨)', '数据日', '来源', '备注'],
          [10, 12, 22, 12, 11, 11, 13, 13, 12, 20, 56])

    for i, rg in enumerate(regions):
        row = 5 + i
        q = quotes.get(rg.get('quote_id'), {})
        ws.cell(row=row, column=1, value=rg['name']).font = BOLD_F
        ws.cell(row=row, column=2, value=rg.get('market', '')).alignment = CTR
        ws.cell(row=row, column=3, value=q.get('spec', '')).alignment = WRAP
        ws.cell(row=row, column=4, value=q.get('delivery_basis', '')).alignment = CTR
        ws.cell(row=row, column=5, value=q.get('price_low')).number_format = N0
        ws.cell(row=row, column=6, value=q.get('price_high')).number_format = N0
        if q.get('price_low') is not None and q.get('price_high') is not None:
            c = ws.cell(row=row, column=7, value='=ROUND(AVERAGE(E{0}:F{0}),0)'.format(row))
        else:
            c = ws.cell(row=row, column=7, value=q.get('price'))
        _calc(c, N0)
        c = ws.cell(row=row, column=8,
                    value='=IF(G{0}="","",ROUND(G{0}/(1+{1}/100),2))'.format(row, P_GOODS))
        _calc(c, N2)
        ws.cell(row=row, column=9, value=q.get('date', '')).alignment = CTR
        src = sources.get(q.get('source_id'), {})
        ws.cell(row=row, column=10, value=src.get('name', q.get('source_id', ''))).alignment = WRAP
        notes = []
        if '自提' in str(q.get('delivery_basis', '')):
            notes.append('⚠ 自提价：买方自担提货运输')
        if q.get('price_low') is not None and q.get('price_high') is not None \
                and q['price_high'] - q['price_low'] >= 100:
            notes.append('区间宽，建议上下限各算一遍')
        c = ws.cell(row=row, column=11, value='；'.join(notes))
        c.alignment = WRAP
        ws.row_dimensions[row].height = 32
        _body(ws, row, 11)
        if notes:
            for cc in range(1, 12):
                ws.cell(row=row, column=cc).fill = FILL_WARN

    # ============================ 3-到厂成本
    ws = wb.create_sheet('3-到厂成本')
    ws.sheet_view.showGridLines = False
    _title(ws, '到厂成本计算（填运费 → 自动出到厂价）',
           '运费三种填法按优先级：总运费 > 包干运价(元/吨)。都空则该行「待补」，不参与排名。', 11)
    _head(ws, 4, ['区域', '裸价\n(元/吨)', '里程\n(km)', '包干运价\n(元/吨)', '总运费\n(元)', '运费\n(元/吨)',
                  '装车\n(元/吨)', '卸车\n(元/吨)', '到厂单价\n(元/吨)', '整单总额\n(元)', '状态'],
          [11, 11, 9, 12, 12, 11, 10, 10, 13, 14, 12])

    PER = len(regions)  # 价格表与到厂表行号一一对应
    first, last = 5, 4 + PER
    for i, rg in enumerate(regions):
        row = 5 + i
        rt = routes.get(rg.get('route_id'), {})
        legs = ((rt.get('distance') or {}).get('legs')) or rt.get('legs') or []
        km = legs[0]['km'] if legs else None

        ws.cell(row=row, column=1, value=rg['name']).font = BOLD_F
        c = ws.cell(row=row, column=2, value="='2-价格口径'!G{0}".format(row))
        _calc(c, N0)
        _inp(ws.cell(row=row, column=3, value=km), N0)
        _inp(ws.cell(row=row, column=4, value=rt.get('freight_unit')), N2)
        _inp(ws.cell(row=row, column=5, value=rt.get('freight_total')), N0)
        c = ws.cell(row=row, column=6, value=(
            '=IF(E{0}<>"",ROUND(E{0}/{1},2),IF(D{0}<>"",D{0},""))'.format(row, P_QTY)))
        _calc(c, N2)
        _inp(ws.cell(row=row, column=7, value=rt.get('loading_total')), N2)
        _inp(ws.cell(row=row, column=8, value=rt.get('unloading_total')), N2)
        # 到厂单价 = 裸价 + 运费/吨 + 统一的装车卸车（若本行无覆盖则用参数表）
        c = ws.cell(row=row, column=9, value=(
            '=IF(OR(B{0}="",F{0}=""),"",ROUND(B{0}+F{0}+'
            'IF(G{0}<>"",G{0},{1})+IF(H{0}<>"",H{0},{2}),2))'.format(row, P_LOAD, P_UNLOAD)))
        _calc(c, N2)
        c = ws.cell(row=row, column=10,
                    value='=IF(I{0}="","",ROUND(I{0}*{1},0))'.format(row, P_QTY))
        _calc(c, N0)
        c = ws.cell(row=row, column=11, value='=IF(I{0}="","待补：缺运费","可算")'.format(row))
        c.font = Font(name=FONT, size=9, bold=True, color=RED)
        c.alignment = CTR
        ws.row_dimensions[row].height = 20
        _body(ws, row, 11)

    srow = last + 1
    ws.cell(row=srow, column=1, value='汇总').font = BOLD_F
    ws.cell(row=srow, column=2, value='裸价最低：').font = SMALL_F
    ws.merge_cells(start_row=srow, start_column=3, end_row=srow, end_column=4)
    c = ws.cell(row=srow, column=3, value=(
        '=IF(COUNT(B{0}:B{1})=0,"—",INDEX(A{0}:A{1},MATCH(MIN(B{0}:B{1}),B{0}:B{1},0)))'
        .format(first, last)))
    c.font, c.alignment = BOLD_F, CTR
    ws.cell(row=srow, column=5, value='到厂最低：').font = SMALL_F
    ws.merge_cells(start_row=srow, start_column=6, end_row=srow, end_column=8)
    c = ws.cell(row=srow, column=6, value=(
        '=IF(COUNT(I{0}:I{1})<{2},"不排名（有缺项）",INDEX(A{0}:A{1},MATCH(MIN(I{0}:I{1}),I{0}:I{1},0)))'
        .format(first, last, PER)))
    c.font, c.alignment = BOLD_F, CTR
    _calc(ws.cell(row=srow, column=9,
                  value='=IF(COUNT(I{0}:I{1})<{2},"待补",ROUND(MIN(I{0}:I{1}),0))'
                  .format(first, last, PER)), N0)
    _calc(ws.cell(row=srow, column=10,
                  value='=IF(COUNT(J{0}:J{1})<{2},"待补",ROUND(SUM(J{0}:J{1}),0))'
                  .format(first, last, PER)), N0)
    c = ws.cell(row=srow, column=11,
                value='=IF(COUNT(I{0}:I{1})<{2},"✗ 不完整","✓ 齐全")'.format(first, last, PER))
    c.font, c.alignment = BOLD_F, CTR
    ws.row_dimensions[srow].height = 20

    _note(ws, srow + 2, 11, (
        '填法说明：\n'
        '1) 只填「包干运价(元/吨)」→ 运费/吨 = 该价；整单总额 = (裸价+运费+装卸) × 数量；\n'
        '2) 只填「总运费(元)」→ 运费/吨 = 总运费 ÷ 数量（整单议价时用这个）；\n'
        '3) 两者都填 → 以总运费为准（整单结算更接近实际）；\n'
        '4) 全空 → 该行到厂单价为空，汇总显示「不排名」。\n'
        '5) 「装车/卸车」本行为空时，自动取「1-参数」中的统一值；本行填了就用本行的。'), rows=5)

    # ============================ 4-因素分解
    ws = wb.create_sheet('4-因素分解')
    ws.sheet_view.showGridLines = False
    _title(ws, '到厂成本差异的因素分解',
           '以基准区域为 0，把到厂差拆成「市场裸价差 + 运输费用差 + 装卸差」。三项合计必须等于 Δ到厂。', 11)
    _head(ws, 4, ['区域', '裸价\n(元/吨)', '运费/吨', '装卸/吨', '到厂单价',
                  'Δ裸价', 'Δ运费', 'Δ装卸', '三项合计', 'Δ到厂', '校验'],
          [13, 11, 11, 11, 12, 11, 11, 11, 12, 12, 15])

    ref_name = next((x['name'] for x in regions if x['id'] == ref_id), regions[0]['name'] if regions else '')
    ref_row = first + next((i for i, x in enumerate(regions) if x['name'] == ref_name), 0)

    for i, rg in enumerate(regions):
        row = 5 + i
        lbl = rg['name'] + ('（基准）' if rg['name'] == ref_name else '')
        ws.cell(row=row, column=1, value=lbl).font = BOLD_F
        _calc(ws.cell(row=row, column=2, value="='3-到厂成本'!B{0}".format(row)), N0)
        _calc(ws.cell(row=row, column=3,
                      value='=IF(\'3-到厂成本\'!F{0}="","",\'3-到厂成本\'!F{0})'.format(row)), N2)
        _calc(ws.cell(row=row, column=4,
                      value='=ROUND(N(\'3-到厂成本\'!G{0})+N(\'3-到厂成本\'!H{0}),2)'.format(row)), N2)
        _calc(ws.cell(row=row, column=5,
                      value='=IF(\'3-到厂成本\'!I{0}="","",\'3-到厂成本\'!I{0})'.format(row)), N2)
        _calc(ws.cell(row=row, column=6,
                      value='=IF(OR(B{0}="",B{1}=""),"",B{0}-B{1})'.format(row, ref_row)), SIGN2)
        _calc(ws.cell(row=row, column=7,
                      value='=IF(OR(C{0}="",C{1}=""),"",C{0}-C{1})'.format(row, ref_row)), SIGN2)
        _calc(ws.cell(row=row, column=8, value='=D{0}-D{1}'.format(row, ref_row)), SIGN2)
        _calc(ws.cell(row=row, column=9,
                      value='=IF(OR(F{0}="",G{0}=""),"待补",ROUND(F{0}+G{0}+H{0},2))'.format(row)), SIGN2)
        _calc(ws.cell(row=row, column=10,
                      value='=IF(OR(E{0}="",E{1}=""),"待补",ROUND(E{0}-E{1},2))'.format(row, ref_row)), SIGN2)
        c = ws.cell(row=row, column=11, value=(
            '=IF(OR(I{0}="待补",J{0}="待补"),"缺运费",'
            'IF(ABS(I{0}-J{0})<0.01,"✓ 闭合","✗ 差 "&TEXT(I{0}-J{0},"0.00")))'.format(row)))
        c.font, c.alignment = SMALL_F, CTR
        ws.row_dimensions[row].height = 20
        _body(ws, row, 11)
        if rg['name'] == ref_name:
            for cc in range(1, 12):
                ws.cell(row=row, column=cc).fill = FILL_REF

    _note(ws, 5 + PER + 1, 11, (
        '读法：\n'
        '· Δ裸价 < 0 表示该区域裸价更便宜；Δ运费 > 0 表示到该区域的运费更贵；\n'
        '· 「三项合计」= 「Δ到厂」 说明差异被三项解释完（校验列显示「✓ 闭合」）；\n'
        '· 显示「缺运费」= 该区域还没填运价，此时只能比裸价差，不能得出到厂结论；\n'
        '· 不要用「里程 × 某个拍脑袋的吨公里价」来填空——那不是承运方报价。'), rows=5)

    # ============================ 5-线路与距离
    ws = wb.create_sheet('5-线路与距离')
    ws.sheet_view.showGridLines = False
    _title(ws, '运输线路与可核验里程',
           '里程来自可在线复核的公路路线（高速主推方案）。拿到承运方 GPS 实跑里程后，直接改「里程(km)」。', 8)
    _head(ws, 4, ['区域', '起点（低端/高端）', '终点', '里程(km)', '里程依据', '高速方案', '可替代运输方式', '时效(h)'],
          [11, 30, 10, 11, 14, 34, 46, 9])

    for i, rt in enumerate(D.get('routes', [])):
        row = 5 + i
        rg_name = next((x['name'] for x in regions if x.get('route_id') == rt['id']), rt.get('label', ''))
        dist = rt.get('distance') or {}
        legs = dist.get('legs') or rt.get('legs') or []
        lo = legs[0] if legs else {}
        hi = legs[-1] if len(legs) > 1 else None
        ws.cell(row=row, column=1, value=rg_name).font = BOLD_F
        origin = '{0}（{1} km）'.format(lo.get('from', ''), lo.get('km'))
        if hi:
            origin += '\n{0}（{1} km）'.format(hi.get('from', ''), hi.get('km'))
        c = ws.cell(row=row, column=2, value=origin)
        c.alignment = WRAP
        ws.cell(row=row, column=3, value=rt.get('dest_city', '')).alignment = CTR
        _inp(ws.cell(row=row, column=4, value=lo.get('km')), N0)
        ws.cell(row=row, column=5, value='已核验' if dist.get('verified') else '待核验').alignment = CTR
        ws.cell(row=row, column=6, value=lo.get('road', '')).alignment = WRAP
        alts = '\n'.join('{0}：{1}'.format(a.get('mode', ''), a.get('note', ''))
                         for a in rt.get('alternatives', []))
        ws.cell(row=row, column=7, value=alts).alignment = WRAP
        ws.cell(row=row, column=8, value=lo.get('hours')).alignment = CTR
        ws.row_dimensions[row].height = max(32, len(rt.get('alternatives', [])) * 16 + 18)
        _body(ws, row, 8)

    _note(ws, 5 + len(D.get('routes', [])) + 1, 8, (
        '为什么一个省要用两个起点：单个城市代表不了一个省。山东东端（潍坊）到苏州 760 km，'
        '西端（济宁）707 km；河北真正的省内产能集中在唐山（1126 km），比沙河市场所在地多 127 km。'
        '所以到厂成本应给「低端—高端」区间，而不是一个点。'), rows=4)

    # ============================ 6-历史价差
    ws = wb.create_sheet('6-历史价差')
    ws.sheet_view.showGridLines = False
    _title(ws, '历史区域价差',
           '只统计「同一天、同规格、同交货口径」都有报价的日期；缺的那天不插值、不拼凑。', 2 + len(regions))
    heads = ['日期'] + ['{0}\n(元/吨)'.format(x['name']) for x in regions] + ['区域极差']
    _head(ws, 4, heads)

    hist = D.get('history', {})
    spread_raw = hist.get('regional_spread') or []
    by_date = {}
    for p in spread_raw:
        by_date.setdefault(p['date'], {})[p.get('region_key')] = p

    r = 5
    for d in sorted(by_date, reverse=True):
        ws.cell(row=r, column=1, value=d).alignment = CTR
        for j, rg in enumerate(regions):
            v = by_date[d].get(rg['name']) or by_date[d].get(rg['id'])
            c = ws.cell(row=r, column=2 + j,
                        value='{0}–{1}'.format(v['heavy_low'], v['heavy_high']) if v else '—')
            c.alignment = CTR
            c.font = MONO_F if v else SMALL_F
        a = get_column_letter(2)
        b = get_column_letter(1 + len(regions))
        c = ws.cell(row=r, column=2 + len(regions),
                    value='=IFERROR(MAX({0}{1}:{2}{1})-MIN({0}{1}:{2}{1}),"")'.format(a, r, b))
        c.font, c.alignment = NUM_B, CTR
        _body(ws, r, 2 + len(regions))
        r += 1

    if not by_date:
        _note(ws, 5, 2 + len(regions), '本案例未采集到同日可比的分区报价，故不做历史价差统计（不跨日期拼凑）。')
    else:
        _note(ws, r + 1, 2 + len(regions), (
            '说明：「区域极差」是对该日各区报价中值两两比较的最大差，反映当日区域分化程度。'
            '这些日期不是每个区域都有同日报价，缺的日期不插值，因此统计只覆盖可比日。'))

    # ============================ 7-缺口与假设
    ws = wb.create_sheet('7-缺口与假设')
    ws.sheet_view.showGridLines = False
    _title(ws, '数据缺口与关键假设',
           '缺失项不会被估算填充，只会被标出来。补齐之后才能做排名。', 6)
    _head(ws, 4, ['级别', '缺口', '缺什么', '为什么缺', '怎么补', '影响'],
          [10, 18, 34, 34, 42, 34])
    r = 5
    for g in D.get('gaps', []):
        sev = g.get('severity', 'warn')
        c = ws.cell(row=r, column=1, value='阻断' if sev == 'blocker' else '提示')
        c.alignment, c.font = CTR, BOLD_F
        if sev == 'blocker':
            c.fill = FILL_BAD
        ws.cell(row=r, column=2, value=g.get('title') or g.get('key', '')).font = BOLD_F
        for j, k in enumerate(['what', 'why', 'how_to_fix', 'impact'], start=3):
            ws.cell(row=r, column=j, value=g.get(k, '')).alignment = WRAP
        ws.row_dimensions[r].height = 54
        _body(ws, r, 6)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value='关键假设').font = Font(name=FONT, size=11, bold=True, color=NAVY)
    r += 1
    for a in D.get('assumptions', []):
        ws.cell(row=r, column=1, value=a.get('key', '')).font = BOLD_F
        ws.cell(row=r, column=1).alignment = CTR
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        c = ws.cell(row=r, column=2, value=a.get('text', ''))
        c.alignment = WRAP
        ws.row_dimensions[r].height = 32
        _body(ws, r, 6)
        r += 1

    # ============================ 8-来源
    ws = wb.create_sheet('8-来源')
    ws.sheet_view.showGridLines = False
    _title(ws, '数据来源', '每个价格都能点回原文。', 7)
    _head(ws, 4, ['编号', '来源', '类型', '口径等级', '采集时间', '链接', '备注'],
          [8, 30, 16, 18, 20, 52, 34])
    for i, (k, s) in enumerate(sources.items()):
        row = 5 + i
        ws.cell(row=row, column=1, value=k).font = BOLD_F
        ws.cell(row=row, column=2, value=s.get('name', '')).alignment = WRAP
        ws.cell(row=row, column=3, value=s.get('type', '')).alignment = CTR
        ws.cell(row=row, column=4, value=s.get('level', '')).alignment = CTR
        ws.cell(row=row, column=5, value=s.get('retrieved_at', '')).alignment = CTR
        if s.get('url'):
            c = ws.cell(row=row, column=6, value=s['url'])
            c.hyperlink, c.font = s['url'], LINK_F
            c.alignment = Alignment(horizontal='left', vertical='center')
        ws.cell(row=row, column=7, value=s.get('note', '')).alignment = WRAP
        ws.row_dimensions[row].height = 30
        _body(ws, row, 7)

    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    wb.save(out)
    return out


MONO_F = Font(name=MONO, size=9.5, color=INK)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('case_dir', help='案例目录，如 examples/01-soda-ash-su-zhou')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    case_dir = os.path.abspath(a.case_dir)
    with open(os.path.join(case_dir, 'data', 'research.json'), encoding='utf-8') as f:
        D = json.load(f)
    out = a.out or os.path.join(case_dir, 'output', 'cost-model.xlsx')
    build(D, out)
    print('[build_xlsx] {0}  {1:.0f} KB'.format(out, os.path.getsize(out) / 1024))


if __name__ == '__main__':
    main()
