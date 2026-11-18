# -*- coding: utf-8 -*-
"""Date-guided fetcher for a PVC-style weekly 开工率 bulletin series.

WHY DATE-GUIDED
---------------
The upstream site's listing/search endpoints are unreliable (anti-bot, expired tokens,
paged HTML that silently truncates). What IS stable is the article URL shape and the fact
that each bulletin states its own统计周期. So instead of crawling listings, we walk a list
of candidate dates, derive the article code pattern for each, and accept a page only when
the parsed body proves it is the right indicator and the right week.

DESIGN RULES
------------
1. Every fetch attempt is logged, including failures, into  gaps.json. A week we could not
   obtain must appear as an explicit gap -- never silently absent, never estimated.
2. Nothing is interpolated. If a week is missing, the factor is missing.
3. The parsed value is validated against the number quoted in the page body; a mismatch
   rejects the record rather than preferring one of the two.
4. Re-running is idempotent: existing good records are kept, only missing/!invalid ones are
   refetched.

USAGE
-----
    python scripts/fetch_utilization.py --site mysteel_oilchem --start 2026-09-01 \
        --end 2026-10-20 --out data/util_weekly.csv

    # investigate one week without writing anything
    python scripts/fetch_utilization.py --probe 2026-10-15
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

# --------------------------------------------------------------------------- site profiles
#
# A profile turns a week-ending date into candidate URLs and knows how to read a page.
# Add a profile per publisher; the rest of the pipeline is publisher-agnostic.

SITES = {
    "mysteel_oilchem": {
        "url_tpl": "https://www.mysteel.com/oilchem/a/{code}/{slug}.html",
        "note": (
            "隆众资讯 PVC 开工率周报，经 Mysteel 转载。URL 形如 "
            "https://www.mysteel.com/oilchem/a/26101608/4CFEE19A39BC452A.html —— 前 8 位日期码"
            "（YYMMDD）为发稿日，后 16 位为大写十六进制文章码。发稿日通常晚于统计周期结束日。"
        ),
        # 发稿日一般落在统计周期结束后 0..3 天，按由近及远尝试
        "lag_days": [0, 1, 2, 3, -1, 4],
        "weeks": 8,          # 保留最近多少个观测值（滚动窗口）
    },
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


# --------------------------------------------------------------------------- helpers


def log(msg):
    print("[fetch] %s" % msg, flush=True)


def week_ends(start: date, end: date):
    """Thursday week-ends in [start, end] (隆众统计周期为上周五至本周四)."""
    d = start
    while d.weekday() != 3:          # 3 == Thursday
        d += timedelta(days=1)
    while d <= end:
        yield d
        d += timedelta(days=7)


def get(url, timeout=20, retries=2):
    """Small stdlib fetch with retries; returns (status, text)."""
    import urllib.error
    import urllib.request

    last = (0, "")
    for k in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            for enc in ("utf-8", "gbk", "gb18030"):
                try:
                    return 200, raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return 200, raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = (e.code, "")
        except Exception as e:                      # noqa: BLE001 - network surface
            last = (0, str(e))
        time.sleep(0.8 * (k + 1))
    return last


def clean(html):
    """Strip tags and site chrome. The body wrapper id leaks into text unless removed."""
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r'(?is)<div[^>]*id="article-content"[^>]*>', "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"[ \t\u3000]+", " ", h)


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- parsing


def parse_bulletin(html, want_week: date | None = None, title: str = ""):
    """Extract one week's record from a bulletin page, or None if it is not that bulletin.

    The statistical window is most reliably stated in the TITLE (e.g. "统计(20260903-0909)"),
    while the numbers live in the body, so pass both. Returns a dict with the fields the
    pipeline consumes plus a `checks` dict recording what was cross-verified.
    """
    text = clean(html)
    checks = {}

    # 1) which week does this bulletin claim to cover?
    pool = (title or "") + " \n " + text
    # e.g. "(20260903）" (stat week end only) or "（20260828-0903）" (a range)
    m = (re.search(r"[（(]\s*(\d{8})\s*[-－—]\s*(\d{8})\s*[）)]", pool)
         or re.search(r"[（(]\s*(\d{8})\s*[-－—]\s*(\d{4})\s*[）)]", pool)
         or re.search(r"[（(]\s*(\d{8})\s*[）)]", pool))
    if not m:
        return None
    if m.lastindex == 1:
        class _M:                                  # uniform shape for the single-date form
            lastindex = 1
            def __init__(self, g):
                self._g = g
            def group(self, i):
                return self._g if i == 1 else self._g
        m = _M(m.group(1))
    try:
        w_end = datetime.strptime(m.group(1)[:8], "%Y%m%d").date()
        if m.group(2) and m.group(2) != m.group(1):
            endraw = m.group(2)
            if len(endraw) == 4:                  # "20260903-0909" form
                endraw = m.group(1)[:4] + endraw
            w_end = datetime.strptime(endraw, "%Y%m%d").date()
            w_start = datetime.strptime(m.group(1)[:8], "%Y%m%d").date()
        else:
            w_start = w_end - timedelta(days=6)
    except ValueError:
        return None
    if want_week and w_end != want_week:
        return None
    checks["window_text"] = "%s..%s" % (w_start.isoformat(), w_end.isoformat())

    # 2) headline utilization for the whole PVC industry
    util = None
    for pat in (
        r"PVC\s*(?:生产企业)?\s*产能利用率\s*(?:为|在|约)?\s*([\d.]+)\s*%",
        r"PVC\s*整体\s*开工\s*(?:率)?\s*(?:为|在|约)?\s*([\d.]+)\s*%",
        r"国内\s*PVC\s*开工\s*(?:率)?\s*(?:为|在|约)?\s*([\d.]+)\s*%",
        r"产能利用率\s*(?:在|为|约)?\s*([\d.]+)\s*%",
    ):
        mm = re.search(pat, text)
        if mm:
            util = to_float(mm.group(1))
            checks["util_pattern"] = pat
            break

    # 3) process-route split (电石法 / 乙烯法)
    def route(keyword):
        pat = keyword + r"\s*(?:在|为|约)?\s*([\d.]+)\s*%"
        mm = re.search(pat, text)
        return to_float(mm.group(1)) if mm else None

    calc = route("电石法")
    eth = route("乙烯法")

    # 4) week-on-week / year-on-year deltas, if the prose carries them
    chg = yoy = None
    mm = re.search(r"环比\s*(上升|下降|增加|减少|涨|跌)?\s*([\d.]+)\s*(?:个?百分点|%)", text)
    if mm:
        v = to_float(mm.group(2))
        if v is not None:
            chg = -v if mm.group(1) in ("下降", "减少", "跌") else v
    mm = re.search(r"同比\s*(上升|下降|增加|减少|涨|跌)?\s*([\d.]+)\s*(?:个?百分点|%)", text)
    if mm:
        v = to_float(mm.group(2))
        if v is not None:
            yoy = -v if mm.group(1) in ("下降", "减少", "跌") else v

    # 5) sample composition -- required for honest disclosure
    sample_n = None
    mm = re.search(r"(\d+)\s*家\s*PVC\s*生产(?:企业|厂家)", text)
    if mm:
        sample_n = int(mm.group(1))
    capacity = None
    mm = re.search(r"产能基数\s*(?:变更|调整)?\s*为\s*([\d.]+)\s*万吨", text)
    if mm:
        capacity = to_float(mm.group(1))
    sample_note = ""
    mm = re.search(r"[^。；;]{0,80}新融[^。；;]{0,80}产能基数[^。；;]{0,40}万吨[^。；;]{0,10}", text)
    if mm:
        sample_note = mm.group(0).strip()

    # 6) no value parsed -> reject rather than store a half record
    if util is None and calc is None and eth is None:
        return None

    rec = {
        "stat_week_start": w_start.isoformat(),
        "stat_week_end": w_end.isoformat(),
        "window": "%s-%s" % (w_start.isoformat(), w_end.isoformat()),
        "util_total": util,
        "cwe_pct": calc,
        "eth_pct": eth,
        "chg_pp": chg,
        "yoy_pp": yoy,
        "sample_n": sample_n,
        "capacity_base_wt": capacity,
        "sample_note": sample_note,
        "checks": checks,
    }
    return rec


def consistent(rec):
    """Reject internally impossible records instead of picking a side."""
    u, c, e = rec.get("util_total"), rec.get("cwe_pct"), rec.get("eth_pct")
    if u is None:
        return False, "no headline utilization parsed"
    if not (0 < u < 100):
        return False, "headline utilization out of range: %r" % (u,)
    for lab, v in (("cwe_pct", c), ("eth_pct", e)):
        if v is not None and not (0 < v < 100):
            return False, "%s out of range: %r" % (lab, v)
    if c is not None and e is not None and not (min(c, e) - 1e-9 <= u <= max(c, e) + 1e-9):
        return False, ("headline %.2f is outside the 电石法/乙烯法 bracket (%.2f, %.2f); "
                       "one of the three numbers is being read from the wrong sentence" % (u, c, e))
    return True, "ok"


# --------------------------------------------------------------------------- main


def fetch_week(site, week: date, gaps):
    """Try candidate publication dates for one statistical week. Returns rec or None."""
    prof = SITES[site]
    for lag in prof["lag_days"]:
        pub = week + timedelta(days=lag)
        code = pub.strftime("%y%m%d")
        # the article slug is not derivable; the caller supplies it via --slug-map when known
        slug = prof.get("slugs", {}).get(week.isoformat())
        if not slug:
            gaps.append({
                "stat_week_end": week.isoformat(),
                "reason": "no known article code for this week (see references/01-data-sources.md)",
                "tried_pub_date": pub.isoformat(),
            })
            continue
        url = prof["url_tpl"].format(code=code, slug=slug)
        status, body = get(url)
        if status != 200 or not body:
            gaps.append({"stat_week_end": week.isoformat(), "url": url,
                         "http_status": status, "reason": "fetch failed"})
            continue
        rec = parse_bulletin(body, want_week=week)
        if rec is None:
            gaps.append({"stat_week_end": week.isoformat(), "url": url,
                         "reason": "page did not parse as this week's bulletin"})
            continue
        ok, why = consistent(rec)
        rec["url"] = url
        rec["pub_ts"] = pub.isoformat()
        if not ok:
            gaps.append({"stat_week_end": week.isoformat(), "url": url, "reason": why,
                         "parsed": {k: rec.get(k) for k in ("util_total", "cwe_pct", "eth_pct")}})
            continue
        return rec
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Date-guided 开工率 bulletin fetcher")
    ap.add_argument("--site", default="mysteel_oilchem", choices=sorted(SITES))
    ap.add_argument("--start", help="first week-end date (YYYY-MM-DD), inclusive")
    ap.add_argument("--end", help="last week-end date (YYYY-MM-DD), inclusive")
    ap.add_argument("--out", default="data/util_weekly.csv")
    ap.add_argument("--gaps", default="raw/util_gaps.json")
    ap.add_argument("--probe", help="parse a single week and print the record, write nothing")
    ap.add_argument("--slug-map", help="JSON file {week_end: 16-hex article code}")
    args = ap.parse_args(argv)

    site = SITES[args.site]
    if args.slug_map:
        site["slugs"] = json.loads(Path(args.slug_map).read_text(encoding="utf-8"))

    if args.probe:
        week = datetime.strptime(args.probe, "%Y-%m-%d").date()
        gaps = []
        rec = fetch_week(args.site, week, gaps)
        print(json.dumps({"record": rec, "gaps": gaps}, ensure_ascii=False,
                         indent=2, default=str))
        return 0 if rec else 1

    if not (args.start and args.end):
        ap.error("--start and --end are required unless --probe is used")
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    out = Path(args.out)
    have = {}
    if out.exists():
        with out.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                have[row.get("stat_week_end", "")] = row
        log("existing rows: %d" % len(have))

    gaps = []
    records = []
    for week in week_ends(start, end):
        key = week.isoformat()
        if key in have and have[key].get("util_total"):
            log("%s  cached" % key)
            records.append(have[key])
            continue
        rec = fetch_week(args.site, week, gaps)
        if rec is None:
            log("%s  MISSING" % key)
            continue
        log("%s  util=%s calc=%s eth=%s" % (key, rec["util_total"], rec["cwe_pct"], rec["eth_pct"]))
        records.append(rec)

    cols = ["stat_week_end", "stat_week_start", "window", "pub_ts", "util_total", "cwe_pct",
            "eth_pct", "chg_pp", "yoy_pp", "sample_n", "capacity_base_wt", "sample_note", "url"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(records, key=lambda r: r.get("stat_week_end", "")):
            w.writerow(r)

    gp = Path(args.gaps)
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text(json.dumps(gaps, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    log("wrote %s (%d rows), %d gaps -> %s" % (out, len(records), len(gaps), gp))
    if gaps:
        log("!! report every gap in the deliverable; do not interpolate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
