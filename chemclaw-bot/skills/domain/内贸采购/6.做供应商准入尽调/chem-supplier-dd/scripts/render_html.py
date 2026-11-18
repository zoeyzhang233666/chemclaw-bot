# -*- coding: utf-8 -*-
"""render_html.py — 把 data.json 渲染为单文件 HTML 底稿。

用法：
    python render_html.py <data.json> [输出.html]
默认输出到 data.json 同目录下的 <supplier>-底稿.html。

只依赖标准库；样式与交互脚本从 ../assets 读取并内联，产物可离线打开、可直接邮件发送。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ddlib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DEFAULT_UI = {
    "brand": "供应商准入尽调",
    "filter_all": "全部",
    "filter_risk": "聚焦风险",
    "filter_todo": "聚焦待核验",
    "filter_ok": "聚焦已核实",
    "pick_all": "全选模块",
    "download": "下载摘录 HTML",
    "print": "打印 / 导出 PDF",
    "toc": "目录",
    "pick_label": "纳入导出",
    "legend_title": "",
    "footer_note": "内部资料 · 未经许可不得外传",
}


def load_assets():
    css = open(os.path.join(ROOT, "assets", "dossier.css"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "assets", "dossier.js"), encoding="utf-8").read()
    return css, js


# ----------------------------------------------------------------- 区块渲染
def block_html(ctx, b, ui):
    t = b.get("type")

    if t == "verdict":
        side = "".join(f'<div class="row"><span>{L.esc(r.get("k"))}</span><b>{L.esc(r.get("v"))}</b></div>'
                       for r in b.get("rows", []))
        return f'''<div class="verdict">
      <div class="vmain">
        <div class="vk">{L.esc(b.get("kicker", "ADMISSION DECISION"))}</div>
        <div class="vv">{L.esc(b.get("headline"))}</div>
        <p>{L.frag(b.get("text"))}</p>
      </div>
      <div class="vside">{side}</div>
    </div>'''

    if t == "gates":
        gs = "".join(
            f'<div class="gate"><div class="g">{L.esc(g.get("code"))}</div><b>{L.esc(g.get("name"))}</b>'
            f'<p>{L.frag(g.get("text"))}</p></div>' for g in b.get("items", []))
        head = f'<h4>{L.esc(b["title"])}</h4>' if b.get("title") else ""
        return f'<div class="card">{head}<div class="gates">{gs}</div></div>'

    if t == "lead":
        muted = f'<p style="margin:10px 0 0" class="muted">{L.frag(b["muted"])}</p>' if b.get("muted") else ""
        return f'<div class="card"><div class="lead">{L.frag(b.get("text"))}{muted}</div></div>'

    if t == "note":
        tone = b.get("tone")
        cls = "note" + (f" {tone}" if tone else "")
        style = ' style="margin-top:12px"' if b.get("mt") else ""
        return f'<div class="{cls}"{style}>{L.frag(b.get("text"))}</div>'

    if t == "rows":
        return L.rows_html(ctx, b.get("items", []))

    if t == "table":
        body = L.table_html(
            ctx, b.get("columns", []), b.get("rows", []),
            tag_cols={int(k): v for k, v in (b.get("tag_cols") or {}).items()},
            pill_cols={int(k): v for k, v in (b.get("pill_cols") or {}).items()},
            evid_cols=b.get("evid_cols") or [],
        )
        if b.get("title"):
            foot = f'<div class="muted" style="margin-top:8px">{L.frag(b["foot"])}</div>' if b.get("foot") else ""
            note = f'<div class="note" style="margin-top:12px">{L.frag(b["note"])}</div>' if b.get("note") else ""
            return f'<div class="card"><h4>{L.esc(b["title"])}</h4>{body}{foot}{note}</div>'
        foot = f'<div class="muted" style="margin-top:8px">{L.frag(b["foot"])}</div>' if b.get("foot") else ""
        return body + foot

    if t == "certs":
        out = []
        for c in b.get("items", []):
            label, cls = L.cert_state(c.get("end"), ctx.as_of)
            tone = {"expired": "exp", "soon": "soon", "valid": "ok"}.get(cls, "ok")
            tr_cls = "tr-exp" if cls == "expired" else "tr"
            out.append(f'''<tr class="{tr_cls}">
          <td class="c mono">{int(c.get("no", 0)):02d}</td>
          <td>{L.esc(c.get("name"))}</td>
          <td class="mono">{L.esc(c.get("start"))} — {L.esc(c.get("end"))}</td>
          <td>{L.esc(c.get("scope"))}</td>
          <td>{L.esc(c.get("holder"))}</td>
          <td class="c"><span class="tg tg-{tone}">{label}</span></td>
        </tr>''')
        head = ('<th class="c">序号</th><th>资质名称</th><th>有效期限</th>'
                '<th>许可范围 / 适用产品</th><th>持有人</th><th class="c">状态</th>')
        return ('<div class="tblwrap"><table class="tbl"><thead><tr>' + head +
                "</tr></thead><tbody>" + "\n".join(out) + "</tbody></table></div>")

    if t in ("grid2", "grid3"):
        cards = []
        for c in b.get("cards", []):
            inner = L.frag(c.get("text", ""))
            if c.get("muted"):
                inner += f'<p style="margin:10px 0 0" class="muted">{L.frag(c["muted"])}</p>'
            if c.get("scores"):
                inner += f'<div class="scorelist">{L.score_html(c["scores"])}</div>'
            if c.get("table"):
                tb = c["table"]
                inner += L.table_html(ctx, tb.get("columns", []), tb.get("rows", []),
                                      tag_cols={int(k): v for k, v in (tb.get("tag_cols") or {}).items()})
            if c.get("chain"):
                inner += chain_html(c["chain"])
            for n in c.get("notes", []):
                inner += f'<div class="note" style="margin-bottom:10px">{L.frag(n)}</div>'
            cards.append(f'<div class="card" style="margin:0"><h4>{L.esc(c.get("h", ""))}</h4>{inner}</div>')
        return f'<div class="{t}" style="margin-top:12px">' + "".join(cards) + "</div>"

    if t == "kpis":
        items = "".join(
            f'<div class="kpi" style="margin:0"><div class="lab">{L.esc(k.get("label"))}</div>'
            f'<div class="val">{L.esc(k.get("value"))}</div>'
            f'<div class="note">{L.esc(k.get("note", ""))}</div></div>'
            for k in b.get("items", []))
        return f'<div class="{b.get("grid", "grid3")}">' + items + "</div>"

    if t == "risks":
        return "\n".join(L.risk_html(ctx, r) for r in b.get("items", []))

    if t == "matrix":
        head = f'<h4>{L.esc(b["title"])}</h4>' if b.get("title") else ""
        foot = f'<div class="muted" style="margin-top:10px">{L.frag(b["foot"])}</div>' if b.get("foot") else ""
        return f'<div class="card">{head}{L.matrix_html(ctx, b)}{foot}</div>'

    if t == "timeline":
        hot = b.get("hot_tags") or ["业绩", "资本开支"]
        lis = []
        for e in b.get("items", []):
            big = " big" if e.get("tag") in hot else ""
            lis.append(f'<div class="tli{big}"><div class="d">{L.esc(e.get("date"))}</div>'
                       f'<div class="t">{L.esc(e.get("text"))}<span class="tagx">{L.esc(e.get("tag", ""))}</span></div></div>')
        foot = (f'<div class="muted" style="border-top:1px dotted var(--line);padding-top:8px">{L.frag(b["foot"])}</div>'
                if b.get("foot") else "")
        return f'<div class="card"><div class="tl">' + "\n".join(lis) + f"</div>{foot}</div>"

    if t == "checklist":
        kind = b.get("kind", "mat")
        head = f'<h4>{L.esc(b["title"])}</h4>' if b.get("title") else ""
        n = len(b.get("items", []))
        return (f'<div class="card">{head}<div class="chkbox"><div class="prog"><span>完成度</span>'
                f'<div class="bar"><i></i></div><span class="num">0 / {n}</span></div>'
                f'<div class="chk">{L.checklist_html(b.get("items", []), kind)}</div></div></div>')

    if t == "chain":
        head = f'<h4>{L.esc(b["title"])}</h4>' if b.get("title") else ""
        return f'<div class="card">{head}{chain_html(b.get("items", []))}</div>'

    if t == "scores":
        foot = (f'<div class="muted" style="margin-top:10px;border-top:1px dotted var(--line);padding-top:8px">{L.frag(b["foot"])}</div>'
                if b.get("foot") else "")
        return (f'<div class="card"><h4>{L.esc(b.get("title", "维度评分"))}</h4>'
                f'<div class="scorelist">{L.score_html(b.get("items", []))}</div>{foot}</div>')

    if t == "evidence":
        head = f'<h4>{L.esc(b["title"])}</h4>' if b.get("title") else ""
        return f'<div class="card">{head}<div class="rows" style="border:0">{L.evidence_html(ctx)}</div></div>'

    if t == "html":
        return b.get("text", "")

    return ""


def chain_html(items):
    parts = []
    for i, it in enumerate(items):
        self_c = " self" if it.get("self") else ""
        parts.append(f'<div class="box{self_c}"><b>{L.esc(it.get("name"))}</b>'
                     f'<span>{L.esc(it.get("role", ""))}　{L.esc(it.get("code", ""))}</span></div>')
        if i < len(items) - 1:
            parts.append('<div class="arw">↓</div>')
    return '<div class="chain">' + "".join(parts) + "</div>"


# ----------------------------------------------------------------- 文档组装
def build(data):
    ctx = L.Ctx(data)
    meta = data.get("meta", {})
    hero = data.get("hero", {})
    seal = data.get("seal", {})
    ui = dict(DEFAULT_UI)
    ui.update(data.get("ui") or {})
    css, js = load_assets()
    js = js.replace("'供应商准入尽调底稿_山东海化_纯碱_摘录.html'",
                    "window.DD_NAME||'尽调底稿_摘录.html'")

    title = meta.get("page_title") or f'{meta.get("title", "供应商准入尽调底稿")} · {meta.get("target", "")} · {meta.get("product", "")}'

    kpis = "".join(
        f'<div class="kpi {k.get("tone", "")}"><div class="lab">{L.esc(k.get("label"))}</div>'
        f'<div class="val">{L.esc(k.get("value"))}</div>'
        f'<div class="note">{L.esc(k.get("note", ""))}</div></div>'
        for k in data.get("kpis", []))

    nav = "".join(
        f'<a href="#{L.esc(n["id"])}"><i>{i:02d}</i>{L.esc(n.get("title"))}</a>'
        for i, n in enumerate(data.get("nav", []), 1))

    legend = "".join(
        f'<div>{ctx.pill(k)}{L.esc(v.get("desc", ""))}</div>'
        for k, v in ctx.status.items())

    scores = data.get("verdict", {}).get("scores", [])
    avg = round(sum(float(s.get("value", 0)) for s in scores) / len(scores)) if scores else 0
    donut = data.get("donut", {})
    donut_value = donut.get("value", avg)
    donut_sub = donut.get("sub", "")

    sections = "\n".join(
        section_html(ctx, sec, ui) for sec in data.get("sections", []))

    chips = "".join(
        f'<span class="mchip">{L.esc(c.get("k"))} <b>{L.esc(c.get("v"))}</b></span>'
        for c in (hero.get("chips") or []))

    exp_name = meta.get("export_name") or f'{meta.get("title", "尽调底稿")}_{meta.get("target", "")}.html'

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{L.esc(title)}</title>
<style id="css">{css}</style>
</head>
<body>

<div class="topbar"><div class="wrap">
  <div class="tb-l"><span class="tb-dot"></span><b>{L.esc(ui["brand"])}</b><span>·　{L.esc(meta.get("doc_no", ""))}</span></div>
  <div class="tb-mid">
    <button class="fbtn on" data-f="all">{L.esc(ui["filter_all"])}</button>
    <button class="fbtn" data-f="risk">{L.esc(ui["filter_risk"])}</button>
    <button class="fbtn" data-f="todo">{L.esc(ui["filter_todo"])}</button>
    <button class="fbtn" data-f="ok">{L.esc(ui["filter_ok"])}</button>
  </div>
  <div class="tb-r">
    <button class="btn" id="pickall">{L.esc(ui["pick_all"])}</button>
    <button class="btn" id="dl">{L.esc(ui["download"])}</button>
    <button class="btn btn-pri" id="prt">{L.esc(ui["print"])}</button>
  </div>
</div></div>

<header class="hero"><div class="wrap">
  <div>
    <span class="eyebrow">{L.esc(hero.get("eyebrow", ""))}</span>
    <h1>{L.esc(hero.get("h1", meta.get("title", "")))}<small>{L.esc(hero.get("h1_sub", ""))}</small></h1>
    <div class="target">{L.esc(hero.get("target", meta.get("target", "")))}<span>{L.esc(hero.get("target_sub", ""))}</span></div>
    <div class="scene">{hero.get("scene", "")}</div>
    <div class="hero-meta">{chips}</div>
  </div>
  <div class="seal">
    <div class="k">{L.esc(seal.get("kicker", "ADMISSION"))}</div>
    <div class="v">{L.esc(seal.get("value", ""))}</div>
    <div class="d">{L.esc(seal.get("line1", ""))}</div>
    <div class="d">{L.esc(seal.get("line2", meta.get("as_of", "")))}</div>
  </div>
</div></header>

<div class="wrap"><div class="kpis">{kpis}</div></div>

<div class="wrap"><div class="layout">
  <aside class="rail">
    <div class="rt">{L.esc(ui["toc"])}</div>
    <nav>{nav}</nav>
    <div class="sep"></div>
    <div class="donut-box">
      <div class="donut"><b>{L.esc(donut_value)}<span>%</span></b></div>
      <div class="t">{L.esc(donut.get("label", "证据完备度"))}<br><span class="muted">{L.esc(donut_sub)}</span></div>
    </div>
    <div class="legend">{legend}</div>
  </aside>

  <main>
  <div class="exporthead">
    <h1>{L.esc(meta.get("title", ""))} · {L.esc(meta.get("target", ""))} · {L.esc(meta.get("product", ""))}</h1>
    <div class="m">底稿编号 {L.esc(meta.get("doc_no", ""))}　数据截止 {L.esc(meta.get("as_of", ""))}　编制：{L.esc(meta.get("author", ""))}　复核：{L.esc(meta.get("reviewer", ""))}　{L.esc(meta.get("export_note", "本摘录仅供内部采购准入使用"))}</div>
  </div>

{sections}

  </main>
</div></div>

<footer><div class="wrap">
  <div><b>{L.esc(meta.get("title", ""))} · {L.esc(meta.get("target", ""))} · {L.esc(meta.get("product", ""))}</b><br>
    底稿编号 {L.esc(meta.get("doc_no", ""))}　版本 {L.esc(meta.get("version", ""))}　数据截止 {L.esc(meta.get("as_of", ""))}</div>
  <div style="text-align:right">编制：{L.esc(meta.get("author", ""))}　复核：{L.esc(meta.get("reviewer", ""))}<br>
    {L.esc(ui["footer_note"])}</div>
</div></footer>

<script>window.DD_NAME={json.dumps(exp_name, ensure_ascii=False)};{js}</script>
</body></html>'''


def section_html(ctx, sec, ui):
    """section 渲染（放在 build 之后定义以避免前向引用歧义）。"""
    blocks = "\n".join(block_html(ctx, b, ui) for b in sec.get("blocks", []))
    no = L.esc(sec.get("no", ""))
    return f'''  <section id="{L.esc(sec.get("id"))}">
    <div class="sechead"><div class="secno">{no}</div>
      <div class="tt"><h2>{L.esc(sec.get("title"))}</h2><div class="sub">{L.esc(sec.get("sub", ""))}</div></div>
      <label class="pick"><input type="checkbox" checked>{L.esc(ui.get("pick_label", "纳入导出"))}</label>
    </div>
{blocks}
  </section>'''


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = sys.argv[1]
    data = json.load(open(src, encoding="utf-8"))
    html_doc = build(data)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"html -> {out}  ({os.path.getsize(out):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
