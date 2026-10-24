# -*- coding: utf-8 -*-
"""构建单文件交互式 HTML 报告（无外部依赖）。"""
from __future__ import annotations

import json
import os

from lib_common import shanghai_now

GRADE_LABEL = {"A": "权威/许可", "a": "法定披露", "B": "官方/交易所", "C": "媒体/第三方",
               "D": "无链接自述", "E": "推断"}
IDN = {"S": "厂家", "P": "厂家(部分)", "G": "集团内生产", "T": "贸易商", "I": "集成商", "U": "未证实"}
COV = {"direct": "已证实可直供", "partial_spec": "规格/形态待确认", "disclose": "有披露待核",
       "dist_only": "仅贸易分销", "not_listed": "明确未列该产品", "none": "未评估"}

CSS = """
*{box-sizing:border-box}
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#f6f8fa;--card:#fff;
--brand:#0f766e;--brand2:#115e59;--warn:#b45309;--bad:#b91c1c;--ok:#047857;
--direct:#059669;--partial:#84cc16;--disclose:#f59e0b;--dist:#db2777;--none:#e5e7eb}
html,body{margin:0;padding:0}
body{font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
a{color:#1d4ed8;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1560px;margin:0 auto;padding:0 20px 64px}
header.top{background:linear-gradient(135deg,#0f766e,#134e4a 60%,#0b3b38);color:#fff;padding:30px 0 24px;margin-bottom:0}
header.top .wrap{padding-bottom:0}
.brandline{display:flex;align-items:center;gap:10px;font-size:12px;letter-spacing:.18em;opacity:.85;text-transform:uppercase}
h1{font-size:30px;margin:8px 0 4px;font-weight:700;letter-spacing:-.01em}
.sub{opacity:.88;font-size:13.5px;max-width:980px}
.simflag{display:inline-block;background:#fde68a;color:#7c2d12;font-weight:700;font-size:12px;padding:3px 10px;border-radius:99px;margin-top:10px}
nav.tabs{position:sticky;top:0;z-index:40;background:#fff;border-bottom:1px solid var(--line);box-shadow:0 2px 10px rgba(15,23,42,.05);margin-bottom:22px}
nav.tabs .wrap{display:flex;gap:2px;overflow-x:auto;padding:0 20px}
nav.tabs button{flex:0 0 auto;border:0;background:none;padding:13px 15px;font-size:13.5px;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;font-weight:600}
nav.tabs button.on{color:var(--brand);border-bottom-color:var(--brand)}
nav.tabs button:hover{background:#f1f5f9}
.panel{display:none}.panel.on{display:block}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-bottom:20px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .l{font-size:12px;color:var(--muted);font-weight:600}
.kpi .v{font-size:27px;font-weight:700;color:var(--brand);line-height:1.15;margin-top:2px}
.kpi .n{font-size:11.5px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:17px;margin:0 0 4px;font-weight:700}
.card .h2sub{font-size:12.5px;color:var(--muted);margin-bottom:14px}
.card h3{font-size:14px;margin:18px 0 8px}
.insight{display:grid;grid-template-columns:28px 1fr;gap:10px;padding:11px 0;border-top:1px dashed var(--line)}
.insight:first-of-type{border-top:0}
.insight .n{width:26px;height:26px;border-radius:8px;background:#e6f4f1;color:var(--brand);font-weight:700;display:flex;align-items:center;justify-content:center;font-size:12.5px}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
/* 表头只在 .scroll 这个滚动容器内部吸顶；不能相对页面 sticky，否则会盖住第一行数据 */
thead th{background:#f8fafc;font-weight:700;font-size:11.5px;color:var(--muted);white-space:nowrap}
.scroll thead th{position:sticky;top:0;z-index:10;box-shadow:inset 0 -1px 0 var(--line)}
tbody tr:hover{background:#f8fafc}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.scroll{overflow:auto;max-height:72vh;border:1px solid var(--line);border-radius:10px;position:relative}
.scroll table{margin:0}
.scroll-wrap{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff;margin-bottom:4px}
.scroll-wrap .scroll{border:0;border-radius:0;max-height:66vh}
.tablebar{display:flex;align-items:center;gap:8px;padding:7px 10px;background:#f8fafc;border-bottom:1px solid var(--line);font-size:12px}
.tablebar .sp{flex:1}
.tablebar button{padding:4px 10px;font-size:11.5px}
.thfilter{position:relative;cursor:pointer;padding-right:20px !important;user-select:none}
.thfilter:hover{background:#eef6f4;color:var(--brand)}
.thfilter::after{content:"▾";position:absolute;right:6px;top:50%;transform:translateY(-50%);font-size:9px;opacity:.45}
.thfilter.on{background:#d1fae5;color:#065f46}
.thfilter.on::after{opacity:1;color:var(--brand)}
.fpop{position:absolute;z-index:120;width:288px;background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:0 12px 32px rgba(15,23,42,.16);font-size:12.5px;overflow:hidden}
.fpop .fh{display:flex;gap:5px;padding:8px;border-bottom:1px solid var(--line);align-items:center}
.fpop .fh input{flex:1;min-width:60px;border:1px solid var(--line);border-radius:7px;padding:5px 7px;font-size:12px}
.fpop .fh button{padding:4px 7px;font-size:11px}
.fpop .fl{max-height:236px;overflow:auto;padding:4px 0}
.fpop .fl label{display:flex;gap:7px;align-items:center;padding:4px 10px;cursor:pointer}
.fpop .fl label:hover{background:#f1f5f9}
.fpop .fl label span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fpop .fl i{color:var(--muted);font-style:normal;font-size:11px}
.fpop .ff{display:flex;justify-content:space-between;align-items:center;padding:8px;border-top:1px solid var(--line)}
#toast{position:fixed;left:50%;bottom:28px;transform:translate(-50%,14px);background:#0f172a;color:#fff;padding:9px 18px;border-radius:99px;font-size:12.5px;opacity:0;pointer-events:none;transition:.22s;z-index:200}
#toast.on{opacity:1;transform:translate(-50%,0)}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:99px;font-weight:700;white-space:nowrap}
.t-ok{background:#d1fae5;color:#065f46}.t-warn{background:#fef3c7;color:#92400e}
.t-bad{background:#fee2e2;color:#991b1b}.t-gray{background:#f1f5f9;color:#475569}
.t-blue{background:#dbeafe;color:#1e40af}.t-purple{background:#ede9fe;color:#5b21b6}
.trader{background:#fce7f3;color:#9d174d}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.filters input[type=search],.filters select{border:1px solid var(--line);border-radius:8px;padding:6px 9px;font-size:12.5px;background:#fff;color:var(--ink)}
.chip{border:1px solid var(--line);background:#fff;border-radius:99px;padding:5px 12px;font-size:12px;cursor:pointer;color:var(--muted);font-weight:600}
.chip.on{background:var(--brand);border-color:var(--brand);color:#fff}
/* 矩阵 */
.mx{border-collapse:separate;border-spacing:0;font-size:12px}
.mx th{position:sticky;top:0;background:#f8fafc;z-index:12}
.mx th.rowh,.mx td.rowh{position:sticky;left:0;background:#fff;z-index:11;min-width:186px;box-shadow:1px 0 0 var(--line)}
.mx th.rowh{z-index:13;background:#f8fafc}
.mx th.vh{writing-mode:vertical-rl;transform:rotate(180deg);height:118px;padding:6px 3px;font-size:11.5px;vertical-align:bottom;white-space:nowrap;text-align:left}
.mx td.c{width:30px;min-width:30px;text-align:center;padding:0;cursor:pointer;border-right:1px solid #fff;border-bottom:1px solid #fff;height:26px;font-size:13px}
.mx td.c:hover{outline:2px solid #0f766e;outline-offset:-2px}
.c-direct{background:#059669;color:#fff}
.c-partial{background:#a3e635;color:#1a2e05}
.c-disclose{background:#fde68a;color:#78350f}
.c-dist{background:#fbcfe8;color:#9d174d}
.c-not{background:#f1f5f9;color:#cbd5e1}
.c-none{background:#fff;color:#e2e8f0}
.c-none:hover{background:#f8fafc}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin:10px 0 0}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-2px}
/* 抽屉 */
.drawer{position:fixed;inset:0;background:rgba(15,23,42,.42);z-index:90;display:none}
.drawer.on{display:block}
.drawer .box{position:absolute;right:0;top:0;bottom:0;width:min(720px,94vw);background:#fff;overflow:auto;padding:22px 26px;box-shadow:-10px 0 40px rgba(15,23,42,.2)}
.drawer h3{margin:0 0 2px;font-size:18px}
.drawer .close{position:absolute;right:18px;top:14px;border:0;background:#f1f5f9;border-radius:8px;width:32px;height:32px;font-size:16px;cursor:pointer}
.kv{display:grid;grid-template-columns:104px 1fr;gap:6px 12px;font-size:12.5px;margin:14px 0}
.kv .k{color:var(--muted);font-weight:600}
.ev{border:1px solid var(--line);border-radius:10px;padding:12px 13px;margin-bottom:10px;background:#fbfdfd}
.ev .q{border-left:3px solid var(--brand);padding-left:10px;color:#334155;font-size:12.5px;margin:8px 0;line-height:1.6}
.ev .meta{font-size:11.5px;color:var(--muted)}
button.act{border:1px solid var(--brand);background:#fff;color:var(--brand);border-radius:9px;padding:7px 13px;font-size:12.5px;font-weight:700;cursor:pointer}
button.act:hover{background:#e6f4f1}
button.primary{background:var(--brand);color:#fff;border-color:var(--brand)}
button.primary:hover{background:var(--brand2)}
pre.rfq{background:#0f172a;color:#e2e8f0;border-radius:10px;padding:16px;font-size:12px;line-height:1.7;overflow:auto;white-space:pre-wrap;max-height:60vh}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 14px}
.hint{font-size:12px;color:var(--muted)}
td.editable{cursor:text}td.edited{background:#fefce8;box-shadow:inset 0 0 0 1px #fde68a}
.bar{height:8px;background:#e2e8f0;border-radius:99px;overflow:hidden;min-width:70px}
.bar>span{display:block;height:100%;background:linear-gradient(90deg,#0f766e,#14b8a6)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:1100px){.grid2{grid-template-columns:1fr}}
.mini{font-size:11.5px;color:var(--muted)}
.footer{margin-top:26px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}
"""

JS = r"""
const D = window.__DATA__;
const $ = (s,r=document)=>r.querySelector(s);
const $$ = (s,r=document)=>[...r.querySelectorAll(s)];
const esc = s => String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// ---------- tabs
$$('nav.tabs button').forEach(b=>b.onclick=()=>{
  $$('nav.tabs button').forEach(x=>x.classList.toggle('on',x===b));
  $$('.panel').forEach(p=>p.classList.toggle('on',p.id===b.dataset.p));
  window.scrollTo({top:0,behavior:'smooth'});
});

// ---------- 抽屉
const drawer = $('#drawer');
function openDrawer(html){ $('#drawerBox').innerHTML = '<button class="close" onclick="closeDrawer()">✕</button>'+html; drawer.classList.add('on'); }
function closeDrawer(){ drawer.classList.remove('on'); }
drawer.onclick = e=>{ if(e.target===drawer) closeDrawer(); };
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeDrawer(); });

const itemByCode = {}; D.items.forEach(i=>itemByCode[i.code]=i);
const supById = {}; D.suppliers.forEach(s=>supById[s.id]=s);
const evByOrg = {}; D.evidence.forEach(e=>{ (evByOrg[e.org]=evByOrg[e.org]||[]).push(e); });

function gradeTag(g){ const c = 'Aa'.includes(g)?'t-ok':(('BC').includes(g)?'t-warn':'t-gray'); return `<span class="tag ${c}">${g} ${D.grade_label[g]||''}</span>`; }
function idnTag(i){ const c = ['S','P','G'].includes(i)?'t-ok':(i==='T'?'trader':(i==='U'?'t-gray':'t-blue')); return `<span class="tag ${c}">${D.idn[i]||i}</span>`; }
function statusTag(s){ const m={ok:['t-ok','正常'],ambiguous:['t-warn','歧义'],conflict:['t-bad','CAS冲突'],unrecognized:['t-bad','未识别'],blocked:['t-bad','阻塞']}; const x=m[s]||['t-gray',s]; return `<span class="tag ${x[0]}">${x[1]}</span>`; }
function gapTag(g){ const c = g==='无厂家覆盖'?'t-bad':(g==='厂家单一/不足'?'t-warn':(g==='覆盖充分'?'t-ok':'t-blue')); return `<span class="tag ${c}">${g}</span>`; }

// ---------- 证据
function evCards(evs){
  if(!evs.length) return '<div class="hint">该企业/物料暂无可展示的证据条目。</div>';
  return evs.map(e=>`<div class="ev">
    <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
      <div><b>${esc(e.topic)}</b><div class="meta">${esc(e.org)} · ${esc(e.date||'')} · ${esc(e.id)}</div></div>${gradeTag(e.grade)}
    </div>
    <div class="q">${esc(e.quote)}</div>
    <div>${esc(e.detail||'')}</div>
    ${e.caveat?`<div class="meta" style="color:#b45309;margin-top:6px">⚠ ${esc(e.caveat)}</div>`:''}
    ${e.url?`<div class="meta" style="margin-top:8px"><a href="${esc(e.url)}" target="_blank" rel="noopener">打开原文 ↗</a></div>`:`<div class="meta" style="margin-top:8px;color:#b91c1c">无链接（不可核验，仅作线索）</div>`}
  </div>`).join('');
}

// ---------- 单元格详情
function cellDetail(itemCode, supId){
  const it = itemByCode[itemCode], s = supById[supId];
  const lns = D.links.filter(l=>l.item_code===itemCode && l.supplier_id===supId);
  if(!lns.length){ openDrawer(`<h3>${esc(it.name)} × ${esc(s.short)}</h3><div class="hint">该组合未评估：不是“不能供”，而是本轮没有检索到可核验证据。</div>`); return; }
  const ln = lns[0];
  const sev = (s.evidence_ids||[]).map(id=>D.evidence.find(e=>e.id===id)).filter(Boolean);
  const rel = sev.filter(e=>(e.items||[]).includes(itemCode));
  const other = sev.filter(e=>!(e.items||[]).includes(itemCode));
  openDrawer(`
    <h3>${esc(it.code)} ${esc(it.name)}${it.form?' · '+esc(it.form):''} × ${esc(s.short)}</h3>
    <div class="hint">${esc(s.name)}　${idnTag(s.identity)} ${statusTag(it.status)}</div>
    <div class="kv">
      <div class="k">覆盖判定</div><div><b>${D.cov[ln.coverage]}</b>　关系：${esc(ln.degree)}　置信：${esc(ln.confidence)}</div>
      <div class="k">当前/可达</div><div>${ln.text_current?'当前可计入覆盖':'当前不计入'} ／ ${ln.text_achievable?'可达（待核）':'不可达'}</div>
      <div class="k">可靠性</div><div>${ln.score!=null?ln.score:'—'} <span class="mini">（覆盖度分 × 身份权重）</span></div>
      <div class="k">判断理由</div><div>${esc(ln.rationale)}</div>
      <div class="k">清单要求</div><div>${esc(it.spec||'（清单未填技术要求）')}　纯度 ${it.purity!=null?esc(it.purity)+'%':'—'}　包装 ${esc(it.packing||'—')}</div>
      <div class="k">危险属性</div><div>${esc(it.hazard||'—')}</div>
    </div>
    <h3 style="margin-top:18px">与该物料直接相关的证据</h3>
    ${rel.length?evCards(rel):'<div class="hint">该企业在<b>本物料</b>上没有 items 命中的证据 → 覆盖判定依靠跨品种推断，最高只能到“部分规格口径”。</div>'}
    <h3 style="margin-top:18px">企业其他证据（用于判断“它真的是厂家”）</h3>
    ${evCards(other.slice(0,6))}
  `);
}

// ---------- 供应商抽屉
function supDrawer(sid){
  const s = supById[sid];
  const rows = D.links.filter(l=>l.supplier_id===sid).sort((a,b)=>(b.cur-a.cur)||(b.score||0)-(a.score||0));
  const evs = (s.evidence_ids||[]).map(id=>D.evidence.find(e=>e.id===id)).filter(Boolean);
  openDrawer(`
    <h3>${esc(s.name)}</h3>
    <div class="hint">${idnTag(s.identity)} ${esc(s.province||'')} ${s.phone_hint?esc(s.phone_hint):''}</div>
    <div class="kv">
      <div class="k">身份判定</div><div>${esc(s.identity_note)}</div>
      <div class="k">角色/装置</div><div>${esc((s.roles||[]).join('、'))}</div>
      <div class="k">物流</div><div>${esc(s.route||'—')}</div>
      <div class="k">备注风险</div><div>${esc(s.notes||'—')}</div>
    </div>
    <div class="toolbar">
      <button class="act primary" onclick="makeRFQ('${sid}')">生成该企业询价清单</button>
    </div>
    <h3>该企业对清单物料的覆盖（${rows.filter(r=>r.cur).length} 项当前计入）</h3>
    <table><thead><tr><th>物料</th><th>覆盖判定</th><th>身份</th><th>置信</th><th>可靠性</th><th>理由</th></tr></thead><tbody>
    ${rows.map(r=>`<tr onclick="cellDetail('${r.item_code}','${sid}')" style="cursor:pointer">
      <td><b>${esc(r.item_code)}</b> ${esc(r.item_name)}${r.item_form?'·'+esc(r.item_form):''}</td>
      <td><span class="tag ${r.cls}">${esc(D.cov[r.coverage])}</span></td><td>${idnTag(r.identity)}</td>
      <td>${esc(r.confidence)}</td><td class="num">${r.score!=null?r.score:'—'}</td>
      <td class="mini">${esc(r.rationale)}</td></tr>`).join('')}
    </tbody></table>
    <h3 style="margin-top:18px">证据（${evs.length} 条）</h3>
    ${evCards(evs)}
  `);
}

// ---------- 询价清单生成
function makeRFQ(sid){
  const s = supById[sid];
  const rows = D.links.filter(l=>l.supplier_id===sid && l.ach);
  const today = new Date();
  const lines = rows.map((r,i)=>{
    const it = itemByItemCode(r.item_code);
    return `${String(i+1).padStart(2,' ')}. ${it.code} ${it.name}${it.form?'（'+it.form+'）':''} | CAS ${it.cas||'待补'} | 规格：${it.spec||'见附件'} | 数量：${it.qty??'待补'} ${it.unit||''}${it.qty_annual?'（年用量约 '+it.qty_annual+' '+it.unit+'）':''} | 包装：${it.packing||'待定'} | 覆盖判定：${D.cov[r.coverage]}`;
  }).join('');
  const need = rows.filter(r=>r.coverage!=='direct').map(r=>{
    const it = itemByItemCode(r.item_code); return `   - ${it.code} ${it.name}：确认${it.form||''}品规是否在其正常商品量范围内，并提供对应牌号 COA`;
  }).join('\n');
  const txt = `询价函（RFQ）— ${s.name}
生成时间：${today.toISOString().slice(0,10)}　交付地：${D.meta.delivery_point}
本函依据公开披露信息编制，清单为${D.list.simulated?'【模拟数据】':''}演示用途。

一、拟询物料（${rows.length} 项）
${lines||'（该企业当前无已证实/可达物料）'}

二、需你方书面确认的事项
   1) 上述物料是否为贵司自产？若为外购转售，请出具原厂授权书与出厂 COA。
   2) 生产企业名称、生产地址与危险化学品生产许可证编号（涉危化品时）。
   3) 可供数量、最小起订量、包装规格、交货周期与运输方式（罐车/袋装/吨袋）。
   4) 执行标准与质检报告（COA 批次）、保质期与储运条件。
   5) 付款条件、报价有效期与年度锁量可能性。
${need?'\n三、需重点确认的品规\n'+need:''}

四、我方后续动作
   收到回函后 3 个工作日内答复是否进入样品/小批量验证。

（本函由批量寻源工具生成，未包含价格预填，请按贵司报价单格式回传）`;
  openDrawer(`<h3>${esc(s.short)} · 询价清单</h3>
    <div class="toolbar">
      <button class="act primary" onclick="copyRFQ()">复制全文</button>
      <button class="act" onclick="downloadRFQ('${sid}')">下载 .txt</button>
      <button class="act" onclick="closeDrawer()">关闭</button>
    </div>
    <pre class="rfq" id="rfqText">${esc(txt)}</pre>`);
  window.__rfq = txt;
}
function itemByItemCode(c){ return itemByCode[c]||{}; }
function copyRFQ(){ navigator.clipboard.writeText(window.__rfq).then(()=>alert('已复制到剪贴板')); }
function downloadRFQ(sid){
  const b = new Blob([window.__rfq],{type:'text/plain;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(b);
  a.download = `RFQ_${(supById[sid].short||sid)}.txt`; a.click();
}

// ---------- 物料抽屉
function itemDrawer(code){
  const it = itemByCode[code], x = D.item_side[code]||{};
  const rows = D.links.filter(l=>l.item_code===code).sort((a,b)=>(b.cur-a.cur)||(b.score||0)-(a.score||0));
  const evs = D.evidence.filter(e=>(e.items||[]).includes(code));
  const ambs = D.ambiguities.filter(a=>a.code===code);
  openDrawer(`
    <h3>${esc(it.code)} ${esc(it.name)}${it.form?' · '+esc(it.form):''}</h3>
    <div class="hint">${statusTag(it.status)} ${esc(it.en||'')}　CAS ${esc(it.cas||'待补')}</div>
    <div class="kv">
      <div class="k">清单原文</div><div>${esc(it.raw_name)}（第 ${esc(it.source_row)} 行）</div>
      <div class="k">技术要求</div><div>${esc(it.spec||'—')}　纯度 ${it.purity!=null?esc(it.purity)+'%':'—'}</div>
      <div class="k">数量</div><div>${esc(it.qty??'—')} ${esc(it.unit||'')}　年用量 ${esc(it.qty_annual??'—')}</div>
      <div class="k">包装/交付</div><div>${esc(it.packing||'—')} / ${esc(it.delivery||'—')}</div>
      <div class="k">危险属性</div><div>${esc(it.hazard||'—')}${it.hazard_raw?'（清单写法：'+esc(it.hazard_raw)+'）':''}</div>
      <div class="k">覆盖结论</div><div>${gapTag(x.gap_label||'')} 候选 ${x.candidate_count||0} 家，其中厂家 ${x.degree_adv||0} 家</div>
    </div>
    ${ambs.length?`<h3>待确认</h3>${ambs.map(a=>`<div class="ev"><b>${esc(a.id)} · ${esc(a.level)}</b><div class="q">${esc(a.question)}</div><div class="meta">${esc((a.extra||[]).join('；'))}</div></div>`).join('')}`:''}
    <h3 style="margin-top:16px">候选企业（${rows.length}）</h3>
    <table><thead><tr><th>企业</th><th>身份</th><th>覆盖</th><th>置信</th><th>可靠性</th><th>理由</th></tr></thead><tbody>
    ${rows.map(r=>`<tr onclick="cellDetail('${code}','${r.supplier_id}')" style="cursor:pointer">
      <td><b>${esc(r.sup_short)}</b></td><td>${idnTag(r.identity)}</td>
      <td><span class="tag ${r.cls}">${esc(D.cov[r.coverage])}</span></td><td>${esc(r.confidence)}</td>
      <td class="num">${r.score!=null?r.score:'—'}</td><td class="mini">${esc(r.rationale)}</td></tr>`).join('')||'<tr><td colspan="6" class="hint">暂无候选，见缺口清单</td></tr>'}
    </tbody></table>
    <h3 style="margin-top:16px">证据（${evs.length} 条）</h3>
    ${evCards(evs)}
  `);
}

// ---------- 矩阵渲染（行/列实体统一先归一化成 {id,label,sub,meta}，避免不同数据源字段名不一致导致的静默丢格）
function renderMatrix(view){
  $('#mxHost').innerHTML = buildMatrix(view);
  try{ afterRender(); }catch(e){ console.error(e); }
}

function raf(fn){ return requestAnimationFrame? requestAnimationFrame(fn) : setTimeout(fn,0); }

// 供应商列：supplier_rank 里只有 supplier_id，供应商档案里才有 id/short/province
function supCols(){
  return D.supplier_rank.map(row => {
    const s = D.suppliers.find(x => x.id === row.supplier_id) || {};
    return {
      id: row.supplier_id,
      label: s.short || row.short || row.name || row.supplier_id,
      full: s.name || row.name || '',
      identity: s.identity || row.identity || 'U',
      province: s.province || row.province || '',
      row: row,
    };
  });
}
function itemCols(){
  return D.items.map(it => ({id: it.code, label: it.code, full: it.name, form: it.form || '', raw: it}));
}

function buildMatrix(view){
  const filter = window.__mxFilter || {identity:'all', prov:'all', min:0, haz:false};
  let sups = supCols();
  if(filter.identity==='S') sups = sups.filter(s=>['S','P','G'].includes(s.identity));
  if(filter.identity==='T') sups = sups.filter(s=>['T','I'].includes(s.identity));
  if(filter.prov && filter.prov!=='all') sups = sups.filter(s=>s.province===filter.prov);
  if(filter.min>0) sups = sups.filter(s=>s.row.current>=filter.min);
  let items = itemCols();
  if(filter.haz) items = items.filter(i=>String(i.raw.hazard||'').includes('第'));
  const linkMap = {};
  D.links.forEach(l=>{ linkMap[l.item_code+'|'+l.supplier_id]=l; });
  const cell = (ic, sid) => {
    const l = linkMap[ic+'|'+sid];
    if(!l) return `<td class="c c-none" onclick="cellDetail('${ic}','${sid}')" title="未评估：点开查看说明"></td>`;
    const key = l.ach ? l.coverage : 'not_listed';
    const cls = l.ach ? (l.cls || 'c-none') : 'c-not';
    const sym = l.ach ? (l.sym || '') : '·';
    return `<td class="c ${cls}" onclick="cellDetail('${ic}','${sid}')" title="${esc(ic)} × ${esc(sid)}：${esc(D.cov[l.coverage]||'')}">${sym}</td>`;
  };
  let html = '';
  if(view==='item'){
    html += `<div class="scroll"><table class="mx"><thead><tr><th class="rowh">物料</th>`;
    sups.forEach(s=>html+=`<th class="vh" title="${esc(s.full)}">${esc(s.label)}<br><span class="mini">${esc(D.idn[s.identity]||s.identity)}</span></th>`);
    html += `<th>候选</th><th>厂家</th><th>风险</th></tr></thead><tbody>`;
    items.forEach(ic=>{
      const x = D.item_side[ic.id]||{};
      html += `<tr><td class="rowh" onclick="itemDrawer('${ic.id}')" style="cursor:pointer"><b>${esc(ic.id)}</b> ${esc(ic.full)}${ic.form?'<span class="mini"> · '+esc(ic.form)+'</span>':''}</td>`;
      sups.forEach(s=>{ html += cell(ic.id, s.id); });
      html += `<td class="num">${x.candidate_count||0}</td><td class="num">${x.degree_adv||0}</td><td>${gapTag(x.gap_label||'')}</td></tr>`;
    });
    html += `</tbody></table></div>`;
  } else {
    html += `<div class="scroll"><table class="mx"><thead><tr><th class="rowh">企业</th>`;
    items.forEach(ic=>html+=`<th class="vh" title="${esc(ic.full)}">${esc(ic.label)}<br><span class="mini">${esc(ic.full)}</span></th>`);
    html += `<th>当前</th><th>可达</th><th>覆盖比</th></tr></thead><tbody>`;
    sups.forEach(s=>{
      html += `<tr><td class="rowh" onclick="supDrawer('${s.id}')" style="cursor:pointer"><b>${esc(s.label)}</b> ${idnTag(s.identity)}<div class="mini">${esc(s.province)}</div></td>`;
      items.forEach(ic=>{ html += cell(ic.id, s.id); });
      const r0 = s.row;
      html += `<td class="num">${r0.current}</td><td class="num">${r0.achievable}</td><td><div class="bar"><span style="width:${Math.min(100,r0.coverage_ratio)}%"></span></div><span class="mini">${r0.coverage_ratio}%</span></td></tr>`;
    });
    html += `</tbody></table></div>`;
  }
  return html;
}
function setMx(k,v){ window.__mxFilter = Object.assign({identity:'all',prov:'all',min:0,haz:false}, window.__mxFilter||{}, {[k]:v});
  $$('#mxFilters .chip').forEach(c=>c.classList.toggle('on', c.dataset.k===k && String(c.dataset.v)===String(v)));
  renderMatrix(window.__mxView||'item'); }
function setView(v){ window.__mxView=v; $$('#mxViewBtn .chip').forEach(c=>c.classList.toggle('on',c.dataset.v===v)); renderMatrix(v); }

// ---------- 标准化表编辑
function initEdit(){
  const saved = JSON.parse(localStorage.getItem('mx_edits')||'{}');
  $$('#tblItems td.editable').forEach(td=>{
    const key = td.dataset.k;
    if(saved[key]!=null){ td.textContent = saved[key]; td.classList.add('edited'); }
    if(td.__bound) return;
    td.__bound = true;
    td.onclick = ()=>{
      if(td.dataset.edit==='1') return;
      td.dataset.edit='1';
      const v = td.textContent;
      td.innerHTML = `<input id="cellEditor" style="width:100%;border:1px solid #0f766e;border-radius:5px;padding:2px 4px;font-size:12px" value="${esc(v)}">`;
      const inp = td.querySelector('input'); inp.focus(); inp.select();
      const done = ()=>{ const nv = inp.value; td.textContent = nv; td.classList.add('edited'); td.dataset.edit='0';
        saved[key]=nv; localStorage.setItem('mx_edits',JSON.stringify(saved)); };
      inp.onblur = done; inp.onkeydown = e=>{ if(e.key==='Enter'){ inp.blur(); } if(e.key==='Escape'){ inp.onblur=null; td.textContent=v; td.dataset.edit='0'; } };
    };
  });
}
function resetEdits(){ localStorage.removeItem('mx_edits'); location.reload(); }
function exportEdits(){
  const rows = [['物料码','清单原品名','标准名','CAS','形态/规格','数量','单位','技术要求','备注']];
  $$('#tblItems tbody tr').forEach(tr=>{
    const tds = [...tr.querySelectorAll('td')];
    const pick = i => tds[i] ? (tds[i].querySelector('input') ? tds[i].querySelector('input').value : tds[i].textContent) : '';
    rows.push([1,2,3,4,5,7,8,14,17].map(i=>pick(i)));
  });
  const csv = rows.map(r=>r.map(c=>`"${String(c).replace(/"/g,'""')}"`).join(',')).join('\n');
  const b = new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download='物料标准化表_已编辑.csv'; a.click();
}

// ---------- 表格操作条（表内全选过滤 + 复制 Excel 粘贴）
function wrapScrolls(){
  $$('.scroll').forEach(sc=>{
    if(sc.parentElement && sc.parentElement.classList.contains('scroll-wrap')) return;
    const w = document.createElement('div'); w.className='scroll-wrap';
    sc.parentNode.insertBefore(w, sc);
    const bar = document.createElement('div'); bar.className='tablebar';
    bar.innerHTML = `<span class="hint">点表头可筛选 · 「复制表格」可直接粘到 Excel</span>
      <span class="sp"></span>
      <button class="act" data-act="clear">清除筛选</button>
      <button class="act" data-act="copy">复制表格</button>`;
    w.appendChild(bar); w.appendChild(sc);
    bar.addEventListener('click', e=>{
      const act = e.target.dataset.act;
      if(act==='clear') clearFilters(sc);
      if(act==='copy') copyTable(sc);
    });
    const tr = sc.querySelector('thead tr');
    if(tr) [...tr.children].forEach((th,i)=>{
      th.classList.add('thfilter');
      th.title = '点击筛选：' + th.textContent.trim();
      th.addEventListener('click', e=>{ e.stopPropagation(); openFilterPop(th, sc, i); });
    });
  });
}
function rowsOf(sc){ return [...sc.querySelectorAll('tbody tr')].filter(tr=>!tr.classList.contains('empty-row')); }
function applyFilters(sc){
  const f = sc.__filters || {};
  const rows = rowsOf(sc);
  let shown = 0;
  rows.forEach(tr=>{
    let ok = true;
    Object.keys(f).forEach(idx=>{
      const td = tr.children[idx];
      const txt = td ? td.textContent.trim() : '';
      if(!f[idx].has(txt)) ok = false;
    });
    tr.style.display = ok ? '' : 'none';
    if(ok) shown++;
  });
  let empty = sc.querySelector('.empty-row');
  if(shown===0){
    const col = sc.querySelector('thead tr') ? sc.querySelector('thead tr').children.length : 1;
    if(!empty){
      const tb = sc.querySelector('tbody');
      empty = document.createElement('tr'); empty.className='empty-row';
      empty.innerHTML = `<td colspan="${col}" class="hint" style="padding:18px;text-align:center">当前筛选条件下没有匹配的行 —— 点右上角「清除筛选」恢复</td>`;
      tb.appendChild(empty);
    }
    empty.style.display = '';
  } else if(empty){ empty.style.display='none'; }
  const btn = sc.parentElement.querySelector('[data-act="clear"]');
  if(btn) btn.style.display = Object.keys(f).length ? '' : 'none';
}
function clearFilters(sc){ sc.__filters={}; $$('.thfilter.on',sc).forEach(t=>t.classList.remove('on')); applyFilters(sc); }
function openFilterPop(th, sc, idx){
  closeFilterPop();
  const rows = rowsOf(sc);
  const tally = new Map();
  rows.forEach(tr=>{
    const td = tr.children[idx];
    const txt = td ? td.textContent.trim() : '';
    tally.set(txt, (tally.get(txt)||0)+1);
  });
  const active = (sc.__filters||{})[idx];
  const vals = [...tally.entries()].sort((a,b)=>b[1]-a[1] || a[0].localeCompare(b[0],'zh'));
  const pop = document.createElement('div');
  pop.className='fpop'; pop.id='fpop';
  pop.innerHTML = `<div class="fh"><input type="search" id="fpopQ" placeholder="搜值…"> <button class="act" data-a="all">全选</button> <button class="act" data-a="none">全不选</button></div>
    <div class="fl">${vals.map(([v,n],i)=>`<label><input type="checkbox" data-v="${esc(v)}" ${(!active||active.has(v))?'checked':''}> <span>${v===''?'（空白）':esc(v)}</span> <i>${n}</i></label>`).join('')}</div>
    <div class="ff"><span class="hint">点表外关闭即生效</span><button class="act primary" data-a="ok">确定</button></div>`;
  document.body.appendChild(pop);
  const r = th.getBoundingClientRect();
  pop.style.top = (r.bottom + window.scrollY + 4) + 'px';
  pop.style.left = Math.max(8, Math.min(r.left + window.scrollX, window.innerWidth - 300)) + 'px';
  pop.querySelector('#fpopQ').oninput = e=>{
    const kw = e.target.value.trim();
    pop.querySelectorAll('.fl label').forEach(l=>{ l.style.display = !kw || l.textContent.includes(kw) ? '' : 'none'; });
  };
  pop.querySelector('.fh').addEventListener('click', e=>{
    const a = e.target.dataset.a; if(!a) return;
    pop.querySelectorAll('.fl input').forEach(cb=>{ cb.checked = (a==='all'); });
  });
  pop.querySelector('[data-a="ok"]').onclick = ()=>{
    const boxes = [...pop.querySelectorAll('.fl input')];
    const checked = boxes.filter(b=>b.checked).map(b=>b.dataset.v);
    sc.__filters = sc.__filters || {};
    if(checked.length === boxes.length){ delete sc.__filters[idx]; th.classList.remove('on'); }
    else { sc.__filters[idx] = new Set(checked); th.classList.add('on'); }
    closeFilterPop(); applyFilters(sc);
  };
  setTimeout(()=>document.addEventListener('mousedown', outside), 0);
}
function outside(e){ const pop = document.getElementById('fpop'); if(pop && !pop.contains(e.target)){ closeFilterPop(); const th=document.querySelector('.thfilter.open'); if(th) th.classList.remove('open'); } }
function closeFilterPop(){ const p = document.getElementById('fpop'); if(p) p.remove(); document.removeEventListener('mousedown', outside); }
function copyTable(sc){
  const vis = rowsOf(sc).filter(tr=>tr.style.display!=='none');
  const heads = [...sc.querySelectorAll('thead th')].map(th=>th.textContent.trim());
  const lines = [heads.join('\t')];
  vis.forEach(tr=>{
    lines.push([...tr.children].map(td=>td.textContent.replace(/\s+/g,' ').trim()).join('\t'));
  });
  const txt = lines.join('\n');
  const done = ()=>toast('已复制 ' + vis.length + ' 行，可直接粘到 Excel');
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(txt).then(done).catch(()=>fallback());
  } else fallback();
  function fallback(){
    const ta = document.createElement('textarea'); ta.value = txt; document.body.appendChild(ta); ta.select();
    try{ document.execCommand('copy'); done(); }catch(e){ toast('复制失败，请手动选择表格'); }
    ta.remove();
  }
}
function toast(msg){
  let t = document.getElementById('toast');
  if(!t){ t = document.createElement('div'); t.id='toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('on');
  clearTimeout(window.__toastT); window.__toastT = setTimeout(()=>t.classList.remove('on'), 2200);
}

// ---------- 过滤：候选企业表
function initSupFilter(){
  const q = $('#supQ'), idf = $('#supId'), pf = $('#supProv');
  const apply = ()=>{
    const kw = (q.value||'').toLowerCase();
    $$('#supRows tr').forEach(tr=>{
      const t = tr.dataset.txt.toLowerCase();
      let ok = !kw || t.includes(kw);
      if(idf.value!=='all') ok = ok && tr.dataset.id===idf.value;
      if(pf.value!=='all') ok = ok && tr.dataset.prov===pf.value;
      tr.style.display = ok?'':'none';
    });
  };
  [q,idf,pf].forEach(el=>{ el.oninput = apply; el.onchange = apply; });
}

// ---------- 初始化
function afterRender(){
  wrapScrolls();
  initEdit();
  $$('.scroll').forEach(sc=>applyFilters(sc));
}
renderMatrix('item');
initSupFilter();
afterRender();
$$('nav.tabs button').forEach(b=>{
  if(b.__hooked) return; b.__hooked = true;
  const old = b.onclick;
  b.onclick = ev=>{ old && old(ev); raf(afterRender); };
});
// 切回浏览器标签页或打印前，补齐可能漏掉的包装
window.addEventListener('resize', ()=>$$('.scroll').forEach(sc=>applyFilters(sc)));
"""


def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def build_html(project, out_path):
    p = project
    calc = p["_calc"]
    items = p["items"]
    suppliers = p["suppliers"]

    # ---------- 供前端使用的扁平数据
    links = []
    for ln in p["links"]:
        it = next((i for i in items if i["code"] == ln["item_code"]), None)
        s = next((x for x in suppliers if x["id"] == ln["supplier_id"]), None)
        if not it or not s or not ln.get("_deg"):
            continue
        deg = ln["_deg"]
        ach = deg["achievable"]
        cov = ln["coverage"] if ach else "none"
        cls = {"direct": "c-direct", "partial_spec": "c-partial", "disclose": "c-disclose",
               "dist_only": "c-dist", "not_listed": "c-not", "none": "c-not"}.get(cov, "c-not")
        sym = {"direct": "●", "partial_spec": "◐", "disclose": "○", "dist_only": "◆", "not_listed": "×"}.get(cov, "")
        links.append({
            "item_code": ln["item_code"], "item_name": it["name"], "item_form": it.get("form", ""),
            "supplier_id": ln["supplier_id"], "sup_short": s["short"],
            "identity": ln.get("identity") or s["identity"], "coverage": cov,
            "confidence": ln.get("confidence", ""), "degree": ln.get("degree", ""),
            "rationale": ln.get("rationale", ""), "score": ln.get("reliability_score"),
            "cur": 1 if deg["current"] else 0, "ach": 1 if ach else 0, "cls": cls, "sym": sym,
            "text_current": "是" if deg["current"] else "否", "text_achievable": "是" if ach else "否",
        })

    data = {
        "meta": p["meta"], "list": p["list"],
        "grade_label": GRADE_LABEL, "idn": IDN, "cov": COV,
        "items": items, "suppliers": suppliers, "evidence": p["evidence"],
        "ambiguities": p.get("ambiguities", []), "links": links,
        "actions": p.get("actions", []), "gaps": p.get("gaps", []),
        "item_side": calc["item_side"], "supplier_rank": calc["supplier_rank"],
        "multi": calc["multi"], "scarce": calc["scarce"],
    }

    # ---------------- KPI
    n_items = len(items)
    n_man = len([s for s in suppliers if s["identity"] in ("S", "P")])
    n_adv = sum(1 for x in calc["item_side"].values() if x["degree_adv"] >= 2)
    n_single = sum(1 for x in calc["item_side"].values() if x["degree_adv"] == 1)
    n_zero = sum(1 for x in calc["item_side"].values() if x["degree_adv"] == 0)
    n_multi = len(calc["multi"])
    n_amb = len(p.get("ambiguities", []))
    n_haz = sum(1 for i in items if "第" in (i.get("hazard") or ""))
    kpis = [("物料行数", n_items, "含异常行 / 待确认行"), ("候选企业", len(suppliers), f"厂家口径 {n_man} 家"),
            ("≥2 家厂家可直供", n_adv, "可直接进入比价"), ("仅 1 家厂家直供", n_single, "单一来源风险"),
            ("无厂家覆盖", n_zero, "本轮未查出，不等于没有"), ("可跨物料打包企业", n_multi, "覆盖 ≥2 个物料"),
            ("待确认事项", n_amb, "P0 阻塞项须先解决"), ("涉危险化学品物料", n_haz, "需核许可证")]
    kpi_html = "".join(
        f'<div class="kpi"><div class="l">{esc(k)}</div><div class="v">{v}</div><div class="n">{esc(n)}</div></div>'
        for k, v, n in kpis)

    # ---------------- 物料表
    st_map = {"ok": ("t-ok", "正常"), "ambiguous": ("t-warn", "歧义"), "conflict": ("t-bad", "CAS冲突"),
              "unrecognized": ("t-bad", "未识别"), "blocked": ("t-bad", "阻塞")}
    rows_items = []
    for it in items:
        x = calc["item_side"].get(it["code"], {})
        st, stl = st_map.get(it.get("status", "ok"), ("t-gray", it.get("status", "")))
        d = x.get("degree_adv", 0)
        gapc = "t-bad" if d == 0 else ("t-warn" if d == 1 else "t-ok")
        rows_items.append(f"""<tr>
<td><b>{esc(it['code'])}</b></td>
<td class="editable" data-k="{esc(it['code'])}-raw">{esc(it.get('raw_name',''))}</td>
<td class="editable" data-k="{esc(it['code'])}-name"><b>{esc(it.get('name',''))}</b></td>
<td class="editable" data-k="{esc(it['code'])}-cas"><code>{esc(it.get('cas',''))}</code></td>
<td class="editable" data-k="{esc(it['code'])}-form">{esc(it.get('form',''))}</td>
<td class="num editable" data-k="{esc(it['code'])}-qty">{esc(it.get('qty') if it.get('qty') is not None else '')}</td>
<td class="editable" data-k="{esc(it['code'])}-unit">{esc(it.get('unit',''))}</td>
<td class="num">{esc(it.get('qty_annual') if it.get('qty_annual') is not None else '—')}</td>
<td><span class="tag {st}">{esc(stl)}</span></td>
<td class="editable" data-k="{esc(it['code'])}-spec">{esc(it.get('spec','') or '—')}</td>
<td>{esc(it.get('hazard','') or '—')}</td>
<td class="num">{x.get('candidate_count',0)}</td>
<td><span class="tag {gapc}">{d}</span></td>
<td>{esc(x.get('gap_label',''))}</td>
<td class="mini editable" data-k="{esc(it['code'])}-note">{esc('；'.join(it.get('issues',[])) or it.get('notes',''))}</td>
</tr>""")

    # ---------------- 待确认
    amb_rows = []
    for a in sorted(p.get("ambiguities", []),
                    key=lambda x: ({"P0": 0, "P1": 1, "P2": 2}.get(x.get("level"), 3), x.get("id", ""))):
        it = next((i for i in items if i["code"] == a.get("code")), {})
        lv = a.get("level")
        cls = "t-bad" if lv == "P0" else ("t-warn" if lv == "P1" else "t-gray")
        extra = "".join(f"<div class='mini'>· {esc(e)}</div>" for e in (a.get("extra") or []))
        amb_rows.append(f"""<tr><td><b>{esc(a.get('id'))}</b></td><td><span class="tag {cls}">{esc(lv)}</span></td>
<td><b>{esc(a.get('code',''))}</b></td><td>{esc(a.get('row',''))}</td><td>{esc(it.get('name',''))}</td>
<td>{esc(a.get('question',''))}{extra}</td><td class="mini">{esc(a.get('detail',''))}</td>
<td>{esc(a.get('owner','采购方'))}</td><td><span class="tag t-gray">{esc(a.get('status','待确认'))}</span></td></tr>""")

    # ---------------- 候选企业
    idn_cls = {"S": "t-ok", "P": "t-ok", "G": "t-ok", "T": "trader", "I": "t-blue", "U": "t-gray"}
    sup_rows = []
    for i, row in enumerate(calc["supplier_rank"], start=1):
        s = next(x for x in suppliers if x["id"] == row["supplier_id"])
        ratio = row["coverage_ratio"]
        rel = row["avg_reliability"]
        cls = "t-ok" if row["current"] >= 2 else ("t-warn" if row["current"] == 1 else "t-bad")
        sup_rows.append(f"""<tr data-txt="{esc(s['name']+' '+s['short']+' '+','.join(s.get('roles',[]))+' '+s.get('province',''))}"
 data-id="{esc(s['identity'])}" data-prov="{esc(s.get('province',''))}" onclick="supDrawer('{s['id']}')" style="cursor:pointer">
<td class="num">{i}</td><td><b>{esc(s['name'])}</b><div class="mini">{esc(s.get('identity_note',''))[:110]}</div></td>
<td><span class="tag {idn_cls.get(s['identity'],'t-gray')}">{esc(IDN.get(s['identity'],''))}</span></td>
<td>{esc(s.get('province',''))}</td>
<td class="num"><span class="tag {cls}">{row['current']}</span></td><td class="num">{row['adv_current']}</td>
<td class="num">{row['achievable']}</td><td class="num">{rel if rel is not None else '—'}</td>
<td><div class="bar"><span style="width:{min(100,ratio)}%"></span></div><span class="mini">{ratio}%</span></td>
<td class="mini">{esc('、'.join(s.get('roles',[])))}</td></tr>""")

    # ---------------- 多物料
    lbl = {i["code"]: f"{i['code']} {i['name']}{('·' + i['form']) if i.get('form') else ''}" for i in items}
    multi_rows = "".join(f"""<tr><td class="num">{n}</td><td><b>{esc(m['name'])}</b></td>
<td><span class="tag {idn_cls.get(m['identity'],'t-gray')}">{esc(IDN.get(m['identity'],''))}</span></td>
<td class="num"><b>{m['current_count']}</b></td><td class="num">{m['achievable_count']}</td>
<td><div class="bar"><span style="width:{min(100,m['coverage_ratio'])}%"></span></div><span class="mini">{m['coverage_ratio']}%</span></td>
<td>{esc('、'.join(lbl.get(c,c) for c in m['covered_items']))}</td>
<td class="mini">{esc('、'.join(lbl.get(c,c) for c in m['achievable_items']))}</td></tr>"""
                           for n, m in enumerate(calc["multi"], start=1))

    # ---------------- 稀缺
    order = {"无厂家覆盖": 0, "厂家单一/不足": 1, "规格或证据不足": 2}
    scar_rows = []
    for x in sorted(calc["scarce"], key=lambda y: (order.get(y["gap_label"], 9), y["degree_adv"])):
        it = next((i for i in items if i["code"] == x["item_code"]), {})
        d = x["degree_adv"]
        cls = "t-bad" if d == 0 else ("t-warn" if d == 1 else "t-blue")
        scar_rows.append(f"""<tr onclick="itemDrawer('{x['item_code']}')" style="cursor:pointer">
<td><b>{esc(x['item_code'])}</b></td><td>{esc(it.get('name',''))}{esc('·'+it.get('form','')) if it.get('form') else ''}</td>
<td class="num">{x['candidate_count']}</td><td class="num"><b>{d}</b></td><td class="num">{x['degree_adv_achievable']}</td>
<td class="num">{x['trader_degree']}</td><td><span class="tag {cls}">{esc(x['gap_label'])}</span></td>
<td class="mini">{esc('、'.join(x.get('adv_achievable_names',[])) or '—')}</td></tr>""")

    # ---------------- 证据
    order_g = {"A": 0, "a": 1, "B": 2, "C": 3, "D": 4, "E": 5}
    ev_rows = []
    for ev in sorted(p["evidence"], key=lambda e: (order_g.get(e["grade"], 9), e["id"])):
        g = ev["grade"]
        cls = "t-ok" if g in "Aa" else ("t-warn" if g in "BC" else "t-gray")
        url = ev.get("url")
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener">原文 ↗</a>' if url else '<span class="tag t-bad">无链接</span>'
        ev_rows.append(f"""<tr><td><b>{esc(ev['id'])}</b></td><td><span class="tag {cls}">{esc(g)}</span></td>
<td>{esc(ev.get('org',''))}</td><td>{esc(ev.get('topic',''))}</td>
<td class="mini">{esc(ev.get('quote',''))}</td><td class="mini">{esc(ev.get('detail',''))}</td>
<td>{esc('、'.join(ev.get('items',[])) or '企业级')}</td><td>{esc(ev.get('date',''))}</td><td>{link}</td></tr>""")

    # ---------------- 危险
    haz_rows = []
    for it in items:
        hz = it.get("hazard") or "（未标注）"
        haz = "第" in hz
        haz_rows.append(f"""<tr><td><b>{esc(it['code'])}</b></td><td>{esc(it['name'])}</td><td><code>{esc(it.get('cas',''))}</code></td>
<td><span class="tag {'t-bad' if haz else 't-ok'}">{esc(hz)}</span></td><td class="mini">{esc(it.get('hazard_raw','') or '—')}</td>
<td class="mini">{'危险化学品生产/经营许可证 + 危险货物运输资质' if haz else '一般工业品'}</td>
<td>{esc(it.get('packing','') or '—')}</td></tr>""")

    # ---------------- 询价/缺口
    act_rows = []
    for a in p.get("actions", []):
        act_rows.append(f"""<tr><td><b>{esc(a['id'])}</b></td><td><span class="tag t-warn">{esc(a.get('priority',''))}</span></td>
<td><b>{esc(a.get('supplier',''))}</b></td><td>询价包</td>
<td>{esc('；'.join(a.get('actions',[])))}<div class="mini">涉及：{esc('、'.join(a.get('items',[])))}</div></td>
<td><button class="act" onclick="makeRFQ('{esc(a.get('supplier_id',''))}')">生成询价清单</button></td></tr>""")
    for g in p.get("gaps", []):
        act_rows.append(f"""<tr><td><b>{esc(g['id'])}</b></td>
<td><span class="tag {'t-bad' if g.get('severity')=='P0' else 't-warn'}">{esc(g.get('severity'))}</span></td>
<td><b>{esc(g.get('item',''))}</b></td><td>缺口 · {esc(g.get('type',''))}</td>
<td>{esc('；'.join(g.get('actions',[])))}</td><td class="mini">新增可核验厂家 ≥1 家</td></tr>""")

    headline = "".join(f'<div class="insight"><div class="n">{i}</div><div>{esc(t)}</div></div>'
                       for i, t in enumerate(p["meta"].get("headline", []), start=1))

    provs = sorted({s.get("province", "") for s in suppliers if s.get("province")})
    prov_opts = "".join(f'<option value="{esc(x)}">{esc(x)}</option>' for x in provs)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(p['meta']['title'])} · 批量寻源报告</title>
<style>{CSS}</style></head><body>
<header class="top"><div class="wrap">
  <div class="brandline">BATCH PURCHASE SOURCING · 物料—供应商匹配矩阵</div>
  <h1>{esc(p['meta']['title'])}</h1>
  <div class="sub">{esc(p['meta'].get('subtitle',''))}</div>
  <div class="simflag">清单为模拟数据 · 企业与证据为真实公开信息（{esc(p['meta'].get('as_of',''))} 截止）</div>
</div></header>

<nav class="tabs"><div class="wrap">
  <button class="on" data-p="p-overview">① 概览与结论</button>
  <button data-p="p-items">② 物料标准化表</button>
  <button data-p="p-amb">③ 待确认事项</button>
  <button data-p="p-sup">④ 候选企业</button>
  <button data-p="p-mx">⑤ 双向匹配矩阵</button>
  <button data-p="p-multi">⑥ 跨物料企业</button>
  <button data-p="p-scarce">⑦ 稀缺与风险</button>
  <button data-p="p-ev">⑧ 证据库</button>
  <button data-p="p-haz">⑨ 危险与监管</button>
  <button data-p="p-act">⑩ 询价与核验清单</button>
</div></nav>

<div class="wrap">
<!-- ============ 概览 -->
<section class="panel on" id="p-overview">
  <div class="kpis">{kpi_html}</div>
  <div class="card">
    <h2>结论摘要</h2>
    <div class="h2sub">先说结论，再说证据。下面每一条都能在“⑤ 双向匹配矩阵”里点开对应格子看到原始出处。</div>
    {headline}
  </div>
  <div class="grid2">
    <div class="card">
      <h2>这份报告回答了什么</h2>
      <div class="h2sub">对应需求清单的第 1–10 项</div>
      <table><tbody>
      <tr><td>① 识别物料</td><td>{n_items} 行全部解析，字段映射见 Excel 12 表</td></tr>
      <tr><td>② 标准化</td><td>名称/别名/CAS/浓度/形态/单位统一口径，CAS 做校验位校验</td></tr>
      <tr><td>③ 歧义提问</td><td>{n_amb} 条待确认，其中 P0 {len([a for a in p.get('ambiguities',[]) if a.get('level')=='P0'])} 条</td></tr>
      <tr><td>④ 找候选企业</td><td>{len(suppliers)} 家，厂家 {n_man} 家、贸易商/未证实单列</td></tr>
      <tr><td>⑤ 核实供应关系</td><td>{len(p['evidence'])} 条证据，逐条含原文引用与链接</td></tr>
      <tr><td>⑥ 匹配矩阵</td><td>物料→企业、企业→物料双向可切换</td></tr>
      <tr><td>⑦ 跨物料企业</td><td>{n_multi} 家可一次谈多个物料</td></tr>
      <tr><td>⑧ 危险属性</td><td>{n_haz} 个物料涉危化品，附许可要求</td></tr>
      <tr><td>⑨ 稀缺物料</td><td>{len(calc['scarce'])} 项存在厂家不足或规格特殊</td></tr>
      <tr><td>⑩ 询价清单</td><td>{len(p.get('actions',[]))} 个 RFQ 包 + {len(p.get('gaps',[]))} 个缺口任务</td></tr>
      </tbody></table>
    </div>
    <div class="card">
      <h2>怎么读这张矩阵</h2>
      <div class="legend">
        <span><i style="background:#059669"></i>● 已证实可直供</span>
        <span><i style="background:#a3e635"></i>◐ 规格/形态待确认</span>
        <span><i style="background:#fde68a"></i>○ 有披露待核实</span>
        <span><i style="background:#fbcfe8"></i>◆ 仅贸易分销</span>
        <span><i style="background:#f1f5f9"></i>× 明确未列该产品</span>
        <span><i style="background:#fff;border:1px solid #cbd5e1"></i>空白 未评估</span>
      </div>
      <h3>三条硬规则</h3>
      <div class="insight"><div class="n">1</div><div><b>厂家 ≠ 贸易商。</b>只有能指向自有装置/许可证/产量的主体才算厂家；“我们代理××”“能配送”一律进贸易商或未证实池，不进入比价名单。</div></div>
      <div class="insight"><div class="n">2</div><div><b>企业网站提到 ≠ 有稳定供货能力。</b>“有产品线”最多给到 ◐；“产能/产量 + 规格”同时对上才是 ●。</div></div>
      <div class="insight"><div class="n">3</div><div><b>空白 ≠ 不能供。</b>空白表示本轮没检索到证据。要知道能不能供，只能发询价、要 COA 和许可证。</div></div>
    </div>
  </div>
  <div class="footer">数据截止 {esc(p['meta'].get('as_of',''))} · 生成于 {shanghai_now().strftime('%Y-%m-%d %H:%M')} ·
  来源范围：{'、'.join(p['meta'].get('sources_scope',[]))}</div>
</section>

<!-- ============ 物料表 -->
<section class="panel" id="p-items">
  <div class="card">
    <h2>② 物料标准化表（可直接改）</h2>
    <div class="h2sub">点任意灰底单元格即可编辑（如把“—”改成吨、补 CAS、补规格）。改动会记在本机浏览器里，可导出 CSV 交回给采购方确认。</div>
    <div class="toolbar">
      <button class="act primary" onclick="exportEdits()">导出已编辑 CSV</button>
      <button class="act" onclick="resetEdits()">还原全部改动</button>
      <span class="hint">黄色底 = 你改过的单元格</span>
    </div>
    <div class="scroll"><table id="tblItems"><thead><tr>
      <th>物料码</th><th>清单原品名</th><th>标准名称</th><th>CAS</th><th>形态/规格</th><th class="num">数量</th><th>单位</th>
      <th class="num">年用量</th><th>状态</th><th>技术要求</th><th>危险属性</th><th class="num">候选</th><th>厂家</th><th>风险</th><th>问题/备注</th>
    </tr></thead><tbody>{''.join(rows_items)}</tbody></table></div>
  </div>
</section>

<!-- ============ 待确认 -->
<section class="panel" id="p-amb">
  <div class="card">
    <h2>③ 待确认事项（不猜测，只提问）</h2>
    <div class="h2sub">P0 = 阻塞项：不回答就无法寻源或无法比价；P1 = 影响规格或价格；P2 = 不影响寻源但需归档。</div>
    <div class="scroll"><table><thead><tr><th>编号</th><th>优先级</th><th>物料码</th><th>清单原品名</th><th>标准名</th>
      <th>需要确认的问题</th><th>判断依据</th><th>负责人</th><th>状态</th></tr></thead><tbody>{''.join(amb_rows)}</tbody></table></div>
  </div>
</section>

<!-- ============ 候选企业 -->
<section class="panel" id="p-sup">
  <div class="card">
    <h2>④ 候选企业（严格区分厂家与贸易商）</h2>
    <div class="h2sub">点任意一行查看该企业的全部证据与覆盖判定；“当前”只统计已证实的关系。</div>
    <div class="filters">
      <input type="search" id="supQ" placeholder="搜企业名 / 角色 / 省份…" style="min-width:240px">
      <select id="supId"><option value="all">全部身份</option><option value="S">厂家 / 集团</option><option value="T">贸易商 / 集成商</option><option value="U">未证实</option></select>
      <select id="supProv"><option value="all">全部省份</option>{prov_opts}</select>
    </div>
    <div class="scroll"><table><thead><tr><th class="num">#</th><th>企业</th><th>身份</th><th>省份</th>
      <th class="num">当前覆盖</th><th class="num">其中厂家</th><th class="num">可达</th><th class="num">可靠性</th><th>覆盖比</th><th>角色 / 装置</th>
    </tr></thead><tbody id="supRows">{''.join(sup_rows)}</tbody></table></div>
  </div>
</section>

<!-- ============ 矩阵 -->
<section class="panel" id="p-mx">
  <div class="card">
    <h2>⑤ 双向匹配矩阵</h2>
    <div class="h2sub">点格子看证据（谁说的、原文、链接、判定理由）；点行首看该物料/该企业的完整画像。</div>
    <div class="flex" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px">
      <div id="mxViewBtn" class="filters" style="margin:0">
        <button class="chip on" data-v="item" onclick="setView('item')">按物料看企业</button>
        <button class="chip" data-v="sup" onclick="setView('sup')">按企业看物料</button>
      </div>
      <div id="mxFilters" class="filters" style="margin:0">
        <button class="chip on" data-k="identity" data-v="all" onclick="setMx('identity','all')">全部身份</button>
        <button class="chip" data-k="identity" data-v="S" onclick="setMx('identity','S')">只看厂家</button>
        <button class="chip" data-k="identity" data-v="T" onclick="setMx('identity','T')">只看贸易商</button>
        <button class="chip" data-k="min" data-v="0" onclick="setMx('min',0)">全部</button>
        <button class="chip" data-k="min" data-v="2" onclick="setMx('min',2)">覆盖≥2 物料</button>
        <button class="chip" data-k="haz" data-v="false" onclick="setMx('haz',false)">含全部物料</button>
        <button class="chip" data-k="haz" data-v="true" onclick="setMx('haz',true)">只看危化品</button>
        <select onchange="setMx('prov',this.value)"><option value="all">全部省份</option>{prov_opts}</select>
      </div>
    </div>
    <div id="mxHost"></div>
    <div class="legend">
      <span><i style="background:#059669"></i>● 已证实可直供</span>
      <span><i style="background:#a3e635"></i>◐ 规格/形态待确认</span>
      <span><i style="background:#fde68a"></i>○ 有披露待核实</span>
      <span><i style="background:#fbcfe8"></i>◆ 仅贸易分销</span>
      <span><i style="background:#f1f5f9"></i>× 明确未列</span>
    </div>
  </div>
</section>

<!-- ============ 跨物料 -->
<section class="panel" id="p-multi">
  <div class="card">
    <h2>⑥ 可同时供应多种物料的企业</h2>
    <div class="h2sub">这些企业值得“打包谈判”：一次谈多个物料、合并发运，通常能拿到更好的商务条件。但要注意不同物料可能分属不同子公司/装置，签约主体要逐一确认。</div>
    <div class="scroll"><table><thead><tr><th class="num">#</th><th>企业</th><th>身份</th><th class="num">当前覆盖</th>
      <th class="num">可达覆盖</th><th>覆盖比</th><th>已证实的物料</th><th>可达的物料（含待核）</th></tr></thead>
      <tbody>{multi_rows}</tbody></table></div>
  </div>
</section>

<!-- ============ 稀缺 -->
<section class="panel" id="p-scarce">
  <div class="card">
    <h2>⑦ 稀缺物料 / 特殊规格 / 风险物料</h2>
    <div class="h2sub">按厂家数升序。再强调一次：“无厂家覆盖”只代表本轮公开检索没查出可核验厂家，不等于市场上没有——处理办法见第 ⑩ 页的缺口任务。</div>
    <div class="scroll"><table><thead><tr><th>物料码</th><th>物料</th><th class="num">候选数</th><th class="num">厂家</th>
      <th class="num">可达厂家</th><th class="num">贸易商</th><th>风险类型</th><th>已掌握的可达企业（含待确认）</th></tr></thead>
      <tbody>{''.join(scar_rows)}</tbody></table></div>
  </div>
</section>

<!-- ============ 证据 -->
<section class="panel" id="p-ev">
  <div class="card">
    <h2>⑧ 证据库（全部可点击回溯）</h2>
    <div class="h2sub">A = 第三方权威/许可批文；a = 企业法定披露原件；B = 官方/交易所公告；C = 媒体/第三方；D = 无链接自述（不可核验）。</div>
    <div class="scroll"><table><thead><tr><th>ID</th><th>等级</th><th>来源机构</th><th>主题</th><th>原文引用</th><th>对结论的作用</th>
      <th>关联物料</th><th>日期</th><th>链接</th></tr></thead><tbody>{''.join(ev_rows)}</tbody></table></div>
  </div>
</section>

<!-- ============ 危险 -->
<section class="panel" id="p-haz">
  <div class="card">
    <h2>⑨ 危险属性与特殊监管要求</h2>
    <div class="h2sub">危险类别取标准化字典口径，清单原文单列。剧毒/易制爆/易制毒等管制需按现行名录逐条核对，本表只提示方向，不替代法务判断。</div>
    <div class="scroll"><table><thead><tr><th>物料码</th><th>物料</th><th>CAS</th><th>危险属性</th><th>清单写法</th>
      <th>许可/资质要求</th><th>包装与储存</th></tr></thead><tbody>{''.join(haz_rows)}</tbody></table></div>
  </div>
</section>

<!-- ============ 询价 -->
<section class="panel" id="p-act">
  <div class="card">
    <h2>⑩ 后续询价与资质核验清单</h2>
    <div class="h2sub">点“生成询价清单”即可得到一份可直接发出的 RFQ 文本（含该企业所有可达物料与需书面确认的事项），可复制或下载。</div>
    <div class="scroll"><table><thead><tr><th>编号</th><th>优先级</th><th>对象</th><th>类型</th><th>要做的事</th><th>操作</th></tr></thead>
      <tbody>{''.join(act_rows)}</tbody></table></div>
    <h3>资质核验通用清单</h3>
    <table><tbody>
      <tr><td>营业执照</td><td>经营范围是否覆盖该化学品；生产型还是贸易型</td></tr>
      <tr><td>危险化学品生产许可证 / 经营许可证</td><td>许可证载明的产品名称、产能、有效期是否覆盖所询物料</td></tr>
      <tr><td>危险货物道路运输</td><td>承运方是否具备资质；押运、罐车检验与保险</td></tr>
      <tr><td>质量体系与检验</td><td>ISO9001、出厂检验能力、第三方检测报告（SGS 等）</td></tr>
      <tr><td>授权链</td><td>贸易商须提供原厂授权书 + 原厂 COA，禁止“转手凑单”</td></tr>
      <tr><td>交付能力</td><td>月可供量、安全库存、旺季保供承诺、违约条款</td></tr>
    </tbody></table>
  </div>
</section>
</div>

<div class="drawer" id="drawer"><div class="box" id="drawerBox"></div></div>
<script>window.__DATA__ = {_dumps(data)};</script>
<script>{JS}</script>
</body></html>"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def esc(s):
    import html as _h
    return _h.escape(str(s if s is not None else ""), quote=True)
