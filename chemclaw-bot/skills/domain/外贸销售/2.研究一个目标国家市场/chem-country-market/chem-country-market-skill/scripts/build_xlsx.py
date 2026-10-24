"""
build_xlsx.py — case.json → 多工作表 Excel 工作底稿（供销售在内部传阅、批注、交接）

  python build_xlsx.py case.json --out out/中国重质纯碱-印度尼西亚_国别市场研究.xlsx

设计原则
--------
* 每个数字所在行都带“口径 / 来源 / 可信等级”，不留裸数字。
* 缺口单独成表，并且用红色底纹，避免被 Excel 的“看起来完整”误读。
* 所有表放在独立 sheet，便于按需隐藏/复制进其他文件。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    print("需要 openpyxl：pip install openpyxl", file=sys.stderr)
    raise

# ---------------------------------------------------------------- style
INK = "1F2937"
HEAD = "1E3A5F"
ACCENT = "2563EB"
BAND = "F1F5F9"
WARN = "FEF2F2"
WARN_INK = "B91C1C"
OKFILL = "ECFDF5"
OK_INK = "047857"
GAP = "FFF7ED"

F_TITLE = Font(name="Microsoft YaHei", size=15, bold=True, color="FFFFFF")
F_SUB = Font(name="Microsoft YaHei", size=9.5, color="FFFFFF")
F_HEAD = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
F_BODY = Font(name="Microsoft YaHei", size=10, color=INK)
F_BOLD = Font(name="Microsoft YaHei", size=10, bold=True, color=INK)
F_SMALL = Font(name="Microsoft YaHei", size=9, color="64748B")
F_LINK = Font(name="Microsoft YaHei", size=9, color="1D4ED8", underline="single")
THIN = Side(style="thin", color="E2E8F0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def sheet_title(ws, title, subtitle, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=title)
    c.font = F_TITLE
    c.fill = PatternFill("solid", fgColor=HEAD)
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 34
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c2 = ws.cell(row=2, column=1, value=subtitle)
    c2.font = F_SUB
    c2.fill = PatternFill("solid", fgColor=ACCENT)
    c2.alignment = Alignment(vertical="center", indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 30
    ws.row_dimensions[3].height = 6


def header_row(ws, row, headers, widths=None):
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = F_HEAD
        c.fill = PatternFill("solid", fgColor="334155")
        c.alignment = CENTER
        c.border = BOX
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, start=1):
            if w:  # width 0/None = keep sheet default (hidden helper columns)
                ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def body(ws, r0, rows, money_cols=(), num_cols=(), pct_cols=(), text_cols=(), fill=None, fonts=None,
         money2_cols=(), num2_cols=()):
    for j, row in enumerate(rows):
        r = r0 + j
        for i, v in enumerate(row, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.font = (fonts.get(i, F_BODY) if fonts else F_BODY)
            c.border = BOX
            c.alignment = WRAP if i in text_cols or i > 2 else Alignment(vertical="top")
            if i in money_cols and isinstance(v, (int, float)):
                c.number_format = '#,##0.00' if i in money2_cols else '#,##0'
                c.alignment = Alignment(horizontal="right", vertical="top")
            if i in num_cols and isinstance(v, (int, float)):
                c.number_format = '#,##0.00' if i in num2_cols else '#,##0.0'
                c.alignment = Alignment(horizontal="right", vertical="top")
            if i in pct_cols and isinstance(v, (int, float)):
                c.number_format = '0.0%'
                c.alignment = Alignment(horizontal="right", vertical="top")
            if fill and j % 2 == 1:
                c.fill = PatternFill("solid", fgColor=fill)
    return r0 + len(rows)


def auto_height(ws, r0, r1, base=15, cap=120):
    for r in range(r0, r1):
        need = 1
        for c in ws[r]:
            if isinstance(c.value, str):
                need = max(need, min(cap // base, 1 + len(c.value) // 46))
        ws.row_dimensions[r].height = max(base, min(cap, need * base))


# ---------------------------------------------------------------- builders
def s_readme(wb, case, idx):
    ws = wb.create_sheet("00 说明与口径")
    m = case["meta"]
    ts = m.get("trade_source") or {}
    sheet_title(ws, "%s" % m["title"],
                "本工作簿由 chem-country-market 生成器从 case.json 派生；任何改动请改 case.json 后重新生成，避免两处数字打架。", 4)
    rows = [
        ["研究产品", "%s（%s）" % (m["subject"]["product_cn"], m["subject"].get("grade", "")), "meta.subject"],
        ["HS 编码", m["subject"]["hs_code"], "meta.subject.hs_code"],
        ["目标国家", "%s / %s / UN M49 %s" % (m["country"]["name_cn"], m["country"].get("name_en", ""), m["country"].get("un_m49", "")), "meta.country"],
        ["研究年份 / 窗口", "%s / %s 年" % (m["research_year"], m.get("window")), "meta"],
        ["数据截止", m.get("data_asof", ""), "meta.data_asof"],
        ["贸易数据来源", ts.get("name", ""), "meta.trade_source.name"],
        ["数据集", ts.get("dataset", ""), "meta.trade_source.dataset"],
        ["金额口径", ts.get("value_basis", ""), "meta.trade_source.value_basis"],
        ["数量口径", ts.get("weight_basis", ""), "meta.trade_source.weight_basis"],
        ["取数记录", ts.get("pull_record", ""), "meta.trade_source.pull_record"],
    ]
    r = 4
    ws.cell(row=r, column=1, value="一、研究设定").font = Font(name="Microsoft YaHei", size=11, bold=True, color=HEAD)
    r += 1
    header_row(ws, r, ["项目", "内容", "数据字段"], [22, 84, 26])
    r = body(ws, r + 1, rows, text_cols={2}, fill=BAND)
    auto_height(ws, r - len(rows), r)

    r += 1
    ws.cell(row=r, column=1, value="二、口径注意事项（务必读）").font = Font(name="Microsoft YaHei", size=11, bold=True, color=WARN_INK)
    r += 1
    header_row(ws, r, ["#", "说明"], [6, 96])
    notes = ts.get("notes") or []
    r = body(ws, r + 1, [[i + 1, n] for i, n in enumerate(notes)], text_cols={2}, fill=WARN)
    auto_height(ws, r - len(notes), r)

    r += 1
    ws.cell(row=r, column=1, value="三、工作簿结构").font = Font(name="Microsoft YaHei", size=11, bold=True, color=HEAD)
    r += 1
    header_row(ws, r, ["工作表", "内容", "对应报告章节"], [18, 62, 18])
    idx_rows = [
        ["01 关键指标", "首屏 KPI 与派生指标（CAGR、份额、集中度）", "概览"],
        ["02 进口历史", "逐年金额/数量/单位价值/同比，含数量缺口标记", "01 贸易结构"],
        ["03 主要来源国", "每年来源国前 8 位、金额与数量份额、单位价值", "01 贸易结构"],
        ["04 中国出口", "中国对印尼出口、占印尼进口、占中国全球出口", "01 贸易结构"],
        ["05 目标国出口", "印尼自身出口（判断再出口）", "01 贸易结构"],
        ["06 本地产能", "在运/在建/中试项目、产能口径、状态", "02 本地产能与企业"],
        ["07 下游企业", "已识别下游与采购角色、待核实项", "03 下游产业"],
        ["08 下游产业", "分段需求信号与缺口", "03 下游产业"],
        ["09 竞争与渠道", "竞争来源国、分销商、机构价格估算", "03 下游产业"],
        ["10 关税政策", "税率、状态（已核实/待核实）、来源", "04 关税与政策"],
        ["11 非关税措施", "LARTAS、BPOM/Halal、TKDN、SNI", "04 关税与政策"],
        ["12 贸易关系", "协定与政策变化时间线", "04 关税与政策"],
        ["13 研报要点", "公开研报/协会/政府资料要点与警示", "04 关税与政策"],
        ["14 数据缺口", "缺口清单、影响与补齐路径", "05 待核实事项"],
        ["15 待核实行动", "优先级、责任人、时点", "05 待核实事项"],
        ["16 来源清单", "全部来源、URL、可信等级", "06 口径与来源"],
    ]
    r = body(ws, r + 1, idx_rows, text_cols={2}, fill=BAND)
    auto_height(ws, r - len(idx_rows), r)

    r += 1
    ws.cell(row=r, column=1, value="四、可信等级（tier）").font = Font(name="Microsoft YaHei", size=11, bold=True, color=HEAD)
    r += 1
    r = body(ws, r, [["T1", "官方 / 国际组织直接公布（海关、统计局、部委、WTO/RCEP 文本）"],
                     ["T2", "政府指南（如 trade.gov 国别指南）、主流媒体对官方表态的报道"],
                     ["T3", "商业机构估算、行业媒体、第三方资料（方法与明细不公开）"],
                     ["T4", "第三方汇总站 / 付费数据商摘要，仅作线索，不能单独作为事实依据"]],
               text_cols={2}, fill=BAND)
    ws.column_dimensions["A"].width = 22
    return ws


def s_kpi(wb, case, idx, n=1):
    ws = wb.create_sheet("%02d 关键指标" % n)
    sheet_title(ws, "关键指标（首屏卡片的数据底稿）",
                "每个指标都标注它的证据类型与来源；标“缺口”的指标不得当作数据使用。", 6)
    header_row(ws, 4, ["指标", "数值", "说明", "证据类型", "来源 id", "备注"], [30, 18, 62, 14, 22, 30])
    rows = []
    for k in idx["kpi"]:
        rows.append([k["label"], k["value"], k["sub"], C.kind_label(k["kind"]) if k["kind"] != "gap" else "缺口", k.get("source") or "",
                     "缺口" if k["kind"] == "gap" else ""])
    extra = [
        ["金额 CAGR（%d–%d）" % tuple(idx["years_span"]), C.fmt_pct(idx["cagr_value"]), "首末年份几何平均", "推算", "comtrade", "由海关金额推算"],
        ["数量 CAGR", C.fmt_pct(idx["cagr_qty"]), "缺失年份不插值" if idx["cagr_qty"] is None else "", "推算", "comtrade",
         "缺口：数量未报送" if idx["cagr_qty"] is None else ""],
        ["金额峰值年份", str(idx["peak_value_year"] or ""), "区间内进口金额最高年", "官方统计", "comtrade", ""],
        ["金额峰值", C.fmt_money_usd(idx["peak_value"]), "", "官方统计", "comtrade", ""],
        ["数量历史分位", (C.fmt(idx["qty_hist_position"], 0) + "%") if idx["qty_hist_position"] is not None else "—",
         "最新年度数量在历史区间中的分位", "推算", "comtrade", ""],
        ["最新年平均单位价值", ("USD %s/t" % C.fmt(idx["unit_usd_t_latest"], 0)) if idx["unit_usd_t_latest"] else "缺口",
         "CIF 海关申报均价，非成交价", "推算", "comtrade", ""],
        ["供应集中度 HHI", C.fmt(idx["hhi_top"], 0), "前 N 位来源国金额份额平方和×10000", "推算", "comtrade",
         ">2500 视为高度集中"],
        ["再出口比例", (C.fmt(idx["reexport_ratio_latest"], 1) + "%") if idx["reexport_ratio_latest"] is not None else "—",
         "该国出口额 ÷ 进口额", "推算", "comtrade", ""],
        ["来源数量 / 缺口数量 / 待核实行动", "%d / %d / %d" % (idx["source_count"], idx["gap_count"], idx["verify_count"]), "本工作簿的证据密度", "", "", ""],
    ]
    r = body(ws, 5, rows + extra, text_cols={3} | ({6} if True else set()), fill=BAND)
    for i in range(5, 5 + len(rows)):
        if ws.cell(row=i, column=4).value == "缺口":
            ws.cell(row=i, column=4).fill = PatternFill("solid", fgColor=WARN)
            ws.cell(row=i, column=4).font = Font(name="Microsoft YaHei", size=10, bold=True, color=WARN_INK)
    auto_height(ws, 5, r)


def s_history(wb, case, idx, n=2):
    ws = wb.create_sheet("%02d 进口历史" % n)
    sheet_desc = ("金额=CIF；数量=netWgt（吨）；单位价值=金额÷数量。数量未报送的年份留空并标“未报送”，不做任何反推。")
    sheet_title(ws, "进口历史（逐年）", sheet_desc, 9)
    header_row(ws, 4, ["年份", "进口金额 USD", "金额（亿美元）", "金额同比 %", "进口数量（吨）", "数量同比 %",
                       "单位价值 USD/t", "数量口径", "来源"], [10, 18, 14, 12, 16, 12, 14, 12, 12])
    rows = []
    for r_ in idx["imports"]:
        rows.append([r_["year"], r_.get("value_usd"), (r_.get("value_usd") or 0) / 1e8 if r_.get("value_usd") else None,
                     (r_.get("yoy_value") / 100.0) if r_.get("yoy_value") is not None else None,
                     r_.get("qty_t"),
                     (r_.get("yoy_qty") / 100.0) if r_.get("yoy_qty") is not None else None,
                     r_.get("unit_usd_t"),
                     "已报送" if r_.get("qty_t") is not None else "未报送", "UN Comtrade"])
    r = body(ws, 5, rows, money_cols={2}, money2_cols={3}, num_cols={5, 7}, pct_cols={4, 6}, fill=BAND)
    for i in range(5, r):
        if ws.cell(row=i, column=8).value == "未报送":
            ws.cell(row=i, column=8).fill = PatternFill("solid", fgColor=WARN)
            ws.cell(row=i, column=8).font = Font(name="Microsoft YaHei", size=10, bold=True, color=WARN_INK)
    r += 1
    full = idx["imports_history"]
    hist_note = case["trade"].get("imports_history_note") or ""
    if len(full) > len(idx["imports"]):
        extra_years = [x["year"] for x in full if x["year"] not in [y["year"] for y in idx["imports"]]]
        hist_note = ("本表只列研究窗口（近 %s 年）；更长序列中另有 %s 年仅取得金额、无净重，"
                     "已单独存档不使用。%s" % (case["meta"].get("window"), "、".join(str(y) for y in extra_years), hist_note))
    ws.cell(row=r, column=1, value="口径提示：%s" % hist_note).font = F_SMALL
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    ws.cell(row=r, column=1).alignment = WRAP
    ws.row_dimensions[r].height = 34


def s_partners(wb, case, idx, n=3):
    ws = wb.create_sheet("%02d 主要来源国" % n)
    sheet_title(ws, "主要进口来源国（逐年前 8 位）",
                "份额以印尼当年海关进口金额/数量为分母；单位价值仅在同一年份有数量报送时计算。", 8)
    header_row(ws, 4, ["年份", "排名", "来源国", "伙伴代码", "金额 USD", "金额份额 %", "数量（吨）", "单位价值 USD/t"],
               [10, 8, 26, 12, 18, 13, 15, 15])
    rows = []
    for y in sorted(idx["partner_structure"], key=int):
        st = idx["partner_structure"][y]
        for p in st["rows"]:
            rows.append([int(y), p.get("rank"), p.get("name"), p.get("code"), p.get("value_usd"),
                         (p.get("share_value") or 0) / 100.0 if p.get("share_value") is not None else None,
                         p.get("qty_t"), p.get("unit_usd_t")])
    r = body(ws, 5, rows, money_cols={5}, num_cols={7, 8}, pct_cols={6}, text_cols={3}, fill=BAND)


def s_china(wb, case, idx, n=4):
    ws = wb.create_sheet("%02d 中国出口" % n)
    sheet_title(ws, "中国对该国出口（中国海关口径，FOB）",
                "中国对印尼出口与印尼自华进口由两国分别申报，CIF/FOB 与原产地差异会造成不一致；两套数字并列，不做调和。", 8)
    header_row(ws, 4, ["年份", "对目标国出口 USD", "对目标国数量（吨）", "单位价值 USD/t", "对世界出口 USD",
                       "同比 %", "占目标国进口 %", "占中国该产品全球出口 %"], [10, 18, 17, 14, 18, 11, 15, 18])
    rows = []
    for c in idx["china_exports"]:
        rows.append([c["year"], c.get("to_idn_usd"), c.get("to_idn_t"), c.get("unit_usd_t"), c.get("to_world_usd"),
                     (c.get("yoy_value") or 0) / 100.0 if c.get("yoy_value") is not None else None,
                     (c.get("share_of_idn_imports") or 0) / 100.0 if c.get("share_of_idn_imports") is not None else None,
                     (c.get("share_of_china_world") or 0) / 100.0 if c.get("share_of_china_world") is not None else None])
    r = body(ws, 5, rows, money_cols={2, 5}, num_cols={3, 4}, pct_cols={6, 7, 8}, fill=BAND)
    r += 1
    ws.cell(row=r, column=1, value=case["trade"].get("china_exports_note") or "").font = F_SMALL
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    ws.cell(row=r, column=1).alignment = WRAP
    ws.row_dimensions[r].height = 40


def s_exports(wb, case, idx, n=5):
    ws = wb.create_sheet("%02d 目标国出口" % n)
    sheet_title(ws, "目标国自身出口（判断是否再出口 / 转口）",
                "出口额相对进口额很低时，通常说明不是大规模转口国；但海关数据无法排除改包装或加工后复出口。", 5)
    header_row(ws, 4, ["年份", "出口金额 USD", "出口数量（吨）", "主要目的地", "占该国进口金额 %"], [10, 18, 16, 24, 18])
    rows = [[e["year"], e.get("value_usd"), e.get("qty_t"), e.get("top_dest"),
             (e.get("pct_of_imports_value") or 0) / 100.0 if e.get("pct_of_imports_value") is not None else None]
            for e in idx["exports"]]
    body(ws, 5, rows, money_cols={2}, num_cols={3}, pct_cols={5}, text_cols={4}, fill=BAND)


def s_capacity(wb, case, idx, n=6):
    ws = wb.create_sheet("%02d 本地产能" % n)
    sheet_title(ws, "本地生产与在建/中试项目",
                "产能 ≠ 产量；在建 ≠ 在运。产能数字一律注明是设计能力还是实测产量。", 9)
    header_row(ws, 4, ["企业", "角色", "地点", "状态", "状态截止", "产能（吨/年）", "产能口径", "产品", "来源 id"],
               [34, 16, 26, 12, 12, 14, 40, 30, 40])
    lps = case["industries"].get("local_production") or []
    rows = [[p.get("name"), p.get("role"), p.get("location"), p.get("status"), p.get("status_asof"),
             p.get("capacity_t"), p.get("capacity_basis"), "、".join(p.get("products") or []),
             ", ".join(p.get("sources") or [])] for p in lps]
    r = body(ws, 5, rows, money_cols={6}, text_cols={1, 3, 7, 8, 9}, fill=BAND)
    auto_height(ws, 5, r)
    r += 1
    ws.cell(row=r, column=1, value="“本地无规模化产能”的证据链").font = Font(name="Microsoft YaHei", size=11, bold=True, color=HEAD)
    r += 1
    header_row(ws, r, ["判断", "来源 id", "来源类型", "链接"], None)
    ev = case["industries"].get("local_absence_evidence") or []
    srcs = {s["id"]: s for s in case["sources"]}
    rows2 = [[e.get("claim"), e.get("source"), C.kind_label(e.get("kind") or (srcs.get(e.get("source")) or {}).get("kind")),
              (srcs.get(e.get("source")) or {}).get("url", "")] for e in ev]
    r2 = body(ws, r + 1, rows2, text_cols={1, 4}, fill=OKFILL)
    for i in range(r + 1, r2):
        c = ws.cell(row=i, column=4)
        if isinstance(c.value, str) and c.value.startswith("http"):
            c.hyperlink = c.value
            c.font = F_LINK
    auto_height(ws, r + 1, r2)


def s_consumers(wb, case, idx, n=7):
    ws = wb.create_sheet("%02d 下游企业" % n)
    sheet_title(ws, "已识别的下游 / 采购企业",
                "“采购角色”区分直接用户与配方方；未公开采购量的企业留空，并列出待核实项（这是下一次拜访的提纲）。", 10)
    header_row(ws, 4, ["企业", "类型", "地点", "产品", "采购角色", "公开事实", "待核实项", "来源 id"],
               [30, 20, 22, 30, 22, 60, 44, 34])
    rows = [[c.get("name"), c.get("type"), c.get("location"), c.get("products"), c.get("buying_role"),
             "\n".join("· " + f for f in (c.get("facts") or [])),
             "\n".join("· " + f for f in (c.get("verify") or [])),
             ", ".join(c.get("sources") or [])] for c in (case["industries"].get("consumers") or [])]
    r = body(ws, 5, rows, text_cols={1, 2, 3, 4, 5, 6, 7, 8}, fill=BAND)
    auto_height(ws, 5, r, cap=160)
    r += 1
    ws.cell(row=r, column=1, value="未落到具体企业的下游集群").font = Font(name="Microsoft YaHei", size=11, bold=True, color=HEAD)
    r += 1
    header_row(ws, r, ["集群", "为什么未具名", "检索建议"], None)
    rows2 = [[u.get("segment"), u.get("why_unnamed"), u.get("search_hint")] for u in (case["industries"].get("consumers_unnamed") or [])]
    body(ws, r + 1, rows2, text_cols={1, 2, 3}, fill=GAP)


def s_downstream(wb, case, idx, n=8):
    ws = wb.create_sheet("%02d 下游产业" % n)
    sheet_title(ws, "下游产业与需求信号",
                "本表只记录“谁在用、有什么证据”；产量、吨耗、应用拆分需求量属于缺口，见 14 数据缺口。", 6)
    header_row(ws, 4, ["下游分段", "需求信号（原文要点）", "规模线索", "缺口（不填数）", "来源 id"], [20, 66, 34, 40, 34])
    rows = [[i.get("segment"), i.get("demand_signal"), i.get("scale_note"), i.get("gap"), ", ".join(i.get("sources") or [])]
            for i in (case["downstream"].get("items") or [])]
    r = body(ws, 5, rows, text_cols={1, 2, 3, 4, 5}, fill=BAND)
    auto_height(ws, 5, r, cap=140)


def s_competition(wb, case, idx, n=9):
    ws = wb.create_sheet("%02d 竞争与渠道" % n)
    sheet_title(ws, "竞争来源国、当地渠道与价格线索",
                "机构估算价格单独标注，不得作为报价锚点。", 5)
    header_row(ws, 4, ["类型", "对象", "说明", "证据 / 来源"], [16, 30, 70, 44])
    rows = []
    for c in (case.get("competition", {}).get("source_countries") or []):
        rows.append(["竞争来源国", c.get("name"), c.get("basis"), c.get("evidence") or ""])
    for d in (case.get("competition", {}).get("distributors") or []):
        rows.append(["当地渠道", d.get("name"), "%s（%s）" % (d.get("role"), d.get("products")), d.get("source") or ""])
    for p in (case.get("competition", {}).get("price_observation") or []):
        rows.append(["价格线索（%s）" % C.kind_label(p.get("kind")), "机构估算", p.get("claim"), p.get("note") or ""])
    r = body(ws, 5, rows, text_cols={2, 3, 4}, fill=BAND)
    auto_height(ws, 5, r, cap=110)
    for i in range(5, r):
        if str(ws.cell(row=i, column=1).value).startswith("价格线索"):
            for j in range(1, 5):
                ws.cell(row=i, column=j).fill = PatternFill("solid", fgColor=GAP)


def s_tariff(wb, case, idx, n=10):
    ws = wb.create_sheet("%02d 关税政策" % n)
    pol = case["policy"]
    sheet_title(ws, "关税与进口税负",
                "只有能从官方来源直接核验的税率才填数值；其余一律“待核实”，不得写进报价单。", 6)
    header_row(ws, 4, ["项目", "税率 %", "状态", "说明", "来源 id", "备注"], [26, 10, 12, 84, 40, 20])
    rows = []
    for t in pol.get("tariffs") or []:
        rows.append([t.get("item"), t.get("rate_pct"), "已核实" if t.get("status") in ("fact", "official") else "待核实",
                     t.get("detail"), ", ".join(t.get("sources") or []),
                     "需用 HS %s 在 INSW 核验" % case["meta"]["subject"]["hs_code"] if t.get("rate_pct") is None else ""])
    r = body(ws, 5, rows, pct_cols={2}, text_cols={4, 5, 6}, fill=BAND)
    for i in range(5, r):
        if ws.cell(row=i, column=3).value == "待核实":
            ws.cell(row=i, column=3).fill = PatternFill("solid", fgColor=WARN)
            ws.cell(row=i, column=3).font = Font(name="Microsoft YaHei", size=10, bold=True, color=WARN_INK)
    auto_height(ws, 5, r, cap=160)
    r += 1
    ws.cell(row=r, column=1, value="税号：%s — %s" % (pol["hs_line"]["code"], pol["hs_line"]["description"])).font = F_BOLD
    r += 1
    ws.cell(row=r, column=1, value=pol["hs_line"].get("verify_note") or "").font = F_SMALL
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    ws.cell(row=r, column=1).alignment = WRAP


def s_ntm(wb, case, idx, n=11):
    ws = wb.create_sheet("%02d 非关税措施" % n)
    sheet_title(ws, "非关税措施与进口管理制度", "状态“待确认”的项目在发货前必须由进口商书面确认。", 5)
    header_row(ws, 4, ["措施", "状态", "说明", "来源 id"], [26, 12, 92, 40])
    rows = [[x.get("item"), "已核实" if x.get("status") == "fact" else "待确认", x.get("detail"),
             ", ".join(x.get("sources") or [])] for x in (case["policy"].get("ntm") or [])]
    r = body(ws, 5, rows, text_cols={1, 3, 4}, fill=BAND)
    for i in range(5, r):
        if ws.cell(row=i, column=2).value == "待确认":
            ws.cell(row=i, column=2).fill = PatternFill("solid", fgColor=GAP)
    auto_height(ws, 5, r, cap=170)


def s_relations(wb, case, idx, n=12):
    ws = wb.create_sheet("%02d 贸易关系" % n)
    sheet_title(ws, "与中国的贸易关系及近期政策变化（时间线）", "只记录已核实的事件；未取得全文的协定在这里注明。", 5)
    header_row(ws, 4, ["时点", "事件", "状态", "说明", "来源 id"], [16, 30, 10, 84, 40])
    dates = {"r-acfta3": "2025-10-28", "r-rcep": "2023-01-02", "r-import-policy": "2025-06-30", "r-localization": "2025-10-31 起"}
    rows = [[dates.get(x.get("id"), ""), x.get("item"), "已核实" if x.get("status") == "fact" else "待确认",
             x.get("detail"), ", ".join(x.get("sources") or [])] for x in (case["policy"].get("trade_relations") or [])]
    rows.sort(key=lambda r_: r_[0] or "")
    r = body(ws, 5, rows, text_cols={2, 4, 5}, fill=BAND)
    auto_height(ws, 5, r, cap=160)


def s_reports(wb, case, idx, n=13):
    ws = wb.create_sheet("%02d 研报要点" % n)
    sheet_title(ws, "公开研究报告 / 协会 / 政府资料要点",
                "每条都带警示（caveat）：机构估算不能当事实，政府表态不等于数据。", 6)
    header_row(ws, 4, ["类型", "标题", "要点", "警示", "来源 id"], [20, 46, 76, 44, 22])
    rows = [[x.get("type"), x.get("title"), "\n".join("· " + p for p in (x.get("key_points") or [])),
             x.get("caveat"), x.get("source")] for x in (case.get("reports") or [])]
    r = body(ws, 5, rows, text_cols={1, 2, 3, 4, 5}, fill=BAND)
    auto_height(ws, 5, r, cap=170)
    for i in range(5, r):
        if "估算" in str(ws.cell(row=i, column=1).value):
            ws.cell(row=i, column=1).fill = PatternFill("solid", fgColor=GAP)


def s_gaps(wb, case, idx, n=14):
    ws = wb.create_sheet("%02d 数据缺口" % n)
    sheet_title(ws, "数据缺口清单（本表没有数字，这是刻意的）",
                "缺口不是失败，而是下一次调研的清单；把它当成“不知道”写进报告，比编一个数字更有用。", 6)
    header_row(ws, 4, ["#", "层级", "缺什么", "为什么缺", "对销售判断的影响", "怎么补"], [6, 12, 40, 56, 50, 56])
    rows = [[i + 1, g.get("level"), g.get("item"), g.get("why"), g.get("impact"), g.get("how_to_close")]
            for i, g in enumerate(case.get("gaps") or [])]
    r = body(ws, 5, rows, text_cols={3, 4, 5, 6}, fill=WARN)
    auto_height(ws, 5, r, cap=150)


def s_actions(wb, case, idx, n=15):
    ws = wb.create_sheet("%02d 待核实行动" % n)
    sheet_title(ws, "待核实行动清单", "P0 = 报价前必须解决；P1 = 首轮触达；P2 = 签约前后台确认。", 5)
    header_row(ws, 4, ["优先级", "行动", "责任人", "时点", "状态（人工填写）"], [10, 76, 20, 18, 20])
    rows = [[v.get("priority"), v.get("action"), v.get("owner"), v.get("when"), ""] for v in (case.get("verify_actions") or [])]
    r = body(ws, 5, rows, text_cols={2, 3, 4, 5}, fill=BAND)
    for i in range(5, r):
        (ws.cell(row=i, column=1)).fill = PatternFill("solid", fgColor=WARN if ws.cell(row=i, column=1).value == "P0" else GAP)
    auto_height(ws, 5, r, cap=90)


def s_sources(wb, case, idx, n=16):
    ws = wb.create_sheet("%02d 来源清单" % n)
    sheet_title(ws, "来源清单（全部可点击核对）", "T1 官方 → T4 第三方汇总；T4 只能作为线索。", 7)
    header_row(ws, 4, ["#", "等级", "类型", "标题", "发布方", "日期", "URL"], [5, 8, 16, 62, 30, 16, 78])
    rows = [[i + 1, "T%s" % s.get("tier", ""), s.get("kind"), s.get("title"), s.get("publisher"),
             s.get("date"), s.get("url")] for i, s in enumerate(case.get("sources") or [])]
    r = body(ws, 5, rows, text_cols={4, 5, 7}, fill=BAND)
    for i in range(5, r):
        c = ws.cell(row=i, column=7)
        if isinstance(c.value, str) and c.value.startswith("http"):
            c.hyperlink = c.value
            c.font = F_LINK
    auto_height(ws, 5, r, cap=60)


SHEETS = [s_readme, s_kpi, s_history, s_partners, s_china, s_exports, s_capacity, s_consumers,
          s_downstream, s_competition, s_tariff, s_ntm, s_relations, s_reports, s_gaps, s_actions, s_sources]


def build(case, out):
    idx = C.build_index(case)
    wb = Workbook()
    wb.remove(wb.active)
    for fn in SHEETS:
        try:
            fn(wb, case, idx)
        except TypeError:
            fn(wb, case, idx)
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.tabColor = ACCENT
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    wb.save(out)
    return out, len(wb.worksheets)


def default_name(case):
    m = case["meta"]
    return "%s-%s_国别市场研究.xlsx" % (m["country"]["name_cn"], m["subject"]["product_cn"].split("（")[0])


def main():
    ap = argparse.ArgumentParser(description="生成国别市场研究 Excel 工作底稿")
    ap.add_argument("case")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    case = C.load_json(a.case)
    errs, warns = C.validate_case(case)
    if errs:
        for e in errs:
            print("ERROR", e, file=sys.stderr)
        sys.exit(1)
    out, n = build(case, a.out or os.path.join("out", default_name(case)))
    print("Excel 已生成 %s（%d 个工作表）" % (out, n))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

