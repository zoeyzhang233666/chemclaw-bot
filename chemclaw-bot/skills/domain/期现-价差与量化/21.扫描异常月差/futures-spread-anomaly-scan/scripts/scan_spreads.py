# -*- coding: utf-8 -*-
"""scan_spreads —— 异常月差扫描主程序

    python scripts/scan_spreads.py --raw data/raw --as-of 2026-10-20 \
        --products MA SA PP TA --unit-near 1 --unit-far 3 --min-n 3 \
        --out build/scan_result.json

产出
----
1. 期限结构（每品种当日全部挂牌合约）
2. 每对合约组合的：当前月差、历史分位、近1月变化、Z、极端评级、样本清单
3. 按极端程度排序的榜单
4. 明确标出：样本不足 / 不可比 / 数据缺失
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import spreadlib as S
import rule_matcher as RM


def months_from_now(y, m, as_of):
    return (y - as_of.year) * 12 + (m - as_of.month)


def one_month_ago_date(dates, as_of):
    """取 as_of 往前约 1 个自然月、且真实存在的交易日。"""
    target = as_of - dt.timedelta(days=30)
    cands = [x for x in dates if x <= target]
    return max(cands) if cands else None


def scan(rawdir, as_of, products, rules, unit_near=1, unit_far=3, min_n=3,
         min_n_scan=30, thresholds=None, min_oi=500, max_gap=6, basis='settle',
         include_edges=None):
    th = dict(S.DEFAULT_THRESHOLDS)
    th['min_n'] = min_n
    th['min_n_scan'] = min_n_scan
    if thresholds:
        th.update(thresholds)

    cons = S.load_contracts(rawdir)
    result = {'as_of': as_of.isoformat(), 'basis': basis,
              'settings': {'products': products, 'unit_near': unit_near, 'unit_far': unit_far,
                           'unit_str': 'qoq' if (unit_near, unit_far) == (1, 3) else 'cal',
                           'min_n': min_n, 'thresholds': th, 'min_oi': min_oi,
                           'max_gap': max_gap},
              'products': {}, 'ranking': [], 'excluded': [], 'notes': []}

    for p in products:
        if p not in cons:
            result['products'][p] = {'error': 'no data'}
            continue
        cs = cons[p]
        rule = rules[p]
        rows = S.term_structure(cs, as_of)
        # 只保留真正有流动性的前 N 个交割月进入曲线与配对
        ts = [{'symbol': r['symbol'], 'y': r['y'], 'm': r['m'],
               'settle': r['settle'], 'close': r['close'], 'volume': r['volume'],
               'oi': r['oi'], 'is_main': r.get('is_main', False),
               'months_out': months_from_now(r['y'], r['m'], as_of)} for r in rows]

        # 枚举组合：只用"近月在前"的有序列（近月的 months_out 必须更小）
        # 扫描口径排除最前 2 个交割月：它们临近交割，报价受单边交割逻辑扭曲，
        # 且历史上不可比（历史样本需同剩余期限，而近月剩余期限已 <2 周）。
        pairs = []
        pool = ts[2:] if len(ts) > 4 else ts
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                a, b = pool[i], pool[j]
                if a['months_out'] + unit_near == b['months_out'] + unit_far:
                    pairs.append((a, b))
        # 固定主力邻档组合（主力 − 主力+unit_far 档），保证榜单锚定在真正有流动性的边上
        mi = next((k for k, r in enumerate(ts) if r.get('is_main')), None)
        if mi is not None and mi + unit_far < len(ts):
            fixed = (ts[mi], ts[mi + unit_far])
            if fixed not in pairs:
                pairs.insert(0, fixed)
        result['notes'].append(
            f'{p}: 扫描范围为第3个及以后交割月（{"、".join(x["symbol"] for x in pool[:1])} 起），'
            '最前两个交割月因临近交割不纳入分位扫描')
        if include_edges:
            seen = {(a['symbol'], b['symbol']) for a, b in pairs}
            for spec in include_edges:
                n, f = spec.split('-')
                na = next((x for x in ts if x['symbol'] == n), None)
                fa = next((x for x in ts if x['symbol'] == f), None)
                if na and fa and (n, f) not in seen:
                    pairs.append((na, fa))

        out_pairs = []
        for a, b in pairs:
            near_sym, far_sym = a['symbol'], b['symbol']
            ok, reasons, meta = RM.check_pair(
                rules, near_sym, far_sym, as_of, a['oi'], b['oi'],
                min_oi=min_oi, max_gap=max_gap)
            rec = {
                'product': p, 'near': near_sym, 'far': far_sym,
                'label': f'{near_sym}-{far_sym}',
                'gap_months': meta.get('gap_months'),
                'near_settle': a['settle'], 'far_settle': b['settle'],
                'near_close': a['close'], 'far_close': b['close'],
                'near_oi': a['oi'], 'far_oi': b['oi'],
                'near_months_out': a['months_out'], 'far_months_out': b['months_out'],
                'weeks_to_near': meta.get('weeks_to_near'),
                'is_main_edge': meta.get('is_main_edge'),
                'tradable': ok, 'block_reasons': [RM.REASONS[x] for x in reasons],
            }
            # 计算月差
            nc, fc = cs.get(near_sym), cs.get(far_sym)
            if not nc or not fc:
                rec.update({'computable': False, 'note': '合约日线缺失'})
                out_pairs.append(rec)
                continue
            seq = S.compute_pair_series(nc, fc, basis=basis)
            cur = S.series_on(seq, as_of)
            if cur is None:
                rec.update({'computable': False, 'note': '当日无双边有效报价'})
                out_pairs.append(rec)
                continue
            spread = round((a['settle'] if basis == 'settle' else a['close'])
                           - (b['settle'] if basis == 'settle' else b['close']), 2)
            rec.update({'computable': True, 'spread': spread})

            # 近1月变化
            oma = one_month_ago_date([r['date'] for r in seq], as_of)
            if oma:
                ch = S.series_on(seq, oma)
                rec['spread_1m_ago'] = ch['spread']
                rec['date_1m_ago'] = oma.isoformat()
                rec['change_1m'] = round(spread - ch['spread'], 2)
                rec['change_1m_pct'] = (round((spread - ch['spread']) / abs(ch['spread']) * 100, 1)
                                        if ch['spread'] else None)
            else:
                rec['spread_1m_ago'] = None
                rec['change_1m'] = None

            # 可比历史样本
            samp = S.comparable_sample(cs, p, near_sym, far_sym, as_of)
            vals = [x['spread'] for x in samp]
            n = len(vals)
            rec['n_history'] = n
            rec['history_years'] = [x['year'] for x in samp]
            rec['history'] = samp
            rec['as_of'] = as_of.isoformat()
            rec['series_30d'] = [
                {'date': r['date'].isoformat(), 'spread': r['spread']}
                for r in seq if r['date'] >= as_of - dt.timedelta(days=45)]

            if n >= min_n:
                pct = S.percentile_rank(spread, vals)
                z = S.zscore(spread, vals)
                grade, direction = S.classify(pct, z, n, min_n, th)
                rec.update({
                    'percentile': round(pct, 1) if pct is not None else None,
                    'z': round(z, 2) if z is not None else None,
                    'mean_hist': round(sum(vals) / n, 1),
                    'q05': S.quantile(vals, 0.05), 'q25': S.quantile(vals, 0.25),
                    'q50': S.quantile(vals, 0.50), 'q75': S.quantile(vals, 0.75),
                    'q95': S.quantile(vals, 0.95),
                    'min_hist': min(vals), 'max_hist': max(vals),
                    'grade': grade, 'direction': direction,
                    'sample_status': '不足(仅%d年)' % n if n < min_n_scan else '可比(%d年)' % n,
                    'extremeness': round(abs(pct - 50) * 2, 1),   # 0=中位 100=极限
                })
            else:
                rec.update({'percentile': None, 'z': None, 'grade': '样本不足',
                            'direction': 'insufficient', 'sample_status': f'样本不足(N={n}<{min_n})',
                            'extremeness': None})
            out_pairs.append(rec)

        # 曲线形态描述
        shape = describe_shape(ts)
        result['products'][p] = {
            'name_cn': rule['name_cn'], 'exchange': rule['exchange'],
            'exchange_cn': rule['exchange_cn'],
            'rule': {k: rule[k] for k in ('listed_months', 'contract_unit_t', 'tick',
                                          'min_margin_pct', 'price_limit_pct',
                                          'last_trading_day_rule', 'main_months')},
            'term_structure': ts, 'shape': shape, 'pairs': out_pairs,
        }

    # 汇总榜单
    flat = []
    for p, blk in result['products'].items():
        for rec in blk.get('pairs', []):
            if rec.get('percentile') is None:
                continue
            flat.append(rec)
    flat.sort(key=lambda r: (-(r['extremeness'] or 0), r['product']))
    result['ranking'] = flat
    return result


def describe_shape(ts):
    """期限结构形态：用最小二乘拟合"价格 ~ 距今天数"的斜率判定，而非首尾相减。

    首尾相减会因近月逼仓/单点异常而误判；OLS 斜率是整条曲线的平均倾斜度。
    """
    if len(ts) < 3:
        return {'type': '未知', 'note': '挂牌合约不足'}
    pts = [(r['months_out'], (r['settle'] if r['settle'] else r['close']))
           for r in ts if (r['settle'] or r['close'])]
    if len(pts) < 3:
        return {'type': '未知', 'note': '有效价格不足'}
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    slope = sxy / sxx if sxx else 0.0
    # 相关性（曲线单调性）
    syy = sum((p[1] - my) ** 2 for p in pts)
    r = sxy / ((sxx * syy) ** 0.5) if sxx and syy else 0.0
    kind = ('正向市场(contango)' if slope < -3 else
            ('反向市场(backwardation)' if slope > 3 else '平坦'))
    # 找最大单步跳变（相邻交割月价差）
    steps = []
    for k in range(1, len(pts)):
        steps.append({'from_m': pts[k - 1][0], 'to_m': pts[k][0],
                      'near_sym': ts[k - 1]['symbol'], 'far_sym': ts[k]['symbol'],
                      'diff': round(pts[k][1] - pts[k - 1][1], 1)})
    big = max(steps, key=lambda x: abs(x['diff'])) if steps else None
    return {'type': kind, 'slope_per_month': round(slope, 2),
            'monotonicity_r': round(r, 3), 'biggest_step': big, 'points': pts}


def main(argv=None):
    ap = argparse.ArgumentParser(description='扫描异常月差')
    ap.add_argument('--raw', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'data','raw'))
    ap.add_argument('--rules', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'data','contract_rules.json'))
    ap.add_argument('--as-of', default=None)
    ap.add_argument('--products', nargs='+', default=['MA', 'SA', 'PP', 'TA'])
    ap.add_argument('--unit-near', type=int, default=1)
    ap.add_argument('--unit-far', type=int, default=3)
    ap.add_argument('--min-n', type=int, default=3)
    ap.add_argument('--min-n-scan', type=int, default=30)
    ap.add_argument('--min-oi', type=float, default=500)
    ap.add_argument('--max-gap', type=int, default=6)
    ap.add_argument('--basis', default='settle', choices=['settle', 'close'])
    ap.add_argument('--edges', nargs='*', default=None, help='额外强制纳入的组合，如 SA2611-SA2701')
    ap.add_argument('--out', default='build/scan_result.json')
    a = ap.parse_args(argv)

    as_of = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    rules = RM.load_rules(a.rules)
    res = scan(a.raw, as_of, a.products, rules, a.unit_near, a.unit_far,
               a.min_n, a.min_n_scan, min_oi=a.min_oi, max_gap=a.max_gap,
               basis=a.basis, include_edges=a.edges)
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)

    print(f"[as_of {res['as_of']}] 口径 {res['settings']['unit_str']}  "
          f"近月={a.unit_near} 远月={a.unit_far}")
    for p, blk in res['products'].items():
        if 'error' in blk:
            print(f'  {p}: {blk["error"]}')
            continue
        print(f"  {p} {blk['name_cn']}  形态={blk['shape']['type']}  挂牌{len(blk['term_structure'])}个")
        for rec in blk['pairs']:
            if not rec.get('computable'):
                continue
            print(f"    {rec['label']:16s} 月差={rec['spread']:>8.0f}  "
                  f"分位={str(rec.get('percentile')):>5s}  Z={str(rec.get('z')):>6s}  "
                  f"近1月={str(rec.get('change_1m')):>7s}  N={rec.get('n_history')}  "
                  f"{rec.get('grade')}  {'✓可交易' if rec['tradable'] else rec['block_reasons']}")
    print(f"\n榜单前 10：")
    for i, rec in enumerate(res['ranking'][:10], 1):
        print(f"  {i:2d}. {rec['product']} {rec['label']:16s} 极端度={rec['extremeness']:5.1f} "
              f"分位={rec['percentile']:5.1f} {rec['grade']}  N={rec['n_history']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
