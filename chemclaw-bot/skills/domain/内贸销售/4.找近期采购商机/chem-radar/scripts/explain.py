#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""排查工具：某条线索为什么被剔除？闸门是不是误杀了？

写这个脚本的原因：闸门很容易误杀（实测踩过两次——把买方当成同行剔除、
把大量真实需求当成「没写量级」剔除）。所以必须有一个一眼看清判定过程的东西。

用法:
    python explain.py --config <product.json> [--dir <任务目录>] --kv 振华
    python explain.py --config <product.json> --dir <任务目录> --reason R5

输出写到 <任务目录>/leads_raw/_explain.txt（UTF-8），因为控制台中文会乱码。
"""
from __future__ import annotations

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402


def main():
    cfg, base, _ = R.resolve_config()
    argv = sys.argv[1:]
    kv, reason = None, None
    for i, a in enumerate(argv):
        if a == "--kv" and i + 1 < len(argv):
            kv = argv[i + 1]
        elif a == "--reason" and i + 1 < len(argv):
            reason = argv[i + 1]

    rd = R.rawdir(base)
    rows = []
    for f in sorted(os.listdir(rd)):
        if f.endswith(".json") and not f.startswith("_"):
            for rec in (R.read_json(os.path.join(rd, f), []) or []):
                if isinstance(rec, dict):
                    rec["_lane"] = f
                    rows.append(rec)

    L = []
    L.append("配置: %s" % os.path.basename(base))
    L.append("原始记录: %d 条" % len(rows))
    L.append("同行名单(n=%d): %s" % (len(cfg["peers"].get("names", [])),
                                 "、".join(cfg["peers"].get("names", []))))
    L.append("错配词(n=%d): %s" % (len(cfg["gates"].get("mismatch_terms", [])),
                                "、".join(x["term"] if isinstance(x, dict) else str(x)
                                        for x in cfg["gates"].get("mismatch_terms", []))))
    L.append("R5 是否强制含数字: %s ｜ 最短字数: %s"
             % (cfg["gates"].get("require_number_in_relation"),
                cfg["gates"].get("min_relation_chars")))
    L.append("")

    hit = 0
    for rec in rows:
        blob = " ".join(str(rec.get(k, "")) for k in R.FIELDS)
        if kv and kv not in blob:
            continue
        keep, why = R.gate(dict(rec), cfg)
        if reason and reason not in why:
            continue
        hit += 1
        L.append("-" * 78)
        L.append("lane=%s  keep=%s  %s" % (rec.get("_lane"), keep, why or "(通过)"))
        for k in ("公司", "事件类型", "细分行业", "省市", "事件产品", "数量/规模",
                  "发布日", "截止日", "分组", "需求性质", "时效性", "置信度", "证据来源"):
            v = str(rec.get(k, ""))
            L.append("   %-10s %s" % (k, v[:150]))
        L.append("   与我产品的关系: %s" % str(rec.get("与我产品的关系", ""))[:300])
        L.append("   → _is_peer=%s  _subject_is_product=%s  关系字数=%d  含数字=%s"
                 % (R._is_peer(rec, cfg), R._subject_is_product(rec, cfg),
                    len(str(rec.get("与我产品的关系", "")).strip()),
                    bool(R.re.search(r"\d", str(rec.get("与我产品的关系", ""))))))

    if not hit:
        L.append("(没有匹配的记录)")
    L.append("")
    L.append("=== 全部剔除原因汇总 ===")
    c = collections.Counter()
    for rec in rows:
        keep, why = R.gate(dict(rec), cfg)
        if not keep:
            c[why] += 1
    for k, v in c.most_common():
        L.append("  %3d  %s" % (v, k))

    out = os.path.join(rd, "_explain.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("命中 %d 条，已写出: %s" % (hit, out))


if __name__ == "__main__":
    main()