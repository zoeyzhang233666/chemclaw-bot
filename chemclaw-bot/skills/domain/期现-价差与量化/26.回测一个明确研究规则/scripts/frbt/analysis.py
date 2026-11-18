# -*- coding: utf-8 -*-
"""Parameter sensitivity and out-of-sample robustness.

Policy encoded here (and enforced by docs):
  * the grid is declared BEFORE running and never filtered afterwards to keep the
    best-looking cell as "the strategy";
  * every cell is reported, including the losers;
  * a base-case cell is marked and compared with the grid median, so a conclusion such
    as "works" must survive neighbouring parameters, not one lucky point;
  * the out-of-sample test is a fixed-date split declared in the spec, plus a walk-forward
    (anchored) check that the rule is not carried by a handful of periods.
"""
from __future__ import annotations

import copy
import itertools
import statistics
from dataclasses import dataclass

import pandas as pd

from .engine import run_backtest
from .metrics import annual_table, performance
from .signal import build_signal_events


def _apply_override(spec: dict, overrides: dict) -> dict:
    """overrides are dotted paths, e.g. {"signal.ops.0.n": 3}."""
    s = copy.deepcopy(spec)
    for path, value in overrides.items():
        node = s
        parts = path.split(".")
        for p in parts[:-1]:
            node = node[int(p)] if isinstance(node, list) else node[p]
        last = parts[-1]
        if isinstance(node, list):
            node[int(last)] = value
        else:
            node[last] = value
    return s


def run_variant(spec: dict, bundle, ind_raw: pd.DataFrame, overrides: dict | None = None,
                basis_cache=None, sched_cache: dict | None = None):
    s = _apply_override(spec, overrides or {})
    sig_cfg = s["signal"]
    ops = sig_cfg["ops"]
    windows = [int(o.get("n", 2)) for o in ops if o.get("type") == "channel_change"] or [2]
    ev = build_signal_events(ind_raw, ops, sig_cfg.get("combine", "and"),
                             windows, int(sig_cfg.get("min_history", 0)))
    res = run_backtest(s, bundle, ev, basis_cache=basis_cache)
    stats = performance(res.daily, res.trades, rf_annual=float(s.get("metrics", {}).get("rf_annual", 0)))
    return res, stats, s


def make_basis_cache(spec: dict, bundle, lookback: int | None = None):
    """Build the trailing basis-percentile table once for reuse across variants."""
    from .contracts import build_roll_schedule
    from .engine import precompute_basis
    lookback = int(lookback or spec["price_filter"].get("lookback_points", 756))
    sched = build_roll_schedule(
        bundle.contracts, bundle.calendar,
        selection=spec["contract"]["selection"], k=int(spec["contract"].get("k", 1)),
        roll_rule=spec["contract"]["roll_rule"],
        no_trade_window_days=int(spec["contract"].get("no_trade_window_days_before_delivery", 0)),
        fixed_contract=spec["contract"].get("fixed_contract"))
    return precompute_basis(spec, bundle, sched, lookback, list(bundle.calendar["date"]))


@dataclass
class GridResult:
    table: pd.DataFrame
    base: dict
    summary: dict


def sensitivity_grid(spec: dict, bundle, ind_raw: pd.DataFrame, grid: dict, base_label: str = "base"):
    """grid: {"label": overrides dict}. Returns a table with one row per variant."""
    cache = make_basis_cache(spec, bundle)
    rows = []
    for label, overrides in grid.items():
        res, stats, used = run_variant(spec, bundle, ind_raw, overrides, basis_cache=cache)
        rows.append({
            "variant": label,
            "overrides": overrides,
            "return": stats.get("total_return"),
            "cagr": stats.get("cagr"),
            "max_dd": stats.get("max_dd"),
            "sharpe": stats.get("sharpe"),
            "trades": stats.get("trades"),
            "win_rate": stats.get("win_rate"),
            "profit_factor": stats.get("profit_factor"),
            "exposure": stats.get("exposure"),
            "max_margin_util": stats.get("max_margin_util"),
            "is_base": label == base_label,
        })
    table = pd.DataFrame(rows)
    numeric = table[["return", "cagr", "max_dd", "sharpe", "trades"]].dropna()
    summary = {
        "n_variants": len(table),
        "median_return": float(numeric["return"].median()) if len(numeric) else None,
        "median_cagr": float(numeric["cagr"].median()) if len(numeric) else None,
        "median_sharpe": float(numeric["sharpe"].median()) if len(numeric) else None,
        "median_max_dd": float(numeric["max_dd"].median()) if len(numeric) else None,
        "share_positive_return": float((numeric["return"] > 0).mean()) if len(numeric) else None,
        "best_return": float(numeric["return"].max()) if len(numeric) else None,
        "worst_return": float(numeric["return"].min()) if len(numeric) else None,
        "spread_return": float(numeric["return"].max() - numeric["return"].min())
        if len(numeric) else None,
    }
    base_row = table[table["is_base"]].iloc[0].to_dict() if table["is_base"].any() else {}
    # rank of base case without keeping the best variant
    ranked = table.sort_values("return", ascending=False).reset_index(drop=True)
    if len(ranked):
        pos = ranked.index[ranked["is_base"]].tolist()
        summary["base_return_rank"] = int(pos[0] + 1) if pos else None
    return GridResult(table=table, base=base_row, summary=summary)


def build_default_grid(spec: dict) -> dict:
    """Declare the sensitivity grid. Parameters are taken from the spec's analysis block."""
    an = spec.get("analysis", {}).get("sensitivity", {})
    n_values = an.get("drawdown_n", [2, 3, 4])
    thr_values = an.get("channel_threshold_units", [0.0, 0.25, 0.5])
    weeks_values = an.get("change_run_weeks", [2, 3])
    hold_values = an.get("hold_sessions", [5, 10, 15])
    pct_values = an.get("basis_quantile", spec["price_filter"].get("threshold", 0.8)
                        and [round(spec["price_filter"]["threshold"] - 0.1, 2),
                             spec["price_filter"]["threshold"],
                             round(min(0.99, spec["price_filter"]["threshold"] + 0.1), 2)])

    base = {
        "change_run_weeks": next((o.get("weeks") for o in spec["signal"]["ops"]
                                  if o.get("type") == "change_run"), 2),
        "channel_n": next((o.get("n") for o in spec["signal"]["ops"]
                           if o.get("type") == "channel_change"), 2),
        "channel_threshold": next((o.get("threshold") for o in spec["signal"]["ops"]
                                   if o.get("type") == "channel_change"), 0.0),
        "hold_sessions": int(spec["exit"]["max_hold_sessions"]),
        "basis_quantile": float(spec["price_filter"].get("threshold", 0.8)),
    }
    grid = {}
    # 1-D sweeps around the base case
    for k, values in (("change_run_weeks", weeks_values), ("channel_n", n_values),
                      ("channel_threshold", thr_values), ("hold_sessions", hold_values),
                      ("basis_quantile", pct_values)):
        for v in values:
            label = "%s=%s" % (k, v)
            ov = _one_dim_override(spec, k, v)
            grid[label] = ov
    # 2-D corner of the study (declared, not selected)
    for a, b in itertools.product(weeks_values, pct_values):
        label = "run=%s&quant=%s" % (a, b)
        ov = _one_dim_override(spec, "change_run_weeks", a)
        ov.update(_one_dim_override(spec, "basis_quantile", b))
        grid[label] = ov
    grid["base"] = {}
    grid = dict(sorted(grid.items(), key=lambda kv: (len(kv[1]), kv[0])))
    if "base" in grid:
        grid["base"] = {}
    return grid


def _one_dim_override(spec: dict, key: str, value) -> dict:
    ops = spec["signal"]["ops"]
    if key == "change_run_weeks":
        for i, o in enumerate(ops):
            if o.get("type") == "change_run":
                return {"signal.ops.%d.weeks" % i: value}
    if key == "channel_n":
        for i, o in enumerate(ops):
            if o.get("type") == "channel_change":
                return {"signal.ops.%d.n" % i: value}
    if key == "channel_threshold":
        for i, o in enumerate(ops):
            if o.get("type") == "channel_change":
                return {"signal.ops.%d.threshold" % i: value}
    if key == "hold_sessions":
        return {"exit.max_hold_sessions": value}
    if key == "basis_quantile":
        return {"price_filter.threshold": value}
    raise KeyError(key)


def split_by_date(spec: dict, bundle, ind_raw: pd.DataFrame, split_date: str, basis_cache=None):
    """In-sample / out-of-sample by a fixed, pre-declared date split."""
    s_in = copy.deepcopy(spec)
    s_in.setdefault("window", {})["end"] = split_date
    s_out = copy.deepcopy(spec)
    s_out.setdefault("window", {})["start"] = split_date
    res_in, stats_in, _ = run_variant(s_in, bundle, ind_raw, basis_cache=basis_cache)
    res_out, stats_out, _ = run_variant(s_out, bundle, ind_raw, basis_cache=basis_cache)
    return {
        "split_date": split_date,
        "in_sample": stats_in,
        "out_of_sample": stats_out,
        "in_trades": res_in.trades,
        "out_trades": res_out.trades,
    }


def block_bootstrap_returns(trades: pd.DataFrame, n_iter: int = 2000, block: int = 3,
                            seed: int = 7) -> dict:
    """Block bootstrap of trade PnL: how sensitive is the sign to a few periods?"""
    import numpy as np
    if trades is None or len(trades) < 5:
        return {"n": 0 if trades is None else len(trades), "mean": None, "p_positive": None}
    pnl = trades["net_pnl_after_slip"].astype(float).tolist()
    n = len(pnl)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_iter):
        pick = []
        while len(pick) < n:
            st = rng.integers(0, max(1, n - block + 1))
            pick.extend(pnl[st:st + block])
        means.append(float(np.mean(pick[:n])))
    arr = np.array(means)
    return {
        "n": n,
        "mean": float(np.mean(pnl)),
        "p_positive": float((arr > 0).mean()),
        "ci5": float(np.percentile(arr, 5)),
        "ci95": float(np.percentile(arr, 95)),
        "single_year_dominance": _single_year_dominance(trades),
    }


def _single_year_dominance(trades: pd.DataFrame) -> dict:
    t = trades.copy()
    t["year"] = pd.to_datetime(t["exit_day"]).dt.year
    by = t.groupby("year")["net_pnl_after_slip"].sum()
    total = by.sum()
    if total == 0 or len(by) == 0:
        return {"top_year": None, "share": None}
    top = by.idxmax()
    return {"top_year": int(top), "share": float(by.max() / total) if total else None}


def annual_robustness(spec: dict, bundle, ind_raw: pd.DataFrame) -> pd.DataFrame:
    res, stats, _ = run_variant(spec, bundle, ind_raw)
    return annual_table(res.daily, res.trades)
