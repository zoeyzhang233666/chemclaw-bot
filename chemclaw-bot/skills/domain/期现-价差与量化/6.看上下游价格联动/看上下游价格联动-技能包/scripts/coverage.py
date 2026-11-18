# -*- coding: utf-8 -*-
"""coverage.py —— 已抓取 SunSirs 日页的连续性统计（看缺哪天、能否凑出研究窗口）"""
import glob
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
pat = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'raw', 'sst_20*.html')
dates = []
for p in glob.glob(pat):
    m = re.search(r'sst_(\d{4}-\d{2}-\d{2})\.html', p)
    if m:
        dates.append(m.group(1))
dates = sorted(set(dates))
print('files with date:', len(dates))
import datetime as dt
d = dt.date(2023, 1, 1)
have, miss_streak, miss = 0, [], []
while d <= dt.date(2026, 10, 20):
    if d.isoformat() in dates:
        have += 1
        if miss:
            miss_streak.append((miss[0], miss[-1], len(miss)))
            miss = []
    else:
        miss.append(d.isoformat())
    d += dt.timedelta(days=1)
if miss:
    miss_streak.append((miss[0], miss[-1], len(miss)))
print('have:', have, '/', (dt.date(2026, 10, 20) - dt.date(2023, 1, 1)).days + 1)
print('gap runs:', len(miss_streak), 'largest:', sorted(miss_streak, key=lambda x: -x[2])[:5])
