# -*- coding: utf-8 -*-
"""期货序列采集：主连 + 具体合约（东方财富公开行情接口，无需 key）。

用法：
  python fetch_futures.py 甲醇 PP PVC --out raw          # 取主连
  python fetch_futures.py 甲醇 --contracts 2611,2612,2701,2705 --out raw
  python fetch_futures.py --list                          # 内置品种表
  python fetch_futures.py 甲醇 --probe                    # 只探活

产出 raw/<标签>.json：{secid,name,count,first,last,rows:[{d,o,c,h,l,v,amt,pct}]}
注意：主连/合约价均不含税、含交割成本，与现货含税价不可直接相减，
      基差必须用「同期限合约 + 明示含税口径」计算，并在报告里写清。
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Referer': 'https://quote.eastmoney.com/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
HOSTS = ['push2his.eastmoney.com', '23.push2his.eastmoney.com', '45.push2his.eastmoney.com']
KLINE = ('https://{host}/api/qt/stock/kline/get?secid={secid}'
         '&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57,f58'
         '&klt={klt}&fqt=0&beg={beg}&end=20500101&lmt=10000')


def get(url, tries=6, base=1.0):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
        except Exception as e:                      # RemoteDisconnected / 502 都重试
            last = e
            time.sleep(base * (1.7 ** i) + random.random())
    raise RuntimeError('请求失败（%d 次）：%s\n%s' % (tries, last, url))


def kline(secid, beg='20250101', klt='101'):
    for host in HOSTS:
        url = KLINE.format(host=host, secid=secid, beg=beg, klt=klt)
        try:
            d = json.loads(get(url, tries=3))
        except Exception:
            continue
        if d.get('rc') == 0 and d.get('data'):
            dd = d['data']
            rows = []
            for s in dd.get('klines') or []:
                p = s.split(',')
                rows.append({'d': p[0], 'o': float(p[1]), 'c': float(p[2]), 'h': float(p[3]),
                             'l': float(p[4]), 'v': float(p[5] or 0), 'amt': float(p[6] or 0),
                             'pct': float(p[7]) if p[7] not in ('', '-') else None})
            rows.sort(key=lambda r: r['d'])
            return {'secid': secid, 'name': dd.get('name'), 'code': dd.get('code'),
                    'count': len(rows), 'first': rows[0]['d'] if rows else None,
                    'last': rows[-1]['d'] if rows else None, 'rows': rows}
        if d.get('rc') == 100:                       # 该合约无数据
            return {'secid': secid, 'name': None, 'count': 0, 'rows': [], 'rc': 100}
    return {'secid': secid, 'name': None, 'count': 0, 'rows': [], 'err': True}


def save(label, res, out):
    res['label'] = label
    path = os.path.join(out, '%s.json' % label)
    common.dump_json(res, path)
    rows = res.get('rows') or []
    common.ok('%-12s %-10s n=%-4s %s ~ %s  last=%s' % (
        label, res.get('secid'), res.get('count'), res.get('first'), res.get('last'),
        rows[-1]['c'] if rows else '-'))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('products', nargs='*', help='品种中文名/代码：甲醇 PP PVC')
    ap.add_argument('--contracts', help='合约月份，逗号分隔，如 2611,2612,2701,2705')
    ap.add_argument('--out', default='raw')
    ap.add_argument('--beg', default='20250101')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--probe', action='store_true')
    a = ap.parse_args()

    if a.list:
        print('%-8s %-12s %-6s %s' % ('品种', 'secid', '代码', '交易所'))
        for k, (secid, code, exch, _) in common.PRODUCT_LIB.items():
            print('%-8s %-12s %-6s %s' % (k, secid, code, exch))
        return

    if not a.products:
        common.die('请给品种名（或 --list 查看内置品种）')

    os.makedirs(a.out, exist_ok=True)
    index_path = os.path.join(a.out, '_index.json')
    index = common.load_json(index_path) if os.path.exists(index_path) else {}

    for p in a.products:
        if p not in common.PRODUCT_LIB:
            common.warn('未内置品种「%s」，跳过；如需新增请在 common.PRODUCT_LIB 登记' % p)
            continue
        secid = common.PRODUCT_LIB[p][0]
        try:
            main_res = kline(secid, a.beg)
        except Exception as e:
            common.warn('%s 主连抓取失败：%s' % (p, e))
            continue
        if a.probe:
            print(json.dumps({k: v for k, v in main_res.items() if k != 'rows'},
                             ensure_ascii=False, indent=1))
            for r in (main_res.get('rows') or [])[-3:]:
                print(' ', r)
            continue
        save('%s主连' % p, main_res, a.out)
        index['%s主连' % p] = {'product': p, 'secid': secid, 'count': main_res.get('count'),
                               'last': main_res.get('last'), 'kind': 'main'}
        if a.contracts:
            for yymm in [x.strip() for x in a.contracts.split(',') if x.strip()]:
                csid = common.contract_secid(p, yymm)
                try:
                    res = kline(csid, a.beg)
                except Exception as e:
                    common.warn('%s%s 抓取失败：%s' % (p, yymm, e))
                    continue
                if not res.get('count'):
                    common.warn('%s%s（%s）无数据，可能已到期或代码不在该市场' % (p, yymm, csid))
                    continue
                save('%s%s' % (p, yymm), res, a.out)
                index['%s%s' % (p, yymm)] = {'product': p, 'secid': csid, 'month': yymm,
                                            'count': res.get('count'), 'last': res.get('last'),
                                            'kind': 'contract'}
                time.sleep(0.5)
        time.sleep(0.5)

    common.dump_json(index, index_path)
    common.ok('索引已写入 %s（%d 条序列）' % (index_path, len(index)))


if __name__ == '__main__':
    main()
