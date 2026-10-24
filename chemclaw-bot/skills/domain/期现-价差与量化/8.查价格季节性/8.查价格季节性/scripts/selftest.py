# -*- coding: utf-8 -*-
"""selftest.py — 引擎不变式自检（不依赖具体品种数据）

覆盖：
  1. 分位算法与 numpy / Excel PERCENTILE.INC 口径一致
  2. ISO 周 53 折叠规则
  3. 缺口不补造：缺失位置在 rows 中为 status=missing，在 stats 的 years_missing 中出现
  4. 线性趋势被归一化消除（构造每年稳定上涨 24% 的合成序列，归一化分位带应几乎水平）
  5. 异常年识别：人为注入一年极端值，必须被 flags 捕获，且不自动删除
  6. 现有年份按窗口第一天开盘归一化（不是 1 月 1 日插值）
  7. 分位单调性：p10 <= p25 <= p50 <= p75 <= p90
  8. 样本门槛：n < min_years 时 n_sufficient=False
"""
import math
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import seasonality_core as sc

FAILS = []


def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print('  [%s] %s %s' % (status, name, detail))
    if not cond:
        FAILS.append(name)


print('1) 经验分位与 numpy linear / Excel PERCENTILE.INC 一致')
v = [2015.0, 2350.5, 2602.25, 3100.0, 4733.33]
for q in (10, 25, 50, 75, 90):
    a = sc.pctile(v, q)
    b = float(np.percentile(v, q, method='linear'))
    check('p%d' % q, abs(a - b) < 1e-9, '%s vs %s' % (a, b))

print('2) ISO 周 53 折叠')
check('week53->52', sc.norm_iso_week(2026, 53) == 52 and sc.norm_iso_week(2026, 52) == 52)
# 2026-01-01 是周四 -> 2026 有 ISO 第 53 周
y, w, _ = date(2026, 12, 31).isocalendar()
check('2026 has ISO wk53', w == 53, '2026-12-31 -> W%d' % w)

print('3) 缺口不补造（构造 2023-03 整月缺失）')
daily = []
d = date(2023, 1, 2)
while d <= date(2023, 12, 29):
    if not (date(2023, 3, 1) <= d <= date(2023, 3, 31)):
        daily.append({'date': d.isoformat(), 'price': 2500 + (d.timetuple().tm_yday) * 0.5})
    d += timedelta(days=1)
# 再补一年，满足样本门槛
d = date(2024, 1, 2)
while d <= date(2024, 12, 31):
    daily.append({'date': d.isoformat(), 'price': 2300 + (d.timetuple().tm_yday) * 0.6})
    d += timedelta(days=1)
d = date(2025, 1, 2)
while d <= date(2025, 9, 30):
    daily.append({'date': d.isoformat(), 'price': 2100 + (d.timetuple().tm_yday) * 0.7})
    d += timedelta(days=1)
dec, dups = sc.load_daily(daily)
r = sc.analyze(dict(id='t', title='t', current_year=2025, caliber_requested='x',
                    caliber_obtained='x', unit='元/吨', tax='na', min_years_for_stats=3),
               dec, 'monthly')
march = [x for x in r['raw_rows'] if x['year'] == 2023 and x['position'] == 3]
ms = [x for x in r['stats'] if x['position'] == 3][0]
check('3月2023 记为 missing', bool(march) and march[0]['status'] == 'missing' and march[0]['value'] is None)
check('3月统计 years_missing 含 2023', 2023 in ms['years_missing'] and ms['n_years'] == 2)
check('3月 n<3 标记样本不足', ms['n_sufficient'] is False)
check('无插值（3月没有凭空出现数值）', ms['mean'] is not None and 2023 not in ms['years'])

print('4) 线性趋势被归一化消除')
daily = []
for yr, base in [(2022, 2000), (2023, 2400), (2024, 2880), (2025, 3456)]:
    d = date(yr, 1, 3)
    while d <= date(yr, 12, 30):
        doy = (d - date(yr, 1, 1)).days
        daily.append({'date': d.isoformat(), 'price': round(base * (1 + 0.24 * doy / 365.0), 2)})
        d += timedelta(days=1)
dec, _ = sc.load_daily(daily)
r = sc.analyze(dict(id='t2', title='t2', current_year=2025, caliber_requested='x',
                    caliber_obtained='x', unit='元/吨', tax='na'), dec, 'monthly')
rebs = [x['p90'] - x['p10'] for x in r['reb_stats']]
raws = [x['mean'] for x in r['stats']]
check('4期归一化后分位带宽≈0', max(rebs) < 1.0, 'max p90-p10 = %.3f (归一化, 基准100)' % max(rebs))
check('4期绝对价格均值随年份抬升', raws[-1] > raws[0] * 1.12, '%.0f -> %.0f' % (raws[0], raws[-1]))
b = r['years'][0]['base']
check('4期基准=窗口首个有效观测', b['date'].startswith('2022-01-0'), str(b))

print('5) 异常年识别（5年样本，基准年正常；2024 年 7-9 月出现单点尖峰）')
daily = []
for yr in (2021, 2022, 2023, 2024, 2025):
    d = date(yr, 1, 3)
    while d <= date(yr, 12, 30):
        doy = (d - date(yr, 1, 1)).days
        p = 2500 + 300 * math.sin(2 * math.pi * doy / 365)
        if yr == 2024 and 181 <= doy <= 273:          # 7-9 月单点尖峰（持续约3个月）
            p = 4300
        daily.append({'date': d.isoformat(), 'price': round(p, 2)})
        d += timedelta(days=1)
dec, _ = sc.load_daily(daily)
r = sc.analyze(dict(id='t3', title='t3', current_year=2025, caliber_requested='x',
                    caliber_obtained='x', unit='元/吨', tax='na'), dec, 'monthly')
an = {x['year']: x for x in r['anomaly']['yearly']}
check('2024 被判为 anomaly/relevant', an[2024]['grade'] in ('anomaly', 'relevant'),
      '%s %s' % (an[2024]['grade'], an[2024]['flags']))
check('其余年份未被误判为 anomaly',
      all(an[y]['grade'] != 'anomaly' for y in (2021, 2022, 2023, 2025)),
      str({y: an[y]['grade'] for y in (2021, 2022, 2023, 2025)}))
check('异常年仍保留在样本内（未自动删除）',
      all(2024 in st['years'] for st in r['stats']) and '2024' in r['raw_series'])
rob = [x for st in r['stats'] for x in st.get('outlier_years', [])]
check('给出剔除后均值变化 (对统计均值的影响可量化)',
      bool(rob) and all('shift' in x for x in rob), 'n_outlier_pos=%d' % len(rob))

print('6) 分位单调性')
bad = 0
for st in r['stats']:
    if st['p10'] is None:
        continue
    seq = [st['p10'], st['p25'], st['p50'], st['p75'], st['p90']]
    if any(a > b_ + 1e-9 for a, b_ in zip(seq, seq[1:])):
        bad += 1
check('p10<=p25<=p50<=p75<=p90 全部成立', bad == 0, 'violations=%d' % bad)

print('7) 当前年位置：剔除当前年本身')
r2 = sc.analyze(dict(id='t4', title='t4', current_year=2025, caliber_requested='x',
                     caliber_obtained='x', unit='元/吨', tax='na'), dec, 'monthly')
c = [x for x in r2['current'] if x['n_hist']][0]
check('历史样本不含当前年', 2025 not in c['hist_years'], str(c['hist_years']))

print('8) 数据审计：重复日期与空值')
dec, dups = sc.load_daily([('2024-01-02', 1), ('2024-01-02', 1), ('2024-01-03', ''), ('2024/01/04', 3)])
check('重复日期被识别', dups == ['2024-01-02'], str(dups))
check('空值被跳过', [x['price'] for x in dec] == [1.0, 3.0])

print('\n结果: %d 项失败' % len(FAILS))
if FAILS:
    print('失败项:', FAILS)
    sys.exit(1)
print('全部通过')
