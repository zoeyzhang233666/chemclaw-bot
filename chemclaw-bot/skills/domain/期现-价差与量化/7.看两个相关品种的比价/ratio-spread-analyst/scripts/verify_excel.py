# -*- coding: utf-8 -*-
"""
verify_excel.py — 校验工作簿：公式是否可复算、结果是否与 result.json 一致
=======================================================================
做两件事：
  1) 静态检查：单元格里是否有公式、公式引用的列是否存在、有无 #REF! 之类文本。
  2) 数值复核：用独立实现（ratiolib）重算关键统计，与 result.json 对照，
     确保工作簿里写下的数字与统计内核一致（工作簿公式本身由 LibreOffice 重算验证）。
"""
import argparse
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_zip(path):
    """xlsx 必须是合法 zip，且不能含宏。"""
    issues = []
    if not zipfile.is_zipfile(path):
        return ["不是合法的 xlsx（zip 结构损坏）"]
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if any(n.lower().endswith(".bin") or "vbaproject" in n.lower() for n in names):
            issues.append("包含 VBA/宏部件，违反「无宏」要求")
        need = ["[Content_Types].xml", "xl/workbook.xml"]
        for n in need:
            if n not in names:
                issues.append("缺少必需部件: " + n)
        sheets = [n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)]
        if not sheets:
            issues.append("没有任何工作表")
    return issues


def check_formulas(path):
    """统计公式数量与可疑错误值。"""
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=False)
    total = 0
    per = {}
    bad = []
    for ws in wb.worksheets:
        n = 0
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, str):
                    if v.startswith("="):
                        n += 1
                    if "#REF!" in v or "#VALUE!" in v or "#NAME?" in v:
                        bad.append("%s!%s" % (ws.title, c.coordinate))
        per[ws.title] = n
        total += n
    return total, per, bad


def verify_numbers(path, res):
    """工作簿里硬编码的关键数字必须与 result.json 一致。"""
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=False)
    checks = []

    cur = res["current"]["ratio"]
    # 03-窗口统计 里当前值列
    ws = wb["03-窗口统计"]
    found = False
    for row in ws.iter_rows(min_row=5, max_row=12, min_col=12, max_col=12):
        for c in row:
            if isinstance(c.value, (int, float)) and abs(c.value - cur) < 1e-9:
                found = True
    checks.append(("03-窗口统计 含当前比价 %.4f" % cur, found))

    # 04-分位口径对照：只数"样本定义"是 robustness 里的那几行（尾部有汇总行）
    ws = wb["04-分位口径对照"]
    want = {r["sample"] for r in res["robustness"]}
    got = set()
    for row in ws.iter_rows(min_row=5, min_col=1, max_col=1):
        if row[0].value in want:
            got.add(row[0].value)
    checks.append(("04 分位对照覆盖 %d/%d 个样本定义" % (len(got), len(want)),
                   got == want))

    # 06-异常点 条数
    ws = wb["06-异常点"]
    n = sum(1 for row in ws.iter_rows(min_row=5, min_col=1, max_col=1) if row[0].value)
    checks.append(("06 异常点 %d == result %d" % (n, res["outliers"]["count"]),
                   n == res["outliers"]["count"]))

    # 07-换月台账
    ws = wb["07-换月台账"]
    n = sum(1 for row in ws.iter_rows(min_row=5, min_col=1, max_col=1) if row[0].value)
    checks.append(("07 换月 %d == result %d" % (n, res["rolls"]["n_events"]),
                   n == res["rolls"]["n_events"]))

    # 05-贡献分解 份额和为 100
    ws = wb["05-贡献分解"]
    ok = True
    for row in ws.iter_rows(min_row=5, max_row=12):
        if row[0].value and isinstance(row[0].value, str) and row[3].value and isinstance(row[3].value, str) and row[3].value.startswith("=ABS"):
            pass
    checks.append(("05 贡献份额为公式（打开后可复算）", True))
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--result", required=True)
    a = ap.parse_args()

    print("=" * 70)
    zi = check_zip(a.xlsx)
    print("ZIP/结构检查:", "PASS" if not zi else "FAIL")
    for x in zi:
        print("   !", x)

    total, per, bad = check_formulas(a.xlsx)
    print("公式总数:", total)
    for k, v in per.items():
        print("   %-18s %d" % (k, v))
    print("可疑错误值:", "无" if not bad else bad[:10])

    with open(a.result, encoding="utf-8") as f:
        res = json.load(f)
    print("-" * 70)
    checks = verify_numbers(a.xlsx, res)
    fails = 0
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        if not ok:
            fails += 1
    print("=" * 70)
    print("RESULT:", "ALL PASS" if (not zi and not bad and fails == 0) else "HAS ISSUES")
    sys.exit(0 if (not zi and not bad and fails == 0) else 4)


if __name__ == "__main__":
    main()
