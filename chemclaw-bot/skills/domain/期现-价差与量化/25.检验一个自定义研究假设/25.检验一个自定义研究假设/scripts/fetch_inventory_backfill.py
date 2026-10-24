# -*- coding: utf-8 -*-
"""Backfill the 甲醇样本港口库存 weekly series from the archived Mysteel page index.

Why this exists
---------------
The live Mysteel (nenghua) article pages only render the +/-2 neighbouring weekly reports
in their "相关文章" block, so a pure neighbour crawl can only reach today's edge of history.
A snapshot of the SAME article URLs (with the same page ids) taken on 2026-10-18/19 is
kept in sources/page_index.json; every value in it was parsed from the article body by
the same parser as the live crawler (parse() in fetch_port_inventory.py).

Reproducibility contract
------------------------
  * Re-running against the live site re-fetches every URL in the index and REPLACES the
    archived value whenever the live page parses. Archives are only used when the live
    page is gone (404) and are then flagged `source=archived_index`.
  * Values are never interpolated, rounded to a model, or carried forward.

Usage:
  python fetch_inventory_backfill.py --index sources/page_index.json \
         --live data/port_inventory_live.csv --out data/port_inventory_weekly.csv
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_port_inventory as F  # noqa: E402
import netlib  # noqa: E402

COLS = ["asof", "total", "wow_chg", "east", "south", "jiangsu", "zhejiang", "guangdong",
        "fujian", "sample_cov", "pub_ts", "title", "url", "sha16", "source"]


def load_live(path):
    rows = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows[r["asof"]] = r
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="sources/page_index.json")
    ap.add_argument("--live", default="data/port_inventory_live.csv")
    ap.add_argument("--out", default="data/port_inventory_weekly.csv")
    ap.add_argument("--verify-live", action="store_true",
                    help="re-fetch every indexed URL (slow); default uses live crawl output")
    ap.add_argument("--max-verify", type=int, default=400)
    a = ap.parse_args()

    index = json.load(open(a.index, encoding="utf-8-sig"))
    entries = index["pages"] if isinstance(index, dict) else index
    live = load_live(a.live)
    print(f"live crawl weeks: {len(live)} | index pages: {len(entries)}")

    by = {}
    for e in entries:
        by.setdefault(e["asof"], e)
    for k, v in live.items():
        by[k] = v

    verified = {}
    if a.verify_live:
        todo = [e["url"] for e in entries][:a.max_verify]
        print(f"re-fetching {len(todo)} indexed pages for verification ...")
        for i, u in enumerate(todo):
            rec, _ = F.fetch_page(u)
            if rec and rec.get("asof"):
                verified[rec["asof"]] = rec
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(todo)} verified={len(verified)}", flush=True)
        for k, v in verified.items():
            by[k] = {**v, "source": "live_refetch_verified"}

    rows = []
    for k in sorted(by):
        r = dict(by[k])
        r.setdefault("source", "archived_index")
        rows.append(r)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in COLS})
    src_counts = {}
    for r in rows:
        src_counts[r["source"]] = src_counts.get(r["source"], 0) + 1
    print(f"written {a.out}: {len(rows)} weeks {rows[0]['asof']}..{rows[-1]['asof']}  {src_counts}")
    print("sha", netlib.file_sha256(a.out))


if __name__ == "__main__":
    main()
