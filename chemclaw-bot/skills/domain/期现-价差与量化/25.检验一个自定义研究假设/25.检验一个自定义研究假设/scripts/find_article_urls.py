# -*- coding: utf-8 -*-
"""Web-search based URL finder for Mysteel 甲醇港口库存 weekly articles.

Why: Mysteel's mobile channel has NO pagination endpoint reachable without login, and
the "related articles" block only links ±2 weeks. Search engines keep indexes of the
older ones. This module queries several keyless engines, extracts every
nenghua.m.mysteel.com article URL, and lets fetch_port_inventory.py verify the content
itself (title must be 「[港口库存] 中国甲醇样本港口库存周数据统计(YYYYMMDD)」).

Usage:
  python find_article_urls.py --out data/article_urls.txt --extra-queries "..."
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlib  # noqa: E402

URLPAT = re.compile(r"https?://nenghua\.m\.mysteel\.com/a/\d{8,14}/[A-F0-9]{16}_abc\.html")
QUERIES = [
    '"中国甲醇样本港口库存周数据统计" 2022',
    '"中国甲醇样本港口库存周数据统计" 2023',
    '"中国甲醇样本港口库存周数据统计" 2024',
    '"中国甲醇样本港口库存周数据统计" 2025',
    '"中国甲醇样本港口库存周数据统计" 2026',
    'mysteel 甲醇港口库存 周数据 2023年5月',
    'mysteel 甲醇 港口库存 2024年3月 万吨',
    '我的钢铁 甲醇样本港口库存 2025年 周数据统计',
]


def engine_urls(q):
    import urllib.parse as up
    qq = up.quote(q)
    return [
        f"https://cn.bing.com/search?q={qq}&count=50",
        f"https://html.duckduckgo.com/html/?q={qq}",
        f"https://www.so.com/s?q={qq}&pn=1",
        f"https://www.sogou.com/web?query={qq}",
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/article_urls.txt")
    ap.add_argument("--extra-queries", nargs="*", default=[])
    a = ap.parse_args()
    found = set()
    for q in QUERIES + a.extra_queries:
        for u in engine_urls(q):
            try:
                t = netlib.fetch(u, retries=1, timeout=25)
            except Exception:  # noqa: BLE001
                continue
            for m in URLPAT.findall(t):
                found.add(m)
        print(f"{q[:36]:38s} -> total {len(found)}")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(sorted(found)))
    print("written", a.out, len(found))


if __name__ == "__main__":
    main()
