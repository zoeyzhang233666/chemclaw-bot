# -*- coding: utf-8 -*-
"""
crawl_100ppi_par.py — 多线程抓取生意社基准价列表（PP 拉丝/纤维/注塑），可断点续抓。

列表 URL: https://www.100ppi.com/news/list-15-1217-{page}.html
每页 50 条，覆盖约 1.6 天，标题形如 "10月20日生意社PP(拉丝)基准价为10756.67元/吨"

输出 data/raw/pp_spot_bench_100ppi.csv
"""
import csv
import os
import re
import ssl
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "raw", "pp_spot_bench_100ppi.csv")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
PAT = re.compile(r"(\d{1,2})月(\d{1,2})日生意社PP\((拉丝|纤维|注塑)\)基准价为([\d,\.]+)元/吨")
ENTRY = re.compile(
    r'/news/detail-(\d{8})-(\d+)\.html"[^>]*>([^<]{0,120})</a>')


def fetch(url, tries=3):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9", "Connection": "close"})
            return urllib.request.urlopen(req, timeout=25, context=CTX).read().decode("utf-8", "ignore")
        except Exception:
            continue
    return ""


def parse_page(p):
    h = fetch("https://www.100ppi.com/news/list-15-1217-%d.html" % p)
    if not h:
        return p, []
    out = []
    for m in ENTRY.finditer(h):
        ymd, nid, title = m.group(1), m.group(2), m.group(3).strip()
        pm = PAT.search(title)
        if not pm:
            continue
        d = "%s-%02d-%02d" % (ymd[:4], int(pm.group(1)), int(pm.group(2)))
        out.append({
            "date": d, "spec": pm.group(3),
            "price": float(pm.group(4).replace(",", "")),
            "title": title,
            "url": "https://www.100ppi.com/news/detail-%s-%s.html" % (ymd, nid),
            "list_page": p,
        })
    return p, out


def load():
    rows = {}
    if os.path.exists(OUT):
        with open(OUT, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows[(r["date"], r["spec"])] = r
    return rows


def save(rows):
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["date", "spec", "price", "title", "url", "list_page"])
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])


def main(start, end, workers=10):
    rows = load()
    print("existing", len(rows), flush=True)
    done_pages = set()
    for v in rows.values():
        try:
            done_pages.add(int(float(v.get("list_page") or 0)))
        except Exception:
            pass
    todo = [p for p in range(start, end + 1) if p not in done_pages]
    print("todo pages", len(todo), flush=True)
    empty_streak = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, (p, items) in enumerate(ex.map(parse_page, todo), 1):
            if not items:
                empty_streak += 1
            else:
                empty_streak = 0
            for it in items:
                k = (it["date"], it["spec"])
                if k not in rows or rows[k].get("list_page") in ("", None):
                    rows[k] = it
            if i % 50 == 0:
                ds = sorted(r["date"] for r in rows.values())
                print("page %5d/%d rows=%5d span=%s..%s" %
                      (p, end, len(rows), ds[0], ds[-1]), flush=True)
                save(rows)
            if empty_streak >= 40:
                print("stopping: 40 consecutive empty pages at", p, flush=True)
                break
    save(rows)
    ds = sorted(r["date"] for r in rows.values())
    print("DONE rows=%d span=%s..%s" % (len(rows), ds[0], ds[-1]), flush=True)


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    main(a, b)
