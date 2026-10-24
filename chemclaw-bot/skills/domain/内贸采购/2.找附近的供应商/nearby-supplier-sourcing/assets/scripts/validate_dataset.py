# -*- coding: utf-8 -*-
"""validate_dataset.py — 交付前数据校验（不通过就不要生成报告）

用法:
    python validate_dataset.py dataset.json [--strict]

检查项:
  结构   meta / hazmat / match.dims / logistics / items / disclaimer
  事实   id 唯一、坐标为数字且在合理范围、必须写 coord_note
  合规   每条证据必须有 level∈{A,B,C,D}/url/date/supports
  规则   工厂至少 1 条 A 或 2 条 B；匹配维度分不超过权重；至少 1 条缺口
  口径   distances 必须由脚本计算（存在 road_km/straight_km）
"""
import argparse, json, sys

LEVELS = {"A", "B", "C", "D"}
TYPECODES = {"factory", "warehouse", "registered", "trader"}
REQUIRED_ITEM = ["id", "name", "short", "role", "typeCode", "region", "address",
                 "lat", "lon", "coord_note", "match", "evidence", "gaps", "ask"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--allow-missing-distance", action="store_true",
                    help="首次校验时距离尚未计算，跳过该项")
    args = ap.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        ds = json.load(f)

    errs, warns = [], []

    # --- 结构 ---
    for k in ("meta", "hazmat", "match", "logistics", "items", "disclaimer"):
        if k not in ds:
            errs.append(f"缺少顶层字段 {k}")
    meta = ds.get("meta", {})
    for k in ("title", "product", "origin", "generated"):
        if k not in meta:
            errs.append(f"meta 缺少 {k}")
    org = meta.get("origin", {})
    if "lat" not in org or "lon" not in org:
        errs.append("meta.origin 缺少 lat/lon")
    if org and not org.get("is_example") and not org.get("note"):
        warns.append("origin 不是示例点，建议在 note 里写明地址来源")

    dims = {d["name"]: d["max"] for d in ds.get("match", {}).get("dims", [])}
    if not dims:
        errs.append("match.dims 为空")
    elif sum(dims.values()) != 100:
        warns.append(f"match.dims 权重合计 {sum(dims.values())}，通常应为 100")

    if not ds.get("logistics", {}).get("rings"):
        errs.append("logistics.rings 为空（至少给一个半径）")
    if not ds.get("items"):
        errs.append("items 为空")

    # --- 逐条 ---
    seen = set()
    for it in ds.get("items", []):
        tag = it.get("short") or it.get("id") or "?"
        for k in REQUIRED_ITEM:
            if k not in it:
                errs.append(f"[{tag}] 缺少字段 {k}")
        if it.get("id") in seen:
            errs.append(f"[{tag}] id 重复：{it.get('id')}")
        seen.add(it.get("id"))

        if it.get("typeCode") not in TYPECODES:
            errs.append(f"[{tag}] typeCode 非法：{it.get('typeCode')}")
        lat, lon = it.get("lat"), it.get("lon")
        if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
            errs.append(f"[{tag}] lat 非法：{lat}")
        if not isinstance(lon, (int, float)) or not (-180 <= lon <= 180):
            errs.append(f"[{tag}] lon 非法：{lon}")
        if not it.get("coord_note"):
            errs.append(f"[{tag}] 缺少 coord_note（坐标精度必须写明）")

        m = it.get("match", {})
        for name, mx in dims.items():
            v = m.get(name)
            if v is None:
                errs.append(f"[{tag}] 匹配维度缺失 {name}")
            elif not (0 <= v <= mx):
                errs.append(f"[{tag}] {name}={v} 超出权重 {mx}")

        ev = it.get("evidence", [])
        if not ev:
            errs.append(f"[{tag}] 没有证据")
        lv = {"A": 0, "B": 0, "C": 0, "D": 0}
        for e in ev:
            for k in ("claim", "kind", "source", "url", "date", "level", "supports"):
                if not e.get(k):
                    errs.append(f"[{tag}] 证据缺字段 {k}：{str(e.get('claim'))[:24]}")
            if e.get("level") in lv:
                lv[e["level"]] += 1
            else:
                errs.append(f"[{tag}] 证据 level 非法：{e.get('level')}")
        if it.get("typeCode") == "factory" and lv["A"] == 0 and lv["B"] < 2:
            # 用当前 match 分推导档位（不信任可能过期的 tier 字段）
            total = sum(it.get("match", {}).get(n, 0) for n in dims) if dims else 0
            tier_now = "C"
            for t in sorted(ds.get("match", {}).get("tiers", []), key=lambda x: -x["min"]):
                if total >= t["min"]:
                    tier_now = t["code"]; break
            msg = f"[{tag}] 工厂至少需要 1 条 A 级或 2 条 B 级证据（现有 A{lv['A']}/B{lv['B']}，合计 {total} 分）"
            if tier_now == "C":
                warns.append(msg + "；已归入 C 档（仅作参照），符合“弱证据不进主供”规则")
            else:
                errs.append(msg + f"；当前档位 {tier_now} — 请补证或下调评分至 C 档（<70）")

        if not it.get("gaps"):
            warns.append(f"[{tag}] 没有缺口——除非信息确实完备，否则视为查得不够深")
        if "road_km" not in it or "straight_km" not in it:
            if not args.allow_missing_distance:
                errs.append(f"[{tag}] 距离未计算，请先运行 compute_routes.py")

    if len(ds.get("items", [])) and ds.get("items"):
        total_gaps = sum(len(i.get("gaps", [])) for i in ds["items"])
        if total_gaps < len(ds["items"]) * 0.5:
            warns.append(f"缺口总数 {total_gaps} 偏少（<企业数一半），检查是否把不确定写成了确定")

    # --- 输出 ---
    print(f"items={len(ds.get('items',[]))}  errors={len(errs)}  warnings={len(warns)}")
    for w in warns:
        print("  WARN ", w)
    for e in errs:
        print("  ERROR", e)
    if errs:
        print("\n校验未通过：修正后重新生成报告。")
        sys.exit(1)
    print("\n校验通过。可以生成 HTML 与 Excel。")


if __name__ == "__main__":
    main()
