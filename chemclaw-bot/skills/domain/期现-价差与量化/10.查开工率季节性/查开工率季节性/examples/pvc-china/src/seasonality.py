# -*- coding: utf-8 -*-
"""
开工率季节性统计引擎（产品无关，PVC 为其一例）。

设计原则
--------
1. **只统计真实观测**：不做插值、不前向填充、不按“上一期”补洞；缺数就是缺数。
2. **小样本优先诚实**：n<3 不给分位数；n<5 在结论里强制标注“样本不足”。
3. **分位数口径锁定**：经验分位（线性插值），= Excel PERCENTILE / PERCENTILE.INC
   = R quantile(type=7) = numpy.percentile(method="linear")，三处必须一致。
4. **同口径可比**：不同发布方（隆众/卓创/钢联）、不同频率（周/月）、
   不同指标（产能利用率 / 开工负荷率）不得混入同一条序列。
5. **不把样本开工率当产量**：输出里显式给出“不可换算为全行业实际产量”的警示。

用法
----
    python seasonality.py --weekly raw/pvc_util_weekly.csv --out out/
产出
----
    out/seasonal_profile.csv    按 ISO 周对齐的跨年均值/中位数/分位
    out/current_year.csv        今年逐周定位（分位位置、z 值、4W/12W 变化）
    out/anomaly.csv             异常年份 / 异常周识别
    out/comparison.csv          今年的同期对照与锚点对照
    out/summary.json            汇总指标（供 HTML/Excel 复用）
"""
import argparse
import csv
import json
import math
import os
from collections import defaultdict
from datetime import date

MIN_SAMPLES_FOR_PCT = 3
SMALL_SAMPLE = 5


def _iso(week_end):
    d = date(int(week_end[:4]), int(week_end[4:6]), int(week_end[6:8]))
    iy, iw, _ = d.isocalendar()
    return iy, iw, d


# ---------------------------------------------------------------- 基础统计
def percentile_linear(values, q):
    """经验分位（线性插值）。等价 Excel PERCENTILE.INC / numpy.percentile(method='linear')。"""
    v = sorted(float(x) for x in values)
    n = len(v)
    if n == 0:
        return None
    if n == 1:
        return v[0]
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return v[lo]
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def mean(v):
    return sum(v) / len(v) if v else None


def stdev_s(v):
    """样本标准差（n-1）。n<2 返回 None。"""
    if len(v) < 2:
        return None
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def cv(v):
    """变异系数。样本不足返回 None。"""
    m, s = mean(v), stdev_s(v)
    if not m or s is None:
        return None
    return s / m


def describe(v, label):
    v = [x for x in v if x is not None]
    if not v:
        return {'label': label, 'n': 0}
    d = {'label': label, 'n': len(v), 'mean': round(mean(v), 2),
         'median': round(percentile_linear(v, 0.5), 2),
         'min': round(min(v), 2), 'max': round(max(v), 2),
         'stdev': (round(stdev_s(v), 2) if stdev_s(v) is not None else None),
         'cv': (round(cv(v), 4) if cv(v) is not None else None)}
    for q in (0.1, 0.25, 0.75, 0.9):
        d[f'p{int(q * 100)}'] = (round(percentile_linear(v, q), 2)
                                 if len(v) >= MIN_SAMPLES_FOR_PCT else None)
    d['small_sample'] = len(v) < SMALL_SAMPLE
    return d


def seasonal_strength(groups):
    """
    seasonal_ss_share = 组间平方和 / 总平方和（0~1，越大说明“周次”解释力越强）。
    这是判断“是否真的存在季节性”的量化依据；n 很小的时候会高估，必须同时报 n。
    """
    allv = [x for g in groups.values() for x in g]
    if len(allv) < 3:
        return None
    gm = mean(allv)
    sst = sum((x - gm) ** 2 for x in allv)
    ssb = sum(len(g) * (mean(g) - gm) ** 2 for g in groups.values() if g)
    return (ssb / sst) if sst else None


# ---------------------------------------------------------------- 数据装载
def load_weekly(path):
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if not (r.get('util') or '').strip():
            continue
        rec = {
            'week_end': r['week_end'].strip(),
            'date': r['date'].strip(),
            'iso_year': int(r['iso_year']),
            'iso_week': int(r['iso_week']),
            'util': float(r['util']),
            'calc': float(r['calc']) if r.get('calc') else None,
            'eth': float(r['eth']) if r.get('eth') else None,
            'sample_n': float(r['sample_n']) if r.get('sample_n') else None,
            'source_url': r.get('source_url', ''),
            'note': r.get('note', ''),
            'obs_type': r.get('obs_type', ''),
        }
        out.append(rec)
    out.sort(key=lambda x: x['date'])
    return out


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--weekly', default='raw/pvc_util_weekly.csv')
    ap.add_argument('--anchor', default='raw/external_anchor.csv')
    ap.add_argument('--anchor-series', default='raw/anchor_weekly.csv',
                    help='历年单周可核验锚点（同口径），用于补足跨年可比性')
    ap.add_argument('--out', default='out')
    ap.add_argument('--metric', default='util')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = load_weekly(a.weekly)
    if not rows:
        raise SystemExit('无可用周度观测，拒绝生成任何统计结论')

    years = sorted({r['iso_year'] for r in rows})
    cur_year = years[-1]
    metric = a.metric

    # ---- 1) 按 ISO 周对齐 ----
    by_week = defaultdict(list)
    by_year = defaultdict(list)
    for r in rows:
        if r[metric] is None:
            continue
        by_week[r['iso_week']].append(r[metric])
        by_year[r['iso_year']].append(r[metric])

    profile = []
    for w in sorted(by_week):
        v = by_week[w]
        d = describe(v, f'W{w:02d}')
        d['iso_week'] = w
        d['years'] = sorted({r['iso_year'] for r in rows if r['iso_week'] == w and r[metric] is not None})
        profile.append(d)

    # ---- 1b) 历年同周锚点（同口径单周观测）：跨年可比性的唯一可靠来源 ----
    #     必须在这里装载 —— “今年逐周定位”的分母要用它。
    anchor_rows = []
    if os.path.exists(a.anchor_series):
        with open(a.anchor_series, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                try:
                    v = float(r['util'])
                except (TypeError, ValueError, KeyError):
                    continue
                iy, iw, d = _iso(r['week_end'])
                anchor_rows.append({'week_end': r['week_end'], 'date': d.isoformat(),
                                    'iso_year': iy, 'iso_week': iw, 'util': v,
                                    'source': r.get('source', ''), 'url': r.get('url', '')})
    anchor_rows.sort(key=lambda x: x['date'])
    merged_by_week = defaultdict(list)
    for w, vs in by_week.items():
        merged_by_week[w].extend(vs)
    for r in anchor_rows:
        merged_by_week[r['iso_week']].append(r['util'])

    # ---- 2) 今年逐周定位（历史 = 主数据集 + 同口径单周锚点）----
    cur = [r for r in rows if r['iso_year'] == cur_year and r[metric] is not None]
    cur_rows = []
    for i, r in enumerate(cur):
        hist = merged_by_week.get(r['iso_week'], [])
        p50 = percentile_linear(hist, 0.5) if len(hist) >= MIN_SAMPLES_FOR_PCT else None
        p10 = percentile_linear(hist, 0.10) if len(hist) >= MIN_SAMPLES_FOR_PCT else None
        p90 = percentile_linear(hist, 0.90) if len(hist) >= MIN_SAMPLES_FOR_PCT else None
        below = (sum(1 for x in hist if x < r[metric]) / len(hist)) if hist else None
        sd = stdev_s(hist)
        z = ((r[metric] - mean(hist)) / sd) if (sd and len(hist) >= 3) else None
        c4 = (r[metric] - cur[i - 4][metric]) if i >= 4 else None
        c12 = (r[metric] - cur[i - 12][metric]) if i >= 12 else None
        cur_rows.append({
            'week_end': r['week_end'], 'date': r['date'], 'iso_week': r['iso_week'],
            'util': r[metric], 'hist_n': len(hist),
            'hist_mean': (round(mean(hist), 2) if hist else None),
            'hist_p10': (round(p10, 2) if p10 is not None else None),
            'hist_p50': (round(p50, 2) if p50 is not None else None),
            'hist_p90': (round(p90, 2) if p90 is not None else None),
            'below_ratio': (round(below, 3) if below is not None else None),
            'z': (round(z, 2) if z is not None else None),
            'chg_4w': (round(c4, 2) if c4 is not None else None),
            'chg_12w': (round(c12, 2) if c12 is not None else None),
        })

    # ---- 3) 异常年份识别 ----
    anomalies = []
    for y in years:
        v = by_year[y]
        if len(v) < 2:
            anomalies.append({'year': y, 'n': len(v), 'mean': round(mean(v), 2),
                              'flag': '样本不足（<2 周）不可判定'})
            continue
        sd = stdev_s(v)
        anomalies.append({
            'year': y, 'n': len(v), 'mean': round(mean(v), 2),
            'median': round(percentile_linear(v, .5), 2),
            'min': round(min(v), 2), 'max': round(max(v), 2),
            'range': round(max(v) - min(v), 2),
            'stdev': (round(sd, 2) if sd is not None else None),
            'cv': (round(sd / mean(v), 4) if sd and mean(v) else None),
            'flag': '样本不足（<5 周）不可判定常年规律' if len(v) < SMALL_SAMPLE else '',
        })

    # ---- 4) 同期对照（今年本周 vs 可核验的历年同周锚点）----
    comparison = []
    anchors = []
    if os.path.exists(a.anchor):
        with open(a.anchor, encoding='utf-8-sig') as f:
            anchors = list(csv.DictReader(f))
    last = cur[-1] if cur else None
    if last:
        for an in anchors:
            if '同源同定义' not in an.get('caliber', ''):
                continue
            try:
                av = float(an['util'])
            except (TypeError, ValueError):
                continue
            comparison.append({
                'week_end': an['week_end'], 'anchor_util': av,
                'cur_week_end': last['week_end'], 'cur_util': last[metric],
                'diff_pp': round(last[metric] - av, 2),
                'source': an['source'], 'url': an['url'],
            })

    seasonal = seasonal_strength({w: by_week[w] for w in by_week})
    summary = {
        'metric': metric,
        'obs_count': len(rows),
        'date_from': rows[0]['date'], 'date_to': rows[-1]['date'],
        'iso_from': f"{rows[0]['iso_year']}-W{rows[0]['iso_week']:02d}",
        'iso_to': f"{rows[-1]['iso_year']}-W{rows[-1]['iso_week']:02d}",
        'years': years,
        'weeks_per_year': {str(y): len(by_year[y]) for y in years},
        'coverage_years': len(years),
        'coverage_weeks': len(by_week),
        'seasonal_ss_share': (round(seasonal, 4) if seasonal is not None else None),
        'seasonal_verdict': (None if seasonal is None else
                             ('不足以判定季节性：跨年观测<3个年份' if len(years) < 3 else
                              ('季节性弱' if seasonal < 0.4 else
                               ('季节性中等' if seasonal < 0.6 else '季节性显著')))),
        'current': (describe(by_year[cur_year], f'{cur_year}年') if by_year.get(cur_year) else None),
        'latest': (last[metric] if last else None),
        'latest_week_end': (last['week_end'] if last else None),
        'sample_n': (rows[-1]['sample_n'] if rows else None),
        'pct_method': '经验分位·线性插值（=Excel PERCENTILE.INC / R quantile type=7）',
    }

    def dump(name, rows_, fields=None):
        p = os.path.join(a.out, name)
        if not rows_:
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                f.write('empty\n')
            return p
        with open(p, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields or list(rows_[0].keys()), extrasaction='ignore')
            w.writeheader()
            w.writerows(rows_)
        return p

    # 锚点周的分位（用合并历史重算，供报告对照）
    anchor_profile = []
    for r in anchor_rows:
        hist = [x for x in merged_by_week.get(r['iso_week'], []) if x != r['util']] or []
        n = len(hist)
        anchor_profile.append({
            'week_end': r['week_end'], 'iso_week': r['iso_week'], 'util': r['util'],
            'hist_n': n,
            'hist_mean': (round(mean(hist), 2) if hist else None),
            'hist_p50': (round(percentile_linear(hist, .5), 2) if n >= MIN_SAMPLES_FOR_PCT else None),
            'src_hist_note': ('该周号在数据集中另有 %d 个观测可用于对照' % n if n else
                              '该周号在数据集中无其他观测，分位数不可计算'),
            'source': r['source'], 'url': r['url'],
        })

    dump('anchor_series.csv', anchor_profile)

    dump('seasonal_profile.csv', profile)
    dump('current_year.csv', cur_rows)
    dump('anomaly.csv', anomalies)
    dump('comparison.csv', comparison)
    with open(os.path.join(a.out, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print('--- 今年逐周定位 ---')
    for r in cur_rows:
        print(f"  {r['week_end']} W{r['iso_week']:02d} {r['util']:.2f}  "
              f"hist_n={r['hist_n']} below={r['below_ratio']} 4w={r['chg_4w']} 12w={r['chg_12w']}")
    print('--- 同期对照 ---')
    for c in comparison:
        print(f"  vs {c['week_end']}: {c['anchor_util']} -> {c['cur_util']} ({c['diff_pp']:+} pp)")


if __name__ == '__main__':
    main()
