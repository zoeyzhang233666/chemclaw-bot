# -*- coding: utf-8 -*-
"""
抓取 生意社(100ppi) 甲醇基准价 日度序列
==========================================
来源页面：https://me.100ppi.com/news/list--1217-{page}.html （公开，无需登录）
每条记录来自标题目录：「M月D日生意社甲醇基准价为X元/吨」，并保留原文链接。
翻页至无数据为止（实测第37页为最后一页，最早 2022-08-17）。

重要口径声明（写入报告时必须原样引用）：
  - 这是"生意社基准价"，生意社官方定义为
    「基于价格大数据与生意社价格模型产生的交易指导价」，公式 结算价 = 基准价×K + C，
    C 用于吸收区域价差/物流/品牌差异。
  - 因此它 **是全国口径的交易参考价（含税，元/吨），不是华东/太仓/江苏的报价**。
  - 若研究需要"华东现货"，必须另购 隆众/卓创 数据，或在报告中明确降级口径。

不做任何插值/填补；只在 CSV 中如实保留缺失交易日。
"""
import csv
import os
import re
import sys
import time
import urllib.request

try:
    import brotli
except ImportError:
    brotli = None

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE) if os.path.basename(HERE) == 'scripts' else HERE
OUT_DIR = os.path.join(ROOT, 'out')
os.makedirs(OUT_DIR, exist_ok=True)

UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept-Encoding': 'gzip, deflate, br',
}
ROW = re.compile(r'<a href="(https://www\.100ppi\.com/news/detail-(\d{8})-\d+\.html)"[^>]*>([^<]{4,140}?)</a>')
VALUE = re.compile(r'(\d{1,2})月(\d{1,2})日生意社甲醇基准价为([\d,]+\.?\d*)元/吨')


def fetch(url, ref=None, timeout=30, retries=3):
    last = None
    for i in range(retries):
        try:
            h = dict(UA)
            if ref:
                h['Referer'] = ref
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
            b = r.read()
            enc = (r.headers.get('Content-Encoding') or '').lower()
            if enc == 'br' and brotli:
                b = brotli.decompress(b)
            elif enc == 'gzip':
                import gzip
                b = gzip.decompress(b)
            return b.decode('utf-8', 'ignore')
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def scan_page(p):
    u = 'https://me.100ppi.com/news/list--1217-%d.html' % p
    t = fetch(u, ref='https://me.100ppi.com/')
    out = []
    for url, ymd, text in ROW.findall(t):
        m = VALUE.search(text)
        if m:
            out.append({'date': '%s-%s-%s' % (ymd[:4], ymd[4:6], ymd[6:8]),
                        'price': float(m.group(3).replace(',', '')),
                        'source_url': url})
    return t, out


def main():
    allrows = {}
    for p in range(1, 60):
        try:
            t, rows = scan_page(p)
        except Exception as e:
            print('[WARN] page %d failed: %r' % (p, e))
            break
        print('[PAGE] %2d rows=%3d %s' % (p, len(rows), (rows[0]['date'] + '~' + rows[-1]['date']) if rows else '-'))
        if not rows:
            break
        for r in rows:
            allrows.setdefault(r['date'], r)
        time.sleep(0.7)

    rows = [allrows[d] for d in sorted(allrows)]
    dst = os.path.join(OUT_DIR, 'spot_100ppi_meitan_benchmark.csv')
    with open(dst, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['date', 'price', 'source_url'])
        for r in rows:
            w.writerow([r['date'], '%.2f' % r['price'], r['source_url']])
    print('[OK] %s  rows=%d  %s -> %s' % (dst, len(rows), rows[0]['date'], rows[-1]['date']))


if __name__ == '__main__':
    main()
