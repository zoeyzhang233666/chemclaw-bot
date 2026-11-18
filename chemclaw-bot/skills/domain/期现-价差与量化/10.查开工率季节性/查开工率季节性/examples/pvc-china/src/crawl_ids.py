# -*- coding: utf-8 -*-
"""
枚举 mysteel.com 的 PVC 页面 / 化工频道页面 以及 Wayback / 搜索引擎返回的历史链接，
收集“中国PVC企业产能利用率周数据统计”系列速讯的文章 id（文章 id 不可由日期推算，只能枚举）。

用法
----
    python crawl_ids.py --out ../ids_found.csv [--start YYYY-MM-DD] [--end YYYY-MM-DD]

产出
----
ids_found.csv : d8,aid,title,url （去重，按 week_end 降序）
"""
import argparse
import csv
import os
import re
import sys
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
           "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}

ENTRY_URLS = [
    "https://www.mysteel.com/oilchem/pvc/",
    "https://www.mysteel.com/oilchem/pvczq/",
    "https://www.mysteel.com/oilchem/pvc/zhcx/",
    "https://www.mysteel.com/oilchem/",
]
LINK_RE = re.compile(
    r'href="(https?://(?:www|nenghua)(?:\.m)?\.mysteel\.com/(?:oilchem|)/a/(\d{8})/([A-F0-9]+)(?:_abc)?\.html)"[^>]*title="([^"]*)"')


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def collect(html, found):
    n0 = len(found)
    for m in LINK_RE.finditer(html):
        url, d8, aid, title = m.groups()
        if "产能利用率" not in title or "PVC" not in title:
            continue
        if "中国PVC企业产能利用率周数据统计" not in title and "中国PVC产能利用率周数据" not in title:
            continue
        found[aid] = (d8, aid, title, url)
    return len(found) - n0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../ids_found.csv")
    a = ap.parse_args()
    found = {}
    for u in ENTRY_URLS:
        try:
            h = get(u)
            add = collect(h, found)
            print(f"entry {u}: +{add}  (total {len(found)})")
        except Exception as e:  # noqa: BLE001
            print(f"entry {u}: ERR {e!r}")
        time.sleep(0.5)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["d8", "aid", "title", "url"])
        for d8, aid, title, url in sorted(found.values(), key=lambda x: x[0], reverse=True):
            w.writerow([d8, aid, title, url])
    print("wrote", a.out, len(found))


if __name__ == "__main__":
    sys.exit(main())
