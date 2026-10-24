# -*- coding: utf-8 -*-
"""Build the point-in-time datasets used by the PVC operating-rate study.

Inputs  (raw, fetched from public pages, archived verbatim in raw/)
-------
raw/util_articles.json          scraped Mysteel/oilchem PVC capacity-utilisation articles
                                (title / publish timestamp / body snippet / url)
raw/pvc_contracts.json          DCE PVC individual contracts VYYMM from Sina (open, high, low,
                                close, volume, open interest, settlement) 2018-05 .. 2026-10

Outputs (case dir)
------------------
data/util_weekly.csv            one row per weekly *bulletin* (8 rows in this study):
                                stat_week_end, window, pub_ts, util_total, cwe_pct, yoy_pct,
                                calc, calc_cwe, calc_yoy, eth, eth_cwe, eth_yoy, sample_n,
                                capacity_base_wt, url, bulletin
data/util_monthly_production.csv  monthly PVC output (verification index only)
data/pvc_futures_daily.csv      volume-rolled continuous contract, daily bars + roll flag
data/pvc_futures_monthly.csv    monthly bars (month-end close & settlement)
data/futures_meta.json          provenance / gap statement
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.dirname(HERE)
RAW = os.path.join(HERE, "raw")
DATA = os.path.join(CASE, "data")
os.makedirs(DATA, exist_ok=True)

NUM = r"([-+]?\d+(?:\.\d+)?)"
GAP = r"[^0-9]{0,6}"

RE_WEEK = re.compile(r"[\(（]\s*(\d{8})\s*[\)）]")
RE_MAIN = re.compile(r"本周PVC生产企业产能利用率在\s*" + NUM + r"%")
RE_MAIN_C2C = re.compile(r"环比" + GAP + NUM + r"%[，,]\s*同比" + GAP + NUM + "%")
RE_CHAIN = re.compile(
    r"电石法在\s*" + NUM + r"%[，,]\s*环比" + GAP + NUM + r"%[，,]\s*同比" + GAP + NUM +
    r"%[^0-9]{1,12}乙烯法在\s*" + NUM + r"%[，,]\s*环比" + GAP + NUM + r"%[，,]\s*同比" + GAP + NUM + "%")
RE_SAMPLE = re.compile(r"样本涵盖国内\s*(\d+)\s*家PVC生产企业及厂区")
RE_CAPBASE = re.compile(r"产能基数变更为\s*([\d.]+)\s*万吨")
RE_WINDOW = re.compile(r"[\(（](\d{8})-(\d{8})[\)）]")
RE_MONTHLY = re.compile(r"(\d{4})年(\d{1,2})月国内PVC产量在\s*" + NUM + r"\s*万吨")


def clean(s):
    s = s.replace('id="article-content">', ' ')
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).replace("&nbsp;", " ").strip()


# ------------------------------------------------------------------ 1) weekly utilisation


def build_weekly():
    recs = json.load(open(os.path.join(RAW, "util_articles.json"), encoding="utf-8"))
    rows, seen = [], set()
    for url, v in recs.items():
        title, body = v["title"], clean(v["body"])
        m_w = RE_WEEK.search(title)
        if not m_w or not title.startswith("[产能利用率]"):
            continue                      # only the statistical bulletin carries all fields
        week_end = pd.to_datetime(m_w.group(1), format="%Y%m%d")
        if week_end in seen:
            continue
        m = RE_MAIN.search(body)
        if not m:
            continue
        rec = {"stat_week_end": week_end, "bulletin": "产能利用率周数据统计",
               "pub_ts": pd.to_datetime(v["publish"], utc=True).tz_convert("Asia/Shanghai")
               .tz_localize(None), "util_total": float(m.group(1)),
               "cwe_pct": None, "yoy_pct": None,
               "calc": None, "calc_cwe": None, "calc_yoy": None,
               "eth": None, "eth_cwe": None, "eth_yoy": None,
               "sample_n": None, "capacity_base_wt": None, "url": url,
               "title": title, "body": body}
        mc = RE_MAIN_C2C.search(body)
        if mc:
            rec["cwe_pct"], rec["yoy_pct"] = float(mc.group(1)), float(mc.group(2))
        mch = RE_CHAIN.search(body)
        if mch:
            g = [float(x) for x in mch.groups()]
            rec.update(calc=g[0], calc_cwe=g[1], calc_yoy=g[2],
                       eth=g[3], eth_cwe=g[4], eth_yoy=g[5])
        ms = RE_SAMPLE.search(body)
        if ms:
            rec["sample_n"] = int(ms.group(1))
        mcb = RE_CAPBASE.search(body)
        if mcb:
            rec["capacity_base_wt"] = float(mcb.group(1))
        # statistical window label from the companion "周数据分析" article if present
        mwin = RE_WINDOW.search(title)
        rec["window"] = ("%s-%s" % (mwin.group(1), mwin.group(2))) if mwin else ""
        seen.add(week_end)
        rows.append(rec)
    df = pd.DataFrame(rows).sort_values("stat_week_end").reset_index(drop=True)
    if not df.empty:
        df["iso_year"] = df["stat_week_end"].dt.isocalendar().year.astype(int)
        df["iso_week"] = df["stat_week_end"].dt.isocalendar().week.astype(int)
        # internal consistency: level - cwe = level of previous week's bulletin
        prev = df["util_total"].shift(1)
        implied_prev = df["util_total"] / (1 + df["cwe_pct"] / 100.0)
        df["implied_prev_level"] = implied_prev
        df["cwe_check_err_pp"] = df["cwe_pct"] - (df["util_total"] / prev - 1) * 100.0
        df["route_share_sum"] = df["calc"] + df["eth"]
        df["route_weighted_check"] = (df["calc"].fillna(0) + df["eth"].fillna(0))
    df.to_csv(os.path.join(DATA, "util_weekly.csv"), index=False, encoding="utf-8-sig")
    return df


def build_monthly_production():
    recs = json.load(open(os.path.join(RAW, "util_articles.json"), encoding="utf-8"))
    rows = {}
    for url, v in recs.items():
        body = clean(v["body"])
        if "样本产量月数据" not in v["title"]:
            continue
        m = RE_MONTHLY.search(body)
        if not m:
            continue
        key = "%s-%02d" % (m.group(1), int(m.group(2)))
        rows[key] = {"month": key, "output_wan_t": float(m.group(3)),
                     "pub_ts": pd.to_datetime(v["publish"], utc=True)
                     .tz_convert("Asia/Shanghai").tz_localize(None),
                     "url": url, "title": v["title"]}
    df = pd.DataFrame(sorted(rows.values(), key=lambda r: r["month"]))
    if df.empty:
        df = pd.DataFrame(columns=["month", "output_wan_t", "pub_ts", "url", "title"])
    df.to_csv(os.path.join(DATA, "util_monthly_production.csv"), index=False,
              encoding="utf-8-sig")
    return df


# ------------------------------------------------------------------ 2) futures


def ym_of(sym):
    return int(sym[1:3]), int(sym[3:5])


def build_futures():
    store = json.load(open(os.path.join(RAW, "pvc_contracts.json"), encoding="utf-8"))
    # long form
    rows = []
    for sym, recs in store.items():
        y, mo = ym_of(sym)
        for r in recs:
            rows.append({"sym": sym, "ym": y * 100 + mo, "date": r["date"],
                         "close": r["close"], "settle": r["settle"],
                         "volume": r["volume"], "oi": r["oi"],
                         "high": r["high"], "low": r["low"], "open": r["open"]})
    lf = pd.DataFrame(rows)
    lf["date"] = pd.to_datetime(lf["date"])
    lf = lf.sort_values(["date", "sym"]).drop_duplicates(["date", "sym"])

    # calendar sessions
    sessions = pd.DatetimeIndex(sorted(lf["date"].unique()))

    # choose active contract: highest volume; ties -> highest OI; then later expiry
    pick = (lf.sort_values(["date", "volume", "oi", "ym"], ascending=[True, False, False, False])
            .drop_duplicates("date", keep="first"))
    pick = pick.set_index("date").reindex(sessions)

    # force roll only when another contract is clearly dominant, and never back-roll
    active, roll_flag, roll_from = [], [], []
    cur = None
    for d in sessions:
        row = pick.loc[d]
        cand_sym = row["sym"]
        if cur is None:
            cur = cand_sym
        else:
            cur_row = lf[(lf.date == d) & (lf.sym == cur)]
            if len(cur_row) == 0:                       # current contract expired today
                cur = cand_sym
            else:
                cv = float(cur_row["volume"].iloc[0])
                cy = int(cur_row["ym"].iloc[0])
                new_v = float(row["volume"])
                new_y = int(row["ym"])
                if (np.isfinite(new_v) and new_v > 1.3 * cv and new_y > cy
                        and d.month > (cy % 100)):
                    cur = cand_sym
        active.append(cur)
        prev = active[-2] if len(active) > 1 else None
        roll_flag.append(bool(prev is not None and prev != cur))
        roll_from.append(prev if prev is not None and prev != cur else "")

    cont = pd.DataFrame({"date": sessions})
    # price of the active contract on each session
    idx = {(r.date, r.sym): r for r in lf.itertuples()}
    close, settle, vol, oi = [], [], [], []
    for d, sym in zip(sessions, active):
        r = idx.get((d, sym))
        if r is None:
            # carry forward last known close of same contract
            prior = lf[(lf.sym == sym) & (lf.date <= d)]
            r = prior.iloc[-1] if len(prior) else None
        close.append(getattr(r, "close", np.nan) if r is not None else np.nan)
        settle.append(getattr(r, "settle", np.nan) if r is not None else np.nan)
        vol.append(getattr(r, "volume", np.nan) if r is not None else np.nan)
        oi.append(getattr(r, "oi", np.nan) if r is not None else np.nan)
    cont["contract"] = active
    cont["close"] = close
    cont["settle"] = settle
    cont["volume"] = vol
    cont["oi"] = oi
    cont["roll_flag"] = roll_flag
    cont["rolled_from"] = roll_from
    cont["ret_1d"] = cont["close"].pct_change()
    cont["ret_1d_settle"] = cont["settle"].pct_change()
    # zero the roll jump for the adjusted series
    jump = cont["close"] / cont["close"].shift(1) - 1
    cont["roll_jump"] = np.where(cont["roll_flag"], jump, 0.0)
    cont["adj_close"] = (1 + (cont["ret_1d"] - cont["roll_jump"]).fillna(0)).cumprod() * cont["close"].iloc[0]
    cont.to_csv(os.path.join(DATA, "pvc_futures_daily.csv"), index=False, encoding="utf-8-sig")

    # monthly bars (by calendar month; last session)
    m = cont.set_index("date")
    mon = pd.DataFrame({"close": m["close"].resample("ME").last(),
                        "settle": m["settle"].resample("ME").last(),
                        "adj_close": m["adj_close"].resample("ME").last(),
                        "first_session": m.index.to_series().resample("ME").first()})
    mon["ret_m"] = mon["adj_close"].pct_change()
    mon = mon.reset_index().rename(columns={"date": "month_end"})
    mon["month"] = mon["month_end"].dt.strftime("%Y-%m")
    mon.to_csv(os.path.join(DATA, "pvc_futures_monthly.csv"), index=False, encoding="utf-8-sig")

    meta = {"n_sessions": int(len(sessions)), "first": str(sessions[0].date()),
            "last": str(sessions[-1].date()), "n_contracts": int(lf["sym"].nunique()),
            "n_rolls": int(sum(roll_flag)), "source": "Sina InnerFuturesNewService.getDailyKLine",
            "roll_rule": "换月=另一合约成交量>当前合约130%且到期月更晚且已过当前月；否则不换",
            "gap": "月产量件头公开正文只覆盖 2026-08/09；更早历史需付费数据源，未编造。"}
    json.dump(meta, open(os.path.join(DATA, "futures_meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return cont, mon, meta


if __name__ == "__main__":
    w = build_weekly()
    mp = build_monthly_production()
    c, mm, meta = build_futures()
    print("weekly bulletins:", len(w))
    print(w[["stat_week_end", "pub_ts", "util_total", "cwe_pct", "calc", "eth", "sample_n"]]
          .to_string(index=False) if len(w) else "(none)")
    print("monthly production rows:", len(mp))
    print(mp.to_string(index=False) if len(mp) else "(none)")
    print("futures sessions:", meta["n_sessions"], meta["first"], "->", meta["last"],
          "| contracts", meta["n_contracts"], "| rolls", meta["n_rolls"])
    print(c.tail(3)[["date", "contract", "close", "roll_flag"]].to_string(index=False))
    print("monthly bars:", len(mm), mm["month"].iloc[0], "->", mm["month"].iloc[-1])
