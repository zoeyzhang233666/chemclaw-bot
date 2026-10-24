#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all.py — 一条命令跑完全流程：校验 → 覆盖率 → HTML → XLSX →（可选）浏览器自检

用法：
    python tools/run_all.py --data-dir examples/sbs/data --out-dir out
    python tools/run_all.py --data-dir examples/sbs/data --out-dir out --verify
    python tools/run_all.py --data-dir examples/sbs/data --out-dir out --title "SBS 产业链知识图谱"
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def run(cmd, label):
    print("\n" + "=" * 74)
    print("▶ " + label)
    print("=" * 74)
    p = subprocess.run([sys.executable] + cmd, cwd=os.path.dirname(HERE))
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--verify", action="store_true", help="额外跑 Playwright 34 项交互断言")
    ap.add_argument("--strict", action="store_true", help="WARN 也视为失败")
    args = ap.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    chain_id = "chain"
    try:
        with open(os.path.join(data_dir, "meta.json"), encoding="utf-8") as f:
            m = json.load(f)
        chain_id = m.get("chain_id") or m.get("product_name") or "chain"
        chain_id = "".join(c for c in str(chain_id) if c.isalnum() or c in "-_") or "chain"
    except Exception:  # noqa: BLE001
        pass

    html_out = os.path.join(out_dir, "%s_chain.html" % chain_id)
    xlsx_out = os.path.join(out_dir, "%s_chain.xlsx" % chain_id)
    title = args.title or "%s 产业链知识图谱" % chain_id
    json_out = os.path.join(out_dir, "%s_report.json" % chain_id)

    steps = []
    vcmd = [os.path.join(HERE, "validate_chain.py"), "--data-dir", data_dir, "--out-json", json_out]
    if args.strict:
        vcmd.append("--strict")
    steps.append(("0/4 JSON 契约（schema）校验",
                  [os.path.join(HERE, "check_schema.py"), "--data-dir", data_dir]))
    steps.append(("1/4 校验数据与覆盖完整度", vcmd))
    steps.append(("2/4 生成交互式 HTML", [os.path.join(HERE, "build_chain_html.py"),
                                     "--data-dir", data_dir, "--out", html_out, "--title", title]))
    steps.append(("3/4 生成 Excel 工作簿", [os.path.join(HERE, "build_chain_xlsx.py"),
                                       "--data-dir", data_dir, "--out", xlsx_out]))

    rc = 0
    for label, cmd in steps:
        if run(cmd, label) != 0:
            rc = 1
            if "校验" in label:
                print("\n✗ 校验未通过，后续生成中止。请先修 FATAL / schema 问题。")
                return 1

    if args.verify:
        vh = os.path.join(HERE, "verify_html.py")
        if os.path.exists(vh):
            r = run([vh, html_out], "4/4 浏览器交互自检（34 项断言）")
            rc = rc or r
        else:
            print("\n（跳过浏览器自检：未找到 verify_html.py）")

    print("\n" + "=" * 74)
    print("交付物")
    print("=" * 74)
    for f in (html_out, xlsx_out, json_out):
        if os.path.exists(f):
            print("  ✓ %-56s %8.1f KB" % (os.path.basename(f), os.path.getsize(f) / 1024.0))
    print("\n结果：%s" % ("全部通过" if rc == 0 else "存在问题，请看上文"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
