# -*- coding: utf-8 -*-
"""把 research.json + series + specs 算成一个不可变的结果模型（HTML / Excel 同源）。

用法：
  python scripts/model.py <research.json> --out work/model.json
"""
import argparse
import datetime
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)


def _series(base_dir, rel):
    p = rel if os.path.isabs(rel) else os.path.join(base_dir, rel)
    if not os.path.exists(p):
        # 再试 skill 根目录相对路径（research.json 里写 "series/..." 的简写）
        p2 = os.path.join(SKILL, rel)
        if os.path.exists(p2):
            p = p2
        else:
            return None
    return common.load_json(p)


def build(research_path):
    R = common.load_json(research_path)
    base = os.path.dirname(os.path.abspath(research_path))
    spec_name = R['meta']['spec_file']
    # 先按 research.json 同级解析，再退回 skill 根目录（common.load_spec 内部处理）
    cand = spec_name if os.path.isabs(spec_name) else os.path.join(base, spec_name.replace('/', os.sep))
    spec = common.load_spec(cand if os.path.exists(cand) else spec_name)
    q = R['quote']
    asof = R['meta']['asof']

    # ---------------- 1. 报价标准化
    norm = common.standardize(q, spec)
    meta = norm.pop('_meta')

    # ---------------- 2. 参考价与基准区间
    anchors = R['market']['spot_anchors']
    by_id = {a['id']: a for a in anchors}
    bm = R['benchmark']
    primary_id = bm.get('primary_anchor_id')
    if not anchors:
        raise SystemExit('research.json 的 market.spot_anchors 为空：至少需要一条同日市场参考价。\n'
                         '若确实拿不到，请把缺口写进 gaps，并把 quote 标为"无市场参考"，不要编造参考价。')
    if primary_id not in by_id:
        raise SystemExit('benchmark.primary_anchor_id="%s" 在 market.spot_anchors 中不存在。\n可用 ID：%s\n'
                         '（空白模板必须先填入真实参考价，再把 ID 填到 primary_anchor_id）'
                         % (primary_id, ', '.join(by_id) or '（无）'))
    primary = by_id[primary_id]
    intervals = {}
    for k, v in bm['interval_by_target'].items():
        intervals[k] = dict(v)

    # ---------------- 3. 偏离
    # 不含税靶心复用同口径（同交付）的含税参考区间，按 (1+VAT) 折算，避免"无同口径参考价"假缺口
    vat = float(spec.get('vat_rate', 0.13))
    for key in list(intervals):
        tax, deliv = key.split('|')
        if tax == 'excluded' and key not in intervals and ('included|' + deliv) in intervals:
            pass
    if 'excluded|ex_works' not in intervals and intervals.get('included|ex_works', {}).get('center'):
        src_iv = intervals['included|ex_works']
        derived = {}
        for k in ('center', 'low', 'high'):
            v = src_iv.get(k)
            derived[k] = None if v is None else round(v / (1 + vat), 2)
        derived.update({
            'interval_type': src_iv.get('interval_type', 'range'),
            'confidence': src_iv.get('confidence'),
            'basis': '不含税出厂 = 含税出厂参考区间 ÷ (1 + %.0f%%)，由「%s」折算' % (vat * 100, src_iv.get('basis', '')[:40]),
            'caveat': src_iv.get('caveat'),
            'derived_from': 'included|ex_works',
        })
        intervals['excluded|ex_works'] = derived
    targets = []
    for key in ('included|ex_works', 'excluded|ex_works', 'included|delivered', 'excluded|delivered'):
        tax, deliv = key.split('|')
        qv = norm[key]['value']
        iv = intervals.get(key)
        row = {
            'target': key,
            'target_label': ('含税' if tax == 'included' else '不含税') + ('出厂' if deliv == 'ex_works' else '到厂'),
            'quote_value': qv,
            'quote_formula': norm[key]['formula'],
            'quote_gap': norm[key].get('gap_reason'),
            'anchor': iv,
            'comparable': False,
            'status': '',
        }
        if qv is None:
            row['status'] = '报价靶心缺失'
            row['reason'] = norm[key].get('gap_reason')
        elif iv is None or iv.get('center') is None:
            row['status'] = '无同口径参考价'
            row['reason'] = '未取得与「%s」完全同口径的市场参考价' % row['target_label']
        else:
            dev = common.deviation(qv, {'center': iv['center'], 'low': iv['low'], 'high': iv['high'],
                                        'interval_type': iv.get('interval_type', 'range')})
            row.update(dev)
            row['status'] = '可比'
            row['comparability_note'] = bm.get('interval_method', '')
        targets.append(row)

    # 规格不可比的并列展示（工业级 vs 聚酯级），不出偏离
    spec_mismatch = {
        'quote_spec': q.get('grade_claimed'),
        'market_spec': primary.get('spec'),
        'message': '供应商报价为「%s」，市场参考价为「%s」：含量、等级口径不一致，两者不能直接相减。'
                   % (q.get('grade_claimed'), primary.get('spec')),
        'rule': '按 SKILL.md 第 3 步，规格不一致时只并列展示并标注不可比，不输出偏离金额。',
    }

    # ---------------- 4. 历史分位
    sfiles = R['market'].get('series_files') or {}
    s_ppi = _series(base, sfiles['ppi_daily_1y']) if sfiles.get('ppi_daily_1y') else None
    s_fut = _series(base, sfiles['futures_daily_3y']) if sfiles.get('futures_daily_3y') else None
    ppi_pts = (s_ppi or {}).get('points') or []
    fut_pts = (s_fut or {}).get('points') or []

    windows_def = [
        ('3m', 'spot_snapshots', 90, 8),
        ('1y', 'ppi_daily_1y', 365, 60),
        ('1y_fut', 'futures_daily_3y', 365, 60),
        ('3y', 'futures_daily_3y', 1095, 60),
    ]
    snap = R['market'].get('spot_series_3m') or []
    snap_pts = [{'d': x['date'], 'v': x['value']} for x in snap]
    # 期货序列取收盘价 c；指数/快照序列取 v
    fut_pts = [{'d': p['d'], 'v': p['c'], 'h': p.get('h'), 'l': p.get('l')} for p in fut_pts]

    pct_rows = []
    for wid, sid, days, minpts in windows_def:
        if sid == 'spot_snapshots':
            pts, meta_s, quote_proxy = snap_pts, {'name': '隆众 华东自提价（逐日快照）', 'unit': '元/吨', 'freq': '逐交易日', 'tax': '含税', 'spec': '聚酯级 含量≥99.9%', 'region': '华东（张家港）'}, None
            # 用该窗口的代表价：最后一日快照价
            quote_proxy = ('anchor', 'LZ-2026-10-19-0930', primary['value'])
        elif sid == 'ppi_daily_1y':
            pts, meta_s = ppi_pts, (s_ppi or {}).get('meta', {})
            quote_proxy = ('quote', 'included|ex_works', norm['included|ex_works']['value'])
        else:
            pts, meta_s = fut_pts, (s_fut or {}).get('meta', {})
            quote_proxy = ('quote', 'included|ex_works', norm['included|ex_works']['value'])
        st = common.window_stats(pts, days, asof, minpts)
        row = {'window': wid, 'series_id': sid, 'series_name': meta_s.get('name'), 'unit': '元/吨',
               'freq': meta_s.get('freq'), 'tax': meta_s.get('tax'), 'spec': meta_s.get('spec'),
               'region': meta_s.get('region'), 'days': days, 'ok': st.get('ok', False)}
        # 注意：期货序列不含税，报价需换算到不含税
        if sid == 'futures_daily_3y':
            qv = norm['excluded|ex_works']['value']
            row['compared_value_label'] = '供应商报价（不含税出厂折算）'
        elif quote_proxy[0] == 'anchor':
            qv = quote_proxy[2]
            row['compared_value_label'] = '同日华东自提主流价'
        else:
            qv = norm['included|ex_works']['value']
            row['compared_value_label'] = '供应商报价（含税出厂）'
        row['compared_value'] = qv
        if st.get('ok'):
            row.update({'n': st['n'], 'start': st['start'], 'end': st['end'], 'low': st['low'],
                        'high': st['high'], 'median': st['center'],
                        'quote_pctile': common.percentile_of([p['v'] for p in pts
                                                              if st['start'] <= p['d'] <= st['end']], qv)[0],
                        'method': 'P = (#<X + 0.5×#=X) / n × 100%'})
            # 分位对应的价格（同期同值附近的样本区间）
        else:
            row['gap'] = st.get('gap')
            row['gap_reason'] = R['market'].get('series_meta', {}).get(sid, {}).get('note', '')
            row['n'] = st.get('n')
        pct_rows.append(row)

    # 分位条所需的同期曲线（1y 用指数；期货按月抽样）
    hist = {}
    if ppi_pts:
        st = common.window_stats(ppi_pts, 365, asof, 60)
        if st.get('ok'):
            hist['ppi_1y'] = [{'d': p['d'], 'v': p['v']} for p in ppi_pts if st['start'] <= p['d'] <= asof]
    if fut_pts:
        for days, key in ((90, 'fut_3m'), (365, 'fut_1y'), (1095, 'fut_3y')):
            st = common.window_stats(fut_pts, days, asof, 30)
            if st.get('ok'):
                hist[key] = [{'d': p['d'], 'v': p['v'], 'h': p.get('h'), 'l': p.get('l')}
                             for p in fut_pts if st['start'] <= p['d'] <= asof]

    # 年度锚点对比
    anchors_y = spec.get('annual_anchors') or []
    anchor_rows = []
    for a in anchors_y:
        row = dict(a)
        row['quote_vs'] = _anchor_compare(norm['included|ex_works']['value'], a)
        anchor_rows.append(row)

    # ---------------- 5. 年化涨跌（事实）与近期变化
    trend = {}
    if fut_pts:
        trend['fut'] = _trend(fut_pts, asof, 'v')
    if ppi_pts:
        trend['ppi'] = _trend(ppi_pts, asof, 'v')

    # ---------------- 6. 口径矩阵
    comp = R.get('comparability') or []

    out = {
        'meta': R['meta'], 'spec': {'family': spec.get('family'), 'spec_terms': list((spec.get('spec_terms') or {}).keys())},
        'quote': q, 'quote_norm': norm, 'quote_meta': meta,
        'primary_anchor': primary, 'anchors': anchors,
        'enterprise_prices': R['market'].get('enterprise_prices') or [],
        'spot_series_3m': snap,
        'futures_reference': R['market'].get('futures_reference'),
        'transport': R['market'].get('transport'),
        'targets': targets, 'spec_mismatch': spec_mismatch,
        'percentiles': pct_rows, 'history': hist,
        'annual_anchors': anchor_rows, 'trend': trend,
        'comparability': comp, 'events': spec.get('events') or [],
        'gaps': R.get('gaps') or [], 'evidence_summary': R.get('evidence_summary') or {},
        'series_meta': (s_ppi or {}).get('meta') and {'ppi': (s_ppi or {}).get('meta')},
    }
    return out


def _anchor_compare(qv, a):
    if qv is None:
        return None
    pts = []
    for k, lab in (('value_low', '年度低点/下沿'), ('value_high', '年度高点/上沿'),
                   ('value_avg', '年均价'), ('value_end', '年末价'), ('value_start', '年初价')):
        if a.get(k) is not None:
            pts.append({'label': lab, 'value': a[k], 'diff': round(qv - a[k], 2),
                        'diff_pct': round((qv - a[k]) / a[k] * 100, 2)})
    return pts


def _trend(pts, asof, valkey):
    import datetime
    d0 = datetime.date.fromisoformat(asof)
    series = [{'d': p['d'], 'v': p[valkey]} for p in pts if p['d'] <= asof]
    if not series:
        return {}
    last = series[-1]
    out = {'last': last}
    for days, lab in ((30, '30d'), (90, '90d'), (365, '1y'), (1095, '3y')):
        cut = (d0 - datetime.timedelta(days=days)).isoformat()
        w = [p for p in series if p['d'] >= cut]
        if w:
            p0 = w[0]
            out[lab] = {'from': p0['d'], 'from_v': p0['v'], 'to': last['v'],
                        'diff': round(last['v'] - p0['v'], 2),
                        'pct': round((last['v'] - p0['v']) / p0['v'] * 100, 2)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('research')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    m = build(a.research)
    common.dump_json(m, a.out)
    print('OK -> %s' % a.out)
    for t in m['targets']:
        print('  %-16s quote=%s center=%s dev=%s (%s) status=%s' % (
            t['target_label'], t['quote_value'], (t['anchor'] or {}).get('center'),
            t.get('dev_center'), t.get('dev_center_pct'), t['status']))
    for p in m['percentiles']:
        print('  %-8s %-18s n=%s pct=%s %s' % (p['window'], p['series_id'], p.get('n'),
                                               p.get('quote_pctile'), p.get('gap', '')))


if __name__ == '__main__':
    main()
