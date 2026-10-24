# -*- coding: utf-8 -*-
"""
生成自包含交互式 HTML 研究报告（无外部 CDN 依赖，可离线打开）
数据：out/report_data.json
输出：out/甲醇华东_基差季节性研究报告.html
"""
import json, os, sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'out')
DATA = json.load(open(os.path.join(OUT, 'report_data.json'), encoding='utf-8'))

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>甲醇 期现基差季节性研究报告 · 2022-08 ~ 2026-10</title>
<style>
:root{
  --bg:#0e1117; --panel:#151a23; --panel2:#1b222d; --line:#26303f;
  --fg:#e6edf3; --dim:#8b98a9; --accent:#4cc2ff; --long:#e5484d; --short:#30a46c;
  --warn:#f5a524; --violet:#a78bfa;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:14px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;}
.wrap{max-width:1320px;margin:0 auto;padding:22px 20px 80px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:.5px}
h2{font-size:19px;margin:38px 0 14px;padding-left:11px;border-left:3px solid var(--accent)}
h3{font-size:15px;margin:20px 0 10px;color:var(--fg)}
.sub{color:var(--dim);font-size:13px;margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:16px}
.grid{display:grid;gap:14px}
.g4{grid-template-columns:repeat(4,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g2{grid-template-columns:repeat(2,1fr)}
@media(max-width:900px){.g4,.g3,.g2{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.g4,.g3,.g2{grid-template-columns:1fr}}
.kpi{background:linear-gradient(160deg,#19212d,#141a23);border:1px solid var(--line);
  border-radius:12px;padding:14px 16px}
.kpi .lab{color:var(--dim);font-size:12px;letter-spacing:.3px}
.kpi .val{font-size:28px;font-weight:650;margin:4px 0 2px;font-variant-numeric:tabular-nums}
.kpi .note{color:var(--dim);font-size:11.5px}
.up{color:var(--long)} .dn{color:var(--short)} .neu{color:var(--dim)}
table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right}
th{color:var(--dim);font-weight:500;background:#121821;text-align:right;position:sticky;top:0}
th:first-child,td:first-child{text-align:left}
tbody tr:hover{background:#1a2230}
.scroll{max-height:430px;overflow:auto;border:1px solid var(--line);border-radius:10px}
.tag{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11.5px;border:1px solid}
.tag.warn{color:var(--warn);border-color:#5a4415;background:#2a2210}
.tag.ok{color:var(--short);border-color:#1e4a34;background:#0f2418}
.tag.bad{color:var(--long);border-color:#5c2226;background:#2a1114}
.tag.info{color:var(--accent);border-color:#1c4a63;background:#0d2632}
.ctl{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
button{background:#1d2632;color:var(--fg);border:1px solid var(--line);border-radius:8px;
  padding:6px 13px;cursor:pointer;font-size:12.5px;transition:.15s}
button:hover{border-color:var(--accent);color:var(--accent)}
button.on{background:#123046;border-color:var(--accent);color:var(--accent)}
canvas{display:block;width:100%}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin-top:8px}
.legend i{display:inline-block;width:13px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle}
.callout{border-left:3px solid var(--warn);background:#1d1a12;padding:11px 15px;border-radius:0 8px 8px 0;
  font-size:13px;margin:14px 0}
.callout.red{border-color:var(--long);background:#221214}
.callout.blue{border-color:var(--accent);background:#0d1c26}
.hl{color:var(--warn);font-weight:600}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}
footer{margin-top:50px;padding-top:18px;border-top:1px solid var(--line);color:var(--dim);font-size:12px}
.tooltip{position:fixed;pointer-events:none;background:#0b1017;border:1px solid var(--line);
  border-radius:8px;padding:8px 11px;font-size:12px;display:none;z-index:99;box-shadow:0 8px 24px #000a;
  font-variant-numeric:tabular-nums;max-width:290px}
.bar{height:7px;border-radius:4px;background:#222b38;position:relative;overflow:hidden}
.bar>span{position:absolute;top:0;bottom:0;border-radius:4px}
.small{font-size:12px;color:var(--dim)}
</style>
</head>
<body>
<div class="wrap">

<h1>甲醇 期现基差季节性研究报告</h1>
<div class="sub">
  标的：郑州商品交易所 MA 甲醇期货 × 生意社甲醇基准价（现货参考口径）&nbsp;|&nbsp;
  样本区间 <b id="span"></b>&nbsp;|&nbsp; 基差 = 现货 − 期货 &nbsp;|&nbsp;
  生成日期 2026-10-20 · <span class="mono">v1.0</span>
</div>

<div class="callout red">
  <b>口径声明（必读）</b>：本次研究的"现货"为 <b>生意社甲醇基准价</b>，生意社官方定义为
  「基于价格大数据与生意社价格模型产生的交易指导价」，公式 <span class="mono">结算价 = 基准价×K + C</span>，
  其中 C 吸收区域价差与物流。因此它是 <b>全国口径、含税、元/吨的交易参考价，并非华东（江苏/太仓）仓库报价</b>。
  经逐项核实，华东区域优等品现货的 5 年历史在免费渠道不可得（隆众/卓创需登录且数值被屏蔽；生意社区域图表仅保留 93 天且坐标标签存在 1 天偏移）。
  本报告据此 <b>降级为全国基准价口径</b>，所有"华东"结论仅代表该口径，不可直接用于太仓仓单套保定价。详见 §7。
</div>

<h2>一、首屏结论：当前基差处于什么位置</h2>
<div class="grid g4">
  <div class="kpi"><div class="lab">当前基差（近月连续）</div>
    <div class="val up" id="k-basis">—</div>
    <div class="note" id="k-basis-note">—</div></div>
  <div class="kpi"><div class="lab">历史同期分位（10 月）</div>
    <div class="val" id="k-pctl">—</div>
    <div class="note" id="k-pctl-note">—</div></div>
  <div class="kpi"><div class="lab">相对历史均值偏离</div>
    <div class="val" id="k-z">—</div>
    <div class="note" id="k-z-note">—</div></div>
  <div class="kpi"><div class="lab">季节性区间（10月 p10~p90）</div>
    <div class="val neu" id="k-band">—</div>
    <div class="note" id="k-band-note">—</div></div>
</div>

<div class="card" style="margin-top:14px">
  <h3 style="margin-top:0">当前基差在全年季节性区间中的位置（月度 p10–p90 分位带 · 当前年逐年叠加）</h3>
  <canvas id="c-ribbon" height="330"></canvas>
  <div class="legend">
    <span><i style="background:#3b4a5e"></i>p10–p90 历史区间</span>
    <span><i style="background:#2b6f91"></i>p25–p75 历史区间</span>
    <span><i style="background:#8b98a9"></i>历史中位数</span>
    <span><i style="background:#4cc2ff"></i>2026 年当前路径</span>
    <span><i style="background:#f5a524"></i>往年同期（均值）</span>
  </div>
</div>

<div class="callout blue">
  <b>一句话回答</b>：截至 <span id="asof"></span>，按近月连续口径，基差为
  <b id="one-line-v"></b>，处于 10 月历史同期 <b id="one-line-p"></b> 位置；
  按主力连续口径为 <b id="one-line-mv"></b>（同期分位 <b id="one-line-mp"></b>）。
  但 10 月历史同期样本仅 <b>4 年</b>，分位统计的置信度有限，<b>不能据此推断未来基差必然收敛</b>。
</div>

<h2>二、逐项核实：期现价格能否比较</h2>
<div class="card">
<div class="scroll"><table id="t-verify">
<thead><tr><th>核实项</th><th style="text-align:left">现货侧</th><th style="text-align:left">期货侧</th><th style="text-align:left">是否存在可比性障碍</th></tr></thead>
<tbody>
<tr><td>品种</td><td style="text-align:left">甲醇 CH3OH</td><td style="text-align:left">甲醇 MA</td><td style="text-align:left"><span class="tag ok">同品种</span></td></tr>
<tr><td>品质规格</td><td style="text-align:left">基准价（未标明优等品/合格品分级）</td><td style="text-align:left">GB/T 338-2011 工业用甲醇 <b>优等品</b>，不限乙醇含量</td><td style="text-align:left"><span class="tag warn">规格未对齐</span> 现货为综合基准价，非分级优等品报价</td></tr>
<tr><td>地区</td><td style="text-align:left"><b>全国口径</b>（非华东/太仓）</td><td style="text-align:left">郑商所，交割仓库分布于华东（太仓/张家港）、华南等</td><td style="text-align:left"><span class="tag bad">地区不匹配</span> 期货交割地集中在华东，故理论基差应更贴近华东现货</td></tr>
<tr><td>计价单位</td><td style="text-align:left">元/吨</td><td style="text-align:left">元/吨</td><td style="text-align:left"><span class="tag ok">一致</span></td></tr>
<tr><td>含税条件</td><td style="text-align:left">含税（交易参考价）</td><td style="text-align:left">含税（价格已含增值税）</td><td style="text-align:left"><span class="tag ok">一致</span> 无需再做税基调整</td></tr>
<tr><td>报价时点</td><td style="text-align:left">日度工作日发布约 08:30（实为前一交易日参考）</td><td style="text-align:left">日盘收盘 15:00 收盘价</td><td style="text-align:left"><span class="tag warn">存在时点错位</span> 同日在标定上按同一日期配对</td></tr>
<tr><td>交割/合约规则</td><td style="text-align:left">—</td><td style="text-align:left">最后交易日=交割月第 10 个交易日；最后交割日=交割月第 13 个交易日；交割单位 10 吨</td><td style="text-align:left"><span class="tag ok">已核实</span> 95 个合约中 91 个精确吻合，2 个提前 1 日（流动性），2 个待观察</td></tr>
<tr><td>频率</td><td style="text-align:left">工作日日度（1083 点）</td><td style="text-align:left">交易日日度</td><td style="text-align:left"><span class="tag ok">可对齐</span> 以期货交易日为骨架，现货缺报不填补</td></tr>
</tbody></table></div>
</div>

<h2>三、合约映射规则与换月记录</h2>
<div class="card">
  <div class="ctl">
    <span class="small">映射口径：</span>
    <button class="on" data-map="near">近月连续</button>
    <button data-map="main">主力连续</button>
    <span style="flex:1"></span>
    <span class="small" id="map-desc"></span>
  </div>
  <canvas id="c-roll" height="150"></canvas>
  <div class="scroll" style="max-height:300px;margin-top:12px">
    <table id="t-roll"></table>
  </div>
  <div class="callout">
    <b>关键发现：近月连续必须加流动性门槛。</b>最初按"当月合约持有到期"的朴素规则，2026-09-07 至 09-10 期间 MA2609 持仓已降至
    <b>1 309 手</b>（同期主力 MA2610 持仓 62 万手），其收盘价被低流动性扭曲（09-11 单日从 3 465 跳至 4 181，而当日 MA0 主力已跌至 3 016），
    造成基差被误读为 −454 元/吨。加入「临近交割 20 个交易日内、持仓 &lt; 主力 5% 即视为不可交割报价」门槛后，
    <b>共跳过 901 个伪近月报价日</b>，近月换月次数由 156 次降至 <b>50 次</b>，基差序列恢复合理。
  </div>
</div>

<h2>四、历史季节性统计（月度 · 周度）</h2>
<div class="card">
  <div class="ctl">
    <button class="on" data-freq="month">月度</button>
    <button data-freq="week">周度（ISO 周）</button>
    <span style="flex:1"></span>
    <span class="small">分位为同季节位置、跨年份的经验分位（线性插值）</span>
  </div>
  <canvas id="c-seas" height="360"></canvas>
  <div class="legend">
    <span><i style="background:#3b4a5e"></i>p10–p90</span>
    <span><i style="background:#2b6f91"></i>p25–p75</span>
    <span><i style="background:#8b98a9"></i>中位数</span>
    <span><i style="background:#a78bfa"></i>均值</span>
    <span><i style="background:#f5a524"></i>当前年</span>
  </div>
</div>
<div class="card">
  <h3 style="margin-top:0">月度分位明细（近月连续口径）</h3>
  <div class="scroll"><table id="t-seasonal"></table></div>
  <div class="small" style="margin-top:8px">有效样本数 = 该季节位置实际存在配对的年数；少于 3 年标记为样本不足。</div>
</div>

<h2>五、逐年原始基差曲线（不只给一条均值线）</h2>
<div class="card">
  <div class="ctl">
    <span class="small">显示口径：</span>
    <button class="on" data-curve="near">近月连续</button>
    <button data-curve="main">主力连续</button>
    <button data-curve="fixed">固定交割月</button>
    <span style="flex:1"></span>
    <span class="small" id="curve-desc"></span>
  </div>
  <canvas id="c-years" height="380"></canvas>
  <div class="legend" id="years-legend"></div>
</div>
<div class="card" id="fixed-panel" style="display:none">
  <h3 style="margin-top:0">固定交割月逐年基差（同一交割月 · 不同年份单列）</h3>
  <div class="ctl">
    <button class="on" data-fix="01">01 合约</button>
    <button data-fix="05">05 合约</button>
    <button data-fix="09">09 合约</button>
  </div>
  <div class="scroll"><table id="t-fixed"></table></div>
  <div class="callout blue">同一固定交割月在<b>不同年份</b>的基差是独立样本，绝不能与连续合约口径混为同一统计总体。此处按合约单列，年均值与极值仅用于对照合约自身生命周期。</div>
</div>

<h2>六、典型基差走强 / 走弱阶段</h2>
<div class="card">
  <div class="scroll"><table id="t-stages"></table></div>
  <div class="callout">
    识别方法：对月度基差求同月跨年均值 → 相邻月差值 → 排序取最强/最弱阶段。
    <b>注意</b>：阶段强弱是"历史平均形态"，2026 年 9–10 月的极端升水使 9/10 月的均值被单一年份严重拉偏（中位数 14.83 vs 均值 263.33），
    因此报告中同时给出均值与中位数，<b>以中位数为主要季节形态判据</b>。
  </div>
</div>

<h2>七、可比性检查：换月、交割规则、报价口径、样本变化</h2>
<div class="grid g2">
  <div class="card">
    <h3 style="margin-top:0">换月对基差的污染量化</h3>
    <canvas id="c-rollcmp" height="200"></canvas>
    <div class="scroll" style="max-height:180px;margin-top:10px"><table id="t-rollcmp"></table></div>
  </div>
  <div class="card">
    <h3 style="margin-top:0">月度季节性稳定性（跨年变异）</h3>
    <canvas id="c-stab" height="200"></canvas>
    <div class="scroll" style="max-height:180px;margin-top:10px"><table id="t-stab"></table></div>
  </div>
</div>
<div class="card">
  <h3 style="margin-top:0">可比性障碍清单与处理</h3>
  <div class="scroll"><table id="t-compare"></table></div>
</div>

<h2>八、历史季节性是否具有稳定性？</h2>
<div class="card">
  <p id="stab-concl"></p>
  <div class="grid g3">
    <div class="kpi"><div class="lab">季节性方差占比（月份间/总）</div><div class="val" id="k-ss">—</div>
      <div class="note">越高越稳定；&lt;25% 说明季节形态解释力有限</div></div>
    <div class="kpi"><div class="lab">最稳定月份（变异系数最低）</div><div class="val" id="k-bestmode">—</div>
      <div class="note" id="k-bestmode-note">—</div></div>
    <div class="kpi"><div class="lab">最不稳定月份</div><div class="val" id="k-worstmode">—</div>
      <div class="note" id="k-worstmode-note">—</div></div>
  </div>
</div>

<div class="callout red" style="margin-top:22px">
  <b>使用边界（重要）</b><br>
  1. 本报告展示的是<b>历史已实现</b>的基差季节性，<b>不是对未来基差变化的预测</b>。基差受库存、进口节奏、MTO 利润、运费与交割规则共同驱动，任一年份的形态都可能显著偏离历史。
  2. 现货口径为全国基准价而非华东报价，<b>绝对基差水平的可比性受限</b>，宜主要参考季节<b>形态与相对分位</b>。
  3. 各季节位置的有效样本仅 4–5 年，p10/p90 分位对极端年份高度敏感，<b>不应作为交易阈值</b>。
  4. 本项目<b>未使用库存与仓单数据</b>（郑商所公开接口返回 412，未能取得可靠序列），故"极值阶段的库存/仓单背景"一栏留空并标注为数据缺口，<b>未做任何估算或填充</b>。
</div>

<footer>
  数据来源：郑商所 MA 逐合约日线（新浪财经公开行情接口，95 个合约）· 生意社甲醇基准价（me.100ppi.com 资讯频道，1083 个工作日，逐条附原文链接）<br>
  计算脚本：scripts/fetch_spot_100ppi.py → scripts/build_basis.py → scripts/basis_seasonality.py → scripts/supp_analysis.py → scripts/make_report_data.py → 本页<br>
  本页自包含、可离线打开；所有数字均可由上述脚本从原始 CSV 复算。
</footer>
</div>

<div class="tooltip" id="tip"></div>

<script id="DATA" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('DATA').textContent);
const $ = s => document.querySelector(s);
const fmt = (v, d=1) => (v==null||isNaN(v)) ? '—' : Number(v).toLocaleString('zh-CN',{minimumFractionDigits:d,maximumFractionDigits:d});
const tip = $('#tip');
function showTip(e, html){
  tip.innerHTML = html; tip.style.display='block';
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + 300 > innerWidth) x = e.clientX - 300;
  if (y + 120 > innerHeight) y = e.clientY - 110;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
function hideTip(){ tip.style.display='none'; }

/* ---------- 首屏 KPI ---------- */
const mn = D.meta_near, mm = D.meta_main;
const cur = mn.current_position.month, curW = mn.current_position.week;
const asof = cur.as_of;
$('#span').textContent = mn.first + ' ~ ' + mn.last;
$('#asof').textContent = asof;
$('#k-basis').textContent = fmt(cur.value, 2) + ' 元/吨';
$('#k-basis-note').textContent = '截至 ' + cur.as_of + ' · 当月合约为 ' + (D.daily[D.daily.length-1].c||'');
$('#k-pctl').textContent = (cur.below_ratio==null?'—':cur.below_ratio.toFixed(0)+'%');
$('#k-pctl-note').textContent = '历史同期样本 ' + cur.n_hist + ' 年（不含 2026）';
$('#k-z').textContent = (cur.z>0?'+':'') + fmt(cur.z,2) + ' σ';
$('#k-z-note').textContent = '同期均值 ' + fmt(cur.hist_mean,1) + '，标准差 ' + fmt(cur.hist_sd,1);
const sm10 = D.seasonal_month.find(r=>r.month===10);
$('#k-band').textContent = fmt(sm10.p10,0) + ' ~ ' + fmt(sm10.p90,0);
$('#k-band-note').textContent = '10 月中位数 ' + fmt(sm10.median,1) + '，样本 ' + sm10.n_years + ' 年';

$('#one-line-v').textContent = fmt(cur.value,2) + ' 元/吨';
$('#one-line-p').textContent = cur.below_ratio.toFixed(0) + '% 分位';
$('#one-line-mv').textContent = fmt(mm.current_position.month.value,2) + ' 元/吨';
$('#one-line-mp').textContent = mm.current_position.month.below_ratio.toFixed(0) + '% 分位';

/* ---------- 通用绘图工具 ---------- */
function setup(canvas, h){
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || canvas.parentNode.clientWidth;
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.height = h + 'px';
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  return {ctx, w, h};
}
function axes(ctx, w, h, pad, ymin, ymax, xs, yTicks=6){
  const {l=62,r=16,t=14,b=28} = pad;
  ctx.strokeStyle='#26303f'; ctx.lineWidth=1; ctx.fillStyle='#8b98a9';
  ctx.font='11px -apple-system,Segoe UI,sans-serif'; ctx.textAlign='right'; ctx.textBaseline='middle';
  for(let i=0;i<=yTicks;i++){
    const v = ymin + (ymax-ymin)*i/yTicks;
    const y = t + (h-t-b)*(1 - i/yTicks);
    ctx.beginPath(); ctx.moveTo(l,y); ctx.lineTo(w-r,y); ctx.stroke();
    ctx.fillText(Math.round(v), l-8, y);
  }
  ctx.textAlign='center'; ctx.textBaseline='top';
  if(xs) xs(ymin,ymax,(v)=>{ const y = t + (h-t-b)*(1-(v-ymin)/(ymax-ymin)); return y; });
  return {l,r,t,b, y:v=> t + (h-t-b)*(1-(v-ymin)/(ymax-ymin)),
          x:(i,n)=> l + (w-l-r)*(n<=1?0.5:i/(n-1))};
}

/* ---------- 季节性区间带 + 当前年叠加 ---------- */
function drawRibbon(){
  const cv = $('#c-ribbon'); const {ctx,w,h} = setup(cv, 330);
  const S = D.seasonal_month; const months = S.map(r=>r.month);
  let lo = 0, hi = 0;
  S.forEach(r=>{ lo=Math.min(lo,r.p10??0); hi=Math.max(hi,r.p90??0); });
  const curY = D.monthly.filter(r=>r.y===2026);
  curY.forEach(r=>{ lo=Math.min(lo,r.b); hi=Math.max(hi,r.b); });
  lo = Math.floor((lo-60)/50)*50; hi = Math.ceil((hi+60)/50)*50;
  const pad={l:64,r:18,t:16,b:30};
  const g = axes(ctx,w,h,pad,lo,hi,()=>{});
  const X = i => pad.l + (w-pad.l-pad.r)*(i/(months.length-1));
  const Y = g.y;
  // 0 线
  ctx.strokeStyle='#5a6b80'; ctx.setLineDash([4,4]); ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(pad.l,Y(0)); ctx.lineTo(w-pad.r,Y(0)); ctx.stroke(); ctx.setLineDash([]);
  function band(key1,key2,color){
    ctx.beginPath();
    S.forEach((r,i)=>{ const x=X(i), y=Y(r[key1]); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
    for(let i=S.length-1;i>=0;i--){ ctx.lineTo(X(i), Y(S[i][key2])); }
    ctx.closePath(); ctx.fillStyle=color; ctx.fill();
  }
  band('p10','p90','#3b4a5e'); band('p25','p75','#2b6f91');
  // 中位数
  ctx.beginPath(); S.forEach((r,i)=>{ const x=X(i),y=Y(r.median); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
  ctx.strokeStyle='#8b98a9'; ctx.lineWidth=1.6; ctx.stroke();
  // 往年同期均值
  ctx.beginPath(); S.forEach((r,i)=>{ const x=X(i),y=Y(r.mean); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
  ctx.strokeStyle='#f5a524'; ctx.lineWidth=1.4; ctx.setLineDash([5,4]); ctx.stroke(); ctx.setLineDash([]);
  // 2026 当前路径
  ctx.beginPath();
  curY.forEach((r,i)=>{ const x=X((monthIdx(r.m)-1)+(dayFrac(r.d)), Y(r.b));
    i?ctx.lineTo(x,Y(r.b)):ctx.moveTo(x,Y(r.b)); });
  ctx.strokeStyle='#4cc2ff'; ctx.lineWidth=2.4; ctx.stroke();
  curY.forEach(r=>{ const x=X((r.m-1)+dayFrac(r.d));
    ctx.beginPath(); ctx.arc(x,Y(r.b),3,0,7); ctx.fillStyle='#4cc2ff'; ctx.fill(); });
  // 当前点
  const last = curY[curY.length-1];
  if(last){ const x=X((last.m-1)+dayFrac(last.d)), y=Y(last.b);
    ctx.beginPath(); ctx.arc(x,y,6,0,7); ctx.fillStyle='#e5484d'; ctx.fill();
    ctx.strokeStyle='#fff'; ctx.lineWidth=1.5; ctx.stroke(); }
  // x 轴
  ctx.fillStyle='#8b98a9'; ctx.font='11px -apple-system,sans-serif'; ctx.textAlign='center'; ctx.textBaseline='top';
  months.forEach((m,i)=> ctx.fillText(m+'月', X(i), h-pad.b+7));
  // 交互
  cv.onmousemove = e => {
    const rect = cv.getBoundingClientRect(); const x = e.clientX-rect.left;
    let best=0, bd=1e9;
    S.forEach((r,i)=>{ const d=Math.abs(X(i)-x); if(d<bd){bd=d;best=i;} });
    const r = S[best];
    showTip(e, `<b>${r.month} 月</b><br>p10–p90：${fmt(r.p10)} ~ ${fmt(r.p90)}<br>p25–p75：${fmt(r.p25)} ~ ${fmt(r.p75)}<br>中位数：${fmt(r.median,2)}<br>均值：${fmt(r.mean,2)}<br>样本年数：${r.n_years}`);
  };
  cv.onmouseleave = hideTip;
}
const monthIdx = r => r.m;
function dayFrac(d){ // 用日粗略表示月内位置（0~0.95）
  const dd = parseInt(d.slice(8,10),10);
  return Math.min(dd/31, 0.95);
}

/* ---------- 换月记录 ---------- */
let rollMap = 'near';
function drawRoll(){
  const rows = rollMap==='near'? D.rolls_near : D.rolls_main;
  const t = $('#t-roll');
  t.innerHTML = '<thead><tr><th>换月日</th><th>移出</th><th>移入</th><th>移出收盘</th><th>移入收盘</th><th>跨日跳空(元/吨)</th><th>跳空占比</th></tr></thead><tbody>' +
    rows.map(r=>`<tr><td>${r['换月日']}</td><td>${r['移出合约']}</td><td>${r['移入合约']}</td>
      <td>${fmt(r['移出前收盘'])}</td><td>${fmt(r['移入日收盘'])}</td>
      <td class="${(+r['换月跳空(元/吨)'])>=0?'up':'dn'}">${fmt(r['换月跳空(元/吨)'],1)}</td>
      <td>${r['跳空占比%']}%</td></tr>`).join('') + '</tbody>';
  $('#map-desc').textContent = rollMap==='near'
    ? `近月连续：当月合约持有至最后交易日，临近交割且持仓<主力5%时切换（共 ${rows.length} 次换月）`
    : `主力连续：每日取持仓量最大合约（共 ${rows.length} 次换月）`;
  // 条形图：每次换月的跳空幅度
  const cv = $('#c-roll'); const {ctx,w,h} = setup(cv, 150);
  const gaps = rows.map(r=>+r['换月跳空(元/吨)']);
  const m = Math.max(10, ...gaps.map(Math.abs));
  const zero = h/2, bw = (w-40)/gaps.length;
  ctx.font='11px sans-serif';
  gaps.forEach((g,i)=>{
    const x = 20 + i*bw + bw*0.15, bh = Math.abs(g)/m*(h/2-22);
    ctx.fillStyle = g>=0? '#e5484d':'#30a46c';
    ctx.fillRect(x, g>=0? zero-bh : zero, bw*0.7, bh);
  });
  ctx.strokeStyle='#3a4657'; ctx.beginPath(); ctx.moveTo(0,zero); ctx.lineTo(w,zero); ctx.stroke();
  ctx.fillStyle='#8b98a9'; ctx.textAlign='left'; ctx.textBaseline='top';
  ctx.fillText('换月日跨日跳空（红=升水扩大，绿=贴水扩大）', 8, 4);
  ctx.textAlign='right'; ctx.textBaseline='bottom';
  ctx.fillText('最大 '+fmt(Math.max(...gaps.map(Math.abs)),0)+' 元/吨', w-8, h-4);
}
document.querySelectorAll('[data-map]').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('[data-map]').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); rollMap=b.dataset.map; drawRoll();
});

/* ---------- 季节性柱带 ---------- */
let freq = 'month';
function drawSeas(){
  const cv=$('#c-seas'); const {ctx,w,h}=setup(cv,360);
  const S = freq==='month'? D.seasonal_month : D.seasonal_week;
  const key = freq==='month'? 'month':'iso_week';
  const valid = S.filter(r=>r.mean!=null);
  let lo=0, hi=0; valid.forEach(r=>{ lo=Math.min(lo,r.p10??0); hi=Math.max(hi,r.p90??0); });
  lo=Math.floor((lo-+50)/50)*50; hi=Math.ceil((hi+50)/50)*50;
  const pad={l:64,r:18,t:14,b:32};
  const g = axes(ctx,w,h,pad,lo,hi,()=>{});
  const Y=g.y;
  ctx.strokeStyle='#5a6b80'; ctx.setLineDash([4,4]);
  ctx.beginPath(); ctx.moveTo(pad.l,Y(0)); ctx.lineTo(w-pad.r,Y(0)); ctx.stroke(); ctx.setLineDash([]);
  const bw = (w-pad.l-pad.r)/S.length;
  valid.forEach((r,i)=>{
    const idx = S.indexOf(r);
    const x = pad.l + idx*bw + bw*0.18, ww = bw*0.64;
    const y10=Y(r.p10), y90=Y(r.p90), y25=Y(r.p25), y75=Y(r.p75);
    ctx.fillStyle='#3b4a5e'; ctx.fillRect(x, y90, ww, y10-y90);
    ctx.fillStyle='#2b6f91'; ctx.fillRect(x, y75, ww, y25-y75);
    ctx.fillStyle='#8b98a9'; ctx.fillRect(x+ww*0.2, Y(r.median)-1, ww*0.6, 2);
    ctx.fillStyle='#a78bfa'; ctx.beginPath(); ctx.arc(x+ww/2, Y(r.mean), 2.6,0,7); ctx.fill();
  });
  // 当前年
  if(freq==='month'){
    const curY = D.monthly.filter(r=>r.y===2026);
    ctx.beginPath();
    curY.forEach((r,i)=>{ const idx=S.findIndex(s=>s.month===r.m);
      const x = pad.l + idx*bw + bw/2; i?ctx.lineTo(x,Y(r.b)):ctx.moveTo(x,Y(r.b)); });
    ctx.strokeStyle='#f5a524'; ctx.lineWidth=2; ctx.stroke();
    curY.forEach(r=>{ const idx=S.findIndex(s=>s.month===r.m);
      const x=pad.l+idx*bw+bw/2; ctx.beginPath(); ctx.arc(x,Y(r.b),3.4,0,7); ctx.fillStyle='#f5a524'; ctx.fill(); });
  }
  ctx.fillStyle='#8b98a9'; ctx.font='10.5px sans-serif'; ctx.textAlign='center'; ctx.textBaseline='top';
  S.forEach((r,i)=>{ if(r[key]% (freq==='week'?4:1) ===0 || freq==='month')
    ctx.fillText(freq==='month'? r.month+'月':'W'+r.iso_week, pad.l+i*bw+bw/2, h-pad.b+7); });
  cv.onmousemove = e=>{
    const rect=cv.getBoundingClientRect(); const x=e.clientX-rect.left-pad.l;
    const i=Math.floor(x/bw); if(i<0||i>=S.length) return; const r=S[i];
    showTip(e, `<b>${freq==='month'?r.month+' 月':'第 '+r.iso_week+' 周'}</b><br>
      p10：${fmt(r.p10)}<br>p25：${fmt(r.p25)}<br>中位数：${fmt(r.median)}<br>均值：${fmt(r.mean)}<br>
      p75：${fmt(r.p75)}<br>p90：${fmt(r.p90)}<br>有效年数：${r.n_years}`);
  };
  cv.onmouseleave=hideTip;
  // 表格
  const rows = freq==='month'
    ? D.seasonal_month.map(r=>[r.month+'月',r.n_years,r.mean,r.median,r.p10,r.p25,r.p75,r.p90,r.min,r.max])
    : D.seasonal_week.filter(r=>r.n_years>0).map(r=>['W'+r.iso_week,r.n_years,r.mean,r.median,r.p10,r.p25,r.p75,r.p90,'','']);
  $('#t-seasonal').innerHTML = '<thead><tr><th>'+(freq==='month'?'月份':'ISO周')+'</th><th>有效样本年数</th><th>均值</th><th>中位数</th><th>p10</th><th>p25</th><th>p75</th><th>p90</th><th>最小</th><th>最大</th></tr></thead><tbody>' +
    rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td>${fmt(r[2])}</td><td>${fmt(r[3])}</td>
      <td>${fmt(r[4])}</td><td>${fmt(r[5])}</td><td>${fmt(r[6])}</td><td>${fmt(r[7])}</td>
      <td>${fmt(r[8])}</td><td>${fmt(r[9])}</td></tr>`).join('') + '</tbody>';
}
document.querySelectorAll('[data-freq]').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('[data-freq]').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); freq=b.dataset.freq; drawSeas();
});

/* ---------- 逐年原始曲线 ---------- */
let curveMode='near';
const YEAR_COLORS = ['#4cc2ff','#a78bfa','#30a46c','#f5a524','#e5484d','#f472b6'];
function drawYears(){
  const cv=$('#c-years'); const {ctx,w,h}=setup(cv,380);
  const pad={l:64,r:18,t:16,b:32};
  let series = [];
  if(curveMode==='near'||curveMode==='main'){
    const src = curveMode==='near'? D.daily : D.daily_main;
    const byY = {};
    src.forEach(r=>{ const y=r.d.slice(0,4); (byY[y]=byY[y]||[]).push({d:r.d,b:r.b}); });
    series = Object.keys(byY).sort().map((y,i)=>({name:y+'年', color:YEAR_COLORS[i%6], data:byY[y]}));
    $('#curve-desc').textContent = curveMode==='near'
      ? '近月连续：每个自然年一条曲线，不跨年拼接'
      : '主力连续：每个自然年一条曲线';
    $('#fixed-panel').style.display='none';
  } else {
    series = [];
    $('#curve-desc').textContent = '固定交割月已在上方明细表展示';
    $('#fixed-panel').style.display='block';
  }
  let lo=0,hi=0;
  series.forEach(s=>s.data.forEach(p=>{ if(p.b!=null){lo=Math.min(lo,p.b);hi=Math.max(hi,p.b);} }));
  if(!series.length){ lo=-100; hi=200; }
  lo=Math.floor((lo-60)/50)*50; hi=Math.ceil((hi+60)/50)*50;
  const g = axes(ctx,w,h,pad,lo,hi,()=>{}); const Y=g.y;
  ctx.strokeStyle='#5a6b80'; ctx.setLineDash([4,4]);
  ctx.beginPath(); ctx.moveTo(pad.l,Y(0)); ctx.lineTo(w-pad.r,Y(0)); ctx.stroke(); ctx.setLineDash([]);
  // 月度刻度
  ctx.fillStyle='#8b98a9'; ctx.font='11px sans-serif'; ctx.textAlign='center'; ctx.textBaseline='top';
  for(let m=1;m<=12;m++) ctx.fillText(m+'月', pad.l+(w-pad.l-pad.r)*((m-0.5)/12), h-pad.b+7);
  ctx.strokeStyle='#1e2632';
  for(let m=1;m<12;m++){ const x=pad.l+(w-pad.l-pad.r)*(m/12); ctx.beginPath(); ctx.moveTo(x,pad.t); ctx.lineTo(x,h-pad.b); ctx.stroke(); }
  series.forEach(s=>{
    ctx.beginPath(); let started=false;
    s.data.forEach(p=>{ if(p.b==null) return;
      const m=+p.d.slice(5,7), dd=+p.d.slice(8,10);
      const x = pad.l + (w-pad.l-pad.r)*(((m-1)+Math.min(dd/31,0.95))/12);
      const y = Y(p.b);
      started?ctx.lineTo(x,y):ctx.moveTo(x,y); started=true; });
    ctx.strokeStyle=s.color; ctx.lineWidth=1.9; ctx.stroke();
  });
  // 当前点
  const lastAll = D.daily[D.daily.length-1];
  if(curveMode==='near' && lastAll){
    const m=+lastAll.d.slice(5,7), dd=+lastAll.d.slice(8,10);
    const x=pad.l+(w-pad.l-pad.r)*(((m-1)+Math.min(dd/31,0.95))/12), y=Y(lastAll.b);
    ctx.beginPath(); ctx.arc(x,y,5.5,0,7); ctx.fillStyle='#e5484d'; ctx.fill();
    ctx.strokeStyle='#fff'; ctx.lineWidth=1.5; ctx.stroke();
  }
  $('#years-legend').innerHTML = series.map(s=>`<span><i style="background:${s.color}"></i>${s.name}</span>`).join('') +
    (curveMode!=='fixed'?'<span><i style="background:#e5484d"></i>当前基差</span>':'');
  cv.onmousemove = e=>{
    const rect=cv.getBoundingClientRect(); const x=e.clientX-rect.left;
    const t = (x-pad.l)/(w-pad.l-pad.r); if(t<0||t>1) return;
    const targetMonth = t*12;
    let html = `<b>约 ${(Math.floor(targetMonth)+1)} 月</b>`;
    series.forEach(s=>{
      let best=null, bd=1e9;
      s.data.forEach(p=>{ const m=+p.d.slice(5,7), dd=+p.d.slice(8,10);
        const tp=(m-1)+Math.min(dd/31,0.95); const d=Math.abs(tp-targetMonth);
        if(d<bd){bd=d;best=p;} });
      if(best) html += `<br><span style="color:${s.color}">■</span> ${s.name}：${fmt(best.b)} <span style="color:#8b98a9">(${best.d})</span>`;
    });
    showTip(e, html);
  };
  cv.onmouseleave=hideTip;
}
document.querySelectorAll('[data-curve]').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('[data-curve]').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); curveMode=b.dataset.curve; drawYears();
});

/* ---------- 固定交割月表 ---------- */
let fixMM='01';
function drawFixed(){
  const rows = D.fixed[fixMM]||[];
  $('#t-fixed').innerHTML = '<thead><tr><th>合约</th><th>样本日数</th><th>起始</th><th>结束</th><th>基差均值</th><th>基差中位</th><th>最小</th><th>最大</th></tr></thead><tbody>' +
    D.fixed_summary.filter(r=>r['交割月']===fixMM).map(r=>
      `<tr><td>${r['合约']}</td><td>${r['样本日数']}</td><td>${r['起始']}</td><td>${r['结束']}</td>
       <td class="${+r['基差均值']>=0?'up':'dn'}">${fmt(r['基差均值'])}</td><td>${fmt(r['基差中位'])}</td>
       <td>${fmt(r['最小'])}</td><td>${fmt(r['最大'])}</td></tr>`).join('') + '</tbody>';
}
document.querySelectorAll('[data-fix]').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('[data-fix]').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); fixMM=b.dataset.fix; drawFixed();
});

/* ---------- 阶段表 ---------- */
function drawStages(){
  const S = D.seasonal_month.filter(r=>r.median!=null);
  const diffs = [];
  for(let i=1;i<S.length;i++) diffs.push({from:S[i-1], to:S[i], d:(S[i].median - S[i-1].median)});
  diffs.sort((a,b)=>b.d-a.d);
  const strong = diffs.slice(0,3), weak = diffs.slice(-3).reverse();
  const row = (x,dir)=>`<tr><td>${x.from.month}月 → ${x.to.month}月</td>
    <td class="${dir==='up'?'up':'dn'}">${(x.d>0?'+':'')+fmt(x.d)}</td>
    <td>${fmt(x.from.median)} → ${fmt(x.to.median)}</td>
    <td>${dir==='up'?'<span class="tag ok">基差走强</span>':'<span class="tag bad">基差走弱</span>'}</td></tr>`;
  $('#t-stages').innerHTML = '<thead><tr><th>月份区间（中位数口径）</th><th>中位基差变化(元/吨)</th><th>中位基差</th><th>判定</th></tr></thead><tbody>' +
    strong.map(x=>row(x,'up')).join('') + weak.map(x=>row(x,'dn')).join('') + '</tbody>';
}

/* ---------- 换月污染对比 ---------- */
function drawRollCmp(){
  const rows = D.change_compare;
  const cv=$('#c-rollcmp'); const {ctx,w,h}=setup(cv,200);
  const vals = rows.map(r=>+r['均值']), mx = Math.max(...vals)*1.25;
  const bw = (w-80)/rows.length;
  ctx.font='11px sans-serif';
  rows.forEach((r,i)=>{
    const bh = (+r['均值'])/mx*(h-60);
    const x = 60+i*bw+bw*0.22, y = h-40-bh;
    ctx.fillStyle = i? '#2b6f91':'#e5484d';
    ctx.fillRect(x,y,bw*0.56,bh);
    ctx.fillStyle='#e6edf3'; ctx.textAlign='center'; ctx.textBaseline='bottom';
    ctx.fillText(fmt(r['均值'],1), x+bw*0.28, y-4);
    ctx.fillStyle='#8b98a9'; ctx.textBaseline='top';
    ctx.fillText(r['类别'].replace('基差日变化','').replace('基差跨日变化',''), x+bw*0.28, h-34);
  });
  ctx.fillStyle='#8b98a9'; ctx.textAlign='left'; ctx.textBaseline='top';
  ctx.fillText('基差日变化绝对值均值（元/吨）', 8, 4);
  $('#t-rollcmp').innerHTML = '<thead><tr><th>类别</th><th>样本数</th><th>均值</th><th>中位</th><th>p90</th><th>最大</th></tr></thead><tbody>' +
    rows.map(r=>`<tr><td>${r['类别']}</td><td>${r['样本数']}</td><td>${fmt(r['均值'])}</td><td>${fmt(r['中位'])}</td>
      <td>${fmt(r['p90'])}</td><td>${fmt(r['最大'])}</td></tr>`).join('') + '</tbody>';
}

/* ---------- 稳定性 ---------- */
function drawStab(){
  const rows = D.stability;
  const cv=$('#c-stab'); const {ctx,w,h}=setup(cv,200);
  const mx = Math.max(...rows.map(r=>+r['变异系数']||0));
  const bw = (w-70)/rows.length;
  ctx.font='11px sans-serif';
  rows.forEach((r,i)=>{
    const v = +r['变异系数']||0;
    const bh = v/mx*(h-56);
    const x = 56+i*bw+bw*0.2;
    ctx.fillStyle = v>1 ? (v>1.5? '#e5484d':'#f5a524') : '#30a46c';
    ctx.fillRect(x, h-30-bh, bw*0.6, bh);
    ctx.fillStyle='#8b98a9'; ctx.textAlign='center'; ctx.textBaseline='top';
    ctx.fillText(r['月份']+'月', x+bw*0.3, h-24);
  });
  ctx.fillStyle='#8b98a9'; ctx.textAlign='left'; ctx.textBaseline='top';
  ctx.fillText('跨年变异系数（越低越稳定）', 8, 4);
  $('#t-stab').innerHTML = '<thead><tr><th>月份</th><th>样本年数</th><th>均值</th><th>标准差</th><th>变异系数</th><th>升水年份占比</th></tr></thead><tbody>' +
    rows.map(r=>`<tr><td>${r['月份']}月</td><td>${r['样本年数']}</td><td>${fmt(r['均值'])}</td>
      <td>${fmt(r['标准差'])}</td><td>${r['变异系数']}</td><td>${(+r['升水年份占比']*100).toFixed(0)}%</td></tr>`).join('') + '</tbody>';
  // KPI
  const ss = mn.stability.seasonal_ss_share;
  $('#k-ss').textContent = (ss*100).toFixed(1)+'%';
  const sorted = [...rows].sort((a,b)=>(+a['变异系数'])-(+b['变异系数']));
  const best = sorted[0], worst = sorted[sorted.length-1];
  $('#k-bestmode').textContent = best['月份']+'月';
  $('#k-bestmode-note').textContent = 'CV '+best['变异系数']+'，升水年份 '+Math.round(best['升水年份占比']*100)+'%';
  $('#k-worstmode').textContent = worst['月份']+'月';
  $('#k-worstmode-note').textContent = 'CV '+worst['变异系数']+'，极差 '+fmt(+worst['最大值']-+worst['最小值'])+' 元/吨';
  $('#stab-concl').innerHTML =
    `月度季节形态仅解释了基差总方差的 <b>${(ss*100).toFixed(1)}%</b>（月份间平方和 / 总平方和），`+
    `其余 <b>${(100-ss*100).toFixed(1)}%</b> 来自年份间与月内波动。这意味着：`+
    `<b>历史季节性存在，但强度偏弱，且多数月份的跨年离散度超过其均值本身</b>（变异系数 &gt; 1）。`+
    `真正相对稳定的只有 <b>${best['月份']}月</b>（CV ${best['变异系数']}）与 <b>8 月</b>（升级年份占比 0%，即历史上 8 月几乎总是贴水）。`+
    `相反，<b>${worst['月份']}月</b> 是全年最不可靠的季节位置（CV ${worst['变异系数']}）。`;
}

/* ---------- 可比性清单 ---------- */
function drawCompare(){
  const items = [
    ['现货口径降级','全国基准价 vs 华东仓库报价','已量化：绝对水平偏误，形态可比','warn'],
    ['规格不对齐','基准价未分级 vs 优等品交割标准','无法消除，标注为口径限制','bad'],
    ['换月伪跳空','连续合约切换导致价格阶跃','已加流动性门槛；同日两合约价差可剥离','ok'],
    ['流动性枯竭合约','临近交割持仓仅 1 309 手','已跳过 901 个伪近月报价日','ok'],
    ['最后交易日规则','交割月第 10 个交易日','91/95 精确吻合，2 个提前 1 日','ok'],
    ['报价时点错位','现货 08:30 发布 vs 期货 15:00 收盘','按同日配对，存在 1 日错位','warn'],
    ['样本年份不足','各季节位置仅 4–5 年','分位统计置信度低，已标注 n','warn'],
    ['库存/仓单数据','郑商所接口 412 不可得','未做任何填补，留作数据缺口','bad'],
  ];
  $('#t-compare').innerHTML = '<thead><tr><th>障碍</th><th style="text-align:left">描述</th><th style="text-align:left">处理方式</th><th>状态</th></tr></thead><tbody>' +
    items.map(([a,b,c,s])=>`<tr><td>${a}</td><td style="text-align:left">${b}</td><td style="text-align:left">${c}</td>
      <td><span class="tag ${s}">${s==='ok'?'已处理':s==='warn'?'受限':'缺口'}</span></td></tr>`).join('') + '</tbody>';
}

function drawAll(){ drawRibbon(); drawRoll(); drawSeas(); drawYears(); drawFixed(); drawStages(); drawRollCmp(); drawStab(); drawCompare(); }
window.addEventListener('resize', ()=>{ drawAll(); });
drawAll();
</script>
</body>
</html>
"""


def main():
    data = json.dumps(DATA, ensure_ascii=False, separators=(',', ':'))
    html = TPL.replace('__DATA__', data)
    dst = os.path.join(OUT, '甲醇_基差季节性研究报告.html')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(html)
    print('[OK]', dst, os.path.getsize(dst) // 1024, 'KB')


if __name__ == '__main__':
    main()
