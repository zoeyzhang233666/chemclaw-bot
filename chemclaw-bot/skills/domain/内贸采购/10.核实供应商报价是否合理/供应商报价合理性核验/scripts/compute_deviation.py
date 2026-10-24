# -*- coding: utf-8 -*-
"""第 3 步单独跑：给定报价靶心与参考区间，算偏离。

用法（两种）：
  # A. 用 research.json（推荐，参考区间从 benchmark 里读）
  python scripts/compute_deviation.py --research examples/01-meg-huadong/research.json --out work/deviation.json

  # B. 手给数字
  python scripts/compute_deviation.py --quote 5900 --low 5580 --high 5665 --center 5635 --out work/dev.json
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--research', help='research.json，按 benchmark.interval_by_target 逐靶心计算')
    ap.add_argument('--quote', type=float, help='报价（元/吨）')
    ap.add_argument('--low', type=float)
    ap.add_argument('--high', type=float)
    ap.add_argument('--center', type=float)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    if a.research:
        # 复用 model.py 的完整计算，只输出偏离部分
        sys.path.insert(0, HERE)
        import model
        m = model.build(a.research)
        rows = []
        for t in m['targets']:
            if t['status'] == '可比':
                rows.append({k: t.get(k) for k in ('target', 'target_label', 'quote_value', 'low', 'high',
                                                   'center', 'dev_center', 'dev_center_pct', 'dev_low',
                                                   'dev_high', 'dev_low_pct', 'dev_high_pct',
                                                   'position_in_range', 'status')})
            else:
                rows.append({'target': t['target'], 'target_label': t['target_label'],
                             'quote_value': t['quote_value'], 'status': t['status'],
                             'reason': t.get('reason') or t.get('quote_gap')})
        common.dump_json({'source': a.research, 'targets': rows}, a.out)
        print('OK -> %s' % a.out)
        for r in rows:
            if r['status'] == '可比':
                print('  %-10s 报价 %s | 区间 %s–%s | 偏离 %s (%s)' % (
                    r['target_label'], common.fmt(r['quote_value']), common.fmt(r['low']), common.fmt(r['high']),
                    common.sg(r['dev_center']) if hasattr(common, 'sg') else r['dev_center'],
                    common.pct(r['dev_center_pct'])))
            else:
                print('  %-10s %s' % (r['target_label'], r['status']))
        return

    if a.quote is None or a.center is None:
        raise SystemExit('要么给 --research，要么同时给 --quote 与 --center')
    lo = a.low if a.low is not None else a.center
    hi = a.high if a.high is not None else a.center
    r = common.deviation(a.quote, {'center': a.center, 'low': lo, 'high': hi,
                                   'interval_type': 'point' if lo == hi else 'range'})
    common.dump_json(r, a.out)
    print('OK -> %s' % a.out)
    print('  偏离 %s 元/吨 (%s)' % (r['dev_center'], common.pct(r['dev_center_pct'])))
    if r.get('position_in_range') is not None:
        print('  区间内位置 %.1f%%' % r['position_in_range'])


if __name__ == '__main__':
    main()
