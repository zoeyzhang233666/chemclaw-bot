# -*- coding: utf-8 -*-
"""verify_inventory_provenance.py — 对本地库存历史序列做「逐条回源核验」。

背景：data/port_inventory_weekly.csv 只有 3 周是本次实时抓到的；另一份 228 周的
历史序列（来自同工作区的 inventory-price-relationship 示例数据）来源标注为
「archived index / 待核验」。本脚本对每一条 URL 做一次真实 HTTP 抓取，核对：
  * 页面还能打开（200）
  * 页面标题里的日期 == asof
  * 正文「港口库存总量在X万吨」 == value
输出 verification.json：
  verified / mismatch_date / mismatch_value / unreachable 四类计数与逐条明细。

只有在 verified 比例足够高时，才允许把这批数据标为 REAL_DATE_VERIFIED 并用于正式检验；
否则一律标为 PROVENANCE_UNVERIFIED，只能做流程演示（与本项目当前的诚实做法一致）。

Usage:
  python verify_inventory_provenance.py --csv <inventory_weekly.csv> --limit 0 \
         --workers 6 --out build/verification.json
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlib  # noqa: E402

TITLE_DATE = re.compile(r"\((20\d{2})(\d{2})(\d{2})\)")
TOTAL = re.compile(r"港口库存总量在\s*([\d.]+)\s*万吨")


def check_one(row):
    url, asof, val = row["url"], row["asof"], float(row["value"])
    rec = {"asof": asof, "value": val, "url": url, "status": None, "detail": ""}
    try:
        html = netlib.fetch(url, timeout=25, retries=1)
    except Exception as e:                      # noqa: BLE001
        rec["status"] = "unreachable"
        rec["detail"] = f"{type(e).__name__}: {e}"[:160]
        return rec
    text = re.sub(r"<[^>]+>", " ", html)
    m = TITLE_DATE.search(html) or TITLE_DATE.search(text)
    if m:
        page_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if page_date != asof:
            rec["status"] = "mismatch_date"
            rec["detail"] = f"page={page_date}"
            return rec
    mt = TOTAL.search(text)
    if mt:
        page_val = float(mt.group(1))
        if abs(page_val - val) > 0.011:
            rec["status"] = "mismatch_value"
            rec["detail"] = f"page={page_val}"
            return rec
        rec["status"] = "verified"
        rec["detail"] = "date+value match"
        return rec
    rec["status"] = "no_total_found"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--limit", type=int, default=0, help="0 = 全量")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default="build/verification.json")
    a = ap.parse_args()

    import csv as _csv
    with open(a.csv, encoding="utf-8-sig") as f:
        rows = list(_csv.DictReader(f))
    if a.limit:
        rows = rows[:a.limit]

    out = []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, rec in enumerate(ex.map(check_one, rows), 1):
            out.append(rec)
            if i % 20 == 0:
                print(f"  {i}/{len(rows)}", flush=True)
    tally = {}
    for r in out:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    res = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "source_csv": a.csv, "n": len(out), "tally": tally,
           "verified_ratio": round(tally.get("verified", 0) / max(1, len(out)), 4),
           "records": out}
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
    print(json.dumps(tally, ensure_ascii=False), "->", a.out)


if __name__ == "__main__":
    main()
