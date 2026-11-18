# -*- coding: utf-8 -*-
"""check_xlsx.py — 工作簿结构与数据一致性校验。

两层：
  A) 结构：表齐全、表头非空、无未替换占位符、无禁用词（预测类）
  B) 数据：Excel 公式重算结果 vs 引擎 JSON（均值/中位数/分位/n）逐项比对
     —— 这是最容易被手改破坏的一环。

用法: python check_xlsx.py <xlsx> <case_id> [--recalc out/_recalc.xlsx]
"""
import argparse
import json
import os
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')

REQUIRED = ['00封面与口径', '01日度价格', '02周度面板', '03月度面板', '04周次映射规则',
            '05周度统计', '06月度统计', '07归一化面板', '08当前年位置',
            '09异常年证据', '10样本覆盖', '11数据缺口', '12来源与复现']
FORBIDDEN = ['预计涨', '预计跌', '看涨', '看跌', '必然', '将会涨', '将会跌', '抄底', '底部已现']
FAILS = []


def ck(name, cond, detail=''):
    print('  [%s] %s %s' % ('PASS' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    ap.add_argument('case')
    ap.add_argument('--recalc', default='')
    a = ap.parse_args()
    d = json.load(open(os.path.join(DATA, 'out', '%s.json' % a.case), encoding='utf-8'))

    print('A) 结构')
    wb = openpyxl.load_workbook(a.xlsx, data_only=False)
    names = wb.sheetnames
    missing = [s for s in REQUIRED if s not in names]
    ck('13 张表齐全', not missing, str(missing))
    ck('表数量正确', len(names) == len(REQUIRED), 'n=%d' % len(names))

    total_cells, total_formulas, hits = 0, 0, []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is None:
                    continue
                total_cells += 1
                if isinstance(c.value, str):
                    if c.value.startswith('='):
                        total_formulas += 1
                    for f in FORBIDDEN:
                        if f in c.value:
                            hits.append((ws.title, c.coordinate, f))
    ck('单元格有内容', total_cells > 1500, 'cells=%d' % total_cells)
    ck('含活公式（不是死数）', total_formulas >= 200, 'formulas=%d' % total_formulas)
    ck('无预测类禁用词', not hits, str(hits[:3]))
    ph = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and '__' in c.value and 'ERR' in c.value:
                    ph.append((ws.title, c.coordinate))
    ck('无未替换占位符', not ph, str(ph[:3]))

    print('B) 公式重算值 vs 引擎（同源一致性）')
    if not a.recalc or not os.path.exists(a.recalc):
        print('  [SKIP] 未提供重算文件，跳过数值一致性校验')
    else:
        rc = openpyxl.load_workbook(a.recalc, data_only=True)
        for freq, sheet, sname in (('weekly', '05周度统计', '周度'), ('monthly', '06月度统计', '月度')):
            ws = rc[sheet]
            stats = {s['position']: s for s in d[freq]['stats']}
            bad = []
            checked = 0
            for r in range(4, 4 + len(stats)):
                pos = ws.cell(row=r, column=1).value
                if pos is None or pos not in stats:
                    continue
                s = stats[pos]
                got = {k: ws.cell(row=r, column=c).value
                       for k, c in (('n', 3), ('mean', 4), ('median', 5), ('p10', 9),
                                    ('p25', 10), ('p50', 11), ('p75', 12), ('p90', 13))}
                checked += 1
                if got['n'] != s['n_years']:
                    bad.append((pos, 'n', got['n'], s['n_years']))
                for k in ('mean', 'median', 'p10', 'p25', 'p75', 'p90'):
                    if got[k] is None or abs(float(got[k]) - float(s[k])) > 0.02:
                        bad.append((pos, k, got[k], s[k]))
            ck('%s统计：Excel 重算 = 引擎（%d 个位置逐项）' % (sname, checked), not bad,
               str(bad[:4]))

        # 面板：抽若干格与原始 CSV 对
        import csv
        rows = list(csv.DictReader(open(os.path.join(DATA, 'cases', a.case, 'price_daily.csv'),
                                        encoding='utf-8-sig')))
        last = {y: v['price'] for y, v in
                {r['date'][:4]: r for r in rows}.items()}
        ws2 = rc['02周度面板']
        cur = d['meta']['current_year']
        ck('面板含当前年行', any(ws2.cell(row=r, column=1).value == cur
                              for r in range(4, 4 + len(d['weekly']['years']))))
        ws1 = rc['01日度价格']
        ck('日度表行数 = CSV 行数',
           ws1.max_row - 3 == len(rows), 'xlsx=%d csv=%d' % (ws1.max_row - 3, len(rows)))
        v0 = ws1.cell(row=4, column=4).value
        ck('首行价格与 CSV 一致', abs(float(v0) - float(rows[0]['price'])) < 1e-6,
           '%s vs %s' % (v0, rows[0]['price']))

        ws8 = rc['08当前年位置']
        cur_rows = [r for r in range(4, ws8.max_row + 1)
                    if ws8.cell(row=r, column=1).value is not None]
        ck('当前年位置表有数据行', len(cur_rows) > 0, 'rows=%d' % len(cur_rows))

        print('C) 图表与可读性')
        ck('周度面板含折线图', len(wb['02周度面板']._charts) >= 1)
        ck('封面写了口径降级', any('降级' in str(c.value)
                              for row in wb['00封面与口径'].iter_rows() for c in row))
        ck('缺口表列出不可得口径', any('未取得' in str(c.value)
                                for row in wb['11数据缺口'].iter_rows() for c in row))

    print('\n结果: %d 项失败' % len(FAILS))
    if FAILS:
        print('失败:', FAILS)
        sys.exit(1)
    print('全部通过')


if __name__ == '__main__':
    main()
