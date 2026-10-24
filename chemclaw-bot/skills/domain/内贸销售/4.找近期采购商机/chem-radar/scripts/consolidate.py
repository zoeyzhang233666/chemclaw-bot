#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""同一主体的条目合并成一张商机卡（一张卡＝一个企业在一个分组里的一个商机）。

为什么要合并：同一次公告会被多个 lane 各抓一条、同一家公司在公告里有一堆写法，
不合并就会出现「元力股份」占 4 行、读者以为有 4 个客户。

用法: python consolidate.py --config <product.json> [--dir <任务目录>]
"""
from __future__ import annotations

import os
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402

ORDER_F = {R.FRESH_OK: 3, R.FRESH_LEAD: 2, R.FRESH_EXPIRED: 1}
ORDER_C = {R.CONF_HIGH: 3, R.CONF_MID: 2, R.CONF_LOW: 1}


def join_uniq(parts, sep="；"):
    out = []
    for p in parts:
        p = str(p or "").strip()
        if p and p not in out:
            out.append(p)
    return sep.join(out)


def merge(group, cfg):
    group = sorted(group, key=lambda r: (-ORDER_F.get(r.get("时效性"), 0),
                                        -int(r.get("优先级分") or 0)))
    base = dict(group[0])
    if len(group) == 1:
        base.pop("_合并条数", None)
        return base

    for f in ("事件类型", "细分行业", "事件产品"):
        base[f] = join_uniq([r.get(f) for r in group], " / ")
    base["数量/规模"] = join_uniq([r.get("数量/规模") for r in group])
    base["与我产品的关系"] = join_uniq([r.get("与我产品的关系") for r in group])
    base["信号方向"] = join_uniq([r.get("信号方向") for r in group])

    # 发布日保留主证据那条的日期，使「发布日」与首条证据自洽；被并入的来源链接全部保留
    urls = []
    for r in group:
        for u in R.extract_urls(r.get("证据来源")):
            if u not in urls:
                urls.append(u)
    if urls:
        base["证据来源"] = " ｜ ".join(urls)
    cds = [str(r.get("截止日") or "") for r in group if str(r.get("截止日") or "")]
    base["截止日"] = max(cds) if cds else ""
    base["时效性"] = max((r.get("时效性") for r in group), key=lambda x: ORDER_F.get(x, 0))
    base["置信度"] = max((r.get("置信度") for r in group), key=lambda x: ORDER_C.get(x, 0))

    note = base.get("来源备注", "")
    if len(urls) > 1:
        note = ("%s ｜ 同一主体的 %d 条同源证据已合并，共 %d 个来源链接"
                % (note, len(group), len(urls))).strip(" ｜")
    base["来源备注"] = note
    base["_合并条数"] = len(group)
    base["_合并自"] = join_uniq(["%s@%s" % (r.get("事件类型"), r.get("发布日")) for r in group], " + ")
    return base


def main():
    cfg, base, _ = R.resolve_config()
    rows = R.read_json(os.path.join(base, "leads.json"), []) or []
    if not rows:
        sys.exit("leads.json 为空，请先跑 merge_leads.py")
    print("合并前: %d 条" % len(rows))

    buckets = OrderedDict()
    for r in rows:
        # 同一企业 + 同一分组 ⇒ 一张卡（分组不同要保留，因为要归入不同工作表/分区）
        key = (R.norm_company(r.get("公司", ""), cfg), r.get("分组"))
        buckets.setdefault(key, []).append(r)

    out = [merge(v, cfg) for v in buckets.values()]

    for r in out:
        urls, note = R.clean_source(r.get("证据来源"))
        r["证据来源"] = " ｜ ".join(urls) if urls else "未核实"
        if note and not r.get("来源备注"):
            r["来源备注"] = note
        r.setdefault("来源备注", "")
        st, sc, band = R.priority(r, cfg)
        r["用量强度"], r["优先级分"], r["优先级"] = st, sc, band
        r.pop("_合并条数", None)

    out.sort(key=R.sort_key)
    R.write_json(os.path.join(base, "leads.json"), out)

    print("最终: %d 条" % len(out))
    for r in out:
        if r.get("_合并自"):
            print("  合并 %-26s <- %s" % (str(r.get("公司"))[:26], r["_合并自"]))
    print("分组:", dict(Counter(r["分组"] for r in out)))
    cross = {k: v for k, v in Counter(R.norm_company(r.get("公司", ""), cfg) for r in out).items() if v > 1}
    if cross:
        print("同名但跨分组（应保留，分别归入不同分区）:", cross)


if __name__ == "__main__":
    main()