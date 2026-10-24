"""外贸采购合同审阅 → 自包含交互式 HTML 报告。

本文件由 _html_part1.py（渲染与 build）与 _html_part2.py（模板与 CLI）合并生成。
用法：python build_review_html.py --dir <案例目录> --out <输出.html>
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

from common import (KIND_ORDER, SEVERITY_LABEL, clause_locator, esc, excerpt,
                    load_case, validate_case)

TOPIC_COLORS = {
    "parties": "#475569", "quality": "#0e7490", "quantity": "#7c3aed",
    "payment": "#be185d", "delivery": "#1d4ed8", "docs": "#b45309",
    "claims": "#c2410c", "risk": "#0f766e", "breach": "#9333ea",
    "force_majeure": "#6b7280", "dispute": "#334155", "language": "#1f2937",
    "compliance": "#b91c1c",
}
SEV = {
    5: ("极高", "#ffffff", "#b91c1c"),
    4: ("高", "#ffffff", "#ea580c"),
    3: ("中", "#7c2d12", "#fcd34d"),
    2: ("低", "#14532d", "#bbf7d0"),
    1: ("提示", "#1e3a8a", "#dbeafe"),
}
STATUS = ["待处理", "跟进中", "已确认", "待供应商回复", "已解决", "不适用"]


# ---------------------------------------------------------------------------
# 渲染：左栏合同原文
# ---------------------------------------------------------------------------
def render_clause(c: dict, hits: list[dict], bilingual: bool) -> str:
    chips = "".join(
        f'<button class="chip s{h["severity"]}" data-goto-finding="{esc(h["id"])}" '
        f'title="{esc(h["title"])}">{esc(h["id"])}</button>' for h in hits)
    kind = c.get("kind", "")
    cls = f"clause k-{kind}" if kind else "clause"
    if kind in ("annex_head", "cover"):
        cls += " strong"
    en = esc(c["text"])
    zh = ""
    if bilingual and c.get("zh") and kind not in ("table_head",):
        zh = f'<div class="zh">{esc(c["zh"])}</div>'
    elif bilingual and c.get("zh"):
        zh = f'<span class="zh-inline">{esc(c["zh"])}</span>'
    no = esc(c["no"])
    if c.get("kind") == "table_row":
        parts = [p.strip() for p in c["text"].split(" — ")]
        if len(parts) >= 2:
            en = "".join(f"<span class='tc'>{esc(p)}</span>" for p in parts)
    return (
        f'<div class="{cls}" id="clause-{esc(c["id"])}" data-clause="{esc(c["id"])}" data-page="{c["page"]}">'
        f'<div class="clause-h"><span class="cno">{no}</span><span class="cpg">P{c["page"]}</span>'
        f'<span class="chips">{chips}</span></div>'
        f'<div class="en">{en}</div>{zh}</div>'
    )


def render_contract(contract: dict, hits: dict, bilingual: bool) -> str:
    clauses = {c["id"]: c for c in contract["clauses"]}
    out = []
    prev_page = None
    for s in contract["sections"]:
        if s["page"] != prev_page:
            out.append(f'<div class="page-mark">Page {s["page"]} / 第 {s["page"]} 页</div>')
            prev_page = s["page"]
        inner = "".join(render_clause(clauses[cid], hits.get(cid, []), bilingual) for cid in s["clause_ids"])
        out.append(
            f'<section class="csec" id="sec-{esc(s["id"])}">'
            f'<h3><span class="sec-no">{esc(s["no"])}</span>{esc(s["title"])}</h3>{inner}</section>'
        )
    return "".join(out)


# ---------------------------------------------------------------------------
# 渲染：右栏风险卡
# ---------------------------------------------------------------------------
def render_card(f: dict, clauses: dict, topic_name: dict) -> str:
    label, fg, bg = SEV[f["severity"]]
    tcolor = TOPIC_COLORS.get(f["topic"], "#475569")
    anchors = "".join(
        f'<button class="anchor" data-goto-clause="{esc(cid)}">📍 {esc(clause_locator(clauses[cid]))}</button>'
        for cid in f["clause_ids"] if cid in clauses)
    quotes = "".join(
        f'<blockquote class="quote"><span class="qsrc">{esc(clause_locator(clauses[q["clause_id"]]))}</span>'
        f'<span class="qtext">{esc(q["text"])}</span></blockquote>'
        for q in f.get("quotes", []) if q["clause_id"] in clauses)
    if not quotes:
        quotes = ('<p class="noquote">本合同未见该事项约定（检索全文无对应表述），'
                  '因此不引用原文；相关位置以条款锚点为准。</p>')
    missing_block = ""
    if f.get("what_missing"):
        flag = ('<span class="miss-flag">缺失 · 未约定（不作推测）</span>' if f["kind"] == "缺失" else "")
        missing_block = f'<section><h5>哪些没写清楚 / 缺失</h5>{flag}<p>{esc(f["what_missing"])}</p></section>'
    cons = "".join(f"<li>{esc(x)}</li>" for x in f.get("consequences", []))
    todo = "".join(f"<li>{esc(x)}</li>" for x in f.get("to_confirm", []))
    laws = ""
    if f.get("law_refs"):
        laws = ('<section><h5>相关法规 / 规则 / 标准（适用性以「法规核对」页为准）</h5><div class="chips-lite">'
                + "".join(f"<span>{esc(x)}</span>" for x in f["law_refs"]) + "</div></section>")
    basis = (f'<p class="basis">口径：{esc(f["impact_basis"])}</p>' if f.get("impact_basis") else "")
    search_index = " ".join([
        f["id"], f["title"], f.get("what_written", ""), f.get("what_missing", ""),
        f.get("business_impact", ""), " ".join(f.get("to_confirm", [])),
        " ".join(clauses[c]["no"] for c in f["clause_ids"] if c in clauses),
        " ".join(q["text"] for q in f.get("quotes", [])),
    ]).lower()
    return f"""
<article class="card" id="finding-{esc(f['id'])}" data-id="{esc(f['id'])}"
  data-topic="{esc(f['topic'])}" data-kind="{esc(f['kind'])}" data-sev="{f['severity']}"
  data-clauses="{esc(','.join(f['clause_ids']))}"
  data-search="{esc(search_index)}">
  <header class="card-h" data-toggle>
    <span class="rid">{esc(f['id'])}</span>
    <span class="sev" style="color:{fg};background:{bg}">{label} {f['severity']}</span>
    <span class="topic" style="background:{tcolor}">{esc(topic_name.get(f['topic'], f['topic']))}</span>
    <span class="kind k-{esc(f['kind'])}">{esc(f['kind'])}</span>
    <span class="pill" data-pill>待处理</span>
    <span class="caret">▸</span>
  </header>
  <h4 class="card-t">{esc(f['title'])}</h4>
  <div class="card-b">
    <section><h5>合同原文（English excerpt · 逐字）</h5>{quotes}
      <div class="anchors">{anchors}</div></section>
    <section><h5>中文解释 · 合同写了什么</h5><p>{esc(f['what_written'])}</p></section>
    {missing_block}
    <section><h5>对中国买方的商务后果</h5><p>{esc(f['business_impact'])}</p>
      <ul class="cons">{cons}</ul>{basis}</section>
    <section><h5>需要与谁确认 · 确认什么</h5><ul class="todo">{todo}</ul></section>
    {laws}
    <section class="ctrl">
      <h5>处理跟踪（保存在本浏览器；可导出 JSON / CSV）</h5>
      <div class="ctrl-row">
        <label>内部负责人 <input data-owner placeholder="如：采购 王××"></label>
        <label>处理状态 <select data-status>{"".join(f"<option>{s}</option>" for s in STATUS)}</select></label>
      </div>
      <label class="fb">供应商反馈 <textarea data-feedback rows="2" placeholder="记录卖方书面答复、澄清或修改建议…"></textarea></label>
    </section>
  </div>
</article>"""


# ---------------------------------------------------------------------------
# 渲染：问题清单（三张）
# ---------------------------------------------------------------------------
OWNER_META = {
    "legal": ("公司法务待办", "条款效力、责任分配、仲裁与适用法 —— 由法务/律师判断，本表仅提交问题"),
    "procurement": ("采购 / 进口待办", "商务谈判、开证与付款审批、供应保障与到货安排"),
    "supplier": ("供应商问题清单", "可直接作为澄清函附件：只问事实、文件与承诺，不问法律判断"),
}


def render_question_tables(review: dict, fmap: dict) -> str:
    btns, panes = [], []
    for i, (owner, items) in enumerate(review.get("confirmations", {}).items()):
        title, desc = OWNER_META.get(owner, (owner, ""))
        items_sorted = sorted(items, key=lambda q: {"高": 0, "中": 1, "低": 2}[q["priority"]])
        rows = []
        for q in items_sorted:
            f = fmap[q["finding_id"]]
            rows.append(
                f'<tr data-goto-finding="{esc(f["id"])}"><td class="mono">{esc(f["id"])}</td>'
                f'<td><span class="pri p-{esc(q["priority"])}">{esc(q["priority"])}</span></td>'
                f'<td>{esc(f["title"])}</td><td>{esc(q["question"])}</td>'
                f'<td class="mono">{esc(", ".join(f["clause_ids"]))}</td>'
                f'<td class="ck"><input type="checkbox" data-q="{esc(owner)}-{esc(f["id"])}-{i}"></td></tr>')
        panes.append(
            f'<div class="qpane{" active" if i == 0 else ""}" data-owner="{esc(owner)}">'
            f'<p class="qdesc">{esc(desc)}</p>'
            '<table class="qtable"><thead><tr><th>风险</th><th>优先级</th><th>风险标题</th>'
            '<th>需要确认的问题</th><th>条款</th><th>已处理</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')
        btns.append(f'<button class="qbtn{" active" if i == 0 else ""}" data-owner="{esc(owner)}">'
                    f'{esc(title)} · {len(items)} 项</button>')
    return f'<div class="qbtns">{"" .join(btns)}</div>{"".join(panes)}'


def render_bilingual_csv(review: dict, contract: dict) -> str:
    """中英对照问题清单 CSV 文本（供页面内下载）。"""
    clauses = {c["id"]: c for c in contract["clauses"]}
    fmap = {f["id"]: f for f in review["findings"]}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["风险编号", "主题", "类型", "严重度", "风险标题(中文)", "Risk issue (English summary)",
                "引用条款", "条款位置", "合同原文(English)", "需确认事项(中文)", "Question to Supplier (English)"])
    for owner_items in review.get("confirmations", {}).values():
        for q in owner_items:
            f = fmap[q["finding_id"]]
            en_ref = " | ".join(f'{clauses[c]["no"]}: {(f["quotes"][i]["text"] if i < len(f.get("quotes", [])) else "")[:90]}'
                               if c in clauses else c for i, c in enumerate(f["clause_ids"]))
            w.writerow([f["id"], f["topic"], f["kind"], f["severity"], f["title"],
                        f.get("title_en", ""), ", ".join(f["clause_ids"]),
                        "; ".join(clause_locator(clauses[c]) for c in f["clause_ids"] if c in clauses),
                        en_ref, q["question"], q.get("question_en", "")])
    return buf.getvalue()


def make_index_chips(items: list[dict]) -> str:
    """条款索引行的关联风险小标签。"""
    if not items:
        return "—"
    return "".join(
        f'<span class="chip s{h["severity"]}" style="cursor:default">{esc(h["id"])}</span>'
        for h in items)


def build(case_dir: Path, out: Path, title: str | None, seed: dict | None, user_note: str,
          letter_path: Path | None = None) -> dict:
    case = load_case(case_dir)
    contract, review = case["contract"], case["review"]
    check = validate_case(contract, review)
    if check["errors"]:
        raise SystemExit("数据校验失败:\n  " + "\n  ".join(check["errors"]))
    stats = check["stats"]

    clauses = {c["id"]: c for c in contract["clauses"]}
    fmap = {f["id"]: f for f in review["findings"]}
    topic_name = {t["id"]: t["name"] for t in review["topics"]}
    meta = contract.get("contract_meta", {})
    rm = review.get("review_meta", {})
    bilingual = contract.get("language", "en-zh") == "en-zh"

    hits: dict[str, list] = {}
    for f in review["findings"]:
        for cid in f["clause_ids"]:
            hits.setdefault(cid, []).append(f)
    for v in hits.values():
        v.sort(key=lambda x: (-x["severity"], x["id"]))

    contract_html = render_contract(contract, hits, bilingual)
    cards_html = "".join(render_card(f, clauses, topic_name) for f in
                         sorted(review["findings"], key=lambda x: (KIND_ORDER[x["kind"]], -x["severity"], x["id"])))
    q_html = render_question_tables(review, fmap)

    topic_filter = "".join(
        f'<button class="tbtn" data-topic="{esc(t["id"])}" style="--tc:{TOPIC_COLORS.get(t["id"], "#475569")}">'
        f'{esc(t["name"])}<b>{stats["topic"].get(t["id"], 0)}</b></button>'
        for t in review["topics"] if stats["topic"].get(t["id"]))
    kind_filter = "".join(
        f'<button class="kbtn" data-kind="{esc(k)}">{esc(k)}<b>{stats["kind"].get(k, 0)}</b></button>'
        for k in ("缺失", "表述不清", "写了但对我方不利") if stats["kind"].get(k))
    sev_filter = "".join(
        f'<button class="sbtn" data-sev="{n}" style="color:{SEV[n][1]};background:{SEV[n][2]}">{SEV[n][0]} {n}</button>'
        for n in (5, 4, 3, 2, 1) if stats["severity"].get(n))

    law_rows = "".join(
        f'<tr><td><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["name"])}</a></td>'
        f'<td>{esc(r["scope"])}</td>'
        f'<td><span class="st {"ok" if "现行" in r["status"] else "warn"}">{esc(r["status"])}</span></td>'
        f'<td>{esc(r["status_basis"])}</td><td>{esc(r["relevance"])}</td></tr>'
        for r in review.get("legal_refs", []))

    top_rows = "".join(
        f'<li class="toprow" data-goto-finding="{esc(f["id"])}">'
        f'<span class="sev" style="color:{SEV[f["severity"]][1]};background:{SEV[f["severity"]][2]}">'
        f'{SEV[f["severity"]][0]}</span><b>{esc(f["id"])}</b> {esc(f["title"])}</li>'
        for f in sorted(review["findings"], key=lambda x: (-x["severity"], x["id"]))[:10])

    missing_list = "".join(f"<li>{esc(x)}</li>" for x in review["summary"].get("missing_list", []))
    files_ok = "".join(f"<li>✅ {esc(x)}</li>" for x in meta.get("files_received", []))
    files_no = "".join(f"<li class='miss'>❌ {esc(x)}</li>" for x in meta.get("files_missing", []))
    topicbar = "".join(
        f'<div class="tbi" style="--h:{stats["topic"].get(t["id"], 0)}px"><i>{stats["topic"].get(t["id"], 0)}</i>'
        f'<span>{esc(t["short"])}</span></div>' for t in review["topics"] if stats["topic"].get(t["id"]))

    index_rows = "".join(
        f'<tr data-goto-clause="{esc(c["id"])}"><td class="mono">{esc(c["id"])}</td>'
        f'<td>{esc(c["no"])}</td><td>P{c["page"]}</td>'
        f'<td>{esc(excerpt(c["text"], 110))}</td>'
        f'<td>{make_index_chips(hits.get(c["id"], []))}</td></tr>'
        for c in contract["clauses"]
    )

    neg_covered = {c for n in review.get("negative_results", []) for c in n["clause_ids"] if c in clauses}
    neg_left = sorted(set(clauses) - set(hits) - neg_covered)

    letter_html = ""
    if letter_path and letter_path.exists():
        letter_html = f'<pre class="letter">{esc(letter_path.read_text(encoding="utf-8"))}</pre>'

    _neg_total = len(clauses)
    _hit_set = {c for f in review["findings"] for c in f["clause_ids"] if c in clauses}
    _cov_set = {c for n in review.get("negative_results", []) for c in n["clause_ids"] if c in clauses}
    _neg_hit = len(_hit_set)
    _neg_cov = len(_cov_set)
    _neg_left = len(set(clauses) - _hit_set - _cov_set)
    neg_rows = "".join(
        f'<tr><td class="mono">{esc(", ".join(n["clause_ids"]))}</td>'
        f'<td>{esc("; ".join(clauses[c]["no"] for c in n["clause_ids"] if c in clauses))}</td>'
        f'<td>{esc(n["note"])}</td></tr>'
        for n in review.get("negative_results", []))
    neg_html = (
        f'<div class="box"><h3>已审、未发现风险（负结果 · Reviewed without findings）</h3>'
        '<p style="font-size:12.6px;color:#475569">下表条款已被逐条审阅，但未单列为风险条目。它们多属说明性、格式性'
        '或已在可接受范围内表述的条款；列入此处是为了说明「没被列为风险的条款也审过了」，而不是遗漏。</p>'
        '<table class="qtable"><thead><tr><th>条款ID</th><th>条款编号</th><th>审阅结论（未发现风险的原因）</th></tr></thead>'
        f'<tbody>{neg_rows}</tbody></table></div>'
    )

    product = meta.get("product", {})
    prod_txt = (f'{product.get("name_cn", "")} / {product.get("name_en", "")}'
                if isinstance(product, dict) else str(product))
    inco = meta.get("incoterms", {})
    inco_txt = f'{inco.get("rule", "")} {inco.get("place", "")} Incoterms® {inco.get("year", "")}'

    html = TEMPLATE.format(
        title=esc(title or f'{meta.get("contract_no", "")} 外贸采购合同审阅报告'),
        contract_no=esc(meta.get("contract_no", "")),
        contract_title=esc(meta.get("title", "")),
        buyer=esc(meta.get("buyer", "")), supplier=esc(meta.get("supplier", "")),
        review_as=esc(meta.get("review_as", "")), sign_date=esc(meta.get("sign_date", "")),
        review_date=esc(rm.get("review_date", "")), reviewer=esc(rm.get("reviewer", "")),
        signed=esc(rm.get("signed", "")), scope=esc(rm.get("review_scope", "")),
        data_cutoff=esc(rm.get("data_cutoff", "")), law_date=esc(rm.get("law_check_date", "")),
        disclaimer=esc(rm.get("disclaimer", "")), boundary=esc(rm.get("boundary", "")),
        product=esc(prod_txt), incoterms=esc(inco_txt),
        pages=str(meta.get("page_count", rm.get("pages", ""))),
        n_total=str(stats["total"]),
        n_missing=str(stats["kind"].get("缺失", 0)),
        n_unclear=str(stats["kind"].get("表述不清", 0)),
        n_disadvantage=str(stats["kind"].get("写了但对我方不利", 0)),
        n_high=str(stats["severity"].get(5, 0) + stats["severity"].get(4, 0)),
        n_clauses=str(len(hits)), n_conf=str(sum(len(v) for v in review["confirmations"].values())),
        n_legal=str(len(review.get("legal_refs", []))),
        headline=esc(review["summary"].get("headline", "")),
        top_rows=top_rows, missing_list=missing_list, files_ok=files_ok, files_no=files_no,
        topicbar=topicbar, contract_html=contract_html, cards=cards_html, q_html=q_html,
        topic_filter=topic_filter, kind_filter=kind_filter, sev_filter=sev_filter,
        law_rows=law_rows, letter=letter_html, index_rows=index_rows, neg_html=neg_html,
        n_neg_total=str(len(clauses)), n_neg_hit=str(len(hits)),
        n_neg_covered=str(len(neg_covered)), n_neg_left=str(len(neg_left)),
        bscsv=json.dumps(render_bilingual_csv(review, contract), ensure_ascii=False),
        status_json=json.dumps(STATUS, ensure_ascii=False),
        seed=json.dumps(seed or {}, ensure_ascii=False),
        user_note=esc(user_note or "—"),
        method_steps="".join(f"<li>{esc(s)}</li>" for s in review.get("method", {}).get("steps", [])),
        method_product="".join(f"<li>{esc(s)}</li>" for s in review.get("method", {}).get("product_specific", [])),
        calc_note=esc(review["summary"].get("calc_basis", {}).get("note", "")),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return {"out": str(out), "bytes": len(html.encode("utf-8")), "findings": stats["total"]}


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{
  --ink:#0f172a; --muted:#64748b; --line:#e2e8f0; --bg:#f4f6f9; --card:#fff;
  --brand:#0b3350; --brand2:#155e75; --accent:#c2410c; --gold:#f59e0b; --left:50%;
  --shadow:0 1px 2px rgba(15,23,42,.05),0 1px 3px rgba(15,23,42,.06);
}}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0}}
body{{font-family:"Microsoft YaHei","PingFang SC","Noto Sans SC",system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--ink);background:var(--bg);font-size:14px;line-height:1.62;-webkit-font-smoothing:antialiased}}
a{{color:#0b5cad;text-decoration:none}} a:hover{{text-decoration:underline}}
.demo-banner{{background:repeating-linear-gradient(45deg,#fef3c7,#fef3c7 14px,#fde68a 14px,#fde68a 28px);
  color:#78350f;padding:9px 26px;font-size:12.5px;border-bottom:1px solid #f59e0b}}
.demo-banner b{{letter-spacing:.02em}}
.hero{{background:radial-gradient(1200px 300px at 10% -20%,rgba(21,94,117,.55),transparent),
  linear-gradient(135deg,#08243a 0%,#0b3350 45%,#155e75 100%);color:#e6f2f7;padding:26px 30px 20px}}
.hero .kicker{{font-size:11.5px;letter-spacing:.22em;color:#7dd3fc;text-transform:uppercase;font-weight:600}}
.hero h1{{margin:7px 0 6px;font-size:24px;font-weight:700;letter-spacing:.01em;line-height:1.35}}
.hero .meta{{display:flex;flex-wrap:wrap;gap:6px 26px;font-size:12.5px;color:#bae6fd;margin-top:8px}}
.hero .meta b{{color:#fff;font-weight:600}}
.pills{{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}}
.pill{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);padding:3px 11px;border-radius:999px;font-size:12px}}
.tabs{{display:flex;gap:2px;background:#08243a;padding:0 16px;position:sticky;top:0;z-index:60;flex-wrap:wrap}}
.tabs button{{background:transparent;border:0;color:#9ec5d8;padding:12px 16px;font-size:13.5px;cursor:pointer;
  border-bottom:3px solid transparent;font-family:inherit}}
.tabs button.active{{color:#fff;border-bottom-color:var(--gold);font-weight:600}}
.tabs button:hover{{color:#fff}}
.panel{{display:none;padding:18px 22px 46px}} .panel.active{{display:block}}
.cards4{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:2px 0 16px}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 15px;box-shadow:var(--shadow)}}
.stat .num{{font-size:28px;font-weight:700;color:var(--brand);line-height:1.1}}{{}}
.stat .lbl{{font-size:12px;color:var(--muted);margin-top:2px}}
.stat .num.red{{color:#b91c1c}} .stat .num.amber{{color:#c2410c}} .stat .num.blue{{color:#155e75}}
.grid2{{display:grid;grid-template-columns:1.15fr .85fr;gap:14px}}
.box{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:15px 17px;box-shadow:var(--shadow);margin-bottom:14px}}
.box h3{{margin:0 0 9px;font-size:14.5px;color:var(--brand);display:flex;align-items:center;gap:8px}}
.box h3::before{{content:"";width:4px;height:15px;background:var(--gold);border-radius:2px;display:inline-block}}
.box p{{margin:0 0 8px;font-size:13.4px;text-align:justify}}
.uinote{{background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:8px 12px;font-size:12.4px;color:#7c2d12;margin-top:10px}}
ol.top{{padding-left:0;margin:0;list-style:none}}
.toprow{{display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-bottom:1px dashed var(--line);cursor:pointer;font-size:13.2px}}
.toprow:hover{{color:var(--accent)}} .toprow:last-child{{border-bottom:0}}
.sev{{display:inline-block;padding:0 7px;border-radius:5px;font-size:11px;font-weight:700;white-space:nowrap}}
.bars{{display:flex;gap:8px;align-items:flex-end;height:110px;padding:6px 2px 0;border-bottom:1px solid var(--line)}}
.tbi{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:3px}}
.tbi i{{font-style:normal;font-size:11px;color:var(--brand);font-weight:700}}
.tbi::before{{content:"";display:block;width:60%;height:var(--h);min-height:6px;
  background:linear-gradient(180deg,#155e75,#0b3350);border-radius:4px 4px 0 0}}
.tbi span{{font-size:10.5px;color:var(--muted);padding-bottom:4px}}
.miss{{color:#9a3412}}
.disclaimer{{background:#fff1f2;border:1px solid #fecdd3;color:#881337;border-radius:10px;padding:12px 14px;font-size:12.4px;margin-top:6px}}
.disclaimer b{{color:#9f1239}}
.toolbar{{position:sticky;top:47px;background:var(--bg);z-index:50;padding:9px 20px 10px;border-bottom:1px solid var(--line);
  display:flex;flex-direction:column;gap:7px}}
.toolbar .row{{display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.toolbar .lbl{{font-size:12px;color:var(--muted);margin-right:2px;min-width:34px}}
.tbtn,.kbtn,.sbtn{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:3px 10px;font-size:12.3px;
  cursor:pointer;font-family:inherit;color:#334155;transition:all .12s}}
.tbtn b,.kbtn b{{font-weight:700;color:var(--brand);margin-left:4px}}
.tbtn.active{{background:var(--tc);border-color:transparent;color:#fff}} .tbtn.active b{{color:#fff}}
.kbtn.active{{background:var(--brand);color:#fff;border-color:transparent}} .kbtn.active b{{color:#fff}}
.sbtn{{opacity:.55}} .sbtn.active{{opacity:1;box-shadow:0 0 0 2px #fff,0 0 0 3px currentColor}}
.btn{{border:1px solid var(--brand);background:var(--brand);color:#fff;border-radius:8px;padding:5px 11px;font-size:12.3px;
  cursor:pointer;font-family:inherit}}
.btn.ghost{{background:#fff;color:var(--brand)}}
.btn.ghost:hover{{background:#e0f2fe}}
#search{{flex:1;min-width:200px;border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-family:inherit;font-size:12.8px}}
.ws{{display:grid;grid-template-columns:var(--left) 1fr;border-top:1px solid var(--line)}}
.wsL,.wsR{{height:calc(100vh - 150px);overflow:auto;scroll-behavior:smooth}}
.wsL{{background:#fdfcf8;border-right:1px solid var(--line);padding:10px 14px 90px}}
.wsR{{padding:12px 16px 90px;background:#eef2f6}}
.page-mark{{font-size:10.5px;color:#94a3b8;letter-spacing:.14em;margin:14px 0 4px;text-align:center;
  border-top:1px dashed #cbd5e1;padding-top:5px}}
.csec{{margin-bottom:14px}}
.csec h3{{font-size:14px;margin:14px 0 7px;color:var(--brand);border-left:4px solid var(--gold);padding-left:9px;
  display:flex;align-items:center;gap:8px;font-weight:700}}
.sec-no{{background:var(--brand);color:#fff;border-radius:4px;font-size:11.5px;padding:1px 7px;font-weight:600}}
.clause{{padding:7px 10px;border-radius:8px;margin:3px 0;transition:background .15s}}
.clause:hover{{background:#f4f7fa}}
.clause.strong .en{{font-weight:700;color:var(--brand)}}
.clause.flash{{background:#fef3c7;box-shadow:inset 0 0 0 2px var(--gold)}}
.clause-h{{display:flex;align-items:center;gap:7px;font-size:11px;color:#64748b;margin-bottom:2px}}
.cno{{font-weight:700;color:#334155;font-family:Consolas,Menlo,monospace;font-size:11.5px}}
.cpg{{background:#f1f5f9;border-radius:4px;padding:0 5px;font-size:10.5px}}
.chips{{margin-left:auto;display:flex;gap:3px}}
.chip{{border:0;border-radius:4px;font-size:10.2px;padding:0 5px;cursor:pointer;font-weight:700;color:#fff;background:#64748b}}
.chip.s5{{background:#b91c1c}} .chip.s4{{background:#ea580c}} .chip.s3{{background:#d97706}} .chip.s2{{background:#16a34a}}
.en{{font-size:13.1px;color:#111827;text-align:justify;font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;line-height:1.62}}
.zh{{font-size:12.6px;color:#475569;text-align:justify;margin-top:3px;padding-left:8px;border-left:2px solid #dbeafe}}
.zh-inline{{font-size:12px;color:#64748b;margin-left:6px}}
.tc{{display:inline-block;margin-right:12px}}
.clause.k-table_row .en{{font-size:12.4px;font-family:"Segoe UI",Arial,sans-serif}}
.clause.k-table_head .en,.clause.k-table_head .zh-inline{{font-weight:700;color:var(--brand)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:11px;margin-bottom:11px;overflow:hidden;
  box-shadow:var(--shadow);transition:box-shadow .2s}}
.card.flash{{box-shadow:0 0 0 3px var(--gold),0 8px 20px rgba(245,158,11,.25)}}
.card-h{{display:flex;align-items:center;gap:6px;padding:8px 12px;background:#f8fafc;border-bottom:1px solid var(--line);
  cursor:pointer;flex-wrap:wrap}}
.rid{{font-family:Consolas,Menlo,monospace;font-weight:700;color:var(--brand);font-size:12.5px}}
.topic{{font-size:11px;padding:1px 7px;border-radius:5px;color:#fff;font-weight:600}}
.kind{{font-size:11px;padding:1px 7px;border-radius:5px;background:#eef2ff;color:#3730a3;font-weight:600}}
.kind.k-缺失{{background:#fde68a;color:#78350f}}
.kind.k-表述不清{{background:#dbeafe;color:#1e3a8a}}
.kind.k-写了但对我方不利{{background:#fee2e2;color:#991b1b}}
.pill{{margin-left:auto;font-size:11px;color:#64748b;border:1px dashed #cbd5e1;border-radius:999px;padding:0 8px}}
.pill.set{{color:#065f46;border-color:#6ee7b7;background:#ecfdf5}}
.caret{{color:#94a3b8;transition:transform .2s}} .card.open .caret{{transform:rotate(90deg)}}
.card-t{{margin:9px 13px 0;font-size:14px;line-height:1.5;color:#111827;font-weight:700}}
.card-b{{display:none;padding:8px 13px 13px}} .card.open .card-b{{display:block}}
.card section{{margin-top:10px}}
.card h5{{margin:0 0 4px;font-size:11.6px;color:var(--brand);letter-spacing:.03em;font-weight:700}}
.card p{{margin:0 0 3px;font-size:12.9px;color:#334155;text-align:justify}}
.quote{{margin:5px 0;padding:6px 9px;background:#f8fafc;border-left:3px solid #94a3b8;border-radius:0 6px 6px 0;
  display:flex;flex-direction:column;gap:2px}}
.qsrc{{font-size:10.8px;color:#64748b;font-family:Consolas,Menlo,monospace}}
.qtext{{font-size:12.2px;color:#0f172a;font-family:"Segoe UI",Arial,sans-serif;line-height:1.55}}
.noquote{{font-size:12.2px;color:#9a3412;background:#fff7ed;border-left:3px solid #fdba74;padding:6px 9px;border-radius:0 6px 6px 0}}
.anchors{{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}}
.anchor{{border:1px solid #cbd5e1;background:#f8fafc;border-radius:6px;padding:2px 8px;font-size:11.4px;cursor:pointer;
  color:var(--brand);font-family:inherit}}
.anchor:hover{{background:#e0f2fe;border-color:#7dd3fc}}
.miss-flag{{display:inline-block;background:#fef3c7;color:#92400e;font-size:11px;font-weight:700;border-radius:4px;
  padding:0 6px;margin-bottom:3px}}
.cons,.todo{{margin:2px 0 0;padding-left:17px;font-size:12.6px;color:#334155}}
.cons li::marker{{color:#dc2626}} .todo li::marker{{color:#0f766e}}
.basis{{font-size:11.5px;color:#64748b;background:#f8fafc;border-radius:5px;padding:4px 7px;margin-top:5px}}
.chips-lite span{{display:inline-block;font-size:11px;background:#eef2f7;border-radius:5px;padding:1px 7px;
  margin:2px 4px 0 0;color:#334155}}
.ctrl{{background:#f8fafc;border:1px dashed #cbd5e1;border-radius:8px;padding:8px 10px}}
.ctrl-row{{display:flex;gap:8px;flex-wrap:wrap}}
.ctrl-row label,.ctrl .fb{{display:flex;gap:5px;align-items:center;font-size:11.6px;color:#475569}}
.ctrl-row label{{flex:1;min-width:130px}}
.ctrl input,.ctrl select,.ctrl textarea{{border:1px solid var(--line);border-radius:6px;padding:3px 7px;
  font-family:inherit;font-size:12.2px;background:#fff}}
.ctrl input{{flex:1;min-width:80px}} .ctrl select{{flex:1}}
.ctrl .fb{{margin-top:6px;align-items:flex-start}} .ctrl textarea{{flex:1;resize:vertical}}
.qbtns{{display:flex;gap:7px;margin:2px 0 12px;flex-wrap:wrap}}
.qbtn{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 14px;cursor:pointer;
  font-family:inherit;font-size:12.8px}}
.qbtn.active{{background:var(--brand);color:#fff;border-color:transparent}}
.qpane{{display:none}} .qpane.active{{display:block}}
.qdesc{{color:var(--muted);font-size:12.3px;margin:0 0 8px}}
table.qtable,table.law{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;
  font-size:12.4px;box-shadow:var(--shadow)}}
.qtable th,table.law th{{background:var(--brand);color:#fff;text-align:left;padding:8px 10px;font-weight:600;font-size:12.2px}}
.qtable td,table.law td{{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
.qtable tbody tr{{cursor:pointer}} .qtable tbody tr:hover{{background:#f0f9ff}}
.mono{{font-family:Consolas,Menlo,monospace;color:var(--brand);font-weight:600;white-space:nowrap}}
.pri{{font-size:11px;padding:0 7px;border-radius:5px;font-weight:700;color:#fff}}
.p-高{{background:#b91c1c}} .p-中{{background:#d97706}} .p-低{{background:#64748b}}
.ck{{text-align:center}}
.st{{font-size:11.6px;padding:0 7px;border-radius:5px;white-space:nowrap}}
.st.ok{{background:#dcfce7;color:#166534}} .st.warn{{background:#fef3c7;color:#92400e}}
.letter{{background:#0f172a;color:#e2e8f0;border-radius:10px;padding:16px;font-size:12.4px;line-height:1.7;
  white-space:pre-wrap;font-family:Consolas,"Segoe UI",Menlo,monospace;overflow:auto;max-height:70vh}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:11.8px;color:#475569;margin:6px 0 10px}}
.foot{{padding:16px 22px;color:var(--muted);font-size:11.8px;border-top:1px solid var(--line);margin-top:16px}}
ul.plain{{margin:4px 0 10px;padding-left:18px;font-size:12.7px;color:#334155}}
@media(max-width:1080px){{.ws{{grid-template-columns:1fr}} .wsL,.wsR{{height:auto}} .grid2{{grid-template-columns:1fr}}
  .cards4{{grid-template-columns:repeat(2,1fr)}} .toolbar{{position:static}}}}
@media print{{.tabs,.toolbar,.ctrl,.btn,.demo-banner{{display:none}} .ws{{display:block}}
  .wsL,.wsR{{height:auto;overflow:visible}} .card-b{{display:block}} .panel{{display:block}}}}
</style>
</head>
<body>
<div class="demo-banner">⚠ <b>模拟合同（Simulated Contract）</b>：本页所审合同为培训用模拟编写，双方名称、地址、金额、银行与条款均不对应任何真实交易或主体。审查结论仅用于演示外贸采购合同审查方法。</div>
<header class="hero">
  <div class="kicker">外贸采购合同审阅 · International Procurement Contract Review</div>
  <h1>{contract_title}</h1>
  <div class="meta">
    <span>合同编号 <b>{contract_no}</b></span>
    <span>我方身份 <b>{review_as}</b></span>
    <span>卖方 <b>{supplier}</b></span>
    <span>签订日期 <b>{sign_date}</b></span>
  </div>
  <div class="meta">
    <span>审查日期 <b>{review_date}</b></span><span>审查人 <b>{reviewer}</b></span>
    <span>合同状态 <b>{signed}</b></span><span>页数 <b>{pages}</b></span>
  </div>
  <div class="pills">
    <span class="pill">标的：{product}</span><span class="pill">术语：{incoterms}</span>
    <span class="pill">数据截止：{data_cutoff}</span><span class="pill">法规核对日期：{law_date}</span>
  </div>
</header>
<nav class="tabs">
  <button class="active" data-panel="overview">总览</button>
  <button data-panel="workspace">原文 × 风险（双栏）</button>
  <button data-panel="index">条款索引</button>
  <button data-panel="tasks">问题清单</button>
  <button data-panel="laws">法规核对</button>
  <button data-panel="letter">英文澄清函</button>
  <button data-panel="negative">负结果</button>
  <button data-panel="method">方法与边界</button>
</nav>

<section class="panel active" id="panel-overview">
  <div class="cards4">
    <div class="stat"><div class="num">{n_total}</div><div class="lbl">风险条目</div></div>
    <div class="stat"><div class="num red">{n_high}</div><div class="lbl">高及以上（4–5 级）</div></div>
    <div class="stat"><div class="num amber">{n_missing}</div><div class="lbl">缺失（合同未约定）</div></div>
    <div class="stat"><div class="num amber">{n_unclear}</div><div class="lbl">表述不清 / 冲突</div></div>
    <div class="stat"><div class="num blue">{n_clauses}</div><div class="lbl">被引用的原文条款</div></div>
    <div class="stat"><div class="num blue">{n_conf}</div><div class="lbl">待确认问题</div></div>
  </div>
  <div class="grid2">
    <div class="box"><h3>一句话结论</h3><p>{headline}</p>
      <div class="uinote">内部备注：{user_note}</div></div>
    <div class="box"><h3>风险主题分布</h3><div class="bars">{topicbar}</div>
      <p style="font-size:11.6px;color:#64748b;margin-top:10px">{calc_note}</p></div>
  </div>
  <div class="grid2">
    <div class="box"><h3>最需要先处理的 10 条（按严重度）</h3><ol class="top">{top_rows}</ol></div>
    <div class="box"><h3>合同未约定 / 需补齐（缺失，不作推测）</h3><ul class="plain">{missing_list}</ul></div>
  </div>
  <div class="grid2">
    <div class="box"><h3>本次审查范围</h3><p>{scope}</p></div>
    <div class="box"><h3>已收到 / 未取得文件</h3><ul class="plain">{files_ok}</ul><ul class="plain">{files_no}</ul></div>
  </div>
  <div class="disclaimer"><b>本结果仅作为商务审查提醒，不构成法律意见。</b> {disclaimer}</div>
</section>

<section class="panel" id="panel-workspace">
  <div class="toolbar">
    <div class="row"><span class="lbl">主题</span><button class="tbtn active" data-topic="all">全部</button>{topic_filter}</div>
    <div class="row"><span class="lbl">类型</span><button class="kbtn active" data-kind="all">全部</button>{kind_filter}
      <span class="lbl" style="margin-left:10px">严重度</span>{sev_filter}</div>
    <div class="row">
      <input id="search" placeholder="搜索：标题 / 原文 / 中文解释 / 待确认（例：预付款、提单、异议期、仲裁、CAS）">
      <button class="btn ghost" id="btn-open">展开全部</button>
      <button class="btn ghost" id="btn-close">收起全部</button>
      <button class="btn ghost" id="btn-export">导出处理状态 JSON</button>
      <button class="btn ghost" id="btn-csv">导出中英对照清单 CSV</button>
      <span id="count" style="font-size:12px;color:#64748b"></span>
    </div>
  </div>
  <div class="ws">
    <div class="wsL" id="left">{contract_html}</div>
    <div class="wsR" id="right">{cards}</div>
  </div>
</section>

<section class="panel" id="panel-index">
  <p class="qdesc">条款索引是全文锚点：点击任一行跳转到「原文 × 风险」并高亮。风险编号列显示引用了该条款的全部风险条目。</p>
  <table class="qtable" id="idxtable"><thead><tr><th>条款ID</th><th>条款编号</th><th>页码</th><th>原文摘要（逐字）</th><th>关联风险</th></tr></thead>
  <tbody><!--INDEX_ROWS--></tbody></table>
</section>

<section class="panel" id="panel-tasks">
  <p class="qdesc">同一批风险按「谁去办」拆成三张清单。点击任意行定位到原文与风险卡；勾选状态保存在本浏览器。供应商清单可直接作为澄清函附件。</p>
  {q_html}
</section>

<section class="panel" id="panel-laws">
  <p class="qdesc">适用性核对日期：<b>{law_date}</b>。下表只说明「该法规/规则/标准是否存在、是否现行、与本合同的关联点」，<b>不</b>据此对合同效力下结论；正式签约或索赔前须再次核对权威渠道。</p>
  <table class="law"><thead><tr><th>法规 / 规则 / 标准</th><th>适用点</th><th>核验状态</th><th>核验依据（来源+日期）</th><th>与本合同的关联</th></tr></thead>
  <tbody>{law_rows}</tbody></table>
  <div class="disclaimer"><b>本结果仅作为商务审查提醒，不构成法律意见。</b> {disclaimer}</div>
</section>

<section class="panel" id="panel-letter">
  <p class="qdesc">下列英文草稿用于向海外供应商提出条款澄清与修改要求，按「付款—交货—质量—索赔—运输—争议」分组，可直接复制或下载为 .txt。发出前请由采购负责人与法务确认措辞与商务立场。</p>
  {letter}
</section>

<section class="panel" id="panel-method">
  <div class="grid2">
    <div class="box"><h3>本次审查步骤</h3><ol class="plain">{method_steps}</ol></div>
    <div class="box"><h3>标的专项提醒（MEG）</h3><ul class="plain">{method_product}</ul></div>
  </div>
  <div class="box"><h3>商务审查与法律意见的边界</h3>
    <p>本页输出的是<b>业务审查提示</b>：说明合同写了什么、哪些没写清楚、可能产生哪些采购与进口业务后果、建议向谁确认。</p>
    <p>它<b>不是法律意见</b>：不对条款效力、是否可执行、法律责任的分配、仲裁条款是否有效、危险化学品/危险货物的法律定性作出结论；上述事项由公司法务或外部律师判断。</p>
    <p>{boundary}</p>
    <p>数据来源限定为：用户提供的合同文本 + 公开可核验的法规、规则与标准。合同以外的事实（卖方资质、实际生产商、履约能力）一律标为「未提供/需核实」，不作推测。</p>
    <p>处理状态、内部负责人与供应商反馈仅保存在当前浏览器的 localStorage；需要共享时点击「导出处理状态 JSON」，把文件回传采购负责人汇总。</p>
  </div>
  <div class="box"><h3>图例</h3><div class="legend">
    <span><span class="sev" style="background:#b91c1c;color:#fff">极高 5</span> 可能直接造成重大资金损失或停产</span>
    <span><span class="sev" style="background:#ea580c;color:#fff">高 4</span> 大概率损失或履约受限，需修约</span>
    <span><span class="sev" style="background:#fcd34d;color:#7c2d12">中 3</span> 商务摩擦或成本增加，可执行中管控</span>
    <span><span class="kind k-缺失">缺失</span> 全文无该约定</span>
    <span><span class="kind k-表述不清">表述不清</span> 有约定但口径/起算点/主体不明或冲突</span>
    <span><span class="kind k-写了但对我方不利">写了但对我方不利</span> 明确约定，方向对我方不利</span>
  </div></div>
  <div class="disclaimer"><b>本结果仅作为商务审查提醒，不构成法律意见。</b> {disclaimer}</div>
</section>


<section class="panel" id="panel-negative">
  <p class="qdesc">「没有列为风险」不等于「没有审查」。本节列出已逐条审阅但未发现需单列风险的条款，以及未引用条款的处理说明。</p>
  <div class="grid2">
    <div class="box"><h3>条款覆盖情况</h3>
      <p>合同条款总数 <b>{n_neg_total}</b> 条；被风险条目引用 <b>{n_neg_hit}</b> 条；未引用但列入负结果 <b>{n_neg_covered}</b> 条；未覆盖 <b>{n_neg_left}</b> 条。</p>
      <p style="font-size:12.4px;color:#475569">「未引用」的条款通常是说明性文字（封面、表头）或审查后认为可接受的条款，其全文仍可在「原文 × 风险」页左栏查看。</p>
    </div>
    <div class="box"><h3>本次未取得的材料（影响审查深度）</h3><ul class="plain">{files_no}</ul></div>
  </div>
  {neg_html}
</section>

<div class="foot">共 {n_total} 条风险 · 由 Skill「审阅外贸采购合同」生成 · 单文件离线可用 · 打印时自动展开全部卡片 · 本页不构成法律意见</div>

<script>
(function(){{
  var STATUS = {status_json};
  var SEED = {seed};
  var BSCSV = {bscsv};
  var KEY = 'ipcr-' + document.title.slice(0, 60);
  var store = {{}};
  try {{ store = JSON.parse(localStorage.getItem(KEY) || '{{}}'); }} catch(e) {{ store = {{}}; }}
  Object.keys(SEED).forEach(function(k){{ if(!store[k]) store[k] = SEED[k]; }});
  function save(){{ try {{ localStorage.setItem(KEY, JSON.stringify(store)); }} catch(e){{}} }}

  // ---- tabs
  var tabs = [].slice.call(document.querySelectorAll('.tabs button'));
  tabs.forEach(function(b){{ b.addEventListener('click', function(){{
    tabs.forEach(function(x){{x.classList.remove('active')}}); b.classList.add('active');
    [].slice.call(document.querySelectorAll('.panel')).forEach(function(p){{p.classList.remove('active')}});
    var el = document.getElementById('panel-' + b.dataset.panel); if(el) el.classList.add('active');
    window.scrollTo(0,0);
  }});}});
  function switchTab(name){{ var b = document.querySelector('.tabs button[data-panel="' + name + '"]'); if(b) b.click(); }}

  // ---- cards
  var cards = [].slice.call(document.querySelectorAll('.card'));
  cards.forEach(function(c){{
    var id = c.dataset.id;
    if(store[id]) apply_store(c, store[id]);
    c.querySelector('[data-toggle]').addEventListener('click', function(){{ c.classList.toggle('open'); }});
    var st = c.querySelector('[data-status]');
    if(st) st.addEventListener('change', function(e){{ (store[id] = store[id] || {{}}).status = e.target.value; save(); paint(c, e.target.value); }});
    var ow = c.querySelector('[data-owner]');
    if(ow) ow.addEventListener('input', function(e){{ (store[id] = store[id] || {{}}).owner = e.target.value; save(); }});
    var fb = c.querySelector('[data-feedback]');
    if(fb) fb.addEventListener('input', function(e){{ (store[id] = store[id] || {{}}).feedback = e.target.value; save(); }});
    [].slice.call(c.querySelectorAll('.anchor')).forEach(function(b){{
      b.addEventListener('click', function(){{ gotoClause(b.dataset.gotoClause); }});
    }});
  }});
  function paint(c, s){{
    var pill = c.querySelector('[data-pill]'); if(!pill) return;
    pill.textContent = s || '待处理';
    pill.classList.toggle('set', !!s && s !== '待处理');
  }}
  function apply_store(c, v){{
    var id = c.dataset.id, s = c.querySelector('[data-status]');
    if(s && v.status) s.value = v.status;
    var o = c.querySelector('[data-owner]'); if(o && v.owner) o.value = v.owner;
    var f = c.querySelector('[data-feedback]'); if(f && v.feedback) f.value = v.feedback;
    paint(c, v.status);
  }}

  // ---- 定位
  function gotoClause(cid, alsoCard){{
    switchTab('workspace');
    var el = document.getElementById('clause-' + cid); if(!el) return;
    el.scrollIntoView({{behavior:'smooth', block:'center'}});
    el.classList.add('flash'); setTimeout(function(){{ el.classList.remove('flash'); }}, 1800);
    if(alsoCard !== false){{ var chip = el.querySelector('.chip'); if(chip) openFinding(chip.dataset.gotoFinding, true); }}
  }}
  function openFinding(id, keepScroll){{
    switchTab('workspace');
    var card = document.getElementById('finding-' + id); if(!card) return;
    resetFilters();
    card.classList.add('open');
    card.scrollIntoView({{behavior:'smooth', block: 'start'}});
    card.classList.add('flash'); setTimeout(function(){{ card.classList.remove('flash'); }}, 1800);
  }}
  [].slice.call(document.querySelectorAll('[data-goto-finding]')).forEach(function(el){{
    el.addEventListener('click', function(e){{
      if(e.target.tagName === 'INPUT' || e.target.closest('label')) return;
      openFinding(el.dataset.gotoFinding);
    }});
  }});
  [].slice.call(document.querySelectorAll('[data-goto-clause]')).forEach(function(el){{
    el.addEventListener('click', function(){{ gotoClause(el.dataset.gotoClause); }});
  }});

  // ---- 筛选
  var curT = 'all', curK = 'all', curS = {{}}, q = '';
  var tbtns = [].slice.call(document.querySelectorAll('.tbtn'));
  var kbtns = [].slice.call(document.querySelectorAll('.kbtn'));
  var sbtns = [].slice.call(document.querySelectorAll('.sbtn'));
  tbtns.forEach(function(b){{ b.addEventListener('click', function(){{
    curT = b.dataset.topic;
    tbtns.forEach(function(x){{ x.classList.toggle('active', x === b); }});
    apply();
  }});}});
  kbtns.forEach(function(b){{ b.addEventListener('click', function(){{
    curK = b.dataset.kind;
    kbtns.forEach(function(x){{ x.classList.toggle('active', x === b); }});
    apply();
  }});}});
  sbtns.forEach(function(b){{ b.addEventListener('click', function(){{
    var v = b.dataset.sev;
    if(curS[v]) {{ delete curS[v]; b.classList.remove('active'); }} else {{ curS[v] = 1; b.classList.add('active'); }}
    apply();
  }});}});
  var search = document.getElementById('search');
  if(search) search.addEventListener('input', function(e){{ q = e.target.value.trim().toLowerCase(); apply(); }});
  function resetFilters(){{
    curT='all'; curK='all'; curS={{}}; q='';
    if(search) search.value='';
    tbtns.forEach(function(x){{ x.classList.toggle('active', x.dataset.topic === 'all'); }});
    kbtns.forEach(function(x){{ x.classList.toggle('active', x.dataset.kind === 'all'); }});
    sbtns.forEach(function(x){{ x.classList.remove('active'); }});
    apply();
  }}
  function visible(c){{
    if(curT !== 'all' && c.dataset.topic !== curT) return false;
    if(curK !== 'all' && c.dataset.kind !== curK) return false;
    if(Object.keys(curS).length && !curS[c.dataset.sev]) return false;
    if(q && (c.dataset.search + ' ' + c.textContent.toLowerCase()).indexOf(q) === -1) return false;
    return true;
  }}
  function apply(){{
    var n = 0, shown = {{}};
    cards.forEach(function(c){{ var v = visible(c); c.style.display = v ? '' : 'none'; if(v){{ n++; shown[c.dataset.id] = 1; }} }});
    var cnt = document.getElementById('count'); if(cnt) cnt.textContent = '显示 ' + n + ' / ' + cards.length + ' 条';
    var any = (curT !== 'all' || curK !== 'all' || Object.keys(curS).length || q);
    [].slice.call(document.querySelectorAll('.clause')).forEach(function(cl){{
      if(!any) {{ cl.style.opacity = ''; return; }}
      var on = false;
      [].slice.call(cl.querySelectorAll('.chip')).forEach(function(ch){{ if(shown[ch.dataset.gotoFinding]) on = true; }});
      cl.style.opacity = on ? '' : '.32';
    }});
  }}
  apply();
  var bo = document.getElementById('btn-open'), bc = document.getElementById('btn-close');
  if(bo) bo.addEventListener('click', function(){{ cards.forEach(function(c){{ if(c.style.display !== 'none') c.classList.add('open'); }}); }});
  if(bc) bc.addEventListener('click', function(){{ cards.forEach(function(c){{ c.classList.remove('open'); }}); }});
  function download(name, text, mime){{
    var blob = new Blob([text], {{type: mime}});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function(){{ a.remove(); }}, 200);
  }}
  var be = document.getElementById('btn-export');
  if(be) be.addEventListener('click', function(){{ download('contract-review-status.json', JSON.stringify(store, null, 2), 'application/json'); }});
  var bcsv = document.getElementById('btn-csv');
  if(bcsv) bcsv.addEventListener('click', function(){{ download('bilingual-issue-list.csv', '\ufeff' + BSCSV, 'text/csv;charset=utf-8'); }});

  // ---- 问题清单页签
  [].slice.call(document.querySelectorAll('.qbtn')).forEach(function(b){{ b.addEventListener('click', function(){{
    [].slice.call(document.querySelectorAll('.qbtn')).forEach(function(x){{ x.classList.remove('active'); }});
    b.classList.add('active');
    [].slice.call(document.querySelectorAll('.qpane')).forEach(function(p){{ p.classList.toggle('active', p.dataset.owner === b.dataset.owner); }});
  }});}});
}})();
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="生成外贸采购合同审阅 HTML 报告")
    ap.add_argument("--dir", required=True, help="案例目录（含 contract.json 与 review.json）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--status-seed", default=None)
    ap.add_argument("--user-note", default="")
    ap.add_argument("--letter", default=None, help="英文澄清函 txt 路径（可选）")
    a = ap.parse_args()
    seed = json.loads(Path(a.status_seed).read_text(encoding="utf-8")) if a.status_seed else None
    info = build(Path(a.dir), Path(a.out), a.title, seed, a.user_note,
                 Path(a.letter) if a.letter else None)
    print(json.dumps({"ok": True, **info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
