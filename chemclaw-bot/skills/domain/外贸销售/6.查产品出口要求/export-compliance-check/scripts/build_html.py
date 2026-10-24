# -*- coding: utf-8 -*-
"""build_html.py — 由 case.json 生成自包含交互式 HTML 出口合规准备页

设计要点
--------
- 单文件、零外部依赖（不引用 CDN、不加载字体），可直接用浏览器打开或嵌入桌面壳。
- 交互流程：① 产品身份与 HS 候选确认 → ② 按主题筛选合规条目 → ③ 逐项展开看法规/条件/证据/状态。
- 危险化学品监管 与 危险货物运输 分栏呈现，并在页脚显式声明二者不可互推。

用法
----
python build_html.py <case.json> [--out page.html]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
from pathlib import Path

STATUS_CLASS = {
    "已核实": "ok",
    "待确认": "tbd",
    "参考信息": "ref",
    "不适用": "na",
    "不触发": "ok",
    "待取得": "tbd",
    "待准备": "tbd",
    "待确认是否办理": "tbd",
    "未闭环": "tbd",
    "已闭环": "ok",
}


def cls_of(status: str) -> str:
    """把业务状态映射到 4 类展示色：
    ok  = 已核实/已闭环/不触发（可作为结论使用）
    tbd = 待确认/需确认/待取得/待准备（未闭环，不得对外承诺）
    ref = 参考信息（非官方原文，仅供定位）
    na  = 不适用/已排除
    """
    s = status or ""
    if s.startswith("已核实") or s.startswith("不触发") or s.startswith("已闭环"):
        return "ok"
    if s.startswith(("待确认", "需确认", "待取得", "待准备", "未闭环", "待复核")):
        return "tbd"
    if s.startswith(("参考", "参考信息")):
        return "ref"
    if s.startswith(("不适用", "排除")):
        return "na"
    return "na"


def e(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def norm(s: str) -> str:
    return (s or "").replace("_", "-")


TOPIC_META = {
    "中国出口": ("🇨🇳", "危险化学品管理属性、许可证、检验与报关"),
    "目的国进口": ("🇻🇳", "法规版本、清关前申报、资质、标签/SDS、关税"),
    "运输": ("⚓", "UN 号、类别、包装类别、包装指令（危险货物体系）"),
    "标签与包装": ("🏷️", "GHS 公示标签、危险货物标签、包装相容性"),
}


def build(case: dict, chk: dict | None = None) -> str:
    meta = case["meta"]
    p = case["inputs"]["product"]
    as_of = meta["prepared_on"]

    # ---------- 统计 ----------
    secs = [("cn_export", "中国出口"), ("import_vn", "目的国进口"),
            ("transport", "运输"), ("label_pkg", "标签与包装")]
    by_topic = {}
    for key, t in secs:
        items = case[key]
        by_topic[t] = {
            "total": len(items),
            "ok": sum(1 for x in items if cls_of(x["status"]) == "ok"),
            "tbd": sum(1 for x in items if cls_of(x["status"]) == "tbd"),
            "ref": sum(1 for x in items if cls_of(x["status"]) == "ref"),
        }
    tot = sum(v["total"] for v in by_topic.values())
    tot_ok = sum(v["ok"] for v in by_topic.values())
    tot_tbd = sum(v["tbd"] for v in by_topic.values())

    def topic_chips():
        out = ['<button class="chip active" data-filter="all">全部 <b>%d</b></button>' % tot]
        for t, v in by_topic.items():
            icon, _ = TOPIC_META.get(t, ("•", ""))
            out.append(f'<button class="chip" data-filter="{e(t)}">{icon} {e(t)} <b>{v["total"]}</b></button>')
        out.append('<button class="chip" data-filter="__tbd">仅看待确认 <b>%d</b></button>' % tot_tbd)
        return "".join(out)

    def render_entries(key, topic):
        icon, desc = TOPIC_META.get(topic, ("•", ""))
        rows = []
        for idx, x in enumerate(case[key], start=1):
            c = cls_of(x["status"])
            regs = "".join(
                f'<a class="tag reg" href="{e(r["url"])}" target="_blank" rel="noopener" title="{e(r["name"])} · 生效 {e(r["effective"])}">{e(r["id"])} {e(r["ref"])[:22]}</a>'
                for r in case["regs"] if r["id"] in (x.get("reg_ids") or [])
            )
            ev = ""
            if x.get("evidence"):
                ev = f'<a class="evidence" href="{e(x["evidence"])}" target="_blank" rel="noopener">打开官方原文 ↗</a>'
            caution = f'<div class="caution">⚠ {e(x["caution"])}</div>' if x.get("caution") else ""
            rows.append(f"""
<article class="item" data-topic="{e(topic)}" data-status="{c}" data-id="{e(x['id'])}">
  <header class="item-h" role="button" tabindex="0" aria-expanded="false">
    <span class="idx">{e(x['id'])}</span>
    <span class="it-title">{e(x['item'])}</span>
    <span class="badge {c}">{e(x['status'])}</span>
    <span class="caret">▾</span>
  </header>
  <div class="item-b">
    <p class="finding">{e(x['finding'])}</p>
    <dl class="kv">
      <dt>适用条件</dt><dd>{e(x.get('condition') or '—')}</dd>
      <dt>法规依据</dt><dd>{e(x['reg'])}</dd>
      <dt>生效 / 适用时间</dt><dd>{e(x['effective'])}</dd>
      <dt>下一步动作</dt><dd>{e(x.get('action') or '—')}</dd>
    </dl>
    {caution}
    <div class="tags">{regs}{ev}</div>
  </div>
</article>""")
        return f"""
<section class="topic-block" id="topic-{norm(topic)}" data-topic="{e(topic)}">
  <div class="topic-h">
    <h3>{icon} {e(topic)}</h3>
    <p>{e(desc)}</p>
    <div class="mini-stats">
      <span class="ms ok">已核实 {by_topic[topic]['ok']}</span>
      <span class="ms tbd">待确认 {by_topic[topic]['tbd']}</span>
      <span class="ms ref">参考 {by_topic[topic]['ref']}</span>
    </div>
  </div>
  <div class="items">{''.join(rows)}</div>
</section>"""

    entries_html = "".join(render_entries(k, t) for k, t in secs)

    # ---------- HS ----------
    hs_html = "".join(f"""
<tr class="{'chosen' if h['rank']==1 else ''}">
  <td class="rank">{h['rank']}</td>
  <td><code class="hs">{e(h['code_cn'])}</code><br><span class="muted">越南参考 {e(h.get('code_vn') or h.get('code_vn_alt') or '—')}</span></td>
  <td>{e(h['name_cn'])}</td>
  <td class="basis">{e(h['basis'])}</td>
  <td><span class="conf c{'H' if '高' in h['confidence'] else ('M' if '中' in h['confidence'] else 'L')}">{e(h['confidence'])}</span></td>
  <td><span class="badge {cls_of('待确认' if '候选' in h['status'] else h['status'])}">{e(h['status'])}</span></td>
</tr>""" for h in case["hs_candidates"])

    # ---------- identity ----------
    p_rows = [
        ("中文名称", p["name_cn"]), ("英文名称", p["name_en"]),
        ("CAS 号", p["cas"]), ("EC 号", p["ec"]), ("UN-CAS 索引号", p["un_cas_index"]),
        ("分子式", p["formula"]), ("等级 / 浓度", f"{p['grade']} / {p['concentration']}"),
        ("组成", p["composition"]), ("用途", p["use"]),
        ("包装 / 数量", f"{p['packaging']}；{p['quantity']}"),
        ("路线", f"{p['origin']} → {p['destination']}"), ("运输方式", p["transport_mode"]),
    ]
    p_html = "".join(f'<div class="pf"><span>{e(k)}</span><b>{e(v)}</b></div>' for k, v in p_rows)
    id_html = "".join(
        f'<div class="idc {cls_of(x["status"])}"><div class="idc-t">{e(x["item"])}</div><div class="idc-v">{e(x["value"])}</div>'
        f'<div class="idc-s">{e(x["source"])} <span class="badge {cls_of(x["status"])}">{e(x["status"])}</span></div></div>'
        for x in case["identity"]["checks"])

    # ---------- 运输对照 ----------
    def find(id_):
        for k, _ in secs:
            for x in case[k]:
                if x["id"] == id_:
                    return x
        return None

    tr1 = find("TR-01")
    tr_un = f"""
<div class="un-card">
  <div class="un-big">UN {e('2014')}</div>
  <div class="un-name">{e(tr1['finding'].split('；')[0])}</div>
  <div class="un-grid">
    <div><span>类别</span><b>5.1 氧化性物质</b></div>
    <div><span>次要危险</span><b>8 腐蚀性</b></div>
    <div><span>包装类别</span><b>II</b></div>
    <div><span>EmS</span><b>F-H / S-Q</b></div>
    <div><span>包装指令</span><b>P504 / IBC02</b></div>
    <div><span>大包装</span><b>禁止</b></div>
  </div>
  <p class="un-note">{e(tr1['finding'])}</p>
</div>"""

    # ---------- 文档 ----------
    cats = []
    for d in case["documents"]:
        if d["category"] not in cats:
            cats.append(d["category"])
    doc_html = ""
    for cat in cats:
        items = [d for d in case["documents"] if d["category"] == cat]
        cards = "".join(f"""
<div class="doc {'na' if cls_of(d['status'])=='na' else ''}">
  <div class="doc-h"><span class="doc-id">{e(d['id'])}</span><span class="badge {cls_of(d['status'])}">{e(d['status'])}</span></div>
  <div class="doc-n">{e(d['name'])}</div>
  <div class="doc-m"><span>{e(d['owner'])}</span><span>{e(d['timing'])}</span></div>
  <div class="doc-note">{e(d['note'])}</div>
</div>""" for d in items)
        doc_html += f'<div class="doc-cat"><h4>{e(cat)}</h4><div class="doc-grid">{cards}</div></div>'

    # ---------- 角色 ----------
    roles_html = "".join(f"""
<div class="role">
  <div class="role-h"><i>{['🏭','🏢','🚢','🧾','🔬'][i % 5]}</i>{e(r['role'])}</div>
  <ol>{''.join(f'<li>{e(x)}</li>' for x in r['items'])}</ol>
</div>""" for i, r in enumerate(case["roles"]))

    # ---------- 法规 ----------
    regs_html = "".join(f"""
<tr>
  <td><code>{e(r['id'])}</code></td>
  <td><span class="jur j{ 'cn' if r['jurisdiction']=='中国' else ('vn' if r['jurisdiction']=='越南' else 'int')}">{e(r['jurisdiction'])}</span></td>
  <td>{e(r['name'])}<div class="muted">{e(r['issuer'])} · {e(r['ref'])}</div></td>
  <td>{e(r['effective'])}</td>
  <td>{e(r['status'])}</td>
  <td>{e(r['verified_on'])}</td>
  <td><a href="{e(r['url'])}" target="_blank" rel="noopener">来源 ↗</a></td>
</tr>""" for r in case["regs"])

    # ---------- 时效 ----------
    tl_html = "".join(f"""
<div class="tl-item">
  <div class="tl-dot"></div>
  <div class="tl-t">{e(t['item'])}</div>
  <div class="tl-c">{e(t['what_changed'])}</div>
  <div class="tl-i">影响：{e(t['impact'])}</div>
  <div class="tl-m">核对状态：{e(t['checked'])} · {e(t['date'])}</div>
</div>""" for t in case["timeliness"])

    # ---------- 待确认 ----------
    oq_html = "".join(f"""
<div class="oq">
  <div class="oq-h"><span class="oq-id">{e(q['id'])}</span>{e(q['question'])}<span class="pill">未闭环</span></div>
  <div class="oq-b">
    <div><span>为什么不能确定</span>{e(q['why'])}</div>
    <div><span>责任方</span>{e(q['owner'])}</div>
    <div><span>解除后影响条目</span>{' '.join(f'<code>{e(b)}</code>' for b in q['blocks'])}</div>
  </div>
</div>""" for q in case["open_questions"])

    # ---------- 风险 ----------
    risks = [
        ("监管条件 G ≠ 必须办证", "G 是「定向」两用物项许可证。双氧水仅对缅甸/老挝/阿富汗需申请；越南出口无需，但要留存公告原文备查。", "ok"),
        ("危化品属性 ≠ 危险货物分类", "目录 903 回答「是不是危化品」；UN2014 / 5.1(8) / PG II 来自运输规则，两者独立成立、不能互推。", "ok"),
        ("越南法规已整体换版", "69/2025/QH15 自 2026-01-01 生效；24/25/26/2026 与 01/02/2026 自 2026-01-17 生效。113/2017 体系不再适用。", "tbd"),
        ("浓度口径必须用 w/w", "分类阈值按质量分数；边界浓度（近 20% / 60%）要特别确认，否则 UN 号与 PG 会错。", "ok"),
        ("稳定剂之外不得加料", "加入稳定剂/惰性化学品之外的成分，产品不再属于「过氧化氢水溶液」，须另行鉴定，HS 也可能变。", "ok"),
        ("空运 50% 存在禁运风险", "IATA 20–40% 与 >40–60% 条目许可不同，多家承运人禁运；默认走海运，改空运须取得承运人书面意见。", "tbd"),
        ("进口方资质与食品用途", "若属越南「有条件化学品」，进口方须持资格证；「食品级用途」会触发另一套准入。", "tbd"),
    ]
    risks_html = "".join(f'<div class="risk {c}"><b>{e(t)}</b><p>{e(d)}</p></div>' for t, d, c in risks)

    # ---------- 进度 ----------
    pct = round(tot_ok / tot * 100) if tot else 0

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>出口合规准备 · {e(p['name_cn'])} → {e(p['destination'])}（{e(p['transport_mode'])}）</title>
<style>
:root{{
  --navy:#14294b; --blue:#1f4e79; --blue2:#2e6da4; --ink:#1b2431; --muted:#6b7785;
  --line:#e3e9f0; --bg:#f4f7fb; --card:#ffffff; --ok:#1e7b34; --okbg:#e9f6ec;
  --tbd:#b45309; --tbdbg:#fff4e5; --ref:#1d4ed8; --refbg:#eaf0fe; --na:#6b7280; --nabg:#f1f3f5;
  --shadow:0 1px 2px rgba(16,32,56,.06),0 8px 24px rgba(16,32,56,.06);
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;font-family:"Segoe UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif;color:var(--ink);background:var(--bg);line-height:1.65;-webkit-font-smoothing:antialiased}}
a{{color:var(--blue2);text-decoration:none}}
code{{font-family:Consolas,"SFMono-Regular",monospace;font-size:.86em;background:#eef2f7;padding:.12em .38em;border-radius:4px}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 22px}}

/* ---------- Hero ---------- */
.hero{{background:radial-gradient(1200px 420px at 12% -10%,#2c5c96 0%,transparent 60%),linear-gradient(135deg,#0f2039 0%,#17365c 55%,#1d4b7d 100%);color:#fff;position:relative;overflow:hidden}}
.hero:after{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);background-size:44px 44px;pointer-events:none}}
.hero .wrap{{position:relative;z-index:1;padding-top:34px;padding-bottom:30px}}
.crumb{{font-size:12px;letter-spacing:.08em;color:#9fc0e6;text-transform:uppercase}}
h1{{margin:.35em 0 .2em;font-size:29px;line-height:1.3;font-weight:700;letter-spacing:.01em}}
.sub{{color:#c8dbf0;font-size:13.5px;max-width:900px}}
.hero-badges{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}}
.hb{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);padding:5px 11px;border-radius:999px;font-size:12px;color:#e6f0fa;backdrop-filter:blur(4px)}}
.hero-stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:22px}}
.hs-box{{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);border-radius:12px;padding:13px 15px}}
.hs-box b{{display:block;font-size:24px;line-height:1.2}}
.hs-box span{{font-size:11.5px;color:#a9c6e6;letter-spacing:.04em}}
.progress{{margin-top:16px;height:7px;border-radius:99px;background:rgba(255,255,255,.16);overflow:hidden}}
.progress i{{display:block;height:100%;background:linear-gradient(90deg,#5fd08b,#8fe3ad);width:{pct}%}}

/* ---------- Nav ---------- */
.nav{{position:sticky;top:0;z-index:30;background:rgba(255,255,255,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);box-shadow:0 2px 10px rgba(16,32,56,.04)}}
.nav .wrap{{display:flex;gap:4px;overflow-x:auto;padding-top:9px;padding-bottom:9px}}
.nav a{{white-space:nowrap;font-size:13px;color:#41505f;padding:6px 12px;border-radius:8px;font-weight:500}}
.nav a:hover{{background:#eef3f9;color:var(--blue)}}
.nav a.on{{background:var(--navy);color:#fff}}

/* ---------- Section ---------- */
section.blk{{padding:34px 0 8px}}
.sec-h h2{{margin:0;font-size:20px;letter-spacing:.01em}}
.sec-h h2 .n{{color:#9aa8b8;font-weight:600;margin-right:8px;font-size:15px}}
.sec-h p{{margin:4px 0 18px;color:var(--muted);font-size:13px;max-width:960px}}
.step-tag{{display:inline-block;font-size:11px;letter-spacing:.06em;color:#fff;background:var(--blue2);padding:2px 9px;border-radius:99px;margin-right:8px;vertical-align:2px}}

/* ---------- Cards ---------- */
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}}
.pad{{padding:20px 22px}}

/* identity */
.pf-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border-radius:12px;overflow:hidden;border:1px solid var(--line)}}
.pf{{background:#fff;padding:10px 14px}}
.pf span{{display:block;font-size:11px;color:var(--muted);letter-spacing:.03em}}
.pf b{{font-size:13.5px;font-weight:600}}
.id-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}}
.idc{{border:1px solid var(--line);border-radius:12px;padding:13px 15px;background:#fff;border-left:4px solid var(--na)}}
.idc.ok{{border-left-color:var(--ok)}} .idc.tbd{{border-left-color:var(--tbd)}} .idc.ref{{border-left-color:var(--ref)}}
.idc-t{{font-size:11.5px;color:var(--muted)}}
.idc-v{{font-weight:600;font-size:13.5px;margin:3px 0 6px}}
.idc-s{{font-size:11px;color:#8794a3;display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
.verdict{{margin-top:14px;background:var(--okbg);border:1px solid #cfe9d6;color:#14532d;border-radius:12px;padding:12px 16px;font-size:13.5px}}

/* HS */
table{{width:100%;border-collapse:separate;border-spacing:0;font-size:12.8px;background:#fff}}
th{{text-align:left;font-size:11.5px;letter-spacing:.04em;color:#5c6b7a;background:#eef3f9;padding:10px 12px;font-weight:600;border-bottom:1px solid var(--line)}}
td{{padding:12px;border-bottom:1px solid var(--line);vertical-align:top}}
tbody tr:hover{{background:#fafcfe}}
tr.chosen{{background:#f2f8f4}}
.rank{{font-weight:700;color:var(--blue2)}}
code.hs{{font-size:14px;font-weight:700;background:var(--navy);color:#fff;padding:2px 8px}}
.basis{{color:#33414f}}
.muted{{color:var(--muted);font-size:11px}}
.conf{{display:inline-block;padding:1px 9px;border-radius:99px;font-size:11.5px;font-weight:600}}
.cH{{background:var(--okbg);color:var(--ok)}} .cM{{background:var(--tbdbg);color:var(--tbd)}} .cL{{background:var(--nabg);color:var(--na)}}
.badge{{display:inline-block;padding:2px 9px;border-radius:99px;font-size:11px;font-weight:600;white-space:nowrap}}
.badge.ok{{background:var(--okbg);color:var(--ok)}}
.badge.tbd{{background:var(--tbdbg);color:var(--tbd)}}
.badge.ref{{background:var(--refbg);color:var(--ref)}}
.badge.na{{background:var(--nabg);color:var(--na)}}
.hs-note{{margin:14px 0 0;font-size:12px;color:var(--muted)}}

/* filters */
.filters{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 16px}}
.chip{{border:1px solid var(--line);background:#fff;color:#40505f;border-radius:99px;padding:7px 14px;font-size:12.5px;cursor:pointer;font-family:inherit;transition:.15s}}
.chip b{{font-weight:700;margin-left:4px;color:var(--blue2)}}
.chip:hover{{border-color:#b9cde3}}
.chip.active{{background:var(--navy);color:#fff;border-color:var(--navy)}}
.chip.active b{{color:#9fd3ff}}
.search{{margin-left:auto;display:flex;align-items:center;gap:8px;border:1px solid var(--line);background:#fff;border-radius:10px;padding:6px 12px}}
.search input{{border:0;outline:0;font-size:13px;width:220px;font-family:inherit;background:transparent}}

/* topic */
.topic-block{{margin-top:18px}}
.topic-block.hide{{display:none}}
.topic-h{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:10px}}
.topic-h h3{{margin:0;font-size:16.5px}}
.topic-h p{{margin:0;color:var(--muted);font-size:12px}}
.mini-stats{{margin-left:auto;display:flex;gap:8px}}
.ms{{font-size:11.5px;padding:2px 10px;border-radius:99px;font-weight:600}}
.ms.ok{{background:var(--okbg);color:var(--ok)}} .ms.tbd{{background:var(--tbdbg);color:var(--tbd)}} .ms.ref{{background:var(--refbg);color:var(--ref)}}

.item{{background:#fff;border:1px solid var(--line);border-radius:12px;margin-bottom:9px;overflow:hidden;transition:box-shadow .18s,border-color .18s}}
.item:hover{{border-color:#cfddeb}}
.item.open{{box-shadow:var(--shadow);border-color:#c3d6ea}}
.item.hide{{display:none}}
.item-h{{display:grid;grid-template-columns:76px 1fr auto 18px;gap:10px;align-items:center;padding:13px 16px;cursor:pointer}}
.idx{{font-size:11.5px;font-weight:700;color:#8593a3;font-family:Consolas,monospace}}
.it-title{{font-weight:600;font-size:13.8px}}
.caret{{color:#9aa8b8;transition:transform .2s}}
.item.open .caret{{transform:rotate(180deg)}}
.item-b{{display:none;padding:2px 18px 16px;border-top:1px dashed var(--line)}}
.item.open .item-b{{display:block}}
.finding{{font-size:13.4px;margin:12px 0 12px;color:#26323f}}
.kv{{display:grid;grid-template-columns:118px 1fr;gap:8px 14px;margin:0;font-size:12.8px}}
.kv dt{{color:var(--muted);font-size:12px;padding-top:1px}}
.kv dd{{margin:0;color:#33414f}}
.caution{{margin-top:12px;background:var(--tbdbg);border:1px solid #f6d9b0;color:#8a4b06;border-radius:9px;padding:9px 12px;font-size:12.5px}}
.tags{{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px}}
.tag.reg{{background:#eef3f9;border:1px solid #dbe6f1;color:#33506c;border-radius:7px;padding:3px 9px;font-size:11.5px}}
.tag.reg:hover{{background:#e2ecf7}}
.evidence{{background:var(--blue2);color:#fff;border-radius:7px;padding:3px 10px;font-size:11.5px;font-weight:600}}
.evidence:hover{{background:var(--blue)}}

/* UN */
.un-split{{display:grid;grid-template-columns:380px 1fr;gap:16px;align-items:start}}
.un-card{{background:linear-gradient(160deg,#12243f,#1d3f66);color:#fff;border-radius:14px;padding:20px;box-shadow:var(--shadow)}}
.un-big{{font-size:34px;font-weight:800;letter-spacing:.02em;line-height:1}}
.un-name{{font-size:12px;color:#b6cfe8;margin:8px 0 16px;font-family:Consolas,monospace}}
.un-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.un-grid div{{background:rgba(255,255,255,.08);border-radius:9px;padding:8px 10px}}
.un-grid span{{display:block;font-size:10.5px;color:#9dbad8;letter-spacing:.04em}}
.un-grid b{{font-size:13px}}
.un-note{{font-size:11.8px;color:#c3d7ea;margin:14px 0 0;line-height:1.6}}
.split-note{{background:#fff;border:1px dashed #c9d8e8;border-radius:12px;padding:14px 16px;font-size:12.6px;color:#33414f}}
.split-note h4{{margin:0 0 6px;font-size:13px;color:var(--blue)}}

/* docs */
.doc-cat{{margin-bottom:16px}}
.doc-cat h4{{margin:0 0 9px;font-size:13.5px;color:var(--blue);border-left:3px solid var(--blue2);padding-left:9px}}
.doc-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
.doc{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:12px 14px}}
.doc.na{{opacity:.62;background:#fafbfc}}
.doc-h{{display:flex;justify-content:space-between;align-items:center}}
.doc-id{{font-size:11px;font-family:Consolas,monospace;color:#8593a3;font-weight:700}}
.doc-n{{font-weight:600;font-size:13px;margin:7px 0 6px}}
.doc-m{{display:flex;justify-content:space-between;font-size:11px;color:var(--muted)}}
.doc-note{{font-size:11.5px;color:#51606f;margin-top:7px;padding-top:7px;border-top:1px dashed var(--line)}}

/* roles */
.roles{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
.role{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px 18px}}
.role-h{{font-weight:700;font-size:14px;display:flex;align-items:center;gap:9px;padding-bottom:9px;border-bottom:1px solid var(--line);margin-bottom:9px}}
.role ol{{margin:0;padding-left:19px;font-size:12.6px;color:#33414f}}
.role li{{margin:5px 0;padding-left:2px}}

/* timeline */
.tl{{position:relative;padding-left:22px}}
.tl:before{{content:"";position:absolute;left:6px;top:6px;bottom:6px;width:2px;background:linear-gradient(#cddbea,#e8eff7)}}
.tl-item{{position:relative;background:#fff;border:1px solid var(--line);border-radius:11px;padding:12px 16px;margin-bottom:10px}}
.tl-dot{{position:absolute;left:-22px;top:18px;width:11px;height:11px;border-radius:50%;background:#fff;border:2.5px solid var(--blue2)}}
.tl-t{{font-weight:700;font-size:13.4px}}
.tl-c{{font-size:12.4px;color:#41505f;margin:3px 0}}
.tl-i{{font-size:12px;color:#8a4b06;background:var(--tbdbg);border-radius:7px;padding:5px 9px;margin-top:6px;display:inline-block}}
.tl-m{{font-size:11px;color:var(--muted);margin-top:6px}}

/* open questions */
.oq{{background:#fff;border:1px solid #f2dcbd;border-left:4px solid var(--tbd);border-radius:11px;padding:13px 16px;margin-bottom:10px}}
.oq-h{{font-weight:600;font-size:13.5px;display:flex;gap:10px;align-items:flex-start}}
.oq-id{{background:var(--tbdbg);color:var(--tbd);font-family:Consolas,monospace;font-size:11px;font-weight:700;padding:1px 8px;border-radius:6px;flex:0 0 auto}}
.pill{{margin-left:auto;flex:0 0 auto;font-size:10.5px;background:#fde9cd;color:#8a4b06;border-radius:99px;padding:1px 9px}}
.oq-b{{display:grid;grid-template-columns:1fr 150px 200px;gap:12px;margin-top:9px;font-size:12.2px;color:#41505f}}
.oq-b span{{display:block;font-size:10.5px;color:var(--muted);letter-spacing:.03em;margin-bottom:2px}}

/* risks */
.risk-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:11px}}
.risk{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:13px 16px;border-top:3px solid var(--ok)}}
.risk.tbd{{border-top-color:var(--tbd)}}
.risk b{{font-size:13.2px}}
.risk p{{margin:5px 0 0;font-size:12.3px;color:#41505f}}

/* summary table wrap */
.tbl{{overflow:hidden;border-radius:13px;border:1px solid var(--line);box-shadow:var(--shadow)}}
.jur{{font-size:11px;font-weight:600;padding:1px 8px;border-radius:99px;white-space:nowrap}}
.jcn{{background:#fdecec;color:#a32222}} .jvn{{background:#fff4e0;color:#a85b00}} .jint{{background:#e8f0fe;color:#1d4ed8}}

/* note */
.disclaim{{background:#fff;border:1px solid var(--line);border-left:4px solid var(--tbd);border-radius:12px;padding:16px 20px;font-size:12.6px;color:#41505f}}
.disclaim b{{color:#8a4b06}}
.foot{{padding:30px 0 46px;color:#7c8a99;font-size:11.5px;text-align:center}}

@media (max-width:980px){{
  .hero-stats,.pf-grid,.id-grid,.doc-grid,.roles,.risk-grid{{grid-template-columns:1fr 1fr}}
  .un-split{{grid-template-columns:1fr}}
  .oq-b{{grid-template-columns:1fr}}
}}
@media (max-width:640px){{
  .hero-stats,.pf-grid,.id-grid,.doc-grid,.roles,.risk-grid{{grid-template-columns:1fr}}
  h1{{font-size:22px}}
  .item-h{{grid-template-columns:58px 1fr auto}}
  .caret{{display:none}}
}}
@media print{{
  .nav,.filters{{display:none}}
  .item-b{{display:block!important}}
  .item{{break-inside:avoid}}
}}
</style>
</head>
<body>

<header class="hero">
  <div class="wrap">
    <div class="crumb">EXPORT COMPLIANCE CHECKLIST · {e(meta['case_id'])} · 核验基准日 {e(as_of)}</div>
    <h1>{e(p['name_cn'])} 出口 {e(p['destination'])} · 合规准备清单</h1>
    <div class="sub">{e(meta['title'])}｜{e(p['concentration'])}｜{e(p['packaging'])}｜{e(p['transport_mode'])}｜用途：{e(p['use'])}</div>
    <div class="hero-badges">
      <span class="hb">CAS {e(p['cas'])}</span>
      <span class="hb">HS 候选 2847000000</span>
      <span class="hb">UN 2014 · 5.1(8) · PG II</span>
      <span class="hb">目录 903（&gt;8%）</span>
      <span class="hb">易制爆 6.1</span>
      <span class="hb">越南 2026 新规体系</span>
    </div>
    <div class="hero-stats">
      <div class="hs-box"><b>{tot}</b><span>核对条目</span></div>
      <div class="hs-box"><b>{tot_ok}</b><span>已核实（有官方来源）</span></div>
      <div class="hs-box"><b>{tot_tbd}</b><span>待确认 / 需专业确认</span></div>
      <div class="hs-box"><b>{len(case['regs'])}</b><span>法规来源（含 URL）</span></div>
    </div>
    <div class="progress" title="已核实占比 {pct}%"><i></i></div>
  </div>
</header>

<nav class="nav">
  <div class="wrap">
    <a href="#step1" class="on">① 身份与 HS</a>
    <a href="#step2">② 分主题清单</a>
    <a href="#transport">③ 运输危险属性</a>
    <a href="#docs">④ 单证</a>
    <a href="#roles">⑤ 角色分工</a>
    <a href="#regs">⑥ 法规索引</a>
    <a href="#timeline">⑦ 时效性</a>
    <a href="#openq">⑧ 待确认</a>
  </div>
</nav>

<main class="wrap">

<!-- ① 身份 -->
<section class="blk" id="step1">
  <div class="sec-h">
    <h2><span class="n">01</span><span class="step-tag">STEP 1</span>产品身份与 HS 候选确认</h2>
    <p>先锁定「是什么、什么浓度、什么用途、什么包装」，再判断监管。浓度口径（w/w）与稳定剂成分会改变后续几乎所有结论。</p>
  </div>
  <div class="card pad">
    <div class="pf-grid">{p_html}</div>
    <div class="verdict">✔ {e(case['identity']['verdict'])}</div>
    <div class="id-grid">{id_html}</div>
  </div>

  <div class="card tbl" style="margin-top:16px">
    <table>
      <thead><tr><th style="width:44px">#</th><th style="width:180px">中国 10 位 / 越南参考</th><th style="width:200px">商品名称</th><th>归类依据</th><th style="width:92px">置信度</th><th style="width:170px">状态</th></tr></thead>
      <tbody>{hs_html}</tbody>
    </table>
  </div>
  <p class="hs-note">※ HS 候选须经报关行或归类专业确认后，方可写入报关单与商业发票；越南子目以越南海关现行税则为准。</p>
</section>

<!-- ② 分主题 -->
<section class="blk" id="step2">
  <div class="sec-h">
    <h2><span class="n">02</span><span class="step-tag">STEP 2</span>合规检查清单（按主题筛选，点击展开）</h2>
    <p>共 {tot} 条，覆盖中国出口、目的国进口、运输、标签与包装四个主题。点击任意条目可展开查看法规来源、适用条件、生效时间与下一步动作。</p>
  </div>
  <div class="filters">
    {topic_chips()}
    <label class="search"><span>🔎</span><input id="q" type="search" placeholder="搜索条目 / 法规 / UN 号…"></label>
  </div>
  {entries_html}
</section>

<!-- ③ 运输 -->
<section class="blk" id="transport">
  <div class="sec-h">
    <h2><span class="n">03</span><span class="step-tag">STEP 3</span>危险货物运输属性（与危化品监管分开判定）</h2>
    <p>本节只回答「按危险货物怎么运」，不回答「是否属于危险化学品」。两者分属不同体系，结论不得互相推导。</p>
  </div>
  <div class="un-split">
    {tr_un}
    <div>
      <div class="split-note">
        <h4>为什么不能把两套体系混在一起</h4>
        <p>《危险化学品目录》是<b>安全生产与海关检验</b>的管理口径，条目 903 的门槛是「含量&gt;8%」；而 UN 号、类别与包装类别来自<b>运输规则</b>（IMDG / IATA / ADR），阈值是「8% / 20% / 60%」。同一个产品完全可能「是危险化学品但不是危险货物」，或相反。因此本页两套结论各自成表、各自挂法规。</p>
      </div>
      <div class="card tbl" style="margin-top:12px">
        <table>
          <thead><tr><th style="width:150px">浓度（H₂O₂ w/w）</th><th style="width:150px">UN 号</th><th style="width:110px">类别</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td>&lt; 8%</td><td>一般不作危险货物</td><td>—</td><td>但可能仍属其他管理范畴，需逐项核对</td></tr>
            <tr><td>8% ≤ x &lt; 20%</td><td>UN 2984</td><td>5.1 · PG III</td><td>稳定化后适用</td></tr>
            <tr class="chosen"><td>20% ≤ x ≤ 60%（本案例 50%）</td><td>UN 2014</td><td>5.1（8）· PG II</td><td>本案例适用；次要危险 8 腐蚀性</td></tr>
            <tr><td>&gt; 60%</td><td>UN 2014 条目（PG I）</td><td>5.1（8）· PG I</td><td>附属条目（是否含抑制剂）须 DG 顾问逐条确认</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<!-- ④ 单证 -->
<section class="blk" id="docs">
  <div class="sec-h">
    <h2><span class="n">04</span><span class="step-tag">STEP 4</span>单证准备</h2>
    <p>按「谁出、什么时候出、现在处于什么状态」归档。灰色卡片表示本案例不适用。</p>
  </div>
  {doc_html}
</section>

<!-- ⑤ 角色 -->
<section class="blk" id="roles">
  <div class="sec-h">
    <h2><span class="n">05</span><span class="step-tag">STEP 5</span>按角色分工</h2>
    <p>把事项落到具体责任人：出口方、进口方、承运方、报关行与第三方各做什么。</p>
  </div>
  <div class="roles">{roles_html}</div>
</section>

<!-- ⑥ 法规 -->
<section class="blk" id="regs">
  <div class="sec-h">
    <h2><span class="n">06</span>法规索引与来源</h2>
    <p>每条结论都能回到这里：法域、文号、生效日期、现行状态、核验日期与官方来源。</p>
  </div>
  <div class="card tbl">
    <table>
      <thead><tr><th style="width:52px">ID</th><th style="width:64px">法域</th><th>法规名称</th><th style="width:110px">生效日期</th><th style="width:150px">状态</th><th style="width:92px">核验日期</th><th style="width:70px">来源</th></tr></thead>
      <tbody>{regs_html}</tbody>
    </table>
  </div>
</section>

<!-- ⑦ 时效 -->
<section class="blk" id="timeline">
  <div class="sec-h">
    <h2><span class="n">07</span>法规时效性核查</h2>
    <p>本页回答：结论基于哪一版法规、是否刚换版、是否即将换版。越南化学品法规在 2026 年整体换版，是本案例最大的时效风险。</p>
  </div>
  <div class="tl">{tl_html}</div>
</section>

<!-- ⑧ 待确认 -->
<section class="blk" id="openq">
  <div class="sec-h">
    <h2><span class="n">08</span>仍需专业人员确认的问题</h2>
    <p>无法取得官方原文或需专业判断的，一律保留「待确认」，不作推定、不对客户作承诺性表述。每项写明责任方与闭环条件。</p>
  </div>
  {oq_html}
</section>

<!-- 风险 -->
<section class="blk">
  <div class="sec-h">
    <h2><span class="n">09</span>常见误区与风险提示</h2>
    <p>同类业务最容易出错的地方；逐条确认后才算真正完成「查出口要求」。</p>
  </div>
  <div class="risk-grid">{risks_html}</div>
</section>

<!-- 声明 -->
<section class="blk">
  <div class="disclaim">
    <p><b>使用边界：</b>{e(meta['assumption_notice'])}</p>
    <p><b>专业确认：</b>{e('；'.join(meta['scope_limits']))}</p>
    <p style="margin-bottom:0"><b>复核节奏：</b>若距核验基准日（{e(as_of)}）超过 90 天，或目的国法规换版、运输规则年更，须重新打开「法规索引」逐条复核后再对外使用。</p>
  </div>
</section>

<div class="foot">export-compliance-check · 由 case.json 生成 · {e(meta['case_id'])} · 核验基准日 {e(as_of)}</div>
</main>

<script>
(function(){{
  // 展开/收起
  document.querySelectorAll('.item-h').forEach(function(h){{
    function toggle(){{ const it=h.closest('.item'); it.classList.toggle('open'); h.setAttribute('aria-expanded', it.classList.contains('open')); }}
    h.addEventListener('click', toggle);
    h.addEventListener('keydown', function(ev){{ if(ev.key==='Enter'||ev.key===' '){{ ev.preventDefault(); toggle(); }} }});
  }});

  // 主题筛选
  const chips=document.querySelectorAll('.chip');
  const blocks=document.querySelectorAll('.topic-block');
  const q=document.getElementById('q');
  let filter='all';

  function apply(){{
    const kw=(q.value||'').trim().toLowerCase();
    blocks.forEach(function(b){{
      const topic=b.dataset.topic;
      const items=b.querySelectorAll('.item');
      let shown=0;
      items.forEach(function(it){{
        let ok;
        if(filter==='__tbd'){{
          ok = it.dataset.status==='tbd';
        }} else if(filter==='all'){{
          ok = true;
        }} else {{
          ok = (filter===topic);
        }}
        if(ok && kw) ok = (it.textContent||'').toLowerCase().indexOf(kw)>=0;
        it.classList.toggle('hide', !ok);
        if(ok) shown++;
      }});
      b.classList.toggle('hide', shown===0);
    }});
  }}
  chips.forEach(function(c){{
    c.addEventListener('click', function(){{
      chips.forEach(x=>x.classList.remove('active'));
      c.classList.add('active'); filter=c.dataset.filter; apply();
    }});
  }});
  q.addEventListener('input', apply);

  // 导航高亮
  const links=Array.from(document.querySelectorAll('.nav a'));
  const secs=links.map(a=>document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const io=new IntersectionObserver(function(es){{
    es.forEach(function(en){{
      if(en.isIntersecting){{
        links.forEach(a=>a.classList.remove('on'));
        const i=secs.indexOf(en.target);
        if(i>=0) links[i].classList.add('on');
      }}
    }});
  }},{{rootMargin:'-45% 0px -50% 0px'}});
  secs.forEach(s=>io.observe(s));
}})();
</script>
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--out", default=None)
    ap.add_argument("--checks", default=None)
    a = ap.parse_args(argv)
    case = json.loads(Path(a.case).read_text(encoding="utf-8"))
    chk = json.loads(Path(a.checks).read_text(encoding="utf-8")) if a.checks and Path(a.checks).exists() else None
    out = a.out or str(Path(a.case).parent / f"出口合规准备页_{case['meta']['case_id']}.html")
    Path(out).write_text(build(case, chk), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
