# -*- coding: utf-8 -*-
"""巨潮资讯（cninfo）适配器 —— A 股上市公司公告。

两个入口，行为不同，别搞混：
  1) GET  /new/fulltextSearch/full   —— 全文检索，**按相关度排序**，`seDate` 参数实测不生效，
                                        必须按公司名逐个查，再在客户端按日期过滤。
  2) POST /new/hisAnnouncement/query —— **标题检索 + 服务端真实日期区间**，更精准；
                                        需要 Referer 与 X-Requested-With 头，否则返回空。
公告原文 PDF 在 `http://static.cninfo.com.cn/<adjunctUrl>`（明文 http）。

命令行：
  python -m tools.cninfo search "福莱特" --pages 2 --since 2026-01-01
  python -m tools.cninfo query  "池窑" --begin 2026-01-01 --end 2026-12-31
"""
import argparse
import datetime
import json
import os
import sys
import urllib.parse

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

from tools import http  # noqa: E402

SEARCH_URL = 'http://www.cninfo.com.cn/new/fulltextSearch/full'
QUERY_URL = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
REFERER = 'http://www.cninfo.com.cn/new/fulltextSearch?notautosubmit=&keyWord='


def _ts_to_date(ms):
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime('%Y-%m-%d')
    except Exception:
        return ''


def _clean(s, limit=None):
    import re
    s = re.sub(r'<[^>]+>', '', str(s or ''))
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:limit] if limit else s


def search(key, pages=1, page_size=30, since=None, until=None, timeout=25, snippet=200):
    """全文检索（相关度排序）。客户端按日期过滤。

    返回 [{date, code, name, title, snippet, pdf}]。
    """
    out, dropped = [], 0
    for p in range(1, pages + 1):
        q = urllib.parse.urlencode({
            'searchkey': key, 'isfulltext': 'true', 'sortName': 'nothing',
            'sortType': 'desc', 'pageNum': p, 'pageSize': page_size,
        })
        r = http.fetch('%s?%s' % (SEARCH_URL, q), timeout=timeout)
        if not r['text']:
            break
        try:
            j = json.loads(r['text'])
        except Exception:
            break
        anns = j.get('announcements') or []
        if not anns:
            break
        for a in anns:
            d = _ts_to_date(a.get('announcementTime'))
            if since and d and d < since:
                dropped += 1
                continue
            if until and d and d > until:
                dropped += 1
                continue
            out.append({
                'date': d, 'code': a.get('secCode'), 'name': a.get('secName'),
                'title': _clean(a.get('announcementTitle')),
                'snippet': _clean(a.get('announcementContent'), snippet),
                'pdf': 'http://static.cninfo.com.cn/%s' % (a.get('adjunctUrl') or ''),
            })
        if len(anns) < page_size:
            break
    return out


def query(key, begin, end, pages=2, page_size=30, timeout=25, snippet=200, category=''):
    """标题检索 + 服务端日期区间（推荐）。返回同 search。"""
    body = urllib.parse.urlencode({
        'pageNum': 1, 'pageSize': page_size, 'column': 'szse', 'tabName': 'fulltext',
        'plate': '', 'stock': '', 'searchkey': key, 'secid': '', 'category': category,
        'trade': '', 'seDate': '%s~%s' % (begin, end), 'sortName': '', 'sortType': '',
        'isHLtitle': 'true',
    }).encode()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': REFERER, 'X-Requested-With': 'XMLHttpRequest',
    }
    out = []
    for p in range(1, pages + 1):
        body_p = body.replace(b'pageNum=1', ('pageNum=%d' % p).encode(), 1)
        r = http.fetch(QUERY_URL, method='POST', data=body_p, headers=headers, timeout=timeout)
        if not r['text']:
            break
        try:
            j = json.loads(r['text'])
        except Exception:
            break
        anns = j.get('announcements') or []
        if not anns:
            break
        for a in anns:
            out.append({
                'date': _ts_to_date(a.get('announcementTime')),
                'code': a.get('secCode'), 'name': a.get('secName'),
                'title': _clean(a.get('announcementTitle')),
                'snippet': _clean(a.get('announcementContent'), snippet),
                'pdf': 'http://static.cninfo.com.cn/%s' % (a.get('adjunctUrl') or ''),
            })
        if len(anns) < page_size:
            break
    return out


def fetch_pdf_text(pdf_url, timeout=40):
    """下载公告 PDF 并抽正文（best-effort，见 tools/pdftext.py）。"""
    from tools import pdftext
    r = http.fetch(pdf_url, timeout=timeout)
    if not r['body']:
        return ''
    return pdftext.extract_text(r['body'])


def main():
    ap = argparse.ArgumentParser(description='巨潮公告检索')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('search', help='全文检索（相关度排序，需客户端过滤日期）')
    s.add_argument('key')
    s.add_argument('--pages', type=int, default=1)
    s.add_argument('--since', default=None)
    s.add_argument('--until', default=None)
    q = sub.add_parser('query', help='标题检索 + 服务端日期区间')
    q.add_argument('key')
    q.add_argument('--begin', required=True)
    q.add_argument('--end', required=True)
    q.add_argument('--pages', type=int, default=2)
    a = ap.parse_args()
    if a.cmd == 'search':
        rows = search(a.key, pages=a.pages, since=a.since, until=a.until)
    else:
        rows = query(a.key, a.begin, a.end, pages=a.pages)
    for r in rows:
        print('%s | %s | %s | %s' % (r['date'], r['code'], r['name'], r['title']))
        if r['snippet']:
            print('      %s' % r['snippet'])
        print('      %s' % r['pdf'])
    print('共 %d 条' % len(rows))


if __name__ == '__main__':
    main()