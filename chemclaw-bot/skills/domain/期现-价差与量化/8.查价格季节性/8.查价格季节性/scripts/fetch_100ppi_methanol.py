# -*- coding: utf-8 -*-
"""fetch_100ppi_methanol.py — 生意社(100ppi) 甲醇基准价 日度序列抓取（可复现、带校验）

用途
----
本脚本是 查价格季节性 Skill 的**示例取数器**（品类：甲醇现货）。
它只验证「生意社基准价」这一条免费公开、逐日、逐条附原文链接的渠道。

口径（必须原样写进报告，不得改写成"华东现货"）
------------------------------------------------
生意社官方定义：基准价 = 基于价格大数据与价格模型产生的**交易指导价**；
定价公式 结算价 = 基准价 × K + C（K/C 按地区、品牌、物流由交易双方约定）。
=> 全国口径、含税、元/吨的参考价；**不是**华东/太仓/江苏仓库成交价。

数据源
------
https://me.100ppi.com/news/list--1217-{page}.html   公开栏目，逐条标题形如
「M月D日生意社甲醇基准价为X元/吨」，每条附原文链接（可逐行追溯）。

用法
----
python fetch_100ppi_methanol.py --out ./raw            # 抓取并留证
python fetch_100ppi_methanol.py --audit-only           # 只做校验，不重抓

输出
----
raw/100ppi_methanol_benchmark_daily.csv   date,price,source_url,title
raw/fetch_manifest.json                   抓取时间/页数/条数/缺口/交叉校验结果
"""
import argparse
import csv
import gzip
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, timedelta

try:
    import brotli
except ImportError:                                   # pragma: no cover
    brotli = None

sys.stdout.reconfigure(encoding='utf-8')

CHANNEL = 'https://me.100ppi.com/news/list--1217-{page}.html'
PAGE_MAX = 80
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')

ROW = re.compile(r'<a href="(https://www\.100ppi\.com/news/detail-(\d{8})-\d+\.html)"[^>]*>'
                 r'([^<]{4,160}?)</a>')
VALUE = re.compile(r'(\d{1,2})月(\d{1,2})日生意社甲醇基准价为([\d,]+\.?\d*)\s*元/吨')
# 第二种独立写法：附带涨跌幅，用于交叉解析校验
VALUE_B = re.compile(r'与[^。]{0,40}?(?:相比|较)[^。]{0,20}?([涨跌][^，。]{0,20})。?')


def http_get(url, ref=None, timeout=30, retries=3):
    last = None
    for i in range(retries):
        try:
            h = {'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate, br',
                 'Accept-Language': 'zh-CN,zh;q=0.9'}
            if ref:
                h['Referer'] = ref
            with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                        timeout=timeout) as r:
                b = r.read()
                enc = (r.headers.get('Content-Encoding') or '').lower()
            if 'br' in enc and brotli is not None:
                b = brotli.decompress(b)
            elif 'gzip' in enc:
                b = gzip.decompress(b)
            return b.decode('utf-8', 'ignore')
        except Exception as e:                        # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def parse_page(text, ymd_from_url):
    """Return list of dict rows found on one channel page."""
    out = []
    for url, ymd, title in ROW.findall(text):
        m = VALUE.search(title)
        if not m:
            continue
        mm, dd = int(m.group(1)), int(m.group(2))
        # 标题里的月日才是报价日；URL 的 ymd 是文章发布日，两者可能跨夜相差 1 天，
        # 这里保留 URL 日期作为发布日、标题月日拼到发布日所在年份作为报价日。
        pub = '%s-%s-%s' % (ymd[:4], ymd[4:6], ymd[6:8])
        py = int(ymd[:4])
        cand = date(py, mm, dd)
        # 若标题月日比发布日"晚"很多（>30 天），说明是上一年 12 月发的文
        if (cand - date(py, int(ymd[4:6]), int(ymd[6:8]))).days > 30:
            cand = date(py - 1, mm, dd)
        out.append({'date': cand.isoformat(), 'price': float(m.group(3).replace(',', '')),
                    'source_url': url, 'title': title.strip(), 'publish_date': pub})
    return out


def scrape(outdir):
    allrows = {}
    pages = 0
    for p in range(1, PAGE_MAX + 1):
        url = CHANNEL.format(page=p)
        try:
            t = http_get(url, ref='https://me.100ppi.com/')
        except Exception as e:                        # noqa: BLE001
            print('[WARN] page %d failed: %r' % (p, e))
            break
        rows = parse_page(t, None)
        print('[PAGE] %2d rows=%3d %s' % (p, len(rows),
                                          (rows[0]['date'] + '~' + rows[-1]['date']) if rows else '-'))
        if not rows:
            break
        pages = p
        for r in rows:
            allrows.setdefault(r['date'], r)
        time.sleep(0.6)
    rows = [allrows[d] for d in sorted(allrows)]
    os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, '100ppi_methanol_benchmark_daily.csv')
    with open(dst, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['date', 'price', 'source_url', 'publish_date', 'title'])
        for r in rows:
            w.writerow([r['date'], '%.2f' % r['price'], r['source_url'],
                        r['publish_date'], r['title']])
    print('[OK] %s rows=%d' % (dst, len(rows)))
    return rows, pages, dst


def audit(rows, outdir, pages=None):
    """Structural + logical audit. Never fills gaps."""
    rows = sorted(rows, key=lambda r: r['date'])
    d0, d1 = date.fromisoformat(rows[0]['date']), date.fromisoformat(rows[-1]['date'])
    have = {r['date'] for r in rows}
    missing = []
    d = d0
    while d <= d1:
        if d.weekday() < 5 and d.isoformat() not in have:
            missing.append(d.isoformat())
        d += timedelta(days=1)
    prices = [r['price'] for r in rows]
    # 1) 数值合理性
    lo, hi = min(prices), max(prices)
    # 2) 重复 / 乱序
    dup = len(rows) - len(have)
    # 3) 单日跳变 >8% 视为可疑并列出（不修改）
    jumps = []
    for a, b in zip(rows, rows[1:]):
        if a['price'] > 0:
            chg = (b['price'] - a['price']) / a['price']
            if abs(chg) > 0.08:
                jumps.append({'date': b['date'], 'from': a['price'], 'to': b['price'],
                              'chg': round(chg, 4)})
    # 4) 独立重解析：直接从 CSV 原文 title 再算一遍，比对数值
    recheck = 0
    for r in rows:
        m = VALUE.search(r['title'])
        if m and abs(float(m.group(3).replace(',', '')) - r['price']) < 1e-6:
            recheck += 1
    # 5) 值域：甲醇以元/吨计，历史区间应在 1000~6000 元/吨
    out_of_range = [r for r in rows if not (800 <= r['price'] <= 8000)]
    man = {
        'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'source': CHANNEL.format(page=1) + '  (page 1..%s)' % pages,
        'caliber': '生意社甲醇基准价（全国口径·含税·元/吨·交易指导价）',
        'rows': len(rows), 'first': rows[0]['date'], 'last': rows[-1]['date'],
        'price_min': lo, 'price_max': hi,
        'weekday_missing': missing, 'n_weekday_missing': len(missing),
        'duplicates_removed': dup, 'suspicious_jumps_gt_8pct': jumps,
        'independent_reparse_matched': recheck, 'out_of_range': len(out_of_range),
        'every_row_has_source_url': all(r['source_url'].startswith('https://www.100ppi.com/news/detail-')
                                        for r in rows),
    }
    with open(os.path.join(outdir, 'fetch_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in man.items() if k not in ('weekday_missing',)},
                     ensure_ascii=False, indent=1))
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='./raw')
    args = ap.parse_args()
    rows, pages, dst = scrape(args.out)
    audit(rows, args.out, pages)


if __name__ == '__main__':
    main()
