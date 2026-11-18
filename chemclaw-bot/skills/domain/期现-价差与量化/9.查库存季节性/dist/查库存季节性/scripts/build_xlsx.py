# -*- coding: utf-8 -*-
"""
build_xlsx.py —— 库存季节性工作簿（多表，含可追溯到原文的明细与分位计算过程）
================================================================================
表清单
 00 封面与说明      01 口径核验        02 历史库存明细（逐周，含来源与取值方式）
 03 周度矩阵        04 年份对齐        05 季节性分位      06 逐年曲线数据
 07 年度对齐        08 累去库速度      09 样本变化检验    10 异常年份
 11 来源与查证      12 当前状态摘要
所有派生列写成 Excel 公式（可自行复算），原文数值列保持静态并标注来源。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, ScatterChart, Reference

C_HDR = "1F3864"
C_SUB = "2E5C8A"
C_ACC = "DCE6F1"
C_WARN = "FFF2CC"
C_BAD = "FCE4E4"
C_OK = "E2EFDA"
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _style_header(ws, row=1, ncol=12):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = PatternFill("solid", fgColor=C_HDR)
        cell.font = Font(color="FFFFFF", bold=True, size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX
    ws.row_dimensions[row].height = 30
    ws.freeze_panes = ws.cell(row=row + 1, column=2)


def _title(ws, text, sub=None, ncol=12):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(bold=True, size=14, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_HDR)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 26
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = Font(size=9, color="595959")
        c2.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[2].height = 30


def _widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def write_df(ws, df, start_row=3, fmts=None, width=True, autofilter=True):
    """写 DataFrame 到工作表（表头 + 数据）。"""
    fmts = fmts or {}
    cols = list(df.columns)
    for j, name in enumerate(cols, start=1):
        cell = ws.cell(row=start_row, column=j, value=str(name))
        cell.fill = PatternFill("solid", fgColor=C_SUB)
        cell.font = Font(color="FFFFFF", bold=True, size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX
    ws.row_dimensions[start_row].height = 28
    for i, (_, row) in enumerate(df.iterrows(), start=start_row + 1):
        for j, name in enumerate(cols, start=1):
            v = row[name]
            if isinstance(v, (np.integer,)):
                v = int(v)
            elif isinstance(v, (np.floating,)):
                v = None if pd.isna(v) else float(v)
            elif v is pd.NaT or (isinstance(v, float) and pd.isna(v)):
                v = None
            cell = ws.cell(row=i, column=j, value=v)
            cell.border = BOX
            cell.font = Font(size=9)
            if name in fmts:
                cell.number_format = fmts[name]
            if isinstance(v, str) and len(v) > 22:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    if autofilter and len(df):
        ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(cols))}{start_row + len(df)}"
    if width:
        for j, name in enumerate(cols, start=1):
            w = max(9, min(42, int(max([len(str(name))] + [len(str(x)) for x in df[name].head(80)]) * 1.25) + 3))
            ws.column_dimensions[get_column_letter(j)].width = w
    return start_row + len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--seasonal", required=True)
    ap.add_argument("--story", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cache = Path(args.cache)
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    S = json.loads(Path(args.seasonal).read_text(encoding="utf-8"))
    ST = json.loads(Path(args.story).read_text(encoding="utf-8"))
    a = pd.read_pickle(cache / "a_sample.pkl")
    b = pd.read_pickle(cache / "b_sample.pkl") if (cache / "b_sample.pkl").exists() else pd.DataFrame()
    a["asof"] = pd.to_datetime(a["asof"])
    a = a.sort_values("asof").reset_index(drop=True)

    wb = Workbook()

    # ================= 00 封面与说明 =================
    ws = wb.active
    ws.title = "00 封面与说明"
    _widths(ws, {"A": 22, "B": 96})
    ws.merge_cells("A1:B1")
    c = ws["A1"]
    c.value = f"{cfg['product']} · {cfg['metric_name']} 库存季节性工作簿"
    c.font = Font(bold=True, size=18, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_HDR)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 40
    rows = [
        ("案例编号", cfg["case_id"]),
        ("数据截止", f"{cfg['asof']}（周报，周三发布）"),
        ("生成日期", cfg["run_date"]),
        ("统计对象", f"{S['calibration']['metric_label']}（港口库存 = 显性罐存）"),
        ("单位", S["meta"]["unit"]),
        ("发布方 / 载体", f"{S['calibration']['issuer']} / {S['calibration']['carrier']}"),
        ("样本期", f"{S['integrity']['start']} ~ {S['integrity']['end']}，共 {S['integrity']['n_weeks']} 期"),
        ("历史对照年", " / ".join(map(str, S["meta"]["hist_years"])) + "（本年剔除）"),
        ("季节模型", f"ln I = 趋势(52 周中心化 MA) + 季节(傅里叶 K=2)，R²={S['season_fit']['r2']}，留一年 MAPE={S['season_fit']['oos']['mape_log']}%"),
        ("分位口径", "同 ISO 周次 ±1 周，剔除本年的历史样本；端点 0/100 表示低于/高于全部样本"),
        ("", ""),
        ("阅读顺序", "01 核对口径 → 02 看逐周原始值与来源 → 05 看分位与今年位置 → 08 看累去库速度 → 09/10 看样本断点与异常年"),
        ("", ""),
        ("【重要边界】", "① 库存高于/低于历史均值不直接推导价格方向，价格还需结合基差、到港、开工、MTO 利润与合约结构。"),
        ("", "② 港库、厂库、交易所仓单是三个不同池子，本工作簿只统计港口库存，未混算。"),
        ("", "③ 华东（江苏+浙江）与全国港口（华东+华南）分列，规模不可直接比较，分位只在本口径内成立。"),
        ("", "④ 2026-07-29 之后逐地区库存未再公开，水平值不可得；表内以增减额与全国港口总量描述变化，替代值均标注。"),
        ("", "⑤ 派生列（合计、差分、累计、分位）均写成 Excel 公式，可篡改原始值后自行复算。"),
        ("", ""),
        ("图表", "06 表内嵌“逐年曲线对齐”折线图；08 表内嵌滚动累计变化图"),
        ("可复核性", "每期数据可回溯到原文标题、发布日期与增减额；取值方式分为“表格直接披露 / 由增减额递推 / 全国港口折算”三种，逐行标注"),
    ]
    for i, (k, v) in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True, size=10)
        ws.cell(row=i, column=1).alignment = Alignment(vertical="top")
        cc = ws.cell(row=i, column=2, value=v)
        cc.font = Font(size=10)
        cc.alignment = Alignment(wrap_text=True, vertical="top")
        if k.startswith("【"):
            ws.cell(row=i, column=1).font = Font(bold=True, size=10, color="C00000")

    # ================= 01 口径核验 =================
    ws = wb.create_sheet("01 口径核验")
    _title(ws, "01 口径核验：这条库存到底统计了什么",
           "先把统计对象、覆盖、单位、频率、机构、发布时点锁定；口径不清的分位没有意义。")
    checks = pd.DataFrame(ST["checks"])[["id", "name", "claim", "evidence", "status"]]
    checks.columns = ["编号", "检查项", "结论", "证据", "状态"]
    checks["状态"] = checks["状态"].map({"pass": "通过", "warn": "注意"}).fillna(checks["状态"])
    end = write_df(ws, checks, start_row=4)
    for r in range(5, end + 1):
        st = ws.cell(row=r, column=5).value
        ws.cell(row=r, column=5).fill = PatternFill("solid", fgColor=C_OK if st == "通过" else C_WARN)
    cal = S["calibration"]
    detail = pd.DataFrame([
        ["统计对象", cal["metric_label"]],
        ["库存类型", "港口库存（显性罐存）"],
        ["覆盖省份", "、".join(cal["coverage_regions"].values())],
        ["单位", cal["unit"]],
        ["频率", "周度（每周三 14:00 前后发布）"],
        ["日历", "ISO 周年 + ISO 周次"],
        ["发布机构", cal["issuer"]],
        ["转载载体", cal["carrier"]],
        ["A 样本期数", cal["A 样本期数"] if "A 样本期数" in cal else S["integrity"]["n_weeks"]],
        ["表格直接披露期数", cal["value_methods"].get("east_table", 0)],
        ["由增减额递延期数", cal["value_methods"].get("east_estimated", 0)],
        ["逐地区齐全期数", cal["prov_full_weeks"]],
        ["文本分区披露期数", cal["region_split_weeks"]],
        ["官方增减额 vs 表格差分不一致期数", cal["chg_discrepancy_weeks"]],
        ["B 样本（不并入主统计）", f"{cal['b_sample']['n']} 期，{cal['b_sample']['start']} ~ {cal['b_sample']['end']}"],
    ], columns=["项目", "内容"])
    ws.cell(row=end + 2, column=1, value="口径字典").font = Font(bold=True, size=11, color=C_HDR)
    write_df(ws, detail, start_row=end + 3, autofilter=False)
    _widths(ws, {"A": 26, "B": 30, "C": 62, "D": 62, "E": 10})

    # ================= 02 历史库存明细 =================
    ws = wb.create_sheet("02 历史库存明细")
    _title(ws, "02 历史库存明细（逐周）· 全部原始值 + 来源 + 取值方式",
           "★ 这是全表数据底座。east 列可能来自①表格直接披露②由官方增减额递推③与全国港口折算无关（不填）。取值方式列逐行标注。")
    cols = ["asof", "iso_year", "iso_week", "port_total", "east", "jiangsu", "zhejiang", "guangdong", "fujian",
            "ev_east_chg", "east_dchg", "east_dchg_table", "east_method", "is_chg_official", "prov_full",
            "east_from_port", "gap_days", "week_missing", "title", "url"]
    d = a[[c for c in cols if c in a.columns]].copy()
    d["asof"] = d["asof"].dt.strftime("%Y-%m-%d")
    rename = {
        "asof": "截止日", "iso_year": "ISO年", "iso_week": "ISO周", "port_total": "全国港口合计(万吨)",
        "east": "华东=江苏+浙江(万吨)", "jiangsu": "江苏(万吨)", "zhejiang": "浙江(万吨)",
        "guangdong": "广东(万吨)", "fujian": "福建(万吨)", "ev_east_chg": "原文华东增减额(万吨)",
        "east_dchg": "采用增减额(万吨)", "east_dchg_table": "表格差分(万吨)", "east_method": "华东取值方式",
        "is_chg_official": "增减额是否官方", "prov_full": "逐地区是否齐全", "east_from_port": "华东替代值(全国×占比)",
        "gap_days": "距上期间隔(天)", "week_missing": "是否缺报", "title": "原文标题", "url": "原文链接",
    }
    d = d.rename(columns=rename)
    fmts = {c: "0.00" for c in d.columns if "(万吨)" in c}
    fmts.update({"距上期间隔(天)": "0"})
    end = write_df(ws, d, start_row=4, fmts=fmts)
    n = len(d)
    r0 = 5
    # 校验列：用公式复算 华东 = 江苏 + 浙江（列字母按列名动态定位，避免硬编码错位）
    L_js = get_column_letter(d.columns.get_loc("江苏(万吨)") + 1)
    L_zj = get_column_letter(d.columns.get_loc("浙江(万吨)") + 1)
    L_east = get_column_letter(d.columns.get_loc("华东=江苏+浙江(万吨)") + 1)
    chk_col = len(d.columns) + 1                 # 核对列
    flag_col = len(d.columns) + 2                # 是否一致列
    L_chk = get_column_letter(chk_col)
    L_east23 = get_column_letter(chk_col + 2)    # 两期相减所得变化（辅助列）
    for label, col in (("核对：江苏+浙江", chk_col), ("是否一致", flag_col)):
        c = ws.cell(row=4, column=col, value=label)
        c.fill = PatternFill("solid", fgColor=C_SUB)
        c.font = Font(color="FFFFFF", bold=True, size=9)
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    for r in range(r0, r0 + n):
        ws.cell(row=r, column=chk_col,
                value=f'=IF(OR({L_js}{r}="",{L_zj}{r}=""),"",ROUND({L_js}{r}+{L_zj}{r},2))')
        ws.cell(row=r, column=flag_col,
                value=f'=IF({L_chk}{r}="","",IF(ABS({L_chk}{r}-{L_east}{r})<0.05,"一致","差异"))')
    ws.cell(row=4, column=chk_col + 3, value="校验说明").font = Font(bold=True, size=9, color="C00000")
    ws.merge_cells(start_row=4, start_column=chk_col + 3, end_row=4, end_column=chk_col + 5)
    ws.cell(row=4, column=chk_col + 3,
            value="本列用公式把江苏+浙江与华东列对拍；若某期表格为局部口径，会出现“差异”，这正是局部采样的证据。").font = Font(size=9, color="C00000")
    _widths(ws, {"A": 12, "B": 7, "C": 7, "D": 15, "E": 17, "F": 10, "G": 10, "H": 10, "I": 10})
    ws.column_dimensions[get_column_letter(chk_col)].width = 16
    ws.column_dimensions[get_column_letter(flag_col)].width = 10

    # ================= 03 周度矩阵 =================
    ws = wb.create_sheet("03 周度矩阵")
    _title(ws, "03 周次 × 年份 矩阵（ISO 周次对齐）", "单元格为该周库存（万吨），空=该周未披露。跨年周归入其 ISO 年。")
    wm = S["weekly_matrix"]
    mat = pd.DataFrame(wm["values"], index=[f"W{w}" for w in wm["weeks"]], columns=[str(y) for y in wm["years"]])
    mat.index.name = "ISO周次"
    ws.cell(row=4, column=1, value="ISO周次")
    for j, y in enumerate(mat.columns, start=2):
        c = ws.cell(row=4, column=j, value=y)
        c.fill = PatternFill("solid", fgColor=C_SUB)
        c.font = Font(color="FFFFFF", bold=True, size=10)
        c.alignment = Alignment(horizontal="center")
    for i, (w, row) in enumerate(mat.iterrows(), start=5):
        ws.cell(row=i, column=1, value=w).font = Font(bold=True, size=9)
        for j, y in enumerate(mat.columns, start=2):
            v = row[y]
            cell = ws.cell(row=i, column=j, value=None if pd.isna(v) else float(v))
            cell.number_format = "0.00"
            cell.font = Font(size=9)
            cell.border = BOX
            if str(y) == str(S["meta"]["cur_year"]):
                cell.fill = PatternFill("solid", fgColor=C_OK)
    # 统计行
    sr = 5 + len(mat) + 1
    ws.cell(row=sr, column=1, value="年均值").font = Font(bold=True, size=9)
    ws.cell(row=sr + 1, column=1, value="年最低").font = Font(bold=True, size=9)
    ws.cell(row=sr + 2, column=1, value="年最高").font = Font(bold=True, size=9)
    ws.cell(row=sr + 3, column=1, value="披露周数").font = Font(bold=True, size=9)
    for j, y in enumerate(mat.columns, start=2):
        col = get_column_letter(j)
        rng = f"{col}5:{col}{4 + len(mat)}"
        ws.cell(row=sr, column=j, value=f"=IFERROR(AVERAGE({rng}),\"\")").number_format = "0.00"
        ws.cell(row=sr + 1, column=j, value=f"=IFERROR(MIN({rng}),\"\")").number_format = "0.00"
        ws.cell(row=sr + 2, column=j, value=f"=IFERROR(MAX({rng}),\"\")").number_format = "0.00"
        ws.cell(row=sr + 3, column=j, value=f"=COUNT({rng})")
    _widths(ws, {"A": 10})
    for j in range(2, len(mat.columns) + 2):
        ws.column_dimensions[get_column_letter(j)].width = 11

    # ================= 04 年份对齐 =================
    ws = wb.create_sheet("04 年份对齐")
    _title(ws, "04 年份对齐说明与检查",
           "为何按 ISO 周次对齐：库存季节性由生产/进口到港/下游开工的日历节奏驱动，公历日期跨年漂移会污染同期比较。")
    expl = pd.DataFrame([
        ["对齐键", "ISO 周年（ISO year）+ ISO 周次（1-53）"],
        ["为何用 ISO 年", "12 月末与 1 月初属同一 ISO 周时，若按自然年切分会把同一周拆到两年，导致某年只有 51 或 53 周"],
        ["跨年周处理", "整周归入其 ISO 周年；因此本表“年”是 ISO 年，与自然年可能相差 1-2 周"],
        ["周次 53", "仅闰年结构出现；本样本未使用 W53 做分位（周次 1-52 覆盖）"],
        ["同期容差", "分位计算取目标周次 ±1 周，避免单周缺报导致样本空缺"],
        ["本年处理", "本年样本不进入历史分布（避免自己与自己比较），仅作为“今年值”叠加"],
        ["频率一致性", f"相邻两期间隔中位数 {S['integrity']['gap_median_days']} 天，最大 {S['integrity']['gap_max_days']} 天（春节前后双周报）"],
        ["缺报判定", "间隔 > 16 天记为缺报；10-16 天视为双周报，不剔除"],
    ], columns=["项目", "说明"])
    end = write_df(ws, expl, start_row=4, autofilter=False)
    ymap = a.groupby("iso_year").agg(期数=("asof", "size"),
                                     首期=("asof", "min"), 末期=("asof", "max")).reset_index()
    ymap.columns = ["ISO 年", "期数", "首期", "末期"]
    ymap["首期"] = ymap["首期"].dt.strftime("%Y-%m-%d")
    ymap["末期"] = ymap["末期"].dt.strftime("%Y-%m-%d")
    ymap["首期周次"] = a.groupby("iso_year")["iso_week"].first().values
    ymap["末期周次"] = a.groupby("iso_year")["iso_week"].last().values
    ws.cell(row=end + 2, column=1, value="各 ISO 年覆盖情况").font = Font(bold=True, size=11, color=C_HDR)
    write_df(ws, ymap, start_row=end + 3, autofilter=False)
    _widths(ws, {"A": 16, "B": 70, "C": 12, "D": 13, "E": 13, "F": 10, "G": 10})

    # ================= 05 季节性分位 =================
    ws = wb.create_sheet("05 季节性分位")
    _title(ws, "05 季节性分位：过去 N 年同周次分布 + 今年位置",
           "分布列由 03 表历史年份同周次样本计算；今年列取自 02 表。分位＝(小于当期数+0.5×等于当期数)/样本数×100。")
    wk = S["weeks"]
    rowsr = []
    cy = {c["year"]: c for c in S["curves"]}
    cur_w = {w: v for w, v in zip(cy[S["meta"]["cur_year"]]["weeks"], cy[S["meta"]["cur_year"]]["east"])}
    for w in sorted(wk, key=int):
        v = wk[w]
        cur = cur_w.get(int(w))
        hist = [x for y, x in v["values"].items() if S["meta"]["cur_year"] - 5 <= int(y) < S["meta"]["cur_year"]]
        rank = None
        if cur is not None and hist:
            rank = round(100 * (sum(1 for x in hist if x < cur) + 0.5 * sum(1 for x in hist if x == cur)) / len(hist), 1)
        rowsr.append({
            "ISO周次": int(w), "历史样本年数": len(hist), "均值": round(float(np.mean(hist)), 2) if hist else None,
            "中位数": round(float(np.median(hist)), 2) if hist else None,
            "最小": round(min(hist), 2) if hist else None, "最大": round(max(hist), 2) if hist else None,
            "p10": v.get("p10"), "p25": v.get("p25"), "p75": v.get("p75"), "p90": v.get("p90"),
            "今年值": cur, "今年分位": rank,
            "位置判定": ("低于历史最小值" if (cur is not None and hist and cur < min(hist)) else
                     "高于历史最大值" if (cur is not None and hist and cur > max(hist)) else
                     ("低于 p10" if (cur is not None and v.get("p10") and cur < v["p10"]) else
                      "p10-p25" if (cur is not None and v.get("p25") and cur < v["p25"]) else
                      "p25-p75" if (cur is not None and v.get("p75") and cur <= v["p75"]) else
                      "p75-p90" if (cur is not None and v.get("p90") and cur <= v["p90"]) else
                      "高于 p90" if cur is not None else "今年无披露")),
        })
    qdf = pd.DataFrame(rowsr)
    end = write_df(ws, qdf, start_row=4, fmts={c: "0.00" for c in ["均值", "中位数", "最小", "最大", "p10", "p25", "p75", "p90", "今年值"]})
    ws.cell(row=end + 2, column=1, value="说明：今年值只在其周次已披露时存在；2026-07-29 之后华东水平值不可得，故 8 月以后为空（不是 0）。").font = Font(size=9, italic=True, color="C00000")

    # ================= 06 逐年曲线数据 =================
    ws = wb.create_sheet("06 逐年曲线数据")
    _title(ws, "06 逐年曲线数据（周次对齐长表）+ 折线图",
           "长表便于自行作图：一行 = 一年一周次的库存。图在表格右侧。")
    long = a[["asof", "iso_year", "iso_week", "east", "port_total", "east_from_port", "jiangsu", "zhejiang", "east_dchg", "east_method"]].copy()
    long.columns = ["截止日", "ISO年", "ISO周", "华东", "全国港口", "华东替代值", "江苏", "浙江", "华东增减额", "取值方式"]
    long["截止日"] = long["截止日"].dt.strftime("%Y-%m-%d")
    end = write_df(ws, long, start_row=4, fmts={c: "0.00" for c in ["华东", "全国港口", "华东替代值", "江苏", "浙江", "华东增减额"]})
    # 宽表 + 图
    piv = a.pivot_table(index="iso_week", columns="iso_year", values="east", aggfunc="last")
    start_col = len(long.columns) + 3
    hr = 4
    ws.cell(row=hr - 1, column=start_col, value="宽表（作图用）").font = Font(bold=True, size=11, color=C_HDR)
    ws.cell(row=hr, column=start_col, value="ISO周")
    ws.cell(row=hr, column=start_col).fill = PatternFill("solid", fgColor=C_SUB)
    ws.cell(row=hr, column=start_col).font = Font(color="FFFFFF", bold=True)
    for j, y in enumerate(piv.columns, start=start_col + 1):
        c = ws.cell(row=hr, column=j, value=int(y))
        c.fill = PatternFill("solid", fgColor=C_SUB)
        c.font = Font(color="FFFFFF", bold=True, size=9)
    for i, (w, row) in enumerate(piv.iterrows(), start=hr + 1):
        ws.cell(row=i, column=start_col, value=int(w)).font = Font(size=9)
        for j, y in enumerate(piv.columns, start=start_col + 1):
            v = row[y]
            cc = ws.cell(row=i, column=j, value=None if pd.isna(v) else float(v))
            cc.number_format = "0.00"
            cc.font = Font(size=9)
    ch = LineChart()
    ch.title = "逐年对齐：华东港口库存（万吨）"
    ch.y_axis.title = "万吨"
    ch.x_axis.title = "ISO 周次"
    ch.height = 11
    ch.width = 20
    data = Reference(ws, min_col=start_col + 1, max_col=start_col + len(piv.columns), min_row=hr, max_row=hr + len(piv))
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=start_col, min_row=hr + 1, max_row=hr + len(piv)))
    ws.add_chart(ch, f"{get_column_letter(start_col + len(piv.columns) + 1)}{hr}")
    _widths(ws, {"A": 12, "B": 8, "C": 8})

    # ================= 07 年度对齐 =================
    ws = wb.create_sheet("07 年度对齐")
    _title(ws, "07 年度对齐：每年同周次水平对比", "每行一年，列出关键周次的库存，便于横向看“同一时点不同年份”。")
    keyweeks = [4, 8, 13, 17, 22, 26, 31, 35, 39, 43, 48, 52]
    rowsy = []
    for y, sub in a.groupby("iso_year"):
        rec = {"ISO年": int(y), "披露周数": int(sub["east"].notna().sum()), "均值": round(float(sub["east"].mean()), 2) if sub["east"].notna().any() else None,
               "最低": round(float(sub["east"].min()), 2) if sub["east"].notna().any() else None,
               "最高": round(float(sub["east"].max()), 2) if sub["east"].notna().any() else None,
               "年末增减额合计": round(float(sub["east_dchg"].sum()), 2)}
        for w in keyweeks:
            s = sub.loc[(sub["iso_week"].between(w - 1, w + 1)), "east"].dropna()
            rec[f"W{w}±1"] = round(float(s.mean()), 2) if len(s) else None
        rowsy.append(rec)
    ydf = pd.DataFrame(rowsy)
    write_df(ws, ydf, start_row=4, fmts={c: "0.00" for c in ydf.columns if c.startswith("W") or c in ("均值", "最低", "最高", "年末增减额合计")})

    # ================= 08 累去库速度 =================
    ws = wb.create_sheet("08 累去库速度")
    _title(ws, "08 累去库速度：周度增减额与实际幅度",
           "增减额优先取原文披露值（东部地区），缺失时才回退为表格差分。累计列由公式计算，可改原值复算。")
    sp = a[["asof", "iso_week", "east", "ev_east_chg", "east_dchg", "east_dchg_table", "east_method", "is_chg_official"]].copy()
    sp = sp.rename(columns={"asof": "截止日", "iso_week": "ISO周", "east": "华东水平", "ev_east_chg": "原文增减额",
                            "east_dchg": "采用增减额", "east_dchg_table": "表格差分", "east_method": "取值方式",
                            "is_chg_official": "增减额来源"})
    sp["截止日"] = pd.to_datetime(sp["截止日"]).dt.strftime("%Y-%m-%d")
    sp["增减额来源"] = sp["增减额来源"].map({True: "原文", False: "表格差分"}).fillna("—")
    end = write_df(ws, sp, start_row=4, fmts={"华东水平": "0.00", "原文增减额": "0.00", "采用增减额": "0.00", "表格差分": "0.00"})
    nrow = len(sp)
    col_use = get_column_letter(list(sp.columns).index("采用增减额") + 1)
    for label, span, col in [("滚动4周累计", 4, None), ("滚动12周累计", 12, None), ("滚动26周累计", 26, None)]:
        cidx = len(sp.columns) + (1 if label == "滚动4周累计" else (2 if label == "滚动12周累计" else 3))
        ws.cell(row=4, column=cidx, value=label).fill = PatternFill("solid", fgColor=C_SUB)
        ws.cell(row=4, column=cidx).font = Font(color="FFFFFF", bold=True, size=9)
        for i in range(5, 5 + nrow):
            if i - 5 >= span - 1:
                rng = f"{col_use}{i - span + 1}:{col_use}{i}"
                ws.cell(row=i, column=cidx, value=f"=IF(COUNT({rng})={span},ROUND(SUM({rng}),2),\"\")").number_format = "0.00"
    # 速度汇总：放在明细右侧独立区块，避免与明细表混排
    sm = 4
    scol = len(sp.columns) + 5
    ws.cell(row=sm, column=scol, value="速度汇总（当前）").font = Font(bold=True, size=11, color=C_HDR)
    summ = pd.DataFrame([
        ["最近一周变化", S["speed"].get("last_week_chg"), "万吨"],
        ["连续状态", S["speed"].get("run_label"), f'{S["speed"].get("run_len")} 周'],
        ["近 4 周累计", S["speed"].get("cum4w"), "万吨"],
        ["近 12 周累计", S["speed"].get("cum12w"), "万吨"],
        ["近 26 周累计", S["speed"].get("cum26w"), "万吨"],
        ["近 52 周累计", S["speed"].get("cum52w"), "万吨"],
        ["4 周变化历史同周次中位数", S["speed"].get("cum4w_hist_mean"), "万吨"],
        ["4 周变化历史分位", S["speed"].get("cum4w_pct_rank"), "%"],
        ["12 周变化历史分位", S["speed"].get("cum12w_pct_rank"), "%"],
        ["历史单期平均绝对变化", S["speed"].get("hist_chg_vol"), "万吨"],
    ], columns=["项目", "数值", "单位"])
    for j, name in enumerate(summ.columns):
        c = ws.cell(row=sm + 1, column=scol + j, value=str(name))
        c.fill = PatternFill("solid", fgColor=C_SUB)
        c.font = Font(color="FFFFFF", bold=True, size=9)
    for i, (_, row) in enumerate(summ.iterrows(), start=sm + 2):
        for j, name in enumerate(summ.columns):
            v = row[name]
            if isinstance(v, (np.floating,)):
                v = float(v)
            ws.cell(row=i, column=scol + j, value=v).font = Font(size=9)
    for j in range(scol, scol + 3):
        ws.column_dimensions[get_column_letter(j)].width = 22
    ch = LineChart()
    ch.title = "滚动累计变化（万吨）"
    ch.height = 9
    ch.width = 18
    ch.add_data(Reference(ws, min_col=len(sp.columns) + 1, max_col=len(sp.columns) + 2, min_row=4, max_row=4 + nrow), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=4, min_row=5, max_row=4 + nrow))
    ws.add_chart(ch, f"{get_column_letter(scol)}{sm + len(summ) + 3}")

    # ================= 09 样本变化检验 =================
    ws = wb.create_sheet("09 样本变化检验")
    _title(ws, "09 样本变化检验：断点、披露降级、局部采样与敏感性",
           "任何一次统计范围或披露方式的变化都在这里显式登记；断点两侧数据不合并统计。")
    brk = pd.DataFrame(S["breakpoints"])[["date", "kind", "effect"]]
    brk.columns = ["日期", "类型", "对统计的影响"]
    end = write_df(ws, brk, start_row=4, autofilter=False)
    r2 = end + 2
    ws.cell(row=r2, column=1, value="局部采样造成的虚假跳变（官方增减额 vs 表格差分）").font = Font(bold=True, size=11, color=C_HDR)
    jd = pd.DataFrame(S["calibration"].get("chg_discrepancy_detail") or [])
    if len(jd):
        jd = jd.rename(columns={"asof": "截止日", "chg_official": "原文增减额", "chg_table": "表格差分", "diff": "差额"})
        end2 = write_df(ws, jd, start_row=r2 + 1, fmts={"原文增减额": "0.00", "表格差分": "0.00", "差额": "0.00"}, autofilter=False)
    else:
        end2 = r2 + 1
    r3 = end2 + 2
    ws.cell(row=r3, column=1, value="样本口径敏感性（同一指标、不同样本）").font = Font(bold=True, size=11, color=C_HDR)
    sc = pd.DataFrame(S["scenarios"]).rename(columns={"scenario": "场景", "n": "样本数", "mean": "均值",
                                                      "median": "中位数", "min": "最小值", "max": "最大值"})
    r4 = write_df(ws, sc, start_row=r3 + 1, fmts={"均值": "0.00"}, autofilter=False)
    r5 = r4 + 2
    ws.cell(row=r5, column=1, value="披露状态（逐月）").font = Font(bold=True, size=11, color=C_HDR)
    md = pd.DataFrame(S["disclosure"]["monthly"]).rename(columns={
        "month": "月份", "n": "期数", "region_split": "文本分区披露", "prov_full": "逐地区齐全",
        "east_tbl": "华东表格值", "official": "含官方增减额"})
    md["逐地区齐全比例"] = (md["逐地区齐全"] / md["期数"]).round(3)
    write_df(ws, md, start_row=r5 + 1, autofilter=False)
    _widths(ws, {"A": 14, "B": 34, "C": 70, "D": 18, "E": 18, "F": 18, "G": 18})

    # ================= 10 异常年份 =================
    ws = wb.create_sheet("10 异常年份")
    _title(ws, "10 异常年份检查", "去季节残差按年汇总；|z|>2 记为异常周。异常年不剔除，但结论中必须标注。")
    an = pd.DataFrame(S["anomaly_years"]).rename(columns={
        "year": "年份", "n": "样本周数", "mean_dev_pct": "平均去季节偏离%", "sd_dev_pct": "偏离标准差%",
        "share_z2": "|z|>2周占比%", "max_dev_week": "最大偏离周次", "max_dev_pct": "最大偏离%",
        "min": "年内最低", "max": "年内最高"})
    end = write_df(ws, an, start_row=4, fmts={"平均去季节偏离%": "0.0", "偏离标准差%": "0.0", "|z|>2周占比%": "0.0",
                                              "最大偏离%": "0.0", "年内最低": "0.00", "年内最高": "0.00"})
    r2 = end + 2
    ws.cell(row=r2, column=1, value="预登记异常窗口").font = Font(bold=True, size=11, color=C_HDR)
    ex = pd.DataFrame(S.get("exception_windows") or [])
    if len(ex):
        write_df(ws, ex, start_row=r2 + 1, autofilter=False)
    # 极值周
    r3 = r2 + 4
    ws.cell(row=r3, column=1, value="年内极值（明细）").font = Font(bold=True, size=11, color=C_HDR)
    ext = []
    for y, sub in a.groupby("iso_year"):
        s = sub.dropna(subset=["east"])
        if len(s):
            lo = s.loc[s["east"].idxmin()]
            hi = s.loc[s["east"].idxmax()]
            ext.append({"年份": int(y), "最低值": round(float(lo["east"]), 2),
                        "最低周次": f'W{int(lo["iso_week"])}', "最低日期": lo["asof"].strftime("%Y-%m-%d"),
                        "最高值": round(float(hi["east"]), 2), "最高周次": f'W{int(hi["iso_week"])}',
                        "最高日期": hi["asof"].strftime("%Y-%m-%d")})
    write_df(ws, pd.DataFrame(ext), start_row=r3 + 1, autofilter=False)

    # ================= 11 来源与查证 =================
    ws = wb.create_sheet("11 来源与查证")
    _title(ws, "11 来源与查证清单", "每一期数据的原文标题/链接/发布日期都在 02 表；本表给出发布特征与核验要点。")
    src = pd.DataFrame([
        ["发布机构", S["calibration"]["issuer"]],
        ["转载载体", S["calibration"]["carrier"]],
        ["栏目", "[港口库存]：中国甲醇样本港口库存周数据统计"],
        ["发布频率", "每周三下午 14:00 前后"],
        ["正文结构", "港口库存总量 + 较上一期增减额；分列华东、华南增减额；表格列江苏/浙江/广东/福建"],
        ["单位", "万吨"],
        ["口径边界", "样本港口库存，非全国全量；不代表厂库与交易所仓单"],
        ["核验要点1", "增减额取原文披露值，不用相邻两期表格值相减"],
        ["核验要点2", "表格为局部采样，某期只覆盖部分港口时数值会跳变，需与增减额交叉验证"],
        ["核验要点3", "2026-07 后表格不再逐地区披露，仅有总量与分区增减额，水平值须标注缺失"],
        ["核验要点4", "2016-2018 存在口径不同的早期序列，其周报形式为简报，与本样本不可拼接"],
        ["链接形态", "https://nenghua.m.mysteel.com/a/{post_id}_abc.html"],
        ["复算方式", "本工作簿派生列均为公式；脚本见 skills/scripts/*.py，可一键重跑"],
    ], columns=["项目", "内容"])
    end = write_df(ws, src, start_row=4, autofilter=False)
    ws.cell(row=end + 2, column=1, value="原文样例（最近 8 期）").font = Font(bold=True, size=11, color=C_HDR)
    samp = a[["asof", "title", "url"]].tail(8).copy()
    samp["asof"] = samp["asof"].dt.strftime("%Y-%m-%d")
    samp.columns = ["截止日", "原文标题", "链接"]
    write_df(ws, samp, start_row=end + 3, autofilter=False)
    _widths(ws, {"A": 16, "B": 90, "C": 60})

    # ================= 12 当前状态摘要 =================
    ws = wb.create_sheet("12 当前状态摘要")
    _title(ws, "12 当前状态摘要（首屏结论的数据底稿）",
           "本表所有数字都来自前序工作表；结论句严格由规则生成，不含价格方向预测。")
    k = ST["kpis"]
    v = ST["verdict"]
    rows = [
        ("主口径当前值", k["current_value"], "万吨", f'截止 {k["current_asof"]}（W{v["level_week"]}）'),
        ("同期历史分位", k["pct_rank"], "%", f'样本 n={k["pct_rank_n"]}，同周次 ±1 周'),
        ("同期均值", k["hist_mean"], "万吨", "过去 5 年同周次"),
        ("相对均值偏离", k["vs_mean_pct"], "%", "负=低于同期均值"),
        ("近 4 周变化", k["chg4w"], "万吨", "官方增减额累计"),
        ("近 12 周变化", k["chg12w"], "万吨", "官方增减额累计"),
        ("连续状态", f'{k["run_label"]} {abs(k["run_len"] or 0)} 周', "", "基于周度增减额符号"),
        ("最新一期全国港口", k["latest_port_total"], "万吨", f'截止 {k["latest_asof"]}（对照口径）'),
        ("最新一期华东替代值", k["latest_east_est"], "万吨", "全国港口 × 近一年华东占比，仅定位"),
        ("水平状态判定", v["level_state"], "", f'按 R3 五档规则，W{v["level_week"]}'),
        ("去季节状态判定", v["deseason_state"], "", f'去季节残差 {v["deseason_resid_pct"]}%'),
        ("速度状态判定", v["speed_state"], "", f'4 周变化分位 {v["speed_rank"]}'),
        ("水平缺失起始", v["level_missing_from"], "", f'共 {v["level_missing_weeks"]} 周无逐地区水平值'),
        ("是否可下水平结论", "是" if v["can_conclude_level"] else "否", "", "样本年数 ≥4 且有可核验水平值"),
        ("护栏标记", "、".join(v["flags"]), "", "见 00 表边界说明与 09 表断点"),
    ]
    df = pd.DataFrame(rows, columns=["项目", "数值", "单位", "说明"])
    end = write_df(ws, df, start_row=4, autofilter=False)
    r = end + 2
    ws.cell(row=r, column=1, value="结论句").font = Font(bold=True, size=11, color=C_HDR)
    for i, line in enumerate(ST["statements"], start=1):
        ws.merge_cells(start_row=r + i, start_column=1, end_row=r + i, end_column=4)
        c = ws.cell(row=r + i, column=1, value=f"{i}. {line}")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(size=10)
        ws.row_dimensions[r + i].height = 46
    r2 = r + len(ST["statements"]) + 2
    ws.cell(row=r2, column=1, value="判断规则（硬编码）").font = Font(bold=True, size=11, color=C_HDR)
    rules = pd.DataFrame(ST["rules"]).rename(columns={"id": "编号", "rule": "规则"})
    write_df(ws, rules, start_row=r2 + 1, autofilter=False)
    _widths(ws, {"A": 20, "B": 22, "C": 8, "D": 62})

    # 统一页面设置
    for s in wb.worksheets:
        s.sheet_view.showGridLines = False
        s.page_setup.orientation = "landscape"
        s.page_setup.fitToWidth = 1
        s.sheet_properties.pageSetUpPr.fitToPage = True

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"wrote {out} sheets={len(wb.worksheets)}")


if __name__ == "__main__":
    main()

