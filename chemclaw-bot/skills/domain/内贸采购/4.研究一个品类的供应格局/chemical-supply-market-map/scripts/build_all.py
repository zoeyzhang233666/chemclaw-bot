#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_all.py —— 一键从 project.json + plants/companies/projects.json 生成交付物

用法
  python scripts/build_all.py --dir examples/soda-ash-cn-2026
  python scripts/build_all.py --dir work/<项目> --html-only     # 没装 openpyxl 时
  python scripts/build_all.py --dir work/<项目> --excel-only
  python scripts/build_all.py --dir work/<项目> --check         # 只体检不出文件

产物（写在项目目录）
  <产品>供应格局全景_<年>.html     单文件、离线可开、可打印
  <产品>供应格局数据包_<年>.xlsx   多表工作簿（需 openpyxl）
  data_bundle.json                 渲染用数据包（便于排查/二次加工）

约定：所有产品差异都来自配置；脚本里不允许出现任何具体产品名。
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ASSETS = os.path.join(PKG, "assets")


# ================================================================== 组装数据
def build_bundle(directory):
    ds = C.load_dataset(directory)
    cfg, plants_raw, companies_raw, projects_raw = ds["cfg"], ds["plants"], ds["companies"], ds["projects"]

    plants = []
    for p in plants_raw:
        row = dict(p)
        row["province"] = p.get("province") or C.province_of(p.get("city")) or "未标注"
        row["capacity_base"] = C.num(p.get("capacity_base"))
        row["capacity_forward"] = C.num(p.get("capacity_forward"))
        row["status"] = C.norm_status(p.get("status") or C.infer_status(
            row["capacity_base"], row["capacity_forward"]))
        row["lat"] = p.get("lat")
        row["lon"] = p.get("lon")
        row["company_id"] = p.get("company_id") or p.get("company") or "未标注"
        row["source"] = p.get("source") or "未核实"
        plants.append(row)

    companies = C.company_rollup(plants, companies_raw)
    projects = C.project_rollup(projects_raw)
    regions = C.region_rollup(plants)

    metrics = dict(cfg["metrics"])
    sample_cap = sum(p["capacity_base"] for p in plants)
    sample_fwd = sum(p["capacity_forward"] for p in plants)
    metrics.setdefault("sample_capacity", sample_cap)
    national = C.num(metrics.get("capacity_total"))
    metrics["sample_coverage"] = C.coverage(sample_cap, national)
    metrics["sample_groups"] = len({p["company_id"] for p in plants})
    metrics["sample_sites"] = len(plants)
    metrics["hhi_industry"] = C.hhi([c["capacity_base"] for c in companies])
    metrics["cr5_computed"] = C.cr_n([c["capacity_base"] for c in companies], 5)
    metrics["hhi_region"] = C.hhi([r["capacity_base"] for r in regions])
    metrics["top4_region_share"] = round(sum(r["share_base"] for r in regions[:4]) * 100, 1)
    metrics["top5_region_share"] = round(sum(r["share_base"] for r in regions[:5]) * 100, 1)

    # 工艺结构：配置优先，缺失时按 plants 现算
    routes = []
    for r in cfg["routes"]:
        routes.append(dict(r))
    if not routes:
        agg = {}
        for p in plants:
            if not p.get("route"):
                continue
            agg.setdefault(p["route"], 0.0)
            agg[p["route"]] += p["capacity_base"]
        total = sum(agg.values()) or 1
        palette = ["#1d4ed8", "#b45309", "#0f766e", "#7c3aed", "#0891b2", "#be123c"]
        for i, (name, cap) in enumerate(sorted(agg.items(), key=lambda x: -x[1])):
            routes.append({"name": name, "cap": cap, "share": round(cap / total * 100, 1),
                           "color": palette[i % len(palette)], "producers": "", "raw": "",
                           "unit": "", "energy": "", "byproduct": "", "cost_low": None,
                           "cost_high": None, "advantage": "", "risk": ""})

    gaps = list(cfg["gaps"])
    if metrics["sample_coverage"] == C.MISSING:
        gaps.append({"gap": "全国产能合计", "impact": "无法计算样本覆盖率与 CR5",
                     "status": "未取得", "fill": "协会年报/统计年鉴/行业年度报告",
                     "priority": "高"})
    if any(p["lat"] is None or p["lon"] is None for p in plants):
        gaps.append({"gap": "部分基地经纬度", "impact": "地图气泡缺失（不估算坐标）",
                     "status": "未逐一取得", "fill": "企业官网/环评公示/地图检索，逐个登记",
                     "priority": "中"})

    bundle = {
        "meta": {
            "product": cfg["product"],
            "scope": cfg["scope"],
            "buyer": cfg.get("buyer", {}),
            "metrics": metrics,
            "routes_note": cfg.get("routes_note", ""),
            "activity_legend": cfg.get("activity_legend", {}),
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "schema_version": cfg.get("schema_version", 3),
            "skill_version": C.VERSION,
        },
        "verdicts": cfg["verdicts"],
        "routes": routes,
        "regions": regions,
        "region_meta": cfg["region_meta"],
        "companies": companies,
        "plants": plants,
        "projects": projects,
        "markets": cfg["markets"],
        "prices": cfg["prices"],
        "strategies": cfg["strategies"],
        "supplier_mix": cfg["supplier_mix"],
        "risks": cfg["risks"],
        "gaps": gaps,
        "dd": cfg["dd"],
        "scorecard": cfg["scorecard"],
        "sources": cfg["sources"],
    }
    return ds, bundle


def output_names(bundle, directory):
    prod = bundle["meta"]["product"]
    short = (prod.get("short") or prod.get("name") or "化工品").replace("/", "-")
    year = bundle["meta"]["scope"].get("base_year") or "2026"
    html = os.path.join(directory, f"{short}供应格局全景_{year}.html")
    xlsx = os.path.join(directory, f"{short}供应格局数据包_{year}.xlsx")
    return html, xlsx


# ================================================================== HTML
def write_html(bundle, out_path, excel_name=""):
    import _render
    css = open(os.path.join(ASSETS, "style.css"), encoding="utf-8").read()
    tpl = open(os.path.join(ASSETS, "template.html"), encoding="utf-8").read()
    js = open(os.path.join(ASSETS, "app.js"), encoding="utf-8").read()
    parts = _render.render_all(bundle, excel_name or "")
    html = tpl.replace("@@HEAD@@", render_head(bundle))
    for key, val in parts.items():
        html = html.replace(f"@@{key}@@", val)
    html = (html.replace("@@CSS@@", css)
                .replace("@@DATA_JSON@@", json.dumps(bundle, ensure_ascii=False, separators=(",", ":")))
                .replace("@@APP_JS@@", js))
    leftover = [t for t in ("@@HEAD@@", "@@CSS@@", "@@DATA_JSON@@", "@@APP_JS@@") if t in html]
    if leftover:
        raise SystemExit(f"模板 token 未替换：{leftover}")
    C.write_text(out_path, html)
    return len(html)


def render_head(bundle):
    meta = bundle["meta"]
    prod = meta["product"]
    short = prod.get("short") or prod.get("name")
    year = meta["scope"].get("base_year") or ""
    geo = meta["scope"].get("geography") or ""
    desc = (f"{prod.get('name')}供应格局研究（{geo}）：产能、区域、工艺、项目、价格与采购关注。"
            f"数据截止 {meta['scope'].get('data_cutoff') or '数据缺口'}；缺口明确标注，不做估算。")
    return (f'<meta name="description" content="{desc}">\n'
            f'<title>{short} · {geo}供应市场全景 | 采购视角 {year}</title>\n'
            f'<meta name="generator" content="chemical-supply-market-map v{C.VERSION}">')


# ================================================================== Excel
def _need_openpyxl():
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


def write_excel(bundle, out_path):
    import build_excel  # 延迟导入，--html-only 时不需要 openpyxl
    return build_excel.build(bundle, out_path)


# ================================================================== 主流程
def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description="生成供应格局 HTML + Excel")
    ap.add_argument("--dir", required=True, help="项目目录（含 project.json 等）")
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--excel-only", action="store_true")
    ap.add_argument("--check", action="store_true", help="只跑体检")
    ap.add_argument("--bundle-out", default="", help="额外输出 data_bundle.json 的路径")
    args = ap.parse_args()

    directory = os.path.abspath(args.dir)
    if not os.path.isdir(directory):
        raise SystemExit(f"目录不存在：{directory}")

    ds, bundle = build_bundle(directory)
    errors, warnings, stats = C.validate_dataset(ds)

    print("== 数据体检 ==")
    for k in ("plants", "companies", "projects", "sources", "routes", "gaps", "dd", "provinces"):
        print(f"  {k:10s} {stats.get(k)}")
    print(f"  {'样本产能':10s} {C.fmt_num(stats.get('sample_capacity'))} / 全国 "
          f"{C.fmt_num(bundle['meta']['metrics'].get('capacity_total'))}"
          f"  覆盖 {bundle['meta']['metrics'].get('sample_coverage')}%")
    for w in warnings:
        print(f"  [警告] {w}")
    for e in errors:
        print(f"  [错误] {e}")
    if errors:
        print("\n有错误，先修数据再出文件。")
        print("提示：骨架里的 plants.json 只有 1 行示例（capacity=0），"
              "填完真实产能与 sources 后再跑。字段说明见 references/data-model.md。")
        return 2
    if args.check:
        return 0

    html_path, xlsx_path = output_names(bundle, directory)
    made = []

    if not args.excel_only:
        size = write_html(bundle, html_path, os.path.basename(xlsx_path))
        made.append(("HTML", html_path, f"{size / 1024:.0f} KB"))

    if not args.html_only:
        if _need_openpyxl():
            size = write_excel(bundle, xlsx_path)
            made.append(("Excel", xlsx_path, f"{size / 1024:.0f} KB"))
        else:
            print("\n[跳过 Excel] 未安装 openpyxl：pip install -r requirements.txt")
            print("  仍可交付 HTML；或改用 Excel 模板手工填（templates/数据包模板.xlsx 不存在时忽略）。")

    bundle_out = args.bundle_out or os.path.join(directory, "data_bundle.json")
    C.dump_json(bundle_out, bundle)
    made.append(("数据包", bundle_out, "用于排查/二次加工"))

    print("\n== 已生成 ==")
    for kind, path, size in made:
        print(f"  [{kind}] {path}  ({size})")
    if warnings:
        print(f"\n提示：有 {len(warnings)} 条警告（多为数据缺口），已在报告的「数据与来源」里体现。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
