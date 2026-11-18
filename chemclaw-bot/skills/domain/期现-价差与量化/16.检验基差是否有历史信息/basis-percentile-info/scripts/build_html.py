# -*- coding: utf-8 -*-
"""
build_html.py —— 把 report_data.json 注入模板，产出单文件自包含 HTML
=====================================================================
用法：
  python build_html.py --data out/report_data.json --template templates/report_template.html \
        --out out/基差分位信息检验_甲醇.html [--title "..."]
特性：无 CDN、无外链脚本、无外链字体；所有数据与交互内嵌，双击即可离线打开。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_TITLE = "甲醇基差分位信息检验 · 华东现货 × 郑商所期货｜历史统计报告"


def build(data_path: str, tpl_path: str, out_path: str, title: str = DEFAULT_TITLE) -> str:
    payload = json.load(open(data_path, encoding="utf-8"))
    tpl = open(tpl_path, encoding="utf-8").read()

    # 内联 JSON：转义 </script>（JSON 为合法 JS，只需防提前闭合）
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("</", "<\\/")
    if "__DATA_JSON__" not in tpl:
        raise SystemExit("模板缺少 __DATA_JSON__ 占位符")
    html = tpl.replace("__DATA_JSON__", raw).replace("__TITLE__", title)

    # 基本自检：不允许外链
    ext = re.findall(r'(?:src|href)\s*=\s*["\']https?://', html, flags=re.I)
    if ext:
        raise SystemExit("模板含外部资源引用 %d 处，违反自包含要求" % len(ext))
    if "<script src=" in html:
        raise SystemExit("模板含外部脚本引用")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("[OK] %s  %.2fMB  数据 %.2fMB" % (
        out_path, os.path.getsize(out_path) / 1048576, len(raw) / 1048576))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="out/report_data.json")
    ap.add_argument("--template", default="templates/report_template.html")
    ap.add_argument("--out", default="out/report.html")
    ap.add_argument("--title", default=DEFAULT_TITLE)
    a = ap.parse_args()
    build(a.data, a.template, a.out, a.title)


if __name__ == "__main__":
    main()
