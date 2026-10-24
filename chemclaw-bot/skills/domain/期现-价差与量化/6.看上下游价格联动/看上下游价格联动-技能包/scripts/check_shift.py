# -*- coding: utf-8 -*-
"""check_shift.py —— 用重叠期验证 SunSirs 页面日期到价格交易日的偏移方向

比较两种假设的平均绝对差：
  shift=0：页面日期 d 的价格 = 交易日 d
  shift=+1：页面日期 d 的价格 = 交易日 d+1（即页面按报道日归档）
取差异更小的假设作为口径。
"""
import csv
import datetime as dt
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path, col):
    out = {}
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r.get(col) in (None, ''):
                continue
            try:
                out[dt.date.fromisoformat(r['date'])] = float(r[col])
            except (ValueError, KeyError):
                continue
    return out


ss = load(os.path.join(HERE, 'processed', 'sunsirs_daily.csv'), 'px')
ref = load(os.path.join(HERE, 'raw', 'px_bjz_daily.csv'), 'value')

for shift in (0, 1, -1):
    diffs = []
    for d, v in ref.items():
        target = d + dt.timedelta(days=shift)
        if target in ss:
            diffs.append(abs(ss[target] - v))
    if diffs:
        n = len(diffs)
        print(f'shift={shift:+d}  N={n:4d}  mean|Δ|={sum(diffs)/n:8.3f}  '
              f'max|Δ|={max(diffs):9.2f}  exact={sum(1 for x in diffs if x < 0.005)}')

# PTA 同样检验
ss_p = load(os.path.join(HERE, 'processed', 'sunsirs_daily.csv'), 'pta')
ref_p = load(os.path.join(HERE, 'raw', 'pta_bjz_daily.csv'), 'value')
print()
for shift in (0, 1, -1):
    diffs = []
    for d, v in ref_p.items():
        target = d + dt.timedelta(days=shift)
        if target in ss_p:
            diffs.append(abs(ss_p[target] - v))
    if diffs:
        n = len(diffs)
        print(f'PTA shift={shift:+d}  N={n:4d}  mean|Δ|={sum(diffs)/n:8.3f}  '
              f'max|Δ|={max(diffs):9.2f}  exact={sum(1 for x in diffs if x < 0.005)}')
