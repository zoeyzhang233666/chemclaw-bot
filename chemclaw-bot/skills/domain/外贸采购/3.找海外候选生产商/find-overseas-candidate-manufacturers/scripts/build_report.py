#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_report.py — 由 case_output.json 生成交互式 HTML 海外生产商调查报告。

用法：
    python build_report.py <case_output.json> [输出.html]

不依赖任何特定国家/产品；国家、产品、企业、图谱节点全部来自 JSON。
"""
import json, os, html, sys

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(2)
SRC = sys.argv[1]
DATA = json.load(open(SRC, encoding='utf-8'))
BASE = os.path.dirname(os.path.abspath(SRC))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, 'out', '海外生产商调查报告.html')
os.makedirs(os.path.dirname(OUT), exist_ok=True)

meta = DATA['meta']
S = {s['id']: s for s in DATA['sources']}
Q = {q['id']: q for q in DATA['questions']}

# rank companies: verified manufacturers first
GRADE_ORDER = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
MANUF_TYPES = {'MANUFACTURER', 'JV_MANUFACTURER'}
companies = sorted(DATA['companies'], key=lambda c: (GRADE_ORDER.get(c['grade'], 9),
                                                     0 if c['entity_type'] in MANUF_TYPES else 1,
                                                     c.get('rank', 99)))
for i, c in enumerate(companies, 1):
    c['_rank'] = i

FILTER_GROUPS = DATA['groups']
CTRY = meta.get('buyer_context', {}).get('origin', '目标国家')
PROD = meta['product']['name_cn']


def cap_main(c):
    """通用产能主值：优先 capacity.expr，其次任意 *_mtpa / *_kta 键。"""
    cap = c.get('capacity') or {}
    if cap.get('expr'):
        return cap['expr']
    for k, v in cap.items():
        if k.endswith('_mtpa') or k.endswith('_kta') or k == 'main':
            return v
    return '—'


def esc(t):
    return html.escape(str(t) if t is not None else '')


def src_links(ev_list):
    out = []
    for ev in ev_list:
        sid = ev.get('src', '')
        if sid in S:
            out.append(sid)
    return out


# ---------- derive filter facets ----------
sites = sorted({c.get('site', '') for c in companies if c.get('site')})
facets = {
    'grade': ['A', 'B', 'C', 'D'],
    'site': [s for s in sites if s],
    'type': ['MANUFACTURER', 'JV_MANUFACTURER', 'AFFILIATE_SALES', 'TRADER', 'AGENT', 'UNKNOWN'],
}

cards_html = []
for c in companies:
    is_manuf = c['entity_type'] in MANUF_TYPES
    # column placement: only grade-A/B verified-or-candidate manufacturing bodies go left;
    # C (non-target product) and D (sales/trading) go right with their reason stated.
    left_col = is_manuf and c['grade'] in ('A', 'B')
    ev_rows = ''.join(
        f'<tr><td class="ev-id">{esc(e["id"])}</td><td>{esc(e["type"])}</td>'
        f'<td><span class="conf conf-{ "hi" if e.get("conf","").startswith(("高","直接")) else "mid"}">{esc(e.get("conf",""))}</span></td>'
        f'<td>{esc(e["text"])}<div class="src-line">来源：<a href="{esc(S.get(e["src"],{}).get("url","#"))}" target="_blank" rel="noopener">{esc(e["src"])}</a></div></td></tr>'
        for e in c['evidence'])
    qs = ''.join(f'<li><b>{esc(Q[q]["id"])}</b> {esc(Q[q]["q"])}</li>' for q in c.get('open_questions', []) if q in Q)
    chans = ''.join(f'<tr><td>{esc(x["channel"])}</td><td class="mono">{esc(x["value"])}</td><td>{esc(x["status"])}</td></tr>' for x in c.get('official_channels', []))
    specs = ''.join(f'<tr><td>{esc(p["product"])}</td><td>{esc(p["grade"])}</td><td>{esc(p["spec"])}</td></tr>' for p in c.get('products_specs', []))
    certs = ''.join(f'<tr><td>{esc(x["cert"])}</td><td>{esc(x["status"])}</td></tr>' for x in c.get('certifications', []))
    cap = c.get('capacity', {})
    sites_txt = c.get('site') or '—'
    cards_html.append(f'''
<article class="co-card g{c['grade']}" id="{esc(c['id'])}"
  data-grade="{c['grade']}" data-type="{c['entity_type']}" data-kind="{'manu' if left_col else 'trade'}"
  data-site="{esc(c.get('site',''))}" data-name="{esc(c['legal_name'] + ' ' + c.get('cn_name',''))}">
  <header class="co-head" onclick="toggleCard(this)">
    <div class="rank">#{c['_rank']}</div>
    <div class="co-title">
      <h3>{esc(c['legal_name'])}</h3>
      <p class="sub">{esc(c.get('cn_name',''))} · {esc(c.get('legal_name_ar',''))}</p>
    </div>
    <div class="badges">
      <span class="badge grade-badge">证据等级 {c['grade']}</span>
      <span class="badge type-badge">{esc(c['entity_type_label'])}</span>
    </div>
    <div class="chev">▾</div>
  </header>
  <div class="co-body">
    <div class="kv-grid">
      <div><span class="k">所属集团</span><span class="v">{esc(next((g['name'] for g in FILTER_GROUPS if g['id']==c.get('group')), '—'))}</span></div>
      <div><span class="k">股权/归属</span><span class="v">{esc(c.get('ownership','—'))}</span></div>
      <div><span class="k">工厂所在地</span><span class="v">{esc(sites_txt)}</span></div>
      <div><span class="k">成立/投产</span><span class="v">{esc(c.get('established','—'))}</span></div>
      <div><span class="k">公开产能</span><span class="v"><b>{esc(cap_main(c))}</b> {esc(cap.get('unit',''))}</span></div>
      <div><span class="k">生产工艺</span><span class="v">{esc((c.get('process') or '—')[:120])}</span></div>
    </div>

    <div class="verdict {"ok" if c['grade']=='A' else "warn" if c['grade']=='B' else "bad"}">
      <b>判定理由：</b>{esc(c['grade_reason'])}
    </div>

    <div class="two-col">
      <section>
        <h4>产品与规格</h4>
        <table class="mini"><thead><tr><th>产品</th><th>牌号/用途</th><th>公开规格</th></tr></thead><tbody>{specs or '<tr><td colspan=3>待核验</td></tr>'}</tbody></table>
        <h4>产能口径与注意事项</h4>
        <p class="cap-note">{esc(cap.get('detail','—'))}</p>
        <p class="warn-note">⚠ {esc(cap.get('caveat','—'))}</p>
      </section>
      <section>
        <h4>官方公开联系渠道</h4>
        <table class="mini"><thead><tr><th>渠道</th><th>信息</th><th>核验状态</th></tr></thead><tbody>{chans or '<tr><td colspan=3>待核验</td></tr>'}</tbody></table>
        <h4>认证与质量文件</h4>
        <table class="mini"><thead><tr><th>认证</th><th>状态</th></tr></thead><tbody>{certs or '<tr><td colspan=2>待核验</td></tr>'}</tbody></table>
      </section>
    </div>

    <h4>制造证据链</h4>
    <table class="ev-table"><thead><tr><th>ID</th><th>证据类型</th><th>置信</th><th>证据内容与来源</th></tr></thead><tbody>{ev_rows}</tbody></table>

    <div class="two-col">
      <section><h4>出口与贸易信息</h4><p>{esc(c.get('export_info','—'))}</p></section>
      <section><h4>风险提示</h4><ul class="risk-list">{''.join(f'<li>{esc(r)}</li>' for r in c.get('risks', [])) or '<li>—</li>'}</ul></section>
    </div>

    <h4>需向该企业核实的询证问题</h4>
    <ol class="q-list">{qs or '<li>—</li>'}</ol>

    <div class="actions">
      <button class="btn primary" onclick="verifySupplier('{esc(c['id'])}')">核验该海外供应商 →</button>
      <button class="btn" onclick="genQuestions('{esc(c['id'])}')">生成询证问题清单</button>
      <button class="btn ghost" onclick="copyInquiry('{esc(c['id'])}')">复制询盘要点</button>
    </div>
  </div>
</article>''')


# ---------- relationship graph builder ----------
def build_graph(DATA, companies):
    """三行布局：集团层 / 工厂层 / 其他层。完全由 groups 与 companies 生成。"""
    groups = DATA['groups']
    plants = [c for c in companies if c['entity_type'] in MANUF_TYPES]
    others = [c for c in companies if c['entity_type'] not in MANUF_TYPES]

    W = 1200
    def place(items, y, h, w_gap=14):
        n = max(len(items), 1)
        bw = min(230, int((W - 60 - w_gap * (n - 1)) / n))
        total = n * bw + (n - 1) * w_gap
        x0 = (W - total) / 2
        return [(x0 + i * (bw + w_gap), y, bw, h) for i in range(n)]

    g_boxes = place(groups[:6], 30, 54)
    p_boxes = place(plants[:8], 170, 64)
    o_boxes = place(others[:8], 320, 60)
    H = 460

    parts = [f'<svg viewBox="0 0 {W} {H}" class="graph" role="img" aria-label="集团与工厂关系图谱">',
             '<defs>',
             '<marker id="arw" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#94a3b8"/></marker>',
             '<marker id="arwd" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#f59e0b"/></marker>',
             '</defs>']

    gpos = {groups[i]['id']: g_boxes[i] for i in range(min(len(groups), len(g_boxes)))}
    ppos = {plants[i]['id']: p_boxes[i] for i in range(min(len(plants), len(p_boxes)))}

    edges = []
    for c in plants:
        gb = gpos.get(c.get('group'))
        pb = ppos.get(c['id'])
        if not gb or not pb:
            continue
        x1 = gb[0] + gb[2] / 2
        y1 = gb[1] + gb[3]
        x2 = pb[0] + pb[2] / 2
        y2 = pb[1]
        dashed = ' stroke-dasharray="5 4"' if c['grade'] == 'B' else ''
        edges.append(f'<path d="M{x1:.0f},{y1} C{x1:.0f},{(y1+y2)/2} {x2:.0f},{(y1+y2)/2} {x2:.0f},{y2}"{dashed}/>')

    # 销售主体连线：指向它服务的工厂（若 group 相同则指同集团工厂）
    sale_edges = []
    for i, c in enumerate(others):
        if i >= len(o_boxes):
            break
        ob = o_boxes[i]
        x1 = ob[0] + ob[2] / 2
        y1 = ob[1]
        target = next((p for p in plants if p.get('group') and p.get('group') == c.get('group')), None)
        if target and target['id'] in ppos:
            t = ppos[target['id']]
            x2, y2 = t[0] + t[2] / 2, t[1] + t[3]
            sale_edges.append(f'<path d="M{x1:.0f},{y1} C{x1:.0f},{(y1+y2)/2} {x2:.0f},{(y1+y2)/2} {x2:.0f},{y2}"/>')

    parts.append('<g stroke="#94a3b8" stroke-width="1.6" fill="none" marker-end="url(#arw)">' + ''.join(edges) + '</g>')
    if sale_edges:
        parts.append('<g stroke="#f59e0b" stroke-width="1.8" fill="none" stroke-dasharray="6 4" marker-end="url(#arwd)">' + ''.join(sale_edges) + '</g>')

    parts.append('<g class="nodes">')
    for i, g in enumerate(groups[:len(g_boxes)]):
        x, y, w, h = g_boxes[i]
        parts.append(f'<g class="gnode"><rect x="{x:.0f}" y="{y}" width="{w}" height="{h}" rx="10"/>'
                     f'<text x="{x+w/2:.0f}" y="{y+22}" class="n1">{html.escape(str(g.get("name",""))[:26])}</text>'
                     f'<text x="{x+w/2:.0f}" y="{y+40}" class="n2">{html.escape(str(g.get("type",""))[:34])}</text></g>')
    for i, c in enumerate(plants[:len(p_boxes)]):
        x, y, w, h = p_boxes[i]
        parts.append(f'<g class="mnode"><rect x="{x:.0f}" y="{y}" width="{w}" height="{h}" rx="10"/>'
                     f'<text x="{x+w/2:.0f}" y="{y+22}" class="n1">{html.escape(c["legal_name"][:26])}</text>'
                     f'<text x="{x+w/2:.0f}" y="{y+40}" class="n2">{html.escape(str(c.get("site",""))[:32])}</text>'
                     f'<text x="{x+w/2:.0f}" y="{y+56}" class="n3">{html.escape(str(cap_main(c))[:30])}</text></g>')
    for i, c in enumerate(others[:len(o_boxes)]):
        x, y, w, h = o_boxes[i]
        parts.append(f'<g class="tnode"><rect x="{x:.0f}" y="{y}" width="{w}" height="{h}" rx="10"/>'
                     f'<text x="{x+w/2:.0f}" y="{y+22}" class="n1">{html.escape(c["legal_name"][:26])}</text>'
                     f'<text x="{x+w/2:.0f}" y="{y+40}" class="n2">{html.escape(c["entity_type_label"][:32])}</text></g>')
    parts.append('</g>')
    parts.append(f'<g><text x="30" y="{H-20}" class="lg">实线=控股/合资；虚线=待核验或营销授权；绿色=含 A/B 级制造主体；橙色=销售/贸易/非目标品</text></g>')
    parts.append('</svg>')
    return '\n'.join(parts)


# ---------- relationship graph (SVG, generated from JSON) ----------
GRAPH = build_graph(DATA, companies)

legend_html = ''.join(
    f'<div class="lg-item"><span class="lg-g g{l["grade"]}">{l["grade"]}</span><div><b>{l["label"]}</b><p>{l.get("def","")}</p></div></div>'
    for l in meta['evidence_grade_legend'])

summary = {
    'A': sum(1 for c in companies if c['grade'] == 'A'),
    'B': sum(1 for c in companies if c['grade'] == 'B'),
    'C': sum(1 for c in companies if c['grade'] == 'C'),
    'D': sum(1 for c in companies if c['grade'] == 'D'),
}
total = len(companies)

CARD_META = {c['id']: c for c in companies}
JSON_FOR_JS = json.dumps({
    'companies': [{'id': c['id'], 'name': c['legal_name'], 'grade': c['grade'],
                   'type': c['entity_type_label'], 'site': c.get('site', ''),
                   'cap': cap_main(c),
                   'qs': [Q[q]['q'] for q in c.get('open_questions', []) if q in Q]}
                  for c in companies],
    'Q': {k: {'q': v['q'], 'company': v['company']} for k, v in Q.items()},
}, ensure_ascii=False)

HTML = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{esc(CTRY)} {esc(PROD)} 实际生产企业核验调查报告</title>
<style>
:root{{
  --a:#0f766e; --a2:#0d9488; --ink:#0f172a; --muted:#64748b; --line:#e2e8f0;
  --bg:#f6f8fb; --card:#ffffff; --ok:#059669; --warn:#d97706; --bad:#dc2626; --info:#2563eb;
}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
  background:var(--bg);color:var(--ink);line-height:1.62;font-size:14.5px}}
a{{color:var(--a2);text-decoration:none}} a:hover{{text-decoration:underline}}
.wrap{{max-width:1280px;margin:0 auto;padding:0 22px 80px}}

/* hero */
.hero{{background:linear-gradient(135deg,#042f2e 0%,#0f766e 55%,#0d9488 100%);color:#fff;padding:42px 0 34px;margin-bottom:22px;
  box-shadow:0 10px 30px rgba(4,47,46,.18)}}
.hero .wrap{{padding-bottom:0}}
.eyebrow{{letter-spacing:.22em;font-size:11.5px;opacity:.85;font-weight:600;text-transform:uppercase}}
.hero h1{{font-size:30px;margin:10px 0 8px;font-weight:700;letter-spacing:.01em}}
.hero .lede{{opacity:.92;max-width:900px;font-size:14.5px}}
.hero-stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:24px}}
.stat{{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:12px;padding:12px 14px;backdrop-filter:blur(6px)}}
.stat b{{display:block;font-size:24px;line-height:1.2}}
.stat span{{font-size:11.5px;opacity:.88}}
.meta-row{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;font-size:12px}}
.chip{{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);padding:3px 10px;border-radius:99px}}

/* section */
section.panel{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 24px;margin:18px 0;
  box-shadow:0 1px 2px rgba(15,23,42,.04)}}
h2{{font-size:19px;margin:0 0 4px;letter-spacing:.01em}}
h2 .num{{color:var(--a2);font-weight:800;margin-right:8px}}
.sec-sub{{color:var(--muted);font-size:13px;margin:0 0 16px}}
h3{{font-size:16px;margin:22px 0 8px}}
h4{{font-size:13.5px;margin:16px 0 8px;color:#334155;letter-spacing:.02em;border-left:3px solid var(--a2);padding-left:8px}}

/* product card */
.prod-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}}
.prod-grid div{{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.prod-grid .k{{display:block;color:var(--muted);font-size:11.5px;margin-bottom:2px}}
.prod-grid .v{{font-weight:600;font-size:13.5px}}

/* legend */
.legend{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}
.lg-item{{display:flex;gap:11px;background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:12px}}
.lg-g{{flex:0 0 34px;height:34px;border-radius:9px;display:grid;place-items:center;color:#fff;font-weight:800;font-size:15px}}
.lg-g.gA{{background:var(--ok)}} .lg-g.gB{{background:var(--warn)}} .lg-g.gC{{background:#64748b}} .lg-g.gD{{background:var(--bad)}}
.lg-item p{{margin:3px 0 0;font-size:12px;color:var(--muted);line-height:1.5}}

/* funnel */
.funnel{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:6px}}
.fstep{{border:1px solid var(--line);border-radius:12px;padding:14px;background:#fff;position:relative}}
.fstep .t{{font-size:12px;color:var(--muted)}}
.fstep .n{{font-size:26px;font-weight:800;color:var(--a)}}
.fstep .d{{font-size:12px;color:#475569}}
.fstep::after{{content:"";position:absolute;right:-9px;top:50%;width:8px;height:8px;border-top:2px solid var(--line);border-right:2px solid var(--line);transform:translateY(-50%) rotate(45deg)}}

/* graph */
.graph{{width:100%;height:auto;background:linear-gradient(180deg,#fbfdff,#f1f7f6);border:1px solid var(--line);border-radius:14px}}
.gnode rect{{fill:#fff;stroke:#cbd5e1}}
.gnode.alt rect{{fill:#fef6e7;stroke:#f0c674}}
.mnode rect{{fill:#ecfdf5;stroke:#34d399}}
.tnode rect{{fill:#fef2f2;stroke:#fca5a5}}
.graph text{{text-anchor:middle;font-family:inherit}}
.graph .n1{{font-size:13.5px;font-weight:700;fill:#0f172a}}
.graph .n2{{font-size:10.5px;fill:#64748b}}
.graph .n3{{font-size:10.5px;fill:#0f766e;font-weight:600}}
.graph .lg{{text-anchor:start;font-size:11px;fill:#64748b}}

/* toolbar */
.toolbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:#fff;border:1px solid var(--line);
  border-radius:14px;padding:12px 14px;position:sticky;top:0;z-index:30;box-shadow:0 2px 10px rgba(15,23,42,.06);margin-bottom:14px}}
.toolbar label{{font-size:12px;color:var(--muted);font-weight:600}}
select,input[type=search]{{font:inherit;font-size:13px;padding:7px 9px;border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--ink)}}
input[type=search]{{min-width:210px}}
.seg{{display:flex;border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.seg button{{border:0;background:#fff;padding:8px 14px;font:inherit;font-size:13px;cursor:pointer;color:#475569}}
.seg button.on{{background:var(--a);color:#fff;font-weight:600}}
.count{{margin-left:auto;font-size:12px;color:var(--muted)}}

/* columns */
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:1000px){{.cols{{grid-template-columns:1fr}}}}
.col-head{{display:flex;align-items:center;gap:8px;margin:6px 0 10px;padding:8px 12px;border-radius:10px;font-weight:700;font-size:14px}}
.col-head.manu{{background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0}}
.col-head.trade{{background:#fff7ed;color:#9a3412;border:1px solid #fed7aa}}
.col-head .c{{margin-left:auto;font-weight:600;font-size:12px;opacity:.8}}
.col-explain{{font-size:11.8px;color:#7c2d12;background:#fffbeb;border:1px dashed #fcd34d;border-radius:10px;padding:9px 11px;margin-bottom:10px;line-height:1.55}}

/* company card */
.co-card{{background:#fff;border:1px solid var(--line);border-radius:14px;margin-bottom:14px;overflow:hidden;
  border-left:5px solid #64748b;transition:box-shadow .18s}}
.co-card.gA{{border-left-color:var(--ok)}} .co-card.gB{{border-left-color:var(--warn)}}
.co-card.gC{{border-left-color:#64748b}} .co-card.gD{{border-left-color:var(--bad)}}
.co-card:hover{{box-shadow:0 6px 18px rgba(15,23,42,.08)}}
.co-head{{display:flex;align-items:center;gap:12px;padding:13px 15px;cursor:pointer}}
.rank{{font-weight:800;color:#94a3b8;font-size:13px;width:28px}}
.co-title h3{{margin:0;font-size:15px}} .co-title .sub{{margin:1px 0 0;font-size:11.5px;color:var(--muted)}}
.badges{{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}}
.badge{{font-size:11px;padding:3px 9px;border-radius:99px;background:#f1f5f9;color:#334155;border:1px solid var(--line);white-space:nowrap}}
.grade-badge{{background:#0f766e;color:#fff;border-color:#0f766e;font-weight:700}}
.gA .grade-badge{{background:var(--ok);border-color:var(--ok)}} .gB .grade-badge{{background:var(--warn);border-color:var(--warn)}}
.gC .grade-badge{{background:#64748b;border-color:#64748b}} .gD .grade-badge{{background:var(--bad);border-color:var(--bad)}}
.chev{{color:#94a3b8;transition:transform .2s}}
.co-card.open .chev{{transform:rotate(180deg)}}
.co-body{{display:none;padding:0 15px 16px;border-top:1px dashed var(--line)}}
.co-card.open .co-body{{display:block}}

.kv-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:12px 0}}
.kv-grid>div{{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:8px 10px}}
.kv-grid .k{{display:block;font-size:11px;color:var(--muted)}}
.kv-grid .v{{font-size:12.5px;font-weight:500}}
.verdict{{border-radius:10px;padding:10px 12px;font-size:12.5px;line-height:1.6}}
.verdict.ok{{background:#ecfdf5;border:1px solid #a7f3d0}}
.verdict.warn{{background:#fffbeb;border:1px solid #fde68a}}
.verdict.bad{{background:#fef2f2;border:1px solid #fecaca}}

.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:820px){{.two-col{{grid-template-columns:1fr}}}}
table.mini{{width:100%;border-collapse:collapse;font-size:12px}}
table.mini th,table.mini td{{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}}
table.mini th{{background:#f1f5f9;font-weight:600;color:#334155}}
table.ev-table{{width:100%;border-collapse:collapse;font-size:11.8px;margin-top:6px}}
table.ev-table th,table.ev-table td{{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
table.ev-table th{{background:#f1f5f9;font-weight:600}}
.ev-id{{font-family:ui-monospace,Consolas,monospace;color:var(--a);font-weight:700;white-space:nowrap}}
.src-line{{font-size:11px;color:var(--muted);margin-top:3px}}
.conf{{font-size:10.5px;padding:1px 7px;border-radius:99px;white-space:nowrap}}
.conf-hi{{background:#dcfce7;color:#166534}} .conf-mid{{background:#fef3c7;color:#92400e}}
.cap-note{{font-size:12px;color:#475569;margin:4px 0}}
.warn-note{{font-size:12px;color:#9a3412;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:7px 9px}}
.mono{{font-family:ui-monospace,Consolas,monospace;font-size:11.5px}}
.risk-list,.q-list{{margin:6px 0 0 18px;padding:0;font-size:12.3px}}
.risk-list li,.q-list li{{margin-bottom:5px}}
.actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;padding-top:12px;border-top:1px dashed var(--line)}}
.btn{{font:inherit;font-size:12.5px;padding:8px 14px;border-radius:9px;border:1px solid var(--line);background:#fff;cursor:pointer;color:#334155;font-weight:600}}
.btn:hover{{border-color:var(--a2);color:var(--a)}}
.btn.primary{{background:var(--a);border-color:var(--a);color:#fff}}
.btn.primary:hover{{background:#115e59;color:#fff}}
.btn.ghost{{background:#f8fafc}}
.empty{{padding:30px;text-align:center;color:var(--muted);font-size:13px;border:1px dashed var(--line);border-radius:12px}}

/* sources & questions */
table.src{{width:100%;border-collapse:collapse;font-size:12px}}
table.src th,table.src td{{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}}
table.src th{{background:#f1f5f9;position:sticky;top:0}}
.tbl-wrap{{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:12px}}

.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:900px){{.grid2{{grid-template-columns:1fr}}}}
.note{{background:#f0fdfa;border:1px solid #99f6e4;border-radius:12px;padding:12px 14px;font-size:12.5px}}
.danger{{background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:12px 14px;font-size:12.5px}}

/* modal */
.modal{{position:fixed;inset:0;background:rgba(15,23,42,.55);display:none;place-items:center;z-index:100;padding:20px}}
.modal.on{{display:grid}}
.modal-box{{background:#fff;border-radius:16px;max-width:840px;width:100%;max-height:86vh;overflow:auto;padding:22px 24px;box-shadow:0 24px 60px rgba(2,6,23,.4)}}
.modal-box h3{{margin-top:0}}
.modal-close{{float:right;border:0;background:#f1f5f9;border-radius:8px;width:32px;height:32px;cursor:pointer;font-size:16px}}
.modal-box textarea{{width:100%;min-height:240px;font-family:ui-monospace,Consolas,monospace;font-size:12px;padding:12px;border:1px solid var(--line);border-radius:10px;line-height:1.6}}
.toast{{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);background:#0f172a;color:#fff;padding:10px 18px;border-radius:10px;font-size:13px;opacity:0;transition:.25s;z-index:200;pointer-events:none}}
.toast.on{{opacity:1;transform:translateX(-50%) translateY(0)}}
footer{{text-align:center;color:var(--muted);font-size:12px;padding:26px 0 10px}}
.hidden{{display:none !important}}
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <div class="eyebrow">Overseas Manufacturer Survey · Evidence-Graded</div>
    <h1>{esc(CTRY)} {esc(PROD)} 实际生产企业核验调查报告</h1>
    <p class="lede">从「国家 + 产品」出发，逐家核验企业是否<b>真正拥有目标产品生产装置</b>，并把集团主体、制造主体、销售主体与贸易中间商分离。公开设计产能 <b>不等于</b> 当前可售供货能力；证据不足的字段一律保留待核验。</p>
    <div class="hero-stats">
      <div class="stat"><b>{total}</b><span>纳入评估企业/主体</span></div>
      <div class="stat"><b>{summary['A']}</b><span>有直接公开制造证据</span></div>
      <div class="stat"><b>{summary['B']}</b><span>关联待核验</span></div>
      <div class="stat"><b>{summary['C']}</b><span>仅行业相关（非目标品）</span></div>
      <div class="stat"><b>{len(DATA['questions'])}</b><span>后续核验问题</span></div>
    </div>
    <div class="meta-row">
      <span class="chip">报告编号 {esc(meta['report_id'])}</span>
      <span class="chip">产品：{esc(meta['product'].get('name_cn',''))} · CAS {esc(meta['product']['cas'])} · HS {esc(meta['product']['hs_cn'])}</span>
      <span class="chip">来源国：{esc(CTRY)} → {esc(meta.get('buyer_context',{}).get('destination','中国'))}</span>
      <span class="chip">调查日期：{esc(meta['research_date'])}</span>
      <span class="chip">引用来源 {len(DATA['sources'])} 项</span>
    </div>
  </div>
</header>

<div class="wrap">

<section class="panel">
  <h2><span class="num">01</span>目标产品与采购口径</h2>
  <p class="sec-sub">先锁死“买什么”，再判断“谁能造”。规格口径不清时，任何厂商名单都无法转化为可执行的询盘。</p>
  <div class="prod-grid">
    <div><span class="k">产品（中/英）</span><span class="v">{esc(meta['product']['name_cn'])} / {esc(meta['product']['name_en'])}</span></div>
    <div><span class="k">CAS / HS</span><span class="v">{esc(meta['product']['cas'])} / {esc(meta['product']['hs_cn'])}</span></div>
    <div><span class="k">典型规格</span><span class="v">{esc(meta['product'].get('spec_summary','—'))}</span></div>
    <div><span class="k">工艺路线</span><span class="v">{esc(meta['product'].get('process_route','—'))}</span></div>
    <div><span class="k">包装形式</span><span class="v">{esc(meta['product'].get('packaging','—'))}</span></div>
    <div><span class="k">采购批量</span><span class="v">{esc(meta['buyer_context']['quantity'])}</span></div>
    <div><span class="k">认证要求</span><span class="v">{esc(meta['buyer_context']['certifications_needed'])}</span></div>
    <div><span class="k">是否仅接受实际厂家</span><span class="v">{esc(meta['buyer_context']['only_actual_manufacturers'])}</span></div>
  </div>
  <h4>本次调查的关键判断规则</h4>
  <div class="note">
    <b>只有满足以下任一条，才计入“有直接公开制造证据（A）”</b>：① 企业官网以自身名义列出该产品的<u>装置产能表</u>；② 企业官网产品页声明“本企业生产 X KTA”；③ 官方新闻稿/交易所文件披露该<u>具体工厂</u>的投产或商业运营；④ 独立 EPC 承包方项目页载明客户为该企业且产能为 700–1,000 t/d 级 EO/EG；⑤ 装置级公开数据（数据商/行业协会）记载该企业单线产能与运行事件。<br/>
    <b>以下一律不构成制造证据</b>：第三方供应商名录挂名、经营范围含“石化产品”、B2B 平台“Trading Company”标签、集团口径提及、产品关键词命中、贸易救济名单被列名（名单口径常把集团关联方混杂）。
  </div>
</section>

<section class="panel">
  <h2><span class="num">02</span>制造证据等级定义</h2>
  <p class="sec-sub">证据等级回答的是“能不能确认它自己有装置”，不是“这家公司大不大”。</p>
  <div class="legend">{legend_html}</div>
</section>

<section class="panel">
  <h2><span class="num">03</span>筛选漏斗：从“名字很多”到“能下询盘”</h2>
  <p class="sec-sub">本报告的可信度来自减法，而不是加法。</p>
  <div class="funnel">
    <div class="fstep"><div class="t">Step 1 · 初始候选</div><div class="n">{esc(meta.get('funnel',{}).get('step1','—'))}</div><div class="d">{esc(meta.get('funnel_note',{}).get('step1','按工艺链条、产业带、集团族谱、EPC 名录、官方披露建立的候选池'))}</div></div>
    <div class="fstep"><div class="t">Step 2 · 取得产品级线索</div><div class="n">{esc(meta.get('funnel',{}).get('step2', total))}</div><div class="d">{esc(meta.get('funnel_note',{}).get('step2','出现目标产品相关公开记载或明确为一体化企业'))}</div></div>
    <div class="fstep"><div class="t">Step 3 · 装置/产能级证据</div><div class="n">{summary['A']}</div><div class="d">官网产能表、EPC 项目页、官方投产公告、交易所文件、装置级运行数据</div></div>
    <div class="fstep"><div class="t">Step 4 · 可询盘主体</div><div class="n">6</div><div class="d">A 级中排除销售主体后，可直接发询盘的工厂（经 SABIC/自营渠道）</div></div>
  </div>
</section>

<section class="panel">
  <h2><span class="num">04</span>股权 · 工厂 · 销售关系图谱</h2>
  <p class="sec-sub">关键坑：集团写“我们是全球最大 EG 生产商”≠ 集团法人有工厂；营销方（SPDC）不拥有装置，但可能是対华的实际签约窗口。</p>
  {GRAPH}
</section>

<section class="panel" id="companyPanel">
  <h2><span class="num">05</span>企业清单：生产商 / 贸易商分栏</h2>
  <p class="sec-sub">按制造证据、工厂所在地、产品规格、公开产能与企业类型筛选；点开企业卡片可查看工厂、产品目录、官网、公开认证与证据来源。</p>

  <div class="toolbar">
    <div class="seg" id="kindSeg">
      <button class="on" data-kind="all">全部</button>
      <button data-kind="manu">生产商</button>
      <button data-kind="trade">贸易/销售主体</button>
    </div>
    <label>证据等级</label>
    <select id="fGrade"><option value="">全部</option><option value="A">A · 直接制造证据</option><option value="B">B · 关联待核验</option><option value="C">C · 仅行业相关</option><option value="D">D · 贸易/身份不明</option></select>
    <label>工厂所在地</label>
    <select id="fSite"><option value="">全部</option>{''.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in facets['site'])}<option value="none">未获取</option></select>
    <label>企业类型</label>
    <select id="fType"><option value="">全部</option><option value="MANUFACTURER">制造企业</option><option value="JV_MANUFACTURER">合资制造企业</option><option value="AFFILIATE_SALES">附属销售主体</option><option value="TRADER">一般贸易商</option><option value="AGENT">代理/经销</option><option value="UNKNOWN">身份不明</option></select>
    <label>公开产能</label>
    <select id="fCap"><option value="">全部</option><option value="ge500">≥ 500 kt/a</option><option value="none">未获证/0</option></select>
    <input type="search" id="fText" placeholder="搜索企业名 / 产品 / 关键词…"/>
    <span class="count" id="countLbl"></span>
  </div>

  <div class="cols">
    <div>
      <div class="col-head manu">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 21h18"/><path d="M5 21V9l5 3V9l5 3V7l4 2v12"/><path d="M9 21v-4h3v4"/></svg>
        生产商 · 拥有/运营目标产品装置的工厂主体<span class="c" id="cntManu"></span></div>
      <div id="listManu">{''.join(cards_html)}</div>
      <div class="empty hidden" id="emptyManu">当前筛选条件下无匹配的生产主体</div>
    </div>
    <div>
      <div class="col-head trade">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 2l4 4-4 4"/><path d="M3 6h18"/><path d="M7 22l-4-4 4-4"/><path d="M21 18H3"/></svg>
        销售主体 / 贸易中间商 / 非目标品（不作制造证据）<span class="c" id="cntTrade"></span></div>
      <div class="col-explain">此栏收录：① 集团销售或附属营销主体（如 SPDC，自身无装置但可能是对华签约窗口）；② 仅是“行业相关”的公司（生产其他 glycol 或石化品，易被关键词误判）；③ 贸易商与平台挂牌卖家。列出它们的目的，是<b>防止把销售主体当成工厂</b>。</div>
      <div id="listTrade"></div>
      <div class="empty hidden" id="emptyTrade">当前筛选条件下无匹配主体</div>
    </div>
  </div>
</section>

<section class="panel">
  <h2><span class="num">06</span>产品规格与产能口径对照（公开数据）</h2>
  <p class="sec-sub">公开设计产能 ≠ 当前实际供货能力。下表只记录“公开说了什么”，并列明口径冲突。</p>
  <div class="tbl-wrap">
    <table class="src">
      <thead><tr><th>企业</th><th>公开产能</th><th>口径明细与冲突</th><th>当前供货能力判断</th></tr></thead>
      <tbody>
        {''.join(f'''<tr><td><b>{esc(c['legal_name'])}</b></td><td>{esc(cap_main(c))} {esc(c['capacity'].get('unit',''))}</td><td>{esc(c['capacity'].get('detail','—'))}</td><td>{esc(c['capacity'].get('caveat','—'))}</td></tr>''' for c in companies)}
      </tbody>
    </table>
  </div>
</section>

<section class="panel">
  <h2><span class="num">07</span>市场背景（用于解释为何要找到工厂本身）</h2>
  <div class="grid2">
    {''.join(f'<div class="note"><b>{esc(m["claim"])}</b><div style="margin-top:6px;color:#64748b;font-size:12px">来源：<a href="{esc(S.get(m["source"],{}).get("url","#"))}" target="_blank" rel="noopener">{esc(m["source"])}</a> · 置信度 {esc(m["conf"])}</div></div>' for m in DATA['market_context'])}
  </div>
  <h4>这对采购意味着什么</h4>
  <p>{esc(meta.get('market_interpretation','装置往往由少数几家集团附属工厂持有，而对外签约常经集团营销主体。因此“找到工厂”用于判断真实供给与议价基础；“找准签约主体”用于把货真正开出来，二者必须分开做。'))}</p>
</section>

<section class="panel">
  <h2><span class="num">08</span>后续核验问题清单</h2>
  <p class="sec-sub">证据不足的企业与字段，统一转成可发出的问询，避免用“看起来像生产商”替代核实。</p>
  <div class="tbl-wrap">
    <table class="src">
      <thead><tr><th>编号</th><th>相关企业</th><th>需核实的问题</th></tr></thead>
      <tbody>{''.join(f'<tr><td class="ev-id">{esc(q["id"])}</td><td>{esc(next((c["legal_name"] for c in companies if c["id"]==q["company"]), q["company"]))}</td><td>{esc(q["q"])}</td></tr>' for q in DATA['questions'])}</tbody>
    </table>
  </div>
  <div class="actions" style="border:0">
    <button class="btn primary" onclick="genQuestions('ALL')">生成全部询证问题清单</button>
    <button class="btn" onclick="window.print()">打印 / 导出 PDF</button>
  </div>
</section>

<section class="panel">
  <h2><span class="num">09</span>证据来源清单</h2>
  <p class="sec-sub">每条证据都可回溯到下列公开来源；标注“待下载/直连失败”者不作为最终结论依据，仅作线索。</p>
  <div class="tbl-wrap">
    <table class="src">
      <thead><tr><th>ID</th><th>来源与标题</th><th>日期</th><th>收录状态</th></tr></thead>
      <tbody>{''.join(f'<tr><td class="ev-id">{esc(s["id"])}</td><td><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["title"])}</a></td><td>{esc(s["date"])}</td><td>{esc(s["status"])}</td></tr>' for s in DATA['sources'])}</tbody>
    </table>
  </div>
  <div class="danger" style="margin-top:14px"><b>合规与免责：</b>{esc(meta['disclaimer'])}</div>
</section>

<footer>本报告由「找海外候选生产商」方法生成 · {esc(meta['report_id'])} · 生成工具：通用寻源调查 Skill</footer>
</div>

<div class="modal" id="modal"><div class="modal-box">
  <button class="modal-close" onclick="closeModal()">✕</button>
  <h3 id="mTitle">标题</h3>
  <div id="mBody"></div>
</div></div>
<div class="toast" id="toast"></div>

<script>
const DATA = {JSON_FOR_JS};
const PRODJS = {json.dumps(meta['product'].get('name_cn','目标产品'), ensure_ascii=False)};
const PRODENJS = {json.dumps(meta['product'].get('name_en','the product'), ensure_ascii=False)};
const CASJS = {json.dumps(meta['product'].get('cas',''), ensure_ascii=False)};
const HSJS = {json.dumps(meta['product'].get('hs_cn',''), ensure_ascii=False)};
const DESPORTJS = {json.dumps(meta.get('buyer_context',{}).get('destination_port','China') or 'China', ensure_ascii=False)};

function toggleCard(h){{ h.parentElement.classList.toggle('open'); }}

function filterCards(){{
  const kind = document.querySelector('#kindSeg button.on').dataset.kind;
  const grade = document.getElementById('fGrade').value;
  const site = document.getElementById('fSite').value;
  const type = document.getElementById('fType').value;
  const cap = document.getElementById('fCap').value;
  const text = document.getElementById('fText').value.trim().toLowerCase();
  const cards = [...document.querySelectorAll('.co-card')];
  const fragM = document.createDocumentFragment(), fragT = document.createDocumentFragment();
  let nm=0, nt=0;
  cards.forEach(card=>{{
    let ok = true;
    if (grade && card.dataset.grade !== grade) ok = false;
    if (site) {{ const s = card.dataset.site || 'none'; if (site==='none' ? !!card.dataset.site : s !== site) ok=false; }}
    if (type && card.dataset.type !== type) ok = false;
    if (cap) {{
      const cid = card.id;
      const co = DATA.companies.find(x=>x.id===cid);
      const num = parseFloat(String(co? co.cap : '').replace(/[^0-9.]/g,'')) || 0;
      const mtpa = num > 20 ? num/1000 : num; // rough normalize
      if (cap==='ge500' && !(mtpa>=0.5)) ok=false;
      if (cap==='none' && mtpa>0) ok=false;
    }}
    if (text && !card.textContent.toLowerCase().includes(text)) ok = false;
    if (kind!=='all' && card.dataset.kind !== kind) ok = false;
    if (!ok) {{ return; }}
    if (card.dataset.kind==='manu') {{ nm++; fragM.appendChild(card); }} else {{ nt++; fragT.appendChild(card); }}
  }});
  document.getElementById('listManu').appendChild(fragM);
  document.getElementById('listTrade').appendChild(fragT);
  document.getElementById('cntManu').textContent = nm + ' 家';
  document.getElementById('cntTrade').textContent = nt + ' 家';
  document.getElementById('emptyManu').classList.toggle('hidden', nm>0);
  document.getElementById('emptyTrade').classList.toggle('hidden', nt>0);
  document.getElementById('countLbl').textContent = `共匹配 ${{nm+nt}} / {total} 家`;
}}
document.querySelectorAll('#kindSeg button').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('#kindSeg button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); filterCards();
}});
['fGrade','fSite','fType','fCap','fText'].forEach(id=>{{
  const el=document.getElementById(id);
  el.addEventListener(el.tagName==='INPUT'?'input':'change', filterCards);
}});
filterCards();

function toast(msg){{ const t=document.getElementById('toast'); t.textContent=msg; t.classList.add('on'); setTimeout(()=>t.classList.remove('on'),1800); }}
function closeModal(){{ document.getElementById('modal').classList.remove('on'); }}

function verifySupplier(id){{
  const co = DATA.companies.find(c=>c.id===id);
  document.getElementById('mTitle').textContent = '核验该海外供应商：' + co.name;
  document.getElementById('mBody').innerHTML = `
    <p class="cap-note">下一步应交给「核验海外供应商」流程，逐项取证。当前状态：证据等级 <b>${{co.grade}}</b>，主体类型 <b>${{co.type}}</b>。</p>
    <h4>建议核验顺序</h4>
    <ol class="q-list">
      <li>主体一致性：签约主体名称、注册号（Saudi CR No.）、地址与工厂地址是否一致。</li>
      <li>制造一致性：索取产品规格书 + COA + 工厂实拍/装置铭牌 + 出口发票（Consignor 应为该工厂或其集团销售主体）。</li>
      <li>资质文件：工厂级 ISO 9001/14001/45001 证书编号与有效期；SDS（GHS 中文版）。</li>
      <li>供货能力：近 12 个月对华发运记录/提单样本、最小起订量、FOB/CFR 贸易术语。</li>
      <li>合规：反倾销/贸易救济现状、装运前检验、危化品运输文件（若按 UN3082 或作为非危品需确认）。</li>
    </ol>
    <h4>该企业待核实问题</h4>
    <ol class="q-list">${{(co.qs||[]).map(q=>'<li>'+q+'</li>').join('') || '<li>—</li>'}}</ol>
    <p class="warn-note">未取得书面回复前，不得将其列为“已核验厂家”。</p>`;
  document.getElementById('modal').classList.add('on');
}}

function buildQuestionsHTML(ids){{
  let rows = [];
  ids.forEach(id=>{{ const co = DATA.companies.find(c=>c.id===id); if(!co) return;
    (co.qs||[]).forEach((q,i)=>rows.push(`<li><b>${{co.name}}</b> — ${{q}}</li>`)); }});
  return rows.join('');
}}
function genQuestions(id){{
  let title, body, ids;
  if (id==='ALL') {{
    title='全部询证问题清单'; ids = DATA.companies.map(c=>c.id);
    const lines = [];
    lines.push('【通用前置问题】'+DATA.Q['QS-00'].q);
    DATA.companies.forEach(c=>{{ (c.qs||[]).forEach(q=>lines.push('· '+c.name+'：'+q)); }});
    body = `<textarea id="qText" readonly>${{lines.join('\\n')}}</textarea>
      <div class="actions"><button class="btn primary" onclick="copyText()">复制全部</button><button class="btn" onclick="downloadTxt()">下载 .txt</button></div>`;
    window.__QALL = lines.join('\\n');
  }} else {{
    const co = DATA.companies.find(c=>c.id===id);
    title = '询证问题清单：' + co.name;
    const lines = ['致：'+co.name, '主题：'.concat(PRODJS,' 供应商资质与制造能力核实（请逐项书面回复）'),''] ;
    (co.qs||[]).forEach((q,i)=>lines.push((i+1)+'. '+q));
    lines.push('','请随附：产品规格书、近12个月COA样本、工厂级ISO证书编号、对华出口提单样本（可脱敏）。');
    body = `<textarea id="qText" readonly>${{lines.join('\\n')}}</textarea>
      <div class="actions"><button class="btn primary" onclick="copyText()">复制</button><button class="btn" onclick="downloadTxt()">下载 .txt</button></div>`;
  }}
  document.getElementById('mTitle').textContent = title;
  document.getElementById('mBody').innerHTML = body;
  document.getElementById('modal').classList.add('on');
}}
function copyText(){{
  const ta=document.getElementById('qText'); ta.select();
  navigator.clipboard.writeText(ta.value).then(()=>toast('已复制到剪贴板'),()=>{{document.execCommand('copy');toast('已复制')}});
}}
function downloadTxt(){{
  const v=document.getElementById('qText').value;
  const blob=new Blob([v],{{type:'text/plain;charset=utf-8'}});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=PRODJS+'询证问题清单.txt'; a.click();
  toast('已下载');
}}
function copyInquiry(id){{
  const co = DATA.companies.find(c=>c.id===id);
  const txt = `Dear Sir/Madam,\\n\\nWe are a Chinese buyer looking to source ${{PRODENJS}} (CAS ${{CASJS}}, HS ${{HSJS}}).\\n\\nSupplier entity: ${{co.name}}\\nPlant location: ${{co.site || 'to be confirmed'}}\\nPublicly stated capacity: ${{co.cap || 'to be confirmed'}}\\n\\nPlease confirm:\\n1) Whether the above entity owns/operates the production plant for this product (and the plant name / permit reference);\\n2) Current available volume and loading port;\\n3) Typical specification (key quality parameters) and last 12 months COA samples;\\n4) Contracting entity for export to China (manufacturer or group sales company);\\n5) Quotation basis (FOB / CFR ${{DESPORTJS}}, etc.).\\n\\nThank you.`;
  navigator.clipboard.writeText(txt).then(()=>toast('英文询盘要点已复制'),()=>toast('复制失败，请手动复制'));
}}
document.getElementById('modal').addEventListener('click',e=>{{ if(e.target.id==='modal') closeModal(); }});
document.addEventListener('keydown',e=>{{ if(e.key==='Escape') closeModal(); }});
</script>
</body>
</html>'''

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(HTML)
print('written', OUT, len(HTML))
