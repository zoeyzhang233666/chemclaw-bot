#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
customer360-chemical :: build.py
把按 references/data-schema.md 填好的 data.json 渲染为两份固定交付物：
  1) 客户360_{公司}_画像.html    —— 单文件交互式一页画像（点击展开证据，无外部依赖）
  2) 客户360_{公司}_核查台账.xlsx —— 多 sheet 证据台账（缺 openpyxl 时自动降级为同名 CSV 系列）

用法：
  python build.py data.json [-o 输出目录] [--stem 文件名前缀] [--html-only|--xlsx-only]

本脚本不做任何研究判断：所有内容来自 data.json。不要为渲染效果修改事实。
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from datetime import datetime

# ---------------------------------------------------------------- utilities

STATUS_MAP = {
    "ok":   ("正常", "tag ok"),
    "warn": ("待复核", "tag warn"),
    "risk": ("关注", "tag risk"),
    "todo": ("待办", "tag todo"),
}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def as_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


def safe_stem(s):
    s = re.sub(r'[\\/:*?"<>|\r\n]+', "_", str(s)).strip()
    return s or "客户360"


def collect_ledger(data):
    """遍历 data，收集所有 evidence 条目，按 URL 去重，编号 E01…"""
    ledger, seen = [], set()
    def walk(node):
        if isinstance(node, dict):
            for ev in as_list(node.get("evidence")):
                if isinstance(ev, dict) and ev.get("url") and ev["url"] not in seen:
                    seen.add(ev["url"])
                    ledger.append({
                        "id": "E%02d" % (len(ledger) + 1),
                        "title": ev.get("title", ""),
                        "date": ev.get("date", ""),
                        "url": ev["url"],
                    })
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(data)
    return ledger, {e["url"]: e["id"] for e in ledger}


# ---------------------------------------------------------------- HTML

CSS = """
:root{--ink:#1a2233;--sub:#5a6472;--line:#e3e7ee;--bg:#f4f6f9;--blue:#1554c0;
--blue-bg:#eef3fc;--red:#c0392b;--red-bg:#fdf0ee;--green:#1e7f4f;--green-bg:#edf7f1;
--amber:#9a6b00;--amber-bg:#fdf6e7;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;background:var(--bg);
color:var(--ink);font-size:14px;line-height:1.65;}
.wrap{max-width:1080px;margin:0 auto;padding:16px 16px 60px;}
.hero{background:linear-gradient(120deg,#12274a,#1554c0 85%);color:#fff;border-radius:14px;
padding:22px 24px 18px;}
.hero .kicker{font-size:12px;letter-spacing:.14em;opacity:.75;}
.hero h1{font-size:24px;margin:4px 0 2px;font-weight:700;}
.hero .code{font-size:13px;opacity:.85;}
.badges{margin-top:12px;display:flex;flex-wrap:wrap;gap:8px;}
.badge{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.28);
border-radius:999px;padding:3px 12px;font-size:12.5px;}
.badge b{font-weight:700;}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-top:14px;}
.card h2{font-size:16px;margin-bottom:10px;display:flex;align-items:center;gap:8px;}
.tag{font-size:11.5px;border-radius:4px;padding:1px 7px;}
.tag.ok{background:var(--green-bg);color:var(--green);}
.tag.warn{background:var(--amber-bg);color:var(--amber);}
.tag.risk{background:var(--red-bg);color:var(--red);}
.tag.todo{background:#eef0f3;color:#5a6472;}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:14px;}
.ans{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px;}
.ans .q{font-size:12px;color:var(--sub);letter-spacing:.06em;}
.ans .a{font-size:16px;font-weight:700;margin:4px 0 8px;}
.ans .why{font-size:13px;color:var(--sub);}
.ans .why b{color:var(--ink);}
.verdict{background:var(--amber-bg);border:1px solid #ecd9a8;}
.verdict .a{color:var(--amber);}
.buy{background:var(--blue-bg);border:1px solid #c9dbf5;}
.buy .a{color:var(--blue);}
.riskbar{margin-top:14px;background:var(--red-bg);border:1px solid #f0c9c2;border-radius:12px;
padding:12px 18px;font-size:13.5px;}
.riskbar b{color:var(--red);}
.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;}
.abtn{cursor:pointer;border:1px solid var(--blue);color:var(--blue);background:#fff;
border-radius:8px;padding:8px 16px;font-size:13.5px;font-weight:600;}
.abtn:hover{background:var(--blue);color:#fff;}
.apanel{display:none;margin-top:10px;background:#f8fafc;border:1px dashed #c4cfdd;
border-radius:10px;padding:14px 18px;font-size:13.5px;}
.apanel.show{display:block;}
.apanel h3{font-size:13.5px;margin:0 0 6px;}
.apanel ul{padding-left:18px;}
.apanel li{margin:3px 0;}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-top:22px;border-bottom:2px solid var(--line);}
.tab{cursor:pointer;padding:8px 18px;font-size:14px;font-weight:600;color:var(--sub);
border-radius:8px 8px 0 0;border:1px solid transparent;border-bottom:none;}
.tab.active{color:var(--blue);background:#fff;border-color:var(--line);position:relative;
top:2px;border-bottom:2px solid #fff;}
.pane{display:none;background:#fff;border:1px solid var(--line);border-top:none;
border-radius:0 0 12px 12px;padding:18px 22px;}
.pane.active{display:block;}
.pane h3{font-size:14.5px;margin:14px 0 6px;color:var(--blue);}
.pane h3:first-child{margin-top:0;}
.pane p,.pane li,.pane td,.pane th{font-size:13.5px;}
.pane ul{padding-left:20px;margin:4px 0;}
.pane li{margin:4px 0;}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin:8px 0;}
.kv .cell{background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:10px 12px;}
.kv .k{font-size:11.5px;color:var(--sub);}
.kv .v{font-size:14px;font-weight:700;margin-top:2px;}
table.dt{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0;}
table.dt th,table.dt td{border:1px solid var(--line);padding:6px 10px;text-align:left;
vertical-align:top;}
table.dt th{background:#f8fafc;white-space:nowrap;}
.note{background:var(--amber-bg);border-left:3px solid #d9a92c;border-radius:0 8px 8px 0;
padding:10px 14px;margin:10px 0;font-size:13px;}
.note b{color:var(--amber);}
.tl{border-left:2px solid #c9d6ea;margin:8px 0 8px 6px;padding-left:18px;}
.tl .item{position:relative;margin:10px 0;}
.tl .item::before{content:"";position:absolute;left:-23.5px;top:7px;width:9px;height:9px;
border-radius:50%;background:var(--blue);}
.tl .d{font-size:12px;color:var(--sub);font-weight:600;}
.tl .t{font-size:13.5px;}
details.ev{margin-top:10px;border-top:1px dashed var(--line);padding-top:6px;}
details.ev summary{cursor:pointer;font-size:12.5px;color:var(--blue);user-select:none;}
.ev .src{font-size:12.5px;color:var(--sub);margin:4px 0 2px;}
.ev .src a{color:var(--blue);word-break:break-all;}
.estimate{color:var(--amber);font-weight:600;}
footer{margin-top:22px;font-size:12px;color:var(--sub);border-top:1px solid var(--line);
padding-top:12px;}
a{color:var(--blue);}
"""


def ev_html(evidence, evmap):
    evs = as_list(evidence)
    if not evs:
        return ""
    rows = []
    for ev in evs:
        eid = evmap.get(ev.get("url"), "")
        rows.append(
            '<div class="src">%s ｜ %s%s ｜ <a href="%s" target="_blank">%s</a></div>'
            % (esc(eid), esc(ev.get("title", "")),
               ("（%s）" % esc(ev["date"])) if ev.get("date") else "",
               esc(ev.get("url")), esc(ev.get("url")))
        )
    return ('<details class="ev"><summary>▸ 来源证据（%d 条，编号对应Excel证据台账）</summary>%s</details>'
            % (len(evs), "".join(rows)))


def pane_products(sec):
    if not sec:
        return "<p>待补充</p>"
    out = ['<h3>关键指标</h3><div class="kv">']
    for m in as_list(sec.get("key_metrics")):
        out.append('<div class="cell"><div class="k">%s</div><div class="v">%s</div></div>'
                   % (esc(m.get("label", "")), esc(m.get("value", ""))))
    out.append("</div>")
    if sec.get("facts"):
        out.append("<h3>事实与结构</h3><ul>")
        out += ["<li>%s</li>" % esc(f) for f in as_list(sec["facts"])]
        out.append("</ul>")
    if sec.get("value_chain"):
        out.append("<h3>产业链位置</h3><ul>")
        out += ["<li><b>%s</b></li>" % esc(f) for f in as_list(sec["value_chain"])]
        out.append("</ul>")
    return "".join(out)


def pane_projects(sec):
    if not sec:
        return "<p>待补充</p>"
    out = ["<h3>近期事件时间线</h3><div class='tl'>"]
    for it in as_list(sec.get("timeline")):
        out.append('<div class="item"><div class="d">%s</div><div class="t">%s</div></div>'
                   % (esc(it.get("date", "")), esc(it.get("text", ""))))
    out.append("</div>")
    if sec.get("implications_for_my_product"):
        out.append("<div class='note'><b>对我的产品的含义</b><ul>")
        out += ["<li>%s</li>" % esc(f) for f in as_list(sec["implications_for_my_product"])]
        out.append("</ul></div>")
    return "".join(out)


def pane_procurement(sec):
    if not sec:
        return "<p>待补充</p>"
    out = []
    if sec.get("demand_estimates"):
        out.append("<h3>需求测算</h3><table class='dt'><tr><th>品类</th><th>测算口径</th>"
                   "<th>结果</th><th>性质</th></tr>")
        for d in as_list(sec["demand_estimates"]):
            est = ('<span class="estimate">估算（%s）</span>' % esc(d.get("estimate", "口径未注明"))
                   if d.get("estimate") else "披露值")
            out.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                       % (esc(d.get("item", "")), esc(d.get("basis", "")),
                          esc(d.get("value", "")), est))
        out.append("</table>")
    if sec.get("supply_layers"):
        out.append("<h3>供应三层结构</h3><table class='dt'><tr><th>层次</th><th>内容</th>"
                   "<th>对销售的意义</th></tr>")
        for s in as_list(sec["supply_layers"]):
            out.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                       % (esc(s.get("layer", "")), esc(s.get("content", "")),
                          esc(s.get("meaning", ""))))
        out.append("</table>")
    if sec.get("decision_chain"):
        out.append("<h3>决策链推断（推断，需验证）</h3><ul>")
        out += ["<li>%s</li>" % esc(f) for f in as_list(sec["decision_chain"])]
        out.append("</ul>")
    if sec.get("caveats"):
        out.append("<div class='note'><b>口径与诚信提示</b><ul>")
        out += ["<li>%s</li>" % esc(f) for f in as_list(sec["caveats"])]
        out.append("</ul></div>")
    return "".join(out)


def pane_risks(sec):
    if not sec:
        return "<p>待补充</p>"
    out = ["<h3>七项背景核查结果</h3><table class='dt'><tr><th>核查项</th><th>结果与证据</th>"
           "<th>状态</th></tr>"]
    for c in as_list(sec.get("seven_checks")):
        label, cls = STATUS_MAP.get(c.get("status", "todo"), STATUS_MAP["todo"])
        out.append('<tr><td>%s</td><td>%s</td><td><span class="%s">%s</span></td></tr>'
                   % (esc(c.get("item", "")), esc(c.get("finding", "")), cls, label))
    out.append("</table>")
    if sec.get("key_concerns"):
        out.append("<h3>需要重点关注的事项</h3><ul>")
        out += ["<li>%s</li>" % esc(f) for f in as_list(sec["key_concerns"])]
        out.append("</ul>")
    return "".join(out)


def pane_checklist(items):
    if not items:
        return "<p>待补充</p>"
    out = ["<h3>合作前建议补充核实的材料清单</h3><table class='dt'><tr><th>#</th><th>材料/动作</th>"
           "<th>目的</th></tr>"]
    for i, c in enumerate(as_list(items), 1):
        out.append("<tr><td>%d</td><td>%s</td><td>%s</td></tr>"
                   % (i, esc(c.get("item", "")), esc(c.get("purpose", ""))))
    out.append("</table>"
               "<div class='note'><b>边界声明：</b>本页仅为公开信息整理与销售线索分析，"
               "<b>不含信用评级、授信额度或履约概率</b>；交易与账期决策以官方核验、合同尽调与"
               "贵司风控政策为准。</div>")
    return "".join(out)


def render_html(data, ledger, evmap):
    meta = data.get("meta", {})
    ent = data.get("entity_confirmation") or {}
    summ = data.get("summary") or {}
    act = data.get("next_actions") or {}

    code_line = " ｜ ".join(x for x in [meta.get("uscc", ""), meta.get("listing", ""),
                                        meta.get("registered_address", "")] if x)
    badges = [
        '我的销售产品：<b>%s</b>' % esc(meta.get("sales_product", "未指定")),
        '主体确认：<b>%s</b>' % ("已核验" if ent.get("conclusion") else "待确认"),
        '检索窗口：%s' % esc(meta.get("research_date", "")),
    ]
    if meta.get("prepared_for"):
        badges.append(esc(meta["prepared_for"]) + "视角")
    if meta.get("notes"):
        badges.append(esc(meta["notes"]))

    demo_banner = ""
    if meta.get("is_demo"):
        demo_banner = ('<div class="note" style="border-left-color:#c0392b;background:var(--red-bg);">'
                       '<b>教学示例（is_demo=true）：</b>本文件的公司为虚构、证据URL为 example.com 占位符，'
                       '仅演示数据结构与判断方法；实际研究必须用真实检索结果填充。'
                       '生成正式报告时请删除 data.json 中的 is_demo 标记。</div>')

    # 主体确认卡
    ent_rows = "".join(
        "<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>"
        % (esc(r.get("name", "")), esc(r.get("identity", "")), esc(r.get("sales_meaning", "")))
        for r in as_list(ent.get("near_name_table")))
    entity_card = """
<div class="card"><h2>① 主体确认（防止同名/近名查错）<span class="tag ok">已锁定交易主体</span></h2>
<p style="font-size:13.5px">%s</p>
<table class="dt"><tr><th>主体</th><th>是什么</th><th>对销售的意义</th></tr>%s</table>
%s</div>""" % (esc(ent.get("conclusion", "待补充")), ent_rows,
               ev_html(ent.get("evidence"), evmap))

    # 首屏三问
    def ans_card(cls, q, a, why):
        return ('<div class="ans %s"><div class="q">%s</div><div class="a">%s</div>'
                '<div class="why">%s</div></div>' % (cls, q, a, why))
    it = summ.get("is_target_customer") or {}
    lb = summ.get("likely_buy") or {}
    wb = summ.get("why_buy_logic") or {}
    grid = ('<div class="grid3">%s%s%s</div>'
            '<div class="riskbar">⚠ <b>给账期前必看：</b>%s %s</div>'
            % (ans_card("verdict", "问题一：它是不是我要找的客户？",
                        esc(it.get("verdict", "待补充")), esc(it.get("reason", ""))),
               ans_card("buy", "问题二：它可能买什么？",
                        esc(lb.get("answer", "待补充")), esc(lb.get("reason", ""))),
               ans_card("", "问题三：为什么（需求逻辑链）",
                        esc(wb.get("headline", "待补充")), esc(wb.get("detail", ""))),
               esc(summ.get("risk_banner", "")),
               ev_html(summ.get("evidence"), evmap)))

    # 后续动作
    panels = [("p1", "找客户最近的切入点", act.get("entry_points")),
              ("p2", "判断应该先找哪个部门", act.get("departments")),
              ("p3", "准备客户拜访", act.get("visit_prep"))]
    actions = '<div class="actions">%s</div>' % "".join(
        '<button class="abtn" onclick="showPanel(\'%s\')">%s</button>' % (pid, title)
        for pid, title, _ in panels)
    panels_html = "".join(
        '<div class="apanel" id="%s"><h3>%s</h3><ul>%s</ul></div>'
        % (pid, title, "".join("<li>%s</li>" % esc(x) for x in as_list(items)))
        for pid, title, items in panels)

    # 分区
    tabs_def = [
        ("产品与工厂", pane_products(data.get("products_plants")),
         ev_html((data.get("products_plants") or {}).get("evidence"), evmap)),
        ("项目与动态", pane_projects(data.get("projects_news")),
         ev_html((data.get("projects_news") or {}).get("evidence"), evmap)),
        ("采购关系", pane_procurement(data.get("procurement")),
         ev_html((data.get("procurement") or {}).get("evidence"), evmap)),
        ("企业风险", pane_risks(data.get("risks")),
         ev_html((data.get("risks") or {}).get("evidence"), evmap)),
        ("合作前核实清单", pane_checklist(data.get("verification_checklist")), ""),
    ]
    tabs = '<div class="tabs">%s</div>' % "".join(
        '<div class="tab%s" onclick="switchTab(%d)">%s</div>'
        % (" active" if i == 0 else "", i, esc(t)) for i, (t, _, _) in enumerate(tabs_def))
    panes = "".join(
        '<div class="pane%s" id="pane%d">%s%s</div>'
        % (" active" if i == 0 else "", i, body, ev)
        for i, (_, body, ev) in enumerate(tabs_def))

    ledger_rows = "".join(
        "<div class='src'>%s ｜ %s%s ｜ <a href='%s' target='_blank'>%s</a></div>"
        % (esc(e["id"]), esc(e["title"]), ("（%s）" % esc(e["date"])) if e["date"] else "",
           esc(e["url"]), esc(e["url"]))
        for e in ledger)

    disclaimer = ("数据来源：公开信息与信用聚合平台快照，检索窗口%s；点击各处“来源证据”可查看原始链接。"
                  "本页不构成任何信用评级、授信建议或履约承诺。%s"
                  % (esc(meta.get("research_date", "")), esc(data.get("disclaimer_extra", ""))))

    return """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>客户360画像 · %s</title><style>%s</style></head><body><div class="wrap">
<div class="hero"><div class="kicker">客户 360 画像 · 内贸销售</div>
<h1>%s</h1><div class="code">%s</div>
<div class="badges">%s</div></div>
%s%s%s%s%s
%s%s
<div class="card"><h2>证据台账（全部 %d 条）</h2>%s</div>
<footer>%s<br>生成时间：%s ｜ customer360-chemical skill</footer></div>
<script>
function switchTab(i){var t=document.querySelectorAll('.tab'),p=document.querySelectorAll('.pane');
for(var k=0;k<t.length;k++){t[k].classList.toggle('active',k===i);}
for(var k=0;k<p.length;k++){p[k].classList.toggle('active',k===i);}}
function showPanel(id){var el=document.getElementById(id),open=el.classList.contains('show');
document.querySelectorAll('.apanel').forEach(function(x){x.classList.remove('show');});
if(!open){el.classList.add('show');}}
</script></body></html>""" % (
        esc(meta.get("company_display", "")), CSS,
        esc(meta.get("company_display", "")), esc(code_line),
        "".join('<span class="badge">%s</span>' % b for b in badges),
        demo_banner, entity_card, grid, actions, panels_html, tabs, panes,
        len(ledger), ledger_rows, esc(disclaimer),
        esc(datetime.now().strftime("%Y-%m-%d %H:%M")))


# ---------------------------------------------------------------- sheets（Excel/CSV共用）

def build_sheets(data, ledger, evmap):
    meta = data.get("meta", {})
    ent = data.get("entity_confirmation") or {}
    summ = data.get("summary") or {}
    act = data.get("next_actions") or {}
    prod = data.get("products_plants") or {}
    proj = data.get("projects_news") or {}
    proc = data.get("procurement") or {}
    risk = data.get("risks") or {}
    chk = data.get("verification_checklist") or []

    def ev_rows(evlist):
        rows = [["证据编号", "标题", "日期", "URL"]]
        for ev in as_list(evlist):
            eid = evmap.get(ev.get("url"), "")
            rows.append([eid, ev.get("title", ""), ev.get("date", ""), ev.get("url", "")])
        return rows

    sheets = []
    sheets.append({"name": "1使用说明", "widths": [22, 90], "rows": [
        ["项目", "内容"],
        ["标的公司", meta.get("company_display", "")],
        ["统一社会信用代码", meta.get("uscc", "")],
        ["上市信息", meta.get("listing", "")],
        ["注册地址", meta.get("registered_address", "")],
        ["销售产品（视角）", meta.get("sales_product", "")],
        ["检索窗口", meta.get("research_date", "")],
        ["用途", meta.get("prepared_for", "")],
        ["备注", meta.get("notes", "")],
        ["示例标记", "教学示例（虚构数据，URL占位）" if meta.get("is_demo") else "常规研究"],
        ["免责声明", "本台账为公开信息整理，不含信用评级、授信额度或履约概率；"
                    "交易与账期决策以官方核验与风控政策为准。"],
    ]})
    sheets.append({"name": "2销售摘要", "widths": [26, 46, 46], "rows": [
        ["问题", "结论", "理由/口径"],
        ["它是不是我要找的客户", (summ.get("is_target_customer") or {}).get("verdict", ""),
         (summ.get("is_target_customer") or {}).get("reason", "")],
        ["它可能买什么", (summ.get("likely_buy") or {}).get("answer", ""),
         (summ.get("likely_buy") or {}).get("reason", "")],
        ["为什么（需求逻辑链）", (summ.get("why_buy_logic") or {}).get("headline", ""),
         (summ.get("why_buy_logic") or {}).get("detail", "")],
        ["给账期前必看", summ.get("risk_banner", ""), ""],
    ] + ev_rows(summ.get("evidence"))})
    ent_rows = [["主体", "是什么", "对销售的意义"]] + [
        [r.get("name", ""), r.get("identity", ""), r.get("sales_meaning", "")]
        for r in as_list(ent.get("near_name_table"))]
    sheets.append({"name": "3主体确认", "widths": [34, 40, 46], "rows":
                   [["主体锁定结论", ent.get("conclusion", ""), ""]] + ent_rows
                   + ev_rows(ent.get("evidence"))})
    seven_rows = [["核查项", "结果与证据", "状态", "检索窗口"]] + [
        [c.get("item", ""), c.get("finding", ""),
         STATUS_MAP.get(c.get("status", "todo"), STATUS_MAP["todo"])[0],
         meta.get("research_date", "")]
        for c in as_list(risk.get("seven_checks"))]
    sheets.append({"name": "4七项核查", "widths": [24, 84, 10, 16], "rows": seven_rows})
    prod_rows = [["指标", "数值"]] + [
        [m.get("label", ""), m.get("value", "")] for m in as_list(prod.get("key_metrics"))]
    prod_rows.append(["事实与结构", "\n".join("· %s" % f for f in as_list(prod.get("facts"))), ""])
    prod_rows.append(["产业链位置", "\n".join("· %s" % f for f in as_list(prod.get("value_chain"))), ""])
    sheets.append({"name": "5产品与工厂", "widths": [22, 100, 10], "rows":
                   prod_rows + ev_rows(prod.get("evidence"))})
    proj_rows = [["日期", "事件"]] + [
        [t.get("date", ""), t.get("text", "")] for t in as_list(proj.get("timeline"))]
    proj_rows.append(["对我的产品的含义", "\n".join("· %s" % f for f in
                     as_list(proj.get("implications_for_my_product"))), ""])
    sheets.append({"name": "6项目与动态", "widths": [20, 100, 10], "rows":
                   proj_rows + ev_rows(proj.get("evidence"))})
    proc_rows = [["需求品类", "测算口径", "结果", "性质"]] + [
        [d.get("item", ""), d.get("basis", ""), d.get("value", ""),
         ("估算：" + str(d.get("estimate", ""))) if d.get("estimate") else "披露值"]
        for d in as_list(proc.get("demand_estimates"))]
    proc_rows.append(["供应层次", "内容", "对销售的意义", ""])
    proc_rows += [[s.get("layer", ""), s.get("content", ""), s.get("meaning", ""), ""]
                  for s in as_list(proc.get("supply_layers"))]
    proc_rows.append(["决策链推断（需验证）", "\n".join("· %s" % f for f in
                      as_list(proc.get("decision_chain"))), "", ""])
    proc_rows.append(["口径与诚信提示", "\n".join("· %s" % f for f in
                      as_list(proc.get("caveats"))), "", ""])
    sheets.append({"name": "7采购关系", "widths": [24, 60, 34, 18], "rows":
                   proc_rows + ev_rows(proc.get("evidence"))})
    sheets.append({"name": "8风险与关注", "widths": [110, 10], "rows":
                   [["需要重点关注的事项（事实+动作，非评级）", ""]] + [
                       ["%d. %s" % (i, f), ""] for i, f in enumerate(as_list(risk.get("key_concerns")), 1)]
                   + ev_rows(risk.get("evidence"))})
    sheets.append({"name": "9核实清单", "widths": [70, 60], "rows":
                   [["材料/动作", "目的"]] + [
                       [c.get("item", ""), c.get("purpose", "")] for c in as_list(chk)]})
    sheets.append({"name": "10证据台账", "widths": [10, 50, 14, 80], "rows":
                   [["证据编号", "标题", "日期", "URL"]] + [
                       [e["id"], e["title"], e["date"], e["url"]] for e in ledger]})
    return sheets


def write_xlsx(sheets, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    head_fill = PatternFill("solid", fgColor="DCE6F4")
    for sh in sheets:
        ws = wb.create_sheet(sh["name"][:31])
        for j, w in enumerate(sh["widths"], 1):
            ws.column_dimensions[get_column_letter(j)].width = w
        for row in sh["rows"]:
            ws.append([(c if isinstance(c, str) else str(c)) for c in row])
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = head_fill
            cell.alignment = Alignment(vertical="top")
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"
        # URL 列加超链接
        for j, head in enumerate(sh["rows"][0], 1):
            if str(head).strip() == "URL":
                for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                    for cell in row:
                        if cell.value and str(cell.value).startswith("http"):
                            cell.hyperlink = cell.value
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
    ap = argparse.ArgumentParser(description="customer360-chemical 交付物渲染器")
    ap.add_argument("data", help="data.json 路径（规范见 references/data-schema.md）")
    ap.add_argument("-o", "--outdir", default=None)
    ap.add_argument("--stem", default=None)
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--xlsx-only", action="store_true")
    args = ap.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta", {})
    stem = args.stem or safe_stem("客户360_%s" % meta.get("company_display", "目标客户"))
    outdir = args.outdir or os.path.join(os.path.dirname(os.path.abspath(args.data)), "output")
    os.makedirs(outdir, exist_ok=True)

    ledger, evmap = collect_ledger(data)
    made = []
    if not args.xlsx_only:
        p = os.path.join(outdir, stem + "_画像.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(render_html(data, ledger, evmap))
        made.append(p)
    if not args.html_only:
        p = os.path.join(outdir, stem + "_核查台账.xlsx")
        try:
            write_xlsx(build_sheets(data, ledger, evmap), p)
        except ImportError:
            print("[warn] 未安装 openpyxl，Excel 降级为 CSV 系列", file=sys.stderr)
            made += write_csvs(build_sheets(data, ledger, evmap), outdir, stem + "_核查台账")
        else:
            made.append(p)
    for p in made:
        print("[ok]", os.path.abspath(p))
    if not ledger:
        print("[warn] data.json 中没有任何 evidence 条目——请补证据后重跑", file=sys.stderr)


if __name__ == "__main__":
    main()
