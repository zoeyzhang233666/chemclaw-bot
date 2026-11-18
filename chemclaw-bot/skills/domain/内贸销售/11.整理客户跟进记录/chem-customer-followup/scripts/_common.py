# -*- coding: utf-8 -*-
"""
_common.py — 客户跟进卡生成器共享库

产品无关：不含任何具体化工品硬编码文案。
依赖：Python 3.9+，标准库；Excel 输出额外需要 openpyxl。
"""
import math
import re
import datetime as _dt

# ───────────────────────── 配色 ─────────────────────────
FONT = "微软雅黑"

INK = "0D3B4F"
INK2 = "14617D"
GOLD = "B7822B"
GOLD_L = "FDF6E8"
RISK = "C02626"
OK = "0F7A52"
WARN = "B45309"
LINE = "D8E0E8"
ZEBRA = "F7F9FB"
BG = "F4F6F9"
AI_FG = "5B6B7C"

# 分类 → (前景色, 浅底色)
CATEGORY_COLORS = {
    "客户需求": ("1D4ED8", "EEF3FF"),
    "客户异议": ("C02626", "FDEEEE"),
    "我方承诺": ("0F7A52", "E9F8F1"),
    "待确认": ("6D28D9", "F3EEFF"),
    "客户动作": ("0E7490", "E7F6FA"),
    "我方动作": ("A85A08", "FDF1E3"),
    "系统提醒": ("475569", "EEF1F5"),
}
FALLBACK_CATS = [
    ("8B5CF6", "F5F3FF"),
    ("0891B2", "ECFEFF"),
    ("BE123C", "FFF1F2"),
    ("65A30D", "F7FEE7"),
]

TONE = {
    "risk": (RISK, "FDEEEE"),
    "warn": (WARN, "FDF1E3"),
    "ok": (OK, "E9F8F1"),
    "info": (INK2, "E8F2F6"),
    "neutral": ("475569", "EEF1F5"),
}


def cat_color(name):
    name = (name or "").strip()
    if name in CATEGORY_COLORS:
        return CATEGORY_COLORS[name]
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFF
    return FALLBACK_CATS[h % len(FALLBACK_CATS)]


def tone_color(tone):
    return TONE.get((tone or "neutral").strip(), TONE["neutral"])


# ───────────────────────── 文本度量 ─────────────────────────
def cjk_len(t):
    """按半角宽度估算字符串长度（中文算 2）。"""
    return sum(2 if ord(c) > 127 else 1 for c in str(t))


def est_h(texts, widths, base=15.6, minh=20, pad=5):
    lines = 1
    for t, w in zip(texts, widths):
        if t is None:
            continue
        per = max(4, int(w))
        lines = max(lines, math.ceil(cjk_len(t) / per))
    return max(minh, lines * base + pad)


# ───────────────────────── 日期与推导 ─────────────────────────
_DATE_RE = re.compile(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})")
_SHORT_RE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})$")


def parse_as_of(text):
    """解析 as_of 日期；失败返回今天。"""
    if text:
        m = _DATE_RE.search(str(text))
        if m:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return _dt.date.today()


def parse_record_date(date_text, as_of):
    """
    把 '09-18' / '2026-09-18' / '9-18' 解析为 date。
    只有月日时按 as_of 推断年份：若落在 as_of 之后超过 7 天，视为上一年。
    """
    if not date_text:
        return None
    s = str(date_text).strip()
    m = _DATE_RE.search(s)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = _SHORT_RE.match(s)
    if m:
        mo, dy = int(m.group(1)), int(m.group(2))
        for year in (as_of.year, as_of.year - 1):
            try:
                d = _dt.date(year, mo, dy)
            except ValueError:
                continue
            if d <= as_of + _dt.timedelta(days=7):
                return d
        return None
    return None


CUSTOMER_SIDE = {"客户", "客户方", "双方", "客户+我方"}


def customer_records(timeline):
    """客户侧实质记录（用于计算停滞天数）。"""
    out = []
    for rec in timeline or []:
        actor = str(rec.get("actor") or "").strip()
        cat = str(rec.get("category") or "").strip()
        if cat == "系统提醒":
            continue
        if actor in CUSTOMER_SIDE or cat in ("客户需求", "客户异议"):
            out.append(rec)
    return out


def last_customer_date(timeline, as_of):
    best = None
    for rec in customer_records(timeline):
        d = parse_record_date(rec.get("date"), as_of)
        if d and (best is None or d > best[0]):
            best = (d, rec)
    return best


def compute_stall_days(timeline, as_of_date):
    """停滞天数 = as_of − 最后一次客户实质回复日期。"""
    got = last_customer_date(timeline, as_of_date)
    if not got:
        return None, None
    d, rec = got
    return max(0, (as_of_date - d).days), rec


def days_left(due_text, as_of_date):
    d = parse_record_date(due_text, as_of_date)
    if not d:
        return None
    return (d - as_of_date).days


def promise_state(p, as_of_date):
    """
    返回 (状态文案, tone)。已有显式状态优先，但会补上逾期天数。
    """
    raw = str(p.get("status") or "").strip()
    due = p.get("due") or ""
    done = "已兑现" in raw or "已完成" in raw
    if done:
        return raw or "已兑现", "ok"
    d = parse_record_date(due, as_of_date)
    if d is None:
        return raw or "未到期", "info"
    delta = (as_of_date - d).days
    if delta > 0:
        if "逾期" in raw:
            has_num = any(ch.isdigit() for ch in raw)
            return (raw if has_num else f"{raw} {delta} 天"), "risk"
        return f"逾期 {delta} 天", "risk"
    if delta == 0:
        return "今日到期", "warn"
    if "草稿未发" in raw or "未发" in raw:
        return f"{raw}（还有 {-delta} 天）", "warn"
    return f"未到期 · 还有 {-delta} 天", "info"


# ───────────────────────── 数据校验 ─────────────────────────
STAGE_NAMES = ["初次接触", "需求确认", "送样", "报价谈判", "合同", "停滞"]
CATEGORY_NAMES = ["客户需求", "客户异议", "我方承诺", "待确认", "客户动作", "我方动作", "系统提醒"]


def validate(data, as_of_date=None):
    """
    返回 (errors, warnings)。errors 阻断生成，warnings 打印但继续。
    这是把「整理纪律」写成代码的部分。
    """
    errors, warnings = [], []
    meta = data.get("meta") or {}
    as_of = as_of_date or parse_as_of(meta.get("as_of_date"))
    timeline = data.get("timeline") or []

    if not timeline:
        errors.append("timeline 为空：至少需要一条记录")
    if not data.get("headline"):
        warnings.append("headline 为空：HTML 顶部「一句话结论」会缺失")

    # 分类合法性
    for i, rec in enumerate(timeline, 1):
        cat = str(rec.get("category") or "").strip()
        if cat not in CATEGORY_NAMES:
            errors.append(f"timeline#{i} 分类「{cat}」不在允许集合 {CATEGORY_NAMES} 内")

    # 出处完整性：四类事实类清单必须带 source
    for key, label in (("requirements", "客户需求"), ("objections", "客户异议"),
                       ("promises", "我方承诺"), ("pending", "待确认")):
        for i, item in enumerate(data.get(key) or [], 1):
            if not str(item.get("source") or "").strip() and key != "pending":
                warnings.append(f"{key}#{i} 缺少 source（出处），交付前建议补齐")

    # 客户需求不得凭空出现：置信度字段必须存在
    for i, item in enumerate(data.get("requirements") or [], 1):
        if not item.get("confidence"):
            warnings.append(f"requirements#{i} 缺少 confidence（高/中/低）")

    # 阶段合法性
    stage = data.get("stage") or {}
    cur = stage.get("current")
    if cur and cur not in STAGE_NAMES:
        errors.append(f"stage.current「{cur}」不在 {STAGE_NAMES} 内")

    # 停滞天数自洽
    computed, rec = compute_stall_days(timeline, as_of)
    declared = (stage.get("stall") or {}).get("days")
    if computed is not None and declared is not None and int(declared) != computed:
        warnings.append(
            f"停滞天数不一致：声明 {declared} 天，按时间线核算 {computed} 天"
            f"（最后客户回复 {rec.get('date')}）")

    # 承诺逾期自洽
    for i, p in enumerate(data.get("promises") or [], 1):
        st, tone = promise_state(p, as_of)
        if tone == "risk" and "逾期" not in str(p.get("status") or ""):
            warnings.append(
                f"promises#{i} 已过期（due={p.get('due')}）但 status 未标逾期，"
                f"生成时按「{st}」处理")

    # AI 摘要必须显式存在且标注
    ai = data.get("ai_summary") or {}
    if not ai.get("paragraphs"):
        warnings.append("ai_summary 为空：AI 推断区会缺失（不得用事实清单冒充）")

    return errors, warnings
