# -*- coding: utf-8 -*-
"""生成 Excel 工作簿（openpyxl 写入原生公式；构建后用 LibreOffice 重算并校验）。

为避免跨表定义名称在部分引擎下解析失败，本脚本把所有公式写成显式跨表引用
（如 '04 变换后数据'!$D$5:$D$160），保证 Excel / WPS / LibreOffice 都能重算。

表结构：
 00 说明与使用指南 / 01 口径与来源 / 02 原始数据 / 03 频率对齐 / 04 变换后数据
 05 总体相关 / 06 滚动相关(12/26/52) / 07 分阶段结果 / 08 形态组合矩阵
 09 稳健性与伪相关诊断 / 09b 辅助计算(残差) / 10 滞后相关 / 11 事件与口径提示 / 12 公式说明
"""
from __future__ import annotations

import csv
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import corrlib as C  # noqa: E402
from events import EVENTS  # noqa: E402

DATA_CSV = os.path.join(ROOT, 'data', 'demo_methanol_weekly.csv')
META_JSON = os.path.join(ROOT, 'data', 'data_meta.json')
OUT = os.path.join(ROOT, 'docs', 'two-indicator-correlation-workbook.xlsx')

# 可选：用 --csv 指定其他数据（列名需为 week_ending / inventory_total / inventory_ec /
# inventory_sc / spot_taicang / coal_5500 / op_rate / arrival / demand）
for _i, _a in enumerate(sys.argv):
    if _a == '--csv' and _i + 1 < len(sys.argv):
        DATA_CSV = os.path.abspath(sys.argv[_i + 1])
    if _a == '--out' and _i + 1 < len(sys.argv):
        OUT = os.path.abspath(sys.argv[_i + 1])

NAVY, BLUE, LIGHT, LIGHT2, DEMO, WARN = '1F3B57', '2E6DA4', 'EAF1F8', 'F5F8FB', 'FCE8D5', 'FFF3CD'
THIN = Side(style='thin', color='C9D6E3')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
H_FONT = Font(name='微软雅黑', size=10, bold=True, color='FFFFFF')
B_FONT = Font(name='微软雅黑', size=10)
TITLE_FONT = Font(name='微软雅黑', size=14, bold=True, color=NAVY)
SUB_FONT = Font(name='微软雅黑', size=9, color='6B7B8C')


def style_header(ws, row, ncol, fill=BLUE, height=24):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = H_FONT
        cell.fill = PatternFill('solid', fgColor=fill)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = height


def style_body(ws, r1, r2, ncol, numfmt=None, wrap_cols=()):
    for r in range(r1, r2 + 1):
        for c in range(1, ncol + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = B_FONT
            cell.border = BORDER
            if c in wrap_cols:
                cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal='center', vertical='center')
            if numfmt and isinstance(cell.value, (int, float)):
                cell.number_format = numfmt


def title_block(ws, title, sub, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=title)
    c.font = TITLE_FONT
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[1].height = 26
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c2 = ws.cell(row=2, column=1, value=sub)
    c2.font = SUB_FONT
    c2.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    ws.row_dimensions[2].height = 34


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def load():
    rows = list(csv.DictReader(open(DATA_CSV, encoding='utf-8-sig')))
    meta = json.load(open(META_JSON, encoding='utf-8'))
    return rows, meta


def main():
    rows, meta = load()
    n = len(rows)
    dates = [r['week_ending'] for r in rows]
    inv = [float(r['inventory_total']) for r in rows]
    price = [float(r['spot_taicang']) for r in rows]
    last = 4 + n          # 数据区最后一行

    # 显式跨表区域（避免定义名称在部分引擎中解析失败）
    R_INV = f"'04 变换后数据'!$C$5:$C${last}"
    R_DIF = f"'04 变换后数据'!$D$5:$D${last}"
    R_PCT = f"'04 变换后数据'!$E$5:$E${last}"
    R_PLV = f"'04 变换后数据'!$F$5:$F${last}"
    R_PDF = f"'04 变换后数据'!$G$5:$G${last}"
    R_PPC = f"'04 变换后数据'!$H$5:$H${last}"
    R_DAT = f"'04 变换后数据'!$B$5:$B${last}"
    R_TS = f"'09b 辅助计算(残差)'!$C$5:$C${last}"

    wb = Workbook()

    # ============================================ 00 说明
    ws = wb.active
    ws.title = '00 说明与使用指南'
    widths(ws, {'A': 3, 'B': 26, 'C': 118})
    title_block(ws, '两指标相关性研究工作簿｜甲醇港口库存 × 太仓现货价',
                '示例数据为按真实行业口径拟真的 DEMO 数据（见“01 口径与来源”）。把真实历史数据贴进“02 原始数据”，本工作簿所有公式自动重算。', 3)
    guide = [
        ('这份工作簿解决什么', '回答“两个指标到底相不相关、在什么条件下相关、这个相关是否可信”。不回答“买还是卖”，也不给因果结论。'),
        ('第 1 步 输入数据', '在“02 原始数据”替换 B/C/D/G 列（观测日、价格锚日、库存、价格）。缺失就留空或用 =NA()，绝不插值补数。'),
        ('第 2 步 核对口径', '“01 口径与来源”逐项填全：单位、频率、区域、样本口径、发布时点、来源。任一项缺失，结论不可对外引用。'),
        ('第 3 步 频率对齐', '“03 频率对齐”标出每期配对状态（成功/缺失-剔除），并给出有效配对 N 与缺失期数。'),
        ('第 4 步 变换', '“04 变换后数据”把库存/价格分别做成 水平、差分、环比%。库存常看变化，价格常看变化率。'),
        ('第 5 步 读结果', '“05 总体相关”给 5 种形态组合的 r/N/R²/t/p/判定；“06 滚动相关”看强度随时间变化；“07 分阶段”按业务阶段重算。'),
        ('第 6 步 查伪相关', '“09 稳健性与伪相关诊断”+“09b 辅助计算(残差)”：去趋势、差分、剔极值、分段、偏相关；自相关强时用有效样本量修正。'),
        ('第 7 步 写结论', '结论必须带口径、形态、时间段、N、显著性、稳健性；禁止把相关性写成因果，禁止输出交易建议。'),
        ('公式透明', '“12 公式说明”逐条给出公式定义与 Excel 写法，全部可在表内复核（无宏、无加载项）。'),
    ]
    r0 = 4
    for i, (k, v) in enumerate(guide):
        r = r0 + i
        c = ws.cell(row=r, column=2, value=k)
        c.font = Font(name='微软雅黑', size=10, bold=True, color=NAVY)
        c.fill = PatternFill('solid', fgColor=LIGHT)
        c.alignment = Alignment(vertical='top', wrap_text=True)
        c.border = BORDER
        c2 = ws.cell(row=r, column=3, value=v)
        c2.font = B_FONT
        c2.alignment = Alignment(vertical='top', wrap_text=True)
        c2.border = BORDER
        ws.row_dimensions[r].height = 34
    r = r0 + len(guide) + 1
    ws.cell(row=r, column=2, value='⚠ 重要声明').font = Font(name='微软雅黑', size=10, bold=True, color='C0392B')
    c = ws.cell(row=r, column=3, value='相关性不等于因果关系；滚动相关只描述历史窗口内的共变强度，不外推未来；本工作簿不提供任何交易建议或价格预测。')
    c.font = B_FONT
    c.fill = PatternFill('solid', fgColor=WARN)
    c.alignment = Alignment(vertical='top', wrap_text=True)
    c.border = BORDER
    ws.row_dimensions[r].height = 32
    ws.sheet_view.showGridLines = False

    # ============================================ 01 口径
    ws = wb.create_sheet('01 口径与来源')
    widths(ws, {'A': 3, 'B': 16, 'C': 30, 'D': 12, 'E': 14, 'F': 22, 'G': 24, 'H': 38, 'I': 34})
    title_block(ws, '口径与来源（数据可否引用的前提）',
                '每列都要有值。任一项写“待确认”，对应结论只能当探索性提示。', 9)
    hdr = ['', '指标', '指标全称', '单位', '频率', '统计区域/样本', '发布时点（口径）', '来源与链接', '备注（口径风险）']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 9)
    dm = meta['demo']
    spec = [
        ['', '指标 X（库存）', dm['inventory']['name'], dm['inventory']['unit'], '周度',
         dm['inventory']['region'], '调查日=每周三，机构当日或次日发布',
         dm['inventory']['source'], '示例为拟真数据；真实使用请替换为可获得的历史序列'],
        ['', '指标 Y（价格）', dm['price']['name'], dm['price']['unit'], '周度（由日报汇总）',
         dm['price']['region'], '日报午评口径（如 12:00），取当周锚日',
         dm['price']['source'], '现货报价的税基/现汇/库提口径需与成交口径核对'],
        ['', '控制变量（可选）', '动力煤 5500 现货价', '元/吨', '周度', '环渤海/秦皇岛', '周度发布',
         'DEMO：成本参照', '仅用于偏相关诊断“共同外部因素”'],
        ['', '分析频率', '周度（周三对齐）', '—', '周度', '—', '—', '对齐规则见“03 频率对齐”',
         '若原始为日度，须按同一时点汇总，禁止使用未来信息'],
    ]
    r = 5
    for row in spec:
        for i, v in enumerate(row, 1):
            ws.cell(row=r, column=i, value=v)
        r += 1
    style_body(ws, 5, r - 1, 9, wrap_cols=(3, 6, 7, 8, 9))
    for rr in range(5, r):
        ws.row_dimensions[rr].height = 34
    r += 1
    ws.cell(row=r, column=2, value='数据状态').font = Font(name='微软雅黑', size=10, bold=True)
    c = ws.cell(row=r, column=3, value=dm['caveat'])
    c.font = B_FONT
    c.fill = PatternFill('solid', fgColor=DEMO)
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=9)
    ws.row_dimensions[r].height = 46
    ws.sheet_view.showGridLines = False

    # ============================================ 02 原始数据
    ws = wb.create_sheet('02 原始数据')
    title_block(ws, '原始数据（唯一数据入口，其余表全部由本表驱动）',
                '橙底两列为需替换的核心输入列（库存、价格）。留空=缺失，全表按缺失处理，不插补。', 11)
    hdr = ['序号', '观测日(库存调查日)', '价格锚日', '港口库存-总计', '港口库存-华东', '港口库存-华南',
           '太仓现货价', '动力煤5500', '下游开工率%', '周度到港', '周度提货']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 11)
    keys = ['inventory_total', 'inventory_ec', 'inventory_sc', 'spot_taicang', 'coal_5500', 'op_rate', 'arrival', 'demand']
    for i, rw in enumerate(rows):
        r = 5 + i
        ws.cell(row=r, column=1, value=i + 1)
        ws.cell(row=r, column=2, value=rw['week_ending'])
        ws.cell(row=r, column=3, value=rw['price_date'])
        for j, k in enumerate(keys):
            # 缺失写成空单元格（不用 =NA()）：空单元格会被 CORREL/SLOPE 等函数自动跳过，
            # 且不会像 NA() 那样在 IF 里被当成“有值”而污染差分公式。
            v = rw[k]
            ws.cell(row=r, column=4 + j, value=None if v in ('', None) else float(v))
    style_body(ws, 5, last, 11)
    fmts = {4: '0.00', 5: '0.00', 6: '0.00', 7: '#,##0', 8: '#,##0', 9: '0.0', 10: '0.00', 11: '0.00'}
    for i in range(n):
        r = 5 + i
        for col in range(1, 12):
            ws.cell(row=r, column=col).fill = PatternFill('solid', fgColor=('FFFFFF' if i % 2 else LIGHT2))
        ws.cell(row=r, column=4).fill = PatternFill('solid', fgColor=DEMO)
        ws.cell(row=r, column=7).fill = PatternFill('solid', fgColor=DEMO)
        for col, f in fmts.items():
            ws.cell(row=r, column=col).number_format = f
    widths(ws, {'A': 6, 'B': 20, 'C': 13, 'D': 15, 'E': 15, 'F': 15, 'G': 13, 'H': 13, 'I': 13, 'J': 11, 'K': 11})
    ws.freeze_panes = 'B5'
    ws.sheet_view.showGridLines = False

    # ============================================ 03 频率对齐
    ws = wb.create_sheet('03 频率对齐')
    title_block(ws, '频率对齐与配对规则',
                '库存为周三调查值，价格为同一交易日午评报价；两序列均按周度处理，直接按观测日一一配对。任一期缺失则不参与配对，也不补数。', 9)
    hdr = ['序号', '观测日', '价格锚日', '配对状态', '库存', '价格', '库存形态', '价格形态', '时点一致性']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 9)
    for i in range(n):
        r = 5 + i
        ws.cell(row=r, column=1, value=i + 1)
        ws.cell(row=r, column=2, value=f"='02 原始数据'!B{5+i}")
        ws.cell(row=r, column=3, value=f"='02 原始数据'!C{5+i}")
        ws.cell(row=r, column=4,
                value=f'=IF(OR(E{r}="",F{r}=""),"缺失-剔除","配对成功")')
        ws.cell(row=r, column=5, value=f"='02 原始数据'!D{5+i}")
        ws.cell(row=r, column=6, value=f"='02 原始数据'!G{5+i}")
        ws.cell(row=r, column=7, value=f'=IF(D{r}="配对成功","水平可用","")')
        ws.cell(row=r, column=8, value=f'=IF(AND(D{r}="配对成功",A{r}>1,E{r-1}<>""),"变化可用","")' if i > 0 else '=""')
        ws.cell(row=r, column=9, value=f'=IF(B{r}=C{r},"同日","不同日，需注明时点差")')
    style_body(ws, 5, last, 9)
    tot = last + 2
    ws.cell(row=tot, column=2, value='有效配对数 N =').font = Font(name='微软雅黑', size=10, bold=True)
    ws.cell(row=tot, column=5, value=f'=COUNTIF(D5:D{last},"配对成功")').font = Font(name='微软雅黑', size=10, bold=True, color=NAVY)
    ws.cell(row=tot + 1, column=2, value='缺失期数 =').font = Font(name='微软雅黑', size=10, bold=True)
    ws.cell(row=tot + 1, column=5, value=f'=COUNTIF(D5:D{last},"缺失-剔除")').font = Font(name='微软雅黑', size=10, bold=True, color='C0392B')
    widths(ws, {'A': 6, 'B': 15, 'C': 13, 'D': 12, 'E': 11, 'F': 10, 'G': 11, 'H': 11, 'I': 24})
    ws.freeze_panes = 'B5'
    ws.sheet_view.showGridLines = False

    # ============================================ 04 变换后数据
    ws = wb.create_sheet('04 变换后数据')
    title_block(ws, '变换：水平 / 一阶差分 / 环比%',
                '差分与环比的首期必为空（没有上一期），这是设计而非缺数。库存变化单位是万吨，价格变化单位是%，相关系数本身与单位无关，但经济含义不同。', 11)
    hdr = ['序号', '观测日', '库存-水平', '库存-差分', '库存-环比%', '价格-水平', '价格-差分', '价格-环比%',
           '煤价-水平', '开工率-水平', '库存/提货比']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 11)
    for i in range(n):
        r = 5 + i
        ws.cell(row=r, column=1, value=i + 1)
        ws.cell(row=r, column=2, value=f"='02 原始数据'!B{5+i}")
        ws.cell(row=r, column=3, value=f"='02 原始数据'!D{5+i}")
        ws.cell(row=r, column=4, value=f'=IF(OR(C{r}="",C{r-1}=""),"",C{r}-C{r-1})' if i > 0 else '=""')
        ws.cell(row=r, column=5, value=f'=IF(OR(C{r}="",C{r-1}=""),"",(C{r}-C{r-1})/ABS(C{r-1}))' if i > 0 else '=""')
        ws.cell(row=r, column=6, value=f"='02 原始数据'!G{5+i}")
        ws.cell(row=r, column=7, value=f'=IF(OR(F{r}="",F{r-1}=""),"",F{r}-F{r-1})' if i > 0 else '=""')
        ws.cell(row=r, column=8, value=f'=IF(OR(F{r}="",F{r-1}=""),"",(F{r}-F{r-1})/ABS(F{r-1}))' if i > 0 else '=""')
        ws.cell(row=r, column=9, value=f"='02 原始数据'!H{5+i}")
        ws.cell(row=r, column=10, value=f"='02 原始数据'!I{5+i}")
        ws.cell(row=r, column=11, value=f"=IFERROR(IF(C{r}=\"\",\"\",C{r}/'02 原始数据'!K{5+i}),\"\")")
    style_body(ws, 5, last, 11)
    for i in range(n):
        r = 5 + i
        ws.cell(row=r, column=4).number_format = '0.00'
        ws.cell(row=r, column=5).number_format = '0.00%'
        ws.cell(row=r, column=7).number_format = '#,##0'
        ws.cell(row=r, column=8).number_format = '0.00%'
        ws.cell(row=r, column=11).number_format = '0.00'
    widths(ws, {'A': 6, 'B': 14, 'C': 12, 'D': 12, 'E': 11, 'F': 12, 'G': 12, 'H': 11, 'I': 12, 'J': 12, 'K': 14})
    ws.freeze_panes = 'C5'
    ws.sheet_view.showGridLines = False

    # ============================================ 05 总体相关
    ws = wb.create_sheet('05 总体相关')
    title_block(ws, '总体相关系数（Excel 原生公式，可在表内直接重算）',
                '五种形态组合齐列，避免“只用一种口径下结论”。p 用 T.DIST.2T，R² 用 RSQ，N 用 COUNT 系列函数统计有效数。', 8)
    hdr = ['', '组合', 'Pearson r', 'N', 'R²', 't 统计量', 'p 值（双侧）', '判定']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 8)
    combos = [
        ('① 库存水平 × 价格水平', R_INV, R_PLV, '最易被共同趋势抬升'),
        ('② 库存水平 × 价格环比%', R_INV, R_PPC, '一端水平一端变化，易误用'),
        ('③ 库存差分 × 价格环比%', R_DIF, R_PPC, '推荐主口径：变化对变化'),
        ('④ 库存差分 × 价格差分', R_DIF, R_PDF, '同为绝对变化'),
        ('⑤ 库存环比% × 价格环比%', R_PCT, R_PPC, '两端都标准化为百分比'),
    ]
    r = 5
    for name, xr, yr, note in combos:
        ws.cell(row=r, column=2, value=name)
        ws.cell(row=r, column=3, value=f'=IFERROR(CORREL({xr},{yr}),"样本不足")')
        ws.cell(row=r, column=4, value=f'=SUMPRODUCT(--ISNUMBER({xr}),--ISNUMBER({yr}))')
        ws.cell(row=r, column=5, value=f'=IFERROR(C{r}^2,"")')
        ws.cell(row=r, column=6, value=f'=IFERROR(C{r}*SQRT((D{r}-2)/(1-C{r}^2)),"")')
        ws.cell(row=r, column=7, value=f'=IFERROR(_XLFN.T.DIST.2T(ABS(F{r}),D{r}-2),"")')
        ws.cell(row=r, column=8,
                value=f'=IF(G{r}="","",IF(G{r}<0.01,"显著(1%)",IF(G{r}<0.05,"显著(5%)",IF(G{r}<0.1,"边际(10%)","不显著"))))')
        r += 1
    style_body(ws, 5, r - 1, 8)
    for rr in range(5, r):
        ws.cell(row=rr, column=3).number_format = '0.0000'
        ws.cell(row=rr, column=5).number_format = '0.0000'
        ws.cell(row=rr, column=6).number_format = '0.00'
        ws.cell(row=rr, column=7).number_format = '0.0000E+00'
    r += 1
    notes = [
        ('N 的算法', 'SUMPRODUCT(--ISNUMBER(x),--ISNUMBER(y)) 统计“两列同时有数”的期数；缺失用 NA() 表示，CORREL 会自动跳过缺配对，不会把缺失当 0。'),
        ('p 值的含义', '“若总体真实相关为 0，出现这么极端样本的概率”。p 小只说明不像偶然；相关强不强看 |r|，是不是因果与 p 无关。'),
        ('为什么列五种组合', '同一对指标换个形态，r 可能完全不同。只报一种口径的相关系数，无法被复核。'),
    ]
    for k, v in notes:
        ws.cell(row=r, column=2, value=k).font = Font(name='微软雅黑', size=10, bold=True, color=NAVY)
        c = ws.cell(row=r, column=3, value=v)
        c.font = B_FONT
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=8)
        ws.row_dimensions[r].height = 34
        r += 1
    widths(ws, {'A': 3, 'B': 24, 'C': 12, 'D': 8, 'E': 10, 'F': 11, 'G': 14, 'H': 14})
    ws.sheet_view.showGridLines = False

    # ============================================ 06 滚动相关
    ws = wb.create_sheet('06 滚动相关')
    title_block(ws, '滚动相关系数（12 / 26 / 52 周；主口径：库存差分 × 价格环比%）',
                '每行对应窗口末端日期。窗口内有效配对数低于“最小样本数”时输出空白，不外推、不插值。改第 3 行窗口参数后整表自动重算。', 9)
    ws.cell(row=3, column=2, value='12周窗口').font = Font(name='微软雅黑', size=9, color='6B7B8C')
    ws.cell(row=3, column=3, value=12)
    ws.cell(row=3, column=4, value='26周窗口').font = Font(name='微软雅黑', size=9, color='6B7B8C')
    ws.cell(row=3, column=5, value=26)
    ws.cell(row=3, column=6, value='52周窗口').font = Font(name='微软雅黑', size=9, color='6B7B8C')
    ws.cell(row=3, column=7, value=52)
    for col in range(2, 8):
        ws.cell(row=3, column=col).alignment = Alignment(horizontal='center')
    hdr = ['序号', '窗口末端日期', '12周 r', '12周 N', '26周 r', '26周 N', '52周 r', '52周 N', '主口径强度']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 9)
    for i in range(n):
        r = 5 + i
        ws.cell(row=r, column=1, value=i + 1)
        ws.cell(row=r, column=2, value=f"='04 变换后数据'!B{5+i}")
        for j, (wcell, rcol, ncol) in enumerate([('C', 3, 4), ('E', 5, 6), ('G', 7, 8)]):
            wref = f'${wcell}$3'
            ws.cell(row=r, column=rcol,
                    value=(f'=IF({i+1}<{wref},"",IF({ncol}{r}=0,"",'
                           f'IF({ncol}{r}<MAX(5,ROUND({wref}*0.8,0)),"样本不足",'
                           f'CORREL(OFFSET({R_DIF},ROW()-5-{wref}+1,0,{wref},1),OFFSET({R_PPC},ROW()-5-{wref}+1,0,{wref},1))))'))
            ws.cell(row=r, column=ncol,
                    value=f'=IF({i+1}<{wref},0,SUMPRODUCT(--(ROW({R_DIF})<=ROW()),--ISNUMBER(OFFSET({R_DIF},ROW()-5-{wref}+1,0,MIN({wref},ROW()-4),1)),--ISNUMBER(OFFSET({R_PPC},ROW()-5-{wref}+1,0,MIN({wref},ROW()-4),1))))')
            ws.cell(row=r, column=rcol).number_format = '0.000'
        ws.cell(row=r, column=9, value=f'=IF(ISNUMBER(E{r}),IF(ABS(E{r})>=0.7,"强",IF(ABS(E{r})>=0.4,"中","弱")),"-")')
    style_body(ws, 5, last, 9)
    ch = LineChart()
    ch.title = '26 周滚动相关（库存差分 × 价格环比%）'
    ch.y_axis.title = 'r'
    ch.x_axis.title = '窗口末端日期'
    data = Reference(ws, min_col=5, min_row=4, max_row=last)
    cats = Reference(ws, min_col=2, min_row=5, max_row=last)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    ch.height = 8.5
    ch.width = 22
    ws.add_chart(ch, 'K4')
    widths(ws, {'A': 6, 'B': 15, 'C': 10, 'D': 8, 'E': 10, 'F': 8, 'G': 10, 'H': 8, 'I': 11})
    ws.freeze_panes = 'C5'
    ws.sheet_view.showGridLines = False

    # ============================================ 07 分阶段
    ws = wb.create_sheet('07 分阶段结果')
    title_block(ws, '分阶段结果（相关强度会随市场阶段变化）',
                '断点写在第 4 行，改日期后公式自动重算。断点应按行业逻辑设定（检修季、需求淡季、产能投放、政策窗口），不要为凑结果反复切分。', 9)
    breaks = ['2023-10-11', '2024-09-01', '2025-09-01', '2026-09-30']
    for i, b in enumerate(breaks):
        c = ws.cell(row=4, column=2 + i, value=b)
        c.font = Font(name='微软雅黑', size=10, bold=True, color=BLUE)
        c.fill = PatternFill('solid', fgColor=LIGHT)
        c.border = BORDER
        c.alignment = Alignment(horizontal='center')
    for i in range(3):
        ws.cell(row=5, column=2 + i, value=f'阶段{i+1}断点 →').font = Font(name='微软雅黑', size=9, color='6B7B8C')
    hdr = ['阶段', '起始', '结束', 'N', 'Pearson r', 'Spearman ρ', 'p 值', '强度', '显著性']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=7, column=i, value=h)
    style_header(ws, 7, 9)
    for ph in range(3):
        r = 8 + ph
        ws.cell(row=r, column=1, value=f'阶段{ph+1}')
        ws.cell(row=r, column=2, value=f'=TEXT({get_column_letter(2+ph)}4,"yyyy-mm-dd")')
        ws.cell(row=r, column=3, value=f'=TEXT({get_column_letter(3+ph)}4,"yyyy-mm-dd")')
        ws.cell(row=r, column=4, value=f'=SUMPRODUCT(({R_DAT}>=$B{r})*({R_DAT}<=$C{r})*ISNUMBER({R_DIF})*ISNUMBER({R_PPC}))')
        ws.cell(row=r, column=5,
                value=f'=IFERROR(CORREL(IF(({R_DAT}>=$B{r})*({R_DAT}<=$C{r}),{R_DIF}),IF(({R_DAT}>=$B{r})*({R_DAT}<=$C{r}),{R_PPC})),"")')
        ws.cell(row=r, column=6,
                value=f'=IFERROR(CORREL(IF(({R_DAT}>=$B{r})*({R_DAT}<=$C{r}),{R_DIF}),'
                      f'IF(({R_DAT}>=$B{r})*({R_DAT}<=$C{r}),{R_PPC})),"")')
        ws.cell(row=r, column=7, value=f'=IFERROR(_XLFN.T.DIST.2T(ABS(E{r}*SQRT((D{r}-2)/(1-E{r}^2))),D{r}-2),"")')
        ws.cell(row=r, column=8, value=f'=IF(E{r}="","-",IF(ABS(E{r})>=0.7,"强",IF(ABS(E{r})>=0.4,"中","弱")))')
        ws.cell(row=r, column=9, value=f'=IF(G{r}="","",IF(G{r}<0.05,"显著","不显著"))')
        ws.cell(row=r, column=5).number_format = '0.0000'
        ws.cell(row=r, column=6).number_format = '0.0000'
        ws.cell(row=r, column=7).number_format = '0.000E+00'
    style_body(ws, 8, 10, 9)
    c = ws.cell(row=12, column=2, value='E/F 列为 IF 掩码数组公式：Excel 365 / WPS 直接回车即可；旧版 Excel 需 Ctrl+Shift+Enter。'
                                        'Spearman ρ 在此按 Pearson 掩码近似占位，精确秩相关由 scripts/analyze.py 输出（见 10 滞后相关旁的脚本结果）。')
    c.font = Font(name='微软雅黑', size=9, color='6B7B8C')
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.merge_cells(start_row=12, start_column=2, end_row=12, end_column=9)
    ws.row_dimensions[12].height = 34
    widths(ws, {'A': 10, 'B': 18, 'C': 18, 'D': 8, 'E': 12, 'F': 12, 'G': 13, 'H': 8, 'I': 11})
    ws.sheet_view.showGridLines = False

    # ============================================ 08 形态矩阵
    ws = wb.create_sheet('08 形态组合矩阵')
    title_block(ws, '形态组合矩阵（3×3）',
                '同一对指标换形态后 r 可以差很多。写结论必须写明“哪种形态对哪种形态”，否则无法复核。', 6)
    forms = [('水平', R_INV, R_PLV), ('差分', R_DIF, R_PDF), ('环比%', R_PCT, R_PPC)]
    ws.cell(row=4, column=2, value='库存 ＼ 价格')
    for j, (fname, _, _) in enumerate(forms):
        ws.cell(row=4, column=3 + j, value=f'价格-{fname}')
    style_header(ws, 4, 5)
    for i, (xname, xr, _) in enumerate(forms):
        r = 5 + i
        c = ws.cell(row=r, column=2, value=f'库存-{xname}')
        c.font = Font(name='微软雅黑', size=10, bold=True)
        c.fill = PatternFill('solid', fgColor=LIGHT)
        c.border = BORDER
        c.alignment = Alignment(horizontal='center')
        for j, (_, _, yr) in enumerate(forms):
            cell = ws.cell(row=r, column=3 + j, value=f'=IFERROR(CORREL({xr},{yr}),"")')
            cell.number_format = '0.000'
            cell.border = BORDER
            cell.font = Font(name='微软雅黑', size=11, bold=True)
            cell.alignment = Alignment(horizontal='center')
    r = 9
    ws.cell(row=r, column=2, value='解读').font = Font(name='微软雅黑', size=10, bold=True)
    c = ws.cell(row=r, column=3, value='主口径建议“库存差分 × 价格环比%”（第 3 行第 3 列）：两端都是变化量、各自用合适单位，且不会因共同趋势虚高。'
                                       '“水平 × 水平”只能作背景描述，必须同时给出差分口径并说明差异。')
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
    ws.row_dimensions[r].height = 44
    widths(ws, {'A': 3, 'B': 18, 'C': 16, 'D': 16, 'E': 16, 'F': 16})
    ws.sheet_view.showGridLines = False

    # ============================================ 09 稳健性诊断
    ws = wb.create_sheet('09 稳健性与伪相关诊断')
    title_block(ws, '稳健性与伪相关诊断',
                '逐项检验“这个相关是不是只来自趋势 / 自相关 / 共同外部因素”。任何一项让 r 大幅衰减，都要在结论里如实写出来。', 5)
    hdr = ['诊断项', '数值', '计算口径', '判读标准', '结论与处理']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 5)
    ws5 = wb['05 总体相关']
    diag = [
        ('基准：库存差分 × 价格环比%', "='05 总体相关'!C7", 'CORREL(库存差分, 价格环比%)', '其余诊断的参照基准', '所有稳健性结论相对此项比较'),
        ('去趋势后 r', "='09b 辅助计算(残差)'!D160", '对时间回归取残差后的 CORREL', '显著低于基准 → 有共同趋势成分', '结论以变化口径为准'),
        ('水平 × 水平（对照）', "='05 总体相关'!C5", 'CORREL(库存水平, 价格水平)', '通常明显高于差分口径', '只作背景，不作结论依据'),
        ('库存一阶自相关 ρ₁', "='04 变换后数据'!C6", 'CORREL(水平_t, 水平_t-1)', '>0.7 表示强记忆性', '用有效样本量修正 p'),
        ('价格一阶自相关 ρ₁', "='04 变换后数据'!F6", '同上', '同上', '同上'),
        ('剔极值后 r', '', '剔除上下 5% 后重算', '与基准接近 → 结论不由极值撑起', '如变化大，需点名极值日期'),
        ('分段一致性', '', '前 1/3 与后 1/3 分别计算', '方向一致才谈“稳定”', '方向相反必须写“阶段性失效”'),
        ('控制煤价后的偏相关', '', '对煤价回归取残差再相关', '明显低于基准 → 成本解释一部分', '写明“控制成本后仍剩多少”'),
        ('有效样本量 N_eff', '', 'n(1-ρxρy)/(1+ρxρy)', '比名义 N 小很多时，名义 p 过于乐观', '报告修正 p（见 analyze.py）'),
    ]
    r = 5
    for a, b, c_, d, e in diag:
        ws.cell(row=r, column=1, value=a)
        ws.cell(row=r, column=2, value=b if b else '见 analyze.py 输出')
        ws.cell(row=r, column=3, value=c_)
        ws.cell(row=r, column=4, value=d)
        ws.cell(row=r, column=5, value=e)
        r += 1
    style_body(ws, 5, r - 1, 5, wrap_cols=(1, 3, 4, 5))
    widths(ws, {'A': 26, 'B': 24, 'C': 34, 'D': 32, 'E': 34})
    ws.sheet_view.showGridLines = False

    # ============================================ 09b 辅助计算
    ws = wb.create_sheet('09b 辅助计算(残差)')
    title_block(ws, '辅助计算：回归残差（去趋势）',
                '用 SLOPE/INTERCEPT 逐行算预测值与残差；残差之间的相关即“去趋势后相关”。改数据后自动重算。', 9)
    hdr = ['序号', '日期', 't', '库存-水平', '价格-水平', '库存趋势拟合', '库存残差', '价格趋势拟合', '价格残差']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 9)
    for i in range(n):
        r = 5 + i
        ws.cell(row=r, column=1, value=i + 1)
        ws.cell(row=r, column=2, value=f"='04 变换后数据'!B{5+i}")
        ws.cell(row=r, column=3, value=i + 1)
        ws.cell(row=r, column=4, value=f"='04 变换后数据'!C{5+i}")
        ws.cell(row=r, column=5, value=f"='04 变换后数据'!F{5+i}")
        ws.cell(row=r, column=6, value=f'=IF(ISNUMBER(D{r}),SLOPE({R_INV},{R_TS})*C{r}+INTERCEPT({R_INV},{R_TS}),"")')
        ws.cell(row=r, column=7, value=f'=IF(ISNUMBER(D{r}),D{r}-F{r},"")')
        ws.cell(row=r, column=8, value=f'=IF(ISNUMBER(E{r}),SLOPE({R_PLV},{R_TS})*C{r}+INTERCEPT({R_PLV},{R_TS}),"")')
        ws.cell(row=r, column=9, value=f'=IF(ISNUMBER(E{r}),E{r}-H{r},"")')
    style_body(ws, 5, last, 9, numfmt='0.00')
    r = last + 2
    rows_out = [
        ('去趋势后相关 r =', f'=IFERROR(CORREL(G5:G{last},I5:I{last}),"")', '0.0000'),
        ('R²（库存 vs 时间）=', f'=IFERROR(RSQ({R_INV},{R_TS}),"")', '0.0000'),
        ('R²（价格 vs 时间）=', f'=IFERROR(RSQ({R_PLV},{R_TS}),"")', '0.0000'),
        ('库存时间趋势斜率 =', f'=IFERROR(SLOPE({R_INV},{R_TS}),"")', '0.0000'),
        ('价格时间趋势斜率 =', f'=IFERROR(SLOPE({R_PLV},{R_TS}),"")', '0.0000'),
    ]
    for k, (label, formula, nf) in enumerate(rows_out):
        ws.cell(row=r + k, column=2, value=label).font = Font(name='微软雅黑', size=10, bold=True)
        c = ws.cell(row=r + k, column=4, value=formula)
        c.font = Font(name='微软雅黑', size=10, bold=True, color=NAVY)
        c.number_format = nf
    # 09 表引用第 160 行（去趋势相关）——用动态行号保证指向正确单元格
    wb['09 稳健性与伪相关诊断']['B6'] = f"='09b 辅助计算(残差)'!$D${r}"
    widths(ws, {'A': 6, 'B': 14, 'C': 10, 'D': 12, 'E': 12, 'F': 16, 'G': 12, 'H': 16, 'I': 12})
    ws.sheet_view.showGridLines = False

    # ============================================ 10 滞后相关
    ws = wb.create_sheet('10 滞后相关')
    title_block(ws, '滞后相关（lag = -4 ~ +4 期，主口径）',
                'lag>0：库存领先价格（库存[t] 对 价格[t+lag]）。峰值在 lag>0 只能说明先后顺序与数据吻合，不能证明因果。数值由 analyze.py 预计算写入。', 4)
    hdr = ['lag（期）', '含义', 'Pearson r', 'N']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 4)
    dI = C.transform(inv, 'change')
    pP = C.transform(price, 'pct')
    dI2, pP2, _ = C.align(dI, pP, dates)
    r = 5
    for L in range(-4, 5):
        ws.cell(row=r, column=1, value=L)
        ws.cell(row=r, column=2, value=('价格领先库存' if L < 0 else '同期' if L == 0 else '库存领先价格'))
        v = C.lag_corr(dI2, pP2, L)
        ws.cell(row=r, column=3, value=None if v is None else round(v, 4))
        ws.cell(row=r, column=4, value=len(dI2) - abs(L))
        ws.cell(row=r, column=3).number_format = '0.0000'
        r += 1
    style_body(ws, 5, r - 1, 4)
    ws.cell(row=r + 1, column=2, value='替换数据后请重跑：python scripts/analyze.py ... 以更新本表。')
    widths(ws, {'A': 10, 'B': 18, 'C': 12, 'D': 8})
    ws.sheet_view.showGridLines = False

    # ============================================ 11 事件
    ws = wb.create_sheet('11 事件与口径提示')
    title_block(ws, '行业事件与口径提示（用于解释“相关性为何变化”）',
                '只记录可公开核对的事件与口径风险；不写因果断言、不写交易建议。事件与价格/库存的关系需单独验证。', 5)
    hdr = ['起始', '结束', '类型', '事件', '说明']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 5)
    r = 5
    for e in EVENTS:
        ws.cell(row=r, column=1, value=e['start'])
        ws.cell(row=r, column=2, value=e['end'])
        ws.cell(row=r, column=3, value=e['kind'])
        ws.cell(row=r, column=4, value=e['title'])
        ws.cell(row=r, column=5, value=e['note'])
        ws.row_dimensions[r].height = 30
        r += 1
    style_body(ws, 5, r - 1, 5, wrap_cols=(4, 5))
    widths(ws, {'A': 12, 'B': 12, 'C': 10, 'D': 30, 'E': 76})
    ws.sheet_view.showGridLines = False

    # ============================================ 12 公式说明
    ws = wb.create_sheet('12 公式说明')
    title_block(ws, '公式说明（统计口径与 Excel 实现）',
                '每条都能在工作簿内找到对应单元格复核；Excel 无法原生实现的量注明由哪个脚本输出。', 4)
    hdr = ['统计量', '定义/公式', 'Excel 写法', '注意事项']
    for i, h in enumerate(hdr, 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 4)
    items = [
        ('Pearson r', 'r = Σ(x-x̄)(y-ȳ) / √(Σ(x-x̄)²·Σ(y-ȳ)²)', 'CORREL(区域X, 区域Y)', '只度量线性关系；对离群点敏感'),
        ('Spearman ρ', '两列取平均秩后求 Pearson', 'CORREL(RANK.AVG 秩列) 或 matrix 脚本输出', '抗离群，可捕捉单调非线性'),
        ('R²', 'r²，解释的方差比例', 'RSQ(y, x) 或 r²', '不是因果强度'),
        ('t 统计量', 't = r·√((N-2)/(1-r²))', 'r*SQRT((N-2)/(1-r^2))', 'N 必须是有效配对数'),
        ('p 值', '双侧，自由度 N-2', 'T.DIST.2T(ABS(t), N-2)', 'p 小 ≠ 相关强'),
        ('95% 置信区间', 'Fisher-z：z=atanh(r)，SE=1/√(N-3)，tanh 回推', 'TANH(ATANH(r)±1.96/SQRT(N-3))', 'N 小时区间会极宽'),
        ('HAC 标准误', 'Newey-West 长期方差', 'scripts/analyze.py 输出', 'Excel 无原生实现'),
        ('有效样本量 N_eff', 'n(1-ρxρy)/(1+ρxρy)', 'scripts/analyze.py 输出', '修正自相关造成的显著性夸大'),
        ('去趋势相关', '对时间回归取残差后求 r', "'09b 辅助计算(残差)'!D$行号", '检验共同趋势造成的伪相关'),
        ('偏相关', '对控制变量回归取残差后求 r', 'CORREL(残差X, 残差Y)', '控制变量需与两者都相关才有意义'),
        ('滚动相关', '窗口内 CORREL，末端对齐日期', 'CORREL(OFFSET(...))', '有效配对不足时留空'),
        ('一阶差分/环比', 'Δx = x_t − x_{t−1}；(x_t−x_{t−1})/|x_{t−1}|', "'04 变换后数据'", '首期必为空'),
    ]
    r = 5
    for a, b, c_, d in items:
        ws.cell(row=r, column=1, value=a)
        ws.cell(row=r, column=2, value=b)
        ws.cell(row=r, column=3, value=c_)
        ws.cell(row=r, column=4, value=d)
        r += 1
    style_body(ws, 5, r - 1, 4, wrap_cols=(1, 2, 3, 4))
    widths(ws, {'A': 20, 'B': 46, 'C': 40, 'D': 32})
    ws.sheet_view.showGridLines = False

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    print('written', OUT, 'rows', n, 'sheets', len(wb.sheetnames))


if __name__ == '__main__':
    main()
