# -*- coding: utf-8 -*-
"""render_html.py —— 单文件交互式 HTML 核对报告。

特性（规格要求逐条落地）：
  * 顶部展示文件抽取结果，三态可编辑/确认（确认/标疑/非本批）
  * 全指标比对表：按状态筛选 + 关键词搜索 + 点击行展开"COA 原文 vs 规格原文 + 定位"
  * 每项展示：实测、限值、单位换算公式、判定理由、可比性五维、偏离公式
  * 多批次趋势 SVG（含限值带、单位归一说明）
  * 证书完整性问题清单（得分 + 高/中/低 + 处理动作）
  * 方法差异表
  * 一键生成质量异议函（正式/强硬/沟通三语气，复制/下载）
  * 全局免责：不替用户决定是否接收

用法：python render_html.py data.json out.html
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "assets"))
import coa_lib as L        # noqa: E402
import engine             # noqa: E402

ASSETS = os.path.join(HERE, "..", "assets")

STATUS_CLS = {L.ST_OK: "ok", L.ST_FAIL: "fail", L.ST_UNSPEC: "unspec",
              L.ST_UNTESTED: "untested", L.ST_UNKNOWN: "unknown"}
STATUS_ICON = {L.ST_OK: "✓", L.ST_FAIL: "✕", L.ST_UNSPEC: "—", L.ST_UNTESTED: "?", L.ST_UNKNOWN: "≈"}


def e(s):
    return html.escape("" if s is None else str(s), quote=True)


TONE_LABELS = {"formal": "正式 · 质量异议函", "firm": "强硬 · 索赔前置", "soft": "沟通 · 供应商友好版"}


def st_badge(s):
    return f'<span class="st st-{STATUS_CLS.get(s, "unknown")}">{e(s)}</span>'


def sev_badge(s):
    return f'<span class="sev sev-{e(s)}">{e(s)}</span>' if s else ""


def g(v, nd=4):
    if v is None:
        return ""
    if isinstance(v, float):
        if v == 0:
            return "0"
        if abs(v) < 1e-3:
            return f"{v:.3g}"
        return f"{round(v, nd):g}"
    return e(v)


def fmt_pct(p, sign=True):
    if p is None:
        return ""
    return f"{p:+.2f}%" if sign else f"{p:.2f}%"


def css():
    with open(os.path.join(ASSETS, "coa-report.css"), encoding="utf-8") as f:
        return f.read()


# ======================================================================================
# 各区块
# ======================================================================================

def sec_hero(res):
    m, p, sp = res["meta"], res["product"], res["supplier"]
    k = res["kpis"]
    sim = m.get("simulated")
    band = (f'<div class="wm-band">⚠ 模拟数据 SIMULATED DATA — {e(m.get("sim_note", ""))}</div>'
            if sim else "")
    return band + f"""
<header class="hero">
  <h1>{e(m.get('title'))}</h1>
  <div class="sub">COA / 检验报告 ↔ 采购规格书 / 合同技术附件 / 适用标准 · 逐项质量指标核对</div>
  <div class="chips">
    <span class="chip">产品 <b>{e(p['name'])}</b> · {e(p.get('grade',''))}</span>
    <span class="chip">CAS <b>{e(p.get('cas',''))}</b> · HS {e(p.get('hs',''))}</span>
    <span class="chip">供应商 <b>{e(sp.get('name',''))}</b></span>
    <span class="chip">核对基准日 <b>{e(m.get('as_of',''))}</b></span>
    <span class="chip">重点批次 <b>{e(k['target_batch'])}</b></span>
    <span class="chip">规格依据 <b>{e(m.get('spec_ref',''))}</b></span>
  </div>
</header>
"""


def sec_kpis(res):
    k = res["kpis"]
    c = k["counts"]
    cards = [
        ("c-brand", "核对指标总数", k["total"], "规格 ∪ 标准 ∪ COA ∪ 历史批次出现的全部项目"),
        ("c-ok", "符合", c.get(L.ST_OK, 0), "实测在限值内，且方法/单位可比"),
        ("c-fail", "不符合", c.get(L.ST_FAIL, 0), "实测越过合同/规格限值"),
        ("c-untested", "COA未检测", c.get(L.ST_UNTESTED, 0), "规格已约定，COA 缺项或标注未测"),
        ("c-unknown", "无法判断", c.get(L.ST_UNKNOWN, 0), "缺方法/检出限/单位不可比等，交人工"),
        ("c-unspec", "规格未约定", c.get(L.ST_UNSPEC, 0), "合同未约定，不能据以判不合格"),
    ]
    out = ['<div class="kpis">']
    for cls, lab, val, sub in cards:
        out.append(f'<div class="kpi {cls}"><div class="lab">{lab}</div>'
                   f'<div class="val">{val}</div><div class="sub">{e(sub)}</div></div>')
    out.append('</div>')
    # 第二行：可量化口径
    out.append(f"""<div class="kpis">
<div class="kpi c-fail"><div class="lab">最大偏离幅度</div><div class="val">{fmt_pct(k['max_dev_pct'])}</div>
  <div class="sub">以限值为分母：超出部分 ÷ 限值</div></div>
<div class="kpi c-brand"><div class="lab">可量化核验比例</div><div class="val">{k['verifiable_ratio']:.0f}%</div>
  <div class="sub">(符合+不符合) ÷ 全部指标</div></div>
<div class="kpi c-untested"><div class="lab">证书完整性得分</div><div class="val">{k['completeness']}</div>
  <div class="sub">100 起扣，高 -18 / 中 -8 / 低 -3</div></div>
<div class="kpi c-unknown"><div class="lab">方法差异项</div><div class="val">{k['method_diff']}</div>
  <div class="sub">COA 方法与合同/标准约定不同</div></div>
<div class="kpi c-unspec"><div class="lab">异议要点</div><div class="val">{k['objection_points']}</div>
  <div class="sub">可直接用于质量异议函</div></div>
</div>""")
    return "".join(out)


def sec_scope(res):
    m = res["meta"]
    sp = res["supplier"]
    ct = res["contract"]
    rows = [
        ("采购方", m.get("buyer_name", "")),
        ("供应商", f"{sp.get('name','')} · {sp.get('role','')}"),
        ("合同号 / 技术附件", f"{ct.get('no','')} / {ct.get('attach','')}"),
        ("质量条款", ct.get("quality_clause", "")),
        ("执行规格", m.get("spec_ref", "")),
        ("产品用途（相关性参照）", res["product"].get("use", "")),
        ("原文定位约定", "每条比对均给出 COA 与规格文件中的条款/行号；点击指标行可展开原文摘录"),
        ("可追溯性", "data.json 记录全部原始取值与解析结果；本报告由 engine.py 自动生成，不手工改数"),
    ]
    kv = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in rows)
    return f"""<section class="card"><h2><span class="n">0</span>核对范围与依据</h2>
<div class="lead">先确定"拿什么比什么"，再谈结论。合同技术附件优先于采购规格书，规格书优先于国家/行业标准。</div>
<div class="grid2"><dl class="kv">{kv}</dl>
<div><h4 style="color:var(--brand);font-size:13px;margin-bottom:6px">文件清单</h4>
<table><tr><th>类型</th><th>文件</th><th>版本/编号</th><th>条款定位</th></tr>
<tr><td>采购规格书</td><td>{e(res['specs'][0]['title']) if res['specs'] else ''}</td>
    <td>{e(res['specs'][0].get('spec_no','')) if res['specs'] else ''}</td>
    <td class="tiny">{e(res['specs'][0].get('loc','')) if res['specs'] else ''}</td></tr>
{''.join(f"<tr><td>合同技术附件</td><td>{e(s['title'])}</td><td>{e(s.get('spec_no',''))}</td><td class='tiny'>{e(s.get('loc',''))}</td></tr>" for s in res['specs'][1:])}
{''.join(f"<tr><td>适用标准（参照）</td><td>{e(s.get('title',''))}</td><td>{e(s.get('code',''))}</td><td class='tiny'>{e(s.get('loc',''))}</td></tr>" for s in res['standards'])}
{''.join(f"<tr><td>COA</td><td>{e(c.get('label', c.get('batch_no')))}</td><td>{e(c.get('header',{}).get('report_no',''))}</td><td class='tiny'>文件 {e(c.get('file',''))}</td></tr>" for c in res['coas'])}
</table></div></div></section>"""


EXTR_FIELDS = [
    ("header", "product_name", "产品名称"), ("header", "grade", "产品等级"),
    ("header", "producer", "生产企业"), ("header", "batch_no", "生产批号"),
    ("header", "report_no", "证书编号"), ("header", "mfg_date", "生产日期"),
    ("header", "test_date", "检测日期"), ("header", "retest_date", "复检期至"),
    ("header", "test_standard", "检测依据"), ("header", "conclusion", "检验结论"),
]


def sec_extract(res):
    """文件抽取结果 + 人工确认态（确认/存疑/非本批）。"""
    cards = []
    for c in res["coas"]:
        h = c["header"]
        cells = []
        for _, key, lab in EXTR_FIELDS:
            v = h.get(key)
            miss = v in (None, "")
            if key == "batch_no" and c.get("linked_delivery_batch"):
                same = L.batch_key(v) == L.batch_key(c["linked_delivery_batch"])
                mark = "" if same else " ⚠"
            else:
                mark = ""
            cells.append(f'<div class="{"miss" if miss else ""}"><span>{e(lab)}</span>'
                         f'<span>{e(v) if not miss else "（缺失）"}{mark}</span></div>')
        n_items = len(c.get("items", []))
        n_meth = sum(1 for i in c.get("items", []) if i.get("method") not in (None, "", "—"))
        ridge = res["completeness"][c["batch_no"]]
        cid = re.sub(r"[^A-Za-z0-9]", "", c["batch_no"])
        cards.append(f"""<div style="margin-bottom:18px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap">
    <b style="font-size:14px">{e(c.get('label', c['batch_no']))}</b>
    <span class="tiny muted">文件：{e(c.get('file',''))} · 指标 {n_items} 项 · 带方法 {n_meth} 项 ·
      完整性 {ridge['score']} 分</span>
  </div>
  <div class="extr" data-coa="{e(c['batch_no'])}">{''.join(cells)}</div>
  <div class="toolbar" style="margin-top:8px">
    <span class="tiny muted">人工确认：</span>
    <button class="btn primary" onclick="confirmCoa('{cid}',this,'已确认')">✔ 数值已确认</button>
    <button class="btn" onclick="confirmCoa('{cid}',this,'存疑')">⚠ 数值存疑，需查原件</button>
    <button class="btn" onclick="confirmCoa('{cid}',this,'非本批')">✕ 非本批货物</button>
    <span class="tiny" id="cf-{cid}" style="color:var(--brand-2)"></span>
  </div>
  <details style="margin-top:2px"><summary class="tiny muted" style="cursor:pointer">
    展开 {n_items} 项指标抽取明细（原始写法 → 解析结构）</summary>
    <div class="tbl-wrap" style="margin-top:8px"><table><tr><th>COA 原始名称</th><th>原始值</th>
    <th>单位</th><th>方法</th><th>检出限</th><th>解析结构</th><th>原文位置</th></tr>
    {''.join(extr_item_rows(c))}
    </table></div></details>
</div>""")
    return f"""<section class="card"><h2><span class="n">1</span>文件抽取结果（请先确认关键数值）</h2>
<div class="lead">系统只做"读出来"，不做"猜出来"。识别不清的值标为缺失；批号与到货单不一致会打 ⚠。
请逐份确认后再看比对结论——抽取错了，后面全错。</div>
{''.join(cards)}</section>"""


def extr_item_rows(c):
    out = []
    for it in c.get("items", []):
        p = L.parse_value(it.get("value"), "ref")
        kind_cn = {"single": "单值", "max": "上限值（≤）", "min": "下限值（≥）", "range": "范围",
                   "nd": "未检出", "lod": "低于检出限", "text": "定性/描述", "unspecified": "未测/空"}.get(p["kind"], p["kind"])
        if p["kind"] in ("single",) and it.get("lod"):
            kind_cn += "（⚠ 疑为检出限，见比对表）"
        out.append(f"<tr><td>{e(it.get('name'))}</td><td class='num'>{e(it.get('value'))}</td>"
                   f"<td>{e(it.get('unit'))}</td><td class='tiny'>{e(it.get('method') or '—')}</td>"
                   f"<td class='tiny'>{e(it.get('lod') or '')}</td><td class='tiny'>{e(kind_cn)}</td>"
                   f"<td class='tiny muted'>{e(it.get('loc') or '')}</td></tr>")
    return out


def sec_compare(res):
    t = res["target_batch"]
    rows = res["results"][t]
    coa = next((c for c in res["coas"] if c.get("batch_no") == t), {})
    cnt = res["summary"][t]
    counts = "".join(
        f'<button class="fbtn f-{STATUS_CLS[s]}" data-st="{s}" onclick="filt(this,\'{s}\')">'
        f'{e(s)}<span class="cnt">{cnt.get(s, 0)}</span></button>'
        for s in L.STATUS_SET if cnt.get(s, 0) > 0 or s == L.ST_OK)
    body = "".join(item_row_main(r, i) for i, r in enumerate(rows))
    return f"""<section class="card" id="cmp"><h2><span class="n">2</span>逐项指标比对表
  <span class="tiny muted" style="font-weight:400">批次 {e(t)} · 规格 {e(coa.get('header',{}).get('test_standard',''))}</span></h2>
<div class="lead">点击任意一行展开 COA 原文 / 规格原文与定位、单位换算、可比性五维、偏离公式。
列中 <span class="lim">黄底</span> 为规格限值；判定只依据"数值 + 限值 + 方法 + 单位"四件事。</div>
<div class="toolbar">
  <button class="fbtn on" data-st="*" onclick="filt(this,'*')">全部<span class="cnt">{len(rows)}</span></button>
  {counts}
  <input class="search" placeholder="搜索指标名 / 方法 / 类别…" oninput="q(this.value)">
  <span class="tiny muted" id="shown"></span>
</div>
<div class="tbl-wrap"><table id="cmpTable">
<thead><tr>
  <th style="width:34px">#</th><th style="width:15%">指标</th><th style="width:11%">COA 实测</th>
  <th style="width:11%">规格限值</th><th style="width:9%">方法关系</th><th style="width:9%">判定</th>
  <th style="width:8%">严重度</th><th>判定理由 / 偏离</th><th style="width:9%">定位</th>
</tr></thead><tbody>{body}</tbody></table></div>
<div class="legend">
  <span>✓ 符合</span><span>✕ 不符合</span><span>— 规格未约定</span><span>? COA未检测</span>
  <span>≈ 无法判断（缺条件）</span>
  <span>行底色浅红 = 不符合</span>
</div></section>"""


def item_row_main(r, i):
    st = r["status"]
    cls = STATUS_CLS.get(st, "unknown")
    tr_cls = "item-row row-fail" if st == L.ST_FAIL else "item-row"
    dev = r["deviation"]
    reason = e(r["reason"])
    if st == L.ST_FAIL and dev.get("human"):
        reason = f'{e(dev["human"])} <span class="tiny muted">｜{e(r["reason"])}</span>'
    lim = r["spec_limit"] or "—"
    meth_rel = {"same": "一致", "equivalent": "等效", "different": "不同",
                "missing_coa": "COA缺方法", "missing_spec": "规格缺方法",
                "both_missing": "双方均缺"}.get(r["method_relation"], "—")
    mcls = "warn-txt" if r["method_relation"] == "different" else "muted"
    crit = '<span class="flag">关键</span>' if r["critical"] else ""
    return f"""<tr class="{tr_cls}" data-st="{e(st)}" data-key="{e(r['name_key'])}"
   data-txt="{e(r['name'] + ' ' + (r['method_coa'] or '') + ' ' + (r['method_spec'] or '') + ' ' + r['category'])}"
   onclick="toggleRow(this)">
  <td class="muted">{i+1}</td>
  <td class="name">{e(r['name'])}{crit}<div class="tiny muted">{e(r['category'])} · {e({'mandatory':'强制项','customer':'约定项'}.get(r['basis'],r['basis']))}</div></td>
  <td class="num">{e(r['coa_value'])}<div class="tiny muted">{e(r['coa_unit'])}</div></td>
  <td class="num"><span class="lim">{e(lim)}</span><div class="tiny muted">{e(r['spec_unit'])}</div></td>
  <td class="tiny {mcls}">{e(meth_rel)}</td>
  <td>{st_badge(st)}</td>
  <td>{sev_badge(r['severity'])}</td>
  <td class="tiny">{reason}</td>
  <td class="tiny"><a href="javascript:void(0)" onclick="event.stopPropagation();toggleRow(this.closest('tr'))">定位 ↗</a></td>
</tr>
<tr class="detail-row" style="display:none"><td colspan="9">{item_detail(r, i+1)}</td></tr>"""


def item_detail(r, no):
    coa_loc = (r["loc"] or {}).get("coa") or "（COA 未提供该项位置）"
    spec_loc = (r["loc"] or {}).get("spec") or "（规格文件未约定该项）"
    comp = "".join(
        f'<li><span class="tick {"y" if ok else "n"}">{"✓" if ok else "✕"}</span>'
        f'<span><b>{e(L.COMP_DIMS[k])}</b>{"：" + e(why) if why else ""}</span></li>'
        for k, ok, why in r["comparability"])
    notes = "".join(f'<div class="note-box">📌 {e(n)}</div>' for n in (r.get("notes") or []))
    dev = r["deviation"]
    devbox = ""
    if r["status"] == L.ST_FAIL:
        devbox = f"""<div style="margin-top:10px"><h4 style="color:var(--fail)">偏离程度（可复算）</h4>
<div class="formula">{e(dev.get('formula') or '—')}
{e(dev.get('mde_note') or '')}</div>
<div class="bar-track"><div class="bar-fill" style="width:{min(100, abs(dev.get('pct') or 0) * 2.2):.0f}%"></div></div>
<div class="tiny muted" style="margin-top:3px">条长 = |偏离%| × 2.2（100% 封顶），仅作视觉参照</div></div>"""
    adj = r.get("adjustment")
    if adj is not None and r["status"] == L.ST_FAIL:
        devbox += (f'<div class="tiny muted" style="margin-top:6px">相对调整量 |实测−限值| ÷ 限值 = '
                   f'{adj*100:.2f}%（百分比口径与上表一致，供换算后复核）</div>')
    inferred = ""
    if r.get("inferred_spec"):
        ins = r["inferred_spec"]
        inferred = (f'<div class="note-box">🏭 生产规格建议值：<b>{e(ins["limit_display"])} {e(ins["unit"])}</b>'
                    f'（{e(ins.get("basis",""))}；来源：{e(ins.get("source",""))}）<br>'
                    f'仅为提议，<b>不能作为验收依据</b>；若需纳入验收，须走合同补充约定。</div>')
    rep = ""
    if r.get("replicate"):
        rep = ('<div class="note-box">🔬 该指标 COA 给出多个方法结果：' +
               "；".join(f'{e(x.get("method",""))} → {e(x.get("value",""))}' for x in r["replicate"]) +
               "。与约定方法一致的那一个优先用于判定。</div>")
    return f"""<div class="detail">
  <div>
    <h4>原始位置对照</h4>
    <div class="src coa"><div class="who"><span>COA · {e(no)} 号指标</span>
      <span>{e(r['method_coa'] or '未标注方法')}</span></div>
      <div class="quote">{e(r['name'])} ＝ <b>{e(r['coa_value'])}</b> {e(r['coa_unit'])}
        {('（' + e(r['basis_coa']) + '）') if r['basis_coa'] and '到货' not in r['basis_coa'] else ''}</div>
      <div class="loc">📍 {e(coa_loc)}</div></div>
    <div class="src spec" style="margin-top:10px"><div class="who"><span>规格 · {e(r['spec_source'] or '未约定')}</span>
      <span>{e(r['method_spec'] or '未约定方法')}</span></div>
      <div class="quote">{e(r['name'])} 要求 <b>{e(r['spec_limit'] or '（未约定）')}</b> {e(r['spec_unit'])}
        {('（' + e(r['basis_spec']) + '）') if r['basis_spec'] and '到货' not in r['basis_spec'] else ''}</div>
      <div class="loc">📍 {e(spec_loc)}</div></div>
    {notes}{inferred}{rep}{devbox}
  </div>
  <div>
    <h4>判定与可比性</h4>
    <dl class="kv">
      <dt>判定结果</dt><dd>{st_badge(r['status'])} {sev_badge(r['severity'])}</dd>
      <dt>判定理由</dt><dd>{e(r['reason'])}</dd>
      <dt>COA 方法</dt><dd>{e(r['method_coa'] or '未标注')}</dd>
      <dt>约定方法</dt><dd>{e(r['method_spec'] or '未约定')}</dd>
      <dt>方法关系</dt><dd>{e({'same':'一致','equivalent':'不同但等效','different':'不同','missing_coa':'COA 缺方法','missing_spec':'规格缺方法','both_missing':'双方均缺'}.get(r['method_relation'], r['method_relation']))}</dd>
      <dt>COA 基准</dt><dd>{e(r['basis_coa'])}</dd>
      <dt>规格基准</dt><dd>{e(r['basis_spec'])}</dd>
    </dl>
    <h4 style="margin-top:12px">可比性五维（任一不满足即落"无法判断"）</h4>
    <ul class="comp-list">{comp}</ul>
  </div></div>"""


def sec_batches(res):
    """逐批次视图：多份 COA 同时在场时，一次性看全部批次的判定分布与差异。"""
    bs = res["batch_order"]
    if len(bs) < 2:
        return ""
    t = res["target_batch"]
    first = res["results"][bs[0]]
    head = "".join(
        f'<th style="text-align:center">{e(b)}<br><span class="tiny muted">'
        f'{"重点批次" if b == t else "对照批次"} · 完整性 {res["completeness"][b]["score"]}</span></th>'
        for b in bs)
    rows = []
    for i, r0 in enumerate(first):
        cells = []
        for b in bs:
            rs = res["results"][b]
            r = next((x for x in rs if x["name_key"] == r0["name_key"]), None)
            if not r:
                cells.append('<td style="text-align:center">—</td>')
                continue
            dev = ""
            if r["status"] == L.ST_FAIL and r["deviation"].get("pct") is not None:
                dev = f'<div class="tiny" style="color:var(--fail)">{r["deviation"]["pct"]:+.2f}%</div>'
            cells.append(f'<td style="text-align:center">{st_badge(r["status"])}'
                         f'<div class="tiny muted" style="font-family:var(--mono)">{e(r["coa_value"])} {e(r["coa_unit"])}</div>'
                         f'{dev}</td>')
        rows.append(f'<tr><td><b>{e(r0["name"])}</b></td>'
                    f'<td class="num"><span class="lim">{e(r0["spec_limit"] or "—")}</span> '
                    f'<span class="tiny muted">{e(r0["spec_unit"])}</span></td>{"".join(cells)}</tr>')
    srow = "".join(
        "<td style='text-align:center' class='tiny'>" + " ".join(
            f"<b style='color:var(--{ {'符合':'ok','不符合':'fail','COA未检测':'untested','无法判断':'unknown','规格未约定':'unspec'}[s] })'>{s} {res['summary'][b].get(s,0)}</b>"
            for s in L.STATUS_SET) + "</td>" for b in bs)
    return f"""<section class="card"><h2><span class="n">2b</span>多批次逐项对照（全部批次同表）</h2>
<div class="lead">同一张规格，横向比较各批次的判定与实测。每个单元格为"该批 COA 实测 + 判定"；
超限项同时给出批次内偏离%。注意：单位不同的批次已在引擎内统一换算，单元格仍显示 COA 原始单位。</div>
<div class="tbl-wrap"><table><tr><th style="width:16%">指标</th><th style="width:13%">规格限值</th>{head}</tr>
{''.join(rows)}
<tr style="background:#f8fafc;font-weight:700"><td>判定分布</td><td></td>{srow}</tr></table></div>
<div class="legend">{' '.join(st_badge(s) for s in L.STATUS_SET)}</div></section>"""


def sec_integrity(res):
    blocks = []
    for c in res["coas"]:
        b = c["batch_no"]
        comp = res["completeness"][b]
        sc = comp["score"]
        col = "#0f7b52" if sc >= 85 else ("#b45309" if sc >= 60 else "#b42318")
        issues = "".join(
            f'<div class="issue"><div>{sev_badge(i["level"])}</div><div class="body">'
            f'<div class="t">{e(i["field"])}</div><div class="d">{e(i["msg"])}</div>'
            f'<div class="a">{e(i["action"])}</div></div></div>'
            for i in comp["issues"]) or '<p class="tiny muted">未发现证书完整性缺陷。</p>'
        ring = (f'<div class="ring" style="background:conic-gradient({col} {sc*3.6:.0f}deg,#e8eef4 0)">'
                f'<div class="in" style="color:{col}">{sc}</div></div>')
        blocks.append(f"""<div class="grid2" style="margin-bottom:18px">
  <div><div class="score-ring">{ring}<div><b style="font-size:14px">{e(c.get('label', b))}</b>
    <div class="tiny muted">完整性得分 {sc} / 100　高 {comp['counts']['高']} · 中 {comp['counts']['中']} · 低 {comp['counts']['低']}</div>
    <div class="tiny muted">只评价"证书文件本身齐不齐"，不代表产品质量</div></div></div></div>
  <div>{issues}</div></div>""")
    return f"""<section class="card"><h2><span class="n">3</span>证书完整性检查</h2>
<div class="lead">先证"这份 COA 是这批发货的、且是完整出具的"，再谈指标。缺项本身不构成不合格，
但会让指标结论失去依据——例如无检出限，则"≤0.5 ppm"无法验证。</div>
{''.join(blocks)}</section>"""


def sec_methods(res):
    t = res["target_batch"]
    items = res["method_issues"][t]["items"]
    head = res["method_issues"][t].get("header_note")
    if not items:
        return (f"""<section class="card"><h2><span class="n">4</span>检测方法差异</h2>
<p class="muted tiny">批次 {e(t)} 的 COA 方法与合同/规格约定方法一致，无方法争议项。</p>
{f'<div class="note-box">{e(head)}</div>' if head else ''}</section>""")
    rows = "".join(
        f"<tr><td><b>{e(m['name'])}</b></td><td class='mono tiny'>{e(m['coa_method'] or '—')}</td>"
        f"<td class='mono tiny'>{e(m['spec_method'] or '—')}</td>"
        f"<td>{('<span class=\"sev sev-高\">不同</span>' if m['relation']=='different' else '<span class=\"sev sev-中\">'+e(m['label'])+'</span>')}</td>"
        f"<td class='tiny'>{e(m['coa_value'])} {e('')}</td><td class='tiny'>{e(m['spec_limit'])}</td>"
        f"<td class='tiny'>{e(m['impact'] or m['note'] or '—')}</td></tr>"
        for m in items)
    return f"""<section class="card"><h2><span class="n">4</span>检测方法差异与影响</h2>
<div class="lead">"同类指标"用不同方法测出来的数不能直接比。这张表只回答一件事：这个数是怎么测的，
和约定方法是不是同一个东西。</div>
{f'<div class="note-box">{e(head)}</div>' if head else ''}
<div class="tbl-wrap"><table><tr><th>指标</th><th>COA 方法</th><th>约定方法</th><th>关系</th>
<th>COA 实测</th><th>规格限值</th><th>对本批判断的影响</th></tr>{rows}</table></div></section>"""


# ------------------------------ 趋势 SVG ------------------------------
def trend_chart(t, w=430, h=178):
    pts = [s for s in t["series"] if s["base_value"] is not None]
    unit = t.get("unit") or ""
    if len(pts) < 2:
        return (f'<div class="chart-card"><h4>{e(t["name"])}</h4><div class="desc">仅 1 个有效批次，无法成趋势</div>'
                f'<div class="tiny muted" style="height:60px;display:grid;place-items:center">—</div></div>')
    ml, mr, mt, mb = 46, 12, 10, 26
    xs = list(range(len(pts)))
    vals = [p["base_value"] for p in pts]
    lim = t.get("limit_line")
    pad = list(vals) + ([lim] if lim is not None else [])
    lo, hi = min(pad), max(pad)
    span = (hi - lo) or (abs(hi) * 0.02 or 1)
    lo2, hi2 = lo - span * 0.30, hi + span * 0.30
    def X(i): return ml + (w - ml - mr) * (i / max(1, len(pts) - 1))
    def Y(v): return mt + (h - mt - mb) * (1 - (v - lo2) / (hi2 - lo2))
    grid = []
    for k in range(4):
        v = lo2 + (hi2 - lo2) * k / 3
        y = Y(v)
        grid.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{w-mr}" y2="{y:.1f}" stroke="#eef2f6"/>'
                    f'<text x="{ml-6}" y="{y+3.5:.1f}" font-size="9.5" fill="#94a3b8" text-anchor="end">{v:.4g}</text>')
    # 限值线
    limsvg = ""
    if lim is not None and lo2 <= lim <= hi2:
        y = Y(lim)
        limsvg = (f'<line x1="{ml}" y1="{y:.1f}" x2="{w-mr}" y2="{y:.1f}" stroke="#b42318" stroke-width="1.4" '
                  f'stroke-dasharray="5 3"/><text x="{w-mr-2}" y="{y-4:.1f}" font-size="9.5" fill="#b42318" '
                  f'text-anchor="end">规格限值 {lim:g}</text>')
    d = " ".join(f"{'M' if i==0 else 'L'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    area = d + f" L{X(len(vals)-1):.1f},{h-mb} L{X(0):.1f},{h-mb} Z"
    dots = []
    for i, p in enumerate(pts):
        oos = p.get("oos")
        col = "#b42318" if oos else ("#0b3d66" if p["is_target"] else "#155e91")
        r = 4.6 if (oos or p["is_target"]) else 3.4
        dots.append(f'<circle cx="{X(i):.1f}" cy="{Y(p["base_value"]):.1f}" r="{r}" fill="#fff" '
                    f'stroke="{col}" stroke-width="2.2"><title>{e(p["batch"])} {e(p["date"])}：'
                    f'{p["base_value"]:.4g} {e(unit)}</title></circle>')
        if oos or p["is_target"]:
            dots.append(f'<text x="{X(i):.1f}" y="{Y(p["base_value"])-9:.1f}" font-size="9.5" fill="{col}" '
                        f'text-anchor="middle" font-weight="700">{p["base_value"]:.4g}</text>')
    labels = "".join(f'<text x="{X(i):.1f}" y="{h-8}" font-size="8.8" fill="#94a3b8" text-anchor="middle">'
                     f'{e(p["batch"][-8:])}</text>' for i, p in enumerate(pts))
    conv = ""
    if t.get("conversions"):
        conv = f'<div class="tiny warn-txt" style="margin-top:4px">单位已归一：{e("；".join(t["conversions"]))}</div>'
    return f"""<div class="chart-card">
  <h4><span>{e(t["name"])}</span><span class="tiny muted">单位 {e(unit)}</span></h4>
  <div class="desc">{e(t["desc"])}</div>
  <svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img">
    {''.join(grid)}
    <path d="{area}" fill="url(#g1)" opacity=".55"/>
    <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#cfe3f2"/><stop offset="1" stop-color="#f5f9fc" stop-opacity="0"/>
    </linearGradient></defs>
    {limsvg}
    <path d="{d}" fill="none" stroke="#155e91" stroke-width="2" stroke-linejoin="round"/>
    {''.join(dots)}{labels}
  </svg>{conv}
</div>"""


def sec_trends(res):
    t = res["target_batch"]
    trends = [x for x in res["trends"][t] if x.get("n")]
    # 给趋势线补限值（按指标各自匹配，不按行序号）
    for x in trends:
        r = next((rr for rr in res["results"][t] if rr["name"] == x["name"]), None)
        if not r or not r["spec_limit"]:
            continue
        lv = L.parse_value(r["spec_limit"], "limit")
        if lv["kind"] in ("max", "min", "single"):
            x["limit_line"] = lv["value"]
        elif lv["kind"] == "range":
            x["limit_line"] = lv["range"][0]
        for s in x["series"]:
            if s["base_value"] is None:
                continue
            s["oos"] = False
            if lv["kind"] == "max" and s["base_value"] > lv["value"]:
                s["oos"] = True
            if lv["kind"] == "min" and s["base_value"] < lv["value"]:
                s["oos"] = True
            if lv["kind"] == "range" and not (lv["range"][0] <= s["base_value"] <= lv["range"][1]):
                s["oos"] = True
            s["is_target"] = s["batch"] == t
    charts = "".join(trend_chart(x) for x in trends)
    tbl_rows = "".join(
        f"<tr><td><b>{e(x['name'])}</b></td><td class='num'>{x['n']}</td>"
        f"<td class='num'>{x['mean']:.4g}</td><td class='num'>{x['min']:.4g} ~ {x['max']:.4g}</td>"
        f"<td class='num'>{g(x['sd'], 3)}</td>"
        f"<td>{e(x['direction'])}</td>"
        f"<td class='tiny'>{e('、'.join(f'{b}({v:g})' for b, v in x['oos']) or '无')}</td></tr>"
        for x in trends)
    return f"""<section class="card"><h2><span class="n">5</span>多批次指标变化趋势</h2>
<div class="lead">把本批放进历史序列里看，才知道是"偶发偏离"还是"趋势性劣化"。所有批次先统一到规格单位再比较；
红点 = 越过规格限值，深色点 = 本次重点批次。趋势只陈述事实，不推断原因。</div>
<div class="chart-grid">{charts}</div>
<div class="tbl-wrap" style="margin-top:14px"><table>
<tr><th>指标</th><th>批次数</th><th>均值</th><th>区间</th><th>标准差</th><th>方向</th><th>越限批次</th></tr>
{tbl_rows}</table></div></section>"""


def sec_objection(res):
    o = res["objections"]
    pts = "".join(
        f'<div class="opoint s-{e(p["severity"])}"><div class="top-line">'
        f'<span class="no">{p["no"]:02d}</span>{sev_badge(p["severity"])}'
        f'<span class="ttl">{e(p["title"])}</span><span class="cat">{e(p["category"])}</span></div>'
        f'<div class="f">📄 {e(p["facts"])}</div><div class="k">{e(p["ask"])}</div>'
        f'<div class="tiny muted" style="margin-top:3px">依据：' +
        "；".join(f'{e(x["doc"])}{(" · " + e(x["loc"])) if x.get("loc") else ""}' for x in p["evidence"]) +
        "</div></div>"
        for p in o["points"]) or '<p class="tiny muted">本批次未发现需要向供应商提出的异议事项。</p>'
    tones = "".join(
        f'<button class="fbtn {"on" if k == o["tone"] else ""}" data-tone="{k}" onclick="tone(this)">'
        f'{e(TONE_LABELS[k])}</button>'
        for k in ("formal", "firm", "soft"))
    return f"""<section class="card" id="obj"><h2><span class="n">6</span>质量异议要点与函件草稿</h2>
<div class="lead">每条要点都必须能指回一条原始数据或一个文件位置，否则不进函件——这是异议能不能站住的关键。
草稿由数据自动拼装，发之前请人工过一遍语气与收件人。</div>
<div class="grid2" style="align-items:start">
  <div><h4 style="font-size:13.5px;margin-bottom:8px">异议要点清单
    <span class="tiny muted">高 {o['counts']['高']} · 中 {o['counts']['中']} · 低 {o['counts']['低']}</span></h4>
    {pts}</div>
  <div><h4 style="font-size:13.5px;margin-bottom:8px">函件草稿</h4>
    <div class="tone-sel">{tones}</div>
    <div class="tone-sel" style="margin-top:-4px">
      <button class="btn primary" onclick="copyMsg()">📋 复制全文</button>
      <button class="btn" onclick="dlMsg()">⬇ 下载 .txt</button>
      <button class="btn" onclick="window.print()">🖨 打印 / 存 PDF</button>
    </div>
    <div class="msg" id="msgBox" data-tone="{e(o['tone'])}">{e(res['drafts'][o['tone']])}</div>
    <div class="tiny muted" style="margin-top:6px">
      语气说明：{e(o['tone_desc'])}</div>
  </div></div></section>"""


def sec_alerts(res):
    if not res["alerts"]:
        return ""
    rows = "".join(f'<div class="issue"><div>{sev_badge(a["level"])}</div>'
                   f'<div class="body"><div class="d">{e(a["text"])}</div></div></div>' for a in res["alerts"])
    return f'<section class="card"><h2><span class="n">!</span>重点提示</h2>{rows}</section>'


def sec_next(res):
    k = res["kpis"]
    asks = []
    if k["fail"]:
        asks.append(f"对 {k['fail']} 项超限指标要求复检（约定方法）或书面技术说明")
    if k["untested"]:
        asks.append(f"补测 {k['untested']} 项规格已约定但 COA 缺失的指标")
    if k["unknown"]:
        asks.append(f"对 {k['unknown']} 项'无法判断'指标补充检出限 / 方法 / 单位说明后重新核对")
    if res["completeness"][res["target_batch"]]["counts"]["高"]:
        asks.append("索取补全批号、结论、方法的正式 COA 原件（带防伪码与签章）")
    if k["unspec"]:
        asks.append(f"{k['unspec']} 项规格未约定的指标，如需纳入验收，走合同补充约定")
    items = "".join(f"<li>{e(a)}</li>" for a in asks) or "<li>未发现需要跟进的事项</li>"
    return f"""<section class="card"><h2><span class="n">7</span>后续动作建议（仅限主张与取证，不含收货决定）</h2>
<div class="grid2"><div><ol style="margin:0;padding-left:20px;font-size:13.2px;line-height:2">{items}</ol></div>
<div class="disclaimer"><b>本报告不作收货决定。</b>它只回答三个问题：哪些指标符合、哪些偏离、哪些因条件缺失无法判断，
以及证书本身是否完整。是否接收、是否让步接收、是否退换货，需要采购、质量、生产与商务按合同条款共同决策；
本报告可作为该决策的事实底稿。<br><br>
<b>另外两点提醒：</b>① 模拟数据不得用于任何真实索赔；② 若原始扫描件数值/小数点/单位看不清，
必须回到原件人工确认，<b>不得以本报告的识读结果替代</b>。</div></div></section>"""


# ======================================================================================
# 脚本
# ======================================================================================
def scripts(res):
    drafts = json.dumps(res["drafts"], ensure_ascii=False)
    return f"""
<script>
const DRAFTS = {drafts};
const TONE_NAME = {{"formal":"正式 · 质量异议函","firm":"强硬 · 索赔前置","soft":"沟通 · 供应商友好版"}};
let curTone = document.getElementById('obj') ? (document.getElementById('msgBox')?.dataset.tone || 'formal') : 'formal';

function toggleRow(tr){{
  const nx = tr.nextElementSibling;
  if(!nx || !nx.classList.contains('detail-row')) return;
  const open = nx.style.display !== 'none';
  nx.style.display = open ? 'none' : 'table-row';
  tr.classList.toggle('expanded', !open);
}}
let _st = '*', _q = '';
function applyFilter(){{
  const t = document.getElementById('cmpTable'); if(!t) return;
  const rows = t.querySelectorAll('tbody tr.item-row');
  let shown = 0;
  rows.forEach(r=>{{
    const okSt = (_st==='*' || r.dataset.st===_st);
    const okQ = !_q || (r.dataset.txt||'').toLowerCase().includes(_q);
    const ok = okSt && okQ;
    r.style.display = ok ? '' : 'none';
    const d = r.nextElementSibling;
    if(d && d.classList.contains('detail-row') && !ok) {{ d.style.display='none'; r.classList.remove('expanded'); }}
    if(ok) shown++;
  }});
  const el = document.getElementById('shown');
  if(el) el.textContent = `显示 ${{shown}} / ${{rows.length}} 项`;
}}
function filt(btn, st){{
  document.querySelectorAll('.toolbar .fbtn[data-st]').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on'); _st = st; applyFilter();
}}
function q(v){{ _q = (v||'').trim().toLowerCase(); applyFilter(); }}
function confirmCoa(id, btn, val){{
  const box = document.getElementById('cf-' + id);
  if(box) box.textContent = '当前状态：' + val + '（' + new Date().toLocaleTimeString() + '）';
  btn.parentElement.querySelectorAll('.btn').forEach(b=>b.style.borderColor='');
  btn.style.borderColor = '#0b3d66'; btn.style.boxShadow='0 0 0 2px #bfd8ea';
  try{{ localStorage.setItem('coa-confirm-'+id, val); }}catch(e){{}}
}}
function tone(btn){{
  document.querySelectorAll('[data-tone]').forEach(b=>{{ if(b.tagName==='BUTTON') b.classList.remove('on'); }});
  btn.classList.add('on');
  curTone = btn.dataset.tone;
  const box = document.getElementById('msgBox');
  if(box){{ box.textContent = DRAFTS[curTone]; box.dataset.tone = curTone; }}
}}
function copyMsg(){{
  const box = document.getElementById('msgBox');
  navigator.clipboard?.writeText(box.textContent).then(
    ()=>{{ const o=box.style.outline; box.style.outline='2px solid #4cc38a';
           setTimeout(()=>box.style.outline=o, 700); }},
    ()=>{{ const r=document.createRange(); r.selectNodeContents(box);
           const s=getSelection(); s.removeAllRanges(); s.addRange(r); document.execCommand('copy'); }});
}}
function dlMsg(){{
  const box = document.getElementById('msgBox');
  const blob = new Blob([box.textContent], {{type:'text/plain;charset=utf-8'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '质量异议函_' + curTone + '.txt';
  a.click(); setTimeout(()=>URL.revokeObjectURL(a.href), 2000);
}}
document.addEventListener('DOMContentLoaded', ()=>{{
  applyFilter();
  // 顶部导航高亮
  const secs = [...document.querySelectorAll('section[id], [data-nav]')];
  const links = [...document.querySelectorAll('.top nav a')];
  const io = new IntersectionObserver(es=>{{
    es.forEach(en=>{{ if(en.isIntersecting){{
      links.forEach(l=>l.classList.toggle('on', l.getAttribute('href') === '#' + en.target.id));
    }}}});}}, {{rootMargin:'-45% 0px -50% 0px'}});
  secs.forEach(s=>io.observe(s));
}});
</script>"""


NAV = [("scope", "范围与依据"), ("extr", "抽取确认"), ("cmp", "逐项比对"), ("batch", "多批次"),
       ("integ", "证书完整性"), ("meth", "方法差异"), ("trend", "批次趋势"), ("obj", "异议与函件")]


def render(data, out_path):
    res = engine.run(data)
    m = res["meta"]
    nav = "".join(f'<a href="#{i}">{t}</a>' for i, t in NAV)
    body = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(m.get('title'))}｜COA × 规格核对报告</title>
<style>{css()}</style></head><body>
<div class="top"><div class="top-in">
  <div class="brand"><span class="dot"></span>COA × 规格核对</div>
  <nav>{nav}</nav>
  <div class="meta"><span>基准日 {e(m.get('as_of',''))}</span><span>批次 {e(res['kpis']['target_batch'])}</span>
  <span>{e(res['product']['name'])}</span></div>
</div></div>
<div class="wrap">
{sec_hero(res)}
{sec_kpis(res)}
<div data-nav id="scope">{sec_scope(res)}</div>
<div data-nav id="extr">{sec_extract(res)}</div>
{sec_compare(res)}
<div data-nav id="batch">{sec_batches(res)}</div>
<div data-nav id="integ">{sec_integrity(res)}</div>
<div data-nav id="meth">{sec_methods(res)}</div>
<div data-nav id="trend">{sec_trends(res)}</div>
{sec_alerts(res)}
{sec_objection(res)}
{sec_next(res)}
<div class="foot">
  本报告由 chem-coa-spec-check 引擎自动生成 · 数据源 {e(os.path.basename(out_path).replace('.html','.xlsx'))} ·
  所有判定可回溯到原始取值与限值 · 未作任何收货/退货结论
</div></div>
{scripts(res)}
</body></html>"""
    # 让 section id 与导航一致
    body = body.replace('<section class="card" id="cmp">', '<section class="card" id="cmp">')
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)
    return res


def main():
    if len(sys.argv) < 3:
        print("usage: render_html.py data.json out.html")
        raise SystemExit(2)
    data = engine.load(sys.argv[1])
    res = render(data, sys.argv[2])
    print("html ->", sys.argv[2], "| items", res["kpis"]["total"])


if __name__ == "__main__":
    main()
