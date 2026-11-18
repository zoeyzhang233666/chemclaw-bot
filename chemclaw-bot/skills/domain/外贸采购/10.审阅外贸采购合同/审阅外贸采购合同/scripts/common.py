"""审阅外贸采购合同 —— 共享数据契约与硬校验器。

一份数据集（contract.json + review.json）同时驱动：
  * 交互式 HTML 审阅报告   build_review_html.py
  * Excel 问题清单工作簿   build_review_xlsx.py
  * 中英对照模拟合同 DOCX  build_contract_docx.py
  * 英文澄清/修改函草稿     build_clarification_letter.py

设计原则：
  1. 校验不过直接失败，绝不静默丢条目（CaseError）。
  2. 所有「原文引用」必须是 clauses[].text 的逐字子串 —— 由 check_quotes() 硬校验。
  3. 统计数字（summary.stats）必须与实际条目一致 —— 由 validate_case() 硬校验。

被任何 agent / 宿主（DSH、Claude Code、codex、终端）调用时，
只依赖 Python 3.9+ 标准库 + python-docx / openpyxl（生成 Office 文件时）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
KINDS = ("缺失", "表述不清", "写了但对我方不利")
KIND_ORDER = {k: i for i, k in enumerate(KINDS)}
PRIORITIES = ("高", "中", "低")
STATUSES = ("待处理", "跟进中", "已确认", "待供应商回复", "已解决", "不适用")
OWNERS = ("legal", "procurement", "supplier")
SEVERITY_LABEL = {5: "极高", 4: "高", 3: "中", 2: "低", 1: "提示"}

# 合同侧「角色」枚举：决定审查方向
SIDE_CN = {"buyer": "买方", "seller": "卖方", "agent": "代理"}

# 语言标识：英文原文条款必须带 zh（中文译文）用于左右对照
LANGS = ("en-zh", "zh", "en")


class CaseError(ValueError):
    """数据不一致。调用方应直接中止构建并修复数据，而不是绕过。"""


# ---------------------------------------------------------------------------
# 加载
# ---------------------------------------------------------------------------
def load_case(directory: str | Path) -> dict:
    """读取 <dir> 下的合同 JSON 与审查 JSON。

    识别规则：顶层含 "clauses" 的是合同，含 "findings" 的是审查。
    """
    d = Path(directory)
    contract = review = None
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CaseError(f"{f.name} 不是合法 JSON: {e}") from e
        if isinstance(data, dict) and "clauses" in data and contract is None:
            contract = data
            contract["_source"] = f.name
        elif isinstance(data, dict) and "findings" in data and review is None:
            review = data
            review["_source"] = f.name
    if not contract or not review:
        raise CaseError(f"{d} 需要同时包含 合同JSON(clauses) 与 审查JSON(findings)")
    return {"contract": contract, "review": review}


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------
_RE_NUMERIC_EVIDENCE = re.compile(r"\d")


def validate_case(contract: dict, review: dict) -> dict:
    """返回 {"errors": [...], "warnings": [...], "stats": {...}}。errors 非空必须中止。"""
    errors: list[str] = []
    warnings: list[str] = []

    clauses_list = contract.get("clauses", [])
    clauses = {c["id"]: c for c in clauses_list}
    sections = {s["id"]: s for s in contract.get("sections", [])}
    findings = review.get("findings", [])
    topics = {t["id"] for t in review.get("topics", [])}

    # --- 合同基础 ---
    if len(clauses) != len(clauses_list):
        errors.append("合同条款 id 存在重复")
    if contract.get("language", "en-zh") not in LANGS:
        errors.append(f"contract.language 非法: {contract.get('language')}")

    for s in contract.get("sections", []):
        for cid in s.get("clause_ids", []):
            if cid not in clauses:
                errors.append(f"章节 {s['id']} 引用未知条款 {cid}")
            elif clauses[cid].get("sec") != s["id"]:
                errors.append(f"条款 {cid} 的 sec 字段与章节 {s['id']} 不一致")

    for c in clauses_list:
        for field in ("id", "sec", "no", "page", "text"):
            if not c.get(field):
                errors.append(f"条款 {c.get('id', '?')} 缺少必填字段 {field}")
        if c.get("sec") not in sections:
            errors.append(f"条款 {c['id']} 指向未知章节 {c.get('sec')}")
        if contract.get("language", "en-zh") == "en-zh" and not c.get("zh") and not c.get("kind"):
            warnings.append(f"条款 {c['id']} 为英文但缺少中文对照 zh")

    # --- 风险条目 ---
    if len({f["id"] for f in findings}) != len(findings):
        errors.append("风险条目 id 存在重复")

    stats = {"kind": {}, "severity": {}, "topic": {}, "clause_hit": {}, "owner": {}}
    for f in findings:
        fid = f.get("id", "?")
        if f.get("topic") not in topics:
            errors.append(f"{fid} 主题未知: {f.get('topic')}")
        if f.get("kind") not in KINDS:
            errors.append(f"{fid} 风险类型未知: {f.get('kind')}")
        if not isinstance(f.get("severity"), int) or not 1 <= f["severity"] <= 5:
            errors.append(f"{fid} severity 必须为 1-5 整数")
        if not f.get("clause_ids"):
            errors.append(f"{fid} 未引用任何条款（无 trace 的发现不得进入总表）")
        for cid in f.get("clause_ids", []):
            if cid not in clauses:
                errors.append(f"{fid} 引用未知条款 {cid}")
            stats["clause_hit"][cid] = stats["clause_hit"].get(cid, 0) + 1
        for field in ("title", "what_written", "business_impact"):
            if not f.get(field):
                errors.append(f"{fid} 缺少 {field}")
        if f.get("kind") == "缺失" and not f.get("what_missing"):
            errors.append(f"{fid} 为「缺失」类，必须填写 what_missing")
        if not f.get("to_confirm"):
            errors.append(f"{fid} 缺少 to_confirm（待确认问题）")
        if not f.get("business_impact_from_contract", True):
            pass
        # 业务影响含数字时必须给出口径依据
        if _RE_NUMERIC_EVIDENCE.search(f.get("business_impact", "")) and not f.get("impact_basis"):
            warnings.append(f"{fid} 业务影响含数字但未提供 impact_basis（测算口径），请补")
        for o in f.get("owner", []):
            stats["owner"][o] = stats["owner"].get(o, 0) + 1
        stats["kind"][f["kind"]] = stats["kind"].get(f["kind"], 0) + 1
        stats["severity"][f["severity"]] = stats["severity"].get(f["severity"], 0) + 1
        stats["topic"][f["topic"]] = stats["topic"].get(f["topic"], 0) + 1

    # --- 原文引用逐字校验 ---
    quote_errors = check_quotes(contract, review)
    errors.extend(quote_errors)

    # --- 法规核对表 ---
    law_names = {r["name"] for r in review.get("legal_refs", [])}
    for f in findings:
        for ref in f.get("law_refs", []):
            if ref not in law_names:
                warnings.append(f"{f['id']} 引用的法规 {ref} 未在 legal_refs 中登记")
    for r in review.get("legal_refs", []):
        for field in ("name", "scope", "status", "status_basis", "relevance", "url"):
            if not r.get(field):
                errors.append(f"legal_refs 条目缺少 {field}: {r.get('name', '?')}")
        if "现行" in r.get("status", "") and "核对" not in r.get("status_basis", "") and "日期" not in r.get("status_basis", ""):
            warnings.append(f"法规 {r['name']} 标注现行但 status_basis 未见核对日期")

    # --- 待确认清单 ---
    fids = {f["id"] for f in findings}
    for owner, items in review.get("confirmations", {}).items():
        if owner not in OWNERS:
            errors.append(f"confirmations 未知办理方 {owner}")
        if not items:
            warnings.append(f"confirmations.{owner} 为空（三张清单都应非空）")
        for q in items:
            if q.get("finding_id") not in fids:
                errors.append(f"待确认问题引用未知风险 {q.get('finding_id')}")
            if q.get("priority") not in PRIORITIES:
                errors.append(f"待确认问题优先级非法: {q.get('priority')}")

    # --- summary 一致性 ---
    st = review.get("summary", {}).get("stats")
    if st:
        if st.get("total") not in (None, len(findings)):
            errors.append(f"summary.stats.total={st.get('total')} 与风险条数 {len(findings)} 不一致")
        if st.get("by_kind") and dict(sorted(st["by_kind"].items())) != dict(sorted(stats["kind"].items())):
            errors.append(f"summary.stats.by_kind 与实测不一致: {st['by_kind']} vs {stats['kind']}")
        if st.get("by_severity"):
            measured = {str(k): v for k, v in sorted(stats["severity"].items())}
            if st["by_severity"] != measured:
                errors.append(f"summary.stats.by_severity 与实测不一致: {st['by_severity']} vs {measured}")
        if st.get("by_topic") and dict(sorted(st["by_topic"].items())) != dict(sorted(stats["topic"].items())):
            errors.append(f"summary.stats.by_topic 与实测不一致: {st['by_topic']} vs {stats['topic']}")

    uncovered = [cid for cid in clauses if cid not in stats["clause_hit"] and not clauses[cid].get("kind")]
    if uncovered:
        warnings.append(f"未被任何风险条目引用的正文条款: {', '.join(uncovered)}")
    stats["uncovered"] = uncovered
    stats["total"] = len(findings)
    return {"errors": errors, "warnings": warnings, "stats": stats}


def check_quotes(contract: dict, review: dict) -> list[str]:
    """硬校验：findings[].quotes[].text 必须是同一条款 clauses[].text 的逐字子串。

    这是本 skill 的「不编造原文」底线。允许全半角空白差异与 U+2019/’ 差异。
    """
    clauses = {c["id"]: c for c in contract.get("clauses", [])}
    errs: list[str] = []
    for f in review.get("findings", []):
        for q in f.get("quotes", []) or []:
            cid = q.get("clause_id")
            if cid not in clauses:
                errs.append(f"{f['id']} 的引用指向未知条款 {cid}")
                continue
            if not q.get("text"):
                errs.append(f"{f['id']} 的引用（{cid}）缺少 text")
                continue
            if not _contains_verbatim(q["text"], clauses[cid]["text"]):
                errs.append(f"{f['id']} 的引用（{cid}）不是原文逐字摘录: 「{q['text'][:40]}…」")
    return errs


def _norm(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _contains_verbatim(quote: str, source: str) -> bool:
    return _norm(quote) in _norm(source)


# ---------------------------------------------------------------------------
# 便捷工具
# ---------------------------------------------------------------------------
def excerpt(text: str, max_len: int = 160) -> str:
    """单行逐字摘录（超长时在标点处截断并加省略号），绝不改写语义。"""
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= max_len:
        return flat
    cut = flat[:max_len]
    for sep in ("；", "。", "，", "、", ";", ".", ","):
        idx = cut.rfind(sep)
        if idx >= max_len * 0.5:
            return cut[: idx + 1] + "……"
    return cut + "……"


def clause_locator(c: dict) -> str:
    """人类可读定位串：第三条 3.1 · P2（第 2 页 第 3 行）。"""
    line = c.get("page_line") or ""
    return f'{c.get("no", "")} · P{c.get("page", "?")}' + (f"（{line}）" if line else "")


def money(x: float) -> str:
    return f"{x:,.0f}"


def esc(s) -> str:
    import html

    return html.escape(str(s), quote=True)


def counts_by(review: dict, key: str) -> list[tuple[str, int]]:
    from collections import Counter

    return Counter(f[key] for f in review["findings"]).most_common()


def owner_label(owner: str, roles: dict | None = None) -> str:
    roles = roles or {}
    return roles.get(owner) or {"legal": "公司法务", "procurement": "采购/进口", "supplier": "海外供应商"}.get(owner, owner)


def ensure_ok(check: dict, context: str = "") -> None:
    """错误即中止；警告打印到 stderr。"""
    import sys

    if check["errors"]:
        raise SystemExit(
            f"数据校验失败{'（' + context + '）' if context else ''}:\n  "
            + "\n  ".join(check["errors"])
        )
    for w in check["warnings"]:
        print(f"WARN: {w}", file=sys.stderr)
