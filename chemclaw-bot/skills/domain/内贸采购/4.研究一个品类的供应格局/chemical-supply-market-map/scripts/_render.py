#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_render.py —— 模板片段生成器（把 data bundle 变成 HTML 片段）

build_all.py 先用本模块把 @@TOKEN@@ 全部算好，模板里不允许出现任何产品特定文字。
"""
import html as H
import json

import _common as C

MISSING = C.MISSING


def esc(text):
    return H.escape(str(text if text is not None else ""), quote=True)


def pct(v, digits=1):
    v = C.num(v)
    return f"{v:.{digits}f}%"


def num(v, digits=0):
    if v is None or v == MISSING:
        return MISSING
    return C.fmt_num(v, digits)


def sgn(v):
    """带符号的整数；None 显示「待确认」。"""
    if v is None:
        return "待确认"
    return f"{C.num(v):+,.0f}"


def tag(text, cls="neutral"):
    return f'<span class="chip chip-{cls}">{esc(text)}</span>'


CONF_CLS = {"高": "good", "中高": "good", "中": "warn", "中低": "risk", "低": "risk"}


# ------------------------------------------------------------------ 品牌与抬头
def brand_mark(product):
    cas = str(product.get("cas") or "").strip()
    if cas:
        return cas
    name = str(product.get("short") or product.get("name") or "")
    return name[:6] or "供应全景"


def masthead(bundle, excel_name):
    meta = bundle["meta"]
    product, scope, metrics = meta["product"], meta["scope"], meta["metrics"]
    short = product.get("short") or product.get("name")
    year = scope.get("base_year") or ""
    fwd = scope.get("forward_years") or []
    fwd_label = f"{fwd[0]}E" if fwd else "预测年"
    unit = product.get("unit") or "万吨/年"
    price_unit = product.get("price_unit") or "元/吨"

    kpis = []
    if metrics.get("capacity_total"):
        subs = [f"{esc(metrics.get('capacity_total_label') or '全国产能')}"]
        if metrics.get("capacity_total_note"):
            subs.append(esc(metrics["capacity_total_note"]))
        delta = ""
        if metrics.get("capacity_forward"):
            delta = f'{esc(metrics.get("capacity_forward_label") or fwd_label)} {num(metrics["capacity_forward"])}'
        kpis.append(("全国产能", num(metrics["capacity_total"]), unit, "<br>".join(subs), delta, ""))
    if metrics.get("output"):
        subs = []
        if metrics.get("utilization") is not None:
            subs.append(f"开工率 {C.fmt_num(metrics['utilization'], 1)}%")
        if metrics.get("output_alt"):
            alts = "；".join(f"{a.get('label')} {C.fmt_num(a.get('value'))}"
                            for a in metrics["output_alt"] if isinstance(a, dict))
            if alts:
                subs.append(esc(alts))
        kpis.append(("产量", num(metrics["output"]), unit, "<br>".join(subs) or MISSING,
                     f"出口 {num(metrics['export'])}" if metrics.get("export") else "", ""))
    if metrics.get("cr5"):
        top = "、".join(c["name"] for c in bundle["companies"][:5])
        tot = sum(c["capacity_base"] for c in bundle["companies"][:5])
        fwd_cr = metrics.get("cr5_forward") or {}
        delta = (f"{fwd_label} {fwd_cr.get('low', MISSING)}–{fwd_cr.get('high', MISSING)}%"
                 if isinstance(fwd_cr, dict) and fwd_cr.get("low") else "")
        kpis.append(("CR5", num(metrics["cr5"], 1), "%",
                     f"{esc(top)}<br>合计 {num(tot)} {esc(unit)}", delta, ""))
    routes = bundle["routes"]
    if len(routes) >= 2:
        lead = routes[0]
        kpis.append((f"{esc(lead.get('name'))}占比", num(lead.get("share"), 1), "%",
                     f"产能 {num(lead.get('cap'))} {esc(unit)}<br>主要路线",
                     f"{len(routes)} 条工艺路线", ""))
    if metrics.get("price_now"):
        delta_cls = ""
        if metrics.get("drawdown"):
            delta_cls = "red" if C.num(metrics["drawdown"]) > 40 else "warn"
            delta = f"较峰值 -{C.fmt_num(metrics['drawdown'], 0)}%"
        else:
            delta = ""
        cur = bundle["prices"].get("current") or []
        subs = [esc(metrics.get("price_now_label") or "当前价")]
        if len(cur) > 1:
            subs.append(" / ".join(f"{esc(x.get('label'))} {C.fmt_num(x.get('value'))}" for x in cur[1:3]))
        kpis.append(("当前价格", num(metrics["price_now"]), price_unit, "<br>".join(subs), delta, delta_cls))
    if metrics.get("sample_coverage") not in (None, MISSING):
        kpis.append(("样本覆盖", num(metrics["sample_coverage"], 1), "%",
                     f"{metrics.get('sample_groups')} 集团 / {metrics.get('sample_sites')} 基地<br>"
                     f"合计 {num(metrics.get('sample_capacity'))} {esc(unit)}",
                     "未披露企业为数据缺口", "warn"))

    out = [f'''<div class="masthead">
  <div class="wrap mast-inner">
    <div class="brand">
      <div class="brand-mark">{esc(brand_mark(product))}</div>
      <div>
        <div class="eyebrow">PROCUREMENT MARKET INTELLIGENCE · {esc(year) or '—'}</div>
        <h1>{esc(short)} · {esc(scope.get('geography') or '')}供应市场全景</h1>
        <p class="sub">从「哪里产、谁能供、什么成本、未来怎么变」四个问题出发，把公开产能、区域结构、工艺路线、项目投产与价格周期放在同一张采购地图上。所有产能均标注口径；缺失数据明确标记，不做估算。</p>
      </div>
    </div>
    <div class="mast-actions">
      <a class="btn ghost" href="#tab-method"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19V5M4 19h16M8 15l4-5 3 3 5-7"/></svg>数据口径</a>
      <a class="btn solid" href="{esc(excel_name)}" download><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16"/></svg>下载 Excel 数据包</a>
    </div>
  </div>
  <div class="wrap kpi-grid">''']
    for label, val, unit_txt, sub, delta, cls in kpis:
        delta_html = f'<div class="k-delta {cls}">{delta}</div>' if delta else ""
        out.append(f'''    <div class="kpi">
      <div class="k-label">{esc(label)}</div>
      <div class="k-val">{val}<small>{esc(unit_txt)}</small></div>
      <div class="k-sub">{sub}</div>
      {delta_html}
    </div>''')
    out.append('''  </div>
  <div class="wrap mast-note">
    <div>数据截止 <b>''' + esc(scope.get("data_cutoff") or MISSING) + '''</b> · 产能单位 <b>''' + esc(unit) +
               '''</b> · 价格单位 <b>''' + esc(price_unit) + '''</b> · 覆盖 <b>''' +
               esc(scope.get("geography") or MISSING) + '''</b></div>
    <div>口径提示：名义产能 / 有效产能 / 样本合计 / 集团合并口径分别标注，详见「数据与来源」</div>
  </div>
</div>''')
    return "\n".join(out)


# ------------------------------------------------------------------ 全景
def overview(bundle):
    meta = bundle["meta"]
    product, scope, metrics = meta["product"], meta["scope"], meta["metrics"]
    unit = product.get("unit") or "万吨/年"
    price_unit = product.get("price_unit") or "元/吨"
    year = scope.get("base_year") or ""
    fwd = scope.get("forward_years") or []
    fwd_label = f"{fwd[0]}E" if fwd else "预测年"
    routes = bundle["routes"]
    regions = bundle["regions"]
    top = bundle["companies"][:8]
    max_cap = max([c["capacity_forward"] for c in top] + [1])

    # 工艺环
    segs, acc = [], 0
    for rt in routes:
        share = C.num(rt.get("share"))
        if not share and metrics.get("capacity_total"):
            share = C.num(rt.get("cap")) / C.num(metrics["capacity_total"]) * 100
        segs.append(f'<circle class="donut-seg" data-route="{esc(rt.get("name"))}" r="54" cx="70" cy="70" '
                    f'fill="none" stroke="{esc(rt.get("color") or "#0f766e")}" stroke-width="22" '
                    f'stroke-dasharray="{max(share, 0.4):.2f} {100 - max(share, 0.4):.2f}" '
                    f'stroke-dashoffset="{-acc:.2f}" pathLength="100"><title>{esc(rt.get("name"))} {share:.1f}%</title></circle>')
        acc += share
    legend = "".join(
        f'<div class="lg-row"><i style="background:{esc(rt.get("color") or "#0f766e")}"></i>'
        f'<span class="nm">{esc(rt.get("name"))}</span>'
        f'<span class="v">{num(rt.get("cap"))} · {pct(C.num(rt.get("share")) if rt.get("share") else (C.num(rt.get("cap")) / max(C.num(metrics.get("capacity_total")), 1) * 100))}</span></div>'
        for rt in routes) or '<div class="tiny muted">未配置 routes</div>'

    # 区域条
    reg_max = max([r["capacity_base"] for r in regions] + [1])
    reg_bars = "".join(
        f'<div class="hb-row" data-province="{esc(r["province"])}">'
        f'<div class="nm">{esc(r["province"])}</div>'
        f'<div class="bar"><i style="width:{r["capacity_base"] / reg_max * 100:.1f}%"></i></div>'
        f'<div class="v">{num(r["capacity_base"])}</div></div>' for r in regions[:10]) \
        or '<div class="tiny muted">plants.json 为空</div>'

    # 头部集团
    head_rows = "".join(
        f'<div class="hb-row co-row" data-company="{esc(c["id"])}" role="button" tabindex="0">'
        f'<div class="nm">{esc(c["name"])}</div>'
        f'<div class="bar"><i style="width:{c["capacity_base"] / max_cap * 100:.1f}%"></i></div>'
        f'<div class="v">{num(c["capacity_base"])}</div></div>' for c in top) \
        or '<div class="tiny muted">companies.json 为空</div>'

    # 成本带
    cost_rows = ""
    costs = [r for r in routes if r.get("cost_low") is not None and r.get("cost_high") is not None]
    if costs:
        lo_all = min(C.num(r["cost_low"]) for r in costs)
        hi_all = max(C.num(r["cost_high"]) for r in costs)
        span = max(hi_all - lo_all, 1)
        price_now = C.num(metrics.get("price_now"))
        for rt in sorted(costs, key=lambda x: C.num(x["cost_low"])):
            lo, hi = C.num(rt["cost_low"]), C.num(rt["cost_high"])
            left = (lo - lo_all) / span * 100
            width = max((hi - lo) / span * 100, 2)
            pos = "高于区间" if price_now >= hi else ("区间内" if price_now >= lo else "低于成本")
            cost_rows += (f'<div class="cost-row"><div class="nm">{esc(rt.get("name"))}</div>'
                          f'<div class="bar"><i style="left:{left:.1f}%;width:{width:.1f}%;'
                          f'background:linear-gradient(90deg,{esc(rt.get("color") or "#0f766e")},#fbbf24)"></i></div>'
                          f'<div class="val"><b>{num(lo)}–{num(hi)}</b><br>{esc(pos)}</div></div>')
        cost_note = (f'当前价 <b>{num(price_now)} {esc(price_unit)}</b>；'
                     f'成本区间为公开报道/行业研究的行业经验值，不同基地差异很大，'
                     f'不能直接用于结算或成本审计。')
    else:
        cost_rows = '<div class="tiny muted">未配置 routes.cost_low / cost_high</div>'
        cost_note = "补充 routes 的成本区间后，这里会显示成本曲线与当前价位置。"

    summary = ""
    if bundle["verdicts"]:
        v = bundle["verdicts"][0]
        summary = (f'{esc(bundle["meta"]["product"].get("short"))}的核心矛盾：{esc(v.get("title"))}。'
                   f'{esc(v.get("implication"))}')

    return f'''    <div class="section">
      <div class="section-head">
        <div>
          <div class="kicker">ONE-PAGE VIEW</div>
          <h2>一页看懂：供给、区域与成本</h2>
          <p>{summary or '先看总量与集中度，再看区域与成本；采购风险往往不在总量，而在可替代性与到厂经济性。'}</p>
        </div>
        <div class="side">{esc(year)} 基准年 · {esc(fwd_label)} 前瞻</div>
      </div>

      <div class="grid-3">
        <div class="card card-pad">
          <div class="card-head"><h3>工艺结构</h3><span class="hint">{esc(year)} · {esc(unit)}</span></div>
          <div class="route-wrap">
            <svg class="donut" viewBox="0 0 140 140" role="img" aria-label="工艺结构">
              <circle r="54" cx="70" cy="70" fill="none" stroke="#eef3f8" stroke-width="22"></circle>
              <g transform="rotate(-90 70 70)">{segs and "".join(segs)}</g>
            </svg>
            <div class="donut-center"><b>{num(metrics.get("capacity_total"))}</b><span>{esc(unit)}</span></div>
          </div>
          <div class="legend-list">{legend}</div>
          {f'<div class="tiny muted" style="margin:-2px 0 8px;font-size:9.5px">注：{esc(meta.get("routes_note"))}</div>' if meta.get("routes_note") else ""}
        </div>

        <div class="card card-pad">
          <div class="card-head"><h3>区域结构</h3><span class="hint">样本口径 · {esc(year)}</span></div>
          <div class="hb-list">{reg_bars}</div>
          <div class="cost-note">样本 {meta["metrics"].get("sample_groups")} 集团 / {meta["metrics"].get("sample_sites")} 基地合计
            <b>{num(metrics.get("sample_capacity"))} {esc(unit)}</b>，占全国 <b>{metrics.get("sample_coverage")}%</b>。
            前 4 省合计 {pct(metrics.get("top4_region_share"))}、前 5 省 {pct(metrics.get("top5_region_share"))}，
            区域 HHI {metrics.get("hhi_region")}。</div>
        </div>

        <div class="card card-pad">
          <div class="card-head"><h3>成本曲线</h3><span class="hint">{esc(price_unit)} · 行业经验值</span></div>
          <div class="cost-list">{cost_rows}</div>
          <div class="cost-note">{cost_note}</div>
        </div>
      </div>

      <div class="card card-pad" style="margin-top:18px">
        <div class="card-head" style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px">
          <div><h3>头部集团：{esc(year)} vs {esc(fwd_label)}</h3>
            <div class="hint" style="margin-top:2px">按 {esc(year)} 产能排序；点击条形查看企业尽调卡</div></div>
          <div class="legend"><span><i style="background:#0f766e"></i>{esc(year)}</span><span><i style="background:#93c5fd"></i>{esc(fwd_label)}</span></div>
        </div>
        <div class="hb-list wide">{head_rows}</div>
        <div class="tiny muted" style="margin-top:6px">注：{esc(fwd_label)} 为集团口径毛产能，含搬迁/置换项目的名义产能；毛产能不等于净新增，详见「项目时间线」的净增还原。</div>
      </div>
    </div>

    <div class="section">
      <div class="section-head">
        <div><div class="kicker">KEY JUDGMENTS</div><h2>核心结论</h2>
          <p>每条判断都带证据、采购含义与置信度；置信度「高」= 有年报/公告直接支撑。</p></div>
        <div class="side">{len(bundle["verdicts"])} 条</div>
      </div>
      <div class="conclusion-grid">''' + "".join(
        f'''<div class="conclusion-card"><div class="num">{i + 1:02d} / {esc(v.get("confidence", "中"))}</div>
          <h3>{esc(v.get("title"))}</h3><p>{esc(v.get("evidence"))}</p>
          <div class="tag">→ {esc(v.get("implication"))}</div></div>'''
        for i, v in enumerate(bundle["verdicts"])) + f'''</div>
    </div>'''


# ------------------------------------------------------------------ 企业表
def company_table(bundle):
    comps = bundle["companies"]
    rows = "".join(
        f'''<tr data-company="{esc(c["id"])}" class="co-row" tabindex="0">
          <td class="co">{esc(c["name"])}</td>
          <td class="mono">{esc(c.get("code") or "—")}</td>
          <td>{esc("、".join(c.get("provinces") or []) or MISSING)}</td>
          <td>{esc("、".join(c.get("routes") or []) or MISSING)}</td>
          <td class="mono n">{num(c["capacity_base"])}</td>
          <td class="mono n">{num(c["capacity_forward"])}</td>
          <td class="mono n">{pct(C.num(c.get("share_base")) * 100)}</td>
          <td class="mono n">{esc(C.fmt_num(c.get("output_base")) if c.get("output_base") not in (None, MISSING) else MISSING)}</td>
          <td class="mono n">{esc(C.fmt_num(c.get("utilization"), 1) if c.get("utilization") not in (None, MISSING) else MISSING)}</td>
        </tr>''' for c in comps) if comps else \
        '<tr><td colspan="9" class="empty">companies.json 为空</td></tr>'
    return f'''    <div class="section">
      <div class="section-head">
        <div><div class="kicker">PRODUCERS</div><h2>企业表：{len(comps)} 集团</h2>
          <p>点击任意一行查看企业画像与尽调卡。产能为集团合并口径；产量/开工率未披露的标「数据缺口」。</p></div>
        <div class="side">样本 {num(bundle["meta"]["metrics"].get("sample_capacity"))} {esc(bundle["meta"]["product"].get("unit") or "")}</div>
      </div>
      <div class="table-tools">
        <input id="coSearch" class="inp" type="search" placeholder="搜索企业 / 省份 / 工艺…" aria-label="搜索企业">
        <select id="coSort" class="sel" aria-label="排序">
          <option value="cap">按基准年产能</option>
          <option value="share">按份额</option>
          <option value="name">按名称</option>
        </select>
        <span class="tiny muted" id="coCount"></span>
      </div>
      <div class="table-wrap">
        <table class="tbl" id="companyTable">
          <thead><tr>
            <th>集团</th><th>代码</th><th>省份</th><th>工艺</th>
            <th class="n">基准年产能</th><th class="n">预测年产能</th><th class="n">份额</th>
            <th class="n">产量</th><th class="n">开工率 %</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      <div class="tiny muted" style="margin-top:10px">份额 = 集团产能 / 样本合计产能（非全国份额）。CR5 与 HHI 用同一口径计算，见「数据与来源」。</div>
    </div>'''


# ------------------------------------------------------------------ 项目时间线
def projects(bundle):
    rows = bundle["projects"]
    lane_order = []
    for p in rows:
        key = str(p.get("date") or "")[:4] or "待定"
        if key not in lane_order:
            lane_order.append(key)
    lane_order.sort()
    # 按年分组
    groups = []
    for lane in lane_order:
        items = [p for p in rows if (str(p.get("date") or "")[:4] or "待定") == lane]
        groups.append((lane, items))

    grid = ""
    max_cap = max([p["capacity"] for p in rows] + [1])
    for lane, items in groups:
        cells = []
        for p in items:
            w = max(p["capacity"] / max_cap * 100, 12)
            net = p["net_label"]
            net_cls = "risk" if net.startswith("-") else ("good" if net.startswith("+") else "warn")
            cells.append(f'''<div class="prj" data-project="{esc(p["id"])}" role="button" tabindex="0">
              <div class="prj-h"><b>{esc(p["name"])}</b><span class="mono">{num(p["capacity"])}</span></div>
              <div class="prj-bar"><i style="width:{w:.0f}%"></i></div>
              <div class="prj-meta"><span>{esc(p.get("company_id") or "")}</span>
                {tag(p.get("status") or MISSING, "neutral")} {tag("净 " + net, net_cls)}</div>
            </div>''')
        grid += f'<div class="prj-year"><div class="prj-year-h">{esc(lane)}</div><div class="prj-year-body">{"".join(cells)}</div></div>'

    total_gross = sum(p["capacity"] for p in rows)
    total_net = sum(p["net"] for p in rows if p["net"] is not None)
    pending = [p["name"] for p in rows if p["net"] is None]
    return f'''    <div class="section">
      <div class="section-head">
        <div><div class="kicker">PIPELINE</div><h2>项目时间线：{len(rows)} 个项目</h2>
          <p>点击项目查看净增还原。毛产能 ≠ 净新增：置换、搬迁、待确认的项目都不按名义产能计入供应规划。</p></div>
        <div class="side">毛 {num(total_gross)} · 净 {sgn(total_net)}</div>
      </div>
      <div class="timeline">{grid or '<div class="empty">projects.json 为空</div>'}</div>
      <div class="kpi-strip">
        <div><b>{num(total_gross)}</b><span>毛产能合计</span></div>
        <div><b>{sgn(total_net)}</b><span>净影响（可确认项）</span></div>
        <div><b>{len(pending)}</b><span>净增待确认</span></div>
        <div><b>{len(lane_order)}</b><span>时间分组</span></div>
      </div>
      {f'<div class="tiny muted" style="margin-top:8px">待确认项目：{esc("、".join(pending))}。这些项目只在上行情景中体现，不进入基准预测。</div>' if pending else ""}
    </div>'''


# ------------------------------------------------------------------ 价格
def price(bundle):
    prices = bundle["prices"]
    annual = prices.get("annual") or []
    periods = prices.get("periods") or []
    current = prices.get("current") or []
    markets = bundle.get("markets") or []
    unit = bundle["meta"]["product"].get("price_unit") or "元/吨"

    vals = [(a.get("year"), a.get("avg"), a.get("low"), a.get("high")) for a in annual]
    svg = ""
    if vals:
        ys = [C.num(v[1]) if v[1] is not None else C.num(v[3]) for v in vals]
        hi = max(ys + [1])
        lo = min([y for y in ys if y > 0] + [0])
        W, Hh, pad = 640, 240, 36
        n = len(vals)
        step = (W - pad * 2) / max(n - 1, 1)
        pts = []
        for i, (yy, avg, low, high) in enumerate(vals):
            yv = C.num(avg) if avg is not None else C.num(high)
            x = pad + i * step
            y = Hh - pad - (yv - lo) / max(hi - lo, 1) * (Hh - pad * 2)
            pts.append((x, y, yy, yv))
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts)
        markers = "".join(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#0f766e"></circle>'
            f'<text x="{x:.1f}" y="{y - 10:.1f}" class="pt">{num(yv)}</text>'
            f'<text x="{x:.1f}" y="{Hh - 12}" class="px">{esc(yy)}</text>' for x, y, yy, yv in pts)
        svg = (f'<svg class="chart" viewBox="0 0 {W} {Hh}" role="img" aria-label="年度价格">'
               f'<polyline points="{poly}" fill="none" stroke="#0f766e" stroke-width="2.5"></polyline>'
               f'{markers}</svg>')

    cur_html = "".join(f'<div class="mk"><b>{num(c.get("value"))}</b>'
                       f'<span>{esc(c.get("label"))}<br>{esc(c.get("date") or "")}</span></div>'
                       for c in current) or '<div class="tiny muted">未配置 prices.current</div>'
    mkt_html = "".join(f'<div class="mk"><b>{num(m.get("price"))}</b>'
                       f'<span>{esc(m.get("region"))}<br>{esc(m.get("note") or "")}</span></div>'
                       for m in markets) or ""
    period_rows = "".join(
        f'<tr><td class="co">{esc(p.get("period"))}</td><td class="mono">{esc(p.get("time"))}</td>'
        f'<td>{esc(p.get("light") or "—")}</td><td>{esc(p.get("heavy") or "—")}</td>'
        f'<td class="mono">{esc(p.get("change") or "—")}</td><td>{esc(p.get("driver") or "")}</td>'
        f'<td class="mono tiny">{esc(p.get("source") or "")}</td></tr>' for p in periods) or \
        '<tr><td colspan="7" class="empty">未配置 prices.periods</td></tr>'

    outlook = prices.get("outlook") or {}
    out_html = "".join(
        f'<div class="oc"><div class="oc-h">{esc(k)}</div><p>{esc(v)}</p></div>'
        for k, v in [("基准情景", outlook.get("base")), ("上行条件", outlook.get("up")),
                     ("下行风险", outlook.get("down")), ("采购含义", outlook.get("procurement"))] if v) \
        or '<div class="empty">未配置 prices.outlook</div>'

    return f'''    <div class="section">
      <div class="section-head">
        <div><div class="kicker">PRICE</div><h2>价格：历史区间与当前位置</h2>
          <p>价格为公开报价（{esc(unit)}），年度均值用于判断周期位置，不作为结算依据。</p></div>
        <div class="side">{esc(prices.get("caveat") or "")[:0] or "周期位置 · 区域价差 · 情景"}</div>
      </div>
      <div class="grid-2">
        <div class="card card-pad">
          <div class="card-head"><h3>年度价格</h3><span class="hint">{esc(unit)}</span></div>
          {svg or '<div class="empty">未配置 prices.annual</div>'}
        </div>
        <div class="card card-pad">
          <div class="card-head"><h3>当前价位</h3><span class="hint">现货</span></div>
          <div class="mk-grid">{cur_html}</div>
          {f'<div class="card-head" style="margin-top:14px"><h3>区域价格</h3><span class="hint">主流报价</span></div><div class="mk-grid">{mkt_html}</div>' if mkt_html else ""}
        </div>
      </div>
      <div class="card card-pad" style="margin-top:18px">
        <div class="card-head"><h3>阶段复盘</h3><span class="hint">{len(periods)} 个阶段</span></div>
        <div class="table-wrap"><table class="tbl">
          <thead><tr><th>阶段</th><th>时间</th><th>主规格</th><th>副规格</th><th>涨跌</th><th>驱动</th><th>来源</th></tr></thead>
          <tbody>{period_rows}</tbody></table></div>
      </div>
      <div class="grid-2" style="margin-top:18px">{out_html}</div>
      {f'<div class="tiny muted" style="margin-top:12px">{esc(prices.get("caveat"))}</div>' if prices.get("caveat") else ""}
    </div>'''


# ------------------------------------------------------------------ 采购关注
def procurement(bundle):
    risks = bundle["risks"]
    strategies = bundle["strategies"]
    mix = bundle["supplier_mix"]
    metrics = bundle["meta"]["metrics"]
    buyer = bundle["meta"].get("buyer") or {}
    price_unit = bundle["meta"]["product"].get("price_unit") or "元/吨"

    risk_html = "".join(
        f'''<div class="risk" data-level="{esc(r.get("level") or "中")}">
          <div class="risk-h">{tag(r.get("level") or "中", CONF_CLS.get(r.get("level"), "warn"))}
            <b>{esc(r.get("risk"))}</b></div>
          <div class="risk-body"><div class="rl">证据</div><p>{esc(r.get("evidence") or MISSING)}</p>
            <div class="rl">动作</div><p>{esc(r.get("action") or MISSING)}</p></div>
        </div>''' for r in C.order_by_priority(risks, "level")) or '<div class="empty">未配置 risks</div>'

    strat_html = "".join(
        f'''<div class="stcard"><h4>{esc(s.get("title"))}</h4><p>{esc(s.get("how"))}</p>
          <div class="tiny"><b>条款</b> {esc(s.get("terms") or "—")}</div>
          <div class="tiny"><b>KPI</b> {esc(s.get("kpi") or "—")}</div></div>''' for s in strategies) or \
        '<div class="empty">未配置 strategies</div>'

    mix_bars = ""
    acc = 0
    for m in mix:
        w = C.num(m.get("share")) * 100
        mix_bars += (f'<div class="mix-row"><div class="nm">{esc(m.get("type"))}</div>'
                     f'<div class="bar"><i style="width:{w:.0f}%;background:{esc(m.get("color") or "#0f766e")}"></i></div>'
                     f'<div class="v mono">{w:.0f}%</div></div>')
    vol = C.num(buyer.get("volume_10kt"), 5)
    landed = C.num(buyer.get("landed_price"), C.num(metrics.get("price_now")))
    freight = C.num(buyer.get("freight"), 150)
    days = C.num(buyer.get("stock_days"), 30)
    amount = vol * 10000 * (landed + freight) / 10000
    return f'''    <div class="section">
      <div class="section-head">
        <div><div class="kicker">PROCUREMENT</div><h2>采购关注：{len(risks)} 项风险与应对</h2>
          <p>按风险等级排序。每项都给出可验证证据与可执行动作；不可执行的动作不写。</p></div>
        <div class="side">高 / 中高 / 中</div>
      </div>
      <div class="grid-2">{risk_html}</div>

      <div class="grid-2" style="margin-top:22px">
        <div class="card card-pad">
          <div class="card-head"><h3>采购策略</h3><span class="hint">{len(strategies)} 条</span></div>
          {strat_html}
        </div>
        <div class="card card-pad">
          <div class="card-head"><h3>建议供应商组合</h3><span class="hint">示例比例</span></div>
          <div class="mix-list">{mix_bars or '<div class="empty">未配置 supplier_mix</div>'}</div>
          <hr class="hr">
          <div class="card-head"><h3>采购量测算</h3><span class="hint">默认 5 万吨/年</span></div>
          <table class="sim">
            <tr><td>年采购量</td><td class="mono n">{num(vol)} 万吨</td></tr>
            <tr><td>到厂价</td><td class="mono n">{num(landed)} {esc(price_unit)}</td></tr>
            <tr><td>运费</td><td class="mono n">{num(freight)} {esc(price_unit)}</td></tr>
            <tr><td>安全库存天数</td><td class="mono n">{num(days)} 天</td></tr>
            <tr class="hl"><td>年度采购金额（含运费）</td><td class="mono n">{num(amount)} 万元</td></tr>
            <tr><td>月度提货量</td><td class="mono n">{num(vol * 10000 / 12)} 吨</td></tr>
            <tr><td>安全库存量</td><td class="mono n">{num(vol * 10000 * days / 365)} 吨</td></tr>
            <tr><td>价格每涨 100</td><td class="mono n">{num(vol * 100)} 万元/年</td></tr>
          </table>
          <div class="tiny muted" style="margin-top:8px">模拟为量级测算，未含增值税、资金占用、仓储、损耗与账期成本。Excel 里的「07A_采购策略」可直接改输入，自动重算。</div>
        </div>
      </div>
    </div>'''


# ------------------------------------------------------------------ 数据与来源
def method(bundle):
    meta = bundle["meta"]
    scope, metrics, product = meta["scope"], meta["metrics"], meta["product"]
    sources = bundle["sources"]
    gaps = bundle["gaps"]
    comps = bundle["companies"]

    route_cfg = {r.get("name"): r for r in bundle["routes"]}
    natural = bundle["routes"][0]["name"] if bundle["routes"] else "-"
    gap_rows = "".join(
        f'<tr><td>{esc(g.get("gap"))}</td><td>{esc(g.get("impact") or "")}</td>'
        f'<td>{esc(g.get("status") or "")}</td><td>{esc(g.get("fill") or "")}</td>'
        f'<td class="mono n">{esc(g.get("priority") or "")}</td></tr>'
        for g in C.order_by_priority(gaps, "priority")) or \
        '<tr><td colspan="5" class="empty">未配置 gaps</td></tr>'

    basis_rows = "".join(
        f'<tr><td>{esc(b)}</td></tr>' for b in (scope.get("basis_notes") or [])) or \
        '<tr><td class="empty">未填写 scope.basis_notes</td></tr>'

    def _link(s):
        url = str(s.get("url") or "")
        if url.startswith("http"):
            return f'<a href="{esc(url)}" target="_blank" rel="noopener">链接</a>'
        return '<span class="risk-text">无链接</span>'

    src_rows = "".join(
        f'<tr><td class="mono">{esc(s.get("id"))}</td><td>{esc(s.get("name"))}</td>'
        f'<td>{esc(s.get("publisher") or "")}</td><td class="mono">{esc(s.get("date") or "")}</td>'
        f'<td>{esc(s.get("used") or "")}</td>'
        f'<td>{_link(s)}</td>'
        f'<td class="mono n">{esc(s.get("confidence") or "")}</td></tr>' for s in sources) or \
        '<tr><td colspan="7" class="empty">sources 为空：所有数字都无法回溯</td></tr>'

    hhi_note = (f"集团 HHI ≈ {metrics.get('hhi_industry')}；"
                f"区域 HHI ≈ {metrics.get('hhi_region')}；CR5（样本口径）≈ {metrics.get('cr5_computed')}%。"
                if metrics.get("hhi_industry") not in (None, MISSING) else "")

    return f'''    <div class="section">
      <div class="section-head">
        <div><div class="kicker">METHOD & SOURCES</div><h2>数据与来源</h2>
          <p>口径、缺口与来源全部公开：任何数字都能回溯到一条公开披露；任何缺失都明确标注，不做估算。</p></div>
        <div class="side">{len(sources)} 条来源 · {len(gaps)} 项缺口</div>
      </div>

      <div class="grid-2">
        <div class="card card-pad">
          <div class="card-head"><h3>口径说明</h3><span class="hint">{esc(product.get("grades") or "")}</span></div>
          <table class="kv">
            <tr><td>覆盖范围</td><td>{esc(scope.get("geography") or MISSING)}</td></tr>
            <tr><td>统计边界</td><td>{esc(scope.get("boundary") or MISSING)}</td></tr>
            <tr><td>基准年 / 预测年</td><td>{esc(scope.get("base_year") or MISSING)} / {esc("、".join(str(y) for y in (scope.get("forward_years") or [])) or MISSING)}</td></tr>
            <tr><td>全国产能</td><td class="mono">{num(metrics.get("capacity_total"))} {esc(product.get("unit") or "")}</td></tr>
            <tr><td>样本覆盖</td><td class="mono">{metrics.get("sample_groups")} 集团 / {metrics.get("sample_sites")} 基地 / {num(metrics.get("sample_capacity"))} → {metrics.get("sample_coverage")}%</td></tr>
            <tr><td>集中度</td><td class="mono">{hhi_note or MISSING}</td></tr>
            <tr><td>数据截止</td><td class="mono">{esc(scope.get("data_cutoff") or MISSING)}</td></tr>
            <tr><td>生成方式</td><td>chemical-supply-market-map v{esc(meta.get("skill_version"))} · 生成于 {esc(meta.get("generated_at"))}</td></tr>
          </table>
        </div>
        <div class="card card-pad">
          <div class="card-head"><h3>口径提示</h3><span class="hint">{len(scope.get("basis_notes") or [])} 条</span></div>
          <table class="basis"><tbody>{basis_rows}</tbody></table>
        </div>
      </div>

      <div class="card card-pad" style="margin-top:18px">
        <div class="card-head"><h3>数据缺口</h3><span class="hint">不估算 · 不插值</span></div>
        <div class="table-wrap"><table class="tbl">
          <thead><tr><th>缺口</th><th>影响</th><th>当前状态</th><th>补齐方式</th><th class="n">优先级</th></tr></thead>
          <tbody>{gap_rows}</tbody></table></div>
      </div>

      <div class="card card-pad" style="margin-top:18px">
        <div class="card-head"><h3>来源列表</h3><span class="hint">{len(sources)} 条</span></div>
        <div class="table-wrap"><table class="tbl">
          <thead><tr><th>ID</th><th>名称</th><th>发布方</th><th>日期</th><th>用于</th><th>链接</th><th class="n">置信度</th></tr></thead>
          <tbody>{src_rows}</tbody></table></div>
      </div>

      <div class="card card-pad" style="margin-top:18px">
        <div class="card-head"><h3>使用限制</h3><span class="hint">必读</span></div>
        <ul class="limits">
          <li>公开信息研究，不含任何企业的非公开成本、合同价、库存与客户数据。</li>
          <li>产能为名义/设计能力，实际可用量受检修、环保、能耗、原料与订单影响。</li>
          <li>项目投产存在延期；净增以企业公告/产能置换文件为准，「待确认」项不进入基准预测。</li>
          <li>价格为公开报价，实际成交受批量、账期、运费与质量影响。</li>
          <li>本报告不构成投资建议；引用请注明数据截止日期与来源。</li>
        </ul>
      </div>
    </div>'''


# ------------------------------------------------------------------ 抽屉骨架
def drawers(bundle):
    comps = {c["id"]: c for c in bundle["companies"]}
    projects = {p["id"]: p for p in bundle["projects"]}
    plants_by_co = {}
    for p in bundle["plants"]:
        plants_by_co.setdefault(p["company_id"], []).append(p)
    dd = bundle["dd"]

    co_cards = []
    for cid, c in comps.items():
        sites = plants_by_co.get(cid, [])
        site_rows = "".join(
            f'<tr><td>{esc(s.get("site"))}</td><td>{esc(s.get("province"))}</td>'
            f'<td>{esc(s.get("route") or "—")}</td><td class="mono n">{num(s.get("capacity_base"))}</td>'
            f'<td class="mono n">{num(s.get("capacity_forward"))}</td><td>{esc(s.get("status"))}</td></tr>'
            for s in sites) or '<tr><td colspan="6" class="empty">无基地级明细</td></tr>'
        strengths = "".join(f"<li>{esc(x)}</li>" for x in (c.get("strengths") or [])) or "<li class='muted'>未记录</li>"
        risks = "".join(f"<li>{esc(x)}</li>" for x in (c.get("risks") or [])) or "<li class='muted'>未记录</li>"
        own_dd = "".join(f"<li>{esc(x)}</li>" for x in (c.get("dd") or []))
        generic = "".join(f"<li>{esc(q[1] if isinstance(q, (list, tuple)) and len(q) > 1 else q)}</li>"
                          for q in dd[:8])
        co_cards.append(f'''<div class="drawer-card" data-company="{esc(cid)}">
          <div class="dc-head"><div><div class="kicker">DUE DILIGENCE</div>
            <h3>{esc(c["name"])}</h3>
            <div class="tiny muted">{esc(c.get("code") or "未上市/未披露")} · {esc("、".join(c.get("provinces") or []) or MISSING)} · {esc("、".join(c.get("routes") or []) or MISSING)}</div></div>
            <div class="dc-kpi"><b>{num(c["capacity_base"])}</b><span>{esc(bundle["meta"]["product"].get("unit") or "")}</span></div></div>
          <div class="dc-grid">
            <div><div class="rl">产量</div><p>{esc(C.fmt_num(c.get("output_base")) if c.get("output_base") not in (None, MISSING) else MISSING)}</p></div>
            <div><div class="rl">开工率</div><p>{esc(C.fmt_num(c.get("utilization"), 1) if c.get("utilization") not in (None, MISSING) else MISSING)}</p></div>
            <div><div class="rl">样本份额</div><p>{pct(C.num(c.get("share_base")) * 100)}</p></div>
          </div>
          <div class="rl">基地明细</div>
          <div class="table-wrap"><table class="tbl sm"><thead><tr><th>基地</th><th>省份</th><th>工艺</th>
            <th class="n">基准年</th><th class="n">预测年</th><th>状态</th></tr></thead><tbody>{site_rows}</tbody></table></div>
          <div class="dc-cols">
            <div><div class="rl">优势</div><ul>{strengths}</ul></div>
            <div><div class="rl">风险</div><ul>{risks}</ul></div>
          </div>
          <div class="rl">采购判断</div><p>{esc(c.get("procurement") or "未记录：需补充尽调结论。")}</p>
          <div class="rl">尽调问题</div><ul class="dd">{(own_dd or generic) or "<li class='muted'>未配置 dd</li>"}</ul>
          <div class="tiny muted">来源：{esc("、".join(c.get("sources") or []) or "未核实")}</div>
        </div>''')

    prj_cards = []
    for pid, p in projects.items():
        prj_cards.append(f'''<div class="drawer-card" data-project="{esc(pid)}">
          <div class="dc-head"><div><div class="kicker">PROJECT</div><h3>{esc(p["name"])}</h3>
            <div class="tiny muted">{esc(p.get("company_id") or "")} · {esc(p.get("province") or "")} · {esc(p.get("route") or "")} · {esc(p.get("date") or "")}</div></div>
            <div class="dc-kpi"><b>{num(p["capacity"])}</b><span>毛产能</span></div></div>
          <table class="kv"><tr><td>项目类型</td><td>{esc(p.get("type") or MISSING)}</td></tr>
            <tr><td>状态</td><td>{esc(p.get("status") or MISSING)}</td></tr>
            <tr><td>置换 / 退出</td><td class="mono">{num(p["capacity_retired"])}</td></tr>
            <tr class="hl"><td>净影响</td><td class="mono">{esc(p["net_label"])}</td></tr>
            <tr><td>进度</td><td>{esc(p.get("step") or MISSING)}</td></tr>
            <tr><td>来源</td><td>{esc(p.get("source") or "未核实")}</td></tr></table>
          <div class="rl">对供给的影响</div><p>{esc(p.get("impact") or "未记录")}</p>
          <div class="tl-note">读法：毛产能不等于净新增。「待确认」的项目不纳入基准预测，只在上行情景中体现。</div>
        </div>''')

    return (f'<div class="drawer-inner" id="drawerCo">{"".join(co_cards)}'
            f'<div class="drawer-empty" id="drawerCoEmpty">点击企业表/头部集团条形/地图气泡查看企业画像与尽调卡。</div></div>'
            f'<div class="drawer-inner" id="drawerPrj" hidden>{"".join(prj_cards)}'
            f'<div class="drawer-empty" id="drawerPrjEmpty">点击项目时间线中的项目查看净增还原。</div></div>')


def footer(bundle):
    meta = bundle["meta"]
    return f'''<div class="foot-wrap">
    <div>
      <div style="font-size:13px;color:#d9e7f2;font-weight:700;margin-bottom:4px">{esc(meta["product"].get("short"))} · {esc(meta["scope"].get("geography") or "")}供应市场全景（采购视角）</div>
      <div class="tiny">数据截止 {esc(meta["scope"].get("data_cutoff") or MISSING)} · 基准年 {esc(meta["scope"].get("base_year") or "—")} · 覆盖 {esc(meta["scope"].get("geography") or "—")} · 产能单位{esc(meta["product"].get("unit") or "")} · 价格单位{esc(meta["product"].get("price_unit") or "")}</div>
    </div>
    <div class="foot-r">
      <div><b>{len(bundle["companies"])}</b> 集团 · <b>{len(bundle["plants"])}</b> 基地 · <b>{len(bundle["sources"])}</b> 来源</div>
      <div class="tiny" style="margin-top:4px">生成日期 {esc((meta.get("generated_at") or "")[:10])} · chemical-supply-market-map v{esc(meta.get("skill_version"))}</div>
    </div>
  </div>'''


def render_all(bundle, excel_name):
    return {
        "MASTHEAD": masthead(bundle, excel_name),
        "OVERVIEW": overview(bundle),
        "COMPANY_TABLE": company_table(bundle),
        "PROJECTS": projects(bundle),
        "PRICE": price(bundle),
        "PROCUREMENT": procurement(bundle),
        "METHOD": method(bundle),
        "DRAWERS": drawers(bundle),
        "FOOTER": footer(bundle),
        "EXCEL_FILE": excel_name,
    }
