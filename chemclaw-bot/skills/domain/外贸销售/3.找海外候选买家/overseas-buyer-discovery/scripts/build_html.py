# -*- coding: utf-8 -*-
"""Build the interactive HTML overseas candidate-buyer report (single self-contained file)."""
import json, os, sys, html, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "report.html")
TODAY = "2026-10-19"

def J(name, default):
    try:
        return json.load(open(os.path.join(HERE, name), encoding="utf-8"))
    except Exception:
        return default

leads = J("leads_merged.json", [])
series = J("comtrade_series.json", [])
partners = J("comtrade_partners.json", {})
peers = J("peer_gate.json", [])
mf = J("market_facts.json", {"facts": [], "headline": {}})
facts = mf.get("facts", [])
HL = mf.get("headline", {})

def esc(s):
    return html.escape(str(s if s is not None else ""))

TYPE_COLOR = {"终端生产企业": "#0e7c66", "直接进口商": "#1f5fa8", "经销商": "#8a5cd6", "待确认": "#8a8f98"}
TIER_COLOR = {"A": "#12864b", "B": "#b8800b", "C": "#6b7280"}
TIER_LABEL = {"A": "有直接贸易证据", "B": "有产品或业务相关证据", "C": "仅根据行业关系推断"}
LANE_COLOR = {"glass": ("玻璃制造", "#0e7c66"), "detergent": ("洗涤剂/日化", "#c2571a"),
              "distributor": ("化工分销/贸易", "#1f5fa8"), "silicate": ("水玻璃/硅酸钠", "#7b5ea7"),
              "pulp_paper": ("纸浆造纸", "#8a6d3b"), "textile_ceramic": ("纺织/陶瓷", "#b03a6a")}
CONF_COLOR = {"高": "#12864b", "中": "#b8800b", "低": "#6b7280"}

n = len(leads)
cA = sum(1 for l in leads if l.get("evidence_tier") == "A")
cB = sum(1 for l in leads if l.get("evidence_tier") == "B")
cC = sum(1 for l in leads if l.get("evidence_tier") == "C")
nEnd = sum(1 for l in leads if l.get("type") == "终端生产企业")
nImp = sum(1 for l in leads if l.get("type") in ("直接进口商", "经销商"))

def tier_badge(t):
    return '<span class="tier t%s">%s · %s</span>' % (t, t, TIER_LABEL.get(t, ""))

def type_badge(t):
    return '<span class="pill" style="color:%s;border-color:%s33;background:%s12">%s</span>' % (
        TYPE_COLOR.get(t, "#666"), TYPE_COLOR.get(t, "#666"), TYPE_COLOR.get(t, "#666"), esc(t))

def regs():
    out = {}
    for l in leads:
        k = l.get("region_short") or "未标注"
        out[k] = out.get(k, 0) + 1
    return sorted(out.items(), key=lambda x: -x[1])

# ---------- SVG chart: import value + China share ----------
def chart_svg():
    W, H, PL, PB, PT = 760, 320, 62, 46, 24
    vals = [s.get("value_usd_m") or 0 for s in series]
    yrs = [str(s.get("year")) for s in series]
    if not vals:
        return "<svg></svg>"
    vmax = max(vals) * 1.18
    iw, ih = W - PL - 24, H - PB - PT
    bw = iw / len(vals)
    bars, labels, line = [], [], []
    pts = []
    for i, s in enumerate(series):
        v = s.get("value_usd_m") or 0
        h = ih * v / vmax
        x = PL + i * bw + bw * 0.22
        w = bw * 0.56
        y = PT + ih - h
        bars.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="url(#g1)"/>' % (x, y, w, h))
        bars.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" fill="#2b3440" font-weight="700">%.0f</text>' % (x + w / 2, y - 7, v))
        q = s.get("qty_kt")
        labels.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="12.5" fill="#4a5260" font-weight="600">%s</text>' % (x + w / 2, H - PB + 20, yrs[i]))
        if q:
            labels.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="10.5" fill="#8b9199">%s kt</text>' % (x + w / 2, H - PB + 35, q))
        u = s.get("unit_usd_t")
        if u:
            pts.append((x + w / 2, u))
    for g in range(5):
        yy = PT + ih - ih * g / 4
        bars.insert(0, '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e8ebef" stroke-width="1"/>' % (PL, yy, W - 24, yy))
        bars.insert(1, '<text x="%d" y="%.1f" text-anchor="end" font-size="10.5" fill="#9aa0a8">%.0f</text>' % (PL - 8, yy + 4, vmax * g / 4))
    # unit-value polyline on right axis
    extra = ""
    if len(pts) >= 2:
        umax = max(p[1] for p in pts) * 1.25
        coords = " ".join("%.1f,%.1f" % (p[0], PT + ih - ih * p[1] / umax) for p in pts)
        extra = ('<polyline points="%s" fill="none" stroke="#c2571a" stroke-width="2.2" stroke-dasharray="5 3"/>' % coords)
        for p in pts:
            extra += '<circle cx="%.1f" cy="%.1f" r="3.2" fill="#fff" stroke="#c2571a" stroke-width="2"/>' % (p[0], PT + ih - ih * p[1] / umax)
        extra += ('<text x="%d" y="%d" text-anchor="end" font-size="11" fill="#c2571a">CIF 均价（美元/吨）</text>' % (W - 26, PT + 2))
    return ('<svg id="chart" viewBox="0 0 %d %d" width="100%%" role="img" aria-label="印尼纯碱进口额与均价">'
            '<defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#2b8fd8"/><stop offset="1" stop-color="#0b5a96"/></linearGradient></defs>') % (W, H) \
        + "".join(bars) + extra + "".join(labels) + '</svg>'

def partner_rows(year):
    rows = partners.get(year, [])
    tot = 1051.9 if year == "2025" else 844.1
    out = []
    for p in rows:
        v = p["value_usd_m"]
        out.append('<tr><td>%s</td><td class="num">%.1f</td><td class="num">%.1f</td><td class="num">%.0f</td>'
                   '<td class="num">%s</td></tr>' % (esc(p["name"]), v, p["kt"], p["unit"],
                                                     ("%.1f%%" % (p["kt"] / tot * 100))))
    return "".join(out)

# ---------- lead cards ----------
def contact_block(l):
    cs = l.get("contact_struct") or {}
    urls = l.get("evidence_urls") or []
    site = cs.get("website") or (urls[0] if urls else "")
    rows = []
    if site:
        rows.append(("官网", site, site.startswith("http")))
    for k, lab in [("phone", "企业总机"), ("email", "企业邮箱/表单"), ("address", "地址")]:
        if cs.get(k):
            rows.append((lab, cs[k], False))
    if cs.get("social"):
        rows.append(("社媒", cs["social"], False))
    if not rows:
        for c in (l.get("contact") or [])[:3]:
            rows.append(("公开渠道", c, str(c).startswith("http")))
    if not rows:
        return '<tr><td colspan="2" class="muted">官网/总机待补充核实</td></tr>'
    h = []
    for lab, val, is_url in rows:
        if is_url:
            h.append('<tr><th>%s</th><td><a href="%s" target="_blank" rel="noopener">%s</a></td></tr>'
                     % (lab, esc(val), esc(val[:78])))
        else:
            h.append('<tr><th>%s</th><td>%s</td></tr>' % (lab, esc(val)))
    if cs.get("note"):
        h.append('<tr><th>说明</th><td class="muted">%s</td></tr>' % esc(cs["note"]))
    if cs.get("verified_on"):
        h.append('<tr><th>核验日</th><td class="muted">%s</td></tr>' % esc(cs["verified_on"]))
    return "".join(h)

def evidence_block(l):
    evs = l.get("evidence_list") or []
    if not evs:
        return ('<li><p class="muted">未取得可点击核验的独立链接，本条置信度较低，仅作电话核实起点。</p></li>')
    out = []
    for e in evs:
        t = e.get("tier", "C")
        out.append(
            '<li><div class="ev-h"><span class="tier t%s">%s</span><b>%s</b>'
            '<span class="when">%s</span></div>'
            '%s'
            '%s'
            '<a class="src" href="%s" target="_blank" rel="noopener">%s</a></li>' % (
                t, t, esc(e.get("type", "")), esc(e.get("period", "") or "期间未标注"),
                ('<p class="q">%s</p>' % esc(e.get("quote"))) if e.get("quote") else "",
                ('<p class="caveat">局限：%s</p>' % esc(e["caveat"])) if e.get("caveat") else "",
                esc(e.get("url", "#")), esc(e.get("source_name", "来源"))))
    return "".join(out)

cards = []
for l in leads:
    t = l.get("evidence_tier") or "C"
    urls = l.get("evidence_urls") or []
    lane = l.get("lane") or "distributor"
    lane_lab, lane_col = LANE_COLOR.get(lane, ("化工分销/贸易", "#1f5fa8"))
    q = " ".join([l.get("company", ""), l.get("main_business", ""), l.get("product_relation", ""),
                  l.get("region_short", "") or "", l.get("lane_label", "") or ""]).lower()
    oq = l.get("open_questions") or []
    oq_html = "".join("<li>%s</li>" % esc(x) for x in oq) or "<li>待补充</li>"
    cards.append("""
    <article class="card" data-type="{typ}" data-tier="{tier}" data-region="{reg}" data-lane="{lane}" data-q="{q}">
      <div class="card-h" onclick="tog(this)">
        <div class="rank">{idx}</div>
        <div class="who">
          <div class="nm">{name}</div>
          <div class="biz">{biz}</div>
          <div class="meta">{tbad}{typbad}<span class="pill">{reg}</span><span class="pill lane" style="color:{lcol};border-color:{lcol}33">{llab}</span><span class="pill conf" style="color:{ccol}">置信度 {conf}</span></div>
        </div>
        <div class="open-hint">展开 ▾</div>
      </div>
      <div class="card-b">
        <div class="grid2">
          <div>
            <h4>业务与产品相关性</h4>
            <p>{why}</p>
            <h4>证据摘要 <span class="pill">{period}</span></h4>
            <p>{summ}</p>
          </div>
          <div>
            <h4>公开企业联系方式</h4>
            <table class="kv">{contacts}</table>
            <h4>建议核验路径</h4>
            <p class="muted">{vch}</p>
          </div>
        </div>
        <h4>证据链</h4>
        <div class="srcs"><ul class="evs">{evs}</ul></div>
        <h4>还需验证的关键问题</h4>
        <ul class="qs">{oq}</ul>
        <div class="actions">
          <button class="btn" onclick="mailto(this)" data-co="{name}">生成询盘邮件</button>
          <button class="btn ghost" onclick="addLead(this)" data-co="{name}">加入我的线索档案</button>
          <button class="btn ghost" onclick="copyCard(this)" data-co="{name}">复制联系人卡片</button>
          <a class="btn ghost" href="https://www.google.com/search?q=%22{qsafe}%22+soda+ash" target="_blank" rel="noopener">企业背景核查</a>
        </div>
      </div>
    </article>""" .format(
        typ=esc(l.get("type") or "待确认"), tier=t, reg=esc(l.get("region_short") or "未标注"), lane=lane,
        q=esc(q).replace('"', "&quot;"), idx=l.get("id"), name=esc(l.get("company")),
        biz=esc(l.get("main_business") or "")[:150], tbad=tier_badge(t), typbad=type_badge(l.get("type") or "待确认"),
        lcol=lane_col, llab=lane_lab, ccol=CONF_COLOR.get(l.get("confidence"), "#666"),
        conf=esc(l.get("confidence") or "中"),
        why=esc(l.get("why_related") or l.get("product_relation") or ""),
        period=esc(l.get("evidence_period") or "期间未标注"),
        summ=esc(l.get("evidence_summary") or ""), contacts=contact_block(l),
        vch=esc(l.get("verify_channel") or ""), evs=evidence_block(l), oq=oq_html,
        qsafe=esc(l.get("company", "")).replace('"', "%22")))

region_opts = "".join('<option value="%s">%s (%d)</option>' % (esc(k), esc(k), v) for k, v in regs())
lane_counts = {}
for l in leads:
    lane_counts[l.get("lane")] = lane_counts.get(l.get("lane"), 0) + 1
lane_opts = "".join('<option value="%s">%s (%d)</option>' % (k, LANE_COLOR.get(k, ("其他", ""))[0], v)
                    for k, v in sorted(lane_counts.items(), key=lambda x: -x[1]))

# peers
VERD = {"EXCLUDE_AS_PEER": ("排除·同行/未来产能", "#b03a6a"),
        "EXCLUDE_AS_COMPETITOR": ("排除·竞品/竞品渠道", "#c2571a"),
        "KEEP_AS_CUSTOMER_CANDIDATE": ("保留·客户候选", "#12864b"),
        "UNCERTAIN": ("待定·证据不足", "#8a8f98")}
peer_rows = "".join(
    '<tr><td><b>%s</b></td><td><span class="pill" style="color:%s;border-color:%s33;background:%s0d">%s</span></td>'
    '<td>%s</td><td><a class="src" href="%s" target="_blank" rel="noopener">来源</a></td></tr>'
    % (esc(p.get("company")), VERD.get(p.get("verdict"), ("", "#666"))[1], VERD.get(p.get("verdict"), ("", "#666"))[1],
       VERD.get(p.get("verdict"), ("", "#666"))[1], VERD.get(p.get("verdict"), (p.get("verdict"), "#666"))[0],
       esc((p.get("why") or p.get("evidence") or "")[:300]),
       esc((p.get("evidence_urls") or ["#"])[0])) for p in peers)

# facts
TOPIC = {"imports": "进口", "structure": "产业结构", "demand": "需求", "price": "价格", "regulation": "法规", "gap": "数据缺口"}
fact_rows = "".join(
    '<tr><td><span class="pill">%s</span></td><td>%s</td><td class="num">%s</td><td>%s</td>'
    '<td><span class="cbadge" style="color:%s">%s</span></td>'
    '<td>%s</td></tr>' % (
        TOPIC.get(f.get("topic"), f.get("topic")), esc(f.get("fact")), esc(f.get("value")), esc(f.get("period")),
        CONF_COLOR.get(f.get("confidence"), "#666"), esc(f.get("confidence")),
        ('<a class="src" href="%s" target="_blank" rel="noopener">来源</a>' % esc(f["source_url"])) if f.get("source_url") else "—")
    for f in facts)

# type playbook
PLAY = [
    ("终端生产企业", "#0e7c66", "玻璃、洗涤剂、水玻璃、造纸、印染",
     "关注点：稳定供应 + 品质一致性。",
     ["先问三件事：现在用哪个规格（重质/轻质）、年用量、现有供应商与原产国",
      "提供 25–50 kg 样品 + 批次 COA（Na₂CO₃、Fe₂O₃、盐不溶物、堆积密度、粒度分布）",
      "报价给出 CIF 主要港口（雅加达 Tanjung Priok / 泗水 Tanjung Perak / 勿拉湾 Belawan）",
      "强调能否按窑炉/配方做长期锁量，而非单笔低价"],
     "这类客户换供应商周期长（3–9 个月），一旦切入复购稳定，是首选攻克对象。"),
    ("直接进口商", "#1f5fa8", "持有 API-U 进口资质、自营报关与清关",
     "关注点：价差 + 资金与清关能力。",
     ["确认其进口资质（API-U）、是否可开信用证（L/C）与账期习惯",
      "明确贸易条款：CIF / CFR、是否接受指定货代、是否需要熏蒸/托盘",
      "给出与现有原产国（美国/土耳其）的到岸价差测算",
      "了解其下游客户结构（玻璃优先？洗涤优先？）"],
     "进口商是自己有报关能力的中间环节，能快速放量，但价格敏感、忠诚度低。"),
    ("经销商", "#8a5cd6", "化学品分销、区域仓储、多品牌代理",
     "关注点：区域覆盖 + 库存周转。",
     ["问清其代理品牌（是否已有中国或美国品牌，注意排他条款）",
      "确认仓储与区域覆盖（爪哇/苏门答腊/加里曼丹）",
      "讨论寄售/备货仓模式（在雅加达或泗水设寄售库存）",
      "要其年度提货量与主要下游行业"],
     "适合做市场覆盖与试水，但不建议把核心客户直接交给已代理竞品的分销商。"),
]
play_html = "".join("""
<div class="play" style="border-left-color:%s">
  <h4 style="color:%s">%s <span class="muted">· %s</span></h4>
  <p class="lead2">%s</p>
  <ol>%s</ol>
  <p class="note">%s</p>
</div>""" % (c, c, t, sub, focus, "".join("<li>%s</li>" % x for x in acts), note) for t, c, sub, focus, acts, note in PLAY)

# verification questions
VQ = [
    ("采购规模与结构", ["该企业年采购重质纯碱（或轻质纯碱）多少吨？",
                   "目前的供应商与原产国（美国/土耳其/中国/印度）？是否有替代计划？",
                   "单笔订单的常规批量与到货频率？"]),
    ("品质与规格", ["要求的 Na₂CO₃ 含量（99.2% 或更高）？Fe₂O₃ 上限？盐不溶物上限？",
                "堆积密度与粒度分布要求（是否要求 ≥1.0 g/cm³、粒度中心值）？",
                "是否接受合成碱替代天然碱？是否需第三方检验（SGS/BV）？"]),
    ("合规与准入", ["该企业是否持有 API-U 进口资质？是否需要我方配合 SNI 认证？",
                "HS 2836.20 适用关税（MFN 7.5% / ACFTA 0%）需以 INSW 原件复核——谁承担？",
                "是否属于 LARTAS 管制商品、是否需进口许可（PI）？"]),
    ("商务与交付", ["可接受的贸易条款（CIF/CFR/FOB）与目的港？",
                "付款方式（T/T 预付比例 / L/C at sight / 账期天数）？",
                "包装要求（50 kg PP 袋 / 1,000 kg 吨袋 / 散装）与托盘、唛头要求？"]),
]
vq_html = "".join('<div class="vqbox"><h4>%s</h4><ul class="qs">%s</ul></div>'
                  % (h, "".join("<li>%s</li>" % x for x in items)) for h, items in VQ)

CSS = open(os.path.join(HERE, "report.css"), encoding="utf-8").read()

TPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>印度尼西亚 · 重质纯碱 海外候选买家调查报告</title>
<style>{{css}}</style></head>
<body>
<div class="hero">
  <div class="kicker">Overseas Buyer Discovery · Evidence-Graded</div>
  <h1>印度尼西亚 · 重质纯碱 海外候选买家调查报告</h1>
  <p class="sub">目标产品：重质（密质）纯碱 Heavy / Dense Soda Ash，Na₂CO₃ 99.2% min，CAS 497-19-8，常规包装 50 kg PP 袋 / 1,000 kg 吨袋。<br/>
     目标国家：印度尼西亚。目标客户：玻璃制造终端工厂、洗涤剂与日化工厂、水玻璃/造纸/印染等终端用户，以及化工品直接进口商与区域经销商。</p>
  <div class="stamp"><span>报告日期 {{today}}</span><span>候选企业 {{n}} 家</span>
    <span>A 级 {{cA}} · B 级 {{cB}} · C 级 {{cC}}</span><span>终端工厂 {{nEnd}} · 进口/分销 {{nImp}}</span></div>
</div>

<div class="wrap">
  <div class="kpis">
    <div class="kpi a"><b>{{cA}}</b><small>A 级 · 有公开的直接采购/进口证据</small></div>
    <div class="kpi b"><b>{{cB}}</b><small>B 级 · 产品与业务强相关，缺交易层证据</small></div>
    <div class="kpi c"><b>{{cC}}</b><small>C 级 · 仅行业推断，须先电话核实</small></div>
    <div class="kpi"><b>{{peerN}}</b><small>已剔除的同行与竞品渠道</small></div>
  </div>

  <section class="block">
    <h2>0. 怎么读这份报告</h2>
    <p class="lead">这份报告回答的不是“谁一定买”，而是“谁最可能买、证据到什么程度、下一步怎么问”。所有结论都可以点开原始链接自行复核。</p>
    <div class="note"><b>不确认任何采购关系。</b>{{n}} 家候选企业中，只有 {{cA}} 家取得了公开或第三方数据层面的直接证据；其余为产品工艺相关证据或行业推断。所有联系方式均为企业级公开渠道，未使用任何个人联系方式，也未虚构任何交易记录。</div>
    <div class="grid2">
      <div>
        <h4>证据三级定义</h4>
        <table class="dt">
          <tr><th style="width:64px">等级</th><th>判定标准</th><th style="width:170px">下一步动作</th></tr>
          <tr><td><span class="tier tA">A</span></td><td>公开来源直接出现该企业就该产品的采购、进口或消耗记录，并给出产品、方向与期间</td><td>直接进入商务谈判，重点做供应链结构与价格对标</td></tr>
          <tr><td><span class="tier tB">B</span></td><td>来源能证明企业真实存在且业务与产品强相关（目录列明、工艺必然消耗），但无交易层证据</td><td>先确认“是否在用、从谁买、年用量”，再报价</td></tr>
          <tr><td><span class="tier tC">C</span></td><td>仅能证明其属于相关行业，无任何产品或贸易层面证据</td><td>只作电话核实起点，禁止报价与承诺</td></tr>
        </table>
      </div>
      <div>
        <h4>三条使用红线</h4>
        <ul class="qs">
          <li>不得把 C 级线索写成“目标客户”或“已确认购买”。</li>
          <li>不得虚构采购记录、进口量、联系人姓名或个人手机号。</li>
          <li>官网与贸易数据在发出报价前必须重新打开核实（本报告链接均于 {{today}} 前后抓取）。</li>
        </ul>
        <h4>本次没有拿到的东西（如实说明）</h4>
        <p class="muted">印尼海关逐公司进口报关明细属付费数据，本次未取得；因此“某企业实际从中国进口纯碱多少吨”这类企业级贸易记录无法在本报告中给出。A 级证据来自两类公开物：企业自身的年报/披露，以及可免费读取的提单样例与官方统计。二者已在证据链中分别标注。</p>
      </div>
    </div>
  </section>

  <section class="block">
    <h2>1. 市场背景：印尼纯碱从哪来、用到哪</h2>
    <p class="lead">印尼长期没有在产纯碱装置，需求几乎全部依赖进口；第一大下游是玻璃。对中国供应商而言，这意味着“进口来源结构”本身就是替代空间。</p>
    <div class="chartwrap">
      <div>
        <h4>HS 2836.20 印尼进口额（百万美元，柱）与 CIF 均价（橙线）</h4>
        {{chart}}
        <p class="muted small">数据：UN Comtrade（reporter Indonesia, HS 283620, flow Import），2026-10 抓取。数量为净重净吨，均价=CIF 总额/数量。</p>
      </div>
      <div>
        <h4>关键读数</h4>
        <ul class="qs">
          <li>2025 年进口量 <b>105.19 万吨</b>，进口额 <b>2.26 亿美元</b>，CIF 均价 <b>214 美元/吨</b>——量创新高而价创五年新低。</li>
          <li>均价从 2022 年 <b>375 美元/吨</b> 跌到 2025 年 <b>214 美元/吨</b>（−43%），与 USGS 所述全球价格下行一致。</li>
          <li>来源结构：<b>美国天然碱</b> 73.16 万吨（69.6%）仍是第一来源，<b>中国货 2025 年 28.70 万吨</b>（27.3%），较 2024 年 10.51 万吨暴增 173%，且到岸价已与美国货持平（212 vs 215 美元/吨）。</li>
          <li>土耳其从 3.46 万吨萎缩到 2.02 万吨、印度从 6.83 万吨萎缩到 0.14 万吨——份额正在被美国与中国瓜分，这正是中国企业切入的窗口。</li>
        </ul>
      </div>
    </div>
    <div class="grid2">
      <div>
        <h4>2025 年分来源国进口（UN Comtrade）</h4>
        <table class="dt"><tr><th>来源国</th><th class="num">金额（百万美元）</th><th class="num">数量（千吨）</th><th class="num">均价（美元/吨）</th><th class="num">占全年量</th></tr>
        {{p25}}
        </table>
      </div>
      <div>
        <h4>2024 年分来源国进口（对照）</h4>
        <table class="dt"><tr><th>来源国</th><th class="num">金额（百万美元）</th><th class="num">数量（千吨）</th><th class="num">均价（美元/吨）</th><th class="num">占全年量</th></tr>
        {{p24}}
        </table>
      </div>
    </div>
    <div class="note"><b>时间窗口：</b>印尼首套纯碱装置（Pupuk Kaltim + Rekind，东加里曼丹 Bontang，30 万吨/年 + 30 万吨/年氯化铵，投资约 3 亿美元，EPC 为中国天辰牵头的联合体）已于 2025-10-31 动工，<b>目标 2028 年 3 月投产</b>。届时约 30% 需求转为本地供应，进口溢价将被压缩。也就是说：<b>现在到 2028 年一季度，是替代美国货的最后窗口。</b></div>
  </section>

  <section class="block">
    <h2>2. 候选企业筛选器 <span class="counter" id="shown">{{n}}</span></h2>
    <p class="lead">按客户类型、证据等级、地区和业务领域筛选；点击企业展开官网、业务介绍、产品关联证据与公开联系方式，并可一键生成询盘邮件或建立线索档案。</p>
    <div class="toolbar">
      <input type="search" id="q" placeholder="搜索公司名 / 业务 / 产品关键词…"/>
      <div class="seg" id="typeSeg">
        <button class="chip on" data-f="all">全部类型</button>
        <button class="chip" data-f="终端生产企业">终端生产</button>
        <button class="chip" data-f="直接进口商">直接进口</button>
        <button class="chip" data-f="经销商">经销商</button>
        <button class="chip" data-f="待确认">待确认</button>
      </div>
      <div class="seg" id="tierSeg">
        <button class="chip on" data-f="all">全部证据</button>
        <button class="chip" data-f="A">A 级</button>
        <button class="chip" data-f="B">B 级</button>
        <button class="chip" data-f="C">C 级</button>
      </div>
      <select id="regionSel"><option value="all">全部地区</option>{{regions}}</select>
      <select id="laneSel"><option value="all">全部业务领域</option>{{lanes}}</select>
    </div>
    <div id="list" class="list">{{cards}}</div>
  </section>

  <section class="block">
    <h2>3. 三类客户怎么打</h2>
    <p class="lead">同样是纯碱客户，终端工厂、进口商、经销商的决策逻辑完全不同，话术与报价方式也应不同。</p>
    {{play}}
  </section>

  <section class="block">
    <h2>4. 同行与竞品排除（peer gate）</h2>
    <p class="lead">名单里最容易犯的错，是把未来的生产者、同行和竞品渠道当成客户。以下企业已逐条核查并剔除，附理由与来源。</p>
    <table class="dt wide"><tr><th style="width:24%">企业</th><th style="width:150px">判定</th><th>理由与证据</th><th style="width:60px">来源</th></tr>{{peers}}</table>
    <div class="note"><b>两个典型陷阱：</b>① 分销商页面上写着“Soda Ash Dense ex ANSAC USA”，证明的是<b>这家分销商</b>在卖美国货，而不是 ANSAC 是客户；② 中国同行（唐山三友）在自己出口页上列出“Asahi、Unilever、P&G”为客户，说明这些厂<b>已被中国竞品拿下</b>——是竞争情报，不是客户资格。</div>
  </section>

  <section class="block">
    <h2>5. 后市核验清单（联系前必答）</h2>
    <p class="lead">每一家进入报价阶段的客户，都应先答完下面这些问题的至少前两组。</p>
    <div class="vqgrid">{{vq}}</div>
  </section>

  <section class="block">
    <h2>6. 市场事实与数据来源</h2>
    <table class="dt wide"><tr><th style="width:86px">类别</th><th>事实</th><th class="num" style="width:96px">数值</th><th style="width:96px">期间</th><th style="width:64px">置信度</th><th style="width:60px">来源</th></tr>{{facts}}</table>
  </section>

  <footer>
    <p>本报告由公开来源自动采集与人工核验生成，仅用于销售线索筛选，不构成任何采购承诺或商业担保。</p>
    <p class="muted small">报告日期 {{today}} · 候选企业 {{n}} 家 · 证据等级 A/B/C · 所有联系方式均为企业级公开渠道</p>
  </footer>
</div>
<div id="toast" class="toast"></div>
<script>
const DATA = {{data}};
const shownEl = document.getElementById('shown');
let fType='all', fTier='all';
function apply(){
  const q=document.getElementById('q').value.trim().toLowerCase();
  const reg=document.getElementById('regionSel').value, lane=document.getElementById('laneSel').value;
  let n=0;
  document.querySelectorAll('#list .card').forEach(c=>{
    const ok = (fType==='all'||c.dataset.type===fType) && (fTier==='all'||c.dataset.tier===fTier)
      && (reg==='all'||c.dataset.region===reg) && (lane==='all'||c.dataset.lane===lane)
      && (!q || c.dataset.q.includes(q));
    c.classList.toggle('hidden', !ok); if(ok) n++;
  });
  shownEl.textContent=n;
}
document.querySelectorAll('#typeSeg .chip').forEach(b=>b.onclick=()=>{fType=b.dataset.f;document.querySelectorAll('#typeSeg .chip').forEach(x=>x.classList.toggle('on',x===b));apply();});
document.querySelectorAll('#tierSeg .chip').forEach(b=>b.onclick=()=>{fTier=b.dataset.f;document.querySelectorAll('#tierSeg .chip').forEach(x=>x.classList.toggle('on',x===b));apply();});
document.getElementById('q').oninput=apply;
document.getElementById('regionSel').onchange=apply;
document.getElementById('laneSel').onchange=apply;
function tog(el){ el.parentNode.classList.toggle('open'); }
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1900);}
function draft(d){
  const tier=d.evidence_tier||'C', type=d.type||'';
  const qs=(d.open_questions||[]).slice(0,3).map((q,i)=>(i+1)+'. '+q).join('\\n');
  const vol=d.volume_hint||'your annual requirement';
  if(tier==='A' && type==='终端生产企业'){
    return 'Subject: Dense soda ash (Na2CO3 99.2%) - supply option for '+d.company+'\\n\\n'
      +'Dear Procurement Team,\\n\\n'
      +'Our public-source review indicates that '+d.company+' consumes dense soda ash in the order of '+vol+'. '
      +'We are a dense soda ash producer based in China (Na2CO3 99.2% min, bulk density 0.90-1.10 g/cm3, Fe2O3 0.003% max), '
      +'supplied in 50 kg PP bags or 1,250 kg jumbo bags, with lot-by-lot COA and third-party inspection on request.\\n\\n'
      +'Before we send a formal quotation, could you kindly confirm:\\n'+qs+'\\n\\n'
      +'A price indication for 500 t or 1,000 t CIF Jakarta / Surabaya can be issued within two working days.\\n\\n'
      +'Best regards,\\n[Name] | [Company] | [Email] | [Phone]';
  }
  if(type==='直接进口商' || type==='经销商'){
    return 'Subject: Dense soda ash Na2CO3 99.2% - CIF Indonesia price for distribution\\n\\n'
      +'Dear '+d.company+' Team,\\n\\n'
      +'We supply dense soda ash for the Indonesian market and are looking for established importers and distributors '
      +'with their own import licence (API-U) and warehousing.\\n\\n'
      +'Our specification: Na2CO3 99.2% min; bulk density 0.90-1.10 g/cm3; Fe2O3 0.003% max; chlorides 0.30% max; '
      +'packing 50 kg PP bags / 1,000 kg jumbo bags / bulk.\\n\\n'
      +'To quote accurately, could you confirm:\\n'+qs+'\\n\\n'
      +'We can also discuss a consignment stock arrangement in Jakarta or Surabaya.\\n\\n'
      +'Best regards,\\n[Name] | [Company] | [Email] | [Phone]';
  }
  return 'Subject: Dense soda ash Na2CO3 99.2% - supply enquiry from a Chinese producer\\n\\n'
    +'Dear '+d.company+' Team,\\n\\n'
    +'We are a soda ash producer in China and understand that '+d.company+' operates in a sector that may use dense soda ash.\\n\\n'
    +'Could you kindly confirm whether you purchase dense soda ash, and if so:\\n'+qs+'\\n\\n'
    +'If soda ash is not part of your purchasing scope, we would be grateful if you could point us to the right colleague.\\n\\n'
    +'Best regards,\\n[Name] | [Company] | [Email] | [Phone]';
}
function mailto(btn){
  const d=Object.values(DATA).find(x=>x.company===btn.dataset.co)||{};
  const cs=d.contact_struct||{};
  const to=cs.email||'';
  const body=draft(d);
  const url='mailto:'+encodeURIComponent(to)+'?subject='+encodeURIComponent(body.split('\\n')[0].replace('Subject: ',''))+'&body='+encodeURIComponent(body.split('\\n').slice(2).join('\\n'));
  window.open(url,'_blank');
  toast('已生成询盘邮件草稿'+(to?'（收件人：'+to+'）':'（未收录企业邮箱，请手动填写收件人）'));
}
function addLead(btn){
  const co=btn.dataset.co;
  const d=Object.values(DATA).find(x=>x.company===co)||{};
  let arr=[]; try{arr=JSON.parse(localStorage.getItem('oceanLeads_v1')||'[]');}catch(e){arr=[];}
  if(arr.some(a=>a.company===co)){ toast('该企业已在你的线索档案中'); return; }
  arr.push({company:co,type:d.type||'',tier:d.evidence_tier||'',region:d.region_short||'',
            lane:d.lane_label||'',website:(d.contact_struct||{}).website||'',
            next_step:'核实年用量与现有供应商',added:new Date().toISOString().slice(0,10)});
  localStorage.setItem('oceanLeads_v1',JSON.stringify(arr));
  toast('已加入线索档案（共 '+arr.length+' 家，保存在本机浏览器）');
}
function copyCard(btn){
  const d=Object.values(DATA).find(x=>x.company===btn.dataset.co)||{};
  const cs=d.contact_struct||{};
  const txt=[d.company,'类型：'+(d.type||''),'证据：'+d.evidence_tier+' 级（'+(d.confidence||'')+'）',
    '地区：'+(d.region_short||''),'业务：'+(d.main_business||''),
    '官网：'+(cs.website||''),'电话：'+(cs.phone||''),'邮箱：'+(cs.email||''),'地址：'+(cs.address||''),
    '证据：'+(d.evidence_summary||'')].join('\\n');
  navigator.clipboard.writeText(txt).then(()=>toast('联系人卡片已复制'),()=>toast('复制失败，请手动选择文本'));
}
</script>
</body></html>
"""

vals = {
    "css": CSS, "today": TODAY, "n": n, "cA": cA, "cB": cB, "cC": cC, "nEnd": nEnd, "nImp": nImp,
    "peerN": len(peers), "chart": chart_svg(), "p25": partner_rows("2025"), "p24": partner_rows("2024"),
    "regions": region_opts, "lanes": lane_opts, "cards": "".join(cards), "play": play_html,
    "peers": peer_rows, "vq": vq_html, "facts": fact_rows,
    "data": json.dumps({str(l.get("id")): l for l in leads}, ensure_ascii=False),
}
out = TPL
for k, v in vals.items():
    out = out.replace("{{" + k + "}}", str(v))
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(out)
print("saved", OUT, "size", len(out), "leads", n)
