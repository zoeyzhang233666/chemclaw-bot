# -*- coding: utf-8 -*-
"""
qclib.py — 化学品供应商资质证照核验：零依赖公共库（Python 3.9+）

职责：
  1) 统一社会信用代码 / 营业执照号 / 证照编号的机械校验（校验码、格式）
  2) 证照有效期判定（相对 as_of，全文唯一时间基准）
  3) 监管分类核验结果（清晰表述 / 不清晰 / 待核验）与证照覆盖比对
  4) 四态分类（已核验 / 信息不一致 / 待核验 / 无公开信息 / 已过期）
  5) HTML / Excel 共用的格式化助手

本文件不含任何具体化学品知识——所有化学品属性都来自 data.json 中的
product.findings / classification_checklist，以保证 Skill 不限品。
"""

import datetime
import re

# ---------------------------------------------------------------- 常量

# GB 32100-2015 校核码字符集与权重
_USCC_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"
_USCC_WEIGHTS = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]

# 证照核验状态（四态 + 过期），顺序即展示优先级
CERT_STATES = [
    ("verified", "已核验", "#1f7a4d"),
    ("mismatch", "信息不一致", "#b3402a"),
    ("pending", "待核验", "#a9761b"),
    ("no_public", "无公开信息", "#6b7280"),
    ("expired", "已过期", "#8b1e1e"),
]

# 监管分类判定三态：不得对未确认事项下"不属于"的结论
CLASS_VERDICTS = [
    ("confirmed", "已确认", "#1f7a4d"),
    ("not_confirmed", "未确认（不等于不属于）", "#b3402a"),
    ("pending", "待核验", "#a9761b"),
]

# 覆盖比对结果
COVER_VERDICTS = [
    ("cover", "覆盖", "#1f7a4d"),
    ("partial", "部分覆盖", "#a9761b"),
    ("not_cover", "未覆盖", "#b3402a"),
    ("unknown", "无法判断", "#6b7280"),
]

# 优先级
PRIORITIES = ["P0", "P1", "P2"]


# ---------------------------------------------------------------- 信用代码校验

def _uscc_check_char(code17):
    total = 0
    for i in range(17):
        idx = _USCC_CHARS.find(code17[i].upper())
        if idx < 0:
            return None
        total += idx * _USCC_WEIGHTS[i]
    return _USCC_CHARS[(31 - total % 31) % 31]


def check_uscc(code):
    """
    统一社会信用代码（GB 32100-2015）：18 位。
    返回 dict(valid=bool|None, level='ok|warn|error', reason=str, code=规范化值)
    None 表示未提供代码，不做任何推断。
    """
    if code is None:
        return {"valid": None, "level": "warn", "reason": "未提供统一社会信用代码", "code": ""}
    raw = str(code).strip().replace(" ", "")
    if raw == "":
        return {"valid": None, "level": "warn", "reason": "未提供统一社会信用代码", "code": ""}
    up = raw.upper()
    if not re.fullmatch(r"[0-9A-HJ-NPQRTUWXY]{18}", up):
        return {"valid": False, "level": "error",
                "reason": "格式不符：应为 18 位数字/大写字母（不含 I O S V Z）", "code": raw}
    expect = _uscc_check_char(up[:17])
    if expect != up[17]:
        return {"valid": False, "level": "error",
                "reason": "校验码不符（第18位应为 %s，实际为 %s）——必须视为核对失败" % (expect, up[17]),
                "code": raw}
    return {"valid": True, "level": "ok", "reason": "第18位校验码通过", "code": raw}


def check_biz_lic_no(code):
    """15 位旧营业执照注册号（工商注册号）：仅做格式检查，旧号无校验码。"""
    if not code:
        return {"valid": None, "level": "warn", "reason": "未提供", "code": ""}
    raw = str(code).strip()
    if re.fullmatch(r"\d{15}", raw):
        return {"valid": True, "level": "ok", "reason": "15 位工商注册号格式正确（旧号无校验码）", "code": raw}
    return {"valid": False, "level": "error", "reason": "不符合 15 位工商注册号格式", "code": raw}


def check_cert_no(no, must_prefixes=None):
    """
    证照编号的机械检查：非空、长度合理、前缀是否命中该证种常见前缀。
    只提示"形似/不形似"，最终仍以主管部门公示与原件为准。
    """
    if not no:
        return {"valid": None, "level": "warn", "reason": "未取得编号（待核验）", "code": ""}
    raw = str(no).strip()
    if len(raw) < 6:
        return {"valid": False, "level": "error", "reason": "编号过短，明显异常", "code": raw}
    if must_prefixes:
        if any(raw.upper().startswith(p.upper()) for p in must_prefixes):
            return {"valid": True, "level": "ok",
                    "reason": "前缀命中常见格式（%s）" % "/".join(must_prefixes), "code": raw}
        return {"valid": None, "level": "warn",
                "reason": "前缀未命中常见格式（%s），不必然是假证，需与公示核对" % "/".join(must_prefixes),
                "code": raw}
    return {"valid": None, "level": "warn", "reason": "仅做非空与长度检查", "code": raw}


# ---------------------------------------------------------------- 日期

def parse_date(v):
    """支持 2026-01-31 / 2026.01.31 / 2026/1/31 / 2026.01 / 2026-01 / 2026。返回 date 或 None。"""
    if not v:
        return None
    if isinstance(v, datetime.date):
        return v
    s = str(v).strip().replace(".", "-").replace("/", "-")
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), 1)
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return datetime.date(int(m.group(1)), 1, 1)
    return None


def fmt_date(v):
    d = parse_date(v)
    return d.isoformat() if d else ("" if not v else str(v))


def validity(end, as_of, warn_days=180):
    """
    相对 as_of 判定有效期。返回 dict(status, days, label, tone)
      status: valid | expiring | expired | unknown | perpetual
    """
    aso = parse_date(as_of)
    if not end:
        return {"status": "unknown", "days": None, "label": "有效期未取得", "tone": "muted"}
    if str(end).strip() in ("长期", "永久", "无期限", "长期（无固定期限）"):
        return {"status": "perpetual", "days": None, "label": "长期有效", "tone": "ok"}
    e = parse_date(end)
    if not e or not aso:
        return {"status": "unknown", "days": None, "label": "有效期无法解析", "tone": "muted"}
    days = (e - aso).days
    if days < 0:
        return {"status": "expired", "days": days,
                "label": "已过期 %d 天" % (-days) if days > -100000 else "已过期", "tone": "bad"}
    if days <= warn_days:
        return {"status": "expiring", "days": days,
                "label": "%d 天后到期" % days, "tone": "warn"}
    return {"status": "valid", "days": days, "label": "有效（余 %d 天）" % days, "tone": "ok"}


# ---------------------------------------------------------------- 状态与判定

def state_meta(key):
    for k, label, color in CERT_STATES:
        if k == key:
            return {"key": k, "label": label, "color": color}
    return {"key": key or "pending", "label": key or "待核验", "color": "#a9761b"}


def class_meta(key):
    for k, label, color in CLASS_VERDICTS:
        if k == key:
            return {"key": k, "label": label, "color": color}
    return {"key": key, "label": key, "color": "#a9761b"}


def cover_meta(key):
    for k, label, color in COVER_VERDICTS:
        if k == key:
            return {"key": k, "label": label, "color": color}
    return {"key": key, "label": key, "color": "#6b7280"}


def cert_effective_state(cert, as_of):
    """
    合并"证照状态"与"有效期"：status=verified 但已过期 -> expired；
    status=pending 且临近/已过期 -> 保持 pending 但由 validity 单独提示。
    """
    v = validity(cert.get("valid_to"), as_of)
    st = cert.get("status") or "pending"
    if v["status"] == "expired" and st in ("verified", "mismatch"):
        return "expired"
    return st


def summarize(certs, as_of):
    """统计四态 + 即将到期数量。"""
    out = {k: 0 for k, _, _ in CERT_STATES}
    expiring = 0
    for c in certs:
        s = cert_effective_state(c, as_of)
        out[s] = out.get(s, 0) + 1
        v = validity(c.get("valid_to"), as_of)
        if v["status"] == "expiring":
            expiring += 1
    out["expiring"] = expiring
    return out


def erp_check(data):
    """
    采购方主体一致性：拿数据里出现的所有统一社会信用代码相互比对，
    发现"同一主体名不同代码"或"同一代码不同主体名"时列出冲突。
    """
    seen = {}
    for obj in _iter_named_entities(data):
        name = (obj.get("name") or "").strip()
        code = (obj.get("uscc") or "").strip().upper()
        if not name and not code:
            continue
        seen.setdefault((name, code), 0)
        seen[(name, code)] += 1
    names = {}
    codes = {}
    for (name, code), n in seen.items():
        if name:
            names.setdefault(name, set()).add(code)
        if code:
            codes.setdefault(code, set()).add(name)
    conflicts = []
    for name, cs in names.items():
        if len([c for c in cs if c]) > 1:
            conflicts.append({"type": "同名不同代码", "name": name, "codes": sorted(cs)})
    for code, ns in codes.items():
        if len([x for x in ns if x]) > 1:
            conflicts.append({"type": "同代码不同名称", "code": code, "names": sorted(ns)})
    return conflicts


def _iter_named_entities(data):
    s = data.get("subject") or {}
    if s.get("name") or s.get("uscc"):
        yield {"name": s.get("name"), "uscc": s.get("uscc")}
    for a in (data.get("subject_aliases") or []):
        yield a
    for c in (data.get("certs") or []):
        if c.get("issuer_subject"):
            yield {"name": c.get("issuer_subject"), "uscc": ""}
    erp = data.get("erp") or {}
    if erp.get("name") or erp.get("uscc"):
        yield {"name": erp.get("name"), "uscc": erp.get("uscc")}


def pending_derivation(data):
    """
    派生"必须索取的证照"：凡 certs 中应办=required 且 状态≠verified/expired 的，
    自动进入索证清单；若 data 中 request_list 已含同名条目则复用编号。
    返回 (auto_items, notices)
    """
    notices = []
    request = data.get("request_list") or []
    existing = {}
    for it in request:
        existing[(it.get("cert") or "").strip()] = it.get("code")
    auto = []
    n = 0
    for i, c in enumerate(data.get("certs") or []):
        if c.get("need") != "required":
            continue
        st = cert_effective_state(c, data.get("as_of"))
        if st in ("verified", "expired"):
            continue
        n += 1
        code = existing.get((c.get("name") or "").strip()) or "A%02d" % n
        auto.append({
            "code": code,
            "cert": c.get("name"),
            "issuer": c.get("issuer"),
            "priority": c.get("priority") or "P1",
            "reason": "证照表状态为「%s」：%s" % (
                state_meta(st)["label"],
                (c.get("note") or "需取得原件/书面确认后核定")),
            "ask": c.get("ask") or "请提供加盖公章的复印件及编号，供与主管部门公示核对",
            "auto": True,
        })
    notices.append("本清单由证照表与监管要求自动派生 %d 项（标注 AUTO），请与人工补充项合并去重。" % len(auto))
    return auto, notices


# ---------------------------------------------------------------- 文本

def clip(s, n):
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def pct(a, b):
    if not b:
        return "—"
    return "%d/%d = %.0f%%" % (a, b, (a * 100.0) / b)


def esc(s):
    s = "" if s is None else str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def nl2p(s):
    """把 \\n\\n 分段转为 <p>，保留单内联标签。"""
    s = "" if s is None else str(s)
    parts = [p.strip() for p in s.split("\n\n") if p.strip()]
    return "".join("<p>%s</p>" % p.replace("\n", "<br>") for p in parts)
