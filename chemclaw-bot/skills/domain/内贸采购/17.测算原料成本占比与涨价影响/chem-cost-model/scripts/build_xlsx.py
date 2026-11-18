#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 Excel 工作簿（真实公式版：改基础参数 → 自动重算）。

设计要点
--------
* 只有"原始输入"（单耗、价格、涨跌幅、历史价格）是硬编码值；
  其余（单项成本、占比、敏感性、组合情景、历史成本、贡献比）**全部是 Excel 公式**。
* 产品无关：所有公式都按 原料行数 / 幅度档数动态生成。
* 没有价格的原料：成本列写空字符串而不是 0，占比用 IF 保护，避免把缺口伪装成 0。
"""
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

C_DEEP = '1F3A5F'
C_MAIN = '2F5D8C'
C_ACC = 'C1442E'
C_HEAD = 'EAF0F6'
C_INPUT = 'FFF2CC'
THIN = Side(style='thin', color='C8D0DA')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_TITLE = Font(name='微软雅黑', size=15, bold=True, color=C_DEEP)
F_SUB = Font(name='微软雅黑', size=9, color='5A6B7B')
F_H2 = Font(name='微软雅黑', size=11, bold=True, color=C_ACC)
F_HEAD = Font(name='微软雅黑', size=9.5, bold=True, color='FFFFFF')
F_BODY = Font(name='微软雅黑', size=9.5)
F_BOLD = Font(name='微软雅黑', size=9.5, bold=True)
FILL_HEAD = PatternFill('solid', fgColor=C_MAIN)
FILL_INPUT = PatternFill('solid', fgColor=C_INPUT)
FILL_CALC = PatternFill('solid', fgColor='F4F7FA')
FILL_GAP = PatternFill('solid', fgColor='FDE8E8')
FILL_SUB = PatternFill('solid', fgColor=C_HEAD)

NUM2 = '#,##0.00'
NUM4 = '0.0000'
NUM6 = '0.000000'
NUM0 = '#,##0'
PCT = '0.0%'
PCT2 = '0.00%'
PCTLBL = '0.00"%"'
# 涨跌幅输入格：存小数（-0.10），显示带符号百分数；热力图公式里再 ×100 换算
PCT_LBL_SIGNED = '+0.00"%";-0.00"%"'
DATE = 'yyyy-mm-dd'

# 单耗单位 -> 系数（得到 t/t）
DOS_FACTOR = {'t/t': 1.0, 'ton/t': 1.0, '吨/吨': 1.0, 'kg/t': 0.001, 'kg/kg': 1.0,
              'g/t': 1e-6, '克/t': 1e-6}
# 计价单位 -> 系数（得到 元/t）
PRICE_FACTOR = {'CNY/t': 1.0, '元/吨': 1.0, 'RMB/t': 1.0, 'CNY/kg': 1000.0,
                '元/千克': 1000.0, '元/公斤': 1000.0, 'USD/t': None, 'USD/kg': None}


def title(ws, text, sub=None):
    ws['A1'] = text
    ws['A1'].font = F_TITLE
    if sub:
        ws['A2'] = sub
        ws['A2'].font = F_SUB
    ws.sheet_view.showGridLines = False
    ws.row_dimensions[1].height = 24


def h2(ws, r, text, span=6):
    c = ws.cell(row=r, column=1, value=text)
    c.font = F_H2
    return r


def header(ws, row, cols, height=30):
    for i, c in enumerate(cols, start=1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = F_HEAD
        cell.fill = FILL_HEAD
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = height


def widths(ws, w):
    for i, x in enumerate(w, start=1):
        ws.column_dimensions[get_column_letter(i)].width = x


def put(ws, r, c, v, fmt=None, fill=None, bold=False, wrap=False, align=None, border=True):
    cell = ws.cell(row=r, column=c)
    cell.value = v
    cell.font = F_BOLD if bold else F_BODY
    if fmt:
        cell.number_format = fmt
    if fill is not None:
        cell.fill = fill
    if border:
        cell.border = BORDER
    if align is None:
        align = 'right' if isinstance(v, (int, float)) else 'left'
    cell.alignment = Alignment(horizontal=align, vertical='center', wrap_text=wrap)
    return cell


def note(ws, r, text, span=6):
    cell = ws.cell(row=r, column=1, value=text)
    cell.font = F_SUB
    cell.alignment = Alignment(wrap_text=True, vertical='top')
    if span and span > 1:          # 单格"合并"是非法操作，会造成 Excel 拒绝打开
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=span)
    ws.row_dimensions[r].height = max(15, 15 * (1 + len(str(text)) // 90))


def build(R, data, path):
    wb = Workbook()
    allm = R['materials']
    comp = [m for m in allm if m.get('cost') is not None]
    rates = R['rates']
    nr = len(rates)
    nrow = len(allm)

    # ------------------------------------------------------------ 0 封面说明
    ws = wb.active
    ws.title = '0_封面说明'
    ws.sheet_view.showGridLines = False
    ws['A1'].font = F_TITLE
    title(ws, '%s · 理论原料成本分析工作簿' % R['meta'].get('product', ''),
          '数据截止 %s ｜ 价格口径：%s ｜ 币种 CNY ｜ 单位：元/吨产品 ｜ 由 chem-cost-model skill 生成'
          % (R['meta'].get('as_of', ''), R['price_basis']['label']))
    widths(ws, [24, 30, 30, 26, 34])
    r = 4
    info = [('产品', R['meta'].get('product')),
            ('产品 CAS', R['meta'].get('product_cas', '—')),
            ('工艺口径', R['meta'].get('process_name', '—')),
            ('工艺说明', R['meta'].get('process_desc', '—')),
            ('反应式', R['meta'].get('reaction', '—')),
            ('数据截止日', R['meta'].get('as_of')),
            ('采购方 / 视角', R['meta'].get('buyer', '—')),
            ('区域口径', R['meta'].get('region', '—')),
            ('单耗口径', R['params']['basis_label'])]
    for k, v in info:
        put(ws, r, 1, k, fill=FILL_SUB, bold=True, wrap=True)
        put(ws, r, 2, v, wrap=True)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        ws.row_dimensions[r].height = 30 if len(str(v)) > 70 else 18
        r += 1

    r += 1
    h2(ws, r, '本工作簿怎么用')
    r += 1
    for s in ['① 只改「1_原料参数」的黄色单元格（单耗、价格、规格/地区/来源）与「3_敏感性矩阵」第 5 行的涨跌幅；',
              '② 「2_成本构成」「3_敏感性矩阵」「4_组合情景明细」「5_历史理论成本」「6_贡献分解」全部是公式，改数即联动；',
              '③ 「5_历史理论成本」的价格列是真实序列，可替换为你自己的采购成交价（保持日期列）；',
              '④ 无可靠价格的原料，价格留空 —— 成本显示为空、占比受 IF 保护，这是"缺口"，不要填 0。']:
        ws.cell(row=r, column=1, value=s).font = F_SUB
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        r += 1

    r += 1
    h2(ws, r, '未纳入的成本项（理论原料成本 ≠ 完整生产成本 ≠ 利润）')
    r += 1
    header(ws, r, ['未纳入项', '原因 / 影响', '', '', ''], height=20)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    r += 1
    for it in R['not_included']:
        put(ws, r, 1, it.get('item'), wrap=True)
        put(ws, r, 2, it.get('reason', ''), wrap=True)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        r += 1
    if R['unquantified']:
        r += 1
        h2(ws, r, '文献中存在但无法量化的项')
        r += 1
        for it in R['unquantified']:
            put(ws, r, 1, it.get('item'), wrap=True)
            put(ws, r, 2, '原因：%s ｜ 影响：%s' % (it.get('why', ''), it.get('impact', '')), wrap=True)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
            r += 1

    r += 1
    h2(ws, r, '使用限制')
    r += 1
    for s in ['本表是"理论原料成本"模型：只含"有价格的原料单耗 × 价格"，不含能源、人工、折旧、维护、运输、包装与期间费用。',
              '不得把本表结果当作完整生产成本、销售成本或利润，也不得据此对外报价。',
              '本表不预测原料未来价格；敏感性矩阵只是"若涨/跌 X% 则成本变化"的机械演算。',
              '单耗为行业典型值时，已在「1_原料参数」列明来源与适用工艺；替换为企业实测值后结论可能显著改变。',
              '历史价格缺口未插值，一律留空；数据来源见「7_数据来源」与「9_缺口与待补」。']:
        ws.cell(row=r, column=1, value='· ' + s).font = F_SUB
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        r += 1

    # ------------------------------------------------------------ 1 原料参数
    w1 = wb.create_sheet('1_原料参数')
    title(w1, '① 原料参数（黄色 = 可修改的原始输入；灰色 = 公式）',
          '改这里，其余工作表自动重算。单耗统一换算为 t/t 产品；价格统一换算为 %s 元/吨。'
          % R['price_basis']['label'])
    cols = ['原料ID', '原料名称', 'CAS', '主/辅', '单耗(原值)', '单耗单位', '单耗(t/t)',
            '价格(原值)', '计价单位', '原口径', '价格(元/t目标口径)', '单项成本(元/t)',
            '成本占比', '规格', '地区', '交货方式', '价格日期', '单耗来源', '价格来源']
    header(w1, 3, cols, 34)
    widths(w1, [9, 24, 11, 6, 11, 9, 13, 12, 10, 8, 15, 14, 9, 26, 15, 14, 12, 14, 36])
    w1.freeze_panes = 'C4'
    r0 = 4
    rN = r0 + nrow - 1
    TOT = rN + 1
    tax_scale = 1.0
    tgt_in = R['price_basis']['target'] == 'tax_included'

    for i, m in enumerate(allm):
        r = r0 + i
        put(w1, r, 1, m['id'])
        put(w1, r, 2, m['name'], wrap=True)
        put(w1, r, 3, m.get('cas') or '—', align='center')
        put(w1, r, 4, '辅料' if m.get('role') == 'aux' else '主料', align='center')
        put(w1, r, 5, m.get('dosage_raw'), NUM4, FILL_INPUT)
        put(w1, r, 6, m.get('dosage_unit_in') or 't/t', fill=FILL_INPUT, align='center')
        kf = DOS_FACTOR.get((m.get('dosage_unit_in') or 't/t').replace(' ', ''), 1.0)
        put(w1, r, 7, '=IF(E%d="","",E%d*%s)' % (r, r, repr(kf)), NUM6, FILL_CALC, bold=True)
        put(w1, r, 8, m.get('price_raw'), NUM2, FILL_INPUT)
        put(w1, r, 9, m.get('price_unit_in') or 'CNY/t', fill=FILL_INPUT, align='center')
        put(w1, r, 10, m.get('price_tax_in') or '含税', fill=FILL_INPUT, align='center')
        pk = PRICE_FACTOR.get((m.get('price_unit_in') or 'CNY/t').replace(' ', ''))
        src_in = (m.get('price_tax_in') or '含税') == '含税'
        tf = 1.0
        if tgt_in != src_in:
            tf = 1.13 if tgt_in else 1 / 1.13
        if pk is None:      # USD 计价：汇率换算在引擎中完成，这里写引擎结果
            put(w1, r, 11, m.get('price'), NUM2, FILL_CALC, bold=True)
        else:
            put(w1, r, 11, '=IF(H%d="","",H%d*%s*%s)' % (r, r, repr(pk), repr(tf)), NUM2, FILL_CALC, bold=True)
        put(w1, r, 12, '=IF(OR($G%d="",$K%d=""),"",$G%d*$K%d)' % (r, r, r, r), NUM2, FILL_CALC, bold=True)
        put(w1, r, 13, '=IF($L%d="","",IF(SUM($L$%d:$L$%d)=0,"",$L%d/SUM($L$%d:$L$%d)))'
            % (r, r0, rN, r, r0, rN), PCT, FILL_CALC)
        put(w1, r, 14, m.get('price_spec') or m.get('spec') or '—', wrap=True)
        put(w1, r, 15, m.get('price_region') or m.get('region') or '—', wrap=True)
        put(w1, r, 16, m.get('price_delivery') or m.get('delivery') or '—', wrap=True)
        put(w1, r, 17, m.get('price_date') or '—', align='center', wrap=True)
        put(w1, r, 18, m.get('dosage_source_label') or '—', wrap=True)
        put(w1, r, 19, m.get('price_source') or '（无价格：缺口）', wrap=True)
        if m.get('price_raw') is None or m.get('price') is None:
            for c in (8, 11, 12, 13):
                w1.cell(row=r, column=c).fill = FILL_GAP
    put(w1, TOT, 2, '合计（仅计有价格的原料）', fill=FILL_SUB, bold=True)
    for c in (1, 3, 4, 5, 6, 8, 9, 10, 14, 15, 16, 17, 18, 19):
        put(w1, TOT, c, None, fill=FILL_SUB)
    put(w1, TOT, 7, '=SUM(G%d:G%d)' % (r0, rN), NUM6, FILL_SUB, bold=True)
    put(w1, TOT, 11, None, fill=FILL_SUB)
    put(w1, TOT, 12, '=SUM(L%d:L%d)' % (r0, rN), NUM2, FILL_SUB, bold=True)
    put(w1, TOT, 13, '=IF(L%d=0,"",SUM(M%d:M%d))' % (TOT, r0, rN), PCT, FILL_SUB, bold=True)
    note(w1, TOT + 2, '单位与税口径换算：单耗(t/t) = 原值 × 系数（kg/t→0.001，g/t→0.000001）；'
                      '价格(元/t) = 原值 × 计价换算（元/kg→1000）× 税口径系数（含税→不含税 ÷1.13，反之 ×1.13）。'
                      '公式写在单元格里，可直接点开查看。', span=10)
    note(w1, TOT + 3, '税率 13% 为增值税一般税率默认值，须由企业按自身纳税身份核定；'
                      '若为小规模纳税人或享受优惠，请把本表 X 列（见「8_公式与口径」）改成本企业实际值。', span=10)

    ROW = {m['id']: r0 + i for i, m in enumerate(allm)}

    # ------------------------------------------------------------ 2 成本构成
    w2 = wb.create_sheet('2_成本构成')
    title(w2, '② 单位产品理论原料成本与构成',
          '公式：C = Σ(q_i × p_i)；占比 = c_i / C。全部引用「1_原料参数」。')
    header(w2, 3, ['原料', '单耗(t/t)', '价格(元/t)', '单项成本(元/t)', '成本占比', '累计占比', '排名'])
    widths(w2, [30, 13, 15, 17, 11, 11, 8])
    rr = 4
    for m in comp:
        k = ROW[m['id']]
        put(w2, rr, 1, "='1_原料参数'!B%d" % k)
        put(w2, rr, 2, "='1_原料参数'!G%d" % k, NUM4)
        put(w2, rr, 3, "='1_原料参数'!K%d" % k, NUM2)
        put(w2, rr, 4, "='1_原料参数'!L%d" % k, NUM2, bold=True)
        put(w2, rr, 5, '=IF($D$%d=0,"",D%d/$D$%d)' % (4 + len(comp), rr, 4 + len(comp)), PCT)
        put(w2, rr, 6, '=E%d' % rr if rr == 4 else '=F%d+E%d' % (rr - 1, rr), PCT)
        put(w2, rr, 7, rr - 3, NUM0)
        rr += 1
    t2 = 4 + len(comp)
    put(w2, t2, 1, '理论原料成本合计', fill=FILL_SUB, bold=True)
    put(w2, t2, 2, '=SUM(B4:B%d)' % (t2 - 1), NUM4, FILL_SUB, bold=True)
    put(w2, t2, 3, None, fill=FILL_SUB)
    put(w2, t2, 4, '=SUM(D4:D%d)' % (t2 - 1), NUM2, FILL_SUB, bold=True)
    put(w2, t2, 5, '=SUM(E4:E%d)' % (t2 - 1), PCT, FILL_SUB, bold=True)
    put(w2, t2, 6, None, fill=FILL_SUB)
    put(w2, t2, 7, None, fill=FILL_SUB)
    r = t2 + 2
    for label, fn in [('主料合计', 'SUMIF(\'1_原料参数\'!$D$%d:$D$%d,"主料",\'1_原料参数\'!$L$%d:$L$%d)'),
                      ('辅料合计', 'SUMIF(\'1_原料参数\'!$D$%d:$D$%d,"辅料",\'1_原料参数\'!$L$%d:$L$%d)')]:
        put(w2, r, 1, label, fill=FILL_SUB, bold=True)
        put(w2, r, 4, '=' + fn % (r0, rN, r0, rN), NUM2)
        r += 1
    put(w2, r, 1, '已计价原料条数', fill=FILL_SUB, bold=True)
    put(w2, r, 4, '=COUNT(\'1_原料参数\'!$L$%d:$L$%d)&" / %d 条"' % (r0, rN, nrow), align='center')
    put(w2, r + 1, 1, '未计价（缺口）原料', fill=FILL_SUB, bold=True)
    gapnames = [m['name'] for m in allm if m.get('cost') is None]
    put(w2, r + 1, 4, '、'.join(gapnames) if gapnames else '无，成本覆盖完整', align='left', wrap=True)
    w2.merge_cells(start_row=r + 1, start_column=4, end_row=r + 1, end_column=7)

    pie = PieChart()
    pie.title = '成本占比'
    pie.height, pie.width = 8.5, 12
    data_ = Reference(w2, min_col=4, min_row=3, max_row=t2 - 1)
    cats = Reference(w2, min_col=1, min_row=4, max_row=t2 - 1)
    pie.add_data(data_, titles_from_data=True)
    pie.set_categories(cats)
    pie.dataLabels = DataLabelList()
    pie.dataLabels.showPercent = True
    w2.add_chart(pie, 'I3')
    bar = BarChart()
    bar.type = 'bar'
    bar.title = '单项成本金额（元/吨产品）'
    bar.height, bar.width = 8.5, 12
    bar.add_data(data_, titles_from_data=True)
    bar.set_categories(cats)
    bar.legend = None
    w2.add_chart(bar, 'I22')

    # ------------------------------------------------------------ 3 敏感性矩阵
    w3 = wb.create_sheet('3_敏感性矩阵')
    title(w3, '③ 价格敏感性矩阵与组合情景',
          'Δc_i = q_i × p_i × r_i；组合 ΔC = ΣΔc_i。第 5 行涨跌幅（%）为输入，其余为公式。')
    put(w3, 4, 1, '涨跌幅档位（与热力图 D 列起一一对齐）', fill=FILL_SUB, bold=True)
    RATE_ROW = 5
    for j, s in enumerate(rates):
        put(w3, 4, 4 + j, s['label'], fill=FILL_SUB, bold=True, align='center')
        put(w3, RATE_ROW, 4 + j, round(s['ratio'], 6), PCT_LBL_SIGNED, FILL_INPUT, align='center')
    put(w3, 4, 4 + nr, '单耗+1% 影响(元/吨)', fill=FILL_SUB, bold=True, align='center')
    put(w3, RATE_ROW, 4 + nr, None, fill=FILL_SUB)
    widths(w3, [26, 11, 14, 14, 16, 16, 12] + [2] * max(0, nr - 5) + [34])
    note(w3, 6, '第 5 行可改（例如改成 3、7、15），下方热力图与合计自动跟随。', span=6)

    hr = 8
    h2(w3, hr - 1, 'A. 敏感性热力图：单位成本变化（元/吨产品）')
    header(w3, hr, ['原料', '单耗(t/t)', '价格(元/t)'] + [x['label'] for x in rates])
    h0 = hr + 1
    for i, s in enumerate(R['sensitivity']):
        k = ROW[s['material_id']]
        r = h0 + i
        put(w3, r, 1, "='1_原料参数'!B%d" % k)
        put(w3, r, 2, "='1_原料参数'!G%d" % k, NUM4)
        put(w3, r, 3, "='1_原料参数'!K%d" % k, NUM2)
        for j in range(nr):
            cc = get_column_letter(4 + j)
            put(w3, r, 4 + j, '=$B%d*$C%d*%s$%d' % (r, r, cc, RATE_ROW), NUM2)
    hl = h0 + len(R['sensitivity']) - 1
    HEAT_FIRST = h0
    lastc = 4 + nr - 1
    w3.conditional_formatting.add(
        'D%d:%s%d' % (h0, get_column_letter(lastc), hl),
        ColorScaleRule(start_type='min', start_color='63BE7B',
                       mid_type='num', mid_value=0, mid_color='FFFFFF',
                       end_type='max', end_color='F8696B'))
    tr = hl + 1
    put(w3, tr, 1, '合计/全部原料同步', fill=FILL_SUB, bold=True)
    put(w3, tr, 2, '=SUM(B%d:B%d)' % (h0, hl), NUM4, FILL_SUB)
    put(w3, tr, 3, None, fill=FILL_SUB)
    for j in range(nr):
        col = get_column_letter(4 + j)
        put(w3, tr, 4 + j, '=SUM(%s%d:%s%d)' % (col, h0, col, hl), NUM2, FILL_SUB, bold=True)

    # B. 单原料逐档明细（新成本 / Δ%）
    br = tr + 3
    h2(w3, br - 1, 'B. 单原料逐档明细：变动后每吨原料成本（元/吨）与相对变化（%）')
    header(w3, br, ['原料'] + ['%s 后成本' % x['label'] for x in rates] + ['%s Δ%%' % x['label'] for x in rates])
    for i, s in enumerate(R['sensitivity']):
        k = ROW[s['material_id']]
        r = br + 1 + i
        hr_ = h0 + i
        put(w3, r, 1, "='1_原料参数'!B%d" % k)
        for j in range(nr):
            put(w3, r, 2 + j, '=$D$%d*$C$%d+%s%d' % (t2, hr_, get_column_letter(4 + j), hr_), NUM2)
        for j in range(nr):
            put(w3, r, 2 + nr + j, '=IF($D$%d=0,"",%s%d/$D$%d)' % (t2, get_column_letter(4 + j), hr_, t2), PCT)
    # 合并"合计"行在 D 列（与 A 小节对齐）
    w3.cell(row=br - 1, column=1).value = 'B. 单原料逐档明细（基于「2_成本构成」合计 D%d）' % t2

    # C. 组合情景
    cr = br + len(R['sensitivity']) + 3
    h2(w3, cr - 1, 'C. 组合情景：多原料同时变动后每吨理论原料成本')
    nm = len(comp)
    chead = ['情景'] + ['%s %%' % m['name'][:8] for m in comp] + ['基准成本', '情景成本', 'Δ成本', 'Δ%']
    header(w3, cr, chead)
    cas = cr + 1
    cs = 2
    for i, c in enumerate(R['combos']):
        r = cas + i
        put(w3, r, 1, c['name'], wrap=True)
        for j, m in enumerate(comp):
            put(w3, r, cs + j, c['changes'].get(m['id'], 0), PCTLBL, FILL_INPUT, align='center')
        base_c = cs + nm
        put(w3, r, base_c, "='2_成本构成'!$D$%d" % t2, NUM2)
        first_rng = '%s%d:%s%d' % (get_column_letter(cs), r, get_column_letter(cs + nm - 1), r)
        q_rng = '\'1_原料参数\'!$G$%d:$G$%d' % (r0, rN)
        p_rng = '\'1_原料参数\'!$K$%d:$K$%d' % (r0, rN)
        # 组合成本按「有价格的原料」对应行装配，保证与 1_原料参数 行对齐
        if nm == len(allm):
            put(w3, r, base_c + 1, '=SUMPRODUCT(%s,%s,1+%s/100)' % (q_rng, p_rng, first_rng), NUM2, bold=True)
        else:
            # 原料顺序在 1_原料参数 中与 comp 不同：逐项相加，避免行错位
            terms = []
            for j, m in enumerate(comp):
                k = ROW[m['id']]
                terms.append("'1_原料参数'!$G$%d*'1_原料参数'!$K$%d*(1+%s%d/100)" % (k, k, get_column_letter(cs + j), r))
            put(w3, r, base_c + 1, '=' + '+'.join(terms), NUM2, bold=True)
        put(w3, r, base_c + 2, '=%s%d-%s%d' % (get_column_letter(base_c + 1), r, get_column_letter(base_c), r), NUM2)
        put(w3, r, base_c + 3, '=IF(%s%d=0,"",%s%d/%s%d)' % (get_column_letter(base_c), r,
                                                             get_column_letter(base_c + 2), r,
                                                             get_column_letter(base_c), r), PCT)
    note(w3, cas + len(R['combos']) + 1,
         '情景成本 = Σ 单耗_i × 价格_i × (1 + 涨跌幅_i/100)。缺价原料不进入求和——若某原料缺价，'
         '情景结果与该缺口同口径（页面已在"缺口"清单中标注）。', span=8)

    # ------------------------------------------------------------ 4 组合情景明细
    w4 = wb.create_sheet('4_组合情景明细')
    title(w4, '④ 组合情景逐原料贡献', '每情景下各原料成本变化与对总成本的贡献。')
    widths(w4, [30, 12, 14, 14, 14, 14])
    r = 3
    for c in R['combos']:
        put(w4, r, 1, c['name'], fill=FILL_SUB, bold=True)
        w4.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        r += 1
        header(w4, r, ['原料', '变动幅度', '原成本', '新成本', 'Δ成本', 'Δ占总成本'])
        r += 1
        first = r
        for b in c['by_material']:
            k = ROW[b['material_id']]
            put(w4, r, 1, "='1_原料参数'!B%d" % k)
            put(w4, r, 2, b['ratio_pct'], PCTLBL, FILL_INPUT, align='center')
            put(w4, r, 3, "='1_原料参数'!L%d" % k, NUM2)
            put(w4, r, 4, '=IF(C%d="","",C%d*(1+B%d/100))' % (r, r, r), NUM2)
            put(w4, r, 5, '=IF(D%d="","",D%d-C%d)' % (r, r, r), NUM2)
            put(w4, r, 6, '=IF($E%d="",0,0)' % r, PCT)     # 占位，下面统一改
            w4.cell(row=r, column=6).value = '=IF(\'2_成本构成\'!$D$%d=0,"",E%d/\'2_成本构成\'!$D$%d)' % (t2, r, t2)
            put(w4, r, 6, w4.cell(row=r, column=6).value, PCT)
            r += 1
        put(w4, r, 1, '合计', fill=FILL_SUB, bold=True)
        put(w4, r, 2, None, fill=FILL_SUB)
        put(w4, r, 3, '=SUM(C%d:C%d)' % (first, r - 1), NUM2, FILL_SUB, bold=True)
        put(w4, r, 4, '=SUM(D%d:D%d)' % (first, r - 1), NUM2, FILL_SUB, bold=True)
        put(w4, r, 5, '=SUM(E%d:E%d)' % (first, r - 1), NUM2, FILL_SUB, bold=True)
        put(w4, r, 6, '=IF(\'2_成本构成\'!$D$%d=0,"",E%d/\'2_成本构成\'!$D$%d)' % (t2, r, t2), PCT, FILL_SUB, bold=True)
        r += 2

    # ------------------------------------------------------------ 5 历史理论成本
    w5 = wb.create_sheet('5_历史理论成本')
    hist = R['history']
    hrows = hist['rows']
    hmats = hist['coverage']['series']
    hids = [h['material_id'] for h in hmats]
    title(w5, '⑤ 历史价格原始数据与历史理论原料成本',
          '价格列 = 真实序列；成本列 = 公式（固定单耗 × 当日价格）。价格留空 → 成本留空（缺口，不插值）。')
    cols5 = ['日期'] + ['%s 价格(元/t)' % h['name'] for h in hmats] + \
            ['%s 成本' % c['name'] for c in comp] + ['历史理论原料成本(元/t)']
    header(w5, 3, cols5)
    widths(w5, [12] + [15] * len(hmats) + [14] * len(comp) + [22])
    w5.freeze_panes = 'B4'
    r = 4
    for row in hrows:
        put(w5, r, 1, row['date'], align='center')
        for j, h in enumerate(hmats):
            put(w5, r, 2 + j, row['items'].get(h['material_id']) is not None and _lookup(data, h['material_id'], row['date']) or _lookup(data, h['material_id'], row['date']), NUM2)
        base = 2 + len(hmats)
        for j, m in enumerate(comp):
            if m['id'] in hids:
                hcol = get_column_letter(2 + hids.index(m['id']))
                put(w5, r, base + j,
                    '=IF(%s%d="","",\'1_原料参数\'!$G$%d*%s%d)' % (hcol, r, ROW[m['id']], hcol, r), NUM2)
            else:
                put(w5, r, base + j, '无序列', fill=FILL_GAP, align='center')
        lc = base + len(comp)
        if comp:
            cond = ','.join('%s%d=""' % (get_column_letter(base + j), r) for j in range(len(comp)))
            put(w5, r, lc, '=IF(OR(%s),"",SUM(%s%d:%s%d))' % (cond, get_column_letter(base), r,
                                                              get_column_letter(lc - 1), r), NUM2, bold=True)
        r += 1
    hlast = r - 1
    r += 2
    h2(w5, r - 1, '历史变化统计（按日历回溯；起点早于数据起点 → 缺口，不插值）')
    header(w5, r, ['窗口', '起点日', '起点成本', '终点日', '终点成本', 'Δ成本', 'Δ%'])
    for p in R['periods']:
        r += 1
        put(w5, r, 1, p['label'])
        put(w5, r, 2, p.get('start_date') or '—', align='center')
        put(w5, r, 3, p.get('start'), NUM2)
        put(w5, r, 4, p.get('end_date') or '—', align='center')
        put(w5, r, 5, '=%s%d' % (get_column_letter(lc), hlast), NUM2)
        if p['status'] == 'ok':
            put(w5, r, 6, '=E%d-C%d' % (r, r), NUM2)
            put(w5, r, 7, '=IF(C%d=0,"",F%d/C%d)' % (r, r, r), PCT)
        else:
            put(w5, r, 6, '缺口，未插值', fill=FILL_GAP, align='center')
            put(w5, r, 7, '—', fill=FILL_GAP, align='center')
    # 图表
    ch = LineChart()
    ch.title = '历史理论原料成本（元/吨产品）'
    ch.height, ch.width = 9, 24
    ch.y_axis.title = '元/吨'
    ch.add_data(Reference(w5, min_col=lc, min_row=3, max_row=hlast), titles_from_data=True)
    ch.set_categories(Reference(w5, min_col=1, min_row=4, max_row=hlast))
    skip = max(1, len(hrows) // 14)
    ch.x_axis.tickLblSkip = skip
    ch.x_axis.tickMarkSkip = skip
    w5.add_chart(ch, 'B%d' % (r + 3))
    if comp:
        ch2 = LineChart()
        ch2.title = '各原料成本贡献（堆叠）'
        ch2.height, ch2.width = 9, 24
        ch2.add_data(Reference(w5, min_col=2 + len(hmats), max_col=lc - 1, min_row=3, max_row=hlast),
                     titles_from_data=True)
        ch2.set_categories(Reference(w5, min_col=1, min_row=4, max_row=hlast))
        ch2.grouping = 'stacked'
        ch2.overlap = 100
        ch2.x_axis.tickLblSkip = skip
        ch2.x_axis.tickMarkSkip = skip
        w5.add_chart(ch2, 'B%d' % (r + 25))

    # ------------------------------------------------------------ 6 贡献分解
    w6 = wb.create_sheet('6_贡献分解')
    title(w6, '⑥ 各原料对历史成本变化的贡献',
          'Δc_i = q_i×(p_i,T − p_i,0)；贡献比 = Δc_i / ΔC_T（ΔC_T≈0 时留空）。')
    widths(w6, [30, 15, 15, 15, 14])
    r = 3
    for c in R['contribution']:
        put(w6, r, 1, '窗口 %s：%s → %s' % (c['period'], c.get('start_date', '—'), c.get('end_date', '—')),
            fill=FILL_SUB, bold=True)
        w6.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        r += 1
        if c['status'] != 'ok':
            put(w6, r, 1, '缺口：%s' % c.get('why', ''), fill=FILL_GAP, wrap=True)
            w6.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
            r += 2
            continue
        header(w6, r, ['原料', '起点成本', '终点成本', 'Δ成本', '占总变化比'])
        r += 1
        first = r
        for it in c['items']:
            put(w6, r, 1, it['name'])
            put(w6, r, 2, it['start'], NUM2)
            put(w6, r, 3, it['end'], NUM2)
            put(w6, r, 4, '=C%d-B%d' % (r, r), NUM2)
            put(w6, r, 5, '=IF(ABS($D$%d)<0.000001,"",D%d/$D$%d)' % (first + len(c['items']), r,
                                                                     first + len(c['items'])), PCT)
            r += 1
        put(w6, r, 1, '合计', fill=FILL_SUB, bold=True)
        put(w6, r, 2, '=SUM(B%d:B%d)' % (first, r - 1), NUM2, FILL_SUB, bold=True)
        put(w6, r, 3, '=SUM(C%d:C%d)' % (first, r - 1), NUM2, FILL_SUB, bold=True)
        put(w6, r, 4, '=SUM(D%d:D%d)' % (first, r - 1), NUM2, FILL_SUB, bold=True)
        put(w6, r, 5, '=IF(ABS(D%d)<0.000001,"",SUM(E%d:E%d))' % (r, first, r - 1), PCT, FILL_SUB, bold=True)
        r += 2

    # ------------------------------------------------------------ 7 数据来源
    w7 = wb.create_sheet('7_数据来源')
    title(w7, '⑦ 数据来源清单（单耗 / 价格 / 标准）')
    header(w7, 3, ['来源ID', '类型', '标题', 'URL', '用于哪些参数'])
    widths(w7, [16, 26, 54, 50, 46])
    r = 4
    for s in data.get('data_sources') or []:
        put(w7, r, 1, s.get('id'))
        put(w7, r, 2, s.get('type'), wrap=True)
        put(w7, r, 3, s.get('title'), wrap=True)
        put(w7, r, 4, s.get('url'), wrap=True)
        put(w7, r, 5, s.get('used_for'), wrap=True)
        r += 1

    # ------------------------------------------------------------ 8 公式与口径
    w8 = wb.create_sheet('8_公式与口径')
    title(w8, '⑧ 计算公式、单位换算与口径约定')
    header(w8, 3, ['项目', '公式 / 规则', '说明 / 本例取值'])
    widths(w8, [28, 60, 54])
    r = 4
    for f in data.get('formula_doc') or []:
        put(w8, r, 1, f.get('name'), wrap=True)
        put(w8, r, 2, f.get('f'), wrap=True)
        put(w8, r, 3, f.get('v'), wrap=True)
        r += 1
    r += 1
    for k, v in [('单位换算', '1 t = 1000 kg；1 kg/t 产品 = 0.001 t/t 产品；涨跌幅列按"%"填写，公式内部 ÷100'),
                 ('税口径', '含税→不含税 ÷(1+税率)；不含税→含税 ×(1+税率)。税率由「1_原料参数」X 列语义约定，默认 13%，须企业核定'),
                 ('单耗口径', R['params']['basis_label'] + '。' + (R['params']['notes'] or '')),
                 ('成品收率', '收率 %s / 转化率 %s / 过量醇回收率 %s' % (
                     _pv(R['params'].get('yield_pct')), _pv(R['params'].get('conversion_pct')),
                     _pv(R['params'].get('recycle_pct'))))]:
        put(w8, r, 1, k, fill=FILL_SUB, bold=True, wrap=True)
        put(w8, r, 2, v, wrap=True)
        w8.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        r += 1

    # ------------------------------------------------------------ 9 缺口
    w9 = wb.create_sheet('9_缺口与待补')
    title(w9, '⑨ 缺口、未量化项与待补数据', '缺什么、影响什么、怎么补。没有可靠数据的一律留空，不估算、不插值。')
    header(w9, 3, ['类型', '项目', '说明', '影响', '补齐路径'])
    widths(w9, [14, 28, 50, 42, 44])
    r = 4
    tn = {'price': '价格缺口', 'dosage': '单耗来源', 'history': '历史序列',
          'history_window': '历史窗口', 'data': '数据缺口'}
    for g in R['gaps']:
        put(w9, r, 1, tn.get(g['type'], g['type']), wrap=True)
        put(w9, r, 2, g['item'], wrap=True)
        put(w9, r, 3, g['detail'], wrap=True)
        put(w9, r, 4, g.get('impact', ''), wrap=True)
        put(w9, r, 5, g.get('fix', ''), wrap=True)
        r += 1
    if not R['gaps']:
        put(w9, r, 3, '无缺口')

    # ------------------------------------------------------------ 10 与产品价并列
    w10 = wb.create_sheet('10_与产品价并列')
    title(w10, '⑩ 理论原料成本 vs 产品现货价（加工价差 ≠ 利润）',
          '价差 = 产品价 − 理论原料成本，仅表示"原料之外还剩多少空间"，未扣能源/人工/折旧/运费，不是利润。')
    refs = (data.get('history') or {}).get('reference_series') or []
    if refs:
        header(w10, 3, ['日期', '产品价(元/t)', '理论原料成本(元/t)', '价差(元/t)', '价差率'])
        widths(w10, [12, 16, 20, 16, 12])
        pmap = {x['date']: x['value'] for x in refs[0]['rows']}
        r = 4
        for row in hrows:
            put(w10, r, 1, row['date'], align='center')
            put(w10, r, 2, pmap.get(row['date']), NUM2)
            put(w10, r, 3, '=\'5_历史理论成本\'!%s%d' % (get_column_letter(lc), 4 + (r - 4)), NUM2)
            put(w10, r, 4, '=IF(OR(B%d="",C%d=""),"",B%d-C%d)' % (r, r, r, r), NUM2)
            put(w10, r, 5, '=IF(OR(B%d="",C%d="",B%d=0),"",D%d/B%d)' % (r, r, r, r, r), PCT)
            r += 1
        note(w10, r + 1, '产品价来源：%s（%s，%s）' % (refs[0].get('source'), refs[0].get('spec'), refs[0].get('region')))
        note(w10, r + 2, refs[0].get('note', ''))
    else:
        put(w10, 3, 1, '未提供产品价格序列：本表留空（未用估算值代替）')

    wb.properties.title = '%s 理论原料成本模型' % R['meta'].get('product')
    wb.properties.subject = '理论原料成本 / 敏感性 / 历史成本 / 缺口'
    wb.properties.creator = 'chem-cost-model skill'
    wb.properties.description = '理论原料成本 ≠ 完整生产成本 ≠ 利润；不预测价格。'
    wb.save(path)
    return path


def _pv(v):
    return '—' if v is None else '%s%%' % v


def _lookup(data, mid, date):
    for h in (data.get('history') or {}).get('materials') or []:
        if h.get('material_id') == mid:
            for r in h.get('rows') or []:
                if (r.get('date') or '')[:10] == date:
                    return r.get('value')
    return None
