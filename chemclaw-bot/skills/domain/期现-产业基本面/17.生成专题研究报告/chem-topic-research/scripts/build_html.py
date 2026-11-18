# -*- coding: utf-8 -*-
"""
build_html.py —— 把 case.json 渲染成单文件交互式 HTML 专题报告。

用法
----
  python build_html.py <case.json> --out <报告.html> [--audience management]

特性
----
* 单文件、离线可用、无外部依赖（图表为内联 SVG）
* 首屏：KPI + 核心结论（点击展开证据与计算）
* 每张图表：点击“查看原始数据”打开全量数据表，可复制为 TSV 粘贴 Excel
* 章节可拖动排序（localStorage 记忆）
* 可导出完整 Markdown 材料、可打印为 PDF
* 按受众屏蔽章节包（audience_frameworks.<受众>.suppressed_topic_packs）
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "templates", "report.html")


def reference_price(case: dict):
    """取最新一条重碱现货价，作为成本图上的参考线。"""
    pts = [p for p in case.get("price_points") or [] if p.get("value") is not None]
    heavy = [p for p in pts if "重" in (p.get("item") or "")]
    pool = heavy or pts
    if not pool:
        return None
    pool = sorted(pool, key=lambda p: p.get("date") or "")
    return pool[-1].get("value")


def build(case: dict, audience: str | None = None, template: str | None = None):
    errs, warns = C.validate(case)
    prof = C.audience_profile(case, audience)
    payload = C.build_payload(case, prof)
    payload["meta"] = dict(payload["meta"])
    payload["meta"]["refPrice"] = reference_price(case)
    tpl_path = template or TEMPLATE
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    meta = case.get("meta") or {}
    title = "%s｜%s版专题研究" % (meta.get("title", "专题研究"),
                                C.AUDIENCE_CN.get(prof["audience_key"], prof["audience_key"]))
    html = (tpl.replace("__TITLE__", _escape_title(title))
               .replace("__DATA__", C.safe_json(payload)))
    return html, payload, errs, warns


def _escape_title(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def write(html: str, path: str) -> str:
    C.ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成单文件交互式专题研究 HTML")
    ap.add_argument("case")
    ap.add_argument("--out", default="")
    ap.add_argument("--audience", default="", help="覆盖 case.meta.audience")
    ap.add_argument("--template", default="", help="自定义模板路径")
    ap.add_argument("--allow-warn", action="store_true", help="有警告也继续（默认允许）")
    ap.add_argument("--strict", action="store_true", help="有警告即失败")
    a = ap.parse_args(argv)

    case = C.load(a.case)
    html, payload, errs, warns = build(case, a.audience or None, a.template or None)
    for w in warns:
        print("WARN ", w, file=sys.stderr)
    if errs:
        for e in errs:
            print("ERROR", e, file=sys.stderr)
        print("case.json 未通过校验，已中止。先修复错误再生成。", file=sys.stderr)
        return 1
    if a.strict and warns:
        print("strict 模式下存在警告，已中止。", file=sys.stderr)
        return 1
    out = a.out or C.default_filename(case, payload["profile"]["audience_key"], ".html")
    write(html, out)
    print("HTML ->", out, "(%.1f KB)" % (os.path.getsize(out) / 1024.0))
    print("  受众:", payload["profile"]["label"],
          "| 章节:", len(payload["sections"]),
          "| 结论:", len(payload["conclusions"]),
          "| 来源:", len(payload["sources"]),
          "| 缺口:", len(payload["gaps"]))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
