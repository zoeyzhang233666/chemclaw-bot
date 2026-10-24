#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态检查工作簿：不符合以下任一条，Excel/WPS 可能打不开或显示 #REF!。

1. 合并区域必须 ≥2 个单元格
2. 所有 merge 不得重叠
3. 不得出现 0 长度合并（如 A5:A5）
4. 公式中不得出现 openpyxl 无法识别的裸文本
5. 工作表名不得含 : \\ / ? * [ ]
6. 公式中的跨表引用必须指向已存在的工作表
"""
import re
import sys

import openpyxl

BAD_SHEET = re.compile(r'[:\\/?*\[\]]')
REF = re.compile(r"'([^']+)'!|\b([A-Za-z\u4e00-\u9fa5][\w\u4e00-\u9fa5]*)!")


def main(path):
    wb = openpyxl.load_workbook(path)
    errs, warns = [], []
    names = set(wb.sheetnames)
    for s in wb.sheetnames:
        if BAD_SHEET.search(s):
            errs.append('表名含非法字符：%s' % s)
    for ws in wb.worksheets:
        cells = set()
        for rng in ws.merged_cells.ranges:
            n = (rng.max_row - rng.min_row + 1) * (rng.max_col - rng.min_col + 1)
            if n < 2:
                errs.append('%s!%s 是单格合并（非法）' % (ws.title, rng))
            overlap = False
            for r in range(rng.min_row, rng.max_row + 1):
                for c in range(rng.min_col, rng.max_col + 1):
                    if (r, c) in cells:
                        overlap = True
                    cells.add((r, c))
            if overlap:
                errs.append('%s!%s 与其他合并区域重叠' % (ws.title, rng))
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str) and v.startswith('='):
                    if v.count('"') % 2:
                        errs.append('%s!%s 公式引号不成对：%s' % (ws.title, cell.coordinate, v[:80]))
                    for m in REF.finditer(v):
                        tgt = (m.group(1) or m.group(2) or '').strip()
                        if tgt and tgt not in names and not tgt.isupper() is None:
                            if tgt not in names:
                                warns.append('%s!%s 引用未找到的表：%s' % (ws.title, cell.coordinate, tgt))
    print('工作表 %d 个：%s' % (len(wb.sheetnames), ' / '.join(wb.sheetnames)))
    for e in errs:
        print('  [ERROR] ' + e)
    for w in warns[:10]:
        print('  [WARN ] ' + w)
    print('静态检查：%d error / %d warn' % (len(errs), len(warns)))
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
