#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基差计算命令行（品种无关，纯标准库）。

用法：
  python calc_basis.py --spot data/spot.csv --futures data/futures.csv \
      --asof 2026-10-20 --dates 2026-09-21,2026-10-09 --windows 1y,3y,5y \
      --out build/basis.json

输入格式（CSV，UTF-8 或 UTF-8-BOM，首行表头，列名可配置）：

  spot.csv（现货）
    date,spot_low,spot_high[,spot]
    date 必填；spot_low/high 给区间则取中点；也可直接给 spot 列。

  futures.csv（期货，**每行一个合约**，不要拼接）
    date,contract,close[,open,high,low,settle,volume,oi]

输出 JSON 结构见 README。所有数字都带 n / n_window / source 说明，便于追溯。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import basislib as B                                             # noqa: E402

TRADING_DAYS_PER_YEAR = 244


def read_csv(path):
    if not os.path.exists(path):
        sys.exit('找不到文件：%s' % path)
    # utf-8-sig 兼容 BOM；Excel 导出常带 BOM
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def fnum(x):
    if x is None or x == '':
        return None
    try:
        return float(str(x).replace(',', '').strip())
    except ValueError:
        return None


def load_spot(path, low='spot_low', high='spot_high', direct='spot'):
    out = {}
    for r in read_csv(path):
        d = (r.get('date') or '').strip()
        if not d:
            continue
        v = fnum(r.get(direct))
        if v is None:
            lo, hi = fnum(r.get(low)), fnum(r.get(high))
            v = (lo + hi) / 2.0 if (lo is not None and hi is not None) else None
        # 无价日保留在表里但不进入基差（不插值）
        out[d] = v
    return out


def load_futures(path):
    closes, oi, dates = {}, {}, set()
    for r in read_csv(path):
        d = (r.get('date') or '').strip()
        c = (r.get('contract') or '').strip()
        cl = fnum(r.get('close'))
        if not d or not c or cl is None:
            continue
        closes.setdefault(d, {})[c] = cl
        o = fnum(r.get('oi'))
        if o is not None:
            oi[d] = oi.get(d, {})
            oi[d][c] = o
        dates.add(d)
    return closes, oi, sorted(dates)


def pick_main(dates, closes, oi):
    """主力 = 当日持仓量最大的合约；没有 oi 列则退化为成交量最大的合约。"""
    mains = {}
    for d in dates:
        row = oi.get(d)
        if row:
            mains[d] = max(row.items(), key=lambda kv: kv[1])[0]
        elif closes.get(d):
            mains[d] = max(closes[d].items(), key=lambda kv: kv[1])[0]
    return mains


def window_start(asof, years):
    d = datetime.strptime(asof, '%Y-%m-%d').date()
    return (d - timedelta(days=int(round(365.25 * years)))).isoformat()


def main():
    ap = argparse.ArgumentParser(description='现货-期货基差计算（品种无关）')
    ap.add_argument('--spot', required=True, help='现货 CSV')
    ap.add_argument('--futures', required=True, help='期货 CSV（每行一个合约）')
    ap.add_argument('--asof', required=True, help='基准日 YYYY-MM-DD')
    ap.add_argument('--dates', default='', help='额外比较日，逗号分隔（用于近 30 天变化）')
    ap.add_argument('--windows', default='1y,3y,5y', help='分位窗口，逗号分隔')
    ap.add_argument('--contracts', default='', help='指定展示的合约，逗号分隔（留空=自动取近月与主力）')
    ap.add_argument('--min-n', type=int, default=B.MIN_N_FOR_PERCENTILE,
                    help='给历史分位所需的最小样本数')
    ap.add_argument('--out', required=True, help='输出 JSON')
    args = ap.parse_args()

    spot = load_spot(args.spot)
    closes, oi, fdates = load_futures(args.futures)
    if args.asof not in closes:
        sys.exit('基准日 %s 在期货数据中不存在' % args.asof)
    if args.asof not in spot or spot[args.asof] is None:
        sys.exit('基准日 %s 没有现货报价，不能计算基差（不插值）' % args.asof)

    mains = pick_main(fdates, closes, oi)
    asof = args.asof
    spot_now = spot[asof]
    main_c = mains.get(asof)
    fut_now = closes[asof].get(main_c)

    # ---------- 各合约口径对比
    contracts = {}
    want = [c.strip() for c in args.contracts.split(',') if c.strip()] or sorted(closes[asof])
    for c in want:
        if c not in closes[asof]:
            continue
        contracts[c] = {
            'close': closes[asof][c],
            'basis': B.basis(spot_now, closes[asof][c]),
            'basis_rate': B.basis_rate(spot_now, closes[asof][c]),
            'is_main': c == main_c,
        }

    # ---------- 换月与跳空
    rolls = B.roll_events(fdates, mains, closes)
    seq = [{'date': d, 'close': closes[d][mains[d]]} for d in fdates if mains.get(d) in closes.get(d, {})]
    adj = B.forward_adjust(seq, rolls)

    # ---------- 真实配对样本
    pairs = sorted(d for d in fdates if d in spot and spot[d] is not None and mains.get(d) in closes[d])
    basis_series = [(d, round(spot[d] - closes[d][mains[d]], 2)) for d in pairs]

    # ---------- 分位窗口
    windows = {}
    for w in [x.strip() for x in args.windows.split(',') if x.strip()]:
        yr = float(w.rstrip('yY'))
        start = window_start(asof, yr)
        vals = [v for d, v in basis_series if start <= d <= asof]
        stats = B.window_stats(vals, round(spot_now - fut_now, 2), min_n=args.min_n)
        cov = B.coverage_check(pairs, start, asof)
        stats.update({'window': start + ' ~ ' + asof, 'coverage': cov,
                      'notes': []})
        if not cov['sufficient']:
            stats['notes'].append('真实配对样本 %d / 应有约 %d 个交易日，覆盖率 %.0f%%，'
                                  '不足以代表该窗口的基差分布'
                                  % (cov['have'], cov['expected'], cov['ratio'] * 100))
        if not stats['usable_as_percentile']:
            stats['notes'].append(stats['reason'])
        windows[w] = stats

    # ---------- 指定日的变化归因
    changes = {}
    for d in [x.strip() for x in args.dates.split(',') if x.strip()]:
        if d not in spot or spot[d] is None or d not in closes:
            changes[d] = {'error': '该日缺少现货或期货报价，不归因'}
            continue
        if mains.get(d) != main_c:
            changes[d] = {'error': '该日主力为 %s，与基准日 %s 不同；跨换月不可直接相减，'
                                   '请用固定合约口径或复权序列' % (mains.get(d), main_c)}
            continue
        dec = B.decompose(spot_now, spot[d], fut_now, closes[d][main_c])
        dec.update({'from': d, 'to': asof, 'contract': main_c,
                    'spot_from': spot[d], 'spot_to': spot_now,
                    'fut_from': closes[d][main_c], 'fut_to': fut_now})
        changes[d] = dec

    out = {
        'asof': asof,
        'definition': '基差 = 现货价格 - 期货价格；基差率 = 基差 / 现货 * 100',
        'spot_now': spot_now,
        'main_contract': main_c,
        'main_close': fut_now,
        'basis_now': B.basis(spot_now, fut_now),
        'basis_rate_now': B.basis_rate(spot_now, fut_now),
        'contracts': contracts,
        'rolls': rolls,
        'roll_summary': B.naive_splice_check(seq, rolls, spot),
        'series': [{'date': d, 'basis': v} for d, v in basis_series],
        'n_pairs': len(pairs),
        'first_pair': pairs[0] if pairs else None,
        'windows': windows,
        'changes': changes,
        'adjusted_tail': adj[-5:] if adj else [],
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('基差 %+0.0f 元/吨（基差率 %.2f%%）  现货 %.0f  主力 %s 收盘 %.0f'
          % (out['basis_now'], out['basis_rate_now'], spot_now, main_c, fut_now))
    print('真实配对样本 %d 个（%s ~ %s）' % (len(pairs), out['first_pair'], asof))
    for w, s in windows.items():
        tag = '可用' if s['usable_as_percentile'] and s['coverage']['sufficient'] else '不可用'
        print('  窗口 %-3s N=%-4d 分位=%s%%  [%s]' %
              (w, s['n'], ('%.0f' % s['pct']) if s['pct'] is not None else 'NA', tag))
        for n in s['notes']:
            print('       ! %s' % n)
    if rolls:
        print('换月 %d 次，累计跳空 %.0f 元/吨' % (len(rolls), out['roll_summary']['abs_gap_sum']))
    print('-> %s' % args.out)


if __name__ == '__main__':
    main()
