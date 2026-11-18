# -*- coding: utf-8 -*-
"""生成自包含交互式 HTML 核验报告（数据全部来自 input.json）"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (CATEGORY_ORDER, STRENGTH, VERDICT_META, VERDICT_RULES,
                     categories_of, esc as e, load_doc)

DIMENSIONS, CASES, MATERIALS, ONSITE, SOURCES = [], [], [], [], []
META, PROFILE = {}, {}
REPORT_ID = REPORT_DATE = PRODUCT = PRODUCT_SPEC = ""
SYNTHETIC = set()


def dash(score):
    return round(2 * 3.1415926 * 58 * float(score) / 100, 1)


CSS = r"""
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:#EEF1F5;color:#16283C;
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
 font-size:14px;line-height:1.7;-webkit-font-smoothing:antialiased}
a{color:#0F5C8C;text-decoration:none}
a:hover{text-decoration:underline}
:root{
 --ink:#0B1F33;--ink2:#123A5A;--muted:#64748B;--line:#E3E9EF;--paper:#F1F4F7;--card:#fff;
 --gold:#B8892B;--gold2:#D9B768;--green:#0F7B5F;--amber:#B7791F;--red:#B23A2E;--gray:#64748B;
}
.wrap{max-width:1280px;margin:0 auto;padding:0 24px}
/* ---------- topbar ---------- */
.topbar{position:sticky;top:0;z-index:80;background:rgba(11,31,51,.97);color:#fff;border-bottom:1px solid rgba(216,178,92,.28)}
.topbar .inner{max-width:1280px;margin:0 auto;height:62px;padding:0 24px;display:flex;align-items:center;gap:14px}
.mark{width:30px;height:30px;border:1px solid var(--gold2);display:grid;place-items:center;
 font-family:Consolas,monospace;font-size:11px;letter-spacing:.08em;color:var(--gold2)}
.brand{font-size:14px;letter-spacing:.14em;font-weight:600}
.brand small{display:block;font-size:10px;letter-spacing:.22em;color:#8FA6BC;font-weight:400}
.tb-spacer{flex:1}
.tb-meta{font-family:Consolas,monospace;font-size:11px;color:#9FB3C6;letter-spacing:.04em}
.tb-btn{border:1px solid rgba(255,255,255,.22);background:transparent;color:#DCE6EF;border-radius:8px;
 padding:7px 13px;font-size:12px;cursor:pointer;transition:.2s}
.tb-btn:hover{background:rgba(255,255,255,.08);border-color:rgba(216,178,92,.5)}
/* ---------- intro ---------- */
.intro{padding:44px 0 26px}
.eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:.22em;color:var(--gold);text-transform:uppercase}
h1{font-size:38px;line-height:1.25;margin:12px 0 12px;letter-spacing:-.01em;font-weight:700;color:var(--ink)}
.lead{font-size:15px;color:#4A5C6E;max-width:760px;margin:0}
.searchbar{display:grid;grid-template-columns:1.2fr 1.2fr 1.1fr auto;gap:10px;margin-top:26px;
 background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px;box-shadow:0 10px 30px -22px rgba(11,31,51,.5)}
.searchbar label{display:block;padding:6px 12px;border-right:1px solid var(--line)}
.searchbar label:last-of-type{border-right:none}
.searchbar span{display:block;font-size:10.5px;letter-spacing:.14em;color:var(--muted);text-transform:uppercase}
.searchbar input{border:none;outline:none;width:100%;font-size:14px;font-family:inherit;color:var(--ink);background:transparent;padding:3px 0}
.searchbar input::placeholder{color:#A9B6C4}
.btn-run{background:var(--ink);color:#fff;border:none;border-radius:10px;padding:0 26px;font-size:13.5px;
 letter-spacing:.06em;cursor:pointer;transition:.2s;font-family:inherit}
.btn-run:hover{background:#17395C}
.hint{margin-top:9px;font-size:12px;color:var(--muted)}
.hint b{color:#41566B}
/* ---------- case nav ---------- */
.casenav{position:sticky;top:62px;z-index:70;background:rgba(238,241,245,.93);backdrop-filter:blur(10px);
 border-bottom:1px solid #DDE4EB;margin-bottom:22px}
.casenav .inner{max-width:1280px;margin:0 auto;padding:10px 24px;display:flex;gap:8px;overflow-x:auto}
.casebtn{display:flex;align-items:center;gap:8px;border:1px solid #D8E0E8;background:#fff;border-radius:999px;
 padding:8px 15px;font-size:12.5px;color:#33475B;cursor:pointer;white-space:nowrap;font-family:inherit;transition:.18s}
.casebtn .d{width:7px;height:7px;border-radius:50%;background:#B9C4CF}
.casebtn:hover{border-color:#B7C4D2;transform:translateY(-1px)}
.casebtn.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.casebtn.on .d{background:var(--gold2)}
.casebtn .v{font-size:10.5px;opacity:.65;font-family:Consolas,monospace}
/* ---------- case ---------- */
.case{display:none;animation:fade .35s ease}
.case.on{display:block}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.hero{display:grid;grid-template-columns:1fr 330px;background:#fff;border:1px solid var(--line);
 border-radius:18px;overflow:hidden;box-shadow:0 18px 40px -34px rgba(11,31,51,.7)}
.hero-main{padding:30px 34px 28px;position:relative}
.hero-main:after{content:"";position:absolute;left:0;top:0;width:4px;height:100%;
 background:linear-gradient(180deg,var(--gold2),var(--gold),transparent)}
.hero-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.vbadge{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:5px 13px;
 font-size:12.5px;font-weight:600;letter-spacing:.04em;border:1px solid}
.vbadge.green{color:var(--green);background:#EAF6F1;border-color:#BFE3D6}
.vbadge.amber{color:var(--amber);background:#FDF4E3;border-color:#EFD6A8}
.vbadge.red{color:var(--red);background:#FBEDEA;border-color:#EBC3BB}
.vbadge.gray{color:var(--gray);background:#F2F5F8;border-color:#D8E0E7}
.conf{font-size:11.5px;color:#5B6B7C;background:#F4F7FA;border:1px solid #E2E9EF;border-radius:6px;padding:3px 9px}
.repoid{margin-left:auto;font-family:Consolas,monospace;font-size:10.5px;color:#93A3B3;letter-spacing:.06em}
.hero h2{font-size:27px;line-height:1.3;margin:0;color:var(--ink);letter-spacing:-.01em}
.hero h2 small{display:block;font-size:13px;font-weight:400;color:#6B7C8E;margin-top:6px;letter-spacing:.02em}
.subline{margin-top:10px;font-size:13.5px;color:#3C536A}
.headline{margin:16px 0 0;font-size:15.5px;line-height:1.7;color:#1E3A55;font-weight:600;
 padding-left:14px;border-left:2px solid var(--gold)}
.meta-row{display:flex;flex-wrap:wrap;gap:7px;margin-top:18px}
.meta-row span{font-size:11.5px;color:#4F6377;background:#F3F6F9;border:1px solid #E4EAF0;border-radius:6px;padding:4px 10px}
.hero-side{background:linear-gradient(155deg,#0B1F33 0%,#123A5A 70%,#16456A 100%);color:#fff;
 padding:26px 24px;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;overflow:hidden}
.hero-side:before{content:"";position:absolute;inset:0;
 background-image:radial-gradient(rgba(216,178,92,.16) 1px,transparent 1px);background-size:16px 16px;opacity:.5}
.ring{width:150px;height:150px;position:relative;z-index:1}
.ring-bg{fill:none;stroke:rgba(255,255,255,.13);stroke-width:7}
.ring-fg{fill:none;stroke:var(--gold2);stroke-width:7;stroke-linecap:round;transform:rotate(-90deg);transform-origin:70px 70px;transition:stroke-dasharray .8s}
.ring-num{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:2}
.ring-num b{font-size:34px;font-weight:600;letter-spacing:-.02em;line-height:1}
.ring-num span{font-size:10px;letter-spacing:.18em;color:#9FB6CB;margin-top:6px}
.side-label{margin-top:14px;font-size:11px;letter-spacing:.18em;color:#B7CADC;z-index:1}
.side-counts{margin-top:8px;font-family:Consolas,monospace;font-size:11px;color:#8FA9BF;z-index:1}
.synthetic{margin:12px 0 0;background:#FFF8E8;border:1px solid #EFD9A8;color:#7A5A15;border-radius:10px;
 padding:10px 14px;font-size:12.5px}
/* ---------- verdict box ---------- */
.vbox{margin:16px 0;background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px 24px;
 display:grid;grid-template-columns:120px 1fr;gap:18px}
.vbox .lab{font-size:11px;letter-spacing:.16em;color:var(--gold);text-transform:uppercase;padding-top:3px}
.vbox p{margin:0;font-size:13.8px;line-height:1.85;color:#31465A}
.vbox .next{margin-top:10px;font-size:12.5px;color:#5B6B7C;border-top:1px dashed #E2E9EF;padding-top:10px}
.vbox .next b{color:var(--ink)}
/* ---------- facts ---------- */
.facts{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:0 0 8px}
.fact{background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 14px;position:relative;overflow:hidden}
.fact:before{content:"";position:absolute;left:0;top:0;width:100%;height:2px;background:#E8EEF3}
.fact.g:before{background:linear-gradient(90deg,var(--gold2),transparent)}
.fact .k{font-size:10.5px;letter-spacing:.12em;color:var(--muted);text-transform:uppercase}
.fact .v{font-size:15px;font-weight:600;color:var(--ink);margin-top:5px;line-height:1.4}
.fact .n{font-size:11px;color:#7B8B9B;margin-top:4px;line-height:1.5}
/* ---------- section ---------- */
.sec{margin:34px 0}
.sec-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:14px;flex-wrap:wrap}
.sec-head h3{font-size:19px;margin:0;color:var(--ink);letter-spacing:-.01em}
.sec-head p{margin:5px 0 0;font-size:12.5px;color:var(--muted);max-width:720px}
.sec-head .idx{font-family:Consolas,monospace;font-size:11px;color:var(--gold);letter-spacing:.16em;margin-right:9px}
/* ---------- filters ---------- */
.filters{display:flex;gap:7px;flex-wrap:wrap}
.filters button{border:1px solid #DCE3EA;background:#fff;color:#4A5D70;font-size:12px;border-radius:8px;
 padding:6px 12px;cursor:pointer;font-family:inherit;transition:.16s}
.filters button:hover{border-color:#B9C7D5}
.filters button.on{background:#EAF0F6;border-color:#9FB4C8;color:var(--ink);font-weight:600}
/* ---------- evidence groups ---------- */
.group{margin-top:18px}
.group-head{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #DCE3EA;margin-bottom:12px}
.g-idx{width:22px;height:22px;border-radius:6px;display:grid;place-items:center;font-size:11px;font-family:Consolas,monospace}
.g-a .g-idx{background:#E7F2EC;color:var(--green)}
.g-b .g-idx{background:#EDF2F8;color:#2F5F8A}
.g-c .g-idx{background:#F1F3F5;color:#7B8B9B}
.group-head h4{margin:0;font-size:14.5px;color:var(--ink)}
.group-head .note{font-size:11.5px;color:#8494A5}
.group-head .count{margin-left:auto;font-family:Consolas,monospace;font-size:11px;color:#7B8B9B}
.ev-list{display:grid;gap:11px}
.ev{background:#fff;border:1px solid var(--line);border-left:3px solid #CBD6E1;border-radius:11px;
 padding:16px 19px;transition:.18s;scroll-margin-top:130px}
.ev:hover{border-color:#C3D0DC;box-shadow:0 10px 26px -20px rgba(11,31,51,.55);transform:translateY(-1px)}
.ev.s3{border-left-color:var(--green)}
.ev.s2{border-left-color:var(--amber)}
.ev.s1{border-left-color:#8FA3B6}
.ev-top{display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap}
.ev-top .code{font-family:Consolas,monospace;font-size:11px;color:#fff;background:#2B4763;border-radius:5px;
 padding:2px 7px;letter-spacing:.05em;margin-top:2px}
.ev-top h5{margin:0;font-size:15px;color:var(--ink);flex:1;min-width:220px;line-height:1.5;font-weight:600}
.pill{font-size:10.5px;border-radius:999px;padding:2px 9px;border:1px solid;letter-spacing:.04em;white-space:nowrap}
.pill.strong{color:var(--green);background:#EDF8F3;border-color:#C6E4D8}
.pill.mid{color:var(--amber);background:#FDF5E6;border-color:#EDD8AC}
.pill.weak{color:#63768A;background:#F2F5F8;border-color:#DCE4EB}
.pill.na{color:#7B8B9B;background:#F1F3F5;border-color:#DDE3E9}
.ev-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:9px 0 10px;font-size:11.5px;color:#7B8B9B}
.ev-meta .dot{width:3px;height:3px;border-radius:50%;background:#C3CED9}
.ev-meta .cat{background:#F4F7FA;border:1px solid #E5EBF1;border-radius:5px;padding:1px 7px;color:#5D7084}
blockquote{margin:0;background:#F8FAFC;border-left:2px solid #DDE6EE;border-radius:0 7px 7px 0;
 padding:10px 14px;font-size:12.8px;color:#3B5169;line-height:1.8;overflow-wrap:anywhere}
.why{margin-top:10px;font-size:12.8px;color:#3F5568;line-height:1.8;overflow-wrap:anywhere}
.why b{color:var(--gold);font-weight:600;margin-right:6px;letter-spacing:.02em}
.ev-foot{display:flex;align-items:center;gap:14px;margin-top:11px;padding-top:10px;border-top:1px dashed #E6ECF2}
.ev-foot a{font-size:12px;color:#0F5C8C;display:inline-flex;align-items:center;gap:4px}
.ev-foot .finger{margin-left:auto;font-family:Consolas,monospace;font-size:10px;color:#A6B3C0}
.ev.x{border-left-color:#C9D2DB;background:#FBFCFD}
.ev.x .ev-top h5{color:#5E6E7E;font-weight:500}
.ev.x blockquote{background:#F5F7F9;color:#6B7B8B}
.ev.x .why b{color:#8A98A6}
.empty{background:#FBFCFD;border:1px dashed #CDD8E2;border-radius:11px;padding:18px 20px;font-size:13px;color:#5B6B7C}
.empty b{color:var(--red)}
/* ---------- timeline ---------- */
.tl{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:0;background:#fff;border:1px solid var(--line);
 border-radius:14px;padding:22px 8px 18px;overflow-x:auto}
.tl-item{padding:0 16px;position:relative}
.tl-item:before{content:"";position:absolute;left:0;right:0;top:5px;height:1px;background:#E1E8EE}
.tl-item:first-child:before{left:16px}
.tl-item:last-child:before{right:calc(100% - 16px)}
.tl-dot{width:11px;height:11px;border-radius:50%;background:#fff;border:2px solid var(--gold);position:relative;z-index:1;margin-bottom:12px}
.tl-year{font-family:Consolas,monospace;font-size:12px;color:var(--gold);letter-spacing:.06em}
.tl-item b{display:block;font-size:13px;color:var(--ink);margin-top:3px}
.tl-item p{margin:3px 0 0;font-size:11.5px;color:#7B8B9B;line-height:1.6}
/* ---------- score ---------- */
.score{background:#fff;border:1px solid var(--line);border-radius:14px;padding:24px 26px;display:grid;
 grid-template-columns:190px 1fr;gap:30px}
.score-total{text-align:center;border-right:1px solid #E8EEF3;padding-right:20px}
.score-total b{display:block;font-size:52px;line-height:1;color:var(--ink);letter-spacing:-.03em;font-weight:600}
.score-total small{font-size:11px;color:var(--muted);letter-spacing:.1em}
.score-total .tag{margin-top:10px;font-size:11px;color:#5B6B7C}
.bar-row{display:grid;grid-template-columns:170px 1fr 54px;align-items:center;gap:12px;margin-bottom:11px}
.bar-row .l{font-size:12.5px;color:#3F5568}
.bar-row .l em{display:block;font-style:normal;font-size:10.5px;color:#93A3B3}
.bar{height:7px;background:#EDF1F5;border-radius:99px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#2C5A82,#4E86B4)}
.bar-row .v{font-family:Consolas,monospace;font-size:12px;color:#5B6B7C;text-align:right}
.score-note{grid-column:1/-1;font-size:11.5px;color:#7B8B9B;border-top:1px dashed #E6ECF2;padding-top:12px}
/* ---------- gaps ---------- */
.gaps{background:linear-gradient(160deg,#0B1F33,#153E60);color:#fff;border-radius:14px;padding:24px 26px}
.gaps h4{margin:0 0 4px;font-size:15px;letter-spacing:.02em}
.gaps .gp{font-size:11.5px;color:#9FB6CB;margin-bottom:12px}
.gaps ul{margin:0;padding-left:0;list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:8px 20px}
.gaps li{font-size:12.5px;color:#D6E2EC;padding-left:18px;position:relative;line-height:1.7}
.gaps li:before{content:"□";position:absolute;left:0;color:var(--gold2)}
.gaps .act{margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,.12);
 font-size:12.5px;color:#C9D8E5;display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}
.gaps .act b{color:#fff}
.gaps .act a{color:#F0D79B;font-weight:600;border-bottom:1px solid rgba(240,215,155,.5);padding-bottom:2px;white-space:nowrap}
.gaps .act a:hover{text-decoration:none;color:#fff;border-color:#fff}
/* ---------- method ---------- */
.method{background:#fff;border:1px solid var(--line);border-radius:16px;padding:28px 30px}
.tri{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:6px}
.tri-card{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:#FBFCFD}
.tri-card .n{font-family:Consolas,monospace;font-size:10.5px;color:var(--gold);letter-spacing:.14em}
.tri-card h5{margin:6px 0 6px;font-size:14.5px;color:var(--ink)}
.tri-card p{margin:0;font-size:12.3px;color:#5E7083;line-height:1.75}
.tri-card.c1{border-top:3px solid var(--green)}
.tri-card.c2{border-top:3px solid #2F5F8A}
.tri-card.c3{border-top:3px solid #A9B6C3}
.tree{margin-top:26px;border-top:1px dashed #E6ECF2;padding-top:22px}
.tree h4{font-size:14px;margin:0 0 12px;color:var(--ink)}
.tree-row{display:grid;grid-template-columns:64px 1fr 230px;gap:14px;align-items:start;
 border:1px solid var(--line);border-radius:10px;padding:12px 15px;margin-bottom:8px;background:#fff}
.tree-row .q{font-family:Consolas,monospace;font-size:11px;color:var(--gold);letter-spacing:.1em;padding-top:3px}
.tree-row b{font-size:13px;color:var(--ink);display:block}
.tree-row p{margin:2px 0 0;font-size:11.8px;color:#7B8B9B;line-height:1.65}
.tree-row .ans{font-size:11.5px;color:#3F5568;background:#F6F8FA;border:1px solid #E6ECF2;border-radius:8px;padding:7px 10px;line-height:1.6}
.tree-row .ans i{font-style:normal;color:var(--green);font-weight:600}
/* ---------- materials ---------- */
.mats{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden}
.mat-bar{display:flex;align-items:center;gap:16px;padding:16px 22px;border-bottom:1px solid var(--line);background:#FBFCFD}
.mat-bar .prog{flex:1;height:6px;background:#EDF1F5;border-radius:99px;overflow:hidden}
.mat-bar .prog i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--gold),var(--gold2));transition:width .3s}
.mat-bar .cnt{font-family:Consolas,monospace;font-size:12px;color:#5B6B7C;white-space:nowrap}
table.mat{width:100%;border-collapse:collapse}
table.mat th{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:#7B8B9B;font-weight:600;
 text-align:left;padding:11px 14px;border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0}
table.mat td{padding:13px 14px;border-bottom:1px solid #EEF2F6;font-size:12.6px;vertical-align:top;color:#3F5568}
table.mat tr:hover td{background:#FAFCFE}
table.mat td.name{font-weight:600;color:var(--ink);min-width:200px}
table.mat .chk{width:38px}
input[type=checkbox]{width:15px;height:15px;accent-color:#0F7B5F;cursor:pointer}
.pri{font-family:Consolas,monospace;font-size:10px;border-radius:4px;padding:2px 6px;border:1px solid}
.pri.P0{color:#B23A2E;background:#FBEDEA;border-color:#EBC3BB}
.pri.P1{color:#B7791F;background:#FDF5E6;border-color:#EDD8AC}
.pri.P2{color:#63768A;background:#F2F5F8;border-color:#DCE4EB}
.copy{border:1px solid #DCE3EA;background:#fff;border-radius:6px;font-size:10.5px;padding:3px 8px;
 cursor:pointer;color:#5B6B7C;font-family:inherit;white-space:nowrap}
.copy:hover{background:#F2F6FA;color:var(--ink)}
.script{font-size:11.6px;color:#6B7B8B;line-height:1.65;margin-top:3px}
/* ---------- onsite ---------- */
.onsite{display:grid;grid-template-columns:repeat(4,1fr);gap:11px}
.os{background:#fff;border:1px solid var(--line);border-radius:11px;padding:15px 16px}
.os .n{font-family:Consolas,monospace;font-size:10px;color:var(--gold);letter-spacing:.1em}
.os b{display:block;font-size:13.2px;color:var(--ink);margin:5px 0 5px}
.os p{margin:0;font-size:11.7px;color:#6B7B8B;line-height:1.65}
.os .fake{color:#B23A2E;margin-top:6px;font-size:11.4px}
/* ---------- compare ---------- */
.cmp{background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}
table.cmp-t{width:100%;border-collapse:collapse}
table.cmp-t th{background:var(--ink);color:#fff;font-size:11px;letter-spacing:.08em;font-weight:500;
 padding:11px 13px;text-align:left;white-space:nowrap}
table.cmp-t td{padding:12px 13px;border-bottom:1px solid #EEF2F6;font-size:12.4px;color:#3F5568;vertical-align:top}
table.cmp-t tr:last-child td{border-bottom:none}
.vchip{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:2px 9px;font-size:11px;border:1px solid;white-space:nowrap}
.vchip.green{color:var(--green);background:#EDF8F3;border-color:#C6E4D8}
.vchip.amber{color:var(--amber);background:#FDF5E6;border-color:#EDD8AC}
.vchip.red{color:var(--red);background:#FBEDEA;border-color:#EBC3BB}
.vchip.gray{color:var(--gray);background:#F2F5F8;border-color:#D8E0E7}
/* ---------- footer ---------- */
footer{margin:48px 0 40px;padding-top:22px;border-top:1px solid #DCE3EA;font-size:11.5px;color:#8494A5;line-height:1.9}
footer b{color:#5B6B7C}
/* ---------- toast ---------- */
#toast{position:fixed;left:50%;bottom:34px;transform:translate(-50%,20px);background:#0B1F33;color:#fff;
 border:1px solid rgba(216,178,92,.4);border-radius:10px;padding:11px 18px;font-size:12.5px;opacity:0;
 pointer-events:none;transition:.25s;z-index:200;box-shadow:0 18px 40px -20px rgba(0,0,0,.6)}
#toast.on{opacity:1;transform:translate(-50%,0)}
/* ---------- responsive ---------- */
@media (max-width:1100px){
 .hero{grid-template-columns:1fr}
 .hero-side{flex-direction:row;gap:24px;padding:18px}
 .facts{grid-template-columns:repeat(3,1fr)}
 .score{grid-template-columns:1fr}
 .score-total{border-right:none;border-bottom:1px solid #E8EEF3;padding:0 0 16px}
 .onsite{grid-template-columns:repeat(2,1fr)}
 .tri{grid-template-columns:1fr}
 .tree-row{grid-template-columns:52px 1fr}
 .tree-row .ans{grid-column:1/-1}
 .searchbar{grid-template-columns:1fr 1fr}
 .searchbar label{border-right:none;border-bottom:1px solid var(--line)}
 .btn-run{grid-column:1/-1;padding:12px}
}
@media (max-width:700px){
 .wrap{padding:0 14px}
 h1{font-size:27px}
 .hero-main{padding:22px 18px}
 .hero h2{font-size:21px}
 .facts{grid-template-columns:1fr 1fr}
 .tl{grid-auto-flow:row;grid-auto-columns:auto}
 .tl-item:before{display:none}
 .gaps ul{grid-template-columns:1fr}
 .onsite{grid-template-columns:1fr}
 .vbox{grid-template-columns:1fr;gap:6px}
 .searchbar{grid-template-columns:1fr}
 .tb-meta{display:none}
}
@media print{
 body{background:#fff}
 .topbar,.casenav,.searchbar,.hint,.filters,.copy,#toast,.btn-run,.tb-btn{display:none!important}
 .case{display:none}.case.on{display:block}
 .hero,.ev,.score,.mats,.method,.cmp{box-shadow:none;break-inside:avoid}
 a{color:#0B1F33}
 .gaps{background:#fff;color:#16283C;border:1px solid #ccc}
 .gaps li,.gaps .act,.gaps .gp{color:#444}
}
"""


def badge(verdict):
    meta = VERDICT_META[verdict]
    return f'<span class="vbadge {meta["color"]}">{meta["icon"]} {e(verdict)}</span>'


def strength_pill(s):
    name, dots, _ = STRENGTH[s]
    cls = {3: "strong", 2: "mid", 1: "weak", 0: "na"}[s]
    label = f"{dots} {name}" if s else "不计分"
    return f'<span class="pill {cls}">{label}</span>'


def ev_card(item, group):
    s = item["strength"]
    cls = f"ev s{s}" if group != "excluded" else "ev x"
    cat = f'<span class="cat">{e(item.get("cat", ""))}</span>' if item.get("cat") else ""
    src = f'<span class="src">{e(item.get("source", "对方提供"))}</span><span class="dot"></span>' if item.get("source") else ""
    date = f'<span>{e(item["date"])}</span>' if item.get("date") else ""
    quote = f"<blockquote>{e(item['quote'])}</blockquote>" if item.get("quote") else ""
    why_label = "判读" if group != "excluded" else "为什么不算"
    link = ""
    if item.get("url"):
        link = f'<a href="{e(item["url"])}" target="_blank" rel="noopener">查看原始记录 ↗</a>'
    finger = f'<span class="finger">ID {e(item["code"])} / {REPORT_ID}</span>'
    return f"""<article class="{cls}" data-cat="{e(item.get('cat',''))}">
  <div class="ev-top">
    <span class="code">{e(item['code'])}</span>
    <h5>{e(item['title'])}</h5>
    {strength_pill(s)}
  </div>
  <div class="ev-meta">{src}{date}{cat}</div>
  {quote}
  <div class="why"><b>{why_label}</b>{e(item['why'])}</div>
  <div class="ev-foot">{link}{finger}</div>
</article>"""


def group_html(gid, letter, title, note, items, case):
    if not items:
        if gid == "direct":
            body = (f'<div class="empty"><b>0 条。</b>本次检索未发现任何可指向“{e(PRODUCT)}生产装置”的硬证据——'
                    '既无对应行业类别的排污许可，也无环评批复、项目备案或可核产量。'
                    '这本身就是一个强信号：不能用“没查到”代替“确认”，应当降级处理。</div>')
        elif gid == "indirect":
            body = ('<div class="empty"><b>0 条。</b>没有找到业务侧旁证：无官网产品页、无代理授权、无成交与仓配记录。'
                    '这通常意味着对方在公开市场几乎没有痕迹，风险等级应上调。</div>')
        else:
            body = ('<div class="empty"><b>0 条。</b>没有需要单独排除的材料——但这不等于证据充分，'
                    '只说明本次检索没有拿到“看似证据”的东西。</div>')
    else:
        body = "\n".join(ev_card(i, gid) for i in items)
    return f"""<div class="group {letter}" data-group="{gid}">
  <div class="group-head">
    <span class="g-idx">{'A' if gid=='direct' else ('B' if gid=='indirect' else 'C')}</span>
    <h4>{e(title)}</h4><span class="note">{e(note)}</span>
    <span class="count">{len(items)} 条</span>
  </div>
  <div class="ev-list">{body}</div>
</div>"""


def case_section(c, idx):
    meta = VERDICT_META[c["verdict"]]
    n_d, n_i, n_x = len(c["direct"]), len(c["indirect"]), len(c["excluded"])
    facts = "\n".join(
        f'<div class="fact {"g" if i == 0 else ""}"><div class="k">{e(k)}</div><div class="v">{e(v)}</div><div class="n">{e(n)}</div></div>'
        for i, (k, v, n) in enumerate(c["facts"]))
    cats = {}
    for it in c["direct"] + c["indirect"]:
        k = it.get("cat")
        if k:
            cats[k] = cats.get(k, 0) + 1
    order = [k for k in CATEGORY_ORDER if k in cats] + [k for k in cats if k not in CATEGORY_ORDER]
    filt = f'<button class="on" data-cat="all">全部 {n_d+n_i}</button>'
    for k in order:
        if cats[k]:
            filt += f'<button data-cat="{e(k)}">{e(k)} {cats[k]}</button>'
    filt += '<button data-cat="excluded">不构成证据</button>'

    tl = "\n".join(
        f'<div class="tl-item"><div class="tl-dot"></div><div class="tl-year">{e(y)}</div>'
        f'<b>{e(t)}</b><p>{e(d)}</p></div>' for y, t, d in c["timeline"])

    bars = ""
    for i, d in enumerate(DIMENSIONS):
        val = c["dims"][i]
        pct = round(val / d["weight"] * 100)
        bars += (f'<div class="bar-row"><div class="l">{e(d["name"])}<em>权重 {d["weight"]} 分</em></div>'
                 f'<div class="bar"><i style="width:{pct}%"></i></div>'
                 f'<div class="v">{val}/{d["weight"]}</div></div>')

    gaps = "".join(f"<li>{e(g)}</li>" for g in c["gaps"])

    synth = ('<div class="synthetic">⚠ 脱敏合成样例：用于演示判定路径与撰写口径，不指向任何真实企业；'
             '真实项目请替换为企业实际材料。</div>') if c["id"] in SYNTHETIC else ""

    return f"""<section class="case{' on' if idx==0 else ''}" id="case-{c['id']}" data-case="{c['id']}">
  <div class="hero">
    <div class="hero-main">
      <div class="hero-top">
        {badge(c['verdict'])}
        <span class="conf">置信度 {e(c['confidence'])}</span>
        <span class="repoid">REPORT {REPORT_ID}</span>
      </div>
      <h2>{e(c['company'])}<small>{e(c['unit'])}</small></h2>
      <div class="subline">{e(c['product'])} · {e(c['spec'])}</div>
      <p class="headline">{e(c['headline'])}</p>
      <div class="meta-row">
        <span>{e(c['listed'])}</span><span>{e(c['addr'])}</span><span>{e(c['process'])}</span>
        <span>{e(c['status'])}</span>
      </div>
    </div>
    <div class="hero-side">
      <div style="position:relative">
        <svg class="ring" viewBox="0 0 140 140">
          <circle class="ring-bg" cx="70" cy="70" r="58"></circle>
          <circle class="ring-fg" cx="70" cy="70" r="58" style="stroke-dasharray:{dash(c['score'])} 364.4"></circle>
        </svg>
        <div class="ring-num"><b>{c['score']}</b><span>/ 100</span></div>
      </div>
      <div class="side-label">证 据 充 分 度</div>
      <div class="side-counts">直接 {n_d} · 间接 {n_i} · 排除 {n_x}</div>
    </div>
  </div>
  {synth}
  <div class="vbox">
    <div class="lab">核验结论</div>
    <div>
      <p>{e(c['verdict_detail'])}</p>
      <div class="next"><b>下一步：</b>{e(c['next_action'])}</div>
    </div>
  </div>
  <div class="facts">{facts}</div>

  <div class="sec">
    <div class="sec-head">
      <div><h3><span class="idx">02</span>证据清单 · 三分法</h3>
      <p>同一份材料，放在哪一组决定它能不能被采信。绿色为“能指向装置”的硬证据，蓝色为业务旁证，灰色为常见误判材料。</p></div>
      <div class="filters" data-case="{c['id']}">{filt}</div>
    </div>
    {group_html('direct', 'g-a', '直接生产证据', '指向“装置、许可、产量”的硬证据', c['direct'], c)}
    {group_html('indirect', 'g-b', '间接业务证据', '业务侧旁证，需与直接证据联读', c['indirect'], c)}
    {group_html('excluded', 'g-c', '不构成证据', '容易被当作证据、但采信会出错的材料', c['excluded'], c)}
  </div>

  <div class="sec">
    <div class="sec-head"><div><h3><span class="idx">03</span>时间线</h3>
    <p>把公开事件按时间排列，可以看出一家企业是“有连续生产史”还是“只有一段宣传期”。</p></div></div>
    <div class="tl">{tl}</div>
  </div>

  <div class="sec">
    <div class="sec-head"><div><h3><span class="idx">04</span>证据充分度拆解</h3>
    <p>分数不是“真假概率”，而是“证据链完整度”。同一套权重，五个案例横向可比。</p></div></div>
    <div class="score">
      <div class="score-total"><b>{c['score']}</b><small>证据充分度 / 100</small>
        <div class="tag">{e(c['confidence'])}置信 · {e(c['verdict'])}</div></div>
      <div>{bars}</div>
      <div class="score-note">{e(c['score_note'])}</div>
    </div>
  </div>

  <div class="sec">
    <div class="gaps">
      <h4>还需要向对方索取（{c['short']}）</h4>
      <div class="gp">以下材料按“能否独立证明装置存在”排序，建议一次性发出，避免来回拉扯。</div>
      <ul>{gaps}</ul>
      <div class="act"><span>拿到材料后，用同一套三分法重新归档，再决定是否现场验厂。</span>
      <a href="#materials">进入完整尽调清单 →</a></div>
    </div>
  </div>
</section>"""


SCRIPT = r"""
const CASES = __CASES__;
const ALIAS = __ALIAS__;

function activate(id, scroll){
  document.querySelectorAll('.case').forEach(function(s){ s.classList.toggle('on', s.dataset.case===id); });
  document.querySelectorAll('.casebtn').forEach(function(b){ b.classList.toggle('on', b.dataset.target===id); });
  var c = document.getElementById('case-'+id);
  if(scroll && c){ c.scrollIntoView({behavior:'smooth', block:'start'}); }
  if(history.replaceState){ history.replaceState(null, '', '#'+id); }
}
document.querySelectorAll('.casebtn').forEach(function(b){
  b.addEventListener('click', function(){ activate(b.dataset.target, false); });
});

var toastEl = document.getElementById('toast');
var toastTimer;
function toast(msg){
  toastEl.textContent = msg; toastEl.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function(){ toastEl.classList.remove('on'); }, 2600);
}

document.getElementById('run').addEventListener('click', function(){
  var v = (document.getElementById('q-company').value || '').trim();
  if(!v){ toast('请输入企业名称'); return; }
  var hit = ALIAS.find(function(p){ return v.indexOf(p[0])>=0 || p[0].indexOf(v)>=0; });
  if(hit){ activate(hit[1], true); toast('已切换至：' + hit[0] + ' 案例'); }
  else { toast('演示模式仅内置 5 个案例；接入检索后可按企业全名自动取证'); }
});
document.getElementById('q-company').addEventListener('keydown', function(ev){
  if(ev.key==='Enter'){ document.getElementById('run').click(); }
});

document.querySelectorAll('.filters').forEach(function(f){
  f.addEventListener('click', function(ev){
    var btn = ev.target.closest('button'); if(!btn) return;
    f.querySelectorAll('button').forEach(function(b){ b.classList.remove('on'); });
    btn.classList.add('on');
    var cat = btn.dataset.cat;
    var sec = f.closest('.case');
    sec.querySelectorAll('.ev').forEach(function(card){
      var show = true;
      if(cat==='excluded'){ show = card.classList.contains('x'); }
      else if(cat!=='all'){ show = card.dataset.cat === cat; }
      card.style.display = show ? '' : 'none';
    });
    sec.querySelectorAll('.group').forEach(function(g){
      var n = [].slice.call(g.querySelectorAll('.ev')).filter(function(c){ return c.style.display!=='none'; }).length;
      g.style.display = n ? '' : 'none';
      var cnt = g.querySelector('.count');
      if(cnt){ cnt.textContent = n + ' 条'; }
    });
  });
});

var chks = [].slice.call(document.querySelectorAll('.mat-chk'));
function refresh(){
  var n = chks.filter(function(c){ return c.checked; }).length;
  document.getElementById('matcnt').textContent = n + ' / ' + chks.length;
  document.getElementById('prog').style.width = (n/chks.length*100) + '%';
}
chks.forEach(function(c){ c.addEventListener('change', refresh); });
refresh();

document.querySelectorAll('.copy').forEach(function(b){
  b.addEventListener('click', function(){
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(b.dataset.copy).then(function(){ b.textContent='已复制'; })
        .catch(function(){ toast('复制失败，请手动选择文本'); });
    } else { toast('当前环境不支持一键复制'); }
    setTimeout(function(){ b.textContent='复制话术'; }, 1400);
  });
});

if(location.hash && CASES.indexOf(location.hash.slice(1))>=0){ activate(location.hash.slice(1), false); }
"""


def build(doc, outdir=None):
    global DIMENSIONS, CASES, MATERIALS, ONSITE, SOURCES, META, PROFILE
    global REPORT_ID, REPORT_DATE, PRODUCT, PRODUCT_SPEC, SYNTHETIC

    META = doc.get("meta", {})
    PROFILE = doc.get("product_profile", {})
    DIMENSIONS = doc.get("dimensions", [])
    CASES = doc.get("cases", [])
    MATERIALS = doc.get("materials", [])
    ONSITE = doc.get("onsite", [])
    SOURCES = doc.get("sources", [])
    REPORT_ID = META.get("report_id", "SV-001")
    REPORT_DATE = META.get("as_of", "")
    PRODUCT = META.get("product", "")
    PRODUCT_SPEC = META.get("product_spec", "")
    SYNTHETIC = {c["id"] for c in CASES if c.get("synthetic")}

    outdir = outdir or os.path.dirname(os.path.abspath(__file__))
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "%s.html" % META.get("slug", "supplier-verification"))
    first = CASES[0] if CASES else {}

    nav = ""
    for i, c in enumerate(CASES):
        meta = VERDICT_META[c["verdict"]]
        nav += (f'<button class="casebtn{" on" if i==0 else ""}" data-target="{c["id"]}">'
                f'<span class="d"></span>{e(c["short"])}'
                f'<span class="v">{e(c["verdict"])}</span></button>')

    cases_html = "\n".join(case_section(c, i) for i, c in enumerate(CASES))
    regime_txt = "；".join(PROFILE.get("regimes") or
                           ["排污许可证（对应行业类别）", "环评批复与验收（产品+产能）", "项目备案/产能置换公示"])

    tri = f"""
    <div class="tri">
      <div class="tri-card c1"><div class="n">A / DIRECT</div><h5>直接生产证据</h5>
        <p>能独立指向“这套装置存在且在运行”的材料：{e(regime_txt)}；以及上市公司披露的产量、非计划停产公告、厂址与装置卫星/视频。判定只看这一组。</p></div>
      <div class="tri-card c2"><div class="n">B / INDIRECT</div><h5>间接业务证据</h5>
        <p>能说明“确实在做这门生意”，但不能单独证明自产：官网产品页、自营商城、交易所交割厂库、协会名录、原料采购、生产岗位招聘、专利、行业报道。需与 A 组交叉。</p></div>
      <div class="tri-card c3"><div class="n">C / EXCLUDED</div><h5>不构成证据</h5>
        <p>最容易被误采信的材料：营业执照经营范围、“厂家直销”话术、注册资本、可大量供货、单张无定位照片。它们只能证明“允许做/想做/能垫资”，不能证明“在做”。</p></div>
    </div>"""

    tree = ""
    for r in VERDICT_RULES:
        tree += f"""<div class="tree-row"><div class="q">{r['step']}</div>
        <div><b>{e(r['question'])}</b><p>{e(r['detail'])}</p></div>
        <div class="ans">是 → <i>{e(r['yes'])}</i><br>否 → {e(r['no'])}</div></div>"""

    dim_rows = "".join(
        f'<tr><td class="name">{e(d["name"])}</td><td>{d["weight"]}</td><td>{e(d["detail"])}</td></tr>'
        for d in DIMENSIONS)

    mat_rows = ""
    for m in MATERIALS:
        mat_rows += f"""<tr>
      <td class="chk"><input type="checkbox" class="mat-chk" aria-label="已获取"></td>
      <td class="name">{e(m['name'])}<div class="script">{e(m['scene'])}</div></td>
      <td><span class="pri {m['priority']}">{m['priority']}</span></td>
      <td>{e(m['purpose'])}<div class="script">看点：{e(m['look'])}</div></td>
      <td>{e(m['script'])}<div style="margin-top:6px"><button class="copy" data-copy="{e(m['script'])}">复制话术</button></div></td>
    </tr>"""

    os_cards = ""
    for i, o in enumerate(ONSITE):
        os_cards += f"""<div class="os"><div class="n">CHECK {i+1:02d}</div><b>{e(o['item'])}</b>
      <p>{e(o['method'])}</p><p style="color:#3F5568;margin-top:4px">合格：{e(o['pass'])}</p>
      <p class="fake">造假信号：{e(o['fake'])}</p></div>"""

    cmp_rows = ""
    for c in CASES:
        meta = VERDICT_META[c["verdict"]]
        hard = "、".join([i["title"].split("：")[0] for i in c["direct"][:3]]) or "无"
        cmp_rows += f"""<tr><td><b>{e(c['short'])}</b><div class="script">{e(c['company'])}</div></td>
      <td><span class="vchip {meta['color']}">{meta['icon']} {e(c['verdict'])}</span></td>
      <td style="font-family:Consolas,monospace">{c['score']}</td>
      <td>{len(c['direct'])} / {len(c['indirect'])} / {len(c['excluded'])}</td>
      <td>{e(hard)}</td><td>{e(c['confidence'])}</td></tr>"""

    hint_items = "、".join(f'<b>{e(c["short"])}</b>（{e(c["verdict"])}）' for c in CASES)

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(META.get('title', '供应商真伪核验'))} · {e(PRODUCT)}</title>
<style>{CSS}</style>
</head>
<body>

<div class="topbar"><div class="inner">
  <div class="mark">SV</div>
  <div class="brand">供应商真伪核验台<small>SUPPLIER AUTHENTICATION DESK</small></div>
  <div class="tb-spacer"></div>
  <div class="tb-meta">{e(REPORT_ID)} · {e(REPORT_DATE)}</div>
  <button class="tb-btn" onclick="window.print()">打印 / 存 PDF</button>
</div></div>

<div class="wrap">
  <section class="intro">
    <div class="eyebrow">IS IT A REAL FACTORY? · 内贸采购尽调</div>
    <h1>{e(META.get('h1', '查供应商是不是真厂家'))}</h1>
    <p class="lead">{e(META.get('lead', ''))}</p>
    <div class="searchbar">
      <label><span>企业名称</span><input id="q-company" value="{e(first.get('company', ''))}" placeholder="输入企业全名"></label>
      <label><span>产品 / 规格</span><input id="q-product" value="{e(PRODUCT_SPEC or PRODUCT)}" placeholder="产品 + 规格"></label>
      <label><span>辅助材料</span><input id="q-file" value="营业执照 / 许可证 / 工厂照片" placeholder="可上传：执照、许可证、照片"></label>
      <button class="btn-run" id="run">开始核验</button>
    </div>
    <div class="hint">演示模式内置 {len(CASES)} 个案例：{hint_items}。输入其中任一名称即可切换。</div>
  </section>
</div>

<div class="casenav"><div class="inner">{nav}</div></div>

<div class="wrap">
{cases_html}

  <section class="sec" id="method">
    <div class="sec-head"><div><h3><span class="idx">05</span>判定方法：三分法与四类结论</h3>
    <p>先分类，再判定。分类错了，结论一定错——把“经营范围”当生产证据，是内贸采购最常见的翻车点。</p></div></div>
    <div class="method">
      {tri}
      <div class="tree">
        <h4>判定顺序（必须按 Q1→Q4 走，不能跳步）</h4>
        {tree}
        <p style="font-size:11.8px;color:#8494A5;margin:10px 0 0">说明：Q1 的硬证据只需命中一条即可进入 Q2；“分装或复配”优先于“贸易经销”，
        因为分装商也有资质、也有车间，只有看许可明细与设备清单才能区分。四类都不成立时，输出“证据不足暂无法确认”，不做倾向性推断。</p>
      </div>
      <div class="tree" style="margin-top:20px">
        <h4>证据充分度模型（100 分制）</h4>
        <table class="mat" style="border:1px solid #E6ECF2;border-radius:10px;overflow:hidden">
          <thead><tr><th style="width:200px">维度</th><th style="width:70px">权重</th><th>评分要点</th></tr></thead>
          <tbody>{dim_rows}</tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="sec" id="materials">
    <div class="sec-head"><div><h3><span class="idx">06</span>完整尽调清单 · {len(MATERIALS)} 项材料</h3>
    <p>按优先级发问；P0 拿不到，就不要进入打款与长协。话术可直接复制给业务员。</p></div></div>
    <div class="mats">
      <div class="mat-bar">
        <span style="font-size:12px;color:#5B6B7C">已获取</span>
        <div class="prog"><i id="prog"></i></div>
        <span class="cnt" id="matcnt">0 / {len(MATERIALS)}</span>
      </div>
      <table class="mat">
        <thead><tr><th class="chk"></th><th style="width:230px">材料</th><th style="width:60px">优先级</th>
        <th style="width:250px">核验目的</th><th>索取话术</th></tr></thead>
        <tbody>{mat_rows}</tbody>
      </table>
    </div>
  </section>

  <section class="sec" id="onsite">
    <div class="sec-head"><div><h3><span class="idx">07</span>现场 / 视频验厂脚本</h3>
    <p>不预约、不剪辑、按顺序走。真正的工厂不怕看装置，怕看的是门牌和地磅。</p></div></div>
    <div class="onsite">{os_cards}</div>
  </section>

  <section class="sec" id="compare">
    <div class="sec-head"><div><h3><span class="idx">08</span>{len(CASES)} 个案例横向对照</h3>
    <p>同一套方法，不同证据结构，落点自然不同：有的能定“厂家”，有的只能定“贸易”，有的必须留白。</p></div></div>
    <div class="cmp"><table class="cmp-t">
      <thead><tr><th style="width:210px">企业</th><th>结论</th><th>充分度</th><th>直接/间接/排除</th><th>关键硬证据</th><th>置信度</th></tr></thead>
      <tbody>{cmp_rows}</tbody>
    </table></div>
  </section>

  <footer>
    <b>方法与口径</b>：本报告只采信可公开复核的来源；企业官网信息标注为“自述”，须与许可/公告/交易所文件交叉。
    “证据充分度”衡量证据链完整度，不代表企业信用或产品质量；分数与结论均随新证据更新。<br>
    <b>数据截止</b>：{e(REPORT_DATE)}。许可、交割厂库名单、产能置换公示均可能变动，正式签约前应重新核验一次。<br>
    <b>免责</b>：{e(META.get('disclaimer', '本报告为采购尽调辅助材料，不构成法律意见。'))}
  </footer>
</div>

<div id="toast"></div>
"""

    alias, seen_alias = [], set()
    for c in CASES:
        for a in [c.get("short"), c.get("company")] + list(c.get("aliases") or []):
            if a and (a, c["id"]) not in seen_alias:
                seen_alias.add((a, c["id"]))
                alias.append([a, c["id"]])
    script = SCRIPT.replace("__CASES__", json.dumps([c["id"] for c in CASES], ensure_ascii=False))
    script = script.replace("__ALIAS__", json.dumps(alias, ensure_ascii=False))

    html_doc += "\n<script>\n" + script + "\n</script>\n</body>\n</html>"

    with open(out, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print("[ok] html -> %s (%d bytes)" % (out, len(html_doc.encode("utf-8"))))
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="生成 HTML 核验报告")
    ap.add_argument("input", help="input.json")
    ap.add_argument("-o", "--outdir", default=".", help="输出目录")
    a = ap.parse_args()
    build(load_doc(a.input), a.outdir)
