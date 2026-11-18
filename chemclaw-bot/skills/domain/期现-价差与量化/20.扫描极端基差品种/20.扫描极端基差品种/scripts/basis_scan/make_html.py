# -*- coding: utf-8 -*-
"""make_html.py — 生成自包含（离线可用）的交互式基差扫描看板

输入：out/scan_result.json（由 scan.py 产出，唯一数据源，保证可复现）
输出：单个 HTML（内嵌 ECharts，无外链、无 CDN）

看板要素
--------
1. 顶部 KPI：品种池规模 / 可扫描数 / 极端数 / 数据不足数 / 数据截至日
2. 极端基差排行榜（按「品种内」分位排序，绝不跨品种比较基差金额）
3. 历史分位分布（每个品种在自身历史中的位置，0-100% 刻度）
4. 近一月基差变化（元/吨 + 分位变化）
5. 数据覆盖核验表（样本长度、窗口、有效日期、合约映射、交叉校验通过率）
6. 点击品种 -> 展开完整基差走势、分位带、现货/期货分解、月度表、口径与事件
用户可实时改「极端阈值」和「历史窗口」，前端按同一规则重算分位。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ECHARTS_CANDIDATES = [
    os.path.join(HERE, 'assets', 'echarts.min.js'),
    os.path.join(HERE, '..', 'assets', 'echarts.min.js'),
    r'./assets\echarts.min.js',
]


def load_echarts() -> str:
    for p in ECHARTS_CANDIDATES:
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                return f.read()
    return ''


def build(result: dict) -> str:
    echarts_js = load_echarts()
    data_js = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
    html = TEMPLATE.replace('/*__ECHARTS__*/', echarts_js).replace('/*__DATA__*/', data_js)
    return html


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>化工期货 · 极端基差扫描看板</title>
<style>
:root{
  --bg:#0b1020; --bg2:#111831; --card:#151d38; --card2:#1b2547; --line:#2a3559;
  --txt:#e8ecf8; --dim:#93a0c4; --dim2:#6b7899;
  --up:#ff6b6b; --down:#3ddc97; --accent:#5b8cff; --accent2:#8f6bff; --warn:#ffb84d;
  --hi:#ff7a59; --lo:#2ec4b6;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(1200px 600px at 20% -10%,#1b2a5c 0%,transparent 60%),
  radial-gradient(900px 500px at 110% 10%,#3a1f5c 0%,transparent 55%),var(--bg);
  color:var(--txt);font:14px/1.6 "Microsoft YaHei","PingFang SC",system-ui,-apple-system,sans-serif;
  min-height:100vh;padding:22px 26px 60px}
.wrap{max-width:1560px;margin:0 auto}
header{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-bottom:16px}
h1{font-size:25px;font-weight:800;letter-spacing:.5px;background:linear-gradient(92deg,#fff 0%,#a9c0ff 45%,#c9a6ff 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.sub{color:var(--dim);font-size:12.5px;margin-top:5px}
.badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11.5px;border:1px solid var(--line);
  background:#111a33;color:var(--dim);margin-left:6px}
.badge.warn{border-color:#5c4320;background:#2a1f0f;color:var(--warn)}
.badge.ok{border-color:#1e4a3a;background:#0f2a20;color:#3ddc97}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:14px}
.kpi{background:linear-gradient(160deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:14px;
  padding:13px 15px;position:relative;overflow:hidden}
.kpi::after{content:'';position:absolute;right:-30px;top:-30px;width:80px;height:80px;border-radius:50%;
  background:radial-gradient(circle,rgba(91,140,255,.28),transparent 70%)}
.kpi .lab{font-size:11.5px;color:var(--dim);letter-spacing:.4px}
.kpi .val{font-size:26px;font-weight:800;margin-top:2px;font-variant-numeric:tabular-nums}
.kpi .note{font-size:11px;color:var(--dim2);margin-top:1px}
.toolbar{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 16px;
  display:flex;gap:22px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.ctl{display:flex;align-items:center;gap:9px;font-size:12.5px;color:var(--dim)}
.ctl input[type=range]{width:150px;accent-color:var(--accent)}
.ctl b{color:var(--txt);font-variant-numeric:tabular-nums;min-width:52px;display:inline-block}
.seg{display:flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg button{background:#101830;color:var(--dim);border:0;padding:6px 12px;font-size:12.5px;cursor:pointer}
.seg button.on{background:linear-gradient(180deg,#2b4bb5,#243c8f);color:#fff;font-weight:700}
.grid{display:grid;grid-template-columns:1.45fr 1fr;gap:14px;margin-bottom:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 17px;overflow:hidden}
.card h2{font-size:14.5px;font-weight:700;margin-bottom:2px;display:flex;align-items:center;gap:8px}
.card h2 i{width:4px;height:15px;border-radius:2px;background:linear-gradient(180deg,var(--accent),var(--accent2));display:inline-block}
.card .hint{font-size:11.5px;color:var(--dim2);margin-bottom:10px}
.rank{display:flex;flex-direction:column;gap:7px;max-height:560px;overflow:auto;padding-right:4px}
.rrow{display:grid;grid-template-columns:34px 1fr 168px 78px;gap:10px;align-items:center;
  background:#10172f;border:1px solid #222c4c;border-radius:11px;padding:9px 11px;cursor:pointer;
  transition:.16s border-color,.16s transform,.16s background}
.rrow:hover{border-color:#3a4e8f;background:#141d3b;transform:translateX(2px)}
.rrow.sel{border-color:var(--accent);box-shadow:0 0 0 1px rgba(91,140,255,.35) inset}
.rk{font-size:15px;font-weight:800;color:var(--dim);text-align:center;font-variant-numeric:tabular-nums}
.rk.top{color:#ffd166}
.nm{font-weight:700;font-size:14px}
.nm small{color:var(--dim2);font-weight:400;margin-left:6px;font-size:11.5px}
.meta2{font-size:11.5px;color:var(--dim);margin-top:1px}
.bar{height:7px;border-radius:4px;background:#1d2745;position:relative;overflow:hidden}
.bar>span{position:absolute;left:0;top:0;bottom:0;border-radius:4px}
.pctv{font-variant-numeric:tabular-nums;font-weight:800;font-size:15px;text-align:right}
.tag{display:inline-block;padding:1px 7px;border-radius:6px;font-size:10.5px;font-weight:700;letter-spacing:.3px}
.tag.hi{background:rgba(255,122,89,.16);color:var(--hi);border:1px solid rgba(255,122,89,.35)}
.tag.lo{background:rgba(46,196,182,.16);color:var(--lo);border:1px solid rgba(46,196,182,.35)}
.tag.mid{background:#1a2444;color:var(--dim2);border:1px solid #26325a}
.tag.na{background:#2a1f0f;color:var(--warn);border:1px solid #5c4320}
.chart{width:100%}
.distwrap{display:flex;flex-direction:column;gap:6px;max-height:560px;overflow:auto;padding-right:4px}
.dist{display:grid;grid-template-columns:104px 1fr 46px;gap:9px;align-items:center;font-size:12px}
.dist .trk{height:12px;border-radius:6px;position:relative;background:
  linear-gradient(90deg,rgba(46,196,182,.22),rgba(120,130,160,.10) 25%,rgba(120,130,160,.10) 75%,rgba(255,122,89,.22));
  border:1px solid #232e50}
.dist .dot{position:absolute;top:50%;width:11px;height:11px;border-radius:50%;transform:translate(-50%,-50%);
  box-shadow:0 0 0 2px #0b1020}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:7px 8px;border-bottom:1px solid #212b49;text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:11.5px;background:#121a33;position:sticky;top:0;z-index:2}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.click{cursor:pointer}
tr.click:hover td{background:#151f3d}
.up{color:var(--up)}.down{color:var(--down)}.dim{color:var(--dim2)}
.detail{display:none;margin-top:14px}
.detail.on{display:block;animation:fade .25s ease}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.dhead{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap}
.dtitle{font-size:18px;font-weight:800}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.fact{background:#10172f;border:1px solid #222c4c;border-radius:11px;padding:10px 12px}
.fact .k{font-size:11px;color:var(--dim2)}
.fact .v{font-size:13.5px;font-weight:600;margin-top:2px;line-height:1.45}
.note{background:linear-gradient(180deg,#1a1a10,#15150d);border:1px solid #4a3d18;border-radius:11px;
  padding:10px 13px;font-size:12px;color:#e5cf9a;margin-top:10px}
.note b{color:#ffd166}
ul.ev{list-style:none;font-size:12px}
ul.ev li{padding:6px 0;border-bottom:1px dashed #212b49;display:flex;gap:9px}
ul.ev li:last-child{border-bottom:0}
ul.ev time{color:var(--dim2);white-space:nowrap;font-variant-numeric:tabular-nums}
a{color:#8fb0ff;text-decoration:none}a:hover{text-decoration:underline}
footer{margin-top:22px;color:var(--dim2);font-size:11.5px;line-height:1.8}
.legend{display:flex;gap:14px;font-size:11.5px;color:var(--dim);margin-top:6px;flex-wrap:wrap}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}
@media (max-width:1180px){.grid{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(3,1fr)}.grid3{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>化工期货 · 极端基差扫描看板</h1>
    <div class="sub">
      <span id="poolLine"></span>
      <span class="badge ok" id="convBadge">基差 = 现货基准价 − 期货收盘价</span>
      <span class="badge warn">分位为品种内历史位置，非多空信号</span>
    </div>
  </div>
  <div class="sub" id="genLine"></div>
</header>

<div class="kpis" id="kpis"></div>

<div class="note" id="sampleNote" style="margin:0 0 14px"></div>

<div class="toolbar">
  <div class="ctl">极端阈值 ±<b id="thVal">10%</b>
    <input type="range" id="th" min="2" max="25" step="1" value="10"></div>
  <div class="ctl">历史窗口 <b id="wyVal">3 年</b>
    <input type="range" id="wy" min="1" max="5" step="1" value="3"></div>
  <div class="ctl">品种筛选
    <div class="seg" id="seg">
      <button data-f="all" class="on">全部</button>
      <button data-f="extreme">仅极端</button>
      <button data-f="low">低位极端</button>
      <button data-f="high">高位极端</button>
    </div>
  </div>
  <div class="ctl" style="margin-left:auto">样本长度色标：<span class="dim">每日有效样本数（窗口内）</span></div>
</div>

<div class="grid">
  <div class="card">
    <h2><i></i>极端基差排行榜<span class="badge" id="rankNote"></span></h2>
    <div class="hint">按「品种自身」历史分位排序（低位极端在前，再高位极端）。基差金额不可跨品种比较，故榜单排序只用分位、不用金额。</div>
    <div class="rank" id="rank"></div>
  </div>
  <div class="card">
    <h2><i></i>历史分位分布</h2>
    <div class="hint">每个点在 0–100% 刻度上的位置 = 当前基差在该品种自身历史窗口中的分位。</div>
    <div class="distwrap" id="dist"></div>
    <div class="legend"><span><i style="background:var(--lo)"></i>低位极端</span>
      <span><i style="background:var(--warn)"></i>高位极端</span>
      <span><i style="background:#4a5a8a"></i>常态</span></div>
  </div>
</div>

<div class="card" style="margin-bottom:14px">
  <h2><i></i>数据覆盖核验</h2>
  <div class="hint">每个品种独立计算；样本长度、有效日期、合约映射与交叉校验全部展示，便于复现与质疑。不可扫描的品种单列原因。</div>
  <div style="max-height:430px;overflow:auto"><table id="cov"></table></div>
</div>

<div class="detail card" id="detail"></div>

<footer id="foot"></footer>
</div>

<script>/*__ECHARTS__*/</script>
<script>
const DATA = /*__DATA__*/;
const D = DATA.details || {};
const R = DATA.results || [];
const M = DATA.meta || {};
const COV = DATA.coverage || [];
let cur = null, filter = 'all';

const fmt = (v,d=2)=>{ if(v===''||v===null||v===undefined||Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString('zh-CN',{minimumFractionDigits:d,maximumFractionDigits:d}); };
const pctColor = p => { p=Number(p); if(Number.isNaN(p)) return '#6b7899';
  if(p<=10) return 'var(--lo)'; if(p>=90) return 'var(--hi)';
  if(p<50) return '#5b8cff'; return '#ffb84d'; };
const tagOf = (r)=>{ if(r.status!=='OK') return '<span class="tag na">数据不足/不可比</span>';
  if(r.flag==='低位极端') return '<span class="tag lo">低位极端</span>';
  if(r.flag==='高位极端') return '<span class="tag hi">高位极端</span>';
  return '<span class="tag mid">常态</span>'; };

/* ---------- KPI ---------- */
function renderKpis(){
  const ok = R.filter(r=>r.status==='OK').length;
  const ext = R.filter(r=>r.extreme).length;
  const low = R.filter(r=>r.flag==='低位极端').length;
  const high = R.filter(r=>r.flag==='高位极端').length;
  const ins = R.length-ok;
  const items = [
    ['品种池规模', R.length, '含不可扫描品种，全部披露'],
    ['可扫描品种', ok, '样本长度满足最小要求'],
    ['极端品种', ext, `低位 ${low} / 高位 ${high}`],
    ['数据不足', ins, '见覆盖核验表'],
    ['数据截至', M.data_latest||'—', '现货与期货同日对齐'],
    ['默认口径', (M.threshold*100).toFixed(0)+'% / '+M.window_years+'年', '可拖动上方滑杆改口径'],
  ];
  document.getElementById('kpis').innerHTML = items.map(([a,b,c])=>
    `<div class="kpi"><div class="lab">${a}</div><div class="val">${b}</div><div class="note">${c}</div></div>`).join('');
  document.getElementById('poolLine').textContent =
    `品种池：${(DATA.pool||[]).map(p=>p.name).join(' · ')}`;
  if(M.sample_note){
    document.getElementById('sampleNote').innerHTML =
      `<b>⚠ 样本长度如实披露：</b>${M.sample_note}<br>${M.sample_warning||''}`
      + (M.long_history_note? `<br><span class="dim">${M.long_history_note}</span>`:'');
  }
  document.getElementById('genLine').innerHTML =
    `生成于 ${M.generated_at||''}　版本 v${M.version||''}<br>现货：生意社(100ppi) 基准价　期货：新浪财经逐合约日线`;
  document.getElementById('foot').innerHTML =
    `口径声明：基差 = 现货基准价 − 期货收盘价；现货为含税基准价，期货为不含税价，二者相减天然含增值税项，`
    + `因此<b>只看该品种自身历史分位</b>，绝不跨品种比较基差金额。连续规则：${M.roll_rule==='near'?'近月连续（交割月≥当日最近月份，持仓<主力5%顺延）':'主力连续（每交易日持仓量最大合约）'}。`
    + `<br>未做任何插值/前值填充；期货缺该交易日即不出基差。分位仅为历史位置描述，<b>不构成多空信号</b>。`
    + `<br>数据源：生意社 100ppi 商品栏目公开文章（含逐日「基准价/市场基差」稿）· 新浪财经 InnerFuturesNewService 逐合约日线。`;
}

/* ---------- 经验分位（前端与后端同口径：中位秩） ---------- */
function addYears(iso, y){ const d=new Date(iso+'T00:00:00'); const t=new Date(d); t.setFullYear(d.getFullYear()+y);
  if(t.getMonth()!==d.getMonth()) t.setDate(0); return t; }
function recompute(r, wy, th){
  const dd = (D[r.code]||{}).daily||[];
  if(!dd.length || r.status!=='OK') return r;
  const last = dd[dd.length-1].date;
  const start = addYears(last, -wy).toISOString().slice(0,10);
  const win = dd.filter(x=>x.date>=start);
  if(win.length<50) return Object.assign({},r,{_n:win.length,_insuff:true});
  const vals = win.map(x=>x.basis).sort((a,b)=>a-b);
  const curB = win[win.length-1].basis;
  let lo=0,hi=vals.length;
  let a=0,b=vals.length; while(a<b){const m=(a+b)>>1; if(vals[m]<curB) a=m+1; else b=m;} lo=a;
  a=0;b=vals.length; while(a<b){const m=(a+b)>>1; if(vals[m]<=curB) a=m+1; else b=m;} hi=a;
  const pct = (lo+0.5*(hi-lo))/vals.length*100;
  const prev = win[Math.max(0,win.length-22)];
  let pl=0,ph=0; a=0;b=vals.length; while(a<b){const m=(a+b)>>1; if(vals[m]<prev.basis) a=m+1; else b=m;} pl=a;
  a=0;b=vals.length; while(a<b){const m=(a+b)>>1; if(vals[m]<=prev.basis) a=m+1; else b=m;} ph=a;
  const pctPrev=(pl+0.5*(ph-pl))/vals.length*100;
  const flag = pct<=th*100 ? '低位极端' : (pct>=100-th*100 ? '高位极端' : '常态');
  return Object.assign({},r,{_pct:pct,_flag:flag,_n:win.length,_start:start,_chg:curB-prev.basis,
    _chgPct:pct-pctPrev,_q10:vals[Math.floor((vals.length-1)*0.1)],_q90:vals[Math.floor((vals.length-1)*0.9)],
    _min:vals[0],_max:vals[vals.length-1],_cur:curB});
}
function getTh(){ return Number(document.getElementById('th').value)/100; }
function getWy(){ return Number(document.getElementById('wy').value); }
function rowsNow(){
  const th=getTh(), wy=getWy();
  return R.map(r=>recompute(r,wy,th)).map(r=>{
    if(r._pct!==undefined){ r.flag=r._flag; r.extreme=r._flag!=='常态'; r.pct_used=+r._pct.toFixed(1);
      r.n_obs=r._n; r.window_start=r._start; r.chg_1m=+(r._chg||0).toFixed(2); r.pct_delta_1m=+(r._chgPct||0).toFixed(1); }
    return r;
  });
}
function sortedRows(){
  const all = rowsNow();
  const ok = all.filter(r=>r.status==='OK');
  const order={'低位极端':0,'高位极端':1,'常态':2};
  ok.sort((x,y)=> (order[x.flag]-order[y.flag]) || (x.flag==='低位极端'? x.pct_used-y.pct_used : y.pct_used-x.pct_used));
  ok.forEach((r,i)=>r.rank=i+1);
  const na = all.filter(r=>r.status!=='OK');
  let list = ok.concat(na);
  if(filter==='extreme') list=list.filter(r=>r.extreme);
  if(filter==='low') list=list.filter(r=>r.flag==='低位极端');
  if(filter==='high') list=list.filter(r=>r.flag==='高位极端');
  return {list, all};
}

/* ---------- 排行榜 ---------- */
function renderRank(){
  const {list,all} = sortedRows();
  document.getElementById('rankNote').textContent =
    `可扫描 ${all.filter(r=>r.status==='OK').length} / 品种池 ${all.length}`;
  document.getElementById('rank').innerHTML = list.map((r,i)=>{
    if(r.status!=='OK'){
      return `<div class="rrow" data-code="${r.code}"><div class="rk">—</div>
        <div><div class="nm">${r.name}<small>${r.code}</small> ${tagOf(r)}</div>
        <div class="meta2">${r.reason||'样本不足，不出分位'}</div></div>
        <div class="bar"><span style="width:0"></span></div><div class="pctv dim">—</div></div>`;
    }
    const p=Math.max(0,Math.min(100,r.pct_used));
    const c = r.flag==='低位极端'?'var(--lo)':(r.flag==='高位极端'?'var(--hi)':'#4a5a8a');
    return `<div class="rrow${cur===r.code?' sel':''}" data-code="${r.code}">
      <div class="rk${(r.rank<=3)?' top':''}">${r.rank}</div>
      <div><div class="nm">${r.name}<small>${r.code} ${r.exchange||''}</small> ${tagOf(r)}</div>
        <div class="meta2">基差 ${fmt(r.basis_yuan)} ${r.unit||'元/吨'} · 主力 ${r.current_contract||''} · n=${r.n_obs}
        · <span class="${r.chg_1m>0?'up':(r.chg_1m<0?'down':'dim')}">近一月 ${r.chg_1m>0?'+':''}${fmt(r.chg_1m)}</span></div></div>
      <div class="bar"><span style="width:${p}%;background:linear-gradient(90deg,${c}88,${c})"></span></div>
      <div class="pctv" style="color:${c}">${fmt(r.pct_used,1)}%</div></div>`;
  }).join('') || '<div class="dim" style="padding:18px">当前筛选下没有品种</div>';
  document.querySelectorAll('.rrow').forEach(el=>el.onclick=()=>openDetail(el.dataset.code));
}

/* ---------- 分位分布 ---------- */
function renderDist(){
  const {list} = sortedRows();
  const ok = list.filter(r=>r.status==='OK');
  document.getElementById('dist').innerHTML = ok.map(r=>{
    const p=Math.max(0,Math.min(100,r.pct_used));
    const c=r.flag==='低位极端'?'var(--lo)':(r.flag==='高位极端'?'var(--hi)':'#5b8cff');
    return `<div class="dist" title="${r.name} 分位 ${r.pct_used}%">
      <span>${r.name} <span class="dim">n=${r.n_obs}</span></span>
      <div class="trk"><span class="dot" style="left:${p}%;background:${c}"></div>
      <span style="color:${c};text-align:right">${fmt(r.pct_used,0)}%</span></div>`;
  }).join('') || '<div class="dim">无可扫描品种</div>';
}

/* ---------- 覆盖核验 ---------- */
function renderCov(){
  const all = rowsNow();
  const head = `<tr><th>品种</th><th>状态</th><th class="num">窗口样本</th><th>有效窗口</th>
    <th class="num">全序列天数</th><th>现货起点</th><th>合约映射</th><th class="num">交叉校验</th><th>声明口径</th></tr>`;
  const body = all.map(r=>{
    const st = r.status==='OK'
      ? (r.extreme? tagOf(r) : '<span class="tag ok" style="background:#141f36;color:#9fb3e0;border:1px solid #2a3559">可扫描</span>')
      : `<span class="tag na">${r.status}</span>`;
    return `<tr class="click" data-code="${r.code}"><td><b>${r.name}</b> <span class="dim">${r.code}</span></td>
      <td>${st}</td><td class="num">${r.n_obs||'—'}</td>
      <td class="dim">${r.window_start? r.window_start+' ~ '+r.window_end : (r.reason||'')}</td>
      <td class="num">${r.n_total_basis_days||'—'}</td><td class="dim">${r.basis_first||'—'}</td>
      <td class="dim">${r.current_contract||'—'}</td>
      <td class="num">${r.xcheck&&r.xcheck.match_rate!=null? r.xcheck.match_rate+'%<span class="dim"> (n=${r.xcheck.checked})</span>':'—'}</td>
      <td class="dim" style="max-width:280px">${r.spot_spec||''}<br><span style="font-size:11px">${r.note||''}</span></td></tr>`;
  }).join('');
  document.getElementById('cov').innerHTML = head+body;
  document.querySelectorAll('#cov tr.click').forEach(el=>el.onclick=()=>openDetail(el.dataset.code));
}

/* ---------- 详情 ---------- */
function openDetail(code){
  cur=code;
  const all=rowsNow(); const r=all.find(x=>x.code===code);
  const dd=(D[code]||{}).daily||[];
  const panel=document.getElementById('detail');
  panel.classList.add('on');
  if(!dd.length){
    panel.innerHTML=`<div class="dhead"><div class="dtitle">${r.name} ${r.code}</div>
      <div>${tagOf(r)}</div></div><div class="note"><b>无法生成基差走势：</b>${r.reason||'无日度样本'}</div>`;
    renderRank(); window.scrollTo({top:panel.offsetTop-20,behavior:'smooth'}); return;
  }
  const wy=getWy(), th=getTh();
  const last=dd[dd.length-1].date; const start=addYears(last,-wy).toISOString().slice(0,10);
  const win=dd.filter(x=>x.date>=start);
  const pct=(r.pct_used!=null?r.pct_used:'—');
  const evs=(DATA.fundamentals&&DATA.fundamentals[code]&&DATA.fundamentals[code].events)||[];
  panel.innerHTML = `
  <div class="dhead">
    <div>
      <div class="dtitle">${r.name} <span class="dim" style="font-size:14px">${r.code} · ${r.exchange||''}</span></div>
      <div class="sub">${r.spot_spec||''}　|　现货地区/口径：${r.spot_region||'—'}（${r.spot_tax||''}）
      　|　期货合约：${r.current_contract||''}　|　连续规则：${r.roll_rule||''}</div>
    </div>
    <div style="text-align:right">${tagOf(r)}
      <div style="font-size:12px;color:var(--dim);margin-top:4px">历史分位 <b style="font-size:18px;color:${pctColor(pct)}">${pct}%</b>
      <span class="dim">（n=${r.n_obs}，${r.window_start} ~ ${r.window_end}）</span></div>
    </div>
  </div>
  <div class="grid" style="grid-template-columns:1.55fr 1fr;margin-top:12px">
    <div><div id="ch_basis" class="chart" style="height:330px"></div>
         <div id="ch_decomp" class="chart" style="height:210px;margin-top:6px"></div></div>
    <div><div id="ch_hist" class="chart" style="height:300px"></div>
         <div id="ch_near" class="chart" style="height:210px;margin-top:6px"></div></div>
  </div>
  <div style="display:grid;grid-template-columns:1.2fr 1fr;gap:12px;margin-top:12px">
    <div>
      <h2 style="font-size:13.5px;margin-bottom:8px"><i></i>库存 / 仓单 / 供需事件</h2>
      <div class="grid3" style="grid-template-columns:1fr 1fr;gap:10px">
        <div class="fact"><div class="k">交易所仓单（最新）</div><div class="v">${(r.inventory&&r.inventory.latest)? fmt(r.inventory.latest.inventory,0)+' 张' : (r.inventory&&r.inventory.status)||'未获取'}</div>
          <div class="k" style="margin-top:4px">${(r.inventory&&r.inventory.latest)? ('数据日 '+r.inventory.latest.date+' · '+((r.inventory.chg_20d>0?'近20日 +':'近20日 ')+fmt(r.inventory.chg_20d,0)+' 张 ('+fmt(r.inventory.chg_20d_pct,1)+'%)')) : ((r.inventory&&r.inventory.reason)||'')}</div></div>
        <div class="fact"><div class="k">基差近一月变化</div><div class="v ${r.chg_1m>0?'up':'down'}">${r.chg_1m>0?'+':''}${fmt(r.chg_1m)} ${r.unit||'元/吨'}</div>
          <div class="k" style="margin-top:4px">分位变化 ${r.pct_delta_1m>0?'+':''}${fmt(r.pct_delta_1m,1)} pct　现货 ${fmt(r.spot_chg_1m)} / 期货 ${fmt(r.fut_chg_1m)}</div></div>
      </div>
      ${(r.inventory&&r.inventory.series&&r.inventory.series.length>3)? '<div id="ch_inv" class="chart" style="height:150px;margin-top:8px"></div>' : '<div class="dim" style="font-size:11.5px;margin-top:8px">该品种未取到仓单日序列，因此不绘库存趋势（不做估算）。</div>'}
      <h2 style="font-size:13.5px;margin:12px 0 8px"><i></i>可获取的产业事件（生意社资讯）</h2>
      <ul class="ev">${evs.length? evs.map(e=>`<li><time>${e.date}</time><a href="${e.url}" target="_blank" rel="noopener">${e.title}</a></li>`).join('') : '<li class="dim">该栏目未提供检修/投产/库存类稿件（本站栏目以价格稿为主），如需供需事件建议接入专业资讯源</li>'}</ul>
    </div>
    <div>
      <h2 style="font-size:13.5px;margin-bottom:8px"><i></i>口径与极值</h2>
      <div class="grid3" style="grid-template-columns:1fr 1fr">
        <div class="fact"><div class="k">当前基差</div><div class="v">${fmt(r.basis_yuan)} ${r.unit||'元/吨'}</div></div>
        <div class="fact"><div class="k">现货 → 期货</div><div class="v">${fmt(r.spot)} → ${fmt(r.fut)}</div></div>
        <div class="fact"><div class="k">窗口内最高基差</div><div class="v">${fmt(r.hist_max)} <span class="dim" style="font-size:11px">${r.hist_max_date||''}</span></div></div>
        <div class="fact"><div class="k">窗口内最低基差</div><div class="v">${fmt(r.hist_min)} <span class="dim" style="font-size:11px">${r.hist_min_date||''}</span></div></div>
        <div class="fact"><div class="k">分位（严格/中位/含当日）</div><div class="v">${r.pct_strict}% / ${r.pct_midrank}% / ${r.pct_le}%</div></div>
        <div class="fact"><div class="k">距历史极值</div><div class="v">高于最低 ${fmt(r.pmin_gap)}，距最高 ${fmt(r.pmax_gap)}</div></div>
      </div>
      <div class="note"><b>口径声明：</b>${r.spot_spec||''}；交割品级：${r.contract_spec||''}；交割区域：${r.futures_region||''}；
      合约乘数 ${r.multiplier||'—'}，最小变动 ${r.tick||'—'}；最后交易日：${r.last_trade_rule||'—'}。
      ${r.note||''}。<br><b>换月披露：</b>窗口内换月 ${r.roll_count||0} 次${(r.roll_jumps_big&&r.roll_jumps_big.length)?('，其中 '+r.roll_jumps_big.length+' 次基差跳变≥30元/吨（换月伪跳空，已保留未修正）'):''}。</div>
    </div>
  </div>`;
  drawCharts(r, dd, win, th);
  renderRank();
  window.scrollTo({top:panel.offsetTop-14,behavior:'smooth'});
}

function baseGrid(){ return {left:58,right:18,top:26,bottom:26}; }
function drawCharts(r, dd, win, th){
  const okCss = v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const axisStyle = {axisLine:{lineStyle:{color:'#2a3559'}},axisLabel:{color:'#93a0c4',fontSize:11},
    splitLine:{lineStyle:{color:'#1c2542'}}};
  const wy=getWy(); const last=dd[dd.length-1].date;
  const allStart = addYears(last,-wy).toISOString().slice(0,10);
  // 1) 基差走势 + 分位带
  const vals = win.map(x=>x.basis).slice().sort((a,b)=>a-b);
  const q=(p)=>vals[Math.min(vals.length-1,Math.max(0,Math.floor((vals.length-1)*p)))];
  const q10=q(0.1), q90=q(0.9), q50=q(0.5);
  const ch1=echarts.init(document.getElementById('ch_basis'));
  ch1.setOption({
    backgroundColor:'transparent',animationDuration:500,
    title:{text:`基差走势（${wy}年窗口，日均 ${dd.length>0?win.length:0} 个有效日）`,left:0,top:0,
      textStyle:{color:'#e8ecf8',fontSize:12.5,fontWeight:600}},
    tooltip:{trigger:'axis',backgroundColor:'#0e1730',borderColor:'#2a3559',textStyle:{color:'#e8ecf8',fontSize:12},
      formatter:ps=>{const i=ps[0].dataIndex,x=win[i];
        return `<b>${x.date}</b><br>基差 ${fmt(x.basis)}<br>现货 ${fmt(x.spot)} / 期货 ${fmt(x.fut)}<br>合约 ${x.symbol}`;}},
    grid:{left:58,right:54,top:34,bottom:26},
    xAxis:{type:'category',data:win.map(x=>x.date),boundaryGap:false,...axisStyle,
      axisLabel:{color:'#93a0c4',fontSize:10.5,formatter:v=>v.slice(2)}},
    yAxis:{type:'value',scale:true,...axisStyle,
      axisLabel:{color:'#93a0c4',fontSize:11,formatter:v=>fmt(v,0)}},
    series:[
      {name:'历史90分位',type:'line',data:win.map(()=>q90),symbol:'none',lineStyle:{color:'#ff7a5933',width:1,type:'dashed'},silent:true},
      {name:'历史中位',type:'line',data:win.map(()=>q50),symbol:'none',lineStyle:{color:'#8f6bff88',width:1,type:'dashed'},silent:true},
      {name:'历史10分位',type:'line',data:win.map(()=>q10),symbol:'none',lineStyle:{color:'#2ec4b633',width:1,type:'dashed'},silent:true},
      {name:'基差',type:'line',data:win.map(x=>x.basis),symbol:'none',showSymbol:false,
        lineStyle:{color:'#5b8cff',width:1.8},areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[
          {offset:0,color:'rgba(91,140,255,.34)'},{offset:1,color:'rgba(91,140,255,0)'}])},
        markPoint:{symbolSize:9,data:[{type:'max',name:'最高'},{type:'min',name:'最低'}],
          label:{color:'#0b1020',fontSize:10,fontWeight:700},itemStyle:{color:'#ffd166'}}},
    ]});
  // 2) 现货/期货分解（近 120 日）
  const rec = win.slice(-120);
  const ch2=echarts.init(document.getElementById('ch_decomp'));
  ch2.setOption({backgroundColor:'transparent',
    title:{text:'现货基准价 vs 期货收盘价（近120个有效日）',left:0,top:0,textStyle:{color:'#93a0c4',fontSize:12}},
    tooltip:{trigger:'axis',backgroundColor:'#0e1730',borderColor:'#2a3559',textStyle:{color:'#e8ecf8'}},
    legend:{data:['现货','期货'],right:0,top:0,textStyle:{color:'#93a0c4',fontSize:11},itemWidth:12,itemHeight:8},
    grid:{left:58,right:20,top:30,bottom:22},
    xAxis:{type:'category',data:rec.map(x=>x.date),boundaryGap:false,...axisStyle,
      axisLabel:{color:'#93a0c4',fontSize:10,formatter:v=>v.slice(5)}},
    yAxis:{type:'value',scale:true,...axisStyle},
    series:[
      {name:'现货',type:'line',data:rec.map(x=>x.spot),symbol:'none',lineStyle:{color:'#ffb84d',width:1.6}},
      {name:'期货',type:'line',data:rec.map(x=>x.fut),symbol:'none',lineStyle:{color:'#3ddc97',width:1.6}},
    ]});
  // 3) 分位分布直方图
  const bin=10, cnt=new Array(bin).fill(0);
  vals.forEach(v=>{let k=Math.floor((v-vals[0])/((vals[vals.length-1]-vals[0])||1)*bin); k=Math.min(bin-1,Math.max(0,k)); cnt[k]++;});
  const edges=Array.from({length:bin},(_,i)=>fmt(vals[0]+(vals[vals.length-1]-vals[0])*i/bin,0));
  const curB=win[win.length-1].basis;
  const ch3=echarts.init(document.getElementById('ch_hist'));
  ch3.setOption({backgroundColor:'transparent',
    title:{text:'品种自身历史基差分布'+(r.extreme?'（当前处于极端区）':''),left:0,top:0,
      textStyle:{color:'#e8ecf8',fontSize:12.5,fontWeight:600}},
    tooltip:{trigger:'axis',backgroundColor:'#0e1730',borderColor:'#2a3559',textStyle:{color:'#e8ecf8'},
      formatter:ps=>`基差约 ${edges[ps[0].dataIndex]}：<b>${ps[0].value}</b> 天`},
    grid:{left:48,right:16,top:34,bottom:24},
    xAxis:{type:'category',data:edges,...axisStyle,axisLabel:{color:'#93a0c4',fontSize:10}},
    yAxis:{type:'value',...axisStyle},
    series:[{type:'bar',data:cnt,barWidth:'86%',
      itemStyle:{borderRadius:[3,3,0,0],color:(p)=> {
        const e=vals[0]+(vals[vals.length-1]-vals[0])*p.dataIndex/bin;
        return e<curB?'rgba(91,140,255,.75)':'rgba(91,140,255,.32)';}},
      markLine:{symbol:'none',silent:true,data:[{xAxis:Math.min(bin-1,Math.floor((curB-vals[0])/((vals[vals.length-1]-vals[0])||1)*bin)),
        label:{formatter:'当前 ',color:'#ffd166',fontSize:10},lineStyle:{color:'#ffd166',type:'dashed'}}]}}]});
  // 4) 近一月分位变化
  const nb = Math.min(46, win.length), seg = win.slice(-nb);
  const ch4=echarts.init(document.getElementById('ch_near'));
  const pctSeries=[];
  for(const x of seg){
    let a=0,b=vals.length; while(a<b){const m=(a+b)>>1; if(vals[m]<x.basis) a=m+1; else b=m;}
    let c=0,d=vals.length; while(c<d){const m=(c+d)>>1; if(vals[m]<=x.basis) c=m+1; else d=m;}
    pctSeries.push(+(((a+0.5*(c-a))/vals.length)*100).toFixed(1));
  }
  ch4.setOption({backgroundColor:'transparent',
    title:{text:'近一月分位轨迹（%）',left:0,top:0,textStyle:{color:'#93a0c4',fontSize:12}},
    tooltip:{trigger:'axis',backgroundColor:'#0e1730',borderColor:'#2a3559',textStyle:{color:'#e8ecf8'}},
    grid:{left:48,right:20,top:30,bottom:22},
    xAxis:{type:'category',data:seg.map(x=>x.date),...axisStyle,axisLabel:{color:'#93a0c4',fontSize:10,formatter:v=>v.slice(5)}},
    yAxis:{type:'value',min:0,max:100,...axisStyle,axisLabel:{color:'#93a0c4',fontSize:10,formatter:'{value}%'}},
    series:[{type:'line',data:pctSeries,symbol:'none',lineStyle:{color:'#8f6bff',width:2},
      areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(143,107,255,.35)'},{offset:1,color:'rgba(143,107,255,0)'}])},
      markLine:{symbol:'none',silent:true,data:[{yAxis:th*100,label:{formatter:'低阈',color:'#2ec4b6',fontSize:10},lineStyle:{color:'#2ec4b655',type:'dashed'}},
        {yAxis:100-th*100,label:{formatter:'高阈',color:'#ff7a59',fontSize:10},lineStyle:{color:'#ff7a5955',type:'dashed'}}]}}]});
  window.onresize=()=>{[ch1,ch2,ch3,ch4].forEach(c=>c&&c.resize());};
  // 5) 交易所仓单趋势
  const invEl=document.getElementById('ch_inv');
  if(invEl && r.inventory && r.inventory.series && r.inventory.series.length>3){
    const s=r.inventory.series;
    const ch5=echarts.init(invEl);
    ch5.setOption({backgroundColor:'transparent',
      title:{text:'交易所仓单（张）· 近'+s.length+'个交易日',left:0,top:0,textStyle:{color:'#93a0c4',fontSize:11.5}},
      tooltip:{trigger:'axis',backgroundColor:'#0e1730',borderColor:'#2a3559',textStyle:{color:'#e8ecf8',fontSize:12}},
      grid:{left:64,right:16,top:28,bottom:20},
      xAxis:{type:'category',data:s.map(x=>x.date),boundaryGap:false,...axisStyle,
        axisLabel:{color:'#93a0c4',fontSize:10,formatter:v=>v.slice(5)}},
      yAxis:{type:'value',scale:true,...axisStyle,axisLabel:{color:'#93a0c4',fontSize:10,formatter:v=>fmt(v,0)}},
      series:[{type:'line',data:s.map(x=>x.inventory),symbol:'none',step:'end',
        lineStyle:{color:'#ffb84d',width:1.8},
        areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[
          {offset:0,color:'rgba(255,184,77,.28)'},{offset:1,color:'rgba(255,184,77,0)'}])}}]});
    window.onresize=()=>{[ch1,ch2,ch3,ch4,ch5].forEach(c=>c&&c.resize());};
  }
}

/* ---------- 事件绑定 ---------- */
function renderAll(){ renderKpis(); renderRank(); renderDist(); renderCov();
  if(cur) { /* 保持选中项高亮 */ } }
document.getElementById('th').oninput=e=>{ document.getElementById('thVal').textContent=e.target.value+'%'; renderAll(); if(cur) openDetail(cur); };
document.getElementById('wy').oninput=e=>{ document.getElementById('wyVal').textContent=e.target.value+' 年'; renderAll(); if(cur) openDetail(cur); };
document.querySelectorAll('#seg button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#seg button').forEach(x=>x.classList.remove('on')); b.classList.add('on');
  filter=b.dataset.f; renderRank(); renderDist(); });
renderAll();
</script>
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description='生成 HTML 看板')
    ap.add_argument('--result', default='out/scan_result.json')
    ap.add_argument('--out', default='out/极端基差扫描看板.html')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    with open(a.result, encoding='utf-8') as f:
        result = json.load(f)
    html = build(result)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)
    print('[html] %s  %.1f KB' % (a.out, len(html.encode('utf-8')) / 1024))


if __name__ == '__main__':
    main()
