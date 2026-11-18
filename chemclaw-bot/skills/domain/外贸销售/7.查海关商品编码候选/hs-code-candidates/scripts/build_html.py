# -*- coding: utf-8 -*-
"""Build the interactive HTML report for the SBS HS-classification case."""
import sys, os, json, html, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def arg(flag, default=None):
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default

CASE_PATH = arg('--case') or arg('--in') or (sys.argv[1] if len(sys.argv) > 1 else None)
if not CASE_PATH:
    sys.exit('usage: python build_html.py --case <case.json> --out <page.html>')
case = json.load(open(CASE_PATH, encoding='utf-8'))
E = html.escape

def lv_class(level):
    l = str(level)
    if l.startswith('A'):
        return 'lv-a'
    if l.startswith('B'):
        return 'lv-b'
    if l.startswith('C'):
        return 'lv-c'
    return 'lv-d'

def pill(text, cls):
    return f'<span class="pill {cls}">{E(str(text))}</span>'

C = case['candidates']
byrank = sorted(C, key=lambda x: x['rank'])
C1 = [c for c in C if c['id'] == 'C1']
C1 = C1[0] if C1 else sorted(C, key=lambda x: x['rank'])[0]

# ---------------- header ----------------
M = case['meta']
P = case['product']

header = f'''
<header class="hero">
  <div class="hero-top">
    <div class="brand">ChemClaw · 外贸销售 · 查海关商品编码候选</div>
    <div class="meta">
      <span>查询日期 <b>{E(M['query_date'])}</b></span>
      <span>HS 版本 <b>HS 2022 / 中国 2026 税则</b></span>
      <span>案例号 <b>{E(M['case_id'])}</b></span>
    </div>
  </div>
  <h1>{E(P['name_cn'])} HS 编码候选研究</h1>
  <p class="sub">{E(P['name_en'])}｜CAS {E(P.get('cas') or '—')}｜形态：{E(P.get('form') or '—')}</p>
  <p class="sub">同一个产品名，在中国税则里可能落进不止一个编码。本页给的是<b>候选 + 每个候选的成立条件 + 法条依据 + 还缺什么</b>，
  不是一个强行得出的唯一编码。</p>
  <div class="kpis">
    <div class="kpi"><div class="k">候选编码</div><div class="v">{len(C)}</div><div class="n">首选 C1 / 并列 C2</div></div>
    <div class="kpi"><div class="k">首选编码</div><div class="v mono">{E(C1['code10'])}</div><div class="n">热塑丁苯橡胶（非充油）</div></div>
    <div class="kpi"><div class="k">进口最惠国税率</div><div class="v">{E(C1['mfn'])}</div><div class="n">普通税率 {E(C1['gen'])}</div></div>
    <div class="kpi warn"><div class="k">出口退税率（数据源）</div><div class="v">{E(C1['rebate'])}</div><div class="n">须按 2026C 版文库核验</div></div>
    <div class="kpi"><div class="k">关键缺失项</div><div class="v">{len(case['missing'])}</div><div class="n">其中高优先级 {sum(1 for m in case['missing'] if m[3]=='高')}</div></div>
  </div>
</header>
'''

# ---------------- nav ----------------
tabs = [
    ('flow', '① 归类路径'),
    ('cands', '② 候选编码'),
    ('basis', '③ 法律依据'),
    ('amb', '④ 歧义与误配'),
    ('layer', '⑤ 编码层级'),
    ('reg', '⑥ 监管条件'),
    ('miss', '⑦ 缺失信息'),
    ('conf', '⑧ 待确认'),
    ('src', '⑨ 来源'),
]
nav = '<nav class="tabs" id="tabs">' + ''.join(
    f'<button class="tab{" active" if i==0 else ""}" data-tab="{k}">{E(t)}</button>'
    for i, (k, t) in enumerate(tabs)) + '</nav>'

# ---------------- ① flow ----------------
def step(no, title, body, tone=''):
    return f'''<div class="step {tone}"><div class="no">{no}</div><div class="sc"><h4>{title}</h4><div>{body}</div></div></div>'''

flow = f'''
<section class="panel active" id="p-flow">
  <h2>归类是怎么一步步收敛的</h2>
  <p class="lead">归类的顺序不能省：章 → 税目 → 子目 → 本国细分。跳过中间任何一步直接给 10 位码，都是“凑编码”。</p>
  <div class="flow">
    {step('1', '章：第39章还是第40章？',
      '<p>SBS 是嵌段共聚物，可反复热塑加工，容易被当成“塑料”。但第39章注释二（十一）把<b>“第四十章规定的合成橡胶及其制品”</b>排除出第39章，第40章注释一又把合成橡胶定义为“橡胶”。</p>'
      '<p>结论方向：只要满足第40章注释四的合成橡胶要件，就走第40章；不满足时才回头看第39章（候选 C5）。</p>',
      'ok')}
    {step('2', '税目：40.02 还是 40.05？',
      '<p>第40章注释五（一）规定：与硫化剂、促进剂、颜料（仅识别用除外）、增塑剂或增量剂（<b>充油橡胶所加矿物油除外</b>）、填料、增强剂等混合的橡胶，<b>不归入 40.01/40.02</b>，落到 40.05 复合橡胶。</p>'
      '<p>所以：“SBS 里有没有炭黑/白炭黑/填料/助剂”这一问，直接决定退税是 13% 还是 0%。</p>',
      'warn')}
    {step('3', '子目：4002.19 的哪一档？',
      '<p>4002.1 是 SBR/XSBR；胶乳走 4002.11，固体走 4002.19。中国在 4002.19 项下进一步细分：</p>'
      '<p class="mono small">4002.1911 未经任何加工（溶聚除外）｜4002.1912 充油（溶聚除外）｜<b>4002.1913 热塑丁苯橡胶</b>｜<b>4002.1914 充油热塑丁苯橡胶</b>｜4002.1915 未经任何加工的溶聚｜4002.1916 充油溶聚｜4002.1919 其他｜4002.1990 其他（非初级形状）</p>'
      '<p>SBS 的化学身份（丁苯）+ 热塑特征 → 命中 4002.1913；若充油 → 4002.1914。</p>',
      'ok')}
    {step('4', '形态：初级形状还是板片带？',
      '<p>第40章注释三把“初级形状”限定为液体/糊状（含胶乳）以及不规则块、团、包、粉、粒、碎屑等散装形状；注释九限定“板、片、带”。</p>'
      '<p>粒料出口 → 4002.1913/14；压片、压块、成卷 → 4002.1990，<b>退税率掉到 0%</b>。</p>',
      'warn')}
    {step('5', '申报要素与单证要能自证',
      '<p>4002.1913/14 的申报要素里有一条专门写死的：<b>“丁苯橡胶请注明是否充油、热塑”</b>；此外还要填外观（板、片、带等）、成分含量、用途。</p>'
      '<p>这意味着“是否充油、是否热塑、什么形态”必须是可举证的（TDS / 检验报告 / 实物照片），否则申报要素本身就不成立。</p>',
      '')}
    {step('6', '对外表述：给客户的是目的国编码',
      '<p>客户清关用的是他们国家的编码：美国已单列 <b>4002.19.00.14（SBS 溶液聚合热塑弹性体）</b>；欧盟走 CN 4002.19.20；日本/韩国只到 4002.19 再加本国细分。</p>'
      '<p>所以对外报价表里写“中国出口 HS：4002191300；贵国对应编码请按 4002.19 项下核实”，不要直接把中国 10 位码当客户编码。</p>',
      'ok')}
  </div>
  <div class="callout danger">
    <b>一句话结论（对客户可以说的话）：</b>
    “我们的 SBS 是苯乙烯-丁二烯-苯乙烯嵌段共聚物，未充油、未硫化、未添加填料，以颗粒状出口，按中国税则归入 4002.1913（热塑丁苯橡胶）；
    若为充油牌号则为 4002.1914。最终以中国海关认定为准，贵国进口编码在 4002.19 项下另行确认。”
  </div>
</section>
'''

# ---------------- ② candidates ----------------
def cand_card(c):
    tone = 'rank-1' if c['rank'] == 1 else ('rank-2' if c['rank'] == 2 else ('rank-3' if c['rank'] <= 4 else 'rank-4'))
    conds = ''.join(f'<li>{E(x)}</li>' for x in c['conditions'])
    basis = ''.join(f'<li>{E(x)}</li>' for x in c['basis'])
    return f'''
    <article class="card {tone}" data-code="{E(c['code10'])}" data-rank="{c['rank']}">
      <div class="card-h">
        <div class="rank">#{c['rank']}</div>
        <div class="ch-main">
          <div class="code mono">{E(c['code10'])}<span class="hs6">HS6 {E(c['hs6'])}</span></div>
          <h3>{E(c['title'])}</h3>
          <div class="chips">
            {pill(c['verdict'], 'p-verdict')}
            {pill('置信度：' + c['confidence'], 'p-conf')}
            {pill('监管条件 ' + (c['reg'] or '无'), 'p-reg')}
            {pill('检验检疫 ' + (c['ciq'] or '无'), 'p-reg')}
          </div>
        </div>
        <div class="rates">
          <div><span>最惠国</span><b>{E(c['mfn'])}</b></div>
          <div><span>普通</span><b>{E(c['gen'])}</b></div>
          <div class="hot"><span>出口退税</span><b>{E(c['rebate'])}</b></div>
        </div>
      </div>
      <div class="card-b">
        <div class="col">
          <h5>成立条件（缺一不可）</h5><ul>{conds}</ul>
        </div>
        <div class="col">
          <h5>为什么是这个码</h5><p>{E(c['why'])}</p>
          <h5>法律依据</h5><ul>{basis}</ul>
        </div>
        <div class="col">
          <h5>风险点</h5><p class="risk">{E(c['vuln'])}</p>
          <h5>退税状态</h5><p class="small">{E(c['rebate_status'])}</p>
          <h5>互惠税率（进口方向参考）</h5>
          <p class="small">RCEP 日本 {E(c['rcep'].get('日本','—'))}｜东盟 {E(c['rcep'].get('泰国','—'))}｜韩国 {E(c['rcep'].get('韩国','—'))}｜新西兰 {E(c['rcep'].get('新西兰','—'))}</p>
        </div>
      </div>
      <div class="card-f"><a href="{E(c['url'])}" target="_blank" rel="noopener">编码详情页 ↗</a><a href="{E(c['tariff_source']['url'])}" target="_blank" rel="noopener">税则原文（官方 PDF）↗</a></div>
    </article>'''

cands = f'''
<section class="panel" id="p-cands">
  <h2>候选编码总表</h2>
  <p class="lead">共 {len(C)} 个候选。C1/C2 是主流落点，C3/C6 是兜底，C4/C5 是“条件一变就接管”的路径，C7/C8 是形态/胶乳分岔。点击卡片展开细节，或用筛选快速定位。</p>
  <div class="toolbar">
    <input id="q" type="search" placeholder="搜索编码 / 关键词，如 4002、充油、复合橡胶">
    <div class="filters">
      <button class="fbtn active" data-f="all">全部</button>
      <button class="fbtn" data-f="main">主路径（C1–C3）</button>
      <button class="fbtn" data-f="cond">条件性（C4/C5）</button>
      <button class="fbtn" data-f="form">形态分岔（C6–C8）</button>
    </div>
  </div>
  <div class="tablewrap">
  <table class="tbl" id="ctab">
    <thead><tr><th>#</th><th>编码</th><th>HS6</th><th>品名</th><th>定位</th><th>最惠国</th><th>普通</th><th>出口退税</th><th>监管</th><th>检疫</th><th>置信度</th></tr></thead>
    <tbody>
    {''.join(f'<tr data-f="{"main" if c["rank"]<=3 else ("cond" if c["rank"]<=5 else "form")}"><td>{c["rank"]}</td><td class="mono">{E(c["code10"])}</td><td class="mono">{E(c["hs6"])}</td><td>{E(c["title"])}</td><td>{E(c["verdict"])}</td><td>{E(c["mfn"])}</td><td>{E(c["gen"])}</td><td class="{"bad" if c["rebate"].startswith("0") else "good"}">{E(c["rebate"])}</td><td>{E(c["reg"] or "无")}</td><td>{E(c["ciq"] or "无")}</td><td class="small">{E(c["confidence"])}</td></tr>' for c in byrank)}
    </tbody>
  </table>
  </div>
  <div class="cards" id="cards">
    {''.join(cand_card(c) for c in byrank)}
  </div>
</section>
'''

# ---------------- ③ basis ----------------
LAW = [
    ('归类总规则一', '具有法律效力的归类，应按税目条文和有关类注或章注确定', '先定章、再定税目；不按商品俗称或 CAS 直接给码'),
    ('第39章注释二（十一）', '本章不包括：第四十章规定的合成橡胶及其制品', '排除“SBS 是塑料所以归 39 章”的错误路径'),
    ('第39章注释四', '共聚物（含嵌段共聚物）按聚合物中重量最大的共聚单体单元分类；无最大者按号列顺序归最末', '若按 39 章口径，苯乙烯与丁二烯比例决定 3903 还是 3902'),
    ('第40章注释一', '本目录所称“橡胶”，是指……合成橡胶、从油类提取的油膏以及上述物品的再生品', 'SBS 进入第40章考察的入口'),
    ('第40章注释三', '“初级形状”只限于：液状及糊状（含胶乳）；不规则形状的块、团、包、粉、粒、碎屑及类似散装形状', '粒料=初级形状；压片/成卷≠初级形状'),
    ('第40章注释四（一）', '不饱和合成物质，用硫磺硫化能使其不可逆地变为非热塑物质，且 18–29℃ 下拉伸至 3 倍不断裂、拉伸至 2 倍后 5 分钟内回复至不超过 1.5 倍', 'SBS 含丁二烯不饱和双键；需以技术数据举证'),
    ('第40章注释五（一）', '与硫化剂、促进剂、颜料（识别用除外）、增塑剂或增量剂（充油橡胶所加矿物油除外）、填料、增强剂等混合的橡胶，不归入 40.01/40.02', '含填料/助剂的复配料 → 4005'),
    ('第40章注释五（二）', '含乳化剂、少量乳化剂分解产品、微量抗氧剂/稳定剂/粘度控制剂等特殊用途添加剂的橡胶，仍具原料基本特性时留在 40.01/40.02', '微量抗氧剂不改变 40.02 归类'),
    ('第40章注释九', '“板”“片”“带”仅指未切割或仅切割成矩形的板片带及正几何形块', '与注释三配合判定形态'),
    ('税目 40.02', '合成橡胶及从油类提取的油膏，初级形状或板、片、带；税目40.01所列产品与本税目所列产品的混合物', 'SBS 的税目层级'),
    ('子目 4002.19', '--其他（丁苯橡胶 SBR；羧基丁苯橡胶 XSBR 项下，非胶乳）', '固体 SBS 粒料的第一层落点'),
    ('本国子目 4002.1913', '----热塑丁苯橡胶', '与 SBS 化学身份 + 热塑特征直接对应'),
    ('本国子目 4002.1914', '----充油热塑丁苯橡胶', '充油牌号的对应子目'),
    ('本国子目 4002.1919', '----其他', '4002.19 项下兜底'),
    ('本国子目 4002.1990', '---其他（非初级形状）', '板、片、带等形态'),
    ('本国子目 4005.9900', '--其他（未硫化的复合橡胶，初级形状）', '复配料路径'),
    ('本国子目 4002.9911', '---其他初级形状的合成橡胶', '非 SBR 列名胶种的兜底（如 SEBS 口径）'),
    ('本级子目 3903.9000', '初级形状的其他苯乙烯聚合物', '仅当第40章路径被否定时'),
    ('归类总规则六', '子目归类按子目条文及子目注释确定，子目比较只能在同一数级上进行', '10 位细分只能在 4002.19 同级比较'),
    ('《海关预裁定管理暂行办法》第十三条', '预裁定决定有效期为3年；所依据法律法规变化影响其效力的，自动失效', '锁定编码稳定性的正式路径'),
]
basis = f'''
<section class="panel" id="p-basis">
  <h2>法律依据对照表</h2>
  <p class="lead">每条依据都定位到具体注释/子目条文（原文可在中国 2026 年进出口税则 PDF 的第三十九章 497 页起、第四十章 529 页起核对）。看归类不要去翻品名索引，先看注释。</p>
  <div class="tablewrap">
  <table class="tbl">
    <thead><tr><th style="width:18%">条文/规则</th><th style="width:46%">原文摘录</th><th>在本例中的作用</th></tr></thead>
    <tbody>{''.join(f'<tr><td><b>{E(a)}</b></td><td class="quote">{E(b)}</td><td>{E(c)}</td></tr>' for a,b,c in LAW)}</tbody>
  </table>
  </div>
  <div class="callout">
    <b>为什么不能只用 CAS 号查编码：</b>CAS 9003-55-8 是族类登记号，同一个号覆盖 SBS 与 SBR 的众多牌号，
    充油、充不充、加不加填料、什么形态，全都不在 CAS 里。编码是“货品”的属性，不是“化学物质”的属性。
  </div>
</section>
'''

# ---------------- ④ ambiguity ----------------
amb_rows = ''.join(
    f'<tr><td class="mono">{E(a[0])}</td><td><b>{E(a[1])}</b></td><td>{E(a[2])}</td></tr>' for a in case['ambiguity'])
ac_rows = ''.join(
    f'<tr class="{"row-bad" if ("过期" in a[2] or "不适用" in a[2]) else "row-mid"}"><td class="mono">{E(a[0])}</td><td>{E(a[1])}</td><td><b>{E(a[2])}</b></td><td>{E(a[3])}</td><td class="small">{E(a[4])}</td></tr>'
    for a in case['ac'])
amb = f'''
<section class="panel" id="p-amb">
  <h2>歧义对照与常见误配</h2>
  <p class="lead">上半部分是“同一产品可能落入的相邻编码”（这是正常的归类歧义）；下半部分是“检索时容易被误命中、但不该用的编码”（这是错误）。两者要分开看。</p>
  <h3>一、同一产品的相邻编码（真正的歧义）</h3>
  <div class="tablewrap">
  <table class="tbl">
    <thead><tr><th style="width:24%">编码对 / 概念对</th><th style="width:20%">判断要点</th><th>为什么必须分清</th></tr></thead>
    <tbody>{amb_rows}</tbody>
  </table>
  </div>
  <h3>二、常见误配与已过期编码（不该用）</h3>
  <div class="tablewrap">
  <table class="tbl">
    <thead><tr><th style="width:16%">编码</th><th style="width:24%">名称</th><th style="width:14%">判断</th><th>判断理由</th><th style="width:14%">证据等级</th></tr></thead>
    <tbody>{ac_rows}</tbody>
  </table>
  </div>
  <div class="callout danger">
    <b>最容易踩的两个坑：</b>① 把“热塑性弹性体”当成一个品名去搜，会同时命中 3902.30（丙烯共聚物）、3903.90（其他苯乙烯聚合物）、3907.99（聚酯类）、3909.50（聚氨酯）、4002.99（其他合成橡胶）——这些是不同化学结构的热塑性弹性体，不能互换。
    ② 沿用 4002199001 / 4002199090：这两个 10 位码在数据源中状态为“过期”，2026 年税则 4002.1990 项下未见对应细分，沿用会被退单或申报不实。
  </div>
</section>
'''

# ---------------- ⑤ layer ----------------
six = ''.join(f'<tr><td class="mono">{E(k)}</td><td>{E(v)}</td></tr>' for k, v in case['six_tree'])
foreign_cards = ''.join(f'''
  <div class="fcard {lv_class(f['level'])}">
    <div class="fh"><b>{E(f['country'])}</b><span class="pill {lv_class(f['level'])}">{E(f['level'])}</span></div>
    <div class="row"><span>该国 HS6</span><b class="mono">{E(f['hs6'])}</b></div>
    <div class="row"><span>细分编码</span><div>{E(f['sub'])}</div></div>
    <div class="row"><span>税率</span><div>{E(f['rate'])}</div></div>
    <div class="note">{E(f['note'])}</div>
    <a href="{E(f['url'])}" target="_blank" rel="noopener">{E(f['src'])} ↗</a>
  </div>''' for f in case['foreign'])
layer = f'''
<section class="panel" id="p-layer">
  <h2>国际 6 位 → 中国 8/10 位 → 目的国编码</h2>
  <p class="lead">HS 前 6 位全球一致，第 7 位以后各国自定。给客户报价时写“中国出口编码”，同时提醒客户按其本国编码清关，这两件事不能混。</p>
  <h3>一、国际 HS 与中国税则的层级</h3>
  <div class="tablewrap">
  <table class="tbl"><thead><tr><th style="width:16%">层级</th><th>内容</th></tr></thead><tbody>{six}</tbody></table>
  </div>
  <h3>二、目的国编码层级（本次检索所得）</h3>
  <div class="fgrid">{foreign_cards}</div>
  <div class="callout warn">
    本轮只有美国（A 级，官方 API）、中国（A 级，税则 PDF）拿到了原文；<b>欧盟、日本、韩国、东盟的细分与税率为 D 级待核验</b>，
    报价或向客户承诺税率前，必须让客户或目的国报关行按其海关数据库确认。
  </div>
</section>
'''

# ---------------- ⑥ reg ----------------
reg_rows = ''.join(f'''
  <tr class="{lv_class(g['level'])}">
    <td class="mono">{E(g['id'])}</td>
    <td><b>{E(g['topic'])}</b></td>
    <td>{E(g['conclusion'])}</td>
    <td class="small">{E(g['basis'])}</td>
    <td>{pill(g['level'], lv_class(g['level']))}</td>
    <td class="small">{E(g['condition'])}</td>
    <td class="small">{E(g['todo'])}</td>
    <td class="small">{E(g['effect'])}</td>
  </tr>''' for g in case['regulatory'])

rate_rows = ''
keys = sorted(C1['agreement_rates'])
for c in byrank:
    rate_rows += f'<tr><td class="mono">{E(c["code10"])}</td><td>{E(c["name"])}</td><td>{E(c["mfn"])}</td><td>{E(c["gen"])}</td><td>{E(c["export_tax"])}</td><td class="{"bad" if c["rebate"].startswith("0") else "good"}">{E(c["rebate"])}</td><td>{E(c["vat"])}</td><td>{E(c["rcep"].get("日本","—"))}</td><td>{E(c["rcep"].get("韩国","—"))}</td><td>{E(c["agreement_rates"].get("东盟","—"))}</td></tr>'

reg = f'''
<section class="panel" id="p-reg">
  <h2>各候选的出口监管条件</h2>
  <p class="lead">监管条件不能只写“无”或“有”，要写清是什么证件、依据哪份文件、在什么条件下成立、还有哪一步没确认。</p>
  <div class="tablewrap">
  <table class="tbl">
    <thead><tr><th>#</th><th style="width:11%">主题</th><th style="width:22%">结论</th><th style="width:16%">依据</th><th>等级</th><th style="width:12%">适用条件</th><th style="width:14%">仍需确认</th><th style="width:12%">对业务的影响</th></tr></thead>
    <tbody>{reg_rows}</tbody>
  </table>
  </div>
  <h3>税率一览（中国进口方向 + 出口退税）</h3>
  <div class="tablewrap">
  <table class="tbl">
    <thead><tr><th>编码</th><th>品名</th><th>最惠国</th><th>普通</th><th>出口关税</th><th>出口退税</th><th>增值税</th><th>RCEP日本</th><th>RCEP韩国</th><th>协定·东盟</th></tr></thead>
    <tbody>{rate_rows}</tbody>
  </table>
  </div>
  <div class="callout danger">
    <b>退税这一项必须二次核验：</b>数据源显示 C1/C2 为 13%，但 2026 年出口退税政策有调整（财政部 税务总局公告2026年第2号涉及光伏/电池），
    现行退税文库为 <b>2026C 版（税总货劳函〔2026〕214号，2026-09-30 发布）</b>；最新的第29号公告（2026-10-12）只涉及新能源汽车与电子烟设备，未涉及橡胶聚合物。
    因此 SBS 很可能仍是 13%，但<b>必须以电子税务局按 4002191300 查询结果为准</b>再对外报价。
  </div>
</section>
'''

# ---------------- ⑦ missing ----------------
miss_rows = ''.join(f'''
  <tr class="{'row-high' if m[3]=='高' else 'row-mid'}">
    <td class="mono">{E(m[0])}</td><td><b>{E(m[1])}</b></td><td>{E(m[2])}</td>
    <td><span class="prio {'p-hi' if m[3]=='高' else 'p-mid'}">{E(m[3])}</span></td>
    <td>{E(m[4])}</td><td>{E(m[5])}</td>
  </tr>''' for m in case['missing'])
miss = f'''
<section class="panel" id="p-miss">
  <h2>关键缺失信息：为什么现在不能给唯一编码</h2>
  <p class="lead">用户提供的信息（名称、CAS、外观、用途、非零售包装）足以锁定“章”和“税目方向”，但不足以锁定 10 位。
  下面这些字段每一个都会改变编码或退税率，补齐前只能给候选。</p>
  <div class="tablewrap">
  <table class="tbl">
    <thead><tr><th>#</th><th style="width:20%">缺失信息</th><th style="width:16%">影响哪个编码决策</th><th>优先级</th><th style="width:24%">如何补证</th><th style="width:14%">补齐后的后果</th></tr></thead>
    <tbody>{miss_rows}</tbody>
  </table>
  </div>
  <div class="callout warn">
    <b>产品参数最小集（一次性问全，别反复打断客户/技术部）：</b><br>
    ① 是否充油 + 充油比例 + 油种；② 苯乙烯含量 + 是否氢化（SBS / SEBS）；③ 是否含炭黑/白炭黑/填料/助剂及比例；
    ④ 出口形态（粒/块/粉/片/卷）与包装；⑤ 是否硫化；⑥ 主要用途；⑦ 是否零售包装；⑧ 牌号与 TDS。
  </div>
</section>
'''

# ---------------- ⑧ confirm ----------------
conf_rows = ''.join(f'''
  <tr><td class="mono">{E(q[0])}</td><td><b>{E(q[1])}</b></td><td>{E(q[2])}</td><td>{E(q[3])}</td><td>{E(q[4])}</td>
  <td><label class="chk"><input type="checkbox" data-q="{E(q[0])}"> 已确认</label></td></tr>''' for q in case['confirm'])
conf = f'''
<section class="panel" id="p-conf">
  <h2>需要报关行 / 预裁定 / 税务确认的问题</h2>
  <p class="lead">勾选框仅在本页有效，用来和报关行开会时逐条过。每一条没解除之前，不要对客户承诺“编码是确定的”或“退税一定是 13%”。</p>
  <div class="tablewrap">
  <table class="tbl">
    <thead><tr><th>#</th><th style="width:26%">问题</th><th style="width:18%">影响哪项结论</th><th style="width:24%">找谁确认</th><th style="width:12%">提出方</th><th>状态</th></tr></thead>
    <tbody>{conf_rows}</tbody>
  </table>
  </div>
  <div class="box">
    <h3>预裁定怎么走（正式路径）</h3>
    <ul>
      <li><b>依据：</b>《中华人民共和国海关预裁定管理暂行办法》（海关总署令第236号公布，第273号修正，2024-12-01 实施）。</li>
      <li><b>适用：</b>商品归类、原产地/原产资格、完税价格相关要素与估价方法（第三条）。</li>
      <li><b>时限：</b>应在货物拟进出口 <b>3 个月前</b>向备案地直属海关提出（第七条）；海关 10 日内决定是否受理（第八条），受理后 <b>60 日内</b>制发决定书（第十一条）。</li>
      <li><b>效力：</b>决定书 <b>有效期 3 年</b>，有效期内进出口相同情形货物应按该决定申报，海关予以认可（第十三、十五条）；依据的法规变化影响效力时自动失效。</li>
      <li><b>救济：</b>不服可向海关总署申请行政复议，对复议不服可提起行政诉讼（第十八条）。</li>
      <li><b>费用与风险：</b>提供虚假材料或隐瞒情况，海关可警告并处 1 万元以下罚款（第十九条）。</li>
    </ul>
  </div>
</section>
'''

# ---------------- ⑨ sources ----------------
src_rows = ''.join(f'''
  <tr class="{lv_class(s['level'])}">
    <td class="mono">{E(s['id'])}</td>
    <td><a href="{E(s['url'])}" target="_blank" rel="noopener">{E(s['name'])}</a><div class="small">{E(s['publisher'])} · {E(s['docno'])} · {E(s['date'])}</div></td>
    <td>{pill(s['level'], lv_class(s['level']))}</td>
    <td class="small">{E(s['used_for'])}</td>
    <td class="small">{E(s['verified'])}</td>
    <td class="small">{E(s['note'])}</td>
  </tr>''' for s in case['sources'])
src = f'''
<section class="panel" id="p-src">
  <h2>来源清单与证据等级</h2>
  <p class="lead">A 官方原文 / B 二手或供应商原始文件（已与官方交叉核对）/ C 第三方数据库 / D 待核验。D 级不得作为对客户的承诺依据。</p>
  <div class="tablewrap">
  <table class="tbl">
    <thead><tr><th>#</th><th style="width:30%">来源</th><th>等级</th><th style="width:16%">用于</th><th style="width:18%">核验情况</th><th style="width:16%">备注</th></tr></thead>
    <tbody>{src_rows}</tbody>
  </table>
  </div>
  <div class="box">
    <h3>本次做过的核验动作（可复现）</h3>
    <ol>
      <li>下载《中华人民共和国进出口税则（2026）》官方 PDF 全文（1492 页），逐条核对 40.02 / 40.05 / 39.03 条文与 MFN、普通、协定、RCEP 税率。</li>
      <li>抓取 22 个中国 10 位编码详情页，取得品名、申报要素、监管条件、检验检疫、退税快照；税号与税率再与官方税则逐一比对一致。</li>
      <li>下载 2026 年度《两用物项和技术进出口许可证管理目录》PDF（168 页）全文检索：无“苯乙烯/丁二烯/SBS”，4002 仅出现在无关页眉。</li>
      <li>读取 2026 年《出口许可证管理货物目录》公告全文，确认 43 种许可证货物不含合成橡胶。</li>
      <li>读取税总 2026C 版退税文库通知与财政部/税务总局 2026 年第29号公告，确认 SBS 未被最新调整覆盖。</li>
      <li>调用美国 USITC HTS 官方检索接口，取得 4002.19.00.14（SBS）等统计细分。</li>
      <li>下载 SBS 供应商 SDS（LCY 3780）与 CAS 9003-55-8 物质信息，确认形态、用途、非危险品与 CAS 族类号性质。</li>
    </ol>
  </div>
  <div class="callout">{E(case['not_advice'])}</div>
</section>
'''

CSS = r'''
:root{
  --bg:#f6f7fb; --card:#fff; --ink:#1b2430; --muted:#5b6675; --line:#e3e7ee;
  --brand:#1f3864; --brand2:#2f5597; --ok:#1e7b4a; --okbg:#e7f5ec;
  --warn:#8a5a00; --warnbg:#fff4dc; --bad:#b3261e; --badbg:#fdecea; --info:#22556e;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",system-ui,sans-serif}
.mono,.small.mono,td.mono{font-family:ui-monospace,Consolas,"SFMono-Regular",monospace}
.small{font-size:12.5px;color:var(--muted)}
.hero{background:linear-gradient(135deg,#14284a,#2f5597 60%,#3f6fbf);color:#fff;padding:26px 32px 22px}
.hero-top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;font-size:12.5px;opacity:.92}
.brand{font-weight:600;letter-spacing:.3px}
.meta span{margin-left:16px}
.hero h1{margin:14px 0 8px;font-size:26px;line-height:1.35}
.hero .sub{margin:0;max-width:1180px;font-size:14px;opacity:.95}
.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-top:18px}
.kpi{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:12px;padding:12px 14px}
.kpi .k{font-size:12px;opacity:.85}
.kpi .v{font-size:22px;font-weight:700;margin:2px 0}
.kpi .n{font-size:11.5px;opacity:.8}
.kpi.warn{background:rgba(255,196,0,.18);border-color:rgba(255,214,102,.5)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;padding:12px 32px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
.tab{border:1px solid var(--line);background:#fff;color:var(--muted);padding:7px 13px;border-radius:999px;font-size:13px;cursor:pointer}
.tab:hover{border-color:var(--brand2);color:var(--brand)}
.tab.active{background:var(--brand);border-color:var(--brand);color:#fff;font-weight:600}
main{padding:22px 32px 60px;max-width:1500px;margin:0 auto}
.panel{display:none;animation:fade .18s ease}
.panel.active{display:block}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
h2{font-size:21px;margin:6px 0 6px;color:var(--brand)}
h3{font-size:16px;margin:22px 0 8px;color:#243b62}
h5{margin:12px 0 6px;font-size:13px;color:var(--brand2);text-transform:none}
.lead{color:var(--muted);margin:0 0 16px;max-width:1150px}
.flow{display:grid;gap:12px}
.step{display:flex;gap:14px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--brand2);border-radius:10px;padding:14px 16px}
.step.ok{border-left-color:var(--ok)}
.step.warn{border-left-color:#e0a800}
.step .no{width:30px;height:30px;flex:none;border-radius:50%;background:var(--brand);color:#fff;display:grid;place-items:center;font-weight:700}
.step h4{margin:0 0 6px;font-size:15px}
.step p{margin:4px 0}
.callout{margin-top:16px;padding:13px 16px;border-radius:10px;background:#eef3fb;border:1px solid #cddcf3;font-size:14px}
.callout.danger{background:var(--badbg);border-color:#f3c1bd;color:#6d1a15}
.callout.warn{background:var(--warnbg);border-color:#f0dca8;color:#5c3d00}
.tablewrap{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:10px}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px;min-width:760px}
.tbl th{background:#eef2f9;text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);position:sticky;top:0;font-size:12.5px}
.tbl td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
.tbl tr:last-child td{border-bottom:0}
.tbl tr:hover td{background:#fafcff}
.tbl .quote{font-size:12.5px;color:#33414f}
.good{color:var(--ok);font-weight:700}
.bad{color:var(--bad);font-weight:700}
.row-bad td{background:#fff7f6}
.row-mid td{background:#fffdf5}
.row-high td{background:#fff8f7}
.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
#q{flex:1;min-width:260px;padding:9px 12px;border:1px solid var(--line);border-radius:9px;font-size:14px}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.fbtn{border:1px solid var(--line);background:#fff;padding:6px 11px;border-radius:999px;font-size:12.5px;cursor:pointer;color:var(--muted)}
.fbtn.active{background:var(--brand2);border-color:var(--brand2);color:#fff}
.cards{display:grid;gap:14px;margin-top:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.card.rank-1{border-color:#9ccfae;box-shadow:0 1px 0 #dff0e5 inset}
.card.rank-2{border-color:#b9cde8}
.card-h{display:flex;gap:14px;align-items:flex-start;padding:14px 16px;border-bottom:1px solid var(--line);background:#fbfcff}
.rank{font-weight:800;color:var(--brand2);font-size:18px;flex:none;width:38px}
.ch-main{flex:1;min-width:0}
.code{font-size:18px;font-weight:700;letter-spacing:.5px}
.code .hs6{margin-left:10px;font-size:12px;color:var(--muted);font-weight:400}
.ch-main h3{margin:2px 0 6px;font-size:15.5px;color:#1d2b45}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;border:1px solid transparent;white-space:nowrap}
.p-verdict{background:#e8f0ff;color:#1f3864;border-color:#c9d8f5}
.p-conf{background:#f3f0ff;color:#45309b;border-color:#ddd4f7}
.p-reg{background:#f1f3f5;color:#3a4653;border-color:#e2e6eb}
.lv-a{background:var(--okbg)!important;color:var(--ok)!important;border-color:#bfe3cd!important}
.lv-b{background:#eaf3fb!important;color:#1b5c86!important;border-color:#c5dff1!important}
.lv-c{background:var(--warnbg)!important;color:#7a5000!important;border-color:#efdca5!important}
.lv-d{background:var(--badbg)!important;color:var(--bad)!important;border-color:#f2c3be!important}
.rates{display:flex;gap:10px;flex:none}
.rates>div{text-align:center;background:#fff;border:1px solid var(--line);border-radius:9px;padding:6px 10px;min-width:76px}
.rates span{display:block;font-size:11px;color:var(--muted)}
.rates b{font-size:16px}
.rates .hot{background:var(--badbg);border-color:#f3c1bd}
.rates .hot b{color:var(--bad)}
.card-b{display:grid;grid-template-columns:1.05fr 1.15fr 1fr;gap:16px;padding:14px 16px}
.card-b ul{margin:0;padding-left:18px}
.card-b li{margin:3px 0;font-size:13px}
.card-b p{margin:4px 0;font-size:13px}
.risk{color:#7a2018}
.card-f{display:flex;gap:18px;padding:10px 16px;border-top:1px solid var(--line);background:#fbfcff;font-size:12.5px}
.card-f a{color:var(--brand2);text-decoration:none}
.card-f a:hover{text-decoration:underline}
.fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.fcard{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.fh{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.fcard .row{display:flex;gap:10px;padding:4px 0;border-bottom:1px dashed #eef1f5;font-size:13px}
.fcard .row span{flex:none;width:82px;color:var(--muted);font-size:12px}
.fcard .note{margin:10px 0;font-size:12.5px;color:#3c4a59}
.fcard a{font-size:12px;color:var(--brand2);text-decoration:none;word-break:break-all}
.box{background:#fff;border:1px solid var(--line);border-radius:12px;padding:6px 18px 14px;margin-top:18px}
.box ul,.box ol{margin:6px 0;padding-left:20px}
.box li{margin:5px 0;font-size:13.5px}
.chk{font-size:12.5px;color:var(--muted);cursor:pointer;user-select:none}
.chk input{margin-right:4px}
.chk.on{color:var(--ok);font-weight:600}
.prio{display:inline-block;padding:1px 8px;border-radius:6px;font-size:12px;font-weight:700}
.p-hi{background:var(--badbg);color:var(--bad)}
.p-mid{background:var(--warnbg);color:var(--warn)}
footer{padding:18px 32px 40px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);background:#fff}
@media (max-width:1100px){
  .kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  .card-b{grid-template-columns:1fr}
  .rates{width:100%;justify-content:flex-start}
  .card-h{flex-wrap:wrap}
}
@media (max-width:640px){
  main{padding:16px}
  .hero{padding:20px}
  .hero h1{font-size:20px}
  .tabs{padding:10px 16px}
}
@media print{
  .tabs{display:none}
  .panel{display:block!important;page-break-inside:avoid}
}
'''

JS = r'''
(function(){
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  var panels=[].slice.call(document.querySelectorAll('.panel'));
  function show(k){
    tabs.forEach(function(t){t.classList.toggle('active',t.dataset.tab===k)});
    panels.forEach(function(p){p.classList.toggle('active',p.id==='p-'+k)});
    window.scrollTo({top:0,behavior:'smooth'});
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){show(t.dataset.tab)})});

  var q=document.getElementById('q');
  var fbtns=[].slice.call(document.querySelectorAll('.fbtn'));
  var cards=[].slice.call(document.querySelectorAll('.card'));
  var rows=[].slice.call(document.querySelectorAll('#ctab tbody tr'));
  var cur='all';
  function apply(){
    var s=(q&&q.value||'').trim().toLowerCase();
    cards.forEach(function(c){
      var hitF=(cur==='all');
      if(!hitF){
        var r=+c.dataset.rank;
        hitF=(cur==='main'&&r<=3)||(cur==='cond'&&(r===4||r===5))||(cur==='form'&&r>=6);
      }
      var hitS=!s||c.textContent.toLowerCase().indexOf(s)>=0;
      c.style.display=(hitF&&hitS)?'':'none';
    });
    rows.forEach(function(r){
      var f=r.dataset.f;
      var hitF=(cur==='all')||(cur==='main'&&f==='main')||(cur==='cond'&&f==='cond')||(cur==='form'&&f==='form');
      var hitS=!s||r.textContent.toLowerCase().indexOf(s)>=0;
      r.style.display=(hitF&&hitS)?'':'none';
    });
  }
  if(q){q.addEventListener('input',apply)}
  fbtns.forEach(function(b){b.addEventListener('click',function(){
    fbtns.forEach(function(x){x.classList.remove('active')});
    b.classList.add('active');cur=b.dataset.f;apply();
  })});
  document.querySelectorAll('.chk input').forEach(function(cb){
    cb.addEventListener('change',function(){cb.parentNode.classList.toggle('on',cb.checked)});
  });
  window.__reportReady=true;
})();
'''

doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HS 候选研究 · SBS 热塑性弹性体 · ChemClaw</title>
<style>{CSS}</style>
</head>
<body>
{header}
{nav}
<main>
{flow}
{cands}
{basis}
{amb}
{layer}
{reg}
{miss}
{conf}
{src}
</main>
<footer>
  ChemClaw 外贸销售 · 查海关商品编码候选 · 案例 {E(M['case_id'])} · 生成于 {E(M['query_date'])} ·
  HS 版本：{E(M['hs_version'])} · 退税文库：{E(M['rebate_version'])}<br>
  {E(case['not_advice'])}
</footer>
<script>{JS}</script>
</body>
</html>'''

M = case['meta']
default_name = 'HS归类候选研究报告_%s_%s.html' % (
    re.sub(r'[\\/:*?"<>|\s]+', '', case['product']['name_cn'][:24]), M['case_id'])
out = arg('--out') or os.path.join(os.path.dirname(os.path.abspath(CASE_PATH)), default_name)
open(out, 'w', encoding='utf-8').write(doc)
print('saved', out, os.path.getsize(out))
