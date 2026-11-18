# -*- coding: utf-8 -*-
"""spreadlib —— 跨品种月差（近远月价差）计算内核

设计原则
--------
1. **逐合约、不换月**：只用逐合约日线，绝不用主力连续合约（连续合约换月会产生假跳变）。
2. **一对合约组合 = 一个独立分布**：不同月份组合绝不合并成一个"月差分布"。
3. **可比样本三条件**：同一品种、同一(近月,远月)组合、同一"剩余期限"（周数）对齐的比较月。
4. **样本不足就报不足**：N 低于阈值直接标 insufficient，不给分位数。
5. **价格为缺失/为零/合约已到期就留空**：绝不插值、绝不向前填充。

口径
----
- 月差（近月减远月）：spread = P_near − P_far        （单位：元/吨）
- 定义排除近月，远月必须晚于近月（far_index > near_index）
- 价格主口径 = 结算价 settle（交易所官方）；参考口径 = 收盘价 close
- 只统计"有效报价"日：settle 为 NULL 或 <=0、或当日成交量与持仓量同时为 0 视为无效
"""
from __future__ import annotations

import bisect
import csv
import datetime as dt
import glob
import json
import os
import re
from collections import defaultdict

# ----------------------------------------------------------------------------
# 日期工具
# ----------------------------------------------------------------------------


def d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def months_between(y1, m1, y2, m2):
    return (y2 - y1) * 12 + (m2 - m1)


def contract_end(y, m):
    """交割月最后一个交易日近似：交割月中旬（第10个交易日 ≈ 15 日）。"""
    if m == 12:
        return dt.date(y, 12, 20)
    return dt.date(y, m, 20)


def quarter_of(m):
    return (m - 1) // 3 + 1


# ----------------------------------------------------------------------------
# 数据装载
# ----------------------------------------------------------------------------


class Contract:
    __slots__ = ("product", "y", "m", "dates", "settle", "close", "volume", "oi", "first", "last")

    def __init__(self, product, y, m):
        self.product, self.y, self.m = product, y, m
        self.dates, self.settle, self.close, self.volume, self.oi = [], [], [], [], []
        self.first = self.last = None

    @property
    def symbol(self):
        return f'{self.product}{self.y % 100:02d}{self.m:02d}'

    def valid(self, i):
        """该日是否有可用的有效报价。"""
        s = self.settle[i]
        if s is None or s <= 0:
            return False
        if (self.volume[i] or 0) == 0 and (self.oi[i] or 0) == 0:
            return False
        return True

    def close_at(self, date):
        """取 date 当日或之前最近一个交易日的收盘/结算；超出区间返回 None（不填充）。"""
        i = bisect.bisect_right(self.dates, date) - 1
        if i < 0:
            return None
        return self.settle[i], self.close[i], self.volume[i], self.oi[i], self.dates[i]


def _f(x):
    x = (x or '').strip()
    if not x:
        return None
    try:
        v = float(x.replace(',', ''))
    except ValueError:
        return None
    return v


def load_contracts(rawdir):
    """读取 raw/<SYM>.csv → {product: {symbol: Contract}}"""
    out = defaultdict(dict)
    for fp in glob.glob(os.path.join(rawdir, '*.csv')):
        m = re.fullmatch(r'([A-Z]{1,3})(\d{2})(\d{2})\.csv', os.path.basename(fp))
        if not m:
            continue
        p, y, mo = m.group(1), 2000 + int(m.group(2)), int(m.group(3))
        c = Contract(p, y, mo)
        with open(fp, encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                try:
                    c.dates.append(d(row['date']))
                except Exception:
                    continue
                c.settle.append(_f(row.get('settle')))
                c.close.append(_f(row.get('close')))
                c.volume.append(_f(row.get('volume')))
                c.oi.append(_f(row.get('open_interest')))
        if c.dates:
            c.first, c.last = c.dates[0], c.dates[-1]
            out[p][c.symbol] = c
    return dict(out)


# ----------------------------------------------------------------------------
# 月差定义
# ----------------------------------------------------------------------------


def spread_label(near, far):
    return f'{near}-{far}'


def parse_label(label):
    a, b = label.split('-')
    return a, b


def compute_pair_series(near: Contract, far: Contract, basis='settle'):
    """同一对合约的日度月差序列（按两者共同交易日对齐，缺任一边即跳过）。"""
    idx = {dt_: i for i, dt_ in enumerate(far.dates)}
    out = []
    for i, dt_ in enumerate(near.dates):
        j = idx.get(dt_)
        if j is None:
            continue
        if not (near.valid(i) and far.valid(j)):
            continue
        pn = near.settle[i] if basis == 'settle' else near.close[i]
        pf = far.settle[j] if basis == 'settle' else far.close[j]
        if pn is None or pf is None:
            continue
        out.append({
            'date': dt_, 'near': pn, 'far': pf, 'spread': round(pn - pf, 2),
            'near_oi': near.oi[i], 'far_oi': far.oi[j],
        })
    return out


def series_as_of(seq, as_of):
    """截至 as_of（含）的序列。"""
    return [r for r in seq if r['date'] <= as_of]


def series_on(seq, target):
    """恰好在 target 交易日的值；没有就返回 None（不取最近值，避免口径漂移）。"""
    for r in seq:
        if r['date'] == target:
            return r
    return None


# ----------------------------------------------------------------------------
# 可比历史样本（核心）
# ----------------------------------------------------------------------------


def comparable_sample(all_contracts, product, near_sym, far_sym, as_of,
                      annual_only=True, min_bars=20):
    """构造与"当前这对合约组合"可比的历年样本（**每历史年份 1 个样本**）。

    对齐口径：剩余期限 = 近月交割月结束日 − 观测日 的**整周数**取整
    （floor(days/7)）。当前组合剩余 W 周 → 每年取 floor 后等于 W 的那一个交易日
    （同一年内若有多个，取距 as_of 月日最近的一个），保证：
      同一品种 × 同一(近月,远月)组合 × 同一剩余期限周数。

    不用"±N 周全收"是因为那样每年会塞进 20 个相邻交易日，样本高度自相关，
    分位数会被同一段行情重复计数而失真。

    返回: list of {date, spread, year, week_to_near, near, far, near_sym, far_sym}
    """
    res = []
    ny, nm = 2000 + int(near_sym[-4:-2]), int(near_sym[-2:])
    fy, fm = 2000 + int(far_sym[-4:-2]), int(far_sym[-2:])
    near_end = contract_end(ny, nm)
    cur_w = int((near_end - as_of).days // 7)

    for year in sorted({c.y for c in all_contracts.values()}):
        if annual_only and year == ny:
            continue
        near_c = all_contracts.get(f'{product}{year % 100:02d}{nm:02d}')
        far_c = all_contracts.get(f'{product}{year % 100:02d}{fm:02d}')
        if not near_c or not far_c:
            continue
        h_end = contract_end(year, nm)
        if h_end >= near_end:            # 只要比当前组合更早的年份
            continue
        seq = compute_pair_series(near_c, far_c)
        if len(seq) < min_bars:
            continue
        cands = [r for r in seq if int((h_end - r['date']).days // 7) == cur_w]
        if not cands:
            # 该周恰好无完整双边报价（如节假日），退一步取最接近的日期，并标注
            best = min(seq, key=lambda r: abs((h_end - r['date']).days - (cur_w * 7)))
            off = (h_end - best['date']).days - cur_w * 7
            if abs(off) > 7:
                continue
            pick = best
            exact = False
        else:
            # 同年多个候选时，取月日最接近 as_of 的那一天
            def mdd(x):
                return abs((x['date'].month * 31 + x['date'].day) - (as_of.month * 31 + as_of.day))
            pick = min(cands, key=mdd)
            exact = True
        res.append({
            'date': pick['date'], 'spread': pick['spread'], 'year': year,
            'week_to_near': round((h_end - pick['date']).days / 7.0, 2),
            'near': pick['near'], 'far': pick['far'],
            'near_sym': near_c.symbol, 'far_sym': far_c.symbol,
            'week_aligned_exact': exact,
        })
    res.sort(key=lambda x: x['date'])
    return res


# ----------------------------------------------------------------------------
# 分位数与评级
# ----------------------------------------------------------------------------


def percentile_rank(value, sample, side='two'):
    """value 在 sample 中的分位（0-100）。

    side='two'  : 用"不超过"口径 ((<v)+0.5*(==v))/N*100，双侧极限都能识别
    side='above': 历史中 <= value 的比例（低值 = 极度反向）
    side='below': 历史中 >= value 的比例（低值 = 极度正向）
    """
    n = len(sample)
    if n == 0:
        return None
    less = sum(1 for s in sample if s < value)
    eq = sum(1 for s in sample if s == value)
    if side == 'above':
        return (less + eq) / n * 100.0
    if side == 'below':
        return (n - less) / n * 100.0
    return (less + 0.5 * eq) / n * 100.0


def quantile(sample, q):
    """线性插值分位数（q in [0,1]）。"""
    if not sample:
        return None
    s = sorted(sample)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def zscore(value, sample):
    if len(sample) < 2:
        return None
    mu = sum(sample) / len(sample)
    var = sum((x - mu) ** 2 for x in sample) / (len(sample) - 1)
    sd = var ** 0.5
    if sd == 0:
        return None
    return (value - mu) / sd


def classify(pct_two, z, n, min_n, thresholds):
    """极端程度评级。返回 (等级, 方向说明)。

    只有两侧都可以判断时才给"正向/反向"标签：分位接近 0 或接近 100。
    """
    if n < min_n:
        return '样本不足', '不可比'
    low, high, ext_low, ext_high = thresholds['low'], thresholds['high'], thresholds['ext_low'], thresholds['ext_high']
    if pct_two <= ext_low:
        return '极端(近月贴水)', 'near_far_discount'   # 近月远低于历史 → 月差极低
    if pct_two >= ext_high:
        return '极端(近月升水)', 'near_far_premium'
    if pct_two <= low:
        return '偏高(近月贴水)', 'near_far_discount'
    if pct_two >= high:
        return '偏高(近月升水)', 'near_far_premium'
    if z is not None and abs(z) >= thresholds.get('z_alert', 2):
        return '偏离(Z≥2)', 'z_deviation'
    return '正常', 'normal'


DEFAULT_THRESHOLDS = {'low': 20, 'high': 80, 'ext_low': 5, 'ext_high': 95, 'z_alert': 2,
                      'min_n': 20, 'min_n_scan': 30}


# ----------------------------------------------------------------------------
# 单一品种的期限结构
# ----------------------------------------------------------------------------


def term_structure(product_contracts, as_of):
    """返回当日挂牌合约曲线（按交割月排序），并标注主力。"""
    rows = []
    for sym, c in product_contracts.items():
        got = c.close_at(as_of)
        if got is None:
            continue
        settle, close, vol, oi, rowdate = got
        if rowdate != as_of:
            # 该合约当日无报价（可能已到期），不进入曲线
            continue
        if (settle is None or settle <= 0) and (close is None or close <= 0):
            continue
        rows.append({'symbol': sym, 'y': c.y, 'm': c.m,
                     'settle': settle, 'close': close, 'volume': vol, 'oi': oi,
                     'oi_yi': round((oi or 0) / 1e4, 2)})
    rows.sort(key=lambda r: (r['y'], r['m']))
    if rows:
        main = max(rows, key=lambda r: r['oi'] or 0)
        for r in rows:
            r['is_main'] = (r['symbol'] == main['symbol'])
    return rows


def list_pairs(rows, max_month_gap=None, min_oi=500, require_main=False):
    """从期限结构里枚举可行的近月-远月组合。"""
    pairs = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            gap = months_between(a['y'], a['m'], b['y'], b['m'])
            if gap <= 0:
                continue
            if max_month_gap and gap > max_month_gap:
                continue
            if (a['oi'] or 0) < min_oi or (b['oi'] or 0) < min_oi:
                continue
            if require_main and not (a.get('is_main') or b.get('is_main')):
                continue
            pairs.append((a, b, gap))
    return pairs
