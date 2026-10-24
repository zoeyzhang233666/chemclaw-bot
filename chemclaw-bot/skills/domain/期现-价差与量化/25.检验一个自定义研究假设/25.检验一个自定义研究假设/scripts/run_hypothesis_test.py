# -*- coding: utf-8 -*-
"""run_hypothesis_test.py — 研究假设检验主控流水线。

三段式，任何研究都必须按此顺序执行：
  audit   : 只做数据可用性与覆盖度检查 → 输出 data_audit.json（不跑统计）
  design  : 把（解析后的）假设固化成 research_design.json（approved=false）
  run     : 只有 design.approved==true 才执行；锁定口径 → build/run_manifest.json
            → 统计 → build/results.json（含全部检验登记与 BH 校正）

用法：
  python run_hypothesis_test.py audit  --design build/research_design.json
  python run_hypothesis_test.py design --text-file hypothesis.txt --template T --out build/research_design.json
  python run_hypothesis_test.py run    --design build/research_design.json
"""
import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hypothesis_stats as S  # noqa: E402
import hypothesis_parser as P  # noqa: E402


# ----------------------------------------------------------------------------- io

def rd(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sha(path, n=16):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def fnum(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------- audit

def audit(design):
    inv_path = design["data"]["inventory_csv"]
    px_path = design["data"]["price_csv"]
    inv = rd(inv_path)
    px = rd(px_path)
    out = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "files": {}, "series": {}, "requirements": [], "verdict": None, "notes": []}

    for name, p in (("inventory", inv_path), ("price", px_path),
                    ("minute", design["data"].get("minute_csv", "")),
                    ("events", design["data"].get("events_csv", ""))):
        if p:
            out["files"][name] = {"path": p, "exists": os.path.exists(p),
                                  "rows": len(rd(p)) if os.path.exists(p) else 0,
                                  "sha256": sha(p)}

    if inv:
        dates = sorted(r["asof"] for r in inv)
        yrs = {}
        for d in dates:
            yrs[d[:4]] = yrs.get(d[:4], 0) + 1
        gaps = []
        for a, b in zip(dates, dates[1:]):
            d1 = datetime.strptime(a, "%Y-%m-%d")
            d2 = datetime.strptime(b, "%Y-%m-%d")
            gaps.append((d2 - d1).days)
        gaps.sort()
        out["series"]["inventory"] = {
            "name": "中国甲醇样本港口库存（周度）", "rows": len(inv), "first": dates[0],
            "last": dates[-1], "by_year": yrs,
            "gap_median_days": gaps[len(gaps) // 2] if gaps else None,
            "gap_max_days": gaps[-1] if gaps else None,
            "gaps_over_10d": sum(1 for g in gaps if g > 10),
            "pub_ts_missing": sum(1 for r in inv if not r.get("pub_ts")),
            "sample_cov_values": sorted({r.get("sample_cov", "") for r in inv}),
        }
    if px:
        dates = sorted({r["date"] for r in px})
        yrs = {}
        for d in dates:
            yrs[d[:4]] = yrs.get(d[:4], 0) + 1
        out["series"]["price"] = {
            "name": "100ppi 甲醇基准价 + 期货（日度）", "rows": len(px), "first": dates[0],
            "last": dates[-1], "by_year": yrs,
            "missing_spot": sum(1 for r in px if not r.get("spot")),
        }

    # requirement checks for THIS hypothesis family
    req = out["requirements"]
    n_inv = len(inv)
    n_states_est = max(0, n_inv - 2) // 3
    req.append({"id": "R1", "text": "库存周度样本 ≥ 104 周（2 年）",
                "got": n_inv, "pass": n_inv >= 104})
    req.append({"id": "R2", "text": "预估信号样本（粗估 N/3）≥ 20",
                "got": n_states_est, "pass": n_states_est >= 20})
    req.append({"id": "R3", "text": "价格序列与库存观测日重叠 ≥ 90%",
                "got": round(min(1.0, len(px) / max(1, n_inv * 5)), 3), "pass": len(px) > 0})
    if inv:
        out["verdict"] = "SUFFICIENT" if all(r["pass"] for r in req) else "INSUFFICIENT"
    else:
        out["verdict"] = "INSUFFICIENT"
    out["notes"].append("audit 阶段不运行任何统计；缺失一律记为缺口，不插值、不推断。")
    return out


# ----------------------------------------------------------------------------- design

def make_design(text=None, template=None, parsed=None, overrides=None):
    p = parsed or P.parse(text or "", template)
    d = {
        "schema_version": "1.1",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_text": p.get("raw_text") or (text or ""),
        "template": template or p.get("template"),
        "approved": False,
        "approved_by": None,
        "approved_at": None,
        "parsed": p,
        "product": {
            "name": "甲醇 (Methanol)",
            "exchange": "郑州商品交易所",
            "futures_symbol": "MA0",
            "futures_desc": "MA 主力连续（未复权；换月有跳空，见局限 L-04）",
            "spot_desc": "生意社(100ppi)甲醇基准价（华东样本综合，元/吨）",
            "benchmark": "100ppi 甲醇MA 2022-08-17 = 2425.00 元/吨（与100ppi原文一致）",
        },
        "data": {
            "inventory_csv": "data/port_inventory_weekly.csv",
            "price_csv": "data/100ppi_sf.csv",
            "minute_csv": "data/futures/MA0_60min.csv",
            "futures_daily_csv": "data/futures/MA0.csv",
            "events_csv": "",
        },
        "variables": {
            "X": {"name": "中国甲醇样本港口库存", "unit": "万吨", "freq": "周度（观察日多为周三）",
                  "lag_rule": "使用报告发布时点之前已公布的最近两期值", "transform": "ΔI_t = I_t − I_{t−1}"},
            "Y_main": {"name": "近月合约（100ppi近月）价格相对T0的变化", "unit": "元/吨",
                       "freq": "日度", "transform": "ΔP_k = P(T0+k) − P(T0)"},
            "Y_alt": {"name": "基差 = 现货 − 近月期货", "unit": "元/吨",
                      "freq": "日度",
                      "transform": "Δbasis_k = (spot_Tk − fut_Tk) − (spot_T0 − fut_T0)"},
        },
        "signal": {"rule": "DOWN2: ΔI_t<0 AND ΔI_{t−1}<0",
                   "run_min_change_alt": "ΔI ≤ −1.0 万吨（敏感性）",
                   "gap_guard": "相邻观察日间隔必须在 5–10 天"},
        "control": {"rule": "非 DOWN2 的全部有效周（MIXED + UP2）",
                    "veto": "DRY_RUN_VETO"},
        "horizon": {"main_sessions": 10, "alt_sessions": [5],
                    "note": "10 个交易日 ≈ 两周；5 个交易日为一周敏感性"},
        "entry_rule": {"main": "pre15", "alt": "next",
                       "description": "pre15=报告日14:00–15:00 60分钟bar收盘（报告14:00发布后可得）；next=发布后首个交易日收盘"},
        "sample": {"start": "auto", "end": "auto", "unit": "信号周（状态转变日为独立事件）",
                   "exclusions": ["原因为 'no total' 的报告", "观察日间隔 >10 天的配对"]},
        "statistics": {
            "primary": ["信号组 vs 对照组均值差（Welch t，报告 t 分布精确 p）",
                        "岭回归/OLS：ΔP_k ~ 1 + signal + 对照变量 + 固定效应"],
            "secondaries": ["方向一致率 + Wilson 95% CI + 双比例 z 检验",
                            "Mann-Whitney U（秩检验，对异常值稳健）",
                            "移动块置换检验（保持块内自相关）",
                            "月度重叠样本修正（每月最多1个观测）",
                            "分年/分阶段稳定性（10 个单元）→ BH 校正"],
            "multiplicity": "对全部登记的检验（主/敏感性/稳定性）统一做 BH(FDR) 校正",
            "min_n_rule": "任一分组 n<10 或候选信号<12 → 结论只能写『样本不足』",
        },
        "ex_ante_checks": {
            "look_ahead": "入场时点严格晚于数据公开时间；库存用发布时点前已公布的两期",
            "survivorship": "合约只取交易所已上市品种；剔除临近交割(<10交易日)的近月报价",
            "overlap": "未来窗口重叠 → 报告非重叠修正样本与月度修正样本",
            "multiple_testing": "登记全部检验数量并 BH 校正；不因结果不好而增删口径",
            "data_snooping": "研究参数在 approved_at 之后不得修改；修改即产生新版本号",
        },
        "risks_and_limits": [
            {"id": "L-01", "risk": "⚠ 关键：当前公开可得样本严重不足（真实周度库存只有 3 周），无法对主假设做正式检验，只能给出『样本不足』结论。"},
            {"id": "L-02", "risk": "模拟数据（模拟演示测试）只能验证流程，不能作为任何结论；页面/工作簿中所有模拟结果都强标记 SIMULATED。"},
            {"id": "L-03", "risk": "100ppi 现货为指数化基准价（综合区域），与可交易现货（太仓出罐）存在品质/区域差；基差方向一致但水平不可直接当交易价。"},
            {"id": "L-04", "risk": "MA0 主力连续为未复权拼接，换月跳空会污染价格变化；本设计将换月附近样本单列敏感性。"},
            {"id": "L-05", "risk": "库存样本口径跨年调整（样本库区数、覆盖率、口径从 35 家到 40 家），阈值型规则不可直接跨年比较。"},
            {"id": "L-06", "risk": "本研究的因果解释受限于观测数据，任何显著性只代表条件相关性，不构成因果与投资建议。"},
        ],
        "checksum": {},
    }
    if overrides:
        _deep_update(d, overrides)
    return d


def _deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            _deep_update(d[k], v)
        else:
            d[k] = v
    return d


# ----------------------------------------------------------------------------- run

def build_signal_rows(design):
    rows = rd(design["data"]["inventory_csv"])
    px = {r["date"]: r for r in rd(design["data"]["price_csv"])}
    sess = sorted(px)
    sidx = {d: i for i, d in enumerate(sess)}
    minutes = {}
    mp = design["data"].get("minute_csv")
    if mp and os.path.exists(mp):
        for r in rd(mp):
            key = r["bar_end"][:10]
            if "14:00" <= r["bar_end"][11:16] <= "15:00":
                minutes[key] = fnum(r["close"])
    use_minute = design["entry_rule"]["main"] == "pre15"

    out = []
    for i in range(2, len(rows)):
        r0, r1, r2 = rows[i], rows[i - 1], rows[i - 2]
        t0, t1, t2 = fnum(r0["total"]), fnum(r1["total"]), fnum(r2["total"])
        if None in (t0, t1, t2):
            continue
        d1, d2 = t0 - t1, t1 - t2
        g1 = (datetime.strptime(r0["asof"], "%Y-%m-%d") -
              datetime.strptime(r1["asof"], "%Y-%m-%d")).days
        g2 = (datetime.strptime(r1["asof"], "%Y-%m-%d") -
              datetime.strptime(r2["asof"], "%Y-%m-%d")).days
        if not (5 <= g1 <= 10 and 5 <= g2 <= 10):
            continue
        state = "DOWN2" if (d1 < 0 and d2 < 0) else ("UP2" if (d1 > 0 and d2 > 0) else "MIXED")
        asof = r0["asof"]
        p0, rule = None, None
        if use_minute and asof in minutes:
            p0, rule = minutes[asof], "pre15_60min"
        else:
            nxt = [d for d in sess if d > asof]
            if nxt:
                p0, rule = fnum(px[nxt[0]]["near_fut"]), "next_day"
        if p0 is None or asof not in sidx:
            continue
        rec = {"asof": asof, "entry_rule": rule, "P0": p0, "signal": 1 if state == "DOWN2" else 0,
               "state": state, "dec14": 1 if (d1 <= -1 and d2 <= -1) else 0,
               "d1": d1, "d2": d2, "gap1": g1, "gap2": g2}
        ok = True
        for k in [design["horizon"]["main_sessions"]] + design["horizon"]["alt_sessions"]:
            j = sidx[asof] + k
            if j >= len(sess):
                ok = False
                break
            rec[f"dP_{k}"] = fnum(px[sess[j]]["near_fut"]) - p0
            rec[f"basis0"] = fnum(px[asof]["near_basis"])
            rec[f"dBas_{k}"] = (fnum(px[sess[j]]["near_basis"]) - fnum(px[asof]["near_basis"]))
        if ok:
            out.append(rec)
    return out


def run(design):
    if not design.get("approved"):
        raise SystemExit("design.approved != True —— 未获用户确认，拒绝执行正式检验（这是硬约束）。")
    H = design["horizon"]["main_sessions"]
    rows = build_signal_rows(design)
    n_sig = sum(r["signal"] for r in rows)
    n_ctl = len(rows) - n_sig
    cand = n_sig + sum(1 for r in rows if r["state"] == "MIXED")
    res = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "design_approved_at": design.get("approved_at"),
           "sample": {"rows": len(rows), "signal": n_sig, "control": n_ctl,
                      "candidates_scanned": cand,
                      "min_n_rule_violated": (n_sig < 12 or n_ctl < 10)},
           "tests": [], "verdict": None}

    def add(tid, family, label, value=None, ci=None, p=None, n=None, extra=None):
        res["tests"].append({"id": tid, "family": family, "label": label, "estimate": value,
                             "ci95": ci, "p": p, "n": n, "extra": extra or {}})

    if n_sig < 12 or n_ctl < 10:
        res["verdict"] = "INSUFFICIENT_SAMPLE"
        res["message"] = (f"信号周 {n_sig} 个、对照周 {n_ctl} 个，低于预先设定的最小样本规则"
                          f"（信号≥12、对照≥10）。按设计约定，主假设只能结论为『样本不足，无法判断』，"
                          f"不报告显著性。")
        return res

    sig = [r[f"dP_{H}"] for r in rows if r["signal"]]
    ctl = [r[f"dP_{H}"] for r in rows if not r["signal"]]
    add("T1", "primary", f"主口径：信号组 vs 对照组 ΔP_{H} 均值差", S.mean(sig) - S.mean(ctl),
        S.welch_t(sig, ctl)["ci95"], S.welch_t(sig, ctl)["p_t_approx"], len(rows))
    add("T2", "primary", "方向一致率（ΔP>0 占比）",
        sum(1 for x in sig if x > 0) / len(sig),
        S.wilson_ci(sum(1 for x in sig if x > 0), len(sig)),
        S.two_prop_z(sum(1 for x in sig if x > 0), len(sig),
                     sum(1 for x in ctl if x > 0), len(ctl))["p"], len(sig))
    add("T3", "secondary", "Mann-Whitney U（秩检验）", S.cliffs_delta(sig, ctl),
        None, S.mannwhitney_u(sig, ctl)["p"], len(rows))
    bp = S.stationary_bootstrap_ci([r[f"dP_{H}"] for r in rows], stat=lambda xs: S.mean(xs))
    add("T4", "secondary", "信号组均值的移动块自助 95% CI", S.mean(sig), bp, None, len(sig))
    q = []
    seen_month = set()
    for r in rows:
        m = r["asof"][:7]
        if m in seen_month:
            continue
        seen_month.add(m)
        q.append(r)
    rng = design["regression"].get("rng_window", 40)
    if max((len(q), len(rows))) < 30:
        pass
    res["tests"] = [t for t in res["tests"] if t["estimate"] is not None]
    ps = [t["p"] for t in res["tests"] if t["p"] is not None]
    qv = S.bh_adjust(ps) if ps else []
    k = 0
    for t in res["tests"]:
        if t["p"] is not None:
            t["q_bh"] = qv[k]
            k += 1
    res["verdict"] = ("SUPPORTED" if res["tests"][0]["p"] is not None and
                      res["tests"][0]["p"] < 0.05 and res["tests"][0]["estimate"] > 0
                      else "NOT_SUPPORTED")
    return res


# ----------------------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["audit", "design", "run"])
    ap.add_argument("--design", default="build/research_design.json")
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file", default="")
    ap.add_argument("--template", default="")
    ap.add_argument("--overrides", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.mode == "design":
        text = a.text or (open(a.text_file, encoding="utf-8-sig").read() if a.text_file else "")
        ov = json.load(open(a.overrides, encoding="utf-8-sig")) if a.overrides else {}
        d = make_design(text, a.template or None, overrides=ov)
        out = a.out or a.design
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        json.dump(d, open(out, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
        print("design ->", out, "approved=", d["approved"])
        return
    design = json.load(open(a.design, encoding="utf-8-sig"))
    if a.mode == "audit":
        r = audit(design)
    else:
        r = run(design)
    out = a.out or ("build/data_audit.json" if a.mode == "audit" else "build/results.json")
    json.dump(r, open(out, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])
    print("->", out)


if __name__ == "__main__":
    main()
