# -*- coding: utf-8 -*-
"""Fetch 60-minute bars for a continuous futures symbol (Sina getFewMinLine).

Why 60-min: the inventory report is released ~14:00 on the observation day, i.e. BEFORE
the 15:00 close. A 60-min bar labelled 15:00 covers 14:00-15:00, so its close IS the
price available right after publication -> same-day-close design without look-ahead.
(For backtest-grade studies buy the historical intraday feed; this is the public fallback.)

Usage: python fetch_minute.py --symbol MA0 --out data/futures/MA0_60min.csv
"""
import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlib  # noqa: E402

PAT = re.compile(r'"d":"([^"]+)","o":"([^"]+)","h":"([^"]+)","l":"([^"]+)","c":"([^"]+)",'
                 r'"v":"([^"]+)","p":"([^"]+)"')
URL = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{s}_{p}=/"
       "InnerFuturesNewService.getFewMinLine?symbol={s}&type={p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="MA0")
    ap.add_argument("--period", default="60")
    ap.add_argument("--out", default="data/futures/MA0_60min.csv")
    a = ap.parse_args()
    text = netlib.fetch(URL.format(s=a.symbol, p=a.period),
                        referer="https://finance.sina.com.cn/")
    rows = PAT.findall(text)
    if not rows:
        raise SystemExit("no bars parsed")
    rows.sort(key=lambda r: r[0])
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["bar_end", "open", "high", "low", "close", "volume", "open_interest"])
        for r in rows:
            w.writerow([r[0]] + [float(x) for x in r[1:]])
    meta = {"symbol": a.symbol, "period_min": int(a.period), "rows": len(rows),
            "first": rows[0][0], "last": rows[-1][0],
            "source": "Sina InnerFuturesNewService.getFewMinLine",
            "sha256": netlib.file_sha256(a.out)}
    with open(os.path.splitext(a.out)[0] + ".meta.json", "w", encoding="utf-8-sig") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
