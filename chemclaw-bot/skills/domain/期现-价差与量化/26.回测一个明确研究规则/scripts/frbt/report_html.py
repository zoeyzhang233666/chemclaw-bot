# -*- coding: utf-8 -*-
"""Build the self-contained interactive research platform (single HTML file).

Design constraints (must hold for any product, not just methanol):
  * one file, no CDN, no network: everything inlined so it can be emailed or opened offline;
  * charts drawn with inline SVG generated in Python -> no JS chart library needed;
  * filters/aggregations in vanilla JS over embedded JSON payloads;
  * the data-mode banner (verified vs assumed publication clock) is always visible,
    so a screenshot can never pass an assumed clock off as a verified one.
"""
from __future__ import annotations

import json
import io
import os
from datetime import datetime

import pandas as pd


def _svg_path(xs: list[float], ys: list[float], width: int, height: int, pad: int,
              ymin: float | None = None, ymax: float | None = None,
              invert: bool = False) -> tuple[str, float, float]:
    if not xs:
        return "", 0.0, 0.0
    lo = min(ys) if ymin is None else ymin
    hi = max(ys) if ymax is None else ymax
    if hi == lo:
        hi = lo + 1
    n = len(xs)
    x0 = min(xs)
    x1 = max(xs) or 1
    span = (x1 - x0) or 1
    pts = []
    for x, y in zip(xs, ys):
        px = pad + (x - x0) / span * (width - 2 * pad)
        py = pad + (hi - y) / (hi - lo) * (height - 2 * pad)
        if invert:
            py = pad + (y - lo) / (hi - lo) * (height - 2 * pad)
        pts.append("%.2f,%.2f" % (px, py))
    return " ".join(pts), lo, hi


def _line_chart(dates, series_list, width=980, height=320, pad=46, invert=False,
                y_fmt="{:,.0f}", colors=None, fill_first=False):
    """series_list = [(label, values, color), ...]"""
    colors = colors or ["#2f6fd0", "#d9534f", "#4a9b6e"]
    xs = list(range(len(dates)))
    allv = [v for _, vals, _ in series_list for v in vals if v is not None and v == v]
    if not allv:
        return "<svg width='%d' height='%d'></svg>" % (width, height)
    body = []
    # grid + y axis labels
    lo, hi = min(allv), max(allv)
    pad_v = (hi - lo) * 0.08 or 1
    lo2, hi2 = lo - pad_v, hi + pad_v
    for k in range(5):
        y = pad + k / 4 * (height - 2 * pad)
        val = hi2 - k / 4 * (hi2 - lo2)
        body.append("<line x1='%d' y1='%.2f' x2='%d' y2='%.2f' stroke='#e6eaf0'/>"
                    % (pad, y, width - pad, y))
        body.append("<text x='6' y='%.2f' font-size='10' fill='#7a8698'>%s</text>"
                    % (y + 3, y_fmt.format(val)))
    for label, vals, color in series_list:
        pts, _, _ = _svg_path(xs, vals, width, height, pad, ymin=lo2, ymax=hi2, invert=invert)
        if fill_first and label == series_list[0][0]:
            poly = pts + " %.2f,%d %.2f,%d" % (width - pad, height - pad, pad, height - pad)
            body.append("<polygon points='%s' fill='%s' opacity='0.10'/>" % (poly, color))
        body.append("<polyline points='%s' fill='none' stroke='%s' stroke-width='1.6'/>"
                    % (pts, color))
    # x labels (first / middle / last)
    for frac in (0, 0.5, 1):
        i = int(frac * (len(dates) - 1))
        x = pad + frac * (width - 2 * pad)
        anchor = "start" if frac == 0 else ("end" if frac == 1 else "middle")
        body.append("<text x='%.2f' y='%d' font-size='10' fill='#7a8698' text-anchor='%s'>%s</text>"
                    % (x, height - 8, anchor, dates[i]))
    legend = []
    for i, (label, _, color) in enumerate(series_list):
        legend.append("<rect x='%d' y='12' width='10' height='3' fill='%s'/><text x='%d' y='18' "
                      "font-size='10' fill='#43506b'>%s</text>" % (pad + i * 150, color,
                                                                  pad + i * 150 + 14, label))
    return ("<svg viewBox='0 0 %d %d' width='100%%' style='max-width:%dpx'>%s%s</svg>"
            % (width, height, width, "".join(legend), "".join(body)))


def _bar_chart(labels, values, width=980, height=260, pad=46):
    if not values:
        return ""
    lo, hi = min(min(values), 0), max(max(values), 0)
    if hi == lo:
        hi = lo + 1
    span = hi - lo or 1
    zero_y = pad + (hi - 0) / span * (height - 2 * pad)
    bw = (width - 2 * pad) / max(1, len(values)) * 0.62
    body = ["<line x1='%d' y1='%.2f' x2='%d' y2='%.2f' stroke='#c8d0dc'/>"
            % (pad, zero_y, width - pad, zero_y)]
    for i, v in enumerate(values):
        cx = pad + (i + 0.5) * (width - 2 * pad) / max(1, len(values))
        y = pad + (hi - v) / span * (height - 2 * pad)
        top = min(y, zero_y)
        h = abs(zero_y - y)
        color = "#4a9b6e" if v >= 0 else "#d9534f"
        body.append("<rect x='%.2f' y='%.2f' width='%.2f' height='%.2f' fill='%s' rx='2'/>"
                    % (cx - bw / 2, top, bw, max(h, 0.8), color))
        body.append("<text x='%.2f' y='%.2f' font-size='9' fill='#556' text-anchor='middle'>%s</text>"
                    % (cx, height - 10, labels[i]))
        body.append("<text x='%.2f' y='%.2f' font-size='9' fill='#556' text-anchor='middle'>%s</text>"
                    % (cx, top - 3 if v >= 0 else top + h + 10, "{:,.0f}".format(v)))
    return ("<svg viewBox='0 0 %d %d' width='100%%' style='max-width:%dpx'>%s</svg>"
            % (width, height, width, "".join(body)))


CSS = """
:root{--ink:#1b2436;--muted:#6b7a90;--line:#e3e9f2;--bg:#f6f8fb;--card:#fff;
--accent:#2f6fd0;--green:#2e8b57;--red:#c0392b;--amber:#c87f0a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Segoe UI","Microsoft YaHei",system-ui,-apple-system,sans-serif;font-size:13px;line-height:1.6}
header{background:linear-gradient(135deg,#1d2b45,#2c4a7a);color:#fff;padding:22px 30px}
header h1{margin:0 0 6px;font-size:20px;font-weight:600;letter-spacing:.2px}
header .sub{color:#b7c6e0;font-size:12px}
.banner{margin:14px 30px 0;padding:11px 16px;border-radius:8px;font-size:12.5px;border:1px solid}
.banner.warn{background:#fff8e6;border-color:#f0d48a;color:#7a5300}
.banner.ok{background:#eef7f1;border-color:#bfe0cb;color:#1f5f3c}
.banner.bad{background:#fdeeee;border-color:#f2bcbc;color:#8b2020}
.banner b{font-weight:700}
nav{display:flex;gap:4px;flex-wrap:wrap;margin:16px 30px 0;border-bottom:1px solid var(--line)}
nav button{background:none;border:none;padding:9px 15px;font-size:13px;color:var(--muted);
cursor:pointer;border-bottom:2px solid transparent;font-family:inherit}
nav button.active{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
main{padding:18px 30px 60px;max-width:1280px}
section{display:none}section.active{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;
margin-bottom:16px;box-shadow:0 1px 2px rgba(20,30,50,.04)}
.card h2{margin:0 0 4px;font-size:15px;font-weight:600}
.card h3{margin:16px 0 8px;font-size:13px;font-weight:600;color:#334}
.card .note{color:var(--muted);font-size:12px;margin:0 0 12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{background:#fbfcfe;border:1px solid var(--line);border-radius:9px;padding:12px 14px}
.kpi .k{color:var(--muted);font-size:11.5px;letter-spacing:.3px}
.kpi .v{font-size:20px;font-weight:650;margin-top:3px;font-variant-numeric:tabular-nums}
.kpi .h{color:var(--muted);font-size:11px;margin-top:2px}
.pos{color:var(--green)}.neg{color:var(--red)}.neu{color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:12.2px}
th,td{padding:6px 9px;text-align:right;border-bottom:1px solid var(--line);
font-variant-numeric:tabular-nums}
th{background:#f2f5f9;color:#465268;font-weight:600;position:sticky;top:0;text-align:right;
white-space:nowrap}
th:first-child,td:first-child{text-align:left}
tbody tr:hover{background:#f7fafd}
.scroll{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}
.tag{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11px;font-weight:600}
.tag.g{background:#e6f4ec;color:#1f6b41}.tag.r{background:#fdeaea;color:#a12a22}
.tag.a{background:#fdf3e0;color:#8a5a05}.tag.b{background:#e9f0fb;color:#2559a8}
.heat td{color:#fff;text-align:center;font-weight:600;font-size:11.5px}
.ctrl{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:12px;font-size:12.5px}
select,input[type=text]{font-family:inherit;font-size:12.5px;padding:5px 8px;border:1px solid #cfd8e6;
border-radius:6px;background:#fff;color:var(--ink)}
code{background:#eef2f8;padding:1px 5px;border-radius:4px;font-size:11.5px}
.flag{font-size:11.5px;padding:2px 8px;border-radius:6px;font-weight:600}
ul.tight{margin:6px 0 0;padding-left:20px}ul.tight li{margin:4px 0}
.foot{color:var(--muted);font-size:11.5px;margin-top:26px;border-top:1px solid var(--line);
padding-top:12px}
"""


def build_html(stats: dict, daily: pd.DataFrame, trades: pd.DataFrame, alignment: pd.DataFrame,
               sens: dict | None, oos: dict | None, cost_sens: pd.DataFrame | None,
               spec: dict, out_path: str, extra: dict | None = None) -> str:
    extra = extra or {}
    mode = stats.get("digest", {}).get("publication_mode", "unknown")
    meta = stats.get("meta", {})
    st = stats.get("stats", {})
    dg = stats.get("digest", {})

    # ---------- payloads for JS
    daily_js = {
        "date": [str(d)[:10] for d in daily["date"]],
        "equity": [round(float(v), 2) for v in daily["equity"]],
        "drawdown": [round(float(v) * 100, 3) for v in daily["drawdown"]],
        "lots": [int(v) if v == v else 0 for v in daily["lots"]],
        "contract": [("" if (c is None or (isinstance(c, float) and pd.isna(c))) else str(c))
                     for c in daily["contract"]],
        "margin_util": [round(float(v) * 100, 3) if v == v else 0 for v in daily["margin_util"]],
        "daily_return": [round(float(v) * 100, 4) for v in daily["daily_return"]],
    }
    tcols = ["trade_id", "sig_asof", "sig_avail", "contract", "entry_day", "entry_px",
             "exit_day", "exit_contract", "exit_px", "exit_reason", "bars_held", "lots",
             "gross_pnl", "fees", "slippage_cost", "net_pnl_after_slip", "basis_cur",
             "basis_pctile", "sig_value", "sig_run_len", "rolls"]
    has = [c for c in tcols if c in trades.columns]
    trades_js = {"cols": has, "rows": [
        [("" if (v is None or (isinstance(v, float) and pd.isna(v))) else
          (str(v)[:10] if c.endswith("_day") or c.endswith("_asof") or c.endswith("_avail")
           else (round(float(v), 4) if isinstance(v, (int, float)) else str(v))))
         for c, v in zip(has, row)]
        for row in trades[has].itertuples(index=False, name=None)]}

    # ---------- charts
    dates = [str(d)[:10] for d in daily["date"]]
    eq_svg = _line_chart(dates, [("权益曲线 equity (CNY)", daily["equity"].tolist(), "#2f6fd0")],
                         height=300, y_fmt="{:,.0f}", fill_first=True)
    dd_svg = _line_chart(dates, [("回撤 drawdown (%)", (daily["drawdown"] * 100).tolist(), "#c0392b")],
                         height=200, y_fmt="{:,.1f}", invert=True, fill_first=True)
    ann = pd.DataFrame(stats.get("annual", []))
    ann_svg = _bar_chart([str(int(y)) for y in ann["year"]], ann["net_pnl"].round(0).tolist()) \
        if len(ann) else ""

    # ---------- banner
    verified = dg.get("weeks_verified_publish", 0)
    total = dg.get("weeks_total", 0)
    if mode == "strict":
        cls, txt = "ok", ("<b>数据模式：strict（仅用可核验原始发布时刻）</b> — %d / %d 周指标的原始发布时刻可核验，"
                          "其余 %d 周被排除在信号样本之外。信号只在原始发布后第一个交易日才可交易。"
                          % (verified, total, total - verified))
    else:
        cls, txt = "warn", ("<b>数据模式：backfill_assumed（对照口径，非主结论）</b> — 对未核验周使用 "
                            "as-of 日 14:00 的<b>假设</b>发布时间。此模式仅用于暴露数据缺口对结论的影响，"
                            "不得作为策略表现引用。")

    # ---------- sensitivity heat table
    sens_rows = ""
    if sens and sens.get("grid"):
        g = pd.DataFrame(sens["grid"])
        g = g.sort_values("return", ascending=False)
        lo, hi = g["return"].min(), g["return"].max()
        for _, r in g.iterrows():
            t = (r["return"] - lo) / (hi - lo) if hi > lo else 0.5
            # diverging ramp red -> neutral -> green
            if t < 0.5:
                p = t / 0.5
                bg = "rgb(%d,%d,%d)" % (int(192 + (245 - 192) * p), int(57 + (245 - 57) * p),
                                        int(43 + (240 - 43) * p))
                fg = "#fff" if p < 0.6 else "#333"
            else:
                p = (t - 0.5) / 0.5
                bg = "rgb(%d,%d,%d)" % (int(245 - (245 - 46) * p), int(245 - (155 - 46) * p) * 0 +
                                         int(240 - (240 - 110) * p),
                                        int(240 - (240 - 80) * p))
                fg = "#fff"
            tag = " <span class='tag b'>基准</span>" if r.get("is_base") else ""
            sens_rows += ("<tr><td style='text-align:left'>%s%s</td>"
                          "<td class='heat' style='background:%s;color:%s'>%+.2f%%</td>"
                          "<td>%+.2f%%</td><td>%.2f%%</td><td>%s</td><td>%d</td>"
                          "<td>%s</td><td>%s</td></tr>") % (
                r["variant"], tag, bg,
                fg, r["return"] * 100, (r["cagr"] or 0) * 100, (r["max_dd"] or 0) * 100,
                "{:.2f}".format(r["sharpe"]) if r["sharpe"] == r["sharpe"] else "—",
                int(r["trades"]),
                "{:.1%}".format(r["win_rate"]) if r["win_rate"] == r["win_rate"] else "—",
                "{:.2f}".format(r["profit_factor"]) if r["profit_factor"] == r["profit_factor"]
                else "—")
    sens_summary = sens.get("summary", {}) if sens else {}

    cost_rows = ""
    if cost_sens is not None and len(cost_sens):
        for _, r in cost_sens.iterrows():
            cost_rows += ("<tr><td style='text-align:left'>%.1f×</td><td>%.2f</td><td>%+.2f%%</td>"
                          "<td>%.2f%%</td><td>%d</td><td>%s</td></tr>") % (
                r["fee_multiple"], r["slippage_ticks"], r["total_return"] * 100,
                r["max_dd"] * 100, int(r["trades"]),
                "{:,.0f}".format(r["net_pnl"]))

    oos_html = ""
    if oos:
        i, o = oos.get("in_sample", {}), oos.get("out_of_sample", {})

        def _row(name, a, b):
            return ("<tr><td style='text-align:left'>%s</td><td>%s</td><td>%s</td></tr>"
                    % (name, a, b))
        bs = oos.get("bootstrap", {})
        oos_html = """
        <table><thead><tr><th>指标</th><th>样本内 (至 %s)</th><th>样本外 (%s 起)</th></tr></thead><tbody>
        %s %s %s %s %s %s %s
        </tbody></table>""" % (
            oos.get("split_date"), oos.get("split_date"),
            _row("交易笔数", i.get("trades", 0), o.get("trades", 0)),
            _row("累计收益", "%+.2f%%" % ((i.get("total_return") or 0) * 100),
                 "%+.2f%%" % ((o.get("total_return") or 0) * 100)),
            _row("最大回撤", "%.2f%%" % ((i.get("max_dd") or 0) * 100),
                 "%.2f%%" % ((o.get("max_dd") or 0) * 100)),
            _row("胜率", "{:.1%}".format(i.get("win_rate")) if i.get("win_rate") == i.get("win_rate")
                 else "—", "{:.1%}".format(o.get("win_rate")) if o.get("win_rate") == o.get("win_rate")
                 else "—"),
            _row("盈亏比", "{:.2f}".format(i.get("profit_factor")) if i.get("profit_factor") ==
                 i.get("profit_factor") else "—",
                 "{:.2f}".format(o.get("profit_factor")) if o.get("profit_factor") ==
                 o.get("profit_factor") else "—"),
            _row("Sharpe", "{:.2f}".format(i.get("sharpe")) if i.get("sharpe") == i.get("sharpe")
                 else "—", "{:.2f}".format(o.get("sharpe")) if o.get("sharpe") == o.get("sharpe")
                 else "—"),
            _row("块自助检验 均值&gt;0 概率",
                 "—", "{:.1%}".format(bs.get("p_positive")) if bs.get("p_positive") is not None
                 else "—"))

    annual_rows = ""
    if len(ann):
        for _, r in ann.iterrows():
            annual_rows += ("<tr><td style='text-align:left'>%d</td><td>%d</td><td>%s</td>"
                            "<td>%s</td><td class='%s'>%+.2f%%</td><td>%.2f%%</td><td>%d</td>"
                            "<td>%s</td><td>%s</td><td class='%s'>%s</td></tr>") % (
                int(r["year"]), int(r["sessions"]), "{:,.0f}".format(r["start_equity"]),
                "{:,.0f}".format(r["end_equity"]), "pos" if r["return"] >= 0 else "neg",
                r["return"] * 100, r["max_dd"] * 100, int(r["trades"]),
                "{:.1%}".format(r["win_rate"]) if r["win_rate"] == r["win_rate"] else "—",
                "{:.2f}".format(r["profit_factor"]) if r["profit_factor"] == r["profit_factor"]
                else "—", "pos" if r["net_pnl"] >= 0 else "neg", "{:,.0f}".format(r["net_pnl"]))

    align_rows = ""
    for _, r in alignment.iterrows():
        ev = bool(r.get("event"))
        av = r.get("availability_session")
        ver = bool(r.get("pub_verified"))
        align_rows += ("<tr data-ev='%d' data-ver='%d'><td style='text-align:left'>%s</td>"
                       "<td>%s</td><td>%s</td>"
                       "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                       "<td style='text-align:center'>%s</td></tr>") % (
            1 if ev else 0, 1 if ver else 0,
            str(r["asof_date"])[:10], "{:.2f}".format(r["value"]),
            "{:+.2f}".format(r["chg"]) if r["chg"] == r["chg"] else "—",
            "{}".format(int(r["run_len"])), "{}".format(int(r["run_dir"])),
            str(r.get("publish_used"))[:16] if pd.notna(r.get("publish_used")) else "—",
            "✔ 可核验" if ver else "假设时刻",
            str(av)[:10] if pd.notna(av) else "<span class='tag r'>不可用</span>",
            "<span class='tag g'>是</span>" if ev else "")

    roll_rows = ""
    for _, r in pd.DataFrame(stats.get("rolls", [])).iterrows() if stats.get("rolls") else []:
        pass

    prov = spec.get("provenance", {})
    prov_rows = "".join(
        "<tr><td style='text-align:left'>%s</td><td style='text-align:left'>%s</td>"
        "<td style='text-align:left'>%s</td></tr>" % (
            k, (v or {}).get("basis", ""), (v or {}).get("note", "") if isinstance(v, dict) else v)
        for k, v in prov.items())


    # ---- assemble with literal placeholders (CSS/JS contain % signs)
    html = _TEMPLATE
    vals = {
        "title": meta.get("title", "rule backtest"),
        "nl": meta.get("nl_rule", ""),
        "css": CSS,
        "fp": stats.get("fingerprint", ""),
        "first": dg.get("first_session", ""),
        "last": dg.get("last_session", ""),
        "sessions": dg.get("sessions", len(daily)),
        "events": dg.get("events", 0),
        "ntr": int(st.get("trades", 0)),
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "bcls": cls, "btxt": txt,
        "ret": "%+.2f%%" % ((st.get("total_return") or 0) * 100),
        "cls_ret": "pos" if (st.get("total_return") or 0) >= 0 else "neg",
        "cagr": "%+.2f%%" % ((st.get("cagr") or 0) * 100),
        "cls_cagr": "pos" if (st.get("cagr") or 0) >= 0 else "neg",
        "years": "%.2f" % (st.get("years") or 0),
        "end_eq": "{:,.0f}".format(st.get("end_equity") or 0),
        "mdd": "%.2f%%" % ((st.get("max_dd") or 0) * 100),
        "mdd_range": "%s to %s" % (str(st.get("max_dd_start"))[:10],
                                   str(st.get("max_dd_trough"))[:10]),
        "hold": "%.1f" % (st.get("avg_hold_sessions") or 0),
        "win": "{:.1%}".format(st.get("win_rate")) if st.get("win_rate") == st.get("win_rate")
        else "n/a",
        "pf": "{:.2f}".format(st.get("profit_factor"))
        if st.get("profit_factor") == st.get("profit_factor") else "n/a",
        "payoff": "{:.2f}".format(st.get("payoff_ratio"))
        if st.get("payoff_ratio") == st.get("payoff_ratio") else "n/a",
        "sharpe": "{:.2f}".format(st.get("sharpe")) if st.get("sharpe") == st.get("sharpe") else "n/a",
        "rf": "%.1f%%" % (float(spec.get("analysis", {}).get("metrics", {}).get("rf_annual", 0)) * 100),
        "expo": "{:.1%}".format(st.get("exposure") or 0),
        "mmu": "{:.2f}%".format((st.get("max_margin_util") or 0) * 100),
        "eq_svg": eq_svg, "dd_svg": dd_svg, "ann_svg": ann_svg,
        "annual_rows": annual_rows,
        "gross": "{:,.0f}".format(st.get("gross_pnl") or 0),
        "fees": "{:,.0f}".format(st.get("fees") or 0),
        "slip": "{:,.0f}".format(st.get("slippage") or 0),
        "netpnl": "{:,.0f}".format(st.get("net_pnl") or 0),
        "nvar": sens_summary.get("n_variants", 0),
        "med_ret": "%+.2f%%" % ((sens_summary.get("median_return") or 0) * 100),
        "share_pos": "{:.0%}".format(sens_summary.get("share_positive_return") or 0),
        "best": "%+.2f%%" % ((sens_summary.get("best_return") or 0) * 100),
        "worst": "%+.2f%%" % ((sens_summary.get("worst_return") or 0) * 100),
        "rank": "%s / %s" % (sens_summary.get("base_return_rank", "-"),
                             sens_summary.get("n_variants", "-")),
        "sens_rows": sens_rows or "<tr><td colspan='8'>sensitivity not run</td></tr>",
        "cost_rows": cost_rows or "<tr><td colspan='6'>cost sensitivity not run</td></tr>",
        "oos_html": oos_html or "<p class='note'>OOS not run</p>",
        "robust": extra.get("robust_html", "<p class='note'>-</p>"),
        "sig_desc": extra.get("sig_desc", ""),
        "pf_desc": extra.get("pf_desc", ""),
        "timing": extra.get("timing", ""),
        "contract": extra.get("contract", ""),
        "entry": extra.get("entry", ""),
        "exit": extra.get("exit", ""),
        "position": extra.get("position", ""),
        "costs": extra.get("costs", ""),
        "roll": extra.get("roll", ""),
        "prov_rows": prov_rows,
        "align_rows": align_rows,
        "limit_note": extra.get("limit_note", ""),
        "margin": "{:.0%}".format(float(spec.get("costs", {}).get("margin_rate", 0.1))),
        "gap": extra.get("gap", ""),
        "spot_note": extra.get("spot_note", ""),
        "diag_rows": extra.get("diag_rows", ""),
        "daily_js": json.dumps(daily_js, ensure_ascii=False),
        "trades_js": json.dumps(trades_js, ensure_ascii=False),
    }
    for k, v in vals.items():
        html = html.replace("{{" + k + "}}", str(v))
    if "{{" in html:
        raise RuntimeError("unfilled template placeholder remains")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def _load_template() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    with io.open(os.path.join(here, "template.html"), encoding="utf-8") as f:
        return f.read()


_TEMPLATE = _load_template()
