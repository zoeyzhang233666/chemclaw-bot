# -*- coding: utf-8 -*-
"""
build_md.py —— 从 case.json 生成两类 Markdown：

  1) --kind outline   研究提纲（待确认 / 已确认），用于"先出提纲再研究"的工作流
  2) --kind record    执行记录：研究过程、数据采集、变更、自检、剩余缺口
  3) --kind report    完整文字稿（便于放进 Word / 飞书 / 邮件）

用法
----
  python build_md.py outline <case.json> --out 提纲.md [--status confirmed]
  python build_md.py record  <case.json> --out 执行记录.md
  python build_md.py report  <case.json> --out 报告.md [--audience management]
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

TYPE_MARK = {"事实": "【事实】", "计算": "【计算】", "解释": "【解释】", "判断": "【判断】"}


def _h(level, text):
    return "#" * level + " " + text


def _table(headers, rows):
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join(" --- " for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v).replace("|", "／").replace("\n", " ")
                                     for v in r) + " |")
    return out


# --------------------------------------------------------------------------
def build_outline(case, status="draft", audience=None):
    meta = case.get("meta") or {}
    prof = C.audience_profile(case, audience)
    key = prof.get("audience_key")
    fw = (case.get("audience_frameworks") or {}).get(key) or {}
    brief = case.get("research_brief") or {}
    L = []
    L.append(_h(1, "%s｜研究提纲（%s）" % (meta.get("title", ""), "已确认" if status == "confirmed" else "待确认")))
    L.append("")
    L += _table(["项目", "内容"], [
        ["受众", "%s（%s）" % (prof.get("label", ""), key)],
        ["研究范围", meta.get("horizon", "")],
        ["数据截止", meta.get("data_cutoff", "")],
        ["提纲版本", "%s / %s" % (meta.get("version", ""), datetime.date.today().isoformat())],
        ["状态", "已确认，进入研究阶段" if status == "confirmed" else "**待确认：请逐章确认、增删或调整顺序后再开始研究**"],
    ])
    L.append("")
    if fw.get("positioning"):
        L.append(_h(2, "一、这一版提纲为谁写"))
        L.append("")
        L.append(fw["positioning"])
        L.append("")
    L.append(_h(2, "二、要回答的核心问题"))
    L.append("")
    qs = brief.get("questions") or []
    if qs:
        # 检索方向：优先用题目自带的 search_hint；否则用各章“依赖数据”里与问题关键词重合的条目
        chapter_data = []
        for ch in fw.get("chapters") or []:
            for d in ch.get("data") or []:
                if d not in chapter_data:
                    chapter_data.append(d)

        def hint_for(q):
            if q.get("search_hint"):
                return "、".join(q["search_hint"])
            text = q.get("question", "")
            toks = [t for t in ("产能", "结构", "企业", "集中度", "投产", "项目", "供给", "需求",
                                "价格", "库存", "成本", "出口", "工艺", "区域", "退出")
                    if t in text]
            hits = [d for d in chapter_data if any(t in d for t in toks)]
            return "、".join(hits[:3]) if hits else "（沿用本章依赖数据）"

        L += _table(["#", "问题", "为什么问（回答状态说明）", "检索方向"],
                    [[q.get("id"), q.get("question"),
                      q.get("why") or q.get("note", ""), hint_for(q)] for q in qs])
    L.append("")
    if brief.get("scope_in") or brief.get("scope_out"):
        L.append(_h(2, "三、范围界定"))
        L.append("")
        L.append("**纳入**：" + "；".join(brief.get("scope_in") or []))
        L.append("")
        L.append("**不纳入**：" + "；".join(brief.get("scope_out") or []))
        L.append("")
    L.append(_h(2, "四、章节设计（每章都写清：为什么存在 / 要验证什么 / 依赖哪些数据）"))
    L.append("")
    for c in fw.get("chapters") or []:
        L.append(_h(3, "%s %s" % (c.get("no"), c.get("title"))))
        L.append("")
        L.append("- **要回答的问题**：%s" % c.get("question", ""))
        L.append("- **为什么需要这一章**：%s" % c.get("why", ""))
        L.append("- **它要验证/证伪什么**：%s" % c.get("verify", ""))
        L.append("- **依赖数据**：%s" % "、".join(c.get("data") or []))
        L.append("- **方法**：%s" % c.get("method", ""))
        if c.get("risk"):
            L.append("- **风险**：%s" % c.get("risk"))
        L.append("")
    L.append(_h(2, "五、需要的资料清单（按优先级）"))
    L.append("")
    dl = fw.get("data_list") or brief.get("data_list") or []
    if dl:
        L += _table(["优先级", "资料", "预期来源", "拿不到的替代方案"],
                    [[d.get("priority"), d.get("item"), d.get("expected_source", ""), d.get("fallback", "")]
                     for d in dl])
    else:
        L.append("（见各章“依赖数据”一栏）")
    L.append("")
    L.append(_h(2, "六、口径与判据（先定规则，再看数）"))
    L.append("")
    for n in case.get("method_notes") or []:
        L.append("- **%s**：%s" % (n.get("topic") or n.get("id", ""), n.get("rule") or n.get("text", "")))
    L.append("")
    if fw.get("suppressed_topic_packs"):
        L.append(_h(2, "七、本版有意不写的章节"))
        L.append("")
        L.append("以下章节包对本受众优先级低，本版不写（如需要可加入）：" +
                 "、".join(C.SECTION_PACKS.get(p, p) for p in fw["suppressed_topic_packs"]))
        L.append("")
    L.append(_h(2, "八、交付物"))
    L.append("")
    L += _table(["交付物", "说明"], [
        ["交互式 HTML 报告", "首屏核心结论与指标；结论可点开证据与计算；图表可点开原始数据；章节可拖动排序；可导出"],
        ["Excel 数据底稿", "13 页：证据索引、原始数据、企业产能、项目台账、价格、产业指标、计算、结论、关键变量、缺口、大纲、自检"],
        ["已确认提纲", "本文件（确认后归档）"],
        ["执行记录", "研究过程、口径变更、自检结果与剩余缺口"],
    ])
    L.append("")
    L.append("---")
    L.append(meta.get("disclaimer", ""))
    return "\n".join(L)


def build_record(case, audience=None):
    meta = case.get("meta") or {}
    prof = C.audience_profile(case, audience)
    errs, warns = C.validate(case)
    L = []
    L.append(_h(1, "%s｜执行记录" % meta.get("title", "")))
    L.append("")
    L.append("> 本记录用于回答：这份报告是怎么做出来的、哪些地方改过、还有什么没核实。")
    L.append("")
    L.append(_h(2, "一、基本信息"))
    L.append("")
    L += _table(["项目", "内容"], [
        ["报告标题", meta.get("title", "")],
        ["受众", prof.get("label", "")],
        ["报告日 / 数据截止", "%s / %s" % (meta.get("report_date", ""), meta.get("data_cutoff", ""))],
        ["研究范围", meta.get("horizon", "")],
        ["记录生成时间", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["case 校验", "错误 %d · 警告 %d" % (len(errs), len(warns))],
    ])
    L.append("")
    L.append(_h(2, "二、研究流程与阶段产出"))
    L.append("")
    stages = [
        ["1. 界定问题", "从标题拆出可回答的子问题；划清纳入/不纳入", "research_brief.questions %d 条" % len((case.get("research_brief") or {}).get("questions") or [])],
        ["2. 写提纲", "按受众选定章节包，逐章写“为什么/验证什么/依赖数据”", "audience_frameworks.%s %d 章" % (prof.get("audience_key"), len(((case.get("audience_frameworks") or {}).get(prof.get("audience_key")) or {}).get("chapters") or []))],
        ["3. 提纲确认", "用户确认后进入研究；本章节顺序可调整", "已确认提纲见同名 .md"],
        ["4. 取证", "优先公告、统计、协会数据；行业媒体作交叉验证", "来源 %d 条（A 级 %d 条）" % (len(case.get("sources") or []), sum(1 for s in case.get("sources") or [] if s.get("tier") == "A"))],
        ["5. 项目核验", "逐个项目判断已投产/在建/规划/退出，写清依据", "项目 %d 个" % len(case.get("projects") or [])],
        ["6. 测算", "把“预计投产”折算为“有效新增供给”，参数全部写出口径", "计算 %d 条" % len(case.get("calculations") or [])],
        ["7. 成文", "结论分级（事实/计算/解释/判断）+ 置信度 + 反证条件", "结论 %d 条" % len(case.get("conclusions") or [])],
        ["8. 自检与交付", "校验引用完整性、缺口登记、数量约束；生成 HTML/Excel", "自检 16 项"],
    ]
    L += _table(["阶段", "做了什么", "产出"], stages)
    L.append("")
    L.append(_h(2, "三、数据口径与冲突处理"))
    L.append("")
    for n in case.get("method_notes") or []:
        L.append("- **%s**：%s" % (n.get("topic") or n.get("id", ""), n.get("rule") or n.get("text", "")))
    L.append("")
    L.append(_h(2, "四、关键判断的形成过程"))
    L.append("")
    for c in case.get("conclusions") or []:
        L.append(_h(3, "%s. %s" % (c.get("rank"), (c.get("text") or "")[:60] + ("…" if len(c.get("text") or "") > 60 else ""))))
        L.append("")
        L.append("- **结论**：%s" % c.get("text"))
        L.append("- **类型 / 置信度**：%s / %s" % (c.get("type"), c.get("confidence")))
        L.append("- **依据**：证据 %s；计算 %s" % ("、".join(c.get("evidence") or []),
                                                "、".join(c.get("calcs") or []) or "无"))
        L.append("- **反证条件**：%s" % (c.get("falsify") or "—"))
        L.append("")
    L.append(_h(2, "五、没有查到、也没有估算的数据"))
    L.append("")
    L += _table(["ID", "主题", "缺什么", "为什么缺", "对结论的影响", "下一步"],
                [[g.get("id"), g.get("topic"), g.get("missing"), g.get("why"),
                  g.get("impact"), g.get("next_step")] for g in case.get("data_gaps") or []])
    L.append("")
    L.append(_h(2, "六、自检结果"))
    L.append("")
    rows = []
    rows.append(["case 结构校验", "PASS" if not errs else "FAIL", "错误 %d / 警告 %d" % (len(errs), len(warns))])
    idx = C.build_evidence_index(case)
    unused = [e["id"] for e in idx if e["kind"] == "source" and not e["refs"]]
    missing = [e["id"] for e in idx if e["kind"] == "missing"]
    rows.append(["来源均被引用", "PASS" if not unused else "FAIL", "、".join(unused) or "全部被引用"])
    rows.append(["引用均已登记", "PASS" if not missing else "FAIL", "、".join(missing) or "全部已登记"])
    conc = case.get("conclusions") or []
    rows.append(["结论均有证据", "PASS" if all(c.get("evidence") for c in conc) else "FAIL", "%d 条" % len(conc)])
    rows.append(["判断/解释有反证条件",
                 "PASS" if all(c.get("falsify") for c in conc if c.get("type") in ("判断", "解释")) else "FAIL",
                 "判断 %d / 解释 %d" % (sum(1 for c in conc if c.get("type") == "判断"),
                                       sum(1 for c in conc if c.get("type") == "解释"))])
    L += _table(["检查项", "结果", "说明"], rows)
    L.append("")
    L.append(_h(2, "七、下一步要核验的事"))
    L.append("")
    for v in case.get("key_variables") or []:
        L.append("- **%s %s**：观察 %s；阈值 %s" % (v.get("id"), v.get("name"), v.get("watch"), v.get("threshold")))
    L.append("")
    L.append("---")
    L.append(meta.get("disclaimer", ""))
    return "\n".join(L)


def build_report(case, audience=None):
    prof = C.audience_profile(case, audience)
    payload = C.build_payload(case, prof)
    meta = case.get("meta") or {}
    L = []
    L.append(_h(1, meta.get("title", "")))
    L.append("")
    if meta.get("subtitle"):
        L.append("> " + meta["subtitle"])
        L.append(">")
    L.append("> 受众：%s ｜ 报告日：%s ｜ 数据截止：%s ｜ 范围：%s" %
             (prof.get("label", ""), meta.get("report_date", ""), meta.get("data_cutoff", ""),
              meta.get("horizon", "")))
    L.append("")
    L.append(_h(2, "核心指标"))
    L.append("")
    L += _table(["指标", "数值", "变化/口径", "证据"],
                [[k.get("label"), "%s %s" % (k.get("value"), k.get("unit") or ""), k.get("delta"),
                  k.get("evidence")] for k in case.get("kpis") or []])
    L.append("")
    L.append(_h(2, "核心结论"))
    L.append("")
    for c in case.get("conclusions") or []:
        L.append("%d. %s %s（%s，置信度 %s）" % (c.get("rank"), TYPE_MARK.get(c.get("type"), ""),
                                              c.get("text"), c.get("type"), c.get("confidence")))
        L.append("   - 证据：%s ｜ 计算：%s" % ("、".join(c.get("evidence") or []),
                                            "、".join(c.get("calcs") or []) or "—"))
        if c.get("falsify"):
            L.append("   - 反证条件：%s" % c["falsify"])
    L.append("")
    for s in payload.get("sections") or []:
        L.append(_h(2, "%s %s" % (s.get("no", ""), s.get("title", ""))))
        L.append("")
        if s.get("lede"):
            L.append(s["lede"])
            L.append("")
        for b in s.get("blocks") or []:
            t = b.get("type")
            if t == "para":
                L.append(b.get("text", ""))
                L.append("")
            elif t == "callout":
                L.append("> **%s** %s" % (b.get("title", ""), b.get("text", "")))
                L.append("")
            elif t == "chart":
                L.append("- 图表：**%s**%s（来源：%s）" %
                         (b.get("title", ""), ("——" + b["note"]) if b.get("note") else "",
                          "、".join(b.get("source") or [])))
                L.append("")
            elif t == "calc":
                c = C.calc_index(case).get(b.get("calc_id"))
                if c:
                    L.append("- **%s %s**：`%s` → **%s**（%s）" %
                             (c.get("id"), c.get("title"), c.get("formula"), c.get("output"),
                              c.get("result_note", "")))
                    L.append("")
            elif t == "table":
                rows = b.get("rows")
                if rows is None and b.get("rows_key"):
                    rows = C.get_by_path(case, b["rows_key"]) or []
                if b.get("title"):
                    L.append("**%s**" % b["title"])
                    L.append("")
                if rows:
                    if isinstance(rows[0], dict):
                        keys = list(rows[0].keys())
                        L += _table(keys, [[r.get(k) for k in keys] for r in rows])
                    else:  # 行是列表：首行当表头
                        L += _table(rows[0], rows[1:])
                    L.append("")
            elif t == "conclusions_full":
                for c in case.get("conclusions") or []:
                    L.append("%d. %s %s" % (c.get("rank"), TYPE_MARK.get(c.get("type"), ""), c.get("text")))
                    L.append("   - 反证条件：%s" % (c.get("falsify") or "—"))
                L.append("")
    L.append(_h(2, "计算过程"))
    L.append("")
    L += _table(["ID", "计算项", "公式", "结果", "口径"],
                [[c.get("id"), c.get("title"), c.get("formula"), c.get("output"), c.get("result_note")]
                 for c in case.get("calculations") or []])
    L.append("")
    L.append(_h(2, "证据索引"))
    L.append("")
    L += _table(["ID", "机构", "标题", "日期", "层级", "链接"],
                [[s.get("id"), s.get("org"), s.get("title"), s.get("date"), s.get("tier"), s.get("url")]
                 for s in case.get("sources") or []])
    L.append("")
    L.append(_h(2, "资料缺口"))
    L.append("")
    L += _table(["ID", "主题", "缺什么", "影响", "下一步"],
                [[g.get("id"), g.get("topic"), g.get("missing"), g.get("impact"), g.get("next_step")]
                 for g in case.get("data_gaps") or []])
    L.append("")
    L.append("---")
    L.append(meta.get("disclaimer", ""))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成 Markdown（提纲/执行记录/文字稿）")
    ap.add_argument("kind", choices=["outline", "record", "report"])
    ap.add_argument("case")
    ap.add_argument("--out", default="")
    ap.add_argument("--audience", default="")
    ap.add_argument("--status", default="draft", choices=["draft", "confirmed"])
    a = ap.parse_args(argv)
    case = C.load(a.case)
    aud = a.audience or None
    if a.kind == "outline":
        text = build_outline(case, a.status, aud)
        suffix = "_研究提纲_%s.md" % ("已确认" if a.status == "confirmed" else "待确认")
    elif a.kind == "record":
        text = build_record(case, aud)
        suffix = "_执行记录.md"
    else:
        text = build_report(case, aud)
        suffix = "_报告全文.md"
    if a.out:
        out = a.out
    else:
        base = C.default_filename(case, C.audience_profile(case, aud)["audience_key"], "")
        out = base + suffix
    C.ensure_dir(os.path.dirname(os.path.abspath(out)))
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print("MD ->", out, "(%d 字)" % len(text))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

