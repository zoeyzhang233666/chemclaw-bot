"""把审查数据编译成自包含的交互式 HTML 合同审查页面。

用法:
    python build_review_html.py --dir <案例目录> --out <输出.html>
        [--title "…"] [--status-seed <status.json>] [--user-note "内部备注…"]

输出特点:
  * 单文件、无外部依赖、可离线双击打开；
  * 左栏为合同原文（按章/条/页渲染，带条款锚点 <a id="clause-C01">）；
  * 右栏为风险提示卡，点击卡片高亮并滚动定位到原文条款；
  * 按主题 / 风险类型 / 严重程度筛选，支持关键词搜索；
  * 三类问题清单（采购 / 法务 / 供应商）独立标签页；
  * 处理状态与备注保存在浏览器 localStorage，可导出 JSON 回传。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import esc, excerpt, load_case, validate_case

TOPIC_COLORS = {
    "quality": "#0e7490", "quantity": "#7c3aed", "delivery": "#1d4ed8",
    "packaging": "#b45309", "measure": "#475569", "price": "#0f766e",
    "payment": "#be185d", "safety": "#b91c1c", "breach": "#9333ea",
    "forcemajeure": "#64748b", "dispute": "#334155", "general": "#6b7280",
}


def sev_meta(sev: int) -> tuple[str, str, str]:
    """(label, text color, bg color)"""
    return {
        5: ("极高", "#ffffff", "#b91c1c"),
        4: ("高", "#ffffff", "#ea580c"),
        3: ("中", "#7c2d12", "#fcd34d"),
        2: ("低", "#14532d", "#bbf7d0"),
        1: ("提示", "#1e3a8a", "#dbeafe"),
    }[sev]


def render_clause(c: dict, hits: list[dict], sec_lookup: dict) -> str:
    chip = ""
    if hits:
        chips = "".join(
            f'<button class="hit-chip s{h["severity"]}" data-goto-finding="{esc(h["id"])}" title="{esc(h["title"])}">{esc(h["id"])}</button>'
            for h in hits
        )
        chip = f'<div class="clause-chips">{chips}</div>'
    extra = ""
    if c.get("kind") == "table_row":
        extra = ' style="padding-left:34px"'
    text = esc(c["text"]).replace("　", " ")
    return (
        f'<div class="clause{" flagged" if hits else ""}" id="clause-{esc(c["id"])}" data-clause="{esc(c["id"])}"{extra}>'
        f'<div class="clause-no">{esc(c["no"])}<span class="pg">P{c["page"]}</span>{chip}</div>'
        f'<div class="clause-text">{text}</div></div>'
    )


def render_attachment(att: dict) -> str:
    head = f'<div class="att-head">{esc(att["no"])}　{esc(att["title"])}<span class="pg">P{att["page"]}</span></div>'
    body = ""
    table = att.get("table")
    if table:
        rows = "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in r) + "</tr>" for r in table["rows"])
        head_cols = "".join(f"<th>{esc(h)}</th>" for h in table["cols"])
        body = f'<table class="c-table"><caption>{esc(table["caption"])}</caption><thead><tr>{head_cols}</tr></thead><tbody>{rows}</tbody></table>'
        if table.get("note"):
            body += f'<p class="att-note">{esc(table["note"])}</p>'
    if att.get("list"):
        body += "<ol class='att-list'>" + "".join(f"<li>{esc(x)}</li>" for x in att["list"]) + "</ol>"
    return f"<section class='attachment' id='att-{esc(att['no'])}'>{head}{body}</section>"


def render_finding_card(f: dict, clauses: dict, topic_name: dict) -> str:
    label, fg, bg = sev_meta(f["severity"])
    color = TOPIC_COLORS.get(f["topic"], "#475569")
    anchors = "".join(
        f'<button class="anchor-btn" data-goto-clause="{esc(cid)}">📍 {esc(clauses[cid]["no"])} · P{clauses[cid]["page"]}</button>'
        for cid in f["clause_ids"] if cid in clauses
    )
    quotes = "".join(
        f'<blockquote class="quote"><span class="q-src">{esc(clauses[cid]["no"])} · 第{clauses[cid]["page"]}页</span>'
        f'<span class="q-text">“{esc(excerpt(clauses[cid]["text"], 190))}”</span></blockquote>'
        for cid in f["clause_ids"] if cid in clauses
    )
    confirms = "".join(f'<li>{esc(q)}</li>' for q in f["to_confirm"])
    laws = ""
    if f.get("law_refs"):
        laws = '<div class="sec"><h5>核对的法律 / 标准（适用性以文末为准）</h5><div class="law-chips">' + "".join(
            f"<span>{esc(x)}</span>" for x in f["law_refs"]) + "</div></div>"
    return f"""
<article class="fcard" id="finding-{esc(f['id'])}" data-id="{esc(f['id'])}" data-topic="{esc(f['topic'])}"
         data-kind="{esc(f['kind'])}" data-sev="{f['severity']}" data-clauses="{esc(','.join(f['clause_ids']))}"
         data-search="{esc((f['title'] + f['what_written'] + f['business_impact'] + ' '.join(f['to_confirm'])).lower())}">
  <header class="fc-head" data-jump>
    <span class="rid">{esc(f['id'])}</span>
    <span class="sev" style="color:{fg};background:{bg}">{label} · {f['severity']}</span>
    <span class="topic" style="color:#fff;background:{color}">{esc(topic_name.get(f['topic'], f['topic']))}</span>
    <span class="kind k-{esc(f['kind'])}">{esc(f['kind'])}</span>
    <span class="status-pill" data-status-pill>{esc(f.get('status', '待处理'))}</span>
    <span class="caret">▸</span>
  </header>
  <h4 class="fc-title">{esc(f['title'])}</h4>
  <div class="fc-body">
    <div class="sec"><h5>合同写了什么（原文摘录）</h5><p>{esc(f['what_written'])}</p>{quotes}</div>
    <div class="sec"><h5>原文位置</h5><div class="anchors">{anchors}</div></div>
    <div class="sec"><h5>哪些没写清楚 / 缺失</h5>{'<p class="missing">⚠ 本项在合同中未见约定（缺失），不作推测。</p>' if f['kind'] == '缺失' else ''}<p>{esc(f['what_missing'])}</p></div>
    <div class="sec"><h5>业务风险与可能后果</h5><p>{esc(f['business_impact'])}</p><ul class="cons">{''.join(f'<li>{esc(x)}</li>' for x in f.get('consequences', []))}</ul></div>
    <div class="sec"><h5>需要向谁确认 / 确认什么</h5><ul class="todo">{confirms}</ul></div>
    {laws}
    <div class="sec note-sec">
      <h5>处理状态与备注（仅存于本浏览器，可导出）</h5>
      <div class="note-controls">
        <select data-status>{"".join(f'<option>{s}</option>' for s in ["待处理", "已确认", "待供应商回复", "已解决", "不适用"])}</select>
        <input type="text" data-note placeholder="内部处理备注…">
      </div>
    </div>
  </div>
</article>"""


def render_question_tables(review: dict, findings: dict, titles: dict[str, tuple[str, str]]) -> str:
    tabs = []
    for i, (owner, items) in enumerate(review.get("confirmations", {}).items()):
        label, desc = titles.get(owner, (owner, ""))
        rows = "".join(
            f'<tr data-goto-finding="{esc(q["finding_id"])}" class="qrow">'
            f'<td class="mono">{esc(q["finding_id"])}</td>'
            f'<td><span class="pr pr-{esc(q["priority"])}">{esc(q["priority"])}</span></td>'
            f'<td class="t">{esc(titles.get(q["finding_id"], (findings[q["finding_id"]]["title"],))[0] if q["finding_id"] in titles else findings[q["finding_id"]]["title"])}</td>'
            f'<td>{esc(q["question"])}</td>'
            f'<td class="mono">{esc(", ".join(findings[q["finding_id"]]["clause_ids"]))}</td>'
            f'<td><label class="chk"><input type="checkbox" data-qbox="{esc(owner)}-{esc(q["finding_id"])}"></label></td></tr>'
            for q in items
        )
        tabs.append(
            f'<div class="qtab{" active" if i == 0 else ""}" data-owner="{esc(owner)}">'
            f'<p class="qtab-desc">{esc(desc)}</p>'
            '<table class="qtable"><thead><tr><th>关联风险</th><th>优先级</th><th>风险标题</th><th>需要确认的问题</th><th>条款</th><th>已处理</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>"
        )
    buttons = "".join(
        f'<button class="qtab-btn{" active" if i == 0 else ""}" data-owner="{esc(owner)}">{esc(titles.get(owner, (owner, ""))[0])} · {len(items)} 项</button>'
        for i, (owner, items) in enumerate(review.get("confirmations", {}).items())
    )
    return f'<div class="qtabs">{buttons}</div><div class="qpanes">{"".join(tabs)}</div>'


def build(data_dir: Path, out: Path, title: str | None, seed: dict | None, user_note: str = "") -> dict:
    case = load_case(data_dir)
    contract, review = case["contract"], case["review"]
    check = validate_case(contract, review)
    if check["errors"]:
        raise SystemExit("数据校验失败:\n  " + "\n  ".join(check["errors"]))

    clauses = {c["id"]: c for c in contract["clauses"]}
    findings = review["findings"]
    fmap = {f["id"]: f for f in findings}
    topic_name = {t["id"]: t["name"] for t in review["topics"]}
    meta = contract.get("contract_meta", {})
    rm = review.get("review_meta", {})
    roles = review.get("roles", {})
    demo = contract.get("demo", False)

    hits: dict[str, list[dict]] = {}
    for f in findings:
        for cid in f["clause_ids"]:
            hits.setdefault(cid, []).append(f)
    for lst in hits.values():
        lst.sort(key=lambda x: (-x["severity"], x["id"]))

    # ---- left column: contract body
    body_parts = []
    for s in contract["sections"]:
        cs = "".join(render_clause(clauses[cid], hits.get(cid, []), s) for cid in s["clause_ids"])
        body_parts.append(
            f'<section class="csec" id="sec-{esc(s["id"])}"><h3><span class="sec-no">{esc(s["no"])}</span>{esc(s["title"])}'
            f'<span class="pg">P{s["page"]}</span></h3>{cs}</section>'
        )
    for att in contract.get("attachments", []):
        body_parts.append(render_attachment(att))
    contract_html = "".join(body_parts)

    index_rows = "".join(
        f'<tr data-goto-clause="{esc(c["id"])}" class="irow"><td class="mono">{esc(c["id"])}</td>'
        f'<td>{esc(c["no"])}</td><td>P{c["page"]}</td><td class="t">{esc(excerpt(c["text"], 42))}</td>'
        f'<td>{"".join(f"<span class=\'mini s{r["severity"]}\'>{r["id"]}</span>" for r in hits.get(c["id"], [])) or "—"}</td></tr>'
        for c in contract["clauses"]
    )

    # ---- right column: cards
    cards = "".join(render_finding_card(f, clauses, topic_name) for f in findings)

    # ---- filters
    topic_btns = '<button class="fbtn active" data-topic="all">全部主题</button>' + "".join(
        f'<button class="fbtn" data-topic="{esc(t["id"])}" style="--tc:{TOPIC_COLORS.get(t["id"], "#475569")}">'
        f'{esc(t["name"])} <b>{check["stats"]["topic"].get(t["id"], 0)}</b></button>'
        for t in review["topics"] if check["stats"]["topic"].get(t["id"])
    )
    kind_btns = '<button class="kbtn active" data-kind="all">全部类型</button>' + "".join(
        f'<button class="kbtn" data-kind="{esc(k)}">{esc(k)} <b>{check["stats"]["kind"].get(k, 0)}</b></button>'
        for k in ["缺失", "表述不清", "写了但对我方不利"] if check["stats"]["kind"].get(k)
    )
    sev_btns = "".join(
        f'<button class="sbtn" data-sev="{n}" style="color:{sev_meta(n)[1]};background:{sev_meta(n)[2]}">'
        f'{sev_meta(n)[0]} {n}</button>' for n in (5, 4, 3, 2, 1) if check["stats"]["severity"].get(n)
    )

    titles = {owner: (f"内部{label}", desc) for owner, (label, desc) in {
        "legal": ("法务", "条款效力、责任分配、争议解决、需要律师判断的问题"),
        "procurement": ("采购", "商务谈判、计划与供应保障、供应商管理"),
        "supplier": ("供应商", "直接向乙方索要的事实、文件与承诺"),
    }.items()}
    q_html = render_question_tables(review, fmap, titles)

    # ---- legal refs table
    law_rows = "".join(
        f'<tr><td class="t"><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["name"])}</a></td>'
        f'<td>{esc(r["scope"])}</td><td><span class="st {"ok" if "现行" in r["status"] else "warn"}">{esc(r["status"])}</span></td>'
        f'<td>{esc(r["status_basis"])}</td><td>{esc(r["relevance"])}</td></tr>'
        for r in review.get("legal_refs", [])
    )

    summary = review.get("summary", {})
    calc = summary.get("calc_basis", {})
    stat_cards = "".join(
        f'<div class="stat"><div class="num">{check["stats"]["total"]}</div><div class="lbl">风险条目合计</div></div>'
        f'<div class="stat"><div class="num">{check["stats"]["kind"].get("缺失", 0)}</div><div class="lbl">缺失条款</div></div>'
        f'<div class="stat"><div class="num">{check["stats"]["kind"].get("表述不清", 0)}</div><div class="lbl">表述不清/冲突</div></div>'
        f'<div class="stat"><div class="num">{len(hits)}</div><div class="lbl">被引用的原文条款</div></div>'
        f'<div class="stat"><div class="num">{sum(len(v) for v in review.get("confirmations", {}).values())}</div><div class="lbl">待确认问题</div></div>'
    )
    top_rows = "".join(
        f'<li data-goto-finding="{esc(f["id"])}" class="toprow"><span class="sev" style="color:{sev_meta(f["severity"])[1]};background:{sev_meta(f["severity"])[2]}">{sev_meta(f["severity"])[0]}</span>'
        f'<b>{esc(f["id"])}</b> {esc(f["title"])}</li>'
        for f in sorted(findings, key=lambda x: (-x["severity"], x["id"]))[:8]
    )
    missing_list = "".join(f"<li>{esc(x)}</li>" for x in summary.get("missing_list", []))
    case_files = "".join(f"<li>✅ {esc(x)}</li>" for x in meta.get("files_received", [])) + "".join(
        f"<li class='miss'>❌ {esc(x)}</li>" for x in meta.get("files_missing", []))
    topics_bar = "".join(
        f'<div class="topicbar-item" style="--w:{check["stats"]["topic"].get(t["id"], 0)}"><span>{esc(t["name"])}</span>'
        f'<i>{check["stats"]["topic"].get(t["id"], 0)}</i></div>' for t in review["topics"]
    )

    seed_json = json.dumps(seed or {}, ensure_ascii=False)
    js_script = PAGE_JS.format(seed=seed_json)

    doc = TEMPLATE.format(
        title=esc(title or f"{meta.get('title', '采购合同')} · 合同风险审查"),
        demo_banner=(f'<div class="demo-banner">⚠ 本页面演示所用合同为 <b>{esc(contract.get("demo_label", "虚构演示合同"))}</b>：'
                     f'双方名称、金额、条款均为演示编写，不对应任何真实交易或公司。审查结论仅用于演示业务审查方法，'
                     f'不构成法律意见。</div>' if demo else ""),
        ctitle=esc(meta.get("title", "")), cno=esc(meta.get("contract_no", "")),
        buyer=esc(meta.get("buyer", "")), supplier=esc(meta.get("supplier", "")),
        sign_date=esc(meta.get("sign_date", "")), role=esc(meta.get("review_as", "")),
        review_date=esc(rm.get("review_date", "")), product=esc(meta.get("product") or rm.get("product", "")),
        reviewer=esc(rm.get("reviewer", "")), signed=esc(rm.get("signed", "")),
        scope=esc(rm.get("review_scope", "")), disclaimer=esc(rm.get("disclaimer", "")),
        stat_cards=stat_cards, headline=esc(summary.get("headline", "")), top_rows=top_rows,
        missing_list=missing_list, case_files=case_files, topics_bar=topics_bar,
        calc_note=esc(calc.get("note", "")),
        contract_html=contract_html, cards=cards, index_rows=index_rows,
        topic_btns=topic_btns, kind_btns=kind_btns, sev_btns=sev_btns,
        q_html=q_html, law_rows=law_rows, seed=seed_json,
        user_note=esc(user_note) or "—",
        role_legal=esc(roles.get("legal", "法务")), role_proc=esc(roles.get("procurement", "采购")),
        role_supplier=esc(roles.get("supplier", "供应商")),
        method_steps="".join(f"<li>{esc(s)}</li>" for s in review.get("method", {}).get("steps", [])),
        law_check_date=esc(rm.get("law_check_date", "")), n_total=str(check["stats"]["total"]),
        js=js_script,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return {"out": str(out), "bytes": len(doc.encode("utf-8")), "warnings": check["warnings"], "stats": check["stats"]}


PAGE_JS = r'''
(function(){{
  var SEED = {seed};
  var KEY = 'cr-status-' + (document.title||'').slice(0,40);
  var store = {{}};
  try {{ store = JSON.parse(localStorage.getItem(KEY) || '{{}}'); }} catch(e) {{ store = {{}}; }}
  Object.keys(SEED).forEach(function(k){{ if(!store[k]) store[k]=SEED[k]; }});

  function save(){{ try {{ localStorage.setItem(KEY, JSON.stringify(store)); }} catch(e){{}} }}

  // tabs
  var tabs = document.querySelectorAll('.tabs button');
  tabs.forEach(function(b){{ b.addEventListener('click', function(){{
    tabs.forEach(function(x){{x.classList.remove('active')}}); b.classList.add('active');
    document.querySelectorAll('.panel').forEach(function(p){{p.classList.remove('active')}});
    var target = document.getElementById('panel-' + b.dataset.panel);
    target.classList.add('active');
    if(b.dataset.panel === 'workspace'){{ setTimeout(layoutHeights, 30); }}
  }});}});

  // right heights based on toolbar
  function layoutHeights(){{
    var tb = document.querySelector('#panel-workspace .toolbar');
    if(!tb) return;
    var h = tb.offsetHeight + 118;
    document.querySelectorAll('.ws-left,.ws-right').forEach(function(el){{ el.style.height = 'calc(100vh - ' + h + 'px)'; }});
  }}
  window.addEventListener('resize', layoutHeights);

  var cards = Array.prototype.slice.call(document.querySelectorAll('.fcard'));
  cards.forEach(function(c){{
    var id = c.dataset.id;
    if(store[id]) {{
      var sel = c.querySelector('[data-status]'); var inp = c.querySelector('[data-note]');
      if(store[id].status){{ sel.value = store[id].status; }}
      if(store[id].note){{ inp.value = store[id].note; }}
      paintStatus(c, store[id].status);
    }}
    c.querySelector('[data-jump]').addEventListener('click', function(){{ c.classList.toggle('open'); }});
    c.querySelector('[data-status]').addEventListener('change', function(e){{
      store[id] = store[id] || {{}}; store[id].status = e.target.value; save(); paintStatus(c, e.target.value);
    }});
    c.querySelector('[data-note]').addEventListener('input', function(e){{
      store[id] = store[id] || {{}}; store[id].note = e.target.value; save();
    }});
    c.querySelectorAll('.anchor-btn').forEach(function(b){{
      b.addEventListener('click', function(){{ gotoClause(b.dataset.gotoClause); }});
    }});
  }});
  function paintStatus(card, s){{
    var pill = card.querySelector('[data-status-pill]');
    if(!pill) return;
    pill.textContent = s || '待处理';
    pill.classList.toggle('set', !!s && s !== '待处理');
  }}
  document.querySelectorAll('[data-goto-finding]').forEach(function(el){{
    el.addEventListener('click', function(){{
      var id = el.dataset.gotoFinding;
      switchTab('workspace');
      var card = document.getElementById('finding-' + id);
      if(!card) return;
      // clear filters so card is visible
      resetFilters();
      card.classList.add('open');
      card.scrollIntoView({{behavior:'smooth', block:'start'}});
      card.classList.add('flash'); setTimeout(function(){{card.classList.remove('flash')}}, 1800);
      var cid = card.dataset.clauses.split(',')[0];
      setTimeout(function(){{ gotoClause(cid, false); }}, 500);
    }});
  }});
  document.querySelectorAll('[data-goto-clause]').forEach(function(el){{
    el.addEventListener('click', function(){{ gotoClause(el.dataset.gotoClause); }});
  }});
  function switchTab(name){{
    var b = document.querySelector('.tabs button[data-panel="' + name + '"]'); if(b) b.click();
  }}
  function gotoClause(cid, alsoCard){{
    switchTab('workspace');
    var el = document.getElementById('clause-' + cid); if(!el) return;
    el.scrollIntoView({{behavior:'smooth', block:'center'}});
    el.classList.add('flash'); setTimeout(function(){{el.classList.remove('flash')}}, 1800);
    if(alsoCard !== false){{
      var chip = el.querySelector('.hit-chip'); if(chip) chip.click();
    }}
  }}

  // filters
  var curTopic = 'all', curKind = 'all', curSev = new Set(), q = '';
  var sevBtns = document.querySelectorAll('.sbtn');
  sevBtns.forEach(function(b){{ b.addEventListener('click', function(){{
    var v = b.dataset.sev;
    if(curSev.has(v)) {{ curSev.delete(v); b.classList.remove('on'); }} else {{ curSev.add(v); b.classList.add('on'); }}
    apply();
  }});}});
  document.querySelectorAll('.fbtn').forEach(function(b){{ b.addEventListener('click', function(){{
    curTopic = b.dataset.topic;
    document.querySelectorAll('.fbtn').forEach(function(x){{x.classList.remove('active')}}); b.classList.add('active'); apply();
  }});}});
  document.querySelectorAll('.kbtn').forEach(function(b){{ b.addEventListener('click', function(){{
    curKind = b.dataset.kind;
    document.querySelectorAll('.kbtn').forEach(function(x){{x.classList.remove('active')}}); b.classList.add('active'); apply();
  }});}});
  document.getElementById('search').addEventListener('input', function(e){{ q = e.target.value.trim().toLowerCase(); apply(); }});
  function resetFilters(){{
    curTopic='all'; curKind='all'; curSev.clear(); q='';
    document.getElementById('search').value='';
    document.querySelectorAll('.fbtn').forEach(function(x){{x.classList.toggle('active', x.dataset.topic==='all')}});
    document.querySelectorAll('.kbtn').forEach(function(x){{x.classList.toggle('active', x.dataset.kind==='all')}});
    sevBtns.forEach(function(x){{x.classList.remove('on')}});
    apply();
  }}
  function visible(c){{
    if(curTopic !== 'all' && c.dataset.topic !== curTopic) return false;
    if(curKind !== 'all' && c.dataset.kind !== curKind) return false;
    if(curSev.size && !curSev.has(c.dataset.sev)) return false;
    if(q && (c.dataset.search + ' ' + c.textContent.toLowerCase()).indexOf(q) === -1) return false;
    return true;
  }}
  function apply(){{
    var n = 0;
    cards.forEach(function(c){{ var v = visible(c); c.style.display = v ? '' : 'none'; if(v) n++; }});
    document.getElementById('count-hint').textContent = '显示 ' + n + ' / ' + cards.length + ' 条';
    // dim clauses without visible findings
    var shownIds = new Set();
    cards.forEach(function(c){{ if(visible(c)) shownIds.add(c.dataset.id); }});
    var anyFilter = curTopic!=='all' || curKind!=='all' || curSev.size || q;
    document.querySelectorAll('.clause').forEach(function(cl){{
      if(!anyFilter) {{ cl.style.opacity=''; return; }}
      var chips = cl.querySelectorAll('.hit-chip'); var on = false;
      chips.forEach(function(ch){{ if(shownIds.has(ch.dataset.gotoFinding)) on = true; }});
      cl.style.opacity = on ? '' : '.35';
    }});
  }}
  apply();
  document.getElementById('btn-all-open').onclick = function(){{ cards.forEach(function(c){{ if(c.style.display!=='none') c.classList.add('open'); }}); }};
  document.getElementById('btn-all-close').onclick = function(){{ cards.forEach(function(c){{ c.classList.remove('open'); }}); }};
  document.getElementById('btn-export').onclick = function(){{
    var blob = new Blob([JSON.stringify(store, null, 2)], {{type:'application/json'}});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'contract-review-status.json'; a.click();
  }};

  // question tabs
  document.querySelectorAll('.qtab-btn').forEach(function(b){{ b.addEventListener('click', function(){{
    document.querySelectorAll('.qtab-btn').forEach(function(x){{x.classList.remove('active')}}); b.classList.add('active');
    document.querySelectorAll('.qtab').forEach(function(p){{p.classList.toggle('active', p.dataset.owner === b.dataset.owner)}});
  }});}});
  document.querySelectorAll('.qrow').forEach(function(r){{
    r.addEventListener('click', function(e){{
      if(e.target.tagName === 'INPUT' || e.target.tagName === 'LABEL') return;
      var id = r.dataset.gotoFinding; switchTab('workspace');
      var card = document.getElementById('finding-' + id); if(!card) return;
      resetFilters(); card.classList.add('open');
      card.scrollIntoView({{behavior:'smooth', block:'start'}});
      card.classList.add('flash'); setTimeout(function(){{card.classList.remove('flash')}}, 1800);
    }});
  }});
  document.querySelectorAll('.toprow').forEach(function(r){{
    r.addEventListener('click', function(){{
      var id = r.dataset.gotoFinding; switchTab('workspace');
      var card = document.getElementById('finding-' + id); if(!card) return;
      resetFilters(); card.classList.add('open');
      card.scrollIntoView({{behavior:'smooth', block:'start'}});
      card.classList.add('flash'); setTimeout(function(){{card.classList.remove('flash')}}, 1800);
    }});
  }});
  window.addEventListener('load', layoutHeights);
}})();
'''


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{{{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#f6f8fb;--card:#ffffff;--brand:#0f3d5c;--accent:#c2410c;--left:46%;}}}}
*{{{{box-sizing:border-box}}}}
html,body{{{{margin:0;padding:0}}}}
body{{{{font-family:"Microsoft YaHei","PingFang SC","Noto Sans SC",system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg);font-size:14px;line-height:1.65}}}}
a{{{{color:#0b5cad}}}}
.demo-banner{{{{background:repeating-linear-gradient(45deg,#fef3c7,#fef3c7 12px,#fde68a 12px,#fde68a 24px);color:#78350f;padding:10px 26px;font-size:13px;border-bottom:1px solid #f59e0b}}}}
.hero{{{{background:linear-gradient(135deg,#0b2e45 0%,#0f3d5c 45%,#155e75 100%);color:#e6f2f7;padding:26px 30px 22px}}}}
.hero .kicker{{{{font-size:12px;letter-spacing:.2em;color:#7dd3fc;text-transform:uppercase}}}}
.hero h1{{{{margin:6px 0 4px;font-size:26px;font-weight:700;letter-spacing:.02em}}}}
.hero .meta{{{{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:12.5px;color:#bae6fd;margin-top:10px}}}}
.hero .meta b{{{{color:#fff;font-weight:600}}}}
.pills{{{{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}}}}
.pill{{{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);padding:3px 10px;border-radius:999px;font-size:12px}}}}
.tabs{{{{display:flex;gap:2px;background:#0b2e45;padding:0 18px;position:sticky;top:0;z-index:50}}}}
.tabs button{{{{background:transparent;border:0;color:#9ec5d8;padding:12px 18px;font-size:14px;cursor:pointer;border-bottom:3px solid transparent;font-family:inherit}}}}
.tabs button.active{{{{color:#fff;border-bottom-color:#f59e0b;font-weight:600}}}}
.tabs button:hover{{{{color:#fff}}}}
.panel{{{{display:none;padding:20px 24px 40px}}}}
.panel.active{{{{display:block}}}}
.stats{{{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:6px 0 18px}}}}
.stat{{{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:0 1px 2px rgba(15,23,42,.04)}}}}
.stat .num{{{{font-size:30px;font-weight:700;color:var(--brand);line-height:1.1}}}}
.stat .lbl{{{{font-size:12px;color:var(--muted)}}}}
.grid2{{{{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}}}}
.card{{{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;box-shadow:0 1px 2px rgba(15,23,42,.04)}}}}
.card h3{{{{margin:0 0 10px;font-size:15px;color:var(--brand)}}}}
.toprow,.qrow,.irow,.cla{{{{list-style:none}}}}
ol.top{{{{padding-left:0;margin:0}}}}
.toprow{{{{display:flex;gap:8px;align-items:flex-start;padding:7px 0;border-bottom:1px dashed var(--line);cursor:pointer;font-size:13.5px}}}}
.toprow:hover{{{{color:var(--accent)}}}}
.toprow:last-child{{{{border-bottom:0}}}}
.sev{{{{display:inline-block;padding:0 7px;border-radius:5px;font-size:11.5px;font-weight:600;white-space:nowrap}}}}
.topicbar{{{{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}}}}
.topicbar-item{{{{display:flex;flex-direction:column;align-items:center;background:#eef4f8;border-radius:8px;padding:4px 10px;font-size:12px;color:#155e75;min-width:56px}}}}
.topicbar-item i{{{{font-style:normal;font-weight:700;font-size:16px;color:#0f3d5c}}}}
.miss{{{{color:#9a3412}}}}
.uinote{{{{background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:8px 12px;font-size:12.5px;color:#7c2d12;margin-top:10px}}}}
.disclaimer{{{{background:#fff1f2;border:1px solid #fecdd3;color:#881337;border-radius:10px;padding:12px 14px;font-size:12.5px;margin-top:16px}}}}
/* ---------- review workspace ---------- */
.ws{{{{display:grid;grid-template-columns:var(--left) 1fr;gap:0;border-top:1px solid var(--line);}}
.ws-left,.ws-right{{{{height:calc(100vh - 118px);overflow:auto;scroll-behavior:smooth}}}}
.ws-left{{{{background:#fdfdfb;border-right:1px solid var(--line);padding:16px 18px 80px}}}}
.ws-right{{{{padding:14px 18px 90px;background:#f3f6f9}}}}
.toolbar{{{{position:sticky;top:0;background:var(--bg);z-index:40;padding:10px 24px 12px;border-bottom:1px solid var(--line);display:flex;flex-direction:column;gap:8px}}}}
.toolbar .row{{{{display:flex;flex-wrap:wrap;gap:6px;align-items:center}}}}
.toolbar .lbl{{{{font-size:12px;color:var(--muted);margin-right:4px}}}}
.fbtn,.kbtn,.sbtn,.tb{{{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:4px 11px;font-size:12.5px;cursor:pointer;font-family:inherit;color:#334155}}}}
.fbtn b,.kbtn b{{{{font-weight:700;color:var(--brand)}}}}
.fbtn.active{{{{background:var(--tc,#0f3d5c);border-color:transparent;color:#fff}}}}
.fbtn.active b{{{{color:#fff}}}}
.kbtn.active{{{{background:var(--brand);color:#fff;border-color:transparent}}}}
.kbtn.active b{{{{color:#fff}}}}
.btn{{{{border:1px solid #0f3d5c;background:#0f3d5c;color:#fff;border-radius:8px;padding:5px 12px;font-size:12.5px;cursor:pointer;font-family:inherit}}}}
.btn.ghost{{{{background:#fff;color:#0f3d5c}}}}
#search{{{{flex:1;min-width:180px;border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-family:inherit;font-size:13px}}}}
.csec{{{{margin-bottom:18px}}}}
.csec h3{{{{font-size:15px;margin:16px 0 8px;color:#0f3d5c;border-left:4px solid #f59e0b;padding-left:10px;display:flex;align-items:center;gap:8px}}}}
.sec-no{{{{background:#0f3d5c;color:#fff;border-radius:4px;font-size:12px;padding:1px 7px}}}}
.pg{{{{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:400;background:#f1f5f9;border-radius:4px;padding:0 6px}}}}
.clause{{{{padding:8px 10px;border-radius:8px;margin:4px 0;cursor:default;transition:background .15s}}}}
.clause:hover{{{{background:#f4f7fa}}}}
.clause.flagged{{{{background:#fffdf5}}}}
.clause.flash{{{{background:#fef3c7;box-shadow:inset 0 0 0 2px #f59e0b}}}}
.clause-no{{{{font-size:11.5px;color:#64748b;display:flex;align-items:center;gap:6px;margin-bottom:2px}}}}
.clause-text{{{{font-size:13.5px;color:#1e293b;text-align:justify}}}}
.clause-chips{{{{display:flex;gap:3px;margin-left:auto}}}}
.hit-chip{{{{border:0;border-radius:4px;font-size:10.5px;padding:0 5px;cursor:pointer;font-weight:700;color:#fff;background:#64748b}}}}
.hit-chip.s5{{{{background:#b91c1c}}}}.hit-chip.s4{{{{background:#ea580c}}}}.hit-chip.s3{{{{background:#d97706}}}}.hit-chip.s2{{{{background:#16a34a}}}}
.attachment{{{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px;margin:16px 0}}}}
.att-head{{{{font-weight:700;color:#0f3d5c;display:flex;gap:8px;align-items:center;margin-bottom:8px}}}}
.c-table{{{{width:100%;border-collapse:collapse;font-size:12.5px}}}}
.c-table caption{{{{caption-side:top;text-align:left;color:#64748b;font-size:12px;padding-bottom:6px}}}}
.c-table th{{{{background:#eef4f8;text-align:left;padding:6px 8px;border:1px solid #dbe5ec;font-weight:600}}}}
.c-table td{{{{padding:6px 8px;border:1px solid #e2e8f0}}}}
.c-table tr td:nth-child(2){{{{color:#7c2d12}}}}
.att-note{{{{font-size:12.5px;color:#475569;background:#f8fafc;border-left:3px solid #cbd5e1;padding:8px 10px}}}}
.att-list{{{{font-size:13px;color:#1e293b;padding-left:20px}}}}
/* ---------- cards ---------- */
.fcard{{{{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:12px;overflow:hidden;box-shadow:0 1px 2px rgba(15,23,42,.05);transition:box-shadow .2s,transform .2s}}}}
.fcard.flash{{{{box-shadow:0 0 0 3px #f59e0b,0 6px 18px rgba(245,158,11,.25)}}}}
.fc-head{{{{display:flex;align-items:center;gap:7px;padding:9px 13px;background:#f8fafc;border-bottom:1px solid var(--line);cursor:pointer;flex-wrap:wrap}}}}
.rid{{{{font-family:Consolas,monospace;font-weight:700;color:#0f3d5c}}}}
.topic,.kind{{{{font-size:11.5px;padding:1px 7px;border-radius:5px}}}}
.kind{{{{background:#eef2ff;color:#3730a3}}}}
.kind.k-缺失{{{{background:#fde68a;color:#78350f}}}}
.kind.k-表述不清{{{{background:#dbeafe;color:#1e3a8a}}}}
.status-pill{{{{margin-left:auto;font-size:11.5px;color:#64748b;border:1px dashed #cbd5e1;border-radius:999px;padding:0 8px}}}}
.status-pill.set{{{{color:#065f46;border-color:#6ee7b7;background:#ecfdf5}}}}
.caret{{{{color:#94a3b8;transition:transform .2s}}}}
.fcard.open .caret{{{{transform:rotate(90deg)}}}}
.fc-title{{{{margin:10px 14px 0;font-size:14.5px;line-height:1.5;color:#111827}}}}
.fc-body{{{{display:none;padding:8px 14px 14px}}}}
.fcard.open .fc-body{{{{display:block}}}}
.sec{{{{margin-top:10px}}}}
.sec h5{{{{margin:0 0 4px;font-size:12px;color:#0f3d5c;letter-spacing:.05em}}}}
.sec p{{{{margin:0 0 4px;font-size:13.2px;color:#334155;text-align:justify}}}}
.quote{{{{margin:6px 0;padding:7px 10px;background:#f8fafc;border-left:3px solid #94a3b8;border-radius:0 6px 6px 0;display:flex;flex-direction:column;gap:2px}}}}
.q-src{{{{font-size:11px;color:#64748b}}}}
.q-text{{{{font-size:12.8px;color:#111827}}}}
.anchors{{{{display:flex;flex-wrap:wrap;gap:6px}}}}
.anchor-btn{{{{border:1px solid #cbd5e1;background:#f8fafc;border-radius:6px;padding:3px 9px;font-size:12px;cursor:pointer;color:#0f3d5c;font-family:inherit}}}}
.anchor-btn:hover{{{{background:#e0f2fe;border-color:#7dd3fc}}}}
.missing{{{{color:#9a3412;font-weight:600;font-size:12.5px}}}}
.cons,.todo{{{{margin:2px 0 0;padding-left:18px;font-size:12.8px;color:#334155}}}}
.cons li::marker{{{{color:#dc2626}}}}
.todo li::marker{{{{color:#0f766e}}}}
.law-chips span{{{{display:inline-block;font-size:11.5px;background:#eef2f7;border-radius:5px;padding:1px 7px;margin:2px 4px 0 0;color:#334155}}}}
.note-sec{{{{background:#f8fafc;border:1px dashed #cbd5e1;border-radius:8px;padding:8px 10px}}}}
.note-controls{{{{display:flex;gap:8px}}}}
.note-controls select,.note-controls input{{{{border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-family:inherit;font-size:12.5px}}}}
.note-controls input{{{{flex:1}}}}
/* ---------- index table ---------- */
table.qtable,table.idx{{{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;font-size:12.8px}}}}
.qtable th,table.idx th{{{{background:#0f3d5c;color:#fff;text-align:left;padding:8px 10px;font-weight:600;position:sticky;top:0}}}}
.qtable td,table.idx td{{{{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}}}}
.qtable tr:hover,table.idx tr:hover{{{{background:#f0f9ff;cursor:pointer}}}}
.mono{{{{font-family:Consolas,monospace;color:#0f3d5c;font-weight:600;white-space:nowrap}}}}
.t{{{{max-width:420px}}}}
.pr{{{{font-size:11.5px;padding:0 7px;border-radius:5px;font-weight:700;color:#fff}}}}
.pr-高{{{{background:#b91c1c}}}}.pr-中{{{{background:#d97706}}}}.pr-低{{{{background:#64748b}}}}
.qtabs{{{{display:flex;gap:6px;margin:4px 0 12px;flex-wrap:wrap}}}}
.qtab-btn{{{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 14px;cursor:pointer;font-family:inherit;font-size:13px}}}}
.qtab-btn.active{{{{background:#0f3d5c;color:#fff;border-color:transparent}}}}
.qtab{{{{display:none}}}}.qtab.active{{{{display:block}}}}
.qtab-desc{{{{color:#64748b;font-size:12.5px;margin:0 0 8px}}}}
.mini{{{{display:inline-block;font-size:10.5px;color:#fff;background:#64748b;border-radius:4px;padding:0 4px;margin-right:2px;font-family:Consolas,monospace}}}}
.mini.s5{{{{background:#b91c1c}}}}.mini.s4{{{{background:#ea580c}}}}.mini.s3{{{{background:#d97706}}}}.mini.s2{{{{background:#16a34a}}}}
.legend{{{{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#475569;margin:8px 0 12px}}}}
.legend i{{{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px}}}}
.st{{{{font-size:12px;padding:0 7px;border-radius:5px}}}}
.st.ok{{{{background:#dcfce7;color:#166534}}}}.st.warn{{{{background:#fef3c7;color:#92400e}}}}
.foot{{{{padding:18px 24px;color:#64748b;font-size:12px;border-top:1px solid var(--line);margin-top:20px}}}}
@media (max-width:1100px){{{{.ws{{{{grid-template-columns:1fr}}}} .ws-left,.ws-right{{{{height:auto}}}} .stats{{{{grid-template-columns:repeat(2,1fr)}}}} .grid2{{{{grid-template-columns:1fr}}}}}}}}
@media print{{{{.tabs,.toolbar,.note-sec{{{{display:none}}}} .ws{{{{display:block}}}} .ws-left,.ws-right{{{{height:auto;overflow:visible}}}} .fc-body{{{{display:block}}}}}}}}
</style>
</head>
<body>
{demo_banner}
<header class="hero">
  <div class="kicker">内贸采购 · 合同风险审查 / Contract Risk Review</div>
  <h1>{ctitle}</h1>
  <div class="meta">
    <span>合同编号 <b>{cno}</b></span><span>我方身份 <b>{role}</b></span><span>供应商 <b>{supplier}</b></span>
    <span>签订日期 <b>{sign_date}</b></span><span>审查日期 <b>{review_date}</b></span><span>审查人 <b>{reviewer}</b></span>
  </div>
  <div class="pills"><span class="pill">标的：{product}</span><span class="pill">状态：{signed}</span><span class="pill">审查范围：{scope}</span></div>
</header>
<nav class="tabs">
  <button class="active" data-panel="overview">总览</button>
  <button data-panel="workspace">原文 × 风险双栏</button>
  <button data-panel="index">条款索引</button>
  <button data-panel="tasks">问题清单（采购/法务/供应商）</button>
  <button data-panel="laws">法规标准核对</button>
  <button data-panel="method">方法与边界</button>
</nav>

<section class="panel active" id="panel-overview">
  <div class="stats">{stat_cards}</div>
  <div class="grid2">
    <div class="card"><h3>一句话结论</h3><p style="margin:0 0 12px;font-size:14px">{headline}</p>
      <h3>最需要先处理的 8 条</h3><ol class="top">{top_rows}</ol>
      <div class="uinote">内部备注：{user_note}</div>
    </div>
    <div class="card"><h3>合同未约定 / 需补齐的事项（缺失，不作推测）</h3><ul>{missing_list}</ul>
      <h3 style="margin-top:14px">本次收到的文件</h3><ul>{case_files}</ul>
      <h3 style="margin-top:14px">风险主题分布</h3><div class="topicbar">{topics_bar}</div>
      <p style="font-size:12px;color:#64748b;margin:10px 0 0">{calc_note}</p>
    </div>
  </div>
  <div class="disclaimer">{disclaimer}</div>
</section>

<section class="panel" id="panel-workspace">
  <div class="toolbar">
    <div class="row"><span class="lbl">主题</span>{topic_btns}</div>
    <div class="row"><span class="lbl">类型</span>{kind_btns}<span class="lbl" style="margin-left:12px">严重度</span>{sev_btns}</div>
    <div class="row">
      <input id="search" placeholder="搜索风险、原文、待确认问题…（支持「溴」「押金」「仲裁」等词）">
      <button class="btn ghost" id="btn-all-open">展开全部</button>
      <button class="btn ghost" id="btn-all-close">收起全部</button>
      <button class="btn ghost" id="btn-export">导出处理状态 JSON</button>
      <span id="count-hint" style="font-size:12px;color:#64748b"></span>
    </div>
  </div>
  <div class="ws" id="ws">
    <div class="ws-left" id="left">{contract_html}</div>
    <div class="ws-right" id="right">{cards}</div>
  </div>
</section>

<section class="panel" id="panel-index">
  <p style="color:#64748b;font-size:12.8px;margin-top:0">条款索引是全文锚点：每行可点击，跳转到「原文 × 风险」并对该条款高亮。<b>风险编号</b>列显示引用了该条款的所有风险条目。</p>
  <table class="idx"><thead><tr><th>条款ID</th><th>条款编号</th><th>页码</th><th>原文摘要（逐字摘录）</th><th>关联风险</th></tr></thead><tbody>{index_rows}</tbody></table>
</section>

<section class="panel" id="panel-tasks">
  <p style="color:#64748b;font-size:12.8px;margin-top:0">同一份风险条目按「谁去办」拆成三张清单：内部采购（商务与供应保障）、法务（条款效力与责任分配）、供应商（向乙方索要的事实、文件与承诺）。点击任意行定位到原文与风险卡片；勾选框状态同样保存在本浏览器。</p>
  {q_html}
</section>

<section class="panel" id="panel-laws">
  <p style="color:#64748b;font-size:12.8px;margin-top:0">适用性核对日期：<b>{law_check_date}</b>。下表只说明「这条法规/标准是否存在、是否现行、与本合同的关联点」，<b>不</b>据此对合同效力下结论；正式签约或索赔前，请通过国家法律法规数据库与全国标准信息公共服务平台再次核对。</p>
  <table class="qtable"><thead><tr><th>法规 / 标准</th><th>适用点</th><th>核验状态</th><th>核验依据（来源与日期）</th><th>与本合同的关联</th></tr></thead><tbody>{law_rows}</tbody></table>
  <div class="disclaimer">{disclaimer}</div>
</section>

<section class="panel" id="panel-method">
  <div class="grid2">
    <div class="card"><h3>本次审查步骤</h3><ol>{method_steps}</ol></div>
    <div class="card"><h3>业务提醒与法律意见的边界</h3>
      <p style="font-size:13.2px">本页面输出的是<b>业务审查提示</b>：说明合同写了什么、哪些没写清楚、可能产生哪些采购业务后果、建议向谁确认。</p>
      <p style="font-size:13.2px">它<b>不是法律意见</b>：不对条款效力、是否可执行、法律责任如何分配作出结论；涉及解释争议与诉讼仲裁的事项，由{role_legal}或外部律师判断。</p>
      <p style="font-size:13.2px">数据来源限定为：用户提供的合同文本 + 公开可核验的法规标准。合同以外的信息（供应商资质、履约能力）一律标为「未提供/需核实」，不作推测。</p>
      <h3 style="margin-top:14px">处理状态说明</h3>
      <p style="font-size:12.8px;color:#475569">状态与备注仅保存在当前浏览器的 localStorage 中，便于业务同事各自消化；需要共享时点击「导出处理状态 JSON」，把文件回传给采购负责人汇总。</p>
    </div>
  </div>
  <div class="disclaimer">{disclaimer}</div>
</section>

<div class="foot">共 {n_total} 条风险 · 页面由 skill「检查采购合同风险点」生成 · 单文件离线可用 · 打印时自动展开全部卡片</div>

<script>
  {js}
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="生成交互式 HTML 合同审查页面")
    ap.add_argument("--dir", required=True, help="案例目录（含 合同JSON 与 审查JSON）")
    ap.add_argument("--out", required=True, help="输出 HTML 路径")
    ap.add_argument("--title", default=None)
    ap.add_argument("--status-seed", default=None, help="预置处理状态 JSON（可选）")
    ap.add_argument("--user-note", default="")
    a = ap.parse_args()
    seed = json.loads(Path(a.status_seed).read_text(encoding="utf-8")) if a.status_seed else None
    info = build(Path(a.dir), Path(a.out), a.title, seed, a.user_note)
    print(json.dumps({"ok": True, **{k: v for k, v in info.items() if k != "stats"}}, ensure_ascii=False))
    if info["warnings"]:
        print("WARN:", "; ".join(info["warnings"]))


if __name__ == "__main__":
    main()
