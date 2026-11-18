#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""产出单文件自包含 HTML 报告（推荐主交付物）。

特点:
  · 单个 .html 文件，CSS/JS 全部内联，不依赖任何外部资源 —— 拷到任何电脑、离线、发微信都能打开
  · 商机卡按三个分组分区展示，每张卡显示全部字段、证据链接可点
  · 顶部有筛选条：按分组 / 区域 / 置信度 / 时效性 / 关键词实时筛选
  · 含概览分布、置信度分级依据、被剔除同行名单、负结果与覆盖缺口、复现方法

叙事内容（负结果、覆盖缺口、通道清单、置信度依据）由 agent 写在
<任务目录>/report_notes.json 里，本脚本负责渲染。缺这个文件也能出表，只是那几节留空。

用法: python build_html.py --config <product.json> [--dir <任务目录>]
"""
from __future__ import annotations

import html
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1f2933;--mut:#6b7280;--line:#e5e7eb;
--p1:#b91c1c;--p2:#c2410c;--p3:#a16207;--p4:#6b7280;
--g1:#15803d;--g2:#a16207;--g3:#1d4ed8;--out:#9ca3af;--link:#1d4ed8;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:26px 18px 70px}
h1{font-size:25px;margin:0 0 6px}h2{font-size:19px;margin:38px 0 12px;padding-bottom:7px;border-bottom:2px solid var(--line)}
h3{font-size:15px;margin:22px 0 9px}
.sub{color:var(--mut);font-size:13px;margin-bottom:16px}
.box{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:14px 0}
.kv{display:grid;grid-template-columns:150px 1fr;gap:6px 14px;font-size:13.5px}
.kv b{color:var(--mut);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px 15px}
.stat .n{font-size:25px;font-weight:700;line-height:1.15}
.stat .l{color:var(--mut);font-size:12.5px;margin-top:3px}
.bar{height:9px;border-radius:5px;background:#e5e7eb;overflow:hidden;margin-top:6px}
.bar>i{display:block;height:100%}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--card)}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#eef2f7;font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-left-width:5px;border-radius:10px;
padding:14px 17px;margin:12px 0}
.card.g1{border-left-color:var(--g1)}.card.g2{border-left-color:var(--g2)}.card.g3{border-left-color:var(--g3)}
.card .top{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;margin-bottom:8px}
.card .co{font-size:16px;font-weight:700}
.badge{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);
background:#f3f4f6;color:#374151;white-space:nowrap}
.b-p1{background:#fee2e2;color:var(--p1);border-color:#fecaca}
.b-p2{background:#ffedd5;color:var(--p2);border-color:#fed7aa}
.b-p3{background:#fef9c3;color:var(--p3);border-color:#fde68a}
.b-p4{background:#f3f4f6;color:var(--p4)}
.b-hi{background:#dcfce7;color:#166534;border-color:#bbf7d0}
.b-mid{background:#fef9c3;color:#854d0e;border-color:#fde68a}
.b-low{background:#f3f4f6;color:#6b7280}
.b-ok{background:#dcfce7;color:#166534;border-color:#bbf7d0}
.b-exp{background:#fee2e2;color:#991b1b;border-color:#fecaca}
.b-out{background:#f3f4f6;color:var(--out)}
.f-out{opacity:.62}
.f-out .co{color:var(--out)}
.rel{background:#f8fafc;border:1px dashed var(--line);border-radius:8px;padding:9px 11px;margin-top:8px;font-size:13px}
.rel b{color:var(--mut)}
.src{font-size:12px;word-break:break-all;margin-top:7px}
.src a{color:var(--link)}
.ctrl{position:sticky;top:0;z-index:20;background:rgba(246,247,249,.96);backdrop-filter:blur(4px);
border:1px solid var(--line);border-radius:10px;padding:11px 13px;margin:14px 0;
display:flex;flex-wrap:wrap;gap:9px;align-items:center}
.ctrl input,.ctrl select{padding:6px 9px;border:1px solid var(--line);border-radius:7px;font-size:13px;background:#fff}
.ctrl input[type=search]{min-width:210px}
.ctrl .cnt{color:var(--mut);font-size:12.5px;margin-left:auto}
ul{margin:8px 0 8px 20px;padding:0}li{margin:5px 0}
.warn{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:11px 13px;font-size:13px}
.tip{color:var(--mut);font-size:12.5px}
.hl{background:#dcfce7;border:1px solid #bbf7d0;border-radius:10px;padding:13px 16px;margin:12px 0}
@media print{.ctrl{display:none}.card{break-inside:avoid}}
"""

JS = """
function flt(){
  var g=document.getElementById('f-g').value,
      r=document.getElementById('f-r').value,
      c=document.getElementById('f-c').value,
      t=document.getElementById('f-t').value,
      q=(document.getElementById('f-q').value||'').trim().toLowerCase(),
      n=0;
  document.querySelectorAll('#cards .card').forEach(function(el){
    var ok=(g===''||el.dataset.g===g)&&(r===''||el.dataset.r===r)&&
           (c===''||el.dataset.c===c)&&(t===''||el.dataset.t===t)&&
           (q===''||el.dataset.q.indexOf(q)>=0);
    el.style.display=ok?'':'none'; if(ok)n++;
  });
  document.querySelectorAll('.grp').forEach(function(sec){
    var vis=sec.querySelectorAll('#cards .card:not([style*="none"])').length;
    sec.style.display=vis?'':'none';
    var s=sec.querySelector('.gcnt'); if(s)s.textContent=vis+' 条';
  });
  var o=document.getElementById('cnt'); if(o)o.textContent='显示 '+n+' / '+TOTAL+' 条';
}
var TOTAL=0;
window.addEventListener('DOMContentLoaded',function(){
  TOTAL=document.querySelectorAll('#cards .card').length;
  ['f-g','f-r','f-c','f-t','f-q'].forEach(function(id){
    var e=document.getElementById(id); e.addEventListener('input',flt); e.addEventListener('change',flt);
  });
  flt();
});
"""


def esc(x):
    return html.escape(str(x if x is not None else ""), quote=True)


def links(field):
    urls = R.extract_urls(field)
    if not urls:
        return '<span class="badge b-low">未核实（无原文链接）</span>'
    out = []
    for i, u in enumerate(urls, 1):
        host = u.split("/")[2] if "//" in u else u
        label = "原文" if len(urls) == 1 else "原文%d" % i
        out.append('<a href="%s" target="_blank" rel="noopener">%s · %s</a>' % (esc(u), label, esc(host)))
    return '<div class="src">' + "<br>".join(out) + "</div>"


def conf_badge(c):
    k = {R.CONF_HIGH: "b-hi", R.CONF_MID: "b-mid"}.get(c, "b-low")
    return '<span class="badge %s">置信度 %s</span>' % (k, esc(c))


def fresh_badge(t):
    k = {R.FRESH_OK: "b-ok", R.FRESH_EXPIRED: "b-exp"}.get(t, "b-low")
    return '<span class="badge %s">%s</span>' % (k, esc(t))


def pri_badge(p):
    k = "b-p1" if p.startswith("P1") else "b-p2" if p.startswith("P2") else "b-p3" if p.startswith("P3") else "b-p4"
    return '<span class="badge %s">%s</span>' % (k, esc(p))


def card_html(r, cfg):
    gclass = {R.GROUP_EXPLICIT: "g1", R.GROUP_CAPACITY: "g2", R.GROUP_OTHER: "g3"}.get(r["分组"], "g3")
    outside = r.get("区域") == cfg["region"].get("out_label", "区外")
    qblob = " ".join(str(r.get(k, "")) for k in
                     ("公司", "事件类型", "细分行业", "省市", "事件产品", "数量/规模", "与我产品的关系")).lower()
    h = ['<div class="card %s%s" data-g="%s" data-r="%s" data-c="%s" data-t="%s" data-q="%s">'
         % (gclass, " f-out" if outside else "", esc(r["分组"]), esc(r.get("分组")),
            esc(r["置信度"]), esc(r["时效性"]), esc(qblob))]
    h.append('<div class="top"><span class="co">%s</span>%s%s%s%s%s</div>' % (
        esc(r["公司"]), pri_badge(str(r["优先级"])), conf_badge(r["置信度"]),
        fresh_badge(r["时效性"]),
        '<span class="badge">%s</span>' % esc(r["事件类型"]) if r.get("事件类型") else "",
        '<span class="badge b-out">区外</span>' if outside else ""))
    meta = []
    if r.get("省市"):
        meta.append("地区：%s" % esc(r["省市"]))
    if r.get("细分行业"):
        meta.append("行业：%s" % esc(r["细分行业"]))
    if r.get("发布日"):
        meta.append("发布：%s" % esc(r["发布日"]))
    meta.append("截止：%s" % (esc(r["截止日"]) if r.get("截止日") else "—"))
    meta.append("优先级分：%s（强度 %s★）" % (esc(r.get("优先级分", "")), esc(r.get("用量强度", ""))))
    if r.get("信号方向"):
        meta.append("信号方向：<b>%s</b>" % esc(r["信号方向"]))
    h.append('<div class="tip">%s</div>' % " ｜ ".join(meta))
    if r.get("事件产品"):
        h.append('<div style="margin-top:7px"><b>涉及产品：</b>%s</div>' % esc(r["事件产品"]))
    if r.get("数量/规模"):
        h.append('<div><b>数量/规模：</b>%s</div>' % esc(r["数量/规模"]))
    if r.get("与我产品的关系"):
        h.append('<div class="rel"><b>与我产品的关系：</b>%s</div>' % esc(r["与我产品的关系"]))
    if r.get("来源备注"):
        h.append('<div class="tip">备注：%s</div>' % esc(r["来源备注"]))
    h.append(links(r.get("证据来源")))
    h.append("</div>")
    return "".join(h)


def bar(label, n, total, color):
    pct = (100.0 * n / total) if total else 0
    return ('<div><div style="display:flex;justify-content:space-between;font-size:13px">'
            '<span>%s</span><b>%d</b></div><div class="bar"><i style="width:%.1f%%;background:%s"></i>'
            '</div></div>' % (esc(label), n, pct, color))


def main():
    cfg, base, _ = R.resolve_config()
    kept = R.read_json(os.path.join(base, "leads.json"), []) or []
    dropped = R.read_json(os.path.join(base, "剔除记录.json"), []) or []
    notes = R.read_json(os.path.join(base, "report_notes.json"), {}) or {}
    qa = R.read_json(os.path.join(R.rawdir(base), "_qa_report.json"), {}) or {}
    if not kept:
        sys.exit("leads.json 为空，请先跑 merge_leads.py")

    t, p = cfg["task"], cfg["product"]
    n_all = len(kept)
    P = []
    P.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    P.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    P.append("<title>%s（%s）近期采购商机卡</title><style>%s</style></head><body><div class='wrap'>"
             % (esc(t["product_name"]), esc(t["region_name"]), CSS))
    P.append("<h1>%s（%s）近期采购商机卡</h1>" % (esc(t["product_name"]), esc(t["region_name"])))
    P.append('<div class="sub">基准日 %s ｜ 检索窗口 %s ~ %s ｜ 结果 %d 条（已剔除 %d 条）</div>'
             % (esc(t["baseline_date"]), esc(t["window_start"]), esc(t["window_end"]), n_all, len(dropped)))

    P.append('<div class="box"><div class="kv">')
    P.append("<b>销售产品</b><span>%s　%s</span>" % (esc(t["product_name"]), esc(t.get("product_spec", ""))))
    P.append("<b>同义/检索名</b><span>%s</span>" % esc("、".join(p.get("aliases", []))))
    P.append("<b>目标市场</b><span>%s（%s）</span>" % (esc(t["region_name"]),
                                                 esc("、".join(cfg["region"].get("provinces", [])))))
    P.append("<b>最小订单规模</b><span>%s</span>" % esc(t["min_order"]))
    P.append("<b>结果构成</b><span>明确采购/招标 %d ｜ 扩产或复产需求 %d ｜ 其他潜在需求信号 %d</span>"
             % (sum(1 for r in kept if r["分组"] == R.GROUP_EXPLICIT),
                sum(1 for r in kept if r["分组"] == R.GROUP_CAPACITY),
                sum(1 for r in kept if r["分组"] == R.GROUP_OTHER)))
    P.append("</div></div>")

    # ---- 概览
    P.append("<h2>一、结果概览</h2><div class='grid'>")
    stats = [("商机卡总数", n_all, "#1f4e79"),
             ("明确采购/招标", sum(1 for r in kept if r["分组"] == R.GROUP_EXPLICIT), "#15803d"),
             ("扩产或复产需求", sum(1 for r in kept if r["分组"] == R.GROUP_CAPACITY), "#a16207"),
             ("其他潜在需求信号", sum(1 for r in kept if r["分组"] == R.GROUP_OTHER), "#1d4ed8"),
             ("华东内", sum(1 for r in kept if r.get("区域") == cfg["region"].get("in_label", "本区")), "#374151"),
             ("高置信度", sum(1 for r in kept if r["置信度"] == R.CONF_HIGH), "#15803d"),
             ("仍可参与", sum(1 for r in kept if r["时效性"] == R.FRESH_OK), "#b91c1c"),
             ("被剔除", len(dropped), "#6b7280")]
    for l, n, c in stats:
        P.append('<div class="stat"><div class="n" style="color:%s">%d</div><div class="l">%s</div></div>'
                 % (c, n, esc(l)))
    P.append("</div>")

    P.append('<div class="box"><h3 style="margin-top:0">分布</h3><div class="grid">')
    for title, ctr, color in [("按优先级", Counter(r["优先级"] for r in kept), "#1d4ed8"),
                              ("按置信度", Counter(r["置信度"] for r in kept), "#15803d"),
                              ("按省份", Counter(str(r["省市"]).split("（")[0].split("/")[0][:10] for r in kept), "#a16207"),
                              ("按时效性", Counter(r["时效性"] for r in kept), "#b91c1c")]:
        P.append('<div><b style="font-size:13px">%s</b>' % esc(title))
        for k, v in ctr.most_common(6):
            P.append(bar(k, v, n_all, color))
        P.append("</div>")
    P.append("</div>")
    if qa.get("抽样数"):
        P.append('<div class="tip">链接抽检：抽 %s 条，可达 %s 条（%s）%s</div>' % (
            esc(qa.get("抽样数")), esc(qa.get("可达数")), esc(qa.get("可达率")),
            "；另有 %s 条属反爬拦截、需人工复核（浏览器多半能打开）" % esc(qa.get("反爬拦截数"))
            if qa.get("反爬拦截数") else ""))
    P.append("</div>")

    hl = notes.get("highlights") or []
    if hl:
        P.append('<div class="hl"><h3 style="margin-top:0">先打这几家</h3><ul>')
        for x in hl:
            P.append("<li><b>%s</b> —— %s</li>" % (esc(x.get("company", "")), esc(x.get("why", ""))))
        P.append("</ul></div>")

    cb = notes.get("confidence_basis") or []
    P.append("<h2>二、置信度分级依据</h2>")
    if cb:
        P.append("<table><tr><th style='width:70px'>置信度</th><th>判定标准</th></tr>")
        for x in cb:
            P.append("<tr><td><b>%s</b></td><td>%s</td></tr>" % (esc(x.get("level", "")), esc(x.get("criterion", ""))))
        P.append("</table>")
    else:
        P.append('<div class="warn">未提供 <code>report_notes.json</code> 的 confidence_basis，'
                 "请补上——高置信度靠什么证据支撑，是这份报告必须交代的内容。</div>")
    P.append('<div class="box"><h3 style="margin-top:0">六道闸门（过滤规则）</h3><ul>')
    P.append("<li><b>R1 同行闸门</b>：自己也生产%s的公司是同行、不是客户，一律剔除。名单：%s。"
             "<b>反向用法</b>：同行检修/停产/降负荷＝供给收紧＝我方补货窗口，归入其他信号并标【利好】。</li>"
             % (esc(t["product_name"]), esc("、".join(cfg["peers"].get("names", [])))))
    rev = cfg["peers"].get("role_reversal", {})
    for key, label in (("customer_not_peer", "⚠ 名字像同行、实际是买方（要留作客户）"),
                       ("peer_not_customer", "⚠ 名字像客户、实际是同行（必须剔除）")):
        if rev.get(key):
            P.append("<li><b>%s</b>：%s</li>" % (label, esc("；".join(
                "%s —— %s" % (x["name"], x["why"]) for x in rev[key]))))
    P.append("<li><b>R2 产品错配</b>：%s</li>" % esc("；".join(
        "%s（%s）" % (x["term"], x.get("reason", "")) if isinstance(x, dict) else str(x)
        for x in cfg["gates"].get("mismatch_terms", []))))
    P.append("<li><b>R3 地域闸门</b>：区外信号保留但标注『%s』并灰置，不删除。</li>"
             % esc(cfg["region"].get("out_label", "区外")))
    P.append("<li><b>R4 时间闸门</b>：发布日须落在 %s ~ %s；更早但截止日仍在未来的招标保留并标『仍可参与』。</li>"
             % (esc(t["window_start"]), esc(t["window_end"])))
    P.append("<li><b>R5 相关性闸门</b>：『与我产品的关系』必须写清用量逻辑＋量级估算，写空话不收。</li>")
    P.append("<li><b>R6 证据闸门</b>：证据必须是真实抓取到的链接；抓不到则标『未核实』＋低置信度并单列。"
             "<b>严禁编造 URL、标题、企业名。</b></li>")
    P.append("</ul>")
    if cfg.get("tonnage"):
        P.append("<h3>用量强度与吨耗表（量级估算依据）</h3>")
        P.append("<table><tr><th>下游行业</th><th>吨耗系数</th><th>单位</th><th>依据</th><th>强度</th></tr>")
        for row in cfg["tonnage"]:
            P.append("<tr><td>%s</td><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s★</td></tr>" % (
                esc(row.get("industry", "")), esc(row.get("coefficient", "")), esc(row.get("unit", "")),
                esc(row.get("basis", "")), esc(row.get("strength", ""))))
        P.append("</table>")
        P.append('<div class="tip">系数是估算，条目里已标『（估算）』。要核实请向企业采购部电话确认月度用量。</div>')
    P.append("</div>")

    # ---- 筛选条 + 卡片
    groups = [(R.GROUP_EXPLICIT, "g1"), (R.GROUP_CAPACITY, "g2"), (R.GROUP_OTHER, "g3")]
    gname = {R.GROUP_EXPLICIT: "三、第一组：明确采购 / 招标（有公开采购动作）",
             R.GROUP_CAPACITY: "四、第二组：扩产或复产需求（由生产变化推断）",
             R.GROUP_OTHER: "五、第三组：其他潜在需求信号（更间接）"}
    gdesc = {R.GROUP_EXPLICIT: "这一组是唯一可以直接投标/报价的组。注意区分两种形态："
                              "① 可投标的<b>招标/询价公告</b>；② 定期报告/募集说明书里披露的"
                              "<b>采购量、采购金额、采购均价、年度采购合同</b>——白纸黑字在买，但不是招标文件。",
             R.GROUP_CAPACITY: "对方在扩产、技改、点火、复产或提负荷 → 投产后将形成新的原料需求。"
                              "需求性质是<b>推断</b>，量级靠吨耗系数估算。",
             R.GROUP_OTHER: "更间接的信号：环评公示里的新建项目、同行检修/停产带来的补货窗口、下游景气变化。"
                           "同行检修/停产已在下表用『信号方向』标为【利好】。"}

    P.append('<div class="ctrl">')
    P.append('<select id="f-g"><option value="">全部分组</option>'
             + "".join('<option value="%s">%s</option>' % (esc(g), esc(g)) for g, _ in groups)
             + "</select>")
    P.append('<select id="f-r"><option value="">全部区域</option><option value="%s">只看%s</option>'
             '<option value="%s">只看%s</option></select>' % (
                 esc(cfg["region"].get("in_label", "本区")), esc(cfg["region"].get("in_label", "本区")),
                 esc(cfg["region"].get("out_label", "区外")), esc(cfg["region"].get("out_label", "区外"))))
    P.append('<select id="f-c"><option value="">全部置信度</option><option value="高">只看高</option>'
             '<option value="中">只看中</option><option value="低">只看低</option></select>')
    P.append('<select id="f-t"><option value="">全部时效性</option>'
             '<option value="%s">只看仍可参与</option></select>' % esc(R.FRESH_OK))
    P.append('<input type="search" id="f-q" placeholder="搜索公司 / 产品 / 行业…">')
    P.append('<span class="cnt" id="cnt"></span></div>')

    P.append('<div id="cards">')
    for g, cls in groups:
        rows = [r for r in kept if r["分组"] == g and not (g == R.GROUP_OTHER and r.get("信号方向"))]
        P.append('<div class="grp"><h2>%s <span class="badge gcnt">%d 条</span></h2>'
                 '<div class="tip">%s</div>' % (esc(gname[g]), len(rows), gdesc[g]))
        P.append("".join(card_html(r, cfg) for r in rows) or '<div class="box">本组无条目。</div>')
        P.append("</div>")

    peer_rows = [r for r in kept if r["分组"] == R.GROUP_OTHER and r.get("信号方向")]
    if peer_rows:
        P.append('<h2>六、同行动态与市场信号</h2><div class="tip">同行是竞争对手、不是客户；但它们的'
                 "检修/停产会让供给收紧，对我方是【利好】（补货窗口），扩产则是【利空】。</div>")
        P.append("".join(card_html(r, cfg) for r in peer_rows))
    P.append("</div>")

    # ---- 被剔除的同行
    P.append("<h2>七、被剔除的条目与被剔除的同行</h2>")
    P.append('<div class="box"><h3 style="margin-top:0">被剔除的同行（peer）名单</h3>'
             "<p>自己也生产该产品的公司是同行、不是客户，必须从商机池剔除：</p>")
    pr = [r for r in dropped if "R1" in str(r.get("剔除原因", ""))]
    seen, uniq = set(), []
    for r in pr:
        u = R.extract_urls(r.get("证据来源"))
        k = u[0] if u else "N/" + str(r.get("公司", ""))[:8]
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    if uniq:
        P.append("<table><tr><th>企业</th><th>事件</th><th>发布日</th><th>剔除理由</th><th>证据</th></tr>")
        for r in uniq:
            u = R.extract_urls(r.get("证据来源"))
            P.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                esc(r.get("公司", "")), esc(r.get("事件类型", "")), esc(r.get("发布日", "")),
                esc(r.get("剔除原因", "")),
                ('<a href="%s" target="_blank" rel="noopener">原文</a>' % esc(u[0])) if u else "—"))
        P.append("</table>")
    P.append("</div>")
    P.append('<div class="box"><h3 style="margin-top:0">全部剔除条目（%d 条，逐条可追溯）</h3>' % len(dropped))
    P.append("<table><tr><th style='width:46%'>剔除原因</th><th>公司</th><th>事件类型</th><th>发布日</th></tr>")
    for r in dropped:
        P.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(r.get("剔除原因", "")), esc(r.get("公司", "")), esc(r.get("事件类型", "")),
            esc(r.get("发布日", ""))))
    P.append("</table></div>")

    # ---- 负结果与缺口
    P.append("<h2>八、负结果与覆盖缺口（必须知道的边界）</h2>")
    nr, cg = notes.get("negative_results") or [], notes.get("coverage_gaps") or []
    if nr or cg:
        if nr:
            P.append('<div class="box"><h3 style="margin-top:0">负结果：这些方向查了，是真没有</h3><ul>')
            P.extend("<li>%s</li>" % x for x in nr)
            P.append("</ul></div>")
        if cg:
            P.append('<div class="box"><h3 style="margin-top:0">覆盖缺口：这些地方够不着</h3><ul>')
            P.extend("<li>%s</li>" % x for x in cg)
            P.append("</ul></div>")
    else:
        P.append('<div class="warn">未提供 <code>report_notes.json</code> 的 negative_results / '
                 "coverage_gaps。这一节必须写：哪些行业检索为零、哪些通道不可达、哪些客户只能电话核实——"
                 "不写清楚边界，读者会把「没查到」误当成「没有」。</div>")
    ch = notes.get("channels_used") or []
    if ch:
        P.append('<div class="box"><h3 style="margin-top:0">本轮通道清单</h3>'
                 "<table><tr><th>通道</th><th style='width:90px'>状态</th><th>说明</th></tr>")
        for c in ch:
            cls = "b-ok" if str(c.get("status", "")).startswith("可用") else "b-exp"
            P.append("<tr><td>%s</td><td><span class='badge %s'>%s</span></td><td>%s</td></tr>" % (
                esc(c.get("channel", "")), cls, esc(c.get("status", "")), esc(c.get("note", ""))))
        P.append("</table></div>")

    # ---- 复现
    P.append("<h2>九、怎么换一个产品再跑一遍</h2>")
    P.append('<div class="box"><p>整套流程是 <b>config 驱动</b> 的：唯一需要行业知识的是配置文件，'
             "脚本全部产品无关。</p><ol>"
             "<li>复制 <code>config/product.template.json</code>，填成你的产品（学名/俗名/英文名、"
             "下游应用地图与吨耗系数、同行名单、误配清单、检索词、区域、时间窗）。</li>"
             "<li>按 lane 分头抓数，每个 lane 把结果落成 <code>leads_raw/NN_xxx.json</code>"
             "（字段契约固定 14 项）。</li>"
             "<li>依次运行：<code>merge_leads.py</code> → <code>consolidate.py</code> → "
             "<code>qa_links.py</code> → <code>build_workbook.py</code> → <code>build_html.py</code>；"
             "或者直接 <code>run_all.py</code> 一键跑完。</li>"
             "<li>把负结果、覆盖缺口、通道清单写进 <code>report_notes.json</code>，重跑出 HTML。</li>"
             "</ol><div class='tip'>取数通道与陷阱清单见 <code>references/channels.md</code>；"
             "闸门规则见 <code>references/gates.md</code>；怎么为新化工品建产品画像见 "
             "<code>references/product-profiling.md</code>。</div></div>")

    P.append('<div class="tip" style="margin-top:30px;text-align:center">'
             "本报告由「化工品采购商机雷达」skill 生成 ｜ 所有证据链接均为真实抓取，"
             "未核实项已单列 ｜ 基准日 %s</div>" % esc(t["baseline_date"]))
    P.append("</div><script>%s</script></body></html>" % JS)

    name = "%s%s_采购商机卡.html" % (t["product_name"], t["region_name"])
    out = os.path.join(R.outdir(cfg, base), name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(P))
    print("已写出:", out, "(%d KB)" % (os.path.getsize(out) // 1024))
    print("  卡片数: %d ｜ 剔除条目: %d ｜ 叙事节: %s"
          % (n_all, len(dropped), "有" if (nr or cg) else "缺(report_notes.json)"))


if __name__ == "__main__":
    main()