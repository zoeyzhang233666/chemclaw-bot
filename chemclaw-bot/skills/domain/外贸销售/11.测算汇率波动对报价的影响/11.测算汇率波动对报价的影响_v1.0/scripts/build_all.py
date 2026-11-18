# -*- coding: utf-8 -*-
"""build_all.py —— 一键重建并校验全部交付物

用法:
    python scripts/build_all.py examples/01-export-soda-ash-usd/case.json
    python scripts/build_all.py <case.json> --skip-excel-verify

做：
  1. run_case        case.json → build/scenario.json
  2. build_html      → build/*.html
  3. build_xlsx      → build/*.xlsx
  4. check_workbook_static（Excel 结构与公式）
  5. qa_render.mjs（37 项渲染与交互 + 截图）
  6. visual_audit.mjs（布局/对比度）
  7. verify_formulas_com（Excel 引擎真算，可跳过）

任一步失败 → 汇总报告，退出码 1。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
PY = sys.executable


def find_node():
    cands = [
        os.environ.get("NODE"),
        (__import__('shutil').which('node') or 'node'),
        "node", "node.exe",
    ]
    for c in cands:
        if not c:
            continue
        try:
            subprocess.run([c, "--version"], capture_output=True, timeout=15, check=True)
            return c
        except Exception:
            continue
    return None


def run(cmd, label, timeout=900):
    t0 = time.time()
    print(f"\n{'=' * 66}\n▶ {label}\n{'=' * 66}")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, cwd=ROOT)
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {label}")
        return False, f"{label}: 超时"
    out = (p.stdout or "") + (p.stderr or "")
    tail = out.strip().splitlines()
    for line in tail[-40:]:
        print(line)
    print(f"（耗时 {time.time() - t0:.1f}s）")
    if p.returncode != 0:
        return False, f"{label}: 退出码 {p.returncode}"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--skip-excel-verify", action="store_true")
    ap.add_argument("--skip-render", action="store_true")
    a = ap.parse_args()

    case_path = os.path.abspath(a.case)
    case_dir = os.path.dirname(case_path)
    slug = json.load(open(case_path, encoding="utf-8")).get("case_id") or os.path.basename(case_dir)
    build_dir = os.path.join(case_dir, "build")
    shots_dir = os.path.join(case_dir, "shots")
    os.makedirs(build_dir, exist_ok=True)

    scen = os.path.join(build_dir, "scenario.json")
    fx = os.path.join(ROOT, "build", "fx_series.json")

    failures = []
    ok, msg = run([PY, os.path.join(SCRIPTS, "run_case.py"), case_path], "① 计算：case.json → scenario.json")
    if not ok:
        print(f"\n✗ 计算失败，终止：{msg}")
        return 1

    meta = json.load(open(scen, encoding="utf-8"))["meta"]
    base_name = meta.get("output_basename")
    if not base_name:
        # 默认命名：汇率风险测算_<产品>_<金额>万美元出口_<日期>
        amt = meta.get("amount_fx") or 0
        cur = meta.get("currency") or ""
        if cur in ("USD", "EUR", "GBP", "AUD", "NZD", "SGD", "CHF", "CAD", "HKD"):
            unit = {"USD": "万美元", "EUR": "万欧元", "GBP": "万英镑", "AUD": "万澳元",
                    "NZD": "万新西兰元", "SGD": "万新元", "CHF": "万瑞郎", "CAD": "万加元",
                    "HKD": "万港元"}[cur]
            amt_s = f"{amt/10000:.0f}{unit}" if amt >= 10000 else f"{amt:.0f}{cur}"
        else:
            amt_s = f"{amt:,.0f}{cur}"
        dir_s = "出口" if meta.get("direction") == "export" else "进口"
        asof = (meta.get("asof") or "").replace("-", "")
        base_name = f"汇率风险测算_{meta.get('product') or slug}_{amt_s}{dir_s}_{asof}"
    base_name = re.sub(r'[\\/:*?"<>|]', "_", base_name)
    html_path = os.path.join(build_dir, base_name + ".html")
    xlsx_path = os.path.join(build_dir, base_name + ".xlsx")

    ok, msg = run([PY, os.path.join(SCRIPTS, "build_html.py"), "--scenario", scen, "--out", html_path],
                  "② 生成 HTML 测算台")
    if not ok:
        failures.append(msg)

    ok, msg = run([PY, os.path.join(SCRIPTS, "build_xlsx.py"), "--scenario", scen, "--out", xlsx_path],
                  "③ 生成 Excel 工作簿")
    if not ok:
        failures.append(msg)

    if os.path.exists(xlsx_path):
        ok, msg = run([PY, os.path.join(SCRIPTS, "check_workbook_static.py"), xlsx_path, scen, fx],
                      "④ Excel 结构与公式静态检查")
        if not ok:
            failures.append(msg)

    if os.path.exists(xlsx_path) and os.path.exists(html_path):
        ok, msg = run([PY, os.path.join(SCRIPTS, "verify.py"), scen, xlsx_path, html_path],
                      "④b 三方一致性校验（引擎 / Excel / HTML）")
        if not ok:
            failures.append(msg)

    ok, msg = run([PY, os.path.join(SCRIPTS, "audit_html.py"), html_path],
                  "④c 成品 HTML 审计（外链 / 禁用词 / 声明）")
    if not ok:
        failures.append(msg)

    node = find_node()
    if node and os.path.exists(html_path) and not a.skip_render:
        ok, msg = run([node, os.path.join(SCRIPTS, "qa_render.mjs"), html_path,
                       "--shots", shots_dir, "--json", os.path.join(build_dir, "qa.json")],
                      "⑤ HTML 渲染与交互自检（37 项 + 截图）")
        if not ok:
            failures.append(msg)

        ok, msg = run([node, os.path.join(SCRIPTS, "visual_audit.mjs"), html_path,
                       "--json", os.path.join(build_dir, "visual_audit.json")],
                      "⑥ 视觉审计（重叠/截断/对比度/字号）")
        if not ok:
            failures.append(msg)
    elif not node:
        print("\n[SKIP] 未找到 Node，跳过渲染检查")

    if os.path.exists(xlsx_path) and not a.skip_excel_verify:
        ok, msg = run([PY, os.path.join(SCRIPTS, "verify_formulas_com.py"), xlsx_path, scen, fx],
                      "⑦ Excel 计算引擎真机验算")
        if not ok:
            failures.append(msg)

    print("\n" + "=" * 66)
    if failures:
        print(f"✗ 有 {len(failures)} 项未通过：")
        for f in failures:
            print("   -", f)
        return 1
    print("✓ 全部通过")
    print(f"  HTML : {html_path}")
    print(f"  XLSX : {xlsx_path}")
    print(f"  截图 : {shots_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
