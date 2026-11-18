# -*- coding: utf-8 -*-
"""cost_engine.py —— 上下游成本传导通用引擎（品种无关）

把「上游 → 下游」的成本关系写成可复核的模型：

  · 单耗成本模型：理论原料成本 = Σ(单耗_i × 原料_i 价格)，默认值 + 低/高单耗敏感性
  · 加工价差：下游价格 − 理论原料成本（价差口径，**不是利润**）
  · 阶段分解：Δ下游价 = Δ原料成本 + Δ加工价差（同口径下严格恒等）
  · 传导率 / 有符号传导率 / 滞后相关（仅作观察，绝不作因果证明）
  · 背离区间：加工价差相对其滚动中枢的 z 分数异常段
  · 异常值标注：单日价差跳变超过阈值时标注，不下结论

单位约定（最容易出错的地方，务必先读）：
  所有价格列在进入本模块前，必须已折算为「元/吨、同一税基、同一交货口径」。
  上游若原为美元/吨（如 CFR 中国），必须先按
      上游价(元/吨) = CFR(美元/吨) × 汇率 × (1+关税率) × (1+增值税率)
  折算成元/吨，再进模型。**不要**在模型里再做一次汇率/税率换算。

用法：
  import cost_engine as ce
  res = ce.run_extended(project, calendar=None, breakpoints=[...])
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import sys

# ------------------------------------------------------------------ 基础工具


def d(s):
    s = str(s).replace('-', '')
    return _dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def iso(dt_) -> str:
    return dt_.strftime('%Y-%m-%d')


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1.0) * 100.0


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def std(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def pct_rank(xs, v):
    """v 在 xs 中的分位（0-100）。"""
    xs = [x for x in xs if x is not None]
    if not xs or v is None:
        return None
    return sum(1 for x in xs if x <= v) / len(xs) * 100.0


def pearson(xs, ys):
    pairs = [(a, b) for a, b in zip(xs, ys) if a is not None and b is not None]
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def diffs(xs):
    out = [None]
    for a, b in zip(xs[:-1], xs[1:]):
        out.append(None if a is None or b is None else b - a)
    return out


def rolling(xs, w, fn):
    out = []
    for i in range(len(xs)):
        seg = [x for x in xs[max(0, i - w + 1):i + 1] if x is not None]
        out.append(fn(seg) if seg else None)
    return out


# ------------------------------------------------- 1. 单耗成本模型


def unit_cost(price_up_cny, spec, params=None):
    """单原料吨下游成本（元/吨下游） = 单耗 × 上游价格（元/吨）。

    spec: {"name","unit"(t/t),"low","high","scale"(默认1)}
    注意：上游价格必须已是元/吨同口径；这里不再做任何汇率/税换算。
    """
    if price_up_cny is None:
        return None
    unit = spec.get('unit', (params or {}).get('unit_default'))
    if unit is None:
        raise ValueError('原料 %s 缺少单耗 unit' % spec.get('name'))
    return unit * price_up_cny * spec.get('scale', 1.0)


def total_material_cost(up_prices_cny: dict, materials: list, params=None):
    """Σ 单耗×价格。任一原料缺价 → 返回 (None, detail)，不猜。"""
    total = 0.0
    detail = {}
    for spec in materials:
        p = up_prices_cny.get(spec['name'])
        c = unit_cost(p, spec, params)
        detail[spec['name']] = {'price': p, 'unit': spec.get('unit'), 'cost': c}
        if c is None:
            return None, detail
        total += c
    return total, detail


def processing_spread(down_price_cny, cost):
    """加工价差（元/吨） = 下游价格 − 理论原料成本。

    **这是价差，不是利润**：不含能源、辅料、催化剂、人工、折旧、财务费用、
    检维修、包装、运费、库存损益等。给出时必须原样保留这句限定。
    """
    if down_price_cny is None or cost is None:
        return None
    return down_price_cny - cost


def cost_share(cost, down_price_cny):
    if not down_price_cny:
        return None
    return cost / down_price_cny * 100.0


# ------------------------------------------------- 2. 价格对齐


def align_series(series: dict, start, end, calendar=None):
    """多列价格对齐成同一日历；缺失用前值填充但记录填充天数（不悄悄补数）。"""
    start, end = d(start), d(end)
    if calendar:
        days = [iso(x) if not isinstance(x, str) else x for x in calendar]
        days = [x for x in days if start <= d(x) <= end]
    else:
        all_days = sorted({x for s in series.values() for x in s})
        days = [x for x in all_days if start <= d(x) <= end]
    out = {'dates': days, 'filled': {}}
    for k, s in series.items():
        cols, last, filled = [], None, 0
        for key in days:
            v = s.get(key, s.get(key.replace('-', '')))
            if v is None:
                cols.append(last); filled += 1
            else:
                cols.append(v); last = v
        out[k] = cols
        out['filled'][k] = filled
    return out


# ------------------------------------------------- 3. 阶段分解


def decompose(dates, cost_col, down_col, spread_col, breakpoints):
    """按阶段分解：Δ下游价 = Δ原料成本 + Δ加工价差（残差应恒为 0）。"""
    idx = {x: i for i, x in enumerate(dates)}
    stages = []
    for a, b in zip(breakpoints[:-1], breakpoints[1:]):
        if a not in idx or b not in idx:
            raise ValueError('断点不在交易日历内：%s / %s' % (a, b))
        i, j = idx[a], idx[b]
        st = {'start': a, 'end': b, 'days': j - i,
              'cost_start': cost_col[i], 'cost_end': cost_col[j],
              'down_start': down_col[i], 'down_end': down_col[j],
              'spread_start': spread_col[i], 'spread_end': spread_col[j]}
        if None not in (cost_col[i], cost_col[j]):
            st['d_cost'] = cost_col[j] - cost_col[i]
        if None not in (down_col[i], down_col[j]):
            st['d_down'] = down_col[j] - down_col[i]
            st['d_down_pct'] = pct(down_col[j], down_col[i])
        if None not in (spread_col[i], spread_col[j]):
            st['d_spread'] = spread_col[j] - spread_col[i]
        if st.get('d_cost') is not None and st.get('d_down') is not None:
            st['identity_resid'] = st['d_down'] - (st['d_cost'] + (st.get('d_spread') or 0.0))
            if st['d_cost'] != 0:
                st['pass_through'] = st['d_down'] / st['d_cost']
                st['spread_absorb'] = 1 - st['pass_through']
                # 传导率的"有效性"：上游阶段内变动幅度太小（<成本 1%）时，
                # 比值不稳定，不能当结论用。用 valid 标记，报告里降级展示。
                st['pass_through_valid'] = abs(st['d_cost']) >= 0.01 * abs(cost_col[i] or 1)
                if not st['pass_through_valid']:
                    st['pass_through_note'] = (
                        '阶段内上游成本仅变动 %.1f 元（占成本 %.2f%%），分母过小，'
                        '该传导率不稳定，仅供参照' %
                        (st['d_cost'], abs(st['d_cost']) / abs(cost_col[i] or 1) * 100))
        stages.append(st)
    return stages


# ------------------------------------------------- 4. 传导统计（仅观察）


def pass_through_stats(up, down, up_cost, max_lag=20):
    """滞后相关 + 水平回归弹性。

    结论只能表述为「同期/滞后 k 日的相关系数为 x」，**不能**据此断言因果：
    两条曲线同涨同跌可能来自共同驱动（原油、宏观、情绪），也可能互为因果。
    """
    r_up, r_down = diffs(up), diffs(down)
    lag_corr = []
    for k in range(0, max_lag + 1):
        x = r_up[:len(r_up) - k] if k else r_up
        y = r_down[k:] if k else r_down
        c = pearson(x, y)
        lag_corr.append({'lag': k, 'corr': None if c is None else round(c, 4)})
    valid = [x for x in lag_corr if x['corr'] is not None]
    best = max(valid, key=lambda z: z['corr']) if valid else None
    pairs = [(c, dn) for c, dn in zip(up_cost, down) if c is not None and dn is not None]
    beta = None
    if len(pairs) > 3:
        cs = [p[0] for p in pairs]; dn = [p[1] for p in pairs]
        mc, md = mean(cs), mean(dn)
        v = sum((x - mc) ** 2 for x in cs)
        if v > 0:
            beta = sum((x - mc) * (y - md) for x, y in pairs) / v
    return {
        'lag_corr': lag_corr, 'best_lag': best, 'level_beta': beta,
        'corr_level_up_down': pearson(up, down),
        'corr_diff_up_down': pearson(r_up, r_down),
        'corr_level_cost_down': pearson(up_cost, down),
    }


# ------------------------------------------------- 5. 背离识别


def find_divergences(dates, spread, window=20, z_thr=1.5, min_days=5):
    """加工价差相对自身滚动中枢的 z 分数，连续越阈 ≥min_days 记为一个背离区间。

    z > +thr：价差走阔（下游跌得比原料慢，或原料跌得更快）
    z < -thr：价差压缩（原料涨得快，下游没跟上）
    只标记异常，归因必须另有装置/供需事件证据，否则写「未找到可核查事件」。
    """
    m = rolling(spread, window, mean)
    sd = rolling(spread, window, std)
    z = [None if (v is None or mu is None or s is None or s == 0) else (v - mu) / s
         for v, mu, s in zip(spread, m, sd)]
    segs, cur = [], None
    for i, zi in enumerate(z):
        sign = 0 if zi is None or abs(zi) < z_thr else (1 if zi > 0 else -1)
        if cur is not None and cur['sign'] == sign and sign != 0:
            cur['end_idx'] = i
        else:
            if cur is not None and (cur['end_idx'] - cur['start_idx'] + 1) >= min_days:
                segs.append(cur)
            cur = {'sign': sign, 'start_idx': i, 'end_idx': i} if sign else None
    if cur is not None and (cur['end_idx'] - cur['start_idx'] + 1) >= min_days:
        segs.append(cur)
    out = []
    for s in segs:
        i, j = s['start_idx'], s['end_idx']
        vals = [v for v in spread[i:j + 1] if v is not None]
        zs = [v for v in z[i:j + 1] if v is not None]
        out.append({
            'type': 'spread_widen' if s['sign'] > 0 else 'spread_compress',
            'start': dates[i], 'end': dates[j], 'days': j - i + 1,
            'spread_start': spread[i], 'spread_end': spread[j],
            'spread_mean': mean(vals), 'spread_chg': None if None in (spread[i], spread[j])
            else spread[j] - spread[i],
            'z_mean': round(mean(zs), 2) if zs else None,
            'z_extreme': round(max(zs, key=abs), 2) if zs else None,
        })
    return out, z


def flag_outliers(dates, spread, jump=400.0):
    """单日价差跳变超阈值 → 标注为「待核异常」，不自动剔除。"""
    out = []
    for i in range(1, len(spread)):
        a, b = spread[i - 1], spread[i]
        if a is None or b is None:
            continue
        if abs(b - a) >= jump:
            out.append({'date': dates[i], 'prev': a, 'now': b, 'jump': b - a})
    return out


def flat_runs(dates, xs, min_len=4):
    """找出连续取值不变的台阶（评估价常见），返回 [{start,end,value,days}]。

    评估价是"阶梯式"更新的：上游可能连续十几日不调价，而下游每日变动，
    这会让"同阶段传导率"失真（分母几乎是 0，传导率被放大到几倍）。
    报告里必须披露台阶情况，否则读图的人会误以为下游脱离成本。
    """
    runs, i, n = [], 0, len(xs)
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1] is not None and xs[i] is not None and xs[j + 1] == xs[i]:
            j += 1
        if xs[i] is not None and (j - i + 1) >= min_len:
            runs.append({'start': dates[i], 'end': dates[j], 'value': xs[i], 'days': j - i + 1})
        i = j + 1
    return runs


def step_metrics(dates, up, down):
    """衡量两列价格的"更新频率"差异，作为口径可比性证据。"""
    def changes(xs):
        return [i for i in range(1, len(xs)) if xs[i] is not None and xs[i - 1] is not None
                and xs[i] != xs[i - 1]]
    cu, cd = changes(up), changes(down)
    return {
        'up_change_days': len(cu), 'down_change_days': len(cd),
        'n': len(dates) - 1,
        'up_change_ratio': len(cu) / max(1, len(dates) - 1),
        'down_change_ratio': len(cd) / max(1, len(dates) - 1),
        'up_flat_runs': flat_runs(dates, up),
        'down_flat_runs': flat_runs(dates, down),
    }


def flat_run_context(dates, upstream_px, down_px, min_len=4):
    """逐个 ≥min_len 日的上游台阶，记录台阶内下游的累计变动。

    用途：说明"上游没动、下游却动了"的区间到底是下游定价脱离成本，
    还是上游评估价没更新。输出的是观察事实，不是推断的上游真值。
    """
    out = []
    for run in flat_runs(dates, upstream_px, min_len):
        s, e = run['start'], run['end']
        idx = [i for i, x in enumerate(dates) if s <= x <= e]
        if not idx:
            continue
        d0, d1 = down_px[idx[0]], down_px[idx[-1]]
        out.append({
            'start': s, 'end': e, 'days': run['days'], 'up_value': run['value'],
            'down_start': d0, 'down_end': d1,
            'down_chg': None if None in (d0, d1) else d1 - d0,
            'down_chg_pct': None if None in (d0, d1) or not d0 else (d1 / d0 - 1) * 100,
        })
    return out


# ------------------------------------------------- 6. 主流程


def _robust_stats(dates, spread, jump):
    """剔除"单日跳变超阈值"的样本点后重算统计，用于和原始口径并列展示。"""
    bad = set()
    for i in range(1, len(spread)):
        a, b = spread[i - 1], spread[i]
        if a is not None and b is not None and abs(b - a) >= jump:
            bad.add(dates[i]); bad.add(dates[i - 1])
    kept = [v for dt_, v in zip(dates, spread) if v is not None and dt_ not in bad]
    if not kept:
        return None
    return {'n': len(kept), 'excluded': len(bad),
            'mean': mean(kept), 'median': quantile(kept, 0.5),
            'min': min(kept), 'max': max(kept),
            'p10': quantile(kept, 0.1), 'p90': quantile(kept, 0.9)}


def run_extended(project, calendar=None, breakpoints=None, rolling_w=20, z_thr=1.5,
                 max_lag=20, real_spread=None, outlier_jump=400.0):
    """完整分析。project 见 references/data-contract.md。"""
    p = project
    params = p.get('params', {})
    mat = p['materials']
    # 便利支持：若 upstream/downstream 直接内联了 series，则自动登记到 price_series
    p.setdefault('price_series', {})
    for side, default_key in (('upstream', 'up'), ('downstream', 'down')):
        node = p[side]
        if 'series' in node and isinstance(node['series'], dict):
            k = node.get('series_key') or node.get('name') or default_key
            node['series_key'] = k
            p['price_series'].setdefault(k, node['series'])
        node.setdefault('series_key', node.get('name') or default_key)
    up_key = p['upstream']['series_key']
    down_key = p['downstream']['series_key']
    key_of = {m['name']: p.get('material_series', {}).get(m['name'], m['name']) for m in mat}
    keys = {up_key, down_key} | set(key_of.values())
    series = {k: p['price_series'][k] for k in keys if k in p['price_series']}
    al = align_series(series, p['window']['start'], p['window']['end'], calendar)
    dates = al['dates']
    up, down = al[up_key], al[down_key]

    mat_cost, spread, spread_low, spread_high, detail = [], [], [], [], []
    for i in range(len(dates)):
        prices = {m['name']: al[key_of[m['name']]][i] for m in mat}
        tot, det = total_material_cost(prices, mat, params)
        detail.append(det); mat_cost.append(tot)
        spread.append(processing_spread(down[i], tot))
        lo = hi = 0.0; ok = True
        for m in mat:
            pr = prices.get(m['name'])
            if pr is None:
                ok = False; break
            lo += m.get('low', m.get('unit')) * pr
            hi += m.get('high', m.get('unit')) * pr
        spread_high.append(down[i] - lo if ok and down[i] is not None else None)
        spread_low.append(down[i] - hi if ok and down[i] is not None else None)

    segs, z = find_divergences(dates, spread, window=rolling_w, z_thr=z_thr)
    stats = pass_through_stats(up, down, mat_cost, max_lag=max_lag)
    bps = breakpoints or [dates[0], dates[-1]]
    stages = decompose(dates, mat_cost, down, spread, bps)

    reconcile = None
    if real_spread:
        rs = [real_spread.get(x) for x in dates]
        pairs = [(a, b) for a, b in zip(rs, spread) if a is not None and b is not None]
        if pairs:
            reconcile = {
                'rows': len(pairs),
                'model_mean': mean([b for a, b in pairs]),
                'real_mean': mean([a for a, b in pairs]),
                'gap_mean': mean([b - a for a, b in pairs]),
                'corr': pearson([a for a, b in pairs], [b for a, b in pairs]),
                'series_real': rs,
            }

    valid = [s for s in spread if s is not None]
    return {
        'dates': dates, 'up': up, 'down': down,
        'material_cost': mat_cost, 'spread': spread,
        'spread_low_unit': spread_high, 'spread_high_unit': spread_low,
        'detail': detail, 'filled': al['filled'],
        'z': z, 'divergences': segs, 'stages': stages, 'stats': stats,
        'reconcile': reconcile,
        'outliers': flag_outliers(dates, spread, outlier_jump),
        'steps': step_metrics(dates, up, down),
        'flat_context': flat_run_context(dates, up, down),
        'spread_stats': {
            'n': len(valid), 'mean': mean(valid), 'median': quantile(valid, 0.5),
            'min': min(valid) if valid else None, 'max': max(valid) if valid else None,
            'p10': quantile(valid, 0.1), 'p90': quantile(valid, 0.9),
            'latest': valid[-1] if valid else None,
            'latest_rank': pct_rank(valid, valid[-1]) if valid else None,
        },
        # 稳健口径：剔除单日跳变超阈值的样本后再算分位，避免一次数据异常拉宽区间
        'spread_stats_robust': _robust_stats(dates, spread, outlier_jump),
        'cost_share_latest': cost_share(mat_cost[-1], down[-1]),
        'sensitivity': {
            'base_mean': mean(valid),
            'low_unit_mean': mean([x for x in spread_high if x is not None]),
            'high_unit_mean': mean([x for x in spread_low if x is not None]),
        },
    }


if __name__ == '__main__':
    print(__doc__)
