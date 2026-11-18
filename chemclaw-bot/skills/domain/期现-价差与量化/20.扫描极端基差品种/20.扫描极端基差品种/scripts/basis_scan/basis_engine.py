# -*- coding: utf-8 -*-
"""basis_engine.py — 基差序列构建 + 品种内经验分位 + 极端筛选（纯计算，无网络）

口径红线（写入 SKILL.md / 报告 / 工作簿，不得省略）
--------------------------------------------------
1. 基差 = 现货基准价 − 期货价（严格此符号，正=现货升水）。跨品种绝不比较基差「金额」。
2. 分位只在「品种自身」的历史分布内计算；经验分位 = 历史日数中严格小于当日的比例，
   并同时给出中位秩（相等计数按 1/2 计入）与含当日的经验 CDF，三口径并列，避免边界争议。
3. 历史窗口 = 最近 N 年（默认 3 年），以数据最新可用日为锚点向前推。
4. 现货与期货按「同一交易日」对齐；期货缺该日 -> 当日不出基差（不插值、不前值填充）。
5. 样本不足（有效日数 < min_obs，默认 120）时，只给「数据不足」状态，不给分位。
6. 高低分位只是「历史位置描述」，不是多空信号。
"""
from __future__ import annotations

import bisect
import csv
import datetime as dt
import json
import math
import os
from statistics import median

DEFAULT_MIN_OBS = 120
ROLL_JUMP_WARN_YUAN = 30.0   # 换月当日基差跳变告警阈值（元/吨）


# --------------------------------------------------------------------- utils
def add_years(d: dt.date, years: int) -> dt.date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:                      # 2/29
        return d.replace(year=d.year + years, day=28)


def to_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s[:10])


def pct_strict(hist: list[float], x: float) -> float:
    """严格小于 x 的比例（不含相等），0~1。"""
    if not hist:
        return float('nan')
    return bisect.bisect_left(hist, x) / len(hist)


def pct_midrank(hist: list[float], x: float) -> float:
    """中位秩：小于按 0、相等按 1/2 计入，0~1。"""
    if not hist:
        return float('nan')
    lo = bisect.bisect_left(hist, x)
    hi = bisect.bisect_right(hist, x)
    return (lo + 0.5 * (hi - lo)) / len(hist)


def pct_le(hist: list[float], x: float) -> float:
    """含当日的经验 CDF：小于等于 x 的比例（最小值为 0，最大值为 1）。"""
    if not hist:
        return float('nan')
    return bisect.bisect_right(hist, x) / len(hist)


def quantile(sorted_hist: list[float], q: float) -> float:
    """线性插值分位数（sorted_hist 已排序）。"""
    if not sorted_hist:
        return float('nan')
    if q <= 0:
        return sorted_hist[0]
    if q >= 1:
        return sorted_hist[-1]
    pos = (len(sorted_hist) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_hist) - 1)
    frac = pos - lo
    return sorted_hist[lo] * (1 - frac) + sorted_hist[hi] * frac


def r2(x, n=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ''
    return round(float(x), n)


# ------------------------------------------------------------------ loaders
def load_spot(path: str) -> list[dict]:
    rows = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            try:
                rows.append(dict(date=r['date'][:10], price=float(r['price']),
                                 src_type=r.get('src_type', ''), unit=r.get('unit', ''),
                                 fut_contract=r.get('fut_contract', ''),
                                 fut_close=r.get('fut_close', ''),
                                 url=r.get('url', '')))
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(rows, key=lambda r: r['date'])


def load_series(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            try:
                r['close'] = float(r['close'])
                r['oi'] = float(r.get('oi') or 0)
            except (TypeError, ValueError):
                continue
            r['is_roll'] = int(float(r.get('is_roll') or 0))
            out.append(r)
    return sorted(out, key=lambda r: r['date'])


# ---------------------------------------------------------- basis assembly
def build_basis(spot_rows: list[dict], fut_rows: list[dict]) -> tuple[list[dict], dict]:
    """按同一交易日对齐，返回 [date, spot, fut, basis, symbol, is_roll] 和覆盖率统计。"""
    fut_idx = {r['date']: r for r in fut_rows}
    out, missing = [], 0
    for s in spot_rows:
        f = fut_idx.get(s['date'])
        if f is None:
            missing += 1
            continue
        out.append(dict(date=s['date'], spot=s['price'], fut=f['close'],
                        basis=round(s['price'] - f['close'], 4),
                        symbol=f['symbol'], is_roll=f['is_roll'],
                        fut_oi=f['oi'], src_type=s['src_type'],
                        src_fut_contract=s.get('fut_contract', ''), url=s.get('url', ''),
                        unit=s.get('unit', '吨')))
    cov = dict(spot_days=len(spot_rows), fut_days=len(fut_rows), matched=len(out),
               spot_unmatched=missing, first=out[0]['date'] if out else None,
               last=out[-1]['date'] if out else None)
    return out, cov


# ------------------------------------------------------------- statistics
def scan_product(code: str, name: str, basis_rows: list[dict], window_years: int = 3,
                 threshold: float = 0.10, min_obs: int = DEFAULT_MIN_OBS,
                 change_window: int = 21, anchor: str | None = None) -> dict:
    """对单个品种做「品种内」历史分位与极端判定。"""
    if not basis_rows:
        return dict(code=code, name=name, status='数据不足', reason='无可用基差样本')
    last = anchor or basis_rows[-1]['date']
    start = add_years(to_date(last), -window_years).isoformat()
    win = [r for r in basis_rows if start <= r['date'] <= last]
    if len(win) < min_obs:
        return dict(code=code, name=name, status='数据不足',
                    reason='窗口内有效样本 %d < 最小要求 %d' % (len(win), min_obs),
                    n_obs=len(win), window_start=start, window_end=last)
    vals = sorted(r['basis'] for r in win)
    cur = win[-1]
    x = cur['basis']
    cur_i = len(win) - 1
    prev = win[max(0, cur_i - change_window)]
    prev5 = win[max(0, cur_i - 5)]
    p_s = pct_strict(vals, x)
    p_m = pct_midrank(vals, x)
    p_l = pct_le(vals, x)
    hi_lim, lo_lim = 1 - threshold, threshold
    if p_m <= lo_lim:
        flag = '低位极端'
    elif p_m >= hi_lim:
        flag = '高位极端'
    else:
        flag = '常态'
    i_min = min(range(len(win)), key=lambda i: win[i]['basis'])
    i_max = max(range(len(win)), key=lambda i: win[i]['basis'])
    # 换月日基差跳变（换月伪跳空披露）
    roll_jumps = []
    for i in range(1, len(win)):
        if win[i]['is_roll']:
            jump = win[i]['basis'] - win[i - 1]['basis']
            roll_jumps.append(dict(date=win[i]['date'], from_symbol=win[i - 1]['symbol'],
                                   to_symbol=win[i]['symbol'], jump=round(jump, 2)))
    big_roll = [r for r in roll_jumps if abs(r['jump']) >= ROLL_JUMP_WARN_YUAN]
    return dict(
        code=code, name=name, status='OK',
        window_years=window_years, window_start=start, window_end=last,
        n_obs=len(win), n_window_days=(to_date(last) - to_date(start)).days + 1,
        date=cur['date'], spot=cur['spot'], fut=cur['fut'], symbol=cur['symbol'],
        basis=x, basis_yuan=r2(x), basis_pct_spot=r2(100 * x / cur['spot'], 2) if cur['spot'] else '',
        pct_strict=r2(100 * p_s, 1), pct_midrank=r2(100 * p_m, 1), pct_le=r2(100 * p_l, 1),
        pct_used=r2(100 * p_m, 1), rank_ascending=round(p_m * len(vals) + 0.5, 1),
        flag=flag, extreme=flag != '常态',
        hi_lim_pct=r2(100 * hi_lim, 1), lo_lim_pct=r2(100 * lo_lim, 1),
        q10=r2(quantile(vals, 0.10)), q25=r2(quantile(vals, 0.25)), q50=r2(quantile(vals, 0.50)),
        q75=r2(quantile(vals, 0.75)), q90=r2(quantile(vals, 0.90)),
        mean=r2(sum(vals) / len(vals)), std=r2(math.sqrt(sum((v - sum(vals) / len(vals)) ** 2
                                                            for v in vals) / (len(vals) - 1)), 2)
        if len(vals) > 1 else '',
        hist_min=r2(vals[0]), hist_max=r2(vals[-1]),
        hist_min_date=win[i_min]['date'], hist_max_date=win[i_max]['date'],
        pmax_gap=r2(cur['basis'] - vals[-1]), pmin_gap=r2(cur['basis'] - vals[0]),
        basis_1w_ago=r2(prev5['basis']), chg_1w=r2(x - prev5['basis']),
        basis_1m_ago=r2(prev['basis']), chg_1m=r2(x - prev['basis']),
        chg_1m_date=prev['date'],
        chg_1m_pct_of_spot=r2(100 * (x - prev['basis']) / prev['spot'], 2) if prev['spot'] else '',
        pct_1m_ago=r2(100 * pct_midrank(vals, prev['basis']), 1),
        pct_delta_1m=r2(100 * (p_m - pct_midrank(vals, prev['basis'])), 1),
        spot_1m_ago=r2(prev['spot']), fut_1m_ago=r2(prev['fut']),
        spot_chg_1m=r2(cur['spot'] - prev['spot']), fut_chg_1m=r2(cur['fut'] - prev['fut']),
        roll_count=len(roll_jumps), roll_jumps_big=big_roll,
        months_with_data=sorted({r['date'][:7] for r in win}),
    )


def build_monthly(basis_rows: list[dict]) -> list[dict]:
    """月度基差（末值 + 均值 + 样本数），供图表与工作簿月度表使用。"""
    by = {}
    for r in basis_rows:
        by.setdefault(r['date'][:7], []).append(r)
    out = []
    for k in sorted(by):
        v = by[k]
        out.append(dict(month=k, n=len(v), basis_mean=r2(sum(x['basis'] for x in v) / len(v)),
                        basis_last=r2(v[-1]['basis']), spot_last=r2(v[-1]['spot']),
                        fut_last=r2(v[-1]['fut'])))
    return out


def percentile_bucket(pct) -> str:
    """把分位映射到 10 档（0-10% ... 90-100%），仅用于展示分布。"""
    try:
        p = float(pct)
    except (TypeError, ValueError):
        return 'NA'
    lo = int(p // 10) * 10
    if lo >= 100:
        lo = 90
    return '%d-%d%%' % (lo, lo + 10)
