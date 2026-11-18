#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""common.py — 通用工具：日期解析、口径判断、偏离计算、格式化。

本文件不含任何品种字面量。所有品种/规格/地区信息都只从数据里读。
仅依赖 Python 标准库。
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re

# ---------------------------------------------------------------- 口径枚举
TAX_VALUES = ("含税", "不含税", "未注明")
DELIVERY_VALUES = ("出厂", "送到", "库提", "集港", "未注明")
PAYMENT_VALUES = ("现金", "现汇", "承兑", "未注明")

# 常见税前/税后换算：仅用于「客户未说明」时的展示，不作为结论
DEFAULT_VAT = 0.13


def today():
    return _dt.date.today()


def parse_date(s):
    """'2026-10-20' -> date。容错 '2026/10/20'、'20261020'、'2026-10-20 15:47'。"""
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r"^(\d{4})[-/]?(\d{1,2})[-/]?(\d{1,2})", s)
    if not m:
        return None
    try:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def days_between(a, b):
    da, db = parse_date(a), parse_date(b)
    if not da or not db:
        return None
    return (db - da).days


def norm_tax(v):
    if not v:
        return "未注明"
    v = str(v).strip()
    if "不含税" in v or "未税" in v or "税前" in v:
        return "不含税"
    if "含税" in v:
        return "含税"
    if "未注明" in v or "未注" in v:
        return "未注明"
    return "未注明"


def norm_delivery(v):
    if not v:
        return "未注明"
    v = str(v).strip()
    # 先判送到：有些写「出厂/送到均可」
    if "送到" in v or "到厂" in v or "到货" in v or "到岸" in v:
        return "送到"
    if "出厂" in v or "厂提" in v or "自提" in v:
        return "出厂"
    if "库提" in v or "仓库" in v:
        return "库提"
    if "集港" in v or "港口" in v:
        return "集港"
    return "未注明"


def norm_payment(v):
    if not v:
        return "未注明"
    v = str(v).strip()
    if "承兑" in v or "银承" in v or "商承" in v:
        return "承兑"
    if "现汇" in v:
        return "现汇"
    if "现金" in v or "电汇" in v:
        return "现金"
    return "未注明"


def caliber_equal(a, b):
    """两个口径是否「可直接比较」。返回 (ok, reasons:list[str])。"""
    reasons = []
    ta, tb = norm_tax(a.get("tax")), norm_tax(b.get("tax"))
    da, db = norm_delivery(a.get("delivery")), norm_delivery(b.get("delivery"))
    pa, pb = norm_payment(a.get("payment")), norm_payment(b.get("payment"))
    if ta != tb:
        reasons.append(f"税费口径不同：{ta} vs {tb}")
    if da != db:
        reasons.append(f"交付口径不同：{da} vs {db}")
    if pb != "未注明" and pa != "未注明" and pa != pb:
        reasons.append(f"付款方式不同：{pa} vs {pb}")
    return (len(reasons) == 0), reasons


# ---------------------------------------------------------------- 偏离计算
def pct(part, base):
    if base in (None, 0):
        return None
    return part / base


def compare_to_range(customer, low, high, band_min=None, band_max=None):
    """计算客户价与区间的偏离，并给出「接近 / 略高 / 略低 / 明显偏高 / 明显偏低」判定。

    判定规则（不使用任何固定百分比阈值）：
      ① 客户价落在 [下沿,上沿]                    → 接近市场参考区间
      ② 区间外、距最近端点 ≤ 区间半宽              → 略高于 / 略低于市场参考区间
      ③ 区间外、距最近端点 >  区间半宽              → 明显偏高 / 明显偏低
    「半宽」= (上沿 − 下沿) / 2，即这个市场报价自身的自然尺度。
    若同时给了近3月价格带（band_min/band_max），会额外标注客户价是否也超出历史带，
    用于判断「可能是时间点差异」而不是「明显偏高/偏低」。

    返回 dict:
      delta_to_dot / pct_to_dot     客户价 − 参考点（区间中值）及其比例
      delta_to_low / pct_to_low
      delta_to_high / pct_to_high
      inside                        是否落在 [low, high]
      pos                           inside / above / below / undecidable
      distance_to_edge              区间外时距最近端点的距离（区间内为 0）
      half_width                    区间半宽
      label                         中文结论
      code                          inside / above_slight / below_slight / high / low / undecidable
      band_check                    与近3月价格带的交叉核对（含 band_* 时才有）
    """
    out = {"inside": None, "pos": "undecidable", "label": "无法判定（缺少可比市场价格）",
           "code": "undecidable", "distance_to_edge": None, "half_width": None}
    if customer is None:
        return out
    if low is None and high is None:
        return out
    lo = low if low is not None else high
    hi = high if high is not None else low
    if lo is None or hi is None:
        return out
    if lo > hi:
        lo, hi = hi, lo
    dot = PICK_REFERENCE(lo, hi)
    half = round((hi - lo) / 2.0, 4)
    out.update({
        "low": lo, "high": hi, "reference": dot, "half_width": half,
        "delta_to_dot": round(customer - dot, 2),
        "pct_to_dot": pct(customer - dot, dot),
        "delta_to_low": round(customer - lo, 2),
        "pct_to_low": pct(customer - lo, lo),
        "delta_to_high": round(customer - hi, 2),
        "pct_to_high": pct(customer - hi, hi),
    })

    if lo <= customer <= hi:
        out.update({"inside": True, "pos": "inside", "distance_to_edge": 0,
                    "label": "接近市场参考区间", "code": "inside"})
    else:
        above = customer > hi
        edge = hi if above else lo
        dist = abs(customer - edge)
        out.update({
            "inside": False,
            "pos": "above" if above else "below",
            "distance_to_edge": round(dist, 2),
        })
        if dist <= half:
            out.update({"label": "略高于市场参考区间" if above else "略低于市场参考区间",
                        "code": "above_slight" if above else "below_slight"})
        else:
            out.update({"label": "明显偏高" if above else "明显偏低",
                        "code": "high" if above else "low"})

    if band_min is not None and band_max is not None:
        in_band = band_min <= customer <= band_max
        out["band_check"] = {
            "band_min": band_min, "band_max": band_max,
            "in_band": in_band,
            "also_outside_history": (not in_band),
            "note": ("客户价也超出近3月价格带，『明显』的判断更有把握"
                     if not in_band else
                     "客户价落在近3月价格带内，需考虑是否为不同日期的价格"),
        }
    return out


def PICK_REFERENCE(low, high):
    """参考点取区间中值（不取平均不同来源；仅在单一来源区间内取中值）。"""
    if low is None:
        return high
    if high is None:
        return low
    return round((low + high) / 2.0, 2)


# ---------------------------------------------------------------- 标准化
def to_incl_tax(v, tax, rate=DEFAULT_VAT):
    """把不含税价换成含税价。tax='含税' 原样返回。"""
    if v is None:
        return None
    t = norm_tax(tax)
    if t == "不含税":
        return round(v * (1 + rate), 2)
    return v


def to_excl_tax(v, tax, rate=DEFAULT_VAT):
    if v is None:
        return None
    t = norm_tax(tax)
    if t == "含税":
        return round(v / (1 + rate), 2)
    return v


def fx(unit):
    """统一到元/吨。默认已在元/吨；其它单位需显式换算，否则返回 None（不猜）。"""
    u = (unit or "").strip()
    if u in ("元/吨", "元/t", "CNY/t", "人民币/吨"):
        return 1.0
    if u in ("元/千克", "元/kg"):
        return 1000.0
    if u in ("美元/吨", "USD/t"):
        return None  # 需汇率，不得自行假设
    return None


# ---------------------------------------------------------------- IO
def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def dump_json(obj, path):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 格式化
def fmt_num(v, nd=0, dash="—", thousands=True):
    if v is None:
        return dash
    try:
        if thousands:
            s = f"{v:,.{nd}f}"
        else:
            s = f"{v:.{nd}f}"
        return s
    except (TypeError, ValueError):
        return str(v)


def fmt_pct(v, nd=1, dash="—"):
    if v is None:
        return dash
    try:
        return f"{v*100:+.{nd}f}%"
    except (TypeError, ValueError):
        return str(v)


def fmt_pct_abs(v, nd=1, dash="—"):
    if v is None:
        return dash
    try:
        return f"{abs(v)*100:.{nd}f}%"
    except (TypeError, ValueError):
        return str(v)


def fmt_money(v, dash="—"):
    if v is None:
        return dash
    try:
        return f"{v:,.0f}"
    except (TypeError, ValueError):
        return str(v)


def short_date(s):
    d = parse_date(s)
    return d.strftime("%m-%d") if d else str(s or "—")


if __name__ == "__main__":
    print("ok")
