# -*- coding: utf-8 -*-
"""月差（日历价差）分析内核 —— 纯标准库，无第三方依赖。

核心口径（整个 Skill 保持一致）
--------------------------------
* 月差 Spread(X, Y) = Price(X) − Price(Y)     X 在前、Y 在后，顺序写死；
* 期限结构 TS(t, c) = Close(t, c) − Close(t, 最近到期合约)；TS(t, c1) = 0；
* 可比样本必须满足两条：① 合约月份组合相同（同为一月对五月这种日历间隔）；
  ② 距本腿交割的交易日数相近（±window 个交易日）。
  绝对不把剩余到期时间完全不同的两个月差塞进同一个分布；
* 价格变化贡献（对数价差精确分解）：
      ΔlnSpread = ln(x1/x0) − ln(y1/y0) = 近月贡献 + 远月贡献
  两腿口径一致（同为收盘价或同为结算价），且 x、y 在同一交易日都有报价。

本模块只做计算，不做交易建议。
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import os
import re
from bisect import bisect_left

HOLIDAYS_FIX_DATES = [(1, 1), (5, 1), (10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7),
                      (12, 25), (12, 26)]  # 仅为粗估，真实节假日表由调用方传入


# --------------------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------------------
def parse_date(s: str) -> dt.date:
    return dt.date(int(s[:4]), int(s[5:7]), int(s[8:10]))


def iso(d: dt.date) -> str:
    return d.strftime('%Y-%m-%d')


def contract_code(product: str, yymm: str) -> str:
    return f'{product.upper()}{yymm}'


def code_to_delivery(code: str, product_len: int = 2):
    """SA2701 -> (2027, 1)。支持字母长度不等于 product_len 的品种（如 TA/PF/UR/V 等）。"""
    m = re.match(r'^([A-Za-z]+)(\d{4})$', code.strip())
    if not m:
        raise ValueError(f'合约代码格式不正确: {code!r}（应为字母+4位YYMM）')
    yymm = m.group(2)
    yy, mm = int(yymm[:2]), int(yymm[2:])
    if not 1 <= mm <= 12:
        raise ValueError(f'交割月份非法: {code!r}')
    return 2000 + yy, mm


def delivery_date(year: int, month: int) -> dt.date:
    """交割月 15 日作为“交割锚点日”，只用于计算大体剩余期限 T+（用于分层与展示）。"""
    return dt.date(year, month, 15)


def trading_days_between(d0: dt.date, d1: dt.date, holidays=()) -> int:
    """粗略的交易日计数（剔除周六日与给定节假日），用于 T+ 分层与可比匹配。"""
    hset = set(holidays or ())
    if d1 <= d0:
        return 0
    n = 0
    d = d0
    while d < d1:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d not in hset:
            n += 1
    return n


# --------------------------------------------------------------------------------------
# 数据装载
# --------------------------------------------------------------------------------------
class ContractSeries:
    __slots__ = ('code', 'product', 'year', 'month', 'dates', 'idx', 'close', 'settle',
                 'volume', 'oi')

    def __init__(self, code: str, rows: list):
        self.code = code
        self.product = re.match(r'^([A-Za-z]+)', code).group(1).upper()
        self.year, self.month = code_to_delivery(code)
        rows = sorted(rows, key=lambda r: r['date'])
        self.dates = [r['date'] for r in rows]
        self.idx = {d: i for i, d in enumerate(self.dates)}
        self.close = [r['close'] for r in rows]
        self.settle = [r['settle'] for r in rows]
        self.volume = [r['volume'] for r in rows]
        self.oi = [r['oi'] for r in rows]

    # -- 序列访问 -----------------------------------------------------------------
    def last_date(self) -> dt.date:
        return self.dates[-1]

    def first_date(self) -> dt.date:
        return self.dates[0]

    def _pick(self, day: dt.date, field: str, allow_prev: int = 0):
        """严格取当天的值；allow_prev>0 时允许向回找最多 N 个交易日内最近的一个（用于库存等低频数据）。"""
        f = getattr(self, field)
        if day in self.idx:
            v = f[self.idx[day]]
            return v if _valid(v) else None
        if allow_prev:
            i = bisect_left(self.dates, day) - 1
            for k in range(allow_prev):
                if i - k < 0:
                    break
                v = f[i - k]
                if _valid(v):
                    return v
        return None

    def quote(self, day: dt.date, field: str = 'close'):
        """当天报价；缺失返回 None（绝不向前填充价格）。"""
        return self._pick(day, field, allow_prev=0)

    def oi_at(self, day: dt.date):
        return self._pick(day, 'oi', allow_prev=0)

    def quote_with_prev(self, day: dt.date, field: str = 'close'):
        """返回 (price, prev_price, prev_date)：prev 为该合约自身前一个有效交易日。"""
        i = self.idx.get(day)
        if i is None:
            return None, None, None
        p = self.close[i] if field == 'close' else self.settle[i]
        if not _valid(p):
            return None, None, None
        j = i - 1
        while j >= 0:
            q = self.close[j] if field == 'close' else self.settle[j]
            if _valid(q):
                return p, q, self.dates[j]
            j -= 1
        return p, None, None


def _valid(v) -> bool:
    return v is not None and isinstance(v, (int, float)) and math.isfinite(v) and v > 0


class ContractBook:
    """一个品种的全部合约序列（逐合约，不是主力连续）。"""

    def __init__(self, product: str, series: dict, source: str = ''):
        self.product = product.upper()
        self.series = series           # code -> ContractSeries
        self.source = source

    # -- 构建 ---------------------------------------------------------------------
    @classmethod
    def from_dir(cls, rawdir: str, product: str, source: str = '') -> 'ContractBook':
        """从 data/raw/ 读取 <SYMBOL>.csv；结算价 ≤0 或缺失的行整行丢弃并计数。"""
        product = product.upper()
        series = {}
        dropped = []
        for fn in sorted(os.listdir(rawdir)):
            if not fn.lower().endswith('.csv'):
                continue
            sym = fn[:-4].upper()
            if not sym.startswith(product) or not re.search(r'\d{4}$', sym):
                continue
            rows = []
            with open(os.path.join(rawdir, fn), encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    try:
                        rec = {
                            'date': parse_date(r['date']),
                            'close': float(r.get('close') or 0),
                            'settle': float(r.get('settle') or r.get('close') or 0),
                            'volume': float(r.get('volume') or 0),
                            'oi': float(r.get('open_interest') or r.get('oi') or 0),
                        }
                    except (ValueError, KeyError):
                        dropped.append((sym, r.get('date'), 'parse_error'))
                        continue
                    if not _valid(rec['settle']) or not _valid(rec['close']):
                        dropped.append((sym, r.get('date'), 'nonpositive_ohlc'))
                        continue
                    rows.append(rec)
            if rows:
                series[sym] = ContractSeries(sym, rows)
        book = cls(product, series, source)
        book.dropped_rows = dropped
        return book

    # -- 查询 ---------------------------------------------------------------------
    def codes(self) -> list:
        return sorted(self.series)

    def latest_trading_date(self) -> dt.date:
        return max(s.last_date() for s in self.series.values())

    def all_dates(self) -> list:
        ds = set()
        for s in self.series.values():
            ds.update(s.dates)
        return sorted(ds)

    def listed_on(self, day: dt.date, min_oi: float = 0.0) -> list:
        """当天有报价且持仓量≥min_oi 的合约（按交割月升序）。"""
        out = []
        for code, s in self.series.items():
            q = s.quote(day)
            if q is None:
                continue
            oi = s.oi_at(day)
            if min_oi and (oi is None or oi < min_oi):
                continue
            out.append(code)
        return sorted(out, key=lambda c: code_to_delivery(c))

    def active_dates(self, code: str, min_oi: float = 1000.0, min_vol: float = 0.0) -> list:
        """该合约“真实可交易”的日期（持仓量达到门槛），月差只在双方都存活的区间计算。"""
        s = self.series[code]
        return [d for d, oi, v in zip(s.dates, s.oi, s.volume)
                if oi >= min_oi and v >= min_vol]


# --------------------------------------------------------------------------------------
# 月差
# --------------------------------------------------------------------------------------
def spread_series(book: ContractBook, a: str, b: str, price: str = 'close',
                  date_from=None, date_to=None, min_oi: float = 0.0) -> dict:
    """月差 = A − B（A、B 都是具体合约代码）。返回按日序列与口径说明。

    - 只在 A、B **同一天都有报价**（有报价 = 该合约当天有 K 线且有收盘价）时计算；
    - date_from / date_to 为区间过滤；min_oi 用于剔除“刚挂牌、无流动性”的日期。
    """
    if a not in book.series or b not in book.series:
        raise KeyError(f'合约不存在: {[c for c in (a, b) if c not in book.series]}')
    if a == b:
        raise ValueError('A 与 B 不能是同一个合约')
    sa, sb = book.series[a], book.series[b]
    common = sorted(set(sa.dates) & set(sb.dates))
    rows = []
    for d in common:
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        x = sa.quote(d, price)
        y = sb.quote(d, price)
        if x is None or y is None:
            continue
        oa, ob = sa.oi_at(d), sb.oi_at(d)
        if min_oi and ((oa or 0) < min_oi or (ob or 0) < min_oi):
            continue
        da, db = delivery_date(*code_to_delivery(a)), delivery_date(*code_to_delivery(b))
        rows.append({
            'date': d, 'a': x, 'b': y, 'spread': x - y,
            'oi_a': oa, 'oi_b': ob,
            # T+：距本腿“交割锚点日”的近似交易日数，仅用于分层与可比匹配
            'dtd_a': trading_days_between(d, da),
            'dtd_b': trading_days_between(d, db),
        })
    return {'a': a, 'b': b, 'price': price, 'rows': rows,
            'formula': f'月差 = P({a}) − P({b})，单位 元/吨，价格口径 = {"收盘价" if price == "close" else "结算价"}'}


def spread_stats(rows: list, vals: list = None) -> dict:
    """对一个样本序列做描述统计 + 当期值的历史分位（当期值必须来自同一分布样本）。"""
    if vals is None:
        vals = [r['spread'] for r in rows]
    vals = [v for v in vals if v is not None]
    n = len(vals)
    if n == 0:
        return {'n': 0}
    vs = sorted(vals)
    mean = sum(vs) / n
    var = sum((v - mean) ** 2 for v in vs) / (n - 1) if n > 1 else 0.0
    return {
        'n': n, 'min': vs[0], 'max': vs[-1], 'mean': mean, 'median': _pct(vs, 50),
        'std': math.sqrt(var), 'p10': _pct(vs, 10), 'p25': _pct(vs, 25), 'p75': _pct(vs, 75),
        'p90': _pct(vs, 90),
    }


def _pct(sorted_vals: list, p: float) -> float:
    """线性插值分位数（与 numpy 默认 method='linear' 一致），小样本也稳定。"""
    n = len(sorted_vals)
    if n == 0:
        return float('nan')
    if n == 1:
        return sorted_vals[0]
    pos = (p / 100.0) * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def percentile_of(value: float, vals: list, strict: bool = False) -> float:
    """value 在 vals 中的百分位 = 小于它的比例（×100）。strict=True 时为严格小于。"""
    if not vals:
        return float('nan')
    if strict:
        c = sum(1 for v in vals if v < value)
    else:
        c = sum(1 for v in vals if v <= value)
    return 100.0 * c / len(vals)


# --------------------------------------------------------------------------------------
# 可比样本匹配（月差分析最容易被做错的一步）
# --------------------------------------------------------------------------------------
def month_pair_gap(a: str, b: str) -> int:
    """两个合约之间的日历间隔（月数），用来判断“月份组合”是否相同。"""
    ya, ma = code_to_delivery(a)
    yb, mb = code_to_delivery(b)
    return (yb * 12 + mb) - (ya * 12 + ma)


def build_comparable_samples(book: ContractBook, a: str, b: str, date: dt.date,
                             price: str = 'close', dtd_tol: int = 10,
                             min_oi: float = 1000.0, min_sample: int = 5) -> dict:
    """构造“可比历史样本”：同月份组合 + 距本腿交割时间相近（±dtd_tol 交易日）。

    返回每个历史合约对的样本序列与统计量，按可用天数降序。
    """
    gap = month_pair_gap(a, b)
    ya, ma = code_to_delivery(a)
    cur_y, cur_m = date.year, date.month
    pairs = []
    # 枚举历史交割年月与当前相同月差间隔的组合
    for y in range(2020, cur_y + 2):
        for m in range(1, 13):
            ay, am = y, m
            by, bm = y, m + gap
            while bm > 12:
                bm -= 12
                by += 1
            ca = contract_code(book.product, f'{ay % 100:02d}{am:02d}')
            cb = contract_code(book.product, f'{by % 100:02d}{bm:02d}')
            if ca not in book.series or cb not in book.series:
                continue
            if (ay, am) == (ya, ma):
                continue  # 当前这一对单列
            # 用该历史组合在“同一日历日期”上的本腿剩余期限做锚
            live_a = book.series[ca].dates
            if not live_a:
                continue
            # 找到历史合约对中，距离交割时间 ≈ 当前 dtd 的那些交易日
            dtd_now = trading_days_between(date, delivery_date(ya, ma))
            lo, hi = max(0, dtd_now - dtd_tol), dtd_now + dtd_tol
            rows = spread_series(book, ca, cb, price=price, min_oi=min_oi)['rows']
            sel = [r for r in rows if lo <= r['dtd_a'] <= hi]
            if len(sel) < min_sample:
                continue
            vals = [r['spread'] for r in sel]
            pairs.append({
                'pair': [ca, cb], 'gap_months': gap,
                'first': iso(sel[0]['date']), 'last': iso(sel[-1]['date']),
                'stats': spread_stats(sel, vals), 'vals': vals,
                'last_value': sel[-1]['spread'],
            })
    pairs.sort(key=lambda p: -p['stats']['n'])
    return {'gap_months': gap, 'dtd_tol': dtd_tol, 'price': price, 'pairs': pairs}


def historical_same_month_value(book: ContractBook, a: str, b: str, date: dt.date,
                                price: str = 'close', dtd_tol: int = 5,
                                min_oi: float = 1000.0) -> dict:
    """上一年“相同月份组合”在同一剩余期限（±dtd_tol 交易日）附近的月差，作面包屑参考。

    不是“去年同一天”的硬对齐：若当期合约去年尚未挂牌，会明确返回 unavailable。
    """
    ya, ma = code_to_delivery(a)
    gap = month_pair_gap(a, b)
    try:
        prev_year = ya - 1
        prev_a = contract_code(book.product, f'{prev_year % 100:02d}{ma:02d}')
    except Exception:  # noqa: BLE001
        return {'available': False, 'reason': '上年合约代码无法构造'}
    by, bm = prev_year, ma + gap
    while bm > 12:
        bm -= 12
        by += 1
    prev_b = contract_code(book.product, f'{by % 100:02d}{bm:02d}')
    if prev_a not in book.series or prev_b not in book.series:
        return {'available': False, 'reason': f'上年组合 {prev_a}/{prev_b} 无数据',
                'pair': [prev_a, prev_b]}
    dtd_now = trading_days_between(date, delivery_date(ya, ma))
    rows = spread_series(book, prev_a, prev_b, price=price, min_oi=min_oi)['rows']
    if not rows:
        return {'available': False, 'reason': f'{prev_a}/{prev_b} 无有效月差样本',
                'pair': [prev_a, prev_b]}
    # 该历史组合生命周期内，最接近 dtd_now 的那一天
    best = min(rows, key=lambda r: abs(r['dtd_a'] - dtd_now))
    if abs(best['dtd_a'] - dtd_now) > dtd_tol:
        return {'available': False, 'pair': [prev_a, prev_b],
                'reason': f'{prev_a} 上市太晚，没有距交割 {dtd_now}±{dtd_tol} 个交易日的样本',
                'closest': {'date': iso(best['date']), 'dtd_a': best['dtd_a'],
                            'value': best['spread']}}
    return {'available': True, 'pair': [prev_a, prev_b], 'date': iso(best['date']),
            'value': best['spread'], 'dtd_a': best['dtd_a'], 'dtd_now': dtd_now,
            'diff': best['spread'] - _cur_value(book, a, b, date, price, min_oi)}


def _cur_value(book: ContractBook, a: str, b: str, date: dt.date, price: str,
               min_oi: float) -> float:
    rows = [r for r in spread_series(book, a, b, price=price, min_oi=min_oi)['rows']
            if r['date'] <= date]
    return rows[-1]['spread'] if rows else float('nan')


# --------------------------------------------------------------------------------------
# 期限结构
# --------------------------------------------------------------------------------------
def term_structure(book: ContractBook, date: dt.date, price: str = 'close',
                   min_oi: float = 0.0) -> list:
    """当日完整期限结构。首行（最近到期合约）作为基准，TS 归零。"""
    codes = book.listed_on(date, min_oi=min_oi)
    rows = []
    anchor = None
    for c in codes:
        s = book.series[c]
        p = s.quote(date, price)
        if p is None:
            continue
        y, m = code_to_delivery(c)
        dtd = trading_days_between(date, delivery_date(y, m))
        if anchor is None:
            anchor = p
        rows.append({'contract': c, 'year': y, 'month': m, 'price': p,
                     'settle': s.settle[s.idx[date]] if date in s.idx else None,
                     'oi': s.oi_at(date), 'volume': s.volume[s.idx[date]] if date in s.idx else None,
                     'dtd': dtd, 'ts': p - anchor,
                     'ts_pct': (p / anchor - 1) * 100 if anchor else None})
    return rows


def term_structure_shape(rows: list) -> dict:
    """判断结构形态：contango / backwardation / humped / flat / mixed。"""
    if len(rows) < 2:
        return {'shape': 'n/a', 'slope': None}
    x = [r['ts'] for r in rows]
    diffs = [x[i + 1] - x[i] for i in range(len(x) - 1)]
    up = sum(1 for d in diffs if d > 0)
    down = sum(1 for d in diffs if d < 0)
    tot = len(diffs)
    first_last = x[-1] - x[0]
    if up == tot:
        shape = 'contango（全月正向、远月升水）'
    elif down == tot:
        shape = 'backwardation（全月反向、近月升水）'
    elif up / tot >= 0.7:
        shape = 'dominant contango（多数月份上行）'
    elif down / tot >= 0.7:
        shape = 'dominant backwardation（多数月份下行）'
    else:
        shape = 'humped / mixed（先扬后抑或结构不均匀）'
    return {'shape': shape, 'slope': first_last,
            'slope_per_month': first_last / max(1, len(rows) - 1), 'n': len(rows)}


# --------------------------------------------------------------------------------------
# 价格变化贡献分解
# --------------------------------------------------------------------------------------
def decompose(book: ContractBook, a: str, b: str, d0: dt.date, d1: dt.date,
              price: str = 'close') -> dict:
    """月差变化的近月/远月贡献（对数精确分解，加和=ΔlnSpread）。

    ΔlnSpread = ln(Pa1/Pa0) − ln(Pb1/Pb0)
    - 近月贡献 = +ln(Pa1/Pa0)：近月涨 → 月差走阔（正贡献）
    - 远月贡献 = −ln(Pb1/Pb0)：远月涨 → 月差收窄（负贡献）
    ΔSpread(元/吨) ≈ Spread0 × ΔlnSpread，故也可换算成“约 X 元/吨”。
    """
    sa, sb = book.series.get(a), book.series.get(b)
    if not sa or not sb:
        return {'error': '合约不存在'}
    pa0, pa0p, _ = sa.quote_with_prev(d0, price) if d0 not in sa.idx else (sa.quote(d0, price), None, None)
    pb0 = sb.quote(d0, price)
    pa1 = sa.quote(d1, price)
    pb1 = sb.quote(d1, price)
    pa0 = pa0 if pa0 is not None else pa0p
    if None in (pa0, pb0, pa1, pb1):
        return {'error': '区间端点在两腿都缺少报价，无法分解（不插值）',
                'detail': {'pa0': pa0, 'pb0': pb0, 'pa1': pa1, 'pb1': pb1}}
    la, lb = math.log(pa1 / pa0), math.log(pb1 / pb0)
    dln = la - lb
    s0, s1 = pa0 - pb0, pa1 - pb1
    ds = s1 - s0
    return {
        'a': a, 'b': b, 'price': price, 'd0': iso(d0), 'd1': iso(d1),
        'pa0': pa0, 'pa1': pa1, 'pb0': pb0, 'pb1': pb1, 's0': s0, 's1': s1, 'ds': ds,
        'chg_a': pa1 - pa0, 'chg_b': pb1 - pb0,
        'r_a': (pa1 / pa0 - 1) * 100, 'r_b': (pb1 / pb0 - 1) * 100,
        'contrib_a_dln': la, 'contrib_b_dln': -lb, 'dln': dln,
        'contrib_a_cny': s0 * la, 'contrib_b_cny': -s0 * lb,
        'residual_cny': ds - s0 * dln,
        'share_a': la / dln * 100 if abs(dln) > 1e-12 else float('nan'),
    }


def decompose_window(book: ContractBook, a: str, b: str, d1: dt.date, n: int = 5,
                     price: str = 'close') -> list:
    """逐日贡献：最近 n 个交易日每天的月差变化由谁来推动。"""
    out = []
    sd = spread_series(book, a, b, price=price)['rows']
    days = [r['date'] for r in sd if r['date'] <= d1]
    for i in range(max(1, len(days) - n), len(days)):
        d0, dd = days[i - 1], days[i] if i > 0 else (None, None)
        if d0 is None or dd is None:
            continue
        dec = decompose(book, a, b, d0, dd, price)
        if 'error' in dec:
            continue
        out.append({'date': iso(dd), 'ds': dec['ds'], 'chg_a': dec['chg_a'],
                    'chg_b': dec['chg_b'], 'contrib_a': dec['contrib_a_dln'],
                    'contrib_b': dec['contrib_b_dln']})
    return out


# --------------------------------------------------------------------------------------
# 换月/移仓扫描（同一“近月-远月组合”不连续时要提醒）
# --------------------------------------------------------------------------------------
def roll_off(book: ContractBook, date: dt.date, min_oi: float = 1000.0) -> dict:
    """当前挂牌合约里谁的持仓量在快速衰减（即将失去流动性）。"""
    codes = book.listed_on(date, min_oi=0)
    out = []
    for c in codes:
        s = book.series[c]
        act = [d for d in s.dates if d <= date]
        if len(act) < 21:
            continue
        i = s.idx[act[-1]]
        oi_now = s.oi[i]
        oi_20 = s.oi[max(0, i - 20)]
        out.append({'contract': c, 'oi': oi_now, 'oi_20d_ago': oi_20,
                    'chg_pct': (oi_now / oi_20 - 1) * 100 if oi_20 else None,
                    'dtd': trading_days_between(date, delivery_date(*code_to_delivery(c)))})
    return {'rows': out}


# --------------------------------------------------------------------------------------
# 数据质量自检
# --------------------------------------------------------------------------------------
def data_quality(book: ContractBook) -> list:
    """ERROR / WARN 列表。有 ERROR 不得出结论。"""
    issues = []
    if not book.series:
        issues.append(('ERROR', 'EMPTY', '没有任何合约序列'))
        return issues
    for code, s in book.series.items():
        if len(s.dates) < 5:
            issues.append(('WARN', code, f'序列仅 {len(s.dates)} 根K线'))
        # 时间逆序 / 重复
        if s.dates != sorted(s.dates):
            issues.append(('ERROR', code, '日期未按升序'))
        if len(set(s.dates)) != len(s.dates):
            issues.append(('ERROR', code, '日期重复'))
        # 单日跳变 > 15%（超过涨跌停幅度说明数据可疑）
        for i in range(1, len(s.close)):
            a, b = s.close[i - 1], s.close[i]
            if b and a and abs(b / a - 1) > 0.15:
                issues.append(('WARN', code, f'{iso(s.dates[i])} 单日跳变 {(b / a - 1) * 100:.1f}%'))
        # 收盘价落在 [最低,最高] 之外
        last_settle = s.settle[-1]
        if last_settle and abs(last_settle / s.close[-1] - 1) > 0.1:
            issues.append(('WARN', code, f'最后结算价 {last_settle} 与收盘 {s.close[-1]} 偏离 >10%'))
    # 不同合约最后日期不一致（停牌/退市）
    last = {}
    for code, s in book.series.items():
        last.setdefault(s.last_date(), []).append(code)
    latest = max(last)
    for d, cs in last.items():
        if (latest - d).days > 4:
            issues.append(('INFO', ','.join(cs), f'最后交易日 {iso(d)}，早于最新 {iso(latest)}（已摘牌）'))
    return issues


def nearest_date(dates: list, target: dt.date) -> dt.date:
    """在给定交易日集合里取 ≤ target 的最近一天。"""
    if not dates:
        raise ValueError('空日期序列')
    i = bisect_left(dates, target) - 1
    if i + 1 < len(dates) and dates[i + 1] == target:
        return target
    return dates[max(0, i)]
