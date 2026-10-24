# -*- coding: utf-8 -*-
"""
build_html.py — 生成自包含交互式比价分析页
===========================================
一条命令：
    python scripts/build_html.py --result build/result.json \
        --result-ba build/result_BA.json --events build/events.csv \
        --meta build/meta.json --out build/report.html

设计要点
--------
* 单文件 HTML，零外部依赖（不引 CDN），离线可开。
* 首屏：当前比价 / 历史分位 / 近期变化；A/B ↔ B/A 一键切换。
* 下文：比价历史曲线（可叠加滚动分位与滚动均值）、分布直方图、两边价格对照、
  贡献分解、滚动分位、极端阶段（点击看当时的产业背景）、稳健性、结论与限制。
* 所有数值来自 result.json，页面只做呈现与窗口内重算，不另造数。
"""
import argparse
import csv
import json
import os
import sys


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_events(p):
    if not p or not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out.append(r)
    return out


def build(result_ab, result_ba, events, meta, title, subtitle):
    payload = {
        "AB": result_ab,
        "BA": result_ba,
        "events": events,
        "meta": meta,
        "title": title,
        "subtitle": subtitle,
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "templates", "ratio-report-template.html")
    with open(tpl, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DATA__*/null", data)
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    ap.add_argument("--result-ba", default=None)
    ap.add_argument("--events", default=None)
    ap.add_argument("--meta", default=None)
    ap.add_argument("--title", default="两个相关品种比价分析")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    rab = load_json(a.result)
    rba = load_json(a.result_ba) if a.result_ba and os.path.exists(a.result_ba) else rab
    ev = load_events(a.events)
    meta = load_json(a.meta) if a.meta and os.path.exists(a.meta) else {}
    html = build(rab, rba, ev, meta, a.title, a.subtitle)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("written:", a.out, "%.0f KB" % (len(html.encode("utf-8")) / 1024))


if __name__ == "__main__":
    main()
