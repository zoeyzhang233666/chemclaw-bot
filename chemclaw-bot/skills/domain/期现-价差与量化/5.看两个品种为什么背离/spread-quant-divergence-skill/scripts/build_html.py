# -*- coding: utf-8 -*-
"""build_html.py — 生成自包含交互式 HTML 报告"""
import json
import os

B = r"./_pp_ll_skew"
R = json.load(open(os.path.join(B, "result.json"), encoding="utf-8"))
N = json.load(open(os.path.join(B, "narrative.json"), encoding="utf-8"))

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>PP 与 LLDPE 为什么背离 · 双品种诊断</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--txt:#e6edf3;--dim:#8b949e;
--pp:#f0883e;--l:#3fb950;--acc:#58a6ff;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:.5px}
h2{font-size:19px;margin:38px 0 12px;padding-left:11px;border-left:4px solid var(--acc)}
h3{font-size:15px;margin:20px 0 8px;color:var(--acc)}
.sub{color:var(--dim);font-size:13px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
.grid{display:grid;gap:12px}
.g2{grid-template-columns:repeat(2,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:900px){.g2,.g3,.g4{grid-template-columns:1fr}}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .v{font-size:22px;font-weight:650;margin:2px 0}
.kpi .k{color:var(--dim);font-size:12px}
.pos{color:var(--l)}.neg{color:var(--bad)}.neu{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}
th{color:var(--dim);font-weight:600;font-size:12px;background:#1c2128}
tr:hover td{background:#1c2128}
.tag{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11px;border:1px solid}
.t-pp{color:var(--pp);border-color:var(--pp)}
.t-l{color:var(--l);border-color:var(--l)}
.t-acc{color:var(--acc);border-color:var(--acc)}
.note{background:#1c2128;border-left:3px solid var(--warn);padding:11px 14px;border-radius:0 6px 6px 0;margin:12px 0;font-size:13px}
.note.bad{border-left-color:var(--bad)}
.note.ok{border-left-color:var(--l)}
canvas{width:100%;height:300px;display:block}
.tabs{display:flex;gap:8px;margin:10px 0 14px;flex-wrap:wrap}
.tab{padding:6px 15px;border:1px solid var(--line);border-radius:20px;cursor:pointer;font-size:13px;color:var(--dim);background:transparent}
.tab.on{background:var(--acc);color:#0d1117;border-color:var(--acc);font-weight:600}
.legend{display:flex;gap:18px;font-size:12px;color:var(--dim);margin:6px 0}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle}
.brush{font-size:12px;color:var(--dim);margin-top:6px}
select,button{background:#21262d;color:var(--txt);border:1px solid var(--line);
border-radius:6px;padding:5px 10px;font-size:13px;cursor:pointer}
ol,ul{padding-left:22px}li{margin:5px 0}
code{background:#21262d;padding:1px 6px;border-radius:4px;font-size:12px;color:#79c0ff}
.foot{margin-top:50px;padding-top:16px;border-top:1px solid var(--line);color:var(--dim);font-size:12px}
</style>
</head>
<body><div class="wrap">

<h1>PP 与 LLDPE 为什么背离</h1>
<div class="sub">__WINDOW__ · 期货主力连续日度 726 个交易日 + 现货日报核验 · 数据截止 __END__</div>

<div class="note bad" style="margin-top:16px">
<b>核心纪律：</b>本报告只做<b>统计描述 + 双边基本面事实核查</b>。
滚动相关性的下降<b>不能</b>被解读为"PP 基本面导致 LLDPE 下跌"——相关性变化既可能来自 A 边、B 边，
也可能来自共同成本或统计假象。所有归因在第 6 节都以"待验证假设"形式列出，并标注证伪条件。
</div>

<h2>1 先回答：这两个品种为什么值得比</h2>
<div class="card">
__REL__
</div>

<div class="grid g4" style="margin-top:12px">
__KPI__
</div>

<h2>2 价格可比性检查：单位、地区、规格、合约</h2>
<div class="card">
<p class="sub" style="margin-top:0">价格背离研究最常见的错误，是把不可比的两个价格放在一起。逐项核对如下：</p>
<table>
<thead><tr><th>维度</th><th>PP（聚丙烯）</th><th>LLDPE（线型低密度聚乙烯）</th><th>可比性结论</th></tr></thead>
<tbody>
<tr><td>计价单位</td><td>元/吨，含税</td><td>元/吨，含税</td><td class="pos">✓ 一致</td></tr>
<tr><td>期货合约规模</td><td>5 吨/手（DCE pp）</td><td>5 吨/手（DCE l）</td><td class="pos">✓ 一致</td></tr>
<tr><td>交割地</td><td>华东为主（浙江/江苏/上海/山东）</td><td>华东/华北/华南多点</td><td class="neu">△ 区域集合不完全重合</td></tr>
<tr><td>基准规格</td><td>拉丝（均聚，注塑级）</td><td>7042（薄膜级，国产料）</td><td class="neu">△ 用途不同，非同质品</td></tr>
<tr><td>上游原料</td><td>丙烯（油/煤/PDH 三路径）</td><td>乙烯（油/煤/乙烷/轻烃）</td><td class="neu">△ 同属烯烃，但路径权重不同</td></tr>
<tr><td>下游</td><td>编织袋、BOPP、注塑、纤维</td><td>农膜、包装膜</td><td class="neu">△ 需求季节不同</td></tr>
<tr><td>替代关系</td><td colspan="2">部分场景互替（薄膜、注塑件），但<b>不构成完全替代</b></td><td class="neu">△ 弱替代 → 价差有边界但无硬锚</td></tr>
</tbody></table>
<div class="note">
<b>结论：</b>两者可比但<b>非同质</b>。因此本报告<b>同时</b>使用三种口径：
<b>①归一化价格</b>（消除绝对水平差异，看相对强弱）、
<b>②价差 PP−L 元/吨</b>（产业习惯口径，直观但有量级漂移）、
<b>③比价 PP/L</b>（无量纲，对长期成本中枢下移更稳健）。
任何单一指标都不足以判定背离。
</div>
</div>

<h2>3 三种视图：价格叠加 · 价差/比价 · 滚动相关</h2>
<div class="tabs">
<div class="tab on" data-v="norm">归一化价格</div>
<div class="tab" data-v="spread">价差 PP−L</div>
<div class="tab" data-v="ratio">比价 PP/L</div>
<div class="tab" data-v="corr">滚动相关</div>
<div class="tab" data-v="z">背离 z 分数</div>
</div>
<div class="card">
<div class="legend">
<span><span class="dot" style="background:#f0883e"></span>PP 聚丙烯</span>
<span><span class="dot" style="background:#3fb950"></span>LLDPE 线型低密度聚乙烯</span>
<span><span class="dot" style="background:#58a6ff"></span>价差/比价/相关</span>
</div>
<canvas id="c3" height="300"></canvas>
<div class="brush" id="info3"></div>
</div>

<h2>4 相关性：水平相关 vs 收益率相关</h2>
<div class="grid g2">
<div class="card">
<h3 style="margin-top:0">全样本相关系数</h3>
__CORR__
<div class="note" style="margin-bottom:0">
<b>关键点：</b>价格<b>水平</b>相关（__LVL__）低于<b>收益率</b>相关（__RET__）。
这说明两条价格曲线"看起来靠得很近"并不是因为它们同频波动，而更多来自<b>共同趋势与共同成本</b>。
判断背离，应以<b>收益率相关</b>为主、<b>水平相关</b>仅作参考——否则极易把趋势造成的
"平行上涨"误读成"紧密联动"。
</div>
</div>
<div class="card">
<h3 style="margin-top:0">分年度演变</h3>
__YEAR__
</div>
</div>

<div class="card">
<h3 style="margin-top:0">滚动相关（20 / 60 / 120 期，收益率口径）</h3>
<canvas id="c4" height="280"></canvas>
<div class="brush">灰色虚线为 95% 显著性参考带 ±1.96/√(n−3)（Fisher z 近似）。相关跌破下沿，说明"同步性"在统计上已不成立。</div>
</div>

<h2>5 背离识别：明确规则，可复现</h2>
<div class="card">
<div class="note ok" style="margin-top:0">
<b>识别规则（四步，全部参数公开）：</b>
<ol style="margin:8px 0 0">
<li><b>指标</b>：I = 价差（PP−L）或 比价（PP/L），二选一分别计算。</li>
<li><b>中枢</b>：μ = I 的 20（或 60）期滚动均值，σ = 同期滚动标准差。<b>用滚动而非全样本</b>，避免前视偏差。</li>
<li><b>进入/退出</b>：|z| ≥ <code>1.5</code> 记为进入偏离，|z| &lt; <code>0.5</code> 记为回归；同一段内符号须一致。</li>
<li><b>噪声过滤</b>：持续期 &lt; <code>5</code> 个交易日的段丢弃。</li>
</ol>
</div>
<div class="tabs"><div class="tab on" data-r="spread_60">价差 · 60期</div><div class="tab" data-r="spread_20">价差 · 20期</div>
<div class="tab" data-r="ratio_60">比价 · 60期</div><div class="tab" data-r="ratio_20">比价 · 20期</div></div>
<div id="segtable"></div>
</div>

<h2>6 双边基本面核查：背离来自哪一边？</h2>
<div class="note">
以下每一条都是<b>可追溯的公开事实</b>（含来源与日期）。请特别注意：事实能说明<b>两侧条件不同</b>，
但<b>不能</b>单独证明"就是它造成了价差走阔/收窄"。
</div>
__FUND__

<h2>7 结论与证据局限</h2>
<div class="card">
__CONCL__
</div>

<h2>8 数据来源与缺口声明</h2>
<div class="card">
__SRC__
</div>

<div class="foot">
本报告由「期现价差与量化研究 · 看两个品种为什么背离」Skill 生成 · 数据截止 __END__<br/>
仅供研究参考，不构成投资建议。相关性不等于因果；历史统计不保证未来表现。
</div>
</div>

<script>
const D = __DATA__;
const FMT = (v,d=0)=> v==null? '—' : Number(v).toLocaleString('zh-CN',{minimumFractionDigits:d,maximumFractionDigits:d});
function seriesXY(dates, vals){
  const pts=[]; for(let i=0;i<dates.length;i++){ if(vals[i]!=null) pts.push([i, vals[i]]); } return pts;
}
function drawLine(cv, cfg){
  const dpr=window.devicePixelRatio||1;
  const w=cv.clientWidth, h=cv.clientHeight;
  cv.width=w*dpr; cv.height=h*dpr;
  const g=cv.getContext('2d'); g.setTransform(dpr,0,0,dpr,0,0);
  g.clearRect(0,0,w,h);
  const pad={l:56,r:14,t:14,b:26};
  const iw=w-pad.l-pad.r, ih=h-pad.t-pad.b;
  let all=[]; cfg.series.forEach(s=>s.pts.forEach(p=>all.push(p[1])));
  if(cfg.band) all=all.concat([cfg.band[0],cfg.band[1]]);
  if(!all.length) return null;
  let mn=Math.min(...all), mx=Math.max(...all);
  if(cfg.zeroLine){ mn=Math.min(mn,0); mx=Math.max(mx,0); }
  const padv=(mx-mn)*0.08||1; mn-=padv; mx+=padv;
  const N=cfg.n-1;
  const X=i=>pad.l+(N<=0?0:i/N*iw);
  const Y=v=>pad.t+(mx-v)/(mx-mn)*ih;
  // grid
  g.strokeStyle='#30363d'; g.lineWidth=1; g.font='11px sans-serif'; g.fillStyle='#8b949e';
  for(let k=0;k<=4;k++){
    const v=mn+(mx-mn)*k/4, y=Y(v);
    g.beginPath(); g.moveTo(pad.l,y); g.lineTo(w-pad.r,y); g.stroke();
    g.textAlign='right'; g.fillText(cfg.fmtY?cfg.fmtY(v):FMT(v), pad.l-6, y+4);
  }
  if(cfg.zeroLine){ const y=Y(0); g.strokeStyle='#484f58'; g.beginPath(); g.moveTo(pad.l,y); g.lineTo(w-pad.r,y); g.stroke(); }
  if(cfg.band){ [cfg.band[0],cfg.band[1]].forEach(b=>{
    const y=Y(b); g.strokeStyle='#484f58'; g.setLineDash([4,4]);
    g.beginPath(); g.moveTo(pad.l,y); g.lineTo(w-pad.r,y); g.stroke(); g.setLineDash([]); }); }
  // x labels
  g.fillStyle='#8b949e'; g.textAlign='center';
  const step=Math.max(1,Math.floor(N/6));
  for(let i=0;i<=N;i+=step){ g.fillText(cfg.dates[i].slice(0,7), X(i), h-8); }
  // series
  cfg.series.forEach(s=>{
    g.strokeStyle=s.color; g.lineWidth=s.w||1.8; g.beginPath();
    let started=false;
    s.pts.forEach(([i,v])=>{ const x=X(i),y=Y(v);
      if(!started){ g.moveTo(x,y); started=true; } else g.lineTo(x,y); });
    g.stroke();
  });
  return {X,Y,pad,iw,mn,mx,N};
}
let M3=null;
function render3(view){
  const cv=document.getElementById('c3');
  const f=D.series;
  const zs=D.standardized;
  let cfg;
  if(view==='norm') cfg={n:f.dates.length,dates:f.dates,
    series:[{pts:seriesXY(f.dates,zs.A_n||zs.PP_n),color:'#f0883e',w:2},{pts:seriesXY(f.dates,zs.B_n||zs.L_n),color:'#3fb950',w:2}],
    fmtY:v=>FMT(v,0)};
  else if(view==='spread') cfg={n:f.dates.length,dates:f.dates,
    series:[{pts:seriesXY(f.dates,zs.spread),color:'#58a6ff',w:1.8}],zeroLine:true,fmtY:v=>FMT(v,0)};
  else if(view==='ratio') cfg={n:f.dates.length,dates:f.dates,
    series:[{pts:seriesXY(f.dates,zs.ratio),color:'#58a6ff',w:1.8}],fmtY:v=>v.toFixed(3)};
  else if(view==='corr'){
    const rc=D.rolling_corr.w60;
    cfg={n:f.dates.length,dates:f.dates,band:[-rc.band_ret,rc.band_ret],zeroLine:true,
      series:[{pts:seriesXY(f.dates,rc.ret),color:'#58a6ff',w:2}],fmtY:v=>v.toFixed(2)};
  } else cfg={n:f.dates.length,dates:f.dates,band:[-1.5,1.5],zeroLine:true,
      series:[{pts:seriesXY(f.dates,D.z20),color:'#d29922',w:1.6}],fmtY:v=>v.toFixed(1)};
  M3=drawLine(cv,cfg);
  const info=document.getElementById('info3');
  if(view==='norm') info.textContent='以区间首个共同交易日=100 指数化。归一化只消除水平差异，不消除趋势，趋势造成的"平行"不等于联动。';
  else if(view==='spread') info.textContent='价差 = PP − LLDPE（元/吨）。正值表示 PP 相对更贵。产业习惯口径，但会随两者绝对价位整体漂移。';
  else if(view==='ratio') info.textContent='比价 = PP / LLDPE（无量纲）。对长期成本中枢下移更稳健，适合跨年比较。';
  else if(view==='corr') info.textContent='滚动 60 期收益率相关。跌破灰色虚线（95% 显著性带）意味着"同频"在统计上已不成立。';
  else info.textContent='价差相对其 20 期滚动均值的 z 分数。|z|≥1.5 进入背离，<0.5 回归；灰色虚线即阈值。';
}
document.querySelectorAll('.tab[data-v]').forEach(t=>{
  t.onclick=()=>{ document.querySelectorAll('.tab[data-v]').forEach(x=>x.classList.remove('on'));
    t.classList.add('on'); render3(t.dataset.v); };
});
let M4=null;
function render4(){
  const cv=document.getElementById('c4'), f=D.series;
  const a=D.rolling_corr.w20.ret, b=D.rolling_corr.w60.ret, c=D.rolling_corr.w120.ret;
  M4=drawLine(cv,{n:f.dates.length,dates:f.dates,band:[-D.rolling_corr.w20.band_ret,D.rolling_corr.w20.band_ret],zeroLine:true,
    series:[{pts:seriesXY(f.dates,a),color:'#8b949e',w:1.3},
            {pts:seriesXY(f.dates,b),color:'#58a6ff',w:2},
            {pts:seriesXY(f.dates,c),color:'#f0883e',w:2.2}],
    fmtY:v=>v.toFixed(2)});
}
function renderSegs(key){
  const segs=D.divergences[key]||[];
  const el=document.getElementById('segtable');
  if(!segs.length){ el.innerHTML='<div class="note">该口径下未识别出满足规则的背离段。</div>'; return; }
  let h='<table><thead><tr><th>开始</th><th>结束</th><th>持续(交易日)</th><th>方向</th><th>|z|峰值</th>'+
    '<th>PP变动%</th><th>LLDPE变动%</th><th>分化（百分点）</th></tr></thead><tbody>';
  segs.slice().reverse().forEach(s=>{
    h+=`<tr><td>${s.start}</td><td>${s.end}</td><td>${s.periods}</td>
      <td>${s.direction}</td><td>${s.peak_abs_z}</td>
      <td class="${s.a_change_pct>=0?'pos':'neg'}">${s.a_change_pct}</td>
      <td class="${s.b_change_pct>=0?'pos':'neg'}">${s.b_change_pct}</td>
      <td class="${s.divergence_pct_points>=0?'pos':'neg'}">${s.divergence_pct_points}</td></tr>`;
  });
  h+='</tbody></table>';
  el.innerHTML=h;
}
document.querySelectorAll('.tab[data-r]').forEach(t=>{
  t.onclick=()=>{ document.querySelectorAll('.tab[data-r]').forEach(x=>x.classList.remove('on'));
    t.classList.add('on'); renderSegs(t.dataset.r); };
});
render3('norm'); render4(); renderSegs('spread_60');
window.addEventListener('resize',()=>{ render3(document.querySelector('.tab[data-v].on').dataset.v); render4(); });
</script>
</body></html>
"""


def table(rows, head):
    h = "<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in head) + "</tr></thead><tbody>"
    for r in rows:
        h += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    h += "</tbody></table>"
    return h


def main():
    m = R["meta"]
    cb = R["corr_full"]
    st = R["stats"]
    # KPI
    kpi = [
        ("PP 区间涨跌", f'{st["a_chg_pct"]}%', "pos" if st["a_chg_pct"] >= 0 else "neg"),
        ("LLDPE 区间涨跌", f'{st["b_chg_pct"]}%', "pos" if st["b_chg_pct"] >= 0 else "neg"),
        ("收益率相关", f'{cb["ret_pearson"]:.3f}', "neu"),
        ("水平相关", f'{cb["level_pearson"]:.3f}', "neu"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="k">{k}</div><div class="v {c}">{v}</div></div>' for k, v, c in kpi)

    # 相关性表
    corr_rows = [
        ["价格水平 Pearson", f'{cb["level_pearson"]:.4f}', "受共同趋势影响，易高估联动"],
        ["价格水平 Spearman", f'{cb["level_spearman"]:.4f}', "同上，抗异常值"],
        ["对数收益率 Pearson", f'{cb["ret_pearson"]:.4f}', "推荐主口径"],
        ["对数收益率 Spearman", f'{cb["ret_spearman"]:.4f}', "抗异常值"],
    ]
    corr_html = table(corr_rows, ["口径", "系数", "解读"])

    yr_rows = [[y["year"], y["n"], f'{y["pp_ret"]}%', f'{y["l_ret"]}%',
                y["level_corr"], y["ret_corr"], FMT_INT(y["spread_avg"]), y["ratio_avg"]]
               for y in R["by_year"]]
    yr_html = table(yr_rows, ["年度", "交易日", "PP涨跌", "LLDPE涨跌", "水平相关", "收益相关", "价差均值", "比价均值"])

    for k in list(N.keys()):
        pass

    html = (HTML
            .replace("__WINDOW__", m["window"]["label"])
            .replace("__END__", m["end_date"])
            .replace("__REL__", N["relation_html"])
            .replace("__KPI__", kpi_html)
            .replace("__CORR__", corr_html)
            .replace("__YEAR__", yr_html)
            .replace("__FUND__", N["fund_html"])
            .replace("__CONCL__", N["concl_html"])
            .replace("__SRC__", N["src_html"])
            .replace("__LVL__", f'{cb["level_pearson"]:.3f}')
            .replace("__RET__", f'{cb["ret_pearson"]:.3f}')
            .replace("__DATA__", json.dumps({
                "meta": m, "series": R["series"], "standardized": R["standardized"],
                "rolling_corr": R["rolling_corr"], "z20": R["z20"],
                "divergences": R["divergences"], "corr_full": cb, "stats": st,
            }, ensure_ascii=False)))
    fp = os.path.join(B, "PP_LLDPE_背离诊断报告.html")
    open(fp, "w", encoding="utf-8").write(html)
    print("written", fp, len(html))


def FMT_INT(v):
    return f"{int(round(v)):,}"


if __name__ == "__main__":
    main()
