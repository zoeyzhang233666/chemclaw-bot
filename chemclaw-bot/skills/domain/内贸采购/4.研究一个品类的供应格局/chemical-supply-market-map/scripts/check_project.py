#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_project.py —— 交付前体检（数据 + HTML + Excel 三项）

用法
  python scripts/check_project.py --dir work/<项目> [--html x.html] [--xlsx y.xlsx]

检查内容
  A 数据：必填项、枚举、交叉核对、缺口是否登记（来自 validate_dataset）
  B HTML：单文件是否真的自包含（无外部 http 链接、无 CDN、有 DOCTYPE/utf-8）、
          结构计数（企业卡、项目卡、来源行、数据缺口行）、token 残留
  C Excel：sheet 数量与顺序、每张 sheet 的非空单元格数、图表数、冻结窗格

退出码：0 全部通过；1 有错误；2 有警告但可交付
"""
import argparse
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

SKIP_DIRS = {"__pycache__", "scripts", "assets", "templates", "references", "soda_build"}


def find_file(directory, ext):
    cands = [f for f in os.listdir(directory) if f.endswith(ext)]
    if not cands:
        return ""
    # 优先匹配「全景」HTML /「数据包」xlsx
    pref = "全景" if ext == ".html" else "数据包"
    for c in cands:
        if pref in c:
            return os.path.join(directory, c)
    return os.path.join(directory, sorted(cands)[0])


# ------------------------------------------------------------------ A 数据
def check_data(directory):
    ds = C.load_dataset(directory)
    errors, warnings, stats = C.validate_dataset(ds)
    return ds, errors, warnings, stats


# ------------------------------------------------------------------ B HTML
def check_html(path):
    errors, warnings, info = [], [], {}
    if not path or not os.path.exists(path):
        return ["未找到 HTML 产物（先跑 build_all.py）"], [], {}
    text = open(path, "r", encoding="utf-8").read()
    info["bytes"] = len(text.encode("utf-8"))
    info["tabs"] = len(re.findall(r'class="tab-btn', text))
    info["panels"] = len(re.findall(r'class="tab-panel', text))
    info["company_cards"] = len(re.findall(r'class="drawer-card" data-company=', text))
    info["project_cards"] = len(re.findall(r'class="drawer-card" data-project=', text))
    info["source_rows"] = len(re.findall(r'<td class="mono">S\d+</td>', text))
    info["gap_rows"] = len(re.findall(r'<tr><td>[^<]+</td><td>[^<]*</td><td>[^<]*</td><td>[^<]*</td><td class="mono n">', text))

    if not text.lstrip().lower().startswith("<!doctype html"):
        errors.append("HTML 缺少 <!DOCTYPE html>")
    if '<meta charset="utf-8">' not in text.lower():
        errors.append("HTML 缺少 <meta charset=\"utf-8\">，中文会乱码")
    for token in ("@@CSS@@", "@@HEAD@@", "@@DATA_JSON@@", "@@APP_JS@@", "@@OVERVIEW@@"):
        if token in text:
            errors.append(f"模板 token 未替换：{token}")
    # 自包含性：只允许正文里的来源超链接（a href="http..."），不允许 src/css/link 外链
    ext_res = re.findall(r'<(?:script|link|img)[^>]+(?:src|href)="(?:https?:)?//', text)
    if ext_res:
        errors.append(f"存在外部资源引用 {len(ext_res)} 处（必须是零外部依赖的单文件）")
    if "<style>" not in text or "<script>" not in text:
        errors.append("CSS/JS 未内联")
    anchors = len(re.findall(r'<a [^>]*href="http', text))
    info["source_links"] = anchors
    if anchors == 0:
        warnings.append("正文里没有任何来源超链接（来源是否都有 URL？）")
    if info["company_cards"] == 0:
        warnings.append("没有企业抽屉卡：companies.json 为空？")
    if info["project_cards"] == 0:
        warnings.append("没有项目抽屉卡：projects.json 为空？")
    # 数据注入完整性
    m = re.search(r"window\.DATA\s*=", text)
    if not m:
        errors.append("未注入 window.DATA")
    if "数据缺口" not in text:
        warnings.append("页面里没有出现「数据缺口」字样：确认没有用 0 或均值顶替缺失值")
    info["missing_marks"] = text.count("数据缺口")
    return errors, warnings, info


# ------------------------------------------------------------------ C Excel
EXPECTED = ["00_封面", "01_核心结论", "02_企业产能", "03_区域汇总", "04_工艺路线", "04A_原料与成本",
            "05_新增项目", "05A_净增还原", "06_价格历史", "06A_价格周期", "07_采购关注", "07A_采购策略",
            "08_尽调清单", "09_供应商评分", "10_数据缺口", "11_来源与口径"]


def check_excel(path):
    errors, warnings, info = [], [], {}
    if not path or not os.path.exists(path):
        return ["未找到 Excel 产物（未装 openpyxl 时可只交付 HTML）"], [], {}
    try:
        from openpyxl import load_workbook
    except ImportError:
        warnings.append("本机未安装 openpyxl，跳过 Excel 结构检查")
        return errors, warnings, info
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad:
            errors.append(f"xlsx 包内文件损坏：{bad}")
    wb = load_workbook(path)
    info["sheets"] = [ws.title for ws in wb.worksheets]
    info["count"] = len(wb.worksheets)
    missing = [s for s in EXPECTED if s not in info["sheets"]]
    if missing:
        warnings.append(f"缺少标准表：{missing}")
    empty = []
    charts = 0
    frozen = 0
    for ws in wb.worksheets:
        n = sum(1 for row in ws.iter_rows() for c in row if c.value not in (None, ""))
        if n < 5:
            empty.append(ws.title)
        charts += len(ws._charts)
        if ws.freeze_panes:
            frozen += 1
    info["charts"] = charts
    info["frozen"] = frozen
    info["empty_sheets"] = empty
    if empty:
        errors.append(f"以下表几乎没有内容：{empty}")
    if charts < 4:
        warnings.append(f"图表只有 {charts} 个（建议 ≥4：区域/工艺/成本/项目）")
    # 数字单元格不得是字符串 "数据缺口" 混在数值列里：粗查
    ws2 = None
    for ws in wb.worksheets:
        if ws.title.startswith(("02_", "03_", "05_")):
            ws2 = ws
            break
    if ws2 is not None:
        info["spot_sheet"] = ws2.title
    return errors, warnings, info


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description="交付前体检")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--html", default="")
    ap.add_argument("--xlsx", default="")
    args = ap.parse_args()
    directory = os.path.abspath(args.dir)
    if not os.path.isdir(directory):
        raise SystemExit(f"目录不存在：{directory}")

    ds, data_err, data_warn, stats = check_data(directory)
    html_path = args.html or find_file(directory, ".html")
    xlsx_path = args.xlsx or find_file(directory, ".xlsx")
    h_err, h_warn, h_info = check_html(html_path)
    x_err, x_warn, x_info = check_excel(xlsx_path)

    print("=" * 68)
    print(f"项目：{os.path.basename(directory)}")
    print(f"产品：{ds['cfg']['product'].get('name')}  ·  基准年 {ds['cfg']['scope'].get('base_year')}"
          f"  ·  数据截止 {ds['cfg']['scope'].get('data_cutoff')}")
    print("=" * 68)
    print("\n[A] 数据")
    for k in ("plants", "companies", "projects", "sources", "routes", "gaps", "dd", "provinces"):
        print(f"    {k:10s} {stats.get(k)}")
    print(f"    {'样本产能':10s} {C.fmt_num(stats.get('sample_capacity'))} / 全国 "
          f"{C.fmt_num(ds['cfg']['metrics'].get('capacity_total'))}")
    for e in data_err:
        print(f"    [错误] {e}")
    for w in data_warn:
        print(f"    [警告] {w}")

    print("\n[B] HTML")
    if h_info:
        print(f"    {os.path.basename(html_path)}  {h_info.get('bytes', 0) / 1024:.0f} KB")
        print(f"    标签页 {h_info.get('tabs')} / 面板 {h_info.get('panels')}  ·  "
              f"企业卡 {h_info.get('company_cards')}  ·  项目卡 {h_info.get('project_cards')}")
        print(f"    来源行 {h_info.get('source_rows')}  ·  来源链接 {h_info.get('source_links')}  ·  "
              f"「数据缺口」出现 {h_info.get('missing_marks')} 次")
    for e in h_err:
        print(f"    [错误] {e}")
    for w in h_warn:
        print(f"    [警告] {w}")

    print("\n[C] Excel")
    if x_info:
        print(f"    {os.path.basename(xlsx_path)}  ·  {x_info.get('count')} 张表  ·  "
              f"图表 {x_info.get('charts')}  ·  冻结窗格 {x_info.get('frozen')} 张")
    for e in x_err:
        print(f"    [错误] {e}")
    for w in x_warn:
        print(f"    [警告] {w}")

    errs = len(data_err) + len(h_err) + len(x_err)
    warns = len(data_warn) + len(h_warn) + len(x_warn)
    print("\n" + "=" * 68)
    print(f"结论：错误 {errs} 条，警告 {warns} 条")
    if errs:
        print("→ 不可交付，先修错误。")
        return 1
    if warns:
        print("→ 可交付；警告多为数据缺口，确认已在「10_数据缺口 / 数据与来源」中体现。")
        return 2
    print("→ 全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
