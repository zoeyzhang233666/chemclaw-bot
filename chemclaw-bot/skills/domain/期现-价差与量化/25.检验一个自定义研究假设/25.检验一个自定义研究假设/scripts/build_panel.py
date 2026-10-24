# -*- coding: utf-8 -*-
"""Build the point-in-time weekly panel for the hypothesis study.

Alignment rules (recording, never interpolation):
  * Inventory observation date = 统计截止日 printed in the article ("截至...")
  * Inventory release time     = 原文发布时间 pub_ts (Mysteel page header)
  * Entry time (T0):
        pre15  -> close of the 14:00-15:00 bar on the observation day (report out ~14:00)
        next   -> first trading-day close strictly after publication (conservative)
  * Signal state uses (I_t, I_{t-1}, I_{t-2}), all published BEFORE T0 -> no look-ahead.
  * Forward return = close(T0 + k trading sessions) - close(T0), on the price basis chosen.

Price bases:
  near  : 100ppi daily table "near contract" quote (= 主力合约 quotes at T-1 open)
  basis : near_basis = spot_100ppi - near_fut, in 元/吨
  MA0   : Sina 主力连续 close (unadjusted) - for reference / robustness only

Outputs: build/panel_weekly.csv, build/coverage.json
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

try:  # optional, legacy provenance files; not needed for the run
    pass
except Exception:  # noqa: BLE001
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inv", default="data/port_inventory_weekly.csv")
    ap.add_argument("--sf", default="data/100ppi_sf.csv")
    ap.add_argument("--fut-extra", default="data/port_inventory_legacy_2019_2022.csv",
                    help="OPTIONAL legacy file, provenance UNVERIFIED -> excluded by default")
    ap.add_argument("--include-legacy", action="store_true")
    ap.add_argument("--min", default="data/futures/MA0_60min.csv")
    ap.add_argument("--entry", default="pre15", choices=["pre15", "next"])
    ap.add_argument("--out", default="build/panel_weekly.csv")
    ap.add_argument("--cov", default="build/coverage.json")
    ap.add_argument("--horizons", default="5,10")
    a = ap.parse_args()

    H = [int(x) for x in a.horizons.split(",")]
    inv = pd.read_csv(a.inv, parse_dates=["asof"])
    inv = inv.dropna(subset=["total"]).sort_values("asof").reset_index(drop=True)
    legacy_added = 0
    if a.include_legacy and os.path.exists(a.fut_extra):
        lg = pd.read_csv(a.fut_extra, parse_dates=["asof"])
        lg = lg.dropna(subset=["total"])
        lg["pub_ts"] = pd.to_datetime(lg["pub_ts"], errors="coerce")
        have = set(inv["asof"].dt.date)
        lg = lg[~lg["asof"].dt.date.isin(have)]
        inv = pd.concat([inv, lg], ignore_index=True).sort_values("asof").reset_index(drop=True)
        legacy_added = len(lg)
    inv["pub_ts"] = pd.to_datetime(inv["pub_ts"], errors="coerce")

    sf = pd.read_csv(a.sf, parse_dates=["date"]).sort_values("date").set_index("date")
    mn = None
    if a.entry == "pre15" and os.path.exists(a.min):
        mn = pd.read_csv(a.min, parse_dates=["bar_end"]).set_index("bar_end")["close"]

    def price_at(ts_dt, obs_day):
        """Price observable right after publication."""
        if a.entry == "pre15" and mn is not None:
            cand = mn[(mn.index.date == obs_day.date()) &
                      (mn.index.time <= pd.Timestamp("15:00").time()) &
                      (mn.index.time >= pd.Timestamp("14:00").time())]
            if len(cand):
                return float(cand.iloc[-1]), "60min_1400_1500"
        # fallback: first daily row strictly after the observation day
        later = sf.index[(sf.index > obs_day)]
        if len(later):
            return float(sf["near_fut"].loc[later[0]]), "next_day_close"
        return np.nan, "missing"

    def fwd(t0_date, k):
        if pd.isna(t0_date) or t0_date not in sf.index:
            return np.nan, ""
        j = sf.index.get_loc(t0_date)
        if j + k >= len(sf.index):
            return np.nan, ""
        d1 = sf.index[j + k]
        return float(sf["near_fut"].loc[d1]) - float(sf["near_fut"].loc[t0_date]), d1.date().isoformat()

    out = []
    for i in range(len(inv)):
        r = inv.iloc[i]
        obs = r["asof"]
        rec = {"asof": obs.date().isoformat(),
               "pub_ts": r["pub_ts"].strftime("%Y-%m-%d %H:%M") if pd.notna(r["pub_ts"]) else "",
               "total": float(r["total"]), "wow_chg": r.get("wow_chg"),
               "east": r.get("east"), "south": r.get("south"),
               "sample_cov": r.get("sample_cov"), "url": r.get("url", ""),
               "legacy": bool(r.get("legacy", "legacy" in inv.columns and r.get("legacy") is True))}
        rec["W1"] = inv["asof"].iloc[i - 1].date().isoformat() if i >= 1 else ""
        rec["W2"] = inv["asof"].iloc[i - 2].date().isoformat() if i >= 2 else ""
        rec["gap_days"] = (obs - inv["asof"].iloc[i - 1]).days if i >= 1 else np.nan
        if i >= 2:
            d1 = float(r["total"]) - float(inv["total"].iloc[i - 1])
            d2 = float(inv["total"].iloc[i - 1]) - float(inv["total"].iloc[i - 2])
            rec["d1"], rec["d2"] = round(d1, 2), round(d2, 2)
            valid = 5 <= rec["gap_days"] <= 10 and 5 <= (inv["asof"].iloc[i - 1] -
                                                         inv["asof"].iloc[i - 2]).days <= 10
            rec["state"] = ("DOWN2" if (d1 < 0 and d2 < 0) else
                            "UP2" if (d1 > 0 and d2 > 0) else "MIXED")
            rec["flat_flag"] = int(abs(d1) < 0.005 or abs(d2) < 0.005)
            rec["dec1"] = "DOWN2" if (d1 <= -1 and d2 <= -1) else (
                "UP2" if (d1 >= 1 and d2 >= 1) else "OTHER")
            rec["valid_gap"] = int(valid)
        p0, tag = price_at(r["pub_ts"], obs)
        rec["P0"], rec["entry_rule"] = p0, tag
        rec["fut0"] = float(sf["near_fut"].loc[obs]) if obs in sf.index else np.nan
        rec["spot0"] = float(sf["spot"].loc[obs]) if obs in sf.index else np.nan
        rec["near_basis0"] = float(sf["near_basis"].loc[obs]) if obs in sf.index else np.nan
        for k in H:
            v, d = fwd(obs, k)
            rec[f"dFut_{k}"] = v
            rec[f"end_{k}"] = d
        out.append(rec)

    panel = pd.DataFrame(out)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    panel.to_csv(a.out, index=False, encoding="utf-8-sig")

    cov = {
        "inventory": {"rows": int(len(inv)),
                      "first": inv["asof"].min().date().isoformat(),
                      "last": inv["asof"].max().date().isoformat(),
                      "legacy_added": int(legacy_added),
                      "pub_ts_missing": int(inv["pub_ts"].isna().sum())},
        "price": {"daily_rows": int(len(sf)),
                  "daily_range": [sf.index.min().date().isoformat(),
                                  sf.index.max().date().isoformat()],
                  "minute_rows": int(0 if mn is None else len(mn))},
        "panel": {"rows": int(len(panel)),
                  "state_counts": panel["state"].value_counts().to_dict() if "state" in panel else {},
                  "entry_rule_counts": panel["entry_rule"].value_counts().to_dict(),
                  "gap_days_counts": {str(k): int(v) for k, v in
                                      panel["gap_days"].value_counts().head(8).items()}},
    }
    with open(a.cov, "w", encoding="utf-8-sig") as f:
        json.dump(cov, f, ensure_ascii=False, indent=1)
    print(json.dumps(cov, ensure_ascii=False, indent=1))
    print("written", a.out, len(panel), "rows")


if __name__ == "__main__":
    main()
