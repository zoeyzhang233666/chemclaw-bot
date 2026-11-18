# -*- coding: utf-8 -*-
"""fields.json + 已确认价格 → 报价草稿（.md / .xlsx）。

硬闸门：没有 --ack（"我确认该单价为我方销售价格"）就退 2，绝不生成带价格的文本。
价格只能由 --price 传入，脚本没有任何默认价、参考价、区间价。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402


def load_price(path: str | Path | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="按已确认价格生成报价草稿")
    ap.add_argument("fields", help="fields.json（extract.py 产出）")
    ap.add_argument("--price-json", dest="price_json", default=None, help="价格确认 JSON")
    ap.add_argument("--price", type=float, default=None, help="确认单价（元/单位）")
    ap.add_argument("--qty", type=float, default=None, help="报价数量")
    ap.add_argument("--tax", default=None, help="税费口径，取值见 references/quotation-template.md")
    ap.add_argument("--freight", default=None, help="运费口径")
    ap.add_argument("--validity", type=int, default=None, help="有效期（天）")
    ap.add_argument("--company", default=None, help="我方公司抬头")
    ap.add_argument("--contact", default=None, help="我方联系人/电话")
    ap.add_argument("--quote-no", dest="quote_no", default=None)
    ap.add_argument("--ack", default=None, help='必须填写确认语，例如"我确认该单价为我方销售价格"')
    ap.add_argument("--confirmed-at", dest="confirmed_at", default=None,
                    help="确认日期（默认今天，写进报价单生成说明）")
    ap.add_argument("--template", default=None, help="公司报价模板（Markdown，占位符见模板文件）")
    ap.add_argument("-o", "--out", default=None, help="输出目录，默认与 fields.json 同目录")
    ap.add_argument("--slug", default=None, help="输出文件名前缀")
    ap.add_argument("--xlsx", action="store_true", help="同时生成 Excel 报价工作簿")
    ap.add_argument("--check-only", action="store_true", help="只校验闸门，不写文件")
    args = ap.parse_args(argv)

    doc = C.load_doc(args.fields)
    conf = load_price(args.price_json)
    p = doc["price"]
    for key, val in [
        ("unit_price", args.price),
        ("quote_quantity", args.qty),
        ("validity_days", args.validity),
        ("company", args.company),
        ("contact", args.contact),
        ("quote_no", args.quote_no),
        ("ack", args.ack),
    ]:
        if val not in (None, ""):
            p[key] = val
    for k, v in conf.items():
        if v not in (None, ""):
            p[k] = v
    if args.tax:
        doc["gate"]["tax_mode"]["value"] = args.tax
    if args.freight:
        doc["gate"]["freight_mode"]["value"] = args.freight
    for key in ("tax_mode", "freight_mode"):
        if conf.get(key):
            doc["gate"][key]["value"] = conf[key]
    p["confirmed_at"] = args.confirmed_at or _dt.date.today().isoformat()

    print("\n【闸门检查】")
    bl = C.blockers(doc)
    if bl:
        for i, b in enumerate(bl, 1):
            print(f"  {i}. {b}")
        print("\n拒绝生成：报价草稿必须由你补齐上述项并确认单价。系统不产生价格。")
        return 2
    print("  通过：单价与口径均已由你确认。")

    template = None
    if args.template:
        template = Path(args.template).read_text(encoding="utf-8")
    md = C.render_quote_md(doc, template=template)
    if args.check_only:
        print("\n（--check-only，未写文件）")
        return 0

    outdir = Path(args.out) if args.out else Path(args.fields).resolve().parent
    outdir.mkdir(parents=True, exist_ok=True)
    slug = args.slug or _slug(doc)
    md_path = outdir / f"{slug}-报价草稿.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  ← {md_path}")

    if args.xlsx:
        import build_xlsx

        xlsx_path = outdir / f"{slug}-报价工作簿.xlsx"
        build_xlsx.build(doc, xlsx_path, quote_md=md)
        print(f"  ← {xlsx_path}")
    return 0


def _slug(doc: dict) -> str:
    name = doc["meta"].get("customer") or doc["fields"]["product"].get("value") or "询盘"
    base = f"报价_{name}"
    return "".join(ch for ch in base if ch not in '\\/:*?"<>|')[:60]


if __name__ == "__main__":
    raise SystemExit(main())
