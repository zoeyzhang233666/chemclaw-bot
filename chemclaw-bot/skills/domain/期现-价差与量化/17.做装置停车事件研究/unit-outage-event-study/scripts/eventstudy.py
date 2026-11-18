# -*- coding: utf-8 -*-
"""eventstudy.py — 事件日对齐、价格路径、异常收益与分布统计

用法（命令行）：
    python scripts/eventstudy.py --project <项目目录> --out <输出目录>

项目目录约定：
    events.csv            事件表（可中文表头，见 references/02-event-table-spec.md）
    data/prices.csv       交易日序列：date, close（期货主力或连续合约收盘）
    data/benchmark.csv    可选：date, close（市场基准；必须与标的同一交易日序列）
    project.json          口径配置（见 references/05-project-json.md）

不插值、不补数：任何取不到的交易日都记为缺失，并在事件行里写 gap。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import core  # noqa: E402
from core import Event, TradingCalendar, describe, bootstrap_ci, wilcoxon_like_summary, quantile  # noqa: E402


# ---------------------------------------------------------------------------
# 价格面板
# ---------------------------------------------------------------------------

class PricePanel:
    """交易日价格序列。索引 = 交易日序号，保证各序列同一日历对齐。"""

    def __init__(self, rows: Sequence[Dict[str, Any]], date_col: str = "date", close_col: str = "close"):
        data: Dict[str, float] = {}
        for r in rows:
            d = core.parse_date(r.get(date_col))
            c = core.parse_float(r.get(close_col))
            if d and c is not None:
                data[d] = c
        self.data = dict(sorted(data.items()))
        self.cal = TradingCalendar(self.data.keys())

    def close(self, d: Optional[str]) -> Optional[float]:
        return None if d is None else self.data.get(d)

    def ret(self, d0: str, d1: str) -> Optional[float]:
        """区间收益（%）。d0 必须早于 d1，且两个都是真实交易日。"""
        a, b = self.close(d0), self.close(d1)
        if a is None or b is None or a == 0:
            return None
        return (b / a - 1.0) * 100.0


@dataclass
class StudyConfig:
    price_col: str = "close"
    anchor_kind: str = "first_market"      # first_market | actual_start
    windows: List[int] = field(default_factory=lambda: [1, 5, 10, 20])
    pre_window: int = 20                    # 估计窗口长度（交易日）
    min_pre_obs: int = 10                   # 估计窗口最少样本
    benchmark_mode: str = "market_model"    # none | market_model | mean_adjusted | matched_day
    matched_days: int = 250                 # matched_day 模式：往前找多少个交易日做匹配（年=250）
    matched_min_n: int = 10
    include_restart: bool = False
    min_evidence_grade: str = "E3"
    dedup: bool = True
    capacity_threshold_wt: Optional[float] = None   # 若设置，则产能缺失者单列、不进阈值合规子样本
    # 区间状态标记：换月日落在窗口内 / 事件前波动率处于高分位
    flag_rolls: bool = True
    flag_volatility: bool = True
    vol_lookback: int = 60                  # 波动率分位数的回溯窗口（交易日）
    vol_high_pct: float = 0.80              # 超过该分位视为“高波动区”
    display_tzone: str = "Asia/Shanghai"


def load_roll_dates(path: str) -> List[str]:
    """换月清单（rolls.csv）里的换月日期集合；文件不存在则返回空。"""
    if not os.path.exists(path):
        return []
    return [r["date"] for r in core.read_csv(path) if r.get("date")]


def realized_vol(path: str) -> Dict[str, float]:
    """逐日年化波动率（20 交易日滚动标准差 × sqrt(250)），用于判断事件是否落在高波动区。"""
    rows = core.read_csv(path)
    rec = []
    for r in rows:
        d = core.parse_date(r.get("date"))
        c = core.parse_float(r.get("adj_close")) or core.parse_float(r.get("close"))
        if d and c:
            rec.append((d, c))
    rec.sort()
    rets = []
    for i in range(1, len(rec)):
        rets.append((rec[i][0], (rec[i][1] / rec[i - 1][1] - 1) * 100))
    out: Dict[str, float] = {}
    k = 20
    for i in range(k, len(rets)):
        w = [x[1] for x in rets[i - k:i]]
        m = sum(w) / k
        var = sum((x - m) ** 2 for x in w) / (k - 1)
        out[rets[i][0]] = math.sqrt(var) * math.sqrt(250)
    return out


def _grade_ok(grade: str, floor: str) -> bool:
    order = ["E1", "E2", "E3", "E4", "E5"]
    try:
        return order.index(grade.upper()) <= order.index(floor.upper())
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# 事件对齐
# ---------------------------------------------------------------------------

def anchor_date_for(ev: Event, cal: TradingCalendar, kind: str) -> Tuple[Optional[str], str, List[str]]:
    """把事件映射到“可交易的锚定日”。

    规则：
      - 事件日不是交易日（周末/节假日/停牌）→ 顺延到其后第一个交易日，并记录 flag。
      - first_market 口径优先；缺失时回退 actual_start 并记录 gap（不得混用为同一名单）。
      - 事件日早于价格序列起点或晚于终点 → 不纳入，记录 gap。
    """
    flags: List[str] = []
    gaps: List[str] = []
    src_date: Optional[str] = None
    used_kind = kind
    if kind == "actual_start":
        src_date = ev.actual_start_date
        if not src_date:
            gaps.append("actual_start_date 缺失")
    else:
        src_date = ev.first_market_date
        if not src_date:
            gaps.append("first_market_date 缺失")
    if not src_date:
        return None, used_kind, gaps + flags

    if cal.contains(src_date):
        return src_date, used_kind, flags

    nxt = cal.next_on_or_after(src_date)
    if nxt is None:
        gaps.append("事件日晚于价格序列终点")
        return None, used_kind, gaps + flags
    if src_date < cal.days[0]:
        gaps.append("事件日早于价格序列起点")
        return None, used_kind, gaps + flags
    gap_days = (cal and (core.parse_date(nxt) and (__import__("datetime").date.fromisoformat(nxt)
                - __import__("datetime").date.fromisoformat(src_date)).days)) or 0
    flags.append(f"事件日 {src_date} 非交易日，顺延 {gap_days} 个自然日到 {nxt}")
    if gap_days >= 3:
        flags.append("疑似长假/停牌，顺延跨度≥3天")
    return nxt, used_kind, gaps + flags


def build_windows(cal: TradingCalendar, anchor: str, windows: Sequence[int],
                  pre: int) -> Tuple[Dict[str, Optional[str]], Optional[str], List[str]]:
    gaps: List[str] = []
    base = cal.index(anchor)
    if base is None:
        return {}, None, ["锚定日不在日历内"]
    pre_d = cal.shift(anchor, -pre)
    if pre_d is None:
        gaps.append(f"锚定日前不足 {pre} 个交易日")
    out: Dict[str, Optional[str]] = {}
    for w in windows:
        d = cal.shift(anchor, w)
        if d is None:
            gaps.append(f"锚定日后不足 {w} 个交易日（序列已到末端）")
        out[f"t+{w}"] = d
    return out, pre_d, gaps


# ---------------------------------------------------------------------------
# 基准调整
# ---------------------------------------------------------------------------

def estimate_market_model(bench: PricePanel, rel_cal: TradingCalendar, t0_idx: int,
                          pre: int, min_obs: int):
    """在锚定日之前的估计窗口内，用基准收益对标的收益做 OLS（单因子市场模型）。

    返回 (alpha, beta, n_obs, note)。不做任何外推。
    """
    rows = []
    for i in range(max(1, t0_idx - pre), t0_idx):
        d0, d1 = rel_cal.days[i - 1], rel_cal.days[i]
        rb = bench.ret(d0, d1)
        rows.append((i, rb))
    rows = [(i, rb) for i, rb in rows if rb is not None]
    if len(rows) < min_obs:
        return None, None, len(rows), f"估计窗口仅 {len(rows)} 个可用观测 < {min_obs}，不做市场模型"
    return None, None, len(rows), "由调用方在标的序列上计算"


def ols_beta_alpha(pairs: List[Tuple[float, float]]) -> Tuple[float, float]:
    """y = alpha + beta*x 的 OLS 估计（纯标准库）"""
    n = len(pairs)
    if n < 2:
        raise ValueError("样本不足")
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    beta = sxy / sxx if sxx else 0.0
    alpha = my - beta * mx
    return beta, alpha


def matched_day_baseline(target: PricePanel, target_cal: TradingCalendar, bench: PricePanel,
                         anchor: str, w: int, lookback: int, min_n: int) -> Dict[str, Any]:
    """匹配日基线：在锚定日之前 lookback 个交易日里，找出“标的同窗口收益”分布，
    再比较本次事件窗口收益在其中的分位。用于回答“这次涨跌在历史日常波动里算不算异常”。
    """
    i0 = target_cal.index(anchor)
    if i0 is None:
        return {"ok": False, "reason": "锚定日不在日历内"}
    start = max(w, i0 - lookback)
    vals = []
    for i in range(start, i0):
        d0, d1 = target_cal.days[i - w], target_cal.days[i]
        r = target.ret(d0, d1)
        if r is not None:
            vals.append(r)
    if len(vals) < min_n:
        return {"ok": False, "reason": f"匹配日样本 {len(vals)} < {min_n}"}
    return {"ok": True, "n": len(vals), "p10": quantile(vals, .1), "p50": quantile(vals, .5),
            "p90": quantile(vals, .9), "sd": statistics.pstdev(vals),
            "mean": sum(vals) / len(vals)}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run(project_dir: str, out_dir: str, cfg: Optional[StudyConfig] = None) -> Dict[str, Any]:
    cfg = cfg or StudyConfig()
    core.ensure_dir(out_dir)
    events = core.load_events_csv(os.path.join(project_dir, "events.csv"))
    prices = core.read_csv(os.path.join(project_dir, "data", "prices.csv"))
    target = PricePanel(prices, "date", cfg.price_col)
    cal = target.cal

    bench = None
    bpath = os.path.join(project_dir, "data", "benchmark.csv")
    if cfg.benchmark_mode != "none" and os.path.exists(bpath):
        bench = PricePanel(core.read_csv(bpath), "date", cfg.price_col)

    # 区间状态标记所需的辅助信息（缺失则该标记自动跳过，不影响主计算）
    roll_dates_for_flag: List[str] = []
    rpath = os.path.join(project_dir, "data", "rolls.csv")
    if cfg.flag_rolls and os.path.exists(rpath):
        roll_dates_for_flag = load_roll_dates(rpath)
    vol_series: Dict[str, float] = {}
    if cfg.flag_volatility:
        vol_series = realized_vol(os.path.join(project_dir, "data", "prices.csv"))

    # ---- 1. 去重（标注，不自动删） ----
    dup_groups = core.find_duplicates(events) if cfg.dedup else []

    # ---- 2. 逐事件对齐 ----
    results: List[Dict[str, Any]] = []
    for ev in events:
        if not ev.include_flag:
            ev.gaps.append("include_flag=否（未纳入样本）")
        if ev.product_verified is False:
            ev.gaps.append("产品核验失败（正文主体不是本品种）")
        if ev.event_type == "restart" and not cfg.include_restart:
            ev.gaps.append("重启事件，未开启 include_restart")
        if not _grade_ok(ev.evidence_grade, cfg.min_evidence_grade):
            ev.gaps.append(f"证据等级 {ev.evidence_grade} 低于下限 {cfg.min_evidence_grade}")

        anchor, used_kind, flags_gaps = anchor_date_for(ev, cal, cfg.anchor_kind)
        ev.anchor_date = anchor
        ev.anchor_kind = used_kind
        for f in flags_gaps:
            (ev.flags if not f.endswith("缺失") and "早于" not in f and "晚于" not in f else ev.gaps).append(f)

        rec: Dict[str, Any] = {**ev.to_row(), "used": False}
        if not anchor:
            results.append(rec)
            continue

        wd, pre_d, wgaps = build_windows(cal, anchor, cfg.windows, cfg.pre_window)
        ev.gaps.extend(wgaps)
        rec["window_dates"] = wd
        rec["pre_start_date"] = pre_d

        # 价格水平与累计收益（区间从锚定日算起；若序列已到头，则退化为可得的最长窗口并标注）
        t0_idx = cal.index(anchor)
        p0 = target.close(anchor)
        rec["t0_close"] = p0
        for w in cfg.windows:
            d = wd.get(f"t+{w}")
            end_idx = cal.index(d) if d else (len(cal.days) - 1)
            rec[f"close_t+{w}"] = target.close(d)
            rec[f"ret_t+{w}_pct"] = target.ret(anchor, d) if d else None
            if not d and end_idx > t0_idx:
                rec[f"partial_t+{w}_days"] = end_idx - t0_idx
                rec[f"partial_t+{w}_ret_pct"] = target.ret(anchor, cal.days[end_idx])

        # 区间状态：是否有换月日落在 [t0, t+w]（换月会让区间收益口径变化，需标注）
        if cfg.flag_rolls and roll_dates_for_flag:
            for w in cfg.windows:
                d = wd.get(f"t+{w}")
                if not d:
                    continue
                inner = [r for r in roll_dates_for_flag if anchor <= r <= d]
                if inner:
                    ev.flags.append(f"t+{w} 区间内含换月日 {','.join(inner)}（已后向复权）")
                    rec[f"roll_in_t+{w}"] = ",".join(inner)

        # 区间状态：事件前波动率分位（高波动区间里，同样的涨跌不具可比性）
        if cfg.flag_volatility and vol_series:
            pre_days = cal.days[max(0, t0_idx - cfg.vol_lookback):t0_idx]
            hist = [vol_series[d] for d in pre_days if d in vol_series]
            v_now = vol_series.get(anchor)
            if len(hist) >= 20 and v_now is not None:
                pct = sum(1 for x in hist if x < v_now) / len(hist)
                rec["vol_at_t0_ann_pct"] = v_now
                rec["vol_precentile"] = pct
                if pct >= cfg.vol_high_pct:
                    ev.flags.append(f"事件日年化波动率 {v_now:.1f}% 处于前 {100-100*pct:.0f}% 高波动区")

        # 事件前路径
        pre_ret: Dict[str, Optional[float]] = {}
        for k in (-10, -5, -3, -1):
            d = cal.shift(anchor, k)
            r = target.ret(d, anchor) if d else None
            pre_ret[f"ret_{k}d_pct"] = r
            rec[f"ret_{k}d_pct"] = r
        rec["pre_ret"] = pre_ret
        rec["pre_close_minus1"] = target.close(cal.shift(anchor, -1))

        # 事件当日收益（对照“前一日收盘 → 事件日收盘”）
        rec["ret_t0_pct"] = target.ret(cal.shift(anchor, -1), anchor) if cal.shift(anchor, -1) else None

        # 基准调整
        if bench is not None and cfg.benchmark_mode in ("market_model", "mean_adjusted"):
            pairs = []
            for i in range(max(1, t0_idx - cfg.pre_window), t0_idx):
                b0, b1 = cal.days[i - 1], cal.days[i]
                rt = target.ret(b0, b1)
                rb = bench.ret(b0, b1)
                if rt is not None and rb is not None:
                    pairs.append((rb, rt))
            if len(pairs) >= cfg.min_pre_obs and cfg.benchmark_mode == "market_model":
                beta, alpha = ols_beta_alpha(pairs)
                rec["alpha"], rec["beta"], rec["est_n"] = alpha, beta, len(pairs)
                for w in cfg.windows:
                    d = wd.get(f"t+{w}")
                    rb = bench.ret(anchor, d) if d else None
                    rt = rec.get(f"ret_t+{w}_pct")
                    if rb is not None and rt is not None:
                        rec[f"ar_t+{w}_pct"] = rt - (alpha + beta * rb)
                        rec[f"benchmark_ret_t+{w}_pct"] = rb
                    else:
                        ev.gaps.append(f"t+{w} 基准收益缺失，异常收益留空")
            elif cfg.benchmark_mode == "mean_adjusted":
                m = sum(p[1] for p in pairs) / len(pairs)
                rec["alpha"], rec["beta"], rec["est_n"] = m, 0.0, len(pairs)
                for w in cfg.windows:
                    rt = rec.get(f"ret_t+{w}_pct")
                    if rt is not None:
                        rec[f"ar_t+{w}_pct"] = rt - m
                        rec[f"benchmark_ret_t+{w}_pct"] = 0.0
            else:
                ev.gaps.append(f"估计窗口可用观测 {len(pairs)} < {cfg.min_pre_obs}，无法做基准调整")

        if cfg.benchmark_mode == "matched_day":
            for w in cfg.windows:
                mb = matched_day_baseline(target, cal, bench, anchor, w, cfg.matched_days, cfg.matched_min_n)
                rec[f"matched_t+{w}"] = mb

        rec["used"] = True
        rec["in_comparison_set"] = (rec.get("include_flag") is not False
                                    and ev.product_verified is not False
                                    and (ev.event_type != "restart" or cfg.include_restart)
                                    and _grade_ok(ev.evidence_grade, cfg.min_evidence_grade))
        rec["flags"] = ev.flags
        rec["gaps"] = ev.gaps
        results.append(rec)

    # ---- 3. 重叠检测（在可比集上） ----
    spans = []
    for r in results:
        if r.get("used") and r.get("anchor_date"):
            i0 = cal.index(r["anchor_date"])
            spans.append((r["event_id"], i0 + min(cfg.windows) * 0 - (cfg.windows[0] + 0), i0 + max(cfg.windows), r["anchor_date"]))
    # 实际重叠判定窗口：[-5, max window]
    spans = [(eid, cal.index(ad) - 5, cal.index(ad) + max(cfg.windows), ad) for eid, _, _, ad in spans]
    ov = core.overlap_pairs(spans, (-5, max(cfg.windows)))[0]
    overlap_map: Dict[str, List[str]] = {}
    for p in ov["overlap_pairs"]:
        overlap_map.setdefault(p["excluded"], []).append(p["kept"])
        overlap_map.setdefault(p["kept"], []).append(p["excluded"])
    for r in results:
        r["overlaps_with"] = overlap_map.get(r["event_id"], [])

    # ---- 4. 统计 ----
    def subset(rs, dedup=False):
        s = [r for r in rs if r.get("used") and r.get("in_comparison_set")]
        if dedup:
            keep = set(ov["kept_in_dedup_subsample"])
            s = [r for r in s if r["event_id"] in keep]
        return s

    stats: Dict[str, Any] = {}
    for label, rs in (("all", subset(results)), ("dedup", subset(results, True))):
        block: Dict[str, Any] = {"n": len(rs), "windows": {}}
        for w in cfg.windows:
            rets = [r.get(f"ret_t+{w}_pct") for r in rs]
            ars = [r.get(f"ar_t+{w}_pct") for r in rs]
            block["windows"][f"t+{w}"] = {
                "raw_return": describe(rets),
                "abnormal_return": describe(ars),
                "abnormal_sign_test": wilcoxon_like_summary(ars),
                "abnormal_boot_ci_mean": bootstrap_ci([a for a in ars if a is not None]),
                "abnormal_boot_ci_median": bootstrap_ci([a for a in ars if a is not None], stat="median"),
            }
        block["pre_path"] = {k: describe([r.get(k) for r in rs]) for k in
                             ("ret_-10d_pct", "ret_-5d_pct", "ret_-3d_pct", "ret_-1d_pct", "ret_t0_pct")}
        stats[label] = block

    # ---- 5. 输出 ----
    core.write_csv(os.path.join(out_dir, "event_results.csv"),
                   [{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                     for k, v in r.items()} for r in results])
    core.dump_json(os.path.join(out_dir, "stats.json"), stats)
    core.dump_json(os.path.join(out_dir, "overlap.json"), ov)
    core.dump_json(os.path.join(out_dir, "duplicates.json"), {"groups": dup_groups})
    core.dump_json(os.path.join(out_dir, "config.json"), cfg.__dict__)
    return {"results": results, "stats": stats, "overlap": ov, "duplicates": dup_groups,
            "calendar": {"n_days": len(cal), "start": cal.days[0] if len(cal) else None,
                         "end": cal.days[-1] if len(cal) else None}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="化工装置停车事件研究：对齐与统计")
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--anchor", default="first_market", choices=["first_market", "actual_start"])
    ap.add_argument("--windows", default="1,5,10,20")
    ap.add_argument("--pre", type=int, default=20)
    ap.add_argument("--benchmark", default="market_model",
                    choices=["none", "market_model", "mean_adjusted", "matched_day"])
    ap.add_argument("--include-restart", action="store_true")
    ap.add_argument("--min-grade", default="E3")
    args = ap.parse_args(argv)
    cfg = StudyConfig(anchor_kind=args.anchor, windows=[int(x) for x in args.windows.split(",")],
                      pre_window=args.pre, benchmark_mode=args.benchmark,
                      include_restart=args.include_restart, min_evidence_grade=args.min_grade)
    res = run(args.project, args.out, cfg)
    st = res["stats"]["all"]
    print(f"[OK] 事件 {len(res['results'])} 条，可比集 n={st['n']}；日历 "
          f"{res['calendar']['start']} ~ {res['calendar']['end']}（{res['calendar']['n_days']} 个交易日）")
    for w, b in st["windows"].items():
        ar = b["abnormal_return"]
        if ar.get("n"):
            print(f"   {w}: 原始收益均值 {ar['mean']:+.2f}% 中位 {ar['median']:+.2f}% (n={ar['n']})")
    print(f"[输出] {args.out}")


if __name__ == "__main__":
    main()
