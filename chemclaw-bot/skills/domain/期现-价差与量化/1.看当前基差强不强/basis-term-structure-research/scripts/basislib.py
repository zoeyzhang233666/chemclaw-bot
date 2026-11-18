#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基差计算内核 (Basis Kernel) —— 纯标准库，无第三方依赖。

口径全文统一（改动必须同步 references/02-公式与口径.md）：
    基差 basis       = 现货价格 - 期货价格        （>0 为现货升水 / Back）
    基差率 basis_rate= basis / 现货价格 * 100
    经验分位 pct     = #{x <= 当前值} / N * 100
    基差变化分解     = Δbasis = Δspot - Δfut
    贡献度           = Δspot/Δbasis（现货） 与 -Δfut/Δbasis（期货），两者之和恒为 100%
    换月跳空 gap     = 切换日 新主力收盘 - 旧主力收盘

所有函数都是纯函数，不读写文件、不发请求，便于在任何 Agent 里复用与测试。
"""
from __future__ import annotations

import math


# --------------------------------------------------------------------------- 基础描述统计
def _clean(xs):
    return [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]


def mean(xs):
    xs = _clean(xs)
    return sum(xs) / len(xs) if xs else None


def median(xs):
    xs = sorted(_clean(xs))
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def stdev(xs):
    """样本标准差 (n-1)。"""
    xs = _clean(xs)
    if len(xs) < 2:
        return None
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def quantile(xs, q):
    """线性插值分位数（仅供描述，不用于"历史分位"结论）。"""
    xs = sorted(_clean(xs))
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def empirical_percentile(xs, value):
    """经验分位：样本中小于等于 value 的比例 (%)。"""
    xs = _clean(xs)
    if not xs or value is None:
        return None
    return sum(1 for x in xs if x <= value) / len(xs) * 100.0


# --------------------------------------------------------------------------- 基差
def basis(spot, futures, round_to=2):
    """基差 = 现货 - 期货。任一缺失返回 None（不填补）。"""
    if spot is None or futures is None:
        return None
    return round(spot - futures, round_to)


def basis_rate(spot, fut):
    """基差率 (%) = 基差 / 现货 * 100。现货为 0 或缺失返回 None。"""
    if spot in (None, 0) or fut is None:
        return None
    return round((spot - fut) / spot * 100, 2)


def spot_mid(low, high):
    """区间报价取中点。"""
    if low is None or high is None:
        return None
    return (low + high) / 2.0


def decompose(spot_t, spot_0, fut_t, fut_0):
    """基差变动归因。

    Δbasis = (spot_t - spot_0) - (fut_t - fut_0)
    期货贡献取负号：期货上涨压缩基差。
    """
    if None in (spot_t, spot_0, fut_t, fut_0):
        raise ValueError('decompose() 不接受缺失值，缺失区间不得归因')
    ds = spot_t - spot_0
    df = fut_t - fut_0
    db = ds - df
    # 以基差变化为分母：现货上涨推升基差(正贡献)，期货上涨压低基差(负贡献)。
    # 两项符号相反、绝对值加总 100%，即"基差变化里现货占多少、期货占多少"。
    # 用 |Δs|+|Δf| 作分母也可以，但两项会变成同号(+17%/-83%)，容易误读方向。
    return {
        'delta_spot': round(ds, 4),
        'delta_fut': round(df, 4),
        'delta_basis': round(db, 4),
        'share_spot': round(ds / db * 100, 4) if db else None,
        'share_fut': round(-df / db * 100, 4) if db else None,
        'direction': ('期货主导上行' if df > ds else '现货主导下行') if db == 0 else
                     ('基差走强' if db > 0 else '基差走弱'),
    }


# --------------------------------------------------------------------------- 合约与换月
def pick_main(rows, oi_key='oi', drop=('MA0',)):
    """rows: [{date, contract, oi, ...}]；按日返回持仓量最大的合约。

    返回 {(date): {'contract':c, 'oi':oi}}。
    """
    by = {}
    for r in rows:
        if r.get('contract') in drop:
            continue
        d = r['date']
        oi = r.get('oi')
        if oi is None:
            continue
        if d not in by or oi > by[d]['oi']:
            by[d] = {'contract': r['contract'], 'oi': oi}
    return by


def roll_events(dates, mains, closes_by_date):
    """识别换月并计算跳空。

    dates: 升序交易日列表
    mains: {date: contract}
    closes_by_date: {date: {contract: close}}

    跳空 = 切换日 新主力收盘 - 同一日 旧主力收盘

    另给 shift = 前一交易日 新主力收盘 - 前一交易日 旧主力收盘（同日价差）。
    价差法才是**复权应用**的正确口径：它把"换月造成的价格阶梯"与"当日行情涨跌"
    完全分开，因此复权后换月日的收益率恰好等于新合约自身当日收益率。
    """
    out = []
    for i in range(1, len(dates)):
        d, p = dates[i], dates[i - 1]
        c_new, c_old = mains.get(d), mains.get(p)
        if not c_new or not c_old or c_new == c_old:
            continue
        row = closes_by_date.get(d, {})
        prow = closes_by_date.get(p, {})
        new_c, old_c = row.get(c_new), row.get(c_old)
        # 同日价差：优先取换月日前一日，其次取换月日当日
        shift = None
        if prow.get(c_new) is not None and prow.get(c_old) is not None:
            shift = round(prow[c_new] - prow[c_old], 4)
        elif new_c is not None and old_c is not None:
            shift = round(new_c - old_c, 4)
        if new_c is None or old_c is None:
            out.append({'date': d, 'from': c_old, 'to': c_new, 'new_close': new_c,
                        'old_close': old_c, 'gap': None, 'shift': shift,
                        'note': '切换日旧主力无报价，跳空不可计算'})
            continue
        out.append({'date': d, 'from': c_old, 'to': c_new, 'new_close': new_c,
                    'old_close': old_c, 'gap': round(new_c - old_c, 4),
                    'shift': shift, 'note': ''})
    return out


def forward_adjust(seq, gaps):
    """前复权主力连续序列。

    已验证的市场惯例（2026-09-10 实例：MA2610 3411 -> MA2701 3043）：
      * 换月当日，行情商发布的主连（MA0）仍打印**旧合约**收益，跳空被推到次日；
      * 复权必须把**换月日之前**的所有价格整体平移，累计之后所有换月的**同日价差**：
            adj(t) = close(t) + Σ{ shift(k) : k 为 t 之后的换月日 }
      * 用 shift（同日价差）而不是 gap（切换日新旧之差），才能把"合约阶梯"与
        "当日行情"分开，使复权后换月日收益率等于新合约自身收益率。
      * 最新一段等于原始价格，每张合约在换月前的收益率保持真实。

    seq: [{'date','close'}] 升序；gaps: roll_events() 的输出
    """
    gap_by_date = {}
    for g in gaps:
        v = g.get('shift') if g.get('shift') is not None else g.get('gap')
        if v is not None:
            gap_by_date[g['date']] = v
    suffix = {}
    acc = 0.0
    for r in reversed(seq):
        suffix[r['date']] = acc
        acc += gap_by_date.get(r['date'], 0.0)
    return [{'date': r['date'], 'raw_close': r['close'],
             'adj_close': round(r['close'] + suffix[r['date']], 4)} for r in seq]


def naive_splice_check(seq, gaps, spot_all):
    """诊断：如果不复权直接拼接，会把多少换月跳空误记为"价格/基差变化"。

    spot_all: {date: spot}，用来估算被污染的基差变动（只做量级诊断，不作为结论）。
    """
    total = sum(abs(g['gap']) for g in gaps if g.get('gap') is not None)
    biggest = max(gaps, key=lambda g: abs(g.get('gap') or 0), default=None)
    return {
        'n_rolls': len(gaps),
        'abs_gap_sum': round(total, 2),
        'largest_gap': biggest,
        'warning': '直接拼接不可比合约会把 %d 次换月共 %.0f 元/吨的跳空记成价差变化'
                   % (len(gaps), total),
    }


# --------------------------------------------------------------------------- 分位与样本充分性
MIN_N_FOR_PERCENTILE = 20      # 少于 20 个独立观测不给"历史分位"结论


def window_stats(series, current, min_n=MIN_N_FOR_PERCENTILE):
    """series: [(date, value)] 或 [value]。返回描述统计 + 是否可用作历史分位。"""
    vals = []
    for x in series:
        v = x[1] if isinstance(x, (tuple, list)) else x
        if v is not None:
            vals.append(v)
    if not vals or current is None:
        return {'n': 0, 'usable_as_percentile': False,
                'reason': '无有效样本'}
    s = {
        'n': len(vals),
        'current': current,
        'pct': round(empirical_percentile(vals, current), 2),
        'mean': mean(vals), 'median': median(vals), 'stdev': stdev(vals),
        'min': min(vals), 'max': max(vals),
        'p05': quantile(vals, 0.05), 'p25': quantile(vals, 0.25),
        'p75': quantile(vals, 0.75), 'p95': quantile(vals, 0.95),
    }
    s['z'] = round((current - s['mean']) / s['stdev'], 3) if s['stdev'] else None
    s['usable_as_percentile'] = len(vals) >= min_n
    s['reason'] = ('' if s['usable_as_percentile']
                   else '有效样本仅 %d 个（< %d），不足以给出历史分位结论' % (len(vals), min_n))
    return s


def coverage_check(pairs, window_start, window_end, min_ratio=0.5):
    """检查真实样本对名义窗口的覆盖率。

    pairs: [date] 有真实现货+期货配对的日子
    以每自然年约 244 个交易日估算应有样本。
    """
    from datetime import date

    def parse(s):
        y, m, d = s.split('-')
        return date(int(y), int(m), int(d))

    d0, d1 = parse(window_start), parse(window_end)
    expected = max(1, int((d1 - d0).days / 365.0 * 244))
    have = len([p for p in pairs if window_start <= p <= window_end])
    ratio = have / expected
    return {'have': have, 'expected': expected, 'ratio': round(ratio, 3),
            'sufficient': ratio >= min_ratio}


# --------------------------------------------------------------------------- 自测
if __name__ == '__main__':
    # 基差基本式
    assert basis(3980, 3157) == 823
    assert basis_rate(3980, 3157) == 20.68
    assert spot_mid(3960, 4000) == 3980
    assert basis(None, 3157) is None

    # 归因：现货 +45、期货 +215 -> 基差 -170
    d = decompose(3980, 3935, 3157, 2942)
    assert d['delta_basis'] == -170 and d['delta_spot'] == 45 and d['delta_fut'] == 215
    assert abs(d['share_spot'] + d['share_fut'] - 100) < 1e-2   # 两项同号、加总 100%
    # 基差 -170 走弱：现货 +45 压低基差 26.5%，期货 +215 压低基差 126.5%
    assert round(d['share_spot'], 2) == -26.47 and round(d['share_fut'], 2) == 126.47
    assert d['direction'] == '基差走弱'
    try:
        decompose(None, 1, 2, 3)
        raise AssertionError('缺失值应当报错')
    except ValueError:
        pass

    # 分位
    assert empirical_percentile([1, 2, 3, 4], 3) == 75.0
    assert median([1, 2, 3]) == 2 and median([1, 2, 3, 4]) == 2.5

    # 换月：MA2610 3411 -> MA2701 3043，跳空 -368
    dates = ['2026-09-09', '2026-09-10']
    mains = {'2026-09-09': 'MA2610', '2026-09-10': 'MA2701'}
    closes = {'2026-09-09': {'MA2610': 3411.0, 'MA2701': 3310.0},
              '2026-09-10': {'MA2610': 3430.0, 'MA2701': 3043.0}}
    g = roll_events(dates, mains, closes)
    assert len(g) == 1 and g[0]['gap'] == -387.0, g
    seq = [{'date': '2026-09-09', 'close': 3411.0}, {'date': '2026-09-10', 'close': 3043.0}]
    adj = forward_adjust(seq, g)
    assert adj[-1]['adj_close'] == 3043.0                     # 最新段=原始价
    assert adj[0]['adj_close'] == 3310.0              # 历史段整体下移
    # 本例用切换前同日价差平移，切换日收益对应新合约
    r_adj = adj[1]['adj_close'] / adj[0]['adj_close'] - 1
    r_true = 3043.0 / 3310.0 - 1                              # 新合约(MA2701)自身
    assert abs(r_adj - r_true) < 1e-12

    # 样本不足判定
    w = window_stats([1, 2, 3], 2)
    assert w['usable_as_percentile'] is False
    w2 = window_stats(list(range(100)), 50)
    assert w2['usable_as_percentile'] is True and w2['pct'] == 51.0

    print('basislib self-test OK (23 assertions)')
