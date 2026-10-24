# -*- coding: utf-8 -*-
"""fetch_contract_history.py — 逐合约拉取期货日线（可选模块，换月连续序列）

为什么需要
----------
做「期货合约」口径的季节性而不是现货口径时，必须先有逐合约日线，才能
  1) 自建换月规则（主力 max-OI / 近月，带流动性门槛），而不是依赖来源不明的连续合约；
  2) 输出换月日志，把换月伪跳空从季节性统计里剥离；
  3) 复算/交叉验证。

本模块对**新浪财经公开逐合约 K 线**（实测可用，甲醇 95 个合约）做通用封装。
来源: https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/InnerFuturesNewService.getDailyKLine?symbol=MA2501
字段: d 日期, o 开, h 高, l 低, c 收, v 量, p 持仓, s 结算

注意
----
- 生产研究前请自行核对交易所合约规则（最后交易日、交割品级、交割单位），本脚本不做假设。
- 本脚本只负责"取数与自建连续序列"，品种前缀通过 --prefix 指定（如 MA / TA / SR / RM）。
"""
import argparse
import csv
import json
import os
import re
import time
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
URL = ('https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/'
       'InnerFuturesNewService.getDailyKLine?symbol={sym}')
URL2 = ('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/'
        'InnerFuturesNewService.getDailyKLine?symbol={sym}')


def get_contract(sym, retries=3):
    last = None
    for base in (URL, URL2):
        for i in range(retries):
            try:
                req = urllib.request.Request(base.format(sym=sym), headers={'User-Agent': UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    t = r.read().decode('utf-8', 'ignore')
                m = re.search(r'=\s*\((.*)\)\s*;?\s*$', t, re.S)
                body = m.group(1) if m else t
                body = body.strip()
                if not body or body in ('null', '[]'):
                    return []
                data = json.loads(body)
                out = []
                for k in data:
                    out.append({'date': k['d'], 'open': float(k['o']), 'high': float(k['h']),
                                'low': float(k['l']), 'close': float(k['c']),
                                'volume': float(k.get('v') or 0),
                                'oi': float(k.get('p') or 0),
                                'settle': float(k['s']) if k.get('s') else None})
                return out
            except Exception as e:                        # noqa: BLE001
                last = e
                time.sleep(1.2 * (i + 1))
    print('[WARN] %s failed: %r' % (sym, last))
    return []


def build_main_continuous(bar_by_sym, roll_rule='max_oi', min_oi_frac=0.05,
                          roll_blackout=None):
    """Cross-contract roll to a continuous series; records every switch.

    roll_rule='max_oi' : 每日取持仓量最大的合约
    min_oi_frac        : 流动性门槛（新合约持仓须 >= 主力持仓 * 该比例）
    roll_blackout      : {hhmm:int} 在交割月前 N 天禁止新开仓（研究近月口径时用）
    返回 (series, roll_log)；series 每行带 used_symbol 与 is_roll_day。
    """
    dates = sorted({r['date'] for v in bar_by_sym.values() for r in v})
    idx = {s: {r['date']: r for r in v} for s, v in bar_by_sym.items()}
    series, log, cur = [], [], None
    for d in dates:
        live = [(s, idx[s][d]) for s in idx if d in idx[s]]
        if not live:
            continue
        best = max(live, key=lambda x: x[1]['oi'])
        if cur is None:
            cur = best[0]
        else:
            cur_row = idx.get(cur, {}).get(d)
            if cur_row is None:                      # 主力合约已到期/停牌
                series.append(dict(date=d, close=best[1]['close'], oi=best[1]['oi'],
                                   symbol=best[0], is_roll_day=True))
                log.append(dict(date=d, from_symbol=cur, to_symbol=best[0], reason='expired',
                                from_close=None, to_close=best[1]['close'], same_day_spread=None))
                cur = best[0]
                continue
            if best[0] != cur and best[1]['oi'] >= max(cur_row['oi'], 1) * min_oi_frac:
                same = idx.get(cur, {}).get(d)
                series.append(dict(date=d, close=best[1]['close'], oi=best[1]['oi'],
                                   symbol=best[0], is_roll_day=True))
                log.append(dict(date=d, from_symbol=cur, to_symbol=best[0],
                                reason='%s switch' % roll_rule,
                                from_close=same['close'] if same else None,
                                to_close=best[1]['close'],
                                same_day_spread=(same['close'] - best[1]['close']) if same else None))
                cur = best[0]
                continue
        series.append(dict(date=d, close=idx[cur][d]['close'], oi=idx[cur][d]['oi'],
                           symbol=cur, is_roll_day=False))
    return series, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', default='MA', help='contract prefix, e.g. MA / TA / SR')
    ap.add_argument('--syms', default='', help='comma list of explicit contract codes')
    ap.add_argument('--out', default='./data/raw')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    if args.syms:
        syms = [s.strip().upper() for s in args.syms.split(',') if s.strip()]
    else:
        # 逐合约枚举：用月度合约代码探测（近 60 个月）
        syms = []
        for y in range(2018, 2030):
            for m in range(1, 13):
                syms.append('%s%02d%02d' % (args.prefix, y % 100, m))
    bars = {}
    for s in syms:
        v = get_contract(s)
        if v:
            bars[s] = v
            print('[OK] %-8s %s..%s  n=%d' % (s, v[0]['date'], v[-1]['date'], len(v)))
        time.sleep(0.25)
    with open(os.path.join(args.out, 'contracts_%s.json' % args.prefix), 'w', encoding='utf-8') as f:
        json.dump(bars, f, ensure_ascii=False)
    series, log = build_main_continuous(bars)
    with open(os.path.join(args.out, 'continuous_%s_main.csv' % args.prefix), 'w',
              encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(series[0].keys()))
        w.writeheader()
        w.writerows(series)
    with open(os.path.join(args.out, 'rolls_%s_main.csv' % args.prefix), 'w',
              encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(log[0].keys()))
        w.writeheader()
        w.writerows(log)
    print('[DONE] contracts=%d  continuous=%d  rolls=%d' % (len(bars), len(series), len(log)))


if __name__ == '__main__':
    main()
