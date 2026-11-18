"""通用风险审查模型 -> 交互式 HTML（不依赖具体合同）。

用法:
    python render_html.py --case <案例目录> --out <html>
      [--title "…"] [--status-seed <json>] [--note "内部备注"]

案例目录需包含（见 SKILL.md 第 3 步）：
  contract.json  合同结构（sections / clauses / attachments）
  review.json    审查结果（topics / findings / legal_refs / confirmations / summary）

与 build_review_html.py 的区别：本文件是**面向任意合同**的通用渲染器，
输出模板化页面；示例案例里另附一份「精修版」页面以展示设计上限。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import esc, excerpt, load_case, validate_case

SEV = {5: ("极高", "#ffffff", "#b91c1c"), 4: ("高", "#ffffff", "#ea580c"),
       3: ("中", "#7c2d12", "#fcd34d"), 2: ("低", "#14532d", "#bbf7d0"),
       1: ("提示", "#1e3a8a", "#dbeafe")}
OWNER_LABEL = {"legal": "法务", "procurement": "采购", "supplier": "供应商"}


def build(case_dir: Path, out: Path, title: str | None, seed: dict | None, note: str) -> dict:
    case = load_case(case_dir)
    contract, review = case["contract"], case["review"]
    check = validate_case(contract, review)
    if check["errors"]:
        raise SystemExit("数据校验失败:\n  " + "\n  ".join(check["errors"]))
    clauses = {c["id"]: c for c in contract["clauses"]}
    fmap = {f["id"]: f for f in review["findings"]}
    topic_name = {t["id"]: t["name"] for t in review.get("topics", [])}
    meta = contract.get("contract_meta", {})
    rm = review.get("review_meta", {})
    hits: dict[str, list] = {}
    for f in review["findings"]:
        for cid in f["clause_ids"]:
            hits.setdefault(cid, []).append(f)

    # 合同正文
    body = []
    for s in contract["sections"]:
        parts = "".join(
            f'<div class="cl" id="cl-{esc(cid)}" data-clause="{esc(cid)}">'
            f'<div class="cl-h"><b>{esc(clauses[cid]["no"])}</b><i>P{clauses[cid]["page"]}</i>'
            + "".join(f'<span class="tag t{h["severity"]}" data-finding="{esc(h["id"])}">{esc(h["id"])}</span>'
                      for h in hits.get(cid, []))
            + f'</div><p>{esc(clauses[cid]["text"])}</p></div>'
            for cid in s["clause_ids"])
        body.append(f'<h3 id="sec-{esc(s["id"])}">{esc(s["no"])}　{esc(s["title"])}<i>P{s["page"]}</i></h3>{parts}')
    for att in contract.get("attachments", []):
        inner = ""
        if att.get("table"):
            rows = "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in r) + "</tr>" for r in att["table"]["rows"])
            heads = "".join(f"<th>{esc(h)}</th>" for h in att["table"]["cols"])
            inner = f'<table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table><p class="nt">{esc(att["table"].get("note", ""))}</p>'
        if att.get("list"):
            inner += "<ol>" + "".join(f"<li>{esc(x)}</li>" for x in att["list"]) + "</ol>"
        body.append(f'<div class="att"><h4>{esc(att["no"])}　{esc(att["title"])}<i>P{att["page"]}</i></h4>{inner}</div>')

    # 风险卡
    cards = []
    for f in review["findings"]:
        label, fg, bg = SEV.get(f["severity"], SEV[3])
        anchors = "".join(
            f'<button class="anc" data-clause="{esc(cid)}">{esc(clauses[cid]["no"])} · P{clauses[cid]["page"]}</button>'
            for cid in f["clause_ids"] if cid in clauses)
        quotes = "".join(
            f'<blockquote><i>{esc(clauses[cid]["no"])} · P{clauses[cid]["page"]}</i>“{esc(excerpt(clauses[cid]["text"], 200))}”</blockquote>'
            for cid in f["clause_ids"] if cid in clauses)
        cards.append(f'''<article class="card" data-id="{esc(f['id'])}" data-topic="{esc(f['topic'])}"
  data-kind="{esc(f['kind'])}" data-sev="{f['severity']}"
  data-search="{esc(' '.join([f['title'], f['what_written'], f.get('what_missing',''), f['business_impact'], ' '.join(f['to_confirm'])]).lower())}">
  <header data-toggle><b>{esc(f['id'])}</b>
    <span class="sev" style="color:{fg};background:{bg}">{label}</span>
    <span class="tp">{esc(topic_name.get(f['topic'], f['topic']))}</span>
    <span class="kd">{esc(f['kind'])}</span>
    <span class="st" data-pill>待处理</span><span class="cv">▾</span></header>
  <h4>{esc(f['title'])}</h4>
  <div class="body">
    <section><h5>合同原文</h5><p>{esc(f['what_written'])}</p>{quotes}<div class="ancs">{anchors}</div></section>
    <section><h5>未写清楚 / 缺失</h5>{'<em class="miss">⚠ 合同未见约定，不作推测</em>' if f['kind'] == '缺失' else ''}<p>{esc(f.get('what_missing',''))}</p></section>
    <section><h5>业务影响</h5><p>{esc(f['business_impact'])}</p><ul>{''.join(f'<li>{esc(x)}</li>' for x in f.get('consequences', []))}</ul></section>
    <section><h5>待确认</h5><ul class="q">{''.join(f'<li>{esc(x)}</li>' for x in f['to_confirm'])}</ul></section>
    {'<section><h5>法规标准</h5><div class="law">' + ''.join(f'<span>{esc(x)}</span>' for x in f.get('law_refs', [])) + '</div></section>' if f.get('law_refs') else ''}
    <section class="ctl"><select data-status>{''.join(f'<option>{x}</option>' for x in ['待处理','已确认','待供应商回复','已解决','不适用'])}</select>
      <input data-note placeholder="处理备注（保存在本浏览器）"></section>
  </div></article>''')

    topics = "".join(f'<button class="fb" data-topic="{esc(t["id"])}">{esc(t["name"])}<b>{check["stats"]["topic"].get(t["id"],0)}</b></button>'
                     for t in review.get("topics", []) if check["stats"]["topic"].get(t["id"]))
    kinds = "".join(f'<button class="kb" data-kind="{esc(k)}">{esc(k)}<b>{check["stats"]["kind"].get(k,0)}</b></button>'
                    for k in check["stats"]["kind"])
    law_rows = "".join(
        f'<tr><td><a href="{esc(r["url"])}" target="_blank">{esc(r["name"])}</a></td><td>{esc(r["scope"])}</td>'
        f'<td><b>{esc(r["status"])}</b></td><td>{esc(r["status_basis"])}</td></tr>' for r in review.get("legal_refs", []))
    qpanes, qbtns = [], []
    for i, (owner, items) in enumerate(review.get("confirmations", {}).items()):
        rows = "".join(
            f'<tr data-finding="{esc(q["finding_id"])}"><td>{esc(q["finding_id"])}</td>'
            f'<td><span class="pr p{esc(q["priority"])}">{esc(q["priority"])}</span></td>'
            f'<td>{esc(fmap[q["finding_id"]]["title"])}</td><td>{esc(q["question"])}</td>'
            f'<td>{esc(",".join(fmap[q["finding_id"]]["clause_ids"]))}</td></tr>' for q in items)
        lbl = OWNER_LABEL.get(owner, owner)
        qbtns.append(f'<button class="qb{" on" if i == 0 else ""}" data-owner="{esc(owner)}">{lbl} · {len(items)}</button>')
        qpanes.append(f'<div class="qp{" on" if i == 0 else ""}" data-owner="{esc(owner)}"><table class="qt">'
                      '<thead><tr><th>风险</th><th>优先级</th><th>标题</th><th>待确认问题</th><th>条款</th></tr></thead>'
                      f'<tbody>{rows}</tbody></table></div>')
    sm = review.get("summary", {})
    top = "".join(f'<li data-finding="{esc(f["id"])}"><b>{esc(f["id"])}</b> {esc(f["title"])}</li>'
                  for f in sorted(review["findings"], key=lambda x: (-x["severity"], x["id"]))[:10])

    page = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title or meta.get("title","合同风险审查"))}</title>
<style>
body{{margin:0;font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;color:#0f172a;background:#f6f8fb;font-size:14px;line-height:1.65}}
.demo{{background:#fef3c7;color:#78350f;padding:9px 22px;font-size:12.5px;border-bottom:1px solid #f59e0b}}
header.top{{background:linear-gradient(135deg,#0b2e45,#0f3d5c,#155e75);color:#e6f2f7;padding:22px 26px}}
header.top h1{{margin:0 0 6px;font-size:23px}} header.top p{{margin:2px 0;font-size:12.5px;color:#bae6fd}}
nav{{display:flex;gap:2px;background:#0b2e45;padding:0 16px;position:sticky;top:0;z-index:9}}
nav button{{background:none;border:0;color:#9ec5d8;padding:11px 16px;cursor:pointer;font-family:inherit;font-size:14px;border-bottom:3px solid transparent}}
nav button.on{{color:#fff;border-bottom-color:#f59e0b;font-weight:600}}
.pn{{display:none;padding:18px 22px 50px}} .pn.on{{display:block}}
.kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:14px}}
.kpi div{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px}}
.kpi b{{display:block;font-size:26px;color:#0f3d5c}} .kpi span{{font-size:12px;color:#64748b}}
.box{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin-bottom:12px}}
.box h3{{margin:0 0 8px;font-size:15px;color:#0f3d5c}}
.tb{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:10px 22px;background:#f6f8fb;border-bottom:1px solid #e2e8f0;position:sticky;top:47px;z-index:8}}
.fb,.kb{{border:1px solid #e2e8f0;background:#fff;border-radius:999px;padding:3px 11px;font-size:12.5px;cursor:pointer;font-family:inherit}}
.fb.on,.kb.on{{background:#0f3d5c;color:#fff;border-color:#0f3d5c}} .fb b,.kb b{{margin-left:5px}}
#q{{flex:1;min-width:160px;border:1px solid #e2e8f0;border-radius:7px;padding:5px 9px;font-family:inherit}}
.wrap{{display:grid;grid-template-columns:44% 1fr}} .L,.R{{height:calc(100vh - 150px);overflow:auto;padding:14px 16px 80px}}
.L{{background:#fdfdfb;border-right:1px solid #e2e8f0}}
h3.sc,h3{{font-size:15px}} .L h3{{color:#0f3d5c;border-left:4px solid #f59e0b;padding-left:9px;margin:16px 0 8px;display:flex;align-items:center}}
.L h3 i{{margin-left:auto;font-style:normal;font-size:11px;color:#94a3b8}}
.cl{{padding:7px 9px;border-radius:7px}} .cl:hover{{background:#f4f7fa}} .cl.fl{{background:#fef3c7;box-shadow:inset 0 0 0 2px #f59e0b}}
.cl-h{{display:flex;gap:6px;align-items:center;font-size:11.5px;color:#64748b}} .cl-h i{{font-style:normal}}
.tag{{color:#fff;border-radius:4px;font-size:10px;padding:0 4px;cursor:pointer}} .t5{{background:#b91c1c}}.t4{{background:#ea580c}}.t3{{background:#d97706}}.t2{{background:#16a34a}}.t1{{background:#64748b}}
.cl p{{margin:2px 0 0;font-size:13.4px;text-align:justify}}
.att{{background:#fff;border:1px solid #e2e8f0;border-radius:9px;padding:12px;margin:14px 0}} .att h4{{margin:0 0 8px;display:flex;color:#0f3d5c}} .att h4 i{{margin-left:auto;font-style:normal;font-size:11px;color:#94a3b8}}
table{{width:100%;border-collapse:collapse;font-size:12.6px}} th{{background:#eef4f8;text-align:left;padding:6px 8px;border:1px solid #dbe5ec}} td{{padding:6px 8px;border:1px solid #e2e8f0;vertical-align:top}}
.nt{{font-size:12.4px;color:#475569;background:#f8fafc;padding:7px 9px;border-left:3px solid #cbd5e1}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;margin-bottom:11px}} .card.fl{{box-shadow:0 0 0 3px #f59e0b}}
.card header{{display:flex;gap:7px;align-items:center;padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;cursor:pointer;font-size:12.5px}}
.card h4{{margin:9px 13px 0;font-size:14px}} .card .body{{display:none;padding:6px 13px 12px}} .card.op .body{{display:block}} .card.op .cv{{transform:rotate(180deg)}}
.card section{{margin-top:9px}} .card h5{{margin:0 0 3px;font-size:12px;color:#0f3d5c}} .card p{{margin:0;font-size:13.1px;color:#334155;text-align:justify}}
.card ul{{margin:3px 0 0;padding-left:18px;font-size:12.7px}} .q li::marker{{color:#0f766e}}
blockquote{{margin:5px 0;padding:6px 9px;background:#f8fafc;border-left:3px solid #94a3b8;font-size:12.6px}}
blockquote i{{display:block;font-style:normal;font-size:11px;color:#64748b}}
.sev{{color:#fff;border-radius:5px;padding:0 6px;font-size:11px}} .tp{{background:#0e7490;color:#fff;border-radius:5px;padding:0 6px;font-size:11px}}
.kd{{background:#eef2ff;color:#3730a3;border-radius:5px;padding:0 6px;font-size:11px}} .st{{margin-left:auto;color:#64748b;font-size:11px}} .cv{{color:#94a3b8}}
.anc{{border:1px solid #cbd5e1;background:#f8fafc;border-radius:6px;padding:2px 8px;font-size:12px;cursor:pointer;color:#0f3d5c;font-family:inherit}} .ancs{{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}}
.miss{{display:block;color:#9a3412;font-size:12px;font-style:normal;font-weight:600}}
.law span{{display:inline-block;background:#eef2f7;border-radius:4px;padding:0 6px;font-size:11.5px;margin:2px 3px 0 0}}
.ctl{{display:flex;gap:7px;background:#f8fafc;border:1px dashed #cbd5e1;border-radius:7px;padding:7px}} .ctl input{{flex:1}} .ctl select,.ctl input{{border:1px solid #e2e8f0;border-radius:5px;padding:3px 7px;font-family:inherit;font-size:12.4px}}
.qt tbody tr{{cursor:pointer}} .qt tbody tr:hover{{background:#f0f9ff}} .pr{{color:#fff;border-radius:4px;padding:0 6px;font-size:11.5px}} .p高{{background:#b91c1c}}.p中{{background:#d97706}}.p低{{background:#64748b}}
.qb{{border:1px solid #e2e8f0;background:#fff;border-radius:999px;padding:5px 13px;cursor:pointer;font-family:inherit}} .qb.on{{background:#0f3d5c;color:#fff}}
.qp{{display:none}} .qp.on{{display:block}}
.disc{{background:#fff1f2;border:1px solid #fecdd3;color:#881337;border-radius:9px;padding:11px 13px;font-size:12.4px;margin-top:14px}}
footer{{padding:16px 22px;color:#64748b;font-size:12px;border-top:1px solid #e2e8f0}}
@media(max-width:1000px){{.wrap{{grid-template-columns:1fr}}.L,.R{{height:auto}}}}
@media print{{nav,.tb,.ctl{{display:none}}.wrap{{display:block}}.card .body{{display:block}}}}
</style></head><body>
{'<div class="demo">⚠ 本页面合同为「虚构演示合同」，双方名称、金额与条款均为演示编写，不对应任何真实交易。</div>' if contract.get("demo") else ''}
<header class="top"><h1>{esc(meta.get('title','采购合同'))}</h1>
<p>合同编号 {esc(meta.get('contract_no',''))} ｜ 我方身份 {esc(meta.get('review_as',''))} ｜ 供应商 {esc(meta.get('supplier',''))} ｜ 签订 {esc(meta.get('sign_date',''))}</p>
<p>审查日期 {esc(rm.get('review_date',''))} ｜ 审查人 {esc(rm.get('reviewer',''))} ｜ 范围 {esc(rm.get('review_scope',''))}</p></header>
<nav><button class="on" data-p="ov">总览</button><button data-p="ws">原文 × 风险</button><button data-p="tp">问题清单</button><button data-p="law">法规核对</button><button data-p="ms">方法与边界</button></nav>
<div class="pn on" id="ov">
  <div class="kpi"><div><b>{check["stats"]["total"]}</b><span>风险条目</span></div>
  <div><b>{check["stats"]["kind"].get("缺失",0)}</b><span>缺失</span></div><div><b>{check["stats"]["kind"].get("表述不清",0)}</b><span>表述不清</span></div>
  <div><b>{len(hits)}</b><span>涉及条款</span></div><div><b>{sum(len(v) for v in review.get('confirmations',{}).values())}</b><span>待确认问题</span></div></div>
  <div class="box"><h3>结论摘要</h3><p>{esc(sm.get('headline',''))}</p>{f'<p class="nt">{esc(note)}</p>' if note else ''}</div>
  <div class="box"><h3>优先处理</h3><ol>{top}</ol></div>
  <div class="box"><h3>合同未约定 / 需补齐</h3><ul>{''.join(f'<li>{esc(x)}</li>' for x in sm.get('missing_list',[]))}</ul></div>
  <div class="disc">{esc(rm.get('disclaimer','本结果属于业务审查提示，不构成法律意见。'))}</div>
</div>
<div class="pn" id="ws"><div class="tb"><button class="fb on" data-topic="all">全部</button>{topics}<button class="kb on" data-kind="all">全部类型</button>{kinds}
<input id="q" placeholder="搜索风险/原文/待确认…"><span id="cnt"></span></div>
<div class="wrap"><div class="L">{''.join(body)}</div><div class="R">{''.join(cards)}</div></div></div>
<div class="pn" id="tp"><p class="nt">同一批风险按办理人拆成三张清单：内部采购、法务、供应商。点击任一行定位原文与风险卡。</p>
<div style="margin:8px 0">{''.join(qbtns)}</div>{''.join(qpanes)}</div>
<div class="pn" id="law"><p class="nt">适用性核对日期 {esc(rm.get('law_check_date',''))}。下表只说明法规标准是否存在、是否现行、与本合同的关联，不据此对合同效力下结论。</p>
<table class="qt"><thead><tr><th>法规/标准</th><th>适用点</th><th>状态</th><th>核验依据（来源+日期）</th></tr></thead><tbody>{law_rows}</tbody></table>
<div class="disc">{esc(rm.get('disclaimer',''))}</div></div>
<div class="pn" id="ms"><div class="box"><h3>审查步骤</h3><ol>{''.join(f'<li>{esc(s)}</li>' for s in review.get('method',{}).get('steps',[]))}</ol></div>
<div class="box"><h3>业务提醒与法律意见的边界</h3><p>本页是业务审查提示：说明写了什么、哪些缺失、可能后果、找谁确认；<b>不是法律意见</b>，不对条款效力与责任分配下结论，涉争议解释请交法务/律师。</p></div>
<div class="disc">{esc(rm.get('disclaimer',''))}</div></div>
<footer>共 {check["stats"]["total"]} 条风险 · 单文件离线可用 · 状态与备注仅存于本浏览器</footer>
<script>
var SEED={json.dumps(seed or {}, ensure_ascii=False)};
var KEY="crx-"+document.title.slice(0,40),store={{}};
try{{store=JSON.parse(localStorage.getItem(KEY)||"{{}}")}}catch(e){{store={{}}}}
Object.keys(SEED).forEach(function(k){{if(!store[k])store[k]=SEED[k]}});
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(store))}}catch(e){{}}}}
document.querySelectorAll("nav button").forEach(function(b){{b.onclick=function(){{document.querySelectorAll("nav button").forEach(function(x){{x.classList.remove("on")}});b.classList.add("on");
document.querySelectorAll(".pn").forEach(function(p){{p.classList.remove("on")}});document.getElementById(b.dataset.p).classList.add("on")}}}});
var cards=[].slice.call(document.querySelectorAll(".card"));
cards.forEach(function(c){{var id=c.dataset.id;
c.querySelector("[data-toggle]").onclick=function(){{c.classList.toggle("op")}};
if(store[id]){{var s=c.querySelector("[data-status]"),n=c.querySelector("[data-note]");if(store[id].status)s.value=store[id].status;if(store[id].note)n.value=store[id].note;var p=c.querySelector("[data-pill]");if(store[id].status&&store[id].status!=="待处理")p.textContent=store[id].status;}}
c.querySelector("[data-status]").onchange=function(e){{(store[id]=store[id]||{{}}).status=e.target.value;save();c.querySelector("[data-pill]").textContent=e.target.value}};
c.querySelector("[data-note]").oninput=function(e){{(store[id]=store[id]||{{}}).note=e.target.value;save()}};
c.querySelectorAll(".anc").forEach(function(b){{b.onclick=function(){{go(b.dataset.clause)}}}});
}});
function go(cid){{var el=document.getElementById("cl-"+cid);if(!el)return;el.scrollIntoView({{behavior:"smooth",block:"center"}});el.classList.add("fl");setTimeout(function(){{el.classList.remove("fl")}},1600)}}
function show(id){{var c=document.querySelector('.card[data-id="'+id+'"]');if(!c)return;c.classList.add("op");c.scrollIntoView({{behavior:"smooth",block:"start"}})&&0;
document.querySelector('.tb [data-topic="all"]').click();c.scrollIntoView({{behavior:"smooth",block:"start"}});var cid=c.querySelector(".anc");if(cid)setTimeout(function(){{go(cid.dataset.clause)}},400)}}
document.querySelectorAll("[data-finding]").forEach(function(el){{el.onclick=function(){{document.querySelector('nav button[data-p="ws"]').click();show(el.dataset.finding)}}}});
var T="all",K="all",Q="";
document.querySelectorAll(".fb").forEach(function(b){{b.onclick=function(){{T=b.dataset.topic;document.querySelectorAll(".fb").forEach(function(x){{x.classList.remove("on")}});b.classList.add("on");ap()}}}});
document.querySelectorAll(".kb").forEach(function(b){{b.onclick=function(){{K=b.dataset.kind;document.querySelectorAll(".kb").forEach(function(x){{x.classList.remove("on")}});b.classList.add("on");ap()}}}});
document.getElementById("q").oninput=function(e){{Q=e.target.value.toLowerCase();ap()}};
function ap(){{var n=0;cards.forEach(function(c){{var v=(T=="all"||c.dataset.topic==T)&&(K=="all"||c.dataset.kind==K)&&(!Q||c.dataset.search.indexOf(Q)>-1);c.style.display=v?"":"none";if(v)n++}});
document.getElementById("cnt").textContent="显示 "+n+"/"+cards.length;}}
ap();
document.querySelectorAll(".qb").forEach(function(b){{b.onclick=function(){{document.querySelectorAll(".qb").forEach(function(x){{x.classList.remove("on")}});b.classList.add("on");
document.querySelectorAll(".qp").forEach(function(p){{p.classList.toggle("on",p.dataset.owner==b.dataset.owner)}})}}}});
</script></body></html>'''
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return {"out": str(out), "bytes": len(page.encode("utf-8"))}


def main() -> None:
    ap = argparse.ArgumentParser(description="通用渲染：任意合同审查数据 -> HTML（不含与特定合同绑定的设计）")
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--status-seed", default=None)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    seed = json.loads(Path(a.status_seed).read_text(encoding="utf-8")) if a.status_seed else None
    print(json.dumps({"ok": True, **build(Path(a.case), Path(a.out), a.title, seed, a.note)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
