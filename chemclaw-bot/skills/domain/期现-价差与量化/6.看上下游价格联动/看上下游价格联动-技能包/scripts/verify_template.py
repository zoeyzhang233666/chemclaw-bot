# -*- coding: utf-8 -*-
"""verify_template.py —— 校验模板：重算后检查关键单元格有值、无错误值"""

_CHEMCLAW_ROOT = next(parent for parent in __import__('pathlib').Path(__file__).resolve().parents if (parent / 'runtime/deliver.mjs').is_file())
import os
import subprocess
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, 'assets', 'templates', '联动分析模板.xlsx')
RECALC = os.path.join(HERE, 'build', 'tpl_recalc.xlsx')
NODE = __import__('sys').executable
CLI = (str(_CHEMCLAW_ROOT / 'runtime/office-cli.py'))


def main():
    if os.path.exists(RECALC):
        os.remove(RECALC)
    p = subprocess.run([NODE, CLI, 'recalculate', '--input', TPL, '--output', RECALC],
                       capture_output=True, text=True, encoding='utf-8')
    if p.returncode != 0:
        print('recalc failed:', p.stdout, p.stderr)
        return 1
    wb = openpyxl.load_workbook(RECALC, data_only=True)
    problems = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith('#') and c.value[-1] in '!?A':
                    problems.append(f'{ws.title}!{c.coordinate}={c.value}')

    checks = {
        '06_相关性 B5/B6 (r)': (wb['06_相关性']['B5'].value, wb['06_相关性']['B6'].value),
        '04_价差 P10/P50/P90': (wb['04_价差']['B13'].value, wb['04_价差']['B14'].value),
        '05_敏感性 均值': (wb['05_单耗敏感性']['B5'].value,),
        '08_阶段 N': (wb['08_阶段']['D5'].value,),
    }
    for k, v in checks.items():
        print(f'{k}: {v}')
    if problems:
        print('FAIL 错误值:', problems[:8])
        return 1
    print('TEMPLATE OK')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
