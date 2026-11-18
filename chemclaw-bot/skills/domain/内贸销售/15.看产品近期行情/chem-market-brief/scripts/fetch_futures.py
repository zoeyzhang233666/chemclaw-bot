# -*- coding: utf-8 -*-
"""按品种抓取期货主连日线（东方财富公开行情接口，免费、无需 key）。

用法：
  python fetch_futures.py 纯碱 --out raw/纯碱_daily.json
  python fetch_futures.py 玻璃 --out raw/玻璃_daily.json --beg 20180101
  python fetch_futures.py --list            # 列出内置品种表
  python fetch_futures.py 纯碱 --secid 115.SAM --probe   # 只探活，不落盘

产出 JSON：[{d,o,c,h,l,v,pct,amt}]，按日期升序。
说明：主连（连续合约）价格不含税、含交割成本，与现货含税价不可直接相减。
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36',
    'Referer': 'https://quote.eastmoney.com/',
    'Accept': '*/*',
}

KLINE = ('https://push2his.eastmoney.com/api/qt/stock/kline/get'
         '?secid={secid}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57,f58'
         '&klt=101&fqt=0&beg={beg}&end=20500101&lmt=10000')

LIST = ('https://futsseapi.eastmoney.com/list/{mkt}?orderBy=zdf&sort=desc&pageSize=400&pageIndex=0'
        '&token=1101ffec366cf74a9b8c6d2a1a0e9d3f&field=dm,sc,name&_={ts}')


def get(url, tries=6, pause=2.0):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=25).read().decode('utf-8', 'ignore')
        except Exception as e:                     # 网络抖动 / RemoteDisconnected 都重试
            last = e
            time.sleep(pause * (i + 1) * 0.5)
    raise RuntimeError('请求失败（已重试 %d 次）：%s\n%s' % (tries, last, url))


def resolve(product, mkt=None, code=None):
    """品种名 -> (secid, 交易所名, 主连代码)。优先用内置表，其次在线枚举。"""
    if mkt and code:
        return '%s.%s' % (mkt, code), common.MARKETS.get(mkt, mkt), code
    hit = common.PRODUCT_LIB.get(product)
    if hit:
        mkt, code, exch = hit
        return '%s.%s' % (mkt, code), exch, code
    for mk in ('115', '114', '113', '142', '225'):
        try:
            d = json.loads(get(LIST.format(mkt=mk, ts=int(time.time() * 1000)), tries=3))
        except Exception:
            continue
        for x in d.get('list', []):
            if x.get('name') == product + '主连':
                return '%s.%s' % (mk, x['dm']), common.MARKETS[mk], x['dm']
    raise RuntimeError('未找到品种「%s」的期货主连。请用 --secid 手动指定，'
                       '或确认该品种没有场内期货（如多数精细化工品）。' % product)


def fetch(secid, beg='20180101'):
    url = KLINE.format(secid=secid, beg=beg)
    d = json.loads(get(url))
    if d.get('rc') not in (0, None) or not d.get('data'):
        raise RuntimeError('接口无数据：secid=%s rc=%s' % (secid, d.get('rc')))
    dd = d['data']
    out = []
    for s in dd.get('klines') or []:
        p = s.split(',')
        row = {'d': p[0], 'o': float(p[1]), 'c': float(p[2]), 'h': float(p[3]), 'l': float(p[4]),
               'v': float(p[5] or 0), 'amt': float(p[6] or 0)}
        try:
            row['pct'] = float(p[7]) if p[7] not in ('', '-') else None
        except Exception:
            row['pct'] = None
        out.append(row)
    out.sort(key=lambda r: r['d'])
    return {'name': dd.get('name'), 'secid': secid, 'code': dd.get('code'),
            'count': len(out), 'first': out[0]['d'] if out else None, 'last': out[-1]['d'] if out else None,
            'rows': out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('product', nargs='?', help='品种中文名，如 纯碱 / 玻璃 / 烧碱')
    ap.add_argument('--out', help='输出 JSON 路径')
    ap.add_argument('--beg', default='20180101', help='起始日期 YYYYMMDD')
    ap.add_argument('--secid', help='直接指定，如 115.SAM')
    ap.add_argument('--mkt', help='市场代码，配合 --code 使用')
    ap.add_argument('--code', help='主连代码，如 SAM')
    ap.add_argument('--list', action='store_true', help='打印内置品种表')
    ap.add_argument('--probe', action='store_true', help='只探活，不写文件')
    a = ap.parse_args()

    if a.list:
        print('%-8s %-6s %-6s %s' % ('品种', '市场', '代码', '交易所'))
        for k, (mk, code, exch) in common.PRODUCT_LIB.items():
            print('%-8s %-6s %-6s %s' % (k, mk, code, exch))
        return

    if not a.product and not a.secid:
        common.die('请给品种名或 --secid')

    if a.secid:
        secid, exch, code = a.secid, '', a.secid.split('.')[-1]
    else:
        secid, exch, code = resolve(a.product, a.mkt, a.code)

    common.ok('目标合约 %s（%s）' % (secid, exch or '手工指定'))
    res = fetch(secid, a.beg)
    common.ok('拿到 %d 根日线，%s ~ %s，合约名「%s」' % (res['count'], res['first'], res['last'], res['name']))
    if a.probe:
        print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, ensure_ascii=False, indent=1))
        print('最后 3 根：')
        for r in res['rows'][-3:]:
            print(' ', r)
        return
    out = a.out or os.path.join('raw', '%s_daily.json' % (a.product or code))
    common.dump_json(res, out)
    common.ok('已写入 %s（%.1f KB）' % (out, os.path.getsize(out) / 1024))


if __name__ == '__main__':
    main()
