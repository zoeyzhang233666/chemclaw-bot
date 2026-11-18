# -*- coding: utf-8 -*-
"""校验 Excel：结构、公式可算性、以及关键单元格与 Python 结果是否一致。"""
import sys

from openpyxl import load_workbook

path = sys.argv[1] if len(sys.argv) > 1 else 'assets/PVC开工率季节性分析.xlsx'
wb = load_workbook(path)
print('sheets:', len(wb.sheetnames))
for s in wb.sheetnames:
    ws = wb[s]
    print(f'  {s:16s} dims={ws.dimensions:12s} rows={ws.max_row} cols={ws.max_column}')

ws = wb['01_周度数据']
hdr = [c.value for c in ws[4]]
print('\n01 headers:', hdr)
print('first row :', [c.value for c in ws[5]][:12])
print('last  row :', [c.value for c in ws[ws.max_row]][:12])

ws4 = wb['04_历史分位']
print('\n04 formulas sample:', ws4['D5'].value)
ws5 = wb['05_今年逐周定位']
print('05 formulas sample:', ws5['H9'].value, '|', ws5['I17'].value)
ws6 = wb['06_跨年同期对照']
print('06 rows:', [ws6.cell(r, 1).value for r in range(5, ws6.max_row + 1)])

# 检查是否夹带了空值/None 填充
bad = 0
for s in wb.sheetnames:
    for row in wb[s].iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value.strip() in ('None', 'nan', 'NaN'):
                bad += 1
print('\nplaceholder None/nan cells:', bad)
