# -*- coding: utf-8 -*-
"""render_html.py — data.json → 单文件交互式供应商横向比较报告。

    python scripts/render_html.py data.json out.html

特性：横向比较表（隐藏列 / 排序 / 筛选 / 证据标签直链 / 展开企业档案）、
差异聚焦、证据索引、报价对比、问询清单导出（逐家 txt / 一键复制）、打印样式。
零第三方依赖，样式与脚本全部内联。
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re  # noqa: E402
import cmplib as L  # noqa: E402


def findall_ids(raw):
    return sorted(set(i.upper() for i in re.findall(r"[Ee]\d+", str(raw or ""))), key=lambda x: int(x[1:]))


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", str(s or "")).strip()


def cell_labels(raw):
    return L.cell_labels(raw)

CSS = r"""
:root{
  --ink:#0f1b24;--ink2:#1d2d38;--body:#2c3a44;--muted:#67747d;--faint:#8f9aa2;
  --paper:#f4f2ec;--card:#fffefb;--line:#e4dfd3;--line2:#d0c9b8;
  --brand:#0f3b4c;--brand2:#1b5b70;--brand3:#eaf1f3;
  --brass:#97702f;--brass2:#c29a55;--brass-l:#f8f1e4;
  --ok:#1b6a49;--ok-bg:#e7f4ed;--ok-ln:#b9dcc8;
  --blue:#2a5a86;--blue-bg:#e9f0f7;--blue-ln:#c3d5e7;
  --amber:#9c5f13;--amber-bg:#fbf1e1;--amber-ln:#efd7b2;
  --red:#9c2a2a;--red-bg:#fbeae9;--red-ln:#efc4c1;
  --gray:#636a70;--gray-bg:#eef0f1;--gray-ln:#d6dade;
  --serif:Georgia,"Times New Roman","Songti SC","STSong","Noto Serif SC","Source Han Serif SC",SimSun,serif;
  --sans:"Microsoft YaHei","PingFang SC","Hiragino Sans GB","Source Han Sans SC",-apple-system,"Segoe UI",sans-serif;
  --mono:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
  --sh:0 1px 2px rgba(15,27,36,.05),0 12px 32px -20px rgba(15,27,36,.25);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--body);font-family:var(--sans);font-size:14px;line-height:1.7;
  -webkit-font-smoothing:antialiased;
  background-image:radial-gradient(rgba(15,27,36,.03) 1px,transparent 1px);background-size:22px 22px}
h1,h2,h3,h4{margin:0;color:var(--ink);font-weight:700;line-height:1.35}
a{color:var(--brand2);text-decoration:none}
.wrap{max-width:1500px;margin:0 auto;padding:0 24px}
.mono{font-family:var(--mono);font-size:12px}

/* ---------- hero ---------- */
.hero{position:relative;overflow:hidden;color:#dbe7ea;
  background:radial-gradient(900px 400px at 86% -18%,rgba(27,91,112,.8),transparent 62%),
             radial-gradient(700px 320px at 0% 120%,rgba(151,112,47,.32),transparent 60%),
             linear-gradient(155deg,#07151d 0%,#0d2a37 46%,#10384a 100%)}
.hero::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.32;
  background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);
  background-size:40px 40px;mask-image:radial-gradient(70% 90% at 35% 15%,#000 30%,transparent 100%)}
.hero .wrap{position:relative;z-index:2;padding:34px 24px 30px}
.eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:11px;font-weight:700;letter-spacing:.16em;
  color:#f0d6a6;background:rgba(255,255,255,.06);border:1px solid rgba(240,214,166,.3);padding:5px 11px;border-radius:999px}
.hero h1{color:#fff;font-family:var(--serif);font-size:40px;line-height:1.18;margin:16px 0 6px;letter-spacing:.01em}
.hero .sub{color:#a8c5cf;font-size:14px;letter-spacing:.04em}
.hero .req{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:22px;
  background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:16px 18px}
.hero .req div{min-width:0}
.hero .req .k{font-size:10.5px;letter-spacing:.14em;color:#8fb3c0;font-weight:700;text-transform:uppercase}
.hero .req .v{color:#fff;font-size:13px;line-height:1.6;margin-top:3px;word-break:break-word}
.hero .req .v small{color:#9dbcc7;display:block;font-size:11.5px}
.mchips{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.mchip{font-size:11.5px;color:#cfe0e5;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);padding:4px 10px;border-radius:6px}
.mchip b{color:#fff}

/* ---------- principle banner ---------- */
.principle{position:relative;z-index:4;margin-top:-18px;display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.pr{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;box-shadow:var(--sh);
  position:relative;overflow:hidden}
.pr::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--brand2)}
.pr .n{font-family:var(--serif);font-size:12px;color:var(--brass);font-weight:700;letter-spacing:.1em}
.pr b{display:block;color:var(--ink);font-size:13px;margin:2px 0}
.pr span{font-size:11.5px;color:var(--muted);line-height:1.55}

/* ---------- toolbar ---------- */
.toolbar{position:sticky;top:0;z-index:50;background:rgba(244,242,236,.94);backdrop-filter:saturate(160%) blur(10px);
  border-bottom:1px solid var(--line2);margin-top:20px}
.toolbar .wrap{display:flex;align-items:center;gap:10px;height:54px;flex-wrap:wrap}
.toolbar .tt{font-size:12px;font-weight:700;color:var(--ink);letter-spacing:.04em;white-space:nowrap}
.spacer{flex:1}
.btn{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line2);background:#fff;color:var(--ink2);
  font:inherit;font-size:12px;font-weight:600;padding:6px 11px;border-radius:8px;cursor:pointer;transition:.15s;white-space:nowrap}
.btn:hover{border-color:var(--brand2);color:var(--brand2);background:var(--brand3)}
.btn.on{background:var(--brand);border-color:var(--brand);color:#fff}
.btn-pri{background:var(--brand);border-color:var(--brand);color:#fff}
.btn-pri:hover{background:var(--brand2);border-color:var(--brand2);color:#fff}
.btn-ghost{background:transparent}
.seg{display:inline-flex;border:1px solid var(--line2);border-radius:9px;overflow:hidden;background:#fff}
.seg button{border:0;background:transparent;font:inherit;font-size:12px;padding:6px 11px;cursor:pointer;color:var(--muted)}
.seg button.on{background:var(--brand);color:#fff;font-weight:600}
.search{border:1px solid var(--line2);background:#fff;border-radius:8px;padding:6px 10px;font:inherit;font-size:12px;width:190px;color:var(--ink2)}
.search:focus{outline:2px solid var(--brand3);border-color:var(--brand2)}

/* ---------- popover ---------- */
.pop{position:absolute;z-index:80;background:#fff;border:1px solid var(--line2);border-radius:10px;box-shadow:0 20px 50px -20px rgba(15,27,36,.45);
  padding:10px;min-width:230px;display:none}
.pop.show{display:block}
.pop label{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--ink2);padding:4px 6px;border-radius:6px;cursor:pointer}
.pop label:hover{background:var(--brand3)}
.pop .ph{font-size:10.5px;letter-spacing:.12em;color:var(--faint);font-weight:700;margin:2px 6px 6px}

/* ---------- section ---------- */
section.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh);margin:22px 0;overflow:hidden}
.card-h{display:flex;align-items:flex-start;gap:14px;padding:20px 22px 12px;border-bottom:1px solid var(--line)}
.card-h .no{font-family:var(--serif);font-size:26px;color:var(--brass);font-weight:700;line-height:1;margin-top:2px}
.card-h h2{font-size:19px;letter-spacing:-.01em}
.card-h .sub{font-size:12.5px;color:var(--muted);margin-top:3px}
.card-h .right{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.card-b{padding:16px 22px 22px}
.lead{background:var(--brass-l);border:1px solid #ecdfc4;border-left:3px solid var(--brass2);border-radius:8px;padding:12px 14px;
  font-size:13px;color:#4a3a20;line-height:1.75;margin-bottom:14px}
.lead b{color:#3a2c15}
.note{border:1px dashed var(--line2);border-radius:8px;padding:10px 13px;font-size:12.5px;color:var(--muted);background:#fbfaf6;margin-top:12px}
.note.warn{border-color:var(--amber-ln);background:var(--amber-bg);color:#6b4711}

/* ---------- matrix ---------- */
.mx-scroll{overflow:auto;border:1px solid var(--line2);border-radius:10px;background:#fff}
table.mx{border-collapse:separate;border-spacing:0;width:100%;min-width:980px;font-size:12.5px}
table.mx th,table.mx td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);vertical-align:top;padding:10px 11px;text-align:left}
table.mx thead th{position:sticky;top:0;z-index:5;background:#f7f5ef;color:var(--ink);font-size:12px;font-weight:700;line-height:1.45}
table.mx thead th .sid{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:5px;
  background:var(--brand);color:#fff;font-size:10.5px;margin-right:6px;font-family:var(--mono)}
table.mx thead th .sd{display:block;font-weight:400;color:var(--muted);font-size:11px;margin-top:2px}
table.mx thead th .th-t{display:flex;align-items:center;gap:6px}
table.mx thead th .x{border:0;background:transparent;color:var(--faint);cursor:pointer;font-size:13px;line-height:1;padding:0 2px}
table.mx thead th .x:hover{color:var(--red)}
table.mx th.dim-col,table.mx td.dim-col{position:sticky;left:0;z-index:4;background:#fbfaf6;min-width:170px;max-width:210px;box-shadow:2px 0 0 var(--line)}
table.mx thead th.dim-col{z-index:6;background:#f2efe7}
table.mx tbody tr:hover td{background:#fcfbf7}
table.mx tbody tr:hover td.dim-col{background:#f7f5ef}
.dk{display:flex;gap:7px;align-items:baseline}
.dk .dn{font-family:var(--mono);font-size:10.5px;color:var(--brass);font-weight:700}
.dk b{font-size:12.5px;color:var(--ink);line-height:1.45}
.dnote{font-size:11px;color:var(--faint);margin-top:3px;line-height:1.5}
.cv{line-height:1.6;color:var(--ink2)}
.cv p{margin:6px 0 0}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
.diffdot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--brass2);margin-left:5px;vertical-align:middle;
  title:属性}
td.isdiff{background:linear-gradient(0deg,rgba(194,154,85,.07),rgba(194,154,85,.07))}
tr.focus-dim td.dim-col{box-shadow:inset 3px 0 0 var(--brass),2px 0 0 var(--line)}

/* ---------- pill / tag / evid ---------- */
.pill{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;
  border:1px solid;line-height:1.6;white-space:nowrap}
.pill i{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block}
.p-green{color:var(--ok);background:var(--ok-bg);border-color:var(--ok-ln)}
.p-amber{color:var(--amber);background:var(--amber-bg);border-color:var(--amber-ln)}
.p-red{color:var(--red);background:var(--red-bg);border-color:var(--red-ln)}
.p-blue{color:var(--blue);background:var(--blue-bg);border-color:var(--blue-ln)}
.p-gray{color:var(--gray);background:var(--gray-bg);border-color:var(--gray-ln)}
.evs{display:inline-flex;flex-wrap:wrap;gap:4px;margin-top:6px;vertical-align:middle}
a.ev,.ev.evmiss{font-family:var(--mono);font-size:10.5px;font-weight:700;padding:1px 6px;border-radius:5px;
  border:1px solid var(--brand3);background:var(--brand3);color:var(--brand2);line-height:1.7}
a.ev:hover{background:var(--brand);color:#fff;border-color:var(--brand)}
.ev.evmiss{color:var(--red);background:var(--red-bg);border-color:var(--red-ln)}
.lv{display:inline-block;font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:5px;border:1px solid}
.lv-high{color:var(--red);background:var(--red-bg);border-color:var(--red-ln)}
.lv-mid{color:var(--amber);background:var(--amber-bg);border-color:var(--amber-ln)}
.lv-low{color:var(--ok);background:var(--ok-bg);border-color:var(--ok-ln)}
.lv-none{color:var(--gray);background:var(--gray-bg);border-color:var(--gray-ln)}
.st{display:inline-block;font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:5px;border:1px solid;white-space:nowrap}
.st-confirmed{color:var(--ok);background:var(--ok-bg);border-color:var(--ok-ln)}
.st-quoted{color:var(--blue);background:var(--blue-bg);border-color:var(--blue-ln)}
.st-pending{color:var(--amber);background:var(--amber-bg);border-color:var(--amber-ln)}
.st-missing{color:var(--gray);background:var(--gray-bg);border-color:var(--gray-ln)}
.st-risk{color:var(--red);background:var(--red-bg);border-color:var(--red-ln)}
.lgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:2px 0 4px}
.lg{border:1px solid var(--line);border-radius:8px;padding:8px 10px;background:#fff}
.lg b{display:block;font-size:12px;color:var(--ink)}
.lg span{font-size:10.5px;color:var(--muted);line-height:1.5;display:block;margin-top:2px}
.lg .n{font-family:var(--serif);font-size:17px;color:var(--brass);font-weight:700}

/* ---------- cards ---------- */
.g2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.g3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.mini{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.mini h4{font-size:13px;margin-bottom:4px}
.mini p{margin:0;font-size:12px;color:var(--muted);line-height:1.7}
.ft{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:#fff}
.ft .fh{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.ft .fh .id{font-family:var(--mono);font-size:10.5px;font-weight:700;color:var(--brass);background:var(--brass-l);
  border:1px solid #ecdfc4;border-radius:5px;padding:1px 6px}
.ft h4{font-size:13.5px;flex:1}
.ft .fb{font-size:12.5px;color:var(--ink2);line-height:1.75}
.ft .fm{margin-top:6px;display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.ft .fm .dm{font-size:10.5px;color:var(--faint)}

/* ---------- supplier dossier ---------- */
.sup{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh);margin:18px 0;overflow:hidden}
.sup-h{display:flex;align-items:center;gap:14px;padding:16px 20px;cursor:pointer;user-select:none}
.sup-h:hover{background:#fcfbf7}
.sup-h .av{width:42px;height:42px;border-radius:10px;display:flex;align-items:center;justify-content:center;
  font-family:var(--serif);font-size:20px;font-weight:700;color:#fff;background:linear-gradient(145deg,#1b5b70,#0f3b4c);flex:none}
.sup-h .nm{flex:1;min-width:0}
.sup-h .nm h3{font-size:16px}
.sup-h .nm .meta{font-size:11.5px;color:var(--muted);margin-top:2px}
.sup-h .cv-btn{transition:.2s}
.sup.open .cv-btn{transform:rotate(180deg)}
.sup-b{display:none;border-top:1px solid var(--line);padding:18px 20px 22px}
.sup.open .sup-b{display:block}
.tiers{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}
.tier{border:1px solid var(--line);border-radius:9px;padding:9px 11px;background:#fbfaf6;min-width:0}
.tier .t1{font-size:10.5px;color:var(--faint);font-weight:700;letter-spacing:.08em}
.tier .t2{font-size:12px;color:var(--ink);font-weight:700;margin:1px 0 2px}
.tier .t3{font-size:11.5px;color:var(--muted);line-height:1.55}
.kv{display:grid;grid-template-columns:150px 1fr;gap:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}
.kv>div{padding:8px 12px;border-bottom:1px solid var(--line);font-size:12.5px}
.kv>div:nth-child(2n+1){background:#fbfaf6;color:var(--muted);font-weight:600}
.kv>div.lasts{border-bottom:0}
.subh{font-size:11px;letter-spacing:.12em;font-weight:700;color:var(--brass);margin:16px 0 8px;text-transform:uppercase}

/* ---------- tables ---------- */
.tw{overflow:auto;border:1px solid var(--line2);border-radius:10px;background:#fff}
table.tb{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px}
table.tb th,table.tb td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
table.tb thead th{position:sticky;top:0;background:#f7f5ef;font-size:11.5px;font-weight:700;color:var(--ink);z-index:2}
table.tb tbody tr:last-child td{border-bottom:0}
table.tb tbody tr:hover td{background:#fcfbf7}
table.tb td.c,table.tb th.c{text-align:center}
table.tb td.r,table.tb th.r{text-align:right}
.tscroll-x{overflow-x:auto}

/* ---------- timeline ---------- */
.tl{position:relative;margin:6px 0 0 8px;padding-left:22px}
.tl::before{content:"";position:absolute;left:5px;top:4px;bottom:4px;width:2px;background:linear-gradient(var(--brass2),var(--line2))}
.tli{position:relative;margin-bottom:12px}
.tli::before{content:"";position:absolute;left:-22px;top:6px;width:9px;height:9px;border-radius:50%;background:#fff;border:2px solid var(--brass2)}
.tli .d{font-family:var(--mono);font-size:11px;color:var(--brass);font-weight:700}
.tli .x{font-size:12.5px;color:var(--ink2);line-height:1.7}
.tg{display:inline-block;font-size:10px;font-weight:700;padding:0 6px;border-radius:4px;background:var(--brand3);
  color:var(--brand2);border:1px solid #cfe0e5;margin-right:6px}

/* ---------- questions ---------- */
.qtabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.qb{border:1px solid var(--line);border-radius:10px;background:#fff;padding:0;overflow:hidden}
.qrow{display:grid;grid-template-columns:26px 64px 1fr;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line);align-items:start}
.qrow:last-child{border-bottom:0}
.qrow .i{font-family:var(--mono);font-size:10.5px;color:var(--faint);font-weight:700;padding-top:2px}
.qrow .q{font-size:12.5px;color:var(--ink2);line-height:1.75}
.qrow .w{font-size:11.5px;color:var(--muted);margin-top:4px;line-height:1.6}
.qrow:hover{background:#fcfbf7}
.pri{display:inline-block;font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;border:1px solid;white-space:nowrap}
.pri-h{color:var(--red);background:var(--red-bg);border-color:var(--red-ln)}
.pri-m{color:var(--amber);background:var(--amber-bg);border-color:var(--amber-ln)}
.pri-l{color:var(--ok);background:var(--ok-bg);border-color:var(--ok-ln)}

/* ---------- footer / toast ---------- */
footer{margin:40px 0 30px;color:var(--faint);font-size:11.5px;line-height:1.8;border-top:1px solid var(--line2);padding-top:16px}
footer b{color:var(--muted)}
.toast{position:fixed;left:50%;bottom:28px;transform:translate(-50%,20px);background:var(--ink);color:#fff;font-size:12.5px;
  padding:9px 16px;border-radius:999px;opacity:0;pointer-events:none;transition:.25s;z-index:200;box-shadow:0 14px 30px -12px rgba(0,0,0,.5)}
.toast.show{opacity:1;transform:translate(-50%,0)}
.only-focus .hide-focus{display:none!important}

@media (max-width:1180px){
  .principle{grid-template-columns:repeat(2,1fr)}
  .hero .req{grid-template-columns:repeat(2,1fr)}
  .g3{grid-template-columns:1fr}
  .tiers{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (max-width:820px){
  .hero h1{font-size:28px}
  .g2{grid-template-columns:1fr}
  .lgrid{grid-template-columns:repeat(2,1fr)}
  .kv{grid-template-columns:110px 1fr}
  .toolbar .wrap{height:auto;padding-top:8px;padding-bottom:8px}
  .search{width:130px}
}
@media print{
  body{background:#fff;background-image:none}
  .toolbar,.pop,.toast,.btn,.seg,.search{display:none!important}
  section.card,.sup,.pr{box-shadow:none;break-inside:avoid}
  .sup-b{display:block!important}
  table.mx{min-width:0;font-size:10px}
  .mx-scroll{overflow:visible}
  .hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  table.mx th.dim-col{position:static}
}
"""

JS = r"""
(function(){
  var S = document.querySelectorAll('[data-sup]');
  var focus = null;
  function toast(t){var el=document.getElementById('toast');el.textContent=t;el.classList.add('show');clearTimeout(el._t);el._t=setTimeout(function(){el.classList.remove('show');},2000);}
  window.__toast = toast;

  /* ---- 隐藏列 ---- */
  var colsBtn = document.getElementById('colsBtn'), colsPop = document.getElementById('colsPop');
  if(colsBtn){
    colsBtn.onclick = function(e){
      e.stopPropagation();
      var r = colsBtn.getBoundingClientRect();
      colsPop.style.left = Math.min(r.left, window.innerWidth-280)+'px';
      colsPop.style.top = (r.bottom+6)+'px';
      colsPop.classList.toggle('show');
    };
    document.addEventListener('click', function(e){
      if(!colsPop.contains(e.target) && e.target!==colsBtn) colsPop.classList.remove('show');
    });
    colsPop.querySelectorAll('input[data-col]').forEach(function(chk){
      chk.onchange = function(){
        var i = chk.getAttribute('data-col');
        document.querySelectorAll('[data-col="'+i+'"]').forEach(function(el){ el.style.display = chk.checked ? '' : 'none'; });
        var hidden = colsPop.querySelectorAll('input[data-col]:not(:checked)').length;
        document.getElementById('colsCount').textContent = hidden ? '已隐藏 '+hidden+' 列' : '隐藏列';
      };
    });
  }

  /* ---- 排序 ---- */
  document.querySelectorAll('th[data-sort]').forEach(function(th){
    th.addEventListener('click', function(e){
      if(e.target.classList.contains('x')) return;
      var table = th.closest('table');
      var idx = +th.getAttribute('data-sort');
      var tbody = table.querySelector('tbody');
      var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr')).filter(function(r){return !r.classList.contains('hide-sort');});
      var dir = th.dataset.dir === 'asc' ? -1 : 1;
      th.dataset.dir = dir===1 ? 'asc' : 'desc';
      table.querySelectorAll('th[data-sort]').forEach(function(o){ if(o!==th) delete o.dataset.dir; });
      rows.sort(function(a,b){
        var A = a.dataset.k[idx]||'', B = b.dataset.k[idx]||'';
        var nA = parseFloat(A), nB = parseFloat(B);
        if(!isNaN(nA) && !isNaN(nB) && /^[-\d.]+$/.test(A.trim()) && /^[-\d.]+$/.test(B.trim())) return (nA-nB)*dir;
        return A.localeCompare(B,'zh')*dir;
      });
      rows.forEach(function(r){ tbody.appendChild(r); });
      th.querySelector('.sicon').textContent = dir===1 ? ' ↑' : ' ↓';
    });
  });

  /* ---- 只看差异 ---- */
  var diffBtn = document.getElementById('diffBtn'), diffOn = false;
  if(diffBtn){
    diffBtn.onclick = function(){
      diffOn = !diffOn; diffBtn.classList.toggle('on', diffOn);
      document.querySelectorAll('tr[data-diff]').forEach(function(tr){
        if(!diffOn) tr.classList.remove('hide-focus');
        else if(tr.getAttribute('data-diff')==='1') tr.classList.remove('hide-focus');
        else tr.classList.add('hide-focus');
      });
      toast(diffOn ? '只显示存在实质差异的维度' : '显示全部维度');
    };
  }

  /* ---- 证据标签筛选 ---- */
  document.querySelectorAll('.lfilter').forEach(function(b){
    b.onclick = function(){
      var lb = b.getAttribute('data-lb');
      document.querySelectorAll('.lfilter').forEach(function(o){o.classList.remove('on');});
      if(b.classList.contains('on')){ b.classList.remove('on'); b.dataset.active='0'; }
      else { b.classList.add('on'); b.dataset.active='1'; }
      var any = document.querySelector('.lfilter.on') ? document.querySelector('.lfilter.on').getAttribute('data-lb') : null;
      document.querySelectorAll('[data-lbl]').forEach(function(el){
        el.style.opacity = (!any || el.getAttribute('data-lbl').indexOf(any)>=0) ? '' : '.22';
      });
    };
  });

  /* ---- 搜索 ---- */
  var q = document.getElementById('q');
  if(q){
    q.addEventListener('input', function(){
      var v = q.value.trim();
      document.querySelectorAll('table.mx td[data-search]').forEach(function(td){
        td.style.background = (v && td.textContent.indexOf(v)>=0) ? '#fff3cf' : '';
      });
      document.querySelectorAll('.sup').forEach(function(sp){
        var hit = v && sp.textContent.indexOf(v)>=0;
        if(v && hit) sp.classList.add('open');
      });
    });
  }

  /* ---- 供应商聚焦 ---- */
  document.querySelectorAll('.sfocus').forEach(function(b){
    b.onclick = function(){
      var sid = b.getAttribute('data-sid');
      var on = sFocus === sid ? null : sid;
      setFocus(on);
    };
  });
  var sFocus = null;
  function setFocus(sid){
    sFocus = sid;
    document.querySelectorAll('.sfocus').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-sid')===sid); });
    document.querySelectorAll('table.mx th[data-col], table.mx td[data-col]').forEach(function(el){
      var isDim = el.classList.contains('dim-col');
      if(!sid || isDim){ if(el.dataset.hidByFocus!=='1') el.style.display=''; }
      else {
        if(el.dataset.hidByFocus!=='1' && el.style.display!=='none') el.dataset.hidByFocus='0';
        if(el.getAttribute('data-col')!==sid) el.style.display='none';
      }
    });
    toast(sid ? '已聚焦 '+sid : '已恢复全部供应商列');
  }

  /* ---- 档案展开 ---- */
  document.querySelectorAll('.sup-h').forEach(function(h){
    h.onclick = function(){ h.parentElement.classList.toggle('open'); };
  });
  var openAll = document.getElementById('openAll');
  if(openAll){ openAll.onclick=function(){ var any=document.querySelector('.sup:not(.open)');
    document.querySelectorAll('.sup').forEach(function(s){s.classList.toggle('open', !!any);});
    openAll.textContent = any ? '收起档案' : '展开档案'; }; }

  /* ---- 展开/收起全部章节明细 ---- */
  document.querySelectorAll('[data-toggle-group]').forEach(function(b){
    b.onclick = function(){
      var g = b.getAttribute('data-toggle-group');
      var items = document.querySelectorAll('[data-group="'+g+'"].collapse-body');
      var anyHidden = Array.prototype.some.call(items, function(i){return i.style.display==='none'||!i.style.display;});
      items.forEach(function(i){ i.style.display = anyHidden ? 'block' : 'none'; });
      b.textContent = anyHidden ? '收起' : '展开';
    };
  });

  /* ---- 复制问询清单 ---- */
  document.querySelectorAll('[data-copy]').forEach(function(b){
    b.onclick = function(){
      var txt = document.getElementById(b.getAttribute('data-copy')).innerText;
      navigator.clipboard.writeText(txt).then(function(){toast('问询清单已复制，可直接粘贴到邮件');},
        function(){toast('复制失败：请手动选择文本复制');});
    };
  });

  /* ---- 下载问询清单 ---- */
  document.querySelectorAll('[data-dl]').forEach(function(b){
    b.onclick = function(){
      var txt = document.getElementById(b.getAttribute('data-dl')).innerText;
      var name = b.getAttribute('data-name') || '询证问题清单.txt';
      var blob = new Blob(['\ufeff'+txt], {type:'text/plain;charset=utf-8'});
      var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      toast('已下载 '+name);
    };
  });

  /* ---- 页码 / 章节跳转 ---- */
  document.querySelectorAll('[data-goto]').forEach(function(b){
    b.onclick = function(){ var el=document.getElementById(b.getAttribute('data-goto')); if(el) el.scrollIntoView({behavior:'smooth',block:'start'}); };
  });
})();
"""


def pill(text, color):
    return '<span class="pill p-%s"><i></i>%s</span>' % (color, L.esc(text))


def status_chip(st):
    s = L.STATUS.get(st, L.STATUS["pending"])
    return '<span class="st st-%s">%s</span>' % (st, L.esc(s["cn"]))


def lvl_chip(lvl):
    if not lvl:
        return ""
    s = L.LEVELS.get(lvl)
    if not s:
        return '<span class="lv lv-none">%s</span>' % L.esc(lvl)
    return '<span class="lv lv-%s">%s</span>' % (lvl, L.esc(s["cn"]))


def render(data):
    c = L.Cmp(data)
    m = c.meta
    sups = c.suppliers
    parts = []
    A = parts.append

    # ---------------- head ----------------
    page_title = "%s · %s" % (m.get("title", "供应商横向比较"), m.get("product", ""))
    A('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A('<title>%s</title>' % L.esc(page_title))
    A('<style>%s</style></head><body>' % CSS)

    # ---------------- hero ----------------
    A('<header class="hero"><div class="wrap">')
    A('<span class="eyebrow">SUPPLIER BENCHMARK · %s</span>' % L.esc(m.get("doc_no", "")))
    A('<h1>%s</h1>' % L.esc(m.get("issue") or m.get("title", "")))
    A('<div class="sub">%s</div>' % L.esc(m.get("product", "")))
    req = c.req
    A('<div class="req">')
    for k, kk in (("采购标的", "product"), ("数量", "qty"), ("收货地", "destination"), ("数据截止", "as_of")):
        v = req.get(kk) or m.get(kk)
        if kk == "qty" and req.get("qty_alt"):
            v = "%s<small>备选口径：%s</small>" % (L.esc(req.get("qty")), L.esc(req.get("qty_alt")))
        else:
            v = L.esc(v)
        A('<div><div class="k">%s</div><div class="v">%s</div></div>' % (k, v))
    A('</div>')
    chips = [("比较对象", " · ".join(s.get("short", "") for s in sups)),
             ("维度", "%d 个（含 %d 个自定义）" % (len(c.dims), sum(1 for d in c.dims if d.get("type") == "custom"))),
             ("证据", "%d 条" % len(c.ev)),
             ("版本", m.get("version", "v1.0")),
             ("编制", m.get("prepared_by", ""))]
    A('<div class="mchips">' + "".join('<span class="mchip">%s <b>%s</b></span>' % (L.esc(k), L.esc(v)) for k, v in chips if v) + '</div>')
    A('</div></header>')

    # ---------------- principle ----------------
    A('<div class="wrap"><div class="principle">')
    principles = [
        ("01", "事实 / 自述 / 不可核", "每一条都带标签：已核实、企业自述、无法核实、风险事实"),
        ("02", "经营范围 ≠ 生产能力", "许可证上的“经营范围包含该化学品”不等同于具备该产品的实际产线"),
        ("03", "不做综合评分", "只呈现可核验的差异与不确定项，不给“最佳供应商”"),
        ("04", "商业条款不虚构", "未取得报价即标“待确认”，并转成逐家问询问题"),
    ]
    for n, b, s in principles:
        A('<div class="pr"><div class="n">%s</div><b>%s</b><span>%s</span></div>' % (n, L.esc(b), L.esc(s)))
    A('</div></div>')

    # ---------------- toolbar ----------------
    A('<div class="toolbar"><div class="wrap">')
    A('<span class="tt">比较工作台</span>')
    for s in sups:
        A('<button class="btn sfocus" data-sid="%s">只看 %s</button>' % (L.esc(s["id"]), L.esc(s.get("short", s["id"]))))
    A('<div class="spacer"></div>')
    A('<button class="btn" id="diffBtn">只看实质差异</button>')
    A('<button class="btn" id="colsBtn"><span id="colsCount">隐藏列</span> ▾</button>')
    A('<div class="seg" id="segMode"><button class="on" data-goto="sec-mx">横向比较表</button>'
      '<button data-goto="sec-sup">企业档案</button><button data-goto="sec-ev">证据索引</button>'
      '<button data-goto="sec-q">问询清单</button></div>')
    A('<input class="search" id="q" placeholder="全文检索（高亮单元格）">')
    A('<button class="btn" onclick="window.print()">打印 / PDF</button>')
    A('</div>')
    A('<div class="pop" id="colsPop"><div class="ph">选择要显示的维度列</div>')
    for i, d in enumerate(c.dims):
        A('<label><input type="checkbox" data-col="%d" checked> %s</label>' % (i, L.esc(d["label"])))
    A('</div></div>')

    # ---------------- summary / KPI ----------------
    lcount = c.report_labels()
    A('<section class="card" id="sec-sum"><div class="card-h"><span class="no">00</span>'
      '<div><h2>一页读懂：三家企业到底哪里不一样</h2>'
      '<div class="sub">先看事实与标签，再看差异；解读与决策留给你</div></div></div><div class="card-b">')

    A('<div class="lgrid">')
    for k in L.LABEL_ORDER:
        info = L.LABELS[k]
        desc = info["desc"].split("（")[0]
        A('<div class="lg"><div class="n">%d</div><b>%s</b><span>%s</span></div>' % (lcount[k], L.esc(info["cn"]), L.esc(desc)))
    A('</div>')
    gap = c.day_gap()
    A('<div class="note">数据截止 <b>%s</b>%s。证据标签的计数口径为“维度单元格中出现的证据簇数”，'
      '同一份文件支撑不同维度会被重复计数，请以证据索引中的 %d 条原文为准。</div>'
      % (L.esc(m.get("as_of")), ("（距今天 %d 天，请留意时效）" % gap) if gap and gap > 30 else "", len(c.ev)))

    # KPI 卡
    A('<div class="g3" style="margin-top:14px">')
    for s in sups:
        sid = s["id"]
        pr = L.PRODUCER.get(s.get("producer", "unknown"), L.PRODUCER["unknown"])
        A('<div class="mini"><h4><span style="color:var(--brass);font-family:var(--serif)">%s</span> %s</h4>' % (sid, L.esc(s.get("name"))))
        A('<p>%s</p>' % L.frag(s.get("summary", "")))
        A('<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">%s %s</div>' % (pill(pr["cn"], pr["color"]),
          pill("%d 条证据" % c.evidence_count(sid), "blue")))
        A('</div>')
    A('</div>')

    # 层级卡（Tier 1–4）
    A('<div class="subh">四层核验（本报告固定结构）</div>')
    tiers = [("T1", "主体与厂家身份", "营业执照、信用代码、生产≠注册地址"),
             ("T2", "产品与生产能力", "设计产能、许可产能、实际产量三数是否自洽"),
             ("T3", "资质与合规", "排污许可、危化/食品等专项许可、体系认证"),
             ("T4", "经营与商业条款", "司法与处罚、负面事件、价格与交付口径")]
    A('<div class="g2">')
    for code, t, d in tiers:
        A('<div class="mini"><h4>%s · %s</h4><p>%s</p></div>' % (code, L.esc(t), L.esc(d)))
    A('</div>')
    A('</div></section>')

    # ---------------- matrix ----------------
    A('<section class="card" id="sec-mx"><div class="card-h"><span class="no">01</span>'
      '<div><h2>供应商横向比较表</h2><div class="sub">点击列头排序 · 右上角隐藏列 · “只看实质差异”收起无差异维度 · 证据标签可点击打开原文</div></div>'
      '<div class="right"><button class="btn" id="copyMx" data-copy="mxText" data-dl="mxText" data-name="横向比较表.txt">复制表格文本</button></div></div>')
    A('<div class="card-b">')
    A('<div class="lead">下表给出三家在同一组维度下的原始信息。<b>金色小圆点</b>表示该维度三家之间“真正不同”，灰色副标题给出该维度的判读要点。所有单元格右侧的证据标签：'
      '绿色=一手文件已核实、琥珀=企业自述、蓝色=媒体/第三方、灰色=无法核实、红色=可核实的风险事实。</div>')
    A('<div class="mx-scroll"><table class="mx" id="mx"><thead><tr>')
    A('<th class="dim-col" data-sort="0">比较维度</th>')
    for i, s in enumerate(sups):
        A('<th data-col="%s" data-sort="%d"><div class="th-t"><span class="sid">%s</span>%s</div><span class="sd">%s</span></th>'
          % (L.esc(s['id']), i + 1, L.esc(s['id']), L.esc(s.get('short')), L.esc(s.get('code', ''))))
    A('</tr></thead><tbody>')

    for di, dim in enumerate(c.dims):
        k = dim['key']
        dd = c.dim_diff(k)
        keys = ['%02d %s' % (di + 1, dim['label'])]
        A('<tr data-diff="%d" class="dimrow" data-dim="%s">' % (1 if dd['differ'] else 0, L.esc(k)))
        A('<td class="dim-col"><div class="dk"><span class="dn">%02d</span><b>%s%s</b></div>' % (
            di + 1, L.esc(dim['label']),
            '<span class="diffdot" title="三家在此维度存在实质差异"></span>' if dd['differ'] else ''))
        if dim.get('hint'):
            A('<div class="dnote">%s</div>' % L.frag(dim['hint']))
        if dim.get('type') == 'terms':
            n_pending = sum(1 for s in sups if c.term_cells.get('price', {}).get(s['id'], {}).get('status') == 'pending')
            A('<div class="dnote">%d / %d 家尚未提供报价 · 8 项条款明细见第 09 节</div>' % (n_pending, len(sups)))
        A('</td>')
        for s in sups:
            sid = s['id']
            cell = c.cells[k].get(sid) or {}
            if dim.get('type') == 'terms':
                tc = c.term_cells.get('price', {}).get(sid, {})
                st = tc.get('status', 'pending')
                labels = ['U'] if st == 'pending' else (cell_labels(tc.get('ev', '')) or ['V'])
                inner = '<div class="cv"><b>%s</b> %s</div>' % (
                    L.esc(L.STATUS.get(st, {}).get('cn', '')), L.esc(tc.get('v') or ''))
                inner += '<div class="dnote">价格、含税口径、运费、包装、账期、交期、MOQ、有效期共 8 项见第 09 节</div>'
                inner += '<div class="chips">%s</div>' % ''.join(
                    '<span data-lbl="%s">%s</span>' % (lb, pill(L.LABELS[lb]['cn'], L.LABELS[lb]['color'])) for lb in labels)
                inner += c.evchips(findall_ids(tc.get('ev', '')))
                plain = st
            else:
                labels = c.labels[(k, sid)]
                inner = '<div class="cv">%s</div>' % (L.frag(cell.get('v')) or '<span style="color:var(--faint)">—</span>')
                if cell.get('note'):
                    inner += '<div class="dnote">%s</div>' % L.frag(cell['note'])
                chips = []
                if cell.get('lvl'):
                    chips.append(lvl_chip(cell['lvl']))
                for lb in labels:
                    chips.append('<span data-lbl="%s">%s</span>' % (lb, pill(L.LABELS[lb]['cn'], L.LABELS[lb]['color'])))
                if chips:
                    inner += '<div class="chips">%s</div>' % ''.join(chips)
                inner += c.evchips(findall_ids(cell.get('ev', '')))
                plain = strip_tags(cell.get('v'))
            keys.append(L.LEVELS.get(cell.get('lvl'), {}).get('cn', '') + ' ' + plain)
            A('<td data-col="%s" data-search="1" class="%s">%s</td>' % (
                L.esc(sid), 'isdiff' if dd['differ'] else '', inner))
        A('</tr>')

    A('</tbody></table></div>')
    A('<div class="note">说明：表中"风险等级"（高/中/低）是<b>对本次采购的潜在影响分级</b>，不是对企业的整体评级；'
      '"未发现"仅代表公开渠道在截止日未检索到，不代表不存在。</div>')
    A('</div></section>')

    # ---------------- differences ----------------
    A('<section class="card" id="sec-diff"><div class="card-h"><span class="no">02</span>'
      '<div><h2>真正不同的地方</h2><div class="sub">系统自动比对：同一维度数值或等级相同即视为"没有差异"，不占用你的注意力</div></div></div><div class="card-b">')
    same = [d for d in c.dimension_summary() if not d["differ"]]
    diff = [d for d in c.dimension_summary() if d["differ"]]
    A('<div class="lead">%d 个维度中，<b>%d 个存在实质差异</b>，%d 个三家趋同。趋同不等于可以忽略——'
      '它只是说明"在这点上没必要再花时间比较"。</div>' % (len(diff) + len(same), len(diff), len(same)))
    A('<div class="g2">')
    for d in diff:
        groups = d["groups"]
        A('<div class="mini"><h4>%s <span class="diffdot"></span></h4>' % L.esc(d["dim"]["label"]))
        A('<p>')
        for gi, g in enumerate(groups):
            names = "、".join(c.sname(x) for x in g)
            sample = "；".join(strip_tags(c.cells[d["dim"]["key"]][x]["v"])[:46] for x in g)
            A('<br><b style="color:var(--ink)">%s：</b>%s' % (L.esc(names), L.esc(sample) + ("…" if len(sample) >= 46 else "")))
        A('</p></div>')
    A('</div>')
    if same:
        A('<div class="note">三家趋同的维度：%s。这些维度已归入"无差异"，问题清单中不再单独提问。</div>'
          % "、".join(L.esc(d["dim"]["label"]) for d in same))
    A('</div></section>')

    # ---------------- supplier dossiers ----------------
    A('<section class="card" id="sec-sup"><div class="card-h"><span class="no">03</span>'
      '<div><h2>企业详细档案</h2><div class="sub">点击卡片展开：身份核验、规模、许可、风险与不确定项</div></div>'
      '<div class="right"><button class="btn" id="openAll">展开档案</button></div></div><div class="card-b">')
    for s in sups:
        A(render_dossier(c, s))
    A('</div></section>')

    # ---------------- facts vs claims ----------------
    A('<section class="card" id="sec-lab"><div class="card-h"><span class="no">04</span>'
      '<div><h2>事实 / 自述 / 无法核实 三分法</h2><div class="sub">把同一条信息从"谁说"的角度重新排一遍，避免把宣传口径当核验结果</div></div></div><div class="card-b">')
    buckets = {"V": [], "S": [], "U": [], "X": []}
    for dim in c.dims:
        if dim.get("type") == "terms":
            continue
        for s in sups:
            cell = c.cells[dim["key"]][s["id"]]
            lbs = c.labels[(dim["key"], s["id"])]
            for lb in lbs:
                if lb in buckets:
                    buckets[lb].append("%s · %s：%s" % (s.get("short"), dim["label"], strip_tags(cell["v"])[:110]))
            if not lbs:
                buckets["U"].append("%s · %s：本维度无证据标签（请核查填写）" % (s.get("short"), dim["label"]))
    for lb, title in (("V", "可核验的事实"), ("S", "企业自述与行业说法"), ("U", "无法核实 / 口径冲突"), ("X", "已发生的负面事实")):
        info = L.LABELS[lb]
        items = buckets[lb]
        A('<div class="subh">%s（%d）</div>' % (L.esc(title), len(items)))
        A('<div class="mini" style="padding:10px 14px"><p style="color:var(--ink2)">')
        if items:
            A("<br>".join("· " + L.esc(x) for x in items[:40]))
            if len(items) > 40:
                A("<br>… 另有 %d 条见横向比较表" % (len(items) - 40))
        else:
            A("（无）")
        A('</p></div>')
    A('</div></section>')

    # ---------------- findings ----------------
    if c.findings:
        A('<section class="card" id="sec-fd"><div class="card-h"><span class="no">05</span>'
          '<div><h2>关键差异与不确定项</h2><div class="sub">每条都指出"为什么不同""对采购意味着什么""下一步要核什么"</div></div></div><div class="card-b">')
        A('<div class="g2">')
        for f in c.findings:
            lv = f.get("level", "mid")
            A('<div class="ft"><div class="fh"><span class="id">%s</span><h4>%s</h4>%s</div><div class="fb">%s</div>'
              '<div class="fm"><span class="dm">%s</span>%s</div></div>'
              % (L.esc(f.get("id")), L.esc(f.get("title")), lvl_chip(lv), L.frag(f.get("text")),
                 L.esc(dim_label(c, f.get("dim", ""))), c.evchips(findall_ids(f.get("evid", "")))))
        A('</div></div></section>')

    # ---------------- intel / timeline ----------------
    if c.intel:
        A('<section class="card" id="sec-tl"><div class="card-h"><span class="no">06</span>'
          '<div><h2>近期动态与行业切片</h2><div class="sub">按时间倒序；每条都说清来源与口径</div></div></div><div class="card-b"><div class="tl">')
        for it in sorted(c.intel, key=lambda x: str(x.get("date", "")), reverse=True):
            A('<div class="tli"><div class="d">%s <span class="tg">%s</span>%s</div><div class="x">%s %s</div></div>'
              % (L.esc(it.get("date")), L.esc(it.get("tag", "")),
                 ("<span class='tg' style='background:var(--brass-l);color:var(--brass);border-color:#ecdfc4'>%s</span>"
                  % L.esc(c.sname(it["supplier"]))) if it.get("supplier") else "",
                 L.frag(it.get("text", "")), c.evchips(findall_ids(it.get("evid", "")))))
        A('</div>')
        if c.intel_reach:
            A('<div class="note">本轮检索覆盖：%s。%s</div>' % (
                "、".join(c.evchips([i]) for i in c.intel_reach.get("ids", [])[:40]),
                L.esc(c.intel_reach.get("note", ""))))
            if c.intel_reach.get("unselected"):
                A('<div class="note warn">本轮未完成（已转入问题清单）：%s</div>'
                  % L.esc("；".join(c.intel_reach.get("unselected"))))
        A('</div></section>')

    # ---------------- licences ----------------
    if c.certs:
        A('<section class="card" id="sec-cert"><div class="card-h"><span class="no">07</span>'
          '<div><h2>许可与资质全量表</h2><div class="sub">到期状态按数据截止日 %s 自动计算；180 天内到期标黄，已过期标红</div></div></div><div class="card-b">'
          % L.esc(c.meta.get("as_of")))
        A('<div class="tw"><table class="tb"><thead><tr><th>企业</th><th>证照名称</th><th>起</th><th>止</th><th>状态</th><th>许可范围 / 适用产品</th><th>持有人</th><th>相关度</th></tr></thead><tbody>')
        for ct in c.certs:
            st, tone = L.cert_state(ct.get("end"), c.as_of)
            cls = {"expired": "lv-high", "soon": "lv-mid", "valid": "lv-low"}.get(tone, "lv-none")
            rel = {"core": "本次必需", "related": "相关", "irrelevant": "无关"}.get(ct.get("relevance"), "")
            A('<tr><td>%s</td><td>%s</td><td class="mono">%s</td><td class="mono">%s</td>'
              '<td><span class="lv %s">%s</span></td><td>%s</td><td>%s</td><td>%s</td></tr>'
              % (L.esc(c.sname(ct["sid"])), L.esc(ct.get("name")), L.esc(ct.get("start", "")), L.esc(ct.get("end", "")),
                 cls, L.esc(st), L.esc(ct.get("scope", "")), L.esc(ct.get("holder", "")), L.esc(rel)))
        A('</tbody></table></div>')
        A('<div class="note">依据：巨潮资讯网年报“相关批复、许可、资质及有效期的情况”。未在表中的企业 = 公开渠道未取得其许可清单，'
          '不等于没有相关证照。</div>')
        A('</div></section>')

    # ---------------- quotes ----------------
    A('<section class="card" id="sec-q"><div class="card-h"><span class="no">08</span>'
      '<div><h2>商业条款对比（报价）</h2><div class="sub">%s</div></div></div><div class="card-b">' %
      L.esc(c.quotes.get("status_note") or ("已收到 %d 家报价" % len(c.quotes.get("received", []))) if c.quotes.get("received") else "本次未取得任何报价"))
    A('<div class="tw"><table class="tb"><thead><tr><th>条款</th>')
    for s in sups:
        A('<th>%s</th>' % L.esc(s.get("short")))
    A('</tr></thead><tbody>')
    for t in c.terms:
        A('<tr><td><b>%s</b></td>' % L.esc(t["label"]))
        for s in sups:
            cell = c.term_cells[t["key"]][s["id"]]
            v = L.esc(cell.get("v", "")) or '<span style="color:var(--faint)">—</span>'
            A('<td>%s %s<div class="evs" style="margin-top:3px">%s</div></td>' % (
                status_chip(cell.get("status", "pending")), v, c.evchips(findall_ids(cell.get("ev", "")))))
        A('</tr>')
    A('</tbody></table></div>')
    A('<div class="note warn">为什么没有价格：%s</div>' % L.frag(c.quotes.get("note", "未收到报价单。")))
    if c.quotes.get("received"):
        A('<div class="subh">已收到的报价文件</div><div class="mini"><p>')
        for q in c.quotes["received"]:
            A('· %s：%s（%s）<br>' % (L.esc(q.get("supplier")), L.esc(q.get("file")), L.esc(q.get("date"))))
        A('</p></div>')
    A('</div></section>')

    # ---------------- questions ----------------
    A('<section class="card" id="sec-questions"><div class="card-h"><span class="no">09</span>'
      '<div><h2>逐家问询问题清单</h2><div class="sub">按供应商分组，可直接复制或下载；每条问题都注明“为什么要问”</div></div>'
      '<div class="right"><button class="btn" data-copy="qTextAll">复制全部</button><button class="btn" data-dl="qTextAll" data-name="问询问题清单_全部供应商.txt">下载全部</button></div></div>')
    A('<div class="card-b">')
    A('<div class="qtabs">')
    for s in sups:
        num = sum(1 for q in c.q_all if q["sid"] == s["id"])
        A('<button class="btn" data-goto="q-%s">%s（%d 条）</button>' % (L.esc(s["id"]), L.esc(s.get("short")), num))
    A('</div>')
    for s in sups:
        qs = [q for q in c.q_all if q["sid"] == s["id"]]
        A('<div id="q-%s"><div class="subh" style="display:flex;align-items:center;gap:8px">%s · %s'
          '<button class="btn" style="margin-left:auto" data-copy="qText-%s">复制</button>'
          '<button class="btn" data-dl="qText-%s" data-name="询证问题清单_%s.txt">下载</button></div>'
          % (L.esc(s["id"]), L.esc(s.get("name")), L.esc(s.get("code", "")), L.esc(s["id"]), L.esc(s["id"]),
             L.esc(s.get("short", s["id"]))))
        A('<div class="qb">')
        for q in qs:
            pr = q.get("priority", "中")
            A('<div class="qrow"><div class="i">%s</div><div><span class="pri pri-%s">%s优先</span></div>'
              '<div><div class="q">%s</div><div class="w">依据 / 为什么要问：%s</div></div></div>'
              % (L.esc(q.get("no", "").split("-")[-1]), {"高": "h", "中": "m", "低": "l"}.get(pr, "m"), L.esc(pr),
                 L.frag(q.get("q", "")), L.frag(q.get("why", ""))))
        A('</div></div>')
    A('</div></section>')

    # ---------------- next actions ----------------
    if c.actions:
        A('<section class="card" id="sec-act"><div class="card-h"><span class="no">10</span>'
          '<div><h2>下一步动作</h2><div class="sub">把问询、验厂与报价回收排成有责任人和时限的动作</div></div></div><div class="card-b">')
        A('<div class="tw"><table class="tb"><thead><tr><th>#</th><th>动作</th><th>责任</th><th>时限</th><th>对象</th></tr></thead><tbody>')
        for a in c.actions:
            A('<tr><td class="mono">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
              % (L.esc(a.get("no")), L.frag(a.get("action")), L.esc(a.get("owner", "")), L.esc(a.get("due", "")), L.esc(a.get("target", ""))))
        A('</tbody></table></div></div></section>')

    # ---------------- evidence ----------------
    A('<section class="card" id="sec-ev"><div class="card-h"><span class="no">11</span>'
      '<div><h2>证据索引</h2><div class="sub">%d 条；正文中出现的每个编号都能在这里打开原文</div></div></div><div class="card-b">' % len(c.ev))
    types = {}
    for e in data.get("evidence", []):
        types.setdefault(e.get("type", "其他"), []).append(e)
    A('<div class="tw"><table class="tb"><thead><tr><th style="width:60px">编号</th><th>文件</th><th style="width:120px">来源</th>'
      '<th style="width:88px">日期</th><th style="width:96px">类型</th><th>支撑了什么</th></tr></thead><tbody>')
    for tid, lst in types.items():
        for e in lst:
            A('<tr id="ev-%s"><td class="mono"><a href="%s" target="_blank" rel="noopener">%s</a></td>'
              '<td><b>%s</b></td><td>%s</td><td class="mono">%s</td><td>%s</td><td style="color:var(--muted)">%s</td></tr>'
              % (L.esc(e["id"]), L.esc(e.get("url", "#")), L.esc(e["id"]), L.esc(e.get("name")), L.esc(e.get("source", "")),
                 L.esc(e.get("date", "")), L.esc(e.get("type", "")), L.esc(e.get("note", ""))))
    A('</tbody></table></div>')
    A('</div></section>')

    A('<footer><div class="wrap">')
    A('<b>使用边界：</b>%s<br>' % L.esc(m.get("use_note", "")))
    A('<b>口径：</b>全文唯一时间基准 %s；风险等级是“对本次采购的潜在影响”，不是企业整体评级；“无法核实”不等于“不存在”。<br>' % L.esc(m.get("as_of")))
    A('<b>编制：</b>%s · %s · 文档编号 %s · 生成于 %s' % (L.esc(m.get("prepared_by", "")), L.esc(m.get("version", "")),
                                                 L.esc(m.get("doc_no", "")), datetime.date.today().isoformat()))
    A('</div></footer>')
    A('<div class="toast" id="toast"></div>')

    # hidden text blobs for copy/download
    A('<textarea id="mxText" style="position:absolute;left:-9999px;top:0;width:1px;height:1px" aria-hidden="true">')
    A(matrix_text(c))
    A('</textarea>')
    for s in sups:
        A('<textarea id="qText-%s" style="position:absolute;left:-9999px;top:0;width:1px;height:1px" aria-hidden="true">' % L.esc(s["id"]))
        A(question_text(c, s["id"]))
        A('</textarea>')
    A('<textarea id="qTextAll" style="position:absolute;left:-9999px;top:0;width:1px;height:1px" aria-hidden="true">')
    A("\n\n".join(question_text(c, s["id"]) for s in sups))
    A('</textarea>')

    A('<script>%s</script></body></html>' % JS)
    return "".join(parts)


def dim_label(c, key):
    for d in c.dims:
        if d["key"] == key:
            return d["label"]
    return key


def render_dossier(c, s):
    sid = s["id"]
    pr = L.PRODUCER.get(s.get("producer", "unknown"), L.PRODUCER["unknown"])
    o = []
    o.append('<div class="sup">')
    o.append('<div class="sup-h"><div class="av">%s</div><div class="nm"><h3>%s</h3>'
             '<div class="meta">%s%s</div></div>%s %s<span class="cv-btn">▾</span></div>'
             % (L.esc(sid), L.esc(s.get("name")), L.esc(s.get("code", "")),
                (" · " + L.esc(s.get("track", ""))) if s.get("track") else "",
                pill(pr["cn"], pr["color"]), pill("%d 条证据" % c.evidence_count(sid), "blue")))
    o.append('<div class="sup-b">')
    o.append('<div class="tiers">')
    for t in s.get("tiers") or []:
        o.append('<div class="tier"><div class="t1">%s %s</div><div class="t2">%s</div><div class="t3">%s</div></div>'
                 % (L.esc(t[0]) if len(t) > 0 else "", L.esc(t[1]) if len(t) > 1 else "",
                    L.esc(t[2]) if len(t) > 2 else "", L.esc(t[3]) if len(t) > 3 else ""))
    o.append('</div>')
    o.append('<div class="kv">')
    kv = [("全称", s.get("name", "")), ("所属集团 / 控制关系", s.get("group", "")),
          ("证券代码 / 上市状态", "%s · %s" % (s.get("code", ""), s.get("track", ""))),
          ("生产基地", s.get("site", "")),
          ("到收货地距离", "%s（直线/公路估算，非精确路线里程）" % s.get("plant_to_dest_km", "")),
          ("厂家身份判定", "%s —— %s" % (pr["cn"], s.get("producer_note", ""))),
          ("证据基础", s.get("evidence_note", "")),
          ("一句话判断", s.get("summary", ""))]
    for i, (k, v) in enumerate(kv):
        cls = ' class="lasts"' if i == len(kv) - 1 else ""
        o.append('<div%s>%s</div><div%s>%s</div>' % (cls.replace("lasts", "").replace("class=\"\"", ""),
                                                    L.esc(k), cls, L.frag(v)))
    o.append('</div>')

    # 该企业各维度
    o.append('<div class="subh">本企业在各维度上的信息</div><div class="kv">')
    for di, dim in enumerate(c.dims):
        if dim.get("type") == "terms":
            cell = c.term_cells.get("price", {}).get(sid, {})
            o.append('<div>%02d %s</div><div>%s %s</div>' % (di + 1, L.esc(dim["label"]),
                                                             status_chip(cell.get("status", "pending")),
                                                             L.esc(cell.get("v", "") or "见第 09 节")))
            continue
        cell = c.cells[dim["key"]][sid]
        lbs = c.labels[(dim["key"], sid)]
        chips = " ".join(pill(L.LABELS[x]["cn"], L.LABELS[x]["color"]) for x in lbs)
        lv = lvl_chip(cell.get("lvl")) if cell.get("lvl") else ""
        o.append('<div>%02d %s</div><div>%s %s %s</div>' % (di + 1, L.esc(dim["label"]), lv, L.frag(cell["v"]), chips))
    o.append('</div>')

    # 许可
    my = [x for x in c.certs if x["sid"] == sid]
    if my:
        o.append('<div class="subh">公开可查的许可 / 资质（%d 项）</div><div class="tw"><table class="tb">'
                 '<thead><tr><th>证照</th><th>有效期</th><th>状态</th><th>范围</th><th>持有人</th></tr></thead><tbody>' % len(my))
        for ct in my:
            st, tone = L.cert_state(ct.get("end"), c.as_of)
            cls = {"expired": "lv-high", "soon": "lv-mid", "valid": "lv-low"}.get(tone, "lv-none")
            o.append('<tr><td>%s</td><td class="mono">%s – %s</td><td><span class="lv %s">%s</span></td><td>%s</td><td>%s</td></tr>'
                     % (L.esc(ct.get("name")), L.esc(ct.get("start", "")), L.esc(ct.get("end", "")), cls, L.esc(st),
                        L.esc(ct.get("scope", "")), L.esc(ct.get("holder", ""))))
        o.append('</tbody></table></div>')
    else:
        o.append('<div class="subh">公开可查的许可 / 资质</div><div class="note warn">'
                 '公开渠道未取得该企业的许可清单，全部许可证照列为“待索取”（见问询清单）。注意：'
                 '<b>经营范围里出现“碳酸钠/该品类”不能证明其具备该产品的实际生产能力</b>。</div>')

    # 该企业的问题
    qs = [q for q in c.q_all if q["sid"] == sid]
    if qs:
        o.append('<div class="subh">需向本企业书面确认的问题（%d 条，完整版见第 09 节）</div><div class="mini"><p>' % len(qs))
        o.append("<br>".join("%s %s" % (L.esc(q.get("no", "").split("-")[-1]), L.frag(q.get("q", ""))) for q in qs))
        o.append('</p></div>')
    o.append('</div></div>')
    return "".join(o)


def matrix_text(c):
    lines = []
    m = c.meta
    lines.append("%s —— %s" % (m.get("title", "供应商横向比较"), m.get("product", "")))
    lines.append("数据截止：%s｜数量：%s｜收货地：%s" % (m.get("as_of"), c.req.get("qty", ""), c.req.get("destination", "")))
    lines.append("")
    head = ["比较维度"] + ["%s（%s）" % (s.get("short"), s.get("code", "")) for s in c.suppliers]
    lines.append(" | ".join(head))
    lines.append("-" * 80)
    for di, dim in enumerate(c.dims):
        row = ["%02d %s" % (di + 1, dim["label"])]
        for s in c.suppliers:
            if dim.get("type") == "terms":
                cell = c.term_cells.get("price", {}).get(s["id"], {})
                row.append("[%s] %s" % (L.STATUS.get(cell.get("status", "pending"), {}).get("cn"), strip_tags(cell.get("v", ""))))
            else:
                cell = c.cells[dim["key"]][s["id"]]
                tags = "/".join(L.LABELS[x]["cn"] for x in c.labels[(dim["key"], s["id"])])
                row.append("[%s] %s" % (tags, strip_tags(cell["v"])))
        lines.append(" | ".join(row))
    return "\n".join(lines)


def question_text(c, sid):
    s = c.supplier(sid)
    qs = [q for q in c.q_all if q["sid"] == sid]
    m = c.meta
    lines = ["%s 供应商询证问题清单" % s.get("short", sid), "=" * 40,
             "致：%s" % s.get("name", ""),
             "采购标的：%s" % (c.req.get("product", "") or m.get("product", "")),
             "数量：%s；收货地：%s" % (c.req.get("qty", ""), c.req.get("destination", "")),
             "数据截止：%s；本清单编号：%s" % (m.get("as_of", ""), m.get("doc_no", "")),
             "",
             "说明：以下问题仅为核实公开信息中的差异与不确定项，不构成任何采购承诺。请逐条书面回复并附证明文件。",
             ""]
    for q in qs:
        lines.append("%s【%s优先】%s" % (q.get("no", ""), q.get("priority", "中"), strip_tags(q.get("q"))))
        if q.get("why"):
            lines.append("     依据：%s" % strip_tags(q.get("why")))
    lines.append("")
    lines.append("回复方式：加盖公章的扫描件 + 电子版，于收悉后 5 个工作日内回复。")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("usage: python render_html.py data.json out.html")
        raise SystemExit(2)
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    html = render(data)
    out = sys.argv[2]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML -> %s (%.1f KB)" % (out, len(html.encode("utf-8")) / 1024))


if __name__ == "__main__":
    main()
