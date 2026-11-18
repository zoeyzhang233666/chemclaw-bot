# -*- coding: utf-8 -*-
"""validate_sources.py —— 两个独立数据源的一致性校验 + 日期错位诊断

诊断背景：SunSirs 英文站日页标题日期 = 100ppi 中文基准价「翌日」的日期（观察发现），
需要判断是 (a) 英文站滞后一天发布，还是 (b) 中文站提前一天发布。
方法：在重叠区间内，比较「同日对齐」与「错一天对齐」的平均绝对差，取小者为对齐方式，
并把结论写入 data_meta（报告与 Excel 的口径表里必须写明）。
"""
import csv
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))


def load(kind):
    rows = list(csv.DictReader(open(os.path.join(here, 'raw', f'{kind}_bjz_daily.csv'), encoding='utf-8-sig')))
    return {r['date']: float(r['value']) for r in rows}


def report(ss, ref, col):
    same = [(r['date'], float(r[col]), ref[r['date']]) for r in ss if r['date'] in ref and r[col]]
    # 错一天：SunSirs(d) 对 100ppi(d+1)
    import datetime as dt
    shifted = []
    for r in ss:
        if not r[col]:
            continue
        d = (dt.date.fromisoformat(r['date']) + dt.timedelta(days=1)).isoformat()
        if d in ref:
            shifted.append((r['date'], float(r[col]), ref[d]))
    out = {}
    for name, both in (('same_day', same), ('ss_vs_prev_day', shifted)):
        if not both:
            out[name] = None
            continue
        dif = [abs(a - b) for _, a, b in both]
        out[name] = {'n': len(both), 'exact': sum(1 for x in dif if x <= 0.5),
                     'mean_abs': round(sum(dif) / len(dif), 3), 'max_abs': round(max(dif), 2)}
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ss = list(csv.DictReader(open(os.path.join(here, 'processed', 'sunsirs_daily.csv'), encoding='utf-8-sig')))
    for col in ('px', 'pta'):
        ref = load(col)
        print(col, report(ss, ref, col))
