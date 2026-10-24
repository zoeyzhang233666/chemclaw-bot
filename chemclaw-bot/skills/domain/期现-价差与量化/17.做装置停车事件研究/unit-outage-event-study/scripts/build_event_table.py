# -*- coding: utf-8 -*-
"""build_event_table.py — 生成“待确认”的可编辑事件表（HTML，单文件）

这是第 2 步的产物：把候选事件交给用户确认，**不是研究结果**。
页面顶部有醒目的“待确认”状态条；导出后把 CSV 覆盖 events.csv，再跑 build_all.py。

用法：
  python scripts/build_event_table.py --project <项目目录> --out <事件确认表.html>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="候选事件表（待确认）")
    a = ap.parse_args(argv)

    rows = core.read_csv(os.path.join(a.project, "events.csv"))
    meta = {}
    mp = os.path.join(a.project, "project.json")
    if os.path.exists(mp):
        meta = json.load(open(mp, encoding="utf-8"))

    data = []
    for r in rows:
        data.append({
            "id": r.get("event_id", ""), "name": r.get("event_name", ""),
            "company": r.get("company", ""), "unit": r.get("unit_name", ""),
            "product": r.get("product", ""), "cap": core.parse_float(r.get("capacity_wt")),
            "region": r.get("region", ""), "country": r.get("country", ""),
            "type": core.normalize_event_type(r.get("event_type")),
            "announce": r.get("announce_date", ""), "first": r.get("first_market_date", ""),
            "actual": r.get("actual_start_date", ""), "restart": r.get("actual_restart_date", ""),
            "include": core.parse_flag(r.get("include_flag"), True),
            "reason": r.get("screening_reason", ""), "grade": r.get("evidence_grade", ""),
            "verified": core.parse_flag(r.get("product_verified"), None),
            "title": r.get("source_title", ""), "media": r.get("source_media", ""),
            "url": r.get("source_url", ""), "quote": r.get("quote", ""), "notes": r.get("notes", ""),
        })

    html = Template.replace("{DATA}", json.dumps(data, ensure_ascii=False)) \
                   .replace("{TITLE}", a.title) \
                   .replace("{PRODUCT}", meta.get("product", "")) \
                   .replace("{THRESH}", str((meta.get("thresholds") or {}).get("note", "")))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(html)
    print(f"[OK] 待确认事件表 {len(data)} 条 -> {a.out}")
    print("     确认后：把导出的 CSV 覆盖 events.csv，再跑 build_all.py")


Template = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{TITLE}</title>
<style>
:root{--bg:#101418;--panel:#171e25;--line:#2a3742;--fg:#e6edf3;--dim:#8b98a5;--acc:#4fc3f7;--warn:#ffb74d;--bad:#e57373;--ok:#81c784}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:18px 22px 70px}
h1{font-size:20px;margin:0 0 4px}
.status{background:linear-gradient(90deg,#3a2a00,#1d1500);border:1px solid #8c6d2a;border-radius:8px;padding:11px 15px;margin:12px 0;font-size:13px;line-height:1.7}
.status b{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:10px}
th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--panel);color:var(--dim);font-weight:500;position:sticky;top:0}
tr.ev:hover{background:#1e2a34;cursor:pointer}
.sub{color:var(--dim);font-size:12px}
.num{font-family:Consolas,monospace;text-align:right}
input[type=date],input[type=text]{background:#0b1015;border:1px solid var(--line);color:var(--fg);border-radius:5px;padding:3px 5px;font:12px Consolas,monospace}
input[type=checkbox]{accent-color:var(--acc)}
.tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;border:1px solid #3d6b8c;color:#90caf9}
.tag.un{color:#ef9a9a;border-color:#8c3d3d}.tag.rs{color:#a5d6a7;border-color:#3d8c4a}
.detail{display:none;background:#0b1218}.detail.on{display:table-row}
.quote{background:#0b1015;border-left:2px solid var(--warn);padding:8px 12px;margin:6px 0;font-size:12.5px}
.btn{background:var(--acc);color:#04222f;border:0;border-radius:6px;padding:8px 16px;font-weight:600;cursor:pointer}
.btn.ghost{background:#22303b;color:var(--fg)}
.muted{color:var(--dim)}.gap{color:var(--bad)}
.bar{display:flex;gap:10px;align-items:center;margin:12px 0;flex-wrap:wrap}
</style></head><body><div class="wrap">
<h1>{TITLE}</h1>
<div class="sub">品种：{PRODUCT} ｜ 阈值口径：{THRESH}</div>
<div class="status"><b>⚠ 这份表还不是研究结果。</b>
请先核对下面 8 件事，确认无误后再点“导出确认版 CSV”，覆盖 <code>events.csv</code> 并重跑流水线：<br>
① 每个事件是否<b>真的属于本品种</b>（企业同时有别的产品装置，容易串）；<br>
② 产能是<b>单套</b>还是合计（合计不能当单套用）；<br>
③ <b>市场首次获知日</b>是否真的是盘面第一次反应那天（而不是事后综述的发布日）；<br>
④ 三个日期有没有被互相顶替；<br>
⑤ 有没有同一次停车被拆成两条；<br>
⑥ 区域级/跨月滚动的事件，有没有被硬塞进单一日期的框里；<br>
⑦ 每条是否都有能在原文里搜到的原文摘录；<br>
⑧ 剔除样本的剔除理由是否站得住。</div>
<div class="bar">
  <button class="btn" id="exp">导出确认版 CSV</button>
  <button class="btn ghost" id="reset">恢复初始勾选</button>
  <span class="sub" id="cnt"></span>
</div>
<table><thead><tr>
<th style="width:32px">纳入</th><th style="width:80px">编号</th><th>事件</th><th style="width:120px">企业</th>
<th style="width:140px">装置</th><th style="width:70px">产能</th><th style="width:64px">类型</th>
<th style="width:118px">公告日</th><th style="width:118px">首次获知</th><th style="width:118px">实际停车</th>
<th style="width:56px">证据</th><th style="width:52px">核验</th>
</tr></thead><tbody id="tb"></tbody></table></div>
<script>
const DATA = {DATA};
const ORIG = JSON.parse(JSON.stringify(DATA));
let rows = JSON.parse(JSON.stringify(DATA));
const tb = document.getElementById('tb');
function draw(){
  tb.innerHTML='';
  rows.forEach((r,idx)=>{
    const tr=document.createElement('tr'); tr.className='ev';
    tr.innerHTML = `<td><input type="checkbox" data-i="${idx}" data-f="include" ${r.include!==false?'checked':''}></td>
      <td class="sub" style="font-family:Consolas">${r.id}</td>
      <td>${r.name}<div class="sub">${r.region||''} ${r.country||''}</div></td>
      <td>${r.company}</td><td class="sub">${r.unit||'—'}</td>
      <td class="num">${r.cap===null?'<span class="gap">缺</span>':r.cap}</td>
      <td><span class="tag ${r.type==='unplanned'?'un':(r.type==='restart'?'rs':'')}">${r.type==='planned'?'计划':(r.type==='unplanned'?'意外':'重启')}</span></td>
      <td><input type="date" data-i="${idx}" data-f="announce" value="${r.announce||''}"></td>
      <td><input type="date" data-i="${idx}" data-f="first" value="${r.first||''}"></td>
      <td><input type="date" data-i="${idx}" data-f="actual" value="${r.actual||''}"></td>
      <td>${r.grade||''}</td>
      <td>${r.verified===false?'<span class="gap">否</span>':'是'}</td>`;
    if(r.include===false) tr.style.opacity=.5;
    tr.addEventListener('click',e=>{ if(e.target.closest('input'))return;
      document.getElementById('d'+idx).classList.toggle('on');});
    tb.appendChild(tr);
    const dr=document.createElement('tr'); dr.id='d'+idx; dr.className='detail';
    dr.innerHTML=`<td colspan="12">
      <div><b>筛选理由</b>：${r.reason||'—'}</div>
      <div class="quote">「${r.quote||'（无原文摘录，此条证据不可核验）'}」</div>
      <div class="sub">来源：${r.media||'—'} ·《${r.title||'—'}》
      ${r.url?`　<a href="${r.url}" target="_blank" style="color:var(--acc)">打开原文</a>`:''}</div>
      ${r.notes?`<div class="sub">备注：${r.notes}</div>`:''}
      ${r.verified===false?'<div class="gap">产品核验未通过：正文主体不是本品种，不应作为本品种供给事件</div>':''}
      </td>`;
    tb.appendChild(dr);
  });
  const n = rows.filter(r=>r.include!==false).length;
  document.getElementById('cnt').textContent = `共 ${rows.length} 条候选，当前勾选纳入 ${n} 条`;
}
tb.addEventListener('change',e=>{
  const t=e.target; if(t.dataset.f===undefined) return;
  const r=rows[+t.dataset.i];
  if(t.dataset.f==='include') r.include=t.checked; else r[t.dataset.f]=t.value||'';
  draw();
});
document.getElementById('reset').addEventListener('click',()=>{rows=JSON.parse(JSON.stringify(ORIG));draw();});
document.getElementById('exp').addEventListener('click',()=>{
  const cols=['event_id','event_name','company','unit_name','product','capacity_wt','region','country',
    'event_type','announce_date','first_market_date','actual_start_date','actual_restart_date',
    'include_flag','screening_reason','evidence_grade','product_verified','source_title','source_media',
    'source_url','quote','notes'];
  const lines=[cols.join(',')];
  for(const r of rows){
    lines.push([r.id,r.name,r.company,r.unit,r.product,r.cap===null?'':r.cap,r.region,r.country,r.type,
      r.announce,r.first,r.actual,r.restart,r.include!==false?'是':'否',r.reason,r.grade,
      r.verified===false?'否':'是',r.title,r.media,r.url,r.quote,r.notes]
      .map(v=>`"${String(v===null||v===undefined?'':v).replace(/"/g,'""')}"`).join(','));
  }
  const blob=new Blob(['\\ufeff'+lines.join('\\n')],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='events_confirmed.csv'; a.click();
});
draw();
</script></div></body></html>"""

if __name__ == "__main__":
    main()
