# -*- coding: utf-8 -*-
"""第 4 步单独跑：从序列文件算历史分位（可指定窗口与比较值）。

用法：
  python scripts/compute_percentile.py examples/01-meg-huadong/series/ppi_benchmark_1y.json \
         --value 5900 --asof 2026-10-19 --window 1y --out work/pct.json

  # 不知道比较值时，先打印该序列的各分位阈值，用来人工比对
  python scripts/compute_percentile.py <series.json> --asof 2026-10-19 --window 3y --levels
"""
import argparse
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

WINDOW_DAYS = {'1m': 30, '3m': 90, '6m': 180, '1y': 365, '2y': 730, '3y': 1095}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('series')
    ap.add_argument('--value', type=float, help='被比较的报价（元/吨，须与该序列同税费口径）')
    ap.add_argument('--asof', required=True, help='窗口终点 YYYY-MM-DD')
    ap.add_argument('--window', default='1y', choices=sorted(WINDOW_DAYS))
    ap.add_argument('--min-points', type=int, default=8, help='最少有效样本数（默认 8）')
    ap.add_argument('--levels', action='store_true', help='打印 p10/p25/p50/p75/p90 阈值')
    ap.add_argument('--out')
    a = ap.parse_args()

    s = common.load_json(a.series)
    pts = s.get('points') or []
    meta = s.get('meta') or {}
    if not pts:
        raise SystemExit('序列 %s 没有 points' % a.series)
    # 期货序列可能用 c（收盘）
    pts = [{'d': p['d'], 'v': p.get('v', p.get('c'))} for p in pts if p.get('d')]
    pts.sort(key=lambda x: x['d'])

    days = WINDOW_DAYS[a.window]
    st = common.window_stats(pts, days, a.asof, a.min_points)
    print('序列：%s（%s，%s，%s）' % (meta.get('name', a.series), meta.get('freq', ''), meta.get('tax', ''), meta.get('spec', '')))
    result = {'series': os.path.basename(a.series), 'meta': meta, 'window': a.window,
              'asof': a.asof, 'days': days}
    if not st.get('ok'):
        print('  缺口：%s' % st.get('gap'))
        result.update({'ok': False, 'gap': st.get('gap'), 'n': st.get('n')})
    else:
        print('  窗口 %s ~ %s，n=%d，区间 %.2f – %.2f，中位 %.2f' % (
            st['start'], st['end'], st['n'], st['low'], st['high'], st['center']))
        vals = [p['v'] for p in pts if st['start'] <= p['d'] <= a.asof]
        result.update({'ok': True, 'n': st['n'], 'start': st['start'], 'end': st['end'],
                       'low': st['low'], 'high': st['high'], 'median': st['center']})
        if a.levels:
            sv = sorted(vals)
            lv = {}
            for q in (10, 25, 50, 75, 90):
                idx = min(len(sv) - 1, int(round(q / 100.0 * (len(sv) - 1))))
                lv['p%d' % q] = round(sv[idx], 2)
            print('  分位阈值：' + '  '.join('%s=%.2f' % (k, v) for k, v in lv.items()))
            result['levels'] = lv
        if a.value is not None:
            pc, n = common.percentile_of(vals, a.value)
            print('  %.2f 的分位 = %.1f%%（n=%d）' % (a.value, pc, n))
            result.update({'value': a.value, 'percentile': pc})
    result['method'] = 'P = (#<X + 0.5×#=X) / n × 100%'
    if a.out:
        common.dump_json(result, a.out)
        print('OK -> %s' % a.out)


if __name__ == '__main__':
    main()
