# -*- coding: utf-8 -*-
"""月差全景分析：一次跑完 7 项研究内容，输出 result.json 供 HTML/Excel 使用。

用法
----
    python scripts/analyze_spread.py --product SA --a SA2612 --b SA2701 \
        --asof 2026-10-20 --price close --out build/result.json \
        --warehouse data/external/warrant_SA.csv --events data/external/events_SA.json

输出（result.json 顶层）
------------------------
product / asof / contracts / spread / change / percentile / term_structure /
comparable / decomposition / daily_contrib / roll / warehouse / events / data_quality / meta
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import spreadlib as S  # noqa: E402

REGISTRY_PATH = os.path.join(ROOT, 'references', 'contracts_registry.json')


# --------------------------------------------------------------------------------------
def load_registry(path: str = REGISTRY_PATH) -> dict:
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def load_warehouse(path: str):
    """外部仓单/库存 CSV：date,value[,unit]。缺文件返回 None（脚本不编数据）。"""
    if not path or not os.path.exists(path):
        return None
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            try:
                rows.append({'date': r['date'][:10], 'value': float(r['value']),
                             'unit': r.get('unit', '')})
            except (KeyError, ValueError):
                continue
    rows.sort(key=lambda r: r['date'])
    return rows


def load_events(path: str):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return json.load(f)


# --------------------------------------------------------------------------------------
def change_table(rows: list, windows=((5, '近1周'), (10, '近2周'), (20, '近1月'),
                                      (60, '近3月'), (120, '近半年'))) -> list:
    """当前月差相对 N 个交易日前的变化。样本不足则返回 None（不硬凑）。"""
    out = []
    if not rows:
        return out
    last = rows[-1]
    for n, label in windows:
        if len(rows) <= n:
            out.append({'window': label, 'n': n, 'from': None, 'to': S.iso(last['date']),
                        'change': None, 'pct': None, 'note': f'历史样本仅 {len(rows)} 个交易日，不足 {n}'})
            continue
        prev = rows[-1 - n]
        chg = last['spread'] - prev['spread']
        out.append({'window': label, 'n': n, 'from': S.iso(prev['date']), 'to': S.iso(last['date']),
                    'from_value': prev['spread'], 'to_value': last['spread'], 'change': chg,
                    'pct': (chg / abs(prev['spread']) * 100) if prev['spread'] else None,
                    'chg_a': last['a'] - prev['a'], 'chg_b': last['b'] - prev['b']})
    return out


def percentile_block(cur: float, rows: list, asof_lookback_days: int = 366) -> dict:
    """当前合约对的历史分位：全样本 / 近1年 / 近3年。

    **实际可比时长不足时如实标注**（例如 SA2612 于 2025-12 才挂牌，
    近 1 年、近 3 年与全样本完全重合），绝不把不足 3 年的样本说成“3 年分位”。
    """
    if not rows:
        return {}
    vals = [r['spread'] for r in rows]
    asof = rows[-1]['date']
    first = rows[0]['date']
    span_days = (asof - first).days
    span_years = span_days / 365.25

    def sub(days):
        cut = asof - dt.timedelta(days=days)
        return [r for r in rows if r['date'] >= cut]

    out = {'span_days': span_days, 'span_years': round(span_years, 2),
           'first': S.iso(first), 'last': S.iso(asof)}
    for key, want_days, label in (('all', None, '全样本（本合约对上市以来）'),
                                  ('y1', 366, '近1年'),
                                  ('y3', 1096, '近3年')):
        if want_days is None:
            sel, vv = rows, vals
            data_ok = True
        else:
            sel = sub(want_days)
            vv = [r['spread'] for r in sel]
            data_ok = span_days >= want_days - 31
        if not vv:
            out[key] = {'label': label, 'n': 0, 'available': False}
            continue
        st = S.spread_stats([], vv)
        note = None
        if want_days is not None and not data_ok:
            note = (f'合约对实际历史仅 {span_years:.2f} 年（{S.iso(first)} 起），'
                    f'不足 {appr(want_days)}，本项与全样本重合，不能称为“{label}分位”')
        out[key] = {
            'label': label, 'n': len(vv), 'pct': S.percentile_of(cur, vv),
            'first': S.iso(sel[0]['date']), 'last': S.iso(sel[-1]['date']),
            'stats': st, 'rank': sum(1 for v in vv if v <= cur), 'usable': data_ok,
            'note': note,
        }
    return out


def appr(days: int) -> str:
    return '1 年' if days < 500 else '3 年'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='月差全景分析')
    ap.add_argument('--product', default='SA')
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    ap.add_argument('--asof', default=None, help='分析日（默认数据最后一天）')
    ap.add_argument('--price', default='close', choices=['close', 'settle'])
    ap.add_argument('--rawdir', default=os.path.join(ROOT, 'data', 'raw'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'result.json'))
    ap.add_argument('--warehouse', default=None, help='仓单/库存 CSV（date,value,unit）')
    ap.add_argument('--warehouse-label', default='')
    ap.add_argument('--events', default=None, help='事件 JSON')
    ap.add_argument('--min-oi', type=float, default=1000.0)
    ap.add_argument('--dtd-tol', type=int, default=10, help='可比样本距交割时间容差（交易日）')
    ap.add_argument('--no-registry', action='store_true')
    args = ap.parse_args(argv)

    book = S.ContractBook.from_dir(args.rawdir, args.product)
    if not book.series:
        print(f'[错误] 没有 {args.product} 数据', file=sys.stderr)
        return 2
    for c in (args.a, args.b):
        if c not in book.series:
            print(f'[错误] 合约 {c} 不在数据中，现有：{book.codes()}', file=sys.stderr)
            return 2
    asof = S.parse_date(args.asof) if args.asof else book.latest_trading_date()
    # 若 asof 不是交易日，取不晚于它的最近交易日（并记录）
    all_dates = book.all_dates()
    if asof not in set(all_dates):
        real = S.nearest_date(all_dates, asof)
        print(f'[提示] {S.iso(asof)} 非交易日，改用最近的 {S.iso(real)}')
        asof = real

    A, B = args.a.upper(), args.b.upper()
    dq = S.data_quality(book)

    # 1) 月差序列 ---------------------------------------------------------------
    sp = S.spread_series(book, A, B, price=args.price, min_oi=args.min_oi)
    rows = sp['rows']
    if not rows:
        print('[错误] 两个合约没有共同的持仓量达标交易日', file=sys.stderr)
        return 2
    rows_to = [r for r in rows if r['date'] <= asof]
    if not rows_to:
        print('[错误] asof 之前没有有效月差样本', file=sys.stderr)
        return 2
    cur_row = rows_to[-1]
    cur = cur_row['spread']

    # 2) 描述 + 变化 ------------------------------------------------------------
    stats = S.spread_stats(rows_to)
    changes = change_table(rows_to)

    # 3) 分位 ------------------------------------------------------------------
    pct_block = percentile_block(cur, rows_to)
    # 可比样本分位单独算（这才是“同口径”的口径）
    cmp_ = S.build_comparable_samples(book, A, B, asof, price=args.price,
                                      dtd_tol=args.dtd_tol, min_oi=args.min_oi)
    cmp_vals = [v for p in cmp_['pairs'] for v in p['vals']]
    cmp_pct = S.percentile_of(cur, cmp_vals) if cmp_vals else None
    cmp_stats = S.spread_stats([], cmp_vals) if cmp_vals else {'n': 0}
    last_year = S.historical_same_month_value(book, A, B, asof, price=args.price)

    # 4) 期限结构 ---------------------------------------------------------------
    ts = S.term_structure(book, asof, price=args.price, min_oi=args.min_oi)
    ts_shape = S.term_structure_shape(ts)
    # 历史同月期限结构对照（去年同期同日）
    try:
        ly_date = S.nearest_date(all_dates, dt.date(asof.year - 1, asof.month, asof.day if asof.day <= 28 else 28))
        ts_ly = S.term_structure(book, ly_date, price=args.price, min_oi=args.min_oi)
    except ValueError:
        ly_date, ts_ly = None, []

    # 5) 贡献分解 ---------------------------------------------------------------
    dec = {}
    for label, days in (('近1周', 5), ('近2周', 10), ('近1月', 20)):
        idx = max(0, len(rows_to) - 1 - days)
        d0 = rows_to[idx]['date']
        if d0 < rows_to[-1]['date']:
            dec[label] = S.decompose(book, A, B, d0, asof, price=args.price)
    daily = S.decompose_window(book, A, B, asof, n=10, price=args.price)
    full = S.decompose(book, A, B, rows_to[0]['date'], asof, price=args.price)

    # 6) 换月/流动性 ------------------------------------------------------------
    roll = S.roll_off(book, asof)

    # 7) 外部数据 ---------------------------------------------------------------
    wh = load_warehouse(args.warehouse)
    wh_block = None
    if wh:
        upto = [r for r in wh if r['date'] <= S.iso(asof)]
        if upto:
            cur_wh = upto[-1]
            hist = [r['value'] for r in upto]
            w20 = upto[-21] if len(upto) > 21 else None
            wh_block = {'label': args.warehouse_label or os.path.basename(args.warehouse),
                        'unit': cur_wh['unit'], 'current': cur_wh['value'], 'date': cur_wh['date'],
                        'n_days': len(upto), 'first': upto[0]['date'],
                        'pct_own_history': S.percentile_of(cur_wh['value'], hist),
                        'change_20d': (cur_wh['value'] - w20['value']) if w20 else None,
                        'max': max(hist), 'min': min(hist),
                        'series': upto}
    events = load_events(args.events)

    registry = {} if args.no_registry else load_registry().get(args.product.upper(), {})

    result = {
        'meta': {
            'generated_at': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'product': args.product.upper(), 'asof': S.iso(asof), 'price_basis': args.price,
            'min_oi': args.min_oi, 'dtd_tol': args.dtd_tol,
            'engine': 'futures-calendar-spread / analyze_spread.py',
            'formula': f'月差 = P({A}) − P({B})（{"收盘价" if args.price == "close" else "结算价"}，元/吨）',
            'note': '月差与分位只做描述，不含任何交易建议。',
        },
        'contracts': {'a': A, 'b': B,
                      'a_delivery': list(S.code_to_delivery(A)), 'b_delivery': list(S.code_to_delivery(B)),
                      'gap_months': S.month_pair_gap(A, B),
                      'a_dtd': cur_row['dtd_a'], 'b_dtd': cur_row['dtd_b'],
                      'a_first': S.iso(book.series[A].first_date()),
                      'b_first': S.iso(book.series[B].first_date()),
                      'a_last': S.iso(book.series[A].last_date()),
                      'b_last': S.iso(book.series[B].last_date()),
                      'registry': registry},
        'spread': {'current': cur, 'date': S.iso(cur_row['date']),
                   'a_price': cur_row['a'], 'b_price': cur_row['b'],
                   'a_oi': cur_row['oi_a'], 'b_oi': cur_row['oi_b'],
                   'stats': stats, 'n': len(rows_to),
                   'first': S.iso(rows_to[0]['date']),
                   'series': [{'date': S.iso(r['date']), 'a': r['a'], 'b': r['b'],
                               'spread': r['spread'], 'dtd_a': r['dtd_a']} for r in rows_to]},
        'change': changes,
        'percentile': {'pair_history': pct_block,
                       'comparable': {'label': f'同月份组合+距交割±{args.dtd_tol}交易日 可比样本',
                                      'n': len(cmp_vals), 'pct': cmp_pct, 'stats': cmp_stats},
                       'last_year_same_date': last_year},
        'term_structure': {'asof': S.iso(asof), 'rows': ts, 'shape': ts_shape,
                           'last_year_date': S.iso(ly_date) if ly_date else None, 'last_year': ts_ly},
        'comparable': cmp_,
        'decomposition': {'windows': dec, 'daily': daily, 'full': full},
        'roll': roll,
        'warehouse': wh_block,
        'events': events,
        'data_quality': dq,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    # ---- 控制台摘要 ----------------------------------------------------------
    errs = [d for d in dq if d[0] == 'ERROR']
    print(f'== {args.product} {A} − {B} @ {S.iso(asof)}（{args.price}）==')
    print(f'当前月差 {cur:+.0f} 元/吨；{A} {cur_row["a"]:.0f}，{B} {cur_row["b"]:.0f}')
    for c in changes:
        if c.get('change') is not None:
            print(f'  {c["window"]:<5} 变化 {c["change"]:+.0f}（{c["from"]} → {c["to"]}）')
    for k, v in pct_block.items():
        if not isinstance(v, dict):
            continue
        if v.get('n'):
            tag = '  (与全样本重合，不可称为该区间分位)' if v.get('note') else ''
            print(f'  分位[{v["label"]}] {v["pct"]:.0f}%（N={v["n"]}）{tag}')
    print(f'  可比样本分位 {cmp_pct:.0f}%（N={len(cmp_vals)}，{len(cmp_["pairs"])} 组历史同类合约对）'
          if cmp_vals else '  可比样本不足，未计算分位')
    print(f'  期限结构：{" ".join(r["contract"] + "=" + format(r["price"], ".0f") for r in ts)}')
    print(f'  形态：{ts_shape["shape"]}')
    for lab, d in dec.items():
        if d and 'error' not in d:
            print(f'  贡献[{lab}] Δ月差 {d["ds"]:+.0f}；近月 {d["contrib_a_dln"] * 100:+.2f}%（{d["chg_a"]:+.0f}），'
                  f'远月 {d["contrib_b_dln"] * 100:+.2f}%（{d["chg_b"]:+.0f}）')
    if wh_block:
        print(f'  {wh_block["label"]}：{wh_block["current"]:.0f}{wh_block["unit"]} @ {wh_block["date"]}')
    print(f'  数据质量：ERROR {len(errs)} 条，WARN {len([d for d in dq if d[0] == "WARN"])} 条')
    print(f'  → {args.out}')
    return 0 if not errs else 1


if __name__ == '__main__':
    sys.exit(main())
