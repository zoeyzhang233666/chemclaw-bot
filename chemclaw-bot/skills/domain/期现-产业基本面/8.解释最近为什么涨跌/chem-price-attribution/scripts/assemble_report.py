# -*- coding: utf-8 -*-
"""assemble_report.py —— 把对齐结果、证据分级、异动识别拼成一份可直接渲染的报告数据包。

中间产物 build/report_data.json 同时是 HTML 与 Excel 的唯一数据源，
两者所以能"同源同数"，是因为它们都只读这一个文件。

用法：
  python assemble_report.py --case case.json --aligned build/aligned.json \
      --graded build/graded.json --anomalies build/phases.json --narrative narrative.json \
      --out build/report_data.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

GROUP_ORDER = ['structure', 'trade', 'inventory', 'supply', 'demand', 'cost', 'policy']
GROUP_CN = {'cost': '成本', 'supply': '供给', 'demand': '需求', 'inventory': '库存',
            'trade': '贸易', 'policy': '政策/事件', 'structure': '期现结构'}
STRUCT = {'cost': '成本传导', 'supply': '供给收缩', 'demand': '需求负反馈', 'inventory': '库存周期',
          'trade': '进口替代', 'policy': '外生冲击', 'structure': '期现结构'}


def rolling(series_map, n=5):
    """返回 {date: MA_n}，只对连续交易日计算。"""
    ks = sorted(series_map)
    out = {}
    for i in range(n - 1, len(ks)):
        vals = [series_map[ks[j]] for j in range(i - n + 1, i + 1)]
        out[ks[i]] = st.mean(vals)
    return out


def build(case, aligned, graded, anomalies, narrative, base_dir):
    win = case['window']
    start, end = win['start'], win['end']

    # ---------- 价格序列（含基差） ----------
    spot = C.load_csv(os.path.join(base_dir, case['spot']['file']),
                      case['spot']['date_col'], case['spot']['value_col'])
    fut = {}
    if case.get('futures'):
        fut = C.load_json_series(os.path.join(base_dir, case['futures']['file']),
                                 'date', case['futures'].get('value_col', 'close'))
        oi = C.load_json_series(os.path.join(base_dir, case['futures']['file']), 'date',
                                case['futures'].get('oi_col', 'oi'))
    else:
        oi = {}
    struct = aligned.get('structure', {})
    daily = {p[0]: p[1] for p in struct.get('daily', [])} if struct.get('ok') else {}

    price_rows = []
    base_daily = {x['date']: x for x in (struct.get('baseline', {}) or {}).get('daily', [])}
    spread_daily = {x['date']: x for x in (struct.get('spread', {}) or {}).get('daily', [])}
    for d in sorted(set(spot) | set(fut)):
        if not C.in_win(d, start, end):
            continue
        s = spot.get(d)
        f = fut.get(d)
        sm = daily.get(d) or {}
        bl = base_daily.get(d) or {}
        sp = spread_daily.get(d) or {}
        price_rows.append({
            'date': d,
            'spot': round(s, 2) if s else None,
            'fut': round(f, 2) if f else None,
            'front': round(sm.get('front'), 2) if sm.get('front') else None,
            'front_contract': sm.get('front_contract'),
            'basis': round(sm['basis'], 2) if sm.get('basis') is not None else None,
            'basis_pct': round(sm['basis_pct'], 2) if sm.get('basis_pct') is not None else None,
            'base_close': round(bl['fut'], 2) if bl.get('fut') is not None else None,
            'base_basis': round(bl['basis'], 2) if bl.get('basis') is not None else None,
            'spread': round(sp['spread'], 2) if sp.get('spread') is not None else None,
            'm1m2': round(sm['m1m2'], 2) if sm.get('m1m2') is not None else None,
            'oi': round(oi[d], 0) if oi.get(d) else None,
            'anomaly': None,
        })
    # 用异动识别结果标注
    bar_of = {b['date']: b for b in (anomalies or {}).get('bars_in_window', [])}
    for r in price_rows:
        b = bar_of.get(r['date'])
        if b and b.get('spike'):
            r['anomaly'] = 'spike'
        elif b and b.get('extreme'):
            r['anomaly'] = 'extreme'

    # ---------- 驱动序列（HTML 稀疏共享轴用） ----------
    series_store = {}
    for drv in case['drivers']:
        for spc in drv.get('series', []):
            path = os.path.join(base_dir, spc['file'])
            if not os.path.exists(path):
                continue
            pts = C.load_csv(path, spc.get('date_col', 'date'), spc.get('value_col', 'price')) \
                if path.lower().endswith('.csv') else \
                C.load_json_series(path, spc.get('date_col', 'name'), spc.get('value_col', 'age'))
            pts = {k: v for k, v in pts.items() if C.in_win(k, start, end)}
            series_store[spc['id']] = {
                'name': spc['name'], 'unit': spc.get('unit'), 'driver': drv['id'],
                'points': [[k, round(v, 2)] for k, v in sorted(pts.items())],
                'freq': 'day',
            }
    # 持仓量
    if oi:
        series_store['oi'] = {'name': '甲醇期货持仓量（主连）', 'unit': '手', 'driver': 'structure',
                              'points': [[k, round(v, 0)] for k, v in sorted(oi.items()) if C.in_win(k, start, end)],
                              'freq': 'day'}
    # 期现结构（基差/月差）也作为可框选的序列，供局部归因使用
    base_daily = {x['date']: x for x in (struct.get('baseline', {}) or {}).get('daily', [])}
    if base_daily:
        series_store['basis_base'] = {
            'name': '基差（现货−%s）' % struct.get('baseline_contract'), 'unit': '元/吨', 'driver': 'basis',
            'points': [[k, round(v['basis'], 2)] for k, v in sorted(base_daily.items())], 'freq': 'day'}
    spread_daily = {x['date']: x for x in (struct.get('spread', {}) or {}).get('daily', [])}
    if spread_daily:
        pair = '-'.join(struct['spread']['pair'])
        series_store['spread_base'] = {
            'name': '月差 %s' % pair, 'unit': '元/吨', 'driver': 'basis',
            'points': [[k, round(v['spread'], 2)] for k, v in sorted(spread_daily.items())], 'freq': 'day'}

    # ---------- 分期对齐矩阵 ----------
    phases = (anomalies or {}).get('phases', [])
    names = [('spot', case['spot']['name'], '元/吨'), ('fut', case['futures']['name'] if case.get('futures') else '期货', '元/吨')]
    for drv in case['drivers']:
        for spc in drv.get('series', []):
            names.append((spc['id'], spc['name'], spc.get('unit', '')))
    matrix = []
    for ph in aligned.get('phases', []):
        row = {'start_date': ph['start_date'], 'end_date': ph['end_date'],
               'chg_pct': round(ph['chg_pct'], 2) if ph.get('chg_pct') is not None else None, 'vals': {}}
        for key, label, unit in names:
            v = ph['drivers'].get(key) or {}
            row['vals'][key] = round(v['pct_change'], 2) if v.get('pct_change') is not None else None
        matrix.append(row)
    series_meta = [{'id': k, 'name': n, 'unit': u} for k, n, u in names]

    # ---------- 因子时间线（HTML 热图） ----------
    tree = []
    for drv in case['drivers']:
        layer = aligned['layers'].get(drv['id'], {})
        items = [it for it in graded['items'] if it['factor'] == drv['name']]
        lv = {l: sum(1 for it in items if it['level'] == l) for l in ('E1', 'E2', 'E3', 'E4')}
        best = next((it for it in items if it['level'] == 'E1'), None) or \
               next((it for it in items if it['level'] == 'E2'), None) or \
               next((it for it in items if it['level'] == 'E3'), None) or \
               (items[0] if items else None)
        tree.append({
            'id': drv['id'], 'name': drv['name'], 'group': drv['group'],
            'group_cn': GROUP_CN.get(drv['group'], drv['group']),
            'sign': drv.get('sign'), 'logic': drv.get('logic'),
            'counts': lv, 'level': (best or {}).get('level', 'E4'),
            'best': best, 'items': items,
            'series': layer.get('series', []), 'manual': layer.get('manual', []),
        })
    tree.sort(key=lambda x: (GROUP_ORDER.index(x['group']) if x['group'] in GROUP_ORDER else 99,
                             {'E1': 0, 'E2': 1, 'E3': 2, 'E4': 3}[x['level']]))

    # ---------- 事件时间线 ----------
    evs = []
    for drv in case['drivers']:
        for it in graded['items']:
            if it['factor'] == drv['name'] and it.get('date') and it.get('evidence_type', '').startswith('事件'):
                evs.append({'date': it['date'], 'group': drv['group'], 'group_cn': GROUP_CN.get(drv['group']),
                            'driver': drv['id'], 'title': it['series'], 'level': it['level'],
                            'dir': it.get('dir'), 'magnitude': it.get('value'), 'src': it.get('src'),
                            'url': it.get('src_url'), 'lead_days': it.get('lead_days')})
    evs.sort(key=lambda x: x['date'])

    # ---------- 摘要 ----------
    pl = aligned['layers']['price']
    summary = {
        'spot_start': pl['spot'].get('start_value'), 'spot_end': pl['spot'].get('end_value'),
        'spot_chg_pct': pl['spot'].get('pct_change'), 'spot_abs': pl['spot'].get('abs_change'),
        'spot_start_date': pl['spot'].get('start_date'), 'spot_end_date': pl['spot'].get('end_date'),
        'fut_start': pl['futures'].get('start_value'), 'fut_end': pl['futures'].get('end_value'),
        'fut_chg_pct': pl['futures'].get('pct_change'), 'fut_abs': pl['futures'].get('abs_change'),
        'fut_start_date': pl['futures'].get('start_date'), 'fut_end_date': pl['futures'].get('end_date'),
        'basis_start': struct.get('start', {}).get('basis') if struct.get('ok') else None,
        'basis_end': struct.get('end', {}).get('basis') if struct.get('ok') else None,
        'basis_max': struct.get('basis_max') if struct.get('ok') else None,
        'basis_max_date': struct.get('basis_max_date') if struct.get('ok') else None,
        'basis_min': struct.get('basis_min') if struct.get('ok') else None,
        'basis_min_date': struct.get('basis_min_date') if struct.get('ok') else None,
        'n_events': len(evs),
        'n_items': len(graded['items']),
        'level_counts': {l: sum(1 for it in graded['items'] if it['level'] == l) for l in ('E1', 'E2', 'E3', 'E4')},
    }
    # 基准合约口径的汇总（同一合约全期可比）
    bl = struct.get('baseline') if struct.get('ok') else None
    if bl:
        summary.update({
            'base_contract': struct.get('baseline_contract'),
            'base_basis_start': bl['start']['basis'], 'base_basis_end': bl['end']['basis'],
            'base_basis_max': bl['basis_max'], 'base_basis_max_date': bl['basis_max_date'],
            'base_basis_min': bl['basis_min'], 'base_basis_min_date': bl['basis_min_date'],
        })
    sp = struct.get('spread') if struct.get('ok') else None
    if sp:
        summary.update({'spread_pair': sp['pair'], 'spread_start': sp['start']['spread'],
                        'spread_end': sp['end']['spread'],
                        'spread_min': sp['min'], 'spread_max': sp['max']})

    # 期内极值
    sp = [r for r in price_rows if r['spot']]
    if sp:
        hi = max(sp, key=lambda r: r['spot'])
        lo = min(sp, key=lambda r: r['spot'])
        summary.update({'spot_period_high': hi['spot'], 'spot_period_high_date': hi['date'],
                        'spot_period_low': lo['spot'], 'spot_period_low_date': lo['date']})
    fp = [r for r in price_rows if r['fut']]
    if fp:
        hi = max(fp, key=lambda r: r['fut'])
        lo = min(fp, key=lambda r: r['fut'])
        summary.update({'fut_period_high': hi['fut'], 'fut_period_high_date': hi['date'],
                        'fut_period_low': lo['fut'], 'fut_period_low_date': lo['date']})

    return {
        'meta': {
            'generated': C.dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'case': case.get('case', {}),
            'window': win,
            'spot_spec': case['spot'],
            'fut_spec': case.get('futures') or {},
            'score_rule': graded.get('score_rule'),
            'disclaimer': graded.get('disclaimer'),
            'level_text': graded.get('level_text'),
        },
        'summary': summary,
        'price': price_rows,
        'series': series_store,
        'series_meta': series_meta,
        'matrix': matrix,
        'phases': phases,
        'tree': tree,
        'events': evs,
        'ranked': graded['ranking'],
        'items': graded['items'],
        'narrative': narrative,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True)
    ap.add_argument('--aligned', required=True)
    ap.add_argument('--graded', required=True)
    ap.add_argument('--anomalies', default=None)
    ap.add_argument('--narrative', default=None)
    ap.add_argument('--out', default='build/report_data.json')
    ap.add_argument('--base-dir', default=None)
    a = ap.parse_args()
    case = C.jload(a.case)
    base = a.base_dir or os.path.dirname(os.path.abspath(a.case))
    aligned = C.jload(a.aligned)
    graded = C.jload(a.graded)
    anomalies = C.jload(a.anomalies) if a.anomalies else None
    narrative = C.jload(a.narrative) if a.narrative and os.path.exists(a.narrative) else {}
    data = build(case, aligned, graded, anomalies, narrative, base)
    C.jdump(data, a.out)
    s = data['summary']
    print('报告数据包 ->', a.out)
    print('  现货 %+.2f%% / 期货 %+.2f%% / 事件 %d / 证据条目 %d' % (
        s['spot_chg_pct'] or 0, s['fut_chg_pct'] or 0, s['n_events'], s['n_items']))


if __name__ == '__main__':
    main()
