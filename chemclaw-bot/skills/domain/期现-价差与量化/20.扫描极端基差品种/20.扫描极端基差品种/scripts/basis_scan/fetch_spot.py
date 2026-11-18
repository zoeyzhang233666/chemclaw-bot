# -*- coding: utf-8 -*-
"""fetch_spot.py — 生意社(100ppi) 化工品种「现货基准价」日度序列（长历史）

数据形态（实测）
----------------
100ppi 化工/橡塑/化纤/建材各行业频道下，每个商品有一个「数据资讯」栏目：
    https://www.100ppi.com/data/dlist-{channel}--{ppid}-{page}.html
栏目里逐日发布两类文章（公开，无需登录）：

A. 基准价稿： 「10月20日生意社甲醇基准价为3966.67元/吨」
B. 基差稿  ： 「10月20日生意社PP市场基差为1357.33元/吨」
   正文含三行可解析字段：
       「10月20日PP期货主力合约2701收盘价为9376元/吨。」
       「10月20日生意社现货基准价为10733.3元/吨。」
       「市场基差=现货价格-期货价格=10733.3-9376=1357.33元/吨。」

本模块把 A/B 两类统一成一张「现货基准价日序列」：
  - A 稿 price 直接取标题数值；
  - B 稿 price 取正文「现货基准价」，并同时保留其自带的主力合约与基差，供交叉校验（见 build 步骤）。
每页 40 条，翻页向更早历史回溯（实测可回溯至 2020 年前后）。

输出：data/raw/spot/{code}.csv
      date,price,src_type,article_spec,fut_contract,fut_close,src_basis,title,url,page
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import re
import sys

from .http import Http

BASE = 'https://www.100ppi.com'
ROW_RE = re.compile(
    r'<a\s+href="(detail-(\d{8})-(\d+)\.html)"[^>]*class="blueq"[^>]*>([^<]{4,180})</a>',
    re.S)
A_RE = re.compile(r'(\d{1,2})月(\d{1,2})日生意社\s*(.+?)\s*基准价为\s*(-?[\d.]+)\s*元/(吨|公斤|平方米)')
B_RE = re.compile(r'(\d{1,2})月(\d{1,2})日生意社\s*(.+?)\s*市场基差为\s*(-?[\d.]+)\s*元/吨')
BODY_SPOT = re.compile(r'生意社现货基准价为\s*(-?[\d.]+)\s*元/(吨|平方米|公斤)')
BODY_FUT = re.compile(r'(\d{1,2})月(\d{1,2})日\s*(.+?)\s*期货主力合约\s*(\d{4})\s*收盘价为\s*(-?[\d.]+)\s*元/吨')
BODY_BASIS = re.compile(r'市场基差=现货价格-期货价格=\s*(-?[\d.]+)(?:\s*/\s*([\d.]+))?\s*-\s*(-?[\d.]+)\s*=\s*(-?[\d.]+)')


def _text(html: str) -> str:
    t = re.sub(r'<script[\s\S]*?</script>', ' ', html)
    t = re.sub(r'<style[\s\S]*?</style>', ' ', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = t.replace('&nbsp;', ' ').replace('&#8226;', '·').replace('&gt;', '>').replace('&lt;', '<')
    return re.sub(r'[ \t\u3000]+', ' ', t)


def _date_in(y: str, m: str, d: str, url_ymd: str) -> str | None:
    """标题只写月日，年份取 URL 日期；跨年时按 ±6 个月纠偏。"""
    try:
        mm, dd = int(m), int(d)
        uy, um = int(url_ymd[:4]), int(url_ymd[4:6])
        if mm - um > 6:
            uy -= 1
        elif um - mm > 6:
            uy += 1
        return dt.date(uy, mm, dd).isoformat()
    except ValueError:
        return None


def list_rows(http: Http, channel: int, ppid: int, page: int) -> list[tuple]:
    if channel in (None, 0):
        return []
    url = '%s/data/dlist-%d--%d-%d.html' % (BASE, channel, ppid, page)
    html = http.get(url, referer=BASE + '/data/')
    if not html:
        return []
    out = []
    for m in ROW_RE.finditer(html):
        href, ymd, nid, title = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        if '基准价为' in title or '市场基差为' in title:
            out.append((href, ymd, nid, title))
    return out


def n_pages(http: Http, channel: int, ppid: int) -> int:
    url = '%s/data/dlist-%d--%d-1.html' % (BASE, channel, ppid)
    html = http.get(url, referer=BASE + '/data/')
    if not html:
        return 0
    pages = [int(x) for x in re.findall(r'dlist-%d--%d-(\d+)\.html' % (channel, ppid), html)]
    return max(pages) if pages else 1


def parse_article(http: Http, href: str) -> dict:
    url = BASE + '/data/' + href if href.startswith('detail-') else BASE + '/' + href
    html = http.get(url, referer=BASE + '/data/')
    if not html:
        return {}
    body = _text(html)
    i = body.find('来源')
    j = body.find('版权')
    seg = body[i:j] if (i >= 0 and j > i) else body
    out = {}
    m = BODY_SPOT.search(seg)
    if m:
        out['spot'] = float(m.group(1))
        out['unit'] = m.group(2)
    m = BODY_FUT.search(seg)
    if m:
        out['fut_contract'] = m.group(4)
        out['fut_close'] = float(m.group(5))
    m = BODY_BASIS.search(seg)
    if m:
        out['basis'] = float(m.group(4))
        out['basis_spot'] = float(m.group(1))
        out['basis_fut'] = float(m.group(3))
        if m.group(2):
            # 源站自带换算式：现货单位 → 期货单位的除数（如 629/0.32、11.95/0.0125）
            out['unit_divisor'] = float(m.group(2))
    return out


def fetch_product(http: Http, prod: dict, max_pages: int = 40, since: str | None = None,
                  verbose: bool = True) -> list[dict]:
    """抓单个品种的现货基准价日序列。"""
    code, ch, ppid = prod['code'], int(prod['channel']), int(prod['ppid'])
    pages = min(max_pages, n_pages(http, ch, ppid))
    if verbose:
        print('[spot] %-3s %-6s channel=%s ppid=%s pages=%s' % (code, prod['name'], ch, ppid, pages),
              flush=True)
    rows: dict[str, dict] = {}
    for p in range(1, pages + 1):
        items = list_rows(http, ch, ppid, p)
        if not items:
            if verbose:
                print('   page %d: 0 rows, stop' % p, flush=True)
            break
        oldest = min(ymd for _, ymd, _, _ in items)
        for href, ymd, nid, title in items:
            ma = A_RE.search(title)
            mb = B_RE.search(title)
            rec = None
            if ma:
                d = _date_in(ymd, ma.group(1), ma.group(2), ymd)
                if d:
                    rec = dict(date=d, price=float(ma.group(4)), src_type='benchmark',
                               article_spec=ma.group(3).strip(), unit=ma.group(5),
                               fut_contract='', fut_close='', src_basis='',
                               title=title, url=BASE + '/' + href if href.startswith('detail-')
                               else BASE + '/data/' + href, page=p)
            elif mb:
                d = _date_in(ymd, mb.group(1), mb.group(2), ymd)
                if d:
                    art = parse_article(http, href)
                    if 'spot' in art:
                        # 正文偶尔不写「市场基差=现货-期货=…」那行（如玻璃稿），
                        # 此时用标题里的基差数值作为源站口径的交叉校验值。
                        src_b = art.get('basis', '')
                        if src_b == '' and mb.group(4):
                            try:
                                src_b = float(mb.group(4))
                            except (TypeError, ValueError):
                                src_b = ''
                        rec = dict(date=d, price=art['spot'], src_type='basis_article',
                                   article_spec=mb.group(3).strip(), unit=art.get('unit', '吨'),
                                   fut_contract=art.get('fut_contract', ''),
                                   fut_close=art.get('fut_close', ''),
                                   src_basis=src_b,
                                   unit_divisor=art.get('unit_divisor', ''),
                                   title=title, url=BASE + '/' + href if href.startswith('detail-')
                                   else BASE + '/data/' + href, page=p)
            if rec:
                rows.setdefault(rec['date'], rec)
        if verbose:
            ds = sorted(rows)
            print('   page %2d rows=%3d total=%3d span=%s..%s' % (
                p, len(items), len(rows), ds[0] if ds else '-', ds[-1] if ds else '-'), flush=True)
        if since and oldest <= since:
            if verbose:
                print('   reached %s <= since %s, stop' % (oldest, since), flush=True)
            break
    return [rows[d] for d in sorted(rows)]


FIELDS = ['date', 'price', 'src_type', 'article_spec', 'unit', 'fut_contract', 'fut_close',
          'src_basis', 'unit_divisor', 'title', 'url', 'page']


def save(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    import argparse
    from .products import load_pool
    ap = argparse.ArgumentParser(description='抓取 100ppi 现货基准价日序列')
    ap.add_argument('--codes', default='', help='逗号分隔品种代码，空=全部')
    ap.add_argument('--max-pages', type=int, default=40)
    ap.add_argument('--since', default='', help='回溯到该日期为止(YYYY-MM-DD)，空=翻到底')
    ap.add_argument('--out', default='data/raw/spot')
    ap.add_argument('--cache', default='data/cache')
    ap.add_argument('--pool', default='')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    pool = load_pool(a.pool or None)
    codes = [c.strip().upper() for c in a.codes.split(',') if c.strip()]
    if codes:
        pool = [p for p in pool if p['code'] in codes]
    http = Http(cache_dir=a.cache)
    summary = []
    for prod in pool:
        rows = fetch_product(http, prod, max_pages=a.max_pages, since=(a.since or None))
        if rows:
            save(rows, os.path.join(a.out, '%s.csv' % prod['code']))
        summary.append((prod['code'], prod['name'], len(rows),
                        rows[0]['date'] if rows else '-', rows[-1]['date'] if rows else '-'))
        print('  => %-3s %-6s n=%4d %s..%s' % summary[-1], flush=True)
    print('\n[SUMMARY]')
    for s in summary:
        print('  %-3s %-6s n=%4d %s..%s' % s)


if __name__ == '__main__':
    main()
