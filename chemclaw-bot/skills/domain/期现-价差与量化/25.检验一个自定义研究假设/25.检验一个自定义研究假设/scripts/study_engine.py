# -*- coding: utf-8 -*-
"""study_engine.py — 在「已冻结研究设计」上执行完整检验，并登记每一次检验。

输入 : research_design.json（approved 字段 + 参数）+ 一份价格/库存面板 CSV
输出 : results.json（全部检验、稳定性、风险检查）+ samples.csv（逐条原始记录）

关键约束
--------
1. 只读参数：引擎不提供"改参数让结果变好"的开关；敏感性分析必须在设计里预先登记。
2. 全量登记：每一次检验写入 tests[]，包含检验族(primary/sensitivity/robustness/stability/
   placebo/diagnostic)、N、效应量、95%CI、p、BH 校正后 q。禁止挑选汇报。
3. 样本不足规则：n_signal < min_signal 或 n_control < min_n → verdict=INSUFFICIENT_SAMPLE，
   不报告显著性、不计算"看起来有帮助"的修正 p。

用法
  python study_engine.py --design build/research_design.formal.json \
         --inventory data/port_inventory_weekly.csv --price data/100ppi_sf.csv \
         --minute data/futures/MA0_60min.csv --out build/results_real.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hypothesis_stats as S  # noqa: E402


# --------------------------------------------------------------------------- data loading

def read_csv(p):
    if not p or not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def dnum(x):
    return None if x in (None, "", "nan", "NaN") else num(x)


class Market:
    """Daily price frame: close of the near contract (100ppi) + basis + 60-min closes."""

    def __init__(self, price_csv, minute_csv=None):
        px = read_csv(price_csv)
        self.days = []
        self.fut, self.spot, self.basis = {}, {}, {}
        self.near_code = {}
        for r in px:
            d = r.get("date") or r.get("asof")
            if not d or dnum(r.get("near_fut")) is None:
                continue
            self.days.append(d)
            self.fut[d] = dnum(r["near_fut"])
            self.spot[d] = dnum(r.get("spot"))
            self.basis[d] = dnum(r.get("near_basis"))
            code = (r.get("near_code") or "").strip()
            self.near_code[d] = code or None
        self.days.sort()
        self.idx = {d: i for i, d in enumerate(self.days)}
        # 合约换月日：近月合约代码发生变化的那一天（100ppi 的近月列随交割日切换）
        self.roll_days = set()
        prev = None
        for d in self.days:
            c = self.near_code.get(d)
            if c and prev and c != prev:
                self.roll_days.add(d)
            if c:
                prev = c
        self.minute = {}
        for r in read_csv(minute_csv):
            t = r["bar_end"]
            day, hm = t[:10], t[11:16]
            if "14:00" <= hm <= "15:00":
                self.minute[day] = dnum(r["close"])

    def rolls_between(self, d0, d1):
        """T0(不含) → T1(含) 之间是否发生近月合约切换。"""
        i0 = self.idx.get(d0)
        i1 = self.idx.get(d1)
        if i0 is None or i1 is None:
            return False
        return any(self.days[k] in self.roll_days for k in range(i0 + 1, i1 + 1))

    def next_day(self, d):
        i = self.idx.get(d)
        if i is None:
            larger = [x for x in self.days if x > d]
            return larger[0] if larger else None
        return self.days[i + 1] if i + 1 < len(self.days) else None

    def shift(self, d, k):
        i = self.idx.get(d)
        if i is None or i + k >= len(self.days):
            return None
        return self.days[i + k]


# --------------------------------------------------------------------------- panel

def build_panel(inv_rows, market, design):
    """One row per evaluable weekly signal state (only state *transitions* are kept)."""
    inv = sorted([r for r in inv_rows if dnum(r.get("total")) is not None],
                 key=lambda r: r["asof"])
    out, skip = [], {"parse_fail": 0, "gap": 0, "no_price": 0, "dup_state": 0,
                     "incomplete": 0, "roll_in_window": 0}
    prev_state = None
    for i in range(2, len(inv)):
        r0, r1, r2 = inv[i], inv[i - 1], inv[i - 2]
        i0, i1, i2 = dnum(r0["total"]), dnum(r1["total"]), dnum(r2["total"])
        from datetime import date as _d
        f = lambda s: _d.fromisoformat(s)
        g1 = (f(r0["asof"]) - f(r1["asof"])).days
        g2 = (f(r1["asof"]) - f(r2["asof"])).days
        if not (5 <= g1 <= 10 and 5 <= g2 <= 10):
            skip["gap"] += 1
            continue
        d1, d2 = i0 - i1, i1 - i2
        state = "DOWN2" if (d1 < 0 and d2 < 0) else ("UP2" if (d1 > 0 and d2 > 0) else "MIXED")
        # 连续很多周同向很常见（一段去库可以持续 6–8 周）。去重规则由设计文件显式给出：
        #   transition —— 只有状态转变的那一周算事件（降权，避免重复计数）
        #   weekly     —— 每一周都算一个观测（重叠严重，见 diagnostics）
        dedup = design.get("dedup", "transition")
        if dedup == "transition":
            if state == prev_state:
                skip["dup_state"] += 1
                continue
            prev_state = state
        # 入场价：pre15 → 报告日 14:00–15:00 的 60 分钟 bar 收盘（缺 bar 时用该日收盘代理，并计数）；
        #          next  → 发布日之后首个交易日收盘。代理比例在结果里如实披露。
        if design.get("entry") == "pre15":
            if r0["asof"] in market.minute:
                T0, entry_kind = r0["asof"], "pre15_60min_bar"
            elif r0["asof"] in market.idx:
                T0, entry_kind = r0["asof"], "same_day_close_proxy"
                skip["pre15_bar_missing"] = skip.get("pre15_bar_missing", 0) + 1
            else:
                T0, entry_kind = market.next_day(r0["asof"]), "next_day_fallback"
        else:
            T0 = market.next_day(r0["asof"])
            entry_kind = "next_day_close"
        if T0 is None:
            skip["no_price"] += 1
            continue
        p0 = market.fut.get(T0)
        b0 = market.basis.get(T0)
        if p0 is None:
            skip["no_price"] += 1
            continue
        row = {"asof": r0["asof"], "pub_ts": r0.get("pub_ts", ""), "T0": T0,
               "entry_kind": entry_kind,
               "total": i0, "d1": round(d1, 4), "d2": round(d2, 4), "state": state,
               "signal": 1 if state == "DOWN2" else 0,
               "dec14": 1 if (d1 <= -1 and d2 <= -1) else 0,
               "gap1": g1, "gap2": g2, "P0": p0, "basis0": b0,
               "level_band": None}
        ok = True
        roll_flag = None
        for k in design["horizons"]:
            Tk = market.shift(T0, k)
            if Tk is None:
                ok = False
                break
            pk = market.fut.get(Tk)
            bk = market.basis.get(Tk)
            row[f"T_k_{k}"] = Tk
            row[f"dP_{k}"] = round(pk - p0, 4) if pk is not None else None
            row[f"dB_{k}"] = round(bk - b0, 4) if (bk is not None and b0 is not None) else None
            row[f"r_{k}"] = round((pk - p0) / p0 * 100, 4) if pk else None
            row[f"roll_{k}"] = int(market.rolls_between(T0, Tk))
            if k == design.get("horizon_main"):
                roll_flag = row[f"roll_{k}"]
        if not ok:
            skip["incomplete"] += 1
            continue
        # 主窗口跨越近月合约换月 → 期货价变化含合约跳变，不能与基本面变化混为一谈
        if roll_flag:
            skip["roll_in_window"] += 1
            if design.get("exclude_roll", True):
                continue
        row["roll_main"] = roll_flag
        # 库存水平分位（只用过去 52 周，避免全样本信息泄露）
        out.append(row)

    hist = [dnum(r["total"]) for r in inv]
    for row in out:
        i = [r["asof"] for r in inv].index(row["asof"])
        win = hist[max(0, i - 52):i]
        if len(win) >= 10:
            below = sum(1 for v in win if v < row["total"])
            pct = below / len(win)
            row["level_pct"] = round(pct, 3)
            row["level_band"] = "LOW" if pct < 0.3 else ("HIGH" if pct > 0.7 else "MID")
        else:
            row["level_pct"] = None
            row["level_band"] = "NA"
        row["iso_week"] = int(datetime.fromisoformat(row["asof"]).isocalendar()[1])
    return out, skip


# --------------------------------------------------------------------------- tests

class Registry:
    def __init__(self, status):
        self.tests = []
        self.status = status

    def add(self, tid, family, label, est=None, ci=None, p=None, n=None, **extra):
        self.tests.append({"id": tid, "family": family, "label": label, "estimate": est,
                           "ci95": list(ci) if ci else None, "p": p, "n": n,
                           "extra": extra, "data_status": self.status})

    def finalize(self):
        idx = [i for i, t in enumerate(self.tests) if t["p"] is not None]
        q = S.bh_adjust([self.tests[i]["p"] for i in idx]) if idx else []
        for k, i in enumerate(idx):
            self.tests[i]["q_bh"] = q[k]
        for t in self.tests:
            t.setdefault("q_bh", None)
        return self.tests


def proportion_block(tag, ys, ys_ctl, reg, fam="primary", label=""):
    k1, n1 = sum(1 for y in ys if y > 0), len(ys)
    k2, n2 = sum(1 for y in ys_ctl if y > 0), len(ys_ctl)
    if n1 < 2 or n2 < 2:
        reg.add(tag + "_dir", fam, label + " 方向一致率（样本不足）", None, None, None, n1 + n2)
        return None
    lo, hi = S.wilson_ci(k1, n1)
    z = S.two_prop_z(k1, n1, k2, n2)
    reg.add(tag + "_dir", fam, label + f" 方向一致率 P(Δ>0 | 信号) vs 对照",
            k1 / n1 - k2 / n2 if n2 else None, (lo, hi), z["p"], n1,
            signal_rate=round(k1 / n1, 4), control_rate=round(k2 / n2, 4), n_control=n2)
    return {"sig_rate": k1 / n1, "ctl_rate": k2 / n2, "p": z["p"], "ci": (lo, hi)}


def mean_block(tag, xs, xc, reg, fam="primary", label=""):
    if len(xs) < 3 or len(xc) < 3:
        reg.add(tag + "_mean", fam, label + " 均值差（样本不足）", None, None, None, len(xs))
        return None
    w = S.welch_t(xs, xc)
    mw = S.mannwhitney_u(xs, xc)
    reg.add(tag + "_mean", fam, label + " 均值差（信号−对照）", w["diff"], w["ci95"],
            w["p_t_approx"], len(xs), p_normal_approx=w["p"], control_mean=S.mean(xc),
            control_n=len(xc), se=w["se"], t=w["t"], df=round(w["df"], 2))
    reg.add(tag + "_mw", fam, label + " Mann-Whitney U（Cliff's δ）", S.cliffs_delta(xs, xc),
            None, mw["p"], len(xs) + len(xc), auc=mw["auc"])
    return {"mean": S.mean(xs), "ctl": S.mean(xc), "p": w["p_t_approx"], "ci": w["ci95"]}


def ols_block(tag, rows, yk, reg):
    rr = [r for r in rows if r.get(yk) is not None and r.get("d1") is not None]
    if len(rr) < 20:
        reg.add(tag, "robustness", "OLS+HAC（样本不足，未估计）", None, None, None, len(rr))
        return None
    y = [r[yk] for r in rr]
    X = [[1.0, float(r["signal"]), r["d1"], float(r.get("level_pct") or 0.5)] for r in rr]
    res = S.ols_hac(y, X, lags=None)
    if "error" in res:
        return None
    reg.add(tag, "robustness", "OLS + Newey-West HAC：Δ 基差 ~ 信号 + Δ库存 + 库存分位",
            res["beta"][1], None, res["p"][1], res["n"],
            betas={f"b{i}": round(b, 4) for i, b in enumerate(res["beta"])},
            se_hac=[None if s is None else round(s, 4) for s in res["se_hac"]],
            r2=round(res["r2"], 4) if res["r2"] is not None else None,
            hac_lags=res["lags"], hac_inflation=round(res["hac_inflation"], 3) if res["hac_inflation"] else None)
    return res


def block_perm_block(tag, rows, yk, reg):
    rr = [{"g": "signal" if r["signal"] else "control", "y": r[yk]} for r in rows
          if r.get(yk) is not None]
    if len(rr) < 20 or len({r["g"] for r in rr}) < 2:
        return None
    bp = S.block_permutation_p(rr, "g", "y", n_perm=3000)
    reg.add(tag, "robustness", "移动块置换检验（保持块内自相关）", bp["diff"], None,
            bp["p_block_perm"], len(rr), blocks=bp["n_blocks"], n_perm=bp["n_perm"])
    return bp


def nonoverlap_block(rows, market, H, seed=1):
    """Keep entries at least H sessions apart; also a monthly variant."""
    kept, last = [], None
    for r in sorted(rows, key=lambda x: x["T0"]):
        i = market.idx.get(r["T0"])
        if i is None:
            continue
        if last is None or i - last >= H:
            kept.append(r)
            last = i
    monthly, seen = [], set()
    for r in sorted(rows, key=lambda x: x["T0"]):
        m = r["T0"][:7]
        if m in seen:
            continue
        seen.add(m)
        monthly.append(r)
    return kept, monthly


def placebo_block(rows, yk, reg, seeds=(11, 12, 13)):
    """Label shuffle placebo: how often does a random signal look this good?"""
    import random
    xs = [r[yk] for r in rows if r.get(yk) is not None]
    sig = [r["signal"] for r in rows if r.get(yk) is not None]
    if len(xs) < 20 or sum(sig) < 3:
        return None
    obs = S.mean([x for x, g in zip(xs, sig) if g]) - S.mean([x for x, g in zip(xs, sig) if not g])
    hits, total = 0, 0
    for sd in seeds:
        rng = random.Random(sd)
        lab = sig[:]
        rng.shuffle(lab)
        if sum(lab) < 2 or sum(lab) == len(lab):
            continue
        d = S.mean([x for x, g in zip(xs, lab) if g]) - S.mean([x for x, g in zip(xs, lab) if not g])
        total += 1
        if abs(d) >= abs(obs):
            hits += 1
    if not total:
        return None
    p = (hits + 1) / (total + 1)
    reg.add("PLAC_1", "placebo", "标签洗牌安慰剂（信号随机化后 |差|≥观测差异 的比例）",
            round(obs, 3), None, p, len(xs), n_shuffle=total)
    return p


def ar1(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 3:
        return None
    m = S.mean(xs)
    num_ = sum((xs[i] - m) * (xs[i - 1] - m) for i in range(1, len(xs)))
    den = sum((x - m) ** 2 for x in xs)
    return num_ / den if den else None


# --------------------------------------------------------------------------- main study

def run_study(design, inventory_csv, price_csv, minute_csv=None, status="REAL",
              demo_note=""):
    market = Market(price_csv, minute_csv)
    inv = read_csv(inventory_csv)
    rows, skip = build_panel(inv, market, design)
    H = int(design["horizon_main"])
    yk = design.get("target_column", f"dB_{H}")
    reg = Registry(status)

    sig_rows = [r for r in rows if r["signal"]]
    ctl_rows = [r for r in rows if not r["signal"]]
    n_sig, n_ctl = len(sig_rows), len(ctl_rows)

    res = {
        "meta": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "design_version": design.get("version"),
            "design_approved_at": design.get("approved_at"),
            "data_status": status,
            "demo_note": demo_note,
            "inventory_rows": len(inv), "evaluable_states": len(rows),
            "skipped": skip,
            "price_days": len(market.days),
            "inventory_range": [inv[0]["asof"], inv[-1]["asof"]] if inv else None,
            "price_range": [market.days[0], market.days[-1]] if market.days else None,
            "registry_cap": int(design.get("max_pre_registered_tests", 18)),
        },
        "sample": {"n_signal": n_sig, "n_control": n_ctl,
                   "signal_dates": [r["asof"] for r in sig_rows],
                   "min_n_rule_violated": (n_sig < int(design.get("min_signal", 12)) or
                                           n_ctl < int(design.get("min_control", 10)))},
        "tests": [], "stability": {}, "diagnostics": {}, "verdict": None,
    }

    if res["sample"]["min_n_rule_violated"]:
        res["verdict"] = "INSUFFICIENT_SAMPLE"
        res["message"] = (f"信号周 {n_sig} 个、对照周 {n_ctl} 个，低于预登记最小样本规则"
                          f"（信号≥{design.get('min_signal', 12)}、对照≥{design.get('min_control', 10)}）。"
                          "按设计约定：结论只能写『样本不足，无法判断』，不报告任何显著性。")
        reg.add("RULE_1", "diagnostic", "最小样本规则检查（先于数据设定）",
                float(n_sig), None, None, len(rows), required_signal=design.get("min_signal", 12))
        res["tests"] = reg.finalize()
        return res, rows

    xs = [r[yk] for r in sig_rows if r.get(yk) is not None]
    xc = [r[yk] for r in ctl_rows if r.get(yk) is not None]

    # ---- primary
    mean_block("P1", xs, xc, reg, "primary", f"主口径 Δbasis_{H}")
    proportion_block("P2", xs, xc, reg, "primary", f"主口径 Δbasis_{H}")
    bp = S.stationary_bootstrap_ci([r[yk] for r in rows if r.get(yk) is not None])
    reg.add("P3", "primary", "信号组均值 移动块自助 95%CI（全序列顺序）", S.mean(xs),
            bp, None, len(xs))

    # ---- direction of the futures move (independent registration)
    ys = [r[f"dP_{H}"] for r in sig_rows if r.get(f"dP_{H}") is not None]
    yc = [r[f"dP_{H}"] for r in ctl_rows if r.get(f"dP_{H}") is not None]
    mean_block("P4", ys, yc, reg, "primary", f"期货 ΔP_{H}")

    # ---- pre-registered sensitivities
    if 5 in design.get("alt_horizons", []):
        x5s = [r[f"dB_5"] for r in sig_rows if r.get("dB_5") is not None]
        x5c = [r[f"dB_5"] for r in ctl_rows if r.get("dB_5") is not None]
        mean_block("S1", x5s, x5c, reg, "sensitivity", "敏感性 S1：窗口缩短为 5 日")
    dec = [r for r in rows if r["dec14"]]
    dctl = [r for r in rows if not r["dec14"]]
    mean_block("S2", [r[yk] for r in dec if r.get(yk) is not None],
               [r[yk] for r in dctl if r.get(yk) is not None], reg, "sensitivity",
               "敏感性 S2：连续两周降幅均 ≥1.0 万吨")
    # ---- robustness
    ols_block("R1", rows, yk, reg)
    block_perm_block("R2", rows, yk, reg)
    kept, monthly = nonoverlap_block(rows, market, H)
    mean_block("R3", [r[yk] for r in kept if r["signal"] and r.get(yk) is not None],
               [r[yk] for r in kept if not r["signal"] and r.get(yk) is not None],
               reg, "robustness", f"鲁棒性 R3：非重叠样本（间隔≥{H}交易日）")
    mean_block("R4", [r[yk] for r in monthly if r["signal"] and r.get(yk) is not None],
               [r[yk] for r in monthly if not r["signal"] and r.get(yk) is not None],
               reg, "robustness", "鲁棒性 R4：月度样本（每月至多 1 个）")
    placebo_block(rows, yk, reg)

    # ---- stability
    st = {"by_year": [], "by_band": [], "by_baseline_sign": []}
    years = sorted({r["asof"][:4] for r in rows})
    for y in years:
        ss = [r[yk] for r in rows if r["asof"][:4] == y and r["signal"] and r.get(yk) is not None]
        cc = [r[yk] for r in rows if r["asof"][:4] == y and not r["signal"] and r.get(yk) is not None]
        d = None if (len(ss) < 2 or len(cc) < 2) else S.mean(ss) - S.mean(cc)
        p = None if (len(ss) < 3 or len(cc) < 3) else S.welch_t(ss, cc)["p_t_approx"]
        st["by_year"].append({"group": y, "n_signal": len(ss), "n_control": len(cc),
                              "diff": d, "p": p})
    for b in ("LOW", "MID", "HIGH"):
        ss = [r[yk] for r in rows if r["level_band"] == b and r["signal"] and r.get(yk) is not None]
        cc = [r[yk] for r in rows if r["level_band"] == b and not r["signal"] and r.get(yk) is not None]
        d = None if (len(ss) < 2 or len(cc) < 2) else S.mean(ss) - S.mean(cc)
        p = None if (len(ss) < 3 or len(cc) < 3) else S.welch_t(ss, cc)["p_t_approx"]
        st["by_band"].append({"group": b, "n_signal": len(ss), "n_control": len(cc),
                              "diff": d, "p": p})
    for lab, f in (("basis>=0", lambda r: (r.get("basis0") or 0) >= 0),
                   ("basis<0", lambda r: (r.get("basis0") or 0) < 0)):
        ss = [r[yk] for r in rows if f(r) and r["signal"] and r.get(yk) is not None]
        cc = [r[yk] for r in rows if f(r) and not r["signal"] and r.get(yk) is not None]
        d = None if (len(ss) < 2 or len(cc) < 2) else S.mean(ss) - S.mean(cc)
        p = None if (len(ss) < 3 or len(cc) < 3) else S.welch_t(ss, cc)["p_t_approx"]
        st["by_baseline_sign"].append({"group": lab, "n_signal": len(ss), "n_control": len(cc),
                                       "diff": d, "p": p})
    res["stability"] = st

    # ---- diagnostics (explicit look-ahead / overlap / autocorr)
    ys_all = [r[yk] for r in rows if r.get(yk) is not None]
    rho = ar1(ys_all)
    n_eff = S.effective_n(rho, 0.0, len(ys_all)) if rho is not None else len(ys_all)
    res["diagnostics"] = {
        "autocorr_y": rho,
        "effective_n": n_eff if rho is not None else None,
        "overlap_ratio": round(H / 5.0, 2),
        "nonoverlap_n": len(kept),
        "monthly_n": len(monthly),
        "look_ahead": "entry = 报告发布后可得价格；库存使用 T0 前已公布两期（通过）",
        "mult_testing_registered": len(reg.tests),
    }
    res["tests"] = reg.finalize()

    # ---- verdict
    prim = [t for t in res["tests"] if t["family"] == "primary" and t["id"].startswith("P1")
            and t["id"].endswith("_mean")]
    if prim and prim[0]["p"] is not None:
        t = prim[0]
        if t["p"] < 0.05 and t["estimate"] > 0:
            res["verdict"] = "SUPPORTED"
        elif t["p"] < 0.05 and t["estimate"] < 0:
            res["verdict"] = "CONTRADICTED"
        else:
            res["verdict"] = "NOT_SIGNIFICANT"
        res["message"] = f"主检验 p={t['p']:.4f}，均值差={t['estimate']:.3f}，N={t['n']}"
    else:
        res["verdict"] = "NOT_SIGNIFICANT"
    return res, rows


# --------------------------------------------------------------------------- cli

def load_design(path):
    d = json.load(open(path, encoding="utf-8-sig"))
    H = d["horizon"]["main_sessions"]
    flat = {
        "version": d.get("version") or d.get("schema_version"),
        "approved_at": d.get("approved_at"),
        "horizon_main": H,
        "horizons": sorted({H} | {int(x) for x in d["horizon"].get("alt_sessions", [])}),
        "alt_horizons": d["horizon"].get("alt_sessions", []),
        "entry": "pre15" if d.get("entry_rule", {}).get("main") == "pre15" else "next",
        "min_signal": 12, "min_control": 10,
        "target_column": f"dB_{H}",
        "max_pre_registered_tests": 18,
    }
    return flat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default="build/research_design.formal.json")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--price", required=True)
    ap.add_argument("--minute", default="")
    ap.add_argument("--out", default="build/results.json")
    ap.add_argument("--samples", default="")
    ap.add_argument("--status", default="REAL")
    ap.add_argument("--demo-note", default="")
    a = ap.parse_args()
    d = load_design(a.design)
    res, rows = run_study(d, a.inventory, a.price, a.minute or None,
                          status=a.status, demo_note=a.demo_note)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
    if a.samples:
        keys = sorted({k for r in rows for k in r})
        with open(a.samples, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)
    print(f"verdict={res['verdict']} n_signal={res['sample']['n_signal']} "
          f"n_control={res['sample']['n_control']} tests={len(res['tests'])} -> {a.out}")


if __name__ == "__main__":
    main()
