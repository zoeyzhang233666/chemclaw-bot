# -*- coding: utf-8 -*-
"""把 result.json 升级成“有历史对照”的完整研究成果（供 HTML / Excel 共用）。

用法
----
    python scripts/build_panel.py --result build/result.json --out build/enriched.json \
        --events data/external/events_SA.json

新增内容
--------
* panel         ：每个历史交易日、每个合约的价格/结算/持仓/距交割交易日/期限结构 TS（近月归一）
* shape_history ：每一天的期限结构形态、近端月差、近端斜率（元/吨/月）
* ts_history    ：以“最近月合约”为锚分段观察近端月差演变（换月点拆段）
* story         ：把“为什么变了”组织成 时点→数值→形态→事件 的核查骨架
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import spreadlib as S  # noqa: E402


def build_panel(book: S.ContractBook, price: str, min_oi: float, date_from=None) -> list:
    dates = book.all_dates()
    rows = []
    for d in dates:
        if date_from and d < date_from:
            continue
        listed = book.listed_on(d, min_oi=min_oi)
        if len(listed) < 2:
            continue
        anchor = book.series[listed[0]].quote(d, price)
        if anchor is None:
            continue
        for c in listed:
            s = book.series[c]
            p = s.quote(d, price)
            if p is None:
                continue
            y, m = S.code_to_delivery(c)
            rows.append({
                'date': S.iso(d), 'contract': c, 'y': y, 'm': m, 'price': p,
                'settle': s.settle[s.idx[d]], 'oi': s.oi_at(d), 'volume': s.volume[s.idx[d]],
                'dtd': S.trading_days_between(d, S.delivery_date(y, m)),
                'ts': p - anchor, 'ts_pct': (p / anchor - 1) * 100,
                'is_nearest': c == listed[0], 'n_listed': len(listed),
            })
    return rows


def shape_history(panel: list) -> list:
    by_date = {}
    for r in panel:
        by_date.setdefault(r['date'], []).append(r)
    out = []
    for d in sorted(by_date):
        rs = sorted(by_date[d], key=lambda r: (r['y'], r['m']))
        if len(rs) < 2:
            continue
        shape = S.term_structure_shape([{'ts': r['ts']} for r in rs])
        near_gap = rs[1]['dtd'] - rs[0]['dtd']
        out.append({
            'date': d, 'near': rs[0]['contract'], 'near_next': rs[1]['contract'],
            'near_spread': rs[1]['ts'],
            'near_slope_per_month': (rs[1]['ts'] / near_gap) if near_gap else None,
            'far_spread': rs[-1]['ts'], 'far': rs[-1]['contract'],
            'shape': shape['shape'], 'n': len(rs),
        })
    return out


def build_story(res: dict, shape_hist: list, events: list) -> list:
    """生成“为什么变了”的核查骨架：每个关键节点给出可复核的数字与待证原因。"""
    sp = res['spread']['series']
    if not sp:
        return []
    pts = [{'date': sp[0]['date'], 'tag': '序列起点', 'value': sp[0]['spread'],
            'text': '该合约对首次双方都有持仓量的交易日'}]
    if len(sp) > 6:
        w = 5
        best, bi = 0, 0
        for i in range(w, len(sp)):
            dv = sp[i]['spread'] - sp[i - w]['spread']
            if abs(dv) > abs(best):
                best, bi = dv, i
        pts.append({'date': sp[bi]['date'], 'tag': f'最大{w}日变动', 'value': sp[bi]['spread'],
                    'change': best,
                    'text': f'从 {sp[bi - w]["spread"]:+.0f} 到 {sp[bi]["spread"]:+.0f}，变化 {best:+.0f} 元/吨'})
    hi = max(sp, key=lambda r: r['spread'])
    lo = min(sp, key=lambda r: r['spread'])
    pts.append({'date': hi['date'], 'tag': '区间最高', 'value': hi['spread'], 'text': '本合约对月差最高点'})
    pts.append({'date': lo['date'], 'tag': '区间最低', 'value': lo['spread'], 'text': '本合约对月差最低点'})
    pts.append({'date': sp[-1]['date'], 'tag': '当前', 'value': sp[-1]['spread'], 'text': '最新交易日'})

    sh_map = {s['date']: s for s in shape_hist}
    for p in pts:
        p['events'] = [e for e in events
                       if abs((S.parse_date(e['date']) - S.parse_date(p['date'])).days) <= 3]
        s = sh_map.get(p['date'])
        p['shape'] = s['shape'] if s else None
        p['near_spread'] = s['near_spread'] if s else None
    return sorted(pts, key=lambda x: x['date'])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--result', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--rawdir', default=None)
    ap.add_argument('--events', default=None)
    ap.add_argument('--panel-from', default='2021-01-01')
    args = ap.parse_args(argv)

    with open(args.result, encoding='utf-8') as f:
        res = json.load(f)
    root = os.path.dirname(HERE)
    rawdir = args.rawdir or os.path.join(root, 'data', 'raw')
    product = res['meta']['product']
    book = S.ContractBook.from_dir(rawdir, product)
    price = res['meta']['price_basis']
    min_oi = res['meta']['min_oi']

    panel = build_panel(book, price, min_oi, date_from=S.parse_date(args.panel_from))
    sh = shape_history(panel)
    events = []
    if args.events and os.path.exists(args.events):
        with open(args.events, encoding='utf-8') as f:
            events = json.load(f)

    segs, cur = [], None
    for s in sh:
        if cur is None or s['near'] != cur['anchor']:
            cur = {'anchor': s['near'], 'points': []}
            segs.append(cur)
        cur['points'].append({'date': s['date'], 'near_spread': s['near_spread'],
                              'near_next': s['near_next'], 'shape': s['shape']})
    for sg in segs:
        sg['from'] = sg['points'][0]['date']
        sg['to'] = sg['points'][-1]['date']
        sg['n'] = len(sg['points'])

    res['panel'] = panel
    res['shape_history'] = sh
    res['ts_history'] = segs
    res['story'] = build_story(res, sh, events)
    res['panel_meta'] = {'from': args.panel_from, 'n_rows': len(panel),
                         'n_dates': len({r['date'] for r in panel}),
                         'n_contracts': len({r['contract'] for r in panel}),
                         'price': price, 'min_oi': min_oi}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f'面板 {len(panel)} 行 / {res["panel_meta"]["n_dates"]} 个交易日 / '
          f'{res["panel_meta"]["n_contracts"]} 个合约；形态序列 {len(sh)} 天；'
          f'近端分段 {len(segs)} 段 -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
