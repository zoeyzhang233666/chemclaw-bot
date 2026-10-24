# -*- coding: utf-8 -*-
"""数据契约校验：errors 阻断构建，warnings 提示修补。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402

REQ_TOP = ["meta", "regions", "series", "freight", "narrative"]
REQ_META = ["product", "spec", "unit", "basis", "asof", "title"]
REQ_NARR = ["conclusions", "method", "gaps", "disclaimer"]


def check(data: dict) -> tuple[list[str], list[str]]:
    e, w = [], []
    for k in REQ_TOP:
        if k not in data:
            e.append(f"缺少顶层键: {k}")
    if e:
        return e, w

    meta = data["meta"]
    for k in REQ_META:
        if not meta.get(k):
            e.append(f"meta 缺少: {k}")

    regions = data["regions"]
    if len(regions) < 2:
        e.append("regions 少于 2 个，无法比较")
    ids = [r.get("id") for r in regions]
    if len(set(ids)) != len(ids):
        e.append("regions.id 有重复")
    for r in regions:
        for k in ("id", "name", "hub", "lon", "lat", "price_conf"):
            if r.get(k) in (None, ""):
                e.append(f"region {r.get('id','?')} 缺少 {k}")
        if r.get("lon") is None or not (-180 <= float(r["lon"]) <= 180):
            e.append(f"region {r.get('id')} 经度异常")
        if r.get("lat") is None or not (-90 <= float(r["lat"]) <= 90):
            e.append(f"region {r.get('id')} 纬度异常")
        if "water_ok" not in r:
            w.append(f"region {r.get('id')} 缺少 water_ok，水运可达性默认按内陆处理")

    bench = meta.get("benchmark")
    if bench and bench not in ids:
        e.append(f"meta.benchmark={bench} 不在 regions 中")

    s = data["series"]
    dates = s.get("dates", [])
    values = s.get("values", {})
    if not dates:
        e.append("series.dates 为空")
    for rid, arr in values.items():
        if rid not in ids:
            e.append(f"series.values 含未知区域 {rid}")
        if len(arr) != len(dates):
            e.append(f"series.values.{rid} 长度 {len(arr)} ≠ 日期数 {len(dates)}")
    if set(values) != set(ids):
        w.append("series.values 的区域与 regions 不完全一致")
    if dates != sorted(dates):
        e.append("series.dates 未按升序排列")
    if not s.get("sources"):
        w.append("series.sources 为空，价格无法回溯")
    if s.get("gap_note") is None:
        w.append("缺少 series.gap_note：有断点却不说明会误导")

    f = data["freight"]
    modes = f.get("modes", [])
    if not modes:
        e.append("freight.modes 为空")
    for m in modes:
        if m.get("rate") is None:
            e.append(f"freight.mode {m.get('id')} 缺少 rate")
        if m.get("conf") not in ("高", "中", "低"):
            w.append(f"freight.mode {m.get('id')} 置信度不规范")

    n = data["narrative"]
    for k in REQ_NARR:
        if not n.get(k):
            e.append(f"narrative 缺少: {k}")
    if len(n.get("conclusions", [])) < 3:
        w.append("conclusions 少于 3 条，结论偏薄")
    if not n.get("judge_rules"):
        w.append("缺少 judge_rules：没有判读规则，读者只会看到价差数字")

    # 口径一致性提醒
    if any("送到" in r.get("price_basis", "") or "到厂" in r.get("price_basis", "") for r in regions) and \
       any("出厂" in r.get("price_basis", "") for r in regions):
        w.append("五区 price_basis 混合出厂/到厂，请确认已在 meta.basis_note 说明")
    return e, w


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    args = ap.parse_args()
    try:
        data = common.load(args.data)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] JSON 解析失败: {exc}")
        raise SystemExit(2)
    e, w = check(data)
    for x in e:
        print(f"[ERROR] {x}")
    for x in w:
        print(f"[WARN ] {x}")
    print(f"\n校验完成：{len(e)} error / {len(w)} warning")
    raise SystemExit(1 if e else 0)


if __name__ == "__main__":
    main()
