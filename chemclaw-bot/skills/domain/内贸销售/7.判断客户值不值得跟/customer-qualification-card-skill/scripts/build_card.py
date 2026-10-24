# -*- coding: utf-8 -*-
"""build_card.py —— 由 data.json + 模板生成自包含 HTML 判断卡。

用法:
    python build_card.py <data.json> <out.html> [--template path/to/card.template.html]
"""
import json
import os
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = [a for a in sys.argv[1:] if a.startswith("--")]
    if len(args) < 2:
        print("用法: python build_card.py <data.json> <out.html>")
        sys.exit(2)
    data_path, out_path = args[0], args[1]
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "card.template.html")
    if "--template" in opts:
        tpl = sys.argv[sys.argv.index("--template") + 1]

    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    with open(tpl, encoding="utf-8") as f:
        html = f.read()

    title = (data.get("meta") or {}).get("title") or "客户多维判断卡"
    html = html.replace("<title>客户多维判断卡</title>", "<title>%s</title>" % title, 1)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if "__CARD_DATA__" not in html:
        raise SystemExit("模板缺少 __CARD_DATA__ 占位符")
    html = html.replace("__CARD_DATA__", payload, 1)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("OK ->", os.path.abspath(out_path))


if __name__ == "__main__":
    main()
