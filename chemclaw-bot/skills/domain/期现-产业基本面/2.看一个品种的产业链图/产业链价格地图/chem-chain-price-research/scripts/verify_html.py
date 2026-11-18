#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_html.py —— 生成后的 HTML 产物校验（交付之前运行）

检查的是「交付物能不能被放心打开」这件事：

  1. 单文件自包含：不出现 http(s):// 的外部 src/href、@import、url(http...)、<iframe>。
  2. 内嵌数据可解析：<script id="chain-data"> 里的 JSON 必须能被 json.loads 读出来。
  3. 数据与源文件一致（可选，用 --source 指定 chain-data.json 时逐项比对）。
  4. 版式安全：节点卡片互不重叠、不超出画布、卡片内文本不溢出（用与生成器相同的字宽估算）。
  5. 连线两端都存在，没有孤立连线。
  6. 图上出现的每个价格数字，都能在数据集的原始记录里找到（防止手改 HTML 后数据对不上）。
  7. 页面必备区块齐全：核心结论、缺口清单、明细区、口径说明、数据日。

用法
  python verify_html.py out.html
  python verify_html.py out.html --source chain-data.json
退出码 0 = 通过；1 = 存在问题。
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chain_layout import node_size  # noqa: E402

EXTERNAL_PATTERNS = [
    (r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//""", "外部 src/href 引用"),
    (r"""@import\s+url""", "CSS @import"),
    (r"""url\(\s*["']?https?://""", "CSS url(http://...)"),
    (r"""<iframe\b""", "iframe"),
    (r"""<link\b[^>]*\brel=["']stylesheet""", "外链样式表"),
]

problems = []
notes = []


def fail(m):
    problems.append(m)


def note(m):
    notes.append(m)


def char_width(ch, size):
    return size if ord(ch) > 0x2E7F else size * 0.56


def text_width(text, size):
    return sum(char_width(c, size) for c in str(text))


def expected_size(n):
    """用共享布局引擎复算卡片尺寸，返回 (w, h)。"""
    probe = {
        "role": n.get("role", "material"),
        "name": n.get("name", ""),
        "price": n.get("price", ""),
        "unit": n.get("unit", ""),
        "basis": n.get("basis", ""),
        "gap_label": n.get("gapLabel", ""),
        "short": n.get("short", []),
    }
    return node_size(probe)


def extract_payload(html_text):
    m = re.search(r'<script id="chain-data" type="application/json">(.*?)</script>',
                  html_text, re.S)
    if not m:
        return None
    raw = m.group(1).replace("<\\/", "</")
    return json.loads(raw)


def check_geometry(lay):
    canvas = lay.get("canvas", {})
    W, H = canvas.get("w", 0), canvas.get("h", 0)
    nodes = lay.get("nodes", [])
    for n in nodes:
        if n["x"] < 0 or n["y"] < 0 or n["x"] + n["w"] > W + 1 or n["y"] + n["h"] > H + 1:
            fail("节点 %s 超出画布 (%.0f,%.0f,%.0fx%.0f) 画布 %.0fx%.0f"
                 % (n["id"], n["x"], n["y"], n["w"], n["h"], W, H))
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                fail("节点卡片重叠：%s 与 %s" % (a["id"], b["id"]))
    for n in nodes:
        ew, eh = expected_size(n)
        if abs(n["w"] - ew) > 1.0 or abs(n["h"] - eh) > 1.0:
            fail("节点 %s 卡片尺寸 %.0fx%.0f 与布局引擎复算结果 %.0fx%.0f 不一致"
                 % (n["id"], n["w"], n["h"], ew, eh))
        need = (max(text_width(n["name"], 17),
                    text_width(n["price"], 25) + text_width(n.get("unit", ""), 12.5) + 10,
                    text_width(n.get("basis", ""), 11.5)) if n["role"] != "application"
                else max([text_width(n["name"], 16), text_width(n.get("gapLabel", ""), 12.5)]
                         + [text_width(s, 12) for s in n.get("short", [])]))
        if need + 12 > n["w"] + 1:
            fail("节点 %s 文本宽度 %.0fpx 超出卡片宽度 %.0fpx（缩短名称/口径文案）"
                 % (n["id"], need + 12, n["w"]))
    return W, H


def check_links(lay):
    ids = {n["id"] for n in lay.get("nodes", [])}
    deg = {i: 0 for i in ids}
    for lk in lay.get("links", []):
        if lk.get("from") not in ids:
            fail("连线起点 %s 不存在" % lk.get("from"))
        if lk.get("to") not in ids:
            fail("连线终点 %s 不存在" % lk.get("to"))
        deg[lk.get("from")] = deg.get(lk.get("from"), 0) + 1
        deg[lk.get("to")] = deg.get(lk.get("to"), 0) + 1
        if not str(lk.get("d", "")).startswith("M "):
            fail("连线 %s→%s 缺少合法路径" % (lk.get("from"), lk.get("to")))
    for nid, d in deg.items():
        if d == 0:
            note("节点 %s 没有任何连线，检查是否漏画产业链关系" % nid)


def check_prices_in_records(lay):
    """图上标注的每个价格，必须在原始记录里出现。"""
    for n in lay.get("nodes", []):
        if n["role"] == "application":
            continue
        rows = n.get("rows") or []
        if not rows:
            fail("有价环节 %s 没有原始记录" % n["id"])
            continue
        vals = {str(r.get("price", "")) for r in rows}
        if n["price"] and n["price"] not in vals:
            fail("节点 %s 图上标注价「%s」不在其 %d 条原始记录中" % (n["id"], n["price"], len(rows)))
    for t in lay.get("tables", []):
        if not (t.get("rows") or []):
            fail("附加明细「%s」没有记录" % t.get("title"))


def check_required_blocks(html_text, lay):
    meta = lay.get("meta", {})
    checks = [
        ("核心结论", "核心结论"),
        ("完整报价明细", "完整报价明细"),
        ("口径说明", "口径、方法与缺口说明"),
        ("交互提示", "鼠标"),
    ]
    for name, token in checks:
        if token not in html_text:
            fail("页面缺少「%s」区块" % name)
    if lay.get("gaps") and "本次未取到授权价格的环节" not in html_text:
        fail("页面缺少缺口清单区块")
    d = meta.get("data_date", "")
    if d and d not in html_text:
        fail("页面正文没有出现数据日 %s" % d)
    if meta.get("unit") and meta["unit"] not in html_text:
        fail("页面正文没有出现价格单位 %s" % meta["unit"])


def compare_with_source(lay, data):
    if not data:
        return
    m1, m2 = lay.get("meta", {}), data.get("meta", {})
    for k in ("title", "data_date", "unit"):
        if str(m1.get(k, "")) != str(m2.get(k, "")):
            fail("meta.%s 与源文件不一致：「%s」≠「%s」" % (k, m1.get(k), m2.get(k)))
    src_nodes = {n["id"]: n for n in data.get("nodes", [])}
    out_nodes = {n["id"]: n for n in lay.get("nodes", [])}
    for nid, n in src_nodes.items():
        if nid not in out_nodes:
            fail("源文件节点 %s 没有出现在 HTML 中" % nid)
            continue
        o = out_nodes[nid]
        if str(n.get("price", "")) != str(o.get("price", "")):
            fail("节点 %s 价格与源文件不一致：「%s」≠「%s」" % (nid, o.get("price"), n.get("price")))
        if len(n.get("rows") or []) != len(o.get("rows") or []):
            fail("节点 %s 记录条数与源文件不一致：%d ≠ %d"
                 % (nid, len(o.get("rows") or []), len(n.get("rows") or [])))
    for nid in out_nodes:
        if nid not in src_nodes:
            fail("HTML 中出现源文件没有的节点 %s" % nid)


def main(argv=None):
    ap = argparse.ArgumentParser(description="校验生成的自包含产业链 HTML")
    ap.add_argument("html", help="待校验的 HTML")
    ap.add_argument("--source", help="原始 chain-data.json，用于逐项比对")
    args = ap.parse_args(argv)

    with open(args.html, "r", encoding="utf-8") as f:
        html_text = f.read()

    for pat, label in EXTERNAL_PATTERNS:
        hits = re.findall(pat, html_text, re.I)
        if hits:
            fail("存在%s：%s" % (label, hits[:3]))
    if html_text.count("<script") != html_text.count("</script>"):
        fail("<script> 标签不配对")
    if html_text.count("<details") and html_text.count("</details>"):
        pass  # details 由 JS 生成，这里不作要求

    try:
        lay = extract_payload(html_text)
    except Exception as e:  # noqa: BLE001
        fail("内嵌数据 JSON 无法解析：%s" % e)
        lay = None
    if lay is None:
        fail("找不到 <script id=\"chain-data\"> 数据块")

    if lay:
        node_keys = {"id", "name", "role", "x", "y", "w", "h", "price", "unit", "rows"}
        for n in lay.get("nodes", []):
            miss = node_keys - set(n.keys())
            if miss:
                fail("渲染节点 %s 缺字段 %s" % (n.get("id"), sorted(miss)))
        W, H = check_geometry(lay)
        check_links(lay)
        check_prices_in_records(lay)
        check_required_blocks(html_text, lay)
        note("画布 %.0fx%.0f · 节点 %d · 连线 %d · 明细行 %d"
             % (W, H, len(lay.get("nodes", [])), len(lay.get("links", [])),
                sum(len(n.get("rows") or []) for n in lay.get("nodes", []))
                + sum(len(t.get("rows") or []) for t in lay.get("tables", []))))
        if args.source:
            with open(args.source, "r", encoding="utf-8") as f:
                compare_with_source(lay, json.load(f))
        else:
            note("未提供 --source，跳过「HTML 与源数据一致」的比对")

    print("产物校验：%s" % args.html)
    for m in notes:
        print("  [信息] %s" % m)
    for m in problems:
        print("  [问题] %s" % m)
    if problems:
        print("结果：不通过（%d 项问题）" % len(problems))
        return 1
    print("结果：通过（0 项问题）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
