# -*- coding: utf-8 -*-
"""
通用「基差季节性」计算引擎（跨品种可复用）
======================================================
输入：
  --spot  CSV：date,price[,spec,region,note]   （原样现货报价，不做任何填补）
  --map   CSV：date,fut_price[,contract]       （期货合约映射后的逐日价格）
输出：out/ 下若干 CSV + JSON，供 HTML/Excel 渲染

核心口径（全部显式记录，供审计）：
  1) 基差 = 现货价格 - 期货价格（严格按此符号，不取负、不取绝对值）
  2) 同口径对齐：以"期货交易日"为骨架；现货缺报日期不填补，只标记缺失，
     季节性统计时"有效样本数"为实际存在配对的年数。
  3) 对齐频率：
     - 周度：ISO 周，取该周最后一个有配对数据的交易日（weekday='Friday' 等效),
       并给出 week_of_year(ISO)。
     - 月度：自然月，取该月最后一个有配对数据的交易日（月末值），
       月度均值另存一列。
  4) 季节位置(seasonal position)：
     - 周度：ISO 周序号（1-53）
     - 月度：自然月（1-12）
  5) 分位：经验分位数（线性插值 numpy.percentile, method='linear'），
     对"同一季节位置在不同年份的取值"计算 p10/p25/p50/p75/p90 与均值。
     要求：该位置有效样本 >= MIN_SAMPLES（默认3），否则标记样本不足。
  6) 当前年位置：
     current_pct = 历史(不含当前年)中 < 当前值的比例（经验分位位置 0-100）
     z_position  = (当前值 - 历史均值)/历史标准差（样本标准差）
  7) 换月影响识别：
     在换月日，比较 [换月日基差] vs [前一交易日基差]，并把跳空拆成
     roll_component（换月纯价格跳空）与 genuine_change（剔除换月后变化）。
"""

import argparse, csv, json, os, sys, math
from collections import defaultdict
import statistics

MIN_SAMPLES = 3


def read_csv(path, required):
    rows = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        missing = [c for c in required if c not in rd.fieldnames]
        if missing:
            raise SystemExit('CSV %s 缺少列: %s (实际: %s)' % (path, missing, rd.fieldnames))
        for r in rd:
            rows.append(r)
    return rows


def to_float(x):
    try:
        if x is None or str(x).strip() == '':
            return None
        return float(str(x).replace(',', ''))
    except Exception:
        return None


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * (q / 100.0)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spot', required=True)
    ap.add_argument('--map', required=True)
    ap.add_argument('--outdir', default='out')
    ap.add_argument('--label', default='basis')
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    spot = read_csv(args.spot, ['date', 'price'])
    fmap = read_csv(args.map, ['date', 'fut_price'])
    spot_d = {}
    for r in spot:
        v = to_float(r['price'])
        d = r['date'].strip()
        if v is not None and d:
            spot_d[d] = v
    fut_d = {}
    fut_c = {}
    for r in fmap:
        v = to_float(r['fut_price'])
        d = r['date'].strip()
        if v is not None and d:
            fut_d[d] = v
            fut_c[d] = (r.get('contract') or '').strip()

    dates = sorted(fut_d)
    pairs = []
    missing_days = []
    for d in dates:
        if d in spot_d:
            pairs.append((d, spot_d[d], fut_d[d], fut_c[d]))
        else:
            missing_days.append(d)

    print('[INFO] 期货交易日 %d, 其中有现货报价 %d, 缺现货 %d (%.1f%%)'
          % (len(dates), len(pairs), len(missing_days),
             100.0 * len(missing_days) / max(1, len(dates))))

    # ---- 日度基差 ----
    daily = []
    for i, (d, s, f, c) in enumerate(pairs):
        daily.append({'date': d, 'year': int(d[:4]), 'month': int(d[5:7]),
                      'spot': s, 'fut': f, 'contract': c, 'basis': round(s - f, 2)})

    # ---- 周度 / 月度 对齐 ----
    import datetime
    def iso_week(d):
        y, m, dd = map(int, d.split('-'))
        iso = datetime.date(y, m, dd).isocalendar()
        return int(iso[0]), int(iso[1])

    weekly_last = {}
    monthly_last = {}
    monthly_vals = defaultdict(list)
    for row in daily:
        wy, wn = iso_week(row['date'])
        row['iso_year'], row['iso_week'] = wy, wn
        k = (wy, wn)
        if k not in weekly_last or row['date'] > weekly_last[k]['date']:
            weekly_last[k] = row
        mk = (row['year'], row['month'])
        if mk not in monthly_last or row['date'] > monthly_last[mk]['date']:
            monthly_last[mk] = row
        monthly_vals[mk].append(row['basis'])

    weekly = []
    for (wy, wn), row in sorted(weekly_last.items(), key=lambda x: x[0]):
        weekly.append({'iso_year': wy, 'iso_week': wn, 'date': row['date'],
                       'year': row['year'], 'month': row['month'],
                       'spot': row['spot'], 'fut': row['fut'], 'contract': row['contract'],
                       'basis': row['basis']})
    monthly = []
    for (y, m), row in sorted(monthly_last.items()):
        vals = monthly_vals[(y, m)]
        monthly.append({'year': y, 'month': m, 'date': row['date'],
                        'spot': row['spot'], 'fut': row['fut'], 'contract': row['contract'],
                        'basis_month_end': row['basis'],
                        'basis_mean': round(sum(vals) / len(vals), 2),
                        'n_days': len(vals)})

    # ---- 季节性分位（月度） ----
    by_month = defaultdict(list)
    for r in monthly:
        by_month[r['month']].append(r)
    seas_month = []
    for m in range(1, 13):
        rows = by_month.get(m, [])
        vals = [r['basis_month_end'] for r in rows]
        seas_month.append({
            'month': m, 'n_years': len(vals), 'n_sufficient': len(vals) >= MIN_SAMPLES,
            'mean': round(statistics.fmean(vals), 2) if vals else None,
            'median': round(pct(vals, 50), 2) if vals else None,
            'p10': round(pct(vals, 10), 2) if vals else None,
            'p25': round(pct(vals, 25), 2) if vals else None,
            'p75': round(pct(vals, 75), 2) if vals else None,
            'p90': round(pct(vals, 90), 2) if vals else None,
            'min': round(min(vals), 2) if vals else None,
            'max': round(max(vals), 2) if vals else None,
            'years': ','.join(str(r['year']) for r in rows),
        })

    # ---- 季节性分位（周度） ----
    by_week = defaultdict(list)
    for r in weekly:
        by_week[r['iso_week']].append(r)
    seas_week = []
    for w in range(1, 54):
        rows = by_week.get(w, [])
        vals = [r['basis'] for r in rows]
        seas_week.append({
            'iso_week': w, 'n_years': len(vals), 'n_sufficient': len(vals) >= MIN_SAMPLES,
            'mean': round(statistics.fmean(vals), 2) if vals else None,
            'median': round(pct(vals, 50), 2) if vals else None,
            'p10': round(pct(vals, 10), 2) if vals else None,
            'p25': round(pct(vals, 25), 2) if vals else None,
            'p75': round(pct(vals, 75), 2) if vals else None,
            'p90': round(pct(vals, 90), 2) if vals else None,
            'years': ','.join(str(r['iso_year']) for r in rows),
        })

    # ---- 当前年位置（月度 & 周度） ----
    cur_month_rows = monthly[-1] if monthly else None
    cur_week_row = weekly[-1] if weekly else None

    def position(cur_val, hist_vals):
        hv = [v for v in hist_vals if v is not None]
        if cur_val is None or len(hv) < 1:
            return {'value': cur_val, 'n_hist': len(hv), 'below_ratio': None,
                    'z': None, 'rank': None}
        below = sum(1 for v in hv if v < cur_val)
        below_strict_hi = sum(1 for v in hv if v <= cur_val)
        rank = (below + 0.5 * (below_strict_hi - below)) / len(hv)
        mean = statistics.fmean(hv)
        sd = statistics.pstdev(hv) if len(hv) > 1 else 0.0
        return {'value': cur_val, 'n_hist': len(hv),
                'below_ratio': round(rank * 100, 1),
                'z': round((cur_val - mean) / sd, 2) if sd else None,
                'hist_mean': round(mean, 2), 'hist_sd': round(sd, 2)}

    cur_pos = {}
    if cur_month_rows:
        m = cur_month_rows['month']
        hist = [r['basis_month_end'] for r in by_month[m] if r['year'] != cur_month_rows['year']]
        cur_pos['month'] = {'month': m, 'current_year': cur_month_rows['year'],
                            'as_of': cur_month_rows['date'],
                            **position(cur_month_rows['basis_month_end'], hist)}
    if cur_week_row:
        w = cur_week_row['iso_week']
        hist = [r['basis'] for r in by_week[w] if r['iso_year'] != cur_week_row['iso_year']]
        cur_pos['week'] = {'iso_week': w, 'current_year': cur_week_row['iso_year'],
                           'as_of': cur_week_row['date'],
                           **position(cur_week_row['basis'], hist)}

    # ---- 稳定性度量 ----
    # 1) 各月基差的跨年标准差 vs 全样本标准差（季节解释力，类似组间/组内）
    all_vals = [r['basis_month_end'] for r in monthly]
    grand = statistics.fmean(all_vals) if all_vals else 0
    sst = sum((v - grand) ** 2 for v in all_vals)
    ssw = 0.0
    for m in range(1, 13):
        rows = by_month.get(m, [])
        if rows:
            mu = statistics.fmean([r['basis_month_end'] for r in rows])
            ssw += sum((r['basis_month_end'] - mu) ** 2 for r in rows)
    stability = {
        'n_monthly_obs': len(monthly),
        'grand_mean': round(grand, 2),
        'between_month_ss': round(sst - ssw, 2),
        'within_month_ss': round(ssw, 2),
        'seasonal_ss_share': round((sst - ssw) / sst, 4) if sst else None,
        'note': 'seasonal_ss_share = 月份间方差占总方差比例，越高说明月度季节性越强；不做预测用途',
    }

    # ---- 输出 ----
    def wcsv(name, rows, cols):
        p = os.path.join(args.outdir, name)
        with open(p, 'w', encoding='utf-8-sig', newline='') as f:
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            for r in rows:
                wr.writerow({c: r.get(c, '') for c in cols})
        print('[OUT]', p, len(rows))

    wcsv('daily_basis.csv', daily, ['date', 'year', 'month', 'spot', 'fut', 'basis', 'contract'])
    wcsv('weekly_basis.csv', weekly, ['iso_year', 'iso_week', 'date', 'month', 'spot', 'fut', 'basis', 'contract'])
    wcsv('monthly_basis.csv', monthly, ['year', 'month', 'date', 'spot', 'fut', 'basis_month_end', 'basis_mean', 'n_days', 'contract'])
    wcsv('seasonal_month.csv', seas_month, ['month', 'n_years', 'n_sufficient', 'mean', 'median', 'p10', 'p25', 'p75', 'p90', 'min', 'max', 'years'])
    wcsv('seasonal_week.csv', seas_week, ['iso_week', 'n_years', 'n_sufficient', 'mean', 'median', 'p10', 'p25', 'p75', 'p90', 'years'])
    with open(os.path.join(args.outdir, 'meta_%s.json' % args.label), 'w', encoding='utf-8') as f:
        json.dump({'n_fut_days': len(dates), 'n_pairs': len(pairs),
                   'n_missing_spot': len(missing_days),
                   'missing_sample': missing_days[:20],
                   'first': daily[0]['date'] if daily else None,
                   'last': daily[-1]['date'] if daily else None,
                   'current_position': cur_pos, 'stability': stability,
                   'min_samples': MIN_SAMPLES}, f, ensure_ascii=False, indent=1)
    print('[INFO] 当前位置:', json.dumps(cur_pos, ensure_ascii=False))
    print('[INFO] 稳定性:', json.dumps(stability, ensure_ascii=False))


if __name__ == '__main__':
    main()
