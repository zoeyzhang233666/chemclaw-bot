#!/usr/bin/env python3
"""build_anchors.py — 从期货日线序列计算真实“价格锚点”，输出可直接填入 research.json 的 spot 结构

为什么要它：期现入口页里的价格写成“约 2500”就是编数据。这个脚本把价格改为
「日期 + 收盘 + 区间分位 + 区间极值」的可复核事实，并保留来源与口径。

用法:
    python scripts/build_anchors.py raw/MA0_daily.json --name "甲醇期货主连" --symbol MA0 \
        --spec "不含税、含交割成本的主连拼接价" --region "郑商所" --tax 不含税 \
        --out anchors.json

输入 JSON 支持两种形态：
    {"rows": [{"d":"YYYY-MM-DD","o":..,"h":..,"l":..,"c":..,"v":..,"oi":..}, ...], ...}
    或 [ {"date":..,"close":..}, ... ]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load_rows(p: Path):
    raw = json.loads(p.read_text(encoding="utf-8-sig"))
    rows = raw.get("rows") if isinstance(raw, dict) else raw
    out = []
    for r in rows:
        d = r.get("d") or r.get("date")
        c = r.get("c") if r.get("c") is not None else r.get("close")
        if d and c is not None:
            out.append({"d": str(d)[:10], "c": float(c), "v": r.get("v"), "oi": r.get("oi")})
    out.sort(key=lambda x: x["d"])
    return out


def pctile(vals, v):
    return 100.0 * sum(1 for x in vals if x <= v) / len(vals)


def anchor(rows, n, label, name, unit="元/吨", spec="", region="", tax="不含税"):
    win = rows[-n:] if n else rows
    vals = [x["c"] for x in win]
    last = win[-1]
    return {
        "name": f"{name}（{label}）",
        "value": f"{last['c']:.0f}",
        "unit": unit,
        "spec": spec,
        "region": region,
        "tax": tax,
        "date": last["d"],
        "pctile": f"{pctile(vals, last['c']):.0f}%",
        "range": f"{min(vals):.0f}–{max(vals):.0f}",
        "n": len(win),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--name", default="期货主连")
    ap.add_argument("--symbol", default="")
    ap.add_argument("--spec", default="")
    ap.add_argument("--region", default="")
    ap.add_argument("--tax", default="不含税")
    ap.add_argument("--src", default="", help="来源 id，如 S22")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    rows = load_rows(Path(a.raw))
    if not rows:
        raise SystemExit("序列为空")
    spans = [("历史全样本", 0), ("近3年", 756), ("近1年", 252), ("近3月", 63), ("近20日", 20)]
    anchors = []
    for label, n in spans:
        if n and len(rows) < n:
            continue
        x = anchor(rows, n, label, a.name, spec=a.spec, region=a.region, tax=a.tax)
        x["src"] = [a.src] if a.src else []
        anchors.append(x)

    vol = [x["v"] for x in rows[-20:] if x.get("v")]
    oi = [x["oi"] for x in rows[-20:] if x.get("oi")]
    summary = {
        "symbol": a.symbol,
        "first": rows[0]["d"],
        "last": rows[-1]["d"],
        "n": len(rows),
        "last_close": rows[-1]["c"],
        "all_min": min(x["c"] for x in rows),
        "all_max": max(x["c"] for x in rows),
        "avg_volume_20d": round(sum(vol) / len(vol), 0) if vol else None,
        "avg_oi_20d": round(sum(oi) / len(oi), 0) if oi else None,
        "anchors": anchors,
    }
    txt = json.dumps(summary, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
        print(f"[build_anchors] → {a.out}")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
