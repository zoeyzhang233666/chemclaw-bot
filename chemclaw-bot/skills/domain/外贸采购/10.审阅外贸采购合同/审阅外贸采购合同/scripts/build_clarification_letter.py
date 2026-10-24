"""由 review.json 的供应商问题清单生成英文澄清/修改要求函草稿（.txt）。

原则：
  * 只问「事实 / 文件 / 承诺」，不问法律判断，不替买方下结论；
  * 每条问题注明条款位置与风险编号，便于对方逐条回复；
  * 信头、称谓、落款均为占位符，发出前须由采购负责人与法务确认。

用法:
    python build_clarification_letter.py --dir <案例目录> --out <英文澄清函.txt>
        [--ref "GY-PO-2026-MEG-017"] [--buyer "…"] [--seller "…"] [--date 2026-10-20]
        [--deadline 2026-11-05]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import clause_locator, load_case

GROUP_ORDER = [
    ("PAYMENT & LETTER OF CREDIT", {"payment"}),
    ("DELIVERY & SHIPMENT", {"delivery"}),
    ("QUALITY & SPECIFICATION", {"quality", "quantity"}),
    ("INSPECTION, CLAIMS & REMEDIES", {"claims", "breach"}),
    ("TRANSPORT, RISK & INSURANCE", {"risk"}),
    ("DISPUTE RESOLUTION, GOVERNING LAW & LANGUAGE", {"dispute", "language"}),
    ("DOCUMENTS, PACKAGING & REGULATORY COMPLIANCE", {"docs", "compliance", "parties", "force_majeure"}),
]

PRI_EN = {"高": "High priority", "中": "Medium priority", "低": "Low priority"}


def locators_en(c: dict) -> str:
    """英文定位串：Clause 8.1, Section 3, p.3（仅英文，供对外函件使用）。"""
    no = c.get("no", "")
    page = c.get("page", "?")
    line = c.get("page_line") or ""
    m = re.search(r"第(\d+)段", line)
    if m:
        return f"{no}, Section {m.group(1)}, p.{page}"
    part = ""
    for zh, en in (("附件标题", "heading"), ("表1表头", "Table 1 header"),
                   ("表1数据行", "Table 1 row"), ("表1注释", "Table 1 note"),
                   ("表2数据行", "Table 2 row"), ("签署栏", "signature block"),
                   ("页眉", "header")):
        if zh in line:
            part = en
            break
    return f"{no}, p.{page}" + (f" ({part})" if part else "")


def wrap(text: str, indent: int = 3, width: int = 96) -> str:
    """按宽度折行（英文），保留缩进。"""
    prefix = " " * indent
    words = text.split()
    if not words:
        return prefix.rstrip()
    line = prefix
    out = []
    for w in words:
        if len(line) + len(w) + 1 > width and line.strip():
            out.append(line)
            line = " " * (indent + 3) + w
        else:
            line = (line + " " + w) if line.strip() else prefix + w
    out.append(line)
    return "\n".join(out)


def _split_questions(q: str) -> list[str]:
    """把一串英文问题拆成独立句子（问号分隔），保留问号。"""
    parts = re.split(r"(?<=\?)\s+", q.strip())
    return [p.strip() for p in parts if p.strip()]


def build(case_dir: Path, out: Path, ref: str | None, buyer: str, seller: str,
          date: str, deadline: str) -> dict:
    case = load_case(case_dir)
    contract, review = case["contract"], case["review"]
    meta = contract.get("contract_meta", {})
    clauses = {x["id"]: x for x in contract["clauses"]}
    fmap = {f["id"]: f for f in review["findings"]}
    ref = ref or meta.get("contract_no", "")
    buyer = buyer or meta.get("buyer_en", "ZHEJIANG HONYU NEW MATERIALS CO., LTD.")
    seller = seller or meta.get("supplier_en", "GULF PETROCHEMICAL TRADING FZE")

    items = []
    for q in review.get("confirmations", {}).get("supplier", []):
        f = fmap[q["finding_id"]]
        items.append((q["priority"], f, q))

    lines: list[str] = []
    add = lines.append
    add("=" * 78)
    add("[DRAFT — INTERNAL USE ONLY — to be reviewed by Procurement and Legal before sending]")
    add("=" * 78)
    add("")
    add(f"{buyer}")
    add(f"Attention: {seller}")
    add("")
    add(f"Subject: Requests for Clarification and Proposed Amendments to Purchase Contract No. {ref}")
    add("         (Monoethylene Glycol / MEG — CIF Ningbo, Incoterms 2020)")
    add(f"Reference: {ref}")
    add(f"Date: {date}")
    add("")
    add("Dear Sirs,")
    add("")
    add("Thank you for your efforts in preparing the captioned Purchase Contract. Having reviewed the")
    add("Contract against our procurement requirements, we set out below the points on which we would")
    add("be grateful for your clarification and, where indicated, for your agreement to the proposed")
    add("amendments. The points are grouped by subject and each is cross-referenced to the relevant")
    add("clause of the Contract and to our internal issue reference.")
    add("")
    add("We would appreciate your written response to each numbered item separately. Unless otherwise")
    add(f"stated, please reply by {deadline}. Items marked [AGREEMENT REQUIRED] call for your express")
    add("agreement in writing; items marked [INFORMATION] require factual information, documents or")
    add("confirmations only. Nothing in this letter is intended as a legal opinion or as a waiver of")
    add("any right of the Buyer.")
    add("")

    n = 0
    grouped = {name: [] for name, _ in GROUP_ORDER}
    for pri, f, q in items:
        target = None
        for name, topics in GROUP_ORDER:
            if f["topic"] in topics:
                target = name
                break
        if target is None:
            target = GROUP_ORDER[-1][0]
        grouped[target].append((pri, f, q))

    for name, _ in GROUP_ORDER:
        if not grouped[name]:
            continue
        add("-" * 78)
        add(name)
        add("-" * 78)
        add("")
        for pri, f, q in sorted(grouped[name], key=lambda t: ({"高": 0, "中": 1, "低": 2}[t[0]], t[1]["id"])):
            n += 1
            tag = ("[AGREEMENT REQUIRED]" if pri == "高"
                   else "[AGREEMENT PREFERRED]" if pri == "中" else "[INFORMATION]")
            locs = "; ".join(locators_en(clauses[c]) for c in f["clause_ids"] if c in clauses)
            add(f"{n}. [{f['id']} · {PRI_EN[pri]}] {tag}")
            add(f"   Contract provision: {locs}")
            add(f"   Issue: {f.get('title_en') or f['title']}")
            # 英文问题优先；没有英文时若含中文字符则跳过（避免英文函件夹中文）
            question_en = (q.get("question_en") or "").strip()
            zh = (q.get("question") or "").strip()
            for t in _split_questions(question_en):
                add(wrap(t, 3))
            quotes = [x for x in f.get("quotes", []) if x.get("text")]
            if quotes:
                add("   Contract wording referred to (verbatim):")
                for qq in quotes[:2]:
                    text = " ".join(qq["text"].split())
                    if len(text) > 300:
                        text = text[:300].rsplit(" ", 1)[0] + " [...]"
                    line = '      "'
                    for w in text.split():
                        if len(line) + len(w) + 1 > 96:
                            add(line)
                            line = "       " + w
                        else:
                            line = line + " " + w
                    add(line + '"')
            add("   Supplier response: _______________________________________________________")
            add("")

    add("-" * 78)
    add("GENERAL OBSERVATIONS")
    add("-" * 78)
    add("")
    add(f"{n + 1}. [CONTRACT ADMINISTRATION] Please confirm the name, telephone number and e-mail address")
    add("   of the person within your organisation who will be responsible for contract execution,")
    add("   shipping documents and claims handling.")
    add("")
    add(f"{n + 2}. [DOCUMENTS] Please provide, for our file, the following items not attached to the")
    add("   Contract: (a) the full text of your \"Fiber Grade MEG\" standard specification in force on")
    add("   the date of signature; (b) the current GHS safety data sheet (SDS); (c) your trade licence;")
    add("   and (d) the name of the actual producer of the Goods.")
    add("")
    add(f"{n + 3}. [LANGUAGE] The Contract is executed in English and Chinese. Please confirm which")
    add("   version will be used for day-to-day administration and whether you are prepared to accept")
    add("   the Chinese version as the prevailing text.")
    add("")
    add("We propose to arrange a short call to go through the above items once we have your written")
    add("response, so that any resulting revisions can be incorporated before shipment planning")
    add("commences. In the meantime, the Contract remains subject to our internal approval and to the")
    add("outcome of due diligence on your organisation and on the producer of the Goods.")
    add("")
    add("We look forward to hearing from you.")
    add("")
    add("Yours faithfully,")
    add("")
    add("_________________________________")
    add(f"{buyer}")
    add("Procurement Department")
    add("")
    add("[-- this document is a draft generated from a simulated contract review and is not legal advice --]")

    text = "\n".join(lines) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return {"out": str(out), "items": n + 3, "bytes": len(text.encode("utf-8"))}


def main() -> None:
    ap = argparse.ArgumentParser(description="生成英文澄清/修改要求函草稿")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref", default=None)
    ap.add_argument("--buyer", default="")
    ap.add_argument("--seller", default="")
    ap.add_argument("--date", default="2026-10-20")
    ap.add_argument("--deadline", default="2026-11-05")
    a = ap.parse_args()
    info = build(Path(a.dir), Path(a.out), a.ref, a.buyer, a.seller, a.date, a.deadline)
    print(json.dumps({"ok": True, **info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
