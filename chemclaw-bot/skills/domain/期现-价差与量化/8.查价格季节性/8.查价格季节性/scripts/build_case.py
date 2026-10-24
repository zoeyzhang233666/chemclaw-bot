# -*- coding: utf-8 -*-
"""build_case.py — 跑某个案例（现货或期货）的全部季节性统计，落盘 JSON + CSV。

用法
  python build_case.py --case methanol-eastchina-spot
  python build_case.py --all
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seasonality_core as sc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'out')

# 已知停市日（交易所/生意社不发布、不应计为"缺失"）：仅用于 weekday_gaps 标注
CN_HOLIDAYS = []
try:
    _h = os.path.join(DATA, 'cn_market_holidays.txt')
    if os.path.exists(_h):
        CN_HOLIDAYS = [x.strip() for x in open(_h, encoding='utf-8') if x.strip() and not x.startswith('#')]
except Exception:                                          # noqa: BLE001
    CN_HOLIDAYS = []


def load_case(cfg, case):
    path = os.path.join(DATA, case['price_csv'].replace('cases/', 'cases/'))
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    return rows


def run(case):
    rows = load_case(None, case)
    daily, dups = sc.load_daily([{'date': r['date'], 'price': r['price']} for r in rows])
    res = {}
    for freq in ('weekly', 'monthly'):
        r = sc.analyze(case, daily, freq)
        r['source_file'] = case['price_csv']
        r['audit'] = case.get('audit', {})
        r['requested_span_years'] = case.get('sample_years')
        r['exclude_years'] = case.get('exclude_years', [])
        r['duplicates'] = dups
        r['weekday_gaps'] = sc.weekday_gaps(daily, CN_HOLIDAYS)
        res[freq] = r
    # 组合频率无关的审计块
    res['meta'] = dict(
        case_id=case['id'], title=case['title'], product=case['product'],
        caliber=dict(requested=case['caliber_requested'], obtained=case['caliber_obtained'],
                     downgraded=bool(case.get('caliber_downgraded')),
                     note=case.get('downgrade_note'), unit=case['unit'], tax=case['tax']),
        current_year=case['current_year'], requested_years=case.get('sample_years'),
        n_days=len(daily), first=res['weekly']['first_date'], last=res['weekly']['last_date'],
        duplicates=dups,
    )
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', default='')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()
    cfg = json.load(open(os.path.join(DATA, 'config.json'), encoding='utf-8'))
    os.makedirs(OUT, exist_ok=True)
    cases = cfg['cases']
    if args.case:
        cases = [c for c in cases if c['id'] == args.case]
    for case in cases:
        res = run(case)
        dst = os.path.join(OUT, '%s.json' % case['id'])
        json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
        w = res['weekly']
        print('=' * 78)
        print(case['title'], '| 口径:', case['caliber_obtained'])
        print('样本:', w['first_date'], '->', w['last_date'], '| 自然日报价点数:', w['n_days'])
        print('覆盖年份:', [x['year'] for x in w['years']])
        for f in ('weekly', 'monthly'):
            r = res[f]
            usable = [s for s in r['stats'] if s['n_sufficient']]
            print('--%s: 位置数=%d 可用位置=%d min_years=%d' % (f, len(r['stats']), len(usable), r['min_years']))
            print('   稳定性:', r['stability'])
            print('   异常分级:', {x['year']: x['grade'] for x in r['anomaly']['yearly']})
            cur = [x for x in r['current'] if x['current'] is not None]
            if cur:
                last = cur[-1]
                print('   当前年最后一个位置 %s: %s (历史 %d 年, 分位 %.0f%%, 排名 %s/%d)'
                      % (last['label'], last['current'], last['n_hist'],
                         (last['pctile_of_current'] or 0) * 100, last['rank'], last['n_hist']))
        print('-> ', dst)


if __name__ == '__main__':
    main()
