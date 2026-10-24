#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取生意社（100ppi.com）基准价日序列 —— 可公开核验的现货价来源。

用法：
  python fetch_prices.py --pid 541 --name 苯酐
  python fetch_prices.py --pid 541 --pid 489 --out ./prices
  python fetch_prices.py --list            # 打印已内置的常用 PID

原理：
  1) GET https://www.100ppi.com/  → 636 字节拦截页，内含 var _0x2 = "<hex>"
  2) 回填 Cookie: HW_CHECK=<hex>，重取
  3) GET https://www.100ppi.com/graph/cindex.php?f=graph_ppid_ave&ppid=<PID>
     返回 packer 混淆的 ECharts option 文本
  4) JS packer 解包，取 xAxis.data（日期）与 series[0].data（基准价）

已知限制（务必写进报告，不要绕过）：
  * 该端点固定只返回最近 93 个日历日，任何 start/end/type 参数均无效；
  * 序列含周末/节假日的承袭值，不是新报价；
  * 基准价有固定规格（如苯酐 ≥99.0%），若你需要 99.5% 片状等规格，须另加升贴水并注明"估算"；
  * 只覆盖该站收录的品种。

输出：<out>/<name>.csv（date,value）与 <out>/<name>.json（含来源与口径元信息）
"""
import argparse
import csv
import gzip
import json
import os
import random
import re
import sys
import time
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
GRAPH = 'https://www.100ppi.com/graph/cindex.php?f=graph_ppid_ave&ppid=%s'
DETAIL = 'https://www.100ppi.com/rawmex/detail-%s.html'
_HW = {'v': None}

KNOWN = {
    '541': '苯酐（≥99.0%）',
    '489': '异辛醇 / 辛醇（2-EH）',
    '538': 'DOP',
    '1963': '纯碱（重质）',
    '1160': '烧碱（32% 液碱）',
    '2001': '尿素',
    '1024': '甲醇',
    '486': 'PTA',
    '1208': '钛白粉（金红石型）',
    '333': '丙烯酸',
    '1380': '双氧水（27.5%）',
    '221': '乙二醇',
    '837': '苯乙烯',
    '306': '冰醋酸',
}


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
            if r.headers.get('Content-Encoding') == 'gzip':
                b = gzip.decompress(b)
            t = b.decode('utf-8', 'replace')
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(1 + random.random())
            continue
        m = re.search(r'var _0x2\s*=\s*"([0-9a-f]{16,})"', t)
        if m:
            _HW['v'] = m.group(1)
            time.sleep(0.4)
            continue
        return t
    raise RuntimeError('100ppi HW_CHECK handshake failed: ' + url)


def unpack(html):
    """JS packer 解包（base-62 词表，分隔符 '|'）。"""
    m = re.search(r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)", html, re.S)
    if not m:
        raise RuntimeError('no packer payload（页面结构可能变化）')
    p, words = m.group(1), m.group(4).split('|')
    dg = set('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    out, i = [], 0
    while i < len(p):
        ch = p[i]
        if ch == '\\':
            out.append(p[i + 1])
            i += 2
            continue
        if ch not in dg:
            out.append(ch)
            i += 1
            continue
        j = i
        while j < len(p) and p[j] in dg:
            j += 1
        word, idx = p[i:j], 0
        for c in word:
            idx = idx * 62 + (ord(c) - 48 if c.isdigit() else
                              ord(c) - 87 if c.islower() else ord(c) - 29)
        out.append(words[idx] if idx < len(words) and words[idx] else word)
        i = j
    return ''.join(out)


def series_of(pid):
    page = _get(DETAIL % pid, referer='https://www.100ppi.com/')
    html = _get(GRAPH % pid, referer=DETAIL % pid)
    js = unpack(html) if 'eval(function' in html else html

    dates = re.findall(r"'(\d{4}-\d{2}-\d{2})'", js)
    if not dates:
        short = re.findall(r"'(\d{1,2}-\d{1,2}-\d{1,2})'", js)
        dates = ['20%s-%02d-%02d' % (s.split('-')[2], int(s.split('-')[0]), int(s.split('-')[1]))
                 for s in short]
    arr = None
    for mm in re.finditer(r'\[([^\[\]]{200,})\]', js):
        if re.match(r'^\s*[\d.]+\s*,', mm.group(1)):
            arr = [float(v) for v in mm.group(1).split(',') if v.strip()]
            break
    if not dates or not arr:
        raise RuntimeError('未解析到日期/数值（pid=%s）' % pid)
    n = min(len(dates), len(arr))
    return page, list(zip(dates[:n], arr[:n]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', action='append', default=[])
    ap.add_argument('--name', action='append', default=[])
    ap.add_argument('--out', default='prices')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()

    if a.list or not a.pid:
        print('内置常用 PID：')
        for k, v in KNOWN.items():
            print('  %-6s %s' % (k, v))
        return 0

    os.makedirs(a.out, exist_ok=True)
    for i, pid in enumerate(a.pid):
        nm = a.name[i] if i < len(a.name) else KNOWN.get(pid, 'pid' + pid)
        page, rows = series_of(pid)
        safe = re.sub(r'[\\/:*?"<>|\s]', '_', nm)
        cp = os.path.join(a.out, safe + '.csv')
        with open(cp, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['date', 'value', 'unit', 'tax_included'])
            for d, v in rows:
                w.writerow([d, v, 'CNY/t', 'true'])
        jp = os.path.join(a.out, safe + '.json')
        json.dump({'name': nm, 'pid': pid, 'unit': 'CNY/t', 'tax_included': True,
                   'source': '生意社（100ppi.com）基准价',
                   'source_url': GRAPH % pid, 'detail_url': DETAIL % pid,
                   'freq': '日', 'method': 'graph_ppid_ave 端点 + HW_CHECK cookie + packer 解包',
                   'limitation': '端点固定返回最近 93 个日历日；含周末/节假日承袭值',
                   'retrieved_at': time.strftime('%Y-%m-%d'),
                   'rows': [{'date': d, 'value': v} for d, v in rows]},
                  open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('%-28s %d 点  %s ~ %s  末值 %.2f  -> %s'
              % (nm, len(rows), rows[0][0], rows[-1][0], rows[-1][1], cp))
    return 0


if __name__ == '__main__':
    sys.exit(main())
