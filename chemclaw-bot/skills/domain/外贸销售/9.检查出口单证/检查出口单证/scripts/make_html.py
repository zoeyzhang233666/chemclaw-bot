# -*- coding: utf-8 -*-
"""生成自包含的交互式检查页（单文件 HTML，内嵌全部数据与逻辑）。

功能：
  * 文件清单：类型自动识别 + 置信度 + 每份单证抽取到的字段
  * 跨文件字段矩阵：一致 / 不一致 / 缺失 / 不适用 / 无法判断 / 计算错误
  * 筛选：只看差异、只看缺失、只看计算错误、按字段分组、按单证
  * 单元格点击 → 展示原文上下文 + 页码 + 坐标（定位到 PDF 原文位置）
  * 字段修正 / 标记为已确认 → 重新计算状态，导出问题清单与修正记录
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATUS_CN = {
    "OK": "一致", "DIFF": "不一致", "CALC": "计算不符", "MISS": "缺失",
    "NA": "不适用", "UNK": "无法判断", "MANUAL": "需人工确认",
}
STATUS_ORDER = ["DIFF", "CALC", "MISS", "MANUAL", "UNK", "OK", "NA"]


def _ctx(text, needle, span=90):
    """在原文里定位字段值附近的一段，供"定位原文"使用。"""
    if not text:
        return ""
    if needle:
        key = str(needle).strip()
        for cand in (key, key[:24], key[:16], key[:10]):
            if len(cand) < 3:
                continue
            i = text.find(cand)
            if i >= 0:
                a = max(0, i - span // 2)
                return text[a:i + len(cand) + span // 2]
    return ""


def build(result, out_path):
    docs = result["docs"]
    live = [d for d in docs if not d.get("excluded")]
    refs = [d for d in docs if d.get("excluded")]
    doc_ids = [d["id"] for d in live]

    payload = {
        "run_at": result.get("run_at", ""),
        "anchor": result.get("anchor", {}),
        "summary": result.get("summary", {}),
        "docs": [{"id": d["id"], "type": d["type"], "type_cn": d.get("type_cn", ""),
                  "filename": d["filename"], "pages": d.get("pages", 0),
                  "fields": {k: {"value": v.get("value", ""), "page": v.get("page"),
                                 "source": v.get("source", "")}
                             for k, v in (d.get("fields") or {}).items()},
                  "excluded": bool(d.get("excluded")),
                  "exclude_reason": d.get("exclude_reason", "")}
                 for d in docs],
        "matrix": [], "checks": result.get("checks", []),
        "issues": result.get("issues", []),
        "status_cn": STATUS_CN, "status_order": STATUS_ORDER,
    }

    # 矩阵：附带原文上下文，便于"定位原文件页码及具体字段"
    text_by_id = {d["id"]: d.get("text", "") for d in docs}
    for row in result["matrix"]:
        cells = {}
        for did, c in row["cells"].items():
            cells[did] = {
                "status": c.get("status", "NA"),
                "value": c.get("value", ""),
                "page": c.get("page"),
                "bbox": c.get("bbox"),
                "how": c.get("how", ""),
                "note": c.get("note", ""),
                "ctx": _ctx(text_by_id.get(did, ""), c.get("value", "")),
            }
        payload["matrix"].append({
            "field": row["field"], "cn": row["cn"], "en": row.get("en", ""),
            "group": row.get("group", ""), "kind": row.get("kind", "fact"),
            "unit": row.get("unit", ""), "cells": cells,
        })

    data_js = json.dumps(payload, ensure_ascii=False)
    html = _TEMPLATE.replace("/*__DATA__*/", "const DATA = " + data_js + ";")
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return out_path


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>出口单证交叉检查 · 演示票</title>
<style>
:root{
  --bg:#f6f7f9; --panel:#fff; --line:#e3e6ec; --ink:#1b2330; --mute:#66718a;
  --navy:#1f3a5f; --navy2:#2d5580; --s1:#c0392b; --s2:#d68910; --s3:#7f8c8d;
  --ok:#1e8449; --diff:#c0392b; --miss:#d68910; --na:#aab2c0; --unk:#7d3c98;
  --calc:#b03a2e; --hi:#fff4d6;
}
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
  color:var(--ink);background:var(--bg)}
header{background:var(--navy);color:#fff;padding:14px 22px;display:flex;
  align-items:center;gap:18px;flex-wrap:wrap}
header h1{font-size:17px;margin:0;font-weight:600;letter-spacing:.3px}
header .tag{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);
  padding:2px 9px;border-radius:11px;font-size:12px}
header .spacer{flex:1}
header button{font-size:12.5px;padding:6px 12px;border-radius:6px;border:1px solid #fff5;
  background:rgba(255,255,255,.12);color:#fff;cursor:pointer}
header button:hover{background:rgba(255,255,255,.24)}
main{padding:16px 22px 60px;max-width:1680px;margin:0 auto}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  margin-bottom:16px;overflow:hidden}
.panel>h2{margin:0;padding:11px 16px;font-size:14px;background:#fafbfc;
  border-bottom:1px solid var(--line);font-weight:600;display:flex;
  align-items:center;gap:10px;flex-wrap:wrap}
.panel>h2 .hint{font-weight:400;color:var(--mute);font-size:12.5px}
.panel .body{padding:14px 16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:10px}
.kpi{border:1px solid var(--line);border-radius:8px;padding:9px 12px;background:#fcfdff}
.kpi .n{font-size:22px;font-weight:700;line-height:1.2}
.kpi .l{font-size:12px;color:var(--mute)}
.kpi.diff .n{color:var(--diff)} .kpi.miss .n{color:var(--miss)}
.kpi.ok .n{color:var(--ok)} .kpi.calc .n{color:var(--calc)}
.verdict{margin-top:10px;padding:9px 12px;border-radius:8px;font-size:13.5px;
  background:#fdf3f2;border:1px solid #f3cfcb;color:#8e2b21}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:12.8px}
th,td{border-bottom:1px solid var(--line);padding:7px 9px;text-align:left;
  vertical-align:top}
th{background:#f7f9fb;font-weight:600;position:sticky;top:0;z-index:2;
  white-space:nowrap;font-size:12.4px}
tbody tr:hover td{background:#fbfcfe}
td.rot{white-space:nowrap;font-weight:600;color:var(--navy)}
td.rot .en{display:block;font-weight:400;color:var(--mute);font-size:11.4px}
.cell{cursor:pointer;border-radius:5px;padding:3px 6px;display:block;
  border:1px solid transparent;min-height:22px;word-break:break-word}
.cell:hover{border-color:#b9c6d8;background:#eef4fb}
.cell.sel{border-color:var(--navy);background:var(--hi);box-shadow:0 0 0 2px #1f3a5f22}
.st{display:inline-block;font-size:10.5px;padding:0 5px;border-radius:9px;
  margin-right:4px;vertical-align:1px;font-weight:600;color:#fff}
.st.OK{background:var(--ok)} .st.DIFF{background:var(--diff)}
.st.MISS{background:var(--miss)} .st.NA{background:var(--na)}
.st.UNK{background:var(--unk)} .st.CALC{background:var(--calc)}
.st.MANUAL{background:var(--navy2)}
.cell.NA{color:#b3bcc9} .cell.MISS{color:#9c6f10;font-style:italic}
.cell.DIFF{background:#fdf1f0} .cell.CALC{background:#fdf1f0}
.cell.UNK{background:#f7f0fb}
.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.chip{border:1px solid var(--line);background:#fff;border-radius:14px;
  padding:4px 11px;font-size:12.5px;cursor:pointer;user-select:none}
.chip.on{background:var(--navy);color:#fff;border-color:var(--navy)}
select{font-size:12.5px;padding:4px 8px;border:1px solid var(--line);border-radius:6px;
  background:#fff}
.scroll{max-height:640px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.detail{position:fixed;right:0;top:0;height:100vh;width:min(470px,94vw);
  background:#fff;border-left:1px solid var(--line);box-shadow:-8px 0 26px #1b233018;
  transform:translateX(100%);transition:transform .22s;z-index:50;
  display:flex;flex-direction:column}
.detail.open{transform:none}
.detail .dh{padding:13px 16px;border-bottom:1px solid var(--line);background:#fafbfc}
.detail .dh h3{margin:0;font-size:15px}
.detail .dh .sub{color:var(--mute);font-size:12.5px;margin-top:3px}
.detail .db{padding:14px 16px;overflow:auto;flex:1}
.detail .df{padding:11px 16px;border-top:1px solid var(--line);background:#fafbfc;
  display:flex;gap:8px;flex-wrap:wrap}
.kv{margin-bottom:10px}
.kv .k{font-size:11.6px;color:var(--mute);letter-spacing:.3px}
.kv .v{font-size:13.4px;word-break:break-word}
.orig{background:#f7f9fb;border:1px solid var(--line);border-radius:7px;
  padding:9px 11px;font-family:Consolas,Menlo,monospace;font-size:12.2px;
  white-space:pre-wrap;word-break:break-word;max-height:190px;overflow:auto}
.orig mark{background:#ffe9a8;padding:0 1px}
input[type=text]{width:100%;padding:6px 9px;border:1px solid var(--line);
  border-radius:6px;font-size:13px;font-family:inherit}
button.act{font-size:12.5px;padding:6px 12px;border-radius:6px;border:1px solid var(--line);
  background:#fff;cursor:pointer}
button.act.primary{background:var(--navy);color:#fff;border-color:var(--navy)}
button.act:hover{filter:brightness(.96)}
.peers{width:100%;font-size:12.4px;margin-top:6px}
.peers td{padding:3px 6px;border-bottom:1px dashed var(--line)}
.badge{font-size:11px;padding:1px 7px;border-radius:9px;background:#eef1f5;
  color:var(--mute);margin-left:6px}
.refs{font-size:12.6px;color:var(--mute);padding:10px 16px}
.refs b{color:var(--ink)}
.empty{color:var(--mute);padding:16px;text-align:center;font-size:13px}
.legend{font-size:12px;color:var(--mute);display:flex;gap:12px;flex-wrap:wrap}
.calcrow.fail td{background:#fdf1f0}
.calcrow td.res{font-weight:600}
#toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(80px);
  background:#1b2330;color:#fff;padding:9px 16px;border-radius:8px;font-size:13px;
  opacity:0;transition:.24s;z-index:99;pointer-events:none}
#toast.show{opacity:1;transform:translateX(-50%)}
.docgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:10px}
.doc{border:1px solid var(--line);border-radius:8px;padding:10px 12px;background:#fcfdff}
.doc .t{font-weight:600;font-size:13px}
.doc .f{font-size:11.8px;color:var(--mute);word-break:break-all;margin-top:2px}
.doc .n{font-size:12px;margin-top:7px}
.doc .n b{color:var(--navy);font-size:14px}
</style>
</head>
<body>
<header>
  <h1>出口单证交叉检查</h1>
  <span class="tag">演示票 · 模拟单证</span>
  <span class="tag" id="hticket"></span>
  <span class="spacer"></span>
  <button id="btnIssue">导出问题清单 CSV</button>
  <button id="btnFix">导出修正记录 CSV</button>
  <button id="btnJSON">导出检查结果 JSON</button>
</header>

<main>
  <div class="panel">
    <h2>检查结论 <span class="hint" id="runat"></span></h2>
    <div class="body">
      <div class="kpis" id="kpis"></div>
      <div class="verdict" id="verdict"></div>
      <div class="legend" style="margin-top:10px">
        <span><span class="st OK">一致</span>跨单证取值相同</span>
        <span><span class="st DIFF">不一致</span>取值冲突，须修正或确认</span>
        <span><span class="st MISS">缺失</span>本单证应载明但未识别到</span>
        <span><span class="st CALC">计算不符</span>数量/重量/金额关系不自洽</span>
        <span><span class="st UNK">无法判断</span>表述不可比，需人工核对</span>
        <span><span class="st NA">不适用</span>该单证不要求此字段</span>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>单证清单与自动识别 <span class="hint">点击任一单证可查看其已抽取字段</span></h2>
    <div class="body"><div class="docgrid" id="docgrid"></div></div>
    <div class="refs" id="refs"></div>
  </div>

  <div class="panel">
    <h2>计算关系核验
      <span class="hint">数量×单价=金额、净重↔数量、毛重−净重=皮重、单件净重、体积≤柜容量</span>
    </h2>
    <div class="body" style="padding:0">
      <table><thead><tr><th style="width:70px">编号</th><th>核验项</th>
        <th style="width:210px">说明</th><th style="width:88px">结论</th></tr></thead>
      <tbody id="calcbody"></tbody></table>
    </div>
  </div>

  <div class="panel">
    <h2>跨文件字段核对矩阵
      <span class="hint">点击单元格 → 查看原文定位、其他单证取值，并可直接修正</span>
    </h2>
    <div class="body" style="padding-bottom:0">
      <div class="filters" id="filters"></div>
    </div>
    <div class="body" style="padding-top:0">
      <div class="scroll"><table id="matrix"></table></div>
    </div>
  </div>

  <div class="panel">
    <h2>需要修改 / 人工确认清单 <span class="hint" id="issuehint"></span></h2>
    <div class="body" style="padding:0">
      <div class="scroll" style="max-height:520px">
        <table><thead><tr>
          <th style="width:52px">编号</th><th style="width:56px">级别</th>
          <th style="width:150px">字段</th><th style="width:96px">单证</th>
          <th style="width:150px">当前值</th><th>问题与建议</th>
          <th style="width:96px">定位</th></tr></thead>
        <tbody id="issuebody"></tbody></table>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>人工修正记录 <span class="hint" id="fixhint">修正后会重新计算矩阵状态</span></h2>
    <div class="body" style="padding:0">
      <table><thead><tr><th style="width:52px">#</th><th style="width:150px">字段</th>
        <th style="width:96px">单证</th><th style="width:170px">原值</th>
        <th style="width:170px">修正值</th><th style="width:90px">类型</th>
        <th style="width:150px">时间</th></tr></thead>
      <tbody id="fixbody"><tr><td colspan="7" class="empty">尚无修正记录</td></tr></tbody></table>
    </div>
  </div>
</main>

<div class="detail" id="detail">
  <div class="dh">
    <h3 id="dTitle">字段</h3>
    <div class="sub" id="dSub"></div>
  </div>
  <div class="db" id="dBody"></div>
  <div class="df">
    <button class="act primary" id="dSave">保存修正并重新核对</button>
    <button class="act" id="dConfirm">标记已人工确认</button>
    <button class="act" id="dClose">关闭</button>
  </div>
</div>
<div id="toast"></div>

<script>
/*__DATA__*/

const DOCNAME = {};
DATA.docs.forEach(d => DOCNAME[d.id] = d.type_cn || d.type);
const LIVE = DATA.docs.filter(d => !d.excluded);
const DOCIDS = LIVE.map(d => d.id);

// ---------- 状态：在原始数据上叠加人工修正 ----------
const STORE = {};
DATA.matrix.forEach(row => {
  STORE[row.field] = {cn: row.cn, en: row.en, group: row.group, kind: row.kind,
                      cells: JSON.parse(JSON.stringify(row.cells))};
});
const FIXES = [];  // {field, doc, old, val, kind, at}
const state = {status: new Set(), group: "all", doc: "all", onlyIssue: false, sel: null};

function toast(msg){
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toast._t); toast._t = setTimeout(()=>t.classList.remove("show"), 1900);
}
function esc(s){
  return String(s==null?"":s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",
    ">":"&gt;",'"':"&quot;"}[c]));
}
function nowText(){
  const d = new Date();
  const p = n => String(n).padStart(2,"0");
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

// ---------- 顶部 KPI ----------
function recompute(){
  const cells = {OK:0,DIFF:0,MISS:0,NA:0,UNK:0,CALC:0,MANUAL:0,total:0};
  Object.values(STORE).forEach(row => {
    Object.values(row.cells).forEach(c => { cells.total++; cells[c.status] = (cells[c.status]||0)+1; });
  });
  return cells;
}
function renderKpis(){
  const c = recompute();
  const bad = (c.DIFF||0) + (c.MANUAL||0);
  const k = [
    ["单证份数", LIVE.length, ""],
    ["核对字段", Object.keys(STORE).length, ""],
    ["不一致", bad, "diff"],
    ["计算不符", DATA.checks.filter(x=>!x.ok).length, "calc"],
    ["缺失", c.MISS||0, "miss"],
    ["一致", c.OK||0, "ok"],
  ];
  document.getElementById("kpis").innerHTML = k.map(([l,n,cls]) =>
    `<div class="kpi ${cls}"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("");
  const v = (bad || DATA.checks.some(x=>!x.ok))
    ? "存在必须修改或人工确认后才能交单的问题：请先处理下方「不一致 / 计算不符」，再核对「缺失」项。"
    : "未发现阻断交单的冲突；「缺失」项请按单证惯例确认是否需补录。";
  document.getElementById("verdict").textContent = v;
}

// ---------- 单证清单 ----------
function renderDocs(){
  document.getElementById("docgrid").innerHTML = LIVE.map(d => {
    const n = Object.keys(d.fields||{}).length;
    return `<div class="doc" onclick="showDoc('${d.id}')">
      <div class="t">${esc(d.type_cn)} <span class="badge">${esc(d.type)}</span></div>
      <div class="f">${esc(d.filename)}</div>
      <div class="n">已抽取 <b>${n}</b> 个字段 · ${d.pages||"?"} 页</div>
    </div>`;
  }).join("");
  const refs = DATA.docs.filter(d => d.excluded);
  document.getElementById("refs").innerHTML = refs.length
    ? "另有 <b>" + refs.length + "</b> 份参考文件（非本票业务单证，仅作填制依据，不参与核对）：" +
      refs.map(d => `<b>${esc(d.filename)}</b>`).join("、")
    : "";
}

// ---------- 计算核验 ----------
function renderChecks(){
  document.getElementById("calcbody").innerHTML = DATA.checks.map(c => `
    <tr class="calcrow ${c.ok?"":"fail"}">
      <td>${esc(c.id)}</td>
      <td>${esc(c.name)}</td>
      <td>${esc(c.detail)}</td>
      <td class="res">${c.ok?'<span class="st OK">通过</span>':'<span class="st CALC">不符</span>'}</td>
    </tr>`).join("") || '<tr><td colspan="4" class="empty">无可核验项</td></tr>';
}

// ---------- 矩阵 ----------
function cellHtml(field, did, c){
  const st = c.status, cn = DATA.status_cn[st] || st;
  let label = c.value || "";
  if (st === "NA") label = "—";
  if (st === "MISS") label = "未识别到";
  return `<span class="cell ${st}" data-f="${field}" data-d="${did}"
     onclick="openCell('${field}','${did}',event)">
     <span class="st ${st}">${cn}</span>${esc(label)}</span>`;
}
function renderMatrix(){
  const groups = {all:"全部字段"};
  Object.values(STORE).forEach(r => groups[r.group] = groups[r.group] || r.group);
  const GROUP_CN = {party:"当事人",commerce:"商务",product:"商品",logistics:"物流",
    amount:"金额",weight:"重量包装",doc:"单证信息",other:"其他"};
  const gsel = document.getElementById("filters").querySelector("#gsel");
  if (gsel && !gsel.dataset.init){
    gsel.innerHTML = Object.keys(groups).map(g =>
      `<option value="${g}">${GROUP_CN[g]||groups[g]||g}</option>`).join("");
    gsel.dataset.init = "1";
  }
  let fields = Object.keys(STORE);
  if (state.group !== "all") fields = fields.filter(f => STORE[f].group === state.group);
  if (state.status.size)
    fields = fields.filter(f => Object.values(STORE[f].cells).some(c => state.status.has(c.status)));
  if (state.onlyIssue)
    fields = fields.filter(f => Object.values(STORE[f].cells).some(c => c.status==="DIFF"||c.status==="MANUAL"));
  const head = `<thead><tr><th style="min-width:190px">字段</th>` +
    DOCIDS.map(d => `<th>${esc(DOCNAME[d]||d)}<br><span class="badge">${d}</span></th>`).join("") +
    `</tr></thead>`;
  const rows = fields.map(f => {
    const r = STORE[f];
    return `<tr><td class="rot">${esc(r.cn)}<span class="en">${esc(r.en||f)}</span></td>` +
      DOCIDS.map(d => `<td>${r.cells[d] ? cellHtml(f, d, r.cells[d]) : ""}</td>`).join("") +
      `</tr>`;
  }).join("");
  document.getElementById("matrix").innerHTML = head + "<tbody>" +
    (rows || `<tr><td colspan="${DOCIDS.length+1}" class="empty">没有符合筛选条件的字段</td></tr>`) +
    "</tbody>";
  if (state.sel){
    const el = document.querySelector(`.cell[data-f="${state.sel.f}"][data-d="${state.sel.d}"]`);
    if (el) el.classList.add("sel");
  }
}

function renderFilters(){
  const chips = [["DIFF","不一致"],["CALC","计算不符"],["MISS","缺失"],["UNK","无法判断"]];
  document.getElementById("filters").innerHTML =
    `<span style="color:var(--mute);font-size:12.5px">筛选：</span>` +
    chips.map(([k,l]) => `<span class="chip ${state.status.has(k)?"on":""}"
       onclick="toggleStatus('${k}')">${l}</span>`).join("") +
    `<span class="chip ${state.onlyIssue?"on":""}" onclick="toggleIssue()">只看问题</span>` +
    `<span style="width:10px"></span>` +
    `<select id="gsel" onchange="state.group=this.value;renderMatrix()"></select>` +
    `<select id="dsel" onchange="state.doc=this.value;renderMatrix()">
       <option value="all">全部单证</option>` +
    DOCIDS.map(d => `<option value="${d}">${esc(DOCNAME[d]||d)}</option>`).join("") +
    `</select>` +
    `<span class="spacer" style="flex:1"></span>` +
    `<span class="chip" onclick="clearFilters()">清除筛选</span>`;
  renderMatrix();
}
function toggleStatus(k){ state.status.has(k) ? state.status.delete(k) : state.status.add(k); renderFilters(); }
function toggleIssue(){ state.onlyIssue = !state.onlyIssue; renderFilters(); }
function clearFilters(){ state.status.clear(); state.onlyIssue=false; state.group="all"; renderFilters(); }

// ---------- 单元格详情 ----------
function openCell(field, did, ev){
  if (ev) ev.stopPropagation();
  state.sel = {f: field, d: did};
  const r = STORE[field], c = r.cells[did] || {};
  const st = c.status || "NA";
  document.getElementById("dTitle").textContent = `${r.cn} · ${DOCNAME[did]||did}`;
  document.getElementById("dSub").innerHTML =
    `${esc(r.en||field)} ｜ 状态：<span class="st ${st}">${DATA.status_cn[st]||st}</span>` +
    (c.page ? ` ｜ 第 ${c.page} 页` : "");
  const peers = DOCIDS.filter(d => d !== did && r.cells[d] && r.cells[d].value);
  const others = peers.map(d => `<tr><td>${esc(DOCNAME[d]||d)}</td>
      <td><span class="st ${r.cells[d].status}">${DATA.status_cn[r.cells[d].status]}</span></td>
      <td>${esc(r.cells[d].value)}</td></tr>`).join("");
  let orig = c.ctx || "";
  if (orig && c.value){
    const v = esc(c.value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    try { orig = esc(c.ctx).replace(new RegExp(v, "i"), m => `<mark>${m}</mark>`); }
    catch(e){ orig = esc(c.ctx); }
  }
  document.getElementById("dBody").innerHTML = `
    <div class="kv"><div class="k">当前识别值</div>
      <div class="v">${c.value ? esc(c.value) : '<span style="color:var(--mute)">（空）</span>'}</div></div>
    ${c.note ? `<div class="kv"><div class="k">系统判断</div><div class="v">${esc(c.note)}</div></div>` : ""}
    <div class="kv"><div class="k">原文定位${c.page ? `（第 ${c.page} 页）` : ""}</div>
      <div class="orig">${orig || '<span style="color:var(--mute)">未在原文中定位到该值</span>'}</div></div>
    <div class="kv"><div class="k">同一字段在其他单证的取值</div>
      ${others ? `<table class="peers"><tbody>${others}</tbody></table>`
               : '<div class="v" style="color:var(--mute)">其他单证未载明该字段</div>'}</div>
    <div class="kv"><div class="k">修正为（可留空表示无法判断）</div>
      <input type="text" id="dInput" value="${esc(c.value||"")}" placeholder="输入正确值…"></div>
    <div class="kv"><div class="k">修正后状态</div>
      <select id="dStatus">
        <option value="OK">一致 / 已核对无误</option>
        <option value="MANUAL">需人工确认（保留提示）</option>
        <option value="NA">本单证不适用</option>
      </select></div>`;
  document.getElementById("dStatus").value = (st === "MANUAL") ? "MANUAL" : "OK";
  document.getElementById("detail").classList.add("open");
  renderMatrix();
}
function closeDetail(){ document.getElementById("detail").classList.remove("open"); state.sel = null; renderMatrix(); }

function applyFix(kind){
  const {f, d} = state.sel || {};
  if (!f || !d) return;
  const inp = document.getElementById("dInput");
  const val = inp ? inp.value.trim() : "";
  const st = document.getElementById("dStatus").value;
  const old = STORE[f].cells[d] ? STORE[f].cells[d].value : "";
  STORE[f].cells[d] = Object.assign({}, STORE[f].cells[d]||{}, {
    value: val, status: st, note: kind === "confirm" ? "已人工确认" : "人工修正为：见修正记录"
  });
  FIXES.push({field: f, cn: STORE[f].cn, doc: d, old: old, val: val, kind: kind, at: nowText()});
  renderAll();
  closeDetail();
  toast(kind === "confirm" ? "已标记为人工确认" : "已保存修正");
}
document.getElementById("dSave").onclick = () => applyFix("correct");
document.getElementById("dConfirm").onclick = () => applyFix("confirm");
document.getElementById("dClose").onclick = closeDetail;

// ---------- 单证字段速览 ----------
function showDoc(id){
  const d = LIVE.find(x => x.id === id);
  if (!d) return;
  const rows = Object.entries(d.fields||{}).map(([f, v]) => {
    const meta = STORE[f] || {cn:f, en:""};
    return `<tr><td class="rot">${esc(meta.cn)}<span class="en">${esc(meta.en||f)}</span></td>
      <td>${esc(v.value)}</td><td style="width:52px;color:var(--mute)">第 ${v.page||"?"} 页</td></tr>`;
  }).join("");
  document.getElementById("dTitle").textContent = `${d.type_cn} · 已抽取字段`;
  document.getElementById("dSub").innerHTML = `${esc(d.filename)} ｜ 共 ${d.pages||"?"} 页`;
  document.getElementById("dBody").innerHTML = rows
    ? `<table class="peers" style="width:100%"><tbody>${rows}</tbody></table>`
    : '<div class="empty">未抽取到字段</div>';
  document.getElementById("detail").classList.add("open");
}

// ---------- 问题清单 ----------
function renderIssues(){
  const live = DATA.issues.filter(it => STORE[it.field] &&
      (STORE[it.field].cells[it.doc]||{}).status !== "NA");
  if (!live.length){
    document.getElementById("issuebody").innerHTML =
      '<tr><td colspan="7" class="empty">无待处理问题</td></tr>';
    document.getElementById("issuehint").textContent = "";
    return;
  }
  document.getElementById("issuehint").textContent =
    `共 ${live.length} 项（S1 阻断交单 / S2 需修正 / S3 建议核对）`;
  document.getElementById("issuebody").innerHTML = live.map(it => {
    const cell = STORE[it.field] && STORE[it.field].cells[it.doc];
    const cur = cell ? cell.value : (it.value||"");
    const st = cell ? cell.status : it.status;
    return `<tr>
      <td>${esc(it.id||"")}</td>
      <td><span class="st ${it.severity==="S1"?"DIFF":it.severity==="S2"?"MISS":"NA"}">${esc(it.severity||"")}</span></td>
      <td>${esc(it.field_cn||it.field)}</td>
      <td>${esc(DOCNAME[it.doc]||it.doc)}</td>
      <td>${esc(cur)||'<span style="color:var(--mute)">—</span>'}</td>
      <td>${esc(it.advice||it.note||"")}</td>
      <td>${it.page ? `<span class="chip" onclick="openCell('${it.field}','${it.doc}')">第 ${it.page} 页</span>` : "—"}</td>
    </tr>`;
  }).join("");
}

// ---------- 修正记录 ----------
function renderFixes(){
  document.getElementById("fixhint").textContent =
    FIXES.length ? `共 ${FIXES.length} 条` : "修正后会重新计算矩阵状态";
  document.getElementById("fixbody").innerHTML = FIXES.length
    ? FIXES.map((f,i) => `<tr><td>${i+1}</td><td>${esc(f.cn)}</td><td>${esc(DOCNAME[f.doc]||f.doc)}</td>
        <td>${esc(f.old)||"—"}</td><td>${esc(f.val)||"—"}</td>
        <td>${f.kind==="confirm"?"确认":"修正"}</td><td>${esc(f.at)}</td></tr>`).join("")
    : '<tr><td colspan="7" class="empty">尚无修正记录</td></tr>';
}

// ---------- 导出 ----------
function download(name, text, mime){
  const blob = new Blob([text], {type: (mime||"text/csv") + ";charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 2000);
}
function csvCell(v){ return '"' + String(v==null?"":v).replace(/"/g,'""') + '"'; }
document.getElementById("btnIssue").onclick = () => {
  const head = ["编号","级别","字段","单证","当前值","问题与建议","页码"];
  const rows = DATA.issues.map(it => {
    const cell = STORE[it.field] && STORE[it.field].cells[it.doc];
    return [it.id, it.severity, it.field_cn||it.field, DOCNAME[it.doc]||it.doc,
            cell?cell.value:(it.value||""), it.advice||it.note||"", it.page||""];
  });
  download("问题清单.csv", "\ufeff" + [head, ...rows].map(r=>r.map(csvCell).join(",")).join("\r\n"));
  toast("已导出问题清单");
};
document.getElementById("btnFix").onclick = () => {
  const head = ["#","字段","单证","原值","修正值","类型","时间"];
  const rows = FIXES.map((f,i)=>[i+1, f.cn, DOCNAME[f.doc]||f.doc, f.old, f.val,
    f.kind==="confirm"?"人工确认":"人工修正", f.at]);
  if (!rows.length){ toast("尚无修正记录"); return; }
  download("修正记录.csv", "\ufeff" + [head, ...rows].map(r=>r.map(csvCell).join(",")).join("\r\n"));
  toast("已导出修正记录");
};
document.getElementById("btnJSON").onclick = () => {
  const out = {run_at: DATA.run_at, anchor: DATA.anchor, summary: recompute(),
    matrix: STORE, fixes: FIXES, checks: DATA.checks, issues: DATA.issues};
  download("检查结果.json", JSON.stringify(out, null, 2), "application/json");
  toast("已导出检查结果 JSON");
};

// ---------- 启动 ----------
function renderAll(){ renderKpis(); renderMatrix(); renderIssues(); renderFixes(); }
function boot(){
  const a = DATA.anchor || {};
  document.getElementById("hticket").textContent =
    [a.contract_no, a.pol && a.pod ? a.pol + " → " + a.pod : ""].filter(Boolean).join(" ｜ ");
  document.getElementById("runat").textContent = DATA.run_at ? "（运行时间 " + DATA.run_at + "）" : "";
  renderDocs(); renderChecks(); renderFilters(); renderAll();
}
boot();
</script>
</body>
</html>
"""


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(base, "out", "check_result.json")
    dst = os.path.join(base, "out", "check_page.html")
    if len(sys.argv) > 1:
        src = sys.argv[1]
    if len(sys.argv) > 2:
        dst = sys.argv[2]
    with io.open(src, encoding="utf-8") as f:
        result = json.load(f)
    build(result, dst)
    size = os.path.getsize(dst)
    print("已生成: %s (%.1f KB)" % (dst, size / 1024.0))


if __name__ == "__main__":
    main()
