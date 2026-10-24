#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_html.py — data.json → 单文件交互式 HTML（内联 CSS/JS，可离线打开）

用法：
    python scripts/render_html.py examples/h2o2-kr-30/data.json -o out/report.html
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import imrules as R  # noqa: E402

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


# ---------------------------------------------------------------------------
# 基础组件
# ---------------------------------------------------------------------------
def badge(text, cls="gray", lg=False):
    return f'<span class="badge {cls}{" lg" if lg else ""}">{E(text)}</span>'


VERDICT_CLS = {"applies": "bad", "not_applies": "ok", "conditional": "warn", "pending": "info"}
STATUS_CLS = {"ok": "ok", "partial": "warn", "missing": "bad", "pending": "info", "expired": "bad", "na": "gray"}
RESULT_CLS = {"pass": "ok", "fail": "bad", "warn": "warn", "na": "gray"}
RESULT_SYM = {"pass": "✓", "fail": "✕", "warn": "!", "na": "–"}
CONF_CLS = {"high": "ok", "medium": "warn", "low": "bad"}
REQ_CLS = {"必须": "solid", "视情形": "info", "建议": "gray"}


def src_tags(ids):
    out = []
    for sid in [x for x in str(ids or "").replace("，", ",").replace(" ", ",").split(",") if x]:
        out.append(f'<span class="tag src" data-src="{E(sid)}">{E(sid)}</span>')
    return " ".join(out)


def dl(pairs, cls=""):
    rows = []
    for k, v in pairs:
        if v is None or v == "":
            continue
        rows.append(f"<dt>{k}</dt><dd>{v}</dd>")
    return f'<dl class="dl {cls}">' + "".join(rows) + "</dl>"


def icon(name):
    paths = {
        "doc": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
        "check": '<path d="M20 6 9 17l-5-5"/>',
        "warn": '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
        "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
        "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
        "print": '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v8H6z"/>',
        "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
        "building": '<path d="M3 21h18M5 21V7l7-4 7 4v14"/><path d="M9 9h1M9 13h1M14 9h1M14 13h1"/>',
        "truck": '<path d="M1 3h15v13H1zM16 8h4l3 3v5h-7z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
        "clipboard": '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>',
        "flask": '<path d="M9 3h6M10 3v6L4 20a1 1 0 0 0 .9 1.5h14.2A1 1 0 0 0 20 20l-6-11V3"/>',
        "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
        "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/>',
        "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20"/>',
        "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
        "scale": '<path d="M12 3v18M5 7h14"/><path d="m5 7-3 7h6zM19 7l-3 7h6z"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    }
    return f'<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">{paths.get(name, "")}</svg>'


# ---------------------------------------------------------------------------
# 各节渲染
# ---------------------------------------------------------------------------
def gate_text(d, code):
    """闸门说明文字随状态变化，不写死在数据里，避免与实际判定脱节。"""
    hard = [x for x in d["documents"] if x["required"] == "必须"
            and R.norm_status(x["status"]) in ("missing", "expired")]
    partial = [x for x in d["documents"] if x["required"] == "必须"
               and R.norm_status(x["status"]) == "partial"]
    if code == "GATE-1":
        pid = d["product_identity"]
        if pid["identity_verdict"] != "confirmed" and pid.get("unconfirmed"):
            return f"产品身份为『部分确认』，尚缺 {len(pid['unconfirmed'])} 项要素；这些要素直接决定危化品与易制爆是否适用。"
        return "产品身份要素齐备，可进入监管判定。"
    if code == "GATE-2":
        return f"归类置信度高（{d['hs_verdict']['recommended']}），有章注与品目条文支撑；仍需报关行复核后申报。"
    if code == "GATE-3":
        pend = [r for r in d["regulation_checklist"] if r["verdict"] in ("pending", "conditional")]
        return f"{len(pend)} 项监管事项为『待核验/视条件适用』，须取得书面结论（见第 10 节）。"
    if code == "GATE-4":
        g = d["danger_distinction"]["goods"]
        return f"运输分类明确：{g['un']} / {g['cls']} / PG {g['pg']}；仍需供应商提供 UN 包装证书后方可报关填报。"
    if code == "GATE-5":
        if hard:
            return f"必须件缺失 {len(hard)} 项（{'、'.join(x['id'] for x in hard[:6])}…），不补齐无法报关。"
        if partial:
            return f"必须件均已取得但需补正 {len(partial)} 项。"
        return "必须件齐备。"
    if code == "GATE-6":
        dis = [f for f in d["tax_rates"]["fta"] if f.get("status") in ("disputed", "pending", "claimed")]
        if dis:
            return f"{len(dis)} 项协定税率存在数据冲突，须以单一窗口实查结果为准后再锁定成本。"
        return "税率已核实。"
    return ""


def sec_hero(d, grade):
    inp = d["inputs"]
    pid = d["product_identity"]
    dd = d.get("danger_distinction", {})
    g_cls = {"A": "gA", "B": "gB", "C": "gC", "D": "gD"}.get(grade["grade"], "gB")
    ring = {"A": 96, "B": 72, "C": 46, "D": 24}.get(grade["grade"], 72)
    comp = R.doc_completeness(d["documents"])
    p0_total = sum(1 for g in d["gaps"] if g["priority"] == "P0")
    q_high = sum(1 for q in d["to_confirm"] if q["severity"] == "高")

    chips = [
        f'<span class="chip k">{icon("globe")} 来源国 <b>{E(inp["origin_country"])}</b></span>',
        f'<span class="chip">CAS <b>{E(inp["cas"])}</b></span>',
        f'<span class="chip">浓度 <b>{E(inp["concentration"])}</b></span>',
        f'<span class="chip dg">{icon("flame") if False else ""}危险货物 <b>{E(dd.get("goods", {}).get("un", "—"))}</b> · 5.1 / PG {E(dd.get("goods", {}).get("pg", ""))}</span>',
        f'<span class="chip hz">危险化学品 <b>目录第903项（视条件）</b></span>',
        f'<span class="chip k">HS <b>{E(d.get("hs_verdict", {}).get("recommended", "—"))}</b></span>',
        f'<span class="chip tax">最惠国 <b>{E(d["tax_rates"]["mfn"]["rate"])}</b> · 增值税 <b>{E(d["tax_rates"]["vat"]["rate"])}</b></span>',
        f'<span class="chip">{icon("truck")}<b>{E(inp["transport_mode"])}</b></span>',
        f'<span class="chip">{icon("box")}<b>{E(inp["package_type"])}</b></span>',
    ]

    return f"""
<section id="s0" class="hero-wrap">
<div class="hero">
  <div class="eyebrow"><span class="dot"></span>进口资料准备与合规核验底稿 · IMPORT DOCUMENTATION DOSSIER
    <span style="margin-left:auto;font-family:var(--mono);letter-spacing:0;color:var(--muted)">
      {E(d["meta"]["record_id"])} · 基准日 {E(d["as_of"])}</span></div>
  <h1>{E(inp["product_name_cn"])} <span style="font-size:.6em;color:var(--muted);font-weight:400">{E(inp["concentration"])}</span>
     <span class="arrow">/</span> <span class="flow">{E(inp["origin_country"])} → 中国</span></h1>
  <p class="sub">{E(pid["one_liner"])}</p>
  <div class="chips">{"".join(chips)}</div>

  <div class="grade-row">
    <div class="grade-badge {g_cls}" style="--ring:{ring}%">
      <span class="g">{E(grade["grade"])}</span><span class="gl">{E(grade["grade_text"][:4])}</span>
    </div>
    <div class="grade-text">
      <div class="gt">{E(grade["grade_text"])}</div>
      <div class="gd">{E(d["assessment"]["one_liner"])}</div>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi {'bad' if p0_total else 'ok'}"><div class="kv">{p0_total}<small>项</small></div><div class="kl">P0 阻断性缺口</div></div>
    <div class="kpi {'warn' if q_high else 'ok'}"><div class="kv">{q_high}<small>项</small></div><div class="kl">高优先级待确认</div></div>
    <div class="kpi {'ok' if comp['pct'] >= 90 else 'warn' if comp['pct'] >= 60 else 'bad'}"><div class="kv">{comp['pct']}<small>%</small></div><div class="kl">单证完备度</div></div>
    <div class="kpi ink"><div class="kv">{comp['n_required_ok']}<small>/{comp['n_required']}</small></div><div class="kl">必须件已齐备</div></div>
    <div class="kpi ind"><div class="kv">{len(d['regulation_checklist'])}<small>项</small></div><div class="kl">已核监管事项</div></div>
    <div class="kpi ink"><div class="kv">{len(d['sources'])}<small>条</small></div><div class="kl">可回溯证据</div></div>
  </div>
</div>
</section>
"""


def sec_gates(d, grade):
    rows = []
    cls = {"pass": "ok", "fail": "bad", "pending": "warn"}
    txt = {"pass": "通过", "fail": "未通过", "pending": "待确认"}
    for g in grade["gates"]:
        rows.append(f"""<tr>
<td class="m"><b>{E(g['code'])}</b><div class="sml">{E(g['name'])}</div></td>
<td>{E(g['rule'])}</td>
<td class="c">{badge(txt[g['status']], cls[g['status']])}</td>
<td class="sml">{E(gate_text(d, g['code']))}</td></tr>""")
    return f"""
<section id="s1">
<div class="sec-head"><span class="no">00</span><h2>放行闸门</h2>
  <div class="lead">六道闸门决定这批货能否进入报关准备。任一项「未通过」即不可放行；「待确认」需在 T-30 前闭环。</div></div>
<div class="tw"><table class="t">
<thead><tr><th style="width:110px">闸门</th><th style="width:34%">判定规则</th><th style="width:78px">状态</th><th>本单说明</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
</section>
"""


def sec_identity(d):
    inp = d["inputs"]
    pid = d["product_identity"]
    comp_rows = "".join(
        f"<tr><td>{E(c['name'])}</td><td class='sml'>{E(c.get('ename',''))}</td><td class='m'>{E(c.get('cas','—'))}</td>"
        f"<td class='r num'>{c['pct_min']:g}{('–' + format(c['pct_max'], 'g')) if c.get('pct_max') != c.get('pct_min') else ''}%</td>"
        f"<td class='sml'>{E(c.get('role',''))}</td></tr>"
        for c in inp.get("composition", [])
    )
    unconf = "".join(f"<li>{E(x)}</li>" for x in pid.get("unconfirmed", []))
    conf = "".join(f"<li>{E(x)}</li>" for x in pid.get("confirmed", []))
    risks = "".join(f"""<div class="gap p1" style="margin-bottom:6px">
        <div class="gh"><span class="gt">{E(r['item'])}</span></div>
        <div class="gb">
          <div class="q"><span class="k">为什么</span><span>{E(r['why'])}</span></div>
          <div class="q"><span class="k">怎么办</span><span>{E(r['action'])}</span></div>
        </div></div>""" for r in pid.get("risk_points", []))

    return f"""
<section id="s2">
<div class="sec-head"><span class="no">01</span><h2>产品与归类</h2>
  <div class="lead">先锁身份，再谈监管。名称、浓度、组成、形态、用途、包装、运输方式七项任一变化，都可能导致监管结论改变。</div></div>

<div class="grid2">
  <div class="card">
    <h3>{icon('flask')} 产品身份要素 {badge({'confirmed':'已确认','partial':'部分确认','pending':'待确认'}[pid['identity_verdict']], {'confirmed':'ok','partial':'warn','pending':'bad'}[pid['identity_verdict']])}</h3>
    {dl([
        ("中文品名", E(inp['product_name_cn'])),
        ("英文品名", f"<span class='mono'>{E(inp['product_name_en'])}</span>"),
        ("CAS", f"<span class='mono'>{E(inp['cas'])}</span>"),
        ("UN 编号", f"<span class='mono'>{E(inp.get('un_no','—'))}</span>"),
        ("浓度/含量", f"<b>{E(inp['concentration'])}</b>"),
        ("形态", E(inp['physical_form'])),
        ("等级", E(inp['grade'])),
        ("执行标准", E(inp['exec_standard'])),
        ("进口用途", E(inp['usage'])),
        ("用途敏感性", E(inp['usage_sensitivity'])),
        ("包装方式", E(inp['packing'])),
        ("包装容器", E(inp['package_type'])),
        ("单件毛重", E(inp['gross_weight'])),
        ("申报『包装规格』", E(inp['hs_packing_spec'])),
        ("数量", E(inp['qty'])),
        ("运输方式", E(inp['transport_mode'])),
        ("贸易术语", E(inp['incoterm'])),
        ("起运/目的", E(inp['pol_pod'])),
        ("海外供应商", E(inp['supplier'])),
        ("进口企业", E(inp['importer'])),
    ])}
  </div>

  <div class="card">
    <h3>{icon('doc')} 组成（成分表）</h3>
    <div class="tw"><table class="t" style="min-width:0">
      <thead><tr><th>组分</th><th>英文</th><th>CAS</th><th class="r">含量</th><th>角色</th></tr></thead>
      <tbody>{comp_rows}</tbody></table></div>
    <p class="sml" style="margin-top:8px;color:var(--ink-3)">
      <b>为什么组成要写到稳定剂：</b>《危险化学品目录》第903项只覆盖「过氧化氢的水溶液」。应急管理部答复明确：浓度&gt;8% 的过氧化氢溶液中若添加了<b>稳定剂、惰性化学品以外</b>的其他化学品，即不属该水溶液条目，须另行开展危险特性鉴定。</p>
  </div>
</div>

<div class="grid2" style="margin-top:12px">
  <div class="card">
    <h3>{icon('check')} 已取得的身份证据</h3>
    <ul class="sml" style="margin:0;padding-left:18px;display:grid;gap:4px">{conf}</ul>
    <h3 style="margin-top:14px">{icon('warn')} 仍未确认的要素</h3>
    <ul class="sml" style="margin:0;padding-left:18px;display:grid;gap:4px;color:var(--bad)">{unconf}</ul>
  </div>
  <div class="card">
    <h3>{icon('shield')} 身份风险点与处置</h3>
    {risks}
  </div>
</div>
</section>
"""


def sec_hs(d):
    hv = d["hs_verdict"]
    rows = []
    for c in sorted(d["hs_candidates"], key=lambda x: x.get("rank", 9)):
        r1 = c.get("rank") == 1
        rows.append(f"""<tr class="{'rowwarn' if not r1 else ''}">
<td class="c">{'★' if r1 else c.get('rank')}</td>
<td class="m"><b style="font-size:13.4px">{E(c['code'])}</b></td>
<td>{E(c['desc'])}{' ' + badge('首选', 'solid') if r1 else ''}</td>
<td class="c">{badge(c.get('confidence','—'), CONF_CLS.get(c.get('confidence'), 'gray'))}</td>
<td class="sml">{E(c['basis'])}<div style="margin-top:4px">{src_tags(c.get('source'))}</div></td>
<td class="sml">{E(c['tests'])}</td>
<td class="sml">{E(c['alternatives'])}</td></tr>""")
    els = "".join(f"<span class='tag'>{i + 1}. {E(x)}</span> " for i, x in enumerate(hv.get("declaration_elements", [])))
    ciq = "".join(f"<li class='sml'><span class='mono'>{E(x)}</span></li>" for x in hv.get("ciq_codes", []))
    return f"""
<section id="s3">
<div class="sec-head"><span class="no">01</span><h2>HS 编码候选与归类依据</h2>
  <div class="lead">归类不是一个编码，而是一条可复核的推理链：章注/子目注释 → 品目条文 → 构成条件 → 不确定点。</div>
  <div class="tools">{badge('首选 ' + hv['recommended'], 'solid', True)}</div></div>

<div class="tw" data-tw="hs"><div class="filters">
  <span class="sml" id="count-hs" style="color:var(--muted)"></span></div>
<table class="t">
<thead><tr><th style="width:42px">排名</th><th style="width:112px">税则号列</th><th style="width:15%">品目描述</th>
<th style="width:64px">置信</th><th style="width:26%">归类依据</th><th>成立条件</th><th style="width:18%">不成立时去向</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>

<div class="grid2" style="margin-top:12px">
  <div class="card">
    <h3>{icon('clipboard')} 规范申报要素（按顺序填写）</h3>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">{els}</div>
    <div style="background:var(--card-2);border:1px dashed var(--line-2);border-radius:6px;padding:9px 11px">
      <div class="sml" style="color:var(--muted);margin-bottom:3px">填报示例（『规格型号』栏，用 | 分隔）</div>
      <div class="mono" style="font-size:11.8px;word-break:break-all">{E(hv.get('declaration_example',''))}</div>
    </div>
    <h3 style="margin-top:14px">{icon('scale')} 归类不确定性</h3>
    <p class="sml" style="margin:0">{E(hv['uncertainty'])}</p>
    <p class="sml" style="margin-top:8px">是否需要预裁定：<b>{E(hv['need_classification_ruling'])}</b></p>
  </div>
  <div class="card">
    <h3>{icon('search')} CIQ 扩展码（法定检验检疫）</h3>
    <ul style="margin:0;padding-left:18px;display:grid;gap:3px">{ciq}</ul>
    <p class="sml" style="margin-top:10px;color:var(--ink-3)">{E(hv.get('ciq_note',''))}</p>
  </div>
</div>
</section>
"""


def sec_tax(d):
    tr = d["tax_rates"]
    calc = d.get("calculation", {})
    fta_rows = "".join(f"""<tr class="{'rowwarn' if f.get('status') in ('disputed','pending','claimed') else ''}">
<td>{E(f['scheme'])}</td><td class="c m">{E(f['rate_hint'])}</td>
<td class="c">{badge({'disputed':'数据冲突·待核实','pending':'待核验','claimed':'仅供应商声称','verified':'已核实'}.get(f.get('status'), f.get('status')), {'disputed':'bad','pending':'warn','claimed':'warn','verified':'ok'}.get(f.get('status'),'gray'))}</td>
<td class="sml">{E(f['condition'])}</td></tr>""" for f in tr.get("fta", []))

    def money(v):
        return R.money(v)

    fta_sc = "".join(f"<tr><td class='sml'>{E(s['rate'])}</td><td class='r num'>{money(s['duty'])}</td><td class='sml'>{E(s['note'])}</td></tr>"
                     for s in calc.get("fta_scenario", []))

    return f"""
<section id="s4">
<div class="sec-head"><span class="no">02</span><h2>进口税费与优惠</h2>
  <div class="lead">税率以 {E(tr['tariff_year'])} 年税则为口径；优惠税率必须以「原产地规则 + 直接运输 + 原产地证书」三者同时成立为前提。</div></div>

<div class="grid3">
  <div class="card"><div class="sml" style="color:var(--muted)">最惠国税率</div>
    <div style="font-family:var(--num);font-size:30px;font-weight:700;color:var(--ink)">{E(tr['mfn']['rate'])}</div>
    <div class="sml">{E(tr['mfn']['note'])}</div></div>
  <div class="card"><div class="sml" style="color:var(--muted)">暂定税率</div>
    <div style="font-family:var(--num);font-size:24px;font-weight:700;color:var(--ink-3)">{E(tr['provisional']['rate'])}</div>
    <div class="sml">{E(tr['provisional']['note'])}</div></div>
  <div class="card"><div class="sml" style="color:var(--muted)">进口环节增值税</div>
    <div style="font-family:var(--num);font-size:30px;font-weight:700;color:var(--ink)">{E(tr['vat']['rate'])}</div>
    <div class="sml">{E(tr['vat']['note'])}</div></div>
  <div class="card"><div class="sml" style="color:var(--muted)">普通税率</div>
    <div style="font-family:var(--num);font-size:24px;font-weight:700;color:var(--ink-3)">{E(tr['general']['rate'])}</div>
    <div class="sml">{E(tr['general']['note'])}</div></div>
  <div class="card"><div class="sml" style="color:var(--muted)">消费税</div>
    <div style="font-family:var(--num);font-size:24px;font-weight:700;color:var(--ink-3)">{E(tr['consumption_tax']['rate'])}</div>
    <div class="sml">{E(tr['consumption_tax']['note'])}</div></div>
  <div class="card" style="background:linear-gradient(160deg,var(--warn-bg),var(--card) 70%)">
    <div class="sml" style="color:var(--warn)">优惠税率状态</div>
    <div style="font-family:var(--serif);font-size:16px;font-weight:700;color:var(--warn)">存在数据冲突，不可直接采用</div>
    <div class="sml">详见下方说明与待确认 Q03</div></div>
</div>

<div class="tw" style="margin-top:12px"><table class="t">
<thead><tr><th style="width:26%">优惠安排</th><th style="width:150px">页面显示税率</th><th style="width:120px">状态</th><th>适用条件</th></tr></thead>
<tbody>{fta_rows}</tbody></table></div>

<div class="card" style="margin-top:12px;border-left:3px solid var(--warn)">
  <h3>{icon('warn')} 为什么不能直接写「协定税率 1.1%」</h3>
  <p class="sml" style="margin:0">{E(tr['fta_note'])}
  <span class="tag src tC" data-src="S19">S19</span></p>
</div>

<div class="grid2" style="margin-top:12px">
  <div class="card">
    <h3>{icon('scale')} 税额试算（示例口径）</h3>
    {dl([
      ("CIF（USD）", f"<span class='num'>${calc.get('cif_usd',0):,.2f}</span>"),
      ("汇率", f"<span class='mono'>{calc.get('fx')}</span>（示例值，以海关计征日为准）"),
      ("CIF（CNY）", f"<span class='num'>{money(calc.get('cif_cny'))}</span>"),
      ("关税 " + E(calc.get('duty_rate', '')), f"<span class='num'>{money(calc.get('duty_cny'))}</span>"),
      ("增值税计税价", f"<span class='num'>{money(calc.get('vat_base_cny'))}</span>"),
      ("增值税 " + E(calc.get('vat_rate', '')), f"<span class='num'>{money(calc.get('vat_cny'))}</span>"),
      ("税费合计", f"<b class='num' style='font-size:15px'>{money(calc.get('total_tax_cny'))}</b>"),
    ])}
    <p class="sml" style="margin:10px 0 0;color:var(--ink-3)">{E(calc.get('note',''))}</p>
  </div>
  <div class="card">
    <h3>{icon('globe')} 若享惠，税额如何变化</h3>
    <div class="tw" style="margin-top:0"><table class="t" style="min-width:0">
      <thead><tr><th>假定税率</th><th class="r">关税（CNY）</th><th>说明</th></tr></thead>
      <tbody>{fta_sc}<tr><td class="sml">{E(calc.get('duty_rate',''))}</td><td class="r num">{money(calc.get('duty_cny'))}</td><td class="sml">最惠国税率（无证书时的兜底）</td></tr></tbody></table></div>
    <p class="sml" style="margin-top:8px;color:var(--ink-3)">上表按 CIF = {money(calc.get('cif_cny'))} 计算；增值税为可抵扣进项，此处仅计现金流影响。</p>
  </div>
</div>
</section>
"""


def sec_regulation(d):
    regs = d["regulation_checklist"]
    rows = []
    for r in regs:
        v = r["verdict"]
        rows.append(f"""<tr class="{'rowwarn' if v in ('conditional','pending') else ''}"
    data-rowkey="{v}" data-search="{E((r['item'] + r['conclusion'] + r['layer']).lower())}">
<td class="m" style="white-space:nowrap">{E(r['id'])}</td>
<td class="sml" style="white-space:nowrap">{E(r['layer'])}</td>
<td><b>{E(r['item'])}</b></td>
<td class="c" style="white-space:nowrap">{badge(R.VERDICT_TEXT.get(v, v), VERDICT_CLS.get(v, 'gray'))}</td>
<td class="sml">{E(r['conclusion'])}</td>
<td class="sml">{E(r['basis'])}<div style="margin-top:4px">{src_tags(r['source'])}</div></td>
<td class="sml">{E(r.get('condition',''))}</td>
<td class="sml">{E(r.get('impact',''))}</td>
<td class="sml" style="white-space:nowrap">{E(r.get('owner',''))}</td></tr>""")
    cnt = {k: sum(1 for x in regs if x["verdict"] == k) for k in R.VERDICTS}
    chips = [f'<button class="fchip on" data-filter="all">全部 <span class="c">{len(regs)}</span></button>']
    for k, label in [("applies", "适用"), ("conditional", "视条件"), ("pending", "待核验"), ("not_applies", "不适用")]:
        chips.append(f'<button class="fchip" data-filter="{k}">{label} <span class="c">{cnt[k]}</span></button>')
    return f"""
<section id="s5">
<div class="sec-head"><span class="no">03</span><h2>监管与许可</h2>
  <div class="lead">逐项比对、逐条留据。「待核验」不等于「不适用」；「不适用」必须能指回条文。</div>
  <div class="tools"><span class="sml" id="count-reg" style="color:var(--muted)"></span></div></div>

<div class="tw" data-tw="reg"><div class="filters">
  {''.join(chips)}
  <div class="search">{icon('search')}<input type="search" placeholder="搜索监管项 / 结论 / 法规" aria-label="搜索监管项"></div>
</div>
<table class="t">
<thead><tr><th>#</th><th>管理层</th><th style="width:15%">监管事项</th><th>判定</th>
<th style="width:22%">结论</th><th style="width:24%">依据（含来源）</th><th style="width:16%">适用条件</th><th style="width:14%">对本单的影响</th><th>责任方</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
</section>
"""


def sec_danger(d):
    dd = d["danger_distinction"]
    ch, gd = dd["chemical"], dd["goods"]
    mrows = "".join(f"""<tr><td><b class="sml">{E(m['case'])}</b></td>
<td class="sml">{E(m['chem'])}</td><td class="sml">{E(m['goods'])}</td><td class="sml">{E(m['note'])}</td></tr>"""
                    for m in dd["matrix"])
    errs = "".join(f"<li>{E(x)}</li>" for x in dd["common_errors"])
    t = d["transport"]
    seg = "".join(f"<li>{E(x)}</li>" for x in t.get("segregation", []))
    stow = "".join(f"<li>{E(x)}</li>" for x in t.get("stowage", []))
    notes = "".join(f"<li>{E(x)}</li>" for x in t.get("notes", []))
    return f"""
<section id="s6">
<div class="sec-head"><span class="no">04</span><h2>危险属性：两套分类必须分开判</h2>
  <div class="lead">{E(dd['lead'])}</div></div>

<div class="vs">
  <div class="box hz">
    <div class="vt">{icon('shield')} 中国安全生产监管</div>
    <h4>危险化学品</h4>
    <div class="en">Hazardous Chemicals（China Catalogue）</div>
    {badge('视条件适用', 'warn', True)}
    {dl([("监管体系", E(ch['regime'])), ("目录条目", f"<b>{E(ch['entry'])}</b>"),
         ("阈值", E(ch['threshold'])), ("后果", E(ch['consequence']))])}
  </div>
  <div class="mid"><span class="ln"></span><span class="neq">≠</span></div>
  <div class="box dg">
    <div class="vt">{icon('truck')} 运输环节国际/国标</div>
    <h4>危险货物</h4>
    <div class="en">Dangerous Goods（UN / GB 12268）</div>
    {badge('适用', 'bad', True)}
    {dl([("监管体系", E(gd['regime'])), ("分类", f"<b>{E(gd['cls'])}</b> · 次要危险 {E(gd.get('subsidiary',''))}"),
         ("UN / 包装类别", f"<span class='mono'><b>{E(gd['un'])}</b> · PG {E(gd['pg'])}</span>"),
         ("正确运输名称", f"<span class='mono' style='font-size:11px'>{E(gd['proper_shipping_name'])}</span>"),
         ("阈值", E(gd['threshold'])), ("后果", E(gd['consequence']))])}
  </div>
</div>

<div class="card">
  <h3>{icon('scale')} 浓度阈值轨道 —— 为什么必须写死 30%</h3>
  <div class="track">
    <span class="lbl" style="left:0;transform:none">0%</span>
    <span class="lbl" style="left:12.5%">8%</span>
    <span class="lbl" style="left:40%">20%</span>
    <span class="lbl" style="left:80%">60%</span>
    <span class="lbl" style="left:100%;transform:translateX(-100%)">100%</span>
    <div class="rail"><i></i><i></i><i></i><i></i></div>
    <span class="tick" style="left:12.5%"></span><span class="tick" style="left:40%"></span><span class="tick" style="left:80%"></span>
    <span class="seg-note" style="left:6.2%">&lt;8%：通常不受此两条约束</span>
    <span class="seg-note" style="left:26%">UN2984 · PG III · 氧化性液体类3</span>
    <span class="seg-note" style="left:60%">UN2014 · PG II · 氧化性液体类2</span>
    <span class="seg-note" style="left:90%">UN2015 · PG I · 类别1</span>
    <div class="mk" style="left:31%"><span class="cap">本单 30%</span><span class="pin"></span></div>
  </div>
  <p class="sml" style="margin:2px 0 0;color:var(--ink-3)">
    浓度同时决定三件事：是否落入危化品目录第903项（&gt;8%）、易制爆名录的分档（≥60% / 20%–60% / 8%–20%）、运输 UN 编号（2984 / 2014 / 2015）。
    因此合同与标签必须写死「30.0%（质量分数）」，并约定<b>不得跨阈值</b>的交货偏差。</p>
</div>

<div class="tw" style="margin-top:12px"><table class="t">
<thead><tr><th style="width:24%">浓度 / 形态</th><th style="width:24%">危险化学品（目录）</th><th style="width:26%">危险货物（运输）</th><th>要点</th></tr></thead>
<tbody>{mrows}</tbody></table></div>

<div class="grid2" style="margin-top:12px">
  <div class="card">
    <h3>{icon('truck')} 运输分类与积载（{E(t['mode'])}）</h3>
    {dl([("适用规则", E(t['regime_standard'])), ("国内国标", E(t['domestic_standard'])),
         ("UN 编号", f"<span class='mono'>{E(t['un'])}</span>"),
         ("正确运输名称", f"<span class='mono' style='font-size:11px'>{E(t['proper_shipping_name_en'])}</span>"),
         ("类别", E(t['class'])), ("次要危险", E(t['subsidiary_risk'])), ("包装类别", f"<b>{E(t['packing_group'])}</b>"),
         ("包装指令", E(t['packing_instruction'])), ("EmS", E(t['emS'])),
         ("类项标志", "、".join(E(x) for x in t.get('labels', [])))])}
    <h3 style="margin-top:12px">隔离与积载</h3>
    <ul class="sml" style="margin:0;padding-left:18px;display:grid;gap:3px">{seg}{stow}</ul>
  </div>
  <div class="card">
    <h3>{icon('warn')} 常见混淆（务必避免）</h3>
    <ul class="sml" style="margin:0;padding-left:18px;display:grid;gap:5px">{errs}</ul>
    <h3 style="margin-top:12px">运输口径补充</h3>
    <ul class="sml" style="margin:0;padding-left:18px;display:grid;gap:3px">{notes}</ul>
  </div>
</div>
</section>
"""


def sec_labels(d):
    lp = d["labels_packaging"]
    g = lp["ghs_label"]
    h = "".join(f"<span class='tag' style='margin:2px 0'>{E(x)}</span> " for x in g.get("h_statements", []))
    p = "".join(f"<span class='tag' style='margin:2px 0'>{E(x)}</span> " for x in g.get("p_statements", []))
    elems = "".join(f"<li class='sml'>{E(x)}</li>" for x in g.get("elements", []))
    pics = "".join(f"<span class='badge dg'>{E(x)}</span> " for x in g.get("pictograms", []))
    marks = "".join(f"<li class='sml'>{E(x)}</li>" for x in lp.get("transport_marks", []))
    issues = "".join(f"""<div class="gap {'p0' if i['level']=='高' else 'p1'}" style="margin-bottom:6px">
        <div class="gh"><span class="gh">{badge(i['level'], 'bad' if i['level']=='高' else 'warn')}</span>
        <span class="gt" style="font-size:12.8px">{E(i['item'])}</span></div>
        <div class="gb"><div class="q"><span class="k">整改</span><span>{E(i['fix'])}</span></div></div></div>"""
                     for i in lp.get("issues", []))
    pk = lp["package"]
    return f"""
<section id="s7">
<div class="sec-head"><span class="no">05</span><h2>包装与标签</h2>
  <div class="lead">中文化学品安全标签（GB 15258）与危险货物运输标志（UN 标记 + 类项标志）是两套并行要求，缺一不可。</div></div>

<div class="grid2">
  <div class="card">
    <h3>{icon('doc')} 中文危险公示标签（GHS）</h3>
    {dl([("是否强制", f"<b>{E(g['required'])}</b>"), ("语言", E(g['lang'])), ("依据标准", E(g['std'])),
         ("信号词", f"<b style='color:var(--bad)'>{E(g['signal_word'])}</b>")])}
    <div style="margin:8px 0 4px">{pics}</div>
    <div class="sml" style="color:var(--muted);margin-top:8px">危险性说明</div><div>{h}</div>
    <div class="sml" style="color:var(--muted);margin-top:8px">防范说明</div><div>{p}</div>
    <div class="sml" style="color:var(--warn);margin-top:10px;border-left:2px solid var(--warn-line);padding-left:8px">{E(g.get('note',''))}</div>
  </div>
  <div class="card">
    <h3>{icon('clipboard')} 标签必备要素</h3>
    <ul style="margin:0;padding-left:18px;display:grid;gap:3px">{elems}</ul>
    <h3 style="margin-top:14px">{icon('box')} 运输标志与包装</h3>
    <ul style="margin:0;padding-left:18px;display:grid;gap:3px">{marks}</ul>
    {dl([("包装型式", E(pk['type'])), ("包装证明", E(pk['cert'])), ("相容性要求", E(pk['compat']))])}
  </div>
</div>

<div class="card" style="margin-top:12px">
  <h3>{icon('warn')} 上传标签存在的问题（{len(lp.get('issues', []))} 项）</h3>
  {issues}
</div>
</section>
"""


def sec_documents(d):
    comp = R.doc_completeness(d["documents"])
    groups = []
    for gname in ["海外供应商资料", "中文合规文件", "进口报关资料", "运输资料", "海关/税费"]:
        gd = [x for x in d["documents"] if x["group"] == gname]
        if gd:
            groups.append((gname, gd))
    other = [x for x in d["documents"] if x["group"] not in dict(groups)]
    if other:
        groups.append(("其他", other))

    rows = []
    for dcs in d["documents"]:
        st = dcs["status"]
        up = next((u for u in d["uploaded"] if u["id"] == dcs.get("uploaded_id")), None)
        rows.append(f"""<tr class="{'rowfail' if st in ('missing','expired') else 'rowwarn' if st in ('partial','pending') else ''}"
  data-rowkey="{st}" data-search="{E((dcs['name_cn']+' '+dcs['name_en']+' '+dcs['group']+' '+dcs['owner']).lower())}">
<td class="m" style="white-space:nowrap">{E(dcs['id'])}</td>
<td class="sml" style="white-space:nowrap">{E(dcs['group'])}</td>
<td><b>{E(dcs['name_cn'])}</b><div class="sml" style="color:var(--muted)">{E(dcs['name_en'])}</div></td>
<td class="c">{badge(dcs['required'], REQ_CLS.get(dcs['required'], 'gray'))}</td>
<td class="c">{badge(R.DOC_STATUS_TEXT.get(st, st), STATUS_CLS.get(st, 'gray'))}</td>
<td class="sml">{E(dcs.get('content_check',''))}</td>
<td class="sml">{E(dcs.get('issue','')) if dcs.get('issue') else '<span style="color:var(--ok)">—</span>'}</td>
<td class="sml" style="white-space:nowrap">{E(dcs['owner'])}</td>
<td class="sml">{src_tags(dcs.get('source'))}</td></tr>""")

    def money_pct(p):
        return f"{p:.0f}%"

    plist = []
    for gname, gd in groups:
        gp = comp["groups"].get(gname, {})
        cls = "ok" if gp.get("pct", 0) >= 90 else "warn" if gp.get("pct", 0) >= 55 else "bad"
        plist.append(f"""<div class="pl-row">
  <div class="pl-n">{E(gname)} <span class="tag">{gp.get('ok',0)}/{gp.get('n',0)}</span></div>
  <div class="pbar {cls}"><i style="width:{gp.get('pct',0):.0f}%"></i></div>
  <div class="pl-v">{gp.get('pct',0):.0f}%</div></div>""")

    cnt = {k: sum(1 for x in d["documents"] if x["status"] == k) for k in R.DOC_STATUS}
    chips = [f'<button class="fchip on" data-filter="all">全部 <span class="c">{len(d["documents"])}</span></button>',
             f'<button class="fchip" data-filter="missing">缺失 <span class="c">{cnt["missing"]}</span></button>',
             f'<button class="fchip" data-filter="partial">不完整 <span class="c">{cnt["partial"]}</span></button>',
             f'<button class="fchip" data-filter="pending">待定 <span class="c">{cnt["pending"]}</span></button>',
             f'<button class="fchip" data-filter="ok">齐备 <span class="c">{cnt["ok"]}</span></button>']

    return f"""
<section id="s8">
<div class="sec-head"><span class="no">06</span><h2>单证清单</h2>
  <div class="lead">按「海外供应商资料 / 中文合规文件 / 进口报关资料 / 运输资料」分组，每项标注依据、必备字段、责任主体与当前状态。</div>
  <div class="tools"><span class="sml" id="count-doc" style="color:var(--muted)"></span></div></div>

<div class="card" style="margin-bottom:12px">
  <h3>{icon('clipboard')} 分组完备度
    <span class="tag-n"><b style="font-family:var(--num);font-size:20px;color:{'var(--ok)' if comp['pct']>=90 else 'var(--warn)' if comp['pct']>=55 else 'var(--bad)'}">{comp['pct']}%</b>
    <span class="sml" style="color:var(--muted)">（按『必须=3/视情形=1/建议=0.5』加权）</span></span></h3>
  <div class="progress-list">{''.join(plist)}</div>
</div>

<div class="tw" data-tw="doc"><div class="filters">
  {''.join(chips)}
  <div class="search">{icon('search')}<input type="search" placeholder="搜索单证 / 责任方" aria-label="搜索单证"></div>
</div>
<table class="t">
<thead><tr><th>#</th><th>分组</th><th style="width:18%">文件</th><th>要求</th><th>状态</th>
<th style="width:20%">必备关键字段</th><th style="width:20%">当前问题</th><th>责任主体</th><th>依据</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
</section>
"""


def sec_uploaded(d):
    cards = []
    icons_map = {"SDS": "SDS", "COA": "COA", "PI": "PI", "标签": "LABEL", "TDS": "TDS"}
    for u in d["uploaded"]:
        chk = []
        for c in u.get("checks", []):
            r = c.get("result", "na")
            chk.append(f"""<div class="ci {r}"><span class="mk">{RESULT_SYM.get(r,'·')}</span>
<span class="ct">{E(c['item'])}<span class="cn">{E(c.get('note',''))}</span></span></div>""")
        kv = "".join(f"<div><div class='k'>{E(e['field'])}</div><div class='v'>{E(e['value'])}</div></div>"
                     for e in u.get("extracted", []))
        nfail = sum(1 for c in u.get("checks", []) if c["result"] == "fail")
        mock = (f'<div class="mock">{icon("warn")} <b>模拟文件</b> · {E(u.get("mock_note",""))}</div>' if u.get("is_mock") else "")
        cards.append(f"""<div class="up">
  <div class="uh"><span class="fi">{E(icons_map.get(u['type'], u['type'][:4].upper()))}</span>
    <div style="min-width:0"><div class="fn">{E(u['file'])}</div>
    <div class="fs">{E(u['id'])} · {E(u['type'])} · {E(u['lang'])} · {E(u['received'])}</div></div>
    {badge(R.UPLOAD_TEXT.get(u['verdict'], u['verdict']), 'ok' if u['verdict']=='usable' else 'warn' if u['verdict']=='usable_with_fix' else 'bad')}</div>
  {mock}
  <div class="ub">
    <div class="sml" style="color:var(--muted)">已提取字段</div>
    <div class="kv-grid">{kv}</div>
    <div class="sml" style="color:var(--muted);margin-top:2px">检查项（{len(u.get('checks',[]))} 项，失败 {nfail}）</div>
    <div class="chk">{''.join(chk)}</div>
  </div>
  <div class="uf">{badge('结论', 'info')}<span style="color:var(--ink-2)">{E(u.get('verdict_note',''))}</span></div>
</div>""")
    cons = R.consistency_issues(d)
    crows = "".join(f"<tr><td class='c'>{badge(x['level'], 'bad' if x['level']=='高' else 'warn')}</td>"
                    f"<td><b>{E(x['item'])}</b></td><td class='sml'>{E(x['detail'])}</td><td class='sml'>{E(x['fix'])}</td></tr>"
                    for x in cons)
    return f"""
<section id="s9">
<div class="sec-head"><span class="no">07</span><h2>已上传文件检查</h2>
  <div class="lead">对每份上传件做「字段提取 + 要件核对 + 交叉一致性」三件事。标有 <b>模拟文件</b> 的件仅用于演示流程，不代表任何真实供应商。</div></div>

<div class="doc-cards">{''.join(cards)}</div>

<div class="card" style="margin-top:14px">
  <h3>{icon('warn')} 交叉一致性检查（{len(cons)} 项）</h3>
  <div class="tw" style="margin-top:0"><table class="t" style="min-width:0">
    <thead><tr><th style="width:64px">等级</th><th style="width:22%">问题</th><th>明细</th><th style="width:36%">处置</th></tr></thead>
    <tbody>{crows or '<tr><td colspan="4" class="c sml">未发现交叉冲突</td></tr>'}</tbody></table></div>
</div>
</section>
"""


def sec_gaps(d):
    order = {"P0": 0, "P1": 1, "P2": 2}
    gaps = sorted(d["gaps"], key=lambda g: (order.get(g["priority"], 9), g["id"]))
    items = []
    for g in gaps:
        p = g["priority"]
        items.append(f"""<div class="gap {p.lower()}">
  <div class="gh">
    <input type="checkbox" data-gap="{E(g['id'])}" data-pri="{p}" id="gl-{E(g['id'])}" aria-label="标记 {E(g['missing'])} 已完成">
    <span class="gid">{E(g['id'])}</span>
    {badge(p, 'bad' if p=='P0' else 'warn' if p=='P1' else 'info')}
    {badge('阻断', 'solid') if g.get('blocking') == '是' else ''}
    <span class="gt">{E(g['missing'])}</span>
    <span class="badge gray">{E(g['owner'])}</span>
  </div>
  <div class="gb">
    <div class="q"><span class="k">为什么</span><span>{E(g['why'])}</span></div>
    <div class="q"><span class="k">怎么要</span><span>{E(g['ask'])}</span></div>
  </div>
</div>""")
    p0 = sum(1 for g in d["gaps"] if g["priority"] == "P0")
    p1 = sum(1 for g in d["gaps"] if g["priority"] == "P1")
    p2 = sum(1 for g in d["gaps"] if g["priority"] == "P2")
    return f"""
<section id="s10" data-box="box-gaps">
<div class="sec-head"><span class="no">08</span><h2>缺失资料清单</h2>
  <div class="lead">P0 = 不取得不得报关/不得使用；P1 = 影响税费、时效或质量；P2 = 档案完善。勾选状态保存在本机浏览器。</div>
  <div class="tools">
    <span class="sml" style="color:var(--muted)">完成进度 <b id="gappct">0%</b> · <span id="gapdone">0/0</span></span>
    <button class="btn" data-markall="box-gaps">{icon('check')}全部标记</button>
    <button class="btn" onclick="window.__resetProgress&&window.__resetProgress()">{icon('x')}清空</button>
  </div></div>

<div class="card" style="margin-bottom:12px;padding:12px 16px">
  <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
    <div class="pbar" id="gapbar-wrap" style="flex:1 1 260px;min-width:180px;height:8px">
      <i id="gapbar" style="width:0"></i></div>
    <span class="badge bad">P0 {p0} 项</span><span class="badge warn">P1 {p1} 项</span><span class="badge info">P2 {p2} 项</span>
  </div>
</div>
{''.join(items)}
</section>
"""


def sec_actors(d):
    cls = {"海外供应商": "a-supplier", "进口商": "a-importer", "承运人/船公司": "a-carrier",
           "报关代理": "a-agent", "第三方检测机构": "a-lab", "监管机构": "a-gov"}
    ic = {"海外供应商": "building", "进口商": "flask", "承运人/船公司": "truck",
          "报关代理": "clipboard", "第三方检测机构": "search", "监管机构": "shield"}
    cards = []
    for a in d["responsibilities"]:
        lis = "".join(f"<li>{E(x)}</li>" for x in a["items"])
        cards.append(f"""<div class="actor {cls.get(a['actor'],'')}">
  <div class="ah"><span class="ai">{icon(ic.get(a['actor'],'doc'))}</span><span class="an">{E(a['actor'])}</span>
    <span class="ac">{len(a['items'])}</span></div>
  <ul>{lis}</ul>
  <div class="an2">{E(a.get('notes',''))}</div></div>""")
    return f"""
<section id="s11">
<div class="sec-head"><span class="no">09</span><h2>责任划分：谁提供、谁办理</h2>
  <div class="lead">同一份资料由谁出、谁核对、谁留存，必须在合同签约前说清楚，否则一旦被查验就会互相推诿。</div></div>
<div class="actors">{''.join(cards)}</div>
</section>
"""


def sec_confirm(d):
    ic = {"高": "bad", "中": "warn", "低": "info"}
    items = []
    for q in d["to_confirm"]:
        items.append(f"""<div class="qc">
  <div class="qh"><span class="qid">{E(q['id'])}</span>{badge(q['severity'] + '优先', ic.get(q['severity'],'gray'))}
    <span class="qt">{E(q['topic'])}</span>{badge(q['who'], 'info')}</div>
  <div class="qb">
    <span class="k">为何不能自判</span><span>{E(q['why'])}</span>
    <span class="k">怎么核实</span><span>{E(q['how'])}</span>
    <span class="k">判断错的代价</span><span style="color:var(--bad)">{E(q['impact_if_wrong'])}</span>
  </div>
</div>""")
    return f"""
<section id="s12">
<div class="sec-head"><span class="no">10</span><h2>待确认事项（须报关行 / 合规顾问 / 属地部门确认）</h2>
  <div class="lead">下列问题<b>不能</b>由公开资料可靠回答。请以书面形式取得答复并归档，口头沟通不构成依据。</div></div>
{''.join(items)}
</section>
"""


def sec_timeline(d):
    items = "".join(f"""<div class="it"><div class="tt">{E(t['t'])}</div>
      <div class="ta">{E(t['action'])}</div><div class="to">{E(t['owner'])}</div></div>""" for t in d["timeline"])
    st = d["assessment"]
    stmt = "".join(f"""<tr><td class="sml" style="color:var(--ok)">{E(a)}</td>
      <td class="sml" style="color:var(--bad)">{E(b)}</td></tr>""" for a, b in st.get("statements", []))
    nxt = "".join(f"<tr><td class='m' style='white-space:nowrap'>{E(a)}</td><td class='sml'>{E(b)}</td></tr>"
                  for a, b in st.get("next_steps", []))
    return f"""
<section id="s13">
<div class="sec-head"><span class="no">11</span><h2>时间线与结论口径</h2>
  <div class="lead">从签约前到到港后的关键动作；以及本底稿允许/不允许出现的表述。</div></div>

<div class="grid2">
  <div class="card"><h3>{icon('clock')} 关键路径</h3><div class="tl">{items}</div></div>
  <div>
    <div class="card"><h3>{icon('scale')} 结论口径（可以写 / 不能写）</h3>
      <div class="tw" style="margin-top:0"><table class="t" style="min-width:0">
        <thead><tr><th style="width:52%">可以写</th><th>不能写</th></tr></thead>
        <tbody>{stmt}</tbody></table></div></div>
    <div class="card" style="margin-top:12px"><h3>{icon('check')} 下一步动作</h3>
      <div class="tw" style="margin-top:0"><table class="t" style="min-width:0">
        <thead><tr><th style="width:120px">时间</th><th>动作</th></tr></thead>
        <tbody>{nxt}</tbody></table></div></div>
  </div>
</div>
</section>
"""


def sec_request(d):
    r = d["supplier_request_en"]
    rows = "".join(f"""<tr><td class="c m">{E(i['no'])}</td><td><b>{E(i['doc'])}</b></td>
      <td class="sml">{E(i['detail'])}</td><td class="sml" style="white-space:nowrap">{E(i['due'])}</td></tr>"""
                   for i in r["items"])
    return f"""
<section id="s14">
<div class="sec-head"><span class="no">12</span><h2>英文索取清单（可直接发给海外供应商）</h2>
  <div class="lead">按 P0/P1 缺口自动生成，含每项必须包含的具体内容与时限。</div>
  <div class="tools">
    <button class="btn" onclick="window.__exportRequest&&window.__exportRequest()">{icon('download')}导出 .txt</button>
    <button class="btn" onclick="window.__copyRequest&&window.__copyRequest()">{icon('copy')}复制全文</button>
  </div></div>

<div class="letter">
  <div class="lh">{icon('doc')}<b>{E(r['title'])}</b><span class="sp"></span>
    <span class="sml" style="color:#9fb0ac;font-family:var(--mono)">{E(d['meta']['record_id'])}</span></div>
  <div class="lb">{E(r['intro'])}</div>
  <div class="ls"><div class="tw"><table class="t">
    <thead><tr><th style="width:38px">#</th><th style="width:26%">Document required</th><th>What it must contain</th><th>Timing</th></tr></thead>
    <tbody>{rows}</tbody></table></div></div>
  <div class="lb" style="padding-top:0">{E(r['closing'])}</div>
  <div class="lf">本文件由进口资料准备底稿自动生成。清单内容随缺口变化，发给供应商前请复核收件人与 PO 号。</div>
</div>
</section>
"""


def sec_sources(d):
    SRC = d["sources"]
    stats = R.source_stats(SRC)
    rows = []
    for s in SRC:
        eff = s.get("effective", "")
        eff_cls = {"现行有效": "ok", "部分替代": "warn", "已废止": "bad", "未核实": "gray"}.get(eff, "gray")
        tier = s.get("tier", "C")
        rows.append(f"""<div class="src-item" id="src-{E(s['id'])}">
  <div class="sh"><span class="sid">{E(s['id'])}</span><span class="tier {tier}">{tier}</span>
    {badge(s.get('kind',''), 'gray')}<span class="st">{E(s['title'])}</span>{badge(eff, eff_cls)}</div>
  <div class="meta"><span>{E(s.get('publisher',''))}</span><span>日期：{E(s.get('date',''))}</span>
    <span>查询日期：{E(s.get('accessed',''))}</span>
    <a href="{E(s.get('url',''))}" target="_blank" rel="noopener" style="max-width:520px;display:inline-block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">原文</a></div>
  <div class="sup">支撑：{E(s.get('supports',''))}</div>
</div>""")
    return f"""
<section id="s15">
<div class="sec-head"><span class="no">13</span><h2>法规来源与查询日期</h2>
  <div class="lead">每条结论都可回溯到下列来源。A 级为官方一手；B 级为官方转载/政务数据库；C 级仅供交叉参考。</div>
  <div class="tools">
    <span class="badge bad">A 级 {stats['A']}</span><span class="badge warn">B 级 {stats['B']}</span>
    <span class="badge gray">C 级 {stats['C']}</span></div></div>
<div class="card">{''.join(rows)}</div>

<div class="card" style="margin-top:12px;background:var(--card-2)">
  <h3>{icon('warn')} 使用边界</h3>
  <p class="sml" style="margin:0;color:var(--ink-3)">
  本底稿是基于公开资料的<b>准备性核验</b>，不构成法律意见，也不替代海关、应急管理、公安等部门的实际认定。
  凡标注「待核验 / 数据冲突 / 未核实」的条目，须由报关行、合规顾问或主管部门书面确认后方可用于申报与结算。
  上传文件中的<b>模拟件</b>仅用于演示流程，其供应商名称、批号与金额均为虚构。</p>
</div>
</section>
"""


def build_nav(d):
    n_docs = len(d["documents"])
    n_gaps = len(d["gaps"])
    n_q = len(d["to_confirm"])
    nav = [
        ("概览", [("s0", "报头与结论", ""), ("s1", "放行闸门", "6")]),
        ("识别", [("s2", "产品与归类", ""), ("s3", "HS 编码候选", str(len(d["hs_candidates"]))), ("s4", "税费与优惠", "")]),
        ("监管", [("s5", "监管与许可", str(len(d["regulation_checklist"]))), ("s6", "危险属性双轨", "")]),
        ("文件", [("s7", "包装与标签", ""), ("s8", "单证清单", str(n_docs)), ("s9", "已上传检查", str(len(d["uploaded"])))]),
        ("行动", [("s10", "缺失资料", str(n_gaps)), ("s11", "责任划分", ""), ("s12", "待确认事项", str(n_q)),
                ("s13", "时间线", ""), ("s14", "英文索取清单", "")]),
        ("证据", [("s15", "法规来源", str(len(d["sources"])))]),
    ]
    out = []
    for grp, items in nav:
        out.append(f'<div class="grp">{E(grp)}</div>')
        for i, (sid, label, cnt) in enumerate(items):
            c = f'<span class="cnt">{E(cnt)}</span>' if cnt else ""
            out.append(f'<a href="#{sid}"><span class="n">{i+1:02d}</span>{E(label)}{c}</a>')
    return "".join(out)


# ---------------------------------------------------------------------------
def render(data: dict) -> str:
    grade = R.overall_grade(data)
    css = open(os.path.join(ROOT, "assets", "report.css"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "assets", "report.js"), encoding="utf-8").read()
    payload = {
        "meta": data["meta"], "as_of": data["as_of"],
        "sources": data["sources"], "supplier_request_en": data["supplier_request_en"],
    }
    payload_js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    body = "".join([
        sec_hero(data, grade),
        sec_gates(data, grade),
        sec_identity(data),
        sec_hs(data),
        sec_tax(data),
        sec_regulation(data),
        sec_danger(data),
        sec_labels(data),
        sec_documents(data),
        sec_uploaded(data),
        sec_gaps(data),
        sec_actors(data),
        sec_confirm(data),
        sec_timeline(data),
        sec_request(data),
        sec_sources(data),
    ])

    meta = data["meta"]
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(data['title'])}</title>
<meta name="description" content="进口资料准备与合规核验底稿：产品身份、HS 归类、监管属性、危险货物、单证与缺口。">
<style>{css}</style>
</head>
<body>
<div class="scrollbar" id="sb"></div>
<header class="topbar">
  <div class="brand"><span class="logo">{icon('flask')}</span>进口资料准备底稿<em>v{meta.get('methodology_version','1.0')}</em></div>
  <div class="tmeta">
    <span>{E(meta['record_id'])}</span><span class="sep">|</span>
    <span>基准日 <b>{E(data['as_of'])}</b></span><span class="sep">|</span>
    <span>分级 <b>{E(grade['grade'])} · {E(grade['grade_text'])}</b></span><span class="sep">|</span>
    <span>单证完备度 <b>{grade['doc_pct']}%</b></span>
  </div>
  <div class="tactions">
    <button class="btn" onclick="window.__print&&window.__print()">{icon('print')}打印 / 存 PDF</button>
    <button class="btn" onclick="window.__resetProgress&&window.__resetProgress()">重置进度</button>
    <button class="btn accent" onclick="window.__exportRequest&&window.__exportRequest()">{icon('download')}导出英文清单</button>
  </div>
</header>
<div class="layout">
  <aside class="side">
    {build_nav(data)}
    <div class="foot">
      <b>使用提示</b><br>
      点击表格中的 <span class="tag src">S01</span> 可查看法规原文与查询日期；<br>
      勾选缺失项进度会保存在本机；<br>
      模拟上传件均以斜纹底纹标注。
    </div>
  </aside>
  <main class="main">
    {body}
    <footer style="margin-top:34px;padding-top:14px;border-top:1px solid var(--line);
      font-size:11.6px;color:var(--muted);display:flex;gap:16px;flex-wrap:wrap">
      <span>{E(meta['record_id'])} · 生成于 {E(meta['generated_at'])}</span>
      <span>整理：{E(meta['prepared_by'])}</span>
      <span style="margin-left:auto">{E(meta.get('demo_notice',''))}</span>
    </footer>
  </main>
</div>

<div class="drawer-bg" id="drawer-bg"></div>
<aside class="drawer" id="drawer" aria-hidden="true" aria-label="来源详情">
  <div class="dh"><span class="dt" id="drawer-title">来源</span>
    <button class="x-btn" id="drawer-close" aria-label="关闭">{icon('x')}</button></div>
  <div class="db" id="drawer-body"></div>
</aside>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>window.DOSSIER = {payload_js};</script>
<script>{js}</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    with open(a.data, encoding="utf-8") as f:
        d = json.load(f)
    html_doc = render(d)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print("wrote", a.out, len(html_doc), "chars")


if __name__ == "__main__":
    main()
