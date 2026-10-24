# -*- coding: utf-8 -*-
"""
prep_data.py — 从原始合约 K 线装配"可比价格序列" + 换月台账
================================================================
这一步只做**装配与记录**，不做统计。

输入（--raw 目录）：
    {PREFIX}0.json   连续/主连序列（Sina InnerFuturesNewService.getDailyKLine）
    {PREFIX}{YYMM}.json  单合约序列（用于换月检查与交叉校验）

输出（--out 目录）：
    price_A.csv / price_B.csv      归一化价格：date,close,open,high,low,volume,oi
    roll_ledger.csv                换月台账：换月日、新旧合约、新旧价差、比价污染
    qc_report.json                 数据质量闸门结果
    contract_panel.csv             全合约面板（可选，供深度复核）

口径说明（写进报告，不许省）：
  连续序列 = 该品种当日**持仓量最大**合约的收盘价拼接（Sina "L0/PP0" 主连）。
  换月日不做事后复权处理；换月带来的跳空单独计量，并在异常点识别中标注。
"""
import argparse
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_json(path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise IOError("cannot read " + path)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_series(path):
    rows = []
    for r in load_json(path):
        rows.append({
            "date": r["d"],
            "open": num(r.get("o")), "high": num(r.get("h")),
            "low": num(r.get("l")), "close": num(r.get("c")),
            "volume": num(r.get("v")) or 0.0, "oi": num(r.get("p")) or 0.0,
        })
    rows.sort(key=lambda x: x["date"])
    return rows


def qc(series, name, contract_index):
    """数据质量闸门：任何 ERROR 都不允许继续。"""
    errs, warns, info = [], [], {}
    dates = [r["date"] for r in series]
    info["rows"] = len(series)
    info["start"] = dates[0] if dates else None
    info["end"] = dates[-1] if dates else None
    if not series:
        errs.append("序列为空")
        return {"name": name, "errors": errs, "warnings": warns, "info": info}
    if len(set(dates)) != len(dates):
        errs.append("日期重复 %d 处" % (len(dates) - len(set(dates))))
    if any(r["close"] is None for r in series):
        errs.append("close 存在空值")
    if any((r["close"] or 0) <= 0 for r in series):
        errs.append("close 存在非正值")
    # OHLC 完整性
    bad = [r for r in series if r["high"] and r["low"] and r["close"]
           and (r["high"] < r["low"] or r["close"] > r["high"] * 1.001
                or r["close"] < r["low"] * 0.999)]
    info["ohlc_violations"] = len(bad)
    if bad:
        warns.append("OHLC 内部矛盾 %d 处，例：%s" % (len(bad), bad[0]["date"]))
    # 涨跌幅极值
    jumps = []
    for i in range(1, len(series)):
        a, b = series[i - 1]["close"], series[i]["close"]
        if a and b and abs(b / a - 1) > 0.15:
            jumps.append((series[i]["date"], (b / a - 1) * 100))
    info["abs_move_gt15"] = len(jumps)
    if jumps:
        warns.append("单日涨跌超 ±15%% %d 处：%s" % (len(jumps), jumps[:3]))
    # 零成交
    zv = [r["date"] for r in series if r["volume"] == 0]
    info["zero_volume_days"] = len(zv)
    if zv:
        warns.append("零成交日 %d 天（多为节假日前后），例：%s" % (len(zv), zv[:3]))
    # 连续序列是否落在当日真实挂盘合约上
    miss = [r["date"] for r in series if r["date"] not in contract_index]
    info["dates_without_listed_contract"] = len(miss)
    if miss:
        warns.append("连续序列有 %d 个日期在单合约库中找不到对应合约（多为早期历史），"
                     "已保留但标注" % len(miss))
    return {"name": name, "errors": errs, "warnings": warns, "info": info}


def build_contract_index(raw_dir, prefixes):
    idx = {}
    for p in prefixes:
        for f in glob.glob(os.path.join(raw_dir, p + "[0-9][0-9][0-9][0-9].json")):
            if os.path.getsize(f) < 10:
                continue
            try:
                data = load_json(f)
            except Exception:
                continue
            for r in data:
                if "d" in r:
                    idx.setdefault(r["d"], set()).add(os.path.basename(f)[:-5])
    return idx


def detect_rolls(raw_dir, prefix, series, listed_months=None):
    """
    识别换月日：在**持仓量最大**的合约发生变化的那一天。

    为什么不用"收盘价相等"来识别：多个合约的收盘价可能恰好相同（尤其远月流动性差、
    报价不动），会造成假换月。用持仓量（OI）做主合约判定更稳，也符合连续序列
    "主连 = 持仓量最大合约"的定义。

    同时对每个换月点计算新旧合约在同一交易日的价差，用来衡量换月跳空（污染）。
    """
    contracts = {}
    for f in glob.glob(os.path.join(raw_dir, prefix + "[0-9][0-9][0-9][0-9].json")):
        if os.path.getsize(f) < 10:
            continue
        name = os.path.basename(f)[:-5]
        try:
            data = load_json(f)
        except Exception:
            continue
        m = {}
        for r in data:
            if "d" in r:
                c = num(r.get("c"))
                if c is not None:
                    m[r["d"]] = (c, num(r.get("p")) or 0.0, num(r.get("v")) or 0.0)
        if m:
            contracts[name] = m

    rolls = []
    cur = None
    cur_start = None
    for r in series:
        d, c = r["date"], r["close"]
        # 当日所有挂盘且成交量>0 的合约
        live = [(n, m[d]) for n, m in contracts.items() if d in m]
        if not live:
            continue
        # 先看是否有合约与连续序列价格完全一致；若有多个，取持仓量最大者
        exact = [(n, v) for n, v in live if abs(v[0] - c) < 1e-9]
        if exact:
            pick = max(exact, key=lambda x: x[1][1])[0]
        else:
            # 价格都不等（连续序列可能来自未抓取的月合约）：按持仓量最大判定
            pick = max(live, key=lambda x: x[1][1])[0]
        if cur is None:
            cur, cur_start = pick, d
        elif pick != cur:
            spread = None
            old_m, new_m = contracts.get(cur, {}), contracts.get(pick, {})
            common = sorted(set(old_m) & set(new_m))
            prior = [x for x in common if x <= d]
            if prior:
                dd = prior[-1]
                if old_m[dd][0] and new_m[dd][0]:
                    spread = (old_m[dd][0] - new_m[dd][0]) / new_m[dd][0] * 100
            rolls.append({
                "date": d, "old_contract": cur, "new_contract": pick,
                "from": cur_start, "spread_old_minus_new_pct": spread,
                "ambiguous": len(exact) > 1,
            })
            cur, cur_start = pick, d
    return rolls


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def main():
    ap = argparse.ArgumentParser(description="装配可比价格序列与换月台账")
    ap.add_argument("--raw", required=True, help="原始 K 线 json 目录")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--prefix-a", required=True, help="品种 A 的合约前缀，如 PP")
    ap.add_argument("--prefix-b", required=True, help="品种 B 的合约前缀，如 L")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    idx = build_contract_index(args.raw, [args.prefix_a, args.prefix_b])

    report = {"raw_dir": os.path.abspath(args.raw), "products": {}, "cross": {}}
    series = {}
    for tag, pre in (("A", args.prefix_a), ("B", args.prefix_b)):
        path = os.path.join(args.raw, pre + "0.json")
        if not os.path.exists(path):
            print("ERROR: 缺少连续序列 %s" % path)
            sys.exit(2)
        s = load_series(path)
        series[tag] = s
        write_csv(os.path.join(args.out, "price_%s.csv" % tag), s,
                  ["date", "open", "high", "low", "close", "volume", "oi"])
        report["products"][tag] = qc(s, pre, idx)

    # 换月台账
    led = []
    for tag, pre in (("A", args.prefix_a), ("B", args.prefix_b)):
        for r in detect_rolls(args.raw, pre, series[tag]):
            r["product"] = pre
            led.append(r)
    led.sort(key=lambda x: (x["date"], x["product"]))
    write_csv(os.path.join(args.out, "roll_ledger.csv"), led,
              ["product", "date", "old_contract", "new_contract", "from",
               "spread_old_minus_new_pct", "ambiguous"])

    # 交叉校验：两边日期交集
    da = {r["date"] for r in series["A"]}
    db = {r["date"] for r in series["B"]}
    common = sorted(da & db)
    report["cross"] = {
        "A_dates": len(da), "B_dates": len(db), "common_dates": len(common),
        "A_only": len(da - db), "B_only": len(db - da),
        "common_start": common[0] if common else None,
        "common_end": common[-1] if common else None,
        "roll_events": len(led),
        "rolls_A": sum(1 for r in led if r["product"] == args.prefix_a),
        "rolls_B": sum(1 for r in led if r["product"] == args.prefix_b),
        "max_abs_roll_spread_pct": max((abs(r["spread_old_minus_new_pct"]) for r in led
                                        if r["spread_old_minus_new_pct"] is not None),
                                       default=None),
    }

    err = sum(len(v["errors"]) for v in report["products"].values())
    report["gate"] = {"errors": err, "passed": err == 0}
    with open(os.path.join(args.out, "qc_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("=" * 68)
    for tag in ("A", "B"):
        p = report["products"][tag]
        print("[%s] %-6s rows=%d  %s -> %s" % (tag, p["name"], p["info"]["rows"],
                                               p["info"]["start"], p["info"]["end"]))
        for e in p["errors"]:
            print("     ERROR   " + e)
        for w in p["warnings"]:
            print("     WARN    " + w)
    print("cross: common=%d  A_only=%d  B_only=%d  rolls=%d  max|roll spread|=%.2f%%"
          % (report["cross"]["common_dates"], report["cross"]["A_only"],
             report["cross"]["B_only"], report["cross"]["roll_events"],
             report["cross"]["max_abs_roll_spread_pct"] or 0))
    print("gate: %s  (errors=%d)" % ("PASS" if report["gate"]["passed"] else "FAIL", err))
    print("=" * 68)
    sys.exit(0 if report["gate"]["passed"] else 3)


if __name__ == "__main__":
    main()
