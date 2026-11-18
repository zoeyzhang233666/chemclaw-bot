"""Shared loader/validator for 检查采购合同风险点 (contract review) skill.

Every build script imports this module so that one dataset drives the
DOCX contract, the HTML review page and the Excel workbook.

Usage (from any build_*.py):
    from common import load_case, validate_case, excerpt, money
"""
from __future__ import annotations

import json
import re
from pathlib import Path

KIND_ORDER = {"缺失": 0, "表述不清": 1, "写了但对我方不利": 2}
KINDS = tuple(KIND_ORDER)


class CaseError(ValueError):
    """Raised when the case data is inconsistent; fail loudly, never silently drop."""


def load_case(directory: str | Path) -> dict:
    """Load <dir>/*.json -> {"contract":…, "review":…}.

    Contract file: any json containing a top-level "clauses" list.
    Review file: any other json containing "findings".
    """
    d = Path(directory)
    cases = {"contract": None, "review": None}
    for f in sorted(d.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "clauses" in data and cases["contract"] is None:
            cases["contract"] = data
        elif isinstance(data, dict) and "findings" in data and cases["review"] is None:
            data.setdefault("_source", f.name)
            cases["review"] = data
    if not cases["contract"] or not cases["review"]:
        raise CaseError(f"{d} 需要同时包含 合同JSON(clauses) 与 审查JSON(findings)")
    return cases


def validate_case(contract: dict, review: dict) -> dict:
    """Return {errors, warnings, stats}; errors must stop the build."""
    errors: list[str] = []
    warnings: list[str] = []

    clauses = {c["id"]: c for c in contract.get("clauses", [])}
    sections = {s["id"]: s for s in contract.get("sections", [])}
    findings = review.get("findings", [])
    topics = {t["id"] for t in review.get("topics", [])}

    if len(clauses) != len(contract.get("clauses", [])):
        errors.append("合同条款 id 重复")
    if len({f["id"] for f in findings}) != len(findings):
        errors.append("风险条目 id 重复")

    for s in contract.get("sections", []):
        for cid in s.get("clause_ids", []):
            if cid not in clauses:
                errors.append(f"章节 {s['id']} 引用未知条款 {cid}")
            elif clauses[cid].get("sec") != s["id"]:
                errors.append(f"条款 {cid} 的 sec 与章节 {s['id']} 不一致")

    stats = {"kind": {}, "severity": {}, "topic": {}, "clause_hit": {}}
    for f in findings:
        if f.get("topic") not in topics:
            errors.append(f"{f['id']} 主题未知: {f.get('topic')}")
        if f.get("kind") not in KINDS:
            errors.append(f"{f['id']} 类型未知: {f.get('kind')}")
        if not f.get("clause_ids"):
            errors.append(f"{f['id']} 未引用任何条款")
        for cid in f.get("clause_ids", []):
            if cid not in clauses:
                errors.append(f"{f['id']} 引用未知条款 {cid}")
            stats["clause_hit"][cid] = stats["clause_hit"].get(cid, 0) + 1
        if not f.get("business_impact"):
            errors.append(f"{f['id']} 缺少业务影响")
        if not f.get("to_confirm"):
            errors.append(f"{f['id']} 缺少待确认问题")
        stats["kind"][f["kind"]] = stats["kind"].get(f["kind"], 0) + 1
        stats["severity"][f["severity"]] = stats["severity"].get(f["severity"], 0) + 1
        stats["topic"][f["topic"]] = stats["topic"].get(f["topic"], 0) + 1

    for owner, items in review.get("confirmations", {}).items():
        for q in items:
            if q["finding_id"] not in {f["id"] for f in findings}:
                errors.append(f"待确认问题引用未知风险 {q['finding_id']}")

    st = review.get("summary", {}).get("stats")
    if st:
        if st.get("total") not in (None, len(findings)):
            errors.append(f"summary.stats.total={st.get('total')} 与风险条数 {len(findings)} 不一致")
        if st.get("by_kind") and dict(sorted(st["by_kind"].items())) != dict(sorted(stats["kind"].items())):
            errors.append(f"summary.stats.by_kind 与实测不一致: {st['by_kind']} vs {stats['kind']}")
        if st.get("by_severity") and {str(k): v for k, v in sorted(stats["severity"].items())} != st["by_severity"]:
            errors.append(f"summary.stats.by_severity 与实测不一致")

    uncovered = [cid for cid in clauses if cid not in stats["clause_hit"]]
    if uncovered:
        warnings.append(f"未被任何风险条目引用的条款: {', '.join(uncovered)}")
    stats["uncovered"] = uncovered
    stats["total"] = len(findings)
    return {"errors": errors, "warnings": warnings, "stats": stats}


def excerpt(text: str, max_len: int = 160) -> str:
    """Return a single-line verbatim excerpt (never rewritten)."""
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= max_len:
        return flat
    cut = flat[:max_len]
    for sep in ("；", "。", "，", "、"):
        idx = cut.rfind(sep)
        if idx >= max_len * 0.5:
            return cut[: idx + 1] + "……"
    return cut + "……"


def locate(clause: dict) -> str:
    """Human-readable locator, e.g. 第2页 / 第二条 2.1（第2页 第2行）."""
    return f"{clause.get('no', '')} · 第{clause.get('page', '?')}页"


def money(x: float) -> str:
    return f"{x:,.0f}"


def counts_by(review: dict, key: str) -> list[tuple[str, int]]:
    from collections import Counter

    return Counter(f[key] for f in review["findings"]).most_common()


def esc(s: str) -> str:
    import html

    return html.escape(str(s), quote=True)
