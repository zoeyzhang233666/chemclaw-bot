#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_chain.py — 化工产业链数据包校验 + 覆盖完整度 + 布局自检

用法：
    python validate_chain.py --data-dir ../examples/sbs/data [--out-json report.json] [--quiet]
    python validate_chain.py --data-dir ... --no-layout      # 跳过布局自检

校验项（FATAL 阻断交付 / WARN 记入缺口）：
  1 SCHEMA      必需文件、字段、ID 唯一、外键可解析
  2 EVIDENCE    证据引用必须存在；量化关系必须有证据；D 级来源不得支撑量化
  3 FORBIDDEN   命中 forbidden_links（把终端用途写成转化产品等）=> FATAL
  4 CLASS       材料/终端节点不得带 CAS（禁止编造）；只有 commodity 可验证 CAS
  5 QUANT       有数值必须有 basis / basis_grade / from_unit
  6 CYCLE       转化-副产-联产边构成有向环 => FATAL
  7 DEPTH       column 单调性（物质流边必须严格递增）
  8 COVERAGE    按预冻结 core_checklist 逐项判定
  9 LAYOUT      节点重叠 / 越界 / 边穿节点 / 斜线段 => FATAL（否则图不可读）

作为模块使用时：
    import validate_chain as V
    doc = V.load_all(data_dir)
    cov = V.compute_coverage(doc)
    rep = V.run(doc, layout=True)
"""

import argparse
import io
import json
import os
import sys
from collections import defaultdict

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

QUANT_TYPES = {"conversion", "coproduction", "byproduct"}
NON_GRAPH_CLASSES = {"route", "utility"}
QUANT_STATUSES = {
    "stoichiometric", "stoichiometric_derived", "commercial_grade", "formulation",
    "industrial_range_literature", "byproduct_yield_range", "stoichiometric_plus_textbook",
    "industrial_estimate_range",
}
NON_QUANT_STATUSES = {"not_applicable", "missing"}
# 允许「层数不递增」的关系类型（配方归属、同一层内的配方共混、终端应用汇总）
NON_MONO_TYPES = {"blend", "processing", "application", "substitution", "packaging"}

REQUIRED_FILES = ["meta.json", "nodes.json", "relations.json",
                  "core_checklist.json", "sources.json"]

TEMPLATE_VALUES = {"", "待补", "TBD", "todo", "TODO", "示例", "demo", "占位", "演示"}


class Result:
    def __init__(self):
        self.fatal, self.warn, self.info = [], [], []

    def f(self, code, msg):
        self.fatal.append({"code": code, "msg": msg})

    def w(self, code, msg):
        self.warn.append({"code": code, "msg": msg})

    def i(self, msg):
        self.info.append(msg)


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all(data_dir):
    d = data_dir
    doc = {
        "dir": d,
        "meta": load_json(os.path.join(d, "meta.json"), {}) or {},
        "nodes_doc": load_json(os.path.join(d, "nodes.json"), {"nodes": []}) or {"nodes": []},
        "rels_doc": load_json(os.path.join(d, "relations.json"), {"relations": []}) or {"relations": []},
        "core": load_json(os.path.join(d, "core_checklist.json"), {}) or {},
        "sources_doc": load_json(os.path.join(d, "sources.json"), {"sources": []}) or {"sources": []},
        "forbidden_doc": load_json(os.path.join(d, "forbidden_links.json"), {"forbidden": []}) or {"forbidden": []},
        "prices": load_json(os.path.join(d, "prices_verified.json"), {}) or {},
        "enterprises": load_json(os.path.join(d, "enterprises.json"), {"enterprises": []}) or {"enterprises": []},
        "projects": load_json(os.path.join(d, "projects.json"), {"projects": []}) or {"projects": []},
        "events": load_json(os.path.join(d, "events.json"), {"events": []}) or {"events": []},
        "processes": load_json(os.path.join(d, "processes.json"), {"processes": []}) or {"processes": []},
        "price_series": load_json(os.path.join(d, "price_series.json"), {"series": []}) or {"series": []},
        "missing_files": [fn for fn in REQUIRED_FILES if not os.path.exists(os.path.join(d, fn))],
    }
    doc["nodes"] = list(doc["nodes_doc"].get("nodes") or [])
    doc["relations"] = list(doc["rels_doc"].get("relations") or [])
    doc["sources"] = {s.get("id"): s for s in (doc["sources_doc"].get("sources") or [])}
    doc["columns"] = doc["nodes_doc"].get("columns") or []
    doc["node_by_id"] = {}
    for n in doc["nodes"]:
        if n.get("column") is None and n.get("layer") is not None:
            n["column"] = n["layer"]
        doc["node_by_id"][n.get("id")] = n
    return doc


# ------------------------------------------------------------------ 覆盖率
def compute_coverage(doc_or_core, node_by_id=None, rels=None, sources=None, r=None):
    """兼容两种调用：compute_coverage(doc) 或 compute_coverage(CORE, nodes, rels, src, r)。"""
    if node_by_id is None:
        doc = doc_or_core
        CORE = doc.get("core") or {}
        node_by_id = doc.get("node_by_id") or {}
        rels = doc.get("relations") or []
        sources = doc.get("sources") or {}
        pv = doc.get("prices") or {}
        priced = {s.get("node_id") for s in (pv.get("series") or []) if s.get("points")}
        for nid, n in node_by_id.items():
            if nid in priced:
                n["price_mapped_ok"] = True
    else:
        CORE = doc_or_core

    def find_rel(fr, to):
        return next((x for x in rels if x.get("from") == fr and x.get("to") == to), None)

    crit_nodes = []
    for item in CORE.get("core_nodes", []):
        nid = item["node_id"]
        n = node_by_id.get(nid)
        failed = []
        for c in item.get("required_criteria", []):
            ok, detail = True, ""
            if c == "node_present":
                ok = n is not None
            elif c == "identity_verified":
                cas = (n or {}).get("cas") or {}
                ok = n is not None and cas.get("status") in ("verified", "不适用")
                detail = "" if ok else "CAS 状态=%s" % cas.get("status")
            elif c == "role_classified":
                ok = n is not None and bool(n.get("segment")) and n.get("column") is not None
            elif c == "evidence_linked":
                ok = n is not None and bool(n.get("evidence")) and any(
                    (sources.get(s) or {}).get("tier", "Z") in ("A", "B", "C") for s in n.get("evidence", []))
                detail = "" if ok else "节点未挂 A~C 级证据"
            elif c == "price_mapped":
                ok = n is not None and (n.get("price_mapped_ok") is True or bool(n.get("price_mapped_note")))
            elif c == "capacity_mapped":
                ok = n is not None and (n.get("capacity_mapped_ok") is True or bool(n.get("capacity_mapped_note")))
            if not ok:
                failed.append(c + ("：" + detail if detail else ""))
        crit_nodes.append({"core_id": item["id"], "label": item.get("label"), "node_id": nid,
                           "priority": item.get("priority"), "pass": not failed, "failed": failed})

    crit_rels = []
    for item in CORE.get("core_relations", []):
        rel = find_rel(item["from"], item["to"])
        failed = []
        for c in item.get("required_criteria", []):
            ok = True
            if c == "node_present":
                ok = item["from"] in node_by_id and item["to"] in node_by_id
            elif c == "direction_verified":
                ok = rel is not None
            elif c == "quant_available":
                if rel is None:
                    ok = False
                else:
                    qs, q = rel.get("quant_status"), (rel.get("quant") or {})
                    if rel.get("relation_type") in QUANT_TYPES:
                        ok = (qs in QUANT_STATUSES
                              and (q.get("from_per_to") is not None or q.get("yield") is not None))
                    else:
                        ok = qs is not None and qs != "missing"
            elif c == "evidence_linked":
                ok = rel is not None and bool(rel.get("evidence"))
            if not ok:
                failed.append(c)
        crit_rels.append({"core_id": item["id"], "label": item.get("label"),
                          "from": item["from"], "to": item["to"],
                          "rel_id": rel["id"] if rel else None,
                          "priority": item.get("priority"), "pass": not failed, "failed": failed})

    def pack(items):
        by_p = defaultdict(lambda: [0, 0])
        for it in items:
            p = it.get("priority") or "P1"
            by_p[p][1] += 1
            if it["pass"]:
                by_p[p][0] += 1
        return {p: {"passed": v[0], "total": v[1]} for p, v in sorted(by_p.items())}

    npass = sum(1 for x in crit_nodes if x["pass"])
    rpass = sum(1 for x in crit_rels if x["pass"])
    tot = len(crit_nodes) + len(crit_rels)
    passed = npass + rpass
    return {
        "definition": "覆盖率 = 逐项判定通过的核心清单条目 / 预先冻结的核心清单条目；节点与关系合计计入，不按条数加权。",
        "scenario": (CORE.get("meta") or {}).get("scope_statement", ""),
        "nodes": {"passed": npass, "total": len(crit_nodes),
                  "rate": round(100.0 * npass / max(1, len(crit_nodes)), 1),
                  "by_priority": pack(crit_nodes), "detail": crit_nodes},
        "relations": {"passed": rpass, "total": len(crit_rels),
                      "rate": round(100.0 * rpass / max(1, len(crit_rels)), 1),
                      "by_priority": pack(crit_rels), "detail": crit_rels},
        "overall": {"passed": passed, "total": tot,
                    "rate": round(100.0 * passed / max(1, tot), 1)},
    }


# ------------------------------------------------------------------ 主校验
def run(doc, layout=True):
    r = Result()
    nodes, rels = doc["nodes"], doc["relations"]
    sources, node_by_id = doc["sources"], doc["node_by_id"]

    for fn in doc["missing_files"]:
        r.f("SCHEMA_FILE_MISSING", "缺少必需文件 %s" % fn)
    if r.fatal:
        return {"ok": False, "fatal": r.fatal, "warn": r.warn, "info": r.info,
                "coverage": compute_coverage(doc), "counts": {}}

    # ---- 5/2 逐条关系 ----
    seen = set()
    for rel in rels:
        rid = rel.get("id")
        if rid in seen:
            r.f("SCHEMA_DUP_REL", "关系 id 重复：%s" % rid)
        seen.add(rid)
        for k in ("from", "to", "relation_type"):
            if not rel.get(k):
                r.f("SCHEMA_REL_FIELD", "关系 %s 缺字段 %s" % (rid, k))
        if rel.get("from") not in node_by_id:
            r.f("SCHEMA_FK", "关系 %s 的 from 节点不存在：%s" % (rid, rel.get("from")))
            continue
        if rel.get("to") not in node_by_id:
            r.f("SCHEMA_FK", "关系 %s 的 to 节点不存在：%s" % (rid, rel.get("to")))
            continue
        ev = rel.get("evidence") or []
        for sid in ev:
            if sid not in sources:
                r.f("EVIDENCE_FK", "关系 %s 引用不存在的来源 %s" % (rid, sid))
        qs = rel.get("quant_status")
        q = rel.get("quant") or {}
        if qs in QUANT_STATUSES:
            if not ev:
                r.f("EVIDENCE_MISSING", "量化关系 %s（%s）未挂任何证据" % (rid, qs))
            for sid in ev:
                s = sources.get(sid) or {}
                if s.get("tier") == "D":
                    r.f("EVIDENCE_TIER_D", "量化关系 %s 依赖 D 级来源 %s" % (rid, sid))
            if q.get("from_per_to") is None and q.get("yield") is None:
                r.w("QUANT_EMPTY", "关系 %s 标记为 %s 但单耗与收率均为空，应改标 missing" % (rid, qs))
            else:
                if not q.get("basis"):
                    r.f("QUANT_BASIS_MISSING", "量化关系 %s 有数值但缺计算口径 basis" % rid)
                if not q.get("basis_grade"):
                    r.f("QUANT_GRADE_MISSING", "量化关系 %s 有数值但缺规格基准 basis_grade" % rid)
                if not q.get("from_unit"):
                    r.f("QUANT_UNIT_MISSING", "量化关系 %s 有数值但缺单位 from_unit" % rid)
        elif qs not in NON_QUANT_STATUSES:
            r.w("QUANT_STATUS_UNKNOWN", "关系 %s 的 quant_status=%s 不在词表中" % (rid, qs))
        if rel.get("relation_type") in QUANT_TYPES and qs == "not_applicable":
            r.f("QUANT_TYPE_NA", "关系 %s 是 %s 却标 not_applicable" % (rid, rel.get("relation_type")))

    # ---- 4 节点 ----
    for n in nodes:
        cls = n.get("node_class")
        if cls not in ("commodity", "material", "application", "route", "utility"):
            r.f("NODE_CLASS", "节点 %s 的 node_class=%s 非法" % (n.get("id"), cls))
        cas = n.get("cas") or {}
        if cls in ("material", "application") and cas.get("value") and cas.get("value") not in ("不适用", "N/A"):
            r.f("NODE_CAS_FAKE", "%s 节点 %s 不应有 CAS：%s" % (cls, n.get("id"), cas.get("value")))
        if cls in ("material", "application") and not cas.get("value"):
            r.w("NODE_CAS_UNSET", "节点 %s 应显式标注 CAS 状态为『不适用』" % n.get("id"))
        if cls == "commodity" and cas.get("status") == "verified" and not cas.get("value"):
            r.f("NODE_CAS_EMPTY", "商品节点 %s 标 verified 但无 CAS 值" % n.get("id"))
        for k in ("name", "segment", "column"):
            if k not in n:
                r.f("NODE_FIELD", "节点 %s 缺字段 %s" % (n.get("id"), k))
        if not isinstance(n.get("missing_flags"), list):
            r.f("NODE_FLAGS", "节点 %s 的 missing_flags 必须是数组" % n.get("id"))
        # 证据质量
        ev = n.get("evidence") or []
        if not ev:
            r.w("NODE_EVIDENCE_MISSING", "节点 %s（%s）未挂任何证据" % (n.get("id"), n.get("name")))
        for sid in ev:
            s = sources.get(sid)
            if not s:
                r.f("EVIDENCE_FK", "节点 %s 引用不存在的来源 %s" % (n.get("id"), sid))
            elif (s.get("verified") in ("snippet_only", "opened_title_only")):
                r.w("EVIDENCE_SHALLOW", "节点 %s 的证据 %s 仅为摘要/标题级" % (n.get("id"), sid))
        # 占位值
        for fld in ("name", "segment", "unit"):
            v = n.get(fld)
            if isinstance(v, str) and v.strip() in TEMPLATE_VALUES:
                r.f("TEMPLATE_LEAK", "节点 %s 的 %s 仍是占位值（%s）" % (n.get("id"), fld, v))

    # ---- 3 forbidden ----
    idx = defaultdict(list)
    for rel in rels:
        idx[(rel.get("from"), rel.get("to"))].append(rel)
    for fb in doc["forbidden_doc"].get("forbidden", []):
        hit = idx.get((fb["from"], fb["to"]), []) + (
            idx.get((fb["to"], fb["from"]), []) if "substitution" in (fb.get("wrong_types") or []) else [])
        for rel in hit:
            if rel.get("relation_type") in (fb.get("wrong_types") or []):
                r.f("FORBIDDEN_LINK", "%s：%s→%s 类型 %s 被禁止（%s）" %
                    (fb.get("id"), fb["from"], fb["to"], rel.get("relation_type"), fb.get("why", "")))
            elif "copy" in (fb.get("wrong_types") or []):
                # 「方向存疑」类：只告警，不阻断
                r.w("FORBIDDEN_SUSPECT", "%s：%s→%s 方向存疑（%s）" %
                    (fb.get("id"), fb["from"], fb["to"], fb.get("why", "")))

    # ---- 6 环 ----
    graph = defaultdict(list)
    for rel in rels:
        if rel.get("relation_type") in QUANT_TYPES:
            graph[rel["from"]].append(rel["to"])
    state = {}

    def dfs(u, stack):
        state[u] = 1
        for v in graph.get(u, []):
            if state.get(v) == 1:
                r.f("CYCLE", "转化/副产/联产边构成有向环：%s" % " → ".join(stack + [v]))
            elif state.get(v) is None:
                dfs(v, stack + [v])
        state[u] = 2

    for n in list(graph.keys()):
        if state.get(n) is None:
            dfs(n, [n])

    # ---- 7 column 单调性 ----
    for rel in rels:
        rt = rel.get("relation_type")
        if rt in NON_MONO_TYPES:
            continue
        a, b = node_by_id[rel["from"]], node_by_id[rel["to"]]
        if a.get("column") is None or b.get("column") is None:
            r.w("DEPTH_UNKNOWN", "关系 %s 端点缺 column" % rel.get("id"))
            continue
        if not (a["column"] < b["column"]):
            r.w("DEPTH_INCONSISTENT", "关系 %s：上游 %s(列 %s) 未严格浅于下游 %s(列 %s)" %
                (rel.get("id"), a["id"], a["column"], b["id"], b["column"]))

    # ---- 其他结构检查 ----
    if not doc["core"].get("core_nodes"):
        r.f("CORE_MISSING", "core_checklist.json 缺少 core_nodes，无法计算覆盖完整度")
    if not (doc["core"].get("meta") or {}).get("scope_statement"):
        r.w("CORE_SCOPE", "core_checklist 未写 scope_statement（覆盖口径声明）")
    # 材料/终端节点不允许出现在上游（column 必须 >= 目标品种列）
    target_cols = [n["column"] for n in nodes if n.get("node_role") == "target"]
    if target_cols:
        tc = min(target_cols)
        for n in nodes:
            if n.get("node_class") in ("material", "application") and n.get("column") is not None \
                    and n["column"] < tc:
                r.f("NODE_ROLE_CONFLICT", "材料/终端节点 %s 位于目标品种上游（列 %s < %s）" %
                    (n.get("id"), n["column"], tc))

    # ---- 9 布局 ----
    layout_counts = None
    if layout:
        try:
            import chain_layout as CL
            rep = CL.layout_report(nodes, rels)
            layout_counts = rep["counts"]
            if layout_counts.get("overlap"):
                r.f("LAYOUT_OVERLAP", "布局存在 %d 处节点重叠" % layout_counts["overlap"])
            if layout_counts.get("outside"):
                r.f("LAYOUT_OUTSIDE", "布局存在 %d 个越界节点" % layout_counts["outside"])
            if layout_counts.get("edge_through_node"):
                r.f("LAYOUT_EDGE_CROSS", "有 %d 处连线穿过节点" % layout_counts["edge_through_node"])
            if layout_counts.get("diagonal"):
                r.f("LAYOUT_DIAGONAL", "存在 %d 段斜线（应全为正交走线）" % layout_counts["diagonal"])
            if layout_counts.get("edge_collinear"):
                r.w("LAYOUT_COLLINEAR", "%d 对连线的垂直段重合" % layout_counts["edge_collinear"])
        except Exception as e:  # noqa: BLE001
            r.w("LAYOUT_SKIPPED", "布局自检异常：%s" % e)

    cov = compute_coverage(doc)
    out = {
        "chain_id": (doc["meta"] or {}).get("chain_id"),
        "counts": {
            "nodes": len(nodes), "relations": len(rels), "sources": len(sources),
            "graph_nodes": len([n for n in nodes if n.get("node_class") not in NON_GRAPH_CLASSES]),
            "graph_relations": len(rels),
            "layout": layout_counts,
        },
        "coverage": cov,
        "fatal": r.fatal, "warn": r.warn, "info": r.info,
        "ok": len(r.fatal) == 0,
    }
    return out


def emit(out, quiet=False):
    if quiet:
        return
    print("=" * 74)
    c = out.get("counts") or {}
    if c:
        print("链路：%s   节点 %d（图谱内 %d）  关系 %d  来源 %d" %
              (out.get("chain_id"), c["nodes"], c["graph_nodes"], c["relations"], c["sources"]))
        if c.get("layout"):
            lc = c["layout"]
            print("布局：重叠 %d · 越界 %d · 穿线 %d · 斜线 %d · 共线 %d · 绕行 %d" %
                  (lc.get("overlap", 0), lc.get("outside", 0), lc.get("edge_through_node", 0),
                   lc.get("diagonal", 0), lc.get("edge_collinear", 0), lc.get("detour", 0)))
    cov = out.get("coverage") or {}
    if cov.get("overall"):
        print("覆盖完整度：%.1f%% （%d/%d；节点 %d/%d，关系 %d/%d）" % (
            cov["overall"]["rate"], cov["overall"]["passed"], cov["overall"]["total"],
            cov["nodes"]["passed"], cov["nodes"]["total"],
            cov["relations"]["passed"], cov["relations"]["total"]))
    if out.get("warn"):
        print("-" * 74)
        print("WARN %d 条：" % len(out["warn"]))
        for w in out["warn"][:40]:
            print("  [%s] %s" % (w["code"], w["msg"]))
        if len(out["warn"]) > 40:
            print("  ... 其余 %d 条省略" % (len(out["warn"]) - 40))
    print("-" * 74)
    if out.get("fatal"):
        print("FATAL %d 条（阻断交付）：" % len(out["fatal"]))
        for f in out["fatal"]:
            print("  [%s] %s" % (f["code"], f["msg"]))
        print("结果：FAIL")
    else:
        print("结果：PASS")
    print("=" * 74)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--no-layout", action="store_true")
    ap.add_argument("--strict", action="store_true", help="WARN 也视为失败（CI 用）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    doc = load_all(args.data_dir)
    out = run(doc, layout=not args.no_layout)
    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    emit(out, args.quiet)
    if out["fatal"]:
        return 1
    if args.strict and out["warn"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
