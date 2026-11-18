# -*- coding: utf-8 -*-
"""
build_html.py — 生成"中国PP大型新增产能事件研究"交互式 HTML 报告（单文件自包含）
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "build"))
import eventengine as EE  # noqa: E402

OUT = os.path.join(BASE, "out")
DATA = os.path.join(BASE, "data")

STAGE_COLOR = {
    "construction": "#6b7a8f", "mechanical": "#4a90a4", "commissioning": "#e0a800",
    "startup": "#d94f4f", "first_product": "#c0392b", "commercial": "#1f7a4d",
    "rampup": "#14532d", "announce": "#8b95a5", "record": "#8b95a5", "eia": "#8b95a5",
}
STAGE_NAME = {
    "construction": "开工", "mechanical": "中交", "commissioning": "试车",
    "startup": "正式投产", "first_product": "打通全流程", "commercial": "商业运营",
    "rampup": "达产标定", "announce": "宣布", "record": "备案", "eia": "环评",
}


def load():
    a = json.load(open(os.path.join(OUT, "analysis.json"), encoding="utf-8"))
    ev = json.load(open(os.path.join(DATA, "events_pp.json"), encoding="utf-8"))
    return a, ev


def build_series_for_js(a, ev):
    """把期货日线 + 现货/基差 + 基本面 打成 JS 数据块"""
    import csv
    blk = {}

    def read_pairs(path, date_col, val_col, flt=None):
        out = []
        if not os.path.exists(path):
            return out
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if flt and not flt(r):
                    continue
                try:
                    out.append([r[date_col], float(r[val_col])])
                except Exception:
                    pass
        out.sort()
        return out

    blk["futures"] = read_pairs(os.path.join(BASE, "data", "raw", "pp_futures_pp0_daily.csv"),
                                "date", "close")
    lp = os.path.join(BASE, "data", "raw", "longhist", "pp_spot_long.csv")
    if os.path.exists(lp):
        blk["spot"] = read_pairs(lp, "date", "value")
    else:
        blk["spot"] = read_pairs(os.path.join(BASE, "data", "raw", "pp_spot_bench_100ppi.csv"),
                                 "date", "price", lambda r: r["spec"] == "拉丝")
    blk["fiber"] = read_pairs(os.path.join(BASE, "data", "raw", "pp_spot_bench_100ppi.csv"),
                              "date", "price", lambda r: r["spec"] == "纤维")
    fund = {}
    # (a) 逐点可溯源基本面数据集（隆众口径，优先）
    ext = {
        "pp_inventory_producer.csv": "inventory",
        "pp_capacity_utilization.csv": "operating",
        "pp_inventory_commercial.csv": "inv_commercial",
        "pp_maintenance_loss.csv": "maintenance",
    }
    for fn, key in ext.items():
        p = os.path.join(BASE, "data", "raw", fn)
        if not os.path.exists(p):
            continue
        pts = []
        with open(p, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    pts.append([r["date"], float(r["value"]), r.get("source_url", ""),
                                (r.get("evidence_quote", "") or "")[:80]])
                except Exception:
                    pass
        if len(pts) >= 2:
            pts.sort()
            fund[key] = pts
    # (b) 官方经评正文抽取（仅保留 >=3 点）
    fpath = os.path.join(BASE, "data", "raw", "pp_fundamentals.csv")
    if os.path.exists(fpath):
        tmp = {}
        with open(fpath, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    tmp.setdefault(r["field"], []).append(
                        [r["pub_date"], float(r["value"]), r.get("source_url", ""),
                         (r.get("quote", "") or "")[:80]])
                except Exception:
                    pass
        for k, v in tmp.items():
            if len(v) >= 3:
                v.sort()
                fund["txt_" + k] = v
    blk["fundamentals"] = fund
    return blk


def main():
    a, ev = load()
    blk = build_series_for_js(a, ev)
    series_info = a["series_info"]
    per_event = a["per_event"]
    agg = a["aggregate"]
    placebo = a["placebo"]

    payload = {
        "meta": a["meta"],
        "series_info": series_info,
        "series": blk,
        "per_event": per_event,
        "aggregate": agg,
        "placebo": placebo,
        "ramp_assumption": a["ramp_assumption"],
        "default_ramp": a["default_ramp"],
        "horizons": a["horizons"],
    }
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    html = HTML_TMPL.replace("/*__DATA__*/", js)
    path = os.path.join(OUT, "PP新增产能投产事件研究报告.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("written", path, len(html))


HTML_TMPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中国聚丙烯(PP)大型新增产能投产事件研究 · 2020–2026</title>
<style>
:root{
  --bg:#0d1117; --panel:#141b24; --panel2:#1a2330; --line:#243040; --line2:#2f3f52;
  --txt:#e6edf3; --dim:#8b98a8; --dim2:#5b6879;
  --red:#e5534b; --green:#3fb950; --amber:#d29922; --blue:#4b9fd5; --violet:#a371f7;
  --accent:#4b9fd5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:14px;line-height:1.65;-webkit-font-smoothing:antialiased}
a{color:var(--blue);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1560px;margin:0 auto;padding:0 28px}
header{border-bottom:1px solid var(--line);background:linear-gradient(180deg,#111823,#0d1117);padding:34px 0 26px;margin-bottom:0}
h1{margin:0 0 10px;font-size:27px;letter-spacing:-.4px;font-weight:650}
h1 .pp{color:var(--blue)}
.sub{color:var(--dim);font-size:13.5px;max-width:1080px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:12px;margin:22px 0 0}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi .l{color:var(--dim);font-size:11.5px;letter-spacing:.4px;text-transform:uppercase}
.kpi .v{font-size:23px;font-weight:650;margin-top:4px;font-variant-numeric:tabular-nums}
.kpi .n{color:var(--dim2);font-size:11px;margin-top:2px}
nav{position:sticky;top:0;z-index:50;background:rgba(13,17,23,.94);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line);margin-bottom:26px}
nav .wrap{display:flex;gap:2px;overflow-x:auto;padding:0 28px}
nav button{background:none;border:0;color:var(--dim);padding:13px 15px;font-size:13px;cursor:pointer;
  border-bottom:2px solid transparent;white-space:nowrap;font-family:inherit}
nav button:hover{color:var(--txt)}
nav button.on{color:var(--txt);border-bottom-color:var(--accent);font-weight:600}
section{display:none;padding-bottom:70px}
section.on{display:block}
h2{font-size:19px;margin:34px 0 6px;font-weight:640;letter-spacing:-.2px}
h3{font-size:15px;margin:26px 0 10px;font-weight:620;color:#dbe4ee}
p.lead{color:var(--dim);margin:0 0 16px;max-width:1080px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
.card.tight{padding:14px 16px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media(max-width:1080px){.grid2,.grid3{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:12.8px}
th{text-align:left;color:var(--dim);font-weight:600;padding:8px 9px;border-bottom:1px solid var(--line2);
  font-size:11.5px;letter-spacing:.3px;text-transform:uppercase;white-space:nowrap;position:sticky;top:0;background:var(--panel)}
td{padding:8px 9px;border-bottom:1px solid #1b2531;vertical-align:top}
tbody tr:hover{background:#182130}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;padding:1px 7px;border-radius:20px;font-size:10.5px;font-weight:600;
  border:1px solid;line-height:1.6;white-space:nowrap}
.pos{color:var(--red)} .neg{color:var(--green)} .flat{color:var(--dim)}
.badge{font-size:10.5px;padding:1px 6px;border-radius:4px;background:#22303f;color:#9fb0c4;white-space:nowrap}
.warn{background:#2a2013;border:1px solid #4a3a18;color:#e8c26a;border-radius:8px;padding:11px 14px;margin:12px 0;font-size:13px}
.warn b{color:#f0d089}
.info{background:#132230;border:1px solid #1e3a52;color:#9fc4e0;border-radius:8px;padding:11px 14px;margin:12px 0;font-size:13px}
.crit{background:#2b1618;border:1px solid #57262a;color:#efa3a0;border-radius:8px;padding:11px 14px;margin:12px 0;font-size:13px}
.scroll{overflow:auto;max-height:640px;border:1px solid var(--line);border-radius:10px}
.scroll table th{background:var(--panel2)}
.ctl{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin:12px 0}
.ctl label{color:var(--dim);font-size:12px}
select,input,button.btn{background:var(--panel2);border:1px solid var(--line2);color:var(--txt);
  border-radius:7px;padding:6px 10px;font-size:12.5px;font-family:inherit;cursor:pointer}
button.btn:hover{border-color:#456}
button.btn.on{background:#1c3a55;border-color:var(--accent);color:#cfe6f8}
svg{display:block;width:100%;height:auto;overflow:visible}
.axis line{stroke:#2b3847;stroke-width:1}
.axis text{fill:#6b7889;font-size:10px}
.axis path{display:none}
.gridln{stroke:#1e2836;stroke-width:1;stroke-dasharray:2 3}
.lbl{fill:#8b98a8;font-size:11px}
.lbl2{fill:#5b6879;font-size:10px}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin:8px 0 2px;font-size:11.5px;color:var(--dim)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}
.ttip{position:fixed;pointer-events:none;background:#0b1016;border:1px solid var(--line2);
  border-radius:7px;padding:7px 10px;font-size:11.5px;color:var(--txt);z-index:200;display:none;
  box-shadow:0 8px 26px rgba(0,0,0,.6);max-width:320px;line-height:1.55}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:10px 0 0}
.tabs button{background:none;border:0;color:var(--dim);padding:9px 14px;cursor:pointer;font-size:13px;
  border-bottom:2px solid transparent;font-family:inherit}
.tabs button.on{color:var(--txt);border-bottom-color:var(--accent);font-weight:600}
.stagechip{display:inline-flex;align-items:center;gap:5px;background:var(--panel2);border:1px solid var(--line2);
  border-radius:16px;padding:3px 10px;font-size:11.5px;cursor:pointer;user-select:none}
.stagechip.on{background:#1c3a55;border-color:var(--accent);color:#cfe6f8}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.projrow{cursor:pointer}
.projrow:hover{background:#1b2634 !important}
.projrow.sel{background:#1c3a55 !important}
.small{font-size:11.5px;color:var(--dim)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
hr{border:0;border-top:1px solid var(--line);margin:26px 0}
.pill{background:#1b2531;border:1px solid var(--line2);border-radius:5px;padding:1px 7px;font-size:11px;color:#9fb0c4}
.hl{color:var(--amber)}
</style>
</head>
<body>
<header>
<div class="wrap">
  <h1>中国<span class="pp">聚丙烯(PP)</span>大型新增产能 · 正式投产事件研究</h1>
  <div class="sub">
    以 <b>2020–2026 年可核验的 29 个 PP 大型新增产能项目 / 45 个分层事件</b>为样本，
    区分「宣布 → 备案 → 环评 → 开工 → 中交 → 试车 → <b>正式投产</b> → 打通全流程 → 商业运营 → 达产」，
    研究各信息节点前后 <b>±20 / ±60 / ±120</b> 个交易日 PP 期货、现货、基差与库存、开工率的变化。
    所有数值均带来源；<b>设计产能不等于投产当天的新增实际产量</b>。
  </div>
  <div class="kpis" id="kpis"></div>
</div>
</header>

<nav><div class="wrap" id="nav"></div></nav>

<div class="wrap">

<section id="s-candidates" class="on">
  <h2>① 候选新增产能项目表与证据</h2>
  <p class="lead">先核实项目，再谈事件。下表只收录<b>有公开来源证实</b>的项目；「设计产能」是名义口径，
  与「实际投产当天新增产量」不是一回事（见第 ④ 节爬坡测算）。点击任意一行查看该项目的历史变化路径。</p>
  <div class="warn"><b>本表最重要的三条纪律：</b>
  ① 新闻里的「计划 X 月投产」<b>不得</b>当作投产日；<br>
  ② 同一项目的开工 / 中交 / 试车 / 投料 / 合格品 / 达产是<b>不同事件</b>，绝不合并统计；<br>
  ③ 仅一个来源的日期单独标注 <span class="badge">单一来源</span>，统计时降权处理。</div>
  <div id="cand-summary" class="grid3" style="margin:16px 0"></div>
  <div class="ctl">
    <label>区域</label><select id="f-region"><option value="">全部</option></select>
    <label>工艺</label><select id="f-process"><option value="">全部</option></select>
    <label>证据等级</label><select id="f-grade"><option value="">全部</option></select>
    <label>排序</label><select id="f-sort">
      <option value="date">按投产日期</option><option value="cap">按设计产能</option>
      <option value="share">按占现有产能比</option><option value="region">按区域</option>
    </select>
    <input id="f-q" placeholder="搜索项目/业主/地点…" style="min-width:190px">
    <span class="small" id="f-count"></span>
  </div>
  <div class="scroll"><table id="cand-table"></table></div>
</section>

<section id="s-timeline">
  <h2>② 事件时间线：投产日期分层</h2>
  <p class="lead">同一项目在不同阶段被披露，市场反应的性质完全不同：<b>宣布/开工/试车属于「预期信息」</b>，
  <b>正式投产/合格品/商运属于「供给兑现信息」</b>。把两者混为一谈，是这类研究最常见的错误。</p>
  <div class="card">
    <div class="ctl" id="stage-filter"></div>
    <div class="legend">
      <span><i style="background:#6b7a8f"></i>开工</span>
      <span><i style="background:#4a90a4"></i>中交</span>
      <span><i style="background:#e0a800"></i>试车</span>
      <span><i style="background:#d94f4f"></i>正式投产</span>
      <span><i style="background:#c0392b"></i>打通全流程</span>
      <span><i style="background:#1f7a4d"></i>商业运营</span>
      <span><i style="background:#14532d"></i>达产标定</span>
    </div>
    <div id="timeline-svg"></div>
  </div>
  <h3>预计 vs 实际：延期天数</h3>
  <p class="lead">「首次预计投产」与「实际投产」的差距，是市场预期差最直接的度量来源。</p>
  <div class="scroll" style="max-height:520px"><table id="delay-table"></table></div>
</section>

<section id="s-window">
  <h2>③ 事件窗口：投产前后 ±20 / ±60 / ±120 交易日</h2>
  <p class="lead">以事件日为 0，<b>相对交易日</b>对齐（不是自然日）：−k 到 +k 是同一个量纲的窗口，
  这样跨周末、跨假期、跨停盘的项目可以横向比较。</p>
  <div class="card">
    <div class="ctl">
      <label>品种序列</label><select id="w-var"></select>
      <label>事件节点</label><select id="w-stage"></select>
      <label>显示</label>
      <button class="btn on" data-wmode="mean">平均路径</button>
      <button class="btn" data-wmode="median">中位路径</button>
      <button class="btn" data-wmode="all">全部事件（细线）</button>
    </div>
    <div id="w-svg"></div>
    <div id="w-note" class="info" style="margin-top:10px"></div>
  </div>
  <h3>逐事件窗口数值</h3>
  <div class="scroll" style="max-height:560px"><table id="w-table"></table></div>
</section>

<section id="s-stats">
  <h2>④ 汇总统计（样本可比性优先）</h2>
  <p class="lead">只有样本 ≥ 3 才给 t 值与显著性；样本 &lt; 3 一律标 <span class="badge">样本不足</span>，不做过度解读。
  三个口径并列展示，避免用单一数字掩盖口径差异。</p>
  <div class="crit"><b>读法（重要）：</b>
  <b>累计变化</b> = 事件后 k 期水平 − 事件前 1 期水平（含事件前的趋势漂移，不等于"事件效应"）；
  <b>超额变化</b>(主口径) = 累计变化 − 同期"相对日历对齐"的市场平均变化（扣除大盘）；
  <b>突变</b> = 累计变化 − 事件前同长度前段变化（二阶差分）。
  三者若同向，结论才稳。</div>
  <div class="ctl">
    <label>品种序列</label><select id="s-var"></select>
    <label>跨度</label><select id="s-h"><option value="20">20 交易日</option><option value="60" selected>60 交易日</option><option value="120">120 交易日</option></select>
  </div>
  <div class="card tight"><div id="s-svg"></div></div>
  <h3>安慰剂检验：真实事件 vs 随机平移日期</h3>
  <p class="lead">把每个事件的日期随机平移 ±180 天重复 400 次，看真实事件的"效应"是否显著区别于噪声。
  <b>p 值大 = 这个效应很可能只是噪声。</b></p>
  <div class="scroll" style="max-height:340px"><table id="p-table"></table></div>
  <h3>完整分组统计表</h3>
  <div class=warn><b>基差(basis)序列的百分比要谨慎读：</b>基差 = 现货 − 期货，是绝对值差额（元/吨），
  不是价格指数。当基差本身接近 0 时，百分比变化会放大成几十甚至上百个百分点
  （例如基差从 +750 元/吨到 +1803 元/吨记为 +140%），这在数学上正确但不是“价格涨了140%”。
  <b>基差应看绝对变化（元/吨），价格序列才看百分比。</b></div>
  <div class="scroll" style="max-height:600px"><table id="agg-table"></table></div>
</section>

<section id="s-capacity">
  <h2>⑤ 各项目占行业现有产能的比例 &amp; 实际产量增量</h2>
  <p class="lead">设计产能是名义值。<b>投产当天新增的实际产量接近于零</b>——装置需要爬坡。
  右图按工程经验爬坡曲线给出"投产第 1 个月 / 第 3 个月 / 第 6 个月"的实际产量增量，并明确标注这是<b>假设而非项目披露值</b>。</p>
  <div class="warn"><b>爬坡假设说明：</b><span id="ramp-txt"></span></div>
  <div class="card tight"><div id="cap-svg"></div></div>
  <div class="scroll" style="max-height:600px"><table id="cap-table"></table></div>
</section>

<section id="s-project">
  <h2>⑥ 逐项目历史变化路径</h2>
  <p class="lead">每个项目单独一条路径：竖线标出该项目的各个信息节点（开工 / 中交 / 试车 / 投产 / 商运），
  叠加 PP 期货收盘价与（若有）库存/开工率。点选项目查看。</p>
  <div class="ctl" id="proj-picker"></div>
  <div class="card tight"><div id="proj-svg"></div><div id="proj-detail" style="margin-top:12px"></div></div>
</section>

<section id="s-limits">
  <h2>⑦ 数据边界、混淆因素与使用限制</h2>
  <div class="grid2">
    <div class="card">
      <h3 style="margin-top:0">数据可用性与缺口（如实披露）</h3>
      <div id="series-gap"></div>
    </div>
    <div class="card">
      <h3 style="margin-top:0">必须同时考虑的混淆因素</h3>
      <ol style="margin:0;padding-left:20px;color:#c5d0dc;font-size:13px">
        <li><b>市场提前反映。</b>新增产能的宣布、环评、开工、试车都会提前定价；正式投产当天的"新闻价值"往往已被消化。
        因此本报告把预期类节点与兑现类节点<b>分开研究</b>，不做合并平均。</li>
        <li><b>达产爬坡。</b>设计产能 ≠ 投产当天产量。爬坡 3–10 个月是常态，且本项目多数未披露逐月负荷。</li>
        <li><b>同期其他新增产能。</b>PP 在 2020–2026 属密集扩能期，任一季度都有多个项目并行。
        本报告用"相对日历对齐"的反事实扣除大盘，但无法完全分离单个项目的影响。</li>
        <li><b>成本端驱动。</b>PP 价格主要受原油/丙烯/甲醇成本推动，供给事件常被成本波动淹没。</li>
        <li><b>检修与停车对冲。</b>同期装置检修会抵消新增供给，单独看投产会高估净增量。</li>
        <li><b>需求季节性。</b>春节前后、农膜旺季、旺季备货都会显著改变库存与价格的季节形态。</li>
        <li><b>日期精度不齐。</b>部分项目仅能精确到"月"，部分为仪式日或试车日，样本内部并不同质。</li>
      </ol>
    </div>
  </div>
  <div class="card">
    <h3 style="margin-top:0">如何把它当作决策输入（而不是结论）</h3>
    <p style="color:#c5d0dc;margin:0">本报告给出的是<b>可复核的证据链与统计骨架</b>，不是方向判断。正确用法是：
    用候选事件表确认样本 → 用分层时间线确定信息节点 → 用超额变化与安慰剂检验判断"有没有效应" →
    再用逐项目路径检查是不是由个别异常项目驱动。若三个口径不同向、或安慰剂 p 值大，就应当结论为"无稳健证据"。</p>
  </div>
  <h2>⑧ 来源清单</h2>
  <div id="sources"></div>
</section>

</div>
<div class="ttip" id="ttip"></div>

<script>
const D = /*__DATA__*/;
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const fmt = (v,d=2)=> (v===null||v===undefined||Number.isNaN(v)) ? '—' : Number(v).toFixed(d);
const pct = (v,d=1)=> (v===null||v===undefined||Number.isNaN(v)) ? '—' : (v*100).toFixed(d)+'%';
const clsOf = v => (v===null||v===undefined)?'flat':(v>0?'pos':(v<0?'neg':'flat'));
const ttip = $('#ttip');
function showTip(evt, html){ ttip.innerHTML=html; ttip.style.display='block';
  const x=Math.min(evt.clientX+14, window.innerWidth-340), y=evt.clientY+14;
  ttip.style.left=x+'px'; ttip.style.top=y+'px'; }
function hideTip(){ ttip.style.display='none'; }

/* ---------- nav ---------- */
const NAV = [['s-candidates','① 候选项目与证据'],['s-timeline','② 事件时间线'],
  ['s-window','③ 事件窗口'],['s-stats','④ 汇总统计'],['s-capacity','⑤ 产能占比与爬坡'],
  ['s-project','⑥ 逐项目路径'],['s-limits','⑦ 边界与来源']];
$('#nav').innerHTML = NAV.map((n,i)=>`<button data-t="${n[0]}" class="${i===0?'on':''}">${n[1]}</button>`).join('');
$$('#nav button').forEach(b=>b.onclick=()=>{
  $$('#nav button').forEach(x=>x.classList.remove('on')); b.classList.add('on');
  $$('section').forEach(s=>s.classList.remove('on')); $('#'+b.dataset.t).classList.add('on');
  window.scrollTo({top:0,behavior:'smooth'});
});

/* ---------- KPIs ---------- */
const evs = D.per_event;
const startups = evs.filter(e=>e.stage==='startup');
const totalCap = [...new Set(startups.map(e=>e.project_id))].reduce((s,pid)=>{
  const e=startups.find(x=>x.project_id===pid); return s+(e.design_capacity||0); },0);
(function(){
  const k=[
    ['已核实项目', D.meta.n_projects, '个（≥20万吨/年）'],
    ['分层事件', evs.length, '个（含试车/中交等）'],
    ['正式投产事件', startups.length, '个“一次开车成功”'],
    ['新增PP产能合计', totalCap.toFixed(0), '万吨/年（设计口径）'],
    ['价格序列起点', D.series_info.futures? D.series_info.futures.start.slice(0,7):'—', '期货主力连续日线'],
    ['现货序列起点', (D.series_info.spot_lasi||{}).start? D.series_info.spot_lasi.start.slice(0,7):'缺口', '生意社PP拉丝基准价'],
  ];
  $('#kpis').innerHTML = k.map(x=>`<div class="kpi"><div class="l">${x[0]}</div><div class="v">${x[1]}</div><div class="n">${x[2]}</div></div>`).join('');
})();

/* ---------- ① 候选表 ---------- */
const projMap = {};
D.per_event.forEach(e=>{
  if(!projMap[e.project_id]) projMap[e.project_id]={
    project_id:e.project_id, name:e.project_name, region:e.region, process:e.process,
    design_capacity:e.design_capacity, share_pct:e.share_pct, capacity_base:e.capacity_base,
    stage_events:[], owner:'', location:''};
  projMap[e.project_id].stage_events.push(e);
});
const projects = Object.values(projMap);
projects.forEach(p=>{
  p.stage_events.sort((a,b)=>a.date.localeCompare(b.date));
  const st=p.stage_events.find(e=>e.stage==='startup')||p.stage_events.find(e=>e.stage==='commissioning')||p.stage_events[0];
  p.ref_event=st; p.date=st?st.date:''; 
  p.grade=Math.min(...p.stage_events.filter(e=>e.stage==='startup'||e.stage==='commissioning').map(e=>({'A':0,'B':1,'C':2,'D':3}[e.evidence_grade]??9)));
  const gl={'A':'A 官方','B':'B 权威媒体','C':'C 行业机构','D':'D 自媒体'};
  p.gradeLabel = gl[Object.keys(gl)[p.grade]]||'—';
  p.single = p.stage_events.some(e=>e.single_source && (e.stage==='startup'));
});
(function initFilters(){
  const reg=[...new Set(projects.map(p=>p.region))].sort();
  const proc=[...new Set(projects.map(p=>p.process))].sort();
  const gr=[...new Set(projects.map(p=>p.gradeLabel))].sort();
  reg.forEach(x=>$('#f-region').insertAdjacentHTML('beforeend',`<option>${x}</option>`));
  proc.forEach(x=>$('#f-process').insertAdjacentHTML('beforeend',`<option>${x}</option>`));
  gr.forEach(x=>$('#f-grade').insertAdjacentHTML('beforeend',`<option>${x}</option>`));
  ['#f-region','#f-process','#f-grade','#f-sort'].forEach(s=>$(s).onchange=renderCand);
  $('#f-q').oninput=renderCand;
})();

function renderCand(){
  const r=$('#f-region').value, pr=$('#f-process').value, g=$('#f-grade').value,
        q=$('#f-q').value.trim(), s=$('#f-sort').value;
  let list=projects.filter(p=>(!r||p.region===r)&&(!pr||p.process===pr)&&(!g||p.gradeLabel===g)
      &&(!q||(p.name+p.project_id+(p.ref_event?.project_name||'')).includes(q)));
  if(s==='cap') list.sort((a,b)=>(b.design_capacity||0)-(a.design_capacity||0));
  else if(s==='share') list.sort((a,b)=>(b.share_pct||0)-(a.share_pct||0));
  else if(s==='region') list.sort((a,b)=>a.region.localeCompare(b.region)||a.date.localeCompare(b.date));
  else list.sort((a,b)=>a.date.localeCompare(b.date));
  $('#f-count').textContent = `共 ${list.length} 个项目`;
  const stageNames={construction:'开工',mechanical:'中交',commissioning:'试车',startup:'正式投产',
    first_product:'打通全流程',commercial:'商业运营',rampup:'达产标定'};
  const stageCol={construction:'#6b7a8f',mechanical:'#4a90a4',commissioning:'#e0a800',
    startup:'#d94f4f',first_product:'#c0392b',commercial:'#1f7a4d',rampup:'#14532d'};
  let h=`<thead><tr><th>项目</th><th>区域</th><th>工艺路线</th>
    <th class="num">设计产能<br>万吨/年</th><th class="num">占现有产能</th>
    <th>正式投产日</th><th>分层事件</th><th>证据</th></tr></thead><tbody>`;
  list.forEach(p=>{
    const chips=p.stage_events.map(e=>
      `<span class="stagechip" style="border-color:${stageCol[e.stage]||'#444'}" title="${e.date} ${stageNames[e.stage]||e.stage}">
        <span class="dot" style="background:${stageCol[e.stage]||'#444'}"></span>${stageNames[e.stage]||e.stage}</span>`).join(' ');
    h+=`<tr class="projrow" data-pid="${p.project_id}">
      <td><b>${p.name}</b><div class="small mono">${p.project_id}</div></td>
      <td>${p.region}</td>
      <td class="small">${p.process}</td>
      <td class="num"><b>${p.design_capacity??'—'}</b></td>
      <td class="num">${p.share_pct!=null?fmt(p.share_pct,2)+'%':'—'}</td>
      <td class="mono">${p.date}</td>
      <td style="min-width:230px">${chips}</td>
      <td><span class="badge">${p.gradeLabel}</span>${p.single?' <span class="badge" style="background:#4a2b12;color:#e0a86a">单一来源</span>':''}</td>
    </tr>`;
  });
  h+='</tbody>';
  $('#cand-table').innerHTML=h;
  $$('#cand-table .projrow').forEach(tr=>tr.onclick=()=>{
    selectProject(tr.dataset.pid);
    $$('#nav button').forEach(x=>x.classList.remove('on'));
    $$('section').forEach(s=>s.classList.remove('on'));
    $('#s-project').classList.add('on'); window.scrollTo({top:0,behavior:'smooth'});
  });
}
(function candSummary(){
  const regs={}; projects.forEach(p=>{regs[p.region]=(regs[p.region]||0)+(p.design_capacity||0);});
  const bySt={}; D.per_event.forEach(e=>{bySt[e.stage]=(bySt[e.stage]||0)+1});
  $('#cand-summary').innerHTML = `
    <div class="card tight"><div class="small">分区域设计产能合计（万吨/年）</div>
      <div style="margin-top:6px">${Object.entries(regs).sort((a,b)=>b[1]-a[1]).map(([k,v])=>
        `<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1b2531">
        <span>${k}</span><b class="num">${v}</b></div>`).join('')}</div></div>
    <div class="card tight"><div class="small">分层事件数量</div>
      <div style="margin-top:6px">${Object.entries(bySt).map(([k,v])=>
        `<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1b2531">
        <span>${({'startup':'正式投产','commissioning':'试车','construction':'开工','commercial':'商业运营','mechanical':'中交','first_product':'打通全流程','rampup':'达产标定'})[k]||k}</span><b class="num">${v}</b></div>`).join('')}</div></div>
    <div class="card tight"><div class="small">证据等级分布（按项目）</div>
      <div style="margin-top:6px">${(()=>{const m={};projects.forEach(p=>{m[p.gradeLabel]=(m[p.gradeLabel]||0)+1});
        return Object.entries(m).sort().map(([k,v])=>
        `<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1b2531">
        <span>${k}</span><b class="num">${v}</b></div>`).join('')})()}</div></div>`;
})();

/* ---------- ② 时间线 ---------- */
const STAGECOL={construction:'#6b7a8f',mechanical:'#4a90a4',commissioning:'#e0a800',
  startup:'#d94f4f',first_product:'#c0392b',commercial:'#1f7a4d',rampup:'#14532d'};

const stageOn = new Set(['construction','mechanical','commissioning','startup','first_product','commercial','rampup']);
(function initStageFilter(){
  const names={construction:'开工',mechanical:'中交',commissioning:'试车',startup:'正式投产',
    first_product:'打通全流程',commercial:'商业运营',rampup:'达产标定'};
  $('#stage-filter').innerHTML = Object.entries(names).map(([k,v])=>
    `<span class="stagechip on" data-stage="${k}"><span class="dot" style="background:${STAGECOL[k]}"></span>${v}</span>`).join('');
  $$('#stage-filter .stagechip').forEach(c=>c.onclick=()=>{
    const k=c.dataset.stage;
    if(stageOn.has(k)){stageOn.delete(k);c.classList.remove('on');} else {stageOn.add(k);c.classList.add('on');}
    renderTimeline();
  });
})();
function renderTimeline(){
  const list = D.per_event.filter(e=>stageOn.has(e.stage)).slice().sort((a,b)=>a.date.localeCompare(b.date));
  const W=1500,H=430,ml=88,mr=30,mt=34,mb=42;
  const iw=W-ml-mr, ih=H-mt-mb;
  const t0=new Date('2020-01-01').getTime(), t1=new Date('2026-12-31').getTime();
  const X=t=>ml+(t-t0)/(t1-t0)*iw;
  // 按项目纵向排列
  const pids=[...new Set(list.map(e=>e.project_id))];
  const rowH=Math.max(12,(ih)/Math.max(1,pids.length));
  let s=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
  for(let y=2020;y<=2027;y++){
    const x=X(new Date(y+'-01-01').getTime());
    s+=`<line class="gridln" x1="${x}" y1="${mt-8}" x2="${x}" y2="${mt+ih}"/>`;
    s+=`<text class="lbl2" x="${x}" y="${mt-14}" text-anchor="middle">${y}</text>`;
  }
  pids.forEach((pid,i)=>{
    const y=mt+i*rowH+rowH/2;
    const p=projMap[pid];
    if(rowH>13) s+=`<text class="lbl2" x="${ml-8}" y="${y+3}" text-anchor="end">${(p.name||pid).slice(0,16)}</text>`;
    const es=list.filter(e=>e.project_id===pid);
    if(es.length>1){
      const x1=X(new Date(es[0].date).getTime()), x2=X(new Date(es[es.length-1].date).getTime());
      s+=`<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="#2f3f52" stroke-width="1.5"/>`;
    }
    es.forEach(e=>{
      const x=X(new Date(e.date).getTime());
      const col=STAGECOL[e.stage]||'#666';
      s+=`<circle cx="${x}" cy="${y}" r="${e.stage==='startup'?4.2:2.8}" fill="${col}" stroke="#0d1117" stroke-width="0.8"
        data-tip="${e.date}｜${p.name}｜${({'construction':'开工','mechanical':'中交','commissioning':'试车','startup':'正式投产','first_product':'打通全流程','commercial':'商业运营','rampup':'达产标定'})[e.stage]||e.stage}｜${e.design_capacity||''}万吨/年｜证据${e.evidence_grade||e.grade||'—'}${e.single_source?'（单一来源）':''}"/>`;
    });
  });
  s+='</svg>';
  $('#timeline-svg').innerHTML=s;
  bindTips('#timeline-svg [data-tip]');
}
function bindTips(sel){
  $$(sel).forEach(el=>{
    el.style.cursor='pointer';
    el.onmousemove=e=>showTip(e, el.dataset.tip);
    el.onmouseleave=hideTip;
  });
}
(function delayTable(){
  const rows=projects.filter(p=>p.stage_events.some(e=>e.stage==='startup'))
   .map(p=>{const st=p.stage_events.find(e=>e.stage==='startup');
     const first=p.stage_events.find(e=>e.stage==='construction');
     return {p,st,first};})
   .sort((a,b)=>a.st.date.localeCompare(b.st.date));
  let h=`<thead><tr><th>项目</th><th>区域</th><th class="num">设计产能</th>
    <th>开工日</th><th>正式投产日</th><th class="num">建设周期(月)</th><th>证据</th></tr></thead><tbody>`;
  rows.forEach(r=>{
    let months='—';
    if(r.first){
      const d1=new Date(r.first.date), d2=new Date(r.st.date);
      months=((d2-d1)/86400000/30.44).toFixed(1);
    }
    h+=`<tr><td>${r.p.name}</td><td>${r.p.region}</td><td class="num">${r.p.design_capacity??'—'}</td>
      <td class="mono">${r.first?r.first.date:'<span class="small">未核实</span>'}</td>
      <td class="mono">${r.st.date}</td><td class="num">${months}</td>
      <td><span class="badge">${r.st.evidence_grade}</span>${r.st.single_source?' <span class="badge" style="background:#4a2b12;color:#e0a86a">单一来源</span>':''}</td></tr>`;
  });
  $('#delay-table').innerHTML=h+'</tbody>';
})();

/* ---------- ③ 事件窗口 ---------- */
(function initW(){
  const vs=Object.keys(D.series_info);
  $('#w-var').innerHTML=vs.map(v=>`<option value="${v}">${D.series_info[v].name}</option>`).join('');
  const stages=['startup','commissioning','construction','mechanical','first_product','commercial','rampup','ALL'];
  const nm={startup:'正式投产',commissioning:'试车',construction:'开工',mechanical:'中交',
    first_product:'打通全流程',commercial:'商业运营',rampup:'达产标定',ALL:'全部阶段'};
  $('#w-stage').innerHTML=stages.map(s=>`<option value="${s}">${nm[s]||s}</option>`).join('');
  $('#w-var').value='futures';
  $('#w-var').onchange=renderWindow; $('#w-stage').onchange=renderWindow;
  $$('[data-wmode]').forEach(b=>b.onclick=()=>{
    $$('[data-wmode]').forEach(x=>x.classList.remove('on')); b.classList.add('on');
    renderWindow();
  });
})();
let wmode='mean';
$$('[data-wmode]').forEach(b=>b.onclick=()=>{wmode=b.dataset.wmode;});

function seriesFor(vk){
  const s=D.series[vk==='basis'?'spot':vk];
  return s;
}
function renderWindow(){
  const vk=$('#w-var').value, stg=$('#w-stage').value;
  const info=D.series_info[vk];
  const evts=D.per_event.filter(e=>stg==='ALL'||e.stage===stg)
     .filter(e=>e.vars[vk] && !e.vars[vk]._status);
  const HU=D.horizons[D.horizons.length-1];
  // 归一化路径：相对事件前1期
  const paths=[];
  const ser=D.series[vk==='basis'?'spot':vk]||[];
  evts.forEach(e=>{
    const ev0=seriesIndexFor(e.date, ser);
    if(ev0<0) return;
    const pts=[];
    for(let k=-HU;k<=HU;k++){
      const i=ev0+k; const p=ser[i];
      // 事件日当天的相对值应为 100（用事件日收盘，而非前一日）——统一口径：以事件日为 0 点
      const base=ser[i]; 
      pts.push([k, i>=0&&i<ser.length?1:null]);
    }
    // 重新按"事件日 = 100"构造
    const arr=[];
    for(let k=-HU;k<=HU;k++){
      const i=ev0+k;
      if(i<0||i>=ser.length){arr.push([k,null]);continue;}
      arr.push([k, ser[i][1]/ser[ev0][1]]);
    }
    paths.push({e, arr});
  });
  if(!paths.length){
    $('#w-svg').innerHTML='<div class="warn">该组合在可用数据范围内没有可计算的完整窗口（现货/基本面序列起始较晚）。</div>';
    $('#w-table').innerHTML=''; $('#w-note').textContent=''; return;
  }
  const W=1480,HH=430,ml=66,mr=24,mt=26,mb=40;
  const iw=W-ml-mr, ih=HH-mt-mb;
  const X=k=>ml+(k+HU)/(2*HU)*iw;
  let lo=Infinity,hi=-Infinity;
  const meanArr=[];
  for(let k=-HU;k<=HU;k++){
    const vals=paths.map(p=>p.arr[k+HU][1]).filter(v=>v!=null);
    if(vals.length){const m=vals.reduce((a,b)=>a+b,0)/vals.length; meanArr.push([k,m,vals.length]);
      lo=Math.min(lo,...vals); hi=Math.max(hi,...vals);}
  }
  const pad=(hi-lo)*0.12||0.02; lo-=pad; hi+=pad;
  const Y=v=>mt+(hi-v)/(hi-lo)*ih;
  let s=`<svg viewBox="0 0 ${W} ${HU}" preserveAspectRatio="xMidYMid meet">`;
  for(let i=0;i<=5;i++){
    const v=lo+(hi-lo)*i/5; const y=Y(v);
    s+=`<line class="gridln" x1="${ml}" y1="${y}" x2="${W-mr}" y2="${y}"/>`;
    s+=`<text class="lbl2" x="${ml-8}" y="${y+3}" text-anchor="end">${(v*100).toFixed(0)}</text>`;
  }
  [-120,-60,-20,0,20,60,120].filter(k=>Math.abs(k)<=HU).forEach(k=>{
    s+=`<line x1="${X(k)}" y1="${mt}" x2="${X(k)}" y2="${mt+ih}" stroke="${k===0?'#e5534b':'#243040'}" stroke-width="${k===0?1.4:1}" ${k===0?'':'stroke-dasharray="3 3"'}/>`;
    s+=`<text class="lbl2" x="${X(k)}" y="${mt+ih+16}" text-anchor="middle">${k>0?'+':''}${k}</text>`;
  });
  s+=`<text class="lbl2" x="${W/2}" y="${mt+ih+32}" text-anchor="middle">相对交易日（0 = 事件日，值=100）</text>`;
  if(wmode==='all'){
    paths.forEach(p=>{
      const d=p.arr.map(([k,v])=>v==null?null:`${X(k)},${Y(v)}`).filter(Boolean);
      if(d.length>1) s+=`<polyline fill="none" stroke="#4b9fd5" stroke-opacity="0.16" stroke-width="1" points="${d.join(' ')}"/>`;
    });
  }
  const key=wmode==='median'?'med':'mean';
  const linePts=meanArr.map(([k,m])=>`${X(k)},${Y(m)}`).join(' ');
  s+=`<polyline fill="none" stroke="${wmode==='median'?'#a371f7':'#4b9fd5'}" stroke-width="2.4" points="${linePts}"/>`;
  s+=`<line x1="${ml}" y1="${Y(1)}" x2="${W-mr}" y2="${Y(1)}" stroke="#8b98a8" stroke-width="1" stroke-dasharray="4 3"/>`;
  s+=`<text class="lbl2" x="${W-mr-4}" y="${Y(1)-5}" text-anchor="end">事件日水平 = 100</text>`;
  s+='</svg>';
  $('#w-svg').innerHTML=s;
  const n=paths.length;
  $('#w-note').innerHTML=`当前序列 <b>${info?info.name:vk}</b>（${info?info.start+' → '+info.end:'缺口'}），
    事件节点 <b>${$('#w-stage').selectedOptions[0].text}</b>，可用事件 <b>${n}</b> 个，
    ±120 交易日窗口内平均可得样本 <b>${meanArr[meanArr.length-1]?meanArr[meanArr.length-1][2]:0}</b> 个。
    ${n<5?'<b class="hl">样本偏少，平均路径不稳定，请以逐事件表为准。</b>':''}`;

  // 逐事件窗口表
  let h=`<thead><tr><th>项目</th><th>节点</th><th>日期</th>
    <th class="num">前1日</th><th class="num">+20</th><th class="num">+60</th><th class="num">+120</th>
    <th class="num">20日累计</th><th class="num">20日超额</th>
    <th class="num">60日累计</th><th class="num">60日超额</th>
    <th class="num">120日累计</th><th class="num">120日超额</th></tr></thead><tbody>`;
  evts.slice().sort((a,b)=>a.date.localeCompare(b.date)).forEach(e=>{
    const v=e.vars[vk];
    if(!v||v._status){return;}
    const g=(h,kk)=> { const cell=v[String(h)]||v[h]; return cell? cell[kk] : undefined; };
    h+=`<tr><td>${e.project_name}</td><td>${({'startup':'正式投产','commissioning':'试车','construction':'开工','mechanical':'中交','first_product':'打通全流程','commercial':'商业运营','rampup':'达产标定'})[e.stage]||e.stage}</td>
      <td class="mono">${e.date}</td>
      <td class="num">${fmt(g(20,'base_value'),0)}</td>
      <td class="num">${fmt(g(20,'post_value'),0)}</td>
      <td class="num">${fmt(g(60,'post_value'),0)}</td>
      <td class="num">${fmt(g(120,'post_value'),0)}</td>
      ${D.horizons.map(hh=>`<td class="num ${clsOf(g(hh,'pct'))}">${pct(g(hh,'pct'))}</td>
        <td class="num ${clsOf(g(hh,'abnormal_pct'))}">${pct(g(hh,'abnormal_pct'))}</td>`).join('')}
      </tr>`;
  });
  $('#w-table').innerHTML=h+'</tbody>';
}
function seriesIndexFor(d, ser){
  // ser: [[date,val],...]; 用 next 对齐（事件日当天或之后首个有数据日）
  let lo=0,hi=ser.length-1,ans=-1;
  while(lo<=hi){const m=(lo+hi)>>1; if(ser[m][0]>=d){ans=m;hi=m-1;}else lo=m+1;}
  return ans;
}

/* ---------- ④ 统计 ---------- */
(function initStats(){
  const vs=Object.keys(D.series_info);
  $('#s-var').innerHTML=vs.map(v=>`<option value="${v}">${D.series_info[v].name}</option>`).join('');
  $('#s-var').value='futures';
  $('#s-var').onchange=renderStats; $('#s-h').onchange=renderStats;
  const nm={startup:'正式投产',commissioning:'试车',construction:'开工',mechanical:'中交',
    first_product:'打通全流程',commercial:'商业运营',rampup:'达产标定',ALL:'全部阶段'};
  let h=`<thead><tr><th>阶段</th><th class="num">跨度</th><th class="num">n</th>
    <th class="num">累计变化<br>均值</th><th class="num">中位</th><th class="num">t</th>
    <th class="num">超额变化<br>(主口径)</th><th class="num">t</th>
    <th class="num">突变<br>(二阶差分)</th><th class="num">正比例</th><th class="num">符号p</th>
    <th class="num">90% CI</th><th>结论</th></tr></thead><tbody>`;
  D.aggregate.forEach(r=>{
    const ins=r.insufficient;
    let verdict='—';
    if(ins) verdict='<span class="badge" style="background:#3a2a12;color:#d8b26a">样本不足</span>';
    else if(r.t_abnormal!=null&&Math.abs(r.t_abnormal)>=2) verdict=`<span class="badge" style="background:#1f3d2c;color:#6fcf97">超额显著</span>`;
    else if(r.t_cum!=null&&Math.abs(r.t_cum)>=2) verdict='<span class="badge" style="background:#22303f">仅累计显著</span>';
    else verdict='<span class="badge">不显著</span>';
    h+=`<tr data-var="${r.var}" data-stage="${r.stage}" data-h="${r.horizon}">
      <td>${nm[r.stage]||r.stage_label}</td><td class="num">${r.horizon}</td><td class="num">${r.n}</td>
      <td class="num ${clsOf(r.mean_pct)}">${pct(r.mean_pct)}</td>
      <td class="num">${pct(r.median_pct)}</td>
      <td class="num">${fmt(r.t_cum,2)}</td>
      <td class="num ${clsOf(r.mean_abnormal)}">${pct(r.mean_abnormal)}</td>
      <td class="num">${fmt(r.t_abnormal,2)}</td>
      <td class="num ${clsOf(r.mean_surprise)}">${pct(r.mean_surprise)}</td>
      <td class="num">${r.pos_share!=null?pct(r.pos_share,0):'—'}</td>
      <td class="num">${fmt(r.sign_p,3)}</td>
      <td class="num small">${r.ci90_lo!=null?`[${pct(r.ci90_lo,1)}, ${pct(r.ci90_hi,1)}]`:'—'}</td>
      <td>${verdict}</td></tr>`;
  });
  $('#agg-table').innerHTML=h+'</tbody>';

  let ph=`<thead><tr><th>序列</th><th class="num">跨度</th><th class="num">事件数</th>
    <th class="num">真实均值</th><th class="num">随机均值</th><th class="num">随机标准差</th>
    <th class="num">真实值分位</th><th class="num">双尾 p</th><th>判读</th></tr></thead><tbody>`;
  Object.entries(D.placebo).forEach(([k,v])=>{
    const [vk,h]=k.split('@');
    if(v._status){ ph+=`<tr><td>${vk}</td><td class="num">${h}</td><td colspan="7" class="small">数据不足（${v._status}）</td></tr>`; return; }
    const sig = v.p_value_two_sided<0.1;
    ph+=`<tr><td>${D.series_info[vk]?D.series_info[vk].name:vk}</td><td class="num">${h}</td>
      <td class="num">${v.n_events}</td>
      <td class="num ${clsOf(v.real_mean_pct)}">${pct(v.real_mean_pct)}</td>
      <td class="num">${pct(v.placebo_mean)}</td>
      <td class="num">${pct(v.placebo_sd)}</td>
      <td class="num">${fmt(v.real_percentile,1)}</td>
      <td class="num"><b>${fmt(v.p_value_two_sided,3)}</b></td>
      <td>${sig?'<span class="badge" style="background:#1f3d2c;color:#6fcf97">与噪声有差异</span>':'<span class="badge">与随机噪声无法区分</span>'}</td></tr>`;
  });
  $('#p-table').innerHTML=ph+'</tbody>';
})();

function renderStats(){
  const vk=$('#s-var').value, hz=$('#s-h').value;
  const rows=D.aggregate.filter(r=>r.var===vk && String(r.horizon)===hz && r.stage!=='ALL');
  const all=D.aggregate.find(r=>r.var===vk && String(r.horizon)===hz && r.stage==='ALL');
  const nm={startup:'正式投产',commissioning:'试车',construction:'开工',mechanical:'中交',
    first_product:'打通全流程',commercial:'商业运营',rampup:'达产标定'};
  const W=1460, H=380, ml=70, mr=30, mt=30, mb=58;
  const iw=W-ml-mr, ih=H-mt-mb;
  const bars=rows.filter(r=>r.mean_abnormal!=null);
  const vals=bars.flatMap(r=>[r.mean_abnormal, r.ci90_lo, r.ci90_hi].filter(v=>v!=null));
  let lo=Math.min(0,...vals), hi=Math.max(0,...vals);
  const pad=(hi-lo)*0.18||0.01; lo-=pad; hi+=pad;
  const Y=v=>mt+(hi-v)/(hi-lo)*ih;
  const bw=iw/Math.max(1,bars.length);
  let s=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
  for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;
    s+=`<line class="gridln" x1="${ml}" y1="${Y(v)}" x2="${W-mr}" y2="${Y(v)}"/>`;
    s+=`<text class="lbl2" x="${ml-8}" y="${Y(v)+3}" text-anchor="end">${(v*100).toFixed(1)}%</text>`;}
  s+=`<line x1="${ml}" y1="${Y(0)}" x2="${W-mr}" y2="${Y(0)}" stroke="#3d4d61"/>`;
  bars.forEach((r,i)=>{
    const x=ml+i*bw+bw*0.22, w=bw*0.56;
    const y0=Y(0), y1=Y(r.mean_abnormal);
    s+=`<rect x="${x}" y="${Math.min(y0,y1)}" width="${w}" height="${Math.abs(y1-y0)}"
      fill="${r.mean_abnormal>0?'#e5534b':'#3fb950'}" fill-opacity="0.82" rx="2"
      data-tip="${nm[r.stage]||r.stage}｜n=${r.n}｜超额 ${pct(r.mean_abnormal)}｜t=${fmt(r.t_abnormal,2)}${r.insufficient?'｜样本不足':''}"/>`;
    if(r.ci90_lo!=null){
      s+=`<line x1="${x+w/2}" y1="${Y(r.ci90_lo)}" x2="${x+w/2}" y2="${Y(r.ci90_hi)}" stroke="#c9d5e2" stroke-width="1.4"/>`;
      s+=`<line x1="${x+w/2-5}" y1="${Y(r.ci90_lo)}" x2="${x+w/2+5}" y2="${Y(r.ci90_lo)}" stroke="#c9d5e2" stroke-width="1.4"/>`;
      s+=`<line x1="${x+w/2-5}" y1="${Y(r.ci90_hi)}" x2="${x+w/2+5}" y2="${Y(r.ci90_hi)}" stroke="#c9d5e2" stroke-width="1.4"/>`;
    }
    s+=`<text class="lbl" x="${x+w/2}" y="${mt+ih+17}" text-anchor="middle" font-size="10">${nm[r.stage]||r.stage}</text>`;
    s+=`<text class="lbl2" x="${x+w/2}" y="${mt+ih+30}" text-anchor="middle">n=${r.n}</text>`;
    s+=`<text class="lbl2" x="${x+w/2}" y="${mt+ih+42}" text-anchor="middle">t=${fmt(r.t_abnormal,1)}</text>`;
  });
  s+=`<text class="lbl2" x="${ml}" y="${mt-12}">${D.series_info[vk]?D.series_info[vk].name:vk} · ${hz} 交易日超额变化（主口径）· 误差棒=90% bootstrap CI</text>`;
  s+='</svg>';
  if(!bars.length){ $('#s-svg').innerHTML='<div class="warn">该序列/跨度无有效样本。</div>'; }
  else { $('#s-svg').innerHTML=s; bindTips('#s-svg [data-tip]'); }
}

/* ---------- ⑤ 产能 ---------- */
(function capacity(){
  $('#ramp-txt').textContent = D.ramp_assumption;
  const ps=projects.filter(p=>p.design_capacity&&p.share_pct!=null).sort((a,b)=>b.share_pct-a.share_pct);
  const W=1460,H=Math.max(300,ps.length*24+70),ml=250,mr=250,mt=30,mb=28;
  const iw=W-ml-mr;
  const maxShare=Math.max(...ps.map(p=>p.share_pct));
  const X=v=>v/maxShare*iw;
  let s=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
  ps.forEach((p,i)=>{
    const y=mt+i*24;
    const w=X(p.share_pct);
    s+=`<text class="lbl" x="${ml-10}" y="${y+12}" text-anchor="end">${p.name.slice(0,26)}</text>`;
    s+=`<rect x="${ml}" y="${y+2}" width="${Math.max(w,1)}" height="14" rx="3" fill="#4b9fd5" fill-opacity="0.8"
      data-tip="${p.name}｜设计产能 ${p.design_capacity} 万吨/年｜占 ${p.date.slice(0,4)} 年现有产能 ${p.share_pct.toFixed(2)}%"/>`;
    s+=`<text class="lbl2" x="${ml+w+7}" y="${y+13}">${p.design_capacity} 万吨/年 · ${p.share_pct.toFixed(2)}%</text>`;
  });
  s+=`<text class="lbl2" x="${ml}" y="${mt-12}">设计产能占当年行业现有产能比例（%）</text>`;
  s+='</svg>';
  $('#cap-svg').innerHTML=s; bindTips('#cap-svg [data-tip]');

  let h=`<thead><tr><th>项目</th><th class="num">设计产能<br>万吨/年</th>
    <th class="num">投产年<br>现有产能</th><th class="num">占比</th>
    <th class="num">投产首月<br>实际增量 万吨</th><th class="num">第3月</th><th class="num">第6月</th>
    <th class="num">首12个月<br>累计产量 万吨</th></tr></thead><tbody>`;
  ps.forEach(p=>{
    const e=p.ref_event||p.stage_events[0];
    const cap=e.capacity_base;
    const m0=e.design_capacity*0.30*30/365, m3=e.design_capacity*0.85*30/365, m6=e.design_capacity*0.93*30/365;
    const c12=D.default_ramp.slice(0,10).reduce((a,r)=>a+r,0)*p.design_capacity*30/365
      + Math.max(0,12-10)*p.design_capacity*30/365;
    h+=`<tr><td>${p.name}</td><td class="num"><b>${p.design_capacity}</b></td>
      <td class="num">${cap??'<span class="small">基数缺失</span>'}</td>
      <td class="num">${p.share_pct!=null?p.share_pct.toFixed(2)+'%':'—'}</td>
      <td class="num">${fmt(m0,2)}</td><td class="num">${fmt(m3,2)}</td><td class="num">${fmt(m6,2)}</td>
      <td class="num">${fmt(c12,1)}</td></tr>`;
  });
  $('#cap-table').innerHTML=h+'</tbody>';
})();

/* ---------- ⑥ 逐项目 ---------- */
let selPid=null;
(function picker(){
  const ps=projects.slice().sort((a,b)=>a.date.localeCompare(b.date));
  $('#proj-picker').innerHTML=`<label>项目</label><select id="p-sel">`+
    ps.map(p=>`<option value="${p.project_id}">${p.date} · ${p.name.slice(0,30)}</option>`).join('')+
    `</select><label>叠加</label>
     <span class="stagechip on" data-ov="futures"><span class="dot" style="background:#4b9fd5"></span>期货</span>
     <span class="stagechip on" data-ov="spot"><span class="dot" style="background:#e0a800"></span>现货</span>
     <span class="stagechip on" data-ov="inv"><span class="dot" style="background:#a371f7"></span>库存</span>
     <span class="stagechip on" data-ov="opr"><span class="dot" style="background:#3fb950"></span>开工率</span>`;
  $('#p-sel').onchange=()=>{selPid=$('#p-sel').value;renderProject();};
  $$('[data-ov]').forEach(c=>c.onclick=()=>{c.classList.toggle('on');renderProject();});
  selPid=ps[0].project_id; $('#p-sel').value=selPid;
})();
function selectProject(pid){ selPid=pid; const sel=$('#p-sel'); if(sel){sel.value=pid;} renderProject(); }
function cut(ser,a,b){ return ser.filter(r=>r[0]>=a&&r[0]<=b); }
function renderProject(){
  if(!selPid) return;
  const p=projMap[selPid]; if(!p) return;
  const ovs=new Set($$('[data-ov].on').map(c=>c.dataset.ov));
  const d0=new Date(p.stage_events[0].date), d1=new Date(p.stage_events[p.stage_events.length-1].date);
  const a=new Date(d0.getTime()-400*86400000).toISOString().slice(0,10);
  const b=new Date(d1.getTime()+400*86400000).toISOString().slice(0,10);
  const fut=cut(D.series.futures,a,b), spot=cut(D.series.spot||[],a,b);
  const inv=cut(D.series.fundamentals.inventory||[],a,b);
  const opr=cut(D.series.fundamentals.operating||[],a,b);
  const W=1460,H=400,ml=64,mr=64,mt=26,mb=44;
  const iw=W-ml-mr, ih=H-mt-mb;
  const t0a=new Date(a).getTime(), t1a=new Date(b).getTime();
  const X=t=>ml+(t-t0a)/(t1a-t0a)*iw;
  const arrs=[];
  if(ovs.has('futures')&&fut.length) arrs.push({s:fut,c:'#4b9fd5',ax:0,n:'期货'});
  if(ovs.has('spot')&&spot.length) arrs.push({s:spot,c:'#e0a800',ax:0,n:'现货'});
  if(ovs.has('inv')&&inv.length) arrs.push({s:inv,c:'#a371f7',ax:1,n:'库存'});
  if(ovs.has('opr')&&opr.length) arrs.push({s:opr,c:'#3fb950',ax:1,n:'开工率'});
  const axes=[[Infinity,-Infinity],[Infinity,-Infinity]];
  arrs.forEach(A=>A.s.forEach(r=>{const l=axes[A.ax]; l[0]=Math.min(l[0],r[1]); l[1]=Math.max(l[1],r[1]);}));
  axes.forEach(l=>{if(!isFinite(l[0])){l[0]=0;l[1]=1;} const pd=(l[1]-l[0])*0.1||1; l[0]-=pd;l[1]+=pd;});
  const Y=(v,ax)=>mt+(axes[ax][1]-v)/(axes[ax][1]-axes[ax][0])*ih;
  let s=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
  for(let i=0;i<=4;i++){
    const v=axes[0][0]+(axes[0][1]-axes[0][0])*i/4, y=Y(v,0);
    s+=`<line class="gridln" x1="${ml}" y1="${y}" x2="${W-mr}" y2="${y}"/>`;
    s+=`<text class="lbl2" x="${ml-7}" y="${y+3}" text-anchor="end">${v.toFixed(0)}</text>`;
    if(isFinite(axes[1][0])){
      const v2=axes[1][0]+(axes[1][1]-axes[1][0])*i/4;
      s+=`<text class="lbl2" x="${W-mr+7}" y="${Y(v2,1)+3}">${v2.toFixed(0)}</text>`;
    }
  }
  // 月份刻度
  const y0=new Date(a).getFullYear(), y1=new Date(b).getFullYear();
  for(let y=y0;y<=y1;y++){for(let m=0;m<12;m+=3){
    const t=new Date(y,m,1).getTime(); if(t<t0a||t>t1a) continue;
    const x=X(t);
    s+=`<line x1="${x}" y1="${mt+ih}" x2="${x}" y2="${mt+ih+4}" stroke="#3d4d61"/>`;
    s+=`<text class="lbl2" x="${x}" y="${mt+ih+16}" text-anchor="middle">${y}-${String(m+1).padStart(2,'0')}</text>`;}}
  // 事件线
  p.stage_events.forEach(e=>{
    const x=X(new Date(e.date).getTime());
    const col=STAGECOL[e.stage]||'#666';
    s+=`<line x1="${x}" y1="${mt}" x2="${x}" y2="${mt+ih}" stroke="${col}" stroke-width="1.4" stroke-opacity="0.85" stroke-dasharray="4 3"/>`;
    s+=`<rect x="${x-1}" y="${mt-4}" width="2" height="8" fill="${col}"/>`;
  });
  arrs.forEach(A=>{
    const d=A.s.map(r=>`${X(new Date(r[0]).getTime())},${Y(r[1],A.ax)}`).join(' ');
    s+=`<polyline fill="none" stroke="${A.c}" stroke-width="1.8" points="${d}" stroke-linejoin="round"/>`;
  });
  s+=`<text class="lbl2" x="${ml}" y="${mt-10}">${ovs.has('futures')?'期货/现货(元/吨)':''}</text>`;
  if(arrs.some(A=>A.ax===1)) s+=`<text class="lbl2" x="${W-mr}" y="${mt-10}" text-anchor="end">库存(万吨)/开工率(%)</text>`;
  s+='</svg>';
  $('#proj-svg').innerHTML=s;

  const nm={construction:'开工',mechanical:'中交',commissioning:'试车',startup:'正式投产',
    first_product:'打通全流程',commercial:'商业运营',rampup:'达产标定'};
  let dh=`<div class="grid2"><div>
    <h3 style="margin-top:0">${p.name}</h3>
    <table><tbody>
    <tr><td class="small" style="width:110px">区域</td><td>${p.region}</td></tr>
    <tr><td class="small">工艺路线</td><td>${p.process}</td></tr>
    <tr><td class="small">设计产能</td><td><b>${p.design_capacity}</b> 万吨/年（≠投产当天产量）</td></tr>
    <tr><td class="small">占当年产能</td><td>${p.share_pct!=null?p.share_pct.toFixed(2)+'%（基数 '+p.capacity_base+' 万吨/年）':'基数缺失'}</td></tr>
    </tbody></table></div><div>
    <h3 style="margin-top:0">分层事件链</h3>
    <table><thead><tr><th>节点</th><th>日期</th><th>证据</th><th>原文关键句</th></tr></thead><tbody>
    ${p.stage_events.map(e=>`<tr><td><span class="dot" style="background:${STAGECOL[e.stage]||'#666'}"></span> ${nm[e.stage]||e.stage}</td>
      <td class="mono">${e.date}</td><td><span class="badge">${e.evidence_grade||e.grade||'—'}</span>${e.single_source?'<span class="badge" style="background:#4a2b12;color:#e0a86a">单一来源</span>':''}</td>
      <td class="small">${((e.quote||e.evidence_quote||'').slice(0,90))||'<i>原文引句见 Excel 02_事件时间线</i>'}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  $('#proj-detail').innerHTML=dh;
}

/* ---------- ⑦ 数据边界 ---------- */
(function gaps(){
  const rows=Object.entries(D.series_info).map(([k,v])=>
    `<tr><td>${v.name}</td><td class="mono">${v.start||'—'}</td><td class="mono">${v.end||'—'}</td>
     <td class="num">${v.n}</td><td>${v.freq}</td></tr>`).join('');
  const missing=['PP 华东/华北/华南 分区域现货价（卓创/隆众/金联创均为付费或反爬）',
    '两油库存 / 社会库存日频序列','区域价差（华东-华南、华东-华北）连续时间序列',
    '项目级逐月达产负荷（多数项目未披露）','PP 分牌号、分区域的严格口径现货价（100ppi 基差表未明示区域，只能称「生意社PP现货价」）'];
  $('#series-gap').innerHTML=`<table><thead><tr><th>已获得序列</th><th>起</th><th>止</th><th class="num">点数</th><th>频率</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <h3>未获得（如实标注缺口，未做任何估算）</h3>
    <ul style="color:#c5d0dc;font-size:12.5px;padding-left:18px;margin:0">
    ${missing.map(m=>`<li>${m}</li>`).join('')}</ul>`;
  $('#sources').innerHTML=`<div class="card">
    <h3 style="margin-top:0">项目事实来源</h3>
    <ul style="color:#c5d0dc;font-size:12.5px;padding-left:18px">
      <li>《中国PP新增产能（2023–2025）核实报告》—— 逐项目事实链表格，含原文引句、URL、发布日期、证据等级（A/B/C/D）</li>
      <li>《中国聚丙烯 2020–2022 新增产能投产核实报告》—— 22 个项目、211 条来源链接、交叉核验评级</li>
      <li>《中国聚丙烯（PP）在建/扩建装置公开进展核实报告 2026-10-20》—— 2026 年在建与最新投产项目</li>
    </ul>
    <h3>市场价格与基本面来源</h3>
    <ul style="color:#c5d0dc;font-size:12.5px;padding-left:18px">
      <li>PP 期货主力连续日线：新浪财经 InnerFuturesNewService（symbol=pp0，未复权），2014-02-28 → 2026-10-20</li>
      <li>PP 现货价：生意社 100ppi「商品主力基差表」日快照页 (sf2/day-YYYY-MM-DD.html)，2019-01-02→2026-10-20 共 1887 点，逐条带当日快照 URL；PP(拉丝)/PP(纤维)基准价日度公告作为交叉验证序列</li>
      <li>库存 / 开工率 / 下游负荷：生意社 PP 月度经评正文原文抽取（保留原文引句）</li>
    </ul>
    <div class="warn" style="margin-top:12px">本报告所有数字均可回溯到上述来源。凡未获得的数据一律标注为“缺口”，
    <b>未做任何插值、估算或“合理假设”填充</b>。</div></div>`;
})();

/* init */
renderCand(); renderTimeline(); renderWindow(); renderStats(); renderProject();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
