# -*- coding: utf-8 -*-
"""
report_html.py —— 生成自包含的交互式 HTML 报告（单文件，无外部依赖）

交互能力（全部离线计算，不联网）：
  · 品种池 / 地区范围筛选 → 排行榜、价差矩阵、地图实时重算
  · 历史窗口切换（3/6/12/24/36 个月）→ 分位与异常度按所选窗口重算
  · 运费调整开关 → 用户在前端直接录入「方向 × 单价」，实时重算扣除后差异
  · 点击排行榜任一行 → 展开该组合的完整价差历史曲线、区间分布、区域供需背景、数据来源
"""
from __future__ import annotations

import html
import json
import os
from typing import Any, Dict, List

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --bg:#0d1117;--bg2:#141b24;--card:#161d27;--card2:#1b2431;--line:#243040;
  --txt:#e6edf5;--dim:#8b9bb0;--dim2:#5f7085;
  --hi:#ff5d5d;--hi2:#ff9f43;--ok:#2ecc9b;--lo:#4aa3ff;--acc:#7c9cff;
  --shadow:0 8px 30px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--acc);text-decoration:none}
.wrap{max-width:1560px;margin:0 auto;padding:0 26px 80px}
/* ---------- header ---------- */
header{position:relative;overflow:hidden;border-bottom:1px solid var(--line);
  background:radial-gradient(1200px 400px at 12% -10%,rgba(124,156,255,.20),transparent 60%),
             radial-gradient(900px 360px at 85% 0%,rgba(255,93,93,.14),transparent 55%),var(--bg2);}
.hd{max-width:1560px;margin:0 auto;padding:30px 26px 24px}
.kicker{font-size:12px;letter-spacing:.22em;color:var(--acc);text-transform:uppercase;font-weight:600}
h1{margin:8px 0 10px;font-size:30px;font-weight:750;letter-spacing:-.3px}
h1 small{display:block;font-size:14px;font-weight:500;color:var(--dim);letter-spacing:0;margin-top:8px}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.pill{background:rgba(124,156,255,.10);border:1px solid rgba(124,156,255,.30);color:#b9c8ff;
  padding:4px 11px;border-radius:999px;font-size:12px}
.pill.warn{background:rgba(255,159,67,.10);border-color:rgba(255,159,67,.35);color:#ffc78a}
.pill.bad{background:rgba(255,93,93,.10);border-color:rgba(255,93,93,.35);color:#ffa8a8}
.pill.ok{background:rgba(46,204,155,.10);border-color:rgba(46,204,155,.35);color:#8ee8c8}
/* ---------- notice ---------- */
.notice{margin:20px 0 0;border:1px solid rgba(255,159,67,.35);background:linear-gradient(180deg,rgba(255,159,67,.10),rgba(255,159,67,.03));
  border-radius:12px;padding:14px 18px;font-size:13px;color:#ffd9ac}
.notice b{color:#ffb45e}
.notice ul{margin:8px 0 0;padding-left:20px}
.notice li{margin:3px 0}
/* ---------- kpi ---------- */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:14px;margin:22px 0 6px}
.kpi{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);
  border-radius:14px;padding:15px 16px;box-shadow:var(--shadow)}
.kpi .lab{font-size:11.5px;color:var(--dim);letter-spacing:.06em}
.kpi .val{font-size:27px;font-weight:750;margin-top:4px;letter-spacing:-.5px}
.kpi .sub{font-size:11.5px;color:var(--dim2);margin-top:3px}
/* ---------- controls ---------- */
.ctrl{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end;background:var(--card);
  border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:22px 0;box-shadow:var(--shadow)}
.fld{display:flex;flex-direction:column;gap:6px;min-width:150px}
.fld>label{font-size:11.5px;color:var(--dim);letter-spacing:.05em}
select,input[type=number],input[type=text]{background:#0e141c;color:var(--txt);border:1px solid var(--line);
  border-radius:8px;padding:8px 10px;font-size:13px;font-family:inherit;outline:none;transition:.15s}
select:focus,input:focus{border-color:var(--acc);box-shadow:0 0 0 3px rgba(124,156,255,.13)}
.seg{display:flex;background:#0e141c;border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg button{background:transparent;border:0;color:var(--dim);padding:8px 13px;font-size:12.5px;
  cursor:pointer;font-family:inherit;border-right:1px solid var(--line);transition:.15s}
.seg button:last-child{border-right:0}
.seg button.on{background:rgba(124,156,255,.18);color:#cfd9ff;font-weight:600}
.seg button:hover:not(.on){background:rgba(255,255,255,.04)}
.sw{display:flex;align-items:center;gap:9px;cursor:pointer;user-select:none;padding-bottom:8px}
.sw input{display:none}
.sw .track{width:44px;height:24px;border-radius:999px;background:#26313f;position:relative;transition:.2s}
.sw .track:after{content:"";position:absolute;width:18px;height:18px;border-radius:50%;background:#8b9bb0;
  top:3px;left:3px;transition:.2s}
.sw input:checked + .track{background:rgba(46,204,155,.35)}
.sw input:checked + .track:after{left:23px;background:var(--ok)}
.sw span{font-size:12.5px;color:var(--dim)}
/* ---------- sections ---------- */
h2{font-size:19px;margin:38px 0 6px;font-weight:700;display:flex;align-items:center;gap:10px}
h2 .n{font-size:12px;color:var(--acc);border:1px solid rgba(124,156,255,.35);border-radius:6px;
  padding:1px 7px;font-weight:600}
.desc{color:var(--dim);font-size:13px;margin:0 0 16px;max-width:1100px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);overflow:hidden}
/* ---------- table ---------- */
.tw{overflow:auto;max-height:none}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:12.8px}
th{position:sticky;top:0;background:#131a23;color:var(--dim);font-weight:600;text-align:left;
  padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap;font-size:11.5px;
  letter-spacing:.04em;z-index:5}
td{padding:9px 12px;border-bottom:1px solid rgba(36,48,64,.6);vertical-align:middle;white-space:nowrap}
tbody tr{cursor:pointer;transition:background .12s}
tbody tr:hover{background:rgba(124,156,255,.07)}
tbody tr.sel{background:rgba(124,156,255,.14)!important}
tbody tr:last-child td{border-bottom:0}
.num{text-align:right;font-variant-numeric:tabular-nums}
.b{font-weight:650}
.tag{display:inline-block;padding:1.5px 8px;border-radius:6px;font-size:11px;font-weight:600;white-space:nowrap}
.t-excess{background:rgba(255,93,93,.16);color:#ff9191;border:1px solid rgba(255,93,93,.35)}
.t-elev{background:rgba(255,159,67,.15);color:#ffb968;border:1px solid rgba(255,159,67,.32)}
.t-norm{background:rgba(46,204,155,.12);color:#7ee0bd;border:1px solid rgba(46,204,155,.28)}
.t-ins{background:rgba(139,155,176,.13);color:#9fb0c4;border:1px solid rgba(139,155,176,.3)}
.bar{height:6px;border-radius:3px;background:#222d3b;overflow:hidden;min-width:70px}
.bar>i{display:block;height:100%;border-radius:3px}
.pos{color:#ff8585}.neg{color:#5fd0a8}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
/* ---------- matrix ---------- */
.mx{display:grid;gap:2px;font-size:11.5px;min-width:max-content}
.mx div{padding:6px 8px;border-radius:5px;text-align:center;white-space:nowrap}
.mx .hd{background:#10161e;color:var(--dim);font-weight:600}
.mx .corner{background:transparent}
.mx .c{font-variant-numeric:tabular-nums;cursor:pointer;transition:.12s;border:1px solid transparent}
.mx .c:hover{outline:1px solid var(--acc);z-index:2}
.mx .na{background:#10161e;color:var(--dim2)}
/* ---------- map ---------- */
.mapbox{position:relative;background:radial-gradient(700px 400px at 50% 40%,rgba(124,156,255,.06),transparent 70%)}
svg.map{display:block;width:100%;height:auto}
.legend{display:flex;flex-wrap:wrap;gap:16px;padding:12px 18px;border-top:1px solid var(--line);
  font-size:12px;color:var(--dim)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}
/* ---------- detail ---------- */
.detail{margin-top:16px}
.dgrid{display:grid;grid-template-columns:1.35fr 1fr;gap:16px}
@media(max-width:1080px){.dgrid{grid-template-columns:1fr}}
.pad{padding:16px 18px}
.h3{font-size:13px;color:var(--dim);letter-spacing:.06em;margin:0 0 10px;font-weight:650}
.kv{display:grid;grid-template-columns:130px 1fr;gap:6px 12px;font-size:12.8px}
.kv .k{color:var(--dim)}
.hist{display:flex;align-items:flex-end;gap:2px;height:110px;padding:6px 0}
.hist i{flex:1;background:linear-gradient(180deg,#4aa3ff,#2b6cb0);border-radius:2px 2px 0 0;min-height:2px;transition:.15s}
.hist i:hover{background:#7c9cff}
.src{font-size:11.5px;color:var(--dim2);word-break:break-all;line-height:1.5}
.chip{display:inline-block;background:#0e141c;border:1px solid var(--line);border-radius:6px;
  padding:2px 8px;margin:2px 4px 2px 0;font-size:11.5px;color:var(--dim)}
.empty{color:var(--dim2);font-size:13px;padding:22px;text-align:center}
footer{margin-top:46px;padding-top:18px;border-top:1px solid var(--line);color:var(--dim2);font-size:11.5px}
.freight-zone{border-top:1px dashed var(--line);margin-top:14px;padding-top:12px}
.freight-zone .h3{margin-bottom:8px}
.frow{display:grid;grid-template-columns:1fr 92px 92px;gap:8px;align-items:center;margin-bottom:7px;font-size:12.3px}
.frow input{padding:6px 8px;font-size:12.3px}
.fnote{font-size:11.5px;color:var(--dim2);margin-top:8px}
.hint{font-size:12px;color:var(--dim2);margin-top:8px}
</style>
</head>
<body>
<header>
  <div class="hd">
    <div class="kicker">Regional Spread Anomaly Scan · 期现价差与量化</div>
    <h1>__TITLE__<small>__SUBTITLE__</small></h1>
    <div class="meta" id="hdmeta"></div>
  </div>
</header>
<div class="wrap">
  <div class="notice">
    <b>阅读前必读（方法与口径约束）</b>
    <ul>
      <li><b>裸价差 ≠ 套利机会。</b>本报告只陈述区域价差与其历史位置，不构成交易或套利建议；扣除运费后的数字也仅称「参考差异」。</li>
      <li><b>异常程度按各自历史分布衡量</b>，用分位数与「双侧尾部距离」判定，不按价差金额绝对值排序。</li>
      <li><b>运费必须由用户提供真实报价</b>；未提供时不做扣除、不做估算，界面默认关闭运费调整。</li>
      <li><b>价格口径为厂家/贸易商公开挂牌报价</b>（非交易所或资讯商统一市场价），同一省份同日多规格并存，已按可比规格档圈定后取中位数。</li>
      <li>覆盖不足或口径不可比的组合不会进入排行榜，统一登记在「数据缺口」中。</li>
    </ul>
  </div>
  <div class="kpis" id="kpis"></div>

  <div class="ctrl">
    <div class="fld"><label>产品池</label><select id="f-product"></select></div>
    <div class="fld"><label>地区范围</label><select id="f-region"></select></div>
    <div class="fld"><label>历史窗口</label>
      <div class="seg" id="f-window">
        <button data-v="3">3个月</button><button data-v="6">6个月</button>
        <button data-v="12" class="on">12个月</button><button data-v="24">24个月</button>
        <button data-v="36">36个月</button>
      </div>
    </div>
    <div class="fld"><label>异常阈值（分位）</label>
      <div class="seg" id="f-thr">
        <button data-v="0.90">90%</button><button data-v="0.95" class="on">95%</button>
        <button data-v="0.99">99%</button>
      </div>
    </div>
    <label class="sw"><input type="checkbox" id="f-freight"><span class="track"></span>
      <span>启用运费调整</span></label>
    <div class="fld"><label>&nbsp;</label><button id="f-reset" style="background:#1c2632;border:1px solid var(--line);color:var(--dim);border-radius:8px;padding:8px 14px;cursor:pointer;font-family:inherit">重置筛选</button></div>
  </div>

  <h2><span class="n">01</span>异常区域价差排行榜</h2>
  <p class="desc">按异常程度排序（异常度 = 1 − 2×双侧尾部距离，越接近 1 越处于历史尾部）。分位基于该组合<b>自身</b>在所选窗口内的历史价差分布。点击任意一行查看完整历史与区域背景。</p>
  <div class="card"><div class="tw"><table id="rank">
    <thead><tr>
      <th>#</th><th>品种</th><th>方向（基准 → 对照）</th><th>当前裸价差</th><th>占均价%</th>
      <th>历史分位</th><th>异常度</th><th>判定</th><th>近5期变化</th><th>近20期变化</th>
      <th>有效样本</th><th>里程</th><th id="th-net">扣除运费后(A→B)</th>
    </tr></thead><tbody></tbody>
  </table></div></div>

  <h2><span class="n">02</span>区域价差矩阵</h2>
  <p class="desc">行 = 基准地区，列 = 对照地区，单元格 = <b>行→列</b> 方向的当前价差（元/吨）。颜色表示历史分位：红=处于历史高位，蓝=处于历史低位，灰=样本不足或不可比。点击单元格可定位到该组合。</p>
  <div class="card"><div class="tw" style="padding:14px"><div id="matrix"></div></div></div>

  <h2><span class="n">03</span>区域地图</h2>
  <p class="desc">节点颜色 = 该地区主规格价格相对全国中位价的偏离方向；连线上标注扣除运费前的裸价差（元/吨），仅显示当前判定为偏离/异常的组合，避免图上信息过载。</p>
  <div class="card mapbox"><div id="map"></div><div class="legend" id="maplegend"></div></div>

  <h2><span class="n">04</span>组合详情</h2>
  <p class="desc" id="detail-hint">在上方排行榜或矩阵中选择一个组合。</p>
  <div id="detail"></div>

  <h2><span class="n">05</span>品种价格水平与口径</h2>
  <p class="desc">每个品种在当前窗口内各地区的主规格价格分布，以及该品种使用的规格档与口径说明。</p>
  <div class="card"><div class="tw"><table id="levels">
    <thead><tr><th>品种</th><th>地区</th><th>最新价</th><th>最新日期</th><th>窗口均价</th>
      <th>最低</th><th>最高</th><th>有效天数</th><th>规格档</th><th>口径</th></tr></thead>
    <tbody></tbody></table></div></div>

  <h2><span class="n">06</span>数据缺口与不可比说明</h2>
  <p class="desc">以下项目<b>没有</b>被纳入排行榜计算。缺口必须显式列出，不能用插值、估算或默认值填补。</p>
  <div class="card"><div class="tw"><table id="gaps">
    <thead><tr><th>类型</th><th>品种</th><th>相关地区/组合</th><th>说明</th></tr></thead><tbody></tbody></table></div></div>

  <footer id="foot"></footer>
</div>

<script>
const DATA = __DATA__;
const GRADE = {EXCESS_HIGH:['显著偏高','t-excess'],EXCESS_LOW:['显著偏低','t-excess'],
  ELEVATED:['偏高偏离','t-elev'],NORMAL:['正常区间','t-norm'],
  INSUFFICIENT:['样本不足','t-ins'],INCOMPARABLE:['不可比','t-ins']};
const $ = s => document.querySelector(s);
const fmt = (v,d=2) => (v===null||v===undefined||isNaN(v)) ? '—' : Number(v).toFixed(d);
const sgn = v => (v>0?'pos':(v<0?'neg':''));
const esc = s => String(s===null||s===undefined?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* 运费开关初始值取自数据本身：若这份结果本来就是「含用户运费」生成的，
   打开时就必须是已启用状态，否则头部显示「未扣除」而正文已有扣除值，自相矛盾。 */
const FREIGHT_ON_AT_LOAD = (DATA.combinations || []).some(c => c.freight && c.freight.enabled);
let ST = {product:'ALL', region:'ALL', window:12, thr:0.95, freight:FREIGHT_ON_AT_LOAD, sel:null};
document.addEventListener('DOMContentLoaded', () => {
  const cb = document.getElementById('f-freight');
  if(cb) cb.checked = FREIGHT_ON_AT_LOAD;
});

/* ---------------- 统计（前端重算，窗口可变） ---------------- */
function statFor(combo, months){
  const ser = combo.spread_series || [];
  if(!ser.length) return {n:0, grade:'INSUFFICIENT'};
  const asof = new Date(ser[ser.length-1].date);
  const cut = new Date(asof); cut.setMonth(cut.getMonth()-months);
  const win = ser.filter(x=> new Date(x.date) >= cut);
  if(!win.length) return {n:0, grade:'INSUFFICIENT'};
  const vals = win.map(x=>x.spread), now = vals[vals.length-1];
  const N = vals.length;
  let less=0, eq=0; vals.forEach(v=>{ if(v<now) less++; else if(v===now) eq++; });
  const pct = (less+0.5*eq)/N, tail = Math.min(pct,1-pct), anomaly = 1-2*tail;
  const mean = vals.reduce((a,b)=>a+b,0)/N;
  const dv = vals.map(v=>v-mean);
  const sd = N>2 ? Math.sqrt(dv.reduce((a,b)=>a+b*b,0)/(N-1)) : null;
  const z = (sd && sd>0) ? (now-mean)/sd : null;
  const srt=[...vals].sort((a,b)=>a-b);
  const chg5 = N>=6 ? now-vals[N-6] : null;
  const chg20 = N>=21 ? now-vals[N-21] : null;
  let grade;
  if(N < 20) grade='INSUFFICIENT';
  else if(pct >= ST.thr) grade='EXCESS_HIGH';
  else if(pct <= 1-ST.thr) grade='EXCESS_LOW';
  else if(pct >= 0.80 || pct <= 0.20) grade='ELEVATED';
  else grade='NORMAL';
  const pctA = win.map(x=> (x.p_a+x.p_b) ? (x.spread/((x.p_a+x.p_b)/2)*100) : null);
  return {n:N, now, pct, anomaly, z, mean, sd, chg5, chg20, grade,
    norm: pctA[pctA.length-1], min:srt[0], max:srt[N-1], series:win,
    p50:srt[Math.floor((N-1)*0.5)], p05:srt[Math.floor((N-1)*0.05)], p95:srt[Math.ceil((N-1)*0.95)]};
}

/* ---------------- 运费 ---------------- */
function freightFor(combo, key){
  if(!ST.freight) return null;
  const raw = FREIGHT[key];
  if(!raw) return null;
  const fee = Number(raw.fee);
  if(!isFinite(fee)) return null;
  let abs = fee;
  if(raw.unit === '元/吨·公里'){
    if(!combo.distance_km) return null;
    abs = fee * combo.distance_km;
  }
  return {fee:abs, mode:raw.mode||''};
}
/* 若结果本身已带用户运费（run_all.py --freight 生成），把已提供的方向报价
   预填进 FREIGHT，这样页头的「用户提供 N 条方向报价」与实际扣除一致，
   用户也可以在此基础上继续补录其他方向。 */
let FREIGHT = (() => {
  const o = {};
  (DATA.combinations || []).forEach(c => {
    const f = c.freight;
    if(!f || !f.enabled) return;
    ['a_to_b', 'b_to_a'].forEach(k => {
      const d = f[k];
      if(d && d.available && d.fee_input != null){
        const key = (k === 'a_to_b' ? c.base + '->' + c.quote : c.quote + '->' + c.base);
        o[key] = {fee: d.fee_input, unit: d.fee_unit || '元/吨', mode: d.mode || '', note: d.note || ''};
      }
    });
  });
  return o;
})();

function netFor(combo, st){
  const ab = freightFor(combo, combo.base+'->'+combo.quote);
  const ba = freightFor(combo, combo.quote+'->'+combo.base);
  return {ab: ab? st.now - ab.fee : null, ba: ba? -st.now - ba.fee : null, feeAB: ab, feeBA: ba};
}

/* ---------------- 组合集合 ---------------- */
function currentCombos(){
  return DATA.combinations.filter(c=>{
    if(ST.product!=='ALL' && c.product_key!==ST.product) return false;
    if(ST.region!=='ALL' && c.base!==ST.region && c.quote!==ST.region) return false;
    return true;
  }).map(c=>{
    const st = statFor(c, ST.window);
    return Object.assign({}, c, st, {net: netFor(c, st)});
  }).sort((a,b)=> (a.grade==='INSUFFICIENT')-(b.grade==='INSUFFICIENT')
     || (b.anomaly||0)-(a.anomaly||0) || Math.abs(b.norm||0)-Math.abs(a.norm||0));
}

/* ---------------- 头部 / KPI ---------------- */
function freightOn(){ return Object.keys(FREIGHT).length > 0; }
function renderHead(){
  const s = DATA.summary;
  const nFee = Object.keys(FREIGHT).length;
  const feePill = !ST.freight ? ['运费','运费调整已关闭 → 未扣除','warn']
    : (nFee ? ['运费','用户提供 '+nFee+' 条方向报价 → 已按方向扣除','ok']
            : ['运费','已开启，但尚未录入方向报价 → 未扣除','warn']);
  $('#hdmeta').innerHTML = [
    ['数据截止','<b>'+esc(s.asof||'—')+'</b>',''],
    ['价格口径','厂家/贸易商挂牌报价中位数',''],
    ['品种池', Object.values(DATA.products).map(p=>p.product).join(' / '), ''],
    feePill,
    ['套利判断','本报告不提供','bad'],
  ].map(([k,v,cls])=>`<span class="pill ${cls}">${esc(k)}：${v}</span>`).join('');
  const combos = currentCombos();
  const exc = combos.filter(c=>c.grade==='EXCESS_HIGH'||c.grade==='EXCESS_LOW').length;
  const ele = combos.filter(c=>c.grade==='ELEVATED').length;
  const ins = combos.filter(c=>c.grade==='INSUFFICIENT').length;
  const nodes = new Set(); combos.forEach(c=>{nodes.add(c.base);nodes.add(c.quote)});
  $('#kpis').innerHTML = [
    ['品种数', Object.keys(DATA.products).length, '进入扫描的产品池'],
    ['地区节点', nodes.size, '有同口径报价的地区'],
    ['可比组合', combos.length, '当前筛选下的地区对'],
    ['显著偏离', exc, '分位达阈值（'+(ST.thr*100).toFixed(0)+'%）'],
    ['偏高关注', ele, '分位 80%–阈值之间'],
    ['样本不足', ins, '未下异常结论'],
  ].map(([k,v,s2])=>`<div class="kpi"><div class="lab">${k}</div><div class="val">${v}</div><div class="sub">${s2}</div></div>`).join('');
}

/* ---------------- 排行榜 ---------------- */
function renderRank(){
  const rows = currentCombos();
  const tb = $('#rank tbody');
  if(!rows.length){ tb.innerHTML = '<tr><td colspan="13" class="empty">当前筛选下无可比组合</td></tr>'; return; }
  tb.innerHTML = rows.map((c,i)=>{
    const [zh,tcl] = GRADE[c.grade];
    const pctW = Math.round((c.pct||0)*100);
    const netTxt = ST.freight
      ? (c.net.ab!==null? `<span class="${sgn(c.net.ab)} b">${fmt(c.net.ab,0)}</span>` : '<span style="color:var(--dim2)">缺运费</span>')
      : '<span style="color:var(--dim2)">未启用</span>';
    return `<tr data-pair="${esc(c.pair_code)}" class="${ST.sel===c.pair_code?'sel':''}">
      <td class="num" style="color:var(--dim2)">${i+1}</td>
      <td>${esc(c.product)}</td>
      <td class="mono">${esc(c.base_region)} <span style="color:var(--dim2)">→</span> ${esc(c.quote_region)}</td>
      <td class="num b ${sgn(c.now)}">${fmt(c.now,0)}</td>
      <td class="num">${fmt(c.norm,2)}%</td>
      <td class="num">${pctW}%<div class="bar"><i style="width:${pctW}%;background:${c.pct>=ST.thr?'#ff5d5d':(c.pct<=1-ST.thr?'#4aa3ff':'#2ecc9b')}"></i></div></td>
      <td class="num b">${fmt(c.anomaly,2)}</td>
      <td><span class="tag ${tcl}">${zh}</span></td>
      <td class="num ${sgn(c.chg5)}">${c.chg5!==null?fmt(c.chg5,0):'—'}</td>
      <td class="num ${sgn(c.chg20)}">${c.chg20!==null?fmt(c.chg20,0):'—'}</td>
      <td class="num" style="color:var(--dim)">${c.n}</td>
      <td class="num" style="color:var(--dim)">${c.distance_km?Math.round(c.distance_km)+'km':'—'}</td>
      <td class="num">${netTxt}</td>
    </tr>`;
  }).join('');
  tb.querySelectorAll('tr').forEach(tr=>tr.onclick=()=>select(tr.dataset.pair));
}

/* ---------------- 矩阵 ---------------- */
function renderMatrix(){
  const combos = DATA.combinations.filter(c=>{
    if(ST.product!=='ALL' && c.product_key!==ST.product) return false;
    return true;
  });
  const nodes = [...new Set(combos.flatMap(c=>[c.base,c.quote]))];
  const regName = {}; combos.forEach(c=>{regName[c.base]=c.base_region; regName[c.quote]=c.quote_region;});
  if(!nodes.length){ $('#matrix').innerHTML='<div class="empty">无可比组合</div>'; return; }
  const idx = {}; combos.forEach(c=>idx[c.base+'|'+c.quote]=c);
  const col = pct => {
    if(pct===null||pct===undefined) return 'background:#10161e;color:#5f7085';
    const d = Math.abs(pct-0.5)*2;
    if(pct>=0.5) return `background:rgba(255,93,93,${0.10+d*0.55});color:#ffd5d5`;
    return `background:rgba(74,163,255,${0.10+d*0.55});color:#d6e8ff`;
  };
  let h = `<div class="mx" style="grid-template-columns:120px repeat(${nodes.length},minmax(78px,1fr))">`;
  h += '<div class="hd corner">基准 \\ 对照</div>';
  nodes.forEach(n=> h += `<div class="hd">${esc(regName[n]||n)}</div>`);
  nodes.forEach(r=>{
    h += `<div class="hd" style="text-align:right">${esc(regName[r]||r)}</div>`;
    nodes.forEach(cn=>{
      if(r===cn){ h += '<div class="na">—</div>'; return; }
      const c = idx[r+'|'+cn];
      if(!c){ h += '<div class="na">·</div>'; return; }
      const st = statFor(c, ST.window);
      h += `<div class="c" style="${col(st.pct)}" data-pair="${esc(c.pair_code)}" title="${esc(c.formula)} | 分位 ${st.pct!==null?fmt(st.pct*100,1)+'%':'—'} | 样本 ${st.n}">${st.now!==undefined?fmt(st.now,0):'—'}</div>`;
    });
  });
  h += '</div>';
  $('#matrix').innerHTML = h;
  $('#matrix').querySelectorAll('.c').forEach(el=>el.onclick=()=>select(el.dataset.pair));
}

/* ---------------- 地图 ---------------- */
const GEO = __GEO__;
function renderMap(){
  // 用组合数据补全节点显示名（GEO 里可能只有代码）
  const NAME = {};
  DATA.combinations.forEach(c=>{ NAME[c.base]=c.base_region; NAME[c.quote]=c.quote_region; });
  const combos = currentCombos().filter(c=>c.grade!=='INSUFFICIENT');
  const nodes = [...new Set(combos.flatMap(c=>[c.base,c.quote]))].filter(n=>GEO[n]);
  const W=1180,H=560;
  if(!nodes.length){ $('#map').innerHTML='<div class="empty">当前筛选下无可用节点（缺少地区坐标）</div>'; return; }
  const lons=nodes.map(n=>GEO[n].lon), lats=nodes.map(n=>GEO[n].lat);
  const lo0=Math.min(...lons)-2, lo1=Math.max(...lons)+2, la0=Math.min(...lats)-1.4, la1=Math.max(...lats)+1.8;
  const X = lo => (lo-lo0)/(lo1-lo0)*(W-140)+70;
  const Y = la => (la1-la)/(la1-la0)*(H-100)+46;
  const pval={}; combos.forEach(c=>{ (pval[c.base]=pval[c.base]||[]).push(c.series?c.series[c.series.length-1].p_a:null);
                                    (pval[c.quote]=pval[c.quote]||[]).push(c.series?c.series[c.series.length-1].p_b:null);});
  const meds = Object.entries(pval).map(([k,v])=>[k, v.filter(x=>x).sort((a,b)=>a-b)[Math.floor(v.filter(x=>x).length/2)]]).filter(x=>x[1]);
  const allMed = meds.map(x=>x[1]).sort((a,b)=>a-b)[Math.floor(meds.length/2)] || 1;
  let svg=`<svg class="map" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<defs><marker id="ar" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
    <polygon points="0 0, 9 3.5, 0 7" fill="#ff5d5d" opacity=".85"/></marker></defs>`;
  combos.slice(0,26).forEach(c=>{
    if(!GEO[c.base]||!GEO[c.quote]) return;
    const x1=X(GEO[c.base].lon), y1=Y(GEO[c.base].lat), x2=X(GEO[c.quote].lon), y2=Y(GEO[c.quote].lat);
    const big = Math.abs(c.now)>0;
    const c2 = (c.grade==='EXCESS_HIGH'||c.grade==='EXCESS_LOW') ? '#ff5d5d' : '#ff9f43';
    const mx=(x1+x2)/2, my=(y1+y2)/2;
    svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${c2}" stroke-width="${1+Math.min(3,Math.abs(c.anomaly||0)*2)}"
              stroke-dasharray="${c.grade==='ELEVATED'?'5 4':''}" marker-end="url(#ar)" opacity=".55"/>`;
    svg += `<text x="${mx}" y="${my-4}" fill="${c2}" font-size="10.5" text-anchor="middle" opacity=".95">${fmt(c.now,0)}</text>`;
  });
  meds.forEach(([n,p])=>{
    const g=GEO[n]; const dev=(p-allMed)/allMed*100;
    const fill = dev>1.5?'#ff5d5d':(dev<-1.5?'#4aa3ff':'#2ecc9b');
    svg += `<circle cx="${X(g.lon)}" cy="${Y(g.lat)}" r="7" fill="${fill}" stroke="#0d1117" stroke-width="2"/>`;
    svg += `<text x="${X(g.lon)}" y="${Y(g.lat)+21}" fill="#e6edf5" font-size="11.5" text-anchor="middle">${esc(NAME[n]||GEO[n].name||n)}</text>`;
    svg += `<text x="${X(g.lon)}" y="${Y(g.lat)-12}" fill="#8b9bb0" font-size="10" text-anchor="middle">${fmt(p,0)}</text>`;
  });
  svg+='</svg>';
  $('#map').innerHTML = svg;
  $('#maplegend').innerHTML = `
    <span><i style="background:#ff5d5d"></i>价格高于全国中位</span>
    <span><i style="background:#2ecc9b"></i>接近中位（±1.5%内）</span>
    <span><i style="background:#4aa3ff"></i>价格低于全国中位</span>
    <span style="color:var(--dim2)">连线 = 当前判定为偏离/异常的组合，标注当前裸价差（元/吨）；虚线 = 偏高偏离</span>`;
}

/* ---------------- 详情 ---------------- */
function select(pair){
  ST.sel = pair; renderRank(); renderDetail();
  const el = document.getElementById('detail');
  if (el && typeof el.scrollIntoView === 'function') el.scrollIntoView({behavior:'smooth', block:'start'});
}
/* 记录当前详情页里用户已输入但尚未提交的运费原值，避免重渲染后丢失 */
let FEE_DRAFT = {};
function feeValue(k){
  if(k in FEE_DRAFT) return FEE_DRAFT[k];
  return FREIGHT[k] ? FREIGHT[k].fee : '';
}
function renderDetail(){
  const c = DATA.combinations.find(x=>x.pair_code===ST.sel);
  const box = $('#detail');
  if(!c){ box.innerHTML='<div class="card"><div class="empty">在上方排行榜或矩阵中选择一个组合</div></div>'; $('#detail-hint').textContent='在上方排行榜或矩阵中选择一个组合。'; return; }
  const st = statFor(c, ST.window);
  const [zh,tcl] = GRADE[st.grade];
  const prod = DATA.products[c.product_key] || {};
  const fx = (DATA.background && DATA.background[c.product_key]) || {};
  const reg_a = (fx.regions||{})[c.base] || {}, reg_b = (fx.regions||{})[c.quote] || {};
  const ser = st.series || [];
  const mn = Math.min(...ser.map(x=>x.spread)), mx = Math.max(...ser.map(x=>x.spread));
  const hb = ser.map(x=>{
    const h = mx>mn ? (x.spread-mn)/(mx-mn)*100 : 50;
    return `<i style="height:${Math.max(3,h)}%" title="${x.date}  价差 ${fmt(x.spread,0)}"></i>`;
  }).join('');
  const net = netFor(c, st);

  box.innerHTML = `
  <div class="card detail">
    <div class="pad" style="border-bottom:1px solid var(--line);display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:center">
      <div>
        <div style="font-size:17px;font-weight:700">${esc(c.product)} · ${esc(c.base_region)} <span style="color:var(--dim2)">→</span> ${esc(c.quote_region)}</div>
        <div class="src" style="margin-top:4px">价差定义：${esc(c.formula)}（方向固定，窗口内不翻转）</div>
      </div>
      <div style="text-align:right">
        <span class="tag ${tcl}" style="font-size:12.5px;padding:4px 12px">${zh}</span>
        <div class="src" style="margin-top:6px">当前裸价差 <b class="${sgn(st.now)}" style="font-size:15px">${fmt(st.now,0)}</b> 元/吨 · 分位 ${st.pct!==null?fmt(st.pct*100,1):'—'}% · 异常度 ${fmt(st.anomaly,2)}</div>
      </div>
    </div>
    <div class="dgrid">
      <div class="pad" style="border-right:1px solid var(--line)">
        <div class="h3">价差历史（近 ${ser.length} 期，${ser.length?esc(ser[0].date):''} 起）</div>
        <div class="hist">${hb||'<div class="empty">无数据</div>'}</div>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--dim2);margin-top:4px">
          <span>${ser.length?esc(ser[0].date):''}</span>
          <span>区间 ${fmt(mn,0)} ~ ${fmt(mx,0)} 元/吨</span>
          <span>${ser.length?esc(ser[ser.length-1].date):''}</span>
        </div>
        <div class="kv" style="margin-top:14px">
          <div class="k">当前价差</div><div class="b ${sgn(st.now)}">${fmt(st.now,0)} 元/吨</div>
          <div class="k">历史分位</div><div>${st.pct!==null?fmt(st.pct*100,1)+'%':'—'}（0% = 历史最低，100% = 历史最高）</div>
          <div class="k">异常度</div><div>${fmt(st.anomaly,2)} <span style="color:var(--dim2)">= 1 − 2×尾部距离</span></div>
          <div class="k">z 值</div><div>${fmt(st.z,2)}</div>
          <div class="k">窗口均值 / 标准差</div><div>${fmt(st.mean,0)} / ${fmt(st.sd,0)}</div>
          <div class="k">分位分布</div><div>P5 ${fmt(st.p05,0)} · P50 ${fmt(st.p50,0)} · P95 ${fmt(st.p95,0)}</div>
          <div class="k">近5期 / 20期变化</div><div><span class="${sgn(st.chg5)}">${st.chg5!==null?fmt(st.chg5,0):'—'}</span> / <span class="${sgn(st.chg20)}">${st.chg20!==null?fmt(st.chg20,0):'—'}</span></div>
          <div class="k">有效样本（配对日）</div><div>${st.n} 天</div>
          <div class="k">公路里程 / 时长</div><div>${c.distance_km?Math.round(c.distance_km)+' km · '+fmt(c.drive_hours,1)+' h（OSRM 实测路由）':'—'}</div>
        </div>
        <div class="freight-zone">
          <div class="h3">运费调整（按方向分别录入真实报价）</div>
          <div class="frow" style="color:var(--dim);font-size:11.5px"><span>方向</span><span>运费(元/吨)</span><span>单位</span></div>
          <div class="frow">
            <span>${esc(c.base_region)} → ${esc(c.quote_region)}</span>
            <input type="number" step="0.01" placeholder="未提供" data-f="${esc(c.base+'->'+c.quote)}">
            <select data-u="${esc(c.base+'->'+c.quote)}"><option value="元/吨">元/吨</option><option value="元/吨·公里">元/吨·公里</option></select>
          </div>
          <div class="frow">
            <span>${esc(c.quote_region)} → ${esc(c.base_region)}</span>
            <input type="number" step="0.01" placeholder="未提供" data-f="${esc(c.quote+'->'+c.base)}">
            <select data-u="${esc(c.quote+'->'+c.base)}"><option value="元/吨">元/吨</option><option value="元/吨·公里">元/吨·公里</option></select>
          </div>
          <div class="kv" style="margin-top:10px">
            <div class="k">正向参考差异</div><div>${net.ab!==null?`<b class="${sgn(net.ab)}">${fmt(net.ab,0)}</b> 元/吨（已扣 ${fmt(net.feeAB.fee,0)}）`:'<span style="color:var(--dim2)">未提供运费，未扣除</span>'}</div>
            <div class="k">反向参考差异</div><div>${net.ba!==null?`<b class="${sgn(net.ba)}">${fmt(net.ba,0)}</b> 元/吨（已扣 ${fmt(net.feeBA.fee,0)}）`:'<span style="color:var(--dim2)">未提供运费，未扣除</span>'}</div>
          </div>
          <div class="fnote">扣除后为负表示「价差不足以覆盖该方向物流成本」；此处仅为参考差异，不构成套利判断（未计入资金成本、损耗、账期、资质与库容约束）。</div>
        </div>
      </div>
      <div class="pad">
        <div class="h3">区域供需与背景</div>
        ${(fx.summary? `<div style="font-size:12.8px;color:var(--dim);margin-bottom:12px">${esc(fx.summary)}</div>`:'')}
        <div class="kv">
          ${c.base!==c.quote?`
          <div class="k">${esc(c.base_region)} 角色</div><div>${esc(reg_a.role||'—')}</div>
          <div class="k">${esc(c.base_region)} 产能/供给</div><div>${esc(reg_a.supply||'—')}</div>
          <div class="k">${esc(c.base_region)} 需求</div><div>${esc(reg_a.demand||'—')}</div>
          <div class="k">${esc(c.base_region)} 近期动态</div><div>${esc(reg_a.news||'—')}</div>
          <div class="k" style="border-top:1px solid var(--line);padding-top:8px">${esc(c.quote_region)} 角色</div><div style="border-top:1px solid var(--line);padding-top:8px">${esc(reg_b.role||'—')}</div>
          <div class="k">${esc(c.quote_region)} 产能/供给</div><div>${esc(reg_b.supply||'—')}</div>
          <div class="k">${esc(c.quote_region)} 需求</div><div>${esc(reg_b.demand||'—')}</div>
          <div class="k">${esc(c.quote_region)} 近期动态</div><div>${esc(reg_b.news||'—')}</div>
          `:''}
        </div>
        ${fx.drivers&&fx.drivers.length?`<div class="h3" style="margin-top:16px">当前价差的主要解释因素</div>
          <ul style="margin:0;padding-left:18px;font-size:12.8px;color:var(--dim)">${fx.drivers.map(d=>`<li>${esc(d)}</li>`).join('')}</ul>`:''}
        <div class="h3" style="margin-top:16px">口径与来源</div>
        <div>
          <span class="chip">规格档：${esc(prod.spec_tier_used||'—')}</span>
          <span class="chip">${esc(c.spec_tier)}</span>
          <span class="chip">挂牌报价中位数</span>
          <span class="chip">含税</span>
          <span class="chip">${esc((fx.basis||prod.price_basis||'—'))}</span>
        </div>
        <div class="src" style="margin-top:8px">
          数据来源：${esc((fx.source||'ChemicalBook 价格报告（厂家/贸易商公开挂牌报价）'))}
          ${fx.source_url?` · <a href="${esc(fx.source_url)}" target="_blank" rel="noopener">原始页面</a>`:''}
        </div>
        ${fx.sources&&fx.sources.length?`<div class="src" style="margin-top:6px">${fx.sources.map(s=>esc(s)).join(' ｜ ')}</div>`:''}
      </div>
    </div>
  </div>`;

  box.querySelectorAll('input[data-f]').forEach(inp=>{
    const k = inp.dataset.f;
    if(feeValue(k) !== '') inp.value = feeValue(k);
    inp.oninput = ()=>{ FEE_DRAFT[k] = inp.value; };
    inp.onchange = ()=>{
      const sel = box.querySelector(`select[data-u="${k}"]`);
      FEE_DRAFT[k] = inp.value;
      if(inp.value===''){ delete FREIGHT[k]; }
      else if(FREIGHT[k]){ FREIGHT[k].fee = Number(inp.value); if(sel) FREIGHT[k].unit = sel.value; }
      else FREIGHT[k] = {fee:Number(inp.value), unit: sel?sel.value:'元/吨'};
      if(!ST.freight){ ST.freight=true; $('#f-freight').checked=true; }
      renderAll();
    };
  });
  box.querySelectorAll('select[data-u]').forEach(sel=>{
    const k = sel.dataset.u;
    if(FREIGHT[k]) sel.value = FREIGHT[k].unit;
    sel.dataset.unit = sel.value;
    sel.onchange = ()=>{
      const inp = box.querySelector(`input[data-f="${k}"]`);
      if(inp && inp.value !== ''){ if(!FREIGHT[k]) FREIGHT[k]={}; FREIGHT[k].fee=Number(inp.value); FREIGHT[k].unit=sel.value; }
      else if(FREIGHT[k]){ FREIGHT[k].unit = sel.value; }
      if(!ST.freight){ ST.freight=true; $('#f-freight').checked=true; }
      renderAll();
    };
  });
}

/* ---------------- 价格水平 ---------------- */
function renderLevels(){
  const tb = $('#levels tbody');
  const rows = [];
  Object.entries(DATA.products).forEach(([pk,p])=>{
    Object.entries(p.regions||{}).forEach(([rc,r])=>{
      rows.push({pk, product:p.product, rc, r});
    });
  });
  if(!rows.length){ tb.innerHTML='<tr><td colspan="10" class="empty">无数据</td></tr>'; return; }
  tb.innerHTML = rows.map(({product,r})=>`
    <tr style="cursor:default">
      <td>${esc(product)}</td><td>${esc(r.region)}</td>
      <td class="num b">${fmt(r.latest,0)}</td><td class="mono" style="color:var(--dim)">${esc(r.latest_date)}</td>
      <td class="num">${fmt(r.daily_mean,0)}</td>
      <td class="num" style="color:var(--lo)">${fmt(r.daily_min,0)}</td>
      <td class="num" style="color:var(--hi)">${fmt(r.daily_max,0)}</td>
      <td class="num" style="color:var(--dim)">${r.n_days}</td>
      <td><span class="chip">${esc(r.spec_tier)}</span></td>
      <td style="color:var(--dim2);font-size:11.5px;white-space:normal;max-width:380px">${esc((r.quote_type||[]).join('/'))}</td>
    </tr>`).join('');
}

/* ---------------- 缺口 ---------------- */
function renderGaps(){
  const tb = $('#gaps tbody');
  const g = DATA.gaps || [];
  if(!g.length){ tb.innerHTML='<tr><td colspan="4" class="empty">无登记缺口</td></tr>'; return; }
  const nameOf = pk => (DATA.products[pk]&&DATA.products[pk].product)||pk;
  tb.innerHTML = g.map(x=>`<tr style="cursor:default">
    <td><span class="tag t-ins">${esc(x.gap_zh||x.gap)}</span></td>
    <td>${esc(nameOf(x.product_key))}</td>
    <td class="mono" style="color:var(--dim)">${esc(x.region||x.pair||(x.regions_available||[]).join(',')||'—')}</td>
    <td style="white-space:normal;color:var(--dim)">${esc(x.detail)}</td></tr>`).join('');
}

/* ---------------- 主控 ---------------- */
function renderAll(){
  renderHead(); renderRank(); renderMatrix(); renderMap(); renderLevels(); renderGaps();
  if(ST.sel) renderDetail();
}
function init(){
  const ps = $('#f-product');
  ps.innerHTML = '<option value="ALL">全部品种</option>' +
    Object.entries(DATA.products).map(([k,p])=>`<option value="${esc(k)}">${esc(p.product)}</option>`).join('');
  const regions = [...new Set(DATA.combinations.flatMap(c=>[[c.base,c.base_region],[c.quote,c.quote_region]]))];
  const seen={}; regions.forEach(([k,v])=>{seen[k]=v});
  $('#f-region').innerHTML = '<option value="ALL">全部地区</option>' +
    Object.entries(seen).sort((a,b)=>a[1].localeCompare(b[1],'zh')).map(([k,v])=>`<option value="${esc(k)}">${esc(v)}</option>`).join('');
  ps.onchange = ()=>{ST.product=ps.value; ST.sel=null; renderAll(); $('#detail').innerHTML='<div class="card"><div class="empty">在上方排行榜或矩阵中选择一个组合</div></div>';};
  $('#f-region').onchange = e=>{ST.region=e.target.value; renderAll();};
  document.querySelectorAll('#f-window button').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('#f-window button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); ST.window=Number(b.dataset.v); renderAll();
  });
  document.querySelectorAll('#f-thr button').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('#f-thr button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); ST.thr=Number(b.dataset.v); renderAll();
  });
  $('#f-freight').onchange = e=>{ST.freight=e.target.checked; renderAll();};
  $('#f-reset').onclick = ()=>{
    ST={product:'ALL',region:'ALL',window:12,thr:0.95,freight:false,sel:null}; FREIGHT={};
    $('#f-product').value='ALL'; $('#f-region').value='ALL'; $('#f-freight').checked=false;
    document.querySelectorAll('#f-window button').forEach(x=>x.classList.toggle('on',x.dataset.v==='12'));
    document.querySelectorAll('#f-thr button').forEach(x=>x.classList.toggle('on',x.dataset.v==='0.95'));
    $('#detail').innerHTML='<div class="card"><div class="empty">在上方排行榜或矩阵中选择一个组合</div></div>';
    renderAll();
  };
  const s = DATA.summary;
  $('#foot').innerHTML = `生成时间 ${esc(DATA.generated_at)} · 数据截止 ${esc(s.asof||'—')} ·
    组合 ${s.n_combinations} 个 · 产品 ${s.n_products} 个 · 数据缺口 ${s.n_gaps} 项<br>
    本报告由「扫描异常区域价差」Skill 自动生成。价格来自公开渠道的厂家/贸易商挂牌报价，
    已按规格档与地区节点统一口径；历史分位基于各自分布计算。报告不构成投资或交易建议。`;
  renderAll();
  if(DATA.combinations.length) select(DATA.combinations[0].pair_code);
}
init();
</script>
</body>
</html>
"""


# 坐标兜底：当 data_raw/distances.json 未收录某节点时（例如该节点不参与运费折算），
# 用省/市驻地坐标保证地图仍可渲染。坐标为地理常识值，仅用于绘图，不参与任何计算。
FALLBACK_GEO = {
    'H_HENAN': ('河南', 113.63, 34.75), 'H_HUBEI': ('湖北', 114.30, 30.59),
    'H_HUNAN': ('湖南', 112.94, 28.23), 'EC_JIANGSU': ('江苏', 118.80, 32.06),
    'EC_JIANGXI': ('江西', 115.89, 28.68), 'EC_SHANGHAI': ('上海', 121.47, 31.23),
    'EC_ZHEJIANG': ('浙江', 120.15, 30.28), 'EC_SHANDONG': ('山东', 117.00, 36.67),
    'EC_ANHUI': ('安徽', 117.28, 31.86), 'EC_TAICANG': ('江苏太仓', 121.10, 31.45),
    'EC_ZIBO': ('山东淄博', 118.05, 36.81), 'N_HEBEI': ('河北沙河', 114.50, 36.86),
    'N_INNERMONGOLIA': ('内蒙古', 111.75, 40.84), 'N_QINGHAI': ('青海', 101.78, 36.62),
    'N_SHAANXI': ('陕西', 108.94, 34.34), 'N_NINGXIA': ('宁夏', 106.28, 38.47),
    'N_GANSU': ('甘肃', 103.82, 36.06), 'N_XINJIANG': ('新疆', 87.62, 43.79),
    'N_SHANXI': ('山西', 112.55, 37.87), 'N_YULIN': ('陕西榆林', 109.74, 38.28),
    'N_ORDOS': ('内蒙古鄂尔多斯', 109.78, 39.61), 'N_SHAHE': ('河北沙河', 114.50, 36.86),
    'N_TIANJIN': ('天津', 117.20, 39.13), 'W_SICHUAN': ('四川', 104.07, 30.65),
    'W_CHONGQING': ('重庆', 106.55, 29.56), 'W_ZHONGQING': ('重庆', 106.55, 29.56),
    'W_GUIZHOU': ('贵州', 106.63, 26.65), 'W_YUNNAN': ('云南', 102.71, 25.05),
    'S_GUANGDONG': ('广东', 113.26, 23.13), 'S_FUJIAN': ('福建', 119.30, 26.08),
    'S_HAINAN': ('海南', 110.20, 20.04), 'S_XIAMEN': ('福建厦门', 118.09, 24.48),
    'S_GUANGZHOU': ('广东广州', 113.26, 23.13),
    'NE_HEILONGJIANG': ('黑龙江', 126.53, 45.80), 'NE_LIAONING': ('辽宁', 123.43, 41.80),
    'NE_JILIN': ('吉林', 125.32, 43.90), 'E_HANGZHOU': ('浙江杭州', 120.15, 30.28),
    'H_TONGBAI': ('河南桐柏', 113.42, 32.38), 'H_WUHAN': ('湖北武汉', 114.31, 30.59),
}


def _build_geo(nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    out = {}
    for k, v in nodes.items():
        lon, lat = v.get('lon'), v.get('lat')
        if lon is None or lat is None:
            fb = FALLBACK_GEO.get(k)
            if fb:
                lon, lat = fb[1], fb[2]
                v = dict(v)
                v.setdefault('name', fb[0])
        if lon is not None and lat is not None:
            out[k] = {'name': v.get('name') or k, 'lon': lon, 'lat': lat}
    return out


def build_html(result: Dict[str, Any], out_path: str, background: Dict[str, Any] | None = None,
               title: str = '异常区域价差扫描报告',
               subtitle: str = '') -> str:
    """把 run_scan() 的结果渲染成自包含 HTML。"""
    data = dict(result)
    data['background'] = background or {}
    for g in data.get('gaps', []):
        g.setdefault('gap_zh', g.get('gap'))

    # 地区节点坐标（用于地图），来自 distances.json
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    nodes = {}
    dp = os.path.join(here, 'data_raw', 'distances.json')
    if os.path.exists(dp):
        dj = json.load(open(dp, encoding='utf-8'))
        for n in dj.get('nodes', []):
            nodes[n['code']] = {'name': n.get('name', n['code']), 'lon': n.get('lon'), 'lat': n.get('lat')}
    for c in data.get('combinations', []):
        for k, kk in (('base', 'base_region'), ('quote', 'quote_region')):
            nodes.setdefault(c[k], {'name': c[kk], 'lon': None, 'lat': None})

    if not subtitle:
        s = result.get('summary', {})
        subtitle = '产品池：%s ｜ 数据截止 %s ｜ 可比组合 %d 个 ｜ 数据缺口 %d 项' % (
            ' / '.join(p['product'] for p in result['products'].values()),
            s.get('asof') or '—', s.get('n_combinations', 0), s.get('n_gaps', 0))

    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    geo = json.dumps(_build_geo(nodes), ensure_ascii=False, separators=(',', ':'))

    html_txt = (TEMPLATE
                .replace('__TITLE__', html.escape(title))
                .replace('__SUBTITLE__', html.escape(subtitle))
                .replace('__DATA__', blob)
                .replace('__GEO__', geo))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_txt)
    return out_path


if __name__ == '__main__':
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = src or os.path.join(here, 'outputs', 'scan_result.json')
    res = json.load(open(src, encoding='utf-8'))
    bg_p = os.path.join(here, 'data_raw', 'background.json')
    bg = json.load(open(bg_p, encoding='utf-8')) if os.path.exists(bg_p) else {}
    out = os.path.join(here, 'outputs', '区域价差扫描报告.html')
    print(build_html(res, out, bg))
