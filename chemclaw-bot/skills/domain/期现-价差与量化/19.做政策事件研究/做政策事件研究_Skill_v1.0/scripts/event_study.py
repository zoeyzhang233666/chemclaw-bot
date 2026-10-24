# -*- coding: utf-8 -*-
"""政策事件研究 · Event Study 核心计算引擎（品种无关、可跨 Agent 复用）

设计原则
--------
1. **只算已发生的事实**：不插值、不外推、不估算缺失价格。缺失一律写 gap。
2. **双时间锚**：区分"市场第一次获知"（publish_date / market_first_aware）与"政策生效"（effective_date），
   两者各自跑一遍窗口，避免把"预期已提前反映"误算成"政策生效后的效果"。
3. **不做虚假显著性**：样本量 < 5 时只输出描述统计并强制标记 `significance_allowed=false`，
   任何 p 值都不计算、不打印。
4. **可比性是显式判断**：由调用方在事件表里填可比性分组（comparable_group），
   本脚本只按组汇总，绝不把不同性质事件机械合并。

用法
----
    python event_study.py --config events.json --prices prices.json --out out_dir
    python event_study.py --selftest          # 内置合成数据自检，不依赖联网数据

输入契约
--------
prices.json:
    {
      "spot":  [{"date":"2021-09-01","value":2800.0}, ...],     # 现货，可为空数组
      "future":[{"date":"2021-09-01","value":2855.0}, ...],     # 期货
      "basis": [{"date":"2021-09-01","value":-55.0},  ...],     # 可选；缺省则用 spot-future 计算
      "trade_days": ["2021-09-01", ...]                          # 可选；缺省取 future 的日期并集
    }

events.json:
    {
      "product":"纯碱", "unit":"元/吨",
      "windows":[1,5,10,20],
      "events":[{
         "id":"SA-E01",
         "name":"...",
         "policy_type":"环保限产|产业政策|税收贸易|准入|能耗",
         "publish_date":"2021-09-11",          # 原文正式发布日期
         "market_first_aware":"2021-09-11",    # 市场首知（可为征求意见稿日期）
         "effective_date":"2021-10-01",
         "strength":"强|中|弱",
         "scope":"全国|区域|单企业",
         "binding":true,
         "comparable_group":"G1",              # 可比的组；不同组不合并
         "sources":[{"url":"...","title":"...","verified":"原文|二手转载|存疑"}],
         "notes":"..."
      }]
    }

输出
----
    out/event_windows.csv      每个事件 × 每个窗口 × 每个锚 × 每个指标的变动
    out/event_stats.json       均值/中位数/分位/分布（按 comparable_group 分组）
    out/paths.json             事件对齐的价格路径（绘图用）
    out/event_study_report.md  人读摘要
"""
import argparse
import json
import math
import os
import re
import statistics
import sys
from datetime import date, datetime, timedelta

# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
MIN_N_FOR_SIGNIFICANCE = 5   # 硬门槛：低于此样本量不计算任何显著性


def _d(s):
    """把多种日期写法统一成 date。"""
    if isinstance(s, date):
        return s
    s = str(s).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y%m%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError('无法解析日期：%r' % s)


def _f(x):
    """安全转 float；None/空/非数字 -> None。"""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def load_json(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def build_series(rows, key_date='date', key_val='value'):
    """[{date,value}] -> {date: value}，丢弃无效值并记录缺口。"""
    out, dropped = {}, []
    for r in rows or []:
        try:
            d = _d(r.get(key_date))
        except Exception:
            dropped.append(r)
            continue
        v = _f(r.get(key_val))
        if v is None:
            dropped.append(r)
            continue
        out[d] = v
    return out, dropped


# --------------------------------------------------------------------------
# 交易日历与窗口对齐
# --------------------------------------------------------------------------
def build_calendar(prices):
    """交易日历：优先用 trade_days，其次 future 日期，最后 spot 日期。"""
    cal = prices.get('trade_days') or []
    if not cal:
        fut = prices.get('future') or []
        cal = [r.get('date') for r in fut]
    if not cal:
        cal = [r.get('date') for r in prices.get('spot') or []]
    days = sorted({_d(c) for c in cal if c})
    return days


def align_event(calendar, anchor_date, windows):
    """把事件日对齐到交易日，并给出各窗口的 [基准日, 终点日]。

    - 若锚定日正好是交易日，则"基准"用锚定日前一交易日（避免把当日反应算进基准）；
    - 若锚定日落在非交易日，则"首个可交易反应日"为其后第一个交易日。
    返回 dict，含 base_idx / end_idx / gaps 描述。
    """
    anchor = _d(anchor_date)
    # 第一个 >= anchor 的交易日
    after = [i for i, d in enumerate(calendar) if d >= anchor]
    if not after:
        return {'ok': False, 'reason': '锚定日晚于数据末端（%s）' % calendar[-1].isoformat() if calendar else '无交易日历'}
    first_idx = after[0]
    base_idx = first_idx - 1               # 事件前最后一个交易日 = 基准日
    if base_idx < 0:
        return {'ok': False, 'reason': '锚定日之前没有交易日，无法建立基准（数据起点 %s）' % calendar[0].isoformat()}

    info = {
        'ok': True,
        'anchor': anchor.isoformat(),
        'first_trade_day': calendar[first_idx].isoformat(),
        'base_date': calendar[base_idx].isoformat(),
        'anchor_is_trading_day': calendar[first_idx] == anchor,
        'shift_days': (calendar[first_idx] - anchor).days,
        'ends': {},
    }
    for w in windows:
        ei = base_idx + w
        if ei < len(calendar):
            info['ends'][w] = {'idx': ei, 'date': calendar[ei].isoformat(), 'ok': True}
        else:
            info['ends'][w] = {'idx': None, 'date': None, 'ok': False,
                               'reason': '窗口超出数据末端'}
    return info


# --------------------------------------------------------------------------
# 指标计算
# --------------------------------------------------------------------------
def pct_change(base, end):
    if base is None or end is None or base == 0:
        return None
    return (end - base) / abs(base) * 100.0


def compute_paths(calendar, spot, future, basis, base_idx, span):
    """取 [base_idx, base_idx+span] 的事件对齐路径，缺失日为 None（不插值）。"""
    out = []
    for k in range(0, span + 1):
        i = base_idx + k
        if i >= len(calendar):
            break
        d = calendar[i]
        s, f, b = spot.get(d), future.get(d), basis.get(d)
        if b is None and s is not None and f is not None:
            b = s - f            # 仅在两者同日齐备时相减，绝不跨日拼凑
        out.append({'k': k, 'date': d.isoformat(), 'spot': s, 'future': f, 'basis': b})
    return out


def window_changes(calendar, spot, future, basis, base_idx, windows):
    """对每个窗口算：现货/期货/基差的价格与变动。"""
    res = {}
    b_date = calendar[base_idx]
    b_spot, b_fut = spot.get(b_date), future.get(b_date)
    b_basis = basis.get(b_date)
    if b_basis is None and b_spot is not None and b_fut is not None:
        b_basis = b_spot - b_fut
    res['base'] = {'date': b_date.isoformat(), 'spot': b_spot, 'future': b_fut, 'basis': b_basis}

    for w in windows:
        i = base_idx + w
        if i >= len(calendar):
            res[w] = {'ok': False, 'reason': '窗口超出数据末端'}
            continue
        d = calendar[i]
        s, f = spot.get(d), future.get(d)
        b = basis.get(d)
        if b is None and s is not None and f is not None:
            b = s - f
        res[w] = {
            'ok': True,
            'date': d.isoformat(),
            'spot': s, 'future': f, 'basis': b,
            'spot_chg': None if (s is None or b_spot is None) else s - b_spot,
            'future_chg': None if (f is None or b_fut is None) else f - b_fut,
            'basis_chg': None if (b is None or b_basis is None) else b - b_basis,
            'spot_pct': pct_change(b_spot, s),
            'future_pct': pct_change(b_fut, f),
            # 基差本身可正可负，百分比无意义，只给绝对值变动（元/吨）
        }
    return res


# --------------------------------------------------------------------------
# 跨事件汇总（严格按可比组）
# --------------------------------------------------------------------------
def _quantiles(vals, qs=(0.0, 0.25, 0.5, 0.75, 1.0)):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return {('q%.2f' % q): None for q in qs}
    if len(vals) == 1:
        return {('q%.2f' % q): vals[0] for q in qs}
    out = {}
    for q in qs:
        pos = (len(vals) - 1) * q
        lo, hi = int(math.floor(pos)), int(math.ceil(pos))
        if lo == hi:
            out['q%.2f' % q] = vals[lo]
        else:
            out['q%.2f' % q] = vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)
    return out


def summarize(vals):
    """对一组样本做描述统计；样本 < MIN_N_FOR_SIGNIFICANCE 时不计算显著性。"""
    v = [x for x in vals if x is not None]
    n = len(v)
    out = {'n': n, 'mean': None, 'median': None, 'std': None,
           'min': None, 'max': None, 'iqr': None,
           'positive_ratio': None, 'quantiles': None,
           'significance_allowed': n >= MIN_N_FOR_SIGNIFICANCE,
           'significant': None, 'p_value': None, 'test': None,
           'note': None}
    if n == 0:
        out['note'] = '无可用样本（窗口数据缺失或事件不足）'
        return out
    out['mean'] = statistics.fmean(v)
    out['median'] = statistics.median(v)
    out['min'], out['max'] = min(v), max(v)
    if n > 1:
        out['std'] = statistics.stdev(v)     # 样本标准差 (n-1)
    out['positive_ratio'] = sum(1 for x in v if x > 0) / n
    q = _quantiles(v)
    out['quantiles'] = q
    out['iqr'] = None if q['q0.75'] is None else q['q0.75'] - q['q0.25']
    out['values'] = v
    if n < MIN_N_FOR_SIGNIFICANCE:
        out['note'] = ('样本量 n=%d < %d，按规范**不计算**任何显著性检验；'
                       '仅作描述性统计，不得据此宣称政策效应显著。'
                       % (n, MIN_N_FOR_SIGNIFICANCE))
    else:
        # 样本量达标后才给单样本 t 检验（对 0）
        try:
            mean, sd = out['mean'], out['std']
            if sd and sd > 0:
                t = mean / (sd / math.sqrt(n))
                out['test'] = 'one-sample t-test (H0: mean=0), two-sided, df=%d' % (n - 1)
                out['t_stat'] = t
                out['p_value'] = _t_pvalue_two_sided(t, n - 1)
                out['significant'] = (out['p_value'] is not None and out['p_value'] < 0.05)
            else:
                out['note'] = '样本标准差为 0，无法做检验'
        except Exception as e:
            out['note'] = '检验未执行：%s' % e
    return out


def _t_pvalue_two_sided(t, df):
    """不依赖 scipy 的双侧 t 检验 p 值（数值积分）。"""
    if df <= 0:
        return None
    x = df / (df + t * t)
    # 正则化不完全贝塔函数 I_x(df/2, 1/2) = 双侧 p
    return _betainc(df / 2.0, 0.5, x)


def _betainc(a, b, x):
    """正则化不完全贝塔函数（连分数，Numerical Recipes 6.4）。"""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1 - x) / b


def _betacf(a, b, x, itmax=200, eps=3e-12):
    tiny = 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def run(cfg, prices, verbose=True):
    product = cfg.get('product', '')
    unit = cfg.get('unit', '元/吨')
    windows = cfg.get('windows') or [1, 5, 10, 20]
    events = cfg.get('events') or []

    calendar = build_calendar(prices)
    if not calendar:
        raise SystemExit('价格数据里没有可用的交易日历，无法做事件对齐')

    spot, spot_drop = build_series(prices.get('spot'))
    future, fut_drop = build_series(prices.get('future'))
    basis, basis_drop = build_series(prices.get('basis'))

    gaps = []
    if not spot:
        gaps.append('没有现货序列：现货涨跌与基差均不可计算')
    if not future:
        gaps.append('没有期货序列：期货涨跌与基差均不可计算')
    if not basis:
        if spot and future:
            gaps.append('未提供独立基差序列，基差由同日 spot-future 现场计算（跨日不拼凑）')
        else:
            gaps.append('无基差序列且无法由现货期货推导')

    path_span = max(windows) if windows else 20
    results, paths = [], []
    for ev in events:
        eid = ev.get('id') or ev.get('name')
        per_event = {'id': eid, 'name': ev.get('name'), 'meta': ev, 'anchors': {}}
        for anchor_key in ('market_first_aware', 'publish_date', 'effective_date'):
            raw = ev.get(anchor_key)
            if not raw:
                continue
            al = align_event(calendar, raw, windows)
            if not al.get('ok'):
                per_event['anchors'][anchor_key] = {'ok': False, 'anchor_date': raw, 'reason': al.get('reason')}
                continue
            # 反查 base_idx
            base_date = _d(al['base_date'])
            base_idx = calendar.index(base_date)
            wc = window_changes(calendar, spot, future, basis, base_idx, windows)
            pth = compute_paths(calendar, spot, future, basis, base_idx, path_span)
            per_event['anchors'][anchor_key] = {
                'ok': True, 'align': al, 'windows': wc, 'path': pth,
                'lead_days_pub_to_eff': None,
            }
        # 记录"发布->生效"的提前量
        try:
            if ev.get('publish_date') and ev.get('effective_date'):
                lead = (_d(ev['effective_date']) - _d(ev['publish_date'])).days
                for k in per_event['anchors'].values():
                    if isinstance(k, dict):
                        k['lead_days_pub_to_eff'] = lead
        except Exception:
            pass
        results.append(per_event)

    # ------ 按锚 × 窗口 × 指标 × 可比组 汇总 ------
    stats = {}
    for anchor_key in ('market_first_aware', 'publish_date', 'effective_date'):
        stats[anchor_key] = {}
        for w in windows:
            stats[anchor_key][w] = {}
            for metric in ('spot_chg', 'future_chg', 'basis_chg', 'spot_pct', 'future_pct'):
                # 分组
                groups = {}
                for pe in results:
                    a = pe['anchors'].get(anchor_key)
                    if not a or not a.get('ok'):
                        continue
                    wd = a['windows'].get(w) or {}
                    if not wd.get('ok'):
                        continue
                    val = wd.get(metric)
                    g = pe['meta'].get('comparable_group') or 'UNG'
                    groups.setdefault(g, []).append((pe['id'], val))
                stats[anchor_key][w][metric] = {}
                for g, pairs in groups.items():
                    s = summarize([v for _, v in pairs])
                    s['members'] = [{'id': i, 'value': v} for i, v in pairs]
                    s['comparable'] = g != 'UNG'
                    stats[anchor_key][w][metric][g] = s

    # 汇总所有组的可比性判断
    groups_meta = {}
    for pe in results:
        g = pe['meta'].get('comparable_group') or 'UNG'
        groups_meta.setdefault(g, []).append(pe['id'])

    out = {
        'product': product, 'unit': unit, 'windows': windows,
        'calendar': {'start': calendar[0].isoformat(), 'end': calendar[-1].isoformat(), 'n_days': len(calendar)},
        'data_coverage': {
            'spot': {'n': len(spot), 'first': min(spot).isoformat() if spot else None,
                     'last': max(spot).isoformat() if spot else None},
            'future': {'n': len(future), 'first': min(future).isoformat() if future else None,
                       'last': max(future).isoformat() if future else None},
            'basis': {'n': len(basis), 'first': min(basis).isoformat() if basis else None,
                      'last': max(basis).isoformat() if basis else None},
        },
        'min_n_for_significance': MIN_N_FOR_SIGNIFICANCE,
        'gaps': gaps,
        'groups': groups_meta,
        'events': results,
        'stats': stats,
    }
    if verbose:
        _print_summary(out)
    return out


def _print_summary(out):
    print('=' * 78)
    print('%s 政策事件研究 · Event Study 结果' % out['product'])
    print('交易日历 %s ~ %s（%d 个交易日）' % (out['calendar']['start'], out['calendar']['end'], out['calendar']['n_days']))
    for k, v in out['data_coverage'].items():
        print('  %-6s n=%-5s %s ~ %s' % (k, v['n'], v['first'], v['last']))
    if out['gaps']:
        print('  数据缺口：')
        for g in out['gaps']:
            print('    - ' + g)
    print('-' * 78)
    print('可比分组：')
    for g, ids in out['groups'].items():
        print('  [%s] %d 个事件：%s' % (g, len(ids), ', '.join(map(str, ids))))
    print('-' * 78)
    for anchor in ('market_first_aware', 'publish_date', 'effective_date'):
        if anchor not in out['stats']:
            continue
        any_hit = False
        for w, metrics in out['stats'][anchor].items():
            for metric, groups in metrics.items():
                for g, s in groups.items():
                    if s['n'] and metric == 'future_chg':
                        if not any_hit:
                            print('【锚 = %s】期货{窗口}日变动（元/吨）' % anchor)
                            any_hit = True
                        print('  +%-3d日  组%-4s n=%-2d 均值=%9.1f 中位=%9.1f 正比例=%s  显著性=%s'
                              % (w, g, s['n'], s['mean'], s['median'],
                                 '%.2f' % s['positive_ratio'] if s['positive_ratio'] is not None else '—',
                                 '允许' if s['significance_allowed'] else '样本不足·不计算'))
        if any_hit:
            print('-' * 78)


# --------------------------------------------------------------------------
# 自检：用合成数据验证对齐、缺口处理与显著性门槛
# --------------------------------------------------------------------------
def _selftest():
    # 构造 60 个连续"交易日"（跳过周末）
    days, d = [], date(2020, 1, 1)
    while len(days) < 60:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    prices = {
        'trade_days': [x.isoformat() for x in days],
        'spot': [{'date': x.isoformat(), 'value': 2000 + i * 10} for i, x in enumerate(days)],
        'future': [{'date': x.isoformat(), 'value': 1900 + i * 8} for i, x in enumerate(days)],
        'basis': [],
    }
    cfg = {
        'product': 'TEST', 'unit': '元/吨', 'windows': [1, 5, 10, 20],
        'events': [
            {'id': 'T1', 'name': '合成事件A', 'publish_date': days[10].isoformat(),
             'market_first_aware': days[10].isoformat(), 'effective_date': days[15].isoformat(),
             'comparable_group': 'G1'},
            # 故意制造一个缺口：删掉 days[20] 的现货
            {'id': 'T2', 'name': '合成事件B', 'publish_date': days[19].isoformat(),
             'market_first_aware': days[19].isoformat(), 'comparable_group': 'G1'},
            # 超出数据末端的锚
            {'id': 'T3', 'name': '越界事件', 'publish_date': '2030-01-01',
             'market_first_aware': '2030-01-01', 'comparable_group': 'G1'},
        ],
    }
    prices['spot'] = [r for r in prices['spot'] if r['date'] != days[20].isoformat()]

    res = run(cfg, prices, verbose=False)
    ok = True

    # 1) 对齐：事件A 基准日应为 days[9]，1日窗口终点 days[10]
    a = res['events'][0]['anchors']['market_first_aware']
    assert a['ok'], '事件A 对齐失败'
    assert a['windows'][1]['date'] == days[10].isoformat(), '1日窗口终点错误：%s' % a['windows'][1]['date']
    print('  [OK] 交易日对齐全')

    # 2) 期货变动可算且方向为正
    fchg = a['windows'][1]['future_chg']
    assert fchg is not None and fchg > 0, '期货1日变动异常：%s' % fchg
    print('  [OK] 期货窗口变动计算：%.2f' % fchg)

    # 3) 缺失现货不被插值
    b = res['events'][1]['anchors']['market_first_aware']
    spot_at_gap = b['path'][1]['spot'] if len(b['path']) > 1 else None
    path_dates = [p['date'] for p in b['path']]
    assert days[20].isoformat() in path_dates, '路径应包含缺口日'
    gap_entry = [p for p in b['path'] if p['date'] == days[20].isoformat()][0]
    assert gap_entry['spot'] is None, '缺口日现货应为 None，实际 %r（说明被插值了）' % gap_entry['spot']
    print('  [OK] 缺失价格未被插值，保留为 None')

    # 4) 越界事件被正确拒绝
    assert not res['events'][2]['anchors']['market_first_aware']['ok'], '越界事件应标记为失败'
    print('  [OK] 越界锚定日被拒绝并给出原因')

    # 5) 样本量不足时不计算显著性
    s = res['stats']['market_first_aware'][5]['future_chg']['G1']
    assert s['n'] < MIN_N_FOR_SIGNIFICANCE
    assert s['significance_allowed'] is False and s['p_value'] is None
    print('  [OK] n=%d < %d 时未计算显著性（p_value=None）' % (s['n'], MIN_N_FOR_SIGNIFICANCE))

    # 6) 统计函数正确性：t 检验 p 值对小样本应能算出数值
    big = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    ss = summarize(big)
    assert ss['significance_allowed'] is True and ss['p_value'] is not None
    assert 0 < ss['p_value'] < 1
    assert abs(ss['mean'] - 3.5) < 1e-9
    print('  [OK] t 检验 p 值数值稳定（n=6 -> p=%.4f）' % ss['p_value'])

    # 7) 贝塔函数在经典值上的校验：t=2.0, df=10 -> 双侧 p≈0.0734
    p = _t_pvalue_two_sided(2.0, 10)
    assert abs(p - 0.0734) < 2e-3, 't 分布 p 值不准确：%.5f' % p
    print('  [OK] t 分布数值校验通过（t=2.0, df=10 -> p=%.5f，期望≈0.0734）' % p)

    # 8) 中位数/分位
    q = summarize([1, 2, 3, 4, 5])['quantiles']
    assert abs(q['q0.50'] - 3) < 1e-9 and abs(q['q0.25'] - 2) < 1e-9
    print('  [OK] 分位数计算正确')

    print('全部自检通过。')
    return 0


def main():
    ap = argparse.ArgumentParser(description='政策事件研究 Event Study 计算引擎')
    ap.add_argument('--config', help='events.json 路径')
    ap.add_argument('--prices', help='prices.json 路径')
    ap.add_argument('--out', default='out', help='输出目录')
    ap.add_argument('--selftest', action='store_true', help='运行内置自检')
    a = ap.parse_args()

    if a.selftest:
        sys.exit(_selftest())
    if not a.config or not a.prices:
        ap.error('需要 --config 与 --prices，或使用 --selftest')

    cfg = load_json(a.config)
    prices = load_json(a.prices)
    out = run(cfg, prices)

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'event_stats.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # 扁平 CSV
    lines = ['event_id,event_name,anchor,anchor_date,window,window_end,'
             'spot_base,spot_end,spot_chg,spot_pct,future_base,future_end,future_chg,future_pct,'
             'basis_base,basis_end,basis_chg,comparable_group']
    for pe in out['events']:
        for ank, av in pe['anchors'].items():
            if not av.get('ok'):
                continue
            base = av['windows']['base']
            for w, wd in av['windows'].items():
                if w == 'base' or not wd.get('ok'):
                    continue
                lines.append(','.join([
                    str(pe['id']), '"%s"' % (pe['name'] or ''), ank, av['align']['anchor'],
                    str(w), wd['date'],
                    _s(base['spot']), _s(wd['spot']), _s(wd['spot_chg']), _s(wd['spot_pct']),
                    _s(base['future']), _s(wd['future']), _s(wd['future_chg']), _s(wd['future_pct']),
                    _s(base['basis']), _s(wd['basis']), _s(wd['basis_chg']),
                    str(pe['meta'].get('comparable_group') or 'UNG'),
                ]))
    with open(os.path.join(a.out, 'event_windows.csv'), 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(lines))

    paths = [{'id': pe['id'], 'name': pe['name'],
              'anchors': {k: v.get('path') for k, v in pe['anchors'].items() if v.get('ok')}}
             for pe in out['events']]
    with open(os.path.join(a.out, 'paths.json'), 'w', encoding='utf-8') as f:
        json.dump(paths, f, ensure_ascii=False)

    print('\n已写出：event_stats.json / event_windows.csv / paths.json -> %s' % a.out)


def _s(x):
    return '' if x is None else ('%.4f' % x).rstrip('0').rstrip('.')


if __name__ == '__main__':
    main()
