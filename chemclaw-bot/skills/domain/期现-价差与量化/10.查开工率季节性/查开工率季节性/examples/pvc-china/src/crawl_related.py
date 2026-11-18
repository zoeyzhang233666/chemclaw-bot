# -*- coding: utf-8 -*-
"""
抓取 mysteel PVC 周度速讯站内推荐位（相关文章 / 最新数据）中的历史链接：
从已知当期文章出发，沿“相关文章”列表做广度爬取，收集历史各周的
“[产能利用率]：中国PVC企业产能利用率周数据统计(YYYYMMDD）”文章 id。

mysteel 文章 id 由 16 位十六进制随机串构成、与日期无关，无法推算；
站内相关文章列表是少数不依赖搜索引擎/会员的历史入口。
"""
import argparse
import csv
import re
import sys
import time
import urllib.error
import urllib.request
from collections import deque

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
           "Referer": "https://www.mysteel.com/oilchem/pvc/"}
SEEDS = [
    "https://www.mysteel.com/oilchem/a/26101608/87AD42ED0F95C49B.html",
    "https://www.mysteel.com/oilchem/a/26100817/5749DD2FBDF426C0.html",
    "https://www.mysteel.com/oilchem/a/26100115/739E6FECE3C9CEC4.html",
    "https://www.mysteel.com/oilchem/a/26092418/6B5932167BE55491.html",
    "https://www.mysteel.com/oilchem/a/26091809/B1C2050F8AFBF228.html",
    "https://www.mysteel.com/oilchem/a/26091109/4A3C5544CB6261C6.html",
    "https://www.mysteel.com/oilchem/a/26090409/F1F67482897E2712.html",
    "https://www.mysteel.com/oilchem/a/26082808/7DEF91BDDCB6835A.html",
    "https://www.mysteel.com/oilchem/a/26082108/C26D3A0FB2A7580A.html",
    "https://www.mysteel.com/oilchem/a/26101609/BDD78E2EAA035E39.html",
]
ART = re.compile(r'(?:https?:)?//(?:www|nenghua)\.mysteel\.com/oilchem/a/(\d{8})/([A-F0-9]{16})\.html')


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../raw/oilchem_history_ids.csv")
    ap.add_argument("--max", type=int, default=400, help="最多抓取的页面数")
    ap.add_argument("--sleep", type=float, default=0.5)
    a = ap.parse_args()
    seen, util, queue = set(), {}, deque()
    for u in SEEDS:
        queue.append(u)
    fetched = 0
    while queue and fetched < a.max:
        u = queue.popleft()
        if u in seen:
            continue
        seen.add(u)
        try:
            h = get(u)
        except Exception:  # noqa: BLE001
            continue
        fetched += 1
        # 本页标题是否为目标系列
        t = re.search(r'<title>(.*?)</title>', h, re.S)
        title = re.sub(r'\s+', ' ', t.group(1)) if t else ''
        m = re.search(r'中国PVC企业产能利用率周数据统计\((\d{8})', title)
        if m:
            util[u] = (m.group(1), title)
        for nd8, nah in ART.findall(h):
            nu = f'https://www.mysteel.com/oilchem/a/{nd8}/{nah}.html'
            if nu not in seen:
                queue.append(nu)
        if fetched % 25 == 0:
            print(f"fetched={fetched} queue={len(queue)} util_hits={len(util)}")
        time.sleep(a.sleep)
    with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['week_end', 'url', 'title'])
        for u, (d8, title) in sorted(util.items(), key=lambda x: x[1][0], reverse=True):
            w.writerow([d8, u, title])
    print('fetched pages', fetched, 'util articles', len(util), '->', a.out)


if __name__ == '__main__':
    sys.exit(main())
