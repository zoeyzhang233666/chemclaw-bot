# -*- coding: utf-8 -*-
"""
analog_lib.py — 历史相似阶段检索引擎（核心算法，跨品种通用）
================================================================
本模块只做三件事，全部与「时间」严格绑定：

1. 状态标准化（无未来函数）
   任一历史日 t 的标准化参数，只能用 t 当日（含）之前已经可得的数据估计：
     - rolling_z     : 均值/标准差取 [t - lookback, t]，且只用已发布数据
     - expanding_z   : 均值/标准差取样本起点至 t
     - rank          : 分位数取 [t - lookback, t]
     - pctile_rank   : 分位数取样本起点至 t
     - diff_std      : 一阶差分后 rolling_z
   组件形态 form:
     - level  : 直接用指标值
     - change : 用 N 期变化（此处由上游已算成变化率/差值，form=change 仅作标记）

2. 相似度
   mae / rmse / cosine / mahalanobis 四种，均按指标权重 w_i 加权。
   返回相似度 ∈ [0,1]（1 = 完全一致）与距离。

3. 去重（non-maximum suppression）
   按相似度从高到低取，若候选窗口与已选窗口的「观察日」相距 < min_gap，
   视为同一段行情，剔除；同时输出「行情轮次」标记与窗口重叠度。

设计原则
--------
* 输入矩阵必须是「已按信息可得性对齐」的：即 t 行的指标值在 t 当日（或之前）可观测。
  周度指标的下游使用方须先把 asof 对齐到「发布日之后的第一个观测日」。
* 不插值、不外推、不填补：缺失指标在该候选处记为 NaN，并按「有效权重」重新归一，
  有效权重不足 min_effective_weight 的候选直接剔除。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# 1. 无未来函数标准化
# --------------------------------------------------------------------------- #
def _rolling_stats(s: pd.Series, lookback: int, min_obs: int):
    """只用 [t-lookback, t] 的滚动均值/标准差（左闭右闭，含当日）。"""
    mean = s.rolling(lookback, min_periods=min_obs).mean()
    std = s.rolling(lookback, min_periods=min_obs).std(ddof=1)
    return mean, std


def standardize(s: pd.Series, method: str, lookback: int = 500, min_obs: int = 78,
                clip: float = 3.0) -> pd.Series:
    """
    单一指标的无未来函数标准化。

    参数
    ----
    s        : 按时间升序、索引为交易日的原始序列（缺失用 NaN，不插值）
    method   : rolling_z | expanding_z | rank | pctile_rank | diff_std | none
    lookback : 滚动窗口（交易日数），rolling_z/rank 使用
    min_obs  : 窗口内最少观测数，不足则输出 NaN（不硬算）
    clip     : 截尾，防止单个极端值主导距离
    """
    s = s.astype(float)
    if method in ("none", None):
        return s

    if method == "rolling_z":
        mean, std = _rolling_stats(s, lookback, min_obs)
        z = (s - mean) / std.replace(0, np.nan)
    elif method == "expanding_z":
        mean = s.expanding(min_periods=min_obs).mean()
        std = s.expanding(min_periods=min_obs).std(ddof=1)
        z = (s - mean) / std.replace(0, np.nan)
    elif method == "rank":
        z = s.rolling(lookback, min_periods=min_obs).apply(
            lambda a: (a < a[-1]).sum() / max(len(a) - 1, 1), raw=True)
        z = (z - 0.5) * 2  # 映射到 [-1, 1]
        return z  # 分位本身已在 [0,1]，不再 z 化
    elif method == "pctile_rank":
        z = s.expanding(min_periods=min_obs).apply(
            lambda a: (a < a[-1]).sum() / max(len(a) - 1, 1), raw=True)
        z = (z - 0.5) * 2
        return z
    elif method == "diff_std":
        d = s.diff()
        mean, std = _rolling_stats(d, lookback, min_obs)
        z = (d - mean) / std.replace(0, np.nan)
    else:
        raise ValueError(f"未知标准化方法: {method}")

    if clip:
        z = z.clip(-clip, clip)
    return z


def build_state_matrix(raw: pd.DataFrame, spec: Dict, asof_col="date") -> pd.DataFrame:
    """
    把原始指标宽表转成状态矩阵（每个交易日一行，每指标一列，已标准化）。

    spec: {"indicators": [{key, std_method, lookback_days?, min_obs?}...],
           "std_defaults": {"lookback": 500, "min_obs": 78, "clip": 3}}
    返回 DataFrame，index=交易日，columns=指标 key；另附 `__raw_*` 原始值列供展示。
    """
    dflt = spec.get("std_defaults", {})
    lb = int(dflt.get("lookback", 500))
    mo = int(dflt.get("min_obs", 78))
    clip = float(dflt.get("clip", 3.0))
    raw = raw.copy()
    if asof_col in raw.columns:
        raw[asof_col] = pd.to_datetime(raw[asof_col])
        raw = raw.set_index(asof_col).sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]

    out = pd.DataFrame(index=raw.index)
    for ind in spec["indicators"]:
        k = ind["key"]
        if k not in raw.columns:
            continue
        out[k] = standardize(raw[k], ind.get("std_method", "rolling_z"),
                             lookback=int(ind.get("lookback_days", lb)),
                             min_obs=int(ind.get("min_obs", mo)), clip=clip)
        out["__raw_" + k] = raw[k]
    return out


# --------------------------------------------------------------------------- #
# 2. 相似度
# --------------------------------------------------------------------------- #
def weighted_distance(z_hist: np.ndarray, z_now: np.ndarray, w: np.ndarray,
                      method: str = "mae", cov_inv: Optional[np.ndarray] = None,
                      scale: float = 3.0):
    """
    计算单条候选与当前状态的距离与相似度。
    缺失（NaN）指标：两端都有效才计入，权重按有效部分重新归一。
    返回 (distance, similarity, efective_weight)
    """
    mask = ~(np.isnan(z_hist) | np.isnan(z_now)) & (w > 0)
    we = float(w[mask].sum())
    if we <= 0:
        return np.nan, np.nan, 0.0
    ww = w[mask] / we
    a, b = z_hist[mask], z_now[mask]

    if method in ("mae", "rmse"):
        diff = a - b
        if method == "mae":
            d = float(np.sum(ww * np.abs(diff)))
            sim = 1.0 - d / scale
        else:
            d = float(math.sqrt(np.sum(ww * diff ** 2)))
            sim = 1.0 - d / scale
        return d, float(np.clip(sim, 0.0, 1.0)), we

    if method == "cosine":
        num = float(np.sum(ww * a * b))
        den = math.sqrt(float(np.sum(ww * a * a))) * math.sqrt(float(np.sum(ww * b * b)))
        sim = num / den if den > 0 else 0.0
        sim = (sim + 1) / 2  # 映射 [-1,1] -> [0,1]
        return float(1 - sim), float(sim), we

    if method == "mahalanobis":
        if cov_inv is None:
            raise ValueError("mahalanobis 需要 cov_inv")
        WW = np.diag(w[mask])
        diff = a - b
        S_inv = cov_inv[np.ix_(mask, mask)]
        d2 = float(diff @ WW @ S_inv @ WW @ diff)
        sim = math.exp(-0.5 * d2)
        return float(math.sqrt(max(d2, 0))), float(sim), we

    raise ValueError(f"未知相似度方法: {method}")


def _shrunk_cov(Z: pd.DataFrame, prior_var: float = 1.0, shrink: float = 0.5) -> np.ndarray:
    """收缩协方差（Ledoit-Wolf 简化版），保证可逆。"""
    Xi = Z.dropna().values
    if Xi.shape[0] < Xi.shape[1] * 3:
        return np.eye(Z.shape[1]) * prior_var
    S = np.cov(Xi, rowvar=False)
    T = np.diag(np.diag(S))
    return (1 - shrink) * S + shrink * T + np.eye(S.shape[0]) * 1e-6


# --------------------------------------------------------------------------- #
# 3. 检索 + 去重
# --------------------------------------------------------------------------- #
@dataclass
class SearchParams:
    asof: str                       # 当前观察日 YYYY-MM-DD
    history_start: str              # 样本起点（含）
    window_weeks: int = 4           # 状态向量由多少周构成（路径形态）
    top_n: int = 5
    min_gap_weeks: int = 8          # 两个命中窗口观察日的最小间隔
    method: str = "mae"
    weights: Dict[str, float] = field(default_factory=dict)
    min_effective_weight: float = 0.5   # 有效权重占比下限
    forward_months: Sequence[int] = (1, 3)
    # —— 以下用于控制「当前状态向量里的指标必须在该历史时点真实存在」——
    min_hist_z_cover: float = 0.9   # 标准化值覆盖率下限（历史窗口里有 z 值的权重占比）
    hist_z_required: bool = True    # False 则退回旧的「有效权重重新归一」口径
    min_sign_match: float = 0.75    # 同向指标占比下限
    lag_at_least_days: int = 7      # 历史观察日至当前观察日的最小间隔（至少提前 1 周，避免同一轮行情自比）


def _path_window(z_row: pd.Series, dates: pd.DatetimeIndex, i: int,
                 window_days: int) -> Optional[np.ndarray]:
    """取以 i 结尾、长度为 window_days 的路径（缺失保持 NaN，不插值）。"""
    if i - window_days + 1 < 0:
        return None
    return z_row.iloc[i - window_days + 1:i + 1].values


def _regime_cluster(sel: pd.DataFrame, gap_days: int) -> list:
    """把命中窗口按时间聚类成「行情轮次」：相邻间隔 < 3×min_gap 视为同一轮。"""
    order = sel.sort_values("date").reset_index()
    ids, cur = {}, 1
    last = None
    for d in order["date"]:
        if last is not None and (d - last).days >= gap_days * 3:
            cur += 1
        ids[order.loc[order["date"] == d, "index"].iloc[0]] = cur
        last = d
    return [ids[i] for i in sel.index]


def search_analogs(state: pd.DataFrame, raw: pd.DataFrame, params: SearchParams,
                   forward_frame: Optional[pd.DataFrame] = None) -> dict:
    """
    主检索函数。

    state  : build_state_matrix 的输出（标准化后），index=交易日
    raw    : 原始指标宽表（与 state 同 index），列名为指标 key（不含 __raw_ 前缀）
    params : SearchParams

    forward_frame: 用于计算「后续表现」的原始指标宽表（可含更长历史），
                   index=交易日，列名为原始指标 key。

    返回 dict：now / candidates / selected / diagnostics
    """
    idx = state.index
    asof = pd.Timestamp(params.asof)
    if asof not in idx:
        prior = idx[idx <= asof]
        if len(prior) == 0:
            raise ValueError(f"观察日 {params.asof} 无数据")
        asof = prior[-1]
    i_now = idx.get_loc(asof)

    keys = [k for k in params.weights if k in state.columns and params.weights[k] > 0]
    if not keys:
        raise ValueError("没有有效指标权重")
    w = np.array([float(params.weights[k]) for k in keys], dtype=float)

    # 当前状态向量：要求「所有纳入指标」在观察日都有标准化值。
    # 若某指标在观察日尚无值（例如开工率覆盖不足），它不进入状态向量，
    # 同时其权重也不进入分母 —— 保证「当前状态」本身是完整可解释的。
    z_now_row = state.loc[asof, keys].astype(float)
    avail_now = [k for k in keys if not np.isnan(z_now_row[k])]
    dropped_now = [k for k in keys if k not in avail_now]
    if not avail_now:
        raise ValueError("观察日没有任何可用指标")
    keys = avail_now
    w = np.array([float(params.weights[k]) for k in keys], dtype=float)
    w_total = float(w.sum())
    z_now_vec = z_now_row[keys].values

    # 限制样本起点：只允许 history_start 之后
    hs = pd.Timestamp(params.history_start)
    # 候选必须能完整取出窗口 + 留有后续观察期
    window_days = int(params.window_weeks * 5)
    start_pos = int(idx.searchsorted(hs))

    # 协方差（仅 mahalanobis）
    cov_inv = None
    if params.method == "mahalanobis":
        Zs = state.loc[idx[start_pos:i_now][keys]]
        S = _shrunk_cov(Zs)
        cov_inv = np.linalg.pinv(S)

    cands: List[dict] = []
    for i in range(start_pos, i_now):
        t = idx[i]
        # 候选窗口必须完全落在历史样本内
        if i - window_days + 1 < start_pos:
            continue
        # 与当前观察日至少相隔 lag_at_least_days 天，避免同一轮行情自己和自己比
        if (asof - t).days < params.lag_at_least_days:
            continue
        z_hist_row = state.loc[t, keys].astype(float)
        # —— 历史时点缺指标的处理 ——
        z_avail = z_hist_row[~z_hist_row.isna()]
        hist_cover = float(w[~z_hist_row.isna().values].sum() / w_total)
        sign_w = sign_ok = 0.0
        for kk, k in enumerate(keys):
            zv = z_hist_row[k]
            if pd.isna(zv):
                continue
            sign_w += w[kk]
            if (zv >= 0) == (z_now_vec[kk] >= 0):
                sign_ok += w[kk]
        sign_match = (sign_ok / sign_w) if sign_w > 0 else float("nan")

        if params.hist_z_required:
            # 严格要求：历史时点的标准化值覆盖率足够，否则该时点不存在「完整状态」
            if hist_cover < params.min_hist_z_cover:
                continue
            d, sim, we = weighted_distance(z_hist_row.values, z_now_vec, w, params.method,
                                           cov_inv=cov_inv)
            sim = float(np.clip(sim - (1 - hist_cover) * 1.0, 0, 1))  # 覆盖不足的折算惩罚
        else:
            d, sim, we = weighted_distance(z_hist_row.values, z_now_vec, w, params.method,
                                           cov_inv=cov_inv)
        if np.isnan(sim):
            continue
        if not np.isnan(sign_match) and sign_match < params.min_sign_match:
            continue

        # 路径相似度（同一窗口内的形态），仅当窗口 > 1 周
        path_sim = np.nan
        path_cover = 0.0
        if window_days > 1:
            acc, nw = [], 0.0
            for k_i, k in enumerate(keys):
                if params.weights[k] <= 0:
                    continue
                ph = _path_window(state[k], idx, i, window_days)
                pn = _path_window(state[k], idx, i_now, window_days)
                if ph is None or pn is None:
                    continue
                ok = ~(np.isnan(ph) | np.isnan(pn))
                if ok.sum() < window_days * 0.8:
                    continue
                acc.append(params.weights[k] * float(np.nanmean(np.abs(ph[ok] - pn[ok]))))
                nw += params.weights[k]
            if nw > 0:
                path_cover = nw / w_total
                path_sim = float(np.clip(1 - (sum(acc) / nw) / 3.0, 0, 1))
        cands.append({"date": t, "i": i, "distance": d, "similarity": sim,
                      "path_similarity": path_sim, "eff_weight": we,
                      "eff_weight_frac": we / w_total,
                      "hist_z_cover": hist_cover, "sign_match": sign_match,
                      "path_cover": path_cover})

    cdf = pd.DataFrame(cands)
    if cdf.empty:
        raise ValueError("没有可用候选窗口")
    # 有效权重不足 → 剔除（不拿半个状态去比；hist_z_required=True 时已在上游过滤）
    cdf = cdf[cdf["eff_weight_frac"] >= params.min_effective_weight].copy()
    cdf = cdf.sort_values(["similarity"], ascending=False).reset_index(drop=True)

    # 合并相似度（状态 + 路径），用于排序与展示
    def _score(r):
        if pd.isna(r["path_similarity"]):
            return r["similarity"]
        return 0.7 * r["similarity"] + 0.3 * r["path_similarity"]
    cdf["score"] = cdf.apply(_score, axis=1)
    cdf = cdf.sort_values("score", ascending=False).reset_index(drop=True)

    # ---- 去重：非极大值抑制 ----
    gap_days = int(params.min_gap_weeks * 7)
    selected: List[int] = []
    for r in cdf.itertuples():
        if len(selected) >= params.top_n:
            break
        if all(abs((r.date - cdf.loc[j, "date"]).days) >= gap_days for j in selected):
            selected.append(r.Index)

    sel = cdf.loc[selected].copy().reset_index(drop=True)
    sel["rank"] = np.arange(1, len(sel) + 1)

    # ---- 行情轮次标记 ----
    sel["regime_id"] = _regime_cluster(sel, gap_days)

    # 未去重前的前 N 名（用于说明「去重前是什么样」）
    raw_top = cdf.head(params.top_n)[["date", "similarity", "score", "eff_weight_frac"]].copy()

    now_vec = pd.Series(z_now_vec, index=keys)
    raw_now = raw.loc[asof] if asof in raw.index else pd.Series(dtype=float)
    return {
        "asof": asof,
        "keys": keys,
        "weights": dict(zip(keys, w.tolist())),
        "dropped_for_now": dropped_now,
        "selected": sel,
        "candidates": cdf,
        "raw_top_before_dedup": raw_top,
        "now_std": now_vec,
        "now_raw": raw_now,
        "window_days": window_days,
        "n_candidates": len(cdf),
        "params": params,
    }


# --------------------------------------------------------------------------- #
# 4. 后续演化
# --------------------------------------------------------------------------- #
def forward_performance(idx: pd.DatetimeIndex, raw: pd.DataFrame, fwd_start: pd.Timestamp,
                        columns: Sequence[str], months: Sequence[int], window_days: int) -> dict:
    """
    从 fwd_start（观察日）之后的月末交易日，取各指标相对观察日的演化。
    价格类取「变化%」，水平类取「水平与变化」。
    """
    def shift_month(ts: pd.Timestamp, m: int) -> pd.Timestamp:
        y, mo = ts.year + (ts.month - 1 + m) // 12, (ts.month - 1 + m) % 12 + 1
        import calendar
        d = min(ts.day, calendar.monthrange(y, mo)[1])
        return pd.Timestamp(y, mo, d)

    out = {}
    pos0 = idx.searchsorted(fwd_start)
    if pos0 >= len(idx) or idx[pos0] != fwd_start:
        prior = idx[idx <= fwd_start]
        if len(prior) == 0:
            return {}
        pos0 = idx.get_loc(prior[-1])
    base = raw.iloc[pos0]
    # 起点区间均值（与状态窗口同口径），用于描述「起点水平」
    lo = max(0, pos0 - window_days + 1)
    base_win = raw.iloc[lo:pos0 + 1].mean()

    for m in months:
        tgt = shift_month(idx[pos0], m)
        # 只接受「恰好到达目标月」的观测：若样本在目标日之前就结束，
        # 用最后一个可用点会静默缩短后续期，等于把 1 个月当成 3 个月报，必须留空。
        tol_days = 15   # 允许目标日落在周末/节假日而顺延的天数
        cand = idx[(idx <= tgt) & (idx >= tgt - pd.Timedelta(days=tol_days))]
        if len(cand) == 0:
            out[f"{m}m"] = None
            continue
        pos1 = idx.get_loc(cand[-1])
        if pos1 <= pos0:
            out[f"{m}m"] = None
            continue
        row = raw.iloc[pos1]
        res = {"start": idx[pos0].date().isoformat(), "end": idx[pos1].date().isoformat(),
               "actual_months": round((idx[pos1] - idx[pos0]).days / 30.44, 2)}
        for c in columns:
            if c not in raw.columns:
                continue
            v0, v1 = base_win.get(c), row.get(c)
            if pd.isna(v0) or pd.isna(v1) or v0 == 0:
                res[c] = None
                res[c + "_chg"] = None
                continue
            res[c] = float(v1)
            res[c + "_chg"] = float(v1 - v0)
            res[c + "_pct"] = float((v1 / v0 - 1) * 100)
        out[f"{m}m"] = res
    return out
