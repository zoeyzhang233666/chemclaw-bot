# -*- coding: utf-8 -*-
"""生意社(100ppi) 基准价抓取器 —— PVC 产业链专用。

流程:
  1) GET https://www.100ppi.com/rawmex/  -> 636B 拦截页, 含 var _0x2 = "<hex>"
  2) 回填 Cookie: HW_CHECK=<hex>
  3) GET https://www.100ppi.com/graph/cindex.php?f=graph_ppid_ave&ppid=<PID>  (packer 混淆的 echarts option)
     同时 GET https://www.100ppi.com/rawmex/detail-<PID>.html 取规格/地区/备注
  4) 解包 -> xAxis.data 与 series[0].data -> 日序列

已知限制: 曲线端点默认返回近一年(可滚动), 早于该窗口需付费源。
"""
import os
import re
import gzip
import json
import time
import random
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HW = {'v': None}


def _get(url, referer=None, tries=3):
    h = {'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9', 'Accept-Encoding': 'gzip'}
    if referer:
        h['Referer'] = referer
    for attempt in range(tries):
        if _HW['v']:
            h['Cookie'] = 'HW_CHECK=' + _HW['v']
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30)
            b = r.read()
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(1 + random.random())
            continue
        if r.headers.get('Content-Encoding') == 'gzip':
            b = gzip.decompress(b)
        t = b.decode('utf-8', 'replace')
        m = re.search(r'var _0x2\s*=\s*"([0-9a-f]{16,})"', t)
        if m:
            _HW['v'] = m.group(1)
            time.sleep(0.4)
            continue
        return t
    raise RuntimeError('100ppi HW_CHECK handshake failed: ' + url)


def unpack(html):
    """JS packer: eval(function(p,a,c,k,e,d){...}('p',a,c,'k'.split('|')))"""
    m = re.search(r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)",
                  html, re.S)
    if not m:
        raise RuntimeError('no packer payload (layout changed?)')
    p, words = m.group(1), m.group(4).split('|')
    out, i = [], 0
    dg = set('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    while i < len(p):
        ch = p[i]
        if ch == '\\':
            out.append(p[i + 1]); i += 2; continue
        if ch not in dg:
            out.append(ch); i += 1; continue
        j = i
        while j < len(p) and p[j] in dg:
            j += 1
        word = p[i:j]
        idx = 0
        for c in word:
            idx = idx * 62 + (ord(c) - 48 if c.isdigit() else
                              ord(c) - 87 if c.islower() else ord(c) - 29)
        out.append(words[idx] if idx < len(words) and words[idx] else word)
        i = j
    return ''.join(out)


def parse_series(js):
    """返回 [(YYYY-MM-DD, value), ...] (升序)。"""
    d4 = re.findall(r"'(\d{4}-\d{2}-\d{2})'", js)
    if d4:
        labels = d4
    else:
        labels = re.findall(r"'(\d{1,2}-\d{1,2}-\d{1,2})'", js)
    arr = None
    for mm in re.finditer(r'\[([^\[\]]{200,})\]', js):
        if re.match(r'^\s*[\d.]+\s*,', mm.group(1)):
            arr = [float(v) for v in mm.group(1).split(',') if v.strip()]
            break
    if not arr or not labels:
        raise RuntimeError('series data not found')
    n = min(len(labels), len(arr))
    rows = [(labels[i], arr[i]) for i in range(n)]
    if not d4:                                   # mm-dd-yy
        yy_year = int(rows[-1][0].split('-')[2])
        cur, prev, out = None, None, []
        base = 2000 + yy_year
        for lab, v in rows:
            mm, dd, yy = [int(x) for x in lab.split('-')]
            y = base if yy == yy_year else base - 1
            ymd = '%04d-%02d-%02d' % (y, mm, dd)
            out.append((ymd, v))
        rows = out
    rows.sort()
    return rows


def fetch_series(pid):
    page = 'https://www.100ppi.com/rawmex/detail-%d.html' % pid
    js = unpack(_get('https://www.100ppi.com/graph/cindex.php?f=graph_ppid_ave&ppid=%d' % pid,
                     referer=page))
    return parse_series(js), page


def fetch_page_text(pid):
    t = _get('https://www.100ppi.com/rawmex/detail-%d.html' % pid)
    t = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', t)
    t = re.sub(r'(?s)<[^>]+>', ' ', t)
    t = re.sub(r'&nbsp;', ' ', t)
    t = re.sub(r'[ \t\r\f\v]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t)
    return t.strip()


if __name__ == '__main__':
    import sys
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    here = os.path.dirname(os.path.abspath(__file__))
    raw = os.path.join(os.path.dirname(here), 'raw')
    os.makedirs(raw, exist_ok=True)
    for pid in [int(x) for x in sys.argv[1:]] or [107, 640, 368]:
        rows, page = fetch_series(pid)
        txt = fetch_page_text(pid)
        open(os.path.join(raw, 'ppi_%d_page.txt' % pid), 'w', encoding='utf-8').write(txt)
        json.dump(rows, open(os.path.join(raw, 'ppi_%d_series.json' % pid), 'w', encoding='utf-8'))
        print('=== pid', pid, 'n=', len(rows), rows[0][0], '..', rows[-1][0],
              'last=', rows[-1][1])
        print('   page head:', txt[:260].replace('\n', ' '))
