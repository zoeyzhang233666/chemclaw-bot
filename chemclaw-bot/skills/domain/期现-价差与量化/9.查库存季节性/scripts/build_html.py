# -*- coding: utf-8 -*-
"""
build_html.py —— 自包含交互式库存季节性报告
=============================================
输入：seasonal.json + story.json + config.json（模板目录含 assets/echarts.min.js）
输出：单文件 HTML，无外链依赖，可离线双击打开。

交互：库存指标切换 / 区域切换 / 样本年数切换 / 周·月频率切换；四种图表随筛选实时重算。
首屏：当前库存、同期分位、近 4 周变化（三张 KPI 卡）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TPL = Path(__file__).parent / "templates" / "inventory_seasonality.html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasonal", required=True)
    ap.add_argument("--story", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    seasonal = json.loads(Path(args.seasonal).read_text(encoding="utf-8"))
    story = json.loads(Path(args.story).read_text(encoding="utf-8"))
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    title = f"{cfg['product']}·{cfg['metric_name']} 库存季节性报告（{cfg['asof']}）"
    html = TPL.read_text(encoding="utf-8")
    # 兼容 JSON 不支持的值
    def _default(o):
        try:
            return float(o)
        except Exception:
            return str(o)
    payload = {"seasonal": seasonal, "story": story, "config": cfg}
    js = json.dumps(payload, ensure_ascii=False, default=_default).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/", "window.__DATA__ = " + js + ";")
    html = html.replace("__TITLE__", title)
    assets = Path(__file__).parent / "templates" / "assets" / "echarts.min.js"
    echarts = assets.read_text(encoding="utf-8")
    html = html.replace("/*__ECHARTS__*/", echarts)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
