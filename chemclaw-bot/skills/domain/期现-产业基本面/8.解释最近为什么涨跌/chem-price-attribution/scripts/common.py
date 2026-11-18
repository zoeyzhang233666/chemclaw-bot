# -*- coding: utf-8 -*-
"""common.py —— 期现-产业基本面归因 Skill 的公共工具。

原则：本模块只做"机械计算"，不做任何口径推断。
凡是需要口径判断的地方（含税/不含税、口径是否可比、数据是否缺失），一律由 case.json 显式声明，
本模块遇到缺失值只返回 None / 'ND'，绝不插值、绝不猜。
"""
from __future__ import annotations

import bisect
import csv
import datetime as dt
import json
import math
import os
import statistics as st

ND = None

# ---------------------------------------------------------------- 文件与序列


def jload(path):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def jdump(obj, path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(clean(obj), f, ensure_ascii=False, indent=1)


def clean(o):
    """浮点规范化：保留 4 位，避免 2960.0000000001 这类噪声进报告。"""
    if isinstance(o, float):
        v = round(o, 4)
        return v
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o


def load_csv(path, date_col, value_col):
    out = {}
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            d, v = r.get(date_col, ''), r.get(value_col, '')
            if not d or v in ('', '~', None):
                continue
            try:
                out[_norm_date(d)] = float(v)
            except ValueError:
                continue
    return out


def load_json_series(path, date_col, value_col):
    raw = jload(path)
    out = {}
    if isinstance(raw, dict):
        it = raw.items()
        for k, v in it:
            if isinstance(v, dict):
                v = v.get(value_col)
                if isinstance(v, dict):
                    v = v.get('close')
            if v in ('', '~', None):
                continue
            try:
                out[_norm_date(k)] = float(v)
            except (ValueError, TypeError):
                continue
        return out
    for r in raw:
        d = r.get(date_col)
        v = r.get(value_col)
        if v in ('', '~', None):
            continue
        try:
            out[_norm_date(d)] = float(v)
        except (ValueError, TypeError):
            continue
    return out


def _norm_date(s):
    s = str(s).strip()
    if len(s) == 8 and s.isdigit():
        return '%s-%s-%s' % (s[:4], s[4:6], s[6:])
    if len(s) == 10 and s[4] != '-':
        try:
            return dt.date.fromisoformat(s.replace('/', '-')).isoformat()
        except ValueError:
            return s
    return s


# ---------------------------------------------------------------- 区间与窗口


def d2(s):
    return dt.date.fromisoformat(_norm_date(s))


def in_win(d, start, end):
    return d2(start) <= d2(d) <= d2(end)


def series_in(series, start, end):
    return {k: v for k, v in series.items() if in_win(k, start, end)}


def last_on_or_before(series, d):
    ks = sorted(series)
    i = bisect.bisect_right(ks, d) - 1
    return (ks[i], series[ks[i]]) if i >= 0 else (None, None)


def first_on_or_after(series, d):
    ks = sorted(series)
    i = bisect.bisect_left(ks, d)
    return (ks[i], series[ks[i]]) if i < len(ks) else (None, None)


def value_at_end(series, start, end):
    """窗口首末值：用"≤end 的最后一个观测"和"≥start 的第一个观测"。"""
    d0, v0 = first_on_or_after(series, start)
    d1, v1 = last_on_or_before(series, end)
    return d0, v0, d1, v1


def window_change(series, start, end):
    d0, v0, d1, v1 = value_at_end(series, start, end)
    if v0 is None or v1 is None:
        return {'ok': False, 'reason': 'ND'}
    return {'ok': True, 'start_date': d0, 'start_value': v0, 'end_date': d1, 'end_value': v1,
            'abs_change': v1 - v0, 'pct_change': (v1 / v0 - 1) * 100 if v0 else None}


# ---------------------------------------------------------------- 描述统计


def pctiles(values):
    return {p: percentile(values, p) for p in (5, 10, 25, 50, 75, 90, 95)}


def percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def pctile_rank(values, x):
    """x 在样本中的分位（0-100）：严格小于 x 的比例 + 等于的一半。"""
    if not values or x is None:
        return None
    lt = sum(1 for v in values if v < x)
    eq = sum(1 for v in values if v == x)
    return (lt + 0.5 * eq) / len(values) * 100


def zscore(values, x):
    if not values or x is None or len(values) < 3:
        return None
    mu = st.mean(values)
    sd = st.pstdev(values)
    return None if sd == 0 else (x - mu) / sd


def corr(a, b):
    n = min(len(a), len(b))
    if n < 3:
        return None
    a, b = a[:n], b[:n]
    ma, mb = st.mean(a), st.mean(b)
    sa, sb = st.pstdev(a), st.pstdev(b)
    if sa == 0 or sb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n * sa * sb)


def ols_beta(a, b):
    """b = alpha + beta * a，返回 (beta, alpha, r2)，a、b 为收益率序列。"""
    n = min(len(a), len(b))
    if n < 5:
        return None, None, None
    a, b = a[:n], b[:n]
    ma, mb = st.mean(a), st.mean(b)
    va = sum((x - ma) ** 2 for x in a)
    if va == 0:
        return None, None, None
    beta = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / va
    alpha = mb - beta * ma
    ssr = sum((y - (alpha + beta * x)) ** 2 for x, y in zip(a, b))
    sst = sum((y - mb) ** 2 for y in b)
    return beta, alpha, (1 - ssr / sst if sst else None)


def rsi(values, n=14):
    """Wilder RSI，输入为按时间排序的收盘序列。"""
    v = list(values)
    if len(v) <= n:
        return None
    gains, losses = [], []
    for i in range(1, len(v)):
        d = v[i] - v[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = st.mean(gains[:n]); al = st.mean(losses[:n])
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - 100 / (1 + rs)


def rsi_series(series, n=14):
    ks = sorted(series)
    out = {}
    for i in range(n, len(ks)):
        seg = [series[k] for k in ks[:i + 1]]
        out[ks[i]] = rsi(seg, n)
    return out


# ---------------------------------------------------------------- 事件对齐


def align_events(events, price_series, window_days, price_key='date'):
    """把事件对齐到"事件后第一个交易日"，并计算窗口内价格变动。

    返回每条事件：event_date / next_trade_date / lag_trade_days / lag_cal_days /
                 px_before / px_after_{w}d / chg_window
    """
    ks = sorted(price_series)
    out = []
    for e in events:
        ed = _norm_date(e.get('date') or e.get(price_key))
        i = bisect.bisect_left(ks, ed)
        nxt = ks[i] if i < len(ks) else None
        prev = ks[i - 1] if i > 0 else None
        rec = dict(e)
        rec['next_trade_date'] = nxt
        rec['lag_trade_days'] = (d2(nxt) - d2(ed)).days if nxt else None
        rec['px_before'] = price_series.get(prev) if prev else None
        rec['px_next'] = price_series.get(nxt) if nxt else None
        j = bisect.bisect_left(ks, nxt) + window_days if nxt else None
        rec['px_after_wd'] = price_series.get(ks[j]) if (j is not None and j < len(ks)) else None
        rec['after_date'] = ks[j] if (j is not None and j < len(ks)) else None
        if rec['px_next'] and rec['px_after_wd']:
            rec['chg_window_pct'] = (rec['px_after_wd'] / rec['px_next'] - 1) * 100
        else:
            rec['chg_window_pct'] = None
        out.append(rec)
    return out


# ---------------------------------------------------------------- 证据分级

EVIDENCE_LEVELS = {
    'E1': '直接数据支持：同期可量化指标与价格同向变动且量级可核',
    'E2': '数据+事件时间吻合：有事件记录，且对应指标在窗口内确有变动',
    'E3': '仅时间吻合：事件/表态与价格异动同窗，但缺少可比指标数据',
    'E4': '缺乏证据/无法检验：无数据、无法对齐，或方向相反',
}

DIRECTION_Z = 1.0          # 显著异常阈值（同期标准差倍数）
TTC_HORIZON = 3            # 事件前置允许的交易日前置数


def grade_driver(measure, price_dir, event_dir=None):
    """给单一驱动打分。measure 为一个 dict：
        {
          'has_data': bool,
          'z': float|None,            # 指标自身变动相对自身历史的 z 值
          'direction': 'up'|'down'|None,
          'event_hooked': bool,       # 是否有时点明确的事件
          'same_sign': bool|None      # 方向是否支持当前行情
        }
    返回 (level, reason)
    """
    if not measure.get('has_data'):
        return 'E4', '无可用同期数据，无法检验'
    z = measure.get('z')
    sig = (z is not None and abs(z) >= DIRECTION_Z)
    same = measure.get('same_sign')
    if same is False:
        return 'E4', '指标方向与价格异动方向相反'
    if sig and same and not measure.get('event_hooked'):
        return 'E1', '指标显著变动（|z|≥1.0）且方向一致'
    if measure.get('event_hooked') and (sig or measure.get('event_confirmed')):
        return 'E2', '有事件记录，且指标在窗口内确有变动'
    if measure.get('event_hooked'):
        return 'E3', '事件与异动同窗，但缺少可比指标数据'
    return 'E4', '数据未达显著，且无时点明确的事件'


def fmt(v, nd=2):
    if v is None:
        return '—'
    if isinstance(v, str):
        return v
    return ('%.' + str(nd) + 'f') % v
