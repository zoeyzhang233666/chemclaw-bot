# -*- coding: utf-8 -*-
"""采集器模板：期货日线 / 资讯检索 / 网页抓取。按品种改 SYMBOLS 与 KEYWORDS。"""
import json, os, re, ssl, sys, time, gzip, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'raw', '_src')
os.makedirs(SRC, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'zh-CN,zh;q=0.9'}
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def httpget(u, ref=None, timeout=30, tries=3):
    last = None
    for i in range(tries):
        try:
            h = dict(UA)
            if ref: h['Referer'] = ref
            r = urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=timeout, context=CTX)
            b = r.read()
            if (r.headers.get('Content-Encoding') or '').lower() == 'gzip': b = gzip.decompress(b)
            return b.decode('utf-8', 'ignore')
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise last

SINA = ('https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/InnerFuturesNewService.getDailyKLine?symbol={s}',
        'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/InnerFuturesNewService.getDailyKLine?symbol={s}')

def fetch_fut(sym):
    last = None
    for u in SINA:
        try:
            s = httpget(u.format(s=sym))
            d = json.loads(s[s.index('['):s.rindex(']') + 1])
            rows = [{'d': x['d'], 'o': float(x['o']), 'h': float(x['h']), 'l': float(x['l']),
                     'c': float(x['c']), 'v': float(x.get('v') or 0), 'oi': float(x.get('p') or 0)} for x in d]
            rows.sort(key=lambda x: x['d'])
            return rows
        except Exception as e:
            last = e
    raise last

def em_search(kw, pages=1, size=40):
    """东方财富资讯检索（JSONP）。"""
    rows = []
    for p in range(1, pages + 1):
        param = json.dumps({'uid': '', 'keyword': kw, 'type': ['cmsArticleWebOld'], 'client': 'web',
                            'clientType': 'web', 'clientVersion': 'curr',
                            'param': {'cmsArticleWebOld': {'searchScope': 'default', 'sort': 'default',
                                                           'pageIndex': p, 'pageSize': size}}}, ensure_ascii=False)
        u = 'https://search-api-web.eastmoney.com/search/jsonp?' + urllib.parse.urlencode({'cb': 'jQuery', 'param': param})
        s = httpget(u, ref='https://so.eastmoney.com/')
        d = json.loads(s[s.index('(') + 1:s.rindex(')')])
        for x in d.get('result', {}).get('cmsArticleWebOld', []):
            rows.append({'date': x['date'], 'title': re.sub(r'<[^>]+>', '', x['title']),
                         'url': x['url'], 'content': re.sub(r'<[^>]+>', '', x.get('content', ''))})
        time.sleep(0.4)
    return rows

def html2text(b):
    import lxml.html
    doc = lxml.html.fromstring(b)
    for bad in doc.xpath('//script|//style|//noscript'): bad.getparent().remove(bad)
    return re.sub(r'\n{2,}', '\n', '\n'.join(' '.join(t.split()) for t in doc.itertext()))

if __name__ == '__main__':
    SYMBOLS = sys.argv[1:] or ['MA2701']
    for s in SYMBOLS:
        rows = fetch_fut(s)
        json.dump({'symbol': s, 'rows': rows}, open(os.path.join(SRC, 'fut_%s.json' % s), 'w', encoding='utf-8'), ensure_ascii=False)
        print('OK', s, len(rows), rows[-1]['d'], rows[-1]['c'])
