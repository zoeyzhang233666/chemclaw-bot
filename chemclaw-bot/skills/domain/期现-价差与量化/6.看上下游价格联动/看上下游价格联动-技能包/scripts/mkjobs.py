# -*- coding: utf-8 -*-
"""mkjobs.py —— 为 cdp_fetch.js 生成 jobs JSON（避免 PowerShell 字符串转义坑）"""
import argparse
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--site', default='https://www.100ppi.com/news')
ap.add_argument('--tmpl', default='/', help='URL 模板，用 {p} 表示页码；只用 --urls 时可留空')
ap.add_argument('--pages', default='', help='逗号分隔页码，或 a-b')
ap.add_argument('--prefix', required=True, help='输出文件名前缀')
ap.add_argument('--dir', default='raw')
ap.add_argument('--urls', default='', help='额外完整 URL（逗号分隔，文件名自动派生）')
a = ap.parse_args()

here = os.path.dirname(os.path.abspath(__file__))
outdir = os.path.join(here, a.dir)
pages = []
if a.pages:
    if '-' in a.pages:
        lo, hi = a.pages.split('-')
        pages = list(range(int(lo), int(hi) + 1))
    else:
        pages = [int(x) for x in a.pages.split(',') if x]

jobs = []
for p in pages:
    jobs.append({'url': (a.site + a.tmpl).format(p=p),
                 'out': os.path.join(outdir, f'{a.prefix}_{p:04d}.html')})
for u in [u for u in a.urls.split(',') if u]:
    tag = u.rstrip('/').split('/')[-1].replace('.', '_')
    jobs.append({'url': u, 'out': os.path.join(outdir, f'{a.prefix}_{tag}.html')})

with open(a.out, 'w', encoding='utf-8') as f:
    json.dump(jobs, f, ensure_ascii=False, indent=1)
print(len(jobs), 'jobs ->', a.out)
