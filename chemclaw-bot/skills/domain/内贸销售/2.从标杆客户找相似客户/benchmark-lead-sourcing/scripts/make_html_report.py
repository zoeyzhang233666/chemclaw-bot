#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_html_report.py —— 生成单文件 HTML 报告（内联 CSS/JS、零外链、离线可开、可打印成 PDF）

9 节结构固定：0 摘要 / 1 标杆画像 / 2 相似性判据 / 3 应用地图 / 4 潜客池（可搜索+多维筛选）/
5 证据与置信度分级 / 6 被剔除名单 / 7 缺口与负结果 / 8 可复制动作清单

用法： python make_html_report.py --dir <项目> [--out 文件名.html]
"""
import argparse
import datetime
import html
import os
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (bucket_of, load_json, load_project, norm_dims,  # noqa: E402
                     province_of, urls_of, setup_console)

setup_console()

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)  # noqa: E731
PRIO_CLASS = {"高": "p-high", "中": "p-mid", "低": "p-low"}
CONF_CLASS = {"高": "c-high", "中": "c-mid", "低": "c-low"}


def linkify(source):
    out = []
    for u in urls_of(source):
        out.append(f'<a href="{E(u)}" target="_blank" rel="noopener">{E(u)}</a>')
    txt = E(source)
    return "<br>".join(out) if out else txt


def table_html(headers, rows, cls="tbl", raw_cols=()):
    h = "".join(f"<th>{E(x)}</th>" for x in headers)
    body = []
    for row in rows:
        tds = []
        for i, v in enumerate(row):
            tds.append(f"<td>{v if i in raw_cols else E(v)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<table class="{cls}"><thead><tr>{h}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def bars(pairs, total):
    out = []
    for name, n in pairs:
        pct = (n / total * 100) if total else 0
        out.append(f'<div class="bar"><span class="bar-label">{E(name)}</span>'
                   f'<span class="bar-fill" style="width:{pct:.1f}%"></span>'
                   f'<span class="bar-num">{n}</span></div>')
    return "".join(out)


def build(cfg, leads, profile, notes):
    p = cfg["product"]
    rep = cfg["report"]
    reg = cfg.get("region", {})
    provs = reg.get("provinces") or []
    pname = rep.get("product_short") or p["name"]
    bname = rep.get("benchmark_name") or cfg.get("benchmark", {}).get("name") or "标杆客户"

    n_all = len(leads)
    n_hi = sum(1 for x in leads if x.get("置信度") == "高")
    n_mid = sum(1 for x in leads if x.get("置信度") == "中")
    n_low = sum(1 for x in leads if x.get("置信度") == "低")
    n_prio = sum(1 for x in leads if x.get("优先级") == "高")
    n_cninfo = sum(1 for x in leads if "cninfo" in x.get("来源", ""))
    n_mark = sum(1 for x in leads if "⚠" in x.get("来源", ""))
    n_nosrc = sum(1 for x in leads if x.get("来源") in ("", "未核实"))
    blk = Counter(x.get("板块", "") for x in leads)
    prov = Counter(province_of(x.get("所在地", ""), provs) for x in leads)
    dims = Counter()
    for x in leads:
        for d in norm_dims(x.get("相似维度"), cfg):
            dims[d] += 1
    dim_order = [d.get("name") for d in (cfg.get("similarity_dimensions") or [])] or \
                ["产品结构", "工艺路线", "下游市场", "规模", "产业链位置"]

    # ---------------- 0 摘要
    s0 = [f'<div class="kpis">'
          f'<div class="kpi"><b>{n_all}</b><span>潜在客户（条）</span></div>'
          f'<div class="kpi"><b>{n_prio}</b><span>高优先级</span></div>'
          f'<div class="kpi"><b>{n_hi}</b><span>高置信度</span></div>'
          f'<div class="kpi"><b>{len(blk)}</b><span>行业板块</span></div>'
          f'<div class="kpi"><b>{len([k for k in prov if k != "未标注"])}</b><span>省级地区</span></div>'
          f'</div>']
    s0.append(f'<p class="lead">本批共交付 <b>{n_all}</b> 家{reg.get("label") or ""}潜在下游客户，'
              f'全部按「与标杆客户 {E(bname)} 业务特征相似 → 因而产生同类{pname}需求」的逻辑筛出。'
              f'每条线索都写明相似点落在哪一项、以及这种相似为什么带来相似的原料需求。'
              f'证据置信度：高 {n_hi} / 中 {n_mid} / 低 {n_low}；其中 {n_cninfo} 家直接引用上市公司公告原文作为用料证据。</p>')
    if rep.get("headline_facts"):
        s0.append('<p class="lead"><b>标杆的三个硬事实：</b>' +
                  "；".join(E(x) for x in rep["headline_facts"]) + '。</p>')

    # ---------------- 1 画像
    prof_rows = [[f.get("特征项", ""), f.get("内容", ""),
                  linkify(f.get("证据", "")) if urls_of(f.get("证据", "")) else E(f.get("证据", ""))]
                 for f in (profile.get("关键业务特征") or [])]
    s1 = []
    if profile.get("主体信息"):
        s1.append(table_html(["主体信息", "内容"],
                             [[k, v] for k, v in profile["主体信息"].items()]))
    s1.append(table_html(["关键业务特征（六要素）", "内容", "证据（可点开复核）"],
                         prof_rows, raw_cols=(2,)))

    # ---------------- 2 相似性判据
    sim_rows = [[d.get("维度", ""), d.get("判据", ""), d.get("为什么带来相似原料需求", "")]
                for d in (profile.get("可复制的相似性判据") or [])]
    s2 = [table_html(["相似维度", "判据（相似点落在哪一项）", "为什么相似 → 相似原料需求"], sim_rows)]
    s2.append('<h3>本批线索按相似维度的命中分布</h3>')
    s2.append(bars([(k, dims.get(k, 0)) for k in dim_order], sum(dims.values())))

    # ---------------- 3 行业地图
    s3 = [table_html(["行业板块", "细分方向", "用料逻辑 / 工序", "用量强度", "采购与开发要点"],
                     cfg.get("industry_map") or [])]

    # ---------------- 4 潜客池
    s4 = ['<h3>板块分布</h3>',
          table_html(["行业板块", "线索数", "其中高优先级"],
                     [[b, n, sum(1 for x in leads if x.get("板块") == b and x.get("优先级") == "高")]
                      for b, n in blk.most_common()])]
    s4.append('<h3>省份分布</h3>' +
              bars([(k, v) for k, v in prov.most_common()], n_all))

    top = sorted([x for x in leads if x.get("优先级") == "高"], key=lambda x: (x.get("板块", ""), x.get("公司", "")))
    if top:
        s4.append(f'<h3>重点客户（高优先级 {len(top)} 家，建议首批外呼）</h3>')
        s4.append(table_html(
            ["公司", "所在地", "细分行业", "用量强度", "相似维度", "用碱/用料工序", "置信度"],
            [[f'<b>{E(x.get("公司"))}</b>', x.get("所在地", ""), x.get("细分行业", ""),
              x.get("用量强度", ""), x.get("相似维度", ""), x.get("需求点", ""),
              f'<span class="tag {CONF_CLASS.get(x.get("置信度"), "")}">{E(x.get("置信度"))}</span>']
             for x in top], raw_cols=(0, 6)))

    # 全量可筛选表
    blocks = ["全部"] + [b for b, _ in blk.most_common()]
    provs_list = ["全部"] + [k for k in prov if k != "未标注"]
    dims_list = ["全部"] + dim_order
    rows = []
    for i, x in enumerate(sorted(leads, key=lambda y: (y.get("板块", ""), {"高": 0, "中": 1, "低": 2}.get(y.get("优先级", "中"), 3), y.get("公司", ""))), 1):
        dset = norm_dims(x.get("相似维度"), cfg)
        search = " ".join([str(x.get("公司", "")), str(x.get("细分行业", "")), str(x.get("需求点", "")),
                           str(x.get("相似逻辑", "")), str(x.get("规模线索", "")), str(x.get("所在地", ""))]).lower()
        rows.append(
            f'<tr class="row" data-block="{E(x.get("板块", ""))}" '
            f'data-prov="{E(province_of(x.get("所在地", ""), provs))}" '
            f'data-prio="{E(x.get("优先级", "中"))}" data-conf="{E(x.get("置信度", "中"))}" '
            f'data-dims="{E("|".join(sorted(dset)))}" data-text="{E(search)}">'
            f'<td>{i}</td><td>{E(x.get("板块"))}</td><td>{E(x.get("细分行业"))}</td>'
            f'<td class="co">{E(x.get("公司"))}</td><td>{E(x.get("所在地"))}</td>'
            f'<td class="ctr">{E(x.get("用量强度"))}</td>'
            f'<td class="wrap">{E(x.get("需求点"))}</td>'
            f'<td class="wrap">{E(x.get("相似维度"))}</td>'
            f'<td class="wrap">{E(x.get("相似逻辑"))}</td>'
            f'<td class="wrap">{E(x.get("规模线索"))}</td>'
            f'<td class="ctr"><span class="tag {PRIO_CLASS.get(x.get("优先级"), "")}">{E(x.get("优先级"))}</span></td>'
            f'<td class="ctr"><span class="tag {CONF_CLASS.get(x.get("置信度"), "")}">{E(x.get("置信度"))}</span></td>'
            f'<td class="src">{linkify(x.get("来源"))}</td></tr>')

    s4.append('<h3 id="all">全量线索（可搜索 / 多维筛选）</h3>')
    s4.append(f'''<div class="filters no-print">
  <input id="q" type="search" placeholder="搜索公司 / 工序 / 相似逻辑 / 规模…">
  <select id="f-block">{''.join(f'<option>{E(b)}</option>' for b in blocks)}</select>
  <select id="f-prov">{''.join(f'<option>{E(b)}</option>' for b in provs_list)}</select>
  <select id="f-prio">{''.join(f'<option>{E(b)}</option>' for b in ["全部", "高", "中", "低"])}</select>
  <select id="f-conf">{''.join(f'<option>{E(b)}</option>' for b in ["全部", "高", "中", "低"])}</select>
  <select id="f-dim">{''.join(f'<option>{E(b)}</option>' for b in dims_list)}</select>
  <button id="reset" type="button">重置</button>
  <span id="count"></span>
</div>''')
    s4.append('<table class="tbl leads" id="leads"><thead><tr>'
              + "".join(f"<th>{E(h)}</th>" for h in
                        ["#", "板块", "细分行业", "公司", "所在地", "用量强度", "用料工序（需求点）",
                         "相似维度（相似点落在哪一项）", "为什么会产生相似原料需求", "规模线索",
                         "优先级", "置信度", "线索来源"])
              + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")

    # ---------------- 5 证据分级
    s5 = [table_html(["置信度", "判定标准", "电话里怎么用", "本批条数"],
                     [["高", "上市公司公告原文（年报/招股书/可研/募集说明书/问询函）或企业官网明确写明采购或使用该原料",
                       "可直接复述：贵司在XX公告里提到……", n_hi],
                      ["中", "主体与业务板块已核实，用料环节由该品类工艺必然推导",
                       "先确认工艺与品种，不要说成对方披露过", n_mid],
                      ["低", "主体或用料环节均未核到证据，仅行业归属明确", "只作为拜访线索，先电话核实", n_low]])]
    notes_txt = []
    if n_nosrc:
        notes_txt.append(f"本批 {n_nosrc} 条来源为「未核实」，属待电话确认线索。")
    if n_mark:
        notes_txt.append(f"{n_mark} 条链接抽检未通过（已标注 ⚠），公司信息可用但请勿直接引用链接。")
    notes_txt.append(f"共 {n_all} 条线索已通过五道 gate（trace / subject / peer / link / dedup）；"
                     f"{n_cninfo} 条以公告原文为证据。")
    if rep.get("evidence_note"):
        notes_txt.append(str(rep["evidence_note"]))
    if rep.get("boundary_note"):
        notes_txt.append(str(rep["boundary_note"]))
    s5.append("<ul>" + "".join(f"<li>{E(t)}</li>" for t in notes_txt) + "</ul>")

    # ---------------- 6 被剔除名单
    s6 = []
    for title, key, hint in (("6.1 同行（peer gate）：自己也生产该产品，属竞争对手", "peers",
                              "华东/目标区域是主产区时，这一步尤其必要——否则名单里会混进同行的销售部。"),
                             ("6.2 工艺不符：看似同类，实际不用该产品", "process_mismatch",
                              "工商门类相同但工艺路线不用该原料的企业，必须剔除。"),
                             ("6.3 弱相似或主体风险（已剔除/降级）", "weak_excluded",
                              "只命中单一弱维度、或主体存在停产/重整等风险的，剔除或降级并说明。")):
        items = notes.get(key) or []
        s6.append(f"<h3>{E(title)}</h3>")
        if hint:
            s6.append(f'<p class="hint">{E(hint)}</p>')
        s6.append("<ul>" + ("".join(f"<li>{E(x)}</li>" for x in items) or "<li>（无）</li>") + "</ul>")

    # ---------------- 7 缺口
    s7 = ['<h3>7.1 未覆盖的缺口</h3>',
          "<ul>" + ("".join(f"<li>{E(x)}</li>" for x in (notes.get("gaps") or [])) or "<li>（无）</li>") + "</ul>",
          '<h3>7.2 负结果（检索为零 / 通道受限）</h3>',
          "<ul>" + ("".join(f"<li>{E(x)}</li>" for x in (notes.get("negatives") or [])) or "<li>（无）</li>") + "</ul>"]

    # ---------------- 8 SOP
    steps = rep.get("sop_steps") or [
        f"外呼前先读第 1 节画像，记住{E(bname)}的几个硬事实。",
        "优先打用量强度 5 星的板块。",
        "用同工序切入，先测算客户年用量再谈价格。",
        "对置信度「中」的客户，先问品种与月用量，再定档报价。",
        "参照标杆的商务条件（长协锁量 + 分月到货）设计报价。",
        "园区内横向复制：同一集聚地的同类厂一次性扫完。",
    ]
    s8 = ["<ol class='sop'>" + "".join(f"<li>{E(x)}</li>" for x in steps) + "</ol>"]
    if rep.get("sales_script"):
        s8.append(f'<div class="script"><b>复制话术：</b>{E(rep["sales_script"])}</div>')

    secs = [("0", "一页摘要", s0), ("1", f"标杆客户画像：{bname}", s1),
            ("2", "相似性判据：相似点落在哪一项，为什么带来相似原料需求", s2),
            ("3", f"{pname}应用地图与 lane 设计", s3), ("4", "第二批潜客池", s4),
            ("5", "证据与置信度分级", s5), ("6", "被剔除的名单（三道否决 gate）", s6),
            ("7", "未覆盖的缺口与负结果", s7), ("8", "可复制动作清单（把标杆经验复制到第二批）", s8)]

    toc = "".join(f'<a href="#s{i}">{i}. {E(t)}</a>' for i, t, _ in secs)
    body = "".join(f'<section id="s{i}"><h2>{i}. {E(t)}</h2>{"".join(c)}</section>'
                   for i, t, c in secs)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(rep["title"])}</title>
<style>
:root{{--ink:#1f2937;--sub:#6b7280;--line:#e5e7eb;--accent:#2f5597;--bg:#f8fafc;
--high:#c2410c;--mid:#a16207;--low:#4b5563;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.7 "Microsoft YaHei","PingFang SC","Hiragino Sans GB",system-ui,sans-serif}}
header{{background:linear-gradient(135deg,#1f3864,#2f5597);color:#fff;padding:28px 32px}}
header h1{{margin:0 0 6px;font-size:24px}}
header .sub{{opacity:.85;font-size:13px}}
nav{{background:#fff;border-bottom:1px solid var(--line);padding:10px 32px;position:sticky;top:0;
z-index:9;display:flex;flex-wrap:wrap;gap:14px;font-size:13px}}
nav a{{color:var(--accent);text-decoration:none}}
nav a:hover{{text-decoration:underline}}
main{{max-width:1500px;margin:0 auto;padding:24px 32px 64px}}
section{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:20px 24px;margin:18px 0}}
h2{{font-size:19px;margin:0 0 14px;color:#1f3864;border-left:4px solid var(--accent);padding-left:10px}}
h3{{font-size:15px;margin:20px 0 8px;color:#1f3864}}
p.lead{{margin:8px 0}}
.hint{{color:var(--sub);font-size:13px;margin:4px 0 8px}}
table.tbl{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}}
table.tbl th{{background:var(--accent);color:#fff;text-align:left;padding:8px 10px;position:relative}}
table.tbl td{{border:1px solid var(--line);padding:7px 10px;vertical-align:top}}
table.tbl tbody tr:nth-child(even){{background:#fbfcfe}}
table.leads td.wrap{{min-width:180px}}
table.leads td.src{{font-size:11px;word-break:break-all;max-width:260px}}
table.leads td.co{{font-weight:600}}
td.ctr,.ctr{{text-align:center;white-space:nowrap}}
.kpis{{display:flex;flex-wrap:wrap;gap:12px;margin:6px 0 14px}}
.kpi{{background:#eef2fa;border:1px solid #dbe3f4;border-radius:8px;padding:10px 16px;min-width:120px}}
.kpi b{{display:block;font-size:22px;color:var(--accent)}}
.kpi span{{font-size:12px;color:var(--sub)}}
.bar{{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:13px}}
.bar-label{{width:110px;flex:none;text-align:right;color:var(--sub)}}
.bar-fill{{height:14px;background:linear-gradient(90deg,#2f5597,#7fa6dd);border-radius:3px}}
.bar-num{{color:var(--sub)}}
.tag{{display:inline-block;padding:1px 7px;border-radius:10px;font-size:12px;color:#fff}}
.p-high{{background:var(--high)}} .p-mid{{background:var(--mid)}} .p-low{{background:var(--low)}}
.c-high{{background:#15803d}} .c-mid{{background:#a16207}} .c-low{{background:#6b7280}}
.filters{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0;font-size:13px}}
.filters input,.filters select,.filters button{{padding:5px 8px;border:1px solid var(--line);
border-radius:6px;font-size:13px;background:#fff}}
.filters input{{min-width:260px}}
.filters button{{cursor:pointer;background:#eef2fa}}
#count{{color:var(--sub)}}
ol.sop li{{margin:6px 0}}
.script{{background:#f2f8f2;border-left:4px solid #15803d;padding:10px 14px;border-radius:6px;margin-top:10px}}
footer{{color:var(--sub);font-size:12px;text-align:center;padding:18px}}
@media print{{
 nav,.filters,.no-print{{display:none!important}}
 body{{background:#fff}} section{{break-inside:avoid;border:none;padding:0 0 10px;margin:10px 0}}
 header{{background:#1f3864!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
 table.tbl{{font-size:11px}} a{{color:var(--ink);text-decoration:none}}
}}
</style></head>
<body>
<header><h1>{E(rep["title"])}</h1>
<div class="sub">标杆客户：{E(bname)}　|　产品：{E(p["name"])}
{f'（{E(p["grades"])}）' if p.get("grades") else ''}　|　目标区域：{E(reg.get("label") or "")}
{('（' + "、".join(provs) + '）') if provs else ''}　|　生成时间：{now}</div></header>
<nav>{toc}</nav>
<main>{body}</main>
<footer>本报告由 benchmark-lead-sourcing 技能生成：每条线索均带证据出处；同行、工艺不符与弱相似企业已剔除并列出。
打印本页（Ctrl/Cmd+P）即可另存为 PDF。</footer>
<script>
(function(){{
  var q=document.getElementById('q'),fB=document.getElementById('f-block'),
      fP=document.getElementById('f-prov'),fR=document.getElementById('f-prio'),
      fC=document.getElementById('f-conf'),fD=document.getElementById('f-dim'),
      cnt=document.getElementById('count'),rows=[].slice.call(document.querySelectorAll('tr.row'));
  function apply(){{
    var t=(q.value||'').trim().toLowerCase(),n=0;
    rows.forEach(function(r){{
      var ok=(!t||r.dataset.text.indexOf(t)>=0)
        &&(fB.value==='全部'||r.dataset.block===fB.value)
        &&(fP.value==='全部'||r.dataset.prov===fP.value)
        &&(fR.value==='全部'||r.dataset.prio===fR.value)
        &&(fC.value==='全部'||r.dataset.conf===fC.value)
        &&(fD.value==='全部'||(r.dataset.dims||'').split('|').indexOf(fD.value)>=0);
      r.style.display=ok?'':'none'; if(ok)n++;
    }});
    cnt.textContent='命中 '+n+' / '+rows.length+' 条';
  }}
  [q,fB,fP,fR,fC,fD].forEach(function(el){{el.addEventListener('input',apply);el.addEventListener('change',apply);}});
  document.getElementById('reset').addEventListener('click',function(){{
    q.value='';[fB,fP,fR,fC,fD].forEach(function(s){{s.value='全部';}});apply();}});
  apply();
}})();
</script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    d = os.path.abspath(args.dir)
    cfg = load_project(d)
    leads = load_json(os.path.join(d, "leads.json"), [])
    if not leads:
        raise SystemExit("leads.json 为空或不存在，先跑 merge_leads.py")
    profile = load_json(os.path.join(d, cfg.get("benchmark", {}).get("profile_file")
                                     or "benchmark_profile.json"), {})
    notes = load_json(os.path.join(d, "report_notes.json"), {})
    out = os.path.join(d, args.out or cfg["report"].get("html_output") or "报告.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build(cfg, leads, profile, notes))
    size = os.path.getsize(out) / 1024
    print(f"OK 线索={len(leads)} 报告={out}（{size:.0f} KB，单文件零外链）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
