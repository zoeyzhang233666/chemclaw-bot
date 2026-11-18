# -*- coding: utf-8 -*-
"""build_md.py · 独立可复制英文草稿 + 中文简报

- 默认输出「草稿版」：占位符原样保留，并附占位符清单；
- `--pack` 输出「可发送版」：所有占位符必须已由我方确认（status=confirmed_by_us/waived），
  否则 exit 3，并列出还差哪几项——这是脚本层的第二道闸。

用法：
    python build_md.py fields.json reply.json -o 回复_客户.md
    python build_md.py fields.json reply.json -o 回复_客户.md --pack
    python build_md.py fields.json reply.json -o 简要.md --brief cn
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402


def replace_placeholders(body: str, values: dict) -> str:
    def sub(m):
        k = m.group(1)
        v = values.get(k)
        return v if v not in (None, "") else m.group(0)
    return re.sub(r"‹([A-Z0-9_]+)›", sub, body)


def gate_placeholders(reply: dict) -> tuple:
    vals = reply.get("values") or {}
    bad = []
    for p in reply.get("placeholders", []):
        if p.get("status") == "waived":
            continue
        if not p.get("used"):
            continue
        if p.get("status") != "confirmed_by_us" and not vals.get(p["key"]):
            bad.append(p["key"])
    return (len(bad) == 0, bad)


def render_draft(fields_doc, reply, as_draft=True):
    meta = fields_doc.get("meta", {})
    body = reply.get("body", "")
    values = reply.get("values") or {}
    if not as_draft:
        body = replace_placeholders(body, values)
    out = [
        "# 英文回复草稿 · " + (meta.get("customer") or ""),
        "",
        "> 模拟案例：本稿用于演示询盘处理流程，其中的公司、联系人、数量与商务参数均为虚构。" if meta.get("simulation") else "",
        "> 本稿由 overseas-inquiry-triage 生成。**不含任何价格、库存、船期、交期、账期或单证承诺**；"
        "所有 `‹…›` 为占位符，须由对应责任人确认后替换。",
        "",
        "## Subject",
        "",
        "```text",
        reply.get("subject", ""),
        "```",
        "",
        "## Body（可直接复制）",
        "",
        "```text",
        body.rstrip(),
        "```",
        "",
        "## 占位符清单",
        "",
        "| 占位符 | 含义 | 责任人 | 状态 | 出现 |",
        "|---|---|---|---|---|",
    ]
    for p in reply.get("placeholders", []):
        if not p.get("used") and p.get("status") == "unused":
            continue
        st = {"open": "待填", "confirmed_by_us": "已由我方确认", "waived": "本次不用"}.get(p.get("status"), p.get("status", ""))
        used = "是" if p.get("used") else "—（未在正文出现）"
        v = values.get(p["key"], "")
        if v:
            st += f"：`{v}`"
        out.append(f"| `‹{p['key']}›` | {p.get('label_cn','')} | {p.get('owner','')} | {st} | {used} |")
    out += ["", "## 生成说明", ""]
    out.append(f"- 渠道：{reply.get('channel','')} · 语气：{reply.get('tone','')} · 模板：{reply.get('template','')}")
    out.append(f"- 生成时间：{reply.get('generated_at','')} · 生成器：{reply.get('generator','')}")
    out.append(f"- 承诺扫描：{len(reply.get('commitment_scan') or [])} 处命中")
    out.append(f"- 价格痕迹扫描：{len(reply.get('price_scan') or [])} 处命中")
    q = fields_doc.get("questions") or []
    if q:
        out += ["", "## 本轮向客户提出的问题（记录用）", ""]
        for i, x in enumerate(q, 1):
            out.append(f"{i}. {x['question_en']}")
    return "\n".join([x for x in out if x is not None]) + "\n"


def render_brief_cn(fields_doc, reply):
    meta = fields_doc.get("meta", {})
    f = fields_doc.get("fields", {})
    s = fields_doc.get("summary", {})
    def v(k, d="—"):
        x = f.get(k, {})
        return x.get("value") or d
    lines = [
        f"# 中文简报 · {meta.get('customer','')}（{meta.get('customer_country','')}）",
        "",
        f"> {meta.get('simulation_notice','')}",
        "",
        "## 一、客户要什么（均来自客户原话）",
        "",
        f"- 产品：{v('product_std')}（{v('product_cn')}）/ 形态：{v('appearance_form')}",
        f"- 规格：{v('spec_purity')}；{v('spec_impurities')}；{v('spec_particle')}",
        f"- 数量：首批 {v('qty_trial')}；年量约 {v('qty_annual')}",
        f"- 交付：{v('incoterm')} {v('incoterm_place')}",
        f"- 单证：COA / SDS / TDS（客户明确列明）",
        f"- 付款：{v('payment')}（不完整）",
        "",
        "## 二、字段统计",
        "",
        f"- 已明确 {s.get('stated',0)} · 缺失 {s.get('missing',0)} · 歧义 {s.get('ambiguous',0)} · 我方假设 {s.get('assumed',0)}",
        f"- 阻塞报价字段 {len(fields_doc.get('blocking_fields',[]))} 个：{', '.join(fields_doc.get('blocking_fields',[]))}",
        f"- 现在能不能报价：**{'能' if fields_doc.get('can_quote') else '不能'}**",
        "",
        "## 三、回复前必须问客户的",
        "",
    ]
    for i, q in enumerate(fields_doc.get("questions") or [], 1):
        lines.append(f"{i}. {q['label_cn']}：{q['question_en']}")
        if q.get("anchor"):
            lines.append(f"   - 客户原话：`{q['anchor']}`")
    lines += ["", "## 四、我方内部要先定", ""]
    for x in fields_doc.get("internal_confirm") or []:
        lines.append(f"- {x['label_cn']}：{x['desc']}")
    lines += ["", "## 五、回复草稿状态", "",
              f"- 渠道：{reply.get('channel','')} · 语气：{reply.get('tone','')}",
              f"- 占位符 {len([p for p in reply.get('placeholders',[]) if p.get('used')])} 个待填（价格/交期/付款/单证等）",
              "- 不得对询盘真实性或成交可能性打分（本技能不做此评估）。"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="生成独立可复制英文草稿 / 中文简报")
    ap.add_argument("fields")
    ap.add_argument("reply", nargs="?", default="")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--pack", action="store_true", help="输出可发送版（要求占位符均已确认）")
    ap.add_argument("--brief", default="", choices=["", "cn"], help="输出中文简报")
    args = ap.parse_args()

    fields_doc = C.load_json(args.fields)
    reply = C.load_json(args.reply) if args.reply else {}
    if args.brief == "cn":
        text = render_brief_cn(fields_doc, reply)
    else:
        if args.pack:
            ok, bad = gate_placeholders(reply)
            if not ok:
                print("[gate] 拒绝生成可发送版：以下占位符尚未由我方确认：", file=sys.stderr)
                for b in bad:
                    print("   - ‹" + b + "›", file=sys.stderr)
                return 3
        text = render_draft(fields_doc, reply, as_draft=not args.pack)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"[ok] {args.out} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
