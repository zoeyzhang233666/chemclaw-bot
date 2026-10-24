# -*- coding: utf-8 -*-
"""approve_design.py — 冻结并签核研究设计（正式检验的闸门开关）。

用法：
  python approve_design.py --design build/research_design.formal.json \
      --by "用户（会话内确认）" --note "按本页默认口径执行；Q4–Q7 默认值即为确认值" \
      --data data/port_inventory_weekly.csv --data data/100ppi_sf.csv

行为：
  * 写入 approved=true / approved_at / approved_by / approval_state
  * 写入每条数据文件的 sha256 前 16 位（数据指纹），之后数据一改就能发现
  * 递增 version，旧文件另存为 *.prev.json —— 参数改动不可覆盖历史
"""
import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime


def sha16(p, n=16):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--by", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--data", nargs="*", default=[])
    a = ap.parse_args()
    d = json.load(open(a.design, encoding="utf-8-sig"))
    if os.path.exists(a.design):
        shutil.copyfile(a.design, os.path.splitext(a.design)[0] + ".prev.json")
    v = d.get("version", d.get("schema_version", "1.0"))
    try:
        major, minor = str(v).split(".")
        d["version"] = f"{major}.{int(minor)+1}"
    except Exception:                      # noqa: BLE001
        d["version"] = str(v)
    d["approved"] = True
    d["approval_state"] = "APPROVED_FROZEN"
    d["approved_by"] = a.by
    d["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    d["approval_note"] = a.note
    d["data_fingerprint"] = {os.path.basename(p): sha16(p) for p in a.data if os.path.exists(p)}
    json.dump(d, open(a.design, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
    print(json.dumps({"version": d["version"], "approved_at": d["approved_at"],
                      "fingerprint": d["data_fingerprint"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
