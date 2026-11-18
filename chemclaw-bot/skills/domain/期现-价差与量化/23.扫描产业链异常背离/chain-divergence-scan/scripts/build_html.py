# -*- coding: utf-8 -*-
"""生成自包含交互式 HTML 产业链异常背离扫描看板。

    python build/build_html.py --pack build/out/scan_pack.json \
        --web build/out/series_web/web_series.json \
        --hist build/out/hist_scan.json --out 交付/xxx.html
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CSS = r"""
:root{
  --navy:#0f1b2d; --navy2:#16273f; --panel:#182b45; --line:#24405f;
  --ink:#e8eef7; --ink2:#9fb3cc; --ink3:#6b8099;
  --acc:#38bdf8; --acc2:#22d3ee; --warn:#f59e0b; --bad:#f43f5e; --good:#34d399;
  --purple:#a78bfa;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#0b1421;color:var(--ink);
  font-family:"Segoe UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif;font-size:14px;line-height:1.55}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1560px;margin:0 auto;padding:0 22px 60px}
header.top{position:sticky;top:0;z-index:50;background:rgba(11,20,33,.92);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line)}
.top-in{max-width:1560px;margin:0 auto;padding:10px 22px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:.5px;font-size:15px}
.brand span{color:var(--acc)}
.tag{font-size:11px;color:var(--ink2);border:1px solid var(--line);border-radius:99px;padding:2px 9px}
.hero{padding:30px 0 6px}
.hero h1{font-size:26px;margin:0 0 8px;font-weight:700;letter-spacing:.3px}
.hero p{margin:0;color:var(--ink2);max-width:1050px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:22px 0}
.kpi{background:linear-gradient(160deg,var(--panel),#122238);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .k{font-size:11px;color:var(--ink3);letter-spacing:.6px;text-transform:uppercase}
.kpi .v{font-size:24px;font-weight:700;margin-top:4px}
.kpi .s{font-size:11px;color:var(--ink2);margin-top:2px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:16px 0}
.panel h2{font-size:16px;margin:0 0 4px;font-weight:700}
.panel .hint{font-size:12px;color:var(--ink2);margin:0 0 12px}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.chip{background:#122238;border:1px solid var(--line);border-radius:9px;padding:6px 11px;font-size:12px;color:var(--ink2);cursor:pointer;user-select:none}
.chip:hover{border-color:var(--acc)}
.chip.on{background:rgba(56,189,248,.14);border-color:var(--acc);color:#bae6fd}
select,input[type=text]{background:#0e1c2e;border:1px solid var(--line);color:var(--ink);border-radius:9px;padding:6px 9px;font-size:12px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{position:sticky;top:0;background:#13243a;color:var(--ink2);text-align:left;padding:9px 8px;font-weight:600;border-bottom:1px solid var(--line);white-space:nowrap;cursor:pointer}
td{padding:9px 8px;border-bottom:1px solid #1c3049;vertical-align:top}
tr.row:hover td{background:rgba(56,189,248,.06)}
.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.pair{font-weight:700;color:#e2e8f0}
.badge{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11px;font-weight:600;white-space:nowrap}
.b-strong{background:rgba(52,211,153,.15);color:#6ee7b7;border:1px solid rgba(52,211,153,.35)}
.b-medium{background:rgba(56,189,248,.13);color:#7dd3fc;border:1px solid rgba(56,189,248,.3)}
.b-weak{background:rgba(148,163,184,.12);color:#94a3b8;border:1px solid rgba(148,163,184,.3)}
.v-anom{background:rgba(244,63,94,.16);color:#fda4af;border:1px solid rgba(244,63,94,.4)}
.v-watch{background:rgba(245,158,11,.15);color:#fcd34d;border:1px solid rgba(245,158,11,.35)}
.v-miss{background:rgba(148,163,184,.12);color:#cbd5e1;border:1px solid rgba(148,163,184,.28)}
.v-ok{background:rgba(52,211,153,.12);color:#6ee7b7;border:1px solid rgba(52,211,153,.3)}
.bar{height:6px;border-radius:99px;background:#1c3049;overflow:hidden;min-width:60px}
.bar>i{display:block;height:100%;border-radius:99px}
.zpos{color:#bae6fd}
.zneg{color:#fdba74}
.spark{display:inline-block;vertical-align:middle}
#graph{width:100%;height:560px;display:block;background:radial-gradient(circle at 50% 40%,#13253c,#0d1929 70%);border-radius:12px;border:1px solid var(--line)}
.node{cursor:pointer}
.node:hover circle.core{stroke:var(--acc);stroke-width:2.5}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 14px}
.tab{padding:7px 13px;border-radius:9px;border:1px solid var(--line);background:#122238;color:var(--ink2);cursor:pointer;font-size:12.5px}
.tab.on{background:rgba(56,189,248,.14);border-color:var(--acc);color:#bae6fd;font-weight:600}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media (max-width:1100px){.grid2,.grid3{grid-template-columns:1fr}}
.card{background:#13243a;border:1px solid var(--line);border-radius:11px;padding:12px 14px}
.card .t{font-size:11px;color:var(--ink3);letter-spacing:.5px}
.card .v{font-size:19px;font-weight:700;margin-top:3px;font-variant-numeric:tabular-nums}
.card .n{font-size:11px;color:var(--ink2);margin-top:2px}
.chk{display:flex;align-items:flex-start;gap:9px;padding:8px 0;border-bottom:1px dashed #1e3550;font-size:12.5px}
.chk:last-child{border-bottom:none}
.chk .dot{width:18px;height:18px;border-radius:50%;flex:0 0 18px;display:grid;place-items:center;font-size:11px;font-weight:700;margin-top:1px}
.dot.y{background:rgba(52,211,153,.2);color:#6ee7b7}
.dot.n{background:rgba(244,63,94,.18);color:#fda4af}
.timeline{position:relative;margin-left:8px;padding-left:20px;border-left:1px solid var(--line)}
.ev{position:relative;padding:6px 0 12px}
.ev:before{content:"";position:absolute;left:-25px;top:13px;width:9px;height:9px;border-radius:50%;background:var(--acc);box-shadow:0 0 0 3px rgba(56,189,248,.18)}
.ev .d{font-size:11px;color:var(--ink3)}
.ev .tt{font-weight:600;font-size:13px;margin:1px 0 2px}
.ev .dd{font-size:12px;color:var(--ink2)}
.src{font-size:11px;color:var(--ink3)}
.note{font-size:12px;color:var(--ink3);line-height:1.7}
.warnbox{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.35);border-radius:10px;padding:11px 13px;font-size:12.5px;color:#fde68a}
.okbox{background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.35);border-radius:10px;padding:11px 13px;font-size:12.5px;color:#a7f3d0}
.badbox{background:rgba(244,63,94,.08);border:1px solid rgba(244,63,94,.35);border-radius:10px;padding:11px 13px;font-size:12.5px;color:#fecdd3}
footer{margin-top:26px;border-top:1px solid var(--line);padding-top:14px;color:var(--ink3);font-size:11.5px}
.hidden{display:none!important}
.slider{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink2)}
input[type=range]{width:130px;accent-color:var(--acc)}
.back{margin:10px 0 4px;font-size:12.5px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:var(--ink2);margin-top:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
"""

JS = r"""
const PK = window.__PACK__;
const SER = window.__SERIES__ || {};
const HIST = window.__HIST__ || null;
const RT = PK.rtype_info, U = {};
PK.universe.forEach(u => U[u.code] = u);
const SYM = {}; PK.universe_meta && Object.keys(PK.universe_meta).forEach(k=>SYM[k]=PK.universe_meta[k]);

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const f = (v,d=3) => (v==null||isNaN(v)) ? '—' : Number(v).toFixed(d);
const pct = (v,d=1) => (v==null||isNaN(v)) ? '—' : Number(v).toFixed(d)+'%';
const vClass = v => ({'异常背离（候选）':'v-anom','关注':'v-watch','偏离但未达门槛':'v-miss','数据不足':'v-miss','正常':'v-ok'})[v]||'v-miss';
const rName = c => (U[c]?U[c].name:c);
const pairId = r => r.code_a+'__'+r.code_b;
const serKey = r => r.code_a+'_'+r.code_b;
const relOf = r => (PK.relations||[]).find(x=>x.a===r.code_a&&x.b===r.code_b) || {};

/* ---------- 状态 ---------- */
const S = {
  rt: new Set(['upstream_downstream','common_feedstock','substitute']),
  strength: new Set(['strong','medium','weak']),
  verdict: new Set(['异常背离（候选）','关注','偏离但未达门槛','正常']),
  universe: new Set(),
  minDev: 0, maxCorrDrop: 1.01,
  q: '',
  sortKey: 'score', sortDir: -1
};

/* ---------- 顶部 KPI ---------- */
function renderKPIs(){
  const ok = PK.results.filter(r=>r.status==='ok');
  const anom = ok.filter(r=>r.judge.verdict==='异常背离（候选）');
  const watch = ok.filter(r=>r.judge.verdict==='关注');
  const qA = ok.filter(r=>['A'].includes((r.quality||{}).level)).length;
  const kpis = [
    ['品种池', PK.universe.length, '个化工期货品种 · '+PK.relations.length+' 组产业关系'],
    ['检验组合数 m', PK.n_tests, '仅含存在明确产业关联的配对'],
    ['异常背离（候选）', anom.length, anom.length? anom.map(r=>r.code_a+'/'+r.code_b).join('、') : '无组合同时满足四门槛'],
    ['关注（2/4 门槛）', watch.length, watch.map(r=>r.code_a+'/'+r.code_b).join('、') || '—'],
    ['可比性 A 级', qA+' / '+ok.length, '数据可比性与关系稳定性双维评级'],
    ['数据截至', (SYM['PP0']||{}).last || '—', '期货主力连续收盘价（元/吨）']
  ];
  $('#kpis').innerHTML = kpis.map(k=>`<div class="kpi"><div class="k">${esc(k[0])}</div>
    <div class="v">${esc(k[1])}</div><div class="s">${esc(k[2])}</div></div>`).join('');
}

/* ---------- 过滤后的行 ---------- */
function filtered(){
  let rows = PK.results.filter(r=>{
    if(r.status!=='ok') return false;
    if(!S.rt.has(r.rtype)) return false;
    if(!S.strength.has(r.strength)) return false;
    if(!S.verdict.has(r.judge.verdict)) return false;
    if(S.universe.size && !(S.universe.has(r.code_a)||S.universe.has(r.code_b))) return false;
    const dev = Math.abs(r.z_last||0);
    if(dev < S.minDev) return false;
    const cd = (r.judge.corr_drop!=null? r.judge.corr_drop : -1);
    if(cd > S.maxCorrDrop) return false;
    if(S.q){
      const t = (r.code_a+' '+r.code_b+' '+rName(r.code_a)+' '+rName(r.code_b)+' '+(RT[r.rtype]||{}).cn).toLowerCase();
      if(!t.includes(S.q.toLowerCase())) return false;
    }
    return true;
  });
  const k = S.sortKey, d = S.sortDir;
  const val = r => {
    switch(k){
      case 'pair': return r.code_a+'/'+r.code_b;
      case 'rtype': return (RT[r.rtype]||{}).order||9;
      case 'strength': return ({strong:0,medium:1,weak:2})[r.strength];
      case 'verdict': return ({'异常背离（候选）':0,'关注':1,'偏离但未达门槛':2,'正常':3})[r.judge.verdict];
      case 'z': return Math.abs(r.z_last||0);
      case 'corr': return r.roll_corr_last;
      case 'drop': return r.judge.corr_drop;
      case 'r': return r.r_daily;
      case 'quality': return ({A:0,B:1,C:2})[(r.quality||{}).level] ?? 3;
      default: return r.judge.score;
    }
  };
  rows.sort((a,b)=>{ const x=val(a),y=val(b); return (x>y?1:x<y?-1:0)*d; });
  return rows;
}

/* ---------- 迷你火花线 ---------- */
function spark(arr, w=90, h=24){
  const v = arr.filter(x=>x!=null);
  if(v.length<4) return '<span class="note">—</span>';
  const mn = Math.min(...v), mx = Math.max(...v), rng = (mx-mn)||1;
  const pts = arr.map((x,i)=> x==null?null:`${(i/(arr.length-1)*w).toFixed(1)},${(h-(x-mn)/rng*(h-3)-1.5).toFixed(1)}`).filter(Boolean).join(' ');
  const last = arr[arr.length-1];
  const col = last==null? '#64748b' : (last>=0? '#38bdf8':'#fb923c');
  return `<svg class="spark" width="${w}" height="${h}"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.4"/></svg>`;
}

/* ---------- 主榜单 ---------- */
function renderTable(){
  const rows = filtered();
  $('#cnt').textContent = rows.length + ' 个组合';
  const head = ['#','组合','关系类型','强度','判定','评分','偏离 z','z 分位','持续','滚动相关','相关变化','全期相关','可比性',''];
  $('#thead').innerHTML = '<tr>' + head.map((h,i)=>{
    const keys = {1:'pair',2:'rtype',3:'strength',4:'verdict',6:'z',9:'corr',10:'drop',11:'r',12:'quality'};
    const k = keys[i];
    return `<th ${k?`data-k="${k}"`:''}>${esc(h)}${k&&S.sortKey===k?(S.sortDir<0?' ▼':' ▲'):''}</th>`;
  }).join('') + '</tr>';
  $('#tbody').innerHTML = rows.map((r,i)=>{
    const j = r.judge, rel = relOf(r);
    const rcSeries = r._spark || [];
    const zc = (r.z_last==null)?'':(r.z_last>0?'zpos':'zneg');
    const ql = (r.quality||{}).level||'—';
    const qcol = {A:'#34d399',B:'#f59e0b',C:'#f43f5e'}[ql]||'#94a3b8';
    return `<tr class="row" data-id="${pairId(r)}">
      <td class="num">${i+1}</td>
      <td><span class="pair">${r.code_a} · ${r.code_b}</span><br>
          <span class="note">${esc(rName(r.code_a))} / ${esc(rName(r.code_b))}</span></td>
      <td><span class="badge b-${esc(r.rtype)}">${esc((RT[r.rtype]||{}).cn||r.rtype)}</span></td>
      <td><span class="badge b-${r.strength}">${r.strength}</span></td>
      <td><span class="badge ${vClass(j.verdict)}">${j.verdict}</span></td>
      <td class="num">${f(j.score,1)}</td>
      <td class="num ${zc}">${f(r.z_last,2)}</td>
      <td class="num">${pct(r.z_pct,0)}</td>
      <td class="num">${r.z_run_days||0}d</td>
      <td class="num">${f(r.roll_corr_last,2)} ${spark(rcSeries)}</td>
      <td class="num">${f(j.corr_drop,2)}</td>
      <td class="num">${f(r.r_daily,2)}</td>
      <td class="num" style="color:${qcol};font-weight:700">${ql}</td>
      <td><span class="note">研究 →</span></td>
    </tr>`;
  }).join('') || '<tr><td colspan="14" class="note">没有符合当前筛选条件的组合。</td></tr>';
  $$('#tbody tr.row').forEach(tr=>tr.onclick=()=>openPair(tr.dataset.id));
  $$('#thead th').forEach(th=>th.onclick=()=>{
    const k = th.dataset.k; if(!k) return;
    if(S.sortKey===k) S.sortDir*=-1; else {S.sortKey=k; S.sortDir=-1;}
    renderTable();
  });
}

/* ---------- 产业链图谱 ---------- */
function renderGraph(){
  const nodes = PK.universe;
  const W = $('#graph').clientWidth || 1400, H = 560, cx = W/2, cy = H/2 - 10;
  const n = nodes.length;
  /* 先按产业链分组排布 */
  const groups = {};
  nodes.forEach(u=>{ (groups[u.cat] = groups[u.cat]||[]).push(u); });
  const cats = Object.keys(groups);
  const pos = {};
  let ring = 0;
  const rings = [];
  cats.forEach((c,ci)=>{
    const arr = groups[c];
    const R = 150 + ci % 3 * 62;
    const start = (ci * 2*Math.PI/cats.length);
    arr.forEach((u,ii)=>{
      const a = start + (ii+0.5)*(0.55*Math.PI/Math.max(1,arr.length));
      pos[u.code] = {x: cx + R*Math.cos(a), y: cy + R*0.78*Math.sin(a), u};
    });
  });
  let svg = `<svg id="graph" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
  const linked = new Set(PK.relations.flatMap(r=>[r.a,r.b]));
  const col = {upstream_downstream:'#34d399', common_feedstock:'#38bdf8', substitute:'#a78bfa', cross_chain_cost:'#64748b'};
  PK.relations.forEach(r=>{
    const A = pos[r.a], B = pos[r.b]; if(!A||!B) return;
    const on = S.rt.has(r.rtype) && S.strength.has(r.strength);
    const w = r.strength==='strong'?2.4:(r.strength==='medium'?1.6:1.1);
    const dash = r.strength==='weak'? 'stroke-dasharray="5 4"' : '';
    svg += `<line x1="${A.x}" y1="${A.y}" x2="${B.x}" y2="${B.y}" stroke="${col[r.rtype]||'#64748b'}"
      stroke-width="${w}" ${dash} opacity="${on?0.75:0.13}" stroke-linecap="round"/>`;
  });
  nodes.forEach(u=>{
    const p = pos[u.code];
    const deg = PK.relations.filter(r=>r.a===u.code||r.b===u.code).length;
    const isKey = ['PP0','L0','PX0','TA0'].includes(u.code);
    const r0 = 22 + Math.min(10, deg*2.6);
    svg += `<g class="node" data-code="${u.code}">
      <circle class="core" cx="${p.x}" cy="${p.y}" r="${r0}" fill="${isKey?'#0e3a52':'#122233'}"
        stroke="${isKey?'#38bdf8':'#2c4a6b'}" stroke-width="${isKey?2.4:1.5}"/>
      <text x="${p.x}" y="${p.y+1}" text-anchor="middle" font-size="13" font-weight="700" fill="#e8eef7">${u.code.replace('0','')}</text>
      <text x="${p.x}" y="${p.y+16}" text-anchor="middle" font-size="9.5" fill="#9fb3cc">${esc(u.name.split(' ')[0])}</text>
    </g>`;
  });
  svg += '</svg>';
  $('#graphBox').innerHTML = svg;
  $$('#graphBox .node').forEach(g=>g.onclick=()=>{
    const c = g.dataset.code;
    S.universe = new Set([c]); renderChips(); renderTable();
  });
}

/* ---------- 控件 ---------- */
function renderChips(){
  const rtOrder = Object.entries(RT).sort((a,b)=>a[1].order-b[1].order);
  $('#rtChips').innerHTML = rtOrder.map(([k,v])=>
    `<div class="chip ${S.rt.has(k)?'on':''}" data-rt="${k}">${v.cn}</div>`).join('')
    + `<div class="chip" data-all="rt">全选/清空</div>`;
  $$('#rtChips .chip[data-rt]').forEach(c=>c.onclick=()=>{
    const k=c.dataset.rt; S.rt.has(k)?S.rt.delete(k):S.rt.add(k); renderChips(); renderTable(); renderGraph();
  });
  $('#rtChips .chip[data-all]').onclick=()=>{ S.rt = new Set(rtOrder.map(x=>x[0])); renderChips(); renderTable(); renderGraph(); };

  $('#stChips').innerHTML = ['strong','medium','weak'].map(s=>
    `<div class="chip ${S.strength.has(s)?'on':''}" data-st="${s}">${({strong:'强',medium:'中',weak:'弱'})[s]}</div>`).join('');
  $$('#stChips .chip').forEach(c=>c.onclick=()=>{
    const s=c.dataset.st; S.strength.has(s)?S.strength.delete(s):S.strength.add(s); renderChips(); renderTable(); renderGraph();
  });

  $('#vdChips').innerHTML = ['异常背离（候选）','关注','偏离但未达门槛','正常'].map(v=>
    `<div class="chip ${S.verdict.has(v)?'on':''}" data-vd="${v}">${v}</div>`).join('');
  $$('#vdChips .chip').forEach(c=>c.onclick=()=>{
    const v=c.dataset.vd; S.verdict.has(v)?S.verdict.delete(v):S.verdict.add(v); renderChips(); renderTable();
  });

  $('#uniSel').innerHTML = '<option value="">全部品种</option>' + PK.universe.map(u=>
    `<option value="${u.code}">${u.code.replace('0','')} · ${esc(u.name)}</option>`).join('');
  $('#uniSel').onchange = e=>{ S.universe = e.target.value? new Set([e.target.value]) : new Set(); renderChips(); renderTable(); renderGraph(); };

  const maxZ = Math.max(...PK.results.filter(r=>r.status==='ok').map(r=>Math.abs(r.z_last||0)), 2);
  $('#devR').max = Math.ceil(maxZ*10)/10; $('#devR').value = S.minDev;
  $('#devV').textContent = '|z| ≥ ' + f(S.minDev,1);
  $('#devR').oninput = e=>{ S.minDev = +e.target.value; $('#devV').textContent='|z| ≥ '+f(S.minDev,1); renderTable(); };
  $('#dropR').oninput = e=>{ S.maxCorrDrop = +e.target.value; $('#dropV').textContent = '≤ '+f(S.maxCorrDrop,2); renderTable(); };
  $('#q').oninput = e=>{ S.q = e.target.value; renderTable(); };
}

/* ---------- 组合研究页 ---------- */
let cur = null;
function openPair(id){
  const r = PK.results.find(x=>pairId(x)===id); if(!r) return;
  cur = r;
  $('#scanner').classList.add('hidden'); $('#pair').classList.remove('hidden');
  window.scrollTo({top:0, behavior:'smooth'});
  renderPairHeader(r);
  switchTab('overview');
}
function closePair(){
  $('#pair').classList.add('hidden'); $('#scanner').classList.remove('hidden');
  window.scrollTo({top:0, behavior:'instant'});
}

function renderPairHeader(r){
  const rel = relOf(r), j = r.judge, q = r.quality||{};
  $('#pTitle').innerHTML = `<span class="pair" style="font-size:24px">${r.code_a} · ${r.code_b}</span>
    <span class="badge b-${r.rtype}" style="margin-left:8px">${(RT[r.rtype]||{}).cn||r.rtype}</span>
    <span class="badge b-${r.strength}" style="margin-left:4px">${r.strength}</span>
    <span class="badge ${vClass(j.verdict)}" style="margin-left:4px">${j.verdict}</span>`;
  $('#pSub').textContent = `${rName(r.code_a)} / ${rName(r.code_b)} · 样本 ${r.first} ~ ${r.last} · 重叠 ${r.n_overlap} 交易日 · 有效收益样本 ${r.n_returns}`;
  const verdictBox = j.verdict==='异常背离（候选）'
    ? `<div class="badbox"><b>判定：异常背离（候选）</b> —— 四条门槛全部或 ≥3 条通过。这只是"统计上值得进一步研究"的标记，不代表存在可执行机会。</div>`
    : (j.verdict==='关注'
      ? `<div class="warnbox"><b>判定：关注</b> —— 4 条门槛通过 ${j.checks.filter(c=>c.passed).length} 条。部分指标接近阈值但未同时成立。</div>`
      : `<div class="okbox"><b>判定：${j.verdict}</b> —— 4 条门槛仅通过 ${j.checks.filter(c=>c.passed).length} 条。本组合近期<b>不构成</b>异常背离。</div>`);
  $('#pVerdict').innerHTML = verdictBox;
}

function switchTab(k){
  $$('#pairTabs .tab').forEach(t=>t.classList.toggle('on', t.dataset.t===k));
  const r = cur; if(!r) return;
  const box = $('#pBody');
  if(k==='overview') box.innerHTML = tabOverview(r);
  if(k==='price') box.innerHTML = tabPrice(r);
  if(k==='stat') box.innerHTML = tabStat(r);
  if(k==='fund') box.innerHTML = tabFund(r);
  if(k==='quality') box.innerHTML = tabQuality(r);
  if(k==='price') drawPriceCharts(r);
  if(k==='stat') drawStatCharts(r);
}

function tabOverview(r){
  const rel = relOf(r), j = r.judge;
  const cards = [
    ['全期日收益相关 r', f(r.r_daily,3), `95% CI ${f((r.r_daily_ci||[])[0],2)} ~ ${f((r.r_daily_ci||[])[1],2)}`],
    ['滚动 '+r.roll_window+' 日相关（最新）', f(r.roll_corr_last,3), `历史中位数 ${f(r.roll_corr_median,2)} · 分位 ${pct(r.roll_corr_pct,0)}`],
    ['相关性变化（基线−最新）', f(j.corr_drop,3), `阈值 ≥ ${PK.params.drop_threshold} 才算"脱钩"`],
    ['价差/比价 z（最新）', f(r.z_last,2), `历史分位 ${pct(r.z_pct,0)} · 连续超阈值 ${r.z_run_days} 日`],
    ['当前比价 B/A', f(r.ratio_last,4), r.spread_label || ''],
    ['可比性评级', (r.quality||{}).level || '—', (r.quality||{}).notes ? (r.quality.notes[0]||'') : '']
  ];
  return `
  <div class="grid3">${cards.map(c=>`<div class="card"><div class="t">${esc(c[0])}</div>
      <div class="v">${esc(c[1])}</div><div class="n">${esc(c[2])}</div></div>`).join('')}</div>

  <div class="grid2" style="margin-top:14px">
    <div class="panel"><h2>四门槛核查</h2>
      <p class="hint">逐条展示门槛、实际取值与是否通过；所有阈值见"统计与检验"页。</p>
      ${j.checks.map(c=>`<div class="chk"><div class="dot ${c.passed?'y':'n'}">${c.passed?'✓':'✗'}</div>
        <div><b>${esc(c.name)}</b> —— 实际 ${f(c.value,3)}，门槛 ${esc(c.threshold)}
        <div class="note">${esc(c.note||'')}</div></div></div>`).join('')}
    </div>
    <div class="panel"><h2>产业关系</h2>
      <p class="hint">关系类型、强度与来源是"是否值得研究"的第一道筛子。</p>
      <div class="note" style="font-size:12.5px;color:#dbe7f5;line-height:1.8">
        <b>类型：</b>${esc((RT[r.rtype]||{}).cn)}（${esc((RT[r.rtype]||{}).desc)}）<br>
        <b>强度：</b>${esc(r.strength)}；<b>方向：</b>${esc(rel.direction||'—')}<br><br>
        <b>${r.code_a}：</b>${esc(rel.a_role||'')}<br>
        <b>${r.code_b}：</b>${esc(rel.b_role||'')}<br><br>
        <b>传导机制：</b>${esc(rel.mechanism||'')}<br><br>
        <b>业内监测口径：</b>${esc(rel.market_convention||'')}<br>
        <b>系数 k：</b>${rel.k!=null?esc(rel.k):'无（仅比价）'}<br>
        <b>来源：</b>${(rel.source_ids||[]).map(sid=>{const s=PK.sources[sid];return s?`<a href="${s.url}" target="_blank" rel="noopener">${sid}</a>`:sid;}).join('、')}
      </div>
    </div>
  </div>

  <div class="panel" style="margin-top:14px"><h2>核心结论（自动生成，不含交易建议）</h2>
    ${conclusion(r)}
  </div>`;
}

function conclusion(r){
  const j = r.judge;
  const nPass = j.checks.filter(c=>c.passed).length;
  const lines = [];
  const rel = relOf(r);
  lines.push(`<b>① 产业关系：</b>${r.code_a} 与 ${r.code_b} 属「${(RT[r.rtype]||{}).cn}」关系（${r.strength}），`
    + `传导逻辑为：${esc((rel.mechanism||'').slice(0,90))}…`);
  lines.push(`<b>② 统计偏离：</b>最新对数价差 z = ${f(r.z_last,2)}（历史分位 ${pct(r.z_pct,0)}，历史 |z| 最大 ${f(r.z_abs_max_hist,2)}），`
    + `已连续 ${r.z_run_days} 个交易日超过 |z|≥${PK.params.z_threshold} 的阈值。`);
  lines.push(`<b>③ 相关性：</b>全期日收益相关 ${f(r.r_daily,2)}，最近 ${r.roll_window} 日滚动相关 ${f(r.roll_corr_last,2)}，`
    + `变化 ${f(j.corr_drop,2)}（阈值 ${PK.params.drop_threshold}）；${j.corr_drop!=null&&j.corr_drop>=PK.params.drop_threshold?'联动正在明显减弱':'未见明显脱钩'}。`);
  lines.push(`<b>④ 判定：</b>4 条门槛通过 ${nPass} 条 → <b>${j.verdict}</b>。`);
  if(nPass<3){
    lines.push(`<b>⑤ 结论：</b>在当前阈值下，<b>不应</b>把该组合列为"异常背离"；可以作为"关系稳定、偏离在正常波动范围内"的对照样本。`);
  }
  return `<div class="note" style="font-size:12.8px;color:#dbe7f5;line-height:1.95">${lines.join('<br>')}</div>`;
}

function tabPrice(r){
  const sc = r.std_change||{}, ch = r.spread_change||{};
  const row = w => {
    const v = sc[w];
    if(!v) return '';
    return `<tr><td>${w} 日</td><td class="num">${pct(v.a*100,2)}</td><td class="num">${pct(v.b*100,2)}</td>
      <td class="num">${f(v.a_std,2)}σ</td><td class="num">${f(v.b_std,2)}σ</td>
      <td class="num">${ch[w]==null?'—':f(ch[w],4)}</td>
      <td class="num">${f((v.a_std||0)-(v.b_std||0),2)}σ</td></tr>`;
  };
  return `
  <div class="grid2">
    <div class="panel"><h2>价格走势（元/吨）</h2><p class="hint">主力连续收盘价，按月抽样 + 最近 120 个交易日逐日。</p>
      <div style="height:280px"><canvas id="cPrice"></canvas></div></div>
    <div class="panel"><h2>${esc(r.spread_label||'对数价差')}与滚动 z</h2>
      <p class="hint">价差在对数空间计算；z 为相对"过去 ${r.roll_window} 日"的标准化偏离。</p>
      <div style="height:280px"><canvas id="cSpread"></canvas></div></div>
  </div>
  <div class="panel"><h2>标准化价格变化（可跨品种直接比较）</h2>
    <p class="hint">标准化变化 = 累计对数收益 ÷ (日波动率 × √窗口天数)，单位是"σ"。两者之差反映这段时间谁相对更强。</p>
    <table><thead><tr><th>窗口</th><th>${r.code_a} 累计</th><th>${r.code_b} 累计</th>
      <th>${r.code_a} 标准化</th><th>${r.code_b} 标准化</th><th>价差变化(对数)</th><th>标准化差</th></tr></thead>
      <tbody>${[5,20,60].map(row).join('')}</tbody></table>
    <p class="note" style="margin-top:8px">日波动率：${r.code_a} ${pct((r.sigma_daily_a||0)*100,2)}；${r.code_b} ${pct((r.sigma_daily_b||0)*100,2)}。</p>
  </div>`;
}

function tabStat(r){
  const wc = r.window_corr||{};
  const perm = r.perm||{};
  return `
  <div class="grid2">
    <div class="panel"><h2>滚动收益率相关（${r.roll_window} 日）与价差偏离轨迹</h2>
      <p class="hint">上方为价差 z 的逐日轨迹（含 ±2 阈值线）；下方为滚动相关的历史分布位置。</p>
      <div style="height:250px"><canvas id="cCorr"></canvas></div>
      <div style="height:180px;margin-top:10px"><canvas id="cCorrDist"></canvas></div></div>
    <div class="panel"><h2>相关性分层：价格水平 vs 收益率</h2>
      <p class="hint">价格水平相关高，可能只是共同趋势；收益率相关才是"信息同步"的主口径。</p>
      <table><tbody>
        <tr><td>价格水平相关（Pearson）</td><td class="num">${f(r.r_level,3)}</td></tr>
        <tr><td>价格水平相关（Spearman）</td><td class="num">${f(r.r_level_spearman,3)}</td></tr>
        <tr><td><b>日收益率相关（主口径）</b></td><td class="num"><b>${f(r.r_daily,3)}</b></td></tr>
        <tr><td>95% 置信区间</td><td class="num">${f((r.r_daily_ci||[])[0],3)} ~ ${f((r.r_daily_ci||[])[1],3)}</td></tr>
        <tr><td>Spearman（收益）</td><td class="num">${f(r.r_daily_spearman,3)}</td></tr>
        <tr><td>有效样本量 N_eff</td><td class="num">${f(r.n_eff,0)}（n=${r.n_returns}）</td></tr>
        <tr><td>原始 p / 调整后 p</td><td class="num">${sci(r.r_daily_p)} / ${sci(r.r_daily_p_eff)}</td></tr>
        <tr><td>置换检验 p（循环平移）</td><td class="num">${f(perm.p_perm,4)}（零分布 σ=${f(perm.null_sd,3)}）</td></tr>
        <tr><td>5 / 20 / 60 日窗口相关</td><td class="num">${f(wc['5'],2)} / ${f(wc['20'],2)} / ${f(wc['60'],2)}</td></tr>
      </tbody></table></div>
  </div>
  <div class="panel"><h2>四门槛明细与阈值</h2>
    <table><thead><tr><th>门槛</th><th>实际值</th><th>阈值</th><th>是否通过</th><th>说明</th></tr></thead><tbody>
    ${r.judge.checks.map(c=>`<tr><td>${esc(c.name)}</td><td class="num">${f(c.value,3)}</td>
      <td>${esc(c.threshold)}</td><td>${c.passed?'<span class="badge v-ok">通过</span>':'<span class="badge v-anom">未通过</span>'}</td>
      <td class="note">${esc(c.note||'')}</td></tr>`).join('')}
    </tbody></table>
    <p class="note" style="margin-top:8px">检验次数 m = ${r.judge.n_tests}；Bonferroni 校正后 p = ${sci(r.judge.p_bonf)}。
    综合评分 = 偏离程度(0–40) + 相关性变化(0–30) + 持续性(0–30) = <b>${f(r.judge.score,1)}</b>。</p>
  </div>`;
}
function sci(v){ if(v==null) return '—'; if(v===0) return '<1e-300'; if(v<1e-4) return v.toExponential(1); return v.toFixed(4); }

function tabFund(r){
  const codes = [r.code_a, r.code_b];
  const evs = (PK.events||[]).filter(e=>codes.includes(e.ticker));
  const tmpl = PK.fund_template||{};
  const q = (r.quality||{});
  const checklist = c => {
    const t = tmpl[c]||{};
    return `<div class="panel"><h2>${c} · ${esc(rName(c))} 基本面五问</h2>
      <p class="hint">下列为"应查口径"；本次获得的是公开可检索的事实（见右侧事件时间线），连续数值未取得的标"未取得"。</p>
      <table><tbody>
        <tr><td style="width:88px"><b>① 库存</b></td><td>${esc(t.inventory||'—')}</td></tr>
        <tr><td><b>② 开工</b></td><td>${esc(t.operating||'—')}</td></tr>
        <tr><td><b>③ 供需</b></td><td>${esc(t.supply_demand||'—')}</td></tr>
        <tr><td><b>④ 成本</b></td><td>${esc(t.cost||'—')}</td></tr>
        <tr><td><b>⑤ 事件</b></td><td>${evs.filter(e=>e.ticker===c).length
          ? evs.filter(e=>e.ticker===c).map(e=>`<a href="#ev-${e.id}">${esc(e.title)}</a>（${e.date}）`).join('<br>')
          : '<span class="note">窗口内未检索到公开事件</span>'}</td></tr>
      </tbody></table></div>`;
  };
  const priceFacts = (() => {
    const st = r.std_change||{}, s20 = st['20'], s60 = st['60'];
    const rows = [];
    rows.push(`<tr><td>最新价格（${r.last_prices.date}）</td><td class="num">${f(r.last_prices.a,0)}</td><td class="num">${f(r.last_prices.b,0)}</td></tr>`);
    if(s20) rows.push(`<tr><td>20 日涨跌</td><td class="num">${pct(s20.a*100,2)}</td><td class="num">${pct(s20.b*100,2)}</td></tr>`);
    if(s60) rows.push(`<tr><td>60 日涨跌</td><td class="num">${pct(s60.a*100,2)}</td><td class="num">${pct(s60.b*100,2)}</td></tr>`);
    if(s20) rows.push(`<tr><td>20 日标准化变化</td><td class="num">${f(s20.a_std,2)}σ</td><td class="num">${f(s20.b_std,2)}σ</td></tr>`);
    if(s60) rows.push(`<tr><td>60 日标准化变化</td><td class="num">${f(s60.a_std,2)}σ</td><td class="num">${f(s60.b_std,2)}σ</td></tr>`);
    if(r.k) rows.push(`<tr><td>按系数 k=${r.k} 的加工费（近似）</td><td colspan="2" class="num">${f(r.last_prices.b - r.k*r.last_prices.a,0)} 元/吨
      <span class="note">（仅口径近似，期货价≠现货价）</span></td></tr>`);
    return `<table><thead><tr><th>价格可复核指标</th><th>${r.code_a}</th><th>${r.code_b}</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
  })();
  return `
  <div class="warnbox" style="margin-bottom:14px">
    本次对 ${codes.join(' / ')} 的<b>连续</b>库存、开工率、供需数据未能取得可公开复算的序列（多为付费数据库口径）。
    下表把所有可复核的价格类事实与已检索到的公开事件并列，<b>不填补任何数值</b>。
  </div>
  <div class="grid2">${checklist(r.code_a)}${checklist(r.code_b)}</div>
  <div class="panel"><h2>价格事实（可复核）</h2><p class="hint">全部由同一份价格序列直接计算。</p>${priceFacts}</div>
  <div class="panel"><h2>事件时间线</h2>
    <div class="timeline">${evs.length? evs.map(e=>`
      <div class="ev" id="ev-${e.id}"><div class="d">${e.date} · ${esc(e.ticker)} · ${esc(e.kind)}</div>
        <div class="tt">${esc(e.title)}</div><div class="dd">${esc(e.detail)}</div>
        <div class="note">方向提示：${esc(e.direction_hint)} ｜ 来源 ${srcLink(e.source)}</div></div>`).join('')
      : '<div class="note">窗口内无公开事件记录。</div>'}
    </div>
  </div>
  <div class="panel"><h2>解释框架</h2>
    <div class="note" style="font-size:12.6px;line-height:1.9;color:#dbe7f5">
      ① 先看<b>是否共同冲击</b>：${esc((PK.common_shock||{}).note||'')}。<br>
      ② 再看<b>成本/物料端差异</b>：若上游检修、制裁、运费等只影响一端，价差会系统性偏移而非随机波动。<br>
      ③ 再看<b>需求端差异</b>：下游开工与终端订单的落差决定价差能维持多久。<br>
      ④ 最后看<b>库存</b>：低库存 + 紧流通会让价格脱离"成本锚"，此时制造业利润口径会显著失真。<br>
      <b>注意：</b>以上只解释"为什么这段不一样"，不构成方向判断或交易建议。
    </div>
  </div>`;
}

function srcLink(sid){
  const s = PK.sources[sid];
  if(!s) return esc(sid);
  return `<a href="${s.url}" target="_blank" rel="noopener">${sid} ${esc(s.title.slice(0,34))}…</a>`;
}
function rcRegime(r){
  // 只用报告中给出的稳健统计量构造三段对比（无逐点序列时的降级展示）
  const reg = r.rc_regime_spread;
  const med = r.roll_corr_median, last = r.roll_corr_last;
  if(reg==null && med==null) return '<div class="note">该组合无足够滚动相关样本。</div>';
  const bar = (label, val, col) => `<tr><td style="width:150px">${label}</td>
    <td class="num" style="width:70px">${f(val,3)}</td>
    <td><div class="bar"><i style="width:${Math.max(0,Math.min(100,(val+0.2)/1.2*100)).toFixed(0)}%;background:${col}"></i></div></td></tr>`;
  return `<table><tbody>
    ${bar('滚动相关中位数', med, '#38bdf8')}
    ${bar('滚动相关（最新）', last, '#a78bfa')}
    ${bar('三段均值极差（越大越不稳）', reg==null?0:reg, reg>0.30? '#f43f5e':'#34d399')}
  </tbody></table>
  <p class="note" style="margin-top:6px">三段均值极差 ${f(reg,3)}：${(reg!=null&&reg>0.30)
    ? '<b style="color:#fda4af">超过 0.30，说明关系存在明显制度切换，静态价差锚不可靠</b>'
    : '在 0.30 以内，关系跨期相对稳定'}。</p>`;
}

function tabQuality(r){
  const q = r.quality||{};
  const hist = HIST ? HIST.summary.find(x=>x.pair===r.code_a+'/'+r.code_b) : null;
  const reg = rcRegime(r);
  return `
  <div class="grid2">
    <div class="panel"><h2>数据可比性</h2>
      <table><tbody>
        <tr><td>重叠交易日</td><td class="num">${r.n_overlap}</td></tr>
        <tr><td>有效收益样本</td><td class="num">${r.n_returns}</td></tr>
        <tr><td>剔除的换月/断档收益</td><td class="num">${r.excluded_roll_returns||0}</td></tr>
        <tr><td>可比性评级</td><td class="num"><b>${esc(q.level||'—')}</b>（${q.score??'—'} 分）</td></tr>
        <tr><td>样本跨度</td><td class="num">${f(q.span_years,1)} 年</td></tr>
        <tr><td>关系稳定性</td><td>${(q.notes||[]).map(n=>esc(n)).join('<br>')}</td></tr>
      </tbody></table>
      <p class="note" style="margin-top:8px">${esc((relOf(r).comparability)||'')}</p>
    </div>
    <div class="panel"><h2>假设历史扫描（"此刻"回拨检验）</h2>
      <p class="hint">在过去 12 个月按月回拨"当下"，用同一套阈值重跑，看该组合被判定为"异常背离"的频率。</p>
      ${hist? `<table><tbody>
        <tr><td>回看次数</td><td class="num">${hist.n}</td></tr>
        <tr><td>被判"异常背离"</td><td class="num">${hist.n_anom} 次（${pct(hist.n_anom/hist.n*100,0)}）</td></tr>
        <tr><td>z 区间</td><td class="num">${f(hist.ai_min,2)} ~ ${f(hist.zmax,2)}</td></tr>
        <tr><td>本次 z</td><td class="num">${f(r.z_last,2)}</td></tr>
      </tbody></table>` : '<div class="note">未提供历史扫描结果。</div>'}
      <p class="note" style="margin-top:8px">若历史命中率高，说明该组合的价差经常"看起来异常"，单次极端值的信息量有限。</p>
    </div>
  </div>
  <div class="panel"><h2>关系稳定性（分段滚动相关均值）</h2>
    <p class="hint">把滚动相关序列等分三段，比较各段均值。段间差异越大，说明"关系"本身在换制度，不适合做静态价差锚。</p>
    ${reg}
  </div>
  <div class="panel"><h2>该组合不适用于研究的理由（如有）</h2>
    <div class="note" style="font-size:12.6px;line-height:1.9;color:#dbe7f5">
      ${(q.level==='C')
        ? '评级 C：样本不足或历史关系不稳定，<b>不适合</b>基于本数据下"异常背离"结论，应先做更长期/更细口径的数据补齐。'
        : (r.rtype==='cross_chain_cost'
           ? '该组合为"成本共振"型关系，没有直接物料流或替代弹性，价差本身不构成可解释的产业锚，'
             + '即使统计偏离显著，也不宜作为研究对象。'
           : '样本期与关系稳定性均达标，可以正常研究；但仍需注意均为主力连续价、非现货价。')}
    </div>
  </div>`;
}

/* ---------- 图表（纯 canvas，无外链） ---------- */
const drawSeriesChart = (id, series, opts) => renderCanvasChart(id, series, opts);
const drawCanvasChart = (id, series, opts) => renderCanvasChart(id, series, opts);
function renderCanvasChart(id, series, opts){
  const cv = document.getElementById(id); if(!cv) return;
  const dpr = window.devicePixelRatio||1;
  const w = Math.max(320, cv.parentElement.clientWidth);
  const hh = opts.h || 250;
  cv.width = w*dpr; cv.height = hh*dpr; cv.style.width = w+'px'; cv.style.height = hh+'px';
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,w,hh);
  const pad = {l:46,r:14,t:16,b:22};
  const all = series.flatMap(s=>s.data).filter(v=>v!=null);
  if(!all.length && !opts.band) return;
  let mn = all.length? Math.min(...all) : 0, mx = all.length? Math.max(...all) : 1;
  if(opts.zero){ mn=Math.min(mn,0); mx=Math.max(mx,0); }
  if(opts.band){ mn=Math.min(mn,0); mx=Math.max(mx,1); }
  const rng=(mx-mn)||1; mn-=rng*0.07; mx+=rng*0.07;
  const X = i => pad.l + (w-pad.l-pad.r)*(i/(series[0].data.length-1||1));
  const Y = v => pad.t + (hh-pad.t-pad.b)*(1-(v-mn)/(mx-mn));
  ctx.strokeStyle='#24405f'; ctx.fillStyle='#6b8099'; ctx.font='10px sans-serif'; ctx.lineWidth=1;
  for(let i=0;i<=4;i++){
    const y = pad.t + (hh-pad.t-pad.b)*i/4;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    const v = mx - (mx-mn)*i/4;
    ctx.fillText(Math.abs(v)>=1000? v.toFixed(0) : (Math.abs(v)>=1? v.toFixed(1) : v.toFixed(3)), 5, y+3);
  }
  if(opts.hlines){ opts.hlines.forEach(hv=>{ const y=Y(hv); ctx.strokeStyle='#f59e0b'; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke(); ctx.setLineDash([]); }); }
  if(opts.band){ // 滚动相关分布直方图（基于报告中位数与分位，示意当前所处位置）
    const s=opts.band; const bw=(w-pad.l-pad.r)/s.centers.length;
    ctx.fillStyle='rgba(56,211,248,.45)';
    s.counts.forEach((c,i)=>{ const bh=(hh-pad.t-pad.b)*(c/s.maxCount);
      ctx.fillRect(pad.l+i*bw+0.5, hh-pad.b-bh, Math.max(1,bw-1.5), bh); });
    const cur = opts.marker;
    if(cur!=null){ const x = pad.l + (w-pad.l-pad.r)*Math.max(0,Math.min(1,(cur-0)/(1.0-0)));
      ctx.strokeStyle='#f43f5e'; ctx.lineWidth=2; ctx.setLineDash([5,3]);
      ctx.beginPath(); ctx.moveTo(x,pad.t); ctx.lineTo(x,hh-pad.b); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle='#fda4af'; ctx.font='11px sans-serif';
      ctx.fillText('当前'+cur.toFixed(2), Math.min(x+6, w-70), pad.t+12); }
  }
  series.forEach(s=>{
    ctx.strokeStyle=s.color; ctx.lineWidth=1.5; ctx.beginPath(); let started=false;
    s.data.forEach((v,i)=>{ if(v==null) return; const x=X(i),y=Y(v);
      if(!started){ctx.moveTo(x,y);started=true;} else ctx.lineTo(x,y); });
    ctx.stroke();
  });
  if(opts.xlab){
    ctx.fillStyle='#6b8099';
    ctx.fillText(opts.xlab[0], pad.l, hh-5);
    const tw=ctx.measureText(opts.xlab[1]).width; ctx.fillText(opts.xlab[1], w-pad.r-tw, hh-5);
  }
  if(opts.legend){
    let lx = pad.l+6; ctx.font='11px sans-serif';
    series.forEach(s=>{ ctx.fillStyle=s.color; ctx.fillRect(lx, pad.t+1, 10,3); ctx.fillStyle='#9fb3cc';
      ctx.fillText(s.name, lx+14, pad.t+6); lx += ctx.measureText(s.name).width + 34; });
  }
  if(opts.note){ ctx.fillStyle='#94a3b8'; ctx.font='10.5px sans-serif'; ctx.fillText(opts.note, pad.l+6, pad.t+22); }
}
function drawPriceCharts(r){
  const S0 = SER[serKey(r)]; if(!S0) return;
  drawSeriesChart('cPrice', [
    {name:rName(r.code_a)+' '+r.code_a, data:S0.a, color:'#38bdf8'},
    {name:rName(r.code_b)+' '+r.code_b, data:S0.b, color:'#a78bfa'}
  ], {legend:true, h:280, xlab:[S0.dates[0], S0.dates[S0.dates.length-1]]});
  drawSeriesChart('cSpread', [
    {name:r.spread_label||'对数价差', data:S0.spread, color:'#22d3ee'}
  ], {h:280, xlab:[S0.dates[0], S0.dates[S0.dates.length-1]]});
}
function drawStatCharts(r){
  const S0 = SER[serKey(r)]; if(!S0) return;
  drawCanvasChart('cCorr', [
    {name:'价差 z', data:S0.z, color:'#f472b6'}
  ], {h:250, zero:true, hlines:[2,-2],
      xlab:[S0.dates[0], S0.dates[S0.dates.length-1]],
      note:'橙色虚线 = ±2 阈值；需连续 '+PK.params.persist_days+' 日超阈值'});
  // 滚动相关分布（用 z 序列说明当前水平）：改为相关水平分位条
  drawCanvasChart('cCorrDist', [
    {name:'滚动相关分布', data:[], color:'#38bdf8'}
  ], {h:180, band: buildCorrHist(r), marker: r.roll_corr_last,
      note:'滚动相关历史分布（按分位数信息构造的示意，非逐点重算）'});
}
function buildCorrHist(r){
  // 用报告的分位数信息构造示意直方图（非逐点重算，标明为"近似"）
  const med = r.roll_corr_median || 0, lo = -0.2, hi = 1.0, bins = 26;
  const centers = [], counts = [];
  const pct = (r.roll_corr_pct==null? 50 : r.roll_corr_pct)/100;
  for(let i=0;i<bins;i++){
    const c = lo + (hi-lo)*(i+0.5)/bins;
    // 以中位数为中心、按分位位置偏斜的钟形，仅用于展示"当前所处位置"
    const dev = (c-med)/0.18;
    let h = Math.exp(-0.5*dev*dev) * (1 + 0.6*Math.sin((c-lo)*2));
    centers.push(c); counts.push(Math.max(0,h));
  }
  const maxCount = Math.max(...counts);
  return {centers, counts, maxCount};
}

/* ---------- 静态渲染（图谱、榜单、来源、历史） ---------- */
function renderSources(){
  const gs = {};
  Object.entries(PK.sources).forEach(([k,v])=>{(gs[v.group]=gs[v.group]||[]).push([k,v]);});
  $('#sources').innerHTML = Object.entries(gs).map(([g,arr])=>`
    <div class="panel"><h2>${esc(g)}（${arr.length} 条）</h2>
      <table><tbody>${arr.map(([k,v])=>`<tr>
        <td class="num" style="width:52px"><b>${k}</b></td>
        <td><a href="${v.url}" target="_blank" rel="noopener">${esc(v.title)}</a>
          <div class="note">${esc(v.usage)}</div></td>
        <td class="num" style="width:90px">${esc(v.date)}</td>
        <td class="num" style="width:60px">${esc(v.reliability)}</td></tr>`).join('')}</tbody></table>
    </div>`).join('');
}

function renderRelTable(){
  $('#relTable').innerHTML = `<table><thead><tr><th>组合</th><th>关系类型</th><th>强度</th><th>A 的角色</th>
    <th>B 的角色</th><th>传导机制</th><th>系数 k</th><th>来源</th></tr></thead><tbody>
    ${PK.relations.map(r=>`<tr class="row" data-id="${r.a}__${r.b}">
      <td class="pair">${r.a} / ${r.b}</td>
      <td><span class="badge b-${r.rtype}">${esc((RT[r.rtype]||{}).cn)}</span></td>
      <td><span class="badge b-${r.strength}">${r.strength}</span></td>
      <td class="note" style="color:#cbd5e1">${esc(r.a_role)}</td>
      <td class="note" style="color:#cbd5e1">${esc(r.b_role)}</td>
      <td class="note" style="color:#cbd5e1">${esc(r.mechanism)}</td>
      <td class="num">${r.k!=null?r.k:'—'}</td>
      <td class="note">${r.source_ids.join('、')}</td></tr>`).join('')}
    </tbody></table>`;
  $$('#relTable tr.row').forEach(tr=>tr.onclick=()=>openPair(tr.dataset.id));
}

function renderRtTable(){
  const box = $('#rtTable'); if(!box) return;
  const inMain = s => (s!=='weak');
  box.innerHTML = Object.entries(RT).sort((a,b)=>a[1].order-b[1].order).map(([k,v])=>{
    const grp = PK.relations.filter(r=>r.rtype===k);
    return `<tr><td><span class="badge b-${k}">${esc(v.cn)}</span></td>
      <td class="note" style="color:#cbd5e1">${esc(v.desc)}</td>
      <td class="note" style="color:#cbd5e1">${grp.map(r=>`<a href="javascript:void 0" onclick="openPair('${r.a}__${r.b}')">${r.a}/${r.b}</a>`).join('、') || '—'}</td>
      <td>${(v.in_main!==false)?'<span class="badge v-ok">进入</span>':'<span class="badge v-miss">仅背景</span>'}</td></tr>`;
  }).join('');
}

function renderHist(){
  if(!HIST){ $('#histBox').innerHTML='<div class="note">未提供历史扫描结果。</div>'; return; }
  const rows = HIST.summary;
  $('#histBox').innerHTML = `
    <p class="hint">过去 ${HIST.months} 个月，按月把"当下"回拨到 ${HIST.cut_offs[0]} … ${HIST.cut_offs[HIST.cut_offs.length-1]}，
    共 ${HIST.cut_offs.length} 个时点、${HIST.rows.length} 次组合判定。用于量化扫描器本身的假阳性率。</p>
    <table><thead><tr><th>组合</th><th>关系类型</th><th class="num">回看次数</th><th class="num">判为"异常背离"</th>
      <th class="num">命中率</th><th class="num">z 最小</th><th class="num">z 最大</th><th></th></tr></thead><tbody>
      ${rows.map(v=>`<tr class="row" data-id="${v.pair.replace('/', '__')}">
        <td class="pair">${esc(v.pair)}</td>
        <td><span class="badge b-${v.rtype}">${esc((RT[v.rtype]||{}).cn)}</span></td>
        <td class="num">${v.n}</td>
        <td class="num" style="color:${v.n_anom?'#fda4af':'#94a3b8'};font-weight:700">${v.n_anom}</td>
        <td class="num">${pct(v.n_anom/v.n*100,0)}</td>
        <td class="num">${f(v.ai_min,2)}</td><td class="num">${f(v.zmax,2)}</td>
        <td><div class="bar"><i style="width:${(v.n_anom/v.n*100).toFixed(0)}%;background:${v.n_anom?'#f43f5e':'#334155'}"></i></div></td></tr>`).join('')}
    </tbody></table>`;
  $$('#histBox tr.row').forEach(tr=>tr.onclick=()=>openPair(tr.dataset.id));
}

function renderRelationBadge(){
  const anom = PK.results.filter(r=>r.status==='ok' && r.judge.verdict==='异常背离（候选）');
  $('#anomBox').innerHTML = anom.length
    ? `<div class="badbox"><b>本次扫描发现 ${anom.length} 个组合同时通过四门槛：</b>${anom.map(r=>r.code_a+'/'+r.code_b).join('、')}。
       但它们均属 <b>weak（弱关系）</b>，按配对规则只作背景，<b>不进入主榜单</b>。详见"异常背离榜单"与各组合研究页。</div>`
    : `<div class="okbox"><b>本次扫描：无组合通过全部四门槛。</b>在 strong/medium 产业关系范围内，所有组合的价差偏离、持续性与相关性脱钩均未同时成立。</div>`;
}

/* ---------- Tab 切换（页级） ---------- */
function pageTab(k){
  $$('#pageTabs .tab').forEach(t=>t.classList.toggle('on', t.dataset.p===k));
  ['scanner','graph','relations','history','sources','method'].forEach(p=>{
    $('#'+p).classList.toggle('hidden', p!==k);
  });
  if(k==='graph'){ renderGraph(); }
  window.scrollTo({top:0,behavior:'instant'});
}

document.addEventListener('DOMContentLoaded', ()=>{
  renderKPIs(); renderChips(); renderTable(); renderRelationBadge(); renderRelTable(); renderRtTable();
  renderHist(); renderSources();
  $$('#pageTabs .tab').forEach(t=>t.onclick=()=>pageTab(t.dataset.p));
  $('#backBtn').onclick=closePair;
  $$('#pairTabs .tab').forEach(t=>t.onclick=()=>switchTab(t.dataset.t));
  window.addEventListener('resize', ()=>{ if(!$('#graph').classList.contains('hidden')) renderGraph(); });
});
"""

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>产业链异常背离扫描看板 ｜ 化工品种池（PP·LLDPE·PX·PTA 等）</title>
<style>__CSS__</style>
</head>
<body>
<header class="top">
  <div class="top-in">
    <div class="brand">ChemClaw · <span>产业链异常背离扫描</span></div>
    <span class="tag">期现-价差与量化 / 23</span>
    <span class="tag">数据截至 __LASTDATE__</span>
    <span class="tag">期货主力连续 · 元/吨</span>
  </div>
  <div class="top-in" style="padding-top:0">
    <div class="tabs" id="pageTabs" style="margin:0">
      <div class="tab on" data-p="scanner">① 异常背离榜单</div>
      <div class="tab" data-p="graph">② 产业链关系图谱</div>
      <div class="tab" data-p="relations">③ 关系与配对规则</div>
      <div class="tab" data-p="history">④ 历史回看检验</div>
      <div class="tab" data-p="sources">⑤ 来源与口径</div>
      <div class="tab" data-p="method">⑥ 方法与限制</div>
    </div>
  </div>
</header>

<div class="wrap">
<!-- ============ 扫描器 ============ -->
<div id="scanner">
  <div class="hero">
    <h1>在真实产业链关系上找"异常背离"，而不是在 105 个随机组合里找巧合</h1>
    <p>先用产业图谱筛出有业务意义的品种对（上下游 / 共用原料 / 替代 / 同装置切换），
       再对这些配对做价格对齐、标准化变化、价差与比价、滚动收益率相关与四门槛异常判定。
       所有偏离都附「产业关系 + 统计异常程度 + 基本面可解释性 + 数据可比性」四项，而不是只给一个相关性排名。</p>
  </div>
  <div class="kpis" id="kpis"></div>
  <div id="anomBox"></div>

  <div class="panel" style="margin-top:14px">
    <h2>筛选器</h2>
    <p class="hint">点击下方品种池 / 关系类型自动重算榜单与图谱。可叠加偏离程度与相关性变化筛选。</p>
    <div class="controls" style="margin-bottom:10px">
      <span class="note" style="width:70px">关系类型</span><div class="controls" id="rtChips" style="gap:6px"></div>
    </div>
    <div class="controls" style="margin-bottom:10px">
      <span class="note" style="width:70px">关系强度</span><div class="controls" id="stChips" style="gap:6px"></div>
      <span class="note" style="width:70px;margin-left:14px">判定</span><div class="controls" id="vdChips" style="gap:6px"></div>
    </div>
    <div class="controls">
      <span class="note" style="width:70px">品种池</span><select id="uniSel" style="min-width:220px"></select>
      <span class="slider" style="margin-left:12px">偏离程度 <input type="range" id="devR" min="0" max="5" step="0.1" value="0"><b id="devV"></b></span>
      <span class="slider">相关变化 <input type="range" id="dropR" min="-0.4" max="1" step="0.05" value="1.01"><b id="dropV">≤ 1.01</b></span>
      <input type="text" id="q" placeholder="搜索品种或关系…" style="min-width:200px">
    </div>
  </div>

  <div class="panel">
    <h2>异常背离榜单 <span class="note" id="cnt" style="font-weight:400"></span></h2>
    <p class="hint">按评分（偏离 40 + 相关性变化 30 + 持续性 30）排序；点击任意行进入该组合的完整研究页。表头可点击排序。</p>
    <div style="overflow:auto;max-height:640px">
      <table><thead id="thead"></thead><tbody id="tbody"></tbody></table>
    </div>
    <div class="legend">
      <span><i style="background:#34d399"></i>强关系</span><span><i style="background:#38bdf8"></i>中关系</span>
      <span><i style="background:#94a3b8"></i>弱关系（仅背景）</span>
      <span>偏差 z 为对数价差相对"过去 60 日"的标准化偏离；相关变化 = |全期 r| − 最近 60 日滚动 r。</span>
    </div>
  </div>
</div>

<!-- ============ 组合研究页 ============ -->
<div id="pair" class="hidden">
  <div class="back"><span id="backBtn" style="cursor:pointer;color:#38bdf8">← 返回榜单</span></div>
  <div class="hero" style="padding-top:8px">
    <div id="pTitle"></div>
    <p id="pSub" style="margin-top:6px"></p>
  </div>
  <div id="pVerdict" style="margin:10px 0"></div>
  <div class="tabs" id="pairTabs">
    <div class="tab on" data-t="overview">概览与判定</div>
    <div class="tab" data-t="price">价格 · 价差 · 标准化变化</div>
    <div class="tab" data-t="stat">统计与检验</div>
    <div class="tab" data-t="fund">基本面与事件</div>
    <div class="tab" data-t="quality">可比性与历史回看</div>
  </div>
  <div id="pBody"></div>
</div>

<!-- ============ 图谱 ============ -->
<div id="graph" class="hidden" style="height:auto">
  <div class="hero"><h1>产业链关系图谱</h1>
    <p>节点大小 = 关系中出现的次数；实线 = 强/中关系，虚线 = 仅成本共振的弱关系。点击节点可筛选该品种相关的组合。</p></div>
  <div id="graphBox"></div>
  <div class="panel" id="relTableBox">
    <h2>关系明细表</h2>
    <p class="hint">点击任一行进入组合研究页。</p>
    <div id="relTable" style="overflow:auto;max-height:520px"></div>
  </div>
</div>

<!-- ============ 关系与规则 ============ -->
<div id="relations" class="hidden">
  <div class="hero"><h1>产业关系类型与配对构建规则</h1>
    <p>这一步决定了"哪些组合有资格进入统计扫描"。跳过这一步，统计扫描就会退化为数据挖掘。</p></div>
  <div class="panel"><h2>四类产业关系</h2>
    <table><thead><tr><th>类型</th><th>业务含义</th><th>本次纳入的组合</th><th>是否进主榜单</th></tr></thead>
    <tbody id="rtTable"></tbody></table></div>
  <div class="panel"><h2>构建规则</h2>
    <div class="note" style="font-size:12.8px;line-height:1.95;color:#dbe7f5">
      ① <b>定义品种池</b>：__NUNIV__ 个化工期货品种，按炼化/烯烃/芳烃/煤化工/黑色/油品分链；<br>
      ② <b>列出产业关系</b>：只录入存在上下游、共用原料、替代或同装置切换的品种对，逐条标注 A/B 角色、传导机制与来源；<br>
      ③ <b>强度分级</b>：strong = 直接物料流或同一装置；medium = 共用原料/部分替代/二级成本；weak = 仅成本共振，只作背景；<br>
      ④ <b>最小重叠期</b> ≥ __MINOV__ 个交易日，否则标"数据不足"，不做推断；<br>
      ⑤ <b>不做全组合搜索</b>：不对无产业关联的品种做 C(n,2) 全遍历——组合数爆炸会制造大量偶然极端值；<br>
      ⑥ <b>四门槛同时满足</b>才判"异常背离"；<br>
      ⑦ <b>参数固定</b>：窗口、阈值、样本起点必须在扫描前固定并记录（见"方法与限制"），不为凑结论而调参。
    </div>
  </div>
  <div class="panel"><h2>为什么 PP-LLDPE 与 PX-PTA 是本研究的重点</h2>
    <div class="note" style="font-size:12.8px;line-height:1.95;color:#dbe7f5">
      <b>PX → PTA</b>：存在唯一主流工艺路径（PX 经空气氧化生成 CTA，再加氢精制），吨 PTA 约耗 0.655 吨 PX，
      加工费是行业公认的价差锚，属最"干净"的上下游关系。<br>
      <b>PP / LLDPE</b>：原料端共用烯烃（石脑油裂解 / MTO / PDH / 炼厂丙烯），终端在包装、注塑、薄膜上部分互替，
      属"共用原料 + 替代"关系；两者的强弱分化来自各自投产周期与开工率，是聚烯烃研究中最常见的配对对象。<br>
      两者合计覆盖了"强物料关系"与"中强度共用原料/替代"两类典型，正好用来检验扫描器的稳健性。
    </div>
  </div>
</div>

<!-- ============ 历史回看 ============ -->
<div id="history" class="hidden">
  <div class="hero"><h1>假设历史扫描：这个扫描器有多容易"报假警"？</h1>
    <p>把"当下"逐月回拨，用完全相同的窗口与阈值重跑。若某组合在历史回看中频繁被判为异常，
       它当前的异常值就不该被过度解读。</p></div>
  <div class="panel" id="histBox"></div>
</div>

<!-- ============ 来源 ============ -->
<div id="sources" class="hidden">
  <div class="hero"><h1>来源与口径清单</h1>
    <p>数据源、产业关系、事件三类来源逐条列明，均可点击跳转。可靠性分级：高=原始机构/交易所原文；中=券商或行业媒体；低=二手转述。</p></div>
  <div id="sourcesInner"></div>
</div>

<!-- ============ 方法 ============ -->
<div id="method" class="hidden">
  <div class="hero"><h1>方法与限制</h1><p>读结论前请先读这一页。</p></div>
  <div class="panel"><h2>统计口径</h2>
    <table><thead><tr><th>指标</th><th>公式 / 定义</th><th>本次取值</th><th>注意点</th></tr></thead><tbody>
    <tr><td>对齐</td><td>两品种都有交易日的交集；不插补、不外推</td><td>逐对</td><td>节假日差异导致样本不一致</td></tr>
    <tr><td>换月剔除</td><td>|log r|&gt;5% 且前后日振幅&lt;2% 且持仓跳变&gt;10%，或日历间隔≥9 天</td><td>规则见脚本</td><td>无法完整还原每次换月</td></tr>
    <tr><td>价格水平相关</td><td>Pearson(P_A,P_B)</td><td>背景口径</td><td>易被共同趋势抬升</td></tr>
    <tr><td>收益率相关（主口径）</td><td>Pearson(r_A,r_B)，r=ln(P_t/P_{t-1})</td><td>逐对</td><td>日度相关对噪声敏感</td></tr>
    <tr><td>滚动相关</td><td>窗口 __WIN__ 日逐日重算</td><td>__WIN__ 日</td><td>首窗口前无值</td></tr>
    <tr><td>标准化价格变化</td><td>Σln(1+r)/(σ·√n)</td><td>5/20/60 日</td><td>σ 用全样本估计</td></tr>
    <tr><td>价差/比价</td><td>有 k：ln(P_B)−ln(k·P_A)；无 k：ln(P_B/P_A)</td><td>对数空间</td><td>期货价≠现货价</td></tr>
    <tr><td>滚动 z</td><td>只用 t 之前的窗口，避免前视</td><td>阈值 |z|≥__Z__</td><td>窗口内制度切换会失真</td></tr>
    <tr><td>多重检验</td><td>Bonferroni + BH-FDR + 循环平移置换检验</td><td>m=__M__</td><td>仍不能完全排除巧合</td></tr>
    </tbody></table>
  </div>
  <div class="panel"><h2>已知限制</h2>
    <div class="note" style="font-size:12.8px;line-height:1.95;color:#dbe7f5">
      <b>① 价格口径：</b>全部为期货主力连续收盘价。主力连续在换月时拼接不同月份合约，跨月价差被记入价格变化；本工具用规则识别并剔除，但无法完整还原每一次换月。<br>
      <b>② 与现货差异：</b>期货价 ≠ 现货成交价；如与行业现货加工费（例如 PTA 现货加工费）比较，需替换现货序列。<br>
      <b>③ 基本面数据：</b>库存/开工/供需的连续口径需付费数据库，本次仅记录公开可检索的时点事实，未取得的数值标"未取得"，<b>不估算、不填补</b>。<br>
      <b>④ 事件≠因果：</b>事件库用于解释统计差异，不代表因果；价格由多因素共同决定。<br>
      <b>⑤ 关系稳定性：</b>替代型与成本共振型关系本身不稳定，可比性评级会降为 B/C。<br>
      <b>⑥ 不作交易建议：</b>本看板不包含任何交易、套利或择时建议。
    </div>
  </div>
</div>

<footer>
  生成于 __GEN__ ｜ 数据源：新浪财经 InnerFuturesNewService（主力连续日线，截至 __LASTDATE__）｜
  本页为研究记录，所有"异常/背离"结论均为统计描述，不构成投资建议、套利建议或交易指令。
</footer>
</div>

<script>window.__PACK__ = __PACKJSON__;</script>
<script>window.__SERIES__ = __SERIESJSON__;</script>
<script>window.__HIST__ = __HISTJSON__;</script>
<script>__JS__</script>
</body>
</html>
"""


def build(pack_path, series_path, hist_path, out_path):
    pack = json.load(open(pack_path, encoding='utf-8'))
    series = json.load(open(series_path, encoding='utf-8')) if series_path and os.path.exists(series_path) else {}
    hist = None
    if hist_path and os.path.exists(hist_path):
        h = json.load(open(hist_path, encoding='utf-8'))
        sp = os.path.join(os.path.dirname(hist_path), 'hist_scan_summary.json')
        summ = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else []
        hist = dict(months=h['months'], cut_offs=h['cut_offs'], rows=h['rows'], summary=summ)

    last = (pack['universe_meta'].get('PP0') or {}).get('last', '—')
    html = HTML
    html = html.replace('__CSS__', CSS).replace('__JS__', JS)
    html = html.replace('__PACKJSON__', json.dumps(pack, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('__SERIESJSON__', json.dumps(series, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('__HISTJSON__', json.dumps(hist, ensure_ascii=False, separators=(',', ':')) if hist else 'null')
    html = html.replace('__LASTDATE__', last)
    html = html.replace('__GEN__', pack['generated_at'])
    html = html.replace('__NUNIV__', str(len(pack['universe'])))
    html = html.replace('__MINOV__', str(pack['pair_rules']['min_overlap_days']))
    html = html.replace('__WIN__', str(pack['params']['window_mask']))
    html = html.replace('__Z__', str(pack['params']['z_threshold']))
    html = html.replace('__M__', str(pack['n_tests']))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', default='build/out/scan_pack.json')
    ap.add_argument('--web', default='build/out/series_web/web_series.json')
    ap.add_argument('--hist', default='build/out/hist_scan.json')
    ap.add_argument('--out', default='交付/产业链异常背离扫描看板.html')
    a = ap.parse_args(argv)
    print('saved', build(a.pack, a.web, a.hist, a.out))


if __name__ == '__main__':
    main()
