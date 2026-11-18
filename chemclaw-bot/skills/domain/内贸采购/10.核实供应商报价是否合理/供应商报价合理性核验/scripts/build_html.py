# -*- coding: utf-8 -*-
"""把 model.json 渲染成单文件离线 HTML 报告。"""
import argparse
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TPL = os.path.join(SKILL, 'templates')
sys.path.insert(0, HERE)
import common

E = html.escape


def f(n, d=0):
    if n is None:
        return '—'
    return format(round(float(n), d), ',.%df' % d)


def sg(n, d=0):
    if n is None:
        return '—'
    return ('+' if n > 0 else '−' if n < 0 else '') + format(abs(float(n)), ',.%df' % d)


def pf(n, d=2):
    if n is None:
        return '—'
    return ('+' if n > 0 else '−' if n < 0 else '') + format(abs(float(n)), '.%df' % d) + '%'


def tag(text, cls):
    return '<span class="tag t-%s">%s</span>' % (cls, E(text))


# ------------------------------------------------------------------ 区块
def sec_overview(m):
    q, t = m['quote'], [x for x in m['targets'] if x['status'] == '可比']
    t0 = t[0] if t else {}
    p1y = [p for p in m['percentiles'] if p['window'] == '1y']
    p1y = p1y[0] if p1y else {}
    ms = m['spec_mismatch']
    alert = ('<div class="alert test"><b>⚠ 测试输入：</b>本报告中的供应商报价为<b>明确标注的测试数据</b>'
             '（%s），不来自真实供应商；市场价格为可追溯的公开数据，逐条附日期与来源。</div>') % E(q.get('supplier_label', ''))
    mis = ('<div class="alert mismatch"><b>⚠ 口径不匹配提示：</b>%s<br>'
           '<span class="small">规则：%s</span></div>') % (E(ms['message']), E(ms['rule']))
    a = m['primary_anchor']
    src = '<div class="srcs">主参考价来源：%s，%s，%s · <a href="%s" target="_blank" rel="noopener">原文链接</a></div>' % (
        E(a['source_name']), E(a['source_title']), E(a.get('time', '')), E(a['url']))
    return """
<section id="sec-overview" class="on">
  {alert}
  <div class="grid g4" id="kpis"></div>
  <div class="card" style="margin-top:16px">
    <h2>供应商报价 vs 市场参考区间</h2>
    <p class="hint">红旗标为供应商报价在「{lab}」口径下的市场位置；蓝色线段为同日同口径市场参考区间。</p>
    <div class="rangebar" id="rangebar"></div>
    {mis}
    {src}
  </div>
  <div class="card">
    <h2>同期行情走势（可切换口径与窗口）</h2>
    <div class="chips" id="trend-chips">
      <button class="chip on" data-k="ppi">1 年 · 生意社基准价（含税现货指数）</button>
      <button class="chip" data-k="fut1y">1 年 · EG0 期货（不含税）</button>
      <button class="chip" data-k="fut3m">3 个月 · EG0 期货</button>
      <button class="chip" data-k="fut3y">3 年 · EG0 期货</button>
    </div>
    <div id="chart-trend" class="chart"></div>
    <div class="legend"><span><span class="dot" style="background:#dc2626"></span>供应商报价水平线</span>
    <span><span class="dot" style="background:#111"></span>红点为已发生的行情事件日期</span>
    <span class="small">期货与现货口径不同（不含税 vs 含税、盘面 vs 现货），图中共存仅用于对照走势，不作价差结论。</span></div>
  </div>
  <div class="grid g2">
    <div class="card">
      <h2>近 6 个交易日华东自提价（逐日证据）</h2>
      <div id="chart-spot" class="chart sm"></div>
    </div>
    <div class="card">
      <h2>历史分位（报价在同序列中的位置）</h2>
      <div id="chart-pct" class="chart sm"></div>
      <p class="hint">分位定义：P =（小于报价的样本数 + 0.5 × 等于报价的样本数）÷ 有效样本数 × 100%。灰色为缺口。</p>
    </div>
  </div>
</section>""".format(alert=alert, mis=mis, src=src, lab=E(t0.get('target_label', '—')))


def sec_targets(m):
    rows = []
    for t in m['targets']:
        if t['status'] != '可比':
            cls = 'bad' if '缺失' in t['status'] else 'muted'
            rows.append('<tr><td><b>%s</b></td><td class="num">%s</td><td>%s</td><td colspan="4" class="small">%s</td><td>%s</td></tr>' % (
                E(t['target_label']), f(t['quote_value']), tag(t['status'], cls),
                E(t.get('reason') or t.get('quote_gap') or ''), E(t['quote_formula'])))
            continue
        anc = t['anchor']
        pos = E(t.get('position_label') or ('%.1f%%' % t['position_in_range'] if t.get('position_in_range') is not None else '—（单点口径）'))
        if t.get('outside') in ('above', 'below'):
            pos = '<span class="tag t-bad">%s</span>' % pos
        rows.append('<tr><td><b>%s</b></td><td class="num">%s</td><td class="num">%s – %s</td>'
                    '<td class="num">%s</td><td class="num" style="color:%s;font-weight:700">%s</td>'
                    '<td class="num">%s</td><td class="num">%s</td><td>%s</td></tr>' % (
                        E(t['target_label']), f(t['quote_value']), f(t['low']), f(t['high']),
                        f(t['center']), '#dc2626' if t['dev_center'] > 0 else '#0f9d76',
                        sg(t['dev_center']), pf(t['dev_center_pct']), pos, tag('可比', 'ok')))

    comp_rows = []
    for c in m['comparability']:
        lab = c['label']
        cls = {'已对齐': 'ok', '已有依据（方向）': 'ok', '待确认': 'warn', '不可比': 'bad'}.get(lab, 'muted')
        comp_rows.append('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class="wrapcell">%s</td></tr>' % (
            E(c['item']), E(c['quote']), E(c['market']), E(c['direction']),
            '可量化' if c['quantifiable'] else '不可量化', tag(lab, cls), E(c['evidence'])))

    iv = m['targets'][0].get('anchor') or {}
    caveat = iv.get('caveat')
    cav_block = ('<div class="alert gap"><b>参考区间的构造方式与局限：</b>%s</div>' % E(caveat)) if caveat else ''

    return """
<section id="sec-targets">
  <div class="card">
    <h2>1. 报价口径核验与偏离计算</h2>
    <p class="hint">四个靶心分别对应「含税/不含税 × 出厂/到厂」。只有报价与参考价<b>同靶心</b>时才计算偏离；不同靶心并列展示、不出偏离数。</p>
    <table>
      <thead><tr><th>口径（靶心）</th><th class="num">供应商报价<br>元/吨</th><th class="num">市场参考区间<br>元/吨</th>
      <th class="num">参考中枢</th><th class="num">偏离金额</th><th class="num">偏离比例</th><th class="num">区间内位置</th><th>状态</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    {cav}
    <div class="alert gap"><b>为什么「到厂」口径没有偏离数：</b>供应商未提供连云港至苏州工业园区的运价，且市场公开报价为华东库区自提（不含运至终端），
    因此「到厂」靶心记为缺口，<b>不用行业均运费顶替</b>。</div>
  </div>

  <div class="card">
    <h2>2. 口径差异分析（含量 · 等级 · 地区 · 税费 · 运输 · 数量 · 账期 · 包装 · 工艺 · 价格性质）</h2>
    <p class="hint">每项只给三种结论：<b>已对齐/有依据</b>（能落到证据）、<b>待确认</b>（方向清楚但金额未定）、<b>不可比</b>。</p>
    <table>
      <thead><tr><th>口径项</th><th>供应商报价</th><th>市场参考</th><th>方向</th><th>可量化</th><th>结论</th><th>依据</th></tr></thead>
      <tbody>{comp}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>3. 报价标准化（每一步都可复核）</h2>
    <div class="two">
      <div><div class="sec-title">原始报价</div>
        <table><tbody>
          <tr><th>供应商</th><td>{sup}</td></tr>
          <tr><th>品种 / 规格</th><td>{prod} / {spec}</td></tr>
          <tr><th>报价</th><td class="num"><b>{val}</b> 元/吨</td></tr>
          <tr><th>税费</th><td>{tax}</td></tr>
          <tr><th>交付</th><td>{dlv}</td></tr>
          <tr><th>到货地</th><td>{dst}</td></tr>
          <tr><th>数量</th><td>{qty}</td></tr>
          <tr><th>账期</th><td>{pay}</td></tr>
          <tr><th>有效期</th><td>{valid}</td></tr>
        </tbody></table>
      </div>
      <div><div class="sec-title">标准化靶心</div>
        <table><tbody>{norm}</tbody></table>
        <div class="sec-title" style="margin-top:12px">未确认项（须问供应商）</div>
        <div>{unknown}</div>
      </div>
    </div>
  </div>
</section>""".format(
        rows=''.join(rows), cav=cav_block, comp=''.join(comp_rows),
        sup=E(m['quote']['supplier_label']), prod=E(m['quote']['product_name']),
        spec=E(m['quote']['spec_text']), val=f(m['quote']['value']),
        tax=E(m['quote']['tax']['text']), dlv=E(m['quote']['delivery']['text']),
        dst=E(m['quote']['destination']), qty='%s %s' % (m['quote']['quantity']['value'], m['quote']['quantity']['unit']),
        pay=E(m['quote']['payment']['terms']), valid=E(m['quote']['validity']),
        norm=''.join('<tr><th>%s</th><td class="num">%s</td></tr><tr><th>公式</th><td class="small">%s</td></tr>' % (
            E(k['target_label']), f(k['quote_value']), E(k['quote_formula'])) for k in m['targets']),
        unknown=''.join('<span class="tag t-warn" style="margin:2px 4px 2px 0">%s</span>' % E(u) for u in m['quote'].get('unknowns', [])))


def sec_history(m):
    rows = []
    for p in m['percentiles']:
        nm = p.get('series_name') or '—'
        if p.get('ok'):
            pc = p.get('quote_pctile')
            cls = 'bad' if pc >= 80 else ('warn' if pc >= 50 else 'ok')
            rows.append('<tr><td><b>%s</b></td><td>%s</td><td class="num">%s</td><td>%s<br><span class="small">%s</span></td>'
                        '<td class="num">%s – %s</td><td class="num">%s</td><td class="num"><b>%s</b></td><td>%s</td></tr>' % (
                            {'3m': '3 个月', '1y': '1 年', '1y_fut': '1 年（期货）', '3y': '3 年（期货）'}.get(p['window'], p['window']),
                            E(nm), f(p['n']), E(p['start']), E(p['end']), f(p['low']), f(p['high']), f(p['median']),
                            ('%.1f%%' % pc), tag('已计算', cls)))
        else:
            rows.append('<tr><td><b>%s</b></td><td>%s</td><td class="num">%s</td><td colspan="4" class="small">%s</td>'
                        '<td>%s</td></tr>' % (
                            {'3m': '3 个月', '1y': '1 年', '1y_fut': '1 年（期货）', '3y': '3 年（期货）'}.get(p['window'], p['window']),
                            E(nm), f(p.get('n')), E(p.get('gap') or ''), tag('缺口', 'muted')))

    bars = []
    for p in m['percentiles']:
        if p.get('quote_pctile') is None:
            continue
        pc = p['quote_pctile']
        bars.append('<div style="margin:10px 0"><div class="small">%s · %s（n=%s，%s ~ %s）</div>'
                    '<div class="pctbar"><div class="fill" style="width:%.1f%%"></div><div class="qq">报价位于 %.1f%% 分位</div></div></div>' % (
                        E({'3m': '3 个月', '1y': '1 年', '1y_fut': '1 年（期货）', '3y': '3 年（期货）'}[p['window']]),
                        E(p.get('series_name') or ''), f(p['n']), E(p['start']), E(p['end']), pc, pc))

    anc = []
    for a in m['annual_anchors']:
        cmp_ = a.get('quote_vs') or []
        cells = ' · '.join('%s %s（%s）' % (E(x['label']), f(x['value']), pf(x['diff_pct'])) for x in cmp_)
        anc.append('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td class="wrapcell">%s</td><td style="max-width:300px" class="small">%s</td></tr>' % (
            a['year'], E(a['period']), E(a['nature']), tag({'high': '较可靠', 'medium': '参考', 'low': '低置信'}.get(a.get('confidence'), '参考'),
                                                          {'high': 'ok', 'medium': 'warn', 'low': 'muted'}.get(a.get('confidence'), 'muted')),
            cells, E(a.get('source', ''))))

    # 给图表用的年度锚点整形：区间/均值/首末价
    anchor_chart = []
    for a in m['annual_anchors']:
        if a.get('value_low') is not None and a.get('value_high') is not None:
            lo, hi, kind = a['value_low'], a['value_high'], 'range'
        elif a.get('value_avg') is not None:
            lo = hi = a['value_avg']
            kind = 'avg'
        else:
            lo, hi, kind = a.get('value_start'), a.get('value_end'), 'point'
        anchor_chart.append({'year': a['year'], 'low': lo, 'high': hi, 'kind': kind, 'nature': a.get('nature')})

    return """
<section id="sec-history">
  <div class="card">
    <h2>1. 历史分位表（只基于有效序列，不用最高最低价推断）</h2>
    <p class="hint">报价与序列必须同口径比较：与期货序列比较时，报价先折算为<b>不含税</b>；与含税指数比较时用<b>含税</b>报价。</p>
    <table>
      <colgroup><col style="width:110px"><col style="width:170px"><col style="width:74px"><col><col style="width:150px"><col style="width:90px"><col style="width:96px"><col style="width:88px"></colgroup>
      <thead><tr><th>历史窗口</th><th>序列</th><th class="num">样本数</th><th>起止日期</th><th class="num">区间</th><th class="num">中位数</th><th class="num">报价分位</th><th>状态</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <div class="grid g2">
    <div class="card">
      <h2>2. 报价所处的历史位置</h2>
      {bars}
      <p class="hint" style="margin-top:10px">说明：1 年分位基于生意社基准价（含税、全国综合口径）；期货分位口径为不含税盘面价，两者不可混用。</p>
    </div>
    <div class="card">
      <h2>3. 年度锚点对照（锚点≠序列，不出分位）</h2>
      <div id="chart-anchors" class="chart sm"></div>
      <table><colgroup><col style="width:58px"><col><col style="width:92px"><col><col style="width:190px"></colgroup>
      <thead><tr><th>年份</th><th>区间口径</th><th>数据性质</th><th>报价相对锚点</th><th>来源</th></tr></thead>
      <tbody>{anc}</tbody></table>
    </div>
  </div>
</section>""".format(rows=''.join(rows), bars=''.join(bars), anc=''.join(anc))


def sec_events(m):
    items = []
    for i, e in enumerate(m.get('events') or []):
        items.append('<div class="tl-item" id="ev%d" onclick="this.classList.toggle(\'hot\')">'
                     '<div class="d">%s · <span class="tag t-muted">%s</span></div>'
                     '<div class="t">%s</div><div class="f">%s</div><div class="pe">价格表现：%s</div>'
                     '<div class="srcs">来源：%s</div></div>' % (
                         i, E(e['d']), E(e.get('phase', '')), E(e['title']), E(e['fact']), E(e.get('price_effect', '')), E(e.get('source', ''))))
    # 异常价格阶段（由序列计算，非人工标注）
    phases = []
    hist = m.get('history') or {}
    fp = hist.get('fut_1y') or []
    if fp:
        import statistics
        v = [x['v'] for x in fp]
        med = statistics.median(v)
        top = max(fp, key=lambda x: x['v'])
        low = min(fp, key=lambda x: x['v'])
        phases.append('<tr><td>近 1 年最高</td><td>%s</td><td class="num">%s</td><td class="num">%s</td><td>%s</td></tr>' % (
            E(top['d']), f(top['v']), pf((top['v'] - med) / med * 100), E(m['quote']['region_supplier'])))
        phases.append('<tr><td>近 1 年最低</td><td>%s</td><td class="num">%s</td><td class="num">%s</td><td>—</td></tr>' % (
            E(low['d']), f(low['v']), pf((low['v'] - med) / med * 100)))
        # 单日涨跌超过 3% 的交易日
        big = []
        for j in range(1, len(fp)):
            p = (fp[j]['v'] - fp[j - 1]['v']) / fp[j - 1]['v'] * 100
            if abs(p) >= 3:
                big.append((fp[j]['d'], fp[j]['v'], p))
        for d, v, p in big[-8:]:
            phases.append('<tr><td>单日波动 ≥3%%</td><td>%s</td><td class="num">%s</td><td class="num">%s</td><td>EG0 连续合约</td></tr>' % (E(d), f(v), pf(p)))
    return """
<section id="sec-events">
  <div class="card">
    <h2>1. 近期已经发生的行情变化（只列事实，不含方向判断）</h2>
    <p class="hint">点击任一事件可在走势图上定位其所在价格阶段。事件来自公开报道，逐条注明发布方与日期。</p>
    <div class="timeline">{items}</div>
  </div>
  <div class="card">
    <h2>2. 由序列自动识别的异常价格阶段</h2>
    <p class="hint">下表按「近 1 年 EG0 期货收盘序列」计算，偏离比以近 1 年中位数 %s 元/吨为基准，非人工指定。</p>
    <table><thead><tr><th>阶段/类型</th><th>日期</th><th class="num">价格（元/吨）</th><th class="num">相对中位偏离</th><th>口径</th></tr></thead>
    <tbody>{phases}</tbody></table>
  </div>
</section>""".format(items=''.join(items), phases=''.join(phases),
                     )
    # 中位数文本在上方 format 中已固定，另行补入


def sec_evidence(m):
    srcs = []
    for a in m['anchors']:
        srcs.append('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td class="num">%s</td><td>%s</td><td>%s</td>'
                    '<td class="wrapcell"><a href="%s" target="_blank" rel="noopener">%s</a><div class="small">%s</div></td></tr>' % (
                        E(a['id']), E(a['date']), E(a['source_name']), E(a['spec']), f(a['value']),
                        '含税' if a['tax_included'] else '不含税', E(a['delivery']), E(a['url']),
                        E(a['source_title']), E(a.get('note', ''))))
    ent = ''.join('<tr><td>%s</td><td>%s</td><td class="num">%s</td><td>%s</td><td class="small">%s</td></tr>' % (
        E(x['party']), E(x['month']), f(x.get('list_price') or x.get('settlement')),
        E(x.get('note', '')), E(x.get('source', ''))) for x in m.get('enterprise_prices', []))
    gaps = ''.join('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        E(g['id']), E(g['item']), E(g['impact']), E(g['tried']), E(g['why']), E(g['next'])) for g in m.get('gaps', []))
    ex = m.get('evidence_summary') or {}
    expl = ''.join('<tr><td>%s</td><td class="num">%s</td><td>%s</td><td class="small">%s</td></tr>' % (
        E(x['difference']), E(x['amount']), E(x['direction']), E(x['basis'])) for x in ex.get('explainable', []))
    pend = ''.join('<li>%s</li>' % E(x) for x in ex.get('pending', []))
    return """
<section id="sec-evidence">
  <div class="card">
    <h2>1. 市场价格来源（每条六项口径齐全）</h2>
    <table><thead><tr><th>ID</th><th>日期</th><th>发布方</th><th>规格</th><th class="num">价格</th><th>税费</th><th>交付</th><th>原文</th></tr></thead>
    <tbody>{srcs}</tbody></table>
    <h3>企业挂牌价 / 结算价（企业定价，非市场均价，仅作对照）</h3>
    <table><thead><tr><th>企业</th><th>月份</th><th class="num">价格</th><th>说明</th><th>来源</th></tr></thead><tbody>{ent}</tbody></table>
  </div>
  <div class="grid g2">
    <div class="card">
      <h2>2. 可以用证据解释的差异</h2>
      <table><thead><tr><th>差异来源</th><th class="num">金额</th><th>方向</th><th>依据</th></tr></thead><tbody>{expl}</tbody></table>
      <h3>3. 尚待确认的差异（须问供应商）</h3>
      <ul>{pend}</ul>
    </div>
    <div class="card">
      <h2>4. 数据缺口（缺口本身就是结论）</h2>
      <table><thead><tr><th>#</th><th>缺什么</th><th>影响</th><th>已尝试</th><th>为什么缺</th><th>补数路径</th></tr></thead><tbody>{gaps}</tbody></table>
    </div>
  </div>
</section>""".format(srcs=''.join(srcs), ent=ent, expl=expl, pend=pend, gaps=gaps)


def sec_method(m):
    n = m['quote_norm']
    meta = m['quote_meta']
    vat = meta['vat']
    qv = m['quote']['value']
    exw_exc = n['excluded|ex_works']['value']
    t0 = [x for x in m['targets'] if x['status'] == '可比']
    t0 = t0[0] if t0 else {}
    dev_f = '偏离金额 = 报价 − 参考中枢 = %s − %s = %s 元/吨' % (f(t0.get('quote')), f(t0.get('center')), sg(t0.get('dev_center')))
    dev_p = '偏离比例 = 偏离金额 ÷ 参考中枢 = %s ÷ %s = %s' % (sg(t0.get('dev_center')), f(t0.get('center')), pf(t0.get('dev_center_pct')))
    pos_f = ('区间内位置 = (报价 − 区间下沿) ÷ (区间上沿 − 区间下沿) = (%s − %s) ÷ (%s − %s) = %s%s' % (
        f(t0.get('quote')), f(t0.get('low')), f(t0.get('high')), f(t0.get('low')),
        ('%.1f%%' % t0['position_raw']) if t0.get('position_raw') is not None else '—',
        '；报价已超出区间，故展示时记为「%s」而不按百分位外推' % t0.get('position_label') if t0.get('outside') in ('above', 'below') else ''))
    rows = ''.join('<tr><td>%s</td><td class="num">%s</td><td>%s</td></tr>' % (
        E(k['target_label']), f(k['quote_value']), E(k['quote_formula'])) for k in m['targets'])
    pct_def = 'P = ( #{v < X} + 0.5 × #{v = X} ) ÷ N × 100%'
    return """
<section id="sec-method">
  <div class="card">
    <h2>1. 报价标准化公式</h2>
    <table><thead><tr><th>靶心</th><th class="num">结果 元/吨</th><th>公式</th></tr></thead><tbody>{rows}</tbody></table>
    <pre>增值税率 VAT = {vatp}
含税 → 不含税： 不含税 = 含税 ÷ (1 + VAT)  = {qv} ÷ {vatf} = {exc}
不含税 → 含税： 含税 = 不含税 × (1 + VAT)
到厂 = 出厂 + 运费；运费未取得 → 到厂靶心 = 缺口（不用行业均运费顶替）
账期折算： 现款价 = 报价 × (1 − 年化资金成本 × 账期天数 ÷ 365)
           {credit}</pre>
  </div>
  <div class="card">
    <h2>2. 偏离公式</h2>
    <pre>{d1}
{d2}
{d3}
偏离比例带符号：正数=报价高于参考，负数=报价低于参考。</pre>
  </div>
  <div class="card">
    <h2>3. 历史分位公式</h2>
    <pre>{pctdef}

有效样本要求：
 · 3 个月窗口 ≥ 8 个交易日点，否则只给区间不给分位
 · 1 年 / 3 年窗口 ≥ 60 个点，并要求同一口径、同一频率
 · 禁止用最高价/最低价推断分位；禁止插值；禁止跨口径拼接
窗口区间（同序列）：
 low  = min(样本)；high = max(样本)；中位数 = median(样本)</pre>
  </div>
  <div class="card">
    <h2>4. 期货与现货的换算边界</h2>
    <pre>现货含税价 ÷ (1 + VAT) 才可与不含税期货同屏比较；
报价在不含税口径下的分位，只说明「在不含税价格序列中的位置」，
不等于「现货溢价/贴水」。期货不含交割成本与基差，不得用期货 − 现货作为价差结论。</pre>
  </div>
</section>""".format(rows=rows, vatp='%.0f%%' % (vat * 100), qv=f(qv), vatf='%.2f' % (1 + vat), exc=f(exw_exc),
                     credit=E(meta.get('credit_formula', '—')), d1=E(dev_f), d2=E(dev_p), d3=E(pos_f), pctdef=E(pct_def))


def build(model_path, out_path):
    m = common.load_json(model_path)
    echarts = open(os.path.join(SKILL, 'templates', 'echarts.min.js'), encoding='utf-8').read()
    app = open(os.path.join(SKILL, 'templates', 'app.js'), encoding='utf-8').read()
    tpl = open(os.path.join(SKILL, 'templates', 'report.html.tpl'), encoding='utf-8').read()
    sections = (sec_overview(m) + sec_targets(m) + sec_history(m) + sec_events(m)
                + sec_evidence(m) + sec_method(m))
    # 图表数据（与表格同源）
    anchor_chart = []
    for a in m.get('annual_anchors') or []:
        if a.get('value_low') is not None and a.get('value_high') is not None:
            lo, hi, kind = a['value_low'], a['value_high'], 'range'
        elif a.get('value_avg') is not None:
            lo = hi = a['value_avg']
            kind = 'avg'
        else:
            lo, hi, kind = a.get('value_start'), a.get('value_end'), 'point'
        anchor_chart.append({'year': a['year'], 'low': lo, 'high': hi, 'kind': kind,
                             'nature': a.get('nature')})
    chart_data = {'anchor': anchor_chart}
    # 修正异常阶段说明里的中位数
    import statistics
    fp = ((m.get('history') or {}).get('fut_1y') or [])
    if fp:
        med = statistics.median([x['v'] for x in fp])
        sections = sections.replace('为基准，非人工指定。', '为基准（%s 元/吨），非人工指定。' % f(med))
    badges = ['数据基准日 %s' % m['meta']['asof'], '报告编号 %s' % m['meta']['report_id'],
              '现货主锚：%s' % m['primary_anchor']['source_name'],
              '期货：DCE EG0（仅作走势参照）']
    if m['quote'].get('is_test_input'):
        badges.insert(0, '测试输入')
    html_out = tpl
    repl = {
        '__TITLE__': E(m['meta']['title']),
        '__H1__': E(m['meta']['title']),
        '__SUBTITLE__': E('采购报价核验底稿 · %s · 品种族：%s' % (m['meta']['asof'], m['meta'].get('product_family', ''))),
        '__BADGES__': ''.join('<span class="badge%s">%s</span>' % (' test' if b == '测试输入' else '', E(b)) for b in badges),
        '__SECTIONS__': sections,
        '__FOOTER__': E(m['meta'].get('disclaimer', '') + ' · 本报告不构成价格预测或议价建议。'),
        '__ECHARTS__': echarts,
        '__DATA__': 'window.SQV=' + json.dumps(m, ensure_ascii=False) + ';window.SQVCHART=' + json.dumps(chart_data, ensure_ascii=False) + ';',
        '__APP__': app,
    }
    for k, v in repl.items():
        html_out = html_out.replace(k, v)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(html_out)
    return out_path


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    p = build(a.model, a.out)
    print('OK -> %s (%.1f KB)' % (p, os.path.getsize(p) / 1024))
