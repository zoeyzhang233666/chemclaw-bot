# -*- coding: utf-8 -*-
"""Event-driven backtest engine.

Session loop (one iteration per trading session, chronological):

 1. mark-to-market  : settle the existing position on the session's price for its contract
 2. exits           : scheduled exit (holding counter / stop / take-profit) -> trade at the
                      configured price of THIS session
 3. rolls           : if the session is a roll session, close on the old contract and reopen
                      on the new one within the same session
 4. signals         : signals whose availability_session == this session become actionable
 5. entries         : open at the configured price of THIS session (open or close), never at
                      a price observed before the decision
 6. cash/margin     : update equity, record the daily log

Costs are charged exactly once per contract leg per side:
  commission = max(min_per_lot, fee) * lots
  slippage   = slippage_ticks * tick_size * lot_size * lots   (market orders only)
Rolls therefore cost two legs, which is visible in every trade record.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .contracts import build_roll_schedule, price_at


class BacktestResult:
    def __init__(self, daily: pd.DataFrame, trades: pd.DataFrame, rolls: pd.DataFrame,
                 diagnostics: dict):
        self.daily = daily
        self.trades = trades
        self.rolls = rolls
        self.diagnostics = diagnostics

    def to_dict(self) -> dict:
        return {"daily": self.daily, "trades": self.trades, "rolls": self.rolls,
                "diagnostics": self.diagnostics}


def _commission(spec_costs: dict, price: float, lots: float) -> float:
    if spec_costs.get("fee_mode") == "per_lot":
        per = float(spec_costs.get("fee_value", 0))
    else:
        per = float(spec_costs.get("fee_value", 0)) * price * float(spec_costs["multiplier"])
    per = max(per, float(spec_costs.get("commission_min_per_lot", 0) or 0))
    return per * lots


def _slippage(spec_costs: dict, lots: float, market_order: bool = True) -> float:
    if not market_order:
        return 0.0
    return (float(spec_costs.get("slippage_ticks", 0)) * float(spec_costs["tick_size"])
            * float(spec_costs["multiplier"]) * lots)


def _exec_price(contracts: pd.DataFrame, contract: str, day: pd.Timestamp, when: str,
                direction: int, spec_costs: dict) -> float | None:
    """direction +1 buy, -1 sell. Applies half-spread via slippage ticks for market fills."""
    price = price_at(contracts, contract, day, when)
    if price is None:
        return None
    slip = float(spec_costs.get("slippage_ticks", 0)) * float(spec_costs["tick_size"])
    return price + direction * slip / 2.0


def precompute_basis(spec: dict, bundle, sched: pd.DataFrame, lookback: int,
                     sessions: list) -> pd.DataFrame:
    """Trailing basis percentile for EVERY session, computed once and cached.

    For each session d:
        basis(d)   = spot(prev session of d) - fut(d, settled on the contract held at d)
        pctile(d)  = share of the previous `lookback` sessions whose basis <= basis(d)
    The historical window ends STRICTLY before d, so no same-session or future data leaks.
    """
    contracts = bundle.contracts
    cal = bundle.calendar
    spot = bundle.spot
    pf = spec["price_filter"]
    base_map = pf.get("basis_mapping", "spot_minus_fut")
    if spot is None:
        return pd.DataFrame({"date": sessions, "basis": np.nan, "pctile": np.nan,
                             "n_hist": 0})

    mtm_field = "settle" if (contracts["settle"].notna().mean() > 0.9) else "close"
    spot_map = dict(zip(spot["date"], spot["spot_east_cn"].astype(float)))
    prev_of = dict(zip(cal["date"], cal["prev_date"]))
    contract_of = dict(zip(sched["date"], sched["trade_contract"]))
    # fast price lookup
    px_map = {}
    for c, d, v in zip(contracts["contract"], contracts["date"], contracts[mtm_field]):
        px_map[(c, d)] = v

    rows = []
    for d in sessions:
        sday = prev_of.get(d)
        c = contract_of.get(d)
        sp = spot_map.get(sday) if sday is not None else None
        fu = px_map.get((c, d)) if (c is not None and not pd.isna(c)) else None
        if sp is None or fu is None or pd.isna(sp) or pd.isna(fu):
            rows.append((d, np.nan))
            continue
        rows.append((d, sp - fu if base_map == "spot_minus_fut" else fu - sp))
    basis = pd.DataFrame(rows, columns=["date", "basis"])
    vals = basis["basis"].tolist()
    n_total = len(vals)
    pct, hn = [], []
    for i in range(n_total):
        cur = vals[i]
        lo = max(0, i - lookback)
        hist = [v for v in vals[lo:i] if v is not None and not (isinstance(v, float) and np.isnan(v))]
        hn.append(len(hist))
        if cur is None or (isinstance(cur, float) and np.isnan(cur)) or len(hist) < 20:
            pct.append(np.nan)
        else:
            arr = np.asarray(hist, dtype=float)
            pct.append(float((arr <= cur).mean()))
    basis["pctile"] = pct
    basis["n_hist"] = hn
    return basis


def run_backtest(spec: dict, bundle, indicator: pd.DataFrame,
                 basis_cache: pd.DataFrame | None = None) -> BacktestResult:
    cal = bundle.calendar
    contracts = bundle.contracts
    spot = bundle.spot
    costs = spec["costs"]
    timing = spec["timing"]
    entry_cfg = spec["entry"]
    exit_cfg = spec["exit"]
    pos_cfg = spec["position"]
    pf = spec["price_filter"]

    lot = float(costs["multiplier"])
    tick = float(costs["tick_size"])
    margin_rate = float(costs["margin_rate"])
    price_field = timing.get("prices", "open")
    if price_field not in ("open", "close", "settle"):
        price_field = "open"
    mtm_field = "settle" if (contracts["settle"].notna().mean() > 0.9) else "close"

    sched = build_roll_schedule(
        contracts, cal,
        selection=spec["contract"]["selection"], k=int(spec["contract"].get("k", 1)),
        roll_rule=spec["contract"]["roll_rule"],
        no_trade_window_days=int(spec["contract"].get("no_trade_window_days_before_delivery", 0)),
        fixed_contract=spec["contract"].get("fixed_contract"),
    )
    sched_idx = sched.set_index("date")

    # ---- scheduled signals: one per availability session (first event wins per session)
    events = indicator.dropna(subset=["availability_session"])
    events = events[events.get("event", pd.Series(True, index=events.index)).astype(bool)]
    event_by_session: dict[pd.Timestamp, list[pd.Series]] = {}
    for _, r in events.iterrows():
        event_by_session.setdefault(pd.Timestamp(r["availability_session"]), []).append(r)

    start = pd.Timestamp(spec.get("window", {}).get("start") or cal["date"].min())
    end = pd.Timestamp(spec.get("window", {}).get("end") or cal["date"].max())
    sessions = [d for d in cal["date"] if start <= d <= end]

    # ---- basis percentile comes from the precomputed trailing-window table
    spot_by_date = {}
    if spot is not None:
        spot_by_date = dict(zip(spot["date"], spot["spot_east_cn"]))
    if basis_cache is None:
        basis_cache = precompute_basis(spec, bundle, sched, int(pf.get("lookback_points", 756)),
                                       list(cal["date"]))
    b_idx = basis_cache.set_index("date")
    _b_basis = b_idx["basis"].to_dict()
    _b_pct = b_idx["pctile"].to_dict()
    _b_n = b_idx["n_hist"].to_dict()

    def basis_percentile(avail_day: pd.Timestamp, lookback: int):
        return (_b_basis.get(avail_day, np.nan), _b_pct.get(avail_day, np.nan),
                _b_n.get(avail_day, 0))

    # ---- state
    cash = float(pos_cfg["capital"])
    equity0 = cash
    position = None          # dict(contract, direction, lots, entry_px, entry_day, bars_held, sig)
    daily_rows = []
    trade_rows = []
    roll_rows = []
    trade_id = 0
    blocked = {"no_contract": 0, "no_price": 0, "insufficient_margin": 0,
               "limit_reject": 0, "filter_fail": 0, "holding": 0}
    entry_sessions = set()

    def current_margin(p: dict, px: float) -> float:
        return margin_rate * px * lot * p["lots"]

    for i, day in enumerate(sessions):
        sched_row = sched_idx.loc[day] if day in sched_idx.index else None
        contract = None if sched_row is None else sched_row["trade_contract"]

        # 2) exits scheduled for today (mark at today's price)
        if position is not None:
            position["bars_held"] += 1
            px_today = price_at(contracts, position["contract"], day, mtm_field)
            if px_today is None:
                px_today = price_at(contracts, position["contract"], day, "close")
            if px_today is not None:
                ret = (px_today / position["entry_px"] - 1.0) * position["direction"]
                tp = exit_cfg.get("take_profit_pct")
                sl = exit_cfg.get("stop_loss_pct")
                reason = None
                if exit_cfg["exit_on_roll_when_contract_changes"] and sched_row is not None and \
                        sched_row["roll_flag"] and sched_row["roll_from"] == position["contract"]:
                    reason = "roll"
                elif position["bars_held"] >= int(exit_cfg["max_hold_sessions"]):
                    reason = "max_hold"
                elif tp is not None and ret >= float(tp):
                    reason = "take_profit"
                elif sl is not None and ret <= -float(sl):
                    reason = "stop_loss"
                if reason:
                    exec_day = day
                    px = _exec_price(contracts, position["contract"], exec_day, price_field,
                                     -position["direction"], costs)
                    if px is None:
                        px = _exec_price(contracts, position["contract"], exec_day, "close",
                                         -position["direction"], costs)
                    if px is not None:
                        gross = (px - position["entry_px"]) * position["direction"] * lot * position["lots"]
                        fee = _commission(costs, px, position["lots"])
                        slip = _slippage(costs, position["lots"])
                        cash += gross - fee
                        trade = dict(position)
                        trade.update({
                            "trade_id": position["trade_id"],
                            "exit_day": exec_day, "exit_contract": position["contract"],
                            "exit_px": px, "exit_reason": reason,
                            "gross_pnl": gross, "fees": position["entry_fee"] + fee,
                            "slippage_cost": position["entry_slip"] + slip,
                            "net_pnl": gross - position["entry_fee"] - fee,
                            "bars_held": position["bars_held"],
                            "ret_on_price": (px / position["entry_px"] - 1.0) * position["direction"],
                        })
                        trade["net_pnl_after_slip"] = trade["net_pnl"] - trade["slippage_cost"]
                        trade_rows.append(trade)
                        position = None

        # 3) rolls: if a position is still on the old contract, move it today
        if position is not None and sched_row is not None and sched_row["roll_flag"] \
                and sched_row["roll_from"] == position["contract"] and contract is not None:
            old = position["contract"]
            px_out = _exec_price(contracts, old, day, price_field, -position["direction"], costs)
            px_in = _exec_price(contracts, contract, day, price_field, position["direction"], costs)
            if px_out is not None and px_in is not None:
                gross = (px_out - position["entry_px"]) * position["direction"] * lot * position["lots"]
                fee_out = _commission(costs, px_out, position["lots"])
                fee_in = _commission(costs, px_in, position["lots"])
                slip = _slippage(costs, position["lots"]) * 2
                cash += gross - fee_out
                roll_rows.append({
                    "date": day, "trade_id": position["trade_id"], "from": old, "to": contract,
                    "dir": position["direction"], "lots": position["lots"],
                    "px_out": px_out, "px_in": px_in,
                    "leg_gross": gross, "fees": fee_out + fee_in,
                    "spread_cost": (px_in - px_out) * position["direction"] * lot * position["lots"],
                })
                position.update({
                    "contract": contract, "entry_px": px_in,
                    "entry_fee": position["entry_fee"] + fee_out + fee_in,
                    "entry_slip": position["entry_slip"] + slip,
                    "realised_gross": position.get("realised_gross", 0.0) + gross,
                    "rolls": int(position.get("rolls", 0)) + 1,
                })

        # 4) signals actionable today
        todays = event_by_session.get(day, [])
        pending_entry = None
        if todays:
            # newest published observation wins; record the signal provenance
            sig = max(todays, key=lambda r: r["asof_date"])
            direction = 1 if spec["universe"]["direction_mode"] == "long" else \
                (-1 if spec["universe"]["direction_mode"] == "short" else 1)
            ok_filter = True
            basis_cur = pct = np.nan
            n_hist = 0
            if pf.get("enabled"):
                basis_cur, pct, n_hist = basis_percentile(day, int(pf["lookback_points"]))
                if np.isnan(pct) or n_hist < 20:
                    ok_filter = False
                elif pf["side"] == "above":
                    ok_filter = pct >= float(pf["threshold"])
                else:
                    ok_filter = pct <= float(pf["threshold"])
            if position is not None:
                blocked["holding"] += 1
                if entry_cfg.get("reentry_while_holding") == "restart_holding":
                    position["bars_held"] = 0
            elif not ok_filter:
                blocked["filter_fail"] += 1
            else:
                pending_entry = (sig, direction, basis_cur, pct, n_hist)

        # 5) entry
        if pending_entry is not None and contract is not None and day not in entry_sessions:
            sig, direction, basis_cur, pct, n_hist = pending_entry
            px = _exec_price(contracts, contract, day, price_field, direction, costs)
            if px is None:
                blocked["no_price"] += 1
            else:
                sizing = pos_cfg.get("sizing", "fixed_lots")
                if sizing == "fixed_lots":
                    lots = float(pos_cfg["lots"])
                elif sizing == "pct_equity_notional":
                    lots = max(1.0, float(pos_cfg["target_pct_equity"]) * cash / (px * lot))
                else:  # pct_equity_margin
                    lots = max(1.0, float(pos_cfg["target_pct_equity"]) * cash / (px * lot * margin_rate))
                lots = float(int(np.floor(lots)))
                max_lots = float(pos_cfg.get("max_lots")) if pos_cfg.get("max_lots") else lots
                lots = min(lots, max_lots)
                need_margin = margin_rate * px * lot * lots
                if need_margin > cash:
                    lots = float(int(np.floor(cash / (margin_rate * px * lot))))
                if lots < 1:
                    blocked["insufficient_margin"] += 1
                else:
                    trade_id += 1
                    fee = _commission(costs, px, lots)
                    slip = _slippage(costs, lots)
                    cash -= fee
                    entry_sessions.add(day)
                    position = {
                        "trade_id": trade_id,
                        "contract": contract, "direction": direction, "lots": lots,
                        "entry_px": px, "entry_day": day, "entry_fee": fee,
                        "entry_slip": slip, "bars_held": 0, "rolls": 0,
                        "sig_asof": sig["asof_date"],
                        "sig_publish": sig.get("publish_used"),
                        "sig_avail": sig["availability_session"],
                        "sig_value": float(sig["value"]),
                        "sig_run_len": int(sig.get("run_len", 0) or 0),
                        "sig_dd": None,
                        "basis_cur": basis_cur, "basis_pctile": pct, "basis_hist_n": n_hist,
                        "target_lots": lots,
                    }
                    for key in sig.index:
                        if key.startswith("dd_"):
                            position["sig_dd"] = float(sig[key]) if pd.notna(sig[key]) else None
                            position["sig_dd_window"] = int(key.split("_")[1])

        # 6) mark to market + records
        equity = cash
        pos_mv = 0.0
        margin_used = 0.0
        pos_px = None
        if position is not None:
            pos_px = price_at(contracts, position["contract"], day, mtm_field)
            if pos_px is None:
                pos_px = price_at(contracts, position["contract"], day, "close")
            if pos_px is None:
                pos_px = position["entry_px"]
            unreal = (pos_px - position["entry_px"]) * position["direction"] * lot * position["lots"]
            pos_mv = unreal
            margin_used = margin_rate * pos_px * lot * position["lots"]
        equity = cash + pos_mv
        daily_rows.append({
            "date": day,
            "cash": cash, "unrealised": pos_mv, "equity": equity,
            "margin_used": margin_used,
            "margin_util": margin_used / equity if equity > 0 else np.nan,
            "contract": None if position is None else position["contract"],
            "direction": 0 if position is None else position["direction"],
            "lots": 0 if position is None else position["lots"],
            "mark_price": pos_px,
            "trade_id": None if position is None else position["trade_id"],
            "trade_action": "entry" if (position is not None and position["bars_held"] == 0
                                        and pending_entry is not None and day in entry_sessions
                                        and position["entry_day"] == day) else "",
            "roll_flag": bool(sched_row["roll_flag"]) if sched_row is not None else False,
        })

    daily = pd.DataFrame(daily_rows)
    trades = pd.DataFrame(trade_rows)
    rolls = pd.DataFrame(roll_rows)
    diagnostics = {
        "sessions": len(sessions),
        "events_available": int(events.shape[0] if len(events) else 0),
        "blocked": blocked,
        "price_field": price_field,
        "mtm_field": mtm_field,
        "equity0": equity0,
    }
    return BacktestResult(daily=daily, trades=trades, rolls=rolls, diagnostics=diagnostics)
