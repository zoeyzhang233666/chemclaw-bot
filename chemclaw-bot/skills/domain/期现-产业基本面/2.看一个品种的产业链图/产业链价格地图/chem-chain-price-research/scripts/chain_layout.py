#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chain_layout.py —— 产业链图布局引擎（生成器与校验器共用）

把 chain-data.json 变成带绝对坐标的渲染结构：按 stage 分列、层内垂直居中、
列宽按卡片内最长文本自适应。整套几何只有这一份实现，生成与校验都调用它，
避免「生成时算一套、校验时算另一套」。

被 build_chain_html.py（生成）与 verify_html.py（校验）导入。
"""

PALETTE = {
    "up": {"fill": "#eaf1fc", "stroke": "#6d9ee0", "text": "#1d4e8f", "band": "#eef3fb"},
    "mid": {"fill": "#e8f6ef", "stroke": "#4cb287", "text": "#12654a", "band": "#eef7f2"},
    "raw": {"fill": "#fdf3e2", "stroke": "#d9a03c", "text": "#7a5410", "band": "#fbf5ea"},
    "product": {"fill": "#f1ecfd", "stroke": "#8d72dc", "text": "#4b32a3", "band": "#f4effc"},
    "app": {"fill": "#fbf0e9", "stroke": "#d98a56", "text": "#8a4a1e", "band": "#fbf1eb"},
}
PALETTE_ORDER = ["up", "mid", "raw", "product", "app"]

MARGIN_X = 40
MARGIN_BOTTOM = 44
STAGE_HEADER_TOP = 44
STAGE_HEADER_H = 54
COL_GAP = 58
NODE_GAP = 30
COL_PAD = 18

# 字号（与前端渲染保持一致，改这里就要同步改 build_chain_html.py 的 APP_JS）
FS_NAME_M = 17.0
FS_PRICE = 25.0
FS_UNIT = 12.5
FS_BASIS = 11.5
FS_NAME_A = 16.0
FS_GAP = 12.5
FS_SHORT = 12.0
PAD_X = 34.0


def char_width(ch, size):
    """粗略字宽：CJK/全角按 1em，其余按 0.56em。"""
    return size if ord(ch) > 0x2E7F else size * 0.56


def text_width(text, size):
    return sum(char_width(c, size) for c in str(text or ""))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def node_size(node, default_unit=""):
    """返回 (w, h)：保证卡片内文本不换行、不溢出。"""
    role = node.get("role", "material")
    if role == "application":
        head = text_width(node.get("name", ""), FS_NAME_A)
        gap = text_width(node.get("gap_label", ""), FS_GAP)
        short = node.get("short") or []
        body = max([text_width(s, FS_SHORT) for s in short] or [0])
        w = clamp(max(head, gap, body) + PAD_X, 220, 460)
        h = 40 + 26 + 22 * max(1, len(short)) + 14
        return w, h

    unit = node.get("unit") or default_unit
    need = max(
        text_width(node.get("name", ""), FS_NAME_M),
        text_width(node.get("price", ""), FS_PRICE) + text_width(unit, FS_UNIT) + 10,
        text_width(node.get("basis", ""), FS_BASIS),
    )
    return clamp(need + PAD_X, 158, 320), 112


def build_layout(data):
    stages = data.get("stages") or [{"key": "all", "label": ""}]
    meta = data.get("meta") or {}
    unit_default = meta.get("unit", "")

    stage_style = {}
    for i, st in enumerate(stages):
        key = st.get("color") or PALETTE_ORDER[i % len(PALETTE_ORDER)]
        if key not in PALETTE:
            key = PALETTE_ORDER[i % len(PALETTE_ORDER)]
        stage_style[st["key"]] = PALETTE[key]

    grouped = {st["key"]: [] for st in stages}
    for node in data.get("nodes", []):
        grouped.setdefault(node.get("stage", stages[0]["key"]), []).append(node)

    colw, colh = {}, {}
    for st in stages:
        key = st["key"]
        sizes = [node_size(n, unit_default) for n in grouped.get(key, [])]
        colw[key] = max([s[0] for s in sizes] or [160])
        colh[key] = sum(s[1] for s in sizes) + NODE_GAP * max(0, len(sizes) - 1)

    canvas_w = MARGIN_X * 2 + sum(colw[st["key"]] for st in stages) + COL_GAP * (len(stages) - 1)
    inner_h = max([colh[st["key"]] for st in stages] or [120])
    canvas_h = STAGE_HEADER_TOP + STAGE_HEADER_H + inner_h + MARGIN_BOTTOM

    geo, columns = {}, []
    x = MARGIN_X
    for st in stages:
        key = st["key"]
        style = stage_style[key]
        columns.append({
            "x": x - COL_PAD, "y": STAGE_HEADER_TOP,
            "w": colw[key] + COL_PAD * 2,
            "h": STAGE_HEADER_H + inner_h + MARGIN_BOTTOM - 24,
            "label": st.get("label", ""),
            "band": style["band"],
            "labelX": x + colw[key] / 2.0,
            "labelY": STAGE_HEADER_TOP + 30,
        })
        y = STAGE_HEADER_TOP + STAGE_HEADER_H + (inner_h - colh[key]) / 2.0
        for node in grouped.get(key, []):
            w, h = node_size(node, unit_default)
            geo[node["id"]] = {"x": x + (colw[key] - w) / 2.0, "y": y, "w": w, "h": h}
            y += h + NODE_GAP
        x += colw[key] + COL_GAP

    links = data.get("links", [])
    out_map, in_map = {}, {}
    for lk in links:
        out_map.setdefault(lk["from"], []).append(lk)
        in_map.setdefault(lk["to"], []).append(lk)

    def spread(mapping, key, link, h):
        arr = mapping.get(key, [])
        k = len(arr)
        if k <= 1:
            return 0.0
        step = min(34.0, (h - 34.0) / (k - 1))
        return (arr.index(link) - (k - 1) / 2.0) * step

    render_links = []
    for lk in links:
        a, b = geo.get(lk["from"]), geo.get(lk["to"])
        if not a or not b:
            continue
        x1 = a["x"] + a["w"]
        y1 = a["y"] + a["h"] / 2.0 + spread(out_map, lk["from"], lk, a["h"])
        x2 = b["x"]
        y2 = b["y"] + b["h"] / 2.0 + spread(in_map, lk["to"], lk, b["h"])
        dx = max(30.0, (x2 - x1) * 0.45)
        d = "M %.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f" % (
            x1, y1, x1 + dx, y1, x2 - dx, y2, x2, y2)
        render_links.append({
            "d": d, "dash": lk.get("kind") == "dashed",
            "from": lk["from"], "to": lk["to"],
            "label": lk.get("label", ""),
            "lx": (x1 + x2) / 2.0, "ly": (y1 + y2) / 2.0 - 6,
        })

    render_nodes = []
    for node in data.get("nodes", []):
        g = geo.get(node["id"])
        if not g:
            continue
        style = stage_style.get(node.get("stage", stages[0]["key"]), PALETTE["up"])
        render_nodes.append({
            "id": node["id"],
            "name": node.get("name", node["id"]),
            "role": node.get("role", "material"),
            "x": round(g["x"], 1), "y": round(g["y"], 1),
            "w": round(g["w"], 1), "h": round(g["h"], 1),
            "fill": style["fill"], "stroke": style["stroke"], "text": style["text"],
            "price": node.get("price", ""),
            "unit": node.get("unit") or unit_default,
            "basis": node.get("basis", ""),
            "gapLabel": node.get("gap_label", "本次无授权报价"),
            "short": node.get("short") or [],
            "desc": node.get("desc", ""),
            "stage": node.get("stage", ""),
            "rows": [r for r in (node.get("rows") or []) if isinstance(r, dict)],
        })

    return {
        "canvas": {"w": round(canvas_w, 1), "h": round(canvas_h, 1)},
        "columns": columns,
        "nodes": render_nodes,
        "links": render_links,
        "stages": [{"key": st["key"], "label": st.get("label", "")} for st in stages],
        "stageStyle": stage_style,
        "tables": data.get("tables", []),
        "gaps": data.get("gaps", []),
        "notes": data.get("notes", {}),
        "meta": meta,
    }
