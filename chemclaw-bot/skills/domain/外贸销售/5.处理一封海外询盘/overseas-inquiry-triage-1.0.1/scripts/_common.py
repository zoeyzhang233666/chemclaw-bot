# -*- coding: utf-8 -*-
"""overseas-inquiry-triage · 共用常量与工具

设计原则：
- 字段结构冻结在这里，HTML / Excel / MD / 自检四处都从这里取，避免漂移；
- 本模块不含任何价格、不含任何"真实性/成交可能性"评分逻辑（技能硬约束）；
- 只做搬运、渲染、校验，不做推断。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import sys

VERSION = "1.0.0"
SKILL_NAME = "overseas-inquiry-triage"

# ---------------------------------------------------------------- 分类与字段
# cat: 分类编号（A buyer / B product / C spec / D qty / E delivery / F commercial / G docs / H context）
# bucket: A 报价前必确认 / B 可带假设 / C 我方内部先定
CATEGORIES = [
    ("A", "买方与联系人", "Buyer & contact"),
    ("B", "产品与化学身份", "Product & chemistry"),
    ("C", "规格与质量", "Specification"),
    ("D", "数量与节奏", "Quantity & schedule"),
    ("E", "交付与贸易术语", "Delivery & Incoterms"),
    ("F", "商务条件", "Commercial terms"),
    ("G", "文件与合规", "Documents & compliance"),
    ("H", "买方侧背景", "Buyer-side context"),
]

# key, label_cn, label_en, cat, bucket, affects_quote, assume_default
FIELD_SPEC = [
    # --- A 买方与联系人
    ("buyer_name", "客户公司全称", "Buyer company (full legal name)", "A", "A", True, ""),
    ("buyer_country", "国家/地区", "Country / region", "A", "A", True, ""),
    ("buyer_site", "地址 / 厂区", "Address / plant site", "A", "A", False, ""),
    ("contact_name", "联系人", "Contact person", "A", "A", True, ""),
    ("contact_title", "职位", "Title", "A", "A", False, ""),
    ("contact_email", "邮箱", "E-mail", "A", "A", True, ""),
    ("contact_phone", "电话 / 手机", "Phone / mobile", "A", "A", False, ""),
    ("buyer_type", "公司类型", "Buyer type", "A", "B", False, "未明确（不推断）"),
    # --- B 产品与化学身份
    ("product_raw", "客户原话品名", "Product as written by buyer", "B", "A", True, ""),
    ("product_std", "标准化品名", "Standardized product name", "B", "A", True, ""),
    ("product_cn", "中文品名", "Chinese name", "B", "A", True, ""),
    ("cas", "CAS 号", "CAS No.", "B", "A", True, ""),
    ("ec", "EC / EINECS 号", "EC No.", "B", "B", False, ""),
    ("formula", "化学式", "Formula", "B", "B", False, ""),
    ("synonyms", "常见别称", "Synonyms", "B", "B", False, ""),
    ("appearance_form", "形态 / 粒度形态", "Form (dense / light / flake)", "B", "A", True, ""),
    # --- C 规格
    ("spec_purity", "主含量", "Main content / purity", "C", "A", True, ""),
    ("spec_impurities", "关键杂质", "Key impurities", "C", "A", True, ""),
    ("spec_particle", "粒度 / 筛分", "Particle size / sieve", "C", "A", True, ""),
    ("spec_bulk", "堆密度", "Bulk density", "C", "B", False, ""),
    ("spec_moisture", "水分 / 烧失", "Moisture / LOI", "C", "B", False, ""),
    ("spec_std", "标准 / 规范", "Standard (GB / ASTM / ISO / buyer spec)", "C", "B", False, ""),
    ("grade", "等级 / 牌号", "Grade", "C", "A", True, ""),
    ("tds_ref", "TDS / 规格书版本", "TDS / spec sheet reference", "C", "B", False, ""),
    # --- D 数量
    ("qty_trial", "试单量 / 首批量", "First / trial shipment quantity", "D", "A", True, ""),
    ("qty_annual", "年量", "Annual volume", "D", "A", True, ""),
    ("qty_monthly", "月量", "Monthly volume", "D", "B", True, ""),
    ("qty_per_shipment", "单批量", "Quantity per shipment", "D", "B", True, ""),
    ("qty_schedule", "交付节奏", "Delivery schedule", "D", "B", True, ""),
    ("qty_unit", "计量单位", "Unit of measure", "D", "A", True, ""),
    # --- E 交付
    ("port_dest", "目的港 / 目的站", "Port of discharge / destination", "E", "A", True, ""),
    ("incoterm", "贸易术语", "Incoterms 2020 term", "E", "A", True, ""),
    ("incoterm_place", "术语地点", "Incoterms place", "E", "A", True, ""),
    ("port_load", "装运港", "Port of loading", "E", "C", True, "我方确定"),
    ("transport_mode", "运输方式", "Mode of transport", "E", "B", True, "海运整柜 FCL"),
    ("pack_std", "包装", "Packing type", "E", "B", True, "按客户确认的包装，待定"),
    ("pack_marking", "唛头 / 标签语言", "Marking / label language", "E", "B", False, "英文唛头"),
    ("pack_pallet", "托盘 / 堆码", "Palletization", "E", "B", False, "按客户确认"),
    ("dg_info", "危险品信息（UN/PG）", "DG information (UN No. / PG)", "E", "B", False, ""),
    # --- F 商务
    ("currency", "币种", "Currency", "F", "A", True, ""),
    ("price_basis", "价格基础", "Price basis", "F", "A", True, ""),
    ("payment", "付款方式", "Payment terms", "F", "A", True, ""),
    ("lc_terms", "信用证条件", "L/C details", "F", "A", True, ""),
    ("delivery_time", "交期 / 装运期", "Delivery / shipment time", "F", "B", True, "由我方排产确认"),
    ("quote_validity", "报价有效期", "Quotation validity", "F", "B", True, "由我方确定，不默认天数"),
    ("sample_req", "样品要求", "Sample request", "F", "B", True, "我方样品政策待定"),
    ("inspection_cost", "检测/检验费承担", "Inspection cost bearer", "F", "B", True, ""),
    ("commission", "佣金 / 代理", "Commission / agent", "F", "B", True, ""),
    # --- G 单证
    ("doc_coa", "COA 质量分析单", "COA (Certificate of Analysis)", "G", "A", False, ""),
    ("doc_sds", "SDS / MSDS", "SDS (MSDS)", "G", "A", False, ""),
    ("doc_tds", "TDS 技术数据表", "TDS", "G", "A", False, ""),
    ("doc_coo", "原产地证 CO", "Certificate of Origin", "G", "B", False, ""),
    ("doc_form_e", "FORM E 等优惠原产地证", "Form E / FTA preferential CO", "G", "B", False, ""),
    ("doc_inspection", "第三方检验", "Third-party inspection (SGS/BV)", "G", "B", False, ""),
    ("doc_dg", "危险品单证", "DG declaration / certificate", "G", "B", False, ""),
    ("doc_audit", "工厂审计 / 认证", "Factory audit / certificates", "G", "B", False, ""),
    ("doc_lang", "单证语言", "Document language", "G", "B", False, ""),
    ("doc_other", "其他单证", "Other documents", "G", "B", False, ""),
    # --- H 背景
    ("application", "应用 / 工艺", "Application / process", "H", "B", False, ""),
    ("current_supplier", "现有供应来源", "Current supplier", "H", "B", False, ""),
    ("annual_scale", "采购规模背景", "Purchase scale (buyer statement)", "H", "B", False, ""),
    ("sample_stage", "询价阶段", "Inquiry stage (first / repeat)", "H", "B", False, ""),
    ("urgency", "时间压力", "Time pressure", "H", "B", False, ""),
    ("price_sensitivity", "价格敏感线索", "Price-sensitivity cue", "H", "B", False, ""),
]

FIELDS = {}
_ORDER = []
for _k, _lcn, _len, _cat, _b, _aq, _as in FIELD_SPEC:
    FIELDS[_k] = {
        "key": _k, "label_cn": _lcn, "label_en": _len,
        "cat": _cat, "bucket": _b, "affects_quote": _aq, "assume": _as,
    }
    _ORDER.append(_k)

BUCKET_LABEL = {
    "A": "A 类 · 报价前必须先确认",
    "B": "B 类 · 可带我方假设先准备",
    "C": "C 类 · 我方内部先定",
}

STATUS_LABEL = {
    "stated": "已明确",
    "missing": "缺失",
    "ambiguous": "歧义 / 待确认",
    "assumed": "我方假设",
    "internal": "我方待定",
}

LANG_LABEL = {
    "en": "English", "zh": "中文", "id": "Bahasa Indonesia", "vi": "Tiếng Việt",
    "es": "Español", "pt": "Português", "ms": "Bahasa Melayu", "ar": "العربية", "ja": "日本語",
}

# C 类业务用语（出口报价口径）——只给选项，不预选
GATE_CHOICES = {
    "our_entity": ["（请填写我方出口主体全称）"],
    "price_currency_basis": ["USD / MT（出口惯例）", "EUR / MT", "RMB / MT"],
    "port_load": ["（按我方工厂最近的装运港填写）"],
    "tax_basis": ["不含增值税（出口离境）", "含增值税（客户要求内贸口径，需审批）"],
    "incoterm_confirm": ["可按客户术语承接（待内部确认）", "需调整术语（待内部确认）"],
}

# 真实外贸询盘里"看起来给了其实没给"的句子（用于歧义提示，不自动改字段）
AMBIGUITY_TRAPS = [
    {"pattern": r"\b(please\s+)?(advise|quote|give)\s+(us\s+)?your\s+best\s+price\b",
     "label_cn": "只问了最低价", "why": "这是问价，不是给了任何商务条件；也不代表客户接受任何条款"},
    {"pattern": r"\bprice\s+should\s+be\s+(competitive|attractive|reasonable)\b",
     "label_cn": "\"价格要有竞争力\"", "why": "只说明价格敏感，不含任何数字或标准；不得据此报低价"},
    {"pattern": r"\bstandard\s+(packing|packaging)\b",
     "label_cn": "\"标准包装\"", "why": "没给袋型/袋重，需我方建议并由客户确认"},
    {"pattern": r"\b(as\s+usual|as\s+before|same\s+as\s+last\s+time)\b",
     "label_cn": "\"照旧/同上次\"", "why": "必须回查上一单的单证与条款，不能按常识填"},
    {"pattern": r"\b(a\.?s\.?a\.?p\.?)\b|as\s+soon\s+as\s+possible",
     "label_cn": "\"ASAP\"", "why": "ASAP 不是交期；交期由我方排产确认"},
    {"pattern": r"payment\s*[:\-]?\s*l/?c\b|letter\s+of\s+credit",
     "label_cn": "只写了 L/C", "why": "缺 L/C 类型、有效期、开证行、是否保兑"},
    {"pattern": r"\bwe\s+are\s+a\s+(big|large)\s+(buyer|customer)\b",
     "label_cn": "\"我们是大买家\"", "why": "没有年量数字，不能据此给阶梯价"},
    {"pattern": r"\bdocuments?\s+(as\s+usual|as\s+required)\b",
     "label_cn": "\"单证照常规\"", "why": "必须逐项列名单证，常规不等于客户要求"},
]

# 回复承诺扫描（selfcheck / polish 共用）
COMMITMENT_PATTERNS = [
    # 保证性词
    (r"\bwe\s+(guarantee|warrant|assure\s+you)\b", "保证性承诺", "删除或改为条件句"),
    (r"\bguaranteed\b", "保证性承诺", "删除或改为条件句"),
    # 具体能力/即期
    (r"\b(we\s+(can|will|are\s+able\s+to)\s+)?(supply|deliver|ship|provide|offer|arrange)\b[^.\n]{0,60}\b(immediately|right\s+away|at\s+once|today|tomorrow)\b",
     "即期能力承诺", "改为占位符 ‹STOCK_AVAILABILITY› / ‹SHIPMENT_TIME›"),
    # 具体天数 / 周数
    (r"\bwithin\s+\d+\s*(working\s+)?(days?|weeks?)\b", "具体天数承诺", "改为 ‹SHIPMENT_TIME› 等占位符"),
    (r"\bin\s+\d+\s*(working\s+)?(days?|weeks?)\b", "具体天数承诺", "改为占位符"),
    # 具体日期
    (r"\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[,.]?\s+\d{4}\b", "具体日期承诺", "改为占位符"),
    # 单证承诺
    (r"\bform\s+e\b", "提及 FORM E", "确认能否出具后才写；否则改为待确认"),
    (r"\b(sgs|bv|bureau\s+veritas|intertek|ciq)\b", "提及第三方检验", "确认机构/节点/费用后才写"),
    (r"\bcoa[^.\n]{0,30}\b(attached|enclosed)\b", "承诺已附 COA", "附件未附则删除"),
    # 付款与账期
    (r"\bwe\s+(can\s+)?accept\s+(l/?c|d/?p|d/?a|o/?a|payment|t/?t)\b", "主动接受付款条件", "改为内部确认后答复"),
    (r"\b(credit|payment)\s+terms?\s+of\s+\d+\s*days\b", "账期承诺", "改为 ‹PAYMENT_TERMS›"),
    (r"\b\d+\s*days\s+(credit|after\s+(b/?l|arrival))\b", "账期承诺", "改为 ‹PAYMENT_TERMS›"),
    # 商务让利
    (r"\b(free|no\s+charge|complimentary)\s+samples?\b", "免费样品承诺", "改为 ‹SAMPLING_POLICY›"),
    (r"\b(free\s+)?(shipping|freight)\s+(is\s+)?(included|free|on\s+us)\b", "运费承担承诺", "改为占位符 / 内部确认"),
    (r"\b(best|lowest)\s+price\s+(we\s+can|guarantee|in\s+the\s+market)\b", "价格承诺", "删除"),
    (r"\bwe\s+will\s+hold\s+the\s+price\b", "锁价承诺", "改为占位符 ‹QUOTE_VALIDITY›"),
    (r"\bdiscount\s+of\s+\d+(\.\d+)?\s*%\b", "折扣承诺", "改为占位符"),
]

# 价格痕迹：回复正文里一旦命中，说明有人把价格写死了
PRICE_PATTERNS = [
    r"usd\s?\d",
    r"us\$\s?\d",
    r"\$\s?\d",
    r"eur\s?\d",
    r"rp\.?\s?\d",
    r"cny\s?\d",
    r"\brmb\s?\d",
    r"\d+(\.\d+)?\s*(usd|cny|eur|idr)\b",
    r"per\s+mt\s*[=:]\s*\d",
]

# ---------------------------------------------------------------- 工具函数
def now_iso() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_iso() -> str:
    return _dt.date.today().isoformat()


def read_text(path: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as f:
        return f.read().decode("utf-8", "replace")


def load_json(path: str):
    return json.loads(read_text(path))


def load_json_stable(path: str):
    """按固定键序重建 fields.json（工作台编辑后 key 顺序会乱，这里拉回来）。"""
    doc = load_json(path)
    if isinstance(doc.get("fields"), dict):
        doc["fields"] = normalize_fields(doc["fields"])
    return doc


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def short(text: str, n: int = 90) -> str:
    t = norm_ws(text)
    return t if len(t) <= n else t[: n - 1] + "…"


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def eprint(*a):
    print(*a, file=sys.stderr)


def esc_html(s) -> str:
    s = "" if s is None else str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def js_safe(obj) -> str:
    """把对象安全地嵌进 <script type="application/json">。

    先转义 "</" 再 JSON 化：反过来做会把合法的 "\\/" 变成 "\\\\/"（JSON 非法），
    并让 $1 之类的替换模板被二次转义。
    """
    if isinstance(obj, str):
        obj = obj.replace("</", "<\\/").replace("\u2028", "\u2028").replace("\u2029", "\u2029")
        return json.dumps(obj, ensure_ascii=False, indent=2)
    walk = lambda x: ({k: walk(v) for k, v in x.items()} if isinstance(x, dict)
                      else [walk(v) for v in x] if isinstance(x, list) else
                      (x.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029") if isinstance(x, str) else x))
    return json.dumps(walk(obj), ensure_ascii=False)


def field_meta(key: str) -> dict:
    return FIELDS.get(key) or {"key": key, "label_cn": key, "label_en": key,
                               "cat": "?", "bucket": "B", "affects_quote": False, "assume": ""}


def cat_label(cat: str, lang: str = "cn") -> str:
    for c, cn, en in CATEGORIES:
        if c == cat:
            return cn if lang == "cn" else en
    return cat


def empty_field(key: str) -> dict:
    m = field_meta(key)
    return {
        "key": key,
        "label_cn": m["label_cn"],
        "label_en": m["label_en"],
        "cat": m["cat"],
        "bucket": m["bucket"],
        "affects_quote": bool(m["affects_quote"]),
        "value": "",
        "raw": "",
        "unit": "",
        "status": "missing",
        "confidence": "",
        "lang": "",
        "source_id": "",
        "quote": "",
        "locator": "",
        "note": "",
        "assume": m["assume"] if m["bucket"] == "B" else "",
        "vs": "",
    }


def normalize_fields(raw_fields) -> dict:
    """保证每个字段都存在、键序固定。"""
    out = {}
    src = raw_fields or {}
    if isinstance(src, list):
        src = {f.get("key"): f for f in src if isinstance(f, dict) and f.get("key")}
    for k in _ORDER:
        base = empty_field(k)
        if k in src and isinstance(src[k], dict):
            base.update({kk: vv for kk, vv in src[k].items() if vv is not None})
            base["key"] = k
        if base.get("status") not in STATUS_LABEL:
            base["status"] = "stated" if base.get("value") else "missing"
        out[k] = base
    return out


def field_counts(fields: dict) -> dict:
    n = {"stated": 0, "missing": 0, "ambiguous": 0, "assumed": 0, "internal": 0}
    for f in fields.values():
        n[f.get("status", "missing")] = n.get(f.get("status", "missing"), 0) + 1
    n["blocking_missing"] = sum(
        1 for f in fields.values()
        if f["bucket"] == "A" and f["affects_quote"] and f["status"] in ("missing", "ambiguous")
    )
    n["blocking_ambig"] = sum(
        1 for f in fields.values()
        if f["bucket"] == "A" and f["affects_quote"] and f["status"] == "ambiguous"
    )
    return n


def can_quote(fields: dict) -> tuple:
    """A 桶 + affects_quote 字段是否全部 stated（或用户已显式确认）。

    用户在工作台里点「客户已确认，移出待确认」= 销售已人工兜底，此时闸门放行，
    但必须在 HTML/Excel 里留下"人工确认"痕迹（fields[key].confirmed_by = 'sales'）。
    """
    bad = []
    for k, f in fields.items():
        if f["bucket"] == "A" and f["affects_quote"] and f["status"] != "stated":
            if f.get("confirmed_by") in ("sales", "customer"):
                continue
            bad.append(k)
    return (len(bad) == 0, bad)


# 可点击关闭的问题项（与 FIELD_SPEC 的「数值规格类」区分开）
RESOLVABLE = {"grade", "currency", "price_basis", "payment", "lc_terms", "pack_std",
              "delivery_time", "quote_validity", "sample_req"}


def scan_commitments(text: str) -> list:
    hits = []
    for pat, label, fix in COMMITMENT_PATTERNS:
        for m in re.finditer(pat, text, flags=re.I):
            hits.append({"pattern": label, "match": norm_ws(m.group(0)), "fix": fix, "index": m.start()})
    return hits


def scan_prices(text: str) -> list:
    """扫描"写死了的价格"。含占位符 ‹…› 的行跳过（那是设计要求的空位）。"""
    out = []
    for line in (text or "").splitlines():
        if "‹" in line and "›" in line:
            continue
        for pat in PRICE_PATTERNS:
            for m in re.finditer(pat, line, flags=re.I):
                ctx = norm_ws(line[max(0, m.start() - 24): m.end() + 24])
                out.append({"pattern": pat, "match": m.group(0), "context": ctx})
    return out


def find_placeholders(text: str) -> list:
    return re.findall(r"‹([A-Z0-9_]+)›", text or "")


def verify_quote(quote: str, source_text: str) -> bool:
    """原句是否能在原文中找到（忽略大小写与空白）。"""
    if not quote:
        return False
    a = re.sub(r"\s+", " ", quote).strip().lower()
    b = re.sub(r"\s+", " ", source_text or "").lower()
    return a in b


def human_date(d: str = "") -> str:
    if not d:
        return today_iso()
    return d


def split_customer_name(name: str) -> str:
    """用于文件名：去掉非法字符，保留中文/英文/数字。"""
    s = re.sub(r"[\\/:*?\"<>|\n\r\t]", " ", name or "customer")
    s = re.sub(r"\s+", "_", s.strip())
    return s[:60] or "customer"
