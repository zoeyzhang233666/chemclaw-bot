# -*- coding: utf-8 -*-
"""run_case.py —— 读案例 JSON + 官方汇率序列 → 输出完整测算包 scenario.json

用法:
    python scripts/run_case.py examples/01-export-soda-ash-usd/case.json \
        --fx build/fx_series.json --out examples/01-export-soda-ash-usd/build/scenario.json

case.json 字段见 references/data-contract.md，这里只做：
校验 → 取汇率 → 算分位/统计 → 算敏感性/毛利/平衡汇率 → 算分批 → 组装 narrn
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calculations as C  # noqa: E402

PCT = None  # 占位，避免误用


def r6(x):
    return None if x is None else round(float(x), 6)


def r2(x):
    return None if x is None else round(float(x), 2)


def parse_date(s):
    if isinstance(s, (date, datetime)):
        return s.date() if isinstance(s, datetime) else s
    return date.fromisoformat(s)


def latest_le(dates, target):
    ds = [d for d in dates if d <= target]
    return ds[-1] if ds else None


def to_business_days(start: date, end: date) -> int:
    """自然日差换成"工作日"：先扣周末，再扣 case 里声明的节假日（可选）。"""
    n = (end - start).days
    return max(1, int(round(n * 5 / 7)))


def build(case: dict, fx: dict, captured_at: str) -> dict:
    errs, warns = [], []

    # ---------- 1. 必填校验 ----------
    for k in ("amount_fx", "currency", "direction", "settle_date"):
        if case.get(k) in (None, ""):
            errs.append(f"缺少必填字段 {k}")
    if errs:
        return {"ok": False, "errors": errs, "warnings": warns}

    direction = case["direction"]
    if direction not in (C.DIRECTION_EXPORT, C.DIRECTION_IMPORT):
        errs.append("direction 必须是 export 或 import")
    cur = case["currency"]
    curinfo = fx["currencies"].get(cur)
    if not curinfo:
        errs.append(f"币种 {cur} 不在本轮已取数的币种表中：{list(fx['currencies'])}")
        return {"ok": False, "errors": errs, "warnings": warns}
    if errs:
        return {"ok": False, "errors": errs, "warnings": warns}

    amount = float(case["amount_fx"])
    settle = parse_date(case["settle_date"])
    asof = parse_date(case.get("asof") or fx["meta"]["last_date"])
    trade = parse_date(case.get("trade_date") or asof)

    # ---------- 2. 取汇率 ----------
    vals = dict(curinfo["values"])
    date_today = latest_le(list(vals), asof.isoformat())
    if date_today is None:
        return {"ok": False, "errors": [f"{asof} 之前没有 {cur} 的汇率数据"], "warnings": warns}

    series = sorted(vals.items())
    mid = float(vals[date_today])
    band = float(case.get("bank_band_pct", 0.0025))
    actual = case.get("actual_bank_rate")
    toll = float(case.get("toll_rate", 0.0) or 0.0)
    pr = C.pick_rate(mid, direction, band, actual)

    rate_mode = case.get("rate_mode", "auto")
    allowed = {"auto", "mid", "band", "actual"}
    if rate_mode not in allowed:
        errs.append(f"rate_mode 必须是 {allowed} 之一")
    if rate_mode == "actual" and actual is None:
        errs.append("rate_mode=actual 但未提供 actual_bank_rate")
    if errs:
        return {"ok": False, "errors": errs, "warnings": warns}

    if rate_mode == "mid":
        base_rate, basis = mid, "mid"
    elif rate_mode == "band":
        base_rate = pr["sell_fx"] if direction == C.DIRECTION_EXPORT else pr["buy_fx"]
        basis = "mid_x_band_estimate"
    elif rate_mode == "actual":
        base_rate, basis = float(actual), "actual_bank_settle"
    else:
        base_rate, basis = pr["used"], pr["basis"]

    if basis == "mid_x_band_estimate":
        warns.append(
            "基准汇率 = 中间价 × (1 %s %.2f%%)，是按对称点差推算的**示例估算值**，"
            "并非银行实际成交价；拿到银行实际结汇/购汇价后应改用该价。" % ("−" if direction == C.DIRECTION_EXPORT else "+", band * 100)
        )

    # ---------- 3. 历史统计 ----------
    windows = case.get("windows", [1, 3])
    stats = C.window_stats_multi(series, date_today, mid, windows)
    # 分位同时提供 mid 与 used 两个口径
    for key, w in stats.items():
        y = int(key.replace("y", ""))
        win = C.window_slice(series, date_today, y)
        w["pctile_mid"] = r6(C.percentile_rank(win, mid))
        w["pctile_used"] = r6(C.percentile_rank(win, base_rate))
        q = C.quantiles(win)
        w["quantiles"] = {str(k): r6(v) for k, v in q.items()}
        vol = C.realized_vol(win)
        w["vol_daily"] = r6(vol["daily_std_pct"])
        w["vol_annual"] = r6(vol["annualized_pct"])
        w["pctile"] = w["pctile_mid"]  # 兼容字段

    settle_bdays = to_business_days(trade, settle)
    calendar_gap = (settle - trade).days
    horizon = None
    if "1y" in stats and stats["1y"].get("vol_annual"):
        horizon = {
            "calendar_days": calendar_gap,
            "business_days": settle_bdays,
            "one_sigma_pct": r6(C.implied_move(stats["1y"]["vol_annual"], settle_bdays)),
            "note": "按过去 1 年年化波动率折算的 N 个交易日典型波动幅度，仅说明情景量级，不是预测。",
        }

    # ---------- 4. 业务测算 ----------
    cny_cost = case.get("cny_cost")
    cny_cost = None if cny_cost in (None, "") else float(cny_cost)
    target_pct = case.get("target_margin_pct")
    target_pct = None if target_pct in (None, "") else float(target_pct)
    target_cny = case.get("target_margin_cny")
    target_cny = None if target_cny in (None, "") else float(target_cny)
    resale = case.get("resale_cny")
    resale = None if resale in (None, "") else float(resale)

    shifts = case.get("shifts", [-0.05, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.05])
    oc = C.OrderCase(amount_fx=amount, currency=cur, direction=direction, base_rate=base_rate,
                     cny_cost=cny_cost, target_margin_pct=target_pct, target_margin_cny=target_cny,
                     toll_rate=toll, resale_cny=resale)
    summ = oc.summary(shifts)

    sens = []
    base_res = C.business_pnl(amount, base_rate, direction, cny_cost, toll)
    for row in summ["sensitivity"]:
        rec = dict(row)
        if direction == C.DIRECTION_EXPORT:
            rec["revenue_cny"] = cur_rec = C.business_pnl(amount, row["rate"], direction, cny_cost, toll)["revenue_cny"]
            rec["margin_cny"] = cur_rec - (cny_cost or 0.0)
            rec["margin_pct"] = (rec["margin_cny"] / rec["revenue_cny"]) if rec["revenue_cny"] else None
        else:
            p = C.business_pnl(amount, row["rate"], direction, cny_cost, toll)
            rec["payable_cny"] = p["payable_cny"]
            rec["total_cost_cny"] = p["total_cost_cny"]
            if resale is not None:
                m = C.import_margin(amount, row["rate"], cny_cost or 0.0, resale, toll)
                rec["margin_cny"] = m["margin_cny"]
                rec["margin_pct"] = m["margin_pct"]
        for k in list(rec):
            if isinstance(rec[k], float):
                rec[k] = r6(rec[k])
        sens.append(rec)

    margin_curve = []
    if direction == C.DIRECTION_EXPORT and cny_cost is not None:
        # 连续曲线：以基准汇率为中心 ±range
        rng = float(case.get("curve_range_pct", 0.10))
        n = 81
        for i in range(n):
            s = -rng + 2 * rng * i / (n - 1)
            rr = base_rate * (1 + s)
            rev = amount * rr * (1 - toll)
            margin_curve.append({"shift": r6(s), "rate": r6(rr), "revenue": r2(rev),
                                 "margin": r2(rev - cny_cost)})
    elif resale is not None:
        rng = float(case.get("curve_range_pct", 0.10))
        n = 81
        for i in range(n):
            s = -rng + 2 * rng * i / (n - 1)
            rr = base_rate * (1 + s)
            m = C.import_margin(amount, rr, cny_cost or 0.0, resale, toll)
            margin_curve.append({"shift": r6(s), "rate": r6(rr), "revenue": r2(resale),
                                 "cost": r2(m["total_cost_cny"]), "margin": r2(m["margin_cny"])})

    breakevens = {}
    if direction == C.DIRECTION_EXPORT and cny_cost is not None:
        be = C.breakeven_rate_export(cny_cost, amount, toll)
        breakevens["zero"] = _be_pack(C.breakeven_distance(base_rate, be, direction))
        if target_pct is not None:
            be2 = C.rate_needed_for_margin(amount, cny_cost, target_pct, toll)
            breakevens["target_pct"] = _be_pack(C.breakeven_distance(base_rate, be2, direction))
            breakevens["target_pct"]["target"] = target_pct
        if target_cny is not None:
            be3 = C.rate_needed_for_margin(amount, cny_cost, target_cny, toll, as_amount=True)
            breakevens["target_cny"] = _be_pack(C.breakeven_distance(base_rate, be3, direction))
            breakevens["target_cny"]["target"] = target_cny
    elif direction == C.DIRECTION_IMPORT and resale is not None:
        be = C.breakeven_rate_import(amount, cny_cost or 0.0, resale, toll)
        breakevens["zero"] = _be_pack(C.breakeven_distance(base_rate, be, direction))

    # ---------- 5. 分批结算 ----------
    batches = []
    for i, b in enumerate(case.get("batches", []) or []):
        bd = dict(b)
        bd.setdefault("rate", base_rate)
        bd["amount_fx"] = float(bd["amount_fx"])
        bd["days"] = int(bd.get("days") or 0)
        bd["rate"] = float(bd["rate"])
        bd["share_pct"] = (bd["amount_fx"] / amount) if amount else None
        if "settle_date" in bd:
            bd["days"] = (parse_date(bd["settle_date"]) - trade).days
        batches.append(bd)

    batch_out = None
    if batches:
        tot = sum(b["amount_fx"] for b in batches)
        if abs(tot - amount) > 1e-6:
            warns.append(f"分批合计 {tot:,.2f} 与订单外币金额 {amount:,.2f} 不一致（差额 {tot-amount:,.2f}），请确认是否为部分结算。")
        for b in batches:
            b["share_pct"] = r6(b["amount_fx"] / tot if tot else None)
            b["cny"] = r2(b["amount_fx"] * b["rate"])
        weighted = sum(b["cny"] for b in batches) / tot if tot else None
        rows = []
        for s in shifts:
            sc = C.split_batches(C.split_shift_rates(batches, s))
            one_cny = amount * base_rate * (1 + s) * (1 - toll if direction == C.DIRECTION_EXPORT else 1 + toll)
            rows.append({
                "shift": s,
                "staggered_cny": r2(sc["total_cny"] * (1 - toll if direction == C.DIRECTION_EXPORT else 1 + toll)),
                "one_shot_cny": r2(one_cny),
                "delta_vs_base_cny": r2(sc["total_cny"] * (1 - toll if direction == C.DIRECTION_EXPORT else 1 + toll)
                                        - sum(b["cny"] for b in batches) * (1 - toll if direction == C.DIRECTION_EXPORT else 1 + toll)),
                "staggering_effect_cny": r2(sc["total_cny"] * (1 - toll if direction == C.DIRECTION_EXPORT else 1 + toll) - one_cny),
                "batches": [r2(r["cny"] * (1 - toll if direction == C.DIRECTION_EXPORT else 1 + toll)) for r in sc["rows"]],
            })
        batch_out = {
            "batches": batches,
            "total_amount_fx": tot,
            "weighted_rate": r6(weighted),
            "base_total_cny": r2(sum(b["cny"] for b in batches) * (1 - toll if direction == C.DIRECTION_EXPORT else 1 + toll)),
            "rows": rows,
            "duration_days": r6(sum(b["amount_fx"] * b["days"] for b in batches) / tot) if tot else None,
            "note": "分批情景中每批按其自身假设汇率折算；敏感性档位对全部批次同向等比例平移，"
                    "因此'分批 vs 一次性'的差额只反映批次基准汇率差异（结构效应），不是汇率预测。",
        }

    # ---------- 6. 其它口径 ----------
    contract_rate = case.get("contract_rate")
    contract = None
    if contract_rate not in (None, ""):
        contract_rate = float(contract_rate)
        contract = {
            "rate": contract_rate,
            "cny": r2(amount * contract_rate * (1 + (C.toll_sign(direction) * toll))),
            "vs_base_pct": r6(contract_rate / base_rate - 1),
            "vs_base_cny": r2(amount * (contract_rate - base_rate) * (1 + (C.toll_sign(direction) * toll))),
            "note": "若合同已约定汇率，实际人民币收付以此为准，可与市场汇率对照计量「机会差额」。",
        }

    return {
        "ok": True,
        "errors": errs,
        "warnings": warns,
        "meta": {
            "case_id": case.get("case_id"),
            "title": case.get("title"),
            "product": case.get("product"),
            "spec": case.get("spec"),
            "incoterm": case.get("incoterm"),
            "currency": cur,
            "currency_name": curinfo["name_cn"],
            "pair": curinfo["pair"],
            "unit_label": curinfo["unit_label"],
            "direction": direction,
            "direction_label": C.DIRECTION_LABELS[direction],
            "asof": date_today,
            "trade_date": trade.isoformat(),
            "settle_date": settle.isoformat(),
            "horizon_days": calendar_gap,
            "amount_fx": amount,
            "amount_display": case.get("amount_display"),
            "cny_cost": cny_cost,
            "cny_cost_source": case.get("cny_cost_source"),
            "target_margin_pct": target_pct,
            "target_margin_cny": target_cny,
            "toll_rate": toll,
            "resale_cny": resale,
            "rate_mode": rate_mode,
            "generated_at": captured_at,
            "simulated_fields": case.get("simulated_fields", []),
            "notes": case.get("notes", []),
            "disclaimer": case.get("disclaimer") or DEFAULT_DISCLAIMER,
        },
        "rate": {
            "mid": mid,
            "mid_date": date_today,
            "band": band,
            "sell_fx": r6(pr["sell_fx"]),
            "buy_fx": r6(pr["buy_fx"]),
            "base_rate": base_rate,
            "basis": basis,
            "actual_bank_rate": actual,
            "source_id": "safe_parity",
            "quote_convention": "1 单位外币 = X 人民币（直接标价法）",
            "usable_note": (
                "出口收汇：银行从你手中买入外币，看「现汇买入价」，人民币收入 = 外币金额 × 该价。"
                if direction == C.DIRECTION_EXPORT else
                "进口付汇：你用人民币向银行买入外币，看「现汇卖出价」，人民币支出 = 外币金额 × 该价。"
            ),
            "boc_reference": fx_boc(fx, cur),
        },
        "stats": stats,
        "horizon": horizon,
        "series": {
            "dates": [d for d, _ in series],
            "values": [r6(v) for _, v in series],
            "first": series[0][0],
            "last": series[-1][0],
        },
        "base": _round_dict(summ["base"]),
        "one_pct_cny": r2(summ["one_pct_cny"]),
        "sensitivity": sens,
        "margin_curve": margin_curve,
        "breakevens": breakevens,
        "batch": batch_out,
        "contract": contract,
        "fx_meta": fx["meta"],
        "sources": fx["sources"],
        "currency_table": fx["currency_list"],
    }


def fx_boc(fx, cur):
    for s in fx["sources"]:
        if s.get("id") == "boc_spot":
            q = (s.get("quotes") or {}).get(cur)
            if q:
                return {"time": s.get("time"), "url": s.get("url"), "quotes": q}
    return None


def _be_pack(d):
    out = {k: (r6(v) if isinstance(v, float) else v) for k, v in d.items()}
    return out


def _round_dict(d):
    return {k: (r6(v) if isinstance(v, float) else v) for k, v in d.items()}


DEFAULT_DISCLAIMER = (
    "本页只做汇率情景测算，不预测汇率走势，也不构成任何外汇避险产品或交易操作的推荐。"
    "所有「若汇率变为 R」的假设均为压力测试，不代表对未来汇率的判断。"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--fx", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fx_path = args.fx or os.path.join(root, "build", "fx_series.json")
    case = json.load(open(args.case, encoding="utf-8"))
    fx = json.load(open(fx_path, encoding="utf-8"))
    out = build(case, fx, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if not out["ok"]:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        sys.exit(2)
    out_path = args.out or os.path.join(os.path.dirname(os.path.abspath(args.case)), "build", "scenario.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    m = out["meta"]
    print(f"OK {out_path}")
    print(f"  {m['direction_label']} {m['amount_fx']:,.2f} {m['currency']} @ {out['rate']['base_rate']} ({out['rate']['basis']})")
    for k, w in out["stats"].items():
        print(f"  {k}: n={w['n']} min={w['min']} max={w['max']} pctile={w['pctile']:.2%} vol={w['vol_annual']:.2%}")
    for w in out["warnings"]:
        print("  WARN:", w)


if __name__ == "__main__":
    main()
