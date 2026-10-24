#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""产出 Excel 工作簿（多工作表）。

工作表结构:
    0 使用说明与过滤规则   ← 全部由 config 动态生成，换个产品自动变
    1 商机卡总表           ← 所有保留条目
    2/3/4 三个分组          ← 明确采购/招标、扩产或复产需求、其他潜在需求信号
    4b 同行动态与市场信号   ← 从「其他信号」里分出来的同行供给变化（含利好/利空方向）
    5 待核实（无原文链接）  ← 拿不到原文的条目，不混进正式商机池
    6 被剔除条目           ← 每条都记录命中了哪道闸门
    7 统计                 ← 分布统计

用法: python build_workbook.py --config <product.json> [--dir <任务目录>]
依赖: openpyxl
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    sys.exit("缺少 openpyxl。请先安装：pip install openpyxl")

COLS = [("优先级", 13), ("分组", 16), ("需求性质", 14), ("信号方向", 9), ("公司", 32),
        ("事件类型", 15), ("细分行业", 15), ("省市", 12), ("区域", 7), ("事件产品", 22),
        ("数量/规模", 46), ("发布日", 11), ("截止日", 11), ("与我产品的关系", 56),
        ("时效性", 10), ("置信度", 7), ("用量强度", 8), ("优先级分", 9),
        ("证据来源", 48), ("来源备注", 30)]

HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
G_FILL = {R.GROUP_EXPLICIT: "C6EFCE", R.GROUP_CAPACITY: "FFEB9C", R.GROUP_OTHER: "DDEBF7"}
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP_NAMES = ("事件产品", "数量/规模", "与我产品的关系", "证据来源", "来源备注")


def style_header(ws, ncol, row=1):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 26


def write_rows(ws, rows, cfg, with_seq=False):
    cols = COLS if not with_seq else [("序号", 6)] + COLS
    names = [c[0] for c in cols]
    url_col = names.index("证据来源") + 1
    wrap_cols = {names.index(n) + 1 for n in WRAP_NAMES}
    ws.append(names)
    style_header(ws, len(cols))
    for i, r in enumerate(rows, 1):
        vals = [i] if with_seq else []
        vals += [r.get(n, "") for n, _ in COLS]
        ws.append(vals)
        rr = ws.max_row
        urls = R.extract_urls(r.get("证据来源"))
        if urls:
            c = ws.cell(row=rr, column=url_col)
            c.hyperlink = urls[0]
            c.font = Font(color="0563C1", underline="single", size=9)
        for ci in range(1, len(cols) + 1):
            cell = ws.cell(row=rr, column=ci)
            cell.border = BORDER
            if cell.font.size is None or cell.font.size > 9:
                cell.font = Font(size=9, color=cell.font.color if cell.font.color else None,
                                 underline=cell.font.underline)
            cell.alignment = Alignment(vertical="top", wrap_text=(ci in wrap_cols))
        g = ws.cell(row=rr, column=names.index("分组") + 1)
        g.fill = PatternFill("solid", fgColor=G_FILL.get(str(r.get("分组")), "FFFFFF"))
        if r.get("区域") == cfg["region"].get("out_label", "区外"):
            for ci in range(1, len(cols) + 1):
                cc = ws.cell(row=rr, column=ci)
                cc.font = Font(size=9, color="A6A6A6", underline=cc.font.underline)
        t = ws.cell(row=rr, column=names.index("时效性") + 1)
        tv = str(r.get("时效性"))
        if tv == R.FRESH_OK:
            t.font = Font(size=9, bold=True, color="006100")
        elif tv == R.FRESH_EXPIRED:
            t.font = Font(size=9, color="9C0006")
        else:
            t.font = Font(size=9, color="7F6000")
    for i, (n, w) in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B2" if with_seq else "A2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(cols)), max(1, ws.max_row))


def sheet_guide(wb, cfg, kept, dropped, qa):
    ws = wb.create_sheet("0 使用说明与过滤规则")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 108
    t, p, g = cfg["task"], cfg["product"], cfg["gates"]

    def h(txt):
        ws.append([])
        c = ws.cell(row=ws.max_row + 1, column=1, value=txt)
        c.font = Font(bold=True, size=12, color="1F4E79")
        ws.append([])

    def kv(k, v):
        r = ws.max_row + 1
        ws.cell(row=r, column=1, value=k).font = Font(bold=True, size=10)
        c = ws.cell(row=r, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(size=10)

    c = ws.cell(row=1, column=1, value="%s（%s）近期采购商机卡 · 使用说明" % (t["product_name"], t["region_name"]))
    c.font = Font(bold=True, size=15)
    ws.append([])

    h("一、本次查询条件")
    kv("销售产品", "%s %s" % (t["product_name"], t.get("product_spec", "")))
    kv("同义/检索名", "、".join(p.get("aliases", [])[:12]))
    kv("目标市场", "%s（%s）" % (t["region_name"], "、".join(cfg["region"].get("provinces", []))))
    kv("最小订单规模", t["min_order"])
    kv("时间窗口", "%s ~ %s（基准日 %s）" % (t["window_start"], t["window_end"], t["baseline_date"]))
    kv("结果构成", "保留 %d 条 ｜ 明确采购/招标 %d ｜ 扩产或复产需求 %d ｜ 其他潜在需求信号 %d ｜ 被剔除 %d"
       % (len(kept),
          sum(1 for r in kept if r["分组"] == R.GROUP_EXPLICIT),
          sum(1 for r in kept if r["分组"] == R.GROUP_CAPACITY),
          sum(1 for r in kept if r["分组"] == R.GROUP_OTHER),
          len(dropped)))
    if qa and qa.get("抽样数"):
        kv("链接抽检", "抽 %s 条，可达 %s 条（%s）%s" % (
            qa.get("抽样数"), qa.get("可达数"), qa.get("可达率"),
            ("；另有 %s 条属反爬拦截、需人工复核" % qa.get("反爬拦截数")) if qa.get("反爬拦截数") else ""))

    h("二、怎么用这张表")
    kv("只要「能投的标」看哪张", "工作表『2 明确采购_招标』。这一组是唯一可以直接投标/报价的，"
                            "每条都写了买方、标的、发布与截止日期。")
    kv("只想看华东", "在任意工作表点『区域』列筛选 → 选 %s。（外地信号标为『%s』并整行灰置，"
                 "没有删除——外地的强信号往往仍有参考价值。）"
       % (cfg["region"].get("in_label", "本区"), cfg["region"].get("out_label", "区外")))
    kv("最该先打哪几家", "看『优先级』列：P1 立即跟进 > P2 本周跟进 > P3 备选池 > P4 仅存档。"
                    "优先级分 = 用量强度 × 置信度权重 + 分组加成 + 时效加成。")
    kv("每条能不能信", "看『置信度』和『证据来源』。证据来源都是可点的原文链接；"
                   "标『未核实』的已单列到工作表『5 待核实』，不要当商机用。")
    kv("同行动态在哪", "工作表『4b 同行动态与市场信号』。同行检修/停产对我们是【利好】（供给收紧＝补货窗口），"
                   "同行扩产是【利空】（新增供给），已用『信号方向』列标出。")

    h("三、六道闸门（过滤规则）")
    kv("R1 同行闸门", "自己也生产%s的公司是同行、不是客户，一律剔除。本次同行名单：%s。"
                  "**反向用法**：同行『检修/停产/降负荷』＝供给收紧＝我方补货窗口，"
                  "归入其他信号并以【利好】标注。"
       % (t["product_name"], "、".join(cfg["peers"].get("names", []))))
    rev = cfg["peers"].get("role_reversal", {})
    if rev.get("customer_not_peer"):
        kv("　⚠ 反向陷阱一", "名字像同行、实际是买方（必须留作客户）：" + "；".join(
            "%s —— %s" % (x["name"], x["why"]) for x in rev["customer_not_peer"]))
    if rev.get("peer_not_customer"):
        kv("　⚠ 反向陷阱二", "名字像客户、实际是同行（必须剔除）：" + "；".join(
            "%s —— %s" % (x["name"], x["why"]) for x in rev["peer_not_customer"]))
    kv("R2 产品错配", "以下项命中即剔除：" + "；".join(
        "%s（%s）" % (x["term"], x.get("reason", "")) if isinstance(x, dict) else str(x)
        for x in g.get("mismatch_terms", [])))
    kv("　⚠ 千万别放进去", "本产品的**下游产物**（会被用来反推需求的那些）不能放进错配清单——"
                     "那会把真实需求误杀。见本表『吨耗表』右列。")
    kv("R3 地域闸门", "只保留%s；非%s信号保留但标『%s』并灰置。"
       % (cfg["region"].get("in_label", "本区"), cfg["region"].get("in_label", "本区"),
          cfg["region"].get("out_label", "区外")))
    kv("R4 时间闸门", "发布日须落在 %s ~ %s；发布日更早但截止日仍在未来的招标保留，并标『仍可参与』。"
       % (t["window_start"], t["window_end"]))
    kv("R5 相关性闸门", "『与我产品的关系』必须写清用量逻辑＋量级估算（至少 %s 字且含数字），写空话不收。"
       % g.get("min_relation_chars", 30))
    kv("R6 证据闸门", "证据来源必须是真实抓取到的链接；抓不到则写『未核实』、置信度降为『低』，"
                   "并单列到工作表『5 待核实』。**严禁编造 URL、标题、企业名**——宁可少几条。")

    h("四、用量强度与吨耗表（『与我产品的关系』的量级依据）")
    kv("强度星级", "5 星＝单客户千吨级/年 ｜ 4 星＝百吨级 ｜ 3 星＝数十吨级 ｜ 2 星＝十吨级及以下")
    for row in cfg.get("tonnage", []):
        kv(row.get("industry", ""), "%s %s ｜ 依据：%s ｜ 强度 %s★" % (
            row.get("coefficient", ""), row.get("unit", ""), row.get("basis", ""), row.get("strength", "")))
    kv("注意", "系数是估算，条目里已标『（估算）』。要核实请向企业采购部电话确认月度用量。")

    h("五、三个分组怎么分（判别口诀）")
    kv("① " + R.GROUP_EXPLICIT, "对方**已经在买**：招标公告、询价公告、采购公告、"
                             "或定期报告/募集说明书里披露的采购量、采购金额、采购均价、年度采购合同。"
                             "→ 需求性质＝%s" % R.NATURE_EXPLICIT)
    kv("② " + R.GROUP_CAPACITY, "对方**在扩产或复产**：新装置投产、技改扩能、点火、冷修后复产、提负荷。"
                             "→ 需求性质＝%s（由生产变化推断）" % R.NATURE_INFERRED)
    kv("③ " + R.GROUP_OTHER, "更间接：环评公示里的新建项目、同行检修/停产的补货窗口、"
                           "下游行业景气变化。→ 需求性质＝%s" % R.NATURE_INFERRED)
    kv("拆条铁律", "一条公告可能同时含利空与商机，**必须按产品拆条**，不能按公告整条判断。")

    h("六、置信度分级依据")
    kv("高", "读到公告原文正文且有可点链接，能拿到吨数、金额、合同期、采购均价等硬数字。")
    kv("中", "有可点原文，但只有定性表述或只有项目产能，吨耗与年需求需靠系数估算。")
    kv("低", "只有标题或间接转述、没有可点原文（已单列到工作表『5 待核实』）。")

    h("七、本轮覆盖的检索 lane（换产品时按下游行业重列）")
    for ln in cfg.get("lanes", []):
        kv("%s %s" % (ln.get("id", ""), ln.get("name", "")),
           "检索词：%s ｜ 候选企业：%s" % ("、".join(ln.get("keywords", [])[:8]),
                                    "、".join(ln.get("targets", [])[:8])))
    return ws


def sheet_stats(wb, kept, dropped, cfg):
    ws = wb.create_sheet("7 统计")
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 60

    def block(title, counter, note=""):
        ws.append([])
        c = ws.cell(row=ws.max_row + 1, column=1, value=title)
        c.font = Font(bold=True, size=11, color="1F4E79")
        ws.append(["取值", "条数", "说明"])
        style_header(ws, 3, ws.max_row)
        for k, v in counter.most_common():
            ws.append([k, v, note])

    ws.append(["%s（%s）商机卡分布统计" % (cfg["task"]["product_name"], cfg["task"]["region_name"])])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["保留合计", len(kept), "被剔除 %d 条" % len(dropped)])
    block("按分组", Counter(r["分组"] for r in kept))
    block("按需求性质", Counter(r["需求性质"] for r in kept))
    block("按区域", Counter(r["区域"] for r in kept))
    block("按省份/地区", Counter(str(r["省市"]) for r in kept))
    block("按置信度", Counter(r["置信度"] for r in kept))
    block("按时效性", Counter(r["时效性"] for r in kept))
    block("按优先级", Counter(r["优先级"] for r in kept))
    block("按细分行业", Counter(str(r["细分行业"])[:28] for r in kept))
    block("剔除原因", Counter(str(r.get("剔除原因", ""))[:52] for r in dropped))


def main():
    cfg, base, _ = R.resolve_config()
    kept = R.read_json(os.path.join(base, "leads.json"), []) or []
    dropped = R.read_json(os.path.join(base, "剔除记录.json"), []) or []
    if not kept:
        sys.exit("leads.json 为空，请先跑 merge_leads.py")
    qa = R.read_json(os.path.join(R.rawdir(base), "_qa_report.json"), {})

    wb = Workbook()
    wb.remove(wb.active)
    sheet_guide(wb, cfg, kept, dropped, qa)

    ws = wb.create_sheet("1 商机卡总表")
    write_rows(ws, kept, cfg, with_seq=True)

    ws = wb.create_sheet("2 " + R.GROUP_EXPLICIT.replace("/", "_"))
    write_rows(ws, [r for r in kept if r["分组"] == R.GROUP_EXPLICIT], cfg, with_seq=True)

    ws = wb.create_sheet("3 " + R.GROUP_CAPACITY)
    write_rows(ws, [r for r in kept if r["分组"] == R.GROUP_CAPACITY], cfg, with_seq=True)

    ws = wb.create_sheet("4 " + R.GROUP_OTHER)
    write_rows(ws, [r for r in kept if r["分组"] == R.GROUP_OTHER and not r.get("信号方向")],
               cfg, with_seq=True)

    ws = wb.create_sheet("4b 同行动态与市场信号")
    write_rows(ws, [r for r in kept if r["分组"] == R.GROUP_OTHER and r.get("信号方向")],
               cfg, with_seq=True)

    ws = wb.create_sheet("5 待核实（无原文链接）")
    write_rows(ws, [r for r in kept if not R.extract_urls(r["证据来源"])], cfg, with_seq=True)

    ws = wb.create_sheet("6 被剔除条目")
    cols = [("剔除原因", 52)] + COLS
    names = [c[0] for c in cols]
    url_col = names.index("证据来源") + 1
    ws.append(names)
    style_header(ws, len(cols))
    for r in dropped:
        ws.append([r.get(n, "") for n, _ in cols])
        rr = ws.max_row
        urls = R.extract_urls(r.get("证据来源"))
        if urls:
            c = ws.cell(row=rr, column=url_col)
            c.hyperlink = urls[0]
            c.font = Font(color="0563C1", underline="single", size=9)
        for ci in range(1, len(cols) + 1):
            cell = ws.cell(row=rr, column=ci)
            if not cell.hyperlink:
                cell.font = Font(size=9)
            cell.alignment = Alignment(vertical="top",
                                       wrap_text=(ci in (1, names.index("数量/规模") + 1,
                                                         names.index("与我产品的关系") + 1)))
    for i, (n, w) in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(cols)), max(1, ws.max_row))

    sheet_stats(wb, kept, dropped, cfg)

    name = "%s%s_采购商机卡.xlsx" % (cfg["task"]["product_name"], cfg["task"]["region_name"])
    out = os.path.join(R.outdir(cfg, base), name)
    wb.save(out)
    print("已写出:", out)
    print("总表行数(含表头):", len(kept) + 1)
    for sn in wb.sheetnames:
        print("   sheet: %-24s %4d 行" % (sn, wb[sn].max_row))


if __name__ == "__main__":
    main()