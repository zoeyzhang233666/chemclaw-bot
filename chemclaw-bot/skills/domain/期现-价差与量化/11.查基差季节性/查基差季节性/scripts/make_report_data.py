# -*- coding: utf-8 -*-
"""
生成 HTML 报告所需的嵌入式数据包 (report_data.json)
把 out/ 下所有 CSV 汇总成一个 JSON，供交互式 HTML 直接加载（无外部依赖、可离线打开）。
"""
import csv, json, os, sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'out')


def rcsv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        if v is None or str(v).strip() == '':
            return None
        return float(str(v).replace(',', ''))
    except Exception:
        return v


def main():
    pack = {}
    # 近月每日基差
    near = rcsv(os.path.join(OUT, 'seas_near', 'daily_basis.csv'))
    pack['daily'] = [{'d': r['date'], 's': num(r['spot']), 'f': num(r['fut']),
                      'b': num(r['basis']), 'c': r.get('contract', '')} for r in near]
    main_d = rcsv(os.path.join(OUT, 'seas_main', 'daily_basis.csv'))
    pack['daily_main'] = [{'d': r['date'], 'b': num(r['basis'])} for r in main_d]

    pack['weekly'] = [{'y': int(r['iso_year']), 'w': int(r['iso_week']), 'd': r['date'],
                       'b': num(r['basis'])} for r in rcsv(os.path.join(OUT, 'seas_near', 'weekly_basis.csv'))]
    pack['monthly'] = [{'y': int(r['year']), 'm': int(r['month']), 'd': r['date'],
                        'b': num(r['basis_month_end']), 'bm': num(r['basis_mean'])}
                       for r in rcsv(os.path.join(OUT, 'seas_near', 'monthly_basis.csv'))]

    def seas(name):
        return [{k: (num(v) if k not in ('years',) else v) for k, v in r.items()}
                for r in rcsv(os.path.join(OUT, 'seas_near', name))]
    pack['seasonal_month'] = seas('seasonal_month.csv')
    pack['seasonal_week'] = seas('seasonal_week.csv')
    pack['seasonal_month_main'] = [{k: (num(v) if k != 'years' else v) for k, v in r.items()}
                                   for r in rcsv(os.path.join(OUT, 'seas_main', 'seasonal_month.csv'))]

    with open(os.path.join(OUT, 'seas_near', 'meta_near.json'), encoding='utf-8') as f:
        pack['meta_near'] = json.load(f)
    with open(os.path.join(OUT, 'seas_main', 'meta_main.json'), encoding='utf-8') as f:
        pack['meta_main'] = json.load(f)

    pack['rolls_near'] = rcsv(os.path.join(OUT, 'roll_log_near.csv'))
    pack['rolls_main'] = rcsv(os.path.join(OUT, 'roll_log_main.csv'))
    pack['roll_sameday'] = rcsv(os.path.join(OUT, 'roll_sameday_spread.csv'))
    pack['roll_basis_effect'] = rcsv(os.path.join(OUT, 'roll_basis_effect_near.csv'))
    pack['stability'] = rcsv(os.path.join(OUT, 'supp_stability_near.csv'))
    pack['fixed_summary'] = rcsv(os.path.join(OUT, 'supp_fixed_month_summary.csv'))
    pack['calendar'] = rcsv(os.path.join(OUT, 'contract_calendar.csv'))
    pack['change_compare'] = rcsv(os.path.join(OUT, 'supp_daily_change_compare.csv'))
    pack['illiquid'] = rcsv(os.path.join(OUT, 'anomaly_illiquid_skipped.csv'))
    pack['spot_src'] = rcsv(os.path.join(OUT, 'spot_100ppi_meitan_benchmark.csv'))[:3]

    # 固定交割月逐年曲线
    fixed = {}
    for mm in ['01', '05', '09']:
        for f in sorted(os.listdir(OUT)):
            if f.startswith('fixed_%s_' % mm) and f.endswith('.csv'):
                fixed.setdefault(mm, []).append({
                    'contract': f[9:-4],
                    'series': [{'d': r['date'], 'b': num(r['basis'])} for r in rcsv(os.path.join(OUT, f))]})
    pack['fixed'] = fixed

    dst = os.path.join(OUT, 'report_data.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(pack, f, ensure_ascii=False, separators=(',', ':'))
    print('[OK]', dst, os.path.getsize(dst) // 1024, 'KB')
    print('   daily=%d weekly=%d monthly=%d rolls=%d fixed_groups=%s'
          % (len(pack['daily']), len(pack['weekly']), len(pack['monthly']),
             len(pack['rolls_near']), {k: len(v) for k, v in fixed.items()}))


if __name__ == '__main__':
    main()
