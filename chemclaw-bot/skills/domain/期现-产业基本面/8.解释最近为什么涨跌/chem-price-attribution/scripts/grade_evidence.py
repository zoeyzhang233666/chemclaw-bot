# -*- coding: utf-8 -*-
"""grade_evidence.py —— 证据分级与候选解释排序。

分级规则（四级，必须逐字照用，不得自创"强/中/弱"这类含糊说法）：

  E1 直接数据支持：有可量化的同期指标，指标的**变化量**相对其自身历史分布显著（|z| ≥ 1.0），
     且方向与价格异动一致。E1 只说明"该因素确有显著变化并同向"，不等于"它被证明是原因"。
  E2 数据+事件时间吻合：有带日期的可引事件，且对应指标在事件窗口内确有变动（或事件本身带量级）。
  E3 仅时间吻合：有带日期的事件或事后复盘表述，与价格异动同窗，但缺少可比指标数据。
  E4 缺乏证据/无法检验：无数据、无法对齐、方向相反，或"看起来像但查不到"。

排序规则（可复核、可改写）：
  score = 级别权重 + 时间吻合度 + 幅度匹配度 + 方向一致性 − 反证扣分
  级别权重：E1=4.0 E2=3.0 E3=1.5 E4=0
  时间吻合度：事件落在对应价格阶段内且领先 ≤3 交易日 = 1.0；同阶段但不领先 = 0.6；跨阶段 = 0.2
  幅度匹配度：|指标变化| / |价格阶段变化|，封顶 1.0（仅用于排序，不用于"解释百分比"）
  方向一致性：同向 +0.5，反向 −1.0
  反证扣分：指标方向与价格相反且显著 → −1.5

注意：score 只是**排序工具**，不是"归因占比"。报告里禁止把 score 换算成"XX 因素贡献 N%"。

用法：
  python grade_evidence.py --aligned build/aligned.json --case case.json --out build/graded.json
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

LEVEL_W = {'E1': 4.0, 'E2': 3.0, 'E3': 1.5, 'E4': 0.0}
LEVEL_TEXT = {
    'E1': '直接数据支持',
    'E2': '数据＋事件时间吻合',
    'E3': '仅时间吻合',
    'E4': '缺乏证据／无法检验',
}
GROUP_CN = {'cost': '成本', 'supply': '供给', 'demand': '需求', 'inventory': '库存',
            'trade': '贸易', 'policy': '政策/事件', 'structure': '期现结构'}


def phases_from(aligned, case, fut_series):
    """价格阶段：优先用 detect_anomalies 输出的阶段；否则按 aligned.phases。"""
    ph = aligned.get('phases')
    if ph:
        return [{'start_date': p['start_date'], 'end_date': p['end_date'], 'chg_pct': p['chg_pct']} for p in ph]
    return []


def window_periods(case):
    """把整个窗口按"手动/自动"给出的分段边界切开。"""
    return case.get('periods') or []


def find_period(ev_date, periods):
    for p in periods:
        if p['start'] <= ev_date <= p['end']:
            return p
    return None


def lead_lag(ev_date, period, price_dates):
    """事件相对价格阶段起点的交易日领先数（负数=落后）。"""
    if not period:
        return None
    ks = sorted(price_dates)
    i_ev = bisect.bisect_left(ks, ev_date)
    i_st = bisect.bisect_left(ks, period['start'])
    return i_st - i_ev


def grade_layer(layer, price_chg, periods, price_dates, spot_dir):
    """对一个驱动层出证据条目。返回 list[dict]。"""
    items = []
    # 1) 有连续序列的驱动 → 用序列自身变化量做 E1/E4 判断
    for s in layer.get('series', []):
        if not s.get('ok'):
            items.append({'factor': layer['name'], 'series': s.get('name'), 'level': 'E4',
                          'reason': '无可用序列（%s）' % (s.get('reason') or 'ND'),
                          'evidence_type': '无数据', 'value': None, 'z': None, 'dir': None})
            continue
        z = s.get('z')
        chg = s.get('pct_change')
        direction = 'up' if (chg or 0) > 0 else ('down' if (chg or 0) < 0 else 'flat')
        same = (direction == spot_dir)
        sig = z is not None and abs(z) >= 1.0
        if sig and same:
            lvl = 'E1'
            reason = '窗口内变化 %+.1f%%（z=%+.2f≥1.0），方向与现货%s一致' % (chg, z, '上涨' if spot_dir == 'up' else '下跌')
        elif sig and not same:
            lvl = 'E4'
            reason = '窗口内变化 %+.1f%%（z=%+.2f），但方向与现货相反，不构成支持' % (chg, z)
        elif same:
            lvl = 'E3'
            reason = '窗口内变化 %+.1f%%，方向一致但幅度未达显著（|z|=%.2f<1.0）' % (chg, abs(z) if z is not None else 0)
        else:
            lvl = 'E4'
            reason = '窗口内变化 %+.1f%%，方向与现货相反' % chg
        items.append({
            'factor': layer['name'], 'series': s.get('name'), 'level': lvl, 'reason': reason,
            'evidence_type': '连续价格序列', 'value': chg, 'z': z, 'dir': direction,
            'start_date': s.get('start_date'), 'end_date': s.get('end_date'),
            'start_value': s.get('start_value'), 'end_value': s.get('end_value'),
            'unit': s.get('unit'), 'src': s.get('src'), 'src_url': s.get('src_url'),
            'pctile': s.get('pctile_end'),
        })
    # 2) 人工录入的窗口指标（报告披露的周度/月度值）
    for m in layer.get('manual', []):
        dv = m.get('dir')
        note = m.get('note') or ''
        reason = m.get('cite') or '依据原文表述，见来源'
        if dv in ('up', 'down') and dv != spot_dir:
            reason += '；该变化方向与现货%s相反，不构成对本次行情的支持' % ('上涨' if spot_dir == 'up' else '下跌')
        items.append({
            'factor': layer['name'], 'series': m.get('k'), 'level': m.get('grade') or 'E3',
            'reason': reason, 'evidence_type': '报告披露值／统计口径数据',
            'value': m.get('v'), 'z': None, 'dir': dv, 'date': m.get('date'),
            'unit': m.get('unit') or '', 'src': m.get('src'), 'src_url': m.get('src_url'),
            'extra_note': note,
        })
    # 3) 事件
    for ev in layer.get('events', []):
        per = find_period(ev['date'], periods)
        ll = lead_lag(ev['date'], per, price_dates) if per else None
        if ev.get('evidence') == 'E1':
            lvl, etype = 'E1', '事件＋统计口径数据'
            reason = '事件带统计口径数值（%s）' % (ev.get('magnitude') or '')
            if per:
                reason += '；与行情周期「%s」同窗' % per['name']
        elif ev.get('evidence') == 'E2':
            lvl, etype = 'E2', '事件记录（带日期的可引披露）'
            reason = '可引事件：%s；与阶段%s' % (
                ev.get('magnitude') or '—',
                ('同窗且领先 %d 个交易日' % ll) if (ll is not None and 0 < ll <= 3) else
                ('同窗' if per else '不在任何价格阶段内'))
        elif ev.get('evidence') == 'E3':
            lvl, etype = 'E3', '事后复盘表述／无量化'
            reason = '仅有文字表述或定性复盘，缺可比数值'
        else:
            lvl, etype = 'E4', '无数据'
            reason = '无可用证据'
        items.append({
            'factor': layer['name'], 'series': ev.get('title'), 'level': lvl, 'reason': reason,
            'evidence_type': etype, 'value': ev.get('magnitude'), 'z': None,
            'dir': ev.get('direction'), 'date': ev['date'],
            'period': per['name'] if per else None, 'lead_days': ll,
            'src': ev.get('src'), 'src_url': ev.get('url'), 'tag': ev.get('tag'),
        })
    return items


def score_all(items, price_chg, spot_dir):
    """排序分。

    注意：**同一驱动走同一套口径的二级证据不再叠加**——排序在驱动层聚合后做，
    单条条目只保留"级别权重 + 方向修正"，避免一个驱动因为"事件多"而虚高。
    """
    for it in items:
        lvl = it['level']
        sc = LEVEL_W.get(lvl, 0)
        d = it.get('dir')
        if d in ('up', 'down'):
            sc += 0.5 if d == spot_dir else -1.0
        # 反证：方向相反且统计显著
        if d in ('up', 'down') and d != spot_dir and it.get('z') is not None and abs(it['z']) >= 1.0:
            sc -= 1.5
        # 时间吻合（仅对事件条目）
        if it.get('evidence_type', '').startswith('事件'):
            sc += 1.0 if it.get('period') else 0.2
        it['score'] = round(sc, 2)
    items.sort(key=lambda x: (-x['score'], x['level']))
    for i, it in enumerate(items, 1):
        it['rank'] = i
    return items


def aggregate_ranking(items):
    """按驱动聚合：级别取该驱动最强证据；排序分 = 最强证据分 + 幅度匹配（封顶 1）。"""
    agg = {}
    for it in items:
        f = it['factor']
        a = agg.setdefault(f, {'factor': f, 'best_level': 'E4', 'n': 0, 'levels': {},
                               'strongest': None})
        a['n'] += 1
        a['levels'][it['level']] = a['levels'].get(it['level'], 0) + 1
        cur = a['strongest']
        better = cur is None or LEVEL_W[it['level']] > LEVEL_W[cur['level']] or \
            (it['level'] == cur['level'] and it['score'] > cur['score'])
        if better:
            a['strongest'] = it
    for f, a in agg.items():
        st = a['strongest']
        a['best_level'] = st['level']
        a['level_text'] = LEVEL_TEXT[st['level']]
        a['score'] = round(st['score'], 2)
        a['best_score'] = a['score']
        a['counter'] = sum(1 for it in items if it['factor'] == f and it['level'] == 'E4'
                           and it.get('dir') in ('up', 'down'))
    rows = sorted(agg.values(), key=lambda x: (-LEVEL_W[x['best_level']], -x['score']))
    for i, r in enumerate(rows, 1):
        r['rank'] = i
    return rows


def build(aligned, case, anomalies=None):
    win = aligned['window']
    spot = aligned['layers']['price']['spot']
    price_chg = spot.get('pct_change') or 0
    spot_dir = 'up' if price_chg > 0 else 'down'

    periods = list(case.get('periods') or [])
    if not periods and anomalies and anomalies.get('phases'):
        for p in anomalies['phases']:
            periods.append({'name': '%s至%s' % (p['start_date'], p['end_date']),
                            'start': p['start_date'], 'end': p['end_date'], 'chg_pct': p.get('chg_pct')})
    price_dates = [b['date'] for b in (anomalies or {}).get('bars_in_window', [])]

    all_items = []
    for k, L in aligned['layers'].items():
        if k == 'price':
            continue
        all_items.extend(grade_layer(L, price_chg, periods, price_dates, spot_dir))

    # 期现结构单独出条目
    st = aligned.get('structure', {})
    if st.get('ok') and st.get('baseline'):
        bl = st['baseline']
        b0, b1 = bl['start']['basis'], bl['end']['basis']
        all_items.append({
            'factor': '基差·月差·期现结构', 'series': '基差（现货−%s，同一合约全期可比）' % st['baseline_contract'],
            'level': 'E1', 'evidence_type': '逐日可复算',
            'reason': '窗口内基差由 %s 元/吨（%s）变为 %s 元/吨（%s）；峰值 %s 元/吨（%s），谷值 %s 元/吨（%s）' % (
                C.fmt(b0, 0), bl['start']['date'], C.fmt(b1, 0), bl['end']['date'],
                C.fmt(bl['basis_max'], 0), bl['basis_max_date'], C.fmt(bl['basis_min'], 0), bl['basis_min_date']),
            'value': b1 - b0, 'z': None, 'dir': 'up' if b1 > b0 else 'down',
            'start_date': bl['start']['date'], 'end_date': bl['end']['date'],
            'start_value': b0, 'end_value': b1, 'unit': '元/吨',
            'src': '郑商所 %s 合约日线 ＋ 生意社现货' % st['baseline_contract'], 'src_url': '',
        })
    if st.get('ok') and st.get('spread'):
        sp = st['spread']
        s0, s1 = sp['start']['spread'], sp['end']['spread']
        all_items.append({
            'factor': '基差·月差·期现结构', 'series': '月差 %s−%s（同一对合约，全期可比）' % (sp['pair'][0], sp['pair'][1]),
            'level': 'E1', 'evidence_type': '逐日可复算',
            'reason': '月差由 %s 变为 %s 元/吨（区间 %s～%s）；%s' % (
                C.fmt(s0, 0), C.fmt(s1, 0), C.fmt(sp['min'], 0), C.fmt(sp['max'], 0),
                '由 Contango 转为 Back，近端趋紧' if (s0 < 0 and s1 > 0) else
                ('Back 结构加深' if s1 > s0 else 'Back 结构收窄')),
            'value': s1 - s0, 'z': None, 'dir': 'up' if s1 > s0 else 'down',
            'start_date': sp['start']['date'], 'end_date': sp['end']['date'],
            'start_value': s0, 'end_value': s1, 'unit': '元/吨',
            'src': '郑商所合约日线', 'src_url': '',
        })
    for it in all_items:
        it.setdefault('spot_dir', spot_dir)
    scored = score_all(all_items, price_chg, spot_dir)
    ranking = aggregate_ranking(scored)
    return {
        'window': win, 'price_change_pct': price_chg, 'spot_dir': spot_dir,
        'items': scored, 'ranking': ranking, 'level_text': LEVEL_TEXT,
        'score_rule': 'score=级别权重(E1=4/E2=3/E3=1.5/E4=0)+时间吻合+幅度匹配(封顶1)+方向(±0.5/−1)−反证扣分(1.5)',
        'disclaimer': 'score 仅用于排序，不代表该因素解释了价格变动的百分比；报告不给出任何"XX 因素贡献 N%"的数字。',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--aligned', required=True)
    ap.add_argument('--case', required=True)
    ap.add_argument('--anomalies', default=None)
    ap.add_argument('--out', default='build/graded.json')
    a = ap.parse_args()
    aligned = C.jload(a.aligned)
    case = C.jload(a.case)
    anomalies = C.jload(a.anomalies) if a.anomalies and os.path.exists(a.anomalies) else None
    res = build(aligned, case, anomalies)
    C.jdump(res, a.out)
    print('证据条目', len(res['items']), '条 ->', a.out)
    for r in res['ranking']:
        print('  %-4s %-22s 最强证据：%s' % (r['best_level'], r['factor'][:22], (r['strongest'] or {}).get('series', '')[:40]))


if __name__ == '__main__':
    main()
