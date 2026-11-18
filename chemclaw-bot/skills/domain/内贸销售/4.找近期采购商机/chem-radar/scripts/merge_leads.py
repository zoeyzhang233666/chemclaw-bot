#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合并各 lane 的原始线索，套用六道闸门，去重后写出 leads.json 与 剔除记录.json。

用法:
    python merge_leads.py --config <product.json> [--dir <任务目录>]

约定: 原始线索放在 <任务目录>/leads_raw/*.json（以下划线开头的文件会被跳过，
      那是质检报告、临时缓存等非线索文件）。每个文件是一个 JSON 数组。
"""
from __future__ import annotations

import os
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402


def schema_check(rec):
    """缺必填键就报出来——lane 子代理最容易漏字段。"""
    return [k for k in R.FIELDS if k not in rec]


def main():
    cfg, base, cfg_path = R.resolve_config()
    rd = R.rawdir(base)

    files = sorted(f for f in os.listdir(rd)
                   if f.endswith(".json") and not f.startswith("_"))
    if not files:
        sys.exit("leads_raw/ 里没有任何 .json 线索文件")

    raw, per_file, bad_keys = [], OrderedDict(), []
    for f in files:
        data = R.read_json(os.path.join(rd, f), []) or []
        per_file[f] = len(data)
        for rec in data:
            if not isinstance(rec, dict):
                continue
            miss = schema_check(rec)
            if miss:
                bad_keys.append((f, rec.get("公司", "?"), miss))
            raw.append(rec)

    print("== 读入 lane 文件 ==")
    for f, n in per_file.items():
        print("   %-28s %3d 条" % (f, n))
    print("原始合计: %d 条" % len(raw))
    if bad_keys:
        print("!! 字段缺失 %d 处（已按空值处理，请让 lane 补齐）:" % len(bad_keys))
        for f, co, miss in bad_keys[:10]:
            print("   %s / %s -> 缺 %s" % (f, co, ",".join(miss)))

    kept_raw, dropped = [], []
    for rec in raw:
        rec = dict(rec)
        keep, reason = R.gate(rec, cfg)
        if keep:
            kept_raw.append(rec)
        else:
            rec["剔除原因"] = reason
            norm = R.normalize(rec, cfg)
            norm["剔除原因"] = reason
            dropped.append(norm)

    kept, dup_dropped = R.dedupe([R.normalize(r, cfg) for r in kept_raw], cfg)
    dropped.extend(dup_dropped)
    kept.sort(key=R.sort_key)

    R.write_json(os.path.join(base, "leads.json"), kept)
    R.write_json(os.path.join(base, "剔除记录.json"), dropped)

    print("\n== 结果 ==")
    print("保留 %d 条，剔除 %d 条" % (len(kept), len(dropped)))
    print("分组:", dict(Counter(r["分组"] for r in kept)))
    print("需求性质:", dict(Counter(r["需求性质"] for r in kept)))
    print("区域:", dict(Counter(r["区域"] for r in kept)))
    print("置信度:", dict(Counter(r["置信度"] for r in kept)))
    print("时效性:", dict(Counter(r["时效性"] for r in kept)))
    print("优先级:", dict(Counter(r["优先级"] for r in kept)))
    unv = [r for r in kept if not R.extract_urls(r["证据来源"])]
    print("待核实(无链接，将单列): %d 条" % len(unv))
    print("剔除原因分布:", dict(Counter(str(r.get("剔除原因", ""))[:34] for r in dropped)))
    print("\n已写出: leads.json / 剔除记录.json  (config=%s)" % os.path.basename(cfg_path))


if __name__ == "__main__":
    main()