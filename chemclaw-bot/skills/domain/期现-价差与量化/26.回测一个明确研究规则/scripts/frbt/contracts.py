# -*- coding: utf-8 -*-
"""Map every trading session to a specific, actually tradable contract.

Never back-adjusted: the roll is explicit. Each session carries
  `trade_contract`  the contract to hold at that session
  `roll_flag`       True when this session is the first session on a new contract
  `roll_from`       previous contract (for audit)
  `next_contract`   contract used for the next session (so the engine can pre-plan exits)

Roll rules
  open_interest_kth : at the previous close, rank listed contracts by open interest and
                      take the k-th largest that is still outside the no-trade window
                      (and has a live quote on both sessions). This is a liquidity roll,
                      the same logic as a dealer's active-contract switch.
  delivery_month_lead : roll at the start of the session series that first has a next
                      listed contract within `roll_lead_days` of the current delivery.
  none              : never roll (only valid for short windows).
"""
from __future__ import annotations

import pandas as pd


def _state(delivery_month: str):
    return pd.Period(delivery_month, freq="M")


def norm_month(m: str) -> str:
    """'24-05' / '2024-05' / '2405' -> '2024-05'."""
    s = str(m).strip()
    if "-" in s:
        yy, mm = s.split("-")[:2]
    elif len(s) == 4 and s.isdigit():
        yy, mm = s[:2], s[2:]
    else:
        return s
    if len(yy) == 2:
        yy = "20" + yy
    return yy + "-" + str(mm).zfill(2)


def build_month_lookup(con: pd.DataFrame) -> dict:
    """contract -> delivery month, using the raw delivery_month column before grouping."""
    lookup = {}
    if "delivery_month" in con.columns and "contract" in con.columns:
        for c, m in zip(con["contract"], con["delivery_month"]):
            try:
                lookup.setdefault(c, norm_month(m))
            except Exception:  # noqa: BLE001
                continue
    return lookup


def build_roll_schedule(contracts: pd.DataFrame, calendar: pd.DataFrame, *, selection: str,
                        k: int = 1, roll_rule: str = "open_interest_kth",
                        no_trade_window_days: int = 5, fixed_contract: str | None = None,
                        min_oi: float = 0.0) -> pd.DataFrame:
    """Return one row per session with the tradable contract and roll bookkeeping."""
    cal = calendar.sort_values("date").reset_index(drop=True)
    sessions = list(cal["date"])
    con = contracts.copy()
    con["date"] = pd.to_datetime(con["date"]).dt.normalize()
    month_of = build_month_lookup(con)
    con["delivery_month"] = con["delivery_month"].map(norm_month)
    # delivery month end is a conservative approximation of the contract's last day
    con["last_delivery_est"] = con["delivery_month"].map(
        lambda m: pd.Period(m, freq="M").end_time.normalize())
    by_date = {d: g for d, g in con.groupby("date")}

    def eligible(day: pd.Timestamp, contract: str) -> bool:
        g = by_date.get(day)
        if g is None:
            return False
        row = g[g["contract"] == contract]
        return bool(len(row))

    def pick(day: pd.Timestamp, reference_date: pd.Timestamp) -> str | None:
        if selection == "fixed_contract":
            return fixed_contract
        g = by_date.get(day)
        if g is None:
            return None
        g = g[g["open_interest"] >= min_oi]
        if g.empty:
            return None
        # no-trade window measured from the quote date to the end of the delivery month
        def in_window(m: str) -> bool:
            end = pd.Period(m, freq="M").end_time.normalize()
            return (end - day).days <= no_trade_window_days

        g = g[~g["delivery_month"].map(in_window)]
        if g.empty:
            return None
        g = g.sort_values(["open_interest", "volume"], ascending=False)
        if roll_rule == "delivery_month_lead":
            # liquid months stay liquid far ahead: prefer the nearest delivery among top-N
            g = g.sort_values("delivery_month")
        ranked = g.drop_duplicates("contract")["contract"].tolist()
        if selection == "front_month" or roll_rule == "delivery_month_lead":
            return ranked[0]
        if selection == "kth_by_open_interest":
            return ranked[min(k, len(ranked)) - 1]
        return ranked[0]

    rows = []
    current = None

    con = contracts.copy()
    con["date"] = pd.to_datetime(con["date"]).dt.normalize()
    month_of = build_month_lookup(con)

    def tradeable(day: pd.Timestamp, contract: str) -> bool:
        """Listed, quoted, and still outside the delivery no-trade window on `day`."""
        if contract is None or not eligible(day, contract):
            return False
        m = month_of.get(contract)
        if m is None:
            return False
        end = pd.Period(m, freq="M").end_time.normalize()
        return (end - day).days > no_trade_window_days

    for i, day in enumerate(sessions):
        prev = sessions[i - 1] if i > 0 else None
        # decision uses information available at the previous close
        decision_day = prev if prev is not None else day
        target = pick(decision_day, decision_day)
        # a carried contract is only allowed if it is still tradable TODAY: the no-trade
        # window is a calendar condition, so it can close a carried position mid-hold
        if target is None and current is not None and tradeable(day, current):
            target = current
        if target is not None and not tradeable(day, target):
            fallback = pick(day, day)
            target = fallback if (fallback is not None and tradeable(day, fallback)) else None
        roll = current is not None and target is not None and target != current
        rows.append({
            "date": day,
            "trade_contract": target,
            "roll_flag": bool(roll),
            "roll_from": current if roll else None,
        })
        current = target if target is not None else None
    sched = pd.DataFrame(rows)
    sched["next_contract"] = sched["trade_contract"].shift(-1)
    sched["next_date"] = sched["date"].shift(-1)
    return sched


def contract_series(contracts: pd.DataFrame, contract: str) -> pd.DataFrame:
    g = contracts[contracts["contract"] == contract].sort_values("date")
    return g.set_index("date")


def price_at(contracts: pd.DataFrame, contract: str, day: pd.Timestamp, field: str) -> float | None:
    g = contracts[(contracts["contract"] == contract) & (contracts["date"] == day)]
    if g.empty:
        return None
    v = g.iloc[0][field]
    return None if pd.isna(v) else float(v)
