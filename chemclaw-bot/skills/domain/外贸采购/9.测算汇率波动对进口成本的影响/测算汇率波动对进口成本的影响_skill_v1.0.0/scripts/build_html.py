# -*- coding: utf-8 -*-
"""
build_html.py —— 生成单文件交互式《进口汇率敏感性分析计算器》

用法
----
    python build_html.py input.json -o output/计算器.html \
        --history data/fx_real_data.json

历史序列来源必须是真实公开数据（见 references/data-sources.md），
本脚本不做任何插值、平滑或伪造；仅做“按月采样”以控制文件体积，
采样时保留每月的首个与末个交易日，确保首尾与真实端点一致。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import fx_engine as E  # noqa: E402

TEMPLATE = os.path.join(ROOT, "templates", "calculator.template.html")
DEFAULT_HIST = os.path.join(ROOT, "data", "fx_real_data.json")


def compact_series(pairs, max_points=1300):
    """按月轻度抽样：每月最多保留 6 个观测（含首末），其余窗口原样保留。"""
    if len(pairs) <= max_points:
        return [[p[0], round(float(p[1]), 6)] for p in pairs]
    out, cur, buf = [], None, []
    for d, v in pairs:
        m = d[:7]
        if m != cur and buf:
            out.extend(pick(buf, 6))
            buf = []
            cur = m
        buf.append([d, round(float(v), 6)])
    if buf:
        out.extend(pick(buf, 6))
    if out and out[-1][0] != pairs[-1][0]:
        out.append([pairs[-1][0], round(float(pairs[-1][1]), 6)])
    return out


def pick(buf, n):
    if len(buf) <= n:
        return buf
    idx = [round(i * (len(buf) - 1) / (n - 1)) for i in range(n)]
    return [buf[i] for i in sorted(set(idx))]


def build_hist_windows(history, ccy, use_market, use_pboc, rate_date):
    """为 HTML 准备 1y / 3y / 5y / all 四个窗口的统计 + 序列。"""
    key = f"{ccy}CNY"
    daily = (history or {}).get("daily", {}).get(key)
    if not daily:
        return {}
    today = datetime.strptime(rate_date, "%Y-%m-%d").date() if rate_date else datetime.now().date()
    windows = {"1y": 1, "3y": 3, "5y": 5, "all": None}
    out = {}
    for name, yrs in windows.items():
        if yrs is None:
            sub = daily
        else:
            cut = (today.isoformat() if False else
                   (today.replace(year=today.year - yrs) if not (today.month == 2 and today.day == 29)
                    else today.replace(year=today.year - yrs, day=28)).isoformat())
            sub = [p for p in daily if p[0] >= cut]
        if not sub:
            continue
        st = E.series_stats(sub)
        vals = [p[1] for p in sub]
        st["pctl_market"] = E.percentile_rank(vals, use_market) if use_market else None
        st["pctl_pboc"] = E.percentile_rank(vals, use_pboc) if use_pboc else None
        st["series"] = compact_series(sub)
        out[name] = st
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--history", default=DEFAULT_HIST)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    inputs = json.load(open(args.input, encoding="utf-8"))
    history = None
    if os.path.exists(args.history):
        history = json.load(open(args.history, encoding="utf-8"))

    ccy = (inputs.get("foreign_currency") or "USD").upper()
    rates = inputs.get("rates") or {}
    market = E.num(rates.get("market"))
    pboc = E.num(rates.get("pboc"))
    bank = E.num(rates.get("bank"))
    customs = E.num(rates.get("customs"))
    basis = (inputs.get("rates", {}).get("basis") or inputs.get("basis") or "bank")
    rate_date = rates.get("market_date") or rates.get("pboc_date")
    if rate_date and " " in str(rate_date):
        rate_date = str(rate_date).split(" ")[0]

    costs = inputs.get("costs") or {}
    sales = inputs.get("sales") or {}
    pay = inputs.get("payment") or {}
    trs = pay.get("tranches") or [{"pct": 1.0}, {"pct": 0.0}]
    if len(trs) == 1:
        trs = [trs[0], {"pct": 0.0}]

    hist = build_hist_windows(history, ccy, market, pboc, rate_date)

    sources = []
    src = rates.get("source") or {}
    sources.append({"item": f"{ccy}/CNY 市场汇率", "value": E.r6(market) or "–",
                    "date": rates.get("market_date"), "kind": "real",
                    "source": src.get("market", "欧洲央行参考汇率（Frankfurter API）")})
    sources.append({"item": f"{ccy}/CNY 人民币汇率中间价", "value": E.r6(pboc) or "–",
                    "date": rates.get("pboc_date"), "kind": "real",
                    "source": src.get("pboc", "中国人民银行授权中国外汇交易中心公布")})
    sources.append({"item": f"{ccy}/CNY 银行实际购汇价", "value": E.r6(bank) or "–",
                    "date": rates.get("bank_date"), "kind": "demo",
                    "source": src.get("bank", "演示值：中间价 + 点差模拟，实际须由银行实盘提供")})
    sources.append({"item": f"{ccy}/CNY 海关计征汇率", "value": E.r6(customs) or "–",
                    "date": rates.get("customs_date"), "kind": "demo",
                    "source": src.get("customs", "演示值：依法规取上月第三个星期三中间价，实际须查海关公布值")})
    if history:
        m = history.get("meta", {})
        sources.append({"item": "历史日度序列", "value": f"{len(history.get('daily',{}).get(ccy+'CNY',[]))} 个观测",
                        "date": f"{history.get('daily',{}).get(ccy+'CNY',[['–']])[0][0]} 起", "kind": "real",
                        "source": m.get("primary_source", "ECB Euro reference rates")})
        sources.append({"item": "官方中间价交叉核对", "value": str(m.get("official_parity", {}).get(f"{ccy}/CNY", m.get("official_parity_time", "–"))),
                        "date": m.get("official_parity_time"), "kind": "real",
                        "source": m.get("official_parity_source", "CFETS")})
    sources.append({"item": inputs.get("product", "产品"), "value": inputs.get("hs_code") or "–",
                    "date": "", "kind": "real",
                    "source": "HS 编码与税率口径以《中华人民共和国进出口税则》及海关公告为准"})
    if sales.get("price_cny") is not None:
        sources.append({"item": "国内销售价（参与毛利测算）", "value": f"{sales.get('price_cny')} 元/吨",
                        "date": "", "kind": "sim",
                        "source": sales.get("price_note") or "模拟值，须替换为企业实际销售合同价"})
    if sales.get("other_cost_cny_unit") is not None:
        sources.append({"item": "非汇率相关单位成本", "value": f"{sales.get('other_cost_cny_unit')} 元/吨*",
                        "date": "", "kind": "sim",
                        "source": sales.get("other_cost_note") or "模拟值"})
    if pay.get("tranches"):
        sources.append({"item": "分批付款结构", "value": " / ".join(f"{t.get('name','批次')} {t.get('pct',0)*100:.0f}%" for t in trs),
                        "date": pay.get("payment_date", ""), "kind": "sim",
                        "source": "付款条件为演示假设，真实合同以合同条款为准"})

    data = {
        "ccy": ccy,
        "meta": {"rate_date": rates.get("pboc_date") or rate_date},
        "inputs": {
            "amount": inputs.get("amount_fc"),
            "ccy": ccy,
            "dir": inputs.get("direction", "IMPORT_PAYMENT"),
            "product": inputs.get("product", ""),
            "qty": inputs.get("quantity"),
            "market": market, "pboc": pboc, "bank": bank, "customs": customs,
            "basis": basis, "budget": E.num(inputs.get("budget_rate")),
            "duty": E.num(costs.get("duty_rate")) or 0.0,
            "vat": E.num(costs.get("vat_rate")) if E.num(costs.get("vat_rate")) is not None else 13.0,
            "vatMode": costs.get("vat_mode", "deductible"),
            "freight": E.num(costs.get("freight_fc")) or 0.0,
            "port": E.num(costs.get("cny_port")) or 0.0,
            "agent": E.num(costs.get("cny_customs_agent")) or 0.0,
            "inland": E.num(costs.get("cny_inland")) or 0.0,
            "storage": (E.num(costs.get("cny_storage")) or 0.0) + (E.num(costs.get("cny_other")) or 0.0),
            "bankFee": E.num(costs.get("cny_bank_fee")) or 0.0,
            "price": E.num(sales.get("price_cny")),
            "otherUnit": E.num(sales.get("other_cost_cny_unit")),
            "revBasis": sales.get("revenue_basis", "tax_included"),
            "targets": sales.get("target_margins_pct") or [0],
            "p1": (E.num(trs[0].get("pct")) or 0) * 100,
            "t1": E.num(trs[0].get("days")) or 0,
            "r1": E.num(trs[0].get("rate_override")),
            "t2": E.num(trs[1].get("days")) or 0,
            "r2": E.num(trs[1].get("rate_override")),
        },
        "hist": hist,
        "sources": sources,
    }

    tpl = open(TEMPLATE, encoding="utf-8").read()
    title = args.title or f"{inputs.get('product','进口采购')} · 汇率敏感性分析计算器"
    html = (tpl
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__TITLE__", title)
            .replace("__SUBTITLE__",
                     f"{inputs.get('product','')} ｜ {ccy} {inputs.get('amount_fc'):,.0f} ｜ "
                     f"进口付汇 ｜ 汇率口径：1 {ccy} = x CNY ｜ 数据截至 {rates.get('pboc_date') or rate_date}")
            .replace("__CCY1__", ccy)
            .replace("__VER__", E.ENGINE_VERSION)
            .replace("__GENAT__", datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__FOOTER__",
                     f"历史汇率：ECB 欧元参考汇率（经 Frankfurter 公开接口），交叉核对 ER-API；"
                     f"当前汇率：中国人民银行授权 CFETS 人民币汇率中间价。"))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(html)
    print(f"wrote {args.out}  ({len(html)/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
