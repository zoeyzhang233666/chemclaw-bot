#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_analysis.py — 把用户的 CSV 导入为标准配置（长表 → 宽表），并做基本校验。

输入 CSV 列：date, region, price, caliber, unit, source, note
  date     YYYY-MM-DD（周度数据填该周锚点，通常是周五）
  region   地区代码，需与 config/project.json 的 regions[].id 一致
  price    数值；缺失留空（不要填 0）
  caliber  DELIVERED（送到）/ EXW（出厂）—— 决定进哪套口径
  unit     必须是 元/吨（或元/公斤，会自动换算并提示）

产物：
  <out-dir>/prices_wide_<caliber>.csv   宽表（date, SD, HB, JS）
  <out-dir>/import_report.json          导入报告（地区、期间、缺口、异常）

用法：
  python scripts/init_analysis.py --prices my.csv --config config/project.json --out-dir data
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", required=True)
    ap.add_argument("--config", default="config/project.json")
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--strict", action="store_true", help="有任何错误即退出非零")
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    regs = [r["id"] for r in cfg["regions"]]
    calibers = list((cfg.get("calibers") or {}).keys()) or ["DELIVERED"]

    rows = list(csv.DictReader(open(a.prices, encoding="utf-8-sig")))
    if not rows:
        print("CSV 为空", file=sys.stderr)
        return 1

    errors, warnings = [], []
    data = defaultdict(lambda: defaultdict(dict))   # caliber -> region -> date -> price
    seen = set()
    bad_unit = 0
    zero_count = 0

    for i, r in enumerate(rows, start=2):
        d = (r.get("date") or "").strip()
        reg = (r.get("region") or "").strip()
        cal = (r.get("caliber") or "DELIVERED").strip().upper()
        pv = (r.get("price") or "").strip()
        unit = (r.get("unit") or "元/吨").strip()

        if reg not in regs:
            errors.append(f"第{i}行: 未知地区 '{reg}'，应为 {regs} 之一")
            continue
        if cal not in calibers:
            errors.append(f"第{i}行: 未知口径 '{cal}'，应为 {calibers} 之一")
            continue
        if len(d) != 10:
            errors.append(f"第{i}行: 日期格式应为 YYYY-MM-DD，实得 '{d}'")
            continue
        if not pv:
            warnings.append(f"第{i}行: {reg} {d} 价格为空（将作为缺口剔除，这是正确做法）")
            continue
        try:
            v = float(pv)
        except ValueError:
            errors.append(f"第{i}行: 价格不是数字 '{pv}'")
            continue
        if v == 0:
            zero_count += 1
            errors.append(f"第{i}行: 价格为 0 —— 缺失必须留空，不能填 0")
            continue
        if "公斤" in unit or "/kg" in unit.lower():
            v = v * 1000
            bad_unit += 1
        elif "吨" not in unit:
            warnings.append(f"第{i}行: 单位 '{unit}' 非标准，按 元/吨 处理")
        if not (100 <= v <= 50000):
            warnings.append(f"第{i}行: {reg} {d} 价格 {v} 超出常见区间 100–50000，请确认单位")
        k = (cal, reg, d)
        if k in seen:
            errors.append(f"第{i}行: 重复记录 {cal}/{reg}/{d}")
            continue
        seen.add(k)
        data[cal][reg][d] = v

    os.makedirs(a.out_dir, exist_ok=True)
    report = {"source": a.prices, "rows": len(rows), "errors": errors,
              "warnings": warnings[:50], "n_warnings": len(warnings), "calibers": {}}

    for cal in calibers:
        if not data.get(cal):
            continue
        all_dates = sorted({d for reg in data[cal] for d in data[cal][reg]})
        out = os.path.join(a.out_dir, f"prices_wide_{cal.lower()}.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date"] + regs)
            for d in all_dates:
                w.writerow([d] + [data[cal][r].get(d, "") for r in regs])
        per_reg = {r: len(data[cal].get(r, {})) for r in regs}
        full = sum(1 for d in all_dates if all(d in data[cal].get(r, {}) for r in regs))
        report["calibers"][cal] = {
            "file": out, "dates": len(all_dates), "full_cover_dates": full,
            "per_region": per_reg,
            "start": all_dates[0] if all_dates else None,
            "end": all_dates[-1] if all_dates else None,
            "gaps": len(all_dates) - full,
        }
        print(f"[{cal}] {out}  {len(all_dates)} 个日期，三地全覆盖 {full}，缺口 {len(all_dates)-full}")
        for r in regs:
            print(f"    {r}: {per_reg[r]} 条")

    if bad_unit:
        warnings.append(f"有 {bad_unit} 条按 元/公斤 → 元/吨 换算（×1000）")
    report["warnings"] = warnings[:50]
    rp = os.path.join(a.out_dir, "import_report.json")
    json.dump(report, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\n导入报告 → {rp}")
    if errors:
        print(f"\n❌ {len(errors)} 个错误：")
        for e in errors[:20]:
            print("   " + e)
    if warnings:
        print(f"\n⚠ {len(warnings)} 个提示：")
        for w in warnings[:10]:
            print("   " + w)
    if not errors:
        print("\n✅ 导入完成，无错误。下一步：")
        print(f"   python scripts/analyze.py --csv {os.path.join(a.out_dir, 'prices_wide_delivered.csv')} ...")
    return 0 if (not errors or not a.strict) else 1


if __name__ == "__main__":
    sys.exit(main())
