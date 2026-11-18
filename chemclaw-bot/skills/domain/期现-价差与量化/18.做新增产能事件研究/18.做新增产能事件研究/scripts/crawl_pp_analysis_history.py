# -*- coding: utf-8 -*-
"""
crawl_pp_analysis_history.py — 抓取生意社 PP 月度/半月经评文章（含库存、开工率、价格）

锚点校准
--------
  2026-10-20 -> id 6368701
  2026-04-09 -> id 5507768
  => 2026 年 ID 增长速度 ≈ (6368701-5507768)/194 ≈ 4438 id/日（全站）

策略
----
1. 用线性模型估算目标日期的 ID。
2. 在估算值附近做**有界窗口扫描**（±W），逐个探测 detail-{ymd}-{id}.html。
3. 只保留标题含 PP/聚丙烯 且正文含库存/开工率关键词的文章。
4. 无 404 与日期不符时自动调整窗口。

产出
----
data/raw/news/*.txt 及 data/raw/pp_news_index.csv
"""
import csv
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crawl_100ppi_par as P  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS = os.path.join(BASE, "data", "raw", "news")
IDX = os.path.join(BASE, "data", "raw", "pp_news_index.csv")
DT = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*\d{1,2}:\d{2}")
TAG = re.compile(r"<title>([^<]+)</title>")
BLOCK = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S)

# 锚点（**forecast 分析评论区**的 ID 空间，与 news 区不同）
#   2026-10-01 -> 207868   （生意社：成本波动&供应收紧 9月PP冲高整理）
#   2025-10-29 -> 201034   （生意社：供需格局 PP十月震荡整理）
ANCH = [(date(2026, 10, 1), 207868), (date(2025, 10, 29), 201034)]
RATE = (ANCH[0][1] - ANCH[1][1]) / (ANCH[0][0] - ANCH[1][0]).days  # ≈20.3 篇/日


def est_id(d):
    return int(ANCH[0][1] - (ANCH[0][0] - d).days * RATE)


def strip_html(h):
    t = BLOCK.sub(" ", h)
    for a, b in (("&nbsp;", " "), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


KW = ("库存", "开工率", "负荷", "产量", "拉丝")


def probe(ymd, nid):
    url = "https://www.100ppi.com/forecast/detail-%s-%d.html" % (ymd, nid)
    h = P.fetch(url)
    if not h:
        return None
    m = DT.search(h)
    if not m:
        return None
    d = "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    if d != "%s-%s-%s" % (ymd[:4], ymd[4:6], ymd[6:]):
        return None
    t = TAG.search(h)
    ttl = t.group(1).strip() if t else ""
    body = strip_html(h)
    return {"date": d, "id": nid, "title": ttl, "url": url, "body": body}


def run(target_dates, window=80, workers=16):
    os.makedirs(NEWS, exist_ok=True)
    idx = {}
    if os.path.exists(IDX):
        with open(IDX, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                idx[r["id"]] = r
    got = 0
    for d in target_dates:
        ymd = d.strftime("%Y%m%d")
        center = est_id(d)
        hits = []
        # 自适应窗口：从 ±window 试到 ±8*window
        for mult in (1, 3, 8):
            w = window * mult
            cands = list(range(center + w, center - w, -2))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                res = list(ex.map(lambda n: probe(ymd, n), cands))
            hits = [r for r in res if r]
            if len(hits) >= 3:
                break
        nshop = 0
        for r in hits:
            if r["id"] in idx:
                continue
            relevant = ("PP" in r["title"] or "聚丙烯" in r["title"]) and any(k in r["body"] for k in KW)
            fn = os.path.join(NEWS, "%s_%s.txt" % (ymd, r["id"]))
            if relevant:
                with open(fn, "w", encoding="utf-8") as f:
                    f.write("TITLE: %s\nURL: %s\nDATE: %s\n\n%s" % (r["title"], r["url"], r["date"], r["body"]))
                nshop += 1
            idx[r["id"]] = {"id": r["id"], "date": r["date"], "title": r["title"],
                            "url": r["url"], "file": os.path.basename(fn) if relevant else "",
                            "relevant": "1" if relevant else "0", "chars": len(r["body"])}
        got += nshop
        print("%s est=%d hits=%d kept=%d cum_kept=%d" % (d, center, len(hits), nshop, got), flush=True)
        with open(IDX, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["id", "date", "title", "url", "file", "relevant", "chars"])
            w.writeheader()
            for k in sorted(idx):
                w.writerow(idx[k])


def month_starts(y0, m0, y1, m1, step=1):
    out = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(date(y, m, 1))
        m += step
        while m > 12:
            m -= 12
            y += 1
    return out


if __name__ == "__main__":
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    dates = month_starts(y0, 1, 2026, 10, 1)
    # 每月 1 日 + 15 日
    dates = sorted(set(dates) | {date(d.year, d.month, 15) for d in dates})
    run(dates)
