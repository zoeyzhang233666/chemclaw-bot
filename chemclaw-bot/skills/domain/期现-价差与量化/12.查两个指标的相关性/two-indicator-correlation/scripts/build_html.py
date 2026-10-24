# -*- coding: utf-8 -*-
"""构建交互式 HTML 研究报告（自包含，无外部依赖；数据与事件表内嵌，前端可现场重算）。

用法：python scripts/build_html.py
依赖：corrlib / analyze / events；输出 docs/correlation-report.html
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import corrlib as C  # noqa: E402
from events import EVENTS, META as EVENT_META  # noqa: E402

DATA_CSV = os.path.join(ROOT, 'data', 'demo_methanol_weekly.csv')
META_JSON = os.path.join(ROOT, 'data', 'data_meta.json')
OUT = os.path.join(ROOT, 'docs', 'correlation-report.html')

# 可选参数：--csv 换数据源（列名约定见 data_meta.json / examples 目录）  --out 换输出路径
for _i, _a in enumerate(sys.argv):
    if _a == '--csv' and _i + 1 < len(sys.argv):
        DATA_CSV = os.path.abspath(sys.argv[_i + 1])
    if _a == '--meta' and _i + 1 < len(sys.argv):
        META_JSON = os.path.abspath(sys.argv[_i + 1])
    if _a == '--out' and _i + 1 < len(sys.argv):
        OUT = os.path.abspath(sys.argv[_i + 1])


def load():
    rows = list(csv.DictReader(open(DATA_CSV, encoding='utf-8-sig')))
    meta = json.load(open(META_JSON, encoding='utf-8'))
    return rows, meta


def build_payload():
    rows, meta = load()
    dates = [r['week_ending'] for r in rows]
    series = {
        'inventory_total': [float(r['inventory_total']) for r in rows],
        'inventory_ec': [float(r['inventory_ec']) for r in rows],
        'inventory_sc': [float(r['inventory_sc']) for r in rows],
        'spot_taicang': [float(r['spot_taicang']) for r in rows],
        'coal_5500': [float(r['coal_5500']) for r in rows],
        'op_rate': [float(r['op_rate']) for r in rows],
        'arrival': [float(r['arrival']) for r in rows],
        'demand': [float(r['demand']) for r in rows],
    }
    labels = {
        'inventory_total': ('港口库存（总）', '万吨'),
        'inventory_ec': ('港口库存（华东）', '万吨'),
        'inventory_sc': ('港口库存（华南）', '万吨'),
        'spot_taicang': ('江苏太仓出罐现货价', '元/吨'),
        'coal_5500': ('动力煤 5500 现货（成本参照）', '元/吨'),
        'op_rate': ('下游加权开工率', '%'),
        'arrival': ('周度到港量', '万吨'),
        'demand': ('周度下游提货量', '万吨'),
    }
    return {'rows': rows, 'meta': meta, 'dates': dates, 'series': series,
            'labels': labels, 'events': EVENTS, 'eventMeta': EVENT_META}


HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>两指标相关性研究｜甲醇港口库存 × 太仓现货价</title>
<style>
:root{
  --bg:#0e1116; --panel:#161b23; --panel2:#1b2230; --line:#26303f; --txt:#e6ebf2; --dim:#93a1b5;
  --acc:#4da3ff; --acc2:#7ee0c0; --neg:#ff6b81; --pos:#3ddc97; --warn:#ffc857; --demo:#f0a35e;
  --shadow:0 10px 30px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(180deg,#0b0e13,#0e1116 260px);color:var(--txt);
  font:14px/1.6 "Segoe UI","Microsoft YaHei",system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--acc)}
.wrap{max-width:1440px;margin:0 auto;padding:0 22px 64px}
header{padding:26px 0 14px;border-bottom:1px solid var(--line);margin-bottom:20px}
.h1{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
h1{font-size:25px;margin:0;letter-spacing:.5px;font-weight:650}
.sub{color:var(--dim);font-size:13px}
.badge{display:inline-flex;align-items:center;gap:6px;padding:2px 9px;border-radius:999px;font-size:12px;
  border:1px solid var(--line);background:var(--panel2);color:var(--dim)}
.badge.demo{color:#2a1a08;background:var(--demo);border-color:var(--demo);font-weight:700}
.grid{display:grid;gap:16px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow)}
.panel h2{font-size:15px;margin:0 0 10px;font-weight:650;letter-spacing:.3px;display:flex;gap:8px;align-items:center}
.panel h2 .tag{font-size:11px;color:var(--dim);font-weight:500;border:1px solid var(--line);padding:1px 7px;border-radius:999px}
.kpis{grid-template-columns:repeat(auto-fit,minmax(190px,1fr));margin-bottom:16px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 15px;position:relative;overflow:hidden}
.kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--acc);opacity:.9}
.kpi.neg:before{background:var(--neg)} .kpi.pos:before{background:var(--pos)}
.kpi .k{color:var(--dim);font-size:12px} .kpi .v{font-size:24px;font-weight:680;letter-spacing:.4px;margin-top:2px}
.kpi .s{color:var(--dim);font-size:12px;margin-top:2px}
.mono{font-variant-numeric:tabular-nums;font-family:ui-monospace,Consolas,monospace}
.controls{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end}
.ctrl{display:flex;flex-direction:column;gap:5px;min-width:132px}
.ctrl label{font-size:12px;color:var(--dim)}
select,input[type=number],input[type=date]{background:var(--panel2);color:var(--txt);border:1px solid var(--line);
  border-radius:9px;padding:7px 9px;font-size:13px;outline:none}
select:focus,input:focus{border-color:var(--acc)}
button{background:var(--acc);color:#04121f;border:0;border-radius:9px;padding:8px 14px;font-weight:650;cursor:pointer;font-size:13px}
button.ghost{background:transparent;color:var(--txt);border:1px solid var(--line);font-weight:500}
button:hover{filter:brightness(1.08)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.chip{font-size:12px;padding:4px 10px;border-radius:999px;border:1px solid var(--line);color:var(--dim);cursor:pointer;user-select:none}
.chip.on{background:rgba(77,163,255,.15);border-color:var(--acc);color:#cfe6ff}
canvas{width:100%;display:block}
.chartbox{position:relative}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin:6px 0 2px}
.legend i{display:inline-block;width:16px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{color:var(--dim);font-weight:600;font-size:12px;text-align:right;position:sticky;top:0;background:var(--panel)}
td.l,th.l{text-align:left}
tr:hover td{background:rgba(255,255,255,.02)}
.scroll{max-height:340px;overflow:auto;border-radius:10px}
.pill{font-size:11px;padding:1px 7px;border-radius:999px;border:1px solid var(--line);color:var(--dim)}
.pill.ok{color:var(--pos);border-color:rgba(61,220,151,.4)}
.pill.no{color:var(--neg);border-color:rgba(255,107,129,.4)}
.pill.mid{color:var(--warn);border-color:rgba(255,200,87,.4)}
.note{font-size:12.5px;color:var(--dim);line-height:1.75}
.note b{color:#cbd6e6;font-weight:600}
.warnbox{border-left:3px solid var(--warn);background:rgba(255,200,87,.07);padding:10px 14px;border-radius:0 10px 10px 0;font-size:13px}
.errbox{border-left:3px solid var(--neg);background:rgba(255,107,129,.08);padding:10px 14px;border-radius:0 10px 10px 0;font-size:13px}
.demobox{border-left:3px solid var(--demo);background:rgba(240,163,94,.08);padding:10px 14px;border-radius:0 10px 10px 0;font-size:13px}
.two{grid-template-columns:1fr 1fr}
.three{grid-template-columns:1.35fr 1fr}
@media(max-width:1100px){.two,.three{grid-template-columns:1fr}}
.eventlist{display:flex;flex-direction:column;gap:10px;max-height:420px;overflow:auto}
.ev{border:1px solid var(--line);border-radius:10px;padding:9px 12px;background:var(--panel2)}
.ev .t{font-weight:600;font-size:13px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.ev .d{color:var(--dim);font-size:11.5px} .ev .n{color:#c2ccdb;font-size:12.5px;margin-top:4px;line-height:1.65}
.kind{font-size:11px;padding:1px 7px;border-radius:999px;background:rgba(77,163,255,.16);color:#9fc9ff;border:1px solid rgba(77,163,255,.3)}
footer{color:var(--dim);font-size:12px;margin-top:26px;border-top:1px solid var(--line);padding-top:14px;line-height:1.8}
.tooltip{position:fixed;pointer-events:none;background:#0a0f16ee;border:1px solid var(--line);border-radius:9px;
  padding:8px 11px;font-size:12px;line-height:1.55;color:var(--txt);z-index:99;display:none;box-shadow:var(--shadow);white-space:nowrap}
.hint{font-size:12px;color:var(--dim);margin-top:6px}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="h1">
    <h1>两指标相关性研究：甲醇港口库存 × 太仓现货价</h1>
    <span class="badge demo" id="demoBadge">示例数据 · DEMO</span>
    <span class="badge">周度 · 156 期 · 2023-10-11 ~ 2026-09-30</span>
    <span class="badge">Pearson / Spearman · 滚动 12/26/52 周</span>
  </div>
  <div class="sub" style="margin-top:8px">
    本页回答一个问题：<b>港口库存与现货价格，到底在什么时候、以什么形态相关？</b>
    库存与价格各有“水平”和“变化”两种形态，必须分开算；相关性强弱会随市场阶段变化，因此要给出滚动曲线与分阶段结果，并对趋势、自相关、共同外部因素做伪相关排查。
  </div>
</header>

<div class="grid kpis" id="kpis"></div>

<section class="panel" style="margin-bottom:16px">
  <h2>① 交互控制 <span class="tag">改动任一参数后全页指标、图表、表格实时重算</span></h2>
  <div class="controls">
    <div class="ctrl"><label>指标 X（库存口径）</label>
      <select id="xsel">
        <option value="inventory_total">港口库存（总）</option>
        <option value="inventory_ec">港口库存（华东）</option>
        <option value="inventory_sc">港口库存（华南）</option>
      </select></div>
    <div class="ctrl"><label>X 的数据形态</label>
      <select id="xform">
        <option value="level">原值（水平）</option>
        <option value="change">一阶差分（周变化）</option>
        <option value="pct">环比变化率 %</option>
      </select></div>
    <div class="ctrl"><label>指标 Y（价格口径）</label>
      <select id="ysel">
        <option value="spot_taicang">江苏太仓出罐现货价</option>
        <option value="coal_5500">动力煤 5500（成本参照）</option>
        <option value="op_rate">下游加权开工率</option>
      </select></div>
    <div class="ctrl"><label>Y 的数据形态</label>
      <select id="yform">
        <option value="pct">环比变化率 %</option>
        <option value="change">一阶差分</option>
        <option value="level">原值（水平）</option>
      </select></div>
    <div class="ctrl"><label>滚动窗口（周）</label>
      <select id="win"><option>12</option><option selected>26</option><option>52</option></select></div>
    <div class="ctrl"><label>窗口最小有效配对数</label><input id="minp" type="number" value="21" min="5" max="60" step="1"></div>
    <div class="ctrl"><label>起始日期</label><input id="d1" type="date" value="2023-10-11"></div>
    <div class="ctrl"><label>结束日期</label><input id="d2" type="date" value="2026-09-30"></div>
    <div class="ctrl"><label>离群处理</label>
      <select id="outl">
        <option value="none">保留全部</option>
        <option value="winsor">Winsorize 5%/95%</option>
        <option value="drop">剔除极值（5%/95%，任一侧）</option>
      </select></div>
    <button id="reset" class="ghost">恢复默认</button>
  </div>
  <div class="hint" id="ctrlHint"></div>
</section>

<div class="grid three" style="margin-bottom:16px">
  <section class="panel">
    <h2>② 双序列对照 <span class="tag" id="tagA"></span></h2>
    <div class="legend"><span><i style="background:var(--acc)"></i><span id="lgA"></span></span>
      <span><i style="background:var(--acc2)"></i><span id="lgB"></span></span></div>
    <div class="chartbox"><canvas id="cvSeries" height="300"></canvas></div>
    <div class="hint">库存与价格各自标准化（z 分数）显示，便于同时观察形态与转折；悬停查看原始值。</div>
  </section>
  <section class="panel">
    <h2>③ 散点与趋势拟合 <span class="tag" id="tagB"></span></h2>
    <div class="chartbox"><canvas id="cvScatter" height="300"></canvas></div>
    <div class="hint" id="fitHint"></div>
  </section>
</div>

<section class="panel" style="margin-bottom:16px">
  <h2>④ 滚动相关系数 <span class="tag" id="tagC">窗口 26 周 · 点击异常区间查看对应区间明细</span></h2>
  <div class="legend">
    <span><i style="background:var(--acc)"></i>滚动 Pearson r</span>
    <span><i style="background:rgba(147,161,181,.55)"></i>±0.2 / ±0.5 参考带</span>
    <span><i style="background:var(--warn)"></i>符号反转区间</span>
    <span><i style="background:var(--neg)"></i>|r| 骤降（脱钩）</span>
  </div>
  <div class="chartbox"><canvas id="cvRoll" height="290"></canvas></div>
  <div class="hint">灰色虚线为窗口有效配对数不足的区间：<b>不计算</b>，不插值。</div>
</section>

<div class="grid two" style="margin-bottom:16px">
  <section class="panel">
    <h2>⑤ 选中区间明细 <span class="tag" id="selTag">未选择</span></h2>
    <div id="selDetail" class="note">在上图点击任意一点或异常区间，这里显示该窗口覆盖的库存/价格走势、期间统计量与区间内行业事件。</div>
  </section>
  <section class="panel">
    <h2>⑥ 行业事件与口径提示 <span class="tag">仅作解释背景，不构成因果或交易结论</span></h2>
    <div class="eventlist" id="events"></div>
  </section>
</div>

<div class="grid two" style="margin-bottom:16px">
  <section class="panel">
    <h2>⑦ 分阶段结果 <span class="tag">按业务阶段切分后重算</span></h2>
    <div class="scroll"><table id="phaseTbl"></table></div>
    <div class="hint">阶段断点可在脚本参数 <span class="mono">--breaks</span> 中调整，示例断点为季度/年度边界。</div>
  </section>
  <section class="panel">
    <h2>⑧ 形态组合矩阵 <span class="tag">水平对水平 ≠ 变化对变化</span></h2>
    <div class="scroll"><table id="matrixTbl"></table></div>
    <div class="hint">同一对指标的四种组合相关系数可以完全不同；引用结论时必须说明用的是哪一种。</div>
  </section>
</div>

<div class="grid two" style="margin-bottom:16px">
  <section class="panel">
    <h2>⑨ 滞后相关 <span class="tag">正值 = X 领先 Y</span></h2>
    <div class="chartbox"><canvas id="cvLag" height="220"></canvas></div>
    <div class="hint">相关不区分方向；滞后结构只能提示“先后顺序”,不能单独证明因果。</div>
  </section>
  <section class="panel">
    <h2>⑩ 统计稳健性与伪相关诊断</h2>
    <div class="scroll"><table id="robustTbl"></table></div>
  </section>
</div>

<section class="panel">
  <h2>⑪ 结论与使用限制</h2>
  <div id="concl" class="note"></div>
</section>

<footer>
  <div><b>数据状态：</b><span id="footDemo"></span></div>
  <div><b>方法：</b>Pearson（线性）、Spearman（单调）、Fisher-z 95% 置信区间、Newey-West HAC 标准误、考虑自相关的有效样本量、去趋势与一阶差分检验、偏相关（控制共同外部因素）、滞后 0–4 期相关。</div>
  <div><b>声明：</b>相关性不等于因果关系。本页不给交易建议、不做价格预测。滚动窗口在有效样本不足时留空而不外推。</div>
</footer>
</div>
<div class="tooltip" id="tip"></div>

<script>
const PAYLOAD = __PAYLOAD__;
const S = PAYLOAD.series, D = PAYLOAD.dates, R = PAYLOAD.rows, EV = PAYLOAD.events, L = PAYLOAD.labels;

/* ---------------- 统计工具（与 Python 端同算法） ---------------- */
const num = v => (v === null || v === undefined || v === '' || isNaN(v)) ? null : +v;
function mean(a){let s=0,n=0;for(const v of a){if(v!==null){s+=v;n++;}}return n?s/n:null;}
function pearson(x,y){const p=[];for(let i=0;i<x.length;i++){if(x[i]!==null&&y[i]!==null)p.push([x[i],y[i]]);}
  const n=p.length; if(n<3)return null;
  const mx=mean(p.map(v=>v[0])), my=mean(p.map(v=>v[1]));
  let sxy=0,sxx=0,syy=0; for(const [a,b] of p){sxy+=(a-mx)*(b-my);sxx+=(a-mx)**2;syy+=(b-my)**2;}
  if(sxx<=1e-12||syy<=1e-12)return null; return sxy/Math.sqrt(sxx*syy);}
function rank(xs){const n=xs.length,idx=[...Array(n).keys()].sort((i,j)=>xs[i]-xs[j]);const r=new Array(n);let i=0;
  while(i<n){let j=i;while(j+1<n&&xs[idx[j+1]]===xs[idx[i]])j++;const av=(i+j)/2+1;for(let k=i;k<=j;k++)r[idx[k]]=av;i=j+1;}return r;}
function spearman(x,y){const p=[];for(let i=0;i<x.length;i++){if(x[i]!==null&&y[i]!==null)p.push([x[i],y[i]]);}
  if(p.length<3)return null; return pearson(rank(p.map(v=>v[0])),rank(p.map(v=>v[1])));}
function erf(x){const s=Math.sign(x);x=Math.abs(x);const a1=.254829592,a2=-.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429,p=.3275911;
  const t=1/(1+p*x);const y=1-(((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*Math.exp(-x*x);return s*y;}
function tPval(t,df){if(t===null||df<=0)return null;t=Math.abs(t);
  // 用不完全beta的级数近似（只需p值量级）
  const x=df/(df+t*t); return betainc(df/2,0.5,x);}
function betainc(a,b,x){if(x<=0)return 0;if(x>=1)return 1;
  const lb=Math.log(gamma(a))+Math.log(gamma(b))-Math.log(gamma(a+b));
  const front=Math.exp(Math.log(x)*a+Math.log(1-x)*b-lb)/a;
  return x<(a+1)/(a+b+2)?front*betacf(a,b,x):1-Math.exp(Math.log(1-x)*b+Math.log(x)*a-lb)/b*betacf(b,a,1-x);}
function betacf(a,b,x){let qab=a+b,qap=a+1,qam=a-1,c=1,d=1-qab*x/qap;if(Math.abs(d)<1e-300)d=1e-300;d=1/d;let h=d;
  for(let m=1;m<=300;m++){const m2=2*m;let aa=m*(b-m)*x/((qam+m2)*(a+m2));d=1+aa*d;if(Math.abs(d)<1e-300)d=1e-300;c=1+aa/c;
    if(Math.abs(c)<1e-300)c=1e-300;d=1/d;h*=d*c;aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2));d=1+aa*d;
    if(Math.abs(d)<1e-300)d=1e-300;c=1+aa/c;if(Math.abs(c)<1e-300)c=1e-300;d=1/d;const de=d*c;h*=de;if(Math.abs(de-1)<1e-12)break;}
  return h;}
function gamma(z){const g=7,C=[0.99999999999980993,676.5203681218851,-1259.1392167224028,771.32342877765313,-176.61502916214059,12.507343278686905,-0.13857109526572012,9.9843695780195716e-6,1.5056327351493116e-7];
  if(z<0.5)return Math.PI/(Math.sin(Math.PI*z)*gamma(1-z));z-=1;let x=C[0];for(let i=1;i<g+2;i++)x+=C[i]/(z+i);
  const t=z+g+0.5;return Math.sqrt(2*Math.PI)*Math.pow(t,z+0.5)*Math.exp(-t)*x;}
function corrStats(x,y){const r=pearson(x,y);if(r===null)return {r:null,n:0};
  const p=[];for(let i=0;i<x.length;i++)if(x[i]!==null&&y[i]!==null)p.push(1);const n=p.length;
  const out={r,n}; if(n>2&&Math.abs(r)<1){const t=r*Math.sqrt((n-2)/(1-r*r));out.t=t;out.p=tPval(t,n-2);}
  else if(Math.abs(r)>=1){out.t=Infinity;out.p=0;}
  if(n>3){const z=Math.atanh(Math.max(-0.999999,Math.min(0.999999,r)));const se=1/Math.sqrt(n-3);
    out.ci_lo=Math.tanh(z-1.959964*se);out.ci_hi=Math.tanh(z+1.959964*se);}
  return out;}
function autocorr(x,lag=1){const n=x.length;if(n<=lag+2)return null;const m=mean(x);
  let v=0;for(const a of x)v+=(a-m)**2;if(v<=0)return null;let c=0;for(let i=lag;i<n;i++)c+=(x[i]-m)*(x[i-lag]-m);return c/v;}
function transform(arr,kind){const n=arr.length;const out=new Array(n).fill(null);
  if(kind==='level')return arr.slice();
  for(let i=1;i<n;i++){const a=arr[i],b=arr[i-1];if(a===null||b===null||b===undefined)continue;
    if(kind==='change')out[i]=a-b; else if(kind==='pct')out[i]=(a-b)/Math.abs(b)*100;}
  return out;}
function linreg(x,y){const p=[];for(let i=0;i<x.length;i++)if(x[i]!==null&&y[i]!==null)p.push([x[i],y[i]]);
  const n=p.length;if(n<3)return null;const mx=mean(p.map(v=>v[0])),my=mean(p.map(v=>v[1]));
  let sxx=0,sxy=0,syy=0;for(const [a,b] of p){sxx+=(a-mx)**2;sxy+=(a-mx)*(b-my);syy+=(b-my)**2;}
  if(sxx<=1e-12)return null;const b=sxy/sxx,a=my-b*mx;const r2=syy>0?(sxy*sxy)/(sxx*syy):null;
  return {a,b,r2,pts:p};}
function detrendSeries(y){const t=[...Array(y.length).keys()];const f=linreg(t,y);if(!f)return null;
  const out=new Array(y.length).fill(null);
  for(let i=0;i<y.length;i++){let v=0,c=0;for(const [tt,yy] of f.pts){v+=yy-(f.a+f.b*tt);c++;}
    out[i]=y[i]==null?null:null;}
  // 直接用拟合残差
  const res=y.map((v,i)=>v==null?null:v-(f.a+f.b*i)); return res;}
function partial(x,y,z){const p=[];for(let i=0;i<x.length;i++)if(x[i]!==null&&y[i]!==null&&z[i]!==null)p.push([x[i],y[i],z[i]]);
  if(p.length<6)return null;
  const rx=linreg(p.map(v=>v[2]),p.map(v=>v[0])),ry=linreg(p.map(v=>v[2]),p.map(v=>v[1]));
  const ex=p.map((v,i)=>v[0]-(rx.a+rx.b*v[2])),ey=p.map((v,i)=>v[1]-(ry.a+ry.b*v[2]));
  return pearson(ex,ey);}
function winsor(arr,p=0.05){const idx=arr.map((v,i)=>[v,i]).filter(v=>v[0]!==null).sort((a,b)=>a[0]-b[0]);
  if(idx.length<10)return arr.slice();const k=Math.max(1,Math.round(idx.length*p));
  const lo=idx[k][0],hi=idx[idx.length-1-k][0];
  return arr.map(v=>v===null?null:Math.min(hi,Math.max(lo,v)));}
function dropExtreme(x,y,p=0.05){const n=x.length,k=Math.max(1,Math.round(n*p));
  const ix=[...Array(n).keys()].sort((i,j)=>x[i]-x[j]);const iy=[...Array(n).keys()].sort((i,j)=>y[i]-y[j]);
  const ex=new Set([...ix.slice(0,k),...ix.slice(-k),...iy.slice(0,k),...iy.slice(-k)]);
  const a=new Array(n).fill(null),b=new Array(n).fill(null);
  for(let i=0;i<n;i++)if(!ex.has(i)){a[i]=x[i];b[i]=y[i];}
  return [a,b];}
const fmt=(v,d=3)=>v===null||v===undefined||isNaN(v)?'—':(+v).toFixed(d);
const pfmt=p=>p===null||p===undefined?'—':(p<1e-4?'<1e-4':(p<0.001?p.toExponential(1):p.toFixed(3)));
const sig=p=>p===null?'':p<0.01?'***':p<0.05?'**':p<0.1?'*':'';
const clampR=v=>Math.max(-1,Math.min(1,v));

/* ---------------- 状态 ---------------- */
const DEF = {x:'inventory_total',xf:'level',y:'spot_taicang',yf:'pct',win:26,minp:21,d1:D[0],d2:D[D.length-1],outl:'none'};
let ST = {...DEF};
let SEL = null;

function sliceRange(){
  const i0=Math.max(0,D.indexOf(ST.d1)), i1=D.indexOf(ST.d2);
  const a = i0<0?0:i0, b = i1<0?D.length-1:i1;
  return [Math.min(a,b), Math.max(a,b)];
}
function compute(){
  const xRaw=S[ST.x], yRaw=S[ST.y];
  let x=transform(xRaw,ST.xf), y=transform(yRaw,ST.yf);
  const [a,b]=sliceRange();
  const dates=D.slice(a,b+1), xr=x.slice(a,b+1), yr=y.slice(a,b+1);
  if(ST.outl==='winsor'){x=winsor(xr);y=winsor(yr);} else if(ST.outl==='drop'){const r=dropExtreme(xr,yr);x=r[0];y=r[1];}
  else {x=xr;y=yr;}
  const pairs=[];for(let i=0;i<x.length;i++)if(x[i]!==null&&y[i]!==null)pairs.push(i);
  const st=corrStats(x,y);
  const sp=spearman(x,y);
  const tIdx=[...Array(x.length).keys()];
  const dtX=detrendSeries(x), dtY=detrendSeries(y);
  const detR=(dtX&&dtY)?pearson(dtX,dtY):null;
  const diffX=transform(x,'change'), diffY=transform(y,'change');
  const diffR=pearson(diffX,diffY);
  const r1x=autocorr(pairs.map(i=>x[i])), r1y=autocorr(pairs.map(i=>y[i]));
  let neff=pairs.length;
  if(r1x!==null&&r1y!==null&&(1+r1x*r1y)>1e-6){neff=pairs.length*(1-r1x*r1y)/(1+r1x*r1y);neff=Math.max(3,Math.min(pairs.length,neff));}
  const pEff=(st.r!==null&&Math.abs(st.r)<1)?tPval(st.r*Math.sqrt((neff-2)/(1-st.r**2)),neff-2):null;
  const pr=partial(x,y,S.coal_5500.slice(a,b+1));
  // 滚动
  const W=ST.win, need=ST.minp;
  const roll=[],pairsCnt=[];
  for(let t=0;t<x.length;t++){const lo=t-W+1;if(lo<0){roll.push(null);pairsCnt.push(0);continue;}
    let c=0;for(let i=lo;i<=t;i++)if(x[i]!==null&&y[i]!==null)c++;pairsCnt.push(c);
    roll.push(c<need?null:pearson(x.slice(lo,t+1),y.slice(lo,t+1)));}
  // 异常区间：符号反转 或 |r| 相对前段骤降 / 进入 |r|<0.2
  const anomalies=[];
  for(let t=1;t<roll.length;t++){
    const p=roll[t-1],c=roll[t];if(p===null||c===null)continue;
    if(p*c<0&&Math.abs(c-p)>0.12) anomalies.push({t,kind:'reversal',msg:'符号反转'});
    else if(Math.abs(c)<0.2&&Math.abs(p)>=0.45) anomalies.push({t,kind:'decouple',msg:'相关性脱钩（|r|<0.2）'});
  }
  // 滞后
  const lagMax=4, lags=[];
  for(let Lg=-lagMax;Lg<=lagMax;Lg++){
    let xx,yy;
    if(Lg===0){xx=x;yy=y;}
    else if(Lg>0){xx=x.slice(0,x.length-Lg);yy=y.slice(Lg);}
    else{xx=x.slice(-Lg);yy=y.slice(0,y.length+Lg);}
    lags.push({lag:Lg,r:pearson(xx,yy)});
  }
  return {dates,x,y,xRaw:xRaw.slice(a,b+1),yRaw:yRaw.slice(a,b+1),a,b,st,sp,detR,diffR,r1x,r1y,neff,pEff,pr,roll,pairsCnt,anomalies,lags,st_pts:pairs.length};
}

/* ---------------- 绘图 ---------------- */
function setupCanvas(cv,H){const dpr=window.devicePixelRatio||1;const w=cv.clientWidth;
  cv.width=w*dpr;cv.height=H*dpr;cv.style.height=H+'px';const ctx=cv.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,H);return {ctx,w,H};}
function niceTicks(min,max,n=5){const span=max-min||1;const step0=span/n;const mag=Math.pow(10,Math.floor(Math.log10(step0)));
  const norm=step0/mag;const step=(norm<1.5?1:norm<3?2:norm<7?5:10)*mag;const t=[];for(let v=Math.ceil(min/step)*step;v<=max+1e-9;v+=step)t.push(+v.toFixed(10));return t;}

function drawSeries(res){
  const cv=document.getElementById('cvSeries');const {ctx,w,H}=setupCanvas(cv,300);
  const pl=44,pr=44,pt=14,pb=26;const iw=w-pl-pr, ih=H-pt-pb;
  const zs=arr=>{const v=arr.filter(x=>x!==null);const m=mean(v);const s=Math.sqrt(v.reduce((a,b)=>a+(b-m)**2,0)/(v.length-1));return arr.map(x=>x===null?null:(x-m)/s);};
  const zx=zs(res.x), zy=zs(res.y);
  const X=i=>pl+iw*(res.x.length<2?0:i/(res.x.length-1));
  const Y=v=>pt+ih*(1-(v+3)/6);
  ctx.strokeStyle='#26303f';ctx.lineWidth=1;
  for(const v of [-3,-2,-1,0,1,2,3]){const y=Y(v);ctx.beginPath();ctx.moveTo(pl,y);ctx.lineTo(pl+iw,y);
    ctx.strokeStyle=v===0?'#3a4757':'#1f2733';ctx.stroke();ctx.fillStyle='#7d8b9e';ctx.font='11px ui-monospace';ctx.fillText(v.toFixed(0),pl-26,y+4);}
  // 日期刻度
  ctx.fillStyle='#7d8b9e';ctx.font='11px ui-monospace';
  const nT=6;for(let k=0;k<nT;k++){const i=Math.round(k*(res.x.length-1)/(nT-1));ctx.fillText(res.dates[i].slice(2),X(i)-20,H-8);}
  const line=(arr,color)=>{ctx.beginPath();let started=false;
    for(let i=0;i<arr.length;i++){const v=arr[i];if(v===null){started=false;continue;}
      const px=X(i),py=Y(Math.max(-3,Math.min(3,v)));if(!started){ctx.moveTo(px,py);started=true;}else ctx.lineTo(px,py);}
    ctx.strokeStyle=color;ctx.lineWidth=1.8;ctx.stroke();};
  line(zx,'#4da3ff');line(zy,'#7ee0c0');
  cv._hit={X,Y,pl,iw,n:res.x.length,res};
  cv.onmousemove=e=>{const r=cv.getBoundingClientRect();const mx=e.clientX-r.left;
    const i=Math.round((mx-pl)/iw*(res.x.length-1));if(i<0||i>=res.x.length)return;
    tipShow(e,`<b>${res.dates[i]}</b><br>${L[ST.x][0]}：${fmt(res.xRaw[i],2)} ${L[ST.x][1]}<br>${L[ST.y][0]}：${fmt(res.yRaw[i],2)} ${L[ST.y][1]}`);};
  cv.onmouseleave=tipHide;
}

function drawScatter(res){
  const cv=document.getElementById('cvScatter');const {ctx,w,H}=setupCanvas(cv,300);
  const pl=52,pr=16,pt=14,pb=34,iw=w-pl-pr,ih=H-pt-pb;
  const xs=res.x.filter(v=>v!==null),ys=res.y.filter(v=>v!==null);
  if(xs.length<3){ctx.fillStyle='#93a1b5';ctx.fillText('有效样本不足',pl,pt+20);return;}
  const xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
  const padx=(xmax-xmin)*0.08||1,pady=(ymax-ymin)*0.08||1;
  const X=v=>pl+iw*(v-(xmin-padx))/((xmax+padx)-(xmin-padx));
  const Y=v=>pt+ih*(1-(v-(ymin-pady))/((ymax+pady)-(ymin-pady)));
  ctx.strokeStyle='#1f2733';ctx.font='11px ui-monospace';ctx.fillStyle='#7d8b9e';
  for(const t of niceTicks(xmin-padx,xmax+padx,5)){const x=X(t);ctx.beginPath();ctx.moveTo(x,pt);ctx.lineTo(x,pt+ih);ctx.stroke();
    ctx.fillText(t.toFixed(Math.abs(t)<10?2:0),x-14,H-14);}
  for(const t of niceTicks(ymin-pady,ymax+pady,5)){const y=Y(t);ctx.beginPath();ctx.moveTo(pl,y);ctx.lineTo(pl+iw,y);ctx.stroke();
    ctx.fillText(t.toFixed(Math.abs(t)<10?2:0),6,y+4);}
  for(let i=0;i<res.x.length;i++){if(res.x[i]===null||res.y[i]===null)continue;
    ctx.beginPath();ctx.arc(X(res.x[i]),Y(res.y[i]),3.1,0,7);ctx.fillStyle='rgba(77,163,255,.55)';ctx.fill();}
  const f=linreg(res.x,res.y);
  if(f){ctx.beginPath();ctx.moveTo(X(xmin-padx),Y(f.a+f.b*(xmin-padx)));ctx.lineTo(X(xmax+padx),Y(f.a+f.b*(xmax+padx)));
    ctx.strokeStyle='#ffc857';ctx.lineWidth=2;ctx.stroke();}
  document.getElementById('fitHint').innerHTML = f
    ? `拟合：ŷ = ${fmt(f.a,2)} + ${fmt(f.b,4)}·x，R² = ${fmt(f.r2,3)}（n=${res.st_pts}）。散点形态与离群点请结合“统计稳健性”区块判读。`
    : '有效样本不足，无法拟合。';
}

function drawRoll(res){
  const cv=document.getElementById('cvRoll');const {ctx,w,H}=setupCanvas(cv,290);
  const pl=46,pr=14,pt=16,pb=26,iw=w-pl-pr,ih=H-pt-pb;
  const X=i=>pl+iw*(res.roll.length<2?0:i/(res.roll.length-1));
  const Y=v=>pt+ih*(1-(v+1)/2);
  ctx.strokeStyle='#1f2733';
  for(const v of [-1,-0.5,-0.2,0,0.2,0.5,1]){const y=Y(v);ctx.beginPath();ctx.moveTo(pl,y);ctx.lineTo(pl+iw,y);ctx.stroke();
    ctx.fillStyle='#7d8b9e';ctx.font='11px ui-monospace';ctx.fillText(v.toFixed(1),16,y+4);}
  // 参考带
  ctx.fillStyle='rgba(147,161,181,.10)';ctx.fillRect(pl,Y(0.2),iw,Y(-0.2)-Y(0.2));
  // 样本不足区
  ctx.fillStyle='rgba(120,130,145,.10)';
  for(let i=0;i<res.roll.length;i++)if(res.roll[i]===null){const x=X(i);ctx.fillRect(x-1,pt,2.5,ih);}
  // 主曲线
  ctx.beginPath();let started=false;
  for(let i=0;i<res.roll.length;i++){const v=res.roll[i];if(v===null){started=false;continue;}
    const px=X(i),py=Y(v);if(!started){ctx.moveTo(px,py);started=true;}else ctx.lineTo(px,py);}
  ctx.strokeStyle='#4da3ff';ctx.lineWidth=2;ctx.stroke();
  // 零线
  ctx.beginPath();ctx.moveTo(pl,Y(0));ctx.lineTo(pl+iw,Y(0));ctx.strokeStyle='#4a5a6e';ctx.lineWidth=1;ctx.stroke();
  // 异常点
  for(const an of res.anomalies){ctx.beginPath();ctx.arc(X(an.t),Y(res.roll[an.t]),4.4,0,7);
    ctx.fillStyle=an.kind==='reversal'?'#ffc857':'#ff6b81';ctx.fill();}
  // 选中
  if(SEL!==null&&SEL<res.roll.length&&res.roll[SEL]!==null){const x=X(SEL);ctx.strokeStyle='#ffffff55';ctx.setLineDash([4,4]);
    ctx.beginPath();ctx.moveTo(x,pt);ctx.lineTo(x,pt+ih);ctx.stroke();ctx.setLineDash([]);}
  ctx.fillStyle='#7d8b9e';ctx.font='11px ui-monospace';
  const nT=6;for(let k=0;k<nT;k++){const i=Math.round(k*(res.roll.length-1)/(nT-1));ctx.fillText(res.dates[i].slice(2),X(i)-18,H-8);}
  cv.onclick=e=>{const r=cv.getBoundingClientRect();const mx=e.clientX-r.left;
    const i=Math.round((mx-pl)/iw*(res.roll.length-1));
    if(i>=0&&i<res.roll.length){SEL=i;renderSel(res);drawRoll(res);}};
  cv.onmousemove=e=>{const r=cv.getBoundingClientRect();const mx=e.clientX-r.left;
    const i=Math.round((mx-pl)/iw*(res.roll.length-1));if(i<0||i>=res.roll.length)return;
    const v=res.roll[i];
    tipShow(e,`<b>${res.dates[i]}</b><br>窗口 ${ST.win} 周滚动 r：${v===null?'样本不足，不计算':fmt(v,3)}<br>窗口有效配对：${res.pairsCnt[i]}/${ST.win}（下限 ${ST.minp}）`);};
  cv.onmouseleave=tipHide;
}

function drawLag(res){
  const cv=document.getElementById('cvLag');const {ctx,w,H}=setupCanvas(cv,220);
  const pl=44,pr=14,pt=14,pb=30,iw=w-pl-pr,ih=H-pt-pb;
  const n=res.lags.length, bw=iw/n*0.6;
  const X=i=>pl+iw*(i+0.5)/n;
  const Y=v=>pt+ih*(1-(v+1)/2);
  ctx.strokeStyle='#1f2733';for(const v of [-1,-0.5,0,0.5,1]){const y=Y(v);ctx.beginPath();ctx.moveTo(pl,y);ctx.lineTo(pl+iw,y);ctx.stroke();
    ctx.fillStyle='#7d8b9e';ctx.font='11px ui-monospace';ctx.fillText(v.toFixed(1),16,y+4);}
  res.lags.forEach((p,i)=>{if(p.r===null)return;const x=X(i),y=Y(Math.max(0,p.r)),h=Y(p.r)-Y(0);
    ctx.fillStyle=p.r>0?'rgba(61,220,151,.75)':'rgba(255,107,129,.75)';ctx.fillRect(x-bw/2,Math.min(y,Y(0)),bw,Math.abs(h));
    ctx.fillStyle='#7d8b9e';ctx.font='11px ui-monospace';ctx.fillText(p.lag===0?'0':(p.lag>0?'+':'')+p.lag,x-6,H-10);});
  ctx.fillStyle='#93a1b5';ctx.font='11px ui-monospace';ctx.fillText('X 领先 →',w-96,pt+12);
}

/* ---------------- KPI / 表格 ---------------- */
function kpiCard(k,v,s,cls){return `<div class="kpi ${cls||''}"><div class="k">${k}</div><div class="v mono">${v}</div><div class="s">${s}</div></div>`;}
function renderKpis(res){
  const st=res.st;
  const sign=st.r===null?'':(st.r<0?'neg':'pos');
  const strength=st.r===null?'—':Math.abs(st.r)>=0.7?'强':Math.abs(st.r)>=0.4?'中等':'弱';
  document.getElementById('kpis').innerHTML =
    kpiCard('Pearson r（当前设定）',fmt(st.r),`${L[ST.x][0]}(${formLabel(ST.xf)}) × ${L[ST.y][0]}(${formLabel(ST.yf)})`,sign)+
    kpiCard('有效配对 N',st.n,`区间 ${ST.d1} ~ ${ST.d2}`)+
    kpiCard('p 值（双侧）',pfmt(st.p),`t=${fmt(st.t,2)}；显著性 ${sig(st.p)||'不显著'}`)+
    kpiCard('95% 置信区间',st.ci_lo===undefined?'—':`${fmt(st.ci_lo,2)} ~ ${fmt(st.ci_hi,2)}`,'Fisher-z 变换')+
    kpiCard('Spearman ρ',fmt(res.sp),'单调关系（抗离群）')+
    kpiCard('相关强度',strength,`|r| = ${fmt(st.r===null?null:Math.abs(st.r),2)}；R² = ${fmt(st.r===null?null:st.r*st.r,2)}`)+
    kpiCard('考虑自相关后 N_eff',fmt(res.neff,1),`修正 p ≈ ${pfmt(res.pEff)}`)+
    kpiCard('当前滚动 r（末点）',fmt(res.roll[res.roll.length-1]),`${ST.win} 周窗口`);
}
function formLabel(f){return {level:'水平',change:'一阶差分',pct:'环比%'}[f]||f;}
function renderPhases(res){
  const ix=res.dates.map((d,i)=>i);
  const phases=[[res.dates[0],res.dates[Math.floor(res.dates.length/3)],'阶段一'],
                [res.dates[Math.floor(res.dates.length/3)],res.dates[Math.floor(res.dates.length*2/3)],'阶段二'],
                [res.dates[Math.floor(res.dates.length*2/3)],res.dates[res.dates.length-1]+'~','阶段三']];
  let html='<tr><th class="l">阶段</th><th>N</th><th>Pearson r</th><th>p</th><th>Spearman</th><th>判定</th></tr>';
  for(const [a,b,name] of phases){
    const idx=res.dates.map((d,i)=>i).filter(i=>res.dates[i]>=a&&(b.endsWith('~')||res.dates[i]<b));
    const x=idx.map(i=>res.x[i]),y=idx.map(i=>res.y[i]);
    const st=corrStats(x,y),sp=spearman(x,y);
    html+=`<tr><td class="l">${name}<div class="d" style="color:var(--dim);font-size:11px">${a} ~ ${b.replace('~','')}</div></td>
      <td class="mono">${st.n}</td><td class="mono">${fmt(st.r)}</td><td class="mono">${pfmt(st.p)}</td><td class="mono">${fmt(sp)}</td>
      <td>${st.r===null?'—':(Math.abs(st.r)>=0.7?'强':Math.abs(st.r)>=0.4?'中等':'弱')+ (st.r<0?'负':'正')}</td></tr>`;
  }
  document.getElementById('phaseTbl').innerHTML=html;
}
function renderMatrix(){
  const xs=['level','change','pct'], ys=['level','change','pct'];
  const xraw=S[ST.x], yraw=S[ST.y];
  const [a,b]=sliceRange();
  let html='<tr><th class="l">库存 \\\\ 价格</th>'+ys.map(f=>`<th>${formLabel(f)}</th>`).join('')+'</tr>';
  for(const xf of xs){
    html+=`<tr><td class="l">${formLabel(xf)}</td>`;
    for(const yf of ys){
      const x=transform(xraw,xf).slice(a,b+1), y=transform(yraw,yf).slice(a,b+1);
      const st=corrStats(x,y);
      const cur=(xf===ST.xf&&yf===ST.yf)?'style="background:rgba(77,163,255,.13)"':'';
      html+=`<td class="mono" ${cur}>${fmt(st.r)}<span style="color:var(--dim);font-size:11px"> ${sig(st.p)}</span></td>`;
    }
    html+='</tr>';
  }
  html+=`<tr><td class="l" colspan="4" style="color:var(--dim);font-size:11.5px">N 随形态变化（差分/环比损失首期）：水平对水平 N=${corrStats(transform(xraw,'level').slice(a,b+1),transform(yraw,'level').slice(a,b+1)).n}，差分对差分 N=${corrStats(transform(xraw,'change').slice(a,b+1),transform(yraw,'change').slice(a,b+1)).n}</td></tr>`;
  document.getElementById('matrixTbl').innerHTML=html;
}
function renderRobust(res){
  const [a,b]=sliceRange();
  const xr=S[ST.x].slice(a,b+1), yr=S[ST.y].slice(a,b+1);
  const half=Math.floor((b-a)/2);
  const s1=corrStats(transform(xr.slice(0,half+1),ST.xf),transform(yr.slice(0,half+1),ST.yf));
  const s2=corrStats(transform(xr.slice(half),ST.xf),transform(yr.slice(half),ST.yf));
  const rd=dropExtreme(res.x,res.y), sDrop=corrStats(rd[0],rd[1]);
  const w=winsor(res.x),w2=winsor(res.y), sWin=corrStats(w,w2);
  const rows=[
    ['Pearson r（全部样本）',res.st.r,res.st.p,'基准'],
    ['Spearman ρ',res.sp,null,'秩相关，对离群点更稳健'],
    ['去趋势后 r（控制时间趋势）',res.detR,null,'若显著低于基准 → 存在趋势共同移动的伪相关风险'],
    ['一阶差分后 r（去除单位根）',res.diffR,null,'检验“水平相关是否只来自共同趋势”'],
    ['剔除极值 5%（双侧）后 r',sDrop.r,sDrop.p,'离群点敏感性'],
    ['Winsorize 5%/95% 后 r',sWin.r,sWin.p,'缩尾处理的稳健性'],
    ['前半段 r',s1.r,s1.p,`N=${s1.n}`],
    ['后半段 r',s2.r,s2.p,`N=${s2.n}`],
    ['偏相关（控制煤价）',res.pr,null,'共同外部因素（成本）检验'],
    ['X 一阶自相关',res.r1x,null,'高自相关会夸大显著性'],
    ['Y 一阶自相关',res.r1y,null,'同上'],
    ['有效样本量 N_eff',res.neff,null,'按自相关修正后的等效独立样本'],
    ['修正后 p（N_eff）',null,res.pEff,'更保守的显著性判断'],
  ];
  let html='<tr><th class="l">诊断项</th><th>数值</th><th>p</th><th class="l">解读</th></tr>';
  for(const [k,v,p,note] of rows){
    const val = v===null||v===undefined?'—':(Math.abs(v)>100?fmt(v,1):fmt(v,3));
    html+=`<tr><td class="l">${k}</td><td class="mono">${val}</td><td class="mono">${pfmt(p)}</td>
      <td class="l" style="white-space:normal;color:var(--dim);font-size:12px">${note}</td></tr>`;
  }
  document.getElementById('robustTbl').innerHTML=html;
}
function renderSel(res){
  const box=document.getElementById('selDetail'), tag=document.getElementById('selTag');
  if(SEL===null||SEL<0||SEL>=res.roll.length){box.textContent='在上图点击任意一点或异常区间，这里显示该窗口覆盖的库存/价格走势、期间统计量与区间内行业事件。';tag.textContent='未选择';return;}
  const W=ST.win, lo=Math.max(0,SEL-W+1), hi=SEL;
  const d0=res.dates[lo], d1=res.dates[hi], r=res.roll[SEL];
  tag.textContent=`${d0} ~ ${d1} · r=${r===null?'不足':fmt(r,2)}`;
  const idx=[];for(let i=lo;i<=hi;i++)idx.push(i);
  const x=idx.map(i=>res.x[i]),y=idx.map(i=>res.y[i]);
  const st=corrStats(x,y), sp=spearman(x,y);
  const xs=idx.map(i=>res.xRaw[i]).filter(v=>v!==null), ys=idx.map(i=>res.yRaw[i]).filter(v=>v!==null);
  const evs=EV.filter(e=>e.end>=d0&&e.start<=d1);
  box.innerHTML=`
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:10px">
      <div><div class="k" style="color:var(--dim);font-size:12px">窗口 r</div><div class="mono" style="font-size:20px">${r===null?'—':fmt(r,3)}</div></div>
      <div><div class="k" style="color:var(--dim);font-size:12px">有效配对</div><div class="mono" style="font-size:20px">${res.pairsCnt[SEL]}/${W}</div></div>
      <div><div class="k" style="color:var(--dim);font-size:12px">窗口 p</div><div class="mono" style="font-size:20px">${pfmt(st.p)}</div></div>
      <div><div class="k" style="color:var(--dim);font-size:12px">Spearman</div><div class="mono" style="font-size:20px">${fmt(sp)}</div></div>
    </div>
    <div>库存区间：${fmt(Math.min(...xs),2)} ~ ${fmt(Math.max(...xs),2)} ${L[ST.x][1]}（变化 ${fmt(xs[xs.length-1]-xs[0],2)}，首末差）</div>
    <div>价格区间：${fmt(Math.min(...ys),0)} ~ ${fmt(Math.max(...ys),0)} ${L[ST.y][1]}（变化 ${fmt(ys[ys.length-1]-ys[0],0)}，首末差）</div>
    <div style="margin-top:8px"><b>区间内行业事件（${evs.length}）</b></div>
    ${evs.length?evs.map(e=>`<div class="ev" style="margin-top:6px"><div class="t">${e.title}<span class="kind">${e.kind}</span></div><div class="d">${e.start} ~ ${e.end}</div><div class="n">${e.note}</div></div>`).join(''):'<div style="color:var(--dim)">该窗口内无记录事件；请看前后相邻窗口。</div>'}
    <div class="hint" style="margin-top:8px">提示：事件用于解释“相关性为何变化”，不能据此把相关性升级为因果关系。</div>`;
}
function renderEvents(){
  document.getElementById('events').innerHTML = EV.map(e=>
    `<div class="ev"><div class="t">${e.title}<span class="kind">${e.kind}</span></div>
     <div class="d">${e.start} ~ ${e.end}</div><div class="n">${e.note}</div></div>`).join('');
}
function renderConclusion(res){
  const st=res.st;
  const rl=res.roll.filter(v=>v!==null);
  const rmin=rl.length?Math.min(...rl):null, rmax=rl.length?Math.max(...rl):null;
  const signFlips=res.anomalies.filter(a=>a.kind==='reversal').length;
  const decouples=res.anomalies.filter(a=>a.kind==='decouple').length;
  const strong=st.r!==null&&Math.abs(st.r)>=0.7;
  const horiz=(ST.xf==='level'&&ST.yf==='level');
  document.getElementById('concl').innerHTML=`
   <p><b>1) 全样本（${ST.d1} ~ ${ST.d2}，N=${st.n}）：</b>
   库存[${formLabel(ST.xf)}] 与 价格[${formLabel(ST.yf)}] 的 Pearson r = <span class="mono">${fmt(st.r)}</span>
   （p ${pfmt(st.p)}${sig(st.p)?'，显著'+sig(st.p):'，不显著'}），Spearman ρ = <span class="mono">${fmt(res.sp)}</span>。
   按 |r| 判定为<b>${strong?'较强的':'偏弱/中等的'}</b>${st.r===null?'':(st.r<0?'负':'正')}相关。</p>
   <p><b>2) 相关强度随阶段变化：</b>${ST.win} 周滚动 r 在 [${fmt(rmin,2)}, ${fmt(rmax,2)}] 间波动，
   期间出现 <b>${signFlips}</b> 次符号反转、<b>${decouples}</b> 次脱钩（|r| 掉入 0.2 以内）。
   引用“库存与价格相关”时，必须同时说明<b>用的是哪段时间、哪种形态、哪个窗口</b>。</p>
   <p><b>3) 形态敏感性：</b>见“形态组合矩阵”。${horiz?'当前使用“水平对水平”，这类相关最容易被共同趋势抬升；请对照差分/环比口径的结果。':''}
   ${ST.yf==='level'?'注意：价格用“水平”形态时，价格与库存各自的时间趋势会贡献相当一部分相关。':''}</p>
   <p><b>4) 伪相关排查：</b>去趋势后 r=${fmt(res.detR)}、一阶差分后 r=${fmt(res.diffR)}、控制煤价后偏相关=${fmt(res.pr)}；
   库存自相关 ${fmt(res.r1x,2)}、价格自相关 ${fmt(res.r1y,2)}，按自相关修正后有效样本 N_eff≈${fmt(res.neff,1)}，修正 p≈${pfmt(res.pEff)}。
   ${(res.detR!==null&&st.r!==null&&Math.abs(res.detR)<Math.abs(st.r)*0.5)?'<span style="color:var(--warn)">去趋势后相关大幅下降，提示“水平相关”可能主要由共同趋势驱动，需要以变化口径为准。</span>':''}</p>
   <p><b>5) 限制与声明：</b>相关性不等于因果关系：库存与价格可能同时被供给、需求、成本、预期驱动，也可能互为因果；
   本页不给交易建议、不做价格预测。滞后相关只能提示先后顺序，不能单独证明方向。
   数据口径、频率、调查日与发布时点必须在报告正文中标明（见页脚与 Excel“口径与来源”表）。</p>
   <div class="demobox">${(PAYLOAD.meta.demo||{}).caveat||''}</div>`;
}

/* ---------------- 交互 ---------------- */
function tipShow(e,html){const t=document.getElementById('tip');t.innerHTML=html;t.style.display='block';
  t.style.left=Math.min(window.innerWidth-260,e.clientX+14)+'px';t.style.top=(e.clientY+14)+'px';}
function tipHide(){document.getElementById('tip').style.display='none';}
function syncControls(){
  document.getElementById('xsel').value=ST.x;document.getElementById('xform').value=ST.xf;
  document.getElementById('ysel').value=ST.y;document.getElementById('yform').value=ST.yf;
  document.getElementById('win').value=ST.win;document.getElementById('minp').value=ST.minp;
  document.getElementById('d1').value=ST.d1;document.getElementById('d2').value=ST.d2;
  document.getElementById('outl').value=ST.outl;
}
function readControls(){
  ST.x=document.getElementById('xsel').value;ST.xf=document.getElementById('xform').value;
  ST.y=document.getElementById('ysel').value;ST.yf=document.getElementById('yform').value;
  ST.win=+document.getElementById('win').value;ST.minp=+document.getElementById('minp').value;
  ST.d1=document.getElementById('d1').value;ST.d2=document.getElementById('d2').value;
  ST.outl=document.getElementById('outl').value;
}
let RES=null;
function render(){
  readControls();SEL=null;
  RES=compute();
  document.getElementById('tagA').textContent=`${L[ST.x][0]}(${formLabel(ST.xf)}) vs ${L[ST.y][0]}(${formLabel(ST.yf)})`;
  document.getElementById('lgA').textContent=`${L[ST.x][0]}（z 分数，${L[ST.x][1]}）`;
  document.getElementById('lgB').textContent=`${L[ST.y][0]}（z 分数，${L[ST.y][1]}）`;
  document.getElementById('tagB').textContent=`${formLabel(ST.xf)} × ${formLabel(ST.yf)}`;
  document.getElementById('tagC').textContent=`窗口 ${ST.win} 周 · 最小有效配对 ${ST.minp} · 点击查看明细`;
  document.getElementById('ctrlHint').innerHTML =
    `当前：X=${L[ST.x][0]}（${formLabel(ST.xf)}），Y=${L[ST.y][0]}（${formLabel(ST.yf)}），
     区间 ${ST.d1}~${ST.d2}，离群处理=${({none:'保留全部',winsor:'Winsorize',drop:'剔除极值'})[ST.outl]}。
     改变任一控件，页面所有数字、曲线与结论都会实时重算；窗口有效配对不足时不输出结果。`;
  renderKpis(RES);renderPhases(RES);renderMatrix();renderRobust(RES);
  drawSeries(RES);drawScatter(RES);drawRoll(RES);drawLag(RES);renderSel(RES);renderConclusion(RES);
}
window.addEventListener('resize',()=>{if(RES){drawSeries(RES);drawScatter(RES);drawRoll(RES);drawLag(RES);}});
document.querySelectorAll('#xsel,#xform,#ysel,#yform,#win,#minp,#d1,#d2,#outl').forEach(el=>{
  el.addEventListener('change',render);});
document.getElementById('reset').onclick=()=>{ST={...DEF};syncControls();render();};
(function init(){
  const meta=PAYLOAD.meta;
  document.getElementById('footDemo').textContent=(meta.demo||{}).caveat||'';
  const xsel=document.getElementById('xsel'),ysel=document.getElementById('ysel');
  renderEvents();syncControls();
  document.getElementById('minp').value=Math.max(5,Math.round(DEF.win*0.8));
  render();
})();
</script>
</body>
</html>
'''


def main():
    payload = build_payload()
    html = HTML.replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False, default=str))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(html)
    print('written', OUT, len(html), 'bytes')


if __name__ == '__main__':
    main()
