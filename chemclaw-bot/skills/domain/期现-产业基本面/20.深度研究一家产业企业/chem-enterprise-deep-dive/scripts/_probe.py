# -*- coding: utf-8 -*-
"""判断截图是否「渲染正常」：分块统计色彩多样性 / 文字行数 / 空白占比，无需人眼看图。
用法：python _probe.py shot1.png shot2.png ...
"""
import sys
from PIL import Image


def analyze(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    colors = {}
    rows_with_ink = 0
    step = max(1, w // 400)
    for y in range(0, h, 3):
        row_ink = 0
        for x in range(0, w, step):
            c = px[x, y]
            colors[c] = colors.get(c, 0) + 1
            if sum(c) < 720:  # 非纯白
                row_ink += 1
        if row_ink > 2:
            rows_with_ink += 1
    total = len(range(0, h, 3))
    top = sorted(colors.items(), key=lambda kv: -kv[1])[:6]
    return {"size": (w, h), "distinct_colors": len(colors),
            "ink_rows_ratio": round(rows_with_ink / max(total, 1), 3),
            "top_colors": ["#%02x%02x%02x=%d" % (c[0], c[1], c[2], n) for c, n in top]}


for p in sys.argv[1:]:
    print(p.split("\\")[-1], analyze(p))
