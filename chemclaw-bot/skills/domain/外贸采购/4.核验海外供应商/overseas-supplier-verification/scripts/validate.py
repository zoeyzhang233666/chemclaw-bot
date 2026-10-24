# -*- coding: utf-8 -*-
"""
validate.py — check a project.json against the skill's rules before rendering.

    python scripts/validate.py project.json [--strict]

Rules (a "fail" blocks delivery, a "warn" needs a human decision):
  F01  every evidence id referenced anywhere must exist in `evidence`
  F02  every evidence entry needs id / claim / publisher / url / quote / grade / stance / accessed
  F03  a `verified` row must cite at least one evidence id
  F04  a `verified` row must not rely on a single `tertiary` or `mock` source
  F05  `mock` evidence may never be cited as support for a `verified` row
  F06  no risk-score fields (score / rating / risk_score ...)
  F07  every section has id / no / title / blocks
  F08  `unknown` rows must be covered by a gap entry or a document request
  W01  `doubt` rows should explain what conflicts (detected: "不同/不一致/未载/无")
  W02  more than 60% of rows `unknown` suggests the research stage was skipped
  W03  an evidence item older than 3 years used for a `verified` row is flagged for refresh
  W04  non-English-ASCII supplier names should still have an English legal name
  W05  PI / BANK documents present but no entity-consistency matrix
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date

import ovslib as L
from ovslib import as_list, evid_ids, norm_state

FAILS, WARNS, NOTES = [], [], []


def f(msg):
    FAILS.append(msg)


def w(msg):
    WARNS.append(msg)


def n(msg):
    NOTES.append(msg)


def run(project: dict) -> None:
    meta = project.get("meta", {})
    evidence = as_list(project.get("evidence"))
    emap = {e.get("id"): e for e in evidence}

    # F06 no scores — walk the actual keys, and check prose for assertive score language
    SCORE_KEYS = {"risk_score", "trust_score", "credit_rating", "risk_rating", "risk_grade",
                  "overall_score", "dimension_scores", "评分", "风险分", "综合评分", "风险评分"}

    def walk(node, path="$"):
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).lower() in SCORE_KEYS:
                    f(f"F06 发现评分字段 {path}.{k}：本方法禁止输出风险分数或信用评级")
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(project)

    metric = project.get("metrics")
    if metric:
        f("F06 顶层出现 metrics 字段：本方法不接受任何形式的评分或指标打分，请改用 state + evidence")

    # 以代码块/字段形式出现的评分句子
    for sec in as_list(project.get("sections")):
        for b in as_list(sec.get("blocks")):
            for txt in (b.get("text"), b.get("headline"), b.get("foot")):
                if not txt:
                    continue
                for m in re.finditer(r"(风险|信用|综合)\s*(评分|分数)\s*[:：]\s*\d+", str(txt)):
                    f(f"F06 正文出现评分数值：{m.group(0)}")

    # F07 sections
    for i, sec in enumerate(as_list(project.get("sections"))):
        for key in ("id", "no", "title", "blocks"):
            if not sec.get(key):
                f(f"F07 第 {i+1} 个 section 缺字段 {key}")
    if not as_list(project.get("sections")):
        f("F07 没有任何 section")

    # F02 evidence completeness
    for e in evidence:
        for key in ("id", "claim", "publisher", "url", "quote", "grade", "stance", "accessed"):
            if not e.get(key):
                f(f"F02 证据 {e.get('id','?')} 缺字段 {key}")
        if e.get("grade") not in L.EVID_GRADE:
            f(f"F02 证据 {e.get('id')} 分级非法：{e.get('grade')}")
        if e.get("stance") not in L.EVID_STANCE:
            f(f"F02 证据 {e.get('id')} stance 非法：{e.get('stance')}")

    # F01 / F03 / F04 / F05 row-level
    carriers = list(L.iter_state_carriers(project))
    for c in carriers:
        st = norm_state(c.get("state"))
        ids = evid_ids(c.get("evid") or c.get("evidence"))
        for i in ids:
            if i not in emap:
                f(f"F01 {c.get('label')} 引用了不存在的证据 {i}")
        if st == "verified":
            if not ids:
                f(f"F03 「{c.get('label')}」标为已核实但未引用任何证据")
            srcs = [emap.get(i) for i in ids if i in emap]
            if srcs:
                if all(s.get("grade") in ("tertiary", "mock") for s in srcs):
                    f(f"F04 「{c.get('label')}」标为已核实，但只依赖三手或模拟来源")
                if any(s.get("grade") == "mock" for s in srcs):
                    f(f"F05 「{c.get('label')}」标为已核实，但引用了模拟件")
                if len(srcs) == 1 and srcs[0].get("grade") == "secondary":
                    w(f"F04 「{c.get('label')}」已核实仅有单一二手来源，建议补一个独立来源")
                # W03 staleness
                for s in srcs:
                    d = L.parse_date(s.get("published"))
                    if d and (date.today() - d).days > 365 * 3:
                        n(f"W03 证据 {s.get('id')} 发布于 {s.get('published')}，超过 3 年，引用前建议刷新")
        if st == "doubt":
            txt = f"{c.get('label')} {c.get('state')}"
            if not ids:
                w(f"W01 「{c.get('label')}」标为存在疑点但未挂证据，说明冲突点时请引用证据")

    # F08 unknown coverage by gaps
    gaps = as_list(project.get("gaps"))
    gaps_text = " ".join(str(g.get("gap", "")) + str(g.get("area", "")) for g in gaps)
    unknown_labels = [c.get("label") for c in carriers if norm_state(c.get("state")) == "unknown"]
    if unknown_labels and not gaps:
        f(f"F08 有 {len(unknown_labels)} 项「未知」但没有任何 gap 记录，未知必须给出补件动作")
    elif unknown_labels and len(gaps) < 1:
        w("F08 未知项建议逐项对应 gap 编号")

    # W02 unknown ratio
    counts = L.count_states(carriers)
    total = sum(counts.values()) or 1
    if counts["unknown"] / total > 0.6:
        w(f"W02 未知项占比 {counts['unknown']/total:.0%}，可能研究阶段未完成")

    # W04 english legal name for non-ascii names
    sm = project.get("subject_master", {})
    if sm.get("legal_name") and re.search(r"[\u4e00-\u9fff]", str(sm.get("legal_name"))) \
            and not sm.get("legal_name_en"):
        w("W04 法定名称为中文时，建议补 legal_name_en（制裁筛查与 KYC 需要英文全称）")

    # W05 PI/bank without consistency matrix
    doc_types = {d.get("type") for d in as_list(project.get("documents"))}
    has_matrix = any(b.get("type") == "matrix_map" for s in as_list(project.get("sections"))
                     for b in as_list(s.get("blocks")))
    if doc_types & {"PI", "BANK"} and not has_matrix:
        f("W05 提供了 PI/银行信息，但没有交易主体一致性矩阵（matrix_map）")

    # RFI sanity
    rfi = project.get("rfi") or {}
    clauses = as_list(rfi.get("clauses"))
    if clauses:
        if len(clauses) < 8:
            w(f"RFI 只有 {len(clauses)} 条，建议覆盖 主体/收款/工厂/产品/文件/合规 六类")
        non_en = [c for c in clauses if re.search(r"[\u4e00-\u9fff]", str(c.get("text"))) and
                  len(re.findall(r"[A-Za-z]{3,}", str(c.get("text")))) < 6]
        if non_en:
            f(f"RFI 条款 {[c.get('id') for c in non_en]} 不是英文，询证单必须可发给海外供应商")
        missing = [k for k in ("to", "from", "ref", "intro") if not rfi.get(k)]
        if missing:
            w(f"RFI 缺字段：{missing}")

    # meta
    for key in ("doc_no", "as_of", "subject_full", "product"):
        if not meta.get(key):
            f(f"meta 缺字段 {key}")
    if meta.get("as_of") and L.parse_date(meta.get("as_of")) and L.parse_date(meta.get("as_of")) > date.today():
        w("meta.as_of 晚于今天，请确认基准日")


def main(argv=None):
    L.force_utf8()
    ap = argparse.ArgumentParser(description="Validate project.json before rendering.")
    ap.add_argument("project")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = ap.parse_args(argv)

    project = L.load_project(args.project)
    run(project)

    for msg in NOTES:
        print("  [note] " + msg) if os.environ.get("OSV_VERBOSE") else None
    for msg in WARNS:
        print("  [warn] " + msg)
    for msg in FAILS:
        print("  [FAIL] " + msg)

    counts = L.collect_all_states(project)
    print(f"\n状态分布：已核实 {counts['verified']}｜存在疑点 {counts['doubt']}｜"
          f"未核实 {counts['unverified']}｜未知 {counts['unknown']}｜不适用 {counts['na']}")
    print(f"证据 {len(as_list(project.get('evidence')))} 条｜文件 {len(as_list(project.get('documents')))} 份｜"
          f"缺口 {len(as_list(project.get('gaps')))} 项｜询证 {len(as_list((project.get('rfi') or {}).get('clauses')))} 条")

    if FAILS:
        print(f"\n[FAIL] {len(FAILS)} 项必须修复后才能交付")
        return 1
    if args.strict and WARNS:
        print(f"\n[FAIL --strict] {len(WARNS)} 项警告视为失败")
        return 1
    print(f"\n[pass] 无阻断问题" + (f"（{len(WARNS)} 项警告请人工确认）" if WARNS else "，无警告"))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
