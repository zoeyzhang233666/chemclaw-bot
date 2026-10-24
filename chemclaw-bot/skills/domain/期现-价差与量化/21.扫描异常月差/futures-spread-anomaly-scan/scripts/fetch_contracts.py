# -*- coding: utf-8 -*-
"""抓取真实逐合约日线（新浪财经公开 JSONP 接口）→ raw/<SYMBOL>.csv + fetch_manifest.json

只抓真实存在的合约代码；不存在的一律记 missing，绝不补数。
逐合约（非主力连续）序列没有换月跳变，是计算月差的唯一正确基础。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import ssl
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
RAWDIR = os.path.join(DATA, 'raw')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
PAT = re.compile(r'\{"d":"(\d{4}-\d\d-\d\d)","o":"([\d.\-]+)","h":"([\d.\-]+)","l":"([\d.\-]+)",'
                 r'"c":"([\d.\-]+)","v":"([\d.\-]+)","p":"([\d.\-]+)","s":"([\d.\-]+)"')

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass


def http_get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': UA,
                                               'Referer': 'https://finance.sina.com.cn/'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_kline(symbol: str, retries: int = 3) -> list:
    last = None
    for i in range(retries):
        try:
            url = ('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_BASE=/'
                   'InnerFuturesNewService.getDailyKLine?symbol=' + symbol)
            text = http_get(url).decode('utf-8', 'ignore')
            return PAT.findall(text)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 404):
                return []
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(1.0 + i)
    raise RuntimeError(f'{symbol}: {last}')


def quote_symbols(symbols: list) -> dict:
    out = {}
    if not symbols:
        return out
    text = http_get('https://hq.sinajs.cn/list=' + ','.join('nf_' + s for s in symbols)).decode(
        'gb18030', 'ignore')
    for line in text.split('\n'):
        if '=' not in line:
            continue
        name, body = line.split('=', 1)
        code = name.replace('var hq_str_nf_', '').strip()
        body = body.strip().rstrip(';').strip('"')
        if not body:
            out[code] = None
            continue
        f = body.split(',')
        try:
            out[code] = {
                'name': f[0], 'open': float(f[2]), 'high': float(f[3]), 'low': float(f[4]),
                'close': float(f[5]), 'settle_prev': float(f[6]), 'last': float(f[9]),
                'settle': float(f[10]), 'volume': float(f[11]), 'oi': float(f[13]),
                'offset_oi': float(f[14]), 'exchange': f[15], 'trade_date': f[17],
            }
        except (IndexError, ValueError):
            out[code] = None
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--products', nargs='+', default=['MA', 'SA', 'PP', 'TA'])
    ap.add_argument('--months', nargs='+', type=int, default=list(range(1, 13)),
                    help='探测交割月份（先全 12 个月试，用于反推真实挂牌月份）')
    ap.add_argument('--years', nargs='*', type=int, default=None)
    ap.add_argument('--sleep', type=float, default=0.22)
    args = ap.parse_args(argv)

    now_year = time.localtime().tm_year
    years = args.years or list(range(now_year - 2, now_year + 3))
    os.makedirs(RAWDIR, exist_ok=True)
    manifest = {'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': '新浪财经 InnerFuturesNewService.getDailyKLine（公开 JSONP 接口）'
                          ' + hq.sinajs.cn 实时快照',
                'products': {}}

    for product in args.products:
        product = product.upper()
        syms = [f'{product}{y % 100:02d}{m:02d}' for y in years for m in args.months]
        syms = list(dict.fromkeys(syms))
        pman = {'requested': len(syms), 'contracts': {}}
        ok = 0
        # 每一年单独记，避免年报错中断整轮
        for s in syms:
            try:
                rows = fetch_kline(s)
            except Exception as e:  # noqa: BLE001
                pman['contracts'][s] = {'status': 'error', 'msg': str(e)[:120]}
                print(f'[失败] {e}', flush=True)
                time.sleep(args.sleep)
                continue
            if not rows:
                pman['contracts'][s] = {'status': 'missing'}
                time.sleep(args.sleep * 0.5)
                continue
            path = os.path.join(RAWDIR, s + '.csv')
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f)
                w.writerow(['date', 'open', 'high', 'low', 'close', 'volume',
                            'open_interest', 'settle'])
                for r in rows:
                    w.writerow([r[0]] + [float(v) for v in r[1:]])
            sy, sm = 2000 + int(s[-4:-2]), int(s[-2:])
            pman['contracts'][s] = {
                'status': 'ok', 'y': sy, 'm': sm, 'rows': len(rows),
                'first_date': rows[0][0], 'last_date': rows[-1][0],
                'last_settle': float(rows[-1][7]), 'last_oi': float(rows[-1][6]),
                'file': s + '.csv',
            }
            ok += 1
            print(f'[OK] {s:8s} {len(rows):>4} bars  {rows[0][0]}~{rows[-1][0]}  '
                  f'S={float(rows[-1][7]):>8.0f} OI={float(rows[-1][6]):>10,.0f}', flush=True)
            time.sleep(args.sleep)
        manifest['products'][product] = pman
        print(f'== {product}: {ok} contracts ok', flush=True)

    # 实时快照：取每个合约最近 5 日内仍有成交/持仓者
    recent = time.strftime('%Y-%m-%d', time.localtime(time.time() - 5 * 86400))
    live_syms = [s for p in manifest['products'].values()
                 for s, v in p['contracts'].items()
                 if v.get('status') == 'ok' and v.get('last_date', '') >= recent]
    for i in range(0, len(live_syms), 40):
        chunk = live_syms[i:i + 40]
        try:
            live = quote_symbols(chunk)
            manifest.setdefault('live_quotes', {}).update({k: v for k, v in live.items() if v})
        except Exception as e:  # noqa: BLE001
            print('[快照失败]', e, flush=True)
        time.sleep(0.4)

    with open(os.path.join(HERE, 'fetch_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print('done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
