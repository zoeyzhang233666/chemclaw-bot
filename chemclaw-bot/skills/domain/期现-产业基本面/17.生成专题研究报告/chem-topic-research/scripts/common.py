# -*- coding: utf-8 -*-
"""
chem-topic-research 公共工具：case 校验、索引、模板渲染、JSON 安全序列化。

设计原则
--------
1. 一切数字都必须能追溯到 sources / calculations / data_gaps 中的一个；
2. 渲染层（HTML / XLSX / Markdown）只消费 case，不各自实现业务逻辑；
3. 任何"缺数据"的地方都显式输出 gap，而不是留空或估算。

命令行
------
  python common.py validate <case.json>        # 校验并打印结果
  python common.py audit    <case.json>        # 输出证据索引 JSON
"""
from __future__ import annotations

import json
import os
import re
import sys

SCHEMA_VERSION = "chem-topic-research/1.0"

STATEMENT_TYPES = ("事实", "计算", "解释", "判断")
CONFIDENCE = ("高", "中", "低", "中低", "中高")
PROJECT_STATUS = ("已投产", "在建", "规划", "退出", "暂停")
EVIDENCE_STRENGTH = ("A", "B", "C", "D")
GAP_SEVERITY = ("high", "medium", "low")

# 章节包：不按品种固化目录，而是按"研究功能"分类，任何品种都可复用
SECTION_PACKS = {
    "research_design": "研究设计：问题、范围、口径",
    "structure": "供给结构：产能、工艺、企业、集中度",
    "region": "区域格局：产区、物流、价差",
    "projects": "项目台账：在建、新投、退出",
    "calculation": "核心测算：有效供给、平衡表、敏感性",
    "cost": "成本曲线：工艺成本、利润、出清阈值",
    "demand": "需求侧：下游、单耗、终端宏观",
    "price_history": "价格与库存：历史校验",
    "company": "企业深度：集团、产线、财务",
    "policy": "政策与合规",
    "chain": "产业链传导",
    "process": "工艺与技术路线",
    "conclusion": "结论、反证条件、后续核验",
    "risk": "风险",
}

REQUIRED = {
    "meta": ["title", "product_cn", "audience", "report_date", "data_cutoff"],
    "research_brief": ["objective", "questions"],
    "sources": [],
    "data_gaps": [],
}

HIGH_IMPACT_PACKS_FOR_MANAGEMENT = ("calculation", "cost", "structure", "conclusion")


# --------------------------------------------------------------------------
# 读写
# --------------------------------------------------------------------------
def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path: str, obj) -> str:
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return path


def ensure_dir(path: str) -> None:
    if path and not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def safe_json(obj) -> str:
    """把对象安全地嵌入 <script> 标签。"""
    s = json.dumps(obj, ensure_ascii=False)
    return (s.replace("</", "<\\/")
             .replace("<!--", "<\\!--")
             .replace("\u2028", "\\u2028")
             .replace("\u2029", "\\u2029"))


# --------------------------------------------------------------------------
# 索引
# --------------------------------------------------------------------------
def source_index(case: dict) -> dict:
    return {s["id"]: s for s in case.get("sources") or []}


def gap_index(case: dict) -> dict:
    return {g["id"]: g for g in case.get("data_gaps") or []}


def calc_index(case: dict) -> dict:
    return {c["id"]: c for c in case.get("calculations") or []}


def conclusion_index(case: dict) -> dict:
    return {c["id"]: c for c in case.get("conclusions") or []}


def evidence_refs(obj) -> list:
    """从任意对象中提取 source id 列表；支持对象或字典。"""
    if isinstance(obj, dict):
        val = obj.get("evidence") or obj.get("source") or []
    else:
        val = getattr(obj, "evidence", None) or getattr(obj, "source", None) or []
    if isinstance(val, str):
        val = [x.strip() for x in val.split(",") if x.strip()]
    out = []
    for v in val:
        if v and v not in out:
            out.append(v)
    return out


def build_evidence_index(case: dict) -> list:
    """把全文中所有引用汇总成『证据 → 被谁引用 → 定义』的三段式索引。"""
    src = source_index(case)
    gap = gap_index(case)
    calcs = calc_index(case)
    used = {}

    def use(sid, where, what):
        if not sid:
            return
        node = used.setdefault(sid, {"where": [], "what": what})
        if where not in node["where"]:
            node["where"].append(where)

    def what_for(sid):
        if sid in src:
            return "%s｜%s｜%s" % (src[sid].get("org", ""), src[sid].get("title", ""),
                                   src[sid].get("date", ""))
        if sid in gap:
            return "缺口｜%s｜%s" % (gap[sid].get("topic", ""), gap[sid].get("missing", ""))
        return "未登记引用"

    for s in case.get("sections") or []:
        title = s.get("title", s.get("id"))
        for b in s.get("blocks") or []:
            for sid in evidence_refs(b):
                use(sid, "章节·%s" % title, what_for(sid))
            dk = b.get("data_key")
            if dk:
                for sid in refs_in_datakey(case, dk):
                    use(sid, "图表·%s" % (b.get("title") or dk), what_for(sid))
    for c in case.get("conclusions") or []:
        for sid in evidence_refs(c):
            use(sid, "结论·%s" % c.get("id"), what_for(sid))
    for c in case.get("calculations") or []:
        for sid in evidence_refs(c):
            use(sid, "计算·%s" % c.get("id"), what_for(sid))
    for k in case.get("kpis") or []:
        for sid in evidence_refs(k):
            use(sid, "指标·%s" % k.get("label"), what_for(sid))
    for p in case.get("projects") or []:
        for sid in evidence_refs(p):
            use(sid, "项目·%s" % p.get("id"), what_for(sid))
    for c in case.get("companies") or []:
        for sid in evidence_refs(c):
            use(sid, "企业·%s" % c.get("group"), what_for(sid))
    for key in ("price_points", "inventory", "output_weekly", "glass_runrate", "macro",
                "demand_structure", "cr5", "cost_curve", "profit", "supply_demand"):
        for row in _iter_rows(case.get(key)):
            for sid in evidence_refs(row):
                use(sid, "数据·%s" % key, what_for(sid))
    for sid in case.get("capacity_structure", {}).get("source", "").split(","):
        use(sid.strip(), "数据·capacity_structure", what_for(sid.strip()))

    out = []
    for sid in sorted(set(src) | set(gap) | set(used)):
        node = used.get(sid, {"where": [], "what": what_for(sid)})
        out.append({
            "id": sid,
            "kind": "source" if sid in src else ("gap" if sid in gap else "missing"),
            "what": node["what"],
            "refs": node["where"],
            "url": src.get(sid, {}).get("url", ""),
            "tier": src.get(sid, {}).get("tier", ""),
        })
    return out


def _iter_rows(v):
    """统一展开各种数据容器为行字典列表。"""
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict)]
    if isinstance(v, dict):
        rows = []
        for key in ("rows", "shares", "points"):
            if isinstance(v.get(key), list):
                rows.extend(v[key])
        return rows
    return []


def refs_in_datakey(case: dict, dk: str) -> list:
    """解析 data_key（如 'capacity_structure.shares'）并取出其中出现的 source。"""
    node = get_by_path(case, dk)
    out = []
    for row in _iter_rows(node):
        for sid in evidence_refs(row):
            if sid not in out:
                out.append(sid)
    if isinstance(node, dict) and node.get("source"):
        for sid in str(node["source"]).split(","):
            sid = sid.strip()
            if sid and sid not in out:
                out.append(sid)
    return out


def get_by_path(case: dict, path: str):
    node = case
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
        if node is None:
            return None
    return node


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def validate(case: dict) -> tuple:
    """返回 (errors, warnings)。errors 非空时不得生成正式交付物。"""
    errors, warns = [], []

    for k, fields in REQUIRED.items():
        # 只要求"字段存在"；空列表/空字典是合法的骨架状态（提纲阶段），由后续检查提示内容不足
        if k not in case or case[k] is None:
            errors.append("缺少顶层字段 %s" % k)
            continue
        for f in fields:
            if k == "meta":
                if not (case[k] or {}).get(f):
                    errors.append("meta.%s 缺失" % f)
            elif isinstance(case[k], dict) and f not in case[k]:
                errors.append("%s.%s 缺失" % (k, f))

    sv = case.get("schema_version")
    if sv and sv != SCHEMA_VERSION:
        warns.append("schema_version=%s，当前工具按 %s 处理" % (sv, SCHEMA_VERSION))

    src = source_index(case)
    gaps = gap_index(case)
    known = set(src) | set(gaps)

    # 1) 引用可解析
    def check_refs(owner, obj):
        for sid in evidence_refs(obj):
            if sid not in known:
                errors.append("%s 引用了未登记的来源/缺口 %s" % (owner, sid))

    for s in case.get("sections") or []:
        title = s.get("title", s.get("id"))
        if not s.get("id"):
            errors.append("章节缺少 id：%s" % title)
        for b in s.get("blocks") or []:
            check_refs("章节[%s]" % title, b)
            dk = b.get("data_key")
            if dk and get_by_path(case, dk) is None:
                errors.append("章节[%s] 的 data_key 无法解析：%s" % (title, dk))
            if b.get("chart_type") and not dk:
                errors.append("章节[%s] 的图表缺少 data_key" % title)
            if b.get("type") == "calc" and b.get("calc_id") not in calc_index(case):
                errors.append("章节[%s] 引用了不存在的计算 %s" % (title, b.get("calc_id")))
    for c in case.get("conclusions") or []:
        check_refs("结论[%s]" % c.get("id"), c)
        if c.get("type") not in STATEMENT_TYPES:
            errors.append("结论[%s] type=%s 不在 %s 中" % (c.get("id"), c.get("type"), STATEMENT_TYPES))
        if not (c.get("evidence") or []):
            errors.append("结论[%s] 无证据：重要结论必须可追溯" % c.get("id"))
        if c.get("type") in ("判断", "解释") and not c.get("falsify"):
            warns.append("结论[%s] 为%s但缺少反证条件" % (c.get("id"), c.get("type")))
        if c.get("confidence") not in CONFIDENCE:
            warns.append("结论[%s] confidence=%s 未标准化" % (c.get("id"), c.get("confidence")))
        for cid in c.get("calcs") or []:
            if cid not in calc_index(case):
                errors.append("结论[%s] 引用不存在的计算 %s" % (c.get("id"), cid))
    for c in case.get("calculations") or []:
        check_refs("计算[%s]" % c.get("id"), c)
        for f in ("id", "title", "formula", "inputs", "output"):
            if not c.get(f):
                errors.append("计算[%s] 缺少 %s" % (c.get("id"), f))
        if c.get("statement_type") not in STATEMENT_TYPES:
            warns.append("计算[%s] statement_type 未标注" % c.get("id"))
    for p in case.get("projects") or []:
        check_refs("项目[%s]" % p.get("id"), p)
        if p.get("status") not in PROJECT_STATUS:
            errors.append("项目[%s] status=%s 不在 %s 中" % (p.get("id"), p.get("status"), PROJECT_STATUS))
        if not p.get("status_basis"):
            errors.append("项目[%s] 缺少 status_basis：状态必须有依据" % p.get("id"))
        if not p.get("evidence"):
            errors.append("项目[%s] 无证据" % p.get("id"))
        if p.get("strength") not in EVIDENCE_STRENGTH:
            warns.append("项目[%s] 证据强度 %s 未标准化" % (p.get("id"), p.get("strength")))
        if p.get("status") == "已投产" and not p.get("actual_date"):
            warns.append("项目[%s] 已投产但无 actual_date" % p.get("id"))
    for g in case.get("data_gaps") or []:
        for f in ("id", "topic", "missing", "impact", "next_step"):
            if not g.get(f):
                errors.append("缺口[%s] 缺少 %s" % (g.get("id"), f))
        if g.get("severity") not in GAP_SEVERITY:
            warns.append("缺口[%s] severity 未标准化" % g.get("id"))
    for k in case.get("kpis") or []:
        check_refs("指标[%s]" % k.get("id"), k)
        if not (k.get("evidence") or []):
            warns.append("指标[%s] 未挂证据" % k.get("id"))
    for k in case.get("key_variables") or []:
        check_refs("变量[%s]" % k.get("id"), k)
        if not k.get("threshold"):
            warns.append("变量[%s] 缺少阈值" % k.get("id"))

    # 2) 受众
    aud = (case.get("meta") or {}).get("audience")
    fws = case.get("audience_frameworks") or {}
    if fws and aud not in fws:
        warns.append("meta.audience=%s 在 audience_frameworks 中不存在" % aud)

    # 3) 来源最少数量 & URL
    if len(src) < 3:
        warns.append("来源不足 3 条，证据基础偏薄")
    for s in src.values():
        if not s.get("url"):
            warns.append("来源 %s 缺少 URL" % s.get("id"))

    # 4) 章节覆盖
    packs = [s.get("pack") for s in case.get("sections") or []]
    for p in packs:
        if p and p not in SECTION_PACKS:
            warns.append("章节包 %s 不在标准包中（允许自定义，但请确认）" % p)
    if "calculation" not in packs and case.get("calculations"):
        warns.append("存在计算但缺少 calculation 章节，计算过程未在正文展示")
    if not (case.get("conclusions") or []):
        errors.append("缺少结论：报告必须有结构化结论")

    # 5) 数量硬约束
    if len(case.get("kpis") or []) > 10:
        warns.append("KPI 超过 10 个，首屏会失焦")
    return errors, warns


# --------------------------------------------------------------------------
# 受众适配
# --------------------------------------------------------------------------
def audience_profile(case: dict, audience: str | None = None) -> dict:
    fws = case.get("audience_frameworks") or {}
    aud = audience or (case.get("meta") or {}).get("audience") or "industry-researcher"
    requested = aud
    if aud not in fws and fws:                      # 该受众没定制框架 → 回退到 case 默认受众
        fallback = (case.get("meta") or {}).get("audience")
        if fallback in fws:
            aud = fallback
        else:
            aud = next(iter(fws))
    prof = dict(fws.get(aud) or {})
    prof.setdefault("audience_key", aud)
    prof["requested_audience"] = requested
    prof["has_framework"] = requested in fws
    prof.setdefault("label", AUDIENCE_CN.get(aud, aud))
    prof.setdefault("length_target", "15–25 屏")
    if aud == "management":
        prof.setdefault("max_kpi", 6)
        prof.setdefault("narrative_depth", "management")
        prof.setdefault("suppressed_topic_packs", ["industry_chain", "process", "price_history"])
    else:
        prof.setdefault("max_kpi", 8)
        prof.setdefault("narrative_depth", "research")
        prof.setdefault("suppressed_topic_packs", [])
    return prof


def visible_sections(case: dict, profile: dict) -> list:
    """筛选章节，规则依次为：
    1) 章节 pack 被该受众 suppressed_topic_packs 屏蔽 → 跳过
    2) 章节声明了 audience_weight 且不含该受众 → 跳过（受众专属章节）
    3) 否则保留，保持原顺序。
    结论章（pack=conclusion）永远保留。
    """
    suppressed = set(profile.get("suppressed_topic_packs") or [])
    aud = profile.get("audience_key")
    out = []
    for s in case.get("sections") or []:
        if s.get("pack") in suppressed and s.get("pack") != "conclusion":
            continue
        weights = s.get("audience_weight") or []
        if weights and aud and aud not in weights:
            continue
        out.append(s)
    return out


def build_payload(case: dict, profile: dict) -> dict:
    """"HTML 渲染所需的一个扁平数据包（模板只读这个对象）。"""
    src = source_index(case)
    confs = conclusion_index(case)
    sections = visible_sections(case, profile)
    datasets = {}
    datasets["projects_by_status"] = case.get("projects_by_status") or []
    datasets["add_waterfall"] = case.get("add_waterfall") or []
    datasets["supply_scenarios"] = case.get("supply_scenarios") or []
    datasets["capacity_structure"] = case.get("capacity_structure") or {}
    for pool_key in ("capacity_structure", "cr5", "cost_curve", "profit", "supply_demand",
                     "price_history", "price_points", "inventory", "output_weekly",
                     "demand_structure", "glass_runrate", "macro", "chain"):
        node = case.get(pool_key)
        if isinstance(node, dict):
            for sub in ("rows", "shares"):
                if isinstance(node.get(sub), list):
                    datasets["%s.%s" % (pool_key, sub)] = node[sub]
        elif isinstance(node, list):
            datasets[pool_key] = node
    kpi_max = int(profile.get("max_kpi") or 8)
    return {
        "meta": case.get("meta") or {},
        "profile": profile,
        "kpis": (case.get("kpis") or [])[:kpi_max],
        "conclusions": case.get("conclusions") or [],
        "calculations": calc_index(case),
        "sources": src,
        "gaps": gap_index(case),
        "sections": [{k: v for k, v in s.items()} for s in sections],
        "datasets": datasets,
        "projects": case.get("projects") or [],
        "companies": case.get("companies") or [],
        "key_variables": case.get("key_variables") or [],
        "glossary": case.get("glossary") or [],
        "brief": case.get("research_brief") or {},
        "questions": (case.get("research_brief") or {}).get("questions") or [],
        "frameworks": case.get("audience_frameworks") or {},
        "confs": list(confs.keys()),
    }


def default_filename(case: dict, audience: str, ext: str) -> str:
    m = case.get("meta") or {}
    base = "%s_%s_%s" % (m.get("product_cn", "专题"), AUDIENCE_CN.get(audience, audience),
                          m.get("slug") or m.get("report_date", ""))
    return re.sub(r'[\\/:*?"<>|\s]+', "_", base) + ext


AUDIENCE_CN = {
    "management": "管理层",
    "sales": "销售",
    "procurement": "采购",
    "rnd": "研发",
    "industry-researcher": "产业研究员",
}


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, path = argv[0], argv[1]
    case = load(path)
    if cmd == "validate":
        errs, warns = validate(case)
        for e in errs:
            print("ERROR", e)
        for w in warns:
            print("WARN ", w)
        print("RESULT", "FAIL" if errs else "PASS", "errors=%d warnings=%d" % (len(errs), len(warns)))
        return 1 if errs else 0
    if cmd == "audit":
        print(json.dumps(build_evidence_index(case), ensure_ascii=False, indent=1))
        return 0
    print("未知命令", cmd)
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
