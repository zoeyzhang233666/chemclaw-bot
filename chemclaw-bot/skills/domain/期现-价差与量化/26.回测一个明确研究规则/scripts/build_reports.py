# -*- coding: utf-8 -*-
"""Turn the engine's raw outputs into the deliverables (HTML platform + Excel workbook).

    python build_reports.py --config configs/x.json --out out_dir [--tag strict]

Reads out_dir/stats.json, daily_equity.csv, trades.csv, signal_alignment.csv,
sensitivity.json, oos.json, cost_sensitivity.csv and writes:
    <out>/research_platform.html
    <out>/backtest_workbook.xlsx
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from frbt.report_html import build_html  # noqa: E402
from frbt.report_xlsx import build_workbook  # noqa: E402
from frbt.spec import load_spec  # noqa: E402


def _maybe_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _maybe_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)

    spec = load_spec(a.config).raw
    out = a.out
    stats = _maybe_json(os.path.join(out, "stats.json"))
    if stats is None:
        raise SystemExit("run the backtest first: stats.json missing in %s" % out)
    daily = pd.read_csv(os.path.join(out, "daily_equity.csv"))
    daily["date"] = pd.to_datetime(daily["date"])
    trades = _maybe_csv(os.path.join(out, "trades.csv"))
    if trades is None:
        trades = pd.DataFrame()
    align = pd.read_csv(os.path.join(out, "signal_alignment.csv"))
    sens = _maybe_json(os.path.join(out, "sensitivity.json"))
    oos = _maybe_json(os.path.join(out, "oos.json"))
    cost = _maybe_csv(os.path.join(out, "cost_sensitivity.csv"))

    # raw quotes limited to the backtest window for the workbook
    base = os.path.dirname(os.path.abspath(a.config))
    d = spec["data"]

    def res(p):
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
    quotes = pd.read_csv(res(d["contracts_file"]))
    quotes["date"] = pd.to_datetime(quotes["date"])
    lo, hi = daily["date"].min(), daily["date"].max()
    used = sorted(daily["contract"].dropna().unique().tolist())
    quotes = quotes[(quotes["date"] >= lo) & (quotes["date"] <= hi)]
    # keep the contracts actually held plus any that were ranked near the top
    quotes = quotes[quotes["contract"].isin(used)]
    quotes = quotes.sort_values(["date", "contract"])

    dg = stats.get("digest", {})
    st = stats.get("stats", {})
    mode = dg.get("publication_mode", "")
    verified = dg.get("weeks_verified_publish", 0)
    total = dg.get("weeks_total", 0)

    sig_cfg = spec["signal"]
    pf = spec["price_filter"]
    timing = spec["timing"]
    costs = spec["costs"]
    extra = {
        "sig_desc": "；".join(
            "%s（%s）" % (o.get("label", o.get("type")), o.get("type")) for o in sig_cfg["ops"])
        + "，组合方式 = %s" % sig_cfg.get("combine"),
        "pf_desc": "%s；阈值 = 过去 %d 个交易日（≈3年）滚动 %d%% 分位，基差定义 = %s，"
                   "分位窗口严格早于当日（无未来数据）" % (
                       pf.get("type"), int(pf.get("lookback_points", 756)),
                       int(float(pf.get("threshold", 0.8)) * 100), pf.get("basis_mapping")),
        "timing": "指标可用交易日 = 原始发布日之后第一个交易日（w_min=%s）；入场价 = %s；"
                  "出场价 = 到期日收盘（结算价盯市）。现货价格按收盘后才可用（next_session）。"
                  % (timing.get("indicator_lag_sessions_min"), timing.get("prices")),
        "contract": "按前一交易日收盘持仓量排序取第 %s 名真实挂牌合约；交割月前 %s 个自然日内移出可交易范围；"
                    "不使用任何后复权连续合约。" % (spec["contract"].get("k"),
                                        spec["contract"].get("no_trade_window_days_before_delivery")),
        "entry": "%s；持仓期间重复信号按 %s 处理" % (spec["entry"].get("order_type"),
                                            spec["entry"].get("reentry_while_holding")),
        "exit": "持有到期 %s 个交易日；止盈 %s；止损 %s" % (
            spec["exit"].get("max_hold_sessions"), spec["exit"].get("take_profit_pct"),
            spec["exit"].get("stop_loss_pct")),
        "position": "%s，%s 手，初始资金 %s 元" % (spec["position"].get("sizing"),
                                            spec["position"].get("lots"),
                                            spec["position"].get("capital")),
        "costs": "手续费 %s 元/手/边，滑点 %s 跳（1 跳 = %s 元/吨），合约乘数 %s 吨/手，"
                 "保证金率 %.0f%%" % (costs.get("fee_value"), costs.get("slippage_ticks"),
                                  costs.get("tick_size"), costs.get("multiplier"),
                                  float(costs.get("margin_rate", 0.1)) * 100),
        "roll": "持仓合约变化时：当日对旧合约平仓 + 对新合约开仓，各计一次手续费与滑点；"
                "trade_id 保持不变，rolls 计数",
        "limit_note": "本样本内未对涨跌停逐笔撮合；请按交易所规则复核。",
        "gap": ("%d 周指标中仅 %d 周的原始发布时刻可核验（2024-10 起可从文章发布时间核对）。"
                "2022–2024 年的 Mysteel 数据为 2024-07 回填发布，原始时刻无法核验，"
                "strict 模式下这些周被排除，因此信号样本只在 %s 之后才有可交易事件。"
                % (total, verified, dg.get("first_session")))
        if mode == "strict" else
        ("对照模式：对未核验周采用 as-of 日 14:00 的假设发布时间。该假设会改变结论方向，"
         "说明结果对数据时点非常敏感，不能作为业绩引用。"),
        "spot_note": "现货价格序列（华东甲醇现货，元/吨）来自历史整理文件，未标注采集商与发布时间，"
                     "按『收盘后才可用』处理；基差水平本身可能存在口径差异（地区、税基、品级）。",
        "diag_rows": "".join(
            "<tr><td style='text-align:left'>%s</td><td style='text-align:left'>%s</td></tr>"
            % (k, v) for k, v in (stats.get("diagnostics") or {}).items()),
    }

    # robustness html for the OOS page
    rob = []
    if oos:
        bs = oos.get("bootstrap", {})
        dom = bs.get("single_year_dominance", {}) or {}
        p_pos = ("{:.1%}".format(bs["p_positive"])) if bs.get("p_positive") is not None else "—"
        rob.append("<table><tbody>")
        rob.append(
            "<tr><td style='text-align:left;width:240px'>按笔块自助重抽样（{n} 笔，2000 次）</td>"
            "<td style='text-align:left'>均值 {mean:+,.0f} 元，P(均值&gt;0) = {p}，90% 区间 "
            "[{lo:+,.0f}, {hi:+,.0f}]</td></tr>".format(
                n=bs.get("n", 0), mean=bs.get("mean") or 0, p=p_pos,
                lo=bs.get("ci5") or 0, hi=bs.get("ci95") or 0))
        share = ("{:.0f}%".format(dom["share"] * 100)) if dom.get("share") is not None else "—"
        rob.append(
            "<tr><td style='text-align:left'>单一年度贡献占比</td>"
            "<td style='text-align:left'>{y} 年贡献了全部净盈亏的 {s}"
            "（&gt;100% 表示其他年份合计为负）</td></tr>".format(y=dom.get("top_year"), s=share))
        rem = oos.get("annual_removal", {})
        if rem:
            parts = "；".join("剔除 {k} 年 → 剩余 {v:+,.0f} 元".format(k=k, v=v["net_pnl_without_year"])
                             for k, v in sorted(rem.items()))
            rob.append("<tr><td style='text-align:left'>逐年剔除检验</td>"
                       "<td style='text-align:left'>{p}</td></tr>".format(p=parts))
        rob.append("</tbody></table>")
    extra["robust_html"] = "".join(rob) or "<p class='note'>未运行</p>"

    # notes for the workbook readme
    notes = {
        "readme_bullets": [
            "样本极小：完整交易仅 %s 笔，胜率与盈亏比只为描述性统计，不具备统计显著性。" % st.get("trades"),
            "历史回测不代表未来收益；本工作簿不构成任何投资建议或收益承诺。",
            "未使用后复权连续合约：每个交易日映射真实挂牌合约，换月成本已计入，未被平滑。",
            "数据模式 = %s；可核验发布时刻 %s / %s 周。%s" % (
                mode, verified, total,
                "2022–2024 回填数据已被排除，因此样本起点较晚。" if mode == "strict"
                else "此为对照口径，含假设发布时刻，不得作为业绩引用。"),
            "现货基差来源未核验采集商与发布时间，按收盘后可用处理。",
            "未模拟涨跌停无法成交、盘中强平与极端行情下的流动性枯竭。",
        ],
        "rerun_cmd": "python scripts/run_backtest.py analyze --config configs/<spec>.json --out out\n"
                     "python scripts/build_reports.py --config configs/<spec>.json --out out",
    }

    html_path = os.path.join(out, "research_platform.html")
    build_html(stats, daily, trades, align, sens, oos, cost, spec, html_path, extra=extra)
    xlsx_path = os.path.join(out, "backtest_workbook.xlsx")
    build_workbook(xlsx_path, spec=spec, stats=stats, daily=daily, trades=trades,
                   alignment=align, quotes=quotes, sens=sens, oos=oos, cost_sens=cost,
                   notes=notes)
    print("wrote", html_path)
    print("wrote", xlsx_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
