#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_prices.py — 公开价格序列抓取（可插拔数据源）

设计原则（与「不虚构价格」约束一致）：
  1. 只抓页面上公开可见的表格，不做登录绕过、不猜测私有接口。
  2. 每条序列记录 url / 抓取时间 / 点位口径 / 样本天数；样本不足标 partial。
  3. 抓不到的品种写入 gap 说明，**不填估算值**。
  4. 限速与失败退避（HTTP 451/403 常见于连续请求）。

用法：
    python fetch_prices.py --data-dir examples/sbs/data
    python fetch_prices.py --data-dir examples/sbs/data --only PR_ETH,PR_SM
    python fetch_prices.py --data-dir examples/sbs/data --dry-run

序列定义（data/price_series.json）：
{
  "series": [
    {"id": "PR_SM", "node_id": "N_SM", "product": "苯乙烯",
     "source": "oilchem_seo", "seo_id": "128",
     "basis": "全国主流市场均价", "region": "全国", "unit": "元/吨", "tax": "含税"}
  ]
}

支持的数据源（source 字段）：
  oilchem_seo   公开 SEO 点位页 https://www.oilchem.net/seo-<id>-7.html
  csv_url       任意 CSV（列：date,price[,chg,chg_rate]），用 url 字段指定
  其他          在 ADAPTERS 里注册你自己的抓取函数
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

MIN_INTERVAL = 8.0      # 同一站点两次请求的最小间隔（秒）
MAX_RETRY = 3
_last_hit = {}


def http_get(url, timeout=25):
    host = re.sub(r"^https?://([^/]+).*$", r"\1", url)
    gap = time.time() - _last_hit.get(host, 0.0)
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    last = None
    for attempt in range(MAX_RETRY):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                _last_hit[host] = time.time()
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            _last_hit[host] = time.time()
            last = e
            if e.code in (403, 429, 451) and attempt < MAX_RETRY - 1:
                time.sleep(60 * (attempt + 1))
                continue
            raise
        except Exception as e:  # noqa: BLE001
            _last_hit[host] = time.time()
            last = e
            if attempt < MAX_RETRY - 1:
                time.sleep(5)
                continue
            raise
    raise last if last else RuntimeError("unreachable")


def parse_oilchem_seo(html):
    """返回 (point_name, [{date, price, chg, chg_rate}...])，按日期倒序。"""
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        dm = next((re.match(r"^(\d{4}-\d{2}-\d{2})$", c) for c in cells
                   if re.match(r"^\d{4}-\d{2}-\d{2}$", c)), None)
        if not dm:
            continue
        nums = [c for c in cells if re.match(r"^-?[\d,]+(\.\d+)?%?$", c)]
        if not nums:
            continue
        price = nums[0].replace(",", "").rstrip("%")
        try:
            pv = float(price)
        except ValueError:
            continue
        if pv <= 0 or pv > 1e7:
            continue
        chg = nums[1].replace(",", "") if len(nums) > 1 else ""
        rate = nums[2].replace(",", "") if len(nums) > 2 else ""
        rows.append({"date": dm.group(1), "price": price, "chg": chg, "chg_rate": rate})

    seen, uniq = set(), []
    for r in rows:
        if r["date"] in seen:
            continue
        seen.add(r["date"])
        uniq.append(r)
    uniq.sort(key=lambda x: x["date"], reverse=True)
    point = re.split(r"[_|]", title)[0].strip() if title else ""
    return point, uniq


def parse_csv(text):
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        d = (row.get("date") or row.get("日期") or "").strip()
        p = (row.get("price") or row.get("价格") or "").strip()
        if not d or not p:
            continue
        rows.append({"date": d, "price": p.replace(",", ""),
                     "chg": (row.get("chg") or "").strip(),
                     "chg_rate": (row.get("chg_rate") or "").strip()})
    rows.sort(key=lambda x: x["date"], reverse=True)
    return "", rows


def fetch_oilchem_seo(series):
    sid = str(series.get("seo_id") or "").strip()
    if not sid:
        raise ValueError("缺少 seo_id")
    url = series.get("url") or "https://www.oilchem.net/seo-%s-7.html" % sid
    return url, *parse_oilchem_seo(http_get(url))


def fetch_csv_url(series):
    url = series.get("url")
    if not url:
        raise ValueError("缺少 url")
    return url, *parse_csv(http_get(url))


ADAPTERS = {
    "oilchem_seo": fetch_oilchem_seo,
    "csv_url": fetch_csv_url,
}


def build_series(defn, dry=False):
    src = defn.get("source") or "oilchem_seo"
    out = {
        "id": defn.get("id"), "node_id": defn.get("node_id"), "product": defn.get("product"),
        "source": src, "seo_id": defn.get("seo_id"),
        "basis": defn.get("basis"), "region": defn.get("region"),
        "unit": defn.get("unit"), "tax": defn.get("tax"),
        "available": False, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url": defn.get("url"), "point_name": defn.get("point_name"),
        "points": [], "gap": None, "status": None, "caveat": defn.get("caveat"),
    }
    fn = ADAPTERS.get(src)
    if fn is None:
        out["gap"] = "未注册的数据源：%s（可用：%s）" % (src, "、".join(ADAPTERS))
        out["status"] = "unsupported_source"
        return out
    if dry:
        out["status"] = "dry_run"
        return out
    try:
        url, point, rows = fn(defn)
        out["url"] = url
        if point:
            out["point_name"] = point
        if not rows:
            out["gap"] = "页面未解析到价格行（可能需登录、页面结构变更或点位已下线）"
            out["status"] = "no_rows"
            return out
        out["points"] = rows
        out["available"] = True
        out["status"] = "ok"
        if len(rows) < 10:
            out["caveat"] = "仅 %d 个样本点，不足以判断趋势（标记 partial）" % len(rows)
            out["status"] = "partial"
        return out
    except urllib.error.HTTPError as e:
        out["gap"] = "HTTP %s（触发反爬或页面不存在；请降低频率或换源）" % e.code
        out["status"] = "http_%s" % e.code
        return out
    except Exception as e:  # noqa: BLE001
        out["gap"] = "%s: %s" % (type(e).__name__, e)
        out["status"] = "error"
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    defs_path = os.path.join(args.data_dir, "price_series.json")
    if not os.path.exists(defs_path):
        print("找不到 %s（序列定义文件）" % defs_path)
        return 2
    doc = json.load(open(defs_path, encoding="utf-8"))
    defs = doc.get("series") or []
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        defs = [d for d in defs if d.get("id") in want]
    if not defs:
        print("没有匹配的序列定义。")
        return 2

    print("待抓序列：%d 条%s" % (len(defs), "（dry-run）" if args.dry_run else ""))
    out = []
    for i, d0 in enumerate(defs, 1):
        print("  [%d/%d] %-14s %s ..." % (i, len(defs), d0.get("id"), d0.get("product") or ""),
              end=" ", flush=True)
        r = build_series(d0, dry=args.dry_run)
        out.append(r)
        print(("OK %d 点" % len(r["points"])) if r["available"] else ("GAP（%s）" % r.get("status")))

    result = {
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "series": out,
        "note": "available=false 表示该序列是缺口而不是 0；gap 字段说明原因。",
    }
    dst = args.out or os.path.join(args.data_dir, "prices_verified.json")
    if args.dry_run:
        print("\n(dry-run 未写文件)")
    else:
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        ok = sum(1 for x in out if x["available"])
        print("\n写出 %s：%d/%d 条成功" % (dst, ok, len(out)))
        print("提示：抓取结果会覆盖同名文件；建议先备份为 prices_verified.YYYYMMDD.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
