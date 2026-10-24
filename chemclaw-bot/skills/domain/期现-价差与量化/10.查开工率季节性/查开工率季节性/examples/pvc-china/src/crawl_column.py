# -*- coding: utf-8 -*-
"""
从 mysteel “生产”数据栏目分页（/oilchem/article/fxalqb/index_N.html）枚举
“中国PVC企业产能利用率周数据统计”速讯的文章 id。

文章 id 与日期无关、不可推算，只能通过栏目页存在的历史分页枚举。
只抓公开列表页，不绕过任何登录或验证。
"""
import argparse
import csv
import re
import sys
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
           "Referer": "https://www.mysteel.com/oilchem/pvczq/"}
BASE = "https://www.mysteel.com/oilchem/article/fxalqb/index_{n}.html"
ART = re.compile(
    r'href="(?:https?:)?//www\.mysteel\.com/oilchem/a/(\d{8})/([A-F0-9]+)\.html"[^>]*title="([^"]*)"')


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../ids_found.csv")
    ap.add_argument("--max-pages", type=int, default=400)
    ap.add_argument("--sleep", type=float, default=0.35)
    a = ap.parse_args()
    found = {}
    empty_streak = 0
    for n in range(1, a.max_pages + 1):
        url = BASE.format(n=n)
        try:
            h = get(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"page {n}: 404 -> stop")
                break
            print(f"page {n}: HTTP {e.code}")
            time.sleep(2)
            continue
        except Exception as e:  # noqa: BLE001
            print(f"page {n}: ERR {e!r}")
            time.sleep(2)
            continue
        if len(h) < 20000:
            print(f"page {n}: blocked/short ({len(h)}) -> stop")
            break
        hits = 0
        for d8, aid, title in ART.findall(h):
            if "中国PVC企业产能利用率周数据统计" in title:
                found.setdefault(aid, (d8, aid, title))
                hits += 1
        if n % 10 == 0 or hits:
            print(f"page {n}: hits={hits} total={len(found)}")
        empty_streak = empty_streak + 1 if hits == 0 else 0
        if empty_streak >= 60:
            print("60 consecutive pages with no hit -> stop")
            break
        time.sleep(a.sleep)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["d8", "aid", "title"])
        for d8, aid, title in sorted(found.values(), key=lambda x: x[0], reverse=True):
            w.writerow([d8, aid, title])
    print("wrote", a.out, len(found))


if __name__ == "__main__":
    sys.exit(main())
