#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_html.py — 生成自包含交互式 HTML 报告
（零外部请求：ECharts 内核、应用逻辑、数据全部内嵌，可离线打开）

用法：
  python scripts/build_html.py --result build/result.json \
      --out build/regional-spread-report.html
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def rd(p, enc="utf-8"):
    with open(p, "r", encoding=enc) as f:
        return f.read()


def find(*cands):
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default="build/result.json")
    ap.add_argument("--out", default="build/regional-spread-report.html")
    ap.add_argument("--template", default=None)
    a = ap.parse_args()

    tpl_path = find(a.template or "", os.path.join(ROOT, "assets", "templates", "regional-spread-report-template.html"),
                    os.path.join("assets", "templates", "regional-spread-report-template.html"))
    if not tpl_path:
        print("找不到模板 assets/templates/regional-spread-report-template.html", file=sys.stderr)
        sys.exit(1)

    tpl = rd(tpl_path)
    result = json.loads(rd(a.result))
    echarts = rd(find(os.path.join(ROOT, "assets", "echarts.min.js"),
                      os.path.join("assets", "echarts.min.js")) or "", enc="utf-8")
    core = rd(find(os.path.join(ROOT, "scripts", "app-core.js"),
                   os.path.join("scripts", "app-core.js")))
    ui = rd(find(os.path.join(ROOT, "scripts", "app-ui.js"),
                 os.path.join("scripts", "app-ui.js")))
    geo = json.loads(rd(find(os.path.join(ROOT, "assets", "geo", "china-shell.json"),
                             os.path.join("assets", "geo", "china-shell.json"))))

    payload = json.dumps(result, ensure_ascii=False, default=str).replace("</", "<\\/")
    geo_js = json.dumps(geo, ensure_ascii=False)

    # 组装应用脚本：数据 + geo + core + ui
    app = (
        "const PAYLOAD = " + payload + ";\n"
        "const GEO_SHELL = " + geo_js + ";\n"
        + core + "\n" + ui + "\n"
        "/* 注册示意地图 */\n"
        "(function(){ try{ if(typeof echarts!=='undefined'){ echarts.registerMap('china-shell', GEO_SHELL); } }catch(e){} })();\n"
    )
    app = app.replace("</script", "<\\/script")

    # 占位标记必须是「不可能是内核源码内容」的中性串，且不能含 HTML 注释或 </script 片段
    html = tpl.replace("@@ECHARTS_BUNDLE@@", echarts)
    html = html.replace("@@PAYLOAD_JSON@@", payload)
    if "@@ECHARTS_BUNDLE@@" in html or "@@PAYLOAD_JSON@@" in html:
        print("[build_html] ⚠️ 占位符未替换", file=sys.stderr)
        sys.exit(1)

    marker = '<script id="appjs"></script>'
    if marker not in html:
        print("[build_html] ⚠️ 找不到 appjs 挂载点", file=sys.stderr)
        sys.exit(1)
    html = html.replace(marker, '<script id="appjs">\n' + app + '\n</script>')

    title = (f"{result['meta'].get('product','')} 区域价差研究 ｜ "
             + " / ".join(r["name"] for r in result["meta"]["regions"]))
    html = html.replace("__TITLE__", title)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)

    kb = os.path.getsize(a.out) / 1024.0
    print(f"[build_html] {a.out}  {kb:.1f} KB")
    for token in ("__TITLE__",):
        if token in html:
            print(f"[build_html] ⚠️ 占位符未替换: {token}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
