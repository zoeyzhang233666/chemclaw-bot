# -*- coding: utf-8 -*-
"""构建冻结数据集 data.json —— 所有数字单一来源、带口径元数据、无人工编造。

输入 (raw/):
  fut_V0_daily.csv             PVC 主力连续日线 (新浪)
  ppi_107_series.json          生意社 PVC 基准价 (近 93 天)
  ppi_640_series.json          生意社 电石基准价
  ppi_368_series.json          生意社 烧碱基准价
  mysteel_pvc_cost_weekly.json 隆众 全国电石法 PVC 成本/毛利 周度
输出:
  build/data.json
"""
import os
import csv
import json
import statistics as st
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, 'raw')
BUILD = os.path.join(ROOT, 'build')
os.makedirs(BUILD, exist_ok=True)

AS_OF = '2026-10-20'          # 数据冻结日（生意社/新浪最新可用交易日）
WINDOW_START = '2025-10-20'   # 近 1 年


def load_fut():
    rows = list(csv.DictReader(open(os.path.join(RAW, 'fut_V0_daily.csv'), encoding='utf-8-sig')))
    return [{'date': r['date'], 'close': float(r['close']), 'settle': float(r['settle']),
             'open': float(r['open']), 'high': float(r['high']), 'low': float(r['low'])} for r in rows]


def load_ppi(pid):
    a = json.load(open(os.path.join(RAW, 'ppi_%d_series.json' % pid), encoding='utf-8'))
    return {d: v for d, v in a}


def month_avg(series, key='close'):
    """按月聚合日均价（自然日均价）。"""
    buckets = {}
    for r in series:
        buckets.setdefault(r['date'][:7], []).append(r[key])
    return {k: round(st.mean(v), 1) for k, v in sorted(buckets.items())}


def main():
    fut = load_fut()
    ppi_pvc = load_ppi(107)
    ppi_ca = load_ppi(640)
    ppi_naoh = load_ppi(368)
    mysteel = json.load(open(os.path.join(RAW, 'mysteel_pvc_cost_weekly.json'), encoding='utf-8'))

    # ---------- 1) PVC 现货代理校准 ----------
    fut_map = {r['date']: r['close'] for r in fut}
    ov = [(d, ppi_pvc[d], fut_map[d]) for d in sorted(ppi_pvc) if d in fut_map]
    basis = [p - f for _, p, f in ov]
    calib = {'n_overlap': len(ov), 'basis_mean': round(st.mean(basis), 1),
             'basis_median': round(st.median(basis), 1), 'basis_sd': round(st.pstdev(basis), 1),
             'basis_min': round(min(basis), 1), 'basis_max': round(max(basis), 1),
             'overlap_start': ov[0][0], 'overlap_end': ov[-1][0]}

    # ---------- 2) 时间序列（近 1 年） ----------
    win = [r for r in fut if r['date'] >= WINDOW_START]
    series = []
    for r in win:
        d = r['date']
        series.append({
            'date': d,
            'fut_close': r['close'],
            'fut_settle': r['settle'],
            'pvc_proxy': round(r['close'] + calib['basis_mean'], 1),
            'pvc_spot_ppi': ppi_pvc.get(d),
            'carbide_spot': ppi_ca.get(d),
            'naoh_spot': ppi_naoh.get(d),
        })

    # ---------- 3) 月度锚点 ----------
    monthly = {}
    for row in series:
        m = row['date'][:7]
        b = monthly.setdefault(m, {'pvc_proxy': [], 'fut_close': [], 'pvc_spot_ppi': [],
                                   'carbide_spot': [], 'naoh_spot': []})
        for k in b:
            v = row.get(k)
            if v is not None:
                b[k].append(v)
    monthly = {m: {k: (round(st.mean(v), 1) if v else None) for k, v in b.items()}
               for m, b in sorted(monthly.items())}

    # 隆众周度 -> 月度均值
    ms_month = {}
    for r in mysteel:
        c = r.get('date_cut') or ''
        if len(c) < 7:
            continue
        m = c[:7]
        b = ms_month.setdefault(m, {'cost_nat': [], 'cost_nw': [], 'cost_sd': [],
                                    'profit_nat': [], 'profit_nw': []})
        for k in ['cost_nat', 'cost_nw', 'cost_sd', 'profit_nat', 'profit_nw']:
            if r.get(k) is not None:
                b[k].append(r[k])
    ms_month = {m: {k: (round(st.mean(v), 1) if v else None) for k, v in b.items()}
                for m, b in sorted(ms_month.items())}
    for m in ms_month:
        if m in monthly:
            monthly[m].update(ms_month[m])

    # ---------- 4) 最新截面 ----------
    latest_fut = win[-1]
    last_spot = max(ppi_pvc)
    # 电石/烧碱取"不晚于 last_spot 的最近一个有值日期"，并显式记录日期
    ca_dates = sorted([d for d in ppi_ca if d <= last_spot])
    naoh_dates = sorted([d for d in ppi_naoh if d <= last_spot])
    ca_date = ca_dates[-1] if ca_dates else None
    naoh_date = naoh_dates[-1] if naoh_dates else None
    cross = {
        'date': last_spot,
        'pvc_spot_ppi': ppi_pvc[last_spot],
        'pvc_fut_close': fut_map.get(last_spot),
        'carbide_spot': ppi_ca.get(ca_date) if ca_date else None,
        'carbide_date': ca_date,
        'naoh_spot': ppi_naoh.get(naoh_date) if naoh_date else None,
        'naoh_date': naoh_date,
        'pvc_spot_month_ago': ppi_pvc[min(ppi_pvc, key=lambda d: abs((date.fromisoformat(d)
                                                                    - date(2026, 9, 20)).days))],
        'carbide_month_ago': ppi_ca.get(min(ppi_ca, key=lambda d: abs((date.fromisoformat(d)
                                                                      - date(2026, 9, 20)).days))),
    }

    out = {
        'meta': {
            'product': 'PVC 聚氯乙烯 (SG-5 型树脂粉)',
            'process': '电石乙炔法 (calcium carbide / acetylene route)',
            'as_of': AS_OF, 'window_start': WINDOW_START,
            'basis_note': '主力连续在换月日存在跳空；现货代理=主力收盘+重叠期平均基差',
        },
        'calibration': calib,
        'series': series,
        'monthly': monthly,
        'mysteel_weekly': mysteel,
        'cross': cross,
    }
    json.dump(out, open(os.path.join(BUILD, 'data.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('series pts', len(series), series[0]['date'], '->', series[-1]['date'])
    print('calibration', calib)
    print('cross', cross)
    print('months', sorted(monthly))
    print('-> build/data.json')


if __name__ == '__main__':
    main()
