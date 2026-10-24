# -*- coding: utf-8 -*-
"""
build_followup.py — 一条命令生成跟进卡全套交付物

用法：
    python build_followup.py followup.json -o out/ [--name 客户简称] [--md]

输出：
    <out>/<slug>.xlsx   客户跟进卡工作簿（10 表）
    <out>/<slug>.html   自包含 HTML 跟进卡（可打印）
    <out>/<slug>.md     纯文本摘要（可选，便于贴进 CRM 备注）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_xlsx
import build_html
from _common import (
    validate, parse_as_of, compute_stall_days, promise_state, days_left,
)


def build_md(data):
    meta = data.get("meta") or {}
    as_of = parse_as_of(meta.get("as_of_date"))
    timeline = data.get("timeline") or []
    stage = data.get("stage") or {}
    stall_days, last = compute_stall_days(timeline, as_of)
    promises = data.get("promises") or []
    overdue = [p for p in promises if promise_state(p, as_of)[1] == "risk"]

    L = []
    L.append(f"# {meta.get('title','客户跟进卡')}")
    L.append("")
    L.append(f"**阶段**：{stage.get('current','—')}　｜　**停滞**：{stall_days if stall_days is not None else '—'} 天"
             f"　｜　**逾期承诺**：{len(overdue)} 项　｜　生成 {meta.get('generated_at','')}")
    L.append("")
    L.append(f"> {data.get('headline','')}")
    L.append("")
    L.append("## 客户档案")
    L.append("")
    L.append("| 字段 | 内容 |")
    L.append("|---|---|")
    for it in data.get("profile") or []:
        L.append(f"| {it.get('label','')} | {it.get('value','')} |")
    L.append("")
    L.append("## 卡点")
    L.append("")
    L.append("| 卡点 | 状态 | 现状 |")
    L.append("|---|---|---|")
    for b in data.get("blockers") or []:
        L.append(f"| {b.get('title','')} | {b.get('status','')} | {b.get('detail','').replace('|','/')} |")
    L.append("")
    L.append(f"## 时间线（{len(timeline)} 条）")
    L.append("")
    L.append("| # | 时间 | 来源 | 分类 | 记录 |")
    L.append("|---|---|---|---|---|")
    for i, r in enumerate(timeline, 1):
        txt = str(r.get("text", "")).replace("|", "/").replace("\n", " ")
        L.append(f"| {r.get('no', i)} | {r.get('date','')} {r.get('time','')} | {r.get('source','')} | {r.get('category','')} | {txt} |")
    L.append("")
    L.append("## 客户明确需求")
    L.append("")
    L.append("| 维度 | 内容 | 出处 | 置信度 |")
    L.append("|---|---|---|---|")
    for x in data.get("requirements") or []:
        L.append(f"| {x.get('dimension','')} | {str(x.get('content','')).replace('|','/')} | {x.get('source','')} | {x.get('confidence','')} |")
    L.append("")
    L.append("## 客户异议")
    L.append("")
    L.append("| # | 异议 | 出处 | 状态 |")
    L.append("|---|---|---|---|")
    for i, x in enumerate(data.get("objections") or [], 1):
        L.append(f"| {x.get('no', i)} | {str(x.get('content','')).replace('|','/')} | {x.get('source','')} | {x.get('status','')} |")
    L.append("")
    L.append("## 我方承诺")
    L.append("")
    L.append("| # | 承诺 | 截止 | 状态 |")
    L.append("|---|---|---|---|")
    for i, p in enumerate(promises, 1):
        st, _ = promise_state(p, as_of)
        L.append(f"| {p.get('no', i)} | {str(p.get('content','')).replace('|','/')} | {p.get('due','')} | {st} |")
    L.append("")
    L.append("## 待确认事项")
    L.append("")
    L.append("| # | 事项 | 类型 | 卡在谁 | 建议闭环 |")
    L.append("|---|---|---|---|---|")
    for i, x in enumerate(data.get("pending") or [], 1):
        L.append(f"| {x.get('no', i)} | {str(x.get('content','')).replace('|','/')} | {x.get('type','')} | {x.get('owner','')} | {x.get('target','')} |")
    L.append("")
    ai = data.get("ai_summary") or {}
    L.append("## AI 摘要（AI 推断，非客户原话）")
    L.append("")
    for p in ai.get("paragraphs") or []:
        L.append(p)
        L.append("")
    for pt in ai.get("points") or []:
        L.append(f"- **{pt.get('h','')}**：{pt.get('p','')}")
    L.append("")
    L.append("## 无法辨认 / 缺失")
    L.append("")
    for i, x in enumerate(data.get("unknowns") or [], 1):
        L.append(f"{i}. [{x.get('status','待补')}] {x.get('source','')}：{x.get('issue','')} → {x.get('need','')}")
    L.append("")
    L.append("## 下一步")
    L.append("")
    for a in data.get("next_actions") or []:
        L.append(f"- **{a.get('prio','')} {a.get('when','')}**：{a.get('action','')}（闭环：{a.get('closure','')}）")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="由 followup.json 生成 客户跟进卡 Excel + HTML")
    ap.add_argument("input", help="followup.json 路径")
    ap.add_argument("-o", "--outdir", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--name", default=None, help="输出文件名（默认取 meta.slug）")
    ap.add_argument("--md", action="store_true", help="额外输出 Markdown 摘要")
    ap.add_argument("--strict", action="store_true", help="把 warning 也当作错误")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8-sig") as f:
        data = json.load(f)

    errors, warnings = validate(data)
    for w in warnings:
        print(f"[warn] {w}")
    if errors or (args.strict and warnings):
        for e in errors:
            print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    slug = args.name or (data.get("meta") or {}).get("slug") or "followup_card"
    xlsx_path = os.path.join(args.outdir, f"{slug}.xlsx")
    html_path = os.path.join(args.outdir, f"{slug}.html")

    build_xlsx.build(data, xlsx_path)
    print(f"[ok] xlsx -> {xlsx_path}")

    html_text = build_html.build(data)
    with open(html_path, "w", encoding="utf-8-sig") as f:
        f.write(html_text)
    print(f"[ok] html -> {html_path}  ({len(html_text.encode('utf-8'))} bytes)")

    if args.md:
        md_path = os.path.join(args.outdir, f"{slug}.md")
        with open(md_path, "w", encoding="utf-8-sig") as f:
            f.write(build_md(data))
        print(f"[ok] md   -> {md_path}")

    # 摘要
    as_of = parse_as_of((data.get("meta") or {}).get("as_of_date"))
    days, last = compute_stall_days(data.get("timeline") or [], as_of)
    overdue = sum(1 for p in (data.get("promises") or [])
                  if promise_state(p, as_of)[1] == "risk")
    stage = (data.get("stage") or {}).get("current", "—")
    print(f"\n阶段：{stage}｜停滞 {days if days is not None else '—'} 天｜逾期承诺 {overdue} 项"
          f"｜记录 {len(data.get('timeline') or [])} 条")


if __name__ == "__main__":
    main()
