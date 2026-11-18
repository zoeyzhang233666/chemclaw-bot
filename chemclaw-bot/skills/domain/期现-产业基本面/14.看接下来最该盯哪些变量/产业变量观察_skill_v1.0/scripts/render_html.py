# -*- coding: utf-8 -*-
"""
通用产业变量观察看板 —— HTML 渲染器
输入：符合 contract.py 契约的 payload(dict)
输出：自包含单文件 HTML（无外部 CDN 依赖，可离线打开）

设计原则
  1. 数据缺失显示为灰色「数据缺失」标签，不隐藏、不猜数
  2. 三个视图切换：变量卡片 / 事件时间线 / 产业状态快照
  3. 支持分类筛选、重要性排序、自选收藏(localStorage)、全文检索
  4. 每张卡片含：当前状态、近期变化、历史位置、关注原因、传导机制、
     已知事件、可核对数据、验证条件(确认/否证/失效)、来源与下次可观测时间
"""
from __future__ import annotations

import html
import json
import re
from datetime import date

from contract import CATEGORIES, CAT_COLOR, NODATA, validate

E = html.escape


def _esc(x) -> str:
    return E(str(x)) if x is not None else ""


def _split_list(text: str) -> list[str]:
    """把带 ①②③ 或 ；; 分隔的长文本拆成条目，便于渲染为列表。"""
    if not text:
        return []
    parts = re.split(r"(?=[①-⑳])", str(text))
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        parts = [p.strip() for p in re.split(r"[；;]", str(text)) if p.strip()]
    return parts


def _stars(n: int, color: str = "#c99427") -> str:
    n = max(0, min(5, int(n or 0)))
    return (
        '<span class="stars" title="%d/5">' % n
        + "".join('<i class="on" style="--c:%s"></i>' % color if i < n else '<i></i>' for i in range(5))
        + "</span>"
    )


# ---------------------------------------------------------------------------
# 组件
# ---------------------------------------------------------------------------
def _html_head(payload: dict) -> str:
    meta = payload["meta"]
    title = f'{meta["commodity"]} · 产业变量观察看板'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
:root{{
  --bg:#0f1420; --bg2:#151c2b; --card:#1a2233; --card2:#1f2940;
  --line:#2a3650; --line2:#37456a;
  --txt:#e8edf7; --txt2:#9fb0cc; --txt3:#6d7f9e;
  --accent:#4f9cf9; --accent2:#7c5cd6;
  --up:#e0693a; --down:#1a9b8a; --warn:#c99427;
  --radius:14px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:radial-gradient(1200px 700px at 12% -10%, #1b2540 0%, transparent 55%),
             radial-gradient(900px 600px at 92% 0%, #201a35 0%, transparent 50%),
             var(--bg);
  color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif;
  font-size:14px; line-height:1.62; padding:0 0 60px; min-height:100vh;
}}
.wrap{{max-width:1360px;margin:0 auto;padding:0 24px}}

/* ---------- 顶部 ---------- */
header{{padding:34px 0 20px;border-bottom:1px solid var(--line)}}
.kicker{{font-size:12px;letter-spacing:.22em;color:var(--accent);text-transform:uppercase;font-weight:600}}
h1{{font-size:30px;line-height:1.25;margin:10px 0 6px;font-weight:700;letter-spacing:.01em}}
h1 .thin{{font-weight:400;color:var(--txt2);font-size:20px}}
.sub{{color:var(--txt2);font-size:13.5px}}
.metaline{{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}}
.chip{{background:var(--bg2);border:1px solid var(--line);border-radius:999px;padding:5px 13px;font-size:12.5px;color:var(--txt2)}}
.chip b{{color:var(--txt);font-weight:600}}
.chip.accent{{border-color:rgba(79,156,249,.45);color:#a9cdfc}}

/* ---------- 切换与工具条 ---------- */
.toolbar{{position:sticky;top:0;z-index:30;background:rgba(15,20,32,.93);backdrop-filter:blur(12px);
  border-bottom:1px solid var(--line);padding:14px 0;margin-bottom:26px}}
.tbrow{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}}
.tabs{{display:flex;gap:6px;background:var(--bg2);padding:4px;border-radius:11px;border:1px solid var(--line)}}
.tab{{border:0;background:transparent;color:var(--txt2);padding:8px 18px;border-radius:8px;cursor:pointer;
  font-size:13.5px;font-weight:500;transition:.18s;font-family:inherit}}
.tab:hover{{color:var(--txt)}}
.tab.active{{background:linear-gradient(135deg,#2f6fd0,#5a49b8);color:#fff;box-shadow:0 4px 14px rgba(79,156,249,.25)}}
.filters{{display:flex;flex-wrap:wrap;gap:7px;align-items:center}}
.fbtn{{border:1px solid var(--line);background:var(--bg2);color:var(--txt2);padding:6px 13px;border-radius:8px;
  cursor:pointer;font-size:12.5px;font-family:inherit;transition:.15s;display:flex;align-items:center;gap:6px}}
.fbtn:hover{{border-color:var(--line2);color:var(--txt)}}
.fbtn.active{{background:var(--card2);border-color:var(--accent);color:#fff}}
.fbtn .dot{{width:7px;height:7px;border-radius:50%;background:var(--c,#888)}}
.search{{background:var(--bg2);border:1px solid var(--line);border-radius:9px;color:var(--txt);
  padding:8px 14px;font-size:13px;font-family:inherit;width:220px;outline:none}}
.search:focus{{border-color:var(--accent)}}
.count{{font-size:12px;color:var(--txt3)}}

/* ---------- 概览条 ---------- */
.overview{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:30px}}
.ov{{background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);
  border-radius:var(--radius);padding:16px 18px;position:relative;overflow:hidden}}
.ov::after{{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--c,var(--accent))}}
.ov .k{{font-size:12px;color:var(--txt3);letter-spacing:.04em}}
.ov .v{{font-size:22px;font-weight:700;margin:6px 0 2px;letter-spacing:-.01em}}
.ov .n{{font-size:11.5px;color:var(--txt2)}}
.flag{{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:5px;margin-left:6px;
  vertical-align:middle;font-weight:600}}
.flag.low{{background:rgba(26,155,138,.18);color:#5fd8c6;border:1px solid rgba(26,155,138,.4)}}
.flag.high{{background:rgba(224,105,58,.18);color:#f0956f;border:1px solid rgba(224,105,58,.4)}}

/* ---------- 变量卡片 ---------- */
.cards{{display:grid;grid-template-columns:1fr;gap:20px}}
.card{{background:linear-gradient(170deg,var(--card) 0%,#182030 100%);border:1px solid var(--line);
  border-radius:16px;overflow:hidden;transition:.2s;position:relative}}
.card:hover{{border-color:var(--line2)}}
.card.hidden{{display:none}}
.card-head{{padding:20px 24px 16px;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:flex-start;
  background:linear-gradient(90deg,rgba(255,255,255,.022),transparent)}}
.rank{{flex:0 0 auto;width:46px;height:46px;border-radius:12px;display:grid;place-items:center;
  font-size:19px;font-weight:800;color:#fff;background:linear-gradient(140deg,var(--c),#2a3350);
  box-shadow:0 6px 18px rgba(0,0,0,.3)}}
.card-title{{flex:1;min-width:0}}
.card-title h3{{font-size:17.5px;font-weight:650;line-height:1.4;margin-bottom:8px}}
.tags{{display:flex;flex-wrap:wrap;gap:7px;align-items:center}}
.tag{{font-size:11px;padding:2px 9px;border-radius:6px;background:var(--bg2);color:var(--txt2);border:1px solid var(--line)}}
.tag.cat{{background:color-mix(in srgb,var(--c) 18%,transparent);color:var(--c);border-color:color-mix(in srgb,var(--c) 45%,transparent);font-weight:600}}
.tag.next{{background:rgba(79,156,249,.13);color:#8fc2fb;border-color:rgba(79,156,249,.4)}}
.starbtn{{border:1px solid var(--line);background:var(--bg2);color:var(--txt3);width:34px;height:34px;
  border-radius:9px;cursor:pointer;font-size:16px;line-height:1;transition:.15s}}
.starbtn.on{{color:#f5c451;border-color:rgba(245,196,81,.5);background:rgba(245,196,81,.12)}}
.card-body{{padding:20px 24px}}

.block{{margin-bottom:18px}}
.block:last-child{{margin-bottom:0}}
.block h4{{font-size:11.5px;letter-spacing:.1em;color:var(--txt3);font-weight:700;text-transform:uppercase;
  margin-bottom:8px;display:flex;align-items:center;gap:7px}}
.block h4::before{{content:"";width:3px;height:12px;border-radius:2px;background:var(--c,var(--accent))}}
.block p, .block li{{color:#cfd9ea;font-size:13.5px}}
.block ul{{list-style:none;display:grid;gap:5px}}
.block ul li{{padding-left:14px;position:relative}}
.block ul li::before{{content:"";position:absolute;left:0;top:.62em;width:5px;height:5px;border-radius:50%;
  background:var(--c,var(--accent));opacity:.75}}

.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:900px){{.grid2{{grid-template-columns:1fr}}}}

.trio{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
@media(max-width:820px){{.trio{{grid-template-columns:1fr}}}}
.tri{{background:var(--bg2);border:1px solid var(--line);border-left:3px solid var(--tc);
  border-radius:10px;padding:12px 14px}}
.tri .lbl{{font-size:11px;font-weight:700;letter-spacing:.04em;color:var(--tc);margin-bottom:5px}}
.tri .txt{{font-size:12.8px;color:#cbd6e8}}
.tri.yes{{--tc:#2fbf8f}} .tri.no{{--tc:#e0693a}} .tri.inv{{--tc:#c99427}}

.src{{background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:12px 14px;
  font-size:12.3px;color:var(--txt2)}}
.src b{{color:var(--txt);font-weight:600}}
.src .row{{display:flex;gap:8px;margin-bottom:4px}}
.src .row:last-child{{margin-bottom:0}}
.src .kk{{flex:0 0 96px;color:var(--txt3)}}

.gapbox{{margin-top:12px;border:1px dashed rgba(201,148,39,.45);background:rgba(201,148,39,.07);
  border-radius:10px;padding:10px 13px;font-size:12.3px;color:#dcbf7e}}
.gapbox b{{color:var(--warn)}}

/* 迷你折线 */
.mini{{background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-top:8px}}
.mini .mt{{font-size:11.5px;color:var(--txt3);margin-bottom:6px}}
.mini svg{{display:block;width:100%;height:auto}}
.mini .mnote{{font-size:11px;color:var(--txt3);margin-top:5px;line-height:1.5}}

/* ---------- 时间线 ---------- */
.timeline{{position:relative;padding-left:28px}}
.timeline::before{{content:"";position:absolute;left:8px;top:6px;bottom:6px;width:2px;
  background:linear-gradient(180deg,var(--accent),var(--accent2),transparent)}}
.ev{{position:relative;margin-bottom:16px;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:15px 18px;transition:.18s}}
.ev:hover{{border-color:var(--line2);transform:translateX(2px)}}
.ev::before{{content:"";position:absolute;left:-27px;top:20px;width:11px;height:11px;border-radius:50%;
  background:var(--c,var(--accent));border:2px solid var(--bg);box-shadow:0 0 0 3px color-mix(in srgb,var(--c) 25%,transparent)}}
.ev.past{{opacity:.62}}
.ev-top{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:6px}}
.ev-date{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13px;font-weight:700;color:var(--c)}}
.ev-title{{font-size:14.5px;font-weight:600;color:var(--txt);margin-bottom:5px}}
.ev-meta{{font-size:12.3px;color:var(--txt2)}}
.ev-meta b{{color:var(--txt);font-weight:600}}
.kind{{font-size:10.5px;padding:1px 8px;border-radius:5px;border:1px solid var(--line2);color:var(--txt2);background:var(--bg2)}}
.kind.fixed{{border-color:rgba(47,191,143,.5);color:#5fd8b0;background:rgba(47,191,143,.1)}}
.kind.cond{{border-color:rgba(201,148,39,.5);color:#dcbf7e;background:rgba(201,148,39,.1)}}
.kind.periodic{{border-color:rgba(79,156,249,.5);color:#8fc2fb;background:rgba(79,156,249,.1)}}

/* ---------- 快照 ---------- */
.snaptable{{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;
  background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
.snaptable th{{text-align:left;padding:11px 14px;background:var(--bg2);color:var(--txt3);
  font-size:11.5px;font-weight:700;letter-spacing:.05em;border-bottom:1px solid var(--line);white-space:nowrap}}
.snaptable td{{padding:12px 14px;border-bottom:1px solid rgba(42,54,80,.6);vertical-align:top;color:#cfd9ea}}
.snaptable tr:last-child td{{border-bottom:0}}
.snaptable tr:hover td{{background:rgba(255,255,255,.018)}}
.snaptable td.ind{{font-weight:600;color:var(--txt);min-width:150px}}
.snaptable td.val{{font-family:ui-monospace,Consolas,monospace;color:#a9cdfc;font-weight:600;white-space:nowrap}}
.scope{{font-size:11.5px;color:var(--txt3)}}

/* 其它区块 */
.section{{margin-top:38px}}
.section > h2{{font-size:19px;font-weight:650;margin-bottom:6px;display:flex;align-items:center;gap:10px}}
.section > h2 .num{{font-size:12px;color:var(--accent);font-family:ui-monospace,Consolas,monospace}}
.section > .desc{{color:var(--txt2);font-size:13px;margin-bottom:16px;max-width:980px}}
.cand{{display:grid;gap:10px}}
.candrow{{display:grid;grid-template-columns:26px 1fr auto;gap:12px;background:var(--card);
  border:1px solid var(--line);border-radius:11px;padding:13px 16px;align-items:start}}
.candrow.sel{{border-color:rgba(47,191,143,.35);background:linear-gradient(90deg,rgba(47,191,143,.07),var(--card))}}
.candrow .mk{{width:22px;height:22px;border-radius:6px;display:grid;place-items:center;font-size:12px;font-weight:700}}
.candrow.sel .mk{{background:rgba(47,191,143,.2);color:#4fd6a9}}
.candrow:not(.sel) .mk{{background:rgba(109,127,158,.15);color:var(--txt3)}}
.candrow .nm{{font-weight:600;font-size:13.5px}}
.candrow .rs{{font-size:12.5px;color:var(--txt2);margin-top:3px}}
.candrow .vf{{font-size:11px;color:var(--txt3);white-space:nowrap}}

.secondary{{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}}
.seccard{{background:var(--bg2);border:1px solid var(--line);border-radius:11px;padding:14px 16px}}
.seccard .nm{{font-weight:600;font-size:13.5px;margin-bottom:6px}}
.seccard .rs{{font-size:12.5px;color:var(--txt2)}}

.gaptable{{width:100%;border-collapse:separate;border-spacing:0;font-size:12.6px;background:var(--card);
  border:1px solid var(--line);border-radius:12px;overflow:hidden}}
.gaptable th{{text-align:left;padding:10px 14px;background:var(--bg2);color:var(--txt3);font-size:11.5px;
  border-bottom:1px solid var(--line)}}
.gaptable td{{padding:11px 14px;border-bottom:1px solid rgba(42,54,80,.6);color:#cfd9ea;vertical-align:top}}
.gaptable tr:last-child td{{border-bottom:0}}
.gaptable td.item{{font-weight:600;color:var(--txt);white-space:nowrap}}

.weekcal{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.wk{{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:13px 15px;
  border-top:2px solid var(--accent)}}
.wk .w{{font-size:12px;color:var(--accent);font-weight:700;margin-bottom:4px}}
.wk .t{{font-size:12.8px;color:#cfd9ea}}
.wk .s{{font-size:11px;color:var(--txt3);margin-top:5px}}

footer{{margin-top:44px;padding-top:20px;border-top:1px solid var(--line);color:var(--txt3);font-size:11.8px;line-height:1.85}}
footer b{{color:var(--txt2)}}

.view{{display:none}} .view.active{{display:block}}
.empty{{color:var(--txt3);text-align:center;padding:40px;font-size:13px}}

::-webkit-scrollbar{{width:10px;height:10px}}
::-webkit-scrollbar-thumb{{background:#2c3852;border-radius:6px}}
::-webkit-scrollbar-track{{background:transparent}}
@media print{{
  .toolbar{{position:static}} .card{{break-inside:avoid}} .view{{display:block!important}}
  body{{background:#fff;color:#111}}
}}
</style>
</head>
<body>
"""


def _header(payload: dict) -> str:
    m = payload["meta"]
    return f"""<header>
<div class="wrap">
  <div class="kicker">期现 · 产业基本面 · 变量观察</div>
  <h1>{_esc(m['commodity'])} 未来最该盯什么<span class="thin"> · 产业变量观察看板</span></h1>
  <div class="sub">关注周期：{_esc(m['cycle'])}　|　数据截止：{_esc(payload.get('as_of', m.get('as_of','')))}</div>
  <div class="metaline">
    <span class="chip accent">合约锚点　<b>{_esc(m['contract_focus'])}</b></span>
    <span class="chip">重点区域　<b>{_esc(m['region_focus'])}</b></span>
    <span class="chip">口径　<b>{_esc(m['price_basis'])}</b></span>
    <span class="chip">研究定位　<b>{_esc(m['research_position'])}</b></span>
  </div>
</div>
</header>"""


def _overview(payload: dict) -> str:
    vs = payload["variables"]
    n_cat = len({v["cat"] for v in vs})
    events_up = len([e for e in payload["events"] if e["date"] >= payload.get("as_of", "")])
    gaps = len(payload["gaps"])
    n_sel = len([c for c in payload["candidates"] if c["selected"]])
    n_all = len(payload["candidates"])
    items = [
        ("入选变量", f"{len(vs)}", f"覆盖 {n_cat} 类：{' / '.join(sorted({v['cat'] for v in vs}))}", "#4f9cf9"),
        ("候选筛选", f"{n_sel}/{n_all}", "入选 / 全部候选，其余降为二级观察", "#7c5cd6"),
        ("未来已知节点", f"{events_up}", "10-20 至 11-20 区间内的公开事件与数据发布", "#1a9b8a"),
        ("数据缺口", f"{gaps}", "明确限制与替代口径，均已标注", "#c99427"),
    ]
    out = ['<div class="overview">']
    for k, v, n, c in items:
        out.append(f'<div class="ov" style="--c:{c}"><div class="k">{_esc(k)}</div>'
                   f'<div class="v">{_esc(v)}</div><div class="n">{_esc(n)}</div></div>')
    out.append("</div>")
    return "".join(out)


def _toolbar(payload: dict) -> str:
    cats = []
    seen = set()
    for v in payload["variables"]:
        if v["cat"] not in seen:
            seen.add(v["cat"])
            cats.append(v["cat"])
    fbtns = ['<button class="fbtn active" data-cat="all">全部</button>',
             '<button class="fbtn" data-cat="fav" title="仅显示已收藏">★ 自选</button>']
    for c in cats:
        fbtns.append(f'<button class="fbtn" data-cat="{E(c)}"><span class="dot" style="--c:{CAT_COLOR.get(c,"#888")}"></span>{E(c)}</button>')
    return f"""<div class="toolbar"><div class="wrap"><div class="tbrow">
  <div class="tabs">
    <button class="tab active" data-view="cards">变量卡片</button>
    <button class="tab" data-view="timeline">事件时间线</button>
    <button class="tab" data-view="snapshot">产业状态快照</button>
  </div>
  <div class="filters">{''.join(fbtns)}</div>
  <input class="search" id="q" type="search" placeholder="搜索变量 / 事件 / 指标…">
  <span class="count" id="count"></span>
</div></div></div>"""


def _sparkline(points: list, color: str = "#4f9cf9") -> str:
    """极简内联 SVG 折线（无依赖）。"""
    vals = [p[1] for p in points]
    if len(vals) < 2:
        return ""
    w, h, pad = 460, 120, 12
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    n = len(vals)
    xs = [pad + i * (w - 2 * pad) / (n - 1) for i in range(n)]
    ys = [h - pad - (v - lo) / rng * (h - 2 * pad) for v in vals]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{color}" stroke="#151c2b" stroke-width="1.5"/>'
        f'<text x="{x:.1f}" y="{y-9:.1f}" font-size="9.5" fill="#9fb0cc" text-anchor="middle">{vals[i]:g}</text>'
        for i, (x, y) in enumerate(zip(xs, ys))
    )
    # 面积填充：起点→各折线点→闭合到基线
    line_d = " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"M{xs[0]:.1f},{h - pad} L{line_d} L{xs[-1]:.1f},{h - pad} Z"
    gid = f"g{abs(hash(path)) % 99999}"
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img">'
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{color}" stop-opacity=".28"/>'
            f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="{area}" fill="url(#{gid})"/>'
            f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>{dots}</svg>')


def _card(v: dict, payload: dict) -> str:
    c = CAT_COLOR.get(v["cat"], "#4f9cf9")
    key_data = _split_list(v["key_data"])
    mechanism = v["mechanism"]
    chart_key = (payload.get("charts") or {}).get(v.get("chart") or "", None)
    if chart_key is None:
        charts = payload.get("charts", {}) or {}
        auto = {"库存": "port_inventory", "价差": "basis", "供给": "price_futures",
                "需求": "price_futures"}.get(v["cat"])
        chart_key = charts.get(auto) if auto else None

    chart_html = ""
    if chart_key:
        pts = chart_key["points"]
        chart_html = (
            f'<div class="mini"><div class="mt">{_esc(chart_key["title"])}</div>'
            f'{_sparkline(pts, c)}'
            f'<div class="mnote">{_esc(chart_key.get("note",""))}</div></div>'
        )

    return f"""<article class="card" data-cat="{E(v['cat'])}" data-vid="{E(v['vid'])}" data-search="{E((v['name']+' '+v['current']+' '+v['why']).lower())}">
  <div class="card-head" style="--c:{c}">
    <div class="rank" style="--c:{c}">#{v['rank']}</div>
    <div class="card-title">
      <h3>{_esc(v['name'])}</h3>
      <div class="tags">
        <span class="tag cat" style="--c:{c}">{_esc(v['cat'])}</span>
        <span class="tag">重要性 {_stars(v['importance'])}</span>
        <span class="tag">可验证性 {_stars(v['verifiability'], '#4f9cf9')}</span>
        <span class="tag">紧迫度 {_stars(v['urgency'], '#1a9b8a')}</span>
        <span class="tag next">下次观测：{_esc(v['next_date'])}</span>
        <span class="tag">{_esc(v['horizon'])}</span>
      </div>
    </div>
    <button class="starbtn" data-fav="{E(v['vid'])}" title="加入自选" aria-label="收藏">☆</button>
  </div>
  <div class="card-body" style="--c:{c}">
    <div class="grid2">
      <div>
        <div class="block"><h4>当前状态</h4><p>{_esc(v['current'])}</p></div>
        <div class="block"><h4>近期变化</h4><p>{_esc(v['recent_change'])}</p></div>
        <div class="block"><h4>历史位置</h4><p>{_esc(v['history_pos'])}</p></div>
      </div>
      <div>
        <div class="block"><h4>为什么值得盯</h4><p>{_esc(v['why'])}</p></div>
        <div class="block"><h4>与供需 / 价格的传导</h4><p>{_esc(mechanism)}</p></div>
        {chart_html}
      </div>
    </div>

    <div class="block" style="margin-top:4px"><h4>关键可核对数据</h4>
      <ul>{''.join(f'<li>{_esc(x)}</li>' for x in key_data)}</ul>
    </div>

    <div class="block"><h4>判断修正条件</h4>
      <div class="trio">
        <div class="tri yes"><div class="lbl">✓ 确认信号</div><div class="txt">{_esc(v['verify_yes'])}</div></div>
        <div class="tri no"><div class="lbl">✗ 否证信号</div><div class="txt">{_esc(v['verify_no'])}</div></div>
        <div class="tri inv"><div class="lbl">⚠ 变量失效 / 口径失真</div><div class="txt">{_esc(v['invalidate'])}</div></div>
      </div>
    </div>

    <div class="block"><h4>数据来源与更新节奏</h4>
      <div class="src">
        <div class="row"><div class="kk">数据来源</div><div>{_esc(v['source'])}</div></div>
        <div class="row"><div class="kk">更新频率</div><div>{_esc(v['freq'])}</div></div>
        <div class="row"><div class="kk">下次可获得</div><div><b>{_esc(v['next_date'])}</b></div></div>
        <div class="row"><div class="kk">置信度</div><div>{_esc(v['confidence'])}</div></div>
      </div>
      <div class="gapbox"><b>⚠ 口径与数据局限：</b>{_esc(v['gap'])}</div>
    </div>
  </div>
</article>"""


def _cards_view(payload: dict) -> str:
    vs = sorted(payload["variables"], key=lambda v: v["rank"])
    return (f'<div class="view active" id="view-cards"><div class="cards" id="cards">'
            + "".join(_card(v, payload) for v in vs)
            + '</div><div class="empty" id="empty" style="display:none">没有匹配的变量，试试切换筛选或清空搜索。</div></div>')


def _kind_class(kind: str) -> str:
    if "确定" in kind or "进行中" in kind:
        return "fixed"
    if "定期" in kind:
        return "periodic"
    return "cond"


def _timeline_view(payload: dict) -> str:
    as_of = payload.get("as_of", "")
    evs = sorted(payload["events"], key=lambda e: e["date"])
    rows = []
    for e in evs:
        c = CAT_COLOR.get(e["cat"], "#4f9cf9")
        past = " past" if e["date"] < as_of else ""
        dc = f'<span class="tag">{_esc(e["date_certainty"])}</span>' if e.get("date_certainty") else ""
        rows.append(f"""<div class="ev{past}" style="--c:{c}" data-search="{E((e['title']+' '+e['impact']).lower())}">
  <div class="ev-top">
    <span class="ev-date">{_esc(e['date_label'])}</span>
    <span class="kind {_kind_class(e['kind'])}">{_esc(e['kind'])}</span>
    <span class="tag cat" style="--c:{c}">{_esc(e['cat'])}</span>
    <span class="tag">{_esc(e['date'])}</span>{dc}
  </div>
  <div class="ev-title">{_esc(e['title'])}</div>
  <div class="ev-meta"><b>确定性：</b>{_esc(e['certainty'])}<br><b>影响路径：</b>{_esc(e['impact'])}<br><b>来源：</b>{_esc(e['source'])}</div>
</div>""")
    return f"""<div class="view" id="view-timeline">
<p class="desc" style="color:var(--txt2);font-size:13px;margin-bottom:16px">
  仅收录「已公开披露」或「有确定发布节奏」的节点。<span class="kind fixed">绿</span> = 有明确日期或正在进行的确定事件；
  <span class="kind periodic">蓝</span> = 按固定节奏发布的数据；<span class="kind cond">黄</span> = 条件触发或时点模糊，只作为观察窗口，
  <b>不代表必然发生</b>。灰化条目为已经过去的节点。</p>
<div class="timeline">{''.join(rows)}</div></div>"""


def _snapshot_view(payload: dict) -> str:
    rows = []
    for s in payload["snapshot"]:
        flag = ""
        if s.get("flag") == "low":
            flag = '<span class="flag low">低位</span>'
        elif s.get("flag") == "high":
            flag = '<span class="flag high">高位</span>'
        rows.append(f"""<tr data-search="{E(str(s['indicator']).lower())}">
  <td class="ind">{_esc(s['indicator'])}{flag}<div class="scope">{_esc(s['scope'])}</div></td>
  <td class="val">{_esc(s['value'])}</td>
  <td>{_esc(s['recent'])}</td>
  <td>{_esc(s['history'])}</td>
  <td class="scope">{_esc(s['source'])}</td>
</tr>""")
    return f"""<div class="view" id="view-snapshot">
<p class="desc" style="color:var(--txt2);font-size:13px;margin-bottom:16px">
  产业状态核对表：价格、库存、开工、产量、需求、成本六类核心指标。<b>同一指标有多个口径时分行列出且标注口径</b>，
  不同口径的数值不可直接比较或相减。</p>
<table class="snaptable">
  <thead><tr><th>指标 / 口径</th><th>当前值</th><th>近期变化</th><th>历史位置</th><th>来源</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table></div>"""


def _appendix(payload: dict) -> str:
    cands = []
    for c in payload["candidates"]:
        sel = "sel" if c["selected"] else ""
        mk = "✓" if c["selected"] else "—"
        cands.append(f"""<div class="candrow {sel}">
  <div class="mk">{mk}</div>
  <div><div class="nm">{_esc(c['name'])} <span class="tag cat" style="--c:{CAT_COLOR.get(c['cat'],'#888')}">{_esc(c['cat'])}</span></div>
  <div class="rs">{_esc(c['reason'])}</div></div>
  <div class="vf">可验证性<br>{_esc(c['verifiability'])}</div>
</div>""")

    secs = "".join(f'<div class="seccard"><div class="nm">{_esc(s["name"])}</div>'
                   f'<div class="rs">{_esc(s["why"])}</div></div>' for s in payload["secondary"])

    gaps = "".join(f"""<tr>
  <td class="item">{_esc(g['item'])}</td>
  <td>{_esc(g['why'])}</td>
  <td>{_esc(g['workaround'])}</td>
  <td class="scope">{_esc(g['limit'])}</td></tr>""" for g in payload["gaps"])

    cal = "".join(f'<div class="wk"><div class="w">{_esc(w["when"])}</div>'
                  f'<div class="t">{_esc(w["what"])}</div>'
                  f'<div class="s">来源：{_esc(w["src"])}</div></div>'
                  for w in payload.get("weekly_calendar", []))

    return f"""<div class="section">
  <h2><span class="num">01</span>候选池与筛选依据</h2>
  <p class="desc">先列出所有可想到的候选指标，再用「产业逻辑强度 × 可验证性 × 观察周期匹配度」筛选，只保留 3–6 个。
  未被选中的项不是不重要，而是<b>不能在同一周期内被独立验证</b>，或与入选变量高度相关，转为二级观察。</p>
  <div class="cand">{''.join(cands)}</div>
</div>

<div class="section">
  <h2><span class="num">02</span>二级观察（不进卡片，但跌破阈值要提级）</h2>
  <p class="desc">这些变量的信息价值真实存在，但在这个 1 个月周期内要么弹性小、要么与主变量共线。</p>
  <div class="secondary">{secs}</div>
</div>

<div class="section">
  <h2><span class="num">03</span>数据缺口登记</h2>
  <p class="desc">凡是无法稳定获得的指标，一律在这里写明「为什么拿不到 / 用什么替代 / 局限在哪」，
  而不是用估算值冒充实测值。</p>
  <table class="gaptable">
    <thead><tr><th>指标</th><th>为什么不可得</th><th>替代口径</th><th>局限</th></tr></thead>
    <tbody>{gaps}</tbody>
  </table>
</div>

<div class="section">
  <h2><span class="num">04</span>固定观察节奏</h2>
  <p class="desc">把「什么时候查什么」固化下来，避免只盯价格不看数据。</p>
  <div class="weekcal">{cal}</div>
</div>"""


def _footer(payload: dict) -> str:
    m = payload["meta"]
    return f"""<div class="wrap"><footer>
<b>使用说明</b><br>
本看板由「产业变量观察」模板生成，数据截止 {_esc(payload.get('as_of', m.get('as_of','')))}，
来源均为公开发布的行业数据与机构研报（已在各项注明）。<br>
<b>重要声明</b>：本看板是<b>研究观察工具</b>，只回答「接下来该盯什么、什么情况需要修正判断」，
不构成对价格方向的预测，也不构成任何投资建议。标注为「预估 / 估算 / 机构口径」的数值不等同于实测。
条件触发类事件（如海峡通行、限气时点）只表示存在观察窗口，不代表已发生或必然发生。<br>
生成时间：{date.today().isoformat()}　·　模板版本：{_esc(m.get('version','v1.0'))}
</footer></div>"""


SCRIPT = """
<script>
(function(){
  var viewBtns = document.querySelectorAll('.tab');
  var fbtns = document.querySelectorAll('.fbtn');
  var cards = Array.prototype.slice.call(document.querySelectorAll('#cards .card'));
  var events = Array.prototype.slice.call(document.querySelectorAll('.ev'));
  var rows = Array.prototype.slice.call(document.querySelectorAll('.snaptable tbody tr'));
  var q = document.getElementById('q');
  var countEl = document.getElementById('count');
  var emptyEl = document.getElementById('empty');
  var favKey = 'chemvar-fav-' + (document.title||'').slice(0,20);
  var favs = {};
  try { favs = JSON.parse(localStorage.getItem(favKey) || '{}') || {}; } catch(e) { favs = {}; }

  function saveFavs(){ try { localStorage.setItem(favKey, JSON.stringify(favs)); } catch(e){} }

  document.querySelectorAll('.starbtn').forEach(function(b){
    var vid = b.getAttribute('data-fav');
    if (favs[vid]) { b.classList.add('on'); b.textContent = '★'; }
    b.addEventListener('click', function(){
      favs[vid] = !favs[vid];
      b.classList.toggle('on', !!favs[vid]);
      b.textContent = favs[vid] ? '★' : '☆';
      saveFavs();
      apply();
    });
  });

  var curCat = 'all', curView = 'cards';

  function apply(){
    var term = (q.value || '').trim().toLowerCase();
    var shown = 0;
    cards.forEach(function(c){
      var cat = c.getAttribute('data-cat');
      var vid = c.getAttribute('data-vid');
      var okCat = (curCat === 'all') || (curCat === 'fav' ? !!favs[vid] : cat === curCat);
      var okTerm = !term || (c.getAttribute('data-search')||'').indexOf(term) >= 0;
      var show = okCat && okTerm;
      c.classList.toggle('hidden', !show);
      if (show) shown++;
    });
    if (emptyEl) emptyEl.style.display = shown ? 'none' : 'block';

    [events, rows].forEach(function(list){
      list.forEach(function(el){
        var okTerm = !term || (el.getAttribute('data-search')||'').indexOf(term) >= 0;
        el.style.display = okTerm ? '' : 'none';
      });
    });

    var total = curView === 'cards' ? cards.length : (curView === 'timeline' ? events.length : rows.length);
    if (countEl) {
      countEl.textContent = curView === 'cards'
        ? (shown + ' / ' + total + ' 个变量')
        : (total + ' 条记录');
    }
  }

  viewBtns.forEach(function(b){
    b.addEventListener('click', function(){
      curView = b.getAttribute('data-view');
      viewBtns.forEach(function(x){ x.classList.toggle('active', x === b); });
      document.querySelectorAll('.view').forEach(function(v){
        v.classList.toggle('active', v.id === 'view-' + curView);
      });
      apply();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  fbtns.forEach(function(b){
    b.addEventListener('click', function(){
      curCat = b.getAttribute('data-cat');
      fbtns.forEach(function(x){ x.classList.toggle('active', x === b); });
      apply();
    });
  });

  if (q) q.addEventListener('input', apply);
  apply();
})();
</script>
"""


def render(payload: dict, validate_first: bool = True) -> str:
    if validate_first:
        problems = validate(payload)
        if problems:
            raise ValueError("payload 不符合契约：\n- " + "\n- ".join(problems))
    body = (
        _html_head(payload)
        + _header(payload)
        + _toolbar(payload)
        + '<div class="wrap">'
        + _overview(payload)
        + _cards_view(payload)
        + _timeline_view(payload)
        + _snapshot_view(payload)
        + _appendix(payload)
        + "</div>"
        + _footer(payload)
        + SCRIPT
        + "</body></html>"
    )
    return body
