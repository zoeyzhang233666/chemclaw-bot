# -*- coding: utf-8 -*-
"""Fetch 生意社(100ppi) 甲醇基准价 + 当日近月/远月期货价 —— 从每日「商品现货与期货价格对比表」页面解析。

页面: https://www.100ppi.com/sf/day-YYYY-MM-DD.html
行片段示例:  甲醇MA 2425.00&nbsp; 2209&nbsp; 2415&nbsp; 10 0.41% 2301&nbsp; 2412&nbsp; 13 0.54%

字段对应（口径见 references/03-数据源与口径.md）：现货基准价(元/吨) / 近月合约 / 近月价 /
近月基差 / 近月基差率 / 远月合约 / 远月价 / 远月基差 / 远月基差率。

注意：该页面本身即"现货 vs 期货"，只到今天。历史上任一交易日均可回取（PIT 可用）。

Usage:
  python fetch_100ppi_sf.py --start 2022-04-01 --end 2026-10-20 --out data/100ppi_sf.csv
"""
import argparse
import csv
import datetime as dt
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlib  # noqa: E402

CELL = r'<td>\s*(-?(?:[\d.]+)?)\s*(?:&nbsp;)?\s*</td>'
NUM = r'<font[^>]*>\s*(-?[\d.]+%?)\s*</font>'
ROW = re.compile(
    r'>\s*甲醇MA\s*</a>\s*</td>\s*' + CELL + r'\s*' + CELL + r'\s*' + CELL + r'\s*'
    + r'<td>.*?' + NUM + r'.*?' + NUM + r'.*?</td>\s*' + CELL + r'\s*' + CELL + r'\s*'
    + r'<td>.*?' + NUM + r'.*?' + NUM, re.S)
URL = "https://www.100ppi.com/sf/day-{d}.html"

FIELDS = ["date", "spot", "near_code", "near_fut", "near_basis", "near_basis_rate",
          "far_code", "far_fut", "far_basis", "far_basis_rate", "source_url", "page_sha"]


def _pct(s):
    return None if s in (None, "", "-") else float(str(s).rstrip("%"))


def parse_day(text):
    m = ROW.search(text)
    if not m:
        return None
    g = [x.strip() if x else x for x in m.groups()]
    try:
        return {
            "spot": float(g[0]),
            "near_code": "MA" + g[1] if len(g[1]) == 4 else None,
            "near_fut": float(g[2]) if g[2] else None,
            "near_basis": float(g[3]) if g[3] else None,
            "near_basis_rate": _pct(g[4]),
            "far_code": "MA" + g[5] if len(g[5] or "") == 4 else None,
            "far_fut": float(g[6]) if g[6] else None,
            "far_basis": float(g[7]) if g[7] else None,
            "far_basis_rate": _pct(g[8]),
        }
    except (TypeError, ValueError, IndexError):
        return None


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default="data/100ppi_sf.csv")
    ap.add_argument("--manifest", default="data/100ppi_sf_manifest.json")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    have = {}
    if a.resume and os.path.exists(a.out):
        with open(a.out, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                have[r["date"]] = r
        print(f"resume: {len(have)} days already stored")

    days = [d for d in daterange(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
            if d.isoformat() not in have]
    print(f"to fetch: {len(days)} candidate days", flush=True)

    from concurrent.futures import ThreadPoolExecutor, as_completed
    manifest = []
    rows = []
    done = 0

    def work(d):
        u = URL.format(d=d.isoformat())
        try:
            text = netlib.fetch(u, referer="https://www.100ppi.com/sf/", retries=2, timeout=25)
        except Exception as e:  # noqa: BLE001
            return d.isoformat(), None, str(e)
        rec = parse_day(text)
        m = re.search(r'/sf/day-[^"]+\.html', u)
        return d.isoformat(), rec, None

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(work, d): d for d in days}
        for fu in as_completed(futs):
            dstr, rec, err = fu.result()
            done += 1
            if rec:
                rec["date"] = dstr
                rec["source_url"] = URL.format(d=dstr)
                rows.append(rec)
            elif err:
                print(f"  [skip] {dstr}: {err[:60]}")
            if done % 100 == 0:
                print(f"  {done}/{len(days)} processed, {len(rows)} parsed", flush=True)

    rows.sort(key=lambda x: x["date"])
    allrows = list(have.values()) + [
        {k: (v if v is not None else "") for k, v in r.items()} for r in rows]
    allrows.sort(key=lambda x: x["date"])
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in allrows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    netlib.save_manifest(a.manifest, manifest)
    print(f"written {a.out}: {len(allrows)} trading days  "
          f"{allrows[0]['date']} ~ {allrows[-1]['date']}")
    print("sha256 ->", netlib.file_sha256(a.out))


if __name__ == "__main__":
    main()
