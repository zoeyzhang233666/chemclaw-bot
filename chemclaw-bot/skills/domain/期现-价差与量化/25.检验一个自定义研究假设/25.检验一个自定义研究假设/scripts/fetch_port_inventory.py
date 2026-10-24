# -*- coding: utf-8 -*-
"""Fetch 甲醇样本港口库存 weekly reports published by 隆众资讯 and republished by 我的钢铁网(能化频道).

Series: 「[港口库存] 中国甲醇样本港口库存周数据统计(YYYYMMDD)」

Discovery strategy (no paid API):
  * Every article page renders a "相关文章" block with the +/-2 neighbouring weekly
    reports. Crawl that neighbour chain in BOTH directions from any seed, skipping
    pages that are not the 港口库存 series.
  * Article ids encode YYYYMMDDHH, so older/newer direction is known without fetching.
  * The date recorded is the one PRINTED in the body ("截至YYYY年M月D日..."),
    never inferred from the id.

Output CSV columns:
  asof, total, wow_chg, east, south, jiangsu, zhejiang, guangdong, fujian, sample_cov,
  pub_ts, title, url, sha16
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

BASE = "https:"
LINK = re.compile(r"(//nenghua\.m\.mysteel\.com/a/(\d{8})\d{0,6}/([A-F0-9]{16})_abc\.html)")
TITLE = re.compile(r"中国甲醇样本港口库存周数据统计\(\s*(\d{8})\s*[）)]")
TOTAL = re.compile(r"截至\s*(\d{4})年(\d{1,2})月(\d{1,2})日[^。]{0,40}?港口库存总量(?:在|为)\s*([\d.]+)\s*万吨")
WOW = re.compile(r"(?:较(?:上一期|上期|上周|前一期)数据?|较上期|环比)(?!增加|减少|下降|上升|持稳|持平)"
                 r"(增加|减少|下降|上升|持稳|持平)?\s*([\d.]+)?\s*万吨")
SAMPLE = re.compile(r"样本覆盖率\s*([\d.]+)%")
REG_ROW = re.compile(
    r"<td[^>]*>\s*(?:<p[^>]*>)?\s*(?:<strong>)?\s*(?:<span[^>]*>)?\s*\**\s*"
    r"(江苏|浙江|华东总计|广东|福建|华南总计|港口总计)\s*\**\s*"
    r"(?:</span>)?\s*(?:</strong>)?\s*(?:</p>)?\s*</td>(.*?)</tr>", re.S)
CELL_NUM = re.compile(r"<td[^>]*>.*?<span[^>]*>\s*([+\-]?[\d.]+)\s*</span>", re.S)


def body_text(html):
    h = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S)
    m = re.search(r"正文(.*?)资讯编辑", h, re.S)
    seg = m.group(1) if m else h
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", seg)).replace("&nbsp;", "")


def parse(html, url):
    rec = {"url": url, "sha16": re.search(r"/([A-F0-9]{16})_abc", url).group(1)}
    t = re.search(r"<title>(.*?)</title>", html, re.S)
    rec["title"] = re.sub(r"\s+", " ", t.group(1)).strip() if t else ""
    ttl = TITLE.search(rec["title"])
    if not ttl:                       # not the 港口库存 weekly series
        return None
    rec["title_date"] = ttl.group(1)
    bt = body_text(html)
    m = TOTAL.search(bt)
    if not m:
        rec["parse_error"] = "no total"
        return rec
    rec["asof"] = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    rec["total"] = float(m.group(4))
    w = WOW.search(bt)
    if w:
        v = float(w.group(2)) if w.group(2) else 0.0
        rec["wow_chg"] = -v if w.group(1) in ("减少", "下降") else v
    s = SAMPLE.search(bt)
    rec["sample_cov"] = float(s.group(1)) if s else None
    keymap = {"江苏": "jiangsu", "浙江": "zhejiang", "华东总计": "east", "广东": "guangdong",
              "福建": "fujian", "华南总计": "south"}
    for lab, tail in REG_ROW.findall(html):
        vals = CELL_NUM.findall(tail)
        if vals and lab in keymap:
            rec[keymap[lab]] = float(vals[0])
        elif vals and lab == "港口总计":
            rec["total_table"] = float(vals[0])
    pt = re.search(r"(\d{4}-\d\d-\d\d\s+\d\d:\d\d)", html)
    rec["pub_ts"] = pt.group(1) if pt else ""
    return rec


def fetch_page(u):
    """Return (record|None, links) — record None means 'not this series'."""
    try:
        h = netlib.fetch(u, referer="https://m.mysteel.com/", retries=3, timeout=30)
    except Exception as e:  # noqa: BLE001
        return {"url": u, "err": str(e)[:80]}, []
    links = list(dict.fromkeys(BASE + m[0] for m in LINK.findall(h)))
    return parse(h, u), links


def idof(u):
    m = re.search(r"/a/(\d{8})", u)
    return m.group(1) if m else "99999999"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", default=[])
    ap.add_argument("--seed-file", default="")
    ap.add_argument("--probe-url", default="")
    ap.add_argument("--out", default="data/port_inventory_weekly.csv")
    ap.add_argument("--raw-json", default="data/port_inventory_raw.json")
    ap.add_argument("--max-pages", type=int, default=1200)
    ap.add_argument("--start-id", default="19900101", help="stop crawling older than this id")
    a = ap.parse_args()

    if a.probe_url:
        rec, links = fetch_page(a.probe_url)
        print(json.dumps(rec, ensure_ascii=False))
        print("links:", [l[-28:-5] for l in links])
        return

    records = {}
    if os.path.exists(a.raw_json):
        prev = json.load(open(a.raw_json, encoding="utf-8-sig"))
        prev = list(prev.values()) if isinstance(prev, dict) else prev
        for r in prev:
            if isinstance(r, dict) and r.get("url") and "err" not in r:
                records[r["url"]] = r
    seeds = list(a.seeds) + (a.extra if hasattr(a, "extra") else [])
    if a.seed_file and os.path.exists(a.seed_file):
        seeds += [l.strip() for l in open(a.seed_file, encoding="utf-8-sig") if l.strip()]

    queue = [s if s.startswith("http") else BASE + s for s in seeds]
    visited = set(records)
    pages = 0
    while queue and pages < a.max_pages:
        # breadth-first, newest first so "相关文章" duplicates resolve fast
        queue.sort(key=idof)
        u = queue.pop()
        if u in visited:
            continue
        visited.add(u)
        pages += 1
        rec, links = fetch_page(u)
        if rec and "err" not in rec:
            records[u] = rec
        # enqueue only weekly-series candidates and never below start-id
        for l in links:
            if l not in visited and idof(l) >= a.start_id.replace("-", ""):
                queue.append(l)
        if pages % 10 == 0:
            ok = sum(1 for v in records.values() if v.get("asof"))
            print(f"  pages={pages} queue={len(queue)} series_hit={ok}", flush=True)
        time.sleep(0.05)

    rows, by = [], {}
    for v in records.values():
        if v.get("asof"):
            by.setdefault(v["asof"], []).append(v)
    for k in sorted(by):
        by[k].sort(key=lambda x: x.get("pub_ts") or "9")
        rows.append(by[k][0])
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    cols = ["asof", "total", "wow_chg", "east", "south", "jiangsu", "zhejiang", "guangdong",
            "fujian", "sample_cov", "pub_ts", "title", "url", "sha16"]
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
    with open(a.raw_json, "w", encoding="utf-8-sig") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    print(f"pages visited={pages}; series weeks={len(rows)}; "
          f"range={rows[0]['asof'] if rows else '-'}..{rows[-1]['asof'] if rows else '-'}")
    print("written", a.out, "sha", netlib.file_sha256(a.out))


if __name__ == "__main__":
    main()
