#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""overseas-inquiry-kyc · 共享工具：读入、归一化、派生统计。

不联网、不依赖第三方库（除了 HTML/Excel 生成器各自的 openpyxl）。
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

# ---------------------------------------------------------------- 状态词表

STATUS_LABEL = {
    "verified": "已核实",
    "discrepancy": "存在疑点",
    "unverified": "未核实",
    "not_applicable": "不适用",
}
STATUS_ORDER = ["verified", "discrepancy", "unverified", "not_applicable"]
STATUS_ALIASES = {
    "已核实": "verified", "核实": "verified", "verified": "verified", "pass": "verified", "ok": "verified",
    "存在疑点": "discrepancy", "疑点": "discrepancy", "矛盾": "discrepancy",
    "discrepancy": "discrepancy", "conflict": "discrepancy", "flag": "discrepancy",
    "未核实": "unverified", "缺失": "unverified", "unverified": "unverified",
    "missing": "unverified", "unknown": "unverified", "gap": "unverified",
    "不适用": "not_applicable", "not_applicable": "not_applicable", "na": "not_applicable",
}

# 证据等级（与 references/evidence-grading.md 对应）
GRADE_LABEL = {
    "A": "A · 官方登记/政府公示",
    "B": "B · 独立第三方/企业官网一手",
    "C": "C · 媒体转载/行业名录/社媒",
    "D": "D · 对方自述/未验证线索",
}

SEVERITY_LABEL = {"high": "高", "medium": "中", "low": "低"}
SEVERITY_ORDER = ["high", "medium", "low"]

MISMATCH_LABEL = {
    "same": "一致",
    "partial": "部分一致",
    "different": "不一致",
    "unknown": "无法比对",
    "misattribution": "疑似错配（同名/异主体）",
}

# 五个核验区块（页面导航顺序固定）
SECTIONS = [
    {"id": "A", "key": "identity", "title": "身份核验", "subtitle": "主体是否真实存在、名称与登记是否一致"},
    {"id": "B", "key": "business", "title": "业务相关性", "subtitle": "主营业务与询价产品是否合理相关"},
    {"id": "C", "key": "contact", "title": "网站域名与联系方式", "subtitle": "官网、域名、邮箱、地址、电话是否自洽"},
    {"id": "D", "key": "risk", "title": "公开风险", "subtitle": "经营异常、诉讼、制裁、负面报道"},
    {"id": "E", "key": "gaps", "title": "待补充资料", "subtitle": "需要向对方索取的材料与下一步动作"},
]


# ---------------------------------------------------------------- 工具

def norm_status(v, default="unverified"):
    if v is None:
        return default
    s = str(v).strip()
    key = s.lower().replace("-", "_").replace(" ", "_")
    if key in STATUS_ALIASES:
        return STATUS_ALIASES[key]
    if s in STATUS_ALIASES:
        return STATUS_ALIASES[s]
    return default


def norm_severity(v):
    s = str(v or "").strip().lower()
    table = {"高": "high", "中": "medium", "低": "low", "high": "high", "medium": "medium", "low": "low"}
    return table.get(s, "medium")


def norm_grade(v):
    s = str(v or "").strip().upper()[:1]
    return s if s in ("A", "B", "C", "D") else "D"


def as_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [x for x in v if x not in (None, "")]
    if isinstance(v, str):
        return [x.strip() for x in v.split(";") if x.strip()]
    return [v]


def load_json(path):
    # utf-8-sig：容忍 Windows 记事本/PowerShell 写入的 BOM
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_text(path, text):
    ensure_dir(os.path.dirname(os.path.abspath(path)) or ".")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 归一化

def normalize(D):
    """把原始 JSON 补成生成器可直接消费的形状；不修改语义，只补默认值。"""
    meta = D.setdefault("meta", {})
    meta.setdefault("title", "海外询盘企业核验报告")
    meta.setdefault("as_of", datetime.now().strftime("%Y-%m-%d"))
    meta.setdefault("lang", "zh-CN")
    meta.setdefault("synthetic", True)
    meta.setdefault(
        "disclaimer",
        "本报告为公开信息核验辅助材料，不构成法律尽调、投资建议或对交易对手的定性；"
        "所有“未核实”不等同于“虚假”。",
    )

    # --- 来源
    sources = D.setdefault("sources", [])
    seen = set()
    for s in sources:
        s["id"] = str(s.get("id") or "").strip()
        s["grade"] = norm_grade(s.get("grade"))
        s["url"] = (s.get("url") or "").strip()
        s["retrieved"] = (s.get("retrieved") or meta.get("as_of") or "").strip()
        s["kind"] = s.get("kind") or "other"
        s["reliability"] = s.get("reliability") or 3
        if not s["id"]:
            raise ValueError("sources[] 存在缺少 id 的条目")
        if s["id"] in seen:
            raise ValueError(f"sources[] 存在重复 id：{s['id']}")
        seen.add(s["id"])

    # --- 字段提取
    fields = D.setdefault("fields", [])
    for i, f in enumerate(fields, 1):
        f.setdefault("id", f"F{i:02d}")
        f["status"] = norm_status(f.get("status"), "verified")
        f["confidence"] = str(f.get("confidence") or "medium").lower()
        f["source_ids"] = [x for x in as_list(f.get("source_ids"))]
    # 提取字段清单（把询盘里的原文抽成结构化字段）
    ext = D.setdefault("extraction", [])
    for i, e in enumerate(ext, 1):
        e.setdefault("id", f"X{i:02d}")
    # --- 五区块核验项
    checks = D.setdefault("checks", [])
    for i, c in enumerate(checks, 1):
        c.setdefault("id", f"K{i:02d}")
        c["section"] = str(c.get("section") or "A").upper()
        c["status"] = norm_status(c.get("status"))
        c["severity"] = norm_severity(c.get("severity"))
        c["source_ids"] = as_list(c.get("source_ids"))
        c["next_ids"] = as_list(c.get("next_ids"))
        c["question"] = c.get("question") or c.get("title") or ""
        c.setdefault("finding", "")
        c.setdefault("boundary", "")
        c.setdefault("verified_facts", [])
        c.setdefault("doubts", [])
        c.setdefault("unknowns", [])

    # --- 联系方式一致性矩阵
    matrix = D.setdefault("matrix", [])
    for i, r in enumerate(matrix, 1):
        r.setdefault("id", f"M{i:02d}")
        r["mismatch"] = str(r.get("mismatch") or "unknown").lower()

    # --- 关联主体（同名/冒用排查）
    linkage = D.setdefault("linkage", [])
    for i, l in enumerate(linkage, 1):
        l.setdefault("id", f"L{i:02d}")
        l["relation"] = str(l.get("relation") or "unknown").lower()

    # --- 风险
    risks = D.setdefault("risks", [])
    for i, r in enumerate(risks, 1):
        r.setdefault("id", f"R{i:02d}")
        r["severity"] = norm_severity(r.get("severity"))
        r["status"] = norm_status(r.get("status"))
        r["source_ids"] = as_list(r.get("source_ids"))

    # --- 业务相关性
    bid = D.get("business_fit") or {}
    for i, k in enumerate(bid.get("keywords", []), 1):
        k.setdefault("id", f"B{i:02d}")
        k["status"] = norm_status(k.get("status"))
    for i, s in enumerate(bid.get("signals", []), 1):
        s.setdefault("id", f"S{i:02d}")
        s["status"] = norm_status(s.get("status"))
        s.setdefault("strength", "medium")

    # --- 资料清单 & 行动
    asks = D.setdefault("requests", [])
    for i, a in enumerate(asks, 1):
        a.setdefault("id", f"Q{i:02d}")
        a["priority"] = str(a.get("priority") or "P1").upper()
        a["source_ids"] = as_list(a.get("source_ids"))
    actions = D.setdefault("actions", [])
    for i, a in enumerate(actions, 1):
        a.setdefault("id", f"T{i:02d}")
        a["priority"] = str(a.get("priority") or "P1").upper()
        a["status"] = str(a.get("status") or "open").lower()

    # --- 消息草稿
    D.setdefault("messages", [])

    # --- 询盘原文（含邮件、名片等）
    D.setdefault("inquiry",
                 {"subject": "", "from": "", "to": "", "date": "", "body_lines": [], "attachments": []})

    # 引用完整性：source_ids 必须存在；next_ids 必须指向 requests
    request_ids = {str(a["id"]) for a in (D.get("requests") or [])}
    for coll in ("checks", "risks", "fields", "extraction", "requests", "actions"):
        for row in D.get(coll) or []:
            for sid in as_list(row.get("source_ids")):
                if sid not in seen:
                    raise ValueError(f"{coll}[{row.get('id')}] 引用了不存在的 source_id：{sid}")
            nids = [str(x) for x in as_list(row.get("next_ids"))]
            row["next_ids"] = nids
            for nid in nids:
                if nid not in request_ids:
                    raise ValueError(f"{coll}[{row.get('id')}] 的 next_ids 指向不存在的请求项：{nid}")

    D["stats"] = build_stats(D)
    return D


def build_stats(D):
    st = {"status": {k: 0 for k in STATUS_ORDER}, "section": {}, "severity": {k: 0 for k in SEVERITY_ORDER},
          "sources": len(D.get("sources") or []), "source_grade": {}, "requests": {"P0": 0, "P1": 0, "P2": 0},
          "actions_open": 0, "risks": len(D.get("risks") or [])}
    for c in D.get("checks") or []:
        st["status"][c["status"]] = st["status"].get(c["status"], 0) + 1
        sec = c["section"]
        st["section"].setdefault(sec, {k: 0 for k in STATUS_ORDER})
        st["section"][sec][c["status"]] += 1
        if c["status"] == "discrepancy":
            st["severity"][c["severity"]] += 1
    for r in D.get("risks") or []:
        if r["status"] == "discrepancy":
            st["severity"][r["severity"]] += 1
    for s in D.get("sources") or []:
        st["source_grade"][s["grade"]] = st["source_grade"].get(s["grade"], 0) + 1
    for q in D.get("requests") or []:
        if q["priority"] in st["requests"]:
            st["requests"][q["priority"]] += 1
    for a in D.get("actions") or []:
        if a["status"] == "open":
            st["actions_open"] += 1
    st["checks_total"] = len(D.get("checks") or [])
    st["verdict_line"] = verdict_line(D)
    return st


def verdict_line(D):
    """按规则生成一句话结论（规则固定，不自由发挥）。"""
    checks = D.get("checks") or []
    if not checks:
        return "—"
    dis = [c for c in checks if c["status"] == "discrepancy"]
    ver = [c for c in checks if c["status"] == "verified"]
    unv = [c for c in checks if c["status"] == "unverified"]
    hi = [c for c in dis if c["severity"] == "high"]
    if hi:
        return "存在高等级疑点，建议暂停报价与发运，先完成 P0 资料核验"
    if dis:
        return "主体与业务逻辑未见硬矛盾，但存在需解释的疑点，可继续商业沟通并同步补齐资料"
    if unv:
        return "未发现明显矛盾，但关键项目仍待核实，适合继续沟通并索取补充资料"
    return "公开信息范围内未发现矛盾，可按正常流程推进（仍需保留单据与复核）"


def section_counts(D):
    out = []
    for s in SECTIONS:
        c = (D.get("stats") or {}).get("section", {}).get(s["id"], {})
        out.append({**s, "total": sum(c.values()), "counts": c})
    return out


def find_or_none(items, key, value):
    for it in items or []:
        if it.get(key) == value:
            return it
    return None


def index_sources(D):
    return {s["id"]: s for s in D.get("sources") or []}


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path
