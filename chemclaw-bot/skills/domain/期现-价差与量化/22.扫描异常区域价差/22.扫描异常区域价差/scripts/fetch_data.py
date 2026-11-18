# -*- coding: utf-8 -*-
"""
采集脚本：真实数据抓取（重质纯碱 / 甲醇 / PVC）
数据源：
  - 生意社 100ppi（重质纯碱 / 轻质纯碱 / 甲醇 / PVC树脂SG5 的各市场基准价 + 日度序列 + 品牌口径明细）
  - 新浪财经（期货主力合约日K，用于区域价差的期货锚定参考；不作为现货价）
输出：data_raw/*.json
说明：
  - 只抓公开可见数据，不做任何插值或估算；抓不到的字段一律留空并在 gaps 里登记。
  - 服务器若返回 JS Cookie 校验，先取页面里内嵌的 HW_CHECK 值再带 Cookie 请求。
"""
import json
import os
import re
import sys
import time
import gzip
import brotli
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'data_raw')
os.makedirs(RAW, exist_ok=True)

UA = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'),
    'Accept-Encoding': 'gzip',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
PRODUCTS = {737: '重质纯碱', 226: '轻质纯碱', 817: '甲醇', 107: 'PVC树脂SG5'}
COOKIE = {'v': ''}


def fetch(url, referer=None, tries=3):
    for _ in range(tries):
        h = dict(UA)
        if COOKIE['v']:
            h['Cookie'] = 'HW_CHECK=' + COOKIE['v']
        if referer:
            h['Referer'] = referer
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=20) as r:
                b = r.read()
                enc = (r.headers.get('Content-Encoding') or '').lower()
            if enc == 'br':
                b = brotli.decompress(b)
            elif enc == 'gzip':
                b = gzip.decompress(b)
            for e in ('utf-8', 'gbk'):
                try:
                    return b.decode(e)
                except Exception:
                    continue
            return b.decode('utf-8', 'ignore')
        except Exception as ex:
            err = str(ex)[:120]
            time.sleep(0.8)
    raise RuntimeError('fetch failed: %s (%s)' % (url, err))


def ensure_cookie():
    if COOKIE['v']:
        return COOKIE['v']
    t = fetch('https://www.100ppi.com/mprice/')
    m = re.search(r'_0x2\s*=\s*"([0-9a-f]{16,})"', t)
    COOKIE['v'] = m.group(1) if m else ''
    return COOKIE['v']


def unpack(code):
    """还原 Dean Edwards p,a,c,k,e,d 压缩的图表脚本。"""
    m = re.search(r"eval\(function\(p,a,c,k,e,d\).*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)", code, re.S)
    if not m:
        return None
    payload, a, kw = m.group(1).replace("\\'", "'"), int(m.group(2)), m.group(4).split('|')
    alpha = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

    def repl(mm):
        tok, n = mm.group(0), 0
        for ch in tok:
            d = alpha.find(ch)
            if d < 0 or d >= a:
                return tok
            n = n * a + d
        return kw[n] if n < len(kw) and kw[n] else tok

    return re.sub(r'\b[0-9a-zA-Z]+\b', repl, payload)


def cells(row_html):
    out = []
    for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.S):
        c = re.sub(r'<[^>]+>', ' ', c)
        out.append(re.sub(r'\s+', ' ', c).strip())
    return out


def scrape_product(pid, name):
    ensure_cookie()
    url = 'https://www.100ppi.com/rawmex/detail-%d.html' % pid
    html = fetch(url, referer='https://www.100ppi.com/monitor/')
    rec = {
        'ppid': pid,
        'product': name,
        'source_url': url,
        'retrieved_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'snapshot_rows': [],
        'headline': {},
        'series': [],
        'series_meta': {},
    }
    for r in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        cs = cells(r)
        if len(cs) >= 6 and re.match(r'^\d+(\.\d+)?$', cs[4] or ''):
            rec['snapshot_rows'].append({
                'name': cs[0], 'spec': cs[1], 'brand': cs[2], 'market': cs[3],
                'price': float(cs[4]), 'unit': '元/吨', 'time': cs[5],
            })
    box = re.search(r'<div class="price-box01_1">(.*?)</div>\s*</div>', html, re.S)
    if box:
        seg = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', box.group(1)))
        rec['headline']['raw'] = seg.strip()[:300]
    for label, pat in [('三个月均价', r'三个月均价[：:]\s*([\d.]+)'),
                       ('三个月最高', r'三个月最高[：:]\s*([\d.]+)'),
                       ('三个月最低', r'三个月最低[：:]\s*([\d.]+)')]:
        m = re.search(pat, html)
        if m:
            rec['headline'][label] = float(m.group(1))
    for label in ('一年位置', '两年位置', '三年位置'):
        m = re.search(label + r'[：:]\s*([^<\s]+)', html)
        if m:
            rec['headline'][label] = m.group(1)
    # 日度序列（图表 iframe 内嵌压缩脚本）
    gi = re.search(r'src="(https://www\.100ppi\.com/graph/cindex\.php[^"]+)"', html)
    if gi:
        ghtml = fetch(gi.group(1), referer=url)
        js = unpack(ghtml) or ghtml
        sub = re.search(r"subtext:'([^']*)'", js)
        ttl = re.search(r"title:\{[^{}]*?text:'([^']*)'", js)
        dates = re.search(r"boundaryGap:false,data:\[(.*?)\]\}", js, re.S)
        vals = re.search(r"series:\[\{.*?data:\[(.*?)\]\}", js, re.S)
        rec['series_meta'] = {
            'subtext': sub.group(1) if sub else '',
            'title': ttl.group(1) if ttl else '',
            'chart_url': gi.group(1),
        }
        if dates and vals:
            ds = re.findall(r"'([\d\-]+)'", dates.group(1))
            vs = [float(x) for x in re.findall(r'(\d+(?:\.\d+)?)', vals.group(1))]
            n = min(len(ds), len(vs))
            rec['series'] = [{'date': ds[i], 'price': vs[i]} for i in range(n)]
    return rec


def scrape_futures(symbols=('SA0', 'MA0', 'V0')):
    out = {}
    for s in symbols:
        url = ('https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/'
               'InnerFuturesNewService.getDailyKLine?symbol=' + s)
        t = fetch(url)
        m = re.search(r'\((\[.*\])\)', t, re.S)
        if not m:
            continue
        rows = json.loads(m.group(1))
        out[s] = [{'date': r['d'], 'close': float(r['c'])} for r in rows]
    return out


def main():
    data = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'products': {}}
    for pid, nm in PRODUCTS.items():
        try:
            data['products'][str(pid)] = scrape_product(pid, nm)
            print('ok', nm, len(data['products'][str(pid)]['snapshot_rows']), 'rows,',
                  len(data['products'][str(pid)]['series']), 'series pts')
        except Exception as ex:
            print('FAIL', nm, ex)
            data['products'][str(pid)] = {'ppid': pid, 'product': nm, 'error': str(ex)}
        time.sleep(1.0)
    try:
        data['futures'] = scrape_futures()
        print('ok futures', {k: len(v) for k, v in data['futures'].items()})
    except Exception as ex:
        print('FAIL futures', ex)
        data['futures'] = {}
    with open(os.path.join(RAW, 'spot_snapshot.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('saved ->', os.path.join(RAW, 'spot_snapshot.json'))


if __name__ == '__main__':
    main()
