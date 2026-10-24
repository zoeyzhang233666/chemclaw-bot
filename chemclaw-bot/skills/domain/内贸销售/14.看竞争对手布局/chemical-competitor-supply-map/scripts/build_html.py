#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a self-contained interactive HTML for one chemical + target region.

Usage:
  python build_html.py data.json output.html [--xlsx-name name.xlsx]

Everything is inlined: CSS, ECharts, China GeoJSON, normalized data, app JS.
No CDN, no network, no external file at runtime.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

import common

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "templates")
ASSETS = os.path.join(HERE, "assets")


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def fmt(n):
    if n is None:
        return "—"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    return f"{n:,.0f}" if n.is_integer() else f"{n:,.1f}"


def unit(M):
    return M.get("unit") or "万吨/年"


def proc_color(M, name):
    for p in M.get("processes") or []:
        if p.get("name") == name:
            return p.get("color") or "#8c7a5b"
    return "#8c7a5b"


def local_cap(D, prov):
    return sum(p["capacity"] for p in D["plants"] if p.get("province") == prov)


def within(D, km):
    return sum(p["capacity"] for p in D["plants"] if p.get("km") is not None and p["km"] <= km)


def forward_projects(D, year):
    return [p for p in D.get("projects", []) if p.get("year") and int(p["year"]) >= int(year)]


def top_text(D, n=5):
    rows = [p for p in D.get("provs", []) if p.get("capacity", 0) > 0][:n]
    return "、".join(f"{p['province']} {fmt(p['capacity'])}" for p in rows)


def kpi_html(D):
    M = D["meta"]
    t = D["target"]
    u = unit(M)
    local = local_cap(D, t["province"])
    w800 = within(D, 800)
    fwd = forward_projects(D, str(M.get("asof", ""))[:4] or 0)
    fwd_cap = sum(p["capacity"] for p in fwd)
    near = sum(p["capacity"] for p in D["plants"] if p.get("km") is not None and 300 < p["km"] <= 800)
    cov = (M.get("coverage") or {})
    if cov.get("industry_low") and cov.get("industry_high"):
        lo = round(D["total_cap"] / float(cov["industry_high"]) * 100)
        hi = round(D["total_cap"] / float(cov["industry_low"]) * 100)
        k5n, k5x = f"≈{lo}–{hi}%", f"样本 {fmt(D['total_cap'])} / 全国 {fmt(cov['industry_low'])}–{fmt(cov['industry_high'])}"
    else:
        k5n, k5x = f"{len(D.get('sources', []))}", "条公开来源可回溯"
    return f"""
<div class="kpi"><div class="tag">SAMPLE</div><div class="l">样本在产产能</div><div class="n">{fmt(D['total_cap'])}<small>{e(u)}</small></div><div class="x">{D['total_companies']} 家企业 · {D['total_plants']} 座工厂</div></div>
<div class="kpi c2"><div class="tag">LOCAL</div><div class="l">目标区域本地在产</div><div class="n">{fmt(local)}<small>{e(u)}</small></div><div class="x">{e(t['province'])}样本 · 到{e(t['city'])}最近 {fmt(min([p['km'] for p in D['plants'] if p.get('province') == t['province']], default=None))} km</div></div>
<div class="kpi c3"><div class="tag">GAP</div><div class="l">300–800km 在产样本</div><div class="n">{fmt(near)}<small>{e(u)}</small></div><div class="x">800km 内合计 {fmt(w800)} {e(u)}</div></div>
<div class="kpi c4"><div class="tag">PIPELINE</div><div class="l">{e(str(M.get('asof',''))[:4])}+ 公开项目毛增量</div><div class="n">{fmt(fwd_cap)}<small>{e(u)}</small></div><div class="x">{len(fwd)} 个 2026+ 项目；毛增量 ≠ 净增</div></div>
<div class="kpi c5"><div class="tag">COVERAGE</div><div class="l">样本覆盖 / 可回溯</div><div class="n">{e(k5n)}</div><div class="x">{e(k5x)}</div></div>
"""


def conclusions_html(D):
    M = D["meta"]
    items = (D.get("narrative") or {}).get("conclusions") or []
    if not items:
        items = [
            {"no": "1", "tag": "竞争密集区", "title": "样本供给集中在少数省份", "body": f"样本产能 {fmt(D['total_cap'])} {unit(M)}；{top_text(D, 5)} 是主要供给地。", "foot": "判断：先看密集区", "big": "TOP5"},
            {"no": "2", "tag": "空白 / 远距", "title": f"{D['target']['province']} 本地供给薄", "body": f"本地在产 {fmt(local_cap(D, D['target']['province']))} {unit(M)}；300–800km 在产样本 {fmt(next((b['capacity'] for b in D['bands'] if '近邻' in b['band']), 0))}。", "foot": "判断：近距有窗口", "big": "GAP"},
            {"no": "3", "tag": "未来变量", "title": "新增项目会改写格局", "body": f"{len(forward_projects(D, str(M.get('asof',''))[:4]))} 个 2026+ 项目，合计 {fmt(sum(p['capacity'] for p in forward_projects(D, str(M.get('asof',''))[:4])))} {unit(M)}。", "foot": "判断：先锁框架", "big": "NEXT"},
        ]
    out = []
    for i, c in enumerate(items[:3]):
        cls = "" if i == 0 else (" c2" if i == 1 else " c3")
        out.append(f"""<div class="cc{cls}">
  <div class="h"><b>{e(c.get('no', i+1))}</b> {e(c.get('tag',''))}</div>
  <h3>{e(c.get('title',''))}</h3>
  <p>{c.get('body','')}</p>
  <div class="foot"><span>{e(c.get('foot',''))}</span><span class="big">{e(c.get('big',''))}</span></div>
</div>""")
    return "".join(out)


def chips_html(D):
    M = D["meta"]
    out = []
    for c in D["companies"]:
        out.append(f"""<button class="chip co" data-co="{e(c['id'])}" onclick="toggleCompany('{e(c['id'])}')" aria-pressed="true" title="{e(c.get('name','') + ' · ' + fmt(c.get('capacity')) + unit(M))}">
<span class="dot" style="background:{e(proc_color(M, c.get('process')))}"></span>{e(c.get('short') or c.get('name'))} <span class="n">{fmt(c.get('capacity'))}</span></button>""")
    return "".join(out)


def process_buttons(D, attr="data-proc", on_all=True):
    M = D["meta"]
    out = [f'<button class="btn dark sm on" {attr}="all" onclick="setProc(\'all\')">全部</button>']
    for p in M.get("processes") or []:
        out.append(f'<button class="btn dark sm" {attr}="{e(p["name"])}" onclick="setProc(\'{e(p["name"])}\')">{e(p["name"])}</button>')
    return "".join(out)


def matrix_html(D):
    M = D["meta"]
    max_cap = max([c["capacity"] for c in D["companies"]] + [1])
    out = []
    for c in sorted(D["companies"], key=lambda x: -x["capacity"]):
        bar = max(4, c["capacity"] / max_cap * 100)
        plants = "、".join((p.get("name") or "").replace("基地", "").replace("厂区", "") for p in c.get("plants") or [])
        new = c.get("new") or "、".join(p.get("name", "") for p in c.get("projects") or [])
        new_html = e(new) if new else '<span class="muted">无公开新增</span>'
        out.append(f"""<tr data-co="{e(c['id'])}" onclick="openCompany('{e(c['id'])}')">
<td class="check" onclick="event.stopPropagation()"><input type="checkbox" checked onchange="toggleCompany('{e(c['id'])}', this.checked)" aria-label="叠加 {e(c.get('short'))}"></td>
<td><div class="co">{e(c.get('name'))}<small>{e(c.get('ticker') or '非上市')}{' · ' + e(c.get('alias')) if c.get('alias') else ''} · {e(c.get('hq',''))}</small></div></td>
<td><span style="color:{e(proc_color(M, c.get('process')))};font-weight:600">{e(c.get('process'))}</span></td>
<td><span class="num">{fmt(c.get('capacity'))}<small>万吨</small></span><div class="capbar"><i style="width:{bar:.1f}%"></i></div><div class="tiny muted" style="margin-top:2px">{e(c.get('cap_year',''))}</div></td>
<td><span class="num">{'<span class="dash">—</span>' if c.get('output') is None else fmt(c.get('output'))}</span>{'<div class="tiny muted">未披露</div>' if c.get('output') is None else '<div class="tiny muted">实际产出</div>'}</td>
<td><span class="num">{c.get('plant_count',0)}</span><div class="tiny muted" style="max-width:110px;line-height:1.45">{e(plants)}</div></td>
<td><span class="num">{fmt(c.get('min_km'))}</span><div class="tiny {('gA2' if '本地' in (c.get('band') or '') else 'gB2' if '近邻' in (c.get('band') or '') else '')}">{e(c.get('band') or '—')}</div></td>
<td><div class="txt">{e(c.get('coverage') or '—')} <span class="tag infer">D</span></div></td>
<td><div class="txt">{new_html}</div></td>
<td><span class="grade g{e(c.get('grade'))}" style="white-space:nowrap"><b></b>{e(c.get('grade'))}</span></td>
</tr>""")
    return "".join(out)


def prov_table_html(D):
    M = D["meta"]
    t = D["target"]
    out = []
    for p in D.get("provs") or []:
        judge = p.get("judge") or ("空白" if not p.get("capacity") else "薄")
        demand = (D.get("demand_by_prov") or {}).get(p["province"], "")
        out.append(f"""<tr data-prov="{e(p['province'])}">
<td><b>{e(p['province'])}</b></td>
<td><span class="num">{fmt(p.get('capacity'))}</span></td>
<td>{p.get('plants',0)}</td>
<td>{p.get('n_companies',0)}</td>
<td>{e(p.get('dominant','—'))}</td>
<td>{fmt(p.get('km_min'))}</td>
<td><span class="tag {'infer' if p.get('capacity',0)==0 else ''}">{e(judge)}</span></td>
<td>{e('本地' if p.get('capacity',0) else '无在产')}</td>
<td class="tiny">{e(demand)}</td>
<td>{p.get('prospect_count',0)} 家</td>
</tr>""")
    return "".join(out)


def projects_html(D):
    M = D["meta"]
    u = unit(M)
    items = sorted(D.get("projects") or [], key=lambda p: (p.get("year") or 9999, -p.get("capacity", 0)))
    if not items:
        return '<div class="p" style="color:#b9b39f">未录入公开项目；不要用“无项目”代替“没查到”。</div>'
    out, last = [], None
    for p in items:
        y = p.get("year") or "时间待核"
        if y != last:
            out.append(f'<div class="tl-year">{e(y)}</div>')
            last = y
        src = ""
        if p.get("source_ids"):
            s = (D.get("source_map") or {}).get(p["source_ids"][0])
            src = f'<a href="{e(s["url"])}" target="_blank" rel="noopener" style="color:#e8c98e;border:0;font-size:10px">{e(p["source_ids"][0])}</a>' if s else e(p["source_ids"][0])
        out.append(f"""<div class="proj">
  <div class="cap">{fmt(p.get('capacity'))}<small>{e(u)}</small></div>
  <div class="body">
    <h4>{e(p.get('name'))} <span>{e(p.get('company_short') or p.get('company'))}</span></h4>
    <div class="line">{e(p.get('location'))} · {e(p.get('timing'))}</div>
    <div class="impact">{e(p.get('impact'))}</div>
    <div class="meta"><span class="st">{e(p.get('status'))}</span><span class="reloc">{e(p.get('kind'))}</span><span>净增 {e(p.get('net'))}</span><span>{e(p.get('grade'))}级</span>{src}</div>
  </div>
</div>""")
    return "".join(out)


def project_foot(D):
    n = D.get("narrative") or {}
    return n.get("pipeline_foot") or "销售动作应从“有没有货”转向“到厂成本、库存前置、指标稳定性”。"


def anchor_html(D):
    M = D["meta"]
    t = D["target"]
    n = D.get("narrative") or {}
    facts = n.get("anchor_facts") or []
    use = n.get("anchor_use_value")
    use_label = n.get("anchor_use_label") or f"{M.get('dose_label','用量级')}*"
    fact_html = "".join(f'<div class="fact"><span>{e(f.get("label"))}</span><b>{e(f.get("value"))}</b></div>' for f in facts[:6])
    if not fact_html:
        fact_html = f'<div class="fact"><span>本地在产</span><b>{fmt(local_cap(D, t["province"]))} {e(unit(M))}</b></div>'
    # nearest plants ladder
    stops = sorted([p for p in D["plants"]], key=lambda p: p.get("km") or 99999)[:5]
    amax = max([p.get("km") or 1 for p in stops] + [1])
    ladder = "".join(f'<div class="tl-row"><span>{e((p.get("company_short") or p.get("company") or "") + " " + (p.get("city") or ""))}</span><span class="bar"><i style="width:{max(1.5, (p.get("km") or 0)/amax*100):.1f}%"></i></span><b>{fmt(p.get("km"))}</b></div>' for p in stops)
    big = f'<div class="big">{fmt(use)}<small>{e(use_label)}</small></div>' if use is not None else ""
    return f"""<aside class="anchor">
  <div class="lab">ANCHOR CUSTOMER · 示例客户</div>
  <h3>{e(t.get('customer_short') or t.get('customer'))}</h3>
  <div class="sub">{e(t.get('customer'))}</div>
  {big}
  <div class="facts">{fact_html}</div>
  <div class="note">{n.get('anchor_note','用量为按行业吨耗推算；仅作用量级，不是企业披露。')}</div>
  <div class="ladder">{ladder}</div>
</aside>"""


def segments_html(D):
    counts = {}
    for p in D.get("prospects") or []:
        counts[p.get("segment") or "待补"] = counts.get(p.get("segment") or "待补", 0) + 1
    out = [f'<button class="seg-chip on" data-seg="all" onclick="setSeg(\'all\')">全部 <span class="c">{len(D.get("prospects") or [])}</span></button>']
    for seg, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        out.append(f'<button class="seg-chip" data-seg="{e(seg)}" onclick="setSeg(\'{e(seg)}\')">{e(seg)} <span class="c">{n}</span></button>')
    return "".join(out)


def prospects_html(D):
    M = D["meta"]
    out = []
    for p in D.get("prospects") or []:
        out.append(f"""<tr data-seg="{e(p.get('segment',''))}" data-prov="{e(p.get('province',''))}" onclick="openProspect('{e(p['id'])}')" style="cursor:pointer">
<td><span class="tag">{e(p.get('priority','B'))}</span></td>
<td><b>{e(p.get('short') or p.get('name'))}</b><div class="tiny muted">{e(p.get('city',''))}</div></td>
<td>{e(p.get('segment',''))}</td>
<td class="tiny">{e(p.get('scale',''))}</td>
<td class="tiny">{e(p.get('ash') or p.get('dose') or '—')}</td>
<td class="tiny">{e(p.get('scene',''))}</td>
<td class="tiny">{e(p.get('why',''))}<br><span style="color:var(--copper)">下一步：{e(p.get('next',''))}</span></td>
<td><span class="grade g{e(p.get('grade','B'))}"><b></b>{e(p.get('grade','B'))}</span></td>
</tr>""")
    return "".join(out) or '<tr><td colspan="8" class="tiny muted">未录入潜客；不要用空表代替“当地没有客户”。</td></tr>'


def prospect_conclusions_html(D):
    items = (D.get("narrative") or {}).get("prospect_conclusions") or []
    out = []
    for i, c in enumerate(items[:3]):
        cls = "" if i == 0 else (" c2" if i == 1 else " c3")
        out.append(f"""<div class="cc{cls}">
  <div class="h"><b>{e(c.get('no',i+1))}</b> {e(c.get('tag',''))}</div>
  <h3>{e(c.get('title',''))}</h3>
  <p>{c.get('body','')}</p>
  <div class="foot"><span>{e(c.get('foot',''))}</span><span class="big">{e(c.get('big',''))}</span></div>
</div>""")
    return "".join(out)


def sources_html(D):
    out = []
    for s in D.get("sources") or []:
        url = s.get("url") or "#"
        out.append(f"""<tr><td class="tiny">{e(s.get('id'))}</td>
<td><a href="{e(url)}" target="_blank" rel="noopener">{e(s.get('org'))} · {e(s.get('title'))}</a><div class="tiny muted" style="margin-top:2px">{e(s.get('used',''))}</div></td>
<td class="tiny">{e(s.get('date'))}</td><td class="tiny">{e(s.get('used',''))[:70]}</td><td><span class="grade g{s.get('type','B') if s.get('type') in ('A','B','C','D') else 'B'}"><b></b>{e(s.get('type','B'))}</span></td></tr>""")
    return "".join(out)


def conflicts_html(D):
    out = []
    for i, c in enumerate(D.get("conflicts") or []):
        out.append(f"""<div class="conflict">
<div class="h"><span class="n">{i+1:02d}</span>{e(c.get('item'))}</div>
<div class="row"><div class="a"><span class="k">口径 A</span>{e(c.get('a'))}</div><div class="b"><span class="k">口径 B</span>{e(c.get('b'))}</div></div>
<div class="adopt"><b>采用：</b>{e(c.get('adopt'))}</div>
<div class="why"><b>理由：</b>{e(c.get('why'))} <b>影响：</b>{e(c.get('impact'))}</div>
</div>""")
    return "".join(out)


def gaps_html(D):
    out = []
    for g in (D.get("gaps") or []) + (D.get("boundaries") or []):
        out.append(f'<div class="gitem"><b>{e(g.get("title"))}</b><span>{e(g.get("body"))}</span></div>')
    if not out:
        return '<div class="gitem"><b>数据缺口待补</b><span>至少写清样本范围、负增量、距离口径、非上市披露和潜客范围。</span></div>'
    return "".join(out)


def method_conclusions_html(D):
    items = (D.get("narrative") or {}).get("method_conclusions") or []
    out = []
    for i, c in enumerate(items[:3]):
        cls = "" if i == 0 else (" c2" if i == 1 else " c3")
        out.append(f"""<div class="cc{cls}">
  <div class="h"><b>{e(c.get('no',''))}</b> {e(c.get('tag',''))}</div>
  <h3>{e(c.get('title',''))}</h3>
  <p>{c.get('body','')}</p>
</div>""")
    return "".join(out)


def target_ladder_html(D):
    rows = D.get("bands") or []
    mx = max([b.get("capacity", 0) for b in rows] + [1])
    return "".join(f'<div class="tl-row"><span>{e(str(b.get("band","")).split(" ")[0])}</span><span class="bar"><i style="width:{b.get("capacity",0)/mx*100:.1f}%"></i></span><b>{fmt(b.get("capacity"))}</b></div>' for b in rows)


def target_note(D):
    M = D["meta"]
    return M.get("target_note") or f"距离为{M.get('distance_label','直线距离')}，不是铁路/水运运距；正式版可替换目标区域与我方供货半径。"


def page(D, xlsx_name="download.xlsx"):
    M = D["meta"]
    t = D["target"]
    u = unit(M)
    n = D.get("narrative") or {}
    title = f"{M.get('product_short') or M.get('product')}竞争供给地图 · {t['region']}"
    css = open(os.path.join(TEMPLATES, "style.css"), encoding="utf-8").read()
    app = open(os.path.join(TEMPLATES, "app.js"), encoding="utf-8").read()
    echarts = open(os.path.join(ASSETS, "echarts.min.js"), encoding="utf-8").read()
    geo = open(os.path.join(ASSETS, "china_prov.json"), encoding="utf-8").read()
    data_json = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    geo_json = geo.replace("</", "<\\/")
    brand_mark = e(M.get("brand_mark") or "化")
    brand_name = e(M.get("brand_name") or "化图 · SUPPLY MAP")
    brand_sub = e(M.get("brand_sub") or "COMPETITIVE SUPPLY LAYOUT")
    # target stats: local, within 800, demand (optional), anchor use (optional)
    local = local_cap(D, t["province"])
    w800 = within(D, 800)
    demand_v = M.get("target_demand")
    demand_l = M.get("target_demand_label") or "区域需求"
    anchor_use = n.get("anchor_use_value")
    anchor_lab = n.get("anchor_use_label") or "示例客户用量"
    stats = [
        ("本地在产", fmt(local), u),
        ("800km 内在产", fmt(w800), u),
    ]
    if demand_v is not None:
        stats.append((demand_l, fmt(demand_v), u + "*"))
    if anchor_use is not None:
        stats.append((anchor_lab, fmt(anchor_use), u + "**"))
    target_stats = "".join(f'<div><div class="k">{e(k)}</div><div class="v">{e(v)}<small>{e(su)}</small></div></div>' for k, v, su in stats[:4])
    proc_buttons = process_buttons(D, "data-proc")
    # matrix proc buttons need distinct onclick; build separately
    matrix_proc = ['<button class="btn sm on" data-mproc="all" onclick="setMatrixProc(\'all\')">全部工艺</button>']
    for p in M.get("processes") or []:
        matrix_proc.append(f'<button class="btn sm" data-mproc="{e(p["name"])}" onclick="setMatrixProc(\'{e(p["name"])}\')">{e(p["name"])}</button>')
    matrix_proc = "".join(matrix_proc)
    # legend
    legend = "".join(f'<span class="lg"><i style="background:{e(p.get("color"))}"></i>{e(p.get("name"))}</span>' for p in M.get("processes") or [])
    legend += '<span class="lg"><i class="sq" style="background:#d9a441"></i>新增/在建</span><span class="lg"><span class="line"></span>到目标城市</span><span class="lg"><i style="background:#a23b2a;box-shadow:0 0 0 3px rgba(162,59,42,.3)"></i>目标区域</span>'

    synth_banner = ''
    if M.get("is_synthetic"):
        synth_banner = '<div class="synth">结构示例 · 不是研究结论 · 企业/数字/链接均为虚构，禁止用于真实业务判断</div>'

    hero_pills = f"""<span class="pill"><span class="dot"></span>{D['total_companies']} 家企业 · {D['total_plants']} 座工厂</span>
<span class="pill"><span class="dot"></span>{fmt(D['total_cap'])} {e(u)}样本产能</span>
<span class="pill warn"><span class="dot"></span>产能 ≠ 产量 · 样本 ≠ 全行业</span>
<span class="pill red"><span class="dot"></span>不推算市场份额</span>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>{css}</style>
</head>
<body>
{synth_banner}
<header class="top">
  <div class="in">
    <div class="brand">
      <div class="mark">{brand_mark}</div>
      <div><div class="t">{brand_name}</div><div class="s">{brand_sub}</div></div>
    </div>
    <nav class="nav">
      <a href="#mapsec">供给地图</a><a href="#matrixsec">企业矩阵</a><a href="#densitysec">区域密度</a><a href="#newsec">新增产能</a><a href="#prospectsec">区域潜客</a><a href="#methodsec">口径来源</a>
    </nav>
    <div class="meta">
      <span class="hide-s">数据截至 <b>{e(M.get('asof'))}</b></span>
      <span class="hide-s">样本 <b>{D['total_companies']} 家 / {D['total_plants']} 厂</b></span>
      <a class="btn sm" href="{e(xlsx_name)}">下载 Excel</a>
    </div>
  </div>
</header>

<main>
<section class="hero wrap">
  <div class="hero-grid">
    <div>
      <div class="eyebrow">内贸销售 · 竞争供给布局 / 区域空白</div>
      <h1>{e(M.get('product_short') or M.get('product'))}竞争供给<br><em>地图与区域空白</em></h1>
      <p class="lede">{n.get('hero_lede','')}</p>
      <div class="hero-meta">{hero_pills}</div>
    </div>
    <aside class="target-card">
      <div class="target-head">TARGET REGION <span>DEMO</span></div>
      <div class="target-city">{e(t['region'])}</div>
      <div class="target-sub">示例客户：{e(t.get('customer'))}</div>
      <div class="target-stats">{target_stats}</div>
      <div class="target-note">{e(target_note(D))}</div>
      <div class="target-ladder">{target_ladder_html(D)}</div>
    </aside>
  </div>
  <div class="kpis">{kpi_html(D)}</div>
</section>

<section class="wrap" style="padding-top:24px"><div class="concl">{conclusions_html(D)}</div></section>

<section class="sec wrap" id="mapsec">
  <div class="sec-head">
    <div class="sec-no">01 / SUPPLY MAP</div>
    <div><h2>竞争供给地图</h2><div class="hint" style="font-size:12px;color:var(--muted);margin-top:6px">勾选企业叠加图层；点击省份看本地供给与最近外省货源；点击气泡看工厂明细。</div></div>
    <div class="sub">{e(n.get('map_sub',''))}</div>
  </div>
  <div class="map-shell">
    <div class="map-main">
      <div class="map-toolbar">
        <div class="grp"><span class="lab">企业</span>{chips_html(D)}<button class="btn dark sm" onclick="allCompanies(true)">全选</button><button class="btn dark sm" onclick="allCompanies(false)">清空</button></div>
        <div class="sep"></div>
        <div class="grp"><span class="lab">工艺</span>{proc_buttons}</div>
        <div class="sep"></div>
        <div class="grp"><span class="lab">图层</span><button class="btn dark sm on" id="tglLines" onclick="toggleLayer('lines')">距离线</button><button class="btn dark sm on" id="tglProj" onclick="toggleLayer('projects')">新增项目</button><button class="btn dark sm on" id="tglLabels" onclick="toggleLayer('labels')">标签</button><button class="btn dark sm" onclick="resetView()">重置</button></div>
      </div>
      <div id="map" role="img" aria-label="{e(title)}"></div>
      <div class="map-hint">点击省份 / 工厂气泡<br>滚轮缩放 · 拖拽平移</div>
      <div class="map-legend">{legend}</div>
    </div>
    <aside class="map-side">
      <div class="side-head"><div><h3 id="sideTitle">全国样本</h3><div class="tiny" id="sideSub" style="color:#9fb2a7;margin-top:3px">{D['total_companies']} 家企业 · {D['total_plants']} 座工厂 · {fmt(D['total_cap'])} {e(u)}</div></div><span class="tag" id="sideTag">OVERVIEW</span></div>
      <div class="side-body" id="sideBody"></div>
      <div class="s-cta"><button class="btn dark" id="sideCta" onclick="showProspects(null)">查看{e(t['province'])}潜客样本 →</button></div>
    </aside>
  </div>
  <div class="grades" style="margin-top:14px"><span class="grade gA"><b></b>A 公司定期报告 / 政府文件</span><span class="grade gB"><b></b>B 公司 IR / 行业统计 / 券商拆分</span><span class="grade gC"><b></b>C 企业公开业务信息</span><span class="grade gD"><b></b>D 物流/覆盖推断</span><span class="tiny muted" style="margin-left:auto">{e(M.get('grade_note') or '覆盖度不等于市场份额。')}</span></div>
</section>

<section class="sec wrap" id="matrixsec">
  <div class="sec-head"><div class="sec-no">02 / COMPANY MATRIX</div><div><h2>企业对比矩阵</h2><div class="hint" style="font-size:12px;color:var(--muted);margin-top:6px">产能、产量、工厂、距离、覆盖线索与新增项目并排看；点击行看工厂明细与来源。</div></div><div class="sub">排序/筛选/勾选会同步地图。覆盖线索为物流可达性推断（D），不是企业披露。</div></div>
  <div class="table-wrap">
    <div class="table-tools">
      <div class="search"><span style="color:var(--muted);font-size:13px">⌕</span><input id="q" type="text" placeholder="搜索企业、基地、省份…" oninput="setQuery(this.value)"></div>
      {matrix_proc}
      <label class="tiny muted" style="display:flex;align-items:center;gap:5px;cursor:pointer"><input type="checkbox" id="onlyNew" onchange="setOnlyNew(this.checked)" style="accent-color:var(--green)"> 仅有新增/在建</label>
      <span class="count" id="mcount">{D['total_companies']} 家</span>
    </div>
    <div class="table-scroll"><table class="t" id="matrix"><thead><tr><th class="check no-sort"><span class="sr">选择</span></th><th data-sort="name">企业 / 基地</th><th data-sort="process">工艺</th><th data-sort="capacity">产能 <span class="muted">万吨/年</span></th><th data-sort="output">最新产量 <span class="muted">万吨</span></th><th data-sort="plant_count">工厂</th><th data-sort="min_km">到{e(t['city'])} <span class="muted">km</span></th><th class="no-sort">区域覆盖线索 <span class="tag infer">D 推断</span></th><th class="no-sort">新增 / 在建</th><th data-sort="grade">等级</th></tr></thead><tbody id="matrixBody">{matrix_html(D)}</tbody></table></div>
  </div>
</section>

<section class="sec wrap" id="densitysec">
  <div class="sec-head"><div class="sec-no">03 / DENSITY</div><div><h2>供给密度与距离分层</h2><div class="hint" style="font-size:12px;color:var(--muted);margin-top:6px">省级在产产能、到目标区域的距离带、工艺结构，三个角度判断“密集”与“空白”。</div></div><div class="sub">{e(n.get('density_sub',''))}</div></div>
  <div class="chart-grid">
    <div class="panel"><div class="ph"><div><h3>省级在产产能 · 样本</h3><div class="legend-inline">{''.join(f'<span><i style="background:{e(p.get("color"))}"></i>{e(p.get("name"))}主导</span>' for p in M.get('processes') or [])}</div></div><div class="hint">点击柱条 → 地图定位该省<br>单位：{e(u)}</div></div><div id="chProv" class="chart"></div></div>
    <div class="chart-stack"><div class="panel"><div class="ph"><div><h3>到{e(t['city'])} · 距离带</h3></div><div class="hint">{e(u)}</div></div><div id="chBand" class="chart sm"></div></div><div class="panel"><div class="ph"><div><h3>工艺结构</h3></div><div class="hint">点击扇区筛选</div></div><div id="chProc" class="chart sm"></div></div></div>
  </div>
  <div class="table-wrap" style="margin-top:16px"><div class="table-tools"><div style="font:700 15px var(--display)">区域对照表</div><div class="tiny muted" style="margin-left:8px">按样本产能降序 · 点击行定位地图</div><span class="count">{len(D['provs'])} 个省级区域</span></div><div class="table-scroll" style="max-height:560px"><table class="t" id="provTable" style="min-width:980px"><thead><tr><th>省份</th><th>样本在产 <span class="muted">万吨/年</span></th><th>工厂</th><th>企业</th><th>主导工艺</th><th>到{e(t['city'])} <span class="muted">km</span></th><th>距离带</th><th>本地供给</th><th>需求 / 空白线索</th><th>潜客样本</th></tr></thead><tbody>{prov_table_html(D)}</tbody></table></div></div>
</section>

<section class="sec dark" id="newsec"><div class="wrap"><div class="sec-head"><div class="sec-no">04 / CAPACITY PIPELINE</div><div><h2 style="color:#fff8e8">未来新增产能 · 时间线</h2><div class="hint" style="font-size:12px;color:#b9b39f;margin-top:6px">{n.get('pipeline_intro','')}</div></div><div class="sub">项目状态以公开披露为准；毛增量不等于净增。</div></div><div class="timeline">{projects_html(D)}</div><div class="tl-foot"><b>判断：</b>{project_foot(D)}</div></div></section>

<section class="sec wrap" id="prospectsec">
  <div class="sec-head"><div class="sec-no">05 / REGION → PROSPECTS</div><div><h2>从区域到潜客</h2><div class="hint" style="font-size:12px;color:var(--muted);margin-top:6px">{e(n.get('prospect_intro',''))}</div></div><div class="sub">{e(n.get('prospect_note',''))}</div></div>
  <div class="prospect-grid">
    {anchor_html(D)}
    <div>
      <div class="table-tools" style="border:1px solid var(--line);border-radius:12px 12px 0 0;background:var(--card)"><span class="tiny muted" style="font-weight:600">赛道</span>{segments_html(D)}<span class="count" id="pcount">{len(D.get('prospects') or [])} 家</span></div>
      <div class="table-wrap" style="border-radius:0 0 12px 12px;box-shadow:none"><div class="table-scroll" style="max-height:640px"><table class="t prospect-table" id="prospectTable"><thead><tr><th>优先级</th><th>客户 / 城市</th><th>赛道</th><th>公开规模</th><th>{e(M.get('dose_label') or '用量级')}</th><th>{e(M.get('use_label') or '使用场景')}</th><th>为什么优先 / 下一步</th><th>等级</th></tr></thead><tbody>{prospects_html(D)}</tbody></table></div></div>
      <div class="tiny muted" style="margin-top:8px">{e(n.get('prospect_scope_note',''))}</div>
    </div>
  </div>
  <div class="concl" style="margin-top:18px">{prospect_conclusions_html(D)}</div>
</section>

<section class="sec wrap" id="methodsec">
  <div class="sec-head"><div class="sec-no">06 / METHOD & SOURCES</div><div><h2>口径、冲突与来源</h2><div class="hint" style="font-size:12px;color:var(--muted);margin-top:6px">每条产能都能回到来源；冲突口径不强行“抹平”，而是并列展示并说明采用理由。</div></div><div class="sub">{e(M.get('grade_note') or 'A 公司定期报告/政府文件；B 公司IR/行业统计/券商拆分；C 企业公开业务信息；D 物流/覆盖推断。')}</div></div>
  <div class="two-col">
    <div class="table-wrap"><div class="table-tools"><div style="font:700 15px var(--display)">来源清单</div><div class="tiny muted" style="margin-left:8px">点击标题跳转原文</div><span class="count">{len(D.get('sources') or [])} 条</span></div><div class="table-scroll" style="max-height:560px"><table class="t src-table"><thead><tr><th>ID</th><th>来源 / 标题</th><th>日期</th><th>用于</th><th>等级</th></tr></thead><tbody>{sources_html(D)}</tbody></table></div></div>
    <div><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:9px"><div style="font:700 17px var(--display)">口径冲突 · 采用判断</div><span class="tiny muted">{len(D.get('conflicts') or [])} 项</span></div><div style="max-height:560px;overflow:auto;padding-right:3px">{conflicts_html(D)}</div></div>
  </div>
  <div class="gapbox"><div class="gh">数据缺口 / GAPS · 这是下一步取证清单，不是免责声明</div><div class="ggrid">{gaps_html(D)}</div></div>
  <div class="concl" style="margin-top:18px">{method_conclusions_html(D)}</div>
</section>

<footer class="foot wrap">
  <div><b>{e(M.get('product_short') or M.get('product'))} · 竞争供给布局与区域空白</b> · 内贸销售演示<br>数据截至 {e(M.get('asof'))}；产能单位：{e(u)}；距离：{e(M.get('distance_label','直线距离'))}。</div>
  <div class="r">{e(M.get('disclaimer','本报告为销售线索与竞争布局研究，不构成投资建议、价格承诺或市场份额结论。'))}<br>正式版可替换目标区域、竞争企业名单、我方产能与供货半径。</div>
</footer>
</main>

<div class="drawer" id="drawer" aria-hidden="true"><div class="drawer-mask" onclick="closeDrawer()"></div><aside class="drawer-panel" role="dialog" aria-modal="true" aria-label="明细"><div class="drawer-top"><div class="lab" id="drawerLab">DETAIL</div><button class="drawer-close" onclick="closeDrawer()" aria-label="关闭">×</button></div><div class="drawer-body" id="drawerBody"></div></aside></div>
<div class="toast" id="toast" role="status"></div>

<script>window.__DATA__={data_json};</script>
<script>{echarts}</script>
<script>window.__GEO__={geo_json};</script>
<script>{app}</script>
</body>
</html>
"""


def build(data_path, out_path, xlsx_name="download.xlsx"):
    D = common.load(data_path)
    html = page(D, xlsx_name)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("out")
    ap.add_argument("--xlsx-name", default="download.xlsx")
    a = ap.parse_args()
    p = build(a.data, a.out, a.xlsx_name)
    print("OK", p, round(os.path.getsize(p) / 1024 / 1024, 2), "MB")


if __name__ == "__main__":
    main()
