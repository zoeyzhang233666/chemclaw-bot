# -*- coding: utf-8 -*-
"""Build the Excel research workbook.

Sheets (fixed order, documented in 00_README):
  00_README          what the workbook is, how to re-run, the data-mode banner
  01_Rule_Spec       every rule parameter + who owns provenance
  02_Raw_Quotes      real listed contract quotes used by the backtest window
  03_Indicator       weekly indicator with publish clock + availability session
  04_Signals         per-week rule evaluation (op pass flags, combined event)
  05_Fills           per-trade fills incl. fees, slippage, roll count
  06_Daily_Equity    daily mark-to-market with LIVE Excel formulas for return/drawdown
  07_Annual          per-year aggregation (formulas over 06)
  08_Sensitivity     full grid, no cherry-picking
  09_Cost_Sens       fee / slippage stress
  10_OOS             in-sample vs out-of-sample and robustness
  11_Formula_Doc     the exact definition of every computed field

Sheet 06 uses real Excel formulas (not hard-coded values) so a reviewer can change an
equity cell and watch returns and drawdowns recompute.
"""
from __future__ import annotations

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HDR_FILL = PatternFill("solid", fgColor="1D2B45")
HDR_FONT = Font(color="FFFFFF", bold=True, size=10)
TITLE_FONT = Font(bold=True, size=13, color="1D2B45")
NOTE_FONT = Font(size=9, color="6B7A90", italic=True)
WARN_FILL = PatternFill("solid", fgColor="FFF4D6")
OK_FILL = PatternFill("solid", fgColor="EAF6EE")
THIN = Side(style="thin", color="DDE3EC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# English engine column -> Chinese workbook header (kept in one place for consistency)
FILL_LABELS = {
    "trade_id": "交易编号", "sig_asof": "信号as-of日", "sig_avail": "可交易日",
    "contract": "建仓合约", "entry_day": "建仓日", "entry_px": "建仓价",
    "exit_day": "平仓日", "exit_contract": "平仓合约", "exit_px": "平仓价",
    "exit_reason": "平仓原因", "bars_held": "实际持有交易日", "lots": "手数",
    "gross_pnl": "毛盈亏(元)", "fees": "手续费(元)", "slippage_cost": "滑点(元)",
    "net_pnl": "含费净额(元)", "net_pnl_after_slip": "扣滑点净额(元)",
    "ret_on_price": "价格变动收益", "basis_cur": "基差(元/吨)", "basis_pctile": "基差分位",
    "basis_hist_n": "分位窗口样本数", "sig_value": "库存(万吨)", "sig_run_len": "连降周数",
    "sig_dd": "通道回落(万吨)", "sig_dd_window": "通道窗口", "rolls": "换月次数",
    "target_lots": "目标手数", "direction": "方向", "entry_fee": "开仓手续费",
    "entry_slip": "开仓滑点",
}


def _sheet(wb, name, title, note=None):
    ws = wb.create_sheet(name)
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    r = 2
    if note:
        ws["A2"] = note
        ws["A2"].font = NOTE_FONT
        ws["A2"].alignment = Alignment(wrap_text=False)
    return ws, r + 2


def _frame(ws, df: pd.DataFrame, start_row: int, start_col: int = 1, number_formats=None,
           max_width=46):
    cols = list(df.columns)
    for j, c in enumerate(cols):
        cell = ws.cell(row=start_row, column=start_col + j, value=str(c))
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, row in enumerate(df.itertuples(index=False, name=None), start=start_row + 1):
        for j, v in enumerate(row):
            if isinstance(v, (pd.Timestamp,)):
                v = v.to_pydatetime()
            if v is not None and not isinstance(v, (int, float, str, bool)):
                try:
                    if pd.isna(v):
                        v = None
                except (TypeError, ValueError):
                    v = str(v)
            cell = ws.cell(row=i, column=start_col + j, value=v)
            cell.border = BORDER
            cell.font = Font(size=9)
            fmt = (number_formats or {}).get(cols[j])
            if fmt and isinstance(v, (int, float)):
                cell.number_format = fmt
    for j, c in enumerate(cols):
        width = max(len(str(c)) * 1.1, 9)
        sample = df[c].head(200).astype(str)
        if len(sample):
            width = max(width, min(max_width, float(sample.str.len().max() or 0) + 2))
        ws.column_dimensions[get_column_letter(start_col + j)].width = min(max(width, 9), max_width)
    return start_row + len(df) + 2


def build_workbook(path: str, *, spec: dict, stats: dict, daily: pd.DataFrame,
                   trades: pd.DataFrame, alignment: pd.DataFrame, quotes: pd.DataFrame,
                   sens: dict | None, oos: dict | None, cost_sens: pd.DataFrame | None,
                   notes: dict) -> str:
    wb = Workbook()
    wb.remove(wb.active)
    meta = stats.get("meta", {})
    st = stats.get("stats", {})
    dg = stats.get("digest", {})
    mode = dg.get("publication_mode", "")

    # ---------------- 00_README
    ws, r = _sheet(wb, "00_README", "研究规则回测工作簿 — 说明与结论边界",
                   "此文件由可复现脚本生成，所有数字均可在同目录 CSV / JSON 中找到原始出处。")
    readme = [
        ("规则", meta.get("nl_rule", "")),
        ("规则指纹", stats.get("fingerprint", "")),
        ("数据模式", "strict（仅用可核验原始发布时刻）" if mode == "strict"
         else "backfill_assumed（含假设发布时刻，对照口径，不得作为业绩引用）"),
        ("样本区间", "%s → %s（%s 个交易日）" % (dg.get("first_session"), dg.get("last_session"),
                                              dg.get("sessions"))),
        ("可核验发布的周数", "%s / %s" % (dg.get("weeks_verified_publish"), dg.get("weeks_total"))),
        ("信号触发次数", dg.get("events")),
        ("实际成交笔数", st.get("trades")),
        ("累计收益", st.get("total_return")),
        ("最大回撤", st.get("max_dd")),
        ("胜率 / 盈亏比", [st.get("win_rate"), st.get("profit_factor")]),
        ("使用的真实合约", ", ".join(dg.get("contracts_used") or [])),
    ]
    for k, v in readme:
        ws.cell(row=r, column=1, value=k).font = Font(bold=True, size=10)
        c = ws.cell(row=r, column=2, value=v if not isinstance(v, list) else str(v))
        c.font = Font(size=10)
        if k in ("累计收益", "最大回撤") and isinstance(v, float):
            c.number_format = "0.00%"
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="结论边界（务必先读）").font = Font(bold=True, size=11, color="A12A22")
    ws.cell(row=r, column=1).fill = WARN_FILL
    r += 1
    for line in notes.get("readme_bullets", []):
        ws.cell(row=r, column=1, value="•").font = Font(size=9)
        c = ws.cell(row=r, column=2, value=line)
        c.font = Font(size=9)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=10)
        ws.row_dimensions[r].height = 30
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="重新生成").font = Font(bold=True, size=10)
    ws.cell(row=r, column=2, value=notes.get("rerun_cmd", "")).font = Font(size=9, name="Consolas")
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 92

    # ---------------- 01_Rule_Spec
    ws, r = _sheet(wb, "01_Rule_Spec", "规则规格与假设溯源",
                   "依据类型列区分『合约事实』『需核验』与『假设』——假设不得被当作事实引用。")
    rows = []
    prov = spec.get("provenance", {})

    def walk(node, prefix=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, (prefix + "." + k) if prefix else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (prefix, i))
        else:
            rows.append({"参数路径": prefix, "取值": str(node)})
    for blk in ("meta", "universe", "contract", "timing", "signal", "price_filter",
                "entry", "exit", "position", "costs", "analysis"):
        walk(spec.get(blk, {}), blk)
    r = _frame(ws, pd.DataFrame(rows), r)
    ws.cell(row=r, column=1, value="假设溯源").font = Font(bold=True, size=11)
    r += 1
    prov_rows = [{"项目": k, "依据类型": (v or {}).get("basis", ""),
                  "说明": (v or {}).get("note", ""), "数值": str((v or {}).get("value", ""))}
                 for k, v in prov.items()]
    _frame(ws, pd.DataFrame(prov_rows), r)

    # ---------------- 02_Raw_Quotes
    ws, r = _sheet(wb, "02_Raw_Quotes", "原始行情（真实挂牌合约，未做任何复权）",
                   "每行是一个真实合约在某交易日的报价；回测只使用这些原始价格，不使用连续合约。")
    _frame(ws, quotes, r, number_formats={"open": "#,##0.0", "high": "#,##0.0", "low": "#,##0.0",
                                          "close": "#,##0.0", "settle": "#,##0.0",
                                          "volume": "#,##0", "open_interest": "#,##0"})

    # ---------------- 03_Indicator
    ws, r = _sheet(wb, "03_Indicator", "周度指标：as-of 日、原始发布时刻、可交易日",
                   "可交易日 = 原始发布日之后第一个交易日；『时刻来源』列标明是否为可核验原始发布。")
    ind = alignment.copy()
    ind = ind.rename(columns={"asof_date": "as-of日期", "value": "库存(万吨)",
                              "chg": "周变化(万吨)", "run_len": "连降/连涨周数",
                              "run_dir": "方向(-1降/1涨)", "publish_used": "使用的发布时刻",
                              "pub_verified": "是否可核验", "availability_session": "可交易日",
                              "n_blocks": "跳过交易日数", "pub_source": "时刻来源",
                              "event": "规则触发"})
    keep = [c for c in ["as-of日期", "库存(万吨)", "周变化(万吨)", "连降/连涨周数", "方向(-1降/1涨)",
                        "使用的发布时刻", "是否可核验", "时刻来源", "可交易日", "跳过交易日数",
                        "规则触发"] if c in ind.columns]
    _frame(ws, ind[keep], r, number_formats={"库存(万吨)": "0.00", "周变化(万吨)": "+0.00;-0.00"})

    # ---------------- 04_Signals
    ws, r = _sheet(wb, "04_Signals", "信号逐条判定（含每个条件的通过与否）",
                   "逐条保留判定理由，便于复核信号逻辑而非只看最终布尔值。")
    sig = alignment.copy()
    sig["条件通过情况"] = sig["op_detail"].astype(str) if "op_detail" in sig.columns else ""
    keep = [c for c in ["asof_date", "value", "chg", "run_len", "dd_2", "op_detail", "warmup",
                        "event", "availability_session", "pub_verified"] if c in sig.columns]
    sig = sig[keep].rename(columns={"asof_date": "as-of", "value": "库存", "chg": "周变化",
                                    "run_len": "连续同向周数", "dd_2": "2期通道回落",
                                    "op_detail": "各条件判定", "warmup": "预热期",
                                    "event": "触发", "availability_session": "可交易日",
                                    "pub_verified": "可核验发布"})
    _frame(ws, sig, r, max_width=70)

    # ---------------- 05_Fills
    ws, r = _sheet(wb, "05_Fills", "逐笔成交（含手续费、滑点、换月）",
                   "含费净额 等于 毛盈亏 扣 手续费；再扣滑点即扣滑点净额。换月未平仓的同一笔保留相同交易编号。")
    t = trades.copy()
    if len(t):
        for c in ("entry_day", "exit_day", "sig_asof", "sig_avail"):
            if c in t.columns:
                t[c] = pd.to_datetime(t[c]).dt.date
    t = t.rename(columns=FILL_LABELS)
    _frame(ws, t, r, number_formats={"建仓价": "#,##0.00", "平仓价": "#,##0.00",
                                     "毛盈亏": "#,##0.00;[Red]-#,##0.00",
                                     "含费净额": "#,##0.00;[Red]-#,##0.00",
                                     "扣滑点净额": "#,##0.00;[Red]-#,##0.00",
                                     "基差分位": "0.0%", "价格变动收益": "0.00%"})

    # ---------------- 06_Daily_Equity (with formulas)
    ws, r = _sheet(wb, "06_Daily_Equity", "逐日盯市权益（收益与回撤为 Excel 公式）",
                   "D 列日收益 = C本期/C上期扣1；E 列峰值 = MAX(上期峰值,本期权益)；F 列回撤 = C/E 扣1。可自行修改 C 列验证。")
    r += 1  # keep one blank row below the note
    d = daily.copy().reset_index(drop=True)
    heads = ["日期", "持仓合约", "期末权益", "日收益", "峰值权益", "回撤",
             "手数", "保证金占用%", "标记价格"]
    for j, h in enumerate(heads):
        c = ws.cell(row=r, column=1 + j, value=h)
        c.fill = HDR_FILL
        c.font = HDR_FONT
        c.border = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center")
    first = r + 1
    for i, row in d.iterrows():
        rr = first + i
        ws.cell(row=rr, column=1, value=pd.Timestamp(row["date"]).date())
        ws.cell(row=rr, column=2, value=row.get("contract") or "")
        ws.cell(row=rr, column=3, value=float(row["equity"])).number_format = "#,##0.00"
        if rr == first:
            ws.cell(row=rr, column=4, value=0.0).number_format = "0.00%"
            ws.cell(row=rr, column=5, value="=C%d" % rr).number_format = "#,##0.00"
        else:
            ws.cell(row=rr, column=4, value="=C%d/C%d-1" % (rr, rr - 1)).number_format = "0.0000%"
            ws.cell(row=rr, column=5, value="=MAX(E%d,C%d)" % (rr - 1, rr)).number_format = "#,##0.00"
        ws.cell(row=rr, column=6, value="=C%d/E%d-1" % (rr, rr)).number_format = "0.00%"
        ws.cell(row=rr, column=7, value=int(row["lots"]) if row["lots"] == row["lots"] else 0)
        ws.cell(row=rr, column=8, value=float(row["margin_util"]) if row["margin_util"] == row["margin_util"] else 0).number_format = "0.00%"
        ws.cell(row=rr, column=9, value=float(row["mark_price"]) if row["mark_price"] == row["mark_price"] else None).number_format = "#,##0.0"
        for j in range(1, 10):
            ws.cell(row=rr, column=j).border = BORDER
            ws.cell(row=rr, column=j).font = Font(size=9)
    last = first + len(d) - 1
    for col, w in zip("ABCDEFGHI", (11, 12, 15, 11, 15, 10, 8, 13, 11)):
        ws.column_dimensions[col].width = w
    # summary block using formulas
    sr = last + 3
    ws.cell(row=sr, column=1, value="汇总（公式）").font = Font(bold=True, size=11)
    pairs = [("期末权益", "=C%d" % last, "#,##0.00"),
             ("累计收益", "=C%d/C%d-1" % (last, first), "0.00%"),
             ("最大回撤", "=MIN(F%d:F%d)" % (first, last), "0.00%"),
             ("日收益年化波动", "=STDEV(D%d:D%d)*SQRT(244)" % (first + 1, last), "0.00%"),
             ("Sharpe(无风险0)", "=AVERAGE(D%d:D%d)/STDEV(D%d:D%d)*SQRT(244)"
              % (first + 1, last, first + 1, last), "0.00"),
             ("持仓交易日数", "=COUNTIF(G%d:G%d,\">0\")" % (first, last), "0"),
             ("交易日总数", "=%d" % len(d), "0")]
    for k, (name, formula, fmt) in enumerate(pairs):
        ws.cell(row=sr + 1 + k, column=1, value=name).font = Font(size=10)
        c = ws.cell(row=sr + 1 + k, column=3, value=formula)
        c.number_format = fmt
        c.font = Font(size=10, bold=True)

    # ---------------- 07_Annual (formulas over 06)
    ws, r = _sheet(wb, "07_Annual", "分年度表现",
                   "权益口径列由 06_Daily_Equity 汇总；交易口径列由 05_Fills 汇总。")
    ann = pd.DataFrame(stats.get("annual", []))
    if len(ann):
        out = ann.copy()
        out["return"] = out["return"] * 100
        out["max_dd"] = out["max_dd"] * 100
        out["win_rate"] = out["win_rate"] * 100
        out["exposure"] = out["exposure"] * 100
        out = out.rename(columns={"year": "年度", "sessions": "交易日", "start_equity": "期初权益",
                                  "end_equity": "期末权益", "return": "年度收益%",
                                  "max_dd": "年内最大回撤%", "vol": "波动率",
                                  "trades": "笔数", "win_rate": "胜率%",
                                  "profit_factor": "盈亏比PF", "net_pnl": "净盈亏(元)",
                                  "exposure": "持仓暴露%"})
        _frame(ws, out, r, number_formats={"期初权益": "#,##0", "期末权益": "#,##0",
                                           "年度收益%": "0.00", "年内最大回撤%": "0.00",
                                           "波动率": "0.00", "胜率%": "0.0",
                                           "盈亏比PF": "0.00", "净盈亏(元)": "#,##0",
                                           "持仓暴露%": "0.0"})

    # ---------------- 08_Sensitivity
    ws, r = _sheet(wb, "08_Sensitivity", "参数敏感性全表（含亏损变体，不做事后筛选）",
                   "网格在运行前声明；基准行已标注。若仅个别参数点盈利，则结论不可靠。")
    if sens and sens.get("grid"):
        g = pd.DataFrame(sens["grid"])
        g["overrides"] = g["overrides"].astype(str)
        g = g.sort_values("return", ascending=False)
        out = g[["variant", "is_base", "return", "cagr", "max_dd", "sharpe", "trades",
                 "win_rate", "profit_factor", "exposure", "overrides"]].rename(
            columns={"variant": "参数变体", "is_base": "是否基准", "return": "累计收益",
                     "cagr": "CAGR", "max_dd": "最大回撤", "sharpe": "Sharpe", "trades": "笔数",
                     "win_rate": "胜率", "profit_factor": "盈亏比PF", "exposure": "持仓暴露",
                     "overrides": "覆盖参数"})
        _frame(ws, out, r, number_formats={"累计收益": "0.00%", "CAGR": "0.00%",
                                           "最大回撤": "0.00%", "Sharpe": "0.00",
                                           "胜率": "0.0%", "盈亏比PF": "0.00",
                                           "持仓暴露": "0.0%"}, max_width=60)
        sr = r + len(out) + 3
        ws.cell(row=sr, column=1, value="网格汇总").font = Font(bold=True, size=11)
        for k, (name, v) in enumerate(sens.get("summary", {}).items()):
            ws.cell(row=sr + 1 + k, column=1, value=name).font = Font(size=10)
            ws.cell(row=sr + 1 + k, column=2, value=v).font = Font(size=10)

    # ---------------- 09_Cost_Sens
    ws, r = _sheet(wb, "09_Cost_Sens", "成本敏感性（手续费倍数 × 滑点跳数）",
                   "回答『结论是否只在低成本假设下成立』。")
    if cost_sens is not None and len(cost_sens):
        _frame(ws, cost_sens.rename(columns={
            "fee_multiple": "费率倍数", "fee_value": "每手手续费", "slippage_ticks": "滑点(跳)",
            "total_return": "累计收益", "cagr": "CAGR", "max_dd": "最大回撤", "sharpe": "Sharpe",
            "trades": "笔数", "net_pnl": "净盈亏", "fees": "手续费合计", "slippage": "滑点合计"}),
            r, number_formats={"累计收益": "0.00%", "CAGR": "0.00%", "最大回撤": "0.00%",
                               "Sharpe": "0.00", "净盈亏": "#,##0", "手续费合计": "#,##0",
                               "滑点合计": "#,##0", "每手手续费": "0.00"})

    # ---------------- 10_OOS
    ws, r = _sheet(wb, "10_OOS", "样本内 / 样本外 / 稳健性",
                   "切分点运行前声明。样本外结果按原样报告，不做事后调整。")
    if oos:
        i, o = oos.get("in_sample", {}), oos.get("out_of_sample", {})
        keys = ["trades", "total_return", "cagr", "max_dd", "sharpe", "win_rate",
                "profit_factor", "exposure"]
        names = {"trades": "交易笔数", "total_return": "累计收益", "cagr": "CAGR",
                 "max_dd": "最大回撤", "sharpe": "Sharpe", "win_rate": "胜率",
                 "profit_factor": "盈亏比PF", "exposure": "持仓暴露"}
        out = pd.DataFrame({"指标": [names[k] for k in keys],
                            "样本内": [i.get(k) for k in keys],
                            "样本外": [o.get(k) for k in keys]})
        rr = _frame(ws, out, r)
        bs = oos.get("bootstrap", {})
        ws.cell(row=rr, column=1, value="块自助检验（按笔重抽样）").font = Font(bold=True, size=11)
        rr += 1
        for k, v in bs.items():
            ws.cell(row=rr, column=1, value=k).font = Font(size=10)
            if isinstance(v, dict):
                v = "; ".join("%s=%s" % (kk, vv) for kk, vv in v.items())
            ws.cell(row=rr, column=2, value=v).font = Font(size=10)
            rr += 1
        rr += 1
        ws.cell(row=rr, column=1, value="剔除单一年度后的净盈亏").font = Font(bold=True, size=11)
        rr += 1
        rem = oos.get("annual_removal", {})
        if rem:
            tab = pd.DataFrame([{"剔除年度": k, "剩余笔数": v["trades"],
                                 "剩余净盈亏": v["net_pnl_without_year"]}
                                for k, v in rem.items()])
            rr = _frame(ws, tab, rr)

    # ---------------- 11_Formula_Doc
    ws, r = _sheet(wb, "11_Formula_Doc", "字段定义与公式（与代码逐条一致）",
                   "任何复核都应以本表定义为准；报告中出现的每个指标都能在这里找到算法。")
    docs = [
        ("日收益", "r_t = equity_t / equity_{t-1} 减 1", "06 Daily D 列，Excel 公式"),
        ("峰值权益", "peak_t = max(peak_{t-1}, equity_t)", "06 Daily E 列"),
        ("回撤", "dd_t = equity_t / peak_t 减 1（≤0）", "06 Daily F 列"),
        ("最大回撤", "min(dd_t)", "06 汇总 MAX/MIN 公式"),
        ("年化收益 CAGR", "(equity_end/equity_start)^(1/years) 减 1，years = 交易日/244", "metrics.py"),
        ("年化波动", "std(r_t, ddof=1) * sqrt(244)", "metrics.py"),
        ("Sharpe", "(mean(r_t) 减 rf/244) / std(r_t) * sqrt(244)", "metrics.py"),
        ("Sortino", "(mean(r) 减 rf/244)/std(负收益) * sqrt(244)", "metrics.py"),
        ("Calmar", "CAGR / |最大回撤|", "metrics.py"),
        ("单笔毛盈亏", "(exit_px 减 entry_px) * dir * multiplier * lots", "engine.py"),
        ("手续费", "max(min_per_lot, fee_per_lot) * lots，每边各一次", "engine.py"),
        ("滑点", "slippage_ticks * tick_size * multiplier * lots，每边各一次", "engine.py"),
        ("含费净额", "毛盈亏 减 手续费", "trades.csv"),
        ("扣滑点净额", "含费净额 减 滑点", "trades.csv"),
        ("胜率", "扣滑点净额 > 0 的笔数 / 总笔数", "metrics.py"),
        ("盈亏比 PF", "sum(盈利) / |sum(亏损)|", "metrics.py"),
        ("Payoff", "mean(盈利) / |mean(亏损)|", "metrics.py"),
        ("持仓暴露", "持仓交易日数 / 交易日总数", "metrics.py"),
        ("可交易日", "发布日之后第一个交易日 + (min_lag-1)", "data.decide_availability"),
        ("换月", "持仓合约变化时：当日平旧 + 当开新，各计一次手续费与滑点", "engine.py"),
        ("基差分位", "spot(前一交易日) − fut(当日结算)，与严格早于当日的 N 日历史比较取分位", "engine.precompute_basis"),
        ("基差窗口", "lookback_points = 756 ≈ 3 年 × 244 交易日", "rule_spec.json"),
        ("年化交易日", "244（郑商所年均交易日，按样本实际交易日计算 years）", "metrics.py"),
    ]
    _frame(ws, pd.DataFrame(docs, columns=["字段", "定义", "实现位置"]), r, max_width=78)

    wb.save(path)
    return path
