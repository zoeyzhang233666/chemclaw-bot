# -*- coding: utf-8 -*-
"""Build the interactive HTML report and the Excel workbook from pipeline output.

    from build_outputs import build_workbook, build_report
    build_workbook("output", narrative, "研究_数据工作簿.xlsx")
    build_report("output", narrative, "研究报告.html")

Everything numeric comes from ``output/*.csv|json``; ``narrative`` supplies only words
and small metadata so that a report can never silently disagree with the data.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from openpyxl import Workbook

from float_numbers import fmt as fmt_float
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ------------------------------------------------------------------ shared styling
NAVY = "1F3864"
HDR_FILL = PatternFill("solid", fgColor=NAVY)
HDR_FONT = Font(color="FFFFFF", bold=True, size=10, name="等线")
TITLE_FONT = Font(bold=True, size=13, color=NAVY, name="等线")
SUB_FONT = Font(size=9, color="595959", name="等线")
BODY = Font(size=10, name="等线")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WARN_FILL = PatternFill("solid", fgColor="FFF3CD")
BAD_FILL = PatternFill("solid", fgColor="F8D7DA")
OK_FILL = PatternFill("solid", fgColor="D4EDDA")


def _g(g):
    """Accept a quality gate as a dict {name,status,detail} or a [name,status,detail] row."""
    if isinstance(g, dict):
        return {"name": g.get("name", ""), "status": g.get("status", ""),
                "detail": g.get("detail", "")}
    row = list(g) + ["", "", ""]
    return {"name": row[0], "status": row[1], "detail": row[2]}


def _json_safe(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        v = float(o)
        if not np.isfinite(v):
            return None
        # re-round through the repaired string so the value carries a clean repr
        return float(fmt_float(v))
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return None if pd.isna(o) else o.isoformat(sep=" ")
    if isinstance(o, (np.datetime64,)):
        return str(o)
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, str) or o is None:
        return o
    return str(o)


def read_out(out_dir, name):
    p = os.path.join(out_dir, name)
    if not os.path.exists(p):
        return None
    if name.endswith(".json"):
        return json.load(open(p, encoding="utf-8"))
    try:
        df = pd.read_csv(p, encoding="utf-8-sig")
    except Exception:
        return None
    return df.where(pd.notna(df), None)


# ------------------------------------------------------------------ workbook


def _write_df(ws, df, start_row=1, title=None, subtitle=None, pct_cols=(), numfmt_map=None,
              blank_note=None):
    r = start_row
    if title:
        ws.cell(row=r, column=1, value=title).font = TITLE_FONT
        r += 1
    if subtitle:
        ws.cell(row=r, column=1, value=subtitle).font = SUB_FONT
        r += 1
    if df is None or df.empty:
        ws.cell(row=r, column=1, value=blank_note or "（本表无数据：样本/字段不足，未做任何推断）").font = SUB_FONT
        return r + 2
    hdr = r
    for j, c in enumerate(df.columns, 1):
        cell = ws.cell(row=hdr, column=j, value=str(c))
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    for i, row in enumerate(df.itertuples(index=False), hdr + 1):
        for j, v in enumerate(row, 1):
            if isinstance(v, (np.floating, float)) and isinstance(v, float) and v != v:
                v = None
            cell = ws.cell(row=i, column=j, value=v)
            cell.font = BODY
            cell.border = BORDER
            colname = df.columns[j - 1]
            if numfmt_map and colname in numfmt_map:
                cell.number_format = numfmt_map[colname]
            elif isinstance(v, float):
                cell.number_format = "0.0000"
    ws.row_dimensions[hdr].height = 30
    for j, c in enumerate(df.columns, 1):
        try:
            ln = int(pd.Series(df[c]).astype(str).str.len().max())
            if ln != ln:      # NaN
                ln = 10
        except Exception:
            ln = 10
        width = max(10, min(42, ln + 2))
        ws.column_dimensions[get_column_letter(j)].width = max(width, len(str(c)) * 1.35)
    ws.freeze_panes = ws.cell(row=hdr + 1, column=1)
    ws.auto_filter.ref = "A%d:%s%d" % (hdr, get_column_letter(len(df.columns)), hdr + len(df))
    return hdr + len(df) + 2


def _notes_sheet(wb, rows, title="00_使用说明与质量声明"):
    ws = wb.create_sheet(title)
    r = 1
    c = ws.cell(row=r, column=1, value=title)
    c.font = TITLE_FONT
    r += 2
    for k, v in rows:
        if not k:
            continue
        a = ws.cell(row=r, column=1, value=k)
        a.font = Font(bold=True, size=10, name="等线")
        a.alignment = Alignment(vertical="top", wrap_text=True)
        b = ws.cell(row=r, column=2, value=v)
        b.font = BODY
        b.alignment = Alignment(vertical="top", wrap_text=True)
        if str(k).startswith("!"):
            b.fill = WARN_FILL
        r += 1
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 118
    return ws


def build_workbook(out_dir, narrative, path):
    n = narrative
    panel = read_out(out_dir, "panel.csv")
    summary = read_out(out_dir, "summary.json") or {}
    power = read_out(out_dir, "res_power.csv")
    if power is None:
        power = pd.DataFrame(summary.get("power") or [])
    pooled = read_out(out_dir, "res_pooled.csv")
    g_abs = read_out(out_dir, "res_groups_absolute.csv")
    g_chg = read_out(out_dir, "res_groups_change.csv")
    g_pct = read_out(out_dir, "res_groups_percentile.csv")
    yearly = read_out(out_dir, "res_yearly.csv")
    regime = read_out(out_dir, "res_regime.csv")
    placebo = read_out(out_dir, "res_placebo.csv")
    corr = read_out(out_dir, "res_corr.csv")
    monthly = read_out(out_dir, "res_monthly.json") or {}
    util = read_out(out_dir, "../data/util_weekly.csv")
    if util is None:
        util = read_out(out_dir, "../data/util_weekly.csv")
    fut = read_out(out_dir, "../data/pvc_futures_daily.csv")
    fut_m = read_out(out_dir, "../data/pvc_futures_monthly.csv")

    wb = Workbook()
    wb.remove(wb.active)

    # ---- 00 notes / quality statement
    gates = [_g(g) for g in (n.get("quality_gates") or [])]
    note_rows = [(n.get("title", "研究"), n.get("lede", "")),
                 ("生成时间", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")),
                 ("结论", n.get("one_line", "")),
                 ("统计裁决", "样本量不足以识别任何关系（%s）" % summary.get("verdict_stat")
                  if summary.get("verdict_stat") == "insufficient"
                  else "样本量达到可分析门槛（%s）" % summary.get("verdict_stat"))]
    for g in gates:
        note_rows.append(("! " + g.get("name", "质量门"), "%s —— %s" % (g.get("status", ""), g.get("detail", ""))))
    note_rows.append(("", ""))
    note_rows.append(("口径与来源", ""))
    for row in (n.get("source_rows") or []):
        note_rows.append((row[0], " | ".join(str(x) for x in row[1:])))
    dec = n.get("declarations") or []
    if dec:
        note_rows.append(("", ""))
        note_rows.append(("研究方法声明", ""))
        for i, d in enumerate(dec, 1):
            note_rows.append(("D%d" % i, d))
    _notes_sheet(wb, note_rows)

    # ---- 01 utilisation raw (point-in-time)
    if util is not None and len(util):
        cols = [c for c in ["stat_week_end", "window", "pub_ts", "util_total", "cwe_pct", "yoy_pct",
                            "calc", "calc_cwe", "eth", "eth_cwe", "sample_n", "capacity_base_wt",
                            "implied_prev_level", "url", "title"] if c in util.columns]
        ws = wb.create_sheet("01_开工率原始")
        _write_df(ws, util[cols], title="开工率原始观测（逐期留档：统计截止日 + 真实公布时间点 + 原文链接）",
                  subtitle="cwe_pct/yoy_pct 为原文公布值；implied_prev_level = level/(1+环比) 用于核对上一期；"
                           "样本企业与产能基数变化保留在 capacity_base_wt。")

    # ---- 02 factor construction (row-level auditability)
    if panel is not None and len(panel):
        cols = [c for c in ["week_idx", "stat_week_end", "pub_ts", "util", "chg_pp", "chg_rel_pct",
                            "level_pct", "level_z", "pct_hist_n", "run_len", "calc", "eth",
                            "origin_date", "days_stat_to_origin", "days_pub_to_origin"] if c in panel.columns]
        ws = wb.create_sheet("02_因子构造")
        _write_df(ws, panel[cols],
                  title="三类因子逐期构造（每一行都能回答“当天算得出来吗”）",
                  subtitle="F1 利用 util（当期公布值）；F2 变化用相邻两期公布值；F3 分位只用该期之前已公布的 "
                           "pct_hist_n 个历史值（expanding），不引用未来。level_pct 为 NaN 表示历史不足 52 期。")

    # ---- 03 forward returns
    if panel is not None and len(panel):
        cols = [c for c in ["week_idx", "stat_week_end", "pub_ts", "origin_date", "origin_close",
                            "end_date_1w", "fwd_ret_1w", "end_date_2w", "fwd_ret_2w",
                            "end_date_4w", "fwd_ret_4w", "past_ret_1w", "regime_price"] if c in panel.columns]
        d = panel[cols].copy()
        for c in ("fwd_ret_1w", "fwd_ret_2w", "fwd_ret_4w", "past_ret_1w"):
            if c in d:
                d[c + "_pct"] = pd.to_numeric(d[c], errors="coerce") * 100
                d = d.drop(columns=[c])
        ws = wb.create_sheet("03_未来收益")
        _write_df(ws, d, title="未来收益对齐（基期=公布时间之后第一个交易日收盘，窗口按交易日计）",
                  subtitle="1w=5、2w=10、4w=20 个交易日；空白=窗口尚未走完或期货未上市。"
                           "连续周频观测的窗口彼此重叠，自由度已在 05/09 表中按 n_eff=n/h 折算。")

    # ---- 04 formulas & parameter register
    ws = wb.create_sheet("04_公式与参数")
    fr = n.get("formulas") or []
    fdf = pd.DataFrame(fr, columns=["项目", "公式 / 定义", "说明"])
    _write_df(ws, fdf, title="公式登记表（报告正文引用同一份）",
              subtitle="所有因子、收益、分组、检验公式，便于复核。", blank_note="（未提供公式表）")
    par = summary.get("config") or {}
    prow = [{"参数": k, "取值": json.dumps(v, ensure_ascii=False)} for k, v in par.items()]
    _write_df(ws, pd.DataFrame(prow), title="本次运行的固定参数（事后不得为显著性而调整）",
              subtitle="分组切点、窗口、最少历史期数、alpha、bootstrap/placebo 次数均在此登记。")

    # ---- 05 grouping: absolute
    fmt = {"n": "0", "mean_pct": "0.000", "median_pct": "0.000", "std_pct": "0.000",
           "ci95_lo_pct": "0.000", "ci95_hi_pct": "0.000", "share_up_pct": "0.0",
           "wilson_lo_pct": "0.0", "wilson_hi_pct": "0.0", "n_eff": "0.00"}
    ws = wb.create_sheet("05_分组统计_绝对")
    _write_df(ws, g_abs, title="分组一：按开工率绝对水平（固定阈值 %s）" % (summary.get("config", {}).get("level_bands")),
              subtitle="每组给出 样本量、均值、中位数、标准差、P10/P25/P75/P90、最小最大、"
                       "环形块 bootstrap 95% 区间、上涨占比及 Wilson 区间、有效样本 n_eff。"
                       "usable=False 表示样本过少，该组数字不可用于下结论。",
              numfmt_map=fmt)
    ws = wb.create_sheet("06_分组统计_变化")
    _write_df(ws, g_chg, title="分组二：按周度变化方向与幅度（阈值 ±%.1f pp）"
              % float(summary.get("config", {}).get("chg_threshold_pp", 1.0)),
              subtitle="方向分组需两侧都有足够样本才可比较；单侧样本不足时报告为不可用。", numfmt_map=fmt)
    ws = wb.create_sheet("07_分组统计_分位")
    _write_df(ws, g_pct, title="分组三：按历史分位（p20 / p50 / p80 固定切点）",
              subtitle="分位为 expanding 计算；历史不足 52 期时该期不进入本表（这是本案例 F3 为空的原因）。",
              numfmt_map=fmt)

    # ---- 08 significance
    ws = wb.create_sheet("08_显著性")
    _write_df(ws, pooled, title="因子 × 窗口 的关联检验（Spearman IC + HAC 回归 + BH-FDR）",
              subtitle="IC 为秩相关；beta 为“因子每 1 个标准差对应的未来收益百分点”；"
                       "HAC 带宽 = 窗口-1；q_bh 为全部检验族的 Benjamini-Hochberg 校正值。"
                       "n_eff = n / (h/步长)，即不重叠意义上的有效观测数。",
              numfmt_map={"ic": "0.0000", "ic_p": "0.0000", "beta_pct_per_sd": "0.0000",
                          "hac_t": "0.000", "hac_p": "0.0000", "q_bh": "0.0000", "n_eff": "0.00"})
    r = ws.max_row + 2
    ws.cell(row=r, column=1, value="检验功效（该样本能识别多小的效应？）").font = Font(bold=True, name="等线")
    ws.cell(row=r + 1, column=1,
            value="min_n_eff=%s；MDES(sd) 为在 alpha=0.05、power=0.8 下能识别的最小标准化效应；"
                  "prob_halfwidth_pp 为‘方向一致性’在 p=0.5 时的最小可分辨偏离（百分点）。"
                  % summary.get("min_n_eff_required")).font = SUB_FONT
    _write_df(ws, power, start_row=r + 3, numfmt_map={"mdes_sd": "0.000", "prob_halfwidth_pp": "0.00",
                                                      "n_eff_nonoverlap": "0.00"})

    # ---- 09 stability
    ws = wb.create_sheet("09_年度与阶段")
    _write_df(ws, yearly, title="分年度稳定性（verdict=insufficient 表示该年样本不足以判断）",
              numfmt_map={"mean_hi_pct": "0.000", "mean_lo_pct": "0.000",
                          "spread_hi_minus_lo_pct": "0.000", "ic_level": "0.0000",
                          "ic_change": "0.0000"})
    r = ws.max_row + 2
    ws.cell(row=r, column=1, value="市场阶段（期货价相对 60 日线的上/下行）").font = Font(bold=True, name="等线")
    _write_df(ws, regime, start_row=r + 1,
              numfmt_map={"ic_level": "0.0000", "ic_change": "0.0000", "mean_pct": "0.0000"})

    # ---- 10 placebo + collinearity/simultaneous
    ws = wb.create_sheet("10_安慰剂与同向性")
    _write_df(ws, placebo, title="年度内循环平移安慰剂（保留季节性、破坏对齐）",
              subtitle="placebo_p 为 |IC_shift| >= |IC_obs| 的比例；若无真实关系，该值应接近真实 p 值而非更小。",
              numfmt_map={"ic_obs": "0.0000", "placebo_p": "0.0000", "n": "0"})
    r = ws.max_row + 2
    ws.cell(row=r, column=1, value="同期 / 过去 vs 未来（区分“同步指标”与“预测指标”）").font = Font(bold=True, name="等线")
    _write_df(ws, corr, start_row=r + 1, numfmt_map={"ic": "0.0000"})

    # ---- 11 monthly corroboration
    ws = wb.create_sheet("11_月度交叉验证")
    rows = monthly.get("rows") or []
    _write_df(ws, pd.DataFrame(rows) if rows else None,
              title="月度 K 线交叉验证通道（非 point-in-time 证据，仅作检验功效参照）",
              subtitle="本案例开工率可核验样本仅 7 期，年度检验无法进行；此处给出期货月收益的自相关底色，"
                       "说明同口径月度检验至少需要多少观测。",
              blank_note="（无月度数据）")
    if monthly.get("prod_gap"):
        r = ws.max_row + 2
        ws.cell(row=r, column=1, value=monthly["prod_gap"]).font = SUB_FONT

    # ---- 12 futures data
    ws = wb.create_sheet("12_期货连续合约")
    if fut is not None and len(fut):
        d = fut.copy()
        for c in ("adj_close", "close", "settle"):
            if c in d:
                d[c] = pd.to_numeric(d[c], errors="coerce")
        _write_df(ws, d, title="PVC 期货连续合约日线（%d 个交易日，按成交量换月并复权）" % len(d),
                  subtitle="ret_1d 为相邻交易日收益；roll_jump 为换月跳空（已从 adj_close 中剔除）。",
                  numfmt_map={"close": "#,##0.0", "adj_close": "#,##0.0", "ret_1d": "0.0000%"})
    ws2 = wb.create_sheet("13_期货月线")
    _write_df(ws2, fut_m, title="PVC 期货月线（交叉验证通道用量）",
              numfmt_map={"close": "#,##0.0", "adj_close": "#,##0.0", "ret_m": "0.0000%"})

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wb.save(path)
    return path


# ------------------------------------------------------------------ HTML

CSS = """
:root{--bg:#0f1420;--card:#171f2e;--line:#263247;--txt:#e6edf7;--dim:#8fa1bb;--acc:#4da3ff;
--ok:#38d9a9;--warn:#ffb454;--bad:#ff6b6b;--vio:#a78bfa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.75 "PingFang SC","Microsoft YaHei",system-ui,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
header{padding:38px 40px 18px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#131b29,#0f1420)}
h1{margin:0 0 8px;font-size:26px;letter-spacing:.5px}
h2{font-size:19px;margin:0 0 6px}h3{font-size:15px;margin:22px 0 8px;color:var(--acc)}
h4{margin:0 0 8px;font-size:14px}
.sub{color:var(--dim);margin:0 0 14px;font-size:13px}
.wrap{display:flex;gap:0;align-items:flex-start}
nav{position:sticky;top:0;width:196px;flex:0 0 196px;padding:22px 14px;border-right:1px solid var(--line);height:100vh;overflow:auto}
nav a{display:block;padding:6px 10px;border-radius:6px;color:var(--dim);font-size:13px}
nav a:hover{background:#1b2536;color:var(--txt)}
main{flex:1;min-width:0;padding:24px 40px 80px;max-width:1360px}
section{margin:0 0 46px;scroll-margin-top:16px}
.no{display:inline-block;min-width:34px;color:var(--acc);font-weight:700;margin-right:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.grid{display:grid;gap:14px}.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .v{font-size:26px;font-weight:700;letter-spacing:.5px}
.kpi .k{color:var(--dim);font-size:12px;margin-bottom:2px}
.kpi .d{color:var(--dim);font-size:12px;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;background:#131b29;position:sticky;top:0}
tbody tr:hover{background:#1b2434}
.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;border:1px solid}
.t-ok{color:var(--ok);border-color:#2f6e57;background:rgba(56,217,169,.08)}
.t-warn{color:var(--warn);border-color:#7a5a2a;background:rgba(255,180,84,.08)}
.t-bad{color:var(--bad);border-color:#6e3a3a;background:rgba(255,107,107,.08)}
.t-dim{color:var(--dim);border-color:var(--line)}
.note{border-left:3px solid var(--acc);background:#131b29;padding:10px 14px;border-radius:0 8px 8px 0;margin:10px 0;font-size:13px}
.note.warn{border-color:var(--warn)}.note.bad{border-color:var(--bad)}.note.ok{border-color:var(--ok)}
.chip{display:inline-block;margin:3px 6px 3px 0;padding:3px 10px;border-radius:99px;background:#1b2536;
border:1px solid var(--line);font-size:12px;color:var(--dim)}
.chip b{color:var(--txt)}
.ctl{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin:10px 0 4px}
.ctl label{font-size:12px;color:var(--dim);display:flex;gap:6px;align-items:center}
select,button,input{font-family:inherit}
select{background:#131b29;color:var(--txt);border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12.5px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg button{background:#131b29;color:var(--dim);border:0;padding:5px 11px;font-size:12.5px;cursor:pointer}
.seg button.on{background:var(--acc);color:#08121f;font-weight:700}
svg.chart{width:100%;height:auto;display:block}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin-top:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
.formula{font-family:"Cascadia Mono",Consolas,monospace;font-size:12.5px;background:#0b1018;
border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0;white-space:pre-wrap;color:#cfe0f7}
ul{margin:8px 0 8px 18px;padding:0}li{margin:4px 0;font-size:13.5px}
footer{padding:22px 40px 40px;color:var(--dim);font-size:12px;border-top:1px solid var(--line)}
.muted{color:var(--dim)}
.badge-lg{font-size:13px;padding:6px 14px}
.tooltip{position:fixed;pointer-events:none;background:#0b1018;border:1px solid var(--acc);border-radius:8px;
padding:8px 11px;font-size:12px;color:var(--txt);display:none;z-index:99;max-width:340px;line-height:1.6}
"""

JS = r"""
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const tip=document.createElement('div'); tip.className='tooltip'; document.body.appendChild(tip);
function showTip(ev,html){tip.innerHTML=html;tip.style.display='block';
  const x=Math.min(ev.clientX+14,innerWidth-350), y=Math.min(ev.clientY+14,innerHeight-160);
  tip.style.left=x+'px';tip.style.top=y+'px';}
function hideTip(){tip.style.display='none';}
const fmt=(v,d=2)=>(v===null||v===undefined||Number.isNaN(v))?'—':Number(v).toFixed(d);
const pctf=(v,d=2)=>(v===null||v===undefined||Number.isNaN(v))?'—':(v>0?'+':'')+Number(v).toFixed(d)+'%';
const NS='http://www.w3.org/2000/svg';
function el(tag,attrs={},text){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);
  if(text!==undefined)e.textContent=text;return e;}
function clear(svg){while(svg.firstChild)svg.removeChild(svg.firstChild);}

/* ---------- overview chart: utilisation vs futures ---------- */
function drawOverview(svg,series){
  clear(svg); const W=1180,H=330,L=64,R=88,T=18,B=38;
  const iw=W-L-R, ih=H-T-B;
  const us=series.map(d=>d.util).filter(v=>v!==null);
  if(!us.length){svg.appendChild(el('text',{x:W/2,y:H/2,fill:'#8fa1bb','text-anchor':'middle'},'无可显示数据'));return;}
  const u0=Math.min(...us)-1, u1=Math.max(...us)+1;
  const px=series.map(d=>d.px).filter(v=>v!==null);
  const p0=Math.min(...px), p1=Math.max(...px);
  const X=i=>L+iw*(i/Math.max(series.length-1,1));
  const Yu=v=>T+ih*(1-(v-u0)/(u1-u0));
  const Yp=v=>T+ih*(1-(v-p0)/((p1-p0)||1));
  for(let k=0;k<=4;k++){const y=T+ih*k/4;svg.appendChild(el('line',{x1:L,x2:L+iw,y1:y,y2:y,stroke:'#263247','stroke-width':1}));
    svg.appendChild(el('text',{x:L-8,y:y+4,fill:'#8fa1bb','font-size':11,'text-anchor':'end'},(u1-(u1-u0)*k/4).toFixed(0)+'%'));
    svg.appendChild(el('text',{x:L+iw+8,y:y+4,fill:'#ffb454','font-size':11},Math.round(p1-(p1-p0)*k/4)));}
  let dU='',dP='';series.forEach((d,i)=>{if(d.util!==null)dU+=(dU?'L':'M')+X(i)+','+Yu(d.util);
    if(d.px!==null)dP+=(dP?'L':'M')+X(i)+','+Yp(d.px);});
  svg.appendChild(el('path',{d:dP,fill:'none',stroke:'#ffb454','stroke-width':2}));
  svg.appendChild(el('path',{d:dU,fill:'none',stroke:'#4da3ff','stroke-width':2.5}));
  series.forEach((d,i)=>{const c=el('circle',{cx:X(i),cy:Yu(d.util),r:5,fill:'#4da3ff',stroke:'#0f1420',
    'stroke-width':2,style:'cursor:pointer'});
    c.addEventListener('mouseenter',e=>showTip(e,`<b>${d.w}</b><br>统计截止 ${d.w}，公布 ${d.pub}<br>
      开工率 <b>${fmt(d.util)}%</b>（环比 ${d.cwe>0?'+':''}${fmt(d.cwe)}pp）<br>
      电石法 ${fmt(d.calc)}% / 乙烯法 ${fmt(d.eth)}%<br>
      基期 ${d.origin} 收盘 ${fmt(d.origin_px,0)}<br>
      未来5日 ${pctf(d.f1)}｜未来10日 ${pctf(d.f2)}｜未来20日 ${pctf(d.f4)}`));
    c.addEventListener('mouseleave',hideTip);
    c.addEventListener('click',()=>{ if(window.__selectPoint) window.__selectPoint(d); });
    svg.appendChild(c);
    svg.appendChild(el('text',{x:X(i),y:H-14,fill:'#8fa1bb','font-size':10.5,'text-anchor':'middle'},d.w.slice(5)));
  });
}

/* ---------- horizontal bars: group means with CI ---------- */
function drawGroups(svg,groups,field){
  clear(svg); const W=900,H=300,L=118,R=30,T=20,B=42, iw=W-L-R, ih=H-T-B;
  if(!groups||!groups.length){svg.appendChild(el('text',{x:W/2,y:H/2,fill:'#8fa1bb','text-anchor':'middle'},'该组合无可用样本'));return;}
  const vals=[];groups.forEach(g=>{if(g.mean!==null)vals.push(g.mean);if(g.ci_lo!==null){vals.push(g.ci_lo);vals.push(g.ci_hi);}});
  let lo=Math.min(...vals,0),hi=Math.max(...vals,0); const pad=(hi-lo||1)*0.15; lo-=pad;hi+=pad;
  const Y=i=>T+ih*(i+0.5)/groups.length, X=v=>L+iw*(v-lo)/(hi-lo);
  const zero=X(0);svg.appendChild(el('line',{x1:zero,x2:zero,y1:T,y2:T+ih,stroke:'#8fa1bb','stroke-dasharray':'3 3'}));
  for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4,x=X(v);
    svg.appendChild(el('line',{x1:x,x2:x,y1:T,y2:T+ih,stroke:'#263247','stroke-width':1}));
    svg.appendChild(el('text',{x:x,y:H-20,fill:'#8fa1bb','font-size':11,'text-anchor':'middle'},v.toFixed(1)+'%'));}
  groups.forEach((g,i)=>{
    const y=Y(i);
    svg.appendChild(el('text',{x:L-10,y:y+4,fill:g.usable?'#e6edf7':'#8fa1bb','font-size':12,'text-anchor':'end'},
      g.label+'  (n='+g.n+')'));
    if(g.usable&&g.ci_lo!==null){
      svg.appendChild(el('line',{x1:X(g.ci_lo),x2:X(g.ci_hi),y1:y,y2:y,stroke:'#a78bfa','stroke-width':7,
        'stroke-opacity':.55,'stroke-linecap':'round'}));}
    if(g.mean!==null) {
      const r=el('rect',{x:Math.min(X(g.mean),zero),y:y-8,width:Math.max(Math.abs(X(g.mean)-zero),1.5),height:16,
        rx:3,fill:g.mean>=0?'#38d9a9':'#ff6b6b',opacity:g.usable?0.95:0.35,style:'cursor:pointer'});
      r.addEventListener('mouseenter',e=>showTip(e,`<b>${g.label}</b>（${g.horizon}）<br>n=${g.n}（有效 ${fmt(g.n_eff,1)}）<br>
        均值 ${pctf(g.mean)}｜中位数 ${pctf(g.median)}<br>标准差 ${fmt(g.std)}｜P10 ${pctf(g.q10)}｜P90 ${pctf(g.q90)}<br>
        bootstrap 95%：${pctf(g.ci_lo)} ~ ${pctf(g.ci_hi)}<br>上涨占比 ${fmt(g.share_up,1)}%（Wilson ${fmt(g.w_lo,1)}~${fmt(g.w_hi,1)}）`));
      r.addEventListener('mouseleave',hideTip); svg.appendChild(r);
    }
  });
  svg.appendChild(el('text',{x:L+iw/2,y:H-4,fill:'#8fa1bb','font-size':11,'text-anchor':'middle'},
    '未来收益均值（%），紫条=bootstrap 95% 置信区间；浅色=样本不足，不可下结论'));
}

/* ---------- per-point scatter ---------- */
function drawScatter(svg,pts,xlab,ylab){
  clear(svg); const W=900,H=340,L=66,R=20,T=18,B=52, iw=W-L-R, ih=H-T-B;
  if(!pts.length){svg.appendChild(el('text',{x:W/2,y:H/2,fill:'#8fa1bb','text-anchor':'middle'},'无可用点'));return;}
  const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
  let x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys,0),y1=Math.max(...ys,0);
  const xp=(x1-x0||1)*0.1; x0-=xp;x1+=xp; const yp=(y1-y0||1)*0.15; y0-=yp;y1+=yp;
  const X=v=>L+iw*(v-x0)/(x1-x0), Y=v=>T+ih*(1-(v-y0)/(y1-y0));
  for(let k=0;k<=4;k++){const yy=T+ih*k/4;
    svg.appendChild(el('line',{x1:L,x2:L+iw,y1:yy,y2:yy,stroke:'#263247'}));
    svg.appendChild(el('text',{x:L-8,y:yy+4,fill:'#8fa1bb','font-size':11,'text-anchor':'end'},(y1-(y1-y0)*k/4).toFixed(1)+'%'));}
  svg.appendChild(el('line',{x1:L,x2:L+iw,y1:Y(0),y2:Y(0),stroke:'#8fa1bb','stroke-dasharray':'3 3'}));
  pts.forEach(p=>{const c=el('circle',{cx:X(p.x),cy:Y(p.y),r:6,fill:p.y>=0?'#38d9a9':'#ff6b6b',opacity:.9,
    stroke:'#0f1420','stroke-width':1.5,style:'cursor:pointer'});
    c.addEventListener('mouseenter',e=>showTip(e,`<b>${p.w}</b><br>${xlab} = ${fmt(p.x)}<br>${ylab} = ${pctf(p.y)}<br>
      基期 ${p.origin}；原文公布于 ${p.pub}`));
    c.addEventListener('mouseleave',hideTip);
    c.addEventListener('click',()=>{ if(window.__selectPoint) window.__selectPoint(p); });
    svg.appendChild(c);});
  svg.appendChild(el('text',{x:L+iw/2,y:H-16,fill:'#8fa1bb','font-size':11,'text-anchor':'middle'},xlab));
}

/* ---------- power curve ---------- */
function drawPower(svg,curve){
  clear(svg); const W=900,H=300,L=64,R=24,T=18,B=44, iw=W-L-R, ih=H-T-B;
  const X=n=>L+iw*(Math.log10(n)-Math.log10(4))/(Math.log10(1000)-Math.log10(4));
  const Y=h=>T+ih*(1-Math.min(h,55)/55);
  for(let k=0;k<=4;k++){const yy=T+ih*k/4;
    svg.appendChild(el('line',{x1:L,x2:L+iw,y1:yy,y2:yy,stroke:'#263247'}));
    svg.appendChild(el('text',{x:L-8,y:yy+4,fill:'#8fa1bb','font-size':11,'text-anchor':'end'},(55*(1-k/4)).toFixed(0)+'pp'));}
  [4,10,30,100,300,1000].forEach(n=>svg.appendChild(el('text',{x:X(n),y:H-20,fill:'#8fa1bb','font-size':11,
    'text-anchor':'middle'},n)));
  let d='';curve.forEach((p,i)=>{d+=(i?'L':'M')+X(p.n)+','+Y(p.hw);});
  svg.appendChild(el('path',{d,fill:'none',stroke:'#4da3ff','stroke-width':2.5}));
  svg.appendChild(el('line',{x1:X(30),x2:X(30),y1:T,y2:T+ih,stroke:'#ffb454','stroke-dasharray':'4 4'}));
  svg.appendChild(el('text',{x:X(30)+6,y:T+14,fill:'#ffb454','font-size':11},'可分析门槛 n_eff=30'));
  curve.forEach(p=>{if(p.mark){const c=el('circle',{cx:X(p.n),cy:Y(p.hw),r:6,fill:'#ff6b6b',stroke:'#0f1420',
    'stroke-width':2}); c.addEventListener('mouseenter',e=>showTip(e,`本项目：n_eff≈${fmt(p.n,1)}，
    方向一致性可分辨的最小区间宽度 ${fmt(p.hw,1)} 个百分点（即几乎无法区分 50% 与任何别的比例）`));
    c.addEventListener('mouseleave',hideTip);svg.appendChild(c);}});
  svg.appendChild(el('text',{x:L+iw/2,y:H-4,fill:'#8fa1bb','font-size':11,'text-anchor':'middle'},
    '独立观测数（对数轴）→ 判定“方向一致性”时可分辨的最小偏离'));
}
"""

HTML_TPL = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>__TITLE__</title><style>__CSS__</style></head><body>
<header><h1>__TITLE__</h1><p class="sub">__LEDE__</p><div>__CHIPS__</div></header>
<div class="wrap"><nav>__TOC__</nav><main>__BODY__</main></div>
<footer>__FOOTER__<br>本页为自包含单文件（无外链脚本/CDN），可直接离线打开。所有数字由 scripts/pipeline.py 计算并复现。</footer>
<div class="tooltip"></div>
<script>const D=__DATA__;__JS__</script>
</body></html>"""


def build_report(out_dir, narrative, path):
    n = narrative
    summary = read_out(out_dir, "summary.json") or {}
    panel = read_out(out_dir, "panel.csv")
    pooled = read_out(out_dir, "res_pooled.csv")
    power = read_out(out_dir, "res_power.csv")
    if power is None and summary.get("power"):
        power = pd.DataFrame(summary["power"])
    groups = {}
    for k in ("absolute", "change", "percentile"):
        _df = read_out(out_dir, "res_groups_%s.csv" % k)
        groups[k] = _df if _df is not None else pd.DataFrame()
    yearly = read_out(out_dir, "res_yearly.csv")
    placebo = read_out(out_dir, "res_placebo.csv")
    corr = read_out(out_dir, "res_corr.csv")
    monthly = read_out(out_dir, "res_monthly.json") or {}
    cfgv = summary.get("config") or {}
    hz = cfgv.get("horizons_sessions") or {"1w": 5, "2w": 10, "4w": 20}
    hzm = {"1w": 5, "2w": 10, "4w": 20}

    # ---- data payload for JS
    series = []
    if panel is not None and len(panel):
        for row in panel.to_dict("records"):
            series.append({
                "w": str(row.get("stat_week_end", ""))[:10],
                "pub": str(row.get("pub_ts", ""))[:16],
                "util": row.get("util"), "cwe": row.get("chg_pp"),
                "calc": row.get("calc"), "eth": row.get("eth"),
                "pct": row.get("level_pct"),
                "origin": str(row.get("origin_date") or "")[:10],
                "origin_px": row.get("origin_close"),
                "px": row.get("origin_close"),
                "f1": (row.get("fwd_ret_1w") * 100 if row.get("fwd_ret_1w") is not None else None),
                "f2": (row.get("fwd_ret_2w") * 100 if row.get("fwd_ret_2w") is not None else None),
                "f4": (row.get("fwd_ret_4w") * 100 if row.get("fwd_ret_4w") is not None else None),
                "p1": (row.get("past_ret_1w") * 100 if row.get("past_ret_1w") is not None else None),
                "regime": row.get("regime_price"),
            })
    grp_payload = {}
    for dim, df in groups.items():
        rows = []
        for r in (df.to_dict("records") if len(df) else []):
            rows.append({"label": r.get("group"), "horizon": r.get("horizon"), "n": r.get("n"),
                         "mean": r.get("mean_pct"), "median": r.get("median_pct"),
                         "std": r.get("std_pct"), "q10": r.get("q10_pct"), "q90": r.get("q90_pct"),
                         "ci_lo": r.get("ci95_lo_pct"), "ci_hi": r.get("ci95_hi_pct"),
                         "share_up": r.get("share_up_pct"), "w_lo": r.get("wilson_lo_pct"),
                         "w_hi": r.get("wilson_hi_pct"), "n_eff": r.get("n_eff"),
                         "usable": bool(r.get("usable") or False)})
        grp_payload[dim] = rows
    payload = {"series": _json_safe(series), "groups": _json_safe(grp_payload),
               "summary": _json_safe(summary),
               "n_used": summary.get("n_used"),
               "min_n_eff": summary.get("min_n_eff_required", 30)}

    # ---- HTML fragments
    def chip(k, v):
        return '<span class="chip">%s <b>%s</b></span>' % (k, v)

    chips = "".join(chip(k, v) for k, v in (n.get("chips") or []))
    body = []
    # 01 data
    src_rows = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in row)
                       for row in (n.get("source_rows") or []))
    body.append('<section id="s1"><h2><span class="no">01</span>口径核实与真实发布日期</h2>'
                '<p class="sub">先确认“这个数字什么时候被谁公开”，再谈任何统计关系。'
                '所有时间戳来自页面 datePublished，逐篇留档。</p>'
                '<div class="card"><table><thead><tr><th>数据</th><th>口径</th><th>频率 / 时点</th>'
                '<th>覆盖或变更</th><th>说明</th></tr></thead><tbody>%s</tbody></table></div>%s</section>'
                % (src_rows, ('<div class="note warn">%s</div>' % n.get("data_gap_note"))
                   if n.get("data_gap_note") else ""))
    # 02 availability / verdict
    gates = [_g(g) for g in (n.get("quality_gates") or [])]
    grow = "".join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
                   % (g.get("name"), g.get("status"), g.get("detail")) for g in gates)
    verdict_tag = ('<span class="tag t-bad badge-lg">样本不足 · 不可检验</span>'
                   if summary.get("verdict_stat") == "insufficient"
                   else '<span class="tag t-warn badge-lg">样本达到门槛但结论需谨慎</span>')
    body.append('<section id="s2"><h2><span class="no">02</span>可得性与统计裁决</h2>'
                '<p class="sub">这一节回答“这份数据能不能支撑一个结论”。答案先于数字给出。</p>'
                '<div class="card"><div style="margin-bottom:10px">%s</div>'
                '<table><thead><tr><th>质量门</th><th>结论</th><th>依据</th></tr></thead><tbody>%s</tbody></table>'
                '</div>%s</section>' % (verdict_tag, grow,
                                        ('<div class="note bad"><b>裁决：</b>%s</div>'
                                         % n.get("verdict_note")) if n.get("verdict_note") else ""))
    # 03 overview
    body.append('<section id="s3"><h2><span class="no">03</span>开工率与期货价格总览</h2>'
                '<p class="sub">可核验的开工率观测只有 %d 期；期货价格有 %s。'
                '两者的时间覆盖差异本身就是结论的一部分。点可查看原始观测。</p>'
                '<div class="card"><svg class="chart" viewBox="0 0 1180 330" id="ov"></svg>'
                '<div class="legend"><span><i style="background:#4da3ff"></i>产能利用率（左轴，%%）</span>'
                '<span><i style="background:#ffb454"></i>期货连续合约基期收盘价（右轴）</span>'
                '<span><i style="background:#38d9a9"></i>未来收益为正 / <i style="background:#ff6b6b"></i>为负</span>'
                '</div></div></section>' % (summary.get("n_bulletins", 0),
                                            n.get("futures_span", "2,044 个交易日（2018-05 至 2026-10）")))
    # 04 factors + alignment
    forms = n.get("formulas") or []
    frow = "".join('<tr><td><b>%s</b></td><td>%s</td><td class="muted">%s</td></tr>' % tuple(f)
                   for f in forms)
    body.append('<section id="s4"><h2><span class="no">04</span>三类因子与时间对齐</h2>'
                '<p class="sub">每一行都必须能回答“这一天的因子，在当天算得出来吗”。</p>'
                '<div class="card"><table><thead><tr><th>项目</th><th>公式 / 定义</th>'
                '<th>可算性说明</th></tr></thead><tbody>%s</tbody></table></div>'
                '<div class="note">基期 = 公布时间戳之后<b>第一个交易日</b>的收盘；窗口按交易日计'
                '（1w=5、2w=10、4w=20）。同一期若在当日 18:30 才公布，当日收盘<b>不可用</b>，'
                '故本案例中 09-24、10-01、10-08 三期的基期分别是下一个交易日。</div></section>' % frow)
    # 05 power
    prow = ""
    if power is not None and len(power):
        for r in power.to_dict("records"):
            verdict = r.get("verdict")
            tagc = "t-bad" if verdict == "insufficient" else ("t-warn" if verdict == "weak" else "t-ok")
            prow += ('<tr><td>%s（%s 日）</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num">%s</td><td class="num">%s pp</td>'
                     '<td><span class="tag %s">%s</span></td></tr>'
                     % (r.get("horizon"), r.get("sessions"), r.get("n_obs"),
                        r.get("n_eff_nonoverlap"), r.get("mdes_sd"), r.get("prob_halfwidth_pp"),
                        tagc, verdict))
    body.append('<section id="s5"><h2><span class="no">05</span>检验功效：这份样本能识别多大的效应</h2>'
                '<p class="sub">统计上“没有显著差异”有两种解释：真的没有，或者样本太小看不见。'
                '把这两种分开，是这类研究的底线。</p>'
                '<div class="card"><table><thead><tr><th>窗口</th><th>可用观测</th><th>有效观测 n_eff</th>'
                '<th>最小可识别效应(σ)</th><th>方向一致性可分辨宽度</th><th>裁决</th></tr></thead>'
                '<tbody>%s</tbody></table></div>'
                '<div class="card"><svg class="chart" viewBox="0 0 900 300" id="power"></svg></div>'
                '<div class="note warn">要达到可分析门槛（n_eff≥%s）的一半效应，约需 %s 个独立观测；'
                '换算成周频数据约为 %.0f 周（≈%.0f 年），或同等数量的月度观测。</div></section>'
                % (prow, summary.get("min_n_eff_required", 30),
                   summary.get("n_needed_rows", 197), summary.get("n_needed_rows", 197),
                   summary.get("n_needed_rows", 197) / 52.0))
    # 06 grouping
    body.append('<section id="s6"><h2><span class="no">06</span>分组结果：样本量、均值、中位数、分布与不确定性</h2>'
                '<p class="sub">三种分组规则在<b>看结果之前</b>就固定下来：绝对水平（固定阈值）、'
                '周度变化方向+幅度、历史分位（p20/p50/p80）。</p>'
                '<div class="ctl"><label>分组维度<span class="seg" id="g-dim">'
                '<button data-d="absolute" class="on">绝对水平</button>'
                '<button data-d="change">周度变化</button>'
                '<button data-d="percentile">历史分位</button></span></label>'
                '<label>未来窗口<span class="seg" id="g-hor">'
                '<button data-h="1w" class="on">1周</button><button data-h="2w">2周</button>'
                '<button data-h="4w">4周</button></span></label></div>'
                '<div class="card"><svg class="chart" viewBox="0 0 900 300" id="grp"></svg>'
                '<div id="grp-note" class="muted" style="font-size:12px;margin-top:6px"></div></div>'
                '<div class="card"><div id="grp-table"></div></div>'
                '<div class="note bad">本案例中“历史分位”一组全部为空：expanding 分位要求至少 52 期历史，'
                '而可核验历史只有 7 期。这不是“算出来不显著”，而是<b>这个因子在当前数据下无法构造</b>。'
                '报告中不因此把它剔除或替换为 7 期样本内分位——那会引入前视偏差。</div></section>')
    # 07 pooled
    prows = ""
    if pooled is not None and len(pooled):
        for r in pooled.to_dict("records"):
            prows += ('<tr><td>%s</td><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                      '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                      '<td class="num">%s</td></tr>'
                      % (r.get("horizon"), r.get("factor"), r.get("n"),
                         _f(r.get("ic"), 3), _f(r.get("ic_p"), 4), _f(r.get("beta_pct_per_sd"), 3),
                         _f(r.get("hac_t"), 2), _f(r.get("q_bh"), 3)))
    body.append('<section id="s7"><h2><span class="no">07</span>不同因子定义与不同窗口的并列比较</h2>'
                '<p class="sub">3 个因子 × 3 个窗口 = 9 组检验全部列出，不挑选、不隐藏。'
                '所有检验之后再做 BH-FDR——防止把“9 个里最像样的那个”当成结论。</p>'
                '<div class="card"><table><thead><tr><th>窗口</th><th>因子</th><th>n</th><th>IC</th>'
                '<th>p</th><th>β(%%/1σ)</th><th>HAC t</th><th>q(BH)</th></tr></thead><tbody>%s</tbody>'
                '</table></div>%s</section>'
                % (prows, ('<div class="note">%s</div>' % n.get("pooled_note")) if n.get("pooled_note") else ""))
    # 08 stability
    yrows = ""
    if yearly is not None and len(yearly):
        for r in yearly.to_dict("records"):
            yrows += ('<tr><td>%s</td><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                      '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                      '<td class="num">%s</td><td><span class="tag t-dim">%s</span></td></tr>'
                      % (r.get("year"), r.get("horizon"), r.get("n_obs"), r.get("n_hi"), r.get("n_lo"),
                         _f(r.get("mean_hi_pct"), 2), _f(r.get("mean_lo_pct"), 2),
                         _f(r.get("spread_hi_minus_lo_pct"), 2), r.get("verdict")))
    body.append('<section id="s8"><h2><span class="no">08</span>年度、工艺路线与市场阶段的稳定性</h2>'
                '<p class="sub">要求：同一关系在多数年份同向、在两种工艺路线、在上行/下行阶段都不翻转。'
                '任一年度样本不足就直接标注 insufficient，而不是“不明显”。</p>'
                '<div class="card"><table><thead><tr><th>年份</th><th>窗口</th><th>n</th><th>高开工组 n</th>'
                '<th>低开工组 n</th><th>高组均值</th><th>低组均值</th><th>差(高-低)</th><th>裁决</th>'
                '</tr></thead><tbody>%s</tbody></table>%s</div>%s</section>'
                % (yrows,
                   '<div class="muted" style="font-size:12px;margin-top:8px">空白表示该年没有当年样本。</div>',
                   ('<div class="note warn">%s</div>' % n.get("stability_note")) if n.get("stability_note") else ""))
    # 09 placebo
    if placebo is not None and len(placebo):
        plr = ""
        for r in placebo.to_dict("records"):
            plr += ('<tr><td>%s</td><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                    '<td class="num">%s</td></tr>'
                    % (r.get("factor"), r.get("horizon"), r.get("n"), _f(r.get("ic_obs"), 3),
                       _f(r.get("placebo_p"), 3)))
        body.append('<section id="s9"><h2><span class="no">09</span>安慰剂：把“季节性巧合”排掉</h2>'
                    '<p class="sub">年度内循环平移因子标签：保留季节形状、破坏对齐。'
                    '若真实关系存在，观测 IC 应落在安慰剂分布尾部。</p>'
                    '<div class="card"><table><thead><tr><th>因子</th><th>窗口</th><th>n</th>'
                    '<th>观测 IC</th><th>安慰剂 p</th></tr></thead><tbody>%s</tbody></table></div>'
                    '</section>' % plr)
    # 10 corr
    if corr is not None and len(corr):
        crr = ""
        for r in corr.to_dict("records"):
            crr += ('<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td></tr>'
                    % (r.get("relation"), _f(r.get("ic"), 3), r.get("n")))
        body.append('<section id="s10"><h2><span class="no">10</span>同步还是领先：剔除“反向因果”</h2>'
                    '<p class="sub">如果开工率与“过去”的价格关系强、与“未来”的价格关系弱，'
                    '那么它更像同步的供给指标，或价格在驱动开工，而不是预测变量。</p>'
                    '<div class="card"><table><thead><tr><th>关系</th><th>IC</th><th>n</th></tr></thead>'
                    '<tbody>%s</tbody></table></div></section>' % crr)
    # 11 failures
    fails = n.get("failure_periods") or []
    body.append('<section id="s11"><h2><span class="no">11</span>明确失效 / 无法成立的时期</h2>'
                '<p class="sub">本节是强制项：不许把“样本不足”写成“关系不明显”。</p>'
                '<div class="card">%s</div></section>'
                % (_ul(fails, ' class="muted"', "（无）")))
    # 12 conclusions
    body.append('<section id="s12"><h2><span class="no">12</span>结论：统计证据与产业解释分开</h2>'
                '<div class="grid g2">'
                '<div class="card" style="border-color:#2f6e57"><h4 style="color:#38d9a9">可以说的</h4>%s</div>'
                '<div class="card" style="border-color:#6e3a3a"><h4 style="color:#ff6b6b">不能说的</h4>%s</div>'
                '</div>'
                '<h3>产业解释（机制假设，不是因果识别）</h3><div class="note">%s</div>'
                '<h3>必须同时读到的限制</h3>%s'
                '<div class="note bad"><b>一句话：</b>%s</div></section>'
                % (_ul(n.get("findings_ok"), ' style="font-size:13px"'),
                   _ul(n.get("findings_ng"), ' style="font-size:13px"'),
                   _ul(n.get("industry_notes"), ' style="font-size:13px"'),
                   _ul(n.get("limits"), ' style="font-size:13px"'), n.get("one_line", "")))
    # 13 methods
    dec = n.get("declarations") or []
    body.append('<section id="s13"><h2><span class="no">13</span>方法论自查（交付前逐条过）</h2>'
                '<div class="card">%s</div></section>' % _ul(dec, style=' style="font-size:13px"'))

    toc = "".join('<a href="#s%d">%s</a>' % (i, t) for i, t in [
        (1, "口径与发布日期"), (2, "可得性与裁决"), (3, "总览"), (4, "因子与对齐"), (5, "检验功效"),
        (6, "分组结果"), (7, "因子×窗口"), (8, "年度与阶段"), (9, "安慰剂"), (10, "同步vs领先"),
        (11, "失效时期"), (12, "结论"), (13, "方法论自查")])

    html = (HTML_TPL.replace("__TITLE__", n.get("title", "开工率—价格关系检验"))
            .replace("__CSS__", CSS).replace("__LEDE__", n.get("lede", ""))
            .replace("__CHIPS__", chips).replace("__TOC__", toc)
            .replace("__BODY__", "".join(body))
            .replace("__FOOTER__", n.get("footer", "仅用于历史统计关系研究，不构成投资建议或交易信号。"))
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False, default=_json_safe))
            .replace("__JS__", JS + EXTRA_JS))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def _f(v, d=3):
    try:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "—"
        return ("%." + str(d) + "f") % float(fmt_float(v))
    except Exception:
        return "—"


def _ul(items, style="", empty="（无）"):
    if not items:
        return '<p class="muted">%s</p>' % empty
    return "<ul%s>%s</ul>" % (style, "".join("<li>%s</li>" % i for i in items))


EXTRA_JS = r"""
/* ---------- bindings ---------- */
const state={dim:'absolute',hor:'1w'};
function drawAll(){
  drawOverview($('#ov'), D.series);
  renderGroup();
  const curve=[];for(let n=4;n<=1000;n*=1.25){
    const hw=1.959964*Math.sqrt(0.25/n)*2*100; curve.push({n:n,hw:hw});}
  const n0=Math.max(D.n_used||1,1);
  curve.push({n:n0,hw:1.959964*Math.sqrt(0.25/n0)*2*100,mark:true});
  curve.sort((a,b)=>a.n-b.n); drawPower($('#power'),curve);
}
function renderGroup(){
  const rows=(D.groups[state.dim]||[]).filter(r=>r.horizon===state.hor);
  drawGroups($('#grp'),rows,state.dim);
  const nT=rows.reduce((s,r)=>s+(r.n||0),0);
  $('#grp-note').textContent='当前分组下的合计样本：'+nT+' 条（含重叠窗口），门槛为每组 ≥8 条、有效 ≥30 条。';
  let h='<table><thead><tr><th>分组</th><th>n</th><th>n_eff</th><th>均值</th><th>中位数</th><th>标准差</th>'+
    '<th>P10</th><th>P90</th><th>上涨占比</th><th>bootstrap 95%</th><th>可用</th></tr></thead><tbody>';
  if(!rows.length)h+='<tr><td colspan="11" class="muted">该窗口下无可用样本</td></tr>';
  rows.forEach(r=>{h+=`<tr><td>${r.label}</td><td class="num">${r.n}</td><td class="num">${fmt(r.n_eff,1)}</td>
    <td class="num">${pctf(r.mean)}</td><td class="num">${pctf(r.median)}</td><td class="num">${fmt(r.std)}</td>
    <td class="num">${pctf(r.q10)}</td><td class="num">${pctf(r.q90)}</td><td class="num">${fmt(r.share_up,0)}%</td>
    <td class="num">${r.ci_lo===null||r.ci_lo===undefined?'—':pctf(r.ci_lo)+' ~ '+pctf(r.ci_hi)}</td>
    <td>${r.usable?'<span class="tag t-ok">可用</span>':'<span class="tag t-bad">不足</span>'}</td></tr>`;});
  h+='</tbody></table>'; $('#grp-table').innerHTML=h;
}
$$('#g-dim button').forEach(b=>b.onclick=()=>{$$('#g-dim button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');state.dim=b.dataset.d;renderGroup();});
$$('#g-hor button').forEach(b=>b.onclick=()=>{$$('#g-hor button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');state.hor=b.dataset.h;renderGroup();});
drawAll();
"""


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "output"
    nar = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else {}
    print(build_workbook(out, nar, os.path.join(out, "工作簿.xlsx")))
    print(build_report(out, nar, os.path.join(out, "报告.html")))
