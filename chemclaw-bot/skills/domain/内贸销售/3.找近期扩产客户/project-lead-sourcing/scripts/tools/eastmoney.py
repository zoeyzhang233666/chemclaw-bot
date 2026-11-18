# -*- coding: utf-8 -*-
"""东方财富公告适配器 —— 本类环境里最实用的「公告正文」通道。

  目录： http://np-anotice-stock.eastmoney.com/api/security/ann
        ?page_size=60&page_index=1&ann_type=A&client_source=web
        &stock_list=<代码>&begin_time=YYYY-MM-DD&end_time=YYYY-MM-DD
        → 返回 art_code / notice_date / title（**支持服务端真实日期区间**）

  全文： http://np-cnotice-stock.eastmoney.com/api/content/ann
        ?art_code=<art_code>&page_index=N&client_source=web&page_size=5000
        → data.notice_content，每页最多 5000 字，可翻页取完整正文

命令行：
  python -m tools.eastmoney list 600176 --begin 2026-01-01 --end 2026-12-31 --grep 池窑
  python -m tools.eastmoney text AN202608201828203124
"""
import argparse
import json
import os
import sys

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

from tools import http  # noqa: E402

DIR_URL = 'http://np-anotice-stock.eastmoney.com/api/security/ann'
FULL_URL = 'http://np-cnotice-stock.eastmoney.com/api/content/ann'


def list_notices(code, begin, end, pages=3, page_size=60, timeout=25):
    """列出某代码在区间内的公告。返回 [{date, art_code, title}]。"""
    out = []
    for pi in range(1, pages + 1):
        q = ('page_size=%d&page_index=%d&ann_type=A&client_source=web'
             '&stock_list=%s&begin_time=%s&end_time=%s&f_node=0&s_node=0'
             % (page_size, pi, code, begin, end))
        r = http.fetch('%s?%s' % (DIR_URL, q), timeout=timeout)
        if not r['text']:
            break
        try:
            j = json.loads(r['text'])
        except Exception:
            break
        data = j.get('data') or {}
        lst = data.get('list') or []
        if not lst:
            break
        for a in lst:
            d = str(a.get('notice_date') or '')[:10]
            out.append({'date': d, 'art_code': a.get('art_code'), 'title': a.get('title')})
        if len(lst) < page_size:
            break
    return out


def notice_text(art_code, max_pages=12, timeout=25, page_size=5000):
    """取公告正文全文（拼接多页）。"""
    parts = []
    for p in range(1, max_pages + 1):
        q = ('art_code=%s&page_index=%d&client_source=web&page_size=%d'
             % (art_code, p, page_size))
        r = http.fetch('%s?%s' % (FULL_URL, q), timeout=timeout)
        if not r['text']:
            break
        try:
            j = json.loads(r['text'])
        except Exception:
            break
        txt = ((j.get('data') or {}).get('notice_content') or '')
        if not txt:
            break
        parts.append(http.strip_tags(txt) if '<' in txt else txt)
        if len(txt) < page_size:
            break
    return '\n'.join(parts)


def main():
    ap = argparse.ArgumentParser(description='东方财富公告目录/全文')
    sub = ap.add_subparsers(dest='cmd', required=True)
    l = sub.add_parser('list')
    l.add_argument('code')
    l.add_argument('--begin', required=True)
    l.add_argument('--end', required=True)
    l.add_argument('--pages', type=int, default=3)
    l.add_argument('--grep', default=None)
    t = sub.add_parser('text')
    t.add_argument('art_code')
    t.add_argument('--max-pages', type=int, default=12)
    a = ap.parse_args()
    if a.cmd == 'list':
        rows = list_notices(a.code, a.begin, a.end, pages=a.pages)
        for r in rows:
            if a.grep and a.grep not in (r['title'] or ''):
                continue
            print('%s | %s | %s' % (r['date'], r['art_code'], r['title']))
        print('共 %d 条（未过滤前 %d）' % (
            sum(1 for r in rows if not a.grep or a.grep in (r['title'] or '')), len(rows)))
    else:
        print(notice_text(a.art_code, max_pages=a.max_pages))


if __name__ == '__main__':
    main()