# -*- coding: utf-8 -*-
"""polish.py · 自写英文稿的语言润色（只改语言，不加承诺）

用法：
    python polish.py 我的稿.txt --lang en --report polish.json -o 润色后.md
    python polish.py 我的稿.txt --apply glossary.json

规则（硬约束）：
1. 不重写结构、不换观点、不删事实、不改数量/规格/港口/币种；
2. 不改任何商务承诺的强弱（不把 please consider 改成 we guarantee）；
3. 输出改动清单（原文 → 改后 → 理由），每一条都要能回答"承诺变多了吗"；
4. 输出"新增承诺检查"，命中承诺词就回退并报告。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

# 中式英语 / 外贸高频病句（只改语言，不改意思）
LANG_FIXES = [
    (r"\bPlease\s+kindly\s+(note|be\s+advised|send|find)\b", r"Please \1", "冗余 kindy（语言学）"),
    (r"\bWe\s+are\s+a\s+professional\s+manufacturer\s+with\s+(\d+)\s+years?\s+(of\s+)?experience\b",
     r"Our plant has been manufacturing for \1 years", "老式自我介绍 → 事实陈述"),
    (r"\bThe\s+price\s+is\s+very\s+cheap\b", "Our offer will be competitive for this volume", "cheap 不得用于 B2B 报价语言"),
    (r"\bHope\s+you\s+can\s+understand\b", "We appreciate your understanding", "地道表达"),
    (r"\bWaiting\s+for\s+your\s+(early\s+)?reply\b", "We look forward to your reply", "地道表达"),
    (r"\bPlease\s+check\s+and\s+confirm\s+asap\b", "Could you please confirm at your earliest convenience", "asap 改为礼貌问句"),
    (r"\bWe\s+will\s+do\s+our\s+best\s+to\s+satisfy\s+you\b", "We will do our best to meet your requirements", "弱化不正确承诺"),
    (r"\bAs\s+you\s+know,?\s*", "", "删除空洞开场"),
    (r"\bAttached\s+please\s+find\b", "Please find attached", "更常见语序"),
    (r"\bInform\s+you\s+that\b", "advise you that", "商务用词"),
    (r"\bin\s+the\s+near\s+future\b", "shortly", "简洁"),
    (r"\bvery\s+important\s+for\s+us\b", "important to us", "介词"),
    (r"\bwe\s+are\s+looking\s+forward\s+to\s+receive\b", "we look forward to receiving", "动词形式"),
    (r"\bdiscuss\s+about\b", "discuss", "discuss 及物"),
    (r"\baccording\s+to\s+my\s+opinion\b", "in my view", "地道表达"),
    (r"\bno\s+matter\s+what\s+price\b", "regardless of the price", "表达不清"),
    (r"\bSame\s+as\s+before\b", "As previously agreed", "口语化"),
    (r"\bPls\b", "Please", "缩写"),
    (r"\bKindly\s+be\s+informed\s+that\b", "Please note that", "过时公文腔"),
    (r"\bherewith\b", "attached", "过时用词"),
]

# 润色时会改变承诺强度的词对（命中则报警，交给人工）
PROMISE_ESCALATORS = [
    (r"\b(can|could|may|would)\b", r"\b(will|shall|guarantee)\b"),
    (r"\b(please\s+consider|we\s+suggest|we\s+propose)\b", r"\b(must|shall|will)\b"),
    (r"\b(subject\s+to\s+(our\s+)?confirmation)\b", ""),
    (r"\b(indicative|approximate|approx\.?|about)\b", ""),
]


def apply_lang_fixes(text):
    changes = []
    out = text
    for pat, rep, why in LANG_FIXES:
        for m in re.finditer(pat, out, flags=re.I):
            before = m.group(0)
            if re.fullmatch(pat, before, flags=re.I):
                pass
            new_line = re.sub(pat, rep, before, flags=re.I)
            changes.append({"type": "language", "before": before, "after": new_line,
                            "reason": why, "promise_delta": "无"})
        out = re.sub(pat, rep, out, flags=re.I)
    return out, changes


def promise_check(orig, new):
    """对比两版，检查是否有"承诺变多"的迹象。"""
    problems = []
    o_comm = {(h["pattern"], h["match"].lower()) for h in C.scan_commitments(orig)}
    n_comm = C.scan_commitments(new)
    for h in n_comm:
        key = (h["pattern"], h["match"].lower())
        if key not in o_comm:
            problems.append({"kind": "新增承诺", "match": h["match"], "pattern": h["pattern"]})
    # 数字：新稿不得出现原文没有的数字
    nums_o = set(re.findall(r"\d+(?:[.,]\d+)?", orig))
    nums_n = set(re.findall(r"\d+(?:[.,]\d+)?", new))
    for x in nums_n - nums_o:
        problems.append({"kind": "新增数字", "match": x, "pattern": ""})
    # 弱化词被删（subject to confirmation 之类）
    for pat, _ in PROMISE_ESCALATORS[2:]:
        if re.search(pat, orig, re.I) and not re.search(pat, new, re.I):
            problems.append({"kind": "删除限定语", "match": re.search(pat, orig, re.I).group(0), "pattern": pat})
    return problems


def main():
    ap = argparse.ArgumentParser(description="英文回复润色（只改语言，不加承诺）")
    ap.add_argument("draft", help="自写英文稿 .txt/.md")
    ap.add_argument("--report", default="polish.json")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--lang", default="en", choices=["en", "zh"])
    args = ap.parse_args()

    orig = C.read_text(args.draft)
    new, changes = apply_lang_fixes(orig)
    problems = promise_check(orig, new)
    if problems:
        # 有新增承诺 → 拒绝输出润色版，先把原文交回
        new = orig
        verdict = "发现新增承诺/数字，已回退：请人工确认后再润色"
    else:
        verdict = "无新增承诺"

    rep = {
        "draft": os.path.abspath(args.draft),
        "generated_at": C.now_iso(),
        "changes": changes,
        "promise_check": verdict,
        "problems": problems,
        "commitment_scan_before": C.scan_commitments(orig),
        "price_scan": C.scan_prices(orig),
        "rules": "只改语言；不重写结构、不改事实、不新增承诺",
    }
    C.write_json(args.report, rep)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(new if new.endswith("\n") else new + "\n")
    print(f"[polish] 语言改动 {len(changes)} 处 · 承诺检查：{verdict}")
    for p in problems:
        print(f"  ! {p['kind']}: {p['match']}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
