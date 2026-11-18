# -*- coding: utf-8 -*-
"""Command-line entry point.

    python run_backtest.py validate  --config configs/methanol_inventory_basis.json
    python run_backtest.py run       --config ... --out out/run
    python run_backtest.py sensitivity --config ... --out out/run
    python run_backtest.py oos       --config ... --out out/run
    python run_backtest.py analyze   --config ... --out out/run     (run + sensitivity + oos)

Every command writes machine-readable JSON/CSV into --out so the HTML/Excel deliverables
can be regenerated without re-running the engine.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from frbt.analysis import (block_bootstrap_returns, build_default_grid, make_basis_cache,  # noqa: E402
                           run_variant, sensitivity_grid, split_by_date)
from frbt.data import attach_previous_availability, decide_availability, load_bundle  # noqa: E402
from frbt.metrics import annual_table, drawdown_curve, monthly_table, performance  # noqa: E402
from frbt.signal import build_signal_events, compute_indicator_stats  # noqa: E402
from frbt.spec import SpecError, load_spec  # noqa: E402


def _resolve(path: str, base: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base, path))


def prepare(spec_path: str, mode_override: str | None = None, window: dict | None = None):
    spec = load_spec(spec_path)
    spec.require()
    base = os.path.dirname(os.path.abspath(spec_path))
    d = spec.raw["data"]
    mode = mode_override or d["publication_mode"]
    bundle = load_bundle(_resolve(d["indicator_file"], base),
                         _resolve(d["contracts_file"], base),
                         _resolve(d["calendar_file"], base) if d.get("calendar_file") else None,
                         _resolve(d["spot_file"], base) if d.get("spot_file") else None)
    ind = decide_availability(bundle.indicator, bundle.calendar, mode=mode,
                             assumed_time=d.get("assumed_publish_time"),
                             cutoff=spec.raw["timing"].get("signal_cutoff_same_day", "15:00"),
                             min_lag_sessions=int(spec.raw["timing"].get("indicator_lag_sessions_min", 1)),
                             same_day_release_price=spec.raw["timing"].get("same_day_release_price"))
    ind = attach_previous_availability(ind)
    ind = compute_indicator_stats(ind)
    # evaluate the rule ops once on the raw indicator history (availability comes later)
    sig_cfg = spec.raw["signal"]
    ops = sig_cfg["ops"]
    windows = [int(o.get("n", 2)) for o in ops if o.get("type") == "channel_change"] or [2]
    ind = build_signal_events(ind, ops, sig_cfg.get("combine", "and"), windows,
                              int(sig_cfg.get("min_history", 0)))
    raw = copy.deepcopy(spec.raw)
    if window:
        raw.setdefault("window", {}).update(window)
    raw["data"]["publication_mode_used"] = mode
    return raw, spec, bundle, ind


def do_validate(spec_path: str) -> int:
    spec = load_spec(spec_path)
    errors = spec.validate()
    if errors:
        print("INVALID: %d error(s)" % len(errors))
        for e in errors:
            print("  -", e)
        return 1
    print("VALID  fingerprint=%s" % spec.fingerprint())
    from frbt.spec import validate_dict
    _, warnings = validate_dict(spec.raw)
    for w in warnings:
        print("  warning:", w)
    return 0


def do_run(spec_path: str, out: str, mode: str | None = None) -> dict:
    os.makedirs(out, exist_ok=True)
    raw, spec, bundle, ind = prepare(spec_path, mode_override=mode)
    res, stats, used = run_variant(raw, bundle, ind)
    daily = res.daily.copy()
    if daily.empty:
        raise SystemExit("no sessions in the configured window")
    eq = daily["equity"].astype(float)
    daily["equity_peak"] = eq.cummax()
    daily["drawdown"] = eq / daily["equity_peak"] - 1.0
    daily["cum_dd"] = daily["drawdown"]
    daily["daily_return"] = eq.pct_change().fillna(0.0)
    ann = annual_table(res.daily, res.trades)
    mon = monthly_table(res.daily)
    trades = res.trades
    if len(trades):
        trades = trades.copy()
        trades["entry_day"] = pd.to_datetime(trades["entry_day"])
        trades["exit_day"] = pd.to_datetime(trades["exit_day"])
    payload = {
        "meta": used["meta"],
        "fingerprint": spec.fingerprint(),
        "digest": {
            "publication_mode": raw["data"].get("publication_mode_used"),
            "sessions": int(len(daily)),
            "first_session": str(daily["date"].min().date()),
            "last_session": str(daily["date"].max().date()),
            "weeks_usable": int(ind["availability_session"].notna().sum()),
            "weeks_total": int(len(ind)),
            "weeks_verified_publish": int(ind["pub_verified"].sum()),
            "events": int(ind["event"].sum()),
            "contracts_used": sorted(daily["contract"].dropna().unique().tolist()),
        },
        "stats": stats,
        "diagnostics": res.diagnostics,
        "annual": ann.to_dict("records"),
        "monthly": mon.to_dict("records"),
    }
    daily.to_csv(os.path.join(out, "daily_equity.csv"), index=False)
    ind.to_csv(os.path.join(out, "signal_alignment.csv"), index=False)
    pd.DataFrame(res.rolls).to_csv(os.path.join(out, "rolls.csv"), index=False)
    trades.to_csv(os.path.join(out, "trades.csv"), index=False)
    with open(os.path.join(out, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({k: payload["stats"].get(k) for k in
                      ("trades", "total_return", "cagr", "max_dd", "sharpe", "win_rate",
                       "profit_factor", "exposure")}, indent=2, default=str))
    return payload


def do_sensitivity(spec_path: str, out: str, mode: str | None = None) -> dict:
    raw, spec, bundle, ind = prepare(spec_path, mode_override=mode)
    grid = build_default_grid(raw)
    g = sensitivity_grid(raw, bundle, ind, grid, base_label="base")
    os.makedirs(out, exist_ok=True)
    g.table.to_csv(os.path.join(out, "sensitivity.csv"), index=False)
    # cost sensitivity (cheap: reuses the cached basis table)
    from frbt.analysis import make_basis_cache
    cache = make_basis_cache(raw, bundle)
    cost_rows = []
    cs = raw["costs"].get("cost_sensitivity", {})
    for fm in cs.get("fee_multiple", [1]):
        for st in cs.get("slippage_ticks", [raw["costs"]["slippage_ticks"]]):
            ov = {"costs.fee_value": float(raw["costs"]["fee_value"]) * fm,
                  "costs.slippage_ticks": st}
            _, s2, _ = run_variant(raw, bundle, ind, ov, basis_cache=cache)
            cost_rows.append({"fee_multiple": fm, "fee_value": float(raw["costs"]["fee_value"]) * fm,
                              "slippage_ticks": st, **{k: s2.get(k) for k in
                                                       ("total_return", "cagr", "max_dd",
                                                        "sharpe", "trades", "net_pnl", "fees",
                                                        "slippage")}})
    cost_tab = pd.DataFrame(cost_rows)
    cost_tab.to_csv(os.path.join(out, "cost_sensitivity.csv"), index=False)
    payload = {"grid": g.table.to_dict("records"), "summary": g.summary,
               "base": g.base, "cost_sensitivity": cost_tab.to_dict("records")}
    with open(os.path.join(out, "sensitivity.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(g.summary, indent=2, default=str))
    return payload


def do_oos(spec_path: str, out: str, mode: str | None = None) -> dict:
    raw, spec, bundle, ind = prepare(spec_path, mode_override=mode)
    split = raw.get("analysis", {}).get("oos", {}).get("split_date")
    if not split:
        raise SystemExit("spec.analysis.oos.split_date missing")
    cache = make_basis_cache(raw, bundle)
    oos = split_by_date(raw, bundle, ind, split, basis_cache=cache)
    res_all, stats_all, _ = run_variant(raw, bundle, ind, basis_cache=cache)
    boot = block_bootstrap_returns(res_all.trades)
    # period removal test: drop the best year and recompute
    trades = res_all.trades.copy()
    remove = {}
    if len(trades):
        trades["year"] = pd.to_datetime(trades["exit_day"]).dt.year
        by = trades.groupby("year")["net_pnl_after_slip"].sum()
        for y in by.index:
            keep = trades[trades["year"] != y]
            remove[str(int(y))] = {"trades": int(len(keep)),
                                   "net_pnl_without_year": float(keep["net_pnl_after_slip"].sum())}
    payload = {
        "split_date": split,
        "in_sample": oos["in_sample"],
        "out_of_sample": oos["out_of_sample"],
        "bootstrap": boot,
        "annual_removal": remove,
        "full_sample": stats_all,
    }
    os.makedirs(out, exist_ok=True)
    oos["in_trades"].to_csv(os.path.join(out, "trades_in_sample.csv"), index=False)
    oos["out_trades"].to_csv(os.path.join(out, "trades_out_sample.csv"), index=False)
    with open(os.path.join(out, "oos.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({"split": split,
                      "is_trades": payload["in_sample"].get("trades"),
                      "is_return": payload["in_sample"].get("total_return"),
                      "oos_trades": payload["out_of_sample"].get("trades"),
                      "oos_return": payload["out_of_sample"].get("total_return"),
                      "bootstrap": boot}, indent=2, default=str))
    return payload


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="run_backtest")
    ap.add_argument("cmd", choices=["validate", "run", "sensitivity", "oos", "analyze"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--mode", default=None, choices=[None, "strict", "backfill_assumed"])
    args = ap.parse_args(argv)
    if args.cmd == "validate":
        return do_validate(args.config)
    if args.cmd == "run":
        do_run(args.config, args.out, args.mode)
    elif args.cmd == "sensitivity":
        do_sensitivity(args.config, args.out, args.mode)
    elif args.cmd == "oos":
        do_oos(args.config, args.out, args.mode)
    else:
        do_run(args.config, args.out, args.mode)
        do_sensitivity(args.config, args.out, args.mode)
        do_oos(args.config, args.out, args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
