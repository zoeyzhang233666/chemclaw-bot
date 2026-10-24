# -*- coding: utf-8 -*-
"""
抓取 mysteel.com（原文转载自隆众资讯）的 PVC 产能利用率周度速讯正文。

背景
----
www.oilchem.net（隆众源站）的 PVC 产能利用率正文需要会员登录，直接抓取得到的是
"注册为会员，可获得相关产品 15 天的免费浏览权" 的登录墙文本。
www.mysteel.com 会转载同一篇速讯、并免费放出正文前约 200 字，其中包含：
    本周PVC生产企业产能利用率在 X%，环比减少 a%，同比减少 b%；
    其中电石法在 Y%，环比 ±c%，同比 ±d%，乙烯法在 Z%，环比 ±e%，同比 ±f%
样本说明：产能利用率样本涵盖国内 71 家 PVC 生产企业及厂区，样本覆盖率…

因此本脚本以 "网页已公开的正文原文" 为唯一数据来源，逐篇抓取、逐篇留档 URL，
不做任何数值推断。解析失败的篇目一律进入缺口表，不填补。

用法
----
    python fetch_mysteel.py --ids ../ids.txt --out ../raw
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
HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.mysteel.com/oilchem/pvczq/",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

ART_URL = "https://www.mysteel.com/oilchem/a/{d8}/{aid}.html"

TITLE_RE = re.compile(r"中国PVC企业产能利用率周数据统计\s*[\(（]\s*(\d{8})\s*[\)）]")

NUM = r"([-+]?\d+(?:\.\d+)?)"
GAP = r"[^0-9]{0,6}"   # “环比减少 / 环比增加”等措辞，不含数字
RE_MAIN = re.compile(r"本周PVC生产企业产能利用率在\s*" + NUM + r"%")
RE_CHAIN = re.compile(
    r"电石法在\s*" + NUM + r"%[，,]\s*环比" + GAP + NUM +
    r"%[，,]\s*同比" + GAP + NUM + r"%[^0-9]{1,12}乙烯法在\s*" + NUM +
    r"%[，,]\s*环比" + GAP + NUM + r"%[，,]\s*同比" + GAP + NUM + "%")
RE_MAIN_C2C = re.compile(r"环比" + GAP + NUM + r"%[，,]\s*同比" + GAP + NUM + "%")
RE_SAMPLE = re.compile(r"样本涵盖国内\s*(\d+)\s*家PVC生产企业及厂区")
RE_CAPBASE = re.compile(r"全国PVC产能基数变更为\s*([\d.]+)\s*万吨/年")


def http_get(url, retries=3, timeout=30):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                raise
            time.sleep(1.5 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def body_text(html):
    i = html.find('id="article-content"')
    if i < 0:
        i = html.find('id="content-text"')
    if i < 0:
        return ""
    seg = html[i:i + 20000]
    j = seg.find('<div class="editor">')
    if j > 0:
        seg = seg[:j]
    seg = re.sub(r"<script[\s\S]*?</script>", " ", seg)
    seg = re.sub(r"<style[\s\S]*?</style>", " ", seg)
    seg = re.sub(r"<[^>]+>", " ", seg)
    seg = seg.replace("&nbsp;", " ").replace("&amp;", "&")
    seg = re.sub(r"\s+", " ", seg)
    seg = re.sub(r'^id="[^"]*">\s*', "", seg)
    return seg.strip()


def parse_article(html):
    title = ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    pub = ""
    m = re.search(r'class="content-info-text publish-time">\s*([0-9\-: ]+)', html)
    if m:
        pub = m.group(1).strip()
    txt = body_text(html)
    out = {"title": title, "publish": pub, "body": txt,
           "calc": None, "calc_c2c_pct": None, "calc_yoy_pct": None,
           "eth": None, "eth_c2c_pct": None, "eth_yoy_pct": None,
           "util": None, "util_c2c_pct": None, "util_yoy_pct": None,
           "sample_n": None, "cap_base_wt": None}
    m = RE_MAIN.search(txt)
    out["util"] = float(m.group(1)) if m else None
    m = RE_CHAIN.search(txt)
    if m:
        g = [float(x) for x in m.groups()]
        out.update(calc=g[0], calc_c2c_pct=g[1], calc_yoy_pct=g[2],
                   eth=g[3], eth_c2c_pct=g[4], eth_yoy_pct=g[5])
    m = RE_MAIN_C2C.search(txt)
    if m:
        out["util_c2c_pct"] = float(m.group(1))
        out["util_yoy_pct"] = float(m.group(2))
    m = RE_SAMPLE.search(txt)
    out["sample_n"] = int(m.group(1)) if m else None
    m = RE_CAPBASE.search(txt)
    out["cap_base_wt"] = float(m.group(1)) if m else None
    return out


def discover(aid, d8):
    aid = (aid or "").strip().strip("\ufeff\"' ").upper()
    url = ART_URL.format(d8=(d8 or "").strip(), aid=aid)
    try:
        html = http_get(url)
    except Exception as e:  # noqa: BLE001
        if os.environ.get("DEBUG_FETCH"):
            print("  [http]", url, repr(e))
        return None
    if "中国PVC企业产能利用率周数据统计" not in html:
        if os.environ.get("DEBUG_FETCH"):
            print("  [kw-miss]", url)
        return None
    rec = parse_article(html)
    m = TITLE_RE.search(rec["title"])
    if not m:
        if os.environ.get("DEBUG_FETCH"):
            print("  [title-miss]", repr(rec["title"]))
        return None
    rec["week_end"] = m.group(1)
    rec["url"] = url
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="文件：每行 id,d8")
    ap.add_argument("--out", default="../raw")
    ap.add_argument("--sleep", type=float, default=0.4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows, misses = [], []
    with open(a.ids, encoding="utf-8") as f:
        pairs = []
        for ln in f:
            ln = ln.strip().lstrip("\ufeff")
            if not ln:
                continue
            p = [x.strip() for x in ln.replace(" ", "").split(",")]
            if len(p) < 2:
                continue
            # 兼容两种写法：d8,aid  或  aid,d8
            if re.fullmatch(r"\d{8}", p[0]):
                pairs.append((p[1], p[0]))
            else:
                pairs.append((p[0], p[1]))
    for aid, d8 in pairs:
        rec = discover(aid.strip(), d8.strip())
        if rec:
            rows.append(rec)
            print("OK  ", rec["week_end"], rec["util"], "|", rec["calc"], rec["eth"], rec["url"])
        else:
            misses.append((aid, d8))
            print("MISS", aid, d8)
        time.sleep(a.sleep)
    if rows:
        keys = ["week_end", "publish", "util", "util_c2c_pct", "util_yoy_pct",
                "calc", "calc_c2c_pct", "calc_yoy_pct",
                "eth", "eth_c2c_pct", "eth_yoy_pct",
                "sample_n", "cap_base_wt", "title", "url", "body"]
        p = os.path.join(a.out, "mysteel_pvc_util_raw.csv")
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                r = dict(r)
                r["body"] = str(r.get("body", "")).replace(
                    'id="article-content">', "").replace('id="content-text">', "").strip()
                w.writerow(r)
        print("wrote", p, len(rows))
    print("misses:", len(misses))
    return 0


if __name__ == "__main__":
    sys.exit(main())
