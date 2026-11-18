# -*- coding: utf-8 -*-
"""build_all.py — 一键流水线：校验 → 建价 → 事件对齐 → 统计 → Excel → HTML → 自检

用法：
    python scripts/build_all.py <项目目录> [--skip-fetch]

项目目录至少需要：
    events.csv
    data/prices.csv            或 data/raw_contracts/*.json（由本脚本调用 build_prices 生成）
    project.json               口径配置（标题、品种、期货口径等）

产物：
    build/event_results.csv, build/stats.json, build/overlap.json, build/duplicates.json
    output/<品种>_装置停车事件研究.html
    output/<品种>_装置停车事件研究_工作簿.xlsx
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core  # noqa: E402


def run(cmd):
    print("» " + " ".join(os.path.basename(str(c)) if i == 1 else str(c) for i, c in enumerate(cmd)))
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit(f"步骤失败：{' '.join(cmd)}")
    return r


def check_project(project: str) -> list:
    """跑之前先把能想到的“口径错误”拦下来。返回问题清单（空=通过）。"""
    problems = []
    evp = os.path.join(project, "events.csv")
    if not os.path.exists(evp):
        problems.append("缺 events.csv")
        return problems
    events = core.load_events_csv(evp)
    if not events:
        problems.append("events.csv 没有有效行")
    ids = [e.event_id for e in events]
    if len(set(ids)) != len(ids):
        problems.append("event_id 重复")
    for e in events:
        if not (e.first_market_date or e.actual_start_date):
            problems.append(f"{e.event_id}: 三种日期全空，无法对齐")
        if e.first_market_date and e.actual_start_date and e.first_market_date > e.actual_start_date:
            problems.append(f"{e.event_id}: 首次获知日晚于实际停车日（{e.first_market_date} > {e.actual_start_date}），请核实口径")
        if e.announce_date and e.first_market_date and e.announce_date > e.first_market_date:
            problems.append(f"{e.event_id}: 公告日晚于首次获知日，可能把媒体日当公告日")
        if e.evidence_grade not in ("E1", "E2", "E3", "E4", "E5"):
            problems.append(f"{e.event_id}: 证据等级 '{e.evidence_grade}' 不在 E1–E5")
        if e.event_type in ("unplanned", "planned") and not e.quote:
            problems.append(f"{e.event_id}: 无原文摘录，证据无法核验")
    dups = core.find_duplicates(events)
    for g in dups:
        problems.append(f"疑似重复报道组：{' / '.join(g['group'])}（需人工裁决，脚本不自动删除）")
    if not os.path.exists(os.path.join(project, "data", "prices.csv")) and \
       not os.path.isdir(os.path.join(project, "data", "raw_contracts")):
        problems.append("既没有 data/prices.csv 也没有 data/raw_contracts/")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--benchmark", default="market_model")
    ap.add_argument("--include-restart", action="store_true")
    ap.add_argument("--min-grade", default="E3")
    ap.add_argument("--windows", default="1,5,10,20")
    ap.add_argument("--strict", action="store_true", help="校验发现问题就退出（默认只警告）")
    args = ap.parse_args(argv)
    project = os.path.abspath(args.project)

    meta = {}
    mp = os.path.join(project, "project.json")
    if os.path.exists(mp):
        meta = json.load(open(mp, encoding="utf-8"))

    print("=" * 68)
    print("① 口径校验")
    problems = check_project(project)
    if problems:
        for p in problems:
            print("  [!] " + p)
        if args.strict:
            raise SystemExit("校验未通过（--strict）")
    else:
        print("  [OK] 口径校验通过")

    print("=" * 68)
    print("② 构建主力连续（如已存在 prices.csv 则跳过）")
    raw_dir = os.path.join(project, "data", "raw_contracts")
    prices_csv = os.path.join(project, "data", "prices.csv")
    if not os.path.exists(prices_csv):
        if not os.path.isdir(raw_dir):
            raise SystemExit("缺 data/prices.csv 与 data/raw_contracts/")
        run([os.path.join(HERE, "build_prices.py"), "--raw", raw_dir,
             "--out", os.path.join(project, "data"), "--prefix", meta.get("prefix", "MA")])
    else:
        print("  已存在 prices.csv，跳过")

    print("=" * 68)
    print("③ 基准（如有 data/benchmark.csv 则直接用于异常收益）")
    bpath = os.path.join(project, "data", "benchmark.csv")
    if os.path.exists(bpath):
        print(f"  [OK] 使用 {bpath}")
    else:
        print("  [--] 无基准文件：报告将不含异常收益（这是诚实的结果，不作替代）")

    print("=" * 68)
    print("④ 事件对齐与统计")
    build = core.ensure_dir(os.path.join(project, "build"))
    run([os.path.join(HERE, "eventstudy.py"), "--project", project, "--out", build,
         "--benchmark", args.benchmark, "--min-grade", args.min_grade, "--windows", args.windows]
        + (["--include-restart"] if args.include_restart else []))

    print("=" * 68)
    print("⑤ Excel")
    outdir = core.ensure_dir(os.path.join(project, "output"))
    name = meta.get("slug", os.path.basename(project))
    xlsx = os.path.join(outdir, f"{name}_工作簿.xlsx")
    run([os.path.join(HERE, "build_excel.py"), "--project", project, "--out", xlsx])

    print("=" * 68)
    print("⑥ HTML 报告")
    html = os.path.join(outdir, f"{name}_报告.html")
    run([os.path.join(HERE, "build_html.py"), "--project", project, "--out", html,
         "--title", meta.get("title", "化工装置停车事件研究")])

    print("=" * 68)
    print("⑦ 自检")
    run([os.path.join(HERE, "check_report.py"), "--project", project, "--html", html, "--xlsx", xlsx])
    print("\n完成：")
    print("  " + html)
    print("  " + xlsx)


if __name__ == "__main__":
    main()
