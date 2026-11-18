# -*- coding: utf-8 -*-
"""detect_anomalies.py —— 价格异动识别与阶段切分。

设计要点（与"拍脑袋划分区间"划清界限）：
  1. 用**两个独立信号**做异动确认：日收益 |z| ≥ 阈值  **且** 放量（量能 z ≥ 阈值）。
     A 股商品期货习惯：脱离成交量的极端日涨跌多为切换/错价，不应作为"行情异动"。
  2. 异动日按"间隔 ≤ n 个交易日"合并成**异动簇**；簇的起点/终点以**同向延续**为准，
     允许 ±1 个交易日的容忍度（避免把休市后首日的高开/低开误切成两段）。
  3. 再把异动簇与"周线级别累计涨跌 ≥ 阈值"合并，得到**价格阶段（phase）**，
     每个阶段输出起止日、涨跌幅度、年化波动、期内最高/最低、异动日清单。

用法：
  python detect_anomalies.py --series raw/MA0_daily.json --out build/anomalies.json \
      --from 2026-06-01 --to 2026-10-19 --z 2.0 --vol-z 1.5 --cluster 3 --phase 6
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def load_bars(path):
    raw = C.jload(path)
    bars = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                bars.append({'date': C._norm_date(k), 'close': float(v.get('close')), 'high': v.get('high'),
                             'low': v.get('low'), 'volume': v.get('volume')})
    else:
        for r in raw:
            bars.append({'date': C._norm_date(r.get('date')), 'close': float(r.get('close')),
                         'high': r.get('high'), 'low': r.get('low'), 'volume': r.get('volume')})
    bars = [b for b in bars if b['close'] is not None]
    bars.sort(key=lambda b: b['date'])
    return bars


def detect(bars, z_thr=2.0, vol_z_thr=1.5, cluster_gap=3, phase_thr=6.0,
           lookback=60, start=None, end=None, require_volume=True):
    closes = [b['close'] for b in bars]
    rets, vols = [], []
    for i in range(1, len(bars)):
        rets.append(closes[i] / closes[i - 1] - 1)
        v = bars[i].get('volume')
        vols.append(v if v is not None else 0)
    # 滚动 60 日的 z（至少 20 个样本）
    recs = []
    for i, b in enumerate(bars):
        if i == 0:
            continue
        r = rets[i - 1]
        lo = max(0, i - 1 - lookback)
        hist = rets[lo:i - 1]
        z = C.zscore(hist, r) if len(hist) >= 20 else None
        vh = vols[lo:i - 1]
        vz = C.zscore(vh, vols[i - 1]) if len(vh) >= 20 and vols[i - 1] else None
        recs.append({'date': b['date'], 'close': b['close'], 'ret': r * 100, 'z': z,
                     'volume': vols[i - 1], 'vol_z': vz})
    # 异动日
    # spike          = 价格显著(|z|≥z_thr) 且 放量(vol_z≥vol_z_thr)  → 真正的异动
    # price_only     = 价格显著但无放量                          → 多为切换价/错价，不作为异动
    # extreme        = 价格显著（含 price_only），仅用于标注"这根K线异常"
    # vol_only       = 只放量不显著                              → 不作为异动
    for r in recs:
        price_sig = r['z'] is not None and abs(r['z']) >= z_thr
        vol_sig = r['vol_z'] is not None and r['vol_z'] >= vol_z_thr
        r['price_only'] = bool(price_sig and not vol_sig)
        r['vol_only'] = bool(vol_sig and not price_sig)
        # 关键纪律：没有成交量数据时，**不能**默认"放量了"。缺量能证据 → 降级为 price_only，
        # 只有当调用方显式允许 (require_volume=False) 时才把纯价格异动记为异动。
        r['spike'] = bool(price_sig and vol_sig) or bool(price_sig and r['vol_z'] is None and not require_volume)
        r['extreme'] = bool(price_sig)
    # 异动簇
    idx = [i for i, r in enumerate(recs) if r['spike']]
    clusters = []
    for i in idx:
        if clusters and i - clusters[-1][-1] <= cluster_gap:
            clusters[-1].append(i)
        else:
            clusters.append([i])
    out_clusters = []
    for cl in clusters:
        a, b = cl[0], cl[-1]
        # 同向延续：簇内累计方向
        tot = recs[b]['close'] / recs[a - 1]['close'] - 1 if a > 0 else 0
        sign = 1 if tot >= 0 else -1
        s, e = a, b
        # 容忍 ±1 日
        while e + 1 < len(recs) and recs[e + 1]['close'] * sign >= recs[e]['close'] * sign and \
                abs(recs[e + 1]['ret']) >= 0.3:
            e += 1
            if e - a > 12:
                break
        base_px = recs[s - 1]['close'] if s > 0 else recs[s]['close']
        out_clusters.append({
            'start_date': recs[s]['date'], 'end_date': recs[e]['date'],
            'start_close': base_px, 'end_close': recs[e]['close'],
            'chg_pct': (recs[e]['close'] / base_px - 1) * 100,
            'n_spike_days': len(cl),
            'direction': 'up' if sign > 0 else 'down',
            'spike_dates': [recs[k]['date'] for k in cl],
        })
    # 阶段：按"周线级别趋势"合并，避免把单日噪音当作阶段
    phases = build_phases(bars, phase_thr, start, end)
    return {'bars': recs, 'clusters': out_clusters, 'phases': phases,
            'params': {'z_thr': z_thr, 'vol_z_thr': vol_z_thr, 'cluster_gap': cluster_gap,
                       'phase_thr': phase_thr, 'lookback': lookback}}


def build_phases(bars, thr, start=None, end=None):
    """以"摆动高低点（zigzag）"切分阶段。thr 为最小反转幅度(%)。

    第一段必须先确认方向（从区间首日算起的最大涨/跌幅度达到 thr），
    否则区间首日到首次反转之间的走势不会形成"未确认的高点/低点"。
    """
    pts = [b for b in bars if (start is None or b['date'] >= start) and (end is None or b['date'] <= end)]
    if len(pts) < 5:
        return []
    piv = []
    dirn = 0            # 0=未定 1=上行 -1=下行
    base = pts[0]['close']
    hi, hi_i = pts[0]['close'], 0
    lo, lo_i = pts[0]['close'], 0
    for i in range(1, len(pts)):
        p = pts[i]['close']
        if p > hi:
            hi, hi_i = p, i
        if p < lo:
            lo, lo_i = p, i
        if dirn == 0:
            if hi / base - 1 >= thr / 100.0:
                dirn = 1
                piv.append({'i': 0, 'p': base, 'kind': 'start'})
                hi, hi_i = p, i
                lo, lo_i = p, i
            elif base / lo - 1 >= thr / 100.0:
                dirn = -1
                piv.append({'i': 0, 'p': base, 'kind': 'start'})
                hi, hi_i = p, i
                lo, lo_i = p, i
            continue
        if dirn == 1:
            if p <= hi * (1 - thr / 100.0):
                piv.append({'i': hi_i, 'p': hi, 'kind': 'peak'})
                dirn = -1
                lo, lo_i = p, i
        else:
            if p >= lo * (1 + thr / 100.0):
                piv.append({'i': lo_i, 'p': lo, 'kind': 'trough'})
                dirn = 1
                hi, hi_i = p, i
    if dirn == 1:
        piv.append({'i': hi_i, 'p': hi, 'kind': 'peak(未确认)'})
    elif dirn == -1:
        piv.append({'i': lo_i, 'p': lo, 'kind': 'trough(未确认)'})
    nodes = [{'date': pts[0]['date'], 'close': pts[0]['close']}]
    for p in piv[1:]:
        d = {'date': pts[p['i']]['date'], 'close': p['p'], 'kind': p['kind']}
        if d['date'] != nodes[-1]['date']:
            nodes.append(d)
    if nodes[-1]['date'] != pts[-1]['date']:
        nodes.append({'date': pts[-1]['date'], 'close': pts[-1]['close'], 'kind': 'end'})
    phases = []
    for a, b in zip(nodes, nodes[1:]):
        sub = [x['close'] for x in pts if a['date'] <= x['date'] <= b['date']]
        rets = [sub[i] / sub[i - 1] - 1 for i in range(1, len(sub))]
        phases.append({'start_date': a['date'], 'end_date': b['date'], 'start_close': a['close'],
                       'end_close': b['close'], 'chg_pct': (b['close'] / a['close'] - 1) * 100,
                       'n_days': len(sub),
                       'max': max(sub) if sub else None, 'min': min(sub) if sub else None,
                       'vol_daily_pct': (st.pstdev(rets) * 100) if len(rets) > 1 else None,
                       'end_kind': b.get('kind')})
    return phases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--series', required=True)
    ap.add_argument('--out', default='build/anomalies.json')
    ap.add_argument('--from', dest='d0', default=None)
    ap.add_argument('--to', dest='d1', default=None)
    ap.add_argument('--z', type=float, default=2.0)
    ap.add_argument('--vol-z', type=float, default=1.5)
    ap.add_argument('--cluster', type=int, default=3)
    ap.add_argument('--phase', type=float, default=6.0)
    a = ap.parse_args()
    bars = load_bars(a.series)
    res = detect(bars, a.z, a.vol_z, a.cluster, a.phase, start=a.d0, end=a.d1)
    C.jdump({'clusters': res['clusters'], 'phases': res['phases'], 'params': res['params'],
             'bars_in_window': [r for r in res['bars'] if (a.d0 is None or r['date'] >= a.d0) and (a.d1 is None or r['date'] <= a.d1)]},
            a.out)
    print('异动簇', len(res['clusters']), '个；价格阶段', len(res['phases']), '段 ->', a.out)
    for c in res['clusters']:
        print('  簇 %s~%s %s %+.2f%% (%d 个异动日)' % (c['start_date'], c['end_date'], c['direction'], c['chg_pct'], c['n_spike_days']))
    for p in res['phases']:
        print('  阶段 %s~%s %+.2f%%' % (p['start_date'], p['end_date'], p['chg_pct']))


if __name__ == '__main__':
    main()
