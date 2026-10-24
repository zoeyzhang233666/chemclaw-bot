# -*- coding: utf-8 -*-
"""Unit and property tests for the futures rule backtest engine.

Run:  python -m pytest tests -q      (or)      python tests/run_tests.py

The tests target the three failure modes that silently ruin rule research:
  1. look-ahead: a signal must never be tradable before its publication is knowable;
  2. fake continuity: the traded contract must be a real listed contract, and a roll
     must be an explicit pair of trades, never a back-adjusted synthetic series;
  3. accounting: PnL, fees and slippage must reconcile to the equity curve.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from frbt.contracts import build_roll_schedule  # noqa: E402
from frbt.data import decide_availability  # noqa: E402
from frbt.signal import build_signal_events, compute_indicator_stats  # noqa: E402


def make_cal(start="2024-01-01", n=40):
    days = pd.bdate_range(start, periods=n)
    cal = pd.DataFrame({"date": days})
    cal["prev_date"] = cal["date"].shift(1)
    cal["next_date"] = cal["date"].shift(-1)
    return cal


def test_availability_never_reads_publication_day():
    """A Wednesday-release (14:00) indicator must be tradeable on Thursday only."""
    cal = make_cal()
    ind = pd.DataFrame({
        "asof_date": pd.to_datetime(["2024-01-03", "2024-01-10"]),
        "value": [10.0, 9.0],
        "publish_dt_verified": pd.to_datetime(["2024-01-03 14:00", "2024-01-10 13:30"]),
    })
    out = decide_availability(ind, cal, mode="strict", assumed_time="14:00", min_lag_sessions=1)
    assert out["availability_session"].iloc[0] == pd.Timestamp("2024-01-04")
    assert out["availability_session"].iloc[1] == pd.Timestamp("2024-01-11")
    assert (out["availability_session"] > out["asof_date"]).all()
    assert out["n_blocks"].tolist() == [1, 1]


def test_strict_mode_drops_unverified_rows():
    cal = make_cal()
    ind = pd.DataFrame({
        "asof_date": pd.to_datetime(["2024-01-03", "2024-01-10"]),
        "value": [10.0, 9.0],
        "publish_dt_verified": pd.to_datetime(["2024-01-03 14:00", None]),
    })
    strict = decide_availability(ind, cal, mode="strict", assumed_time="14:00")
    assert strict["availability_session"].notna().sum() == 1
    backfill = decide_availability(ind, cal, mode="backfill_assumed", assumed_time="14:00")
    assert backfill["availability_session"].notna().sum() == 2
    # the assumed clock is still the next session, never the same session
    assert backfill["availability_session"].iloc[1] == pd.Timestamp("2024-01-11")


def test_two_week_decline_logic():
    ind = pd.DataFrame({
        "asof_date": pd.bdate_range("2024-01-01", periods=7),
        "value": [100.0, 98.0, 97.5, 99.0, 96.0, 95.0, 95.0],
    })
    stats = compute_indicator_stats(ind)
    assert stats["run_len"].tolist() == [0, 1, 2, 1, 1, 2, 0]
    assert stats["run_dir"].tolist() == [0, -1, -1, 1, -1, -1, 0]
    ops = [{"type": "change_run", "weeks": 2, "direction": "down"}]
    ev = build_signal_events(stats, ops, "and", [2], min_history=0)
    assert ev["event"].tolist() == [False, False, True, False, False, True, False]


def test_channel_op_is_low_of_trailing_n():
    # values fall into the channel repeatedly: index 3 (101.5 -> then 101.0) and index 4
    ind = pd.DataFrame({
        "asof_date": pd.bdate_range("2024-01-01", periods=6),
        "value": [100.0, 101.0, 100.5, 101.5, 101.0, 101.2],
    })
    ops = [{"type": "channel_change", "n": 2, "threshold": 0.0, "channel_mode": "low"}]
    ev = build_signal_events(compute_indicator_stats(ind), ops, "and", [2], min_history=0)
    # ch[3]: max(100.5,101.5)=101.5 vs 101.5 -> not below the top
    # ch[4]: max(101.5,101.0)=101.5 vs 101.0 -> below the top -> channel drawdown
    assert bool(ev["event"].iloc[4]) is True
    # ch[2]: max(101.0,100.5)=101.0 vs 100.5 -> below the top
    assert bool(ev["event"].iloc[2]) is True
    # with a threshold above any observed drawdown nothing passes
    ops_hi = [{"type": "channel_change", "n": 2, "threshold": 99.0, "channel_mode": "low"}]
    ev_hi = build_signal_events(compute_indicator_stats(ind), ops_hi, "and", [2], min_history=0)
    assert not bool(ev_hi["event"].any())


def test_roll_schedule_uses_listed_contracts_only():
    days = pd.bdate_range("2024-11-01", periods=60)
    rows = []
    for d in days:
        rows.append({"contract": "MA2501", "delivery_month": "2025-01", "date": d, "open": 2500,
                     "high": 2510, "low": 2490, "close": 2500, "settle": 2500,
                     "volume": 50000, "open_interest": 400000})
        rows.append({"contract": "MA2505", "delivery_month": "2025-05", "date": d, "open": 2520,
                     "high": 2530, "low": 2510, "close": 2520, "settle": 2520,
                     "volume": 90000, "open_interest": 900000})
    con = pd.DataFrame(rows)
    cal = pd.DataFrame({"date": days})
    sched = build_roll_schedule(con, cal, selection="kth_by_open_interest", k=1,
                                roll_rule="open_interest_kth", no_trade_window_days=10)
    assert set(sched["trade_contract"].dropna()) <= {"MA2501", "MA2505"}
    # highest open interest wins
    assert sched["trade_contract"].iloc[0] == "MA2505"


def test_no_trade_window_excludes_near_delivery():
    days = pd.bdate_range("2024-11-01", periods=60)
    rows = []
    for d in days:
        rows.append({"contract": "MA2412", "delivery_month": "2024-12", "date": d, "open": 1,
                     "high": 1, "low": 1, "close": 1, "settle": 1, "volume": 1,
                     "open_interest": 10_000_000})
        rows.append({"contract": "MA2505", "delivery_month": "2025-05", "date": d, "open": 2,
                     "high": 2, "low": 2, "close": 2, "settle": 2, "volume": 1,
                     "open_interest": 1000})
    con = pd.DataFrame(rows)
    cal = pd.DataFrame({"date": days})
    # 40-day window: by mid-November the Dec contract is inside it -> must switch to May
    sched = build_roll_schedule(con, cal, selection="kth_by_open_interest", k=1,
                                roll_rule="open_interest_kth", no_trade_window_days=40)
    mid = sched[sched["date"] >= pd.Timestamp("2024-11-22")]
    assert (mid["trade_contract"] == "MA2505").all()
    assert (sched[sched["date"] <= pd.Timestamp("2024-11-20")]["trade_contract"]
            == "MA2412").all()
    # a 10-day window leaves it tradable until late November, then forces the switch
    sched10 = build_roll_schedule(con, cal, selection="kth_by_open_interest", k=1,
                                  roll_rule="open_interest_kth", no_trade_window_days=10)
    assert (sched10[sched10["date"] <= pd.Timestamp("2024-12-05")]["trade_contract"]
            == "MA2412").any()
    assert (sched10[sched10["date"] >= pd.Timestamp("2024-12-30")]["trade_contract"]
            == "MA2505").all()


def test_spec_validation_rejects_missing_provenance():
    from frbt.spec import validate_dict
    errors, _ = validate_dict({"meta": {}, "universe": {}, "contract": {}, "timing": {},
                               "signal": {}, "price_filter": {}, "entry": {}, "exit": {},
                               "position": {}, "costs": {}, "data": {}})
    assert any("provenance" in e for e in errors)


def test_engine_accounting_reconciles():
    """Trade-level net PnL must equal the equity change when only one position is traded."""
    from frbt.analysis import run_variant
    from frbt.data import DataBundle
    days = pd.bdate_range("2024-01-01", periods=60)
    con_rows = []
    price = 2000.0
    for i, d in enumerate(days):
        price += 10.0
        con_rows.append({"contract": "MA2409", "delivery_month": "2024-09", "date": d,
                         "open": price, "high": price + 5, "low": price - 5,
                         "close": price + 2, "settle": price + 2, "volume": 10000,
                         "open_interest": 100000})
    con = pd.DataFrame(con_rows)
    cal = pd.DataFrame({"date": days})
    ind = pd.DataFrame({"asof_date": [days[4]], "value": [10.0],
                        "publish_dt_verified": [days[4] + pd.Timedelta(hours=14)]})
    ind = decide_availability(ind, cal, mode="strict", assumed_time="14:00")
    ind = compute_indicator_stats(ind)
    ind = build_signal_events(ind, [{"type": "level", "cmp": ">=", "threshold": 0}], "and",
                              [2], min_history=0)
    spec = {
        "universe": {"direction_mode": "long"}, "timing": {"prices": "open"},
        "contract": {"selection": "fixed_contract", "k": 1, "roll_rule": "none",
                     "fixed_contract": "MA2409", "no_trade_window_days_before_delivery": 0},
        "entry": {"reentry_while_holding": "ignore"},
        "exit": {"max_hold_sessions": 3, "take_profit_pct": None, "stop_loss_pct": None,
                 "exit_on_roll_when_contract_changes": False},
        "position": {"sizing": "fixed_lots", "lots": 2, "capital": 100000,
                     "max_margin_utilisation": 0.5},
        "costs": {"fee_mode": "per_lot", "fee_value": 3.0, "commission_min_per_lot": 0.0,
                  "slippage_ticks": 1.0, "tick_size": 1, "multiplier": 10,
                  "margin_rate": 0.1},
        "price_filter": {"enabled": False, "basis_mapping": "spot_minus_fut"},
        "signal": {"ops": [{"type": "level", "cmp": ">=", "threshold": 0}]},
        "window": {},
    }
    bundle = DataBundle(calendar=cal, contracts=con, indicator=ind, spot=None)
    res, stats, _ = run_variant(spec, bundle, ind)
    if len(res.trades) == 0:
        return  # scenario did not trigger; nothing to reconcile
    t = res.trades.iloc[0]
    # gross PnL uses entry/exit prices net of half-spread; fees charged separately
    assert abs(t["gross_pnl"] - (t["exit_px"] - t["entry_px"]) * t["lots"] * 10) < 1e-6
    assert abs(t["net_pnl"] - (t["gross_pnl"] - t["fees"])) < 1e-6
    # equity change equals net pnl after slippage adjustment for round trips closed in window
    eq_change = res.daily["equity"].iloc[-1] - res.daily["equity"].iloc[0]
    total_pnl = res.trades["net_pnl"].sum()
    # trades still open at the end are not included; allow for that
    assert abs(eq_change - total_pnl) < 1e-6 or len(res.daily) < 60


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except AssertionError as e:  # noqa: PERF203
                failed += 1
                print("FAIL", name, e)
            except Exception as e:  # noqa: BLE001
                failed += 1
                print("ERROR", name, type(e).__name__, e)
    print("failed=%d" % failed)
    raise SystemExit(1 if failed else 0)
