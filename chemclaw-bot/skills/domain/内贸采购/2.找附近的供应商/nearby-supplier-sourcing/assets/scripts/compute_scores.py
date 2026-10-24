# -*- coding: utf-8 -*-
"""compute_scores.py — 计算匹配总分、档位、物流分、运距等级与排序

用法:
    python compute_scores.py --dataset dataset.json

规则（见 references/scoring-model.md）:
  matchTotal = 五个维度之和（上限 100）
  tier       = 按 match.tiers 的分数下限（A≥85 / B 70–84 / C<70）
  lScore     = logistics.anchors 分段线性内插（按公路里程）
  band       = logistics.bands 区间标签
  rank       = 先档位后物流分降序（两者绝不相加）
"""
import argparse, json, sys


def interp(anchors, km):
    a = sorted(anchors, key=lambda x: x[0])
    if km <= a[0][0]:
        return float(a[0][1])
    if km >= a[-1][0]:
        return float(a[-1][1])
    for (k1, v1), (k2, v2) in zip(a, a[1:]):
        if k1 <= km <= k2:
            t = (km - k1) / float(k2 - k1)
            return round(v1 + t * (v2 - v1), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        ds = json.load(f)

    dims = [d["name"] for d in ds["match"]["dims"]]
    tiers = sorted(ds["match"]["tiers"], key=lambda x: -x["min"])
    anchors = ds["logistics"]["anchors"]
    bands = sorted(ds["logistics"].get("bands", []), key=lambda x: x["max"])

    for it in ds["items"]:
        total = sum(it["match"].get(d, 0) for d in dims)
        it["matchTotal"] = min(100, int(round(total)))
        it["tier"] = "C"; it["tierLabel"] = "证据不足"
        for t in tiers:
            if it["matchTotal"] >= t["min"]:
                it["tier"] = t["code"]; it["tierLabel"] = t.get("label", "")
                break
        km = it.get("road_km")
        if km is None:
            print(f"[score] {it.get('short')} 没有 road_km，请先运行 compute_routes.py")
            sys.exit(1)
        it["lScore"] = interp(anchors, km)
        it["band"] = next((b["label"] for b in bands if km <= b["max"]), bands[-1]["label"] if bands else "")

    order = {t["code"]: k for k, t in enumerate(tiers)}
    ds["items"].sort(key=lambda i: (order.get(i["tier"], 9), -i["lScore"], -i["matchTotal"]))
    for k, it in enumerate(ds["items"], 1):
        it["rank"] = k

    with open(args.dataset, "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=1)

    for it in ds["items"]:
        print(f'{it["rank"]:>2} {it["tier"]} {it["matchTotal"]:>3}  L{it["lScore"]:>5}  '
              f'{it["road_km"]:>7.1f}km  {it["band"]:<4} {it["short"]}')
    print(f'\n已写入 {args.dataset}（{len(ds["items"])} 家）')


if __name__ == "__main__":
    main()
