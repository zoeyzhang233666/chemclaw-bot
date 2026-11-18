# -*- coding: utf-8 -*-
"""公共定义：证据分级、四类结论、判定规则、校验。

本文件不依赖任何第三方库，也不含任何产品信息 —— 产品相关内容全部来自 input.json。
"""
import html
import json
import os
import re
import sys

# Windows 控制台默认 GBK，遇到 ₂、③ 这类字符会直接抛 UnicodeEncodeError。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------- 证据强度
STRENGTH = {
    3: ("强", "●●●", "政府许可/备案、交易所或协会名录、上市公司审计披露、可复现的第三方记录"),
    2: ("中", "●●○", "企业官网结构化信息（可与第三方互证）、行业媒体、招聘/招标、专利"),
    1: ("弱", "●○○", "企业自述宣传、单张照片、口头承诺、无法定位的车间视频"),
    0: ("不计分", "○○○", "不构成生产证据，仅作背景参考"),
}

# ---------------------------------------------------------------- 四类结论
VERDICT_META = {
    "生产厂家": {"color": "green", "icon": "◆",
              "meaning": "以自有装置完成目标化学品的合成/提纯，可开出厂价、可验厂"},
    "分装或复配": {"color": "amber", "icon": "◈",
               "meaning": "不合成目标产品，仅做破碎、筛分、混合、稀释、小包装或复配"},
    "贸易经销": {"color": "red", "icon": "◇",
              "meaning": "以调货、代理、仓储交割为主，无自有生产装置"},
    "证据不足暂无法确认": {"color": "gray", "icon": "○",
                 "meaning": "公开可核证据不足以支撑任何一类判断，需补材料或现场核验"},
}

# ---------------------------------------------------------------- 判定顺序
VERDICT_RULES = [
    {"step": "Q1", "question": "是否存在以该企业为主体的目标产品生产硬证据？",
     "detail": "排污许可证（对应行业类别）；或环评批复/验收载明该产品与产能；或项目备案/产能置换公示载明该企业为主体；危化品/食品/农药等另有法定许可",
     "yes": "进入 Q2", "no": "进入 Q3"},
    {"step": "Q2", "question": "公开产能、产量、厂址与许可是否自洽？",
     "detail": "产能与产量量级匹配、厂址与许可地址一致、工艺路线能解释原料与副产品、产品规格对得上",
     "yes": "判定：生产厂家", "no": "判定：生产厂家（待现场核验）"},
    {"step": "Q3", "question": "是否存在分装/复配特征？",
     "detail": "仅持有分装类许可；无合成/反应/精馏/结晶主装置；设备为粉碎、筛分、混合、稀释、包装；外购成品或半成品",
     "yes": "判定：分装或复配", "no": "进入 Q4"},
    {"step": "Q4", "question": "是否存在贸易经销特征？",
     "detail": "交易所贸易商厂库、生产厂代理授权、无生产装置与排污许可、注册地为写字楼、以调货为主",
     "yes": "判定：贸易经销", "no": "判定：证据不足，暂无法确认"},
]

# ---------------------------------------------------------------- 默认评分维度
DEFAULT_DIMENSIONS = [
    {"name": "生产许可与环保手续", "weight": 30,
     "detail": "排污许可（对应行业类别）、环评批复/验收中的产品与产能、项目备案/节能审查、产能置换公示、法定专项许可"},
    {"name": "产能与装置实据", "weight": 30,
     "detail": "公开产能与产量、装置条线与车间编制、厂址与门牌、原料一体化配置、同址关联装置、非计划停产公告"},
    {"name": "产品与市场证据", "weight": 20,
     "detail": "官网产品页与牌号规格、自营销售渠道、交易所交割厂库/协会名录、客户与中标记录、品牌"},
    {"name": "运营侧痕迹", "weight": 10,
     "detail": "原料采购、生产岗位招聘、专利与技术论文、物流与铁路专用线、公开招标"},
    {"name": "现场与第三方核验", "weight": 10,
     "detail": "视频验厂、磅单、批次质检、第三方验厂报告、发票与发货地一致性"},
]

CATEGORY_ORDER = ["许可与环保", "产能与装置", "产品与市场", "运营痕迹"]
PRIORITIES = ["P0", "P1", "P2"]
CONFIDENCES = ["高", "中高", "中", "低"]

REQUIRED_META = ["report_id", "as_of", "title", "product", "slug"]
REQUIRED_CASE = ["id", "company", "short", "product", "verdict", "confidence", "score", "dims",
                 "direct", "indirect", "excluded", "facts", "headline", "verdict_detail",
                 "gaps", "next_action"]
REQUIRED_EV = ["code", "title", "strength", "why"]
REQUIRED_MAT = ["id", "name", "priority", "purpose", "look", "script"]
REQUIRED_ONSITE = ["item", "method", "pass", "fake"]


def load_doc(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        doc = json.load(f)
    return normalize(doc)


def normalize(doc):
    """补齐可选字段的默认值，保证老版本 input.json 也能跑。"""
    doc.setdefault("schema_version", SCHEMA_VERSION)
    doc.setdefault("dimensions", DEFAULT_DIMENSIONS)
    doc.setdefault("materials", [])
    doc.setdefault("onsite", [])
    doc.setdefault("sources", [])
    doc.setdefault("product_profile", {})
    meta = doc.setdefault("meta", {})
    meta.setdefault("slug", "supplier-verification")
    meta.setdefault("title", "供应商真伪核验")
    meta.setdefault("as_of", "")
    meta.setdefault("report_id", "SV-001")
    meta.setdefault("disclaimer", "本报告为采购尽调辅助材料，不构成法律意见。")
    for i, c in enumerate(doc.get("cases", []), start=1):
        c.setdefault("id", "case-%d" % i)
        c.setdefault("short", c.get("company", c["id"]))
        c.setdefault("unit", "")
        c.setdefault("aliases", [])
        c.setdefault("brand", "—")
        c.setdefault("listed", "—")
        c.setdefault("status", "—")
        c.setdefault("addr", "—")
        c.setdefault("capacity", "—")
        c.setdefault("output", "—")
        c.setdefault("process", "—")
        c.setdefault("score_note", "")
        c.setdefault("synthetic", False)
        for k in ("direct", "indirect", "excluded"):
            c.setdefault(k, [])
        for it in c["direct"] + c["indirect"] + c["excluded"]:
            it.setdefault("cat", "")
            it.setdefault("url", "")
            it.setdefault("source", "对方提供" if it.get("strength", 0) == 0 else "")
            it.setdefault("date", "")
            it.setdefault("quote", "")
    return doc


def esc(x):
    return html.escape(str(x if x is not None else ""))


def slug_ok(slug):
    return not re.search(r'[\\/:*?"<>|]', slug or "")


def dims_total(case):
    return sum(int(x) for x in case.get("dims", []))


def categories_of(doc):
    seen = []
    for c in doc.get("cases", []):
        for it in c.get("direct", []) + c.get("indirect", []):
            cat = it.get("cat")
            if cat and cat not in seen:
                seen.append(cat)
    ordered = [x for x in CATEGORY_ORDER if x in seen] + [x for x in seen if x not in CATEGORY_ORDER]
    return ordered


def _is_http(url):
    return bool(re.match(r"^https?://", url or ""))


def check_doc(doc):
    """返回 (errors, warnings)。errors 会阻断 build，warnings 只提示。"""
    errors, warnings = [], []
    cases = doc.get("cases", [])
    dims = doc.get("dimensions", [])
    meta = doc.get("meta", {})

    if doc.get("schema_version") != SCHEMA_VERSION:
        warnings.append("schema_version 不是 %s（当前 %r），按兼容模式继续" % (SCHEMA_VERSION, doc.get("schema_version")))
    for k in REQUIRED_META:
        if not meta.get(k):
            errors.append("meta.%s 缺失" % k)
    if not cases:
        errors.append("cases 为空：至少放 1 个案例")
    if not dims:
        errors.append("dimensions 为空")
    elif sum(int(d.get("weight", 0)) for d in dims) != 100:
        errors.append("dimensions 权重合计 = %d，必须等于 100" % sum(int(d.get("weight", 0)) for d in dims))

    ids = set()
    for c in cases:
        cid = c.get("id")
        if cid in ids:
            errors.append("case.id 重复：%s" % cid)
        ids.add(cid)
        for k in REQUIRED_CASE:
            if k not in c or c[k] in ("", None, []):
                if k not in ("direct", "indirect", "excluded"):
                    errors.append("%s：缺少 %s" % (cid, k))
        if c.get("verdict") not in VERDICT_META:
            errors.append("%s：结论 %r 不在四类之中" % (cid, c.get("verdict")))
        if c.get("confidence") not in CONFIDENCES:
            errors.append("%s：confidence %r 不在 %s 之中" % (cid, c.get("confidence"), CONFIDENCES))
        if len(c.get("dims", [])) != len(dims):
            errors.append("%s：dims 长度 %d ≠ 维度数 %d" % (cid, len(c.get("dims", [])), len(dims)))
        else:
            for i, (v, d) in enumerate(zip(c["dims"], dims)):
                if not (0 <= int(v) <= int(d.get("weight", 0))):
                    errors.append("%s：第 %d 维得分 %s 超出 0—%s" % (cid, i + 1, v, d.get("weight")))
            if dims_total(c) != int(c.get("score", -1)):
                errors.append("%s：dims 合计 %d ≠ score %s" % (cid, dims_total(c), c.get("score")))
        if not (0 <= int(c.get("score", -1)) <= 100):
            errors.append("%s：score 必须在 0—100" % cid)

        ev_all = c.get("direct", []) + c.get("indirect", []) + c.get("excluded", [])
        if not ev_all:
            errors.append("%s：一条证据都没有" % cid)
        codes = set()
        for it in ev_all:
            code = it.get("code")
            if not code:
                errors.append("%s：存在没有 code 的证据" % cid)
                continue
            if code in codes:
                errors.append("%s：证据编号重复 %s（同一案例内必须唯一）" % (cid, code))
            codes.add(code)
            for k in REQUIRED_EV:
                if k not in it or it[k] in ("", None):
                    errors.append("%s %s：缺少 %s" % (cid, code, k))
            s = it.get("strength")
            if s not in (0, 1, 2, 3):
                errors.append("%s %s：strength 必须是 0/1/2/3" % (cid, code))
            if it.get("url") and not _is_http(it["url"]):
                errors.append("%s %s：url 必须以 http(s):// 开头" % (cid, code))
            if not it.get("url") and it.get("strength", 0) >= 2 and not c.get("synthetic"):
                warnings.append("%s %s：中/强证据没有来源链接，复核性弱" % (cid, code))

        for it in c.get("excluded", []):
            if it.get("strength") != 0:
                errors.append("%s %s：排除项 strength 必须为 0" % (cid, it.get("code")))
        for it in c.get("direct", []) + c.get("indirect", []):
            if it.get("strength") == 0:
                warnings.append("%s %s：非排除项却标了 0 分" % (cid, it.get("code")))

        verdict = c.get("verdict")
        if verdict == "生产厂家" and not c.get("direct"):
            errors.append("%s：判为生产厂家，但直接生产证据为 0 条" % cid)
        if verdict in ("分装或复配", "贸易经销", "证据不足暂无法确认") and c.get("direct"):
            warnings.append("%s：判为 %s，但仍有 %d 条直接证据，请复核是否应为生产厂家"
                            % (cid, verdict, len(c.get("direct"))))
        if verdict in ("贸易经销", "分装或复配") and int(c.get("score", 0)) >= 60:
            warnings.append("%s：判为 %s 但充分度 %s 偏高，检查维度打分" % (cid, verdict, c.get("score")))
        if verdict == "证据不足暂无法确认" and int(c.get("score", 0)) >= 50:
            warnings.append("%s：证据不足但分数 ≥50，检查是否漏判" % cid)
        if len(c.get("facts", [])) != 6:
            warnings.append("%s：facts 建议 6 条（当前 %d），版面会不齐" % (cid, len(c.get("facts", []))))
        if not c.get("timeline"):
            warnings.append("%s：没有 timeline，时间线会空" % cid)

    mids = set()
    for m in doc.get("materials", []):
        for k in REQUIRED_MAT:
            if not m.get(k):
                errors.append("materials：%s 缺字段 %s" % (m.get("id", "?"), k))
        if m.get("priority") not in PRIORITIES:
            errors.append("materials %s：priority 必须是 P0/P1/P2" % m.get("id"))
        if m.get("id") in mids:
            errors.append("materials id 重复：%s" % m.get("id"))
        mids.add(m.get("id"))
    for o in doc.get("onsite", []):
        for k in REQUIRED_ONSITE:
            if not o.get(k):
                errors.append("onsite：%r 缺字段 %s" % (o.get("item", "?"), k))
    for s in doc.get("sources", []):
        if s.get("url") and not _is_http(s["url"]):
            errors.append("sources %s：url 非法" % s.get("id"))
    if not doc.get("onsite"):
        warnings.append("onsite 为空：验厂脚本区块会是空的")
    if not doc.get("sources"):
        warnings.append("sources 为空：数据来源表会是空的")
    return errors, warnings
