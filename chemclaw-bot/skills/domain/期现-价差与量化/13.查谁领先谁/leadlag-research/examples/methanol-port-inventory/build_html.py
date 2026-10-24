# -*- coding: utf-8 -*-
"""build_html.py — 生成自包含交互式 HTML 研究报告"""
import json, os, math

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "result.json"), encoding="utf-8"))
S = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))
N = json.load(open(os.path.join(HERE, "narrative.json"), encoding="utf-8"))
rows = S["rows"]
M = R["meta"]

# 序列（展示单位）
def num(x):
    return None if x is None else float(x)

series = []
for i, r in enumerate(rows):
    series.append({
        "i": i, "d": r["stat"], "pub": r["pub"], "pub_hm": r["pub_hm"],
        "I": r["total"], "dI": num(r["dI"]), "dIp": num(r["dI_pct"]),
        "r": None if r["ret"] is None else r["ret"] * 100,
        "rs": None if r["ret_simple"] is None else r["ret_simple"] * 100,
        "ra": None if r["ret_avail"] is None else r["ret_avail"] * 100,
        "P_prev": r["P_prev"], "P_pub": r["P_pub"],
        "east": r["east_chg"], "south": r["south_chg"],
    })

# 主扫描（展示 r 与 p、q、n）
scan = R["main_scan"]
stage_scan = R["stage_scan"]
year_scan = R["year_scan"]
half_scan = R["half_scan"]
variants = R["variants"]
shift = R["shift_scan"]
rolling = R["rolling"]
reg = R["regressions"]
diag = R["diag"]

payload = {
    "meta": M, "series": series, "scan": scan, "stages": R["stages"], "stage_scan": stage_scan,
    "years": R["years"], "year_scan": year_scan, "half_scan": half_scan,
    "variants": {k: [{"lag": d["lag"], "r": d["r"], "p": d["p"], "q_bh": d["q_bh"], "n": d["n"]} for d in v] for k, v in variants.items()},
    "shift": {k: [{"lag": d["lag"], "r": d["r"], "p": d["p"], "n": d["n"]} for d in v] for k, v in shift.items()},
    "naive": [{"lag": d["lag"], "r": d["r"], "p": d["p"]} for d in R["naive_scan"]],
    "rolling": rolling, "reg": reg, "diag": diag, "narr": N, "matrix": R["matrix"],
    "pub_diag": R["pub_diag"], "mto": R["mto_series"],
}

HTML_HEAD = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>甲醇港口库存 × 期货收益 · 领先滞后关系研究</title>
<style>
:root{
  --bg:#0b1220; --panel:#111b2e; --panel2:#16233a; --line:#243552; --ink:#e8eef8; --mut:#8fa3c0;
  --acc:#4fd1c5; --acc2:#7aa2ff; --neg:#ff6b81; --pos:#3ddc97; --warn:#ffb454; --grid:#1c2b44;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:linear-gradient(180deg,#08101c 0%,#0b1220 40%,#0a1626 100%);color:var(--ink);
  font-family:"Segoe UI","Microsoft YaHei","PingFang SC",system-ui,sans-serif;font-size:14px;line-height:1.65}
a{color:var(--acc2);text-decoration:none}
.wrap{max-width:1280px;margin:0 auto;padding:28px 22px 80px}
header.hero{padding:34px 26px 26px;border-radius:18px;background:
  radial-gradient(1200px 260px at 10% -10%,rgba(79,209,197,.18),transparent 60%),
  radial-gradient(900px 300px at 95% 0%,rgba(122,162,255,.18),transparent 60%),
  linear-gradient(160deg,#13233c,#0d1728);border:1px solid var(--line);position:relative;overflow:hidden}
header.hero:after{content:"";position:absolute;inset:0;background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);
  background-size:44px 44px;opacity:.25;pointer-events:none}
h1{font-size:27px;line-height:1.35;margin:0 0 6px;letter-spacing:.3px}
.sub{color:var(--mut);font-size:14px}
.verdict{margin-top:18px;display:flex;gap:14px;align-items:flex-start;padding:16px 18px;border-radius:14px;
  background:linear-gradient(90deg,rgba(255,180,84,.14),rgba(255,180,84,.03));border:1px solid rgba(255,180,84,.45)}
.verdict .badge{flex:0 0 auto;padding:4px 10px;border-radius:999px;background:rgba(255,180,84,.2);color:var(--warn);
  font-weight:700;font-size:12px;border:1px solid rgba(255,180,84,.5);white-space:nowrap}
.verdict .vtext b{color:#ffd39b}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-top:18px}
.kpi{background:rgba(255,255,255,.03);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpi .k{color:var(--mut);font-size:12px}
.kpi .v{font-size:21px;font-weight:700;letter-spacing:.4px;margin-top:2px}
.kpi .n{color:var(--mut);font-size:11px}
section{margin-top:26px}
.card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);border-radius:16px;padding:18px 20px}
h2{font-size:18px;margin:0 0 4px;display:flex;align-items:center;gap:10px}
h2 .idx{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,var(--acc),var(--acc2));color:#06111f;
  font-size:13px;font-weight:800;display:inline-flex;align-items:center;justify-content:center}
h3{font-size:14px;margin:16px 0 8px;color:#cddcf3}
p{margin:8px 0;color:#cfdcef}
.mut{color:var(--mut)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media(max-width:900px){.grid2,.grid3{grid-template-columns:1fr}}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;border:1px solid var(--line);color:var(--mut);margin-right:6px}
.tag.pos{color:var(--pos);border-color:rgba(61,220,151,.4)}
.tag.neg{color:var(--neg);border-color:rgba(255,107,129,.4)}
.tag.warn{color:var(--warn);border-color:rgba(255,180,84,.45)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}
th{color:var(--mut);font-weight:600;position:sticky;top:0;background:var(--panel)}
tbody tr:hover{background:rgba(122,162,255,.07);cursor:pointer}
tr.sel{background:rgba(79,209,197,.14)!important}
.scroll{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:12px}
.ctrl{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0 6px}
button,.btn{background:#16233a;color:var(--ink);border:1px solid var(--line);border-radius:9px;padding:6px 12px;font-size:12.5px;cursor:pointer}
button:hover,.btn:hover{border-color:var(--acc2);color:#fff}
button.on{background:linear-gradient(135deg,rgba(79,209,197,.25),rgba(122,162,255,.25));border-color:var(--acc)}
select,input[type=range]{background:#0f1a2c;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:5px 8px;font-size:12.5px}
.chart{width:100%;height:auto;display:block}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--mut);margin-top:6px}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
.note{font-size:12px;color:var(--mut);border-left:2px solid var(--line);padding-left:10px;margin-top:10px}
.pill{font-size:11.5px;padding:2px 9px;border-radius:999px;display:inline-block}
.ok{background:rgba(61,220,151,.15);color:var(--pos)}
.no{background:rgba(255,107,129,.15);color:var(--neg)}
.mid{background:rgba(255,180,84,.15);color:var(--warn)}
.find{border:1px solid var(--line);border-radius:14px;padding:14px 16px;background:rgba(255,255,255,.02)}
.find .h{display:flex;gap:10px;align-items:baseline}
.find .n{font-weight:800;color:var(--acc);font-size:13px}
.find b{color:#fff}
.tip{background:rgba(122,162,255,.08);border:1px solid rgba(122,162,255,.3);border-radius:12px;padding:10px 14px;font-size:12.5px;color:#cfdcef}
.footer{margin-top:36px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
.kbd{font-family:Consolas,monospace;background:#0f1a2c;border:1px solid var(--line);border-radius:5px;padding:0 5px;font-size:11.5px}
svg text{font-family:"Segoe UI","Microsoft YaHei",sans-serif}
</style>
</head>
<body><div class="wrap">
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def fmt(x, d=3):
    if x is None:
        return "—"
    return ("%." + str(d) + "f") % x


def pfmt(p):
    if p is None:
        return "—"
    if p < 0.001:
        return "<0.001"
    return "%.3f" % p


def sig_class(p):
    if p is None:
        return ""
    if p < 0.01:
        return "ok"
    if p < 0.05:
        return "mid"
    return "no"


parts = [HTML_HEAD]

# ---------------- HERO ----------------
best_p = min([d["p"] for d in scan if d["p"] is not None])
min_q = min([d["q_bh"] for d in scan if d["q_bh"] is not None])
lag0 = [d for d in scan if d["lag"] == 0][0]
best = sorted([d for d in scan if d["r"] is not None], key=lambda d: -abs(d["r"]))[0]
parts.append(f"""
<header class="hero">
  <div class="sub">期现与量化研究 · 场景 13「查谁领先谁」· 案例：甲醇港口库存 vs 甲醇期货</div>
  <h1>{esc(N['title'])}</h1>
  <div class="sub">{esc(N['subtitle'])}</div>
  <div class="verdict">
    <div class="badge">结论</div>
    <div class="vtext"><b>{esc(N['verdict_short'])}</b><br>{esc(N['verdict_detail'])}</div>
  </div>
  <div class="kpis">
    <div class="kpi"><div class="k">样本区间</div><div class="v">{M['start']} → {M['end']}</div><div class="n">101 个周度观测 · 发布日期精确到分钟</div></div>
    <div class="kpi"><div class="k">检验 Lag 数</div><div class="v">25</div><div class="n">Lag ∈ [−12, +12]，全部报告</div></div>
    <div class="kpi"><div class="k">最小未校正 p</div><div class="v">{pfmt(best_p)}</div><div class="n">Lag = {best['lag']:+d} 周</div></div>
    <div class="kpi"><div class="k">FDR 校正后最小 q</div><div class="v" style="color:var(--neg)">{fmt(min_q)}</div><div class="n">远高于 0.05，无可声称的领先</div></div>
    <div class="kpi"><div class="k">同期相关 r (Lag 0)</div><div class="v">{fmt(lag0['r'])}</div><div class="n">n = {lag0['n']} · p = {pfmt(lag0['p'])}</div></div>
    <div class="kpi"><div class="k">最大 |r| 所在 Lag</div><div class="v">{best['lag']:+d} 周 · {fmt(best['r'])}</div><div class="n">FDR q = {fmt(best.get('q_bh'))}（不显著）</div></div>
  </div>
</header>
""")

# ---------------- 1 指标定义 ----------------
parts.append(f"""
<section class="card">
  <h2><span class="idx">1</span>指标定义、频率、覆盖与真实发布日期</h2>
  <p class="mut">领先滞后研究里最容易出错的一步不是统计，而是“当时能不能看到”。本节把两个指标的统计口径与<b style="color:#fff">信息可得时点</b>逐项钉死。</p>
  <div class="grid2">
    <div class="find">
      <div class="h"><span class="n">A</span><b>中国甲醇样本港口库存（周度 · 万吨）</b></div>
      <table>
        <tr><td>定义</td><td>华东 + 华南样本港口甲醇库存总量（隆众资讯「中国甲醇样本港口库存周数据统计」）</td></tr>
        <tr><td>统计频率</td><td>周度，统计日为周三（节假日顺延至最近工作日）</td></tr>
        <tr><td>覆盖范围</td><td>{M['start']} 至 {M['end']}，共 {M['n']} 期，期内无缺失周</td></tr>
        <tr><td>报告期</td><td>截至统计日当日（即统计期最后一天）的时点库存</td></tr>
        <tr><td>实际发布日期</td><td><b style="color:var(--acc)">统计日当天 13:00–15:00</b>（{R['pub_diag']['hour_dist'].get('14', 0)}/{M['n']} 期在 14:00 前后）</td></tr>
        <tr><td>可得性含义</td><td>报告期结束的当天下午盘中即可见，<b>统计日 = 发布日</b>，无需滞后 1 期保守处理</td></tr>
      </table>
    </div>
    <div class="find">
      <div class="h"><span class="n">B</span><b>甲醇期货周度收益率（郑商所 MA 主连 · %）</b></div>
      <table>
        <tr><td>定义</td><td>MA 主连收盘价的对数收益率，以库存披露日为锚点对齐</td></tr>
        <tr><td>交易时段</td><td>日盘 9:00–11:30 / 13:30–15:00；夜盘 21:00–23:30</td></tr>
        <tr><td>价格锚点</td><td><b>披露前</b>：统计日 11:30 定格收盘（当日开盘后可交易，尚未见库存）；<b>披露后</b>：当日 15:00 收盘</td></tr>
        <tr><td>主设定收益</td><td>r<sub>t</sub> = ln(P<sub>披露日15:00</sub> / P<sub>前一日收盘</sub>) × 100，即“披露当日的价格反应”</td></tr>
        <tr><td>覆盖范围</td><td>期货日线 2014-12-24 至 2026-10-19（与本样本交集为研究样本）</td></tr>
        <tr><td>频率统一</td><td>期货日线 → 按库存披露日抽样聚合为周度，<b>不做前向填充</b></td></tr>
      </table>
    </div>
  </div>
  <div class="note">为什么必须用真实发布日：库存、开工等周度指标如果直接把“统计期结束日”当作公布时间，会产生<b>长达 0–7 天的信息泄漏</b>——相当于让研究者提前知道尚未公开的数据，进而系统性夸大领先关系。本报告的时间轴全部取自数据源页面的“发布时间”字段（精确到秒），并逐条校验“统计日 = 发布日”。</div>
</section>
""")

# ---------------- 2 变换 ----------------
tr_rows = "".join(f"<tr><td>{esc(t['name'])}</td><td style='text-align:left'>{esc(t['desc'])}</td><td>{esc(t['used'])}</td></tr>" for t in N["transform_notes"])
parts.append(f"""
<section class="card">
  <h2><span class="idx">2</span>数据变换的选择与理由</h2>
  <p>库存与价格都是 I(1) 非平稳序列（后文 ADF 检验：库存水平 t = {fmt(diag['adf_inv_t'],2)}，价格 t = {fmt(diag['adf_px_t'],2)}，均无法拒绝单位根）。因此主检验使用<b>差分后的库存变化</b>与<b>收益率</b>，而非水平值。两种变换都做了稳健性对照。</p>
  <table><thead><tr><th>变换</th><th style="text-align:left">定义</th><th>用途</th></tr></thead><tbody>{tr_rows}</tbody></table>
</section>
""")

# ---------------- 3 Lag 主曲线 ----------------
parts.append("""
<section class="card">
  <h2><span class="idx">3</span>完整 Lag 相关性曲线（±12 周，全部 25 个点）</h2>
  <p class="mut">点击曲线或下方表格中的任意 Lag，可查看该设定下的数据对齐方式、散点图、滚动相关性与逐年结果。<b style="color:#fff">本节报告全部 Lag，不只报告最大值。</b></p>
  <div class="ctrl">
    <span class="mut">展示：</span>
    <button class="on" data-view="r">相关系数 r</button>
    <button data-view="p">p 值 −log10</button>
    <button data-view="q">FDR 校正 q 值 −log10</button>
    <button data-view="n">有效样本量 n</button>
  </div>
  <svg id="lagchart" class="chart" viewBox="0 0 1160 400" preserveAspectRatio="xMidYMid meet"></svg>
  <div class="legend">
    <span><i style="background:var(--acc)"></i>r 随 Lag 变化</span>
    <span><i style="background:rgba(122,162,255,.5);height:8px"></i>95% 置信带（Fisher-z，按有效样本量）</span>
    <span><i style="background:var(--warn)"></i>未校正 5% 显著</span>
    <span><i style="background:var(--neg)"></i>FDR 校正后仍显著</span>
  </div>
  <div class="note">Lag 符号约定：<b style="color:#fff">Lag = +k 表示库存变化领先期货收益 k 周</b>；Lag = −k 表示期货收益领先库存变化 k 周。Lag 0 为同期（统计周收益）。</div>
  <div class="scroll" style="margin-top:12px">
    <table id="lagtable"><thead><tr><th>Lag（周）</th><th>n</th><th>r</th><th>95% CI</th><th>p（朴素）</th><th>t（NW）</th><th>p（NW）</th><th>q FDR</th><th>q Bonferroni</th><th>n_eff</th></tr></thead><tbody></tbody></table>
  </div>
</section>
""")

# ---------------- 4 领先滞后矩阵 ----------------
parts.append("""
<section class="card">
  <h2><span class="idx">4</span>领先滞后矩阵（A→B 与 B→A 对称检验）</h2>
  <p class="mut">矩阵按“谁领先”把 25 个 Lag 分成左右两半：<b>虚线左侧</b>检验“期货收益 → 库存”（B 领先，Lag 为负），<b>虚线右侧</b>检验“库存 → 期货收益”（A 领先，Lag 为正）。每个 Lag 一格：上方色块内为相关系数 r 及其 FDR 校正 q 值（显示为 q+数值），色深表示 |r|，青绿为正、品红为负；下方为该格的有效样本量 n。若某一方向存在真实领先关系，应在相邻多个 Lag 上形成同色“山脊”，而不是孤立的单点。</p>
  <svg id="matrix" class="chart" viewBox="0 0 1160 250" preserveAspectRatio="xMidYMid meet"></svg>
</section>
""")

# ---------------- 5 明细查看器 ----------------
parts.append("""
<section class="card" id="detail">
  <h2><span class="idx">5</span>Lag 明细：对齐方式 · 散点 · 滚动 · 逐年</h2>
  <div class="ctrl">
    <span class="mut">当前 Lag：</span>
    <select id="lagsel"></select>
    <span class="mut" id="lagdesc"></span>
  </div>
  <div class="grid2" style="margin-top:6px">
    <div>
      <h3>① 该 Lag 下的时间对齐（前 14 个配对）</h3>
      <div class="scroll" style="max-height:300px">
        <table id="aligntable"><thead><tr><th>库存统计日</th><th>库存发布</th><th>ΔI (万吨)</th><th>期货收益日</th><th>r (%)</th></tr></thead><tbody></tbody></table>
      </div>
    </div>
    <div>
      <h3>② 散点与拟合线</h3>
      <svg id="scatter" class="chart" viewBox="0 0 560 320" preserveAspectRatio="xMidYMid meet"></svg>
      <div class="mut" id="scatstat" style="font-size:12px"></div>
    </div>
  </div>
  <h3>③ 26 周滚动相关系数（虚线为 ±95% 近似显著带）</h3>
  <svg id="rollchart" class="chart" viewBox="0 0 1160 260" preserveAspectRatio="xMidYMid meet"></svg>
  <div class="legend"><span><i style="background:var(--acc2)"></i>滚动 r（窗口 26 周）</span><span><i style="background:rgba(255,180,84,.8);height:8px"></i>±0.39 近似显著阈值（n=26）</span></div>
  <h3>④ 逐年与分阶段结果（同一 Lag）</h3>
  <div class="grid2">
    <div><div class="scroll" style="max-height:240px"><table id="yeartable"><thead><tr><th>年度</th><th>n</th><th>r</th><th>p</th><th>q FDR</th></tr></thead><tbody></tbody></table></div></div>
    <div><div class="scroll" style="max-height:240px"><table id="stagetable"><thead><tr><th>阶段</th><th>n</th><th>r</th><th>p</th><th>q FDR</th></tr></thead><tbody></tbody></table></div></div>
  </div>
  <div class="note" id="lagjudge"></div>
</section>
""")

# ---------------- 6 分阶段稳定性 ----------------
parts.append("""
<section class="card">
  <h2><span class="idx">6</span>分年度 / 分市场阶段的稳定性检验</h2>
  <p class="mut">把一个稳定的领先关系应当具备的性质作为检验标准：<b>不同时期的“最优 Lag”位置相近、符号一致、且在多重检验后仍显著</b>。下表逐项对照。</p>
  <div class="grid2">
    <div><h3>各年度最强 Lag</h3><div class="scroll"><table id="ysummary"></table></div></div>
    <div><h3>各市场阶段最强 Lag</h3><div class="scroll"><table id="ssummary"></table></div></div>
  </div>
  <h3>阶段定义依据（按价格路径与库存路径客观切分，可复核）</h3>
  <div class="scroll"><table id="stagelist"></table></div>
  <h3>同一 Lag 在不同阶段的相关性热力图（行：Lag，列：阶段/年度）</h3>
  <svg id="heat" class="chart" viewBox="0 0 1160 560" preserveAspectRatio="xMidYMid meet"></svg>
  <div class="note">热力图应出现“竖条纹”（同一 Lag 在所有时期都显著）才说明领先关系稳定。本图显示的是随机斑块——最优位置在时期之间漂移。</div>
</section>
""")

# ---------------- 7 稳健性与安慰剂 ----------------
parts.append("""
<section class="card">
  <h2><span class="idx">7</span>稳健性：变换方式与“伪造时点”安慰剂检验</h2>
  <p class="mut">同一组关系在多种变换下不应改变结论；同时把库存的可得时点人为提前（时间上不可能），若“领先关系”依然出现，则说明它是噪声或方法伪影，而非可交易的信息优势。</p>
  <div class="ctrl">
    <button class="on" data-variant="D1_主设定_Δ库存(万吨)×披露日对数收益">D1 主设定</button>
    <button data-variant="D2_Δ库存百分比×披露日收益">D2 Δ库存%</button>
    <button data-variant="D3_Δ库存(万吨)×可用周收益">D3 可用周收益</button>
    <button data-variant="D4_库存水平×价格水平(伪回归对照)">D4 水平×水平（伪回归）</button>
    <button data-variant="D5_库存水平×披露日收益">D5 水平×收益</button>
    <button data-variant="D6_Δ库存浮动比例×披露日收益">D6 浮动比例</button>
  </div>
  <svg id="varchart" class="chart" viewBox="0 0 1160 300" preserveAspectRatio="xMidYMid meet"></svg>
  <h3>伪造时点安慰剂：把库存可得时点前移/后移</h3>
  <div class="scroll"><table id="shifttable"></table></div>
  <div class="note">Shift = −1 / −2 表示“提前 1–2 周就知道库存”（现实中不可能发生）。若在提前获得的时点下仍观察到同量级的相关性峰值，则真实时点下的峰值同样只是噪声。</div>
</section>
""")

# ---------------- 8 多重检验 & 样本量 ----------------
parts.append(f"""
<section class="card">
  <h2><span class="idx">8</span>多重比较、自相关与样本量提示</h2>
  <div class="grid3">
    <div class="find"><div class="h"><span class="n">!</span><b>多重比较</b></div>
      <p>检验 25 个 Lag 时，即便真实关系为 0，期望也有 25×5% ≈ 1.25 个 Lag 偶然达到 p&lt;0.05。本报告用 Benjamini-Hochberg FDR 与 Bonferroni 双校正：<b style="color:var(--neg)">最小 q = {fmt(min_q)}</b>，无一通过。</p></div>
    <div class="find"><div class="h"><span class="n">!</span><b>样本自相关</b></div>
      <p>库存变化 8 阶 Ljung-Box Q = {fmt(diag['lb_dI_q8'][0],2)}（p = {fmt(diag['lb_dI_q8'][1])}），存在显著自相关；收益率一阶自相关 {fmt(diag['rho_ret'])}。名义样本 n={M['n']}，<b>有效样本 ≈ {fmt(diag['n_eff_dI_ret'],0)}</b>。所有 t 值均用 Newey-West HAC 稳健标准误重算。</p></div>
    <div class="find"><div class="h"><span class="n">!</span><b>分区样本量</b></div>
      <p>分阶段后每段仅 22–29 期。在 n=26 时，r=0.5 的 95% 置信区间约为 [0.14, 0.75]；r=0.6 时约为 [0.28, 0.80]。<b style="color:var(--warn)">分段结果只能作为方向参考，不能作为结论</b>。</p></div>
  </div>
  <h3>朴素相关性 vs Newey-West 稳健 t 值</h3>
  <svg id="nwchart" class="chart" viewBox="0 0 1160 260" preserveAspectRatio="xMidYMid meet"></svg>
</section>
""")

# ---------------- 9 预测回归 ----------------
parts.append("""
<section class="card">
  <h2><span class="idx">9</span>能否预测？——披露后收益的样本内回归</h2>
  <p class="mut">即使相关性不显著，仍可检查“已知信息能否解释披露后的收益”。以下回归全部只使用 t 期及以前已披露的变量，并在 t+L 期收益上检验（Newey-West HAC）。</p>
  <div class="scroll"><table id="regtable"></table></div>
  <div class="note">单因子（库存变化 + 库存水平）在各 Lag 上 R² 均 ≤ 2.2%，系数不显著；加入江浙 MTO 产能利用率后 R² 明显上升，但显著性来自<b>需求侧变量</b>而非库存变化本身。这说明对甲醇边际定价更重要的是下游负荷，而不是库存的净变化。样本内 R² 不等于样本外可预测性，本节不做交易建议。</div>
</section>
""")

# ---------------- 10 结论 ----------------
finds = "".join(f"""<div class="find"><div class="h"><span class="n">F{f['no']}</span><b>{esc(f['title'])}</b><span class="tag">{esc(f['tag'])}</span></div><p>{esc(f['body'])}</p></div>""" for f in N["key_findings"])
why = "".join(f"<li>{esc(x)}</li>" for x in N["industry_explanation"]["why_no_lead"])
disc = "".join(f"<li>{esc(x)}</li>" for x in N["disclaimer"])
parts.append(f"""
<section class="card">
  <h2><span class="idx">10</span>结论：方向、稳定性与局限</h2>
  <div class="grid2" style="gap:14px">{finds}</div>
  <h3>什么时候有效、什么时候失效</h3>
  <p>本样本中<b style="color:#fff">不存在可以被称为“有效”的时期</b>——所有分段得到的峰值相关性都未通过多重检验校正，且样本量不足以拒绝“无关系”。可以明确的是：</p>
  <ul style="color:#cfdcef">
    <li><b>失效（不可依赖）</b>：2024 年 10–12 月（仅 10 期）；2025 年春节与 2025 年国庆前后（发布间隔 14–15 天，信息缺口期）；任何单一年度或单阶段的“最强 Lag”。</li>
    <li><b>需要谨慎</b>：2025 年（n=51）与 2026 年（n=40）虽各自出现 p&lt;0.05 的 Lag，但方向与期数相反（−9 与 +11），互不印证。</li>
    <li><b>仍成立的事实</b>：库存变化与披露当日价格反应同步相关接近 0，即“披露即消化”，价格在库存公布前已反应了大部分信息。</li>
  </ul>
  <h3>产业解释：为什么库存不领先价格</h3>
  <ul style="color:#cfdcef">{why}</ul>
  <h3>局限与不可越界的解释</h3>
  <ul style="color:#cfdcef">{disc}</ul>
</section>
""")

# ---------------- 附录 ----------------
parts.append("""
<section class="card">
  <h2><span class="idx">附</span>数据来源与计算口径</h2>
  <table><tbody>
    <tr><td style="width:180px">库存数据</td><td style="text-align:left">隆众资讯（www.oilchem.net）「[港口库存]：中国甲醇样本港口库存周数据统计」共 {n} 期，发布时间取自各页面发布字段；数值取自同站文章正文（华东、华南分项同步核对）</td></tr>
    <tr><td>期货数据</td><td style="text-align:left">郑商所甲醇主连（MA0）日线收盘价，2014-12-24 至 2026-10-19</td></tr>
    <tr><td>对照指标</td><td style="text-align:left">隆众「中国江浙地区MTO装置产能利用率（周）」100 期，用于需求侧对照回归</td></tr>
    <tr><td>计算内核</td><td style="text-align:left">纯 numpy/scipy 实现：Pearson r、Fisher-z 置信区间、Newey-West HAC、Benjamini-Hochberg FDR、Bonferroni、ADF、Ljung-Box</td></tr>
    <tr><td>时间口径</td><td style="text-align:left">所有时间均为北京时间（UTC+8）</td></tr>
  </tbody></table>
  <div class="footer">本报告为统计研究，不构成投资建议。所有结论均受样本区间与检验方法限制；统计相关不等于因果或可交易预测能力。</div>
</section>
""".replace("{n}", str(M["n"])))

parts.append("""
</div>
<script>
const DATA = __PAYLOAD__;
</script>
<script>
__JS__
</script>
</body></html>
""")

JS = r"""
const svgNS="http://www.w3.org/2000/svg";
function el(tag,attrs,parent){const e=document.createElementNS(svgNS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e;}
function txt(parent,x,y,s,attrs){const t=el("text",Object.assign({x:x,y:y},attrs||{}),parent);t.textContent=s;return t;}
const F=(v,d=3)=>v===null||v===undefined?"—":Number(v).toFixed(d);
const P=(v)=>v===null||v===undefined?"—":(v<0.001?"<0.001":Number(v).toFixed(3));
const COL={acc:"#4fd1c5",acc2:"#7aa2ff",neg:"#ff6b81",pos:"#3ddc97",warn:"#ffb454",mut:"#8fa3c0",line:"#243552",ink:"#e8eef8"};

/* ---------- 3. 主 Lag 曲线 ---------- */
const scan=DATA.scan;
let view="r";
const chart=document.getElementById("lagchart");
const W=1160,H=400,padL=64,padR=24,padT=26,padB=52;
const iw=W-padL-padR, ih=H-padT-padB;
const lags=scan.map(d=>d.lag);
const x=l=>padL+(l-lags[0])/(lags[lags.length-1]-lags[0])*iw;
function drawLag(){
  chart.innerHTML="";
  const g=el("g",{},chart);
  let ymin=-0.4,ymax=0.4,ylab="r";
  if(view==="r"){ymin=-0.45;ymax=0.45;ylab="相关系数 r";}
  const valsP=scan.map(d=>-Math.log10(Math.max(d.p||1,1e-12)));
  const valsQ=scan.map(d=>-Math.log10(Math.max(d.q_bh||1,1e-12)));
  const autoMax=(arr)=>{const m=Math.max(...arr,0);return Math.max(1.0, Math.ceil((m+0.25)*2)/2);};
  if(view==="p"){ymin=0;ymax=autoMax(valsP);ylab="−log10(p)，越高越显著"}
  if(view==="q"){ymin=0;ymax=autoMax(valsQ);ylab="−log10(q, FDR)，超过 1.30 才显著"}
  if(view==="n"){ymin=Math.min(...scan.map(d=>d.n))-2;ymax=Math.max(...scan.map(d=>d.n))+2;ylab="有效样本 n"}
  const y=v=>padT+(1-(v-ymin)/(ymax-ymin))*ih;
  // grid
  for(let k=0;k<=6;k++){
    const v=ymin+(ymax-ymin)*k/6;
    el("line",{x1:padL,x2:W-padR,y1:y(v),y2:y(v),stroke:"#1c2b44","stroke-width":1},g);
    txt(g,padL-10,y(v)+4,view==="r"?v.toFixed(2):v.toFixed(1),{fill:COL.mut,"font-size":11,"text-anchor":"end"});
  }
  // zero / thresholds
  if(view==="r"){el("line",{x1:padL,x2:W-padR,y1:y(0),y2:y(0),stroke:"#3b5378","stroke-dasharray":"4 4"},g);}
  if(view==="p"||view==="q"){
    el("line",{x1:padL,x2:W-padR,y1:y(-Math.log10(0.05)),y2:y(-Math.log10(0.05)),stroke:COL.warn,"stroke-dasharray":"5 5"},g);
    txt(g,W-padR-4,y(-Math.log10(0.05))-6,"5% 显著线",{fill:COL.warn,"font-size":11,"text-anchor":"end"});
  }
  // x axis
  el("line",{x1:padL,x2:W-padR,y1:padT+ih,y2:padT+ih,stroke:"#2b3e5e"},g);
  scan.forEach(d=>{
    txt(g,x(d.lag),padT+ih+18,(d.lag>0?"+":"")+d.lag,{fill:d.lag===0?COL.acc:COL.mut,"font-size":11,"text-anchor":"middle"});
  });
  txt(g,W-padR,padT+ih+42,"Lag（周）  ← 期货领先库存  |  库存领先期货 →",{fill:COL.mut,"font-size":11.5,"text-anchor":"end"});
  txt(g,padL-52,padT-12,ylab,{fill:COL.mut,"font-size":11.5});
  // confidence band for r
  if(view==="r"){
    let up="",dn="";
    scan.forEach((d,i)=>{const lo=d.ci_lo??0,hi=d.ci_hi??0;up+=(i?"L":"M")+x(d.lag)+","+y(hi);dn="L"+x(d.lag)+","+y(lo)+dn;});
    el("path",{d:up+"L"+x(lags[lags.length-1])+","+y(scan[scan.length-1].ci_lo||0)+dn+"Z",fill:"rgba(122,162,255,.16)",stroke:"none"},g);
  }
  // line + points
  let path="";
  scan.forEach((d,i)=>{
    let v = view==="r"?d.r : view==="p"?-Math.log10(Math.max(d.p,1e-12)) : view==="q"?-Math.log10(Math.max(d.q_bh,1e-12)) : d.n;
    if(v===null||v===undefined){return;}
    v=Math.max(ymin,Math.min(ymax,v));
    path+=(path?"L":"M")+x(d.lag)+","+y(v);
  });
  el("path",{d:path,fill:"none",stroke:COL.acc,"stroke-width":2.2,"stroke-linejoin":"round"},g);
  scan.forEach(d=>{
    let v = view==="r"?d.r : view==="p"?-Math.log10(Math.max(d.p,1e-12)) : view==="q"?-Math.log10(Math.max(d.q_bh,1e-12)) : d.n;
    if(v===null)return; v=Math.max(ymin,Math.min(ymax,v));
    let c = view==="r" ? (Math.abs(d.r||0)>0.15 ? COL.acc : COL.acc2)
          : view==="p" ? ((d.p||1)<0.05 ? COL.warn : COL.acc2)
          : view==="q" ? ((d.q_bh||1)<0.05 ? COL.neg : COL.acc2)
          : COL.acc2;
    const isBest = (d===BEST);
    el("circle",{cx:x(d.lag),cy:y(v),r:isBest?6:3.6,fill:isBest?COL.warn:c,stroke:"#0b1220","stroke-width":isBest?2:0},g).style.cursor="pointer";
    el("circle",{cx:x(d.lag),cy:y(v),r:12,fill:"transparent"},g).onclick=()=>selectLag(d.lag);
  });
  // highlight selected
  const ss=scan.find(d=>d.lag===SEL);
  if(ss){el("line",{x1:x(SEL),x2:x(SEL),y1:padT,y2:padT+ih,stroke:COL.warn,"stroke-width":1,"stroke-dasharray":"3 3",opacity:.6},g);}
  // annotate best |r|（右边界夹紧）
  const by=y(BEST.r);
  let ax=x(BEST.lag)+10; const alab="最强 |r| = "+F(BEST.r)+"（q="+F(BEST.q_bh)+"，不显著）";
  if(ax+230>W-padR-4) ax=x(BEST.lag)-240;
  txt(g,ax,by-12,alab,{fill:COL.warn,"font-size":11.5});
}
const BEST=scan.reduce((a,b)=>Math.abs(b.r)>Math.abs(a.r)?b:a,scan[0]);
let SEL=0;
document.querySelectorAll("[data-view]").forEach(btn=>btn.onclick=()=>{
  document.querySelectorAll("[data-view]").forEach(x=>x.classList.remove("on"));
  btn.classList.add("on"); view=btn.dataset.view; drawLag();
});

/* ---------- lag table ---------- */
const tb=document.querySelector("#lagtable tbody");
scan.forEach(d=>{
  const tr=document.createElement("tr");
  const cls=(d.q_bh||1)<0.05?"ok":((d.p||1)<0.05?"mid":"no");
  tr.innerHTML=`<td>${d.lag>0?"+":""}${d.lag}</td><td>${d.n}</td><td>${F(d.r)}</td>
    <td class="mut">[${F(d.ci_lo,2)}, ${F(d.ci_hi,2)}]</td><td>${P(d.p)}</td><td>${F(d.t_nw,2)}</td>
    <td><span class="pill ${cls}">${P(d.p_nw)}</span></td><td><span class="pill ${(d.q_bh||1)<0.05?'ok':'no'}">${F(d.q_bh)}</span></td>
    <td class="mut">${F(d.q_bonf,2)}</td><td class="mut">${F(d.n_eff,1)}</td>`;
  tr.onclick=()=>selectLag(d.lag);
  tr.dataset.lag=d.lag;
  tb.appendChild(tr);
});

/* ---------- 4. matrix ---------- */
function drawMatrix(){
  const m=document.getElementById("matrix");m.innerHTML="";
  const PW=44, cell=(1160-120)/25, H0=250;
  for(let i=0;i<scan.length;i++){
    const d=scan[i];
    const xx=100+i*cell;
    const r=d.r||0;
    const a=Math.min(1,Math.abs(r)/0.35);
    const col=r<0?`rgba(255,107,129,${0.12+a*0.75})`:`rgba(79,209,197,${0.12+a*0.75})`;
    el("rect",{x:xx,y:74,width:cell-3,height:74,rx:4,fill:col,stroke:"#0b1220"},m).onclick=()=>selectLag(d.lag);
    el("rect",{x:xx,y:156,width:cell-3,height:30,rx:4,fill:"rgba(255,255,255,.03)",stroke:COL.line},m);
    txt(m,xx+cell/2-1.5,80+30,(d.lag>0?"+":"")+d.lag,{fill:COL.ink,"font-size":10.5,"text-anchor":"middle"});
    txt(m,xx+cell/2-1.5,74+50,F(r,2),{fill:COL.ink,"font-size":10.5,"text-anchor":"middle"});
    txt(m,xx+cell/2-1.5,74+64,"q"+F(d.q_bh,2),{fill:"rgba(255,255,255,.65)","font-size":9,"text-anchor":"middle"});
    txt(m,xx+cell/2-1.5,176,"n="+d.n,{fill:COL.mut,"font-size":9.5,"text-anchor":"middle"});
  }
  txt(m,100,40,"B 领先 A：期货收益 → 库存（Lag 为负）",{fill:COL.neg,"font-size":12.5});
  txt(m,1160-100,40,"A 领先 B：库存 → 期货收益（Lag 为正）",{fill:COL.pos,"font-size":12.5,"text-anchor":"end"});
  el("line",{x1:100+12.5*cell,y1:30,x2:100+12.5*cell,y2:200,stroke:"#3b5378","stroke-dasharray":"4 4"},m);
  txt(m,100,210,"← 期货收益领先库存（Lag 为负）                    Lag = 0（同期）                    库存领先期货收益（Lag 为正）→",{fill:COL.mut,"font-size":11});
  el("line",{x1:100+12.5*cell,y1:196,x2:100+12.5*cell,y2:206,stroke:COL.warn},m);
  txt(m,70,110,"相关 r",{fill:COL.mut,"font-size":11,"text-anchor":"middle"});
  txt(m,70,176,"样本 n",{fill:COL.mut,"font-size":11,"text-anchor":"middle"});
}

/* ---------- 5. detail ---------- */
const ser=DATA.series;
const lagsel=document.getElementById("lagsel");
scan.forEach(d=>{const o=document.createElement("option");o.value=d.lag;o.textContent=(d.lag>0?"":(d.lag<0?"−":""))+Math.abs(d.lag)+" 周";lagsel.appendChild(o);});
lagsel.onchange=()=>selectLag(parseInt(lagsel.value));

function selectLag(L){
  SEL=L; lagsel.value=L;
  document.querySelectorAll("#lagtable tbody tr").forEach(tr=>tr.classList.toggle("sel",parseInt(tr.dataset.lag)===L));
  const d=scan.find(x=>x.lag===L);
  const desc = L>0?`库存变化领先期货收益 ${L} 周：用 t 期库存变化对 t+${L} 期期货收益做相关`
             : L<0?`期货收益领先库存变化 ${-L} 周：用 t 期库存变化对 t${L} 期期货收益做相关（即期货收益先行 ${-L} 周）`
             : "同期：库存变化与该周披露日收益的同周相关";
  document.getElementById("lagdesc").textContent=desc;
  // align
  const ab=document.querySelector("#aligntable tbody"); ab.innerHTML="";
  let cnt=0;
  for(let t=0;t<ser.length;t++){
    const j=t+L; if(j<0||j>=ser.length)continue;
    const a=ser[t].dI, b=ser[j].r;
    if(a===null||b===null)continue;
    if(cnt++>=14)break;
    const tr=document.createElement("tr");
    tr.innerHTML=`<td>${ser[t].d}</td><td class="mut">${ser[t].pub_hm}</td><td>${F(a,2)}</td><td>${ser[j].d}</td><td>${F(b,2)}</td>`;
    ab.appendChild(tr);
  }
  // scatter
  const pts=[];
  for(let t=0;t<ser.length;t++){const j=t+L;if(j<0||j>=ser.length)continue;const a=ser[t].dI,b=ser[j].r;if(a===null||b===null)continue;pts.push([a,b]);}
  drawScatter(pts,d);
  // rolling
  drawRolling(L);
  // year & stage
  const yt=document.querySelector("#yeartable tbody"); yt.innerHTML="";
  DATA.years.forEach(y=>{
    const s=DATA.year_scan[y.year].find(x=>x.lag===L);
    const tr=document.createElement("tr");
    tr.innerHTML=`<td>${y.year}</td><td>${s.n}</td><td>${F(s.r)}</td><td>${P(s.p)}</td><td>${F(s.q_bh)}</td>`;
    yt.appendChild(tr);
  });
  const st=document.querySelector("#stagetable tbody"); st.innerHTML="";
  DATA.stages.forEach(g=>{
    const s=DATA.stage_scan[g.code].find(x=>x.lag===L);
    const tr=document.createElement("tr");
    tr.innerHTML=`<td style="text-align:left;font-size:11.5px">${g.code}</td><td>${s.n}</td><td>${F(s.r)}</td><td>${P(s.p)}</td><td>${F(s.q_bh)}</td>`;
    st.appendChild(tr);
  });
  const judge = (d.q_bh||1)<0.05
    ? `<b style="color:var(--pos)">该 Lag 通过 FDR 校正（q<0.05）</b>，仍需结合分阶段稳定性判断。`
    : `<b style="color:var(--neg)">该 Lag 未通过多重检验校正</b>（q = ${F(d.q_bh)}）。未经校正的 p = ${P(d.p)}，在 25 次检验的背景下属于预期内的偶然结果。`;
  document.getElementById("lagjudge").innerHTML=judge;
  drawLag();
}

function drawScatter(pts,d){
  const s=document.getElementById("scatter"); s.innerHTML="";
  const W2=560,H2=320,pl=52,pb=42,pt=18,pr=18;
  const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
  const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
  const padx=(x1-x0)*0.06||1,pady=(y1-y0)*0.06||1;
  const X=v=>pl+(v-(x0-padx))/((x1+padx)-(x0-padx))*(W2-pl-pr);
  const Y=v=>pt+(1-(v-(y0-pady))/((y1+pady)-(y0-pady)))*(H2-pt-pb);
  for(let k=0;k<=5;k++){
    const gy=pt+(H2-pt-pb)*k/5; el("line",{x1:pl,x2:W2-pr,y1:gy,y2:gy,stroke:"#1c2b44"},s);
    const gyv=(y1+pady)-((y1+pady)-(y0-pady))*k/5;
    txt(s,pl-8,gy+4,gyv.toFixed(1),{fill:COL.mut,"font-size":10,"text-anchor":"end"});
    const gx=pl+(W2-pl-pr)*k/5; el("line",{x1:gx,x2:gx,y1:pt,y2:H2-pb,stroke:"#1c2b44"},s);
    const gxv=(x0-padx)+((x1+padx)-(x0-padx))*k/5;
    txt(s,gx,H2-pb+16,gxv.toFixed(1),{fill:COL.mut,"font-size":10,"text-anchor":"middle"});
  }
  pts.forEach(p=>{el("circle",{cx:X(p[0]),cy:Y(p[1]),r:2.8,fill:"rgba(122,162,255,.75)"},s);});
  // OLS line
  const mx=xs.reduce((a,b)=>a+b,0)/xs.length,my=ys.reduce((a,b)=>a+b,0)/ys.length;
  let sxy=0,sxx=0; pts.forEach(p=>{sxy+=(p[0]-mx)*(p[1]-my);sxx+=(p[0]-mx)**2;});
  const b1=sxx?sxy/sxx:0;
  el("line",{x1:X(x0-padx),y1:Y(my+b1*((x0-padx)-mx)),x2:X(x1+padx),y2:Y(my+b1*((x1+padx)-mx)),stroke:COL.warn,"stroke-width":2},s);
  txt(s,pl,H2-8,"Δ库存（万吨）",{fill:COL.mut,"font-size":11});
  txt(s,pl-46,pt-10,"收益 %",{fill:COL.mut,"font-size":11,"text-anchor":"start"});
  document.getElementById("scatstat").innerHTML=`n = ${d.n} · r = ${F(d.r)} · 斜率 = ${F(b1,3)} %/万吨 · p = ${P(d.p)} · FDR q = ${F(d.q_bh)}`;
}

function drawRolling(L){
  const s=document.getElementById("rollchart"); s.innerHTML="";
  const data=(DATA.rolling[String(L)]||[]).filter(p=>p.r!==null);
  if(!data.length){txt(s,20,40,"该 Lag 无足够滚动窗口",{fill:COL.mut,"font-size":12});return;}
  const W3=1160,H3=260,pl=56,pb=36,pt=18,pr=20;
  const X=i=>pl+i/(Math.max(1,data.length-1))*(W3-pl-pr);
  const Y=v=>pt+(1-(v+1)/2)*(H3-pt-pb);
  for(let k=0;k<=4;k++){const v=1-k/2;const gy=Math.min(Y(v),H3-pb-12);el("line",{x1:pl,x2:W3-pr,y1:Y(v),y2:Y(v),stroke:"#1c2b44"},s);txt(s,pl-10,gy+4,v.toFixed(2),{fill:COL.mut,"font-size":10,"text-anchor":"end"});}
  el("line",{x1:pl,x2:W3-pr,y1:Y(0),y2:Y(0),stroke:"#3b5378"},s);
  el("rect",{x:pl,y:Y(0.39),width:W3-pl-pr,height:Y(-0.39)-Y(0.39),fill:"rgba(255,180,84,.06)"},s);
  el("line",{x1:pl,x2:W3-pr,y1:Y(0.39),y2:Y(0.39),stroke:"rgba(255,180,84,.5)","stroke-dasharray":"4 4"},s);
  el("line",{x1:pl,x2:W3-pr,y1:Y(-0.39),y2:Y(-0.39),stroke:"rgba(255,180,84,.5)","stroke-dasharray":"4 4"},s);
  let path="";data.forEach((p,i)=>{path+=(i?"L":"M")+X(i)+","+Y(p.r);});
  el("path",{d:path,fill:"none",stroke:COL.acc2,"stroke-width":2},s);
  data.forEach((p,i)=>{el("circle",{cx:X(i),cy:Y(p.r),r:2.4,fill:COL.acc2},s);});
  for(let k=0;k<5;k++){const i=Math.round(k*(data.length-1)/4);txt(s,X(i),H3-pb+16,data[i].end,{fill:COL.mut,"font-size":10,"text-anchor":"middle"});}
}

/* ---------- 6. summary tables ---------- */
function bestOf(arr){return arr.reduce((a,b)=>(Math.abs(b.r||0)>Math.abs(a.r||0)?b:a),arr[0]);}
(function(){
  const yt=document.getElementById("ysummary");
  let h="<thead><tr><th>年度</th><th>n</th><th>最强 Lag</th><th>r</th><th>p</th><th>q FDR</th><th>方向</th></tr></thead><tbody>";
  DATA.years.forEach(y=>{
    const b=bestOf(DATA.year_scan[y.year]);
    h+=`<tr><td>${y.year}</td><td>${y.n_weeks}</td><td>${b.lag>0?'+':''}${b.lag}</td><td>${F(b.r)}</td><td>${P(b.p)}</td><td>${F(b.q_bh)}</td><td>${b.r>0?'正':'负'}</td></tr>`;
  });
  yt.innerHTML=h+"</tbody>";
  const st=document.getElementById("ssummary");
  h="<thead><tr><th>阶段</th><th>n</th><th>最强 Lag</th><th>r</th><th>p</th><th>q FDR</th></tr></thead><tbody>";
  DATA.stages.forEach(g=>{
    const b=bestOf(DATA.stage_scan[g.code]);
    h+=`<tr><td style="font-size:11.5px">${g.code}</td><td>${g.n_weeks}</td><td>${b.lag>0?'+':''}${b.lag}</td><td>${F(b.r)}</td><td>${P(b.p)}</td><td>${F(b.q_bh)}</td></tr>`;
  });
  st.innerHTML=h+"</tbody>";
  const sl=document.getElementById("stagelist");
  h="<thead><tr><th>阶段</th><th>区间</th><th>周数</th><th style='text-align:left'>划分依据（价格/库存路径）</th></tr></thead><tbody>";
  DATA.stages.forEach(g=>{
    h+=`<tr><td>${g.code.split("_")[0]}</td><td>${g.start} → ${g.end}</td><td>${g.n_weeks}</td>
      <td style="text-align:left;font-size:11.5px">${g.note}<br><span class="mut">库存 ${F(g.inv_start,1)} → ${F(g.inv_end,1)} 万吨 · 价格 ${F(g.px_start,0)} → ${F(g.px_end,0)} 元/吨</span></td></tr>`;
  });
  sl.innerHTML=h+"</tbody>";
})();

/* ---------- heatmap ---------- */
function drawHeat(){
  const s=document.getElementById("heat"); s.innerHTML="";
  const cols=[["2024",DATA.year_scan["2024"]],["2025",DATA.year_scan["2025"]],["2026",DATA.year_scan["2026"]]];
  DATA.stages.forEach(g=>cols.push([g.code.split("_")[0],DATA.stage_scan[g.code]]));
  Object.keys(DATA.half_scan).forEach(k=>cols.push([k,DATA.half_scan[k]]));
  const pl=90,pt=78,cw=(1160-pl-20)/cols.length,chh=(560-pt-40)/25;
  cols.forEach((c,ci)=>{
    txt(s,pl+ci*cw+cw/2,pt-26,c[0],{fill:COL.ink,"font-size":11,"text-anchor":"middle"});
    txt(s,pl+ci*cw+cw/2,pt-10,"n="+(c[1][0].n||"-"),{fill:COL.mut,"font-size":9.5,"text-anchor":"middle"});
  });
  scan.forEach((d,ri)=>{
    txt(s,pl-8,pt+ri*chh+chh/2+3.5,(d.lag>0?"+":"")+d.lag,{fill:COL.mut,"font-size":9.5,"text-anchor":"end"});
    cols.forEach((c,ci)=>{
      const v=c[1][ri].r;
      const a=Math.min(1,Math.abs(v||0)/0.5);
      const fill=(v||0)<0?`rgba(255,107,129,${0.06+a*0.8})`:`rgba(79,209,197,${0.06+a*0.8})`;
      el("rect",{x:pl+ci*cw,y:pt+ri*chh,width:cw-3,height:chh-2,rx:2,fill:fill},s).onclick=()=>selectLag(d.lag);
    });
  });
  txt(s,pl-100,pt-56,"行：Lag　列：时期（颜色=相关系数 r）",{fill:COL.mut,"font-size":11});
}

/* ---------- 7. variants ---------- */
let VARIANT="D1_主设定_Δ库存(万吨)×披露日对数收益";
function drawVariant(){
  const s=document.getElementById("varchart"); s.innerHTML="";
  const arr=DATA.variants[VARIANT];
  const W4=1160,H4=300,pl=60,pb=40,pt=20,pr=20;
  const l0=arr[0].lag,l1=arr[arr.length-1].lag;
  const X=l=>pl+(l-l0)/(l1-l0)*(W4-pl-pr);
  const Y=v=>pt+(1-(v+0.7)/1.4)*(H4-pt-pb);
  for(let k=0;k<=7;k++){const v=-0.7+k*0.2;el("line",{x1:pl,x2:W4-pr,y1:Y(v),y2:Y(v),stroke:"#1c2b44"},s);txt(s,pl-8,Y(v)+4,v.toFixed(1),{fill:COL.mut,"font-size":10,"text-anchor":"end"});}
  el("line",{x1:pl,x2:W4-pr,y1:Y(0),y2:Y(0),stroke:"#3b5378"},s);
  let p="";
  arr.forEach((d,i)=>{if(d.r===null)return;p+=(p?"L":"M")+X(d.lag)+","+Y(d.r);});
  el("path",{d:p,fill:"none",stroke:VARIANT.indexOf("D4")>=0?COL.neg:COL.acc,"stroke-width":2.2},s);
  arr.forEach(d=>{if(d.r===null)return;el("circle",{cx:X(d.lag),cy:Y(d.r),r:(d.q_bh<0.05)?5:3.2,fill:(d.q_bh<0.05)?COL.neg:COL.acc},s);});
  arr.forEach(d=>txt(s,X(d.lag),H4-pb+16,(d.lag>0?"+":"")+d.lag,{fill:COL.mut,"font-size":10,"text-anchor":"middle"}));
  const b=arr.reduce((a,b)=>(Math.abs(b.r||0)>Math.abs(a.r||0)?b:a),arr[0]);
  txt(s,pl,pt-4,VARIANT,{fill:COL.ink,"font-size":12});
  txt(s,X(b.lag)+8,Y(b.r)-8,`最强 Lag ${b.lag>0?'+':''}${b.lag}：r=${F(b.r)}，q=${F(b.q_bh)}${b.q_bh<0.05?"（校正后显著）":"（不显著）"}`,{fill:b.q_bh<0.05?COL.neg:COL.warn,"font-size":11.5});
}
document.querySelectorAll("[data-variant]").forEach(b=>b.onclick=()=>{
  document.querySelectorAll("[data-variant]").forEach(x=>x.classList.remove("on"));
  b.classList.add("on"); VARIANT=b.dataset.variant; drawVariant();
});
(function(){
  const t=document.getElementById("shifttable");
  const keys=Object.keys(DATA.shift).sort((a,b)=>a-b);
  let h="<thead><tr><th>可得时点调整</th><th>最强 Lag</th><th>r</th><th>p</th></tr></thead><tbody>";
  keys.forEach(k=>{
    const arr=DATA.shift[k];
    const b=arr.reduce((x,y)=>(Math.abs(y.r||0)>Math.abs(x.r||0)?y:x),arr[0]);
    const lbl=k==="0"?"真实时点（基准）":(Number(k)<0?`提前 ${-Number(k)} 周（现实中不可能）`:`延后 ${k} 周（更保守）`);
    h+=`<tr><td style="text-align:left">${lbl}</td><td>${b.lag>0?'+':''}${b.lag}</td><td>${F(b.r)}</td><td>${P(b.p)}</td></tr>`;
  });
  t.innerHTML=h+"</tbody>";
})();

/* ---------- 8. NW chart ---------- */
(function(){
  const s=document.getElementById("nwchart"); s.innerHTML="";
  const W5=1160,H5=260,pl=60,pb=40,pt=20,pr=20;
  const X=l=>pl+(l+12)/24*(W5-pl-pr);
  const Y=v=>pt+(1-(v+3)/6)*(H5-pt-pb);
  for(let k=0;k<=6;k++){const v=-3+k;el("line",{x1:pl,x2:W5-pr,y1:Y(v),y2:Y(v),stroke:"#1c2b44"},s);txt(s,pl-8,Y(v)+4,v.toFixed(0),{fill:COL.mut,"font-size":10,"text-anchor":"end"});}
  el("line",{x1:pl,x2:W5-pr,y1:Y(0),y2:Y(0),stroke:"#3b5378"},s);
  let p1="",p2="";
  scan.forEach((d,i)=>{p1+=(i?"L":"M")+X(d.lag)+","+Y(Math.max(-3,Math.min(3,d.t)));p2+=(i?"L":"M")+X(d.lag)+","+Y(Math.max(-3,Math.min(3,d.t_nw)));});
  el("path",{d:p1,fill:"none",stroke:"rgba(122,162,255,.75)","stroke-width":1.8,"stroke-dasharray":"5 4"},s);
  el("path",{d:p2,fill:"none",stroke:COL.acc,"stroke-width":2.2},s);
  scan.forEach(d=>txt(s,X(d.lag),H5-pb+16,(d.lag>0?"+":"")+d.lag,{fill:COL.mut,"font-size":10,"text-anchor":"middle"}));
  txt(s,pl,pt-4,"t 值（±2 约为 5% 显著）",{fill:COL.mut,"font-size":11});
  txt(s,W5-260,pt+10,"—— 朴素 t",{fill:"rgba(122,162,255,.9)","font-size":11});
  txt(s,W5-260,pt+26,"—— Newey-West 稳健 t",{fill:COL.acc,"font-size":11});
})();

/* ---------- 9. regressions ---------- */
(function(){
  const t=document.getElementById("regtable");
  let h="<thead><tr><th>收益期</th><th>模型</th><th>n</th><th>R²</th><th>调整 R²</th><th>Δ库存系数</th><th>t（NW）</th><th>库存水平系数</th><th>t</th><th>MTO 水平系数</th><th>t</th><th>ΔMTO 系数</th><th>t</th></tr></thead><tbody>";
  Object.keys(DATA.reg).forEach(k=>{
    ["inventory_only","inventory_plus_fundamental"].forEach(mk=>{
      const m=DATA.reg[k][mk];
      const name=mk==="inventory_only"?"库存因子":"库存 + 需求侧（MTO）";
      const g=(arr,i)=>arr&&arr[i]!==undefined?arr[i]:null;
      h+=`<tr><td>t${k==="L0"?"":"+"+k.slice(1)}</td><td style="text-align:left">${name}</td><td>${m.n}</td>
        <td>${m.r2===null?"—":F(m.r2,4)}</td><td>${m.adj_r2===null?"—":F(m.adj_r2,4)}</td>
        <td>${m.beta?F(g(m.beta,1),5):"—"}</td><td>${m.t?F(g(m.t,1),2):"—"}</td>
        <td>${m.beta?F(g(m.beta,2),6):"—"}</td><td>${m.t?F(g(m.t,2),2):"—"}</td>
        <td>${m.beta?F(g(m.beta,3),5):"—"}</td><td>${m.t?F(g(m.t,3),2):"—"}</td>
        <td>${m.beta?F(g(m.beta,4),5):"—"}</td><td>${m.t?F(g(m.t,4),2):"—"}</td></tr>`;
    });
  });
  t.innerHTML=h+"</tbody>";
})();

/* ---------- init ---------- */
drawLag(); drawMatrix(); drawHeat(); drawVariant();
selectLag(0);
"""

html = "".join(parts).replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False)).replace("__JS__", JS)
out = os.path.join(os.path.dirname(HERE), "甲醇港口库存与期货收益_领先滞后关系研究报告.html")
open(out, "w", encoding="utf-8").write(html)
print("saved", out, len(html))
