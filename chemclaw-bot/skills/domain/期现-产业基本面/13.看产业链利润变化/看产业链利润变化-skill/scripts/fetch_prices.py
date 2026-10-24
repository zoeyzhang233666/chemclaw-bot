# -*- coding: utf-8 -*-
"""PVC 产业链价格取数：主导合约/主力连续长序列 + 生意社近月基准价 + 卓创口径核实。

产出 (../raw/):
  fut_V0_daily.csv           PVC 主力连续(大连 V) 日线: close & settle
  ppi_<pid>_series.json      生意社基准价近 93 天
  series_manifest.json       每个序列的口径元数据

设计原则：只写入"网上可查到的原始日序列"，不做任何合成/插值。
"""
import os
import re
import csv
import json
import gzip
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.path.dirname(HERE), 'raw')
os.makedirs(RAW, exist_ok=True)
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


def get(url, referer=None, encoding='utf-8'):
    h = {'User-Agent': UA, 'Accept-Encoding': 'gzip'}
    if referer:
        h['Referer'] = referer
    r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40)
    b = r.read()
    if r.headers.get('Content-Encoding') == 'gzip':
        try:
            b = gzip.decompress(b)
        except Exception:
            pass
    return b.decode(encoding, 'replace')


# ---------------- 1) 新浪：期货日线 ----------------
def sina_future(symbol):
    url = ('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_=/'
           'InnerFuturesNewService.getDailyKLine?symbol=' + symbol)
    t = get(url, referer='https://finance.sina.com.cn/')
    m = re.search(r'=\s*\((\[.*\])\)\s*;?\s*$', t, re.S)
    if not m:
        m = re.search(r'\((\[.*\])\)', t, re.S)
    rows = json.loads(m.group(1))
    out = []
    for r in rows:
        out.append({'date': r['d'], 'open': float(r['o']), 'high': float(r['h']),
                    'low': float(r['l']), 'close': float(r['c']),
                    'settle': float(r.get('s') or 0), 'volume': float(r.get('v') or 0)})
    return out


# ---------------- 2) 生意社：基准价近 https://www.100ppi.com ----------------
from pippi import fetch_series  # noqa: E402

PPI = {107: 'PVC树脂(SG-5)', 640: '电石', 368: '液碱(32%)'}
# 尝试补充抓取：原盐/兰炭/动力煤/乙烯等在 100ppi 的 pid（抓不到就记为缺口）
PPI_EXTRA = {}

META = {
    'V0': dict(name='PVC期货主力连续', code='V0',
               unit='元/吨', tax='含13%增值税', region='大连商品交易所',
               spec='聚氯乙烯主力连续合约(换月拼接)',
               source='新浪财经 InnerFuturesNewService.getDailyKLine',
               url='https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_=/InnerFuturesNewService.getDailyKLine?symbol=V0',
               note='主力连续在换月日存在跳空，仅用于刻画趋势与期现计算；期货指标口径为“结算价/收盘价”，用于基差与套保参考，不等于现货出厂价。'),
}

if __name__ == '__main__':
    manifest = {}
    win = '2025-09-01'
    # 期货
    for sym, mid in [('V0', 'V0')]:
        rows = [r for r in sina_future(sym) if r['date'] >= win]
        path = os.path.join(RAW, 'fut_%s_daily.csv' % mid)
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['date', 'open', 'high', 'low', 'close', 'settle', 'volume'])
            for r in rows:
                w.writerow([r['date'], r['open'], r['high'], r['low'], r['close'], r['settle'], r['volume']])
        latest = rows[-1]
        manifest[sym] = dict(META[sym], n=len(rows), start=rows[0]['date'], end=rows[-1]['date'],
                             last_close=latest['close'], last_settle=latest['settle'],
                             file=os.path.basename(path))
        print('[OK] %s n=%d %s..%s close=%.0f settle=%.0f' %
              (sym, len(rows), rows[0]['date'], rows[-1]['date'], latest['close'], latest['settle']))

    # 生意社基准价
    for pid, nm in PPI.items():
        try:
            rows, page = fetch_series(pid)
        except Exception as e:
            print('[FAIL] ppi', pid, nm, e)
            continue
        json.dump(rows, open(os.path.join(RAW, 'ppi_%d_series.json' % pid), 'w', encoding='utf-8'))
        key = 'PPI%d' % pid
        manifest[key] = dict(name='生意社基准价：' + nm, unit='元/吨', tax='含税',
                             region='全国综合(基准规格)', spec='生意社基准规格',
                             source='生意社(100ppi) 基准价曲线',
                             url=page, n=len(rows), start=rows[0][0], end=rows[-1][0],
                             last=rows[-1][1], file='ppi_%d_series.json' % pid,
                             note='生意社基准价=价格大数据+模型生成的交易指导价，默认含税；在报价中使用“结算价=基准价×K+C”修正，故仅作现货方向的基准刻度。')
        print('[OK] ppi %-12s n=%d %s..%s last=%.0f' % (nm, len(rows), rows[0][0], rows[-1][0], rows[-1][1]))

    json.dump(manifest, open(os.path.join(RAW, 'series_manifest.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('manifest ->', os.path.join(RAW, 'series_manifest.json'))
