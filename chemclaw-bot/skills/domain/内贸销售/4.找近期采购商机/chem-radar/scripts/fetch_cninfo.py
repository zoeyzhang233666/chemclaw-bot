#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cninfo（巨潮资讯）公告检索 —— 主力取数通道。

把实测踩过的坑固化进代码：
  · **标题检索（isfulltext=false）与全文检索（isfulltext=true）结果可能天差地别**，
    所以默认两轮都跑，并把对照结果打出来。只看标题会得出「这个产品没有需求」的错误结论。
  · **必须带 Referer + X-Requested-With，否则会静默返回 total=0（假 0）**。
    本脚本任何 total=0 都会补头重试一次，并在输出里明确标为「疑似假 0 / 已复核真零」。
  · **announcementTime 是 UTC，比公告日期早一天** → 发布日一律取 adjunctUrl 里的
    /finalpage/YYYY-MM-DD/ 日期。
  · **并发即 403** → 默认每次请求间隔 4 秒、失败退避重试。
  · **多词是 AND 分词**，不是短语匹配。

用法:
    python fetch_cninfo.py --config config/soda-ash-east.json \
        --terms "纯碱采购,采购纯碱,纯碱采购量" [--mode both|full|title] \
        [--pages 5] [--out leads_raw/_cninfo_fulltext.json]

输出 JSON: 每条含 date/secCode/secName/title/url/snippet/term
中文会写进 UTF-8 文件，不要指望控制台能正确显示。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402

SEARCH_API = "http://www.cninfo.com.cn/new/fulltextSearch/full"
HEADERS = {
    "Referer": "http://www.cninfo.com.cn/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
COLUMN = "szse"


def date_from_url(adjunct):
    """发布日取 adjunctUrl 里的 /finalpage/YYYY-MM-DD/ —— announcementTime 是 UTC，会早一天。"""
    m = re.search(r"/finalpage/(\d{4}-\d{2}-\d{2})/", str(adjunct or ""))
    return m.group(1) if m else ""


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s or ""))).strip()


def one_page(term, page, isfulltext, sdate, edate, page_size=30, sleep=4.0):
    q = {
        "searchkey": term,
        "sdate": sdate,
        "edate": edate,
        "isfulltext": "true" if isfulltext else "false",
        "sortName": "nothing",
        "sortType": "desc",
        "pageNum": str(page),
        "pageSize": str(page_size),
        "type": "",
        "column": COLUMN,
        "plate": "",
        "stock": "",
        "tabName": "fulltext",
        "seDate": "",
    }
    url = SEARCH_API + "?" + urllib.parse.urlencode(q)
    status, body = R.http_get(url, headers=HEADERS, retries=3, backoff=8, timeout=30)
    time.sleep(sleep)
    if not isinstance(status, int) or status >= 400 or not body:
        return None, status
    try:
        return json.loads(body), status
    except Exception:
        return None, status


def search_term(term, isfulltext, sdate, edate, pages, sleep):
    """返回 (records, total, notes)。自动做「假 0」复核。"""
    records, total, notes = [], 0, []
    first, status = one_page(term, 1, isfulltext, sdate, edate, sleep=sleep)
    if first is None:
        notes.append("请求失败(status=%s)" % status)
        return records, 0, notes
    total = int(first.get("totalAnnouncement") or 0)
    if total == 0:
        # 假 0 复核：隔一会儿补头重试一次
        notes.append("首查 0 条，退避 10s 后复核（防假 0）")
        time.sleep(10)
        again, st2 = one_page(term, 1, isfulltext, sdate, edate, sleep=sleep)
        if again and int(again.get("totalAnnouncement") or 0) > 0:
            first = again
            total = int(again["totalAnnouncement"])
            notes.append("复核后确认为 %d 条 → 首查的 0 是假 0" % total)
        else:
            notes.append("复核后仍为 0 条 → 判定为真零（仍建议换词/换窗口再确认一次）")
            return records, 0, notes

    def harvest(payload):
        for a in payload.get("announcements") or []:
            adj = a.get("adjunctUrl") or ""
            records.append({
                "term": term,
                "mode": "fulltext" if isfulltext else "title",
                "date": date_from_url(adj),
                "secCode": a.get("secCode", ""),
                "secName": a.get("secName", ""),
                "title": strip_tags(a.get("announcementTitle")),
                "url": "http://static.cninfo.com.cn/" + adj if adj else "",
                "detail": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=%s&announcementId=%s" % (
                    a.get("secCode", ""), a.get("announcementId", "")),
                "snippet": strip_tags(a.get("announcementContent")),
            })

    harvest(first)
    for p in range(2, pages + 1):
        payload, _ = one_page(term, p, isfulltext, sdate, edate, sleep=sleep)
        if not payload or not payload.get("announcements"):
            break
        harvest(payload)
    return records, total, notes


def main():
    cfg, base, _ = R.resolve_config()
    argv = sys.argv[1:]
    terms = None
    mode = "both"
    pages = 5
    outp = None
    for i, a in enumerate(argv):
        if a == "--terms" and i + 1 < len(argv):
            terms = [x.strip() for x in argv[i + 1].split(",") if x.strip()]
        elif a == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]
        elif a == "--pages" and i + 1 < len(argv):
            pages = int(argv[i + 1])
        elif a == "--out" and i + 1 < len(argv):
            outp = argv[i + 1]

    sdate, edate = cfg["task"]["window_start"], cfg["task"]["window_end"]
    if not terms:
        terms = list(cfg["product"].get("aliases", [])) + list(cfg["product"].get("procure_terms", []))[:3]
        terms = [t for t in terms if len(t) >= 2][:8]

    modes = [True, False] if mode == "both" else [mode == "full"]

    all_rec, summary = [], []
    for term in terms:
        for ft in modes:
            recs, total, notes = search_term(term, ft, sdate, edate, pages, sleep=4.0)
            all_rec.extend(recs)
            tag = "全文" if ft else "标题"
            line = "[%s] %-22s total=%-5d 取回 %-4d %s" % (
                tag, term, total, len(recs), ("｜ " + "；".join(notes)) if notes else "")
            print(line)
            summary.append({"term": term, "mode": "fulltext" if ft else "title",
                            "total": total, "fetched": len(recs), "notes": notes})

    # 按 (url, term) 去重
    seen, uniq = set(), []
    for r in all_rec:
        k = (r["url"], r["term"], r["mode"])
        if r["url"] and k not in seen:
            seen.add(k)
            uniq.append(r)

    outp = outp or os.path.join("leads_raw", "_cninfo_%s.json" % cfg["task"]["id"])
    if not os.path.isabs(outp):
        outp = os.path.join(base, outp)
    R.write_json(outp, {"window": [sdate, edate], "summary": summary, "records": uniq})

    print("\n术语对照小结（标题 vs 全文 的差距就是只看标题的代价）：")
    by = {}
    for s in summary:
        by.setdefault(s["term"], {})[s["mode"]] = s["total"]
    for t, d in by.items():
        print("   %-22s 标题=%-6s 全文=%-6s" % (t, d.get("title", "-"), d.get("fulltext", "-")))
    print("\n合计取回 %d 条（去重后），已写出: %s" % (len(uniq), outp))
    print("提示：正文片段只有约 55 字窗口；要拿吨数/金额/合同期，请用 fetch_pdftext.py 下 PDF 抽正文。")


if __name__ == "__main__":
    main()