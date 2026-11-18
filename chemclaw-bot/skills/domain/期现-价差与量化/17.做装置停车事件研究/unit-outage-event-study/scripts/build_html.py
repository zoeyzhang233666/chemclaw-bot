# -*- coding: utf-8 -*-
"""build_html.py — 生成单文件交互式事件研究报告（HTML）

产物特点：
  * 单文件、双击即开、无需联网（ECharts 内联）
  * 顶部“事件样本表”可直接编辑：改日期、改是否纳入、删除不可比样本 → 全页即时重算
  * 事件对齐曲线 / 平均与中位价格路径 / 分布图 / 逐事件结果
  * 点击任一事件 → 展开企业、装置、产能、停车原因、原文引文、来源链接
  * 所有“缺口”以醒目方式展示；不把不可比的结果洗成结论

用法：
  python scripts/build_html.py --project <项目目录> --out <报告.html>
项目目录须含：
  events.csv, data/prices.csv, data/benchmark.csv(可选), data/spot.csv(可选),
  build/event_results.csv, build/stats.json, build/overlap.json（由 eventstudy.py 生成）
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core  # noqa: E402

ECHARTS_INLINE = os.path.join(os.path.dirname(HERE), "assets", "echarts.min.js")


def read_rows(path):
    return core.read_csv(path) if os.path.exists(path) else []


def build_payload(project_dir: str) -> dict:
    ev_rows = read_rows(os.path.join(project_dir, "events.csv"))
    prices = read_rows(os.path.join(project_dir, "data", "prices.csv"))
    raw = read_rows(os.path.join(project_dir, "data", "prices_raw.csv"))
    bench = read_rows(os.path.join(project_dir, "data", "benchmark.csv"))
    spot = read_rows(os.path.join(project_dir, "data", "spot.csv"))
    results = read_rows(os.path.join(project_dir, "build", "event_results.csv"))
    stats = json.load(open(os.path.join(project_dir, "build", "stats.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(project_dir, "build", "stats.json")) else {}
    overlap = json.load(open(os.path.join(project_dir, "build", "overlap.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(project_dir, "build", "overlap.json")) else {}
    dup = json.load(open(os.path.join(project_dir, "build", "duplicates.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(project_dir, "build", "duplicates.json")) else {}
    meta = {}
    mp = os.path.join(project_dir, "project.json")
    if os.path.exists(mp):
        meta = json.load(open(mp, encoding="utf-8"))

    # 事件详细（含引文）
    events = []
    for r in ev_rows:
        events.append({
            "id": r.get("event_id", ""),
            "name": r.get("event_name", ""),
            "company": r.get("company", ""),
            "unit": r.get("unit_name", ""),
            "product": r.get("product", ""),
            "cap": core.parse_float(r.get("capacity_wt")),
            "region": r.get("region", ""),
            "country": r.get("country", ""),
            "type": core.normalize_event_type(r.get("event_type")),
            "announce": core.parse_date(r.get("announce_date")),
            "first": core.parse_date(r.get("first_market_date")),
            "actual": core.parse_date(r.get("actual_start_date")),
            "restart": core.parse_date(r.get("actual_restart_date")),
            "include": core.parse_flag(r.get("include_flag"), True),
            "reason": r.get("screening_reason", ""),
            "grade": r.get("evidence_grade", ""),
            "verified": core.parse_flag(r.get("product_verified"), None),
            "title": r.get("source_title", ""),
            "media": r.get("source_media", ""),
            "url": r.get("source_url", ""),
            "quote": r.get("quote", ""),
            "notes": r.get("notes", ""),
        })
    return {"events": events, "prices": prices, "raw": raw, "bench": bench, "spot": spot,
            "results": results, "stats": stats, "overlap": overlap, "dup": dup, "meta": meta}


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def render(payload: dict, title: str, echarts_js: str) -> str:
    D = _js(payload)
    return """
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root【LB】--bg:#0f1419;--panel:#161d24;--panel2:#1c252e;--line:#2a3742;--fg:#e6edf3;--dim:#8b98a5;
--accent:#4fc3f7;--up:#ef5350;--down:#26a69a;--warn:#ffb74d;--bad:#e57373;--ok:#81c784;--mono:"Consolas","SF Mono",monospace【RB】
*【LB】box-sizing:border-box【RB】
body【LB】margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif【RB】
.wrap【LB】max-width:1500px;margin:0 auto;padding:20px 22px 80px【RB】
header【LB】border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:18px【RB】
h1【LB】font-size:22px;margin:0 0 6px【RB】 h2【LB】font-size:17px;margin:26px 0 12px;padding-left:10px;border-left:3px solid var(--accent)【RB】
h3【LB】font-size:14px;margin:16px 0 8px;color:var(--accent)【RB】
.sub【LB】color:var(--dim);font-size:12.5px【RB】
.banner【LB】background:linear-gradient(90deg,#3a2a00,#2a1c00);border:1px solid #6d5320;border-radius:8px;padding:10px 14px;margin:12px 0;font-size:13px【RB】
.banner b【LB】color:var(--warn)【RB】
.grid【LB】display:grid;gap:12px【RB】 .g4【LB】grid-template-columns:repeat(4,1fr)【RB】 .g3【LB】grid-template-columns:repeat(3,1fr)【RB】 .g2【LB】grid-template-columns:repeat(2,1fr)【RB】
@media(max-width:1100px)【LB】.g4,.g3,.g2【LB】grid-template-columns:1fr 1fr【RB】【RB】
.card【LB】background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px【RB】
.kpi .v【LB】font:600 22px var(--mono)【RB】 .kpi .l【LB】color:var(--dim);font-size:12px【RB】
.kpi .n【LB】color:var(--dim);font-size:11px;margin-top:2px【RB】
.pos【LB】color:var(--up)【RB】 .neg【LB】color:var(--down)【RB】 .muted【LB】color:var(--dim)【RB】
table【LB】width:100%;border-collapse:collapse;font-size:12.5px【RB】
th,td【LB】padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top【RB】
th【LB】color:var(--dim);font-weight:500;background:var(--panel2);position:sticky;top:0;z-index:2【RB】
tr.ev:hover【LB】background:#1e2a34;cursor:pointer【RB】
td.num【LB】font-family:var(--mono);text-align:right;white-space:nowrap【RB】
input[type=date],input[type=text],select,input[type=number]【LB】background:#0b1015;border:1px solid var(--line);color:var(--fg);border-radius:5px;padding:3px 5px;font:12px var(--mono)【RB】
input[type=checkbox]【LB】accent-color:var(--accent)【RB】
.chart【LB】width:100%;height:340px【RB】 .chart.tall【LB】height:420px【RB】
.tabs【LB】display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap【RB】
.tab【LB】padding:5px 12px;border:1px solid var(--line);border-radius:6px;cursor:pointer;font-size:12.5px;color:var(--dim)【RB】
.tab.on【LB】background:var(--accent);color:#04222f;border-color:var(--accent);font-weight:600【RB】
.detail【LB】display:none;background:#0b1218;border-left:3px solid var(--accent);padding:10px 14px【RB】
.detail.on【LB】display:table-row【RB】
.quote【LB】background:#0b1015;border-left:2px solid var(--warn);padding:8px 12px;margin:6px 0;font-size:12.5px;color:#d7dde3【RB】
.tag【LB】display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;margin-right:4px;border:1px solid【RB】
.t-planned【LB】color:#90caf9;border-color:#3d6b8c【RB】 .t-unplanned【LB】color:#ef9a9a;border-color:#8c3d3d【RB】 .t-restart【LB】color:#a5d6a7;border-color:#3d8c4a【RB】
.t-E1【LB】color:#81c784;border-color:#3d8c4a【RB】 .t-E3【LB】color:#ffb74d;border-color:#8c6d2a【RB】 .t-E5【LB】color:#e57373;border-color:#8c3d3d【RB】
.bar【LB】height:6px;background:#243039;border-radius:3px;overflow:hidden;min-width:60px【RB】 .bar>i【LB】display:block;height:100%【RB】
.gap【LB】color:var(--bad);font-size:12px【RB】 .flag【LB】color:var(--warn);font-size:12px【RB】
.btn【LB】background:var(--accent);color:#04222f;border:0;border-radius:6px;padding:7px 14px;font-weight:600;cursor:pointer【RB】
.btn.ghost【LB】background:#22303b;color:var(--fg);font-weight:500【RB】
.hint【LB】color:var(--dim);font-size:12px;margin-top:6px【RB】
.scroll【LB】max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:8px【RB】
</style></head><body><div class="wrap">
<header>
<h1>{title}</h1>
<div class="sub" id="hdr-sub"></div>
</header>
<div class="banner" id="banner"></div>

<h2>① 研究设计：三种日期严格分开</h2>
<div class="grid g3">
<div class="card"><h3>企业公告日</h3><div class="sub">上市公司/交易所披露的日期。没有公告就是空，不能用媒体报道日顶替。</div></div>
<div class="card"><h3>市场首次获知日 <span class="muted">（默认事件日）</span></h3><div class="sub">媒体首次报道、或盘面首次出现反应的那一天。事件研究默认以它对齐。</div></div>
<div class="card"><h3>实际停车日</h3><div class="sub">装置真正停止进料/降负的日期。与“获知日”经常差几天到几周。</div></div>
</div>
<div class="card" style="margin-top:12px">
<h3>口径切换（改任一项，下方全部重算）</h3>
<div style="display:flex;gap:18px;flex-wrap:wrap;align-items:center">
<label>事件日来源 <select id="cfg-anchor"><option value="first">市场首次获知日</option><option value="actual">实际停车日</option></select></label>
<label>纳入重启事件 <input type="checkbox" id="cfg-restart"></label>
<label>证据等级下限 <select id="cfg-grade"><option value="E2">E2</option><option value="E3" selected>E3</option><option value="E4">E4</option><option value="E5">E5</option></select></label>
<label>最少产能(万吨) <input type="number" id="cfg-cap" value="0" style="width:70px"></label>
<label>去重叠 <select id="cfg-overlap"><option value="all">全样本</option><option value="dedup">去重叠子样本</option></select></label>
</div>
<div class="hint">“去重叠子样本”只保留窗口互不重叠的事件，用于检验结论是否只由一次行情驱动。</div>
</div>

<h2>② 事件样本表（可直接编辑 / 删除 / 改日期，全部即时重算）</h2>
<div style="display:flex;gap:10px;align-items:center;margin-bottom:8px;flex-wrap:wrap">
<button class="btn ghost" id="btn-reset">重置为原始样本</button>
<button class="btn" id="btn-export">导出当前样本 CSV</button>
<span class="hint" id="edit-note"></span>
</div>
<div class="scroll"><table id="ev-table"><thead><tr>
<th style="width:34px">用</th><th style="width:88px">编号</th><th>事件</th><th style="width:130px">企业</th>
<th style="width:150px">装置</th><th style="width:78px">产能</th><th style="width:74px">类型</th>
<th style="width:120px">公告日</th><th style="width:120px">首次获知</th><th style="width:120px">实际停车</th>
<th style="width:110px">证据</th><th style="width:60px">操作</th>
</tr></thead><tbody id="ev-body"></tbody></table></div>
<div class="hint">点击任意一行 → 展开企业背景、停车原因、原文引文与来源链接。灰色行为原始判断“不纳入”的样本（如产品核验失败、无单一事件日）。</div>

<div class="card" id="sample-warning" style="display:none;border-color:#8c6d2a;background:linear-gradient(90deg,#3a2a00,#201600);font-size:13px;line-height:1.7;margin-top:14px"></div>
<div class="grid g4" id="kpis" style="margin-top:14px"></div>

<h2>③ 事件对齐窗口与结果</h2>
<div class="card"><div class="chart tall" id="chart-window"></div>
<div class="hint">横轴为相对事件日的交易日（t=0 即事件日）。曲线为各事件“以 t=0 归一到 100”的价格路径。</div></div>
<div class="scroll" style="margin-top:12px"><table id="res-table"><thead><tr id="res-head"></tr></thead><tbody id="res-body"></tbody></table></div>

<h2>④ 平均与中位价格路径</h2>
<div class="grid g2">
<div class="card"><div class="chart" id="chart-path"></div><h3>累计收益路径（均值 / 中位）</h3></div>
<div class="card"><div class="chart" id="chart-dist"></div><h3>不同窗口的收益分布</h3></div>
</div>

<h2>⑤ 分布与统计</h2>
<div class="scroll"><table id="stat-table"><thead><tr>
<th>窗口</th><th class="num">n</th><th class="num">均值</th><th class="num">中位</th><th class="num">标准差</th>
<th class="num">P05</th><th class="num">P25</th><th class="num">P75</th><th class="num">P95</th>
<th class="num">上涨占比</th><th class="num">符号检验p</th><th>自助法95%CI(均值)</th></tr></thead><tbody id="stat-body"></tbody></table></div>

<h2>⑥ 相对基准的异常收益</h2>
<div class="card"><div class="chart" id="chart-bench"></div>
<div class="hint" id="bench-note"></div></div>

<h2>⑦ 事件重叠与其他同期重大事件</h2>
<div class="grid g2">
<div class="card"><h3>窗口重叠检测</h3><div id="overlap-box"></div></div>
<div class="card"><h3>同期其他重大事件核查</h3><div id="contam-box"></div></div>
</div>

<h2>⑧ 数据缺口与待核实</h2>
<div class="card"><div id="gaps-box"></div></div>

<h2>⑨ 结论与限制</h2>
<div class="card" id="conclusion"></div>

<script>{echarts_js}</script>
<script>
const D = {D};
const WINDOWS = [1,5,10,20];
const PRE = [-10,-5,-3,-1];
let state = 【LB】rows:[], results:[], anchor:'first', restart:false, grade:'E3', cap:0, overlap:'all', deleted:new Set()【RB】;

// ---------- 工具 ----------
const fmt = (v,d=2)=> (v===null||v===undefined||isNaN(v)) ? '—' : (+v).toFixed(d);
const cls = v => (v>0?'pos':(v<0?'neg':'muted'));
const pct = v => (v===null||v===undefined||isNaN(v)) ? '—' : `${v>0?'+':''}${(+v).toFixed(2)}%`;
const DAY = 86400000;
const toDate = s => s ? new Date(s+'T00:00:00') : null;

// ---------- 交易日历（来自价格序列） ----------
const CAL = D.prices.map(p=>p.date);
const CAL_IDX = new Map(CAL.map((d,i)=>[d,i]));
const ADJ = new Map(D.prices.map(p=>[p.date, +p.adj_close]));
const RAW = new Map(D.prices.map(p=>[p.date, +p.close]));
const BENCH = new Map((D.bench||[]).map(p=>[p.date, +p.close]));

function nextTradingDay(d)【LB】 // d 为 YYYY-MM-DD；若在日历内返回自身，否则取其后的第一个交易日
  if (CAL_IDX.has(d)) return d;
  let lo=0, hi=CAL.length;
  while(lo<hi)【LB】const m=(lo+hi)>>1; if(CAL[m]<d) lo=m+1; else hi=m;【RB】
  return lo<CAL.length?CAL[lo]:null;
【RB】
function shift(date, n)【LB】 const i=CAL_IDX.get(date); if(i===undefined) return null; const j=i+n; return (j>=0&&j<CAL.length)?CAL[j]:null; 【RB】
function retBetween(d0,d1)【LB】 const a=ADJ.get(d0), b=ADJ.get(d1); if(a===undefined||b===undefined||!a) return null; return (b/a-1)*100; 【RB】
function benchBetween(d0,d1)【LB】 const a=BENCH.get(d0), b=BENCH.get(d1); if(a===undefined||b===undefined||!a) return null; return (b/a-1)*100; 【RB】

// ---------- 状态 ----------
const ORIG = JSON.parse(JSON.stringify(D.events));
function resetState()【LB】 state.rows = JSON.parse(JSON.stringify(ORIG)); state.deleted=new Set(); 【RB】

function anchorOf(ev)【LB】
  const src = state.anchor==='actual' ? ev.actual : ev.first;
  const fallback = state.anchor==='actual' ? ev.first : ev.actual;
  const use = src || fallback;
  if(!use) return 【LB】d:null, note:'两个日期都缺'【RB】;
  const d = nextTradingDay(use);
  const note = (!CAL_IDX.has(use)) ? `$【LB】use【RB】 非交易日→顺延 $【LB】d【RB】` : '';
  return 【LB】d, note, usedFallback: !src【RB】;
【RB】

function computeAll()【LB】
  const out=[];
  for(const ev of state.rows)【LB】
    if(state.deleted.has(ev.id)) continue;
    const a = anchorOf(ev);
    const rec = 【LB】ev, anchor:a.d, anchorNote:a.note, usedFallback:a.usedFallback【RB】;
    if(a.d)【LB】
      rec.t0 = ADJ.get(a.d);
      rec.rets = 【LB】【RB】; rec.pats = 【LB】【RB】;
      for(const w of WINDOWS)【LB】 rec.rets[w] = retBetween(a.d, shift(a.d,w)); 【RB】
      rec.pre = 【LB】【RB】; for(const k of PRE)【LB】 rec.pre[k]=retBetween(shift(a.d,k), a.d); 【RB】
      rec.t0ret = retBetween(shift(a.d,-1), a.d);
      rec.benchRets = 【LB】【RB】; for(const w of WINDOWS)【LB】 rec.benchRets[w] = benchBetween(a.d, shift(a.d,w)); 【RB】
      // 路径：-10..+20 归一
      rec.path=[]; let base = ADJ.get(shift(a.d,-10));
      for(let k=-10;k<=20;k++)【LB】 const d=shift(a.d,k); rec.path.push(d?【LB】k, d, v: ADJ.get(d)【RB】:【LB】k, d:null, v:null【RB】); 【RB】
      rec.pathBase = base;
    【RB】
    // 纳入判定
    const inc = ev.include!==false;
    const ver = ev.verified!==false;
    const gradeRank = 【LB】E1:1,E2:2,E3:3,E4:4,E5:5【RB】;
    const gradeOk = (gradeRank[ev.grade]||5) <= (gradeRank[state.grade]||3);
    const restartOk = (ev.type!=='restart') || state.restart;
    const capOk = !state.cap || (ev.cap!==null && ev.cap>=state.cap);
    rec.comparable = inc && ver && gradeOk && restartOk && capOk && !!a.d;
    rec.reasons=[]; if(!inc) rec.reasons.push('原始判断不纳入');
    if(!ver) rec.reasons.push('产品核验失败'); if(!gradeOk) rec.reasons.push('证据等级不足');
    if(!restartOk) rec.reasons.push('重启事件未纳入'); if(!capOk) rec.reasons.push('产能低于阈值');
    if(!a.d) rec.reasons.push('缺可对齐日期');
    out.push(rec);
  【RB】
  // 重叠判定（可比集内）
  const cb = out.filter(r=>r.comparable);
  const spans = cb.map(r=>(【LB】id:r.ev.id, s:CAL_IDX.get(r.anchor)-5, e:CAL_IDX.get(r.anchor)+20【RB】)).sort((x,y)=>x.s-y.s);
  const kept=[], excl=new Map();
  for(const sp of spans)【LB】
    const hit = kept.find(k=> sp.s<=k.e && k.s<=sp.e);
    if(hit)【LB】 excl.set(sp.id, hit.id); 【RB】 else kept.push(sp);
  【RB】
  for(const r of out)【LB】 r.overlapWith = excl.get(r.ev.id)||null; 【RB】
  return out;
【RB】

// ---------- 渲染 ----------
function renderHeader()【LB】
  const m = D.meta||【LB】【RB】;
  document.getElementById('hdr-sub').textContent =
    (m.title||'') + (m.product? ` ｜ 品种：$【LB】m.product【RB】`:'') + (m.futures? ` ｜ 期货：$【LB】m.futures【RB】`:'') +
    ` ｜ 交易日历 $【LB】CAL[0]【RB】 ~ $【LB】CAL[CAL.length-1]【RB】（$【LB】CAL.length【RB】 个交易日）`;
  const b=document.getElementById('banner');
  b.innerHTML = (m.banner || '本报告所有价格来自真实公开数据；缺失项一律留空并列入“数据缺口”，不做插值补数。');
【RB】

function renderTable(recs)【LB】
  const tb=document.getElementById('ev-body'); tb.innerHTML='';
  for(const ev of state.rows)【LB】
    if(state.deleted.has(ev.id)) continue;
    const r = recs.find(x=>x.ev.id===ev.id);
    const tr=document.createElement('tr'); tr.className='ev';
    const capTxt = ev.cap!==null? ev.cap : '<span class="muted">缺</span>';
    const gradeCls = 't-'+(ev.grade||'E5');
    tr.innerHTML = `
    <td><input type="checkbox" data-act="use" data-id="$【LB】ev.id【RB】" $【LB】ev.include!==false?'checked':''【RB】></td>
    <td class="muted" style="font-family:var(--mono)">$【LB】ev.id【RB】</td>
    <td>$【LB】ev.name【RB】<div class="sub">$【LB】ev.region||''【RB】 $【LB】ev.country||''【RB】 $【LB】r&&r.anchorNote? '<span class="flag">'+r.anchorNote+'</span>':''【RB】</div></td>
    <td>$【LB】ev.company【RB】</td>
    <td class="sub">$【LB】ev.unit||'—'【RB】</td>
    <td class="num">$【LB】capTxt【RB】</td>
    <td><span class="tag t-$【LB】ev.type【RB】">$【LB】ev.type==='planned'?'计划检修':(ev.type==='unplanned'?'意外停车':'重启')【RB】</span></td>
    <td><input type="date" data-act="date" data-f="announce" data-id="$【LB】ev.id【RB】" value="$【LB】ev.announce||''【RB】"></td>
    <td><input type="date" data-act="date" data-f="first" data-id="$【LB】ev.id【RB】" value="$【LB】ev.first||''【RB】"></td>
    <td><input type="date" data-act="date" data-f="actual" data-id="$【LB】ev.id【RB】" value="$【LB】ev.actual||''【RB】"></td>
    <td><span class="tag t-E$【LB】(ev.grade||'E5').replace('E','')【RB】">$【LB】ev.grade【RB】</span></td>
    <td><button class="btn ghost" style="padding:2px 8px" data-act="del" data-id="$【LB】ev.id【RB】">删</button></td>`;
    if(ev.include===false) tr.style.opacity=.45;
    tr.addEventListener('click', e=>【LB】
      if(e.target.closest('input,button')) return;
      document.getElementById('det-'+ev.id).classList.toggle('on');
    【RB】);
    tb.appendChild(tr);
    const dr=document.createElement('tr'); dr.id='det-'+ev.id; dr.className='detail';
    dr.innerHTML=`<td colspan="12">
      <div class="grid g2">
        <div><h3>企业 / 装置 / 产能</h3>
          <div>企业：<b>$【LB】ev.company||'—'【RB】</b></div>
          <div>装置：$【LB】ev.unit||'—'【RB】</div>
          <div>产品：$【LB】ev.product||'—'【RB】　产能：$【LB】ev.cap!==null?ev.cap+' 万吨/年':'<span class="gap">未披露（缺口）</span>'【RB】</div>
          <div>地区：$【LB】ev.region||'—'【RB】 / $【LB】ev.country||'—'【RB】</div>
          <div>类型：<span class="tag t-$【LB】ev.type【RB】">$【LB】ev.type【RB】</span> 证据：<span class="tag t-E$【LB】(ev.grade||'E5').replace('E','')【RB】">$【LB】ev.grade【RB】</span>
            $【LB】ev.verified===false?'<span class="tag t-unplanned">产品核验失败</span>':''【RB】</div>
          <div style="margin-top:6px">公告日：$【LB】ev.announce||'<span class="muted">无</span>'【RB】　首次获知：$【LB】ev.first||'<span class="muted">无</span>'【RB】　实际停车：$【LB】ev.actual||'<span class="muted">无</span>'【RB】</div>
          <div style="margin-top:6px" class="sub">筛选理由：$【LB】ev.reason||'—'【RB】</div>
          <div class="sub">备注：$【LB】ev.notes||'—'【RB】</div>
        </div>
        <div><h3>停车原因与原文证据</h3>
          <div class="quote">「$【LB】ev.quote||'（未取得原文摘录）'【RB】」</div>
          <div class="sub" style="margin-top:8px">来源：$【LB】ev.media||'—'【RB】 · 《$【LB】ev.title||'—'【RB】》</div>
          $【LB】ev.url?`<a href="$【LB】ev.url【RB】" target="_blank" rel="noopener" style="color:var(--accent);font-size:12px">打开原文 →</a>`:''【RB】
        </div>
      </div></td>`;
    tb.appendChild(dr);
  【RB】
【RB】

function renderSampleWarning(recs)【LB】
  const cb = recs.filter(r=>r.comparable);
  const n = cb.length;
  const box = document.getElementById('sample-warning');
  if(!box) return;
  if(n >= 10)【LB】 box.style.display='none'; return; 【RB】
  box.style.display='';
  const need = 10 - n;
  box.innerHTML = '<b>样本量警告（n='+n+'）</b>：可比事件仅 '+n+' 个，距可做统计推断的 10 个还差 '+need+' 个。'
    + '均值、中位数与分位数的抽样误差很大，<b>只能作为个案路径记录与描述性观察，不能当作“停车事件的一般规律”，'
    + '也不能用来预测下一次停车后的价格</b>。若下方图表看起来有规律，请优先怀疑它来自这几次特定行情'
    + '（尤其是 2026-06 中东地缘冲突与 10 月 MTO 负反馈），而不是停车本身。';
【RB】

function renderKPI(recs)【LB】
  const cb = recs.filter(r=>r.comparable);
  const box=document.getElementById('kpis');
  const nAll = state.rows.filter(e=>!state.deleted.has(e.id)).length;
  const w5 = cb.map(r=>r.rets[5]).filter(v=>v!==null);
  const mean5 = w5.length? w5.reduce((a,b)=>a+b,0)/w5.length : null;
  const med5 = w5.length? [...w5].sort((a,b)=>a-b)[Math.floor(w5.length/2)] : null;
  const cards = [
    ['样本总数', nAll, '原始候选事件'],
    ['可比样本 n', cb.length, '通过纳入筛选'],
    ['t+5 均值', pct(mean5), `n=$【LB】w5.length【RB】`],
    ['t+5 中位', pct(med5), `上涨 $【LB】w5.filter(v=>v>0).length【RB】 / 下跌 $【LB】w5.filter(v=>v<0).length【RB】`],
  ];
  box.innerHTML = cards.map(([l,v,n])=>`<div class="card kpi"><div class="l">$【LB】l【RB】</div>
    <div class="v $【LB】typeof v==='string'&&v.startsWith('+')?'pos':(typeof v==='string'&&v.startsWith('-')?'neg':'')【RB】">$【LB】v【RB】</div>
    <div class="n">$【LB】n【RB】</div></div>`).join('');
【RB】

function renderResults(recs)【LB】
  const cb = state.overlap==='dedup' ? recs.filter(r=>r.comparable && !r.overlapWith) : recs.filter(r=>r.comparable);
  const head=document.getElementById('res-head');
  head.innerHTML = '<th>事件</th><th>锚定日</th><th class="num">t0收盘</th><th class="num">事件日收益</th>'+
    WINDOWS.map(w=>`<th class="num">t+$【LB】w【RB】</th>`).join('') + '<th>备注</th>';
  const tb=document.getElementById('res-body'); tb.innerHTML='';
  for(const r of cb.sort((a,b)=>a.anchor<b.anchor?-1:1))【LB】
    const tr=document.createElement('tr');
    tr.innerHTML = `<td><b>$【LB】r.ev.id【RB】</b> $【LB】r.ev.name【RB】<div class="sub">$【LB】r.ev.company【RB】</div></td>
      <td class="muted" style="font-family:var(--mono)">$【LB】r.anchor【RB】</td>
      <td class="num">$【LB】fmt(r.t0,0)【RB】</td>
      <td class="num $【LB】cls(r.t0ret)【RB】">$【LB】pct(r.t0ret)【RB】</td>` +
      WINDOWS.map(w=>`<td class="num $【LB】cls(r.rets[w])【RB】">$【LB】pct(r.rets[w])【RB】</td>`).join('') +
      `<td class="sub">$【LB】r.overlapWith? '<span class="flag">与 '+r.overlapWith+' 窗口重叠</span>':''【RB】$【LB】r.usedFallback?'<span class="flag">日期回退</span>':''【RB】</td>`;
    tb.appendChild(tr);
  【RB】
  document.getElementById('edit-note').textContent = `当前显示 $【LB】cb.length【RB】 个可比样本（$【LB】state.overlap==='dedup'?'去重叠':'全样本'【RB】口径）`;
  return cb;
【RB】

function renderStat(recs)【LB】
  const cb = recs.filter(r=>r.comparable);
  const tb=document.getElementById('stat-body'); tb.innerHTML='';
  const q=(arr,p)=>【LB】 if(!arr.length) return null; const s=[...arr].sort((a,b)=>a-b); const pos=(s.length-1)*p; const lo=Math.floor(pos),hi=Math.ceil(pos);
    return lo===hi? s[lo] : s[lo]+(s[hi]-s[lo])*(pos-lo); 【RB】;
  const statRows=[];
  for(const w of WINDOWS)【LB】
    const v = cb.map(r=>r.rets[w]).filter(x=>x!==null);
    if(!v.length)【LB】 statRows.push([`t+$【LB】w【RB】`,0]); continue; 【RB】
    const mean=v.reduce((a,b)=>a+b,0)/v.length;
    const sd = v.length>1? Math.sqrt(v.reduce((a,b)=>a+(b-mean)**2,0)/(v.length-1)) : null;
    // 自助法 95% CI（1000 次，固定种子由确定性伪随机替代）
    let seed=20261020; const rnd=()=>【LB】 seed=(seed*1103515245+12345)&0x7fffffff; return seed/0x7fffffff; 【RB】;
    const bs=[];
    for(let i=0;i<1000;i++)【LB】 let s=0; for(let j=0;j<v.length;j++) s+=v[Math.floor(rnd()*v.length)]; bs.push(s/v.length); 【RB】
    const ciLo=q(bs,.025), ciHi=q(bs,.975);
    // 符号检验精确二项
    const nz=v.filter(x=>x!==0), n=nz.length, k=nz.filter(x=>x>0).length;
    let p=null;
    if(n>0)【LB】 const C=(n,r)=>【LB】let c=1;for(let i=1;i<=r;i++)c=c*(n-i+1)/i;return c;【RB】;
      let tail=0; for(let i=0;i<=Math.min(k,n-k);i++) tail+=C(n,i); p=Math.min(1, 2*tail/Math.pow(2,n)); 【RB】
    statRows.push([`t+$【LB】w【RB】`,{n:v.length, mean, med:q(v,.5), sd, p05:q(v,.05), p25:q(v,.25), p75:q(v,.75), p95:q(v,.95),
      win:v.filter(x=>x>0).length/v.length, p, ciLo, ciHi}]);
  【RB】
  for(const [lab,s] of statRows)【LB】
    const tr=document.createElement('tr');
    if(!s.n)【LB】 tr.innerHTML=`<td>$【LB】lab【RB】</td><td colspan="11" class="muted">样本不足，不计算</td>`; tb.appendChild(tr); continue; 【RB】
    tr.innerHTML=`<td><b>$【LB】lab【RB】</b></td><td class="num">$【LB】s.n【RB】</td>
      <td class="num $【LB】cls(s.mean)【RB】">$【LB】pct(s.mean)【RB】</td><td class="num $【LB】cls(s.med)【RB】">$【LB】pct(s.med)【RB】</td>
      <td class="num">$【LB】fmt(s.sd)【RB】</td><td class="num">$【LB】pct(s.p05)【RB】</td><td class="num">$【LB】pct(s.p25)【RB】</td>
      <td class="num">$【LB】pct(s.p75)【RB】</td><td class="num">$【LB】pct(s.p95)【RB】</td>
      <td class="num">$【LB】(s.win*100).toFixed(0)【RB】%</td><td class="num">$【LB】s.p===null?'—':(s.p<0.001?'<0.001':s.p.toFixed(3))【RB】</td>
      <td class="num">[$【LB】pct(s.ciLo)【RB】, $【LB】pct(s.ciHi)【RB】]</td>`;
    tb.appendChild(tr);
  【RB】
【RB】

// ---------- 图表 ----------
let charts=【LB】【RB】;
function chart(id)【LB】 if(!charts[id]) charts[id]=echarts.init(document.getElementById(id), 'dark');
  window.addEventListener('resize',()=>charts[id].resize()); return charts[id]; 【RB】
const DARKBAK='#161d24', GRID=【LB】left:56,right:24,top:36,bottom:36【RB】;

function renderCharts(recs)【LB】
  const cb = recs.filter(r=>r.comparable);
  // 3. 对齐窗口
  const series = cb.map(r=>【LB】
    const base=r.pathBase;
    return 【LB】name:r.ev.id, type:'line', showSymbol:false, smooth:false,
      data: r.path.map(p=> p.v&&base? +(p.v/base*100).toFixed(2) : null)【RB】;
  【RB】);
  chart('chart-window').setOption(【LB】
    backgroundColor:DARKBAK, grid:GRID, tooltip:【LB】trigger:'axis'【RB】,
    legend:【LB】type:'scroll',top:4,textStyle:【LB】fontSize:11【RB】【RB】,
    xAxis:【LB】type:'category',data:Array.from(【LB】length:31【RB】,(_,i)=> i-10), name:'交易日(相对事件)'【RB】,
    yAxis:【LB】type:'value',name:'归一指数',scale:true【RB】,
    series
  【RB】, true);

  // 4a. 均值/中位路径
  const meanPath=[], medPath=[];
  for(let k=-10;k<=20;k++)【LB】
    const vals = cb.map(r=> r.path[k+10]&&r.pathBase ? r.path[k+10].v/r.pathBase*100 : null).filter(v=>v!==null);
    if(!vals.length)【LB】 meanPath.push(null); medPath.push(null); continue; 【RB】
    meanPath.push(+(vals.reduce((a,b)=>a+b,0)/vals.length).toFixed(2));
    const s=[...vals].sort((a,b)=>a-b); medPath.push(+s[Math.floor(s.length/2)].toFixed(2));
  【RB】
  const colors=['#4fc3f7','#ffb74d'];
  chart('chart-path').setOption(【LB】
    backgroundColor:DARKBAK, grid:GRID, tooltip:【LB】trigger:'axis'【RB】,
    legend:【LB】top:4,textStyle:【LB】fontSize:11【RB】【RB】,
    xAxis:【LB】type:'category',data:Array.from(【LB】length:31【RB】,(_,i)=>i-10)【RB】,
    yAxis:【LB】type:'value',scale:true【RB】,
    series:[【LB】name:'均值路径',type:'line',data:meanPath,itemStyle:【LB】color:colors[0]【RB】,showSymbol:false,
        markLine:【LB】silent:true,symbol:'none',data:[【LB】xAxis:10【RB】],lineStyle:【LB】color:'#8b98a5',type:'dashed'【RB】【RB】【RB】,
      【LB】name:'中位路径',type:'line',data:medPath,itemStyle:【LB】color:colors[1]【RB】,showSymbol:false【RB】]
  【RB】, true);

  // 4b. 分布（箱线图 + 散点）
  const boxData = WINDOWS.map(w=>【LB】 const v=cb.map(r=>r.rets[w]).filter(x=>x!==null).sort((a,b)=>a-b);
    if(!v.length) return [null,null,null,null,null];
    const q=(p)=>【LB】const pos=(v.length-1)*p,lo=Math.floor(pos),hi=Math.ceil(pos);return lo===hi?v[lo]:v[lo]+(v[hi]-v[lo])*(pos-lo);【RB】;
    return [q(.05),q(.25),q(.5),q(.75),q(.95)].map(x=>+x.toFixed(2)); 【RB】);
  chart('chart-dist').setOption(【LB】
    backgroundColor:DARKBAK, grid:GRID, tooltip:【LB】trigger:'item'【RB】,
    xAxis:【LB】type:'category',data:WINDOWS.map(w=>'t+'+w)【RB】,
    yAxis:【LB】type:'value',name:'收益 %'【RB】,
    series:[【LB】name:'分布',type:'boxplot',data:boxData,itemStyle:【LB】color:'#1e3a4c',borderColor:'#4fc3f7'【RB】【RB】,
      【LB】name:'事件',type:'scatter',data:WINDOWS.flatMap((w,i)=>cb.map(r=>[i,r.rets[w]]).filter(x=>x[1]!==null)),
        symbolSize:6,itemStyle:【LB】color:'rgba(255,183,77,0.75)'【RB】【RB】]
  【RB】, true);

  // 6. 异常收益
  const hasBench = cb.some(r=>r.benchRets[5]!==null);
  const els=document.getElementById('bench-note');
  if(!hasBench)【LB】
    els.innerHTML='<span class="gap">未提供基准序列（data/benchmark.csv），本页不计算异常收益。</span> '+
      '事件研究若不做基准调整，“涨了”可能只是整个化工板块在涨——这正是需要基准的原因。';
    chart('chart-bench').setOption(【LB】backgroundColor:DARKBAK,title:【LB】text:'（未配置基准）',left:'center',top:'middle',textStyle:【LB】color:'#8b98a5',fontSize:13【RB】【RB】【RB】);
  【RB】 else 【LB】
    const raw5 = cb.map(r=>r.rets[5]).filter(v=>v!==null);
    const bm5 = cb.map(r=>r.benchRets[5]).filter(v=>v!==null);
    const ex5 = cb.map(r=> r.rets[5]!==null&&r.benchRets[5]!==null ? r.rets[5]-r.benchRets[5] : null).filter(v=>v!==null);
    els.textContent='异常收益 = 标的区间收益 − 基准区间收益（同交易日窗口）。样本很小，异常收益的均值为参考值，不作统计显著性结论。';
    chart('chart-bench').setOption(【LB】
      backgroundColor:DARKBAK, grid:GRID, tooltip:【LB】trigger:'axis'【RB】, legend:【LB】top:4【RB】,
      xAxis:【LB】type:'category',data:cb.map(r=>r.ev.id)【RB】,
      yAxis:【LB】type:'value',name:'%'【RB】,
      series:[【LB】name:'标的 t+5',type:'bar',data:cb.map(r=>r.rets[5])【RB】,
        【LB】name:'基准 t+5',type:'bar',data:cb.map(r=>r.benchRets[5])【RB】,
        【LB】name:'异常 t+5',type:'bar',data:cb.map(r=> r.rets[5]!==null&&r.benchRets[5]!==null? +(r.rets[5]-r.benchRets[5]).toFixed(2):null),
          itemStyle:【LB】color:'#ffb74d'【RB】【RB】]
    【RB】, true);
  【RB】
【RB】

function renderOverlap(recs)【LB】
  const ov = D.overlap||【LB】【RB】;
  const box=document.getElementById('overlap-box');
  const pairs = ov.overlap_pairs||[];
  if(!pairs.length)【LB】 box.innerHTML='<div class="muted">未检测到窗口重叠（或可比样本不足 2 个）。</div>'; return; 【RB】
  box.innerHTML = '<div class="sub">窗口定义为 [t−5, t+20]（交易日）。重叠样本的路径不是独立观测。</div>'+
    '<table><thead><tr><th>保留</th><th>排除（去重叠子样本）</th></tr></thead><tbody>'+
    pairs.map(p=>`<tr><td>$【LB】p.kept【RB】</td><td>$【LB】p.excluded【RB】</td></tr>`).join('')+'</tbody></table>';
【RB】

function renderContam(recs)【LB】
  const box=document.getElementById('contam-box');
  const cb=recs.filter(r=>r.comparable);
  box.innerHTML = `<div class="sub">事件研究无法单独证明因果：行情同时受成本端（煤炭/原油/天然气）、宏观、
  下游（MTO）开工、政策与地缘事件共同驱动。下面按事件列出同窗口内的其他已知同类变动。</div>
  <table><thead><tr><th>事件</th><th>同期可识别干扰</th></tr></thead><tbody>$【LB】cb.map(r=>【LB】
    const near = cb.filter(x=>x!==r && Math.abs(CAL_IDX.get(x.anchor)-CAL_IDX.get(r.anchor))<=20)
       .map(x=>x.ev.id+'(同日±20交易日)');
    return `<tr><td>$【LB】r.ev.id【RB】</td><td>$【LB】near.length? near.join('、') : '<span class="muted">窗口内无其他已收录事件</span>'【RB】
      <div class="sub">$【LB】r.ev.type==='restart'?'方向相反的重启事件也在同窗口内，需单独解释':''【RB】</div></td></tr>`;
  【RB】).join('')【RB】</tbody></table>`;
【RB】

function renderGaps(recs)【LB】
  const box=document.getElementById('gaps-box');
  const cb=recs.filter(r=>r.comparable);
  const missingSpot = !D.spot.length;
  const missingBench = !D.bench.length;
  const lack = cb.filter(r=>r.rets[20]===null).map(r=>r.ev.id);
  let h = '<ul style="margin:4px 0 0 18px">';
  if(missingSpot) h += '<li class="gap">现货价格序列缺失：报告不含现货与基差路径（严格口径下不插值补数）。补齐 data/spot.csv 后重跑即可。</li>';
  if(missingBench) h += '<li class="gap">基准序列缺失：不含异常收益。</li>';
  if(lack.length) h += `<li class="flag">后段窗口不足：$【LB】lack.join('、')【RB】 距数据末端不足 20 个交易日，t+20 留空。</li>`;
  const capMiss = state.rows.filter(e=>e.cap===null && e.include!==false).map(e=>e.id);
  if(capMiss.length) h += `<li class="flag">产能未披露：$【LB】capMiss.join('、')【RB】（不满足可核验门槛，单列）。</li>`;
  const multi = state.rows.filter(e=>e.multi);
  h += '</ul>';
  box.innerHTML = h;
【RB】

function renderConclusion(recs)【LB】
  const cb=recs.filter(r=>r.comparable);
  const box=document.getElementById('conclusion');   
  const w5=cb.map(r=>r.rets[5]).filter(v=>v!==null);
  const mean = w5.length? w5.reduce((a,b)=>a+b,0)/w5.length : null;
  const up = w5.filter(v=>v>0).length, dn=w5.filter(v=>v<0).length;
  let txt = `<div>可比样本 <b>n=$【LB】cb.length【RB】</b>；t+5 收益均值 $【LB】pct(mean)【RB】，上涨 $【LB】up【RB】 个、下跌 $【LB】dn【RB】 个。</div>`;
  if(cb.length<3) txt += `<div class="gap" style="margin-top:8px">样本过小（n=$【LB】cb.length【RB】），不足以对“停车事件的普遍价格效应”下结论，
    仅可作为个案路径的记录。请补充更多可比事件或延长历史窗口。</div>`;
  txt += `<div class="sub" style="margin-top:10px">causal disclaimer：以上为事件窗口内的价格变动描述与相对基准的比较，
    不代表“停车导致涨/跌”。同期还存在成本端、宏观、下游负反馈与地缘等竞争性解释；要识别因果，需要
    更外生的事件（如突发事故）与更干净的对照组，并控制同期冲击。</div>`;
  box.innerHTML = txt;
【RB】
{window.D = D; window.initialized = true;}</script>
<script>
window.addEventListener('load', ()=>【LB】
  // 初始化
  const btnReset=document.getElementById('btn-reset');
  resetState();
  const bind=()=>【LB】
    const recs = computeAll();
    renderSampleWarning(recs); renderTable(recs); renderKPI(recs); renderResults(recs); renderStat(recs); renderCharts(recs); renderOverlap(recs); renderContam(recs); renderGaps(recs); renderConclusion(recs);
  【RB】;
  bind();
  document.getElementById('ev-body').addEventListener('change', e=>【LB】
    const t=e.target; const id=t.dataset.id; const ev=state.rows.find(x=>x.id===id); if(!ev) return;
    if(t.dataset.act==='use') ev.include = t.checked;
    if(t.dataset.act==='date') ev[t.dataset.f] = t.value||null;
    bind();
  【RB】);
  document.getElementById('ev-body').addEventListener('click', e=>【LB】
    const b=e.target.closest('[data-act=del]'); if(!b) return;
    state.deleted.add(b.dataset.id); bind();
  【RB】);
  ['cfg-anchor','cfg-grade','cfg-overlap'].forEach(k=>document.getElementById(k).addEventListener('change', ev=>【LB】
    if(k==='cfg-anchor') state.anchor=ev.target.value; if(k==='cfg-grade') state.grade=ev.target.value; if(k==='cfg-overlap') state.overlap=ev.target.value; bind();
  【RB】));
  document.getElementById('cfg-restart').addEventListener('change',e=>【LB】state.restart=e.target.checked; bind();【RB】);
  document.getElementById('cfg-cap').addEventListener('input',e=>【LB】state.cap=+e.target.value||0; bind();【RB】);
  btnReset.addEventListener('click',()=>【LB】resetState(); bind();【RB】);
  document.getElementById('btn-export').addEventListener('click',()=>【LB】
    const cols=['event_id','event_name','company','unit_name','capacity_wt','event_type','announce_date','first_market_date','actual_start_date','include_flag','evidence_grade'];
    const lines=[cols.join(',')];
    for(const ev of state.rows) if(!state.deleted.has(ev.id)) lines.push([ev.id,ev.name,ev.company,ev.unit,ev.cap||'',ev.type,ev.announce||'',ev.first||'',ev.actual||'',ev.include!==false?'1':'0',ev.grade].map(v=>`"$【LB】String(v).replace(/"/g,'""')【RB】"`).join(','));
    const blob=new Blob(['\\ufeff'+lines.join('\\n')],【LB】type:'text/csv'【RB】);
    const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='事件样本_当前编辑版.csv'; a.click();
  【RB】);
  renderHeader();
【RB】);
</script></div></body></html>""".replace("【LB】", "{").replace("【RB】", "}").replace("{title}", title).replace("{D}", D).replace("{echarts_js}", echarts_js)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="化工装置停车事件研究")
    args = ap.parse_args(argv)
    payload = build_payload(args.project)
    # 价格与基准按需裁剪：全历史会让 HTML 很大，这里保留全部（单文件约 1-2MB，可接受）
    echarts_js = open(ECHARTS_INLINE, encoding="utf-8").read() if os.path.exists(ECHARTS_INLINE) else ""
    html = render(payload, args.title, echarts_js)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(html)
    print(f"[OK] 报告 {len(html)/1024:.0f} KB -> {args.out}")


if __name__ == "__main__":
    main()
