# -*- coding: utf-8 -*-
"""
build_template.py —— 生成可复用的空白 Excel 模板（assets/templates/联动分析模板.xlsx）

与案例工作簿的区别：
  - 案例工作簿装着 PX/PTA 的真实数据与结论；
  - 本模板只保留结构与公式，价格列为空，换品种时粘贴数据即可。

模板自带 6 行假数据（标注为示例），以便公式有可见的计算结果；
使用者把「03_原始数据」A5:C10 替换成自己的数据、把行数以外的行删掉或下拉扩展即可。
"""
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'assets', 'templates', '联动分析模板.xlsx')

HEAD = 'FF1F3A5F'
THIN = Side(style='thin', color='FFD8DEE9')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FONT = Font(bold=True, color='FFFFFFFF', size=10.5, name='微软雅黑')
BODY = Font(size=10.5, name='微软雅黑')


def hdr(ws, row, labels, widths=None):
    for i, t in enumerate(labels, 1):
        c = ws.cell(row=row, column=i, value=t)
        c.font, c.fill = HDR_FONT, PatternFill('solid', fgColor=HEAD)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = BOX
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def title(ws, t, sub=None, span=7):
    c = ws.cell(row=1, column=1, value=t)
    c.font = Font(size=15, bold=True, name='微软雅黑')
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    if sub:
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = Font(size=10, color='FF6B7280', name='微软雅黑')
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)


def build():
    wb = Workbook()
    N = 6  # 示例行数
    first, last = 5, 5 + N - 1

    # ---- 00 使用说明 ----
    ws = wb.active
    ws.title = '00_使用说明'
    ws.sheet_view.showGridLines = False
    title(ws, '上下游价格联动分析模板', '换品种时：改「01_参数」→ 粘贴价格到「02_原始数据」→ 下拉公式 → 看「04_价差」与「06_相关性」', 4)
    ws.column_dimensions['A'].width = 4
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 100
    steps = [
        ('1. 核实产业关系', '先在 references/02-工艺与单耗台账.md 里找到上游是不是下游唯一主要原料；不是唯一，就不要用本模板算价差。'),
        ('2. 填参数', '「01_参数」填单耗 λ、其他成本；λ 必须有出处。'),
        ('3. 粘数据', '「02_原始数据」A5 起粘贴 日期/上游价/下游价；行数变化后把公式列下拉到新行数。'),
        ('4. 看结果', '「04_价差」看分位与滚动均值；「06_相关性」看水平 vs 收益率；「08_阶段」改起止日期即自动重算。'),
        ('5. 写报告', '按 references/07-报告模板.md 的九节结构写；每个数字都要能回到本工作簿。'),
    ]
    r = 4
    for k, v in steps:
        a = ws.cell(row=r, column=2, value=k)
        a.font = Font(size=10.5, bold=True, name='微软雅黑')
        a.alignment = Alignment(vertical='top')
        b = ws.cell(row=r, column=3, value=v)
        b.font = BODY
        b.alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = 34
        r += 1
    note = ws.cell(row=r + 1, column=2, value='注意：本模板中的数字来自示例数据，不是真实行情。')
    note.font = Font(size=10.5, bold=True, color='FFB45309', name='微软雅黑')

    # ---- 01 参数 ----
    ws = wb.create_sheet('01_参数')
    ws.sheet_view.showGridLines = False
    title(ws, '参数（改这里，全表重算）', '黄色单元格是参数，已被命名为 Lambda / OtherCost 等，公式直接引用。', 5)
    hdr(ws, 4, ['参数', '名称', '取值', '单位', '来源/说明'], [22, 16, 14, 12, 56])
    params = [
        ('单耗系数 λ', 'Lambda', 0.655, 't/t', '必须来自单耗台账（示例：PX→PTA 0.655）'),
        ('其他成本', 'OtherCost', 0.0, '元/吨', '醋酸+动力+折旧简化项；0 = 收入型加工费'),
        ('滚动窗口', 'WinB', 20, '观测', '滚动均值/标准差窗口'),
        ('滚动窗口2', 'WinC', 60, '观测', '第二档窗口'),
        ('显著水平', 'Alpha', 0.05, '—', '双尾'),
    ]
    for i, p in enumerate(params):
        row = 5 + i
        for j, v in enumerate(p, 1):
            c = ws.cell(row=row, column=j, value=v)
            c.font = BODY
            c.border = BOX
        ws.cell(row=row, column=3).fill = PatternFill('solid', fgColor='FFFFF3CD')
        ws.cell(row=row, column=3).font = Font(size=10.5, bold=True, name='微软雅黑', color='FF92400E')
        wb.defined_names.add(DefinedName(p[1], attr_text=f"'01_参数'!$C${row}"))

    # ---- 02 原始数据 ----
    ws = wb.create_sheet('02_原始数据')
    ws.sheet_view.showGridLines = False
    title(ws, '原始价格数据（示例行，请替换）', 'E~H 列为公式；替换 A~C 后把 E~H 下拉到底。', 8)
    hdr(ws, 4, ['日期', '上游价格', '下游价格', '摘要', '价差', '价比', '上游收益率', '下游收益率'],
        [14, 14, 14, 14, 14, 10, 14, 14])
    demo = [('2025-01-02', 7000, 5000), ('2025-01-03', 7020, 5010), ('2025-01-06', 6990, 4990),
            ('2025-01-07', 7050, 5030), ('2025-01-08', 7100, 5050), ('2025-01-09', 7080, 5060)]
    for i, (d, up, dn) in enumerate(demo):
        r = first + i
        ws.cell(row=r, column=1, value=d)
        ws.cell(row=r, column=2, value=up).number_format = '#,##0.00'
        ws.cell(row=r, column=3, value=dn).number_format = '#,##0.00'
        ws.cell(row=r, column=4, value='示例数据').font = Font(size=10, color='FF9CA3AF', name='微软雅黑')
        ws.cell(row=r, column=5, value=f'=C{r}-Lambda*B{r}-OtherCost').number_format = '#,##0.00'
        ws.cell(row=r, column=6, value=f'=C{r}/B{r}').number_format = '0.0000'
        if i > 0:
            ws.cell(row=r, column=7, value=f'=B{r}/B{r-1}-1').number_format = '0.00%'
            ws.cell(row=r, column=8, value=f'=C{r}/C{r-1}-1').number_format = '0.00%'
        for j in range(1, 9):
            cell = ws.cell(row=r, column=j)
            cell.border = BOX
            if cell.font.color is None or cell.font.color.rgb != 'FF9CA3AF':
                cell.font = BODY if j < 5 else Font(size=10.5, name='微软雅黑', color='FF0B5FFF')

    # ---- 03 单耗台账 ----
    ws = wb.create_sheet('03_单耗台账')
    ws.sheet_view.showGridLines = False
    title(ws, '单耗台账（必须逐条有出处）', '无出处的行请删除；不要保留估算值。', 5)
    hdr(ws, 4, ['来源/装置', '主料单耗 t/t', '辅料单耗 t/t', '出处', '备注'], [28, 14, 14, 40, 30])
    rows = [('行业通用值', 0.655, 0.032, '（填写你的文献来源）', '示例'),
            ('装置 A', 0.657, 0.036, '（填写）', ''),
            ('装置 B', 0.649, 0.029, '（填写）', ''),]
    for i, row in enumerate(rows):
        for j, v in enumerate(row, 1):
            c = ws.cell(row=5 + i, column=j, value=v)
            c.font = BODY
            c.border = BOX
    rng = f'B5:B{5 + len(rows) - 1}'
    ws.cell(row=9, column=1, value='均值').font = Font(size=10.5, bold=True, name='微软雅黑')
    ws.cell(row=9, column=2, value=f'=AVERAGE({rng})').number_format = '0.0000'
    ws.cell(row=10, column=1, value='极差').font = Font(size=10.5, bold=True, name='微软雅黑')
    ws.cell(row=10, column=2, value=f'=MAX({rng})-MIN({rng})').number_format = '0.0000'

    # ---- 04 价差 ----
    ws = wb.create_sheet('04_价差')
    ws.sheet_view.showGridLines = False
    title(ws, '加工价差与分位', '公式引用 02_原始数据；替换数据后下拉。', 6)
    hdr(ws, 4, ['日期', '上游', '下游', '价差', '历史分位', '滚动均值'], [14, 12, 12, 13, 14, 13])
    DR = "'02_原始数据'!"
    nrow = last
    for i in range(N):
        r = 5 + i
        src = first + i
        ws.cell(row=r, column=1, value=f'={DR}A{src}').number_format = 'yyyy-mm-dd'
        ws.cell(row=r, column=2, value=f'={DR}B{src}').number_format = '#,##0.00'
        ws.cell(row=r, column=3, value=f'={DR}C{src}').number_format = '#,##0.00'
        ws.cell(row=r, column=4, value=f'={DR}E{src}').number_format = '#,##0.00'
        ws.cell(row=r, column=5,
                value=f'=PERCENTRANK.INC({DR}$E${first}:$E${nrow},{DR}E{src})').number_format = '0.0%'
        ws.cell(row=r, column=6,
                value=f'=IF(COUNT({DR}$E${first}:$E{src})>=2,AVERAGE({DR}$E${first}:$E{src}),"")'
                ).number_format = '#,##0.00'
        for j in range(1, 7):
            c = ws.cell(row=r, column=j)
            c.border = BOX
            if j > 1:
                c.font = Font(size=10.5, name='微软雅黑', color='FF0B5FFF')

    r0 = 5 + N + 2
    hdr(ws, r0, ['统计量', '数值', '说明'], [22, 16, 56])
    stats = [('P10', f'=PERCENTILE.INC({DR}$E${first}:$E${nrow},0.1)', '历史 10% 分位'),
             ('P50', f'=PERCENTILE.INC({DR}$E${first}:$E${nrow},0.5)', '中位（抗极端值）'),
             ('P90', f'=PERCENTILE.INC({DR}$E${first}:$E${nrow},0.9)', '历史 90% 分位'),
             ('均值', f'=AVERAGE({DR}$E${first}:$E${nrow})', '算术均值'),
             ('标准差', f'=STDEV({DR}$E${first}:$E${nrow})', '样本标准差'),
             ('当前值', f'={DR}E{nrow}', '最后一个观测')]
    for i, (k, f, note) in enumerate(stats):
        ws.cell(row=r0 + 1 + i, column=1, value=k).font = BODY
        c = ws.cell(row=r0 + 1 + i, column=2, value=f)
        c.number_format = '#,##0.00'
        c.font = Font(size=10.5, name='微软雅黑', color='FF0B5FFF')
        ws.cell(row=r0 + 1 + i, column=3, value=note).font = Font(size=10, color='FF6B7280', name='微软雅黑')

    # ---- 05 单耗敏感性 ----
    ws = wb.create_sheet('05_单耗敏感性')
    ws.sheet_view.showGridLines = False
    title(ws, '单耗敏感性（λ 不确定时价差怎么变）', '价差 = 下游 − λ×上游 − 其他成本；每行一个 λ。', 5)
    hdr(ws, 4, ['λ', '价差均值', '价差中位', '标准差'], [10, 14, 14, 14])
    for k in range(9):
        lam = round(0.60 + 0.005 * k, 3)
        r = 5 + k
        ws.cell(row=r, column=1, value=lam).number_format = '0.000'
        # 用辅助列在 F 列生成该 λ 下的价差序列，再统计（避免数组公式兼容问题）
        for i in range(N):
            src = first + i
            cell = ws.cell(row=5 + i, column=6 + k,
                           value=f"={DR}C{src}-{lam}*{DR}B{src}-OtherCost")
            cell.font = Font(size=8.5, color='FF9CA3AF', name='微软雅黑')
            cell.number_format = '#,##0.00'
        L = get_column_letter(6 + k)
        rng2 = f'${L}$5:${L}${4 + N}'
        ws.cell(row=r, column=2, value=f'=AVERAGE({rng2})').number_format = '#,##0.00'
        ws.cell(row=r, column=3, value=f'=MEDIAN({rng2})').number_format = '#,##0.00'
        ws.cell(row=r, column=4, value=f'=STDEV({rng2})').number_format = '#,##0.00'
        for j in range(1, 5):
            ws.cell(row=r, column=j).border = BOX
    ws.cell(row=3, column=6, value='辅助：各 λ 下的价差序列').font = Font(size=9, color='FF9CA3AF', name='微软雅黑')

    # ---- 06 相关性 ----
    ws = wb.create_sheet('06_相关性')
    ws.sheet_view.showGridLines = False
    title(ws, '水平相关 vs 收益率相关', '两个数不能互相替代：水平含共同趋势，收益率才反映逐期传导。', 7)
    hdr(ws, 4, ['口径', 'Pearson r', 'R²', 'N', 't', 'p（双尾）', '95%CI'],
        [26, 13, 11, 8, 12, 14, 22])
    blocks = [('价格水平', f'{DR}$B${first}:$B${nrow}', f'{DR}$C${first}:$C${nrow}'),
              ('日收益率', f'{DR}$G${first + 1}:$G${nrow}', f'{DR}$H${first + 1}:$H${nrow}')]
    for i, (lbl, x, y) in enumerate(blocks):
        r = 5 + i
        vals = [lbl, f'=CORREL({x},{y})', f'=RSQ({y},{x})', f'=COUNT({x})',
                f'=B{r}*SQRT((D{r}-2)/(1-B{r}^2))',
                f'=IF(D{r}>2,T.DIST.2T(ABS(E{r}),D{r}-2),"NA")',
                f'=TEXT(TANH(ATANH(B{r})-NORM.S.INV(1-Alpha/2)/SQRT(D{r}-3)),"0.000")&" ~ "&'
                f'TEXT(TANH(ATANH(B{r})+NORM.S.INV(1-Alpha/2)/SQRT(D{r}-3)),"0.000")']
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.border = BOX
            c.font = Font(size=10.5, name='微软雅黑', color='FF0B5FFF' if j > 1 else 'FF1F2937')
            if j in (2, 3):
                c.number_format = '0.0000'
            if j == 6:
                c.number_format = '0.00E+00'

    # ---- 07 滚动相关 ----
    ws = wb.create_sheet('07_滚动相关')
    ws.sheet_view.showGridLines = False
    title(ws, '滚动相关（窗口内样本不足 80% 留空）', '窗口由「01_参数」的 WinB 控制。', 4)
    hdr(ws, 4, ['日期', '滚动 r（水平）', '有效样本'], [14, 16, 12])
    for i in range(N):
        r = 5 + i
        src = first + i
        s = max(first, src - 4)
        ws.cell(row=r, column=1, value=f'={DR}A{src}').number_format = 'yyyy-mm-dd'
        c = ws.cell(row=r, column=2,
                    value=f'=IF(COUNT({DR}B{s}:B{src})>=2,IFERROR(CORREL({DR}B{s}:B{src},{DR}C{s}:C{src}),""),"")')
        c.number_format = '0.000'
        c.font = Font(size=10.5, name='微软雅黑', color='FF0B5FFF')
        ws.cell(row=r, column=3, value=f'=COUNT({DR}B{s}:B{src})')
        for j in range(1, 4):
            ws.cell(row=r, column=j).border = BOX

    # ---- 08 阶段 ----
    ws = wb.create_sheet('08_阶段')
    ws.sheet_view.showGridLines = False
    title(ws, '阶段统计（改起止日期自动重算）', '阶段必须按产业事件预先定义，不要按结果反复切。', 6)
    hdr(ws, 4, ['阶段', '起', '止', 'N', '上游涨跌', '下游涨跌'], [12, 14, 14, 8, 14, 14])
    segs = [('S1', '2025-01-01', '2025-03-31'), ('S2', '2025-04-01', '2025-06-30')]
    for i, (code, a, b) in enumerate(segs):
        r = 5 + i
        ws.cell(row=r, column=1, value=code)
        ws.cell(row=r, column=2, value=a)
        ws.cell(row=r, column=3, value=b)
        ws.cell(row=r, column=4, value=f'=COUNTIFS({DR}$A${first}:$A${nrow},">="&B{r},{DR}$A${first}:$A${nrow},"<="&C{r})')
        ws.cell(row=r, column=5, value=f'=IFERROR(AVERAGEIFS({DR}$G${first + 1}:$G${nrow},{DR}$A${first + 1}:$A${nrow},">="&B{r},{DR}$A${first + 1}:$A${nrow},"<="&C{r}),"")').number_format = '0.00%'
        ws.cell(row=r, column=6, value=f'=IFERROR(AVERAGEIFS({DR}$H${first + 1}:$H${nrow},{DR}$A${first + 1}:$A${nrow},">="&B{r},{DR}$A${first + 1}:$A${nrow},"<="&C{r}),"")').number_format = '0.00%'
        for j in range(1, 7):
            ws.cell(row=r, column=j).border = BOX

    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    wb.save(OUT)
    # 立刻打补丁：新版函数前缀（否则 PERCENTRANK.INC 等会 #NAME?）
    import xlfn_fix
    n = xlfn_fix.patch(OUT)
    print('written', os.path.abspath(OUT), '| patched sheets:', n)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build()
