"""QA the review data and (optionally) the generated HTML report.

Run it BEFORE building to catch bad anchors and non-verbatim quotes;
run it AFTER building to also verify the rendered report's structure.

    # data-only check (fast gate, works on the raw JSON)
    python qa_report.py --parsed contract_parsed.json --issues data_issues_*.json

    # full check including the built report
    python qa_report.py --parsed contract_parsed.json --issues data_issues_*.json \
        --html review.html

Exit code is 1 when anything fails, so it can gate a build script.
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import re
import sys

VALID_CATEGORY = {"payment", "delivery", "quality", "claim", "compliance", "dispute", "missing"}
VALID_SEVERITY = {"high", "medium", "low"}
VALID_TYPE = {"ambiguous", "unilateral", "conflict", "missing", "unbalanced", "unenforceable", "commercial"}
VALID_STATUS = {"待处理", "处理中", "需法务确认", "已解决", "不适用"}

problems: list[str] = []


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def load_issues(patterns):
    issues = []
    for pat in patterns:
        for p in sorted(glob.glob(pat)) or [pat]:
            data = json.load(io.open(p, encoding="utf-8"))
            for iss in data.get("issues", []):
                iss["_file"] = p
                issues.append(iss)
    issues.sort(key=lambda i: (i.get("seq", 9999), i.get("id", "")))
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate contract review data and report.")
    ap.add_argument("--parsed", required=True, help="contract_parsed.json")
    ap.add_argument("--issues", nargs="+", required=True, help="data_issues_*.json (globs ok)")
    ap.add_argument("--html", help="optional built review.html to validate")
    args = ap.parse_args()

    parsed = json.load(io.open(args.parsed, encoding="utf-8"))
    blocks = parsed["blocks"]

    block_ids = set()
    text_by_id = {}
    for b in blocks:
        block_ids.add(b["id"])
        if b["kind"] == "table":
            text_by_id[b["id"]] = " ".join(" ".join(r) for r in b["rows"])
        else:
            text_by_id[b["id"]] = b.get("text", "")
        for ln in b.get("lines", []):
            block_ids.add(ln["id"])
            text_by_id[ln["id"]] = ln["text"]

    issues = load_issues(args.issues)
    print(f"contract blocks     : {len(blocks)} ({len(block_ids)} ids incl. exec lines)")
    print(f"issues loaded       : {len(issues)}")

    # ---- identity & enums
    seen = {}
    for iss in issues:
        iid = iss.get("id", "?")
        if iid in seen:
            problems.append(f"{iid}: duplicate id (also in {seen[iid]})")
        seen[iid] = iss["_file"]
        if iss.get("category") not in VALID_CATEGORY:
            problems.append(f"{iid}: bad category {iss.get('category')!r}")
        if iss.get("severity") not in VALID_SEVERITY:
            problems.append(f"{iid}: bad severity {iss.get('severity')!r}")
        if iss.get("issue_type") not in VALID_TYPE:
            problems.append(f"{iid}: bad issue_type {iss.get('issue_type')!r}")
        if iss.get("status") and iss["status"] not in VALID_STATUS:
            problems.append(f"{iid}: bad status {iss['status']!r}")

    # ---- anchors
    broken = 0
    for iss in issues:
        anchors = iss.get("anchors") or []
        if not anchors:
            if iss.get("category") != "missing":
                problems.append(
                    f"{iss['id']}: no anchors but category={iss.get('category')!r} "
                    "(only category=missing may omit anchors)"
                )
            continue
        for a in anchors:
            if a.get("block") not in block_ids:
                problems.append(f"{iss['id']}: anchor block {a.get('block')!r} does not exist")
                broken += 1

    # ---- quote fidelity (the core guarantee)
    bad_quotes = 0
    for iss in issues:
        for a in iss.get("anchors") or []:
            src = text_by_id.get(a.get("block"), "")
            q = a.get("quote", "")
            if not q:
                problems.append(f"{iss['id']}: empty quote on block {a.get('block')}")
                bad_quotes += 1
            elif norm(q) not in norm(src):
                problems.append(
                    f"{iss['id']}: quote not verbatim in {a.get('block')}\n"
                    f"      quote: {q[:110]}"
                )
                bad_quotes += 1

    # ---- content quality gates
    for iss in issues:
        if len(iss.get("finding", "")) < 30:
            problems.append(f"{iss['id']}: finding too short to be useful")
        if len(iss.get("consequence", "")) < 30:
            problems.append(f"{iss['id']}: consequence too short to be useful")
        if not iss.get("confirm"):
            problems.append(f"{iss['id']}: no confirmation items")
        for ref in iss.get("legal_refs") or []:
            if not ref.get("label"):
                problems.append(f"{iss['id']}: legal_ref without label")

    print(f"anchors checked     : {sum(len(i.get('anchors') or []) for i in issues)}")
    print(f"quote mismatches    : {bad_quotes}")

    # ---- optional: validate the built HTML
    if args.html:
        html = io.open(args.html, encoding="utf-8").read()
        m = re.search(r"window\.__REVIEW__ = (\{.*?\});\n</script>", html, re.S)
        if not m:
            problems.append("HTML: could not find embedded window.__REVIEW__ payload")
        else:
            payload = json.loads(m.group(1))
            print(f"issues in HTML      : {len(payload.get('issues', []))}")
            if len(payload.get("issues", [])) != len(issues):
                problems.append(
                    f"HTML has {len(payload['issues'])} issues, data has {len(issues)} "
                    "(rebuild after editing data)"
                )

        # Only trust data-bid attributes emitted by the builder's HTML, not the
        # ones that appear inside the inlined JS source (string concatenations).
        html_markup = re.sub(r"<script\b.*?</script>", "", html, flags=re.S)
        data_bids = set(re.findall(r'data-bid="([^"]+)"', html_markup))
        not_rendered = sorted(block_ids - data_bids)
        if not_rendered:
            problems.append(f"HTML missing {len(not_rendered)} contract blocks: {not_rendered[:5]}")
        extra = sorted(data_bids - block_ids)
        if extra:
            problems.append(f"HTML renders {len(extra)} unknown block ids: {extra[:5]}")

        for tag in ("div", "table", "article", "button"):
            o = len(re.findall(rf"<{tag}[\s>]", html))
            c = len(re.findall(rf"</{tag}>", html))
            if o != c:
                problems.append(f"HTML <{tag}> unbalanced: {o} open / {c} close")
        print(f"html size           : {len(html):,} chars")

    # ---- verdict
    if problems:
        print(f"\nFAILED — {len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1

    print("\nALL CHECKS PASSED")
    print("  · every anchor resolves to a real contract block")
    print("  · every quote is a verbatim substring of its anchored block")
    print("  · enums, ids and required fields are valid")
    if args.html:
        print("  · HTML renders every block, payload matches data, tags balanced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
