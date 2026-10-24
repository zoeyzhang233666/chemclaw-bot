#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
self_check.py — 校验 case_output.json 是否符合数据契约与证据分级规则。

用法：
    python self_check.py path/to/case_output.json

退出码：0 = 通过；1 = 存在 ERROR。
WARN 不阻塞交付，但必须在报告中处理或说明。
"""
import json
import sys

MANUF_TYPES = {"MANUFACTURER", "JV_MANUFACTURER"}
ENTITY_TYPES = {"MANUFACTURER", "JV_MANUFACTURER", "GROUP_SALES", "AFFILIATE_SALES",
                "TRADER", "AGENT", "UNKNOWN"}
HARD_EVIDENCE_TYPES = {"装置级", "EPC", "官网产品页", "官网产能表", "官方新闻稿", "交易所", "官方公告"}
SOURCE_STATUS_OK = {"已核验"}
VENUE_HINT = ("mt/a", "kt/a", "kta", "mtpa", "t/a", "t/y", "吨", "万吨")


def check(path):
    errors, warns = [], []
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return ["无法解析 JSON: %s" % e], []

    for key in ("meta", "groups", "companies", "questions", "sources"):
        if key not in d:
            errors.append("缺少顶层字段: %s" % key)
    if errors:
        return errors, warns

    meta = d["meta"]
    for key in ("report_id", "title", "product", "evidence_grade_legend", "disclaimer"):
        if key not in meta:
            errors.append("meta 缺少字段: %s" % key)
    legend_grades = {x.get("grade") for x in meta.get("evidence_grade_legend", [])}
    if legend_grades != {"A", "B", "C", "D"}:
        errors.append("evidence_grade_legend 必须恰好覆盖 A/B/C/D，当前: %s" % sorted(legend_grades))

    src_ids = {s.get("id") for s in d["sources"]}
    if len(src_ids) != len(d["sources"]):
        errors.append("sources 存在重复 ID")
    q_ids = {q.get("id") for q in d["questions"]}
    if len(q_ids) != len(d["questions"]):
        errors.append("questions 存在重复 ID")
    group_ids = {g.get("id") for g in d["groups"]}

    for s in d["sources"]:
        if not str(s.get("url", "")).startswith("http"):
            errors.append("来源 %s 的 URL 非法: %s" % (s.get("id"), s.get("url")))
        if s.get("status") not in (SOURCE_STATUS_OK | {"检索索引命中", "直连失败", "待下载"}):
            warns.append("来源 %s 状态未标准化: %s" % (s.get("id"), s.get("status")))

    company_ids = set()
    for c in d["companies"]:
        cid = c.get("id")
        if not cid:
            errors.append("存在无 id 的企业")
            continue
        if cid in company_ids:
            errors.append("企业 ID 重复: %s" % cid)
        company_ids.add(cid)

        if not c.get("legal_name"):
            errors.append("%s 缺少 legal_name" % cid)
        if c.get("entity_type") not in ENTITY_TYPES:
            errors.append("%s entity_type 非法: %s" % (cid, c.get("entity_type")))
        if c.get("grade") not in ("A", "B", "C", "D"):
            errors.append("%s grade 非法: %s" % (cid, c.get("grade")))
        if not c.get("grade_reason") or len(str(c.get("grade_reason"))) < 10:
            errors.append("%s 缺少有效 grade_reason" % cid)
        if c.get("group") and c["group"] not in group_ids:
            errors.append("%s 的 group 未在 groups 中定义: %s" % (cid, c.get("group")))

        ev = c.get("evidence") or []
        if c.get("grade") == "A":
            if not ev:
                errors.append("%s 判为 A 但没有任何 evidence" % cid)
            else:
                hard = [e for e in ev if any(h in str(e.get("type", "")) for h in HARD_EVIDENCE_TYPES)]
                if not hard:
                    errors.append("%s 判为 A 但缺少硬证据类型（装置级/EPC/官网产品页/官方公告）" % cid)
                if not any(e.get("conf") in ("高",) for e in hard):
                    warns.append("%s 判为 A 但硬证据中没有『高』置信项，建议补充或降级" % cid)

        # 仅凭第三方名录/平台口号不得判 A
        for e in ev:
            t = str(e.get("type", ""))
            if ("名录" in t or "平台" in t or "第三方转述" in t) and c.get("grade") == "A":
                if not any(h in str(x.get("type", "")) for x in ev for h in HARD_EVIDENCE_TYPES):
                    pass  # 已在上方拦截
            if ("名录" in t or "平台挂牌" in t) and c.get("grade") in ("A", "B"):
                warns.append("%s 含平台/名录类证据（%s），不得作为唯一依据" % (cid, e.get("id")))

        for e in ev:
            if e.get("src") not in src_ids:
                errors.append("%s 的证据 %s 指向不存在的来源 %s" % (cid, e.get("id"), e.get("src")))
            if not e.get("text"):
                warns.append("%s 的证据 %s 没有原文摘要" % (cid, e.get("id")))

        for q in c.get("open_questions") or []:
            if q not in q_ids:
                errors.append("%s 引用了不存在的问题编号 %s" % (cid, q))

        cap = c.get("capacity") or {}
        if c.get("grade") in ("A", "B"):
            if not cap.get("detail"):
                errors.append("%s 缺少产能口径说明（detail）" % cid)
            if not cap.get("caveat"):
                warns.append("%s 缺少『当前可供货能力』判断（caveat）" % cid)

        if not (c.get("official_channels") or []):
            warns.append("%s 没有任何官方公开联系渠道" % cid)

        if c.get("grade") in ("C", "D") and c.get("entity_type") in MANUF_TYPES:
            pass  # 合法：近似品企业仍是制造企业，只是不生产目标品

    for q in d["questions"]:
        if q.get("company") not in company_ids and q.get("company") != "通用":
            errors.append("问题 %s 指向不存在的企业 %s" % (q.get("id"), q.get("company")))
        if not q.get("q"):
            errors.append("问题 %s 内容为空" % q.get("id"))

    # 统计
    grades = {}
    for c in d["companies"]:
        grades[c.get("grade")] = grades.get(c.get("grade"), 0) + 1
    print("[stats] companies=%d grades=%s questions=%d sources=%d"
          % (len(d["companies"]), grades, len(d["questions"]), len(d["sources"])))
    return errors, warns


def main():
    if len(sys.argv) < 2:
        print("用法: python self_check.py case_output.json")
        return 2
    errors, warns = check(sys.argv[1])
    for w in warns:
        print("[WARN ] " + w)
    for e in errors:
        print("[ERROR] " + e)
    print("\n结果: %s (errors=%d, warns=%d)" % ("PASS" if not errors else "FAIL", len(errors), len(warns)))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
