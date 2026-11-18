#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""caselib —— case.json 的读取、规整与边界守卫。

被 validate_case.py / build_workbook.py / build_html.py / run_all.py 共用。
纯标准库实现，不依赖第三方包，任何装了 Python 3.8+ 的机器都能跑。
"""
from __future__ import annotations

import json
import os
import re

# ---------------------------------------------------------------- 常量

SYMBOLS = {"✔", "◐", "—", "▲"}
SYMBOL_ALIAS = {"v": "✔", "y": "✔", "ok": "✔", "O": "✔",
                "~": "◐", "half": "◐", "mid": "◐",
                "-": "—", "": "—", "none": "—", "x": "—",
                "del": "▲", "▲": "▲", "d": "▲"}

PROMISE_WORDS = [
    "可以再谈", "再谈", "还可以谈", "给您申请", "帮你申请", "给您申请价",
    "一定", "保证", "绝对", "包您", "包您满意", "随时有货", "随时可以发",
    "免费", "包运费", "包邮", "最低价", "最优惠", "给到底",
    "不会出问题", "放心用", "任何要求都可以", "什么要求都能", "全都答应",
]

SCARCITY_WORDS = [
    "货源紧张", "库存不多", "库存紧张", "货源不稳", "马上涨价", "即将涨价",
    "随时涨价", "最后一天", "最后两天", "最后三天", "抢货", "手慢无", "限量供应",
    "不订就没了", "错过就没了",
]

NUMBER_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(元/吨|元/千克|元|吨|千克|公斤|kg|KG|天|个月|周|%|％|袋|车|件|小时|分钟|m³|立方)")
CN_NUM_RE = re.compile(r"([一二三四五六七八九十百千万两]{1,3})\s*(吨|元|天|袋|车|小时)")

REQUIRED_TOP = ["meta", "product_profile", "facts", "versions", "audit",
                "audit_summary", "placeholders", "scenarios"]
VERSION_KEYS = ["A", "B", "C", "D"]


# ---------------------------------------------------------------- 读取

def load_case(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        case = json.load(f)
    normalize(case)
    return case


def normalize(case):
    """把可选字段补成默认值，把审计符号统一。不修改用户内容，只补结构。"""
    case.setdefault("schema_version", "1.0")
    case.setdefault("links", [])
    case.setdefault("version_order", ["P0"] + VERSION_KEYS)
    case.setdefault("email", {})
    case.setdefault("adjusts", [])
    case.setdefault("replies", [])
    case.setdefault("checklist", [])
    case.setdefault("rules", [])
    case.setdefault("notes", [])
    case.setdefault("disclaim", "")
    case.setdefault("decision_chain", "")
    case.setdefault("allowed_numbers", [])
    case.setdefault("customer_profile", [])
    case.setdefault("timeline", [])

    meta = case.setdefault("meta", {})
    for k, v in [("product", ""), ("spec", ""), ("scenario", ""), ("channel", ""),
                 ("goal", ""), ("stage", ""), ("fictional", True),
                 ("file_stem", ""), ("hero", {})]:
        meta.setdefault(k, v)
    meta.setdefault("seller", {})
    meta.setdefault("customer", {})
    if not meta["file_stem"]:
        cname = (meta.get("customer") or {}).get("name", "客户")
        cname = re.sub(r"[\\/:*?\"<>|]", "", cname)[:18]
        meta["file_stem"] = "%s_%s" % (cname, meta.get("scenario") or "沟通")

    draft = case.setdefault("draft", {})
    draft.setdefault("raw", "")
    draft.setdefault("segments", [{"t": draft["raw"], "m": ""}] if draft["raw"] else [])
    draft.setdefault("legend", [{"m": "q", "label": "追问感，建议软化"},
                                {"m": "w", "label": "过宽表述，需限定"},
                                {"m": "b", "label": "越界，必须处理"}])

    # 审计符号规整：空串保持为空（交给守卫报错），别名映射成标准符号，未知符号原样保留
    for row in case.get("audit", []):
        v = row.get("v", {})
        fixed = {}
        for k in VERSION_KEYS:
            raw = (v.get(k) or "").strip()
            if not raw:
                fixed[k] = ""
            elif raw in SYMBOLS:
                fixed[k] = raw
            else:
                fixed[k] = SYMBOL_ALIAS.get(raw, raw)
        row["v"] = fixed

    # 版本 para 兜底：没有 para 就用 cells
    for key, ver in (case.get("versions") or {}).items():
        if not isinstance(ver, dict):
            continue
        ver.setdefault("cells", [])
        if not ver.get("para"):
            ver["para"] = [c for c in ver.get("cells", []) if c and c.strip() not in ("—", "")]
        ver.setdefault("why", [])
        for f in ("label", "media", "tone", "push", "risk", "fit"):
            ver.setdefault(f, "")
    return case


# ---------------------------------------------------------------- 文本

def version_text(ver, with_cells=False):
    parts = list(ver.get("para") or [])
    if with_cells:
        parts += [c for c in (ver.get("cells") or []) if c and c.strip() not in ("—",)]
    out = []
    for p in parts:
        p = (p or "").strip()
        if not p or p.startswith("（未展开") or p.startswith("（不作"):
            continue
        out.append(p)
    return "\n".join(out)


def output_texts(case):
    """返回 [(位置, 文本)]，只包含「会发给客户」的正文，用于边界扫描。"""
    items = []
    for key in VERSION_KEYS:
        ver = (case.get("versions") or {}).get(key)
        if ver:
            txt = version_text(ver, with_cells=(key == "P0"))
            if key != "P0":  # P0 是用户原文，不扫描
                items.append(("%s 版" % key, txt))
    sig = (case.get("email") or {}).get("signature", "")
    if sig:
        items.append(("邮件落款", sig))
    for i, a in enumerate(case.get("adjusts") or [], 1):
        if a.get("x"):
            items.append(("调整·%s" % (a.get("t") or i), a["x"]))
    for s in case.get("scenarios") or []:
        if s.get("rec"):
            items.append(("场景·%s 推荐版" % s.get("n", ""), s["rec"]))
        if s.get("short"):
            items.append(("场景·%s 最简版" % s.get("n", ""), s["short"]))
    for r in case.get("replies") or []:
        if r.get("say"):
            items.append(("追问·%s" % (r.get("q", "")[:12]), r["say"]))
    return items


def body_for_case(case):
    """本次要发的四个核心版本，不含场景/追问。"""
    out = []
    for key in VERSION_KEYS:
        ver = (case.get("versions") or {}).get(key)
        if ver:
            out.append((key, version_text(ver)))
    return out


def count_placeholders(text):
    return len(re.findall(r"【待填[^】]*】", text or ""))


def wordcount(text):
    """中文按字计，英文按词计；去掉空白与换行。"""
    t = re.sub(r"\s+", "", text or "")
    return len(t)


def facts_blob(case):
    buf = []
    for f in case.get("facts") or []:
        buf.append(str(f.get("text", "")))
        buf.append(str(f.get("note", "")))
    buf.append(str(case.get("draft", {}).get("raw", "")))
    buf += [str(x) for x in (case.get("allowed_numbers") or [])]
    return "\n".join(buf)


# ---------------------------------------------------------------- 守卫

def guard(case):
    """返回 [(level, code, message)]。level ∈ ERROR / WARN / INFO。"""
    problems = []
    add = problems.append

    def E(code, msg): add(("ERROR", code, msg))
    def W(code, msg): add(("WARN", code, msg))

    # 1 结构
    for k in REQUIRED_TOP:
        if k not in case:
            E("SCHEMA_MISSING", "缺少必需字段：%s" % k)
    versions = case.get("versions") or {}
    for k in VERSION_KEYS:
        if k not in versions:
            E("VERSION_INCOMPLETE", "缺少版本 %s（必须 A/B/C/D 齐全）" % k)
        elif not (versions[k].get("para") or versions[k].get("cells")):
            E("VERSION_INCOMPLETE", "版本 %s 没有任何正文" % k)
    if not case.get("facts"):
        E("SCHEMA_MISSING", "facts 为空：至少要有 1 条事实台账")
    if not case.get("audit"):
        E("SCHEMA_MISSING", "audit 为空：事实必须逐条进审计")

    # 2 事实覆盖
    fact_ids = [f.get("id") for f in (case.get("facts") or [])]
    audit_ids = [a.get("id") for a in (case.get("audit") or [])]
    for fid in fact_ids:
        if fid not in audit_ids:
            E("AUDIT_INCOMPLETE", "事实 %s 没有出现在审计表里" % fid)
    for row in case.get("audit") or []:
        for k in VERSION_KEYS:
            sym = (row.get("v") or {}).get(k, "")
            if sym not in SYMBOLS:
                E("AUDIT_SYMBOL_MISSING", "审计 %s 的 %s 列为空或符号非法（%r），只能用 ✔ ◐ — ▲"
                  % (row.get("id"), k, sym))

    # 3 正文扫描
    blob_facts = facts_blob(case)
    ban = [p for p in (case.get("product_profile", {}).get("ban_phrases") or []) if p]

    for where, txt in output_texts(case):
        if not txt:
            continue
        # 3.1 数字
        for m in NUMBER_RE.finditer(txt):
            num, unit = m.group(1), m.group(2)
            if num in blob_facts:
                continue
            ctx = txt[max(0, m.start() - 12):m.end() + 6].replace("\n", " ")
            E("UNSOURCED_NUMBER", "%s 出现未登记数字「%s%s」（上下文：…%s…）" % (where, num, unit, ctx))
        for m in CN_NUM_RE.finditer(txt):
            if m.group(0) in blob_facts:
                continue
            ctx = txt[max(0, m.start() - 10):m.end() + 4].replace("\n", " ")
            W("UNSOURCED_NUMBER_CN", "%s 出现中文数量「%s」，确认是否有出处（…%s…）" % (where, m.group(0), ctx))
        # 3.2 承诺词
        for w in PROMISE_WORDS:
            if w in txt:
                E("BANNED_PROMISE", "%s 出现承诺词「%s」" % (where, w))
        # 3.3 稀缺话术
        for w in SCARCITY_WORDS:
            if w in txt:
                E("FAKE_SCARCITY", "%s 出现无据稀缺话术「%s」" % (where, w))
        # 3.4 产品禁语
        for w in ban:
            if w in txt:
                E("BANNED_PHRASE", "%s 命中本品类禁语「%s」" % (where, w))

    # 4 渠道格式
    a = versions.get("A", {})
    b = versions.get("B", {})
    if a and wordcount(version_text(a)) > 220:
        W("CHANNEL_TOO_LONG", "A 版 %d 字，超过微信建议的 220 字" % wordcount(version_text(a)))
    if b and wordcount(version_text(b)) > 80:
        W("CHANNEL_TOO_LONG", "B 版 %d 字，超过「更短」的 80 字" % wordcount(version_text(b)))
    for k in VERSION_KEYS:
        t = version_text(versions.get(k, {}))
        if t.count("？") + t.count("?") >= 3:
            W("MULTI_REQUEST", "%s 版含 %d 个问句，可能一次提了多个请求" % (k, t.count("？") + t.count("?")))
    c = versions.get("C", {})
    if c and ("邮件" in (c.get("media") or "") or c.get("key") == "C"):
        if not (case.get("email") or {}).get("subject"):
            E("EMAIL_NO_SUBJECT", "C 版是邮件版，但 email.subject 为空")

    # 5 占位符对账
    phs = case.get("placeholders") or []
    used = sum(count_placeholders(version_text(versions.get(k, {}))) for k in VERSION_KEYS)
    if used > len(phs):
        E("PLACEHOLDER_MISMATCH",
          "正文出现 %d 处【待填】，但占位符清单只有 %d 条（少 %d 条未登记）" % (used, len(phs), used - len(phs)))
    for p in phs:
        if not (p.get("owner") or "").strip():
            E("PLACEHOLDER_NO_OWNER", "占位符 %s「%s」没有写确认人" % (p.get("id"), p.get("item")))

    # 6 审计计数
    zeros = {s.get("k"): s.get("v") for s in (case.get("audit_summary") or [])}
    for k, v in zeros.items():
        if k and ("价格" in k or "折扣" in k or "交期" in k or "客户需求" in k):
            if str(v).strip() != "0":
                E("BOUNDARY_NOT_ZERO", "「%s」不为 0（当前 %s）：有新增即不得交付" % (k, v))

    # 7 空转检查：只对「标为可用、且未被显式排除」的事实提示
    disp = {f.get("id"): (f.get("disposal") or "") for f in (case.get("facts") or [])}
    for row in case.get("audit") or []:
        d = disp.get(row.get("id"), "")
        should_use = d.startswith("可用") and ("不进正文" not in d) and ("作话题" not in d)
        if should_use and all((row["v"].get(k) or "") in ("—", "▲") for k in VERSION_KEYS):
            W("FACT_UNUSED", "事实 %s 标为可用，但四个版本里都是「未提/删除」，复核是否漏用" % row.get("id"))
    return problems


def summarize(problems):
    e = sum(1 for p in problems if p[0] == "ERROR")
    w = sum(1 for p in problems if p[0] == "WARN")
    return e, w


def stats(case):
    versions = case.get("versions") or {}
    return {
        "facts": len(case.get("facts") or []),
        "audit": len(case.get("audit") or []),
        "placeholders": len(case.get("placeholders") or []),
        "scenarios": len(case.get("scenarios") or []),
        "adjusts": len(case.get("adjusts") or []),
        "replies": len(case.get("replies") or []),
        "checklist": len(case.get("checklist") or []),
        "words": {k: wordcount(version_text(versions.get(k, {}))) for k in VERSION_KEYS},
    }


def out_paths(case, outdir):
    stem = case.get("meta", {}).get("file_stem") or "case"
    os.makedirs(outdir, exist_ok=True)
    return (os.path.join(outdir, stem + ".xlsx"),
            os.path.join(outdir, stem + ".html"))
