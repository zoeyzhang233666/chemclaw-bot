# -*- coding: utf-8 -*-
"""
fx_engine.py —— 进口付汇汇率敏感性与到厂成本 / 毛利 / 盈亏平衡 计算引擎

设计原则
--------
1. 不写死任何币种、汇率、金额、付款比例。全部来自 input 参数。
2. 严格区分四类汇率（绝不混用）：
     market      —— 市场汇率（ECB 参考汇率 / 交易中心即期价等）
     pboc        —— 中国人民银行授权中国外汇交易中心公布的人民币汇率中间价
     bank        —— 银行实际购汇价（现汇卖出价，进口付汇实际成交价）
     customs     —— 海关计征汇率（海关总署令第272号第十三条：上月第三个星期三中间价）
3. 方向关系固定为“1 单位外币 = x 人民币”（CNY per unit FC）：
     人民币贬值 → x 上升 → 付汇人民币成本上升（+）
     人民币升值 → x 下降 → 付汇人民币成本下降（-）
   若用户给的是 1 CNY = y 外币，引擎先倒数为 x，并在输出中注明换算。
4. 缺参数时返回 None 并写入 missing 清单，绝不臆造利润。

命令行
------
    python fx_engine.py input.json -o output/result.json
    python fx_engine.py --demo                 # 运行引擎自检用例
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

ENGINE_VERSION = "1.0.0"

# 默认敏感性档位（百分比）。可被 input.sensitivity.points 覆盖。
DEFAULT_SENS = [-5.0, -3.0, -1.0, 0.0, 1.0, 3.0, 5.0]


# ----------------------------------------------------------------------------
# 通用工具
# ----------------------------------------------------------------------------
def r2(x: Optional[float]) -> Optional[float]:
    """四舍五入到 2 位小数（None 透传）。

    使用 Decimal + ROUND_HALF_UP，与 Excel/财务口径一致；
    不用内置 round()，因为它是“银行家舍入”（round(0.5)=0），会导致 ±0.005 边界偏差。
    """
    if x is None:
        return None
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def r4(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return float(Decimal(str(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def r6(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return float(Decimal(str(x)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def num(v: Any) -> Optional[float]:
    """安全转数值：None / '' / 非数字 → None。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if not (isinstance(v, float) and math.isnan(v)) else None
    s = str(v).strip().replace(",", "").replace("，", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s: Any) -> Optional[date]:
    if s is None or s == "":
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def third_wednesday(year: int, month: int) -> date:
    """返回指定年月的第三个星期三。

    海关计征汇率口径（海关总署令第272号 第十三条）：
      每月使用的计征汇率 = 上一个月第三个星期三的中间价；
      该日非银行间外汇市场交易日 → 顺延下一个交易日。
    """
    d = date(year, month, 1)
    offset = (2 - d.weekday()) % 7      # 星期三 weekday=2
    return d + timedelta(days=offset + 14)


def prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def customs_rate_date(reference: date) -> date:
    """给定一个日期，返回其适用的“计征汇率基准日”。

    规则：按 reference 所在月份，取上一个月的第三个星期三（未做节假日顺延，
    调用方可传入 trade_calendar 做顺延校正）。
    """
    y, m = prev_month(reference.year, reference.month)
    return third_wednesday(y, m)


def next_trading_day(d: date, holiday_set: set[str]) -> date:
    """跳过周末与给定节假日集合（ISO 字符串）。"""
    cur = d
    for _ in range(30):
        if cur.weekday() < 5 and cur.isoformat() not in holiday_set:
            return cur
        cur += timedelta(days=1)
    return cur


# ----------------------------------------------------------------------------
# 数据类
# ----------------------------------------------------------------------------
@dataclass
class RateSet:
    """一组四个口径的汇率（CNY per 1 unit of foreign currency）。"""
    market: Optional[float] = None
    pboc: Optional[float] = None          # 中间价
    bank: Optional[float] = None          # 银行实际购汇价（现汇卖出价）
    customs: Optional[float] = None       # 海关计征汇率
    market_date: Optional[str] = None
    pboc_date: Optional[str] = None
    bank_date: Optional[str] = None
    customs_date: Optional[str] = None
    source: Dict[str, Any] = field(default_factory=dict)

    def spread_bp(self, basis: str = "pboc") -> Optional[float]:
        """银行购汇价相对某基准的升水（基点 bp，1bp = 0.01%）。"""
        base = getattr(self, basis, None)
        if not base or not self.bank:
            return None
        return (self.bank / base - 1.0) * 10000.0


# ----------------------------------------------------------------------------
# 敏感性
# ----------------------------------------------------------------------------
def apply_sensitivity(base_rate: float, pct: float) -> float:
    """汇率变动 pct%（+ 表示外币升值 / 人民币贬值），返回新汇率 CNY per FC。"""
    return base_rate * (1.0 + pct / 100.0)


def payment_cny(amount_fc: float, rate: float) -> float:
    """付汇人民币金额 = 外币金额 × 汇率。"""
    return amount_fc * rate


def sensitivity_table(amount_fc: float, base_rate: float,
                      points: Optional[List[float]] = None) -> List[Dict[str, Any]]:
    """单笔付汇敏感性表。"""
    pts = points if points else DEFAULT_SENS
    base_cny = payment_cny(amount_fc, base_rate)
    out = []
    for p in pts:
        rate = apply_sensitivity(base_rate, p)
        cny = payment_cny(amount_fc, rate)
        out.append({
            "pct": p,
            "rate": r6(rate),
            "cny": r2(cny),
            "delta_cny": r2(cny - base_cny),
            "delta_pct": r4((cny / base_cny - 1.0) * 100.0) if base_cny else None,
        })
    return out


# ----------------------------------------------------------------------------
# 到厂成本（DDP 口径）
# ----------------------------------------------------------------------------
def landed_cost(amount_fc: float, rate: float,
                freight_fc: float = 0.0, insurance_fc: float = 0.0,
                other_fc: float = 0.0,
                cny_freight: float = 0.0, cny_port: float = 0.0,
                cny_customs_agent: float = 0.0, cny_inland: float = 0.0,
                cny_storage: float = 0.0, cny_bank_fee: float = 0.0,
                cny_other: float = 0.0,
                duty_rate: float = 0.0, cdc_rate: float = 0.0,
                vat_rate: float = 0.13, vat_mode: str = "deductible",
                customs_rate: Optional[float] = None,
                quantity: Optional[float] = None) -> Dict[str, Any]:
    """人民币到厂成本。

    关键区分
    --------
    * 进口环节税（关税、增值税、消费税）的完税价格按 **海关计征汇率** 折算；
      若未提供 customs_rate，则退回使用 rate（并打标记 customs_rate_fallback=True）。
    * 增值税：vat_mode='deductible'（一般纳税人取得增值税专用缴款书可抵扣/留抵）
      → 不计入成本；'cost'（小规模纳税人/不可抵扣）→ 计入成本。
    * 非税费用（港杂/内陆运费/代理费/仓储/银行手续费）按用户给定人民币金额计入，
      这些在多数情况下与汇率无关，是“汇率敏感性被稀释”的来源。

    返回明细，便于逐项核对。
    """
    cust_rate = customs_rate if customs_rate is not None else rate
    fallback = customs_rate is None

    fob_cny = amount_fc * rate
    freight_cny = freight_fc * rate
    ins_cny = insurance_fc * rate
    other_fc_cny = other_fc * rate

    # 完税价格（CIF）按计征汇率折算
    cif_fc = amount_fc + freight_fc + insurance_fc + other_fc
    dutiable_value = cif_fc * cust_rate
    duty = dutiable_value * duty_rate
    cdc = dutiable_value * cdc_rate
    vat_base = dutiable_value + duty + cdc
    vat = vat_base * vat_rate
    vat_in_cost = vat if vat_mode == "cost" else 0.0

    non_fx_cny = cny_freight + cny_port + cny_customs_agent + cny_inland + cny_storage + cny_bank_fee + cny_other

    total = (fob_cny + freight_cny + ins_cny + other_fc_cny
             + duty + cdc + vat_in_cost + non_fx_cny)

    res = {
        "rate_used": r6(rate),
        "customs_rate_used": r6(cust_rate),
        "customs_rate_fallback": fallback,
        "fob_cny": r2(fob_cny),
        "international_freight_cny": r2(freight_cny),
        "insurance_cny": r2(ins_cny),
        "other_fx_fees_cny": r2(other_fc_cny),
        "dutiable_value_cny": r2(dutiable_value),
        "duty_cny": r2(duty),
        "consumption_tax_cny": r2(cdc),
        "vat_base_cny": r2(vat_base),
        "vat_cny": r2(vat),
        "vat_in_cost": r2(vat_in_cost),
        "vat_mode": vat_mode,
        "non_fx_cny": r2(non_fx_cny),
        "landed_cost_cny": r2(total),
    }
    if quantity:
        res["landed_unit_cny"] = r2(total / quantity)
        res["fob_unit_cny"] = r2(fob_cny / quantity)
    # 汇率相关部分 vs 汇率无关部分（用于解释敏感性被稀释）
    fx_linked = fob_cny + freight_cny + ins_cny + other_fc_cny + duty + cdc + vat_in_cost
    res["fx_linked_cny"] = r2(fx_linked)
    res["fx_share"] = r4(fx_linked / total * 100.0) if total else None
    return res


def landed_sensitivity(amount_fc: float, base_rate: float, points: List[float],
                       **landed_kwargs) -> List[Dict[str, Any]]:
    """到厂成本随汇率变化的敏感性表。"""
    base = landed_cost(amount_fc, base_rate, **landed_kwargs)
    base_cost = base["landed_cost_cny"]
    out = []
    for p in points:
        rate = apply_sensitivity(base_rate, p)
        kw = dict(landed_kwargs)
        # 计征汇率若未显式给固定值，则随汇率同步变动
        if kw.get("customs_rate") is not None:
            kw["customs_rate"] = apply_sensitivity(kw["customs_rate"], p)
        lc = landed_cost(amount_fc, rate, **kw)
        out.append({
            "pct": p,
            "rate": r6(rate),
            "fob_cny": lc["fob_cny"],
            "duty_cny": lc["duty_cny"],
            "vat_cny": lc["vat_cny"],
            "landed_cost_cny": lc["landed_cost_cny"],
            "delta_cny": r2(lc["landed_cost_cny"] - base_cost),
            "delta_pct": r4((lc["landed_cost_cny"] / base_cost - 1.0) * 100.0) if base_cost else None,
            "landed_unit_cny": lc.get("landed_unit_cny"),
        })
    return out


# ----------------------------------------------------------------------------
# 毛利
# ----------------------------------------------------------------------------
def gross_margin(landed: float, other_cost_cny: float, quantity: float,
                 sales_price_cny: float, vat_rate: float = 0.13,
                 revenue_basis: str = "tax_included") -> Dict[str, Any]:
    """毛利额与毛利率。

    毛利率分母固定为 **不含税销售收入**（会计口径），revenue_basis 仅说明报价口径：
      tax_included    —— 销售价含增值税，收入 = 价 / (1 + 13%)
      tax_excluded    —— 销售价不含税，收入 = 价
    """
    revenue_unit = sales_price_cny / (1 + vat_rate) if revenue_basis == "tax_included" else sales_price_cny
    revenue = revenue_unit * quantity
    cost = landed + other_cost_cny
    profit = revenue - cost
    return {
        "revenue_cny": r2(revenue),
        "revenue_unit_cny": r4(revenue_unit),
        "total_cost_cny": r2(cost),
        "gross_profit_cny": r2(profit),
        "gross_margin_pct": r4(profit / revenue * 100.0) if revenue else None,
        "cost_per_unit_cny": r2(cost / quantity) if quantity else None,
    }


def breakeven_rate(base_landed: float, base_revenue: float,
                   fx_linked_cny: float, base_rate: float,
                   target_margin_pct: float = 0.0,
                   other_fixed_cny: float = 0.0) -> Dict[str, Any]:
    """盈亏平衡汇率（换算断点分析）。

    思路：目标毛利 = target_margin_pct% × 收入。
      允许成本 = 收入 × (1 − 目标毛利率)
      汇率相关成本随汇率线性变动，其余成本固定。
      令  R0 − C0 = 毛利；  C0 = FX0 + NF
        其中 FX0 为汇率相关成本（正比于汇率），NF 为不随汇率变动的全部成本
        （= 到厂成本中的人民币固定费用 + 国内销售端的非汇率成本 other_fixed_cny）
      FX0(λ) = FX0 × λ，λ = 新汇率 / 基准汇率
      毛利(λ) = R0 − NF − FX0λ = target × R0
      ⇒ λ* = [R0(1 − target) − NF] / FX0

    注：other_fixed_cny 必须传入，否则“基准毛利率”会被高估，
    导致本已低于目标毛利的场景被误判为“适用”。
    """
    nf = base_landed + (other_fixed_cny or 0.0) - fx_linked_cny
    target = target_margin_pct / 100.0
    numer = base_revenue * (1.0 - target) - nf
    if fx_linked_cny <= 0:
        return {"feasible": False, "reason": "汇率相关成本为 0，不存在汇率盈亏平衡点",
                "target_margin_pct": target_margin_pct}
    lam = numer / fx_linked_cny
    base_margin = ((base_revenue - nf - fx_linked_cny) / base_revenue * 100.0) if base_revenue else None

    # 适用性判断：只有当前汇率下已达成目标毛利时，
    # “汇率上升到 λ* 后毛利跌至目标”才有商业含义。
    if base_margin is not None and base_margin < target_margin_pct - 1e-9:
        return {
            "feasible": False,
            "applicable": False,
            "reason": (f"基准情景毛利率 {base_margin:.2f}% 已低于目标 {target_margin_pct:.0f}%，"
                       f"汇率即使走弱也无法达到该目标毛利；盈亏平衡汇率不适用。"),
            "target_margin_pct": target_margin_pct,
            "base_margin_pct": r4(base_margin),
            "reference_rate": r6(base_rate * lam) if lam else None,
            "reference_move_pct": r4((lam - 1.0) * 100.0) if lam else None,
        }
    if lam <= 0:
        return {"feasible": False, "applicable": False,
                "reason": "在目标毛利下，即使汇率趋近于 0 也无法达成（毛利率受非汇率成本挤压）",
                "target_margin_pct": target_margin_pct,
                "base_margin_pct": r4(base_margin)}
    rate_be = base_rate * lam
    return {
        "feasible": True,
        "applicable": True,
        "target_margin_pct": target_margin_pct,
        "base_margin_pct": r4(base_margin),
        "lambda": r6(lam),
        "breakeven_rate": r6(rate_be),
        "rate_move_pct": r4((lam - 1.0) * 100.0),
        "headroom_cny": r2((lam - 1.0) * fx_linked_cny),
        "formula": "λ* = [R0·(1−m) − NF] / FX0 ; 汇率* = 基准汇率 × λ*",
        "base_landed_cny": r2(base_landed),
        "fx_linked_cny": r2(fx_linked_cny),
        "non_fx_cost_cny": r2(nf),
        "base_revenue_cny": r2(base_revenue),
    }


# ----------------------------------------------------------------------------
# 分批付款
# ----------------------------------------------------------------------------
def tranche_analysis(tranches: List[Dict[str, Any]], base_rate: float,
                     scenario_rate: float,
                     payment_date: Optional[date] = None,
                     cash_days: int = 0) -> List[Dict[str, Any]]:
    """分批付款测算。

    tranches: [{"name": "预付款", "pct": 0.30, "days": 0, "rate_override": null}, ...]
      pct          —— 占合同金额比例（总和应 = 1）
      days         —— 相对合同基准日的付款天数（>0 表示延后付款）
      rate_override—— 该笔若已锁价/已确定汇率，直接给定（CNY per FC）

    每笔按 scenario_rate 计价（若未 override）：
      情景金额 = 外币金额 × 情景汇率
    基准金额 = 外币金额 × 基准汇率
    """
    total_pct = sum(num(t.get("pct")) or 0 for t in tranches)
    out = []
    base_total = 0.0
    scen_total = 0.0
    for t in tranches:
        pct = num(t.get("pct")) or 0.0
        days = int(num(t.get("days")) or 0)
        ov = num(t.get("rate_override"))
        rate = ov if ov is not None else scenario_rate
        base_rate_t = ov if ov is not None else base_rate
        amount_fc = (num(t.get("amount_fc")) or 0.0)
        rate_used_scen = rate
        rate_used_base = base_rate_t
        # 金额若未直接给，则在外部按 pct × 合同金额填充
        scen_cny = amount_fc * rate_used_scen
        base_cny = amount_fc * rate_used_base
        pay_date = (payment_date + timedelta(days=days)).isoformat() if payment_date else None
        settle_date = (payment_date + timedelta(days=days + cash_days)).isoformat() if payment_date else None
        out.append({
            "name": t.get("name"),
            "pct": pct,
            "days": days,
            "amount_fc": r2(amount_fc),
            "rate_locked": r6(ov),
            "scenario_rate": r6(rate_used_scen),
            "base_rate": r6(rate_used_base),
            "payment_date": pay_date,
            "settlement_date": settle_date,
            "scenario_cny": r2(scen_cny),
            "base_cny": r2(base_cny),
            "delta_cny": r2(scen_cny - base_cny),
        })
        base_total += base_cny
        scen_total += scen_cny
    return out, {"total_pct": r6(total_pct), "pct_ok": abs(total_pct - 1.0) < 1e-6,
                 "base_total_cny": r2(base_total), "scenario_total_cny": r2(scen_total),
                 "delta_cny": r2(scen_total - base_total)}


def fill_tranche_amounts(tranches: List[Dict[str, Any]], contract_fc: float) -> List[Dict[str, Any]]:
    """未显式给出 amount_fc 的批次，按 pct × 合同金额补齐。"""
    out = []
    for t in tranches:
        t2 = dict(t)
        if num(t2.get("amount_fc")) is None:
            t2["amount_fc"] = (num(t2.get("pct")) or 0.0) * contract_fc
        out.append(t2)
    return out


# ----------------------------------------------------------------------------
# 历史分位
# ----------------------------------------------------------------------------
def percentile_rank(series: List[float], value: float) -> Optional[float]:
    """百分位：序列中小于等于 value 的观测占比（0–100）。"""
    if not series:
        return None
    if isinstance(series[0], (list, tuple)):
        vals = [float(x[1]) for x in series]
    else:
        vals = [float(x) for x in series]
    if not vals:
        return None
    n = sum(1 for v in vals if v <= value)
    return r4(n / len(vals) * 100.0)


def series_stats(pairs: List[List[Any]]) -> Dict[str, Any]:
    """pairs: [[date, value], ...] → 统计量。"""
    if not pairs:
        return {}
    vals = [float(p[1]) for p in pairs]
    mn = min(pairs, key=lambda p: float(p[1]))
    mx = max(pairs, key=lambda p: float(p[1]))
    s = sorted(vals)

    def q(p):
        if len(s) == 1:
            return s[0]
        k = (len(s) - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return s[int(k)]
        return s[f] + (s[c] - s[f]) * (k - f)

    return {
        "n": len(vals),
        "start": pairs[0][0],
        "end": pairs[-1][0],
        "last": r6(vals[-1]),
        "first": r6(vals[0]),
        "min": r6(float(mn[1])), "min_date": mn[0],
        "max": r6(float(mx[1])), "max_date": mx[0],
        "mean": r6(sum(vals) / len(vals)),
        "median": r6(q(0.5)),
        "p10": r6(q(0.10)), "p25": r6(q(0.25)), "p75": r6(q(0.75)), "p90": r6(q(0.90)),
        "stdev": r6(math.sqrt(sum((v - sum(vals) / len(vals)) ** 2 for v in vals) / len(vals))),
        "change_pct": r4((vals[-1] / vals[0] - 1) * 100) if vals[0] else None,
    }


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def quote_direction_guard(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """确认报价方向。若为 1 CNY = y FC（如 CNY/SAR），自动倒数为 CNY per FC。"""
    qd = str(inputs.get("quote_direction") or "FC_CNY").upper()
    notes = []
    if qd in ("CNY_FC", "CNY_PER_FC", "CNYFC"):
        notes.append("用户报价方向为 1 CNY = y 外币，已自动取倒数换算为“1 外币 = x 人民币”后再计算。")
        qd = "FC_CNY"
    # 币对顺序
    pair = inputs.get("pair") or f"{inputs.get('foreign_currency','FC')}/CNY"
    return {"direction": qd, "label": "1 单位外币 = x 人民币（CNY per FC）",
            "pair": pair, "notes": notes}


def run(inputs: Dict[str, Any], history: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """执行完整测算。history 为 fx_real_data.json 结构（可选，用于分位）。"""
    missing: List[str] = []
    warnings: List[str] = []
    result: Dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs_echo": inputs,
        "missing": missing,
        "warnings": warnings,
    }

    qd = quote_direction_guard(inputs)
    result["quote_direction"] = qd

    fc = (inputs.get("foreign_currency") or "").upper()
    lc = (inputs.get("local_currency") or "CNY").upper()
    if not fc:
        missing.append("foreign_currency（外币币种，必填）")
    if lc != "CNY":
        warnings.append(f"本次测算的本地货币为 {lc}，引擎默认按人民币 CNY 计价，请确认口径。")

    amount_fc = num(inputs.get("amount_fc"))
    if amount_fc is None:
        missing.append("amount_fc（采购外币金额，必填）")
    direction = str(inputs.get("direction") or "IMPORT_PAYMENT").upper()
    if direction not in ("IMPORT_PAYMENT", "EXPORT_RECEIPT"):
        warnings.append(f"未识别的交易方向 {direction}，已按进口付汇处理。")

    # ---- 汇率口径 ----
    rates_in = inputs.get("rates") or {}
    rs = RateSet(
        market=num(rates_in.get("market")), pboc=num(rates_in.get("pboc")),
        bank=num(rates_in.get("bank")), customs=num(rates_in.get("customs")),
        market_date=rates_in.get("market_date"), pboc_date=rates_in.get("pboc_date"),
        bank_date=rates_in.get("bank_date"), customs_date=rates_in.get("customs_date"),
        source=rates_in.get("source") or {},
    )
    # 倒置换算
    if str(inputs.get("quote_direction", "FC_CNY")).upper() in ("CNY_FC", "CNY_PER_FC", "CNYFC"):
        for k in ("market", "pboc", "bank", "customs"):
            v = getattr(rs, k)
            if v:
                setattr(rs, k, 1.0 / v)
    result["rates"] = asdict(rs)
    result["rates"]["bank_premium_bp_vs_pboc"] = r2(rs.spread_bp("pboc"))
    result["rates"]["bank_premium_bp_vs_market"] = r2(rs.spread_bp("market"))

    # 基准汇率优先级：银行实际购汇价 > 中间价 > 市场汇率
    basis_name, basis_rate = None, None
    for nm, v in (("bank", rs.bank), ("pboc", rs.pboc), ("market", rs.market)):
        if v:
            basis_name, basis_rate = nm, v
            break
    if not basis_rate:
        missing.append("rates.bank / rates.pboc / rates.market（至少一个汇率）")
        result["ok"] = False
        return result
    result["basis"] = {"name": basis_name, "rate": r6(basis_rate),
                       "note": "基准情景优先使用银行实际购汇价（进口付汇真实成交价）；"
                               "未提供则退用中间价，再退用市场汇率。"}
    if basis_name != "bank":
        warnings.append("未提供银行实际购汇价，基准情景按中间价/市场汇率测算；"
                        "实际付汇金额通常会因银行点差略高于此数。")

    if amount_fc is not None:
        # ---- 2) 付款额与敏感性 ----
        sens_pts = [num(x) for x in (inputs.get("sensitivity", {}).get("points") or DEFAULT_SENS)]
        sens_pts = [p for p in sens_pts if p is not None]
        base_cny = payment_cny(amount_fc, basis_rate)
        result["payment"] = {
            "amount_fc": r2(amount_fc),
            "currency": fc,
            "base_rate": r6(basis_rate),
            "base_cny": r2(base_cny),
            "by_quote_basis": {k: {nm: r2(payment_cny(amount_fc, getattr(rs, nm)))
                                   for nm in ("market", "pboc", "bank") if getattr(rs, nm)}
                               for k in ["all"]},
        }
        result["sensitivity_payment"] = sensitivity_table(amount_fc, basis_rate, sens_pts)
        # 各口径对照
        cmp_rows = []
        for nm, label in (("market", "市场汇率"), ("pboc", "人民币汇率中间价"),
                          ("bank", "银行实际购汇价"), ("customs", "海关计征汇率")):
            v = getattr(rs, nm)
            dt_ = getattr(rs, f"{nm}_date")
            cmp_rows.append({"basis": nm, "label": label, "rate": r6(v), "date": dt_,
                             "cny": r2(payment_cny(amount_fc, v)) if v else None,
                             "delta_vs_basis_cny": r2(payment_cny(amount_fc, v) - base_cny) if v else None})
        result["rate_basis_comparison"] = cmp_rows

        # ---- 3) 到厂成本 ----
        cost_in = inputs.get("costs") or {}
        qty = num(inputs.get("quantity"))
        landed_kw = dict(
            freight_fc=num(cost_in.get("freight_fc")) or 0.0,
            insurance_fc=num(cost_in.get("insurance_fc")) or 0.0,
            other_fc=num(cost_in.get("other_fc")) or 0.0,
            cny_freight=num(cost_in.get("cny_freight")) or 0.0,
            cny_port=num(cost_in.get("cny_port")) or 0.0,
            cny_customs_agent=num(cost_in.get("cny_customs_agent")) or 0.0,
            cny_inland=num(cost_in.get("cny_inland")) or 0.0,
            cny_storage=num(cost_in.get("cny_storage")) or 0.0,
            cny_bank_fee=num(cost_in.get("cny_bank_fee")) or 0.0,
            cny_other=num(cost_in.get("cny_other")) or 0.0,
            duty_rate=(num(cost_in.get("duty_rate")) or 0.0) / 100.0,
            cdc_rate=(num(cost_in.get("cdc_rate")) or 0.0) / 100.0,
            vat_rate=(num(cost_in.get("vat_rate")) if num(cost_in.get("vat_rate")) is not None else 13.0) / 100.0,
            vat_mode=cost_in.get("vat_mode") or "deductible",
            customs_rate=rs.customs,
            quantity=qty,
        )
        has_landed_inputs = any([
            landed_kw["freight_fc"], landed_kw["insurance_fc"], landed_kw["other_fc"],
            landed_kw["cny_freight"], landed_kw["cny_port"], landed_kw["cny_customs_agent"],
            landed_kw["cny_inland"], landed_kw["cny_storage"], landed_kw["cny_bank_fee"],
            landed_kw["cny_other"], landed_kw["duty_rate"], landed_kw["vat_rate"],
        ])
        if has_landed_inputs or rs.customs:
            landed = landed_cost(amount_fc, basis_rate, **landed_kw)
            result["landed_cost"] = landed
            result["sensitivity_landed"] = landed_sensitivity(amount_fc, basis_rate, sens_pts, **landed_kw)
            if not rs.customs:
                warnings.append("未提供海关计征汇率，完税价格暂按基准汇率折算（标记 customs_rate_fallback）。")
            result["tax_detail"] = {
                "duty_rate_pct": landed_kw["duty_rate"] * 100,
                "vat_rate_pct": landed_kw["vat_rate"] * 100,
                "vat_mode": landed_kw["vat_mode"],
                "vat_note": ("增值税进项税额可抵扣/留抵，不计入人民币到厂成本" if landed_kw["vat_mode"] == "deductible"
                             else "增值税不可抵扣，计入人民币到厂成本"),
            }

            # ---- 4) 毛利 ----
            sales = inputs.get("sales") or {}
            sp = num(sales.get("price_cny"))
            other_cny_unit = num(sales.get("other_cost_cny_unit"))
            if sp is not None and qty:
                oc = (other_cny_unit or 0.0) * qty
                gm = gross_margin(landed["landed_cost_cny"] / 1.0 * 1.0, oc, qty, sp,
                                  vat_rate=landed_kw["vat_rate"],
                                  revenue_basis=sales.get("revenue_basis") or "tax_included")
                result["gross_margin"] = gm
                # 各汇率下的毛利
                gm_rows = []
                for row in result["sensitivity_landed"]:
                    r_ = apply_sensitivity(basis_rate, row["pct"])
                    kw = dict(landed_kw)
                    if kw.get("customs_rate") is not None:
                        kw["customs_rate"] = apply_sensitivity(kw["customs_rate"], row["pct"])
                    lc_ = landed_cost(amount_fc, r_, **kw)
                    g = gross_margin(lc_["landed_cost_cny"], oc, qty, sp,
                                     vat_rate=landed_kw["vat_rate"],
                                     revenue_basis=sales.get("revenue_basis") or "tax_included")
                    gm_rows.append({"pct": row["pct"], "rate": r6(r_),
                                    "landed_cost_cny": lc_["landed_cost_cny"],
                                    "gross_profit_cny": g["gross_profit_cny"],
                                    "gross_margin_pct": g["gross_margin_pct"]})
                result["gross_margin_sensitivity"] = gm_rows

                # ---- 5) 盈亏平衡汇率 ----
                be_list = []
                for tgt in (sales.get("target_margins_pct") or [0.0]):
                    be_list.append(breakeven_rate(landed["landed_cost_cny"], gm["revenue_cny"],
                                                  landed["fx_linked_cny"], basis_rate, num(tgt) or 0.0,
                                                  other_fixed_cny=oc))
                result["breakeven"] = be_list
                # 预算汇率对应的毛利
                budget = num(inputs.get("budget_rate"))
                if budget:
                    lam = budget / basis_rate
                    new_fx = landed["fx_linked_cny"] * lam
                    new_cost = new_fx + (landed["landed_cost_cny"] - landed["fx_linked_cny"])
                    gb = gross_margin(new_cost, oc, qty, sp, vat_rate=landed_kw["vat_rate"],
                                      revenue_basis=sales.get("revenue_basis") or "tax_included")
                    result["budget_rate_scenario"] = {
                        "budget_rate": r6(budget),
                        "move_vs_basis_pct": r4((lam - 1) * 100),
                        "landed_cost_cny": r2(new_cost),
                        "gross_profit_cny": gb["gross_profit_cny"],
                        "gross_margin_pct": gb["gross_margin_pct"],
                        "delta_profit_cny": r2((gb["gross_profit_cny"] or 0) - (gm["gross_profit_cny"] or 0)),
                    }
            else:
                missing.append("sales.price_cny 与 quantity（用于毛利测算，可留空）")

        # ---- 6) 分批付款 ----
        pay = inputs.get("payment") or {}
        tranches = pay.get("tranches") or []
        if tranches:
            tranches = fill_tranche_amounts(tranches, amount_fc)
            pdate = parse_date(pay.get("payment_date"))
            cash_days = int(num(pay.get("cash_days")) or 0)
            scen_pts = [num(x) for x in (pay.get("scenario_pct") or [0.0, 1.0, 3.0, 5.0])]
            scen_pts = [p for p in scen_pts if p is not None]
            scen_out = []
            for p in scen_pts:
                r_ = apply_sensitivity(basis_rate, p)
                rows, tot = tranche_analysis(tranches, basis_rate, r_, pdate, cash_days)
                scen_out.append({"pct": p, "rate": r6(r_), "tranches": rows, "total": tot})
            result["tranches"] = {
                "contract_fc": r2(amount_fc),
                "payment_date": pay.get("payment_date"),
                "scenarios": scen_out,
                "pct_ok": scen_out[0]["total"]["pct_ok"] if scen_out else None,
            }
            if scen_out and not scen_out[0]["total"]["pct_ok"]:
                warnings.append(f"分批付款比例合计为 {scen_out[0]['total']['total_pct']}，不等于 1.00，请核对。")

    # ---- 历史分位 ----
    if history:
        series_key = f"{fc}CNY"
        daily = history.get("daily", {}).get(series_key)
        if daily:
            windows = inputs.get("history_windows") or [1, 3, 5]
            hs = {}
            for yrs in windows:
                cutoff = (datetime.now().date() - timedelta(days=int(365.25 * yrs))).isoformat()
                sub = [p for p in daily if p[0] >= cutoff]
                if not sub:
                    continue
                st = series_stats(sub)
                vals = [p[1] for p in sub]
                st["percentile_market"] = percentile_rank(vals, rs.market) if rs.market else None
                st["percentile_pboc"] = percentile_rank(vals, rs.pboc) if rs.pboc else None
                st["window_years"] = yrs
                hs[f"{yrs}y"] = st
            result["history"] = {"series": series_key, "windows": hs,
                                 "source": history.get("meta", {})}
        else:
            warnings.append(f"历史数据中缺少 {series_key} 序列，未计算历史分位。")

    result["ok"] = len([m for m in missing if "可留空" not in m]) == 0
    return result


# ----------------------------------------------------------------------------
# 自检用例
# ----------------------------------------------------------------------------
def _demo() -> int:
    fails = 0

    def chk(name, cond, extra=""):
        nonlocal fails
        print(("  PASS " if cond else "  FAIL ") + name + ("  " + extra if extra else ""))
        if not cond:
            fails += 1

    print("=== T1 方向关系：人民币贬值使付汇人民币增加 ===")
    r0 = 7.0
    up = apply_sensitivity(r0, 3)      # 外币升值 3% = 人民币贬值
    chk("+3% 提高人民币成本", payment_cny(1e6, up) > payment_cny(1e6, r0),
        f"{payment_cny(1e6, up):,.2f} > {payment_cny(1e6, r0):,.2f}")
    dn = apply_sensitivity(r0, -3)
    chk("−3% 降低人民币成本", payment_cny(1e6, dn) < payment_cny(1e6, r0))

    print("=== T2 线性一致性 ===")
    t = sensitivity_table(1e6, r0, [-5, -3, -1, 0, 1, 3, 5])
    chk("Δ 与百分比成正比", all(abs(row["delta_cny"] - 1e6 * r0 * row["pct"] / 100) < 0.01 for row in t))
    chk("0% 处 Δ=0", abs([x for x in t if x["pct"] == 0][0]["delta_cny"]) < 1e-9)

    print("=== T3 海关计征汇率日期 ===")
    w = third_wednesday(2026, 9)
    chk("2026-09 第三个星期三是 16 日", w == date(2026, 9, 16), str(w))
    w2 = third_wednesday(2026, 10)
    chk("2026-10 第三个星期三是 21 日", w2 == date(2026, 10, 21), str(w2))
    cd = customs_rate_date(date(2026, 11, 15))
    chk("2026-11 申报 → 取 2026-10-21", cd == date(2026, 10, 21), str(cd))
    cd2 = customs_rate_date(date(2026, 10, 5))
    chk("2026-10 申报 → 取 2026-09-16", cd2 == date(2026, 9, 16), str(cd2))

    print("=== T4 到厂成本：增值税可抵扣口径 ===")
    lc = landed_cost(1e6, 7.0, duty_rate=0.055, vat_rate=0.13, vat_mode="deductible",
                     cny_port=30000, customs_rate=7.0)
    chk("FOB 人民币 = 700 万", abs(lc["fob_cny"] - 7_000_000) < 1)
    chk("关税 = 700万×5.5%", abs(lc["duty_cny"] - 385_000) < 1, f"{lc['duty_cny']}")
    chk("增值税 = (700万+38.5万)×13%", abs(lc["vat_cny"] - 960_050) < 1, f"{lc['vat_cny']}")
    chk("可抵扣→增值税不入成本", abs(lc["vat_in_cost"]) < 1e-9)
    chk("到厂成本 = 700万+38.5万+3万", abs(lc["landed_cost_cny"] - 7_415_000) < 1, f"{lc['landed_cost_cny']}")
    lc2 = landed_cost(1e6, 7.0, duty_rate=0.055, vat_rate=0.13, vat_mode="cost",
                      cny_port=30000, customs_rate=7.0)
    chk("不可抵扣→增值税入成本", abs(lc2["landed_cost_cny"] - (lc["landed_cost_cny"] + lc["vat_cny"])) < 1)

    print("=== T5 到厂成本敏感性 = 付汇敏感性（无税情形）===")
    s1 = sensitivity_table(1e6, 7.0)
    s2 = landed_sensitivity(1e6, 7.0, [x["pct"] for x in s1])
    chk("无税且无人民币费用时两者一致",
        all(abs(a["delta_cny"] - b["delta_cny"]) < 1 for a, b in zip(s1, s2)))

    print("=== T6 毛利与盈亏平衡 ===")
    # 收入 1000万(不含税)，成本 800万，其中汇率相关 700万，非汇率 100万
    be = breakeven_rate(8_000_000, 10_000_000, 7_000_000, 7.0, 0.0)
    # λ* = (1000万 − 100万)/700万 = 1.285714 → 汇率 9.0
    chk("零毛利平衡汇率 = 7 × 9/7 = 9.0", abs(be["breakeven_rate"] - 9.0) < 1e-6, f"{be['breakeven_rate']}")
    be2 = breakeven_rate(8_000_000, 10_000_000, 7_000_000, 7.0, 10.0)
    # λ* = (1000万×0.9 − 100万)/700万 = 800万/700万=1.142857 → 8.0
    chk("10% 毛利平衡汇率 = 8.0", abs(be2["breakeven_rate"] - 8.0) < 1e-6, f"{be2['breakeven_rate']}")

    gm = gross_margin(8_000_000, 0, 1000, 11_300, vat_rate=0.13, revenue_basis="tax_included")
    chk("含税售价换算不含税收入", abs(gm["revenue_cny"] - 10_000_000) < 1, f"{gm['revenue_cny']}")
    chk("毛利率 = (1000-800)/1000 = 20%", abs(gm["gross_margin_pct"] - 20.0) < 1e-6, f"{gm['gross_margin_pct']}")

    print("=== T7 分批付款 ===")
    tr = fill_tranche_amounts([{"name": "预付款", "pct": 0.3, "days": 0},
                               {"name": "尾款", "pct": 0.7, "days": 90}], 1e6)
    rows, tot = tranche_analysis(tr, 7.0, 7.21)
    chk("比例合计 100%", tot["pct_ok"])
    chk("总额 = 100万×7.21", abs(tot["scenario_total_cny"] - 7_210_000) < 1, f"{tot['scenario_total_cny']}")
    chk("差额 = 100万×0.21", abs(tot["delta_cny"] - 210_000) < 1, f"{tot['delta_cny']}")

    print("=== T8 报价方向倒置 ===")
    q = quote_direction_guard({"quote_direction": "CNY_FC"})
    chk("CNY_FC 被识别并提示取倒数", q["direction"] == "FC_CNY" and q["notes"])

    print("=== T9 分位 ===")
    chk("分位 50%", abs(percentile_rank([1, 2, 3, 4], 2) - 50.0) < 1e-9)
    chk("最小值 25%", abs(percentile_rank([1, 2, 3, 4], 1) - 25.0) < 1e-9)

    print(f"\n{'ALL PASS' if fails == 0 else f'{fails} FAILED'}")
    return 0 if fails == 0 else 1


def main(argv: List[str]) -> int:
    if "--demo" in argv:
        return _demo()
    if len(argv) < 2:
        print(__doc__)
        return 2
    inp = argv[1]
    out = None
    if "-o" in argv:
        out = argv[argv.index("-o") + 1]
    hist = None
    if "--history" in argv:
        hist = json.load(open(argv[argv.index("--history") + 1], encoding="utf-8"))
    inputs = json.load(open(inp, encoding="utf-8"))
    res = run(inputs, hist)
    js = json.dumps(res, ensure_ascii=False, indent=2)
    if out:
        import os
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, "w", encoding="utf-8").write(js)
        print("wrote", out)
    else:
        print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
