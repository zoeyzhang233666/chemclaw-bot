# -*- coding: utf-8 -*-
"""
verify_excel.py —— 校验工作簿：结构、公式、以及「Excel 算出来的结果 == Python 算出来的结果」

用法
  python verify_excel.py <workbook.xlsx> <analysis.json> [recalc.xlsx]

流程
  1. 用 openpyxl 读回文件，检查表名、公式数量、命名区域；
  2. 若有 recalc.xlsx（LibreOffice 重算后的副本），比对关键单元格与 analysis.json；
  3. 任何不一致 → 退出码 1（可直接用于 CI）。

为什么必须做「重算后比对」：openpyxl 写入公式不会计算，data_only=True 读到的是空的。
只有真正重算一遍，才能证明公式本身是对的，而不是「看起来对」。
"""
import json
import os
import sys

import openpyxl

TOL_R = 5e-4      # 相关系数容差
TOL_Y = 1.0       # 元/吨容差
TOL_P = 1e-6      # p 值容差（相对）


def close(a, b, tol):
    if a is None or b is None:
        return False
    return abs(a - b) <= tol * max(1.0, abs(b))


def main(argv):
    xlsx, ajson = argv[1], argv[2]
    recalc = argv[3] if len(argv) > 3 else None
    A = json.load(open(ajson, encoding='utf-8'))
    wb = openpyxl.load_workbook(xlsx)  # 公式视图
    problems, checks = [], []

    need = ['00_说明', '01_口径与来源', '02_参数', '03_原始数据', '04_单耗台账', '05_单耗敏感性',
            '06_加工价差', '07_历史分位', '08_相关性', '09_滚动相关', '10_领先滞后',
            '11_阶段与背离', '12_公式说明']
    missing = [s for s in need if s not in wb.sheetnames]
    if missing:
        problems.append(f'缺少工作表: {missing}')

    n_formulas = sum(1 for ws in wb.worksheets for row in ws.iter_rows() for c in row
                     if isinstance(c.value, str) and c.value.startswith('='))
    checks.append(('工作表数', len(wb.sheetnames)))
    checks.append(('公式单元格数', n_formulas))
    checks.append(('命名区域', len(list(wb.defined_names.keys())) if hasattr(wb.defined_names, 'keys')
                   else len(wb.defined_names)))
    if n_formulas < 500:
        problems.append(f'公式数量偏少（{n_formulas}），可能被硬编码为数值')

    # 生成器与 Python 结果一致性（不依赖重算）
    checks.append(('analysis N', A['meta']['n_obs']))

    if recalc and os.path.exists(recalc):
        r = openpyxl.load_workbook(recalc, data_only=True)
        c8 = r['08_相关性']
        pairs = [
            ('水平 r', c8['B5'].value, A['corr']['level']['r'], TOL_R),
            ('水平 N', c8['D5'].value, A['corr']['level']['n'], 0),
            ('收益率 r', c8['B6'].value, A['corr']['return']['r'], TOL_R),
            ('收益率 p', c8['F6'].value, A['corr']['return']['p'], TOL_P),
            ('水平 p', c8['F5'].value, A['corr']['level']['p'], TOL_P),
            ('水平 CI 下', c8['G5'].value, A['corr']['level']['ci95'][0], TOL_R),
            ('水平 CI 上', c8['H5'].value, A['corr']['level']['ci95'][1], TOL_R),
        ]
        for name, got, want, tol in pairs:
            ok = (got == want) if tol == 0 else close(got, want, tol)
            checks.append((f'Excel {name}', got, want, 'OK' if ok else 'MISMATCH'))
            if not ok:
                problems.append(f'{name}: Excel={got} vs Python={want}')

        c7 = r['07_历史分位']
        qcheck = [('P10', c7['B8'].value, A['spread']['quantiles']['0.1']),
                  ('P50', c7['E5'].value, A['spread']['quantiles']['0.5']),
                  ('P90', c7['E7'].value, A['spread']['quantiles']['0.9'])]
        for name, got, want in qcheck:
            # analysis.json 里的分位已四舍五入到 2 位，Excel 算的是全精度，容差取 0.005
            ok = close(got, want, 1e-6) or (got is not None and want is not None
                                            and abs(got - want) <= 0.005)
            checks.append((f'Excel 分位 {name}', got, want, 'OK' if ok else 'MISMATCH'))
            if not ok:
                problems.append(f'分位 {name}: Excel={got} vs Python={want}')

        c11 = r['11_阶段与背离']
        for i, p in enumerate(A['phases']):
            row = 5 + i
            got_n = c11.cell(row=row, column=5).value
            if got_n != p['n']:
                problems.append(f"阶段 {p['code']} N: Excel={got_n} vs Python={p['n']}")
            else:
                checks.append((f"Excel 阶段 {p['code']} N", got_n, p['n'], 'OK'))

        # 任何残留错误值都算失败
        errs = []
        for ws in r.worksheets:
            if ws.title.endswith('公式说明'):  # 该表是纯文本的公式对照说明，不是可计算单元格
                continue
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith('#') and c.value.endswith(('!', '?', 'A')):
                        errs.append(f'{ws.title}!{c.coordinate}={c.value}')
        if errs:
            problems.append(f'重算后仍有错误值 {len(errs)} 处，例：{errs[:6]}')
        else:
            checks.append(('重算后错误值', 0, 'OK'))

    for item in checks:
        print(' | '.join(str(x) for x in item))
    if problems:
        print('\nFAIL:')
        for p in problems:
            print('  -', p)
        return 1
    print('\nALL CHECKS PASSED')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv))
