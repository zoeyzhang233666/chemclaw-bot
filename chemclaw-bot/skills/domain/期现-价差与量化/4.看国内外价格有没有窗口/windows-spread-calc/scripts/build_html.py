# -*- coding: utf-8 -*-
"""data.json + templates/report.html -> 自包含单文件 HTML 报告。

用法：
    python scripts/build_html.py build/data.json --out output/report.html

产物特性：
  * 完全离线：ECharts 与计算内核都内联，双击即可打开，可直接邮件转发；
  * 交互重算：改报价/汇率/运费/税率/术语，KPI、瀑布、曲线、敏感性全部立即重算；
  * 单一事实源：浏览器侧调用 assets/core.js（与 scripts/core.py 数值等价）。

禁用做法：
  * 不允许从 CDN 引脚本（离线会白屏）；
  * 不允许把派生数字硬编码进模板（只能来自 data.json，否则 HTML 与 Excel 会不一致）。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wio  # noqa: E402

CDN_PATTERNS = [
    r'src\s*=\s*["\']https?://',
    r'href\s*=\s*["\']https?://[^"\']*\.css',
    r'@import\s+url\(\s*["\']?https?://',
]


def find_assets():
    """定位 echarts 与 core.js：优先本 Skill 自带 assets/。"""
    here = os.path.dirname(os.path.abspath(__file__))
    ech = os.path.join(here, "assets", "echarts.min.js")
    core = os.path.join(here, "assets", "core.js")
    if not os.path.exists(ech):
        wio.die("缺少 ECharts 资源：%s\n请把 echarts.min.js 放到 scripts/assets/ 下（仅需一次）。" % ech)
    if not os.path.exists(core):
        wio.die("缺少计算内核镜像：%s" % core)
    return ech, core


def main():
    ap = argparse.ArgumentParser(description="data.json -> 自包含 HTML 报告")
    ap.add_argument("data")
    ap.add_argument("--out", default=None)
    ap.add_argument("--template", default=None)
    args = ap.parse_args()

    data = wio.load_json(args.data)
    here = os.path.dirname(os.path.abspath(__file__))
    tpl_path = args.template or os.path.join(here, "templates", "report.html")
    tpl = wio.read_text(tpl_path)
    ech_path, core_path = find_assets()
    ech = wio.read_text(ech_path)
    corejs = wio.read_text(core_path)

    meta = data["meta"]
    h1 = meta.get("title") or ("%s 内外价差测算" % meta.get("product", ""))
    title = "%s（%s · %s）" % (h1, meta.get("product", ""), meta.get("base_date", ""))

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # 防止数据里的 </script> 提前闭合脚本块
    payload = payload.replace("</", "<\\/")

    html = tpl
    html = html.replace("__ECHARTS__", ech)
    html = html.replace("__COREJS__", corejs)
    html = html.replace("__DATA__", payload)
    html = html.replace("__TITLE__", esc(title))
    html = html.replace("__H1__", esc(h1))

    # 只校验"模板自己声明的"占位符是否都被替换，避免误判 ECharts 内部的 ___xx___ 常量
    declared = set(re.findall(r"__[A-Z][A-Z_]{2,}__", tpl))
    leftover = sorted(p for p in declared if p in html)
    if leftover:
        wio.die("模板占位符未替换：%s" % ", ".join(leftover))

    for pat in CDN_PATTERNS:
        if re.search(pat, html):
            wio.warn("检测到疑似外链资源（%s）：离线打开时可能失效" % pat)

    out = args.out or os.path.join("output", "report.html")
    wio.write_text(out, html)
    size = os.path.getsize(out)
    wio.ok("写出 %s（%.2f MB）" % (out, size / 1024.0 / 1024.0))
    print("  KPI 快照：CIF %.2f / landed_cash %.2f / net_cash %.2f"
          % (data["cost"]["cif"], data["cost"]["landed_cash"], data["cost"]["net_cash"]))
    for g in data["gaps_table"]:
        print("  %-26s %s" % (g["code"], wio.fmt_trim(g["value"])))


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


if __name__ == "__main__":
    main()
