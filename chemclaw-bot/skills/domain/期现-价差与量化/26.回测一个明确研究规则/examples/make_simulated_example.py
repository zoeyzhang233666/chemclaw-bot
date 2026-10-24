# -*- coding: utf-8 -*-
"""Generate a SYNTHETIC dataset and run the engine on it end-to-end.

Purpose: prove the engine works even when no real market data is available, and give a
worked example of the input file formats. The output of this script is SIMULATED and must
never be presented as a real strategy result.

    python make_simulated_example.py --out sim
    python scripts/run_backtest.py analyze --config sim/sim_spec.json --out sim/out
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DEFAULT = os.path.join(HERE, "simulated_demo")


def build(out: str, seed: int = 20261020, n_weeks: int = 220) -> dict:
    rng = np.random.default_rng(seed)
    os.makedirs(os.path.join(out, "data"), exist_ok=True)

    # ---- trading calendar: Mon-Fri, drop a few holiday blocks
    days = pd.bdate_range("2021-01-04", periods=1450)
    holidays = set()
    for anchor in ("2021-02-11", "2021-05-03", "2021-10-01", "2022-02-01", "2022-05-02",
                   "2022-10-03", "2023-01-23", "2023-05-01", "2023-10-02", "2024-02-09",
                   "2024-05-01", "2024-10-01"):
        a = pd.Timestamp(anchor)
        holidays.update(pd.bdate_range(a, periods=5))
    days = [d for d in days if d not in holidays]
    cal = pd.DataFrame({"date": days})
    cal["prev_date"] = cal["date"].shift(1)
    cal["next_date"] = cal["date"].shift(-1)

    # ---- three overlapping contracts, quarterly
    contracts = []
    for year, mon in ((2021, 9), (2022, 1), (2022, 5), (2022, 9), (2023, 1), (2023, 5),
                      (2023, 9), (2024, 1), (2024, 5), (2024, 9)):
        code = "XX%02d%02d" % (year % 100, mon)
        start = pd.Timestamp(year - 1, max(1, mon - 9), 1)
        end = pd.Timestamp(year, mon, 1) + pd.Timedelta(days=20)
        live = [d for d in days if start <= d <= end]
        if not live:
            continue
        base = 2400 + rng.normal(0, 120)
        noise = rng.normal(0, 14, len(live)).cumsum()
        for i, d in enumerate(live):
            px = float(base + noise[i] + (mon - 9) * 6)
            oi = 900_000 if i > len(live) * 0.55 else 200_000
            contracts.append({
                "contract": code, "delivery_month": "%d-%02d" % (year, mon),
                "date": d, "open": round(px + rng.normal(0, 3), 1),
                "high": round(px + abs(rng.normal(0, 8)), 1),
                "low": round(px - abs(rng.normal(0, 8)), 1),
                "close": round(px, 1), "settle": round(px + rng.normal(0, 2), 1),
                "volume": int(abs(rng.normal(80_000, 20_000))) + 100,
                "open_interest": int(oi * (0.7 + 0.6 * rng.random())),
            })
    con = pd.DataFrame(contracts)

    # ---- weekly indicator: mean-reverting level with an upward drift in 30% of weeks
    weeks = pd.date_range("2021-01-06", periods=n_weeks, freq="W-WED")
    level = 60.0
    rows = []
    for w in weeks:
        shock = rng.normal(0, 4.5)
        level = max(20.0, level * 0.94 + 60 * 0.06 + shock)
        # publish clock: Wednesday 13:00-14:40 (verified), or unknown for the first 60 weeks
        if w >= weeks[60]:
            mins = int(rng.integers(0, 100))
            pub = w + pd.Timedelta(hours=13, minutes=mins)
            pubv = pub
        else:
            pubv = pd.NaT
        rows.append({
            "asof_date": w.date().isoformat(),
            "value_wan_ton": round(level, 2),
            "publish_dt_verified": "" if pd.isna(pubv) else pubv.strftime("%Y-%m-%d %H:%M:%S"),
        })
    ind = pd.DataFrame(rows)

    # ---- spot = dominant future + a random basis
    dom = (con.sort_values(["date", "open_interest"], ascending=[True, False])
           .groupby("date").first().reset_index())
    spot = dom[["date", "settle"]].rename(columns={"settle": "future_settle"})
    spot["spot_east_cn"] = (spot["future_settle"] + rng.normal(60, 45, len(spot))).round(1)
    spot = spot[["date", "spot_east_cn"]]

    cal.to_csv(os.path.join(out, "data", "calendar.csv"), index=False)
    con.to_csv(os.path.join(out, "data", "contracts_daily.csv"), index=False)
    ind.to_csv(os.path.join(out, "data", "indicator_weekly.csv"), index=False, encoding="utf-8-sig")
    spot.to_csv(os.path.join(out, "data", "spot_daily.csv"), index=False, encoding="utf-8-sig")

    spec = {
        "meta": {
            "rule_id": "SIM-demo-drawdown-basis",
            "title": "【模拟数据演示】库存回落且基差偏高 → 做多持有 8 日（非真实收益）",
            "nl_rule": "演示用规则：模拟库存两周回落且模拟基差高于滚动 75% 分位时，次日开盘做多，持有 8 个交易日。",
            "declared_before_running": True,
            "data_is_simulated": True,
            "simulation_note": "本示例全部数据由随机过程生成，仅用于验证回测引擎与报告管线，任何数字都不是真实策略收益。",
        },
        "provenance": {
            "contract_spec": {"basis": "simulated", "note": "合成合约：乘数 10、最小变动 1"},
            "margin_rate": {"basis": "assumed", "value": 0.10, "note": "演示假设"},
            "fee_per_lot": {"basis": "assumed", "value": 2.0, "note": "演示假设"},
            "slippage_ticks": {"basis": "assumed", "value": 0.5, "note": "演示假设"},
            "tick_size": {"basis": "simulated", "value": 1},
            "multiplier": {"basis": "simulated", "value": 10},
            "indicator_publication": {"basis": "simulated", "note": "合成发布时刻；前 60 周故意留空以演示缺口处理"},
            "spot_price": {"basis": "simulated", "note": "合成分现货价"},
        },
        "universe": {"exchange": "SIM", "product_code": "XX", "direction_mode": "long"},
        "contract": {"selection": "kth_by_open_interest", "k": 1, "roll_rule": "open_interest_kth",
                     "no_trade_window_days_before_delivery": 10, "roll_lead_days": 2},
        "timing": {"signal_cutoff_same_day": "15:00", "indicator_lag_sessions_min": 1,
                   "entry_lag_sessions": 1, "prices": "open", "same_day_release_price": None,
                   "spot_availability": "next_session"},
        "signal": {
            "indicator": "sim_inventory_wan_ton", "combine": "and", "min_history": 6,
            "ops": [
                {"type": "change_run", "weeks": 2, "direction": "down", "label": "连续两周回落"},
                {"type": "channel_change", "n": 3, "threshold": 0.0, "channel_mode": "low",
                 "label": "处于近3期通道下沿"},
            ],
        },
        "price_filter": {"enabled": True, "type": "pct_quantile", "side": "above",
                         "threshold": 0.75, "lookback_points": 400,
                         "basis_mapping": "spot_minus_fut", "warmup_min_points": 60},
        "entry": {"order_type": "market_next_open", "reentry_while_holding": "ignore"},
        "exit": {"max_hold_sessions": 8, "take_profit_pct": None, "stop_loss_pct": None,
                 "exit_on_roll_when_contract_changes": False},
        "position": {"sizing": "fixed_lots", "lots": 1, "capital": 100000, "max_lots": 1,
                     "max_margin_utilisation": 0.5},
        "costs": {"fee_mode": "per_lot", "fee_value": 2.0, "commission_min_per_lot": 0.0,
                  "slippage_ticks": 0.5, "tick_size": 1, "multiplier": 10, "margin_rate": 0.10,
                  "cost_sensitivity": {"fee_multiple": [1, 2], "slippage_ticks": [0.5, 2.0]}},
        "data": {"indicator_file": "data/indicator_weekly.csv",
                 "contracts_file": "data/contracts_daily.csv",
                 "calendar_file": "data/calendar.csv",
                 "spot_file": "data/spot_daily.csv",
                 "publication_mode": "backfill_assumed",
                 "assumed_publish_time": "14:00"},
        "window": {},
        "analysis": {"metrics": {"rf_annual": 0.0, "sessions_per_year": 244},
                     "sensitivity": {"drawdown_n": [2, 3, 4], "change_run_weeks": [2, 3],
                                     "channel_threshold_units": [0.0, 0.5],
                                     "hold_sessions": [5, 8, 12], "basis_quantile": [0.7, 0.75, 0.85]},
                     "oos": {"split_date": "2023-06-01"}},
    }
    spec_path = os.path.join(out, "sim_spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print("wrote synthetic data to", out)
    print("  indicator weeks: %d (verified after week 60)" % len(ind))
    print("  contracts: %d, sessions: %d" % (con["contract"].nunique(), len(cal)))
    return {"spec": spec_path, "weeks": len(ind)}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--seed", type=int, default=20261020)
    a = ap.parse_args(argv)
    build(a.out, a.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
