#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_quality.py — 数据质检报告（作为交付前的最后一道闸）

检查项：
  Q1  样本长度 ≥ 52 期
  Q2  缺口明细（逐期列出缺失地区）
  Q3  口径换算缺失参数（ERROR 级）
  Q4  三个地区序列是否有异常跳变（单周变动 > 30%）
  Q5  三地区是否完全一致（说明可能误用了全国均价）
  Q6  运费来源级别（有无真实报价）
  Q7  数据状态（DEMO 必须醒目）
  Q8  分位窗口样本量是否足够
  Q9  价差等价校验（M[i][j] = -M[j][i]）
  Q10 下游占比之和是否 = 100%

用法：
  python scripts/data_quality.py --result build/result.json [--strict]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CHECK = {"PASS": 0, "WARN": 1, "ERROR": 2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default="build/result.json")
    ap.add_argument("--strict", action="store_true", help="有 WARN/ERROR 即退出非零")
    ap.add_argument("--out", default=None, help="把质检结果写成 JSON")
    a = ap.parse_args()

    R = json.load(open(a.result, encoding="utf-8"))
    M = R["meta"]
    PR = R["primary"]
    ORDER = PR["region_order"]
    NAME = {r["id"]: r["name"] for r in M["regions"]}

    issues = []

    def add(q, level, title, detail, action=""):
        issues.append({"id": q, "level": level, "title": title, "detail": detail, "action": action})

    # Q1 样本长度
    n = M["n_observations"]
    if n >= 52:
        add("Q1", "PASS", "样本长度", f"{n} 期（≥52 期，足以计算 1 年分位）")
    elif n >= 26:
        add("Q1", "WARN", "样本长度偏短", f"{n} 期（<52 期，1 年分位置信度低）",
            "拉长时间范围，或明确标注分位为低置信")
    else:
        add("Q1", "ERROR", "样本长度不足", f"{n} 期（<26 期，无法可靠计算分位）",
            "至少补到 52 期再对外交付")

    # Q2 缺口
    al = PR.get("align", {}) or {}
    nd = al.get("n_dropped", 0)
    dl = al.get("dropped", []) or []
    detail = "；".join(f"{x['date']} 缺 {'、'.join(NAME.get(m, m) for m in x['missing'])}"
                       for x in dl[:8]) or "无缺口"
    add("Q2", "PASS" if nd == 0 else "WARN", "缺口处理",
        f"剔除 {nd} 期（缺口未插值）｜{detail}",
        "" if nd == 0 else "在报告中列出剔除日期；如缺口>10%需说明原因")

    # Q3 换算缺失
    nr = PR.get("normalize_report", {}) or {}
    miss = {k: v.get("missing") or [] for k, v in nr.items() if v.get("missing")}
    if miss:
        txt = "；".join(f"{NAME.get(k, k)}: {'、'.join(v)}" for k, v in miss.items())
        add("Q3", "ERROR", "口径换算缺参数", txt,
            "补参数，或将该地区从跨区比较中剔除并注明")
    else:
        steps = sum(v.get("total_steps", 0) for v in nr.values())
        add("Q3", "PASS", "口径换算",
            f"三地区均无缺失参数；换算步数合计 {steps}" +
            ("（=0 表示报价已同口径，无需调整）" if steps == 0 else ""))

    # Q4 异常跳变
    jumps = []
    for r in ORDER:
        s = PR["series"]["prices"][r]
        dates = PR["series"]["dates"]
        prev = None
        for i, v in enumerate(s):
            if v is None:
                continue
            if prev is not None and prev != 0:
                ch = abs(v - prev) / abs(prev)
                if ch > 0.30:
                    jumps.append(f"{NAME[r]} {dates[i]} 变动 {ch*100:.0f}%")
            prev = v
    if jumps:
        add("Q4", "WARN", "单周异常跳变", "；".join(jumps[:6]),
            "核查是否为换数据源、单位错误或口径变更")
    else:
        add("Q4", "PASS", "单周变动幅度", "无单周变动超过 30% 的异常点")

    # Q5 三地是否完全一致
    identical = True
    base = PR["series"]["prices"][ORDER[0]]
    for r in ORDER[1:]:
        s = PR["series"]["prices"][r]
        if any((x is None) != (y is None) or (x is not None and abs(x - y) > 1e-9)
               for x, y in zip(base, s)):
            identical = False
            break
    if identical:
        add("Q5", "ERROR", "三地区价格完全相同",
            "三条序列逐点相等，价差恒为 0",
            "很可能误用了全国均价/同一来源，请改用区域级报价")
    else:
        up = PR.get("pairs", [])
        nonzero = sum(1 for p in up if p.get("n") and abs(p.get("current") or 0) > 0.01)
        add("Q5", "PASS", "区域差异存在", f"{nonzero}/{len(up)} 个有序对当前价差非零")

    # Q6 运费来源
    fr = PR.get("freight", {}) or {}
    rts = fr.get("routes", []) or []
    prov = sum(1 for x in rts if x.get("freight_basis") == "provided")
    dflt = sum(1 for x in rts if x.get("freight_basis") == "default_ref")
    na = sum(1 for x in rts if x.get("freight_basis") == "not_available")
    if prov == 0:
        add("Q6", "WARN", "无真实运费报价",
            f"真实 {prov} / 默认参考 {dflt} / 未获得 {na}",
            "扣费后差异只能作敏感性参考，报告中不得作为套利依据")
    else:
        add("Q6", "PASS", "运费来源", f"真实报价 {prov} 条 / 默认参考 {dflt} / 未获得 {na}")

    # Q6b 运费已内含提示
    if PR.get("freight_embedded_in_price"):
        add("Q6b", "WARN", "运费已内含在报价中",
            "主口径为送到价，运费不可重复扣减",
            "报告须明写；运费调整仅用于出厂价口径与物流可行性核对")

    # Q7 数据状态
    st = M["data_status"]
    if st == "DEMO":
        add("Q7", "WARN", "DEMO 数据", "价格序列为拟真构造，非真实报价",
            "报告顶部必须挂 DEMO 徽标；金额与分位不得对外引用")
    else:
        add("Q7", "PASS", "数据状态", st)

    # Q8 窗口样本
    wins = M.get("windows", ["1y", "3y"])
    small = []
    for rec in PR.get("percentiles", []):
        for w in wins:
            x = (rec.get("windows") or {}).get(w) or {}
            if x.get("n") is not None and 0 < x["n"] < 30:
                small.append(f"{rec['pair']} {w} N={x['n']}")
    if small:
        add("Q8", "WARN", "窗口样本不足 30", "；".join(small[:6]),
            "分位标注为低置信，或改用更长窗口")
    else:
        add("Q8", "PASS", "窗口样本量", "所有窗口 N ≥ 30")

    # Q9 等价校验
    mx = PR["matrix"]["values"]
    bad = []
    for i, aa in enumerate(ORDER):
        for b in ORDER:
            if aa == b:
                continue
            v1, v2 = mx.get(f"{aa}|{b}"), mx.get(f"{b}|{aa}")
            if v1 is None or v2 is None:
                continue
            if abs(v1 + v2) > 0.01:
                bad.append(f"{aa}|{b}")
    if bad:
        add("Q9", "ERROR", "价差矩阵不等价", "、".join(bad), "检查 spread_series 的方向")
    else:
        add("Q9", "PASS", "价差等价校验", "M[i][j] = −M[j][i] 全部成立")

    # Q10 下游占比
    fund = (R.get("fundamentals") or {}).get("regions", {}) or {}
    badsum = []
    for r in ORDER:
        ds = (fund.get(r) or {}).get("downstream") or []
        if not ds:
            continue
        s = sum(x.get("share_2023") or 0 for x in ds)
        if abs(s - 1.0) > 0.02:
            badsum.append(f"{NAME[r]} {s*100:.1f}%")
    if badsum:
        add("Q10", "WARN", "下游占比合计偏离 100%", "、".join(badsum),
            "确认是示意性拆分（应标注）还是数据错误")
    else:
        add("Q10", "PASS", "下游占比", "各地区合计均 ≈100%")

    # 输出
    icon = {"PASS": "✓", "WARN": "⚠", "ERROR": "✗"}
    print(f"\n数据质检 ｜ {M['product']} ｜ {' / '.join(NAME[r] for r in ORDER)} ｜ {M['data_status']}\n")
    for it in issues:
        print(f"  [{icon[it['level']]}] {it['id']:4s} {it['title']}")
        print(f"        {it['detail']}")
        if it["action"]:
            print(f"        → {it['action']}")
    cnt = {k: sum(1 for x in issues if x["level"] == k) for k in ("PASS", "WARN", "ERROR")}
    print(f"\n合计：PASS {cnt['PASS']} ｜ WARN {cnt['WARN']} ｜ ERROR {cnt['ERROR']}")

    if a.out:
        json.dump({"meta": {"product": M["product"], "regions": ORDER, "status": M["data_status"]},
                   "counts": cnt, "issues": issues},
                  open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"→ {a.out}")

    if a.strict and (cnt["WARN"] or cnt["ERROR"]):
        return 1
    return 0 if cnt["ERROR"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
