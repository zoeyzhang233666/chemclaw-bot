# -*- coding: utf-8 -*-
"""
补充分析：
  1) 固定交割月份（01/05/09）逐合约、逐年的基差序列（同月份不同年份单列，不混样本）
  2) 月度季节性 vs 全年自然波动的稳定性检验：
     - 季节性强度 SS_share
     - 每年"同月基差符号"一致性（走强/贴水持续时间）
     - 月度均值的跨年离散度（CV）
  3) 换月伪跳空量化：用"同日两合约价差"替代跨日跳空，避免把换月错当基差变化
输出到 out/supp_*.csv、out/fixed_*_year.csv
"""
import csv, glob, json, os, statistics, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, 'raw')
OUT = os.path.join(ROOT, 'out')


def rcsv(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def wcsv(name, rows, cols=None):
    if not rows:
        return
    cols = cols or list(rows[0].keys())
    with open(os.path.join(OUT, name), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, '') for c in cols])
    print('[OUT]', name, len(rows))


def pctile(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (pos - lo) * (s[hi] - s[lo])


def main():
    # ---------- 1) 固定交割月：同月份不同年份单列 ----------
    fixed_report = []
    for mm in ['01', '05', '09']:
        p = os.path.join(OUT, 'basis_fixed_%s.csv' % mm) if os.path.exists(
            os.path.join(OUT, 'basis_fixed_%s.csv' % mm)) else None
        # map_fixed 里是映射，需要再与现货配对生成基差
        mp = os.path.join(OUT, 'map_fixed_%s.csv' % mm)
        if not os.path.exists(mp):
            continue
        spot = {r['date']: float(r['price']) for r in rcsv(os.path.join(OUT, 'spot_100ppi_meitan_benchmark.csv'))}
        rows = rcsv(mp)
        byc = defaultdict(list)
        for r in rows:
            d = r['date']
            if d in spot:
                byc[r['contract']].append({'date': d, 'contract': r['contract'],
                                           'spot': spot[d], 'fut': float(r['fut_price']),
                                           'basis': round(spot[d] - float(r['fut_price']), 2)})
        for c, seq in sorted(byc.items()):
            seq.sort(key=lambda x: x['date'])
            wcsv('fixed_%s_%s.csv' % (mm, c), seq, ['date', 'contract', 'spot', 'fut', 'basis'])
            b = [x['basis'] for x in seq]
            fixed_report.append({'交割月': mm, '合约': c, '样本日数': len(b),
                                 '起始': seq[0]['date'], '结束': seq[-1]['date'],
                                 '基差均值': round(statistics.fmean(b), 2),
                                 '基差中位': round(statistics.median(b), 2),
                                 '最小': round(min(b), 2), '最大': round(max(b), 2),
                                 '说明': '同一固定交割月不同年份单列，不与连续合约混样'})
    wcsv('supp_fixed_month_summary.csv', fixed_report)

    # ---------- 2) 稳定性检验 ----------
    for tag in ['near', 'main']:
        base = os.path.join(OUT, 'seas_%s' % tag)
        mon = rcsv(os.path.join(base, 'monthly_basis.csv'))
        bym = defaultdict(list)
        for r in mon:
            bym[int(r['month'])].append(float(r['basis_month_end']))
        stab = []
        for m in range(1, 13):
            v = bym.get(m, [])
            if not v:
                continue
            mu = statistics.fmean(v)
            sd = statistics.pstdev(v) if len(v) > 1 else 0
            pos = sum(1 for x in v if x > 0) / len(v)
            stab.append({'口径': tag, '月份': m, '样本年数': len(v),
                         '均值': round(mu, 2), '标准差': round(sd, 2),
                         '变异系数': round(sd / abs(mu), 3) if mu else None,
                         '升水年份占比': round(pos, 2),
                         '最小值': round(min(v), 2), '最大值': round(max(v), 2),
                         '分位极差(p90-p10)': round(pctile(v, 90) - pctile(v, 10), 2) if len(v) > 2 else None})
        wcsv('supp_stability_%s.csv' % tag, stab)

    # ---------- 3) 换月伪跳空量化 ----------
    sd = rcsv(os.path.join(OUT, 'roll_sameday_spread.csv'))
    if sd:
        diffs = [abs(float(r['两合约同日价差(元/吨)'])) for r in sd]
        print('[INFO] 同日两合约价差 |d|: n=%d 均值 %.1f 中位 %.1f p90 %.1f 最大 %.1f'
              % (len(diffs), statistics.fmean(diffs), statistics.median(diffs),
                 pctile(diffs, 90), max(diffs)))
        summ = [{'指标': '换月样本数', '值': len(diffs)},
                {'指标': '同日两合约价差绝对值均值(元/吨)', '值': round(statistics.fmean(diffs), 2)},
                {'指标': '同日两合约价差绝对值中位(元/吨)', '值': round(statistics.median(diffs), 2)},
                {'指标': '同日两合约价差绝对值p90(元/吨)', '值': round(pctile(diffs, 90), 2)},
                {'指标': '同日两合约价差绝对值最大(元/吨)', '值': round(max(diffs), 2)},
                {'指标': '口径', '值': '同日两合约同时报收的真实价差，非跨日跳空；用于把换月影响从基差变化中剥离'}]
        wcsv('supp_roll_jump_summary.csv', summ)

    # 换月前后基差变化（跨日，含换月污染）
    rb = rcsv(os.path.join(OUT, 'roll_basis_effect_near.csv'))
    if rb:
        ch = [abs(float(r['基差变化'])) for r in rb if r.get('基差变化') not in ('', None)]
        print('[INFO] 换月日基差跨日变化 |d|: n=%d 均值 %.1f 中位 %.1f p90 %.1f 最大 %.1f'
              % (len(ch), statistics.fmean(ch), statistics.median(ch), pctile(ch, 90), max(ch)))

    # 非换月日的日常基差变化（作为对照）
    daily = rcsv(os.path.join(OUT, 'seas_near', 'daily_basis.csv'))
    roll_days = {r['换月日'] for r in rb}
    normal = []
    prev = None
    for r in daily:
        b = float(r['basis'])
        if prev is not None and r['date'] not in roll_days:
            normal.append(abs(b - prev))
        prev = b
    if normal:
        print('[INFO] 非换月日基差日变化 |d|: n=%d 均值 %.1f 中位 %.1f p90 %.1f'
              % (len(normal), statistics.fmean(normal), statistics.median(normal), pctile(normal, 90)))
        wcsv('supp_daily_change_compare.csv', [
            {'类别': '换月日基差跨日变化', '样本数': len(ch), '均值': round(statistics.fmean(ch), 2),
             '中位': round(statistics.median(ch), 2), 'p90': round(pctile(ch, 90), 2), '最大': round(max(ch), 2)},
            {'类别': '非换月日基差日变化', '样本数': len(normal), '均值': round(statistics.fmean(normal), 2),
             '中位': round(statistics.median(normal), 2), 'p90': round(pctile(normal, 90), 2), '最大': round(max(normal), 2)},
        ])


if __name__ == '__main__':
    main()
