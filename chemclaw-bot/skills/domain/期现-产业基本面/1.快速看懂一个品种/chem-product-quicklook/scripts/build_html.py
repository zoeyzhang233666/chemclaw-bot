#!/usr/bin/env python3
"""build_html.py — research.json → 单文件离线 HTML 品种研究入口页

用法:
    python scripts/build_html.py research.json --out out/
    python scripts/build_html.py research.json --out out/ --no-echarts

设计：
  - 模板（templates/shell.html + styles.css + engine.js）不含任何品种事实；
  - 数据整体内联为 window.__DATA__，离线双击可开，可微信发送；
  - ECharts 内联（可选），用于节点详情里的价格示意曲线。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE / "templates"
ASSETS = HERE / "assets"

FORBIDDEN = ["预计上涨", "预计下跌", "看涨", "看跌", "必涨", "必跌", "抄底", "可以囤货", "建议囤货"]


def load_json(p: Path) -> dict:
    with p.open("r", encoding="utf-8") as f:
        return json.loads(p.read_text(encoding="utf-8-sig"))


def safe_json(obj) -> str:
    """内联到 <script> 的 JSON：转义 </ 防止提前闭合，保留中文可读性。"""
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def read_text(p: Path) -> str:
    # utf-8-sig：PowerShell Set-Content -Encoding utf8 会写入 BOM，
    # BOM 若被注入到 <style> 开头会让首条 CSS 规则失效，必须剥掉。
    return p.read_text(encoding="utf-8-sig")


def scan_forbidden(data: dict) -> list[str]:
    hits = []
    blob = json.dumps(data, ensure_ascii=False)
    for w in FORBIDDEN:
        if w in blob:
            hits.append(w)
    return hits


def build(data: dict, out_path: Path, with_echarts: bool = True) -> Path:
    d = dict(data)
    d.setdefault("vcs", {})
    d.setdefault("scenes", {})
    d.setdefault("caveats", [])
    d.setdefault("gaps", [])
    d.setdefault("sources", [])
    d.setdefault("purposes", [{"id": "general", "name": "通用研究"}])

    html = read_text(TPL / "shell.html")
    css = read_text(TPL / "styles.css")
    engine = read_text(TPL / "engine.js")

    if with_echarts and (ASSETS / "echarts.min.js").exists():
        engine = read_text(ASSETS / "echarts.min.js") + "\n;\n" + engine
    else:
        d["chart_note"] = "未内联 ECharts，价格示意图显示为占位；重新构建时去掉 --no-echarts。"
        engine = engine.replace("typeof echarts === \"undefined\"", "true")

    prod = d.get("product", {})
    title = d.get("meta", {}).get("title") or f"{prod.get('name_cn','品种')} · 品种研究入口"
    desc = f"{prod.get('name_cn','')}（{prod.get('name_en','')}）品种入门研究：身份规格、工艺路线、下游、企业与产能、贸易与期现、研究指标"
    desc = re.sub(r'["<>]', " ", desc)

    # 只替换“第一个”占位符：CSS 注释里的 /*__CSS__*/ 文档示例会抢先命中普通 replace
    def sub_once(text: str, token: str, value: str) -> str:
        idx = text.find(token)
        if idx < 0:
            raise SystemExit(f"[build_html] 模板缺少占位符 {token}")
        return text[:idx] + value + text[idx + len(token):]

    out = sub_once(html, "/*__CSS__*/", css)
    out = sub_once(out, "__TITLE__", title)
    out = sub_once(out, "__DESC__", desc)
    out = sub_once(out, "/*__DATA__*/null", safe_json(d))
    out = sub_once(out, "/*__ENGINE__*/", engine)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("research")
    ap.add_argument("--out", default="out")
    ap.add_argument("--name", default=None, help="输出文件名主干（缺省取 meta.output_name）")
    ap.add_argument("--no-echarts", action="store_true")
    a = ap.parse_args(argv)

    data = load_json(Path(a.research))
    hits = scan_forbidden(data)
    if hits:
        sys.stderr.write(f"[build_html] 拒绝渲染：研究稿含方向性表述 {hits}\n")
        return 2
    name = a.name or data.get("meta", {}).get("output_name") or (data.get("product", {}).get("name_cn", "品种") + "-研究入口")
    out = build(data, Path(a.out) / f"{name}.html", with_echarts=not a.no_echarts)
    print(f"[build_html] OK → {out}  ({out.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
