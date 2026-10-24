# -*- coding: utf-8 -*-
"""爬取隆众资讯(list.oilchem.net) PVC“生产”栏目分页，收集“产能利用率周数据统计”系列文章链接。

公开列表页可直接访问；文章正文对非会员部分可见（会员正文隐藏），
因此本脚本只负责**定位链接**，是否可用由正文解析脚本判断并记录。

URL 形态：https://www.oilchem.net/{YY}-{MMDD}-{HH}-{16位hex}.html
列表页：https://list.oilchem.net/381/38021/{page}.html
"""
import argparse
import csv
import re
import sys
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
           "Referer": "https://ca.oilchem.net/chlor-alkali/pvc.shtml"}
LIST = "https://list.oilchem.net/381/38021/{p}.html"
LINK = re.compile(r'<a\s+href="(https://www\.oilchem\.net/(\d{2})-(\d{4})-(\d{2})-([0-9a-f]{16})\.html)"'
                  r'[^>]*>(.*?)</a>', re.S)


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../raw/oilchem_ids.csv")
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--min-year", type=int, default=21)
    a = ap.parse_args()
    found = {}
    for p in range(1, a.max_pages + 1):
        url = LIST.format(p=p) if p > 1 else LIST.format(p=1)
        try:
            h = get(url)
        except Exception as e:  # noqa: BLE001
            print(f"page {p}: ERR {e!r}")
            time.sleep(2)
            continue
        hits, oldest = 0, None
        for full, yy, mmdd, hh, hx, title in LINK.findall(h):
            title = re.sub(r'<[^>]+>', '', title).strip()
            if int(yy) < a.min_year:
                continue
            oldest = f"{yy}-{mmdd}"
            if "产能利用率" in title and "PVC" in title and "周数据统计" in title:
                found.setdefault(hx, (yy, mmdd, hh, hx, title, full))
                hits += 1
        print(f"page {p}: hits={hits} total={len(found)} oldest={oldest}")
        if oldest and int(oldest[:2]) < a.min_year:
            break
        time.sleep(a.sleep)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["yy", "mmdd", "hh", "hash16", "title", "url"])
        for r in sorted(found.values(), key=lambda x: (x[0], x[1]), reverse=True):
            w.writerow(r)
    print("wrote", a.out, len(found))


if __name__ == "__main__":
    sys.exit(main())
