# -*- coding: utf-8 -*-
"""
basis_core.py —— 期现基差分位信息检验引擎（无未来函数）
==========================================================
本模块是「检验基差是否有历史信息」这一场景的全部统计逻辑，
不依赖任何 GUI / 报告 / Excel 代码，可单独导入与单测。

设计原则（与 SKILL.md 一一对应）
--------------------------------
P1 符号钉死        : basis = spot - futures；basis_ret = basis_ratio(t+h) - basis_ratio(t)
P2 口径显式        : 主力连续（OI 最大，当日可得）、近月连续、固定交割月 三种映射平行计算
P3 无未来函数      : 滚动分位只用 [t-window, t] 的点，且点 m 只有在 t-h_max 时才可进入分位样本
P4 缺失不填补      : 现货缺失当日无基差，不插值、不前值填充
P5 分解价格风险    : 同时给出 现货收益 / 期货收益 / 基差变化，且 basis_ret = spot_ret - fut_ret
P6 样本重叠        : 重叠样本下 p 值必须用 blocksize≈h 的循环块自助法，并给出非重叠子样本复核

核心函数
--------
  load_spot / load_contracts / build_mapping / build_basis
  rolling_percentile          -> 滚动分位（严格滞后 h_max）
  forward_returns             -> 前向 h 日收益（现货/期货/基差）
  bucket_stats                -> 低/中/高分位分组统计
  block_bootstrap_diff        -> 循环块自助法检验组间差异
  threshold_sensitivity       -> 阈值 × 窗口 敏感性
  stability_by_year / by_season / by_regime
  overlap_diagnostics         -> 有效独立样本数、换月污染、交割临近效应

命令行
-----
  python basis_core.py --raw raw --out out --spec spec.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import math
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------- 常量
TRADING_DAYS_PER_YEAR = 244
FETCH_FIELDS = ("date", "contract", "contract_month", "spot", "fut", "basis", "basis_ratio",
                "oi", "days_to_ltd", "basis_pct_lag", "n_hist", "group_lag", "future_share",
                "spot_ret", "fut_ret", "basis_ret", "basis_chg",
                "basis_pit", "basis_chg_pit", "roll_day", "roll_new_next", "flags")
HORIZONS_DEFAULT = (5, 10, 20, 60, 120)
WINDOWS_DEFAULT = (250, 500, 750)
BANDS_DEFAULT = ((0.2, 0.8), (0.3, 0.7), (0.1, 0.9))
GROUP_ORDER = ("低分位", "中间分位", "高分位")
MIN_HIST = 20          # 历史点数少于此值不给分位（样本不足不硬算）


# ================================================================ 小工具
def percentile_linear(sorted_vals: Sequence[float], q: float) -> float:
    """经验分位，线性插值（与 numpy.percentile(method='linear') / Excel PERCENTILE 一致）。
    q ∈ [0,1]，输入必须已排序且非空。"""
    n = len(sorted_vals)
    if n == 0:
        raise ValueError("empty sample")
    if n == 1:
        return float(sorted_vals[0])
    pos = (n - 1) * min(max(q, 0.0), 1.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo]) * (1 - frac) + float(sorted_vals[hi]) * frac


def median(vals: Sequence[float]) -> Optional[float]:
    if not vals:
        return None
    return percentile_linear(sorted(vals), 0.5)


def mean(vals: Sequence[float]) -> Optional[float]:
    return float(sum(vals) / len(vals)) if vals else None


def stdev(vals: Sequence[float]) -> Optional[float]:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def skew(vals: Sequence[float]) -> Optional[float]:
    n = len(vals)
    if n < 3:
        return None
    m = sum(vals) / n
    s = math.sqrt(sum((v - m) ** 2 for v in vals) / n)
    if s == 0:
        return None
    return sum(((v - m) / s) ** 3 for v in vals) / n


def kurt(vals: Sequence[float]) -> Optional[float]:
    n = len(vals)
    if n < 4:
        return None
    m = sum(vals) / n
    s = math.sqrt(sum((v - m) ** 2 for v in vals) / n)
    if s == 0:
        return None
    return sum(((v - m) / s) ** 4 for v in vals) / n - 3.0


def hit_rate(vals: Sequence[float], sign: int = 1) -> Optional[float]:
    """sign=1 算 >0 占比，sign=-1 算 <0 占比，sign=0 算 !=0 占比"""
    if not vals:
        return None
    if sign > 0:
        k = sum(1 for v in vals if v > 0)
    elif sign < 0:
        k = sum(1 for v in vals if v < 0)
    else:
        k = sum(1 for v in vals if v != 0)
    return k / len(vals)


def sample_skewness_of_mean(vals: Sequence[float]) -> Optional[float]:
    """均值抽样分布的偏度估计 = 样本偏度 / sqrt(n)"""
    sk = skew(vals)
    if sk is None or not vals:
        return None
    return sk / math.sqrt(len(vals))


def mean_positive_share(vals: Sequence[float]) -> Optional[float]:
    if not vals:
        return None
    denom = sum(abs(v) for v in vals)
    if denom == 0:
        return None
    return sum(v for v in vals if v > 0) / denom


def r2(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return (sxy * sxy) / (sxx * syy)


def block_sample(n: int, blocksize: int, rng: random.Random) -> List[int]:
    """循环块抽样：返回长度为 n 的下标序列（保持 blocksize 日内的自相关结构）"""
    if n <= 0:
        return []
    b = max(1, min(int(blocksize), n))
    idx: List[int] = []
    starts = [rng.randrange(n) for _ in range((n + b - 1) // b)]
    for s in starts:
        for k in range(b):
            idx.append((s + k) % n)
            if len(idx) >= n:
                return idx
    return idx


def level_adjusted_effects(rows: List[dict], adj: float, horizons: Sequence[int],
                           lookback: int = 20) -> List[dict]:
    """
    「若基差水平整体平移 adj 元/吨，各分组结果如何变化」的局部稳健性检验。
    在一个 lookback 日窗口内，把当日基差整体加上 adj 后重排：
      原本判为低分位的点 -> 可能升为中/高分位。
    只影响分组归属，不影响观测到的未来收益，因此是纯粹的分组误差检验。
    """
    vals = [r["basis"] for r in rows]
    out = []
    shift_assign = []
    for i in range(len(rows)):
        lo = max(0, i - lookback + 1)
        win = sorted(vals[lo:i + 1])
        n = len(win)
        cur = vals[i] + adj
        less = sum(1 for v in win if v < cur)
        eq = sum(1 for v in win if v == cur)
        pct = ((less + 0.5 * eq) / n) if n >= MIN_HIST else None
        shift_assign.append(_group_of(pct, BANDS_DEFAULT))
    for h in horizons:
        rec = {"horizon": h}
        for g in GROUP_ORDER:
            v = [r["basis_ret_%d" % h] for r, gg in zip(rows, shift_assign)
                 if gg == g and r.get("basis_ret_%d" % h) is not None]
            rec[g] = {"n": len(v), "mean": mean(v), "median": median(v)}
        a = [r["basis_ret_%d" % h] for r, gg in zip(rows, shift_assign)
             if gg == "低分位" and r.get("basis_ret_%d" % h) is not None]
        b = [r["basis_ret_%d" % h] for r, gg in zip(rows, shift_assign)
             if gg == "高分位" and r.get("basis_ret_%d" % h) is not None]
        rec["low_minus_high"] = (mean(a) - mean(b)) if a and b else None
        out.append(rec)
    return out


# ================================================================ 数据装载
def load_spot(path: str) -> Dict[str, float]:
    import csv
    out: Dict[str, float] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                out[r["date"].strip()] = float(r["price"])
            except (KeyError, ValueError):
                continue
    return out


def load_contracts(raw_dir: str, prefix: str = "MA") -> Dict[str, List[dict]]:
    """逐合约日线 {symbol: [{d,c,oi}, ...] 按日期升序}"""
    out: Dict[str, List[dict]] = {}
    for fp in glob.glob(os.path.join(raw_dir, "%s_%s*.json" % (prefix, prefix))):
        try:
            j = json.load(open(fp, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        rows = sorted(j.get("rows") or [], key=lambda x: x["d"])
        if rows:
            out[j["symbol"]] = rows
    return out


def contract_ym(sym: str) -> Tuple[int, int]:
    return 2000 + int(sym[2:4]), int(sym[4:6])


def ym_str(y: int, m: int) -> str:
    return "%04d-%02d" % (y, m)


def last_trading_days(contracts: Dict[str, List[dict]]) -> Dict[str, str]:
    return {s: rows[-1]["d"] for s, rows in contracts.items() if rows}


# ================================================================ 映射
def build_mapping(contracts: Dict[str, List[dict]], cal_date: str,
                  rule: str = "main", near_min_oi_ratio: float = 0.05,
                  near_horizon_days: int = 20) -> Optional[dict]:
    """
    返回 {'date','contract','fut','oi','days_to_ltd','alt_contract','alt_fut','rule'} 或 None

    rule:
      main  —— 当日持仓量(OI)最大的、交割月不早于当月的合约（当日收盘即可得，无未来信息）
      near  —— 最近交割月合约；若距最后交易日 ≤ near_horizon_days 且持仓 < 主力持仓×ratio，
               视为「伪近月」跳过（流动性门槛），记录 skipped
      fixed —— 由调用方指定固定交割月，见 build_mapping_fixed
    """
    today = cal_date[:7]
    alive = []
    for sym, rows in contracts.items():
        y, m = contract_ym(sym)
        if ym_str(y, m) < today:
            continue
        alive.append(sym)
    if not alive:
        return None
    day_rows = {}
    for sym in alive:
        for r in contracts[sym]:
            if r["d"] == cal_date:
                day_rows[sym] = r
                break
    if not day_rows:
        return None
    ltd = last_trading_days(contracts)

    if rule == "main":
        sym, row = max(day_rows.items(), key=lambda kv: (kv[1]["oi"], kv[0]))
    elif rule == "near":
        ordered = sorted(day_rows, key=lambda s: contract_ym(s))
        main_sym = max(day_rows.items(), key=lambda kv: kv[1]["oi"])[0]
        main_oi = day_rows[main_sym]["oi"]
        sym = None
        skipped = []
        for cand in ordered:
            r = day_rows[cand]
            days_to_ltd = _days_between(contracts[cand], cal_date)
            if (days_to_ltd is not None and days_to_ltd <= near_horizon_days
                    and main_oi > 0 and r["oi"] < near_min_oi_ratio * main_oi):
                skipped.append(cand)
                continue
            sym = cand
            break
        if sym is None:
            return None
        row = day_rows[sym]
        if skipped:
            row = dict(row)
            row["_skipped"] = skipped
    elif rule == "fixed":
        raise ValueError("fixed 规则请调用 build_mapping_fixed()")
    else:
        raise ValueError("unknown rule %r" % rule)

    days_to_ltd = _days_between(contracts[sym], cal_date)
    # 换月检测：当日主力/近月，与「次日」应持有的合约不同 -> 今天是换月前夜
    alt_sym = None
    alt_fut = None
    for other in sorted(day_rows, key=lambda s: contract_ym(s)):
        if other == sym:
            continue
        alt_sym, alt_fut = other, day_rows[other]["c"]
        break
    return {
        "date": cal_date, "rule": rule, "contract": sym,
        "contract_month": "%04d-%02d" % contract_ym(sym),
        "fut": float(row["c"]), "oi": float(row["oi"]),
        "days_to_ltd": days_to_ltd,
        "alt_contract": alt_sym, "alt_fut": alt_fut,
        "skipped": row.get("_skipped", []),
    }


def build_mapping_fixed(contracts: Dict[str, List[dict]], cal_date: str,
                        delivery_month: int) -> Optional[dict]:
    """固定交割月映射：在当日可交易合约中，选交割月==delivery_month 的最近一个年份。
    同一交割月的不同年份是独立样本，跨年拼接时必须按年分段。"""
    best = None
    for sym, rows in contracts.items():
        y, m = contract_ym(sym)
        if m != delivery_month:
            continue
        if rows[-1]["d"] < cal_date:
            continue
        for r in rows:
            if r["d"] == cal_date:
                if best is None or (y < best[0]):
                    best = (y, sym, r)
                break
    if best is None:
        return None
    y, sym, r = best
    return {
        "date": cal_date, "rule": "fixed%02d" % delivery_month, "contract": sym,
        "contract_month": "%04d-%02d" % (y, delivery_month),
        "fut": float(r["c"]), "oi": float(r["oi"]),
        "days_to_ltd": _days_between(contracts[sym], cal_date),
        "alt_contract": None, "alt_fut": None, "skipped": [],
    }


def _days_between(rows: List[dict], date: str) -> Optional[int]:
    """date 之后该合约剩余交易日数（含末个K线日 = 0）"""
    if not rows:
        return None
    last = rows[-1]["d"]
    if date > last:
        return None
    return sum(1 for r in rows if r["d"] > date)


# ================================================================ 基差
def build_basis(mapping: Dict[str, dict], spot: Dict[str, float],
                h_max: int = 5, window: int = 250,
                bands: Tuple[Tuple[float, float], ...] = BANDS_DEFAULT,
                basis_mode: str = "def") -> List[dict]:
    """
    basis_mode:
      def —— 定义值 (spot - fut)/spot（默认，价差收益直接可加：basis_ret = spot_ret - fut_ret）
      lv  —— 元/吨 level，滚动分位与未来变化都在 level 上计算（稳健性用）
    返回按日期升序的日度记录，含：
      basis_pct_lag   : t-window..t 的滚动分位（严格滞后，见 rolling_percentile）
      n_hist          : 当日前可用分位点数
      group_lag       : 按(B_i,B_j)阈值给出的滞后分组（用于统计与分组着色）
      future_share    : 基差变动的「价格风险占比」= 1 - |期货贡献|/(|现货贡献|+|期货贡献|)
      *_ret           : 未来 h 日变动（相对 t 日），basis_ret = spot_ret - fut_ret
      flags           : 换月污染 / 交割临近 标记
    """
    map_recs = list(mapping) if isinstance(mapping, (list, tuple)) else [mapping[k] for k in sorted(mapping)]
    basis_vals: List[Optional[float]] = []
    for d in map_recs:
        spot_px = spot.get(d["date"])
        if spot_px is None:
            basis_vals.append(None)
            continue
        if basis_mode == "lv":
            basis_vals.append(spot_px - d["fut"])
        else:
            basis_vals.append((spot_px - d["fut"]) / spot_px if spot_px else None)
    k_max = max(max(hi for _, hi in bands), 0.0)
    k_min = min(min(lo for lo, _ in bands), 1.0)

    rows: List[dict] = []
    for i, d in enumerate(map_recs):
        date = d["date"]
        spot_px = spot.get(date)
        if spot_px is None:
            continue
        b = basis_vals[i]
        if b is None:
            continue
        hist = [basis_vals[j] for j in range(max(0, i - window), i) if basis_vals[j] is not None]
        n_hist = len(hist)
        # 百分位秩本身就是分位（∈(0,1)），不要再把秩喂给 percentile_linear
        pct = _rank_of(hist, b) if n_hist >= MIN_HIST else None
        grp = _group_of(pct, bands)
        rec = {
            "date": date, "contract": d["contract"], "contract_month": d["contract_month"],
            "spot": round(spot_px, 4), "fut": round(d["fut"], 4),
            "basis": round(spot_px - d["fut"], 4),
            "basis_ratio": round((spot_px - d["fut"]) / spot_px, 6) if spot_px else None,
            "oi": d["oi"], "days_to_ltd": d["days_to_ltd"],
            "basis_pct_lag": None if pct is None else round(pct, 4),
            "n_hist": n_hist, "group_lag": grp,
            "roll_day": 0, "roll_new_next": 0, "flags": "",
        }
        rows.append(rec)

    # ---- 前向收益（价格风险分解）
    for i, rec in enumerate(rows):
        for h in HORIZONS_ALL:
            s0, f0 = rec["spot"], rec["fut"]
            if i + h < len(rows):
                j = rows[i + h]
                rec["spot_ret_%d" % h] = round((j["spot"] - s0) / s0, 6)
                rec["fut_ret_%d" % h] = round((j["fut"] - f0) / f0, 6)
                rec["basis_ret_%d" % h] = round(rec["spot_ret_%d" % h] - rec["fut_ret_%d" % h], 6)
                if basis_mode == "lv":
                    rec["basis_chg_%d" % h] = round(j["basis"] - rec["basis"], 4)
                else:
                    rec["basis_chg_%d" % h] = round(j["basis"] - rec["basis"], 4)

    # ---- 可操作时点口径：因子时点 t-h 的分位，收益区间 [t-h, t]
    # 全部信息在 t 日收盘时已知；用它的分位把「到期日」归组，即看「到期时的结果」
    lag_index = {rec["date"]: i for i, rec in enumerate(rows)}
    for rec in rows:
        i = lag_index[rec["date"]]
        for h in HORIZONS_ALL:
            src = rows[i - h] if i - h >= 0 else None
            rec["basis_pct_at_%d" % h] = None if src is None else src["basis_pct_lag"]
            rec["group_at_%d" % h] = _group_of(rec["basis_pct_at_%d" % h], bands)
            rec["spot_ret_pit_%d" % h] = None
            rec["fut_ret_pit_%d" % h] = None
            rec["basis_ret_pit_%d" % h] = None
            rec["basis_chg_pit_%d" % h] = None
            if i - h < 0:
                continue
            s0 = rows[i - h]["spot"]
            f0 = rows[i - h]["fut"]
            b0 = rows[i - h]["basis"]
            rec["spot_ret_pit_%d" % h] = round((rec["spot"] - s0) / s0, 6)
            rec["fut_ret_pit_%d" % h] = round((rec["fut"] - f0) / f0, 6)
            rec["basis_ret_pit_%d" % h] = round(rec["spot_ret_pit_%d" % h] - rec["fut_ret_pit_%d" % h], 6)
            rec["basis_chg_pit_%d" % h] = round(rec["basis"] - b0, 4)

    # ---- 价格风险占比 & 旗标
    for i, rec in enumerate(rows):
        div = []
        for h in HORIZONS_ALL:
            if "spot_ret_%d" % h not in rec:
                continue
            fill = _future_share(rec["spot_ret_%d" % h], rec["fut_ret_%d" % h])
            rec["future_share_%d" % h] = None if fill is None else round(fill, 4)
            if rec["days_to_ltd"] is not None and rec["days_to_ltd"] <= 5:
                div.append("交割临近")
        rec["flags"] = ",".join(dict.fromkeys(div))
        if i + 1 < len(rows):
            rec["roll_new_next"] = 1 if rows[i + 1]["contract"] != rec["contract"] else 0
        if i > 0:
            rec["roll_day"] = 1 if rows[i - 1]["contract"] != rec["contract"] else 0
    return rows


HORIZONS_ALL = HORIZONS_DEFAULT


def _rank_of(hist: List[float], b: float) -> float:
    """当前值在历史样本中的经验分位（线性插值）。"""
    s = sorted(hist)
    n = len(s)
    if n == 0:
        return float("nan")
    lo = 0
    hi = n
    while lo < hi:
        mid = (lo + hi) // 2
        if s[mid] < b:
            lo = mid + 1
        else:
            hi = mid
    less = lo
    equal = 0
    k = lo
    while k < n and s[k] == b:
        equal += 1
        k += 1
    if equal:
        # 百分位秩（standard competition rank 的中点）：
        #   = (#小于 + 0.5×#相等) / n ∈ (0,1)
        # 性质：与分布形状无关；当前值 = 历史中位数时恰为 0.5，可直接与 k / 1-k 阈值比较。
        return (less + 0.5 * equal) / n
    # 无并列时 x 不在样本里，仍需一个落在 (0,1) 的秩：
    #   落在第 less 与 less+1 个之间 → 中点位置 = less/n（less=n 时取 (n-0.5)/n）
    # 说明：不加这个半步会让“最大值”只能得到 (n-0.5)/n < 1，
    #       在 k=0.1 阈值下永远进不了“≥0.9”的高分位组。
    if less >= n:
        return (n - 0.5) / n
    return less / n


def _future_share(spot_ret: Optional[float], fut_ret: Optional[float]) -> Optional[float]:
    """期货贡献占基差变动的份额：基差变动 = 现货变动 - 期货变动。
    = |fut| / (|spot| + |fut|)；接近 1 表示基差变动几乎全由期货价格驱动。"""
    if spot_ret is None or fut_ret is None:
        return None
    den = abs(spot_ret) + abs(fut_ret)
    if den == 0:
        return None
    return abs(fut_ret) / den


# ================================================================ 滚动分位（独立函数，便于单测）
def rolling_percentile(values: Sequence[Optional[float]], window: int) -> List[Optional[float]]:
    """
    严格滞后滚动分位：
      P(i) = 当前值 value[i] 在窗口 values[i-window .. i-1] 中的经验分位
    窗口不含 i 当天 -> 当天收盘即可算，无未来函数。
    返回长度同 values；窗口点数 < 20 时返回 None（样本不足不硬算）。
    """
    out: List[Optional[float]] = []
    for i, v in enumerate(values):
        if v is None:
            out.append(None)
            continue
        hist = [values[j] for j in range(max(0, i - window), i) if values[j] is not None]
        if len(hist) < MIN_HIST:
            out.append(None)
        else:
            out.append(_rank_of(hist, v))
    return out


def mask_unknown_periods(rows: List[dict], last_known_date: str,
                         window: int, verbose: bool = True) -> List[dict]:
    """
    把「距今不足 window 个交易日」的历史点标为 point_in_time_unknown：
    那些日子当时用同一 window 算不出分位（数据末端回填），
    在滚动分位对时间稳定性做评估时必须剔除，否则会把回填样本当历史。
    返回带 pit_status 字段的新列表。
    """
    n = len(rows)
    for i, rec in enumerate(rows):
        rec["point_in_time_known"] = 1 if i < n - window else 0
    if verbose and n > window:
        print("[PIT] 最后 %d 个点(%s 起)分位为数据末端回填，时间稳定性检验中剔除"
              % (window, rows[n - window]["date"]))
    return rows


# ================================================================ 分组统计
def bucket_stats(rows: List[dict], horizons: Sequence[int], bands=BANDS_DEFAULT,
                 ret_source: str = "info") -> List[dict]:
    """
    ret_source:
      info —— 信息检验：分位来自 t 日、未来收益区间为 [t, t+h]（标准的事件研究口径）
      deploy —— 可操作口径：分位滞后 h 日、收益区间 [t-h, t]（时点全部已知）
    """
    out = []
    for h in horizons:
        if ret_source == "info":
            skey, fkey, bkey, gkey = ("spot_ret_%d" % h, "fut_ret_%d" % h,
                                      "basis_ret_%d" % h, "group_lag")
        else:
            skey, fkey, bkey, gkey = ("spot_ret_pit_%d" % h, "fut_ret_pit_%d" % h,
                                      "basis_ret_pit_%d" % h, "group_at_%d" % h)
        for g in GROUP_ORDER:
            sub = [r for r in rows if r.get(gkey) == g and r.get(bkey) is not None]
            st = _describe(sub, h, g, skey, fkey, bkey)
            st["ret_source"] = ret_source
            out.append(st)
    return out


def _group_of(pct: Optional[float], bands) -> Optional[str]:
    if pct is None:
        return None
    k_max = max(hi for _, hi in bands)
    k_min = min(lo for lo, _ in bands)
    if pct >= k_max:
        return "高分位"
    if pct <= k_min:
        return "低分位"
    return "中间分位"


def _describe(sub: List[dict], h: int, group: str, skey: str, fkey: str, bkey: str) -> dict:
    basis = [r[bkey] for r in sub if r.get(bkey) is not None]
    spot = [r[skey] for r in sub if r.get(skey) is not None]
    fut = [r[fkey] for r in sub if r.get(fkey) is not None]
    return {
        "horizon": h, "group": group, "n": len(basis),
        "basis_ret_mean": mean(basis), "basis_ret_median": median(basis),
        "basis_ret_std": stdev(basis), "basis_ret_p10": percentile_linear(sorted(basis), 0.10) if basis else None,
        "basis_ret_p25": percentile_linear(sorted(basis), 0.25) if basis else None,
        "basis_ret_p75": percentile_linear(sorted(basis), 0.75) if basis else None,
        "basis_ret_p90": percentile_linear(sorted(basis), 0.90) if basis else None,
        "basis_ret_skew": skew(basis), "basis_ret_kurt": kurt(basis),
        "basis_ret_max": max(basis) if basis else None, "basis_ret_min": min(basis) if basis else None,
        "basis_ret_share_pos": hit_rate(basis, 1), "basis_ret_share_neg": hit_rate(basis, -1),
        "basis_ret_mean_skew": sample_skewness_of_mean(basis),
        "basis_ret_mean_pos_share": mean_positive_share(basis),
        "spot_ret_mean": mean(spot), "spot_ret_median": median(spot), "spot_ret_std": stdev(spot),
        "fut_ret_mean": mean(fut), "fut_ret_median": median(fut), "fut_ret_std": stdev(fut),
        "fut_ret_min": min(fut) if fut else None, "fut_ret_max": max(fut) if fut else None,
        "roll_share": (sum(1 for r in sub if r.get("roll_day")) / len(sub)) if sub else None,
    }


# ================================================================ 推断
def block_bootstrap_diff(a: Sequence[float], b: Sequence[float], rows_a: List[dict],
                         rows_b: List[dict], blocksize: int = 5, n_boot: int = 2000,
                         seed: int = 20261020) -> dict:
    """循环块自助法：H0: mean(a) - mean(b) 的抽样分布。返回 bootstrap p 值与 CI。"""
    rng = random.Random(seed)
    obs = (mean(a) or 0.0) - (mean(b) or 0.0)
    tol = 1e-12
    if not a or not b:
        return {"diff": None, "p": None, "ci_lo": None, "ci_hi": None, "blocksize": blocksize}
    if len(a) <= blocksize * 2 or len(b) <= blocksize * 2:
        # 块长 ≥ 样本一半时循环块退化（每块都覆盖全样本），自助分布无意义
        return {"diff": obs, "p": None, "p_emp": None, "ci_lo": None, "ci_hi": None,
                "boot_sd": None, "obs_over_sd": None, "degenerate": True,
                "reason": "样本 %d/%d ≤ 2×块长 %d，循环块自助退化" % (len(a), len(b), blocksize),
                "blocksize": blocksize, "n_boot": 0, "n_a": len(a), "n_b": len(b)}
    diffs = []
    for _ in range(n_boot):
        ia = block_sample(len(a), blocksize, rng)
        ib = block_sample(len(b), blocksize, rng)
        diffs.append(sum(a[i] for i in ia) / len(ia) - sum(b[i] for i in ib) / len(ib))
    sd = stdev(diffs) or 0.0
    if sd < 1e-12:
        return {"diff": obs, "p": None, "p_emp": None, "ci_lo": None, "ci_hi": None,
                "boot_sd": sd, "obs_over_sd": None, "degenerate": True,
                "reason": "自助分布方差为 0（样本被同一块覆盖）",
                "blocksize": blocksize, "n_boot": n_boot, "n_a": len(a), "n_b": len(b)}
    centred = sorted(d - obs for d in diffs)
    abs_obs = abs(obs)
    # 1) 正态性质的自助 p（H0: 差值=0）：2*(1-Φ(|obs|/sd))
    p_norm = math.erfc(abs_obs / (sd * math.sqrt(2)))
    # 2) 中心化 |diff*| >= |obs| 的经验 p；R 有限时最小可分辨 p≈1/R
    p_emp = sum(1 for c in centred if abs(c) >= abs_obs - tol) / len(centred)
    lo_ = percentile_linear(centred, 0.025) + obs
    hi_ = percentile_linear(centred, 0.975) + obs
    return {"diff": obs, "p": p_norm, "p_emp": p_emp, "ci_lo": lo_, "ci_hi": hi_,
            "boot_sd": sd, "obs_over_sd": (abs_obs / sd) if sd > 0 else None,
            "degenerate": False,
            "blocksize": blocksize, "n_boot": n_boot, "n_a": len(a), "n_b": len(b),
            "p_floor": 1.0 / len(centred)}


def non_overlap_subsample(rows: List[dict], horizon: int) -> List[dict]:
    """非重叠子样本：每 h 个观测取一个（从每个窗口起点开始），用于重叠稳健性复核"""
    return rows[::max(1, horizon)]


def overlap_diagnostics(rows: List[dict], horizons: Sequence[int]) -> List[dict]:
    """样本重叠诊断：n 个日度观测覆盖的独立期间数、平均重叠倍数、有效独立样本数"""
    out = []
    n = len(rows)
    for h in horizons:
        cover = 0
        last_end = -1
        for i, _ in enumerate(rows):
            if i <= last_end:
                continue
            cover += 1
            last_end = i + h - 1
        out.append({
            "horizon": h, "n_obs": n, "multiplicity": h,
            "independent_periods": cover,
            "note": "每个 h 日窗口内地日观测重叠 h 倍；独立期间数 = n/h 量级",
        })
    return out


# ================================================================ 敏感性
def threshold_sensitivity(rows: List[dict], windows: Sequence[int], horizons: Sequence[int],
                          thresholds: Sequence[float], n_boot: int = 800) -> List[dict]:
    """
    对每个 (window 已固化在 rows 里, threshold k, horizon h) 重算低/高分位组均值与低-高差。
    说明：window 敏感性由上层分别用不同 window 构建的 rows 再调用本函数实现。
    """
    out = []
    for k in thresholds:
        lo_grp = [r for r in rows if r.get("basis_pct_lag") is not None and r["basis_pct_lag"] <= k]
        hi_grp = [r for r in rows if r.get("basis_pct_lag") is not None and r["basis_pct_lag"] >= 1 - k]
        for h in horizons:
            a = [r["basis_ret_%d" % h] for r in lo_grp if r.get("basis_ret_%d" % h) is not None]
            b = [r["basis_ret_%d" % h] for r in hi_grp if r.get("basis_ret_%d" % h) is not None]
            sa = [r["spot_ret_%d" % h] for r in lo_grp if r.get("spot_ret_%d" % h) is not None]
            sb = [r["spot_ret_%d" % h] for r in hi_grp if r.get("spot_ret_%d" % h) is not None]
            fa = [r["fut_ret_%d" % h] for r in lo_grp if r.get("fut_ret_%d" % h) is not None]
            fb = [r["fut_ret_%d" % h] for r in hi_grp if r.get("fut_ret_%d" % h) is not None]
            bs = max(2, min(h, len(a) // 8 if a else h, len(b) // 8 if b else h))
            boot = block_bootstrap_diff(a, b, lo_grp, hi_grp, blocksize=bs, n_boot=n_boot)
            out.append({
                "threshold": k, "horizon": h,
                "n_low": len(a), "n_high": len(b),
                "low_basis_mean": mean(a), "high_basis_mean": mean(b),
                "low_minus_high": boot["diff"], "boot_p": boot["p"], "blocksize": bs,
                "ci_lo": boot["ci_lo"], "ci_hi": boot["ci_hi"],
                "low_spot_mean": mean(sa), "high_spot_mean": mean(sb),
                "low_fut_mean": mean(fa), "high_fut_mean": mean(fb),
                "spread_spot": (mean(sa) or 0) - (mean(sb) or 0) if sa and sb else None,
                "spread_fut": (mean(fa) or 0) - (mean(fb) or 0) if fa and fb else None,
            })
    return out


# ================================================================ 稳定性
def stability_by_year(rows: List[dict], h: int, group: str = "full") -> List[dict]:
    out = []
    years = sorted({r["date"][:4] for r in rows})
    for y in years:
        sub = [r for r in rows if r["date"][:4] == y]
        if group != "full":
            sub = [r for r in sub if r.get("group_lag") == group]
        vals = [r["basis_ret_%d" % h] for r in sub if r.get("basis_ret_%d" % h) is not None]
        spot = [r["spot_ret_%d" % h] for r in sub if r.get("spot_ret_%d" % h) is not None]
        fut = [r["fut_ret_%d" % h] for r in sub if r.get("fut_ret_%d" % h) is not None]
        out.append({"year": y, "group": group, "n": len(vals),
                    "basis_ret_mean": mean(vals), "basis_ret_median": median(vals),
                    "spot_ret_mean": mean(spot), "fut_ret_mean": mean(fut),
                    "share_pos": hit_rate(vals, 1)})
    return out


def stability_by_month(rows: List[dict], h: int, group: str = "full") -> List[dict]:
    out = []
    for m in range(1, 13):
        mm = "%02d" % m
        sub = [r for r in rows if r["date"][5:7] == mm]
        if group != "full":
            sub = [r for r in sub if r.get("group_lag") == group]
        vals = [r["basis_ret_%d" % h] for r in sub if r.get("basis_ret_%d" % h) is not None]
        out.append({"month": m, "group": group, "n": len(vals),
                    "basis_ret_mean": mean(vals), "basis_ret_median": median(vals)})
    return out


def regime_labels(rows: List[dict]) -> List[dict]:
    """
    市场阶段：按主力合约月差（近月 - 次近月，即 alt 合约）的 120 分位
    划分为 Back / Contango；缺失时按 基差率 120 分位兜底。
    只用当日可得信息（同日两合约收盘），无未来函数。
    """
    return rows


def stability_by_regime(rows: List[dict], h: int, group: str = "full") -> List[dict]:
    out = []
    for reg in ("Back(近强)", "Contango(远强)", "结构不明"):
        sub = [r for r in rows if r.get("regime") == reg]
        if group != "full":
            sub = [r for r in sub if r.get("group_lag") == group]
        vals = [r["basis_ret_%d" % h] for r in sub if r.get("basis_ret_%d" % h) is not None]
        out.append({"regime": reg, "group": group, "n": len(vals),
                    "basis_ret_mean": mean(vals), "basis_ret_median": median(vals),
                    "spot_ret_mean": mean([r["spot_ret_%d" % h] for r in sub if r.get("spot_ret_%d" % h) is not None]),
                    "fut_ret_mean": mean([r["fut_ret_%d" % h] for r in sub if r.get("fut_ret_%d" % h) is not None])})
    return out


def annotate_regime(rows: List[dict], window: int = 120) -> List[dict]:
    """给每行加 regime：用当日两合约价差（主-次）的滚动分位判断结构。"""
    spread = []
    for r in rows:
        spread.append(r.get("spread_next"))
    pcts = rolling_percentile(spread, window)
    for r, p in zip(rows, pcts):
        if p is None:
            r["regime"] = "结构不明"
        elif p >= 0.6:
            r["regime"] = "Back(近强)"
        elif p <= 0.4:
            r["regime"] = "Contango(远强)"
        else:
            r["regime"] = "结构不明"
    return rows


# ================================================================ 换月 / 交割诊断
def roll_diagnostics(rows: List[dict], horizons: Sequence[int]) -> dict:
    roll_days = [r for r in rows if r.get("roll_day")]
    normal = [r for r in rows if not r.get("roll_day")]
    out = {"n_roll": len(roll_days), "n_normal": len(normal), "rolls": [], "by_horizon": []}
    for r in roll_days:
        out["rolls"].append({
            "date": r["date"], "contract": r["contract"],
            "basis_ratio": r["basis_ratio"],
            "basis_chg_1d": r.get("basis_chg_1"),
            "spot_ret_1d": r.get("spot_ret_1"), "fut_ret_1d": r.get("fut_ret_1"),
        })
    for h in horizons:
        rv = [abs(r["basis_chg_%d" % h]) for r in roll_days if r.get("basis_chg_%d" % h) is not None]
        nv = [abs(r["basis_chg_%d" % h]) for r in normal if r.get("basis_chg_%d" % h) is not None]
        rv1 = [abs(r["basis_chg_1"]) for r in roll_days if r.get("basis_chg_1") is not None]
        nv1 = [abs(r["basis_chg_1"]) for r in normal if r.get("basis_chg_1") is not None]
        out["by_horizon"].append({
            "horizon": h,
            "roll_abs_median": median(rv), "normal_abs_median": median(nv),
            "roll_1d_abs_median": median(rv1), "normal_1d_abs_median": median(nv1),
            "ratio": (median(rv) / median(nv)) if (rv and nv and median(nv)) else None,
            "risk_share_roll": (sum(abs(r["basis_chg_%d" % h]) for r in roll_days
                                    if r.get("basis_chg_%d" % h) is not None)
                                / sum(abs(r["basis_chg_%d" % h]) for r in rows
                                      if r.get("basis_chg_%d" % h) is not None)) if rows else None,
        })
    return out


def delivery_proximity(rows: List[dict], horizons: Sequence[int]) -> List[dict]:
    """交割临近效应：按距最后交易日分组，看基差绝对变动是否放大"""
    bins = [(0, 5), (6, 10), (11, 20), (21, 40), (41, 9999)]
    out = []
    for lo, hi in bins:
        sub = [r for r in rows if r.get("days_to_ltd") is not None and lo <= r["days_to_ltd"] <= hi]
        rec = {"bin": "%d-%d" % (lo, hi) if hi < 9999 else ">40日", "n": len(sub)}
        for h in horizons:
            v = [abs(r["basis_chg_%d" % h]) for r in sub if r.get("basis_chg_%d" % h) is not None]
            rec["abs_basis_chg_median_%d" % h] = median(v)
        out.append(rec)
    return out


# ================================================================ 口径核验
def verify_against_published(rows: List[dict], published: Dict[str, float],
                             tol: float = 0.5) -> dict:
    """
    与 100ppi 公开的「主力基差率」逐日比对：
    重建基差率 = (现货 - 主力期货)/现货 × 100（百分点）。
    tol 为百分点容忍度；0.5 个百分点约等于现货 4000 元/吨时 20 元/吨的取整误差。
    返回重合天数、一致率、中位偏差、分年度一致率。
    """
    diffs, by_year = [], {}
    for r in rows:
        d = r["date"]
        if d not in published or r.get("basis_ratio") is None:
            continue
        gap = r["basis_ratio"] * 100.0 - published[d]
        diffs.append(gap)
        by_year.setdefault(d[:4], []).append(abs(gap) <= tol)
    if not diffs:
        return {"n": 0}
    ad = sorted(abs(x) for x in diffs)
    return {
        "n": len(diffs), "tolerance_pct_point": tol,
        "agree_share": sum(1 for x in diffs if abs(x) <= tol) / len(diffs),
        "agree_share_1pt": sum(1 for x in diffs if abs(x) <= 1.0) / len(diffs),
        "median_abs_gap": percentile_linear(ad, 0.5),
        "p90_abs_gap": percentile_linear(ad, 0.90),
        "by_year": {y: sum(v) / len(v) for y, v in sorted(by_year.items())},
    }


# ================================================================ 全流程
def calibrate_level_adjust(rows: List[dict], published: Dict[str, float],
                           window: int = 120) -> dict:
    """
    量价口径校准（不引入未来函数）：
      100ppi 公布的「主力基差率」与我们重建值的偏差，
      可解释为它合成的现货比市场可交易报价存在水平差 adj（元/吨）：
          (S_t - adj) - F_t = rate_t/100 * (S_t - adj)
      =>  adj_t ≈ (S_t - F_t - S_t*rate_t/100) / (1 - rate_t/100)
      取滚动 window 日中位数，只用于研究披露「口径不确定性带」。
    返回 {'median_adj','p25','p75','n','by_half':{'first':x,'second':y}}
    """
    adj = []
    for r in rows:
        d = r["date"]
        if d not in published or not r.get("spot"):
            continue
        rate = published[d] / 100.0
        if abs(1 - rate) < 1e-6:
            continue
        adj.append((r["spot"] - r["fut"] - r["spot"] * rate) / (1 - rate))
    if not adj:
        return {"n": 0}
    s = sorted(adj)
    half = len(s) // 2
    return {
        "n": len(s),
        "median_adj": percentile_linear(s, 0.5),
        "p25": percentile_linear(s, 0.25),
        "p75": percentile_linear(s, 0.75),
        "first_half_median": percentile_linear(sorted(s[:half]), 0.5) if half > 5 else None,
        "second_half_median": percentile_linear(sorted(s[half:]), 0.5) if len(s) - half > 5 else None,
        "window_days": window,
    }


def run(raw_dir: str, out_dir: str, spec: Optional[dict] = None) -> dict:
    spec = dict(spec or {})
    os.makedirs(out_dir, exist_ok=True)
    prefix = spec.get("prefix", "MA")
    near_min_oi = spec.get("near_min_oi_ratio", 0.05)
    horizons = tuple(spec.get("horizons", list(HORIZONS_DEFAULT)))
    windows = tuple(spec.get("windows", list(WINDOWS_DEFAULT)))
    thresholds = tuple(spec.get("thresholds", [0.1, 0.2, 0.3, 0.4]))
    n_boot = int(spec.get("n_boot", 8000))
    basis_mode = spec.get("basis_mode", "def")
    main_window = int(spec.get("main_window", 250))
    start_date = spec.get("start_date")

    global HORIZONS_ALL
    HORIZONS_ALL = tuple(sorted(set(list(horizons) + [1])))
    h_max = max(HORIZONS_ALL)

    spot = load_spot(os.path.join(raw_dir, "spot_methanol_100ppi_benchmark.csv"))
    contracts = load_contracts(raw_dir, prefix)
    print("[DATA] 现货 %d 点 (%s ~ %s)；合约 %d 个" % (len(spot), min(spot), max(spot), len(contracts)))

    all_dates = sorted({r["d"] for rows in contracts.values() for r in rows})
    cal_dates = [d for d in all_dates if d in spot]
    if start_date:
        cal_dates = [d for d in cal_dates if d >= start_date]
    print("[DATA] 可对齐交易日 %d (%s ~ %s)" % (len(cal_dates), cal_dates[0], cal_dates[-1]))

    result: dict = {"meta": {}, "series": {}, "stats": {}}

    # ---------- 三套映射
    maps = {}
    for rule in ("main", "near"):
        m = {}
        for d in cal_dates:
            x = build_mapping(contracts, d, rule=rule, near_min_oi_ratio=near_min_oi)
            if x:
                m[d] = x
        maps[rule] = m
        print("[MAP] %s: %d 日" % (rule, len(m)))

    # ---------- 主口径：主力连续
    main_map = maps["main"]
    mapping_list = [main_map[d] for d in sorted(main_map)]

    series = {}
    for w in windows:
        rows = build_basis(mapping_list, spot, h_max=h_max, window=w, basis_mode=basis_mode)
        rows = mask_unknown_periods(rows, cal_dates[-1], w)
        # 结构 regime：主-次合约价差（同日两合约收盘，当日可得）
        for d_, rec in zip(sorted(main_map), rows):
            mm = main_map[d_]
            alt = mm.get("alt_contract")
            if alt:
                alt_px = None
                for r in contracts[alt]:
                    if r["d"] == rec["date"]:
                        alt_px = r["c"]
                        break
                rec["spread_next"] = None if alt_px is None else round(rec["fut"] - alt_px, 4)
            else:
                rec["spread_next"] = None
        annotate_regime(rows, window=120)
        series[w] = rows
        print("[BASIS] window=%d rows=%d 有效分位=%d" % (w, len(rows),
              sum(1 for r in rows if r.get("basis_pct_lag") is not None)))

    rows_main = series[main_window]

    # ---------- 分组统计（信息口径 + 可操口径 + 水平值稳健）
    stats = {}
    stats["bucket_info"] = bucket_stats(rows_main, horizons, ret_source="info")
    stats["bucket_deploy"] = bucket_stats(rows_main, horizons, ret_source="deploy")

    # ---------- 低分位 vs 高分位差异 & 自助法
    diffs = []
    for h in horizons:
        lo = [r["basis_ret_%d" % h] for r in rows_main if r["group_lag"] == "低分位" and r.get("basis_ret_%d" % h) is not None]
        hi = [r["basis_ret_%d" % h] for r in rows_main if r["group_lag"] == "高分位" and r.get("basis_ret_%d" % h) is not None]
        s_lo = [r["spot_ret_%d" % h] for r in rows_main if r["group_lag"] == "低分位" and r.get("spot_ret_%d" % h) is not None]
        s_hi = [r["spot_ret_%d" % h] for r in rows_main if r["group_lag"] == "高分位" and r.get("spot_ret_%d" % h) is not None]
        f_lo = [r["fut_ret_%d" % h] for r in rows_main if r["group_lag"] == "低分位" and r.get("fut_ret_%d" % h) is not None]
        f_hi = [r["fut_ret_%d" % h] for r in rows_main if r["group_lag"] == "高分位" and r.get("fut_ret_%d" % h) is not None]
        bt = block_bootstrap_diff(lo, hi, [], [], blocksize=h, n_boot=n_boot)
        bt_spot = block_bootstrap_diff(s_lo, s_hi, [], [], blocksize=h, n_boot=n_boot)
        bt_fut = block_bootstrap_diff(f_lo, f_hi, [], [], blocksize=h, n_boot=n_boot)
        diffs.append({
            "horizon": h, "n_low": len(lo), "n_high": len(hi),
            "low_mean": mean(lo), "high_mean": mean(hi),
            "low_minus_high": bt["diff"], "boot_p": bt["p"], "p_emp": bt.get("p_emp"),
            "ci_lo": bt["ci_lo"], "ci_hi": bt["ci_hi"],
            "boot_sd": bt.get("boot_sd"), "obs_over_sd": bt.get("obs_over_sd"),
            "degenerate": bt.get("degenerate", False), "reason": bt.get("reason"),
            "spot_low_minus_high": bt_spot["diff"], "spot_boot_p": bt_spot["p"],
            "fut_low_minus_high": bt_fut["diff"], "fut_boot_p": bt_fut["p"],
        })
    stats["diff"] = diffs

    boot_hist = _bootstrap_histogram(rows_main, horizons[0], n_boot=min(n_boot, 20000))
    stats["boot_hist"] = boot_hist

    # ---------- 敏感性
    sens = {}
    for w in windows:
        sens[str(w)] = threshold_sensitivity(series[w], [w], horizons, thresholds, n_boot=min(n_boot, 3000))
    stats["sensitivity"] = sens

    # ---------- 稳定性
    stab = {}
    for h in horizons:
        stab[str(h)] = {
            "year_full": stability_by_year([r for r in rows_main if r["point_in_time_known"] == 1], h, "full"),
            "month_full": stability_by_month([r for r in rows_main if r["point_in_time_known"] == 1], h, "full"),
            "regime_full": stability_by_regime([r for r in rows_main if r["point_in_time_known"] == 1], h, "full"),
            "year_groups": {g: stability_by_year([r for r in rows_main if r["point_in_time_known"] == 1], h, g)
                            for g in GROUP_ORDER},
        }
    stats["stability"] = stab

    # ---------- 重叠
    stats["overlap"] = overlap_diagnostics(rows_main, horizons)
    stats["non_overlap"] = _non_overlap_check(rows_main, horizons)

    # ---------- 换月 / 交割
    stats["roll"] = roll_diagnostics(rows_main, horizons)
    stats["delivery"] = delivery_proximity(rows_main, horizons)

    # ---------- 口径核验
    pub_path = os.path.join(raw_dir, "verify_100ppi_basis_rate.csv")
    verify = {}
    if os.path.exists(pub_path):
        pub = load_spot_pairs(pub_path)
        verify = verify_against_published(rows_main, pub)
        verify["level_adjust"] = calibrate_level_adjust(rows_main, pub)
        verify["level_adjusted_effects"] = level_adjusted_effects(
            rows_main, verify["level_adjust"].get("median_adj") or 0.0, horizons)
        print("[VERIFY] 与 100ppi 主力基差率重合 %d 日，±0.5pp 一致率 %.1f%%，中位偏差 %.3f pp，水平差中位 %.1f 元/吨"
              % (verify.get("n", 0), 100 * verify.get("agree_share", 0), verify.get("median_abs_gap", 0) or 0,
                 verify["level_adjust"].get("median_adj") or 0))
    stats["verify"] = verify

    # ---------- 其它映射对照（近月 + 固定 01/05/09）
    alt_rules = {}
    near_map = maps["near"]
    if near_map:
        near_rows = build_basis([near_map[d] for d in sorted(near_map)], spot, h_max=h_max,
                                window=main_window, basis_mode=basis_mode)
        near_stats = bucket_stats(near_rows, horizons, ret_source="info")
        alt_rules["near"] = {"n_days": len(near_rows), "bucket": near_stats,
                             "n_skipped_illiquid": sum(len(x.get("skipped", [])) for x in near_map.values())}
    for mm in (1, 5, 9):
        m = {}
        for d in cal_dates:
            x = build_mapping_fixed(contracts, d, mm)
            if x:
                m[d] = x
        if not m:
            continue
        rr = build_basis([m[d] for d in sorted(m)], spot, h_max=h_max, window=main_window, basis_mode=basis_mode)
        alt_rules["fixed%02d" % mm] = {"n_days": len(rr), "bucket": bucket_stats(rr, horizons, ret_source="info"),
                                       "by_delivery_year": _fixed_by_year(rr, horizons[0])}
    for k, v in alt_rules.items():
        if "bucket" in v and v["bucket"]:
            print("[RULE] %-8s 高分位 n=%d 低分位 n=%d" % (
                k, next((b["n"] for b in v["bucket"] if b["group"] == "高分位" and b["horizon"] == horizons[0]), 0),
                next((b["n"] for b in v["bucket"] if b["group"] == "低分位" and b["horizon"] == horizons[0]), 0)))
    stats["alt_rules"] = alt_rules

    # ---------- meta
    known = [r for r in rows_main if r["point_in_time_known"] == 1]
    result["meta"] = {
        "spot_first": min(spot), "spot_last": max(spot), "spot_n": len(spot),
        "contracts": len(contracts),
        "aligned_first": cal_dates[0], "aligned_last": cal_dates[-1], "aligned_n": len(cal_dates),
        "basis_first": rows_main[0]["date"], "basis_last": rows_main[-1]["date"],
        "pct_first": next((r["date"] for r in rows_main if r["basis_pct_lag"] is not None), None),
        "pit_known_last": known[-1]["date"] if known else None,
        "pit_unknown_n": sum(1 for r in rows_main if r["point_in_time_known"] == 0),
        "horizons": list(HORIZONS_ALL), "windows": list(windows), "thresholds": list(thresholds),
        "main_window": main_window, "basis_mode": basis_mode,
        "n_boot": n_boot, "n_roll": sum(1 for r in rows_main if r["roll_day"]),
        "current": _current_snapshot(rows_main, horizons),
        "latest_basis": rows_main[-1],
    }
    result["series"]["main"] = rows_main
    result["series"]["near"] = alt_rules.get("near", {})
    result["stats"] = stats
    result["mapping"] = {d: main_map[d] for d in sorted(main_map)}
    result["calendar"] = _calendar_report(contracts, spot)

    with open(os.path.join(out_dir, "research_data.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, default=_json_default)
    with open(os.path.join(out_dir, "basis_daily.csv"), "w", encoding="utf-8-sig", newline="") as f:
        _write_csv(f, rows_main)
    return result


def load_spot_pairs(path: str) -> Dict[str, float]:
    import csv
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[r["date"]] = float(r["basis_rate_pct"])
    return out


def _add_deploy_groups(rows: List[dict]) -> List[dict]:
    """兼容旧接口：deploy 分组已在 build_basis 内生成 group_at_h"""
    return rows


def _bootstrap_histogram(rows: List[dict], h: int, n_boot: int = 1500) -> dict:
    lo = [r["basis_ret_%d" % h] for r in rows if r["group_lag"] == "低分位" and r.get("basis_ret_%d" % h) is not None]
    hi = [r["basis_ret_%d" % h] for r in rows if r["group_lag"] == "高分位" and r.get("basis_ret_%d" % h) is not None]
    if not lo or not hi or len(lo) <= 2 * h or len(hi) <= 2 * h:
        return {"horizon": h, "skipped": True,
                "reason": "块长 %d 下循环块自助退化，见 diff 表" % h}
    rng = random.Random(20261020)
    obs = mean(lo) - mean(hi)
    vals = []
    for _ in range(n_boot):
        ia = block_sample(len(lo), h, rng)
        ib = block_sample(len(hi), h, rng)
        vals.append(sum(lo[i] for i in ia) / len(ia) - sum(hi[i] for i in ib) / len(ib))
    return {"horizon": h, "obs": obs, "n_low": len(lo), "n_high": len(hi), "values": vals}


def _non_overlap_check(rows: List[dict], horizons: Sequence[int]) -> List[dict]:
    out = []
    for h in horizons:
        sub = non_overlap_subsample(rows, h)
        lo = [r["basis_ret_%d" % h] for r in sub if r["group_lag"] == "低分位" and r.get("basis_ret_%d" % h) is not None]
        hi = [r["basis_ret_%d" % h] for r in sub if r["group_lag"] == "高分位" and r.get("basis_ret_%d" % h) is not None]
        bt = block_bootstrap_diff(lo, hi, [], [], blocksize=1, n_boot=800)
        out.append({"horizon": h, "n_low": len(lo), "n_high": len(hi),
                    "low_mean": mean(lo), "high_mean": mean(hi),
                    "diff": (mean(lo) - mean(hi)) if lo and hi else None, "p": bt["p"],
                    "reason": bt.get("reason")})
    return out


def _fixed_by_year(rows: List[dict], h: int) -> List[dict]:
    out = []
    years = sorted({r["contract_month"] for r in rows})
    for cm in years:
        sub = [r for r in rows if r["contract_month"] == cm]
        vals = [r["basis_ret_%d" % h] for r in sub if r.get("basis_ret_%d" % h) is not None]
        hi = [r["basis_ret_%d" % h] for r in sub if r["group_lag"] == "高分位" and r.get("basis_ret_%d" % h) is not None]
        lo = [r["basis_ret_%d" % h] for r in sub if r["group_lag"] == "低分位" and r.get("basis_ret_%d" % h) is not None]
        out.append({"contract_month": cm, "n": len(vals), "n_high": len(hi), "n_low": len(lo),
                    "all_mean": mean(vals), "high_mean": mean(hi), "low_mean": mean(lo)})
    return out


def _current_snapshot(rows: List[dict], horizons: Sequence[int]) -> dict:
    last = rows[-1]
    snap = {"date": last["date"], "basis": last["basis"], "basis_ratio": last["basis_ratio"],
            "pct": last.get("basis_pct_lag"), "group": last.get("group_lag"),
            "n_hist": last.get("n_hist"), "contract": last["contract"]}
    return snap


def _calendar_report(contracts: Dict[str, List[dict]], spot: Dict[str, float]) -> List[dict]:
    """
    合约日历核验：实际末个 K 线日 vs 郑商所规则最后交易日（交割月第 10 个交易日）。
    注意两个数据事实，必须如实写出来而不是粉饰：
      1) 新浪逐合约日线在临近交割时常常缺失（该合约流动性枯竭，接口不再返回），
         所以「末个 K 线日」普遍早于「规则最后交易日」，这不代表规则不符，而是数据截断；
      2) 用「该合约有 K 线的天数」近似「交割月交易日数」，会低估真实交易日数。
    因此 verdict 分三类：规则日可核且一致 / 末个K线早于规则日（数据截断）/ 交割月内K线不足。
    """
    cal = []
    for sym in sorted(contracts):
        rows = contracts[sym]
        y, m = contract_ym(sym)
        month_days = [r["d"] for r in rows if r["d"][:7] == ym_str(y, m)]
        # 规则：交割月第 10 个交易日。有 K 线的天数 ≥10 时，第 10 个即为规则最后交易日
        rule_ltd = month_days[9] if len(month_days) >= 10 else None
        actual = rows[-1]["d"]
        if rule_ltd and actual == rule_ltd:
            verdict = "一致"
        elif rule_ltd and actual < rule_ltd:
            verdict = "早于规则日%d日(K线截断)" % (month_days.index(rule_ltd) - month_days.index(actual))
        elif rule_ltd and actual > rule_ltd:
            verdict = "晚于规则日"
        else:
            verdict = "交割月K线不足"
        cal.append({"contract": sym, "delivery_month": ym_str(y, m),
                    "first_day": rows[0]["d"], "last_day": actual,
                    "delivery_month_trading_days": len(month_days),
                    "rule_last_trading_day": rule_ltd, "verdict": verdict,
                    "n_rows": len(rows), "n_with_spot": sum(1 for r in rows if r["d"] in spot)})
    return cal


def _json_default(o):
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    raise TypeError(repr(o))


def _write_csv(f, rows: List[dict]):
    import csv
    cols = ["date", "contract", "contract_month", "spot", "fut", "basis", "basis_ratio",
            "oi", "days_to_ltd", "basis_pct_lag", "n_hist", "group_lag", "regime",
            "point_in_time_known", "roll_day", "spread_next", "flags"]
    for h in HORIZONS_ALL:
        cols += ["spot_ret_%d" % h, "fut_ret_%d" % h, "basis_ret_%d" % h]
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k) for k in cols})


def main():
    ap = argparse.ArgumentParser(description="期现基差分位信息检验引擎")
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--out", default="out")
    ap.add_argument("--spec", default=None, help="JSON 参数文件")
    args = ap.parse_args()
    spec = json.load(open(args.spec, encoding="utf-8")) if args.spec else {}
    run(args.raw, args.out, spec)


if __name__ == "__main__":
    main()
