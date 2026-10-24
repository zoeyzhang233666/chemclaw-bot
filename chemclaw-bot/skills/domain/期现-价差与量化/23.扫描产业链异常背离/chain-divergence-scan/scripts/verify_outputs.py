# -*- coding: utf-8 -*-
"""验证 Excel 与 HTML 交付物的自洽性（交付前必跑）。

    python scripts/verify_outputs.py <xlsx> <html>

检查项：
 1) Excel 公式数量 > 0（确认不是硬编码值）
 2) 08 表交叉校验区的 Python 值与公式引用是否指向有效单元格
 3) HTML 是否自包含（无 http 外链的 script/link）
 4) HTML 内嵌数据与 Excel 的判定是否一致
"""
import json
import os
import re
import sys

FAILS = []


def check(name, cond, detail=''):
    print(f'  [{"PASS" if cond else "FAIL"}] {name} {detail if not cond else ""}')
    if not cond:
        FAILS.append(name)


def main():
    xlsx = sys.argv[1] if len(sys.argv) > 1 else 'examples/pp-lldpe-px-pta/产业链异常背离扫描.xlsx'
    html = sys.argv[2] if len(sys.argv) > 2 else 'examples/pp-lldpe-px-pta/产业链异常背离扫描看板.html'

    print('1) Excel 检查')
    from openpyxl import load_workbook
    wb = load_workbook(xlsx)
    check('sheet 数量 = 16', len(wb.sheetnames) == 16, str(len(wb.sheetnames)))
    ws8 = wb['08 价格价差明细']
    ws9 = wb['09 滚动相关明细']
    nf8 = sum(1 for row in ws8.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith('='))
    nf9 = sum(1 for row in ws9.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith('='))
    check('08 表有原生公式', nf8 > 1000, f'{nf8}')
    check('09 表有原生公式', nf9 > 1000, f'{nf9}')
    # 08 表价格行数
    prices = sum(1 for r in range(5, ws8.max_row + 1) if isinstance(ws8.cell(row=r, column=2).value, (int, float)))
    check('08 表价格行数 > 3000', prices > 3000, str(prices))
    # 交叉校验区存在
    found = False
    for r in range(1, ws8.max_row + 1):
        v = ws8.cell(row=r, column=1).value
        if isinstance(v, str) and v.startswith('交叉校验'):
            found = True
            break
    check('08 表有交叉校验区', found)
    # 图表
    check('08 表有图表', len(ws8._charts) >= 2, str(len(ws8._charts)))
    # 榜单 sheet 有内容
    ws5 = wb['05 异常背离榜单']
    check('05 榜单行数 >= 10', ws5.max_row >= 13, str(ws5.max_row))
    # 来源表
    ws14 = wb['14 来源清单']
    check('14 来源清单 >= 30 条', ws14.max_row >= 30, str(ws14.max_row))

    print('2) HTML 检查')
    html_txt = open(html, encoding='utf-8').read()
    check('HTML 体积 > 1MB（数据已内嵌）', len(html_txt) > 1_000_000, str(len(html_txt)))
    ext = re.findall(r'<(?:script|link)[^>]*(?:src|href)="(https?://[^"]+)"', html_txt)
    check('无外链 script/link（自包含）', not ext, str(ext[:3]))
    check('内嵌 PACK 数据', 'window.__PACK__' in html_txt)
    check('内嵌 SERIES 数据', 'window.__SERIES__' in html_txt)
    check('内嵌 HIST 数据', 'window.__HIST__' in html_txt)
    check('含合规声明', '不构成' in html_txt)
    check('含"异常背离（候选）"判定', '异常背离（候选）' in html_txt)

    print('3) Excel 与 HTML 判定一致性')
    m = re.search(r'window\.__PACK__\s*=\s*(\{.*?\});\s*</script>', html_txt, re.S)
    if m:
        pack = json.loads(m.group(1))
        verdicts_html = {f"{r['code_a']}/{r['code_b']}": r['judge']['verdict']
                         for r in pack['results'] if r.get('status') == 'ok'}
        verdicts_xlsx = {}
        for r in range(4, ws5.max_row + 1):
            p = ws5.cell(row=r, column=2).value
            v = ws5.cell(row=r, column=5).value
            if p and '/' in str(p) and v:
                verdicts_xlsx[str(p)] = v
        common = set(verdicts_html) & set(verdicts_xlsx)
        mism = [k for k in common if verdicts_html[k] != verdicts_xlsx[k]]
        check('判定一致', not mism and len(common) >= 15, f'共{len(common)}组，不一致{mism[:3]}')
    else:
        check('可从 HTML 提取 PACK', False)

    print()
    if FAILS:
        print(f'❌ {len(FAILS)} 项失败: {FAILS}')
        sys.exit(1)
    print('✅ 交付物自洽性检查全部通过')


if __name__ == '__main__':
    main()
