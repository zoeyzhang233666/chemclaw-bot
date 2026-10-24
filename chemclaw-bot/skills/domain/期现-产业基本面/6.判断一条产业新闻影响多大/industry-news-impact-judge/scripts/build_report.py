#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_report.py — case_data.json -> 交互式 HTML 产业新闻影响分析报告

用法：
  python build_report.py <case_data.json> -o <out.html>
  python build_report.py <case_data.json> -o <out.html> --template <template.html>

模板占位符：
  {{TITLE}}   {{SUBTITLE}}   {{CASE_ID}}   {{PAYLOAD_JSON}}   {{BUILT_AT}}
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parent / "assets" / "templates" / "news-impact-report.template.html"


def main() -> int:
    ap = argparse.ArgumentParser(description="JSON -> 交互式 HTML 报告")
    ap.add_argument("data", help="case_data.json 路径")
    ap.add_argument("-o", "--out", required=True, help="输出 HTML 路径")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="模板路径")
    a = ap.parse_args()

    data_path = pathlib.Path(a.data)
    tpl_path = pathlib.Path(a.template)
    if not data_path.exists():
        print(f"[错误] 找不到数据文件：{data_path}", file=sys.stderr)
        return 2
    if not tpl_path.exists():
        print(f"[错误] 找不到模板：{tpl_path}", file=sys.stderr)
        return 2

    raw = data_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[错误] JSON 解析失败：{e}", file=sys.stderr)
        return 2

    # 用 base64 嵌入 JSON：避免 HTML 解析器改写内联 <script type=application/json> 的内容
    # （直接嵌入时 " 会被转成 &quot; 等实体，导致 JSON.parse 报 Invalid token）
    payload_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")

    html = tpl_path.read_text(encoding="utf-8")
    meta = data.get("meta", {})
    subs = {
        "{{TITLE}}": meta.get("title", "产业新闻影响分析"),
        "{{SUBTITLE}}": meta.get("subtitle", ""),
        "{{CASE_ID}}": meta.get("case_id", ""),
        "{{PAYLOAD_B64}}": payload_b64,
        "{{BUILT_AT}}": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    for k, v in subs.items():
        html = html.replace(k, v)

    # 模板里若仍残留未替换占位符，视为错误
    left = re.findall(r"\{\{[A-Z_]+\}\}", html)
    if left:
        print(f"[警告] 模板中存在未替换占位符：{set(left)}", file=sys.stderr)

    # 给每个初始化 IIFE 加独立错误边界：某一块渲染失败不应影响其余区块
    def _guard(match: "re.Match[str]") -> str:
        tag = match.group(1).strip(" -")
        return (
            "/* --- " + tag + " --- */\n(function(){ try {\n"
            "__SECTION__ = '" + tag + "';\n"
            + match.group(2)
            + "\n} catch(e){ (window.__ERR__=window.__ERR__||[]).push({'section':'"
            + tag
            + "','msg':String(e&&e.message||e)}); console.error('[section " + tag + "]', e); } })();"
        )

    html = re.sub(
        r"/\* --- ([A-Z0-9 /$-]+?) --- \*/\n\(function\(\)\{\n(.*?)\n\}\)\(\);",
        _guard,
        html,
        flags=re.S,
    )
    html = html.replace("const $  =", "const __nonce =")
    html = html.replace(
        "const qp = (s,r=document)=>r.querySelector(s);",
        "let __SECTION__='';\nconst qp = (s,r=document)=>{const e=r.querySelector(s); if(!e) console.warn('[missing]', __SECTION__, s); return e;};",
    )

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"[OK] 已生成 {out}  ({len(html):,} 字符)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
