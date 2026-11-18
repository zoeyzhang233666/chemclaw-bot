# -*- coding: utf-8 -*-
"""
build_html.py — 由输入 JSON 生成单文件交互式出口报价计算器 HTML

  python scripts/build_html.py input.json -o 出口报价计算器.html [--title ...] [--simulated k1,k2]

规则：
- 输入 JSON 中不在 `simulated` 列表里的费率一律按「用户输入」展示；
- `simulated` 列出的字段会在页面里标 SIMULATED（紫色），并在草稿里写内部备注；
- 本脚本不生成、不注入任何默认运价。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(ROOT, "templates", "calculator.template.html")
sys.path.insert(0, HERE)
from calc_engine import TERMS, VERSION  # noqa: E402

SEG_ORDER = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"]

DEFAULT_DISCLAIMER = (
    "<b>本页面不是实时运价系统。</b>所有成本数字来自你录入的参数；"
    "标记 <b>SIMULATED</b> 的运费/保险/港口费为演示用模拟值，仅用于展示完整计算流程，"
    "不得作为对外报价依据。系统不提供市场价、参考运费、建议毛利或税费默认值。"
)


def js_json(obj) -> str:
    """安全内嵌到 <script> 的 JSON"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def build(input_path: str, out_path: str, title: str = "", disclaimer: str = "",
          simulated: list[str] | None = None, sim_preset: dict | None = None) -> dict:
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    clean = {k: v for k, v in raw.items() if not k.startswith("_")}

    termmeta = {t: {"segments": TERMS[t][0], "note": TERMS[t][1], "risk": TERMS[t][2]} for t in TERMS}
    payload = {
        "engine_version": VERSION,
        "inputs": clean,
        "simulated": simulated or [],
        "simPreset": sim_preset or {},
        "termmeta": termmeta,
        "disclaimer": disclaimer or raw.get("_disclaimer") or DEFAULT_DISCLAIMER,
    }

    with open(TEMPLATE, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("__DATA__", js_json(payload))
    html = html.replace("__PRODUCT__", clean.get("product_cn") or "化工品出口")
    html = html.replace("__SPEC__", clean.get("spec") or "")
    html = html.replace("__HS__", clean.get("hs_code") or "")
    html = html.replace("__POL__", clean.get("pol") or "")
    html = html.replace("__POD__", clean.get("pod") or "")
    html = html.replace("__VER__", VERSION)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"out": out_path, "bytes": len(html.encode("utf-8")),
            "simulated": payload["simulated"], "product": clean.get("product_cn")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成交互式出口报价计算器 HTML")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", default="出口报价计算器.html")
    ap.add_argument("--title", default="")
    ap.add_argument("--disclaimer", default="")
    ap.add_argument("--simulated", default="",
                    help="逗号分隔的「模拟」字段名，例如 inland_cny_per_t,port_cny_per_t")
    ap.add_argument("--sim-preset", default="",
                    help="JSON 字符串：点击「载入模拟情景」时注入的演示值")
    ap.add_argument("--sim-preset-file", default="",
                    help="同上，从 JSON 文件读取（推荐，免去命令行转义问题）")
    a = ap.parse_args(argv)
    sim = [s.strip() for s in a.simulated.split(",") if s.strip()]
    preset = None
    if a.sim_preset_file:
        with open(a.sim_preset_file, "r", encoding="utf-8") as f:
            preset = json.load(f)
    elif a.sim_preset:
        preset = json.loads(a.sim_preset)
    info = build(a.input, a.out, a.title, a.disclaimer, sim, preset)
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
