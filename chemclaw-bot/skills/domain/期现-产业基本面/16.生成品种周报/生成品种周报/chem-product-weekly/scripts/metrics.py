# -*- coding: utf-8 -*-
"""周度指标计算模板：周变动 / 月差 / 基差 / 主力切换 / 历史同期。按品种改 CONTRACTS、PAIRS、窗口。"""
import json, os, sys
from statistics import mean
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'raw', '_src')
OUT = os.path.join(ROOT, 'data', 'metrics.json')

# ====== 只改这里 ======
CONTRACTS = ['MA2611', 'MA2612', 'MA2701', 'MA2703', 'MA2705']
PAIRS = [('MA2611', 'MA2612'), ('MA2611', 'MA2701'), ('MA2701', 'MA2705'), ('MA2611', 'MA2705')]
WEEK = ('2026-10-12', '2026-10-16')        # 报告周（首末交易日）
PREV = ('2026-10-08', '2026-10-09')        # 上一周（用于基期）
LASTYEAR = ('2025-10-13', '2025-10-17')
YEAR_MAP = {'MA2611': 'MA2511', 'MA2612': 'MA2512', 'MA2701': 'MA2601', 'MA2703': 'MA2603', 'MA2705': 'MA2605'}
# =====================


def load(sym):
    p = os.path.join(SRC, 'fut_%s.json' % sym)
    if not os.path.exists(p):
        return {}
    return {r['d']: r for r in json.load(open(p, encoding='utf-8'))['rows']}


def pct(a, b):
    return None if not a else (b - a) / a * 100


def main():
    fut = {c: load(c) for c in CONTRACTS}
    days = sorted({d for c in fut for d in fut[c] if WEEK[0] <= d <= WEEK[1]})
    if not days:
        raise SystemExit('报告周内没有行情数据，检查窗口与合约代码')
    out = {'window': {'start': WEEK[0], 'end': WEEK[1], 'days': days}, 'futures': {}}
    for c, s in fut.items():
        wd = [d for d in days if d in s]
        if not wd:
            continue
        prev = next((s[d]['c'] for d in sorted(s, reverse=True) if PREV[0] <= d <= PREV[1]), None)
        closes = [s[d]['c'] for d in wd]
        out['futures'][c] = {
            'prev_close': prev, 'week_avg': round(mean(closes), 2),
            'week_high': max(s[d]['h'] for d in wd), 'week_low': min(s[d]['l'] for d in wd),
            'week_close': s[wd[-1]]['c'], 'chg': None if prev is None else s[wd[-1]]['c'] - prev,
            'chg_pct': pct(prev, s[wd[-1]]['c']),
            'oi_start': s[wd[0]]['oi'], 'oi_end': s[wd[-1]]['oi'],
            'oi_chg': s[wd[-1]]['oi'] - s[wd[0]]['oi'], 'vol_total': sum(s[d]['v'] for d in wd),
            'daily': {d: s[d]['c'] for d in wd}, 'daily_oi': {d: s[d]['oi'] for d in wd},
        }
    # 主力切换检测
    dom = []
    for d in days:
        cand = [(fut[c][d]['oi'], c) for c in CONTRACTS if d in fut[c]]
        if cand:
            oi, c = max(cand)
            dom.append({'date': d, 'contract': c, 'oi': oi})
    out['dominant'] = dom
    sw = [x for i, x in enumerate(dom) if i and x['contract'] != dom[i - 1]['contract']]
    out['roll_switch'] = sw
    out['dominant_note'] = ('全周主力为 %s' % dom[0]['contract']) if not sw else ('窗口内主力切换：' +
                            ','.join('%s->%s@%s' % (dom[i - 1]['contract'], x['contract'], x['date']) for i, x in enumerate(dom) if i and x['contract'] != dom[i - 1]['contract']))
    # 月差
    out['spread'] = []
    for d in days:
        row = {'date': d}
        for a, b in PAIRS:
            if d in fut.get(a, {}) and d in fut.get(b, {}):
                row['%s-%s' % (a, b)] = fut[a][d]['c'] - fut[b][d]['c']
        out['spread'].append(row)
    # 历史同期
    out['lastyear'] = {}
    for c in CONTRACTS:
        ly = load(YEAR_MAP.get(c, ''))
        wd = [d for d in sorted(ly) if LASTYEAR[0] <= d <= LASTYEAR[1]]
        if not wd:
            continue
        out['lastyear'][c] = {'ly_contract': YEAR_MAP[c], 'ly_avg': round(mean(ly[d]['c'] for d in wd), 2),
                              'ly_close': ly[wd[-1]]['c']}
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('WINDOW', days)
    for c, v in out['futures'].items():
        print('%-7s avg %-8s close %-7s prev %-7s chg %-7s %-7s OI %s->%s' % (
            c, v['week_avg'], v['week_close'], v['prev_close'], v['chg'],
            None if v['chg_pct'] is None else round(v['chg_pct'], 2), v['oi_start'], v['oi_end']))
    print(out['dominant_note'])
    print('->', OUT)


if __name__ == '__main__':
    main()
