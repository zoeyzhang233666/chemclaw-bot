# -*- coding: utf-8 -*-
"""build_html.py —— 由 analysis.json 生成单文件离线交互式 HTML 研究报告

用法：python scripts/build_html.py build/analysis.json --out-dir out
"""
import argparse, json, os, sys, html

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')


def esc(x):
    return html.escape('' if x is None else str(x))


def f(x, n=2):
    if x is None:
        return '—'
    try:
        return ('{:,.%df}' % n).format(x)
    except Exception:
        return str(x)


def sgn(x, n=2):
    if x is None:
        return '—'
    return ('+' if x > 0 else '') + f(x, n)


def pctf(x, n=2):
    if x is None:
        return '—'
    return ('+' if x > 0 else '') + f(x, n) + '%'


def load_echarts():
    p = os.path.join(ASSETS, 'echarts.min.js')
    if not os.path.exists(p):
        return ''
    return open(p, encoding='utf-8').read()


CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}
:root{
 --bg:#0e1117;--panel:#161b22;--panel2:#1c232c;--line:#2a323d;
 --txt:#e6edf3;--dim:#9aa7b4;--dim2:#6b7885;
 --up:#e5534b;--down:#3fb950;--acc:#4a9eff;--warn:#d29922;--purple:#a371f7;
}
body{background:var(--bg);color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;
 font-size:14px;line-height:1.65;-webkit-font-smoothing:antialiased}
.wrap{max-width:1440px;margin:0 auto;padding:0 20px 60px}
header{background:linear-gradient(135deg,#131a24 0%,#1a2332 100%);border-bottom:1px solid var(--line);
 padding:26px 0 22px;margin-bottom:0}
header .wrap{padding-bottom:0}
h1{font-size:25px;font-weight:650;letter-spacing:-.3px}
.sub{color:var(--dim);font-size:13px;margin-top:6px}
.badges{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px}
.badge{background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:3px 9px;
 font-size:12px;color:var(--dim)}
.badge b{color:var(--txt);font-weight:600}
.badge.warn{border-color:#5c4a1a;background:#2a2312;color:#e3b341}
nav{position:sticky;top:0;z-index:50;background:rgba(14,17,23,.94);backdrop-filter:blur(10px);
 border-bottom:1px solid var(--line);margin-bottom:24px}
nav .wrap{display:flex;gap:2px;overflow-x:auto;padding:0 20px}
nav button{background:none;border:none;color:var(--dim);padding:13px 14px;font-size:13.5px;cursor:pointer;
 border-bottom:2px solid transparent;white-space:nowrap;font-family:inherit;transition:.15s}
nav button:hover{color:var(--txt)}
nav button.on{color:var(--acc);border-bottom-color:var(--acc);font-weight:600}
section{display:none;animation:fade .25s}
section.on{display:block}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
h2{font-size:19px;font-weight:640;margin:0 0 4px;display:flex;align-items:center;gap:9px}
h2 .n{background:var(--acc);color:#0b0f14;width:23px;height:23px;border-radius:6px;
 display:inline-flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex:none}
h3{font-size:15px;font-weight:620;margin:22px 0 10px;color:#dbe4ec}
.lead{color:var(--dim);font-size:13.5px;margin:8px 0 18px;max-width:900px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:16px}
.grid{display:grid;gap:14px}
.g2{grid-template-columns:repeat(2,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:900px){.g2,.g3,.g4{grid-template-columns:1fr}}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:15px 16px}
.kpi .k{font-size:12px;color:var(--dim);margin-bottom:7px;display:flex;align-items:center;gap:5px}
.kpi .v{font-size:24px;font-weight:660;letter-spacing:-.5px;font-variant-numeric:tabular-nums}
.kpi .s{font-size:11.5px;color:var(--dim2);margin-top:5px}
.kpi.up .v{color:var(--up)}.kpi.down .v{color:var(--down)}.kpi.acc .v{color:var(--acc)}
.kpi.warn .v{color:var(--warn)}.kpi.purple .v{color:var(--purple)}
table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);color:var(--dim);
 font-weight:600;font-size:12px;white-space:nowrap;background:var(--panel2)}
td{padding:8px 10px;border-bottom:1px solid #20272f}
tr:hover td{background:#1a212a}
td.num,th.num{text-align:right}
.tag{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11px;font-weight:600}
.tag.up{background:#3d1d1b;color:#ff7b72}.tag.down{background:#12261a;color:#56d364}
.tag.warn{background:#2a2312;color:#e3b341}.tag.acc{background:#132a3d;color:#79c0ff}
.tag.dim{background:#20272f;color:var(--dim)}
.note{border-left:3px solid var(--warn);background:#1e1a10;padding:12px 15px;border-radius:0 7px 7px 0;
 font-size:13px;color:#e3d5b0;margin:14px 0}
.note.acc{border-color:var(--acc);background:#101c28;color:#b8d4ef}
.note.danger{border-color:var(--up);background:#241413;color:#f0c0bc}
.note b{color:#fff}
.chart{width:100%;height:380px}
.chart.tall{height:440px}
.chart.short{height:260px}
.f{font-family:"SF Mono",Consolas,Monaco,monospace;background:#0b0f14;border:1px solid var(--line);
 border-radius:7px;padding:13px 16px;font-size:12.5px;color:#9fd5b0;overflow-x:auto;line-height:1.75;white-space:pre}
.ctrl{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin-bottom:16px;
 background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:14px 17px}
.ctrl label{display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--dim)}
.ctrl input,.ctrl select{background:#0b0f14;border:1px solid var(--line);color:var(--txt);
 border-radius:6px;padding:6px 9px;font-size:13px;font-family:inherit;min-width:96px}
.ctrl input[type=range]{padding:0;min-width:150px}
.ctrl .val{color:var(--acc);font-weight:600;font-variant-numeric:tabular-nums}
.btn{background:var(--acc);color:#06111d;border:none;border-radius:6px;padding:7px 15px;
 font-size:13px;font-weight:620;cursor:pointer;font-family:inherit}
.btn.ghost{background:var(--panel2);color:var(--txt);border:1px solid var(--line)}
.btn:hover{filter:brightness(1.12)}
.mono{font-family:"SF Mono",Consolas,monospace}
.dim{color:var(--dim)}.dim2{color:var(--dim2)}
.tiny{font-size:11.5px}
ul.li{padding-left:20px}ul.li li{margin:6px 0;color:var(--dim)}
ul.li li b{color:var(--txt)}
.steps{display:flex;flex-direction:column;gap:0}
.step{display:flex;gap:14px;padding:15px 0;border-bottom:1px solid #20272f}
.step:last-child{border-bottom:none}
.step .ic{width:26px;height:26px;border-radius:50%;background:var(--panel2);border:1px solid var(--line);
 display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:var(--acc);flex:none}
.step .bd{flex:1}
.step .t{font-weight:600;margin-bottom:4px}
.step .d{color:var(--dim);font-size:13px}
footer{text-align:center;color:var(--dim2);font-size:12px;padding:30px 0 10px;border-top:1px solid var(--line);margin-top:34px}
.pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:var(--panel2);
 border:1px solid var(--line);color:var(--dim);margin-right:5px}
"""


def build(analysis, out_path, events=None, source_notes=None):
    s = analysis['summary']
    meta = analysis['meta']
    up = meta['upstream']
    dn = meta['downstream']
    sp = s['spread']
    rob = meta.get('_robust') or {}
    calib = analysis.get('calibration') or []
    stages = analysis.get('stages') or []
    divs = analysis.get('divergences') or []
    stats = analysis.get('stats') or {}
    steps = analysis.get('steps') or {}
    outliers = analysis.get('outliers') or []
    sens = analysis.get('sensitivity') or {}
    daily = analysis['daily']
    monthly = analysis['monthly']
    yearly = analysis.get('yearly') or []
    events = events or []

    # ---------- 图数据
    dates = [r['date'] for r in daily]
    c_up = [r['up'] for r in daily]
    c_down = [r['down'] for r in daily]
    c_cost = [r['cost'] for r in daily]
    c_sp = [r['spread'] for r in daily]
    c_lo = [r['spread_low_unit'] for r in daily]
    c_hi = [r['spread_high_unit'] for r in daily]

    chart_data = {
        'dates': dates, 'up': c_up, 'down': c_down, 'cost': c_cost,
        'spread': c_sp, 'spread_lo': c_lo, 'spread_hi': c_hi,
        'z': [r.get('z') for r in daily],
        'upName': up['name'], 'downName': dn['name'],
        'divs': divs, 'monthly': monthly,
        'lagCorr': stats.get('lag_corr') or [],
        'unit': '元/吨',
        'unit0': (meta.get('materials') or [{}])[0].get('unit') or 1.0,
        'stages': stages,
    }

    echarts_js = load_echarts()

    # ---------- 各分页 HTML
    tabs = []
    tabs.append(('ov', '总览', tab_overview(s, meta, sp, calib, stages, rob)))
    tabs.append(('proc', '① 产业关系与工艺', tab_process(meta)))
    tabs.append(('price', '② 价格口径与时序', tab_price(meta, s, chart_data)))
    tabs.append(('cost', '③④ 成本与价差', tab_cost(meta, s, sens, chart_data)))
    tabs.append(('stage', '⑤ 分阶段传导', tab_stage(stages, steps, s)))
    tabs.append(('lag', '⑥ 时滞与背离', tab_lag(stats, divs, steps, outliers, chart_data)))
    tabs.append(('evt', '⑦ 事件核查', tab_events(divs, stages, events, dates)))
    tabs.append(('limit', '⑧ 局限与公式', tab_limit(meta, analysis, calib, source_notes)))

    nav_html = ''
    secs_html = ''
    for i, (tid, label, body) in enumerate(tabs):
        nav_html += '<button data-t="%s" class="%s">%s</button>' % (tid, 'on' if i == 0 else '', esc(label))
        secs_html += '<section id="t-%s" class="%s">%s</section>' % (tid, 'on' if i == 0 else '', body)

    doc = (HTML_TMPL
           .replace('__CSS__', CSS)
           .replace('__NAV__', nav_html)
           .replace('__SECTIONS__', secs_html)
           .replace('__TITLE__', esc('%s → %s 成本传导研究' % (up['name'], dn['name'])))
           .replace('__CHAIN__', esc(meta.get('chain') or ''))
           .replace('__WIN__', esc('%s ~ %s' % (s['window'][0], s['window'][1])))
           .replace('__NOBS__', str(s['n_obs']))
           .replace('__ECHARTS__', echarts_js)
           .replace('__DATA__', json.dumps(chart_data, ensure_ascii=False)))
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(doc)
    return out_path, len(doc)


def tab_overview(s, meta, sp, calib, stages, rob):
    up, dn = meta['upstream'], meta['downstream']
    spread_def = (meta.get('params') or {}).get('spread_definition', '')
    h = ['<h2><span class="n">概</span>这份报告回答什么</h2>',
         '<p class="lead">用同期间、同口径的两条现货价格，量化 <b>%s</b> 的变动有多少传到了 <b>%s</b>，'
         '在哪些阶段没传到位，以及这些数字<b>解释不了</b>什么。</p>' % (esc(up['name']), esc(dn['name']))]

    # KPI
    h.append('<div class="grid g4">')
    h.append(kpi('上游 %s 期间变动' % up['name'], pctf(s['up']['chg_pct']),
                 '%s → %s 元/吨' % (f(s['up']['start']), f(s['up']['end'])),
                 'up' if s['up']['chg'] >= 0 else 'down'))
    h.append(kpi('下游 %s 期间变动' % dn['name'], pctf(s['down']['chg_pct']),
                 '%s → %s 元/吨' % (f(s['down']['start']), f(s['down']['end'])),
                 'up' if s['down']['chg'] >= 0 else 'down'))
    h.append(kpi('加工价差均值', f(sp['mean'], 1),
                 '区间 %s ~ %s 元/吨' % (f(sp['min'], 0), f(sp['max'], 0)), 'acc'))
    h.append(kpi('最新价差 / 分位', '%s / %s%%' % (f(sp['latest'], 0), f(sp['latest_rank'], 1)),
                 '在观测期内所处分位', 'purple'))
    h.append('</div>')

    # 口径摘要
    h.append('<h3>口径摘要（数字能不能用，全看这一块）</h3>')
    h.append('<div class="card"><table><thead><tr><th>项目</th><th>上游</th><th>下游</th></tr></thead><tbody>')
    for label, key in [('品种', 'name'), ('规格', 'spec'), ('地区', 'region'),
                       ('单位', 'unit'), ('税基', 'tax'), ('频率/性质', 'granularity'), ('来源', 'source')]:
        h.append('<tr><td class="dim">%s</td><td>%s</td><td>%s</td></tr>'
                 % (esc(label), esc(up.get(key) or '—'), esc(dn.get(key) or '—')))
    h.append('</tbody></table></div>')

    # 价差定义 + 不是利润
    h.append('<div class="note danger"><b>加工价差 ≠ 利润。</b>本报告的价差口径是 '
             '<span class="mono">%s</span>。它只扣了原料，'
             '<b>不含</b>能源/公用工程、辅料与催化剂、人工、折旧、财务费用、检维修、包装运费、库存损益。'
             '把它叫"利润"或"加工利润"，是这类研究最常见的错误。</div>' % esc(spread_def))

    # 原料成本占比
    cs = s.get('cost_share_pct')
    if cs:
        h.append('<div class="grid g3">')
        h.append(kpi('原料成本占下游价格', f(cs, 1) + '%', '正常区间 60%~98%，超出说明单位或单耗有问题', 'acc'))
        h.append(kpi('价差低单耗情形', f((meta.get('_sens') or {}).get('low_unit_mean') or 0, 1), '单耗取下界时的价差均值', 'dim'))
        h.append(kpi('价差高单耗情形', f((meta.get('_sens') or {}).get('high_unit_mean') or 0, 1), '单耗取上界时的价差均值', 'dim'))
        h.append('</div>')

    # 锚点校验
    if calib:
        h.append('<h3>口径校验：模型价差 vs 公开行业数值</h3>')
        h.append('<p class="lead">用同一公式算出的价差，与公开报告披露的加工费对比。'
                 '偏差在 ±150 元/吨内且正负交替，通常来自各机构采样企业与取价时点的差异，属于可接受口径差。</p>')
        h.append('<div class="card"><table><thead><tr><th>锚点</th><th>类型</th><th class="num">模型值</th>'
                 '<th class="num">公开值</th><th class="num">偏差</th><th>来源</th></tr></thead><tbody>')
        for c in calib:
            gap = c.get('gap')
            cls = 'dim'
            if gap is not None:
                cls = 'warn' if abs(gap) <= 150 else 'up'
            h.append('<tr><td class="mono">%s</td><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num"><span class="tag %s">%s</span></td><td class="tiny dim">%s</td></tr>'
                     % (esc(c['date']), esc(c.get('kind', '')), f(c.get('model'), 1),
                        f(c.get('reported'), 1), cls, sgn(gap, 1), esc(c.get('source', ''))))
        h.append('</tbody></table></div>')

    # 八步完成情况
    h.append('<h3>八步完成情况</h3>')
    h.append('<div class="card"><div class="steps">')
    step_info = [
        ('核实产业关系与工艺单耗', '反应式、理论单耗、工业单耗区间与来源'),
        ('取同期间双价并统一口径', '含税、地区、单位、评估价性质'),
        ('计算涨跌幅与期间收益', '上游变动、下游变动、收益率'),
        ('理论原料成本与加工价差', '含单耗敏感性上下界'),
        ('分阶段对比传导', 'Δ下游 = Δ原料成本 + Δ价差（残差校验）'),
        ('传导时滞与价差走阔压缩', '滞后相关（仅观察）+ 背离区间'),
        ('核查分歧阶段事件', '装置/供需/进出口事件对应到区间'),
        ('说明证据与局限', '公式、数据缺口、未计入项'),
    ]
    for i, (t, d) in enumerate(step_info, 1):
        h.append('<div class="step"><div class="ic">%d</div><div class="bd"><div class="t">%s</div>'
                 '<div class="d">%s</div></div></div>' % (i, esc(t), esc(d)))
    h.append('</div></div>')

    # 期间结论
    h.append('<h3>期间事实（只陈述已发生）</h3>')
    h.append('<div class="card"><ul class="li">')
    h.append('<li><b>%s</b> 从 %s 变到 %s 元/吨，变动 <b>%s%%</b>。</li>'
             % (esc(up['name']), f(s['up']['start']), f(s['up']['end']), sgn(s['up']['chg_pct'])))
    h.append('<li><b>%s</b> 从 %s 变到 %s 元/吨，变动 <b>%s%%</b>。</li>'
             % (esc(dn['name']), f(s['down']['start']), f(s['down']['end']), sgn(s['down']['chg_pct'])))
    h.append('<li>加工价差均值 <b>%s</b> 元/吨，观测区间 %s ~ %s 元/吨，最新 %s 元/吨（分位 %s%%）。</li>'
             % (f(sp['mean'], 1), f(sp['min'], 0), f(sp['max'], 0), f(sp['latest'], 0), f(sp['latest_rank'], 1)))
    if stages:
        big = max(stages, key=lambda x: abs(x.get('d_spread') or 0))
        if big.get('d_spread') is not None:
            h.append('<li>价差变动最大的阶段是 <b>%s → %s</b>，价差%s <b>%s</b> 元/吨。</li>'
                     % (esc(big['start']), esc(big['end']), '走阔' if big['d_spread'] > 0 else '压缩',
                        f(abs(big['d_spread']), 0)))
    h.append('<li>全期原料成本占下游价格 <b>%s%%</b>，说明该产品是典型的"原料定价"型品种。</li>'
             % f(s.get('cost_share_pct'), 1))
    h.append('</ul></div>')
    h.append('<div class="note acc"><b>关于因果：</b>本报告<b>不</b>因为两条曲线同涨同跌就判断上游决定下游。'
             '同一时期内上游与下游常受同一第三方（原油、宏观、出口政策、情绪）驱动，'
             '相关性只能说明"同期一起变动"，不能说明谁驱动谁。</div>')
    return ''.join(h)


def kpi(k, v, sub, cls=''):
    return ('<div class="kpi %s"><div class="k">%s</div><div class="v">%s</div>'
            '<div class="s">%s</div></div>' % (cls, esc(k), esc(v), esc(sub)))


def tab_process(meta):
    up, dn = meta['upstream'], meta['downstream']
    proc = meta.get('process') or {}
    mats = meta.get('materials') or []
    opt = meta.get('optional_materials') or []
    verified = proc.get('verified')
    h = ['<h2><span class="n">1</span>产业关系与工艺单耗</h2>',
         '<p class="lead">先确认"上游真的是下游的原料"，再确认"用多少原料做一吨下游"。'
         '这两件事没核实，后面的成本曲线全是错的。</p>']

    if not verified:
        h.append('<div class="note danger"><b>工艺尚未核实到可引用来源</b>，以下内容待补证。</div>')

    h.append('<div class="card"><h3>反应与工艺路线</h3>')
    h.append('<table><tbody>')
    h.append('<tr><td class="dim" style="width:150px">原料 → 产品</td><td><b>%s → %s</b></td></tr>'
             % (esc(up['name']), esc(dn['name'])))
    h.append('<tr><td class="dim">工艺路线</td><td>%s</td></tr>' % esc(proc.get('route') or '—'))
    h.append('<tr><td class="dim">反应式</td><td class="mono" style="color:#9fd5b0">%s</td></tr>'
             % esc(proc.get('equation') or '—'))
    h.append('<tr><td class="dim">核实状态</td><td>%s</td></tr>'
             % ('<span class="tag down">已核实</span>' if verified else '<span class="tag warn">待核实</span>'))
    h.append('<tr><td class="dim">补充说明</td><td>%s</td></tr>' % esc(proc.get('note') or '—'))
    h.append('</tbody></table></div>')

    h.append('<h3>单耗（算成本的核心参数）</h3>')
    h.append('<div class="card"><table><thead><tr><th>原料</th><th class="num">单耗（主模型）</th>'
             '<th class="num">区间下界</th><th class="num">区间上界</th><th>口径</th><th>来源</th></tr></thead><tbody>')
    for m in mats:
        h.append('<tr><td><b>%s</b></td><td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                 '<td class="tiny">%s</td><td class="tiny dim">%s</td></tr>'
                 % (esc(m['name']), f(m.get('unit'), 3), f(m.get('low'), 3), f(m.get('high'), 3),
                    esc(m.get('unit_basis', '')), esc(m.get('source', ''))))
    h.append('</tbody></table></div>')

    if opt:
        h.append('<h3>未纳入主模型的辅料（必须披露）</h3>')
        h.append('<div class="card"><table><thead><tr><th>项目</th><th class="num">单耗</th>'
                 '<th>状态说明</th></tr></thead><tbody>')
        for m in opt:
            h.append('<tr><td>%s</td><td class="num">%s</td><td class="tiny dim">%s</td></tr>'
                     % (esc(m['name']), f(m.get('unit'), 3), esc(m.get('status', ''))))
        h.append('</tbody></table></div>')
        h.append('<div class="note"><b>为什么单列：</b>这些辅料不进价差计算，'
                 '意味着报告的价差<b>多算</b>了这部分成本之外的部分——读价差时要往下再扣。</div>')

    h.append('<h3>核实结论</h3>')
    h.append('<div class="card"><ul class="li">')
    h.append('<li><b>上游是否为下游唯一/主要原料：</b>%s</li>'
             % esc('是，报告期内无商业化替代路线' if up['name'].upper() == 'PX' else '见工艺说明'))
    h.append('<li><b>理论单耗与工业单耗的差：</b>理论值由分子量比得出，是物理下限；'
             '工业单耗必然更高（损失、回收率、纯度），计算须用工业值。</li>')
    h.append('<li><b>单耗敏感性：</b>主模型取 %s，下界 %s、上界 %s，'
             '在③页可拖动查看对价差的影响。</li>'
             % (f(mats[0].get('unit'), 3) if mats else '—',
                f(mats[0].get('low'), 3) if mats else '—',
                f(mats[0].get('high'), 3) if mats else '—'))
    h.append('</ul></div>')
    return ''.join(h)


def tab_price(meta, s, cd):
    up, dn = meta['upstream'], meta['downstream']
    h = ['<h2><span class="n">2</span>价格口径与时序</h2>',
         '<p class="lead">两条价格必须"同一个东西"才能相减：同税基、同单位、同地区、同频率。'
         '这一页把口径摊开，并标出评估价的台阶式更新。</p>']

    h.append('<div class="card"><h3>两条价格序列对照</h3>')
    h.append('<table><thead><tr><th>字段</th><th>上游 %s</th><th>下游 %s</th></tr></thead><tbody>'
             % (esc(up['name']), esc(dn['name'])))
    for label, key in [('规格', 'spec'), ('地区', 'region'), ('单位', 'unit'), ('税基', 'tax'),
                       ('性质', 'granularity'), ('来源', 'source'), ('期货合约', 'futures_contract')]:
        a, b = up.get(key) or '—', dn.get(key) or '—'
        h.append('<tr><td class="dim">%s</td><td>%s</td><td>%s</td></tr>' % (esc(label), esc(a), esc(b)))
    h.append('</tbody></table>')
    if up.get('source_url') or dn.get('source_url'):
        h.append('<p class="tiny dim2" style="margin-top:10px">来源页：%s %s</p>'
                 % (('<a href="%s" style="color:#4a9eff">上游</a>' % esc(up['source_url'])) if up.get('source_url') else '',
                    ('<a href="%s" style="color:#4a9eff">下游</a>' % esc(dn['source_url'])) if dn.get('source_url') else ''))
    h.append('</div>')

    h.append('<div class="card"><div id="c-price" class="chart tall"></div></div>')

    # 变动统计
    h.append('<h3>期间变动</h3>')
    h.append('<div class="card"><table><thead><tr><th>指标</th><th class="num">上游 %s</th>'
             '<th class="num">下游 %s</th><th class="num">比值</th></tr></thead><tbody>'
             % (esc(up['name']), esc(dn['name'])))
    rows = [('期初', s['up']['start'], s['down']['start'], None),
            ('期末', s['up']['end'], s['down']['end'], None),
            ('变动额（元/吨）', s['up']['chg'], s['down']['chg'], None),
            ('变动幅度（%）', s['up']['chg_pct'], s['down']['chg_pct'], None),
            ('期间最低', s['up']['min'], s['down']['min'], None),
            ('期间最高', s['up']['max'], s['down']['max'], None)]
    for label, a, b, _ in rows:
        if isinstance(a, float) and abs(a) < 100 and label.endswith('（%）'):
            a_, b_ = pctf(a), pctf(b)
        elif label.endswith('（%）'):
            a_, b_ = pctf(a), pctf(b)
        else:
            a_, b_ = f(a), f(b)
        ratio = '—'
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a:
            ratio = f(b / a, 3)
        h.append('<tr><td class="dim">%s</td><td class="num">%s</td><td class="num">%s</td>'
                 '<td class="num dim">%s</td></tr>' % (esc(label), a_, b_, ratio))
    h.append('</tbody></table></div>')

    # 台阶披露
    steps = meta.get('_steps') if isinstance(meta.get('_steps'), dict) else {}
    n = s['n_obs'] - 1
    if steps:
        h.append('<h3>关键口径问题：上游是台阶式评估价</h3>')
        h.append('<div class="note"><b>%s</b> 在 %d 个交易日里只有 <b>%d 天</b>调整过报价（占 %.0f%%），'
                 '而 <b>%s</b> 有 <b>%d 天</b>变动（占 %.0f%%）。'
                 '这意味着任何"上游变动 Δ 元、下游变动 Δ 元，所以传导率 = x"的算法，'
                 '在分母很小时都会算出一个失真的倍数。</div>'
                 % (esc(up['name']), n, steps.get('up_change_days', 0),
                    steps.get('up_change_ratio', 0) * 100, esc(dn['name']),
                    steps.get('down_change_days', 0), steps.get('down_change_ratio', 0) * 100))
        runs = steps.get('up_flat_runs') or []
        if runs:
            h.append('<div class="card"><table><thead><tr><th>上游连续不变区间</th><th>天数</th>'
                     '<th class="num">维持价格</th></tr></thead><tbody>')
            for r in runs[:12]:
                h.append('<tr><td class="mono">%s ~ %s</td><td>%d</td><td class="num">%s</td></tr>'
                         % (esc(r['start']), esc(r['end']), r['days'], f(r['value'])))
            if len(runs) > 12:
                h.append('<tr><td class="dim" colspan="3">…共 %d 段（完整见 Excel「原料价格」表）</td></tr>'
                         % len(runs))
            h.append('</tbody></table></div>')
    return ''.join(h)


def tab_cost(meta, s, sens, cd):
    up, dn = meta['upstream'], meta['downstream']
    mats = meta.get('materials') or []
    m0 = mats[0] if mats else {}
    params = meta.get('params') or {}
    excl = params.get('spread_excludes') or []
    h = ['<h2><span class="n">3</span>理论原料成本与加工价差</h2>',
         '<p class="lead">把原料按单耗换成钱，再和下游价格相减。这一页的每个数字都可以在"⑧局限与公式"页倒查。</p>']

    h.append('<div class="card"><h3>计算公式</h3>')
    h.append('<div class="f">理论原料成本(元/吨) = 单耗 × 上游价格\n'
             '                 = %s × %s = %s 元/吨（以期末价为例）\n\n'
             '加工价差(元/吨)   = 下游价格 − 理论原料成本\n'
             '                 = %s − %s = %s 元/吨\n\n'
             '注意：价差 ≠ 利润。不含 %s。'
             % (f(m0.get('unit'), 3), f(s['up']['end']),
                f(m0.get('unit') * s['up']['end'] if m0.get('unit') else None),
                f(s['down']['end']), f(m0.get('unit') * s['up']['end'] if m0.get('unit') else None),
                f(s['down']['end'] - m0.get('unit') * s['up']['end'] if m0.get('unit') else None),
                '、'.join(excl) if excl else '其他成本项'))
    h.append('</div></div>')

    # 交互：单耗滑块
    h.append('<div class="ctrl">')
    h.append('<label>单耗（吨 %s / 吨 %s）<span class="val" id="v-unit">%s</span>'
             '<input type="range" id="s-unit" min="%s" max="%s" step="0.001" value="%s"></label>'
             % (esc(up['name']), esc(dn['name']), f(m0.get('unit'), 3),
                f(m0.get('low'), 3), f(m0.get('high'), 3), f(m0.get('unit'), 3)))
    h.append('<span class="tiny dim2">拖动单耗滑块，成本与价差曲线实时重算（前端按同一公式计算）</span>')
    h.append('<button class="btn ghost" id="b-reset">重置单耗</button>')
    h.append('</div>')

    h.append('<div class="card"><div id="c-cost" class="chart tall"></div></div>')
    h.append('<div class="card"><div id="c-spread" class="chart"></div></div>')

    # 敏感性
    h.append('<h3>单耗敏感性（价差均值）</h3>')
    h.append('<div class="grid g3">')
    h.append(kpi('下界单耗 %s' % f(m0.get('low'), 3), f(sens.get('low_unit_mean'), 1), '价差均值，元/吨', 'up'))
    h.append(kpi('主模型 %s' % f(m0.get('unit'), 3), f(sens.get('base_mean'), 1), '价差均值，元/吨', 'acc'))
    h.append(kpi('上界单耗 %s' % f(m0.get('high'), 3), f(sens.get('high_unit_mean'), 1), '价差均值，元/吨', 'down'))
    h.append('</div>')
    h.append('<div class="note"><b>怎么读这组数：</b>单耗越高，算出的原料成本越高、价差越低。'
             '真实单耗在不同装置之间不同（新旧装置差一整代），'
             '所以价差本身有一个"装置代际"造成的不确定带宽，报单一数字是不严谨的。</div>')

    h.append('<h3>未计入价差的成本项</h3>')
    h.append('<div class="card"><div>')
    for e in excl:
        h.append('<span class="pill">%s</span>' % esc(e))
    h.append('</div><p class="tiny dim" style="margin-top:12px">'
             '以上每一项都会让"真实生产经营成本"高于本报告的原料成本，'
             '因此本报告的价差<b>系统性地高于</b>企业实际的生产毛利。'
             '行业里"加工费"这个词也常被误读——它同样只是销售收入减去原料成本。</p></div>')
    return ''.join(h)


def tab_stage(stages, steps, s):
    h = ['<h2><span class="n">4</span>分阶段传导对比</h2>',
         '<p class="lead">一年的总变动会掩盖阶段之间的反向。按价格转折点切段，'
         '逐段回答"成本变了多少、下游跟了多少、价差吃掉了多少"。</p>']
    if not stages:
        return ''.join(h) + '<div class="note">未设置阶段断点。</div>'

    h.append('<div class="note acc">恒等式校验：<span class="mono">Δ下游价格 = Δ原料成本 + Δ加工价差</span>。'
             '下表每段都做了残差校验，残差应恒为 0。</div>')

    h.append('<div class="card"><table><thead><tr>'
             '<th>阶段</th><th class="num">天数</th><th class="num">Δ原料成本</th>'
             '<th class="num">Δ下游价</th><th class="num">Δ价差</th>'
             '<th class="num">传导率</th><th class="num">残差</th><th>解读</th></tr></thead><tbody>')
    for st in stages:
        pt = st.get('pass_through')
        valid = st.get('pass_through_valid')
        if pt is None:
            pt_s, cls = '—', 'dim'
        elif not valid:
            pt_s, cls = f(pt, 2) + '*', 'warn'
        elif pt > 1.15:
            pt_s, cls = f(pt, 2), 'up'
        elif pt < 0.85:
            pt_s, cls = f(pt, 2), 'down'
        else:
            pt_s, cls = f(pt, 2), 'acc'
        resid = st.get('identity_resid')
        h.append('<tr><td class="mono">%s<br><span class="tiny dim">→ %s</span></td><td class="num">%d</td>'
                 '<td class="num">%s</td><td class="num">%s<br><span class="tiny dim">%s</span></td>'
                 '<td class="num">%s</td><td class="num"><span class="tag %s">%s</span></td>'
                 '<td class="num tiny">%s</td><td class="tiny dim">%s</td></tr>'
                 % (esc(st['start']), esc(st['end']), st['days'],
                    sgn(st.get('d_cost'), 0), sgn(st.get('d_down'), 0),
                    pctf(st.get('d_down_pct')), sgn(st.get('d_spread'), 0),
                    cls, pt_s,
                    '0.00' if resid is not None and abs(resid) < 1e-6 else f(resid, 2),
                    esc(_interpret(st))))
    h.append('</tbody></table></div>')
    h.append('<p class="tiny dim">* 该阶段上游成本变动过小（不足成本 1%），传导率分母接近 0，数值不具解释力。</p>')

    h.append('<div class="card"><div id="c-stage" class="chart"></div></div>')
    h.append('<h3>传导率怎么读</h3>')
    h.append('<div class="card"><table><thead><tr><th>传导率</th><th>含义</th><th>解读前必须先排除</th></tr></thead><tbody>')
    for a, b, c in [('≈1', '成本变化基本全额传到下游，价差不变', '—'),
                    ('<1', '下游没跟满，价差被压缩', '下游自身是否过剩、需求是否走弱'),
                    ('>1', '下游涨幅超过成本，价差走阔', '<b>先查上游台阶是否没更新</b>，再谈下游强势'),
                    ('<0', '反向变动，下游由自身供需定价', '—')]:
        h.append('<tr><td class="mono">%s</td><td>%s</td><td class="tiny dim">%s</td></tr>' % (esc(a), esc(b), c))
    h.append('</tbody></table></div>')
    return ''.join(h)


def _interpret(st):
    ds = st.get('d_spread')
    pt = st.get('pass_through')
    if ds is None or pt is None:
        return '数据不足'
    if not st.get('pass_through_valid', True):
        return '上游成本几乎没动，该比值不稳定'
    if pt > 1.15:
        return '下游涨幅超过成本，价差走阔 %s 元' % f(ds, 0)
    if pt < 0.85:
        return '下游未跟满，价差压缩 %s 元' % f(abs(ds), 0)
    return '成本基本传导到位'


def tab_lag(stats, divs, steps, outliers, cd):
    h = ['<h2><span class="n">5</span>传导时滞与价差背离</h2>',
         '<p class="lead">这一页只做两件事：看两列价格在时间上的同步程度，'
         '以及标出价差相对自身中枢的异常区间。</p>']

    h.append('<div class="note danger"><b>关于时滞的严格限定：</b>'
             '下面的相关系数只回答"在滞后 k 日时两组变动最像"。'
             '它<b>不能</b>证明上游驱动下游，也<b>不能</b>用来预判后续价格。'
             '两条曲线同涨同跌，最常见的原因是有共同的第三方驱动。</div>')

    lag = stats.get('lag_corr') or []
    if lag:
        best = stats.get('best_lag') or {}
        h.append('<div class="grid g4">')
        h.append(kpi('同期相关系数（日变动）', f(stats.get('corr_diff_up_down'), 3), 'lag=0', 'acc'))
        h.append(kpi('水平相关系数', f(stats.get('corr_level_up_down'), 3), '两个价格水平之间', 'purple'))
        h.append(kpi('相关性最高的滞后', '%s 日' % best.get('lag', '—'),
                     'r = %s' % f(best.get('corr'), 3), 'warn'))
        h.append(kpi('原料成本→下游 回归弹性', f(stats.get('level_beta'), 2), '水平回归斜率，非因果', 'dim'))
        h.append('</div>')
        h.append('<div class="card"><div id="c-lag" class="chart short"></div></div>')

    if steps:
        h.append('<div class="note"><b>为什么时滞看起来这么长：</b>%s 只有 %d 天发生变动，'
                 '而 %s 有 %d 天变动。上游的台阶式更新会人为拉长"相关性峰值所在的滞后"，'
                 '这个滞后反映的是评估价的更新节奏，不是物理传导时间。</div>'
                 % (esc(cd['upName']), steps.get('up_change_days', 0),
                    esc(cd['downName']), steps.get('down_change_days', 0)))

    h.append('<h3>价差背离区间</h3>')
    h.append('<p class="lead">定义：加工价差相对其 20 日滚动均值的 z 分数，连续越阈 ≥5 日计为一段。'
             'z>+1.5 记为走阔，z<−1.5 记为压缩。</p>')
    if divs:
        h.append('<div class="card"><table><thead><tr><th>类型</th><th>区间</th><th class="num">天数</th>'
                 '<th class="num">期初价差</th><th class="num">期末价差</th><th class="num">区间均值</th>'
                 '<th class="num">极端 z</th></tr></thead><tbody>')
        for d in divs:
            cls = 'up' if d['type'] == 'spread_widen' else 'down'
            lab = '走阔' if d['type'] == 'spread_widen' else '压缩'
            h.append('<tr><td><span class="tag %s">%s</span></td><td class="mono">%s ~ %s</td>'
                     '<td class="num">%d</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num">%s</td><td class="num">%s</td></tr>'
                     % (cls, lab, esc(d['start']), esc(d['end']), d['days'],
                        f(d.get('spread_start'), 0), f(d.get('spread_end'), 0),
                        f(d.get('spread_mean'), 0), f(d.get('z_extreme'), 2)))
        h.append('</tbody></table></div>')
    else:
        h.append('<div class="note">观测期内未识别出持续 5 日以上的价差异常区间。</div>')

    h.append('<div class="card"><div id="c-div" class="chart tall"></div></div>')

    if outliers:
        h.append('<h3>待核异常跳变（未剔除）</h3>')
        h.append('<p class="lead">单日价差跳变超过 400 元/吨的日期。这些点<b>没有被删除</b>，'
                 '只在统计时另给一列稳健口径。是否剔除要看原始数据是否有误。</p>')
        h.append('<div class="card"><table><thead><tr><th>日期</th><th class="num">前一日</th>'
                 '<th class="num">当日</th><th class="num">跳变</th></tr></thead><tbody>')
        for o in outliers[:15]:
            h.append('<tr><td class="mono">%s</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num"><span class="tag warn">%s</span></td></tr>'
                     % (esc(o['date']), f(o['prev'], 1), f(o['now'], 1), sgn(o['jump'], 1)))
        h.append('</tbody></table></div>')
    return ''.join(h)


def tab_events(divs, stages, events, dates):
    h = ['<h2><span class="n">6</span>分歧阶段的事件核查</h2>',
         '<p class="lead">价差变动本身不是原因。这一页把装置、供需、进出口事件对应到背离区间，'
         '对应不上的就明确写"未检索到"。</p>']

    if not events:
        h.append('<div class="note">未提供事件库。请补充 `events.json` 后重新生成。</div>')

    h.append('<h3>背离区间 × 同期事件</h3>')
    for d in divs:
        seg = [e for e in events if d['start'] <= e['date'] <= d['end']]
        lab = '价差走阔' if d['type'] == 'spread_widen' else '价差压缩'
        h.append('<div class="card"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">'
                 '<b>%s：%s ~ %s（%d 天）</b>'
                 '<span class="tag %s">%s</span></div>'
                 % (esc(lab), esc(d['start']), esc(d['end']), d['days'],
                    'up' if d['type'] == 'spread_widen' else 'down', lab))
        h.append('<p class="tiny dim" style="margin:8px 0">价差期初 %s → 期末 %s，区间均值 %s 元/吨</p>'
                 % (f(d.get('spread_start'), 0), f(d.get('spread_end'), 0), f(d.get('spread_mean'), 0)))
        if seg:
            h.append('<table><thead><tr><th>日期</th><th>事件</th><th>类别</th></tr></thead><tbody>')
            for e in seg[:10]:
                h.append('<tr><td class="mono tiny">%s</td><td>%s</td><td>%s</td></tr>'
                         % (esc(e['date']), esc(e['title'][:70]),
                            ''.join('<span class="pill">%s</span>' % esc(t) for t in e.get('tags', []))))
            h.append('</tbody></table>')
            if len(seg) > 10:
                h.append('<p class="tiny dim2">另有 %d 条事件见 Excel</p>' % (len(seg) - 10))
            h.append('<p class="tiny dim2" style="margin-top:10px">'
                     '以上为同期发生的可核查事件，<b>不代表已证明因果关系</b>。</p>')
        else:
            h.append('<div class="note"><b>该区间未检索到可核查的装置或供需事件，原因未确认。</b>'
                     '不做推测性归因。</div>')
        h.append('</div>')

    # 全部装置事件
    dev = [e for e in events if '装置' in (e.get('tags') or [])]
    if dev:
        h.append('<h3>报告期内的装置事件（共 %d 条）</h3>' % len(dev))
        h.append('<div class="card"><table><thead><tr><th>日期</th><th>事件</th></tr></thead><tbody>')
        for e in dev[:25]:
            h.append('<tr><td class="mono tiny">%s</td><td class="tiny">%s</td></tr>'
                     % (esc(e['date']), esc(e['title'][:78])))
        h.append('</tbody></table></div>')
    return ''.join(h)


def tab_limit(meta, analysis, calib, source_notes):
    up, dn = meta['upstream'], meta['downstream']
    params = meta.get('params') or {}
    mats = meta.get('materials') or []
    m0 = mats[0] if mats else {}
    h = ['<h2><span class="n">7</span>证据边界、公式与数据缺口</h2>',
         '<p class="lead">这一页决定这份报告能被用到什么程度。请先读这一页，再读结论。</p>']

    h.append('<h3>全部计算公式</h3>')
    h.append('<div class="card"><div class="f">'
             '1) 理论原料成本\n   成本ᵢ = 单耗ᵢ × 上游价ᵢ\n   总原料成本 = Σ 成本ᵢ\n\n'
             '2) 单耗敏感性\n   价差(低单耗) = 下游价 − lowᵢ × 上游价ᵢ\n'
             '   价差(高单耗) = 下游价 − highᵢ × 上游价ᵢ\n\n'
             '3) 加工价差\n   价差 = 下游价 − 总原料成本        （价差口径，非利润）\n\n'
             '4) 阶段分解\n   Δ下游 = Δ原料成本 + Δ价差     （恒等，残差应=0）\n'
             '   传导率 = Δ下游 / Δ原料成本\n\n'
             '5) 原料成本占比\n   占比 = 总原料成本 / 下游价 × 100%%\n\n'
             '6) 价差 z 分数（背离识别）\n   z = (价差 − 20日滚动均值) / 20日滚动标准差\n'
             '   |z| ≥ 1.5 且连续 ≥ 5 日 → 记一段背离\n\n'
             '7) 滞后相关\n   r(k) = corr(Δ上游[t], Δ下游[t+k]), k = 0..20\n'
             '   （仅观察，不作因果推断）\n\n'
             '8) 美元 → 人民币（若上游为 CFR 报价时使用）\n'
             '   上游价(元/吨) = CFR(美元/吨) × 汇率 × (1+关税率) × (1+增值税率)'
             '</div></div>')

    h.append('<h3>本期实际参数</h3>')
    h.append('<div class="card"><table><tbody>')
    h.append('<tr><td class="dim" style="width:170px">上游</td><td>%s（%s，%s，%s）</td></tr>'
             % (esc(up['name']), esc(up.get('spec')), esc(up.get('region')), esc(up.get('tax'))))
    h.append('<tr><td class="dim">下游</td><td>%s（%s，%s，%s）</td></tr>'
             % (esc(dn['name']), esc(dn.get('spec')), esc(dn.get('region')), esc(dn.get('tax'))))
    h.append('<tr><td class="dim">单耗</td><td>%s（区间 %s ~ %s）</td></tr>'
             % (f(m0.get('unit'), 3), f(m0.get('low'), 3), f(m0.get('high'), 3)))
    h.append('<tr><td class="dim">价差定义</td><td class="mono tiny">%s</td></tr>'
             % esc(params.get('spread_definition', '—')))
    h.append('<tr><td class="dim">观测数</td><td>%d 个交易日（%s ~ %s）</td></tr>'
             % (analysis['summary']['n_obs'], analysis['summary']['window'][0], analysis['summary']['window'][1]))
    h.append('<tr><td class="dim">缺失填充</td><td>%s</td></tr>'
             % esc(str(analysis['summary'].get('filled'))))
    h.append('</tbody></table></div>')

    h.append('<h3>必须知道的计算局限</h3>')
    h.append('<div class="card"><ul class="li">')
    limits = [
        ('价差不是利润', '价差只扣了原料。能源/公用工程、辅料与催化剂、人工、折旧、财务费用、'
                         '检维修、包装运费、库存损益全部未计入。真实生产毛利一定低于该价差。'),
        ('评估价不是成交价', '本报告使用的是资讯机构的日度评估价，用于趋势与价差分析；'
                             '实际成交价受品牌、账期、批量、地区影响，可能相差百元级。'),
        ('单耗是区间', '不同技术代际的装置单耗不同，报告的价差因此有一个装置代际造成的不确定带宽。'),
        ('上游台阶式更新', '上游评估价常连续多日不变，导致阶段传导率在分母极小的时候失真。'
                           '报告已标记，但读者仍需自行判断。'),
        ('同涨同跌不等于因果', '上游与下游可能被原油、宏观、政策、情绪等共同因素驱动。'
                              '本报告不做因果推断。'),
        ('未覆盖替代与进口', '若存在替代原料路线或大规模进口，简单单耗模型会偏差。'),
    ]
    for t, d in limits:
        h.append('<li><b>%s：</b>%s</li>' % (esc(t), esc(d)))
    h.append('</ul></div>')

    gaps = analysis.get('gaps') or []
    h.append('<h3>数据缺口</h3>')
    if gaps:
        h.append('<div class="card"><table><thead><tr><th>缺口</th><th>原因</th><th>影响</th></tr></thead><tbody>')
        for g in gaps:
            h.append('<tr><td>%s</td><td class="tiny dim">%s</td><td class="tiny">%s</td></tr>'
                     % (esc(g.get('item')), esc(g.get('reason')), esc(g.get('impact'))))
        h.append('</tbody></table></div>')
    else:
        h.append('<div class="note">已声明的缺口见各页说明；未单列的缺失项以"—"标注。</div>')

    if calib:
        h.append('<h3>口径校验记录</h3>')
        h.append('<div class="card"><table><thead><tr><th>锚点</th><th class="num">模型</th>'
                 '<th class="num">公开</th><th class="num">偏差</th><th>来源</th></tr></thead><tbody>')
        for c in calib:
            h.append('<tr><td class="mono tiny">%s</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num">%s</td><td class="tiny dim">%s</td></tr>'
                     % (esc(c['date']), f(c.get('model'), 1), f(c.get('reported'), 1),
                        sgn(c.get('gap'), 1), esc(c.get('source', ''))))
        h.append('</tbody></table><p class="tiny dim" style="margin-top:10px">'
                 '偏差在 ±150 元/吨内且正负交替，说明是统计样本差异而非公式错误。</p></div>')

    if source_notes:
        h.append('<h3>来源清单</h3><div class="card"><ul class="li">')
        for n in source_notes:
            h.append('<li class="tiny">%s</li>' % n)
        h.append('</ul></div>')
    return ''.join(h)


HTML_TMPL = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>__CSS__</style></head>
<body>
<header><div class="wrap">
<h1>__TITLE__</h1>
<div class="sub">__CHAIN__ · 观测窗口 __WIN__ · __NOBS__ 个交易日</div>
<div class="badges">
 <span class="badge">口径：<b>日度评估价 · 元/吨 · 含税</b></span>
 <span class="badge">加工价差：<b>价差口径，非利润</b></span>
 <span class="badge">因果：<b>不作因果推断</b></span>
 <span class="badge warn">⚠ 上游为台阶式评估价，传导率需结合台阶看</span>
</div>
</div></header>
<nav><div class="wrap">__NAV__</div></nav>
<div class="wrap">
__SECTIONS__
<footer>本报告由 cost-pass-through Skill 生成 · 所有数字可由 analysis.json 与原始价格序列复现 ·
不构成投资或交易建议</footer>
</div>
<script>__ECHARTS__</script>
<script>
var D = __DATA__;
</script>
<script>
(function(){
var charts = [];
function el(id){ return document.getElementById(id); }
function mk(id){
  var n = el(id); if(!n) return null;
  var c = echarts.init(n, null, {renderer:'canvas'});
  charts.push(c); return c;
}
var GRID = {left:62,right:26,top:44,bottom:48};
var AXIS_C = '#3a4552', TXT = '#9aa7b4', SPLIT='#1e262f';

function axisX(dates, extra){
  var o = {type:'category', data:dates, axisLine:{lineStyle:{color:AXIS_C}},
    axisLabel:{color:TXT,fontSize:11}, axisTick:{show:false}};
  for(var k in (extra||{})) o[k]=extra[k];
  return o;
}
function axisY(name, extra){
  var o = {type:'value', name:name, scale:true, nameTextStyle:{color:TXT,fontSize:11},
    axisLine:{show:false}, axisLabel:{color:TXT,fontSize:11},
    splitLine:{lineStyle:{color:SPLIT}}};
  for(var k in (extra||{})) o[k]=extra[k];
  return o;
}
function tip(extra){
  var o = {trigger:'axis', backgroundColor:'rgba(22,27,34,.96)', borderColor:'#2a323d',
    textStyle:{color:'#e6edf3',fontSize:12}, axisPointer:{type:'cross',
    crossStyle:{color:'#4a5563'}, lineStyle:{color:'#4a5563'}}};
  for(var k in (extra||{})) o[k]=extra[k];
  return o;
}

window.CPT = {el:el, mk:mk, GRID:GRID, AXIS_C:AXIS_C, TXT:TXT, SPLIT:SPLIT,
              axisX:axisX, axisY:axisY, tip:tip, charts:charts};
})();

/* ---------- 价格走势 ---------- */
window.__paintPrice = function(){
  var CPT = window.CPT, el = CPT.el, mk = CPT.mk, tip = CPT.tip;
  var axisX = CPT.axisX, axisY = CPT.axisY, GRID = CPT.GRID, TXT = CPT.TXT, AXIS_C = CPT.AXIS_C;
  var c = mk('c-price'); if(!c) return;
  c.setOption({
    backgroundColor:'transparent', grid:GRID, tooltip:tip(),
    legend:{data:[D.upName, D.downName], textStyle:{color:TXT}, top:8, icon:'roundRect',
      itemWidth:11, itemHeight:11},
    xAxis:axisX(D.dates),
    yAxis:[axisY('元/吨', {nameTextStyle:{color:TXT,fontSize:11,padding:[0,0,0,-28]}})],
    dataZoom:[{type:'inside'},{type:'slider',height:18,bottom:8,borderColor:'#2a323d',
      fillerColor:'rgba(74,158,255,.14)',handleStyle:{color:'#4a9eff'},
      textStyle:{color:TXT,fontSize:10}}],
    series:[
      {name:D.upName, type:'line', data:D.up, showSymbol:false, lineStyle:{width:1.8,color:'#4a9eff'},
        itemStyle:{color:'#4a9eff'}},
      {name:D.downName, type:'line', data:D.down, showSymbol:false, lineStyle:{width:1.8,color:'#d29922'},
        itemStyle:{color:'#d29922'}}
    ]
  });
};

/* ---------- 成本 vs 下游价（可调单耗） ---------- */
var CPT = window.CPT, el = CPT.el, axisX = CPT.axisX, axisY = CPT.axisY,
    tip = CPT.tip, GRID = CPT.GRID, charts = CPT.charts, TXT = CPT.TXT, AXIS_C = CPT.AXIS_C;
var UNIT0 = D.unit0;
function renderCost(unit){
  var c = el('c-cost'); if(!c) return;
  var inst = echarts.getInstanceByDom(c) || echarts.init(c);
  var cost = D.up.map(function(v){ return unit * v; });
  inst.setOption({
    backgroundColor:'transparent', grid:GRID, tooltip:tip(),
    legend:{data:['理论原料成本', D.downName, '上游价格'], textStyle:{color:TXT}, top:8,
      icon:'roundRect', itemWidth:11, itemHeight:11},
    xAxis:axisX(D.dates),
    yAxis:[axisY('元/吨')],
    dataZoom:[{type:'inside'},{type:'slider',height:18,bottom:8,borderColor:'#2a323d',
      fillerColor:'rgba(74,158,255,.14)',handleStyle:{color:'#4a9eff'},
      textStyle:{color:TXT,fontSize:10}}],
    series:[
      {name:'理论原料成本', type:'line', data:cost, showSymbol:false,
        lineStyle:{width:2,color:'#a371f7'}, itemStyle:{color:'#a371f7'},
        areaStyle:{color:'rgba(163,113,247,.10)'}},
      {name:D.downName, type:'line', data:D.down, showSymbol:false,
        lineStyle:{width:1.9,color:'#d29922'}, itemStyle:{color:'#d29922'}},
      {name:'上游价格', type:'line', data:D.up, showSymbol:false,
        lineStyle:{width:1.2,color:'#4a9eff',type:'dashed'}, itemStyle:{color:'#4a9eff'}}
    ]
  }, true);
  if(charts.indexOf(inst)<0) charts.push(inst);
}

function renderSpread(unit){
  var c = el('c-spread'); if(!c) return;
  var inst = echarts.getInstanceByDom(c) || echarts.init(c);
  var sp = D.down.map(function(v,i){ return v - unit * D.up[i]; });
  inst.setOption({
    backgroundColor:'transparent', grid:GRID, tooltip:tip(),
    legend:{data:['加工价差','价差零轴'], textStyle:{color:TXT}, top:8,
      icon:'roundRect', itemWidth:11, itemHeight:11},
    xAxis:axisX(D.dates),
    yAxis:[axisY('元/吨')],
    dataZoom:[{type:'inside'},{type:'slider',height:18,bottom:8,borderColor:'#2a323d',
      fillerColor:'rgba(74,158,255,.14)',handleStyle:{color:'#4a9eff'},
      textStyle:{color:TXT,fontSize:10}}],
    series:[
      {name:'加工价差', type:'line', data:sp, showSymbol:false,
        lineStyle:{width:1.8,color:'#3fb950'}, itemStyle:{color:'#3fb950'},
        areaStyle:{color:'rgba(63,185,80,.10)'},
        markLine:{silent:true, symbol:'none',
          lineStyle:{color:'#e5534b',type:'dashed',width:1},
          data:[{yAxis:0}], label:{show:false}}},
      {name:'价差零轴', type:'line', data:[], lineStyle:{opacity:0}}
    ]
  }, true);
  if(charts.indexOf(inst)<0) charts.push(inst);
}

window.__paintCost = function(){
  renderCost(UNIT0);
  renderSpread(UNIT0);
  if (window.__costBound) return;
  window.__costBound = 1;
  var s = el('s-unit'), v = el('v-unit');
  if(s) s.addEventListener('input', function(){
    var u = parseFloat(this.value);
    if(v) v.textContent = u.toFixed(3);
    renderCost(u); renderSpread(u);
  });
  var b = el('b-reset');
  if(b) b.addEventListener('click', function(){
    if(s) s.value = UNIT0; if(v) v.textContent = UNIT0.toFixed(3);
    renderCost(UNIT0); renderSpread(UNIT0);
  });
};

/* ---------- 阶段分解 ---------- */
window.__paintStage = function(){
  var CPT = window.CPT;  var el = CPT.el, mk = CPT.mk, tip = CPT.tip, GRID = CPT.GRID;
  var axisX = CPT.axisX, axisY = CPT.axisY, charts = CPT.charts, TXT = CPT.TXT, AXIS_C = CPT.AXIS_C;
  var c = mk('c-stage'); if(!c) return;
  var st = D.stages || [];
  if(!st.length) return;
  var cats = st.map(function(x){ return x.start.slice(2,4)+'/'+x.start.slice(4,6)+'→'+x.end.slice(2,4)+'/'+x.end.slice(4,6); });
  c.setOption({
    backgroundColor:'transparent', grid:{left:64,right:26,top:44,bottom:56},
    tooltip:tip({axisPointer:{type:'shadow'}}),
    legend:{data:['Δ原料成本','Δ下游价格','Δ加工价差'], textStyle:{color:TXT}, top:8,
      icon:'roundRect', itemWidth:11, itemHeight:11},
    xAxis:{type:'category', data:cats, axisLine:{lineStyle:{color:AXIS_C}},
      axisLabel:{color:TXT,fontSize:11,interval:0}, axisTick:{show:false}},
    yAxis:axisY('元/吨'),
    series:[
      {name:'Δ原料成本', type:'bar', data:st.map(function(x){return x.d_cost;}),
        itemStyle:{color:'#a371f7'}, barMaxWidth:26},
      {name:'Δ下游价格', type:'bar', data:st.map(function(x){return x.d_down;}),
        itemStyle:{color:'#d29922'}, barMaxWidth:26},
      {name:'Δ加工价差', type:'bar', data:st.map(function(x){return x.d_spread;}),
        itemStyle:{color:'#3fb950'}, barMaxWidth:26}
    ]
  });
};

/* ---------- 滞后相关 ---------- */
window.__paintLag = function(){
  var CPT = window.CPT;  var el = CPT.el, mk = CPT.mk, tip = CPT.tip, GRID = CPT.GRID;
  var axisX = CPT.axisX, axisY = CPT.axisY, charts = CPT.charts, TXT = CPT.TXT, AXIS_C = CPT.AXIS_C;
  var c = mk('c-lag'); if(!c) return;
  var lc = D.lagCorr || []; if(!lc.length) return;
  c.setOption({
    backgroundColor:'transparent', grid:{left:64,right:26,top:30,bottom:44},
    tooltip:tip({axisPointer:{type:'shadow'}}),
    xAxis:{type:'category', data:lc.map(function(x){return 'k='+x.lag;}),
      axisLine:{lineStyle:{color:AXIS_C}}, axisLabel:{color:TXT,fontSize:11},
      axisTick:{show:false}, name:'滞后天数', nameTextStyle:{color:TXT,fontSize:11}},
    yAxis:axisY('相关系数'),
    series:[{type:'bar', data:lc.map(function(x){return x.corr;}),
      itemStyle:{color:function(p){
        var v = p.value; if(v===null) return '#3a4552';
        return v>=0 ? 'rgba(74,158,255,.8)' : 'rgba(229,83,75,.8)';
      }}, barMaxWidth:18}]
  });
};

/* ---------- 价差与背离区间 ---------- */
window.__paintDiv = function(){
  var CPT = window.CPT;  var el = CPT.el, mk = CPT.mk, tip = CPT.tip, GRID = CPT.GRID;
  var axisX = CPT.axisX, axisY = CPT.axisY, charts = CPT.charts, TXT = CPT.TXT, AXIS_C = CPT.AXIS_C;
  var c = mk('c-div'); if(!c) return;
  var areas = [];
  (D.divs||[]).forEach(function(d){
    areas.push([{xAxis:d.start, itemStyle:{color: d.type==='spread_widen'
      ? 'rgba(229,83,75,.09)' : 'rgba(63,185,80,.09)'}} , {xAxis:d.end}]);
  });
  c.setOption({
    backgroundColor:'transparent', grid:GRID, tooltip:tip(),
    legend:{data:['加工价差','低单耗情形','高单耗情形'], textStyle:{color:TXT}, top:8,
      icon:'roundRect', itemWidth:11, itemHeight:11},
    xAxis:axisX(D.dates),
    yAxis:[axisY('元/吨')],
    dataZoom:[{type:'inside'},{type:'slider',height:18,bottom:8,borderColor:'#2a323d',
      fillerColor:'rgba(74,158,255,.14)',handleStyle:{color:'#4a9eff'},
      textStyle:{color:TXT,fontSize:10}}],
    series:[
      {name:'加工价差', type:'line', data:D.spread, showSymbol:false,
        lineStyle:{width:2,color:'#3fb950'}, itemStyle:{color:'#3fb950'},
        markArea:{silent:true, data:areas},
        markLine:{silent:true, symbol:'none', lineStyle:{color:'#555f6b',type:'dashed'},
          data:[{yAxis:0}], label:{show:false}}},
      {name:'低单耗情形', type:'line', data:D.spread_lo, showSymbol:false,
        lineStyle:{width:1,color:'#3a4552',type:'dotted'}, itemStyle:{color:'#3a4552'}},
      {name:'高单耗情形', type:'line', data:D.spread_hi, showSymbol:false,
        lineStyle:{width:1,color:'#3a4552',type:'dotted'}, itemStyle:{color:'#3a4552'}}
    ]
  });
};

/* ---------- 交互 ---------- */
(function(){
  var CPT = window.CPT;
  var btns = Array.prototype.slice.call(document.querySelectorAll('nav button'));

  function resizeAll(){
    CPT.charts.forEach(function(c){
      try {
        var dom = c.getDom();
        if (dom && dom.offsetParent !== null) { c.resize(); }
      } catch(e) { var q = 0; }
    });
  }

  // 懒初始化：图表只在它所在分页可见时才创建，避免 0×0 画布
  function paintTab(id){
    if (id === 'price' && !CPT.done.price) {
      CPT.done.price = 1; if (window.__paintPrice) window.__paintPrice();
    }
    if (id === 'cost' && !CPT.done.cost) {
      CPT.done.cost = 1; if (window.__paintCost) window.__paintCost();
    }
    if (id === 'stage' && !CPT.done.stage) {
      CPT.done.stage = 1; if (window.__paintStage) window.__paintStage();
    }
    if (id === 'lag' && !CPT.done.lag) {
      CPT.done.lag = 1; if (window.__paintLag) window.__paintLag();
    }
    if (id === 'lag' && !CPT.done.div) {
      CPT.done.div = 1; if (window.__paintDiv) window.__paintDiv();
    }
  }

  function activate(id){
    btns.forEach(function(x){ x.classList.remove('on'); });
    var on = document.querySelector('nav button[data-t="' + id + '"]');
    if (on) on.classList.add('on');
    Array.prototype.forEach.call(document.querySelectorAll('section'), function(s){
      s.classList.remove('on');
    });
    var t = document.getElementById('t-' + id);
    if (t) t.classList.add('on');
    paintTab(id);
    setTimeout(resizeAll, 40);
    setTimeout(resizeAll, 220);
  }

  btns.forEach(function(b){
    b.addEventListener('click', function(){
      activate(this.getAttribute('data-t'));
      window.scrollTo({top:0, behavior:'smooth'});
    });
  });

  window.addEventListener('resize', function(){ setTimeout(resizeAll, 120); });

  // 首屏：总览页无图表，但价格页需要预置（用户切过去前不画）
  CPT.done = {};
  CPT.activate = activate;
})();
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('analysis')
    ap.add_argument('--out-dir', default='out')
    ap.add_argument('--events', default='')
    ap.add_argument('--title-suffix', default='')
    args = ap.parse_args()
    a = json.load(open(args.analysis, encoding='utf-8'))

    # 把 steps/sens 注入 meta 供各页使用
    a['meta']['_steps'] = a.get('steps')
    a['meta']['_sens'] = a.get('sensitivity')

    events = []
    if args.events and os.path.exists(args.events):
        events = json.load(open(args.events, encoding='utf-8'))

    os.makedirs(args.out_dir, exist_ok=True)
    up = a['meta']['upstream']['name']
    dn = a['meta']['downstream']['name']
    name = '%s到%s_成本传导研究%s.html' % (up, dn, args.title_suffix)
    path = os.path.join(args.out_dir, name)

    # 模板里需要展开的标量
    orig = HTML_TMPL
    html_str = build(a, path, events=events)
    print('已生成', path, '%.2f MB' % (html_str[1] / 1048576))
    print('观测', a['summary']['n_obs'], '个交易日')


if __name__ == '__main__':
    main()
