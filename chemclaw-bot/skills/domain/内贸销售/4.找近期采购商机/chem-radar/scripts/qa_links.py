#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""链接抽检（link gate）：随机抽 ≥40 条证据链接逐条探测。

区分两类失败（这个区分很重要，否则会把「浏览器能打开的页面」误判成坏链）：
  · 反爬拦截（403/412/需登录）→ 标「需人工复核」，不是坏链
  · 真空页/故障站/超时        → 标「疑似坏链」

抽检失败的链接会退避后重试一次——限流造成的假失败很常见。

用法: python qa_links.py --config <product.json> [--dir <任务目录>] [--sample 60]
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402

ANTIBOT = {401, 403, 405, 406, 412, 418, 429, 451}


def probe(url):
    status, body = R.http_get(url, headers={"Referer": "http://www.cninfo.com.cn/"},
                              retries=2, backoff=6, timeout=25, want_status=True)
    if isinstance(status, int):
        return status, len(body or b"")
    return status, 0


def main():
    cfg, base, _ = R.resolve_config()
    argv = sys.argv[1:]
    sample_n = 60
    for i, a in enumerate(argv):
        if a == "--sample" and i + 1 < len(argv):
            sample_n = int(argv[i + 1])

    rows = R.read_json(os.path.join(base, "leads.json"), []) or []
    if not rows:
        sys.exit("leads.json 为空，请先跑 merge_leads.py")

    urls, by_url = [], {}
    for r in rows:
        for u in R.extract_urls(r.get("证据来源")):
            if u not in by_url:
                by_url[u] = []
                urls.append(u)
            by_url[u].append(r.get("公司", ""))

    print("唯一链接数:", len(urls))
    if not urls:
        R.write_json(os.path.join(R.rawdir(base), "_qa_report.json"),
                     {"抽样数": 0, "可达数": 0, "可达率": "0%", "明细": []})
        print("没有可抽检的链接")
        return

    random.seed(20260101)
    n = min(sample_n, len(urls))
    sample = urls if len(urls) <= n else random.sample(urls, n)

    report, ok, antibot = [], 0, 0
    for u in sample:
        st, ln = probe(u)
        if isinstance(st, int) and 200 <= st < 400:
            ok += 1
            verdict = "可达"
        elif isinstance(st, int) and st in ANTIBOT:
            antibot += 1
            verdict = "需人工复核（反爬拦截，浏览器可能可打开）"
        else:
            verdict = "疑似坏链"
        report.append({"url": u, "status": st, "bytes": ln,
                       "公司": "、".join(sorted(set(by_url.get(u, []))))[:60],
                       "结论": verdict})
        print("  %-6s %-8s %s" % (st, ln, u[:96]))

    out = {"抽样数": len(sample), "可达数": ok, "反爬拦截数": antibot,
           "可达率": "%.0f%%" % (100.0 * ok / max(1, len(sample))),
           "抽检时间": cfg["task"]["baseline_date"], "明细": report}
    R.write_json(os.path.join(R.rawdir(base), "_qa_report.json"), out)
    print("可达 %d/%d（另有 %d 条属反爬拦截，需人工复核）" % (ok, len(sample), antibot))
    print("已写出 leads_raw/_qa_report.json")


if __name__ == "__main__":
    main()