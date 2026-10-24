# -*- coding: utf-8 -*-
"""抓取当日挂牌合约行情 + 仓单 → quotes_<date>.json

源1（郑商所官方日报）：FutureDataDaily.txt  结算价/收盘/持仓/成交量/交割结算价
源2（郑商所官方仓单日报）：FutureDataWhsheet.txt  仓单张数/有效预报
源3（东方财富 futsseapi）：DCE 聚丙烯 全部挂牌合约（DCE 官网对脚本返回 412）

价格口径（关键）
--------------
MA/SA/TA：settle = 交易所结算价（官方），主口径
PP      ：东财只给 last（最新价）与 prev_settle（昨结算），无当日结算价
          → PP 主口径记为 last，并在 meta 标注与 CZCE 口径不同
两套口径不得混算，报表中分列 price_basis。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import ssl
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
DATE = os.environ.get('QUOTE_DATE', '2026-10-20')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0 Safari/537.36')
PRODUCTS = {'MA': '甲醇', 'SA': '纯碱', 'TA': 'PTA', 'PP': '聚丙烯'}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(url, referer):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': referer})
    with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
        b = r.read()
    for enc in ('utf-8', 'gb18030'):
        try:
            return b.decode(enc)
        except Exception:
            pass
    return b.decode('utf-8', 'ignore')


def num(s):
    s = (s or '').strip().replace(',', '')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def czce_daily(date):
    y4 = date[:4]
    url = f'http://www.czce.com.cn/cn/DFSStaticFiles/Future/{y4}/{date.replace("-", "")}/FutureDataDaily.txt'
    txt = get(url, 'http://www.czce.com.cn/')
    out = {}
    for line in txt.split('\n'):
        if '|' not in line:
            continue
        f0 = line.split('|')[0].strip()
        m = re.fullmatch(r'([A-Z]{1,3})(\d{3}|\d{4})', f0)
        if not m or m.group(1) not in PRODUCTS:
            continue
        code, mo = m.group(1), m.group(2)
        if len(mo) == 3:
            y = 2000 + int(mo[0]) + (int(y4) // 10) * 10
            mm = int(mo[1:])
        else:
            y, mm = 2000 + int(mo[:2]), int(mo[2:])
        f = [x.strip() for x in line.split('|')]
        out[f'{code}{y % 100:02d}{mm:02d}'] = {
            'symbol': f'{code}{y % 100:02d}{mm:02d}', 'product': code, 'y': y, 'm': mm,
            'price_basis': 'settle',
            'settle': num(f[6]), 'prev_settle': num(f[1]), 'open': num(f[2]),
            'high': num(f[3]), 'low': num(f[4]), 'close': num(f[5]),
            'volume': num(f[9]), 'oi': num(f[10]), 'oi_chg': num(f[11]),
            'delivery_settle': num(f[13]) if len(f) > 13 else None,
            'source': 'CZCE每日行情',
        }
    return out, url


def czce_warrant(date):
    url = (f'http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date[:4]}/'
           f'{date.replace("-", "")}/FutureDataWhsheet.txt')
    txt = get(url, 'http://www.czce.com.cn/')
    out, cur, unit = {}, None, None
    for ln in txt.split('\n'):
        if ln.strip().startswith('品种：'):
            mm = re.search(r'品种：[\u4e00-\u9fa5A-Za-z]*?([A-Z]{1,3})\b', ln)
            cur = mm.group(1) if mm else None
            up = re.search(r'每张仓单=(\d+)手合约\*(\d+)吨/手', ln)
            unit = int(up.group(2)) if up else None
            continue
        if cur in PRODUCTS and ln.strip().startswith('总计'):
            f = [x.strip() for x in ln.split('|')]
            v = [num(x) for x in f[1:]]
            nn = [x for x in v if x is not None]
            out[cur] = {'date': date, 'warrant': nn[0] if nn else None,
                        'unit_t': unit, 'fields_raw': f[1:],
                        'source': 'CZCE仓单日报', 'url': url, 'confidence': 'A'}
            cur = None
    return out, url


def em_dce():
    url = ('https://futsseapi.eastmoney.com/list/114?orderBy=ccl&sort=desc&pageSize=400'
           '&pageIndex=0&token=58b2fa8f54638b60b87d69b31969089c'
           '&field=dm,sc,name,p,zsjd,zde,zdf,f152,o,h,l,zjsj,vol,ccl')
    d = json.loads(get(url, 'https://quote.eastmoney.com/'))
    out = {}
    for x in d.get('list', []):
        m = re.fullmatch(r'([a-zA-Z]{1,3})(\d{4})', x.get('dm', ''))
        if not m or m.group(1).upper() not in PRODUCTS:
            continue
        mo = int(m.group(2))
        sym = f'{m.group(1).upper()}{mo:04d}'
        out[sym] = {'symbol': sym, 'product': m.group(1).upper(),
                    'y': 2000 + mo // 100, 'm': mo % 100, 'price_basis': 'last',
                    'settle': x.get('p'), 'prev_settle': x.get('zjsj'),
                    'open': x.get('o'), 'high': x.get('h'), 'low': x.get('l'),
                    'close': x.get('p'), 'volume': x.get('vol'), 'oi': x.get('ccl'),
                    'change': x.get('zde'), 'pct': x.get('zdf'),
                    'source': '东方财富 futsseapi'}
    return out, url


def main():
    res = {'date': DATE, 'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'sources': {}, 'contracts': {}, 'warrants': {},
           'price_basis_by_product': {}}
    try:
        c, u = czce_daily(DATE)
        res['contracts'].update(c)
        res['sources']['czce_daily'] = {'url': u, 'ok': True, 'n': len(c)}
        res['price_basis_by_product'].update({p: 'settle' for p in ('MA', 'SA', 'TA')})
        print(f'[CZCE日行情] {len(c)}')
    except Exception as e:
        res['sources']['czce_daily'] = {'ok': False, 'err': str(e)}
        print('[CZCE日行情失败]', e)
    try:
        w, u = czce_warrant(DATE)
        res['warrants'].update(w)
        res['sources']['czce_warrant'] = {'url': u, 'ok': True, 'n': len(w)}
        for k, v in w.items():
            print(f'[仓单官方] {k}: {v["warrant"]} 张 × {v["unit_t"]}t')
    except Exception as e:
        res['sources']['czce_warrant'] = {'ok': False, 'err': str(e)}
        print('[仓单失败]', e)
    try:
        p, u = em_dce()
        res['contracts'].update(p)
        res['sources']['em_dce'] = {'url': u, 'ok': True, 'n': len(p)}
        res['price_basis_by_product']['PP'] = 'last'
        print(f'[东财DCE] PP {len(p)}')
    except Exception as e:
        res['sources']['em_dce'] = {'ok': False, 'err': str(e)}
        print('[东财DCE失败]', e)

    # 交叉核对：本轮行情 vs 新浪逐合约日线末日收盘
    chk, bad = [], 0
    for sym, row in sorted(res['contracts'].items()):
        fp = os.path.join(DATA, 'raw', sym + '.csv')
        if not os.path.exists(fp):
            continue
        with open(fp, encoding='utf-8-sig') as f:
            last = f.read().strip().split('\n')[-1].split(',')
        if last[0] != DATE:
            continue
        s_close, s_settle = float(last[4]), float(last[7])
        if row.get('price_basis') == 'settle':
            # CZCE：交易所结算价/收盘价应与新浪逐合约日线完全一致
            ok_c = (row.get('close') is None) or abs(s_close - row['close']) < 1e-6
            ok_s = (row.get('settle') is None) or abs(s_settle - row['settle']) < 1e-6
            basis_ok = ok_c and ok_s
            note = '结算价+收盘价双向核对'
        else:
            # DCE：东财 settle 字段实为最新价(last)，应与新浪收盘价一致；新浪结算价属另一口径
            ok_c = (row.get('close') is None) or abs(s_close - row['close']) < 1e-6
            ok_s = None
            basis_ok = ok_c
            note = '仅核对最新价=收盘价；东财无当日结算价，新浪settle不作对照'
        if not basis_ok:
            bad += 1
        chk.append({'symbol': sym, 'basis': row.get('price_basis'),
                    'sina_close': s_close, 'sina_settle': s_settle,
                    'exch': row.get('settle'), 'ok': basis_ok, 'note': note})
    res['cross_check'] = {'n': len(chk), 'mismatch': bad, 'rows': chk,
                          'note': 'PP 口径为 last，与 CZCE 的 settle 口径不同；两者在月差计算中分列 price_basis，不混用'}
    print(f'[交叉核对] {len(chk)} 合约，口径内不一致 {bad}')

    out = os.path.join(ROOT, f'quotes_{DATE}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('saved', out)


if __name__ == '__main__':
    main()
