#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML 看板生成器：输出自包含单文件（无外部依赖，双击即用）。"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppctl as C


def build_payload(proj_dir):
    d = os.path.join(proj_dir, "data")
    pj = C.load_json(os.path.join(d, "projects.json"))
    projects = pj["projects"]
    excluded = pj.get("excluded", [])
    progress = C.load_json(os.path.join(d, "progress.json"))["progress"]
    sources = {s["id"]: s for s in C.load_json(os.path.join(d, "sources.json"))["sources"]}
    cfg = C.load_json(os.path.join(d, "config.json"), {})
    as_of_year = int(cfg.get("as_of", "2026")[:4])

    by = defaultdict(list)
    for x in progress:
        by[x["project_id"]].append(x)

    def pkey(x):
        mi = C.month_index(C.parse_date(x.get("fact_date")))
        return (mi if mi is not None else 0, x["progress_id"])

    P = []
    for p in projects:
        rows = sorted(by.get(p["project_id"], []), key=pkey)
        cap = round(sum((u.get("capacity_wan") or 0) for u in p.get("units") or []), 2)
        evs = []
        for x in rows:
            srcs = [sources[s] for s in x.get("source_ids", []) if s in sources]
            evs.append({
                "id": x["progress_id"], "stage": x.get("stage", ""),
                "fact": x.get("fact_date", ""), "msg": x.get("msg_date", ""),
                "desc": x.get("desc", ""), "grade": x.get("evidence_grade", ""),
                "plan": x.get("plan_date_noted", ""), "chg": x.get("plan_change", ""),
                "from": x.get("plan_from", ""), "to": x.get("plan_to", ""),
                "note": x.get("note", ""),
                "src": [{"id": s["id"], "t": s["title"], "u": s["url"], "p": s.get("publisher", ""),
                         "d": s.get("date", ""), "g": s.get("grade", ""), "ty": s.get("type", "")}
                        for s in srcs],
            })
        hist = [{"fact": e["fact"], "msg": e["msg"], "chg": e["chg"], "from": e["from"],
                 "to": e["to"], "desc": e["desc"], "grade": e["grade"]}
                for e in evs if e["chg"]]
        last = evs[-1] if evs else None
        P.append({
            "id": p["project_id"], "owner": p["owner"], "group": p["group"],
            "name": p["project_name"], "prov": p["province"], "city": p.get("city", ""),
            "park": p.get("park", ""), "region": C.region_of(p["province"]),
            "prod": p["product"], "cap": cap, "nunit": len(p.get("units") or []),
            "proc": p.get("process", ""),
            "proccls": C.ROUTE_CLASS.get(p.get("process", ""), p.get("process", "")),
            "nature": p.get("nature", ""), "stage": p["stage"],
            "capstate": C.cap_state(p["stage"]),
            "first_disc": p.get("first_disclosed", ""),
            "first_plan": p.get("first_plan_date", ""), "latest_plan": p.get("latest_plan_date", ""),
            "delay": p.get("delay_flag", ""), "delay_m": p.get("delay_months", ""),
            "ramp": p.get("ramp_year", ""), "unc": p.get("uncertainty", ""),
            "count": p.get("counting_note", ""), "dup": p.get("dup_note", ""),
            "watch": p.get("watch", ""),
            "online": p.get("actual_online_date", ""),
            "units": [{"id": u["unit_id"], "n": u.get("unit_name", ""),
                       "cap": u.get("capacity_wan") or 0, "rep": u.get("replace_wan") or 0}
                      for u in p.get("units") or []],
            "ev": evs, "hist": hist,
            "last": ({"desc": last["desc"], "fact": last["fact"], "stage": last["stage"],
                      "grade": last["grade"]} if last else None),
            "srcids": p.get("source_ids", []),
            "yplan": C.parse_date(p.get("latest_plan_date"))["year"],
        })

    yearly = C.summary_yearly(proj_dir, projects, cfg)
    region = C.summary_region(proj_dir, projects, cfg)
    deferred = C.deferred_capacity(projects, as_of_year)

    return {
        "as_of": cfg.get("as_of", ""),
        "product": cfg.get("product", ""),
        "base": cfg["baseline_capacity_wan"],
        "base_src": cfg.get("baseline_capacity_source", ""),
        "bases": cfg.get("baseline_alternatives", []),
        "divergence": cfg.get("new_capacity_forecast_divergence", []),
        "ramp": cfg.get("ramp_up_discount", {}),
        "routebase": cfg.get("route_baseline_2026", {}),
        "regionbase": cfg.get("region_baseline_2026", {}),
        "projects": P,
        "yearly": yearly,
        "region": region,
        "deferred": deferred,
        "excluded": excluded,
        "sources": sources,
        "nprogress": len(progress),
        "as_of_year": as_of_year,
    }


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<style>
:root{
  --navy:#12263f; --navy2:#1b3a5c; --ink:#1c2b3a; --mute:#64748b; --line:#e2e8f0;
  --bg:#f6f8fb; --card:#ffffff; --accent:#0f6fc5; --accent2:#0ea5a4;
  --a:#0b8457; --a-bg:#e7f5ee;  --t:#b8860b; --t-bg:#fdf5e0;
  --c:#0f6fc5; --c-bg:#e8f1fb;  --p:#8b5cf6; --p-bg:#f1ecfe;
  --r:#c0392b; --r-bg:#fbeae8;  --x:#64748b; --x-bg:#eef2f6;
  --shadow:0 1px 2px rgba(16,24,40,.06),0 4px 16px rgba(16,24,40,.06);
  --shadow2:0 8px 32px rgba(16,24,40,.16);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:"Microsoft YaHei","PingFang SC","Hiragino Sans GB",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:var(--bg); color:var(--ink); font-size:13px; line-height:1.6; -webkit-font-smoothing:antialiased}
h1,h2,h3,h4{margin:0;font-weight:700;letter-spacing:-.01em}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.mono{font-family:"JetBrains Mono","SF Mono",Consolas,monospace;font-variant-numeric:tabular-nums}

/* ---------- header ---------- */
header{background:linear-gradient(135deg,#12263f 0%,#1b3a5c 55%,#24507a 100%);color:#fff;padding:20px 28px 0}
.hd{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;flex-wrap:wrap}
.hd h1{font-size:21px;letter-spacing:-.02em}
.hd .sub{color:#a9c2dd;font-size:12px;margin-top:5px}
.hd .stamp{text-align:right;font-size:11px;color:#a9c2dd;line-height:1.9}
.hd .stamp b{color:#fff;font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:1px;background:rgba(255,255,255,.14);
  margin:18px -28px 0;border-top:1px solid rgba(255,255,255,.14)}
.kpi{background:rgba(255,255,255,.045);padding:13px 18px}
.kpi .k{font-size:10.5px;color:#9db8d6;letter-spacing:.04em;text-transform:uppercase}
.kpi .v{font-size:23px;font-weight:700;margin-top:3px;letter-spacing:-.02em}
.kpi .v small{font-size:11px;font-weight:400;color:#a9c2dd;margin-left:3px}
.kpi.alert .v{color:#ffb4a8}
.kpi.good .v{color:#8fe3c0}

/* ---------- nav ---------- */
nav{position:sticky;top:0;z-index:60;background:rgba(255,255,255,.96);backdrop-filter:blur(12px);
  border-bottom:1px solid var(--line);padding:0 28px;display:flex;gap:2px;overflow-x:auto;box-shadow:0 1px 3px rgba(16,24,40,.05)}
nav button{background:none;border:0;padding:12px 15px;font-size:13px;font-family:inherit;color:var(--mute);
  cursor:pointer;border-bottom:2.5px solid transparent;white-space:nowrap;font-weight:500}
nav button:hover{color:var(--ink);background:#f8fafc}
nav button.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:700}
main{padding:22px 28px 80px;max-width:1720px;margin:0 auto}
section{display:none} section.on{display:block;animation:fade .25s ease}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

/* ---------- card ---------- */
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);margin-bottom:18px;overflow:hidden}
.card>.ch{padding:14px 18px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
.card>.ch h2{font-size:14.5px}
.card>.ch .desc{font-size:11.5px;color:var(--mute);margin-top:2px;max-width:1000px}
.card>.cb{padding:18px}

/* ---------- callout ---------- */
.callout{border-left:4px solid var(--accent);background:#f0f7ff;padding:13px 16px;border-radius:0 8px 8px 0;margin-bottom:16px;font-size:12.5px}
.callout.warn{border-left-color:var(--r);background:var(--r-bg)}
.callout.ok{border-left-color:var(--a);background:var(--a-bg)}
.callout b{font-weight:700}

/* ---------- filter bar ---------- */
.filters{display:flex;gap:9px;flex-wrap:wrap;align-items:center;padding:12px 18px;background:#fbfcfe;border-bottom:1px solid var(--line)}
.filters select,.filters input{font-family:inherit;font-size:12px;padding:6px 9px;border:1px solid #cfdae6;
  border-radius:7px;background:#fff;color:var(--ink);outline:none}
.filters select:focus,.filters input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(15,111,197,.12)}
.filters label{font-size:11.5px;color:var(--mute);display:flex;align-items:center;gap:5px}
.btn{font-family:inherit;font-size:12px;padding:6px 12px;border-radius:7px;border:1px solid #cfdae6;background:#fff;
  cursor:pointer;color:var(--ink);transition:.15s}
.btn:hover{background:#f1f5f9;border-color:#a9c2dd}
.btn.pri{background:var(--accent);color:#fff;border-color:var(--accent)}
.btn.pri:hover{background:#0a5ba3}
.chip{display:inline-flex;align-items:center;gap:4px;font-size:11px;padding:2px 8px;border-radius:20px;
  background:var(--x-bg);color:var(--x);font-weight:600;white-space:nowrap}
.chip.s-a{background:var(--a-bg);color:var(--a)} .chip.s-t{background:var(--t-bg);color:var(--t)}
.chip.s-c{background:var(--c-bg);color:var(--c)} .chip.s-p{background:var(--p-bg);color:var(--p)}
.chip.s-r{background:var(--r-bg);color:var(--r)} .chip.s-x{background:var(--x-bg);color:var(--x)}
.chip.g-A{background:#0b8457;color:#fff} .chip.g-B{background:#0f6fc5;color:#fff}
.chip.g-C{background:#c99a06;color:#fff} .chip.g-D{background:#c0392b;color:#fff}
.chip.sm{font-size:10px;padding:1px 6px}

/* ---------- table ---------- */
.tw{overflow:auto;max-height:none}
table{width:100%;border-collapse:collapse;font-size:12px}
thead th{position:sticky;top:0;background:#f1f5f9;color:#475569;font-size:11px;font-weight:700;
  text-align:left;padding:9px 10px;border-bottom:1.5px solid #d5dee8;white-space:nowrap;z-index:2;cursor:pointer;user-select:none}
thead th:hover{background:#e4ecf3}
thead th .ar{color:#94a3b8;font-size:9px;margin-left:3px}
tbody td{padding:8px 10px;border-bottom:1px solid #eef2f6;vertical-align:top}
tbody tr:hover{background:#f8fbff;cursor:pointer}
tbody tr.zebra{background:#fcfdfe}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.nm{font-weight:600;color:var(--ink);max-width:340px}
td.ow{color:var(--mute);font-size:11.5px;max-width:200px}
.del{color:var(--r);font-weight:600}

/* ---------- chart ---------- */
.chart{width:100%;overflow-x:auto}
.chart svg{display:block;max-width:100%;height:auto}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--mute);margin-top:10px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}

/* ---------- timeline ---------- */
.tl{position:relative;padding-left:0}
.tl-row{display:grid;grid-template-columns:96px 1fr;gap:0;min-height:34px}
.tl-y{font-weight:700;font-size:12px;color:var(--mute);padding-top:6px;border-right:2px solid var(--line);
  position:relative;padding-right:14px;text-align:right}
.tl-y::after{content:"";position:absolute;right:-6px;top:9px;width:10px;height:10px;border-radius:50%;
  background:#fff;border:2.5px solid var(--accent)}
.tl-b{padding:0 0 14px 18px}
.tl-item{background:#fff;border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;
  padding:9px 12px;margin-bottom:8px;box-shadow:0 1px 2px rgba(16,24,40,.04);cursor:pointer;transition:.15s}
.tl-item:hover{box-shadow:var(--shadow);transform:translateX(2px)}
.tl-item .r1{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.tl-item .nm{font-weight:700;font-size:12.5px}
.tl-item .mt{font-size:11px;color:var(--mute);margin-top:3px}
.tl-item .bars{display:flex;gap:3px;margin-top:6px;flex-wrap:wrap}
.seg{height:5px;border-radius:2px;position:relative}

/* ---------- map ---------- */
.mapwrap{position:relative;background:#fff;border-radius:10px;overflow:hidden}
.mapwrap svg{display:block;width:100%;height:auto}
.map-tip{position:fixed;pointer-events:none;background:rgba(18,38,63,.96);color:#fff;font-size:11.5px;
  padding:8px 11px;border-radius:7px;box-shadow:var(--shadow2);opacity:0;transition:opacity .12s;z-index:200;max-width:280px;line-height:1.55}
.map-tip.on{opacity:1}
.prov-shape{stroke:#fff;stroke-width:1.1;cursor:pointer;transition:.14s}
.prov-shape:hover{stroke:#12263f;stroke-width:2}

/* ---------- drawer ---------- */
.mask{position:fixed;inset:0;background:rgba(15,23,42,.42);backdrop-filter:blur(2px);opacity:0;
  pointer-events:none;transition:opacity .22s;z-index:100}
.mask.on{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;height:100vh;width:min(780px,94vw);background:#fff;box-shadow:var(--shadow2);
  transform:translateX(102%);transition:transform .28s cubic-bezier(.4,0,.2,1);z-index:110;display:flex;flex-direction:column}
.drawer.on{transform:none}
.dh{padding:16px 20px;background:linear-gradient(135deg,#12263f,#24507a);color:#fff;flex-shrink:0}
.dh .id{font-size:10.5px;color:#9db8d6;letter-spacing:.05em}
.dh h3{font-size:16px;margin:3px 0 2px;line-height:1.35}
.dh .ow{font-size:12px;color:#c5d8ec}
.dh .x{position:absolute;top:14px;right:16px;background:rgba(255,255,255,.14);border:0;color:#fff;
  width:28px;height:28px;border-radius:7px;cursor:pointer;font-size:16px;line-height:1}
.dh .x:hover{background:rgba(255,255,255,.26)}
.db{flex:1;overflow-y:auto;padding:18px 20px 40px}
.dsec{margin-bottom:20px}
.dsec h4{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);
  margin-bottom:9px;padding-bottom:5px;border-bottom:1px solid var(--line)}
.kv{display:grid;grid-template-columns:96px 1fr;gap:6px 12px;font-size:12.5px}
.kv .k{color:var(--mute);font-size:11.5px}
.kv .v{color:var(--ink)}
.note{background:#f8fafc;border:1px solid var(--line);border-radius:7px;padding:9px 11px;font-size:12px;
  color:#475569;line-height:1.65;white-space:pre-wrap}
.note.hl{background:#fff8e6;border-color:#f0dca8}
.note.bad{background:var(--r-bg);border-color:#f3c9c2}
.ev{display:grid;grid-template-columns:78px 1fr;gap:0;border-left:2px solid var(--line);margin-left:5px}
.ev-i{position:relative;padding:0 0 14px 16px}
.ev-i::before{content:"";position:absolute;left:-5.5px;top:5px;width:9px;height:9px;border-radius:50%;background:#fff;border:2px solid var(--accent)}
.ev-i.done::before{border-color:var(--a);background:var(--a)}
.ev-i.chg::before{border-color:var(--t);background:var(--t)}
.ev-d{font-size:11px;color:var(--mute);padding-top:2px;font-variant-numeric:tabular-nums}
.ev-t{font-size:12.5px}
.ev-t .hd2{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:2px}
.ev-src{margin-top:5px;display:flex;flex-direction:column;gap:2px}
.ev-src a{font-size:11px;color:var(--accent);display:inline-flex;gap:4px;align-items:baseline;line-height:1.5}
.ev-src a:hover{text-decoration:underline}
.ev-src .sid{font-size:9.5px;color:var(--mute);font-family:monospace;flex-shrink:0}

/* ---------- misc ---------- */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:1100px){.grid2{grid-template-columns:1fr}}
.stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:16px}
.stat{background:#fbfcfe;border:1px solid var(--line);border-radius:9px;padding:11px 14px}
.stat .k{font-size:10.5px;color:var(--mute);letter-spacing:.03em}
.stat .v{font-size:19px;font-weight:700;margin-top:2px}
.stat .v small{font-size:11px;font-weight:400;color:var(--mute)}
.bar-h{height:22px;border-radius:5px;display:flex;overflow:hidden;background:#eef2f6;margin:5px 0}
.bar-h span{display:flex;align-items:center;justify-content:center;font-size:10px;color:#fff;font-weight:600;
  min-width:0;overflow:hidden;white-space:nowrap;transition:width .4s}
.empty{padding:36px;text-align:center;color:var(--mute);font-size:12.5px}
.tag{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:5px;background:var(--x-bg);color:var(--x);margin-right:4px}
.foot{color:var(--mute);font-size:11px;text-align:center;padding:20px;line-height:1.9}
.star{background:none;border:0;cursor:pointer;font-size:15px;color:#cbd5e1;padding:0 2px;line-height:1}
.star.on{color:#f5a623}
.scroll-y{max-height:520px;overflow-y:auto}
.hl-num{color:var(--r);font-weight:700}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:5px;border:2px solid #fff}
::-webkit-scrollbar-thumb:hover{background:#94a3b8}
</style>
</head>
<body>
<header>
  <div class="hd">
    <div>
      <h1>@@TITLE@@</h1>
      <div class="sub">期现研究 · 产业基本面 ｜ 逐项目工程证据驱动的产能跟踪台账 ｜ 备案/在建/计划 <b style="color:#ffb4a8">≠</b> 已形成有效供应</div>
    </div>
    <div class="stamp">
      数据截至 <b>@@ASOF@@</b><br>
      <span id="stampCounts"></span>
    </div>
  </div>
  <div class="kpis" id="kpis"></div>
</header>

<nav id="nav">
  <button data-t="overview" class="on">概览与结论</button>
  <button data-t="timeline">投产时间线</button>
  <button data-t="capacity">年度产能</button>
  <button data-t="map">区域地图</button>
  <button data-t="table">明细表</button>
  <button data-t="delayed">延期与缺口</button>
  <button data-t="dedup">去重与剔除</button>
  <button data-t="watch">自选跟踪</button>
  <button data-t="method">口径与方法</button>
</nav>

<main>
  <section id="s-overview" class="on"></section>
  <section id="s-timeline"></section>
  <section id="s-capacity"></section>
  <section id="s-map"></section>
  <section id="s-table"></section>
  <section id="s-delayed"></section>
  <section id="s-dedup"></section>
  <section id="s-watch"></section>
  <section id="s-method"></section>
</main>

<div class="mask" id="mask"></div>
<div class="drawer" id="drawer">
  <div class="dh">
    <button class="x" id="dclose">×</button>
    <div class="id" id="did"></div>
    <h3 id="dname"></h3>
    <div class="ow" id="downer"></div>
  </div>
  <div class="db" id="dbody"></div>
</div>
<div class="map-tip" id="mtip"></div>

<script>
const D = @@DATA@@;

/* ============ 工具 ============ */
const $ = s => document.querySelector(s);
const el = (t,c,h) => { const e=document.createElement(t); if(c)e.className=c; if(h!==undefined)e.innerHTML=h; return e; };
const fmt = (n,d=1) => (n===null||n===undefined||n==="")?"—":Number(n).toFixed(d).replace(/\.0+$/,"");
const esc = s => String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");

const STAGE_CLS = {"试车":"s-t","投产":"s-a","达产":"s-a","运行":"s-a","中交":"s-c","设备安装":"s-c",
  "建设":"s-c","开工":"s-p","核准":"s-p","环评批复":"s-p","环评受理":"s-p","备案":"s-x","拟建":"s-x",
  "暂停":"s-r","取消":"s-r"};
const stageChip = st => `<span class="chip ${STAGE_CLS[st]||'s-x'}">${esc(st)}</span>`;
const gradeChip = g => `<span class="chip g-${g} sm">${g}</span>`;
const CAP_COLOR = {"已形成有效供应":"#0b8457","试车/调试（未形成稳定商品供应）":"#b8860b",
  "在建（未形成供应）":"#0f6fc5","计划（未形成供应）":"#8b5cf6","暂停/取消":"#c0392b","未分类":"#64748b"};
const capColor = s => CAP_COLOR[s] || "#64748b";

/* ============ 派生统计 ============ */
const projCap = p => p.cap;
const totalCap = D.projects.reduce((a,p)=>a+projCap(p),0);
const byBucket = {};
D.projects.forEach(p=>{ byBucket[p.capstate]=(byBucket[p.capstate]||0)+p.cap; });

/* 年度聚合（与后端同口径） */
function yearAgg(){
  const g = {};
  D.projects.forEach(p=>{
    let bucket = p.stage==="运行"||p.stage==="达产"||p.stage==="投产" ? "actual"
      : p.stage==="试车" ? "trial"
      : ["中交","设备安装","建设","开工"].includes(p.stage) ? "build"
      : p.stage==="暂停"||p.stage==="取消" ? "stopped" : "plan";
    let y = (bucket==="actual" && p.online) ? parseInt(p.online.slice(0,4))
      : (p.yplan ? p.yplan : "未定");
    const k = String(y);
    g[k] = g[k] || {y:k,actual:0,trial:0,build:0,plan:0,stopped:0,repl:0,units:0,ids:new Set()};
    g[k][bucket] += p.cap;
    g[k].repl += p.units.reduce((a,u)=>a+(u.rep||0),0);
    g[k].units += p.nunit;
    g[k].ids.add(p.id);
  });
  const keys = Object.keys(g).sort((a,b)=> a==="未定"?1 : b==="未定"?-1 : a-b);
  return keys.map(k=>{ const o=g[k]; return {...o, ids:[...o.ids],
    nominal: o.actual+o.trial+o.build+o.plan, net: o.actual+o.trial+o.build+o.plan-o.repl}; });
}
const YA = yearAgg();

/* ============ 头部 KPI ============ */
(function(){
  const t2026 = YA.find(x=>x.y===String(D.as_of_year)) || {trial:0,build:0,plan:0,actual:0,nominal:0,net:0};
  const nTrial = D.projects.filter(p=>p.stage==="试车").length;
  const nBuild = D.projects.filter(p=>["中交","设备安装","建设","开工"].includes(p.stage)).length;
  const nPlan = D.projects.filter(p=>["核准","环评批复","环评受理","备案","拟建"].includes(p.stage)).length;
  const defTot = D.deferred.reduce((a,d)=>a+d.capacity_wan,0);
  const kpis = [
    ["跟踪项目", D.projects.length, "个", ""],
    ["装置/生产线", D.projects.reduce((a,p)=>a+p.nunit,0), "套", ""],
    ["设计产能合计", fmt(totalCap), "万吨/年", ""],
    ["已形成有效供应", fmt(byBucket["已形成有效供应"]||0), "万吨/年", "good"],
    ["试车/调试中", fmt(byBucket["试车/调试（未形成稳定商品供应）"]||0), "万吨/年", ""],
    ["在建未形成供应", fmt(byBucket["在建（未形成供应）"]||0), "万吨/年", ""],
    ["仅批文/计划", fmt(byBucket["计划（未形成供应）"]||0), "万吨/年", ""],
  ];
  $("#kpis").innerHTML = kpis.map(([k,v,u,cls])=>
    `<div class="kpi ${cls}"><div class="k">${k}</div><div class="v">${v}<small>${u}</small></div></div>`).join("");
  $("#stampCounts").innerHTML = `项目 <b>${D.projects.length}</b> ｜ 装置 <b>${D.projects.reduce((a,p)=>a+p.nunit,0)}</b> ｜ 进展事实 <b>${D.nprogress}</b> ｜ 来源 <b>${Object.keys(D.sources).length}</b>`;
})();

/* ============ 概览 ============ */
function renderOverview(){
  const s = $("#s-overview");
  const t = YA.find(x=>x.y===String(D.as_of_year)) || {trial:0,build:0,plan:0,actual:0,nominal:0};
  const defTot = D.deferred.reduce((a,d)=>a+d.capacity_wan,0);
  const ready = D.projects.filter(p=>p.stage==="试车").sort((a,b)=>b.cap-a.cap);
  const built = D.projects.filter(p=>["中交","设备安装","建设","开工"].includes(p.stage)).sort((a,b)=>b.cap-a.cap);
  const planned = D.projects.filter(p=>["核准","环评批复","环评受理","备案","拟建"].includes(p.stage)).sort((a,b)=>b.cap-a.cap);
  const actual = D.projects.filter(p=>["投产","达产","运行"].includes(p.stage));

  s.innerHTML = `
  <div class="callout warn">
    <b>本页最重要的一句话：</b>名义上 ${D.as_of_year} 年计划新增 <b class="hl-num">${fmt(t.nominal)}</b> 万吨/年，
    但其中 <b class="hl-num">${fmt(defTot)}</b> 万吨（${t.nominal?fmt(defTot/t.nominal*100,0):0}%）在当前工程进度上
    <b>不支持在年内形成供应</b>。把"计划投产表"直接当"新增供应"用，是这类研究最常犯、代价最大的错误。
    详见 <a href="javascript:void(0)" onclick="go('delayed')">延期与缺口</a>。
  </div>

  <div class="card"><div class="ch"><div><h2>一、按产能状态拆解（四类互斥）</h2>
    <div class="desc">同一套装置在任一时刻只属于一类，因此四类相加恰等于跟踪产能合计，不重复、不遗漏。仅"已形成有效供应"可计入当前供给。</div></div></div>
    <div class="cb">
      <div class="bar-h" style="height:34px">
        ${["已形成有效供应","试车/调试（未形成稳定商品供应）","在建（未形成供应）","计划（未形成供应）","暂停/取消"]
          .filter(k=>(byBucket[k]||0)>0)
          .map(k=>`<span style="width:${(byBucket[k]/totalCap*100).toFixed(2)}%;background:${capColor(k)}"
            title="${k}：${fmt(byBucket[k])} 万吨/年">${byBucket[k]/totalCap>0.09?fmt(byBucket[k]):''}</span>`).join("")}
      </div>
      <div class="legend">
        ${["已形成有效供应","试车/调试（未形成稳定商品供应）","在建（未形成供应）","计划（未形成供应）"]
          .map(k=>`<span><i style="background:${capColor(k)}"></i>${k} <b>${fmt(byBucket[k]||0)}</b> 万吨/年
            (${totalCap?fmt((byBucket[k]||0)/totalCap*100,1):0}%)</span>`).join("")}
      </div>
      <div class="stat-row" style="margin-top:16px">
        <div class="stat"><div class="k">现有产能基数</div><div class="v">${fmt(D.base)}<small> 万吨/年</small></div>
          <div style="font-size:10.5px;color:var(--mute);margin-top:3px">${esc(D.base_src)}</div></div>
        <div class="stat"><div class="k">${D.as_of_year} 年名义新增</div><div class="v">${fmt(t.nominal)}<small> 万吨</small></div>
          <div style="font-size:10.5px;color:var(--mute);margin-top:3px">占现有产能 ${fmt(t.nominal/D.base*100,2)}%</div></div>
        <div class="stat"><div class="k">其中工程证据不支持年内</div><div class="v" style="color:var(--r)">${fmt(defTot)}<small> 万吨</small></div>
          <div style="font-size:10.5px;color:var(--mute);margin-top:3px">隐性供给缺口 ${D.deferred.length} 项</div></div>
        <div class="stat"><div class="k">${D.as_of_year} 年可落地估计</div><div class="v" style="color:var(--a)">${fmt(t.nominal-defTot)}<small> 万吨</small></div>
          <div style="font-size:10.5px;color:var(--mute);margin-top:3px">名义 − 隐性缺口</div></div>
        <div class="stat"><div class="k">2027 年名义新增</div><div class="v">${fmt((YA.find(x=>x.y==="2027")||{}).nominal||0)}<small> 万吨</small></div>
          <div style="font-size:10.5px;color:var(--mute);margin-top:3px">含已推迟项目滚入</div></div>
      </div>
    </div>
  </div>

  <div class="card"><div class="ch"><div><h2>二、核心结论（按证据强度排序）</h2>
    <div class="desc">每条结论都能在"明细表"与项目抽屉里追到事实日期与来源原文。</div></div></div>
    <div class="cb">
      <div class="note" style="margin-bottom:12px">
<b>1｜唯一走完全链条的项目是塔里木二期 45 万吨。</b>
2026-03-27 试压 → 04-23 挤压造粒实物料试车 → 05-21 中交 → 07-16 一次开车 → 07-25 打通全流程出合格 PP →
09-24 首次高负荷标定 → <b>10-15 全面投入商业运营</b>。这是本库中唯一可以写"已形成有效供应"且无需加任何限定的装置。

<b>2｜已开车但尚未形成稳定供应：古雷 95 万吨 + 中煤榆林 60 万吨。</b>
古雷两条线（40 抗冲/无规 + 55 均聚/无规）已于 2026-09 中旬测试开车一次成功，但乙烯龙头装置计划 10 月底才投料试车——
聚合线开车 ≠ 乙烯稳定供料，11 月"全面投产"是目标而非既成事实。中煤榆林 8 月上旬已产出第一粒 PP 颗粒，上游 MTO 负荷决定能否连续供料。

<b>3｜${D.as_of_year} 年内最大变数在四套"年底投产"的装置：华锦阿美 100 + 荣信 40 + 东明 35 + 宝丰 25。</b>
四套合计 ${fmt(D.deferred.filter(d=>["PP-P1-003","PP-P1-006","PP-P1-007","PP-P1-004"].includes(d.project_id)).reduce((a,d)=>a+d.capacity_wan,0))} 万吨，
全部停留在"设备安装"且无任何试车报道。其中荣信最危险：2025-12 土建收官时设备安装仅完成 12%，却报 2026 年底出产品。

<b>4｜最强的"反向信号"是利华益维远 20 万吨：装置已建成，公司说"择机安排试生产"。</b>
2023-11 PDH 就投产了，PP 装置到 2026-04 业绩会仍是"已建设完成、择机试生产"，年报显示工程进度 100% 却未转固。
它证明了一件事：<b>PP 装置的开车时点由价差决定，不由工程进度决定。</b>这个案例应当用来校准对所有制冷项目的判断。

<b>5｜区域上，新疆是全国最拥挤的地方：未来新增 530 万吨，占现有全国产能 ${fmt(530/D.base*100,1)}%。</b>
准东（宝丰 195 + 兖矿新疆 40 + 新疆能化 50）、哈密（山能 40 + 疆纳 35）、库车（塔河 50）、乌鲁木齐（乌石化 45）同时推进，
而本地消费能力有限，全部依赖外运——这会重画全国的物流与价差格局。</div>
    </div>
  </div>

  <div class="grid2">
    <div class="card"><div class="ch"><h2>三、已试车 / 待试车（${ready.length}）</h2></div>
      <div class="cb scroll-y">${ready.map(p=>`
        <div class="tl-item" onclick="openP('${p.id}')" style="border-left-color:var(--t)">
          <div class="r1"><span class="nm">${esc(p.name)}</span>${stageChip(p.stage)}
            <span class="chip s-x">${esc(p.prov)}</span></div>
          <div class="mt">${esc(p.owner)} ｜ <b>${fmt(p.cap)}</b> 万吨/年 ｜ ${esc(p.proc)} ｜ 最新预计 ${esc(p.latest_plan)}</div>
          <div class="mt">${esc((p.last||{}).desc||"").slice(0,90)}</div>
        </div>`).join("") || '<div class="empty">无</div>'}</div></div>
    <div class="card"><div class="ch"><h2>四、在建未开车（${built.length}）</h2></div>
      <div class="cb scroll-y">${built.map(p=>`
        <div class="tl-item" onclick="openP('${p.id}')" style="border-left-color:var(--c)">
          <div class="r1"><span class="nm">${esc(p.name)}</span>${stageChip(p.stage)}
            <span class="chip s-x">${esc(p.prov)}</span></div>
          <div class="mt">${esc(p.owner)} ｜ <b>${fmt(p.cap)}</b> 万吨/年 ｜ ${esc(p.proc)} ｜ 最新预计 ${esc(p.latest_plan)}</div>
          <div class="mt">${esc((p.last||{}).desc||"").slice(0,90)}</div>
        </div>`).join("") || '<div class="empty">无</div>'}</div></div>
  </div>

  <div class="grid2">
    <div class="card"><div class="ch"><h2>五、仅批文 / 计划阶段（${planned.length}）</h2></div>
      <div class="cb scroll-y">${planned.map(p=>`
        <div class="tl-item" onclick="openP('${p.id}')" style="border-left-color:var(--p)">
          <div class="r1"><span class="nm">${esc(p.name)}</span>${stageChip(p.stage)}
            <span class="chip s-x">${esc(p.prov)}</span></div>
          <div class="mt">${esc(p.owner)} ｜ <b>${fmt(p.cap)}</b> 万吨/年 ｜ 预计 ${esc(p.latest_plan)}</div>
        </div>`).join("") || '<div class="empty">无</div>'}</div></div>
    <div class="card"><div class="ch"><h2>六、已形成有效供应（${actual.length}）</h2>
      <div class="desc">已计入现有产能基数，仅作对照样本</div></div>
      <div class="cb scroll-y">${actual.map(p=>`
        <div class="tl-item" onclick="openP('${p.id}')" style="border-left-color:var(--a)">
          <div class="r1"><span class="nm">${esc(p.name)}</span>${stageChip(p.stage)}</div>
          <div class="mt">${esc(p.owner)} ｜ <b>${fmt(p.cap)}</b> 万吨/年 ｜ 投产 ${esc(p.online||"—")}</div>
        </div>`).join("") || '<div class="empty">无</div>'}</div></div>
  </div>`;
}

/* ============ 时间线 ============ */
function renderTimeline(){
  const s = $("#s-timeline");
  const groups = {};
  D.projects.forEach(p=>{
    let y = p.stage==="运行"||p.stage==="达产"||p.stage==="投产" ? (p.online?p.online.slice(0,4):"已投产")
      : (p.latest_plan ? p.latest_plan.slice(0,4) : "未定");
    (groups[y]=groups[y]||[]).push(p);
  });
  const keys = Object.keys(groups).sort((a,b)=>{
    const na=parseInt(a), nb=parseInt(b);
    if(isNaN(na)) return 1; if(isNaN(nb)) return -1; return na-nb;
  });
  let h = `<div class="card"><div class="ch"><div><h2>按预计投产时间排列</h2>
    <div class="desc">每条左侧色条代表当前阶段：<span class="chip s-a">绿=已投产</span>
    <span class="chip s-t">黄=试车</span><span class="chip s-c">蓝=在建</span><span class="chip s-p">紫=计划</span>。
    点击展开该项目全部进展事实与来源。</div></div></div><div class="cb"><div class="tl">`;
  keys.forEach(y=>{
    const list = groups[y].sort((a,b)=>b.cap-a.cap);
    const sum = list.reduce((a,p)=>a+p.cap,0);
    h += `<div class="tl-row"><div class="tl-y">${esc(y)}<div style="font-size:10px;font-weight:400;color:#94a3b8;margin-top:2px">${list.length}项<br>${fmt(sum)}万t</div></div><div class="tl-b">`;
    list.forEach(p=>{
      const cls = p.stage==="试车"?"var(--t)":(["投产","达产","运行"].includes(p.stage)?"var(--a)":
        ["中交","设备安装","建设","开工"].includes(p.stage)?"var(--c)":"var(--p)");
      const seg = Math.min(100, p.cap/260*100);
      h += `<div class="tl-item" onclick="openP('${p.id}')" style="border-left-color:${cls}">
        <div class="r1"><span class="nm">${esc(p.name)}</span>${stageChip(p.stage)}
          <span class="chip ${p.nature==='置换'?'s-r':'s-x'}">${esc(p.nature)}</span>
          <span class="chip s-x">${esc(p.prov)}</span>
          <span class="mono" style="margin-left:auto;font-weight:700">${fmt(p.cap)} 万吨/年</span></div>
        <div class="mt">${esc(p.owner)} ｜ ${esc(p.proccls)} ｜ 预计 <b>${esc(p.latest_plan||"未披露")}</b>
          ${p.delay&&p.delay.startsWith("是")?`<span class="chip s-r sm">${esc(p.delay)}</span>`:""}</div>
        <div class="mt" style="color:#7c8ba1">${esc((p.last||{}).desc||"").slice(0,110)}</div>
        <div class="bars"><div class="seg" style="width:${seg}%;background:${cls};min-width:3px"></div></div>
      </div>`;
    });
    h += `</div></div>`;
  });
  h += `</div></div></div>`;
  s.innerHTML = h;
}

/* ============ 年度产能 ============ */
function renderCapacity(){
  const s = $("#s-capacity");
  const rows = YA;
  const W = 1180, H = 420, PL = 62, PR = 30, PT = 34, PB = 78;
  const maxV = Math.max(...rows.map(r=>r.nominal), 100) * 1.18;
  const bw = (W-PL-PR)/rows.length;
  const y2 = v => PT + (H-PT-PB) * (1 - v/maxV);
  const cols = [["actual","已投产","#0b8457"],["trial","试车/调试","#b8860b"],
                ["build","建设中","#0f6fc5"],["plan","计划/仅批文","#8b5cf6"]];
  let svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="inherit">
    <text x="${PL}" y="16" font-size="12" font-weight="700" fill="#12263f">万吨/年</text>`;
  for(let i=0;i<=5;i++){
    const v = maxV/5*i, yy = y2(v);
    svg += `<line x1="${PL}" y1="${yy}" x2="${W-PR}" y2="${yy}" stroke="${i===0?'#94a3b8':'#eef2f6'}" stroke-width="1"/>
            <text x="${PL-8}" y="${yy+4}" font-size="10" fill="#94a3b8" text-anchor="end">${Math.round(v)}</text>`;
  }
  rows.forEach((r,i)=>{
    const x = PL + i*bw + bw*0.22, w = bw*0.56;
    let acc = 0;
    cols.forEach(([k,lbl,col])=>{
      const v = r[k]; if(v<=0) return;
      const hh = (H-PT-PB)*(v/maxV);
      svg += `<rect x="${x}" y="${y2(acc+v)}" width="${w}" height="${hh}" fill="${col}" rx="2">
        <title>${r.y} ${lbl}：${fmt(v)} 万吨/年</title></rect>`;
      acc += v;
    });
    svg += `<text x="${x+w/2}" y="${y2(acc)-7}" font-size="11.5" font-weight="700" fill="#12263f" text-anchor="middle">${fmt(acc)}</text>`;
    svg += `<text x="${x+w/2}" y="${H-PB+20}" font-size="12" font-weight="700" fill="#334155" text-anchor="middle">${r.y}</text>`;
    svg += `<text x="${x+w/2}" y="${H-PB+36}" font-size="10" fill="#94a3b8" text-anchor="middle">${r.units}套/${r.ids.length}项</text>`;
    if(r.repl>0) svg += `<text x="${x+w/2}" y="${H-PB+51}" font-size="10" fill="#c0392b" text-anchor="middle">退出${fmt(r.repl)}</text>`;
  });
  svg += `<line x1="${PL}" y1="${H-PB}" x2="${W-PR}" y2="${H-PB}" stroke="#94a3b8" stroke-width="1.5"/></svg>`;

  // 累计曲线
  const W2=1180,H2=270,PL2=62,PB2=54;
  let cum=0; const pts=[];
  rows.forEach(r=>{ cum+=r.net; pts.push({y:r.y,v:cum,base:r.net}); });
  const maxC = Math.max(...pts.map(p=>p.v), 100)*1.08;
  const yv = v => 26 + (H2-26-PB2)*(1-v/maxC);
  const xv = i => PL2 + (W2-PL2-40)*(pts.length===1?0.5:i/(pts.length-1));
  let svg2 = `<svg viewBox="0 0 ${W2} ${H2}" xmlns="http://www.w3.org/2000/svg" font-family="inherit">
    <text x="${PL2}" y="15" font-size="12" font-weight="700" fill="#12263f">累计净新增产能（万吨/年）</text>`;
  for(let i=0;i<=4;i++){ const v=maxC/4*i, yy=yv(v);
    svg2+=`<line x1="${PL2}" y1="${yy}" x2="${W2-40}" y2="${yy}" stroke="#eef2f6"/>
      <text x="${PL2-8}" y="${yy+4}" font-size="10" fill="#94a3b8" text-anchor="end">${Math.round(v)}</text>`; }
  if(pts.length>1){
    svg2+=`<polyline points="${pts.map((p,i)=>`${xv(i)},${yv(p.v)}`).join(' ')}" fill="none" stroke="#0f6fc5" stroke-width="2.5"/>`;
    svg2+=`<polygon points="${xv(0)},${yv(0)} ${pts.map((p,i)=>`${xv(i)},${yv(p.v)}`).join(' ')} ${xv(pts.length-1)},${yv(0)}" fill="#0f6fc5" opacity=".08"/>`;
  }
  pts.forEach((p,i)=>{
    svg2+=`<circle cx="${xv(i)}" cy="${yv(p.v)}" r="4" fill="#fff" stroke="#0f6fc5" stroke-width="2.5">
      <title>${p.y}：累计 ${fmt(p.v)} 万吨/年（当年净增 ${fmt(p.base)}）</title></circle>
      <text x="${xv(i)}" y="${yv(p.v)-9}" font-size="10.5" font-weight="700" fill="#12263f" text-anchor="middle">${fmt(p.v)}</text>
      <text x="${xv(i)}" y="${H2-PB2+18}" font-size="11" font-weight="600" fill="#334155" text-anchor="middle">${p.y}</text>`;
  });
  svg2+=`</svg>`;

  s.innerHTML = `
  <div class="card"><div class="ch"><div><h2>年度新增产能（四类互斥堆叠）</h2>
    <div class="desc">每根柱子 = 该年全部装置的名义新增，按产能状态拆分。注意：只有绿色部分在当年是真实供应。</div></div></div>
    <div class="cb"><div class="chart">${svg}</div>
      <div class="legend">${cols.map(([k,l,c])=>`<span><i style="background:${c}"></i>${l}</span>`).join("")}
        <span style="color:#c0392b"><i style="background:#c0392b"></i>替代退出旧产能（单列，不参与堆叠）</span></div>
    </div></div>

  <div class="card"><div class="ch"><h2>累计净新增与期末产能推演</h2></div>
    <div class="cb"><div class="chart">${svg2}</div></div></div>

  <div class="card"><div class="ch"><div><h2>年度汇总表</h2>
    <div class="desc">净新增 = 名义新增 − 替代退出。占比以 ${fmt(D.base)} 万吨现有产能为基数。</div></div></div>
    <div class="tw"><table>
      <thead><tr><th>年份</th><th>已投产</th><th>试车/调试</th><th>建设中</th><th>计划/仅批文</th>
        <th>替代退出</th><th>名义新增</th><th>净新增</th><th>占现有产能</th><th>装置</th><th>项目</th></tr></thead>
      <tbody>${rows.map(r=>`<tr>
        <td class="nm">${r.y}</td>
        <td class="num" style="color:#0b8457;font-weight:600">${r.actual?fmt(r.actual):"—"}</td>
        <td class="num" style="color:#b8860b;font-weight:600">${r.trial?fmt(r.trial):"—"}</td>
        <td class="num" style="color:#0f6fc5;font-weight:600">${r.build?fmt(r.build):"—"}</td>
        <td class="num" style="color:#8b5cf6;font-weight:600">${r.plan?fmt(r.plan):"—"}</td>
        <td class="num del">${r.repl?fmt(r.repl):"—"}</td>
        <td class="num"><b>${fmt(r.nominal)}</b></td>
        <td class="num"><b>${fmt(r.net)}</b></td>
        <td class="num">${fmt(r.net/D.base*100,2)}%</td>
        <td class="num">${r.units}</td><td class="num">${r.ids.length}</td>
      </tr>`).join("")}</tbody>
    </table></div></div>

  <div class="card"><div class="ch"><div><h2>工艺路线结构与边际影响</h2>
    <div class="desc">新增产能按路线拆开，才能看出这一轮扩产在改变什么。</div></div></div>
    <div class="cb" id="routeBox"></div></div>`;

  // 路线
  const rb = {};
  D.projects.forEach(p=>{
    const k = p.proccls;
    rb[k] = rb[k] || {cap:0, units:0, ids:new Set(), now:0};
    rb[k].cap += p.cap; rb[k].units += p.nunit; rb[k].ids.add(p.id);
    if(["运行","达产","投产","试车"].includes(p.stage)) rb[k].now += p.cap;
  });
  const baseMap = {"油制（炼化副产丙烯）":(D.routebase.oil||{}).capacity_wan,
    "煤制（CTO/MTO/MTP）":(D.routebase.coal||{}).capacity_wan,
    "丙烷脱氢（PDH）":(D.routebase.pdh||{}).capacity_wan};
  const interp = {"油制（炼化副产丙烯）":"大型炼化一体化配套，成本锚定石脑油/原油，规模大、牌号全，是本轮扩产主力",
    "煤制（CTO/MTO/MTP）":"成本锚定煤价，高度集中于西北（新疆/宁夏/陕西/内蒙古），产品外运半径是硬约束",
    "丙烷脱氢（PDH）":"成本锚定丙烷进口价，价差敏感度最高，历史上出现过'建成后择机开车'",
    "外购丙烯聚合":"无自有丙烯，成本随行就市，抗周期能力最弱"};
  const ks = Object.keys(rb).sort((a,b)=>rb[b].cap-rb[a].cap);
  const maxt = Math.max(...ks.map(k=>rb[k].cap),1);
  $("#routeBox").innerHTML = `<table>
    <thead><tr><th>工艺归类</th><th>新增产能</th><th>其中已试车/投产</th><th>装置</th><th>项目</th>
      <th>现有产能</th><th>新增/现有</th><th>边际影响</th></tr></thead>
    <tbody>${ks.map(k=>{ const a=rb[k], ex=baseMap[k];
      return `<tr><td class="nm">${esc(k)}</td>
        <td class="num"><b>${fmt(a.cap)}</b><div class="bar-h" style="width:90px;margin-left:auto">
          <span style="width:${a.cap/maxt*100}%;background:#0f6fc5"></span></div></td>
        <td class="num" style="color:#0b8457">${fmt(a.now)}</td>
        <td class="num">${a.units}</td><td class="num">${a.ids.size}</td>
        <td class="num">${ex?fmt(ex):"—"}</td>
        <td class="num">${ex?fmt(a.cap/ex*100,1)+"%":"—"}</td>
        <td style="font-size:11.5px;color:#475569;max-width:420px">${esc(interp[k]||"")}</td></tr>`;
    }).join("")}</tbody></table>`;
}

/* ============ 地图 ============ */
const GEO = @@GEO@@;
function renderMap(){
  const s = $("#s-map");
  const agg = {};
  D.projects.forEach(p=>{
    agg[p.prov] = agg[p.prov] || {cap:0, n:0, now:0, ids:[], names:[]};
    agg[p.prov].cap += p.cap; agg[p.prov].n++;
    if(["运行","达产","投产","试车"].includes(p.stage)) agg[p.prov].now += p.cap;
    agg[p.prov].ids.push(p.id); agg[p.prov].names.push(p.name);
  });
  const maxC = Math.max(...Object.values(agg).map(a=>a.cap),1);
  const colorOf = v => { if(!v) return "#f1f5f9";
    const t = Math.pow(v/maxC, 0.55);
    const r = Math.round(230 - 190*t), g = Math.round(240 - 120*t), b = Math.round(248 - 60*t);
    return `rgb(${r},${g},${b})`; };
  let shapes = "";
  GEO.features.forEach(f=>{
    const nm = f.name || "";
    const a = agg[nm];
    const d = f.d || "";
    shapes += `<path class="prov-shape" data-p="${esc(nm)}" d="${d}" fill="${colorOf(a?a.cap:0)}"></path>`;
  });
  s.innerHTML = `
  <div class="card"><div class="ch"><div><h2>项目区域分布</h2>
    <div class="desc">颜色深浅 = 该省跟踪产能合计（万吨/年）。鼠标悬停看明细，点击进入该省项目。未着色的省份无跟踪项目。</div></div></div>
    <div class="cb">
      <div style="display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap">
        <div class="mapwrap" style="flex:1;min-width:520px"><svg viewBox="@@VIEWBOX@@" xmlns="http://www.w3.org/2000/svg">${shapes}</svg></div>
        <div style="width:300px;flex-shrink:0">
          <h4 style="font-size:11.5px;color:var(--mute);letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px">产能分布 TOP</h4>
          <div id="mapLegend"></div>
        </div>
      </div>
    </div></div>
  <div class="card"><div class="ch"><h2>区域汇总表</h2></div>
    <div class="tw"><table><thead><tr><th>省份</th><th>区域</th><th>已投产</th><th>试车</th>
      <th>在建+计划</th><th>跟踪产能合计</th><th>占全国现有产能</th><th>装置</th><th>项目</th></tr></thead>
      <tbody>${D.region.map(r=>`<tr>
        <td class="nm">${esc(r["省份"])}</td><td>${esc(r["区域"])}</td>
        <td class="num">${r["已投产(万吨/年)"]?fmt(r["已投产(万吨/年)"]):"—"}</td>
        <td class="num">${r["试车调试(万吨/年)"]?fmt(r["试车调试(万吨/年)"]):"—"}</td>
        <td class="num">${fmt(r["在建+计划(万吨/年)"])}</td>
        <td class="num"><b>${fmt(r["跟踪产能合计(万吨/年)"])}</b></td>
        <td class="num">${fmt(r["跟踪产能合计(万吨/年)"]/D.base*100,2)}%</td>
        <td class="num">${r["涉及装置数"]}</td><td class="num">${r["涉及项目数"]}</td></tr>`).join("")}</tbody></table></div></div>`;

  const leg = Object.entries(agg).sort((a,b)=>b[1].cap-a[1].cap).slice(0,14);
  $("#mapLegend").innerHTML = leg.map(([p,a])=>`
    <div style="margin-bottom:7px;cursor:pointer" onclick="filterProv('${esc(p)}')">
      <div style="display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:2px">
        <span style="font-weight:600">${esc(p)}</span><span class="mono">${fmt(a.cap)} 万吨</span></div>
      <div class="bar-h" style="height:14px;margin:0"><span style="width:${a.cap/maxC*100}%;background:${colorOf(a.cap)}"></span></div>
    </div>`).join("");

  const tip = $("#mtip");
  s.querySelectorAll(".prov-shape").forEach(p=>{
    const nm = p.dataset.p, a = agg[nm];
    p.addEventListener("mousemove", e=>{
      if(!a){ tip.innerHTML = `<b>${esc(nm)}</b><br><span style="color:#9db8d6">无跟踪项目</span>`; }
      else { tip.innerHTML = `<b>${esc(nm)}</b>　${a.n} 个项目<br>跟踪产能 <b>${fmt(a.cap)}</b> 万吨/年<br>
        <span style="color:#9db8d6">其中已试车/投产 ${fmt(a.now)} 万吨</span>`; }
      tip.style.left = (e.clientX+14)+"px"; tip.style.top = (e.clientY+14)+"px"; tip.classList.add("on");
    });
    p.addEventListener("mouseleave", ()=>tip.classList.remove("on"));
    if(a) p.addEventListener("click", ()=>filterProv(nm));
  });
}

function filterProv(prov){
  ST.prov = prov; ST.y = ""; ST.stage = ""; ST.owner = ""; ST.proc = ""; ST.nature = ""; ST.capMin = 0; ST.q = "";
  go("table"); renderTable();
}

/* ============ 明细表 ============ */
const ST = {prov:"", y:"", stage:"", owner:"", proc:"", nature:"", capMin:0, q:"", sort:"cap", dir:-1, starOnly:false};
function renderTable(){
  const s = $("#s-table");
  const owners = [...new Set(D.projects.map(p=>p.owner))].sort();
  const provs = [...new Set(D.projects.map(p=>p.prov))].sort();
  const procs = [...new Set(D.projects.map(p=>p.proccls))].sort();
  s.innerHTML = `
  <div class="card">
    <div class="filters">
      <label>省份 <select id="f-prov"><option value="">全部</option>${provs.map(p=>`<option ${ST.prov===p?"selected":""}>${esc(p)}</option>`).join("")}</select></label>
      <label>预计投产 <select id="f-y"><option value="">全部</option>
        ${[...new Set(D.projects.map(p=>p.latest_plan?p.latest_plan.slice(0,4):"未定"))].sort().map(y=>`<option ${ST.y===y?"selected":""}>${esc(y)}</option>`).join("")}</select></label>
      <label>阶段 <select id="f-stage"><option value="">全部</option>
        ${["试车","中交","设备安装","建设","开工","核准","环评批复","环评受理","备案","拟建","投产","达产","运行"].map(x=>`<option ${ST.stage===x?"selected":""}>${esc(x)}</option>`).join("")}</select></label>
      <label>工艺 <select id="f-proc"><option value="">全部</option>${procs.map(p=>`<option ${ST.proc===p?"selected":""}>${esc(p)}</option>`).join("")}</select></label>
      <label>性质 <select id="f-nature"><option value="">全部</option>
        ${["新建","扩建","置换","技改"].map(x=>`<option ${ST.nature===x?"selected":""}>${esc(x)}</option>`).join("")}</select></label>
      <label>业主 <select id="f-owner"><option value="">全部</option>${owners.map(p=>`<option ${ST.owner===p?"selected":""}>${esc(p)}</option>`).join("")}</select></label>
      <label>产能 ≥ <input id="f-cap" type="number" value="${ST.capMin||""}" placeholder="万吨" style="width:74px"></label>
      <label>搜索 <input id="f-q" value="${esc(ST.q)}" placeholder="项目/业主/园区" style="width:150px"></label>
      <label><input type="checkbox" id="f-star" ${ST.starOnly?"checked":""}> 只看自选</label>
      <button class="btn" id="f-reset">重置</button>
      <button class="btn pri" id="f-export" style="margin-left:auto">导出当前结果 CSV</button>
    </div>
    <div class="tw"><table id="ptable">
      <thead><tr>
        <th data-k="star" style="width:30px"></th>
        <th data-k="id">编号<span class="ar">▾</span></th>
        <th data-k="owner">业主 / 集团<span class="ar">▾</span></th>
        <th data-k="name">项目名称<span class="ar">▾</span></th>
        <th data-k="prov">省份<span class="ar">▾</span></th>
        <th data-k="cap">产能<span class="ar">▾</span></th>
        <th data-k="proccls">工艺<span class="ar">▾</span></th>
        <th data-k="nature">性质<span class="ar">▾</span></th>
        <th data-k="stage">当前阶段<span class="ar">▾</span></th>
        <th data-k="latest_plan">最新预计投产<span class="ar">▾</span></th>
        <th data-k="delay">延期<span class="ar">▾</span></th>
        <th>最新进展</th>
      </tr></thead><tbody id="ptbody"></tbody>
    </table></div>
  </div>`;
  const bind = (id, k, num) => { const e=$("#"+id); if(!e) return;
    e.addEventListener("input", ()=>{ ST[k] = num ? (parseFloat(e.value)||0) : e.value; renderRows(); });
    e.addEventListener("change", ()=>{ ST[k] = num ? (parseFloat(e.value)||0) : e.value; renderRows(); }); };
  bind("f-prov","prov"); bind("f-y","y"); bind("f-stage","stage"); bind("f-proc","proc");
  bind("f-nature","nature"); bind("f-owner","owner"); bind("f-cap","capMin",true); bind("f-q","q");
  $("#f-star").addEventListener("change", e=>{ ST.starOnly = e.target.checked; renderRows(); });
  $("#f-reset").addEventListener("click", ()=>{ Object.assign(ST,{prov:"",y:"",stage:"",owner:"",proc:"",nature:"",capMin:0,q:"",starOnly:false}); renderTable(); });
  $("#f-export").addEventListener("click", exportCSV);
  s.querySelectorAll("thead th[data-k]").forEach(th=>{
    th.addEventListener("click", ()=>{ const k = th.dataset.k; if(k==="star") return;
      if(ST.sort===k) ST.dir *= -1; else { ST.sort=k; ST.dir = (k==="cap")?-1:1; }
      renderRows(); });
  });
  renderRows();
}
function curRows(){
  let r = D.projects.filter(p=>{
    if(ST.prov && p.prov!==ST.prov) return false;
    if(ST.y && (p.latest_plan?p.latest_plan.slice(0,4):"未定")!==ST.y) return false;
    if(ST.stage && p.stage!==ST.stage) return false;
    if(ST.proc && p.proccls!==ST.proc) return false;
    if(ST.nature && !p.nature.includes(ST.nature)) return false;
    if(ST.owner && p.owner!==ST.owner) return false;
    if(ST.capMin && p.cap<ST.capMin) return false;
    if(ST.starOnly && !isStar(p.id)) return false;
    if(ST.q){ const q=ST.q.toLowerCase();
      const hay = (p.name+p.owner+p.group+p.park+p.city+p.prov+p.id).toLowerCase();
      if(!hay.includes(q)) return false; }
    return true;
  });
  const k = ST.sort, d = ST.dir;
  r.sort((a,b)=>{ let va=a[k], vb=b[k];
    if(typeof va==="number"||typeof vb==="number") return ((va||0)-(vb||0))*d;
    va=String(va||""); vb=String(vb||"");
    return va.localeCompare(vb,"zh")*d; });
  return r;
}
function renderRows(){
  const r = curRows();
  const tb = $("#ptbody");
  tb.innerHTML = r.map((p,i)=>`<tr class="${i%2?'zebra':''}" onclick="openP('${p.id}')">
    <td onclick="event.stopPropagation();toggleStar('${p.id}',this)">
      <button class="star ${isStar(p.id)?'on':''}">${isStar(p.id)?'★':'☆'}</button></td>
    <td class="mono" style="font-size:11px;color:#64748b">${p.id}</td>
    <td class="ow"><div style="color:#12263f;font-weight:600;font-size:11.5px">${esc(p.owner)}</div>
      <div style="font-size:10.5px">${esc(p.group)}</div></td>
    <td class="nm">${esc(p.name)}<div style="font-weight:400;font-size:10.5px;color:#94a3b8">${esc(p.park||p.city)}</div></td>
    <td>${esc(p.prov)}</td>
    <td class="num"><b>${fmt(p.cap)}</b>${p.nunit>1?`<div style="font-size:10px;color:#94a3b8">${p.nunit}套</div>`:""}</td>
    <td style="font-size:11px">${esc(p.proc)}</td>
    <td><span class="chip ${p.nature==='置换'?'s-r':'s-x'}">${esc(p.nature)}</span></td>
    <td>${stageChip(p.stage)}<div style="font-size:10px;color:#94a3b8;margin-top:2px">${esc(p.capstate)}</div></td>
    <td class="num" style="font-size:11.5px">${esc(p.latest_plan||"未披露")}</td>
    <td style="font-size:10.5px" class="${p.delay&&p.delay.startsWith('是')?'del':''}">${esc(p.delay||"")}</td>
    <td style="font-size:10.5px;color:#64748b;max-width:300px">${esc((p.last||{}).desc||"").slice(0,80)}
      <div style="color:#94a3b8;font-size:10px">${esc((p.last||{}).fact||"")}</div></td>
  </tr>`).join("");
  if(!r.length) tb.innerHTML = '<tr><td colspan="12"><div class="empty">没有符合条件的项目</div></td></tr>';
  const tot = r.reduce((a,p)=>a+p.cap,0);
  const sum = document.createElement("tr");
  sum.innerHTML = `<td colspan="5" style="font-weight:700;background:#f8fafc">筛选结果合计（${r.length} 个项目）</td>
    <td class="num" style="font-weight:700;background:#f8fafc">${fmt(tot)}</td>
    <td colspan="6" style="background:#f8fafc;font-size:11px;color:#64748b">占现有产能 ${fmt(tot/D.base*100,2)}%</td>`;
  if(r.length) tb.appendChild(sum);
}
function exportCSV(){
  const r = curRows();
  const hd = ["项目编号","业主","所属集团","项目名称","省份","地市","园区","设计产能(万吨/年)","装置套数",
    "工艺路线","项目性质","当前阶段","产能状态","首次预计投产","最新预计投产","是否延期",
    "实质放量年份","最新进展","最新进展日期","证据等级","关注要点"];
  const rows = r.map(p=>[p.id,p.owner,p.group,p.name,p.prov,p.city,p.park,p.cap,p.nunit,
    p.proccls,p.nature,p.stage,p.capstate,p.first_plan,p.latest_plan,p.delay,p.ramp,
    (p.last||{}).desc||"",(p.last||{}).fact||"",(p.last||{}).grade||"",p.watch]);
  const csv = "\ufeff" + [hd, ...rows].map(x=>x.map(v=>`"${String(v==null?"":v).replace(/"/g,'""')}"`).join(",")).join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  a.download = "@@PROD@@" + "项目明细_筛选结果.csv"; a.click();
}

/* ============ 延期与缺口 ============ */
function renderDelayed(){
  const s = $("#s-delayed");
  const delayed = D.projects.filter(p=>p.delay && p.delay.startsWith("是")).sort((a,b)=>b.cap-a.cap);
  const defTot = D.deferred.reduce((a,d)=>a+d.capacity_wan,0);
  const t = YA.find(x=>x.y===String(D.as_of_year))||{nominal:0};
  s.innerHTML = `
  <div class="callout warn">
    <b>隐性供给缺口 ${fmt(defTot)} 万吨/年</b>（占 ${D.as_of_year} 年名义新增的 ${t.nominal?fmt(defTot/t.nominal*100,0):0}%）。
    判定规则是机械的、可审计的（R1 已明确延期≥6个月 / R2 计划年内投产但仍在批文阶段 / R3 主体仍在设备安装且无试车报道），不靠主观打分。
  </div>
  <div class="card"><div class="ch"><div><h2>隐性供给缺口明细</h2>
    <div class="desc">这些项目在名义计划上算作"当年投产"，但工程证据不支持年内形成供应。</div></div></div>
    <div class="tw"><table><thead><tr><th>项目编号</th><th>业主</th><th>项目</th><th>省份</th>
      <th>当前阶段</th><th>产能</th><th>最新预计投产</th><th>判定规则</th></tr></thead>
      <tbody>${D.deferred.sort((a,b)=>b.capacity_wan-a.capacity_wan).map(d=>`<tr onclick="openP('${d.project_id}')">
        <td class="mono" style="font-size:11px">${d.project_id}</td>
        <td class="ow">${esc(d.owner)}</td>
        <td class="nm">${esc(d.project_name)}</td>
        <td>${esc(d.province)}</td><td>${stageChip(d.stage)}</td>
        <td class="num"><b class="hl-num">${fmt(d.capacity_wan)}</b></td>
        <td class="num">${esc(d.latest_plan_date)}</td>
        <td style="font-size:11px;color:#c0392b">${esc(d.reasons.join("；"))}</td></tr>`).join("")}
      <tr><td colspan="5" style="font-weight:700;background:#f8fafc">合计</td>
        <td class="num" style="font-weight:700;background:#f8fafc;color:#c0392b">${fmt(defTot)}</td>
        <td colspan="2" style="background:#f8fafc"></td></tr></tbody></table></div></div>

  <div class="card"><div class="ch"><div><h2>已明确延期的项目</h2>
    <div class="desc">按项目档案中记录的最新延期幅度排序。延期原因须在正文中区分工程原因与市场原因。</div></div></div>
    <div class="tw"><table><thead><tr><th>项目编号</th><th>项目</th><th>业主</th><th>产能</th>
      <th>首提预计投产</th><th>最新预计投产</th><th>延期情况</th><th>延期原因判断</th></tr></thead>
      <tbody>${delayed.map(p=>`<tr onclick="openP('${p.id}')">
        <td class="mono" style="font-size:11px">${p.id}</td>
        <td class="nm">${esc(p.name)}</td><td class="ow">${esc(p.owner)}</td>
        <td class="num"><b>${fmt(p.cap)}</b></td>
        <td class="num">${esc(p.first_plan)}</td><td class="num">${esc(p.latest_plan)}</td>
        <td style="color:#c0392b;font-size:11px">${esc(p.delay)}${p.delay_m?`（${p.delay_m}个月）`:""}</td>
        <td style="font-size:11px;color:#475569;max-width:380px">${esc(p.unc).slice(0,180)}</td></tr>`).join("")}</tbody></table></div></div>

  <div class="card"><div class="ch"><h2>预计投产时间变更史（全部项目）</h2></div>
    <div class="tw"><table><thead><tr><th>项目</th><th>事实日期</th><th>变更类型</th>
      <th>变更前</th><th>变更后</th><th>依据</th><th>等级</th></tr></thead>
      <tbody>${D.projects.flatMap(p=>p.hist.map(h=>`
        <tr onclick="openP('${p.id}')"><td class="nm">${esc(p.name)}</td>
        <td class="num">${esc(h.fact)}</td>
        <td><span class="chip ${h.chg==='延期'?'s-r':(h.chg==='提前'?'s-a':'s-x')}">${esc(h.chg)}</span></td>
        <td class="num">${esc(h.from||"—")}</td><td class="num">${esc(h.to||"—")}</td>
        <td style="font-size:11px;max-width:440px">${esc(h.desc).slice(0,150)}</td>
        <td>${gradeChip(h.grade)}</td></tr>`)).join("")}</tbody></table></div></div>`;
}

/* ============ 去重与剔除 ============ */
function renderDedup(){
  const s = $("#s-dedup");
  const typ = r => { for(const k of ["归属错误","混算","口径混算","不含PP","产品误认","产能误记","漏计",
    "立项口径","非新增","已投产","技改不增能","无法证实","口径冲突","产品性质","未逐项披露"])
    if(r.includes(k)) return k; return "重复披露"; };
  s.innerHTML = `
  <div class="callout ok">
    <b>去重不是删除，是留痕。</b>每一条被排除在统计之外的记录都写明理由与依据来源，
    使得后来者能看到"为什么不算"，避免同一个错误被反复引入。当前已剔除 <b>${D.excluded.length}</b> 条。
  </div>
  <div class="card"><div class="ch"><div><h2>剔除与重复披露清单</h2>
    <div class="desc">★标记的为最高风险类型：归属错误、口径混算、产品误认、漏计——这四类会直接让统计结果偏离真实值。</div></div></div>
    <div class="tw"><table><thead><tr><th style="width:36px">#</th><th>被剔除的记录</th>
      <th style="width:110px">类型</th><th>剔除理由与依据</th></tr></thead>
      <tbody>${D.excluded.map((e,i)=>{ const t = typ(e.reason);
        const hi = ["归属错误","口径混算","不含PP","产品误认","漏计"].includes(t);
        return `<tr><td class="num">${i+1}</td>
          <td class="nm">${esc(e.name)}</td>
          <td><span class="chip ${hi?'s-r':'s-x'}">${esc(t)}</span></td>
          <td style="font-size:11.5px;color:#475569;line-height:1.7">${esc(e.reason)}</td></tr>`;
      }).join("")}</tbody></table></div></div>

  <div class="card"><div class="ch"><h2>去重规则（可复制的判定逻辑）</h2></div>
    <div class="cb"><div class="note">
<b>规则 1｜一个项目 = 一个编号。</b>判定"同一项目"的四要素：业主主体（去后缀归一）+ 厂址（省份地市园区）+ 项目主体名称 + 产品。
四要素一致即为同一项目，哪怕来源给的名称不同（东明盛海 vs 东明中油）、产能数字不同（30 vs 50 万吨）。

<b>规则 2｜同一项目的多条生产线不拆项目、也不合并成"一套装置"。</b>写入 units[]，
按 U1/U2 分线登记。中沙古雷 40+55、华锦阿美 50+50、中煤榆林 30+30、镇海 5#PP 都是这种情况。

<b>规则 3｜归属要追到"实际运营主体"，不能停在"大股东"。</b>华锦阿美 2×50 万吨的运营主体是合资公司华锦阿美，
不是北方华锦集团。行业资讯把两者混为一谈，导致"北方华锦 50×2"与"华锦阿美 2×50"被重复登记，虚增 100 万吨。

<b>规则 4｜"合计"与"单套"必须区分。</b>宝丰的"50 万吨 PP"是 C2-C5 项目的单套规模，
而宁东四期本体只有 25 万吨；两者被行业资讯混算成"宝丰四期 50 万吨"。中煤榆林早期环评的"55 万吨 PP"与最终"2×30"也是同类问题。

<b>规则 5｜产品线不能串。</b>中沙古雷 PE 是 40+60=100 万吨、PP 是 40+55=95 万吨，
两个"95 万吨"纯属数字巧合，极易互相写错。上海石化新建 8 套装置里根本没有 PP。

<b>规则 6｜立项口径 ≠ 建设口径，以最终批复与施工通稿为准。</b>中煤榆林环评早期 35PE+55PP，最终建 2×30PP；
荣信早期 45 万吨，最终 40 万吨。立项数字只能用于说明"口径变过"，不能用于统计。

<b>规则 7｜已投产的不再算新增。</b>宝丰内蒙古 3×50、东华能源茂名一期 40 万吨、埃克森美孚惠州一期 95.5 万吨
都已包含在现有产能基数内，重复登记会双重计算。

<b>规则 8｜检修复产不是新增产能。</b>2026 年 8-9 月万华 75 + 斯尔邦 70 + 金发 60 + 万达天弘 45 + 齐翔腾达 42 = 292 万吨复产，
属于存量装置负荷恢复，会显著改变当季供应量，但产能净增为零。单独列示，不进新增表。

<b>规则 9｜技改不增能的要剔除，增能的要核对退出量。</b>独山子 14 万吨 PP 适应性改造明确"产能不变"，剔除；
宁煤 MTP 技改名义新增 70 万吨，但属工艺升级替代，原装置退出量不明，必须标为"待核"而不是直接计入。
    </div></div></div>
  <div class="card"><div class="ch"><h2>待补证清单（明确的"未检索到公开报道"）</h2>
    <div class="desc">把"找不到"写下来，比假装找到更有价值——这些空白决定了哪些结论必须打问号。</div></div>
    <div class="cb"><div class="note bad" id="gapBox"></div></div></div>`;
  const gaps = [
    ["PP-P1-008","5#PP 是否于 2026 年 5 月初产出合格产品（会议目标）","若已达成本库低估约 40 万吨；若未达成则延期成立","镇海炼化、中石化工程部"],
    ["PP-P1-008","5#PP 究竟 30 万吨还是 50 万吨","直接影响 20 万吨的年度统计","宁波市发改委核准原文"],
    ["PP-P1-007","东明盛海 PP 试车/投产的任何公开报道","唯一支撑'2026-12 投产'的是行业资讯","东明石化官网、菏泽市生态环境局"],
    ["PP-P1-006","荣信化工 PP 试车/投产公开报道","设备安装仅 12%，年底投产存疑","兖矿能源公告、鄂尔多斯市政府"],
    ["PP-P1-004","宝丰宁东四期 PP 装置试车报道","公司仅称 12 月下旬出合格乙烯丙烯","宝丰能源公告、上证 e 互动"],
    ["PP-P1-005","宝丰 C2-C5 项目 50 万吨 PP 自 2023 环评后的任何进展","50 万吨完全无进度证据","宁东管委会、宝丰年报在建工程"],
    ["PP-P1-003","华锦阿美 PP 装置单独的中交或试车通稿","PP 进度全靠整批机械竣工清单推断","华锦阿美官网、盘锦市政府"],
    ["PP-P1-009","利华益维远第二套 20 万吨 PP 是否实际建设","按 40 万吨统计可能高估 20 万吨","维远股份年报在建工程"],
    ["PP-P3-016","广西石化 40 万吨 PP 是否已投产出料","已按'投产（需补证）'处理","广西石化官网、中国石油新闻中心"],
    ["PP-P3-024","中科炼化二期 PP 具体产能","本库未设数字","中科炼化环评报告书全文"],
    ["PP-P3-025","内蒙古大路项目 80 万吨聚烯烃中 PP 的拆分","本库未设数字","中国石化环评受理公示全文"],
    ["PP-P3-001","宝丰新疆 400 万吨项目是否有环评批复","目前仅到环评公示（C 级）+ 自媒体（D 级）","新疆生态环境厅、准东开发区"],
    ["PP-P3-008","茂名乙烯提质改造中原 PP 是否同步退出","决定 50 万吨是净增还是置换","茂名石化环评报告书"],
    ["PP-P3-009","扬子石化原 PP 是否同步退出","决定 40 万吨是净增还是置换","扬子石化环评报告书"],
    ["PP-P3-013","宁煤 MTP 技改原装置退出量","决定 70 万吨是净增还是置换","国家能源集团公告"],
    ["PP-P3-010","福建永荣 80 万吨 PP 的投产时间","本库用 2027-06 作工作假设，无来源","永荣控股官网"],
    ["PP-P3-011","上景新材 150 万吨是否分期/是否开工","单位投资强度仅 0.235 亿元/万吨，异常低","福建省生态环境厅环评批复"],
    ["PP-P3-015","桐昆钦州项目是否停工或缩减","原计划 2025-06 竣工，延期 24 个月无报道","桐昆股份公告"],
    ["PP-P3-019","乌石化 45 万吨 PP 实际开车时点","'转入生产准备'不等于投产","乌鲁木齐石化"],
    ["PP-P3-003","大连石化老厂关停时点与 PP 退出量","决定西中岛是净增还是置换","中国石油公告、大连市政府"],
    ["PP-P3-026","东华能源茂名二期是否启动","150-200 万吨为规划口径","东华能源公告"],
  ];
  $("#gapBox").innerHTML = gaps.map((g,i)=>
    `<div style="margin-bottom:7px"><b>${i+1}. [${g[0]}]</b> ${esc(g[1])}
     <div style="color:#7c2d12;font-size:11.5px;margin-top:1px">影响：${esc(g[2])}　→ 核实渠道：${esc(g[3])}</div></div>`).join("");
}

/* ============ 自选跟踪 ============ */
const LSKEY = "pp_tracker_star_v1";
function stars(){ try{ return JSON.parse(localStorage.getItem(LSKEY)||"[]"); }catch(e){ return []; } }
function isStar(id){ return stars().includes(id); }
function toggleStar(id, cell){
  let a = stars();
  a = a.includes(id) ? a.filter(x=>x!==id) : [...a, id];
  localStorage.setItem(LSKEY, JSON.stringify(a));
  if(cell){ const b = cell.querySelector(".star"); if(b){ const on = a.includes(id); b.classList.toggle("on",on); b.textContent = on?"★":"☆"; } }
  const rb = $("#watchBody"); if(rb) renderWatch();
}
function renderWatch(){
  const ids = stars();
  const list = D.projects.filter(p=>ids.includes(p.id));
  const box = $("#s-watch");
  if(!box) return;
  const body = $("#watchBody");
  if(!body) { renderWatchFull(); return; }
  body.innerHTML = list.length ? list.map(p=>`
    <tr onclick="openP('${p.id}')">
      <td><button class="star on" onclick="event.stopPropagation();toggleStar('${p.id}',this.closest('td'))">★</button></td>
      <td class="mono" style="font-size:11px">${p.id}</td>
      <td class="nm">${esc(p.name)}</td>
      <td class="ow">${esc(p.owner)}</td>
      <td>${stageChip(p.stage)}</td>
      <td class="num"><b>${fmt(p.cap)}</b></td>
      <td class="num">${esc(p.latest_plan||"—")}</td>
      <td style="font-size:11px;color:#475569;max-width:420px">${esc(p.watch)}</td>
    </tr>`).join("") : '<tr><td colspan="8"><div class="empty">还没有自选项目。到「明细表」点击 ☆ 收藏关键项目，这里会汇总成你的跟踪清单（保存在本机浏览器）。</div></td></tr>';
  $("#watchCount").textContent = list.length;
}
function renderWatchFull(){
  const s = $("#s-watch");
  s.innerHTML = `
  <div class="callout"><b>自选跟踪</b>保存在本机浏览器（localStorage），不上传、不需要账号。
    建议只收藏 5-10 个"会改变平衡表"的项目，并在每次数据更新后逐个核对进展。</div>
  <div class="card"><div class="ch"><div><h2>我的自选清单（<span id="watchCount">0</span>）</h2>
    <div class="desc">按对供应的边际影响 × 时间临近度排序。优先级 1 = 未来 6 个月内最可能改变平衡表的事。</div></div>
    <div><button class="btn" onclick="exportWatch()">导出清单 CSV</button></div></div>
    <div class="tw"><table><thead><tr><th style="width:30px"></th><th>编号</th><th>项目</th><th>业主</th>
      <th>阶段</th><th>产能</th><th>最新预计</th><th>跟踪要点</th></tr></thead>
      <tbody id="watchBody"></tbody></table></div></div>
  <div class="card"><div class="ch"><h2>建议优先跟踪清单（系统推荐）</h2></div>
    <div class="cb"><div class="note">
<b>优先级 1（未来 6 个月最可能改变平衡表）</b><br>
· 华锦阿美 100 万吨 —— 若 12 月试车，是 2026 年内最后一块大增量；且 PP 至今无独立中交通稿。<br>
· 镇海 5#PP —— "5 月出合格品"目标是否达成无任何报道，是全库最大信息缺口（口径还差 20 万吨）。<br>
· 荣信 40 万吨 —— 设备安装仅 12% 却报年底出产品，延期概率最高。<br>
· 宝丰宁东四期 25 万吨 —— 公司口径 12 月下旬出合格乙烯丙烯，年内确定性较高。<br><br>
<b>优先级 2（3-6 个月内见分晓）</b><br>
· 中沙古雷 95 万吨 —— 两条线已测试开车，11 月全面投产；关注乙烯投料后能否稳定供料。<br>
· 中煤榆林 60 万吨 —— 已出第一粒料，关注全流程负荷与商品量。<br>
· 东明盛海 35 万吨 —— 仅有行业口径的 12 月投产，无公司/政府侧确认。<br>
· 利华益维远 20 万吨 —— 已建成但"择机试生产"，是 PDH 路线的风向标。<br><br>
<b>优先级 3（2027 年变量，但现在就要建档）</b><br>
· 塔河炼化 50 万吨 / 中海壳牌三期 45 万吨 / 兖矿新疆 40 万吨 / 山能哈密 40 万吨。<br><br>
<b>优先级 4（长期变量，只做趋势判断）</b><br>
· 宝丰新疆 3×65 万吨 —— 远期最大变量，但仅到环评公示；宁煤 MTP 技改 70 万吨 —— 净增还是置换未定。
    </div></div></div>`;
  renderWatch();
}
function exportWatch(){
  const list = D.projects.filter(p=>isStar(p.id));
  const hd = ["项目编号","项目","业主","产能(万吨/年)","当前阶段","最新预计投产","跟踪要点"];
  const csv = "\ufeff" + [hd, ...list.map(p=>[p.id,p.name,p.owner,p.cap,p.stage,p.latest_plan,p.watch])]
    .map(x=>x.map(v=>`"${String(v==null?"":v).replace(/"/g,'""')}"`).join(",")).join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  a.download = "@@PROD@@" + "自选跟踪清单.csv"; a.click();
}

/* ============ 方法 ============ */
function renderMethod(){
  const s = $("#s-method");
  s.innerHTML = `
  <div class="card"><div class="ch"><h2>口径定义（引用本台账时必须带上这些限定）</h2></div>
    <div class="cb">
    <table><thead><tr><th style="width:150px">术语</th><th>定义</th><th>能否计入"有效供应"</th></tr></thead><tbody>
      <tr><td class="nm">已形成有效供应</td><td>装置已试车并稳定产出合格品，进入正常商品销售</td><td style="color:#0b8457;font-weight:700">可以</td></tr>
      <tr><td class="nm">试车 / 调试</td><td>装置已投料开车、产出过合格品，但未连续稳定运行、未进入常规销售</td><td class="del">不可以</td></tr>
      <tr><td class="nm">中交</td><td>施工完成、移交生产单位，尚未投料</td><td class="del">不可以</td></tr>
      <tr><td class="nm">设备安装 / 建设 / 开工</td><td>工程实施中</td><td class="del">不可以</td></tr>
      <tr><td class="nm">核准 / 环评批复 / 环评受理 / 备案 / 拟建</td><td>仅有批文或意向</td><td class="del">不可以</td></tr>
      <tr><td class="nm">替代退出</td><td>老旧装置关停或以新代旧中退出运行的产能</td><td>从供给中<strong>扣减</strong></td></tr>
    </tbody></table></div></div>

  <div class="card"><div class="ch"><h2>证据等级</h2></div><div class="cb">
    <table><thead><tr><th style="width:60px">等级</th><th>含义</th><th>典型来源</th></tr></thead><tbody>
      <tr><td>${gradeChip("A")}</td><td>一手权威</td><td>企业公告/定期报告、生态环境部门环评批复与公示原文、政府核准或备案文件、企业官方发布</td></tr>
      <tr><td>${gradeChip("B")}</td><td>一手转载或专业数据库</td><td>政府网站/权威媒体对一手文件的完整转述、金联创/卓创等专业数据库、券商研报</td></tr>
      <tr><td>${gradeChip("C")}</td><td>二手行业资讯</td><td>化工网/搜狐号/微信公号等对项目的整理与转述，数字可能滞后或口径不一</td></tr>
      <tr><td>${gradeChip("D")}</td><td>弱证据</td><td>百科、自媒体汇编、论坛帖子；仅用于线索定位，不单独支撑关键字段</td></tr>
    </tbody></table>
    <div class="note" style="margin-top:12px"><b>只有 A/B 级证据才能支撑"已试车/已投产"这类结论。</b>
    C 级来源可以做线索、可以证明"有人在这么说"，但不能作为事实基准。本台账中所有"预计投产时间"若仅来自 C 级，都在正文中标注了"行业口径"。</div>
  </div></div>

  <div class="card"><div class="ch"><h2>产能基数口径差异（必须并列披露）</h2></div><div class="cb">
    <table><thead><tr><th>口径</th><th>数值(万吨/年)</th><th>说明</th></tr></thead><tbody>
      ${D.bases.map(b=>`<tr class="${b.value_wan===D.base?'zebra':''}">
        <td class="nm">${esc(b.label)}${b.value_wan===D.base?' <span class="chip s-a sm">本看板基数</span>':''}</td>
        <td class="num"><b>${fmt(b.value_wan)}</b></td><td style="font-size:11.5px">${esc(b.note)}</td></tr>`).join("")}
    </tbody></table></div></div>

  <div class="card"><div class="ch"><h2>机构对 ${D.as_of_year} 年新增产能的预测分歧</h2>
    <div class="desc">同为行业资讯，结论相差近 200 万吨。本台账不用任何机构的总量倒推项目，只做逐项目工程证据加总，再用这张表判断自己站在市场预期的哪一侧。</div></div>
    <div class="cb"><table><thead><tr><th>来源</th><th>统计范围</th><th>数值(万吨/年)</th></tr></thead><tbody>
      ${D.divergence.map(d=>`<tr><td>${esc(d.source)}</td><td>${esc(d.scope)}</td>
        <td class="num"><b>${fmt(d.value_wan)}</b></td></tr>`).join("")}
    </tbody></table></div></div>

  <div class="card"><div class="ch"><h2>更新的制度：只追加，不覆盖</h2></div><div class="cb">
    <div class="note">
<b>1. 进展记录只追加。</b>发现新事实就新增一条，绝不改写已记录的 fact_date 与描述。旧记录永远保留，用于回溯"当初是怎么判断的、错在哪"。

<b>2. 预计投产时间用两段式。</b>首次预计（first_plan）写入后不修改；每次获知新口径，在变更史里追加一条（变更前 → 变更后 → 依据 → 来源）。
任何时候都能回答"这个项目一共改过几次口、每次是谁说的"。

<b>3. 事实日与消息日分开。</b>两者之差就是信息滞后。滞后超过 1 个月会被系统提示复核。

<b>4. 每条记录必须能追到来源。</b>没有 source_ids 的记录不成立，校验会直接拦下。
证据等级自评高于其来源最高等级的，也会告警。

<b>5. 阶段倒挂校验。</b>如果时间线上出现"投产"之后又有"环评受理"，要么是并线项目、要么是回填错误，系统会提示复核。
    </div></div></div>

  <div class="card"><div class="ch"><h2>不要做的换算</h2></div><div class="cb">
    <div class="note bad">
<b>本台账不把设计产能折算为年度产量。</b>
设计产能 × 开工率 = 产量，而开工率由价差驱动、逐月变化（如 2026 年 9 月近 40 套装置停车、涉产能 900 多万吨），
属于另一套跟踪体系。把两者混在一起，会得出看似精确、实则错误的"供应增量"。

新装置投产后的真实节奏也不是线性的：${esc(D.ramp.note||"")}
首年实际产量通常只有设计产能的 ${(D.ramp.first_year_utilization_range||[0.4,0.7]).map(x=>(x*100)+"%").join("-")}，
稳定后约 ${(D.ramp.steady_state_utilization_range||[0.75,0.9]).map(x=>(x*100)+"%").join("-")}。
所以"2026 年新增 480 万吨"这句话，对当年实际供应量的含义可能只有 200 万吨级。
    </div></div></div>

  <div class="card"><div class="ch"><h2>数据自检</h2></div><div class="cb">
    <div class="stat-row">
      <div class="stat"><div class="k">项目</div><div class="v">${D.projects.length}</div></div>
      <div class="stat"><div class="k">装置</div><div class="v">${D.projects.reduce((a,p)=>a+p.nunit,0)}</div></div>
      <div class="stat"><div class="k">进展事实</div><div class="v">${D.nprogress}</div></div>
      <div class="stat"><div class="k">来源</div><div class="v">${Object.keys(D.sources).length}</div></div>
      <div class="stat"><div class="k">A 级来源</div><div class="v">${Object.values(D.sources).filter(s=>s.grade==="A").length}</div></div>
      <div class="stat"><div class="k">已剔除记录</div><div class="v">${D.excluded.length}</div></div>
    </div>
  </div></div>
  <div class="foot">本页面为单文件自包含 HTML，无外部依赖、无网络请求，可直接分发或离线打开。<br>
    数据截至 ${esc(D.as_of)}。所有数字均可在"明细表 → 项目抽屉 → 进展事实 → 来源链接"逐层追溯。</div>`;
}

/* ============ 抽屉 ============ */
function openP(id){
  const p = D.projects.find(x=>x.id===id); if(!p) return;
  $("#did").textContent = p.id + " ｜ " + p.nunit + " 套装置 ｜ " + fmt(p.cap) + " 万吨/年";
  $("#dname").textContent = p.name;
  $("#downer").textContent = p.owner + " ｜ " + p.group;
  const evs = p.ev.map(e=>{
    const cls = ["投产","达产","运行"].includes(e.stage) ? "done" : (e.chg?"chg":"");
    return `<div class="ev-i ${cls}">
      <div class="ev-d">${esc(e.fact)}</div>
      <div class="ev-t">
        <div class="hd2">${stageChip(e.stage)} ${gradeChip(e.grade)}
          ${e.chg?`<span class="chip s-t sm">计划变更：${esc(e.chg)}</span>`:""}
          ${e.msg&&e.msg!==e.fact?`<span class="chip s-x sm">消息 ${esc(e.msg)}</span>`:""}</div>
        <div>${esc(e.desc)}</div>
        ${e.chg?`<div style="font-size:11px;color:#b8860b;margin-top:2px">预计投产：${esc(e.from||"—")} → <b>${esc(e.to||"—")}</b></div>`:""}
        ${e.note?`<div style="font-size:11px;color:#7c8ba1;margin-top:3px">${esc(e.note)}</div>`:""}
        <div class="ev-src">${e.src.map(s=>`<a href="${esc(s.u)}" target="_blank" rel="noopener">
          <span class="sid">${esc(s.id)}</span> ${esc(s.t).slice(0,72)}${s.t.length>72?"…":""}
          <span style="color:#94a3b8;font-size:10px">[${esc(s.ty)} ${esc(s.d)}]</span></a>`).join("")}</div>
      </div></div>`;
  }).join("");
  $("#dbody").innerHTML = `
    <div class="dsec"><h4>项目档案</h4><div class="kv">
      <div class="k">业主</div><div class="v">${esc(p.owner)}</div>
      <div class="k">所属集团</div><div class="v">${esc(p.group)}</div>
      <div class="k">所在地区</div><div class="v">${esc(p.prov)} · ${esc(p.city)}${p.park?" · "+esc(p.park):""}</div>
      <div class="k">产品</div><div class="v">${esc(p.prod)}</div>
      <div class="k">设计产能</div><div class="v"><b>${fmt(p.cap)}</b> 万吨/年（${p.nunit} 套）</div>
      <div class="k">工艺路线</div><div class="v">${esc(p.proc)} ｜ ${esc(p.proccls)}</div>
      <div class="k">项目性质</div><div class="v">${esc(p.nature)}</div>
      <div class="k">当前阶段</div><div class="v">${stageChip(p.stage)} ${esc(p.capstate)}</div>
      <div class="k">最新进展日期</div><div class="v">${esc((p.last||{}).fact||"—")}</div>
    </div></div>

    <div class="dsec"><h4>装置 / 生产线拆分</h4>
      <table><thead><tr><th>装置编号</th><th>名称</th><th style="text-align:right">产能(万吨/年)</th>
        <th style="text-align:right">置换退出</th></tr></thead><tbody>
      ${p.units.map(u=>`<tr><td class="mono" style="font-size:10.5px">${esc(u.id)}</td>
        <td>${esc(u.n)}</td><td class="num">${fmt(u.cap)}</td><td class="num">${u.rep?fmt(u.rep):"—"}</td></tr>`).join("")}
      </tbody></table></div>

    <div class="dsec"><h4>预计投产时间：首次 vs 最新</h4>
      <div class="kv">
        <div class="k">首次预计</div><div class="v">${esc(p.first_plan||"未披露")}　<span style="color:#94a3b8;font-size:11px">（首次披露 ${esc(p.first_disc||"—")}）</span></div>
        <div class="k">最新预计</div><div class="v"><b>${esc(p.latest_plan||"未披露")}</b></div>
        <div class="k">延期情况</div><div class="v" style="color:${p.delay&&p.delay.startsWith("是")?"#c0392b":"inherit"}">${esc(p.delay||"未评估")}${p.delay_m?`（约 ${p.delay_m} 个月）`:""}</div>
        <div class="k">实质放量年份</div><div class="v">${esc(p.ramp||"待评估")}</div>
      </div>
      ${p.hist.length?`<div class="note" style="margin-top:9px"><b>计划变更史</b><br>${p.hist.map(h=>
        `· ${esc(h.fact)} 【${esc(h.chg)}】 ${esc(h.from||"—")} → <b>${esc(h.to||"—")}</b>`).join("<br>")}</div>`:""}
    </div>

    <div class="dsec"><h4>投达产不确定性</h4>
      <div class="note ${p.unc.includes("★")?"hl":""}">${esc(p.unc||"未评估")}</div></div>

    <div class="dsec"><h4>统计口径说明</h4><div class="note">${esc(p.count)}</div></div>

    ${p.dup?`<div class="dsec"><h4>去重与重复披露说明</h4>
      <div class="note ${p.dup.includes("★")?"bad":""}">${esc(p.dup)}</div></div>`:""}

    <div class="dsec"><h4>关注要点</h4><div class="note">${esc(p.watch||"—")}</div></div>

    <div class="dsec"><h4>全部进展事实（${p.ev.length} 条，按事实发生日期排序）</h4>
      <div class="ev">${evs}</div></div>

    <div class="dsec"><button class="btn ${isStar(p.id)?"pri":""}" onclick="toggleStar('${p.id}',null);this.classList.toggle('pri');this.textContent=isStar('${p.id}')?'★ 已加入自选':'☆ 加入自选跟踪'">
      ${isStar(p.id)?"★ 已加入自选":"☆ 加入自选跟踪"}</button></div>`;
  $("#mask").classList.add("on"); $("#drawer").classList.add("on");
}
function closeDrawer(){ $("#mask").classList.remove("on"); $("#drawer").classList.remove("on"); }

/* ============ 路由 ============ */
const RENDERED = {};
function go(t){
  document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("on", b.dataset.t===t));
  document.querySelectorAll("main section").forEach(s=>s.classList.toggle("on", s.id==="s-"+t));
  if(!RENDERED[t]){
    RENDERED[t]=1;
    if(t==="overview") renderOverview();
    else if(t==="timeline") renderTimeline();
    else if(t==="capacity") renderCapacity();
    else if(t==="map") renderMap();
    else if(t==="table") renderTable();
    else if(t==="delayed") renderDelayed();
    else if(t==="dedup") renderDedup();
    else if(t==="watch") renderWatchFull();
    else if(t==="method") renderMethod();
  }
  window.scrollTo({top:0,behavior:"smooth"});
}
document.querySelectorAll("nav button").forEach(b=>b.addEventListener("click",()=>go(b.dataset.t)));
$("#mask").addEventListener("click", closeDrawer);
$("#dclose").addEventListener("click", closeDrawer);
document.addEventListener("keydown", e=>{ if(e.key==="Escape") closeDrawer(); });
renderOverview(); RENDERED.overview=1;
</script>
</body>
</html>
"""

SVG_W = 780
SVG_H = 640


def build_html(proj_dir):
    payload = build_payload(proj_dir)
    geo = os.path.join(proj_dir, "data", "geo_cn.json")
    if os.path.exists(geo):
        with open(geo, "r", encoding="utf-8") as f:
            geodata = json.load(f)
    else:
        geodata = {"features": [], "viewBox": "0 0 780 640"}

    title = "中国%s新增产能与项目跟踪看板" % payload.get("product", "产品")
    html = HTML.replace("@@DATA@@", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("@@GEO@@", json.dumps(geodata, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("@@TITLE@@", title)
    html = html.replace("@@PROD@@", prod_label(payload))
    html = html.replace("@@ASOF@@", payload["as_of"])
    html = html.replace("@@VIEWBOX@@", geodata.get("viewBox", "0 0 %.0f %.0f" % (SVG_W, SVG_H)))

    out = os.path.join(proj_dir, "out")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "%s新增产能与项目跟踪看板.html" % prod_label(payload))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def prod_label(payload):
    """从 product 取出文件名用的简称，如 '聚丙烯(PP)' -> 'PP'。"""
    import re as _re
    raw = payload.get("product", "产品")
    m = _re.search(r"[（(]([^）)]+)[）)]", raw)
    return m.group(1).strip() if m else raw


if __name__ == "__main__":
    print(build_html(sys.argv[1] if len(sys.argv) > 1 else "."))
