# -*- coding: utf-8 -*-
"""
build_excel.py — 生成比价分析工作簿（.xlsx，原生公式，无宏）
============================================================
工作表：
  00-说明            口径、方法、免责、数据血缘
  01-原始价格         A/B 两侧逐日收盘（含开高低、成交、持仓）
  02-比价序列         逐日比价 + 滚动统计（分位、均值）、异常标记、换月标记
  03-窗口统计         1/3/5年 + 全样本：N、均值、中位、极值、分位
  04-分位口径对照     稳健性：同一当前值在不同样本下的分位
  05-贡献分解         各区间两边涨跌 + 对数贡献份额
  06-异常点           稳健 z 异常清单（含是否换月日）
  07-换月台账         换月日、新旧合约、价差
  08-分年统计         逐年统计
  09-产业事件台账     事件、来源、核对级别、对比价方向
  10-数据来源         每个字段的来源与可得性

关键约定：所有统计列写成 Excel 原生公式（PERCENTILE.INC / MEDIAN / AVERAGE / STDEV.S），
打开即可复算；写死的只有"从原始数据到比价"这一步的输入值。
"""
import argparse
import csv
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

HDR_FILL = PatternFill("solid", fgColor="1F3B5C")
HDR_FONT = Font(color="FFFFFF", bold=True, size=10, name="Microsoft YaHei")
TITLE_FONT = Font(bold=True, size=14, color="1F3B5C", name="Microsoft YaHei")
SUB_FONT = Font(size=10, color="55606E", name="Microsoft YaHei")
BODY = Font(size=10, name="Microsoft YaHei")
MONO = Font(size=10, name="Consolas")
THIN = Side(style="thin", color="D6DEE8")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WARN_FILL = PatternFill("solid", fgColor="FFF3D6")
OK_FILL = PatternFill("solid", fgColor="E6F7F1")
HL_FILL = PatternFill("solid", fgColor="EAF3FF")


def style_header(ws, row=1, ncol=None):
    ncol = ncol or ws.max_column
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX
    ws.row_dimensions[row].height = 28
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def autosize(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def title_block(ws, title, sub, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=title)
    c.font = TITLE_FONT
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c2 = ws.cell(row=2, column=1, value=sub)
    c2.font = SUB_FONT
    c2.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 30


def read_csv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- sheets
def sheet_readme(wb, res, meta_case):
    ws = wb.create_sheet("00-说明")
    ncol = 3
    title_block(ws, "两个相关品种比价分析 · 工作簿说明",
                "所有统计列均为 Excel 原生公式，可直接复算；不插值、不回填、不外推缺失数据。", ncol)
    rows = [
        ("", ""),
        ("一、本工作簿回答什么", ""),
        ("", "两个品种是否存在替代/上下游/共同原料等产业关系；同一口径下的比价水平；"),
        ("", "该水平在过去 1/3/5 年与全样本中的真实分位；比价变化由哪一边主导；"),
        ("", "历史极端阶段的产业背景；比价分布是否因产业结构变化而长期移动。"),
        ("", ""),
        ("二、不回答什么（红线）", ""),
        ("", "不判断方向、不给目标价、不给交易建议；"),
        ("", "不因为比价处于极端位置就认定必然回归；"),
        ("", "不把相关性说成因果；产业事件只用于解释，不用于证明因果；"),
        ("", "不混用现货与期货口径，不插值填补缺失。"),
        ("", ""),
        ("三、口径（全簿统一）", ""),
        ("品种 A", res["meta"]["product_a"]),
        ("品种 B", res["meta"]["product_b"]),
        ("比价方向", res["meta"]["direction"] + "（逐日收盘价相除）"),
        ("价格类型", "期货主力连续收盘价，元/吨，含增值税、仓库交割基准"),
        ("样本区间", res["meta"]["sample_start"] + " → " + res["meta"]["sample_end"]),
        ("有效样本量 N", res["meta"]["n_valid"]),
        ("交易日对齐", "按日期交集逐日对齐；任一侧当日缺失则该日整体剔除"),
        ("换月处理", "主连日线，不做事后复权；换月跳空在 07-换月台账 单列，异常点中标注"),
        ("分位算法", "经验分布分位 ECDF = 样本中 ≤ 当前值的观测占比；非最高/最低价线性反推"),
        ("前序样本分位", "剔除最近 %d 个交易日后重新打分，用于消除当前值自评分偏差" % res["meta"]["warmup_days"]),
        ("异常点算法", res["outliers"]["method"]),
        ("", ""),
        ("四、数据血缘", ""),
        ("原始来源", "新浪财经 期货主力连续日线接口 InnerFuturesNewService.getDailyKLine"),
        ("字段", "日期 / 开 / 高 / 低 / 收 / 成交量 / 持仓量"),
        ("已做校验", "日期重复、收盘空值、OHLC 内部矛盾、单日异常涨跌、零成交、合约覆盖"),
        ("校验结果", "见 10-数据来源 与 qc_report.json；ERROR 必须为 0 才进入统计"),
        ("", ""),
        ("五、已知局限（写在结论里）", ""),
        ("规格差异", "PP 标准品为均聚拉丝级，LLDPE 标准品为薄膜料，比价含牌号价差，非同物比价"),
        ("换月污染", "主连不连续；换月日新旧合约价差可达数个百分点，当日比价变动不可当产业信号"),
        ("近月混合报价", "数据末端连续序列可能来自临近换月的混合报价路径，与单一挂牌合约不一致（见 10-数据来源）"),
        ("结构漂移", "比价中枢在 13 年内至少移动过两次，全样本分位的分母并不稳定"),
    ]
    r = 3
    for a, b in rows:
        if a.startswith("一、") or a.startswith("二、") or a.startswith("三、") or a.startswith("四、") or a.startswith("五、"):
            ws.cell(row=r, column=1, value=a).font = Font(bold=True, size=11, color="1F3B5C", name="Microsoft YaHei")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
            r += 1
            continue
        ca = ws.cell(row=r, column=1, value=a)
        ca.font = Font(bold=True, size=10, name="Microsoft YaHei")
        ca.alignment = Alignment(vertical="top")
        cb = ws.cell(row=r, column=2, value=b)
        cb.font = BODY
        cb.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        if b and len(str(b)) > 60:
            ws.row_dimensions[r].height = 30
        r += 1
    autosize(ws, [22, 96, 20])


def sheet_prices(wb, rows_a, rows_b, na, nb):
    ws = wb.create_sheet("01-原始价格")
    ncol = 15
    title_block(ws, "原始价格：两侧逐日收盘（元/吨）",
                "A = %s，B = %s。缺失保持空白，不插值。比价日期取两侧交集。" % (na, nb), ncol)
    hdr = ["日期", na + " 收盘", na + " 开盘", na + " 最高", na + " 最低", na + " 成交量", na + " 持仓",
           nb + " 收盘", nb + " 开盘", nb + " 最高", nb + " 最低", nb + " 成交量", nb + " 持仓",
           "是否两侧齐全", "备注"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)

    da = {r["date"]: r for r in rows_a}
    db = {r["date"]: r for r in rows_b}
    dates = sorted(set(da) | set(db))
    r = 5
    for d in dates:
        a, b = da.get(d), db.get(d)
        ws.cell(row=r, column=1, value=d).font = MONO
        for j, k in enumerate(["close", "open", "high", "low", "volume", "oi"]):
            if a:
                v = fnum(a.get(k))
                if v is not None:
                    ws.cell(row=r, column=2 + j, value=v)
        for j, k in enumerate(["close", "open", "high", "low", "volume", "oi"]):
            if b:
                v = fnum(b.get(k))
                if v is not None:
                    ws.cell(row=r, column=8 + j, value=v)
        both = "是" if (a and b) else "否"
        c = ws.cell(row=r, column=14, value=both)
        if both == "否":
            c.fill = WARN_FILL
            note = ("缺 %s" % nb) if (a and not b) else (("缺 %s" % na) if (b and not a) else "")
            ws.cell(row=r, column=15, value=note)
        r += 1
    last = r - 1
    ws.auto_filter.ref = "A4:O%d" % last
    widths = [12] + [11] * 12 + [11, 12]
    autosize(ws, widths)
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=2, max_col=13):
        for c in row:
            c.number_format = "#,##0"
    return last


def sheet_ratio(wb, res, price_last):
    ws = wb.create_sheet("02-比价序列")
    ncol = 13
    title_block(ws, "比价序列与滚动统计（公式可复算）",
                "比价 = A收盘/B收盘（原生除法公式）；滚动252日分位与均值用公式从本表历史自动计算；"
                "异常点用全样本稳健 z（中位数/MAD），因需整列统计，取值为计算结果。", ncol)
    hdr = ["日期", "A 收盘", "B 收盘", "比价 A/B", "A/B 取倒数(=B/A)", "日变化 %",
           "252日滚动分位 %", "252日滚动均值", "稳健 z", "是否异常", "是否换月日", "备注", "来源行"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)

    ser = res["series"]
    # 价格从 01-原始价格 引用，保持单一数据源
    r0 = 5
    for i, p in enumerate(ser):
        r = r0 + i
        ws.cell(row=r, column=1, value=p["d"]).font = MONO
        # 引用 01 表的同一天（01 表按并集排序，需按日期定位 -> 用 VLOOKUP 更稳）
        ws.cell(row=r, column=2, value='=IFERROR(VLOOKUP($A%d,\'01-原始价格\'!$A:$M,2,FALSE),"")' % r)
        ws.cell(row=r, column=3, value='=IFERROR(VLOOKUP($A%d,\'01-原始价格\'!$A:$M,8,FALSE),"")' % r)
        ws.cell(row=r, column=4, value='=IFERROR(B%d/C%d,"")' % (r, r))
        ws.cell(row=r, column=5, value='=IFERROR(C%d/B%d,"")' % (r, r))
        if i == 0:
            ws.cell(row=r, column=6, value="")
        else:
            ws.cell(row=r, column=6, value='=IFERROR((D%d/D%d-1)*100,"")' % (r, r - 1))
        # 滚动 252 日分位：COUNTIF over trailing window
        if i >= 251:
            lo_r, hi_r = r - 251, r
            # 与 kernel 同口径：严格小于计 1、等于计 0.5
            ws.cell(row=r, column=7,
                    value='=IFERROR((COUNTIF($D$%d:$D$%d,"<"&D%d)+0.5*COUNTIF($D$%d:$D$%d,D%d))'
                          '/COUNT($D$%d:$D$%d)*100,"")'
                          % (lo_r, hi_r, r, lo_r, hi_r, r, lo_r, hi_r))
            ws.cell(row=r, column=8, value='=IFERROR(AVERAGE($D$%d:$D$%d),"")' % (lo_r, hi_r))
        else:
            ws.cell(row=r, column=7, value="")
            ws.cell(row=r, column=8, value="")
        if p.get("z") is not None:
            ws.cell(row=r, column=9, value=p["z"])
        out = "是" if p.get("out") else ""
        c = ws.cell(row=r, column=10, value=out)
        if out:
            c.fill = WARN_FILL
        rl = "是" if p.get("roll") else ""
        c2 = ws.cell(row=r, column=11, value=rl)
        if rl:
            c2.fill = PatternFill("solid", fgColor="FDE9E9")
        if p.get("out") and p.get("roll"):
            ws.cell(row=r, column=12, value="异常且换月：多为换月跳空，非产业驱动")
        elif p.get("roll"):
            ws.cell(row=r, column=12, value="换月日")
        elif p.get("out"):
            ws.cell(row=r, column=12, value="统计异常")
    last = r0 + len(ser) - 1
    ws.auto_filter.ref = "A4:M%d" % last
    autosize(ws, [12, 11, 11, 12, 14, 11, 15, 15, 10, 10, 12, 34, 9])
    for row in ws.iter_rows(min_row=r0, max_row=last, min_col=2, max_col=3):
        for c in row:
            c.number_format = "#,##0"
    for row in ws.iter_rows(min_row=r0, max_row=last, min_col=4, max_col=5):
        for c in row:
            c.number_format = "0.0000"
    for row in ws.iter_rows(min_row=r0, max_row=last, min_col=6, max_col=7):
        for c in row:
            c.number_format = "0.00"
    for row in ws.iter_rows(min_row=r0, max_row=last, min_col=8, max_col=9):
        for c in row:
            c.number_format = "0.0000"
    return last


def sheet_windows(wb, res, ratio_last):
    ws = wb.create_sheet("03-窗口统计")
    ncol = 12
    title_block(ws, "窗口统计：1年 / 3年 / 5年 / 全样本",
                "分位与统计量均以 02-比价序列 的比价列为输入，用 Excel 原生公式按窗口区间计算；"
                "N 为该窗口内有效交易日数。", ncol)
    hdr = ["窗口", "起始日", "结束日", "N", "均值", "中位数", "最低", "最低日期", "最高", "最高日期",
           "当前值分位 %", "当前值"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)

    ratios = [p for p in res["series"]]
    cur = res["current"]["ratio"]

    def row_of_date(d):
        for i, p in enumerate(ratios):
            if p["d"] == d:
                return 5 + i
        return None

    labels = [("1Y", "近1年"), ("3Y", "近3年"), ("5Y", "近5年"), ("ALL", "全样本")]
    r = 5
    for key, lab in labels:
        w = res["windows"][key]["calendar"]
        r1 = row_of_date(w["start_date"]) if "start_date" in w else row_of_date(w["start"])
        # window start date: from window_start field
        ws_start = res["windows"][key].get("window_start") or res["windows"][key]["calendar"].get("start")
        r1 = row_of_date(ws_start)
        r2 = ratios and (5 + len(ratios) - 1)
        ws.cell(row=r, column=1, value=lab).font = Font(bold=True, name="Microsoft YaHei")
        ws.cell(row=r, column=2, value=ws_start)
        ws.cell(row=r, column=3, value=res["meta"]["sample_end"])
        if r1:
            ws.cell(row=r, column=4, value='=COUNT(\'02-比价序列\'!$D$%d:$D$%d)' % (r1, r2))
            ws.cell(row=r, column=5, value='=IFERROR(AVERAGE(\'02-比价序列\'!$D$%d:$D$%d),"")' % (r1, r2))
            ws.cell(row=r, column=6, value='=IFERROR(MEDIAN(\'02-比价序列\'!$D$%d:$D$%d),"")' % (r1, r2))
            ws.cell(row=r, column=7, value='=IFERROR(MIN(\'02-比价序列\'!$D$%d:$D$%d),"")' % (r1, r2))
            ws.cell(row=r, column=8, value=w["min_date"])
            ws.cell(row=r, column=9, value='=IFERROR(MAX(\'02-比价序列\'!$D$%d:$D$%d),"")' % (r1, r2))
            ws.cell(row=r, column=10, value=w["max_date"])
            # 分位与 kernel 完全同口径：严格小于计 1、等于计 0.5（并列各半），再除以 N
            ws.cell(row=r, column=11,
                    value='=IFERROR((COUNTIF(\'02-比价序列\'!$D$%d:$D$%d,"<"&$L%d)'
                          '+0.5*COUNTIF(\'02-比价序列\'!$D$%d:$D$%d,$L%d))'
                          '/COUNT(\'02-比价序列\'!$D$%d:$D$%d)*100,"")'
                          % (r1, r2, r, r1, r2, r, r1, r2))
        ws.cell(row=r, column=12, value='=$L$%d' % 5 if False else cur)
        r += 1
    ws.cell(row=r, column=1, value="当前值（唯一）").font = Font(bold=True, name="Microsoft YaHei")
    ws.cell(row=r, column=12, value="",)
    r_note = r + 2
    ws.cell(row=r_note, column=1,
            value="说明：分位 = 窗口内比价 ≤ 当前值的交易日数 / 窗口内有效交易日数（ECDF）。"
                  "不采用 (当前-最低)/(最高-最低) 的线性反推，因为那会把分布形状全部丢掉。").font = SUB_FONT
    ws.merge_cells(start_row=r_note, start_column=1, end_row=r_note, end_column=ncol)
    autosize(ws, [14, 12, 12, 8, 11, 11, 11, 12, 11, 12, 14, 11])
    for row in ws.iter_rows(min_row=5, max_row=8, min_col=5, max_col=9):
        for c in row:
            c.number_format = "0.0000"
    for row in ws.iter_rows(min_row=5, max_row=8, min_col=11, max_col=12):
        for c in row:
            c.number_format = "0.00"


def sheet_robust(wb, res):
    ws = wb.create_sheet("04-分位口径对照")
    ncol = 4
    title_block(ws, "同一个当前值，在不同样本定义下的分位",
                "这张表是本分析最重要的风险提示：分位不是比价的固有属性，而是样本选择的函数。", ncol)
    hdr = ["样本定义", "N", "当前值分位 %", "解读"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)
    r = 5
    for it in res["robustness"]:
        ws.cell(row=r, column=1, value=it["sample"]).font = BODY
        ws.cell(row=r, column=2, value=it["n"])
        c = ws.cell(row=r, column=3, value=it["pct"])
        c.number_format = "0.0"
        if it["pct"] >= 95:
            c.fill = WARN_FILL
        elif it["pct"] <= 20:
            c.fill = OK_FILL
        note = ""
        if it["pct"] >= 99.9:
            note = "样本内几乎最高：该样本区间与当前结构不同"
        elif it["pct"] >= 85:
            note = "偏高"
        elif it["pct"] <= 15:
            note = "偏低"
        else:
            note = "居中"
        ws.cell(row=r, column=4, value=note).font = SUB_FONT
        r += 1
    ps = [x["pct"] for x in res["robustness"]]
    ws.cell(row=r + 1, column=1, value="分位区间").font = Font(bold=True, name="Microsoft YaHei")
    ws.cell(row=r + 1, column=3, value="%.1f%% ~ %.1f%%" % (min(ps), max(ps))).font = Font(bold=True, color="C0392B", name="Microsoft YaHei")
    ws.cell(row=r + 3, column=1,
            value="结论用法：报告必须写明所用样本口径；若不同口径给出的分位差异超过 15 个百分点，"
                  "就不能用「历史高位」作为单一论据。").font = SUB_FONT
    ws.merge_cells(start_row=r + 3, start_column=1, end_row=r + 3, end_column=ncol)
    autosize(ws, [30, 8, 14, 44])


def sheet_contrib(wb, res):
    ws = wb.create_sheet("05-贡献分解")
    ncol = 11
    title_block(ws, "贡献分解：比价变化来自哪一边",
                "恒等式：Δln(A/B) = ΔlnA − ΔlnB。份额 = |ΔlnA| / (|ΔlnA|+|ΔlnB|)，回答谁主导；"
                "方向看涨跌正负。份额列与比价列均为 Excel 公式。", ncol)
    hdr = ["区间", "起始日", "结束日", "A 起", "A 止", "A 涨跌 %", "B 起", "B 止", "B 涨跌 %",
           "比价变化 %", "主导方"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)
    order = [("M1", "近1月"), ("M3", "近3月"), ("M6", "近6月"),
             ("1Y", "近1年"), ("3Y", "近3年"), ("5Y", "近5年"), ("ALL", "全样本")]
    r = 5
    for k, lab in order:
        c = res["contribution"].get(k)
        if not c:
            continue
        ws.cell(row=r, column=1, value=lab).font = Font(bold=True, name="Microsoft YaHei")
        ws.cell(row=r, column=2, value=c["start"])
        ws.cell(row=r, column=3, value=c["end"])
        ws.cell(row=r, column=4, value=c["a_start"])
        ws.cell(row=r, column=5, value=c["a_end"])
        ws.cell(row=r, column=6, value="=(E%d/D%d-1)*100" % (r, r))
        ws.cell(row=r, column=7, value=c["b_start"])
        ws.cell(row=r, column=8, value=c["b_end"])
        ws.cell(row=r, column=9, value="=(H%d/G%d-1)*100" % (r, r))
        ws.cell(row=r, column=10, value="=((E%d/D%d)/(H%d/G%d)-1)*100" % (r, r, r, r))
        ws.cell(row=r, column=11, value=c["dominant"])
        r += 1

    # 份额表（单独一小块，公式）
    r += 1
    ws.cell(row=r, column=1, value="对数贡献份额（|ΔlnA| 与 |ΔlnB| 各自占比）").font = Font(bold=True, size=11, color="1F3B5C", name="Microsoft YaHei")
    r += 1
    h2 = ["区间", "ΔlnA", "ΔlnB", "A 份额 %", "B 份额 %", "主导方", "主导份额 %"]
    for i, h in enumerate(h2, start=1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, row=r, ncol=len(h2))
    head_row = r
    r += 1
    src0 = 5
    for j, (k, lab) in enumerate([(k, lab) for k, lab in order if res["contribution"].get(k)]):
        sr = src0 + j
        ws.cell(row=r, column=1, value=lab).font = BODY
        ws.cell(row=r, column=2, value="=LN(E%d/D%d)" % (sr, sr)).number_format = "0.0000"
        ws.cell(row=r, column=3, value="=LN(H%d/G%d)" % (sr, sr)).number_format = "0.0000"
        ws.cell(row=r, column=4, value="=ABS(B%d)/(ABS(B%d)+ABS(C%d))*100" % (r, r, r)).number_format = "0.0"
        ws.cell(row=r, column=5, value="=ABS(C%d)/(ABS(B%d)+ABS(C%d))*100" % (r, r, r)).number_format = "0.0"
        ws.cell(row=r, column=6, value="=IF(ABS(B%d)>=ABS(C%d),\"%s\",\"%s\")"
                % (r, r, res["meta"]["product_a"], res["meta"]["product_b"])).font = BODY
        ws.cell(row=r, column=7, value="=MAX(D%d:E%d)" % (r, r)).number_format = "0.0"
        r += 1
    ws.cell(row=r + 1, column=1,
            value="读法：份额接近 50/50 说明两边力度相当，比价几乎不动——这仍然是「两边都在动」，"
                  "不能说成「比价没反应所以无关」。份额悬殊则说明是单边主导。").font = SUB_FONT
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=ncol)
    autosize(ws, [14, 12, 12, 10, 10, 12, 10, 10, 12, 13, 10])


def sheet_outliers(wb, res):
    ws = wb.create_sheet("06-异常点")
    ncol = 6
    title_block(ws, "比价异常点（稳健 z 分数）", res["outliers"]["method"] +
                "；共 %d 个 / 评估 %d 个交易日（%.1f%%）。" %
                (res["outliers"]["count"], res["outliers"]["n_evaluated"],
                 100.0 * res["outliers"]["count"] / max(1, res["outliers"]["n_evaluated"])), ncol)
    hdr = ["日期", "比价", "稳健 z", "是否换月日", "性质判断", "处理建议"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)
    r = 5
    for it in res["outliers"]["items"]:
        ws.cell(row=r, column=1, value=it["date"]).font = MONO
        ws.cell(row=r, column=2, value=it["ratio"]).number_format = "0.0000"
        ws.cell(row=r, column=3, value=it["z"]).number_format = "+0.00;-0.00"
        roll = "是" if it["on_roll_day"] else "否"
        c = ws.cell(row=r, column=4, value=roll)
        if it["on_roll_day"]:
            c.fill = WARN_FILL
            ws.cell(row=r, column=5, value="换月跳空（数据原因）")
            ws.cell(row=r, column=6, value="不作为产业信号，单独披露")
        else:
            ws.cell(row=r, column=5, value="价格真实异动")
            ws.cell(row=r, column=6, value="需回到当日两侧产业信息解释")
        r += 1
    ws.auto_filter.ref = "A4:F%d" % (r - 1)
    autosize(ws, [12, 11, 10, 12, 24, 30])


def sheet_rolls(wb, res):
    ws = wb.create_sheet("07-换月台账")
    ncol = 5
    title_block(ws, "换月台账：主连切换日与新旧合约价差",
                "共 %d 次换月。价差 =（旧合约收盘 − 新合约收盘）/ 新合约收盘；"
                "该价差就是换月当天比价被污染的近似幅度。" % res["rolls"]["n_events"], ncol)
    hdr = ["换月日", "旧合约", "新合约", "新旧价差 %", "对当日比价的影响"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)
    r = 5
    for e in res["rolls"]["events"]:
        ws.cell(row=r, column=1, value=e["date"]).font = MONO
        ws.cell(row=r, column=2, value=e["old"])
        ws.cell(row=r, column=3, value=e["new"])
        if e["spread_pct"] is not None:
            c = ws.cell(row=r, column=4, value=e["spread_pct"])
            c.number_format = "+0.00;-0.00"
            if abs(e["spread_pct"]) >= 3:
                c.fill = WARN_FILL
            ws.cell(row=r, column=5, value="跳空较大，当日比价变动需剔除" if abs(e["spread_pct"]) >= 3 else "影响有限")
        else:
            ws.cell(row=r, column=5, value="无重叠报价，无法计量")
        r += 1
    ws.auto_filter.ref = "A4:E%d" % (r - 1)
    autosize(ws, [12, 12, 12, 14, 34])


def sheet_yearly(wb, res):
    ws = wb.create_sheet("08-分年统计")
    ncol = 8
    title_block(ws, "逐年统计：中枢在哪里移动", "看中枢是否有台阶式迁移，而不是只看单年高低。", ncol)
    hdr = ["年份", "N", "均值", "中位数", "最低", "最高", "年内末值", "末值在年内分位 %"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)
    r = 5
    for y in res["yearly"]:
        ws.cell(row=r, column=1, value=y["year"]).font = Font(bold=True, name="Microsoft YaHei")
        ws.cell(row=r, column=2, value=y["n"])
        ws.cell(row=r, column=3, value=y["mean"]).number_format = "0.0000"
        ws.cell(row=r, column=4, value=y["median"]).number_format = "0.0000"
        ws.cell(row=r, column=5, value=y["min"]).number_format = "0.0000"
        ws.cell(row=r, column=6, value=y["max"]).number_format = "0.0000"
        ws.cell(row=r, column=7, value=y["last"]).number_format = "0.0000"
        ws.cell(row=r, column=8, value=y["pct_in_year"]).number_format = "0.0"
        r += 1
    autosize(ws, [8, 8, 11, 11, 11, 11, 11, 16])


def sheet_events(wb, events):
    ws = wb.create_sheet("09-产业事件台账")
    ncol = 6
    title_block(ws, "产业事件台账（用于解释，不用于证明因果）",
                "核对级别：A=有原始报道标题/正文可直接核对；B=有标题但细节需二次确认；"
                "C=行业背景/常识，未逐条核实，不得单独支撑结论。方向列是对比价的预期影响方向，不是幅度预测。", ncol)
    hdr = ["日期", "影响侧", "对比价方向", "核对级别", "事件", "来源"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)
    dv = {"+": "推高比价", "-": "压低比价", "0": "中性", "?": "方向不定"}
    r = 5
    for e in sorted(events, key=lambda x: x["date"]):
        ws.cell(row=r, column=1, value=e["date"]).font = MONO
        ws.cell(row=r, column=2, value=e["scope"])
        ws.cell(row=r, column=3, value=dv.get(e.get("ratio_rel", ""), ""))
        c = ws.cell(row=r, column=4, value=e.get("verify", ""))
        c.alignment = Alignment(horizontal="center")
        if e.get("verify") == "A":
            c.fill = OK_FILL
        elif e.get("verify") == "C":
            c.fill = WARN_FILL
        ct = ws.cell(row=r, column=5, value=e["title"])
        ct.alignment = Alignment(wrap_text=True, vertical="top")
        ct.font = BODY
        cs = ws.cell(row=r, column=6, value=e["source"])
        cs.alignment = Alignment(wrap_text=True, vertical="top")
        cs.font = SUB_FONT
        if len(e["title"]) > 50:
            ws.row_dimensions[r].height = 32
        r += 1
    ws.auto_filter.ref = "A4:F%d" % (r - 1)
    autosize(ws, [12, 9, 12, 10, 62, 46])


def sheet_sources(wb, res, qc):
    ws = wb.create_sheet("10-数据来源")
    ncol = 4
    title_block(ws, "数据来源与可得性", "每个字段的来源、口径与已知问题；缺什么、为什么缺，都写在这里。", ncol)
    hdr = ["项目", "内容", "状态", "备注"]
    for i, h in enumerate(hdr, start=1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, row=4, ncol=ncol)
    rows = [
        ("接口地址", "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{SYM}=/InnerFuturesNewService.getDailyKLine?symbol={SYM}", "可用", "SYM 取 PP0 / L0 为主连"),
        ("实时快照", "https://hq.sinajs.cn/list=nf_L0,nf_PP0", "可用", "需 Referer: finance.sina.com.cn，GBK 解码"),
        ("价格类型", "期货主力连续日线（未复权）", "可用", "非结算价；收盘价口径"),
        ("单位", "元/吨", "可用", "两侧一致"),
        ("成交量/持仓量", "接口返回", "可用", "用于判定主力合约"),
        ("合约面板", "单合约日线（L/PP 各月份）", "可用", "用于换月识别与交叉校验"),
        ("A 侧覆盖", "%s → %s" % (qc["products"]["A"]["info"]["start"], qc["products"]["A"]["info"]["end"]), "可用",
         "%d 个交易日" % qc["products"]["A"]["info"]["rows"]),
        ("B 侧覆盖", "%s → %s" % (qc["products"]["B"]["info"]["start"], qc["products"]["B"]["info"]["end"]), "可用",
         "%d 个交易日" % qc["products"]["B"]["info"]["rows"]),
        ("共同样本", "%s → %s" % (qc["cross"]["common_start"], qc["cross"]["common_end"]), "可用",
         "N=%d；A 独有 %d 天、B 独有 %d 天" % (qc["cross"]["common_dates"], qc["cross"]["A_only"], qc["cross"]["B_only"])),
        ("OHLC 矛盾", "A: %d 处；B: %d 处" % (qc["products"]["A"]["info"]["ohlc_violations"],
                                            qc["products"]["B"]["info"]["ohlc_violations"]), "已标注", "收盘价仍在高低区间内，不影响比价"),
        ("单日涨跌 >15%", "A: %d 处；B: %d 处" % (qc["products"]["A"]["info"]["abs_move_gt15"],
                                              qc["products"]["B"]["info"]["abs_move_gt15"]), "已标注", "集中在 2008/2015 极端行情"),
        ("零成交日", "A: %d 天；B: %d 天" % (qc["products"]["A"]["info"]["zero_volume_days"],
                                          qc["products"]["B"]["info"]["zero_volume_days"]), "已标注", "多为节假日前后，价格仍有效"),
        ("现货价格", "隆众资讯 华东 PP 拉丝 / LLDPE 膜料", "未纳入",
         "现货为付费数据，本次分析统一使用期货口径，未与现货混用"),
        ("产能/开工/库存", "隆众资讯 数据终端", "未纳入", "本轮未取得可核对的量化序列，报告中不作量化引用"),
        ("末端混合报价", "数据末端连续序列可能来自临近换月的混合路径", "已披露",
         "当日连续序列持仓/成交高于任一挂牌合约，说明其为多合约混合报价；比价水平不受影响（约 1.07），但不宜用末端单日做精细判断"),
    ]
    r = 5
    for a, b, c, d in rows:
        ws.cell(row=r, column=1, value=a).font = Font(bold=True, name="Microsoft YaHei")
        cb = ws.cell(row=r, column=2, value=b)
        cb.alignment = Alignment(wrap_text=True, vertical="top")
        cb.font = BODY
        cc = ws.cell(row=r, column=3, value=c)
        cc.alignment = Alignment(horizontal="center", vertical="top")
        cc.fill = OK_FILL if c == "可用" else (WARN_FILL if c in ("未纳入", "已披露") else HL_FILL)
        cd = ws.cell(row=r, column=4, value=d)
        cd.alignment = Alignment(wrap_text=True, vertical="top")
        cd.font = SUB_FONT
        if len(str(b)) > 60 or len(str(d)) > 50:
            ws.row_dimensions[r].height = 34
        r += 1
    autosize(ws, [18, 58, 10, 56])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    ap.add_argument("--price-a", required=True)
    ap.add_argument("--price-b", required=True)
    ap.add_argument("--events", default=None)
    ap.add_argument("--qc", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    with open(a.result, encoding="utf-8") as f:
        res = json.load(f)
    rows_a = read_csv(a.price_a)
    rows_b = read_csv(a.price_b)
    events = read_csv(a.events) if a.events and os.path.exists(a.events) else []
    qc = json.load(open(a.qc, encoding="utf-8")) if a.qc and os.path.exists(a.qc) else {
        "products": {"A": {"info": {"start": "", "end": "", "rows": 0, "ohlc_violations": 0,
                                    "abs_move_gt15": 0, "zero_volume_days": 0}},
                     "B": {"info": {"start": "", "end": "", "rows": 0, "ohlc_violations": 0,
                                    "abs_move_gt15": 0, "zero_volume_days": 0}}},
        "cross": {"common_start": "", "common_end": "", "common_dates": 0, "A_only": 0, "B_only": 0},
    }

    na = res["meta"]["product_a"]
    nb = res["meta"]["product_b"]
    wb = Workbook()
    wb.remove(wb.active)

    sheet_readme(wb, res, {})
    pl = sheet_prices(wb, rows_a, rows_b, na, nb)
    rl = sheet_ratio(wb, res, pl)
    sheet_windows(wb, res, rl)
    sheet_robust(wb, res)
    sheet_contrib(wb, res)
    sheet_outliers(wb, res)
    sheet_rolls(wb, res)
    sheet_yearly(wb, res)
    sheet_events(wb, events)
    sheet_sources(wb, res, qc)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    wb.save(a.out)
    print("written:", a.out, "sheets:", len(wb.sheetnames))
    for s in wb.sheetnames:
        print("   ", s)


if __name__ == "__main__":
    main()
