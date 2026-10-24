# -*- coding: utf-8 -*-
"""把 data.json + 模板 + ECharts 打成一个自包含 HTML。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402

TEMPLATE = HERE / "templates" / "dashboard.html"
ECHARTS = HERE / "assets" / "echarts.min.js"


def build(data_path: Path, out_path: Path) -> Path:
    data = common.load(data_path)
    payload = common.build_payload(data)

    tpl = TEMPLATE.read_text(encoding="utf-8")
    js = ECHARTS.read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    if "</script" in blob.lower():
        raise SystemExit("数据里含有 </script，会破坏内联脚本，请转义后再生成")

    html = (
        tpl.replace("%%TITLE%%", data["meta"]["title"])
           .replace("%%PRODUCT%%", f'{data["meta"]["product"]} · {data["meta"]["spec"]}')
           .replace("%%ASOF%%", data["meta"]["asof"])
           .replace("%%DATA%%", blob)
           .replace("%%ECHARTS%%", js)
    )
    # 占位符必须全部替换干净
    for token in ("%%TITLE%%", "%%DATA%%", "%%ECHARTS%%", "%%PRODUCT%%", "%%ASOF%%"):
        if token in html:
            raise SystemExit(f"占位符未替换: {token}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default="out")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    data = common.load(args.data)
    name = args.name or f'{data["meta"]["product"]}多地区价格对比'
    out = Path(args.out)
    p = build(Path(args.data), out / f"{name}.html")
    print(f"HTML 已生成: {p}  ({p.stat().st_size/1024/1024:.2f} MB)")


if __name__ == "__main__":
    main()
