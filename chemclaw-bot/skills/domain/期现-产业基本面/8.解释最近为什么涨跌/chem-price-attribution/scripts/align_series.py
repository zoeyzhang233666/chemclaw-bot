# -*- coding: utf-8 -*-
"""align_series.py —— 多维产业指标的时间对齐引擎。

核心纪律：
  * 一切对齐都要"注明口径"：周度指标对齐到其**覆盖周的最后交易日**（或声明的前置/滞后），
    月度指标对齐到**发布日**（不是所属月份），日度指标直接对齐。
  * 任何缺失一律输出 null + reason，绝不插值。
  * 区间端点一律用"≤end 的最近一个观测"，并显式记录实际使用的日期（start_date / end_date）。

用法：
  python align_series.py --case case.json --phases phases.json --out build/aligned.json
"""
from __future__ import annotations

import argparse
import bisect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


# ------------------------------------------------------------------ 载入


def load_points(spec, base_dir):
    """spec: {file, date_col, value_col, unit, name} -> list[(date, value)] 升序；缺失值被剔除。"""
    path = os.path.join(base_dir, spec['file'])
    if not os.path.exists(path):
        return [], 'file-missing'
    if path.lower().endswith('.csv'):
        s = C.load_csv(path, spec.get('date_col', 'date'), spec.get('value_col', 'price'))
    else:
        s = C.load_json_series(path, spec.get('date_col', 'name'), spec.get('value_col', 'age'))
    pts = sorted(s.items())
    return pts, None


def point_at(pts, date):
    """取 ≤date 的最近观测，返回 (date, value)；无则 (None, None)。"""
    if not pts:
        return None, None
    ks = [p[0] for p in pts]
    i = bisect.bisect_right(ks, date) - 1
    return pts[i] if i >= 0 else (None, None)


def window_stats(points_list, start, end, history_start=None):
    """对"时点型"指标序列做窗口统计。

    返回 dict：first/last 值及其日期、绝对/相对变化、z 值、分位、观测数、缺失原因。
    z = (窗口末值 − 窗口初值) / 该指标"变化量"在其自身历史分布中的标准差。
    """
    d0, v0 = point_at(points_list, start)
    d1, v1 = point_at(points_list, end)
    n = sum(1 for d, _ in points_list if C.in_win(d, start, end))
    if v0 is None or v1 is None:
        return {'ok': False, 'reason': 'ND', 'n_obs': n}
    # 硬性纪律：区间内一个观测都没有，就不得报告"变化 0%"。否则缺失会被静默当成"没变化"。
    if n == 0 or d0 == d1:
        return {'ok': False, 'reason': '区间内无观测（最后一次观测为 %s，此后无数据）' % d0, 'n_obs': n,
                'last_obs_date': d0, 'last_obs_value': v0}
    deltas = of_deltas(points_list, start, end)
    z = C.zscore(deltas, v1 - v0) if deltas else None
    hist = [v for d, v in points_list if history_start is None or d >= history_start]
    return {
        'ok': True, 'n_obs': n,
        'start_date': d0, 'start_value': v0, 'end_date': d1, 'end_value': v1,
        'abs_change': v1 - v0,
        'pct_change': (v1 / v0 - 1) * 100 if v0 else None,
        'z': z,
        'pctile_end': C.pctile_rank(hist, v1),
        'hist_n': len(hist),
    }


def of_deltas(points_list, start, end):
    """构造"与窗口等长"的历史变化量分布：对每个可能起点，取等长窗口的首末差。"""
    if len(points_list) < 8:
        return []
    ks = [p[0] for p in points_list]
    i0 = bisect.bisect_right(ks, start) - 1
    i1 = bisect.bisect_right(ks, end) - 1
    span = max(1, i1 - i0)
    out = []
    for i in range(0, len(points_list) - span):
        out.append(points_list[i + span][1] - points_list[i][1])
    return out


def load_baseline(cur_file, extra_files, base_dir, contract):
    """基准合约的连续收盘序列（{date: close}）。

    月差必须用**同一对合约**逐日做差，否则合约换月会让 M1−M2 出现假跳变。
    """
    files = [(contract, cur_file)]
    for c, f in (extra_files or {}).items():
        files.append((c, f))
    for c, f in files:
        if c != contract:
            continue
        p = os.path.join(base_dir, f)
        if not os.path.exists(p):
            continue
        d = C.jload(p)
        # 形态 A：{合约: {日期: {close, oi}}}（逐合约全曲线文件）→ 先取到该合约
        # 形态 B：{日期: {close, oi}}（单合约文件）
        # 形态 C：[{date, close}, ...]（日线数组）
        if isinstance(d, dict) and d and isinstance(next(iter(d.values())), dict):
            first_key = next(iter(d))
            if not first_key[:1].isdigit():          # 形态 A
                d = d.get(contract, {})
        out = {}
        if isinstance(d, dict):
            for dt, v in d.items():
                try:
                    out[C._norm_date(dt)] = float(v.get('close') if isinstance(v, dict) else v)
                except (TypeError, ValueError, AttributeError):
                    continue
        else:
            for r in d:
                try:
                    out[C._norm_date(r.get('date'))] = float(r.get('close'))
                except (TypeError, ValueError, AttributeError):
                    continue
        return out
    return {}


def basis_series(spot_map, baseline, oi_map=None):
    """基差 = 现货 − 基准合约收盘（同一合约全期可比）。"""
    out = []
    for d in sorted(set(spot_map) & set(baseline)):
        out.append({'date': d, 'spot': spot_map[d], 'fut': baseline[d],
                    'basis': spot_map[d] - baseline[d],
                    'basis_pct': (spot_map[d] / baseline[d] - 1) * 100,
                    'oi': oi_map.get(d) if oi_map else None})
    return out


# ------------------------------------------------------------------ 期现结构

def load_curve(cur_file, extra_files, base_dir):
    """合约曲线：{contract: {date: {close, oi}}}"""
    curve = {}
    p = os.path.join(base_dir, cur_file)
    if os.path.exists(p):
        d = C.jload(p)
        for c, series in d.items():
            curve[c] = {}
            for dt, v in series.items():
                if isinstance(v, dict):
                    curve[c][C._norm_date(dt)] = v
                else:
                    curve[c][C._norm_date(dt)] = {'close': v, 'oi': None}
    for c, f in (extra_files or {}).items():
        q = os.path.join(base_dir, f)
        if os.path.exists(q):
            d = C.jload(q)
            curve[c] = {C._norm_date(k): v for k, v in d.items()}
    for c in curve:
        for dt, v in curve[c].items():
            v.setdefault('oi', None)
    return curve


def front_contract(curve, date):
    """按当日持仓量最大的合约（不采用"名义主连"，避免切换日错价）。"""
    best, boi = None, -1
    for c, s in curve.items():
        v = s.get(date)
        if v and v.get('oi') and v['oi'] > boi and v.get('close'):
            best, boi = c, v['oi']
    return best


def curve_at(curve, date, min_oi=500):
    """取某一日"当日在交易"的合约集合。

    只保留有实际成交（持仓 ≥ min_oi）的合约，避免把已到期/未挂牌的空壳报价带进曲线比较。
    """
    out = {}
    for c, s in curve.items():
        v = s.get(date)
        if v and v.get('close') and (v.get('oi') or 0) >= min_oi:
            out[c] = v
    return out


def struct_metrics(curve, spot, date):
    """期现结构：基差、月差、期限结构斜率（只在同日有效合约之间比较）。"""
    live = curve_at(curve, date)
    if not live:
        return {'ok': False, 'reason': 'ND'}
    c = max(live, key=lambda k: live[k].get('oi') or 0)          # 持仓量最大合约
    front = live[c]['close']
    codes = sorted(live, key=lambda x: _contract_month(x))
    idx = codes.index(c)
    nxt = codes[idx + 1] if idx + 1 < len(codes) else None
    far = codes[idx + 2] if idx + 2 < len(codes) else None
    out = {
        'ok': True, 'date': date, 'front_contract': c, 'front': front,
        'spot': spot.get(date),
        'curve': {x: live[x]['close'] for x in codes},
        'oi': {x: live[x].get('oi') for x in codes},
    }
    if out['spot'] is not None:
        out['basis'] = out['spot'] - front
        out['basis_pct'] = (out['spot'] / front - 1) * 100
    if nxt:
        out['next_contract'] = nxt
        out['m1m2'] = front - live[nxt]['close']      # 近−远：正值 = 近月升水（Back）
        out['m1m2_pct'] = (front / live[nxt]['close'] - 1) * 100
    if far:
        out['far_contract'] = far
        out['m1m3'] = front - live[far]['close']
        out['structure'] = 'Back' if out.get('m1m3', 0) > 0 else 'Contango'
    return out


def _contract_month(code):
    # 形如 MA2611 -> 2026*12+11
    digits = ''.join(ch for ch in code if ch.isdigit())
    if len(digits) >= 4:
        return int(digits[:2]) * 12 + int(digits[2:4])
    return 9999


# ------------------------------------------------------------------ 事件窗口


def event_window_change(points_list, event_date, win_days):
    """事件后 win_days 个自然日内，指标从"事件前最后观测"到"事件后观测"的变化。"""
    before = point_at(points_list, event_date)
    after_date = (C.d2(event_date) + C.dt.timedelta(days=win_days)).isoformat()
    ks = [p[0] for p in points_list]
    i = bisect.bisect_right(ks, event_date) - 1
    j = bisect.bisect_right(ks, after_date)
    seg = points_list[i + 1:j]
    if not seg:
        return None
    d, v = seg[-1]
    return {'from_date': before[0], 'from_value': before[1], 'to_date': d, 'to_value': v,
            'abs_change': (v - before[1]) if before[1] is not None else None,
            'pct_change': ((v / before[1] - 1) * 100) if before[1] else None}


def build(case, base_dir, phases=None):
    """主流程：把 case.json 的驱动与区间拼成一份对齐结果。"""
    win = case['window']
    start, end = win['start'], win['end']
    hist_start = win.get('history_start') or '2018-01-01'

    spot_spec = case['spot']
    spot_pts, err = load_points(spot_spec, base_dir)
    spot = dict(spot_pts)

    fut = {}
    fut_pts = []
    if case.get('futures'):
        fut_pts, err2 = load_points(case['futures'], base_dir)
        fut = dict(fut_pts)

    curve = {}
    if case.get('futures_front'):
        curve = load_curve(case['futures_front']['file'], case['futures_front'].get('extra', {}), base_dir)

    # 1) 基准品种本身
    res = {'window': win, 'spot': spot_spec, 'futures': case.get('futures'),
           'layers': {}}
    res['layers']['price'] = {
        'spot': window_stats(spot_pts, start, end, hist_start),
        'futures': window_stats(fut_pts, start, end, hist_start) if fut_pts else {'ok': False, 'reason': 'ND'},
    }

    # 2) 各驱动
    events = C.jload(os.path.join(base_dir, case['events']['file'])) if case.get('events') else []
    for drv in case['drivers']:
        layer = {'id': drv['id'], 'name': drv['name'], 'group': drv['group'],
                 'sign_expected': drv.get('sign'), 'logic': drv.get('logic'), 'series': [],
                 'events': [e for e in events if (e.get('driver') == drv['id'])],
                 'manual': []}
        for spc in drv.get('series', []):
            pts, e = load_points(spc, base_dir)
            if e:
                layer['series'].append({'id': spc['id'], 'name': spc['name'], 'ok': False, 'reason': e})
                continue
            stt = window_stats(pts, start, end, hist_start)
            stt.update({'id': spc['id'], 'name': spc['name'], 'unit': spc.get('unit'),
                        'tax': spc.get('tax'), 'src': spc.get('src'), 'src_url': spc.get('src_url'),
                        'note': spc.get('note')})
            # 事件窗口
            evs = []
            for ev in layer['events']:
                cw = event_window_change(pts, ev['date'], case.get('align', {}).get('event_window_days', 5))
                evv = dict(ev)
                evv['series_change'] = cw
                evs.append(evv)
            if evs:
                layer.setdefault('events_with_series', []).extend(
                    [x for x in evs if x['series_change']])
            layer['series'].append(stt)
        # 人工录入的窗口指标（调研/报告披露的周度、月度值）
        for m in drv.get('measures', []):
            layer['manual'].append(dict(m))
        res['layers'][drv['id']] = layer

    # 3) 期现结构
    struct = {'ok': False}
    if curve:
        f_start = struct_metrics(curve, spot, start)
        f_end = struct_metrics(curve, spot, end)
        pts = []
        for d in sorted({x for s in curve.values() for x in s}):
            if C.in_win(d, start, end) and spot.get(d):
                m = struct_metrics(curve, spot, d)
                if m.get('ok') and 'basis' in m:
                    pts.append((d, m))
        struct = {'ok': True, 'start': f_start, 'end': f_end, 'daily': pts}
        if pts:
            basis_vals = [p[1]['basis'] for p in pts]
            struct['basis_min'] = min(basis_vals)
            struct['basis_max'] = max(basis_vals)
            struct['basis_min_date'] = pts[basis_vals.index(min(basis_vals))][0]
            struct['basis_max_date'] = pts[basis_vals.index(max(basis_vals))][0]
            m12 = [p[1]['m1m2'] for p in pts if 'm1m2' in p[1]]
            if m12:
                struct['m1m2_min'] = min(m12)
                struct['m1m2_max'] = max(m12)

        # 基准合约口径：同一合约全期可比，避免换月造成的假跳变
        bcode = case.get('meta', {}).get('baseline_contract')
        if bcode:
            bf = case['futures_front']
            base_map = load_baseline(bf['file'], bf.get('extra', {}), base_dir, bcode)
            if base_map:
                bs = basis_series(spot, base_map, None)
                bs = [x for x in bs if C.in_win(x['date'], start, end)]
                if bs:
                    bvals = [x['basis'] for x in bs]
                    imax = bvals.index(max(bvals))
                    imin = bvals.index(min(bvals))
                    struct['baseline_contract'] = bcode
                    struct['baseline'] = {
                        'daily': bs,
                        'start': bs[0], 'end': bs[-1],
                        'basis_max': max(bvals), 'basis_max_date': bs[imax]['date'],
                        'basis_min': min(bvals), 'basis_min_date': bs[imin]['date'],
                    }
                # 同一对合约的月差（如 M2611−M2612），全期可比
                pair = case.get('meta', {}).get('spread_pair')
                if pair:
                    f1 = load_baseline(bf['file'], bf.get('extra', {}), base_dir, pair[0])
                    f2 = load_baseline(bf['file'], bf.get('extra', {}), base_dir, pair[1])
                    sp = []
                    for d in sorted(set(f1) & set(f2)):
                        if C.in_win(d, start, end):
                            sp.append({'date': d, 'near': f1[d], 'far': f2[d], 'spread': f1[d] - f2[d]})
                    if sp:
                        svals = [x['spread'] for x in sp]
                        struct['spread'] = {'pair': pair, 'daily': sp,
                                            'start': sp[0], 'end': sp[-1],
                                            'min': min(svals), 'max': max(svals)}
    res['structure'] = struct

    # 4) 阶段
    if phases:
        res['phases'] = phase_layers(phases, case, base_dir)
    return res


def phase_layers(phases, case, base_dir):
    """每个阶段重新算一次全部驱动，供"局部归因研究"使用。"""
    out = []
    specs = [('spot', case['spot'])]
    if case.get('futures'):
        specs.append(('futures', case['futures']))
    loaded = {}
    for k, s in specs:
        loaded[k] = load_points(s, base_dir)[0]
    for drv in case['drivers']:
        for spc in drv.get('series', []):
            loaded[spc['id']] = load_points(spc, base_dir)[0]
    for ph in phases:
        row = {'start_date': ph['start_date'], 'end_date': ph['end_date'],
               'chg_pct': ph.get('chg_pct'), 'drivers': {}}
        for k, pts in loaded.items():
            row['drivers'][k] = window_stats(pts, ph['start_date'], ph['end_date'], '2018-01-01')
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True)
    ap.add_argument('--phases', default=None)
    ap.add_argument('--out', default='build/aligned.json')
    ap.add_argument('--base-dir', default=None, help='数据根目录（默认 case.json 所在目录）')
    a = ap.parse_args()
    case = C.jload(a.case)
    base = a.base_dir or os.path.dirname(os.path.abspath(a.case))
    phases = C.jload(a.phases)['phases'] if a.phases else None
    res = build(case, base, phases)
    C.jdump(res, a.out)
    print('对齐完成 ->', a.out)
    pl = res['layers']['price']
    print('  现货 %s -> %s : %+.2f%%' % (pl['spot'].get('start_date'), pl['spot'].get('end_date'),
                                       pl['spot'].get('pct_change') or 0))
    print('  期货 %s -> %s : %+.2f%%' % (pl['futures'].get('start_date'), pl['futures'].get('end_date'),
                                       pl['futures'].get('pct_change') or 0))
    for k, L in res['layers'].items():
        if k == 'price':
            continue
        ss = ['%s %s' % (s['name'][:10], ('%+.2f%%' % s['pct_change']) if s.get('pct_change') is not None else 'ND')
              for s in L['series']]
        print('  [%s] %s | %s | 事件 %d 条' % (L['group'], L['name'], '; '.join(ss) or '无序列', len(L['events'])))


if __name__ == '__main__':
    main()
