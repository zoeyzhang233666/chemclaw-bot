#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_html.py — 把 build/data.json 填进模板，产出单文件离线 HTML。

零外链：ECharts 内联；不引用任何 CDN、字体、图片。
用法：
  python scripts/build_html.py build/data.json --out out/报告.html [--template ...]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "templates", "report.html")
ECHARTS = os.path.join(HERE, "assets", "echarts.min.js")


def _opts(values, current):
    out = []
    for v in values:
        sel = " selected" if v == current else ""
        out.append(f'<option value="{html.escape(v)}"{sel}>{html.escape(v)}</option>')
    return "".join(out)


def _chips(data):
    m = data.get("meta", {})
    cust = data.get("customer", {})
    chips = []
    if cust.get("is_simulated"):
        chips.append(("warn", cust.get("channel_label", "模拟输入")))
    chips.append(("", f"产品：{m.get('product','—')}"))
    chips.append(("", f"规格：{m.get('spec','—')}"))
    chips.append(("", f"地区：{m.get('region','—')}"))
    chips.append(("", f"基准日：{m.get('base_date','—')}"))
    v = data.get("verdict", {})
    chips.append(("", f"核验结论：{v.get('label','—')}"))
    return "".join(f'<span class="chip {c}">{html.escape(t)}</span>' for c, t in chips)


def build(data, out_path, template=TPL, echarts=ECHARTS):
    with open(template, "r", encoding="utf-8") as f:
        tpl = f.read()

    meta = data.get("meta", {})
    cust = data.get("customer", {})
    market = data.get("market", {})
    region = meta.get("region", "")
    title = f"{meta.get('product','')} · {region} 客户市场价核验报告"

    regions = [region] + [r.get("region") for r in data.get("data", {}).get("regions", []) if False]
    # 区域下拉：取自 region_compare + 现货里出现过的地区
    region_set = []
    for r in data.get("region_compare", []) or []:
        if r.get("region") and r["region"] not in region_set:
            region_set.append(r["region"])
    for s in data.get("spot_all", []) or []:
        rr = s.get("region")
        if rr and rr not in region_set and not rr.startswith(region):
            region_set.append(rr)
    region_options = _opts([region] + [x for x in region_set if x != region], region)

    cust_tax = C.norm_tax(cust.get("stated_tax"))
    cust_del = C.norm_delivery(cust.get("stated_delivery"))
    cust_pay = C.norm_payment(cust.get("stated_payment"))

    subs = {
        "{{TITLE}}": html.escape(title),
        "{{SUBTITLE}}": html.escape(
            f"{html.escape(region)} · {html.escape(meta.get('spec',''))} · 核验口径：客户所述价格 vs 同日同规格同税费同交付市场报价 · 报价日期 {market.get('date') or '—'}"
        ),
        "{{TOPBAR_CHIPS}}": _chips(data),
        "{{META_UNIT_SHORT}}": html.escape("（元/吨）"),
        "{{META_ASOF}}": html.escape(f"报价日期 {market.get('date') or '—'}"),
        "{{CUSTOMER_TAG_SUFFIX}}": html.escape("（模拟测试输入）" if cust.get("is_simulated") else ""),
        "{{CUSTOMER_PRICE}}": html.escape(str(cust.get("stated_price") if cust.get("stated_price") is not None else "")),
        "{{REGION_OPTIONS}}": region_options,
        "{{TAX_OPTIONS}}": _opts(["未注明", "含税", "不含税"], cust_tax),
        "{{DELIVERY_OPTIONS}}": _opts(["未注明", "出厂", "送到"], cust_del),
        "{{PAYMENT_OPTIONS}}": _opts(["未注明", "现金", "承兑"], cust_pay),
        "{{MTAX_OPTIONS}}": _opts(["含税", "不含税"], C.norm_tax(market.get("tax")) or "含税"),
        "{{MDELIVERY_OPTIONS}}": _opts(["送到", "出厂"], C.norm_delivery(market.get("delivery")) or "送到"),
        "{{FOOTER}}": html.escape(
            f"案例编号 {meta.get('case_id','—')} · 研究日期 {meta.get('research_date','—')} · "
            f"生成日期 {data.get('generated_at','—')} · 由『核实客户说的市场价』Skill 生成"
        ),
        "{{DATA_JSON}}": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
    }

    with open(echarts, "r", encoding="utf-8") as f:
        ec = f.read()
    subs["{{ECHARTS}}"] = ec.replace("</script", "<\\/script")

    out = tpl
    for k, v in subs.items():
        out = out.replace(k, v)

    left = re.findall(r"\{\{[A-Z0-9_]+\}\}", out)
    if left:
        raise SystemExit(f"[build_html] 未替换的占位符：{sorted(set(left))}")

    d = os.path.dirname(os.path.abspath(out_path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    size = os.path.getsize(out_path)
    print(f"[build_html] {out_path}  ({size/1024:.0f} KB)")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--template", default=TPL)
    ap.add_argument("--echarts", default=ECHARTS)
    a = ap.parse_args()
    build(C.load_json(a.data_json), a.out, a.template, a.echarts)


if __name__ == "__main__":
    main()
