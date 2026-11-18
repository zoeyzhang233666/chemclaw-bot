# -*- coding: utf-8 -*-
"""
build_xlsx.py —— 生成多工作表 Excel 工作簿（含真公式）
=======================================================
工作表：
  00_说明          口径、数据源、局限、如何用公式复核
  01_基差日度       逐日基差 + 滚动分位（真公式复算分位排名，供核对）
  02_滚动分位计算   分位计算的逐步展开（窗口、样本数、小于/等于计数、秩）
  03_前瞻表现       每个交易日 × 每个观察期的 现货/期货/基差 收益
  04_分组统计       低/中/高 分位 × 观察期 的均值/中位/分布/样本量
  05_推断与自 aid    低-高差值、区间、p 值、非重叠复核
  06_敏感性         阈值 × 窗口 × 观察期 矩阵
  07_稳定性         年度 / 月份 / 期限结构
  08_偏差清单       换月、交割临近、口径核验、样本重叠
  09_合约映射       逐日合约映射 + 换月标记
  10_合约日历       每个合约的最后交易日核验
  11_数据源         每个数据源的 URL 与抓取时间

用法：
  python build_xlsx.py --data out/report_data.json --out out/报告.xlsx
"""
from __future__ import annotations

import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

NAVY = "1F3864"
BLUE = "2E75B6"
LIGHT = "DEEBF7"
GREY = "F2F2F2"
WARN = "FFF2CC"
RED = "C00000"
GREEN = "2E7D32"

TITLE_FONT = Font(name="微软雅黑", size=15, bold=True, color=NAVY)
SUB_FONT = Font(name="微软雅黑", size=10, color="595959")
HDR_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
BODY = Font(name="微软雅黑", size=10)
BOLD = Font(name="微软雅黑", size=10, bold=True)
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def sheet_title(ws, title, sub="", width=10):
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws.row_dimensions[1].height = 24
    if sub:
        ws["A2"] = sub
        ws["A2"].font = SUB_FONT
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)


def header_row(ws, row, headers, widths=None, fill=NAVY):
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=j, value=h)
        c.font = HDR_FONT
        c.fill = PatternFill("solid", fgColor=fill)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 30
    if widths:
        for j, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(j)].width = w


def style_body(ws, r0, r1, nc, numfmt_map=None, band=True):
    for i in range(r0, r1 + 1):
        for j in range(1, nc + 1):
            c = ws.cell(row=i, column=j)
            c.font = BODY
            c.border = BOX
            if band and (i - r0) % 2 == 1:
                c.fill = PatternFill("solid", fgColor=GREY)
            if numfmt_map and j in numfmt_map:
                c.number_format = numfmt_map[j]


def fmt_pct(v):
    return v


def build(data_path, out_path):
    import json
    D = json.load(open(data_path, encoding="utf-8"))
    META, ST = D["meta"], D["stats"]
    COLS, ROWS = D["bars"]["cols"], D["bars"]["rows"]
    I = {c: i for i, c in enumerate(COLS)}

    wb = Workbook()

    # ---------------- 00 说明 ----------------
    ws = wb.active
    ws.title = "00_说明"
    sheet_title(ws, "甲醇基差分位信息检验 · 数据说明与复核口径",
                "所有数字均由原始抓取数据本地计算；本工作簿只做历史统计，不含交易建议。", 6)
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 110
    rows = [
        ("研究问题", "基差处于历史高/低分位时，之后 1/2/4 周（及 3/6 月）的现货价格、期货价格与基差各自如何变化。"),
        ("基差定义", "基差 = 现货 − 期货（元/吨）；基差率 = (现货 − 期货) / 现货；基差收益 = 现货收益 − 期货收益。"),
        ("现货口径", "生意社 100ppi「甲醇基准价」——全国口径的含税交易指导价，【非华东/太仓实盘价】，属降级口径。"),
        ("期货口径", "郑商所 MA 逐合约日线，主力连续 = 当日持仓量最大且未到期的合约；换月为旧合约 OI 被超越的次日。"),
        ("滚动分位", "P_t = (#{B_j < B_t} + 0.5·#{B_j = B_t}) / N，j ∈ [t−W, t−1]，严格滞后，不含未来。"),
        ("分组阈值", "低分位 P ≤ k；高分位 P ≥ 1−k；其余为中间分位。默认 k=20%，W=250 交易日。"),
        ("观察期", "1/5/10/20/60/120 个交易日（约 1日/1周/2周/4周/3月/6月）。"),
        ("两种收益口径", "信息检验：分位在 t，收益区间 [t, t+h]；可操作口径：分位 t−h，收益区间 [t−h, t]（时点全已知）。"),
        ("样本区间", f"{META['basis_first']} ~ {META['basis_last']}，{META['aligned_n']} 个对齐交易日，{META['contracts']} 个合约。"),
        ("分位起始", f"{META['pct_first']}（需要 W 个历史点才能算第一个分位）。"),
        ("末端回填", f"{META['pit_known_last']} 之后的 {META['pit_unknown_n']} 个点分位为数据末端回填，时间稳定性检验剔除。"),
        ("自助法", f"循环块自助，块长 = h，R = {META['n_boot']}；块长 ≥ 样本半数时判定退化，不给 p 值。"),
        ("重要限制", "① 现货为全国基准价，非华东实盘；② 主力连续在换月日有月差伪跳变；③ 样本仅约 4 年，跨年稳定性功效有限；④ 未扣交易成本。"),
        ("免责", "本工作簿展示历史已实现关系，不是预测，不构成任何交易建议。"),
    ]
    header_row(ws, 4, ["项目", "说明"], [22, 110])
    for i, (k, v) in enumerate(rows, start=5):
        ws.cell(row=i, column=1, value=k).font = BOLD
        ws.cell(row=i, column=2, value=v).font = BODY
        ws.cell(row=i, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=i, column=1).border = BOX
        ws.cell(row=i, column=2).border = BOX
        ws.row_dimensions[i].height = 30

    # ---------------- 01 基差日度 ----------------
    ws = wb.create_sheet("01_基差日度")
    sheet_title(ws, "01 基差日度序列（主力连续）",
                "I 列分位由 Python 按严格滞后窗口计算；J 列用 Excel 公式对 I 列做独立复核（应完全一致）。")
    hdr = ["日期", "合约", "交割月", "现货(元/吨)", "期货(元/吨)", "基差(元/吨)", "基差率",
           "持仓量", "滚动分位", "分位(公式复核)", "分组", "距最后交易日", "期限结构",
           "当时已知?", "换月日", "主-次价差", "标记"]
    header_row(ws, 4, hdr, [11, 9, 9, 12, 12, 12, 9, 12, 10, 12, 10, 12, 14, 9, 8, 10, 12])
    r0 = 5
    W = META["main_window"]
    for n, row in enumerate(ROWS):
        r = r0 + n
        ws.cell(row=r, column=1, value=row[I["date"]])
        ws.cell(row=r, column=2, value=row[I["contract"]])
        ws.cell(row=r, column=3, value=row[I["contract_month"]])
        ws.cell(row=r, column=4, value=row[I["spot"]])
        ws.cell(row=r, column=5, value=row[I["fut"]])
        ws.cell(row=r, column=6, value=f"=D{r}-E{r}")
        ws.cell(row=r, column=7, value=f"=IF(D{r}=0,\"\",(D{r}-E{r})/D{r})")
        ws.cell(row=r, column=8, value=row[I["oi"]])
        ws.cell(row=r, column=9, value=row[I["basis_pct_lag"]])
        # Excel 公式复核：对窗口内 G 列做排名统计（公式与引擎 _rank_of 完全同构）
        if n >= 20:
            lo = r0 + n - W
            ws.cell(row=r, column=10,
                    value=(f"=IF(COUNT(G{lo}:G{r-1})<20,\"\","
                           f"IF(COUNTIF(G{lo}:G{r-1},\"<\"&G{r})>=COUNT(G{lo}:G{r-1}),"
                           f"(COUNT(G{lo}:G{r-1})-0.5)/COUNT(G{lo}:G{r-1}),"
                           f"IF(COUNTIF(G{lo}:G{r-1},G{r})>0,"
                           f"(COUNTIF(G{lo}:G{r-1},\"<\"&G{r})+0.5*COUNTIF(G{lo}:G{r-1},G{r}))/COUNT(G{lo}:G{r-1}),"
                           f"COUNTIF(G{lo}:G{r-1},\"<\"&G{r})/COUNT(G{lo}:G{r-1}))))"))
        ws.cell(row=r, column=11, value=row[I["group_lag"]])
        ws.cell(row=r, column=12, value=row[I["days_to_ltd"]])
        ws.cell(row=r, column=13, value=row[I["regime"]])
        ws.cell(row=r, column=14, value=row[I["point_in_time_known"]])
        ws.cell(row=r, column=15, value=row[I["roll_day"]])
        ws.cell(row=r, column=16, value=row[I["spread_next"]])
        ws.cell(row=r, column=17, value=row[I["flags"]])
    last = r0 + len(ROWS) - 1
    style_body(ws, r0, last, len(hdr),
               {4: "#,##0.0", 5: "#,##0.0", 6: "#,##0.0", 7: "0.00%", 8: "#,##0",
                9: "0.0%", 10: "0.0%", 16: "#,##0.0"})
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:Q{last}"

    # ---------------- 02 滚动分位计算过程 ----------------
    ws = wb.create_sheet("02_滚动分位计算")
    sheet_title(ws, "02 滚动分位计算过程（逐步展开）",
                f"以 W={W} 为例：窗口取 t−W..t−1 共 W 个基差率，统计小于/等于当日值的个数，得到百分位秩。")
    header_row(ws, 4, ["日期", "当日基差率", "窗口起始日", "窗口结束日", "窗口样本数",
                       "小于当日值个数", "等于当日值个数", "百分位秩", "分组", "说明"],
               [12, 2, 12, 12, 11, 15, 15, 11, 11, 42])
    ws.column_dimensions["B"].width = 15
    r0 = 5
    cnt = 0
    for n, row in enumerate(ROWS):
        if n < 20 or row[I["basis_pct_lag"]] is None:
            continue
        lo = max(0, n - W)
        # 用未舍入的精确基差率判断并列：精简数据保留 6 位小数，
        # 直接把舍入后的值拿去比会制造“假并列”，导致 02 表与引擎差一位。
        hist = [ROWS[k][I["basis"]] / ROWS[k][I["spot"]] if ROWS[k][I["spot"]] else None
                for k in range(lo, n)]
        hist = [v for v in hist if v is not None]
        cur = row[I["basis"]] / row[I["spot"]] if row[I["spot"]] else None
        less = sum(1 for v in hist if v < cur)
        eq = sum(1 for v in hist if v == cur)
        r = r0 + cnt
        ws.cell(row=r, column=1, value=row[I["date"]])
        ws.cell(row=r, column=2, value=cur)
        ws.cell(row=r, column=3, value=ROWS[lo][I["date"]])
        ws.cell(row=r, column=4, value=ROWS[n - 1][I["date"]])
        ws.cell(row=r, column=5, value=len(hist))
        ws.cell(row=r, column=6, value=less)
        ws.cell(row=r, column=7, value=eq)
        ws.cell(row=r, column=8,
                value=f"=IF(F{r}>=E{r},(E{r}-0.5)/E{r},IF(G{r}>0,(F{r}+0.5*G{r})/E{r},F{r}/E{r}))")
        ws.cell(row=r, column=9, value=row[I["group_lag"]])
        ws.cell(row=r, column=10,
                value=("窗口不含当日（严格滞后）；分位只用 t 之前信息。"
                       "秩公式：有并列 (小于+0.5×等于)/N；无并列 小于/N；" if cnt == 0
                       else ""))
        cnt += 1
    style_body(ws, r0, r0 + cnt - 1, 10, {2: "0.0000", 8: "0.0%"})
    ws.freeze_panes = "A5"

    # ---------------- 03 前瞻表现 ----------------
    ws = wb.create_sheet("03_前瞻表现")
    sheet_title(ws, "03 前瞻表现（每个交易日 × 每个观察期）",
                "信息检验口径：分位来自 t 日，收益为 [t, t+h]。基差收益 = 现货收益 − 期货收益（恒等式）。")
    hs = [h for h in [1, 5, 10, 20, 60, 120] if ("spot_ret_%d" % h) in I]
    hdr = ["日期", "分组", "滚动分位"]
    for h in hs:
        hdr += [f"现货{h}日", f"期货{h}日", f"基差{h}日", f"期货贡献{h}日"]
    header_row(ws, 4, hdr, [11, 10, 10] + [11] * (4 * len(hs)))
    r0 = 5
    for n, row in enumerate(ROWS):
        r = r0 + n
        ws.cell(row=r, column=1, value=row[I["date"]])
        ws.cell(row=r, column=2, value=row[I["group_lag"]])
        ws.cell(row=r, column=3, value=row[I["basis_pct_lag"]])
        for k, h in enumerate(hs):
            base = 4 + k * 4
            ws.cell(row=r, column=base, value=row[I[f"spot_ret_{h}"]])
            ws.cell(row=r, column=base + 1, value=row[I[f"fut_ret_{h}"]])
            ws.cell(row=r, column=base + 2, value=row[I[f"basis_ret_{h}"]])
            ws.cell(row=r, column=base + 3, value=row[I[f"future_share_{h}"]])
    style_body(ws, r0, r0 + len(ROWS) - 1, len(hdr),
               {**{c: "0.00%" for c in range(4, 4 + 4 * len(hs))}, 3: "0.0%"})
    ws.freeze_panes = "D5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(hdr))}{r0+len(ROWS)-1}"

    # ---------------- 04 分组统计 ----------------
    ws = wb.create_sheet("04_分组统计")
    sheet_title(ws, "04 分组统计：低/中/高分位 × 观察期",
                "均值/中位/离散度/分位数/样本量。信息检验口径。")
    hdr = ["分组", "观察期", "观察期(日)", "样本量", "基差-均值", "基差-中位", "基差-标准差",
           "基差-P10", "基差-P25", "基差-P75", "基差-P90", "偏度", "超额峰度",
           "正收益占比", "负收益占比", "均值抽样偏度", "正部占比",
           "现货-均值", "现货-中位", "期货-均值", "期货-中位", "换月日占比",
           "最小", "最大"]
    header_row(ws, 4, hdr, [10, 9, 10, 8, 10, 10, 10, 9, 9, 9, 9, 9, 9, 10, 10, 11, 9,
                            10, 10, 10, 10, 10, 9, 9])
    LBL = {1: "1日", 5: "1周", 10: "2周", 20: "4周", 60: "3月", 120: "6月"}
    r0 = 5
    n_r = 0
    for b in ST["bucket_info"]:
        r = r0 + n_r
        vals = [b["group"], LBL.get(b["horizon"], str(b["horizon"])), b["horizon"], b["n"],
                b["basis_ret_mean"], b["basis_ret_median"], b["basis_ret_std"],
                b["basis_ret_p10"], b["basis_ret_p25"], b["basis_ret_p75"], b["basis_ret_p90"],
                b["basis_ret_skew"], b["basis_ret_kurt"], b["basis_ret_share_pos"],
                b["basis_ret_share_neg"], b["basis_ret_mean_skew"], b["basis_ret_mean_pos_share"],
                b["spot_ret_mean"], b["spot_ret_median"], b["fut_ret_mean"], b["fut_ret_median"],
                b["roll_share"], b["basis_ret_min"], b["basis_ret_max"]]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
        n_r += 1
    style_body(ws, r0, r0 + n_r - 1, len(hdr),
               {c: "0.00%" for c in (5, 6, 7, 8, 9, 10, 11, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24)})
    ws.freeze_panes = "C5"

    # ---------------- 05 推断 ----------------
    ws = wb.create_sheet("05_推断与自助")
    sheet_title(ws, "05 低分位 − 高分位 差值与自助推断",
                "块自助（块长=h）处理重叠样本；t = 差值/自助标准差；退化情形不给 p。")
    header_row(ws, 4, ["观察期", "n低", "n高", "低均值", "高均值", "低−高", "95%下界", "95%上界",
                       "块自助 p", "经验 p", "t=差值/sd", "块长", "退化?",
                       "现货差", "现货 p", "期货差", "期货 p"],
               [9, 7, 7, 10, 10, 10, 10, 10, 11, 10, 11, 7, 8, 10, 10, 10, 10])
    r0 = 5
    n_r = 0
    for d in ST["diff"]:
        r = r0 + n_r
        vals = [LBL.get(d["horizon"], str(d["horizon"])), d["n_low"], d["n_high"], d["low_mean"],
                d["high_mean"], d["low_minus_high"], d["ci_lo"], d["ci_hi"], d["boot_p"],
                d.get("p_emp"), d.get("obs_over_sd"), d.get("blocksize"),
                "是：%s" % d.get("reason") if d.get("degenerate") else "否",
                d["spot_low_minus_high"], d["spot_boot_p"], d["fut_low_minus_high"], d["fut_boot_p"]]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
        n_r += 1
    style_body(ws, r0, r0 + n_r - 1, 17,
               {c: "0.00%" for c in (4, 5, 6, 7, 8, 14, 16)})
    # 非重叠复核
    r = r0 + n_r + 2
    ws.cell(row=r, column=1, value="非重叠子样本复核（每 h 日取一个，块长=1）").font = BOLD
    r += 1
    header_row(ws, r, ["观察期", "n低", "n高", "低均值", "高均值", "低−高", "p"], None, fill=BLUE)
    for x in ST["non_overlap"]:
        r += 1
        for j, v in enumerate([LBL.get(x["horizon"], x["horizon"]), x["n_low"], x["n_high"],
                               x["low_mean"], x["high_mean"], x["diff"], x["p"]], start=1):
            ws.cell(row=r, column=j, value=v)
        for j in (4, 5, 6):
            ws.cell(row=r, column=j).number_format = "0.00%"

    # ---------------- 06 敏感性 ----------------
    ws = wb.create_sheet("06_敏感性")
    sheet_title(ws, "06 敏感性：阈值 × 滚动窗口 × 观察期",
                "单元格为「低分位均值 − 高分位均值」，括号内为块自助 p 值。")
    r = 4
    for w in sorted(ST["sensitivity"], key=int):
        ws.cell(row=r, column=1, value=f"滚动窗口 W = {w} 交易日").font = Font(
            name="微软雅黑", size=11, bold=True, color=BLUE)
        r += 1
        rs = ST["sensitivity"][w]
        ths = sorted({x["threshold"] for x in rs})
        hz = sorted({x["horizon"] for x in rs if x["horizon"] >= 5})
        header_row(ws, r, ["阈值 k", "样本量 低/高"] + [f"{LBL.get(h,h)} 低−高(p)" for h in hz],
                   None, fill=BLUE)
        for k in ths:
            r += 1
            s0 = next(x for x in rs if x["threshold"] == k and x["horizon"] == 5)
            ws.cell(row=r, column=1, value=f"{k:.0%} / {1-k:.0%}")
            ws.cell(row=r, column=2, value=f"{s0['n_low']} / {s0['n_high']}")
            for j, h in enumerate(hz, start=3):
                x = next(q for q in rs if q["threshold"] == k and q["horizon"] == h)
                v = x["low_minus_high"]
                p = x["boot_p"]
                cell = ws.cell(row=r, column=j,
                               value=v if v is not None else "")
                cell.number_format = "0.00%"
                if p is None:
                    ws.cell(row=r, column=j).fill = PatternFill("solid", fgColor=WARN)
        r += 2
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 14
    for j in range(3, 9):
        ws.column_dimensions[get_column_letter(j)].width = 18

    # ---------------- 07 稳定性 ----------------
    ws = wb.create_sheet("07_稳定性")
    sheet_title(ws, "07 稳定性：年度 / 月份 / 期限结构",
                "年度与前两列剔除末端回填样本；4 周观察期。")
    r = 4
    ws.cell(row=r, column=1, value="按年度（全样本）").font = Font(name="微软雅黑", size=11, bold=True, color=BLUE)
    r += 1
    header_row(ws, r, ["年份", "样本", "基差均值", "基差中位", "现货均值", "期货均值", "正收益占比"],
               [10, 8, 11, 11, 11, 11, 11], fill=BLUE)
    for y in ST["stability"]["20"]["year_full"]:
        r += 1
        for j, v in enumerate([y["year"], y["n"], y["basis_ret_mean"], y["basis_ret_median"],
                               y["spot_ret_mean"], y["fut_ret_mean"], y["share_pos"]], start=1):
            ws.cell(row=r, column=j, value=v)
        for j in (3, 4, 5, 6, 7):
            ws.cell(row=r, column=j).number_format = "0.00%"
    r += 2
    ws.cell(row=r, column=1, value="按自然月（全样本，4 周）").font = Font(
        name="微软雅黑", size=11, bold=True, color=BLUE)
    r += 1
    header_row(ws, r, ["月份", "样本", "基差均值", "基差中位"], [10, 8, 11, 11], fill=BLUE)
    for m in ST["stability"]["20"]["month_full"]:
        r += 1
        for j, v in enumerate([f"{m['month']}月", m["n"], m["basis_ret_mean"], m["basis_ret_median"]], start=1):
            ws.cell(row=r, column=j, value=v)
        for j in (3, 4):
            ws.cell(row=r, column=j).number_format = "0.00%"
    r += 2
    ws.cell(row=r, column=1, value="按期限结构（全样本，4 周）").font = Font(
        name="微软雅黑", size=11, bold=True, color=BLUE)
    r += 1
    header_row(ws, r, ["期限结构", "样本", "基差均值", "基差中位", "现货均值", "期货均值"], None, fill=BLUE)
    for g in ST["stability"]["20"]["regime_full"]:
        r += 1
        for j, v in enumerate([g["regime"], g["n"], g["basis_ret_mean"], g["basis_ret_median"],
                               g["spot_ret_mean"], g["fut_ret_mean"]], start=1):
            ws.cell(row=r, column=j, value=v)
        for j in (3, 4, 5, 6):
            ws.cell(row=r, column=j).number_format = "0.00%"
    r += 2
    ws.cell(row=r, column=1, value="按年度 × 分组（4 周）").font = Font(name="微软雅黑", size=11, bold=True, color=BLUE)
    r += 1
    header_row(ws, r, ["分组", "年份", "样本", "基差均值", "基差中位"], None, fill=BLUE)
    for g, lst in ST["stability"]["20"]["year_groups"].items():
        for y in lst:
            r += 1
            for j, v in enumerate([g, y["year"], y["n"], y["basis_ret_mean"], y["basis_ret_median"]], start=1):
                ws.cell(row=r, column=j, value=v)
            ws.cell(row=r, column=4).number_format = "0.00%"
            ws.cell(row=r, column=5).number_format = "0.00%"

    # ---------------- 08 偏差清单 ----------------
    ws = wb.create_sheet("08_偏差清单")
    sheet_title(ws, "08 偏差清单：换月 / 交割临近 / 口径核验 / 样本重叠",
                "每一项都给实测数字，避免“已注意”式空话。")
    r = 4
    ws.cell(row=r, column=1, value="① 换月污染").font = Font(name="微软雅黑", size=11, bold=True, color=RED)
    r += 1
    header_row(ws, r, ["观察期", "换月日|Δ|中位", "非换月|Δ|中位", "倍数", "换月日占比",
                       "单日换月|Δ|中位", "单日非换月|Δ|中位"], None, fill=BLUE)
    for x in ST["roll"]["by_horizon"]:
        r += 1
        for j, v in enumerate([x["horizon"], x["roll_abs_median"], x["normal_abs_median"], x["ratio"],
                               x["risk_share_roll"], x["roll_1d_abs_median"], x["normal_1d_abs_median"]], start=1):
            ws.cell(row=r, column=j, value=v)
        ws.cell(row=r, column=2).number_format = "0.00%"
        ws.cell(row=r, column=3).number_format = "0.00%"
        ws.cell(row=r, column=5).number_format = "0.0%"
        ws.cell(row=r, column=6).number_format = "0.00%"
        ws.cell(row=r, column=7).number_format = "0.00%"
    r += 1
    ws.cell(row=r, column=1, value="③ 口径核验：重建基差率 vs 100ppi 公布值").font = Font(
        name="微软雅黑", size=11, bold=True, color=RED)
    r += 1
    V = ST["verify"]
    LA = V.get("level_adjust", {})
    for k, v in [("重合交易日", V.get("n")), ("±0.5pp 一致率", V.get("agree_share")),
                 ("±1.0pp 一致率", V.get("agree_share_1pt")),
                 ("偏差中位|·|(pp)", V.get("median_abs_gap")), ("偏差P90|·|(pp)", V.get("p90_abs_gap")),
                 ("隐含水平差中位(元/吨)", LA.get("median_adj")), ("水平差P25", LA.get("p25")),
                 ("水平差P75", LA.get("p75"))]:
        r += 1
        ws.cell(row=r, column=1, value=k).font = BODY
        ws.cell(row=r, column=2, value=v).font = BODY
    r += 2
    ws.cell(row=r, column=1, value="水平平移后分组稳健性").font = Font(name="微软雅黑", size=11, bold=True, color=RED)
    r += 1
    header_row(ws, r, ["观察期", "低分位均值", "中间均值", "高分位均值", "低−高"], None, fill=BLUE)
    for x in V.get("level_adjusted_effects", []):
        r += 1
        ws.cell(row=r, column=1, value=x["horizon"])
        for j, g in enumerate(["低分位", "中间分位", "高分位"], start=2):
            c = ws.cell(row=r, column=j, value=x[g]["mean"])
            c.number_format = "0.00%"
        c = ws.cell(row=r, column=5, value=x["low_minus_high"])
        c.number_format = "0.00%"
    r += 2
    ws.cell(row=r, column=1, value="④ 样本重叠").font = Font(name="微软雅黑", size=11, bold=True, color=RED)
    r += 1
    header_row(ws, r, ["观察期", "日度样本", "重叠倍数", "独立期间数", "非重叠低−高", "非重叠p"], None, fill=BLUE)
    NO = {x["horizon"]: x for x in ST["non_overlap"]}
    for x in ST["overlap"]:
        r += 1
        no = NO.get(x["horizon"], {})
        for j, v in enumerate([x["horizon"], x["n_obs"], x["multiplicity"], x["independent_periods"],
                               no.get("diff"), no.get("p")], start=1):
            ws.cell(row=r, column=j, value=v)
        ws.cell(row=r, column=5).number_format = "0.00%"
    r += 2
    ws.cell(row=r, column=1, value="② 交割临近").font = Font(name="微软雅黑", size=11, bold=True, color=RED)
    r += 1
    header_row(ws, r, ["距最后交易日", "样本", "1周|Δ|中位", "2周|Δ|中位", "4周|Δ|中位",
                       "3月|Δ|中位", "6月|Δ|中位"], None, fill=BLUE)
    for d in ST["delivery"]:
        r += 1
        for j, v in enumerate([d["bin"], d["n"], d.get("abs_basis_chg_median_5"),
                               d.get("abs_basis_chg_median_10"), d.get("abs_basis_chg_median_20"),
                               d.get("abs_basis_chg_median_60"), d.get("abs_basis_chg_median_120")], start=1):
            ws.cell(row=r, column=j, value=v)
        for j in range(3, 8):
            ws.cell(row=r, column=j).number_format = "0.00%"
    ws.column_dimensions["A"].width = 22
    for j in range(2, 9):
        ws.column_dimensions[get_column_letter(j)].width = 16

    # ---------------- 09 合约映射 ----------------
    ws = wb.create_sheet("09_合约映射")
    sheet_title(ws, "09 逐日合约映射与换月标记",
                "主力连续 = 当日持仓量最大且未到期合约；roll_day=1 表示当日发生了合约切换。")
    header_row(ws, 4, ["日期", "采用合约", "交割月", "持仓量", "距最后交易日", "当日换月?",
                       "次日将换月?", "主-次价差(元/吨)", "期限结构"],
               [12, 10, 10, 13, 13, 11, 12, 15, 14])
    r0 = 5
    for n, row in enumerate(ROWS):
        r = r0 + n
        ws.cell(row=r, column=1, value=row[I["date"]])
        ws.cell(row=r, column=2, value=row[I["contract"]])
        ws.cell(row=r, column=3, value=row[I["contract_month"]])
        ws.cell(row=r, column=4, value=row[I["oi"]])
        ws.cell(row=r, column=5, value=row[I["days_to_ltd"]])
        ws.cell(row=r, column=6, value=row[I["roll_day"]])
        ws.cell(row=r, column=7, value=row[I["roll_new_next"]])
        ws.cell(row=r, column=8, value=row[I["spread_next"]])
        ws.cell(row=r, column=9, value=row[I["regime"]])
    style_body(ws, r0, r0 + len(ROWS) - 1, 9, {4: "#,##0", 8: "#,##0.0"})
    ws.freeze_panes = "A5"
    # 换月明细
    r = r0 + len(ROWS) + 2
    ws.cell(row=r, column=1, value="换月明细").font = BOLD
    r += 1
    header_row(ws, r, ["日期", "新合约", "单日基差变动"], None, fill=BLUE)
    for x in ST["roll"]["rolls"]:
        r += 1
        ws.cell(row=r, column=1, value=x["date"])
        ws.cell(row=r, column=2, value=x["contract"])
        c = ws.cell(row=r, column=3, value=x.get("basis_chg_1d"))
        c.number_format = "0.00%"

    # ---------------- 10 合约日历 ----------------
    ws = wb.create_sheet("10_合约日历")
    sheet_title(ws, "10 合约日历核验",
                "规则：最后交易日 = 交割月第 10 个交易日。K 线在临近交割时常被数据源截断，属数据可得性差异。")
    header_row(ws, 4, ["合约", "交割月", "首个K线日", "末个K线日", "交割月内K线数",
                       "规则最后交易日", "核验结论", "K线总数", "含现货日数"],
               [10, 11, 13, 13, 13, 15, 22, 10, 11])
    r0 = 5
    for n, c in enumerate(D["calendar"]):
        r = r0 + n
        for j, v in enumerate([c["contract"], c["delivery_month"], c["first_day"], c["last_day"],
                               c["delivery_month_trading_days"], c["rule_last_trading_day"],
                               c["verdict"], c["n_rows"], c["n_with_spot"]], start=1):
            ws.cell(row=r, column=j, value=v)
    style_body(ws, r0, r0 + len(D["calendar"]) - 1, 9)
    ws.freeze_panes = "A5"

    # ---------------- 11 数据源 ----------------
    ws = wb.create_sheet("11_数据源")
    sheet_title(ws, "11 数据源清单", "每一条现货价格都可在 100ppi 原文页核对。")
    header_row(ws, 4, ["项目", "来源", "覆盖", "URL / 说明"], [16, 40, 34, 70])
    fm = D.get("fetch_meta", {})
    sp = fm.get("spot", {})
    fu = fm.get("futures", {})
    vr = fm.get("basis_rate_verify", {})
    rows = [
        ("现货价格", sp.get("source", "生意社 100ppi 甲醇基准价"),
         f"{sp.get('rows','')} 点 {sp.get('first','')}~{sp.get('last','')}", sp.get("caliber", "")),
        ("期货价格", fu.get("api", "新浪财经逐合约 K 线"),
         f"{D.get('contracts_count','')} 个合约", str(fu.get("fields", ""))),
        ("口径核验", vr.get("source", "100ppi 主力基差率"),
         f"{vr.get('rows','')} 点", str(vr.get("note", ""))),
        ("抓取时间", fm.get("fetched_at", ""), "", ""),
    ]
    for i, t in enumerate(rows, start=5):
        for j, v in enumerate(t, start=1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = BODY
            c.border = BOX
            c.alignment = Alignment(wrap_text=True, vertical="top")

    # ---------------- 12 结论 ----------------
    ws = wb.create_sheet("12_核心结论")
    sheet_title(ws, "12 核心结论（历史统计，非预测，不含交易建议）",
                "所有数字可在 04/05 表中复核。")
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 96
    h5 = {b["group"]: b for b in ST["bucket_info"] if b["horizon"] == 5}
    h20 = {b["group"]: b for b in ST["bucket_info"] if b["horizon"] == 20}
    d5 = next(x for x in ST["diff"] if x["horizon"] == 5)
    d20 = next(x for x in ST["diff"] if x["horizon"] == 20)
    cons = [
        ("最新状态", f"{META['current']['date']} 合约 {META['current']['contract']}，基差 "
                 f"{META['current']['basis']:+.1f} 元/吨，基差率 {META['current']['basis_ratio']*100:+.2f}%，"
                 f"滚动分位 {META['current']['pct']*100:.1f}%（{META['current']['group']}）。"),
        ("1周 分组均值", f"低分位 {h5['低分位']['basis_ret_mean']*100:+.2f}%｜中间 {h5['中间分位']['basis_ret_mean']*100:+.2f}%"
                    f"｜高分位 {h5['高分位']['basis_ret_mean']*100:+.2f}%"),
        ("4周 分组均值", f"低分位 {h20['低分位']['basis_ret_mean']*100:+.2f}%｜中间 {h20['中间分位']['basis_ret_mean']*100:+.2f}%"
                    f"｜高分位 {h20['高分位']['basis_ret_mean']*100:+.2f}%"),
        ("1周 低−高", f"{d5['low_minus_high']*100:+.2f}%，95%区间 [{d5['ci_lo']*100:+.2f}%, {d5['ci_hi']*100:+.2f}%]，"
                  f"块自助 p={d5['boot_p']:.4f}"),
        ("4周 低−高", f"{d20['low_minus_high']*100:+.2f}%，95%区间 [{d20['ci_lo']*100:+.2f}%, {d20['ci_hi']*100:+.2f}%]，"
                  f"块自助 p={d20['boot_p']:.4f}"),
        ("价格风险分解（4周）", f"现货端贡献 {d20['spot_low_minus_high']*100:+.2f}%（p={d20['spot_boot_p']:.4f}）；"
                         f"期货端仅 {d20['fut_low_minus_high']*100:+.2f}%（p={d20['fut_boot_p']:.4f}）"
                         f" → 基差回归主要发生在现货端。"),
        ("非重叠复核（4周）", "、".join(
            f"{x['horizon']}日 {x['diff']*100:+.2f}%" for x in ST["non_overlap"]
            if x["diff"] is not None and x["horizon"] <= 20)),
        ("口径核验", f"与 100ppi 公布主力基差率重合 {ST['verify']['n']} 日，±0.5pp 一致率 "
                 f"{ST['verify']['agree_share']*100:.1f}%，隐含水平差中位 "
                 f"{ST['verify']['level_adjust']['median_adj']:+.1f} 元/吨。"),
        ("必须同时读的保留意见", "① 现货为全国基准价，非华东实盘；② 主力连续换月日有伪跳变；"
                          "③ 样本仅约 4 年，跨年一致性弱；④ 未扣交易成本，不能据此判断可交易性。"),
    ]
    for i, (k, v) in enumerate(cons, start=4):
        c1 = ws.cell(row=i, column=1, value=k)
        c1.font = BOLD
        c1.border = BOX
        c1.alignment = Alignment(wrap_text=True, vertical="top")
        c2 = ws.cell(row=i, column=2, value=v)
        c2.font = BODY
        c2.border = BOX
        c2.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 34

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    print("[OK] %s  %.2fMB  %d sheets" % (out_path, os.path.getsize(out_path) / 1048576, len(wb.sheetnames)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="out/report_data.json")
    ap.add_argument("--out", default="out/报告.xlsx")
    a = ap.parse_args()
    build(a.data, a.out)


if __name__ == "__main__":
    main()
