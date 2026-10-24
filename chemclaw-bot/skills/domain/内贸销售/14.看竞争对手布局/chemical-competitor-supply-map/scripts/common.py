#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared data layer for the chemical competitor supply map skill.

Input: one data.json for one product + one target region.
Output: a normalized D dict used by both HTML and Excel builders.
No network, no third-party dependency except the Python standard library.
"""
from __future__ import annotations

import json
import math
import os
from copy import deepcopy

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
TEMPLATES = os.path.join(HERE, "templates")

DEFAULT_BANDS = [
    {"id": "local", "label": "≤300km 本地", "max": 300},
    {"id": "near", "label": "300–800km 近邻", "max": 800},
    {"id": "long", "label": "800–1500km 长途", "max": 1500},
    {"id": "far", "label": ">1500km 超长途", "max": None},
]

DEFAULT_PROCESSES = [
    {"id": "natural", "name": "天然碱", "color": "#b4642d"},
    {"id": "combined", "name": "联碱", "color": "#2f6f8f"},
    {"id": "ammonia", "name": "氨碱", "color": "#6b7f4a"},
    {"id": "other", "name": "其他", "color": "#8c7a5b"},
]

DEFAULT_COLORS = ["#b4642d", "#2f6f8f", "#6b7f4a", "#8c5a7a", "#c19a3d", "#4f7f6f"]


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return build(json.load(f))


def haversine(lon1, lat1, lon2, lat2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _fmt(n):
    if n is None:
        return "—"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    return f"{n:,.0f}" if n.is_integer() else f"{n:,.1f}"


def _band_for(km, bands):
    for b in bands:
        if b.get("max") is None or km <= float(b["max"]):
            return b["label"]
    return bands[-1]["label"]


def _get_meta(raw):
    meta = deepcopy(raw.get("meta") or {})
    target = raw.get("target") or {}
    meta.setdefault("product", raw.get("product") or "目标化工品")
    meta.setdefault("product_short", meta["product"].split("（")[0].split("(")[0].strip())
    meta.setdefault("region", target.get("region") or f"{target.get('province','')} · {target.get('city','')}".strip(" ·"))
    meta.setdefault("province", target.get("province") or "")
    meta.setdefault("city", target.get("city") or "")
    meta.setdefault("target_lon", target.get("lon"))
    meta.setdefault("target_lat", target.get("lat"))
    meta.setdefault("anchor_customer", target.get("customer") or "")
    meta.setdefault("anchor_short", target.get("customer_short") or "示例客户")
    meta.setdefault("asof", raw.get("asof") or "")
    meta.setdefault("unit", "万吨/年")
    meta.setdefault("output_unit", "万吨")
    meta.setdefault("distance_label", "直线距离")
    meta.setdefault("brand_mark", "化")
    meta.setdefault("brand_name", "化图 · SUPPLY MAP")
    meta.setdefault("brand_sub", "COMPETITIVE SUPPLY LAYOUT")
    meta.setdefault("download_name", "")
    meta.setdefault("processes", DEFAULT_PROCESSES)
    meta.setdefault("distance_bands", DEFAULT_BANDS)
    meta.setdefault("extra_provinces", [])
    meta.setdefault("zero_provinces", [])
    meta.setdefault("coverage", {})
    meta.setdefault("disclaimer", "本报告为销售线索与竞争布局研究，不构成投资建议、价格承诺或市场份额结论。")
    if not meta.get("target_lon") and raw.get("target"):
        meta["target_lon"] = raw["target"].get("lon")
    if not meta.get("target_lat") and raw.get("target"):
        meta["target_lat"] = raw["target"].get("lat")
    return meta


def _default_narrative(meta):
    product = meta["product_short"]
    region = meta["region"]
    return {
        "hero_lede": f"以 <b>{region}</b> 为目标区域、以 <b>{meta['anchor_customer'] or meta['anchor_short']}</b> 为示例客户，把主要{product}企业的工厂位置、工艺路线、公开产能、新增项目叠到一张图上；先看竞争供给在哪里密集，再看哪些区域只有远距离供应，最后看未来哪些新增产能会改写格局。",
        "map_sub": f"气泡大小＝{product}产能；颜色＝工艺路线。虚线＝到{meta['city']}的{meta['distance_label']}，只作物流线索，不替代运费测算。",
        "density_sub": f"省级产能为样本加总；距离带按工厂到{meta['city']}的{meta['distance_label']}归类。无样本≠无货，只表示无在产工厂。",
        "national_note": "全国供给分布不均；先把样本内密集区与目标区域周边分层看，再决定拜访与报价顺序。",
        "how_to_read": "虚线越密，说明目标区域越依赖远距离调入；点省份看“本省工厂 + 最近外省供给”。",
        "pipeline_intro": "只列公开可核实的新增/在建/搬迁项目；毛增量不等于净增，负增量（停产、冷修、限产）需另行收集。",
        "pipeline_foot": "销售动作应从“有没有货”转向“到厂成本、库存前置、指标稳定性”。",
        "prospect_intro": f"先看示例客户的用量级与供应距离，再按赛道筛选{meta['province']}潜客样本。",
        "prospect_note": "潜客表只放可核实的规模/业务事实；用量为按行业吨耗的推算，已单独标注。",
        "prospect_scope_note": f"本演示只内置{meta['province']}潜客样本；正式版可按省接入潜客库。",
        "anchor_note": "用量为按行业吨耗推算；仅作用量级，不是企业披露。",
        "grade_note": "A 公司定期报告/政府文件；B 公司 IR/行业统计/券商拆分；C 企业公开业务信息；D 物流/覆盖推断。",
        "conclusions": [],
        "prospect_conclusions": [],
        "method_conclusions": [],
    }


def build(raw):
    """Normalize raw JSON into the contract used by both renderers.

    The function is deliberately idempotent: a previously normalized data.json
    can be fed back in and will produce materially the same result.
    """
    D = deepcopy(raw)
    meta = _get_meta(D)
    D["meta"] = meta
    # Compatibility aliases used by the JS layer.
    D["asof"] = meta["asof"]
    D["product"] = meta["product"]

    companies = D.get("companies") or []
    plants = D.get("plants") or []
    projects = D.get("projects") or []
    prospects = D.get("prospects") or []
    sources = D.get("sources") or []
    conflicts = D.get("conflicts") or []
    gaps = D.get("gaps") or []

    # ---- source map ----
    src_map = {s.get("id"): s for s in sources if s.get("id")}

    # ---- target ----
    tlon = _num(meta.get("target_lon"), None)
    tlat = _num(meta.get("target_lat"), None)
    if tlon is None or tlat is None:
        raise ValueError("meta.target_lon / meta.target_lat 必填（目标区域经纬度）")
    D["target"] = {
        "region": meta["region"],
        "province": meta["province"],
        "city": meta["city"],
        "lon": tlon,
        "lat": tlat,
        "customer": meta["anchor_customer"],
        "customer_short": meta["anchor_short"],
        "note": (D.get("target") or {}).get("note", ""),
    }

    # ---- processes ----
    procs = meta.get("processes") or DEFAULT_PROCESSES
    if isinstance(procs, dict):
        procs = [{"id": k, "name": k, "color": v} for k, v in procs.items()]
    # If data uses process names not declared, append a deterministic color.
    known = {p.get("name") for p in procs}
    for p in plants + projects + companies:
        name = p.get("process")
        if name and name not in known:
            color = DEFAULT_COLORS[len(procs) % len(DEFAULT_COLORS)]
            procs.append({"id": str(len(procs) + 1), "name": name, "color": color})
            known.add(name)
    meta["processes"] = procs
    proc_color = {p["name"]: p.get("color", "#8c7a5b") for p in procs}

    # ---- plants ----
    for i, p in enumerate(plants):
        p.setdefault("id", f"pl_{i+1}")
        p["capacity"] = _num(p.get("capacity"))
        p["lon"] = _num(p.get("lon"), None)
        p["lat"] = _num(p.get("lat"), None)
        if p["lon"] is None or p["lat"] is None:
            raise ValueError(f"工厂 {p.get('name')} 缺少 lon/lat")
        p["km"] = round(haversine(tlon, tlat, p["lon"], p["lat"]))
        p["band"] = _band_for(p["km"], meta["distance_bands"])
        p["grade"] = p.get("grade") or "B"
        p["source_ids"] = p.get("source_ids") or []
        p["process_color"] = proc_color.get(p.get("process"), "#8c7a5b")
    plant_map = {p["id"]: p for p in plants}
    comp_map = {c.get("id"): c for c in companies}

    # ---- companies ----
    for i, c in enumerate(companies):
        c.setdefault("id", f"co_{i+1}")
        _plants = [p for p in plants if p.get("company_id") == c["id"]]
        if c.get("capacity") in (None, ""):
            c["capacity"] = round(sum(p["capacity"] for p in _plants), 2)
        else:
            c["capacity"] = _num(c.get("capacity"))
        c["output"] = _num(c.get("output"), None)
        c["grade"] = c.get("grade") or "B"
        c["source_ids"] = c.get("source_ids") or []
        c["plants"] = _plants
        c["plant_count"] = len(c["plants"])
        c["min_km"] = min([p["km"] for p in c["plants"]], default=None)
        c["band"] = _band_for(c["min_km"], meta["distance_bands"]) if c["min_km"] is not None else "—"
        c["projects"] = [p for p in projects if p.get("company_id") == c["id"]]
        c["process_color"] = proc_color.get(c.get("process"), "#8c7a5b")
        if c["plant_count"] and abs(c["capacity"] - sum(p["capacity"] for p in c["plants"])) > 0.51:
            raise ValueError(f"企业 {c.get('name')} 产能 {c['capacity']} 与工厂合计 {sum(p['capacity'] for p in c['plants'])} 不一致")

    # ---- plants backfill company names ----
    for p in plants:
        c = comp_map.get(p.get("company_id"))
        p["company"] = (c or {}).get("name", p.get("company", ""))
        p["company_short"] = (c or {}).get("short", p.get("company_short", p["company"]))

    # ---- projects ----
    for i, pr in enumerate(projects):
        pr.setdefault("id", f"pj_{i+1}")
        pr["capacity"] = _num(pr.get("capacity"))
        pr["lon"] = _num(pr.get("lon"), None)
        pr["lat"] = _num(pr.get("lat"), None)
        pr["year"] = int(_num(pr.get("year"), 0)) or None
        pr["grade"] = pr.get("grade") or "B"
        pr["source_ids"] = pr.get("source_ids") or []
        c = comp_map.get(pr.get("company_id"))
        pr["company"] = (c or {}).get("name", pr.get("company", ""))
        pr["company_short"] = (c or {}).get("short", pr.get("company_short", ""))
        # Default kinds are deliberately simple; project net should be data-supplied.
        pr["kind"] = pr.get("kind") or "新增"
        pr["net"] = pr.get("net") or "待核"
        pr["process_color"] = proc_color.get(pr.get("process"), "#d9a441")

    # ---- prospects ----
    for i, cu in enumerate(prospects):
        cu.setdefault("id", f"cu_{i+1}")
        cu["province"] = cu.get("province") or meta["province"]
        cu["priority"] = cu.get("priority") or "B"
        cu["grade"] = cu.get("grade") or "B"
        cu["segment"] = cu.get("segment") or "待补"
        cu["source_ids"] = cu.get("source_ids") or []

    # ---- province aggregates ----
    provs = {}
    for p in plants:
        d = provs.setdefault(p.get("province") or "未知", {
            "province": p.get("province") or "未知", "capacity": 0, "plants": 0,
            "companies": set(), "processes": {}, "km_min": 10 ** 9,
        })
        d["capacity"] += p["capacity"]
        d["plants"] += 1
        d["companies"].add(p.get("company_id"))
        d["processes"][p.get("process")] = d["processes"].get(p.get("process"), 0) + p["capacity"]
        d["km_min"] = min(d["km_min"], p["km"])
    for d in provs.values():
        d["n_companies"] = len(d["companies"])
        d["companies"] = sorted(d["companies"])
        d["dominant"] = max(d["processes"].items(), key=lambda kv: kv[1])[0] if d["processes"] else "—"
        d["judge"] = "密集" if d["capacity"] >= 400 else ("较密集" if d["capacity"] >= 200 else ("薄" if d["capacity"] > 0 else "空白"))
        if d["km_min"] == 10 ** 9:
            d["km_min"] = None
        d["prospects"] = [cu for cu in prospects if cu["province"] == d["province"]]
        d["prospect_count"] = len(d["prospects"])
    # Include target province even when zero, plus any requested blank provinces.
    for name in [meta["province"]] + list(meta.get("zero_provinces") or []) + list(meta.get("extra_provinces") or []):
        if not name:
            continue
        provs.setdefault(name, {
            "province": name, "capacity": 0, "plants": 0, "n_companies": 0,
            "companies": [], "processes": {}, "dominant": "—", "judge": "空白",
            "km_min": None, "prospects": [cu for cu in prospects if cu["province"] == name], "prospect_count": 0,
        })
    for d in provs.values():
        d["prospect_count"] = len(d.get("prospects") or [])
    D["provs"] = sorted(provs.values(), key=lambda d: (-d["capacity"], d["province"]))

    # ---- bands / totals ----
    bd = {b["label"]: 0 for b in meta["distance_bands"]}
    for p in plants:
        bd[p["band"]] = bd.get(p["band"], 0) + p["capacity"]
    D["bands"] = [{"band": b["label"], "capacity": bd.get(b["label"], 0)} for b in meta["distance_bands"]]
    process_totals = {}
    for p in plants:
        process_totals[p.get("process")] = process_totals.get(p.get("process"), 0) + p["capacity"]
    D["process_totals"] = process_totals
    D["total_cap"] = round(sum(c["capacity"] for c in companies), 2)
    D["total_out"] = round(sum(c["output"] for c in companies if c["output"] is not None), 2)
    D["total_plants"] = len(plants)
    D["total_companies"] = len(companies)
    D["prospect_by_prov"] = {}
    for cu in prospects:
        D["prospect_by_prov"].setdefault(cu["province"], []).append(cu)
    D["sources"] = sources
    D["conflicts"] = conflicts
    D["gaps"] = gaps
    D["source_map"] = src_map
    D["companies"] = companies
    D["plants"] = plants
    D["projects"] = projects
    D["prospects"] = prospects
    D["narrative"] = {**_default_narrative(meta), **(D.get("narrative") or {})}
    D["demand_by_prov"] = D.get("demand_by_prov") or {}
    D["meta"]["coverage"] = meta.get("coverage") or {}
    return D


def load_raw(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(D, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=2)
