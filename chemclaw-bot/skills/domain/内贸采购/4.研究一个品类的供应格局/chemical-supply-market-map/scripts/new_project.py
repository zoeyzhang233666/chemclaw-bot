#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_project.py —— 建一个空项目骨架（产品无关）

用法
  python scripts/new_project.py --dir work/pvc-2026 \
      --product "PVC（聚氯乙烯）" --short PVC --cas 9002-86-2 \
      --region "中国大陆" --year 2025 [--forward 2026,2028] [--from-template]

产出
  work/pvc-2026/
  ├── project.json      唯一事实来源（含待填 TODO 标记）
  ├── plants.json       基地级产能表（含 1 行示例，填完即删）
  ├── companies.json    集团画像（含 1 行示例）
  ├── projects.json     项目表（含 1 行示例）
  ├── sources.json      可选：来源清单（也可直接写在 project.json）
  └── 采集说明.md        本项目的 lane 分工与写入约定（agent 协作时用）
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

PROJECT_TPL = {
    "schema_version": 3,
    "project_id": "",
    "product": {
        "name": "",
        "short": "",
        "aliases": [],
        "grades": "",
        "cas": "",
        "unit": "万吨/年",
        "price_unit": "元/吨（含税）",
        "hs_code": "",
    },
    "scope": {
        "geography": "中国大陆",
        "boundary": "TODO：写清统计边界（含什么、不含什么）",
        "base_year": 2025,
        "forward_years": [2026, 2028],
        "report_date": "",
        "data_cutoff": "",
        "basis_notes": [
            "TODO：列出本项目遇到的口径差异（例如全国产能有多套数字），并列展示不取平均。",
        ],
    },
    "buyer": {
        "applies": True,
        "volume_10kt": 5,
        "landed_price": 0,
        "freight": 150,
        "stock_days": 30,
        "grade": "",
        "delivery": "到厂价，含税",
        "note": "默认模拟值，可按实际采购量覆盖",
    },
    "metrics": {
        "capacity_total": None,
        "capacity_total_label": "全国产能",
        "capacity_total_source": "",
        "capacity_total_note": "",
        "capacity_forward": None,
        "capacity_forward_label": "预测年名义产能",
        "output": None,
        "output_alt": [],
        "utilization": None,
        "producers": None,
        "cr5": None,
        "cr5_forward": {},
        "sample_capacity": None,
        "sample_coverage": None,
        "price_now": None,
        "price_now_label": "",
        "drawdown": None,
        "export": None,
        "inventory": None,
    },
    "verdicts": [
        {
            "id": "V1",
            "title": "TODO：一句话结论",
            "evidence": "TODO：用数字+口径+来源写证据",
            "implication": "TODO：对采购意味着什么（要可执行）",
            "confidence": "中",
            "sources": [],
            "memo": "",
        }
    ],
    "routes": [],
    "routes_note": "",
    "markets": [],
    "region_meta": {},
    "activity_legend": {"A": "交易活跃 / 贸易商密集", "B": "中等活跃", "C": "低活跃 / 直供为主"},
    "prices": {
        "lines": [],
        "annual": [],
        "periods": [],
        "current": [],
        "outlook": {"base": "", "up": "", "down": "", "procurement": ""},
        "caveat": "价格为公开报价；年度均值用于理解周期位置，不作为结算依据。",
    },
    "strategies": [],
    "supplier_mix": [],
    "risks": [],
    "gaps": [],
    "dd": [],
    "scorecard": [],
    "sources": [],
}

PLANTS_TPL = [
    {
        "id": "P001",
        "company_id": "示例集团",
        "site": "示例基地",
        "province": "",
        "city": "",
        "lat": None,
        "lon": None,
        "route": "",
        "capacity_base": 0,
        "capacity_forward": 0,
        "product": "",
        "raw": "",
        "status": "在产",
        "listed": "",
        "source": "",
        "note": "示例行：填完真实数据后删除。capacity 单位见 project.json product.unit",
    }
]

COMPANIES_TPL = [
    {
        "id": "示例集团",
        "name": "示例集团（请改名或删除）",
        "code": "",
        "hq": "",
        "nature": "民营/国有/外资",
        "route": "",
        "capacity_base": 0,
        "capacity_forward": 0,
        "output_base": "未披露",
        "utilization": "数据缺口",
        "strengths": [],
        "risks": [],
        "procurement": "",
        "sources": [],
        "dd": [],
    }
]

PROJECTS_TPL = [
    {
        "id": "J001",
        "name": "示例项目（新建/扩建/技改/置换/搬迁）",
        "company_id": "示例集团",
        "province": "",
        "route": "",
        "capacity": 0,
        "capacity_retired": 0,
        "type": "新建",
        "status": "在建",
        "date": "2026-06",
        "year": 2026,
        "step": "",
        "net": None,
        "impact": "",
        "source": "",
    }
]

NOTE_TPL = """# 采集说明（{product}）

> 本文件由 new_project.py 生成，供主 agent 与子 agent 共用。填完可删。

## 唯一事实来源

- `project.json`：品类、口径、指标、工艺、策略、风险、缺口、尽调、评分、来源
- `plants.json`：基地级产能（**所有汇总、区域、集中度都从这张表算**）
- `companies.json`：集团画像（抽屉里的尽调卡）
- `projects.json`：新建/在建/拟建项目（时间线与净增还原）

## 三条硬规矩

1. **不估算**：拿不到就写「数据缺口」并在 `project.json.gaps` 登记（影响/补齐方式/优先级）。
2. **每个数字带来源**：`source` 填来源 ID（S1、S2…），`project.json.sources` 里必须有对应条目。
3. **毛产能 ≠ 净新增**：置换/搬迁项目必须填 `capacity_retired`，净影响无法确认就填 `net: null`。

## lane 分工建议（有子代理时）

| lane | 负责字段 | 落地文件 |
|---|---|---|
| 产能 | plants.json 全部 | `lanes/plants_01.json` |
| 画像 | companies.json | `lanes/companies_01.json` |
| 项目 | projects.json | `lanes/projects_01.json` |
| 价格 | project.json.prices | `lanes/prices.json` |
| 政策/合规 | risks / gaps | `lanes/risks.json` |

子代理**每 5 条就覆盖写一次文件**，不要把大 JSON 塞回对话。

## 交付前

```bash
python scripts/build_all.py --dir <项目目录>
python scripts/check_project.py --dir <项目目录>
```
"""


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description="新建供应格局研究项目")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--product", required=True, help="产品全名，如「PVC（聚氯乙烯）」")
    ap.add_argument("--short", default="", help="简称，用于文件名与标题")
    ap.add_argument("--cas", default="")
    ap.add_argument("--grades", default="", help="规格/等级，如「重质/轻质」")
    ap.add_argument("--region", default="中国大陆")
    ap.add_argument("--year", type=int, default=datetime.date.today().year - 1)
    ap.add_argument("--forward", default="", help="预测年份，逗号分隔，如 2026,2028")
    ap.add_argument("--unit", default="万吨/年")
    ap.add_argument("--price-unit", default="元/吨（含税）")
    ap.add_argument("--force", action="store_true", help="目录非空也覆盖骨架文件")
    args = ap.parse_args()

    out = os.path.abspath(args.dir)
    os.makedirs(out, exist_ok=True)
    existing = [f for f in os.listdir(out) if f.endswith(".json")]
    if existing and not args.force:
        raise SystemExit(f"目录已有 JSON 文件：{existing}\n确认要覆盖骨架请加 --force")

    today = datetime.date.today().strftime("%Y-%m-%d")
    short = args.short or args.product.split("（")[0]
    cfg = dict(PROJECT_TPL)
    cfg["project_id"] = os.path.basename(out)
    cfg["product"] = dict(PROJECT_TPL["product"])
    cfg["product"].update({"name": args.product, "short": short, "cas": args.cas,
                           "grades": args.grades, "unit": args.unit, "price_unit": args.price_unit})
    cfg["scope"] = dict(PROJECT_TPL["scope"])
    cfg["scope"].update({"geography": args.region, "base_year": args.year,
                         "report_date": today, "data_cutoff": today})
    if args.forward:
        years = [int(y.strip()) for y in args.forward.split(",") if y.strip().isdigit()]
        if years:
            cfg["scope"]["forward_years"] = years

    C.dump_json(os.path.join(out, "project.json"), cfg)
    C.dump_json(os.path.join(out, "plants.json"), {"plants": PLANTS_TPL})
    C.dump_json(os.path.join(out, "companies.json"), {"companies": COMPANIES_TPL})
    C.dump_json(os.path.join(out, "projects.json"), {"projects": PROJECTS_TPL})
    C.write_text(os.path.join(out, "采集说明.md"), NOTE_TPL.format(product=args.product))

    print(f"OK 已建立项目骨架 -> {out}")
    print("\n下一步：")
    print("  1) 填 project.json（product / scope / metrics / routes / sources 必填）")
    print("  2) 填 plants.json（先跑通 3–5 行，再批量补）")
    print(f"  3) python scripts/build_all.py --dir {args.dir} --check")
    print(f"  4) python scripts/build_all.py --dir {args.dir}")
    print(f"  5) python scripts/check_project.py --dir {args.dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
