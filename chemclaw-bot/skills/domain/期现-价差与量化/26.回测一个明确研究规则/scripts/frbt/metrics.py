# -*- coding: utf-8 -*-
"""Performance statistics and the cost-attribution convention.

Definitions (fixed once, used by every report and the workbook formulas):

  daily return      r_t = equity_t / equity_{t-1} - 1
  annualisation     periods_per_year = 244 CZCE trading sessions
  CAGR              (equity_end / equity_start) ** (1 / years) - 1,  years = sessions / 244
  volatility        std(r_t, ddof=1) * sqrt(244)
  Sharpe            (mean(r_t) - rf_daily) / std(r_t) * sqrt(244),  rf_daily = rf_annual / 244
  Max drawdown      max over t of (peak_equity_t - equity_t) / peak_equity_t
  Trade PnL         net_pnl_after_slip = (exit - entry) * dir * multiplier * lots
                    - commissions - slippage(ticks*tick*multiplier*lots, per leg)
  Win rate          share of round trips with net_pnl_after_slip > 0
  Profit factor     sum(positive net pnl) / |sum(negative net pnl)|
  Payoff ratio      mean(positive) / |mean(negative)|
  Exposure          share of sessions with |lots| > 0
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SESSIONS_PER_YEAR = 244


def drawdown_curve(equity: pd.Series) -> pd.DataFrame:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return pd.DataFrame({"equity": equity, "peak": peak, "drawdown": dd,
                         "underwater_sessions": (dd < 0).astype(int).groupby((dd >= 0).cumsum()).cumsum()})


def max_drawdown(equity: pd.Series) -> dict:
    if equity.empty:
        return {"max_dd": np.nan, "start": None, "trough": None, "recovery": None}
    peak = equity.cummax()
    dd = equity / peak - 1.0
    trough = dd.idxmin()
    # find the peak date of the worst drawdown
    peak_idx = equity.loc[:trough].idxmax()
    after = equity.loc[trough:]
    rec = after[after >= equity.loc[peak_idx]]
    return {
        "max_dd": float(dd.min()),
        "start": equity.loc[peak_idx] if peak_idx is not None else None,
        "start_date": peak_idx,
        "trough_date": trough,
        "recovery_date": rec.index[0] if len(rec) else None,
        "dd_duration_sessions": int(equity.index.get_loc(trough) - equity.index.get_loc(peak_idx)),
    }


def performance(daily: pd.DataFrame, trades: pd.DataFrame, *, rf_annual: float = 0.0) -> dict:
    if daily.empty:
        return {}
    d = daily.copy().set_index("date")
    eq = d["equity"].astype(float)
    ret = eq.pct_change().fillna(0.0)
    n = len(eq)
    years = n / SESSIONS_PER_YEAR
    start_eq = float(eq.iloc[0])
    end_eq = float(eq.iloc[-1])
    cagr = (end_eq / start_eq) ** (1 / years) - 1 if years > 0 and start_eq > 0 and end_eq > 0 else np.nan
    vol = float(ret.std(ddof=1) * np.sqrt(SESSIONS_PER_YEAR)) if n > 2 else np.nan
    rf_d = rf_annual / SESSIONS_PER_YEAR
    sharpe = float((ret.mean() - rf_d) / ret.std(ddof=1) * np.sqrt(SESSIONS_PER_YEAR)) \
        if n > 2 and ret.std(ddof=1) > 0 else np.nan
    downside = ret[ret < 0].std(ddof=1)
    sortino = float((ret.mean() - rf_d) / downside * np.sqrt(SESSIONS_PER_YEAR)) \
        if n > 2 and downside and downside > 0 else np.nan
    mdd = max_drawdown(eq)
    calmar = cagr / abs(mdd["max_dd"]) if mdd["max_dd"] and mdd["max_dd"] < 0 else np.nan

    t = trades
    n_tr = int(len(t))
    if n_tr:
        pnl = t["net_pnl_after_slip"].astype(float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        win_rate = float(len(wins) / n_tr)
        profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else np.nan
        payoff = float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else np.nan
        avg_hold = float(t["bars_held"].mean())
        total_fees = float(t["fees"].sum())
        total_slip = float(t["slippage_cost"].sum())
        gross = float(t["gross_pnl"].sum())
    else:
        pnl = pd.Series(dtype=float)
        win_rate = profit_factor = payoff = avg_hold = np.nan
        total_fees = total_slip = gross = 0.0

    exposure = float((d["lots"].fillna(0).astype(float) > 0).mean())
    return {
        "sessions": n,
        "years": years,
        "start_equity": start_eq,
        "end_equity": end_eq,
        "total_return": end_eq / start_eq - 1 if start_eq else np.nan,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_dd": mdd["max_dd"],
        "max_dd_start": mdd["start_date"],
        "max_dd_trough": mdd["trough_date"],
        "max_dd_recovery": mdd["recovery_date"],
        "max_dd_duration_sessions": mdd["dd_duration_sessions"],
        "calmar": calmar,
        "trades": n_tr,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "payoff_ratio": payoff,
        "avg_hold_sessions": avg_hold,
        "gross_pnl": gross,
        "fees": total_fees,
        "slippage": total_slip,
        "net_pnl": float(pnl.sum()) if n_tr else 0.0,
        "exposure": exposure,
        "avg_margin_util": float(d["margin_util"].mean()) if "margin_util" in d else np.nan,
        "max_margin_util": float(d["margin_util"].max()) if "margin_util" in d else np.nan,
    }


def annual_table(daily: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    d = daily.copy()
    d["year"] = pd.to_datetime(d["date"]).dt.year
    rows = []
    for y, g in d.groupby("year"):
        eq = g["equity"].astype(float).reset_index(drop=True)
        start_eq = eq.iloc[0]
        ret = eq.pct_change().fillna(0.0)
        mdd = max_drawdown(pd.Series(eq.values, index=pd.to_datetime(g["date"])))
        tg = trades[pd.to_datetime(trades["exit_day"]).dt.year == y] if len(trades) else trades
        n = len(tg) if len(trades) else 0
        pnl = tg["net_pnl_after_slip"].astype(float) if n else pd.Series(dtype=float)
        rows.append({
            "year": int(y),
            "sessions": len(g),
            "start_equity": float(start_eq),
            "end_equity": float(eq.iloc[-1]),
            "return": float(eq.iloc[-1] / start_eq - 1),
            "max_dd": mdd["max_dd"],
            "vol": float(ret.std(ddof=1) * np.sqrt(SESSIONS_PER_YEAR)) if len(ret) > 2 else np.nan,
            "trades": n,
            "win_rate": float((pnl > 0).mean()) if n else np.nan,
            "profit_factor": float(pnl[pnl > 0].sum() / abs(pnl[pnl < 0].sum()))
            if n and (pnl < 0).any() else np.nan,
            "net_pnl": float(pnl.sum()) if n else 0.0,
            "exposure": float((g["lots"].fillna(0) > 0).mean()),
        })
    return pd.DataFrame(rows)


def monthly_table(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    d = daily.copy()
    d["ym"] = pd.to_datetime(d["date"]).dt.to_period("M")
    out = []
    for ym, g in d.groupby("ym"):
        eq = g["equity"].astype(float).reset_index(drop=True)
        out.append({"month": str(ym), "return": float(eq.iloc[-1] / eq.iloc[0] - 1)})
    return pd.DataFrame(out)
