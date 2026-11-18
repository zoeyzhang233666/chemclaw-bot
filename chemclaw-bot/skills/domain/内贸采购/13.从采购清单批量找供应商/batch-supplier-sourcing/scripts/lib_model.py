# -*- coding: utf-8 -*-
"""batch_sourcing.model — 载入 project.json，注入规则口径，重算覆盖矩阵。"""
from __future__ import annotations

from lib_common import load_assets, load_json
from lib_match import apply_degrees, compute_coverage


def load_project(path):
    project = load_json(path)
    assets = load_assets()
    rules = assets["rules"]
    _meta = project.setdefault("_meta", {})
    _meta.setdefault("evidence_grades", {k: v for k, v in rules["evidence_grades"].items()})
    _meta.setdefault("identity_levels", rules["identity_levels"])
    _meta.setdefault("mat_view_levels", rules["mat_view_levels"])
    _meta.setdefault("degree_levels", rules["degree_levels"])
    _meta.setdefault("reliability_weight", rules["reliability_weight"])
    _meta.setdefault("scarcity_thresholds", rules["scarcity_thresholds"])
    _meta.setdefault("partially_spec_threshold", rules["partially_spec_threshold"])
    _meta.setdefault("grade_score", {k: v["score"] for k, v in rules["evidence_grades"].items()})
    # 只保留本次研究命中的证据等级
    used = {e["grade"] for e in project["evidence"]}
    _meta["grade_score"] = {k: v for k, v in _meta["grade_score"].items() if k in used}

    for e in project["evidence"]:
        g = e.get("grade", "E")
        e["grade_name"] = _meta["evidence_grades"].get(g, {}).get("name", "")
        e["grade_score"] = _meta["grade_score"].get(g, 20)
        e["hits_item"] = list(e.get("items") or [])

    for s in project["suppliers"]:
        s.setdefault("identity_note", _meta["identity_levels"].get(s["identity"], {}).get("note", ""))
        ev = [project["evidence_map"].get(e) for e in s.get("evidence_ids", [])]
        ev = [e for e in ev if e]
        s["evidence_refs"] = ev
        s["max_grade"] = min((e["grade"] for e in ev), default=None)
        s["evidence_count"] = len(ev)

    for it in project["items"]:
        it.setdefault("issues", [])
        it.setdefault("aliases", [])
    # 物料编码重映射（清单解析后人工调整编码时使用）
    remap = (_meta.get("code_remap") or {})
    if remap:
        for it in project["items"]:
            it["code"] = remap.get(it["code"], it["code"])
        for a in project.get("ambiguities", []):
            a["code"] = remap.get(a.get("code"), a.get("code"))
        for ev in project["evidence"]:
            if ev.get("items"):
                ev["items"] = [remap.get(c, c) for c in ev["items"]]
        for ln in project["links"]:
            ln["item_code"] = remap.get(ln["item_code"], ln["item_code"])
        project["evidence_map"] = {e["id"]: e for e in project["evidence"]}

    apply_degrees(project)
    item_side, supplier_side, multi, scarce = compute_coverage(project, project["items"])
    project["_calc"] = {
        "item_side": item_side,
        "supplier_side": {r["supplier_id"]: r for r in supplier_side},
        "supplier_rank": supplier_side,
        "multi": multi,
        "scarce": scarce,
    }
    return project, assets


def evidence_index(project):
    return {e["id"]: e for e in project["evidence"]}
