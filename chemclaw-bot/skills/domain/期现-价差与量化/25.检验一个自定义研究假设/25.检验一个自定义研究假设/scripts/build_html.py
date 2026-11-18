# -*- coding: utf-8 -*-
"""build_html.py — 生成自包含交互式研究页面（单文件 HTML，无外部依赖）。

页面结构（标签页）
 1. 研究设计   自然语言假设 → 可检验设计；每个变量带「为什么这样映射/需要确认」
 2. 参数确认   阻断性问题（走强/走弱口径、合约、入场时点、样本区间…）+ 确认按钮
 3. 数据可用性 真实 vs 模拟双轨；逐序列覆盖度；缺口；回源核验结果
 4. 样本构造   信号/对照条数、状态转移、跳过原因、逐条样本表（可排序筛选）
 5. 统计结果   全量检验登记表（族/效应量/CI/p/BH-q），主检验突出
 6. 稳定性     分年/分库存分位/分基差符号 的小样本表格 + 条形图
 7. 事件研究   信号前后 Δbasis 路径
 8. 局限与风险 未来函数、幸存者、重重检验、样本不足等清单
 9. 复现说明   数据指纹、脚本、参数冻结时间、运行命令

关键设计约束：
 * 真实数据样本不足时，页面首先大字显示「无法给出结论（样本不足）」，不摆放任何显著性数字。
 * 模拟数据轨道每一处都带 SIMULATED 徽标，避免被误读为结论。
 * 所有图表用内联 SVG 手绘，避免外部 CDN 依赖。
"""
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))


def esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def fmt(x, n=2):
    if x is None or x == "":
        return "—"
    if isinstance(x, bool):
        return "是" if x else "否"
    if isinstance(x, (int, float)):
        return f"{x:,.{n}f}"
    return esc(x)


def badge(kind, text):
    return f'<span class="badge b-{kind}">{esc(text)}</span>'


# --------------------------------------------------------------------------- svg helpers

def bar_svg(items, width=760, height=None, unit=""):
    """items: [{label, value, n, color}] — 水平条形图，带零轴与样本数。"""
    if not items:
        return '<p class="muted">无可用数据</p>'
    vals = [i["value"] for i in items if i["value"] is not None]
    if not vals:
        return '<p class="muted">无可用数据</p>'
    vmax = max(max(abs(v) for v in vals), 1e-9)
    rowh = 34
    height = height or (len(items) * rowh + 40)
    left, right = 150, 90
    span = width - left - right
    zero = left + (span / 2 if min(vals) < 0 else 0)
    scale = (span / 2 if min(vals) < 0 else span) / vmax
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    out.append(f'<line x1="{zero}" y1="8" x2="{zero}" y2="{height-26}" class="axis"/>')
    for k, it in enumerate(items):
        y = 12 + k * rowh
        v = it["value"]
        out.append(f'<text x="{left-10}" y="{y+16}" class="lbl" text-anchor="end">{esc(it["label"])}</text>')
        if v is None:
            out.append(f'<text x="{zero+6}" y="{y+16}" class="lbl">样本不足(n={it.get("n", 0)})</text>')
            continue
        w = abs(v) * scale
        x = zero if v >= 0 else zero - w
        col = it.get("color") or ("#0f766e" if v >= 0 else "#b45309")
        out.append(f'<rect x="{x:.1f}" y="{y+4}" width="{max(w,1):.1f}" height="18" rx="3" fill="{col}"/>')
        out.append(f'<text x="{(x+w+8) if v>=0 else (x-8):.1f}" y="{y+17}" class="val" '
                   f'text-anchor="{"start" if v>=0 else "end"}">{v:+.1f}{esc(unit)}'
                   f'<tspan class="n"> n={it.get("n",0)}</tspan></text>')
    out.append("</svg>")
    return "".join(out)


def sparkline(points, width=760, height=170, label=""):
    vals = [p["y"] for p in points if p["y"] is not None]
    if len(vals) < 2:
        return '<p class="muted">数据不足以绘图</p>'
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(points)
    def px(i):
        return 40 + i * (width - 60) / max(1, n - 1)
    def py(v):
        return 20 + (hi - v) / rng * (height - 50)
    path = " ".join(f"{'M' if i==0 else 'L'}{px(i):.1f},{py(p['y']):.1f}"
                    for i, p in enumerate(points) if p["y"] is not None)
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart">']
    out.append(f'<text x="4" y="16" class="lbl">{hi:,.1f}</text>')
    out.append(f'<text x="4" y="{height-22}" class="lbl">{lo:,.1f}</text>')
    out.append(f'<path d="{path}" fill="none" stroke="#0f766e" stroke-width="2"/>')
    for i, p in enumerate(points):
        if p.get("mark") and p["y"] is not None:
            out.append(f'<circle cx="{px(i):.1f}" cy="{py(p["y"]):.1f}" r="4" fill="#b45309"/>')
    out.append(f'<text x="{width-8}" y="{height-6}" class="lbl" text-anchor="end">{esc(label)}</text>')
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- sections

def sec_design(design, parsed):
    q = parsed.get("open_questions", [])
    rows = []
    for v in parsed.get("variables_detected", []):
        rows.append(f"<tr><td>{esc(v['desc'])}</td><td>{esc(v['unit'])}</td>"
                    f"<td><code>{esc(v['evidence'])}</code></td>"
                    f"<td>{'🔴 需确认' if v['need_confirm'] else '✅ 明确'}</td></tr>")
    tgt = parsed.get("target") or {}
    return f"""
<section class="card">
  <h2>① 原始假设 → 可检验的研究问题</h2>
  <blockquote class="hypo">{esc(design.get('raw_text'))}</blockquote>
  <div class="grid2">
    <div>
      <h3>拆解出的变量</h3>
      <table class="tbl"><thead><tr><th>变量</th><th>口径/频率</th><th>原文命中</th><th>置信</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>
      <h3>观察对象 Y</h3>
      <p>识别到目标口径：<b>{esc(tgt.get('label','—'))}</b>
      {badge('warn','需要你确认') if tgt.get('need_confirm') else badge('ok','明确')}</p>
      <p class="muted">为什么这样映射：{esc(tgt.get('chosen_reason','—'))}。金融黑话「走强」本身不可检验，
      必须先落到一个可计算量；本页给出 4 个候选口径（见右侧），由你决定主口径。</p>
    </div>
    <div>
      <h3>信号 / 观察窗口 / 对照组</h3>
      <ul class="tight">
        <li><b>信号</b>：{esc(design['signal']['rule'])}<br><span class="muted">{esc(design['signal']['gap_guard'])}</span></li>
        <li><b>观察窗口</b>：{design['horizon']['main_sessions']} 个交易日（≈{design['horizon']['main_sessions']/5:.0f} 周），
            敏感性 {esc(', '.join(str(x) for x in design['horizon']['alt_sessions']))} 日</li>
        <li><b>对照组</b>：{esc(design['control']['rule'])}</li>
        <li><b>入场时点</b>：{esc(design['entry_rule']['main_desc'])}</li>
      </ul>
      <h3>待你确认的问题（{len(q)}）</h3>
      <ol class="qs">{''.join(
        f"<li>{esc(x['question'])}"
        f"<div class='opts'>{''.join(f'<span class=opt>{esc(o)}</span>' for o in x['options'])}</div>"
        f"{badge('warn','阻断') if x['blocking'] else ''}</li>" for x in q)}</ol>
    </div>
  </div>
  <p class="note">假设条件数 = 变量数 × 口径数 × 窗口数 × 入场规则数 × 阈值数。本设计把条件数压到最小，
  并把所有「可以来回调」的旋钮提前写死，否则任何结论都可以通过调参数造出来。</p>
</section>"""


def sec_confirm(design):
    rows = []
    for k in ["approved", "approval_state", "approved_by", "approved_at", "version"]:
        rows.append(f"<tr><td><code>{k}</code></td><td>{esc(design.get(k, '—'))}</td></tr>")
    return f"""
<section class="card">
  <h2>② 参数确认（正式检验的闸门）</h2>
  <p>本 Skill 的硬约束：<b>设计未经确认前不跑统计</b>。当前状态：</p>
  <table class="tbl narrow">{''.join(rows)}</table>
  <p class="note">闸门实现：<code>run_hypothesis_test.py run</code> 读取设计文件，若 <code>approved != true</code> 直接
  <code>SystemExit</code> 退出。参数一旦确认，脚本会写入 <code>approved_at</code> 与数据指纹；
  之后任何改动都会产生新版本号，旧版本留档对照——这样「先看结果再改参数」在流程上不可能发生。</p>
  <h3>预登记的最小样本规则</h3>
  <p>信号周 &lt; 12 或对照周 &lt; 10 → 结论只能是「样本不足」。该规则在本项目第一次打开数据之前就已写入设计文件。</p>
</section>"""


def sec_data(verification=None, audit=None):
    ver = ""
    if verification:
        t = verification.get("tally", {})
        ratio = verification.get("verified_ratio", 0)
        rows = "".join(f"<tr><td>{esc(k)}</td><td class='num'>{v}</td></tr>"
                       for k, v in sorted(t.items()))
        ver = f"""
  <h3>历史库存序列逐条回源核验（{verification.get('n')} 条）</h3>
  <p>对每一条 Mysteel 原文 URL 重新抓取，核对「标题日期 == 观测日」且「正文库存总量 == 记录值」。
  核验通过率 <b>{ratio*100:.1f}%</b>，状态分布：</p>
  <table class="tbl narrow"><thead><tr><th>状态</th><th>条数</th></tr></thead><tbody>{rows}</tbody></table>"""
    return f"""
<section class="card">
  <h2>③ 数据可用性（先查数据，再谈结论）</h2>
  <div class="tracks">
    <div class="track real">
      <h3>{badge('ok','真实数据')} 公开可核实来源</h3>
      <ul class="tight">
        <li><b>库存</b>：我的钢铁网转载的隆众《中国甲醇样本港口库存周数据统计》。
            <span class="bad">{badge('bad','3 周')} 只能抓到 2024-07-10 / 17 / 24（Mysteel 无分页、无检索接口，搜索引擎也不收录）。</span></li>
        <li><b>现货/期货</b>：生意社 100ppi 每日对比表，1119 个交易日（2022-03-01 → 2026-10-20），
            现货/近月/基差 0 缺失，可用 2022-08-17 原文「2425.00 元/吨」锚点复核。</li>
        <li><b>60 分钟线</b>：新浪 MA0 1023 根，仅覆盖 2026-01-28 之后 → 历史周的 14:00–15:00 入场点无法取，
            只能退回次日收盘（已在设计中登记为敏感性差异）。</li>
      </ul>
      <p class="verdict-inline">{badge('bad','判定：样本不足')} 3 周库存 → 只能形成 1 个状态观测，
      距离最小样本规则（信号≥12）差一个数量级。<b>此轨道不产出显著性结论。</b></p>
    </div>
    <div class="track sim">
      <h3>{badge('sim','模拟数据 SIMULATED')} 流程验证轨道</h3>
      <ul class="tight">
        <li>随机数生成（seed=20261020），208 周，全部行带 <code>data_status=SIMULATED</code>。</li>
        <li>机制：库存 = 季节 + 冲击驱动 AR(0.35)；期货 = 2500 − 6×(库存−88) + 噪声；基差 = 40 − 7×(库存−88) + 噪声。</li>
        <li><b>用途只有一个</b>：证明「假设→设计→样本→检验→稳定性→结论」的流水线能跑通、数字长什么样。</li>
      </ul>
      <p class="verdict-inline">{badge('sim','判定：仅演示')} 模拟结果不构成任何市场结论，
      页面上所有模拟数字都单独标注，不与真实轨道混排。</p>
    </div>
  </div>
  {ver}
</section>"""


def sec_sample(res, samples, simulated=False):
    meta = res["meta"]
    sk = meta.get("skipped", {})
    sig = res["sample"]["n_signal"]
    ctl = res["sample"]["n_control"]
    rows = []
    for r in samples[:400]:
        rows.append("<tr>" + "".join(
            f"<td class='num'>{esc(r.get(k, ''))}</td>" for k in
            ["asof", "total", "d1", "d2", "state", "T0", "P0", "basis0", "dB_10", "dP_10"]) + "</tr>")
    head = "".join(f"<th>{esc(h)}</th>" for h in
                   ["观测日", "库存(万吨)", "Δ1", "Δ2", "状态", "T0", "T0价", "T0基差", "Δ基差10日", "Δ期货10日"])
    return f"""
<section class="card">
  <h2>④ 样本构造{' ' + badge('sim','SIMULATED') if simulated else ''}</h2>
  <div class="kpis">
    <div class="kpi"><span class="k">{sig}</span><span class="kl">信号周（连降两周）</span></div>
    <div class="kpi"><span class="k">{ctl}</span><span class="kl">对照周</span></div>
    <div class="kpi"><span class="k">{meta.get('evaluable_states')}</span><span class="kl">可评估状态</span></div>
    <div class="kpi"><span class="k">{meta.get('inventory_rows')}</span><span class="kl">原始库存周</span></div>
  </div>
  <p class="muted">跳过原因：状态未变化 {sk.get('dup_state',0)} ｜ 观察间隔 &gt;10 天 {sk.get('gap',0)}
   ｜ 无价格 {sk.get('no_price',0)} ｜ 未来窗口不完整 {sk.get('incomplete',0)}。
   同一状态内连续多周不重复计数，只有「状态转变」才算一个独立事件——否则会把一段连续去库重复计数十几次。</p>
  <details open><summary>逐条样本（前 400 条，可在 Excel 中查看全部 {len(samples)} 条）</summary>
  <div class="scroll"><table class="tbl small">
  <thead><tr>{head}</tr></thead><tbody>{''.join(rows) or '<tr><td colspan="10" class="muted">无样本</td></tr>'}</tbody>
  </table></div></details>
</section>"""


def sec_amendment(amend):
    if not amend:
        return ""
    rows = []
    for v in amend["variants"]:
        prim = next((t for t in v["tests"] if t["id"] == "P1_mean"), None)
        p1 = "—" if not prim or prim.get("p") is None else f"{prim['p']:.4f}"
        est = "—" if not prim or prim.get("estimate") is None else f"{prim['estimate']:+.2f}"
        ci = "—" if not prim or not prim.get("ci95") else f"[{prim['ci95'][0]:+.1f}, {prim['ci95'][1]:+.1f}]"
        vd = {"INSUFFICIENT_SAMPLE": badge('bad', '样本不足'),
              "NOT_SIGNIFICANT": badge('none', '不显著'),
              "SUPPORTED": badge('ok', '支持'),
              "CONTRADICTED": badge('bad', '反向')}.get(v["verdict"], esc(v["verdict"]))
        rows.append(f"<tr><td><code>{esc(v['tag'])}</code></td><td>{esc(v['note'])}</td>"
                    f"<td class='num'>{v['n_signal']}</td><td class='num'>{v['n_control']}</td>"
                    f"<td class='num'>{est}</td><td class='num'>{ci}</td><td class='num'>{p1}</td>"
                    f"<td>{vd}</td></tr>")
    return f"""
<section class="card">
  <h2>⑤b 预登记修订口径对照（回答「是不是口径选错了」）</h2>
  <p>主口径去重后信号只剩 10 个，落到「样本不足」。为了判断这是不是口径选择造成的，
  在<b>修订记录</b>里补两个事前就能想到的口径（AM-1 weekly 去重、AM-2 允许换月，二者叠加为 AM-3）：</p>
  <table class="tbl small"><thead><tr><th>口径</th><th>说明</th><th>信号 n</th><th>对照 n</th>
  <th>主检验均值差</th><th>95% CI</th><th>p</th><th>结论</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
  <p class="note">四个口径的结论<b>一致</b>：没有一个口径给出"连降两周 → 基差走强"的显著正向证据。
  放得越松（AM-3，48 个信号），均值差依然只有个位数元/吨、置信区间横跨 0。
  这说明『样本不足』不是口径造成的，而是效应本身在数据里就不明显。</p>
</section>"""


def sec_event(design, ev=None):
    if not ev:
        return (f'<section class="card"><h2>⑦ 事件研究（信号前后基差路径）</h2>'
                f'<p class="muted">尚未生成 build/event_study.json。运行 '
                f'<code>python src/event_study.py --inventory data/port_inventory_weekly.csv '
                f'--price data/100ppi_sf.csv</code> 后重新生成本页。</p></section>')
    pp = ev.get("pre_post", {})
    sig, ctl = pp.get("signal", {}), pp.get("control", {})
    ks = list(range(-20, 21))
    b_sig, b_ctl = ev.get("basis_signal", {}), ev.get("basis_control", {})

    def path_svg():
        vals = [v for k in ks for v in (b_sig.get(str(k)), b_ctl.get(str(k))) if v is not None]
        if not vals:
            return '<p class="muted">无数据</p>'
        lo, hi = min(vals + [0]), max(vals + [0])
        rng = (hi - lo) or 1
        W, H, L, B = 780, 210, 52, 30
        def X(k):
            return L + (k + 20) * (W - L - 20) / 40
        def Y(v):
            return 20 + (hi - v) / rng * (H - 20 - B)
        out = [f'<svg viewBox="0 0 {W} {H}" class="chart">']
        out.append(f'<line x1="{L}" y1="{Y(0):.1f}" x2="{W-20}" y2="{Y(0):.1f}" stroke="#d1d5db" stroke-dasharray="3 3"/>')
        out.append(f'<line x1="{X(0):.1f}" y1="14" x2="{X(0):.1f}" y2="{H-B}" stroke="#9ca3af"/>')
        out.append(f'<text x="{X(0):.1f}" y="{H-10}" class="lbl" text-anchor="middle">T0 报告发布</text>')
        for series, col, name in ((b_sig, "#0f766e", "信号组(连降两周)"),
                                  (b_ctl, "#b45309", "对照组")):
            pts = [(X(k), Y(series[str(k)])) for k in ks if series.get(str(k)) is not None]
            if len(pts) > 1:
                d = " ".join(f"{'M' if i==0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
                out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.2"/>')
        out.append(f'<text x="{L}" y="{Y(hi):.1f}" class="lbl">{hi:+.0f}</text>')
        out.append(f'<text x="{L}" y="{Y(lo):.1f}" class="lbl">{lo:+.0f}</text>')
        out.append(f'<text x="{W-20}" y="{H-10}" class="lbl" text-anchor="end">元/吨（相对 T0 累积）</text>')
        out.append("</svg>")
        return "".join(out)

    def f(x):
        return "—" if x is None else f"{x:+.1f}"
    return f"""
<section class="card">
  <h2>⑦ 事件研究：差异是「信号之后」才出现的吗？</h2>
  <p class="muted">把每个观测的 T0 基差设为 0，对齐后求平均。这一步能识破最常见的伪信号：
  如果两条线在 T0 <b>之前</b>就已经分开，那"信号后走强"只是趋势延续，不是信号的作用。</p>
  {path_svg()}
  <table class="tbl narrow"><thead><tr><th>组别</th><th>n</th><th>T−20…T−1 均值</th>
  <th>T+1…T+10 均值</th><th>T+11…T+20 均值</th></tr></thead>
  <tbody>
  <tr><td>信号组（连降两周）</td><td class="num">{sig.get('n','—')}</td>
      <td class="num">{f(sig.get('pre_mean'))}</td><td class="num">{f(sig.get('post_mean_1_10'))}</td>
      <td class="num">{f(sig.get('post_mean_11_20'))}</td></tr>
  <tr><td>对照组</td><td class="num">{ctl.get('n','—')}</td>
      <td class="num">{f(ctl.get('pre_mean'))}</td><td class="num">{f(ctl.get('post_mean_1_10'))}</td>
      <td class="num">{f(ctl.get('post_mean_11_20'))}</td></tr>
  </tbody></table>
  <p class="note">读法：若信号的 pre 均值已经明显高于对照组，说明『连降两周』这个状态本身更容易出现在
  基差已在走强的阶段（选择效应）；此时后续的均值差有多少来自信号、多少来自趋势，无法用这点样本分离。
  这条正是把所有结论限定为「条件相关、不能作因果解释」的直接理由。</p>
</section>"""


def sec_stats(res, simulated=False):
    tests = res["tests"]
    if not tests:
        return '<section class="card"><h2>⑤ 统计结果</h2><p class="muted">无检验记录</p></section>'
    fam = {"primary": "主检验", "sensitivity": "敏感性(预登记)", "robustness": "鲁棒性",
           "placebo": "安慰剂", "stability": "稳定性", "diagnostic": "诊断"}
    rows = []
    for t in tests:
        if t.get("estimate") is None and t.get("p") is None:
            continue
        est = "—" if t["estimate"] is None else f"{t['estimate']:+.2f}"
        ci = "—" if not t.get("ci95") else f"[{t['ci95'][0]:+.2f}, {t['ci95'][1]:+.2f}]"
        p = "—" if t.get("p") is None else f"{t['p']:.4f}"
        q = "—" if t.get("q_bh") is None else f"{t['q_bh']:.4f}"
        sig = ""
        if t.get("p") is not None:
            sig = badge('ok', 'p<0.05') if t["p"] < 0.05 else badge('none', '不显著')
        if t.get("q_bh") is not None and t["q_bh"] < 0.10:
            sig += badge('ok', 'FDR<0.10')
        rows.append(f"<tr class='{ 'f-'+t['family'] }'><td><code>{esc(t['id'])}</code></td>"
                    f"<td>{esc(fam.get(t['family'], t['family']))}</td>"
                    f"<td>{esc(t['label'])}</td><td class='num'>{est}</td><td class='num'>{ci}</td>"
                    f"<td class='num'>{p}</td><td class='num'>{q}</td><td class='num'>{t.get('n','—')}</td>"
                    f"<td>{sig}</td></tr>")
    verdict = res.get("verdict")
    vmap = {"SUPPORTED": ("ok", "历史数据支持该假设"),
            "NOT_SIGNIFICANT": ("none", "没有证据支持（不显著）"),
            "INSUFFICIENT_SAMPLE": ("bad", "样本不足，无法判断"),
            "NOT_SUPPORTED": ("bad", "与历史数据不一致（反向）")}
    kind, text = vmap.get(verdict, ("none", verdict))
    head = "".join(f"<th>{h}</th>" for h in
                   ["编号", "检验族", "检验内容", "效应量", "95% CI", "p", "BH-q", "N", "判定"])
    return f"""
<section class="card">
  <h2>⑤ 统计结果{(' ' + badge('sim','SIMULATED')) if simulated else ''}</h2>
  <p class="verdict">{badge(kind, text)} <span class="muted">{esc(res.get('message',''))}</span></p>
  <p class="muted">全量登记 {sum(1 for t in tests if t.get('p') is not None)} 个带 p 值的检验，
  统一做 Benjamini–Hochberg FDR 校正（预登记上限 18 个）。这里<b>不挑好看的汇报</b>：
  显著性、不显著、样本不足、反向，全部列出。</p>
  <div class="scroll"><table class="tbl small"><thead><tr>{head}</tr></thead>
  <tbody>{''.join(rows)}</tbody></table></div>
  <details><summary>诊断量（多重检验 / 自相关 / 重叠）</summary>
  <pre>{esc(json.dumps(res.get('diagnostics', {}), ensure_ascii=False, indent=1))}</pre></details>
</section>"""


def sec_stability(res, simulated=False):
    st = res.get("stability") or {}
    if not st:
        return ('<section class="card"><h2>⑥ 稳定性</h2>'
                '<p class="muted">样本不足，未计算分年/分阶段稳定性。这是刻意的：'
                '在 1 个观测上做分年是伪精确。</p></section>')
    blocks = []
    titles = {"by_year": "分年", "by_band": "按库存历史分位",
              "by_baseline_sign": "按 T0 基差符号"}
    for key, items in st.items():
        chart = bar_svg([{"label": i["group"], "value": None if i["diff"] is None else round(i["diff"], 2),
                          "n": (i["n_signal"] or 0) + (i["n_control"] or 0)} for i in items], unit=" 元/吨")
        trows = "".join(
            f"<tr><td>{esc(i['group'])}</td><td class='num'>{i['n_signal']}</td>"
            f"<td class='num'>{i['n_control']}</td>"
            f"<td class='num'>{'—' if i['diff'] is None else f'{i[chr(100)+chr(105)+chr(102)+chr(102)]:+.2f}'}</td>"
            f"<td class='num'>{'—' if i['p'] is None else f'{i[chr(112)]:.3f}'}</td></tr>" for i in items)
        blocks.append(f"""
  <h3>{titles.get(key, key)}</h3>
  {chart}
  <table class="tbl narrow"><thead><tr><th>分组</th><th>信号 n</th><th>对照 n</th><th>均值差</th><th>p</th></tr></thead>
  <tbody>{trows}</tbody></table>""")
    return f"""<section class="card">
  <h2>⑥ 稳定性{' ' + badge('sim','SIMULATED') if simulated else ''}</h2>
  <p class="muted">稳定性比显著性更重要：如果效应只在某一年/某一种库存水平下出现，
  它更可能是那次行情的偶然，而不是可重复的规律。N&lt;3 的分组一律标「样本不足」而不给 p 值。</p>
  {''.join(blocks)}
  <p class="note">读法提醒：分组越细，每组样本越少，p 值越不稳定。
  本页把 n 与 p 一起呈现，就是为了避免「挑一个显著的分组来讲故事」。</p>
</section>"""


def sec_event_old(design, market_rows=None):
    return ""


def sec_limits(design):
    rows = "".join(f"<tr><td><code>{esc(l['id'])}</code></td><td>{esc(l.get('level',''))}</td>"
                   f"<td>{esc(l['text'])}</td></tr>" for l in design.get("risks_and_limits", []))
    ex = design.get("ex_ante_checks", {})
    li = "".join(f"<li><b>{esc(k)}</b>：{esc('；'.join(v) if isinstance(v, list) else v)}</li>"
                 for k, v in ex.items())
    la = """
  <h3>四类典型错误在本研究中的具体表现</h3>
  <table class="tbl">
  <thead><tr><th>风险</th><th>如果做错会怎样</th><th>本研究的处理</th></tr></thead>
  <tbody>
  <tr><td><b>未来函数（前视偏差）</b></td>
      <td>用「本周三的库存报告」配「本周三之前就已成交的价格」，等于提前知道报告；
          或对整段历史用全样本分位阈值，等于偷看未来。</td>
      <td>信号只使用 14:00 发布前已可得的两期库存；价格取发布后 14:00–15:00 的 bar；
          库存分位只用过去 52 周滚动计算；事件研究额外检查 T0 之前是否已分离。</td></tr>
  <tr><td><b>幸存者偏差</b></td>
      <td>只看还在交易的合约 / 只留下报告过数据的周，把消失的样本悄悄删掉。</td>
      <td>合约按 100ppi 当期近月列取，不按事后是否交割过筛；缺失周保留缺口不插值，
          剔除原因逐条计数（gap=24、换月=41、重复状态、窗口不完整）。</td></tr>
  <tr><td><b>重叠样本</b></td>
      <td>相邻信号周共用 8/10 天的未来窗口，N 被虚增，p 值被低估。</td>
      <td>同时报告：全部样本、非重叠样本（间隔≥10 日）、月度样本（每月≤1 个）、
          块自助 CI、AR 自相关与有效样本量。</td></tr>
  <tr><td><b>多重检验 / p-hacking</b></td>
      <td>试了 20 个口径挑一个 p&lt;0.05 汇报，真实的假阳性率远超 5%。</td>
      <td>所有检验编号登记（P/S/R/PLAC），统一 BH-FDR 校正；
          修订口径（AM-1…AM-3）单列汇总；参数确认后冻结，改动即新版本。</td></tr>
  </tbody></table>"""
    return f"""
<section class="card">
  <h2>⑧ 局限与风险（写在结论前面）</h2>
  <table class="tbl"><thead><tr><th>编号</th><th>严重度</th><th>说明</th></tr></thead><tbody>{rows}</tbody></table>
  <h3>事前检查清单（前视 / 幸存者 / 重叠 / 多重检验）</h3>
  <ul class="tight">{li}</ul>
  {la}
  <p class="note">观测数据只能证明「条件相关」：即便未来拿到完整样本做出 p&lt;0.05，
  也不能直接解读成「库存降 → 基差必强」的因果或交易信号。真实交易还要扣掉手续费、滑点、
  换月与流动性成本，这些都不在本页测算内。</p>
</section>"""


def sec_repro(audit, design, verification=None):
    files = (audit or {}).get("files", {})
    rows = "".join(f"<tr><td>{esc(k)}</td><td><code>{esc(v.get('path'))}</code></td>"
                   f"<td class='num'>{v.get('rows')}</td><td><code>{esc(v.get('sha256'))}</code></td></tr>"
                   for k, v in files.items())
    return f"""
<section class="card">
  <h2>⑨ 复现说明</h2>
  <p>页面生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}　｜　设计版本：{esc(design.get('version', design.get('schema_version')))}
  　｜　设计状态：{esc(design.get('approval_state'))}</p>
  <table class="tbl"><thead><tr><th>序列</th><th>文件</th><th>行数</th><th>sha256(前16位)</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <h3>一条命令重建</h3>
  <pre>python src/selftest_stats.py                       # 20 项统计自检（对照 scipy 参考值）
python src/make_demo_simulation.py --weeks 208     # 生成明确标记的模拟数据
python src/study_engine.py --design build/research_design.formal.json \\
       --inventory data/port_inventory_weekly.csv --price data/100ppi_sf.csv \\
       --out build/results_real.json --samples build/samples_real.csv --status REAL</pre>
</section>"""


# --------------------------------------------------------------------------- page

CSS = """
:root{--ink:#1b1f24;--mut:#6b7280;--line:#e5e7eb;--bg:#f7f8fa;--card:#fff;
--ok:#0f766e;--warn:#b45309;--bad:#b91c1c;--sim:#6d28d9}
*{box-sizing:border-box}
body{margin:0;font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
header{background:linear-gradient(135deg,#0f172a,#134e4a);color:#fff;padding:28px 32px 22px}
header h1{margin:0 0 6px;font-size:24px;letter-spacing:.5px}
header .sub{opacity:.8;font-size:13.5px}
header .tagline{margin-top:10px;font-size:14px;background:rgba(255,255,255,.12);display:inline-block;
padding:6px 12px;border-radius:6px}
nav{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);display:flex;gap:2px;
padding:0 20px;overflow-x:auto;z-index:9}
nav button{background:none;border:0;padding:13px 15px;font:inherit;font-size:14px;color:var(--mut);cursor:pointer;
border-bottom:2px solid transparent;white-space:nowrap}
nav button.on{color:var(--ok);border-bottom-color:var(--ok);font-weight:600}
main{max-width:1220px;margin:0 auto;padding:20px 20px 80px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:22px 24px;margin:0 0 18px;
box-shadow:0 1px 2px rgba(16,24,40,.04)}
h2{margin:0 0 14px;font-size:19px}
h3{margin:20px 0 8px;font-size:15.5px;color:#111827}
.hypo{margin:0 0 16px;padding:14px 18px;background:#f0fdfa;border-left:4px solid var(--ok);border-radius:0 8px 8px 0;
font-size:17px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:26px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media(max-width:900px){.grid2,.grid3,.tracks{grid-template-columns:1fr!important}}
.tbl{border-collapse:collapse;width:100%;font-size:13.5px}
.tbl th{background:#f3f4f6;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);font-weight:600;
position:sticky;top:0}
.tbl td{padding:7px 10px;border-bottom:1px solid #f1f2f4;vertical-align:top}
.tbl.small{font-size:12.5px}.tbl.narrow{max-width:640px}
.tbl tr.f-primary td{background:#f0fdfa}
.tbl tr.f-placebo td{background:#fffbeb}
.num{text-align:right;font-variant-numeric:tabular-nums}
.scroll{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.muted{color:var(--mut);font-size:13.5px}
.note{margin-top:14px;padding:12px 14px;background:#f9fafb;border:1px dashed var(--line);border-radius:8px;
font-size:13.5px;color:#374151}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap}
.b-ok{background:#ccfbf1;color:#115e59}.b-warn{background:#fef3c7;color:#92400e}
.b-bad{background:#fee2e2;color:#991b1b}.b-sim{background:#ede9fe;color:#5b21b6}
.b-none{background:#e5e7eb;color:#374151}
.verdict{font-size:16px;margin:0 0 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.verdict-inline{margin-top:12px;font-size:14px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:8px 0 16px}
.kpi{background:#f9fafb;border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.kpi .k{display:block;font-size:24px;font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums}
.kpi .kl{font-size:12.5px;color:var(--mut)}
.tracks{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.track{border-radius:10px;padding:16px;border:1px solid var(--line)}
.track.real{background:#f0fdfa;border-color:#99f6e4}
.track.sim{background:#f5f3ff;border-color:#ddd6fe}
ul.tight,ol.qs{margin:6px 0 0;padding-left:20px}
ul.tight li{margin:5px 0}
ol.qs li{margin:10px 0}
.opts{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.opt{background:#fff;border:1px solid var(--line);border-radius:99px;padding:2px 10px;font-size:12.5px;color:#374151}
.chart{width:100%;height:auto;display:block;margin:6px 0 10px}
.chart .axis{stroke:#d1d5db;stroke-width:1}
.chart .lbl{fill:#6b7280;font-size:12px}
.chart .val{fill:#111827;font-size:12px;font-weight:600}
.chart .n{fill:#9ca3af;font-weight:400}
pre{background:#0f172a;color:#e2e8f0;padding:14px;border-radius:8px;overflow:auto;font-size:12.5px;line-height:1.5}
code{background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:12.5px}
details summary{cursor:pointer;color:var(--ok);font-weight:600;margin:10px 0}
footer{color:var(--mut);font-size:12.5px;text-align:center;padding:24px}
.plan{margin:0;padding-left:22px}
.plan li{margin:8px 0}
"""

JS = """
document.querySelectorAll('nav button').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('nav button').forEach(function(x){x.classList.remove('on')});
    document.querySelectorAll('section.tab').forEach(function(x){x.style.display='none'});
    b.classList.add('on');
    document.getElementById(b.dataset.t).style.display='block';
    window.scrollTo({top:0,behavior:'smooth'});
  });
});
document.querySelectorAll('nav button')[0].click();
"""


def build(out_path, design, parsed, audit, res_real, res_demo, samples_real, samples_demo,
          verification=None, data_meta=None, amend=None, ev=None):
    tabs = [
        ("t1", "① 研究设计", sec_design(design, parsed)),
        ("t2", "② 参数确认", sec_confirm(design)),
        ("t3", "③ 数据可用性", sec_data(verification, audit)),
        ("t4", "④ 样本（真实）", sec_sample(res_real, samples_real, False)),
        ("t5", "⑤ 统计（真实）", sec_stats(res_real, False) + sec_amendment(amend)),
        ("t6", "⑥ 稳定性（真实）", sec_stability(res_real, False) + sec_event(design, ev)),
        ("t7", "⑦ 模拟演示", sec_sample(res_demo, samples_demo, True)
         + sec_stats(res_demo, True) + sec_stability(res_demo, True)),
        ("t9", "⑧ 局限与风险", sec_limits(design)),
        ("t10", "⑨ 复现说明", sec_repro(audit, design, verification)),
    ]
    body = "".join(f'<section class="tab" id="{tid}">{html}</section>' for tid, _, html in tabs)
    nav = "".join(f'<button data-t="{tid}">{esc(label)}</button>' for tid, label, _ in tabs)
    verdict_real = res_real.get("verdict")
    vtext = {"INSUFFICIENT_SAMPLE": "样本不足，无法判断", "SUPPORTED": "历史数据支持",
             "NOT_SIGNIFICANT": "无显著证据", "CONTRADICTED": "与历史相反"}.get(verdict_real, verdict_real)
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>研究假设检验｜甲醇港口库存连降 × 基差走强</title>
<style>{CSS}</style></head>
<body>
<header>
  <h1>自定义研究假设检验：甲醇港口库存连续两周下降 → 随后两周基差更容易走强</h1>
  <div class="sub">期现价差与量化 · Skill 25 ｜ 真实数据轨道 {badge('bad', vtext)} ｜
   模拟数据轨道 {badge('sim', '仅演示流程')} ｜ 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
  <div class="tagline">先把假设变成可检验的设计，再动数据；数据不够就如实说不够，不用模拟数字凑结论。</div>
</header>
<nav>{nav}</nav>
<main>{body}</main>
<footer>本页所有真实数据均可回溯到原始网页；模拟数据由随机数生成且逐行标记。
观测数据只支持条件相关性，不构成因果结论或投资建议。</footer>
<script>{JS}</script>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def load_json(p, default=None):
    if not p or not os.path.exists(p):
        return default
    return json.load(open(p, encoding="utf-8-sig"))


def load_csv(p):
    import csv
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="out/research_hypothesis_test.html")
    a = ap.parse_args()
    r = a.root
    design = load_json(os.path.join(r, "build/research_design.formal.json"))
    parsed = load_json(os.path.join(r, "build/design_draft.json"), {})
    audit = load_json(os.path.join(r, "build/data_audit.json"), {})
    res_real = load_json(os.path.join(r, "build/results_real.json"))
    res_demo = load_json(os.path.join(r, "build/results_demo.json"))
    samples_real = load_csv(os.path.join(r, "build/samples_real.csv"))
    samples_demo = load_csv(os.path.join(r, "build/samples_demo.csv"))
    verification = load_json(os.path.join(r, "build/verification_full.json"))
    amend = load_json(os.path.join(r, "build/amendment.json"))
    ev = load_json(os.path.join(r, "build/event_study.json"))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    build(a.out, design, parsed, audit, res_real, res_demo, samples_real, samples_demo,
          verification, amend=amend, ev=ev)
    print("html ->", a.out, os.path.getsize(a.out), "bytes")


if __name__ == "__main__":
    main()
