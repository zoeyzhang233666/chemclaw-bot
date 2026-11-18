# -*- coding: utf-8 -*-
"""
analyze.py — 比价主分析：一条命令产出全部可复核数字
=====================================================
输出 JSON 里每个数字都带口径（方向、窗口、样本量、算法），
报告只能引用这里算出来的数，不允许另算。

用法
----
python scripts/analyze.py --a build/price_A.csv --b build/price_B.csv \
    --rolls build/roll_ledger.csv --out build/result.json \
    --name-a PP --name-b L --warmup 20

方向
----
默认 ratio = A/B。--direction BA 则输出 B/A（内部用 1/r 精确换算，
并同样交换两侧价格标注，保证"比价方向与价格列"永远一致）。
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ratiolib as R


def read_price(path):
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            def g(k):
                v = row.get(k)
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
            out.append((row["date"], g("close")))
    out.sort(key=lambda x: x[0])
    return out


def read_rolls(path):
    if not path or not os.path.exists(path):
        return {}
    d = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            d.setdefault(row["date"], []).append(row)
    return d


def year_of(d):
    return d[:4]


def main():
    ap = argparse.ArgumentParser(description="比价主分析")
    ap.add_argument("--a", required=True, help="品种 A 价格 csv")
    ap.add_argument("--b", required=True, help="品种 B 价格 csv")
    ap.add_argument("--rolls", default=None, help="换月台账 csv")
    ap.add_argument("--out", required=True, help="输出 json")
    ap.add_argument("--name-a", default="A")
    ap.add_argument("--name-b", default="B")
    ap.add_argument("--direction", default="AB", choices=["AB", "BA"],
                    help="AB = A/B（默认）；BA = B/A")
    ap.add_argument("--warmup", type=int, default=20,
                    help="计算'前序样本分位'时剔除的最近样本数")
    ap.add_argument("--outlier-window", type=int, default=120)
    ap.add_argument("--outlier-z", type=float, default=3.5)
    args = ap.parse_args()

    pa = read_price(args.a)
    pb = read_price(args.b)

    if args.direction == "AB":
        rows = R.build_ratio(pa, pb)
        na, nb = args.name_a, args.name_b
    else:
        rows = R.build_ratio(pb, pa)
        na, nb = args.name_b, args.name_a
    rows = [r for r in rows if r[3] is not None]
    if not rows:
        print("ERROR: 无有效比价样本")
        sys.exit(2)

    rolls = read_rolls(args.rolls)

    end = rows[-1][0]
    res = {
        "meta": {
            "product_a": na, "product_b": nb,
            "direction": "%s/%s" % (na, nb),
            "direction_code": args.direction,
            "sample_start": rows[0][0], "sample_end": end,
            "n_valid": len(rows),
            "warmup_days": args.warmup,
            "outlier_window": args.outlier_window, "outlier_z": args.outlier_z,
            "note": "比价按收盘价逐日对齐；任一侧缺失则该日剔除，不插值。",
        },
        "current": {},
        "windows": {},
        "changes": R.change_metrics(rows, lookbacks=(1, 5, 10, 20, 60, 120, 250)),
        "contribution": {},
        "outliers": {},
        "rolls": {},
        "yearly": [],
        "regimes": [],
        "series": [],
    }

    cur = rows[-1]
    res["current"] = {
        "date": cur[0], "a": cur[1], "b": cur[2], "ratio": cur[3],
    }

    # ---- 1/3/5 年窗口：日历回溯口径 与 前序样本口径 ----
    for label, yrs in (("1Y", 1), ("3Y", 3), ("5Y", 5)):
        s = R.date_offset(end, years=-yrs)
        cal = R.window_stats(rows, s, end)
        pri = R.prior_sample_stats(rows, args.warmup, s, end)
        res["windows"][label] = {
            "window_start": s, "window_end": end,
            "calendar": {k: v for k, v in cal.items()},
            "prior": {k: v for k, v in pri.items()},
        }
    # 全样本
    full = R.window_stats(rows)
    res["windows"]["ALL"] = {
        "window_start": rows[0][0], "window_end": end,
        "calendar": {k: v for k, v in full.items()},
        "prior": dict(R.prior_sample_stats(rows, args.warmup)),
    }

    # ---- 贡献分解：多个窗口 ----
    for label, yrs in (("1Y", 1), ("3Y", 3), ("5Y", 5)):
        s = R.date_offset(end, years=-yrs)
        c = R.contribution(rows, s, end)
        if c:
            res["contribution"][label] = c
    c_all = R.contribution(rows, rows[0][0], end)
    if c_all:
        res["contribution"]["ALL"] = c_all

    # 近 60 日与近 20 日（反映"最近变化"来自哪边）
    for lb, key in ((20, "M1"), (60, "M3"), (120, "M6")):
        if len(rows) > lb:
            c = R.contribution(rows, rows[-1 - lb][0], end)
            if c:
                res["contribution"][key] = c

    # ---- 逐年 ----
    by_year = {}
    for r in rows:
        by_year.setdefault(year_of(r[0]), []).append(r)
    for y in sorted(by_year):
        sub = by_year[y]
        vals = [r[3] for r in sub]
        res["yearly"].append({
            "year": y, "n": len(vals),
            "mean": R.mean(vals), "median": R.median(vals),
            "min": min(vals), "max": max(vals),
            "min_date": min(sub, key=lambda r: r[3])[0],
            "max_date": max(sub, key=lambda r: r[3])[0],
            "last": vals[-1],
            "pct_in_year": R.percentile_rank(vals, vals[-1])["pct"],
        })

    # ---- 异常点 ----
    outs = R.detect_outliers(rows, window=args.outlier_window, z_thresh=args.outlier_z)
    flagged = [o for o in outs if o[3]]
    res["outliers"] = {
        "method": "稳健 z 分数（滚动 %d 日中位数/MAD），|z| > %.1f"
                  % (args.outlier_window, args.outlier_z),
        "count": len(flagged),
        "n_evaluated": len(outs),
        "items": [{"date": d, "ratio": v, "z": z,
                   "on_roll_day": d in rolls} for d, v, z, f in flagged],
    }

    # ---- 换月对异常点的解释力 ----
    roll_dates = sorted(rolls)
    roll_hits = [d for d in roll_dates if any(o["date"] == d for o in res["outliers"]["items"])]
    res["rolls"] = {
        "n_events": len(roll_dates),
        "max_abs_spread_pct": max(
            (abs(float(r["spread_old_minus_new_pct"])) for d in roll_dates for r in rolls[d]
             if r.get("spread_old_minus_new_pct") not in (None, "")), default=None),
        "events": [{"date": d, "old": rolls[d][0]["old_contract"],
                    "new": rolls[d][0]["new_contract"],
                    "spread_pct": (float(rolls[d][0]["spread_old_minus_new_pct"])
                                   if rolls[d][0].get("spread_old_minus_new_pct") not in (None, "") else None)}
                   for d in roll_dates],
        "roll_days_flagged_as_outlier": roll_hits,
        "warning": "换月日两侧品种切换不同合约，当日比价变动含换月跳空，不等于产业面驱动。"
                   "识别到换月日应单独标注，不并入'贡献分解'的产业解释。",
    }

    # ---- 分段（由产业结构决定，不是为凑结果切） ----
    # 这里的断点来自比价长期中枢的实证变化 + PP/PE 产能投放节奏，见 references/04
    segments = [
        ("2014-02-28", "2016-12-30", "煤制烯烃集中投产 + 油价崩跌，PP 相对走弱"),
        ("2017-01-03", "2019-10-31", "PE 新增产能集中释放，PP 相对走强"),
        ("2019-11-01", "2021-12-31", "疫情后放水 + 2021 能耗双控，两者同涨"),
        ("2022-01-04", "2024-12-31", "PP 大扩能周期，比价回落"),
        ("2025-01-01", "2099-12-31", "PE/PP 同步扩能 + 2026 供给冲击"),
    ]
    for s, e, desc in segments:
        sub = [r for r in rows if s <= r[0] <= min(e, end)]
        if len(sub) < 30:
            continue
        vals = [r[3] for r in sub]
        c = R.contribution(rows, sub[0][0], sub[-1][0])
        res["regimes"].append({
            "start": sub[0][0], "end": sub[-1][0], "n": len(sub),
            "label": desc,
            "mean": R.mean(vals), "median": R.median(vals),
            "min": min(vals), "max": max(vals),
            "contribution": c,
        })

    # ---- 序列（供前端画图；含滚动分位、滚动均值、异常标记） ----
    rp = R.rolling_percentile(rows, window=252, prior_days=0)
    rm = R.rolling_mean(rows, window=252)
    rp_map = dict(rp)
    rm_map = dict(rm)
    out_map = {d: (z, f) for d, v, z, f in outs}
    for d, a, b, ratio, am, bm in rows:
        z, f = out_map.get(d, (None, False))
        res["series"].append({
            "d": d, "a": a, "b": b, "r": ratio,
            "rp": rp_map.get(d), "rm": rm_map.get(d),
            "z": z, "out": bool(f), "roll": d in rolls,
        })

    # ---- 稳健性：不同样本定义下当前分位如何变 ----
    robust = []
    for lab, yrs in (("近1年", 1), ("近3年", 3), ("近5年", 5)):
        s = R.date_offset(end, years=-yrs)
        w = R.window_stats(rows, s, end)
        robust.append({"sample": lab, "n": w["n"], "pct": w["pct_rank"]})
    robust.append({"sample": "全样本", "n": full["n"], "pct": full["pct_rank"]})
    # 剔除最近半年
    cut = rows[-1][0]
    idx = max(0, len(rows) - 120)
    pre_end = rows[idx][0]
    w_pre = R.window_stats(rows, rows[0][0], pre_end)
    cur_v = rows[-1][3]
    pv = [r[3] for r in rows[:idx + 1]]
    robust.append({"sample": "全样本剔除近120个交易日", "n": len(pv),
                   "pct": R.percentile_rank(pv, cur_v)["pct"]})
    for y0, y1, lab in (("2014", "2017", "2014-2017"), ("2018", "2022", "2018-2022"),
                        ("2023", "2025", "2023-2025")):
        pv = [r[3] for r in rows if y0 <= r[0][:4] <= y1]
        if pv:
            robust.append({"sample": lab + " 区间内", "n": len(pv),
                           "pct": R.percentile_rank(pv, cur_v)["pct"]})
    res["robustness"] = robust

    # ---- 结构性检验：对 ln(比价) 做两段均值偏移扫描 ----
    import math
    x = [math.log(r[3]) for r in rows]
    n = len(x)
    best = []
    for k in range(120, n - 120):
        seg_a, seg_b = x[:k], x[k:]
        ma, mb = sum(seg_a) / len(seg_a), sum(seg_b) / len(seg_b)
        va = sum((v - ma) ** 2 for v in seg_a) / (len(seg_a) - 1)
        vb = sum((v - mb) ** 2 for v in seg_b) / (len(seg_b) - 1)
        se = math.sqrt(va / len(seg_a) + vb / len(seg_b))
        if se > 0:
            best.append((abs((mb - ma) / se), k, (mb - ma) / se))
    best.sort(reverse=True)
    picks, used = [], []
    for at, k, t in best:
        if any(abs(k - u) < 130 for u in used):
            continue
        used.append(k)
        picks.append({"date": rows[k][0], "t": t,
                      "before_mean": math.exp(sum(x[:k]) / k),
                      "after_mean": math.exp(sum(x[k:]) / (n - k)),
                      "n_before": k, "n_after": n - k})
        if len(picks) >= 5:
            break
    res["structure_scan"] = {
        "method": "对 ln(比价) 做两段均值偏移扫描（Welch t，最小段长 120 样本），"
                  "取 t 最大的若干个不重叠断点",
        "candidates": picks,
        "rolling_mean_252": [{"d": d, "v": v} for d, v in rm if v is not None],
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    # 控制台摘要
    print("=" * 72)
    print("%s/%s  样本 %s → %s  N=%d" % (na, nb, rows[0][0], end, len(rows)))
    print("当前 %s = %.4f  (%s=%.0f, %s=%.0f)  %s"
          % (res["meta"]["direction"], cur[3], na, cur[1], nb, cur[2], cur[0]))
    for lab in ("1Y", "3Y", "5Y", "ALL"):
        w = res["windows"][lab]
        print("  %-4s N=%4d  中位 %.4f  均值 %.4f  [%.4f, %.4f]  日历分位 %5.1f%%  前序分位 %5.1f%%"
              % (lab, w["calendar"]["n"], w["calendar"]["median"], w["calendar"]["mean"],
                 w["calendar"]["min"], w["calendar"]["max"],
                 w["calendar"]["pct_rank"] or -1, w["prior"]["pct_rank"] or -1))
    for lab in ("M1", "M3", "M6", "1Y", "3Y", "5Y", "ALL"):
        c = res["contribution"].get(lab)
        if c:
            print("  贡献 %-4s 比价 %+6.1f%%  |  %s %+7.1f%%  %s %+7.1f%%  → 主导 %s (%.0f%%/%.0f%%)"
                  % (lab, c["ratio_chg_pct"], na, c["a_chg_pct"], nb, c["b_chg_pct"],
                     c["dominant"], c["share_a"], c["share_b"]))
    print("异常点 %d 个（%s），其中落在换月日 %d 个"
          % (res["outliers"]["count"], res["outliers"]["method"],
             len(res["rolls"]["roll_days_flagged_as_outlier"])))
    print("稳健性（当前值的分位）:")
    for r in res["robustness"]:
        print("    %-24s N=%4d  %5.1f%%" % (r["sample"], r["n"], r["pct"]))
    print("结构断点候选:")
    for p in res["structure_scan"]["candidates"]:
        print("    %s  t=%6.2f  %.4f → %.4f" % (p["date"], p["t"], p["before_mean"], p["after_mean"]))
    print("=" * 72)
    print("written:", args.out)


if __name__ == "__main__":
    main()

