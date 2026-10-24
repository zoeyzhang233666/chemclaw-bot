#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_project.py —— 建项目骨架（project.json / benchmark_profile.json / report_notes.json 与目录）

产品无关：只把命令行输入落到配置里，其余内容（lane、判据、报告文案）由 agent 按
references/config-schema.md 填写。

用法
  python new_project.py --dir work/soda-ash --product "纯碱" \
      --benchmark "旗滨集团（601636）" --region "华东:山东,江苏,浙江,安徽,上海" \
      [--grades "重质/轻质"] [--aliases "碳酸钠,苏打"] [--lanes 10] [--customer-list 客户.xlsx]
"""
import argparse
import json
import os
import shutil
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TPL = os.path.join(ROOT, "templates")


def load_tpl(name, fallback):
    p = os.path.join(TPL, name)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    return fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="项目目录")
    ap.add_argument("--product", required=True, help="所售产品正式名")
    ap.add_argument("--benchmark", required=True, help="标杆客户")
    ap.add_argument("--region", required=True, help="区域，格式 名称:省1,省2,...（无冒号则省份留空待填）")
    ap.add_argument("--grades", default="", help="规格级别，如 重质/轻质/食品级")
    ap.add_argument("--aliases", default="", help="别名，逗号分隔")
    ap.add_argument("--lanes", type=int, default=10, help="占位 lane 条数（后续由 agent 填充）")
    ap.add_argument("--customer-list", default="", help="历史成交客户表（仅记录路径，供画像阶段使用）")
    ap.add_argument("--force", action="store_true", help="已存在 project.json 时覆盖")
    args = ap.parse_args()

    d = os.path.abspath(args.dir)
    for sub in ("leads_raw", "briefs", "tools"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)

    if ":" in args.region:
        label, prov = args.region.split(":", 1)
        provinces = [p.strip() for p in prov.replace("，", ",").split(",") if p.strip()]
    else:
        label, provinces = args.region, []

    pj_path = os.path.join(d, "project.json")
    if os.path.exists(pj_path) and not args.force:
        print(f"!! {pj_path} 已存在（用 --force 覆盖）")
        return 1

    project = load_tpl("project.json", {})
    project["project_id"] = os.path.basename(d)
    project.setdefault("product", {})
    project["product"].update({
        "name": args.product,
        "grades": args.grades or "（请填写规格/级别：如 工业级 / 食品级 / 重质 / 轻质）",
        "aliases": [a.strip() for a in args.aliases.replace("，", ",").split(",") if a.strip()],
        "use_summary": "（请填写：该产品在各下游工序中的身份与作用，一句话）",
    })
    project["region"] = {"label": label, "provinces": provinces}
    project.setdefault("benchmark", {})
    project["benchmark"]["name"] = args.benchmark
    project.setdefault("report", {})
    project["report"]["title"] = f"{args.product}（{label}）下游潜客开发地图 · 对标{args.benchmark}复制第二批"
    if args.customer_list:
        project["benchmark"]["customer_list_file"] = os.path.abspath(args.customer_list)

    if not project.get("lanes"):
        project["lanes"] = [{
            "id": f"{i:02d}", "name": f"待填-lane{i}", "block": "待填",
            "scope": "（细分范围）", "use_logic": "（用料逻辑：在哪个工序、起什么作用）",
            "strength": 3, "candidates": [], "clusters": "", "keywords": [],
        } for i in range(1, args.lanes + 1)]

    with open(pj_path, "w", encoding="utf-8") as fh:
        json.dump(project, fh, ensure_ascii=False, indent=2)

    for name in ("benchmark_profile.json", "report_notes.json"):
        dst = os.path.join(d, name)
        if not os.path.exists(dst):
            shutil.copyfile(os.path.join(TPL, name), dst)

    print(f"OK 项目已建立：{d}")
    print("  下一步（由 agent 完成，规范见 references/config-schema.md）：")
    print("   1) 研究标杆客户六要素 → 写 benchmark_profile.json（每行带证据 URL）")
    print(f"   2) 设计 {args.lanes} 条 lane 并填 project.json 的 lanes / strength_rules /"
          " peer_keywords / buckets / industry_map")
    print("   3) 写 report_notes.json（剔除名单、缺口与负结果）")
    print(f"   4) python {os.path.join(HERE, 'make_lane_briefs.py')} --dir {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
