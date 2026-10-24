# -*- coding: utf-8 -*-
"""构建 Excel 利润模型（多工作表，全部为活公式：改单耗/价格即重算）。

工作表：
  00_说明          口径声明、三层指标定义、使用方法
  01_参数与单耗     可编辑的单耗/单价/收率/制造费用（唯一输入源）
  02_成本构成       引用 01 的活公式，逐项展开（单位换算、收率修正）
  03_加工价差与利润  三层指标分离
  04_历史价格       近 1 年 PVC/电石序列 + 来源标注
  05_月度台账       月度汇总 + 与第三方毛利对比
  06_周度校验       40 周理论 vs 隆众毛利
  07_敏感性分析     双因素矩阵（活公式）+ 单因素表
  08_公式与来源     所有公式的文字化说明 + 每个数字的来源链接
"""
import os
import sys
import json
import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, Reference

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import engine as E  # noqa: E402

DATA = json.load(open(os.path.join(ROOT, 'build', 'data.json'), encoding='utf-8'))
HIST = json.load(open(os.path.join(ROOT, 'build', 'history.json'), encoding='utf-8'))
ANCH = json.load(open(os.path.join(ROOT, 'build', 'carbide_anchors.json'), encoding='utf-8'))

NAVY = '0F172A'
BLUE = '1D4ED8'
LBLUE = 'DBEAFE'
GREY = 'F1F5F9'
AMBER = 'FEF3C7'
GREEN = 'DCFCE7'
RED = 'FEE2E2'
WHITE = 'FFFFFF'

F_TITLE = Font(name='Microsoft YaHei', size=15, bold=True, color=WHITE)
F_SUB = Font(name='Microsoft YaHei', size=9, color='CBD5E1')
F_H = Font(name='Microsoft YaHei', size=10, bold=True, color=WHITE)
F_B = Font(name='Microsoft YaHei', size=10, bold=True)
F_N = Font(name='Microsoft YaHei', size=10)
F_S = Font(name='Microsoft YaHei', size=9, color='475569')
F_IN = Font(name='Consolas', size=10, color='9A3412', bold=True)
F_NUM = Font(name='Consolas', size=10)
F_NUMB = Font(name='Consolas', size=11, bold=True)

FILL_H = PatternFill('solid', fgColor=NAVY)
FILL_SEC = PatternFill('solid', fgColor=LBLUE)
FILL_IN = PatternFill('solid', fgColor=AMBER)
FILL_OUT = PatternFill('solid', fgColor=GREY)
FILL_OK = PatternFill('solid', fgColor=GREEN)
FILL_BAD = PatternFill('solid', fgColor=RED)

THIN = Side(style='thin', color='CBD5E1')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

wb = Workbook()


def banner(ws, title, sub, ncol=8):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=title)
    c.font = F_TITLE
    c.fill = PatternFill('solid', fgColor=NAVY)
    c.alignment = Alignment(vertical='center', indent=1)
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c2 = ws.cell(row=2, column=2 - 1, value=sub)
    c2.font = F_SUB
    c2.fill = PatternFill('solid', fgColor=NAVY)
    c2.alignment = Alignment(vertical='center', indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 26


def header(ws, row, cols, widths=None):
    for i, h in enumerate(cols, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = F_H
        c.fill = FILL_H
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def section(ws, row, text, ncol):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
    c = ws.cell(row=row, column=1, value=text)
    c.font = F_B
    c.fill = FILL_SEC
    c.alignment = Alignment(vertical='center', indent=1)
    ws.row_dimensions[row].height = 22


# ====================================================== 00_说明
ws = wb.active
ws.title = '00_说明'
banner(ws, '中国电石法 PVC · 产业链利润模型（理论加工价差 / 理论制造利润）',
       '数据冻结于 2026-10-20　|　区间 2025-10-20～2026-10-19　|　黄色单元格=可编辑输入，灰色=公式输出，请勿手改', 6)
rows = [
    ('', ''),
    ('一、这个模型算什么', ''),
    ('理论加工价差', '= 产品含税价 − 原料成本（原料单耗已按综合收率修正）。只反映"原料→产品"的转换价差，不含任何加工费用。'),
    ('理论制造利润', '= 加工价差 − 已核实的能源/辅料/制造费用。仍不是企业净利润。'),
    ('企业实际利润', '本模型【不输出】。它需要财务费用、销售物流、税费、检修损失、区域价差等企业内部数据，缺少可核实来源时不编造。'),
    ('', ''),
    ('二、三层指标为什么必须分开', ''),
    ('常见错误 1', '把"加工价差"直接叫作"利润"。价差 1083 元/吨听起来很好，扣完成本后是 -431 元/吨，方向完全相反。'),
    ('常见错误 2', '把不同工艺的单耗混用。外购电石口径的电石 1.45 t/t 与一体化口径的综合电耗 8500 kWh/t 放在一起，会重复计算近 5000 度电。'),
    ('常见错误 3', '在缺价区间凭空外推。本模型对无电石报价的交易日直接留空，不做插值填充（除已披露锚点之间）。'),
    ('', ''),
    ('三、怎么用', ''),
    ('第 1 步', '打开 01_参数与单耗，把【单耗】【单价】改成你企业的真实值（黄色格）。有企业实测值就优先用实测值，行业典型值只作默认。'),
    ('第 2 步', '在 01 表修改【综合收率】【制造费用】。'),
    ('第 3 步', '02_成本构成 与 03_加工价差与利润 会自动重算（全部为活公式）。'),
    ('第 4 步', '07_敏感性分析 的双因素矩阵同样会自动跟随 01 表的修改重算。'),
    ('第 5 步', '任何数字要追溯来源 → 看 08_公式与来源。'),
    ('', ''),
    ('四、重要口径提醒', ''),
    ('税费', '产品价与原料价均为含 13% 增值税口径，因此价差本身含税，不做二次扣税。'),
    ('收率', '只作用于原料与辅料单耗，不作用于能源（电、汽按实物量计量，与收率无关）。'),
    ('区域', '本模型价格为全国基准，未体现区域价差（乌海 vs 山东可达 400–600 元/吨）。'),
    ('时段', '电石日价仅近 93 天可得；更早区间使用已披露锚点线性插值，并在 04 表标注 interp。'),
]
r = 4
for k, v in rows:
    if k and not v:
        section(ws, r, k, 6)
    elif k:
        ws.cell(row=r, column=1, value=k).font = F_B
        ws.cell(row=r, column=1).alignment = Alignment(vertical='top')
        c = ws.cell(row=r, column=2, value=v)
        c.font = F_N
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        ws.row_dimensions[r].height = 30 if len(v) < 60 else 44
    r += 1
ws.column_dimensions['A'].width = 20
for col in 'BCDEF':
    ws.column_dimensions[col].width = 26

# ====================================================== 01_参数与单耗
ws = wb.create_sheet('01_参数与单耗')
banner(ws, '01 参数与单耗（唯一输入源）',
       '黄色格为可编辑输入；改这里，02/03/07 全部自动重算。单耗单位按"每吨 PVC"计。', 10)
r = 4
section(ws, r, '产品与工艺', 10)
r += 1
header(ws, r, ['项目', '取值', '单位', '说明'], [26, 16, 14, 78])
r += 1
ws.cell(row=r, column=1, value='产品名称').font = F_N
ws.cell(row=r, column=2, value='PVC 树脂粉 SG-5').font = F_N
ws.cell(row=r, column=3, value='—').font = F_S
ws.cell(row=r, column=4, value='电石乙炔法，悬浮聚合').font = F_S
r += 1
PROD_ROW = r
ws.cell(row=r, column=1, value='产品含税售价').font = F_B
c = ws.cell(row=r, column=2, value=E.DEFAULT['product']['price'])
c.font = F_IN; c.fill = FILL_IN; c.number_format = '#,##0.00'
ws.cell(row=r, column=3, value='元/吨').font = F_S
ws.cell(row=r, column=4, value='生意社 2026-10-19 PVC(SG-5) 基准价 4865 元/吨').font = F_S
for col in range(1, 5):
    ws.cell(row=r, column=col).border = BOX
r += 1
YLD_ROW = r
ws.cell(row=r, column=1, value='综合收率').font = F_B
c = ws.cell(row=r, column=2, value=E.DEFAULT['yield'])
c.font = F_IN; c.fill = FILL_IN; c.number_format = '0.00%'
ws.cell(row=r, column=3, value='CaC₂→PVC').font = F_S
ws.cell(row=r, column=4, value='行业典型 96–98%；取 97%。收率只作用于原料与辅料，不作用于能源').font = F_S
for col in range(1, 5):
    ws.cell(row=r, column=col).border = BOX
r += 1
VAT_ROW = r
ws.cell(row=r, column=1, value='增值税率').font = F_N
c = ws.cell(row=r, column=2, value=0.13)
c.font = F_NUMB; c.fill = FILL_OUT; c.number_format = '0%'
ws.cell(row=r, column=3, value='—').font = F_S
ws.cell(row=r, column=4, value='产品与原料同为含税价，价差含税，不做二次扣税').font = F_S
for col in range(1, 5):
    ws.cell(row=r, column=col).border = BOX

r += 2
section(ws, r, '逐项单耗与单价（单位换算系数：kg→0.001 吨；kWh 元/度=元；吨=1）', 10)
r += 1
header(ws, r, ['物料', '类别', '单耗', '单耗单位', '换算系数', '计费单耗(t/度)', '单价', '单价单位', '成本 元/吨', '占原料'],
       [24, 10, 12, 16, 12, 16, 12, 16, 16, 10])
FIRST_IN = r + 1
r += 1
for it in E.DEFAULT['inputs']:
    ws.cell(row=r, column=1, value=it['name']).font = F_N
    ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True, vertical='center')
    ws.cell(row=r, column=2, value={'raw': '原料', 'energy': '能源', 'aux': '辅料'}[it['kind']]).font = F_S
    c = ws.cell(row=r, column=3, value=it['cons'])
    c.font = F_IN; c.fill = FILL_IN; c.number_format = '0.0000'
    ws.cell(row=r, column=4, value=it['unit']).font = F_S
    k = 0.001 if it['unit'].lower().startswith('kg') else 1.0
    ay = (it['kind'] in ('raw', 'aux'))
    c = ws.cell(row=r, column=5, value=k)
    c.font = F_NUM; c.number_format = '0.000'
    c = ws.cell(row=r, column=6,
                value='=IF(OR(C%d=0,ISBLANK(C%d)),0,C%d*E%d%s)' % (r, r, r, r, ('/$B$%d' % YLD_ROW) if ay else ''))
    c.font = F_NUM; c.number_format = '0.0000'
    c = ws.cell(row=r, column=7, value=it['price'])
    c.font = F_IN; c.fill = FILL_IN; c.number_format = '#,##0'
    ws.cell(row=r, column=8, value='元/吨' if k == 1 else '元/kg').font = F_S
    c = ws.cell(row=r, column=9, value='=ROUND(F%d*G%d,4)' % (r, r))
    c.font = F_NUM; c.number_format = '#,##0.00'
    for col in range(1, 11):
        ws.cell(row=r, column=col).border = BOX
    r += 1
LAST_IN = r - 1

# 副产
BYP_ROW = r
ws.cell(row=r, column=1, value='联产烧碱收益抵减').font = F_N
ws.cell(row=r, column=2, value='副产').font = F_S
c = ws.cell(row=r, column=3, value=E.DEFAULT['byproduct']['cons'])
c.font = F_IN; c.fill = FILL_IN; c.number_format = '0.0000'
ws.cell(row=r, column=4, value='吨/吨').font = F_S
ws.cell(row=r, column=5, value=1).font = F_NUM
c = ws.cell(row=r, column=6, value='=C%d*E%d' % (r, r)); c.font = F_NUM; c.number_format = '0.0000'
c = ws.cell(row=r, column=7, value=E.DEFAULT['byproduct']['price'])
c.font = F_IN; c.fill = FILL_IN; c.number_format = '#,##0'
ws.cell(row=r, column=8, value='元/吨').font = F_S
c = ws.cell(row=r, column=9, value='=ROUND(F%d*G%d,4)' % (r, r)); c.font = F_NUM; c.number_format = '#,##0.00'
for col in range(1, 11):
    ws.cell(row=r, column=col).border = BOX

r += 1
ENABLE_ROW = r
ws.cell(row=r, column=1, value='是否计入联产烧碱收益').font = F_B
c = ws.cell(row=r, column=2, value='否')
c.font = F_IN; c.fill = FILL_IN
ws.cell(row=r, column=4, value='填"是"则按氯碱一体化口径抵减；默认"否"=外购电石口径（与隆众周报样本一致）').font = F_S
ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=10)
r += 2

section(ws, r, '制造费用（元/吨 PVC）', 10)
r += 1
header(ws, r, ['项目', '取值', '单位', '说明'], [24, 16, 14, 70])
r += 1
MFG_ROWS = {}
for key, label, val, note in [
    ('labor', '人工成本', E.DEFAULT['manufacturing']['labor'], '按 60 人/20 万吨·年、人均 14 万元折算'),
    ('depreciation', '设备折旧', E.DEFAULT['manufacturing']['depreciation'], '按投资强度与 10 年折旧折算'),
    ('packaging', '包装费用', E.DEFAULT['manufacturing']['packaging'], '25kg 编织袋 + 托盘，约 480 袋/吨'),
    ('other', '其他制造费用', E.DEFAULT['manufacturing']['other'], '维修、安全环保、检验等'),
]:
    ws.cell(row=r, column=1, value=label).font = F_N
    c = ws.cell(row=r, column=2, value=val)
    c.font = F_IN; c.fill = FILL_IN; c.number_format = '#,##0'
    ws.cell(row=r, column=3, value='元/吨').font = F_S
    ws.cell(row=r, column=4, value=note).font = F_S
    for col in range(1, 5):
        ws.cell(row=r, column=col).border = BOX
    MFG_ROWS[key] = r
    r += 1
MFG_TOT_ROW = r
ws.cell(row=r, column=1, value='制造费用合计').font = F_B
c = ws.cell(row=r, column=2, value='=SUM(B%d:B%d)' % (MFG_ROWS['labor'], MFG_ROWS['other']))
c.font = F_NUMB; c.fill = FILL_OUT; c.number_format = '#,##0'
ws.cell(row=r, column=3, value='元/吨').font = F_S
for col in range(1, 5):
    ws.cell(row=r, column=col).border = BOX
r += 1
MFG_ON_ROW = r
ws.cell(row=r, column=1, value='是否计入制造费用').font = F_B
c = ws.cell(row=r, column=2, value='是'); c.font = F_IN; c.fill = FILL_IN
ws.cell(row=r, column=4, value='填"是"=理论制造利润口径；填"否"=只算加工价差').font = F_S
ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=10)
for col in range(1, 5):
    ws.cell(row=r, column=col).border = BOX

ws.freeze_panes = 'A5'

REFS = {
    'prod': "'01_参数与单耗'!$B$%d" % PROD_ROW,
    'yield': "'01_参数与单耗'!$B$%d" % YLD_ROW,
    'inputs': (FIRST_IN, LAST_IN),
    'byp': BYP_ROW, 'byp_on': ENABLE_ROW,
    'mfg_tot': MFG_TOT_ROW, 'mfg_on': MFG_ON_ROW,
    'mfg': MFG_ROWS,
}

# ====================================================== 02_成本构成
ws2 = wb.create_sheet('02_成本构成')
banner(ws2, '02 成本构成（公式联动 01 表）',
       '本表所有数字均为公式；改 01 表即刻重算。计费单耗=名义单耗×换算系数÷收率（能源不除收率）。', 9)
r = 4
header(ws2, r, ['物料', '类别', '单耗', '换算系数', '计费单耗', '单价', '单位成本', '占原料成本', '占总成本'],
       [24, 8, 12, 11, 13, 11, 13, 13, 12])
r += 1
FIRST2 = r
for i, it in enumerate(E.DEFAULT['inputs']):
    src = FIRST_IN + i
    ws2.cell(row=r, column=1, value=it['name']).font = F_N
    ws2.cell(row=r, column=2, value={'raw': '原料', 'energy': '能源', 'aux': '辅料'}[it['kind']]).font = F_S
    for col, ref in [(3, 'C'), (4, 'E'), (5, 'F'), (6, 'G')]:
        c = ws2.cell(row=r, column=col, value="='01_参数与单耗'!%s%d" % (ref, src))
        c.font = F_NUM; c.number_format = '0.0000' if col in (3, 5) else '#,##0'
    c = ws2.cell(row=r, column=7, value='=ROUND(E%d*F%d,2)' % (r, r))
    c.font = F_NUMB; c.number_format = '#,##0.00'
    c = ws2.cell(row=r, column=8,
                 value='=IF(SUMIF($B$%d:$B$%d,"原料",$G$%d:$G$%d)=0,"—",G%d/SUMIF($B$%d:$B$%d,"原料",$G$%d:$G$%d))'
                       % (FIRST2, FIRST2 + len(E.DEFAULT['inputs']) - 1, FIRST2, FIRST2 + len(E.DEFAULT['inputs']) - 1,
                          r, FIRST2, FIRST2 + len(E.DEFAULT['inputs']) - 1, FIRST2, FIRST2 + len(E.DEFAULT['inputs']) - 1))
    c.font = F_NUM; c.number_format = '0.0%'
    for col in range(1, 10):
        ws2.cell(row=r, column=col).border = BOX
    r += 1
LAST2 = r - 1

for col in range(1, 10):
    ws2.cell(row=r, column=col).border = BOX
ws2.cell(row=r, column=1, value='联产烧碱收益').font = F_N
ws2.cell(row=r, column=2, value='副产').font = F_S
c = ws2.cell(row=r, column=7, value="=IF('01_参数与单耗'!$B$%d=\"是\",'01_参数与单耗'!I%d,0)" % (ENABLE_ROW, BYP_ROW))
c.font = F_NUMB; c.number_format = '#,##0.00'
c = ws2.cell(row=r, column=8, value='抵减'); c.font = F_S
BYP2 = r
r += 1

r += 1
SUM2 = r
labels = [('原料成本小计（已按收率修正）', '=SUMIF($B$%d:$B$%d,"原料",$G$%d:$G$%d)' % (FIRST2, LAST2, FIRST2, LAST2)),
          ('能源成本小计', '=SUMIF($B$%d:$B$%d,"能源",$G$%d:$G$%d)' % (FIRST2, LAST2, FIRST2, LAST2)),
          ('辅料成本小计', '=SUMIF($B$%d:$B$%d,"辅料",$G$%d:$G$%d)' % (FIRST2, LAST2, FIRST2, LAST2))]
SUM_ROWS = {}
for lab, f in labels:
    ws2.cell(row=r, column=1, value=lab).font = F_B
    ws2.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws2.cell(row=r, column=7, value=f); c.font = F_NUMB; c.fill = FILL_OUT; c.number_format = '#,##0.00'
    for col in range(1, 10):
        ws2.cell(row=r, column=col).border = BOX
    SUM_ROWS[lab[:2]] = r
    r += 1
ws2.cell(row=r, column=1, value='制造费用合计').font = F_B
ws2.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
c = ws2.cell(row=r, column=7, value="=IF('01_参数与单耗'!$B$%d=\"是\",'01_参数与单耗'!$B$%d,0)" % (MFG_ON_ROW, MFG_TOT_ROW))
c.font = F_NUMB; c.fill = FILL_OUT; c.number_format = '#,##0.00'
for col in range(1, 10):
    ws2.cell(row=r, column=col).border = BOX
SUM_ROWS['制造'] = r
r += 1
ws2.cell(row=r, column=1, value='总制成成本').font = Font(name='Microsoft YaHei', size=11, bold=True, color='9A3412')
ws2.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
c = ws2.cell(row=r, column=7, value='=G%d-G%d+G%d+G%d' % (SUM_ROWS['原料'], BYP2, SUM_ROWS['能源'], SUM_ROWS['辅料']) + '+G%d' % SUM_ROWS['制造'])
c.font = F_NUMB; c.fill = FILL_SEC; c.number_format = '#,##0.00'
for col in range(1, 10):
    ws2.cell(row=r, column=col).border = BOX
TOTAL2 = r
# 占总成本列（回填）
for i in range(len(E.DEFAULT['inputs'])):
    rr = FIRST2 + i
    c = ws2.cell(row=rr, column=9, value='=IF($G$%d=0,"—",G%d/$G$%d)' % (TOTAL2, rr, TOTAL2))
    c.font = F_NUM; c.number_format = '0.00%'
ws2.freeze_panes = 'A5'

# ====================================================== 03_加工价差与利润
ws3 = wb.create_sheet('03_加工价差与利润')
banner(ws3, '03 三层指标：加工价差 / 制造利润 / 企业实际利润（不输出）',
       '严格分离。① 价差只扣原料；② 利润再扣能源辅料制造；③ 企业实际利润需内部数据，本表留空并说明原因。', 6)
r = 4
rows3 = [
    ('产品含税售价  P', "='01_参数与单耗'!$B$%d" % PROD_ROW, '元/吨', '生意社 PVC(SG-5) 现货基准价', 'in'),
    ('① 原料成本（含收率修正）', "='02_成本构成'!$G$%d" % SUM_ROWS['原料'], '元/吨', '逐项见 02 表', 'out'),
    ('①b 联产烧碱抵减', "=-'02_成本构成'!$G$%d" % BYP2, '元/吨', '仅在"是否计入"填是时生效', 'out'),
    ('② 理论加工价差  = P − ① (+①b)', None, '元/吨', '★ 本指标只反映原料→产品的转换价差', 'key'),
    ('③ 能源成本', "='02_成本构成'!$G$%d" % SUM_ROWS['能源'], '元/吨', '电 + 汽', 'out'),
    ('④ 辅料成本', "='02_成本构成'!$G$%d" % SUM_ROWS['辅料'], '元/吨', 'HCl + 触媒 + 助剂', 'out'),
    ('⑤ 制造费用', "='02_成本构成'!$G$%d" % SUM_ROWS['制造'], '元/吨', '折旧+人工+包装+其他', 'out'),
    ('⑥ 理论制造利润 = ② − ③④⑤', None, '元/吨', '★ 仍不是企业净利润', 'key'),
    ('理论总制成成本（不含产品价）', "='02_成本构成'!$G$%d" % TOTAL2, '元/吨', '= ①+①b+③+④+⑤', 'out'),
    ('理论销售利润率', None, '%', '= ⑥ ÷ P', 'out'),
    ('', '', '', '', ''),
    ('⑦ 企业实际利润', '（不输出）', '元/吨', '需财务费用、销售物流、税费、检修损失、区域价差等内部数据；缺可核实来源则不编造。', 'gap'),
]
header(ws3, r, ['指标', '数值', '单位', '口径说明'], [40, 18, 10, 74])
r += 1
R3 = {}
for lab, f, unit, note, kind in rows3:
    if not lab:
        r += 1
        continue
    ws3.cell(row=r, column=1, value=lab).font = F_B if kind != 'out' else F_N
    c = ws3.cell(row=r, column=2)
    if f and f.startswith('='):
        c.value = f
    elif f:
        c.value = f
    c.number_format = '0.0%' if unit == '%' else '#,##0.00'
    if kind == 'key':
        c.font = Font(name='Consolas', size=13, bold=True, color='1D4ED8')
        c.fill = FILL_SEC
    elif kind == 'gap':
        c.font = Font(name='Microsoft YaHei', size=10, italic=True, color='B91C1C')
        c.fill = FILL_BAD
    else:
        c.font = F_NUMB
        c.fill = FILL_OUT
    ws3.cell(row=r, column=3, value=unit).font = F_S
    cc = ws3.cell(row=r, column=4, value=note)
    cc.font = F_S
    cc.alignment = Alignment(wrap_text=True, vertical='center')
    for col in range(1, 5):
        ws3.cell(row=r, column=col).border = BOX
    R3.setdefault(lab[:1], r)
    R3.setdefault(lab[:1] if lab[:1] in '①②③④⑤⑥⑦' else lab[:6], r)
    R3['name:' + lab.split('  ')[0].strip()] = r
    ws3.row_dimensions[r].height = 34 if kind == 'gap' else 22
    r += 1
# 公式填充（用显式行号，避免相对偏移错位）
r_prod, r_raw, r_byp = R3['name:产品含税售价'], R3['name:① 原料成本（含收率修正）'], R3['name:①b 联产烧碱抵减']
r_spread = R3['②']
r_energy = R3['③']
r_aux = R3['④']
r_mfg = R3['⑤']
r_profit = R3['⑥']
ws3.cell(row=r_spread, column=2, value='=B%d-B%d-B%d' % (r_prod, r_raw, r_byp))
ws3.cell(row=r_spread, column=2).number_format = '#,##0.00'
ws3.cell(row=r_spread, column=2).font = Font(name='Consolas', size=13, bold=True, color='1D4ED8')
ws3.cell(row=r_spread, column=2).fill = FILL_SEC
ws3.cell(row=r_profit, column=2, value='=B%d-B%d-B%d-B%d' % (r_spread, r_energy, r_aux, r_mfg))
ws3.cell(row=r_profit, column=2).number_format = '#,##0.00'
ws3.cell(row=r_profit, column=2).font = Font(name='Consolas', size=13, bold=True, color='1D4ED8')
ws3.cell(row=r_profit, column=2).fill = FILL_SEC
ws3.cell(row=r_profit + 2, column=2, value='=IF(B%d=0,0,B%d/B%d)' % (r_prod, r_profit, r_prod))
ws3.cell(row=r_profit + 2, column=2).number_format = '0.00%'
ws3.cell(row=r_profit + 2, column=2).font = F_NUMB
ws3.cell(row=r_profit + 2, column=2).fill = FILL_OUT

r = r_profit + 4
section(ws3, r, '为什么不能把②或⑥叫“企业净利润”', 4)
r += 1
for t in ['② 加工价差 不扣除电价、汽价、催化剂、人工、折旧、包装——它只是"买原料、卖产品"的价格差。',
          '⑥ 理论制造利润 扣的是"能核实的制造环节费用"，仍未扣财务费用（利息）、销售费用与物流、增值税进销差、检修与开停车损失、环保处置、所得税。',
          '⑦ 企业实际利润 只有拿到该企业的成本表、费用表与销售价格才能算；用行业均价反推"某企业赚了多少"是最常见的错误用法。',
          '本模型对 ⑦ 的态度是：明确留空 + 说明缺什么数据，而不是给一个看起来精确的数字。']:
    ws3.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    c = ws3.cell(row=r, column=1, value='· ' + t)
    c.font = F_N
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws3.row_dimensions[r].height = 30
    r += 1

# ====================================================== 04_历史价格
ws4 = wb.create_sheet('04_历史价格')
banner(ws4, '04 近 1 年价格序列（2025-10-20 ～ 2026-10-19，242 个交易日）',
       'PVC 价格：有现货用现货(spot)，否则用期货主力收盘+平均基差(proxy)。电石：有现货用现货，否则锚点插值(interp)。空白=无可靠价格。', 12)
r = 4
header(ws4, r, ['日期', 'PVC 现货', 'PVC 期货收盘', 'PVC 期货结算', 'PVC 采用价', '价格类型',
                '电石到厂价', '电石类型', '电石锚点说明', '理论加工价差', '理论制造利润', '烧碱价格'],
       [12, 11, 12, 12, 11, 11, 12, 11, 34, 13, 13, 11])
r += 1
FIRST4 = r
for rec in HIST['history']:
    ws4.cell(row=r, column=1, value=rec['date']).font = F_NUM
    ws4.cell(row=r, column=2, value=rec.get('pvc_spot'))
    ws4.cell(row=r, column=3, value=rec.get('fut_close'))
    ws4.cell(row=r, column=4, value=rec.get('fut_settle'))
    ws4.cell(row=r, column=5, value=rec['pvc'])
    ws4.cell(row=r, column=6, value='现货' if rec['pvc_src'] == 'spot' else '期货代理')
    ws4.cell(row=r, column=7, value=rec['carbide'])
    ws4.cell(row=r, column=8, value={'spot': '现货', 'anchor': '锚点', 'interp': '插值'}.get(rec['carbide_src'] or '', ''))
    ws4.cell(row=r, column=9, value=rec.get('carbide_note', ''))
    ws4.cell(row=r, column=10, value=rec['spread'])
    ws4.cell(row=r, column=11, value=rec['profit'])
    ws4.cell(row=r, column=12, value=rec.get('naoh'))
    for col in range(1, 13):
        c = ws4.cell(row=r, column=col)
        c.border = BOX
        if col in (2, 3, 4, 5, 7, 10, 11, 12):
            c.font = F_NUM
            c.number_format = '#,##0.00'
        else:
            c.font = F_S
    if rec['carbide_src'] in ('anchor', 'interp'):
        for col in (7, 8, 9):
            ws4.cell(row=r, column=col).fill = PatternFill('solid', fgColor='FEF9C3')
    r += 1
LAST4 = r - 1

r += 1
section(ws4, r, '电石价格锚点（仅使用文章明确披露的报价，锚点之间线性插值）', 12)
r += 1
header(ws4, r, ['日期', '乌海电石 元/吨', '原文表述', '', '', '', '来源', '', '', '', '', ''])
r += 1
for a in sorted(ANCH, key=lambda x: x['date']):
    ws4.cell(row=r, column=1, value=a['date']).font = F_NUM
    c = ws4.cell(row=r, column=2, value=a['price']); c.font = F_NUMB; c.number_format = '#,##0'
    ws4.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    ws4.cell(row=r, column=3, value=a['quote']).font = F_S
    ws4.merge_cells(start_row=r, start_column=7, end_row=r, end_column=12)
    ws4.cell(row=r, column=7, value=a['source']).font = F_S
    r += 1
ws4.freeze_panes = 'A5'

# 图表
ch = LineChart()
ch.title = 'PVC 采用价 与 理论加工价差'
ch.height = 9
ch.width = 24
data = Reference(ws4, min_col=5, min_row=4, max_row=LAST4)
data2 = Reference(ws4, min_col=10, min_row=4, max_row=LAST4)
cats = Reference(ws4, min_col=1, min_row=FIRST4, max_row=LAST4)
ch.add_data(data, titles_from_data=True)
ch.add_data(data2, titles_from_data=True)
ch.set_categories(cats)
ws4.add_chart(ch, 'N4')

# ====================================================== 05_月度台账
ws5 = wb.create_sheet('05_月度台账')
banner(ws5, '05 月度台账：理论结果 vs 隆众资讯（第三方）',
       '第三列为第三方口径（含全部制造成本），不是同一指标；差值用于校验方向与量级，不能直接相减当误差。', 12)
r = 4
header(ws5, r, ['月份', '交易日数', 'PVC 采用均价', '电石均价', '理论原料成本', '理论加工价差', '理论制造利润',
                '隆众成本(全国)', '隆众毛利(全国)', '偏差(理论利润−隆众毛利)', '价格来源', '方向是否一致'],
       [10, 10, 13, 12, 14, 13, 13, 14, 14, 20, 14, 12])
r += 1
FIRST5 = r
for m in HIST['monthly']:
    ws5.cell(row=r, column=1, value=m['month']).font = F_B
    ws5.cell(row=r, column=2, value=m['n_days']).font = F_NUM
    for col, key in [(3, 'pvc'), (4, 'carbide'), (5, 'raw_cost'), (6, 'spread'), (7, 'profit'),
                     (8, 'ms_cost_nat'), (9, 'ms_profit_nat')]:
        c = ws5.cell(row=r, column=col, value=m.get(key))
        c.font = F_NUM
        c.number_format = '#,##0.0'
    c = ws5.cell(row=r, column=10,
                 value='=IF(OR(G%d="",I%d=""),"",G%d-I%d)' % (r, r, r, r))
    c.font = F_NUMB
    c.number_format = '#,##0.0'
    c = ws5.cell(row=r, column=11, value={'spot': '现货', 'proxy': '期货代理+锚点', 'proxy+spot': '混合'}.get(m.get('src') or '', '无电石价'))
    c.font = F_S
    c = ws5.cell(row=r, column=12, value='=IF(OR(G%d="",I%d=""),"—",IF(SIGN(G%d)=SIGN(I%d),"一致","背离"))' % (r, r, r, r))
    c.font = F_S
    for col in range(1, 13):
        ws5.cell(row=r, column=col).border = BOX
    r += 1
LAST5 = r - 1
r += 1
ws5.cell(row=r, column=1, value='汇总').font = F_B
ws5.cell(row=r, column=2, value='=COUNT(J%d:J%d)' % (FIRST5, LAST5)).font = F_NUMB
ws5.cell(row=r, column=6, value='平均偏差').font = F_S
c = ws5.cell(row=r, column=7, value='=IFERROR(AVERAGE(J%d:J%d),"")' % (FIRST5, LAST5))
c.font = F_NUMB; c.number_format = '#,##0.0'
ws5.cell(row=r, column=8, value='平均绝对偏差').font = F_S
c = ws5.cell(row=r, column=9, value='=IFERROR(AVERAGE(ABS(J%d:J%d)),"")' % (FIRST5, LAST5))
c.font = F_NUMB; c.number_format = '#,##0.0'
ws5.cell(row=r, column=11, value='方向一致月数').font = F_S
c = ws5.cell(row=r, column=12, value='=COUNTIF(L%d:L%d,"一致")' % (FIRST5, LAST5))
c.font = F_NUMB

# ====================================================== 06_周度校验
ws6 = wb.create_sheet('06_周度校验')
banner(ws6, '06 周度校验：理论制造利润 vs 隆众全国电石法 PVC 毛利（40 周）',
       '核心可用性指标是"方向一致率"，不是绝对误差——两者口径不同（第三方含全部制造成本、样本为特定期企业）。', 8)
r = 4
header(ws6, r, ['周报日期', '对应交易日数', '理论制造利润', '隆众毛利', '偏差', '绝对偏差', '方向一致', '备注'],
       [13, 13, 14, 12, 11, 11, 11, 30])
r += 1
FIRST6 = r
for w in HIST['week_validation']['weeks']:
    ws6.cell(row=r, column=1, value=w['date']).font = F_NUM
    ws6.cell(row=r, column=2, value=w['n_days']).font = F_NUM
    c = ws6.cell(row=r, column=3, value=w['theory']); c.font = F_NUM; c.number_format = '#,##0.0'
    c = ws6.cell(row=r, column=4, value=w['mysteel']); c.font = F_NUM; c.number_format = '#,##0.0'
    c = ws6.cell(row=r, column=5, value='=C%d-D%d' % (r, r)); c.font = F_NUMB; c.number_format = '#,##0.0'
    c = ws6.cell(row=r, column=6, value='=ABS(E%d)' % r); c.font = F_NUM; c.number_format = '#,##0.0'
    c = ws6.cell(row=r, column=7, value='=IF(SIGN(C%d)=SIGN(D%d),"一致","背离")' % (r, r)); c.font = F_S
    for col in range(1, 9):
        ws6.cell(row=r, column=col).border = BOX
    r += 1
LAST6 = r - 1
r += 1
agg = HIST['week_validation']['agg']
stats = [('样本周数', '=COUNT(E%d:E%d)' % (FIRST6, LAST6), '0'),
         ('偏差均值', '=AVERAGE(E%d:E%d)' % (FIRST6, LAST6), '#,##0.0'),
         ('平均绝对偏差', '=AVERAGE(F%d:F%d)' % (FIRST6, LAST6), '#,##0.0'),
         ('偏差标准差', '=STDEV(E%d:E%d)' % (FIRST6, LAST6), '#,##0.0'),
         ('最大正偏差', '=MAX(E%d:E%d)' % (FIRST6, LAST6), '#,##0.0'),
         ('最大负偏差', '=MIN(E%d:E%d)' % (FIRST6, LAST6), '#,##0.0'),
         ('方向一致周数', '=COUNTIF(G%d:G%d,"一致")' % (FIRST6, LAST6), '0'),
         ('方向一致率', '=G%d/B%d' % (r + 7, r), '0.0%')]
header(ws6, r, ['统计口径', '数值', '说明'], [18, 14, 60])
r += 1
for lab, f, nf in stats:
    ws6.cell(row=r, column=1, value=lab).font = F_B
    c = ws6.cell(row=r, column=2, value=f); c.font = F_NUMB; c.number_format = nf; c.fill = FILL_OUT
    ws6.cell(row=r, column=1).border = BOX
    ws6.cell(row=r, column=2).border = BOX
    r += 1
ws6.cell(row=r - 8, column=3, value='理论利润与第三方毛利方向是否一致').font = F_S
ws6.cell(row=r - 1, column=3, value='≥85% 可认为模型可用于方向判断（当前 37/40=92.5%）').font = F_S
ws6.freeze_panes = 'A5'

# ====================================================== 07_敏感性分析
ws7 = wb.create_sheet('07_敏感性分析')
banner(ws7, '07 敏感性分析（双因素矩阵为活公式，随 01 表联动）',
       '行=电石价格变动，列=产品价格变动。变动比例写在 B4:F4 / A6:A10，改这里重算全部矩阵。', 8)
steps = [-0.10, -0.05, 0.0, 0.05, 0.10]
r = 4
ws7.cell(row=r, column=1, value='电石＼产品').font = F_H
ws7.cell(row=r, column=1).fill = FILL_H
for j, s in enumerate(steps):
    c = ws7.cell(row=r, column=2 + j, value=s)
    c.font = F_IN; c.fill = FILL_IN; c.number_format = '+0%;-0%;0%'
    c.alignment = Alignment(horizontal='center')
    c.border = BOX
ws7.cell(row=r, column=1).border = BOX
r += 1
MAT_TOP = r
for i, s in enumerate(steps):
    c = ws7.cell(row=r, column=1, value=s)
    c.font = F_IN; c.fill = FILL_IN; c.number_format = '+0%;-0%;0%'
    c.border = BOX
    for j in range(len(steps)):
        ws7.cell(row=r, column=2 + j).border = BOX
    r += 1
MAT_BOT = r - 1

r += 1
ws7.cell(row=r, column=1, value='矩阵①：理论加工价差（元/吨）').font = Font(name='Microsoft YaHei', size=11, bold=True, color='1D4ED8')
r += 1
header(ws7, r, ['电石＼产品'] + ['%+d%%' % (s * 100) for s in steps], [14, 12, 12, 12, 12, 12])
r += 1
SP_TOP = r
cac2 = [x for x in E.DEFAULT['inputs'] if x['id'] == 'cac2'][0]
for i, s in enumerate(steps):
    ws7.cell(row=r, column=1, value='=$A$%d' % (MAT_TOP + i)).font = F_NUM
    ws7.cell(row=r, column=1).number_format = '+0%;-0%;0%'
    for j in range(len(steps)):
        col = get_column_letter(2 + j)
        f = ("='03_加工价差与利润'!$B$%d-('01_参数与单耗'!$C$%d*'01_参数与单耗'!$E$%d*"
             "'01_参数与单耗'!$G$%d*(1+$A%d)/'01_参数与单耗'!$B$%d)"
             ) % (R3['①'], FIRST_IN, FIRST_IN, FIRST_IN, r, YLD_ROW)
        # 价差 = 产品价*(1+列变动) - 电石单耗*系数*单价*(1+行变动)/收率
        # 价差 = 产品价*(1+列变动) − 电石单耗*系数*单价*(1+行变动)/收率 − 其他原料(不含电石)
        f = ("='01_参数与单耗'!$B$%d*(1+%s$%d)-('01_参数与单耗'!$C$%d*'01_参数与单耗'!$E$%d*"
             "'01_参数与单耗'!$G$%d*(1+$A%d)/'01_参数与单耗'!$B$%d)"
             "-('02_成本构成'!$G$%d-'02_成本构成'!$G$%d)"
             ) % (PROD_ROW, col, MAT_TOP - 1, FIRST_IN, FIRST_IN, FIRST_IN, r, YLD_ROW,
                  SUM_ROWS['原料'], FIRST2)
        c = ws7.cell(row=r, column=2 + j, value=f)
        c.font = F_NUMB; c.number_format = '#,##0.0'; c.border = BOX
    r += 1
SP_BOT = r - 1

r += 1
ws7.cell(row=r, column=1, value='矩阵②：理论制造利润（元/吨）= 矩阵① − 能源 − 辅料 − 制造费用').font = Font(name='Microsoft YaHei', size=11, bold=True, color='1D4ED8')
r += 1
header(ws7, r, ['电石＼产品'] + ['%+d%%' % (s * 100) for s in steps], [14, 12, 12, 12, 12, 12])
r += 1
PF_TOP = r
fixed = "('02_成本构成'!$G$%d+'02_成本构成'!$G$%d+'02_成本构成'!$G$%d)" % (SUM_ROWS['能源'], SUM_ROWS['辅料'], SUM_ROWS['制造'])
for i, s in enumerate(steps):
    ws7.cell(row=r, column=1, value='=$A$%d' % (MAT_TOP + i)).font = F_NUM
    ws7.cell(row=r, column=1).number_format = '+0%;-0%;0%'
    for j in range(len(steps)):
        col = get_column_letter(2 + j)
        c = ws7.cell(row=r, column=2 + j, value='=%s%d-%s' % (get_column_letter(2 + j), SP_TOP + i, fixed))
        c.font = F_NUMB; c.number_format = '#,##0.0'; c.border = BOX
    r += 1
PF_BOT = r - 1

r += 2
section(ws7, r, '单因素敏感性：各物料价格 ±5% / ±10% 对利润的影响（元/吨）', 8)
r += 1
header(ws7, r, ['物料', '-10%', '-5%', '+5%', '+10%', '弹性(±10%均价)', '当前成本'], [24, 12, 12, 12, 12, 16, 12])
r += 1
base_r = E.compute()
for i, it in enumerate(E.DEFAULT['inputs']):
    src = FIRST_IN + i
    unit_cost = base_r['breakdown'][i]['cost']
    if unit_cost <= 0.01:
        continue
    ws7.cell(row=r, column=1, value=it['name']).font = F_N
    for j, mult in enumerate([-0.10, -0.05, 0.05, 0.10]):
        c = ws7.cell(row=r, column=2 + j, value='=ROUND(-%s*%s,2)' % ('$G$%d' % (FIRST_IN + i), str(mult + 1)))
        c.font = F_NUM; c.number_format = '#,##0.0'
        c.border = BOX
    c = ws7.cell(row=r, column=7, value='=ROUND(((E%d-D%d)/2),1)' % (r, r))
    c.font = F_NUMB; c.number_format = '#,##0.0'
    c = ws7.cell(row=r, column=8, value='=%s*%s*%s' % ('$C$%d' % src, '$E$%d' % src, '$G$%d' % src))
    c.font = F_NUM; c.number_format = '#,##0.0'
    r += 1

r += 1
section(ws7, r, '盈亏平衡：使理论制造利润 = 0 所需的 PVC 售价（元/吨）', 8)
r += 1
header(ws7, r, ['电石价格变动', '-10%', '-5%', '基准', '+5%', '+10%'], [16, 12, 12, 12, 12, 12])
r += 1
ws7.cell(row=r, column=1, value='PVC 需售价').font = F_B
for j, s in enumerate(steps):
    cac2c = "('01_参数与单耗'!$C$%d*'01_参数与单耗'!$E$%d*'01_参数与单耗'!$G$%d*(1+%s)/'01_参数与单耗'!$B$%d)" % (
        FIRST_IN, FIRST_IN, FIRST_IN, ('%.2f' % s), YLD_ROW)
    f = '=ROUND(%s+%s,0)' % (cac2c, fixed)
    c = ws7.cell(row=r, column=2 + j, value=f)
    c.font = F_NUMB; c.number_format = '#,##0'
    c.fill = FILL_SEC
    c.border = BOX
ws7.cell(row=r, column=1).border = BOX

# ====================================================== 08_公式与来源
ws8 = wb.create_sheet('08_公式与来源')
banner(ws8, '08 公式与来源（每个数字都可追溯）', '左：公式文字化展开；右：数据来源与口径。审阅他人模型时，先看这一页。', 6)
r = 4
section(ws8, r, 'A. 公式展开（与 Excel 单元格公式一一对应）', 6)
r += 1
header(ws8, r, ['指标', '公式', '单位', 'Excel 位置'], [22, 66, 10, 22])
r += 1
formulas = [
    ('计费单耗', '名义单耗 × 换算系数 ÷ 综合收率（能源不除收率）', 't 或 kWh', '02!E 列'),
    ('单位成本', '计费单耗 × 单价', '元/吨', '02!G 列'),
    ('原料成本', 'Σ 电石与原料项单位成本', '元/吨', '02!原料小计'),
    ('能源成本', '电耗 × 电价 + 汽耗 × 汽价', '元/吨', '02!能源小计'),
    ('辅料成本', 'Σ (辅料单耗 ÷ 收率 × 单价)', '元/吨', '02!辅料小计'),
    ('制造费用', '折旧 + 人工 + 包装 + 其他', '元/吨', '01!B 合计'),
    ('理论加工价差', '产品含税价 − 原料成本 − 联产抵减', '元/吨', '03!②'),
    ('理论制造利润', '加工价差 − 能源 − 辅料 − 制造费用', '元/吨', '03!⑥'),
    ('弹性（电石）', '单耗 ÷ 收率 × 单价 × 变动幅度', '元/吨', '07!单因素'),
    ('盈亏平衡价', '电石成本(受冲击后) + 能源 + 辅料 + 制造费用', '元/吨', '07!平衡价'),
]
for f in formulas:
    for j, v in enumerate(f, start=1):
        c = ws8.cell(row=r, column=j, value=v)
        c.font = F_B if j == 1 else F_N
        c.alignment = Alignment(wrap_text=True, vertical='center')
        c.border = BOX
    r += 1

r += 1
section(ws8, r, 'B. 单耗与工艺来源（多源并列，注明适用工艺，绝不混用）', 6)
r += 1
header(ws8, r, ['指标', '取值', '来源', '适用工艺口径', '文献链接/出处'], [20, 16, 34, 26, 46])
r += 1
dose = [
    ('电石 CaC₂', '1.45 t/t', '国标口径（前瞻产业研究院 / 新浪财经引国家标准）', '外购电石，PVC 装置本级', 'https://finance.sina.com.cn/ 2022-01-17'),
    ('电石 CaC₂', '1.35–1.42 t/t', '隆众资讯 行业统计标准', '外购电石，行业统计', 'https://www.mysteel.com/oilchem/ 2024-12-17'),
    ('电石 CaC₂', '1.40–1.60 t/t', '中国化工网', '外购电石，较宽区间', 'https://www.chemnet.com/'),
    ('氯化氢 HCl', '0.72 t/t（630–850 kg 区间）', '国标 750–850 kg；隆众 630–650 kg', '气体计价，氯碱配套', '—'),
    ('PVC 装置电耗', '450–500 kWh/t', '国标口径', '外购电石企业，装置本级', '—'),
    ('综合电耗（全链）', '≈8500 kWh/t', '中国化工报 2025-11-05', '一体化全链，含电石环节', 'https://www.ccin.com.cn/'),
    ('电石电耗', '3400–3600 kWh/t 电石', '联成化学（台塑）公开资料', '电石厂', '—'),
    ('汞触媒', '1.2 kg/t PVC', '专利 CN103408392A', '低汞触媒', '—'),
    ('综合收率', '97%', '行业 96–98%', '悬浮聚合', '—'),
]
for d in dose:
    for j, v in enumerate(d, start=1):
        c = ws8.cell(row=r, column=j, value=v)
        c.font = F_S if j != 2 else F_NUMB
        c.alignment = Alignment(wrap_text=True, vertical='top')
        c.border = BOX
    ws8.row_dimensions[r].height = 28
    r += 1

r += 1
section(ws8, r, 'C. 价格来源（品种 / 地区 / 规格 / 税费 / 频率）', 6)
r += 1
header(ws8, r, ['序列', '来源', '地区与规格', '单位与税费', '区间', '链接'], [18, 22, 24, 18, 22, 44])
r += 1
prices = [
    ('PVC 现货', '生意社基准价', '中国综合，SG-5 型', '元/吨，含税', '近 93 天', 'https://www.100ppi.com/'),
    ('电石', '生意社基准价', '宁夏/内蒙古，出厂折算', '元/吨，含税', '近 93 天', 'https://www.100ppi.com/'),
    ('液碱 32%', '生意社基准价', '华东', '元/吨，含税', '近 93 天', 'https://www.100ppi.com/'),
    ('PVC 期货', '新浪财经 主力连续 V0', '大连商品交易所', '元/吨，含税', '2025-10-20～2026-10-19', 'https://finance.sina.com.cn/futures/quotes/V0.shtml'),
    ('电石（早期）', '文章披露锚点+线性插值', '乌海主流贸易价', '元/吨', '2026-01～2026-09', '见 04 表锚点清单'),
    ('成本与毛利', '隆众资讯 周报（40 期）', '全国/西北/山东 电石法', '元/吨', '2026-01-09～2026-10-16', 'https://www.mysteel.com/oilchem/article/3yb4pa/'),
]
for p_ in prices:
    for j, v in enumerate(p_, start=1):
        c = ws8.cell(row=r, column=j, value=v)
        c.font = F_S
        c.alignment = Alignment(wrap_text=True, vertical='top')
        c.border = BOX
    r += 1

r += 1
section(ws8, r, 'D. 已知局限（写清楚，比装作没有更好）', 6)
r += 1
for t in ['电石日价历史仅约 93 天，更早区间用 6 个已披露锚点线性插值，不能当成真实日价。',
          'PVC 现货早于 93 天用"期货主力收盘 + 平均基差 −119.7 元/吨"代理，属推断值，已在 04 表标注。',
          '电价、汽价、触媒/助剂单价为截面典型值，未随时间变动；企业应替换为自身结算价。',
          '本模型为全国基准，未体现区域价差（乌海 vs 山东电石到厂价差可达 400–600 元/吨）。',
          'HCl 按"自产氯成本"估值 380 元/吨；若改按液氯市价折入（≈1000 元/吨 HCl），HCl 占比升至约 13%（与文献 14–15% 吻合），但理论利润将再降约 390 元/吨。']:
    ws8.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    c = ws8.cell(row=r, column=1, value='· ' + t)
    c.font = F_N
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws8.row_dimensions[r].height = 28
    r += 1

for s in wb.worksheets:
    s.sheet_view.showGridLines = False
    s.page_setup.orientation = 'landscape'
    s.page_setup.fitToWidth = 1

os.makedirs(os.path.join(ROOT, 'output'), exist_ok=True)
out = os.path.join(ROOT, 'output', 'PVC电石法-产业链利润模型.xlsx')
wb.save(out)
print('[OK] %s  %.1f KB' % (out, os.path.getsize(out) / 1024))
print('sheets:', [s.title for s in wb.worksheets])

