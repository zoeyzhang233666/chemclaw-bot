# -*- coding: utf-8 -*-
"""build_html.py — 把 dataset.json + geo_simplified.json 注入模板，产出单文件 HTML

用法:
    python build_html.py --dataset dataset.json --geo geo_simplified.json \
        --template ../template/report.html --out 报告.html
"""
import argparse, json, os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--geo", default="geo_simplified.json")
    ap.add_argument("--template", default=os.path.join(os.path.dirname(__file__), "..", "template", "report.html"))
    ap.add_argument("--out", default="report.html")
    args = ap.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        ds = json.load(f)
    geo = []
    if os.path.exists(args.geo):
        with open(args.geo, encoding="utf-8") as f:
            geo = json.load(f)
    else:
        print(f"[html] 未找到 {args.geo}，底图为空（地图仍显示半径与点位）")

    with open(args.template, encoding="utf-8") as f:
        tpl = f.read()

    if "__DATA__" not in tpl or "__GEO__" not in tpl:
        raise SystemExit("模板缺少 __DATA__ / __GEO__ 占位符")

    doc = tpl.replace("__DATA__", json.dumps(ds, ensure_ascii=False, separators=(",", ":"))) \
             .replace("__GEO__", json.dumps(geo, ensure_ascii=False, separators=(",", ":")))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(doc)

    n = len(ds.get("items", []))
    print(f"[html] {n} 家企业 · {len(geo)} 个底图区域 · {len(doc)} 字符 → {args.out}")
    if n == 0:
        print("[html] 警告：items 为空，报告只有外壳")


if __name__ == "__main__":
    main()
