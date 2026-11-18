# -*- coding: utf-8 -*-
"""
build_html.py — 由 followup.json 生成自包含 HTML 跟进卡

用法：
    python build_html.py followup.json -o 输出.html

纯标准库；生成的 HTML 无外部 CSS/JS/字体，可离线双击打开、可打印为 PDF。
产品无关：所有文案来自 JSON。
"""
import argparse
import html
import json
import sys

from _common import (
    cat_color, tone_color, parse_as_of, compute_stall_days, promise_state,
    days_left, validate, CATEGORY_NAMES,
)

E = html.escape


CSS = """
  :root{
    --ink:#0b1220; --ink2:#16233a; --body:#243247; --muted:#64748b; --faint:#93a3b8;
    --line:#e3e8ef; --line2:#cfd8e3; --bg:#f4f6f9; --card:#ffffff;
    --brand:#0d3b4f; --brand2:#14617d; --brand3:#e8f2f6;
    --gold:#b7822b; --gold-l:#fdf6e8;
    --ai:#5b6b7c; --ai-bg:#f1f4f8;
    --prom:#0f7a52; --prom-bg:#e9f8f1;
    --obj:#c02626; --obj-bg:#fdeeee;
    --req:#1d4ed8; --req-bg:#eef3ff;
    --pend:#6d28d9; --pend-bg:#f3eeff;
    --ours:#a85a08; --ours-bg:#fdf1e3;
    --r:14px; --sh:0 1px 2px rgba(15,23,42,.04),0 8px 24px -12px rgba(15,23,42,.16);
    --mono:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--body);
    font-family:"Microsoft YaHei","PingFang SC","Hiragino Sans GB","Source Han Sans SC",-apple-system,"Segoe UI",Roboto,sans-serif;
    font-size:15px;line-height:1.72;-webkit-font-smoothing:antialiased}
  h1,h2,h3,h4{margin:0;color:var(--ink);font-weight:700;letter-spacing:-.01em;line-height:1.35}
  a{color:var(--brand2);text-decoration:none}
  .wrap{max-width:1180px;margin:0 auto;padding:0 24px}
  .topbar{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.88);
    backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--line)}
  .topbar .wrap{display:flex;align-items:center;gap:18px;height:56px}
  .tb-brand{display:flex;align-items:center;gap:9px;font-weight:700;color:var(--ink);font-size:14px;white-space:nowrap}
  .tb-dot{width:9px;height:9px;border-radius:3px;background:var(--gold);box-shadow:0 0 0 3px var(--gold-l)}
  .tb-nav{display:flex;gap:2px;overflow:auto;scrollbar-width:none;flex:1}
  .tb-nav::-webkit-scrollbar{display:none}
  .tb-nav a{font-size:13px;color:var(--muted);padding:6px 10px;border-radius:8px;white-space:nowrap;transition:.16s}
  .tb-nav a:hover{background:var(--brand3);color:var(--brand)}
  .tb-act{display:flex;gap:8px;flex-shrink:0}
  .btn{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line2);background:#fff;
    color:var(--ink2);font:inherit;font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:9px;
    cursor:pointer;transition:.16s;white-space:nowrap}
  .btn:hover{border-color:var(--brand2);color:var(--brand2);background:var(--brand3)}
  .btn-primary{background:var(--brand);border-color:var(--brand);color:#fff}
  .btn-primary:hover{background:var(--brand2);border-color:var(--brand2);color:#fff}
  .btn.sm{font-size:11.5px;padding:4px 9px;border-radius:7px}
  .hero{position:relative;overflow:hidden;color:#dbe7ee;
    background:radial-gradient(1100px 420px at 82% -18%,rgba(29,111,139,.55),transparent 62%),
      radial-gradient(760px 340px at 4% 118%,rgba(183,130,43,.20),transparent 60%),
      linear-gradient(158deg,#08222e 0%,#0d3b4f 46%,#114f66 100%)}
  .hero::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.30;
    background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);
    background-size:44px 44px;
    mask-image:radial-gradient(60% 80% at 50% 30%,#000 35%,transparent 100%)}
  .hero .wrap{position:relative;z-index:2;padding-top:34px;padding-bottom:36px}
  .eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:11.5px;font-weight:700;letter-spacing:.14em;
    text-transform:uppercase;color:#f3d49a;background:rgba(255,255,255,.07);
    border:1px solid rgba(243,212,154,.32);padding:5px 11px;border-radius:999px}
  .hero h1{color:#fff;font-size:31px;margin:14px 0 6px;letter-spacing:-.02em}
  .hero h1 small{font-size:15px;font-weight:600;color:#9fc3d3;letter-spacing:0;margin-left:8px}
  .hero .sub{color:#a9c6d4;font-size:13.5px}
  .hero .sub b{color:#fff;font-weight:600}
  .oneliner{margin-top:18px;display:flex;gap:12px;align-items:flex-start;max-width:940px;
    background:linear-gradient(90deg,rgba(255,255,255,.10),rgba(255,255,255,.03));
    border:1px solid rgba(255,255,255,.14);border-left:3px solid #e0a94a;
    padding:13px 16px;border-radius:0 12px 12px 0}
  .oneliner .k{font-size:11px;font-weight:800;letter-spacing:.1em;color:#e0a94a;white-space:nowrap;padding-top:2px}
  .oneliner p{margin:0;color:#eaf2f6;font-size:14px;line-height:1.7}
  .oneliner b{color:#fff;background:rgba(224,169,74,.2);padding:0 4px;border-radius:4px;font-weight:700}
  .hero-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
  .chip{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:600;color:#dbe9ef;
    background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);padding:5px 11px;border-radius:8px}
  .chip i{width:7px;height:7px;border-radius:50%;background:#7fd3ad;display:inline-block}
  .chip.warn i{background:#f0b45c}
  .chip.risk i{background:#f27979}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:-26px;position:relative;z-index:5}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:15px 16px 14px;
    box-shadow:var(--sh);position:relative;overflow:hidden}
  .kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--brand2)}
  .kpi.k3::before{background:var(--obj)} .kpi.k4::before{background:var(--obj)}
  .kpi .lab{font-size:11.5px;font-weight:700;letter-spacing:.08em;color:var(--faint);text-transform:uppercase}
  .kpi .val{font-size:22px;font-weight:800;color:var(--ink);margin:6px 0 2px;letter-spacing:-.02em}
  .kpi .val.s{font-size:17px;line-height:1.45}
  .kpi .note{font-size:12px;color:var(--muted)}
  section{margin-top:38px}
  .sec-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:14px;flex-wrap:wrap}
  .sec-head h2{font-size:19px;display:flex;align-items:center;gap:10px}
  .sec-head h2 .ix{font:700 11px/1 var(--mono);color:#fff;background:var(--brand2);
    padding:5px 7px;border-radius:6px;letter-spacing:.04em}
  .sec-head .desc{font-size:12.5px;color:var(--muted);max-width:660px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--sh)}
  .grid-info{display:grid;grid-template-columns:repeat(2,1fr);gap:0 40px;padding:8px 22px 18px}
  .row-i{display:grid;grid-template-columns:110px 1fr;gap:14px;padding:10px 0;border-bottom:1px dashed var(--line)}
  .row-i:last-child{border-bottom:0}
  .row-i dt{font-size:12.5px;color:var(--faint);font-weight:700}
  .row-i dd{margin:0;font-size:13.5px;color:var(--ink2)}
  .row-i dd em{font-style:normal;color:var(--muted);font-size:12px}
  .stage-box{padding:24px 24px 18px}
  .track{display:grid;grid-template-columns:repeat(6,1fr);gap:0;position:relative;margin:6px 0 4px}
  .track::before{content:"";position:absolute;left:8%;right:8%;top:15px;height:3px;border-radius:2px;
    background:linear-gradient(90deg,var(--prom) 0 var(--prog,58%),var(--line2) var(--prog,58%) 100%)}
  .st{position:relative;text-align:center;padding-top:34px}
  .st .dot{position:absolute;top:4px;left:50%;transform:translateX(-50%);
    width:24px;height:24px;border-radius:50%;background:#fff;border:3px solid var(--line2);
    display:grid;place-items:center;font-size:11px;font-weight:800;color:var(--faint);z-index:2}
  .st.done .dot{background:var(--prom);border-color:var(--prom);color:#fff}
  .st.done .dot::after{content:"\\2713"}
  .st.now .dot{background:#fff;border-color:var(--gold);color:var(--gold);box-shadow:0 0 0 6px rgba(183,130,43,.16)}
  .st.now .dot::after{content:"\\25CF"}
  .st.risk .dot{border-color:var(--obj);color:var(--obj);border-style:dashed}
  .st .t{font-size:13px;font-weight:700;color:var(--ink2)}
  .st.now .t{color:var(--gold)}
  .st .d{font-size:11.5px;color:var(--faint);margin-top:1px}
  .stage-note{margin-top:18px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;
    border-top:1px solid var(--line);padding-top:16px}
  .sn{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
  .sn .h{font-size:11.5px;font-weight:800;letter-spacing:.06em;color:var(--faint);margin-bottom:4px}
  .sn p{margin:0;font-size:12.8px;color:var(--ink2);line-height:1.65}
  .sn.warn{background:var(--obj-bg);border-color:#f3c9c9}
  .sn.warn .h{color:var(--obj)}
  .sn.ok{background:var(--prom-bg);border-color:#bfe6d4}
  .sn.ok .h{color:var(--prom)}
  .blockers{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
  .blk{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px;box-shadow:var(--sh)}
  .blk .top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}
  .blk h3{font-size:14.5px}
  .tag{font-size:11px;font-weight:800;letter-spacing:.04em;padding:3px 8px;border-radius:6px;white-space:nowrap}
  .tag.risk{background:var(--obj-bg);color:var(--obj)}
  .tag.warn{background:var(--ours-bg);color:var(--ours)}
  .tag.ok{background:var(--prom-bg);color:var(--prom)}
  .tag.info{background:var(--req-bg);color:var(--req)}
  .blk p{margin:0 0 10px;font-size:13px;color:var(--muted);line-height:1.7}
  .blk .facts{display:flex;flex-wrap:wrap;gap:14px;padding-top:10px;border-top:1px dashed var(--line)}
  .blk .facts div{font-size:11.5px;color:var(--faint)}
  .blk .facts b{display:block;font-size:15px;color:var(--ink);font-weight:800;letter-spacing:-.01em}
  .filters{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:16px}
  .fchip{font-size:12px;font-weight:700;padding:5px 11px;border-radius:999px;cursor:pointer;
    border:1px solid var(--line2);background:#fff;color:var(--muted);transition:.15s;user-select:none}
  .fchip:hover{border-color:var(--brand2);color:var(--brand2)}
  .fchip[aria-pressed="true"]{background:var(--brand);border-color:var(--brand);color:#fff}
  .fchip .c{font-variant-numeric:tabular-nums;opacity:.72;margin-left:3px}
  .fsep{width:1px;height:18px;background:var(--line2);margin:0 4px}
  .tl-item{display:grid;grid-template-columns:104px 30px 1fr;gap:0;align-items:stretch}
  .tl-time{padding:0 12px 22px 0;text-align:right}
  .tl-time .d{font:700 12.5px var(--mono);color:var(--ink2);letter-spacing:-.02em}
  .tl-time .t{font:600 11px var(--mono);color:var(--faint)}
  .tl-mid{position:relative;display:flex;justify-content:center}
  .tl-mid::before{content:"";position:absolute;top:0;bottom:0;width:2px;background:var(--line2)}
  .tl-item:first-child .tl-mid::before{top:9px}
  .tl-item:last-child .tl-mid::before{bottom:calc(100% - 9px)}
  .tl-mid i{position:absolute;top:5px;width:11px;height:11px;border-radius:50%;background:#fff;
    border:2.5px solid #475569;z-index:2}
  .tl-body{padding:0 0 22px 16px}
  .tl-card{background:var(--card);border:1px solid var(--line);border-left:3px solid #475569;
    border-radius:0 12px 12px 0;padding:11px 15px;box-shadow:0 1px 2px rgba(15,23,42,.04);transition:.16s}
  .tl-card:hover{box-shadow:var(--sh);border-color:var(--line2)}
  .tl-card .meta{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:5px}
  .cat{font-size:10.5px;font-weight:800;letter-spacing:.05em;padding:2px 7px;border-radius:5px}
  .src{font:600 10.5px var(--mono);color:var(--faint);background:var(--bg);border:1px solid var(--line);padding:1px 6px;border-radius:5px}
  .tl-card .txt{font-size:13.5px;color:var(--ink2);line-height:1.7}
  .tl-card .txt q{font-style:normal;color:var(--ink);background:#fffbe8;padding:0 3px;border-radius:3px}
  .flag{font-size:10.5px;font-weight:800;color:var(--obj);background:var(--obj-bg);padding:1px 6px;border-radius:5px}
  .tabs{display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:0}
  .tab{font:inherit;font-size:13px;font-weight:700;color:var(--muted);background:none;border:0;cursor:pointer;
    padding:9px 14px;border-radius:9px 9px 0 0;border-bottom:2.5px solid transparent;transition:.15s}
  .tab:hover{color:var(--ink2);background:var(--bg)}
  .tab[aria-selected="true"]{color:var(--brand);background:#fff;border-bottom-color:var(--brand2)}
  .tab .n{font-size:11px;font-weight:800;background:var(--bg);border:1px solid var(--line);border-radius:999px;padding:1px 6px;margin-left:5px;color:var(--muted)}
  .tab[aria-selected="true"] .n{background:var(--brand3);border-color:#cfe3ea;color:var(--brand2)}
  .panel{display:none;padding-top:2px}
  .panel.on{display:block}
  table{width:100%;border-collapse:collapse;font-size:13.2px}
  thead th{text-align:left;font-size:11.5px;font-weight:800;letter-spacing:.06em;color:var(--faint);
    text-transform:uppercase;padding:9px 12px;background:var(--bg);border-bottom:1px solid var(--line2);white-space:nowrap}
  tbody td{padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top;color:var(--ink2);line-height:1.65}
  tbody tr:hover td{background:#fbfcfe}
  tbody tr:last-child td{border-bottom:0}
  td.k{font-weight:700;color:var(--ink);white-space:nowrap}
  td.src-cell{font:600 11.5px var(--mono);color:var(--muted);white-space:nowrap}
  td.q{color:var(--ink)}
  .tbl-wrap{overflow-x:auto}
  .callout{display:flex;gap:11px;align-items:flex-start;background:var(--gold-l);border:1px solid #f0dfb8;
    border-radius:11px;padding:12px 15px;margin-top:14px;font-size:13px;color:#6b4d14;line-height:1.7}
  .callout .ic{font-size:15px;line-height:1.4}
  .callout b{color:#57390a}
  .callout.danger{background:var(--obj-bg);border-color:#f3c9c9;color:#7f1d1d}
  .callout.danger b{color:#6b1212}
  .callout.info{background:var(--req-bg);border-color:#d3dffa;color:#1e3a8a}
  .callout.info b{color:#172554}
  .ai-card{background:linear-gradient(180deg,#f8fafc,#f2f5f9);border:1px dashed #b8c4d2;border-radius:var(--r);
    padding:20px 22px;position:relative}
  .ai-head{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
  .ai-badge{font-size:11px;font-weight:800;letter-spacing:.08em;color:#fff;background:var(--ai);
    padding:4px 9px;border-radius:6px}
  .ai-head h3{font-size:15px}
  .ai-head .warn-txt{font-size:11.5px;color:var(--muted)}
  .ai-card p{margin:0 0 12px;font-size:13.8px;color:#334155;line-height:1.85}
  .ai-card p:last-child{margin-bottom:0}
  .ai-card b{color:var(--ink)}
  .ai-pts{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}
  .ai-pt{background:#fff;border:1px solid #dbe2ea;border-radius:10px;padding:12px 13px}
  .ai-pt .h{font-size:11px;font-weight:800;letter-spacing:.07em;color:var(--ai);margin-bottom:5px}
  .ai-pt p{margin:0;font-size:12.6px;line-height:1.7;color:#475569}
  .unknown{border:1px solid #f3c9c9;border-radius:var(--r);overflow:hidden;background:#fff}
  .unknown .uh{background:linear-gradient(90deg,#fdf0f0,#fff8f4);padding:13px 20px;border-bottom:1px solid #f3d9d0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .unknown .uh h3{font-size:14.5px;color:#8a1f1f}
  .unknown .uh span{font-size:12px;color:#a15c50}
  .conf-bar{display:flex;align-items:center;gap:14px;padding:14px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}
  .prog{flex:1;min-width:180px;height:8px;border-radius:999px;background:var(--line);overflow:hidden}
  .prog i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--brand2),var(--prom));transition:width .35s ease;border-radius:999px}
  .conf-bar .txt{font-size:12.5px;color:var(--muted);white-space:nowrap}
  .conf-bar .txt b{color:var(--ink);font-variant-numeric:tabular-nums}
  input[type=checkbox]{width:16px;height:16px;accent-color:var(--prom);cursor:pointer;margin:0}
  .cf{display:flex;align-items:center;gap:9px}
  tr.checked td{background:#f4fbf7}
  tr.checked td.k::after{content:" \\2713";color:var(--prom);font-weight:800}
  .conf-tag{font-size:10.5px;font-weight:800;padding:2px 6px;border-radius:5px;white-space:nowrap}
  .prio{display:inline-flex;align-items:center;justify-content:center;min-width:34px;font-size:11px;font-weight:900;padding:3px 7px;border-radius:6px}
  .p0{background:var(--obj);color:#fff} .p1{background:#d97706;color:#fff} .p2{background:#94a3b8;color:#fff}
  .linked-panel{display:none;margin-top:10px;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:13px 15px;font-size:13px}
  .linked-panel.on{display:block}
  .linked-panel .ph{font-size:11.5px;font-weight:800;letter-spacing:.06em;color:var(--faint);margin-bottom:7px;display:flex;justify-content:space-between;align-items:center;gap:10px}
  .linked-panel p{margin:0 0 8px;line-height:1.75;color:var(--ink2)}
  .linked-panel p:last-child{margin-bottom:0}
  .linked-panel ul{margin:0;padding-left:18px;color:var(--ink2)}
  .linked-panel li{margin-bottom:5px;line-height:1.65}
  .draft{background:#0e2a33;color:#dbe9ef;border-radius:11px;padding:16px 18px;font-size:13.4px;line-height:1.85;
    border:1px solid #17414f;position:relative;margin-top:16px}
  .draft .dh{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:9px;font-size:11.5px;color:#8fb6c6;letter-spacing:.06em;font-weight:700}
  .draft q{font-style:normal;color:#fff}
  .src-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:18px 20px}
  .src-c{background:var(--bg);border:1px solid var(--line);border-radius:11px;padding:13px 14px}
  .src-c .n{font-size:11px;font-weight:800;color:var(--faint);letter-spacing:.06em}
  .src-c .t{font-size:13.5px;font-weight:700;color:var(--ink);margin:3px 0 2px}
  .src-c .m{font-size:11.5px;color:var(--muted)}
  .src-c .c{font-size:19px;font-weight:800;color:var(--brand2);margin-top:6px;font-variant-numeric:tabular-nums}
  footer{margin:44px 0 0;padding:24px 0 40px;border-top:1px solid var(--line);color:var(--faint);font-size:12px;line-height:1.9}
  footer b{color:var(--muted)}
  .toast{position:fixed;left:50%;bottom:28px;transform:translate(-50%,16px);opacity:0;pointer-events:none;
    background:var(--ink);color:#fff;font-size:13px;font-weight:600;padding:10px 18px;border-radius:999px;
    box-shadow:0 12px 32px -8px rgba(15,23,42,.5);transition:.25s;z-index:99}
  .toast.on{opacity:1;transform:translate(-50%,0)}
  @media (max-width:900px){
    .kpis{grid-template-columns:repeat(2,1fr)}
    .grid-info,.blockers,.stage-note,.ai-pts,.src-grid{grid-template-columns:1fr}
    .grid-info{gap:0}
    .track{grid-template-columns:repeat(3,1fr);row-gap:16px}
    .track::before{display:none}
    .hero h1{font-size:24px}
    .tl-item{grid-template-columns:78px 24px 1fr}
    .tb-nav{display:none}
  }
  @media print{
    body{background:#fff;font-size:11pt}
    .topbar,.tb-act,.filters,.fsep,.btn,.toast{display:none!important}
    .hero{background:#0d3b4f!important}
    .kpis{margin-top:14px}
    .card,.kpi,.blk,.tl-card,.unknown,.ai-card{box-shadow:none}
    section{break-inside:avoid;margin-top:20px}
    .panel{display:block!important}
    .tabs{display:none}
    a{color:inherit}
    *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  }
"""

JS = """
(function(){
  "use strict";
  var chips = document.querySelectorAll('#filters .fchip');
  var items = document.querySelectorAll('#tl .tl-item');
  chips.forEach(function(btn){
    btn.addEventListener('click', function(){
      chips.forEach(function(b){ b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); });
      var cat = btn.getAttribute('data-cat');
      items.forEach(function(it){
        it.style.display = (cat === 'all' || it.getAttribute('data-cat') === cat) ? '' : 'none';
      });
    });
  });
  var tabs = document.querySelectorAll('.tab');
  tabs.forEach(function(t){
    t.addEventListener('click', function(){
      tabs.forEach(function(x){ x.setAttribute('aria-selected', x === t ? 'true' : 'false'); });
      document.querySelectorAll('.panel').forEach(function(p){ p.classList.remove('on'); });
      var el = document.getElementById(t.getAttribute('data-panel'));
      if (el) el.classList.add('on');
    });
  });
  document.querySelectorAll('[data-link]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var el = document.getElementById(btn.getAttribute('data-link'));
      if (!el) return;
      var open = el.classList.contains('on');
      document.querySelectorAll('.linked-panel').forEach(function(p){ p.classList.remove('on'); });
      if (!open) el.classList.add('on');
    });
  });
  var toast = document.getElementById('toast');
  var timer = null;
  function showToast(msg){
    if (!toast) return;
    toast.textContent = msg || '已复制';
    toast.classList.add('on');
    clearTimeout(timer);
    timer = setTimeout(function(){ toast.classList.remove('on'); }, 1800);
  }
  document.querySelectorAll('[data-copy]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var src = document.getElementById(btn.getAttribute('data-copy'));
      var text = src ? (src.innerText || src.textContent || '') : '';
      text = text.replace(/第[\\s\\S]*?可直接复制/, '').trim();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function(){ showToast('已复制到剪贴板'); })
          .catch(function(){ showToast('复制失败，请手动选择文本'); });
      } else { showToast('复制失败，请手动选择文本'); }
    });
  });
  var KEY = document.body.getAttribute('data-confirm-key') || 'followup-confirm';
  var boxes = Array.prototype.slice.call(document.querySelectorAll('#confBody input[type=checkbox]'));
  var numEl = document.getElementById('confNum');
  var barEl = document.getElementById('confBar');
  var totEl = document.getElementById('confTot');
  if (totEl) totEl.textContent = boxes.length;
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch(e){ saved = {}; }
  function paint(){
    var n = 0;
    boxes.forEach(function(b){
      var tr = b.closest('tr');
      if (b.checked) { n++; tr.classList.add('checked'); } else { tr.classList.remove('checked'); }
    });
    if (numEl) numEl.textContent = n;
    if (barEl) barEl.style.width = (boxes.length ? (n / boxes.length * 100) : 0) + '%';
  }
  boxes.forEach(function(b){
    b.checked = !!saved[b.id];
    b.addEventListener('change', function(){
      saved[b.id] = b.checked;
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch(e){}
      paint();
      var tr = b.closest('tr');
      var k = tr ? (tr.querySelector('td.k') || {}).textContent : '';
      if (saved[b.id]) showToast('已确认：' + (k || ''));
    });
  });
  var reset = document.getElementById('confReset');
  if (reset) reset.addEventListener('click', function(){
    boxes.forEach(function(b){ b.checked = false; saved[b.id] = false; });
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch(e){}
    paint();
    showToast('已重置确认状态');
  });
  paint();
})();
"""


def li(items, cls=""):
    return "".join(f'<li>{x}</li>' for x in items)


def build(data):
    meta = data.get("meta") or {}
    as_of = parse_as_of(meta.get("as_of_date"))
    timeline = data.get("timeline") or []
    stage = data.get("stage") or {}
    stall = stage.get("stall") or {}
    slug = meta.get("slug") or "followup"
    title = meta.get("doc_title") or meta.get("title") or "客户跟进卡"

    computed, last_rec = compute_stall_days(timeline, as_of)
    stall_days = stall.get("days") if stall.get("days") not in (None, "") else computed
    promises = data.get("promises") or []
    overdue = [p for p in promises if promise_state(p, as_of)[1] == "risk"]
    dl = days_left(meta.get("quote_expiry"), as_of)

    # ── hero chips ──
    chips = []
    if stage.get("current"):
        chips.append(("", f'阶段：{E(stage["current"])}'))
    if stall_days is not None:
        tgt = "risk" if stall_days >= 14 else ("warn" if stall_days >= 3 else "")
        chips.append((tgt, f'停滞 {stall_days} 天'))
    if overdue:
        chips.append(("warn", f'逾期承诺 {len(overdue)} 项'))
    if dl is not None and dl >= 0:
        chips.append(("risk" if dl <= 7 else "warn", f'报价 {meta.get("quote_expiry","")} 到期（剩 {dl} 天）'))
    chips.append(("", f'素材：{len(timeline)} 条记录 / {meta.get("source_count","—")} 份'))
    chips_html = "".join(f'<span class="chip {c}"><i></i>{t}</span>' for c, t in chips)

    # ── KPI ──
    kpi_html = ""
    for i, k in enumerate((data.get("kpis") or [])[:4], 1):
        val = E(str(k.get("value", "")))
        cls = "val s" if len(str(k.get("value", ""))) > 8 or "\n" in str(k.get("value", "")) else "val"
        val = val.replace("\n", "<br>")
        kpi_html += (f'<div class="kpi k{i}"><div class="lab">{E(str(k.get("label","")))}</div>'
                     f'<div class="{cls}">{val}</div>'
                     f'<div class="note">{E(str(k.get("note","")))}</div></div>')

    # ── profile ──
    prof_html = ""
    for it in (data.get("profile") or []):
        note = f' <em>（{E(str(it["note"]))}）</em>' if it.get("note") else ""
        prof_html += (f'<div class="row-i"><dt>{E(str(it.get("label","")))}</dt>'
                      f'<dd>{E(str(it.get("value","")))}{note}</dd></div>')

    # ── stage track ──
    stages = stage.get("stages") or []
    track_html = ""
    done_n = sum(1 for s in stages if s.get("state") == "done")
    cur_i = next((i for i, s in enumerate(stages) if s.get("state") in ("current", "stalled")), done_n)
    prog = 0
    if stages:
        prog = int(max(6, min(94, (cur_i / max(1, len(stages) - 1)) * 100)))
    for s in stages:
        st = s.get("state", "todo")
        cls = {"done": "done", "current": "now", "stalled": "now risk", "risk": "risk"}.get(st, "")
        track_html += (f'<div class="st {cls}"><span class="dot"></span>'
                       f'<div class="t">{E(str(s.get("name","")))}</div>'
                       f'<div class="d">{E(str(s.get("date","")))}</div></div>')

    judgement = stage.get("judgement") or ""
    stall_reasons = "<br>".join(
        f'<b>{E(str(r.get("title","")))}</b>　{E(str(r.get("detail","")))}'
        for r in (stall.get("reasons") or []))
    if stall_days is not None and last_rec:
        stall_reasons = (f'<b>停滞 {stall_days} 天</b>（as_of {as_of.isoformat()} − 最后客户回复 '
                         f'{(last_rec or {}).get("date","")} {(last_rec or {}).get("time","")}）<br>') + stall_reasons

    stage_html = f"""
    <div class="card stage-box">
      <div class="track" style="--prog:{prog}%">{track_html}</div>
      <div class="stage-note">
        <div class="sn"><div class="h">当前阶段</div><p>{judgement}</p></div>
        <div class="sn warn"><div class="h">停滞原因</div><p>{stall_reasons}</p></div>
        <div class="sn ok"><div class="h">可复用筹码</div><p>{stage.get("assets","—")}</p></div>
      </div>
      {f'<div class="callout danger"><span class="ic">!</span><div>{stage.get("risk_note")}</div></div>' if stage.get("risk_note") else ''}
    </div>"""

    # ── blockers ──
    blk_html = ""
    for b in (data.get("blockers") or []):
        tone = b.get("status_tone", "info")
        facts = "".join(
            f'<div>{E(str(f.get("k","")))}<b class="{("r" if str(f.get("tone",""))=="risk" else ("g" if str(f.get("tone",""))=="ok" else ""))}">'
            f'{E(str(f.get("v","")))}</b></div>' for f in (b.get("facts") or []))
        blk_html += f"""
      <div class="blk">
        <div class="top"><h3>{E(str(b.get("title","")))}</h3><span class="tag {tone}">{E(str(b.get("status","")))}</span></div>
        <p>{b.get("detail","")}</p>
        {f'<div class="facts">{facts}</div>' if facts else ''}
      </div>"""

    # ── timeline ──
    cats, counts = [], {}
    for rec in timeline:
        c = str(rec.get("category") or "").strip()
        counts[c] = counts.get(c, 0) + 1
        if c not in cats:
            cats.append(c)
    order = [c for c in CATEGORY_NAMES if c in counts] + [c for c in cats if c not in CATEGORY_NAMES]
    filt = (f'<button class="fchip" data-cat="all" aria-pressed="true">全部<span class="c">{len(timeline)}</span></button>'
            '<span class="fsep"></span>')
    for c in order:
        filt += f'<button class="fchip" data-cat="{E(c)}" aria-pressed="false">{E(c)}<span class="c">{counts[c]}</span></button>'

    tl_html = ""
    for rec in timeline:
        c = str(rec.get("category") or "").strip()
        fg, bgc = cat_color(c)
        flag = (f'<span class="flag">{E(str(rec["flag"]))}</span>'
                if rec.get("flag") else "")
        tl_html += f"""
      <div class="tl-item" data-cat="{E(c)}">
        <div class="tl-time"><div class="d">{E(str(rec.get("date","")))}</div><div class="t">{E(str(rec.get("time","")))}</div></div>
        <div class="tl-mid"><i style="border-color:{fg};background:{fg if rec.get('category') in ('系统提醒',) else '#fff'}"></i></div>
        <div class="tl-body"><div class="tl-card" style="border-left-color:{fg}">
          <div class="meta"><span class="cat" style="background:{bgc};color:{fg}">{E(c)}</span>
            <span class="src">{E(str(rec.get("source","")))}</span>{flag}</div>
          <div class="txt">{rec.get("text","")}</div>
        </div></div>
      </div>"""

    # ── four tabs ──
    reqs = data.get("requirements") or []
    req_rows = ""
    for x in reqs:
        conf = str(x.get("confidence", ""))
        t = {"高": ("cf-hi", "var(--prom)", "var(--prom-bg)"),
             "中": ("cf-md", "var(--ours)", "var(--ours-bg)")}.get(
            conf, ("cf-lo", "var(--obj)", "var(--obj-bg)"))
        req_rows += (f'<tr><td class="k">{E(str(x.get("dimension","")))}</td>'
                     f'<td class="q">{x.get("content","")}</td>'
                     f'<td class="src-cell">{E(str(x.get("source","")))}</td>'
                     f'<td><span class="conf-tag" style="color:{t[1]};background:{t[2]}">{E(conf or "—")}</span></td>'
                     f'<td style="color:var(--muted);font-size:12.5px">{E(str(x.get("note","")))}</td></tr>')

    objs = data.get("objections") or []
    obj_rows = ""
    for i, x in enumerate(objs, 1):
        tone = x.get("tone", "risk")
        fg, bgc = tone_color(tone)
        obj_rows += (f'<tr><td class="k">{E(str(x.get("no", i)))}</td>'
                     f'<td>{x.get("content","")}</td>'
                     f'<td class="src-cell">{E(str(x.get("source","")))}</td>'
                     f'<td><span class="tag" style="color:{fg};background:{bgc}">{E(str(x.get("status","")))}</span></td>'
                     f'<td>{x.get("given","")}</td>'
                     f'<td style="color:var(--muted);font-size:12.5px">{E(str(x.get("advice","")))}</td></tr>')

    prom_rows = ""
    for i, p in enumerate(promises, 1):
        st, tone = promise_state(p, as_of)
        fg, bgc = tone_color(tone)
        style = ("color:#fff;background:var(--obj)" if tone == "risk" else f"color:{fg};background:{bgc}")
        prom_rows += (f'<tr><td class="k">{E(str(p.get("no", i)))}</td>'
                      f'<td>{p.get("content","")}</td>'
                      f'<td class="src-cell">{E(str(p.get("promised_on","")))}</td>'
                      f'<td class="src-cell">{E(str(p.get("due","")))}</td>'
                      f'<td class="src-cell">{E(str(p.get("source","")))}</td>'
                      f'<td><span class="tag" style="{style}">{E(st)}</span></td>'
                      f'<td style="color:var(--muted);font-size:12.5px">{E(str(p.get("detail","")))}</td></tr>')

    pend_rows = ""
    for i, x in enumerate(data.get("pending") or [], 1):
        pend_rows += (f'<tr><td class="k">{E(str(x.get("no", i)))}</td>'
                      f'<td>{x.get("content","")}</td>'
                      f'<td><span class="tag" style="color:var(--pend);background:var(--pend-bg)">{E(str(x.get("type","")))}</span></td>'
                      f'<td>{E(str(x.get("owner","")))}</td>'
                      f'<td style="color:var(--muted);font-size:12.5px">{E(str(x.get("impact","")))}</td>'
                      f'<td class="src-cell">{E(str(x.get("target","")))}</td></tr>')

    def payload(key):
        return data.get("payload") or {}

    facts_html = f"""
    <div class="card" style="padding:16px 20px 20px">
      <div class="tabs" role="tablist">
        <button class="tab" role="tab" aria-selected="true" data-panel="p-req">① 客户明确需求<span class="n">{len(reqs)}</span></button>
        <button class="tab" role="tab" aria-selected="false" data-panel="p-obj">② 客户异议<span class="n">{len(objs)}</span></button>
        <button class="tab" role="tab" aria-selected="false" data-panel="p-prom">③ 我方承诺<span class="n">{len(promises)}</span></button>
        <button class="tab" role="tab" aria-selected="false" data-panel="p-pend">④ 待确认<span class="n">{len(data.get("pending") or [])}</span></button>
      </div>
      <div class="panel on" id="p-req">
        <div class="tbl-wrap"><table>
          <thead><tr><th style="width:120px">维度</th><th>客户原话 / 纪要内容</th><th style="width:130px">出处</th><th style="width:86px">置信度</th><th style="width:180px">备注</th></tr></thead>
          <tbody>{req_rows}</tbody></table></div>
        {f'<div class="callout info"><span class="ic">✓</span><div>{data.get("requirements_note","")}</div></div>' if data.get("requirements_note") else ''}
      </div>
      <div class="panel" id="p-obj">
        <div class="tbl-wrap"><table>
          <thead><tr><th style="width:44px">#</th><th>客户异议（原话要点）</th><th style="width:140px">出处</th><th style="width:130px">状态</th><th style="width:200px">我方已给出</th><th style="width:200px">应对建议</th></tr></thead>
          <tbody>{obj_rows}</tbody></table></div>
      </div>
      <div class="panel" id="p-prom">
        <div class="tbl-wrap"><table>
          <thead><tr><th style="width:44px">#</th><th>我方承诺</th><th style="width:92px">承诺日</th><th style="width:104px">截止</th><th style="width:110px">出处</th><th style="width:150px">状态</th><th style="width:170px">备注</th></tr></thead>
          <tbody>{prom_rows}</tbody></table></div>
        {f'<div class="callout danger"><span class="ic">!</span><div>{data.get("promises_note","")}</div></div>' if overdue and data.get("promises_note") else ''}
      </div>
      <div class="panel" id="p-pend">
        <div class="tbl-wrap"><table>
          <thead><tr><th style="width:44px">#</th><th>待确认 / 未解决事项</th><th style="width:110px">类型</th><th style="width:180px">卡在谁</th><th style="width:230px">影响 / 说明</th><th style="width:140px">建议闭环时间</th></tr></thead>
          <tbody>{pend_rows}</tbody></table></div>
        {f'<div class="callout"><span class="ic">✎</span><div>{data.get("pending_note","")}</div></div>' if data.get("pending_note") else ''}
      </div>
    </div>"""

    # ── AI ──
    ai = data.get("ai_summary") or {}
    ai_paras = "".join(f"<p>{p}</p>" for p in (ai.get("paragraphs") or []))
    ai_pts = "".join(
        f'<div class="ai-pt"><div class="h">{E(str(p.get("h","")))}</div><p>{p.get("p","")}</p></div>'
        for p in (ai.get("points") or []))
    ai_html = f"""
    <div class="ai-card">
      <div class="ai-head">
        <span class="ai-badge">{E(ai.get("badge","AI 推断 · 非客户原话"))}</span>
        <h3>{E(ai.get("title","AI 根据上下文整理的摘要"))}</h3>
        <span class="warn-txt">生成于 {E(meta.get("generated_at",""))} · 基于 {meta.get("source_count","—")} 份素材 {len(timeline)} 条记录</span>
      </div>
      {ai_paras}
      {f'<div class="ai-pts">{ai_pts}</div>' if ai_pts else ''}
    </div>"""

    # ── unknowns ──
    unk_rows = ""
    for i, x in enumerate(data.get("unknowns") or [], 1):
        st = str(x.get("status", "待补"))
        style = "color:#fff;background:var(--obj)" if st == "待补" else "color:var(--ours);background:var(--ours-bg)"
        unk_rows += (f'<tr><td class="k">{E(str(x.get("no", i)))}</td>'
                     f'<td>{E(str(x.get("source","")))}</td>'
                     f'<td>{x.get("issue","")}</td>'
                     f'<td>{E(str(x.get("need","")))}</td>'
                     f'<td><span class="tag" style="{style}">{E(st)}</span></td></tr>')
    unknowns = data.get("unknowns") or []
    unk_html = ""
    if unknowns:
        unk_html = f"""
    <div class="unknown">
      <div class="uh"><h3>⚠ {len(unknowns)} 项待补</h3><span>{E(data.get("unknowns_note","补齐后重新生成即可，无需重做跟进卡"))}</span></div>
      <div class="tbl-wrap"><table>
        <thead><tr><th style="width:44px">#</th><th style="width:170px">素材</th><th>问题</th><th style="width:280px">需要您做什么</th><th style="width:86px">状态</th></tr></thead>
        <tbody>{unk_rows}</tbody></table></div>
    </div>"""

    # ── field confirm ──
    fields = data.get("field_confirm") or []
    c_rows = ""
    for i, f in enumerate(fields, 1):
        conf = str(f.get("confidence", ""))
        t = {"高": ("var(--prom)", "var(--prom-bg)"),
             "中": ("var(--ours)", "var(--ours-bg)")}.get(
            conf, ("#fff", "var(--obj)"))
        flag = str(f.get("flag", "—"))
        flag_html = ("—" if flag in ("—", "", "None") else
                     f'<span class="tag risk" style="font-size:10.5px;padding:2px 6px">{E(flag)}</span>')
        c_rows += (f'<tr><td><div class="cf"><input type="checkbox" id="c{i}"></div></td>'
                   f'<td class="k">{E(str(f.get("field","")))}</td>'
                   f'<td>{E(str(f.get("value","")))}</td>'
                   f'<td class="src-cell">{E(str(f.get("source","")))}</td>'
                   f'<td><span class="conf-tag" style="color:{t[0]};background:{t[1]}">{E(conf or "—")}</span></td>'
                   f'<td>{flag_html}</td></tr>')
    conf_html = ""
    if fields:
        conf_html = f"""
    <div class="card">
      <div class="conf-bar">
        <div class="txt">已确认 <b id="confNum">0</b> / <b id="confTot">{len(fields)}</b></div>
        <div class="prog"><i id="confBar"></i></div>
        <button class="btn sm" id="confReset">重置</button>
      </div>
      <div class="tbl-wrap"><table>
        <thead><tr><th style="width:52px">确认</th><th style="width:120px">字段</th><th>提取值</th><th style="width:150px">出处</th><th style="width:82px">置信度</th><th style="width:110px">标记</th></tr></thead>
        <tbody id="confBody">{c_rows}</tbody></table></div>
    </div>"""

    # ── next actions ──
    payloads = data.get("payload") or {}
    panels_html = ""
    rows_html = ""
    for i, a in enumerate(data.get("next_actions") or [], 1):
        prio = str(a.get("prio", "P1"))
        pcls = "p0" if prio.startswith("P0") else ("p1" if prio.startswith("P1") else "p2")
        link = a.get("link") or ""
        btn = ""
        if link and link in payloads:
            pid = f"l-{link}-{i}"
            btn = f'<button class="btn sm" data-link="{pid}">{E(a.get("link_label") or payloads[link].get("title","联动"))}</button>'
            pl = payloads[link] or {}
            if pl.get("draft"):
                body = (f'<div class="ph"><span>{E(pl.get("title","草稿"))}</span>'
                        f'<button class="btn sm" data-copy="copy-{pid}">复制</button></div>'
                        f'<p style="background:#fff;border:1px solid var(--line);border-radius:9px;padding:13px 15px;line-height:1.85;color:var(--ink)" id="copy-{pid}">{pl["draft"]}</p>')
            else:
                body = f'<div class="ph"><span>{E(pl.get("title","联动产出"))}</span></div><ul>{li(pl.get("items") or [])}</ul>'
            if pl.get("note"):
                body += f'<p style="font-size:12px;color:var(--muted)">{E(pl["note"])}</p>'
            panels_html += f'<div class="linked-panel" id="{pid}">{body}</div>'
        rows_html += f"""
          <tr>
            <td><span class="prio {pcls}">{E(prio)}</span></td>
            <td class="k">{E(str(a.get("when","")))}</td>
            <td>{a.get("action","")}</td>
            <td>{btn}</td>
          </tr>"""
    next_html = f"""
    <div class="card" style="padding:6px 20px 20px">
      <div class="tbl-wrap"><table>
        <thead><tr><th style="width:64px">优先级</th><th style="width:170px">时间</th><th>动作</th><th style="width:190px">联动</th></tr></thead>
        <tbody>{rows_html}</tbody></table></div>
    </div>
    {panels_html}"""

    # ── sources ──
    src_html = ""
    for s in (data.get("sources") or []):
        src_html += (f'<div class="src-c"><div class="n">{E(str(s.get("no","")))}</div>'
                     f'<div class="t">{E(str(s.get("name","")))}</div>'
                     f'<div class="m">{E(str(s.get("detail","")))}</div>'
                     f'<div class="c">{E(str(s.get("count","")))}</div></div>')

    # ── rules ──
    rules = data.get("rules") or []
    rules_txt = "　".join(
        f'{i}. {E(r.get("title","") if isinstance(r, dict) else str(r))}'
        for i, r in enumerate(rules, 1))

    # ── nav ──
    nav = [("overview", "客户速览"), ("stage", "阶段判定"), ("blockers", "卡点"),
           ("timeline", "时间线"), ("facts", "四类清单"), ("ai", "AI 摘要"),
           ("unknown", "待确认"), ("confirm", "字段确认"), ("next", "下一步")]
    nav_html = "".join(f'<a href="#{k}">{v}</a>' for k, v in nav)

    cover_line = meta.get("cover", "")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<style>{CSS}</style>
</head>
<body data-confirm-key="{E(slug)}-confirm-v1">

<nav class="topbar">
  <div class="wrap">
    <div class="tb-brand"><span class="tb-dot"></span>客户跟进卡</div>
    <div class="tb-nav">{nav_html}</div>
    <div class="tb-act"><button class="btn sm" onclick="window.print()">导出 / 打印 PDF</button></div>
  </div>
</nav>

<header class="hero">
  <div class="wrap">
    <span class="eyebrow">{E(meta.get("eyebrow","内贸销售 · 客户跟进记录整理"))}</span>
    <h1>{E(meta.get("customer_name","客户"))}<small>{E(meta.get("customer_suffix",""))}</small></h1>
    <div class="sub">{cover_line}</div>
    <div class="oneliner"><span class="k">一句话结论</span><p>{data.get("headline","")}</p></div>
    <div class="hero-chips">{chips_html}</div>
  </div>
</header>

<div class="wrap">
  <div class="kpis">{kpi_html}</div>

  <section id="overview">
    <div class="sec-head"><h2><span class="ix">01</span>客户速览</h2>
      <div class="desc">{E(data.get("profile_desc","以下字段均出自上传素材；标注为待确认者需您核对。"))}</div></div>
    <div class="card"><dl class="grid-info" style="margin:0">{prof_html}</dl></div>
  </section>

  <section id="stage">
    <div class="sec-head"><h2><span class="ix">02</span>阶段判定与停滞分析</h2>
      <div class="desc">{E(data.get("stage_desc","阶段六段：初次接触 → 需求确认 → 送样 → 报价谈判 → 合同 → 停滞。"))}</div></div>
    {stage_html}
  </section>

  <section id="blockers">
    <div class="sec-head"><h2><span class="ix">03</span>卡点</h2>
      <div class="desc">{E(data.get("blockers_desc","按「能否我方单方面推进」排序。"))}</div></div>
    <div class="blockers">{blk_html}</div>
  </section>

  <section id="timeline">
    <div class="sec-head"><h2><span class="ix">04</span>跟进时间线</h2>
      <div class="desc">按时间正序，共 {len(timeline)} 条；每条标注分类与出处。点击标签可筛选。</div></div>
    <div class="filters" id="filters">{filt}</div>
    <div class="tl" id="tl">{tl_html}</div>
  </section>

  <section id="facts">
    <div class="sec-head"><h2><span class="ix">05</span>四类清单</h2>
      <div class="desc">严格区分：客户说过的 / 客户反对的 / 我方承诺的 / 尚未确认的。每条带出处。</div></div>
    {facts_html}
  </section>

  <section id="ai">
    <div class="sec-head"><h2><span class="ix">06</span>AI 根据上下文整理的摘要</h2>
      <div class="desc">此节为模型推断，<b>不是客户原话</b>，仅供决策参考，不得直接引用给客户。</div></div>
    {ai_html}
  </section>

  <section id="unknown">
    <div class="sec-head"><h2><span class="ix">07</span>无法辨认 / 缺失内容</h2>
      <div class="desc">以下内容<b>未计入</b>四类清单，避免猜测混入事实。</div></div>
    {unk_html or '<div class="callout"><span class="ic">✓</span><div>本次素材未发现无法辨认内容。</div></div>'}
  </section>

  <section id="confirm">
    <div class="sec-head"><h2><span class="ix">08</span>关键字段确认</h2>
      <div class="desc">生成跟进卡前的最后一步：逐条核对，勾选即视为确认，进度保存在本机。</div></div>
    {conf_html}
  </section>

  <section id="next">
    <div class="sec-head"><h2><span class="ix">09</span>下一步动作 · 联动入口</h2>
      <div class="desc">点击按钮展开对应联动产出。</div></div>
    {next_html}
    {data.get("footer_action_note","")}
  </section>

  <section id="source">
    <div class="sec-head"><h2><span class="ix">10</span>数据来源与整理口径</h2></div>
    <div class="card">
      <div class="src-grid">{src_html}</div>
      <div style="padding:0 20px 20px">
        <div class="callout info" style="margin-top:2px"><span class="ic">§</span>
          <div><b>整理口径：</b>{rules_txt}</div></div>
      </div>
    </div>
  </section>

  <footer>
    <b>{E(title)}</b> ｜ 生成时间 {E(meta.get("generated_at",""))} ｜ 共 {len(timeline)} 条记录 / {E(str(meta.get("source_count","—")))} 份素材
      ｜ 阶段：{E(stage.get("current","—"))}{f" · 停滞 {stall_days} 天" if stall_days is not None else ""}<br>
    {E(meta.get("disclaimer",""))}<br>
    关键字段确认后归档；待办完成后请回填结果，重新生成即可重算阶段与停滞天数。
  </footer>
</div>

<div class="toast" id="toast">已复制</div>
<script>{JS}</script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser(description="由 followup.json 生成自包含 HTML 跟进卡")
    ap.add_argument("input", help="followup.json 路径")
    ap.add_argument("-o", "--out", required=True, help="输出 .html 路径")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8-sig") as f:
        data = json.load(f)

    errors, warnings = validate(data)
    for w in warnings:
        print(f"[warn] {w}")
    if errors:
        for e in errors:
            print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    html_text = build(data)
    with open(args.out, "w", encoding="utf-8-sig") as f:
        f.write(html_text)
    print(f"[ok] html -> {args.out}  ({len(html_text.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
