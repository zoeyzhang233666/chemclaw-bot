#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""assemble.py — 从 research.json 计算全部派生指标，产出 build/data.json。

原则：
  * research.json 里只写「查到的事实」，派生数字一律由本脚本算，禁止手写。
  * 每一步计算都把「公式 + 输入 + 结果」写进 data.json 的 steps，保证可复核。
  * 拿不到的数据一律 None + 记进 gaps，不插值、不编造。

用法：
  python scripts/assemble.py research.json --out out --build build
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as C  # noqa: E402


# ---------------------------------------------------------------- 判定规则
def classify(cmp_res, band, hist_points):
    """按「区间 + 近3月价格带 + 历史序列位置」判定，不使用固定百分比阈值。

    返回 (verdict_code, verdict_label, explain_lines)
      match       接近市场参考区间
      low         明显偏低
      high        明显偏高
      caliber     口径不一致/信息缺失，暂时无法直接比较
      unknown     无可靠市场数据，无法验证
    判定顺序见 references/verdict-rules.md
    """
    lines = []
    if cmp_res.get("pos") == "undecidable":
        return "unknown", "无可靠市场数据，无法验证", ["同规格同口径市场报价缺失，不能给出近似市场价。"]

    lo, hi = cmp_res["low"], cmp_res["high"]
    width = max(hi - lo, 1e-9)
    half = width / 2.0

    if cmp_res["pos"] == "inside":
        lines.append(f"客户价落在同日同口径市场区间 [{lo:g}, {hi:g}] 内，与市场报价一致。")
        return "match", "接近市场参考区间", lines

    dist = cmp_res["delta_to_high"] if cmp_res["pos"] == "above" else abs(cmp_res["delta_to_low"])
    side = "高于区间上沿" if cmp_res["pos"] == "above" else "低于区间下沿"
    lines.append(f"客户价{side} {dist:g} 元/吨（区间半宽 {half:g} 元/吨，区间宽 {width:g}）。")

    # 近 3 个月同口径价格带的上下限
    band_hi = band.get("max") if band else None
    band_lo = band.get("min") if band else None
    hist_max = max(hist_points) if hist_points else None
    hist_min = min(hist_points) if hist_points else None

    if cmp_res["pos"] == "above":
        ref_hi = band_hi if band_hi is not None else hi
        in_band = band_hi is not None and cmp_res["reference"] <= band_hi and cmp_res["low"] <= band_hi
        if dist > half:
            if hist_max is not None and cmp_res["reference"] - hist_max > 0:
                pass
            if hist_max is not None and cmp_res["reference"] > hist_max:
                lines.append(f"且客户价高于近 3 个月同口径序列最高点 {hist_max:g} 元/吨。")
            elif in_band:
                lines.append(f"且客户价高于近 3 个月同口径价格带上沿 {band_hi:g} 元/吨。")
            return "high", "明显偏高", lines
        else:
            return "high", "略高于市场参考区间", lines

    # below
    if dist > half:
        if hist_min is not None and cmp_res["reference"] < hist_min:
            lines.append(f"且客户价低于近 3 个月同口径序列最低点 {hist_min:g} 元/吨。")
        elif band_lo is not None:
            lines.append(f"且客户价低于近 3 个月同口径价格带下沿 {band_lo:g} 元/吨。")
        return "low", "明显偏低", lines
    return "low", "略低于市场参考区间", lines


def series_key(meta):
    """历史序列的匹配键：优先用 meta.series_key（如『重质纯碱』），否则退回 meta.spec。

    现货报价条的 spec 常带产区/地区后缀（如『重质纯碱（华北）』），不能直接当序列键。
    """
    return meta.get("series_key") or meta.get("spot_spec_key") or meta.get("spec")


def compute_band(history, region, spec, tax, delivery, days=92, ref_date=None):
    """取近 N 天同口径历史点，算 min/max/median/mean。"""
    pts = []
    for h in history:
        if region and h.get("region") != region:
            continue
        if spec and h.get("spec") != spec:
            continue
        if tax and C.norm_tax(h.get("tax")) != C.norm_tax(tax):
            continue
        if delivery and C.norm_delivery(h.get("delivery")) != C.norm_delivery(delivery):
            continue
        d = C.parse_date(h.get("date"))
        if ref_date and d:
            if (C.parse_date(ref_date) - d).days > days:
                continue
        pts.append(float(h["point"]))
    if not pts:
        return None
    pts.sort()
    n = len(pts)
    med = pts[n // 2] if n % 2 else (pts[n // 2 - 1] + pts[n // 2]) / 2.0
    return {
        "n": n, "days": days,
        "min": pts[0], "max": pts[-1],
        "median": round(med, 2),
        "mean": round(sum(pts) / n, 2),
    }


def window_change(history, region, spec, ref_date, days):
    """找 <= ref_date - days 的最近一个点，算到最新点的变化。"""
    ref = C.parse_date(ref_date)
    if not ref:
        return None
    cand = []
    for h in history:
        if region and h.get("region") != region:
            continue
        if spec and h.get("spec") != spec:
            continue
        d = C.parse_date(h.get("date"))
        if not d:
            continue
        if (ref - d).days >= days:
            cand.append((d, float(h["point"]), h))
    if not cand:
        return None
    cand.sort(key=lambda x: x[0])
    d0, v0, h0 = cand[-1]
    latest = [h for h in history
              if h.get("region") == (region or h.get("region"))
              and h.get("spec") == (spec or h.get("spec"))
              and C.parse_date(h.get("date"))
              and C.parse_date(h.get("date")) <= ref]
    if not latest:
        return None
    latest.sort(key=lambda h: C.parse_date(h["date"]))
    v1 = float(latest[-1]["point"])
    d1 = C.parse_date(latest[-1]["date"])
    return {
        "days": days,
        "from_date": d0.isoformat(), "from_value": v0,
        "to_date": d1.isoformat(), "to_value": v1,
        "abs_change": round(v1 - v0, 2),
        "change": C.pct(v1 - v0, v0),
        "source": h0.get("source"),
        "url": h0.get("url"),
    }


def nearest_point(history, region, spec, ref_date, target):
    """在历史序列里找离 target 最近的点（用于判断客户价对应哪个时点）。"""
    best = None
    for h in history:
        if region and h.get("region") != region:
            continue
        if spec and h.get("spec") != spec:
            continue
        d = C.parse_date(h.get("date"))
        if not d:
            continue
        if ref_date and d > C.parse_date(ref_date):
            continue
        gap = abs(float(h["point"]) - target)
        if best is None or gap < best[0]:
            best = (gap, h)
    if not best:
        return None
    gap, h = best
    return {"gap": round(gap, 2), "date": h["date"], "point": float(h["point"]),
            "source": h.get("source"), "url": h.get("url")}


# ---------------------------------------------------------------- 主流程
def assemble(research, build_dir=None):
    meta = research.get("meta", {})
    cust = research.get("customer", {})
    spot = research.get("spot", []) or []
    history = research.get("history", []) or []
    history2 = research.get("history_secondary", []) or []
    regions = research.get("regions", []) or []
    calibers = research.get("calibers", []) or []
    factors = research.get("factors", []) or []
    questions = research.get("questions", []) or []
    facts = research.get("facts", []) or []
    gaps = research.get("gaps", []) or []
    events = research.get("events", []) or []
    drivers = research.get("drivers", []) or []
    futs = research.get("futures", {}) or {}
    modes = research.get("comparison_modes", []) or []
    mnotes = research.get("method_notes", []) or []

    ref_date = meta.get("base_date") or C.today().isoformat()
    region = meta.get("region")
    series_k = series_key(meta)
    # ---- 1. 挑选「同规格·同地区·含税·送到·日期最近」的现货作为市场基准
    primary = None
    for s in spot:
        if s.get("exclude_reason"):
            continue
        if s.get("region") != region:
            continue
        if C.norm_tax(s.get("tax")) != "含税" or C.norm_delivery(s.get("delivery")) != "送到":
            continue
        if primary is None:
            primary = s
        else:
            if (C.parse_date(s.get("date")) or C.parse_date("1900-01-01")) > (C.parse_date(primary.get("date")) or C.parse_date("1900-01-01")):
                primary = s
    if primary is None:
        # 退化：取同地区日期最近的任意一条
        cand = [s for s in spot if s.get("region") == region and not s.get("exclude_reason")]
        if cand:
            cand.sort(key=lambda x: C.parse_date(x.get("date")) or C.parse_date("1900-01-01"), reverse=True)
            primary = cand[0]
    if primary:
        if not series_k and primary.get("spec"):
            series_k = primary.get("spec")

    steps = []
    data_gaps = list(gaps)

    # ---- 2. 市场区间
    if primary:
        m_low, m_high = primary.get("low"), primary.get("high")
        if m_low is None and m_high is None and primary.get("point") is not None:
            m_low = m_high = primary["point"]
        steps.append({
            "id": "S1", "name": "确定市场参考区间",
            "formula": "取同日同规格同地区含税送到的最新区间报价",
            "inputs": {"来源": primary.get("source"), "日期": primary.get("date"),
                       "口径": f"{primary.get('tax_label', primary.get('tax'))}·{primary.get('delivery')}"},
            "result": {"low": m_low, "high": m_high},
        })
    else:
        m_low = m_high = None
        data_gaps.append({"item": "同规格同地区市场报价", "impact": "无法给出市场参考区间", "fix": "补充至少一条六项齐全的现货报价"})

    # ---- 3. 客户价与区间比较
    cust_price = cust.get("stated_price")
    cmp_res = C.compare_to_range(cust_price, m_low, m_high)
    if cmp_res.get("pos") != "undecidable":
        steps.append({
            "id": "S2", "name": "客户价相对市场区间的偏离",
            "formula": "偏离金额 = 客户价 − 区间中值；偏离比例 = 偏离金额 ÷ 区间中值；另算相对上下沿的金额与比例",
            "inputs": {"客户价": cust_price, "区间": [m_low, m_high], "区间中值": cmp_res["reference"]},
            "result": {k: cmp_res.get(k) for k in
                       ("delta_to_dot", "pct_to_dot", "delta_to_low", "pct_to_low", "delta_to_high", "pct_to_high", "pos")},
        })

    # ---- 4. 近 3 个月价格带
    band3m = compute_band(history, region, series_k, "含税", "送到", 92, ref_date)
    points = [float(h["point"]) for h in history
              if h.get("region") == region and (not series_k or h.get("spec") == series_k)]
    if band3m:
        steps.append({
            "id": "S3", "name": "近3个月同口径价格带",
            "formula": "近 92 天同地区同规格同口径历史点的 min / max / median / mean（不使用不同来源混算）",
            "inputs": {"样本数": band3m["n"]},
            "result": {k: band3m[k] for k in ("min", "max", "median", "mean")},
        })

    # ---- 5. 判定
    verdict_code, verdict_label, why = classify(cmp_res, band3m, points)
    # 口径缺失风险：客户未说明含税/交付时不直接抹掉
    caliber_missing = []
    if C.norm_tax(cust.get("stated_tax")) == "未注明":
        caliber_missing.append("客户未说明含税/不含税")
    if C.norm_delivery(cust.get("stated_delivery")) == "未注明":
        caliber_missing.append("客户未说明出厂/送到")
    if C.norm_payment(cust.get("stated_payment")) == "未注明":
        caliber_missing.append("客户未说明付款方式/账期")

    steps.append({
        "id": "S4", "name": "结论判定",
        "formula": "区间内=接近市场；区间外但距离≤区间半宽=略高/略低；距离>区间半宽 且 超出近3月价格带=明显偏高/偏低",
        "inputs": {"客户价": cust_price, "区间半宽": (max((m_high or 0) - (m_low or 0), 0) / 2.0) if m_low is not None else None,
                   "近3月最高": band3m["max"] if band3m else None,
                   "近3月最低": band3m["min"] if band3m else None},
        "result": {"verdict": verdict_code, "label": verdict_label},
    })

    # ---- 6. 窗口涨跌
    windows = {}
    for d in (7, 30, 90):
        windows[f"{d}d"] = window_change(history, region, series_k, ref_date, d)
    steps.append({
        "id": "S5", "name": "7/30/90 天价格变化",
        "formula": "变化 = 最新价 − 取最新日向前推 N 天最近的同口径点；比例 = 变化 ÷ 起点价",
        "inputs": {"基准日": ref_date},
        "result": {k: (v["change"] if v else None) for k, v in windows.items()},
    })

    # ---- 7. 客户价在历史中的位置 / 对应时点
    hist_pos = None
    if cust_price is not None and points:
        lo_h, hi_h = min(points), max(points)
        hist_pos = {
            "min": lo_h, "max": hi_h,
            "inside_history": lo_h <= cust_price <= hi_h,
            "above_max_by": round(cust_price - hi_h, 2) if cust_price > hi_h else None,
            "pct_above_max": C.pct(cust_price - hi_h, hi_h) if cust_price > hi_h else None,
        }
    nearest = nearest_point(history, region, series_k, ref_date, cust_price) if cust_price is not None else None
    if hist_pos:
        steps.append({
            "id": "S6", "name": "客户价在历史序列中的位置",
            "formula": "判断客户价是否落近 3 月同口径序列 [min, max]；并找序列中与客户价最接近的点",
            "inputs": {"客户价": cust_price, "序列最低": hist_pos["min"], "序列最高": hist_pos["max"]},
            "result": {"在序列内": hist_pos["inside_history"],
                       "高于序列最高": hist_pos["above_max_by"],
                       "最近点": nearest},
        })

    # ---- 8. 区域比较
    reg_cmp = []
    for r in regions:
        if r.get("is_primary"):
            continue
        item = dict(r)
        item["delta_to_primary_point"] = round((r.get("point") or 0) - (cmp_res.get("reference") or 0), 2) if cmp_res.get("reference") is not None else None
        item["pct_to_primary_point"] = C.pct(item["delta_to_primary_point"], cmp_res.get("reference")) if cmp_res.get("reference") else None
        reg_cmp.append(item)

    # ---- 9. 口径对照（自动标出差异）
    cal_rows = []
    for c in calibers:
        row = dict(c)
        row["diff_flag"] = "一致" if "一致" in str(c.get("same", "")) and "不一致" not in str(c.get("same", "")) else (
            "信息缺失" if "缺失" in str(c.get("same", "")) or "未说明" in str(c.get("customer", "")) else "不一致")
        cal_rows.append(row)

    # ---- 10. 我方报价 vs 客户价（若提供）
    our = cust.get("our_quote")
    our_cmp = None
    if our and cust_price:
        our_cmp = {
            "our_quote": our, "customer_price": cust_price,
            "delta": round(our - cust_price, 2),
            "pct": C.pct(our - cust_price, cust_price),
            "note": "我方报价减客户价；正数表示我方更高",
        }

    data = {
        "generated_at": C.today().isoformat(),
        "meta": meta,
        "customer": cust,
        "market": {
            "primary": primary,
            "low": m_low, "high": m_high,
            "reference": cmp_res.get("reference"),
            "tax": primary.get("tax") if primary else None,
            "tax_label": primary.get("tax_label") if primary else None,
            "delivery": primary.get("delivery") if primary else None,
            "date": primary.get("date") if primary else None,
            "source": primary.get("source") if primary else None,
            "url": primary.get("url") if primary else None,
            "conf": primary.get("conf") if primary else None,
            "quote_type": primary.get("quote_type") if primary else None,
        },
        "comparison": cmp_res,
        "band_3m": band3m,
        "verdict": {
            "code": verdict_code, "label": verdict_label, "reasons": why,
            "caliber_missing": caliber_missing,
            "conditional": (caliber_missing and verdict_code in ("high", "low", "match")),
        },
        "windows": windows,
        "history_position": hist_pos,
        "nearest_history_point": nearest,
        "region_compare": reg_cmp,
        "calibers": cal_rows,
        "factors": factors,
        "questions": questions,
        "facts": facts,
        "gaps": data_gaps,
        "events": events,
        "drivers": drivers,
        "futures": futs,
        "modes": modes,
        "method_notes": mnotes,
        "our_quote_compare": our_cmp,
        "steps": steps,
        "history": history,
        "history_secondary": history2,
        "spot_all": spot,
        "region_primary": region,
    }

    if build_dir:
        C.dump_json(data, os.path.join(build_dir, "data.json"))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("research")
    ap.add_argument("--out", default=None,
                    help="data.json 输出路径；给了 --out 就写到该文件，否则写到 --build 目录下")
    ap.add_argument("--build", default="build", help="data.json 输出目录（未给 --out 时使用）")
    a = ap.parse_args()

    res = C.load_json(a.research)
    if a.out:
        target_dir = os.path.dirname(os.path.abspath(a.out))
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        d = assemble(res, None)
        C.dump_json(d, a.out)
        written = a.out
    else:
        os.makedirs(a.build, exist_ok=True)
        d = assemble(res, a.build)
        written = os.path.join(a.build, "data.json")

    print(f"[assemble] 市场区间 = {d['market']['low']}–{d['market']['high']} {d['meta'].get('unit', '元/吨')}"
          f"（{d['market']['source']} {d['market']['date']}）")
    c = d["comparison"]
    if c.get("pos") != "undecidable":
        print(f"[assemble] 客户价 {d['customer'].get('stated_price')} → 偏离 {c['delta_to_dot']:+g} 元/吨 "
              f"（{C.fmt_pct(c['pct_to_dot'])}）")
    print(f"[assemble] 结论 = {d['verdict']['label']}")
    print(f"[assemble] data.json 已写入 {written}")


if __name__ == "__main__":
    main()
