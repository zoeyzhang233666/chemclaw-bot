# -*- coding: utf-8 -*-
"""mkurls_jobs.py —— 直接按 URL 列表生成 jobs（日期页面专用）"""
import datetime as dt
import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
prefix = sys.argv[2]
start = dt.date.fromisoformat(sys.argv[3])
end = dt.date.fromisoformat(sys.argv[4])
base = sys.argv[5] if len(sys.argv) > 5 else 'https://www.sunsirs.com/uk/sdetail-day-{y}-{md}.html'
jobs = []
d = start
while d <= end:
    url = base.format(y=d.year, md=d.strftime('%m%d'))
    jobs.append({'url': url, 'out': os.path.join(here, 'raw', f'sst_{d.isoformat()}.html')})
    d += dt.timedelta(days=1)
with open(out, 'w', encoding='utf-8') as f:
    json.dump(jobs, f, ensure_ascii=False, indent=1)
print(len(jobs), 'jobs')
