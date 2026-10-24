# -*- coding: utf-8 -*-
"""archive.py — 多年度「历史归档」构建器

背景
----
100ppi 商品栏目只保留最近 ~10 页（约 6 个月）文章。若某品种的「市场基差」稿
早于栏目窗口，就无法靠栏目回溯。此时的做法是：

  * 按周遍历该品种栏目整页（7 页可覆盖约 1.4 个月），按周期增量抓取，
    把结果累积进 data/archive/spot_{code}.csv；
  * 每次运行都合并到同一文件（按日期去重），因此**每周跑一次即可逐步攒出
    3 年长历史**；
  * scan.py 读取逻辑：优先 data/archive/spot_{code}.csv，没有再读 data/raw/spot/{code}.csv，
    并在覆盖核验表里如实标注来源与样本长度。

诚实边界：本工具不制造历史数据。没有归档就只扫已有窗口，并把「样本不足」写清楚。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

from .http import Http
from .fetch_spot import FIELDS, fetch_product, save

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def merge_into_archive(new_rows: list[dict], path: str) -> int:
    old = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                old[r['date']] = r
    for r in new_rows:
        old[r['date']] = {k: r.get(k, '') for k in FIELDS}
    merged = [old[d] for d in sorted(old)]
    save(merged, path)
    return len(merged)


def main(argv=None):
    ap = argparse.ArgumentParser(description='增量归档 100ppi 现货基准价（每周运行即可累积长历史）')
    ap.add_argument('--codes', default='')
    ap.add_argument('--max-pages', type=int, default=14)
    ap.add_argument('--dir', default='data/archive')
    ap.add_argument('--cache', default='data/cache')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    from .products import load_pool
    pool = load_pool()
    codes = [c.strip().upper() for c in a.codes.split(',') if c.strip()]
    if codes:
        pool = [p for p in pool if p['code'] in codes]
    http = Http(cache_dir=a.cache)
    os.makedirs(a.dir, exist_ok=True)
    for prod in pool:
        rows = fetch_product(http, prod, max_pages=a.max_pages, verbose=False)
        path = os.path.join(a.dir, 'spot_%s.csv' % prod['code'])
        n = merge_into_archive(rows, path) if rows else 0
        ds = [r['date'] for r in rows]
        print('[archive] %-3s new=%3d total=%4d %s' % (
            prod['code'], len(rows), n, ('%s..%s' % (min(ds), max(ds))) if ds else '-'),
            flush=True)


if __name__ == '__main__':
    main()
