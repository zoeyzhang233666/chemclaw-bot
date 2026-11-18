#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_leads.py —— 合并各 lane 线索（去重、打分、区域与同行过滤、注入抽检结论）

用法
  python merge_leads.py --dir <项目>                  # 正式合并 -> leads.json
  python merge_leads.py --dir <项目> --make-qa-todo   # 生成 leads_raw/_qa_todo.json（供链接抽检）

过滤：区域白名单（region.provinces）、同行（peer_keywords）、跨 lane 去重（归一化公司名）。
保留：配置 extra_fields 指定的额外字段（默认 相似维度 / 相似逻辑）。
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (block_of, load_project, load_qa, norm_conf, norm_name,  # noqa: E402
                     priority_of, region_ok, strength_of, urls_of, is_peer, setup_console)

setup_console()

DEFAULT_EXTRA = ["相似维度", "相似逻辑"]


def pick(d, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


def read_lanes(raw_dir, cfg):
    files = sorted(p for p in glob.glob(os.path.join(raw_dir, "*.json"))
                   if not os.path.basename(p).startswith("_"))
    out = []
    for path in files:
        base = os.path.basename(path)
        with open(path, "r", encoding="utf-8-sig") as fh:
            txt = fh.read().strip()
        if not txt:
            print(f"  !! 空文件跳过：{base}")
            continue
        try:
            data = json.loads(txt)
        except ValueError as exc:
            print(f"  !! 解析失败跳过 {base}: {exc}")
            continue
        if isinstance(data, dict):
            data = data.get("leads") or data.get("data") or []
        out.append((base, block_of(cfg, base), data))
    return files, out


def make_qa_todo(d, cfg, raw_dir, qa_size):
    files, lanes = read_lanes(raw_dir, cfg)
    cn, other = [], []
    for _, _, data in lanes:
        for it in data:
            if not isinstance(it, dict):
                continue
            for u in urls_of(str(it.get("来源", ""))):
                row = {"公司": pick(it, "公司", "公司名称"), "来源": u,
                       "类型": "cninfo" if "cninfo.com.cn" in u else "HTML"}
                (cn if row["类型"] == "cninfo" else other).append(row)

    def dedup(rows):
        seen, out = set(), []
        for r in rows:
            if r["来源"] in seen:
                continue
            seen.add(r["来源"])
            out.append(r)
        return out

    cn, other = dedup(cn), dedup(other)
    quota = max(qa_size - len(other), 1)
    step = max(len(cn) // quota, 1)
    todo = cn[::step][:quota] + other
    path = os.path.join(raw_dir, "_qa_todo.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(todo, fh, ensure_ascii=False, indent=1)
    print(f"抽检清单：cninfo {len(cn)} 条 / 非 cninfo {len(other)} 条 → 抽 {len(todo)} 条 -> {path}")
    print("  下一步： python scripts/fetch.py check --file "
          f"{path} --out {os.path.join(raw_dir, '_qa_report.json')}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--make-qa-todo", action="store_true", help="只生成抽检清单，不合并")
    ap.add_argument("--qa-size", type=int, default=40, help="抽检目标条数")
    args = ap.parse_args()
    d = os.path.abspath(args.dir)
    raw_dir = os.path.join(d, "leads_raw")
    cfg = load_project(d)
    provs = cfg.get("region", {}).get("provinces") or []
    extra = cfg.get("extra_fields") or DEFAULT_EXTRA

    if args.make_qa_todo:
        return make_qa_todo(d, cfg, raw_dir, args.qa_size)

    files, lanes = read_lanes(raw_dir, cfg)
    if not files:
        raise SystemExit(f"没找到线索文件：{raw_dir}/*.json")

    qa = load_qa(raw_dir)
    leads, seen = [], {}
    total_in = dedup_dropped = 0
    out_region, peers = [], []

    for base, block, data in lanes:
        total_in += len(data)
        for item in data:
            if not isinstance(item, dict):
                continue
            name = pick(item, "公司", "公司名称", "企业")
            if not name:
                continue
            loc = pick(item, "省市", "所在地", "地点", default="未标注")
            if not region_ok(loc, provs):
                out_region.append(name)
                continue
            sub = pick(item, "细分行业", "行业")
            if is_peer(sub, cfg) or item.get("是否同行") is True:
                peers.append(name)
                continue
            conf = norm_conf(pick(item, "置信度", default="中"))
            strength = strength_of(sub, cfg)
            rec = {
                "板块": item.get("板块") or block,
                "细分行业": sub,
                "公司": name,
                "所在地": loc,
                "用量强度": "★" * strength,
                "需求点": pick(item, "需求点", "需求点（用酸环节）", "需求点（用料工序）"),
                "规模线索": pick(item, "规模线索", "规模"),
                "置信度": conf,
                "优先级": item.get("优先级") or priority_of(conf, strength, cfg),
                "来源": pick(item, "来源", "来源URL", "线索来源", default="未核实"),
            }
            for f in extra:
                if f in item:
                    rec[f] = item[f]
            note = qa.get(rec["来源"])
            if note:
                rec["来源"] = f"{rec['来源']}（⚠链接抽检：{note}）"

            key = norm_name(name)
            if key in seen:
                order = {"高": 0, "中": 1, "低": 2}
                dedup_dropped += 1
                if order[conf] >= order[seen[key]["置信度"]]:
                    continue
                leads.remove(seen[key])
            leads.append(rec)
            seen[key] = rec

    out_path = os.path.join(d, "leads.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(leads, fh, ensure_ascii=False, indent=1)

    print(f"合并完成：{len(leads)} 条（lane 文件 {len(files)} 个，原始条目 {total_in} 条，"
          f"去重丢弃 {dedup_dropped} 条）")
    if out_region:
        print(f"  区域外剔除 {len(out_region)} 条 -> {', '.join(out_region[:8])}")
    if peers:
        print(f"  同行剔除 {len(peers)} 条 -> {', '.join(peers[:8])}")
    for b, n in Counter(x["板块"] for x in leads).most_common():
        hi = sum(1 for x in leads if x["板块"] == b and x["优先级"] == "高")
        print(f"  {b}: {n} 条，其中高优先级 {hi}")
    print("  置信度：", dict(Counter(x["置信度"] for x in leads)))
    print("  用量强度：", dict(Counter(x["用量强度"] for x in leads)))
    miss_sim = sum(1 for x in leads if not x.get("相似逻辑")) if "相似逻辑" in extra else 0
    print(f"  缺相似逻辑：{miss_sim} 条")
    print(f"  无来源(未核实)：{sum(1 for x in leads if x['来源'] in ('', '未核实'))} 条")
    print(f"  条数守恒校验：{len(leads)} = {total_in} - {dedup_dropped}(去重) - "
          f"{len(out_region)}(区域) - {len(peers)}(同行)")
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
