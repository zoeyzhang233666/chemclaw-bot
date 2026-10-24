# -*- coding: utf-8 -*-
"""Generic builders: turn pipeline output into (a) an Excel workbook and (b) an interactive
HTML report. Product-agnostic — supply a `narrative` dict describing THIS study.

    from build_outputs import build_workbook, build_report
    build_workbook("output", narrative, "研究_数据工作簿.xlsx")
    build_report("output", narrative, "研究报告.html")

`narrative` keys (all optional except title):
  title, subtitle, source_rows (list of [数据, 口径, 频率/时点, 覆盖, 说明]),
  findings_ok (list), findings_ng (list), industry_notes (list),
  limits (list), one_line, group_labels (dict)
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(color="FFFFFF", bold=True, size=10, name="等线")
TITLE_FONT = Font(bold=True, size=13, color="1F3864", name="等线")
SUB_FONT = Font(size=9, color="595959", name="等线")
BODY = Font(size=10, name="等线")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _load(out, name):
    p = os.path.join(out, "res_%s.csv" % name)
    return pd.read_csv(p, encoding="utf-8-sig") if os.path.exists(p) else pd.DataFrame()


def _rename(df, mapping):
    keep = {k: v for k, v in mapping.items() if k in df.columns}
    return df[list(keep)].rename(columns=keep) if keep else df


# --------------------------------------------------------------------- Excel


def _style_header(ws, row, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def _write_df(ws, df, start_row=1, freeze=True, numfmt=None, title=None, subtitle=None):
    r = start_row
    if title:
        ws.cell(row=r, column=1, value=title).font = TITLE_FONT
        r += 1
    if subtitle:
        ws.cell(row=r, column=1, value=subtitle).font = SUB_FONT
        r += 1
    hdr = r
    for j, col in enumerate(df.columns, start=1):
        ws.cell(row=hdr, column=j, value=str(col))
    _style_header(ws, hdr, len(df.columns))
    for i, (_, row) in enumerate(df.iterrows(), start=hdr + 1):
        for j, col in enumerate(df.columns, start=1):
            v = row[col]
            if isinstance(v, np.integer):
                v = int(v)
            elif isinstance(v, np.floating):
                v = None if not np.isfinite(v) else float(v)
            elif isinstance(v, float) and not np.isfinite(v):
                v = None
            cell = ws.cell(row=i, column=j, value=v)
            cell.font = BODY
            cell.border = BORDER
            if numfmt and col in numfmt:
                cell.number_format = numfmt[col]
            if isinstance(v, float):
                cell.alignment = Alignment(horizontal="right")
    if freeze:
        ws.freeze_panes = ws.cell(row=hdr + 1, column=1)
    ws.auto_filter.ref = "A%d:%s%d" % (hdr, get_column_letter(len(df.columns)), hdr + len(df))
    for j, col in enumerate(df.columns, start=1):
        ws.column_dimensions[get_column_letter(j)].width = min(max(10, len(str(col)) * 1.7 + 2), 30)
    return hdr


def build_workbook(out_dir, narrative, path):
    wb = Workbook()
    wb.remove(wb.active)
    panel = pd.read_csv(os.path.join(out_dir, "panel_weekly.csv"), encoding="utf-8-sig")
    pooled = _load(out_dir, "pooled")
    summ = {}
    sp = os.path.join(out_dir, "summary.json")
    if os.path.exists(sp):
        summ = json.load(open(sp, encoding="utf-8"))

    # 0 summary
    ws = wb.create_sheet("0_研究摘要")
    ws["A1"] = narrative.get("title", "库存—价格关系研究")
    ws["A1"].font = Font(bold=True, size=16, color="1F3864", name="等线")
    ws["A2"] = "样本期 %s 至 %s（%s 周）" % (summ.get("start"), summ.get("end"), summ.get("n_weeks"))
    ws["A2"].font = SUB_FONT
    r = 4
    for k, v in (narrative.get("summary_rows") or []):
        ws.cell(row=r, column=1, value=k).font = Font(bold=True, size=10, name="等线")
        c = ws.cell(row=r, column=2, value=v)
        c.font = BODY
        c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 110

    # 1 raw inventory
    ws = wb.create_sheet("1_原始库存数据")
    tab = panel[["week", "asof", "pub_ts", "total", "wow_chg"]].copy()
    tab.columns = ["周(归位)", "统计截止日", "真实公布时间", "库存", "较上期"]
    _write_df(ws, tab, title="① 原始库存 — 统计截止日与真实公布时间必须分开记录",
              numfmt={"库存": "0.00", "较上期": "+0.00;-0.00"})

    # 2 factors
    ws = wb.create_sheet("2_因子构造")
    cols = [c for c in ["week", "pub_ts", "total", "lvl_pct", "lvl_z", "wow_chg", "wow_pct",
                        "yoy", "w4_chg", "run_len", "ly"] if c in panel.columns]
    tab = panel[cols].copy()
    tab.columns = ["周", "公布时间", "库存", "F1分位", "F1b_z", "F3周度变化", "F4变化率",
                   "F5同比", "F6四周累计", "连续状态(±周数)", "去年同期"][:len(cols)]
    _write_df(ws, tab, title="② 因子构造 — 分位/标准化均为 expanding（只用 t 之前已公布样本）",
              numfmt={"F1分位": "0.000", "F1b_z": "0.00", "F3周度变化": "+0.00;-0.00",
                      "F4变化率": "0.00%", "F5同比": "0.0%", "F6四周累计": "+0.00;-0.00"})

    # 3 forward returns
    ws = wb.create_sheet("3_未来收益")
    hs = sorted({int(c.split("_")[-1]) for c in panel.columns if c.startswith("fwd_spot_")})
    base = [c for c in ["week", "px_base_date", "spot0", "fut0", "basis0"] if c in panel.columns]
    tab = panel[base].copy()
    tab.columns = ["周", "基期日期(公布后首个交易日)", "基期现货", "基期期货", "基差"][:len(base)]
    for h in hs:
        for src, dst in (("fwd_spot", "现货变化%dW"), ("fwd_fut", "期货收益%dW"), ("fwd_basis", "基差变化%dW")):
            c = "%s_%d" % (src, h)
            if c in panel.columns:
                tab[dst % h] = panel[c]
    _write_df(ws, tab, title="③ 未来收益 — 基期严格晚于公布时间，避免未来函数",
              numfmt={c: ("0.00%" if "变化" in c or "收益" in c else "+0.00;-0.00")
                      for c in tab.columns if "W" in str(c)})

    # 4 groups
    ws = wb.create_sheet("4_分组统计")
    gl, gw, gr = _load(out_dir, "groups_level"), _load(out_dir, "groups_wow"), _load(out_dir, "groups_run")
    parts = []
    for df, dim in ((gl, "水平分位"), (gw, "周度变化"), (gr, "连续状态")):
        if len(df):
            d = df.copy()
            d["分组维度"] = dim
            parts.append(d)
    if parts:
        allg = pd.concat(parts, ignore_index=True)
        gcols = ["horizon_w", "target", "分组维度", "group", "n", "mean", "median", "std",
                 "p25", "p75", "ci_lo", "ci_hi", "hit_up", "p_welch"]
        allg = _rename(allg, {c: c for c in gcols})
        allg.columns = ["窗口(周)", "目标", "分组维度", "分组", "有效样本", "均值", "中位数", "标准差",
                        "P25", "P75", "CI下限", "CI上限", "上涨占比", "与其余组p"][:len(allg.columns)]
        _write_df(ws, allg, title="④ 分组统计 — 样本数 / 均值 / 中位数 / 分布 / bootstrap 95% 置信区间",
                  numfmt={"均值": "0.000", "中位数": "0.000", "标准差": "0.000", "P25": "0.000",
                          "P75": "0.000", "CI下限": "0.000", "CI上限": "0.000",
                          "上涨占比": "0.0%", "与其余组p": "0.0000"})

    # 5 sample counts
    ws = wb.create_sheet("5_样本数量")
    p = panel.copy()
    p["yr"] = pd.to_datetime(p["week"]).dt.year
    cnt = p.groupby("yr").agg(周数=("week", "size")).reset_index()
    cnt.columns = ["年份", "周数"]
    for h in hs:
        c = "fwd_spot_%d" % h
        if c in p:
            cnt["有%dW结果" % h] = p.groupby("yr")[c].apply(lambda s: int(s.notna().sum())).values
    if "run_len" in p:
        cnt["连续去库周数"] = p.groupby("yr")["run_len"].apply(lambda s: int((s <= -2).sum())).values
        cnt["连续累库周数"] = p.groupby("yr")["run_len"].apply(lambda s: int((s >= 2).sum())).values
    hdr = _write_df(ws, cnt, title="⑤ 样本数量 — 分年度覆盖",
                    subtitle="名义样本数 ≠ 独立观测数：窗口重叠见下表")
    ov = pd.DataFrame({"窗口(周)": hs,
                       "名义周数": [len(p) - h + 1 for h in hs],
                       "折算独立观测": [round(len(p) / h, 1) for h in hs]})
    _write_df(ws, ov, start_row=hdr + 3 + len(cnt), freeze=False,
              numfmt={"折算独立观测": "0.0"})

    # 6 yearly
    ws = wb.create_sheet("6_分年度结果")
    yr = _load(out_dir, "yearly")
    if len(yr):
        _write_df(ws, yr.rename(columns={
            "year": "年份", "horizon_w": "窗口(周)", "target": "目标", "n_weeks": "周数",
            "rho_level": "水平ρ", "mean_high": "高库存组均值", "n_high": "高库存n",
            "mean_low": "低库存组均值", "n_low": "低库存n", "spread": "高低差",
            "rho_wow": "周度变化ρ"}),
            title="⑥ 分年度结果 — 看方向是否一致，是否存在反向年份",
            numfmt={"水平ρ": "0.000", "高库存组均值": "0.000", "低库存组均值": "0.000",
                    "高低差": "0.000", "周度变化ρ": "0.000"})

    # 7 significance
    ws = wb.create_sheet("7_显著性检验")
    if len(pooled):
        _write_df(ws, pooled.rename(columns={
            "horizon_w": "窗口(周)", "target": "目标", "factor": "因子", "factor_code": "因子代码",
            "n_weeks": "有效周数", "spearman_rho": "Spearman ρ", "spearman_p": "p(原始)",
            "slope_per_unit": "斜率", "hac_se": "HAC标准误", "hac_t": "HAC t", "hac_p": "HAC p",
            "eff_n": "折算独立观测", "q_bh": "BH q", "sig_raw": "名义显著5%", "sig_bh": "BH显著5%"}),
            title="⑦ 显著性检验 — 全部因子×目标×窗口，含 BH-FDR",
            subtitle="原始 p 未考虑重叠窗口；HAC 带宽=窗口-1；BH q 为全部检验同时校正",
            numfmt={"Spearman ρ": "0.000", "p(原始)": "0.0000", "斜率": "0.0000",
                    "HAC标准误": "0.0000", "HAC t": "0.00", "HAC p": "0.0000", "BH q": "0.0000"})

    ws = wb.create_sheet("7b_安慰剂与控制")
    pl = _load(out_dir, "placebo")
    if len(pl):
        _write_df(ws, pl.rename(columns={"group": "分组", "horizon_w": "窗口(周)", "target": "结果变量",
                                         "diff": "组间均值差", "placebo_p": "年度分层置换p",
                                         "n_in": "组内样本"}),
                  title="⑦b 年度分层安慰剂 — 自然年内循环平移分组标签",
                  subtitle="保留季节性与趋势、破坏因子与收益的对齐；这是库存与价格同具季节性时的正确零假设",
                  numfmt={"组间均值差": "0.0000", "年度分层置换p": "0.0000"})
    ctrl = _load(out_dir, "control")
    if len(ctrl):
        _write_df(ws, ctrl.rename(columns={"h": "窗口", "beta_wow_pct": "周度变化系数", "t_wow_pct": "t1",
                                           "beta_basis_rate": "基差率系数", "t_basis_rate": "t2", "n": "n"}),
                  start_row=len(pl) + 6, freeze=False, title="控制同期基差水平后的回归",
                  numfmt={"周度变化系数": "0.0000", "t1": "0.00", "基差率系数": "0.0000", "t2": "0.00"})

    # 8 robustness
    ws = wb.create_sheet("8_稳健性检验")
    sb = _load(out_dir, "subsample")
    if len(sb):
        _write_df(ws, sb.rename(columns={"horizon_w": "窗口(周)", "target": "目标", "sample": "样本划分",
                                         "n": "周数", "rho_level": "水平ρ", "p_level": "水平p",
                                         "rho_wow": "周度变化ρ", "p_wow": "周度变化p"}),
                  title="⑧ 稳健性 — 非重叠子样本 / 样本内 vs 样本外",
                  numfmt={"水平ρ": "0.000", "水平p": "0.0000", "周度变化ρ": "0.000", "周度变化p": "0.0000"})
    rg = _load(out_dir, "regime")
    if len(rg):
        _write_df(ws, rg.rename(columns={"horizon_w": "窗口(周)", "target": "目标", "regime": "市场结构",
                                         "n": "周数", "rho_level": "水平ρ", "p_level": "水平p",
                                         "rho_wow": "周度变化ρ", "p_wow": "周度变化p"}),
                  start_row=len(sb) + 6, freeze=False, title="按基差升贴水 regime 分层",
                  numfmt={"水平ρ": "0.000", "水平p": "0.0000", "周度变化ρ": "0.000", "周度变化p": "0.0000"})

    # 9 notes
    ws = wb.create_sheet("9_口径与数据说明")
    ws["A1"] = "口径与数据说明"
    ws["A1"].font = Font(bold=True, size=14, color="1F3864", name="等线")
    r = 3
    for sec, items in (narrative.get("notes_sections") or {}).items():
        ws.cell(row=r, column=1, value=sec).font = Font(bold=True, size=11, color="1F3864", name="等线")
        r += 1
        for k, v in items:
            ws.cell(row=r, column=1, value=k).font = Font(bold=True, size=10, name="等线")
            c = ws.cell(row=r, column=2, value=v)
            c.font = BODY
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[r].height = 30
            r += 1
        r += 1
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 108

    wb.save(path)
    return path


# --------------------------------------------------------------------- HTML

HTML_SHELL = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>__TITLE__</title><style>
:root{--bg:#0b1220;--panel:#121c2e;--panel2:#16233a;--line:#22334f;--line2:#2c4162;--ink:#e8eef8;
--ink2:#a7b7cf;--ink3:#71869f;--acc:#4da3ff;--good:#38d9a9;--bad:#ff6b6b;--warn:#ffb454;--pur:#a78bfa}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#0a101c,#0b1220 420px);color:var(--ink);
font:14px/1.62 "Microsoft YaHei","PingFang SC","Segoe UI",system-ui,sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:0 26px 90px}
header.hero{padding:52px 0 28px;border-bottom:1px solid var(--line)}
.eyebrow{font-size:12px;letter-spacing:.22em;color:var(--acc);text-transform:uppercase;font-weight:700}
h1{font-size:32px;line-height:1.28;margin:14px 0 10px;font-weight:800}
.lede{color:var(--ink2);font-size:15px;max-width:880px}
.meta{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.chip{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:12px;color:var(--ink2)}
.chip b{color:var(--ink)}
nav.toc{position:sticky;top:0;z-index:50;background:rgba(11,18,32,.94);backdrop-filter:blur(10px);
border-bottom:1px solid var(--line);padding:0 26px;margin:0 -26px}
nav.toc ol{display:flex;gap:4px;overflow-x:auto;list-style:none;margin:0;padding:10px 0}
nav.toc a{color:var(--ink3);text-decoration:none;font-size:12.5px;padding:6px 11px;border-radius:7px;white-space:nowrap}
nav.toc a:hover{color:var(--ink);background:var(--panel)}
section{padding:42px 0 8px;border-bottom:1px solid var(--line)}
h2{font-size:21px;margin:0 0 6px;display:flex;gap:12px;align-items:baseline}
h2 .no{color:var(--acc);font-size:13px;letter-spacing:.12em}
h3{font-size:15px;margin:26px 0 10px}p{color:var(--ink2);margin:10px 0}
.sub{color:var(--ink3);font-size:12.5px;margin:4px 0 16px}
.grid{display:grid;gap:16px}.g2{grid-template-columns:repeat(2,1fr)}.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:900px){.g2,.g3,.g4{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}
.card h4{margin:0 0 4px;font-size:13px;color:var(--ink2)}
.kpi{font-size:29px;font-weight:800;margin:6px 0 2px}.cap{font-size:11.5px;color:var(--ink3);margin-top:6px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:12px 0}
th{background:var(--panel2);color:var(--ink2);text-align:right;padding:9px 10px;border-bottom:1px solid var(--line2);
white-space:nowrap;font-size:11.5px}th:first-child,td:first-child{text-align:left}
td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}
tr:hover td{background:rgba(77,163,255,.06)}
.sig{color:var(--good);font-weight:700}.nsig{color:var(--ink3)}.pos{color:var(--good)}.neg{color:var(--bad)}
.tag{display:inline-block;padding:2px 8px;border-radius:5px;font-size:10.5px;font-weight:700}
.tag.p{background:rgba(56,217,169,.16);color:var(--good)}.tag.w{background:rgba(255,180,84,.15);color:var(--warn)}
.ctl{display:flex;flex-wrap:wrap;gap:16px;align-items:center;background:var(--panel2);border:1px solid var(--line);
border-radius:12px;padding:13px 16px;margin:16px 0}
.ctl label{font-size:12px;color:var(--ink2);font-weight:600;display:flex;gap:7px;align-items:center}
select{background:#0d1626;color:var(--ink);border:1px solid var(--line2);border-radius:7px;padding:6px 9px;font-size:12.5px}
.seg{display:inline-flex;background:#0d1626;border:1px solid var(--line2);border-radius:8px;overflow:hidden}
.seg button{background:none;border:0;color:var(--ink3);padding:7px 14px;font-size:12.5px;cursor:pointer;font-weight:600}
.seg button.on{background:var(--acc);color:#06101f}
.chart{width:100%;height:auto;display:block}
.tip{position:fixed;pointer-events:none;background:#060d19;border:1px solid var(--line2);border-radius:9px;
padding:9px 11px;font-size:12px;box-shadow:0 10px 30px rgba(0,0,0,.6);opacity:0;transition:opacity .1s;z-index:999;max-width:300px}
.note{border-left:3px solid var(--acc);background:rgba(77,163,255,.07);padding:12px 16px;border-radius:0 9px 9px 0;margin:16px 0}
.note.warn{border-color:var(--warn);background:rgba(255,180,84,.07)}
.note.bad{border-color:var(--bad);background:rgba(255,107,107,.07)}
.note.good{border-color:var(--good);background:rgba(56,217,169,.07)}
ul.tight{margin:8px 0;padding-left:20px;color:var(--ink2)}ul.tight li{margin:5px 0}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--ink3);margin:8px 0 0}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
footer{padding:36px 0;color:var(--ink3);font-size:12px;text-align:center}
</style></head><body><div class="wrap">
<header class="hero"><div class="eyebrow">Inventory–Price Study</div>
<h1>__TITLE__</h1><p class="lede">__LEDE__</p>
<div class="meta">__CHIPS__</div></header>
<nav class="toc"><ol>__TOC__</ol></nav>
__BODY__
<footer>__FOOTER__</footer></div>
<div class="tip" id="tip"></div>
<script>const D = __DATA__;
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const fmt=(v,n=2)=>(v===null||v===undefined||Number.isNaN(v))?'—':Number(v).toFixed(n);
const pct=v=>(v===null||v===undefined||Number.isNaN(v))?'—':(v>=0?'+':'')+Number(v).toFixed(2)+'%';
const cls=v=>(v>0?'pos':(v<0?'neg':''));
const pfmt=p=>(p===null||p===undefined||Number.isNaN(p))?'—':'<span class="'+(p<0.05?'sig':'nsig')+'">'+(p<0.001?'&lt;0.001':p.toFixed(4))+'</span>';
const tip=$('#tip');
function showTip(e,h){tip.innerHTML=h;tip.style.opacity=1;
 tip.style.left=Math.min(e.clientX+14,window.innerWidth-310)+'px';tip.style.top=(e.clientY+14)+'px';}
function hideTip(){tip.style.opacity=0;}
__JS__
</script></body></html>"""

CHART_JS = r"""
let OV={win:'all',px:'spot'};
function drawOverview(){
  const S=D.series, d=OV.win==='all'?S:S.filter(r=>r.w.startsWith(OV.win));
  const svg=$('#ov-svg');if(!svg)return;const W=1180,H=330,L=56,R=64,T=18,B=40,iw=W-L-R,ih=H-T-B;
  const invs=d.map(r=>r.inv),pxs=d.map(r=>r[OV.px]);
  const i0=Math.min(...invs),i1=Math.max(...invs),p0=Math.min(...pxs),p1=Math.max(...pxs);
  const X=i=>L+i*iw/Math.max(d.length-1,1),Yi=v=>T+ih-(v-i0)/((i1-i0)||1)*ih,Yp=v=>T+ih-(v-p0)/((p1-p0)||1)*ih;
  let s='';
  for(let g=0;g<=4;g++){const y=T+ih*g/4;
    s+=`<line x1="${L}" y1="${y}" x2="${L+iw}" y2="${y}" stroke="#1b2941"/>`;
    s+=`<text x="${L-8}" y="${y+4}" fill="#71869f" font-size="10" text-anchor="end">${fmt(i1-(i1-i0)*g/4,0)}</text>`;
    s+=`<text x="${L+iw+8}" y="${y+4}" fill="#8a6a3a" font-size="10">${fmt(p1-(p1-p0)*g/4,0)}</text>`;}
  d.forEach((r,i)=>{if(r.run<=-2)s+=`<rect x="${X(i)-iw/(d.length*2)}" y="${T}" width="${iw/d.length}" height="${ih}" fill="rgba(255,107,107,.10)"/>`;});
  s+='<polyline fill="none" stroke="#ffb454" stroke-width="1.6" points="'+d.map((r,i)=>X(i)+','+Yp(r[OV.px])).join(' ')+'"/>';
  s+='<polyline fill="none" stroke="#4da3ff" stroke-width="2.2" points="'+d.map((r,i)=>X(i)+','+Yi(r.inv)).join(' ')+'"/>';
  const st=Math.ceil(d.length/9);
  d.forEach((r,i)=>{if(i%st===0)s+=`<text x="${X(i)}" y="${H-14}" fill="#71869f" font-size="9.5" text-anchor="middle">${r.w.slice(2,7)}</text>`;});
  d.forEach((r,i)=>{s+=`<rect x="${X(i)-iw/(d.length*2)}" y="${T}" width="${iw/d.length}" height="${ih}" fill="transparent" data-i="${i}"/>`;});
  svg.innerHTML=s;
  svg.querySelectorAll('rect[data-i]').forEach(el=>{
    el.addEventListener('mousemove',e=>{const r=d[+el.dataset.i];
      showTip(e,`<b>${r.w}</b>　公布 ${r.pub||''}<br>库存 ${fmt(r.inv,2)} 万吨（${r.chg>0?'+':''}${fmt(r.chg,2)}）<br>
      时点分位 ${fmt(r.pct,3)}　连续状态 ${r.run}<br>现货 ${fmt(r.spot,2)}　期货 ${fmt(r.fut,2)}　基差 ${fmt(r.basis,1)}<br>
      未来1W：现货 ${pct(r.s1)} / 期货 ${pct(r.f1)} / 基差 ${fmt(r.b1,1)}`);});
    el.addEventListener('mouseleave',hideTip);});
}
if($('#ov-window')){$('#ov-window').onchange=e=>{OV.win=e.target.value;drawOverview();};
 $('#ov-px').onchange=e=>{OV.px=e.target.value;drawOverview();};}

let PF={f:'all',t:'all',h:1,sort:'p',only:false};
function drawPooled(){
  const box=$('#pooled-table');if(!box||!D.pooled)return;
  let rows=D.pooled.filter(r=>r.h===PF.h);
  if(PF.f!=='all')rows=rows.filter(r=>r.f===PF.f);
  if(PF.t!=='all')rows=rows.filter(r=>r.t===PF.t);
  if(PF.only)rows=rows.filter(r=>r.p<0.05);
  rows.sort((a,b)=>PF.sort==='p'?(a.p-b.p):(Math.abs(b.rho)-Math.abs(a.rho)));
  box.innerHTML='<table><thead><tr><th>因子</th><th>目标</th><th>有效周数</th><th>Spearman ρ</th><th>原始 p</th>'+
   '<th>斜率</th><th>HAC t</th><th>HAC p</th><th>BH q</th><th>FDR 5%</th></tr></thead><tbody>'+
   rows.map(r=>`<tr><td>${r.f}</td><td>${r.t}</td><td>${r.n}</td><td class="${cls(r.rho)}">${fmt(r.rho,3)}</td>
   <td>${pfmt(r.p)}</td><td>${fmt(r.slope,3)}</td><td>${fmt(r.ht,2)}</td><td>${pfmt(r.hp)}</td>
   <td>${fmt(r.q,3)}</td><td>${r.q<0.05?'<span class="tag p">通过</span>':'<span class="nsig">未通过</span>'}</td></tr>`).join('')+
   '</tbody></table>';
  const nt=$('#pooled-note');
  if(nt)nt.innerHTML=`<div class="note"><b>当前视图：</b>${rows.length} 组中 ${rows.filter(r=>r.p<0.05).length} 组名义显著，
   ${rows.filter(r=>r.q<0.05).length} 组通过 BH-FDR。窗口 ${PF.h} 周，重叠下应以 HAC p 为准。</div>`;
}
if($('#f-factor')&&D.pooled){
  const fs=[...new Set(D.pooled.map(r=>r.f))],ts=[...new Set(D.pooled.map(r=>r.t))];
  $('#f-factor').innerHTML='<option value="all">全部</option>'+fs.map(f=>`<option>${f}</option>`).join('');
  $('#f-target').innerHTML='<option value="all">全部</option>'+ts.map(t=>`<option>${t}</option>`).join('');
  $('#f-factor').onchange=e=>{PF.f=e.target.value;drawPooled();};
  $('#f-target').onchange=e=>{PF.t=e.target.value;drawPooled();};
  $('#f-sort').onchange=e=>{PF.sort=e.target.value;drawPooled();};
  $('#f-onlysig').onchange=e=>{PF.only=e.target.checked;drawPooled();};
  $$('#f-hor button').forEach(b=>b.onclick=()=>{$$('#f-hor button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');PF.h=+b.dataset.h;drawPooled();});
}
function drawHeat(){
  const svg=$('#heat-svg');if(!svg)return;
  const FO=[...new Set(D.pooled.map(r=>r.f))],TO=[...new Set(D.pooled.map(r=>r.t))];
  const W=1100,L=210,T=46,cw=Math.min(150,(W-L-20)/Math.max(TO.length,1)),rh=40;let s='';
  TO.forEach((t,j)=>{s+=`<text x="${L+j*cw+cw/2}" y="${T-14}" fill="#a7b7cf" font-size="11.5" text-anchor="middle">${t}</text>`;});
  FO.forEach((f,i)=>{s+=`<text x="${L-12}" y="${T+i*rh+rh/2+4}" fill="#a7b7cf" font-size="11" text-anchor="end">${f}</text>`;
    TO.forEach((t,j)=>{const r=D.pooled.find(x=>x.h===1&&x.f===f&&x.t===t);if(!r)return;
      const a=Math.min(Math.abs(r.rho)/0.25,1);
      const col=r.rho>=0?`rgba(56,217,169,${a*.85+.06})`:`rgba(255,107,107,${a*.85+.06})`;
      const x=L+j*cw,y=T+i*rh;
      s+=`<rect x="${x+3}" y="${y+3}" width="${cw-6}" height="${rh-6}" rx="6" fill="${col}" data-f="${f}" data-t="${t}"/>`;
      s+=`<text x="${x+cw/2}" y="${y+rh/2+4}" fill="#fff" font-size="12" text-anchor="middle">${fmt(r.rho,2)}${r.p<0.05?' ×':''}</text>`;});});
  svg.innerHTML=s;
  svg.querySelectorAll('rect[data-f]').forEach(el=>{
    el.addEventListener('mousemove',e=>{const r=D.pooled.find(x=>x.h===1&&x.f===el.dataset.f&&x.t===el.dataset.t);
      showTip(e,`<b>${r.f}</b> → ${r.t}(1W)<br>ρ=${fmt(r.rho,3)} p=${fmt(r.p,4)}<br>HAC p=${fmt(r.hp,4)} BH q=${fmt(r.q,3)}<br>n=${r.n}`);});
    el.addEventListener('mouseleave',hideTip);});
}

let GF={dim:'level',t:null,h:1};
function drawGroups(){
  const svg=$('#grp-svg'),box=$('#grp-table');if(!svg||!D.groups)return;
  const rows=D.groups.filter(r=>r.dim===GF.dim&&r.t===GF.t&&r.h===GF.h);
  if(!rows.length){svg.innerHTML='';if(box)box.innerHTML='';return;}
  const W=1140,H=300,L=70,R=24,T=26,B=64,iw=W-L-R,ih=H-T-B;
  const vs=rows.flatMap(r=>[r.lo,r.hi,r.mean,r.med]).filter(v=>v!==null&&!Number.isNaN(v));
  const v0=Math.min(0,...vs),v1=Math.max(0,...vs),span=(v1-v0)||1,Y=v=>T+ih-(v-v0)/span*ih;
  let s='';
  for(let g=0;g<=4;g++){const val=v0+span*g/4,y=Y(val);
    s+=`<line x1="${L}" y1="${y}" x2="${L+iw}" y2="${y}" stroke="${Math.abs(val)<1e-9?'#3d5372':'#1b2941'}"/>`;
    s+=`<text x="${L-8}" y="${y+4}" fill="#71869f" font-size="10" text-anchor="end">${fmt(val,1)}</text>`;}
  const bw=iw/rows.length;
  rows.forEach((r,i)=>{const cx=L+bw*i+bw/2;
    if(r.lo!==null&&r.hi!==null)s+=`<line x1="${cx}" y1="${Y(r.hi)}" x2="${cx}" y2="${Y(r.lo)}" stroke="rgba(167,139,250,.75)" stroke-width="6" stroke-linecap="round"/>`;
    s+=`<circle cx="${cx-11}" cy="${Y(r.mean)}" r="6" fill="#4da3ff"/><circle cx="${cx+11}" cy="${Y(r.med)}" r="6" fill="#38d9a9"/>`;
    s+=`<text x="${cx}" y="${H-44}" fill="#e8eef8" font-size="11" text-anchor="middle">${r.g}</text>`;
    s+=`<text x="${cx}" y="${H-28}" fill="#71869f" font-size="10" text-anchor="middle">n=${r.n}</text>`;
    s+=`<rect x="${L+bw*i}" y="${T}" width="${bw}" height="${ih}" fill="transparent" data-i="${i}"/>`;});
  svg.innerHTML=s;
  svg.querySelectorAll('rect[data-i]').forEach(el=>{
    el.addEventListener('mousemove',e=>{const r=rows[+el.dataset.i];
      showTip(e,`<b>${r.g}</b><br>n=${r.n}<br>均值 ${fmt(r.mean,3)}　中位数 ${fmt(r.med,3)}<br>
      95%CI [${fmt(r.lo,3)}, ${fmt(r.hi,3)}]<br>上涨占比 ${fmt(r.hit,1)}%　p=${fmt(r.p,4)}`);});
    el.addEventListener('mouseleave',hideTip);});
  if(box)box.innerHTML='<table><thead><tr><th>分组</th><th>有效样本</th><th>均值</th><th>中位数</th>'+
   '<th>bootstrap 95% CI</th><th>上涨占比</th><th>与其余组 p</th></tr></thead><tbody>'+
   rows.map(r=>`<tr><td>${r.g}</td><td>${r.n}</td><td class="${cls(r.mean)}">${fmt(r.mean,3)}</td>
   <td class="${cls(r.med)}">${fmt(r.med,3)}</td><td>[${fmt(r.lo,3)}, ${fmt(r.hi,3)}]</td>
   <td>${fmt(r.hit,1)}%</td><td>${pfmt(r.p)}</td></tr>`).join('')+'</tbody></table>';
}
if($('#g-dim')&&D.groups){
  GF.t=[...new Set(D.groups.map(r=>r.t))][0];
  $$('#g-dim button').forEach(b=>b.onclick=()=>{$$('#g-dim button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');GF.dim=b.dataset.d;drawGroups();});
  $$('#g-hor button').forEach(b=>b.onclick=()=>{$$('#g-hor button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');GF.h=+b.dataset.h;drawGroups();});
  const gt=$('#g-target');
  if(gt){gt.innerHTML=[...new Set(D.groups.map(r=>r.t))].map(t=>`<option>${t}</option>`).join('');
    gt.value=GF.t;gt.onchange=e=>{GF.t=e.target.value;drawGroups();};}
}
function drawYearly(){
  const svg=$('#yr-svg'),box=$('#yr-table');if(!svg||!D.yearly)return;
  const t0=[...new Set(D.yearly.map(r=>r.t))][0];
  const rows=D.yearly.filter(r=>r.h===1&&r.t===t0).sort((a,b)=>a.y-b.y);
  if(!rows.length){svg.innerHTML='';return;}
  const W=1140,H=300,L=64,R=24,T=26,B=56,iw=W-L-R,ih=H-T-B;
  const vs=rows.flatMap(r=>[r.hi,r.lo]).filter(v=>v!==null);
  const v0=Math.min(0,...vs),v1=Math.max(0,...vs),span=(v1-v0)||1,Y=v=>T+ih-(v-v0)/span*ih;
  let s='';
  for(let g=0;g<=4;g++){const val=v0+span*g/4,y=Y(val);
    s+=`<line x1="${L}" y1="${y}" x2="${L+iw}" y2="${y}" stroke="${Math.abs(val)<1e-9?'#3d5372':'#1b2941'}"/>`;
    s+=`<text x="${L-8}" y="${y+4}" fill="#71869f" font-size="10" text-anchor="end">${fmt(val,1)}</text>`;}
  const gx=iw/rows.length;
  rows.forEach((r,i)=>{const cx=L+gx*i+gx/2,bh=gx*.26;
    if(r.hi!==null)s+=`<rect x="${cx-bh-3}" y="${Y(r.hi)}" width="${bh}" height="${Math.abs(Y(0)-Y(r.hi))}" fill="#ff6b6b" opacity=".82" rx="3"/>`;
    if(r.lo!==null)s+=`<rect x="${cx+3}" y="${Y(r.lo)}" width="${bh}" height="${Math.abs(Y(0)-Y(r.lo))}" fill="#4da3ff" opacity=".82" rx="3"/>`;
    s+=`<text x="${cx}" y="${H-30}" fill="#e8eef8" font-size="12" text-anchor="middle">${r.y}</text>`;
    s+=`<text x="${cx}" y="${H-14}" fill="#71869f" font-size="10" text-anchor="middle">n=${r.n}</text>`;
    s+=`<rect x="${L+gx*i}" y="${T}" width="${gx}" height="${ih}" fill="transparent" data-i="${i}"/>`;});
  svg.innerHTML=s;
  svg.querySelectorAll('rect[data-i]').forEach(el=>{
    el.addEventListener('mousemove',e=>{const r=rows[+el.dataset.i];
      showTip(e,`<b>${r.y} 年</b>（${r.n} 周）<br>高库存组 ${fmt(r.hi,3)}（n=${r.nh}）<br>
      低库存组 ${fmt(r.lo,3)}（n=${r.nl}）<br>高低差 ${fmt(r.sp,3)}　水平ρ ${fmt(r.rho,3)}`);});
    el.addEventListener('mouseleave',hideTip);});
  if(box)box.innerHTML='<table><thead><tr><th>年份</th><th>周数</th><th>高库存组</th><th>n</th><th>低库存组</th>'+
   '<th>n</th><th>高低差</th><th>水平 ρ</th><th>周度变化 ρ</th></tr></thead><tbody>'+
   rows.map(r=>`<tr><td>${r.y}</td><td>${r.n}</td><td class="${cls(r.hi)}">${fmt(r.hi,3)}</td><td>${r.nh}</td>
   <td class="${cls(r.lo)}">${fmt(r.lo,3)}</td><td>${r.nl}</td><td class="${cls(r.sp)}">${fmt(r.sp,3)}</td>
   <td>${fmt(r.rho,3)}</td><td>${fmt(r.rw,3)}</td></tr>`).join('')+'</tbody></table>';
}
function drawPlacebo(){
  const box=$('#pl-table');if(!box||!D.placebo)return;
  const rows=[...D.placebo].sort((a,b)=>a.p-b.p);
  box.innerHTML='<table><thead><tr><th>分组</th><th>窗口</th><th>结果变量</th><th>组内样本</th>'+
   '<th>组间均值差</th><th>年度分层置换 p</th><th>判定</th></tr></thead><tbody>'+
   rows.map(r=>{const v=r.p<0.01?'<span class="tag p">稳健</span>':r.p<0.05?'<span class="tag w">边缘</span>':'<span class="nsig">不显著</span>';
     return `<tr><td>${r.g}</td><td>${r.h}W</td><td>${r.t}</td><td>${r.n}</td>
     <td class="${cls(r.d)}">${fmt(r.d,4)}</td><td>${pfmt(r.p)}</td><td>${v}</td></tr>`;}).join('')+'</tbody></table>';
}

let SI={s:null};
function drawSub(){
  const box=$('#oos-table');if(!box||!D.subsample)return;
  const rows=D.subsample.filter(r=>r.h===SI.s);
  box.innerHTML='<table><thead><tr><th>样本划分</th><th>目标</th><th>n</th><th>水平 ρ</th><th>水平 p</th>'+
   '<th>周度变化 ρ</th><th>周度变化 p</th></tr></thead><tbody>'+
   rows.map(r=>`<tr><td>${r.s}</td><td>${r.t}</td><td>${r.n}</td><td class="${cls(r.rl)}">${fmt(r.rl,3)}</td>
   <td>${pfmt(r.pl)}</td><td class="${cls(r.rw)}">${fmt(r.rw,3)}</td><td>${pfmt(r.pw)}</td></tr>`).join('')+
   '</tbody></table>';
}
function drawRegime(){
  const box=$('#rg-table');if(!box||!D.regime)return;
  const rows=D.regime.filter(r=>r.h===1);
  box.innerHTML='<table><thead><tr><th>市场结构</th><th>目标</th><th>n</th><th>水平 ρ</th><th>p</th>'+
   '<th>周度变化 ρ</th><th>p</th></tr></thead><tbody>'+
   rows.map(r=>`<tr><td>${r.r}</td><td>${r.t}</td><td>${r.n}</td><td class="${cls(r.rl)}">${fmt(r.rl,3)}</td>
   <td>${pfmt(r.pl)}</td><td class="${cls(r.rw)}">${fmt(r.rw,3)}</td><td>${pfmt(r.pw)}</td></tr>`).join('')+
   '</tbody></table>';
}
function drawCtrl(){
  const box=$('#ctrl-table');if(!box||!D.control)return;
  box.innerHTML='<table><thead><tr><th>窗口</th><th>周度变化率系数</th><th>t</th><th>基差率系数</th><th>t</th><th>n</th>'+
   '</tr></thead><tbody>'+D.control.map(r=>`<tr><td>${r.h} 周</td><td class="${cls(r.bw)}">${fmt(r.bw,4)}</td>
   <td>${fmt(r.tw,2)}</td><td>${fmt(r.bb,4)}</td><td>${fmt(r.tb,2)}</td><td>${r.n}</td></tr>`).join('')+'</tbody></table>';
}
drawOverview();drawPooled();drawHeat();drawGroups();drawYearly();drawPlacebo();drawCtrl();drawRegime();
if(D.subsample){SI.s=Math.min(...D.subsample.map(r=>r.h));drawSub();}
"""


def _payload(out_dir):
    panel = pd.read_csv(os.path.join(out_dir, "panel_weekly.csv"), encoding="utf-8-sig")

    def n(v, nd=4):
        try:
            v = float(v)
        except Exception:
            return None
        return None if not np.isfinite(v) else round(v, nd)

    series = []
    for _, r in panel.iterrows():
        rec = {"w": str(pd.to_datetime(r["week"]).date()),
               "pub": str(r["pub_ts"])[:16] if pd.notna(r.get("pub_ts")) else None,
               "inv": n(r["total"], 2), "chg": n(r.get("wow_chg"), 2),
               "pct": n(r.get("lvl_pct"), 3), "run": int(r.get("run_len", 0) or 0),
               "spot": n(r.get("spot0"), 2), "fut": n(r.get("fut0"), 2), "basis": n(r.get("basis0"), 2)}
        for h in (1, 2, 4):
            for src, key in (("fwd_spot", "s"), ("fwd_fut", "f"), ("fwd_basis", "b")):
                c = "%s_%d" % (src, h)
                rec["%s%d" % (key, h)] = n(r[c] * (100 if src != "fwd_basis" else 1)
                                           if pd.notna(r.get(c)) else np.nan, 2)
        series.append(rec)

    def gt(name, dim):
        df = _load(out_dir, name)
        if not len(df):
            return []
        return [{"dim": dim, "h": int(r["horizon_w"]), "t": r["target"], "g": r["group"],
                 "n": int(r["n"]), "mean": n(r["mean"], 3), "med": n(r["median"], 3),
                 "lo": n(r.get("ci_lo"), 3), "hi": n(r.get("ci_hi"), 3),
                 "hit": n(r.get("hit_up") * 100 if pd.notna(r.get("hit_up")) else np.nan, 1),
                 "p": n(r.get("p_welch"), 4)} for _, r in df.iterrows()]

    pl = _load(out_dir, "pooled")
    yr = _load(out_dir, "yearly")
    pb = _load(out_dir, "placebo")
    sb = _load(out_dir, "subsample")
    rg = _load(out_dir, "regime")
    ct = _load(out_dir, "control")
    return {
        "series": series,
        "pooled": [{"h": int(r["horizon_w"]), "t": r["target"], "f": r["factor"], "n": int(r["n_weeks"]),
                    "rho": n(r["spearman_rho"], 3), "p": n(r["spearman_p"], 4),
                    "slope": n(r["slope_per_unit"], 4), "ht": n(r["hac_t"], 2),
                    "hp": n(r["hac_p"], 4), "q": n(r["q_bh"], 4)} for _, r in pl.iterrows()],
        "groups": gt("groups_level", "level") + gt("groups_wow", "wow") + gt("groups_run", "run"),
        "yearly": [{"y": int(r["year"]), "h": int(r["horizon_w"]), "t": r["target"], "n": int(r["n_weeks"]),
                    "rho": n(r["rho_level"], 3), "hi": n(r["mean_high"], 3), "nh": int(r["n_high"]),
                    "lo": n(r["mean_low"], 3), "nl": int(r["n_low"]), "sp": n(r["spread"], 3),
                    "rw": n(r["rho_wow"], 3)} for _, r in yr.iterrows()],
        "placebo": [{"g": r["group"], "h": int(r["horizon_w"]), "t": r["target"], "d": n(r["diff"], 4),
                     "p": n(r["placebo_p"], 4), "n": int(r["n_in"])} for _, r in pb.iterrows()],
        "subsample": [{"h": int(r["horizon_w"]), "t": r["target"], "s": r["sample"], "n": int(r["n"]),
                       "rl": n(r["rho_level"], 3), "pl": n(r["p_level"], 4),
                       "rw": n(r["rho_wow"], 3), "pw": n(r["p_wow"], 4)} for _, r in sb.iterrows()],
        "regime": [{"h": int(r["horizon_w"]), "t": r["target"], "r": r["regime"], "n": int(r["n"]),
                    "rl": n(r["rho_level"], 3), "pl": n(r["p_level"], 4),
                    "rw": n(r["rho_wow"], 3), "pw": n(r["p_wow"], 4)} for _, r in rg.iterrows()],
        "control": [{"h": int(r["h"]), "bw": n(r["beta_wow_pct"], 4), "tw": n(r["t_wow_pct"], 2),
                     "bb": n(r["beta_basis_rate"], 4), "tb": n(r["t_basis_rate"], 2),
                     "n": int(r["n"])} for _, r in ct.iterrows()],
    }


def _ul(items, style=""):
    if not items:
        return ""
    return '<ul class="tight"%s>%s</ul>' % (style, "".join("<li>%s</li>" % i for i in items))


def build_report(out_dir, narrative, path):
    p = _payload(out_dir)
    sp = os.path.join(out_dir, "summary.json")
    summ = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    n = narrative
    src_rows = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in row)
                       for row in (n.get("source_rows") or []))
    chips = "".join('<span class="chip">%s <b>%s</b></span>' % (c[0], c[1]) for c in (n.get("chips") or []))

    body = []
    if src_rows:
        body.append('<section id="s1"><h2><span class="no">01</span> 数据、口径与真实发布日期</h2>'
                    '<p class="sub">先确认数据在什么时间被公开，再谈任何统计关系。</p>'
                    '<table><thead><tr><th>数据</th><th>口径</th><th>频率 / 时点</th><th>覆盖</th>'
                    '<th>说明</th></tr></thead><tbody>%s</tbody></table>%s</section>'
                    % (src_rows, ('<div class="note warn">%s</div>' % n.get("data_gap_note"))
                       if n.get("data_gap_note") else ""))
    body.append('<section id="s2"><h2><span class="no">03</span> 库存与价格总览</h2>'
                '<p class="sub">先看形态，再判断"关系"是否只是共同趋势或季节性的错觉。</p>'
                '<div class="ctl"><label>区间<select id="ov-window"><option value="all">全部</option>%s</select></label>'
                '<label>叠加<select id="ov-px"><option value="spot">现货价</option><option value="fut">期货价</option>'
                '<option value="basis">基差</option></select></label></div>'
                '<div class="card"><svg class="chart" viewBox="0 0 1180 330" id="ov-svg"></svg>'
                '<div class="legend"><span><i style="background:#4da3ff"></i>库存</span>'
                '<span><i style="background:#ffb454"></i>价格/基差（右轴）</span>'
                '<span><i style="background:rgba(255,107,107,.55)"></i>连续≥2周去库</span></div></div></section>'
                % "".join('<option value="%d">%d</option>' % (y, y)
                          for y in sorted({int(s["w"][:4]) for s in p["series"]})))
    if p["pooled"]:
        body.append('<section id="s4"><h2><span class="no">04</span> 因子 × 未来表现</h2>'
                    '<p class="sub">全部因子×目标×窗口，含 HAC 与 BH-FDR。</p>'
                    '<div class="ctl"><label>因子<select id="f-factor"></select></label>'
                    '<label>目标<select id="f-target"></select></label>'
                    '<label>窗口<span class="seg" id="f-hor"><button data-h="1" class="on">1周</button>'
                    '<button data-h="2">2周</button><button data-h="4">4周</button></span></label>'
                    '<label>排序<select id="f-sort"><option value="p">按p值</option>'
                    '<option value="rho">按|ρ|</option></select></label>'
                    '<label><input type="checkbox" id="f-onlysig"> 只看显著</label></div>'
                    '<div class="card"><div id="pooled-table"></div></div><div id="pooled-note"></div>'
                    '<h3>热力图（1周，× 表示 p&lt;0.05）</h3>'
                    '<div class="card"><svg class="chart" viewBox="0 0 1100 330" id="heat-svg"></svg></div></section>')
    if p["groups"]:
        body.append('<section id="s5"><h2><span class="no">05</span> 分组分布</h2>'
                    '<p class="sub">每组样本数、均值、中位数、bootstrap 95% 置信区间。</p>'
                    '<div class="ctl"><label>维度<span class="seg" id="g-dim">'
                    '<button data-d="level" class="on">水平分位</button><button data-d="wow">周度变化</button>'
                    '<button data-d="run">连续状态</button></span></label>'
                    '<label>目标<select id="g-target"></select></label>'
                    '<label>窗口<span class="seg" id="g-hor"><button data-h="1" class="on">1周</button>'
                    '<button data-h="2">2周</button><button data-h="4">4周</button></span></label></div>'
                    '<div class="card"><svg class="chart" viewBox="0 0 1140 300" id="grp-svg"></svg>'
                    '<div class="legend"><span><i style="background:#4da3ff"></i>均值</span>'
                    '<span><i style="background:#38d9a9"></i>中位数</span>'
                    '<span><i style="background:rgba(167,139,250,.7)"></i>bootstrap 95% CI</span></div></div>'
                    '<div class="card" style="margin-top:16px"><div id="grp-table"></div></div></section>')
    if p["yearly"]:
        body.append('<section id="s6"><h2><span class="no">06</span> 分年度与市场阶段</h2>'
                    '<p class="sub">同一因子在不同年份可能给出相反结论。</p>'
                    '<div class="card"><svg class="chart" viewBox="0 0 1140 300" id="yr-svg"></svg>'
                    '<div class="legend"><span><i style="background:#ff6b6b"></i>高库存组</span>'
                    '<span><i style="background:#4da3ff"></i>低库存组</span></div></div>'
                    '<div class="card" style="margin-top:16px"><div id="yr-table"></div></div>'
                    '<h3>样本内 vs 样本外</h3><div class="card"><div id="oos-table"></div></div></section>')
    if p["placebo"]:
        body.append('<section id="s7"><h2><span class="no">07</span> 显著性与安慰剂</h2>'
                    '<p class="sub">年度内循环平移分组标签，保留季节性、破坏对齐。</p>'
                    '<div class="card"><div id="pl-table"></div></div>'
                    '<h3>控制同期基差水平后的回归</h3><div class="card"><div id="ctrl-table"></div></div>'
                    '</section>')
    if p["regime"]:
        body.append('<section id="s8"><h2><span class="no">08</span> 不同市场结构下的差异</h2>'
                    '<div class="card"><div id="rg-table"></div></div></section>')

    conc = ['<section id="s10"><h2><span class="no">10</span> 结论：统计证据与产业解释分开说</h2>',
            '<div class="grid g2">',
            '<div class="card" style="border-color:#2f6e57"><h4 style="color:#38d9a9">成立的</h4>%s</div>'
            % _ul(n.get("findings_ok"), ' style="font-size:13px"'),
            '<div class="card" style="border-color:#6e3a3a"><h4 style="color:#ff6b6b">不成立的</h4>%s</div>'
            % _ul(n.get("findings_ng"), ' style="font-size:13px"'),
            '</div>',
            '<h3>产业解释（为机制假设，非因果识别）</h3><div class="note">%s</div>'
            % _ul(n.get("industry_notes"), ' style="font-size:13px"'),
            '<h3>必须同时读到的限制</h3>%s' % _ul(n.get("limits"), ' style="font-size:13px"'),
            '<div class="note bad"><b>一句话总结：</b>%s</div></section>' % n.get("one_line", "")]
    body.append("".join(conc))

    toc = "".join('<li><a href="#s%d">%s</a></li>' % (i, t) for i, t in
                  [(1, "数据与口径"), (2, "总览"), (4, "因子×未来表现"), (5, "分组分布"),
                   (6, "分年度"), (7, "显著性与安慰剂"), (8, "市场结构"), (10, "结论")])

    html = (HTML_SHELL
            .replace("__TITLE__", n.get("title", "库存—价格关系研究"))
            .replace("__LEDE__", n.get("lede", ""))
            .replace("__CHIPS__", chips).replace("__TOC__", toc)
            .replace("__BODY__", "".join(body))
            .replace("__FOOTER__", n.get("footer", "仅用于历史统计关系研究，不构成任何投资建议或交易信号。"))
            .replace("__DATA__", json.dumps(p, ensure_ascii=False))
            .replace("__JS__", CHART_JS))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
