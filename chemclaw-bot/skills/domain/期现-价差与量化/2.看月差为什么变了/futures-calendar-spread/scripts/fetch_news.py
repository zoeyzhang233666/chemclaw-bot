# -*- coding: utf-8 -*-
"""按品种抓取财经新闻标题（东方财富搜索接口），用作“带日期的事件线索”。

用法：
    python scripts/fetch_news.py SA --out data/external/news_SA.json \
        --keywords "纯碱 库存,纯碱 期货,纯碱 检修,玻璃 冷修,纯碱 产能"

产出：news_<CODE>.json，每条 {date,title,url,media,content,kw,source,reliability}
提醒：新闻只是“线索”，不能当数据。每条引用前必须打开原文核对数字与日期。
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
try:
    ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
except Exception:  # pragma: no cover
    pass

DEFAULT_KW = '纯碱 库存,纯碱 期货,纯碱 检修,纯碱 产能,纯碱 玻璃,玻璃 冷修'


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': 'https://so.eastmoney.com/'})
    with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310
        return r.read().decode('utf-8', 'ignore')


def search(kw: str, pages: int = 3, size: int = 20, sort: str = 'time') -> list:
    out = []
    for pi in range(1, pages + 1):
        p = {'uid': '', 'keyword': kw, 'type': ['cmsArticleWebOld'], 'client': 'web',
             'clientType': 'web', 'clientVersion': 'curr',
             'param': {'cmsArticleWebOld': {'searchScope': 'default', 'sort': sort,
                                            'pageIndex': pi, 'pageSize': size,
                                            'preTag': '', 'postTag': ''}}}
        u = ('https://search-api-web.eastmoney.com/search/jsonp?cb=cb&param=' +
             urllib.parse.quote(json.dumps(p, ensure_ascii=False)))
        try:
            t = _get(u)
            d = json.loads(t[t.find('(') + 1:t.rfind(')')])['result']['cmsArticleWebOld']
        except Exception:  # noqa: BLE001
            break
        if not d:
            break
        out.extend(d)
        time.sleep(0.25)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('product')
    ap.add_argument('--out', required=True)
    ap.add_argument('--keywords', default=DEFAULT_KW)
    ap.add_argument('--pages', type=int, default=3)
    ap.add_argument('--since', default='')
    args = ap.parse_args(argv)

    seen, rows = {}, []
    for kw in [k.strip() for k in args.keywords.split(',') if k.strip()]:
        for it in search(kw, pages=args.pages):
            title = it.get('title', '').strip()
            date = it.get('date', '')[:10]
            if args.since and date < args.since:
                continue
            # 标题须真正含品种词，避免搜索接口的相关度噪声
            if not any(w in title for w in ('纯碱', '碱厂', '重碱', '轻碱', '玻璃')):
                continue
            if it['code'] in seen:
                continue
            seen[it['code']] = True
            rows.append({'date': date, 'title': title, 'url': it['url'],
                         'media': it.get('mediaName', ''),
                         'content': (it.get('content') or '').strip()[:500], 'kw': kw,
                         'source': '东方财富新闻搜索（search-api-web.eastmoney.com）',
                         'reliability': '媒体转述：引用前须打开原文核对数字与日期'})
    rows.sort(key=lambda r: r['date'], reverse=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f'{len(rows)} 条 -> {args.out}')
    for r in rows[:25]:
        print(' ', r['date'], '|', r['title'][:60], '|', r['url'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
