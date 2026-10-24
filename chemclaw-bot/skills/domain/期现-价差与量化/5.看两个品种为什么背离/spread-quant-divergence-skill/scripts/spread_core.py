# -*- coding: utf-8 -*-
"""
spread_core.py — 双品种背离研究统计内核
=======================================
纯 numpy / pandas 实现，无外部网络依赖。被 HTML / Excel 构建脚本共用。

核心约定
--------
* 输入：两张 DataFrame，列 = [date, price]（date 为交易日），按日期对齐后取交集。
* 标准化：一律以"区间首个共同交易日 = 100"的指数化价格；同时保留"相对均值偏离"。
* 相关：区分"价格水平相关"（趋势伪相关风险）与"收益率相关"（对数收益）。
* 背离：基于标准化价差（或价格比）相对其滚动均值的 z 分数，配合双阈值 + 最短持续期确认。
* 一切统计结论仅代表统计特征，不构成因果推断或交易建议。

作者备注：本文件是 Skill 的"统计内核"，供 templates/ 与 examples/ 复用。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# 0. 数据准备
# ----------------------------------------------------------------------
def prepare_pairs(df_a: pd.DataFrame, df_b: pd.DataFrame,
                  a_name: str = "A", b_name: str = "B") -> pd.DataFrame:
    """按交易日对齐两条价格序列，返回长表 [date, a, b]。

    规则：
      * 只保留两侧都有价格的交易日（交集），不做前向填充 —— 填充会造成"假平坦"，
        低估波动、高估相关性。
      * 日期升序；重复日期（同一交易日多次发布）保留最后一条。
    """
    a = df_a.copy()
    b = df_b.copy()
    a = a.rename(columns={a.columns[0]: "date", a.columns[1]: a_name})
    b = b.rename(columns={b.columns[0]: "date", b.columns[1]: b_name})
    for d in (a, b):
        d["date"] = pd.to_datetime(d["date"])
        d.drop_duplicates("date", keep="last", inplace=True)
    m = a.merge(b, on="date", how="inner").sort_values("date").reset_index(drop=True)
    m = m[(m[a_name] > 0) & (m[b_name] > 0)]
    return m.reset_index(drop=True)


# ----------------------------------------------------------------------
# 1. 标准化价格与相对指标
# ----------------------------------------------------------------------
def standardize(px: pd.Series, base: float | None = None) -> pd.Series:
    """指数化：首值（或指定 base）=100。"""
    b = float(px.iloc[0]) if base is None else float(base)
    return px / b * 100.0


def spread_series(a: pd.Series, b: pd.Series) -> pd.Series:
    """价差 = A - B（元/吨）。上下游/替代品种用绝对价差最直观。"""
    return a - b


def ratio_series(a: pd.Series, b: pd.Series) -> pd.Series:
    """比价 = A / B。对价格水平量级差异大或长期趋势强的组合更稳健。"""
    return a / b


def log_return(px: pd.Series) -> pd.Series:
    """对数收益 ln(P_t/P_{t-1})，首行为 NaN。"""
    return np.log(px / px.shift(1))


def pct_change_n(px: pd.Series, n: int) -> pd.Series:
    """n 期涨跌幅（百分比）。"""
    return (px / px.shift(n) - 1.0) * 100.0


# ----------------------------------------------------------------------
# 2. 相关性：区分水平相关与收益相关
# ----------------------------------------------------------------------
def _corr(x: pd.Series, y: pd.Series, method: str = "pearson") -> float:
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 3:
        return float("nan")
    return float(d.iloc[:, 0].corr(d.iloc[:, 1], method=method))


def corr_bundle(a: pd.Series, b: pd.Series,
                a_ret: pd.Series | None = None,
                b_ret: pd.Series | None = None) -> dict:
    """同时给出四组相关，避免"水平伪相关"被当成结论。

    * level_pearson / level_spearman：价格水平相关 —— 高值常由共同趋势造成，仅作参照。
    * ret_pearson / ret_spearman：收益率相关 —— 真正的同步性证据。
    * level_detrended：用"价格 / 滚动中枢"剔除趋势后的相关（更贴近背离判断）。
    """
    a_ret = log_return(a) if a_ret is None else a_ret
    b_ret = log_return(b) if b_ret is None else b_ret
    return {
        "level_pearson": _corr(a, b, "pearson"),
        "level_spearman": _corr(a, b, "spearman"),
        "ret_pearson": _corr(a_ret, b_ret, "pearson"),
        "ret_spearman": _corr(a_ret, b_ret, "spearman"),
        "n": int(pd.concat([a, b], axis=1).dropna().shape[0]),
    }


def rolling_corr(a: pd.Series, b: pd.Series, window: int,
                 use_returns: bool = True) -> pd.Series:
    """滚动相关。use_returns=True 时用对数收益（推荐），否则用价格水平（仅供对照）。"""
    if use_returns:
        x, y = log_return(a), log_return(b)
    else:
        x, y = a, b
    return x.rolling(window).corr(y)


def corr_significance_band(n: int, level: float = 0.95) -> float:
    """相关系数的近似显著性带 ±z/√(n-3)（Fisher z 近似），用于图上画参考带。"""
    if n <= 4:
        return float("nan")
    z = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}.get(level, 1.96)
    return z / math.sqrt(n - 3)


# ----------------------------------------------------------------------
# 3. 背离识别（明确规则）
# ----------------------------------------------------------------------
@dataclass
class DivergenceRule:
    """背离识别参数（全部可调，报告中必须原样披露）。

    indicator : "spread" = 价差(A-B)；"ratio" = 比价(A/B)
    z_window  : 用于计算滚动中枢的窗口（周度数据建议 26）
    z_entry   : 触发阈值（|z| ≥ 该值视为偏离）
    z_exit    : 解除阈值（|z| < 该值视为回归，用于连续段切分）
    min_periods: 最短持续期（周），短于此的触发视为噪声
    smooth    : 中枢计算的平滑窗口（0 = 用 z_window 本身）
    """
    indicator: str = "spread"
    z_window: int = 26
    z_entry: float = 1.5
    z_exit: float = 0.5
    min_periods: int = 4
    smooth: int = 0


def deviation_z(a: pd.Series, b: pd.Series, rule: DivergenceRule) -> pd.Series:
    """计算相对指标的滚动 z 分数。

    z_t = (I_t - 滚动均值) / 滚动标准差 ；I 为价差或比价。
    使用"滚动"而非全样本，是为了避免用未来信息（全样本均值会引入前视偏差）。
    """
    ind = spread_series(a, b) if rule.indicator == "spread" else ratio_series(a, b)
    w = rule.smooth if rule.smooth > 0 else rule.z_window
    mu = ind.rolling(rule.z_window, min_periods=max(5, rule.z_window // 2)).mean()
    sd = ind.rolling(rule.z_window, min_periods=max(5, rule.z_window // 2)).std()
    z = (ind - mu) / sd.replace(0, np.nan)
    return z


def detect_divergences(a: pd.Series, b: pd.Series, dates: pd.Series,
                       rule: DivergenceRule) -> list[dict]:
    """按双阈值状态机切分背离段。

    规则：
      1) 进入：|z| ≥ z_entry
      2) 退出：|z| < z_exit
      3) 同一段内符号必须一致（价差高于中枢 / 低于中枢 视为两种背离方向）
      4) 段长 < min_periods 的段丢弃（噪声过滤）
    返回每个背离段的起止日期、持续期、峰值 |z|、期间价格涨跌幅。
    """
    z = deviation_z(a, b, rule)
    ind = spread_series(a, b) if rule.indicator == "spread" else ratio_series(a, b)
    segs: list[dict] = []
    cur = None
    for i, (d, zi) in enumerate(zip(dates, z)):
        if pd.isna(zi):
            continue
        sign = 1 if zi >= 0 else -1
        if cur is None:
            if abs(zi) >= rule.z_entry:
                cur = {"start_i": i, "sign": sign, "peak": abs(zi), "peak_i": i}
            continue
        # 已有段：符号反转 或 回落到 exit 以内 → 结束
        if sign != cur["sign"] or abs(zi) < rule.z_exit:
            segs.append((cur, i))
            cur = None
            if abs(zi) >= rule.z_entry:
                cur = {"start_i": i, "sign": sign, "peak": abs(zi), "peak_i": i}
            continue
        if abs(zi) > cur["peak"]:
            cur["peak"] = abs(zi)
            cur["peak_i"] = i
    if cur is not None:
        segs.append((cur, len(dates)))

    out = []
    for s, end_i in segs:
        s_i = s["start_i"]
        length = end_i - s_i
        if length < rule.min_periods:
            continue
        seg = slice(s_i, end_i)
        a_chg = float(a.iloc[end_i - 1] / a.iloc[s_i] - 1) * 100
        b_chg = float(b.iloc[end_i - 1] / b.iloc[s_i] - 1) * 100
        ind_vals = ind.iloc[seg]
        out.append({
            "start": pd.Timestamp(dates.iloc[s_i]).strftime("%Y-%m-%d"),
            "end": pd.Timestamp(dates.iloc[end_i - 1]).strftime("%Y-%m-%d"),
            "peak_date": pd.Timestamp(dates.iloc[s["peak_i"]]).strftime("%Y-%m-%d"),
            "periods": int(length),
            "direction": "A相对B偏高" if s["sign"] > 0 else "A相对B偏低",
            "peak_abs_z": round(float(s["peak"]), 3),
            "indicator_start": round(float(ind_vals.iloc[0]), 2),
            "indicator_end": round(float(ind_vals.iloc[-1]), 2),
            "a_change_pct": round(a_chg, 2),
            "b_change_pct": round(b_chg, 2),
            "divergence_pct_points": round(a_chg - b_chg, 2),
        })
    return out


# ----------------------------------------------------------------------
# 4. 描述统计辅助
# ----------------------------------------------------------------------
def window_stats(a: pd.Series, b: pd.Series) -> dict:
    """区间概览：起止价、区间涨跌、年化波动、最大回撤。"""
    def _md(px: pd.Series) -> float:
        roll = px.cummax()
        return float(((px / roll) - 1).min() * 100)
    return {
        "a_start": round(float(a.iloc[0]), 2), "a_end": round(float(a.iloc[-1]), 2),
        "a_chg_pct": round(float(a.iloc[-1] / a.iloc[0] - 1) * 100, 2),
        "a_vol_ann_pct": round(float(np.log(a / a.shift(1)).std() * math.sqrt(52) * 100), 2),
        "a_mdd_pct": round(_md(a), 2),
        "b_start": round(float(b.iloc[0]), 2), "b_end": round(float(b.iloc[-1]), 2),
        "b_chg_pct": round(float(b.iloc[-1] / b.iloc[0] - 1) * 100, 2),
        "b_vol_ann_pct": round(float(np.log(b / b.shift(1)).std() * math.sqrt(52) * 100), 2),
        "b_mdd_pct": round(_md(b), 2),
    }


def beta_alpha(a: pd.Series, b: pd.Series) -> dict:
    """以 A 为基准的简单 OLS：B_ret = alpha + beta * A_ret（仅统计描述）。"""
    x, y = log_return(a), log_return(b)
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 10:
        return {"beta": float("nan"), "alpha": float("nan"), "r2": float("nan"), "n": len(d)}
    X = np.column_stack([np.ones(len(d)), d.iloc[:, 0].to_numpy()])
    yv = d.iloc[:, 1].to_numpy()
    coef, *_ = np.linalg.lstsq(X, yv, rcond=None)
    pred = X @ coef
    ss_res = float(((yv - pred) ** 2).sum())
    ss_tot = float(((yv - yv.mean()) ** 2).sum())
    return {"alpha": float(coef[0]), "beta": float(coef[1]),
            "r2": 1 - ss_res / ss_tot if ss_tot > 0 else float("nan"), "n": len(d)}


def self_test() -> None:
    """自检：合成"前 60 周同步、后 40 周背离"的数据，应识别出 1 段背离。"""
    rng = np.random.default_rng(7)
    n = 100
    dates = pd.date_range("2023-01-06", periods=n, freq="W-FRI")
    common = np.cumsum(rng.normal(0, 0.01, n))
    a = 8000 * np.exp(common + np.cumsum(rng.normal(0, 0.004, n)))
    b = 8500 * np.exp(common + np.cumsum(rng.normal(0, 0.004, n)))
    b[60:] *= np.linspace(1.0, 0.90, n - 60)      # 后 40 周 B 额外下跌 10%
    ds = pd.Series(dates)
    rule = DivergenceRule(indicator="ratio", z_window=20, z_entry=1.2, z_exit=0.4, min_periods=3)
    segs = detect_divergences(pd.Series(a), pd.Series(b), ds, rule)
    print("[self-test] divergence segments:", len(segs))
    for s in segs:
        print("   ", s["start"], "→", s["end"], s["direction"], "peak|z|=", s["peak_abs_z"])
    cb = corr_bundle(pd.Series(a), pd.Series(b))
    print("[self-test] level r=%.3f  ret r=%.3f" % (cb["level_pearson"], cb["ret_pearson"]))
    assert len(segs) >= 1, "应至少识别出一段背离"


if __name__ == "__main__":
    self_test()
