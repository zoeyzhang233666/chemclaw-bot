# -*- coding: utf-8 -*-
"""batch_sourcing.match — 物料—供应商覆盖矩阵、覆盖度计算、稀缺性判级。"""
from __future__ import annotations

from lib_common import fmt_num

IDENTITY_ORDER = ["S", "P", "G", "T", "I", "U"]


def _bump(bucket, key, link):
    """把一条关联并入覆盖汇总；同一企业的多个产品口径（如 I 型）做去重口径记录。"""
    if bucket.get(key) is None:
        bucket[key] = {"levels": set(), "links": []}
    bucket[key]["levels"].add(link["coverage"])
    bucket[key]["links"].append(link.get("link_id"))
    if bucket[key].get("identity") is None:
        bucket[key]["identity"] = link.get("identity")


def compute_coverage(project, items):
    """返回 (item_side, supplier_side, coverage_summary, scarce_list)。"""
    suppliers = {s["id"]: s for s in project["suppliers"]}
    links = project["links"]
    evidence = {e["id"]: e for e in project["evidence"]}
    grade_score = project["_meta"].get("grade_score") or {}

    by_item, by_sup = {}, {}
    for ln in links:
        s = suppliers.get(ln["supplier_id"])
        if not s:
            raise ValueError(f"链路引用了不存在企业: {ln['supplier_id']}")
        if ln.get("identity") and ln["identity"] != s["identity"]:
            ln["identity_note"] = f"该物料身份判为 {ln['identity']}（企业主身份 {s['identity']}）"
        by_item.setdefault(ln["item_code"], []).append(ln)
        by_sup.setdefault(ln["supplier_id"], []).append(ln)

    # ---------------- 物料侧
    item_side_list = []
    for it in items:
        lns = [l for l in by_item.get(it["code"], []) if l.get("coverage") != "none" and l.get("degree") != "not_covered"]
        adv_cur = [l for l in lns if l["identity"] == "S" and l["coverage"] in ("direct", "partial_spec", "disclose") and l["_deg"].get("current")]
        adv_ach = [l for l in lns if l["identity"] == "S" and l["coverage"] in ("direct", "partial_spec", "disclose") and l["_deg"].get("achievable")]
        trd_cur = [l for l in lns if l["identity"] in ("T", "I") and l["coverage"] in ("direct", "partial_spec", "disclose", "dist_only") and l["_deg"].get("current")]
        partial = [l for l in adv_cur if l["coverage"] in ("partial_spec", "disclose")]
        rec = {
            "item_code": it["code"],
            "item_name": it.get("name", ""),
            "item_form": it.get("form", ""),
            "candidate_count": len(lns),
            "degree_current": len([l for l in lns if l["_deg"].get("current")]),
            "degree_achievable": len([l for l in lns if l["_deg"].get("achievable")]),
            "degree_adv": len(adv_cur),
            "degree_adv_achievable": len(adv_ach),
            "trader_degree": len(trd_cur),
            "partial_spec_count": len(partial),
            "single_source_risk": "是" if len(adv_cur) <= 1 else "否",
        }
        thr = project["_meta"].get("scarcity_thresholds", {"few_adv": 2, "zero": 0})
        if rec["degree_adv"] == 0:
            rec["coverage_gap"] = "gap_zero"
            rec["gap_label"] = "无厂家覆盖"
            rec["severity"] = "P0"
        elif rec["degree_adv"] <= thr.get("few_adv", 2):
            rec["coverage_gap"] = "gap_thin"
            rec["gap_label"] = "厂家单一/不足"
            rec["severity"] = "P1"
        elif rec["degree_current"] <= thr.get("few_adv", 2) + project["_meta"].get("partially_spec_threshold", 2):
            rec["coverage_gap"] = "gap_spec"
            rec["gap_label"] = "规格或证据不足"
            rec["severity"] = "P1"
        else:
            rec["coverage_gap"] = "ok"
            rec["gap_label"] = "覆盖充分"
            rec["severity"] = "ok"
        adv_names = [suppliers[l["supplier_id"]].get("short", l["supplier_id"]) for l in adv_cur]
        rec["adv_names"] = adv_names
        rec["adv_achievable_names"] = [suppliers[l["supplier_id"]].get("short", l["supplier_id"]) for l in adv_ach]
        item_side_list.append(rec)

    # ---------------- 供应商侧
    supplier_side = []
    for sid, s in suppliers.items():
        lns = by_sup.get(sid, [])
        rel_scores, adv, partial, trd, ach = [], 0, 0, 0, 0
        for l in lns:
            deg = l["_deg"]
            if deg.get("current") and l["coverage"] != "dist_only":
                if l["identity"] == "S" and l["coverage"] in ("direct", "partial_spec", "disclose"):
                    adv += 1
                    if l["coverage"] in ("partial_spec", "disclose"):
                        partial += 1
                elif l["identity"] in ("T", "I"):
                    trd += 1
            if deg.get("current"):
                rel_scores.append(l["reliability_score"])
            if deg.get("achievable"):
                ach += 1
        multi_roles = sorted({(l.get("identity") or s["identity"]) for l in lns if l.get("degree") != "none"})
        supplier_side.append({
            "supplier_id": sid,
            "name": s["name"],
            "short": s.get("short", s["name"]),
            "identity": s["identity"],
            "province": s.get("province", ""),
            "current": adv + trd,
            "achievable": ach,
            "adv_current": adv,
            "partial_current": partial,
            "trader_current": trd,
            "avg_reliability": round(sum(rel_scores) / len(rel_scores), 1) if rel_scores else None,
            "linked_items": len(lns),
            "multi_roles": multi_roles,
            "multi_role_note": ("厂家与分销双角色（同集团/同企业一体）" if len(multi_roles) > 1 else
                                ("仅分销" if multi_roles in (["T"], ["I"]) else "")),
        })
    n_all = len(items) or 1
    for r in supplier_side:
        r["coverage_ratio"] = round(r["current"] / n_all * 100, 1)
        r["adv_achievable"] = len([l for l in by_sup.get(r["supplier_id"], [])
                                   if l.get("_deg", {}).get("achievable") and l.get("identity") == "S"])
    supplier_side.sort(key=lambda r: (-r["current"], -r["adv_current"], -(r["avg_reliability"] or 0)))

    # ---------------- 多物料覆盖（跨企业）
    item_side_map = {r["item_code"]: r for r in item_side_list}
    multi = []
    n_items = len(items)
    for r in supplier_side:
        if r["current"] < 2:
            continue
        codes = sorted({l["item_code"] for l in by_sup[r["supplier_id"]]
                        if l.get("_deg", {}).get("current") and l["coverage"] != "dist_only"})
        codes_all = sorted({l["item_code"] for l in by_sup[r["supplier_id"]] if l.get("_deg", {}).get("achievable")})
        main = [l for l in by_sup[r["supplier_id"]] if l.get("_deg", {}).get("current")]
        avg = round(sum(l["reliability_score"] for l in main) / len(main), 1) if main else None
        multi.append({
            "supplier_id": r["supplier_id"],
            "covered_items_current": [l["item_code"] for l in by_sup[r["supplier_id"]]
                                      if l.get("_deg", {}).get("current") and l["coverage"] != "dist_only"],
            "name": r["name"],
            "short": r["short"],
            "identity": r["identity"],
            "province": r["province"],
            "covered_items": codes,
            "achievable_items": codes_all,
            "current_count": len(codes),
            "achievable_count": len(codes_all),
            "coverage_ratio": round(len(codes) / n_items * 100, 1) if n_items else 0,
            "avg_reliability": avg,
            "combo_value": round(sum(1 for c in codes if item_side_map.get(c, {}).get("degree_adv", 9) <= 2), 1),
        })
    multi.sort(key=lambda m: (-m["current_count"], -m["achievable_count"]))

    # ---------------- 稀缺物料
    scarce = sorted([x for x in item_side_list if x["coverage_gap"] != "ok"],
                    key=lambda x: ({"P0": 0, "P1": 1}.get(x["severity"], 2), x["degree_adv"]))
    item_side = {r["item_code"]: r for r in item_side_list}
    return item_side, supplier_side, multi, scarce


def apply_degrees(project):
    """把每个关联的覆盖度标志展开成 current/achievable 布尔。"""
    lv = project["_meta"]["degree_levels"]
    w = project["_meta"]["reliability_weight"]
    for ln in project["links"]:
        conf = ln.get("confidence")
        if not conf:
            conf = "待确认" if ln["coverage"] in ("partial_spec", "disclose", "not_listed", "dist_only") else "已证实"
        level = ln.get("degree")
        counts = lv.get(level, {}).get("counts", False)
        cur = bool(counts and conf == "已证实" and ln.get("current_relation"))
        ach = bool(counts and (cur or conf != "已证实" or not ln.get("current_relation")) and ln.get("potential_relation"))
        if level == "not_recommended" or ln["coverage"] == "none":
            cur = ach = False
        ln["_deg"] = {"current": cur, "achievable": ach}
        ln["degree"] = level
        ln["confidence"] = conf
        ln["reliability_score"] = round(project["_meta"]["mat_view_levels"][ln["coverage"]]["score"]
                                        * w.get(ln.get("identity") or "U", 0.1), 1)
    return project
