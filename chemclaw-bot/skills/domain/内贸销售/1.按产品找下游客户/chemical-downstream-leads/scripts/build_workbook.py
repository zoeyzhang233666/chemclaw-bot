#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《<产品>下游需求工厂线索表.xlsx》（四表结构，配置驱动）。

用法：
    python build_workbook.py --dir <任务目录> [--leads leads.json] [--out xxx.xlsx]

读取 <任务目录>/skill_config.json：
  title / product / region_label / region_provinces / out_prefix / map / notes
产出四个工作表：
  ① 说明与行业地图  ② 客户线索总表  ③ 重点客户TOP  ④ 分布统计
"""
import argparse
import json
import os
from collections import Counter, OrderedDict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADERS = ["序号", "行业板块", "细分行业", "公司名称", "所在地（省/市）", "用量强度",
           "需求点（用料环节）", "规模线索", "优先级", "置信度", "线索来源"]
WIDTHS = [6, 16, 30, 34, 20, 10, 62, 46, 9, 9, 52]

THIN = Side(style="thin", color="D0D7E5")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FILL = PatternFill("solid", fgColor="2F5597")
HEAD_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=14, color="1F3864")
PRIO_FILL = {"高": PatternFill("solid", fgColor="FCE4D6"),
             "中": PatternFill("solid", fgColor="FFF2CC"),
             "低": PatternFill("solid", fgColor="EDEDED")}


def style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 28


def province_of(loc, provinces):
    loc = loc or ""
    for p in provinces:
        if p in loc:
            return p
    return "未标注"


def sheet_guide(wb, leads, cfg):
    notes = cfg.get("notes") or {}
    ws = wb.create_sheet("① 说明与行业地图")
    ws["A1"] = cfg.get("title") or f"{cfg.get('product', '产品')} —— 下游需求工厂开发地图"
    ws["A1"].font = Font(bold=True, size=16, color="1F3864")
    ws.merge_cells("A1:G1")

    provinces = cfg.get("region_provinces") or []
    n_hi = sum(1 for x in leads if x.get("优先级") == "高")
    n_conf_hi = sum(1 for x in leads if x.get("置信度") == "高")
    n_prov = len({province_of(x.get("所在地", ""), provinces) for x in leads} - {"未标注"})

    lines = [
        notes.get("purpose") or f"为 {cfg.get('product', '本产品')} 供应商提供下游用该产品工厂的开发线索与切入逻辑。",
        f"本表共 {len(leads)} 条线索，其中高优先级 {n_hi} 条、高置信度 {n_conf_hi} 条，覆盖 {n_prov} 个省级地区、"
        f"{len({x.get('板块') for x in leads})} 个行业板块。",
        f"地域范围：{cfg.get('region_label', '未指定')}。已剔除区域外工厂、本产品生产商（同行）与纯贸易商。",
        "用量强度口径：" + (notes.get("strength_legend") or "按单一工厂年用量标定。"),
        "优先级口径：" + (notes.get("priority_legend") or "优先级 = 用量强度×2 + 置信度分（高3/中2/低0）。仅用于排外呼顺序。"),
    ]
    for t in notes.get("region_why") or []:
        lines.append(t)
    for t in notes.get("data_source") or []:
        lines.append(t)
    lines.append("")
    lines.append("【数据来源与核验方法】")
    for t in notes.get("evidence_note") or ["证据以政府公示、企业官网与公开披露原文为主；所有 URL 均经实抓核验。"]:
        lines.append(t)
    lines.append("")
    lines.append("【已剔除：同业（本产品生产商，属竞争对手而非客户）】")
    lines.append("、".join(notes.get("excluded_peers") or []) or "（无）")
    for t in notes.get("excluded_others") or []:
        lines.append(t)
    lines.append("")
    lines.append("【未覆盖的缺口与负结果】")
    for t in notes.get("gaps") or ["（无）"]:
        lines.append(t)
    lines.append("")
    lines.append("【使用边界】")
    for i, t in enumerate(notes.get("usage_boundary") or [
        "「需求点」列：有原文佐证的为实证，其余为按工艺推导的合理推断，已在句中标注。",
        "正式外呼前建议核对工商信息、联系方式与经营状态（本表不含联系人）。",
    ], 1):
        lines.append(f"{i}. {t}")

    r = 3
    for n in lines:
        cell = ws.cell(row=r, column=1, value=n)
        cell.font = Font(size=11, bold=True, color="1F3864") if n.startswith("【") else Font(size=10, color="404040")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        r += 1

    r += 1
    head = ["行业板块", "细分行业", "用本产品的逻辑 / 工序", "用量强度", "采购与开发要点"]
    for i, h in enumerate(head, start=1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(head))
    freeze = r + 1
    r += 1
    for row in cfg.get("map") or []:
        for i, v in enumerate(row[:5], start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = BORDER
        ws.cell(row=r, column=1).font = Font(bold=True)
        ws.cell(row=r, column=4).alignment = Alignment(horizontal="center", vertical="top")
        r += 1

    for col, w in zip("ABCDEFG", [16, 34, 62, 11, 68, 12, 12]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = ws.cell(row=freeze, column=1)


def sheet_leads(wb, leads, title):
    ws = wb.create_sheet(title)
    for i, h in enumerate(HEADERS, start=1):
        ws.cell(row=1, column=i, value=h)
    style_header(ws, 1, len(HEADERS))

    prio_rank = {"高": 0, "中": 1, "低": 2}
    ordered = sorted(leads, key=lambda x: (x.get("板块", ""), prio_rank.get(x.get("优先级", "中"), 3),
                                           prio_rank.get(x.get("置信度", "中"), 3), x.get("公司", "")))
    for idx, item in enumerate(ordered, start=1):
        row = [idx, item.get("板块", ""), item.get("细分行业", ""), item.get("公司", ""),
               item.get("所在地", ""), item.get("用量强度", ""), item.get("需求点", ""),
               item.get("规模线索", ""), item.get("优先级", "中"), item.get("置信度", "中"),
               item.get("来源", "")]
        r = idx + 1
        for c, v in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=(c in (3, 7, 8, 11)))
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=4).font = Font(bold=True)
        for c in (5, 6, 9, 10):
            ws.cell(row=r, column=c).alignment = Alignment(horizontal="center", vertical="top")
        fill = PRIO_FILL.get(item.get("优先级", "中"))
        if fill:
            ws.cell(row=r, column=9).fill = fill

    for i, w in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = f"A1:K{len(ordered) + 1}"


def bucket_of(sub, rules):
    """把过细的「细分行业」归并成有统计意义的品类（rules 来自配置，缺省则原样返回）。"""
    t = sub or ""
    for name, keys in rules or []:
        if any(k in t for k in keys):
            return name
    return (t[:18] or "其他")


def sheet_stats(wb, leads, cfg):
    provinces = cfg.get("region_provinces") or []
    rules = cfg.get("category_rules") or []
    ws = wb.create_sheet("④ 分布统计")
    ws["A1"] = "线索分布统计"
    ws["A1"].font = TITLE_FONT
    r = 3

    ws.cell(row=r, column=1, value="按行业板块").font = Font(bold=True, size=12)
    r += 1
    for i, h in enumerate(["行业板块", "线索数", "其中高优先级"], start=1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, 3)
    r += 1
    blocks = OrderedDict()
    for it in leads:
        b = it.get("板块", "未分类")
        blocks.setdefault(b, [0, 0])
        blocks[b][0] += 1
        if it.get("优先级") == "高":
            blocks[b][1] += 1
    for b, (n, hi) in sorted(blocks.items(), key=lambda kv: -kv[1][0]):
        ws.cell(row=r, column=1, value=b).border = BORDER
        ws.cell(row=r, column=2, value=n).border = BORDER
        ws.cell(row=r, column=3, value=hi).border = BORDER
        r += 1
    ws.cell(row=r, column=1, value="合计").font = Font(bold=True)
    ws.cell(row=r, column=2, value=sum(v[0] for v in blocks.values())).font = Font(bold=True)
    ws.cell(row=r, column=3, value=sum(v[1] for v in blocks.values())).font = Font(bold=True)

    r += 3
    ws.cell(row=r, column=1, value="按所在省市（线索数 ≥ 2）").font = Font(bold=True, size=12)
    r += 1
    for i, h in enumerate(["省市", "线索数"], start=1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, 2)
    r += 1
    for p, n in sorted(Counter(province_of(x.get("所在地", ""), provinces) for x in leads).items(),
                       key=lambda kv: (-kv[1], kv[0])):
        if n < 2:
            continue
        ws.cell(row=r, column=1, value=p).border = BORDER
        ws.cell(row=r, column=2, value=n).border = BORDER
        r += 1

    r += 3
    ws.cell(row=r, column=1, value="按细分品类（按 category_rules 归并）").font = Font(bold=True, size=12)
    r += 1
    for i, h in enumerate(["细分品类", "线索数", "其中高优先级"], start=1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, 3)
    r += 1
    cat = Counter()
    cat_hi = Counter()
    for it in leads:
        b = bucket_of(it.get("细分行业", ""), rules)
        cat[b] += 1
        if it.get("优先级") == "高":
            cat_hi[b] += 1
    for s, n in sorted(cat.items(), key=lambda kv: (-kv[1], kv[0])):
        ws.cell(row=r, column=1, value=s).border = BORDER
        ws.cell(row=r, column=2, value=n).border = BORDER
        ws.cell(row=r, column=3, value=cat_hi[s]).border = BORDER
        r += 1

    r += 3
    ws.cell(row=r, column=1, value="按置信度").font = Font(bold=True, size=12)
    r += 1
    for i, h in enumerate(["置信度", "线索数"], start=1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, 2)
    r += 1
    for c in ("高", "中", "低"):
        ws.cell(row=r, column=1, value=c).border = BORDER
        ws.cell(row=r, column=2, value=sum(1 for it in leads if it.get("置信度") == c)).border = BORDER
        r += 1

    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 16


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--leads", default="leads.json")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    task_dir = os.path.abspath(args.dir)
    cfg_path = os.path.join(task_dir, "skill_config.json")
    cfg = json.load(open(cfg_path, encoding="utf-8")) if os.path.exists(cfg_path) else {}
    leads = json.load(open(os.path.join(task_dir, args.leads), encoding="utf-8"))

    provinces = cfg.get("region_provinces") or []
    if provinces:
        keep = [x for x in leads if province_of(x.get("所在地", ""), provinces) != "未标注"
                or any(p in (x.get("所在地") or "") for p in provinces)]
        if keep:
            leads = keep

    wb = Workbook()
    wb.remove(wb.active)
    sheet_guide(wb, leads, cfg)
    sheet_leads(wb, leads, "② 客户线索总表")
    sheet_leads(wb, [x for x in leads if x.get("优先级") == "高"], "③ 重点客户TOP")
    sheet_stats(wb, leads, cfg)

    out = args.out or (cfg.get("out_prefix") or f"{cfg.get('product', '产品')}下游需求工厂线索表") + ".xlsx"
    out_path = out if os.path.isabs(out) else os.path.join(task_dir, out)
    wb.save(out_path)
    print(f"OK leads={len(leads)} top={sum(1 for x in leads if x.get('优先级') == '高')} -> {out_path}")


if __name__ == "__main__":
    main()
