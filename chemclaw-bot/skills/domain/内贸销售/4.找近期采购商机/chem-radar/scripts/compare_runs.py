#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""对比两次运行的商机卡差异（换窗口 / 换区域 / 改闸门后重新跑，用这个看变了什么）。

用法:
    python compare_runs.py <旧任务目录> <新任务目录> [--out 差异.txt]

判定同一张卡用 (公司, 首条证据链接) 作键。输出写 UTF-8 文件（控制台中文会乱码）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402


def keys(rows):
    out = {}
    for r in rows:
        u = R.extract_urls(r.get("证据来源", ""))
        out[(str(r.get("公司", "")), u[0] if u else "")] = r
    return out


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    outp = "差异对比.txt"
    for i, a in enumerate(sys.argv):
        if a == "--out" and i + 1 < len(sys.argv):
            outp = sys.argv[i + 1]
    if len(argv) < 2:
        sys.exit(__doc__)
    a_dir, b_dir = argv[0], argv[1]
    A = keys(R.read_json(os.path.join(a_dir, "leads.json"), []) or [])
    B = keys(R.read_json(os.path.join(b_dir, "leads.json"), []) or [])
    dropB = R.read_json(os.path.join(b_dir, "剔除记录.json"), []) or []
    dmap = {}
    for r in dropB:
        u = R.extract_urls(r.get("证据来源", ""))
        dmap[(str(r.get("公司", "")), u[0] if u else "")] = r.get("剔除原因", "")

    L = ["旧: %s  保留 %d 条" % (a_dir, len(A)),
         "新: %s  保留 %d 条" % (b_dir, len(B)), ""]
    gone = sorted(set(A) - set(B))
    L.append("=== 旧有新无（%d 条）===" % len(gone))
    for k in gone:
        L.append("  %-38s | %s" % (k[0][:38], dmap.get(k, "(被去重/合并掉)")))
    new = sorted(set(B) - set(A))
    L.append("")
    L.append("=== 新有旧无（%d 条）===" % len(new))
    for k in new:
        L.append("  %-38s | %s" % (k[0][:38], str(B[k].get("分组", ""))))
    L.append("")
    L.append("=== 仍然保留（%d 条）===" % len(set(A) & set(B)))
    same = set(A) & set(B)
    chg = []
    for k in same:
        if A[k].get("分组") != B[k].get("分组") or A[k].get("优先级") != B[k].get("优先级"):
            chg.append("  %-38s | 分组 %s→%s ｜ 优先级 %s→%s" % (
                k[0][:38], A[k].get("分组"), B[k].get("分组"),
                A[k].get("优先级"), B[k].get("优先级")))
    L.append("其中分组/优先级发生变化: %d 条" % len(chg))
    L.extend(chg)

    with open(outp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("已写出: %s（旧 %d / 新 %d，旧有新无 %d，新有旧无 %d）"
          % (outp, len(A), len(B), len(gone), len(new)))


if __name__ == "__main__":
    main()