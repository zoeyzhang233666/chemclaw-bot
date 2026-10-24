# -*- coding: utf-8 -*-
"""
build_html.py —— 生成自包含交互式研究报告（单文件 HTML，无外部依赖）

输入：build/analysis.json（analysis.py 产出）+ assets/report.css + assets/report.js
输出：build/report.html

交互（全部前端重算）：
  单耗系数滑块 / 其他成本滑块 → 加工价差、分位、年度区间
  滚动窗口与形态切换 → 滚动相关
  领先滞后最大阶与形态 → 交叉相关
  点击背离区间 → 自动定位并高亮事件台账

只做「描述性统计」，不生成交易信号；每个数字都带 N 与样本区间。
"""
import json
import os
import sys

from industry_graph import svg_industry

HERE = os.path.dirname(os.path.abspath(__file__))


def fmt(v, nd=2):
    if v is None:
        return '—'
    if isinstance(v, float):
        return f'{v:,.{nd}f}'
    return str(v)


def p_or(v):
    if v is None:
        return '—'
    return '<1e-4' if v < 1e-4 else f'{v:.3g}'


def corr_card(d, title):
    if not d or d.get('r') is None:
        return f'<div class="kpi"><div class="k">{title}</div><div class="v">样本不足</div></div>'
    return (f'<div class="kpi"><div class="k">{title}</div><div class="v mono">{d["r"]:.3f}</div>'
            f'<div class="s">N={d["n"]} · p={p_or(d["p"])} · 95%CI {d["ci95"][0]:.2f}~{d["ci95"][1]:.2f}</div></div>')


def build(analysis_path, out_path, css_path, js_path):
    A = json.load(open(analysis_path, encoding='utf-8'))
    css = open(css_path, encoding='utf-8').read()
    js = open(js_path, encoding='utf-8').read()

    meta, sp, anc = A['meta'], A['spread'], A['anchor']
    L, Rt = A['corr']['level'], A['corr']['return']
    WL, WR = A['corr'].get('weekly_level') or {}, A['corr'].get('weekly_return') or {}
    ll = A['leadlag']
    q = sp['quantiles']
    n = meta['n_obs']
    last = A['series'][-1]

    payload = {
        'series': A['series'], 'index': A['index'], 'rolling': A['rolling'],
        'crosscorr_level': ll['crosscorr_level'], 'crosscorr_return': ll['crosscorr_return'],
        'divergence': A['divergence'], 'events': A['events'], 'states': A['states'],
        'coef': meta['coef'], 'windows': meta['windows'], 'maxlag': meta['maxlag'],
    }

    kpi = [
        f'<div class="kpi"><div class="k">样本区间</div><div class="v mono" style="font-size:16px">'
        f'{meta["first"]} → {meta["last"]}</div><div class="s">{n} 个日频成对观测 · 口径见 §2</div></div>',
        f'<div class="kpi"><div class="k">最新 PX / PTA（元/吨）</div><div class="v mono">'
        f'{fmt(last["px"], 0)} / {fmt(last["pta"], 0)}</div><div class="s">含税现货基准价，同期同口径</div></div>',
        f'<div class="kpi"><div class="k">理论加工价差（λ={meta["coef"]}）</div>'
        f'<div class="v mono">{fmt(sp["current"], 0)}</div>'
        f'<div class="s">历史分位 {sp["current_pctl"]:.1f}% · P50={fmt(q["0.5"], 0)}</div></div>',
        corr_card(L, '水平相关 r（PX vs PTA）'),
        corr_card(Rt, '日收益率相关 r'),
        f'<div class="kpi"><div class="k">领先/滞后峰值</div>'
        f'<div class="v mono">{ll["best_level_lag"]["lag"]:+d} 期</div>'
        f'<div class="s">水平 r={ll["best_level_lag"]["r"]:.3f}；收益率 {ll["best_return_lag"]["lag"]:+d} 期 '
        f'r={ll["best_return_lag"]["r"]:.3f}</div></div>',
    ]

    ph_rows = []
    for p in A['phases']:
        ph_rows.append(
            f'<tr><td class="l"><b>{p["code"]}</b> {p["name"]}</td><td class="l mono">{p["start"]} ~ {p["end"]}</td>'
            f'<td class="mono">{p["n"]}</td><td class="mono">{fmt(p["px_chg"])}%</td>'
            f'<td class="mono">{fmt(p["pta_chg"])}%</td><td class="mono">{fmt(p["spread_mean"], 0)}</td>'
            f'<td class="mono">{p["corr_level"]["r"]:.3f}</td><td class="mono">{p["corr_return"]["r"]:.3f}</td></tr>')
    ph_table = ('<table><thead><tr><th class="l">阶段</th><th class="l">区间</th><th>N</th><th>PX 涨跌</th>'
                '<th>PTA 涨跌</th><th>价差均值</th><th>水平 r</th><th>收益 r</th></tr></thead><tbody>'
                + ''.join(ph_rows) + '</tbody></table>')

    div_rows = [f'<tr class="diverge-row" data-start="{d["start"]}" data-end="{d["end"]}" style="cursor:pointer">'
                f'<td class="l mono">{d["start"]} → {d["end"]}</td><td class="mono">{d["n_days"]}</td>'
                f'<td class="mono">{fmt(d["px_chg"])}%</td><td class="mono">{fmt(d["pta_chg"])}%</td>'
                f'<td class="mono">{fmt(d["spread_chg"], 0)}</td></tr>' for d in A['divergence']['runs']]
    div_table = ('<table><thead><tr><th class="l">背离区间（点击定位事件）</th><th>天数</th><th>PX 涨跌</th>'
                 '<th>PTA 涨跌</th><th>价差变化</th></tr></thead><tbody>' + ''.join(div_rows) + '</tbody></table>'
                 ) if div_rows else ('<div class="note">在样本内未识别出满足「|ΔPX| ≥ 3% 且 PTA 反向」的持续背离区间；'
                                     '更细的传导强弱请看 §5 滚动相关与 §6 阶段表。</div>')

    ev_rows = [f'<tr class="ev-row" data-date="{e["date"]}" style="cursor:pointer">'
               f'<td class="l mono">{e["date"]}</td><td class="l"><span class="tag">{e["type"]}</span></td>'
               f'<td class="l">{e["title"]}</td><td class="l" style="white-space:normal;text-align:left">{e["detail"]}</td>'
               f'<td class="l"><span class="tag neg">{e["impact"]}</span></td></tr>' for e in A['events']]
    ev_table = ('<table><thead><tr><th class="l">日期</th><th class="l">类型</th><th class="l">事件</th>'
                '<th class="l" style="text-align:left">说明（产业数据支持）</th><th class="l">对价差方向</th>'
                '</tr></thead><tbody>' + ''.join(ev_rows) + '</tbody></table>')

    g_rows = []
    for k, v in ll['granger'].items():
        if 'F' not in v:
            continue
        p = v['p']
        cls = 'pos' if p < 0.05 else 'neg'
        g_rows.append(f'<tr><td class="l mono">{k}</td><td class="mono">{v["F"]:.3f}</td>'
                      f'<td class="mono">{p_or(p)}</td><td class="mono">{v["n"]}</td>'
                      f'<td class="l"><span class="tag {cls}">{"含增量信息" if p < 0.05 else "无显著增量信息"}</span></td></tr>')
    g_table = ('<table><thead><tr><th class="l">Granger 检验（滞后 p）</th><th>F</th><th>p</th><th>N</th>'
               '<th class="l">结论</th></tr></thead><tbody>' + ''.join(g_rows) + '</tbody></table>')

    sens_rows = []
    sens = sp['sensitivity']
    step = max(1, (len(sens) - 1) // 6)
    for i, s in enumerate(sens):
        if i % step and i != len(sens) - 1:
            continue
        sens_rows.append(f'<tr><td class="mono">{s["coef"]:.3f}</td><td class="mono">{fmt(s["mean"], 0)}</td>'
                         f'<td class="mono">{fmt(s["p10"], 0)}</td><td class="mono">{fmt(s["p50"], 0)}</td>'
                         f'<td class="mono">{fmt(s["p90"], 0)}</td><td class="mono">{fmt(s["current"], 0)}</td></tr>')
    sens_table = ('<table><thead><tr><th>单耗系数 λ</th><th>价差均值</th><th>P10</th><th>P50</th><th>P90</th>'
                  '<th>最新</th></tr></thead><tbody>' + ''.join(sens_rows) + '</tbody></table>')

    win_chips = ''.join(
        f'<span class="chip{" on" if i == min(1, len(meta["windows"]) - 1) else ""}" data-win="{w}">{w}</span>'
        for i, w in enumerate(meta['windows']))

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PX × PTA 上下游价格联动研究报告</title>
<style>{css}</style></head><body>
<div class="wrap">
<header>
  <h1>PX × PTA 上下游价格联动研究</h1>
  <div class="sub">价格传导是否明显 · 哪些阶段背离 · 理论加工价差的定位 · 领先滞后与产业数据核对</div>
  <div>
    <span class="badge live">真实公开数据</span>
    <span class="badge">数据源：100ppi 生意社基准价 / SunSirs 日度现货价（双源互校）</span>
    <span class="badge">频率：日频，成对有效样本 N={n}</span>
    <span class="badge">窗口：{meta['first']} ~ {meta['last']}</span>
  </div>
</header>

<nav>
  <a href="#s1">1 产业关系</a><a href="#s2">2 口径对齐</a><a href="#s3">3 价格曲线</a>
  <a href="#s4">4 加工价差</a><a href="#s5">5 滚动相关</a><a href="#s6">6 背离阶段</a>
  <a href="#s7">7 领先滞后</a><a href="#s8">8 事件核对</a><a href="#s9">9 结论</a>
</nav>

<div class="kpis">{''.join(kpi)}</div>

<section id="s1">
  <h2><span class="n">1</span>产业关系核验：能否计算加工价差</h2>
  <p class="lede">先回答「是否存在多种主要原料」——只有单一主要原料且单耗可追溯，才允许做单耗折算。</p>
  <div class="split">
    <div class="panel"><div class="svgbox">{svg_industry()}</div></div>
    <div class="panel">
      <h3 style="margin-top:0">核验结论</h3>
      <table><tbody>
        <tr><td class="l">主要原料</td><td class="l"><b>PX（对二甲苯），唯一主要原料</b></td></tr>
        <tr><td class="l">是否多条原料路线</td><td class="l"><b>否</b>（无煤基/生物基商业化路线）</td></tr>
        <tr><td class="l">辅料 / 溶剂</td><td class="l">醋酸 0.030~0.039 t/t；Co-Mn-Br 催化剂</td></tr>
        <tr><td class="l">理论单耗</td><td class="l mono">0.655 t PX / t PTA</td></tr>
        <tr><td class="l">单套装置实测</td><td class="l mono">0.647 ~ 0.657</td></tr>
        <tr><td class="l">工艺路线</td><td class="l">PX 液相空气氧化 → CTA → 加氢精制 → PTA</td></tr>
        <tr><td class="l">技术代际</td><td class="l">BP / 英威达 P8(+) / 国产（逸盛、昆仑）</td></tr>
      </tbody></table>
      <div class="note blue"><b>判定：可以计算理论加工价差。</b>代际间单耗仅差 0.647~0.657（±0.8%），
      但能耗与折旧差异大，因此该价差只能读作<b>不含折旧与能源的收入型加工费近似</b>，不等于企业利润。</div>
    </div>
  </div>
</section>

<section id="s2">
  <h2><span class="n">2</span>价格数据对齐：日期、地区、税费、计量单位</h2>
  <p class="lede">两个序列必须同日期、同税基、同单位、同现货口径，否则加工价差会被口径差异污染。</p>
  <div class="panel">
    <table>
      <thead><tr><th class="l">口径项</th><th class="l">上游 PX</th><th class="l">下游 PTA</th><th class="l">处理方式</th></tr></thead>
      <tbody>
        <tr><td class="l">价格定义</td><td class="l">现货基准价（华东综合）</td><td class="l">现货基准价（华东）</td>
            <td class="l">同一机构同一口径，避免跨源拼接</td></tr>
        <tr><td class="l">计量单位</td><td class="l">元/吨</td><td class="l">元/吨</td><td class="l">一致</td></tr>
        <tr><td class="l">税费</td><td class="l">含增值税</td><td class="l">含增值税</td><td class="l">税基一致，无需价税分离</td></tr>
        <tr><td class="l">日期基准</td><td class="l">价格口径日</td><td class="l">价格口径日</td>
            <td class="l">英文站发布日滞后 1 天，已按链接日期校正</td></tr>
        <tr><td class="l">频率</td><td class="l">日度</td><td class="l">日度</td><td class="l">成对有效样本；缺日不插值</td></tr>
        <tr><td class="l">交叉校验</td><td class="l" colspan="2">两源重叠期逐日一致（差异 0 元/吨）</td>
            <td class="l">双源互证</td></tr>
      </tbody>
    </table>
    <div class="note"><b>口径风险：</b>现货基准价含贸易与区域升贴水，且未剔运费；与期货价格不可混用。
    周度口径复核：水平 r={WL.get('r', '—')}（N={WL.get('n', '—')}），收益率 r={WR.get('r', '—')}（N={WR.get('n', '—')}）。</div>
  </div>
</section>

<section id="s3">
  <h2><span class="n">3</span>价格曲线与变化</h2>
  <p class="lede">水平关系与变化关系是两件事，必须分开报：前者含共同趋势，后者才反映逐期传导。</p>
  <div class="panel">
    <div class="chips" id="modeChips">
      <span class="chip on" data-mode="level">价格水平（元/吨）</span>
      <span class="chip" data-mode="index">标准化指数（首日=100）</span>
      <span class="chip" data-mode="ret">日收益率 %</span>
    </div>
    <div class="chartbox"><canvas id="cPrice" height="380"></canvas></div>
    <div class="legend"><span><i style="background:var(--acc)"></i>PX 对二甲苯</span>
      <span><i style="background:var(--acc2)"></i>PTA 精对苯二甲酸</span>
      <span><i style="background:var(--warn)"></i>理论加工价差（{meta['coef']}×PX，单独缩放）</span></div>
    <div id="rangeTable"></div>
    <div class="note">水平 r = <b>{L['r']:.3f}</b>（N={L['n']}，95%CI {L['ci95'][0]:.2f}~{L['ci95'][1]:.2f}）；
    日收益率 r = <b>{Rt['r']:.3f}</b>（N={Rt['n']}，p={p_or(Rt['p'])}）。
    水平高度相关主要来自<b>共同成本中枢（原油—石脑油）</b>与共同趋势，<b>不能</b>据此认定逐日传导强。</div>
  </div>
</section>

<section id="s4">
  <h2><span class="n">4</span>理论加工价差与历史分位</h2>
  <p class="lede">加工价差 = PTA 现货 − λ × PX 现货 − 其他成本；λ 可调，滑块改变即全页重算。</p>
  <div class="panel">
    <div class="ctrl" style="margin-bottom:12px">
      <div><label>单耗系数 λ（吨 PX / 吨 PTA）：<output id="coefOut">{meta['coef']:.3f}</output></label>
        <input id="coefRange" type="range" min="0.60" max="0.72" step="0.001" value="{meta['coef']}"></div>
      <div><label>其他成本（元/吨，醋酸+动力+折旧的简化项）：<output id="ocOut">0</output></label>
        <input id="ocRange" type="range" min="0" max="800" step="10" value="0"></div>
      <div><button class="ghost" id="resetCoef">恢复默认 λ={meta['coef']}</button></div>
    </div>
    <div class="chartbox"><canvas id="cSpread" height="300"></canvas></div>
    <div class="legend"><span><i style="background:var(--warn)"></i>加工价差（元/吨）</span>
      <span><i style="background:rgba(143,160,181,.6)"></i>虚线＝P10 / P50 / P90 历史分位</span></div>
    <div class="kpis" id="spreadKpis"></div>
    <h3>单耗敏感性（λ 不确定时价差如何变化）</h3>
    {sens_table}
    <div class="note"><b>锚定系数检验：</b>log PTA 对 log PX 的回归斜率 = <b>{anc['log_log_slope']:.3f}</b>
    （HAC 标准误 {anc['se_hac']:.4f}），隐含传导系数 ≈ <b>{anc['implied_factor']:.3f}</b>；
    均值 PTA/PX = <b>{anc['mean_pta_over_px']:.3f}</b>。<br>{anc['interpretation']}</div>
  </div>
</section>

<section id="s5">
  <h2><span class="n">5</span>滚动相关性：传导是否稳定</h2>
  <p class="lede">窗口 <b>80% 有效样本</b>以下不画（留空），避免把噪声当结论。</p>
  <div class="panel">
    <div class="ctrl" style="margin-bottom:8px">
      <div><label>滚动窗口（观测数）</label><div class="chips" id="winChips">{win_chips}</div></div>
      <div><label>形态</label><div class="chips" id="rollMode">
        <span class="chip on" data-rm="level">价格水平 r</span>
        <span class="chip" data-rm="return">收益率 r</span></div></div>
    </div>
    <div class="chartbox"><canvas id="cRoll" height="300"></canvas></div>
    <div class="kpis" id="rollKpis"></div>
  </div>
</section>

<section id="s6">
  <h2><span class="n">6</span>跟随与背离阶段</h2>
  <p class="lede">{A['divergence']['definition']}。点击区间 → 自动跳到 §8 并高亮同期事件。</p>
  <div class="panel">
    {div_table}
    <h3>分阶段统计</h3>
    {ph_table}
    <div class="note red">方向相反（上游涨、下游跌）必然放大加工价差波动——这不是数据失真，
    而是产业链利润在环节间重新分配；判定成因必须回到装置、库存、需求等产业数据。</div>
  </div>
</section>

<section id="s7">
  <h2><span class="n">7</span>领先 / 滞后统计</h2>
  <p class="lede">交叉相关看共变时点；Granger 检验看是否含增量预测信息。两者都不是因果证据。</p>
  <div class="panel">
    <div class="ctrl" style="margin-bottom:8px">
      <div><label>最大滞后阶数：<output id="lagOut">{min(20, meta['maxlag'])}</output></label>
        <input id="lagRange" type="range" min="1" max="{meta['maxlag']}" step="1" value="{min(20, meta['maxlag'])}"></div>
      <div><label>形态</label><div class="chips" id="ccMode">
        <span class="chip on" data-cc="level">价格水平</span>
        <span class="chip" data-cc="return">收益率</span></div></div>
    </div>
    <div class="chartbox"><canvas id="cCC" height="300"></canvas></div>
    <div class="note blue">横轴 &gt; 0：PX 领先 PTA；&lt; 0：PTA 领先 PX。若峰值贴近 0 且两侧快速衰减，
    说明二者几乎是同步定价，而非存在明确传导时滞。</div>
    {g_table}
  </div>
</section>

<section id="s8">
  <h2><span class="n">8</span>事件核对：装置、库存、需求</h2>
  <p class="lede">统计只能指出「哪段不规则」，成因必须回到产业数据；事件仅用于解释，不用于证明因果。</p>
  <div class="panel" style="overflow-x:auto">{ev_table}</div>
</section>

<section id="s9">
  <h2><span class="n">9</span>结论、适用边界与禁止事项</h2>
  <div class="split">
    <div class="panel">
      <h3 style="margin-top:0">结论</h3>
      <ul class="concl">
        <li>PX 为 PTA 唯一主要原料，单耗可靠（λ=0.655 t/t），<b>可以</b>计算理论加工价差。</li>
        <li>水平 r=<b>{L['r']:.3f}</b>（N={L['n']}）很高，但日收益率 r 仅 <b>{Rt['r']:.3f}</b>（p={p_or(Rt['p'])}）——
            高度水平相关主要来自共同成本中枢，不是逐日传导。</li>
        <li>最新加工价差 <b>{fmt(sp['current'], 0)}</b> 元/吨，历史分位 <b>{sp['current_pctl']:.1f}%</b>
            （P10={fmt(q['0.1'], 0)}，P50={fmt(q['0.5'], 0)}，P90={fmt(q['0.9'], 0)}）。</li>
        <li>领先滞后峰值：水平口径 <b>{ll['best_level_lag']['lag']:+d}</b> 期（r={ll['best_level_lag']['r']:.3f}），
            收益口径 <b>{ll['best_return_lag']['lag']:+d}</b> 期（r={ll['best_return_lag']['r']:.3f}）；
            结论应以后者为准。</li>
        <li>分阶段看，价差与相关强度都存在结构性差异，见 §6 表。</li>
      </ul>
    </div>
    <div class="panel">
      <h3 style="margin-top:0">禁止事项</h3>
      <ul class="concl">
        <li>不得把相关性写成「PX 涨价导致 PTA 涨价」——两者同受油价驱动。</li>
        <li>不得把加工价差直接当企业利润（未扣能源、折旧、物流、检修）。</li>
        <li>不得给交易建议、目标价、做多/做空信号。</li>
        <li>单耗无出处时不得自造系数；只能报区间并做敏感性。</li>
        <li>缺失数据不得插值填充；样本不足时必须写「样本不足」。</li>
      </ul>
    </div>
  </div>
</section>

<footer>
  数据：100ppi 生意社（中文基准价）、SunSirs（英文日度现货价），逐日抓取、双源互校；统计内核为纯 Python 标准库
  （Pearson/Spearman、Fisher-z、Newey-West HAC、有效样本量、交叉相关、Granger）。所有显著性基于成对有效样本，缺失不插值。
  <br>本报告为描述性统计研究，不构成投资建议。
</footer>
</div>
<script>window.__A__ = {json.dumps(payload, ensure_ascii=False)};</script>
<script>{js}</script>
</body></html>"""

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('written', out_path, len(html), 'bytes')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'build', 'analysis.json'),
          sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'build', 'report.html'),
          os.path.join(HERE, 'assets', 'report.css'), os.path.join(HERE, 'assets', 'report.js'))
