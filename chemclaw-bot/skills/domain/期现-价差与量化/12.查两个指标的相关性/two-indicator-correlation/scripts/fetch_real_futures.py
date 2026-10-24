# -*- coding: utf-8 -*-
"""抓取真实期货日线（新浪财经公开 K 线接口），落地为 CSV。

用法：
  python scripts/fetch_real_futures.py MA0 TA0
  python scripts/fetch_real_futures.py          # 默认抓 MA0（郑商所甲醇主力连续）

说明：
  - 接口为公开 JSONP，返回字段 d/o/h/l/c/v/p/s = 日期/开/高/低/收/成交量/持仓/结算。
  - 无需 key，无需登录；仅用于把"期货价格"这一可得性最好的公开序列拿到本地。
  - 主力连续合约在换月处会有价格跳变，做相关性时请用结算价的环比变化，或在报告中注明。
"""
import csv
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(os.path.dirname(HERE), 'data')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
PAT = re.compile(r'"d":"(\d{4}-\d\d-\d\d)","o":"([\d.]+)","h":"([\d.]+)","l":"([\d.]+)",'
                 r'"c":"([\d.]+)","v":"([\d.]+)","p":"([\d.]+)","s":"([\d.]+)"')


def get(url, timeout=40):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA, 'Referer': 'https://finance.sina.com.cn/', 'Accept': '*/*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ('utf-8', 'gb18030', 'gbk'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'ignore')


def fetch(symbol):
    url = ('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_' + symbol + '=/'
           'InnerFuturesNewService.getDailyKLine?symbol=' + symbol)
    text = get(url)
    rows = PAT.findall(text)
    return rows


def main(argv):
    symbols = argv[1:] or ['MA0']
    os.makedirs(OUTDIR, exist_ok=True)
    for sym in symbols:
        try:
            rows = fetch(sym)
        except Exception as e:  # noqa: BLE001
            print(f'[失败] {sym}: {type(e).__name__}: {e}')
            continue
        if not rows:
            print(f'[失败] {sym}: 返回中未解析到数据（接口可能变更）')
            continue
        path = os.path.join(OUTDIR, sym + '.csv')
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'settle'])
            for r in rows:
                w.writerow([r[0]] + [float(v) for v in r[1:]])
        print(f'[成功] {sym}: {len(rows)} 行  {rows[0][0]} ~ {rows[-1][0]}  -> {path}')
        print('       抓取时间', time.strftime('%Y-%m-%d %H:%M:%S'), '数据源 新浪财经 InnerFuturesNewService')
        time.sleep(0.5)


if __name__ == '__main__':
    main(sys.argv)
