# -*- coding: utf-8 -*-
"""prepare_geo.py — 下载并简化省界底图（带缓存与离线降级）

用法:
    python prepare_geo.py --dataset dataset.json --out geo_simplified.json
    python prepare_geo.py --dataset dataset.json --out geo.json --geojson my_boundaries.json

说明:
  - 默认从 DataV 公共 GeoJSON 拉取中国省级边界，按 dataset 的包围盒裁剪 + 抽稀
  - 结果缓存到 --cache（默认 geo_cache.json）；网络失败时优先用缓存
  - 完全无网络时输出空列表，报告仍可生成（地图只有半径环与点位，无底图）
  - 其他国家的项目：用 --geojson 传入自己的边界文件（FeatureCollection，WGS84）
"""
import argparse, json, math, os, ssl, sys, urllib.request

DATAV = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bbox_of(dataset, margin=2.4):
    pts = [(dataset["meta"]["origin"]["lon"], dataset["meta"]["origin"]["lat"])]
    for it in dataset.get("items", []):
        pts.append((it["lon"], it["lat"]))
    lons = [p[0] for p in pts]; lats = [p[1] for p in pts]
    return (min(lons) - margin, min(lats) - margin, max(lons) + margin, max(lats) + margin)


def simplify(pts, tol):
    if len(pts) <= 2:
        return pts

    def d2(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(x - x1, y - y1)
        t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))

    def dp(lo, hi, keep):
        if hi <= lo + 1:
            return
        dmax, idx = 0.0, lo
        for i in range(lo + 1, hi):
            d = d2(pts[i], pts[lo], pts[hi])
            if d > dmax:
                dmax, idx = d, i
        if dmax > tol:
            keep.add(idx); dp(lo, idx, keep); dp(idx, hi, keep)

    keep = {0, len(pts) - 1}
    dp(0, len(pts) - 1, keep)
    return [pts[i] for i in sorted(keep)]


def clip_rings(features, bbox, tol=0.03):
    x0, y0, x1, y1 = bbox
    out = []
    for f in features:
        geom = f.get("geometry") or {}
        if not geom:
            continue
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]] \
            if geom["type"] == "Polygon" else []
        rings_out = []
        for poly in polys:
            for ring in poly:
                pts = [[float(p[0]), float(p[1])] for p in ring]
                if not pts:
                    continue
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
                    continue
                s = simplify(pts, tol)
                if len(s) < 4:
                    continue
                s = [[round(min(max(p[0], x0 - 0.4), x1 + 0.4), 3),
                      round(min(max(p[1], y0 - 0.4), y1 + 0.4), 3)] for p in s]
                rings_out.append(s)
        if rings_out:
            out.append({"name": f["properties"].get("name", ""), "rings": rings_out})
    return out


def fetch(url, timeout=40):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 nearby-supplier-sourcing/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default="geo_simplified.json")
    ap.add_argument("--cache", default="", help="原始底图缓存路径，默认与 --out 同目录")
    ap.add_argument("--geojson", default="")
    ap.add_argument("--tol", type=float, default=0.03)
    args = ap.parse_args()

    if not args.cache:
        args.cache = os.path.join(os.path.dirname(os.path.abspath(args.out)) or ".", "geo_cache.json")

    ds = load_json(args.dataset)
    bbox = bbox_of(ds)

    src = None
    if args.geojson:
        src = load_json(args.geojson)
    elif os.path.exists(args.cache):
        src = load_json(args.cache)
        print(f"[geo] 使用缓存 {args.cache}")
    else:
        try:
            src = fetch(DATAV)
            with open(args.cache, "w", encoding="utf-8") as f:
                json.dump(src, f)
            print("[geo] 已下载省级边界并缓存")
        except Exception as e:
            print(f"[geo] 底图获取失败（{type(e).__name__}: {e}）→ 输出空底图，地图仍可用")

    feats = []
    if src:
        feats = clip_rings(src.get("features", []), bbox, args.tol)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(feats, f, ensure_ascii=False, separators=(",", ":"))
    pts = sum(len(r) for ft in feats for r in ft["rings"])
    print(f"[geo] 区域 {len(feats)} 个 / 顶点 {pts} / {os.path.getsize(args.out)} bytes → {args.out}")


if __name__ == "__main__":
    main()
