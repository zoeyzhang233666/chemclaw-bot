# -*- coding: utf-8 -*-
"""build_html.py —— 把 scenario.json + fx_series.json 注入模板，生成离线单文件 HTML。

用法:
    python scripts/build_html.py --scenario examples/01-.../build/scenario.json \
        --fx build/fx_series.json --out examples/01-.../build/汇率风险测算.html
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "scripts", "templates", "dashboard.html")
ECHARTS = os.path.join(ROOT, "scripts", "assets", "echarts.min.js")

FORBIDDEN = ["预计将上涨", "预计将下跌", "看涨", "看跌", "建议锁汇", "建议买入远期", "抄底汇", "汇率将升至"]


def compact_json(obj, limits=None):
    """内嵌 JSON：序列只保留到窗口起点前 400 天，减小体积又不影响 1Y/3Y 分位。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def slim_fx(fx, keep_years=3.2):
    """只保留近 keep_years 年的数据点（3 年分位 + 缓冲），避免把整表塞进 HTML。"""
    dates = fx["dates"]
    last = dates[-1]
    import datetime
    cutoff = (datetime.date.fromisoformat(last)
              - datetime.timedelta(days=int(365 * keep_years))).isoformat()
    out = dict(fx)
    out["currencies"] = {}
    for code, c in fx["currencies"].items():
        vals = {d: v for d, v in c["values"].items() if d >= cutoff}
        out["currencies"][code] = {**c, "values": vals}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--fx", default=os.path.join(ROOT, "build", "fx_series.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    scen = json.load(open(args.scenario, encoding="utf-8"))
    if not scen.get("ok", True):
        sys.exit("scenario.json 未通过校验：%s" % scen.get("errors"))
    fx = slim_fx(json.load(open(args.fx, encoding="utf-8")))
    template = open(TPL, encoding="utf-8").read()
    echarts = open(ECHARTS, encoding="utf-8").read()

    m = scen["meta"]
    title = args.title or f"汇率风险测算 · {m.get('product') or ''} {m['amount_fx']:,.0f} {m['currency']} · {m['direction_label']}"
    title = title.replace("  ", " ").strip()
    subline = (f"{m['direction_label']}：{m['amount_fx']:,.2f} {m['currency']}，"
               f"预计 {m['horizon_days']} 天后结算。历史汇率取自国家外汇管理局人民币汇率中间价。")
    html = (template
            .replace("__TITLE__", title)
            .replace("__SUBLINE__", subline)
            .replace("__SCENARIO__", compact_json(scen).replace("</", "<\\/"))
            .replace("__FX__", compact_json(fx).replace("</", "<\\/"))
            .replace("__ECHARTS__", echarts))
    if "__ECHARTS__" in html or "__SCENARIO__" in html or "__TITLE__" in html or "__SUBLINE__" in html or "__FX__" in html:
        sys.exit("模板占位符未全部替换")
    for w in FORBIDDEN:
        if w in html:
            sys.exit(f"HTML 中出现禁用词：{w}")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"wrote {args.out}  ({len(html.encode('utf-8'))/1024:.0f} KB)")


if __name__ == "__main__":
    main()
