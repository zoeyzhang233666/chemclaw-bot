#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""case.json → 单文件自包含 HTML（可离线、可发微信、可打印）。

用法:
  python build_html.py --case case.json [--out out/]
纯标准库，不依赖任何第三方包。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caselib as C  # noqa: E402

CSS = """
:root{
  --ink:#0f172a;--ink2:#334155;--muted:#64748b;--line:#e2e8f0;--line2:#eef2f6;
  --bg:#f6f7f9;--card:#fff;
  --accent:#0f766e;--accent-d:#134e4a;--accent-s:#ccfbf1;--accent-l:#f0fdfa;
  --amber:#b45309;--amber-s:#fef3c7;--red:#b91c1c;--red-s:#fee2e2;
  --green:#15803d;--green-s:#dcfce7;
  --mono:"SFMono-Regular",ui-monospace,"JetBrains Mono",Consolas,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:15px;line-height:1.75;-webkit-font-smoothing:antialiased}
.wrap{max-width:1140px;margin:0 auto;padding:0 26px}
a{color:inherit;text-decoration:none}
code{font-family:var(--mono);font-size:.9em;background:#f1f5f9;padding:1px 5px;border-radius:5px;color:var(--accent-d)}
.topbar{position:sticky;top:0;z-index:60;background:rgba(255,255,255,.84);
  backdrop-filter:blur(14px) saturate(1.4);border-bottom:1px solid var(--line)}
.topbar .in{display:flex;align-items:center;gap:18px;height:58px;max-width:1140px;margin:0 auto;padding:0 26px}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;font-size:14px;white-space:nowrap;letter-spacing:-.01em}
.brand i{width:22px;height:22px;border-radius:7px;background:linear-gradient(140deg,var(--accent),#0b5f59);
  display:inline-block;position:relative;box-shadow:0 2px 6px rgba(15,118,110,.32)}
.brand i::after{content:"";position:absolute;inset:6px;border:1.5px solid #fff;border-radius:3px;opacity:.85}
.nav{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;margin-left:auto}
.nav::-webkit-scrollbar{display:none}
.nav a{font-size:12.5px;color:var(--muted);padding:6px 10px;border-radius:8px;white-space:nowrap;transition:.16s}
.nav a:hover{background:var(--accent-l);color:var(--accent-d)}
.hero{position:relative;overflow:hidden;padding:62px 0 46px;border-bottom:1px solid var(--line);
  background:linear-gradient(180deg,#fff 0%,#fbfdfd 55%,var(--bg) 100%)}
.hero::before{content:"";position:absolute;inset:0;
  background-image:linear-gradient(var(--line2) 1px,transparent 1px),linear-gradient(90deg,var(--line2) 1px,transparent 1px);
  background-size:34px 34px;mask-image:radial-gradient(ellipse 70% 60% at 78% 8%,#000 0%,transparent 72%);opacity:.9}
.hero::after{content:"";position:absolute;width:520px;height:520px;right:-140px;top:-260px;border-radius:50%;
  background:radial-gradient(circle,rgba(15,118,110,.13),transparent 66%)}
.hero .wrap{position:relative}
.eyebrow{font-family:var(--mono);font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);
  display:flex;align-items:center;gap:10px;margin-bottom:18px}
.eyebrow::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--accent-s),transparent);max-width:180px}
h1{font-size:clamp(27px,3.6vw,41px);line-height:1.28;letter-spacing:-.025em;margin:0 0 18px;font-weight:750;max-width:26ch}
h1 em{font-style:normal;color:var(--accent);border-bottom:2px solid var(--accent-s)}
.lead{font-size:16px;color:var(--ink2);max-width:66ch;margin:0 0 26px}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px;margin-top:6px}
.meta div{background:#fff;border:1px solid var(--line);border-radius:12px;padding:11px 14px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.meta span{display:block;font-size:11px;color:var(--muted);letter-spacing:.06em;margin-bottom:3px}
.meta b{font-size:13.5px;font-weight:600;letter-spacing:-.01em}
.hero-note{margin-top:16px;font-size:12.5px;color:var(--muted)}
.hero-note em{font-style:normal;color:var(--amber);font-weight:600}
.block{padding:54px 0;border-top:1px solid var(--line);scroll-margin-top:72px}
.block:first-of-type{border-top:0}
.sh{display:flex;align-items:baseline;gap:13px;margin-bottom:8px;flex-wrap:wrap}
.sh .idx{font-family:var(--mono);font-size:12px;color:var(--accent);background:var(--accent-s);
  padding:3px 8px;border-radius:6px;font-weight:600;letter-spacing:.04em}
.sh h2{font-size:21px;margin:0;letter-spacing:-.02em;font-weight:700}
.sh .tag{font-size:11.5px;color:var(--muted);border:1px solid var(--line);background:#fff;
  padding:2px 8px;border-radius:999px;margin-left:auto}
.sub{color:var(--muted);font-size:13.5px;margin:0 0 24px;max-width:76ch}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;
  box-shadow:0 1px 2px rgba(15,23,42,.04),0 8px 24px -18px rgba(15,23,42,.18)}
.card h3{margin:0 0 12px;font-size:13px;font-weight:700;letter-spacing:.02em;color:var(--accent-d);
  display:flex;align-items:center;gap:8px}
.card h3::before{content:"";width:3px;height:13px;background:var(--accent);border-radius:2px}
.grid4{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.kv{display:grid;grid-template-columns:84px 1fr;gap:6px 10px;font-size:13px;margin:0}
.kv dt{color:var(--muted);font-size:12.5px}
.kv dd{margin:0;color:var(--ink2)}
.tl{list-style:none;margin:0;padding:0 0 0 4px}
.tl li{position:relative;padding:0 0 15px 20px;font-size:13.5px;color:var(--ink2);line-height:1.7}
.tl li:last-child{padding-bottom:0}
.tl li::before{content:"";position:absolute;left:0;top:8px;width:8px;height:8px;border-radius:50%;background:#fff;border:2px solid var(--accent)}
.tl li::after{content:"";position:absolute;left:3.5px;top:18px;bottom:0;width:1px;background:var(--line)}
.tl li:last-child::after{display:none}
.tl b{display:block;font-size:12px;color:var(--muted);font-weight:600;letter-spacing:.02em;margin-bottom:2px}
.tl li.now::before{background:var(--amber);border-color:var(--amber)}
.tl li.now{color:var(--amber);font-weight:600}
.draft{font-size:14px;line-height:2;color:var(--ink2);background:#fffdf8;border:1px solid #f3e9d6;border-radius:12px;padding:16px 18px}
.draft mark{background:transparent;padding:0 1px}
.draft mark.q{color:var(--muted);text-decoration:underline dotted var(--muted);text-underline-offset:4px}
.draft mark.w{background:var(--amber-s);color:#7c4a03;border-radius:3px}
.draft mark.b{background:var(--red-s);color:#8f1414;border-radius:3px}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px;font-size:11.5px;color:var(--muted)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.facts{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:10px}
.fact{background:#fff;border:1px solid var(--line);border-radius:11px;padding:12px 14px;transition:.16s}
.fact:hover{border-color:#cbd5e1;box-shadow:0 6px 18px -12px rgba(15,23,42,.35)}
.fact .hd{display:flex;align-items:center;gap:8px;margin-bottom:5px;flex-wrap:wrap}
.fact .id{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--accent);background:var(--accent-l);
  border:1px solid var(--accent-s);padding:1px 6px;border-radius:5px}
.fact .tp{font-size:10.5px;padding:1px 6px;border-radius:5px}
.tp.t1{background:var(--green-s);color:var(--green)}
.tp.t2{background:var(--accent-s);color:var(--accent-d)}
.tp.t3{background:var(--amber-s);color:var(--amber)}
.tp.t4{background:var(--red-s);color:var(--red)}
.fact p{margin:0;font-size:12.8px;line-height:1.65;color:var(--ink2)}
.fact .hint{margin-top:6px;font-size:11.5px;color:var(--muted);line-height:1.55}
.main-grid{display:grid;grid-template-columns:minmax(0,360px) minmax(0,1fr);gap:26px;align-items:start}
.phone{width:100%;max-width:360px;border-radius:32px;padding:10px;background:linear-gradient(160deg,#1e293b,#0b1220);
  box-shadow:0 26px 60px -30px rgba(15,23,42,.7),0 2px 0 #fff inset}
.phone .scr{border-radius:24px;overflow:hidden;background:#ededed}
.ph-hd{background:#f7f7f7;border-bottom:1px solid #e3e3e3;padding:11px 14px;text-align:center}
.ph-hd b{display:block;font-size:13.5px;color:#111;font-weight:600}
.ph-hd span{font-size:10.5px;color:#94a3b8}
.phone-body{padding:14px 12px 18px;display:flex;flex-direction:column;gap:8px;min-height:200px}
.stamp{text-align:center;font-size:10px;color:#a1a1a1;margin:2px 0 4px}
.bubble{max-width:88%;align-self:flex-end;background:#95ec69;color:#0d1b0d;padding:9px 11px;border-radius:8px;
  font-size:13.2px;line-height:1.68;position:relative;box-shadow:0 1px 1px rgba(0,0,0,.05)}
.bubble::after{content:"";position:absolute;right:-4px;top:11px;width:8px;height:8px;background:#95ec69;transform:rotate(45deg)}
.ph-ft{display:flex;gap:7px;padding:8px 10px;background:#f7f7f7;border-top:1px solid #e3e3e3}
.ph-ft .f{flex:1;background:#fff;border-radius:14px;height:26px;border:1px solid #e3e3e3}
.ph-ft .s{width:26px;height:26px;border-radius:50%;background:#07c160}
.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.btn{font:inherit;font-size:12.5px;font-weight:600;border:1px solid transparent;border-radius:9px;padding:8px 14px;
  background:var(--ink);color:#fff;cursor:pointer;transition:.16s;display:inline-flex;align-items:center;gap:6px}
.btn:hover{background:#1e293b;transform:translateY(-1px)}
.btn.ghost{background:#fff;color:var(--ink2);border-color:var(--line)}
.btn.ghost:hover{background:var(--accent-l);border-color:var(--accent-s);color:var(--accent-d)}
.spec{list-style:none;margin:0;padding:0;font-size:13px}
.spec li{display:flex;gap:10px;padding:9px 0;border-bottom:1px dashed var(--line2)}
.spec li:last-child{border-bottom:0}
.spec .k{color:var(--muted);flex:0 0 74px;font-size:12.5px}
.spec.wide .k{flex:0 0 94px}
.spec .v{color:var(--ink2);flex:1}
.tabs{display:inline-flex;gap:3px;background:#eef2f4;border:1px solid var(--line);padding:4px;border-radius:12px;flex-wrap:wrap}
.tab{font:inherit;font-size:12.5px;font-weight:600;color:var(--muted);background:transparent;border:0;padding:8px 14px;
  border-radius:9px;cursor:pointer;transition:.16s;white-space:nowrap}
.tab:hover{color:var(--ink2)}
.tab[aria-selected="true"]{background:#fff;color:var(--accent-d);box-shadow:0 1px 3px rgba(15,23,42,.12)}
.panel{display:none}
.panel.on{display:block;animation:fade .26s ease}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.msg{font-size:14px;line-height:1.95;color:var(--ink2);word-break:break-word}
.msg p{margin:0 0 10px}
.msg p:last-child{margin-bottom:0}
.subject{display:flex;gap:10px;align-items:baseline;background:var(--accent-l);border:1px solid var(--accent-s);
  border-radius:10px;padding:10px 13px;margin-bottom:14px;font-size:13px}
.subject b{font-size:11px;color:var(--accent-d);letter-spacing:.06em;flex:0 0 auto}
.bars{display:flex;gap:18px;flex-wrap:wrap;margin-top:16px;padding-top:14px;border-top:1px dashed var(--line2);font-size:12px;color:var(--muted)}
.bars b{color:var(--ink2);font-weight:600}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.chip{font:inherit;font-size:12.5px;font-weight:600;color:var(--ink2);background:#fff;border:1px solid var(--line);
  border-radius:999px;padding:7px 14px;cursor:pointer;transition:.16s}
.chip:hover{border-color:var(--accent-s);background:var(--accent-l);color:var(--accent-d)}
.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.adj-out{background:#fffdf8;border:1px solid #f3e9d6;border-radius:12px;padding:16px 18px;min-height:120px;
  font-size:13.8px;line-height:1.9;color:var(--ink2);white-space:pre-wrap;word-break:break-word}
.adj-note{font-size:12.3px;color:var(--muted);margin-top:12px;line-height:1.7}
.adj-note b{color:var(--accent-d)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:20px}
.stat{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.stat b{display:block;font-size:26px;line-height:1.1;font-weight:750;letter-spacing:-.03em}
.stat span{font-size:11.5px;color:var(--muted)}
.stat.zero b{color:var(--green)}
.stat.wait b{color:var(--amber)}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:12.8px;background:#fff;
  border:1px solid var(--line);border-radius:12px;overflow:hidden}
th{background:#f8fafc;text-align:left;padding:10px 11px;font-size:11px;letter-spacing:.06em;color:var(--muted);
  text-transform:uppercase;border-bottom:1px solid var(--line);font-weight:700;white-space:nowrap}
td{padding:10px 11px;border-bottom:1px solid var(--line2);vertical-align:top;color:var(--ink2);line-height:1.6}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:#fcfdfd}
td.c{text-align:center}
.pill{display:inline-block;min-width:22px;padding:1px 6px;border-radius:6px;font-size:11.5px;font-weight:700;text-align:center}
.p-ok{background:var(--green-s);color:var(--green)}
.p-mid{background:var(--amber-s);color:var(--amber)}
.p-del{background:var(--red-s);color:var(--red)}
.p-none{background:#f1f5f9;color:#94a3b8}
.mono{font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.ph-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}
.ph{background:#fff;border:1px solid var(--line);border-left:3px solid var(--amber);border-radius:10px;padding:12px 14px}
.ph .hd{display:flex;gap:8px;align-items:baseline;margin-bottom:4px}
.ph .id{font-family:var(--mono);font-size:10.5px;color:var(--amber);font-weight:700}
.ph .nm{font-size:12.8px;font-weight:600;color:var(--ink)}
.ph .mt{font-size:11.5px;color:var(--muted);line-height:1.6}
.ph .mt b{color:var(--ink2);font-weight:600}
.scn{background:#fff;border:1px solid var(--line);border-radius:14px;margin-bottom:12px;overflow:hidden;
  box-shadow:0 1px 2px rgba(15,23,42,.04)}
.scn-hd{display:flex;align-items:center;gap:10px;padding:13px 18px;background:linear-gradient(90deg,var(--accent-l),#fff);
  border-bottom:1px solid var(--line)}
.scn-hd b{font-size:14px}
.scn-hd .n{font-family:var(--mono);font-size:10.5px;color:var(--accent);background:#fff;border:1px solid var(--accent-s);
  padding:1px 7px;border-radius:5px}
.scn-hd .btn{margin-left:auto;padding:5px 11px;font-size:11.5px}
.scn-bd{padding:16px 18px}
.q{font-size:12.8px;color:var(--muted);background:#fafafa;border-radius:9px;padding:10px 13px;margin:0 0 12px;
  border:1px dashed var(--line)}
.q b{display:block;font-size:10.5px;letter-spacing:.08em;color:#94a3b8;margin-bottom:3px;font-weight:700}
.rec{font-size:13.5px;line-height:1.9;color:var(--ink2);margin:0}
.short{margin-top:12px;padding-top:11px;border-top:1px dashed var(--line2);font-size:12.5px;color:var(--muted)}
.short b{color:var(--ink2);font-size:11px;letter-spacing:.05em;margin-right:6px}
.red{margin-top:10px;font-size:12.3px;color:var(--amber);background:#fffbf2;border:1px solid #f6e6c9;
  border-radius:9px;padding:9px 12px;line-height:1.65}
.red b{color:#8a4b06}
details{background:#fff;border:1px solid var(--line);border-radius:12px;margin-bottom:9px;overflow:hidden}
details[open]{box-shadow:0 8px 24px -20px rgba(15,23,42,.5)}
summary{cursor:pointer;padding:13px 18px;font-size:13.5px;font-weight:600;color:var(--ink);display:flex;
  align-items:center;gap:10px;list-style:none;transition:.15s}
summary::-webkit-details-marker{display:none}
summary:hover{background:var(--accent-l)}
summary::before{content:"+";font-family:var(--mono);font-size:14px;color:var(--accent);width:14px;text-align:center}
details[open] summary::before{content:"−"}
details[open] summary{background:#fcfdfd;border-bottom:1px solid var(--line2)}
.d-bd{padding:15px 18px 17px}
.d-bd .say{font-size:13.3px;line-height:1.9;color:var(--ink2);margin:0 0 12px}
.ban{font-size:12.3px;color:var(--red);background:var(--red-s);border-radius:8px;padding:8px 12px;margin-bottom:10px}
.ban b{font-size:10.5px;letter-spacing:.08em;display:block;margin-bottom:2px;opacity:.85}
.why{font-size:12.3px;color:var(--muted);line-height:1.7}
.why b{color:var(--accent-d);font-size:10.5px;letter-spacing:.08em;display:block;margin-bottom:2px}
.prog{display:flex;align-items:center;gap:14px;margin-bottom:18px}
.bar{flex:1;height:7px;background:#e6ebef;border-radius:99px;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),#22b3a5);border-radius:99px;
  transition:width .35s cubic-bezier(.3,.8,.4,1)}
.prog span{font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap}
.checks{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.ck{display:flex;gap:10px;align-items:flex-start;background:#fff;border:1px solid var(--line);border-radius:10px;
  padding:11px 13px;cursor:pointer;transition:.15s;font-size:12.8px;line-height:1.6;color:var(--ink2)}
.ck:hover{border-color:#cbd5e1}
.ck input{appearance:none;width:16px;height:16px;border:1.5px solid #cbd5e1;border-radius:5px;flex:0 0 auto;
  margin-top:2px;cursor:pointer;transition:.15s;position:relative;background:#fff}
.ck input:checked{background:var(--accent);border-color:var(--accent)}
.ck input:checked::after{content:"";position:absolute;left:4.5px;top:1.5px;width:4px;height:8px;
  border:solid #fff;border-width:0 2px 2px 0;transform:rotate(43deg)}
.ck input:checked ~ .t{color:var(--muted);text-decoration:line-through}
.ck .t b{display:block;font-size:11px;color:var(--accent);letter-spacing:.05em;font-weight:700;margin-bottom:1px}
footer{border-top:1px solid var(--line);background:#fff;padding:44px 0 54px;margin-top:10px}
.rules{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin-bottom:26px}
.rule{border:1px solid var(--line);border-radius:12px;padding:15px 17px;background:linear-gradient(180deg,#fff,#fcfdfd)}
.rule b{display:block;font-size:12.5px;color:var(--accent-d);margin-bottom:5px}
.rule p{margin:0;font-size:12.3px;color:var(--muted);line-height:1.7}
.rule .n{font-family:var(--mono);font-size:10.5px;color:var(--accent);letter-spacing:.1em;display:block;margin-bottom:6px}
.disclaim{font-size:11.8px;color:#94a3b8;line-height:1.8;max-width:90ch}
#toast{position:fixed;left:50%;bottom:34px;transform:translate(-50%,18px);background:var(--ink);color:#fff;
  font-size:12.8px;font-weight:600;padding:10px 20px;border-radius:99px;opacity:0;pointer-events:none;
  transition:.28s;z-index:99;box-shadow:0 10px 30px -10px rgba(15,23,42,.6)}
#toast.on{opacity:1;transform:translate(-50%,0)}
@media (max-width:900px){
  .grid4,.main-grid,.checks{grid-template-columns:1fr}
  .nav{display:none}
  .phone{margin:0 auto}
  .block{padding:40px 0}
}
@media print{
  .topbar,.nav,#toast,.btn{display:none!important}
  body{background:#fff}
  .block{padding:22px 0;break-inside:avoid}
  .card,.scn,table,.phone{box-shadow:none}
  .panel{display:block!important}
}
"""

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<div class="topbar"><div class="in">
  <div class="brand"><i></i><span id="brand">客户沟通润色</span></div>
  <nav class="nav">
    <a href="#material">原始材料</a><a href="#facts">事实台账</a><a href="#main">主版本</a>
    <a href="#versions">四个开关</a><a href="#adjust">快速调整</a><a href="#audit">边界审计</a>
    <a href="#ph">待填清单</a><a href="#scn">场景</a><a href="#reply">追问应对</a><a href="#check">发送清单</a>
  </nav>
</div></div>

<header class="hero"><div class="wrap">
  <div class="eyebrow" id="eyebrow"></div>
  <h1 id="heroTitle"></h1>
  <p class="lead" id="heroLead"></p>
  <div class="meta" id="heroMeta"></div>
  <p class="hero-note" id="heroNote"></p>
</div></header>

<main>
<section class="block" id="material"><div class="wrap">
  <div class="sh"><span class="idx">01</span><h2>先看清楚原材料</h2><span class="tag">收料 · 不美化</span></div>
  <p class="sub">润色的信息量全部来自这几块。原话越口语越好——粗糙的地方，往往就是问题的位置。</p>
  <div class="grid4">
    <div class="card"><h3>产品档案</h3><dl class="kv" id="prof"></dl></div>
    <div class="card"><h3>客户背景</h3><dl class="kv" id="cust"></dl></div>
    <div class="card"><h3>上一轮沟通</h3><ul class="tl" id="timeline"></ul></div>
    <div class="card"><h3>我的原话（草稿）</h3>
      <div class="draft" id="draft"></div>
      <div class="legend" id="legend"></div>
    </div>
  </div>
</div></section>

<section class="block" id="facts"><div class="wrap">
  <div class="sh"><span class="idx">02</span><h2 id="factsTitle">把原话拆成事实</h2><span class="tag">可核验 · 可审计</span></div>
  <p class="sub">先给每条信息定性。没有这一步，“润色”就变成了凭感觉改写；有了这一步，每个版本都能被逐格核对。</p>
  <div class="facts" id="factsList"></div>
</div></section>

<section class="block" id="main"><div class="wrap">
  <div class="sh"><span class="idx">03</span><h2 id="mainTitle">主版本</h2><span class="tag">默认推荐 · 可直接发</span></div>
  <p class="sub" id="mainSub"></p>
  <div class="main-grid">
    <div id="mainLeft"></div>
    <div id="mainRight"></div>
  </div>
</div></section>

<section class="block" id="versions"><div class="wrap">
  <div class="sh"><span class="idx">04</span><h2>四个开关：短 / 正式 / 缓和</h2><span class="tag">同一件事的四种说法</span></div>
  <p class="sub">不是四套话术，是同一份事实的四种排布。切换下面标签，文案与复制按钮会同步。</p>
  <div class="tabs" role="tablist" id="tabs" style="margin-bottom:16px"></div>
  <div id="panels"></div>
</div></section>

<section class="block" id="adjust"><div class="wrap">
  <div class="sh"><span class="idx">05</span><h2>“再短一点”“更正式”——点一下看结果</h2><span class="tag">指令 → 确定的改法</span></div>
  <p class="sub">每条指令背后是一套固定的删改规则，不是随机发挥。任选一条，右侧立刻给出结果，可直接复制。</p>
  <div class="chips" id="chips"></div>
  <div class="grid4" style="grid-template-columns:1.35fr .9fr;align-items:start">
    <div>
      <div class="toolbar"><button class="btn" data-copy="#adjOut">复制这个版本</button><span class="mono" id="adjTag"></span></div>
      <div class="adj-out copyable" id="adjOut"></div>
      <div class="adj-note" id="adjNote"></div>
    </div>
    <div class="card"><h3>四条规则，永远不变</h3><ul class="spec wide" id="ruleSpec"></ul></div>
  </div>
</div></section>

<section class="block" id="audit"><div class="wrap">
  <div class="sh"><span class="idx">06</span><h2 id="auditTitle">边界审计</h2><span class="tag">逐格可核</span></div>
  <p class="sub">✔ 保留　◐ 弱化或改写　— 刻意未提　▲ 已删除。任何一格判定，都必须能在文本里找到依据。</p>
  <div class="stats" id="stats"></div>
  <div style="overflow-x:auto"><table>
    <thead><tr><th style="width:52px">编号</th><th style="min-width:190px">事项</th>
    <th style="width:60px">A</th><th style="width:60px">B</th><th style="width:60px">C</th><th style="width:60px">D</th>
    <th style="min-width:260px">审计说明</th></tr></thead>
    <tbody id="auditBody"></tbody>
  </table></div>
</div></section>

<section class="block" id="ph"><div class="wrap">
  <div class="sh"><span class="idx">07</span><h2 id="phTitle">待填的归属</h2><span class="tag">发出前必须清零</span></div>
  <p class="sub">留一个没填，客户看到的就是“这个人不专业”。占位符不是省略号，是责任人。</p>
  <div class="ph-list" id="phList"></div>
</div></section>

<section class="block" id="scn"><div class="wrap">
  <div class="sh"><span class="idx">08</span><h2>同一套边界规则，各个高频场景</h2><span class="tag">可直接发</span></div>
  <p class="sub">左边是业务真正会打出来的原话，中间是可直接发出去、右边是对方已读不回时的极简版。最后一行是红线。</p>
  <div id="scnList"></div>
</div></section>

<section class="block" id="reply"><div class="wrap">
  <div class="sh"><span class="idx">09</span><h2>发出去之后，客户会怎么接</h2><span class="tag">不越界的接法</span></div>
  <p class="sub">润色的另一半在收到回复之后——对方每一句回话，都可能把你逼回“新增承诺”。</p>
  <div id="replyList"></div>
</div></section>

<section class="block" id="check"><div class="wrap">
  <div class="sh"><span class="idx">10</span><h2>发送前检查清单</h2><span class="tag">勾满再发</span></div>
  <p class="sub">只要有一项过不去，就先别发。发错一条越界承诺的成本，远高于晚半小时发出去。</p>
  <div class="prog"><div class="bar"><i id="barFill"></i></div><span id="progTxt"></span></div>
  <div class="checks" id="checks"></div>
</div></section>
</main>

<footer><div class="wrap">
  <div class="rules" id="footerRules"></div>
  <p class="disclaim" id="disclaim"></p>
</div></footer>
<div id="toast">已复制</div>
<noscript><div style="padding:20px;background:#fee2e2;color:#b91c1c">本页需要启用 JavaScript 才能渲染内容。</div></noscript>

<script id="case-data" type="application/json">__CASE__</script>
<script>
(function(){
"use strict";
var CASE = JSON.parse(document.getElementById('case-data').textContent);
var VK = ["A","B","C","D"];

function esc(s){return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
  .replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
function $(id){return document.getElementById(id);}
function h(tag,cls,html){var e=document.createElement(tag);if(cls)e.className=cls;
  if(html!=null)e.innerHTML=html;return e;}
function setText(id,v){var e=$(id);if(e)e.textContent=v||"";}
function setHTML(id,v){var e=$(id);if(e)e.innerHTML=v||"";}

/* ---------- hero ---------- */
(function(){
  var m = CASE.meta||{}, hero = m.hero||{};
  setText("brand", (m.product||"") + " · 沟通润色");
  setText("eyebrow",(m.product||"化工品")+" · 内贸销售 · "+(m.scenario||"客户沟通"));
  var t = hero.title || ((m.product||"")+" · "+(m.scenario||"客户沟通")+" 润色样板");
  $("heroTitle").innerHTML = esc(t).replace(/“([^”]+)”/g,'“<em>$1</em>”');
  setText("heroLead", hero.lead || "");
  var cust=(m.customer||{}), sel=(m.seller||{});
  var cells=[["客户 / 角色",(cust.name||"")+" · "+(cust.role||"")],
             ["渠道",m.channel||""],["本次目标",m.goal||""],["关系阶段",m.stage||""],
             ["我方",[sel.company,sel.region,sel.name].filter(Boolean).join(" ")]];
  var box=$("heroMeta"); box.innerHTML="";
  cells.forEach(function(c){ if(!c[1])return;
    var d=document.createElement("div");
    d.innerHTML='<span>'+esc(c[0])+'</span><b>'+esc(c[1])+'</b>'; box.appendChild(d);});
  $("heroNote").innerHTML='本页可直接操作：<em>一键复制</em>任意版本 · 点开“四个开关”切换语气 · 清单可勾选计数。'
    + (m.fictional? '示例客户为虚构，仅用于演示流程。':'');
})();

/* ---------- 01 原始材料 ---------- */
(function(){
  var pp = CASE.product_profile||{};
  var rows=[["品名",pp.name],["别名",(pp.alias||[]).join("、")],["CAS",pp.cas],
            ["标准",pp.standard],["形态",pp.form],["危险性",pp.hazard],
            ["包装",(pp.packaging||[]).join("、")],["运输",pp.transport],
            ["验收指标",(pp.key_specs||[]).join("、")],["价格口径",pp.price_basis],
            ["结算惯例",pp.payment_norm],["下游",(pp.downstream||[]).join("、")],
            ["本品类禁语",(pp.ban_phrases||[]).join("；")]];
  setHTML("prof", rows.filter(function(r){return r[1];})
    .map(function(r){return '<dt>'+esc(r[0])+'</dt><dd>'+esc(r[1])+'</dd>';}).join(""));
  setHTML("cust", (CASE.customer_profile||[]).map(function(r){
    return '<dt>'+esc(r[0])+'</dt><dd>'+esc(r[1])+'</dd>';}).join(""));

  var tl=$("timeline");
  (CASE.timeline||[]).forEach(function(t,i){
    var li=document.createElement("li");
    if(i===(CASE.timeline||[]).length-1) li.className="now";
    li.innerHTML='<b>'+esc(t.when||"")+'</b>'+esc(t.what||"")+(t.detail?'（'+esc(t.detail)+'）':'');
    tl.appendChild(li);});

  var d=CASE.draft||{};
  setHTML("draft", (d.segments||[{t:d.raw||"",m:""}]).map(function(s){
    return s.m? '<mark class="'+s.m+'">'+esc(s.t)+'</mark>' : esc(s.t);}).join(""));
  var cols={q:"#94a3b8",w:"#fde68a",b:"#fecaca"};
  setHTML("legend",(d.legend||[]).map(function(l){
    return '<span><i style="background:'+(cols[l.m]||"#e2e8f0")+'"></i>'+esc(l.label)+'</span>';}).join(""));
})();

/* ---------- 02 事实台账 ---------- */
(function(){
  var list=$("factsList"), n=(CASE.facts||[]).length;
  setText("factsTitle","把原话拆成 "+n+" 条事实");
  (CASE.facts||[]).forEach(function(f){
    var t=f.type||"", cls="t1";
    if(/无据|越权|施压/.test(t)) cls="t4"; else if(/承诺/.test(t)) cls="t3";
    else if(/意图|敏感/.test(t)) cls="t2";
    var d=document.createElement("div"); d.className="fact";
    d.innerHTML='<div class="hd"><span class="id">'+esc(f.id)+'</span>'+
      '<span class="tp '+cls+'">'+esc(t)+'</span></div>'+
      '<p>'+esc(f.text)+'</p>'+(f.note?'<div class="hint">'+esc(f.note)+'</div>':'');
    list.appendChild(d);});
})();

/* ---------- 03 主版本 ---------- */
(function(){
  var v=(CASE.versions||{}).A||{}, m=CASE.meta||{}, isMail=/邮件/.test(v.media||"");
  setText("mainTitle","主版本："+(v.label||"A 自然版"));
  setText("mainSub", isMail ? "邮件体：分条、留痕、可转发。" :
    "把请求放到最后，只提一件事——给对方一个低成本的回复理由。");

  var left=$("mainLeft"), right=$("mainRight");
  var targetId = isMail ? "verMail" : "verPhone";
  if(isMail){
    var sub=(CASE.email||{}).subject||"";
    left.innerHTML='<div class="card"><div class="copyable" id="verMail">'+
      (sub?'<div class="subject"><b class="no-copy">主题</b><span>'+esc(sub)+'</span></div>':'')+
      '<div class="msg">'+(v.para||[]).map(function(p){return '<p>'+esc(p).replace(/\\n/g,"<br>")+'</p>';}).join("")+
      '</div></div></div>';
  }else{
    left.innerHTML='<div class="phone"><div class="scr">'+
      '<div class="ph-hd"><b>'+esc(((m.customer||{}).role||(m.customer||{}).name||"客户").replace(/（.*$/,""))+'</b><span>微信</span></div>'+
      '<div class="phone-body copyable" id="verPhone"><div class="stamp no-copy">今天</div>'+
      (v.para||[]).map(function(p){return '<div class="bubble">'+esc(p)+'</div>';}).join("")+
      '</div><div class="ph-ft"><div class="f"></div><div class="s"></div></div></div></div>';
  }

  var why=(v.why||[]).map(function(w){
    return '<li><span class="k">'+esc(w[0])+'</span><span class="v">'+esc(w[1])+'</span></li>';}).join("");
  right.innerHTML=
    '<div class="toolbar"><button class="btn" data-copy="#'+targetId+'">复制这一版</button>'+
    '<button class="btn ghost" data-jump="#versions">看另外三版</button></div>'+
    (why?'<div class="card" style="margin-bottom:14px"><h3>为什么这么改</h3><ul class="spec">'+why+'</ul></div>':'')+
    '<div class="card" style="background:var(--accent-l);border-color:var(--accent-s)">'+
    '<h3>这一版没有任何新增</h3><p style="margin:0;font-size:13px;color:var(--ink2);line-height:1.8">'+
    '没有报新价格、没有让价、没有交期、没有库存、没有替客户编需求。'+
    '所有拿不准的地方都留成【待填】，并在第 07 节列了确认人。</p></div>';
})();

/* ---------- 04 版本切换 ---------- */
(function(){
  var tabs=$("tabs"), panels=$("panels"), vers=CASE.versions||{};
  var keys=VK.filter(function(k){return vers[k];});
  keys.forEach(function(k,i){
    var v=vers[k];
    var b=document.createElement("button");
    b.className="tab"; b.type="button"; b.setAttribute("role","tab");
    b.setAttribute("aria-selected", i===0?"true":"false");
    b.textContent=v.label||k;
    b.addEventListener("click",function(){
      tabs.querySelectorAll(".tab").forEach(function(x){x.setAttribute("aria-selected","false");});
      b.setAttribute("aria-selected","true");
      panels.querySelectorAll(".panel").forEach(function(p){p.classList.remove("on");});
      var t=$("p-"+k); if(t)t.classList.add("on");});
    tabs.appendChild(b);

    var div=document.createElement("div");
    div.className="panel"+(i===0?" on":""); div.id="p-"+k;
    var isMail=/邮件/.test(v.media||"");
    var body=(v.para||[]).map(function(p){
      return isMail? '<p>'+esc(p).replace(/\\n/g,"<br>")+'</p>' : esc(p);}).join(isMail?"":"<br>");
    var sub=(isMail&&(CASE.email||{}).subject)?
      '<div class="subject"><b class="no-copy">主题</b><span>'+esc(CASE.email.subject)+'</span></div>':"";
    var wc=(v.para||[]).join("").replace(/\\s/g,"").length;
    div.innerHTML='<div class="card"><div class="toolbar">'+
      '<button class="btn" data-copy="#pv'+k+'">复制</button>'+
      '<span class="mono">'+(v.media||"")+' · '+wc+' 字'+(v.push?' · 推进力 '+esc(v.push):"")+'</span></div>'+
      '<div class="copyable" id="pv'+k+'">'+sub+'<div class="msg">'+body+'</div></div>'+
      '<div class="bars"><span><b>语气</b> '+esc(v.tone||"—")+'</span>'+
      '<span><b>风险</b> '+esc(v.risk||"—")+'</span>'+
      '<span><b>适合</b> '+esc(v.fit||"—")+'</span></div></div>';
    panels.appendChild(div);});
})();

/* ---------- 05 快速调整 ---------- */
(function(){
  var chips=$("chips"), out=$("adjOut"), tagEl=$("adjTag"), noteEl=$("adjNote");
  var ADJ=CASE.adjusts||[];
  function show(a){ out.textContent=a.x||""; tagEl.textContent=a.tag||""; noteEl.textContent=a.note||""; }
  ADJ.forEach(function(a,i){
    var b=document.createElement("button");
    b.className="chip"; b.type="button"; b.textContent=a.t||("调整"+(i+1));
    b.setAttribute("aria-pressed", i===0?"true":"false");
    b.addEventListener("click",function(){
      chips.querySelectorAll(".chip").forEach(function(x){x.setAttribute("aria-pressed","false");});
      b.setAttribute("aria-pressed","true"); show(a);});
    chips.appendChild(b);
  });
  if(ADJ.length) show(ADJ[0]);
  setHTML("ruleSpec",(CASE.rules||[]).map(function(r){
    return '<li><span class="k">'+esc(r.k)+'</span><span class="v">'+esc(r.v)+'</span></li>';}).join(""));
})();

/* ---------- 06 边界审计 ---------- */
(function(){
  var MARK={"✔":"✔","◐":"◐","▲":"▲","—":"—"};
  var CLS={"✔":"p-ok","◐":"p-mid","▲":"p-del","—":"p-none"};
  var rows=CASE.audit||[];
  setText("auditTitle","边界审计："+rows.length+" 条 × 4 个版本");
  var st=$("stats"); st.innerHTML="";
  (CASE.audit_summary||[]).forEach(function(s){
    var zero=String(s.v).trim()==="0";
    var d=document.createElement("div");
    d.className="stat "+(zero?"zero":"wait");
    d.innerHTML='<b>'+esc(s.v)+'</b><span>'+esc(s.k)+'</span>';
    st.appendChild(d);});
  var tb=$("auditBody");
  rows.forEach(function(r){
    var tr=document.createElement("tr");
    var html='<td class="c"><span class="mono" style="color:#0f766e;font-weight:700">'+esc(r.id)+'</span></td>'+
             '<td>'+esc(r.item)+'</td>';
    VK.forEach(function(k){
      var v=(r.v||{})[k]||"—";
      html+='<td class="c"><span class="pill '+(CLS[v]||"p-none")+'">'+(MARK[v]||"")+'</span></td>';});
    html+='<td style="color:#64748b">'+esc(r.why)+'</td>';
    tr.innerHTML=html; tb.appendChild(tr);});
})();

/* ---------- 07 待填 ---------- */
(function(){
  var list=$("phList"), phs=CASE.placeholders||[];
  setText("phTitle", phs.length+" 个【待填】的归属");
  phs.forEach(function(p){
    var d=document.createElement("div"); d.className="ph";
    d.innerHTML='<div class="hd"><span class="id">'+esc(p.id)+'</span>'+
      '<span class="nm">【待填】'+esc(p.item)+'</span></div>'+
      '<div class="mt"><b>确认人：'+esc(p.owner||"—")+'</b>　位置：'+esc(p.where||"—")+
      '<br>建议口径：'+esc(p.how||"—")+'<br>风险：'+esc(p.risk||"—")+'</div>';
    list.appendChild(d);});
})();

/* ---------- 08 场景 ---------- */
(function(){
  var box=$("scnList");
  (CASE.scenarios||[]).forEach(function(s,i){
    var d=document.createElement("div"); d.className="scn";
    d.innerHTML='<div class="scn-hd"><span class="n">0'+(i+1)+'</span><b>场景 · '+esc(s.n)+'</b>'+
      '<button class="btn ghost" data-copy="#scnRec'+i+'">复制推荐版</button></div>'+
      '<div class="scn-bd">'+
      '<div class="q"><b>我的原话</b>'+esc(s.q)+'</div>'+
      '<p class="rec copyable" id="scnRec'+i+'">'+esc(s.rec)+'</p>'+
      (s.short?'<div class="short"><b>已读不回时</b>'+esc(s.short)+'</div>':'')+
      '<div class="red"><b>红线：</b>'+esc(s.red)+'</div></div>';
    box.appendChild(d);});
})();

/* ---------- 09 追问 ---------- */
(function(){
  var box=$("replyList");
  (CASE.replies||[]).forEach(function(r,i){
    var d=document.createElement("details");
    if(i===0) d.open=true;
    d.innerHTML='<summary>'+esc(r.q)+'</summary><div class="d-bd">'+
      '<p class="say">'+esc(r.say)+'</p>'+
      '<div class="ban"><b>禁止说法</b>'+esc(r.ban)+'</div>'+
      '<div class="why"><b>为什么</b>'+esc(r.why)+'</div></div>';
    box.appendChild(d);});
})();

/* ---------- 10 清单 ---------- */
(function(){
  var box=$("checks"), bar=$("barFill"), ptxt=$("progTxt");
  (CASE.checklist||[]).forEach(function(c){
    var lab=document.createElement("label"); lab.className="ck";
    lab.innerHTML='<input type="checkbox"><span class="t"><b>'+esc(c.dim)+'</b>'+esc(c.item)+'</span>';
    box.appendChild(lab);});
  function refresh(){
    var all=box.querySelectorAll("input"), n=box.querySelectorAll("input:checked").length;
    var pct=all.length? Math.round(n/all.length*100):0;
    bar.style.width=pct+"%";
    ptxt.textContent=n+" / "+all.length+(pct===100?"　可以发了":"");
  }
  box.addEventListener("change",refresh); refresh();
})();

/* ---------- footer ---------- */
(function(){
  setHTML("footerRules",(CASE.rules||[]).map(function(r,i){
    return '<div class="rule"><span class="n">RULE 0'+(i+1)+'</span><b>'+esc(r.k)+'</b><p>'+esc(r.v)+'</p></div>';}).join(""));
  var parts=[];
  if(CASE.disclaim) parts.push(esc(CASE.disclaim));
  (CASE.notes||[]).forEach(function(n){parts.push(esc(n));});
  setHTML("disclaim",parts.join("<br>"));
})();

/* ---------- 复制 / 跳转 / toast ---------- */
var toastEl=$("toast"), timer;
function toast(msg){toastEl.textContent=msg||"已复制，可直接粘贴";toastEl.classList.add("on");
  clearTimeout(timer);timer=setTimeout(function(){toastEl.classList.remove("on");},1700);}
function textOf(el){
  var c=el.cloneNode(true);
  c.querySelectorAll(".no-copy").forEach(function(n){n.remove();});
  return c.innerText.replace(/\\u00a0/g," ").replace(/\\n{3,}/g,"\\n\\n").trim();
}
function fallback(txt){
  var ta=document.createElement("textarea");ta.value=txt;ta.style.position="fixed";ta.style.opacity="0";
  document.body.appendChild(ta);ta.select();
  try{document.execCommand("copy");toast();}catch(e){toast("复制失败，请手动选择");}
  document.body.removeChild(ta);
}
document.addEventListener("click",function(e){
  var c=e.target.closest("[data-copy]");
  if(c){e.preventDefault();
    var el=document.querySelector(c.getAttribute("data-copy"));
    if(!el)return;
    var txt=textOf(el);
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(txt).then(function(){toast();},function(){fallback(txt);});
    }else{fallback(txt);}
    return;}
  var j=e.target.closest("[data-jump]");
  if(j){e.preventDefault();var t=document.querySelector(j.getAttribute("data-jump"));
    if(t)t.scrollIntoView({behavior:"smooth"});}
});
})();
</script>
</body>
</html>
"""


def build(case, outdir):
    xlsx, html_path = C.out_paths(case, outdir)
    meta = case.get("meta") or {}
    title = "%s · %s｜客户沟通润色" % (meta.get("product", "化工品"), meta.get("scenario", "客户沟通"))
    payload = json.dumps(case, ensure_ascii=False).replace("</", "<\\/")
    doc = (HTML.replace("__CSS__", CSS)
                .replace("__TITLE__", title.replace("<", "&lt;"))
                .replace("__CASE__", payload))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return html_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", default="out")
    args = ap.parse_args(argv)
    case = C.load_case(args.case)
    print("html →", build(case, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
