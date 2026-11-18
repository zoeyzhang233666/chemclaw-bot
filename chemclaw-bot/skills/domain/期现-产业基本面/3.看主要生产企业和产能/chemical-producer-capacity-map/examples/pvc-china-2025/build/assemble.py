#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble.py — 把 data/ 下的分片 JSON 合并成单一数据集，跑重复统计校验，输出统计结果。

用法:
    python assemble.py            # 仅校验并打印报告
    python assemble.py --emit     # 另外写出 data/final.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)

from pcd_model import (  # noqa: E402
    Aggregator, BASIS_DESIGN, Dataset, DupChecker, load, coverage, hhi, cr_n,
    concentration_label,
)

REGION_MAP = {
    "新疆维吾尔自治区": "西北", "青海省": "西北", "甘肃省": "西北", "宁夏回族自治区": "西北",
    "陕西省": "西北", "西藏自治区": "西北",
    "内蒙古自治区": "华北", "山西省": "华北", "河北省": "华北", "天津市": "华北", "北京市": "华北",
    "山东省": "华东", "江苏省": "华东", "浙江省": "华东", "上海市": "华东",
    "安徽省": "华东", "福建省": "华东", "江西省": "华东",
    "河南省": "华中", "湖北省": "华中", "湖南省": "华中",
    "广东省": "华南", "广西壮族自治区": "华南", "海南省": "华南",
    "四川省": "西南", "重庆市": "西南", "云南省": "西南", "贵州省": "西南",
    "辽宁省": "东北", "吉林省": "东北", "黑龙江省": "东北",
}


def _j(name):
    with open(os.path.join(DATA, name), "r", encoding="utf-8") as f:
        return json.load(f)


def assemble() -> dict:
    sources = _j("sources.json")
    roster = _j("roster.json")
    units = _j("units.json")["units"]
    projects = _j("projects.json")
    calib = _j("calibration.json")

    # 合并 projects.json 中的增量实体/集团/基地
    groups = roster["groups"] + projects.get("extra_groups", [])
    entities = roster["entities"] + projects.get("extra_entities", [])
    plants = roster["plants"] + projects.get("extra_plants", [])

    s_list = list(sources["sources"])
    have = {s["source_id"] for s in s_list}
    for s in calib.get("extra_sources", []):
        if s["source_id"] not in have:
            s_list.append(s)
            have.add(s["source_id"])

    # benchmarks: 用 calibration 的 patch 覆盖同名 id，并追加新 id
    bms = {b["id"]: dict(b) for b in sources["benchmarks"]}
    order = [b["id"] for b in sources["benchmarks"]]
    for b in calib.get("benchmark_patches", []):
        if b["id"] in bms:
            bms[b["id"]] = dict(b)
        else:
            bms[b["id"]] = dict(b)
            order.append(b["id"])

    notes = dict(sources["notes"])
    notes["policy_notes"] = calib.get("policy_notes", [])

    out = {
        "meta": {
            "title": "中国 PVC（聚氯乙烯）生产企业与产能分布研究报告",
            "generated": "2026-10-20",
            "cutoff": "2026-10-20（产能数据年度以 2025 年为主，部分为 2024/2026 年披露）",
            "sample_scope": "中国境内聚氯乙烯（PVC）树脂生产企业：覆盖主要集团全量基地 + 中型企业主要基地 + 已取得一手披露的独立厂；含电石法、乙烯法、煤制烯烃乙烯法。不含境外产能，不含 VCM/EDC 中间品贸易环节。",
            "coverage": "47.5%",
            "coverage_note": "样本 1,423 万吨 / 全国 2,993 万吨（氯碱协会口径）· 不等于全国总产能",
            "coverage_warning": "本表为「样本口径」。全国约 71 家 PVC 生产企业中，本表仅覆盖主要集团与已取得可引用来源的企业；未覆盖企业的产能未计入，故样本合计 < 全国产能，不得称为全国总产能。",
            "basis_disclaimer": "同一份报告中同时存在 2,962 / 2,993 / 3,017 / 3,038 / 3,088 / 3,087.5 六套全国产能口径，分属商务部、氯碱协会、华经产业研究院、百川盈孚、北元年报转引氯碱网、英力特年报。本报告并列展示、不取平均、不做调和。",
        },
        "product": {
            "name": "聚氯乙烯", "short": "PVC", "cas": "9002-86-2", "formula": "(C2H3Cl)n",
            "base_year": 2025,
            "definition": "由氯乙烯单体（VCM）聚合而成的热塑性树脂。工业产品按聚合工艺分为悬浮法树脂（S-PVC，约占产量 80%）、本体法树脂（M-PVC）、乳液/微悬浮法糊树脂（E-PVC）。",
            "routes": {
                "carbide": "电石法（乙炔法）：煤/石灰石→电石→乙炔→VCM→PVC，成本锚定煤价与电费",
                "ethylene": "乙烯法：石脑油/轻烃或煤制烯烃→乙烯→EDC/VCM→PVC，沿海多依托大型乙烯基地",
            },
        },
        "groups": groups, "entities": entities, "plants": plants, "units": units,
        "projects": projects["projects"], "sources": s_list,
        "benchmarks": [bms[i] for i in order], "gaps": sources["gaps"], "notes": notes,
    }
    return out


def report(ds: Dataset) -> None:
    agg = Aggregator(ds, BASIS_DESIGN)
    rows = agg.rows()
    total = agg.total()
    by_group = agg.by_group()
    print("=" * 78)
    print("PVC 数据集自检报告")
    print("=" * 78)
    print(f"集团 {len(ds.groups)} / 法人 {len(ds.entities)} / 基地 {len(ds.plants)} / "
          f"装置 {len(ds.units)} / 项目 {len(ds.projects)} / 来源 {len(ds.sources)} / 基准 {len(ds.benchmarks)}")
    print(f"设计产能样本合计: {total:,.2f} 万吨/年  （有效装置记录 {len(rows)} 条）")

    print("\n-- 全国口径覆盖率 --")
    for b in ds.benchmarks:
        if b.get("metric", "").startswith("全国 PVC 产能"):
            c = coverage(total, b["value"])
            print(f"  {b['id']:<6} {b['value']:>8,.1f} 万吨  [{b['source_org'][:28]:<28}]  覆盖率 {c:5.1f}%")

    print("\n-- 集团（Top 12，设计产能）--")
    for gid, v in sorted(by_group.items(), key=lambda x: -x[1])[:12]:
        g = ds.groups.get(gid)
        nm = g.short_name if g else gid
        print(f"  {nm:<14} {v:9,.2f} 万吨  {v/total*100:5.1f}%")

    print("\n-- 区域 --")
    reg = agg.by_region(REGION_MAP)
    for k, v in sorted(reg.items(), key=lambda x: -x[1]):
        print(f"  {k:<6} {v:9,.2f} 万吨  {v/total*100:5.1f}%")

    print("\n-- 省份（Top 10）--")
    for k, v in sorted(agg.by_province().items(), key=lambda x: -x[1])[:10]:
        print(f"  {k:<16} {v:9,.2f} 万吨  {v/total*100:5.1f}%")

    print("\n-- 工艺 --")
    rt = agg.by_route()
    for k, v in sorted(rt.items(), key=lambda x: -x[1]):
        print(f"  {k:<10} {v:9,.2f} 万吨  {v/total*100:5.1f}%")

    print("\n-- 集中度（样本内）--")
    vals = list(by_group.values())
    h = hhi(vals)
    print(f"  CR1 {cr_n(vals,1):.1f}%  CR3 {cr_n(vals,3):.1f}%  CR5 {cr_n(vals,5):.1f}%  "
          f"CR10 {cr_n(vals,10):.1f}%  HHI {h:.0f} ({concentration_label(h)})")
    ev = list(agg.by_entity().values())
    print(f"  法人口径: CR5 {cr_n(ev,5):.1f}%  HHI {hhi(ev):.0f}")

    print("\n-- 口径分布 --")
    for k, v in Counter(u.basis for u in ds.units).items():
        print(f"  {k:<10} {v} 条")
    print("\n-- 可信度分布 --")
    for k, v in sorted(Counter(u.confidence for u in ds.units).items()):
        print(f"  {k:<3} {v} 条")
    print("\n-- 状态分布 --")
    for k, v in Counter(u.status for u in ds.units).items():
        print(f"  {k:<12} {v} 条")
    n_null = sum(1 for u in ds.units if u.capacity is None)
    print(f"\n产能未知的装置记录: {n_null} 条（如实留空，未估算）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    a = ap.parse_args()
    data = assemble()
    p = os.path.join(DATA, "final.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    ds = load(p)
    report(ds)
    findings = DupChecker(ds).run()
    print("\n" + "=" * 78)
    print(f"重复统计校验：{len(findings)} 项")
    print("=" * 78)
    for f in findings:
        print(f"  [{f.severity:<5}] {f.rule:<5} {f.subject[:34]:<34} {f.message}")


if __name__ == "__main__":
    main()
