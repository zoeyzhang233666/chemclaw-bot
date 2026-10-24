#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers: load/normalize data.json, safe names, source maps."""
from __future__ import annotations

import json
import os
import re

DEFAULT_PROCESS_COLORS = ["#b45309", "#1f5eff", "#067647", "#6d28d9", "#0e7490", "#be123c"]
DEFAULT_DD_ITEMS = [
    {"label": "营业执照\n/股权", "hint": "营业执照、股权穿透、统一社会信用代码"},
    {"label": "生产许可", "hint": "生产许可证/安全生产许可/排污许可（按行业）"},
    {"label": "质量体系", "hint": "ISO9001/14001/45001 或行业质量体系"},
    {"label": "准入/资质", "hint": "行业准入、交割品牌、客户认证或注册证明"},
    {"label": "近12月\nCOA", "hint": "至少 3 批 COA/出厂检验报告"},
    {"label": "产能/产量\n证明", "hint": "环评/公告/统计/审计报告"},
    {"label": "环保/排污", "hint": "排污许可、环保处罚、园区合规"},
    {"label": "安全/事故", "hint": "安全生产许可、事故/处罚记录"},
    {"label": "财务/涉诉", "hint": "审计报告、征信、重大诉讼"},
    {"label": "客户案例", "hint": "同行业/同规格客户与联系人"},
    {"label": "物流/码头", "hint": "到收货地的运输、码头/铁路专用线"},
    {"label": "合同/条款", "hint": "最小起订、账期、赔付、包装、巡检"},
    {"label": "样品/封样", "hint": "首样、封样、留样与复检规则"},
]


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|]+', "_", str(s or "")).strip(" .")
    s = re.sub(r"\s+", "_", s)
    return s[:120] or "chemical-second-source"


def source_map(D):
    return {s.get("id"): s for s in (D.get("sources") or []) if s.get("id")}


def find_source(D, sid):
    return source_map(D).get(sid)


def _norm_source(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, (list, tuple)) and len(x) >= 3:
        return {"name": x[0], "url": x[1], "grade": x[2], "date": x[3] if len(x) > 3 else ""}
    return {"name": str(x), "url": "", "grade": "C", "date": ""}


def _norm_spec(x):
    if isinstance(x, dict):
        return {"id": x.get("id") or x.get("key"), "label": x.get("label") or x.get("name"), "target": x.get("target") or x.get("spec") or ""}
    if isinstance(x, (list, tuple)) and len(x) >= 2:
        return {"id": x[0], "label": x[1], "target": x[2] if len(x) > 2 else ""}
    return {"id": str(x), "label": str(x), "target": ""}


def normalize(raw):
    """Accept both the canonical schema and a few legacy shapes.

    Canonical keys: meta / params / baseline / candidates / spec_items /
    spec_status / same_source / risks / actions / sources.
    """
    D = dict(raw or {})
    M = dict(D.get("meta") or {})
    M.setdefault("product", "目标化工品")
    M.setdefault("product_short", M["product"])
    M.setdefault("unit", "万吨/年")
    M.setdefault("asof", "")
    M.setdefault("buyer_site", "")
    M.setdefault("volume", "")
    M.setdefault("volume_t", 0)
    M.setdefault("volume_period", "月")
    M.setdefault("spec", "")
    M.setdefault("use_case", "")
    M.setdefault("scenario", "")
    M.setdefault("qualification_label", "准入 / 资质")
    M.setdefault("qualification_short", "准入")
    M.setdefault("grade_label", "等级 / 品牌")
    M.setdefault("near_km", 500)
    M.setdefault("distance_bands", [])
    M.setdefault("risk_categories", ["财务", "装置", "资质", "同源", "行业"])
    M.setdefault("same_source_note", "")
    M.setdefault("spec_note", "")
    M.setdefault("disclaimer", "本页为采购研究辅助材料，不构成供应商选择、替换或授标建议。")
    M.setdefault("action_window", "90 天")
    M.setdefault("fin_year", "")
    M.setdefault("output_year", "")
    M.setdefault("method_steps", [])
    M.setdefault("key_judgements", [])
    M.setdefault("dd_items", DEFAULT_DD_ITEMS)
    M.setdefault("stamp_note", "公开信息研究 · 非报价 · 非决策建议")

    # processes: accept strings or dicts
    procs = []
    for i, p in enumerate(M.get("processes") or []):
        if isinstance(p, str):
            p = {"name": p}
        procs.append({
            "name": p.get("name") or str(p),
            "color": p.get("color") or DEFAULT_PROCESS_COLORS[i % len(DEFAULT_PROCESS_COLORS)],
            "cost_score": int(p.get("cost_score") or 60),
        })
    M["processes"] = procs

    for key in ("method_steps", "key_judgements"):
        vals = []
        for x in (M.get(key) or []):
            if isinstance(x, str):
                vals.append({"label": "", "text": x})
            elif isinstance(x, dict):
                vals.append(x)
        M[key] = vals

    # dd_items
    dd = []
    for x in (M.get("dd_items") or DEFAULT_DD_ITEMS):
        if isinstance(x, str):
            dd.append({"label": x, "hint": ""})
        else:
            dd.append({"label": x.get("label") or x.get("name") or "", "hint": x.get("hint") or ""})
    M["dd_items"] = dd or DEFAULT_DD_ITEMS

    D["meta"] = M
    D["params"] = dict(D.get("params") or {})
    D["baseline"] = dict(D.get("baseline") or {})
    D["candidates"] = list(D.get("candidates") or D.get("suppliers") or [])
    D["spec_items"] = [_norm_spec(x) for x in (D.get("spec_items") or [])]
    D["spec_status"] = dict(D.get("spec_status") or {})
    D["same_source"] = list(D.get("same_source") or [])
    D["risks"] = list(D.get("risks") or [])
    D["actions"] = list(D.get("actions") or [])
    D["sources"] = [_norm_source(x) for x in (D.get("sources") or [])]

    # ensure source IDs and candidate IDs are stable strings
    for i, s in enumerate(D["sources"], 1):
        s.setdefault("id", f"SRC{i:02d}")
        s["id"] = str(s["id"])
        s.setdefault("grade", "C")
        s.setdefault("date", "")
    D["baseline"].setdefault("role", "现有供应商")
    for blk in [D["baseline"]] + D["candidates"]:
        if "qualified" not in blk and "jianmian" in blk:
            blk["qualified"] = bool(blk.get("jianmian"))
        if "grade" not in blk and "heavy" in blk:
            blk["grade"] = blk.get("heavy")
    for i, c in enumerate(D["candidates"], 1):
        c.setdefault("id", f"C{i:02d}")
        c["id"] = str(c["id"])
        c.setdefault("role", "备选")
        c.setdefault("evidence", [])
        c.setdefault("verify", [])
        c.setdefault("tags", c.get("highlights") or [])
    return D


def counts(D):
    M = D["meta"]
    cands = D["candidates"]
    near = [c for c in cands if _num(c.get("distance")) <= _num(M.get("near_km"))]
    qual = [c for c in cands if c.get("qualified")]
    fresh = [c for c in cands if c.get("new_plant")]
    return {
        "candidates": len(cands),
        "near": len(near),
        "qualified": len(qual),
        "new_plants": len(fresh),
        "same_groups": len(D.get("same_source") or []),
        "risks": len(D.get("risks") or []),
        "sources": len(D.get("sources") or []),
        "spec_items": len(D.get("spec_items") or []),
    }


def _num(x):
    try:
        return float(x)
    except Exception:
        return 0.0
