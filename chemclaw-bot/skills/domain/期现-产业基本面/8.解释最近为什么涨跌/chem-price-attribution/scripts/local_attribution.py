# -*- coding: utf-8 -*-
"""local_attribution.py —— 框选区间的局部归因。

需求原文："用户也可以框选一段区间做局部归因"。

做法（与整段归因保持同一套纪律）：
  * 区间内逐因子重算"同期变化 → z 值 → 方向一致性"；
  * 时间吻合：把事件按"落在区间内 / 区间前 N 个交易日内"分档；
  * 输出与整段归因相同的四级证据标签，绝不因为"区间小"就放宽标准；
  * 同时输出反证清单：区间内方向相反且显著的因子，明确写"该因子不能解释本区间"。

用法：
  python local_attribution.py --case case.json --from 2026-09-28 --to 2026-10-19 \
      --out build/local_0928_1019.json
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import align_series as A  # noqa: E402

LEVEL_W = {'E1': 4, 'E2': 3, 'E3': 2, 'E4': 1}


def attribute(case, base_dir, start, end, lead_window=3, events=None):
    spot_pts, _ = A.load_points(case['spot'], base_dir)
    fut_pts = A.load_points(case['futures'], base_dir)[0] if case.get('futures') else []
    s_chg = A.window_stats(spot_pts, start, end, '2018-01-01')
    f_chg = A.window_stats(fut_pts, start, end, '2018-01-01') if fut_pts else {'ok': False}
    if not s_chg.get('ok'):
        return {'ok': False, 'reason': '区间内现货无可比观测'}
    spot_dir = 'up' if s_chg['pct_change'] > 0 else 'down'
    price_dates = [d for d, _ in fut_pts if start <= d <= end]

    rows = []
    for drv in case['drivers']:
        for spc in drv.get('series', []):
            pts, err = A.load_points(spc, base_dir)
            st = A.window_stats(pts, start, end, '2018-01-01')
            if not st.get('ok'):
                rows.append({'driver': drv['name'], 'group': drv['group'], 'metric': spc['name'],
                             'level': 'E4', 'pct': None, 'z': None, 'dir': None,
                             'reason': '区间内无可用数据', 'src': spc.get('src_url', '')})
                continue
            v = st['pct_change']
            d = 'up' if v > 0 else ('down' if v < 0 else 'flat')
            z = st.get('z')
            sig = z is not None and abs(z) >= 1.0
            if d == spot_dir and sig:
                lv, why = 'E1', '区间内 %+.2f%%（z=%+.2f），方向与价格一致且显著' % (v, z)
            elif d != spot_dir and sig:
                lv, why = 'E4', '区间内 %+.2f%%（z=%+.2f），方向与价格相反 → 不能解释本区间' % (v, z)
            elif d == spot_dir:
                lv, why = 'E3', '区间内 %+.2f%%（z=%+.2f），方向一致但幅度不显著' % (v, z if z is not None else 0)
            else:
                lv, why = 'E4', '区间内 %+.2f%%，方向与价格相反' % v
            rows.append({'driver': drv['name'], 'group': drv['group'], 'metric': spc['name'],
                         'level': lv, 'pct': round(v, 2), 'z': round(z, 2) if z is not None else None,
                         'dir': d, 'reason': why, 'src': spc.get('src_url', '')})
        for m in drv.get('manual', []):
            rows.append({'driver': drv['name'], 'group': drv['group'], 'metric': m.get('k'),
                         'level': m.get('grade', 'E3'), 'pct': None, 'z': None,
                         'dir': m.get('dir'), 'reason': m.get('v'), 'src': m.get('src', '')})

    # 事件：区间内 / 区间前 lead_window 个交易日
    evs = []
    all_ev = events if events is not None else C.jload(os.path.join(base_dir, case['events']['file']))
    for e in all_ev:
        inside = start <= e['date'] <= end
        pre = False
        if not inside and price_dates:
            import bisect
            i = bisect.bisect_left(price_dates, start)
            lo = price_dates[max(0, i - lead_window)]
            pre = lo <= e['date'] < start
        if inside or pre:
            evs.append({'date': e['date'], 'title': e['title'], 'level': e.get('evidence', 'E3'),
                        'dir': e.get('direction'), 'magnitude': e.get('magnitude'),
                        'timing': '区间内' if inside else '区间前 %d 个交易日内' % lead_window,
                        'src': e.get('src'), 'url': e.get('url'), 'group': e.get('group')})
    evs.sort(key=lambda x: x['date'])

    rows.sort(key=lambda x: (-LEVEL_W[x['level']], -(abs(x['z']) if x['z'] else 0)))
    counters = [r for r in rows if r['level'] == 'E4' and r['dir'] in ('up', 'down') and r['dir'] != spot_dir]
    return {
        'ok': True, 'start': start, 'end': end,
        'spot': {'pct': round(s_chg['pct_change'], 2), 'abs': round(s_chg['abs_change'], 2),
                 'from': round(s_chg['start_value'], 2), 'to': round(s_chg['end_value'], 2),
                 'from_date': s_chg['start_date'], 'to_date': s_chg['end_date']},
        'futures': {'pct': round(f_chg['pct_change'], 2)} if f_chg.get('ok') else None,
        'direction': spot_dir,
        'factors': rows, 'events': evs, 'counter_evidence': counters,
        'summary': '区间内 %d 个因子有数据、%d 个因子无数据；方向相反可作为反证的 %d 个。' % (
            sum(1 for r in rows if r['pct'] is not None), sum(1 for r in rows if r['pct'] is None), len(counters)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True)
    ap.add_argument('--from', dest='d0', required=True)
    ap.add_argument('--to', dest='d1', required=True)
    ap.add_argument('--lead', type=int, default=3)
    ap.add_argument('--out', default='build/local.json')
    a = ap.parse_args()
    case = C.jload(a.case)
    base = os.path.dirname(os.path.abspath(a.case))
    res = attribute(case, base, a.d0, a.d1, a.lead)
    C.jdump(res, a.out)
    if not res.get('ok'):
        print('失败：', res.get('reason'))
        return 1
    print('%s → %s 现货 %+.2f%%（%s → %s）' % (res['start'], res['end'], res['spot']['pct'],
                                            res['spot']['from'], res['spot']['to']))
    print(res['summary'])
    for r in res['factors']:
        if r['level'] in ('E1', 'E2'):
            print('  %s %-20s %s' % (r['level'], r['driver'][:20], r['reason']))
    print('  区间内/临近事件 %d 条' % len(res['events']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
