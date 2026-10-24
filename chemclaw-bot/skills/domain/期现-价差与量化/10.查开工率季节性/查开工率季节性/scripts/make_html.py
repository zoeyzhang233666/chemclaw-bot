# -*- coding: utf-8 -*-
"""生成自包含交互式 HTML 季节性问题报告（无外部 CDN 依赖）。"""
import argparse
import csv
import json
import os
from datetime import date

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中国PVC开工率（产能利用率）季节性分析 · 2026</title>
<style>
:root{
  --ink:#0f2436; --ink2:#3c556b; --muted:#7b8fa3; --line:#dbe5ee;
  --bg:#f4f7fa; --card:#ffffff; --accent:#0e3a5c; --accent2:#1f6f9e;
  --red:#b42318; --green:#067647; --amber:#b45309; --amberbg:#fff4d6;
  --warnbg:#ffe4e4; --okbg:#e3f6ea;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;
 font-size:14px;line-height:1.65}
.wrap{max-width:1280px;margin:0 auto;padding:0 20px 60px}
header{background:linear-gradient(135deg,#0d2f4a,#1b5c85 60%,#217fae);color:#fff;padding:34px 0 30px;margin-bottom:22px}
header .wrap{padding-bottom:0}
h1{margin:0 0 8px;font-size:26px;font-weight:700;letter-spacing:.5px}
.sub{color:#cfe2f0;font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:12px;margin-top:22px}
.kpi{background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.2);border-radius:10px;padding:12px 14px}
.kpi .k{font-size:11.5px;color:#bfd8ea;letter-spacing:.3px}
.kpi .v{font-size:23px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.kpi .n{font-size:11px;color:#a9c6da;margin-top:2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin-bottom:18px;
 box-shadow:0 1px 2px rgba(16,40,64,.04)}
h2{font-size:17px;margin:0 0 4px;color:var(--accent);display:flex;align-items:center;gap:9px;flex-wrap:wrap}
h2 .no{background:var(--accent);color:#fff;font-size:11.5px;width:22px;height:22px;border-radius:6px;
 display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
h3{font-size:14.5px;margin:18px 0 8px;color:var(--ink)}
.lede{color:var(--ink2);font-size:13px;margin:6px 0 14px}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;align-items:center}
.chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 13px;font-size:12.5px;
 cursor:pointer;user-select:none;color:var(--ink2);transition:.15s}
.chip:hover{border-color:var(--accent2);color:var(--accent2)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
.chip .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:1px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:10px 0}
th{background:#eef4f9;color:var(--accent);font-weight:600;text-align:left;padding:8px 9px;border-bottom:1.5px solid #cfdde9;
 white-space:nowrap;font-size:12px}
td{padding:7px 9px;border-bottom:1px solid #eef2f6;font-variant-numeric:tabular-nums}
tbody tr:hover{background:#f7fbfe}
td.num{text-align:right}
.up{color:var(--red);font-weight:600}
.dn{color:var(--green);font-weight:600}
.gap{background:var(--amberbg);color:var(--amber);font-weight:600;border-radius:4px;padding:1px 6px;font-size:11.5px}
.flag{background:var(--warnbg);color:var(--red);font-weight:600;border-radius:4px;padding:1px 6px;font-size:11.5px}
.ok{background:var(--okbg);color:var(--green);font-weight:600;border-radius:4px;padding:1px 6px;font-size:11.5px}
.note{border-left:3px solid var(--accent2);background:#f2f8fc;padding:11px 14px;border-radius:0 8px 8px 0;
 font-size:12.8px;color:var(--ink2);margin:12px 0}
.alert{border-left:3px solid var(--red);background:var(--warnbg);padding:11px 14px;border-radius:0 8px 8px 0;
 font-size:12.8px;margin:12px 0}
.alert b{color:var(--red)}
svg{display:block;width:100%;overflow:visible}
.grid{stroke:#e6eef5;stroke-width:1}
.axis{font-size:11px;fill:var(--muted)}
.lbl{font-size:11.5px;fill:var(--ink2)}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin:8px 0 0}
.legend i{display:inline-block;width:16px;height:3px;border-radius:2px;margin-right:5px;vertical-align:3px}
.legend i.box{width:12px;height:11px;border-radius:2px;vertical-align:1px}
.tip{position:fixed;pointer-events:none;background:#0f2436;color:#fff;font-size:12px;padding:8px 11px;
 border-radius:7px;line-height:1.5;opacity:0;transition:opacity .1s;z-index:99;max-width:280px;
 box-shadow:0 4px 16px rgba(0,0,0,.22)}
.tip.on{opacity:1}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:900px){.two{grid-template-columns:1fr}}
.tag{display:inline-block;background:#eaf2f8;color:var(--accent2);border-radius:4px;padding:1px 7px;
 font-size:11px;margin-right:5px}
footer{color:var(--muted);font-size:12px;text-align:center;padding:24px 0 0;border-top:1px solid var(--line);margin-top:26px}
a{color:var(--accent2)}
code{background:#eef3f8;padding:1px 5px;border-radius:4px;font-size:12px;
 font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
.hidden{display:none}
</style>
</head>
<body>
<header>
 <div class="wrap">
  <h1>中国 PVC 开工率（产能利用率）季节性分析</h1>
  <div class="sub">口径：隆众资讯 · 中国 PVC 企业产能利用率 · 71 家样本企业 · 统计周期“上周五~本周四” · 每周四发布
   ｜ 数据窗口 __D0__ ~ __D1__（__N__ 个真实周度观测，逐条带源）</div>
  <div class="kpis">
   <div class="kpi"><div class="k">最新一周（整体）</div><div class="v">__LATEST__%</div>
     <div class="n">__LATEST_D__ · 样本 __SAMPLE__ 家</div></div>
   <div class="kpi"><div class="k">年内区间</div><div class="v">__MIN__–__MAX__%</div>
     <div class="n">波动 __RANGE__ pp，变异系数 __CV__</div></div>
   <div class="kpi"><div class="k">近 12 周变化</div><div class="v" style="color:#ffc9c2">__CHG12__ pp</div>
     <div class="n">按观测序相减</div></div>
   <div class="kpi"><div class="k">电石法 − 乙烯法</div><div class="v">__SPLIT__ pp</div>
     <div class="n">__SPLIT_D__</div></div>
   <div class="kpi"><div class="k">跨年同周样本</div><div class="v">__NYEARS__ 年</div>
     <div class="n">≥3 年才可出分位区间</div></div>
  </div>
 </div>
</header>

<div class="wrap">

<div class="alert">
 <b>先读这条，再看任何数字：</b>本报告的“开工率”是<b>样本口径的产能利用率</b>，即 71 家样本企业周产量 ÷ 其有效产能。
它<b>不是</b>全国实际产量，<b>不能</b>用“利用率 × 全国产能”反推产量：样本覆盖率、产能基数口径（剔除僵尸产能）、
以及未纳入样本的装置都会造成偏差。所有跨年对比只用可核验的同口径单周值，缺数一律标“缺口”，<b>不做任何插值或填补</b>。
</div>

<!-- ============ 1 口径 ============ -->
<div class="card">
 <h2><span class="no">1</span>统计定义、样本企业与产能覆盖</h2>
 <div class="lede">三个容易混淆的口径必须分清：开工率 / 产能利用率（样本）/ 产能利用率（统计局·价值量）/ 实际产量。</div>

 <table>
  <thead><tr><th style="width:150px">口径</th><th>定义</th><th style="width:210px">统计范围</th><th style="width:150px">发布节奏</th><th style="width:110px">本报告用法</th></tr></thead>
  <tbody>
   <tr><td><b>产能利用率（样本·本报告主口径）</b></td>
     <td>企业产能的利用程度，也称开工负荷；一般用<b>产品产量或原料加工量</b>与<b>有效产能</b>之间的比值核算。
     每年年底将<b>连续停车 ≥2 个自然年</b>的产能（僵尸产能）剔除，不作为计算基数。</td>
     <td>隆众资讯 PVC 周度样本 <b>71 家</b>生产企业及厂区<br>全国 PVC 产能基数 <b>2,878.5 万吨/年</b>（2026-08-01 起）</td>
     <td>周度，统计“上周五~本周四”，<b>周四</b>发布</td>
     <td><span class="ok">主序列</span></td></tr>
   <tr><td><b>产能利用率（统计局·季度）</b></td>
     <td>实际产出与生产能力<b>均以价值量计量</b>的比率；规模以上大中型企业全面调查、小微企业抽样，约 11 万家工业企业；<b>按季调查、未经季节调整</b></td>
     <td>全部工业行业（含化工），GB/T 4754-2017</td>
     <td>季度</td>
     <td><span class="gap">不混用</span></td></tr>
   <tr><td><b>开工负荷率（卓创/钢联）</b></td>
     <td>名称与隆众近义，但<b>样本、权重、统计周期均不同</b>（卓创部分口径为“周五~次周四”）</td>
     <td>各自样本体系</td>
     <td>周度</td>
     <td><span class="flag">仅登记，禁止并入</span></td></tr>
   <tr><td><b>实际产量</b></td>
     <td>实物量口径的产出，需与“规上工业产量/氯碱协会产量”对齐</td>
     <td>全国/分省份/分工艺（样本 72~73 家）</td>
     <td>月度</td>
     <td><span class="gap">不可由利用率换算</span></td></tr>
  </tbody>
 </table>

 <h3>样本与产能基数的两处变更（会直接改变分子分母）</h3>
 <table>
  <thead><tr><th style="width:170px">生效范围</th><th style="width:90px">样本数</th><th style="width:150px">产能基数</th><th>事件</th><th style="width:230px">对开工率的影响方向</th></tr></thead>
  <tbody>
   <tr><td>2026-07-24 ~ 08-13</td><td>未披露</td><td>未披露</td><td>仅图表接口回传数值，无样本说明</td><td>未知 · 不用于占比推断</td></tr>
   <tr><td>2026-08-01 起</td><td>71</td><td><b>2,878.5 万吨/年</b></td>
     <td>甘肃金川新融 20 万吨/年装置退出样本，全国 PVC 产能基数变更</td>
     <td><span class="flag">口径变更点</span> 分母变化；若退出的是低开工装置，整体利用率会被动上行</td></tr>
   <tr><td>2026-08-20 ~ 10-15</td><td>71</td><td>2,878.5 万吨/年</td><td>稳定期</td><td><span class="ok">可做周度环比</span></td></tr>
  </tbody>
 </table>
 <div class="note">样本一致性核查结论：2026-08-20 至 10-15 共 8 期，样本企业与厂区数<b>均为 71 家、未变</b>，产能基数<b>均为 2,878.5 万吨/年</b>，
 期间口径可比。2026-08-01 之前的口径与之后不可直接连用。</div>
</div>

<!-- ============ 2 走势 ============ -->
<div class="card">
 <h2><span class="no">2</span>周度走势（可切换指标与口径）</h2>
 <div class="lede">拖动鼠标查看逐周明细；阴影带表示“该周号有历史同周观测”才可算分位——本期绝大多数周次为空白，这是关键限制。</div>
 <div class="toolbar" id="mChips"></div>
 <svg id="chart" viewBox="0 0 1180 400" preserveAspectRatio="none" height="400"></svg>
 <div class="legend" id="mLegend"></div>
</div>

<!-- ============ 3 历史分位 ============ -->
<div class="card">
 <h2><span class="no">3</span>按年周次对齐：均值、中位数与分位区间</h2>
 <div class="lede">口径固定：经验分位线性插值（= Excel <code>PERCENTILE.INC</code> = R <code>quantile(type=7)</code>）。
  <b>n &lt; 3 不出分位，n &lt; 5 结论必须标注“样本不足”。</b></div>
 <div id="pctTable"></div>
 <div class="alert" style="margin-top:16px">
  <b>本期不出具历史分位区间的结论。</b>要让“分位带 + 当年路径”成立，需要至少 3 个年份在同一周号上各有观测；
  当前数据只有 2026 一年，因此每个周号的 n=1 → 分位列为“缺口”。这不是数据质量问题，而是<b>样本结构</b>问题：
  在 n=1 上算出来的“P10~P90”只会是同一个数，看起来有区间，实际是假的。
 </div>
</div>

<!-- ============ 4 今年定位 ============ -->
<div class="card">
 <h2><span class="no">4</span>今年（2026）逐周定位</h2>
 <div class="lede">位置指标只有在同周历史 n≥3 时才有意义；本期全为缺口，因此本节只给<b>可核验的绝对水平与变化</b>。</div>
 <div id="curTable"></div>
</div>

<!-- ============ 5 4周12周 ============ -->
<div class="card">
 <h2><span class="no">5</span>最近 4 周与 12 周变化</h2>
 <div class="lede">按<b>观测序</b>相减（不是自然周）：有断档时按日历周减会跨过缺口，得出错误结论。</div>
 <div class="two">
  <div><h3>整体 / 电石法 / 乙烯法同期对比</h3><div id="chgTable"></div></div>
  <div><h3>数据发布节奏与断档</h3><div id="cadence"></div></div>
 </div>
</div>

<!-- ============ 6 季节性事件 ============ -->
<div class="card">
 <h2><span class="no">6</span>春节、集中检修与产业事件的季节性特征</h2>
 <div class="lede">这一节区分两件事：<b>机制上有季节性</b>（有充分产业逻辑与公开旁证） vs <b>本数据集能证明季节性</b>（需要多年逐周数据）。本期只能做前者。</div>

 <h3>6.1 春节：移动节假日会破坏日历周对齐</h3>
 <table>
  <thead><tr><th style="width:90px">年份</th><th style="width:130px">春节日期</th><th style="width:110px">所在 ISO 周</th><th>对周度开工率的影响机制</th></tr></thead>
  <tbody id="cnyTable"></tbody>
 </table>
 <div class="note">春节日期在 1 月下旬到 2 月中旬之间漂移，<b>最多可差 4~5 个 ISO 周</b>。
 因此“春节前后负荷下降”如果按 ISO 周号直接跨年比较，会把节前、节中、节后三个完全不同的状态混在一起。
 正确做法是<b>另建“春节相对周”</b>（以春节所在周为 0，前后各取 ±N 周对齐），并与 ISO 周视图并列给出，而不是互相替代。</div>

 <h3>6.2 集中检修：二季度是传统低谷</h3>
 <div class="note">产业共识与公开研报均指出：<b>PVC 的传统集中检修季在二季度（4—6 月）</b>，近四年均在二季度出现年内开工率低点；
 下半年旺季随“秋检”结束与新增产能释放而回升，随后进入需求淡季。<br>
 但请注意方向：<b>检修季 → 开工率下降</b>，这与“需求淡季 → 开工率下降”在时间上部分重叠，
 单看开工率曲线无法区分是两个原因中的哪一个，必须叠加检修损失量、社会库存与利润三项才能拆解。</div>

 <h3>6.3 2026 年已发生的产业事件（用于解释本年路径，不作为季节性证据）</h3>
 <table>
  <thead><tr><th style="width:110px">时间</th><th>事件</th><th style="width:150px">对本年开工率的影响</th></tr></thead>
  <tbody>
   <tr><td>2026-08-01</td><td>甘肃金川新融 20 万吨/年退出样本，产能基数改为 2,878.5 万吨/年</td><td>分母下降（口径变更，非生产行为）</td></tr>
   <tr><td>2026-09</td><td>检修产能 1,119 万吨（同比 +40.75%）；单月产量 176.56 万吨，为 2023-06 以来新低（环比 −6.41%，同比 −13.06%）</td>
     <td><span class="flag">显著压低</span> 解释 9 月整体利用率的下行</td></tr>
   <tr><td>2026-09-19</td><td>镇洋发展 30 万吨/年装置起停车检修，预计 ≤4 个月</td><td>压低 Q4 供给</td></tr>
   <tr><td>2026 年内</td><td>工信部对电石法 PVC 全覆盖节能监察</td><td>提升电石法合规成本，抑制负荷</td></tr>
   <tr><td>2027-Q1 前</td><td>西湖化学德国科隆 16.5 万吨/年 PVC 永久关停</td><td>海外供给收缩，间接支撑国内电石法出口</td></tr>
  </tbody>
 </table>
</div>

<!-- ============ 7 口径变化与异常年份 ============ -->
<div class="card">
 <h2><span class="no">7</span>统计口径变化检查与异常年份识别</h2>
 <div class="lede">异常年份判定必须写清“用什么标准判异常”。这里同时用三条：均值偏离（需≥3 年才有基准）、
  年内波动幅度、变异系数。样本年数不足时<b>明确写“不可判定”</b>，不硬凑结论。</div>
 <div id="anomTable"></div>

 <h3>异口径数据登记（严禁并入主序列）</h3>
 <table>
  <thead><tr><th style="width:95px">周</th><th style="width:230px">发布方 / 口径</th><th class="num" style="width:80px">整体</th>
   <th class="num" style="width:80px">电石法</th><th class="num" style="width:80px">乙烯法</th><th>为什么不能并入</th></tr></thead>
  <tbody id="crossTable"></tbody>
 </table>
</div>

<!-- ============ 8 跨年对照 ============ -->
<div class="card">
 <h2><span class="no">8</span>与历年的可核验同期值对照</h2>
 <div class="lede">只有“同发布方、同指标、同定义”的单周观测才能对比。对比必须标明是否同周号——不同周号的差值只能当量级参照。</div>
 <div id="anchorTable"></div>
</div>

<!-- ============ 9 数据缺口 ============ -->
<div class="card">
 <h2><span class="no">9</span>数据缺口与复现路径</h2>
 <div class="lede">“没拿到”和“不存在”是两件事。下表把每处缺口的原因、已尝试路径与补救办法写清楚，便于下一期接力。</div>
 <div id="gapTable"></div>
</div>

<footer>
 中国 PVC 开工率季节性分析 · 生成于 2026-10-20 ·
 数据源：隆众资讯（mysteel 转载速讯 / 图表接口）、新华财经转引、卓创资讯与钢联（仅登记） ·
 分位口径：经验分位线性插值 · 缺口不填补
</footer>
</div>

<div class="tip" id="tip"></div>

<script>
const DATA = __DATA__;

/* ---------------- 工具 ---------------- */
const $ = s => document.querySelector(s);
const fmt = (v, d=2) => v===null||v===undefined ? '—' : Number(v).toFixed(d);
const tip = $('#tip');
function showTip(e, html){ tip.innerHTML = html; tip.classList.add('on');
  const pad=14; let x=e.clientX+pad, y=e.clientY+pad;
  if (x+300>innerWidth) x=e.clientX-300-pad;
  if (y+140>innerHeight) y=e.clientY-140-pad;
  tip.style.left=x+'px'; tip.style.top=y+'px'; }
function hideTip(){ tip.classList.remove('on'); }

/* 中文习惯：正=红（偏紧/上涨），负=绿（偏松/下跌） */
function signed(v, d=2){
  if (v===null||v===undefined) return '<span class="gap">缺口</span>';
  const cls = v>0?'up':(v<0?'dn':'');
  return `<span class="${cls}">${v>0?'+':''}${Number(v).toFixed(d)}</span>`;
}

/* ---------------- 2 曲线 ---------------- */
const METRICS = [
  {k:'util', name:'整体', color:'#0e3a5c', on:true},
  {k:'calc', name:'电石法', color:'#c2410c', on:true},
  {k:'eth',  name:'乙烯法', color:'#1f6f9e', on:true},
  {k:'spread', name:'电石法−乙烯法', color:'#7c3aed', on:false},
];

function renderChips(){
  $('#mChips').innerHTML = METRICS.map((m,i)=>
    `<span class="chip ${m.on?'on':''}" data-i="${i}">
      <span class="dot" style="background:${m.color}"></span>${m.name}</span>`).join('')
    + `<span class="chip" data-i="99" style="border-style:dashed">全部重置</span>`;
  $('#mChips').querySelectorAll('.chip').forEach(el=>{
    el.onclick = () => {
      const i = +el.dataset.i;
      if (i===99){ METRICS.forEach(m=>m.on = (m.k!=='spread')); }
      else { METRICS[i].on = !METRICS[i].on; }
      renderChips(); drawChart();
    };
  });
}

function drawChart(){
  const W=1180,H=400, ML=52,MR=92,MT=18,MB=54;
  const iw=W-ML-MR, ih=H-MT-MB;
  const rows = DATA.weekly;
  const active = METRICS.filter(m=>m.on);
  // y 范围
  let vals=[];
  active.forEach(m=>rows.forEach(r=>{
    const v = m.k==='spread' ? (r.calc!==null&&r.eth!==null? r.calc-r.eth : null) : r[m.k];
    if (v!==null&&v!==undefined) vals.push(v);
  }));
  if(!vals.length) vals=[60,80];
  let lo=Math.floor(Math.min(...vals)/5)*5-2, hi=Math.ceil(Math.max(...vals)/5)*5+2;
  const y = v => MT + ih*(1-(v-lo)/(hi-lo));
  const x = i => rows.length===1 ? ML+iw/2 : ML + iw*i/(rows.length-1);

  let s='';
  // 网格
  const step = (hi-lo)<=30?5:10;
  for(let v=Math.ceil(lo/step)*step; v<=hi; v+=step){
    s+=`<line class="grid" x1="${ML}" y1="${y(v)}" x2="${ML+iw}" y2="${y(v)}"/>`;
    s+=`<text class="axis" x="${ML-9}" y="${y(v)+4}" text-anchor="end">${v}</text>`;
  }
  // x 轴
  rows.forEach((r,i)=>{
    s+=`<text class="axis" x="${x(i)}" y="${MT+ih+18}" text-anchor="middle">${r.date.slice(5)}</text>`;
    s+=`<text class="axis" x="${x(i)}" y="${MT+ih+33}" text-anchor="middle" style="font-size:10px">W${String(r.iso_week).padStart(2,'0')}</text>`;
  });
  // 断档提示
  rows.forEach((r,i)=>{
    if(r.gap_days && r.gap_days!==7 && i>0){
      const xm=(x(i-1)+x(i))/2;
      s+=`<line x1="${xm}" y1="${MT}" x2="${xm}" y2="${MT+ih}" stroke="#e9b949" stroke-width="1.4" stroke-dasharray="4 3"/>`;
      s+=`<text class="lbl" x="${xm}" y="${MT+11}" text-anchor="middle" fill="#b45309" style="font-size:10.5px">断档 ${r.gap_days}天</text>`;
    }
  });
  // 线
  active.forEach(m=>{
    const pts=[];
    rows.forEach((r,i)=>{
      const v = m.k==='spread' ? (r.calc!==null&&r.eth!==null? r.calc-r.eth : null) : r[m.k];
      if(v!==null&&v!==undefined) pts.push([x(i),y(v),r,v]);
    });
    if(m.k==='spread'){
      // 填充正负
      pts.forEach(p=>{ s+=`<circle cx="${p[0]}" cy="${p[1]}" r="2.4" fill="${m.color}" opacity=".55"/>`; });
    }
    s+=`<polyline fill="none" stroke="${m.color}" stroke-width="2.2" stroke-linejoin="round"
        points="${pts.map(p=>p[0]+','+p[1]).join(' ')}"/>`;
    pts.forEach(p=>{ s+=`<circle cx="${p[0]}" cy="${p[1]}" r="3.4" fill="#fff" stroke="${m.color}" stroke-width="2"/>`; });
    // 右端标签
    const last=pts[pts.length-1];
    if(last) s+=`<text class="lbl" x="${last[0]+9}" y="${last[1]+4}" fill="${m.color}" style="font-weight:600">${m.name} ${fmt(last[3])}</text>`;
  });
  // 交互热区
  rows.forEach((r,i)=>{
    const bw = iw/Math.max(1,rows.length-1);
    s+=`<rect x="${x(i)-bw/2}" y="${MT}" width="${bw}" height="${ih}" fill="transparent"
        data-i="${i}" class="hot"/>`;
  });
  $('#chart').innerHTML = s;
  $('#chart').querySelectorAll('.hot').forEach(el=>{
    el.onmousemove = e=>{
      const r = rows[+el.dataset.i];
      showTip(e, `<b>${r.date}</b>（W${String(r.iso_week).padStart(2,'0')}）<br>
        整体 ${fmt(r.util)}%　电石法 ${fmt(r.calc)}%<br>乙烯法 ${fmt(r.eth)}%<br>
        价差 <b>${fmt(r.calc-r.eth)}</b> pp<br>
        环比 ${r.util_c2c===null?'未披露':fmt(r.util_c2c)}　样本 ${r.sample_n||'未披露'} 家`);
    };
    el.onmouseleave = hideTip;
  });
  $('#mLegend').innerHTML = active.map(m=>
    `<span><i style="background:${m.color}"></i>${m.name}</span>`).join('')
    + `<span style="color:var(--amber)">┆ 竖虚线 = 发布节奏跳跃（跨度≠7 天）</span>`;
}

/* ---------------- 3 分位表 ---------------- */
function renderPct(){
  const p = DATA.profile;
  let h = `<table><thead><tr>
    <th style="width:70px">ISO周</th><th class="num" style="width:70px">n</th><th style="width:110px">观测年份</th>
    <th class="num">均值</th><th class="num">中位数</th><th class="num">P10</th><th class="num">P25</th>
    <th class="num">P75</th><th class="num">P90</th><th style="width:180px">判定</th></tr></thead><tbody>`;
  p.forEach(r=>{
    const n = r.n;
    const cell = v => (n>=3 && v!==null && v!==undefined) ? fmt(v) : '<span class="gap">缺口</span>';
    const verdict = n<3 ? '<span class="gap">n&lt;3，不出分位</span>'
                  : (n<5 ? '<span class="flag">样本不足，仅供参考</span>' : '<span class="ok">可用</span>');
    h += `<tr><td>W${String(r.iso_week).padStart(2,'0')}</td><td class="num">${n}</td>
      <td>${r.years||'—'}</td><td class="num">${cell(r.mean)}</td><td class="num">${cell(r.median)}</td>
      <td class="num">${cell(r.p10)}</td><td class="num">${cell(r.p25)}</td>
      <td class="num">${cell(r.p75)}</td><td class="num">${cell(r.p90)}</td><td>${verdict}</td></tr>`;
  });
  h += '</tbody></table>';
  $('#pctTable').innerHTML = h;
}

/* ---------------- 4 今年定位 ---------------- */
function renderCur(){
  let h = `<table><thead><tr><th style="width:110px">周期截止日</th><th style="width:60px">周</th>
    <th class="num" style="width:80px">整体%</th><th class="num" style="width:70px">同周n</th>
    <th class="num" style="width:90px">同周均值</th><th class="num" style="width:90px">同周P50</th>
    <th class="num" style="width:110px">低于本周占比</th><th class="num" style="width:90px">4周变化</th>
    <th class="num" style="width:90px">12周变化</th><th>位置判定</th></tr></thead><tbody>`;
  DATA.cur.forEach(r=>{
    const n = r.hist_n;
    const hist = v => n>=3 ? fmt(v) : '<span class="gap">缺口</span>';
    h += `<tr><td>${r.date}</td><td>W${String(r.iso_week).padStart(2,'0')}</td>
      <td class="num"><b>${fmt(r.util)}</b></td><td class="num">${n}</td>
      <td class="num">${hist(r.hist_mean)}</td><td class="num">${hist(r.hist_p50)}</td>
      <td class="num">${n>=3? (r.below_ratio===null?'—':(r.below_ratio*100).toFixed(0)+'%') : '<span class="gap">缺口</span>'}</td>
      <td class="num">${signed(r.chg_4w)}</td><td class="num">${signed(r.chg_12w)}</td>
      <td>${n<3?'<span class="gap">同周无历史样本，无法定位</span>':'<span class="ok">可定位</span>'}</td></tr>`;
  });
  h += '</tbody></table>';
  $('#curTable').innerHTML = h;
}

/* ---------------- 5 变化 + 节奏 ---------------- */
function renderChg(){
  const w = DATA.weekly, n = w.length;
  // 12 周变化需要“第 13 个观测”才存在；不足时返回 null（不拿首周冒充 12 周前）
  const d12 = k => n>=13 ? (w[n-1][k]-w[n-13][k]) : null;
  const d4  = k => n>=5  ? (w[n-1][k]-w[n-5][k])  : null;
  const v12 = k => n>=13 ? w[n-13][k] : null;
  const v4  = k => n>=5  ? w[n-5][k]  : null;
  const rows = [['整体','util'],['电石法','calc'],['乙烯法','eth']];
  let h = `<table><thead><tr><th>指标</th><th class="num">最新</th><th class="num">4周前</th>
    <th class="num">4周变化</th><th class="num">12周前</th><th class="num">12周变化</th></tr></thead><tbody>`;
  rows.forEach(([nm,k])=>{
    const a12 = v12(k), a4 = v4(k);
    h += `<tr><td>${nm}</td><td class="num"><b>${fmt(w[n-1][k])}</b></td>
      <td class="num">${a4===null?'<span class="gap">不足</span>':fmt(a4)}</td>
      <td class="num">${a4===null?'<span class="gap">缺口</span>':signed(d4(k))}</td>
      <td class="num">${a12===null?'<span class="gap">不足</span>':fmt(a12)}</td>
      <td class="num">${a12===null?'<span class="gap">缺口</span>':signed(d12(k))}</td></tr>`;
  });
  h += '</tbody></table>';
  const first = w[0], last = w[n-1];
  h += `<div class="note">4 周变化=最近一周 vs 倒数第 5 个观测（${v4('util')===null?'—':fmt(v4('util'))}% → ${fmt(last.util)}%，
     ${d4('util')===null?'—':(d4('util')>0?'+':'')+d4('util').toFixed(2)} pp）。
     <b>12 周变化严格按“第 13 个观测”定义</b>；本数据集只有 ${n} 个观测，因此 12 周变化为“缺口”，
     不拿首周（${first.date}）冒充 12 周前。<br>
     若改用“窗口内首尾差”表述，可写：${first.date} ${fmt(first.util)}% → ${last.date} ${fmt(last.util)}%，
     跨度 ${n-1} 个观测间隔（其中含 1 处 14 天断档），累计变化 ${(last.util-first.util>0?'+':'')+(last.util-first.util).toFixed(2)} pp——
     这是<b>窗口涨跌幅</b>，不等于 12 周变化。</div>`;
  $('#chgTable').innerHTML = h;

  let c = `<table><thead><tr><th>周期截止日</th><th class="num">距上一期</th><th>节奏判定</th></tr></thead><tbody>`;
  w.forEach((r,i)=>{
    let tag = '<span class="ok">规律（7天）</span>';
    if(i===0) tag = '<span class="tag">序列起点</span>';
    else if(r.gap_days===14) tag = '<span class="gap">跳跃 14 天 · 缺 1 期</span>';
    else if(r.gap_days && r.gap_days!==7) tag = `<span class="flag">${r.gap_days} 天 · 非标准</span>`;
    c += `<tr><td>${r.date}</td><td class="num">${i===0?'—':(r.gap_days??'—')+' 天'}</td><td>${tag}</td></tr>`;
  });
  c += '</tbody></table>';
  const jumps = w.filter((r,i)=>i>0 && r.gap_days!==7).length;
  c += `<div class="note">共 ${jumps} 处非标准节奏。跳变必须被识别：如果按“上一行”算环比，会把两周的累计变化算成一周的变化。`;
  c += `<br><b>已踩坑记录：</b>隆众原文的“环比”=与<b>上一发布日</b>比，不是与 ISO 周-1 比。`;
  c += `用 ISO 周匹配时，2026-08-20 起的每一行都被误判为“不一致”；改用真实发布间隔后才对齐。`;
  c += `</div>`;
  $('#cadence').innerHTML = c;
}

/* ---------------- 6 春节 ---------------- */
function renderCny(){
  const list = DATA.cny;
  const h = list.map(x=>{
    const iy = new Date(x.d+'T00:00:00');
    const wk = isoWeek(iy);
    return `<tr><td>${x.y}</td><td>${x.d}</td><td>${x.iso}</td><td>${x.note||''}</td></tr>`;
  }).join('');
  $('#cnyTable').innerHTML = h;
}
function isoWeek(d){
  const t=new Date(Date.UTC(d.getFullYear(),d.getMonth(),d.getDate()));
  const dn=t.getUTCDay()||7; t.setUTCDate(t.getUTCDate()+4-dn);
  const y0=new Date(Date.UTC(t.getUTCFullYear(),0,1));
  return 1+Math.round(((t-y0)/86400000-3+(y0.getUTCDay()+6)%7)/7);
}

/* ---------------- 7 异常 + 异口径 ---------------- */
function renderAnom(){
  let h = `<table><thead><tr><th style="width:70px">年份</th><th class="num" style="width:80px">观测周数</th>
    <th class="num">均值</th><th class="num">中位数</th><th class="num">最小</th><th class="num">最大</th>
    <th class="num">极差</th><th class="num">标准差</th><th class="num">变异系数</th><th style="width:250px">判定</th></tr></thead><tbody>`;
  DATA.anomaly.forEach(a=>{
    h += `<tr><td>${a.year}</td><td class="num">${a.n}</td>
      <td class="num">${fmt(a.mean)}</td><td class="num">${fmt(a.median)}</td>
      <td class="num">${fmt(a.min)}</td><td class="num">${fmt(a.max)}</td>
      <td class="num">${a.range!==undefined?fmt(a.range):'—'}</td>
      <td class="num">${a.stdev!==undefined?fmt(a.stdev):'—'}</td>
      <td class="num">${a.cv!==undefined&&a.cv!==null?Number(a.cv).toFixed(3):'—'}</td>
      <td>${a.flag? `<span class="gap">${a.flag}</span>` : '<span class="ok">样本充足</span>'}</td></tr>`;
  });
  h += '</tbody></table>';
  h += `<div class="alert"><b>异常年份无法判定。</b>判定“某年异常”需要一个跨年基准（通常 ≥3 年同期均值）。
   当前只有 2026 一年，任何“2026 是异常年”的表述都缺乏参照系。<br>
   但<b>年内</b>可以陈述事实：2026 年这 12 个观测内，整体利用率从 73.76% 高点回落至 64.59%，
   极差 9.17pp，且最后 8 个观测中有 6 个下行——这是<b>年内走势</b>，不是“异常年份”结论。</div>`;
  $('#anomTable').innerHTML = h;

  const c = DATA.cross;
  let t = '';
  c.forEach(x=>{
    t += `<tr><td>${x.week_end}</td><td>${x.source}<br><span class="tag">${x.caliber}</span></td>
      <td class="num">${x.util??'—'}</td><td class="num">${x.calc??'—'}</td><td class="num">${x.eth??'—'}</td>
      <td>${x.why}</td></tr>`;
  });
  if(!t) t = '<tr><td colspan="6"><span class="gap">未登记异口径数据</span></td></tr>';
  $('#crossTable').innerHTML = t;
}

/* ---------------- 8 锚点 ---------------- */
function renderAnchor(){
  const a = DATA.anchors;
  let h = `<table><thead><tr><th style="width:110px">对照周</th><th class="num" style="width:90px">对照值%</th>
    <th class="num" style="width:90px">本期值%</th><th class="num" style="width:90px">差值(pp)</th>
    <th>来源</th><th style="width:300px">可比性判定</th></tr></thead><tbody>`;
  a.forEach(x=>{
    h += `<tr><td>${x.week_end}</td><td class="num">${fmt(x.util)}</td><td class="num">${fmt(x.cur)}</td>
      <td class="num">${signed(x.diff)}</td>
      <td><a href="${x.url}" target="_blank" rel="noopener">${x.source}</a></td>
      <td>${x.verdict}</td></tr>`;
  });
  h += '</tbody></table>';
  h += `<div class="alert"><b>引用规范：</b>与 2025-07-04 的 77.44% 相比低 12.85pp，只能表述为
   “与 2025 年年中水平相比处于明显低位”，<b>不得</b>写成“同周同比下降 12.85pp”——两者相差约 14 个周号，
   中间发生了什么（含季节性）无法从这两个点识别。</div>`;
  $('#anchorTable').innerHTML = h;
}

/* ---------------- 9 缺口 ---------------- */
function renderGaps(){
  const g = DATA.gaps;
  let h = `<table><thead><tr><th style="width:170px">缺口</th><th style="width:110px">范围</th>
    <th style="width:220px">为什么缺</th><th style="width:280px">已尝试路径</th>
    <th style="width:240px">补救办法</th><th>对结论的影响</th></tr></thead><tbody>`;
  g.forEach(x=>{
    h += `<tr><td><b>${x[0]}</b></td><td>${x[1]}</td><td>${x[2]}</td><td>${x[3]}</td><td>${x[4]}</td>
      <td><span class="gap">${x[5]}</span></td></tr>`;
  });
  h += '</tbody></table>';
  $('#gapTable').innerHTML = h;
}

/* ---------------- 启动 ---------------- */
renderChips(); drawChart(); renderPct(); renderCur(); renderChg();
renderCny(); renderAnom(); renderAnchor(); renderGaps();
addEventListener('scroll', hideTip, {passive:true});
</script>
</body>
</html>
"""

CNY = [
    (2021, '2021-02-12', '2021-W06', '节前备货 + 假期停车；节后复工节奏决定 2—3 月负荷'),
    (2022, '2022-02-01', '2022-W05', ''),
    (2023, '2023-01-22', '2023-W04', ''),
    (2024, '2024-02-10', '2024-W06', ''),
    (2025, '2025-01-29', '2025-W05', ''),
    (2026, '2026-02-17', '2026-W08', ''),
]

GAPS = [
    ['2026-W01~W29 周度值', '29 个周号',
     '隆众原文正文对非会员隐藏；mysteel 转载仅保留近 7 期在栏目页',
     '① 栏目分页 index_N.html → 触发验证码；② oilchem 列表页 → 可枚举标题但正文需会员；'
     '③ 文章 ID 为 16 位随机十六进制 → 不可枚举；④ 图表接口仅回传 13 周窗口；⑤ 搜索引擎反爬',
     '① 对图表接口 pageListIds 长期滚动抓取，可攒满 13 周窗口并逐期累积；② 采购数据终端；'
     '③ 用券商研报/财经快讯里的单周原句做锚点',
     '无法出具 2026 全年季节性曲线'],
    ['2025 及更早逐周序列', '5 年目标',
     '同上；历史文章列表已归档',
     '新华财经/中国金融信息网快讯可检索到单周原句（已取到 2025-07-04 的 77.44%）',
     '按“单周锚点”逐个补，每条带 URL；攒够 3 年即可算同周分位',
     '跨年同期只能点对点，不能给区间'],
    ['春节效应量化', '各年 2 月',
     '缺 2021—2025 年 2 月逐周值',
     '已确认春节日期表（2021-02-12 … 2026-02-17）',
     '补 2 月逐周数据后用“春节相对周”对齐重算',
     '本期只做机制解释，无数值结论'],
    ['分工艺历史', '全部历史',
     '快讯正文隐藏，仅近 7 期可见分工艺数值',
     '图表接口 ID01037485 / ID01037486 提供 13 周双口径',
     '同主序列，靠滚动抓取积累',
     '分工艺季节性本期无结论'],
]


def build_data():
    def rd(p):
        if not os.path.exists(p):
            return []
        with open(p, encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))

    weekly_raw = rd('raw/pvc_util_weekly.csv')
    weekly = []
    for r in weekly_raw:
        def f(k):
            v = (r.get(k) or '').strip()
            return float(v) if v not in ('', 'NA') else None
        weekly.append({
            'date': r['date'], 'week_end': r['week_end'], 'iso_week': int(r['iso_week']),
            'util': f('util'), 'calc': f('calc'), 'eth': f('eth'),
            'util_c2c': f('util_c2c'), 'sample_n': f('sample_n'),
            'gap_days': (int(f('gap_days')) if f('gap_days') is not None else None),
        })

    profile = []
    for r in rd('out/seasonal_profile.csv'):
        def g(k):
            v = (r.get(k) or '').strip()
            return float(v) if v not in ('', 'NA', 'None') else None
        profile.append({'iso_week': int(r['iso_week']), 'n': int(r['n']), 'years': r.get('years', ''),
                        'mean': g('mean'), 'median': g('median'), 'p10': g('p10'), 'p25': g('p25'),
                        'p75': g('p75'), 'p90': g('p90')})

    cur = []
    for r in rd('out/current_year.csv'):
        def g(k):
            v = (r.get(k) or '').strip()
            return float(v) if v not in ('', 'NA', 'None') else None
        cur.append({'date': r['date'], 'iso_week': int(r['iso_week']), 'util': float(r['util']),
                    'hist_n': int(r['hist_n']), 'hist_mean': g('hist_mean'), 'hist_p50': g('hist_p50'),
                    'below_ratio': g('below_ratio'), 'chg_4w': g('chg_4w'), 'chg_12w': g('chg_12w')})

    anomaly = []
    for r in rd('out/anomaly.csv'):
        if not r.get('year'):
            continue
        a = {'year': int(r['year']), 'n': int(r['n']), 'mean': float(r['mean']),
             'median': float(r['median']), 'min': float(r['min']), 'max': float(r['max']),
             'flag': r.get('flag', '')}
        for k in ('range', 'stdev', 'cv'):
            v = (r.get(k) or '').strip()
            a[k] = float(v) if v not in ('', 'None') else None
        anomaly.append(a)

    anchors, cross = [], []
    latest = weekly[-1]['util'] if weekly else None
    for r in rd('raw/external_anchor.csv'):
        try:
            v = float(r['util'])
        except (TypeError, ValueError):
            v = None
        if '同源同定义' in r.get('caliber', '') and v is not None:
            if r['week_end'] == weekly[-1]['week_end']:
                verdict = '<span class="ok">同一周号，可直接比较</span>'
            else:
                verdict = ('<span class="gap">非同周号 · 仅作水平量级参照</span>')
            anchors.append({'week_end': r['week_end'], 'util': v, 'cur': latest,
                            'diff': round(latest - v, 2) if latest is not None else None,
                            'source': r['source'], 'url': r['url'], 'verdict': verdict})
        elif v is not None or r.get('calc'):
            def ff(k):
                x = (r.get(k) or '').strip()
                return float(x) if x not in ('', 'NA') else None
            cross.append({'week_end': r['week_end'], 'source': r['source'],
                          'caliber': r.get('caliber', ''), 'util': ff('util'),
                          'calc': ff('calc'), 'eth': ff('eth'),
                          'why': '样本/权重/统计周期不同，同周可差 1~3pp；'
                                 '只能做方向性对照，不能与隆众值相减或拼成一条线'})

    cny = [{'y': y, 'd': d, 'iso': iso, 'note': note} for y, d, iso, note in CNY]

    return {'weekly': weekly, 'profile': profile, 'cur': cur, 'anomaly': anomaly,
            'anchors': anchors, 'cross': cross, 'cny': cny, 'gaps': GAPS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='assets/PVC开工率季节性报告.html')
    a = ap.parse_args()
    data = build_data()
    js = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    w = data['weekly']
    utils = [x['util'] for x in w]
    chg12 = round(w[-1]['util'] - w[0]['util'], 2) if len(w) >= 2 else None
    split = round(w[-1]['calc'] - w[-1]['eth'], 2) if w else None
    mean = sum(utils) / len(utils)
    sd = (sum((x - mean) ** 2 for x in utils) / (len(utils) - 1)) ** 0.5
    html = (TPL
            .replace('__DATA__', js)
            .replace('__D0__', w[0]['date'] if w else '')
            .replace('__D1__', w[-1]['date'] if w else '')
            .replace('__N__', str(len(w)))
            .replace('__LATEST__', f"{w[-1]['util']:.2f}" if w else '')
            .replace('__LATEST_D__', w[-1]['date'] if w else '')
            .replace('__SAMPLE__', str(int(w[-1]['sample_n'])) if w and w[-1]['sample_n'] else '未披露')
            .replace('__MIN__', f'{min(utils):.2f}' if utils else '')
            .replace('__MAX__', f'{max(utils):.2f}' if utils else '')
            .replace('__RANGE__', f'{max(utils) - min(utils):.2f}' if utils else '')
            .replace('__CV__', f'{sd / mean:.3f}' if utils else '')
            .replace('__CHG12__', f'{chg12:+.2f}' if chg12 is not None else '')
            .replace('__SPLIT__', f'{split:.2f}' if split is not None else '')
            .replace('__SPLIT_D__', f"{w[-1]['date']}" if w else '')
            .replace('__NYEARS__', str(len({x['date'][:4] for x in w}) if w else 0)))
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)
    print('wrote', a.out, len(html), 'bytes')


if __name__ == '__main__':
    main()
