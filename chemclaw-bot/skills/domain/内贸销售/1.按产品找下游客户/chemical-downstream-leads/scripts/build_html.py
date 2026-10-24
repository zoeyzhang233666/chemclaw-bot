#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 leads.json 渲染成一份自包含的 HTML 报告（可筛选、可打印、无外部依赖）。

用法：
    python build_html.py --dir <任务目录>                      # 读 <dir>/skill_config.json 与 <dir>/leads.json
    python build_html.py --dir <任务目录> --leads a.json --out b.html
    python build_html.py --leads leads.json --config cfg.json --out report.html

配置（skill_config.json）里用到的键：
    title / product / product_full / region_label / out_prefix
    map        [[板块, 细分行业, 逻辑工序, 用量强度, 采购与开发要点], ...]
    notes      {purpose, strength_legend, priority_legend, region_why[], data_source[],
                evidence_note[], excluded_peers[], excluded_others[], gaps[], usage_boundary[]}
    html       可选，同名字段覆盖上方文案（heading/subheading/section_titles/labels 等）

设计目标：比 Excel 更好读、更好筛、好打印。全部 CSS/JS 内联，可离线双击打开。
"""
import argparse
import html as _html
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef，。；;、）)】」》\"'（(「《]+")

CSS = """
:root{
  --ink:#16202e; --ink-2:#3b4a5f; --muted:#6b7a90; --line:#e3e8ef; --bg:#f6f8fb;
  --card:#ffffff; --accent:#2f5597; --accent-2:#1f7a6b;
  --hi:#1f7a4d; --hi-bg:#e6f5ec; --mid:#8a6100; --mid-bg:#fff5e0; --low:#5d6b7d; --low-bg:#eef1f5;
  --pri-hi:#b3261e; --pri-hi-bg:#fdeceb; --pri-mid:#8a6100; --pri-mid-bg:#fff5e0; --pri-low:#5d6b7d; --pri-low-bg:#eef1f5;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC","Hiragino Sans GB",sans-serif;
  font-size:15px;line-height:1.65;}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1400px;margin:0 auto;padding:0 24px}

/* hero */
.hero{background:linear-gradient(135deg,#1b2a41 0%,#2f5597 60%,#3f7cae 100%);color:#fff;padding:44px 0 34px}
.hero .eyebrow{font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;opacity:.8}
.hero h1{margin:10px 0 8px;font-size:31px;line-height:1.28;font-weight:700}
.hero .sub{margin:0;font-size:14.5px;opacity:.92;max-width:1000px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:12px;margin-top:26px}
.kpi{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.20);border-radius:10px;padding:14px 16px}
.kpi b{display:block;font-size:26px;line-height:1.15;font-weight:700}
.kpi span{display:block;font-size:12.5px;opacity:.85;margin-top:3px}

/* toc */
.toc{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.96);backdrop-filter:blur(6px);
  border-bottom:1px solid var(--line)}
.toc .wrap{display:flex;gap:6px;flex-wrap:wrap;padding-top:10px;padding-bottom:10px;align-items:center}
.toc a{font-size:13.5px;color:var(--ink-2);padding:5px 10px;border-radius:6px}
.toc a:hover{background:#eef2f8;color:var(--accent);text-decoration:none}

/* sections */
section{padding:34px 0 6px}
.sec-head{display:flex;align-items:baseline;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.sec-no{font-size:12px;font-weight:700;color:#fff;background:var(--accent);border-radius:5px;padding:2px 8px;letter-spacing:.05em}
.sec-head h2{margin:0;font-size:21px;font-weight:700}
.sec-head .hint{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;
  box-shadow:0 1px 2px rgba(16,32,56,.04)}
.card + .card{margin-top:12px}
.card h3{margin:0 0 8px;font-size:15.5px}
.card p{margin:6px 0}
.muted{color:var(--muted)}
.small{font-size:13px}
ul.tight{margin:6px 0 0;padding-left:20px}
ul.tight li{margin:3px 0}

/* map table */
table{width:100%;border-collapse:separate;border-spacing:0;font-size:13.5px}
thead th{background:#eef2f8;color:#28374d;font-weight:600;text-align:left;padding:10px 12px;
  border-bottom:1px solid var(--line);position:sticky;top:47px;z-index:5}
tbody td{padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:nth-child(even){background:#fbfcfe}
tbody tr:hover{background:#f2f7ff}
.map-table td:nth-child(4){white-space:nowrap;text-align:center;font-size:12.5px}
.map-table td:nth-child(1){font-weight:600;white-space:nowrap}

/* toolbar + leads table */
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.toolbar input[type=search],.toolbar select{font:inherit;font-size:13.5px;padding:7px 10px;border:1px solid #cfd8e5;
  border-radius:7px;background:#fff;color:var(--ink)}
.toolbar input[type=search]{min-width:270px}
.toolbar .count{margin-left:auto;font-size:13px;color:var(--muted)}
.toolbar .count b{color:var(--accent);font-size:15px}
.switch{display:inline-flex;align-items:center;gap:6px;font-size:13.5px;color:var(--ink-2);
  border:1px solid #cfd8e5;border-radius:7px;padding:6px 10px;background:#fff;cursor:pointer}
.btn{font:inherit;font-size:13.5px;padding:7px 12px;border-radius:7px;border:1px solid #cfd8e5;background:#fff;cursor:pointer}
.btn:hover{background:#f2f6fc}

.leads-table{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.leads-table table{font-size:13.4px}
.leads-table thead th{top:0}
.leads-table td.c-no{color:var(--muted);text-align:right;white-space:nowrap;width:46px}
.leads-table td.c-co{font-weight:600;min-width:180px}
.leads-table td.c-demand{min-width:320px;color:#2c3a4e;line-height:1.6}
.leads-table td.c-scale{min-width:250px;color:#33465e;line-height:1.6}
.leads-table td.c-src{min-width:240px;font-size:12.6px;color:var(--muted);word-break:break-all}
.tag{display:inline-block;font-size:11.5px;font-weight:600;border-radius:5px;padding:1px 7px;white-space:nowrap}
.tag.hi{color:var(--hi);background:var(--hi-bg)}
.tag.mid{color:var(--mid);background:var(--mid-bg)}
.tag.low{color:var(--low);background:var(--low-bg)}
.tag.ph{color:var(--pri-hi);background:var(--pri-hi-bg)}
.tag.pm{color:var(--pri-mid);background:var(--pri-mid-bg)}
.tag.pl{color:var(--pri-low);background:var(--pri-low-bg)}
.stars{color:#d9822b;letter-spacing:1px;white-space:nowrap}
.stars i{color:#d9dee7;font-style:normal}
.warn{color:#b3261e}
.no-result{padding:22px;text-align:center;color:var(--muted)}

/* distribution bars */
.bars{display:grid;gap:9px}
.bar-row{display:grid;grid-template-columns:190px 1fr 64px;align-items:center;gap:10px;font-size:13.3px}
.bar-track{background:#eef2f8;border-radius:5px;height:14px;overflow:hidden}
.bar-fill{height:100%;border-radius:5px;background:linear-gradient(90deg,#3f7cae,#2f5597)}
.bar-fill.alt{background:linear-gradient(90deg,#4aa08c,#1f7a6b)}
.bar-row .val{text-align:right;color:var(--ink-2);font-variant-numeric:tabular-nums}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:14px}

/* top cards */
.top-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.top-card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.top-card .hd{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.top-card .name{font-weight:700;font-size:14.5px}
.top-card .loc{color:var(--muted);font-size:12.8px;white-space:nowrap}
.top-card .demand{margin:8px 0 6px;font-size:13px;color:#2c3a4e}
.top-card .scale{font-size:12.6px;color:#33465e;border-left:3px solid #dbe4f0;padding-left:9px}
.top-card .ft{margin-top:9px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12.4px}

/* peers / gaps */
.pill-list{display:flex;flex-wrap:wrap;gap:7px;margin-top:8px}
.pill{background:#fdeceb;color:#8c2f28;border:1px solid #f6d5d2;border-radius:999px;padding:3px 11px;font-size:12.8px}
.gap-list li{margin:6px 0}

footer{margin-top:36px;padding:22px 0 34px;border-top:1px solid var(--line);color:var(--muted);font-size:12.8px}

@media (max-width:900px){
  .hero h1{font-size:24px}
  .grid-2{grid-template-columns:1fr}
  .bar-row{grid-template-columns:120px 1fr 52px}
  table.responsive thead{display:none}
  table.responsive tbody tr{display:block;border:1px solid var(--line);border-radius:9px;margin-bottom:10px;background:#fff}
  table.responsive tbody td{display:block;border:0;padding:7px 12px}
  table.responsive tbody td::before{content:attr(data-label);display:block;font-size:11.5px;color:var(--muted);
    letter-spacing:.04em;margin-bottom:2px}
  .leads-table{border:0;background:transparent}
}
@media print{
  .toc,.toolbar,.no-print{display:none!important}
  body{background:#fff;font-size:11.5px}
  .hero{background:#1b2a41!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  section{padding:14px 0 0;page-break-inside:auto}
  tbody tr{page-break-inside:avoid}
  thead th{position:static}
  .leads-table{border:1px solid #ccc}
  a{color:#000;text-decoration:none}
}
"""

JS = """
(function(){
  var table=document.getElementById('leadsTable');
  if(!table) return;
  var rows=Array.prototype.slice.call(table.tBodies[0].rows);
  var q=document.getElementById('q'),
      fb=document.getElementById('fBlock'),
      fp=document.getElementById('fProv'),
      fc=document.getElementById('fConf'),
      fr=document.getElementById('fPrio'),
      onlyHi=document.getElementById('onlyHi'),
      cnt=document.getElementById('cnt'),
      none=document.getElementById('noResult'),
      reset=document.getElementById('reset');
  function apply(){
    var kw=(q.value||'').trim().toLowerCase(), b=fb.value, p=fp.value, c=fc.value, r=fr.value, hi=onlyHi.checked;
    var shown=0;
    rows.forEach(function(tr){
      var ok=true;
      if(kw){ ok = (tr.dataset.search||'').indexOf(kw)>=0; }
      if(ok && b) ok = tr.dataset.block===b;
      if(ok && p) ok = tr.dataset.prov===p;
      if(ok && c) ok = tr.dataset.conf===c;
      if(ok && r) ok = tr.dataset.prio===r;
      if(ok && hi) ok = tr.dataset.prio==='高';
      tr.style.display = ok ? '' : 'none';
      if(ok) shown++;
    });
    cnt.innerHTML='显示 <b>'+shown+'</b> / '+rows.length+' 条';
    none.style.display = shown ? 'none' : '';
  }
  [q,fb,fp,fc,fr].forEach(function(el){ el.addEventListener(el.tagName==='SELECT'?'change':'input', apply); });
  onlyHi.addEventListener('change', apply);
  reset.addEventListener('click', function(){ q.value=''; fb.value=''; fp.value=''; fc.value=''; fr.value=''; onlyHi.checked=false; apply(); });
  apply();
})();
"""


def esc(s):
    return _html.escape(str(s if s is not None else ""), quote=True)


def split_source(src):
    """把「URL + 中文说明」拆开，返回 (url|None, 说明文本, 是否含⚠)。"""
    src = src or ""
    m = URL_RE.search(src)
    if not m:
        return None, src, "⚠" in src
    url = m.group(0)
    rest = src.replace(url, " ", 1).strip(" 　（()）")
    return url, rest, "⚠" in src


def stars(v):
    n = (v or "").count("★")
    return '<span class="stars">' + "★" * n + "<i>" + "☆" * max(0, 5 - n) + "</i></span>"


def conf_tag(v):
    cls = {"高": "hi", "中": "mid", "低": "low"}.get(v, "low")
    return f'<span class="tag {cls}">{esc(v)}</span>'


def prio_tag(v):
    cls = {"高": "ph", "中": "pm", "低": "pl"}.get(v, "pl")
    return f'<span class="tag {cls}">{esc(v)}</span>'


def bars(counter, total, alt=False):
    if not counter:
        return '<p class="muted small">（无数据）</p>'
    mx = max(counter.values()) or 1
    out = ['<div class="bars">']
    for k, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        w = max(2.0, n / mx * 100)
        out.append(
            f'<div class="bar-row"><div title="{esc(k)}">{esc(k)}</div>'
            f'<div class="bar-track"><div class="bar-fill{" alt" if alt else ""}" style="width:{w:.1f}%"></div></div>'
            f'<div class="val">{n} 条</div></div>')
    out.append('</div>')
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="")
    ap.add_argument("--leads", default="")
    ap.add_argument("--config", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    base = os.path.abspath(args.dir) if args.dir else os.getcwd()
    leads_path = args.leads or os.path.join(base, "leads.json")
    if not os.path.isabs(leads_path):
        leads_path = os.path.join(base, leads_path)
    cfg_path = args.config or os.path.join(base, "skill_config.json")
    if not os.path.isabs(cfg_path):
        cfg_path = os.path.join(base, cfg_path)

    cfg = json.load(open(cfg_path, encoding="utf-8")) if os.path.exists(cfg_path) else {}
    leads = json.load(open(leads_path, encoding="utf-8"))
    notes = cfg.get("notes") or {}
    hcfg = cfg.get("html") or {}
    product = cfg.get("product") or "产品"

    total = len(leads)
    n_prio_hi = sum(1 for x in leads if x.get("优先级") == "高")
    n_conf_hi = sum(1 for x in leads if x.get("置信度") == "高")
    blocks = Counter(x.get("板块", "未分类") for x in leads)
    provs = Counter((x.get("所在地", "") or "未标注").split("/")[0] for x in leads)
    confs = Counter(x.get("置信度", "未标注") for x in leads)
    cats = Counter((x.get("细分行业") or "未分类") for x in leads)
    n_url = sum(1 for x in leads if URL_RE.search(x.get("来源", "") or ""))
    n_warn = sum(1 for x in leads if "⚠" in (x.get("来源") or ""))

    title = hcfg.get("title") or cfg.get("title") or f"{product} —— 下游需求工厂线索表"
    sub = (hcfg.get("subheading")
           or f'{cfg.get("region_label", "")} · {len(blocks)} 个下游板块 · {total} 条线索 · {n_prio_hi} 条高优先级')
    if cfg.get("product_full"):
        sub = cfg["product_full"] + " · " + sub

    kpis = [
        (total, "线索总数"),
        (n_prio_hi, "高优先级"),
        (n_conf_hi, "高置信度"),
        (len(blocks), "覆盖板块"),
        (len([p for p in provs if p != "未标注"]), "覆盖省市"),
        (f"{n_url / total * 100:.0f}%" if total else "—", "来源含可点链接"),
    ]

    heads = ["序号", "板块", "细分行业", "公司名称", "所在地", "用量强度", "需求点（用料环节）",
             "规模线索", "优先级", "置信度", "线索来源"]
    prio_rank = {"高": 0, "中": 1, "低": 2}
    ordered = sorted(leads, key=lambda x: (x.get("板块", ""), prio_rank.get(x.get("优先级", "中"), 3),
                                           prio_rank.get(x.get("置信度", "中"), 3), x.get("公司", "")))

    rows = []
    for i, it in enumerate(ordered, 1):
        url, rest, warn = split_source(it.get("来源", ""))
        warn_prefix = '<span class="warn">⚠ </span>' if warn else ""
        if url:
            src_html = f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(url)}</a>'
            if rest:
                src_html += f'<div class="small">{warn_prefix}{esc(rest)}</div>'
        else:
            src_html = f'<span class="warn">⚠ {esc(rest or "未核实")}</span>'
        search = " ".join([str(it.get(k, "")) for k in ("公司", "需求点", "规模线索", "细分行业")]).lower()
        rows.append(
            f'<tr data-block="{esc(it.get("板块"))}" data-prov="{esc((it.get("所在地") or "").split("/")[0])}"'
            f' data-conf="{esc(it.get("置信度"))}" data-prio="{esc(it.get("优先级"))}" data-search="{esc(search)}">'
            f'<td class="c-no" data-label="序号">{i}</td>'
            f'<td data-label="板块">{esc(it.get("板块"))}</td>'
            f'<td data-label="细分行业">{esc(it.get("细分行业"))}</td>'
            f'<td class="c-co" data-label="公司名称">{esc(it.get("公司"))}</td>'
            f'<td data-label="所在地">{esc(it.get("所在地"))}</td>'
            f'<td data-label="用量强度">{stars(it.get("用量强度"))}</td>'
            f'<td class="c-demand" data-label="需求点">{esc(it.get("需求点"))}</td>'
            f'<td class="c-scale" data-label="规模线索">{esc(it.get("规模线索"))}</td>'
            f'<td data-label="优先级">{prio_tag(it.get("优先级"))}</td>'
            f'<td data-label="置信度">{conf_tag(it.get("置信度"))}</td>'
            f'<td class="c-src" data-label="线索来源">{src_html}</td></tr>')

    map_rows = "".join(
        "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in (row + [""] * 5)[:5]) + "</tr>"
        for row in (cfg.get("map") or []))

    top_cards = []
    for i, it in enumerate([x for x in ordered if x.get("优先级") == "高"], 1):
        url, rest, warn = split_source(it.get("来源", ""))
        src = (f'<a href="{esc(url)}" target="_blank" rel="noopener">打开来源</a>' if url
               else '<span class="warn">⚠ 无直链</span>')
        top_cards.append(
            f'<div class="top-card"><div class="hd"><div class="name">{i}. {esc(it.get("公司"))}</div>'
            f'<div class="loc">{esc(it.get("所在地"))}</div></div>'
            f'<div class="demand">{esc(it.get("需求点"))}</div>'
            f'<div class="scale">{esc(it.get("规模线索"))}</div>'
            f'<div class="ft">{stars(it.get("用量强度"))} {prio_tag(it.get("优先级"))} {conf_tag(it.get("置信度"))}'
            f'<span class="muted small">{esc(it.get("板块"))}</span><span style="margin-left:auto">{src}</span></div></div>')

    def bullets(items, cls=""):
        if not items:
            return ""
        return f'<ul class="tight {cls}">' + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"

    peers = "".join(f'<span class="pill">{esc(x)}</span>' for x in (notes.get("excluded_peers") or []))
    peers_html = f'<div class="pill-list">{peers}</div>' if peers else '<p class="muted small">（无）</p>'

    strengths, prios = Counter(), Counter()
    for x in leads:
        strengths[(x.get("用量强度") or "").count("★")] += 1
        prios[x.get("优先级", "未标注")] += 1
    strength_bars = bars(Counter({f"{k} 星": v for k, v in sorted(strengths.items(), reverse=True)}), total, alt=True)

    css_extra = f"<style>{hcfg.get('css','')}</style>" if hcfg.get("css") else ""
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>{css_extra}</head><body>

<header class="hero"><div class="wrap">
  <div class="eyebrow">{esc(hcfg.get("eyebrow") or "化工品下游客户开发")}</div>
  <h1>{esc(title)}</h1>
  <p class="sub">{esc(sub)}</p>
  <div class="kpis">{"".join(f'<div class="kpi"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for v, k in kpis)}</div>
</div></header>

<nav class="toc"><div class="wrap">
  <a href="#guide">① 阅读说明</a><a href="#map">② 行业地图</a><a href="#leads">③ 客户线索总表</a>
  <a href="#top">④ 重点客户 TOP</a><a href="#stats">⑤ 分布统计</a><a href="#peers">⑥ 已剔除同行</a>
  <a href="#gaps">⑦ 缺口与负结果</a>
</div></nav>

<main class="wrap">

<section id="guide"><div class="sec-head"><span class="sec-no">01</span><h2>阅读说明</h2>
  <span class="hint">口径先对齐，再看数据</span></div>
  <div class="card">
    <p><b>编制目的：</b>{esc(notes.get("purpose") or "为供应商提供下游用本产品工厂的开发线索与切入逻辑。")}</p>
    <p><b>用量强度：</b>{esc(notes.get("strength_legend") or "按单一工厂年用量标定。")}</p>
    <p><b>优先级：</b>{esc(notes.get("priority_legend") or "优先级 = 用量强度×2 + 置信度分（高3/中2/低0）。仅用于排外呼顺序。")}</p>
    {"".join(f"<p>{esc(x)}</p>" for x in (notes.get("evidence_note") or []))}
    {bullets(notes.get("region_why"), "small")}
    <p class="muted small">共 {total} 条线索，其中 <b>{n_warn}</b> 条的来源带 ⚠（已在来源列注明具体原因）。</p>
  </div>
</section>

<section id="map"><div class="sec-head"><span class="sec-no">02</span><h2>行业地图</h2>
  <span class="hint">本产品用在哪里、在哪个工序、量级多大</span></div>
  <div class="card" style="padding:0;overflow:hidden">
    <table class="map-table"><thead><tr>
      <th>行业板块</th><th>细分行业</th><th>用本产品的逻辑 / 工序</th><th>用量强度</th><th>采购与开发要点</th>
    </tr></thead><tbody>{map_rows or '<tr><td colspan="5" class="muted">（配置中未提供 map）</td></tr>'}</tbody></table>
  </div>
</section>

<section id="leads"><div class="sec-head"><span class="sec-no">03</span><h2>客户线索总表</h2>
  <span class="hint">支持关键词与四维筛选；点来源可直接打开原文</span></div>
  <div class="toolbar no-print">
    <input type="search" id="q" placeholder="搜公司 / 需求点 / 规模线索…">
    <select id="fBlock"><option value="">全部板块</option>{"".join(f'<option>{esc(b)}</option>' for b in sorted(blocks))}</select>
    <select id="fProv"><option value="">全部省市</option>{"".join(f'<option>{esc(p)}</option>' for p in sorted(provs))}</select>
    <select id="fConf"><option value="">全部置信度</option><option>高</option><option>中</option><option>低</option></select>
    <select id="fPrio"><option value="">全部优先级</option><option>高</option><option>中</option><option>低</option></select>
    <label class="switch"><input type="checkbox" id="onlyHi">只看高优先级</label>
    <button class="btn" id="reset">重置</button>
    <span class="count" id="cnt"></span>
  </div>
  <div class="leads-table">
    <table class="responsive" id="leadsTable"><thead><tr>{"".join(f"<th>{esc(h)}</th>" for h in heads)}</tr></thead>
    <tbody>{"".join(rows)}</tbody></table>
    <div class="no-result" id="noResult" style="display:none">没有符合筛选条件的线索</div>
  </div>
</section>

<section id="top"><div class="sec-head"><span class="sec-no">04</span><h2>重点客户 TOP</h2>
  <span class="hint">优先级 = 高，共 {len(top_cards)} 家</span></div>
  <div class="top-grid">{"".join(top_cards) or '<p class="muted">（无）</p>'}</div>
</section>

<section id="stats"><div class="sec-head"><span class="sec-no">05</span><h2>分布统计</h2>
  <span class="hint">按板块 / 省市 / 置信度 / 用量强度</span></div>
  <div class="card"><h3>按行业板块</h3>{bars(blocks, total)}</div>
  <div class="card"><h3>按所在省市</h3>{bars(provs, total, alt=True)}</div>
  <div class="grid-2">
    <div class="card"><h3>按置信度</h3>{bars(confs, total, alt=True)}</div>
    <div class="card"><h3>按用量强度</h3>{strength_bars}</div>
  </div>
  <div class="card"><h3>按细分品类（原始细分行业 TOP 12）</h3>{bars(Counter(dict(cats.most_common(12))), total)}</div>
</section>

<section id="peers"><div class="sec-head"><span class="sec-no">06</span><h2>已剔除的同行（竞争对手，不是客户）</h2></div>
  <div class="card">{peers_html}{bullets(notes.get("excluded_others"))}</div>
</section>

<section id="gaps"><div class="sec-head"><span class="sec-no">07</span><h2>未覆盖的缺口与负结果</h2></div>
  <div class="card"><ul class="tight gap-list">{"".join(f"<li>{esc(x)}</li>" for x in (notes.get("gaps") or ["（无）"]))}</ul></div>
</section>

<section id="boundary"><div class="sec-head"><span class="sec-no">08</span><h2>使用边界</h2></div>
  <div class="card">{bullets(notes.get("usage_boundary")) or '<p class="muted small">（无）</p>'}</div>
</section>

</main>

<footer><div class="wrap">
  {bullets(notes.get("data_source"))}
  <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} · 数据文件：{esc(os.path.basename(leads_path))} · 配置：{esc(os.path.basename(cfg_path))}</p>
  <p>本报告由 chemical-downstream-leads skill 的 build_html.py 生成；全部样式与脚本内联，可离线打开与打印。</p>
</div></footer>

<script>{JS}</script>
</body></html>
"""

    out = args.out or os.path.join(base, f"{cfg.get('out_prefix') or product + '下游需求工厂线索表'}.html")
    if not os.path.isabs(out):
        out = os.path.join(base, out)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)

    # 自检：占位符没漏、行数与数据一致、板块名都出现
    problems = []
    if "{{" in doc or "}}" in doc:
        problems.append("存在未替换的模板占位符 {{ }}")
    if len(rows) != total:
        problems.append(f"表格行数 {len(rows)} != 线索数 {total}")
    for b in blocks:
        if esc(b) not in doc:
            problems.append(f"板块未渲染：{b}")
    print(f"OK leads={total} top={n_prio_hi} blocks={len(blocks)} -> {out}")
    print(f"   页面体积 {len(doc.encode('utf-8')) / 1024:.0f} KB；表格行数 {len(rows)}；来源含链接 {n_url}/{total}")
    if problems:
        print("   ! 自检未通过：" + "；".join(problems))
        sys.exit(2)
    print("   自检通过：占位符已全部替换、行数与数据一致、板块均已渲染")


if __name__ == "__main__":
    main()
