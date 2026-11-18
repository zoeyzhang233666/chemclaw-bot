# -*- coding: utf-8 -*-
"""
ovslib.py — shared constants and helpers for overseas-supplier-verification.

Design rule of this skill: NO risk scores. The only vocabulary is a four-state
verification verdict plus evidence grades. Everything else must cite evidence.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import date, datetime

# ---------------------------------------------------------------- encoding
def force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------- vocabulary
STATE_ORDER = ["verified", "doubt", "unverified", "unknown", "na"]
STATE = {
    "verified":   {"zh": "已核实", "en": "Verified",        "tone": "ok"},
    "doubt":      {"zh": "存在疑点", "en": "Flagged",         "tone": "warn"},
    "unverified": {"zh": "未核实", "en": "Not verified",    "tone": "mid"},
    "unknown":    {"zh": "未知", "en": "Unknown",          "tone": "mute"},
    "na":         {"zh": "不适用", "en": "N/A",            "tone": "mute"},
}
_STATE_ALIASES = {}
for _k, _v in STATE.items():
    _STATE_ALIASES[_k] = _k
    _STATE_ALIASES[_v["zh"]] = _k
    _STATE_ALIASES[_v["en"].lower()] = _k

EVID_GRADE = {
    "primary":   {"zh": "一手/官方",   "desc": "政府登记、监管披露、上市公司公告、企业官网原件"},
    "secondary": {"zh": "二手/媒体",   "desc": "行业协会、行业数据库、主流财经媒体、贸易资讯"},
    "tertiary":  {"zh": "三手/百科",   "desc": "百科、名录站、转述、论坛"},
    "mock":      {"zh": "模拟件",      "desc": "为演示而制作的虚构文件，绝不可作为事实依据"},
}
EVID_STANCE = {
    "support": {"zh": "支持", "desc": "支持被核验事实成立"},
    "context": {"zh": "背景", "desc": "提供背景，不单独构成认定"},
    "note":    {"zh": "说明", "desc": "记录限制或方法性说明"},
}

VERDICT = {
    "identify_only":      {"zh": "仅识别身份", "desc": "主体可识别，但交易层面未闭环；不可直接付款"},
    "proceed_with_gaps":  {"zh": "可推进但需补证", "desc": "关键要素大部分可核，缺口明确且可补"},
    "hold":               {"zh": "暂停推进",     "desc": "存在必须先澄清的主体或收款问题"},
    "insufficient":       {"zh": "证据不足",     "desc": "无法识别主体，需重新取证或更换候选"},
}

PRIORITY = {"高": "high", "中": "mid", "低": "low", "high": "high", "mid": "mid", "low": "low"}

LAYER_ZH = {
    "shareholder": "股东层", "group_parent": "集团层", "manufacturer": "生产层",
    "manufacturer_jv": "生产层（合资）", "contract_party": "交易层",
    "beneficiary": "交易层（收款）", "exporter": "交易层（出口）",
    "agent": "交易层（代理）", "distributor": "交易层（经销）", "trader": "交易层（贸易）",
}

BANNED_SCORE_KEYS = re.compile(
    r'("(?:risk_score|score|rating|credit_rating|trust_score|risk_grade)"\s*:)', re.I)


# ---------------------------------------------------------------- helpers
def norm_state(value, default="unknown"):
    if value is None:
        return default
    s = str(value).strip()
    if not s:
        return default
    return _STATE_ALIASES.get(s, _STATE_ALIASES.get(s.lower(), default))


def state_zh(value) -> str:
    return STATE[norm_state(value)]["zh"]


def state_tone(value) -> str:
    return STATE[norm_state(value)]["tone"]


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_project(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def safe_name(text: str, maxlen: int = 90) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(text)).strip("._ ")
    return text[:maxlen] or "supplier"


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def parse_date(text):
    """Parse common date strings; return date or None."""
    if not text:
        return None
    if isinstance(text, (date, datetime)):
        return text if isinstance(text, date) else text.date()
    s = str(text).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def evid_ids(value) -> list:
    """'E01,E04' | ['E01'] | 'E01 E04' -> ['E01','E04']"""
    out = []
    for chunk in as_list(value):
        for part in re.split(r"[,;、\s]+", str(chunk)):
            part = part.strip()
            if re.fullmatch(r"[EF]\d{1,3}", part):
                out.append(part)
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def count_states(items, key="state") -> dict:
    counts = {k: 0 for k in STATE_ORDER}
    for it in items or []:
        counts[norm_state(it.get(key) if isinstance(it, dict) else None)] += 1
    return counts


def iter_block_rows(project: dict):
    """Yield (section, block, row) for every table row of every section."""
    for sec in project.get("sections", []):
        for block in sec.get("blocks", []):
            if block.get("type") == "table":
                for row in block.get("rows", []):
                    yield sec, block, row


def iter_state_carriers(project: dict):
    """Every dict that carries a 'state' field, tagged with where it came from.

    A table row participates only when it actually carries a state word in the
    column right before the evidence column (or right before a trailing note
    column). Free-form tables (assumptions, ordering checklists) are skipped
    instead of being misread.
    """
    for sec, block, row in iter_block_rows(project):
        if not isinstance(row, list) or len(row) < 3:
            continue
        found = None
        for idx in range(len(row) - 1, 0, -1):
            if norm_state(row[idx], default=None) is not None:
                found = idx
                break
        if found is None:
            continue
        evid = row[found + 1] if found + 1 < len(row) else ""
        yield {"kind": "table", "section": sec.get("id"), "block": block.get("name"),
               "label": row[0], "state": row[found], "evid": evid}
    for item in project.get("entity_map", []) or []:
        yield {"kind": "entity", "section": "entity_map", "block": "entity_map",
               "label": item.get("entity"), "state": item.get("state"), "evid": item.get("evidence")}
    for row in ((project.get("s05") or {}).get("rows") or []):
        yield {"kind": "matrix", "section": "s05", "block": "matrix",
               "label": row.get("item"), "state": row.get("state"), "evid": row.get("evid", "")}
    for sec in project.get("sections", []):
        for block in sec.get("blocks", []):
            if block.get("type") == "matrix_map":
                for row in block.get("rows", []):
                    yield {"kind": "matrix", "section": sec.get("id"), "block": "matrix_map",
                           "label": row.get("item"), "state": row.get("state"), "evid": row.get("evid", "")}


def doc_check_summary(doc: dict) -> dict:
    checks = doc.get("checks") or []
    total = len(checks)
    ok = sum(1 for c in checks if c.get("ok"))
    return {"total": total, "ok": ok, "fail": total - ok}


def derive_doc_state(doc: dict) -> str:
    if not doc.get("provided"):
        return "unknown"
    if doc.get("mock"):
        s = doc_check_summary(doc)
        return "doubt" if s["fail"] else "unverified"
    s = doc_check_summary(doc)
    if s["total"] == 0:
        return "unverified"
    return "verified" if s["fail"] == 0 else "doubt"


def collect_all_states(project: dict) -> dict:
    carriers = list(iter_state_carriers(project))
    return count_states(carriers)


def require_openpyxl():
    try:
        import openpyxl  # noqa: F401
        return True
    except Exception:
        return False
