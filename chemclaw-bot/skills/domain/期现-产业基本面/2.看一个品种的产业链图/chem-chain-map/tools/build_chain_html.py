#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_chain_html.py — 从 data/ 目录生成自包含交互式产业链图谱 HTML。

用法：
    python build_chain_html.py --data-dir examples/sbs/data --out out/sbs_chain.html
        [--title "SBS 产业链图谱"] [--open]

产物特点：
  · 单文件、无外链、无 CDN、离线可用（CSS/JS/SVG 全部内联）；
  · 坐标由 tools/chain_layout.py 预先算好并注入（LAYOUT），浏览器只绘制与交互，
    因此「生成端几何」与「校验端几何」完全一致；
  · 布局失败（重叠/穿线/越界）时自动降级：保留完整层级关系表与全部证据，
    不会因为画不出来就丢数据。

数据契约见 references/03-data-contract.md。
"""
import argparse
import datetime as _dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")   # ../assets 与 tools 同级
sys.path.insert(0, HERE)
import chain_layout as CL  # noqa: E402

REL_TYPE_META = {
    "conversion":    {"zh": "原料转化", "color": "#5b9dff"},
    "coproduction":  {"zh": "联产",     "color": "#8f7bff"},
    "byproduct":     {"zh": "副产",     "color": "#c07bff"},
    "substitution":  {"zh": "替代",     "color": "#ff8a5b"},
    "blend":         {"zh": "配方共混", "color": "#39d0a6"},
    "processing":    {"zh": "成型加工", "color": "#2fb8c6"},
    "application":   {"zh": "终端应用", "color": "#f2c14e"},
    "route_option":  {"zh": "工艺路线", "color": "#9aa7bd"},
    "packaging":     {"zh": "包装",     "color": "#7d8899"},
}

QUANT_STATUS_ZH = {
    "stoichiometric": "化学计量级",
    "stoichiometric_derived": "化学计量推算",
    "commercial_grade": "工业单耗（有口径）",
    "formulation": "配方比",
    "industrial_range_literature": "文献区间",
    "byproduct_yield_range": "副产收率区间",
    "missing": "缺口（未估算）",
    "not_applicable": "不适用",
}


def load_json(d, name, default=None):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _items(doc, key):
    if doc is None:
        return []
    if isinstance(doc, list):
        return doc
    return doc.get(key) or []


def coverage_block(data_dir):
    """复用 validate_chain 的覆盖算法，保证 HTML/Excel/校验三处口径一致。"""
    try:
        import validate_chain as V
        doc = V.load_all(data_dir)
        return V.compute_coverage(doc)
    except Exception as e:                      # noqa: BLE001
        return {"error": "覆盖率计算失败：%s" % e,
                "overall": {"passed": 0, "total": 0, "rate": 0.0}}


def build(data_dir, out_path, title=None, skip_layout_check=False):
    nodes_doc = load_json(data_dir, "nodes.json", {"nodes": []})
    rels_doc = load_json(data_dir, "relations.json", {"relations": []})
    nodes = _items(nodes_doc, "nodes")
    rels = _items(rels_doc, "relations")
    meta = load_json(data_dir, "meta.json", {}) or {}
    sources = _items(load_json(data_dir, "sources.json", {}), "sources")
    ents = _items(load_json(data_dir, "enterprises.json", {}), "enterprises")
    projs = _items(load_json(data_dir, "projects.json", {}), "projects")
    events = _items(load_json(data_dir, "events.json", {}), "events")
    prices = load_json(data_dir, "prices_verified.json", {}) or {}
    core = load_json(data_dir, "core_checklist.json", {}) or {}
    forbidden = _items(load_json(data_dir, "forbidden_links.json", {}), "forbidden")
    columns = nodes_doc.get("columns") or []

    # ---------- 布局 ----------
    report = CL.layout_report(nodes, rels) if not skip_layout_check else {"counts": {}, "issues": {}}
    counts = report.get("counts", {})
    layout_failed = bool(counts.get("overlap") or counts.get("outside")
                         or counts.get("edge_through_node") or counts.get("diagonal"))
    layout = CL.build_layout(nodes, rels)

    cov = coverage_block(data_dir)

    payload = {
        "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": title or (meta.get("title") or "产业链知识图谱"),
        "chain": meta,
        "columns": columns or [{"col": c["col"], "label": "第 %d 列" % c["col"]} for c in layout["columns"]],
        "nodes": nodes,
        "relations": rels,
        "sources": sources,
        "enterprises": ents,
        "projects": projs,
        "events": events,
        "prices": prices,
        "coverage": cov,
        "core": core,
        "forbidden": forbidden,
        "layout": layout,
        "relTypeMeta": REL_TYPE_META,
        "quantStatusZh": QUANT_STATUS_ZH,
        "layoutStatus": {
            "ok": not layout_failed,
            "counts": counts,
        },
    }

    tpl = os.path.join(ASSETS, "chain.html.tpl")
    with open(tpl, encoding="utf-8") as f:
        html = f.read()

    css = open(os.path.join(ASSETS, "chain.css"), encoding="utf-8").read()
    js = open(os.path.join(ASSETS, "chain_graph.js"), encoding="utf-8").read()
    html = html.replace("/*__CHAIN_CSS__*/", css)
    html = html.replace("//__CHAIN_JS__", js)
    data_json = json.dumps(payload, ensure_ascii=False)
    html = html.replace("/*__CHAIN_DATA__*/null", data_json)
    html = html.replace("__CHAIN_TITLE__", payload["title"])

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("HTML  : %s  (%.1f KB)" % (out_path, os.path.getsize(out_path) / 1024.0))
    print("节点  : %d   关系：%d   来源：%d   价格序列：%d"
          % (len(nodes), len(rels), len(sources), len(prices.get("series") or [])))
    print("布局  : %s %s" % ("通过" if not layout_failed else "降级为表格模式", counts))
    ov = (payload["coverage"] or {}).get("overall") or {}
    print("覆盖  : %.1f%% (%s/%s)" % (ov.get("rate", 0), ov.get("passed", 0), ov.get("total", 0)))
    if layout_failed:
        print("提示  : 布局自检未通过，页面会自动以「层级关系表」为主视图，数据不丢失。", file=sys.stderr)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--skip-layout-check", action="store_true")
    args = ap.parse_args()
    build(args.data_dir, args.out, args.title, args.skip_layout_check)


if __name__ == "__main__":
    main()
