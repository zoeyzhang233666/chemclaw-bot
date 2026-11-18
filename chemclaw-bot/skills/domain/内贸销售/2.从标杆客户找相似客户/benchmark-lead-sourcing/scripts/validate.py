#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate.py —— lane 文件结构体检（合并前跑）

检查：文件数与条数、必需字段缺失、区域越界、置信度枚举非法、未核实条数、相似逻辑缺失。
用法： python validate.py --dir <项目目录>
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_project, region_ok, norm_conf, setup_console  # noqa: E402

setup_console()

REQUIRED = ["公司", "细分行业", "省市", "需求点", "规模线索", "相似维度", "相似逻辑", "来源", "置信度"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    d = os.path.abspath(args.dir)
    cfg = load_project(d)
    provs = cfg.get("region", {}).get("provinces") or []
    raw = os.path.join(d, "leads_raw")
    files = sorted(p for p in glob.glob(os.path.join(raw, "*.json"))
                   if not os.path.basename(p).startswith("_"))
    hard = 0
    total = 0
    print(f"lane 文件 {len(files)} 个；区域白名单：{provs or '（未配置，跳过区域检查）'}")
    for p in files:
        base = os.path.basename(p)
        with open(p, "r", encoding="utf-8-sig") as fh:
            txt = fh.read().strip()
        if not txt:
            print(f"  !! 空文件 {base}")
            hard += 1
            continue
        try:
            data = json.loads(txt)
        except ValueError as exc:
            print(f"  !! 解析失败 {base}: {exc}")
            hard += 1
            continue
        if not isinstance(data, list):
            print(f"  !! 顶层不是数组 {base}")
            hard += 1
            continue
        total += len(data)
        miss, bad_prov, bad_conf, nosrc, nosim = Counter(), [], [], [], []
        for it in data:
            for k in REQUIRED:
                if not str(it.get(k, "")).strip():
                    miss[k] += 1
            loc = str(it.get("省市", ""))
            if provs and not region_ok(loc, provs):
                bad_prov.append(it.get("公司", "?"))
            if it.get("置信度") not in ("高", "中", "低"):
                bad_conf.append(f"{it.get('公司', '?')}:{it.get('置信度')}")
            if str(it.get("来源", "")).strip() in ("", "未核实"):
                nosrc.append(it.get("公司", "?"))
            if not str(it.get("相似逻辑", "")).strip():
                nosim.append(it.get("公司", "?"))
        conf = Counter(norm_conf(x.get("置信度")) for x in data)
        line = (f"  {base:34s} {len(data):3d} 条  高{conf.get('高', 0)}/中{conf.get('中', 0)}"
                f"/低{conf.get('低', 0)}")
        if miss:
            line += "  缺字段:" + ",".join(f"{k}×{v}" for k, v in miss.items())
            hard += 1
        if bad_prov:
            line += "  ⚠区域越界:" + ",".join(bad_prov[:3])
            hard += 1
        if bad_conf:
            line += "  ⚠置信度非法:" + ",".join(bad_conf[:3])
            hard += 1
        if nosrc:
            line += f"  未核实{len(nosrc)}"
        if nosim:
            line += f"  ⚠缺相似逻辑{len(nosim)}"
        print(line)
    print(f"合计原始条目 {total}")
    print("体检结论：" + ("通过（可进入抽检/合并）" if hard == 0 else f"发现 {hard} 处硬问题，建议修正后再合并"))
    return 0 if hard == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
