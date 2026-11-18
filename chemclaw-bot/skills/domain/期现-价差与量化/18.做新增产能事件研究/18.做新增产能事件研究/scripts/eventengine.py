# -*- coding: utf-8 -*-
"""
eventengine.py — 新增产能事件研究通用引擎（品种无关）

核心设计原则
------------
1. 事件不是"一个日期"，而是一条带阶段标签的日期序列（announce/record/eia/construction/
   mechanical/commissioning/startup/first_product/full_flow/commercial/rampup）。
   不同阶段是**不同事件**，绝不合并统计。
2. 反事实（正常动量）用**相对日历**对齐：事件前第 k 个交易日 → 事件后第 k 个交易日。
   因为新增产能事件常成批出现（同一一年里多个项目投产），用"绝对日期"做基准会把
   其他项目的影响污染进基准。相对日历对齐可以最大程度抵消。
3. 统计上把超额变化拆成三类：
   - cumulative  : 事件后 k 日水平 − 事件前 1 日水平（含前段漂移）
   - abnormal    : [前1日 → 后k日] 变化 − [前1日 → 后k日] 市场平均变化  ← 主口径
   - surprise    : [前1日 → 后k日] 变化 − [前(k+1)日 → 前1日] 变化     ← 二阶差分
4. 只用真实数据；缺失就是缺失（NaN），不做插值、不做"合理估计"。
5. 设计产能 ≠ 投产当天新增产量。实际增量 = 设计产能 × 达产曲线（爬坡）。

纯标准库实现，便于跨 Agent 移植。
"""

from __future__ import annotations

import csv
import json
import math
import os
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta

# --------------------------------------------------------------------------
# 阶段定义：事件节点分层（顺序 = 信息到达顺序）
# --------------------------------------------------------------------------
STAGES = [
    ("announce",       "项目宣布/签约",      1, "投资决定、战略合作签约、上市公司公告拟建"),
    ("record",         "备案/核准",          2, "发改委备案、项目核准批复"),
    ("eia",            "环评批复/公示",      3, "生态环境部门环评批复或受理公示"),
    ("construction",   "开工",              4, "主体装置土建/建安工程开工"),
    ("mechanical",     "中交/机械竣工",      5, "装置中间交接、机械竣工"),
    ("commissioning",  "试车/投料",          6, "单机试车、挤压造粒机组试车、联动试车、投料试车"),
    ("startup",        "正式投产(开车成功)", 7, "一次开车成功、产出合格聚丙烯产品"),
    ("first_product",  "打通全流程/产品首发", 8, "全线打通、产品对外发运"),
    ("commercial",     "商业运营",          9, "高负荷标定后正式商业运营"),
    ("rampup",         "达产/满负荷",        10, "首次高负荷标定、设计产能标定完成"),
]
STAGE_KEYS = [s[0] for s in STAGES]
STAGE_LABEL = {s[0]: s[1] for s in STAGES}
STAGE_ORDER = {s[0]: s[2] for s in STAGES}

# 哪些阶段属于"预期类信息"，哪些属于"实际供给兑现"
EXPECTATION_STAGES = {"announce", "record", "eia", "construction", "mechanical", "commissioning"}
REALIZATION_STAGES = {"startup", "first_product", "commercial", "rampup"}


# --------------------------------------------------------------------------
# 日期工具
# --------------------------------------------------------------------------
def to_date(x):
    """接受 'YYYY-MM-DD' / 'YYYY-MM' / 'YYYY' / datetime / date / None"""
    if x is None or x == "":
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    s = str(x).strip().replace("/", "-").replace(".", "-")
    # YYYYMMDD（8 位纯数字）
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    parts = s.split("-")
    if len(parts) == 3:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    if len(parts) == 2:
        return date(int(parts[0]), int(parts[1]), 1)
    if len(parts) == 1 and parts[0].isdigit():
        return date(int(parts[0]), 1, 1)
    raise ValueError("unparseable date: %r" % (x,))


def iso(d):
    return d.isoformat() if d else None


# --------------------------------------------------------------------------
# 序列容器：交易/观察日历 + 数值
# --------------------------------------------------------------------------
class Series:
    """
    一条时间序列。dates 升序。values 与 dates 等长，允许 None。
    align='next'  : 事件日落在非交易日时，取下一个有值日
    align='prev'  : 取上一个有值日
    align='nearest': 取最近
    """

    def __init__(self, name, dates, values, freq="D", align="prev", unit="", note=""):
        pairs = [(to_date(d), v) for d, v in zip(dates, values) if d is not None]
        pairs = [p for p in pairs if p[1] is not None]
        pairs.sort(key=lambda p: p[0])
        # 去重：同日期保留最后一条
        dedup = {}
        for d, v in pairs:
            dedup[d] = v
        self.name = name
        self.dates = sorted(dedup.keys())
        self.values = [dedup[d] for d in self.dates]
        self.freq = freq
        self.align = align
        self.unit = unit
        self.note = note
        self._idx = {d: i for i, d in enumerate(self.dates)}

    # -------- 基础 --------
    def __len__(self):
        return len(self.dates)

    def __repr__(self):
        if not self.dates:
            return "<Series %s EMPTY>" % self.name
        return "<Series %s %s..%s n=%d>" % (
            self.name, self.dates[0], self.dates[-1], len(self.dates))

    def value_on(self, d, align=None):
        """事件日 → 对齐后的取值与真实观测日"""
        if not self.dates:
            return (None, None)
        align = align or self.align
        d = to_date(d)
        if d in self._idx:
            i = self._idx[d]
            return (self.values[i], self.dates[i])
        j = bisect_left(self.dates, d)
        if align == "next":
            if j >= len(self.dates):
                return (None, None)
            return (self.values[j], self.dates[j])
        if align == "prev":
            if j == 0:
                return (None, None)
            return (self.values[j - 1], self.dates[j - 1])
        # nearest
        cands = []
        if j > 0:
            cands.append(j - 1)
        if j < len(self.dates):
            cands.append(j)
        if not cands:
            return (None, None)
        best = min(cands, key=lambda i: abs((self.dates[i] - d).days))
        return (self.values[best], self.dates[best])

    def index_on(self, d, align=None):
        v, od = self.value_on(d, align)
        return self._idx.get(od) if od else None

    def at_index(self, i):
        if i is None or i < 0 or i >= len(self.dates):
            return (None, None)
        return (self.values[i], self.dates[i])

    def shift(self, d, k):
        """返回事件日 d 对齐后，向前/向后 k 个观测点（k<0 为之前）"""
        i = self.index_on(d)
        if i is None:
            return (None, None)
        return self.at_index(i + k)

    # -------- 派生序列 --------
    def diff_series(self, other, name=None):
        """两条序列相减（按左序列日历对齐右序列 previous 值）"""
        vals = []
        for d in self.dates:
            ov, _ = other.value_on(d, align="prev")
            v = self.values[self._idx[d]]
            vals.append(None if (v is None or ov is None) else v - ov)
        return Series(name or (self.name + "-" + other.name), self.dates, vals,
                      self.freq, self.align, self.unit, "派生:差值")

    def pct_change_window(self, d, k, mode="pct", baseline=1):
        """事件前 baseline 日 → 事件后 k 日 的变化（pct 或 abs）"""
        b, bd = self.shift(d, -baseline)
        a, ad = self.shift(d, k)
        if b in (None, 0) or a is None:
            return None
        return (a / b - 1.0) if mode == "pct" else (a - b)


# --------------------------------------------------------------------------
# 数据加载
# --------------------------------------------------------------------------
def load_price_csv(path, name=None, value_col="close", freq="D", align="prev", unit="元/吨"):
    """加载 [date, value] 或 [date, open, high, low, close, ...] 格式 CSV"""
    dates, vals = [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames or []
        vcol = value_col if value_col in cols else cols[1]
        for row in rd:
            d = row.get("date") or row.get("日期")
            v = row.get(vcol)
            if v in (None, "", "-", "None", "nan"):
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            dates.append(d)
            vals.append(fv)
    return Series(name or os.path.basename(path), dates, vals, freq, align, unit)


def load_long_csv(path, name_col="series", date_col="date", value_col="value",
                  meta_cols=None):
    """
    加载窄表（一条 CSV 内含多条序列）：
        series,date,value[,region,spec,unit,...]
    返回 {series_name: Series}
    """
    out = {}
    meta = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            k = row.get(name_col)
            if not k:
                continue
            v = row.get(value_col)
            if v in (None, "", "-", "None", "nan"):
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if k not in out:
                out[k] = {"dates": [], "vals": [], "unit": row.get("unit", "")}
                if meta_cols:
                    meta[k] = {c: row.get(c, "") for c in meta_cols}
            out[k]["dates"].append(row[date_col])
            out[k]["vals"].append(fv)
    res = {}
    for k, v in out.items():
        res[k] = Series(k, v["dates"], v["vals"], unit=v["unit"])
    return res, meta


# --------------------------------------------------------------------------
# 事件窗口提取
# --------------------------------------------------------------------------
def extract_window(series, event_date, pre=120, post=120, align=None):
    """
    返回 dict：
      grid      : list of k（相对偏移，含 -pre..+post）
      dates     : 对齐后的日期
      values    : 数值
      base      : 事件前 1 日的值
      k0_index  : 事件日在序列中的索引
    """
    i0 = series.index_on(event_date, align)
    if i0 is None:
        return None
    grid, dates, values = [], [], []
    for k in range(-pre, post + 1):
        v, d = series.at_index(i0 + k)
        if d is None:
            continue
        grid.append(k)
        dates.append(d)
        values.append(v)
    base_v, base_d = series.at_index(i0 - 1)
    return {
        "grid": grid, "dates": dates, "values": values,
        "base": base_v, "base_date": base_d,
        "event_obs_date": series.at_index(i0)[1],
        "i0": i0,
    }


def compute_paths(series, event_date, horizons=(20, 60, 120), align=None):
    """
    对单个序列、单个事件，计算前 n 日 / 后 n 日 / 前后变化。
    返回 dict of horizon -> {...}
    """
    res = {}
    i0 = series.index_on(event_date, align)
    if i0 is None:
        return {"_status": "event_not_on_calendar"}
    e_v, e_d = series.at_index(i0)
    b_v, b_d = series.at_index(i0 - 1)
    for n in horizons:
        pre_v, pre_d = series.at_index(i0 - n)      # 事件前 n 日
        pre2_v, pre2_d = series.at_index(i0 - 2 * n - 1)  # 对称的"更早 n 日"（用于动量基准）
        post_v, post_d = series.at_index(i0 + n)
        chg = None if (b_v is None or post_v is None) else post_v - b_v
        pct = None if (b_v in (None, 0) or post_v is None) else (post_v / b_v - 1.0)
        pre_chg = None if (pre_v is None or b_v is None) else b_v - pre_v
        pre_pct = None if (pre_v in (None, 0) or b_v is None) else (b_v / pre_v - 1.0)
        res[n] = {
            "event_value": e_v, "event_obs_date": iso(e_d),
            "base_value": b_v, "base_date": iso(b_d),
            "pre_value": pre_v, "pre_date": iso(pre_d),
            "post_value": post_v, "post_date": iso(post_d),
            "change": chg, "pct": pct,
            "pre_change": pre_chg, "pre_pct": pre_pct,
            "momentum_ref_value": pre2_v, "momentum_ref_date": iso(pre2_d),
        }
    return res


def compute_paths_by_days(series, event_date, horizons=(20, 60, 120), align=None):
    """
    低频率序列（周度/月度/稀疏）专用：按**自然日**而不是观测个数对齐窗口。
    对每个跨度 n：取事件日之后 n 个自然日内最近的一个观测，与事件日前最近观测比较。
    这样在稀疏数据上不会因为"没有 k 个观测点"而返回空。
    额外返回 obs_count（该窗口内实际观测个数），样本 < 2 时标注为弱证据。
    """
    i0 = series.index_on(event_date, align)
    if i0 is None:
        return {"_status": "event_not_on_calendar"}
    e_d = series.dates[i0]
    b_v, b_d = series.at_index(i0)      # 以事件日当天/之前最近观测为基准
    res = {}
    for n in horizons:
        target = e_d + timedelta(days=n)
        # 窗口内最后一个观测
        j = bisect_right(series.dates, target) - 1
        if j < 0:
            res[n] = {"post_value": None}
            continue
        post_v, post_d = series.at_index(j)
        # 事件前 n 日对应的观测
        k = bisect_right(series.dates, e_d - timedelta(days=n)) - 1
        pre_v, pre_d = series.at_index(k) if k >= 0 else (None, None)
        chg = None if (b_v is None or post_v is None) else post_v - b_v
        pct = None if (b_v in (None, 0) or post_v is None) else (post_v / b_v - 1.0)
        pre_pct = None if (pre_v in (None, 0) or b_v is None) else (b_v / pre_v - 1.0)
        n_obs = sum(1 for dd in series.dates[i0:] if dd <= target)
        res[n] = {
            "event_value": b_v, "event_obs_date": iso(b_d),
            "base_value": b_v, "base_date": iso(b_d),
            "pre_value": pre_v, "pre_date": iso(pre_d),
            "post_value": post_v, "post_date": iso(post_d),
            "change": chg, "pct": pct,
            "pre_change": None if (pre_v is None or b_v is None) else b_v - pre_v,
            "pre_pct": pre_pct,
            "surprise_pct": None if (pct is None or pre_pct is None) else pct - pre_pct,
            "obs_count": n_obs,
        }
    return res


# --------------------------------------------------------------------------
# 统计工具（纯标准库，numpy 可选）
# --------------------------------------------------------------------------
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def stdev(xs):
    """样本标准差（n-1）"""
    xs = [x for x in xs if x is not None]
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def tstat(xs):
    """单样本 t（H0: 均值=0）。样本<2 返回 None。"""
    xs = [x for x in xs if x is not None]
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    s = stdev(xs)
    if s is None or s == 0:
        return None
    return m / (s / math.sqrt(n))


def pct_rank(x, xs):
    """x 在 xs 中的分位（0-100）"""
    xs = [v for v in xs if v is not None]
    if not xs or x is None:
        return None
    below = sum(1 for v in xs if v < x)
    eq = sum(1 for v in xs if v == x)
    return 100.0 * (below + 0.5 * eq) / len(xs)


def bootstrap_mean_ci(xs, n_boot=2000, alpha=0.10, seed=20260101):
    """百分位 bootstrap 置信区间（样本太小仅为参考，不是精确推断）"""
    xs = [x for x in xs if x is not None]
    n = len(xs)
    if n < 3:
        return (None, None)
    import random
    rnd = random.Random(seed)
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += xs[rnd.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot) - 1]
    return (lo, hi)


def sign_test(xs):
    """符号一致性：正号占比 + 二项分布双尾 p（n<=25 精确，否则正态近似）"""
    xs = [x for x in xs if x is not None and x != 0]
    n = len(xs)
    if n == 0:
        return {"n": 0, "pos": 0, "neg": 0, "pos_share": None, "p": None}
    k = sum(1 for x in xs if x > 0)
    p = None
    if n <= 25:
        # 精确二项双尾
        def comb(a, b):
            return math.comb(a, b)
        tail = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / (2 ** n)
        p = min(1.0, 2 * tail)
    else:
        z = (k - n / 2.0) / math.sqrt(n * 0.25)
        # 正态近似双尾
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return {"n": n, "pos": k, "neg": n - k, "pos_share": k / n, "p": p}


# --------------------------------------------------------------------------
# 反事实基准：相对日历对齐的市场平均
# --------------------------------------------------------------------------
def build_relative_counterfactual(series, event_dates, horizons=(20, 60, 120),
                                  min_events=4, align=None):
    """
    对每个事件，取"事件前第 k 个观测点 → 事件后第 k 个观测点"的相对变化；
    汇总成按 k 的市场平均变化曲线。用它对单个事件做 abnormal 分解。

    返回 {"curve": {k: mean_pct}, "count": {k: n}}
    """
    ks = set()
    for n in horizons:
        for k in range(-n, n + 1):
            ks.add(k)
    ks = sorted(ks)
    acc = {k: [] for k in ks}
    for d in event_dates:
        w = extract_window(series, d, pre=max(horizons), post=max(horizons), align=align)
        if not w:
            continue
        base = w["base"]
        if base in (None, 0):
            continue
        for k, v in zip(w["grid"], w["values"]):
            if v is None:
                continue
            acc[k].append(v / base - 1.0)
    curve, counts = {}, {}
    for k in ks:
        arr = acc[k]
        counts[k] = len(arr)
        curve[k] = (sum(arr) / len(arr)) if (arr and len(arr) >= min_events) else None
    return {"curve": curve, "count": counts}


def relative_change(series, event_date, k, align=None):
    """事件基准日 → 偏移 k 的相对变化"""
    b, _ = series.shift(event_date, -1)
    a, _ = series.shift(event_date, k)
    if b in (None, 0) or a is None:
        return None
    return a / b - 1.0


# --------------------------------------------------------------------------
# 事件研究主流程
# --------------------------------------------------------------------------
def run_event_study(events, series_map, horizons=(20, 60, 120), align=None,
                    counterfactual_events=None, do_placebo=True):
    """
    events: list of dict，至少含
        event_id, project_id, project_name, stage, date, design_capacity, region, process
    series_map: {var_key: Series}

    返回：
        per_event  : list（逐项目逐阶段逐变量）
        aggregate  : dict
    """
    per_event = []
    horizons = tuple(sorted(horizons))
    maxh = max(horizons)

    # 反事实曲线
    cf = {}
    if counterfactual_events:
        for vk, s in series_map.items():
            cf[vk] = build_relative_counterfactual(s, counterfactual_events, horizons, align=align)

    for ev in events:
        d = to_date(ev["date"])
        row = {
            "event_id": ev["event_id"],
            "project_id": ev.get("project_id"),
            "project_name": ev.get("project_name"),
            "stage": ev["stage"],
            "stage_label": STAGE_LABEL.get(ev["stage"], ev["stage"]),
            "date": iso(d),
            "region": ev.get("region"),
            "process": ev.get("process"),
            "design_capacity": ev.get("design_capacity"),
            "is_expectation": ev["stage"] in EXPECTATION_STAGES,
            "vars": {},
        }
        for vk, s in series_map.items():
            if d < s.dates[0] - timedelta(days=200) or d > s.dates[-1] + timedelta(days=200):
                row["vars"][vk] = {"_status": "out_of_range"}
                continue
            paths = compute_paths(s, d, horizons, align=align)
            if "_status" in paths:
                row["vars"][vk] = paths
                continue
            for n in horizons:
                p = paths[n]
                # abnormal：扣除同期市场相对日历平均变化
                mkt = None
                if vk in cf and cf[vk]["curve"].get(n) is not None:
                    mkt = cf[vk]["curve"][n]
                p["market_rel_change"] = mkt
                if p["pct"] is not None and mkt is not None:
                    p["abnormal_pct"] = p["pct"] - mkt
                else:
                    p["abnormal_pct"] = None
                # surprise：事件后变化 − 事件前同长度前段变化
                if p["pct"] is not None and p["pre_pct"] is not None:
                    p["surprise_pct"] = p["pct"] - p["pre_pct"]
                else:
                    p["surprise_pct"] = None
            row["vars"][vk] = paths
        per_event.append(row)

    return per_event, aggregate_events(per_event, horizons)


def aggregate_events(per_event, horizons):
    """
    按 (变量, 阶段) 与 (变量, 阶段, 跨度) 汇总。
    只有样本 >= 3 才给 t 值与显著性；< 3 一律标记 insufficient。
    同时计算"事件密集度"（同一项目 ±120 日内其他项目的事件数）作为污染指标。
    """
    agg = []
    # 项目 × 日期 索引，用于密集度
    proj_dates = {}
    for r in per_event:
        proj_dates.setdefault(r["project_id"], set()).add(r["date"])

    for r in per_event:
        d = to_date(r["date"])
        others = 0
        for pid, ds in proj_dates.items():
            if pid == r["project_id"]:
                continue
            for od in ds:
                if abs((to_date(od) - d).days) <= 120:
                    others += 1
                    break
        r["concurrent_projects_within_120d"] = others

    for vk in sorted({vk for r in per_event for vk in r["vars"]}):
        for stage in STAGE_KEYS + ["ALL"]:
            rows = [r for r in per_event if stage == "ALL" or r["stage"] == stage]
            rows = [r for r in rows if isinstance(r["vars"].get(vk), dict) and "grid" not in r["vars"][vk] or True]
            rows = [r for r in rows if isinstance(r["vars"].get(vk), dict) and any(
                isinstance(k2, int) for k2 in r["vars"][vk].keys())]
            if not rows:
                continue
            for n in horizons:
                cum = [r["vars"][vk].get(n, {}).get("pct") for r in rows]
                abn = [r["vars"][vk].get(n, {}).get("abnormal_pct") for r in rows]
                sur = [r["vars"][vk].get(n, {}).get("surprise_pct") for r in rows]
                n_ok = len([x for x in cum if x is not None])
                entry = {
                    "var": vk, "stage": stage,
                    "stage_label": "全部阶段" if stage == "ALL" else STAGE_LABEL[stage],
                    "horizon": n, "n": n_ok,
                    "mean_pct": mean(cum), "median_pct": median(cum),
                    "sd_pct": stdev(cum), "t_cum": tstat(cum),
                    "pos_share": sign_test(cum)["pos_share"],
                    "sign_p": sign_test(cum)["p"],
                    "mean_abnormal": mean(abn), "t_abnormal": tstat(abn),
                    "mean_surprise": mean(sur), "t_surprise": tstat(sur),
                    "insufficient": n_ok < 3,
                }
                lo, hi = bootstrap_mean_ci(cum, alpha=0.10) if n_ok >= 3 else (None, None)
                entry["ci90_lo"], entry["ci90_hi"] = lo, hi
                if n_ok < 3:
                    entry["t_cum"] = None
                    entry["t_abnormal"] = None
                    entry["t_surprise"] = None
                    entry["sign_p"] = None
                agg.append(entry)
    return agg


# --------------------------------------------------------------------------
# 占现有产能比例
# --------------------------------------------------------------------------
def capacity_share(design_capacity, base_capacity, unit="万吨/年"):
    """
    design_capacity: 项目设计产能
    base_capacity  : 投产当期行业现有产能（**不含该项目**）
    返回 dict，含比例、当月实际增量（按爬坡曲线）
    """
    if base_capacity in (None, 0) or design_capacity is None:
        return {"share_pct": None, "note": "产能基数缺失"}
    return {
        "share_pct": 100.0 * design_capacity / base_capacity,
        "note": "",
    }


# 达产爬坡曲线（月序为投产月份，即第 0 个完整月）
DEFAULT_RAMP = [0.30, 0.55, 0.75, 0.85, 0.90, 0.93, 0.95, 0.97, 0.98, 1.00]
RAMP_ASSUMPTION = (
    "默认爬坡曲线为工程经验假设（投料首月约 30% 负荷、第 3 月约 75%、第 6 月约 93%、"
    "第 10 月达 100%），**不是项目披露值**。若项目公开披露高负荷标定日期，应以该日期校准，"
    "并在输出中注明用的是实测达产还是假设曲线。"
)


def incremental_output(design_capacity_wt, month_index, ramp=None, days_in_month=30):
    """
    设计产能(万吨/年) → 某月实际产量增量(万吨)
    关键：不把设计产能当作投产当天的产量
    """
    ramp = ramp or DEFAULT_RAMP
    if design_capacity_wt is None or month_index < 0:
        return 0.0
    r = ramp[month_index] if month_index < len(ramp) else 1.0
    return design_capacity_wt * r * days_in_month / 365.0


def cumulative_output(design_capacity_wt, months, ramp=None, days_in_month=30):
    return sum(incremental_output(design_capacity_wt, m, ramp, days_in_month)
               for m in range(months))


# --------------------------------------------------------------------------
# 安慰剂检验：把事件日随机平移，看真实效应是否显著不同于噪声
# --------------------------------------------------------------------------
def placebo_test(series, event_dates, horizon=60, n_draw=200, seed=20260101,
                 jitter_days=(-180, 180)):
    """
    真实事件的 average pct 变化 vs 随机平移日期的分布。
    返回真实值、随机均值的 p 值（双尾）、分位。
    """
    import random
    rnd = random.Random(seed)
    real = [relative_change(series, d, horizon) for d in event_dates]
    real = [x for x in real if x is not None]
    if not real:
        return {"_status": "no_data"}
    real_mean = sum(real) / len(real)
    lo_d, hi_d = series.dates[0], series.dates[-1]
    draws = []
    valid_events = [d for d in event_dates if lo_d <= to_date(d) <= hi_d]
    for _ in range(n_draw):
        vals = []
        for d in valid_events:
            off = rnd.randint(*jitter_days)
            dd = to_date(d) + timedelta(days=off)
            v = relative_change(series, dd, horizon)
            if v is not None:
                vals.append(v)
        if vals:
            draws.append(sum(vals) / len(vals))
    if len(draws) < 10:
        return {"_status": "insufficient_draws"}
    draws.sort()
    p = sum(1 for x in draws if abs(x) >= abs(real_mean)) / len(draws)
    return {
        "real_mean_pct": real_mean, "n_events": len(real),
        "placebo_mean": sum(draws) / len(draws),
        "placebo_sd": stdev(draws),
        "p_value_two_sided": p,
        "real_percentile": pct_rank(real_mean, draws),
        "n_draws": len(draws),
    }


# --------------------------------------------------------------------------
# 序列化辅助
# --------------------------------------------------------------------------
def _clean(o):
    if isinstance(o, float):
        if o != o or o in (float("inf"), float("-inf")):
            return None
        return round(o, 6)
    if isinstance(o, (date, datetime)):
        return iso(o.date() if isinstance(o, datetime) else o)
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def dump_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_clean(obj), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fp = os.path.join(base, "data", "raw", "pp_futures_pp0_daily.csv")
    s = load_price_csv(fp, name="PP主力连续")
    print(s)
    print("2014-02-28 收盘:", s.value_on("2014-02-28"))
    print("2026-10-20 收盘:", s.value_on("2026-10-20"))
    print("相对日历 20 日:", relative_change(s, "2026-10-20", 20))
    print("提取窗口:", len(extract_window(s, "2023-02-01", 20, 20)["grid"]))
