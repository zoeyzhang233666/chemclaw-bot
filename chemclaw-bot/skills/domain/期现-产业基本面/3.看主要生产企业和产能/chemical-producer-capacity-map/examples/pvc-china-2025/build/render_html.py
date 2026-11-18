#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_html.py — 生成交互式 HTML 企业产能分布研究报告（单文件、零外部依赖、可离线打开）
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from pcd_model import (  # noqa: E402
    Aggregator, BASIS_ACTUAL, BASIS_CAPACITY, BASIS_DESIGN, BASIS_LABELS,
    CONFIDENCE_LABELS, DupChecker, PROJECT_STAGE_LABELS, PIPELINE_WEIGHTS,
    ROUTE_LABELS, STATUS_LABELS, Dataset, concentration_label, coverage, cr_n, hhi,
)

ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "assets")

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


def _read(name: str) -> str:
    with open(os.path.join(ASSETS, name), "r", encoding="utf-8") as f:
        return f.read()


def _geo() -> Dict[str, Any]:
    p = os.path.join(ROOT, "data", "geo_ref.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"provinces": {}, "cities": {}}


CHINA_PROVINCES = json.loads(r'''{
"新疆维吾尔自治区":[[73.5,39.4],[75.0,40.5],[76.5,41.0],[80.3,43.0],[82.5,45.0],[85.0,47.0],[87.0,48.8],[90.0,47.8],[91.0,45.2],[93.5,44.9],[96.4,43.2],[96.0,41.0],[92.5,39.2],[89.5,37.5],[85.5,36.9],[80.0,35.3],[78.5,35.5],[76.0,35.6],[74.5,37.0]],
"西藏自治区":[[78.5,35.5],[80.0,35.3],[85.5,36.9],[89.5,37.5],[92.5,39.2],[96.0,41.0],[99.0,38.5],[101.0,36.0],[102.5,33.5],[100.0,31.0],[98.5,28.2],[97.0,28.3],[96.0,29.0],[93.5,27.9],[91.5,27.8],[89.0,27.3],[87.0,27.9],[85.0,28.3],[81.0,30.3],[78.5,32.5]],
"青海省":[[89.5,37.5],[92.5,39.2],[96.0,41.0],[99.0,38.5],[101.0,36.0],[102.8,35.5],[103.0,33.5],[101.0,32.5],[99.0,31.5],[97.0,31.0],[94.0,32.0],[90.5,33.5],[89.5,35.0]],
"甘肃省":[[96.0,41.0],[99.0,38.5],[101.0,36.0],[102.8,35.5],[104.0,35.5],[106.5,36.0],[107.0,37.5],[106.0,39.0],[103.0,39.5],[99.0,40.5]],
"内蒙古自治区":[[96.0,41.0],[99.0,40.5],[103.0,39.5],[106.0,39.0],[108.0,39.5],[110.0,40.5],[111.5,41.5],[114.0,41.2],[116.5,42.5],[118.5,43.5],[120.0,45.5],[122.5,47.5],[124.0,49.5],[121.0,51.0],[119.0,50.0],[117.0,49.5],[115.0,47.5],[111.0,45.5],[107.0,44.5],[103.0,42.5],[99.0,42.0]],
"宁夏回族自治区":[[104.0,35.5],[106.5,36.0],[107.5,37.5],[107.0,39.3],[106.0,39.5],[104.5,38.5],[104.0,37.0]],
"陕西省":[[104.0,35.5],[106.5,36.0],[107.5,37.5],[109.5,38.5],[110.5,39.5],[110.0,37.5],[111.0,36.0],[111.0,34.5],[110.5,33.5],[109.0,32.5],[107.0,32.5],[105.5,33.0],[104.0,33.0]],
"山西省":[[110.5,39.5],[111.5,41.5],[114.0,41.2],[114.5,39.5],[114.5,37.5],[113.5,35.5],[111.0,35.0],[110.5,33.5],[111.0,34.5],[111.0,36.0],[110.0,37.5]],
"河北省":[[114.0,41.2],[116.5,42.5],[118.5,43.5],[120.0,45.5],[118.5,41.0],[117.5,39.0],[117.8,38.0],[116.5,37.5],[115.0,36.4],[114.0,36.5],[113.5,35.5],[114.5,37.5],[114.5,39.5]],
"北京市":[[115.4,39.4],[116.0,40.0],[116.2,40.5],[116.9,40.9],[117.5,40.3],[116.8,39.6],[116.2,39.5]],
"天津市":[[117.0,39.6],[117.5,40.0],[118.0,39.5],[117.9,38.8],[117.2,38.6],[116.9,39.1]],
"山东省":[[114.9,36.4],[116.5,37.5],[117.8,38.0],[117.5,39.0],[121.0,37.8],[122.7,37.4],[122.5,36.9],[120.5,35.9],[119.5,35.0],[118.0,34.7],[116.5,34.6],[115.5,34.9]],
"河南省":[[110.5,33.5],[111.0,34.5],[113.5,35.5],[115.5,36.0],[116.5,34.6],[116.2,33.0],[115.0,32.2],[114.0,31.8],[113.5,32.5],[111.5,32.6]],
"江苏省":[[116.5,34.6],[118.0,34.7],[119.5,35.0],[119.2,34.4],[120.5,33.0],[121.8,32.0],[121.5,31.0],[121.0,30.9],[119.5,31.0],[118.5,31.2],[117.5,31.7],[116.2,33.0]],
"上海市":[[121.0,30.9],[121.0,31.5],[121.9,31.7],[122.0,31.0],[121.5,30.8]],
"浙江省":[[118.5,31.2],[119.5,31.0],[121.0,30.9],[122.0,30.3],[121.7,29.0],[120.5,27.6],[119.0,27.0],[118.2,28.0],[118.0,29.5]],
"安徽省":[[114.0,31.8],[115.0,32.2],[116.2,33.0],[117.5,31.7],[118.5,31.2],[119.3,30.8],[118.5,29.8],[117.5,29.6],[116.5,29.5],[115.5,30.0],[114.5,30.5]],
"湖北省":[[111.0,32.6],[113.5,32.5],[114.0,31.8],[114.5,30.5],[116.0,30.0],[116.1,29.5],[114.5,29.0],[113.0,29.4],[111.5,29.5],[110.0,30.0],[109.0,31.0],[108.5,31.5],[110.0,32.5]],
"湖南省":[[108.5,31.5],[110.0,32.5],[111.5,29.5],[113.0,29.4],[114.5,29.0],[113.8,27.5],[114.5,25.5],[113.0,24.5],[111.5,25.0],[110.0,25.5],[109.5,27.0],[108.5,28.0]],
"江西省":[[114.0,29.5],[116.1,29.5],[117.0,28.5],[118.5,28.5],[118.5,27.5],[117.5,26.5],[116.0,24.8],[114.5,24.5],[113.8,25.5],[114.5,27.0]],
"福建省":[[118.2,28.0],[118.5,28.5],[119.5,27.5],[120.5,27.0],[120.5,26.0],[119.5,25.0],[118.5,24.2],[117.3,23.5],[116.5,24.5],[117.5,26.5],[118.0,27.0]],
"广东省":[[111.5,25.0],[113.0,24.5],[114.5,24.5],[116.5,24.5],[117.3,23.5],[116.0,22.8],[114.5,22.2],[114.0,22.5],[113.5,22.2],[112.5,21.5],[110.5,21.2],[110.0,22.0],[111.0,23.5]],
"广西壮族自治区":[[104.5,23.5],[106.0,25.0],[108.0,26.5],[110.0,25.5],[111.5,25.0],[111.0,23.5],[110.0,22.0],[109.5,21.5],[108.5,21.5],[107.0,21.5],[106.5,22.8]],
"海南省":[[108.6,19.2],[109.5,20.1],[110.5,20.1],[111.0,19.6],[110.5,18.2],[109.0,18.2],[108.4,18.7]],
"四川省":[[101.0,32.5],[103.0,33.5],[104.0,33.0],[105.5,33.0],[107.0,32.5],[108.5,31.5],[108.0,30.0],[106.5,29.0],[105.5,28.2],[104.5,28.0],[103.0,27.3],[101.5,26.5],[100.5,28.5],[99.0,30.0],[98.5,31.5]],
"重庆市":[[105.5,33.0],[107.0,32.5],[109.0,31.5],[110.0,30.0],[109.0,29.0],[108.0,28.3],[106.5,29.0],[105.5,30.0]],
"贵州省":[[104.5,28.0],[105.5,28.2],[108.0,28.3],[109.0,29.0],[109.5,27.0],[108.5,25.5],[107.0,24.8],[105.5,25.0],[104.5,26.0],[104.0,27.0]],
"云南省":[[97.5,28.3],[100.5,29.2],[101.5,27.5],[103.0,27.3],[104.5,26.0],[105.5,25.0],[104.5,23.2],[103.0,22.4],[101.5,21.2],[99.5,22.0],[98.5,23.5],[97.5,24.5],[98.0,26.5]],
"辽宁省":[[119.5,42.5],[121.0,42.5],[122.5,42.4],[124.0,41.0],[125.2,41.0],[125.3,40.0],[124.0,40.0],[121.5,39.0],[121.0,38.8],[120.0,40.0],[119.5,40.5]],
"吉林省":[[121.0,45.5],[124.0,45.5],[126.0,45.0],[128.0,45.0],[130.5,44.0],[131.5,43.0],[130.5,42.3],[128.0,41.5],[126.0,41.0],[125.2,41.0],[124.0,41.0],[122.5,42.4],[121.5,43.5]],
"黑龙江省":[[121.0,51.0],[124.0,49.5],[125.5,51.0],[127.5,52.5],[130.5,51.0],[134.5,48.5],[135.0,47.0],[133.0,45.2],[131.5,43.0],[130.5,44.0],[128.0,45.0],[126.0,45.0],[124.0,45.5],[121.0,45.5]]
}''')


# ===========================================================================
def build_payload(ds: Dataset, checks=None) -> Dict[str, Any]:
    geo = _geo()
    city_xy = geo.get("cities", {})
    prov_xy = geo.get("provinces", {})

    plants_out = []
    for p in ds.plants.values():
        lat, lon, precision = p.lat, p.lon, p.coord_precision
        if lat is None or lon is None:
            for key in (p.district and f"{p.city}{p.district}", p.city, p.park):
                if key and key in city_xy:
                    lat, lon = city_xy[key]; precision = "city"; break
            if lat is None:
                base = p.city.replace("市", "").replace("区", "")
                for k, v in city_xy.items():
                    if base and base in k:
                        lat, lon = v; precision = "city"; break
        if lat is None and p.province in prov_xy:
            lat, lon = prov_xy[p.province]["lat"], prov_xy[p.province]["lon"]; precision = "province"
        e = ds.entities.get(p.entity_id)
        g = ds.groups.get(e.group_id) if e else None
        plants_out.append({
            "id": p.plant_id, "name": p.name, "entity_id": p.entity_id,
            "entity": e.name if e else "", "group_id": g.group_id if g else "",
            "group": g.short_name if g else "", "province": p.province, "city": p.city,
            "district": p.district, "park": p.park, "lat": lat, "lon": lon,
            "precision": precision, "region": REGION_MAP.get(p.province, "其他"),
            "address": p.registered_address, "location": p.location,
        })

    units_out = []
    for u in ds.units:
        p = ds.plants.get(u.plant_id)
        e = ds.entities.get(p.entity_id) if p else None
        g = ds.groups.get(e.group_id) if e else None
        s = ds.sources.get(u.source_id)
        units_out.append({
            "uid": u.uid, "plant_id": u.plant_id, "plant": p.name if p else u.plant_id,
            "province": p.province if p else "", "city": p.city if p else "",
            "region": REGION_MAP.get(p.province, "其他") if p else "",
            "entity_id": u.entity_id, "entity": e.name if e else "",
            "group_id": g.group_id if g else "", "group": g.short_name if g else "",
            "product": u.product, "grade_class": u.grade_class,
            "basis": u.basis, "basis_label": BASIS_LABELS.get(u.basis, u.basis),
            "capacity": u.capacity, "capacity_note": u.capacity_note,
            "capacity_year": u.capacity_year, "route": u.route,
            "route_label": ROUTE_LABELS.get(u.route, u.route), "route_note": u.route_note,
            "start_year": u.start_year, "status": u.status,
            "status_label": STATUS_LABELS.get(u.status, u.status), "status_note": u.status_note,
            "integrated": u.integrated_calcium_carbide, "source_id": u.source_id,
            "source_title": s.title if s else "", "source_url": s.url if s else "",
            "source_type": s.pub_type if s else "", "source_date": s.date if s else "",
            "confidence": u.confidence, "confidence_label": CONFIDENCE_LABELS.get(u.confidence, ""),
        })

    groups_out = []
    for g in ds.groups.values():
        ents = ds.entities_of_group(g.group_id)
        plants = [p for e in ents for p in ds.plants_of_entity(e.entity_id)]
        groups_out.append({
            "id": g.group_id, "name": g.name, "short": g.short_name,
            "controller": g.ultimate_controller, "type": g.group_type, "note": g.note,
            "entities": [{"id": e.entity_id, "name": e.name, "short": e.short_name,
                          "stock": e.stock_code, "ownership": e.ownership, "type": e.entity_type,
                          "code": e.unified_code, "verified_by": e.verified_by}
                         for e in ents],
            "plant_ids": [p.plant_id for p in plants],
            "provinces": sorted({p.province for p in plants}),
        })

    proj_out = []
    for pr in ds.projects:
        p = ds.plants.get(pr.plant_id)
        e = ds.entities.get(pr.entity_id)
        g = ds.groups.get(e.group_id) if e else None
        pv = pr.province or (p.province if p else "")
        proj_out.append({
            "id": pr.project_id, "name": pr.name, "entity": e.name if e else "",
            "group": g.short_name if g else "", "plant": p.name if p else "",
            "province": pv, "city": pr.city or (p.city if p else ""),
            "region": REGION_MAP.get(pv, "其他"),
            "capacity": pr.capacity, "capacity_note": pr.capacity_note,
            "route": pr.route, "route_label": ROUTE_LABELS.get(pr.route, pr.route),
            "stage": pr.stage, "stage_label": PROJECT_STAGE_LABELS.get(pr.stage, pr.stage),
            "expected_year": pr.expected_year, "expected_period": pr.expected_period,
            "retired": pr.retired_capacity, "replacement_note": pr.replacement_note,
            "capex": pr.capex, "timeline": pr.timeline, "source_ids": pr.source_ids,
            "net": (pr.capacity - (pr.retired_capacity or 0)) if pr.capacity is not None else None,
            "confidence": pr.confidence, "note": pr.note,
        })

    sources_out = [{"id": s.source_id, "title": s.title, "type": s.pub_type, "org": s.org,
                    "date": s.date, "url": s.url, "confidence": s.confidence,
                    "confidence_label": CONFIDENCE_LABELS.get(s.confidence, "")}
                   for s in ds.sources.values()]

    agg_all = {}
    for basis in BASIS_CAPACITY + (BASIS_ACTUAL,):
        a = Aggregator(ds, basis=basis)
        rows = a.rows()
        if not rows and basis != BASIS_DESIGN:
            agg_all[basis] = None
            continue
        total = a.total()
        by_group = a.by_group()
        h = hhi(by_group.values())
        agg_all[basis] = {
            "basis_label": BASIS_LABELS[basis], "total": round(total, 2), "count_units": len(rows),
            "count_plants": len(a.by_plant()), "count_entities": len(a.by_entity()),
            "count_groups": len([k for k in by_group if k != "__ungrouped__"]),
            "by_group": {k: round(v, 2) for k, v in by_group.items()},
            "by_entity": {k: round(v, 2) for k, v in a.by_entity().items()},
            "by_plant": {k: round(v, 2) for k, v in a.by_plant().items()},
            "by_province": {k: round(v, 2) for k, v in a.by_province().items()},
            "by_route": {k: round(v, 2) for k, v in a.by_route().items()},
            "by_region": {k: round(v, 2) for k, v in a.by_region(REGION_MAP).items()},
            "cr1": cr_n(by_group.values(), 1), "cr3": cr_n(by_group.values(), 3),
            "cr5": cr_n(by_group.values(), 5), "cr10": cr_n(by_group.values(), 10),
            "hhi": h, "hhi_label": concentration_label(h),
            "cr5_entity": cr_n(a.by_entity().values(), 5), "hhi_entity": hhi(a.by_entity().values()),
            "unit_ids": a.unit_ids(),
        }

    pipe = {}
    for st in PROJECT_STAGE_LABELS:
        items = [p for p in proj_out if p["stage"] == st]
        if not items:
            continue
        gross = sum(x["capacity"] for x in items if x["capacity"])
        retired = sum(x["retired"] for x in items if x["retired"])
        rs: Dict[str, float] = {}
        for x in items:
            if x["capacity"]:
                rs[x["route"]] = round(rs.get(x["route"], 0) + x["capacity"], 2)
        pipe[st] = {"label": PROJECT_STAGE_LABELS[st], "count": len(items), "gross": round(gross, 2),
                    "retired": round(retired, 2), "net": round(gross - retired, 2) if gross else None,
                    "weight": PIPELINE_WEIGHTS.get(st),
                    "route_split": rs, "ids": [x["id"] for x in items]}

    by_year: Dict[str, Dict[str, Any]] = {}
    for p in proj_out:
        if p["stage"] in PIPELINE_WEIGHTS and p["capacity"]:
            y = str(p["expected_year"] or "未定")
            d = by_year.setdefault(y, {"gross": 0.0, "retired": 0.0, "carbide": 0.0,
                                       "ethylene": 0.0, "count": 0})
            d["gross"] += p["capacity"]
            d["retired"] += p["retired"] or 0
            if p["route"] == "carbide":
                d["carbide"] += p["capacity"]
            elif p["route"] == "ethylene":
                d["ethylene"] += p["capacity"]
            d["count"] += 1
    for y, d in by_year.items():
        for k in ("gross", "retired", "carbide", "ethylene"):
            d[k] = round(d[k], 2)
        d["net"] = round(d["gross"] - d["retired"], 2)

    return {"meta": ds.meta, "product": ds.product, "plants": plants_out, "units": units_out,
            "groups": groups_out, "projects": proj_out, "sources": sources_out, "agg": agg_all,
            "pipeline": pipe, "by_year": dict(sorted(by_year.items())),
            "benchmarks": ds.benchmarks, "gaps": ds.gaps, "notes": ds.notes,
            "checks": checks or [],
            "geo": {"provinces": CHINA_PROVINCES, "region_map": REGION_MAP,
                    "prov_center": {k: [v["lat"], v["lon"]] for k, v in prov_xy.items()}}}


# ===========================================================================
def render_body(ds: Dataset, payload: Dict[str, Any]) -> str:
    prod = ds.product.get("name", "产品")
    short = ds.product.get("short", "产品")
    year = ds.product.get("base_year", "")
    meta = ds.meta
    agg = payload["agg"]["design"]
    unit_n = len(ds.units)
    plant_n = len(ds.plants)
    ent_n = len(ds.entities)
    grp_n = len(ds.groups)
    proj_n = len(ds.projects)
    src_n = len(ds.sources)
    checks = payload["checks"]
    n_err = sum(1 for c in checks if c["severity"] == "ERROR")
    n_warn = sum(1 for c in checks if c["severity"] == "WARN")

    def kpi(cls, kid, label, value, detail=""):
        return (f'<div class="kpi {cls}"><div class="k">{label}</div>'
                f'<div class="v" id="{kid}">{value}</div><div class="d" id="{kid}-d">{detail}</div></div>')

    html = []
    A = html.append

    # ---------------- 顶栏 ----------------
    A(f'''<div class="topbar"><div class="topbar-in">
  <div class="brand"><span class="dot"></span>{short} 产能分布<small>PRODUCING CAPACITY MAP</small></div>
  <div class="tabs">
    <button class="tab on" data-tab="overview">01 全景</button>
    <button class="tab" data-tab="map">02 产能地图</button>
    <button class="tab" data-tab="company">03 企业与集团</button>
    <button class="tab" data-tab="units">04 装置明细</button>
    <button class="tab" data-tab="project">05 在建拟建</button>
    <button class="tab" data-tab="basis">06 口径与校验</button>
    <button class="tab" data-tab="source">07 数据与来源</button>
  </div>
  <div class="topmeta">
    <span>数据年度 <b>{year}</b></span>
    <span>截止 <b>{meta.get("cutoff","")}</b></span>
    <span>装置 <b>{unit_n}</b></span>
    <span>来源 <b>{src_n}</b></span>
  </div>
</div></div>''')

    A(f'<div class="wrap"><div class="hero">')
    A(f'<h1>中国 <em>{prod}</em> 主要生产企业与产能分布</h1>')
    A(f'<div class="sub">{meta.get("sample_scope","")}</div>')
    A('<div class="badges">')
    A(f'<span class="badge info">统计基期 {year}</span>')
    A(f'<span class="badge">{plant_n} 个生产基地</span>')
    A(f'<span class="badge">{ent_n} 个法人主体</span>')
    A(f'<span class="badge">{grp_n} 个企业集团</span>')
    A(f'<span class="badge">{unit_n} 条装置记录</span>')
    A(f'<span class="badge">{proj_n} 个在建/拟建项目</span>')
    A(f'<span class="badge">{src_n} 条来源</span>')
    if n_err:
        A(f'<span class="badge warn">校验 ERROR {n_err} 项</span>')
    if n_warn:
        A(f'<span class="badge warn">校验 WARN {n_warn} 项</span>')
    A('</div></div>')

    # ---------------- 01 全景 ----------------
    A('<div class="tab-page" id="tab-overview">')
    A('<div class="filters">')
    A('<span class="lbl">口径</span>')
    A('<div class="seg">')
    for b in ("design", "effective", "approved", "actual"):
        on = " on" if b == "design" else ""
        avail = "" if payload["agg"].get(b) else " disabled"
        A(f'<button data-basis="{b}" class="{on.strip()}"{avail}>{BASIS_LABELS.get(b,b)}</button>')
    A('</div>')
    A('<span class="lbl">筛选</span>')
    A('<select id="f-group"><option value="">全部集团</option></select>')
    A('<select id="f-prov"><option value="">全部省份</option></select>')
    A('<select id="f-route"><option value="">全部工艺</option>'
      '<option value="carbide">电石法</option><option value="ethylene">乙烯法</option>'
      '<option value="mixed">电石+乙烯</option><option value="unknown">未核实</option></select>')
    A('<select id="f-status"><option value="">全部状态</option>'
      '<option value="running">在产</option><option value="idle">长期停车</option>'
      '<option value="maintenance">检修</option><option value="unknown">未核实</option></select>')
    A('<input type="search" id="f-q" placeholder="搜索企业/基地/产品…" style="width:190px">')
    A('<button class="chip" id="f-reset">重置</button>')
    A('<span class="filter-count" id="active-filters"></span>')
    A('</div>')

    A('<div class="kpis">')
    A(kpi("e", "kpi-cap", "样本产能合计", "—", "口径：设计产能 · 加载中"))
    A(kpi("g", "kpi-ents", f'{grp_n} / {ent_n}', "样本集团数 / 法人主体数"))
    A(kpi("g", "kpi-cr5", "—", "CR5（集团口径，样本内）"))
    A(kpi("c", "kpi-route", "—", "电石法占比（按产能）"))
    A(kpi("m", "kpi-cov", meta.get("coverage", "—"), meta.get("coverage_note", "样本合计 ≠ 全国总产能")))
    A('</div>')

    A('<div class="callout warn"><h5>口径提示 · 使用前必读</h5>'
      f'全国 {short} 产能存在多套公开口径（3,088 / 3,017 / 3,038 万吨等），差异来自①是否含糊状树脂、'
      '②是否含长期停车装置、③统计时点。本报告<b>并列展示、不取平均</b>；'
      '下方所有图表均为<b>样本口径</b>，样本合计 <b>不等于</b>全国总产能。详见「06 口径与校验」。</div>')

    A('<div class="grid2">')
    A('<div class="card"><div class="card-h"><h3>集团产能比较（Top 12）</h3>'
      '<span class="sub">点击条形查看集团 → 法人 → 基地 → 装置</span></div>'
      '<div id="bar-group"></div></div>')
    A('<div class="card"><div class="card-h"><h3>工艺路线构成</h3>'
      '<span class="sub">电石法 / 乙烯法 / 未核实</span></div><div id="donut-route"></div></div>')
    A('</div>')

    A('<div class="grid2">')
    A('<div class="card"><div class="card-h"><h3>省级产能分布</h3>'
      '<span class="sub">按产能排序 · 点击筛选省份</span></div><div id="bar-prov"></div></div>')
    A('<div class="card"><div class="card-h"><h3>省级产能 · 按工艺堆叠</h3>'
      '<span class="sub">橙=电石法、蓝=乙烯法</span></div><div id="stack-prov"></div></div>')
    A('</div>')
    A('<div class="grid2">')
    A('<div class="card"><div class="card-h"><h3>产业带（区域）结构</h3>'
      '<span class="sub">西北 / 华北 / 华东 / 华中 / 华南 / 西南</span></div>'
      '<div id="bar-region"></div></div>')
    A('<div class="card"><div class="card-h"><h3>产品等级构成</h3>'
      '<span class="sub">通用树脂 / 专用料 / 糊树脂 / 特种树脂</span></div>'
      '<div id="bar-grade"></div></div>')
    A('</div>')
    A('</div>')  # tab-overview

    # ---------------- 02 地图 ----------------
    A('<div class="tab-page hide" id="tab-map">')
    A('<div class="sec"><div class="sec-h"><h2><span class="num">02</span>企业产能地图</h2>'
      '<div class="hint">气泡面积 ∝ 基地产能；颜色代表主导工艺路线。点击气泡查看企业 / 基地 / 装置 / 来源，'
      '点击省份筛选。坐标为厂址或城市级，非测绘精度。</div></div>')
    A('<div class="card">')
    A('<div class="card-h"><h3>中国 PVC 产能空间分布</h3>'
      '<span class="sub">样本口径 · 随筛选联动</span>'
      '<div class="right"><span class="map-legend" style="position:static;display:none"></span></div></div>')
    A('<div class="mapwrap" id="mapwrap"><svg id="map" xmlns="http://www.w3.org/2000/svg"></svg>'
      '<div class="map-tip" id="maptip"></div>'
      '<div class="map-legend">'
      '<div style="color:#8aa6c4;margin-bottom:2px">工艺路线</div>'
      '<div class="row"><span class="dotl" style="background:#ff7a45"></span>电石法</div>'
      '<div class="row"><span class="dotl" style="background:#2fb4ff"></span>乙烯法</div>'
      '<div class="row"><span class="dotl" style="background:#b084ff"></span>电石+乙烯</div>'
      '<div class="row"><span class="dotl" style="background:#7d8ea6"></span>未核实</div>'
      '<div style="color:#8aa6c4;margin:6px 0 2px">气泡大小 = 基地产能</div>'
      '</div></div>')
    A('<div class="small muted" style="margin-top:10px">底图为省级简化轮廓，仅用于产能空间分布示意，'
      '不作为行政边界依据。坐标精度 city 级的气泡在同一个城市内可能重叠。</div>')
    A('</div>')
    A('</div>')
    A('</div>')

    # ---------------- 03 企业 ----------------
    A('<div class="tab-page hide" id="tab-company">')
    A('<div class="sec"><div class="sec-h"><h2><span class="num">03</span>企业集团产能比较</h2>'
      '<div class="hint">集团合计已合并其全部下属法人，不得再与子公司产能相加。点击行查看关系树与装置。</div></div>')
    A('<div class="card tight"><div class="card-h" style="padding:14px 16px 0">'
      '<h3>集团 → 法人 → 基地 → 装置</h3>'
      f'<span class="sub">共 <b id="group-count">0</b> 个集团有产能</span></div>')
    A('<div class="tbl-wrap"><table id="tbl-group"><thead><tr>'
      '<th class="num nosort">#</th><th>集团 / 全称</th><th>实际控制人 / 性质</th>'
      '<th class="num">产能(万吨/年)</th><th class="num">占样本</th><th class="num">法人数</th>'
      '<th class="num">基地数</th><th>覆盖省份</th><th>工艺构成</th>'
      '</tr></thead><tbody id="tb-group"></tbody></table></div></div>')
    A('</div>')
    A('</div>')

    # ---------------- 04 装置 ----------------
    A('<div class="tab-page hide" id="tab-units">')
    A('<div class="sec"><div class="sec-h"><h2><span class="num">04</span>装置明细表</h2>'
      '<div class="hint">一行 = 一个装置的一条产能事实，是全报告的<b>唯一事实层</b>；'
      '切换口径会改变参与汇总的装置集合。点击行查看基地全貌。</div></div>')
    A('<div class="card tight"><div class="card-h" style="padding:14px 16px 0">'
      '<h3>装置级明细</h3>'
      '<span class="sub"><b id="unit-count">0</b> 条 · 合计 <b id="unit-sum">0</b> 万吨/年 · '
      '口径 <b id="unit-basis">设计产能</b></span></div>')
    A('<div class="tbl-wrap"><table><thead><tr>'
      '<th class="nosort">装置ID</th><th>基地 / 法人</th><th>省 / 市</th><th>产品 / 等级</th>'
      '<th>工艺</th><th class="num">产能</th><th>口径</th><th class="num">投产年</th>'
      '<th>状态</th><th>来源 / 可信度</th>'
      '</tr></thead><tbody id="tb-unit"></tbody></table></div></div>')
    A('</div></div>')

    # ---------------- 05 项目 ----------------
    A('<div class="tab-page hide" id="tab-project">')
    A('<div class="sec"><div class="sec-h"><h2><span class="num">05</span>在建、拟建与新投产项目</h2>'
      '<div class="hint">增量与存量严格分离。净新增 = 规模 − 置换退出；无法确认置换的记为「待确认」，不进基准预测。</div></div>')
    A('<div class="card"><div class="card-h"><h3>项目流水线</h3>'
      '<span class="sub">按建设阶段 · 毛产能（万吨/年）</span></div><div class="pipe" id="pipe"></div>')
    A('<div class="hr"></div>')
    A('<div class="card-h"><h3>按预计投产年份的增量</h3>'
      '<span class="sub">橙色=电石法、蓝色=乙烯法；只计 stage 属于增量的项目</span></div>')
    A('<div id="year-chart"></div>')
    A('<div class="callout info" style="margin-top:14px">毛新增 ≠ 净新增 ≠ 实际可增量。'
      '加权可增量（在建×0.85、试车×0.95、环评×0.45、备案×0.25、拟建×0.10）仅为情景参考，不是预测。</div>')
    A('</div>')
    A('<div class="sec"><div class="card tight"><div class="tbl-wrap" style="max-height:none">'
      '<table><thead><tr><th>项目 / 建设单位</th><th>省 / 市</th><th>工艺</th><th class="num">规模</th>'
      '<th>阶段</th><th>预计投产</th><th class="num">置换退出</th><th class="num">净增</th><th>来源</th>'
      '</tr></thead><tbody id="tb-proj"></tbody></table></div></div></div>')
    A('</div>')

    # ---------------- 06 口径与校验 ----------------
    A('<div class="tab-page hide" id="tab-basis">')
    A('<div class="sec"><div class="sec-h"><h2><span class="num">06</span>统计口径、集中度与重复统计校验</h2>'
      '<div class="hint">这一节回答：行业产能到底怎么统计、不同口径差在哪、数据有没有被重复计入。</div></div>')

    A('<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>全国产能口径并列对照</h3>'
      '<span class="sub">多套公开数字并列，不取平均</span></div>')
    A('<div class="tbl-wrap"><table><thead><tr><th>编号</th><th>指标</th><th class="num">数值</th><th>单位</th>'
      '<th>年份</th><th>来源机构</th><th>等级</th><th>定义 / 说明</th></tr></thead>'
      '<tbody id="tb-bench"></tbody></table></div></div>')

    A('<div class="grid2">')
    A('<div class="card"><div class="card-h"><h3>集中度指标（样本口径）</h3></div>')
    A(f'<div class="grid-mini">')
    for label, val, note in [
        ("CR1（最大集团）", f'{agg.get("cr1","—")}%', "首位集团产能占样本比"),
        ("CR3", f'{agg.get("cr3","—")}%', "前三集团合计占比"),
        ("CR5", f'{agg.get("cr5","—")}%', "前五集团合计占比"),
        ("CR10", f'{agg.get("cr10","—")}%', "前十集团合计占比"),
        ("HHI（集团）", f'{agg.get("hhi","—")}', agg.get("hhi_label", "")),
        ("CR5（法人）", f'{agg.get("cr5_entity","—")}%', "以单一法人为单位，通常低于集团口径"),
        ("HHI（法人）", f'{agg.get("hhi_entity","—")}', "按法人计算的集中度"),
        ("平均单厂规模", f'{(agg.get("total",0)/max(1,agg.get("count_plants",1))):.1f}', "万吨/年·厂"),
    ]:
        A(f'<div class="mini"><div class="t">{label}</div><div class="v">{val}</div>'
          f'<div class="d">{note}</div></div>')
    A('</div>')
    A('<div class="callout warn" style="margin-top:14px">集中度是<b>样本口径</b>。样本覆盖率低于 70% 时，'
      '实际集中度可能被低估，因为未覆盖的中小企业未被计入分母。</div>')
    A('</div>')

    A('<div class="card"><div class="card-h"><h3>统计口径是否包含联产 / 副产 / 长期停车 / 不同等级</h3></div>')
    A('<ul class="tight" style="color:#a9bcd6;font-size:12.5px">')
    for r in ds.notes.get("basis_rules", []):
        A(f"<li>{r}</li>")
    A('</ul></div>')
    A('</div>')

    A('<div class="sec"><div class="card tight"><div class="card-h" style="padding:14px 16px 0">'
      '<h3>重复统计与口径一致性自动校验</h3>'
      f'<span class="sub">ERROR <b style="color:#ff5c5c">{n_err}</b> · WARN <b style="color:#ffb020">{n_warn}</b> · '
      f'规则 R1–R14</span></div>')
    A('<div class="tbl-wrap"><table><thead><tr><th>规则</th><th>级别</th><th>对象</th>'
      '<th>校验信息</th><th>处理建议</th></tr></thead><tbody id="tb-check"></tbody></table></div></div></div>')
    A('</div>')

    # ---------------- 07 来源 ----------------
    A('<div class="tab-page hide" id="tab-source">')
    A('<div class="sec"><div class="sec-h"><h2><span class="num">07</span>数据来源与缺口</h2>'
      '<div class="hint">A=一手文件（年报/公告/评级/环评/协会）；B=权威二手；C=一般二手；D=未核实。</div></div>')
    A('<div class="card tight" style="margin-bottom:16px"><div class="tbl-wrap"><table><thead><tr>'
      '<th>编号</th><th>类型</th><th>标题</th><th>发布机构</th><th>日期</th><th>等级</th>'
      '</tr></thead><tbody id="tb-src"></tbody></table></div></div>')
    A('<div class="card tight"><div class="card-h" style="padding:14px 16px 0">'
      '<h3>数据缺口清单</h3><span class="sub">缺口如实登记，禁止用均值/邻年/比例外推补齐</span></div>'
      '<div class="tbl-wrap"><table><thead><tr><th>编号</th><th>缺口项</th><th>影响范围</th>'
      '<th>当前状态</th><th>补齐方式</th><th>优先级</th></tr></thead><tbody id="tb-gap"></tbody></table></div></div>')
    A('</div>')

    A(f'<div class="foot">{meta.get("title","")} · 数据截止 {meta.get("cutoff","")} · '
      f'本报告所有产能为公开信息披露口径，样本合计不等于全国总产能；'
      '任何数字在引用前请核对来源年份与口径。生成于 ' + meta.get("generated", "") + '。</div>')
    A('</div>')

    # ---------------- 抽屉 ----------------
    A('<div class="overlay" id="overlay"></div>')
    A('<div class="drawer" id="drawer"><div class="drawer-h"><h3 id="drawer-title">详情</h3>'
      '<button class="x" id="drawer-x">×</button></div>'
      '<div class="drawer-b" id="drawer-body"></div></div>')
    A('<script>/* placeholder */</script>')
    return "\n".join(html)


def render(ds: Dataset, out_path: str, checks=None) -> str:
    payload = build_payload(ds, checks)
    title = f"{ds.product.get('short','产品')} 生产企业与产能分布研究报告"
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script id="payload" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>
<style>
{_read("style.css")}
</style>
</head>
<body>
{render_body(ds, payload)}
<script>
{_read("app.js")}
</script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    from pcd_model import load
    d = load(args.data)
    findings = DupChecker(d).run()
    print(render(d, args.out, [{"rule": f.rule, "severity": f.severity, "subject": f.subject,
                                "message": f.message, "fix": f.fix} for f in findings]))
