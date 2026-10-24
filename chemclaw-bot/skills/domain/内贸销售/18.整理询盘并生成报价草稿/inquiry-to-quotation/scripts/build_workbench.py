# -*- coding: utf-8 -*-
"""fields.json → 自包含交互式工作台 HTML（上传区 + 字段确认 + 价格闸门 + 报价草稿）。

    python build_workbench.py fields.json -o 询盘工作台.html
    python build_workbench.py fields.json -o 工作台.html --demo-text "示例询盘原文..."

页面是纯前端：素材不出本机，没有后端，也不含任何默认价格。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

TPL = Path(__file__).resolve().parent.parent / "templates" / "workbench.template.html"

DEMO_TEXT = (
    "王经理你好，我们玻璃厂想找重质纯碱长期供应商，月用量大概 800 吨，先试单 200 吨。"
    "要求 Na2CO3 ≥ 99.2%、Fe2O3 ≤ 0.003%、烧失量 ≤ 0.5%、粒度 180 目筛余 ≤ 5%。"
    "送到我们江苏盐城的厂区，吨包就行，你们报个价，价格有效期也写一下。"
)


def build(doc: dict, out: Path, demo_text: str = DEMO_TEXT, template: Path | None = None) -> Path:
    tplp = template or TPL
    html = tplp.read_text(encoding="utf-8")
    data = json.dumps(doc, ensure_ascii=False)
    html = (
        html.replace("__DATA__", data)
        .replace("__TAX_OPTIONS__", json.dumps(C.TAX_OPTIONS, ensure_ascii=False))
        .replace("__FREIGHT_OPTIONS__", json.dumps(C.FREIGHT_OPTIONS, ensure_ascii=False))
        .replace("__DEMO_TEXT__", json.dumps(demo_text, ensure_ascii=False))
        .replace("__TITLE__", f"询盘整理与报价草稿 · {doc['meta'].get('customer') or doc['fields']['product'].get('value') or '询盘'}")
    )
    if "__DATA__" in html or "__TITLE__" in html:
        raise RuntimeError("模板占位符未替换干净")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fields.json → 交互式询盘工作台 HTML")
    ap.add_argument("fields")
    ap.add_argument("-o", "--out", default="询盘工作台.html")
    ap.add_argument("--template", default=None)
    ap.add_argument("--demo-text", default=None, help="工作台默认文本（默认用内置短示例）")
    ap.add_argument("--demo-text-file", default=None, help="从文本文件读取默认文本")
    args = ap.parse_args(argv)
    doc = C.load_doc(args.fields)
    demo_text = DEMO_TEXT
    if args.demo_text_file:
        demo_text = Path(args.demo_text_file).read_text(encoding="utf-8")
    elif args.demo_text:
        demo_text = args.demo_text
    p = build(doc, Path(args.out), demo_text=demo_text, template=Path(args.template) if args.template else None)
    print(f"← {p}（{p.stat().st_size/1024:.1f} KB）")
    print("  闸门状态：" + ("可生成" if not C.blockers(doc) else "待补 %d 项" % len(C.blockers(doc))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
