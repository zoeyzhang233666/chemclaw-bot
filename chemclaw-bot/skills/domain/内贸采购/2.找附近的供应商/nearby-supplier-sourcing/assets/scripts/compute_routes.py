# -*- coding: utf-8 -*-
"""compute_routes.py — 计算直线距离、公路里程与路径几何，并回填 dataset.json

用法:
    python compute_routes.py --dataset dataset.json                 # 默认 OSRM
    python compute_routes.py --dataset dataset.json --no-osrm       # 离线：直线×系数
    python compute_routes.py --dataset dataset.json --osrm-url http://127.0.0.1:5000

行为:
  - 计算 straight_km（haversine）、road_km、ratio、hours、geometry
  - OSRM 可用 → distance_source="osrm"；不可用 → "estimated"（系数见 logistics.fallback_factor）
  - 结果写回 dataset.json（幂等，可重复运行）
  - 同时产出 routes.json 供审计
"""
import argparse, json, math, ssl, sys, time, urllib.request

R = 6371.0088


def haversine(a, b):
    lat1, lon1 = a; lat2, lon2 = b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def osrm(base, a, b, timeout=45):
    url = (f"{base.rstrip('/')}/route/v1/driving/"
           f"{a[1]},{a[0]};{b[1]},{b[0]}?overview=simplified&geometries=geojson")
    req = urllib.request.Request(url, headers={"User-Agent": "nearby-supplier-sourcing/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("code") != "Ok":
        raise RuntimeError(d.get("code"))
    rt = d["routes"][0]
    geo = rt["geometry"]["coordinates"]
    return (round(rt["distance"] / 1000.0, 1),
            round(rt["duration"] / 3600.0, 2),
            [[round(c[0], 4), round(c[1], 4)] for c in geo])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default="routes.json")
    ap.add_argument("--osrm-url", default="http://router.project-osrm.org")
    ap.add_argument("--no-osrm", action="store_true", help="离线：公路=直线×系数")
    ap.add_argument("--factor", type=float, default=0.0, help="覆盖 logistics.fallback_factor")
    ap.add_argument("--sleep", type=float, default=1.1, help="OSRM 请求间隔（公共服务器请≥1s）")
    args = ap.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        ds = json.load(f)

    org = ds["meta"]["origin"]
    origin = (org["lat"], org["lon"])
    factor = args.factor or ds.get("logistics", {}).get("fallback_factor", 1.25)
    ok = fail = 0
    log = []

    for it in ds["items"]:
        target = (it["lat"], it["lon"])
        it["straight_km"] = round(haversine(origin, target), 1)
        real = None
        if not args.no_osrm:
            try:
                km, hrs, geo = osrm(args.osrm_url, origin, target)
                it.update(road_km=km, hours=hrs, geometry=geo, distance_source="osrm")
                real = True; ok += 1
            except Exception as e:
                print(f"[OSRM] {it.get('short')} 失败: {type(e).__name__} {e} → 降级估算")
                real = False; fail += 1
        if real is None or real is False:
            km = round(it["straight_km"] * factor, 1)
            it.update(road_km=km, hours=round(km / 60.0, 2), geometry=[],
                      distance_source="estimated",
                      distance_note=f"无路网数据，按直线×{factor} 估算")
        it["ratio"] = round(it["road_km"] / it["straight_km"], 2) if it["straight_km"] else None
        if it["straight_km"] < 5 and it.get("distance_source") == "osrm":
            it["short_haul"] = True
            it.setdefault("distance_note", "")
            it["distance_note"] = ("起终点同在园区范围内，公路里程受园区道路与门禁影响、参考意义有限；"
                                   "应优先确认是否可园区内短驳或管道输送")
        log.append({"id": it["id"], "short": it.get("short"), "straight_km": it["straight_km"],
                    "road_km": it["road_km"], "ratio": it["ratio"], "source": it["distance_source"]})
        print(f'{it.get("short","?"):<18} 直线 {it["straight_km"]:8.1f}  公路 {it["road_km"]:8.1f}  '
              f'系数 {it["ratio"]}  {it["distance_source"]}')

    with open(args.dataset, "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=1)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"origin": org, "items": log}, f, ensure_ascii=False, indent=1)

    print(f"\n完成：osrm {ok} / 降级 {fail}；已回填 {args.dataset}，审计 {args.out}")
    if fail and not args.no_osrm:
        print("提示：降级条目在报告中会标注“估算”，请勿当作路径规划结果引用。")


if __name__ == "__main__":
    main()
