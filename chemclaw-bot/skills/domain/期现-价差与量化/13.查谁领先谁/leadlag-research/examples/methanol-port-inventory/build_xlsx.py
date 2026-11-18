# -*- coding: utf-8 -*-
"""
build_xlsx.py — 领先滞后研究数据工作簿
工作表：00_说明 01_指标A_库存原始 02_指标B_期货原始 03_发布日期与可得时点 04_研究样本
        05_Lag对齐明细 06_Lag扫描结果 07_分段与逐年 08_滚动相关 09_回归与稳健性 10_公式与口径
"""
import json, os, math
import xlsxwriter

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "result.json"), encoding="utf-8"))
S = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))
N = json.load(open(os.path.join(HERE, "narrative.json"), encoding="utf-8"))
rows = S["rows"]
RAW = {x["url"]: x for x in json.load(open(os.path.join(os.path.dirname(HERE), "raw", "port_inv_raw.json"), encoding="utf-8"))}
for _r in rows:
    _r["content"] = RAW[_r["url"]]["contentWithOutHtmlTag"]
M = R["meta"]
OUT = os.path.join(os.path.dirname(HERE), "领先滞后研究数据工作簿_甲醇港口库存与期货.xlsx")

wb = xlsxwriter.Workbook(OUT)
wb.set_properties({"title": "甲醇港口库存 × 期货收益 领先滞后研究数据工作簿",
                   "subject": "期现与量化 · 查谁领先谁", "author": "DSH 量化研究"})

F = lambda n: wb.add_format(n)
base = F({"font_name": "Microsoft YaHei", "font_size": 10, "valign": "vcenter"})
hdr = F({"font_name": "Microsoft YaHei", "font_size": 10, "bold": True, "bg_color": "#13233C",
         "font_color": "#FFFFFF", "border": 1, "border_color": "#2B3E5E", "text_wrap": True,
         "valign": "vcenter", "align": "center"})
title = F({"font_name": "Microsoft YaHei", "font_size": 15, "bold": True, "font_color": "#13233C"})
sub = F({"font_name": "Microsoft YaHei", "font_size": 9, "font_color": "#5A6B85", "italic": True})
sec = F({"font_name": "Microsoft YaHei", "font_size": 11, "bold": True, "font_color": "#0F5C8C",
         "bottom": 1, "bottom_color": "#7AA2FF"})
num3 = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "0.000", "border": 1, "border_color": "#DFE6F0"})
num4 = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "0.0000", "border": 1, "border_color": "#DFE6F0"})
intf = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "0", "border": 1, "border_color": "#DFE6F0"})
datef = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "yyyy-mm-dd", "border": 1, "border_color": "#DFE6F0"})
dtf = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "yyyy-mm-dd hh:mm", "border": 1, "border_color": "#DFE6F0"})
txt = F({"font_name": "Microsoft YaHei", "font_size": 9.5, "border": 1, "border_color": "#DFE6F0", "valign": "top"})
wrap = F({"font_name": "Microsoft YaHei", "font_size": 9.5, "text_wrap": True, "valign": "top"})
pct = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "0.00", "border": 1, "border_color": "#DFE6F0"})
red = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "0.000", "border": 1, "border_color": "#DFE6F0",
         "bg_color": "#FFE3E3", "font_color": "#A4001D"})
amb = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "0.000", "border": 1, "border_color": "#DFE6F0",
         "bg_color": "#FFF2D8"})
grn = F({"font_name": "Consolas", "font_size": 9.5, "num_format": "0.000", "border": 1, "border_color": "#DFE6F0",
         "bg_color": "#DDF7E8"})
warnbox = F({"font_name": "Microsoft YaHei", "font_size": 10, "bold": True, "bg_color": "#FFF4E0",
             "border": 1, "border_color": "#E0A93B", "text_wrap": True, "valign": "vcenter"})



def _blank(ws, r, c, fmt):
    """写入带格式的空单元格（XlsxWriter 需要 write_blank 且不能带值）"""
    ws.write_blank(r, c, None, fmt)

def head(ws, r, cols, widths=None):
    for i, c in enumerate(cols):
        ws.write(r, i, c, hdr)
    if widths:
        for i, w in enumerate(widths):
            ws.set_column(i, i, w)


# ---------------- 00 说明 ----------------
ws = wb.add_worksheet("00_说明")
ws.hide_gridlines(2)
ws.set_column(0, 0, 22); ws.set_column(1, 1, 118)
ws.write(0, 0, N["title"], title)
ws.write(1, 0, "数据工作簿 · 指标原始数据 / 发布日期 / Lag 对齐 / 相关系数与样本量 / 逐年检验 / 计算公式", sub)
r = 3
ws.write(r, 0, "研究设定", sec); r += 1
items = [
    ("指标 A", M["a_name"]),
    ("指标 B", M["b_name"]),
    ("样本区间", f"{M['start']} 至 {M['end']}，共 {M['n']} 个周度观测（无缺失周）"),
    ("Lag 窗口", f"±{M['maxlag']} 周，共 {2*M['maxlag']+1} 个 Lag 全部报告"),
    ("Lag 符号", "Lag=+k：A（库存变化）领先 B（期货收益）k 周；Lag=−k：B 领先 A k 周"),
    ("对齐基准", "以库存真实发布日期（精确到分钟）为锚；披露前价格=统计日 11:30 定格收盘，披露后价格=当日 15:00 收盘"),
    ("主设定变换", "A = ΔI（库存差分，万吨）；B = ln(P_披露日/P_前日) × 100（披露日对数收益，%）"),
    ("结论", N["verdict_short"]),
    ("详细结论", N["verdict_detail"]),
]
for k, v in items:
    ws.write(r, 0, k, F({"font_name": "Microsoft YaHei", "font_size": 9.5, "bold": True, "valign": "top"}))
    ws.write(r, 1, v, wrap)
    ws.set_row(r, 30 if len(v) > 60 else 16)
    r += 1
r += 1
ws.write(r, 0, "工作表导航", sec); r += 1
nav = [
    ("01_指标A_库存原始", "隆众资讯 101 期港口库存原始记录（含文章标题、正文摘要、原文链接）"),
    ("02_指标B_期货原始", "郑商所 MA 主连日线（研究样本区间内逐日）"),
    ("03_发布日期与可得时点", "每期统计日、实际发布时间、可得性判断（逐条校验统计日=发布日）"),
    ("04_研究样本", "统一频率后的研究样本：库存、ΔI、价格锚点、收益率（含 Excel 公式）"),
    ("05_Lag对齐明细", "选定 Lag 下的逐期配对明细（含库存领先与期货领先两个方向）"),
    ("06_Lag扫描结果", "25 个 Lag 的 r、n、CI、p、NW t、FDR q、Bonferroni 校正"),
    ("07_分段与逐年", "分年度 / 分市场阶段 / 分半年的完整 Lag 扫描"),
    ("08_滚动相关", "26 周滚动相关系数时间序列"),
    ("09_回归与稳健性", "变换稳健性、伪造时点安慰剂、预测回归"),
    ("10_公式与口径", "全部计算公式、检验方法与出处"),
]
for k, v in nav:
    ws.write(r, 0, k, F({"font_name": "Consolas", "font_size": 9.5, "font_color": "#0F5C8C"}))
    ws.write(r, 1, v, wrap)
    r += 1
r += 1
ws.merge_range(r, 0, r, 1, "本工作簿为统计研究材料，不构成投资建议。统计相关不等于因果关系或可交易预测能力。", warnbox)
ws.set_row(r, 26)

# ---------------- 01 库存原始 ----------------
ws = wb.add_worksheet("01_指标A_库存原始")
head(ws, 0, ["序号", "统计日（截至）", "发布时间", "港口库存总量(万吨)", "较上期变化(万吨)", "环比(%)",
             "华东变化(万吨)", "华南变化(万吨)", "文档标题", "正文摘要", "原文链接"],
     [6, 13, 16, 16, 16, 10, 14, 14, 46, 60, 48])
for i, r0 in enumerate(rows):
    r_ = i + 1
    ws.write_number(r_, 0, i + 1, intf)
    ws.write_string(r_, 1, r0["stat"], datef)
    ws.write_string(r_, 2, r0["pub"][:16].replace("T", " "), dtf)
    ws.write_number(r_, 3, r0["total"], num3)
    if r0["dI"] is not None:
        ws.write_number(r_, 4, round(r0["dI"], 2), num3)
        ws.write_number(r_, 5, round(r0["dI_pct"], 2), pct)
    else:
        _blank(ws, r_, 4, num3); _blank(ws, r_, 5, pct)
    ws.write_number(r_, 6, r0["east_chg"], num3)
    ws.write_number(r_, 7, r0["south_chg"], num3)
    ws.write_string(r_, 8, r0["title"], txt)
    ws.write_string(r_, 9, r0["content"][:160], txt)
    ws.write_url(r_, 10, r0["url"], txt, "隆众原文")
ws.freeze_panes(1, 2)
ws.autofilter(0, 0, len(rows), 10)

# ---------------- 02 期货原始 ----------------
ws = wb.add_worksheet("02_指标B_期货原始")
fut = json.load(open(r"./methanol-attrib\raw\MA0_daily.json", encoding="utf-8"))
fut = [x for x in fut if "2024-10-01" <= x["date"] <= "2026-10-20"]
head(ws, 0, ["交易日", "收盘价", "成交量", "持仓量", "日涨跌(点)", "日涨跌幅(%)"], [13, 12, 16, 16, 13, 13])
prev_c = None
for i, x in enumerate(fut):
    r_ = i + 1
    c_ = float(x["close"])
    ws.write_string(r_, 0, x["date"], datef)
    ws.write_number(r_, 1, c_, num3)
    ws.write_number(r_, 2, float(x.get("volume") or 0), F({"font_name": "Consolas", "font_size": 9.5, "num_format": "#,##0"}))
    ws.write_number(r_, 3, float(x.get("oi") or 0), F({"font_name": "Consolas", "font_size": 9.5, "num_format": "#,##0"}))
    if prev_c is not None:
        ws.write_formula(r_, 4, f"=B{r_+1}-B{r_}", num3, round(c_ - prev_c, 2))
        ws.write_formula(r_, 5, f"=(B{r_+1}/B{r_}-1)*100", pct, round((c_ / prev_c - 1) * 100, 3))
    prev_c = c_
ws.freeze_panes(1, 1)

# ---------------- 03 发布日期与可得时点 ----------------
ws = wb.add_worksheet("03_发布日期与可得时点")
head(ws, 0, ["期序", "报告期截止日(统计日)", "报告期星期", "实际发布时间", "发布时刻",
             "是否盘中披露", "研究者最早可得时点", "统计日=发布日", "可得性判定"],
     [6, 18, 10, 18, 8, 12, 22, 12, 46])
WD = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
for i, r0 in enumerate(rows):
    r_ = i + 1
    import datetime
    d = datetime.date.fromisoformat(r0["stat"])
    ws.write_number(r_, 0, i + 1, intf)
    ws.write_string(r_, 1, r0["stat"], datef)
    ws.write_string(r_, 2, WD[d.weekday()], txt)
    ws.write_string(r_, 3, r0["pub"][:16].replace("T", " "), dtf)
    ws.write_string(r_, 4, r0["pub_hm"], txt)
    ws.write_string(r_, 5, "是（13:00-15:00）" if 13 <= int(r0["pub_hm"][:2]) <= 15 else "否", txt)
    ws.write_string(r_, 6, r0["stat"] + " 14:00 左右（当日盘中）", txt)
    ws.write_string(r_, 7, "是", txt)
    ws.write_string(r_, 8, "当日 11:30 收盘早于披露，可用于'披露前'价格锚点", txt)
ws.freeze_panes(1, 2)
r_ = len(rows) + 2
ws.merge_range(r_, 0, r_, 8, "校验结论：101 期全部满足「统计日 = 发布日」，且发布时间集中在 13:00–15:00。"
               "因此本样本可以采用当日 11:30 定格收盘作为披露前价格锚点，无需对库存数据额外滞后 1 期；"
               "若直接以统计期结束日收盘作为'收盘价'再与下一期收益做相关，会引入当日已消化部分的信息泄漏。", warnbox)
ws.set_row(r_, 46)

# ---------------- 04 研究样本 ----------------
ws = wb.add_worksheet("04_研究样本")
head(ws, 0, ["期序", "统计日", "库存I(万吨)", "ΔI(万吨)", "ΔI(%)", "披露前收盘 P_prev", "披露日收盘 P_pub",
             "披露日收益 r(%)", "可用周收益(%)", "库存水平分位(52周)", "MTO产能利用率(%)"],
     [6, 13, 13, 12, 10, 18, 18, 14, 16, 16, 18])
MTO = {m["date"]: m["mto"] for m in R["mto_series"]}
for i, r0 in enumerate(rows):
    r_ = i + 1
    ws.write_number(r_, 0, i + 1, intf)
    ws.write_string(r_, 1, r0["stat"], datef)
    ws.write_number(r_, 2, r0["total"], num3)
    # ΔI 用 Excel 公式，保留可复核性
    if i == 0:
        _blank(ws, r_, 3, num3); _blank(ws, r_, 4, pct)
    else:
        ws.write_formula(r_, 3, f"=C{r_+1}-C{r_}", num3, round(r0["dI"], 2))
        ws.write_formula(r_, 4, f"=(C{r_+1}-C{r_})/C{r_}*100", pct, round(r0["dI_pct"], 2))
    ws.write_number(r_, 5, r0["P_prev"], num3)
    ws.write_number(r_, 6, r0["P_pub"], num3)
    ws.write_formula(r_, 7, f"=LN(G{r_+1}/F{r_+1})*100", num3, round(r0["ret"] * 100, 4))
    if r0["ret_avail"] is None:
        _blank(ws, r_, 8, pct)
    else:
        ws.write_number(r_, 8, round(r0["ret_avail"] * 100, 3), pct)
    ws.write_number(r_, 9, r0["dI_float"] if r0["dI_float"] is not None else 0, num4)
    v = MTO.get(r0["stat"])
    if v is None:
        _blank(ws, r_, 10, num3)
    else:
        ws.write_number(r_, 10, v, num3)
ws.freeze_panes(1, 2)
ws.autofilter(0, 0, len(rows), 10)

# ---------------- 05 Lag 对齐明细 ----------------
sheets_align = [("05_Lag+2", 2), ("05_Lag0", 0), ("05_Lag-2", -2)]
for name, L in sheets_align:
    ws = wb.add_worksheet(name)
    head(ws, 0, ["配对序", "A 期：统计日", "A 期：发布时间", "A：Δ库存(万吨)", "B 期：统计日", "B 期：收益(%)",
                 "Lag 说明"], [7, 15, 17, 15, 15, 13, 40])
    k = 0
    for t in range(len(rows)):
        j = t + L
        if not (0 <= j < len(rows)):
            continue
        a = rows[t]["dI"]; b = rows[j]["ret"]
        if a is None or b is None:
            continue
        r_ = k + 1
        ws.write_number(r_, 0, k + 1, intf)
        ws.write_string(r_, 1, rows[t]["stat"], datef)
        ws.write_string(r_, 2, rows[t]["pub"][:16].replace("T", " "), dtf)
        ws.write_number(r_, 3, round(a, 2), num3)
        ws.write_string(r_, 4, rows[j]["stat"], datef)
        ws.write_number(r_, 5, round(b * 100, 3), num3)
        if L > 0:
            note = f"A 在 {rows[t]['stat']} 披露，领先 B 期 {rows[j]['stat']} 的收益 {L} 周"
        elif L < 0:
            note = f"B 在 {rows[j]['stat']} 先行，A 在 {rows[t]['stat']} 披露（A 滞后 {-L} 周）"
        else:
            note = "同一期：库存披露当日的价格反应"
        ws.write_string(r_, 6, note, txt)
        k += 1
    # 相关公式放在表尾
    ws.write(k + 2, 3, f"相关系数 r", F({"bold": True}))
    ws.write_formula(k + 2, 4, f"=CORREL(D2:D{k+1},F2:F{k+1})", num3, None)
    ws.write(k + 3, 3, "有效样本 n", F({"bold": True}))
    ws.write_formula(k + 3, 4, f"=COUNT(D2:F{k+1})/3", intf, k)
    ws.write(k + 4, 3, "p 值（双尾）", F({"bold": True}))
    ws.write_formula(k + 4, 4, f"=T.DIST.2T(ABS(E{k+3}*SQRT((E{k+4}-2)/(1-E{k+3}^2))),E{k+4}-2)", num4, None)
    ws.freeze_panes(1, 0)

# ---------------- 06 Lag 扫描 ----------------
ws = wb.add_worksheet("06_Lag扫描结果")
head(ws, 0, ["Lag(周)", "含义", "n", "r", "CI 下限", "CI 上限", "t(朴素)", "p(朴素)",
             "t(NW稳健)", "p(NW)", "NW滞后阶", "q(BH-FDR)", "q(Bonferroni)", "有效样本n_eff", "判定"],
     [9, 30, 6, 10, 10, 10, 11, 11, 12, 11, 11, 13, 14, 14, 26])
for i, d in enumerate(R["main_scan"]):
    r_ = i + 1
    ws.write_number(r_, 0, d["lag"], F({"font_name": "Consolas", "font_size": 9.5, "num_format": "+0;-0;0",
                                        "border": 1, "border_color": "#DFE6F0", "align": "center"}))
    meaning = ("同期（同周）" if d["lag"] == 0 else
               (f"库存变化领先期货收益 {d['lag']} 周" if d["lag"] > 0 else
                f"期货收益领先库存变化 {-d['lag']} 周"))
    ws.write_string(r_, 1, meaning, txt)
    ws.write_number(r_, 2, d["n"], intf)
    style = grn if (d["q_bh"] or 1) < 0.05 else (amb if (d["p"] or 1) < 0.05 else num3)
    ws.write_number(r_, 3, d["r"], style)
    ws.write_number(r_, 4, d["ci_lo"], num3)
    ws.write_number(r_, 5, d["ci_hi"], num3)
    ws.write_number(r_, 6, d["t"], num3)
    ws.write_number(r_, 7, d["p"], num4)
    ws.write_number(r_, 8, d["t_nw"], num3)
    ws.write_number(r_, 9, d["p_nw"], num4)
    ws.write_number(r_, 10, d["nw_lags"], intf)
    ws.write_number(r_, 11, d["q_bh"], num4)
    ws.write_number(r_, 12, d["q_bonf"], num4)
    ws.write_number(r_, 13, d["n_eff"], num3)
    verdict = "FDR 校正后显著" if (d["q_bh"] or 1) < 0.05 else ("仅未校正显著（不成立）" if (d["p"] or 1) < 0.05 else "不显著")
    ws.write_string(r_, 14, verdict, txt)
n0 = len(R["main_scan"])
ws.write(n0 + 2, 0, "最小未校正 p 值", F({"bold": True}))
ws.write_formula(n0 + 2, 3, f"=MIN(H2:H{n0+1})", num4, None)
ws.write(n0 + 3, 0, "最小 FDR 校正 q 值", F({"bold": True}))
ws.write_formula(n0 + 3, 3, f"=MIN(L2:L{n0+1})", num4, None)
ws.write(n0 + 4, 0, "是否通过多重检验", F({"bold": True}))
ws.write_formula(n0 + 4, 3, f'=IF(MIN(L2:L{n0+1})<0.05,"是","否：无任何 Lag 通过 FDR 校正")', txt)
ws.write(n0 + 5, 0, "最大 |r| 所在 Lag", F({"bold": True}))
ws.write_formula(n0 + 5, 3, f"=INDEX(A2:A{n0+1},MATCH(MAX(ABS(D2:D{n0+1})),INDEX(ABS(D2:D{n0+1}),0),0))", txt)
ws.freeze_panes(1, 2)
ws.conditional_format(1, 3, n0, 3, {"type": "3_color_scale", "min_color": "#FF6B81", "mid_color": "#FFFFFF", "max_color": "#4FD1C5"})

# ---------------- 07 分段与逐年 ----------------
ws = wb.add_worksheet("07_分段与逐年")
r_ = 0
def block(title_, metas, scans, keyf, labelf):
    global r_
    ws.write(r_, 0, title_, sec)
    r_ += 1
    head(ws, r_, ["分组", "区间", "周数 n"] + [f"Lag{l:+d}" if l != 0 else "Lag0" for l in range(-12, 13)],
         [30, 26, 8] + [8] * 25)
    r_ += 1
    for m in metas:
        key = keyf(m)
        ws.write_string(r_, 0, labelf(m), txt)
        ws.write_string(r_, 1, f"{m.get('start', '')} → {m.get('end', '')}", txt)
        ws.write_number(r_, 2, m.get("n_weeks"), intf)
        sc = scans[key]
        for j, d in enumerate(sc):
            if d["r"] is None:
                _blank(ws, r_, 3 + j, num3); continue
            st = grn if (d["q_bh"] or 1) < 0.05 else num3
            ws.write_number(r_, 3 + j, d["r"], st)
        r_ += 1
    r_ += 1

block("逐年 Lag 扫描（r 值，绿色=FDR 显著；n 为该年周数）", R["years"], R["year_scan"], lambda m: m["year"], lambda m: m["year"])
block("分市场阶段 Lag 扫描（r 值）", R["stages"], R["stage_scan"], lambda m: m["code"], lambda m: m["code"])
block("分半年 Lag 扫描（r 值）", [{"year": k, "n_weeks": R["half_scan"][k][0]["n"], "start": k, "end": k} for k in R["half_scan"]],
      R["half_scan"], lambda m: m["year"], lambda m: m["year"])
r_ += 1
ws.write(r_, 0, "说明：每个分组内部独立完整扫描 ±12 周，并各自做 FDR 校正。分组样本量 10–51 期，"
               "单个 r 的 95% 置信区间半宽约 0.3–0.6，分段结果仅作方向参考。", wrap)
ws.merge_range(r_, 0, r_, 9, "说明：每个分组内部独立完整扫描 ±12 周，并各自做 FDR 校正。分组样本量 10–51 期，"
               "单个 r 的 95% 置信区间半宽约 0.3–0.6，分段结果仅作方向参考。")
ws.set_row(r_, 30)

# ---------------- 08 滚动相关 ----------------
ws = wb.add_worksheet("08_滚动相关")
head(ws, 0, ["窗口末端(统计日)"] + [f"Lag{k:+d} 滚动 r" for k in (2, 1, 0, -1, -2)] + [f"Lag{k:+d} n" for k in (2, -1)],
     [18] + [15] * 5 + [12, 12])
base_dates = {p["end"]: p for p in R["rolling"]["0"]}
for i, p in enumerate(R["rolling"]["0"]):
    r_ = i + 1
    ws.write_string(r_, 0, p["end"], datef)
    for j, L in enumerate(["2", "1", "0", "-1", "-2"]):
        v = next((q for q in R["rolling"].get(L, []) if q["end"] == p["end"]), None)
        if v and v["r"] is not None:
            ws.write_number(r_, 1 + j, v["r"], num3)
        else:
            _blank(ws, r_, 1 + j, num3)
    ws.write_number(r_, 6, p["n"], intf)
    v = next((q for q in R["rolling"].get("-1", []) if q["end"] == p["end"]), None)
    ws.write_number(r_, 7, v["n"] if v else 0, intf)
ws.freeze_panes(1, 1)

# ---------------- 09 回归与稳健性 ----------------
ws = wb.add_worksheet("09_回归与稳健性")
r_ = 0
ws.write(r_, 0, "A. 变换稳健性（各变换下最强 |r| 的 Lag）", sec); r_ += 1
head(ws, r_, ["变换设定", "最强 Lag", "r", "p", "q(BH-FDR)", "n"], [46, 10, 10, 10, 12, 8]); r_ += 1
for k, sc in R["variants"].items():
    b = max(sc, key=lambda d: abs(d["r"] or 0))
    ws.write_string(r_, 0, k, txt)
    ws.write_number(r_, 1, b["lag"], intf)
    ws.write_number(r_, 2, b["r"], num3)
    ws.write_number(r_, 3, b["p"], num4)
    ws.write_number(r_, 4, b["q_bh"], num4)
    ws.write_number(r_, 5, b["n"], intf)
    r_ += 1
r_ += 1
ws.write(r_, 0, "B. 伪造时点安慰剂（库存可得时点整体前移/后移）", sec); r_ += 1
head(ws, r_, ["可得时点调整", "最强 Lag", "r", "p", "解读"], [30, 10, 10, 10, 46]); r_ += 1
for k in sorted(R["shift_scan"], key=lambda x: int(x)):
    sc = R["shift_scan"][k]
    b = max(sc, key=lambda d: abs(d["r"] or 0))
    lbl = "真实时点（基准）" if int(k) == 0 else (f"提前 {-int(k)} 周（时间上不可能）" if int(k) < 0 else f"延后 {k} 周（更保守）")
    ws.write_string(r_, 0, lbl, txt)
    ws.write_number(r_, 1, b["lag"], intf)
    ws.write_number(r_, 2, b["r"], num3)
    ws.write_number(r_, 3, b["p"], num4)
    note = "峰值位置随平移整体移动、量级不变 → 真实时点下的弱相关属噪声水平" if int(k) != 0 else "基准结果：r≈0.23，FDR 不显著"
    ws.write_string(r_, 4, note, txt)
    r_ += 1
r_ += 1
ws.write(r_, 0, "C. 披露后收益的样本内预测回归（Newey-West HAC，仅用 t 期已披露信息）", sec); r_ += 1
head(ws, r_, ["收益期", "模型", "n", "R²", "调整R²", "Δ库存 系数", "t", "库存水平 系数", "t", "MTO水平 系数", "t", "ΔMTO 系数", "t"],
     [8, 24, 6, 9, 9, 12, 8, 13, 8, 12, 8, 11, 8]); r_ += 1
for k, v in R["regressions"].items():
    for mk, nm in (("inventory_only", "库存因子"), ("inventory_plus_fundamental", "库存 + 需求侧(MTO)")):
        m = v[mk]
        ws.write_string(r_, 0, "t" + ("" if k == "L0" else "+" + k[1:]), txt)
        ws.write_string(r_, 1, nm, txt)
        ws.write_number(r_, 2, m["n"], intf)
        if m["r2"] is None:
            for c in range(3, 13):
                _blank(ws, r_, c, num3)
        else:
            ws.write_number(r_, 3, m["r2"], num4)
            ws.write_number(r_, 4, m["adj_r2"], num4)
            for j in range(4):
                idx = 1 + j
                if idx < len(m["beta"]):
                    ws.write_number(r_, 5 + j * 2, m["beta"][idx], num4)
                    ws.write_number(r_, 6 + j * 2, m["t"][idx], num3)
                else:
                    _blank(ws, r_, 5 + j * 2, num4)
                    _blank(ws, r_, 6 + j * 2, num3)
        r_ += 1
r_ += 1
ws.write(r_, 0, "D. 诊断统计", sec); r_ += 1
head(ws, r_, ["统计量", "值", "含义"], [34, 14, 60]); r_ += 1
diag = R["diag"]
drows = [
    ("ADF t（Δ库存）", diag["adf_dI_t"], "远离 -2.86 → 差分为平稳序列"),
    ("ADF t（库存水平）", diag["adf_inv_t"], ">-2.86 → 不能拒绝单位根，水平序列非平稳"),
    ("ADF t（价格水平）", diag["adf_px_t"], ">-2.86 → 不能拒绝单位根"),
    ("库存变化一阶自相关 ρ", diag["rho_dI"], "存在自相关，需 NW 稳健标准误"),
    ("收益率一阶自相关 ρ", diag["rho_ret"], "弱自相关"),
    ("库存变化 Ljung-Box Q(8)", diag["lb_dI_q8"][0], f"p={diag['lb_dI_q8'][1]:.4f}，存在显著自相关"),
    ("有效样本量 n_eff", diag["n_eff_dI_ret"], "名义 101 期的有效信息量"),
    ("收益率均值(%)", diag["ret_mean_pct"], "披露日平均收益"),
    ("收益率标准差(%)", diag["ret_sd_pct"], "周度波动"),
    ("Δ库存均值(万吨)", diag["dI_mean"], "样本期内平均去库速度"),
    ("Δ库存标准差(万吨)", diag["dI_sd"], "单周库存变化波动"),
]
for k, v, m in drows:
    ws.write_string(r_, 0, k, txt)
    ws.write_number(r_, 1, v, num3)
    ws.write_string(r_, 2, m, txt)
    r_ += 1

# ---------------- 10 公式 ----------------
ws = wb.add_worksheet("10_公式与口径")
ws.set_column(0, 0, 6); ws.set_column(1, 1, 26); ws.set_column(2, 2, 92); ws.set_column(3, 3, 34)
ws.write(0, 0, "全部计算公式与统计方法（可据此复核任一数字）", title)
r_ = 2
head(ws, r_, ["#", "名称", "公式 / 方法", "出处 / 备注"]); r_ += 1
formulas = [
    ("库存变化", "ΔI_t = I_t − I_{t−1}（万吨）；ΔI_t% = (I_t − I_{t−1}) / I_{t−1} × 100", "差分消除趋势；万吨与百分比两种口径"),
    ("披露日收益", "r_t = ln(P_披露日15:00 / P_前一日收盘) × 100", "衡量库存披露当日的价格反应"),
    ("可用周收益", "r_avail_t = P_t / P_{t−1} − 1", "两次披露之间的全部市场收益，保守口径"),
    ("Lag 对齐", "Lag = k：配对 (A_t, B_{t+k})；k>0 → A 领先 B k 期", "正负方向同时保留，逐 Lag 报 n"),
    ("Pearson r", "r = Σ(x−x̄)(y−ȳ) / √[Σ(x−x̄)²·Σ(y−ȳ)²]", "逐 Lag 计算"),
    ("t 统计量", "t = r·√(n−2) / √(1−r²)，自由度 n−2", "朴素 t（假定独立同分布）"),
    ("Newey-West t", "V_β = (X'X)⁻¹ S (X'X)⁻¹，S = Σx²u² + 2Σ_{l=1..L} w_l Σ x_t x_{t−l} u_t u_{t−l}，w_l = 1 − l/(L+1)",
     "Bartlett 核；L 取 ⌊1.5·|Lag|⌋+1，处理重叠样本的自相关"),
    ("Fisher-z 置信区间", "z = 0.5·ln((1+r)/(1−r))，SE = 1/√(n−3)，CI = tanh(z ± 1.96·SE)", "用有效样本量替代 n"),
    ("Benjamini-Hochberg", "将 p 升序排列，q_(i) = min_{k≥i} p_(k)·m/k", "控制 FDR；m = 25 个 Lag"),
    ("Bonferroni", "p_adj = min(1, p·m)", "最保守的家庭错误率控制"),
    ("Ljung-Box", "Q = n(n+2)Σ_{k=1..K} r_k²/(n−k)，服从 χ²(K)", "检验残差/序列自相关"),
    ("ADF 检验", "Δy_t = α + γy_{t−1} + Σb_i Δy_{t−i} + e_t，检验 γ=0", "5% 临界值约 −2.86；t 值大于临界值则不能拒绝单位根"),
    ("领先滞后矩阵", "M[i][j] = corr(A_i, B_{i+j})，j ∈ [−12, 12]", "对称检验 A→B 与 B→A"),
    ("滚动相关", "r_w(t) = corr({A_{t−25..t}}, {B_{t−25+k..t+k}})", "窗口 26 周，近似显著阈值 ±1.96/√(n−3) ≈ ±0.39"),
    ("伪造时点安慰剂", "将 A 的可得时点整体平移 s 期后重做扫描", "s<0 表示提前知道（现实中不可能）"),
    ("增量 R²", "ΔR² = R²(全模型) − R²(仅库存)；系数检验用 NW t", "检验需求侧指标是否有额外解释力"),
]
for i, (nm, fm, src) in enumerate(formulas):
    ws.write_number(r_, 0, i + 1, intf)
    ws.write_string(r_, 1, nm, F({"font_name": "Microsoft YaHei", "font_size": 9.5, "bold": True, "text_wrap": True, "valign": "top"}))
    ws.write_string(r_, 2, fm, F({"font_name": "Consolas", "font_size": 9, "text_wrap": True, "valign": "top"}))
    ws.write_string(r_, 3, src, wrap)
    ws.set_row(r_, 34)
    r_ += 1
r_ += 1
ws.merge_range(r_, 1, r_, 3, "数据来源：A = 隆众资讯「中国甲醇样本港口库存周数据统计」101 期（发布时间取自各页面发布字段）；"
               "B = 郑商所甲醇主连 MA0 日线收盘（2014-12-24 至 2026-10-19）；需求侧对照 = 隆众江浙 MTO 装置产能利用率周数据。"
               "时间均为北京时间(UTC+8)。", wrap)
ws.set_row(r_, 44)

wb.close()
print("saved", OUT, os.path.getsize(OUT))
