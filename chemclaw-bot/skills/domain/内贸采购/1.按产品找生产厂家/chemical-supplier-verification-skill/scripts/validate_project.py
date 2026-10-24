#!/usr/bin/env python3
"""Validate a chemical-supplier-verification project.json.

Usage:
    python scripts/validate_project.py path/to/project.json [--strict]

Exit code 1 if errors; 0 if only warnings.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

VALID_LEVELS = {"直接-A", "直接-B", "间接-C", "仅工商-D"}
VALID_IDENTITIES = {"producer", "trader", "agent", "unknown"}
VALID_SPEC_STATUS = {"部分公开", "未公开", "待验证"}
VALID_GRADES = {"A", "B", "C", "D"}
VALID_PRIORITIES = {"P0", "P1", "P2"}


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def calc_composite(c: dict, weights: dict) -> float:
    return round(
        c.get("certainty", 0) * weights.get("certainty", 0)
        + c.get("spec_score", 0) * weights.get("spec", 0)
        + c.get("scale_score", 0) * weights.get("scale", 0)
        + c.get("distance_score", 0) * weights.get("distance", 0),
        1,
    )


def tier_for(score: float, tiers: list[dict]) -> str:
    for t in sorted(tiers, key=lambda x: x.get("min", 0), reverse=True):
        if score >= t.get("min", 0):
            return t.get("label", "")
    return ""


def validate(d: dict, strict: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    def warn(msg: str) -> None:
        warnings.append(msg)

    # top level
    for key in ["meta", "rfq", "specs", "sources", "companies", "traders", "conflicts", "gaps", "actions", "scoring"]:
        if key not in d:
            err(f"缺少顶层字段: {key}")
    if errors:
        return errors, warnings

    meta = d["meta"]
    for key in ["title", "brand", "product", "product_short", "application", "destination", "destination_short", "as_of", "capacity_unit", "quantity_unit", "sample_note"]:
        if not str(meta.get(key, "")).strip():
            err(f"meta.{key} 不能为空")
    if not meta.get("disclaimer"):
        warn("meta.disclaimer 为空；建议写明“仅作初筛/非报价”")

    rfq = d["rfq"]
    for key in ["title", "product", "destination"]:
        if not str(rfq.get(key, "")).strip():
            err(f"rfq.{key} 不能为空")
    for key in ["qty_month", "qty_year"]:
        if not is_num(rfq.get(key)) or rfq[key] <= 0:
            err(f"rfq.{key} 必须是正数")

    # specs
    specs = d["specs"]
    if not isinstance(specs, list) or not specs:
        err("specs 必须是非空数组")
        specs = []
    spec_ids = []
    for i, s in enumerate(specs):
        sid = s.get("id")
        if not sid:
            err(f"specs[{i}].id 为空")
        elif sid in spec_ids:
            err(f"specs.id 重复: {sid}")
        else:
            spec_ids.append(sid)
        for key in ["label", "requirement"]:
            if not str(s.get(key, "")).strip():
                err(f"specs[{i}].{key} 为空")
    if specs and not (6 <= len(specs) <= 12):
        warn(f"规格项为 {len(specs)} 项；建议 6–12 项，覆盖下游关键指标")

    # sources
    sources = d["sources"]
    source_ids = []
    for i, s in enumerate(sources):
        sid = s.get("id")
        if not sid:
            err(f"sources[{i}].id 为空")
        elif sid in source_ids:
            err(f"sources.id 重复: {sid}")
        else:
            source_ids.append(sid)
        for key in ["org", "title", "date", "used"]:
            if not str(s.get(key, "")).strip():
                err(f"sources[{i}].{key} 为空")
        if s.get("grade") not in VALID_GRADES:
            err(f"sources[{i}].grade 必须是 A/B/C/D")
        if s.get("grade") in {"A", "B"} and not str(s.get("url", "")).strip():
            warn(f"sources[{i}] 为 {s.get('grade')} 级但没有 URL")

    # companies
    companies = d["companies"]
    if not isinstance(companies, list) or not companies:
        err("companies 必须是非空数组")
        companies = []
    company_ids = []
    company_names = []
    ranks = []
    for i, c in enumerate(companies):
        label = c.get("name") or f"companies[{i}]"
        cid = c.get("id")
        if not cid:
            err(f"{label}: id 为空")
        elif cid in company_ids:
            err(f"companies.id 重复: {cid}")
        else:
            company_ids.append(cid)
        if c.get("name") in company_names:
            warn(f"公司名重复: {c.get('name')}")
        company_names.append(c.get("name"))
        for key in ["name", "full_name", "founded", "hq", "process", "products", "capacity_year", "action"]:
            if str(c.get(key, "")).strip() == "":
                err(f"{label}: {key} 为空")
        if c.get("identity") not in VALID_IDENTITIES:
            err(f"{label}: identity 必须是 producer/trader/agent/unknown")
        if c.get("identity") != "producer":
            err(f"{label}: 非 producer 不应出现在 companies；请移到 traders")
        if not is_num(c.get("capacity")) or c["capacity"] <= 0:
            err(f"{label}: capacity 必须是正数")
        if c.get("output") is not None and (not is_num(c.get("output")) or c["output"] < 0):
            err(f"{label}: output 必须是非负数或 null")
        if c.get("output") is not None and not str(c.get("output_year", "")).strip():
            err(f"{label}: 有 output 但 output_year 为空")
        for key in ["certainty", "spec_score", "availability"]:
            if not is_num(c.get(key)) or not (0 <= c[key] <= 100):
                err(f"{label}: {key} 必须是 0–100 数字")

        plants = c.get("plants") or []
        if not plants:
            err(f"{label}: plants 不能为空")
        for j, p in enumerate(plants):
            pname = p.get("name") or f"{label}.plants[{j}]"
            for key in ["name", "province", "city", "address", "capacity_year", "process"]:
                if not str(p.get(key, "")).strip():
                    err(f"{pname}: {key} 为空")
            if not is_num(p.get("capacity")) or p["capacity"] <= 0:
                err(f"{pname}: capacity 必须是正数")
            p_sources = p.get("source_ids") or []
            if not p_sources:
                err(f"{pname}: source_ids 不能为空")
            for sid in p_sources:
                if sid not in source_ids:
                    err(f"{pname}: 未知来源 {sid}")

        evidence = c.get("evidence") or []
        if not evidence:
            err(f"{label}: evidence 不能为空")
        levels = []
        for j, e in enumerate(evidence):
            ename = e.get("id") or f"{label}.evidence[{j}]"
            if e.get("level") not in VALID_LEVELS:
                err(f"{ename}: level 必须是 {sorted(VALID_LEVELS)}")
            levels.append(e.get("level"))
            for key in ["id", "type", "title", "date", "org", "quote", "proves", "source_id"]:
                if not str(e.get(key, "")).strip():
                    err(f"{ename}: {key} 为空")
            if e.get("source_id") and e["source_id"] not in source_ids:
                err(f"{ename}: 未知来源 {e['source_id']}")
        if levels and not any(x in {"直接-A", "直接-B"} for x in levels):
            err(f"{label}: 只有 C/D 级证据，不能作为生产厂家；请移到 traders 或补 A/B 级")
        if levels == ["仅工商-D"]:
            err(f"{label}: 仅工商-D，不能作为生产厂家")

        spec_rows = c.get("spec_rows") or []
        if not spec_rows:
            err(f"{label}: spec_rows 不能为空")
        row_ids = []
        for j, r in enumerate(spec_rows):
            rname = f"{label}.spec_rows[{j}]"
            if r.get("id") not in spec_ids:
                err(f"{rname}: id 不在 specs 中: {r.get('id')}")
            if r.get("id") in row_ids:
                err(f"{rname}: spec_rows.id 重复: {r.get('id')}")
            row_ids.append(r.get("id"))
            for key in ["label", "requirement", "public_info", "gap"]:
                if not str(r.get(key, "")).strip():
                    err(f"{rname}: {key} 为空")
            if r.get("status") not in VALID_SPEC_STATUS:
                err(f"{rname}: status 必须是 {sorted(VALID_SPEC_STATUS)}")
        missing = [sid for sid in spec_ids if sid not in row_ids]
        if missing:
            err(f"{label}: spec_rows 缺少指标 {missing}")

        if c.get("rank") is not None:
            if not isinstance(c["rank"], int):
                err(f"{label}: rank 必须是整数")
            else:
                ranks.append(c["rank"])
        if c.get("composite") is not None and not is_num(c["composite"]):
            err(f"{label}: composite 必须是数字")

    if ranks:
        dup = {r for r in ranks if ranks.count(r) > 1}
        if dup:
            err(f"rank 重复: {sorted(dup)}")
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            warn(f"rank 不是连续 1..{len(ranks)}；请检查是否漏排")

    # traders overlap
    for t in d.get("traders", []):
        if t.get("name") in company_names:
            err(f"贸易商出现在 companies 中: {t.get('name')}")
        if t.get("level") not in VALID_LEVELS:
            err(f"贸易商 {t.get('name')}: level 非法")
        for key in ["name", "type", "region", "evidence", "why", "action"]:
            if not str(t.get(key, "")).strip():
                err(f"贸易商 {t.get('name')}: {key} 为空")

    # gaps / conflicts / actions
    for i, g in enumerate(d.get("gaps", [])):
        if g.get("priority") not in VALID_PRIORITIES:
            err(f"gaps[{i}].priority 必须是 P0/P1/P2")
        for key in ["gap", "affected", "impact", "verify"]:
            if not str(g.get(key, "")).strip():
                err(f"gaps[{i}].{key} 为空")
    for i, c in enumerate(d.get("conflicts", [])):
        for key in ["topic", "a", "b", "resolution"]:
            if not str(c.get(key, "")).strip():
                err(f"conflicts[{i}].{key} 为空")
    for i, a in enumerate(d.get("actions", [])):
        for key in ["phase", "action", "detail"]:
            if not str(a.get(key, "")).strip():
                err(f"actions[{i}].{key} 为空")

    # scoring
    scoring = d["scoring"]
    weights = scoring.get("weights", {})
    wsum = sum(weights.get(k, 0) for k in ["certainty", "spec", "scale", "distance"])
    if abs(wsum - 1.0) > 0.001:
        err(f"scoring.weights 合计为 {wsum:.3f}，必须为 1")
    tiers = scoring.get("tiers", [])
    if not tiers:
        err("scoring.tiers 不能为空")
    else:
        for i, t in enumerate(tiers):
            if not is_num(t.get("min")):
                err(f"scoring.tiers[{i}].min 必须是数字")
            if not str(t.get("label", "")).strip():
                err(f"scoring.tiers[{i}].label 为空")

    # composite/tier consistency
    for c in companies:
        if is_num(c.get("composite")):
            expected = calc_composite(c, weights)
            if abs(c["composite"] - expected) > 1.0:
                warn(f"{c.get('name')}: composite={c['composite']} 与加权计算={expected} 相差 >1")
            if not c.get("tier"):
                c["tier"] = tier_for(c["composite"], tiers)
        elif all(is_num(c.get(k)) for k in ["certainty", "spec_score", "scale_score", "distance_score"]):
            warn(f"{c.get('name')}: 缺少 composite；生成器会按权重计算")

    if len(companies) < 8:
        warn(f"样本仅 {len(companies)} 家；建议 15–30 家，或明确写“样本有限”")

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a project.json for chemical supplier verification")
    ap.add_argument("project", type=Path)
    ap.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = ap.parse_args()

    if not args.project.exists():
        print(f"[ERROR] file not found: {args.project}")
        return 1
    try:
        d = load(args.project)
    except Exception as e:
        print(f"[ERROR] cannot parse JSON: {e}")
        return 1

    errors, warnings = validate(d, strict=args.strict)
    print(f"project: {args.project}")
    print(f"companies: {len(d.get('companies', []))}, plants: {sum(len(c.get('plants', [])) for c in d.get('companies', []))}, sources: {len(d.get('sources', []))}")
    w = d.get("scoring", {}).get("weights", {})
    if sum(w.get(k, 0) for k in ["certainty", "spec", "scale", "distance"]) == 1:
        print(f"weights: certainty {w.get('certainty', 0):.0%} / spec {w.get('spec', 0):.0%} / scale {w.get('scale', 0):.0%} / distance {w.get('distance', 0):.0%}")
    print(f"errors: {len(errors)}, warnings: {len(warnings)}")
    for e in errors:
        print(f"[ERROR] {e}")
    for w in warnings:
        print(f"[WARN]  {w}")
    if errors or (args.strict and warnings):
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
