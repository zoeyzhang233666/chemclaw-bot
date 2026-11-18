# -*- coding: utf-8 -*-
"""build_workbench.py · 字段 + 回复 → 单文件离线双栏审阅板 HTML

用法：
    python build_workbench.py fields.json [reply.json] -o 询盘审阅板.html
    python build_workbench.py fields.json [reply.json] -o out.html --template 公司模板.html

设计：
- 纯前端，数据以 JSON 注入 <script type="application/json">，不联网、不上传；
- 左栏原文按素材分块并编号，右栏字段点击即定位（靠 quote 精确匹配行）；
- 页面不出现任何价格、库存、船期或单证承诺（占位符除外）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# [正则, 替换（$N 表示第 N 个捕获组）, 理由]
LANG_FIXES = [
    [r"\bPlease\s+kindly\s+(note|be\s+advised|find)\b", "Please $1", "冗余 kindly（语法）"],
    [r"\bWe\s+are\s+a\s+professional\s+manufacturer\s+with\s+(\d+)\s+years?\s+of\s+experience\b",
     "Our plant has been manufacturing for $1 years", "老式自我介绍 → 事实陈述"],
    [r"\bThe\s+price\s+is\s+very\s+cheap\b", "Our offer will be competitive for this volume", "cheap 不用于 B2B 报价"],
    [r"\bHope\s+you\s+can\s+understand\b", "We appreciate your understanding", "地道表达"],
    [r"\bWaiting\s+for\s+your\s+(early\s+)?reply\b", "We look forward to your reply", "地道表达"],
    [r"\bPlease\s+check\s+and\s+confirm\s+asap\b", "Could you please confirm at your earliest convenience", "asap → 礼貌问句"],
    [r"\bAs\s+you\s+know,\s*", "", "删除空洞开场"],
    [r"\bAttached\s+please\s+find\b", "Please find attached", "更常见语序"],
    [r"\bdiscuss\s+about\b", "discuss", "discuss 及物"],
    [r"\bKindly\s+be\s+informed\s+that\b", "Please note that", "过时公文腔"],
    [r"\bPls\b", "Please", "缩写"],
    [r"\bwe\s+are\s+looking\s+forward\s+to\s+receive\b", "we look forward to receiving", "动词形式"],
]
TPL_DEFAULT = os.path.join(HERE, "..", "templates", "workbench.template.html")


def short_product(fields):
    f = fields.get("product_std", {})
    v = f.get("value") or ""
    if "Dense" in v:
        return "Dense Soda Ash"
    if "Light" in v:
        return "Soda Ash Light"
    return v or "your requirement"


def build_restatement(fields):
    """复述块（英文），两端一致：由 build_workbench 生成后注入，前端只读。"""
    def g(k):
        f = fields.get(k, {})
        return f.get("value") if f.get("status") == "stated" else ""
    items = [
        ("Product", g("product_std") or "‹PRODUCT_TO_CONFIRM›"),
        ("Specification", "; ".join(x for x in [g("spec_purity"), g("spec_impurities"), g("spec_particle")] if x)),
        ("Quantity", "; ".join([x for x in [(g("qty_trial") + " for the first shipment") if g("qty_trial") else "",
                                            ("approx. " + g("qty_annual")) if g("qty_annual") else ""] if x])),
        ("Delivery", (f"{g('incoterm')} {g('incoterm_place')}, Incoterms 2020"
                      if g("incoterm") else "‹TERMS_TO_CONFIRM›")),
        ("Documents", ", ".join([n for k, n in (("doc_coa", "COA"), ("doc_sds", "SDS"), ("doc_tds", "TDS")) if g(k)])),
        ("Application", "glass manufacturing (as stated in your email)" if g("application") else ""),
    ]
    w = max(len(k) for k, _ in items)
    return "\n".join(f"- {k.ljust(w)} : {v}" for k, v in items if v)


def payload(fields_doc, reply):
    fields = fields_doc.get("fields", {})
    meta = fields_doc.get("meta", {})
    contact = (fields.get("contact_name") or {}).get("value", "")
    body_present = reply.get("body", "")
    # 计算 thanksDate（前端复用）
    import email.utils
    date_str = ((fields.get("_date") or {}) or {}).get("value", "") or meta.get("inquiry_date", "")
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        pretty = dt.strftime("%d %B %Y").lstrip("0")
    except Exception:
        pretty = date_str
    questions = []
    for q in fields_doc.get("questions", []):
        questions.append({
            "key": q.get("field"), "question_en": q.get("question_en", ""), "label_cn": q.get("label_cn", ""),
            "reason_cn": q.get("reason_cn", ""), "anchor": q.get("anchor", ""), "priority": q.get("priority", 1),
        })
    return {
        "version": C.VERSION,
        "meta": {
            "inquiry_no": meta.get("inquiry_no", ""),
            "customer": meta.get("customer", ""),
            "country": meta.get("customer_country", ""),
            "contact": contact,
            "subject": meta.get("subject", ""),
            "as_of": meta.get("as_of", ""),
            "inquiry_date": pretty,
            "simulation": bool(meta.get("simulation", True)),
            "productShort": short_product(fields),
            "disclaimer": meta.get("disclaimer", ""),
        },
        "categories": [[c, cn, en] for c, cn, en in C.CATEGORIES],
        "fields": fields,
        "snippets": [{k: s.get(k) for k in ("id", "kind", "title", "date", "text", "lines", "chars")}
                     for s in fields_doc.get("snippets", [])],
        "questions": questions,
        "internalConfirm": fields_doc.get("internal_confirm", []),
        "traps": C.AMBIGUITY_TRAPS,
        "commitPatterns": [[p, lab, fix] for p, lab, fix in C.COMMITMENT_PATTERNS],
        "pricePatterns": C.PRICE_PATTERNS,
        "langFixes": LANG_FIXES + [
            [r"\bPlease\s+kindly\s+(note|be\s+advised|find)\b", r"Please \1", "冗余 kindly（语法）"],
            [r"\bWe\s+are\s+a\s+professional\s+manufacturer\s+with\s+(\d+)\s+years?\s+of\s+experience\b",
             r"Our plant has been manufacturing for \1 years", "老式自我介绍 → 事实陈述"],
            [r"\bThe\s+price\s+is\s+very\s+cheap\b", "Our offer will be competitive for this volume", "cheap 不用于 B2B 报价"],
            [r"\bHope\s+you\s+can\s+understand\b", "We appreciate your understanding", "地道表达"],
            [r"\bWaiting\s+for\s+your\s+(early\s+)?reply\b", "We look forward to your reply", "地道表达"],
            [r"\bPlease\s+check\s+and\s+confirm\s+asap\b", "Could you please confirm at your earliest convenience", "asap → 礼貌问句"],
            [r"\bAs\s+you\s+know,\s*", "", "删除空洞开场"],
            [r"\bAttached\s+please\s+find\b", "Please find attached", "更常见语序"],
            [r"\bdiscuss\s+about\b", "discuss", "discuss 及物"],
            [r"\bKindly\s+be\s+informed\s+that\b", "Please note that", "过时公文腔"],
            [r"\bPls\b", "Please", "缩写"],
            [r"\bwe\s+are\s+looking\s+forward\s+to\s+receive\b", "we look forward to receiving", "动词形式"],
        ],
        "config": {"maxQuestions": 6},
        "reply": {
            "subject": reply.get("subject", ""),
            "body": reply.get("body", ""),
            "tone": reply.get("tone", "friendly-professional"),
            "template": reply.get("template", "reply_A_confirm"),
            "placeholders": reply.get("placeholders", []),
            "thanksDate": pretty,
            "restatement": build_restatement(fields),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="生成双栏审阅板 HTML")
    ap.add_argument("fields")
    ap.add_argument("reply", nargs="?", default="")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--template", default="", help="自定义 HTML 模板路径")
    args = ap.parse_args()

    fields_doc = C.load_json_stable(args.fields)
    reply = C.load_json(args.reply) if args.reply else {}
    if not reply:
        reply = {"subject": "Re: Inquiry", "body": "(未生成回复：请先运行 extract.py)",
                 "tone": "friendly-professional", "template": "reply_A_confirm", "placeholders": []}
    tpl_path = args.template or TPL_DEFAULT
    tpl = C.read_text(tpl_path)
    data = payload(fields_doc, reply)
    title = (fields_doc.get("meta", {}).get("customer") or "Customer") + " · 重质纯碱" \
        if "Dense" in (fields_doc.get("fields", {}).get("product_std", {}).get("value") or "") else \
        (fields_doc.get("meta", {}).get("customer") or "Customer")
    html = (tpl.replace("__DATA__", C.js_safe(data))
               .replace("__TITLE__", C.esc_html(title))
               .replace("__VERSION__", C.VERSION))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"[ok] {args.out} ({len(html)/1024:.0f} KB · 字段 {len(data['fields'])} · 素材 {len(data['snippets'])} · 问题 {len(data['questions'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
