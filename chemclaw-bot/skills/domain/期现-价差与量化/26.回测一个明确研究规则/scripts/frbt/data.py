# -*- coding: utf-8 -*-
"""Data loading and look-ahead-free alignment.

The single invariant of this module:

    availability_session = (first trading session AFTER the publication day)
                           + indicator_lag_sessions_min - 1

i.e. a weekly figure released on Wednesday (at any time of day, because release clocks
range from 13:00 to 18:00) becomes tradeable at the Thursday open unless the spec
declares that the release is known before that day's close AND that the engine may trade
it on the same session.

Nothing may be read at a session in which it was not yet knowable:
  * 2022-07 -> 2024-07 inventory rows were re-posted to the Mysteel mobile site in
    2024-07; using that re-post timestamp would shift every signal in that window by two
    years in the wrong direction. Such rows are `pub_verified = False`.
  * a daily spot quote dated D is assumed published after D's close, so a signal built
    from basis may be traded no earlier than D + 1 session (spot_availability=next_session).

Every week carries `availability_session` and `n_blocks` so a reviewer can audit the
alignment row by row (see the exported 05_signal_alignment sheet).
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

import pandas as pd

CUTOFF_DEFAULT = "15:00"             # exchange close
CUTOFF_SESSION_CLOSE_DATA = "15:15"  # daily quote publication assumed after settlement


@dataclass
class DataBundle:
    calendar: pd.DataFrame        # date, prev_date, next_date, dow
    contracts: pd.DataFrame       # contract, delivery_month, date, ohlc, settle, volume, oi
    indicator: pd.DataFrame       # asof_date, value, publish_dt(+assumed), pub_resolution
    spot: pd.DataFrame | None


def load_bundle(indicator_file: str, contracts_file: str, calendar_file: str | None,
                spot_file: str | None = None) -> DataBundle:
    ind = pd.read_csv(indicator_file, encoding="utf-8-sig")
    for c in ("asof_date", "publish_dt_verified", "publish_dt"):
        if c in ind.columns:
            ind[c] = pd.to_datetime(ind[c], errors="coerce")
    ind["asof_date"] = pd.to_datetime(ind["asof_date"]).dt.normalize()
    # the engine's canonical level column is `value`; accept common aliases
    for alias in ("value_wan_ton", "value_wan", "level", "reading"):
        if alias in ind.columns:
            ind["value"] = pd.to_numeric(ind[alias], errors="coerce")
            break
    if "value" not in ind.columns:
        raise ValueError("indicator file needs a level column (value / value_wan_ton / level)")
    ind = ind.sort_values("asof_date").reset_index(drop=True)

    con = pd.read_csv(contracts_file)
    con["date"] = pd.to_datetime(con["date"]).dt.normalize()
    con = con.sort_values(["date", "contract"]).reset_index(drop=True)

    if calendar_file:
        cal = pd.read_csv(calendar_file)
        cal["date"] = pd.to_datetime(cal["date"]).dt.normalize()
        for c in ("prev_date", "next_date"):
            if c in cal:
                cal[c] = pd.to_datetime(cal[c], errors="coerce")
        cal = cal.sort_values("date").reset_index(drop=True)
    else:
        cal = pd.DataFrame({"date": sorted(con["date"].unique())})
        cal["prev_date"] = cal["date"].shift(1)
        cal["next_date"] = cal["date"].shift(-1)

    spot = None
    if spot_file:
        spot = pd.read_csv(spot_file, encoding="utf-8-sig")
        spot["date"] = pd.to_datetime(spot["date"]).dt.normalize()
        spot = spot.sort_values("date").reset_index(drop=True)
    return DataBundle(calendar=cal, contracts=con, indicator=ind, spot=spot)


# --------------------------------------------------------------------------
# availability of a periodic indicator
# --------------------------------------------------------------------------
def decide_availability(ind: pd.DataFrame, cal: pd.DataFrame, *, mode: str,
                        assumed_time: str | None, cutoff: str = CUTOFF_DEFAULT,
                        min_lag_sessions: int = 1,
                        same_day_release_price: str | None = None) -> pd.DataFrame:
    """Attach publish_used / availability_session / n_blocks to the indicator frame.

    mode == "strict"           : only verified original publication timestamps are used.
                                 Rows without one are marked unavailable (NaT) and later
                                 dropped, so the sample is honest but shorter.
    mode == "backfill_assumed" : rows without a verified timestamp fall back to
                                 `assumed_time` on the as-of date; rows *with* a verified
                                 timestamp always use it (never the re-post date).
    """
    out = ind.copy()
    sessions = [pd.Timestamp(x) for x in cal["date"].tolist()]
    n = len(sessions)
    hh, mm = (int(x) for x in str(assumed_time or "14:00").split(":"))

    used = []
    for _, r in out.iterrows():
        v = r.get("publish_dt_verified")
        if pd.notna(v):
            used.append(pd.Timestamp(v))
        elif mode == "backfill_assumed":
            used.append(pd.Timestamp(r["asof_date"]).normalize() + pd.Timedelta(hours=hh, minutes=mm))
        else:
            used.append(pd.NaT)
    out["publish_used"] = pd.Series(used, index=out.index)
    out["pub_verified"] = out["publish_dt_verified"].notna()

    avail, blocks, lag_days = [], [], []
    for _, r in out.iterrows():
        pub = r["publish_used"]
        if pd.isna(pub) or n == 0:
            avail.append(pd.NaT)
            blocks.append(0)
            lag_days.append(None)
            continue
        pub_day = pd.Timestamp(pub).normalize()
        day_pos = bisect.bisect_right(sessions, pub_day) - 1  # index of publication-day session
        if same_day_release_price in ("close", "settle"):
            allow_same_day = pd.Timestamp(pub).time() <= pd.Timestamp(
                pub_day.strftime("%Y-%m-%d") + " " + cutoff).time()
            first = day_pos if allow_same_day else day_pos + 1
        else:
            first = day_pos + 1
        target = first + max(0, int(min_lag_sessions) - 1)
        target = max(0, min(target, n - 1))
        avail.append(sessions[target])
        blocks.append(target - day_pos)
        lag_days.append((sessions[target] - pub_day).days)
    out["availability_session"] = pd.to_datetime(pd.Series(avail, index=out.index))
    out["n_blocks"] = blocks
    out["availability_lag_days"] = lag_days
    return out


def attach_previous_availability(ind: pd.DataFrame) -> pd.DataFrame:
    """Availability of the previous published observation (needed for 'two weeks down')."""
    out = ind.copy()
    out["prev_availability_session"] = out["availability_session"].shift(1)
    out["prev_asof_date"] = out["asof_date"].shift(1)
    return out
