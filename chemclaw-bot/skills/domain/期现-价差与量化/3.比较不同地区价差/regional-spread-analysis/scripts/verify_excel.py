#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_excel.py — 用真实计算引擎重算工作簿，再与 result.json 对账。

流程：
  1) 调 LibreOffice Kit recalculate 得到带缓存值的副本（openpyxl 自身不算公式）
  2) 用 openpyxl(data_only=True) 读回计算结果
  3) 逐项比：价差矩阵、当前价差、分位、运费调整、产能小计、下游合计
  4) 断言：无 #REF!/#NAME?/#VALUE! 等错误值；差异 < 0.01

用法：
  python scripts/verify_excel.py --xlsx build/workbook.xlsx --result build/result.json
"""
from __future__ import annotations

_CHEMCLAW_ROOT = next(parent for parent in __import__('pathlib').Path(__file__).resolve().parents if (parent / 'runtime/deliver.mjs').is_file())

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

from openpyxl import load_workbook

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

NODE = __import__('sys').executable
CLI = str(_CHEMCLAW_ROOT / 'runtime/office-cli.py')
ERRVALS = ("#REF!", "#NAME?", "#VALUE!", "#DIV/0!", "#N/A", "#NUM!", "#NULL!", "Err:")


def find_node():
    cands = [NODE]
    for base in (str(_CHEMCLAW_ROOT / 'runtime'),
                 str(_CHEMCLAW_ROOT / 'runtime')):
        cands.extend(glob.glob(os.path.join(base, "**", "node.exe"), recursive=False))
    for c in cands:
        if os.path.exists(c):
            return c
    return shutil.which("node")


def recalc(src, dst):
    node = find_node()
    if not node or not os.path.exists(CLI):
        return False, "找不到 LibreOffice Kit（node/cli），无法重算"
    try:
        p = subprocess.run([node, CLI, "recalculate", "--input", src, "--output", dst],
                           capture_output=True, text=True, timeout=300)
    except Exception as e:
        return False, f"重算失败: {e}"
    if p.returncode != 0 or not os.path.exists(dst):
        return False, f"重算失败: {(p.stderr or p.stdout)[:400]}"
    return True, (p.stdout or "").strip()[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="build/workbook.xlsx")
    ap.add_argument("--result", default="build/result.json")
    a = ap.parse_args()

    R = json.load(open(a.result, encoding="utf-8"))
    PR = R["primary"]
    ORDER = PR["region_order"]
    NAME = {r["id"]: r["name"] for r in R["meta"]["regions"]}

    calc_path = os.path.join(os.path.dirname(a.xlsx) or ".", f"_recalc_{os.getpid()}.xlsx")
    if os.path.exists(calc_path):
        try:
            os.remove(calc_path)
        except Exception:
            pass
    ok, msg = recalc(a.xlsx, calc_path)
    fails, passes = [], []

    def chk(name, cond, detail=""):
        (passes if cond else fails).append(name)
        print(("  [PASS] " if cond else "  [FAIL] ") + name + ((" " + str(detail)) if detail else ""))

    print(f"重算引擎: {'LibreOffice Kit' if ok else '不可用'}")
    if not ok:
        print("  " + msg)
        # 降级：只做结构检查
        wb = load_workbook(a.xlsx, data_only=False)
        chk("工作簿可打开", True, f"{len(wb.worksheets)} 张表")
        nf = sum(1 for ws in wb.worksheets for row in ws.iter_rows() for c in row
                 if isinstance(c.value, str) and c.value.startswith("="))
        chk("含原生公式", nf > 500, f"{nf} 个公式单元格")
        print("\n无法重算，仅完成结构检查。")
        return 1

    wbv = load_workbook(calc_path, data_only=True)
    wbf = load_workbook(a.xlsx, data_only=False)

    # 1. 错误值扫描
    errs = []
    for ws in wbv.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and any(c.value.startswith(e) for e in ERRVALS):
                    errs.append(f"{ws.title}!{c.coordinate}={c.value}")
    chk("全簿无公式错误值", not errs, f"{len(errs)} 处 {errs[:5]}")

    # 2. 公式数量
    nf = sum(1 for ws in wbf.worksheets for row in ws.iter_rows() for c in row
             if isinstance(c.value, str) and c.value.startswith("="))
    chk("公式为原生公式（非硬编码）", nf > 500, f"{nf} 个")

    # 3. 价差矩阵
    ws = wbv["05 价差矩阵"]
    mx = PR["matrix"]["values"]
    for i, A in enumerate(ORDER):
        for j, B in enumerate(ORDER):
            if A == B:
                continue
            v = ws.cell(row=4 + i, column=2 + j).value
            exp = mx.get(f"{A}|{B}")
            good = isinstance(v, (int, float)) and exp is not None and abs(v - exp) < 0.01
            chk(f"矩阵 {A}−{B}", good, f"XL={v} PY={exp}")

    # 4. 06 历史分位：当前值 & 1y/3y 分位
    ws = wbv["06 历史分位"]
    windows = R["meta"]["windows"]
    for idx, rec in enumerate(PR["percentiles"]):
        if not rec.get("n_total"):
            continue
        row = 4 + idx
        cur = ws.cell(row=row, column=4).value
        chk(f"分位表 {rec['pair']} 当前值", isinstance(cur, (int, float)) and abs(cur - rec["current"]) < 0.01,
            f"XL={cur} PY={rec['current']}")
        for ci, w in ((5, "1y"), (7, "3y")):
            xv = ws.cell(row=row, column=ci).value
            pv = rec["windows"][w]["pct"]
            good = (xv is None and pv is None) or (isinstance(xv, (int, float)) and pv is not None and abs(xv - pv) < 0.15)
            chk(f"分位表 {rec['pair']} {w} 分位", good, f"XL={xv} PY={pv}")

    # 5. 10 运费调整：综合运费 / 扣费后参考差异
    ws = wbv["10 运费调整"]
    fr = PR["freight"]["routes"]
    # 找到表头行
    hdr_row = None
    for rr in range(1, 30):
        if ws.cell(row=rr, column=1).value == "路线":
            hdr_row = rr
            break
    if hdr_row:
        for i, rt in enumerate(fr):
            row = hdr_row + 1 + i
            py = rt.get("result") or {}
            k = ws.cell(row=row, column=11).value
            m = ws.cell(row=row, column=13).value
            if py.get("ok"):
                chk(f"运费 {rt['route']} 综合运费", isinstance(k, (int, float)) and abs(k - py["freight_total"]) < 0.01,
                    f"XL={k} PY={py['freight_total']}")
                chk(f"运费 {rt['route']} 参考差异", isinstance(m, (int, float)) and abs(m - py["ref_diff"]) < 0.01,
                    f"XL={m} PY={py['ref_diff']}")
            else:
                chk(f"运费 {rt['route']} 缺运费时留空", m in (None, "") or not isinstance(m, (int, float)),
                    f"XL={m}")

    # 6. 11 企业产能小计
    ws = wbv["11 企业产能"]
    fund = (R.get("fundamentals", {}).get("regions") or {})
    for row in ws.iter_rows(min_row=1, max_row=60):
        label = row[1].value
        if isinstance(label, str) and label.endswith("可核实产能小计"):
            rid = next((r["id"] for r in R["meta"]["regions"] if label.startswith(r["name"])), None)
            if not rid:
                continue
            exp = sum(p.get("capacity_mt") or 0 for p in (fund.get(rid, {}) or {}).get("producers", []))
            got = row[4].value
            chk(f"{label}", isinstance(got, (int, float)) and abs(got - exp) < 0.01, f"XL={got} PY={exp}")

    # 7. 12 下游合计 = 100%
    ws = wbv["12 下游结构"]
    for row in ws.iter_rows(min_row=1, max_row=80):
        if row[1].value == "合计":
            got = row[2].value
            chk(f"{row[0].value} 下游占比合计=100%", isinstance(got, (int, float)) and abs(got - 1.0) < 0.005,
                f"XL={got}")

    # 8. 05 等价校验列
    ws = wbv["05 价差矩阵"]
    checks = [c.value for row in ws.iter_rows(min_row=8, max_row=20) for c in row
              if isinstance(c.value, str) and ("✓" in c.value or "✗" in c.value)]
    chk("矩阵等价校验全部通过", checks and all("✓" in x for x in checks), f"{checks}")

    try:
        os.remove(calc_path)
    except Exception:
        pass

    print("\n" + "=" * 62)
    print(f"通过 {len(passes)} 项，失败 {len(fails)} 项")
    if fails:
        print("失败项：", fails)
    print("=" * 62)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
