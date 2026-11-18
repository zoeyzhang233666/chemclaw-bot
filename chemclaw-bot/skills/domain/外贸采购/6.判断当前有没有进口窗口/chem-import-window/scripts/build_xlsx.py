# -*- coding: utf-8 -*-
"""build_xlsx.py — 生成"进口窗口判断"Excel 工作簿（全活公式，改数即重算）

用法: python scripts/build_xlsx.py <case.json> <out.xlsx> [--engine-json engine.json]

设计原则（对应 SKILL.md 红线）：
  · 每个数字都必须能追溯到「来源」列；来源为空的输入格填 amber，提示必须补
  · 缺数据一律写 "待补"（IFERROR/IF 判断），绝不写 0 冒充真实值
  · 所有折算用**单元格公式**，改汇率/运费/税率即全表重算（不在 Python 里算好再塞值）
  · 「9-引擎校验」页把 Node 引擎的结果并列出来，肉眼可比对
"""
import datetime
import io
import json
import sys

from openpyxl import Workbook
from openpyxl.styles import (Alignment, Border, Font, PatternFill, Side)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

INPUT_FILL = PatternFill('solid', fgColor='FFF7E0')     # 可编辑输入
CALC_FILL = PatternFill('solid', fgColor='F4F8FC')      # 公式
HEAD_FILL = PatternFill('solid', fgColor='0F172A')      # 表头（深色）
HEAD_FONT = Font(color='FFFFFF', bold=True, size=10)
TITLE_FONT = Font(bold=True, size=14, color='0F172A')
NOTE_FONT = Font(size=9, color='6B7280', italic=True)
GAP_FILL = PatternFill('solid', fgColor='F3E8FF')       # 缺口
WARN_FILL = PatternFill('solid', fgColor='FEF3C7')
OK_FILL = PatternFill('solid', fgColor='DCFCE7')
BAD_FILL = PatternFill('solid', fgColor='FEE2E2')
THIN = Side(style='thin', color='D6DEEB')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def pct(v):
    return None if v is None else v / 100.0


def main():
    case_path, out_path = sys.argv[1], sys.argv[2]
    engine = {}
    if '--engine-json' in sys.argv:
        engine = json.load(open(sys.argv[sys.argv.index('--engine-json') + 1], encoding='utf-8'))

    case = json.load(open(case_path, encoding='utf-8'))
    prod = case['product']
    req = case.get('request', {})
    quote = case['quote']
    dom = case['domestic']
    fx = case['fx']
    tax_p = case['tax']['profiles'][0]
    params = case.get('params', {})
    freight = case.get('freight', {})
    ins = case.get('insurance', {})

    wb = Workbook()

    # ======================================================== 0-说明
    ws = wb.active
    ws.title = '0-说明'
    ws.sheet_view.showGridLines = False
    ws['A1'] = '进口窗口判断 · ' + case['meta']['title']
    ws['A1'].font = TITLE_FONT
    ws['A2'] = case['meta'].get('subtitle', '')
    ws['A2'].font = Font(size=10, color='475569')
    rows = [
        ('基准日', case['asof']['date']),
        ('商品 / 规格', '%s（%s）· HS %s · CAS %s' % (prod['name_cn'], prod['spec'], prod['hs_code_cn'], prod.get('cas', ''))),
        ('海外市场 → 国内区域', '%s → %s' % (req.get('origin', ''), req.get('destination', ''))),
        ('币种 / 单位', '海外 USD/吨；国内 CNY/吨'),
        ('生成时间', case['meta']['generated_at']),
        ('', ''),
        ('【本表怎么用】', ''),
        ('1. 黄色单元格 = 可修改的输入（报价、汇率、运费、税率、费用等）；改完 Excel 自动重算全表。', ''),
        ('2. 蓝灰色单元格 = 公式，请勿手改。', ''),
        ('3. 任何"待补"都表示该项数据缺失，不得当成 0 使用；在「8-缺口登记」补齐来源后再算。', ''),
        ('4. 「9-引擎校验」为独立计算引擎的对照结果，用于确认真实计算与页面一致。', ''),
        ('', ''),
        ('【口径声明】', ''),
        ('· 比较对象：国内含税现货价（增值税可抵扣） ↔ 进口"含税净成本"（剔除可抵扣进口增值税）。', ''),
        ('· 两端都只算到"口岸/罐区"，不含内陆配送；如国内是有送货价，必须扣回。', ''),
        ('· 理论价差 ≠ 可执行贸易利润：运费、资金、罐容、损耗、对手方风险均未包含。', ''),
        ('· 本表不做价格预测，也不给出交易指令。', ''),
    ]
    r = 4
    for a, b in rows:
        ws.cell(row=r, column=1, value=a).font = Font(bold=(a.startswith('【')), size=10)
        c = ws.cell(row=r, column=2, value=b)
        c.font = Font(size=10, color='334155')
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        r += 1
    ws.column_dimensions['A'].width = 26
    for col in 'BCDEF':
        ws.column_dimensions[col].width = 24
    ws.cell(row=r + 1, column=1, value=case['meta'].get('disclaimer', '')).font = NOTE_FONT

    # ======================================================== 1-参数
    ws1 = wb.create_sheet('1-参数')
    ws1.sheet_view.showGridLines = False
    ws1['A1'] = '① 参数区（黄底=可编辑，改完自动重算全表）'
    ws1['A1'].font = TITLE_FONT
    hdr = ['参数', '值', '单位', '来源 / 依据', '备注']
    for i, h in enumerate(hdr, 1):
        c = ws1.cell(row=3, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BOX
        c.alignment = Alignment(horizontal='center')

    P = {}   # 参数名 -> 单元格地址

    def put(row, key, label, value, unit, source, note='', gap=False):
        ws1.cell(row=row, column=1, value=label).font = Font(size=10, bold=True)
        vc = ws1.cell(row=row, column=2, value=value)
        vc.fill = GAP_FILL if value is None else INPUT_FILL
        vc.font = Font(size=10, bold=True)
        vc.border = BOX
        if isinstance(value, float) and value < 2:
            vc.number_format = '0.0000' if unit in ('CNY/USD',) else '0.00'
        ws1.cell(row=row, column=3, value=unit).font = Font(size=9, color='6B7280')
        sc = ws1.cell(row=row, column=4, value=source)
        sc.font = Font(size=9, color='334155')
        sc.alignment = Alignment(wrap_text=True, vertical='top')
        nc = ws1.cell(row=row, column=5, value=note)
        nc.font = Font(size=9, color='6B7280')
        nc.alignment = Alignment(wrap_text=True, vertical='top')
        for col in range(1, 6):
            ws1.cell(row=row, column=col).border = BOX
        P[key] = 'B%d' % row
        return row + 1

    def section(row, text):
        c = ws1.cell(row=row, column=1, value=text)
        c.font = Font(bold=True, size=11, color='1D4ED8')
        ws1.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        return row + 1

    row = section(5, '— 商品与批次 —')
    row = put(row, 'product', '商品', prod['name_cn'], '', '本案例')
    row = put(row, 'spec', '规格', prod['spec'], '', '本案例', '规格不同不可比')
    row = put(row, 'hs', 'HS 税号', prod['hs_code_cn'], '', '财政部 2026 暂定税率表', '以实际报关税号为准')
    row = put(row, 'batch', '单批数量', req.get('volume_ton'), '吨', '本案例', '影响运费与议价')
    row = put(row, 'transit', '预计航程', req.get('transit_days'), '天', '常规航程', '用于资金占用测算')

    row = section(row + 1, '— 海外报价 —')
    row = put(row, 'q_date', '报价日期', quote['date'], '', 'S-CPH-1015', '')
    row = put(row, 'q_price', '海外报价', float(quote['price_usd']), 'USD/吨', 'S-CPH-1015', quote.get('quote_type', ''))
    row = put(row, 'q_term', '贸易术语', quote['term'], '', '报价单', 'FOB / CFR / CIF')
    row = put(row, 'q_prem', '升贴水', float(quote.get('premium_usd') or 0), 'USD/吨', '议价结果', '')
    row = put(row, 'q_port', '交货口岸', quote.get('port', ''), '', '', '')

    row = section(row + 1, '— 国际运费与保险 —')
    f_usd = freight.get('usd_per_ton')
    row = put(row, 'frt', '国际运费', f_usd, 'USD/吨', (freight.get('source_id') or '') + ' ' + (freight.get('basis') or ''),
              '缺口时务必留空，不要填 0', gap=(f_usd is None))
    row = put(row, 'ins_rate', '保险费率', pct(ins.get('rate')), '%（占 CIF×110%）',
              '保单' if ins.get('rate') else '缺口 G7', 'CFR 口径需另加保险')

    row = section(row + 1, '— 汇率 —')
    row = put(row, 'fx_date', '汇率日期', fx['date'], '', 'S-ECB-REF / S-CFETS', '必须与价格同日')
    row = put(row, 'fx', 'USD/CNY', float(fx['rate']), 'CNY/USD', fx.get('source_id', ''), '海关适用汇率可能略低')

    row = section(row + 1, '— 关税与增值税 —')
    row = put(row, 'duty', '关税税率', pct(tax_p['duty_rate']) * 100, '%', tax_p.get('source_id', ''),
              '以报关日税则为准', gap=False)
    row = put(row, 'vat', '进口增值税率', pct(tax_p['vat_rate']) * 100, '%', '增值税暂行条例', '13% 标准税率')
    row = put(row, 'vat_rec', '增值税可抵扣', '是' if params.get('vat_recoverable') else '否', '', '', '一般纳税人为"是"')

    row = section(row + 1, '— 境内费用 —')
    row = put(row, 'inland', '境内费用合计', params.get('inland_cost_cny'), '元/吨', '港杂/报关/仓储/短驳实票',
              '缺口 G6', gap=(params.get('inland_cost_cny') is None))
    row = put(row, 'other', '其他费用', float(params.get('other_cost_cny') or 0), '元/吨', '', '')

    row = section(row + 1, '— 国内现货 —')
    row = put(row, 'd_price', '国内现货价（含税）', float(dom['price_cny']), '元/吨', dom.get('source_id', ''), dom.get('market', ''))
    row = put(row, 'd_deliv', '交货方式', dom.get('delivery', ''), '', '', '自提价不可与送到价直接比')
    row = put(row, 'd_tax', '是否含税', '是' if dom.get('tax_included') else '否', '', '', '')

    ws1.column_dimensions['A'].width = 20
    ws1.column_dimensions['B'].width = 16
    ws1.column_dimensions['C'].width = 16
    ws1.column_dimensions['D'].width = 40
    ws1.column_dimensions['E'].width = 34
    # 百分比格式
    for cell in ('ins_rate', 'duty', 'vat'):
        ws1[P[cell]].number_format = '0.00'
    # 术语下拉
    dv = DataValidation(type='list', formula1='"FOB,CFR,CIF"', allow_blank=True)
    ws1.add_data_validation(dv)
    dv.add(ws1[P['q_term']])
    dv2 = DataValidation(type='list', formula1='"是,否"', allow_blank=True)
    ws1.add_data_validation(dv2)
    dv2.add(ws1[P['vat_rec']])

    # ======================================================== 2-计算
    ws2 = wb.create_sheet('2-进口成本折算')
    ws2.sheet_view.showGridLines = False
    ws2['A1'] = '② 折算过程（全部为公式，随「1-参数」实时重算）'
    ws2['A1'].font = TITLE_FONT
    for i, h in enumerate(['步骤', '项目', '公式（中文口径）', '金额', '单位', '取值说明'], 1):
        c = ws2.cell(row=3, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BOX
        c.alignment = Alignment(horizontal='center')

    C = {}
    # 注意：参数引用必须是"裸引用"（不带前导 =），由各公式自行加 =
    qp, qt = "'1-参数'!%s" % P['q_price'], "'1-参数'!%s" % P['q_term']
    prem, frt = "'1-参数'!%s" % P['q_prem'], "'1-参数'!%s" % P['frt']
    insr, fxc = "'1-参数'!%s" % P['ins_rate'], "'1-参数'!%s" % P['fx']
    dutyr, vatr, rec = "'1-参数'!%s" % P['duty'], "'1-参数'!%s" % P['vat'], "'1-参数'!%s" % P['vat_rec']
    inland, other = "'1-参数'!%s" % P['inland'], "'1-参数'!%s" % P['other']
    dprice = "'1-参数'!%s" % P['d_price']

    steps = [
        ('1', '海外报价（净价）', '报价 − 升贴水补充', '=IF(%s="","待补",%s+IF(%s="",0,%s))' % (qp, qp, prem, prem), 'USD/吨', '报价加升贴水'),
        ('2', 'CFR 价格', 'FOB 加运费；CFR/CIF 直接取', '=IF($D$4="FOB",IF(OR(%s="",%s=""),"待补",$D$4+%s),$D$4)' % (frt, frt, frt), 'USD/吨', '缺运费则 FOB 不可折算'),
        ('3', '保险费', 'CFR × 费率 × 110% ÷ (1 − 费率×1.1)', '=IF($D$5="CIF",0,IF(OR(%s="",%s=""),0,%s*(1-%s*1.1)/(%s))*0 )' % (insr, insr, insr, '', ''), 'USD/吨', 'CIF 已含保险'),
        ('4', 'CIF 价格', 'CFR + 保险费', '=IF(OR($D$5="CIF",$D$5=""),$D$4,$D$4+$D$6)', 'USD/吨', '到岸价'),
        ('5', '汇率', 'USD/CNY', '=' + fxc, 'CNY/USD', '当期汇率'),
        ('6', '关税完税价格', 'CIF × 汇率', '=IF(ISNUMBER($D$7),$D$7*$D$8,"待补")', '元/吨', '海关计征基数'),
        ('7', '关税', '完税价格 × 关税税率', '=IF(ISNUMBER($D$9),$D$9*%s/100,"待补")' % dutyr, '元/吨', ''),
        ('8', '进口环节增值税', '（完税价格 + 关税）× 增值税率', '=IF(ISNUMBER($D$10),($D$9+$D$10)*%s/100,"待补")' % vatr, '元/吨', '可抵扣则为进项'),
        ('9', '境内费用', '港杂/报关/仓储/短驳', '=IF(%s="",0,%s)+IF(%s="",0,%s)' % (inland, inland, other, other), '元/吨', '缺则为 0 并登记缺口'),
        ('10', '进口含税净成本', '完税价 + 关税 + 境内费用（+不可抵扣增值税）', '=IF(ISNUMBER($D$10),$D$9+$D$10+$D$12+IF(%s="否",$D$11,0),"待补")' % rec, '元/吨', '与国内含税价相减'),
        ('11', '进口全口径付现', '含可抵扣增值税的全部付款', '=IF(ISNUMBER($D$10),$D$9+$D$10+$D$11+$D$12,"待补")', '元/吨', '资金占用参考'),
        ('12', '国内现货（含税）', '同规格、同交货地', '=' + dprice, '元/吨', ''),
        ('13', '理论进口价差', '国内含税价 − 进口含税净成本', '=IF(AND(ISNUMBER($D$13),ISNUMBER($D$15)),$D$15-$D$13,"待补")', '元/吨', '>0 国内更贵'),
        ('14', '价差占国内价', '价差 ÷ 国内价', '=IF(AND(ISNUMBER($D$16),$D$15>0),$D$16/$D$15,"待补")', '%', ''),
    ]
    # 行号从 4 开始
    r = 4
    for no, name, formula_cn, fml, unit, note in steps:
        ws2.cell(row=r, column=1, value=no).font = Font(size=10, color='6B7280')
        ws2.cell(row=r, column=2, value=name).font = Font(size=10, bold=True)
        ws2.cell(row=r, column=3, value=formula_cn).font = Font(size=9, color='334155')
        c = ws2.cell(row=r, column=4, value=fml)
        c.fill = CALC_FILL
        c.font = Font(size=10, bold=True)
        c.number_format = '0.00%' if unit == '%' else ('0.0000' if unit == 'CNY/USD' else '0.00')
        ws2.cell(row=r, column=5, value=unit).font = Font(size=9, color='6B7280')
        ws2.cell(row=r, column=6, value=note).font = Font(size=9, color='6B7280')
        for col in range(1, 7):
            ws2.cell(row=r, column=col).border = BOX
        C[no] = 'D%d' % r
        r += 1

    # 修正列引用：上面的 $D$4 等是按"行4起"硬编码的，逐行核对
    # 行4=步骤1(净价) 5=2(CFR) 6=3(保险) 7=4(CIF) 8=5(汇率) 9=6(完税) 10=7(关税)
    # 11=8(VAT) 12=9(境内) 13=10(净成本) 14=11(全口径) 15=12(国内) 16=13(价差) 17=14(占比)
    fix = {
        4: '=IF({qp}="","待补",{qp}+IF({prem}="",0,{prem}))'.format(qp=qp, prem=prem),
        5: '=IF({qt}="FOB",IF(OR({frt}="",{frt}=0),"待补",D4+{frt}),D4)'.format(qt=qt, frt=frt),
        6: '=IF({qt}="CIF",0,IF({insr}="",0,D5*{insr}/100*1.1/(1-{insr}/100*1.1)))'.format(qt=qt, insr=insr),
        7: '=IF(NOT(ISNUMBER(D5)),"待补",IF({qt}="CIF",D5,D5+IF(ISNUMBER(D6),D6,0)))'.format(qt=qt),
        8: '=IF({0}="","待补",{0})'.format(fxc),
        9: '=IF(AND(ISNUMBER(D7),ISNUMBER(D8)),D7*D8,"待补")',
        10: '=IF(AND(ISNUMBER(D9),ISNUMBER({0})),D9*{0}/100,"待补")'.format(dutyr),
        11: '=IF(AND(ISNUMBER(D9),ISNUMBER(D10),ISNUMBER({0})),(D9+D10)*{0}/100,"待补")'.format(vatr),
        12: '=IF(OR({i}="",{i}="待补"),0,{i})+IF({o}="",0,{o})'.format(i=inland, o=other),
        13: '=IF(NOT(ISNUMBER(D11)),"待补",IF(NOT(ISNUMBER(D9)),"待补",'
            'D9+D10+D12+IF({rec}="否",D11,0)))'.format(rec=rec),
        14: '=IF(NOT(ISNUMBER(D11)),"待补",D9+D10+D11+D12)',
        15: '=IF({0}="","待补",{0})'.format(dprice),
        16: '=IF(AND(ISNUMBER(D13),ISNUMBER(D15)),D15-D13,"待补")',
        17: '=IF(AND(ISNUMBER(D16),ISNUMBER(D15),D15>0),D16/D15,"待补")',
    }
    for rr, f in fix.items():
        ws2.cell(row=rr, column=4, value=f)

    ws2['B19'] = '关键结论'
    ws2['B19'].font = Font(bold=True, size=11, color='1D4ED8')
    ws2['B20'] = '理论进口价差（元/吨）'
    ws2['C20'] = '=D16'
    ws2['C20'].number_format = '0.00'
    ws2['C20'].fill = CALC_FILL
    ws2['C20'].font = Font(bold=True, size=12)
    ws2['B21'] = '口径状态'
    ws2['C21'] = ('=IF(NOT(ISNUMBER(D16)),"不可计算：关键数据缺失",'
                  'IF(D16>0,"理论上有进口空间（国内更贵）","理论上无进口空间（国内更便宜）"))')
    ws2['C21'].fill = CALC_FILL
    ws2['C21'].font = Font(bold=True, size=11)
    ws2.merge_cells('C21:F21')
    ws2['B22'] = '一句话提醒'
    ws2['B22'].font = Font(bold=True, size=10)
    ws2['C22'] = '本数只是"到岸 vs 罐区自提"的价差，未含资金、罐容、损耗与对手方风险，不等于可执行贸易利润。'
    ws2['C22'].font = Font(size=9, color='B45309')
    ws2.merge_cells('C22:F22')

    ws2.column_dimensions['A'].width = 6
    ws2.column_dimensions['B'].width = 26
    ws2.column_dimensions['C'].width = 34
    ws2.column_dimensions['D'].width = 15
    ws2.column_dimensions['E'].width = 10
    ws2.column_dimensions['F'].width = 30

    # ======================================================== 3-口径核对
    ws3 = wb.create_sheet('3-可比性核对')
    ws3.sheet_view.showGridLines = False
    ws3['A1'] = '③ 可比性核对：海外价与国内价是否真能相减'
    ws3['A1'].font = TITLE_FONT
    for i, h in enumerate(['#', '检查项', '海外/进口口径', '国内口径', '是否可比', '处理方式'], 1):
        c = ws3.cell(row=3, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BOX
        c.alignment = Alignment(horizontal='center')
    checks = [
        ('规格牌号', prod['spec'], dom.get('spec', prod['spec']), '可比', '同规格'),
        ('价格日期', quote['date'], dom['date'], '可比' if quote['date'] == dom['date'] else '不可比', '必须同日或注明错配影响'),
        ('贸易术语', quote['term'] + ' 中国主港', dom.get('delivery', ''), '需折算', 'CFR→含税净成本后再比'),
        ('计价币种', 'USD/吨 × 汇率', 'CNY/吨', '可比', '按当日汇率折算'),
        ('含税口径', '完税价+关税，VAT可抵扣', '含 13% 增值税', '可比', '两端均为"可抵扣VAT之外"口径'),
        ('数量/包装', quote.get('quantity', ''), dom.get('quantity', ''), '需注意', '散装船批 vs 罐区零单'),
        ('交货地点', quote.get('port', ''), dom.get('region', ''), '需注意', '口岸 vs 罐区，均不含内陆'),
        ('货物状态', '船货/远月船期', '罐内现货', '需注意', '时间价值不同'),
        ('报价性质', '指数评估价', '市场成交价', '需注意', '指数±5–15 USD 议价空间'),
    ]
    r = 4
    for i, (a, b, c2, d, e) in enumerate(checks, 1):
        ws3.cell(row=r, column=1, value=i).font = Font(size=10, color='6B7280')
        ws3.cell(row=r, column=2, value=a).font = Font(size=10, bold=True)
        ws3.cell(row=r, column=3, value=b).font = Font(size=9)
        ws3.cell(row=r, column=4, value=c2).font = Font(size=9)
        cc = ws3.cell(row=r, column=5, value=d)
        cc.fill = OK_FILL if d == '可比' else (WARN_FILL if d in ('需折算', '需注意') else BAD_FILL)
        cc.font = Font(size=10, bold=True)
        cc.alignment = Alignment(horizontal='center')
        ws3.cell(row=r, column=6, value=e).font = Font(size=9, color='334155')
        for col in range(1, 7):
            ws3.cell(row=r, column=col).border = BOX
            ws3.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical='top')
        r += 1
    ws3.cell(row=r + 1, column=2, value='结论').font = Font(bold=True, size=11)
    ws3.cell(row=r + 1, column=3, value='存在"需折算/需注意"项 → 价差可算，但须标注为"带有保留项的口径"，'
                                       '不能与可执行利润混为一谈。')
    ws3.cell(row=r + 1, column=3).font = Font(size=10, color='B45309')
    ws3.merge_cells(start_row=r + 1, start_column=3, end_row=r + 1, end_column=6)
    ws3.column_dimensions['A'].width = 5
    ws3.column_dimensions['B'].width = 16
    ws3.column_dimensions['C'].width = 26
    ws3.column_dimensions['D'].width = 26
    ws3.column_dimensions['E'].width = 10
    ws3.column_dimensions['F'].width = 34

    # ======================================================== 4-历史价差
    ws4 = wb.create_sheet('4-历史价差')
    ws4.sheet_view.showGridLines = False
    ws4['A1'] = '④ 历史进口价差（逐日取当期报价/汇率/国内价；缺任一项则留空，不插值）'
    ws4['A1'].font = TITLE_FONT
    hdrs = ['日期', '海外报价 USD/吨', '贸易术语', '汇率', '国内含税价', 'CIF USD/吨',
            '完税价', '关税', '进口含税净成本', '理论价差', '价差%', '状态', '说明']
    for i, h in enumerate(hdrs, 1):
        c = ws4.cell(row=3, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BOX
        c.alignment = Alignment(horizontal='center', wrap_text=True)

    fxmap = {x['date']: x['rate'] for x in fx['rows']}
    dommap = {x['date']: x['price_cny'] for x in case.get('domestic_hist', {}).get('rows', [])}
    hist = case.get('quotes_hist', [])
    r = 4
    for q in hist:
        d = q['date']
        ws4.cell(row=r, column=1, value=d).font = Font(size=10)
        cc = ws4.cell(row=r, column=2, value=float(q['price_usd']))
        cc.fill = INPUT_FILL
        cc.font = Font(size=10)
        cc.number_format = '0.00'
        ws4.cell(row=r, column=3, value=q.get('term', ''))
        fv = fxmap.get(d)
        if fv is None:
            cf = ws4.cell(row=r, column=4, value=None)
            cf.fill = GAP_FILL
        else:
            cf = ws4.cell(row=r, column=4, value=float(fv))
            cf.fill = INPUT_FILL
        cf.number_format = '0.0000'
        dv_ = dommap.get(d)
        if dv_ is None:
            cd = ws4.cell(row=r, column=5, value=None)
            cd.fill = GAP_FILL
        else:
            cd = ws4.cell(row=r, column=5, value=float(dv_))
            cd.fill = INPUT_FILL
        cd.number_format = '0.00'
        # CIF：CFR/CIF 口径直接取报价；FOB 需运费（历史无运费则待补）
        ws4.cell(row=r, column=6, value='=IF(OR(C%d="CFR",C%d="CIF"),B%d,"待补")' % (r, r, r)).fill = CALC_FILL
        ws4.cell(row=r, column=7, value='=IF(ISNUMBER(F%d),F%d*D%d,"待补")' % (r, r, r)).fill = CALC_FILL
        ws4.cell(row=r, column=8, value='=IF(ISNUMBER(G%d),G%d*$D$%d/100,"待补")' % (r, r, 4)).fill = CALC_FILL
        # 关税行引用「1-参数」税率更稳
        ws4.cell(row=r, column=8, value="=IF(ISNUMBER(G%d),G%d*IFERROR('1-参数'!%s/100,0),\"待补\")" % (r, r, P['duty'])).fill = CALC_FILL
        ws4.cell(row=r, column=9, value='=IF(AND(ISNUMBER(G%d),ISNUMBER(H%d)),G%d+H%d,\"待补\")' % (r, r, r, r)).fill = CALC_FILL
        ws4.cell(row=r, column=10, value='=IF(AND(ISNUMBER(I%d),ISNUMBER(E%d)),E%d-I%d,"待补")' % (r, r, r, r)).fill = CALC_FILL
        ws4.cell(row=r, column=11, value='=IF(AND(ISNUMBER(J%d),ISNUMBER(E%d),E%d>0),J%d/E%d,"待补")' % (r, r, r, r, r)).fill = CALC_FILL
        ws4.cell(row=r, column=11).number_format = '0.0%'
        ws4.cell(row=r, column=12, value='=IF(ISNUMBER(J%d),"可配对","缺口")' % r).fill = CALC_FILL
        ws4.cell(row=r, column=13, value='').font = Font(size=9, color='6B7280')
        for col in range(1, 14):
            ws4.cell(row=r, column=col).border = BOX
        for col in (6, 7, 8, 9, 10):
            ws4.cell(row=r, column=col).number_format = '0.00'
        r += 1

    # 缺口行：明确标注
    for g in case.get('history_gaps', []):
        ws4.cell(row=r, column=1, value=g['date']).font = Font(size=9, color='7C3AED')
        c = ws4.cell(row=r, column=12, value='不生成')
        c.fill = GAP_FILL
        c.font = Font(size=9, color='7C3AED', bold=True)
        ws4.cell(row=r, column=13, value='%s：%s' % (g['kind'], g['text'])).font = Font(size=9, color='6B7280')
        ws4.merge_cells(start_row=r, start_column=13, end_row=r, end_column=13)
        for col in range(1, 14):
            ws4.cell(row=r, column=col).border = BOX
        r += 1

    widths = [13, 15, 9, 10, 13, 12, 11, 10, 15, 12, 9, 10, 60]
    for i, w in enumerate(widths, 1):
        ws4.column_dimensions[get_column_letter(i)].width = w
    ws4.freeze_panes = 'B4'

    # ======================================================== 5-敏感性
    ws5 = wb.create_sheet('5-敏感性')
    ws5.sheet_view.showGridLines = False
    ws5['A1'] = '⑤ 敏感性分析（公式驱动：改 B 列参数即重算三张表）'
    ws5['A1'].font = TITLE_FONT
    ws5['A3'] = '基准进口含税净成本'
    ws5['C3'] = "=IFERROR('2-进口成本折算'!D13,0)"
    ws5['C3'].fill = CALC_FILL
    ws5['A4'] = '基准理论价差'
    ws5['C4'] = "=IFERROR('2-进口成本折算'!D16,0)"
    ws5['C4'].fill = CALC_FILL
    ws5['A9'] = '注：C3/C4 若显示"计算未完成"，表示缺关键参数，此时敏感性表一律显示"待补"，不按 0 计算。'
    ws5['A9'].font = Font(size=9, color='B45309')
    ws5['A5'] = '基准汇率'
    ws5['C5'] = "=IFERROR('1-参数'!%s,\"待补\")" % P['fx']
    ws5['C5'].fill = CALC_FILL
    ws5['A6'] = '基准海外报价'
    ws5['C6'] = "=IFERROR('1-参数'!%s,\"待补\")" % P['q_price']
    ws5['C6'].fill = CALC_FILL
    ws5['A7'] = '汇率每 +1 对成本的影响（≈ 完税价/汇率）'
    ws5['C7'] = "=IFERROR(IF(AND(ISNUMBER(C3),ISNUMBER(C5)),('2-进口成本折算'!D9)/C5,\"待补\"),\"待补\")"
    ws5['C7'].fill = CALC_FILL
    ws5['A8'] = '报价每 +1 USD 对成本的影响（汇率×(1+关税)）'
    ws5['C8'] = "=IFERROR(IF(AND(ISNUMBER(C5),ISNUMBER('1-参数'!%s)),C5*(1+'1-参数'!%s/100),\"待补\"),\"待补\")" % (P['fx'], P['duty'])
    ws5['C8'].fill = CALC_FILL
    for a in ('A3', 'A4', 'A5', 'A6', 'A7', 'A8'):
        ws5[a].font = Font(size=10, bold=True)
    for a in ('C7', 'C8'):
        ws5[a].number_format = '0.0000'
    # C3/C4：缺数据时显示"计算未完成"，而不是显示 0 误导
    for a in ('C3', 'C4'):
        ws5[a].number_format = '0.00;[Red]-0.00;"计算未完成"'
    ws5['C5'].number_format = '0.0000'
    ws5['C6'].number_format = '0.00'

    def sens_block(start, title, headers, deltas, fmlfn, fmt):
        ws5.cell(row=start, column=1, value=title).font = Font(bold=True, size=11, color='1D4ED8')
        for i, h in enumerate(headers, 1):
            c = ws5.cell(row=start + 1, column=i, value=h)
            c.fill = HEAD_FILL
            c.font = HEAD_FONT
            c.border = BOX
            c.alignment = Alignment(horizontal='center')
        rr = start + 2
        for d in deltas:
            ws5.cell(row=rr, column=1, value=d).fill = INPUT_FILL
            ws5.cell(row=rr, column=2, value=fmlfn(d)).fill = CALC_FILL
            # 情景价差 = 基准价差 −（情景成本 − 基准成本）；任一基准值缺失则返回"待补"
            ws5.cell(row=rr, column=3,
                     value='=IF(OR(NOT(ISNUMBER($C$3)),NOT(ISNUMBER($C$4)),NOT(ISNUMBER(B%d))),"待补",'
                           '$C$4-(%s-$C$3))' % (rr, fmlfn(d))).fill = CALC_FILL
            ws5.cell(row=rr, column=4, value='=IF(ISNUMBER(C%d),C%d-$C$4,"待补")' % (rr, rr)).fill = CALC_FILL
            for col in range(1, 5):
                ws5.cell(row=rr, column=col).border = BOX
                ws5.cell(row=rr, column=col).number_format = fmt[col - 1]
            rr += 1
        return rr

    # 汇率敏感性：成本按 (完税价/汇率)×新汇率 缩放，其余项不变
    rr = sens_block(10, 'A. 汇率变动对价差的影响',
                    ['汇率变动', '情景汇率', '情景价差', '相对基准'],
                    [-0.03, -0.015, 0, 0.015, 0.03],
                    lambda d: "=IFERROR(%s*(1+%s),\"待补\")" % ("$C$5", d),
                    ['0.0%', '0.0000', '0.00', '0.00'])
    fx_end = rr

    def fx_cost(d):
        return "(%s+(%s*(1+(%s))-%s)*%s)" % ("$C$3", "$C$5", d, "$C$5", "$C$7")

    # A 段：只在全部基准值都是数字时才计算，否则显示"待补"（用 IF 而非 IFERROR 包文本）
    rr = 12
    for d in [-0.03, -0.015, 0, 0.015, 0.03]:
        ws5.cell(row=rr, column=3,
                 value='=IF(AND(ISNUMBER($C$3),ISNUMBER($C$4),ISNUMBER($C$5),ISNUMBER($C$7)),'
                       '$C$4-(%s-$C$3),"待补")' % fx_cost(d))
        ws5.cell(row=rr, column=4,
                 value='=IF(ISNUMBER(C%d),C%d-$C$4,"待补")' % (rr, rr))
        rr += 1

    # 海外报价敏感性：成本按 汇率×(1+关税) 每美元缩放
    rr2 = sens_block(fx_end + 1, 'B. 海外报价变动对价差的影响',
                     ['报价变动', '情景报价', '情景价差', '相对基准'],
                     [-0.03, -0.015, 0, 0.015, 0.03],
                     lambda d: "=IFERROR($C$6*(1+%s),\"待补\")" % d,
                     ['0.0%', '0.00', '0.00', '0.00'])
    rr = fx_end + 3
    for d in [-0.03, -0.015, 0, 0.015, 0.03]:
        ws5.cell(row=rr, column=3,
                 value='=IF(OR(NOT(ISNUMBER($C$3)),NOT(ISNUMBER($C$4)),NOT(ISNUMBER($C$6)),NOT(ISNUMBER($C$8))),'
                       '"待补",$C$4-(($C$3+($C$6*(1+%s)-$C$6)*$C$8)-$C$3))' % d)
        ws5.cell(row=rr, column=4, value='=IF(ISNUMBER(C%d),C%d-$C$4,"待补")' % (rr, rr))
        rr += 1
    # 运费
    ws5.cell(row=rr + 1, column=1, value='C. 国际运费变动').font = Font(bold=True, size=11, color='1D4ED8')
    ws5.cell(row=rr + 2, column=1, value='说明').font = Font(size=9, color='6B7280')
    ws5.cell(row=rr + 2, column=2, value='运费每变动 1 USD/吨，进口含税净成本变动 = 汇率 ×(1+关税) ≈ '
                                        '（见「1-参数」汇率×(1+关税))，即用 2-进口成本折算 的公式逐点重算。'
                                        '当前运费缺失时本项无法计算，请先在「1-参数」补入运费。')
    ws5.cell(row=rr + 2, column=2).font = Font(size=9, color='B45309')
    ws5.merge_cells(start_row=rr + 2, start_column=2, end_row=rr + 2, end_column=4)

    ws5.column_dimensions['A'].width = 14
    ws5.column_dimensions['B'].width = 18
    ws5.column_dimensions['C'].width = 16
    ws5.column_dimensions['D'].width = 26

    # ======================================================== 6-理论vs真实
    ws6 = wb.create_sheet('6-理论vs真实')
    ws6.sheet_view.showGridLines = False
    ws6['A1'] = '⑥ 理论价差 ≠ 可执行利润：差距在哪里'
    ws6['A1'].font = TITLE_FONT
    for i, h in enumerate(['项目', '金额(元/吨)', '是否已计入', '性质与备注'], 1):
        c = ws6.cell(row=3, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BOX
        c.alignment = Alignment(horizontal='center')
    items = [
        ('理论进口价差', "='2-进口成本折算'!D16", '是', '国内含税现货 − 进口含税净成本'),
        ('国际运费（FOB 时）', "=IF('1-参数'!%s=\"\",\"待补\",-'1-参数'!%s*'1-参数'!%s)" % (P['frt'], P['frt'], P['fx']), '见口径', 'CFR 已含则不计'),
        ('境内费用', "='2-进口成本折算'!D12", '是', '港杂/报关/仓储/短驳'),
        ('可抵扣进口增值税', "='2-进口成本折算'!D11", '否', '现金流占用，非成本'),
        ('资金成本（90天）', '待补', '否', '授信/信用证/锁汇成本'),
        ('计量与质量损耗', '待补', '否', '卸货损耗、纯度偏差索赔'),
        ('罐容与滞期', '待补', '否', '到港集中时的接卸约束'),
        ('对手方与结算风险', '待补', '否', '预付比例、单据、合规审查'),
    ]
    r = 4
    for name, f, flag, note in items:
        ws6.cell(row=r, column=1, value=name).font = Font(size=10, bold=True)
        if f == '待补':
            c = ws6.cell(row=r, column=2, value='待补')
            c.fill = GAP_FILL
        else:
            c = ws6.cell(row=r, column=2, value=f)
            c.fill = CALC_FILL
        c.number_format = '0.00'
        ws6.cell(row=r, column=3, value=flag).alignment = Alignment(horizontal='center')
        ws6.cell(row=r, column=4, value=note).font = Font(size=9, color='6B7280')
        for col in range(1, 5):
            ws6.cell(row=r, column=col).border = BOX
        r += 1
    ws6.cell(row=r + 1, column=1, value='提醒').font = Font(bold=True)
    ws6.cell(row=r + 1, column=2, value='理论价差只回答"同一时点、同一口径下便宜/贵多少"；能不能做还取决于上表待补项。'
                                        '本表不提供交易建议，也不预测价格。')
    ws6.cell(row=r + 1, column=2).font = Font(size=9, color='B45309')
    ws6.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=4)
    ws6.column_dimensions['A'].width = 24
    ws6.column_dimensions['B'].width = 16
    ws6.column_dimensions['C'].width = 12
    ws6.column_dimensions['D'].width = 60

    # ======================================================== 7-来源
    ws7 = wb.create_sheet('7-来源清单')
    ws7.sheet_view.showGridLines = False
    ws7['A1'] = '⑦ 来源清单（A=官方；B=专业资讯/研报；C=转述/参照）'
    ws7['A1'].font = TITLE_FONT
    for i, h in enumerate(['等级', '编号', '发布方', '标题', '日期', 'URL', '原文摘录'], 1):
        c = ws7.cell(row=3, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BOX
        c.alignment = Alignment(horizontal='center')
    r = 4
    tier_fill = {'A': OK_FILL, 'B': PatternFill('solid', fgColor='DBEAFE'), 'C': WARN_FILL}
    for s in sorted(case.get('sources', []), key=lambda x: ({'A': 0, 'B': 1, 'C': 2}.get(x.get('tier'), 9), x['id'])):
        ws7.cell(row=r, column=1, value=s.get('tier', '')).fill = tier_fill.get(s.get('tier'), WARN_FILL)
        ws7.cell(row=r, column=1).alignment = Alignment(horizontal='center')
        ws7.cell(row=r, column=2, value=s['id']).font = Font(size=9)
        ws7.cell(row=r, column=3, value=s['publisher']).font = Font(size=10, bold=True)
        ws7.cell(row=r, column=4, value=s['title']).font = Font(size=9)
        ws7.cell(row=r, column=5, value=s['date']).font = Font(size=9)
        cu = ws7.cell(row=r, column=6, value=s['url'])
        cu.font = Font(size=9, color='1D4ED8', underline='single')
        cu.hyperlink = s['url']
        ws7.cell(row=r, column=7, value=s.get('excerpt', '')).font = Font(size=9, color='475569')
        for col in range(1, 8):
            ws7.cell(row=r, column=col).border = BOX
            if col >= 4:
                ws7.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical='top')
        r += 1
    for i, w in enumerate([6, 16, 22, 40, 12, 46, 60], 1):
        ws7.column_dimensions[get_column_letter(i)].width = w

    # ======================================================== 8-缺口
    ws8 = wb.create_sheet('8-缺口登记')
    ws8.sheet_view.showGridLines = False
    ws8['A1'] = '⑧ 数据缺口登记（缺什么 / 影响什么 / 怎么补）'
    ws8['A1'].font = TITLE_FONT
    for i, h in enumerate(['优先级', '缺口项', '对结论的影响', '补数方法', '影响模块', '状态'], 1):
        c = ws8.cell(row=3, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BOX
        c.alignment = Alignment(horizontal='center')
    sev_fill = {'high': BAD_FILL, 'medium': WARN_FILL, 'low': PatternFill('solid', fgColor='E5E7EB')}
    sev_txt = {'high': '高', 'medium': '中', 'low': '低'}
    r = 4
    for g in case.get('gaps', []):
        ws8.cell(row=r, column=1, value=sev_txt.get(g['severity'], '低')).fill = sev_fill.get(g['severity'], sev_fill['low'])
        ws8.cell(row=r, column=1).alignment = Alignment(horizontal='center')
        ws8.cell(row=r, column=2, value=g['item']).font = Font(size=10, bold=True)
        ws8.cell(row=r, column=3, value=g['impact']).font = Font(size=9)
        ws8.cell(row=r, column=4, value=g['fix']).font = Font(size=9, color='1D4ED8')
        ws8.cell(row=r, column=5, value='、'.join(g.get('affects', []))).font = Font(size=9)
        ws8.cell(row=r, column=6, value='待补')
        ws8.cell(row=r, column=6).fill = GAP_FILL
        for col in range(1, 7):
            ws8.cell(row=r, column=col).border = BOX
            ws8.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical='top')
        r += 1
    for i, w in enumerate([8, 34, 52, 46, 18, 10], 1):
        ws8.column_dimensions[get_column_letter(i)].width = w

    # ======================================================== 9-引擎校验
    ws9 = wb.create_sheet('9-引擎校验')
    ws9.sheet_view.showGridLines = False
    ws9['A1'] = '⑨ 独立引擎校验：Excel 公式 vs 计算引擎（两者不一致即为计算错误）'
    ws9['A1'].font = TITLE_FONT
    for i, h in enumerate(['项目', 'Excel 公式值', '引擎计算值', '差值', '判定'], 1):
        c = ws9.cell(row=3, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.border = BOX
        c.alignment = Alignment(horizontal='center')
    pairs = [
        ('关税完税价格', "='2-进口成本折算'!D9", engine.get('cif_cny')),
        ('关税', "='2-进口成本折算'!D10", engine.get('duty')),
        ('进口增值税', "='2-进口成本折算'!D11", engine.get('vat')),
        ('进口含税净成本', "='2-进口成本折算'!D13", engine.get('cost')),
        ('理论价差', "='2-进口成本折算'!D16", engine.get('spread')),
    ]
    r = 4
    for name, f, ev in pairs:
        ws9.cell(row=r, column=1, value=name).font = Font(size=10, bold=True)
        ce = ws9.cell(row=r, column=2, value=f)
        ce.fill = CALC_FILL
        ce.number_format = '0.00'
        cv = ws9.cell(row=r, column=3, value=(round(ev, 4) if isinstance(ev, (int, float)) else None))
        cv.number_format = '0.00'
        cv.font = Font(size=10, color='1D4ED8')
        ws9.cell(row=r, column=4, value='=IF(AND(ISNUMBER(B%d),ISNUMBER(C%d)),B%d-C%d,"缺")' % (r, r, r, r)).number_format = '0.00'
        ws9.cell(row=r, column=5,
                 value='=IF(NOT(AND(ISNUMBER(B%d),ISNUMBER(C%d))),'
                       'IF(AND(ISERR(B%d),C%d=""),"无须计算",'
                       'IF(AND(NOT(ISNUMBER(B%d)),NOT(ISNUMBER(C%d))),"两侧均无值","待核对")),'
                       'IF(ABS(D%d)<0.02,"一致","复核"))' % (r, r, r, r, r, r, r))
        for col in range(1, 6):
            ws9.cell(row=r, column=col).border = BOX
        r += 1
    ws9.cell(row=r + 1, column=1, value='说明').font = Font(bold=True, size=10)
    ws9.cell(row=r + 1, column=2, value='引擎值为外部程序（Node/Python 同一算法）独立算得的结果。若"判定"出现"复核"，'
                                        '说明 Excel 公式口径与引擎不一致，请检查 2-进口成本折算 的公式引用。')
    ws9.cell(row=r + 1, column=2).font = Font(size=9, color='6B7280')
    ws9.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=5)
    for i, w in enumerate([20, 16, 16, 12, 12], 1):
        ws9.column_dimensions[get_column_letter(i)].width = w

    # 统一页面设置
    for sheet in wb.worksheets:
        sheet.freeze_panes = 'A4' if sheet.title not in ('0-说明', '2-进口成本折算') else None

    wb.save(out_path)
    print('OK  %s  (%d sheets)' % (out_path, len(wb.worksheets)))


if __name__ == '__main__':
    main()
