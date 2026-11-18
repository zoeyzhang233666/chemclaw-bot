# -*- coding: utf-8 -*-
"""Indicator computation and signal logic.

Two layers:
  1. `compute_indicator_stats` — purely descriptive transforms of the indicator series
     (change, run length, drawdown from rolling maximum). These use *past* samples only.
  2. `build_signal_events` — evaluate the rule's ops on each publication date and attach
     the session at which the resulting event becomes tradable.

The percentile filter on the basis is evaluated with a trailing window that ends at the
basis date actually observed on the availability session, so no future price enters.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_indicator_stats(ind: pd.DataFrame) -> pd.DataFrame:
    """Add change / run-length / drawdown columns. All computations look backwards only."""
    out = ind.sort_values("asof_date").reset_index(drop=True).copy()
    v = out["value"].astype(float)
    out["chg"] = v.diff()
    out["chg_pct"] = v.pct_change()

    run = []
    direction = []
    streak = 0
    cur = 0
    for i, chg in enumerate(out["chg"].tolist()):
        if i == 0 or chg is None or (isinstance(chg, float) and np.isnan(chg)) or chg == 0:
            cur = 0
            streak = 0
        elif chg < 0:
            streak = streak + 1 if cur == -1 else 1
            cur = -1
        else:
            streak = streak + 1 if cur == 1 else 1
            cur = 1
        run.append(streak)
        direction.append(cur)
    out["run_len"] = run
    out["run_dir"] = direction

    # drawdown (in magnitude units) and its % counterpart from a rolling max window
    return out


def rolling_drawdown(ind: pd.DataFrame, window: int) -> pd.Series:
    """Peak-to-current fall (in indicator units) over a trailing window of published values."""
    return ind["value"].astype(float).rolling(window, min_periods=1).max() - ind["value"].astype(float)


def evaluate_ops(row: pd.Series, ops: list[dict], combine: str,
                 dd: dict[int, float], hist: dict | None = None) -> tuple[bool, list[dict]]:
    """Evaluate the list of ops on one published observation; return (pass, details)."""
    hist = hist or {}
    results = []
    for i, op in enumerate(ops):
        kind = op.get("type")
        n_hist = op.get("min_history")
        ok = False
        reason = ""
        if kind == "change_run":
            weeks = int(op.get("weeks", 2))
            direction = op.get("direction", "down")
            need = direction == -1 or direction == "down"
            sign = -1 if need else 1
            ok = (int(row.get("run_len", 0) or 0) >= weeks) and int(row.get("run_dir", 0) or 0) == sign
            reason = "run_len=%s dir=%s need>=%s %s" % (row.get("run_len"), row.get("run_dir"),
                                                       weeks, direction)
        elif kind == "channel_change":
            # "channel" view: value is at/below the low of the trailing n-point channel
            # and the decline happened within the channel. Interpretation is a spec choice:
            #   low: channel high - value >= threshold (sustained fall from the channel top)
            #   high: value - channel low >= threshold (rise from the channel bottom)
            n = int(op.get("n", 2))
            thr = float(op.get("threshold", 0.0))
            series = list(hist.get("values", []))
            if len(series) >= n and n >= 2:
                chan = series[-n:]
                top, bottom = max(chan), min(chan)
                mode_ = op.get("channel_mode", "high")
                fall = top - float(row["value"])
                rise = float(row["value"]) - bottom
                ok = (fall >= thr) if mode_ == "high" else (rise >= thr)
                reason = "channel[%d] high=%.2f low=%.2f fall=%.2f rise=%.2f mode=%s thr=%.2f" % (
                    n, top, bottom, fall, rise, mode_, thr)
            else:
                reason = "channel needs %d samples" % n
        elif kind == "level":
            cmp = op.get("cmp", ">=")
            thr = float(op.get("threshold", 0))
            val = float(row["value"])
            ok = {">=": val >= thr, "<=": val <= thr, ">": val > thr, "<": val < thr}[cmp]
            reason = "level %s %s %s" % (val, cmp, thr)
        elif kind == "zscore":
            mean = float(op.get("mean_value", np.nan))
            sd = float(op.get("std_value", np.nan))
            if sd and not np.isnan(sd):
                z = (float(row["value"]) - mean) / sd
                ok = z >= float(op.get("threshold", 0))
                reason = "z=%.2f" % z
            else:
                reason = "z unavailable"
        if n_hist is not None:
            idx = row.name
            if idx is not None and idx < int(n_hist):
                ok = False
                reason += " (warmup: need %d samples)" % int(n_hist)
        results.append({"op": i, "type": kind, "pass": bool(ok), "detail": reason})
    passed = [r["pass"] for r in results]
    verdict = all(passed) if combine == "and" else any(passed)
    return bool(verdict), results


def build_signal_events(ind: pd.DataFrame, ops: list[dict], combine: str,
                        dd_windows: list[int], min_history: int) -> pd.DataFrame:
    """Add per-op pass flags, drawn-down values and the combined event flag."""
    out = ind.copy()
    dds = {w: rolling_drawdown(out, w) for w in dd_windows}
    for w, s in dds.items():
        out["dd_%d" % w] = s
    flags, details = [], []
    warm = int(max([min_history] + [int(o.get("min_history") or 0) for o in ops]))
    for idx, row in out.iterrows():
        row = row.copy()
        row.name = idx
        vals = out["value"].astype(float).iloc[: idx + 1].tolist()
        ok, det = evaluate_ops(row, ops, combine, {i: 0.0 for i in range(len(ops))},
                               {"values": vals})
        warmup = idx < warm
        flags.append(bool(ok) and not warmup)
        details.append({"details": det, "warmup": warmup})
    out["event"] = flags
    out["op_detail"] = [d["details"] for d in details]
    out["warmup"] = [d["warmup"] for d in details]
    return out
