#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch China province boundaries and convert to compact SVG paths. Output geo_cn.json ships with templates."""
import json
import os
import re
import urllib.request

URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "geo_cn.json")

NORM = {
    "北京市": "北京", "天津市": "天津", "河北省": "河北", "山西省": "山西",
    "内蒙古自治区": "内蒙古", "辽宁省": "辽宁", "吉林省": "吉林", "黑龙江省": "黑龙江",
    "上海市": "上海", "江苏省": "江苏", "浙江省": "浙江", "安徽省": "安徽",
    "福建省": "福建", "江西省": "江西", "山东省": "山东", "河南省": "河南",
    "湖北省": "湖北", "湖南省": "湖南", "广东省": "广东", "广西壮族自治区": "广西",
    "海南省": "海南", "重庆市": "重庆", "四川省": "四川", "贵州省": "贵州",
    "云南省": "云南", "西藏自治区": "西藏", "陕西省": "陕西", "甘肃省": "甘肃",
    "青海省": "青海", "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆",
    "台湾省": "台湾", "香港特别行政区": "香港", "澳门特别行政区": "澳门",
}


def rings(geom):
    t = geom["type"]
    if t == "Polygon":
        return [geom["coordinates"][0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode("utf-8"))

    feats, xs, ys = [], [], []
    for f in data["features"]:
        raw = f["properties"].get("name", "")
        name = NORM.get(raw, raw)
        if name in ("台湾", "香港", "澳门"):
            continue
        parts = []
        for ring in rings(f["geometry"]):
            if len(ring) < 4:
                continue
            step = max(1, len(ring) // 220)
            pts = ring[::step]
            if pts[-1] != ring[-1]:
                pts.append(ring[-1])
            seg = []
            for i, (lon, lat) in enumerate(pts):
                x, y = lon, -lat
                xs.append(x)
                ys.append(y)
                seg.append(("M" if i == 0 else "L") + "%.3f %.3f" % (x, y))
            seg.append("Z")
            parts.append("".join(seg))
        if parts:
            feats.append({"name": name, "d": "".join(parts)})

    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad, W, H = 8.0, 780.0, 640.0
    s = min((W - 2 * pad) / (maxx - minx), (H - 2 * pad) / (maxy - miny))
    ox = pad + ((W - 2 * pad) - (maxx - minx) * s) / 2 - minx * s
    oy = pad + ((H - 2 * pad) - (maxy - miny) * s) / 2 - miny * s

    def rep(m):
        x = float(m.group(2)) * s + ox
        y = float(m.group(3)) * s + oy
        return m.group(1) + "%.2f %.2f" % (x, y)

    for f in feats:
        f["d"] = re.sub(r"([ML])(-?\d+\.\d+) (-?\d+\.\d+)", rep, f["d"])

    out = {"viewBox": "0 0 %.0f %.0f" % (W, H), "features": feats}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print("provinces:", len(feats), "size:", os.path.getsize(OUT), "bytes")
    print("names:", ",".join(x["name"] for x in feats))


if __name__ == "__main__":
    main()
