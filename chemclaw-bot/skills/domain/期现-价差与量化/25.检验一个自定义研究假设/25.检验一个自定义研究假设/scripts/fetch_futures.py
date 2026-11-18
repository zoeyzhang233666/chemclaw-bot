# -*- coding: utf-8 -*-
"""Fetch daily futures k-lines (Sina public JSONP endpoint).

  * MA0      = 主力连续（未复权）——交割日切换，合约价格不连续
  * MA-near  = 真实近月合约（由调用方给出符号，如 MA2601），用于合成
               无跳空换月序列（back-adjusted），避免主力切换制造的假基差跳变。

Usage:
  python fetch_futures.py --symbols MA0 MA2601 MA2605 MA2609 MA2610 MA2701 --out data/futures
"""
import argparse
import csv
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlib  # noqa: E402

PAT = re.compile(r'"d":"(\d{4}-\d\d-\d\d)","o":"([\d.]+)","h":"([\d.]+)","l":"([\d.]+)",'
                 r'"c":"([\d.]+)","v":"([\d.]+)","p":"([\d.]+)","s":"([\d.]+)"')
URL = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{s}=/"
       "InnerFuturesNewService.getDailyKLine?symbol={s}")


def fetch_symbol(sym, manifest):
    text = netlib.fetch(URL.format(s=sym), referer="https://finance.sina.com.cn/",
                        manifest=manifest, tag="futures:" + sym)
    rows = PAT.findall(text)
    if not rows:
        raise RuntimeError(f"{sym}: no rows parsed (interface changed?)")
    out = []
    for r in rows:
        out.append({
            "date": r[0], "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
            "close": float(r[4]), "volume": float(r[5]), "open_interest": float(r[6]),
            "settle": float(r[7]),
        })
    out.sort(key=lambda x: x["date"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["MA0"])
    ap.add_argument("--out", default="data/futures")
    ap.add_argument("--manifest", default="data/futures/_manifest.json")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    manifest = []
    summary = {}
    for sym in a.symbols:
        try:
            rows = fetch_symbol(sym, manifest)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {sym}: {e}")
            continue
        path = os.path.join(a.out, f"{sym}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        summary[sym] = {"rows": len(rows), "first": rows[0]["date"], "last": rows[-1]["date"],
                        "sha256": netlib.file_sha256(path)}
        print(f"[OK] {sym}: {len(rows)} rows  {rows[0]['date']} ~ {rows[-1]['date']}")
        time.sleep(0.35)
    netlib.save_manifest(a.manifest, manifest)
    with open(os.path.join(a.out, "_summary.json"), "w", encoding="utf-8-sig") as f:
        json.dump({"source": "Sina InnerFuturesNewService.getDailyKLine", "symbols": summary},
                  f, ensure_ascii=False, indent=1)
    print("manifest ->", a.manifest)


if __name__ == "__main__":
    main()
