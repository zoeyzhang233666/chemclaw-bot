# -*- coding: utf-8 -*-
"""fetch_futures.py — 逐合约日线 + 自建「主力连续」与「近月连续」，带换月日志

来源：新浪财经公开逐合约日线（实测可用，无需登录）
  https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/InnerFuturesNewService.getDailyKLine?symbol=PP2605
字段：d 日期 / o 开 / h 高 / l 低 / c 收 / v 量 / p 持仓 / s 结算
每个合约接口约返回 240 个交易日（≈合约挂牌至到期的后段），因此生成连续序列需
遍历多年、多月份的全部合约代码。

连续规则（写入报告，必须可复现）
--------------------------------
1. 候选合约：品种前缀 + 年份后两位 + 月份（如 PP2605），枚举 [今天-6年, 今天+2年]。
2. 主力连续 main：每个交易日取「当日持仓量 oi 最大」且未过最后交易日的合约。
3. 近月连续 near：每个交易日取「交割月 >= 当日月份」的最近月份合约；
   若该合约持仓 < 当日主力持仓 × MIN_OI_FRAC（默认 5%），视为流动性不足，
   顺延到下一月份合约（跳过原因写入日志）。
4. 最后交易日：以该合约 K 线最后一根日线为准（LTD = max(date)）。
5. 换月日标记 is_roll=1，并记录 移出/移入合约 与 同日价差，供「换月伪跳空」披露。

输出：data/raw/fut/{code}_contracts.csv   逐合约原始日线
      data/raw/fut/{code}_main.csv        主力连续
      data/raw/fut/{code}_near.csv        近月连续
      data/raw/fut/{code}_rolls.csv       换月日志
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys

from .http import Http

BASE = ('https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/'
        'InnerFuturesNewService.getDailyKLine?symbol=')
MIN_OI_FRAC = 0.05


def contract_code(prefix: str, y: int, m: int) -> str:
    return '%s%02d%02d' % (prefix, y % 100, m)


def candidate_contracts(prefix: str, y0: int, y1: int) -> list[str]:
    out = []
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            out.append(contract_code(prefix, y, m))
    return out


def parse_klines(data, symbol: str) -> list[dict]:
    rows = []
    for k in data or []:
        try:
            rows.append(dict(symbol=symbol, date=k['d'], open=float(k['o']), high=float(k['h']),
                             low=float(k['l']), close=float(k['c']),
                             volume=float(k.get('v') or 0), oi=float(k.get('p') or 0),
                             settle=float(k['s']) if k.get('s') else ''))
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def fetch_all_contracts(http: Http, prefix: str, y0: int, y1: int,
                        verbose: bool = True) -> dict[str, list[dict]]:
    out = {}
    syms = candidate_contracts(prefix, y0, y1)
    for s in syms:
        data = http.jsonp(BASE + s)
        rows = parse_klines(data, s)
        if rows:
            out[s] = sorted(rows, key=lambda r: r['date'])
    if verbose:
        ds = [v[-1]['date'] for v in out.values()]
        print('[fut] %s contracts=%d/%d last=%s' % (prefix, len(out), len(syms),
                                                    max(ds) if ds else '-'), flush=True)
    return out


def _ym(sym: str):
    return 2000 + int(sym[2:4]), int(sym[4:6])


def build_continuous(contracts: dict[str, list[dict]], min_oi_frac: float = MIN_OI_FRAC):
    """返回 (main_rows, near_rows, rolls)。"""
    idx = {s: {r['date']: r for r in v} for s, v in contracts.items()}
    ltd = {s: v[-1]['date'] for s, v in contracts.items()}
    dates = sorted({d for v in idx.values() for d in v})
    main, near, rolls = [], [], []
    prev_main = prev_near = None
    for d in dates:
        y, m = int(d[:4]), int(d[5:7])
        live = [(s, idx[s][d]) for s in idx if d in idx[s]]
        if not live:
            continue
        best_sym, best = max(live, key=lambda x: x[1]['oi'])
        # ---- 主力连续
        rec = dict(date=d, symbol=best_sym, close=best['close'], oi=best['oi'],
                   volume=best['volume'], settle=best['settle'], is_roll=0)
        if prev_main and prev_main['symbol'] != best_sym:
            rec['is_roll'] = 1
            old = idx.get(prev_main['symbol'], {}).get(d)
            rolls.append(dict(series='main', date=d, from_symbol=prev_main['symbol'],
                              to_symbol=best_sym,
                              from_close=old['close'] if old else '',
                              to_close=best['close'],
                              same_day_spread=round(old['close'] - best['close'], 2) if old else ''))
        main.append(rec)
        prev_main = rec
        # ---- 近月连续
        cands = []
        yy, mm = y, m
        for _ in range(10):
            cands.append(contract_code(best_sym[:len(best_sym) - 4], yy, mm))
            mm += 1
            if mm > 12:
                mm, yy = 1, yy + 1
        chosen = None
        for s in cands:
            c = idx.get(s)
            if not c or d not in c or ltd.get(s, '') < d:
                continue
            oi = c[d]['oi']
            if oi < min_oi_frac * best['oi']:
                continue
            chosen = (s, c[d])
            break
        if chosen is None:
            chosen = (best_sym, best)
        s, r = chosen
        rec2 = dict(date=d, symbol=s, close=r['close'], oi=r['oi'], volume=r['volume'],
                    settle=r['settle'], is_roll=0, days_to_expiry='')
        rec2['days_to_expiry'] = sum(1 for x in dates if d <= x <= ltd.get(s, d))
        if prev_near and prev_near['symbol'] != s:
            rec2['is_roll'] = 1
            old = idx.get(prev_near['symbol'], {}).get(d)
            rolls.append(dict(series='near', date=d, from_symbol=prev_near['symbol'], to_symbol=s,
                              from_close=old['close'] if old else '',
                              to_close=r['close'],
                              same_day_spread=round(old['close'] - r['close'], 2) if old else ''))
        near.append(rec2)
        prev_near = rec2
    return main, near, rolls


def _w(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def fetch_product(http: Http, prod: dict, years_back: int = 6, years_fwd: int = 2,
                  verbose: bool = True) -> dict:
    prefix = prod['futures_contract_prefix']
    today = dt.date.today()
    y0, y1 = today.year - years_back, today.year + years_fwd
    contracts = fetch_all_contracts(http, prefix, y0, y1, verbose=verbose)
    main, near, rolls = build_continuous(contracts)
    raw = [r for v in contracts.values() for r in v]
    out = 'data/raw/fut'
    _w(os.path.join(out, '%s_contracts.csv' % prefix), raw)
    _w(os.path.join(out, '%s_main.csv' % prefix), main)
    _w(os.path.join(out, '%s_near.csv' % prefix), near)
    _w(os.path.join(out, '%s_rolls.csv' % prefix), rolls)
    meta = dict(prefix=prefix, contracts=len(contracts), bars=len(raw),
                main_days=len(main), near_days=len(near), rolls=len(rolls),
                first=main[0]['date'] if main else None, last=main[-1]['date'] if main else None,
                min_oi_frac=MIN_OI_FRAC)
    with open(os.path.join(out, '%s_meta.json' % prefix), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    if verbose:
        print('   main %s..%s  near %s..%s  rolls=%d' % (
            meta['first'], meta['last'], near[0]['date'] if near else '-',
            near[-1]['date'] if near else '-', len(rolls)), flush=True)
    return meta


def main(argv=None):
    import argparse
    from .products import load_pool
    ap = argparse.ArgumentParser(description='抓取逐合约日线并生成主力/近月连续')
    ap.add_argument('--codes', default='')
    ap.add_argument('--years-back', type=int, default=6)
    ap.add_argument('--cache', default='data/cache')
    ap.add_argument('--pool', default='')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    pool = load_pool(a.pool or None)
    codes = [c.strip().upper() for c in a.codes.split(',') if c.strip()]
    if codes:
        pool = [p for p in pool if p['code'] in codes]
    http = Http(cache_dir=a.cache, sleep=0.2)
    for prod in pool:
        print('[fut] %-3s %s' % (prod['code'], prod['name']), flush=True)
        fetch_product(http, prod, years_back=a.years_back)


if __name__ == '__main__':
    main()
