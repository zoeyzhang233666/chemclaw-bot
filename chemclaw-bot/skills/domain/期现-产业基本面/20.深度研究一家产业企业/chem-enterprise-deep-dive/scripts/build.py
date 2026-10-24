#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chem-enterprise-deep-dive :: build.py
把按 references/data-schema.md 填好的 data.json 渲染成两件交付物：
  1) 企业深研_{公司}_{用途}.html  —— 单文件交互式档案（首屏卡片 / 股权图 / 基地地图 /
     产品·工艺关系 / 项目清单 / 事件时间线 / 证据抽屉 / 多维筛选），无外部依赖
  2) 企业深研_{公司}_{用途}.xlsx  —— 15 个 sheet 的结构化台账（缺 openpyxl 时降级为同名 CSV 系列）

用法：
  python build.py data.json [-o 输出目录] [--stem 文件名前缀] [--html-only|--xlsx-only]

本脚本不做任何研究判断：所有内容来自 data.json。不要为渲染效果修改事实。
缺字段的区块自动渲染为「无公开资料」，不要为填满而编造。

口径校验（--strict 时直接失败，默认仅告警）：
  - 每个带 ev 的结论行，ev 必须存在于 evidence[] 台账
  - eid 作为「编号锚点」时必须在 evidence[] 中存在
  - grade 必须是 A/B/C/D
  - 估算行必须写明 basis（口径）
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from datetime import datetime

SKILL_VERSION = "1.0.0"
SKILL_DATE = "2026-10-20"

GRADE_MAP = {
    "A": ("A 已核实", "gA", "官方一手：公告/年报/政府网站/证书原文"),
    "B": ("B 多源", "gB", "两家以上独立公开来源或企业官网自述"),
    "C": ("C 单源", "gC", "单一二手来源，需交叉验证"),
    "D": ("D 估算", "gD", "行业经验值/计算推得，非披露值"),
    "NA": ("NA 无资料", "gNA", "未找到可公开核实的资料"),
}
STATUS_MAP = {
    "ok": ("正常", "tag ok"),
    "warn": ("待复核", "tag warn"),
    "risk": ("关注", "tag risk"),
    "todo": ("待办", "tag todo"),
}
PURPOSE_MAP = {
    "supplier": "供应商调查",
    "customer": "客户调查",
    "competitor": "竞争对手研究",
    "industry": "产业研究",
    "investment": "投资研究",
}


# ---------------------------------------------------------------- utilities

def esc(s):
    return html.escape(str("" if s is None else s))


def as_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


def safe_stem(s):
    s = re.sub(r'[\\/:*?"<>|\r\n]+', "_", str(s)).strip()
    return s or "企业深研"


def g(x):
    """取值：None / 空串 / 空列表 统一返回占位符"""
    if x is None or x == "" or x == []:
        return '<span class="na">无公开资料</span>'
    if isinstance(x, list):
        return "；".join(esc(i) for i in x if i)
    return esc(x)


def collect_evidence(data):
    """证据台账：按 evidence[] 出现顺序编号 E01…，同一 URL 只编一次。"""
    ledger, seen = [], {}
    for node in data.get("evidence") or []:
        if not isinstance(node, dict):
            continue
        key = node.get("eid") or node.get("url") or node.get("title")
        if key in seen:
            continue
        eid = node.get("eid") or ("E%02d" % (len(ledger) + 1))
        seen[key] = eid
        ledger.append({
            "eid": eid,
            "id": eid,
            "title": node.get("title", ""),
            "publisher": node.get("publisher", ""),
            "date": node.get("date", ""),
            "url": node.get("url", ""),
            "type": node.get("type", ""),
            "quote": node.get("quote", ""),
            "note": node.get("note", ""),
            "status": node.get("status", ""),
        })
    return ledger, seen


def validate(data, ledger_eids, strict=False):
    problems = []
    base = {n.get("id"): n for n in as_list(data.get("base_info"))}

    def check_ev(ev, where):
        if not ev:
            return
        for e in as_list(ev):
            if e not in ledger_eids:
                problems.append("%s：证据编号 %s 不在 evidence[] 台账中" % (where, e))

    for sec, items in (("conclusion", as_list(data.get("conclusion"))),
                       ("identity", as_list(data.get("identity"))),
                       ("shareholders", as_list(data.get("shareholders"))),
                       ("products", as_list(data.get("products"))),
                       ("plants", as_list(data.get("plants"))),
                       ("projects", as_list(data.get("projects"))),
                       ("timeline", as_list(data.get("timeline"))),
                       ("finance", as_list(data.get("finance"))),
                       ("risks", as_list(data.get("risks")))):
        for it in items:
            if isinstance(it, dict):
                check_ev(it.get("ev"), "%s/%s" % (sec, it.get("id") or it.get("name") or "?"))
                gr = it.get("grade")
                if gr and gr not in GRADE_MAP:
                    problems.append("%s/%s：grade=%r 非法（应为 A/B/C/D）"
                                    % (sec, it.get("id") or it.get("name"), gr))
    for p in as_list(data.get("products")):
        for cap in as_list(p.get("capacity")):
            if cap.get("estimate") and not cap.get("basis"):
                problems.append("products/%s：估算产能未写 basis（口径）" % p.get("id"))
    for bp in as_list(data.get("base_info")):
        eid = bp.get("id")
        if eid and eid not in ledger_eids:
            problems.append("base_info/%s：eid 不在 evidence[] 台账中" % eid)
    del base
    if problems:
        head = "[口径校验失败]" if strict else "[口径校验告警]"
        for p in problems:
            print("%s %s" % (head, p), file=sys.stderr)
        if strict:
            sys.exit(2)
    return problems


# ---------------------------------------------------------------- CSS

CSS = r"""
:root{
--ink:#111827;--sub:#5b6572;--line:#e4e8ee;--bg:#f3f5f8;--card:#ffffff;
--blue:#1554c0;--blue-bg:#eef3fc;--blue-line:#c9dbf5;
--red:#c0392b;--red-bg:#fdf0ee;--red-line:#f2c9c2;
--green:#1a7f4f;--green-bg:#edf7f1;--green-line:#c4e3d4;
--amber:#8a6100;--amber-bg:#fdf6e7;--amber-line:#ecd9a8;
--violet:#5b46b8;--violet-bg:#f1eefc;
--gray-bg:#eef0f3;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:"Microsoft YaHei","PingFang SC","Hiragino Sans GB",system-ui,sans-serif;
background:var(--bg);color:var(--ink);font-size:14px;line-height:1.68;-webkit-font-smoothing:antialiased}
.wrap{max-width:1280px;margin:0 auto;padding:18px 18px 64px}
a{color:var(--blue);text-decoration:none}
a:hover{text-decoration:underline}
.na{color:#9aa3ad}

/* ---------- hero ---------- */
.hero{position:relative;overflow:hidden;border-radius:16px;color:#fff;padding:26px 28px 22px;
background:radial-gradient(1200px 400px at 10% -30%,#2f6fd8 0%,transparent 60%),
linear-gradient(115deg,#0d1f3f 0%,#123a78 55%,#1554c0 100%);box-shadow:0 10px 30px rgba(13,31,63,.18)}
.hero .kicker{font-size:12px;letter-spacing:.18em;opacity:.78;text-transform:uppercase}
.hero h1{font-size:27px;font-weight:800;margin:6px 0 4px;letter-spacing:.02em}
.hero .sub{font-size:13px;opacity:.86}
.badges{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px}
.badge{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.3);
border-radius:999px;padding:4px 13px;font-size:12.5px;backdrop-filter:blur(4px)}
.badge b{font-weight:700}
.hero .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:18px}
.hero .stat{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.22);
border-radius:12px;padding:10px 14px}
.hero .stat .k{font-size:11.5px;opacity:.82}
.hero .stat .v{font-size:18px;font-weight:800;margin-top:2px;letter-spacing:.01em}
.hero .stat .m{font-size:11.5px;opacity:.72;margin-top:2px}

/* ---------- cards ---------- */
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-top:16px;
box-shadow:0 2px 6px rgba(17,24,39,.04)}
.card>h2{font-size:16.5px;font-weight:800;display:flex;align-items:center;gap:9px;margin-bottom:4px}
.card>h2 .no{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;
border-radius:7px;background:var(--blue);color:#fff;font-size:13px;font-weight:800}
.card>h2 .hint{font-size:12px;font-weight:400;color:var(--sub);margin-left:4px}
.card>p.lead{font-size:13.4px;color:var(--sub);margin:6px 0 10px}
h3.sec{font-size:14px;font-weight:800;color:var(--blue);margin:16px 0 8px}
.note{background:var(--amber-bg);border-left:3px solid #d9a92c;border-radius:0 8px 8px 0;
padding:10px 14px;margin:10px 0;font-size:13px;color:#5c4607}
.note b{color:var(--amber)}
.gapbox{background:var(--gray-bg);border:1px dashed #c7ced8;border-radius:10px;padding:12px 16px;
font-size:13px;color:#4b5563}
.gapbox b{color:#374151}

/* ---------- tags / grades ---------- */
.tag{display:inline-block;font-size:11.5px;border-radius:5px;padding:1px 8px;white-space:nowrap;font-weight:600}
.tag.ok{background:var(--green-bg);color:var(--green)}
.tag.warn{background:var(--amber-bg);color:var(--amber)}
.tag.risk{background:var(--red-bg);color:var(--red)}
.tag.todo{background:var(--gray-bg);color:var(--sub)}
.gA,.gB,.gC,.gD,.gNA{display:inline-block;font-size:11px;font-weight:800;border-radius:5px;
padding:1px 6px;letter-spacing:.02em;cursor:help}
.gA{background:var(--green-bg);color:var(--green);border:1px solid var(--green-line)}
.gB{background:var(--blue-bg);color:var(--blue);border:1px solid var(--blue-line)}
.gC{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-line)}
.gD{background:var(--violet-bg);color:var(--violet);border:1px solid #d7d0f5}
.gNA{background:var(--gray-bg);color:#7b8695;border:1px solid #d5dae1}
.est{font-size:11px;color:var(--violet);font-weight:700;border:1px dashed #c6bdf0;
border-radius:5px;padding:0 5px;margin-left:4px;white-space:nowrap}
.evref{display:inline-flex;gap:4px;flex-wrap:wrap;margin-left:4px}
.evref a{font-size:11px;font-weight:700;background:var(--blue-bg);border:1px solid var(--blue-line);
color:var(--blue);border-radius:5px;padding:0 5px;cursor:pointer}
.evref a:hover{background:var(--blue);color:#fff;text-decoration:none}

/* ---------- tables ---------- */
table.dt{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}
table.dt th,table.dt td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
table.dt th{background:#f7f9fc;font-weight:700;white-space:nowrap;position:sticky;top:0;z-index:1}
table.dt tr:nth-child(even) td{background:#fcfdfe}
table.dt td.num{text-align:right;font-variant-numeric:tabular-nums}
.tbl-wrap{overflow-x:auto}

/* ---------- kv grid ---------- */
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:10px;margin:10px 0}
.kv .cell{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.kv .k{font-size:11.5px;color:var(--sub);letter-spacing:.02em}
.kv .v{font-size:14.5px;font-weight:700;margin-top:3px;word-break:break-word}
.kv .src{font-size:11px;color:#8a939f;margin-top:4px}

/* ---------- KPI ---------- */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:8px 0}
.kpi{background:linear-gradient(180deg,#fff,#f8fafc);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpi .k{font-size:11.5px;color:var(--sub)}
.kpi .v{font-size:19px;font-weight:800;margin-top:2px;font-variant-numeric:tabular-nums}
.kpi .v.neg{color:var(--red)}
.kpi .m{font-size:11.5px;color:#8a939f;margin-top:3px}
.kpi .evref a{font-size:10.5px}

/* ---------- research conclusion cards ---------- */
.concl{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:12px;margin-top:10px}
.cc{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;position:relative;
border-top:3px solid var(--blue)}
.cc.k{ border-top-color:var(--green)} .cc.r{border-top-color:var(--red)} .cc.w{border-top-color:#d9a92c}
.cc .q{font-size:11.7px;color:var(--sub);letter-spacing:.05em;font-weight:700}
.cc .a{font-size:15.5px;font-weight:800;margin:5px 0 7px;line-height:1.5}
.cc .why{font-size:13px;color:#374151}
.cc .why b{color:var(--ink)}
.cc .foot{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}

/* ---------- ownership tree ---------- */
.own-scroll{overflow-x:auto;padding:6px 0 10px}
.own{display:flex;flex-direction:column;align-items:center;min-width:820px;font-size:12.5px}
.own .row{display:flex;justify-content:center;align-items:flex-start;gap:56px;position:relative}
.own .node{position:relative;background:#fff;border:1.5px solid var(--blue-line);border-radius:10px;
padding:8px 12px;min-width:170px;text-align:center;box-shadow:0 2px 5px rgba(17,24,39,.05)}
.own .node.state{border-color:#9fb3cf;background:#f7f9fc}
.own .node.sub{border-color:#9fcaae;background:#f7fcf9}
.own .node.assoc{border-color:#d7d0f5;background:#faf8ff}
.own .node.target{border-color:var(--blue);background:linear-gradient(180deg,#eaf1fd,#fff);
box-shadow:0 0 0 3px rgba(21,84,192,.13)}
.own .node.excl{border-style:dashed;border-color:#d9a92c;background:var(--amber-bg)}
.own .node .n{font-weight:800;font-size:13.5px}
.own .node .r{font-size:11px;color:var(--sub)}
.own .node .p{font-size:11.5px;font-weight:800;color:var(--blue)}
.own .node .evref{justify-content:center}
.own .vline{width:2px;height:22px;background:#b9c7dc;margin:0 auto}
.own .split{width:calc(100% - 170px);height:2px;background:#b9c7dc;margin:0 auto}
.own .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--sub);margin-top:6px}
.own .legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;
vertical-align:-2px;border:1.5px solid}

/* ---------- map ---------- */
.map-grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(280px,.95fr);gap:14px;align-items:start}
@media(max-width:960px){.map-grid{grid-template-columns:1fr}}
.map-svg-wrap{position:relative;border:1px solid var(--line);border-radius:12px;background:
linear-gradient(180deg,#f9fbfe,#eef3fa);padding:6px}
svg.cn{width:100%;height:auto;display:block}
svg.cn .prov{fill:#e7edf6;stroke:#c3cfe0;stroke-width:.8}
svg.cn .hull{fill:rgba(21,84,192,.10);stroke:rgba(21,84,192,.45);stroke-width:1.2;stroke-dasharray:5 4}
svg.cn .marker{cursor:pointer}
svg.cn .marker circle.dot{stroke:#fff;stroke-width:1.6}
svg.cn .marker text.num{font-size:8.5px;font-weight:800;fill:#fff;text-anchor:middle;dominant-baseline:central;pointer-events:none}
svg.cn .marker text.lab{font-size:8px;fill:#334155;text-anchor:middle;pointer-events:none;paint-order:stroke;
stroke:#fff;stroke-width:2.4px;stroke-linejoin:round}
svg.cn .marker.active circle.dot{stroke:#111827;stroke-width:2.4}
.plant-list{display:flex;flex-direction:column;gap:8px;max-height:520px;overflow:auto;padding-right:2px}
.plant{background:#fff;border:1px solid var(--line);border-radius:10px;padding:9px 12px;cursor:pointer}
.plant:hover,.plant.active{border-color:var(--blue);box-shadow:0 0 0 2px rgba(21,84,192,.12)}
.plant .t{font-weight:800;font-size:13px;display:flex;justify-content:space-between;gap:8px;align-items:center}
.plant .m{font-size:12px;color:var(--sub);margin-top:3px}
.plant .k{font-size:11.5px;color:#6b7280}
.plant .badge{display:inline-block;font-size:10.5px;border-radius:999px;padding:1px 7px;
background:var(--gray-bg);color:#4b5563;border:1px solid #dfe3e9}

/* ---------- flow (product chain) ---------- */
.flow{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;align-items:stretch;margin-top:8px}
@media(max-width:1020px){.flow{grid-template-columns:1fr 1fr}}
.flow .lane{background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:10px}
.flow .lane h4{font-size:12.5px;color:var(--blue);margin-bottom:8px;letter-spacing:.04em}
.flow .pchip{background:#fff;border:1px solid var(--line);border-radius:9px;padding:7px 9px;margin-bottom:7px}
.flow .pchip .n{font-weight:800;font-size:12.5px}
.flow .pchip .c{font-size:11.5px;color:var(--sub)}
.flow .pchip .pn{font-size:10.5px;color:#6b7280;margin-top:3px}
.flow .pchip.core{border-color:var(--blue);box-shadow:0 0 0 2px rgba(21,84,192,.1)}
.prod-card{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:12px;background:#fff}
.prod-card h3{font-size:14.5px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.prod-card .meta{font-size:12.5px;color:var(--sub);margin:4px 0 8px}
.cap-line{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0}
.cap{background:var(--blue-bg);border:1px solid var(--blue-line);border-radius:8px;padding:6px 10px;font-size:12px}
.cap b{font-size:13.5px}
.cap .src{display:block;font-size:10.8px;color:#6b7280}

/* ---------- timeline ---------- */
.tl{position:relative;margin:8px 0 6px 10px;padding-left:22px;border-left:2px solid #c9d6ea}
.tl .item{position:relative;margin:0 0 14px}
.tl .item::before{content:"";position:absolute;left:-29px;top:6px;width:11px;height:11px;border-radius:50%;
background:#fff;border:2.5px solid var(--blue)}
.tl .item.p{border-color:var(--red)} .tl .item.p::before{border-color:var(--red)}
.tl .item.f::before{border-color:var(--green)}
.tl .item.s::before{border-color:#d9a92c}
.tl .d{font-size:12px;font-weight:800;color:var(--blue)}
.tl .item.p .d{color:var(--red)} .tl .item.f .d{color:var(--green)}
.tl .t{font-size:13.3px;margin-top:2px}
.tl .meta{margin-top:4px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}

/* ---------- filters ---------- */
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:12px;
background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 14px;position:sticky;top:8px;z-index:20;
box-shadow:0 4px 14px rgba(17,24,39,.06)}
.filters label{font-size:11.8px;color:var(--sub);font-weight:700;margin-right:4px}
.filters select,.filters input[type=search]{font:inherit;font-size:12.5px;padding:5px 8px;border:1px solid #cfd6df;
border-radius:8px;background:#fff;color:var(--ink);max-width:190px}
.filters .cnt{font-size:12px;color:var(--sub);margin-left:auto}
.filters button{font:inherit;font-size:12px;font-weight:700;border:1px solid var(--blue);color:var(--blue);
background:#fff;border-radius:8px;padding:5px 12px;cursor:pointer}
.filters button:hover{background:var(--blue);color:#fff}
.hide{display:none !important}

/* ---------- evidence drawer ---------- */
.evlist{display:flex;flex-direction:column;gap:8px}
.evitem{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.evitem .hd{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.evitem .id{font-weight:800;color:var(--blue);font-size:12px}
.evitem .ti{font-weight:700;font-size:13px}
.evitem .meta{font-size:11.8px;color:var(--sub);margin-top:3px}
.evitem blockquote{margin:7px 0 0;padding:8px 12px;background:#f8fafc;border-left:3px solid var(--blue-line);
border-radius:0 7px 7px 0;font-size:12.5px;color:#374151}
.evitem .u{font-size:11.5px;word-break:break-all;margin-top:5px}
#evPanel{position:fixed;top:0;right:0;height:100vh;width:min(560px,96vw);background:#fff;z-index:90;
box-shadow:-12px 0 40px rgba(17,24,39,.22);transform:translateX(105%);transition:transform .22s ease;
display:flex;flex-direction:column}
#evPanel.open{transform:translateX(0)}
#evPanel .ph{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;
border-bottom:1px solid var(--line);font-weight:800}
#evPanel .pb{overflow:auto;padding:14px 18px}
#evPanel .pc{cursor:pointer;border:none;background:var(--gray-bg);border-radius:8px;font:inherit;
font-weight:800;width:30px;height:30px}
#mask{position:fixed;inset:0;background:rgba(17,24,39,.35);z-index:80;display:none}
#mask.open{display:block}

/* misc */
.footer{margin-top:22px;font-size:12px;color:var(--sub);border-top:1px solid var(--line);padding-top:14px}
.legend-row{display:flex;gap:10px;flex-wrap:wrap;font-size:11.8px;color:var(--sub);margin:6px 0 2px}
.legend-row span{display:inline-flex;align-items:center;gap:5px}
.pill{display:inline-block;font-size:11px;border-radius:999px;padding:1px 9px;background:var(--blue-bg);
color:var(--blue);border:1px solid var(--blue-line);margin-right:4px}
.toc{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px;background:#fff;border:1px solid var(--line);
border-radius:12px;padding:8px 10px;box-shadow:0 2px 6px rgba(17,24,39,.04);position:sticky;top:8px;z-index:30}
.toc a{font-size:12.3px;color:#374151;padding:3px 9px;border-radius:7px;display:inline-flex;gap:5px;align-items:center}
.toc a i{font-style:normal;font-size:10.5px;font-weight:800;color:var(--blue);background:var(--blue-bg);
border-radius:4px;padding:0 5px}
.toc a:hover{background:var(--blue-bg);text-decoration:none;color:var(--blue)}
.basis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:10px}
@media(max-width:900px){.basis{grid-template-columns:1fr}}
.basis .b{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:10px 13px;font-size:12.6px}
.basis .b h5{font-size:12.5px;margin-bottom:5px;color:var(--blue)}
.basis .b ul{padding-left:16px}
@media print{.filters,#evPanel,#mask{display:none}body{background:#fff}.card{break-inside:avoid}}
"""


# ---------------------------------------------------------------- HTML blocks

def ev_ref(ids, ledger_map):
    ids = [i for i in as_list(ids) if i]
    if not ids:
        return ""
    parts = []
    for i in ids:
        e = ledger_map.get(i)
        title = (e["title"][:70] + "…") if e and len(e["title"]) > 70 else (e["title"] if e else i)
        cls = " onclick=\"openEv('%s')\"" % esc(i) if e else ""
        parts.append('<a%s title="%s">%s</a>' % (cls, esc(title), esc(i)))
    return '<span class="evref">%s</span>' % "".join(parts)


def grade_chip(gr):
    if not gr:
        return ""
    label, cls, tip = GRADE_MAP.get(gr, GRADE_MAP["NA"])
    return '<span class="%s" title="%s">%s</span>' % (cls, esc(tip), esc(label))


def status_chip(st):
    label, cls = STATUS_MAP.get(st or "todo", STATUS_MAP["todo"])
    return '<span class="%s">%s</span>' % (cls, label)


def kpi_block(items):
    if not items:
        return '<div class="gapbox">本区块<b>无公开资料</b>。</div>'
    out = ['<div class="kpis">']
    for it in items:
        neg = " neg" if it.get("neg") else ""
        out.append('<div class="kpi"><div class="k">%s</div><div class="v%s">%s</div>'
                   '<div class="m">%s %s</div></div>'
                   % (esc(it.get("k", "")), neg, g(it.get("v")), g(it.get("m")),
                      it.get("ev") and '<span class="evref">%s</span>' % "".join(
                          "<a onclick=\"openEv('%s')\">%s</a>" % (esc(e), esc(e)) for e in as_list(it["ev"]))))
    out.append("</div>")
    return "".join(out)


def table(headers, rows, cls=""):
    th = "".join("<th>%s</th>" % esc(h) for h in headers)
    trs = "".join("<tr>%s</tr>" % "".join("<td%s>%s</td>" % (c[1] if isinstance(c, tuple) else "", c[0] if isinstance(c, tuple) else c)
                                          for c in r) for r in rows)
    return '<div class="tbl-wrap"><table class="dt %s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (cls, th, trs)


def section_evidence(ids, ledger, title="本章证据"):
    ids = [i for i in as_list(ids) if i]
    if not ids:
        return ""
    items = []
    for i in ids:
        e = next((x for x in ledger if x["eid"] == i), None)
        if not e:
            continue
        items.append('<div class="evitem"><div class="hd"><span class="id">%s</span>'
                     '<span class="ti">%s</span></div><div class="meta">%s ｜ %s ｜ %s</div>%s%s</div>'
                     % (esc(e["eid"]), esc(e["title"]), esc(e["publisher"]), esc(e["date"]), esc(e["type"]),
                        ('<blockquote>%s</blockquote>' % esc(e["quote"])) if e["quote"] else "",
                        ('<div class="u"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
                         % (esc(e["url"]), esc(e["url"]))) if e["url"] else ""))
    return ('<h3 class="sec">%s（%d）</h3><div class="evlist">%s</div>'
            % (esc(title), len(items), "".join(items)))


def filter_bar(prefix, filter_defs):
    """filter_defs: [(key, label, options)]；options 由数据推导"""
    cells = []
    for key, label, opts in filter_defs:
        o = "".join('<option value="%s">%s</option>' % (esc(v), esc(t)) for v, t in opts)
        cells.append('<span><label for="%s_%s">%s</label><select id="%s_%s" data-f="%s" data-k="%s">'
                     '<option value="">全部</option>%s</select></span>'
                     % (prefix, key, esc(label), prefix, key, prefix, key, o))
    cells.append('<span><label for="%s_q">关键词</label><input id="%s_q" data-f="%s" data-k="kw" '
                 'type="search" placeholder="产品/地区/主体/事件"></span>' % (prefix, prefix, prefix))
    cells.append('<button onclick="resetF(\'%s\')">重置</button>' % prefix)
    cells.append('<span class="cnt" id="%s_cnt"></span>' % prefix)
    return '<div class="filters" id="%s_bar">%s</div>' % (prefix, "".join(cells))


def filter_attrs(prefix, rec):
    return ' data-f="%s" data-prod="%s" data-region="%s" data-entity="%s" data-grade="%s" data-kw="%s"' % (
        prefix,
        "|".join(rec.get("prod", []) or [""]),
        "|".join(rec.get("region", []) or [""]),
        "|".join(rec.get("entity", []) or [""]),
        rec.get("grade", "") or "",
        esc(" ".join(str(x) for x in (rec.get("kw") or []))))


# ---------------------------------------------------------------- ownership tree

def render_ownership(own, ledger_map):
    nodes = {n.get("id"): n for n in as_list(own.get("nodes"))}
    if not nodes:
        return '<div class="gapbox">股权结构<b>无公开资料</b>。</div>'
    children = {}
    for n in own["nodes"]:
        children.setdefault(n.get("parent") or "", []).append(n)

    def node_html(n):
        kind = n.get("kind", "other")
        cls = {"target": "target", "state": "state", "sub": "sub",
               "assoc": "assoc", "excluded": "excl"}.get(kind, "")
        return ('<div class="node %s" data-node="%s"><div class="n">%s</div><div class="r">%s</div>'
                '%s%s</div>'
                % (cls, esc(n.get("id", "")), esc(n.get("name", "")),
                   esc(n.get("role", "")),
                   ('<div class="p">%s</div>' % esc(n["pct"])) if n.get("pct") else "",
                   n.get("ev") and ev_ref(n.get("ev"), ledger_map)))

    def build(pid):
        kids = children.get(pid) or []
        if not kids:
            return ""
        row = '<div class="row">%s</div>' % "".join(
            '<div style="display:flex;flex-direction:column;align-items:center">%s%s</div>'
            % (node_html(k), build(k.get("id"))) for k in kids)
        return '<div class="vline"></div>%s' % row

    roots = children.get("") or []
    top = "".join('<div class="node %s" data-node="%s"><div class="n">%s</div><div class="r">%s</div>%s</div>'
                  '<div class="vline"></div>%s'
                  % ({"target": "target", "state": "state", "sub": "sub", "assoc": "assoc",
                      "excluded": "excl"}.get(r.get("kind", ""), "state"),
                     esc(r.get("id", "")), esc(r.get("name", "")), esc(r.get("role", "")),
                     (('<div class="p">%s</div>' % esc(r["pct"])) if r.get("pct") else "")
                     + (r.get("ev") and ev_ref(r.get("ev"), ledger_map) or ""),
                     build(r.get("id")))
                  for r in roots)
    legend = ('<div class="legend">'
              '<span><i style="border-color:var(--blue);background:#eaf1fd"></i>研究主体</span>'
              '<span><i style="border-color:#9fb3cf;background:#f7f9fc"></i>国资/上级股东</span>'
              '<span><i style="border-color:#9fcaae;background:#f7fcf9"></i>控股子公司/分公司</span>'
              '<span><i style="border-color:#d7d0f5;background:#faf8ff"></i>参股/合营/联营（不并表）</span>'
              '<span><i style="border-color:#d9a92c;background:#fdf6e7"></i>同集团但不在研究范围内（易混淆）</span>'
              '</div>')
    notes = "".join("<li>%s</li>" % esc(x) for x in as_list(own.get("notes")))
    excl = [n for n in own["nodes"] if n.get("kind") == "excluded"]
    excl_tbl = ""
    if excl:
        excl_tbl = ('<h3 class="sec">同集团易混淆主体（其产能/资产不得计入研究主体）</h3>' +
                    table(["身体", "关系", "为什么容易混"],
                          [[esc(n.get("name", "")), esc(n.get("role", "")),
                            esc(n.get("note", "") or "—")] for n in excl]))
    return ('<p class="lead">%s</p><div class="own-scroll"><div class="own">%s%s</div></div>%s%s'
            % (esc(own.get("headline", "")), top, legend,
               ("<ul style='font-size:13px;padding-left:20px;margin-top:6px'>%s</ul>" % notes) if notes else "",
               excl_tbl))


# ---------------------------------------------------------------- map

CITY_COORD = {
    "潍坊": (119.10, 36.71), "滨海": (119.15, 37.20), "寿光": (118.79, 36.86),
    "东营": (118.67, 37.43), "淄博": (118.05, 36.81), "济南": (117.00, 36.65),
    "泰安": (117.09, 36.19), "青岛": (120.38, 36.07), "烟台": (121.39, 37.54),
    "滨州": (117.97, 37.38), "临沂": (118.35, 35.05), "德州": (116.36, 37.44),
    "鄂尔多斯": (109.78, 39.61), "奈曼": (120.66, 42.85), "阿拉善": (105.73, 38.85),
    "连云港": (119.16, 34.60), "唐山": (118.18, 39.63), "乌海": (106.83, 39.67),
    "呼和浩特": (111.75, 40.84), "武汉": (114.31, 30.59), "银川": (106.23, 38.49),
    "北京": (116.41, 39.90), "上海": (121.47, 31.23), "杭州": (120.15, 30.27),
    "阜阳": (115.81, 32.89), "常州": (119.97, 31.81), "佛山": (113.12, 23.02),
}
CN_OUTLINE = ("M 28,44 L 33,33 L 47,27 L 55,33 L 71,31 L 80,19 L 92,25 L 101,16 L 111,22 "
              "L 120,15 L 129,19 L 141,26 L 150,33 L 158,31 L 166,37 L 172,46 L 165,54 "
              "L 158,57 L 152,66 L 145,74 L 139,82 L 131,88 L 126,96 L 118,101 L 114,110 "
              "L 108,117 L 100,120 L 94,114 L 87,110 L 78,104 L 70,96 L 63,92 L 59,84 "
              "L 53,78 L 45,72 L 39,63 L 31,58 L 28,44 Z")
PROV_SEP = [  # 仅用于示意，不代表精确省界
    "M 80,19 L 78,40 L 74,58 L 66,74",
    "M 101,16 L 104,36 L 99,56 L 94,74 L 87,92",
    "M 126,20 L 121,40 L 117,60 L 112,80 L 104,98",
    "M 145,33 L 135,44 L 128,60 L 122,78",
    "M 47,40 L 70,44 L 96,40 L 118,42 L 145,40",
    "M 45,60 L 74,58 L 100,60 L 124,58 L 152,58",
    "M 55,80 L 78,78 L 100,80 L 120,78",
]


def _project(lon, lat):
    x = 28 + (lon - 106.0) * 5.35
    y = 120 - (lat - 28.2) * 4.75
    return round(min(max(x, 20), 178), 2), round(min(max(y, 10), 124), 2)


def render_map(plants, ledger_map):
    pts = []
    for p in plants:
        lat, lon = p.get("lat"), p.get("lon")
        if lat is None or lon is None:
            c = None
            for k, v in CITY_COORD.items():
                if k in (p.get("city") or "") or k in (p.get("location") or ""):
                    c = v
                    break
            if c:
                lon, lat = c
        if lat is None or lon is None:
            continue
        x, y = _project(float(lon), float(lat))
        pts.append((p, x, y))
    if not pts:
        return ('<div class="gapbox">生产基地坐标<b>无公开资料</b>，无法定位；请在 data.json 中补充 '
                'lat/lon 或城市名。</div>')
    xs = [x for _, x, _ in pts]
    ys = [y for _, _, y in pts]
    pad = 6
    hull = ('M %s,%s L %s,%s L %s,%s L %s,%s Z'
            % (min(xs) - pad, min(ys) - pad, max(xs) + pad, min(ys) - pad,
               max(xs) + pad, max(ys) + pad, min(xs) - pad, max(ys) + pad))
    svg = ['<svg class="cn" viewBox="20 10 160 116" role="img" aria-label="全国生产基地示意分布">']
    svg.append('<path class="prov" d="%s"/>' % CN_OUTLINE)
    for d in PROV_SEP:
        svg.append('<path d="%s" fill="none" stroke="#c3cfe0" stroke-width=".5"/>' % d)
    svg.append('<path class="hull" d="%s"/>' % hull)
    for i, (p, x, y) in enumerate(pts, 1):
        color = p.get("color") or "#1554c0"
        svg.append('<g class="marker" id="mk%d" data-plant="%s" onclick="pickPlant(\'%s\')">'
                   '<circle class="dot" cx="%s" cy="%s" r="4.2" fill="%s"/>'
                   '<text class="num" x="%s" y="%s">%d</text>'
                   '<text class="lab" x="%s" y="%s">%s</text></g>'
                   % (i, esc(p.get("id", "")), esc(p.get("id", "")), x, y, esc(color),
                      x, y, i, x, y - 6.5, esc(p.get("short") or p.get("city") or "")))
    svg.append('</svg>')
    cards = []
    for i, (p, x, y) in enumerate(pts, 1):
        caps = "、".join("%s %s" % (c.get("product", ""), c.get("value", ""))
                        for c in as_list(p.get("capacity"))[:3])
        cards.append('<div class="plant" id="pl_%s" data-plant="%s" onclick="pickPlant(\'%s\')">'
                     '<div class="t"><span>%d. %s</span><span class="badge">%s</span></div>'
                     '<div class="m">%s</div><div class="k">%s</div>%s</div>'
                     % (esc(p.get("id", "")), esc(p.get("id", "")), esc(p.get("id", "")), i,
                        esc(p.get("name", "")), esc(p.get("status", "")),
                        esc(p.get("location", "")), esc(caps) if caps else "产能口径：无公开资料",
                        ev_ref(p.get("ev"), ledger_map)))
    return ('<div class="map-grid"><div class="map-svg-wrap">%s'
            '<div class="legend-row"><span><i style="display:inline-block;width:10px;height:10px;'
            'border-radius:50%%;background:#1554c0"></i>在产主体/装置</span>'
            '<span><i style="display:inline-block;width:10px;height:10px;border-radius:50%%;'
            'background:#c0392b"></i>在建/改造</span>'
            '<span><i style="display:inline-block;width:10px;height:10px;border-radius:50%%;'
            'background:#5b46b8"></i>参股/联营（不并表）</span></div>'
            '<div class="note" style="margin-bottom:0"><b>底图为示意，非精确地理边界</b>；'
            '标记点按公开地址/城市中心附近定位，用于表达区域布局关系，不能作为选址依据。</div></div>'
            '<div class="plant-list">%s</div></div>' % ("".join(svg), "".join(cards)))


# ---------------------------------------------------------------- main render

def render_html(data, ledger, ledger_map, problems):
    meta = data.get("meta") or {}
    purpose = PURPOSE_MAP.get(meta.get("purpose", ""), meta.get("purpose_label") or "产业研究")
    company = meta.get("company", "未命名企业")
    stats = as_list(meta.get("hero_stats"))
    badges = ['研究目的：<b>%s</b>' % esc(purpose),
              '统一社会信用代码：<b>%s</b>' % esc(meta.get("uscc") or "无公开资料"),
              '证据台账：<b>%d</b> 条' % len(ledger),
              '检索窗口：%s' % esc(meta.get("as_of", ""))]
    if meta.get("listing"):
        badges.append(esc(meta["listing"]))

    parts = []
    parts.append('<div class="hero"><div class="kicker">企业深研档案 · Enterprise Dossier</div>'
                 '<h1>%s</h1><div class="sub">%s</div>'
                 '<div class="badges">%s</div>'
                 '<div class="stats">%s</div></div>'
                 % (esc(company), esc(meta.get("subtitle", "")),
                    "".join('<span class="badge">%s</span>' % b for b in badges),
                    "".join('<div class="stat"><div class="k">%s</div><div class="v">%s</div>'
                            '<div class="m">%s</div></div>'
                            % (esc(s.get("k", "")), esc(s.get("v", "")), esc(s.get("m", "")))
                            for s in stats)))

    # ---- 目录导航
    nav_items = [(1, "主体信息"), (2, "研究结论"), (3, "关键指标"), (4, "股权与关联"),
                 (5, "产品·产能·工艺"), (6, "生产基地"), (7, "项目清单"), (8, "财务与分业务"),
                 (9, "风险与合规"), (10, "近12个月动态"), (11, "证据台账"), (12, "全量筛选")]
    parts.append('<nav class="toc">%s</nav>' % "".join(
        '<a href="#sec%d"><i>%d</i>%s</a>' % (n, n, esc(t)) for n, t in nav_items))

    # ---- 依据与边界（三栏）
    graded = []
    for key in ("base_info", "products", "projects", "risks", "timeline", "disambiguation", "entities", "plants"):
        for node in as_list(data.get(key)):
            if isinstance(node, dict) and node.get("grade"):
                graded.append(node["grade"])
    a_cnt = graded.count("A")
    b_cnt = graded.count("B")
    basis_inner = (
        '仅研究<b>一个法人主体</b>；集团、兄弟公司、合营企业的产能与资产不并入；'
        '「分公司」无独立法人资格，产能在母公司名下；持股50%以上但章程约定共同控制者按合营企业处理。')
    parts.append(
        '<div class="basis">'
        '<div class="b"><h5>① 依据从哪来</h5>共 <b>%d</b> 条证据，其中条目级 A 级一手来源 %d 条、B 级 %d 条；'
        '优先交易所公告/年报、环评与许可公示、企业官网，其次行业与财经媒体。'
        '正文里的 <b>E编号</b> 可直接点击查看原文摘录与原链接。</div>'
        '<div class="b"><h5>② 边界在哪里</h5>%s'
        '<div style="margin-top:5px">不预测经营业绩、不推测非上市主体营收与利润；'
        '经营范围所列品种未经装置/许可证据支持的不计入产品清单。</div></div>'
        '<div class="b"><h5>③ 缺口怎么办</h5>未取得公开资料的条目在各章节统一标灰为「无公开资料」，'
        '并汇总在「9 风险与合规」的待核验清单，附建议核实途径；估算值一律标注「估算」并写明口径。</div>'
        '</div>' % (len(ledger), a_cnt, b_cnt, basis_inner))

    # ---- 1 主体信息
    bi_rows = []
    for b in as_list(data.get("base_info")):
        if b.get("group"):
            bi_rows.append(("__group__", b.get("group")))
            continue
        val = b.get("value")
        cell = ('<span class="na">无公开资料</span>' if not val else esc(val))
        note = ('<div class="src" style="font-size:11.5px;color:#8a939f">%s</div>' % esc(b["note"])) if b.get("note") else ""
        bi_rows.append("__row__")
        bi_rows.append([esc(b.get("label", "")), cell + note + ev_ref(b.get("ev"), ledger_map)])
    bi_html = []
    pending = []
    for r in bi_rows:
        if isinstance(r, tuple):
            if pending:
                bi_html.append(table(["项目", "内容"], pending))
                pending = []
            bi_html.append('<h3 class="sec">%s</h3>' % esc(r[1]))
        elif r != "__row__":
            pending.append(r)
    if pending:
        bi_html.append(table(["项目", "内容"], pending))

    parts.append('<div class="card" id="sec1"><h2><span class="no">1</span>主体信息与消歧'
                 '<span class="hint">先锁定法人主体，再看业务</span></h2>'
                 '<p class="lead">%s</p>%s</div>'
                 % (esc(data.get("entity_note", "")), "".join(bi_html)))

    # ---- 消歧表
    dis = as_list(data.get("disambiguation"))
    if dis:
        rows = [[esc(d.get("name", "")), esc(d.get("uscc", "") or "—"),
                 esc(d.get("relation", "")), esc(d.get("verdict", "")),
                 ('<span class="tag %s">%s</span>' % ("ok" if d.get("in_scope") else "warn",
                                                      "纳入研究" if d.get("in_scope") else "排除")),
                 grade_chip(d.get("grade")) + ev_ref(d.get("ev"), ledger_map)] for d in dis]
        parts.append('<h3 class="sec">同名/近名主体消歧表（%d 个）</h3>%s'
                     % (len(dis), table(["主体名称", "统一社会信用代码", "与本主体的关系", "判定依据",
                                         "是否纳入范围", "证据"], rows)))

    # ---- 2 研究结论
    cc = as_list(data.get("conclusion"))
    if cc:
        cards = []
        for c in cc:
            cards.append('<div class="cc %s"><div class="q">%s</div><div class="a">%s</div>'
                         '<div class="why">%s</div><div class="foot">%s%s</div></div>'
                         % (esc(c.get("tone", "")), esc(c.get("q", "")), esc(c.get("a", "")),
                            c.get("why", ""), grade_chip(c.get("grade")),
                            ev_ref(c.get("ev"), ledger_map)))
        parts.append('<div class="card" id="sec2"><h2><span class="no">2</span>研究结论<span class="hint">%s 视角</span></h2>'
                     '%s%s</div>'
                     % (esc(purpose), '<div class="concl">%s</div>' % "".join(cards),
                        ('<div class="note"><b>结论边界：</b>%s</div>' % esc(data["conclusion_note"]))
                        if data.get("conclusion_note") else ""))

    # ---- 3 基础KPI
    parts.append('<div class="card" id="sec3"><h2><span class="no">3</span>关键经营与产能指标'
                 '<span class="hint">披露值标注数据源，推得值标注「估算」</span></h2>%s'
                 '<div class="legend-row">%s</div></div>'
                 % (kpi_block(data.get("kpis")),
                    "".join('<span>%s：%s</span>' % (esc(v[0]), esc(v[2])) for v in GRADE_MAP.values())))

    # ---- 4 股权结构
    parts.append('<div class="card" id="sec4"><h2><span class="no">4</span>股权与关联关系'
                 '<span class="hint">区分「并表」「参股」「同集团」</span></h2>%s%s</div>'
                 % (render_ownership(data.get("ownership") or {}, ledger_map),
                    section_evidence((data.get("ownership") or {}).get("ev"), ledger, "股权关系证据")))

    # ---- 5 产品与工艺
    products = as_list(data.get("products"))
    flow = data.get("chain_flow") or []
    flow_html = ""
    if flow:
        lanes = []
        for lane in flow:
            chips = []
            for it in as_list(lane.get("items")):
                chips.append('<div class="pchip %s"><div class="n">%s</div><div class="c">%s</div>'
                             '<div class="pn">%s</div></div>'
                             % ("core" if it.get("core") else "", esc(it.get("n", "")),
                                esc(it.get("c", "")), esc(it.get("pn", ""))))
            lanes.append('<div class="lane"><h4>%s</h4>%s</div>' % (esc(lane.get("lane", "")), "".join(chips)))
        flow_html = '<h3 class="sec">产业链位置（上游原料 → 自身装置 → 下游产品 → 下游流向）</h3>' \
                    '<div class="flow">%s</div>' % "".join(lanes)
    prod_cards = []
    for p in products:
        caps = []
        for c in as_list(p.get("capacity")):
            caps.append('<div class="cap"><b>%s</b>%s<span class="src">%s</span></div>'
                        % (esc(c.get("value", "")), ('<span class="est">估算</span>' if c.get("estimate") else ""),
                           esc("%s：%s" % (c.get("basis", ""), "、".join(as_list(c.get("ev")))))))
        facts = "".join("<li>%s</li>" % f for f in as_list(p.get("facts")))
        prod_cards.append(
            '<div class="prod-card" %s><h3>%s %s<div style="margin-left:auto">%s%s</div></h3>'
            '<div class="meta">%s</div>'
            '<div><b>在产/生产主体：</b>%s</div>'
            '<div class="cap-line">%s</div>'
            '<div><b>主要下游流向：</b>%s</div>'
            '%s</div>'
            % (filter_attrs("prd", p), esc(p.get("name", "")), ("<span class='pill'>%s</span>" % esc(p["tag"])) if p.get("tag") else "",
               grade_chip(p.get("grade")), ev_ref(p.get("ev"), ledger_map),
               esc(p.get("note", "") or ""),
               g(p.get("producers")),
               "".join(caps) if caps else '<span class="na">无公开资料</span>',
               g(p.get("downstream")),
               ("<ul style='font-size:12.8px;padding-left:20px;color:#374151;margin-top:6px'>%s</ul>" % facts) if facts else ""))
    parts.append('<div class="card" id="sec5"><h2><span class="no">5</span>产品、产能与生产工艺'
                 '<span class="hint">经营范围 ≠ 实际产品</span></h2>'
                 '<p class="lead">%s</p>%s%s%s</div>'
                 % (esc(data.get("products_note", "")), flow_html,
                    ('<div class="note"><b>口径提示：</b>下列产品清单只收录有公开证据支持「实际生产/销售」的品种；'
                     '仅出现在经营范围但与主业无关的品种，统一列入文末「无公开资料与待核验清单」。</div>'),
                    "".join(prod_cards) or '<div class="gapbox">产品<b>无公开资料</b>。</div>'))

    # ---- 6 生产基地
    plants = as_list(data.get("plants"))
    plant_tbl = table(["基地/装置", "所在地区", "主体归属", "并表", "状态", "主要产品与产能", "证据"],
                      [[esc(p.get("name", "")), esc(p.get("location", "")), esc(p.get("entity_name", "")),
                        '<span class="tag %s">%s</span>' % ("ok" if p.get("consolidated") else "warn",
                                                           "并表" if p.get("consolidated") else "不并表"),
                        esc(p.get("status", "")), esc(p.get("capacity_text", "") or "无公开资料"),
                        grade_chip(p.get("grade")) + ev_ref(p.get("ev"), ledger_map)]
                       for p in plants]) if plants else '<div class="gapbox">生产基地<b>无公开资料</b>。</div>'
    parts.append('<div class="card" id="sec6"><h2><span class="no">6</span>生产基地与区域布局'
                 '<span class="hint">点击地图标记或右侧卡片联动</span></h2>%s'
                 '<h3 class="sec">基地清单</h3>%s%s</div>'
                 % (render_map(plants, ledger_map), plant_tbl,
                    section_evidence(data.get("plants_ev"), ledger, "基地与装置证据")))

    # ---- 7 项目
    projects = as_list(data.get("projects"))
    if projects:
        rows = [[esc(p.get("name", "")), esc(p.get("type", "")), esc(p.get("location", "")),
                 esc(p.get("scale", "")), esc(p.get("capex", "") or "—"), esc(p.get("status", "")),
                 esc(p.get("timeline", "")), grade_chip(p.get("grade")) + ev_ref(p.get("ev"), ledger_map)]
                for p in projects]
        proj_html = table(["项目名称", "类型", "地点", "建设内容/规模", "投资额", "进展", "时间节点", "证据"], rows)
    else:
        proj_html = '<div class="gapbox">在建/拟建项目<b>无公开资料</b>。</div>'
    parts.append('<div class="card" id="sec7"><h2><span class="no">7</span>项目清单（在建·拟建·已投产）</h2>%s%s</div>'
                 % (proj_html, section_evidence(data.get("projects_ev"), ledger, "项目证据")))

    # ---- 8 财务
    fin = as_list(data.get("finance"))
    if fin:
        ys = data.get("finance_years") or []
        rows = []
        for f in fin:
            rows.append([esc(f.get("item", "")), grade_chip(f.get("grade"))] +
                        [(esc(v), ' class="num"') for v in as_list(f.get("values"))] +
                        [ev_ref(f.get("ev"), ledger_map)])
        parts.append('<div class="card" id="sec8"><h2><span class="no">8</span>财务与分业务资料'
                     '<span class="hint">仅上市/发债主体适用，单位：亿元或 %%</span></h2>'
                     '<p class="lead">%s</p>%s%s%s</div>'
                     % (esc(data.get("finance_note", "")),
                        table(["指标"] + [esc(y) for y in ys] + ["证据"], rows),
                        section_evidence(data.get("finance_ev"), ledger, "财务证据"),
                        ('<div class="note">%s</div>' % esc(data["finance_caveat"])) if data.get("finance_caveat") else ""))
    else:
        parts.append('<div class="card" id="sec8"><h2><span class="no">8</span>财务与分业务资料</h2>'
                     '<div class="gapbox">该主体为非上市公司或公开财务数据不足，<b>不推测其营收与盈利</b>；'
                     '如需判断规模，仅可使用公开产能、员工数与招投标金额等可核验指标。</div></div>')

    # ---- 9 风险
    risks = as_list(data.get("risks"))
    if risks:
        rows = []
        for r in risks:
            rows.append([esc(r.get("category", "")), esc(r.get("finding", "")),
                         status_chip(r.get("status")), grade_chip(r.get("grade")) + ev_ref(r.get("ev"), ledger_map)])
        risk_html = table(["类别", "公开事实", "状态", "证据"], rows)
    else:
        risk_html = '<div class="gapbox">风险事项<b>无公开资料</b>（不等于无风险，需依法核实）。</div>'
    gaps = as_list(data.get("gaps"))
    gaps_html = ""
    if gaps:
        gaps_html = ('<h3 class="sec">无公开资料 / 待核验清单</h3>' +
                     table(["事项", "当前状态", "建议核实途径"],
                           [[esc(x.get("item", "")), '<span class="tag warn">%s</span>' % esc(x.get("status", "无公开资料")),
                             esc(x.get("how", ""))] for x in gaps]))
    parts.append('<div class="card" id="sec9"><h2><span class="no">9</span>公开风险与合规记录'
                 '<span class="hint">只写可核实的公开事实，不评级</span></h2>%s%s%s</div>'
                 % (risk_html, section_evidence(data.get("risks_ev"), ledger, "风险证据"), gaps_html))

    # ---- 10 时间线
    tl = as_list(data.get("timeline"))
    if tl:
        items = []
        for t in tl:
            items.append('<div class="item %s" %s><div class="d">%s</div><div class="t">%s</div>'
                         '<div class="meta">%s%s</div></div>'
                         % (esc(t.get("kind", "")), filter_attrs("tl", t), esc(t.get("date", "")),
                            esc(t.get("text", "")), grade_chip(t.get("grade")),
                            ev_ref(t.get("ev"), ledger_map)))
        tl_html = '<div class="tl">%s</div>' % "".join(items)
    else:
        tl_html = '<div class="gapbox">近 12 个月重要动态<b>无公开资料</b>。</div>'
    parts.append('<div class="card" id="sec10"><h2><span class="no">10</span>近 12 个月重要公开动态'
                 '<span class="hint">新增项目 / 经营变化 / 产品布局 / 重大公告</span></h2>%s%s</div>'
                 % (tl_html, section_evidence(data.get("timeline_ev"), ledger, "动态证据")))

    # ---- 11 证据台账
    ev_html_list = []
    for e in ledger:
        ev_html_list.append('<div class="evitem" id="ev_%s"><div class="hd"><span class="id">%s</span>'
                            '<span class="ti">%s</span></div>'
                            '<div class="meta">%s ｜ %s ｜ %s%s</div>%s%s</div>'
                            % (esc(e["eid"]), esc(e["eid"]), esc(e["title"]),
                               esc(e["publisher"]), esc(e["date"]), esc(e["type"]),
                               (" ｜ " + esc(e["note"])) if e["note"] else "",
                               ('<blockquote>%s</blockquote>' % esc(e["quote"])) if e["quote"] else "",
                               ('<div class="u"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
                                % (esc(e["url"]), esc(e["url"]))) if e["url"] else '<div class="u na">无公开链接</div>'))
    parts.append('<div class="card" id="sec11"><h2><span class="no">11</span>证据台账（%d 条）'
                 '<span class="hint">A官方一手 / B多源 / C单源 / D估算</span></h2>'
                 '<p class="lead">每条证据可点击右侧悬浮面板查看；也可直接点击正文中的 <b>E编号</b> 打开。</p>'
                 '<div class="evlist">%s</div></div>' % (len(ledger), "".join(ev_html_list)))

    # 筛选栏：选项一律由数据反推，缺值给「未标注」，避免空下拉
    def _opts(values, empty_label="未标注"):
        seen = []
        for v in values:
            v = (v or "").strip()
            if v and v not in seen:
                seen.append(v)
        return [(v, v) for v in seen] + ([(("", ""))] if False else [])

    all_rows = []
    prod_pool, region_pool, entity_pool, grade_pool = [], [], [], []
    for it in as_list(data.get("filter_index")):
        prod_pool += as_list(it.get("prod"))
        region_pool.append(it.get("region"))
        entity_pool.append(it.get("entity"))
        grade_pool.append(it.get("grade"))
    for p in products:
        prod_pool.append(p.get("name"))
    for it in as_list(data.get("filter_index")):
        all_rows.append(
            '<tr %s><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (filter_attrs("idx", it), esc(it.get("type", "")), esc(it.get("subject", "")),
               esc(it.get("statement", "")), esc(it.get("entity", "")), esc(it.get("region", "")),
               grade_chip(it.get("grade")),
               ('<a onclick="openEv(\'%s\')">%s</a>' % (esc(it["ev"]), esc(it["ev"]))) if it.get("ev") else '<span class="na">—</span>'))
    if all_rows:
        fdefs = [("prod", "产品", _opts(prod_pool)),
                 ("region", "地区", _opts(region_pool)),
                 ("entity", "主体", _opts(entity_pool)),
                 ("grade", "证据等级", [(k, GRADE_MAP[k][0]) for k in ("A", "B", "C", "D") if k in (grade_pool or [])] or
                  [(k, GRADE_MAP[k][0]) for k in ("A", "B", "C", "D")])]
        parts.append('<div class="card" id="sec12"><h2><span class="no">12</span>全量结论筛选器'
                     '<span class="hint">按产品 / 地区 / 主体 / 证据等级过滤</span></h2>%s'
                     '<div class="tbl-wrap"><table class="dt" id="idx_tbl"><thead><tr>'
                     '<th>类型</th><th>对象</th><th>结论</th><th>主体</th><th>地区</th><th>等级</th><th>证据</th>'
                     '</tr></thead><tbody>%s</tbody></table></div></div>'
                     % (filter_bar("idx", fdefs), "".join(all_rows)))

    disclaimer = ("<b>资料边界：</b>本档案全部结论来自公开信息（交易所公告、年报、政府公示、企业官网与媒体），"
                  "检索窗口 %s；每项结论标注证据编号、来源日期与可靠程度（A/B/C/D）。"
                  "凡推断与估算均已显式标注，未标注者视为披露值。"
                  "<b>本档案不做经营业绩预测，不构成投资、采购或授信建议</b>；"
                  "经营范围中的产品清单不等同于实际生产产品；数据以原始公告为准。"
                  % esc(meta.get("as_of", "")))

    # filter bar for products / timeline / index
    prd_opts = sorted({x for t in products for x in as_list(t.get("prod"))}) or \
        sorted({p.get("name") for p in products if p.get("name")})
    cat_options = sorted({t.get("category", "") for t in tl if t.get("category")})
    tl_filter = filter_bar("tl", []) if tl else ""

    html_doc = """!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>企业深研档案 · __COMPANY__</title><style>__CSS__</style></head><body>
<div class="wrap">
__BODY__
<div class="footer">__DISCLAIMER__<br>生成时间：__TS__ ｜ chem-enterprise-deep-dive skill ｜ 证据 __NEV__ 条 ｜ 口径告警 __NPROB__ 条</div>
</div>
<div id="mask" onclick="closeEv()"></div>
<div id="evPanel"><div class="ph"><span>证据详情</span><button class="pc" onclick="closeEv()">×</button></div>
<div class="pb" id="evBody"></div></div>
<script>
var EV = __EVJSON__;
function openEv(id){
  var e = EV[id]; if(!e) return;
  var h = '<div class="evitem"><div class="hd"><span class="id">'+e.eid+'</span><span class="ti">'+esc(e.title)+'</span></div>';
  h += '<div class="meta">'+esc(e.publisher)+' ｜ '+esc(e.date)+' ｜ '+esc(e.type)+'</div>';
  if(e.quote) h += '<blockquote>'+esc(e.quote)+'</blockquote>';
  h += '<div class="u">'+(e.url?'<a href="'+esc(e.url)+'" target="_blank" rel="noopener">'+esc(e.url)+'</a>':'<span class="na">无公开链接</span>')+'</div>';
  if(e.note) h += '<div class="meta" style="margin-top:6px">备注：'+esc(e.note)+'</div>';
  h += '</div>';
  document.getElementById('evBody').innerHTML = h;
  document.getElementById('evPanel').classList.add('open');
  document.getElementById('mask').classList.add('open');
}
function closeEv(){document.getElementById('evPanel').classList.remove('open');
document.getElementById('mask').classList.remove('open');}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeEv();});
document.addEventListener('click',function(e){
  var t=e.target; while(t && !t.getAttribute){t=t.parentNode;}
  if(t && t.getAttribute && t.getAttribute('data-f')){
    var k=t.getAttribute('data-k'), f=t.getAttribute('data-f'), v=t.value||'';
    applyF(f, k, v, t);
  }
},true);
function applyF(f,k,v){
  var rows=document.querySelectorAll('[data-f="'+f+'"]:not(select):not(input):not(button)');
  var kw=''; var q=document.getElementById(f+'_q'); if(q) kw=(q.value||'').toLowerCase();
  var states={};
  document.querySelectorAll('select[data-f="'+f+'"]').forEach(function(s){states[s.getAttribute('data-k')]=s.value;});
  var shown=0;
  rows.forEach(function(r){
    var ok=true;
    for(var key in states){
      var want=states[key]; if(!want) continue;
      var have=(r.getAttribute('data-'+key)||'');
      if(have!==want){ok=false;break;}
    }
    if(ok && kw){
      var blob=((r.getAttribute('data-kw')||'')+' '+r.textContent).toLowerCase();
      if(blob.indexOf(kw)<0) ok=false;
    }
    r.classList.toggle('hide',!ok); if(ok) shown++;
  });
  var c=document.getElementById(f+'_cnt'); if(c) c.textContent='命中 '+shown+' 条';
}
function resetF(f){
  document.querySelectorAll('[data-f="'+f+'"]').forEach(function(el){
    if(el.tagName==='SELECT') el.value='';
    if(el.type==='search') el.value='';
  });
  document.querySelectorAll('[data-f="'+f+'"]').forEach(function(el){
    if(el.getAttribute && el.getAttribute('data-kw')!==null) el.classList.remove('hide');
  });
  applyF(f,'','');
}
function pickPlant(id){
  document.querySelectorAll('.plant').forEach(function(p){p.classList.toggle('active',p.getAttribute('data-plant')===id);});
  document.querySelectorAll('svg.cn .marker').forEach(function(m){m.classList.toggle('active',m.getAttribute('data-plant')===id);});
  var el=document.getElementById('pl_'+id); if(el) el.scrollIntoView({block:'nearest',behavior:'smooth'});
}
</script></body></html>"""
    subs = {"__COMPANY__": esc(company), "__CSS__": CSS, "__BODY__": "".join(parts),
            "__DISCLAIMER__": disclaimer, "__TS__": esc(datetime.now().strftime("%Y-%m-%d %H:%M") + " ｜ chem-enterprise-deep-dive v" + SKILL_VERSION + " (" + SKILL_DATE + ")"),
            "__NEV__": str(len(ledger)), "__NPROB__": str(len(problems)),
            "__EVJSON__": json.dumps({e["eid"]: e for e in ledger}, ensure_ascii=False)}
    for k, v in subs.items():
        html_doc = html_doc.replace(k, v)
    return html_doc


# ---------------------------------------------------------------- Excel / CSV

def build_sheets(data, ledger, ledger_map):
    meta = data.get("meta") or {}
    purpose = PURPOSE_MAP.get(meta.get("purpose", ""), meta.get("purpose_label") or "产业研究")
    sheets = []

    # 01 使用说明
    rows = [["项目", "内容"],
            ["研究主体", meta.get("company", "")],
            ["统一社会信用代码", meta.get("uscc", "") or "无公开资料"],
            ["上市信息", meta.get("listing", "") or "非上市/无公开资料"],
            ["研究目的", purpose],
            ["检索窗口", meta.get("as_of", "")],
            ["证据台账编号", "E01–E%02d，与各 sheet「证据编号」列一一对应" % len(ledger)],
            ["可靠程度分级", "A 官方一手 / B 多源或多方交叉 / C 单一二手来源 / D 估算（口径见 basis 列）"],
            ["口径约定", "经营范围中的产品不等于实际生产产品；集团资产不计入研究主体；估算值不与披露值混列"],
            ["免责声明", "本台账为公开信息整理，不含经营预测、投资建议或信用评级；采购、合作、交易决策以官方核验与合同尽调为准。"],
            ["口径校验告警", "%d 条（详见 build.py stderr 输出）" % len(data.get("_problems", []))]]
    sheets.append({"name": "01_使用说明", "widths": [24, 110], "rows": rows})

    # 02 主体信息
    rows = [["项目", "内容", "证据编号", "证据标题", "来源日期", "等级"]]
    for b in as_list(data.get("base_info")):
        if b.get("group"):
            continue
        evs = [i for i in as_list(b.get("ev")) if i in ledger_map]
        if evs:
            for i in evs:
                e = ledger_map[i]
                rows.append([b.get("label", ""), b.get("value", "") or "无公开资料", i,
                             e["title"], e["date"], b.get("grade", "")])
        else:
            rows.append([b.get("label", ""), b.get("value", "") or "无公开资料", "", "", "", b.get("grade", "")])
    sheets.append({"name": "02_企业主体信息", "widths": [22, 56, 10, 42, 13, 7], "rows": rows})

    # 03 主体消歧
    rows = [["主体名称", "统一社会信用代码", "与本主体关系", "判定依据", "是否纳入范围", "证据编号", "等级"]]
    for d in as_list(data.get("disambiguation")):
        rows.append([d.get("name", ""), d.get("uscc", "") or "—", d.get("relation", ""), d.get("verdict", ""),
                     "纳入" if d.get("in_scope") else "排除", "、".join(as_list(d.get("ev"))), d.get("grade", "")])
    sheets.append({"name": "03_主体消歧", "widths": [34, 24, 26, 50, 10, 14, 7], "rows": rows})

    # 04 股权结构
    nodes = as_list((data.get("ownership") or {}).get("nodes"))
    n_map = {n.get("id"): n for n in nodes}
    rows = [["节点名称", "上级", "关系类型", "持股比例", "是否并表", "说明", "证据编号", "等级"]]
    for n in nodes:
        parent = n_map.get(n.get("parent") or "", {})
        rows.append([n.get("name", ""), parent.get("name", "—"), n.get("role", ""), n.get("pct", "") or "—",
                     "是" if n.get("kind") in ("target", "sub") else "否",
                     n.get("note", ""), "、".join(as_list(n.get("ev"))), n.get("grade", "")])
    sheets.append({"name": "04_股权结构", "widths": [34, 26, 26, 12, 9, 40, 12, 7], "rows": rows})

    # 05 分公司与子公司
    rows = [["名称", "性质", "注册地/主要经营地", "注册资本(万元)", "持股比例", "主要业务", "是否并表", "证据编号", "等级"]]
    for e in as_list(data.get("entities")):
        rows.append([e.get("name", ""), e.get("kind", ""), e.get("location", ""), e.get("capital", ""),
                     e.get("pct", ""), e.get("business", ""), "是" if e.get("consolidated") else "否",
                     "、".join(as_list(e.get("ev"))), e.get("grade", "")])
    sheets.append({"name": "05_子分公司", "widths": [38, 16, 22, 16, 12, 44, 9, 12, 7], "rows": rows})

    # 06 生产基地
    rows = [["基地/装置", "所在地区", "经纬度", "主体归属", "并表", "状态", "主要产品与产能", "证据编号", "等级"]]
    for p in as_list(data.get("plants")):
        geo = "%s, %s" % (p.get("lat"), p.get("lon")) if p.get("lat") else ""
        rows.append([p.get("name", ""), p.get("location", ""), geo, p.get("entity_name", ""),
                     "是" if p.get("consolidated") else "否", p.get("status", ""),
                     p.get("capacity_text", "") or "无公开资料", "、".join(as_list(p.get("ev"))), p.get("grade", "")])
    sheets.append({"name": "06_生产基地", "widths": [30, 30, 18, 26, 7, 14, 50, 12, 7], "rows": rows})

    # 07 装置
    rows = [["基地", "装置名称", "工艺", "规模/产能", "投产年份", "状态", "说明", "证据编号", "等级"]]
    for u in as_list(data.get("units")):
        rows.append([u.get("plant", ""), u.get("name", ""), u.get("process", ""), u.get("scale", ""),
                     u.get("year", ""), u.get("status", ""), u.get("note", ""),
                     "、".join(as_list(u.get("ev"))), u.get("grade", "")])
    sheets.append({"name": "07_装置清单", "widths": [20, 34, 20, 22, 10, 14, 40, 12, 7], "rows": rows})

    # 08 产品与产能
    rows = [["产品", "产品说明", "生产主体/基地", "产能口径", "产能值", "是否估算", "推得口径(basis)",
             "下游流向", "证据编号", "等级"]]
    for p in as_list(data.get("products")):
        caps = as_list(p.get("capacity")) or [{}]
        for c in caps:
            rows.append([p.get("name", ""), p.get("note", ""), "；".join(as_list(p.get("producers"))),
                         c.get("label", ""), c.get("value", "") or "无公开资料",
                         "估算" if c.get("estimate") else "披露",
                         c.get("basis", ""), "；".join(as_list(p.get("downstream"))),
                         "、".join(as_list(p.get("ev"))) or "、".join(as_list(c.get("ev"))), p.get("grade", "")])
    sheets.append({"name": "08_产品与产能", "widths": [16, 40, 30, 22, 18, 8, 34, 30, 12, 7], "rows": rows})

    # 09 工艺路线
    rows = [["工艺名称", "路线简述", "适用产品", "单耗/原料特征", "证据编号", "等级"]]
    for pr in as_list(data.get("processes")):
        rows.append([pr.get("name", ""), pr.get("desc", ""), "；".join(as_list(pr.get("products"))),
                     pr.get("key", ""), "、".join(as_list(pr.get("ev"))), pr.get("grade", "")])
    sheets.append({"name": "09_生产工艺", "widths": [22, 66, 22, 34, 12, 7], "rows": rows})

    # 10 产业链
    rows = [["环节", "对象", "与本主体关系", "说明", "证据编号", "等级"]]
    for c in as_list(data.get("chain")):
        rows.append([c.get("lane", ""), c.get("obj", ""), c.get("rel", ""), c.get("note", ""),
                     "、".join(as_list(c.get("ev"))), c.get("grade", "")])
    sheets.append({"name": "10_产业链位置", "widths": [16, 26, 30, 50, 12, 7], "rows": rows})

    # 11 区域布局
    rows = [["地区", "覆盖范围", "主体/基地", "业务内容", "证据编号", "等级"]]
    for r in as_list(data.get("regions")):
        rows.append([r.get("region", ""), r.get("scope", ""), "；".join(as_list(r.get("entities"))),
                     r.get("business", ""), "、".join(as_list(r.get("ev"))), r.get("grade", "")])
    sheets.append({"name": "11_区域布局", "widths": [16, 26, 30, 46, 12, 7], "rows": rows})

    # 12 项目
    rows = [["项目名称", "类型", "地点", "建设内容/规模", "投资额", "资金来源", "进展", "时间节点",
             "证据编号", "等级"]]
    for p in as_list(data.get("projects")):
        rows.append([p.get("name", ""), p.get("type", ""), p.get("location", ""), p.get("scale", ""),
                     p.get("capex", ""), p.get("funding", ""), p.get("status", ""), p.get("timeline", ""),
                     "、".join(as_list(p.get("ev"))), p.get("grade", "")])
    sheets.append({"name": "12_项目清单", "widths": [30, 12, 20, 46, 16, 20, 16, 24, 12, 7], "rows": rows})

    # 13 财务
    ys = as_list(data.get("finance_years"))
    rows = [["指标"] + ys + ["证据编号", "等级"]]
    for f in as_list(data.get("finance")):
        rows.append([f.get("item", "")] + as_list(f.get("values")) + ["、".join(as_list(f.get("ev"))), f.get("grade", "")])
    if not as_list(data.get("finance")):
        rows.append(["非上市主体或公开财务数据不足，不推测营收与盈利", "", "", "", "", "", ""])
    sheets.append({"name": "13_财务与分业务", "widths": [30, 16, 16, 16, 16, 12, 7], "rows": rows})

    # 14 经营风险
    rows = [["类别", "公开事实", "状态", "证据编号", "等级"]]
    for r in as_list(data.get("risks")):
        rows.append([r.get("category", ""), r.get("finding", ""),
                     STATUS_MAP.get(r.get("status", "todo"), STATUS_MAP["todo"])[0],
                     "、".join(as_list(r.get("ev"))), r.get("grade", "")])
    sheets.append({"name": "14_经营风险", "widths": [20, 86, 10, 14, 7], "rows": rows})

    # 15 重要事件时间线
    rows = [["日期", "事件", "类别", "证据编号", "等级"]]
    for t in as_list(data.get("timeline")):
        rows.append([t.get("date", ""), t.get("text", ""), t.get("category", "") or t.get("kind", ""),
                     "、".join(as_list(t.get("ev"))), t.get("grade", "")])
    sheets.append({"name": "15_重要事件", "widths": [14, 92, 12, 12, 7], "rows": rows})

    # 16 证据台账
    rows = [["证据编号", "标题", "发布方", "来源日期", "类型", "原文摘录", "URL", "备注"]]
    for e in ledger:
        rows.append([e["eid"], e["title"], e["publisher"], e["date"], e["type"], e["quote"], e["url"], e["note"]])
    sheets.append({"name": "16_证据台账", "widths": [9, 50, 18, 12, 16, 60, 60, 30], "rows": rows})

    # 17 无公开资料与待核验
    rows = [["事项", "当前状态", "建议核实途径"]]
    for x in as_list(data.get("gaps")):
        rows.append([x.get("item", ""), x.get("status", "无公开资料"), x.get("how", "")])
    sheets.append({"name": "17_待核验清单", "widths": [40, 18, 70], "rows": rows})
    return sheets


def write_xlsx(sheets, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    head_fill = PatternFill("solid", fgColor="1F3F70")
    head_font = Font(bold=True, color="FFFFFF", size=10.5, name="Microsoft YaHei")
    body_font = Font(size=10, name="Microsoft YaHei")
    thin = Side(style="thin", color="DDE2E9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for sh in sheets:
        ws = wb.create_sheet(sh["name"][:31])
        if sh["name"] == "01_使用说明":
            ws.column_dimensions["A"].width = 24
            ws.column_dimensions["B"].width = 110
            for r in sh["rows"]:
                ws.append(r)
            for cell in ws[1]:
                cell.font = head_font
                cell.fill = head_fill
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.font = body_font
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.freeze_panes = "A2"
            continue
        for j, w in enumerate(sh["widths"], 1):
            ws.column_dimensions[get_column_letter(j)].width = w
        for r in sh["rows"]:
            ws.append([("" if c is None else c) for c in r])
        for cell in ws[1]:
            cell.font = head_font
            cell.fill = head_fill
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = border
        ws.row_dimensions[1].height = 26
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = body_font
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                cell.border = border
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(max(len(sh["widths"]), 1)), max(len(sh["rows"]), 1))
        heads = [str(c) for c in sh["rows"][0]]
        for j, head in enumerate(heads, 1):
            if head.strip().upper() == "URL":
                for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                    for cell in row:
                        if cell.value and str(cell.value).startswith("http"):
                            cell.hyperlink = cell.value
                            cell.font = Font(size=9.5, color="1554C0", underline="single", name="Microsoft YaHei")
    wb.save(path)


def write_csvs(sheets, outdir, stem):
    paths = []
    for i, sh in enumerate(sheets, 1):
        p = os.path.join(outdir, "%02d_%s.csv" % (i, safe_stem(sh["name"])))
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerows(sh["rows"])
        paths.append(p)
    return paths


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="chem-enterprise-deep-dive 交付物渲染器")
    ap.add_argument("data", help="data.json 路径（规范见 references/data-schema.md）")
    ap.add_argument("-o", "--outdir", default=None)
    ap.add_argument("--stem", default=None)
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--xlsx-only", action="store_true")
    ap.add_argument("--strict", action="store_true", help="口径校验不通过时直接失败")
    args = ap.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta") or {}
    purpose = PURPOSE_MAP.get(meta.get("purpose", ""), meta.get("purpose_label") or "产业研究")
    stem = args.stem or safe_stem("企业深研_%s_%s" % (meta.get("company", "目标企业"), purpose))
    outdir = args.outdir or os.path.join(os.path.dirname(os.path.abspath(args.data)), "output")
    os.makedirs(outdir, exist_ok=True)

    ledger, ledger_map = collect_evidence(data)
    problems = validate(data, set(e["eid"] for e in ledger), strict=args.strict)
    data["_problems"] = problems
    ledger_map = {e["eid"]: e for e in ledger}
    made = []
    if not args.xlsx_only:
        p = os.path.join(outdir, stem + ".html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(render_html(data, ledger, ledger_map, problems))
        made.append(p)
    if not args.html_only:
        p = os.path.join(outdir, stem + ".xlsx")
        try:
            write_xlsx(build_sheets(data, ledger, ledger_map), p)
        except ImportError:
            print("[warn] 未安装 openpyxl，Excel 降级为 CSV 系列", file=sys.stderr)
            made += write_csvs(build_sheets(data, ledger, ledger_map), outdir, stem)
        else:
            made.append(p)
    for p in made:
        print("[ok]", os.path.abspath(p))
    if not ledger:
        print("[warn] data.json 的 evidence[] 为空——请补证据后重跑", file=sys.stderr)


if __name__ == "__main__":
    main()
