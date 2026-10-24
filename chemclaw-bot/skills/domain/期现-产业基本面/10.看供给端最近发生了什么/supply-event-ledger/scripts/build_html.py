# -*- coding: utf-8 -*-
"""生成单文件自包含交互式 HTML 供给事件时间线报告。

特性：
  * 内联 ECharts（离线可用）
  * 装置事件时间线（甘特）、地区分布、事件类型分布、影响量排行
  * 明细表支持按事件类型/大区/工艺/企业/确认状态筛选 + 搜索
  * 点击事件打开抽屉：企业、装置、产能、状态序列、来源、公式
  * 切换“只看已确认 / 含未来计划事件”
  * 公式与参数可展开、可调（负荷、爬坡），前端实时重算
"""
from __future__ import annotations
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc_impact as ci

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ASSETS = os.path.join(SKILL, 'assets')


def load(case_dir):
    def j(f):
        d = json.load(open(os.path.join(case_dir, f), encoding='utf-8'))
        return d
    return {
        'datum': j('datum.json')['meta'],
        'companies': j('companies.json'),
        'units': j('units.json')['units'],
        'events': j('status_events.json')['events'],
        'planned': j('planned_events.json')['planned_events'],
    }


def build_payload(case_dir):
    D = load(case_dir)
    meta = D['datum']
    ws_, we_ = ci.parse_date(meta['window_start']), ci.parse_date(meta['window_end'])
    S = ci.summarize(D['events'], ws_, we_, meta['national_capacity_wt'], meta['weekly_output_t'])
    evmap = {e['event_id']: e for e in D['events']}
    rows = []
    for r in S['rows']:
        e = evmap[r['event_id']]
        rows.append({
            **{k: r.get(k) for k in ('event_id', 'unit_id', 'company', 'unit_name', 'province',
                                     'region_code', 'route', 'capacity_wt', 'event_type',
                                     'start_date', 'end_date', 'status_latest', 'confidence',
                                     'source_count', 'bucket', 'days', 'loss_t', 'daily_t',
                                     'baseline_load', 'downtime_load', 'reduction_coef',
                                     'loss_upper_t', 'formula', 'assumed', 'is_stock',
                                     'excluded', 'scope')},
            'site': e.get('site', ''),
            'status_note': e.get('status_note', ''),
            'event_family': e.get('event_family', ''),
            'conflict': e.get('conflict', ''),
            'dedupe_check': e.get('dedupe_check', ''),
            'sources': e.get('sources', []),
            'load_note': e.get('load_note', ''),
            'clip_to_window': bool(e.get('clip_to_window')),
            'starts_before_window': bool(e.get('starts_before_window')),
            'reason': e.get('reason', ''),
        })
    return {
        'meta': meta,
        'regions': D['companies']['regions'],
        'process_routes': D['companies']['process_routes'],
        'regions_all': D['companies']['regions'],
        'units': D['units'],
        'events': rows,
        'planned': D['planned'],
        'summary': {k: v for k, v in S.items() if k != 'rows'},
    }


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script>__ECHARTS__</script>
<style>
:root{
  --bg:#f6f8fb; --card:#ffffff; --ink:#0f2e4c; --ink2:#43607d; --ink3:#7b93aa;
  --line:#e2e9f1; --brand:#1f4e79; --brand2:#2f7fb8; --accent:#e8833a;
  --ok:#2f9e6f; --okbg:#eaf7f1; --warn:#c94a4a; --warnbg:#fdeeee;
  --ovs:#6b5fc4; --ovsbg:#f2f0fb; --stock:#8a8a8a; --stockbg:#f5f5f5;
  --shadow:0 2px 10px rgba(16,42,67,.07),0 12px 32px rgba(16,42,67,.06);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1560px;margin:0 auto;padding:26px 24px 90px}
/* header */
.hero{background:linear-gradient(135deg,#123a5c 0%,#1f4e79 45%,#2f7fb8 100%);color:#fff;
  border-radius:18px;padding:28px 32px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.hero:after{content:"";position:absolute;right:-70px;top:-70px;width:300px;height:300px;
  background:radial-gradient(circle,rgba(255,255,255,.16),transparent 68%);border-radius:50%}
.hero h1{margin:0 0 6px;font-size:25px;letter-spacing:.5px;font-weight:700}
.hero .sub{opacity:.9;font-size:13.5px}
.tagrow{margin-top:14px;display:flex;gap:8px;flex-wrap:wrap}
.tag{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.28);
  padding:3px 11px;border-radius:20px;font-size:12px}
/* kpi */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(196px,1fr));gap:14px;margin:18px 0}
.kpi{background:var(--card);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow);
  border-left:4px solid var(--brand2);position:relative}
.kpi.k-warn{border-left-color:var(--warn)}
.kpi.k-ovs{border-left-color:var(--ovs)}
.kpi.k-ok{border-left-color:var(--ok)}
.kpi .lab{font-size:12.5px;color:var(--ink3);margin-bottom:5px}
.kpi .val{font-size:26px;font-weight:700;letter-spacing:-.4px;line-height:1.15}
.kpi .unit{font-size:13px;font-weight:500;color:var(--ink2);margin-left:3px}
.kpi .note{font-size:11.5px;color:var(--ink3);margin-top:5px}
/* card */
.card{background:var(--card);border-radius:16px;box-shadow:var(--shadow);padding:20px 22px;margin-bottom:18px}
.card h2{margin:0 0 4px;font-size:16.5px;font-weight:700;display:flex;align-items:center;gap:9px}
.card h2 .dot{width:4px;height:17px;background:var(--brand2);border-radius:2px}
.card .hint{color:var(--ink3);font-size:12.5px;margin:0 0 14px}
.grid2{display:grid;grid-template-columns:1.32fr 1fr;gap:18px}
@media(max-width:1180px){.grid2{grid-template-columns:1fr}}
/* controls */
.ctrl{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:13px}
.seg{display:inline-flex;background:#eef3f8;border-radius:10px;padding:3px;gap:2px}
.seg button{border:0;background:transparent;padding:6px 14px;border-radius:8px;cursor:pointer;
  font-size:13px;color:var(--ink2);font-family:inherit;transition:.18s;font-weight:500}
.seg button.on{background:#fff;color:var(--brand);box-shadow:0 1px 4px rgba(16,42,67,.13);font-weight:700}
select,input[type=text]{border:1px solid var(--line);background:#fff;border-radius:9px;
  padding:7px 11px;font-size:13px;color:var(--ink);font-family:inherit;outline:none}
select:focus,input:focus{border-color:var(--brand2)}
input[type=text]{min-width:190px}
.pill{font-size:12px;padding:2px 9px;border-radius:20px;background:#eef3f8;color:var(--ink2)}
/* table */
.tblbox{overflow:auto;max-height:620px;border:1px solid var(--line);border-radius:12px}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}
thead th{position:sticky;top:0;background:#f2f6fa;color:var(--ink2);font-weight:700;
  text-align:left;padding:9px 11px;border-bottom:1px solid var(--line);white-space:nowrap;z-index:2;font-size:12.5px}
tbody td{padding:9px 11px;border-bottom:1px solid #f0f4f8;vertical-align:top}
tbody tr{cursor:pointer;transition:background .13s}
tbody tr:hover{background:#f7fafd}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.bar{height:6px;border-radius:3px;background:#e8eef5;position:relative;min-width:52px}
.bar>i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:linear-gradient(90deg,#4f9bd1,#1f4e79)}
.badge{display:inline-block;font-size:11.5px;padding:1.5px 8px;border-radius:6px;font-weight:600;white-space:nowrap}
.b-ok{background:var(--okbg);color:var(--ok)}
.b-warn{background:var(--warnbg);color:var(--warn)}
.b-ovs{background:var(--ovsbg);color:var(--ovs)}
.b-stock{background:var(--stockbg);color:var(--stock)}
.b-info{background:#eaf1f8;color:var(--brand2)}
.b-plan{background:#fff3e4;color:#b4691b}
.chip{display:inline-block;font-size:11px;padding:1px 7px;border-radius:5px;background:#f0f4f8;color:var(--ink2);margin-right:4px}
/* drawer */
.mask{position:fixed;inset:0;background:rgba(12,32,52,.42);opacity:0;pointer-events:none;transition:.22s;z-index:40}
.mask.on{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(620px,94vw);background:#fff;z-index:50;
  transform:translateX(100%);transition:transform .28s cubic-bezier(.3,.8,.3,1);
  box-shadow:-8px 0 40px rgba(12,32,52,.2);display:flex;flex-direction:column}
.drawer.on{transform:none}
.drawer .dh{padding:18px 22px 14px;border-bottom:1px solid var(--line);background:linear-gradient(135deg,#f7fafd,#fff)}
.drawer .dh h3{margin:0 0 5px;font-size:17px}
.drawer .db{padding:16px 22px 30px;overflow:auto;flex:1}
.close{position:absolute;right:14px;top:14px;border:0;background:#eef3f8;width:30px;height:30px;
  border-radius:9px;cursor:pointer;font-size:17px;color:var(--ink2);line-height:1}
.kv{display:grid;grid-template-columns:98px 1fr;gap:7px 12px;font-size:13px;margin:12px 0}
.kv dt{color:var(--ink3);font-size:12.5px}
.kv dd{margin:0;color:var(--ink)}
.sec{margin:18px 0 8px;font-size:13px;font-weight:700;color:var(--brand);display:flex;align-items:center;gap:7px}
.sec:before{content:"";width:3px;height:13px;background:var(--brand2);border-radius:2px}
.src{border:1px solid var(--line);border-left:3px solid var(--brand2);border-radius:9px;
  padding:10px 12px;margin-bottom:9px;font-size:12.5px;background:#fbfdff}
.src .sn{font-weight:700;color:var(--ink)}
.src .sd{color:var(--ink3);margin-left:7px;font-size:11.5px}
.src .sq{margin-top:6px;color:var(--ink2);line-height:1.62;font-size:12.5px}
.src a{color:#0563c1;text-decoration:none;font-size:11.5px;word-break:break-all}
.formula{background:#0f2e4c;color:#d8e6f2;border-radius:10px;padding:12px 14px;font-size:12.5px;
  font-family:ui-monospace,Consolas,monospace;line-height:1.7;overflow-x:auto}
.formula b{color:#7fd3a6}
details{border:1px solid var(--line);border-radius:10px;padding:11px 14px;background:#fbfdff;margin-top:12px}
summary{cursor:pointer;font-weight:600;font-size:13px;color:var(--brand)}
details p,details li{font-size:12.5px;color:var(--ink2)}
.slider{display:flex;align-items:center;gap:10px;margin:9px 0;font-size:12.5px}
.slider input[type=range]{flex:1}
.chart{width:100%}
.note{background:#fffaf0;border:1px solid #f5e0bd;border-radius:11px;padding:12px 15px;
  font-size:12.5px;color:#8a5a11;margin-top:12px;line-height:1.7}
.note b{color:#7a4a06}
.foot{text-align:center;color:var(--ink3);font-size:12px;margin-top:26px;line-height:1.8}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin-top:8px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}
.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:760px){.split{grid-template-columns:1fr}.kpis{grid-template-columns:1fr 1fr}}
.mini{font-size:12px;color:var(--ink3)}
</style>
</head>
<body>
<div class="wrap">

  <div class="hero">
    <h1>__TITLE__</h1>
    <div class="sub">统计窗口 <b>__WIN_START__ ~ __WIN_END__</b>　·　基准日 __AS_OF__　·　口径：国内甲醇生产装置（煤制 / 天然气制 / 焦炉气制 / 其他）</div>
    <div class="tagrow" id="heroTags"></div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="card">
    <h2><span class="dot"></span>装置事件时间线</h2>
    <p class="hint">横轴为时间，纵轴按大区分组；条带长度=事件持续时间，颜色区分事件类型。虚线右侧为未来已披露事项（如开启）。点击任意条带查看详情。</p>
    <div class="ctrl">
      <div class="seg" id="scopeSeg">
        <button data-scope="confirmed" class="on">只看已确认事件</button>
        <button data-scope="all">含未来计划事件</button>
      </div>
      <span class="pill" id="tlCount"></span>
    </div>
    <div id="timeline" class="chart" style="height:520px"></div>
    <div class="legend" id="tlLegend"></div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2><span class="dot"></span>确认减产影响量排行</h2>
      <p class="hint">仅统计已确认口径（国内装置）。数值为窗口内理论减产量，非设计产能。</p>
      <div id="rankChart" class="chart" style="height:430px"></div>
    </div>
    <div class="card">
      <h2><span class="dot"></span>大区分布</h2>
      <p class="hint">按大区汇总的确认减产（吨）与事件数量。</p>
      <div id="regionChart" class="chart" style="height:430px"></div>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2><span class="dot"></span>事件类型结构</h2>
      <p class="hint">计划检修 / 实际停车 / 意外故障 / 降负荷 的减产贡献占比。</p>
      <div id="typeChart" class="chart" style="height:360px"></div>
    </div>
    <div class="card">
      <h2><span class="dot"></span>工艺路线对比</h2>
      <p class="hint">煤制是国内主体；天然气制集中在西南/青海；焦炉气制分散于晋陕蒙鲁。</p>
      <div id="routeChart" class="chart" style="height:360px"></div>
    </div>
  </div>

  <div class="card">
    <h2><span class="dot"></span>事件明细表</h2>
    <p class="hint">支持组合筛选与关键词搜索。点击任意行打开右侧详情（含来源与计算过程）。</p>
    <div class="ctrl">
      <select id="fStatus">
        <option value="confirmed">已确认（国内口径）</option>
        <option value="all">全部（含境外/未确认/存量）</option>
        <option value="overseas">仅境外装置</option>
        <option value="unconfirmed">仅未确认/待核</option>
      </select>
      <select id="fType"><option value="">全部事件类型</option></select>
      <select id="fRegion"><option value="">全部大区</option></select>
      <select id="fRoute"><option value="">全部工艺</option></select>
      <select id="fCompany"><option value="">全部企业</option></select>
      <input type="text" id="fSearch" placeholder="搜索企业 / 装置 / 省份…">
      <span class="pill" id="rowCount"></span>
    </div>
    <div class="tblbox">
      <table id="mainTbl">
        <thead><tr>
          <th>事件ID</th><th>企业</th><th>装置</th><th>类型</th><th>工艺</th>
          <th>大区</th><th>产能<br><span class="mini">万吨/年</span></th>
          <th>起止</th><th>天数</th><th>减产<br><span class="mini">吨</span></th>
          <th>影响强度</th><th>状态</th><th>置信度</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2><span class="dot"></span>未来已披露事项（与已发生事件严格分列）</h2>
    <p class="hint">以下为已公开披露但尚未发生或未获执行确认的事项，不计入上方任何影响量合计。</p>
    <div class="tblbox" style="max-height:none">
      <table id="planTbl">
        <thead><tr>
          <th>ID</th><th>企业</th><th>装置</th><th>类型</th><th>产能<br><span class="mini">万吨/年</span></th>
          <th>计划时点</th><th>披露方式</th><th>状态说明</th><th>置信度</th><th>来源</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2><span class="dot"></span>计算口径与公式（可展开）</h2>
    <details open>
      <summary>停车 / 检修 / 故障类：理论减产量</summary>
      <div class="formula">L = (产能 ÷ 365) × 窗口内停留天数 × (基准负荷 − 事件期负荷)
基准负荷默认 = 1.00；计划检修、实际停车、意外故障的事件期负荷 = 0
⇒ L = 产能 ÷ 365 × 天数</div>
      <p class="mini" style="margin-top:8px">示例：新奥一期 60 万吨，9/4–9/26 共 23 天 ⇒ 60×10000÷365×23×(1.00−0.00) = 37,808 吨。</p>
    </details>
    <details>
      <summary>降负荷类：按实际负荷折算，不用设计产能代替</summary>
      <div class="formula">L = (产能 ÷ 365) × 天数 × (基准负荷 − 实际负荷)
仅当来源明确给出负荷数值（如“负荷45%”）才计入确认口径；
只写“低负荷/开工不满”而无数值者，按假设值计算并强制排除出确认合计。</div>
    </details>
    <details>
      <summary>新增产能：与检修损失分列，绝不相互抵销</summary>
      <div class="formula">A = (产能 ÷ 365) × 窗口内运行天数 × 爬坡负荷
爬坡负荷默认 0.85（区间 0.80–0.90），投产 ≠ 达产。</div>
    </details>
    <details>
      <summary>时间口径</summary>
      <ul>
        <li>天数含首尾（left-closed, right-closed）；跨窗口事件只计算落在窗口内的天数。</li>
        <li>存量停车（窗口开始前已停车且无恢复计划）单独标记，不计入窗口内边际变化。</li>
        <li>境外装置（伊朗、马来西亚、文莱等）只影响进口/到港，<b>不并入国产供给合计</b>。</li>
      </ul>
    </details>
    <div class="note">
      <b>重要说明：</b>本报告只回答“供给端最近发生了什么、具体到哪些装置、影响多少产量、哪些尚未确定”。
      部分事件起止为“按披露的检修时长倒推”的推定值（误差约 ±3~7 天），已在明细中逐条标注；
      传闻级信息仅登记、不计入任何确认合计。<b>本报告不构成供应预警、价格判断或交易建议。</b>
    </div>
  </div>

  <div class="foot">
    数据来源：隆众资讯（经我的钢铁网转载）、金联创、生意社 PriceSeek、化销网装置动态、甲醇时代信息播报、各期货公司研究观点。<br>
    生成时间 __GEN_TIME__　·　统计窗口 __WIN_START__ ~ __WIN_END__　·　全部来源链接见明细抽屉
  </div>
</div>

<div class="mask" id="mask"></div>
<div class="drawer" id="drawer">
  <div class="dh">
    <h3 id="dTitle">—</h3>
    <div id="dSub" class="mini"></div>
    <button class="close" id="dClose">×</button>
  </div>
  <div class="db" id="dBody"></div>
</div>

<script>
const DATA = __DATA__;

const ROUTE_CN = {COAL:'煤制',NG:'天然气制',COKE_OVEN:'焦炉气制',CO2H2:'二氧化碳加氢',FURNACE_GAS:'矿热炉尾气',UNKNOWN:'未披露'};
const REGION_CN = {};
(DATA.regions||[]).forEach(r=>REGION_CN[r.code]=r.name);
const BUCKET = {
  domestic_confirmed:{cn:'国内·已确认',cls:'b-ok'},
  overseas:{cn:'境外·进口端',cls:'b-ovs'},
  unconfirmed:{cn:'未确认/待核',cls:'b-warn'},
  stock_stop:{cn:'存量停车',cls:'b-stock'},
  status_only:{cn:'状态确认',cls:'b-info'},
  new_capacity:{cn:'新增产能',cls:'b-ok'}
};
const TYPE_COLOR = {'计划检修':'#2f7fb8','实际停车':'#c94a4a','意外故障':'#e8833a','复产':'#2f9e6f','降负荷':'#c9a227','新投产':'#6b5fc4','试车':'#8a7fd4'};

const N = x => (x==null||x==='')?'—':Number(x).toLocaleString('zh-CN',{maximumFractionDigits:1});
const fdate = s => s ? s : '—';

/* ---------- KPI ---------- */
(function kpi(){
  const s = DATA.summary, T = s.totals;
  const items = [
    {lab:'国内已确认减产', val:N(s.domestic_loss_wt), unit:'万吨', note:`${T.n_domestic_confirmed} 起确认事件 · 占窗口内理论产能 ${s.domestic_loss_pct_window_capacity}%`, cls:'k-warn'},
    {lab:'折合周产量', val:s.domestic_loss_weeks, unit:'周', note:`参照 ${N(s.weekly_output_t/10000)} 万吨/周（隆众 9/25–10/1）`, cls:''},
    {lab:'境外装置影响', val:N(s.overseas_loss_wt), unit:'万吨', note:`仅影响进口/到港，不并入国产合计`, cls:'k-ovs'},
    {lab:'未确认 / 待核', val:N(s.unconfirmed_loss_wt), unit:'万吨', note:`${T.n_unconfirmed} 起，未计入任何确认合计`, cls:'k-warn'},
    {lab:'窗口内新增产能贡献', val:N(s.new_capacity_wt), unit:'万吨', note:'与检修损失分列，不相互抵销', cls:'k-ok'},
    {lab:'已建档装置', val:N(DATA.units.length), unit:'套', note:`事件 ${DATA.events.length} 条 · 未来事项 ${DATA.planned.length} 条`, cls:''}
  ];
  document.getElementById('kpis').innerHTML = items.map(i=>`
    <div class="kpi ${i.cls}">
      <div class="lab">${i.lab}</div>
      <div class="val">${i.val}<span class="unit">${i.unit}</span></div>
      <div class="note">${i.note}</div>
    </div>`).join('');
  document.getElementById('heroTags').innerHTML = [
    `窗口 ${DATA.meta.window_start} ~ ${DATA.meta.window_end}`,
    `已建档装置 ${DATA.units.length} 套`,
    `已发生事件 ${DATA.events.length} 条`,
    `未来已披露 ${DATA.planned.length} 条`,
    `来源 ${DATA.events.reduce((a,e)=>a+(e.sources?e.sources.length:0),0)} 条`
  ].map(t=>`<span class="tag">${t}</span>`).join('');
})();

/* ---------- filters ---------- */
let SCOPE='confirmed';
let FILT={status:'confirmed',type:'',region:'',route:'',company:'',q:''};

function confirmedRows(){ return DATA.events.filter(e=>e.bucket==='domestic_confirmed'); }

function baseRows(){
  if(SCOPE==='confirmed') return confirmedRows();
  return DATA.events;
}

function fillSelects(){
  const types=[...new Set(DATA.events.map(e=>e.event_type))];
  const regions=[...new Set(DATA.events.map(e=>e.region_code))];
  const routes=[...new Set(DATA.events.map(e=>e.route))];
  const comps=[...new Set(DATA.events.map(e=>e.company))].sort();
  const t=document.getElementById('fType');
  types.forEach(v=>t.insertAdjacentHTML('beforeend',`<option value="${v}">${v}</option>`));
  const r=document.getElementById('fRegion');
  regions.forEach(v=>r.insertAdjacentHTML('beforeend',`<option value="${v}">${REGION_CN[v]||v}</option>`));
  const rt=document.getElementById('fRoute');
  routes.forEach(v=>rt.insertAdjacentHTML('beforeend',`<option value="${v}">${ROUTE_CN[v]||v}</option>`));
  const c=document.getElementById('fCompany');
  comps.forEach(v=>c.insertAdjacentHTML('beforeend',`<option value="${v}">${v}</option>`));
}
fillSelects();

/* ---------- timeline chart ---------- */
let tlChart, rankChart, regionChart, typeChart, routeChart;

function renderTimeline(){
  const el=document.getElementById('timeline');
  if(!tlChart) tlChart=echarts.init(el);
  let rows = baseRows().filter(e=>e.start_date);
  const groups=[...new Set(rows.map(e=>e.region_code))];
  const yLabels=groups.map(g=>REGION_CN[g]||g);
  const series=[];

  // 按事件类型分组系列，便于图例过滤
  const byType={};
  rows.forEach(e=>{ (byType[e.event_type]=byType[e.event_type]||[]).push(e); });
  const winStart=DATA.meta.window_start, winEnd=DATA.meta.window_end;

  Object.keys(byType).forEach(tp=>{
    const items=byType[tp];
    series.push({
      name:tp, type:'custom', renderItem:renderGantt,
      encode:{x:[0,1],y:2},
      itemStyle:{color:TYPE_COLOR[tp]||'#2f7fb8'},
      data:items.map(e=>{
        const gi=groups.indexOf(e.region_code);
        return {
          value:[e.start_date, e.end_date||winEnd, gi, e],
          name:e.company
        };
      })
    });
  });

  // 未来计划事件（虚线空心）
  if(SCOPE==='all'){
    const plans=DATA.planned.filter(p=>p.planned_date);
    series.push({
      name:'未来已披露', type:'custom', renderItem:renderGanttPlan,
      encode:{x:[0,1],y:2},
      itemStyle:{color:'#b4691b'},
      data:plans.map(p=>{
        let gi=groups.indexOf(p.region_code);
        if(gi<0) gi=0;
        return {value:[p.planned_date, winEnd, gi, p], name:p.company};
      })
    });
  }

  tlChart.setOption({
    animationDuration:520,
    grid:{left:132,right:36,top:52,bottom:44},
    tooltip:{
      trigger:'item', confine:true, borderWidth:0, backgroundColor:'rgba(15,46,76,.95)',
      textStyle:{color:'#eaf3fb',fontSize:12.5}, padding:[9,13],
      formatter:p=>{
        const v=p.value[3]; if(!v) return '';
        const isPlan = !!v.plan_id;
        const loss = isPlan ? '—（未来事项）' : (v.loss_t==null?'不计':N(v.loss_t)+' 吨');
        return `<b>${v.company}</b><br>${v.unit_name||v.unit_name}<br>
          类型：${v.event_type}　工艺：${ROUTE_CN[v.route]||v.route||'—'}<br>
          产能：${N(v.capacity_wt)} 万吨/年<br>
          起止：${v.start_date||v.planned_date||'—'} → ${v.end_date||'—'}<br>
          减产：${loss}<br>
          <span style="opacity:.72">点击查看详情</span>`;
      }
    },
    legend:{top:8,left:8,itemWidth:11,itemHeight:11,textStyle:{color:'#43607d',fontSize:12}},
    xAxis:{type:'time',min:winStart,max:winEnd,axisLine:{lineStyle:{color:'#cfdce8'}},
      splitLine:{show:true,lineStyle:{color:'#eef3f8'}},
      axisLabel:{color:'#7b93aa',fontSize:11.5,formatter:v=>{const d=new Date(v);return (d.getMonth()+1)+'/'+d.getDate();}}},
    yAxis:{type:'category',data:yLabels,inverse:true,
      axisLine:{lineStyle:{color:'#cfdce8'}},axisTick:{show:false},
      axisLabel:{color:'#43607d',fontSize:12},splitLine:{show:true,lineStyle:{color:'#f2f6fa'}}},
    dataZoom:[{type:'inside',xAxisIndex:0,filterMode:'weakFilter'}],
    series
  },true);

  document.getElementById('tlCount').textContent =
    SCOPE==='confirmed' ? `显示 ${rows.length} 条已确认事件` : `显示 ${rows.length} 条已发生 + ${DATA.planned.length} 条未来事项`;
  document.getElementById('tlLegend').innerHTML =
    Object.keys(TYPE_COLOR).map(k=>`<span><i style="background:${TYPE_COLOR[k]}"></i>${k}</span>`).join('') +
    `<span><i style="background:#fff;border:1.5px dashed #b4691b"></i>未来已披露</span>`;
}


function renderGantt(params,api){
  const cat=api.value(2);
  const s=api.coord([api.value(0),cat]);
  const e=api.coord([api.value(1),cat]);
  const h=Math.min(15,api.size([0,1])[1]*0.52);
  const w=Math.max(3,e[0]-s[0]);
  return {
    type:'rect', shape:{x:s[0],y:s[1]-h/2,width:w,height:h,r:3},
    style:{fill:api.visual('color'),opacity:.9},
    emphasis:{style:{opacity:1}}
  };
}
function renderGanttPlan(params,api){
  const cat=api.value(2);
  const s=api.coord([api.value(0),cat]);
  const e=api.coord([api.value(1),cat]);
  const h=13;
  const w=Math.max(6,Math.min(e[0]-s[0],70));
  return {
    type:'rect', shape:{x:s[0],y:s[1]-h/2,width:w,height:h,r:3},
    style:{fill:'#fff',stroke:'#b4691b',lineWidth:1.4,lineDash:[4,3]}
  };
}

/* ---------- charts ---------- */
function renderRank(){
  const el=document.getElementById('rankChart');
  if(!rankChart) rankChart=echarts.init(el);
  const rows=confirmedRows().filter(e=>e.loss_t>0).sort((a,b)=>a.loss_t-b.loss_t);
  rankChart.setOption({
    grid:{left:118,right:76,top:14,bottom:26},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},borderWidth:0,
      backgroundColor:'rgba(15,46,76,.95)',textStyle:{color:'#eaf3fb',fontSize:12.5},
      formatter:p=>{const e=p[0].data.e; return `<b>${e.company}</b><br>${e.unit_name}<br>
        ${e.event_type} · ${e.days} 天<br>减产 ${N(e.loss_t)} 吨<br>
        <span style="opacity:.75">${e.capacity_wt}×10000/365×${e.days}×(1−${e.downtime_load})</span>`;}},
    xAxis:{type:'value',axisLabel:{color:'#7b93aa',fontSize:11,formatter:v=>N(v/10000)+'万'},
      splitLine:{lineStyle:{color:'#eef3f8'}},axisLine:{show:false}},
    yAxis:{type:'category',data:rows.map(e=>e.company.length>11?e.company.slice(0,10)+'…':e.company),
      axisTick:{show:false},axisLine:{show:false},
      axisLabel:{color:'#43607d',fontSize:11.5}},
    series:[{
      type:'bar',barWidth:'62%',
      itemStyle:{borderRadius:[0,4,4,0],
        color:p=>{const e=rows[p.dataIndex];const c=TYPE_COLOR[e.event_type]||'#2f7fb8';
          return new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:c+'99'},{offset:1,color:c}]);}},
      label:{show:true,position:'right',color:'#43607d',fontSize:11,
        formatter:p=>N(p.value/10000)+'万'},
      data:rows.map(e=>({value:e.loss_t,e}))
    }]
  },true);
}

function renderRegion(){
  const el=document.getElementById('regionChart');
  if(!regionChart) regionChart=echarts.init(el);
  const agg={};
  confirmedRows().forEach(e=>{
    const k=REGION_CN[e.region_code]||e.region_code;
    agg[k]=agg[k]||{loss:0,n:0};
    agg[k].loss+=e.loss_t||0; agg[k].n++;
  });
  const arr=Object.entries(agg).sort((a,b)=>b[1].loss-a[1].loss);
  regionChart.setOption({
    grid:{left:16,right:22,top:34,bottom:22,containLabel:true},
    tooltip:{trigger:'item',borderWidth:0,backgroundColor:'rgba(15,46,76,.95)',
      textStyle:{color:'#eaf3fb',fontSize:12.5},
      formatter:p=>`<b>${p.name}</b><br>确认减产 ${N(p.value)} 吨<br>事件 ${arr[p.dataIndex][1].n} 起`},
    xAxis:{type:'value',axisLabel:{color:'#7b93aa',fontSize:11,formatter:v=>N(v/10000)+'万'},
      splitLine:{lineStyle:{color:'#eef3f8'}},axisLine:{show:false}},
    yAxis:{type:'category',data:arr.map(a=>a[0]).reverse(),axisTick:{show:false},
      axisLine:{show:false},axisLabel:{color:'#43607d',fontSize:11.5}},
    series:[{
      type:'bar',barWidth:'56%',
      itemStyle:{borderRadius:[0,5,5,0],
        color:new echarts.graphic.LinearGradient(0,0,1,0,
          [{offset:0,color:'#8fc0e2'},{offset:1,color:'#1f4e79'}])},
      label:{show:true,position:'right',color:'#43607d',fontSize:11,
        formatter:p=>N(p.value/10000)+'万'},
      data:arr.map(a=>a[1].loss).reverse()
    }]
  },true);
}

function renderType(){
  const el=document.getElementById('typeChart');
  if(!typeChart) typeChart=echarts.init(el);
  const agg={};
  confirmedRows().forEach(e=>{agg[e.event_type]=(agg[e.event_type]||0)+(e.loss_t||0);});
  const data=Object.entries(agg).map(([k,v])=>({name:k,value:v,
    itemStyle:{color:TYPE_COLOR[k]||'#2f7fb8'}}));
  typeChart.setOption({
    tooltip:{trigger:'item',borderWidth:0,backgroundColor:'rgba(15,46,76,.95)',
      textStyle:{color:'#eaf3fb',fontSize:12.5},
      formatter:p=>`<b>${p.name}</b><br>${N(p.value)} 吨（${p.percent}%）`},
    legend:{bottom:4,itemWidth:11,itemHeight:11,textStyle:{color:'#43607d',fontSize:12}},
    series:[{
      type:'pie',radius:['44%','70%'],center:['50%','45%'],
      avoidLabelOverlap:true,
      itemStyle:{borderColor:'#fff',borderWidth:2.5,borderRadius:5},
      label:{color:'#43607d',fontSize:11.5,formatter:p=>`${p.name}\n${N(p.value/10000)}万`},
      labelLine:{lineStyle:{color:'#cfdce8'}},
      data
    }]
  },true);
}

function renderRoute(){
  const el=document.getElementById('routeChart');
  if(!routeChart) routeChart=echarts.init(el);
  const agg={};
  confirmedRows().forEach(e=>{
    const k=ROUTE_CN[e.route]||e.route||'未披露';
    agg[k]=agg[k]||{loss:0,n:0,cap:0};
    agg[k].loss+=e.loss_t||0; agg[k].n++; agg[k].cap+=Number(e.capacity_wt)||0;
  });
  const arr=Object.entries(agg).sort((a,b)=>b[1].loss-a[1].loss);
  routeChart.setOption({
    grid:{left:16,right:24,top:30,bottom:22,containLabel:true},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},borderWidth:0,
      backgroundColor:'rgba(15,46,76,.95)',textStyle:{color:'#eaf3fb',fontSize:12.5},
      formatter:p=>{const a=arr[p[0].dataIndex][1];
        return `<b>${p[0].name}</b><br>确认减产 ${N(a.loss)} 吨<br>事件 ${a.n} 起 · 涉及产能 ${N(a.cap)} 万吨/年`;}},
    xAxis:{type:'category',data:arr.map(a=>a[0]),
      axisLabel:{color:'#43607d',fontSize:11.5},axisTick:{show:false},
      axisLine:{lineStyle:{color:'#cfdce8'}}},
    yAxis:{type:'value',axisLabel:{color:'#7b93aa',fontSize:11,formatter:v=>N(v/10000)+'万'},
      splitLine:{lineStyle:{color:'#eef3f8'}},axisLine:{show:false}},
    series:[{
      type:'bar',barWidth:'46%',
      itemStyle:{borderRadius:[5,5,0,0],
        color:new echarts.graphic.LinearGradient(0,0,0,1,
          [{offset:0,color:'#5aa6d6'},{offset:1,color:'#1f4e79'}])},
      label:{show:true,position:'top',color:'#43607d',fontSize:11,
        formatter:p=>N(p.value/10000)+'万'},
      data:arr.map(a=>a[1].loss)
    }]
  },true);
}

/* ---------- table ---------- */
function filtered(){
  let rows=DATA.events;
  if(FILT.status==='confirmed') rows=rows.filter(e=>e.bucket==='domestic_confirmed');
  else if(FILT.status==='overseas') rows=rows.filter(e=>e.bucket==='overseas');
  else if(FILT.status==='unconfirmed') rows=rows.filter(e=>e.bucket==='unconfirmed'||e.bucket==='stock_stop');
  if(FILT.type) rows=rows.filter(e=>e.event_type===FILT.type);
  if(FILT.region) rows=rows.filter(e=>e.region_code===FILT.region);
  if(FILT.route) rows=rows.filter(e=>e.route===FILT.route);
  if(FILT.company) rows=rows.filter(e=>e.company===FILT.company);
  if(FILT.q){
    const q=FILT.q.toLowerCase();
    rows=rows.filter(e=>[e.company,e.unit_name,e.province,e.event_family,e.status_latest]
      .some(v=>String(v||'').toLowerCase().includes(q)));
  }
  return rows.sort((a,b)=>(b.loss_t||0)-(a.loss_t||0));
}

function renderTable(){
  const rows=filtered();
  const max=Math.max(1,...rows.map(e=>e.loss_t||0));
  const tb=document.querySelector('#mainTbl tbody');
  tb.innerHTML=rows.map(e=>{
    const b=BUCKET[e.bucket]||{cn:e.bucket,cls:'b-info'};
    const w=Math.max(2,((e.loss_t||0)/max)*100);
    const conf=e.confidence==='official'?'<span class="badge b-ok">官方</span>'
      :e.confidence==='industry'?'<span class="badge b-info">行业</span>'
      :'<span class="badge b-warn">待核</span>';
    return `<tr data-id="${e.event_id}">
      <td class="mini">${e.event_id}</td>
      <td><b>${e.company}</b></td>
      <td class="mini">${e.unit_name}</td>
      <td><span class="badge" style="background:${(TYPE_COLOR[e.event_type]||'#2f7fb8')}1a;color:${TYPE_COLOR[e.event_type]||'#2f7fb8'}">${e.event_type}</span></td>
      <td class="mini">${ROUTE_CN[e.route]||e.route||'—'}</td>
      <td class="mini">${REGION_CN[e.region_code]||e.region_code}</td>
      <td class="num">${N(e.capacity_wt)}</td>
      <td class="mini">${fdate(e.start_date)}<br>→ ${e.end_date||'进行中'}</td>
      <td class="num">${e.days==null?'—':e.days}</td>
      <td class="num"><b style="color:${(e.loss_t||0)>0?'#c94a4a':'#7b93aa'}">${e.loss_t==null?'不计':N(e.loss_t)}</b></td>
      <td style="min-width:70px"><div class="bar"><i style="width:${w}%"></i></div></td>
      <td><span class="badge ${b.cls}">${e.status_latest||'—'}</span></td>
      <td>${conf}${e.source_count>1?`<span class="mini"> ${e.source_count}源</span>`:''}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="13" style="text-align:center;color:#7b93aa;padding:26px">没有匹配的事件</td></tr>';
  document.getElementById('rowCount').textContent=`${rows.length} 条`;
  [...tb.querySelectorAll('tr[data-id]')].forEach(tr=>{
    tr.onclick=()=>openDrawer(tr.dataset.id);
  });
}

function renderPlan(){
  const tb=document.querySelector('#planTbl tbody');
  tb.innerHTML=DATA.planned.map(p=>{
    const conf=p.confidence==='official'?'<span class="badge b-ok">官方</span>'
      :p.confidence==='industry'?'<span class="badge b-info">行业</span>'
      :'<span class="badge b-warn">待核</span>';
    return `<tr data-plan="${p.plan_id}" style="cursor:pointer">
      <td class="mini">${p.plan_id}</td>
      <td><b>${p.company}</b></td>
      <td class="mini">${p.unit_name}</td>
      <td><span class="badge b-plan">${p.event_type}</span></td>
      <td class="num">${N(p.capacity_wt)}</td>
      <td class="mini">${p.planned_date||'—'}<br><span style="color:#7b93aa">${p.planned_window||''}</span></td>
      <td class="mini">${p.disclosure_type||'—'}</td>
      <td class="mini">${p.status_note||''}</td>
      <td>${conf}</td>
      <td class="mini">${(p.sources||[]).map(s=>`<a href="${s.url}" target="_blank" rel="noopener">${s.name}</a> <span style="color:#7b93aa">${s.date}</span>`).join('<br>')}</td>
    </tr>`;
  }).join('');
}

/* ---------- drawer ---------- */
const mask=document.getElementById('mask'), drawer=document.getElementById('drawer');
document.getElementById('dClose').onclick=closeDrawer;
mask.onclick=closeDrawer;
function closeDrawer(){drawer.classList.remove('on');mask.classList.remove('on');}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer();});

function openDrawer(id){
  const e=DATA.events.find(x=>x.event_id===id); if(!e) return;
  const b=BUCKET[e.bucket]||{cn:e.bucket,cls:'b-info'};
  document.getElementById('dTitle').innerHTML=`${e.company} · ${e.unit_name}`;
  document.getElementById('dSub').innerHTML=
    `<span class="badge ${b.cls}">${b.cn}</span>
     <span class="chip">${e.event_type}</span>
     <span class="chip">${ROUTE_CN[e.route]||e.route}</span>
     <span class="chip">${REGION_CN[e.region_code]||e.region_code}</span>
     <span class="chip">${e.confidence==='official'?'官方来源':e.confidence==='industry'?'行业资讯':'待核/传闻'}</span>`;

  const lossLine = e.formula
    ? `<div class="formula">${e.formula.replace(/=/g,'<b>=</b>')}<br>
       <span style="opacity:.8">⇒ 理论减产量 = ${N(e.loss_t)} 吨（${(e.loss_t/10000).toFixed(2)} 万吨）；全停上限 ${N(e.loss_upper_t)} 吨</span></div>`
    : `<div class="formula" style="opacity:.85">本事件不计算减产量：${e.formula===null?'缺少负荷参数或产能':(e.reason||'属于状态确认/复产事件，可恢复供应已在对应停车事件中体现')}</div>`;

  document.getElementById('dBody').innerHTML=`
    <dl class="kv">
      <dt>事件ID</dt><dd>${e.event_id}　<span class="mini">去重键：${e.event_family||'—'}</span></dd>
      <dt>生产基地</dt><dd>${e.site||'—'}（${e.province||'—'}）</dd>
      <dt>装置产能</dt><dd>${N(e.capacity_wt)} 万吨/年　<span class="mini">日基准 ${N(e.daily_t)} 吨/日</span></dd>
      <dt>起止时间</dt><dd>${e.start_date||'—'} → ${e.end_date||'进行中/未定'}　<span class="mini">窗口内 ${e.days==null?'—':e.days} 天</span></dd>
      <dt>事件期负荷</dt><dd>${e.downtime_load==null?'未知':(e.downtime_load*100).toFixed(0)+'%'}${e.assumed?' <span class="badge b-warn">假设值</span>':''}</dd>
      <dt>最新状态</dt><dd><span class="badge ${b.cls}">${e.status_latest||'—'}</span></dd>
      <dt>状态说明</dt><dd>${e.status_note||'—'}</dd>
      <dt>数据置信度</dt><dd>${e.confidence==='official'?'官方':e.confidence==='industry'?'行业资讯（专业机构）':'待核/传闻'}　<span class="mini">${e.source_count} 个来源印证</span></dd>
    </dl>
    <div class="sec">理论影响量计算</div>
    ${lossLine}
    ${e.load_note?`<p class="mini" style="margin-top:7px">负荷假设说明：${e.load_note}</p>`:''}
    ${e.conflict&&e.conflict!=='无'?`<div class="note"><b>口径冲突/不确定性：</b>${e.conflict}</div>`:''}
    ${e.dedupe_check?`<div class="sec">去重核对</div><p class="mini">${e.dedupe_check}</p>`:''}
    <div class="sec">来源与证据链（${(e.sources||[]).length}）</div>
    ${(e.sources||[]).map(s=>`<div class="src">
        <span class="sn">${s.name}</span><span class="sd">${s.date}</span>
        <div class="sq">“${s.quote}”</div>
        <div style="margin-top:5px"><a href="${s.url}" target="_blank" rel="noopener">${s.url}</a></div>
      </div>`).join('') || '<p class="mini">无来源记录</p>'}
    ${e.bucket==='unconfirmed'?`<div class="note"><b>未计入确认合计：</b>该事件来源不足、缺少负荷或起止信息，或属传闻级信息，仅作登记，不进入任何确认影响量汇总。</div>`:''}
  `;
  drawer.classList.add('on'); mask.classList.add('on');
}

/* ---------- wiring ---------- */
document.getElementById('scopeSeg').onclick=ev=>{
  const b=ev.target.closest('button'); if(!b) return;
  [...ev.currentTarget.children].forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); SCOPE=b.dataset.scope;
  renderTimeline(); renderRank(); renderRegion(); renderType(); renderRoute();
};
document.getElementById('fStatus').onchange=ev=>{FILT.status=ev.target.value;renderTable();};
document.getElementById('fType').onchange=ev=>{FILT.type=ev.target.value;renderTable();};
document.getElementById('fRegion').onchange=ev=>{FILT.region=ev.target.value;renderTable();};
document.getElementById('fRoute').onchange=ev=>{FILT.route=ev.target.value;renderTable();};
document.getElementById('fCompany').onchange=ev=>{FILT.company=ev.target.value;renderTable();};
document.getElementById('fSearch').oninput=ev=>{FILT.q=ev.target.value.trim();renderTable();};

renderTimeline(); renderRank(); renderRegion(); renderType(); renderRoute();
renderTable(); renderPlan();
window.addEventListener('resize',()=>{
  [tlChart,rankChart,regionChart,typeChart,routeChart].forEach(c=>c&&c.resize());
});
</script>
</body>
</html>
"""


def build(case_dir, out_html, title, echarts_path=None):
    payload = build_payload(case_dir)
    echarts = ''
    ep = echarts_path or os.path.join(ASSETS, 'echarts.min.js')
    if os.path.exists(ep):
        with open(ep, encoding='utf-8') as f:
            echarts = f.read()
    else:  # 兜底：CDN
        echarts = ''
    data_js = json.dumps(payload, ensure_ascii=False)
    data_js = data_js.replace('</', '<\\/')
    html = (HTML
            .replace('__ECHARTS__', echarts)
            .replace('__DATA__', data_js)
            .replace('__TITLE__', title)
            .replace('__WIN_START__', payload['meta']['window_start'])
            .replace('__WIN_END__', payload['meta']['window_end'])
            .replace('__AS_OF__', payload['meta']['as_of'])
            .replace('__GEN_TIME__', __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')))
    os.makedirs(os.path.dirname(out_html), exist_ok=True)
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_html, payload


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    case = os.environ.get('CASE_DIR') or os.path.join(root, 'case')
    out = os.environ.get('OUT_HTML') or os.path.join(case, 'out', '甲醇供给事件时间线报告.html')
    title = os.environ.get('REPORT_TITLE') or '看供给端最近发生了什么 · 甲醇生产装置供给事件时间线'
    p, payload = build(case, out, title)
    print('written:', p, os.path.getsize(p), 'bytes')
    print('events:', len(payload['events']), 'planned:', len(payload['planned']))

