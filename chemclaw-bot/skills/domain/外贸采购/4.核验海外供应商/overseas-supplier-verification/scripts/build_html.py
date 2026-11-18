# -*- coding: utf-8 -*-
"""
build_html.py — render a self-contained interactive verification dossier.

Usage:
    python scripts/build_html.py project.json -o out/
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime

import ovslib as L
from ovslib import esc

CSS = r"""
:root{
  --ink:#0e1726; --ink2:#33415c; --mute:#6b7a90; --line:#e3e8ef; --line2:#eef2f7;
  --bg:#f5f7fa; --card:#ffffff; --brand:#0f4c81; --brand2:#1b6ca8; --brandsoft:#eaf2f9;
  --ok:#0f7b53; --okbg:#e6f5ee; --warn:#a15c00; --warnbg:#fdf1dd;
  --mid:#5b6472; --midbg:#eef1f5; --mutebg:#f3f5f8;
  --red:#b3261e; --redbg:#fdecea;
  --r:14px; --sh:0 1px 2px rgba(16,24,40,.04),0 8px 24px -12px rgba(16,24,40,.18);
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
  --mono:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.65 var(--font);-webkit-font-smoothing:antialiased}
a{color:var(--brand2);text-decoration:none}
a:hover{text-decoration:underline}
code,.mono{font-family:var(--mono);font-size:12.5px}
.wrap{display:grid;grid-template-columns:266px minmax(0,1fr);gap:28px;max-width:1480px;margin:0 auto;padding:0 28px}

/* ---------------- hero ---------------- */
.hero{position:relative;overflow:hidden;color:#fff;background:
  radial-gradient(1100px 420px at 12% -10%,rgba(103,196,255,.34),transparent 60%),
  radial-gradient(900px 380px at 92% 0%,rgba(120,220,190,.20),transparent 55%),
  linear-gradient(135deg,#08243c 0%,#0f4c81 52%,#12587f 100%)}
.hero-in{max-width:1480px;margin:0 auto;padding:40px 28px 34px}
.hero .eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#bfe0f5;font-weight:600}
.dot{width:7px;height:7px;border-radius:50%;background:#5eead4;box-shadow:0 0 0 4px rgba(94,234,212,.18)}
.hero h1{margin:12px 0 8px;font-size:31px;line-height:1.28;font-weight:700;letter-spacing:-.01em}
.hero .sub{color:#cfe2f2;max-width:940px;font-size:14.5px}
.chips{display:flex;flex-wrap:wrap;gap:9px;margin-top:20px}
.chip{display:inline-flex;gap:8px;align-items:center;padding:7px 13px;border-radius:999px;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.20);font-size:12.5px;color:#eaf4fc;backdrop-filter:blur(4px)}
.chip b{color:#fff;font-weight:600}
.hero-grid{display:flex;flex-wrap:wrap;gap:14px;margin-top:24px}
.kpi{flex:1 1 190px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);border-radius:12px;padding:13px 15px}
.kpi .n{font-size:23px;font-weight:700;letter-spacing:-.01em}
.kpi .l{font-size:12px;color:#c7dcf0;margin-top:2px}
.kpi.warn .n{color:#ffd79a}.kpi.bad .n{color:#ffb3ab}.kpi.good .n{color:#9ff0cd}

/* ---------------- sidebar ---------------- */
.side{position:sticky;top:0;align-self:start;height:100vh;overflow:auto;padding:22px 0 40px}
.side h4{margin:0 0 10px;font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute);font-weight:700}
.side nav{display:flex;flex-direction:column;gap:2px}
.side nav a{display:flex;gap:10px;align-items:baseline;padding:7px 11px;border-radius:9px;color:var(--ink2);font-size:13.2px;line-height:1.4}
.side nav a:hover{background:#fff;text-decoration:none}
.side nav a.on{background:#fff;color:var(--brand);font-weight:600;box-shadow:var(--sh)}
.side nav a i{font-style:normal;font-family:var(--mono);font-size:11px;color:var(--mute);min-width:18px}
.sidebox{margin-top:20px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 14px;box-shadow:var(--sh)}
.sidebox .t{font-size:12px;font-weight:700;color:var(--ink2);margin-bottom:8px}
.tally{display:flex;flex-direction:column;gap:6px}
.tally button{all:unset;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:8px;padding:5px 8px;border-radius:8px;font-size:12.5px}
.tally button:hover{background:var(--line2)}
.tally button .num{font-family:var(--mono);font-weight:700}
.flt{margin-top:16px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px;box-shadow:var(--sh)}
.flt .t{font-size:12px;font-weight:700;color:var(--ink2);margin-bottom:8px;display:flex;justify-content:space-between}
.flt .t a{font-size:11.5px;font-weight:500}
.fbtns{display:flex;flex-wrap:wrap;gap:6px}
.fbtn{all:unset;cursor:pointer;padding:5px 10px;border-radius:999px;border:1px solid var(--line);font-size:12px;color:var(--ink2);background:#fff;transition:.15s}
.fbtn:hover{border-color:var(--brand2);color:var(--brand2)}
.fbtn.on{background:var(--brand);border-color:var(--brand);color:#fff}

/* ---------------- sections ---------------- */
main{padding:26px 0 90px;min-width:0}
.sec{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--sh);padding:26px 28px;margin-bottom:22px;scroll-margin-top:16px}
.sec-h{display:flex;gap:14px;align-items:flex-start;border-bottom:1px solid var(--line2);padding-bottom:14px;margin-bottom:20px}
.sec-no{flex:none;width:42px;height:42px;border-radius:11px;display:grid;place-items:center;font-family:var(--mono);font-weight:700;color:#fff;background:linear-gradient(135deg,#0f4c81,#2a7fb8);font-size:15px}
.sec-h h2{margin:0;font-size:20px;letter-spacing:-.01em}
.sec-h .s{color:var(--mute);font-size:13px;margin-top:2px}
.sec-h .st{margin-left:auto;flex:none}

/* ---------------- blocks ---------------- */
.verdict{border:1px solid #cfe3f2;background:linear-gradient(180deg,#f6fbff,#fff);border-radius:12px;padding:19px 20px;margin-bottom:18px}
.verdict .k{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--brand2);font-weight:700}
.verdict h3{margin:7px 0 9px;font-size:19px;line-height:1.4}
.verdict p{margin:0;color:var(--ink2)}
.vrows{margin-top:14px;display:grid;gap:6px}
.vrows .r{display:flex;gap:12px;font-size:13px;padding:7px 10px;background:#fff;border:1px solid var(--line2);border-radius:8px}
.vrows .r .kk{color:var(--mute);min-width:110px;flex:none}
.vrows .r .vv{color:var(--ink)}

.lead{display:flex;gap:12px;background:var(--brandsoft);border:1px solid #cfe3f2;border-left:4px solid var(--brand2);border-radius:10px;padding:14px 16px;margin:14px 0;color:#173a56}
.lead::before{content:"i";flex:none;width:20px;height:20px;border-radius:50%;background:var(--brand2);color:#fff;font-weight:700;font-size:12px;display:grid;place-items:center;margin-top:3px}
.lead.muted{background:var(--mutebg);border-color:var(--line);border-left-color:#94a3b8;color:var(--ink2)}
.lead.muted::before{background:#94a3b8}

.note{display:flex;gap:11px;border-radius:10px;padding:12px 15px;margin:14px 0;background:var(--mutebg);border:1px solid var(--line);color:var(--ink2);font-size:13.3px}
.note::before{content:"※";color:var(--mute);font-weight:700}
.note.warn{background:var(--warnbg);border-color:#f3dcb4;color:#6b3d00}
.note.warn::before{content:"!";width:18px;height:18px;border-radius:50%;background:var(--warn);color:#fff;display:grid;place-items:center;font-size:12px;flex:none}

h3.bt{font-size:14.5px;margin:20px 0 10px;display:flex;align-items:center;gap:9px}
h3.bt::before{content:"";width:4px;height:15px;border-radius:2px;background:var(--brand2)}

/* table */
.tbl-wrap{overflow:auto;border:1px solid var(--line);border-radius:11px;margin:10px 0 6px}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;background:#fff}
thead th{position:sticky;top:0;background:#f8fafc;color:var(--ink2);font-weight:700;font-size:12.2px;text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap;z-index:1}
tbody td{padding:10px 12px;border-bottom:1px solid var(--line2);vertical-align:top}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:#fbfdff}
tbody td:first-child{color:var(--ink2);font-weight:600}
.tbl-foot{font-size:12.3px;color:var(--mute);margin:6px 0 16px}
td.c{text-align:center}td.r{text-align:right}

/* pills */
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap;border:1px solid transparent;cursor:default}
.pill::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.85}
.p-ok{background:var(--okbg);color:var(--ok);border-color:#c9ead9}
.p-warn{background:var(--warnbg);color:var(--warn);border-color:#f2dcb6}
.p-mid{background:var(--midbg);color:var(--mid);border-color:#dde2e9}
.p-mute{background:var(--mutebg);color:var(--mute);border-color:#e2e6ec}
.pill.lg{padding:5px 12px;font-size:12.5px}

/* evidence chips */
.ev{display:inline-flex;align-items:center;gap:4px;font-family:var(--mono);font-size:11.5px;font-weight:700;color:#0b5f8a;background:#e8f4fb;border:1px solid #c6e2f2;border-radius:6px;padding:1px 7px;cursor:pointer;margin:1px 2px 1px 0;transition:.15s}
.ev:hover{background:#d3ebfa}
.ev.mock{color:#8a3bb5;background:#f4ebfa;border-color:#e3cdf3}
.ev.sel{outline:2px solid #0b5f8a;outline-offset:1px}
.trunc{display:inline-block;max-width:430px;vertical-align:bottom;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* cards */
.grid{display:grid;gap:14px}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
.card{border:1px solid var(--line);border-radius:12px;padding:15px 16px;background:#fff}
.card h4{margin:0 0 7px;font-size:13.6px}
.card p{margin:0;color:var(--ink2);font-size:13px}
.bound{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:14px 0}
.bound .b{border:1px solid var(--line);border-radius:12px;padding:14px;background:#fff;position:relative;overflow:hidden}
.bound .b::after{content:"";position:absolute;left:0;top:0;bottom:0;width:4px}
.bound .b:nth-child(1)::after{background:var(--ok)}
.bound .b:nth-child(2)::after{background:var(--mid)}
.bound .b:nth-child(3)::after{background:var(--warn)}
.bound .b:nth-child(4)::after{background:var(--mute)}
.bound .b:nth-child(5)::after{background:#cfd6df}
.bound .t{font-weight:700;font-size:13.4px;margin-bottom:5px}
.bound .d{font-size:12.5px;color:var(--ink2);line-height:1.6}

/* hierarchy */
.hier{display:flex;flex-direction:column;gap:10px;margin:12px 0 4px}
.hlayer{display:grid;grid-template-columns:96px 1fr;gap:12px;align-items:stretch}
.hlayer .lab{display:grid;place-items:center;font-size:12.3px;font-weight:700;color:var(--brand);background:var(--brandsoft);border:1px solid #cfe3f2;border-radius:10px}
.hnodes{display:flex;flex-wrap:wrap;gap:8px}
.hnode{flex:1 1 200px;border:1px solid var(--line);border-radius:10px;padding:9px 12px;font-size:12.8px;background:#fff}
.hnode.contract{border-color:#f0c9a0;background:#fffaf3}
.arrowdown{height:14px;display:flex;justify-content:center}
.arrowdown span{width:2px;background:linear-gradient(#cfd8e3,transparent)}

/* chain */
.chain{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
.chain .n{flex:1 1 168px;border:1px solid var(--line);border-radius:12px;padding:13px;background:#fff;position:relative}
.chain .n .code{font-family:var(--mono);font-weight:700;color:var(--brand2);font-size:12px}
.chain .n .nm{font-weight:700;margin:3px 0 4px;font-size:13.4px}
.chain .n .rl{font-size:12.3px;color:var(--ink2)}
.chain .n.self{border-color:#9fc9e6;background:#f7fbff}
.chain .arrow{align-self:center;color:#b9c4d2;font-size:16px}

/* matrix_map */
.mmap{display:flex;flex-direction:column;gap:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:12px 0}
.mmap .hd,.mmap .rw{display:grid;grid-template-columns:1.05fr 1.05fr 1.35fr 1.15fr 104px 1.5fr;gap:0}
.mmap .hd>div{background:#f8fafc;font-size:12px;font-weight:700;color:var(--ink2);padding:10px 12px;border-bottom:1px solid var(--line)}
.mmap .rw>div{padding:11px 12px;border-bottom:1px solid var(--line2);font-size:12.7px;background:#fff;display:flex;align-items:center}
.mmap .rw:last-child>div{border-bottom:none}
.mmap .rw>div:first-child{font-weight:600;color:var(--ink2);background:#fcfdfe}
.mmap .rw.conflict>div:not(:first-child):not(.st){background:#fff8f6}
.mmap .k{color:var(--ink2)}
.mmap .hi{color:var(--red);font-weight:700}

/* steps */
.steps{display:flex;flex-direction:column;gap:10px;margin:12px 0}
.step{display:grid;grid-template-columns:34px 1fr;gap:12px;border:1px solid var(--line);border-radius:11px;padding:12px 14px;background:#fff}
.step .n{width:26px;height:26px;border-radius:8px;background:var(--brand);color:#fff;display:grid;place-items:center;font-weight:700;font-size:13px}
.step .t{font-weight:700;font-size:13.4px}
.step .d{font-size:12.6px;color:var(--ink2)}

/* risks */
.rk{border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:10px;padding:12px 15px;margin:9px 0;background:#fff}
.rk .t{font-weight:700;font-size:13.4px;margin-bottom:3px}
.rk .d{font-size:12.7px;color:var(--ink2)}

/* timeline */
.tl{position:relative;margin:16px 0 6px;padding-left:8px}
.tl::before{content:"";position:absolute;left:74px;top:4px;bottom:4px;width:2px;background:linear-gradient(#cfe3f2,#eef2f7)}
.tl .it{display:grid;grid-template-columns:66px 22px 1fr;gap:10px;margin-bottom:12px;align-items:start}
.tl .dt{font-family:var(--mono);font-size:11.8px;color:var(--mute);text-align:right;padding-top:2px}
.tl .pt{width:11px;height:11px;border-radius:50%;background:#fff;border:2px solid var(--brand2);margin-left:4px;margin-top:6px;z-index:1}
.tl .tx{font-size:13px;color:var(--ink2)}
.tl .it.supply .pt{border-color:var(--warn)}
.tl .it.trade .pt{border-color:#7a4bc4}
.tl .it.meta .pt{border-color:#94a3b8}

/* tags */
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:5px;background:var(--mutebg);color:var(--mute);margin-left:6px;font-weight:600}
.tag.hi{background:var(--redbg);color:var(--red)}

/* evidence index */
.evidx{display:flex;flex-direction:column;gap:9px}
.evi{border:1px solid var(--line);border-radius:11px;padding:12px 14px;background:#fff;scroll-margin-top:20px}
.evi.sel{border-color:#0b5f8a;box-shadow:0 0 0 3px rgba(11,95,138,.12)}
.evi .top{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:5px}
.evi .id{font-family:var(--mono);font-weight:800;color:#0b5f8a;background:#e8f4fb;border:1px solid #c6e2f2;border-radius:6px;padding:1px 7px;font-size:11.5px}
.evi .pub{font-size:12px;color:var(--mute)}
.evi .cl{font-size:13px;color:var(--ink);margin:3px 0 6px}
.evi blockquote{margin:6px 0 8px;padding:8px 12px;border-left:3px solid #cfe3f2;background:#f8fbfe;color:var(--ink2);font-size:12.4px;line-height:1.6}
.evi .meta{font-size:11.8px;color:var(--mute);display:flex;gap:14px;flex-wrap:wrap}
.mockband{display:inline-flex;align-items:center;gap:6px;background:#f4ebfa;color:#8a3bb5;border:1px dashed #d8bdee;border-radius:6px;padding:1px 8px;font-size:11.5px;font-weight:700}

/* RFI */
.rfi{background:#fbfcfe;border:1px solid var(--line);border-radius:12px;padding:18px 20px;font-size:13px}
.rfi .rh{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:12px}
.rfi .rh .t{font-weight:700;font-size:14px}
.rfi ol{padding-left:20px;margin:0}
.rfi li{margin:7px 0;color:var(--ink2);line-height:1.6}
.rfi .ref{font-family:var(--mono);font-size:12px;color:var(--brand2)}

/* toolbar */
.toolbar{position:fixed;right:26px;bottom:26px;display:flex;flex-direction:column;gap:9px;z-index:40}
.toolbar button{all:unset;cursor:pointer;width:44px;height:44px;border-radius:12px;background:#fff;border:1px solid var(--line);box-shadow:var(--sh);display:grid;place-items:center;font-size:15px;color:var(--ink2)}
.toolbar button:hover{color:var(--brand2);border-color:#bfd8ea}

/* drawer */
.drawer{position:fixed;inset:0;background:rgba(14,23,38,.34);opacity:0;pointer-events:none;transition:.2s;z-index:60}
.drawer.open{opacity:1;pointer-events:auto}
.drawer .panel{position:absolute;right:0;top:0;bottom:0;width:min(560px,92vw);background:#fff;box-shadow:-20px 0 60px rgba(16,24,40,.18);transform:translateX(24px);transition:.22s;display:flex;flex-direction:column}
.drawer.open .panel{transform:none}
.drawer .dph{display:flex;align-items:center;gap:10px;padding:16px 18px;border-bottom:1px solid var(--line)}
.drawer .dph .id{font-family:var(--mono);font-weight:800;color:#0b5f8a;background:#e8f4fb;border-radius:7px;padding:3px 9px}
.drawer .dph button{all:unset;cursor:pointer;margin-left:auto;font-size:20px;color:var(--mute);line-height:1}
.drawer .dpb{padding:18px;overflow:auto}
.drawer .dpb h5{margin:14px 0 5px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
.drawer .dpb p{margin:0 0 10px;font-size:13.2px;color:var(--ink2)}
.drawer .dpb blockquote{margin:0;padding:10px 13px;border-left:3px solid #cfe3f2;background:#f8fbfe;font-size:12.8px;color:var(--ink2)}
.drawer .dpb a.brk{word-break:break-all}

/* misc */
.foot{border-top:1px solid var(--line);margin-top:26px;padding-top:16px;color:var(--mute);font-size:12.3px}
.foot p{margin:5px 0}
.hidden{display:none !important}
.empty{padding:22px;text-align:center;color:var(--mute);border:1px dashed var(--line);border-radius:11px;margin:12px 0}
@media print{
  .side,.toolbar,.drawer,.flt{display:none !important}
  .wrap{display:block;max-width:none;padding:0}
  .sec{break-inside:avoid;box-shadow:none}
  .hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
@media (max-width:1180px){
  .wrap{grid-template-columns:minmax(0,1fr);padding:0 16px}
  .side{position:static;height:auto;padding:16px 0 0}
  .side nav{flex-direction:row;flex-wrap:wrap}
  .bound{grid-template-columns:repeat(2,minmax(0,1fr))}
  .g3,.g4{grid-template-columns:repeat(2,minmax(0,1fr))}
  .mmap .hd,.mmap .rw{grid-template-columns:1fr 1fr}
}
"""

JS = r"""
(function(){
  var state=null, q='';
  function pillClass(s){
    return {verified:'p-ok',doubt:'p-warn',unverified:'p-mid',unknown:'p-mute',na:'p-mute'}[s]||'p-mute';
  }
  function norm(s){
    var m={'已核实':'verified','存在疑点':'doubt','未核实':'unverified','未知':'unknown','不适用':'na',
           'verified':'verified','doubt':'doubt','unverified':'unverified','unknown':'unknown','na':'na'};
    return m[s]||m[(s||'').trim()]||'unknown';
  }
  function apply(){
    document.querySelectorAll('[data-state]').forEach(function(el){
      var s=norm(el.getAttribute('data-state'));
      var ok=(!state||state===s);
      el.classList.toggle('hidden',!ok);
    });
    document.querySelectorAll('tr[data-state]').forEach(function(tr){
      var tbl=tr.closest('table'); if(!tbl) return;
      var rows=tbl.querySelectorAll('tbody tr[data-state]');
      var any=false; rows.forEach(function(r){ if(!r.classList.contains('hidden')) any=true; });
      var empty=tbl.parentElement.querySelector('.empty-row');
      if(empty) empty.classList.toggle('hidden',any);
    });
    document.querySelectorAll('[data-sec]').forEach(function(sec){
      var n=sec.querySelectorAll('tbody tr[data-state]:not(.hidden)').length;
      var secState=sec.getAttribute('data-state');
      if(!state){ sec.classList.remove('hidden'); return; }
      var hasState = secState && norm(secState)===state;
      var hasAny = sec.querySelectorAll('[data-state]:not(.hidden)').length>0;
      sec.classList.toggle('hidden', !(hasState||hasAny||state==='all'));
    });
    document.querySelectorAll('.fbtn').forEach(function(b){
      b.classList.toggle('on',(b.getAttribute('data-state')||'')===(state||''));
    });
  }
  function search(){
    var ql=q.trim().toLowerCase();
    document.querySelectorAll('[data-state]').forEach(function(el){
      if(!ql){ el.classList.remove('q-hide'); return; }
      var hit=el.textContent.toLowerCase().indexOf(ql)>=0;
      el.classList.toggle('q-hide',!hit);
    });
    document.querySelectorAll('[data-state]').forEach(function(el){
      el.classList.toggle('hidden', el.classList.contains('q-hide')||(state && norm(el.getAttribute('data-state'))!==state));
    });
  }
  document.querySelectorAll('.fbtn').forEach(function(b){
    b.addEventListener('click',function(){
      var s=b.getAttribute('data-state')||null;
      state=(state===s)?null:s;
      if(state) document.querySelectorAll('[data-state]').forEach(function(el){el.classList.remove('q-hide');});
      apply();
      if(q) search();
    });
  });
  var si=document.getElementById('q');
  if(si) si.addEventListener('input',function(){ q=si.value; if(!q){document.querySelectorAll('[data-state]').forEach(function(el){el.classList.remove('q-hide')});} apply(); if(q) search(); });
  var clr=document.getElementById('clear-filter');
  if(clr) clr.addEventListener('click',function(){ state=null; q=''; if(si) si.value=''; document.querySelectorAll('[data-state]').forEach(function(el){el.classList.remove('q-hide')}); apply(); });

  // evidence drawer
  var drawer=document.getElementById('drawer');
  function openEv(id){
    var card=document.getElementById('ev-'+id);
    if(!card){ return; }
    var ph=drawer.querySelector('.dph .id'); ph.textContent=id;
    var body=drawer.querySelector('.dpb'); body.innerHTML=card.querySelector('.inner').innerHTML;
    drawer.classList.add('open');
    document.querySelectorAll('.ev').forEach(function(x){ x.classList.toggle('sel', x.getAttribute('data-ev')===id); });
  }
  document.addEventListener('click',function(e){
    var t=e.target.closest('[data-ev]');
    if(t){ e.preventDefault(); openEv(t.getAttribute('data-ev')); return; }
    if(e.target.closest('[data-close]')||e.target===drawer){ drawer.classList.remove('open'); }
  });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape'){ drawer.classList.remove('open'); } });

  // scroll spy
  var links=[].slice.call(document.querySelectorAll('.side nav a'));
  var secs=links.map(function(a){return document.querySelector(a.getAttribute('href'));}).filter(Boolean);
  function spy(){
    var y=window.scrollY+90, cur=secs[0];
    secs.forEach(function(s){ if(s.offsetTop<=y) cur=s; });
    links.forEach(function(a){ a.classList.toggle('on', a.getAttribute('href')==='#'+cur.id); });
  }
  window.addEventListener('scroll',spy,{passive:true}); spy();

  var pa=document.getElementById('print-btn'); if(pa) pa.addEventListener('click',function(){window.print();});
  var to=document.getElementById('top-btn'); if(to) to.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
  var cl=document.getElementById('collapse-btn');
  if(cl) cl.addEventListener('click',function(){
    document.body.classList.toggle('compact');
    document.querySelectorAll('.sec').forEach(function(s,i){ if(i>1) s.classList.toggle('hidden',document.body.classList.contains('compact')); });
  });
  apply();
})();
"""


# ---------------------------------------------------------------- renderers
def pill(state_raw, extra=""):
    s = L.norm_state(state_raw)
    return f'<span class="pill {("p-"+L.STATE[s]["tone"])} {extra}">{L.STATE[s]["zh"]}</span>'


def ev_chips(raw, mock_ids=()):
    ids = L.evid_ids(raw)
    if not ids:
        return '<span class="muted" style="color:var(--mute)">—</span>'
    out = []
    for i in ids:
        cls = "ev mock" if i in mock_ids else "ev"
        out.append(f'<button type="button" class="{cls}" data-ev="{i}" title="查看证据 {i}">{i}</button>')
    return "".join(out)


def r_verdict(b):
    rows = "".join(
        f'<div class="r"><span class="kk">{esc(r.get("k"))}</span><span class="vv">{esc(r.get("v"))}</span></div>'
        for r in L.as_list(b.get("rows")))
    return (f'<div class="verdict"><div class="k">{esc(b.get("kicker",""))}</div>'
            f'<h3>{esc(b.get("headline",""))}</h3><p>{esc(b.get("text",""))}</p>'
            f'<div class="vrows">{rows}</div></div>')


def r_lead(b):
    cls = "lead muted" if b.get("muted") else "lead"
    text = b.get("text", "")
    return f'<div class="{cls}"><div>{text}</div></div>'  # allow inline <b>


def r_note(b):
    cls = "note warn" if b.get("tone") == "warn" else "note"
    return f'<div class="{cls}"><div>{b.get("text","")}</div></div>'


def r_boundary(b):
    cells = "".join(
        f'<div class="b"><div class="t">{esc(x.get("t"))}</div><div class="d">{esc(x.get("d"))}</div></div>'
        for x in L.as_list(b.get("items")))
    foot = f'<div class="tbl-foot">{esc(b.get("foot"))}</div>' if b.get("foot") else ""
    return f'<div class="bound">{cells}</div>{foot}'


def r_table(b, mock_ids=()):
    cols = L.as_list(b.get("columns"))
    n = len(cols)
    th = "".join(
        f'<th style="{("width:"+c.get("width")+";") if c.get("width") else ""}'
        f'{("text-align:center;" if c.get("align")=="c" else "text-align:right;" if c.get("align")=="r" else "")}">'
        f'{esc(c.get("h"))}</th>' for c in cols)
    all_rows = L.as_list(b.get("rows"))
    ragged = any(not isinstance(r, (list, tuple)) or len(r) != n for r in all_rows)
    # 状态列：默认「倒数第二列」，但仅当每行宽度与表头一致时才自动推断，
    # 否则回退为「第 3 列且值确实是状态词」，避免错位。
    state_col = n - 2 if (n >= 3 and not ragged) else None
    body = []
    for row in all_rows:
        if not isinstance(row, (list, tuple)):
            row = [row]
        st = None
        if state_col is not None and len(row) > state_col and L.norm_state(row[state_col], default=None):
            st = row[state_col]
        if st is None:
            for i, v in enumerate(row):
                if i and isinstance(v, str) and L.norm_state(v, default=None):
                    st = v
                    break
        cells = []
        for i, val in enumerate(row):
            align = ""
            if i < n and cols[i].get("align"):
                align = "text-align:center;" if cols[i]["align"] == "c" else "text-align:right;"
            if st is not None and val is st and i > 0:
                cells.append(f'<td class="c">{pill(val)}</td>')
            elif i == n - 1 and n >= 3 and L.evid_ids(val) and st is not None:
                cells.append(f'<td class="c">{ev_chips(val, mock_ids)}</td>')
            elif isinstance(val, str) and val.strip() in ("—", "-", "–", ""):
                cells.append(f'<td class="c" style="color:var(--mute)">—</td>')
            else:
                v = "" if val is None else str(val)
                cells.append(f'<td style="{align}">{esc(v)}</td>')
        ds = L.norm_state(st) if st else ""
        if len(row) < n:
            cells.extend(['<td></td>'] * (n - len(row)))
        body.append(f'<tr data-state="{ds}">' + "".join(cells) + "</tr>")
    title = f'<h3 class="bt">{esc(b.get("title"))}</h3>' if b.get("title") else ""
    warn = ('<div class="note warn"><div>数据表列数与表头不一致，已按原样渲染；'
            '请检查 project.json 中该表的 columns / rows 数量。</div></div>' if ragged else "")
    foot = f'<div class="tbl-foot">{esc(b.get("foot"))}</div>' if b.get("foot") else ""
    return (f'{title}{warn}<div class="tbl-wrap"><table><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table><div class="empty empty-row hidden">当前筛选条件下没有记录</div></div>{foot}')


def r_hierarchy(b):
    layers = []
    for i, lay in enumerate(L.as_list(b.get("layers"))):
        nodes = "".join(f'<div class="hnode">{esc(x)}</div>' for x in L.as_list(lay.get("nodes")))
        layers.append(f'<div class="hlayer"><div class="lab">{esc(lay.get("layer"))}</div><div class="hnodes">{nodes}</div></div>')
        if i < len(b.get("layers")) - 1:
            layers.append('<div class="arrowdown"><span></span></div>')
    title = f'<h3 class="bt">{esc(b.get("title"))}</h3>' if b.get("title") else ""
    note = f'<div class="note"><div>{esc(b.get("note"))}</div></div>' if b.get("note") else ""
    return f'{title}<div class="hier">{"".join(layers)}</div>{note}'


def r_matrix_map(b, mock_ids=()):
    rows = []
    for r in L.as_list(b.get("rows")):
        st = L.norm_state(r.get("state"))
        conflict = " conflict" if st in ("doubt", "unverified") else ""
        a = esc(r.get("a"))
        if r.get("c") and ("不同" in str(r.get("c")) or "不一致" in str(r.get("c")) or "非" in str(r.get("c"))):
            a = f'<span class="hi">{a}</span>'
        ev = ev_chips(r.get("evid"), mock_ids) if r.get("evid") else ""
        note = esc(r.get("note")) + (f'<div style="margin-top:4px">{ev}</div>' if ev else "")
        rows.append(f'<div class="rw{conflict}" data-state="{st}">'
                    f'<div>{esc(r.get("item"))}</div><div>{a}</div>'
                    f'<div class="k">{esc(r.get("b"))}</div><div>{esc(r.get("c"))}</div>'
                    f'<div class="st">{pill(r.get("state"))}</div><div class="k">{note}</div></div>')
    title = f'<h3 class="bt">{esc(b.get("title"))}</h3>' if b.get("title") else ""
    foot = f'<div class="tbl-foot">{esc(b.get("foot"))}</div>' if b.get("foot") else ""
    head = ('<div class="hd"><div>核对项</div><div>交易文件所载</div><div>官方/公开基线</div>'
            '<div>比对判断</div><div>状态</div><div>说明与证据</div></div>')
    return f'{title}<div class="mmap">{head}{"".join(rows)}</div>{foot}'


def r_chain(b):
    items = L.as_list(b.get("items"))
    parts = []
    for i, it in enumerate(items):
        cls = "n self" if it.get("self") else "n"
        parts.append(f'<div class="{cls}"><div class="code">{esc(it.get("code"))}</div>'
                     f'<div class="nm">{esc(it.get("name"))}</div><div class="rl">{esc(it.get("role"))}</div></div>')
        if i < len(items) - 1:
            parts.append('<div class="arrow">→</div>')
    title = f'<h3 class="bt">{esc(b.get("title"))}</h3>' if b.get("title") else ""
    return f'{title}<div class="chain">{"".join(parts)}</div>'


def r_steps(b):
    out = "".join(f'<div class="step"><div class="n">{esc(s.get("n"))}</div><div>'
                  f'<div class="t">{esc(s.get("t"))}</div><div class="d">{esc(s.get("d"))}</div></div></div>'
                  for s in L.as_list(b.get("items")))
    return f'<div class="steps">{out}</div>'


def r_risknotes(b):
    out = "".join(f'<div class="rk" data-state="doubt"><div class="t">{esc(x.get("t"))}</div>'
                  f'<div class="d">{esc(x.get("d"))}</div></div>' for x in L.as_list(b.get("items")))
    return out


def r_timeline(b):
    out = "".join(
        f'<div class="it {esc(x.get("tag",""))}"><div class="dt">{esc(x.get("date"))}</div>'
        f'<div class="pt"></div><div class="tx">{esc(x.get("event"))}'
        f'{(" "+ev_chips(x.get("evid"))) if x.get("evid") and x.get("evid")!="—" else ""}</div></div>'
        for x in L.as_list(b.get("items")))
    title = f'<h3 class="bt">{esc(b.get("title"))}</h3>' if b.get("title") else ""
    return f'{title}<div class="tl">{out}</div>'


def r_grid(b):
    cards = "".join(f'<div class="card"><h4>{esc(c.get("h"))}</h4><p>{esc(c.get("text"))}</p></div>'
                    for c in L.as_list(b.get("cards")))
    return f'<div class="grid g2">{cards}</div>'


BLOCKERS = {
    "verdict": r_verdict, "lead": r_lead, "note": r_note, "boundary": r_boundary,
    "table": r_table, "hierarchy": r_hierarchy, "matrix_map": r_matrix_map,
    "chain": r_chain, "steps": r_steps, "risknotes": r_risknotes,
    "timeline": r_timeline, "grid": r_grid,
}

MATRIX_TYPES = {"matrix_map"}


def render_section(sec, mock_ids):
    blocks = []
    for b in L.as_list(sec.get("blocks")):
        fn = BLOCKERS.get(b.get("type"))
        if not fn:
            blocks.append(f'<div class="note warn"><div>未知区块类型：{esc(b.get("type"))}</div></div>')
            continue
        if b.get("type") in MATRIX_TYPES:
            blocks.append(fn(b, mock_ids))
        else:
            blocks.append(fn(b))
    counts = [r[2] for r in L.as_list(sec.get("_rows_state"))]
    return (f'<section class="sec" id="{esc(sec.get("id"))}">'
            f'<div class="sec-h"><div class="sec-no">{esc(sec.get("no"))}</div>'
            f'<div><h2>{esc(sec.get("title"))}</h2><div class="s">{esc(sec.get("sub"))}</div></div></div>'
            f'{"".join(blocks)}</section>')


def render_evidence(evidence, mock_ids):
    cards = []
    for e in evidence:
        eid = esc(e.get("id"))
        grade = L.EVID_GRADE.get(e.get("grade"), L.EVID_GRADE["tertiary"])
        stance = L.EVID_STANCE.get(e.get("stance"), L.EVID_STANCE["context"])
        mockband = '<span class="mockband">模拟件 · 非真实文件</span>' if e.get("grade") == "mock" else ""
        url = e.get("url") or ""
        inner = (f'<div class="top"><span class="id">{eid}</span>'
                 f'<span class="pill {"p-ok" if e.get("grade")=="primary" else "p-mute"}">{esc(grade["zh"])}</span>'
                 f'<span class="pill p-mute">{esc(stance["zh"])}</span>{mockband}'
                 f'<span class="pub">{esc(e.get("publisher"))}</span></div>'
                 f'<div class="cl">{esc(e.get("claim"))}</div>'
                 f'<blockquote>{esc(e.get("quote"))}</blockquote>'
                 f'<div class="meta"><span>发布：{esc(e.get("published") or "—")}</span>'
                 f'<span>访问：{esc(e.get("accessed") or "—")}</span>'
                 f'<span>用途：{esc(e.get("used_for") or "—")}</span></div>'
                 f'{f"<p style=\"margin:6px 0 0\"><a class=\"brk\" href=\"{esc(url)}\" target=\"_blank\" rel=\"noopener\">{esc(url)}</a></p>" if url else ""}'
                 f'{f"<p style=\"margin:6px 0 0;color:#8a3bb5\">注：{esc(e.get("note"))}</p>" if e.get("note") else ""}')
        cards.append(f'<div class="evi" id="ev-{eid}"><div class="inner">{inner}</div>'
                     f'<div style="margin-top:8px"><a href="#{eid}" class="ev" data-ev="{eid}">在抽屉中打开</a>'
                     f'<span style="font-size:11.5px;color:var(--mute);margin-left:8px">锚点 #{eid}</span></div></div>')
    return "".join(cards)


def render_entity(project):
    rows = L.as_list(project.get("entity_map"))
    if not rows:
        return ""
    body = "".join(
        f'<tr data-state="{L.norm_state(r.get("state"))}">'
        f'<td>{esc(r.get("layer"))}</td><td>{esc(L.LAYER_ZH.get(r.get("kind"), r.get("kind")))}</td>'
        f'<td>{esc(r.get("entity"))}</td><td>{esc(r.get("jurisdiction"))}</td>'
        f'<td class="c">{pill(r.get("state"))}</td><td class="c">{ev_chips(r.get("evidence"))}</td>'
        f'<td>{esc(r.get("note"))}</td></tr>' for r in rows)
    return ('<section class="sec" id="entity_map"><div class="sec-h"><div class="sec-no">EM</div>'
            '<div><h2>主体映射表</h2><div class="s">先分清「集团 / 生产 / 交易 / 收款」四层主体，再谈核验</div></div></div>'
            '<div class="note"><div>同一集团内不同法人不能混用：产能在 A 公司、合同签在 B 公司、钱付给 C 公司，'
            '三件事必须都能用文件对上。下表是本次核验涉及的全部主体，状态可随证据更新。</div></div>'
            '<div class="tbl-wrap"><table><thead><tr><th>层级</th><th>角色</th><th>主体名称</th><th>注册地</th>'
            '<th class="c">状态</th><th class="c">证据</th><th>说明</th></tr></thead><tbody>'
            f'{body}</tbody></table></div></section>')


def render_gaps(project):
    gaps = L.as_list(project.get("gaps"))
    if not gaps:
        return ""
    body = "".join(
        f'<tr data-state="{L.norm_state("unknown" if g.get("priority")=="高" else "unverified")}">'
        f'<td>{esc(g.get("id"))}</td><td>{esc(g.get("area"))}</td><td>{esc(g.get("gap"))}</td>'
        f'<td>{esc(g.get("impact"))}</td><td>{esc(g.get("action"))}</td>'
        f'<td class="c">{pill("unknown")}</td><td>{esc(g.get("owner"))}</td>'
        f'<td class="c">{esc(g.get("priority"))}</td></tr>' for g in gaps)
    return ('<section class="sec" id="gaps"><div class="sec-h"><div class="sec-no">G</div>'
            '<div><h2>待确认事项（Gap Register）</h2><div class="s">每一个「未知」都要落到一个人、一个动作、一个期限</div></div></div>'
            '<div class="tbl-wrap"><table><thead><tr><th>编号</th><th>领域</th><th>缺口</th><th>影响</th>'
            '<th>补证动作</th><th class="c">状态</th><th>责任人</th><th class="c">优先级</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></section>')


def render_docs(project):
    docs = L.as_list(project.get("documents"))
    if not docs:
        return ""
    rows = []
    for d in docs:
        s = L.doc_check_summary(d)
        st = L.derive_doc_state(d)
        badge = '<span class="mockband">模拟</span>' if d.get("mock") else ""
        checks = "".join(
            f'<div style="font-size:12.3px;margin:2px 0"><span style="color:{"var(--ok)" if c.get("ok") else "var(--red)"}">'
            f'{"✓" if c.get("ok") else "✕"}</span> {esc(c.get("k"))}：{esc(c.get("v"))}</div>'
            for c in L.as_list(d.get("checks")))
        rows.append(f'<tr data-state="{st}"><td>{esc(d.get("id"))}</td>'
                    f'<td>{esc(d.get("name"))} {badge}</td><td>{esc(d.get("holder"))}</td>'
                    f'<td class="c">{s["ok"]}/{s["total"] if s["total"] else "—"}</td>'
                    f'<td class="c">{pill(st)}</td>'
                    f'<td>{checks or "<span style=\'color:var(--mute)\'>未提供 / 待索取</span>"}</td></tr>')
    return ('<section class="sec" id="docs"><div class="sec-h"><div class="sec-no">DC</div>'
            '<div><h2>文件核验明细</h2><div class="s">逐件核到要素级：谁出的、能不能对主体、缺哪一项</div></div></div>'
            '<div class="tbl-wrap"><table><thead><tr><th style="width:52px">编号</th><th style="width:170px">文件</th>'
            '<th style="width:150px">名义持有人</th><th class="c" style="width:88px">检查通过</th>'
            '<th class="c" style="width:92px">状态</th><th>逐项检查</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            '<div class="note warn"><div>凡标有「模拟」的文件均为演示用虚构样本，不代表任何真实企业曾向我方报价、'
            '出具或签署任何文件。</div></div></section>')


def render_rfi(project):
    rfi = project.get("rfi")
    if not rfi:
        return ""
    items = "".join(f'<li><b class="ref">{esc(c.get("id"))}</b> — {esc(c.get("text"))}</li>'
                    for c in L.as_list(rfi.get("clauses")))
    return ('<section class="sec" id="rfi"><div class="sec-h"><div class="sec-no">RFI</div>'
            '<div><h2>英文供应商询证清单</h2><div class="s">可直接复制发送；要求对方以公司抬头纸、有权签署人回函</div></div></div>'
            f'<div class="rfi"><div class="rh"><div><div class="t">{esc(rfi.get("title"))}</div>'
            f'<div class="ref">Ref: {esc(rfi.get("ref"))}</div></div>'
            f'<div style="font-size:12.5px;color:var(--ink2);text-align:right">To: {esc(rfi.get("to"))}<br>'
            f'From: {esc(rfi.get("from"))}<br>Date: {esc(rfi.get("date"))}</div></div>'
            f'<p style="color:var(--ink2)">{esc(rfi.get("intro"))}</p><ol>{items}</ol></div></section>')


def render_timeline_section(project):
    tl = L.as_list(project.get("timeline"))
    if not tl:
        return ""
    return ('<section class="sec" id="timeline"><div class="sec-h"><div class="sec-no">TL</div>'
            '<div><h2>公开事件时间轴</h2><div class="s">只看与「主体 / 生产 / 供应 / 贸易救济」相关的事件</div></div></div>'
            + r_timeline({"title": "", "items": tl}) + '</section>')


def render_evidence_section(evidence):
    return ('<section class="sec" id="evidence"><div class="sec-h"><div class="sec-no">EV</div>'
            '<div><h2>证据索引</h2><div class="s">每条结论都可回溯：来源、发布时间、访问时间、原文摘录、用途与局限</div></div></div>'
            '<div class="note"><div>证据分级：<b>一手/官方</b>（政府登记、监管披露、官网原件）＞ <b>二手/媒体</b>（行业协会、数据库、财经媒体）'
            '＞ <b>三手/百科</b>。只有一手来源可直接支撑「已核实」，二手来源需两个以上独立来源交叉印证。'
            '标紫色的为模拟件。</div></div>'
            f'<div class="evidx">{render_evidence(evidence, ())}</div></section>')


def build(project: dict) -> str:
    meta = project.get("meta", {})
    summary = project.get("summary", {})
    evidence = L.as_list(project.get("evidence"))
    mock_ids = {e.get("id") for e in evidence if e.get("grade") == "mock"}

    carriers = list(L.iter_state_carriers(project))
    counts = L.count_states(carriers)

    # 侧栏目录
    nav = [f'<a href="#{esc(s.get("id"))}"><i>{esc(s.get("no"))}</i><span>{esc(s.get("title"))}</span></a>'
           for s in L.as_list(project.get("sections"))]
    for sid, label in (("entity_map", "主体映射表"), ("docs", "文件核验明细"), ("gaps", "待确认事项"),
                       ("timeline", "公开事件时间轴"), ("evidence", "证据索引"), ("rfi", "英文询证清单")):
        nav.append(f'<a href="#{sid}"><i>•</i><span>{label}</span></a>')

    tally = "".join(
        f'<button type="button" onclick=""><span class="pill {"p-"+L.STATE[k]["tone"]}">{L.STATE[k]["zh"]}</span>'
        f'<span class="num">{counts[k]}</span></button>' for k in L.STATE_ORDER)

    verdict = L.VERDICT.get(summary.get("verdict"), L.VERDICT["insufficient"])

    kpis = "".join(
        f'<div class="kpi {tone}"><div class="n">{esc(value)}</div><div class="l">{esc(label)}</div></div>'
        for value, label, tone in [
            (counts["verified"], "已核实项", "good"),
            (counts["doubt"], "存在疑点", "warn"),
            (counts["unknown"] + counts["unverified"], "未知/未核实", "bad"),
            (len(evidence), "证据条目", ""),
            (len(L.as_list(project.get("gaps"))), "待确认缺口", ""),
        ])

    chips = "".join(f'<span class="chip"><span>{esc(k)}</span><b>{esc(v)}</b></span>' for k, v in [
        ("核验基准日", meta.get("as_of")), ("采购品", meta.get("product")),
        ("国家/地区", meta.get("country")), ("结论", verdict["zh"]),
        ("报告编号", meta.get("doc_no")),
    ] if v)

    secs_html = "".join(render_section(s, mock_ids) for s in L.as_list(project.get("sections")))
    body = (secs_html + render_entity(project) + render_docs(project) + render_gaps(project)
            + render_timeline_section(project) + render_evidence_section(evidence) + render_rfi(project))

    intro = f'<section class="sec" id="summary"><div class="sec-h"><div class="sec-no">★</div><div><h2>核验结论摘要</h2><div class="s">先看这一段，再决定要不要读后面的证据</div></div></div>'
    intro += (f'<div class="verdict"><div class="k">结论口径 · {esc(verdict["zh"])}</div>'
              f'<h3>{esc(summary.get("headline"))}</h3><p>{esc(summary.get("text"))}</p>'
              f'<div class="tbl-foot" style="margin:9px 0 0">该结论的含义：{esc(verdict["desc"])}</div></div>')
    kf = "".join(f'<div class="rk" style="border-left-color:#0f7b53"><div class="d">{esc(x)}</div></div>'
                 for x in L.as_list(summary.get("key_findings")))
    nc = "".join(f'<li>{esc(x)}</li>' for x in L.as_list(summary.get("not_concluded")))
    intro += f'<h3 class="bt">已确认的关键事实</h3>{kf}'
    intro += (f'<h3 class="bt">本报告明确不下的结论</h3><div class="note warn"><div><ul style="margin:0;padding-left:18px">{nc}</ul></div></div>')
    intro += '</section>'

    drawer = ('<div class="drawer" id="drawer"><div class="panel">'
              '<div class="dph"><span class="id">EV</span><span>证据详情</span>'
              '<button type="button" data-close="1" aria-label="关闭">×</button></div>'
              '<div class="dpb"></div></div></div>')

    page_title = meta.get("page_title") or "海外供应商核验报告"
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(page_title)}</title>
<style>{CSS}</style></head>
<body>
<header class="hero"><div class="hero-in">
  <span class="eyebrow"><span class="dot"></span>Overseas Supplier Verification · 公开信息核验</span>
  <h1>{esc(meta.get("title"))}<br><span style="font-size:17px;font-weight:500;color:#bfe0f5">{esc(meta.get("subject_full"))}</span></h1>
  <div class="sub">{esc(meta.get("disclaimer"))}</div>
  <div class="chips">{chips}</div>
  <div class="hero-grid">{kpis}</div>
</div></header>
<div class="wrap">
  <aside class="side">
    <h4>报告导航</h4>
    <nav>{''.join(nav)}</nav>
    <div class="sidebox"><div class="t">状态分布（点击筛选）</div><div class="tally">{tally}</div></div>
    <div class="flt">
      <div class="t"><span>筛选结论</span><a href="#" id="clear-filter">清空</a></div>
      <div class="fbtns">
        <button class="fbtn" data-state="verified">已核实</button>
        <button class="fbtn" data-state="doubt">存在疑点</button>
        <button class="fbtn" data-state="unverified">未核实</button>
        <button class="fbtn" data-state="unknown">未知</button>
      </div>
      <div style="margin-top:10px"><input id="q" placeholder="在本页内搜索…" style="width:100%;padding:7px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;font-size:12.6px;outline:none"></div>
    </div>
  </aside>
  <main>
    {intro}
    {body}
    <div class="foot">
      <p>{esc(meta.get("doc_no"))} · {esc(meta.get("title"))} · 基准日 {esc(meta.get("as_of"))} · {esc(meta.get("version"))}</p>
      <p>编制：{esc(meta.get("author"))} ｜ 复核：{esc(meta.get("reviewer"))}</p>
      <p>本文件由 overseas-supplier-verification Skill 生成；不提供风险评分，不替代法律、审计或信用调查意见。所有「未知」均可补齐，补齐前不得据此签约或付款。</p>
    </div>
  </main>
</div>
<div class="toolbar">
  <button type="button" id="print-btn" title="打印/导出 PDF">⎙</button>
  <button type="button" id="top-btn" title="回到顶部">↑</button>
</div>
{drawer}
<script>{JS}</script>
</body></html>"""


def main(argv=None):
    L.force_utf8()
    ap = argparse.ArgumentParser(description="Render interactive verification dossier (HTML).")
    ap.add_argument("project", help="path to project.json")
    ap.add_argument("-o", "--outdir", default="out", help="output directory")
    ap.add_argument("-n", "--name", default=None, help="output filename (no extension)")
    args = ap.parse_args(argv)

    project = L.load_project(args.project)
    os.makedirs(args.outdir, exist_ok=True)
    name = args.name or project.get("meta", {}).get("export_prefix") or "supplier-verification"
    path = os.path.join(args.outdir, L.safe_name(name) + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build(project))
    print(f"[ok] html -> {path}  ({os.path.getsize(path)/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
