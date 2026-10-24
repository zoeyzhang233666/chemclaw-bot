# -*- coding: utf-8 -*-
"""区域价差对比 —— 共用计算层。

所有指标只在这里定义一次：HTML 与 Excel 都从 build_payload() 取数，
避免「网页一个数、表格另一个数」。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROAD_FACTOR = 1.28      # 陆路绕行系数（球面距离 → 公路里程）
WATER_FACTOR = 1.18     # 水运绕行系数（球面距离 → 航线里程）


def load(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance(region_a: dict, region_b: dict, mode: str) -> float:
    """返回估算运距（km），四舍五入到 10 km。"""
    if region_a["id"] == region_b["id"]:
        return 0.0
    d = haversine(region_a["lon"], region_a["lat"], region_b["lon"], region_b["lat"])
    factor = WATER_FACTOR if mode == "water" else ROAD_FACTOR
    return round(d * factor / 10) * 10


def region_index(data: dict) -> dict:
    return {r["id"]: r for r in data["regions"]}


def latest_series(data: dict) -> tuple[list[str], dict]:
    """取每个区域最后一个非空值（容忍尾部缺失）。"""
    dates = data["series"]["dates"]
    values = data["series"]["values"]
    latest = {}
    for rid, arr in values.items():
        for d, v in zip(reversed(dates), reversed(arr)):
            if v is not None:
                latest[rid] = {"date": d, "value": v}
                break
    return dates, latest


def latest_prices(data: dict) -> dict:
    _, latest = latest_series(data)
    return {rid: item["value"] for rid, item in latest.items()}


def spreads(data: dict, benchmark: str) -> list[dict]:
    """按日期对齐的价差序列：ΔP = P(region) − P(benchmark)。"""
    dates = data["series"]["dates"]
    values = data["series"]["values"]
    base = values[benchmark]
    out = []
    for i, d in enumerate(dates):
        row = {"date": d, "base": base[i]}
        for rid, arr in values.items():
            v = arr[i]
            row[rid] = None if (v is None or base[i] is None) else round(v - base[i], 1)
        out.append(row)
    return out


def stats(values: list[float | None]) -> dict:
    xs = [v for v in values if v is not None]
    if not xs:
        return {"n": 0}
    cur = xs[-1]
    srt = sorted(xs)
    return {
        "n": len(xs),
        "cur": cur,
        "mean": round(sum(xs) / len(xs), 1),
        "min": min(xs),
        "max": max(xs),
        "range": round(max(xs) - min(xs), 1),
        "pctl": round(100.0 * sum(1 for v in xs if v <= cur) / len(xs), 0),
    }


def build_payload(data: dict, benchmark: str | None = None) -> dict:
    ridx = region_index(data)
    benchmark = benchmark or data["meta"].get("benchmark", data["regions"][0]["id"])
    mode = data["meta"].get("default_mode", "water")

    modes = {m["id"]: m for m in data["freight"]["modes"]}
    # 运距矩阵：所有有序对
    matrix = {}
    for a in data["regions"]:
        for b in data["regions"]:
            entry = {"km": {}, "cost": {}}
            for mid, cfg in modes.items():
                if a["id"] == b["id"]:
                    entry["km"][mid] = 0
                    entry["cost"][mid] = 0
                    continue
                if mid == "water" and not (a.get("water_ok") and b.get("water_ok")):
                    # 内陆枢纽：水运需铁水/江海联运，不在本表计价
                    entry["km"][mid] = None
                    entry["cost"][mid] = None
                    continue
                km = distance(a, b, mid)
                surcharge = max(a.get("water_surcharge", 0), b.get("water_surcharge", 0)) if mid == "water" else 0
                entry["km"][mid] = km
                entry["cost"][mid] = round(km * cfg["rate"] + cfg.get("base", 0) + surcharge, 1)
            matrix[f"{a['id']}>{b['id']}"] = entry

    latest = latest_prices(data)
    sp = spreads(data, benchmark)
    latest_row = sp[-1]
    per_region = []
    for r in data["regions"]:
        rid = r["id"]
        arr = [row.get(rid) for row in sp]
        st = stats(arr)
        per_region.append({
            "id": rid,
            "name": r["name"],
            "price": latest.get(rid),
            "delta": None if rid == benchmark else latest_row.get(rid),
            "stats": st,
        })

    return {
        "meta": data["meta"],
        "regions": data["regions"],
        "series": data["series"],
        "freight": data["freight"],
        "modes": data["freight"]["modes"],
        "matrix": matrix,
        "benchmark": benchmark,
        "latest_spreads": latest_row,
        "region_stats": per_region,
        "narrative": data["narrative"],
    }


def write_json(payload: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    import sys

    data = load(sys.argv[1])
    p = build_payload(data)
    print("基准:", p["benchmark"])
    for row in p["region_stats"]:
        print(f'{row["name"]:<4} 价 {row["price"]:>6}  Δ {str(row["delta"]):>6}  统计 {row["stats"]}')
    print("\n运距 / 水运 / 汽运（自基准区出发）")
    base = p["benchmark"]
    for r in p["regions"]:
        if r["id"] == base:
            continue
        e = p["matrix"][f"{base}>{r['id']}"]
        print(f'{r["name"]:<4} km={e["km"]["water"]:>5}/{e["km"]["road"]:>5}  '
              f'cost={e["cost"]["water"]:>6}/{e["cost"]["road"]:>6}')
