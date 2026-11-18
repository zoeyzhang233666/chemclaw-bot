# -*- coding: utf-8 -*-
"""
batch_scan.py —— 批量扫描：一次跑多个品种 / 多个窗口 / 多种运费情形

三种典型用法：
  1) 多品种一次扫描，各自出排行榜，再合并成一张跨品种异常榜：
       python scripts/batch_scan.py --products soda,methanol,pvc
  2) 同一品种多窗口对照（3/6/12 月），检查「结论是否依赖窗口选择」：
       python scripts/batch_scan.py --products soda --windows 3,6,12
  3) 运费敏感性：在用户已提供运费的基础上，按 ±20% 做情形对照（仅作敏感性，
     不改变「运费必须由用户提供」的前提，也不会输出套利结论）：
       python scripts/batch_scan.py --products soda --freight freight.json --sensitivity 0.2

输出：outputs/batch_scan.json + outputs/batch_scan.csv + 每个组合的首选窗口说明。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'scripts'))

from scan import ScanConfig, run_scan  # noqa: E402


def _scale(freight: dict, k: float) -> dict:
    out = {}
    for pk, dirs in (freight or {}).items():
        out[pk] = {}
        for d, v in dirs.items():
            v2 = dict(v)
            if v2.get('fee') is not None:
                v2['fee'] = round(float(v2['fee']) * k, 4)
            out[pk][d] = v2
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--products', default='soda,methanol')
    ap.add_argument('--windows', default='12', help='逗号分隔，如 3,6,12')
    ap.add_argument('--regions', default=None)
    ap.add_argument('--min-samples', type=int, default=20)
    ap.add_argument('--anomaly-pct', type=float, default=0.95)
    ap.add_argument('--freight', default=None)
    ap.add_argument('--sensitivity', type=float, default=0.0,
                    help='运费敏感性 amplitude，如 0.2 表示 ±20%%')
    a = ap.parse_args()

    products = [p for p in a.products.split(',') if p]
    windows = [int(w) for w in a.windows.split(',') if w]
    regions = [r for r in a.regions.split(',')] if a.regions else None
    freight = json.load(open(a.freight, encoding='utf-8')) if a.freight else {}

    out_dir = os.path.join(BASE, 'outputs')
    os.makedirs(out_dir, exist_ok=True)

    rows, runs = [], []
    for w in windows:
        for pk in products:
            for label, fr, enabled in ([('裸价差', {}, False)] +
                                       ([('含运费', freight, True)] if freight else [])):
                if enabled and a.sensitivity:
                    ks = [(1 - a.sensitivity, 'low'), (1.0, 'base'), (1 + a.sensitivity, 'high')]
                else:
                    ks = [(1.0, label)]
                for k, tag in ks:
                    cfg = ScanConfig(products=[pk], regions=regions, window_months=w,
                                     min_samples=a.min_samples, anomaly_grade_pct=a.anomaly_pct,
                                     freight=_scale(fr, k) if enabled else {}, freight_enabled=enabled)
                    res = run_scan(cfg)
                    runs.append({'product': pk, 'window': w, 'case': tag, 'k': k,
                                 'summary': res['summary']})
                    for c in res['combinations']:
                        rows.append({
                            '品种': pk, '窗口(月)': w, '情形': tag, '运费系数': k,
                            '方向': '%s -> %s' % (c['base_region'], c['quote_region']),
                            '当前裸价差': c['spread_now'], '历史分位': c['pct'],
                            '异常度': c['anomaly'], '判定': c['grade'],
                            '有效样本': c['n_obs'],
                            '扣除运费后': (c.get('freight') or {}).get('net_ab'),
                            '运费状态': ((c.get('freight') or {}).get('fee_ab') or {}).get('status'),
                            '规格档': c.get('spec_tier'),
                        })
            print('  完成 %s / %d 月' % (pk, w), flush=True)

    # 窗口一致性：同一组合同一情形在不同窗口下的判定是否稳定
    by_key = {}
    for r in rows:
        if r['情形'] not in ('裸价差', 'base'):
            continue
        k = (r['品种'], r['情形'], r['方向'])
        by_key.setdefault(k, []).append((r['窗口(月)'], r['判定'], r['历史分位']))
    consistency = []
    for (pk, case, pair), lst in by_key.items():
        lst.sort()
        grades = {g for _, g, _ in lst}
        consistency.append({
            '产品': pk, '情形': case, '方向': pair,
            '各窗口判定': ' | '.join('%d月:%s(%.0f%%)' % (w, g, (p or 0) * 100) for w, g, p in lst),
            '判定稳定': len(grades) == 1,
            '注意': '' if len(grades) == 1 else '不同历史窗口下判定不同 —— 结论依赖窗口，交付时必须同时披露',
        })

    json.dump({'runs': runs, 'rows': rows, 'consistency': consistency},
              open(os.path.join(out_dir, 'batch_scan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    if rows:
        with open(os.path.join(out_dir, 'batch_scan.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    unstable = [c for c in consistency if not c['判定稳定']]
    print('\n组合 %d 条，其中 %d 条的判定在不同窗口下不一致：' % (len(consistency), len(unstable)))
    for c in unstable[:10]:
        print('  %-8s %-24s %s' % (c['产品'], c['方向'], c['各窗口判定']))
    print('\n输出：outputs/batch_scan.json / outputs/batch_scan.csv')


if __name__ == '__main__':
    main()
