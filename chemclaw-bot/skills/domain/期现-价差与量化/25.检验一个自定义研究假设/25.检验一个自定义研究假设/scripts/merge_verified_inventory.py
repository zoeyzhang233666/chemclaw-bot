# -*- coding: utf-8 -*-
"""merge_verified_inventory.py — 把「逐条回源核验通过」的库存序列合并进主库存文件。

规则
----
* 只接受 verification.json 里 status == "verified" 的记录（页面日期与库存总量都对上）。
* 输出统一列名；新增两列：
    provenance = "verified_mysteel_open_page"（逐条回源核验） 或 "live_crawl_2026-10-20"
    verified_at = 核验时间
* 与本次实时抓取的 3 周做重叠比对：数值必须一致，否则报冲突并不写入。
* 绝不插值、绝不补全缺失周：缺口就留空，由引擎记为「观察窗口不连续」。
"""
import argparse
import csv
import json
import os
from datetime import datetime


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", required=True, help="原始历史库存 CSV（asof,pub_ts,value,url）")
    ap.add_argument("--verification", required=True, help="verification.json")
    ap.add_argument("--live", default="", help="本次实时抓取 CSV（可选，用于重叠比对）")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    ver = json.load(open(a.verification, encoding="utf-8-sig"))
    ok = {(r["asof"]): r for r in ver["records"] if r["status"] == "verified"}
    vtime = ver.get("generated_at", "")

    with open(a.history, encoding="utf-8-sig") as f:
        hist = list(csv.DictReader(f))

    live = {}
    if a.live and os.path.exists(a.live):
        with open(a.live, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                live[r["asof"]] = r

    rows, conflicts = [], []
    for r in hist:
        asof = r["asof"]
        if asof not in ok:
            continue
        val = float(ok[asof]["value"])
        if asof in live and abs(float(live[asof]["total"]) - val) > 0.011:
            conflicts.append((asof, val, live[asof]["total"]))
            continue
        src = live.get(asof, {})
        rows.append({
            "asof": asof,
            "pub_ts": r.get("pub_ts", ""),
            "total": val,
            "east": src.get("east", ""),
            "south": src.get("south", ""),
            "jiangsu": src.get("jiangsu", ""),
            "zhejiang": src.get("zhejiang", ""),
            "guangdong": src.get("guangdong", ""),
            "fujian": src.get("fujian", ""),
            "sample_cov": src.get("sample_cov", ""),
            "title": src.get("title", ""),
            "url": ok[asof]["url"],
            "sha16": src.get("sha16", ""),
            "provenance": "verified_mysteel_open_page",
            "verified_at": vtime,
        })
    rows.sort(key=lambda x: x["asof"])
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    meta = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rows": len(rows), "first": rows[0]["asof"], "last": rows[-1]["asof"],
            "verified_ratio": ver.get("verified_ratio"), "conflicts": conflicts,
            "note": "仅收录逐条回源核验通过的记录；缺失周保持缺失，不插值。"}
    json.dump(meta, open(os.path.splitext(a.out)[0] + ".meta.json", "w", encoding="utf-8-sig"),
              ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
