# -*- coding: utf-8 -*-
"""
fetch_data.py —— 取数层：现货基准价 + 逐合约期货日线
========================================================
与统计层（basis_core.py）解耦：本脚本只负责「把原始数据抓到本地 raw/」，
并在 raw/_sources.json 里记录每个字段的来源 URL 与抓取时间，供报告引用。

三个数据源（全部公开、免登录）
------------------------------------------------
1) 100ppi 生意社 甲醇基准价（日度）
   - 列表页 https://me.100ppi.com/news/list--1217-{page}.html
   - 原标题形如「M月D日生意社甲醇基准价为X元/吨」，逐条保留文章 URL
   - 站点有 HW_CHECK 前端校验，直接用带该 cookie 的会话即可（无需 JS）
   - 口径：全国交易指导价（含税，元/吨），**不是**华东/太仓报价
   - 历史深度：实测约 2022-08 起（列表最多约 50 页 × 50 条）

2) 新浪财经 逐合约期货日线（郑商所 MA）
   - InnerFuturesNewService.getDailyKLine?symbol=MAYYMM
   - 字段 d,o,h,l,c,v,p(持仓量),s(结算价)
   - 历史深度：MA1905 起的合约可用（更早的合约返回 null）

3) 100ppi 甲醇「基差率」年度对比序列（主力基差率，用于交叉核验）
   - https://www.100ppi.com/graph/future.php?f=futures_date&ppid=817
   - 只用于校验我们的重建口径，不直接进入统计

用法
----
  python fetch_data.py --outdir raw
  python fetch_data.py --outdir raw --contracts MA1905:MA2712
  python fetch_data.py --outdir raw --skip-spot --skip-verify
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# 100ppi 前端的静态校验串（页面里 document.cookie = "HW_CHECK" + "=" + ...），不是账号凭据。
# Override with HW_CHECK_TOKEN when the site rotates the public check value.
HW_TOKEN = os.environ.get("HW_CHECK_TOKEN", "example-hw-check-token")

SINA_HOSTS = ["https://stock.finance.sina.com.cn", "https://stock2.finance.sina.com.cn"]
SPOT_LIST = "https://me.100ppi.com/news/list--1217-{page}.html"
BASIS_RATE_URL = "https://www.100ppi.com/graph/future.php?f=futures_date&ppid=817"


# ------------------------------------------------------------------ 现货
def ppi_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    for dom in ("www.100ppi.com", "me.100ppi.com", "graph.100ppi.com"):
        s.cookies.set("HW_CHECK", HW_TOKEN, domain=dom, path="/")
    s.get("https://www.100ppi.com/", timeout=25)  # 预热
    return s


SPOT_ROW = re.compile(
    r'detail-(\d{8})-(\d+)\.html"[^>]*>([^<]{4,160}?)</a>')
SPOT_VAL = re.compile(r'(\d{1,2})月(\d{1,2})日生意社甲醇基准价为([\d,]+\.?\d*)元/吨')


def fetch_spot(session: requests.Session, max_pages: int = 60, sleep: float = 0.45):
    """抓 100ppi 甲醇基准价日度序列，每行带原文 URL。缺失日不填补。"""
    rows: dict[str, dict] = {}
    page = 1
    stale = 0
    oldest = None
    while page <= max_pages:
        try:
            r = session.get(SPOT_LIST.format(page=page), timeout=30)
            r.encoding = "utf-8"
        except Exception as e:  # noqa: BLE001
            print("[WARN] list page %d failed: %r" % (page, e))
            break
        if len(r.text) < 2000:
            print("[WARN] list page %d returned challenge page (%d bytes), stop" % (page, len(r.text)))
            break
        # 每一页里的「日期 + 标题」对
        hits = SPOT_ROW.findall(r.text)
        new = 0
        page_min = None
        for ymd, art_id, title in hits:
            m = SPOT_VAL.search(title)
            if not m:
                continue
            date = "%s-%s-%s" % (ymd[:4], ymd[4:6], ymd[6:8])
            page_min = date if page_min is None else min(page_min, date)
            if date in rows:
                continue
            rows[date] = {
                "date": date,
                "price": float(m.group(3).replace(",", "")),
                "source_url": "https://www.100ppi.com/news/detail-%s-%s.html" % (ymd, art_id),
                "title": title.strip(),
            }
            new += 1
        if page_min:
            oldest = page_min if oldest is None else min(oldest, page_min)
            print("[SPOT] page %2d  new=%2d  page_min=%s  total=%4d"
                  % (page, new, page_min, len(rows)))
        stale = 0 if new else stale + 1
        if stale >= 3:
            break
        page += 1
        time.sleep(sleep)
    out = [rows[d] for d in sorted(rows)]
    return out


# ------------------------------------------------------------------ 期货
def month_iter(start: str, end: str):
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def fetch_contract(symbol: str, retries: int = 3):
    """单合约日线；返回 {symbol, rows:[{d,o,h,l,c,v,oi,settle}]} 或 None"""
    last_err = None
    for host in SINA_HOSTS:
        url = host + "/futures/api/jsonp.php/var%20t=/InnerFuturesNewService.getDailyKLine"
        for attempt in range(retries):
            try:
                r = requests.get(url, params={"symbol": symbol}, timeout=20,
                                 headers={"User-Agent": UA, "Referer": host + "/"})
                m = re.search(r"\((\[.*\])\)", r.text, re.S) or re.search(r"(\[\s*\{.*\}\s*\])", r.text, re.S)
                if not m:
                    raise RuntimeError("unparsable payload")
                data = json.loads(m.group(1))
                if not data:
                    return None
                rows = [{
                    "d": it["d"],
                    "o": float(it.get("o") or 0), "h": float(it.get("h") or 0),
                    "l": float(it.get("l") or 0), "c": float(it.get("c") or 0),
                    "v": float(it.get("v") or 0), "oi": float(it.get("p") or 0),
                    "settle": float(it.get("s") or 0),
                } for it in data]
                rows.sort(key=lambda x: x["d"])
                return {"symbol": symbol, "exchange": "CZCE", "rows": rows}
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(0.5 * (attempt + 1))
    print("  [FAIL] %s (%r)" % (symbol, last_err))
    return None


def fetch_futures(prefix: str, start: str, end: str, outdir: str, sleep: float = 0.25):
    os.makedirs(outdir, exist_ok=True)
    ok = empty = 0
    for y, m in month_iter(start, end):
        sym = "%s%02d%02d" % (prefix.upper(), y % 100, m)
        dst = os.path.join(outdir, "%s_%s.json" % (prefix.upper(), sym))
        if os.path.exists(dst) and os.path.getsize(dst) > 50:
            ok += 1
            continue
        d = fetch_contract(sym)
        if d:
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            print("[FUT] %s rows=%3d %s~%s" % (sym, len(d["rows"]), d["rows"][0]["d"], d["rows"][-1]["d"]))
            ok += 1
        else:
            empty += 1
        time.sleep(sleep)
    print("[FUT] done: ok=%d empty=%d" % (ok, empty))


# ------------------------------------------------------------------ 基差率核验样本
def fetch_basis_rate(session: requests.Session):
    """100ppi 主力基差率年度序列（只用于口径核验）。返回 {date: pct}"""
    r = session.get(BASIS_RATE_URL, timeout=40)
    r.encoding = "utf-8"
    t = r.text
    i = t.find("series:")
    if i < 0:
        return {}
    out = {}
    for year, blob in re.findall(r"name: '(\d{4})',\s*type: 'line',.*?data: \[(.*?)\]", t[i:], re.S):
        vals = [x.strip() for x in blob.split(",") if x.strip()]
        base = dt.date(int(year), 1, 1)
        for j, v in enumerate(vals):
            if v in ("null", "-", ""):
                continue
            out[(base + dt.timedelta(days=j)).isoformat()] = float(v)
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="甲醇期现基差研究取数层")
    ap.add_argument("--prefix", default="MA")
    ap.add_argument("--start", default="2019-01")
    ap.add_argument("--end", default="2027-12")
    ap.add_argument("--outdir", default="raw")
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--skip-spot", action="store_true")
    ap.add_argument("--skip-futures", action="store_true")
    ap.add_argument("--skip-verify", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    sess = ppi_session()
    sources = {}

    if not args.skip_spot:
        rows = fetch_spot(sess, max_pages=args.max_pages)
        dst = os.path.join(args.outdir, "spot_methanol_100ppi_benchmark.csv")
        with open(dst, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "price", "source_url", "title"])
            for r in rows:
                w.writerow([r["date"], "%.2f" % r["price"], r["source_url"], r["title"]])
        print("[OK] %s rows=%d %s -> %s" % (dst, len(rows), rows[0]["date"], rows[-1]["date"]))
        sources["spot"] = {
            "file": os.path.basename(dst), "rows": len(rows),
            "first": rows[0]["date"], "last": rows[-1]["date"],
            "source": SPOT_LIST.format(page="1..%d" % args.max_pages),
            "caliber": "生意社甲醇基准价（全国交易指导价，含税，元/吨）",
        }

    if not args.skip_futures:
        fetch_futures(args.prefix, args.start, args.end, args.outdir)
        sources["futures"] = {
            "dir": args.outdir, "api": SINA_HOSTS[0] + "/futures/api/jsonp.php/.../getDailyKLine",
            "fields": "d,o,h,l,c,v,p(持仓量),s(结算价)",
        }

    if not args.skip_verify:
        rate = fetch_basis_rate(sess)
        if rate:
            dst = os.path.join(args.outdir, "verify_100ppi_basis_rate.csv")
            with open(dst, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["date", "basis_rate_pct"])
                for d in sorted(rate):
                    w.writerow([d, rate[d]])
            print("[OK] %s rows=%d (口径核验用)" % (dst, len(rate)))
            sources["basis_rate_verify"] = {
                "file": os.path.basename(dst), "rows": len(rate), "source": BASIS_RATE_URL,
                "note": "主力基差率 = (现货-主力期货)/现货；只用于核验重建口径",
            }

    sources["fetched_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(args.outdir, "_sources.json"), "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)
    print("[OK] sources -> %s" % os.path.join(args.outdir, "_sources.json"))


if __name__ == "__main__":
    main()
