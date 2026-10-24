#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""radarlib —— 化工品采购商机雷达的公共库（产品无关）。

所有产品相关的知识都来自 config 文件（见 config/product.template.json），
本库只实现「与产品无关」的机制：取数、闸门、归一化、优先级、链接清洗。

只用标准库；出表脚本才需要 openpyxl。
"""
from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

# --------------------------------------------------------------------------
# 记录字段契约（跨产品固定；每条的字段含义见 references/outputs.md）
# --------------------------------------------------------------------------
FIELDS = [
    "公司", "事件类型", "细分行业", "省市", "事件产品", "数量/规模",
    "发布日", "截止日", "与我产品的关系", "分组", "需求性质",
    "时效性", "证据来源", "置信度",
]
OPTIONAL_FIELDS = ["信号方向", "用量强度", "优先级分", "优先级", "区域", "来源备注"]

GROUP_EXPLICIT = "明确采购/招标"
GROUP_CAPACITY = "扩产或复产需求"
GROUP_OTHER = "其他潜在需求信号"
GROUPS = [GROUP_EXPLICIT, GROUP_CAPACITY, GROUP_OTHER]

NATURE_EXPLICIT = "明确采购需求"
NATURE_INFERRED = "推断的潜在需求"

FRESH_OK, FRESH_LEAD, FRESH_EXPIRED = "仍可参与", "仅作线索", "已过期"
CONF_HIGH, CONF_MID, CONF_LOW = "高", "中", "低"

DIRECTION_GOOD, DIRECTION_BAD, DIRECTION_NEUTRAL = "利好", "利空", "中性"

DEFAULT_CONF = "product.json"


# --------------------------------------------------------------------------
# 可移植性：中文 Windows 的 stdout 默认是 GBK，打印非 GBK 字符（「↳」「≈」「●」等）
# 会直接抛 UnicodeEncodeError 把脚本打断。这是「换台电脑就废」的头号原因，
# 所以在 import 时就统一把 stdout/stderr 切成 UTF-8（这个模块是所有脚本的入口）。
# --------------------------------------------------------------------------
def ensure_utf8():
    for name in ("stdout", "stderr"):
        s = getattr(sys, name, None)
        if s is None:
            continue
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


ensure_utf8()


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------
def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("task", {})
    cfg.setdefault("product", {})
    cfg.setdefault("region", {})
    cfg.setdefault("peers", {})
    cfg.setdefault("gates", {})
    cfg.setdefault("priority", {})
    cfg.setdefault("strength_rules", [])
    cfg.setdefault("tonnage", [])
    cfg.setdefault("lanes", [])
    t = cfg["task"]
    t.setdefault("window_start", "1970-01-01")
    t.setdefault("window_end", "2999-12-31")
    t.setdefault("baseline_date", t["window_end"])
    t.setdefault("product_name", cfg["product"].get("name", "产品"))
    t.setdefault("region_name", cfg["region"].get("name", "全国"))
    t.setdefault("min_order", "未指定")
    t.setdefault("outdir", "out")
    return cfg


def slug(cfg: dict) -> str:
    return "%s_%s" % (cfg["task"]["product_name"], cfg["task"]["region_name"])


def outdir(cfg: dict, base: str) -> str:
    d = os.path.join(base, cfg["task"]["outdir"])
    os.makedirs(d, exist_ok=True)
    return d


def rawdir(base: str) -> str:
    d = os.path.join(base, "leads_raw")
    os.makedirs(d, exist_ok=True)
    return d


# --------------------------------------------------------------------------
# HTTP：优先 https，失败回退 http（有些环境完全没有 TLS 能力）
# --------------------------------------------------------------------------
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_SSL_CTX = None
_HTTPS_OK = True          # 一旦 https 因环境原因整体失败，就不再重试，直接走 http
_HTTPS_FAILS = 0


def _no_verify_ctx():
    global _SSL_CTX
    if _SSL_CTX is None:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        _SSL_CTX = ctx
    return _SSL_CTX


def _scheme_variants(url: str):
    """给出该 URL 的尝试顺序：原样 → 换个协议。"""
    if url.startswith("https://"):
        yield url, _no_verify_ctx()
        if not _HTTPS_OK:
            return
        yield "http://" + url[len("https://"):], None
    elif url.startswith("http://"):
        yield url, None
        if _HTTPS_OK:
            yield "https://" + url[len("http://"):], _no_verify_ctx()
    else:
        yield url, None


def http_get(url, headers=None, retries=3, backoff=6, timeout=30,
             data=None, method=None, want_status=False):
    """返回 (status, bytes_or_text) 或 (status, None)。

    - 优先 https，失败回退 http；反之亦然。
    - 403/5xx/网络错误都会退避重试（限流是常见假失败来源）。
    """
    global _HTTPS_OK, _HTTPS_FAILS
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    last = None
    for attempt in range(1, retries + 1):
        for real, ctx in _scheme_variants(url):
            req = urllib.request.Request(real, data=data, headers=hdrs)
            if method:
                req.get_method = lambda m=method: m
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                    body = r.read()
                    if want_status:
                        return r.status, body
                    return r.status, body.decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                last = (e.code, None)
                if e.code in (403, 429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(backoff * attempt)
                continue
            except ssl.SSLError as e:
                last = ("ERR", str(e)[:80])
                _HTTPS_FAILS += 1
                if _HTTPS_FAILS >= 3:
                    _HTTPS_OK = False      # 本环境无 TLS 能力，之后只走 http
                continue
            except Exception as e:
                last = ("ERR", str(e)[:80])
                continue
        time.sleep(backoff)
    return last if last else ("ERR", "unknown")


def http_post_json(url, payload, headers=None, retries=3, backoff=8, timeout=30):
    hdrs = {"Content-Type": "application/json;charset=UTF-8", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    return http_get(url, headers=hdrs, retries=retries, backoff=backoff, timeout=timeout,
                    data=json.dumps(payload).encode("utf-8"))


# --------------------------------------------------------------------------
# 链接清洗
# --------------------------------------------------------------------------
URL_RE = re.compile(r"https?://[^\s｜|，,、）)】\]]+")


def extract_urls(field) -> list:
    seen, out = set(), []
    for u in URL_RE.findall(str(field or "")):
        u = u.rstrip("。；;、")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def clean_source(field):
    """把「证据来源」整理成干净的 URL 列表 + 被剥离的说明文字。"""
    raw = str(field or "")
    urls = extract_urls(raw)
    note = URL_RE.sub("", raw)
    note = re.sub(r"[（）()【】\[\]｜|]", " ", note).strip(" ；;，,、")
    if note in ("未核实", "无"):
        note = ""
    return urls, note


# --------------------------------------------------------------------------
# 同义词 / 公司名归一化
# --------------------------------------------------------------------------
_ALIAS_RULES = None


def _alias_rules(cfg):
    global _ALIAS_RULES
    if _ALIAS_RULES is None:
        _ALIAS_RULES = [(a["match"], a["canonical"]) for a in cfg.get("company_aliases", [])]
    return _ALIAS_RULES


def norm_company(name, cfg=None):
    """公司名归一化：先套 config 里的别名表（把母子公司/不同写法并成一张卡），再剥掉通用后缀。"""
    s = str(name or "").strip()
    if cfg:
        for match, canon in _alias_rules(cfg):
            if match in s:
                return canon
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = re.sub(r"(股份有限公司|有限责任公司|有限公司|集团|公司|有限)$", "", s)
    return s.strip()


def product_hit(text, cfg) -> bool:
    """文本是否命中目标产品（学名/俗名/别名全都要算）。"""
    text = str(text or "")
    for term in cfg["product"].get("aliases", []):
        if term and term in text:
            return True
    return False


# --------------------------------------------------------------------------
# 用量强度 / 优先级
# --------------------------------------------------------------------------
def strength(text, cfg) -> int:
    """按 config 的 strength_rules 打分（pattern 命中即取该权重，取最高）。"""
    text = str(text or "")
    best = 0
    for rule in cfg.get("strength_rules", []):
        if re.search(rule["pattern"], text):
            best = max(best, int(rule["weight"]))
    return best or 1


CONF_W = {CONF_HIGH: 3, CONF_MID: 2, CONF_LOW: 1}


def priority(rec, cfg):
    st = strength(rec.get("_strength_text") or
                  " ".join(str(rec.get(k, "")) for k in ("细分行业", "事件产品", "事件类型", "数量/规模")), cfg)
    conf = CONF_W.get(rec.get("置信度"), 1)
    score = st * conf
    p = cfg.get("priority", {})
    score += int(p.get("bucket_bonus", {}).get(rec.get("分组"), 0))
    score += int(p.get("freshness_bonus", {}).get(rec.get("时效性"), 0))
    if extract_urls(rec.get("证据来源")):
        score += int(p.get("evidence_bonus", 0))
    th = p.get("thresholds", {"P1": 18, "P2": 13, "P3": 8})
    if score >= th.get("P1", 18):
        band = "P1 立即跟进"
    elif score >= th.get("P2", 13):
        band = "P2 本周跟进"
    elif score >= th.get("P3", 8):
        band = "P3 备选池"
    else:
        band = "P4 仅存档"
    return st, score, band


def in_region(rec, cfg) -> bool:
    blob = " ".join(str(rec.get(k, "")) for k in ("省市", "公司", "细分行业"))
    return any(k in blob for k in cfg["region"].get("keywords", []))


# --------------------------------------------------------------------------
# 六道闸门（产品无关的实现；产品知识来自 config）
# --------------------------------------------------------------------------
def _is_peer(rec, cfg) -> bool:
    company = str(rec.get("公司", ""))
    for name in cfg["peers"].get("names", []):
        if name and name in company:
            return True
    return False


def _subject_is_product(rec, cfg) -> bool:
    """事件主体是否真的就是目标产品本身（用于区分「同行产本产品」与「下游用本产品」）。"""
    prod = " ".join(str(rec.get(k, "")) for k in ("事件产品", "细分行业"))
    for pat in cfg["peers"].get("subject_patterns", []):
        if re.search(pat, prod):
            return True
    return False


def gate(rec, cfg):
    """返回 (keep: bool, reason: str)。keep=False 表示剔除。"""
    task = cfg["task"]
    company = str(rec.get("公司", ""))
    blob = " ".join(str(rec.get(k, "")) for k in
                    ("公司", "事件类型", "细分行业", "省市", "事件产品", "数量/规模", "与我产品的关系"))
    # R2 只能看「事件标的」字段，**绝不能把「与我产品的关系」算进去**：那是分析人员的解释
    # 文字，常常要写「本工序主耗烧碱而非纯碱」来排除干扰，一旦计入，就会把最好的线索
    # （实测：亚星化学的纯碱招标）当成产品错配误杀。这个坑踩过一次，写死在代码里防复发。
    subject_blob = " ".join(str(rec.get(k, "")) for k in
                            ("公司", "事件类型", "细分行业", "事件产品", "数量/规模"))
    grp = rec.get("分组")
    rel = str(rec.get("与我产品的关系", ""))

    # ---- R2 产品错配闸门（**必须排在 R1 之前**：先排除「事件标的其实是近名产品」的情况，
    #      否则同行主体的近名产品事件会被 R1 误判成「同行自身动态」，剔除理由失真）
    for item in cfg["gates"].get("mismatch_terms", []):
        term = item["term"] if isinstance(item, dict) else item
        reason = item.get("reason", "") if isinstance(item, dict) else ""
        if not term or term not in subject_blob:
            continue
        # 守卫：事件标的里只要**同时出现了目标产品**，就不算错配 —— 公告常常是混合标的
        # （「本次采购含纯碱 300 吨、烧碱 50 吨」），不能因为顺带提到烧碱就整条丢掉。
        if product_hit(subject_blob, cfg):
            continue
        return False, "R2 产品错配闸门：命中「%s」%s" % (term, ("——" + reason) if reason else "")

    # 方向标注 [利好]/[利空]/[中性] 只要是「信号类」线索都要提出来 —— 不仅同行，
    # 买方的评级报告口径、市场供需判断同样要进「同行动态与市场信号」那一组。
    m = re.search(r"\[(%s|%s|%s)\]" % (DIRECTION_GOOD, DIRECTION_BAD, DIRECTION_NEUTRAL), rel)
    if m:
        rec["信号方向"] = m.group(1)

    # ---- R1 同行闸门（含反向用法：同行检修/停产/降负荷 = 我方补货窗口）
    if _is_peer(rec, cfg) and _subject_is_product(rec, cfg):
        if rec.get("信号方向"):
            # 带方向标注的同行信号：**利好/利空/中性都保留**，归入「同行动态与市场信号」。
            # 同行检修停产是补货窗口（利好），同行扩产是新增供给（利空），都是影响我方
            # 报价与库存策略的情报，删掉等于丢信息。只在「信号方向」列里标清方向即可。
            rec["分组"] = GROUP_OTHER
            rec["需求性质"] = NATURE_INFERRED
            rec["_peer_signal"] = True
            return True, ""
        if grp in (GROUP_EXPLICIT, GROUP_CAPACITY):
            return False, "R1 同行闸门：%s 是%s生产主体，其扩产/技改属新增供给，非我方商机" % (
                company[:16], task["product_name"])
        return False, "R1 同行闸门：%s %s同行自身动态，非采购需求" % (company[:16], task["product_name"])

    # ---- R1b 名单外的「本产品产能建设」也属同行
    if not _is_peer(rec, cfg):
        for pat in cfg["gates"].get("capacity_patterns", []):
            if re.search(pat, str(rec.get("事件产品", "")) + str(rec.get("细分行业", ""))):
                return False, "R1 同行闸门：名单外主体的%s产能建设，属新增供给" % task["product_name"]

    # ---- R4 时间闸门
    pub = str(rec.get("发布日") or "")
    if pub and pub[:10] > task["window_end"]:
        return False, "R4 时间闸门：发布日 %s 晚于窗口 %s" % (pub[:10], task["window_end"])
    if pub and pub[:10] < task["window_start"]:
        if rec.get("时效性") == FRESH_OK:
            rec["来源备注"] = ("发布日 %s 早于窗口但截止日 %s 仍在未来，保留" %
                           (pub[:10], rec.get("截止日", ""))) + (
                ("；" + rec["来源备注"]) if rec.get("来源备注") else "")
        else:
            return False, "R4 时间闸门：发布日 %s 超出窗口 %s~%s" % (
                pub[:10], task["window_start"], task["window_end"])

    # ---- R3 地域闸门（不剔除，只标注；让用户自己筛）
    rec["区域"] = cfg["region"].get("in_label", "本区") if in_region(rec, cfg) \
        else cfg["region"].get("out_label", "区外")

    # ---- R5 相关性闸门
    if len(rel.strip()) < int(cfg["gates"].get("min_relation_chars", 30)):
        return False, "R5 相关性闸门：与我产品的关系过短，未写清用量逻辑"
    # 注意：默认**不**强制关系里出现数字。实测把这条打开会误杀一批质量不错的推断线索
    # （比如「同行检修 → 供给收紧 → 补货窗口」这类本来就没有数字），所以默认关闭，
    # 需要更严的召回时再在 config 里打开。
    if cfg["gates"].get("require_number_in_relation", False) and not re.search(r"\d", rel):
        return False, "R5 相关性闸门：与我产品的关系里没有任何量级/数量，属空话"

    # ---- R6 证据闸门（不剔除，降置信度并另列到待核实表）
    if not extract_urls(rec.get("证据来源")):
        rec["置信度"] = CONF_LOW
        rec["证据来源"] = "未核实"
        rec["_unverified"] = True

    return True, ""


def normalize(rec: dict, cfg: dict) -> dict:
    """补齐字段与派生字段，保证下游脚本拿到的记录形状一致。"""
    out = {}
    for k in FIELDS:
        out[k] = str(rec.get(k, "") or "").strip()
    for k in ("信号方向", "来源备注"):
        out[k] = str(rec.get(k, "") or "").strip()

    if out["分组"] not in GROUPS:
        out["分组"] = GROUP_OTHER
    if out["需求性质"] not in (NATURE_EXPLICIT, NATURE_INFERRED):
        out["需求性质"] = NATURE_EXPLICIT if out["分组"] == GROUP_EXPLICIT else NATURE_INFERRED
    if out["时效性"] not in (FRESH_OK, FRESH_LEAD, FRESH_EXPIRED):
        out["时效性"] = FRESH_LEAD
    if out["置信度"] not in (CONF_HIGH, CONF_MID, CONF_LOW):
        out["置信度"] = CONF_MID
    if not out["发布日"]:
        out["发布日"] = ""

    urls, note = clean_source(out["证据来源"])
    out["证据来源"] = " ｜ ".join(urls) if urls else "未核实"
    if note and not out.get("来源备注"):
        out["来源备注"] = note
    if not urls:
        out["置信度"] = CONF_LOW
        out["_unverified"] = True

    st, sc, band = priority(out, cfg)
    out["用量强度"], out["优先级分"], out["优先级"] = st, sc, band
    if "区域" not in rec or not rec.get("区域"):
        out["区域"] = cfg["region"].get("in_label", "本区") if in_region(out, cfg) \
            else cfg["region"].get("out_label", "区外")
    else:
        out["区域"] = str(rec["区域"])
    return out


ORDER_G = {GROUP_EXPLICIT: 0, GROUP_CAPACITY: 1, GROUP_OTHER: 2}
ORDER_F = {FRESH_OK: 3, FRESH_LEAD: 2, FRESH_EXPIRED: 1}


def sort_key(rec):
    return (ORDER_G.get(rec.get("分组"), 9), -int(rec.get("优先级分") or 0),
            -ORDER_F.get(rec.get("时效性"), 0), str(rec.get("公司", "")))


def dedupe(rows, cfg):
    """两级去重：① 证据链接完全相同；② 公司+事件类型+发布日 完全相同。"""
    kept, dropped = [], []
    seen_url, seen_key = set(), set()
    for r in sorted(rows, key=sort_key):
        urls = extract_urls(r.get("证据来源"))
        ukey = (urls[0], str(r.get("分组"))) if urls else None
        # 二级去重键**必须带分组**：同一家公司在「明确采购」和「扩产」两个分组里各有一条
        # 是正常的（要分别进不同工作表），不带分组会把跨分组的一条杀掉。
        kkey = (norm_company(r.get("公司"), cfg), str(r.get("事件类型"))[:12],
                str(r.get("发布日"))[:10], str(r.get("分组")))
        if ukey and ukey in seen_url:
            r["剔除原因"] = "重复条目（同一分组内证据链接与已有条目相同）"
            dropped.append(r)
            continue
        if kkey in seen_key:
            r["剔除原因"] = "重复条目（同一分组内公司+事件类型+发布日 与已有条目相同）"
            dropped.append(r)
            continue
        if ukey:
            seen_url.add(ukey)
        seen_key.add(kkey)
        kept.append(r)
    return kept, dropped


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------
def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def resolve_config(argv=None):
    """统一解析 --config / --dir 两个参数。"""
    argv = argv if argv is not None else sys.argv[1:]
    cfg_path, base = None, None
    for i, a in enumerate(argv):
        if a == "--config" and i + 1 < len(argv):
            cfg_path = argv[i + 1]
        elif a == "--dir" and i + 1 < len(argv):
            base = argv[i + 1]
    base = base or os.getcwd()
    if not cfg_path:
        for cand in (os.path.join(base, DEFAULT_CONF),
                     os.path.join(base, "config", DEFAULT_CONF)):
            if os.path.exists(cand):
                cfg_path = cand
                break
    if not cfg_path or not os.path.exists(cfg_path):
        sys.exit("找不到 config。用法: --config <product.json> [--dir <任务目录>]")
    cfg = load_config(cfg_path)
    return cfg, base, cfg_path