# -*- coding: utf-8 -*-
"""
parse_100ppi.py —— 从生意社(100ppi)已渲染列表页中提取「基准价」日度报价。

输入：raw/px_*.html、raw/pta_*.html（CDP 渲染后的 HTML，UTF-8）
输出：
  raw/px_bjz_daily.csv   列: date,publish_dt,value,unit,title,url,page
  raw/pta_bjz_daily.csv
  raw/parse_report.json  各页提取到的行数、缺失页、日期覆盖

说明（口径红线）：
  - 只抽取标题形如「X月X日生意社PX基准价为N元/吨」的条目；不做任何插值/填充。
  - 同一日期若出现多条（重复抓取或补发），保留发布最早的一条，并在 report 中记录重复。
  - 日期以标题中的「M月D日」为准，年份取详情页 URL 中的 YYYYMMDD；两者就日
    数据每日发布，据此换算交易日。
  - 非交易日（周六周日）发布的条目单独标记，默认不进入日频序列（可在 QC 中复核）。
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

ROW_RE = re.compile(
    r'detail-(\d{8})-(\d+)\.html"\s+target="_blank"\s+class="blueq">([^<]+)</a>\s*'
    r'<span>(\d{4}-\d\d-\d\d \d\d:\d\d)</span>'
)
BZ_RE = re.compile(r'(\d{1,2})月(\d{1,2})日生意社\s*([A-Za-z]+)\s*基准价为\s*([\d.]+)\s*(元/吨)')


def parse_page(path, product):
    with open(path, encoding='utf-8') as f:
        html = f.read()
    out = []
    for m in ROW_RE.finditer(html):
        url_date, news_id, title, pub = m.groups()
        b = BZ_RE.search(title)
        if not b:
            continue
        mm, dd, prod_name, val, unit = b.groups()
        if prod_name.upper() != product.upper():
            continue
        y = int(url_date[:4])
        try:
            d = dt.date(y, int(mm), int(dd))
        except ValueError:
            continue
        # 跨年保护：若标题月份明显大于 URL 月份（如 1 月标题配 12 月 URL），回退一年
        url_m = int(url_date[4:6])
        if int(mm) - url_m > 6:
            d = dt.date(y - 1, int(mm), int(dd))
        elif url_m - int(mm) > 6:
            d = dt.date(y + 1, int(mm), int(dd))
        out.append({
            'date': d.isoformat(),
            'publish_dt': pub,
            'value': float(val),
            'unit': unit,
            'title': title,
            'url': f'https://www.100ppi.com/news/detail-{url_date}-{news_id}.html',
            'page': os.path.basename(path),
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default='raw')
    ap.add_argument('--out', default='raw')
    a = ap.parse_args(argv)

    report = {}
    for product, pat in (('PX', 'px_*.html'), ('PTA', 'pta_*.html')):
        rows, pages, empty = [], 0, []
        for path in sorted(glob.glob(os.path.join(a.raw, pat))):
            got = parse_page(path, product)
            pages += 1
            if not got:
                empty.append(os.path.basename(path))
            rows += got
        rows.sort(key=lambda r: (r['date'], r['publish_dt']))
        # 去重：同日多源保留发布最早
        seen, dedup, dups = {}, [], []
        for r in rows:
            if r['date'] in seen:
                dups.append(r['date'])
                continue
            seen[r['date']] = r
            dedup.append(r)
        path = os.path.join(a.out, f'{product.lower()}_bjz_daily.csv')
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=['date', 'publish_dt', 'value', 'unit', 'title', 'url', 'page'])
            w.writeheader()
            w.writerows(dedup)
        report[product] = {
            'pages_parsed': pages,
            'pages_without_bjz': len(empty),
            'rows_raw': len(rows),
            'rows_dedup': len(dedup),
            'dup_dates': sorted(set(dups)),
            'first': dedup[0]['date'] if dedup else None,
            'last': dedup[-1]['date'] if dedup else None,
            'out': path,
        }
    with open(os.path.join(a.out, 'parse_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
