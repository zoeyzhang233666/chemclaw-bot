#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a self-contained HTML workbench from data.json.

Usage:
  python build_html.py data.json out.html [--xlsx-name 工作簿.xlsx]
"""
from __future__ import annotations

import argparse
import json
import os
from html import escape as htmlescape

import common

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "templates")


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read(name):
    with open(os.path.join(TPL, name), "r", encoding="utf-8") as f:
        return f.read()


def safe_json(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    s = s.replace("<", "\\u003c")
    s = s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return s


def build(data_path, out_path, xlsx_name=""):
    D = common.normalize(load(data_path))
    M = D.get("meta") or {}
    title = M.get("title") or f"{M.get('product_short') or M.get('product') or '化工品'} · 第二供应源备选池"
    html = read("workbench.html")
    html = html.replace("__STYLE__", read("style.css"))
    html = html.replace("__APP__", read("app.js"))
    html = html.replace("__TITLE__", htmlescape(str(title)))
    html = html.replace("__XLSX_NAME__", str(xlsx_name or ""))
    html = html.replace("__DATA__", safe_json(D))
    if "__DATA__" in html:
        raise SystemExit("template still contains __DATA__ placeholder")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("out")
    ap.add_argument("--xlsx-name", default="")
    a = ap.parse_args()
    p = build(a.data, a.out, a.xlsx_name)
    print(f"OK  HTML  {p}  {os.path.getsize(p)/1024:.1f} KB")


if __name__ == "__main__":
    main()
