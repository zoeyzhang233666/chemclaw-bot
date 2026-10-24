#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并 leads_raw/*.json -> leads.json（配置驱动，通用于任何化工品）。

用法：
    python merge_leads.py --dir <任务目录> [--raw leads_raw] [--out leads.json]

读取 <任务目录>/skill_config.json 中的：
  file_blocks     文件名前缀 -> 板块名（决定板块归属）
  strength_rules  关键词 -> 用量强度星级（决定 ★ 与优先级）

做四件事：
  1) 按归一化公司名去重（保留「置信度更高 / 来源是完整 URL / 来源更具体」的一条）
  2) 板块名规范化（去掉子代理可能带上的 "01_ " 前缀，并校验取值）
  3) 按 strength_rules 算用量强度、按 强度×2+置信度分 算优先级
  4) 把 _qa_report.json 的抽检结论标注进「来源」
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

DEFAULT_STRENGTH = [
    (5, ["改性沥青", "防水卷材", "自粘卷材", "公路养护", "沥青改性"]),
    (4, ["热熔胶", "压敏胶", "胶黏剂", "胶粘剂", "鞋底", "鞋材", "TPR", "充油"]),
    (3, ["改性塑料", "塑料改性", "TPE", "TPV", "电缆料", "电缆", "胶管", "母粒", "增韧"]),
    (2, ["卫材", "纸尿裤", "弹性膜", "玩具", "标签", "阻尼", "瑜伽"]),
]
CONF_SCORE = {"高": 3, "中": 2, "低": 0}
CONF_ORDER = {"高": 0, "中": 1, "低": 2}
CONF_ALIAS = {"中高": "中", "较高": "高", "较低": "低", "高置信": "高"}


def load_config(task_dir):
    path = os.path.join(task_dir, "skill_config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def strength_of(text, rules):
    for level, keys in rules:
        for k in keys:
            if k and k in text:
                return level
    return 2


def priority_of(conf, strength):
    score = strength * 2 + CONF_SCORE.get(conf, 2)
    if score >= 11:
        return "高"
    if score >= 9:
        return "中"
    return "低"


def norm(name):
    n = re.sub(r"[（(].*?[)）]", "", name or "")
    return re.sub(r"(股份有限公司|有限责任公司|有限公司|集团有限公司|集团|公司|股份)", "", n).strip()


def pick(d, *keys):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return ""


def clean_source(src):
    """URL 与紧跟其后的中文说明之间补空格。

    URL 的边界定义：遇空白、中文或全角标点即截断——否则「URL＋中文说明」会被整体当成链接。
    """
    return re.sub(r"(https?://[^\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef，。；;、）)】」》\"'（(「《]+)(?=（)", r"\1 ", src or "")


def load_qa(raw_dir):
    """读抽检报告，返回 (按来源索引, 按公司名索引)。

    按公司名回退是必要的：同一家公司在多个原始文件里可能带不同的来源，
    去重后留下的那条与抽检时的来源不一致，只按来源匹配会漏标。
    """
    path = os.path.join(raw_dir, "_qa_report.json")
    if not os.path.exists(path):
        return {}, {}
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    by_src, by_co = {}, {}
    for row in data if isinstance(data, list) else []:
        if row.get("可达") and row.get("主体一致"):
            continue
        note = (row.get("备注") or "抽检未通过").strip()
        url = (row.get("来源") or "").strip()
        if url:
            by_src[url] = note
        co = norm(row.get("公司") or "")
        if co:
            by_co[co] = note
    return by_src, by_co


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="任务目录")
    ap.add_argument("--raw", default="leads_raw")
    ap.add_argument("--out", default="leads.json")
    args = ap.parse_args()

    task_dir = os.path.abspath(args.dir)
    raw_dir = os.path.join(task_dir, args.raw)
    cfg = load_config(task_dir)
    file_blocks = cfg.get("file_blocks") or {}
    canon = set(file_blocks.values()) or {"其他"}
    rules = [(int(lv), ks) for lv, ks in (cfg.get("strength_rules") or DEFAULT_STRENGTH)]

    files = sorted(p for p in glob.glob(os.path.join(raw_dir, "*.json"))
                   if not os.path.basename(p).startswith("_"))
    if not files:
        sys.exit(f"没有找到原始线索文件：{raw_dir}/*.json")

    qa_src, qa_co = load_qa(raw_dir)
    leads, seen = [], {}

    def rank(conf, src):
        conf = CONF_ALIAS.get((conf or "中").strip(), (conf or "中").strip())
        url_ok = 0 if re.match(r"^https?://", (src or "").strip()) else 1
        return (CONF_ORDER.get(conf, 3), url_ok, -len(src or ""))

    for path in files:
        base = os.path.basename(path)
        block = next((v for k, v in sorted(file_blocks.items()) if base.startswith(k)), "")
        try:
            data = json.load(open(path, encoding="utf-8-sig"))
        except ValueError as e:
            print(f"  ! 跳过无法解析的文件 {base}: {e}")
            continue
        if isinstance(data, dict):
            data = data.get("leads", [])
        for item in data:
            name = pick(item, "公司", "公司名称", "企业")
            if not name:
                continue
            src = clean_source(pick(item, "来源", "来源URL", "线索来源") or "未核实")
            conf = CONF_ALIAS.get((pick(item, "置信度") or "中").strip(), (pick(item, "置信度") or "中").strip())
            if conf not in CONF_SCORE:
                conf = "中"

            key = norm(name)
            if key in seen:
                if rank(conf, src) >= rank(seen[key]["置信度"], seen[key]["来源"]):
                    continue
                leads.remove(seen[key])

            block_val = re.sub(r"^\s*\d{2}\s*[_、.．]\s*", "", (item.get("板块") or "").strip())
            if block_val not in canon:
                block_val = block if block in canon else sorted(canon)[0]
            sub = pick(item, "细分行业", "行业")
            demand = pick(item, "需求点", "需求点（用料环节）")
            strength = strength_of(f"{sub}{demand}{block_val}", rules)

            rec = {
                "板块": block_val,
                "细分行业": sub,
                "公司": name,
                "所在地": pick(item, "省市", "所在地", "地点") or "未标注",
                "用量强度": "★" * strength,
                "需求点": demand,
                "规模线索": pick(item, "规模线索", "规模"),
                "优先级": item.get("优先级") or priority_of(conf, strength),
                "置信度": conf,
                "来源": src,
            }
            note = qa_src.get(src) or qa_co.get(key)
            if note:
                rec["来源"] = f"{src}（⚠链接抽检：{note}）"
            leads.append(rec)
            seen[key] = rec

    out_path = os.path.join(task_dir, args.out)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(leads, fh, ensure_ascii=False, indent=1)

    print(f"合并完成：{len(leads)} 条（源文件 {len(files)} 个）-> {out_path}")
    for b, n in Counter(x["板块"] for x in leads).most_common():
        hi = sum(1 for x in leads if x["板块"] == b and x["优先级"] == "高")
        print(f"  {b}: {n} 条，其中高优先级 {hi}")
    print("置信度分布:", dict(Counter(x["置信度"] for x in leads)))
    print("优先级分布:", dict(Counter(x["优先级"] for x in leads)))
    print("用量强度分布:", dict(Counter(x["用量强度"] for x in leads)))
    unknown = sum(1 for x in leads if not re.match(r"^https?://", x["来源"]))
    print(f"来源非 URL（未核实）: {unknown} 条")
    print("地域分布:", dict(Counter((x["所在地"].split("/")[0] if "/" in x["所在地"] else x["所在地"]) for x in leads)))


if __name__ == "__main__":
    main()
