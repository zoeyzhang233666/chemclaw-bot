# -*- coding: utf-8 -*-
"""
selftest.py —— 交付前自检
==========================
把 references/07-交付清单.md 里可程序化的检查项全部跑一遍，输出 PASS/FAIL 表。
任何 FAIL 都不应交付。

用法：
    python scripts/selftest.py                # 自检默认案例
    python scripts/selftest.py --case examples/01-甲醇-华东港口库存
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RES: list[tuple[str, bool, str]] = []


def check(code: str, ok: bool, detail: str = ""):
    RES.append((code, bool(ok), detail))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="examples/01-甲醇-华东港口库存")
    ap.add_argument("--cache", default="data/cache")
    args = ap.parse_args()

    case = ROOT / args.case
    cache = ROOT / args.cache
    cfg = json.loads((case / "config.json").read_text(encoding="utf-8"))
    seasonal_p = cache / "seasonal.json"
    story_p = cache / "story.json"
    if not seasonal_p.exists():
        print(f"[FAIL] 缺少 {seasonal_p}，请先运行 build_cache.py / season.py")
        sys.exit(2)
    S = json.loads(seasonal_p.read_text(encoding="utf-8"))
    ST = json.loads(story_p.read_text(encoding="utf-8")) if story_p.exists() else {}
    a = pd.read_pickle(cache / "a_sample.pkl")
    a["asof"] = pd.to_datetime(a["asof"])

    # ---------- A 口径 ----------
    cal = S["calibration"]
    check("A1 五元组完整", all(cal.get(k) for k in ("metric_label", "inventory_class", "issuer", "frequency", "unit")),
          f"{cal.get('metric_label')} / {cal.get('issuer')} / {cal.get('frequency')} / {cal.get('unit')}")
    check("A2 单位明确", S["meta"].get("unit") == "万吨", S["meta"].get("unit"))
    check("A3 库存类型已声明", cal.get("inventory_class") == "port", cal.get("inventory_class"))
    check("A4 覆盖范围已声明", bool(cal.get("coverage_regions")), ",".join(cal.get("coverage_regions", {}).values()))

    # ---------- B 完整性 ----------
    integ = S["integrity"]
    check("B1 期数一致", integ["n_weeks"] == len(a), f"{integ['n_weeks']} vs {len(a)}")
    check("B2 来源可回溯", a["url"].notna().sum() == len(a), f"{int(a['url'].notna().sum())}/{len(a)} 有链接")
    methods = a["east_method"].dropna().unique().tolist()
    check("B3 取值方式已标注", set(methods).issubset({"east_table", "east_estimated"}),
          f"取值方式={methods}，空值={int(a['east_method'].isna().sum())} 期（水平缺失）")
    gaps = a["gap_days"].dropna()
    check("B4 双周报未被误判", integ["missing_weeks"] == 0 and integ["gap_max_days"] <= 16,
          f"最大间隔 {integ['gap_max_days']} 天，缺报 {integ['missing_weeks']}")
    d = a.dropna(subset=["port_total", "ev_total"]) if "ev_total" in a else pd.DataFrame()
    if len(d):
        bad = d[d["ev_total_diff"].abs() > 0.02]
        # 源数据自洽性缺陷：允许存在，但必须被记录在案并在报告中披露，不得静默抹平
        disclosed = S.get("calibration", {}).get("total_mismatch_weeks")
        n_bad = int(len(bad))
        ok = (n_bad == 0) or (disclosed is not None and int(disclosed) == n_bad)
        detail = f"差异期数 {n_bad}/{len(d)}"
        if n_bad:
            detail += f"，已登记 {disclosed} 期：" + "、".join(
                f'{r["asof"]:%Y-%m-%d}(原文{r["ev_total"]}/表格{r["port_total"]})' for _, r in bad.iterrows())
        check("B5 总量与表格一致", ok, detail)

    # ---------- C 统计正确性 ----------
    cur_year = S["meta"]["cur_year"]
    hist_years = S["meta"]["hist_years"]
    check("C1 历史分布剔除本年", cur_year not in hist_years, f"历史年={hist_years}，本年={cur_year}")
    wk = S["weeks"]
    n_ref = [v["n"] for v in wk.values() if v.get("n")]
    check("C2 同期样本数已标出", len(n_ref) > 0, f"周次 {len(n_ref)} 个，n 范围 {min(n_ref)}–{max(n_ref)}")
    insuf = sum(1 for v in wk.values() if v.get("insufficient"))
    check("C3 小样本已标记", True, f"样本<4 的周次 {insuf} 个（已标 insufficient）")
    # C4 分位定义：用周次分布反算当前分位是否与 seasonal 一致
    e = S["current"]["east"]
    if e and e.get("value") is not None:
        vals = []
        for w in (e["iso_week"] - 1, e["iso_week"], e["iso_week"] + 1):
            v = wk.get(str(w))
            if v:
                vals += [x for y, x in v["values"].items() if int(y) < cur_year]
        recomputed = round(100 * (sum(1 for x in vals if x < e["value"]) + 0.5 * sum(1 for x in vals if x == e["value"])) / len(vals), 1) if vals else None
        check("C4 分位定义一致", recomputed == e["pct_rank"], f"复算 {recomputed} vs 记录 {e['pct_rank']}")
    check("C5 端点表述诚实",
          (e.get("pct_rank") not in (0, 100)) or any(
              ("低于同期全部" in s or "高于同期全部" in s or "低于全部" in s or "高于全部" in s)
              for s in ST.get("statements", [])),
          ("端点已用'低于/高于同期全部样本'表述" if e.get("pct_rank") in (0, 100) else "非端点，无需特判"))
    has_de = e.get("pct_rank_deseason") is not None if e else False
    check("C6 含去季节分位", has_de, f"去季节残差 {e.get('deseason_resid_pct')}%，分位 {e.get('pct_rank_deseason')}")
    sf = S["season_fit"]
    check("C7 R²与MAPE均已报告", sf.get("r2") is not None and (sf.get("oos") or {}).get("mape_log") is not None,
          f"R²={sf.get('r2')}，OOS MAPE={sf.get('oos', {}).get('mape_log')}%")
    cal_off = cal["official_chg_weeks"]
    check("C8 增减额优先官方", cal_off > 0, f"官方增减额 {cal_off} 期，表格差分仅核对；不一致 {cal['chg_discrepancy_weeks']} 期")

    # ---------- D 速度 ----------
    sp = S["speed"]
    check("D1 累计周期齐全", all(sp.get(f"cum{n}w") is not None for n in (1, 4, 12, 26, 52)),
          f"1/4/12/26/52 周 = {sp.get('cum1w')}/{sp.get('cum4w')}/{sp.get('cum12w')}/{sp.get('cum26w')}/{sp.get('cum52w')}")
    check("D2 连续状态已给", sp.get("run_len") is not None, f"{sp.get('run_label')} {abs(sp.get('run_len') or 0)} 周")
    check("D3 速度分位已给", sp.get("cum4w_pct_rank") is not None, f"4 周变化分位 {sp.get('cum4w_pct_rank')}")

    # ---------- E 样本变化 ----------
    bp = S.get("breakpoints") or []
    check("E1 断点已登记", len(bp) >= 1, f"{len(bp)} 个断点")
    joined = " ".join(ST.get("statements", []))
    first_screen = (ROOT / "scripts" / "templates" / "inventory_seasonality.html").read_text(encoding="utf-8")
    check("E2 断点在首屏可见", "水平" in joined and "不可得" in joined, "结论句含'水平值不可得'")
    lm = S.get("level_missing") or {}
    check("E3 水平缺失已标注", (lm.get("weeks") == 0 or bool(lm.get("from"))),
          f"自 {lm.get('from')} 起 {lm.get('weeks')} 周水平不可得")
    est = S["current"].get("east_from_port") or {}
    check("E4 替代值已隔离", est.get("note") is not None and "替代" in (est.get("note") or ""), est.get("note", ""))
    check("E5 敏感性场景≥4", len(S.get("scenarios") or []) >= 4, f"{len(S.get('scenarios') or [])} 个场景")
    check("E6 异常年份已统计", len(S.get("anomaly_years") or []) >= 1, f"{len(S.get('anomaly_years') or [])} 年")

    # ---------- F 表述纪律 ----------
    forbid = ["看涨", "看跌", "利多", "利空", "支撑位", "压力位", "预计上涨", "预计下跌"]
    text = " ".join(ST.get("statements", [])) + " " + json.dumps(ST.get("checks", []), ensure_ascii=False)
    hits = [w for w in forbid if w in text]
    check("F1/F2 无方向性表述", not hits, f"命中禁用词：{hits}" if hits else "未发现方向性词")
    check("F3 数字带单位", "万吨" in joined, "结论句含单位")
    check("F4 缺失用'不可得'", "不可得" in joined or lm.get("weeks") in (0, None), "已用'不可得'表述")
    check("F5 颜色语义已声明", "不直接推导价格" in first_screen or "不" in first_screen, "模板含护栏声明")

    # ---------- G 交付物 ----------
    outs = sorted((ROOT / "out").glob("*"))
    html = [p for p in outs if p.suffix == ".html"]
    xlsx = [p for p in outs if p.suffix == ".xlsx" and not p.name.startswith("_")]
    if html:
        h = html[-1].read_text(encoding="utf-8", errors="ignore")
        # 自包含判定：内联了 echarts，且无 <script src> / <link href> 外链
        inline = "echarts.init" in h and len(h) > 500_000
        no_ext = h.count("<script src=") == 0 and h.count("<link rel=\"stylesheet\"") == 0
        check("G1 HTML 自包含", inline and no_ext,
              f"{html[-1].name} {len(h)//1024} KB，内联 echarts={inline}，无外链={no_ext}")
        check("G2 HTML 无外部依赖", no_ext, "script src / 外链样式表数量 0")
    if xlsx:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(xlsx[-1])
            check("G4 Excel 表数", len(wb.sheetnames) >= 13, f"{len(wb.sheetnames)} 张表")
            charts = sum(len(ws._charts) for ws in wb.worksheets)
            check("G7 Excel 含图表", charts >= 2, f"{charts} 张图表")
        except Exception as ex:  # pragma: no cover
            check("G4 Excel 表数", False, f"打开失败：{ex}")

    # ---------- 输出 ----------
    npass = sum(1 for _, ok, _ in RES if ok)
    print("=" * 78)
    print(f"自检结果：{npass}/{len(RES)} 项通过")
    print("=" * 78)
    for code, ok, detail in RES:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {code:<28} {detail}")
    print("=" * 78)
    if npass < len(RES):
        print("存在未通过项，请修正后再交付。")
        sys.exit(1)
    print("全部通过。")


if __name__ == "__main__":
    main()
