# -*- coding: utf-8 -*-
"""
calculations.py —— 汇率风险测算计算引擎（币种无关 / 品种无关 / 不预测汇率）

设计原则
--------
1. **不写死任何币种**：所有计算只依赖 "1 单位外币 = 多少个人民币(CNY)" 这一统一口径。
   外币既可能是结算币（USD、EUR…），也可能是 "100 JPY" 这类 100 倍计价单位。
2. **不写死任何汇率**：基准汇率（base_rate）必须先取得、带来源与日期，再喂进来。
3. **不预测**：所有情景只回答 "若汇率变为 R，结果如何"，不外推未来。
4. **出口收汇 / 进口付汇 严格分开**：
   - 出口收汇：人民币收入 = 外币金额 × 汇率 × (1 - 银行费用率)
   - 进口付汇：人民币成本 = 外币金额 × 汇率 × (1 + 银行费用率)
5. 所有函数均为纯函数，便于被 HTML(JS)、Excel(公式)、验证脚本三处交叉核对。

术语
----
- rate            1 单位外币可兑换的人民币数量（单位：CNY/FX 或 CNY/100FX）
- notional_fx     本笔业务外币金额（可含分批）
- cny_cost        人民币成本（可选）
- target_margin   目标毛利率（比例，如 0.12）或目标毛利额（金额）
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# 常量与口径
# ---------------------------------------------------------------------------

DIRECTION_EXPORT = "export"  # 出口收汇：收到外币，换成人民币
DIRECTION_IMPORT = "import"  # 进口付汇：付出人民币，换外币

DIRECTION_LABELS = {
    DIRECTION_EXPORT: "出口收汇",
    DIRECTION_IMPORT: "进口付汇",
}

# 银行费用率(toll) 的方向符号：出口收汇时从收入里扣，进口付汇时加到成本上
def toll_sign(direction: str) -> float:
    _check_direction(direction)
    return -1.0 if direction == DIRECTION_EXPORT else 1.0


def _check_direction(direction: str) -> None:
    if direction not in (DIRECTION_EXPORT, DIRECTION_IMPORT):
        raise ValueError(f"direction 必须是 {DIRECTION_EXPORT!r} 或 {DIRECTION_IMPORT!r}，收到 {direction!r}")


def _check_rate(rate: float) -> float:
    if rate is None or not isinstance(rate, (int, float)) or rate <= 0:
        raise ValueError(f"汇率必须为正数，收到 {rate!r}")
    return float(rate)


# ---------------------------------------------------------------------------
# 1. 汇率折算（统一口径）
# ---------------------------------------------------------------------------

def rate_band(rate: float, band: float = 0.0025) -> dict:
    """由中间价 + 银行点差带 (对称、比例) 推算结汇/购汇用价。

    band 是单侧比例，0.0025 表示 ±0.25%（示例默认值，真实值以银行成交价为准）。
    """
    r = _check_rate(rate)
    return {
        "mid": r,
        "sell_fx": r * (1 - band),        # 银行现汇买入价（银行买你的外币）→ 出口结汇到手价
        "buy_fx": r * (1 + band),         # 银行现汇卖出价（银行卖外币给你）→ 进口购汇付出价
        "band": band,
    }


def pick_rate(rate_mid: float, direction: str, band: float = 0.0025,
              actual_settle_rate: float | None = None) -> dict:
    """选择本次测算使用的汇率口径。

    actual_settle_rate：用户已从银行拿到的实际结汇/购汇价，给了就优先用它（最真实）。
    """
    _check_direction(direction)
    b = rate_band(rate_mid, band)
    if actual_settle_rate is not None:
        used = _check_rate(actual_settle_rate)
        basis = "actual_bank_settle"
    else:
        used = b["sell_fx"] if direction == DIRECTION_EXPORT else b["buy_fx"]
        basis = "mid_x_band_estimate"
    return {
        "used": used,
        "mid": b["mid"],
        "sell_fx": b["sell_fx"],
        "buy_fx": b["buy_fx"],
        "band": band,
        "basis": basis,
        "direction": direction,
    }


# ---------------------------------------------------------------------------
# 2. 核心折算
# ---------------------------------------------------------------------------

def cny_gross(amount_fx: float, rate: float) -> float:
    """外币金额 × 汇率 = 人民币毛额（未扣银行费用）。"""
    return float(amount_fx) * _check_rate(rate)


def cny_net(value_cny: float, toll_rate: float, direction: str) -> float:
    """按方向施加银行费用/点差（比例）。出口：扣减；进口：增加。"""
    tol = float(toll_rate or 0.0)
    if tol < 0:
        raise ValueError("toll_rate 不能为负；方向由 direction 决定")
    return value_cny * (1.0 + toll_sign(direction) * tol)


def business_pnl(amount_fx: float, rate: float, direction: str,
                 cny_cost: float | None = None,
                 toll_rate: float = 0.0) -> dict:
    """单笔业务的收入/成本/毛利。

    - 出口收汇：收益方 = 人民币收入（越大越好），cost = cny_cost
    - 进口付汇：收益方 = 对外付出的人民币（越大越贵），cost = cny_cost（可为 0）
    """
    _check_direction(direction)
    gross = cny_gross(amount_fx, rate)
    net = cny_net(gross, toll_rate, direction)
    out = {
        "direction": direction,
        "rate": rate,
        "amount_fx": amount_fx,
        "gross_cny": gross,
        "toll_cny": abs(gross - net),
        "net_cny": net,
    }
    if direction == DIRECTION_EXPORT:
        out["revenue_cny"] = net
        out["cost_cny"] = float(cny_cost or 0.0)
        out["margin_cny"] = out["revenue_cny"] - out["cost_cny"]
        out["margin_pct"] = (out["margin_cny"] / out["revenue_cny"]) if out["revenue_cny"] else None
    else:
        out["payable_cny"] = net          # 进口：对外付出
        out["base_cost_cny"] = float(cny_cost or 0.0)  # 其他人民币成本（关税/清关/内贸运费…）
        out["total_cost_cny"] = out["payable_cny"] + out["base_cost_cny"]
        out["margin_cny"] = None           # 进口端毛利率需给定销售人民币收入（见 import_margin）
        out["margin_pct"] = None
    return out


def import_margin(amount_fx: float, rate: float, cny_cost_other: float,
                  resale_cny: float, toll_rate: float = 0.0) -> dict:
    """进口付汇端毛利：以进口后的人民币销售收入为分母。

    毛利额 = 人民币销售收入 - (外币货值折算支付 + 其他人民币成本)
    毛利率 = 毛利额 / 人民币销售收入
    """
    b = business_pnl(amount_fx, rate, DIRECTION_IMPORT, cny_cost_other, toll_rate)
    rev = float(resale_cny)
    m = rev - b["total_cost_cny"]
    return {
        "revenue_cny": rev,
        "payable_cny": b["payable_cny"],
        "other_cost_cny": b["base_cost_cny"],
        "total_cost_cny": b["total_cost_cny"],
        "margin_cny": m,
        "margin_pct": (m / rev) if rev else None,
    }


# ---------------------------------------------------------------------------
# 3. 敏感性：汇率 ±n% 时结果如何
# ---------------------------------------------------------------------------

def sensitivity(amount_fx: float, base_rate: float, shifts: Sequence[float],
                direction: str, cny_cost: float | None = None,
                toll_rate: float = 0.0) -> list[dict]:
    """shifts 为比例序列，如 [-0.05, -0.03, -0.01, 0, 0.01, 0.03, 0.05]。

    返回每档的：新汇率、人民币毛额/净额、相对基准的人民币变化额与变化率、
    毛利额与毛利率（给定成本时）。
    """
    _check_direction(direction)
    base = business_pnl(amount_fx, base_rate, direction, cny_cost, toll_rate)
    key = "net_cny"
    rows = []
    for s in shifts:
        r = base_rate * (1 + float(s))
        cur = business_pnl(amount_fx, r, direction, cny_cost, toll_rate)
        delta = cur[key] - base[key]
        rows.append({
            "shift": float(s),
            "rate": r,
            "gross_cny": cur["gross_cny"],
            "net_cny": cur[key],
            "delta_cny": delta,
            "delta_pct_of_base": (delta / base[key]) if base[key] else None,
            "delta_pct_of_notional": (delta / base["gross_cny"]) if base["gross_cny"] else None,
            "margin_cny": cur.get("margin_cny"),
            "margin_pct": cur.get("margin_pct"),
        })
    return rows


def one_percent_value(amount_fx: float, rate: float, toll_rate: float = 0.0) -> float:
    """汇率每变动 1%（相对）对应的人民币金额变化（绝对值，已考虑银行费用率）。"""
    return abs(cny_gross(amount_fx, rate) * (1 - float(toll_rate or 0.0))) * 0.01


# ---------------------------------------------------------------------------
# 4. 毛利与盈亏平衡汇率
# ---------------------------------------------------------------------------

def breakeven_rate_export(cny_cost: float, amount_fx: float, toll_rate: float = 0.0) -> float:
    """出口收汇：毛利额 = 0 时的汇率。

    amount_fx × R × (1 - toll) - cny_cost = 0
    ⇒ R* = cny_cost / (amount_fx × (1 - toll))
    """
    if amount_fx <= 0:
        raise ValueError("amount_fx 必须 > 0")
    denom = float(amount_fx) * (1 - float(toll_rate or 0.0))
    if denom <= 0:
        raise ValueError("amount_fx × (1 - toll_rate) 必须 > 0")
    return float(cny_cost) / denom


def breakeven_rate_import(amount_fx: float, cny_cost_other: float, resale_cny: float,
                          toll_rate: float = 0.0) -> float:
    """进口付汇：毛利额 = 0 时的汇率（汇率越高越亏）。

    resale_rev - (amount_fx × R × (1 + toll) + other_cost) = 0
    ⇒ R* = (resale_rev - other_cost) / (amount_fx × (1 + toll))
    """
    denom = float(amount_fx) * (1 + float(toll_rate or 0.0))
    return (float(resale_cny) - float(cny_cost_other)) / denom


def breakeven_rate_cov(amount_fx: float, rate: float, denom_cny: float,
                       direction: str, toll_rate: float = 0.0) -> float:
    """通用：给定 "分母"（出口=收入，进口=销售收入），求贡献毛利率 = 0 的汇率。

    denom_cny 的口径与 business_pnl 一致（出口用净收入，进口用销售收入）。
    """
    _check_direction(direction)
    if direction == DIRECTION_EXPORT:
        return breakeven_rate_export(denom_cny, amount_fx, toll_rate)
    raise ValueError("进口请用 breakeven_rate_import（需要区分其他人民币成本与销售收入）")


def rate_needed_for_margin(amount_fx: float, cny_cost: float, target_margin: float,
                           toll_rate: float = 0.0, as_amount: bool = False) -> float:
    """出口收汇：要达到目标毛利率/毛利额，所需的最低汇率。

    毛利率版：(A·R·(1-t) - C) / (A·R·(1-t)) = m
             ⇒ A·R·(1-t) = C / (1-m) ⇒ R = C / (A·(1-t)·(1-m))
    毛利额版：A·R·(1-t) - C = M ⇒ R = (C + M) / (A·(1-t))
    """
    if amount_fx <= 0:
        raise ValueError("amount_fx 必须 > 0")
    denom = float(amount_fx) * (1 - float(toll_rate or 0.0))
    if as_amount:
        return (float(cny_cost) + float(target_margin)) / denom
    m = float(target_margin)
    if not -1 < m < 1:
        raise ValueError("target_margin(毛利率) 必须在 (-1, 1) 之间")
    return float(cny_cost) / (denom * (1 - m))


def breakeven_distance(base_rate: float, breakeven_rate: float, direction: str) -> dict:
    """盈亏平衡汇率相对基准汇率的距离（出口跌破 / 进口涨破）。

    delta_pct = 平衡汇率/基准汇率 - 1（带符号）
    出口：负值 = 汇率下跌多少会打平
    进口：正值 = 汇率上涨多少会打平
    """
    delta = breakeven_rate / float(base_rate) - 1.0
    adverse = (delta < 0) if direction == DIRECTION_EXPORT else (delta > 0)
    return {
        "breakeven": breakeven_rate,
        "base_rate": base_rate,
        "delta_pct": delta,
        "is_adverse_side": adverse,
        "label": ("汇率下跌" if direction == DIRECTION_EXPORT else "汇率上涨") + f" {abs(delta):.2%} 即打到平衡点",
    }


def margin_impact(base: dict, scenario: dict) -> dict:
    """把两档测算结果相减，得到毛利影响。"""
    if base.get("margin_cny") is None or scenario.get("margin_cny") is None:
        raise ValueError("两侧都需要 margin 结果")
    return {
        "margin_cny_delta": scenario["margin_cny"] - base["margin_cny"],
        "margin_pct_delta": (scenario["margin_pct"] or 0) - (base["margin_pct"] or 0),
        "revenue_cny_delta": scenario.get("revenue_cny") - base.get("revenue_cny"),
    }


# ---------------------------------------------------------------------------
# 5. 历史分位与区间（只用真实序列，不插值、不外推）
# ---------------------------------------------------------------------------

def _as_series(series: Sequence[tuple[str, float]]) -> list[tuple[str, float]]:
    out = [(str(d), float(v)) for d, v in series]
    out.sort(key=lambda x: x[0])
    return out


def window_slice(series: Sequence[tuple[str, float]], asof: str, years: float) -> list[tuple[str, float]]:
    """按自然日窗口截取 (asof - years×365 天, asof]，两端都留样本。"""
    s = _as_series(series)
    end = date.fromisoformat(asof)
    start = end - timedelta(days=int(round(365 * years)))
    return [(d, v) for d, v in s if start < date.fromisoformat(d) <= end]


def percentile_rank(window: Iterable[tuple[str, float]], value: float) -> float:
    """当前值在窗口中的分位（0~1）。

    口径：分位 = (小于当前值的样本数 + 0.5×等于当前值的样本数) / 样本总数。
    —— 即"历史上有多少比例的交易日低于今天"，等于当前值时按半数计。
    """
    vals = [v for _, v in window]
    if not vals:
        raise ValueError("窗口为空，无法计算分位")
    below = sum(1 for v in vals if v < value)
    equal = sum(1 for v in vals if v == value)
    return (below + 0.5 * equal) / len(vals)


def window_stats(series: Sequence[tuple[str, float]], asof: str, value: float | None = None) -> dict:
    """窗口统计：样本数、极值与日期、均值、中位数、标准差、分位、距极值。"""
    w = window_slice(series, asof, 1.0) if asof else _as_series(series)
    return _stats_of(w, value)


def _stats_of(w: Sequence[tuple[str, float]], value: float | None) -> dict:
    if not w:
        raise ValueError("窗口为空")
    vals = [v for _, v in w]
    n = len(vals)
    cur = float(vals[-1]) if value is None else float(value)
    hi = max(w, key=lambda x: x[1])
    lo = min(w, key=lambda x: x[1])
    mu = sum(vals) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
    srt = sorted(vals)
    med = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    return {
        "n": n,
        "first_date": w[0][0],
        "first": w[0][1],
        "last_date": w[-1][0],
        "last": w[-1][1],
        "current": cur,
        "min": lo[1], "min_date": lo[0],
        "max": hi[1], "max_date": hi[0],
        "mean": mu, "median": med, "std": sd,
        "pctile": percentile_rank(w, cur),
        "change_from_first_pct": w[-1][1] / w[0][1] - 1 if w[0][1] else None,
        "vs_mean_pct": cur / mu - 1 if mu else None,
        "drawdown_from_max_pct": cur / hi[1] - 1 if hi[1] else None,
        "upside_to_max_pct": hi[1] / cur - 1 if cur else None,
        "range_width_pct": hi[1] / lo[1] - 1 if lo[1] else None,
    }


def window_stats_multi(series: Sequence[tuple[str, float]], asof: str, value: float | None = None,
                       windows: Sequence[float] = (1, 3)) -> dict:
    s = _as_series(series)
    out = {}
    for y in windows:
        w = window_slice(s, asof, y)
        out[f"{y}y"] = _stats_of(w, value)
    return out


def quantiles(window: Sequence[tuple[str, float]], qs=(0.1, 0.25, 0.5, 0.75, 0.9)) -> dict:
    vals = sorted(v for _, v in window)
    if not vals:
        raise ValueError("窗口为空")
    res = {}
    for q in qs:
        if len(vals) == 1:
            res[q] = vals[0]
            continue
        pos = (len(vals) - 1) * q
        lo = math.floor(pos)
        hi = math.ceil(pos)
        frac = pos - lo
        res[q] = vals[lo] * (1 - frac) + vals[hi] * frac
    return res


def realized_vol(window: Sequence[tuple[str, float]], ppy: int = 252) -> dict:
    """已实现波动率——只用来描述"过去波动有多大"，不是对未来波动的预测。"""
    vals = [v for _, v in sorted(window)]
    if len(vals) < 3:
        return {"daily_std_pct": None, "annualized_pct": None}
    rets = [math.log(vals[i] / vals[i - 1]) for i in range(1, len(vals))]
    mu = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / (len(rets) - 1))
    return {"daily_std_pct": sd, "annualized_pct": sd * math.sqrt(ppy)}


def implied_move(annualized_vol: float, days: int) -> float:
    """把"过去年化波动率"折算成 N 个交易日的典型波动幅度（仅作情景量级参考，非预测）。

    days 为交易天数；自然日需先按 ×5/7 折算。
    """
    return float(annualized_vol) * math.sqrt(max(days, 1) / 252.0)


def natural_to_business_days(calendar_days: int) -> int:
    return max(1, int(round(calendar_days * 5 / 7)))


# ---------------------------------------------------------------------------
# 6. 分批结算
# ---------------------------------------------------------------------------

def split_batches(batches: Sequence[dict], base_rate_lookup=None) -> dict:
    """分批结算敏感性。

    batches: [{"label": "定金", "amount_fx": 30000, "days": 0, "rate": 7.0}, ...]
      - rate 为该批次的假设汇率（可为各批不同）
      - 若不给 rate，必须给 base_rate_lookup 或者用 base_rate 统一
    """
    rows = []
    total_amt = 0.0
    total_cny = 0.0
    for i, b in enumerate(batches):
        amt = float(b["amount_fx"])
        r = b.get("rate")
        if r is None:
            r = base_rate_lookup(b) if base_rate_lookup else None
        if r is None:
            raise ValueError(f"批次 {b.get('label', i)} 缺少汇率")
        cny = amt * float(r)
        spent = float(b.get("days", 0))
        rows.append({
            "label": b.get("label", f"批次{i + 1}"),
            "amount_fx": amt,
            "days": spent,
            "rate": float(r),
            "cny": cny,
            "share": None,
        })
        total_amt += amt
        total_cny += cny
    for row in rows:
        row["share"] = (row["amount_fx"] / total_amt) if total_amt else None
    weighted = (total_cny / total_amt) if total_amt else None
    return {"rows": rows, "total_amount_fx": total_amt, "total_cny": total_cny,
            "weighted_rate": weighted}


def split_shift_rates(batches: Sequence[dict], total_shift: float) -> list[dict]:
    """整体汇率变动 total_shift 时，各批次同向同步变动（不含分批结构效应）。"""
    out = []
    for b in batches:
        r = b.get("rate")
        if r is None:
            raise ValueError("分批需先给定各批次基准汇率")
        out.append({**b, "rate": float(r) * (1 + float(total_shift))})
    return out


def staggered_padding(batches: Sequence[dict], total_shift: float) -> dict:
    """分批结构 vs 一次性结算（都在基准汇率下）的"时间错配"效应。

    做法：把所有批次按同一整体变动 total_shift 平移，比较加权汇率与
    全部按首日（最早一档）汇率结算的差额——衡量"分批"本身带来的暴露差异。
    """
    base = split_batches(batches)
    sc = split_batches(split_shift_rates(batches, total_shift))
    earliest = min(batches, key=lambda b: b.get("days", 0))
    one_shot_rate = float(earliest["rate"]) * (1 + float(total_shift))
    one_shot_cny = base["total_amount_fx"] * one_shot_rate
    return {
        "shift": total_shift,
        "staggered_cny": sc["total_cny"],
        "one_shot_cny": one_shot_cny,
        "staggering_effect_cny": sc["total_cny"] - one_shot_cny,
        "base_cny": base["total_cny"],
        "delta_vs_base_cny": sc["total_cny"] - base["total_cny"],
    }


# ---------------------------------------------------------------------------
# 7. 便捷入口：把一笔订单的全部指标一次算全
# ---------------------------------------------------------------------------

@dataclass
class OrderCase:
    amount_fx: float
    currency: str
    direction: str
    base_rate: float
    contract_rate: float | None = None
    cny_cost: float | None = None
    target_margin_pct: float | None = None
    target_margin_cny: float | None = None
    toll_rate: float = 0.0
    resale_cny: float | None = None     # 进口时：进口后人民币销售收入
    batches: list = field(default_factory=list)

    def __post_init__(self):
        _check_direction(self.direction)
        _check_rate(self.base_rate)
        if self.amount_fx <= 0:
            raise ValueError("amount_fx 必须 > 0")

    def summary(self, shifts=(-0.05, -0.03, -0.01, 0.0, 0.01, 0.03, 0.05)) -> dict:
        base = business_pnl(self.amount_fx, self.base_rate, self.direction, self.cny_cost, self.toll_rate)
        sens = sensitivity(self.amount_fx, self.base_rate, shifts, self.direction, self.cny_cost, self.toll_rate)
        out = {
            "direction": self.direction,
            "amount_fx": self.amount_fx,
            "base_rate": self.base_rate,
            "base": base,
            "sensitivity": sens,
            "one_pct_cny": one_percent_value(self.amount_fx, self.base_rate, self.toll_rate),
        }
        if self.direction == DIRECTION_EXPORT and self.cny_cost is not None:
            be0 = breakeven_rate_export(self.cny_cost, self.amount_fx, self.toll_rate)
            out["breakeven_zero"] = breakeven_distance(self.base_rate, be0, self.direction)
            if self.target_margin_pct is not None:
                rb = rate_needed_for_margin(self.amount_fx, self.cny_cost, self.target_margin_pct, self.toll_rate)
                out["breakeven_target_pct"] = breakeven_distance(self.base_rate, rb, self.direction)
                out["breakeven_target_pct"]["target"] = self.target_margin_pct
            if self.target_margin_cny is not None:
                rb2 = rate_needed_for_margin(self.amount_fx, self.cny_cost, self.target_margin_cny,
                                             self.toll_rate, as_amount=True)
                out["breakeven_target_cny"] = breakeven_distance(self.base_rate, rb2, self.direction)
                out["breakeven_target_cny"]["target"] = self.target_margin_cny
        if self.direction == DIRECTION_IMPORT and self.resale_cny is not None:
            be1 = breakeven_rate_import(self.amount_fx, self.cny_cost or 0.0, self.resale_cny, self.toll_rate)
            out["breakeven_zero"] = breakeven_distance(self.base_rate, be1, self.direction)
        if self.batches:
            out["batch"] = split_batches(self.batches)
        return out


# ---------------------------------------------------------------------------
# 8. 自检（python calculations.py 直接跑）
# ---------------------------------------------------------------------------

def _t(cond, msg):
    if not cond:
        raise AssertionError(msg)


if __name__ == "__main__":
    # 出口：10 万美元 @ 7.0 中间价，成本 62 万元，毛利率 10%
    c = OrderCase(amount_fx=100000, currency="USD", direction="export", base_rate=7.0, cny_cost=600000)
    s = c.summary()
    print("出口 基准净收入", round(s["base"]["net_cny"], 2))
    _t(abs(s["base"]["net_cny"] - 700000) < 1e-6, "出口净收入")
    _t(abs(s["one_pct_cny"] - 7000) < 1e-6, "1% 敞口")
    be = breakeven_rate_export(600000, 100000)
    _t(abs(be - 6.0) < 1e-9, f"平衡汇率 {be}")
    r10 = rate_needed_for_margin(100000, 600000, 0.10)
    _t(abs(r10 - 6 / 0.9) < 1e-9, f"目标毛利率汇率 {r10}")
    # 银行费用 0.2%
    be_t = breakeven_rate_export(600000, 100000, 0.002)
    _t(abs(be_t - 600000 / 99800) < 1e-9, "含费用平衡汇率")
    # 进口：10 万美元 @ 7.0，再售 750000 元
    im = import_margin(100000, 7.0, 5000, 750000)
    _t(abs(im["total_cost_cny"] - 705000) < 1e-6, "进口总成本")
    be_i = breakeven_rate_import(100000, 5000, 750000)
    _t(abs(be_i - 7.45) < 1e-9, f"进口平衡汇率 {be_i}")
    # 分位
    ser = [("2024-01-02", 7.0), ("2024-01-03", 7.2), ("2024-01-04", 6.8), ("2024-01-05", 6.9)]
    _t(abs(percentile_rank(ser, 6.8) - 0.125) < 1e-12, "分位")
    # 窗口
    st = window_stats([("2024-01-02", 7.0), ("2024-02-02", 7.1), ("2024-03-02", 7.2)], "2024-03-02", 7.2)
    _t(abs(st["max"] - 7.2) < 1e-12 and st["n"] == 3, f"窗口 {st}")
    print("calculations.py 自检通过")
