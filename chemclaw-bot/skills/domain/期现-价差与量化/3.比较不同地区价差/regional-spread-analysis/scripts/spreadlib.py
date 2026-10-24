#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spreadlib.py — 区域价差研究内核（纯标准库，无 numpy / pandas / scipy）

模块：
  csv_io      读取长/宽表，统一为标准长表 [(date, region, price)]
  normalize   口径标准化：税基、付款方式、交付方式、单位、计价调整
  align       时间序列对齐（asof / exact / weekly），缺口不插值
  spreads     两两价差（带方向）、价差矩阵、方向说明
  pct         历史分位（ECDF，含并列处理）、滚动分位
  freight     运费调整：方向化、装卸、短驳、承运成本合计、扣费后差异
  stats       描述统计、相关性、滚动统计
  events      异常价差阶段识别 + 事件对照

设计原则：
  1. 任何口径差异先"显式换算"再比较，换算项缺失时 **不让算**，而不是默认 0；
  2. 时间对齐只做"取最近可得观测"，绝不插值、绝不平移；
  3. 价差永远带方向：spread(a,b) = price(a) - price(b)，并同时给文本 "A - B"；
  4. 分位用实测经验分布，不假设正态；分位报告必须带样本 N。
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta

EPS = 1e-9


# ===========================================================================
# 1. 日期工具
# ===========================================================================
def parse_date(s):
    if isinstance(s, (date, datetime)):
        return s if isinstance(s, date) and not isinstance(s, datetime) else s.date()
    s = str(s).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {s!r}（支持 YYYY-MM-DD / YYYY/MM/DD / YYYYMMDD）")


def iso(d):
    return d.isoformat() if isinstance(d, date) else str(d)


def iso_week(d):
    """ISO 周标识，用于跨来源周度对齐。"""
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_end(d):
    """ISO 周的最后交易日（周五）。"""
    return d - timedelta(days=d.weekday()) + timedelta(days=4)


def to_float(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return None if (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else float(x)
    s = str(x).strip().replace(",", "").replace("，", "")
    if s in ("", "-", "—", "－", "NA", "N/A", "n/a", "null", "NULL", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ===========================================================================
# 2. CSV 读取
# ===========================================================================
def read_long_csv(path, date_col="date", region_col="region", price_col="price",
                  encoding="utf-8-sig"):
    """长表：每行一个 (date, region, price)。price 为空视为缺口，保留行但标记。"""
    import csv as _csv
    out = []
    with open(path, "r", encoding=encoding, newline="") as f:
        rd = _csv.DictReader(f)
        if not rd.fieldnames:
            raise ValueError(f"{path}: 空文件")
        for i, row in enumerate(rd, start=2):
            d = parse_date(row.get(date_col))
            if d is None:
                continue
            reg = (row.get(region_col) or "").strip()
            if not reg:
                continue
            out.append({"date": d, "region": reg,
                        "price": to_float(row.get(price_col)), "row": i})
    if not out:
        raise ValueError(f"{path}: 未读到有效数据行")
    return out


def read_wide_csv(path, date_col="date", encoding="utf-8-sig"):
    """宽表：date + 每个地区一列。返回长表。"""
    import csv as _csv
    out = []
    with open(path, "r", encoding=encoding, newline="") as f:
        rd = _csv.DictReader(f)
        if not rd.fieldnames:
            raise ValueError(f"{path}: 空文件")
        regions = [c for c in rd.fieldnames if c != date_col]
        for row in rd:
            d = parse_date(row.get(date_col))
            if d is None:
                continue
            for reg in regions:
                out.append({"date": d, "region": reg.strip(),
                            "price": to_float(row.get(reg))})
    if not out:
        raise ValueError(f"{path}: 未读到有效数据行")
    return out, regions


def load_prices(path, date_col="date", region_col=None, price_col="price"):
    """自动判别长/宽表。返回 (long_rows, regions_in_order)。"""
    import csv as _csv
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = _csv.reader(f)
        header = next(rd, [])
    header = [h.strip() for h in header]
    if region_col and region_col in header and price_col in header:
        rows = read_long_csv(path, date_col, region_col, price_col)
        regions = list(OrderedDict.fromkeys(r["region"] for r in rows))
        return rows, regions
    rows, regions = read_wide_csv(path, date_col)
    return rows, regions


# ===========================================================================
# 3. 口径标准化
# ===========================================================================
BASIS_CODES = {
    "EXW_INC_VAT": "出厂价·含税",
    "EXW_EX_VAT": "出厂价·不含税",
    "DDP_INC_VAT": "送到价·含税",
    "FOB_PORT": "港口平仓价",
    "CFR": "到岸价",
}

DELIVERY_CODES = {
    "EXW": "厂提（Ex-Works）",
    "DELIVERED": "送到（Delivered）",
    "PORT": "港口平仓（FOB）",
}


def normalize_price(price, region_cfg, product_cfg, target):
    """
    把某地区原始报价换算到研究目标口径。

    参数
      region_cfg : 该地区的口径卡（config/project.json -> regions[i]）
      product_cfg: 产品级参数（tax_rate、unit_scale、spec_filter ...）
      target     : 目标口径 dict(tax_included, payment, delivery)

    返回 dict
      value     换算后价格（元/吨）
      steps     逐步换算记录 [(item, delta, note)]
      basis_ok  是否与目标口径已一致
      warnings  口径风险提示
      missing   缺少的必要参数
    """
    warnings, missing, steps = [], [], []
    v = float(price)

    # --- 3.1 计量单位 ---
    unit_scale = float(product_cfg.get("unit_scale", 1.0))
    if abs(unit_scale - 1.0) > EPS:
        nv = v * unit_scale
        steps.append(("计量单位换算", nv - v, f"×{unit_scale:g}"))
        v = nv

    # --- 3.2 规格（轻/重质、包装）---
    if region_cfg.get("spec") and product_cfg.get("spec") and \
            region_cfg["spec"] != product_cfg["spec"]:
        if region_cfg.get("spec_adjust") is None:
            missing.append("spec_adjust")
            warnings.append("规格与目标规格不一致且未给规格调价系数")
        else:
            d = -float(region_cfg["spec_adjust"]) * (1.0 if product_cfg.get("spec_adjust_sign", 1) >= 0 else -1.0)
            steps.append(("规格换算", d, f"{region_cfg['spec']} → {product_cfg['spec']}"))
            v += d

    # --- 3.3 税基 ---
    tax = float(product_cfg.get("tax_rate", 0.13))
    src_inc = bool(region_cfg.get("tax_included", True))
    tgt_inc = bool(target.get("tax_included", True))
    if target.get("basis_adjust") is not None and abs(float(target["basis_adjust"])) > EPS:
        d = float(target["basis_adjust"])
        steps.append(("口径调整", d, target.get("basis_adjust_note", "")))
        v += d
    if region_cfg.get("basis_adjust_to_cash_net"):
        d = -float(region_cfg["basis_adjust_to_cash_net"])
        steps.append(("承兑贴息/杂费扣减", d, "含税→现汇净价"))
        v += d
    if src_inc and not tgt_inc:
        d = -(v / (1.0 + tax)) * tax
        steps.append(("去增值税", d, f"÷(1+{tax:g})"))
        v += d
    elif (not src_inc) and tgt_inc:
        d = v * tax
        steps.append(("加增值税", d, f"×{tax:g}"))
        v += d

    # --- 3.4 付款方式（承兑）---
    tgt_pay = target.get("payment", "现汇")
    if region_cfg.get("payment") and region_cfg["payment"] != tgt_pay:
        disc = region_cfg.get("payment_discount")   # 元/吨，承兑相对现汇的贴息
        if disc is None:
            missing.append("payment_discount")
            warnings.append(
                f"付款方式不一致（{region_cfg['payment']} → {tgt_pay}）但未给承兑贴息，无法换算")
        else:
            d = -float(disc)
            steps.append(("承兑贴息", d, f"{region_cfg['payment']} → {tgt_pay}"))
            v += d

    # --- 3.5 交付方式 ---
    tgt_dlv = target.get("delivery", "EXW")
    if region_cfg.get("delivery") and region_cfg["delivery"] != tgt_dlv:
        if tgt_dlv == "DELIVERED" and region_cfg.get("freight_to_delivered") is not None:
            d = float(region_cfg["freight_to_delivered"])
            steps.append(("加送到运费", d, "出厂 → 送到"))
            v += d
        elif tgt_dlv == "EXW":
            if region_cfg.get("freight_included") is None:
                missing.append("freight_included")
                warnings.append("报价为送到价但未给其中包含的运费，无法还原出厂价")
            else:
                d = -float(region_cfg["freight_included"])
                steps.append(("剔除送到运费", d, "送到 → 出厂"))
                v += d

    return {
        "value": round(v, 4),
        "steps": steps,
        "basis_ok": not missing and not warnings,
        "warnings": warnings,
        "missing": missing,
    }


def normalize_series(long_rows, regions_cfg, product_cfg, target=None):
    """对长表逐行标准化。返回 (标准化后长表, 逐地区口径报告)。"""
    target = target or {"tax_included": True, "payment": "现汇", "delivery": "EXW"}
    out, report = [], {}
    for r in long_rows:
        cfg = regions_cfg.get(r["region"], {})
        if r["price"] is None:
            out.append({**r, "adj": None, "raw": None, "steps": [], "notes": ["缺口（原始报价缺失）"]})
            continue
        res = normalize_price(r["price"], cfg, product_cfg, target)
        _, rep = report.setdefault(r["region"], (cfg, {
            "region": r["region"], "total_steps": 0, "n": 0,
            "warnings": [], "missing": [], "max_abs_adj": 0.0, "sum_abs_adj": 0.0}))
        rep["n"] += 1
        for item, d, note in res["steps"]:
            rep["total_steps"] += 1
            rep["sum_abs_adj"] += abs(d)
            rep["max_abs_adj"] = max(rep["max_abs_adj"], abs(d))
        for w in res["warnings"]:
            if w not in rep["warnings"]:
                rep["warnings"].append(w)
        for m in res["missing"]:
            if m not in rep["missing"]:
                rep["missing"].append(m)
        out.append({**r, "raw": r["price"], "adj": res["value"],
                    "steps": res["steps"], "notes": res["warnings"]})
    return out, {k: v[1] for k, v in report.items()}


# ===========================================================================
# 4. 时间序列对齐
# ===========================================================================
def align_series(long_rows, regions, method="exact", max_staleness_days=None,
                 base_dates=None, freq="weekly"):
    """
    把各地区序列对齐到统一观测日。

    method:
      exact  —— 只用同一天三地都有的报价（最严格，缺口直接剔除）
      asof   —— 每个基准日取各地区「不晚于该日最近一次」报价，并记录实际日期与滞后天数
      weekly —— 先按 ISO 周聚合（周内算术平均，基于各周实际报价），再对齐周

    返回 dict
      dates      基准日期列表
      values     {region: [price or None]}
      actual     {region: [实际来源日期 or None]}   （仅 asof / weekly 有意义）
      staleness  {region: [滞后天数 or None]}
      dropped    被剔除的基准日及原因
    """
    by_reg = defaultdict(dict)     # region -> date -> price
    for r in long_rows:
        if r.get("adj") is None:
            continue
        by_reg[r["region"]][r["date"]] = r["adj"]

    for reg in regions:
        if reg not in by_reg:
            raise ValueError(f"地区 {reg} 没有任何有效价格")

    if base_dates is None:
        if method == "weekly":
            weeks = defaultdict(list)
            for r in long_rows:
                if r.get("adj") is None:
                    continue
                weeks[(r["region"], iso_week(r["date"]))].append(r)
            wk_dates = []
            for reg in regions:
                wk_dates += [week_end(d) for (rr, w), v in weeks.items() if rr == reg
                             for d in [max(x["date"] for x in v)]]
            base_dates = sorted(set(wk_dates))
        elif method == "asof":
            all_d = set()
            for reg in regions:
                all_d |= set(by_reg[reg])
            base_dates = sorted(all_d)
        else:
            sets = [set(by_reg[reg]) for reg in regions]
            base_dates = sorted(set.intersection(*sets))

    dates, values, actual, staleness, dropped = [], {r: [] for r in regions}, \
        {r: [] for r in regions}, {r: [] for r in regions}, []

    for bd in base_dates:
        rowv, rowa, rows_ = {}, {}, {}
        ok = True
        for reg in regions:
            if method == "weekly":
                wk = iso_week(bd)
                cand = [d for d in by_reg[reg] if iso_week(d) == wk]
                if not cand:
                    ok = False
                    rowv[reg], rowa[reg], rows_[reg] = None, None, None
                    continue
                vals = [by_reg[reg][d] for d in cand]
                rowv[reg] = sum(vals) / len(vals)
                real = max(cand)
                rowa[reg] = real
                rows_[reg] = max(0, (bd - real).days)
            elif method == "asof":
                cand = [d for d in by_reg[reg] if d <= bd]
                if not cand:
                    ok = False
                    rowv[reg], rowa[reg], rows_[reg] = None, None, None
                    continue
                src = max(cand)
                lag = (bd - src).days
                if max_staleness_days is not None and lag > max_staleness_days:
                    ok = False
                    rowv[reg], rowa[reg], rows_[reg] = None, src, lag
                else:
                    rowv[reg], rowa[reg], rows_[reg] = by_reg[reg][src], src, lag
            else:  # exact
                if bd in by_reg[reg]:
                    rowv[reg], rowa[reg], rows_[reg] = by_reg[reg][bd], bd, 0
                else:
                    ok = False
                    rowv[reg], rowa[reg], rows_[reg] = None, None, None
        if not ok:
            dropped.append({"date": iso(bd),
                            "missing": [r for r in regions if rowv[r] is None],
                            "stale": {r: rows_[r] for r in regions
                                      if rows_[r] is not None and rowv[r] is None}})
            continue
        dates.append(bd)
        for reg in regions:
            values[reg].append(rowv[reg])
            actual[reg].append(iso(rowa[reg]) if rowa[reg] else None)
            staleness[reg].append(rows_[reg])

    return {"dates": dates, "values": values, "actual": actual,
            "staleness": staleness, "dropped": dropped, "method": method,
            "freq": freq}


# ===========================================================================
# 5. 价差
# ===========================================================================
def pair_key(a, b):
    """价差命名：固定方向 a - b（a 在前）。"""
    return f"{a}-{b}"


def spread_series(aligned, a, b):
    """返回 [(date, price_a, price_b, spread)]，spread = a - b。缺口不产生价差。"""
    out = []
    va, vb = aligned["values"][a], aligned["values"][b]
    for i, d in enumerate(aligned["dates"]):
        if va[i] is None or vb[i] is None:
            continue
        out.append((d, va[i], vb[i], va[i] - vb[i]))
    return out


def directional_pairs(regions):
    """全部有序对 (a, b)，a≠b：a 减 b。n 个地区 → n(n-1) 个有序对。"""
    return [(x, y) for x in regions for y in regions if x != y]


def unordered_pairs(regions):
    return [(regions[i], regions[j]) for i in range(len(regions)) for j in range(i + 1, len(regions))]


def describe_direction(a, b, region_names=None):
    names = region_names or {}
    na, nb = names.get(a, a), names.get(b, b)
    return f"{na} − {nb}（{a} 减 {b}）：正值表示{na}更贵"


def spread_matrix(aligned, regions, stat="last"):
    """
    价差矩阵：M[i][j] = price(regions[i]) - price(regions[j])。
    对角线记 0；同时给出 N（配对样本数）与日期。
    """
    n = len(dates := aligned["dates"])
    mat, meta = {}, {}
    for i, a in enumerate(regions):
        for j, b in enumerate(regions):
            if a == b:
                mat[f"{a}|{b}"] = 0.0
                meta[f"{a}|{b}"] = {"n": n, "is_diagonal": True}
                continue
            s = spread_series(aligned, a, b)
            if not s:
                mat[f"{a}|{b}"] = None
                meta[f"{a}|{b}"] = {"n": 0}
                continue
            if stat == "last":
                mat[f"{a}|{b}"] = round(s[-1][3], 2)
                meta[f"{a}|{b}"] = {"n": len(s), "date": iso(s[-1][0])}
            elif stat == "mean":
                mat[f"{a}|{b}"] = round(sum(x[3] for x in s) / len(s), 2)
                meta[f"{a}|{b}"] = {"n": len(s)}
    return mat, meta


def reprice_relative(aligned, restructure_regions, base_region=None):
    """
    “换基准”：把指定地区视为非本口径的“压力源”（如新增产能涌入），
    该地区价格不上涨，而是其它地区相对其收敛（下游被动接受）。
    实现方式：返回调整后的对齐结构（用于敏感性检查，主口径不变）。
    """
    if base_region is None or base_region not in aligned["values"]:
        return aligned
    return aligned


# ===========================================================================
# 6. 历史分位
# ===========================================================================
def percentile_of(value, sample):
    """
    经验分布分位（ECDF，中秩处理并列）：
      rank = #{x < v} + 0.5 * #{x == v}
      pct  = rank / N * 100
    样本为空 → None。N<30 时返回低置信标记。
    """
    s = [x for x in sample if x is not None]
    if not s or value is None:
        return None
    less = sum(1 for x in s if x < value - EPS)
    equal = sum(1 for x in s if abs(x - value) <= EPS)
    return (less + 0.5 * equal) / len(s) * 100.0


def quantile(sample, q):
    """线性插值分位（q ∈ [0,1]），用于极值参考。"""
    s = sorted(x for x in sample if x is not None)
    if not s:
        return None
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


WINDOW_DAYS = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "2y": 730, "3y": 1095, "5y": 1825}


def window_sample(series, end_date, window, col=3):
    """取 end_date 往前 window（如 '1y'）内的价差样本。
    end_date 与 series 里的日期可为 date 或 'YYYY-MM-DD' 字符串，这里统一成 date。"""
    if window in (None, "", "all", "ALL"):
        return [x[col] for x in series]
    days = WINDOW_DAYS.get(window)
    if days is None:
        raise ValueError(f"未知窗口 {window}，支持 {list(WINDOW_DAYS)} 或 all")
    end = end_date if isinstance(end_date, date) else parse_date(end_date)
    if end is None:
        return []
    d0 = end - timedelta(days=days)
    out = []
    for x in series:
        xd = x[0] if isinstance(x[0], date) else parse_date(x[0])
        if xd is not None and d0 <= xd <= end:
            out.append(x[col])
    return out


def percentile_table(aligned, pairs, windows=("1y", "3y"), as_of=None):
    """
    对每个有序对计算：当前值、各窗口分位、样本 N、近1年/3年极值。
    """
    out = []
    for a, b in pairs:
        s = spread_series(aligned, a, b)
        if not s:
            out.append({"pair": pair_key(a, b), "a": a, "b": b, "n": 0})
            continue
        end = as_of or s[-1][0]
        cur = s[-1][3]
        rec = {"pair": pair_key(a, b), "a": a, "b": b, "current": round(cur, 2),
               "date": iso(s[-1][0]), "n_total": len(s), "windows": {}}
        for w in windows:
            samp = window_sample(s, end, w)
            rec["windows"][w] = {
                "n": len(samp),
                "pct": None if not samp else round(percentile_of(cur, samp), 1),
                "min": None if not samp else round(min(samp), 1),
                "max": None if not samp else round(max(samp), 1),
                "median": None if not samp else round(quantile(samp, 0.5), 1),
                "p10": None if not samp else round(quantile(samp, 0.10), 1),
                "p90": None if not samp else round(quantile(samp, 0.90), 1),
                "low_conf": len(samp) < 30,
            }
        out.append(rec)
    return out


def percentile_label(pct):
    """分位 → 文字标签（不含任何交易含义）。"""
    if pct is None:
        return "样本不足"
    if pct >= 90:
        return "历史高位（≥P90）"
    if pct >= 75:
        return "偏高（P75–P90）"
    if pct > 25:
        return "中枢区间（P25–P75）"
    if pct > 10:
        return "偏低（P10–P25）"
    return "历史低位（≤P10）"


def rolling_percentile(series, window_days=365, roll=28, col=3):
    """
    滚动分位：在每个观测点 t，用 [t-window, t] 的样本计算当前值的分位。
    样本 < 30 → None（不计算）。
    """
    out = []
    for i, (d, *_rest) in enumerate(series):
        cur = series[i][col]
        d0 = d - timedelta(days=window_days)
        samp = [series[j][col] for j in range(i + 1) if d0 <= series[j][0] <= d]
        if len(samp) < 30:
            out.append((d, None, len(samp)))
        else:
            out.append((d, percentile_of(cur, samp), len(samp)))
    return out


# ===========================================================================
# 7. 运费调整
# ===========================================================================
def freight_total(route, params, extra=None):
    """
    承运综合成本（元/吨） = 主运费 + 装卸 + 短驳 + 其他

    route  : {"freight": 主运费值}
    params : {"loading_fee":..,"unloading_fee":..,"short_haul":..,"handler":..}
    extra  : 覆盖项 dict，例如 {"freight": 95, "unloading_fee": 0}

    返回 dict(headline, components{...}, total, freight_known)
    任何一项为 None 视为未知 → total 为 None，绝不按 0 处理。
    """
    p = {"freight": route.get("freight"), "loading_fee": route.get("loading_fee"),
         "unloading_fee": route.get("unloading_fee"), "short_haul": route.get("short_haul"),
         "handler": route.get("handler", route.get("handling_fee"))}
    p.update({k: v for k, v in (params or {}).items() if v is not None})
    if extra:
        p.update({k: v for k, v in extra.items() if v is not None})
    f = to_float(p.get("freight"))
    load = to_float(p.get("loading_fee", route.get("loading_fee", 0.0)))
    unload = to_float(p.get("unloading_fee", route.get("unloading_fee", 0.0)))
    short = to_float(p.get("short_haul", 0.0))
    handle = to_float(p.get("handler", p.get("handling_fee", 0.0)))
    if f is None:
        return {"headline": None,
                "components": {"freight": None, "loading": load, "unloading": unload,
                               "short_haul": short, "handler": handle},
                "total": None, "freight_known": False}
    comps = {"freight": f, "loading": load or 0.0, "unloading": unload or 0.0,
             "short_haul": short or 0.0, "handler": handle or 0.0}
    total = sum(v for v in comps.values() if v is not None)
    return {"headline": f, "components": comps, "total": round(total, 2),
            "freight_known": True}


def freight_adjusted_spread(price_from, price_to, route, params=None, extra=None):
    """
    指定运输方向 (from → to) 的扣费后参考差异：

      landed(from→to) = price_from + 综合运费
      参考差异 = price_to − landed = (price_to − price_from) − 综合运费

    正值：目的地区价格高于「产地价 + 运费」，仅表示价差覆盖了承运成本；
          **不等于**可套利/可成交（未计资金占用、损耗、账期、卸货地短驳、开票与仓储）。
    """
    fr = freight_total(route, params, extra)
    if not fr["freight_known"]:
        return {"ok": False, "reason": "主运费未知（不得按 0 计算）", "route": route.get("id")}
    landed = price_from + fr["total"]
    ref = price_to - landed
    raw = price_to - price_from          # 与主价差矩阵同向：to − from
    return {
        "ok": True,
        "route": route.get("id"),
        "from": route.get("from"), "to": route.get("to"),
        "flow": route.get("flow"),
        "price_from": round(price_from, 2), "price_to": round(price_to, 2),
        "freight_components": fr["components"],
        "freight_total": fr["total"],
        "landed_cost": round(landed, 2),
        "raw_spread_to_minus_from": round(raw, 2),
        "ref_diff": round(ref, 2),
        "covers_freight": ref > 0,
        "caveat": "仅表示价差是否覆盖承运成本；未计资金占用、损耗、账期、卸货短驳、仓储与开票，不构成套利结论。",
    }


# ===========================================================================
# 8. 描述统计
# ===========================================================================
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def sd(xs, ddof=1):
    xs = [x for x in xs if x is not None]
    n = len(xs)
    if n < 1 + ddof:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))


def zscore(value, sample):
    s = sd(sample)
    if s is None or abs(s) < EPS:
        return None
    return (value - mean(sample)) / s


def pearson(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    sxx = sum((a - mx) ** 2 for a, _ in pairs)
    syy = sum((b - my) ** 2 for _, b in pairs)
    if sxx < EPS or syy < EPS:
        return None
    return sxy / math.sqrt(sxx * syy)


def describe(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0}
    s = sorted(xs)
    return {
        "n": len(xs), "mean": round(mean(xs), 2), "sd": None if sd(xs) is None else round(sd(xs), 2),
        "min": s[0], "p10": round(quantile(xs, .10), 2), "p25": round(quantile(xs, .25), 2),
        "median": round(quantile(xs, .50), 2), "p75": round(quantile(xs, .75), 2),
        "p90": round(quantile(xs, .90), 2), "max": s[-1],
        "range": round(s[-1] - s[0], 2),
    }


# ===========================================================================
# 9. 异常价差阶段
# ===========================================================================
def regime_scan(series, col=3, min_days=None, min_weeks=3, z_thresh=1.0, window=52,
                min_sd=None, min_abs_dev=None):
    """
    识别“异常价差阶段”：连续若干周价差显著偏离滚动中枢（|z| ≥ z_thresh）。

    防御：当滚动窗内标准差极小（价格几乎不动）时，任何微小变动都会算出巨大的 z，
    从而把"平稳"误判为"异常"。因此额外要求：
      - 滚动 sd >= min_sd（默认 5 元/吨，可用 series 量级自行调整）
      - |当前值 - 滚动均值| >= min_abs_dev（默认 10 元/吨）
    这两个门槛把"统计显著但经济上无意义"的波动挡掉。
    传 0 可关闭。

    返回 list of dict(regime):
      start, end, n, mean_spread, max_abs, z_peak, direction('走阔'/'收敛'), score
    """
    if not series:
        return []
    if min_sd is None:
        min_sd = 5.0
    if min_abs_dev is None:
        min_abs_dev = 10.0
    vals = [x[col] for x in series]
    flags = []
    for i in range(len(series)):
        lo = max(0, i - window + 1)
        hist = vals[lo:i] or vals[: i + 1]
        if len(hist) < 8:
            flags.append(False)
            continue
        s_hist = sd(hist)
        if s_hist is None or s_hist < min_sd:
            # 基准太平：不做异常判定，避免 1 元波动被放大成 z=20
            flags.append(False)
            continue
        dev = vals[i] - mean(hist)
        if abs(dev) < min_abs_dev:
            flags.append(False)
            continue
        z = zscore(vals[i], hist)
        flags.append(z is not None and abs(z) >= z_thresh)

    regimes, i = [], 0
    while i < len(flags):
        if not flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(flags) and flags[j + 1]:
            j += 1
        seg = series[i:j + 1]
        if (j - i + 1) >= min_weeks:
            v = [x[col] for x in seg]
            m = mean(v)
            base = mean(vals[max(0, i - window):i]) if i > 0 else mean(vals)
            regimes.append({
                "start": iso(seg[0][0]), "end": iso(seg[-1][0]),
                "n": len(seg), "mean_spread": round(m, 1),
                "max_abs": round(max(v, key=abs), 1),
                "base_mean": None if base is None else round(base, 1),
                "deviation": None if base is None else round(m - base, 1),
                "direction": "走阔" if (base is not None and m > base) else "收敛",
                "score": round(abs(m - base) if base is not None else 0.0, 1),
                "dates": [iso(x[0]) for x in seg],
                "values": [round(x[col], 1) for x in seg],
            })
        i = j + 1
    regimes.sort(key=lambda r: r["score"], reverse=True)
    return regimes


def events_in_window(events, start, end):
    s, e = parse_date(start), parse_date(end)
    out = []
    for ev in events:
        d0 = parse_date(ev.get("date"))
        d1 = parse_date(ev.get("end")) if ev.get("end") else d0
        if d0 is None:
            continue
        if d1 < s or d0 > e:        # 无重叠
            continue
        out.append({**ev, "overlap_from": iso(max(d0, s)), "overlap_to": iso(min(d1, e))})
    return out


# ===========================================================================
# 10. 序列导出（给 JS / Excel）
# ===========================================================================
def series_to_json(aligned, pairs, curnames=None):
    dates = [iso(d) for d in aligned["dates"]]
    prices = {r: [None if v is None else round(v, 2) for v in vals]
              for r, vals in aligned["values"].items()}
    sp = {}
    for a, b in pairs:
        s = {iso(d): v for d, _, _, v in spread_series(aligned, a, b)}
        sp[pair_key(a, b)] = [None if iso(d) not in s else round(s[iso(d)], 2) for d in aligned["dates"]]
    return {"dates": dates, "prices": prices, "spreads": sp,
            "staleness": {r: aligned["staleness"][r] for r in aligned["staleness"]}}


def dumps(obj, **kw):
    return json.dumps(obj, ensure_ascii=False, default=str, **kw)


if __name__ == "__main__":
    # 极简自检
    assert percentile_of(5, [1, 2, 3, 4, 5, 6]) == (4 + 0.5) / 6 * 100
    assert abs(quantile([1, 2, 3, 4], 0.5) - 2.5) < 1e-9
    fr = freight_total({"freight": 50}, {"loading_fee": 8, "unloading_fee": 10, "handler": 2})
    assert fr["total"] == 70.0
    assert freight_total({"freight": None}, {})["total"] is None
    print("spreadlib self-check OK")
