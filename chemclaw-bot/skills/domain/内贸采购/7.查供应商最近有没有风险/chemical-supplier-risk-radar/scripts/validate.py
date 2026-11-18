# -*- coding: utf-8 -*-
"""Validate a supplier-risk data.json before generating deliverables.

Usage:
    python validate.py data.json
Exit code 0 = no errors (warnings allowed), 1 = errors.
"""
import json
import sys
from datetime import date
from pathlib import Path

CATS = ["工商", "司法", "处罚", "安全环保", "经营动态"]
SEVS = ["高", "中", "低"]
DIRS = ["风险", "中性", "正向"]
EVID = ["A", "B", "C"]
RISKS = ["高", "中", "中低", "低"]
COV_LEVELS = ["高", "中", "低", "待复核", "—"]

errors, warnings = [], []


def req(obj, key, where):
    v = obj.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        errors.append(f"{where}: missing {key}")
    return v


def is_date(s):
    try:
        date.fromisoformat(str(s))
        return True
    except Exception:
        return False


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data.json").resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data.get("meta") or {}
    for k in ["title", "product", "query_date", "query_time", "window_default", "windows"]:
        req(meta, k, "meta")
    for k in ["financial_period", "period_tag", "subtitle", "scope_summary", "product_en"]:
        if not meta.get(k):
            warnings.append(f"meta: {k} is recommended but missing")

    wins = meta.get("windows") or {}
    for key in ["3m", "6m", "12m"]:
        if key not in wins:
            errors.append(f"meta.windows: missing required window {key} (template has 3m/6m/12m buttons)")
    if len(wins) < 2:
        errors.append("meta.windows: need at least 2 windows (e.g. 3m/6m/12m)")
    for key, w in wins.items():
        if not is_date(w.get("start")) or not is_date(w.get("end")):
            errors.append(f"meta.windows.{key}: start/end must be YYYY-MM-DD")
        elif w["start"] > w["end"]:
            errors.append(f"meta.windows.{key}: start after end")
        if not w.get("label"):
            warnings.append(f"meta.windows.{key}: missing label")
    default_key = meta.get("window_default")
    if default_key and default_key not in wins:
        errors.append(f"meta.window_default={default_key} not in windows")
    if meta.get("query_date") and is_date(meta["query_date"]):
        if wins.get(default_key, {}).get("end") != meta["query_date"]:
            warnings.append("default window end != meta.query_date")

    suppliers = data.get("suppliers") or []
    if not suppliers:
        errors.append("suppliers: empty")
    sids = set()
    for i, s in enumerate(suppliers, 1):
        where = f"suppliers[{i}] {s.get('name','')}"
        for k in ["id", "name", "full_name", "code", "market", "region", "process",
                  "capacity", "capacity_short", "risk_level", "risk_label", "conclusion", "coverage"]:
            req(s, k, where)
        if s.get("id") in sids:
            errors.append(f"{where}: duplicate supplier id")
        sids.add(s.get("id"))
        if s.get("risk_level") not in RISKS:
            errors.append(f"{where}: risk_level must be one of {RISKS}")
        if not s.get("revenue") and not s.get("h1_revenue"):
            warnings.append(f"{where}: no revenue field")
        if not s.get("profit") and not s.get("h1_profit"):
            warnings.append(f"{where}: no profit field")

    events = data.get("events") or []
    if not events:
        errors.append("events: empty")
    eids = set()
    all_dates = []
    for i, e in enumerate(events, 1):
        where = f"events[{i}] {e.get('id','')}"
        for k in ["id", "date", "supplier_id", "supplier", "category", "severity", "direction",
                  "title", "fact", "why", "source", "source_type", "source_date", "url",
                  "evidence", "questions", "action"]:
            req(e, k, where)
        if e.get("id") in eids:
            errors.append(f"{where}: duplicate event id")
        eids.add(e.get("id"))
        if is_date(e.get("date")):
            all_dates.append(e["date"])
        else:
            errors.append(f"{where}: bad date")
        if e.get("supplier_id") not in sids:
            errors.append(f"{where}: supplier_id not found")
        else:
            s = next(x for x in suppliers if x.get("id") == e["supplier_id"])
            if e.get("supplier") != s.get("name"):
                warnings.append(f"{where}: supplier name != supplier_id name")
        if e.get("category") not in CATS:
            errors.append(f"{where}: category must be one of {CATS}")
        if e.get("severity") not in SEVS:
            errors.append(f"{where}: severity must be one of {SEVS}")
        if e.get("direction") not in DIRS:
            errors.append(f"{where}: direction must be one of {DIRS}")
        if e.get("evidence") not in EVID:
            errors.append(f"{where}: evidence must be A/B/C")
        if not str(e.get("url", "")).startswith(("http://", "https://")):
            errors.append(f"{where}: url must be http(s)")
        if not isinstance(e.get("questions"), list) or not e.get("questions"):
            errors.append(f"{where}: questions must be a non-empty list")
        if len(str(e.get("fact", ""))) < 40:
            warnings.append(f"{where}: fact looks short; usually needs >40 chars")

    if all_dates and wins:
        lo = min(w["start"] for w in wins.values())
        hi = max(w["end"] for w in wins.values())
        outside = sorted({d for d in all_dates if not (lo <= d <= hi)})
        if outside:
            errors.append(f"events outside the 12m window {lo}..{hi}: {outside[:8]}")

    cov = data.get("coverage_check") or []
    if not cov:
        warnings.append("coverage_check: missing; generators will use placeholder rows — fill it for a defensible report")
    seen_cov = set()
    for i, c in enumerate(cov, 1):
        where = f"coverage_check[{i}]"
        for k in ["cat", "status", "note", "level"]:
            req(c, k, where)
        if c.get("level") not in COV_LEVELS:
            warnings.append(f"{where}: unusual level {c.get('level')!r}")
        if c.get("cat") in seen_cov:
            warnings.append(f"{where}: duplicate category")
        seen_cov.add(c.get("cat"))

    industry = data.get("industry") or []
    if not industry:
        warnings.append("industry: missing; the method view will be thin")
    for i, x in enumerate(industry, 1):
        for k in ["text", "source", "date"]:
            req(x, k, f"industry[{i}]")

    method = data.get("method") or {}
    for k in ["scope", "evidence_levels", "limits", "search_queries", "disclaimer"]:
        if not method.get(k):
            warnings.append(f"method.{k}: missing")

    # summary
    print(f"file: {path}")
    print(f"product: {meta.get('product')} | suppliers: {len(suppliers)} | events: {len(events)}")
    for key, w in wins.items():
        n = sum(1 for e in events if w["start"] <= e.get("date", "") <= w["end"])
        hi = sum(1 for e in events if w["start"] <= e.get("date", "") <= w["end"] and e.get("severity") == "高")
        print(f"  {key:>3} {w.get('label','')}: {n} events, {hi} high")
    for cat in CATS:
        n = sum(1 for e in events if e.get("category") == cat)
        print(f"  {cat}: {n}")
    print(f"coverage: {len(cov)} rows | industry: {len(industry)} | sources: {len({e.get('url') for e in events})}")
    if warnings:
        print("\nWARNINGS")
        for w in warnings:
            print("  -", w)
    if errors:
        print("\nERRORS")
        for e in errors:
            print("  -", e)
        print("\nverdict: FAIL")
        return 1
    print("\nverdict: PASS (warnings are non-blocking)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
