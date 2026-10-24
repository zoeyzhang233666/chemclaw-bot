# -*- coding: utf-8 -*-
"""批量扫描主程序：对齐 → 相关 → 偏离 → 多重检验 → 稳定性 → 导出 scan_pack.json。

用法示例
    python build/run_scan.py --out build/out                       # 全池
    python build/run_scan.py --out build/out --hist 2024-06-30     # 历史回看
    python build/run_scan.py --out build/out --pairs PP0:L0        # 单对
"""
import argparse
import csv
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stats_core as SC  # noqa: E402
import chain_graph as CG  # noqa: E402
import fundamentals as FD  # noqa: E402
import sources as SRC  # noqa: E402

SERIES_KEYS = ('common_dates', 'ret_dates', 'ret_a', 'ret_b', 'roll_corr_series',
               'dates', 'close_a', 'close_b', 'z_series', 'spread_series')


# ---------------------------------------------------------------------------
# 数据装载
# ---------------------------------------------------------------------------
def load_series(path):
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            try:
                c = float(r['close'])
            except (TypeError, ValueError):
                continue
            if c <= 0:
                continue
            rows.append(dict(date=r['date'], close=c,
                             vol=float(r.get('volume') or 0),
                             oi=float(r.get('open_interest') or 0),
                             settle=float(r.get('settle') or 0)))
    rows.sort(key=lambda x: x['date'])
    return rows


def _to_ord(s):
    y, m, d = map(int, s.split('-'))
    return datetime.date(y, m, d).toordinal()


def detect_rolls(rows, gap_days=9, jump_thresh=0.05, oi_jump=0.10):
    """主力换月/数据断档的可用代理识别（数据源不含逐日主力合约代码）。

    1) 日期断档：相邻交易日历天数 >= gap_days（默认 9 天），标记为数据断档日；
    2) 无断档但跳空：|log(p_t/p_{t-1})| > 5%，且前一日与后一日振幅均 < 2%，
       且持仓量单日变化 > 10%（换月时持仓跳空的典型特征）。

    节后首日（长假后第一个交易日）会自然满足上述形态而被标记，但它反映的是假期累计信息，
    不是换月。因此对"首日涨跌在前一日非首日、后一日非首日都成立"的情形，用当日成交量与
    前 20 日均量之比判断：放量（>=1.2 倍）视为节后集中定价，不标记为换月。
    """
    import math
    flag = [0] * len(rows)
    for i in range(1, len(rows)):
        g = _to_ord(rows[i]['date']) - _to_ord(rows[i - 1]['date'])
        if g >= gap_days:
            flag[i] = 1
            continue
        r0 = rows[i]['close'] / rows[i - 1]['close']
        if r0 <= 0:
            continue
        lr = math.log(r0)
        if abs(lr) <= jump_thresh:
            continue
        prev_ok = i < 2 or abs(math.log(rows[i - 1]['close'] / rows[i - 2]['close'])) < 0.02
        next_ok = i + 1 >= len(rows) or abs(math.log(rows[i + 1]['close'] / rows[i]['close'])) < 0.02
        oj = abs(rows[i]['oi'] - rows[i - 1]['oi']) / max(rows[i - 1]['oi'], 1) > oi_jump
        if not (prev_ok and next_ok and oj):
            continue
        hist = [x['vol'] for x in rows[max(0, i - 20):i] if x['vol'] > 0]
        vol_ratio = rows[i]['vol'] / (sum(hist) / len(hist)) if hist else 0
        if vol_ratio < 1.2:          # 缩量跳空 → 更可能是换月/数据问题
            flag[i] = 1
    return flag


def build_series(rows, flags):
    seg = [1 if (f and i > 0) else 0 for i, f in enumerate(flags)]
    return dict(dates=[r['date'] for r in rows],
                closes=[r['close'] for r in rows],
                roll_flag=[bool(f) for f in flags],
                roll_dates=set(r['date'] for r, f in zip(rows, flags) if f),
                seg=seg)


def load_universe(data_dir, codes=None):
    series, meta = {}, {}
    for u in CG.UNIVERSE:
        code = u['code']
        if codes and code not in codes:
            continue
        p = os.path.join(data_dir, code + '.csv')
        if not os.path.exists(p):
            continue
        rows = load_series(p)
        flags = detect_rolls(rows)
        series[code] = build_series(rows, flags)
        meta[code] = dict(code=code, name=u['name'], n=len(rows), first=rows[0]['date'],
                          last=rows[-1]['date'], roll_flagged=sum(flags),
                          file=os.path.basename(p), unit='元/吨', mult=u['mult'])
    return series, meta


# ---------------------------------------------------------------------------
# 扫描
# ---------------------------------------------------------------------------
def select_pairs(args, series):
    pairs = CG.build_pairs()
    if args.universe != 'all':
        keep = set(x.strip() for x in args.universe.split(',') if x.strip())
        pairs = [p for p in pairs if p['a'] in keep and p['b'] in keep]
    if args.pairs:
        want = set(tuple(sorted(t.strip() for t in x.split(':'))) for x in args.pairs.split(','))
        pairs = [p for p in pairs if tuple(sorted([p['a'], p['b']])) in want]
    if args.primary_only:
        pairs = [p for p in pairs if p['strength'] in CG.PAIR_RULES['min_strength_for_primary']]
    return pairs, len(pairs)


def scan(data_dir='data', out='build/out', params=None, pairs_filter=None,
         universe_filter=None, cut_off=None, primary_only=False, verbose=True,
         dump_series=True):
    P = dict(SC.DEFAULTS)
    if params:
        P.update(params)
    series, meta = load_universe(data_dir)
    if cut_off:
        for code, s in series.items():
            keep = [i for i, d in enumerate(s['dates']) if d <= cut_off]
            for k in ('dates', 'closes', 'roll_flag', 'seg'):
                s[k] = [s[k][i] for i in keep]
            s['roll_dates'] = set(d for d in s['roll_dates'] if d <= cut_off)
    classes = argparse.Namespace(universe=universe_filter or 'all',
                                 pairs=pairs_filter or '', primary_only=primary_only)
    pairs, n_pairs = select_pairs(classes, series)

    results = []
    for rel in pairs:
        if rel['a'] not in series or rel['b'] not in series:
            results.append(dict(code_a=rel['a'], code_b=rel['b'], rtype=rel['rtype'],
                                status='no_data', notes=['缺价格数据文件']))
            continue
        r = SC.scan_pair(series[rel['a']], series[rel['b']], rel, P, meta)
        r['strength'] = rel['strength']
        r['k'] = rel.get('k')
        r['direction'] = rel.get('direction')
        results.append(r)

    ok = [r for r in results if r.get('status') == 'ok']
    m = max(1, len(ok))

    # ---- 置换检验（可关闭：--perm 0）----
    if P['perm_n'] > 0:
        for r in ok:
            n = min(len(r['ret_a']), len(r['ret_b']), 500)
            pn = SC.permutation_null_corr(r['ret_a'][-n:], r['ret_b'][-n:],
                                          n_perm=P['perm_n'], seed=P['seed'])
            r['perm'] = pn

    # ---- 判定 ----
    for r in results:
        r['judge'] = SC.judge_anomaly(r, n_tests=m)
        if r.get('z_last') is not None:
            r['z_p'] = SC.two_sided_tail_from_z(r['z_last'])
        else:
            r['z_p'] = None
    qs = SC.bh_fdr([r['z_p'] for r in results])
    for r, q in zip(results, qs):
        r['z_q_bh'] = q

    # ---- 稳定性 / 可比性评级 ----
    for r in ok:
        r['quality'] = assess_quality(r, meta)

    # ---- 窗口相关变化（近期 vs 历史分位）----
    for r in ok:
        rc = [v for v in r['roll_corr_series'] if v is not None]
        r['rc_series_pct'] = SC.percentile_of(r['roll_corr_last'], rc) if r['roll_corr_last'] is not None else None
        r['rc_argmin'] = (min(rc) if rc else None)

    pack = dict(
        generated_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        cut_off=cut_off,
        params=P,
        universe=[u for u in CG.UNIVERSE if u['code'] in series],
        universe_meta=meta,
        rtype_info=CG.RTYPE_INFO,
        pair_rules=CG.PAIR_RULES,
        n_pairs=n_pairs, n_tests=m,
        relations=[dict(a=p['a'], b=p['b'], rtype=p['rtype'], strength=p['strength'],
                        direction=p['direction'], mechanism=p['mechanism'],
                        market_convention=p['market_convention'], k=p.get('k'),
                        coef_kind=p.get('coef_kind'), source_ids=p['source_ids'],
                        comparability=p['comparability'],
                        a_role=p['a_role'], b_role=p['b_role']) for p in pairs],
        sources={k: v for k, v in SRC.SOURCES.items()},
        events=FD.EVENTS,
        common_shock=FD.COMMON_SHOCK,
        fund_template=FD.FUND_TEMPLATE,
        results=results,
    )
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'scan_pack.json'), 'w', encoding='utf-8') as f:
        json.dump(_slim(pack), f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(out, 'scan_pack_pretty.json'), 'w', encoding='utf-8') as f:
        json.dump(_slim(pack), f, ensure_ascii=False, indent=1)
    if dump_series:
        write_decimated_series(results, os.path.join(out, 'series_web'))
        write_timeseries(results, os.path.join(out, 'series'))
    if verbose:
        print_table(results)
    return pack


def _slim(pack):
    """压缩：浮点保留 5 位有效数字，去掉滚动相关逐点序列（可在浏览器按需重算）。
    不改变返回值（仍是深拷贝前的 pack 未被修改），所以调用方拿到的 pack 保持完整精度与序列。"""
    import copy

    def rnd(v):
        if isinstance(v, float):
            return float(f'{v:.5g}')
        if isinstance(v, list):
            return [rnd(x) for x in v]
        if isinstance(v, dict):
            return {k: rnd(x) for k, x in v.items()}
        return v

    def strip(r):
        return {k: v for k, v in r.items() if k not in ('roll_corr_series', 'spread_series')}

    p = copy.deepcopy({k: v for k, v in pack.items() if k != 'results'})
    p['results'] = [rnd(strip(r)) for r in pack['results']]
    return p


def write_decimated_series(results, d):
    """为每个组合输出按月抽样的时间序列（同时保留最近 120 个交易日逐日），供 HTML 交互图表。"""
    os.makedirs(d, exist_ok=True)
    bundle = {}
    for r in results:
        if r.get('status') != 'ok':
            continue
        dates, ca, cb = r['dates'], r['close_a'], r['close_b']
        n = len(dates)
        keep = set(range(max(0, n - 120), n))
        seen_month = set()
        for i, dt in enumerate(dates):
            m = dt[:7]
            if m not in seen_month:
                seen_month.add(m)
                keep.add(i)
        idx = sorted(keep)
        name = f"{r['code_a']}_{r['code_b']}"
        bundle[name] = dict(
            code_a=r['code_a'], code_b=r['code_b'],
            dates=[dates[i] for i in idx],
            a=[round(ca[i], 2) for i in idx],
            b=[round(cb[i], 2) for i in idx],
            spread=[round(r['spread_series'][i], 5) for i in idx],
            z=[None if r['z_series'][i] is None else round(r['z_series'][i], 3) for i in idx],
        )
    with open(os.path.join(d, 'web_series.json'), 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False, separators=(',', ':'))


def _slim(r):
    return {k: v for k, v in r.items() if k not in SERIES_KEYS}


def assess_quality(r, meta):
    """数据可比性 + 关系稳定性 双维评级（A/B/C）。"""
    notes = []
    score = 0
    n_ov = r.get('n_overlap') or 0
    span_years = None
    if r.get('first') and r.get('last'):
        span_years = (_to_ord(r['last']) - _to_ord(r['first'])) / 365.25
    if n_ov >= 1500:
        score += 2
        notes.append(f'重叠 {n_ov} 交易日（约 {span_years:.1f} 年），样本充分')
    elif n_ov >= 700:
        score += 1
        notes.append(f'重叠 {n_ov} 交易日（约 {span_years:.1f} 年），样本一般')
    else:
        notes.append(f'重叠仅 {n_ov} 交易日（约 {span_years:.1f} 年），历史分位统计功效有限')
    # 稳定性：滚动相关中位数与近 20 日窗口
    med = r.get('roll_corr_median')
    if med is not None:
        if med >= 0.7:
            score += 2
            notes.append(f'滚动 60 日相关中位数 {med:.2f}，关系稳定')
        elif med >= 0.4:
            score += 1
            notes.append(f'滚动 60 日相关中位数 {med:.2f}，关系中等')
        else:
            notes.append(f'滚动 60 日相关中位数 {med:.2f}，历史关系本身不稳定')
    # 分年稳定性：用滚动相关序列的分段标准差近似
    rc = [v for v in r.get('roll_corr_series', []) if v is not None]
    if len(rc) > 120:
        third = len(rc) // 3
        parts = [SC.mean(rc[:third]), SC.mean(rc[third:2 * third]), SC.mean(rc[2 * third:])]
        spread = max(parts) - min(parts)
        r['rc_regime_spread'] = spread
        if spread > 0.30:
            notes.append(f'三段滚动相关均值区间 {min(parts):.2f}~{max(parts):.2f}，存在明显制度切换')
        else:
            score += 1
            notes.append(f'三段滚动相关均值区间 {min(parts):.2f}~{max(parts):.2f}，跨期稳定')
    if r.get('rtype') in ('cross_chain_cost',):
        notes.append('成本共振型关系，无直接物料流，主业参考价值有限')
        score -= 1
    level = 'A' if score >= 4 else ('B' if score >= 2 else 'C')
    return dict(level=level, score=score, notes=notes, n_overlap=n_ov, span_years=span_years)


def write_timeseries(results, d):
    os.makedirs(d, exist_ok=True)
    for r in results:
        if r.get('status') != 'ok':
            continue
        name = f"{r['code_a']}_{r['code_b']}"
        with open(os.path.join(d, name + '.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['date', 'close_a', 'close_b', 'spread_ln', 'z_roll60'])
            for i, dt in enumerate(r['dates']):
                w.writerow([dt, r['close_a'][i], r['close_b'][i],
                            round(r['spread_series'][i], 8),
                            '' if r['z_series'][i] is None else round(r['z_series'][i], 4)])
        with open(os.path.join(d, name + '_ret.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['date', 'ret_a', 'ret_b', 'roll_corr60'])
            rc = r['roll_corr_series']
            for i, dt in enumerate(r['ret_dates']):
                w.writerow([dt, round(r['ret_a'][i], 8), round(r['ret_b'][i], 8),
                            '' if rc[i] is None else round(rc[i], 4)])


def print_table(results):
    hdr = (f"{'pair':9s} {'rtype':19s} {'n':>5s} {'r_all':>6s} {'r_roll':>6s} {'drop':>6s} "
           f"{'z':>6s} {'zrun':>4s} {'|zmx|':>6s} {'q':>6s} {'verdict':10s} {'qf':4s}")
    print(hdr)
    print('-' * len(hdr))
    order = {'异常背离（候选）': 0, '关注': 1, '偏离但未达门槛': 2, '正常': 3, '数据不足': 4}
    for r in sorted([x for x in results if x.get('status') == 'ok'],
                    key=lambda x: (order.get(x['judge']['verdict'], 9), -x['judge']['score'])):
        j = r['judge']
        q = r.get('quality', {}).get('level', '-')
        print(f"{r['code_a']+'/'+r['code_b']:9s} {r['rtype']:19s} {r['n_returns']:5d} "
              f"{_f(r['r_daily'],6)} {_f(r['roll_corr_last'],6)} {_f(j.get('corr_drop'),6)} "
              f"{_f(r['z_last'],6)} {r['z_run_days']:4d} {_f(r['z_abs_max_hist'],6)} "
              f"{_f(r.get('z_q_bh'),6)} {j['verdict']:10s} {q:4s}")
    for r in [x for x in results if x.get('status') != 'ok']:
        print(f"{r['code_a']+'/'+r['code_b']:9s} {r['rtype']:19s}  {r.get('status')}")


def _f(v, w=4):
    return '-' if v is None else f'{v:.{w}g}' if abs(v) < 10 else f'{v:.2f}'


def main(argv=None):
    ap = argparse.ArgumentParser(description='产业链异常背离扫描')
    ap.add_argument('--data', default='data')
    ap.add_argument('--out', default='build/out')
    ap.add_argument('--window', type=int, default=60, help='滚动相关窗口（交易日）')
    ap.add_argument('--z', type=float, default=2.0, help='偏离阈值 |z|')
    ap.add_argument('--persist', type=int, default=5, help='持续性天数')
    ap.add_argument('--drop', type=float, default=0.45, help='脱钩阈值')
    ap.add_argument('--perm', type=int, default=1200, help='置换次数，0=关闭')
    ap.add_argument('--cut-off', default=None, help='历史回看截止日 YYYY-MM-DD')
    ap.add_argument('--universe', default='all')
    ap.add_argument('--pairs', default='')
    ap.add_argument('--primary-only', action='store_true', help='只扫 strong/medium 关系（主榜单）')
    a = ap.parse_args(argv)
    params = dict(window_mask=a.window, z_threshold=a.z, persist_days=a.persist,
                  drop_threshold=a.drop, perm_n=a.perm)
    scan(data_dir=a.data, out=a.out, params=params, pairs_filter=a.pairs,
         universe_filter=a.universe, cut_off=a.cut_off, primary_only=a.primary_only)


if __name__ == '__main__':
    main()
