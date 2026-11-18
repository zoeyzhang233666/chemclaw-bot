# -*- coding: utf-8 -*-
"""抓取真实期货合约日线（新浪财经公开 K 线接口）→ data/raw/<SYMBOL>.csv

用法
----
    python scripts/fetch_futures.py SA                 # 抓 SA 全部历史合约 + 当前挂牌合约
    python scripts/fetch_futures.py SA --years 2023 2024 2025 2026
    python scripts/fetch_futures.py SA --extra SA2801 SA2805

说明
----
- 接口：`stock2.finance.sina.com.cn/futures/api/jsonp.php` 的 `InnerFuturesNewService.getDailyKLine`，
  返回 d/o/h/l/c/v/p/s = 日期/开/高/低/**收盘**/**成交量**/**持仓量**/**结算价**。
- 只抓**真实存在**的合约代码；代码不存在时返回空，脚本记为 "missing"，绝不补数。
- 逐合约（非主力连续）序列没有换月跳变，是计算月差的唯一正确基础。
- 每个合约的上市首日以接口返回的第一根 K 线为准（合约挂牌日，通常距交割约 12-13 个月）。
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
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAWDIR = os.path.join(ROOT, 'data', 'raw')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
PAT = re.compile(r'\{"d":"(\d{4}-\d\d-\d\d)","o":"([\d.\-]+)","h":"([\d.\-]+)","l":"([\d.\-]+)",'
                 r'"c":"([\d.\-]+)","v":"([\d.\-]+)","p":"([\d.\-]+)","s":"([\d.\-]+)"')
MONTHS = (1, 3, 5, 9, 12)

try:  # 老版 Python / 企业代理常缺根证书
    ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
except Exception:  # pragma: no cover
    pass


def http_get(url: str, referer: str = 'https://finance.sina.com.cn/', timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': referer})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.read()


def kline_url(symbol: str) -> str:
    var = 'var%20_BASE='
    return ('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/' + var +
            '/InnerFuturesNewService.getDailyKLine?symbol=' + symbol)


def fetch_kline(symbol: str, retries: int = 3) -> list:
    last = None
    for i in range(retries):
        try:
            text = http_get(kline_url(symbol)).decode('utf-8', 'ignore')
            return PAT.findall(text)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 404):
                return []
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(1.0 + i)
    raise RuntimeError(f'{symbol} 抓取失败: {last}')


def quote_symbols(symbols: list) -> dict:
    """实时行情（当日快照），字段位置见 references/04-数据源与口径清单.md。"""
    out = {}
    if not symbols:
        return out
    raw = http_get('https://hq.sinajs.cn/list=' + ','.join('nf_' + s for s in symbols))
    text = raw.decode('gb18030', 'ignore')
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
                'close': float(f[5]), 'settle_prev': float(f[6]), 'bid': float(f[7]),
                'ask': float(f[8]), 'last': float(f[9]), 'settle': float(f[10]),
                'volume': float(f[11]), 'oi': float(f[13]), 'offset_oi': float(f[14]),
                'exchange': f[15], 'trade_date': f[17],
            }
        except (IndexError, ValueError):
            out[code] = None
    return out


def candidate_symbols(product: str, years: list) -> list:
    return [f'{product}{y % 100:02d}{m:02d}' for y in years for m in MONTHS]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='抓取期货逐合约日线')
    ap.add_argument('product', help='品种代码，如 SA')
    ap.add_argument('--years', nargs='*', type=int, default=None,
                    help='交割年份（默认：今年-3 .. 今年+2）')
    ap.add_argument('--extra', nargs='*', default=[], help='额外合约代码')
    ap.add_argument('--sleep', type=float, default=0.35)
    args = ap.parse_args(argv)

    product = args.product.upper()
    now_year = time.localtime().tm_year
    years = args.years or list(range(now_year - 3, now_year + 3))
    syms = candidate_symbols(product, years) + [s.upper() for s in args.extra]
    syms = list(dict.fromkeys(syms))

    os.makedirs(RAWDIR, exist_ok=True)
    manifest = {
        'product': product,
        'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'source': '新浪财经 InnerFuturesNewService.getDailyKLine（公开 JSONP 接口）',
        'contracts': {},
    }
    ok = 0
    for s in syms:
        try:
            rows = fetch_kline(s)
        except RuntimeError as e:
            print(f'[失败] {e}')
            manifest['contracts'][s] = {'status': 'error'}
            continue
        if not rows:
            manifest['contracts'][s] = {'status': 'missing'}
            print(f'[无合约] {s}')
            time.sleep(args.sleep)
            continue
        path = os.path.join(RAWDIR, s + '.csv')
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'settle'])
            for r in rows:
                w.writerow([r[0]] + [float(v) for v in r[1:]])
        manifest['contracts'][s] = {
            'status': 'ok', 'rows': len(rows), 'first_date': rows[0][0],
            'last_date': rows[-1][0], 'last_settle': float(rows[-1][7]),
            'last_oi': float(rows[-1][6]), 'file': os.path.relpath(path, ROOT),
        }
        ok += 1
        print(f'[成功] {s} {len(rows):>4} 行 {rows[0][0]} ~ {rows[-1][0]}  '
              f'结算 {float(rows[-1][7]):.0f} 持仓 {float(rows[-1][6]):,.0f}')
        time.sleep(args.sleep)

    live = quote_symbols([s for s, v in manifest['contracts'].items()
                          if v.get('status') == 'ok' and v.get('last_date', '') >=
                          time.strftime('%Y-%m-%d', time.localtime(time.time() - 3 * 86400))])
    manifest['live_quotes'] = {k: v for k, v in live.items() if v}
    with open(os.path.join(ROOT, 'data', 'fetch_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'\n完成：{ok} 个合约 → {os.path.relpath(RAWDIR, ROOT)}；清单 data/fetch_manifest.json')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
