#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chain_layout.py — 产业链图谱布局引擎（单一实现，三处共用）

被 build_chain_html.py（把坐标注入浏览器渲染）、build_chain_xlsx.py（层级关系表）
与 tools/check_layout.py（几何自检）导入。浏览器端 assets/chain_graph.js 只负责
「按给定坐标绘制 + 交互」，不再自行推算行列，避免生成端与校验端几何漂移。

布局规则
--------
1. 列 = column 字段；节点只在同列内排布，同 column 的节点共享一个层级带。
2. 列内排序：node_role 所属 band → 显式 order → 名称；band 之间留白分区，
   使「原料 / 副产 / 中间体 / 单体 / 配方材料 / 替代品 / 终端」一眼可辨。
3. 列宽 = 该列最宽节点；列 x 累进；列间隙恒定，用作正交走线通道。
4. 边的三种形态：
   a. 相邻两列且两端 y 相同      → 直线
   b. 相邻两列（y 不同）或跨列    → 正交折线：出钩 → 垂直段 → 入钩；垂直段放在
      两列之间的某个通道上（可能不在紧邻间隙，以避开中间列的节点）
   c. 中间确有节点挡路且找不到通道 → 从绘图区上方/下方「绕行」，画布高度随之扩展
5. 同一通道内多条垂直段按槽位错开；标签放在垂直段中点外侧。

诊断：layout_report() 输出重叠/越界/边穿节点/垂直段重合计数。
"""

NODE_W_MIN = 192
NODE_W_MAX = 268
NODE_H = 56
ROW_GAP = 14
BAND_GAP = 22
COL_GAP = 72
PAD_X = 26
PAD_TOP = 58
PAD_BOTTOM = 44
HEADER_H = 32
TRACK_STEP = 9.0
DETOUR_MARGIN = 26.0
HOOK = 26.0

FS_TITLE = 12.5
FS_SUB = 10.0

BAND_ORDER = ["raw", "byproduct", "intermediate", "monomer", "auxiliary", "target",
              "compound", "article", "system", "derivative", "same_family", "substitute",
              "end_market"]


def _cw(ch):
    return 1.0 if ord(ch) > 0x2E7F else 0.56


def text_w(s, size):
    return sum(_cw(c) for c in str(s)) * size if s else 0.0


def node_title(n):
    return str(n.get("name") or n.get("id") or "")


def node_sub(n):
    cas = (n.get("cas") or {})
    if cas.get("value"):
        return "CAS " + str(cas["value"])
    return {"commodity": "化学品", "material": "材料", "application": "终端应用"}.get(
        n.get("node_class"), "")


def node_box(n):
    title, sub = node_title(n), node_sub(n)
    flags = n.get("missing_flags") or []
    w = max(text_w(title, FS_TITLE), text_w(sub, FS_SUB)) + 34 + (13 if flags else 0)
    w = max(NODE_W_MIN, min(NODE_W_MAX, w))
    h = NODE_H + (15 if len(title) > 24 else 0)
    return w, h


def _row_key(n):
    band = BAND_ORDER.index(n["node_role"]) if n.get("node_role") in BAND_ORDER else 99
    return (band, n.get("order") if n.get("order") is not None else 10 ** 6, node_title(n))


def build_layout(nodes, relations):
    nodes = [dict(n) for n in nodes]
    for n in nodes:
        if n.get("column") is None:
            n["column"] = n.get("layer", 0)
        n["column"] = int(n["column"])

    by_id = {n["id"]: n for n in nodes}
    cols = sorted({n["column"] for n in nodes})
    by_col = {c: sorted([n for n in nodes if n["column"] == c], key=_row_key) for c in cols}

    # ---------- 第一遍：列内行（先按内容区顶部对齐计算） ----------
    row_top, col_h = {}, {}
    for c in cols:
        y, prev_band = 0.0, None
        for n in by_col[c]:
            band = _row_key(n)[0]
            if prev_band is not None and band != prev_band:
                y += BAND_GAP
            w, h = node_box(n)
            row_top[n["id"]] = (y, w, h)
            y += h + ROW_GAP
            prev_band = band
        col_h[c] = y - ROW_GAP
    tallest = max(max(col_h.values()), 140)

    # ---------- 预留绕行空间：先粗略判断哪些边需要绕行 ----------
    # 简化：跨列边若两端列之间夹着「节点数不为 0」的列，就预留绕行带。
    detour_needed = 0
    for r in relations:
        fr, to = r.get("from"), r.get("to")
        if fr not in by_id or to not in by_id:
            continue
        ca, cb = by_id[fr]["column"], by_id[to]["column"]
        between = [c for c in cols if min(ca, cb) < c < max(ca, cb)]
        if between:
            detour_needed += 1
    top_band = (DETOUR_MARGIN + 18 * min(6, max(1, detour_needed // 4))) if detour_needed else 0.0
    bottom_band = top_band

    content_top = PAD_TOP + HEADER_H + top_band
    canvas_h = content_top + tallest + bottom_band + PAD_BOTTOM

    # ---------- 列 x ----------
    geo, col_x = {}, {}
    x = PAD_X
    for c in cols:
        col_w = max(row_top[n["id"]][1] for n in by_col[c])
        col_x[c] = (x, col_w)
        off = content_top + (tallest - col_h[c]) / 2.0
        for n in by_col[c]:
            y, w, h = row_top[n["id"]]
            geo[n["id"]] = {"x": x + (col_w - w) / 2.0, "y": off + y, "w": w, "h": h}
        x += col_w + COL_GAP
    canvas_w = x - COL_GAP + PAD_X
    col_idx = {c: i for i, c in enumerate(cols)}

    def gap_center(i):
        return col_x[cols[i]][0] + col_x[cols[i]][1] + COL_GAP / 2.0

    def rect_hit(x1, x2, y, skip):
        lo, hi = min(x1, x2), max(x1, x2)
        n = 0
        for nid, g in geo.items():
            if nid in skip:
                continue
            if g["x"] - 3 < hi and g["x"] + g["w"] + 3 > lo and g["y"] - 2 < y < g["y"] + g["h"] + 2:
                n += 1
        return n

    def has_free_lane(c, y, skip):
        """在第 c 个列间隙里，高度 y 处是否有走线空间（不与任何节点相交）。"""
        if c >= len(cols) - 1:
            return False
        tx = gap_center(c)
        return rect_hit(tx - 6, tx + 6, y, skip) == 0

    def _alloc_track(store, key, base, step, lo=None, hi=None, n_max=6):
        """在 store[key] 里为该用途分配一个唯一轨道 x：从 base 开始左右交替展开。"""
        used = store.setdefault(key, [])
        for i in range(n_max * 2):
            off = (i + 1) // 2 * step * (1 if i % 2 else -1)
            x = base + off
            if lo is not None and x < lo:
                continue
            if hi is not None and x > hi:
                continue
            if all(abs(x - u) > step * 0.5 for u in used):
                used.append(x)
                return x
        used.append(base)
        return base

    def seg_clear(x1, y1, x2, y2, skip):
        """正交段是否不与任何节点相交（竖线查 y 区间，横线查 x 区间）。"""
        for nid, g in geo.items():
            if nid in skip:
                continue
            l, r = g["x"] - 2, g["x"] + g["w"] + 2
            t, bt = g["y"] - 2, g["y"] + g["h"] + 2
            if abs(x1 - x2) < 0.5:                       # 竖线
                if l < x1 < r and min(y1, y2) < bt and max(y1, y2) > t:
                    return False
            elif abs(y1 - y2) < 0.5:                     # 横线
                if t < y1 < bt and min(x1, x2) < r and max(x1, x2) > l:
                    return False
        return True

    # ---------- 第二遍：边路由 ----------
    edges = []
    track_count, detour_count = {}, {"top": 0, "bottom": 0}

    for r in relations:
        fr, to = r.get("from"), r.get("to")
        if fr not in by_id or to not in by_id:
            continue
        A, B = geo[fr], geo[to]
        ca, cb = by_id[fr]["column"], by_id[to]["column"]
        y_a, y_b = A["y"] + A["h"] / 2.0, B["y"] + B["h"] / 2.0
        skip = (fr, to)

        # a. 同行相邻 → 直线
        if cb == ca + 1 and abs(y_a - y_b) < 2:
            edges.append({"id": r.get("id"), "from": fr, "to": to,
                          "d": "M %.1f %.1f L %.1f %.1f" % (A["x"] + A["w"], y_a, B["x"], y_b),
                          "straight": True, "label_x": (A["x"] + A["w"] + B["x"]) / 2.0,
                          "label_y": y_a - 6, "reversed": False, "route": "straight"})
            continue

        # a2. 相邻两列、但两端高度差超出通道内可正交化的范围 →
        #     在通道里做「双钩」：出钩上升/下降，再水平接入目标。避免斜线穿过中间节点。
        if cb == ca + 1:
            x1, x2 = A["x"] + A["w"], B["x"]
            if abs(y_a - y_b) <= COL_GAP * 0.6:
                tx = _alloc_track(track_count, ("elbow", col_idx[ca]), (x1 + x2) / 2.0, 6.0,
                                  lo=x1 + 8, hi=x2 - 6)
                if seg_clear(x1, y_a, tx, y_a, skip) and seg_clear(tx, y_a, tx, y_b, skip) \
                        and seg_clear(tx, y_b, x2, y_b, skip):
                    d = "M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f" % (
                        x1, y_a, tx, y_a, tx, y_b, x2, y_b)
                    edges.append({"id": r.get("id"), "from": fr, "to": to, "d": d,
                                  "straight": False, "label_x": tx,
                                  "label_y": (y_a + y_b) / 2.0, "reversed": False,
                                  "route": "elbow"})
                    continue

        forward = cb > ca
        if cb == ca:                       # 同列（配方归属、副产同行）：向右出→左回
            forward = True
        if forward:
            x_out, x_in = A["x"] + A["w"], B["x"]
            i_lo, i_hi = col_idx[ca], col_idx[cb] - 1
        else:
            x_out, x_in = A["x"], B["x"] + B["w"]
            i_lo, i_hi = col_idx[cb], col_idx[ca] - 1
        if i_hi < i_lo:
            i_lo = i_hi = max(0, col_idx[ca])
        i_hi = min(i_hi, len(cols) - 1)

        # b. 找通道：先找 cost=0 的；找不到就取最小 cost
        best = None
        for gi in range(i_lo, i_hi + 1):
            tx = gap_center(gi)
            if tx <= min(A["x"], B["x"]) or tx >= max(A["x"] + A["w"], B["x"] + B["w"]):
                continue
            xh1 = x_out + HOOK if forward else x_out - HOOK
            xh2 = x_in - HOOK if forward else x_in + HOOK
            if not forward:
                xh1 = min(xh1, max(x_in + 4, x_out - HOOK))
                xh2 = max(xh2, min(xh1 - 4, x_in + HOOK))
            cost = rect_hit(x_out, tx, y_a, skip) + rect_hit(tx, x_in, y_b, skip)
            if best is None or cost < best[0]:
                best = (cost, tx, gi, xh1, xh2)
            if cost == 0:
                break

        # ---- 主路径：逐列折线 + 台阶（近似直线观感，且按列间隙落地）----
        if forward:
            lane_cols = [c for c in range(col_idx[ca], col_idx[cb])
                         if c < len(cols) - 1]
            lane_ys = {}
            steps = []
            ok = True
            for k, c in enumerate(lane_cols):
                yk = y_a + (y_b - y_a) * (k / float(len(lane_cols)))
                if has_free_lane(c, yk, skip):
                    lane_ys[c] = yk
                    steps.append(yk)
                else:
                    ok = False
                    break
            if ok and lane_cols:
                # 槽位错开，避免多条边画在同一条垂直线上
                pts = [(A["x"] + A["w"], y_a)]
                prev_y = y_a
                for k, c in enumerate(lane_cols):
                    tx = gap_center(c)
                    band_key = ("sub", c) if r.get("relation_type") == "substitution" else ("mass", c)
                    slot = track_count.get(band_key, 0)
                    track_count[band_key] = slot + 1
                    if band_key[0] == "sub":
                        tx = tx + 26 + (slot % 3) * 9.0
                    else:
                        tx = tx + (slot % 3 - 1) * 2.5
                    yk = lane_ys[c]
                    xh_end = col_x[cols[c + 1]][0]
                    if abs(yk - prev_y) > 1:
                        # 竖向段：给它一个专属 x，避免与相邻列的肘形/梯子边共线
                        tx = _alloc_track(track_count, ("vseg", c),
                                          gap_center(c) - (COL_GAP / 2.0 - 30) ,
                                          5.0,
                                          lo=col_x[cols[c]][0] + col_x[cols[c]][1] + 6,
                                          hi=col_x[cols[c + 1]][0] - 8)
                    pts.append((tx, prev_y))
                    pts.append((tx, yk))
                    if c < len(lane_cols) - 1:
                        # 中间列：走满到下一列左边界，保持台阶连续
                        pts.append((xh_end, yk))
                    prev_y = yk
                last_y = pts[-1][1]
                if abs(y_b - last_y) >= 2:
                    # 最后一列：在目标列左侧做竖直折角 + 水平入射。
                    # 先向右移到通道中线，再竖到目标高度，再水平进入目标。
                    xm = _alloc_track(track_count, ("lastcol", col_idx[cb]), B["x"] - HOOK, 5.0)
                    made = (seg_clear(pts[-1][0], last_y, xm, last_y, skip)
                            and seg_clear(xm, last_y, xm, y_b, skip)
                            and seg_clear(xm, y_b, B["x"], y_b, skip))
                    if not made:
                        # 备选位置：紧贴目标列左边的两个窄槽
                        for cand in (B["x"] - 9.0, B["x"] - 16.0, B["x"] - 24.0):
                            if seg_clear(pts[-1][0], last_y, cand, last_y, skip) \
                                    and seg_clear(cand, last_y, cand, y_b, skip) \
                                    and seg_clear(cand, y_b, B["x"], y_b, skip):
                                xm, made = cand, True
                                break
                    if made:
                        pts.append((xm, last_y))
                        pts.append((xm, y_b))
                pts.append((B["x"], y_b))
                lane_ok = all(seg_clear(pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1], skip)
                              for k in range(len(pts) - 1))
                # 只要出现斜线段（dx 与 dy 同时非零），一律判为不合格，走兜底路由
                for k in range(len(pts) - 1):
                    if abs(pts[k][0] - pts[k + 1][0]) > 0.5 and abs(pts[k][1] - pts[k + 1][1]) > 0.5:
                        lane_ok = False
                if not lane_ok:
                    ok = False
            if ok and lane_cols:
                d = "M " + " L ".join("%.1f %.1f" % p for p in pts)
                edges.append({"id": r.get("id"), "from": fr, "to": to, "d": d,
                              "straight": False,
                              "label_x": gap_center(lane_cols[0]),
                              "label_y": (y_a + (steps[0] if steps else y_a)) / 2.0 - 8,
                              "reversed": False, "route": "ladder"})
                continue

        # ---- 兜底 1：单通道正交（来源在右侧往前跨列 / 目标在左侧回探）----
        if best is not None and best[0] == 0:
            cost, tx, gi, xh1, xh2 = best
            band_key = ("sub", gi) if r.get("relation_type") == "substitution" else ("mass", gi)
            slot = track_count.get(band_key, 0)
            track_count[band_key] = slot + 1
            if band_key[0] == "sub":
                tx = tx + 26 + (slot % 3) * 9.0
            else:
                tx += (slot % 3 - 1) * 2.5
            d = "M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f" % (
                x_out, y_a, xh1, y_a, tx, y_a, tx, y_b, xh2, y_b, x_in, y_b)
            edges.append({"id": r.get("id"), "from": fr, "to": to, "d": d, "straight": False,
                          "label_x": tx, "label_y": (y_a + y_b) / 2.0, "reversed": not forward,
                          "route": "orthogonal"})
            continue

        # ---- 兜底 2：绕行（从绘图区上方或下方整段穿过去）----
        n_top, n_bot = detour_count["top"], detour_count["bottom"]
        y_top = content_top - 10 - (n_top % 6) * 15
        y_bot = content_top + tallest + 12 + (n_bot % 6) * 15
        y_top = max(PAD_TOP + HEADER_H + 6, y_top)
        y_bot = min(canvas_h - 8, y_bot)
        y_route = y_top if abs(y_top - y_a) <= abs(y_bot - y_a) else y_bot
        if y_route == y_top:
            detour_count["top"] += 1
        else:
            detour_count["bottom"] += 1
        n_dt = track_count.get(("detour", col_idx[ca], forward), 0)
        track_count[("detour", col_idx[ca], forward)] = n_dt + 1
        dt_shift = (n_dt % 3) * 7.0
        if forward:
            vy_out, vy_in = x_out + HOOK + dt_shift, x_in - HOOK + dt_shift
        else:
            vy_out, vy_in = x_out - HOOK - dt_shift, x_in + HOOK - dt_shift
        vy_out = min(max(vy_out, PAD_X / 2.0), canvas_w - PAD_X / 2.0)
        vy_in = min(max(vy_in, PAD_X / 2.0), canvas_w - PAD_X / 2.0)
        d = "M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f" % (
            x_out, y_a, vy_out, y_a, vy_out, y_route, vy_in, y_route, vy_in, y_b)
        d += " L %.1f %.1f" % (x_in, y_b)
        edges.append({"id": r.get("id"), "from": fr, "to": to, "d": d, "straight": False,
                      "label_x": (vy_out + vy_in) / 2.0, "label_y": y_route - 6,
                      "reversed": not forward, "route": "detour"})

    return {
        "canvas": {"w": round(canvas_w, 1), "h": round(canvas_h, 1)},
        "columns": [{"col": c, "x": round(col_x[c][0], 1), "w": round(col_x[c][1], 1),
                     "label_x": round(col_x[c][0] + col_x[c][1] / 2.0, 1)} for c in cols],
        "nodes": [{"id": nid, "x": round(g["x"], 1), "y": round(g["y"], 1),
                   "w": round(g["w"], 1), "h": round(g["h"], 1)} for nid, g in geo.items()],
        "edges": edges,
    }


def _count_diagonals(edges):
    """统计非水平/垂直的斜线段（斜线最容易穿节点，应尽量为 0）。"""
    import re
    n = 0
    for e in edges:
        pts = [(float(a), float(b)) for a, b in re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", e["d"])]
        for k in range(len(pts) - 1):
            dx = abs(pts[k][0] - pts[k + 1][0])
            dy = abs(pts[k][1] - pts[k + 1][1])
            if dx > 0.5 and dy > 0.5:
                n += 1
    return n


def layout_report(nodes, relations):
    import re
    lay = build_layout(nodes, relations)
    boxes = {n["id"]: n for n in lay["nodes"]}
    ids = sorted(boxes)
    issues = {"overlap": [], "outside": [], "edge_through_node": [], "edge_collinear": []}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = boxes[ids[i]], boxes[ids[j]]
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if ox > 1 and oy > 1:
                issues["overlap"].append([ids[i], ids[j], round(ox, 1)])
    W, H = lay["canvas"]["w"], lay["canvas"]["h"]
    for nid, b in boxes.items():
        if b["x"] < 0 or b["y"] < 0 or b["x"] + b["w"] > W or b["y"] + b["h"] > H:
            issues["outside"].append(nid)
    for e in lay["edges"]:
        pts = [(float(a), float(b)) for a, b in re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", e["d"])]
        hit = set()
        for k in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[k], pts[k + 1]
            for t in (0.15, 0.35, 0.5, 0.65, 0.85):
                px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                for nid, b in boxes.items():
                    if nid in (e["from"], e["to"]):
                        continue
                    if b["x"] + 2 < px < b["x"] + b["w"] - 2 and b["y"] + 2 < py < b["y"] + b["h"] - 2:
                        hit.add(nid)
        for nid in hit:
            issues["edge_through_node"].append([e["id"], nid])
    segs = []
    for e in lay["edges"]:
        pts = [(float(a), float(b)) for a, b in re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", e["d"])]
        for k in range(len(pts) - 1):
            if abs(pts[k][0] - pts[k + 1][0]) < 0.5 and abs(pts[k][1] - pts[k + 1][1]) > 6:
                segs.append((e["id"], round(pts[k][0]),
                             min(pts[k][1], pts[k + 1][1]), max(pts[k][1], pts[k + 1][1])))
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if segs[i][1] == segs[j][1]:
                lo, hi = max(segs[i][2], segs[j][2]), min(segs[i][3], segs[j][3])
                if hi - lo > 6:
                    issues["edge_collinear"].append([segs[i][0], segs[j][0]])
    return {"canvas": lay["canvas"], "issues": issues,
            "counts": {"nodes": len(boxes), "edges": len(lay["edges"]),
                       "overlap": len(issues["overlap"]),
                       "outside": len(issues["outside"]),
                       "edge_through_node": len(issues["edge_through_node"]),
                       "edge_collinear": len(issues["edge_collinear"]),
                       "diagonal": _count_diagonals(lay["edges"]),
                       "detour": sum(1 for e in lay["edges"] if e.get("route") == "detour")}}


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    nd = json.load(open(sys.argv[1], encoding="utf-8"))["nodes"]
    rl = json.load(open(sys.argv[2], encoding="utf-8"))["relations"]
    rep = layout_report(nd, rl)
    print(json.dumps(rep["counts"], ensure_ascii=False))
    for k, v in rep["issues"].items():
        if v:
            print(k, v[:6])
