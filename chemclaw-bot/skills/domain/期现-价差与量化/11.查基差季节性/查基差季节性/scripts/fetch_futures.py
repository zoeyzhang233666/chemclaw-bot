# -*- coding: utf-8 -*-
"""
抓取郑商所/大连/上海期货交易所任一品种的逐合约日线（新浪财经公开接口）。

为什么必须逐合约抓：
    连续合约（如 MA0）的换月规则不透明，实测 MA0 与"持仓量最大"规则在
    1644 个交易日中有 48 天不一致（换月日滞后一天）。若研究要可复现，
    必须自己从逐合约数据构建映射。

用法：
    python fetch_futures.py --prefix MA --start 2019-01 --end 2027-12 --outdir raw
    python fetch_futures.py --prefix TA --start 2020-01 --end 2026-12 --outdir raw

输出：<outdir>/MA_MA2501.json 等，结构 {symbol, exchange, rows:[{d,o,h,l,c,v,oi,settle}]}
"""
import argparse
import json
import os
import re
import sys
import time

import requests

try:
    import brotli  # noqa: F401  很多站点返回 Content-Encoding: br
except ImportError:
    print('[WARN] 未安装 brotli，若站点返回 br 压缩会失败: pip install brotli')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

HOSTS = [
    'https://stock.finance.sina.com.cn',
    'https://stock2.finance.sina.com.cn',
]

# 交易所前缀（用于归类输出）
EXCHANGE_OF = {
    'MA': 'CZCE', 'TA': 'CZCE', 'SR': 'CZCE', 'CF': 'CZCE', 'FG': 'CZCE',
    'SA': 'CZCE', 'UR': 'CZCE', 'RM': 'CZCE', 'OI': 'CZCE', 'AP': 'CZCE',
    'RB': 'SHFE', 'HC': 'SHFE', 'CU': 'SHFE', 'AL': 'SHFE', 'RU': 'SHFE',
    'I': 'DCE', 'M': 'DCE', 'Y': 'DCE', 'P': 'DCE', 'EG': 'DCE', 'PP': 'DCE',
}


def month_iter(start, end):
    """生成 (yy, mm) 序列, 例如 2019-01 .. 2027-12"""
    sy, sm = map(int, start.split('-'))
    ey, em = map(int, end.split('-'))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def fetch_one(symbol, session, retries=3):
    """返回 {symbol, exchange, rows:[...]} 或 None"""
    for host in HOSTS:
        url = (host + '/futures/api/jsonp.php/var%20t=/'
               'InnerFuturesNewService.getDailyKLine')
        for attempt in range(retries):
            try:
                r = session.get(url, params={'symbol': symbol}, timeout=15,
                                headers={'User-Agent': UA, 'Referer': host + '/'})
                if r.status_code != 200:
                    raise RuntimeError('HTTP %s' % r.status_code)
                txt = r.text
                m = re.search(r'\((\[.*\])\)', txt, re.S)
                if not m:
                    m = re.search(r'(\[\s*\{.*\}\s*\])', txt, re.S)
                if not m:
                    raise RuntimeError('无法解析返回体 (len=%d)' % len(txt))
                raw = m.group(1)
                # 新浪字段顺序: d,o,h,l,c,v,p(持仓),s(结算)
                data = json.loads(raw)
                rows = []
                for it in data:
                    if isinstance(it, dict):
                        rows.append({'d': it.get('d'), 'o': float(it.get('o', 0) or 0),
                                     'h': float(it.get('h', 0) or 0), 'l': float(it.get('l', 0) or 0),
                                     'c': float(it.get('c', 0) or 0), 'v': float(it.get('v', 0) or 0),
                                     'oi': float(it.get('p', 0) or 0),
                                     'settle': float(it.get('s', 0) or 0)})
                if not rows:
                    return None
                prefix = re.match(r'[A-Za-z]+', symbol).group(0).upper()
                return {'symbol': symbol, 'exchange': EXCHANGE_OF.get(prefix, '?'), 'rows': rows}
            except Exception as e:
                if attempt == retries - 1:
                    print('  [FAIL] %s @%s: %s' % (symbol, host, e))
                time.sleep(0.6)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', required=True, help='品种代码，如 MA / TA / RB')
    ap.add_argument('--start', default='2019-01')
    ap.add_argument('--end', default='2027-12')
    ap.add_argument('--outdir', default='raw')
    ap.add_argument('--sleep', type=float, default=0.25)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    session = requests.Session()
    ok = fail = 0
    for y, m in month_iter(args.start, args.end):
        sym = '%s%02d%02d' % (args.prefix.upper(), y % 100, m)
        dst = os.path.join(args.outdir, '%s_%s.json' % (args.prefix.upper(), sym))
        if os.path.exists(dst) and os.path.getsize(dst) > 50:
            print('[SKIP]', sym)
            ok += 1
            continue
        d = fetch_one(sym, session)
        if d:
            with open(dst, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False)
            print('[OK] %s rows=%d %s~%s' % (sym, len(d['rows']),
                                             d['rows'][0]['d'], d['rows'][-1]['d']))
            ok += 1
        else:
            fail += 1
        time.sleep(args.sleep)
    print('\n完成: 成功 %d, 失败/无数据 %d' % (ok, fail))


if __name__ == '__main__':
    sys.exit(main())
