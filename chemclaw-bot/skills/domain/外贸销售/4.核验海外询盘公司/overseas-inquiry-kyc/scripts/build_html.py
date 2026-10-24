#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inquiry.json → 单文件交互式 HTML 报告。

用法:
    python build_html.py inquiry.json out.html [--xlsx-name 核验工作簿.xlsx]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

import _common as C

if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "templates")

PLACEHOLDERS = ["__STYLE__", "__APP__", "__TITLE__", "__XLSX_NAME__", "__DATA__"]


def read(name):
    with open(os.path.join(TPL, name), "r", encoding="utf-8") as f:
        return f.read()


def safe_json(obj):
    """内联到 <script> 里的 JSON：必须转义 < 与行分隔符，防止提前闭合标签。"""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    s = s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    s = s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return s


def build_view(D):
    """只给渲染层所需的派生字段（区块清单与计数），不在 JS 里重复定义。"""
    return {
        "meta": D["meta"],
        "inquiry": D["inquiry"],
        "extraction": D["extraction"],
        "subject": D["subject"],
        "domains": D["domains"],
        "email_auth": D["email_auth"],
        "matrix": D["matrix"],
        "business_fit": D["business_fit"],
        "checks": D["checks"],
        "linkage": D["linkage"],
        "risks": D["risks"],
        "sources": D["sources"],
        "requests": D["requests"],
        "actions": D["actions"],
        "messages": D["messages"],
        "boundaries": D.get("boundaries", []),
        "stats": D["stats"],
        "sections": [{k: s[k] for k in ("id", "key", "title", "subtitle")} for s in C.SECTIONS],
    }


def render_title(M):
    t = M.get("title") or "海外询盘企业核验报告"
    prefix = "[模拟] " if M.get("synthetic") else ""
    return prefix + t


def build(data_path, out_path, xlsx_name=""):
    D = C.normalize(C.load_json(data_path))
    view = build_view(D)

    html = read("report.html")
    html = html.replace("__STYLE__", read("style.css"))
    html = html.replace("__APP__", read("app.js"))
    html = html.replace("__TITLE__", render_title(D["meta"]))
    html = html.replace("__XLSX_NAME__", xlsx_name or "")
    # DATA 必须最后替换，避免其内容里的占位符样式字串被再次替换
    html = html.replace("__DATA__", safe_json(view))

    for ph in PLACEHOLDERS:
        if ph in html:
            raise SystemExit(f"模板仍残留占位符 {ph}")

    C.write_text(out_path, html)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="生成单文件交互式 HTML 核验报告")
    ap.add_argument("data")
    ap.add_argument("out")
    ap.add_argument("--xlsx-name", default="", help="在页面页脚标注配套工作簿文件名")
    a = ap.parse_args()
    p = build(a.data, a.out, a.xlsx_name)
    size = os.path.getsize(p) / 1024
    print(f"[ok] HTML  {p}  {size:.1f} KB")


if __name__ == "__main__":
    main()
