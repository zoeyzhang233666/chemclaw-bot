#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""case.json → Excel 工作簿（11 张表）。

用法:
  python build_workbook.py --case case.json [--out out/]
依赖: openpyxl（pip install openpyxl）
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caselib as C  # noqa: E402

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.properties import PageSetupProperties
    from openpyxl.chart import BarChart, Reference
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    sys.stderr.write("需要 openpyxl：pip install openpyxl\n")
    raise

INK, INK2, SLATE = "1E293B", "334155", "475569"
ACCENT, ACCENT_D, ACCENT_L, ACCENT_L2 = "0F766E", "134E4A", "CCFBF1", "F0FDFA"
AMBER, AMBER_L, RED, RED_L = "B45309", "FEF3C7", "B91C1C", "FEE2E2"
GREEN, GREEN_L, GRAY_BG, GRAY_LN, WHITE = "166534", "DCFCE7", "F8FAFC", "E2E8F0", "FFFFFF"
FONT, MONO = "微软雅黑", "Consolas"

thin = Side(style="thin", color=GRAY_LN)
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

STEPS = [
    ("STEP 1  收料", "原话全文 + 产品与客户背景 + 上一轮沟通记录。原话保持口语，别先美化。", "一份不修饰的原话"),
    ("STEP 2  抽事实", "把原话拆成 F1…Fn，标类型（事实/意图/承诺/无据/越权）与来源。", "事实台账"),
    ("STEP 3  建产品档案", "形态、危险性、包装运输、验收指标、价格口径、本品类禁语。", "决定哪些话能说"),
    ("STEP 4  出主版本 + 三开关", "A 自然 / B 更短 / C 正式 / D 缓和；一条消息只提一个请求。", "四个版本"),
    ("STEP 5  审计 + 占位符", "逐格判定 + 【待填】登记 → 跑脚本，ERROR 清零才可交付。", "审计表 + 待填清单"),
]

GUIDE = [
    ("01_客户档案", "跟谁说话：客户、产品档案、决策链、验收关注点、禁语。"),
    ("02_事实台账", "把原话拆成可核验条目，后面所有审计的基准。"),
    ("03_主案例版本对照", "按“沟通环节”横向对齐各版本，一眼看出哪句被怎么改了。"),
    ("04_边界审计", "逐格判定 + 新增项计数（必须全为 0）。"),
    ("05_场景矩阵", "约见/报价跟进/催款/涨价/送样，各一套可直接发的文本。"),
    ("06_占位符清单", "每个【待填】的确认人与填错后果，发出去之前清零。"),
    ("07_快速调整指令库", "“再短一点/更正式”命中的具体改法，附前后对照。"),
    ("08_发送前检查清单", "12 项自检，带下拉状态与自动统计。"),
    ("09_追问应对", "客户几种常见回法，给不越界的接法 + 禁止说法。"),
    ("10_复盘看板", "指标汇总与版本评分图。"),
]

PROMPT_FRAME = """以下是我准备发给【客户/角色】的内容，渠道是【微信/邮件】，背景是【背景】，这次想推进【约见/报价跟进/催款/解释涨价/送样安排】。请在保留我的原意和全部事实的前提下优化表达，使其更【自然/简洁/正式/缓和】。
严格要求：不要新增我没有提供的价格、折扣、交期、库存、承诺或客户需求；不确定处保留为占位符【待填】。
原文：【粘贴原文】"""

VERDICT_FILL = {"✔": (GREEN_L, GREEN), "◐": (AMBER_L, AMBER), "▲": (RED_L, RED), "—": (GRAY_BG, SLATE)}


def fill(c):
    return PatternFill("solid", start_color=c, end_color=c)


def dispw(s):
    return sum(2 if ord(ch) > 127 else 1 for ch in str(s))


def est_lines(text, width, fudge=1.0):
    if text is None:
        return 1
    per = max(3.0, width * fudge)
    n = 0
    for seg in str(text).split("\n"):
        d = dispw(seg)
        n += max(1, math.ceil(d / per)) if d else 1
    return n


class Sheet:
    def __init__(self, wb, name, widths, first=False):
        self.ws = wb.active if first else wb.create_sheet(name)
        self.ws.title = name
        self.ws.sheet_view.showGridLines = False
        self.widths = widths
        self.n = len(widths)
        for i, w in enumerate(widths, start=1):
            self.ws.column_dimensions[get_column_letter(i)].width = w
        self.r = 1

    # ---------- 版式 ----------
    def title(self, t, sub):
        last = get_column_letter(self.n)
        self.ws.merge_cells("A1:%s1" % last)
        c = self.ws["A1"]
        c.value = t
        c.font = Font(name=FONT, size=17, bold=True, color=WHITE)
        c.fill = fill(INK)
        c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
        self.ws.row_dimensions[1].height = 44
        self.ws.merge_cells("A2:%s2" % last)
        c = self.ws["A2"]
        c.value = sub
        c.font = Font(name=FONT, size=10, color=INK2)
        c.fill = fill(ACCENT_L)
        c.alignment = Alignment(vertical="center", horizontal="left", indent=1, wrap_text=True)
        self.ws.row_dimensions[2].height = 30
        self.ws.row_dimensions[3].height = 8
        self.r = 4

    def section(self, text, color=ACCENT, light=ACCENT_L2):
        last = get_column_letter(self.n)
        r = self.r
        self.ws.merge_cells("A%d:%s%d" % (r, last, r))
        c = self.ws.cell(row=r, column=1, value=text)
        c.font = Font(name=FONT, size=11, bold=True, color=color)
        c.fill = fill(light)
        c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
        for i in range(1, self.n + 1):
            self.ws.cell(row=r, column=i).border = Border(
                left=Side(style="thick", color=color) if i == 1 else None,
                bottom=Side(style="thin", color=GRAY_LN))
        self.ws.row_dimensions[r].height = 26
        self.r += 1

    def header(self, headers, h=32):
        for i, x in enumerate(headers, start=1):
            c = self.ws.cell(row=self.r, column=i, value=x)
            c.font = Font(name=FONT, size=10, bold=True, color=WHITE)
            c.fill = fill(INK2)
            c.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
            c.border = BORDER
        self.ws.row_dimensions[self.r].height = h
        self.r += 1
        return self.r - 1

    def row(self, values, aligns=None, fills=None, bolds=None, size=10, color=INK,
            zebra=None, base=None, minh=22, merge=None):
        r = self.r
        if merge:
            values = list(values) + [None] * (self.n - len(values))
            aligns = (list(aligns) if aligns else ["left"] * len(values)) + ["left"] * (self.n - len(aligns or []))
        aligns = aligns or ["left"] * len(values)
        base = base or (size * 1.62 + 1.5)
        for i, v in enumerate(values, start=1):
            c = self.ws.cell(row=r, column=i, value=v)
            bold = bolds[i - 1] if bolds else (i == 1)
            c.font = Font(name=FONT, size=size, bold=bool(bold), color=color)
            c.alignment = Alignment(vertical="top", wrap_text=True, indent=1 if aligns[i - 1] == "left" else 0,
                                    horizontal=aligns[i - 1])
            c.border = BORDER
            if fills and fills[i - 1]:
                c.fill = fill(fills[i - 1])
            elif zebra and r % 2 == 0:
                c.fill = fill(zebra)
        if merge:
            c1, c2 = merge
            self.ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
            for i in range(c1, c2 + 1):
                self.ws.cell(row=r, column=i).border = BORDER
        self.ws.row_dimensions[r].height = max(
            minh, min(409, max(est_lines(v, self.widths[i]) for i, v in enumerate(values)) * base + 8))
        self.r += 1
        return r

    def note(self, text, color=SLATE, bg=GRAY_BG, size=9.5, h=None, bold=False):
        last = get_column_letter(self.n)
        r = self.r
        self.ws.merge_cells("A%d:%s%d" % (r, last, r))
        c = self.ws.cell(row=r, column=1, value=text)
        c.font = Font(name=FONT, size=size, color=color, bold=bold)
        c.fill = fill(bg)
        c.alignment = Alignment(vertical="top", horizontal="left", indent=1, wrap_text=True)
        for i in range(1, self.n + 1):
            self.ws.cell(row=r, column=i).border = BORDER
        total = sum(self.widths)
        lines = est_lines(text, total)
        self.ws.row_dimensions[r].height = h or max(24, min(409, lines * (size * 1.62 + 2) + 8))
        self.r += 1

    def finish(self, landscape=True, freeze=None, tab=None):
        ws = self.ws
        if freeze:
            ws.freeze_panes = freeze
        ws.page_setup.orientation = "landscape" if landscape else "portrait"
        ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.page_margins.left = ws.page_margins.right = 0.4
        ws.page_margins.top = ws.page_margins.bottom = 0.5
        if tab:
            ws.sheet_properties.tabColor = tab


def build(case, outdir):
    meta = case["meta"]
    pp = case.get("product_profile") or {}
    seller = meta.get("seller") or {}
    cust = meta.get("customer") or {}
    versions = case["versions"]
    order = case.get("version_order") or (["P0"] + C.VERSION_KEYS)
    vkeys = [k for k in order if k in versions]
    st = C.stats(case)

    wb = Workbook()

    # ------------------------------------------------------------ 00
    s = Sheet(wb, "00_使用说明", [26, 62, 46], first=True)
    s.title("客户沟通润色工作簿",
            "%s · %s｜客户：%s｜渠道：%s｜本次目标：%s" % (
                meta.get("product", ""), meta.get("spec", "") or "", cust.get("name", ""),
                meta.get("channel", ""), meta.get("goal", "")))
    s.section("一、这次要做的事")
    info = [("产品", "%s %s" % (meta.get("product", ""), meta.get("spec", ""))),
            ("客户 / 角色", "%s · %s" % (cust.get("name", ""), cust.get("role", ""))),
            ("渠道", meta.get("channel", "")),
            ("本次目标", meta.get("goal", "")),
            ("关系阶段", meta.get("stage", "")),
            ("我方", "%s %s %s" % (seller.get("company", ""), seller.get("region", ""), seller.get("name", ""))),
            ("渠道备注", meta.get("channel", ""))]
    for k, v in info:
        s.row([k, v], aligns=["left", "left"], fills=[GRAY_BG, None, None], merge=(2, 3))
    s.r += 1

    s.section("二、四条红线（这套方法的全部价值在这里）")
    for i, rr in enumerate(case.get("rules") or [], start=1):
        s.row(["%d. %s" % (i, rr.get("k", "")), rr.get("v", "")], aligns=["left", "left"], merge=(2, 3))
    s.r += 1

    s.section("三、五步流程")
    s.header(["步骤", "做什么", "产出"])
    for a, b, c in STEPS:
        s.row([a, b, c], aligns=["left", "left", "left"], zebra=GRAY_BG)
    s.r += 1

    s.section("四、工作簿导航")
    s.header(["工作表", "用途", ""])
    for a, b in GUIDE:
        s.row([a, b], aligns=["left", "left"], merge=(2, 3), zebra=GRAY_BG)
    s.r += 1

    s.section("五、提示词框架（复制进工具输入框，把方括号换成你的内容）")
    s.note(PROMPT_FRAME, color=INK, bg=GRAY_BG, size=10)
    s.r += 1

    s.section("六、说明与免责")
    notes = list(case.get("notes") or [])
    if case.get("disclaim"):
        notes.append(case["disclaim"])
    for t in notes:
        s.note("· " + str(t), size=9.5)
    s.finish(landscape=False, tab=INK)

    # ------------------------------------------------------------ 01
    s = Sheet(wb, "01_客户档案", [18, 46, 62])
    s.title("01 · 客户档案", "先看清“跟谁说话”：决策链、验收口径、禁语。带【待填】的字段在发出任何文本前必须确认。")
    s.section("客户档案")
    s.header(["维度", "内容", "对沟通的影响"])
    for row in case.get("customer_profile") or []:
        vals = list(row) + ["", "", ""]
        s.row(vals[:3], aligns=["left", "left", "left"], zebra=GRAY_BG)
    s.r += 1

    s.section("产品档案（决定哪些话能说）")
    s.header(["项", "内容", "备注"])
    pmap = [("品名 / 别名", pp.get("name", "") + (" / " + "、".join(pp.get("alias") or []) if pp.get("alias") else ""), "检索与沟通统一用学名"),
            ("CAS / 标准", "%s　%s" % (pp.get("cas", "") or "—", pp.get("standard", "") or "—"), "引用国标必须核实现行版本"),
            ("形态", pp.get("form", ""), "固/液/气决定包装与运输"),
            ("危险性", pp.get("hazard", ""), "危化品/易制毒须先谈资质与备案"),
            ("包装", "、".join(pp.get("packaging") or []) or "—", "包装决定装卸与计量方式"),
            ("运输", pp.get("transport", ""), "卸车与到货节奏是常见痛点"),
            ("验收指标", "、".join(pp.get("key_specs") or []) or "—", "具体数值以客户质检单/合同为准【待填】"),
            ("价格口径", pp.get("price_basis", ""), "口径不同＝报错价"),
            ("结算惯例", pp.get("payment_norm", ""), "账期须财务确认"),
            ("下游行业", "、".join(pp.get("downstream") or []) or "—", "决定话题与拜访理由"),
            ("已知痛点", "；".join(pp.get("pain_points") or []) or "—", "作议题，不作卖点"),
            ("季节性", pp.get("seasonality", "") or "—", "影响库存与到货话术"),
            ("本品类禁语", "；".join(pp.get("ban_phrases") or []) or "—", "脚本会逐条扫描正文")]
    for k, v, note in pmap:
        s.row([k, v, note], aligns=["left", "left", "left"], zebra=GRAY_BG)
    s.r += 1

    if case.get("decision_chain"):
        s.section("决策链示意")
        s.note(case["decision_chain"], color=ACCENT_D, bg=ACCENT_L, size=10, bold=True)
        s.r += 1
    s.finish(freeze="A5", tab=SLATE)

    # ------------------------------------------------------------ 02
    s = Sheet(wb, "02_事实台账", [7, 44, 14, 16, 16, 44])
    s.title("02 · 事实台账", "把原话拆成可核验的条目。后面的每一次改写、每一格审计，都以这张表为基准。")
    s.header(["编号", "事实 / 表述", "类型", "来源", "处置", "备注"])
    first = s.r
    for f in case.get("facts") or []:
        fs = [None] * 6
        t = f.get("type", "")
        if any(x in t for x in ("无据", "越权", "施压")):
            fs[2] = RED_L
        elif "承诺" in t:
            fs[2] = AMBER_L
        d = f.get("disposal", "")
        if d in ("建议删除", "禁止直发"):
            fs[4] = RED_L
        elif d in ("需改写", "谨慎"):
            fs[4] = AMBER_L
        s.row([f.get("id"), f.get("text"), t, f.get("source"), d, f.get("note")],
              aligns=["center", "left", "center", "center", "center", "left"],
              bolds=[True] + [False] * 5, fills=fs)
    last = s.r - 1
    s.r += 1
    s.note("读法：可用＝放心写进正文；谨慎＝敏感不点破；需改写＝降级后使用；建议删除/禁止直发＝不进正文，并在审计里标 ▲。")
    s.finish(freeze="B5", tab=SLATE)
    facts_range = (first, last)

    # ------------------------------------------------------------ 03
    links = case.get("links") or ["① 开场与由头", "② 核心事项", "③ 请求", "④ 收口", "⑤ 越界项处理"]
    nver = len(vkeys)
    widths = [15] + [44 if ("邮件" in (versions[k].get("media") or "")) else 38 for k in vkeys]
    s = Sheet(wb, "03_主案例版本对照", widths)
    s.title("03 · 主案例：%s · 多版横向对照" % meta.get("scenario", ""),
            "按“沟通环节”对齐，而不是按句子顺序对齐——这样才能看出哪一句话被换成了什么。")
    s.header(["环节"] + [versions[k].get("label", k) for k in vkeys], h=34)
    for i, link in enumerate(links):
        vals = [link]
        for k in vkeys:
            cells = versions[k].get("cells") or []
            vals.append(cells[i] if i < len(cells) else "—")
        fills = [None] * len(vals)
        if i == len(links) - 1:
            for j, k in enumerate(vkeys):
                fills[j + 1] = RED_L if k == "P0" else GREEN_L
        s.row(vals, aligns=["center"] + ["left"] * nver, fills=fills)
    s.r += 1

    s.section("版本参数（字数按正文计）")
    s.header(["参数"] + [k for k in vkeys], h=28)
    tone = [str((versions[k].get("score") or {}).get("tone", 5 if "邮件" in (versions[k].get("media") or "") else 2))
            for k in vkeys]
    push = [str((versions[k].get("score") or {}).get("push", 3 if k == "P0" else 4)) for k in vkeys]
    rows = [("字数", [str(C.wordcount(C.version_text(versions[k]))) for k in vkeys]),
            ("媒介", [versions[k].get("media", "") for k in vkeys]),
            ("语气", [versions[k].get("tone", "") for k in vkeys]),
            ("推进力", [versions[k].get("push", "") for k in vkeys]),
            ("风险", [versions[k].get("risk", "") for k in vkeys]),
            ("适用场景", [versions[k].get("fit", "") for k in vkeys])]
    for name, vals in rows:
        fs = [None] * (1 + nver)
        if name == "风险":
            for j, v in enumerate(vals):
                fs[j + 1] = RED_L if v.startswith("高") else GREEN_L
        s.row([name] + vals, aligns=["center"] + ["center" if name == "字数" else "left"] * nver, fills=fs)
    if (case.get("email") or {}).get("subject"):
        s.r += 1
        s.note("邮件主题行：" + case["email"]["subject"], color=ACCENT_D, bg=ACCENT_L, size=10, bold=True)
    s.finish(freeze="B5", tab=ACCENT)
    score_rows = (tone, push)

    # ------------------------------------------------------------ 04
    ncol = 4 + 4 + 1
    s = Sheet(wb, "04_边界审计", [7, 38, 13, 14, 7, 7, 7, 7, 52])
    s.title("04 · 边界审计：每个版本 × 每条事实",
            "✔ 保留　◐ 弱化/改写　— 刻意未提　▲ 已删除。判定必须能为每格找出文本依据。")
    s.header(["编号", "事项", "类型", "来源"] + C.VERSION_KEYS + ["审计说明"], h=30)
    first = s.r
    for a in case.get("audit") or []:
        vals = [a.get("id"), a.get("item"), a.get("type"), a.get("source")] + \
               [a["v"].get(k, "—") for k in C.VERSION_KEYS] + [a.get("why")]
        fs = [None] * len(vals)
        for j in range(4, 8):
            fs[j] = VERDICT_FILL.get(vals[j], (GRAY_BG, SLATE))[0]
        s.row(vals, aligns=["center", "left", "center", "center", "center", "center", "center", "center", "left"],
              bolds=[True] + [False] * 8, fills=fs)
        for j in range(4, 8):
            s.ws.cell(row=s.r - 1, column=j + 1).font = Font(
                name=FONT, size=11, bold=True, color=VERDICT_FILL.get(vals[j], (GRAY_BG, SLATE))[1])
    last = s.r - 1
    s.r += 1

    s.section("新增项计数 —— 这一栏必须全部为 0，否则不许发", color=RED, light=RED_L)
    s.header(["项目", "计数", "判定", "", "", "", "", "", "说明"], h=26)
    s.ws.merge_cells(start_row=s.r - 1, start_column=3, end_row=s.r - 1, end_column=8)
    for it in case.get("audit_summary") or []:
        v = str(it.get("v", ""))
        ok = v.strip() == "0"
        r = s.row([it.get("k"), v, "PASS" if ok else "待清", "", "", "", "", "", it.get("note")],
                  aligns=["left", "center", "left", "left", "left", "left", "left", "left", "left"],
                  bolds=[True, True] + [False] * 7,
                  fills=[None, GREEN_L if ok else AMBER_L] + [None] * 7)
        s.ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=8)
        s.ws.cell(row=r, column=3).font = Font(name=FONT, size=10, bold=True, color=GREEN if ok else AMBER)
    s.finish(freeze="C5", tab=RED)
    audit_range = (first, last)

    # ------------------------------------------------------------ 05
    s = Sheet(wb, "05_场景矩阵", [12, 34, 62, 34, 40])
    s.title("05 · 高频场景 · 同一套边界规则",
            "左边是业务真实会打出来的原话，右边是可直接发出去的版本。最后一列是红线。")
    s.header(["场景", "我的原话（真实口语）", "推荐版（可直接发）", "最简版（已读不回时）", "红线提示"], h=32)
    for sc in case.get("scenarios") or []:
        s.row([sc.get("n"), sc.get("q"), sc.get("rec"), sc.get("short"), sc.get("red")],
              aligns=["center", "left", "left", "left", "left"], size=9.5, zebra=GRAY_BG)
    s.finish(tab=ACCENT_D)

    # ------------------------------------------------------------ 06
    s = Sheet(wb, "06_占位符清单", [7, 34, 20, 20, 34, 38])
    s.title("06 · 占位符清单：【待填】的归属",
            "发出去之前，这张表必须清零。留一个没填，客户看到的就是“这个人不专业”。")
    s.header(["编号", "占位符", "出现位置", "谁来确认", "建议填写口径", "填错/漏填的后果"])
    for p in case.get("placeholders") or []:
        r = s.row([p.get("id"), "【待填】" + str(p.get("item", "")), p.get("where"), p.get("owner"),
                   p.get("how"), p.get("risk")],
                  aligns=["center", "left", "center", "center", "left", "left"], size=9.5, zebra=GRAY_BG)
        s.ws.cell(row=r, column=2).font = Font(name=FONT, size=9.5, bold=True, color=AMBER)
    s.finish(freeze="B5", tab=AMBER)

    # ------------------------------------------------------------ 07
    s = Sheet(wb, "07_快速调整指令库", [24, 20, 50, 66])
    s.title("07 · 快速调整指令库",
            "“再短一点”“更正式”“适合微信”——这类指令命中之后，到底改的是什么？这张表把它写死，避免每次改成随机发挥。")
    s.header(["指令", "目标 / 结果", "实际执行的改法", "示例输出"], h=30)
    for a in case.get("adjusts") or []:
        r = s.row([a.get("t"), a.get("tag"), a.get("note"), a.get("x")],
                  aligns=["left", "center", "left", "left"], size=9.5)
        s.ws.cell(row=r, column=1).font = Font(name=FONT, size=9.5, bold=True, color=INK)
    s.finish(freeze="A5")

    # ------------------------------------------------------------ 08
    s = Sheet(wb, "08_发送前检查清单", [7, 16, 62, 14, 30])
    s.title("08 · 发送前检查清单", "点“状态”列的下拉框逐项确认。最后一列写这次的具体情况，下次回头看就是经验。")
    s.header(["序号", "维度", "检查项", "状态", "本单备注"])
    first = s.r
    for i, ck in enumerate(case.get("checklist") or [], start=1):
        s.row([i, ck.get("dim"), ck.get("item"), "未查", ""],
              aligns=["center", "center", "left", "center", "left"], zebra=GRAY_BG, size=9.5)
    last = s.r - 1
    if last >= first:  # 清单允许为空；空表不加下拉，避免 "4 must be greater than 5"
        dv = DataValidation(type="list", formula1='"未查,通过,需修改,不适用"', allow_blank=False,
                            showDropDown=False, promptTitle="状态", prompt="逐项确认后再发",
                            errorTitle="只能选：未查/通过/需修改/不适用", error="请从下拉列表选择")
        s.ws.add_data_validation(dv)
        dv.add("D%d:D%d" % (first, last))
    s.r += 1
    s.note("提示：只要有一项“需修改”，就先别发。发错一条越界承诺的成本，远高于晚半小时发出去。",
           color=AMBER, bg=AMBER_L, bold=True)
    s.finish(freeze="C5")
    ck_range = (first, last)

    # ------------------------------------------------------------ 09
    s = Sheet(wb, "09_追问应对", [22, 60, 28, 40])
    s.title("09 · 客户会怎么接，你怎么接",
            "润色的另一半：发出去之后，对方的每一句回话都可能把你逼回“新增承诺”。")
    s.header(["客户可能这样说", "推荐应对（可直接发）", "禁止说法", "为什么"], h=30)
    for rp in case.get("replies") or []:
        r = s.row([rp.get("q"), rp.get("say"), rp.get("ban"), rp.get("why")],
                  aligns=["left", "left", "left", "left"], size=9.5, bolds=[True] + [False] * 3,
                  zebra=GRAY_BG)
        s.ws.cell(row=r, column=3).font = Font(name=FONT, size=9.5, color=RED)
    s.finish(freeze="B5")

    # ------------------------------------------------------------ 10
    s = Sheet(wb, "10_复盘看板", [30, 16, 72])
    s.title("10 · 复盘看板", "静态指标由 case.json 直接统计；勾选类指标由公式计算，改动后按 F9 刷新。")
    s.section("核心指标")
    s.header(["指标", "数值", "说明"], h=28)
    metrics = [
        ("事实台账条目", st["facts"], "被显式管理的信息条数"),
        ("边界审计行", st["audit"], "每条事实 × 4 个版本都要有判定"),
        ("待填占位符", st["placeholders"], "发出前清零，否则不许发"),
        ("场景模板", st["scenarios"], "约见/跟进/催款/涨价/送样…"),
        ("调整指令", st["adjusts"], "每条指令对应确定的改法"),
        ("追问应对", st["replies"], "客户常见回法的不越界接法"),
        ("检查清单项", st["checklist"], "发送前逐项确认"),
    ]
    for k, v, note in metrics:
        s.row([k, v, note], aligns=["left", "center", "left"], bolds=[True, True, False])
    r = s.row(["已通过检查项", "=COUNTIF('08_发送前检查清单'!D%d:D%d,\"通过\")" % ck_range, "下拉选“通过”后自动累加"],
              aligns=["left", "center", "left"], bolds=[True, True, False])
    s.ws.cell(row=r, column=2).font = Font(name=FONT, size=13, bold=True, color=ACCENT_D)
    r = s.row(["仍待检查项", "=COUNTIF('08_发送前检查清单'!D%d:D%d,\"未查\")" % ck_range, "理想状态：0"],
              aligns=["left", "center", "left"], bolds=[True, True, False])
    s.ws.cell(row=r, column=2).font = Font(name=FONT, size=13, bold=True, color=AMBER)
    s.row(["新增价格/折扣/交期/库存/需求", 0, "硬指标：必须恒为 0。不是“尽量”，是“不许”。"],
          aligns=["left", "center", "left"], bolds=[True, True, False],
          fills=[None, GREEN_L, None])
    s.ws.cell(row=s.r - 1, column=2).font = Font(name=FONT, size=13, bold=True, color=GREEN)
    s.r += 1

    s.section("版本三维评分（1–5）")
    s.header(["版本", "语气正式度", "推进力"], h=28)
    sf = s.r
    for j, k in enumerate(vkeys):
        s.row([versions[k].get("label", k), int(tone[j]), int(push[j])],
              aligns=["left", "center", "center"], zebra=GRAY_BG)
    s.r += 1
    s.note("读图：正式度高、推进力强适合“流程型客户”；正式度低、推进力弱适合“反感被催的关系”。"
           "没有最优版本，只有最匹配当下关系阶段的版本。", size=9.5)
    if vkeys:
        ch = BarChart()
        ch.type = "bar"
        ch.style = 10
        ch.title = "各版本语气正式度 vs 推进力"
        ch.y_axis.title = "评分（1–5）"
        ch.height, ch.width, ch.gapWidth = 8.4, 17, 60
        data = Reference(s.ws, min_col=2, max_col=3, min_row=sf - 1, max_row=sf - 1 + len(vkeys))
        cats = Reference(s.ws, min_col=1, min_row=sf, max_row=sf - 1 + len(vkeys))
        ch.add_data(data, titles_from_data=True)
        ch.set_categories(cats)
        s.ws.add_chart(ch, "E%d" % max(4, sf - 2))
    s.finish(landscape=False, tab=ACCENT_D)

    wb.properties.title = "%s %s · 客户沟通润色" % (meta.get("product", ""), meta.get("scenario", ""))
    wb.properties.subject = "%s · %s" % (cust.get("name", ""), meta.get("goal", ""))
    wb.properties.creator = "chem-message-polish"
    wb.properties.description = "由 case.json 生成；所有商业条款按规则留为【待填】。"
    wb.calculation.fullCalcOnLoad = True

    xlsx, _ = C.out_paths(case, outdir)
    wb.save(xlsx)
    return xlsx


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", default="out")
    args = ap.parse_args(argv)
    case = C.load_case(args.case)
    p = build(case, args.out)
    print("xlsx →", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
