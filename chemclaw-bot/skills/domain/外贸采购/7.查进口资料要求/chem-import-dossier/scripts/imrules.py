#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
importlib.py — 进口资料准备检查的**规则库**（不含任何化工品字面量）

设计原则（对应 SKILL.md 第二节硬纪律）：
  1. 本文件只放「方法论」：阈值比较、状态机、四态、严重度、合规闸门、证据分级。
  2. 任何具体产品的结论（过氧化氢属于危化品目录第 903 项之类）只能来自 data.json。
  3. 所有时间只相对 as_of 计算，禁止 now()。

跨品类复用时：换 data.json 即可，不要改本文件。
"""
from __future__ import annotations

import datetime as _dt
import math
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# 枚举（与 data.json 契约一致）
# --------------------------------------------------------------------------
VERDICTS = ("applies", "not_applies", "conditional", "pending")
DOC_STATUS = ("ok", "partial", "missing", "pending", "expired", "na")
UPLOAD_VERDICT = ("usable", "usable_with_fix", "not_usable")
PRIORITIES = ("P0", "P1", "P2")
GATES = ("GATE-1", "GATE-2", "GATE-3", "GATE-4", "GATE-5", "GATE-6")
ACTORS = ("海外供应商", "进口商", "承运人/船公司", "报关代理", "第三方检测机构", "监管机构")
CONFIDENCE = ("high", "medium", "low")

# 结论语气映射：把枚举翻译成人话，禁止出现「一定」「绝对」「完全合规」
VERDICT_TEXT = {
    "applies": "适用",
    "not_applies": "不适用",
    "conditional": "视条件适用",
    "pending": "待核验",
}
DOC_STATUS_TEXT = {
    "ok": "齐备",
    "partial": "有但不完整",
    "missing": "缺失",
    "pending": "待定（需外部确认）",
    "expired": "过期/版本失效",
    "na": "不适用",
}
DOC_STATUS_CLASS = {
    "ok": "ok",
    "partial": "warn",
    "missing": "bad",
    "pending": "warn",
    "expired": "bad",
    "na": "gray",
}
UPLOAD_TEXT = {
    "usable": "可直接使用",
    "usable_with_fix": "需修订后使用",
    "not_usable": "不可用",
}

# 资料完整度权重（分母）：必须=3 视情形=1 建议=0.5
DOC_WEIGHT = {"必须": 3.0, "视情形": 1.0, "建议": 0.5}
STATUS_SCORE = {"ok": 1.0, "partial": 0.55, "missing": 0.0, "pending": 0.25, "expired": 0.0, "na": 1.0}


def norm_status(value: Any) -> str:
    """把内部键（ok/partial/...）或中文标签（齐备/缺失/...）统一成内部键。

    data.json 里既可能出现 "partial"，也可能因为人工编辑写成 "有但不完整"，
    因此所有比较都必须先经过本函数，否则会静默退化成 0 分。
    """
    v = str(value or "").strip()
    if not v:
        return "missing"
    if v in STATUS_SCORE:
        return v
    for key, label in DOC_STATUS_TEXT.items():
        if v == label:
            return key
    for key, label in DOC_STATUS_TEXT.items():
        if v and (v in label or label in v):
            return key
    return "missing"

# 责任主体别名归一
ACTOR_ALIAS = {
    "供应商": "海外供应商",
    "海外供应商": "海外供应商",
    "出口商": "海外供应商",
    "manufacturer": "海外供应商",
    "进口商": "进口商",
    "收货人": "进口商",
    "consignee": "进口商",
    "船公司": "承运人/船公司",
    "承运人": "承运人/船公司",
    "货代": "承运人/船公司",
    "报关行": "报关代理",
    "报关代理": "报关代理",
    "检测机构": "第三方检测机构",
    "实验室": "第三方检测机构",
    "海关": "监管机构",
    "海事局": "监管机构",
    "应急管理部门": "监管机构",
}


def norm_actor(name: str) -> str:
    n = (name or "").strip()
    for k, v in ACTOR_ALIAS.items():
        if k in n:
            return v
    return n or "未指定"


# --------------------------------------------------------------------------
# 日期工具（全部相对 as_of）
# --------------------------------------------------------------------------
def parse_date(s: Any) -> Optional[_dt.date]:
    if not s:
        return None
    if isinstance(s, _dt.date):
        return s
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def days_between(later: Any, earlier: Any) -> Optional[int]:
    a, b = parse_date(later), parse_date(earlier)
    if not a or not b:
        return None
    return (a - b).days


def age_warning(date_str: Any, as_of: str, warn_days: int = 365, hard_days: int = 1095) -> str:
    """文件时效：返回 ok / warn / stale / unknown。"""
    d = days_between(as_of, date_str)
    if d is None:
        return "unknown"
    if d < 0:
        return "future"
    if d > hard_days:
        return "stale"
    if d > warn_days:
        return "warn"
    return "ok"


# --------------------------------------------------------------------------
# 浓度 / 阈值解析
# --------------------------------------------------------------------------
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_OP = re.compile(r"(≥|<=|≤|<|>|＞|＜|>=|=)")


def parse_pct(s: Any) -> Optional[float]:
    """从 '30%（质量分数）' / '20percent<=x<60percent' / '≤60' 里取出第一个数值。"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s)
    m = _PCT.search(t)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return float(m.group(1)) if m else None


def compare(value: Optional[float], op: str, bound: Optional[float]) -> Optional[bool]:
    if value is None or bound is None:
        return None
    op = {"≥": ">=", "≤": "<=", "＞": ">", "＜": "<"}.get(op, op)
    return {
        ">": value > bound,
        ">=": value >= bound,
        "<": value < bound,
        "<=": value <= bound,
        "=": math.isclose(value, bound, abs_tol=1e-9),
    }.get(op)


def threshold_hit(value: Optional[float], rule: Dict[str, Any]) -> Optional[bool]:
    """
    阈值型目录条目 / 运输分级判定。
    rule = {"op": ">=", "value": 8, "upper": None}
    返回 True/False/None（None = 数据不足，必须落 pending）
    """
    if value is None:
        return None
    low = compare(value, rule.get("op", ">="), rule.get("value"))
    if low is None:
        return None
    if rule.get("upper") is not None and rule.get("upper_op"):
        up = compare(value, rule["upper_op"], rule["upper"])
        if up is None:
            return None
        return low and up
    return low


# --------------------------------------------------------------------------
# 资料完整度
# --------------------------------------------------------------------------
def doc_completeness(documents: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0.0
    got = 0.0
    by_group: Dict[str, Dict[str, float]] = {}
    counts = {k: 0 for k in DOC_STATUS}
    for d in documents:
        req = d.get("required", "必须")
        st = norm_status(d.get("status"))
        w = DOC_WEIGHT.get(req, 1.0)
        s = STATUS_SCORE.get(st, 0.0)
        total += w
        got += w * s
        counts[st] = counts.get(st, 0) + 1
        g = d.get("group", "未分组")
        slot = by_group.setdefault(g, {"total": 0.0, "got": 0.0, "n": 0, "ok": 0})
        slot["total"] += w
        slot["got"] += w * s
        slot["n"] += 1
        if st == "ok":
            slot["ok"] += 1
    pct = (got / total * 100.0) if total else 0.0
    groups = {
        k: {**v, "pct": (v["got"] / v["total"] * 100.0) if v["total"] else 0.0}
        for k, v in by_group.items()
    }
    return {
        "pct": round(pct, 1),
        "counts": counts,
        "n_docs": len(documents),
        "n_required": sum(1 for d in documents if d.get("required") == "必须"),
        "n_required_ok": sum(1 for d in documents if d.get("required") == "必须" and norm_status(d.get("status")) == "ok"),
        "groups": groups,
    }


def upload_completeness(uploaded: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    out = {"pass": 0, "fail": 0, "warn": 0, "na": 0}
    for u in uploaded:
        for c in u.get("checks", []):
            out[c.get("result", "na")] = out.get(c.get("result", "na"), 0) + 1
    return out


# --------------------------------------------------------------------------
# 合规闸门（决定「能不能放行」）
# --------------------------------------------------------------------------
GATE_DEFS = {
    "GATE-1": {
        "name": "身份闸门",
        "rule": "CAS/浓度/组成/稳定剂/用途/包装/运输方式全部有证据支撑，且与 PI、SDS、合同一致",
    },
    "GATE-2": {
        "name": "归类闸门",
        "rule": "HS 首选编码可回溯到税则条文与归类决定要素；不确定点已书面移交（报关行/预归类/预裁定）",
    },
    "GATE-3": {
        "name": "监管闸门",
        "rule": "《危险化学品目录》、易制爆/易制毒、两用物项、用途专项（食品/消毒/药品）逐项比对，无 pending",
    },
    "GATE-4": {
        "name": "运输闸门",
        "rule": "UN 编号/类项/包装类别/正确运输名称与 IMDG（或 IATA）一致，包装与积载满足要求",
    },
    "GATE-5": {
        "name": "文件闸门",
        "rule": "中文化学品安全技术说明书、中文危险公示标签、符合性声明、UN 包装标记信息齐备",
    },
    "GATE-6": {
        "name": "税费与原产地闸门",
        "rule": "适用税率（最惠国/协定/暂定）与优惠资格已确认；原产地证书与直接运输条件满足",
    },
}


def gate_status(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """把闸门逐条算成 pass / fail / pending。"""
    out: List[Dict[str, Any]] = []
    pid = data.get("product_identity", {})
    docs = data.get("documents", [])
    regs = data.get("regulation_checklist", [])
    hv = data.get("hs_verdict", {})
    tr = data.get("transport", {})

    # GATE-1 身份
    g1 = "pass"
    if pid.get("identity_verdict") == "pending":
        g1 = "fail"
    elif pid.get("identity_verdict") == "partial" or pid.get("unconfirmed"):
        g1 = "pending"

    # GATE-2 归类
    g2 = "pass"
    candidates = data.get("hs_candidates", [])
    if not candidates:
        g2 = "fail"
    elif any(c.get("confidence") == "低" for c in candidates[:1]) or hv.get("need_classification_ruling") == "是":
        g2 = "pending"

    # GATE-3 监管
    g3 = "pass"
    if not regs:
        g3 = "fail"
    elif any(r.get("verdict") == "pending" for r in regs):
        g3 = "pending"

    # GATE-4 运输
    g4 = "pass"
    if not tr.get("un") and data.get("danger_distinction", {}).get("goods", {}).get("applicable") == "是":
        g4 = "fail"
    elif tr.get("packing_group") in (None, "", "待定"):
        g4 = "pending"

    # GATE-5 文件
    g5 = "pass"
    must = [d for d in docs if d.get("required") == "必须"]
    if not must:
        g5 = "pending"
    elif any(norm_status(d.get("status")) in ("missing", "expired") for d in must):
        g5 = "fail"
    elif any(norm_status(d.get("status")) == "partial" for d in must):
        g5 = "pending"

    # GATE-6 税费
    g6 = "pass"
    fta = data.get("tax_rates", {}).get("fta", [])
    if any(f.get("status") in ("disputed", "pending", "claimed") for f in fta):
        g6 = "pending"

    for code in GATES:
        st = {"GATE-1": g1, "GATE-2": g2, "GATE-3": g3, "GATE-4": g4, "GATE-5": g5, "GATE-6": g6}[code]
        out.append({
            "code": code,
            "name": GATE_DEFS[code]["name"],
            "rule": GATE_DEFS[code]["rule"],
            "status": st,
            "text": data.get("assessment", {}).get("_gate_text", {}).get(code, ""),
        })
    return out


def overall_grade(data: Dict[str, Any]) -> Dict[str, Any]:
    """总体分级。

    规则（按严重度自上而下，取第一条命中）：
      D  — 存在硬缺口：必须件「缺失/过期」，或关键监管判定为 fail
      C  — 待确认项 >= 3 道闸门
      B  — 有 1~2 道闸门待确认（必须件「不完整」或资料已取得但待修正）
      A  — 全部通过

    注意：「必须件不完整（partial）」不等于「缺失」——文件已到手、只是要补正，
    这类应归 B/有条件推进，而不是直接判 D。
    """
    gates = gate_status(data)
    fails = [g for g in gates if g["status"] == "fail"]
    pends = [g for g in gates if g["status"] == "pending"]
    comp = doc_completeness(data.get("documents", []))
    hard = [d for d in data.get("documents", [])
            if d.get("required") == "必须" and norm_status(d.get("status")) in ("missing", "expired")]
    if fails or hard:
        grade, text = "D", "不可放行（存在硬缺口）"
    elif len(pends) >= 3:
        grade, text = "C", "暂缓（待确认事项过多）"
    elif pends:
        grade, text = "B", "有条件推进（待确认项已列明）"
    else:
        grade, text = "A", "资料齐备（可进入报关准备）"
    return {
        "grade": grade,
        "grade_text": text,
        "gates": gates,
        "doc_pct": comp["pct"],
        "n_fail": len(fails),
        "n_pending": len(pends),
        "n_hard_missing": len(hard),
    }


# --------------------------------------------------------------------------
# 证据分级（A 官方 / B 官方转载与数据库 / C 行业与第三方）
# --------------------------------------------------------------------------
SOURCE_TIER = {
    "A": "官方一手（法律原文、税则、部委公告、官方答复、国标原文）",
    "B": "官方转载/政务数据库（地方政府网站转发、单一窗口参数）",
    "C": "行业数据库与商业平台（仅作交叉参考，不作唯一依据）",
}


def source_stats(sources: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    out = {"A": 0, "B": 0, "C": 0}
    for s in sources:
        t = s.get("tier", "C")
        out[t] = out.get(t, 0) + 1
    return out


def unverified_sources(sources: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [s for s in sources if s.get("tier") == "C" or s.get("effective") in ("未核实", "部分替代")]


# --------------------------------------------------------------------------
# 交叉一致性：上传件之间、上传件与录入口径之间
# --------------------------------------------------------------------------
def consistency_issues(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    inp = data.get("inputs", {})
    cas_in = (inp.get("cas") or "").strip()
    conc_in = inp.get("concentration") or ""
    pct_in = parse_pct(conc_in)
    for u in data.get("uploaded", []):
        fields = {f.get("field", ""): f.get("value", "") for f in u.get("extracted", [])}

        # CAS 一致性
        cas_u = next((str(v) for k, v in fields.items() if k.upper().startswith("CAS")), "")
        if cas_in and cas_u and cas_in not in cas_u:
            issues.append({
                "level": "高",
                "item": "CAS 号不一致",
                "detail": f"{u.get('file')} 记录 {cas_u}，本单录入 {cas_in}",
                "fix": "以 SDS 与 COA 原件核对；不一致则不得按本单口径申报",
            })
        # 浓度一致性
        conc_u = next((str(v) for k, v in fields.items() if "浓度" in k or "含量" in k), "")
        pct_u = parse_pct(conc_u)
        if pct_in is not None and pct_u is not None and abs(pct_in - pct_u) > 0.5:
            issues.append({
                "level": "高",
                "item": "浓度口径不一致",
                "detail": f"{u.get('file')} 为 {conc_u}，本单录入为 {conc_in}",
                "fix": "浓度直接决定危化品目录、易制爆与 UN 分级，必须先锁死口径",
            })
        # 语言
        if u.get("lang") and u["lang"] not in ("zh", "mixed") and u.get("type") in ("SDS", "标签"):
            issues.append({
                "level": "中",
                "item": f"{u.get('type')} 无中文版本",
                "detail": f"{u.get('file')} 为 {'韩文/英文' if u['lang'] == 'ko' else u['lang']} 版本",
                "fix": "进口危化品须随货提供中文化学品安全技术说明书与中文危险公示标签",
            })
    return issues


# --------------------------------------------------------------------------
# 文本卫生：禁用表述检查
# --------------------------------------------------------------------------
BANNED_PHRASES = [
    (r"完全可以放心", "绝对化承诺"),
    (r"百分百合法", "绝对化承诺"),
    (r"绝对不会被查", "绝对化承诺"),
    (r"保证通关", "绝对化承诺"),
    (r"不需要任何手续", "误导性简化"),
    (r"属于普通货物", r"未经危险货物判定不得断言"),
    (r"无需报关", "常识性错误"),
]


def lint_text(text: str) -> List[Tuple[str, str]]:
    hits = []
    for pat, why in BANNED_PHRASES:
        for m in re.finditer(pat, text):
            hits.append((text[max(0, m.start() - 20): m.end() + 20], why))
    return hits


# --------------------------------------------------------------------------
# 数字格式化
# --------------------------------------------------------------------------
def money(v: Any, cur: str = "CNY") -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    sym = {"CNY": "¥", "USD": "$", "EUR": "€", "KRW": "₩"}.get(cur, "")
    return f"{sym}{f:,.2f}"


def pct(v: Any, nd: int = 1) -> str:
    try:
        return f"{float(v):.{nd}f}%"
    except (TypeError, ValueError):
        return "—"


def slugify(s: str, maxlen: int = 60) -> str:
    """给中文文件名用：只去掉 Windows 非法字符。"""
    t = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s).strip(" .")
    return t[:maxlen] or "untitled"


def safe_json_default(o: Any) -> Any:
    if isinstance(o, (_dt.date, _dt.datetime)):
        return o.isoformat()
    raise TypeError(f"not serializable: {type(o)}")
