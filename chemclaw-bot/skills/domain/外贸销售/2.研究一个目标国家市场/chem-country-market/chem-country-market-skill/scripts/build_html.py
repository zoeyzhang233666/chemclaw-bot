"""
build_html.py — case.json → 派生 data.json → 自包含单文件 HTML（ECharts 内联，可离线打开）

  python build_html.py case.json --out out/中国重质纯碱-印度尼西亚_国别市场研究.html
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def safe_json(obj):
    s = json.dumps(obj, ensure_ascii=False)
    # avoid breaking the inline <script> and HTML parsers
    return (s.replace("</script", "<\\/script")
             .replace("<!--", "<\\!--")
             .replace("\u2028", "\\u2028")
             .replace("\u2029", "\\u2029"))


def build_data(case):
    idx = C.build_index(case)
    return {
        "case": case,
        "index": idx,
        "handoff": C.nco_report_links(case),
        "stats": {
            "sources": len(case.get("sources") or []),
            "gaps": len(case.get("gaps") or []),
            "verify": len(case.get("verify_actions") or []),
            "companies": len((case.get("industries") or {}).get("consumers") or []) +
                         len((case.get("industries") or {}).get("local_production") or []),
        },
        "generator": "chem-country-market v1.0",
    }


def build_html(case, template=None, echarts=None):
    template = template or os.path.join(HERE, "templates", "report.html")
    echarts = echarts or os.path.join(HERE, "assets", "echarts.min.js")
    with open(template, "r", encoding="utf-8") as f:
        tpl = f.read()
    with open(echarts, "r", encoding="utf-8") as f:
        js = f.read()
    data = build_data(case)
    meta = case.get("meta") or {}
    title = "%s ｜ %s（HS %s）" % (
        case.get("meta", {}).get("country", {}).get("name_cn", ""),
        meta.get("subject", {}).get("product_cn", ""),
        meta.get("subject", {}).get("hs_code", ""))
    html = (tpl.replace("__TITLE__", title)
               .replace("__ECHARTS__", js)
               .replace("__DATA__", safe_json(data)))
    return html, data


def default_name(case):
    m = case["meta"]
    return "%s-%s_国别市场研究.html" % (m["country"]["name_cn"], m["subject"]["product_cn"].split("（")[0])


def write(html, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def main():
    ap = argparse.ArgumentParser(description="生成自包含交互式国别市场研究 HTML")
    ap.add_argument("case")
    ap.add_argument("--out", default="")
    ap.add_argument("--data", default="", help="同时写出派生 data.json 的路径")
    a = ap.parse_args()
    case = C.load_json(a.case)
    errs, warns = C.validate_case(case)
    if errs:
        for e in errs:
            print("ERROR", e, file=sys.stderr)
        print("case 未通过校验，先修 validate.py 报错再生成。", file=sys.stderr)
        sys.exit(1)
    for w in warns:
        print("WARN", w, file=sys.stderr)
    html, data = build_html(case)
    out = a.out or os.path.join("out", default_name(case))
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    if a.data:
        C.save_json(data, a.data)
    print("HTML 已生成 %s（%.2f MB）" % (out, os.path.getsize(out) / 1048576.0))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
