# -*- coding: utf-8 -*-
"""build_html.py —— 生成自包含交互式月差扫描看板（单文件 HTML，无外部依赖）

依赖：scan_result.json + industry_data.json + quotes_<date>.json
用法：python build_html.py --scan build/scan_result.json --industry industry_data.json \
                          --quotes quotes_2026-10-20.json --out out/dashboard.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description='生成异常月差扫描看板 HTML')
    ap.add_argument('--scan', default='build/scan_result.json')
    ap.add_argument('--industry', default='industry_data.json')
    ap.add_argument('--quotes', default=None)
    ap.add_argument('--out', default='out/dashboard.html')
    ap.add_argument('--title', default='化工期货异常月差扫描看板')
    a = ap.parse_args(argv)
    scan = load(a.scan)
    ind = load(a.industry)
    qp = a.quotes
    if not qp:
        cands = [os.path.join(os.path.dirname(a.scan) or '.', f'quotes_{scan["as_of"]}.json'),
                 f'quotes_{scan["as_of"]}.json',
                 os.path.join('data', f'quotes_{scan["as_of"]}.json')]
        qp = next((c for c in cands if os.path.exists(c)), None)
    quotes = load(qp) if qp and os.path.exists(qp) else {
        'date': scan['as_of'], 'contracts': {}, 'sources': {}}
    out = build(scan, ind, quotes, a.title)
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'wrote {a.out}  ({len(out) / 1024:.1f} KB)')
    return 0


def build(scan, industry, quotes, title):
    payload = json.dumps({'scan': scan, 'industry': industry, 'quotes': {
        'date': quotes.get('date'),
        'sources': quotes.get('sources'),
        'warrants': quotes.get('warrants'),
        'price_basis_by_product': quotes.get('price_basis_by_product'),
        'cross_check': {'n': quotes.get('cross_check', {}).get('n'),
                        'mismatch': quotes.get('cross_check', {}).get('mismatch'),
                        'note': quotes.get('cross_check', {}).get('note')},
        'contracts': quotes.get('contracts', {}),
    }}, ensure_ascii=False)
    data = payload.replace('</', '<\\/')
    as_of = scan['as_of']
    head = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
"""
    body_a = f"""<div class="wrap">
<header>
  <div class="h1">
    <h1>化工期货｜异常月差（近远月价差）扫描看板</h1>
    <span class="badge live">真实数据</span>
    <span class="badge">数据日 {as_of}</span>
    <span class="badge" id="basisBadge"></span>
    <span class="badge">口径：近月 − 远月</span>
  </div>
  <div class="sub">品种池：甲醇 MA · 纯碱 SA · 聚丙烯 PP · PTA TA　|　价格源：郑商所官方日报 + 东方财富(DCE)　|　历史样本：逐合约日线，同品种同组合同剩余期限周对齐</div>
</header>
"""
    return head + STYLE + body_a + BODY_B + '<script>\nconst DATA = ' + data + ';\n' + JS + '\n</script>\n</body>\n</html>\n'


STYLE = r"""<style>
:root{
  --bg:#0e1116; --panel:#161b23; --panel2:#1b2230; --line:#26303f; --txt:#e6ebf2; --dim:#93a1b5;
  --acc:#4da3ff; --acc2:#7ee0c0; --neg:#ff6b81; --pos:#3ddc97; --warn:#ffc857; --ext:#ff5e8a;
  --shadow:0 10px 30px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(180deg,#0b0e13,#0e1116 260px);color:var(--txt);
  font:14px/1.6 "Segoe UI","Microsoft YaHei",system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--acc)}
.wrap{max-width:1500px;margin:0 auto;padding:0 22px 64px}
header{padding:26px 0 14px;border-bottom:1px solid var(--line);margin-bottom:20px}
.h1{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
h1{font-size:24px;margin:0;letter-spacing:.5px;font-weight:650}
.sub{color:var(--dim);font-size:13px}
.badge{display:inline-flex;align-items:center;gap:6px;padding:2px 9px;border-radius:999px;font-size:12px;
  border:1px solid var(--line);background:var(--panel2);color:var(--dim)}
.badge.live{color:#04121f;background:var(--acc2);border-color:var(--acc2);font-weight:700}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow)}
.panel h2{font-size:15px;margin:0 0 10px;font-weight:650;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.panel h2 .tag{font-size:11px;color:var(--dim);font-weight:500;border:1px solid var(--line);padding:1px 7px;border-radius:999px}
.grid{display:grid;gap:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:16px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 15px;position:relative;overflow:hidden}
.kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--acc)}
.kpi.ext:before{background:var(--ext)} .kpi.pos:before{background:var(--pos)} .kpi.neg:before{background:var(--neg)}
.kpi .k{color:var(--dim);font-size:12px} .kpi .v{font-size:23px;font-weight:680;margin-top:2px}
.kpi .s{color:var(--dim);font-size:12px;margin-top:2px}
.mono{font-variant-numeric:tabular-nums;font-family:ui-monospace,Consolas,monospace}
.controls{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end}
.ctrl{display:flex;flex-direction:column;gap:5px;min-width:150px}
.ctrl label{font-size:12px;color:var(--dim)}
select,input{background:var(--panel2);color:var(--txt);border:1px solid var(--line);border-radius:9px;padding:7px 9px;font-size:13px;outline:none}
select:focus,input:focus{border-color:var(--acc)}
button{background:var(--acc);color:#04121f;border:0;border-radius:9px;padding:8px 14px;font-weight:650;cursor:pointer;font-size:13px}
button.ghost{background:transparent;color:var(--txt);border:1px solid var(--line);font-weight:500}
button:hover{filter:brightness(1.08)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.chip{font-size:12px;padding:4px 11px;border-radius:999px;border:1px solid var(--line);color:var(--dim);cursor:pointer;user-select:none}
.chip.on{background:rgba(77,163,255,.15);border-color:var(--acc);color:#cfe6ff}
canvas{width:100%;display:block}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin:6px 0 2px}
.legend i{display:inline-block;width:16px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{color:var(--dim);font-weight:600;font-size:12px}
td.l,th.l{text-align:left}
tr.rowlink{cursor:pointer} tr.rowlink:hover td{background:rgba(77,163,255,.07)}
tr.sel td{background:rgba(77,163,255,.13)}
.scroll{max-height:430px;overflow:auto;border-radius:10px}
.pill{font-size:11px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);color:var(--dim)}
.pill.ok{color:var(--pos);border-color:rgba(61,220,151,.45)}
.pill.no{color:var(--neg);border-color:rgba(255,107,129,.45)}
.pill.ext{color:var(--ext);border-color:rgba(255,94,138,.5);background:rgba(255,94,138,.1)}
.pill.warn{color:var(--warn);border-color:rgba(255,200,87,.45)}
.pos{color:var(--pos)} .neg{color:var(--neg)} .dim{color:var(--dim)}
.note{font-size:12px;color:var(--dim);background:rgba(255,200,87,.06);border:1px solid rgba(255,200,87,.25);
  border-radius:10px;padding:10px 12px;margin-top:10px}
.disc{font-size:12px;color:var(--dim);border-left:3px solid var(--neg);padding:8px 12px;background:rgba(255,107,129,.06);border-radius:0 10px 10px 0;margin-top:14px}
.ev{border-left:2px solid var(--line);padding:6px 0 6px 12px;margin:8px 0;position:relative}
.ev:before{content:"";position:absolute;left:-5px;top:13px;width:8px;height:8px;border-radius:50%;background:var(--acc)}
.ev.bullish:before{background:var(--pos)} .ev.bearish:before{background:var(--neg)}
.ev.bearish_near:before{background:#ff9f5e} .ev.bearish_far:before{background:#c86bff}
.ev.bullish_near:before{background:#3ddc97} .ev.bullish_cost:before{background:#7ee0c0}
.ev .d{font-size:11px;color:var(--dim)} .ev .t{font-size:13px}
.src{font-size:11px;color:#5d7492;word-break:break-all}
.empty{color:var(--dim);font-size:13px;padding:18px;text-align:center}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:1000px){.two{grid-template-columns:1fr}}
.heat{display:inline-block;width:100%;height:8px;border-radius:4px;background:var(--panel2);position:relative;min-width:70px}
.heat span{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:linear-gradient(90deg,#3ddc97,#ffc857,#ff5e8a)}
</style>"""

BODY_B = r"""<div class="wrap">
<header>
  <div class="h1">
    <h1>化工期货｜异常月差（近远月价差）扫描看板</h1>
    <span class="badge live">真实数据</span>
    <span class="badge">数据日 {as_of}</span>
    <span class="badge" id="basisBadge"></span>
    <span class="badge">口径：近月 − 远月</span>
  </div>
  <div class="sub">品种池：甲醇 MA · 纯碱 SA · 聚丙烯 PP · PTA TA　|　价格源：郑商所官方日报 + 东方财富(DCE)　|　历史样本：逐合约日线，同品种同组合同剩余期限周对齐</div>
</header>

<div class="kpis" id="kpis"></div>

<div class="panel" style="margin-bottom:16px">
  <h2>筛选 <span class="tag">改动任一项即重算</span></h2>
  <div class="controls">
    <div class="ctrl"><label>品种池</label>
      <select id="fProduct" multiple size="4"></select></div>
    <div class="ctrl"><label>月差口径（近月 = 主力后第 N 档）</label>
      <select id="fScenario">
        <option value="0">主力 − 下一档</option>
        <option value="1" selected>主力 − 次二档（主推）</option>
        <option value="2">主力 − 次三档</option>
        <option value="3">主力 − 次四档</option>
      </select></div>
    <div class="ctrl"><label>极端分位阈值（%）</label>
      <select id="fThr">
        <option value="5">5% / 95%（严格）</option>
        <option value="10" selected>10% / 90%（标准）</option>
        <option value="20">20% / 80%（宽松）</option>
      </select></div>
    <div class="ctrl"><label>最少历史样本 N</label>
      <select id="fMinN"><option value="3" selected>3</option><option value="4">4</option><option value="5">5</option></select></div>
    <div class="ctrl"><label>排序</label>
      <select id="fSort"><option value="ext" selected>极端程度</option><option value="pct_hi">分位从高到低</option><option value="pct_lo">分位从低到高</option><option value="chg">近1月变化</option></select></div>
    <div class="ctrl"><label>仅看可交易组合</label>
      <select id="fTrad"><option value="0" selected>否（全部展示）</option><option value="1">是</option></select></div>
    <div class="ctrl"><label>显示样本不足的候选</label>
      <select id="fShowIns"><option value="1" selected>显示</option><option value="0">隐藏</option></select></div>
  </div>
  <div class="chips" id="chips"></div>
  <div class="note" id="scanNote"></div>
</div>

<div class="panel" style="margin-bottom:16px">
  <h2>异常月差榜单 <span class="tag" id="rankInfo"></span></h2>
  <div class="scroll" style="max-height:520px"><table id="rankTable">
    <thead><tr>
      <th class="l">#</th><th class="l">品种</th><th class="l">近月 − 远月</th>
      <th>当前月差</th><th>历史分位</th><th>极端度</th><th>Z</th>
      <th>近1月变化</th><th>历史均值</th><th>N</th><th class="l">评级</th><th class="l">可交易</th>
    </tr></thead><tbody></tbody>
  </table></div>
  <div class="disc">排名只表示"当前月差在自身可比历史中的位置"，<b>不构成跨期套利或交易建议</b>。分位高（靠近100%）＝近月相对远月比历史更贵；分位低（靠近0%）＝近月相对更便宜。样本不足的组合不给分位。</div>
</div>

<div class="panel" style="margin-bottom:16px" id="detailPanel">
  <h2>品种明细 <span class="tag">点击榜单任一行切换</span></h2>
  <div class="kpis" id="detailKpis"></div>
  <div class="two">
    <div>
      <h2 style="font-size:13px;color:var(--dim);margin:6px 0 2px">期限结构（当日全部挂牌合约结算价）</h2>
      <div class="legend"><span><i style="background:var(--acc)"></i>挂牌合约曲线</span><span><i style="background:var(--ext)"></i>当前所选组合两腿</span></div>
      <canvas id="cvCurve" height="300"></canvas>
      <div id="curveNote" class="note" style="display:none"></div>
    </div>
    <div>
      <h2 style="font-size:13px;color:var(--dim);margin:6px 0 2px">历史可比样本（同组合、同剩余期限）</h2>
      <div class="legend"><span><i style="background:var(--acc2)"></i>历年同期月差</span><span><i style="background:var(--ext)"></i>当前月差</span></div>
      <canvas id="cvHist" height="300"></canvas>
      <div id="histNote" class="note" style="display:none"></div>
    </div>
  </div>
  <div class="two" style="margin-top:16px">
    <div>
      <h2 style="font-size:13px;color:var(--dim);margin:6px 0 2px">该组合近 45 个交易日</h2>
      <canvas id="cvSeries" height="220"></canvas>
    </div>
    <div>
      <h2 style="font-size:13px;color:var(--dim);margin:6px 0 2px">合约明细</h2>
      <div class="scroll" style="max-height:230px"><table id="legTable"><thead><tr>
        <th class="l">合约</th><th>结算价</th><th>收盘价</th><th>持仓</th><th>距交割</th><th class="l">角色</th></tr></thead><tbody></tbody></table></div>
    </div>
  </div>
  <div class="two" style="margin-top:16px">
    <div>
      <h2 style="font-size:13px;color:var(--dim);margin:6px 0 2px">该品种全部月差组合（扫描结果）</h2>
      <div class="scroll" style="max-height:300px"><table id="pairTable"><thead><tr>
        <th class="l">组合</th><th>月差</th><th>分位</th><th>Z</th><th>近1月</th><th>N</th><th class="l">评级</th></tr></thead><tbody></tbody></table></div>
    </div>
    <div>
      <h2 style="font-size:13px;color:var(--dim);margin:6px 0 2px">库存 / 仓单 / 现货 <span class="tag">产业面</span></h2>
      <div class="scroll" style="max-height:300px"><table id="indTable"><thead><tr>
        <th class="l">指标</th><th>数值</th><th class="l">单位</th><th>变化</th><th class="l">日期</th><th class="l">可信度</th></tr></thead><tbody></tbody></table></div>
    </div>
  </div>
  <div style="margin-top:16px">
    <h2 style="font-size:13px;color:var(--dim);margin:6px 0 2px">供需事件时间线 <span class="tag">仅用于解释位置，不构成方向判断</span></h2>
    <div id="events"></div>
  </div>
</div>

<div class="panel" style="margin-bottom:16px">
  <h2>合约规则匹配 <span class="tag">交易所规则 vs 实测挂牌</span></h2>
  <div class="scroll" style="max-height:400px"><table id="ruleTable"><thead><tr>
    <th class="l">品种</th><th class="l">交易所</th><th class="l">合约月份</th><th>交易单位</th><th>最小变动</th>
    <th>最低保证金</th><th class="l">最后交易日</th><th class="l">主力锚点</th><th>当日挂牌</th></tr></thead><tbody></tbody></table></div>
  <div class="note">合约月份"1–12月全挂牌"经 <b>276 个逐合约日线实测</b>：各合约上市首日均在交割月前 12 个月，四品种无跳月设计。MA/SA/TA 价格取<b>交易所结算价</b>；PP 因大商所官网对脚本返回 412，当日行情取自东方财富，为<b>最新价</b>口径 —— 两套口径分列，不混算。</div>
</div>

<div class="panel">
  <h2>数据与口径说明 <span class="tag">可追溯</span></h2>
  <div id="dataNotes"></div>
</div>
</div>
"""

JS = r"""const S = DATA.scan, IND = DATA.industry, Q = DATA.quotes;

/* ---------- 工具 ---------- */
const fmt = (v,d=0)=> v===null||v===undefined||v==='' ? '—' : (typeof v==='number'? v.toFixed(d) : v);
const sgn = v => v===null||v===undefined ? 'dim' : (v>0?'pos':(v<0?'neg':'dim'));
const esc = s => String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* ---------- 场景：从主力位置推组合 ---------- */
function scenarioPairs(prod, k){
  const b = S.products[prod]; if(!b || !b.term_structure) return [];
  const ts = b.term_structure;
  const mainIdx = ts.findIndex(r=>r.is_main);
  if(mainIdx<0) return [];
  const near = ts[mainIdx], far = ts[mainIdx+1+k];
  if(!near || !far) return null;
  return [near.symbol, far.symbol];
}
/* 在扫描结果里找组合；找不到就用曲线现算（无历史分位） */
function findPair(prod, label){
  const b = S.products[prod]; if(!b) return null;
  return (b.pairs||[]).find(p=>p.label===label) || null;
}
function quickPair(prod, near, far){
  const b = S.products[prod];
  const a = b.term_structure.find(r=>r.symbol===near), c = b.term_structure.find(r=>r.symbol===far);
  if(!a||!c) return null;
  const pa = a.settle??a.close, pc = c.settle??c.close;
  return {product:prod, near, far, label:`${near}-${far}`, spread: pa!==null&&pc!==null? +(pa-pc).toFixed(2):null,
    percentile:null, z:null, n_history:0, grade:'未计算', block_reasons:[], tradable:true,
    near_settle:pa, far_settle:pc, near_oi:a.oi, far_oi:c.oi, change_1m:null, mean_hist:null, history:[], series_30d:[]};
}

/* ---------- 状态 ---------- */
const state = {products:new Set(Object.keys(S.products)), k:1, thr:10, minN:3, sort:'ext', trad:false, showIns:true, selected:null, histRange:'all'};

/* ---------- 初始化控件 ---------- */
const fProd=document.getElementById('fProduct');
Object.entries(S.products).forEach(([p,b])=>{
  const o=document.createElement('option'); o.value=p; o.textContent=`${b.name_cn} ${p}`; o.selected=true; fProd.appendChild(o);
});
fProd.onchange = ()=>{ state.products=new Set([...fProd.selectedOptions].map(o=>o.value)); render(); };
document.getElementById('fScenario').onchange=e=>{state.k=+e.target.value; render();};
document.getElementById('fThr').onchange=e=>{state.thr=+e.target.value; render();};
document.getElementById('fMinN').onchange=e=>{state.minN=+e.target.value; render();};
document.getElementById('fSort').onchange=e=>{state.sort=e.target.value; render();};
document.getElementById('fTrad').onchange=e=>{state.trad=e.target.value==='1'; render();};
document.getElementById('fShowIns').onchange=e=>{state.showIns=e.target.value==='1'; render();};

/* ---------- 组装候选组合 ---------- */
function candidates(){
  const out=[];
  for(const p of state.products){
    const b=S.products[p]; if(!b||!b.term_structure) continue;
    const sc=scenarioPairs(p,state.k);
    if(sc){ const rec=findPair(p, sc.join('-')) || quickPair(p, sc[0], sc[1]); if(rec){rec._scenario=true; out.push(rec);} }
    for(const pr of (b.pairs||[])) if(!pr._scenario) out.push(pr);
  }
  // 去重
  const seen=new Set();
  return out.filter(r=>{const k=r.label; if(seen.has(k))return false; seen.add(k); return true;});
}
function hasPct(r){ return r.percentile!==null && r.percentile!==undefined && (r.n_history||0)>=state.minN; }
function isExtreme(r){ if(!hasPct(r)) return false; const t=state.thr; return r.percentile<=t || r.percentile>=100-t; }

/* ---------- 渲染 KPI ---------- */
function renderKpis(list){
  const withPct=list.filter(hasPct), ext=list.filter(isExtreme);
  const nHist=withPct.map(r=>r.n_history||0);
  const basis=B=>B==='last'?'PP为最新价口径':'结算价口径';
  const html=[
    {k:'扫描组合数', v:list.length, s:`覆盖 ${state.products.size} 个品种`},
    {k:'有可比分位的组合', v:withPct.length, s:`样本 N≥${state.minN}`},
    {k:'极端组合（≤${state.thr}% 或 ≥${100-state.thr}%）', v:ext.length, s:ext.length?'已标红':'当前阈值下无', cls:'neg'},
    {k:'极端度最高的组合', v:ext.length?ext[0].label:'—', s:ext.length?`极端度 ${fmt(ext[0].extremeness??Math.abs((ext[0].percentile??50)-50)*2,0)}`:'—', cls:'ext', small:true},
    {k:'历史样本年数', v:'2022–2026', s:'同组合同剩余期限周对齐'},
    {k:'行情交叉核对', v:Q.cross_check.mismatch===0?'通过':'有差异', s:`${Q.cross_check.n||0} 合约，不一致 ${Q.cross_check.mismatch}`},
  ].map(x=>`<div class="kpi ${x.cls||''}"><div class="k">${x.k}</div><div class="v ${x.small?'':''}" style="${x.small?'font-size:16px':''}">${esc(x.v)}</div><div class="s">${esc(x.s)}</div></div>`).join('');
  document.getElementById('kpis').innerHTML=html;
  document.getElementById('basisBadge').textContent=`${Q.date} 行情｜结算价(MA/SA/TA) + 最新价(PP)`;
}

/* ---------- 渲染榜单 ---------- */
function renderRank(list){
  let rows=list.slice();
  if(state.trad) rows=rows.filter(r=>r.tradable!==false && !(r.block_reasons||[]).length);
  if(!state.showIns) rows=rows.filter(hasPct);
  const t=state.thr;
  const ext=r=>hasPct(r)&&(r.percentile<=t||r.percentile>=100-t);
  const sorters={
    ext:(a,b)=>((b.extremeness??(hasPct(b)?Math.abs(b.percentile-50)*2:-1))-(a.extremeness??(hasPct(a)?Math.abs(a.percentile-50)*2:-1))),
    pct_hi:(a,b)=>((b.percentile??-1)-(a.percentile??-1)),
    pct_lo:(a,b)=>((a.percentile??999)-(b.percentile??999)),
    chg:(a,b)=>Math.abs(b.change_1m??0)-Math.abs(a.change_1m??0)
  };
  rows.sort(sorters[state.sort]);
  const tb=document.querySelector('#rankTable tbody');
  if(!rows.length){ tb.innerHTML='<tr><td colspan="12" class="empty">当前筛选下没有组合</td></tr>'; }
  else tb.innerHTML=rows.map((r,i)=>{
    const pct=r.percentile, ex=ext(r);
    const pill = ex?'pill ext':(hasPct(r)? (Math.abs(pct-50)>(50-t)?'pill warn':'pill') : 'pill');
    const block=(r.block_reasons||[]).filter(x=>x).join('、');
    const trad=r.tradable===false? `<span class="pill no">${esc(block||'不可交易')}</span>`:
      (block? `<span class="pill warn">${esc(block)}</span>` : '<span class="pill ok">✓</span>');
    return `<tr class="rowlink ${state.selected===r.product+'|'+r.label?'sel':''}" data-p="${r.product}" data-l="${r.label}">
      <td class="l dim">${i+1}</td>
      <td class="l">${r.product}<span class="dim"> ${S.products[r.product]?.name_cn||''}</span></td>
      <td class="l mono">${r.label}</td>
      <td class="mono ${sgn(r.spread)}">${fmt(r.spread,0)}</td>
      <td class="mono">${pct===null||pct===undefined?'<span class="dim">样本不足</span>':fmt(pct,1)+'%'}</td>
      <td><span class="heat"><span style="width:${hasPct(r)?Math.min(100,Math.abs(pct-50)*2):0}%"></span></span></td>
      <td class="mono">${r.z===null||r.z===undefined?'—':fmt(r.z,2)}</td>
      <td class="mono ${sgn(r.change_1m)}">${r.change_1m===null||r.change_1m===undefined?'—':(r.change_1m>0?'+':'')+fmt(r.change_1m,0)}</td>
      <td class="mono dim">${r.mean_hist===null||r.mean_hist===undefined?'—':fmt(r.mean_hist,0)}</td>
      <td class="mono dim">${r.n_history??0}</td>
      <td class="l"><span class="${pill}">${esc(r.grade)}</span></td>
      <td class="l">${trad}</td></tr>`;
  }).join('');
  tb.querySelectorAll('tr.rowlink').forEach(tr=>tr.onclick=()=>{
    state.selected=tr.dataset.p+'|'+tr.dataset.l; renderDetail(); renderRank(candidates());
  });
  document.getElementById('rankInfo').textContent=`${rows.length} 个组合 · 排序：${document.getElementById('fSort').selectedOptions?.[0]?.text || state.sort}`;
}

/* ---------- 渲染明细 ---------- */
function pickInitial(list){
  if(state.selected){
    const [p,l]=state.selected.split('|'); const r=list.find(x=>x.product===p&&x.label===l); if(r) return r;
  }
  const sc=list.filter(r=>r._scenario);
  const best=sc.filter(hasPct).sort((a,b)=>Math.abs(b.percentile-50)-Math.abs(a.percentile-50))[0];
  return best || sc[0] || list.find(hasPct) || list[0] || null;
}
function renderDetail(){
  const list=candidates(); const r=pickInitial(list);
  if(!r){ document.getElementById('detailPanel').style.display='none'; return; }
  const p=r.product, b=S.products[p];
  state.selected=p+'|'+r.label;
  const ind=IND.products[p]||{};
  // KPI
  const basis=b.rule? null:null;
  const kp=[
    {k:'品种/组合', v:`${b.name_cn} ${p}`, s:r.label, small:true},
    {k:'当前月差（近−远）', v:fmt(r.spread,0), s:'元/吨', cls:(r.spread??0)>0?'pos':'neg'},
    {k:'历史分位', v:hasPct(r)?fmt(r.percentile,1)+'%':'样本不足', s:hasPct(r)?`N=${r.n_history} 年可比样本`:'不给分位', cls:hasPct(r)&&Math.abs(r.percentile-50)>50-state.thr?'ext':''},
    {k:'Z 分数', v:r.z===null||r.z===undefined?'—':fmt(r.z,2), s:'相对历史均值'},
    {k:'近1月变化', v:r.change_1m===null||r.change_1m===undefined?'—':((r.change_1m>0?'+':'')+fmt(r.change_1m,0)), s:'元/吨', cls:sgn(r.change_1m)},
    {k:'历史均值 / 区间', v:r.mean_hist===null||r.mean_hist===undefined?'—':fmt(r.mean_hist,0), s:hasPct(r)?`${fmt(r.min_hist,0)} ~ ${fmt(r.max_hist,0)} (5–95%: ${fmt(r.q05,0)}~${fmt(r.q95,0)})`:''},
    {k:'评级', v:r.grade, s:r.direction==='insufficient'?'样本不足，不评级':'基于自身分布', cls:hasPct(r)&&Math.abs(r.percentile-50)>50-state.thr?'ext':''},
  ];
  document.getElementById('detailKpis').innerHTML=kp.map(x=>`<div class="kpi ${x.cls||''}"><div class="k">${x.k}</div>
      <div class="v" style="${x.small?'font-size:16px':'font-size:21px'}">${esc(x.v)}</div><div class="s">${esc(x.s)}</div></div>`).join('');

  // 期限结构
  const ts=b.term_structure||[];
  drawCurve(document.getElementById('cvCurve'), ts, [r.near, r.far]);
  document.getElementById('curveNote').innerHTML =
    `形态：<b>${esc(b.shape.type)}</b>　斜率 ${b.shape.slope_per_month} 元/月　单调性 r=${b.shape.monotonicity_r}` +
    (b.shape.biggest_step?`　最大单步跳变：${esc(b.shape.biggest_step.near_sym)}→${esc(b.shape.biggest_step.far_sym)} ${b.shape.biggest_step.diff} 元`:'');
  document.getElementById('curveNote').style.display='block';

  // 历史样本
  drawHist(document.getElementById('cvHist'), r);
  const hn=document.getElementById('histNote');
  if(!hasPct(r)) { hn.innerHTML=`该组合仅有 <b>${r.n_history||0}</b> 个可比历史年份，低于阈值 N=${state.minN}，<b>样本不足，不计算分位</b>。（如需提高覆盖，可放宽"同剩余期限周对齐"，但会降低可比性 —— 不建议以此换样本量。）`; hn.style.display='block'; }
  else { hn.innerHTML=`可比样本：${(r.history||[]).map(h=>`${h.year}: ${fmt(h.spread,0)}（${esc(h.date)}）`).join('　|　')}`; hn.style.display='block'; }

  // 45日序列
  drawSeries(document.getElementById('cvSeries'), r.series_30d||[]);

  // 合约明细
  const basisText = Q.price_basis_by_product?.[p]==='last' ? '(东方财富最新价)' : '(郑商所结算价)';
  const legRows=[r.near,r.far].map((s,i)=>{
    const c=(b.term_structure||[]).find(x=>x.symbol===s); if(!c) return '';
    const q=Q.contracts?.[s];
    const px=c.settle??c.close;
    return `<tr><td class="l mono">${s}</td><td class="mono">${fmt(px,0)}</td><td class="mono dim">${fmt(q?.close??c.close,0)}</td>
      <td class="mono">${fmt(c.oi,0)}</td><td class="mono">${c.months_out} 个月</td>
      <td class="l">${i===0?'近月':'远月'}${c.is_main?' · 主力':''}</td></tr>`;
  }).join('');
  document.querySelector('#legTable tbody').innerHTML=legRows+
    `<tr><td class="l" colspan="6" class="dim" style="color:var(--dim);font-size:12px">价差口径：${esc(Q.price_basis_by_product?.[p]||'settle')}${basisText}；合约乘数 ${b.rule.contract_unit_t} 吨/手，最小变动 ${b.rule.tick} 元/吨</td></tr>`;

  // 品种全部组合
  document.querySelector('#pairTable tbody').innerHTML=(b.pairs||[]).filter(x=>x.computable).map(x=>
    `<tr class="rowlink" data-l="${x.label}"><td class="l mono">${x.label}</td><td class="mono ${sgn(x.spread)}">${fmt(x.spread,0)}</td>
     <td class="mono">${x.percentile==null?'<span class="dim">样本不足</span>':fmt(x.percentile,1)+'%'}</td>
     <td class="mono">${x.z==null?'—':fmt(x.z,2)}</td><td class="mono ${sgn(x.change_1m)}">${x.change_1m==null?'—':fmt(x.change_1m,0)}</td>
     <td class="mono dim">${x.n_history??0}</td>
     <td class="l"><span class="pill ${hasPct(x)&&Math.abs(x.percentile-50)>50-state.thr?'ext':''}">${esc(x.grade)}</span></td></tr>`).join('')
     || '<tr><td colspan="7" class="empty">该品种在当前口径下无可计算组合</td></tr>';
  document.querySelectorAll('#pairTable tr.rowlink').forEach(tr=>tr.onclick=()=>{
    state.selected=p+'|'+tr.dataset.l; renderDetail(); renderRank(candidates());
  });

  // 产业面
  const ir=[];
  const w=ind.warrant;
  if(w) ir.push([`仓单（${w.source.includes('郑商所')?'交易所官方':'媒体转述'}）`, fmt(w.value,0), w.unit, '', w.date, w.confidence]);
  (ind.inventory||[]).forEach(x=>ir.push([x.name, fmt(x.value,2), x.unit, x.chg==null?'':`${x.chg>0?'+':''}${fmt(x.chg,2)}`, x.date, x.confidence]));
  if(ind.spot) ir.push([`现货 ${ind.spot.region||''}`, fmt(ind.spot.value,0), ind.spot.unit, '', ind.spot.date, ind.spot.confidence]);
  if(ind.spot_alt) ir.push([`现货 ${ind.spot_alt.region||''}`, fmt(ind.spot_alt.value,0), ind.spot_alt.unit, '', ind.spot_alt.date, ind.spot_alt.confidence]);
  if(ind.basis) ir.push(['基差（参考）', fmt(ind.basis.value,0), '元/吨', '', ind.basis.date||'', ind.basis.confidence]);
  document.querySelector('#indTable tbody').innerHTML=ir.map(x=>
    `<tr><td class="l">${esc(x[0])}</td><td class="mono">${esc(x[1])}</td><td class="l dim">${esc(x[2])}</td>
     <td class="mono ${sgn(parseFloat(x[3]))}">${esc(x[3])}</td><td class="l dim">${esc(x[4])}</td>
     <td class="l"><span class="pill ${x[5]==='A'?'ok':(x[5]==='D'?'no':'warn')}">${esc(x[5])}</span></td></tr>`).join('')
     || '<tr><td colspan="6" class="empty">该品种暂无产业面数据</td></tr>';

  // 事件
  const evs=(ind.events||[]).slice().sort((a,c)=>String(a.date).localeCompare(String(c.date)));
  document.getElementById('events').innerHTML=evs.map(e=>
    `<div class="ev ${esc(e.direction||'')}"><div class="d">${esc(e.date)}</div>
     <div class="t">${esc(e.event)}</div>
     <div class="dim" style="font-size:12px">影响：${esc(e.impact||'')}</div></div>`).join('')
     || '<div class="empty">该品种暂无事件记录</div>';

  renderRules();
  renderDataNotes();
}

/* ---------- 图表（Canvas 手绘，无外部库） ---------- */
function setup(cv){
  const dpr=window.devicePixelRatio||1; const w=cv.clientWidth||600; const h=cv.height||300;
  cv.width=w*dpr; cv.height=h*dpr; const ctx=cv.getContext('2d'); ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,w,h); return {ctx,w,h};
}
function axes(ctx,w,h,pad,xlab,ylab){
  ctx.strokeStyle='#26303f'; ctx.lineWidth=1; ctx.beginPath();
  ctx.moveTo(pad.l,h-pad.b); ctx.lineTo(w-pad.r,h-pad.b); ctx.moveTo(pad.l,pad.t); ctx.lineTo(pad.l,h-pad.b); ctx.stroke();
}
function drawCurve(cv, ts, marks){
  const {ctx,w,h}=setup(cv); const pad={l:56,r:16,t:16,b:34};
  const pts=ts.filter(r=>(r.settle??r.close));
  if(!pts.length){ ctx.fillStyle='#93a1b5'; ctx.fillText('无有效价格',20,40); return; }
  const ys=pts.map(r=>r.settle??r.close);
  const ymin=Math.min(...ys), ymax=Math.max(...ys); const sp=(ymax-ymin)||1;
  const X=i=> pad.l+(w-pad.l-pad.r)*(i/(Math.max(1,pts.length-1)));
  const Y=v=> pad.t+(h-pad.t-pad.b)*(1-(v-ymin)/sp);
  axes(ctx,w,h,pad);
  ctx.fillStyle='#93a1b5'; ctx.font='11px ui-monospace,Consolas,monospace';
  for(let g=0;g<=4;g++){ const v=ymin+sp*g/4; const y=Y(v); ctx.strokeStyle='rgba(38,48,63,.6)'; ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillStyle='#93a1b5'; ctx.fillText(v.toFixed(0),6,y+4); }
  // 线
  ctx.strokeStyle='#4da3ff'; ctx.lineWidth=2; ctx.beginPath();
  pts.forEach((r,i)=>{ const x=X(i), y=Y(r.settle??r.close); i?ctx.lineTo(x,y):ctx.moveTo(x,y); }); ctx.stroke();
  // 点 + 标签
  pts.forEach((r,i)=>{ const x=X(i), y=Y(r.settle??r.close);
    const hl=marks.includes(r.symbol);
    ctx.fillStyle=hl?'#ff5e8a':'#4da3ff'; ctx.beginPath(); ctx.arc(x,y,hl?5:3.2,0,7); ctx.fill();
    ctx.save(); ctx.translate(x,y-10); ctx.rotate(-Math.PI/4); ctx.fillStyle=hl?'#ff9db6':'#7f8fa5'; ctx.font='10px ui-monospace'; 
    ctx.textAlign='left'; ctx.fillText(r.symbol.replace(/^[A-Z]+/,''),0,0); ctx.restore();
    if(hl){ ctx.fillStyle='#ff9db6'; ctx.font='11px ui-monospace'; ctx.textAlign='center'; ctx.fillText((r.settle??r.close).toFixed(0),x,y-22); }
  });
  // x 轴月份
  ctx.fillStyle='#93a1b5'; ctx.font='11px ui-monospace'; ctx.textAlign='center';
  pts.forEach((r,i)=>{ if(i%2===0) ctx.fillText(r.m+'月',X(i),h-pad.b+16); });
  ctx.textAlign='left';
}
function drawHist(cv, r){
  const {ctx,w,h}=setup(cv); const pad={l:56,r:16,t:16,b:40};
  const hs=r.history||[];
  if(!hs.length){ ctx.fillStyle='#93a1b5'; ctx.font='12px sans-serif'; ctx.fillText('无可比历史样本（该组合在各历史年份均无同剩余期限的双边报价）',20,50); return; }
  const cur=r.spread; const vals=[...hs.map(x=>x.spread), ...(cur==null?[]:[cur])];
  let ymin=Math.min(...vals), ymax=Math.max(...vals); if(ymin===ymax){ymin-=10;ymax+=10;}
  const sp=ymax-ymin; ymin-=sp*0.12; ymax+=sp*0.12;
  const Y=v=> pad.t+(h-pad.t-pad.b)*(1-(v-ymin)/(ymax-ymin));
  axes(ctx,w,h,pad);
  const bw=(w-pad.l-pad.r)/Math.max(1,hs.length+1);
  // 零线
  const y0=Y(0); if(0>ymin&&0<ymax){ ctx.strokeStyle='#3a4a5f'; ctx.setLineDash([4,4]); ctx.beginPath(); ctx.moveTo(pad.l,y0); ctx.lineTo(w-pad.r,y0); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle='#5d7492'; ctx.font='10px ui-monospace'; ctx.fillText('0',pad.l-18,y0+3); }
  ctx.font='11px ui-monospace'; ctx.textAlign='center';
  hs.forEach((x,i)=>{ const cx=pad.l+bw*(i+0.5); const y=Y(x.spread); const ytop=Math.min(y,Y(0)), hh=Math.abs(Y(0)-y)||1;
    ctx.fillStyle='rgba(126,224,192,.75)'; ctx.fillRect(cx-bw*0.28,ytop,bw*0.56,Math.max(1,hh));
    ctx.fillStyle='#e6ebf2'; ctx.fillText(x.spread.toFixed(0),cx,ytop-5);
    ctx.fillStyle='#93a1b5'; ctx.fillText(String(x.year),cx,h-pad.b+16);
    ctx.fillStyle='#5d7492'; ctx.font='9px ui-monospace'; ctx.fillText(x.date.slice(5),cx,h-pad.b+28); ctx.font='11px ui-monospace';
  });
  if(cur!=null){
    const cx=pad.l+bw*(hs.length+0.5); const y=Y(cur);
    ctx.fillStyle='#ff5e8a'; ctx.fillRect(cx-bw*0.28,Math.min(y,Y(0)),bw*0.56,Math.max(1,Math.abs(Y(0)-y)));
    ctx.fillStyle='#ff8fab'; ctx.fillText(cur.toFixed(0),cx,y-5);
    ctx.fillStyle='#ff9db6'; ctx.fillText('当前',cx,h-pad.b+16);
    ctx.fillStyle='#5d7492'; ctx.fillText(r.as_of||'',cx,h-pad.b+28);
  }
  ctx.textAlign='left';
  // 均值线
  if(r.mean_hist!=null){ const y=Y(r.mean_hist); ctx.strokeStyle='#ffc857'; ctx.setLineDash([5,4]); ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle='#ffc857'; ctx.fillText('均值 '+r.mean_hist.toFixed(0), w-pad.r-70, y-4); }
}
function drawSeries(cv, s){
  const {ctx,w,h}=setup(cv); const pad={l:56,r:16,t:14,b:32};
  if(!s.length){ ctx.fillStyle='#93a1b5'; ctx.font='12px sans-serif'; ctx.fillText('无近 45 日序列',20,50); return; }
  const ys=s.map(x=>x.spread); let ymin=Math.min(...ys), ymax=Math.max(...ys); if(ymin===ymax){ymin-=5;ymax+=5;}
  const pd=(ymax-ymin)*0.15; ymin-=pd; ymax+=pd;
  const X=i=> pad.l+(w-pad.l-pad.r)*(i/Math.max(1,s.length-1));
  const Y=v=> pad.t+(h-pad.t-pad.b)*(1-(v-ymin)/(ymax-ymin));
  axes(ctx,w,h,pad);
  ctx.fillStyle='#93a1b5'; ctx.font='10px ui-monospace';
  for(let g=0;g<=3;g++){ const v=ymin+(ymax-ymin)*g/3, y=Y(v); ctx.strokeStyle='rgba(38,48,63,.6)'; ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke(); ctx.fillText(v.toFixed(0),6,y+3); }
  ctx.strokeStyle='#7ee0c0'; ctx.lineWidth=2; ctx.beginPath();
  s.forEach((x,i)=>{ const px=X(i),py=Y(x.spread); i?ctx.lineTo(px,py):ctx.moveTo(px,py); }); ctx.stroke();
  ctx.fillStyle='#7ee0c0'; const lx=X(s.length-1), ly=Y(s[s.length-1].spread);
  ctx.beginPath(); ctx.arc(lx,ly,3.5,0,7); ctx.fill();
  ctx.font='11px ui-monospace'; ctx.textAlign='right'; ctx.fillText(s[s.length-1].spread.toFixed(0),lx-6,ly-8);
  ctx.textAlign='left'; ctx.fillStyle='#93a1b5'; ctx.fillText(s[0].date.slice(5),pad.l,h-pad.b+16);
  ctx.textAlign='right'; ctx.fillText(s[s.length-1].date.slice(5),w-pad.r,h-pad.b+16); ctx.textAlign='left';
}

/* ---------- 规则表 ---------- */
function renderRules(){
  document.querySelector('#ruleTable tbody').innerHTML=Object.entries(S.products).map(([p,b])=>{
    const mo=(b.rule.listed_months||[]).join(',');
    return `<tr><td class="l">${p} ${b.name_cn}</td><td class="l">${esc(b.exchange_cn)} (${b.exchange})</td>
      <td class="l mono">${mo==='1,2,3,4,5,6,7,8,9,10,11,12'?'1–12 全月':mo}</td>
      <td class="mono">${b.rule.contract_unit_t} 吨/手</td><td class="mono">${b.rule.tick} 元/吨</td>
      <td class="mono">${b.rule.min_margin_pct}%</td><td class="l dim">${esc(b.rule.last_trading_day_rule)}</td>
      <td class="l mono">${(b.rule.main_months||[]).map(m=>m+'月').join('/')}</td>
      <td class="mono">${(b.term_structure||[]).length} 个</td></tr>`;
  }).join('');
}
function renderDataNotes(){
  const src=Q.sources||{};
  const rows=[
    ['郑商所日行情', src.czce_daily?.ok?'✓ 已抓取':'✗ 失败', src.czce_daily?.url||''],
    ['郑商所仓单日报', src.czce_warrant?.ok?'✓ 已抓取':'✗ 失败', src.czce_warrant?.url||''],
    ['大商所PP行情(东财)', src.em_dce?.ok?('✓ 已抓取('+(src.em_dce.n||0)+'合约)'):'✗ 失败', src.em_dce?.url||'大商所官网对脚本返回412'],
    ['逐合约历史日线', '✓ 276 个合约（2021-01 ~ 2026-10）', '新浪财经 InnerFuturesNewService.getDailyKLine'],
  ];
  document.getElementById('dataNotes').innerHTML=`<table><thead><tr><th class="l">数据源</th><th class="l">状态</th><th class="l">地址/说明</th></tr></thead>
    <tbody>${rows.map(r=>`<tr><td class="l">${esc(r[0])}</td><td class="l">${esc(r[1])}</td><td class="l src">${esc(r[2])}</td></tr>`).join('')}</tbody></table>
    <div class="note" style="margin-top:12px">
      <b>月差定义：</b>近月 − 远月（元/吨）。正值＝正向市场（近月升水，contango）；负值＝反向市场（近月贴水）。<br>
      <b>可比样本：</b>同一品种、同一(近月,远月)月份组合、同一"剩余期限整周数"，每年取 1 个样本（2022–2026）。不同月份组合<b>分别统计</b>，绝不合并为一个分布。<br>
      <b>缺失处理：</b>结算价为空/为0、或成交量与持仓量同时为0 的交易日视为无效，直接跳过；不插值、不前向填充、不用主力连续合约（换月会制造假跳变）。
    </div>
    <div class="disc"><b>重要声明：</b>本页给出的是"期限结构在自身历史中的位置"，用于为基本面研究提供线索。<b>异常月差本身不等于套利机会</b>，未扣除仓储费、资金成本、交割成本、品级与地区升贴水，也未考虑流动性。不构成任何交易建议。</div>`;
}

/* ---------- 主渲染 ---------- */
function render(){
  const list=candidates();
  renderKpis(list);
  state.selected=null;
  renderDetail();
  renderRank(list);
  const notes=(S.notes||[]).slice(0,1).join(' ');
  document.getElementById('scanNote').innerHTML=`扫描口径：所选品种，<b>${document.getElementById('fScenario').selectedOptions?.[0]?.text || '默认口径'}</b>；
    排除最前两个交割月（临近交割，报价受单边交割逻辑扭曲）。${esc(notes)}`;
}
document.querySelectorAll('.chip').forEach(c=>c.remove());
window.addEventListener('resize',()=>{renderDetail();});
render();"""

if __name__ == "__main__":
    main()
