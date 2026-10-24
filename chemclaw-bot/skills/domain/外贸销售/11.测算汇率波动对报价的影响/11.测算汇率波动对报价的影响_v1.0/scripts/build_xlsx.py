# -*- coding: utf-8 -*-
"""build_xlsx.py —— 生成可运行的汇率风险测算工作簿（公式全部保留，改输入即重算）

用法:
    python scripts/build_xlsx.py --scenario <scenario.json> --fx build/fx_series.json \
        --out <xxx.xlsx>

设计要点
--------
* 每张表的计算都用 **Excel 公式**，不写死结果；只有历史汇率原始序列是静态值（必须如此）。
* 输入区统一黄底、公式区白底、结论区浅蓝底；关键输入命名便于跨表引用。
* 所有公式在 Excel / WPS / LibreOffice 中均可直接计算（不使用动态数组、不使用 LET/LAMBDA）。
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- 样式
C_INK = "1F2937"
C_MUTED = "6B7280"
C_BRAND = "0F3D7A"
C_BRAND2 = "1A6FC4"
F_TITLE = Font(name="Microsoft YaHei", size=15, bold=True, color="FFFFFF")
F_H2 = Font(name="Microsoft YaHei", size=11.5, bold=True, color=C_BRAND)
F_HDR = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
F_B = Font(name="Microsoft YaHei", size=10, bold=True, color=C_INK)
F_N = Font(name="Microsoft YaHei", size=10, color=C_INK)
F_S = Font(name="Microsoft YaHei", size=9.5, color=C_MUTED)
F_IN = Font(name="Microsoft YaHei", size=10, bold=True, color="7A3E00")
FILL_TITLE = PatternFill("solid", fgColor=C_BRAND)
FILL_H2 = PatternFill("solid", fgColor="E8F0FA")
FILL_HDR = PatternFill("solid", fgColor=C_BRAND2)
FILL_IN = PatternFill("solid", fgColor="FFF7DD")
FILL_IN_BORDER = PatternFill("solid", fgColor="FFE9B8")
FILL_CALC = PatternFill("solid", fgColor="F8FAFD")
FILL_RES = PatternFill("solid", fgColor="EAF3FF")
FILL_WARN = PatternFill("solid", fgColor="FFF4E5")
FILL_BAND = PatternFill("solid", fgColor="F3F6FB")
THIN = Side(style="thin", color="D5DCE6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
AL_C = Alignment(horizontal="center", vertical="center", wrap_text=True)
AL_L = Alignment(horizontal="left", vertical="center", wrap_text=True)
AL_R = Alignment(horizontal="right", vertical="center")

NUM = {
    "rate4": "0.0000",
    "rate6": "0.000000",
    "money": "#,##0.00",
    "money0": "#,##0",
    "pct2": "0.00%",
    "pct3": "0.000%",
    "pct1": "0.0%",
    "int": "0",
    "date": "yyyy-mm-dd",
    "text": "@",
}

# 输入单元格位置（全工作簿统一引用）
IN = {
    "dir": "Inputs!$C$6",         # "出口收汇" / "进口付汇"
    "cur": "Inputs!$C$7",         # 币种代码
    "pair": "Inputs!$C$8",        # USD/CNY 等
    "amount": "Inputs!$C$9",      # 外币金额
    "mid": "Inputs!$C$10",
    "mid_date": "Inputs!$C$11",
    "band": "Inputs!$C$12",       # 单侧 %
    "actual": "Inputs!$C$13",
    "mode": "Inputs!$C$14",       # 基准汇率口径
    "cost": "Inputs!$C$15",
    "resale": "Inputs!$C$16",
    "tpct": "Inputs!$C$17",
    "tcny": "Inputs!$C$18",
    "toll": "Inputs!$C$19",
    "trade_date": "Inputs!$C$20",
    "settle": "Inputs!$C$21",
    "contract": "Inputs!$C$22",
    "shifts": "Inputs!$C$23",      # 档位串
    # 派生
    "sell": "Inputs!$C$26",
    "buy": "Inputs!$C$27",
    "base": "Inputs!$C$30",
    "basis": "Inputs!$C$31",
    "sign": "Inputs!$C$32",       # 出口 -1 / 进口 +1
    "horizon": "Inputs!$C$33",
}

formula_errors = []


def S(ws):
    """记录本工作表的公式，便于事后校验。"""
    return ws


def put(ws, r, c, v, font=F_N, fill=None, fmt=None, align=None, border=True):
    cell = ws.cell(row=r, column=c, value=v)
    cell.font = font
    if fill is not None:
        cell.fill = fill
    if fmt:
        cell.number_format = NUM.get(fmt, fmt)
    if align:
        cell.alignment = align
    if border:
        cell.border = BORDER
    return cell


def title(ws, text, span, sub=None):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    c = ws.cell(row=1, column=1, value=text)
    c.font = F_TITLE
    c.fill = FILL_TITLE
    c.alignment = AL_L
    ws.row_dimensions[1].height = 34
    for k in range(1, span + 1):
        ws.cell(row=1, column=k).fill = FILL_TITLE
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
        s = ws.cell(row=2, column=1, value=sub)
        s.font = F_S
        s.alignment = AL_L
        ws.row_dimensions[2].height = 30


def section(ws, r, text, span=8):
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=span)
    c = ws.cell(row=r, column=1, value=text)
    c.font = F_H2
    c.fill = FILL_H2
    c.alignment = AL_L
    ws.row_dimensions[r].height = 22
    for k in range(1, span + 1):
        ws.cell(row=r, column=k).fill = FILL_H2


def header_row(ws, r, cols, span_from=1):
    for i, t in enumerate(cols):
        c = ws.cell(row=r, column=span_from + i, value=t)
        c.font = F_HDR
        c.fill = FILL_HDR
        c.alignment = AL_C
        c.border = BORDER
    ws.row_dimensions[r].height = 30


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


# ---------------------------------------------------------------- 主构建
def build(scen, fx, out_path):
    meta, rateR, stats = scen["meta"], scen["rate"], scen["stats"]
    direction = meta["direction"]
    wb = Workbook()
    wb.remove(wb.active)

    # =========================================================== 00 封面
    ws0 = wb.create_sheet("00_封面说明")
    widths(ws0, {"A": 3, "B": 26, "C": 60, "D": 30, "E": 22})
    ws0.merge_cells("B2:D2")
    c = ws0.cell(row=2, column=2, value="汇率波动对报价的影响 · 测算工作簿")
    c.font = F_TITLE
    c.fill = FILL_TITLE
    c.alignment = AL_L
    ws0.row_dimensions[2].height = 36
    for k in (2, 3, 4):
        ws0.cell(row=2, column=k).fill = FILL_TITLE

    info = [
        ("案例", meta.get("title") or ""),
        ("产品 / 规格", f"{meta.get('product') or ''}  {meta.get('spec') or ''}"),
        ("交易方向", meta["direction_label"]),
        ("金额 / 币种", f"{meta['amount_fx']:,.2f} {meta['currency']}（{meta.get('pair')}）"),
        ("结算日 / 期限", f"{meta['settle_date']}（{meta['horizon_days']} 个自然日）"),
        ("汇率数据截至", meta["asof"]),
        ("历史序列", f"{fx['meta']['first_date']} ~ {fx['meta']['last_date']}，{fx['meta']['trading_days']} 个交易日，来源：国家外汇管理局人民币汇率中间价"),
        ("生成时间", meta["generated_at"]),
    ]
    r = 4
    for k, v in info:
        put(ws0, r, 2, k, F_B, FILL_BAND, align=AL_L)
        ws0.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        put(ws0, r, 3, v, F_N, align=AL_L)
        ws0.cell(row=r, column=4).border = BORDER
        r += 1

    r += 1
    section(ws0, r, "一、怎么用（改黄底，全簿自动重算）", 4)
    r += 1
    guide = [
        ("① 改参数", "在「01_输入参数」只改黄底单元格：金额、币种、方向、汇率、成本、目标毛利、分批比例。其余全是公式。"),
        ("② 看结果", "「02_汇率敏感性」「03_毛利测算」「05_分批结算」会自动重算；切方向后毛利率、平衡汇率同步切换口径。"),
        ("③ 查历史", "「06_历史汇率序列」是官方中间价的日频原始数据（静态值）；「07_历史分位」用公式实时计算分位与区间。"),
        ("④ 对公式", "「04_计算公式」「10_口径与免责」写明每一步的公式；scripts/verify.py 会用 Python 重算并与 Excel 交叉核对。"),
        ("⑤ 带报价", "「09_报价带入」给出目标毛利下的最低外币金额，可直接粘到报价单或形式发票环节。"),
    ]
    for k, v in guide:
        put(ws0, r, 2, k, F_B, None, align=AL_L)
        ws0.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        put(ws0, r, 3, v, F_N, align=AL_L)
        ws0.row_dimensions[r].height = 34
        r += 1

    r += 1
    section(ws0, r, "二、数据标签（必读）", 4)
    r += 1
    tags = [
        ("真实", "官方中间价历史序列、当日中间价、银行牌价，均有可回溯来源与日期。"),
        ("模拟", "人民币成本、结算期限、分批比例等示例参数，仅为演示计算流程，不是该订单真实数据。已模拟字段：" +
                 "、".join(meta.get("simulated_fields") or []) + "。"),
        ("估算", "银行点差带（示例值）、结汇手续费率（默认 0）——不是任何一家银行的真实报价。"),
    ]
    for k, v in tags:
        put(ws0, r, 2, k, F_B, FILL_IN if k == "模拟" else None, align=AL_C)
        ws0.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        put(ws0, r, 3, v, F_N, align=AL_L)
        ws0.row_dimensions[r].height = 32
        r += 1

    r += 1
    section(ws0, r, "三、合规边界", 4)
    r += 1
    ws0.merge_cells(start_row=r, start_column=2, end_row=r + 3, end_column=4)
    c = ws0.cell(row=r, column=2, value=(
        "本工作簿只做汇率情景测算：所有「若汇率为 R」的假设都是压力测试，不代表对未来汇率的任何判断，也未预测走势。\n"
        "本工作簿不推荐、不比较任何具体外汇避险产品（远期、期权、掉期、结构性产品）或操作；是否锁汇、如何锁汇由企业与银行独立决定。\n"
        "毛利与毛利率只反映汇率与成本假设下的静态关系；退税率、运费、合同条款、多币种交叉盘等未计入，见「10_口径与免责」。\n"
        "对外使用前请把模拟参数替换为真实数据，并核对银行实际结汇/购汇价。"))
    c.font = F_N
    c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    c.fill = FILL_WARN
    for k in (2, 3, 4):
        ws0.cell(row=r, column=k).fill = FILL_WARN

    # =========================================================== 01 输入参数
    ws1 = wb.create_sheet("01_输入参数")
    widths(ws1, {"A": 2, "B": 30, "C": 16, "D": 13, "E": 52})
    title(ws1, "01 · 输入参数与汇率口径", 5,
          "只改黄底单元格；白底为公式派生。出口收汇与进口付汇的计算方向由「交易方向」自动切换。")
    section(ws1, 4, "A. 业务输入", 5)
    rows = [
        ("交易方向", "出口收汇" if direction == "export" else "进口付汇", "text", "出口收汇 / 进口付汇（下拉选择）", "export" ),
        ("结算币种代码", meta["currency"], "text", "如 USD / EUR / 100JPY", None),
        ("汇率对", meta.get("pair") or f"{meta['currency']}/CNY", "text", "直接标价：1 单位外币 = X 人民币", None),
        ("业务外币金额", meta["amount_fx"], "money", "本笔业务的外币计价款（可含分批合计）", None),
        ("当日中间价", rateR["mid"], "rate4", "来源：国家外汇管理局 / 中国外汇交易中心；可直接覆盖", None),
        ("中间价日期", datetime.strptime(meta["asof"], "%Y-%m-%d").date(), "date", "", None),
        ("银行点差带（单侧 %）", rateR["band"], "pct3", "示例值；真实点差以银行报价为准", None),
        ("银行实际结汇/购汇价", rateR.get("actual_bank_rate") or None, "rate4", "有就填（最真实），口径选「实际成交价」", None),
        ("基准汇率口径", {"mid": "官方中间价", "mid_x_band_estimate": "中间价+点差带", "actual_bank_settle": "实际成交价"}.get(rateR["basis"], "中间价+点差带"), "text",
         "下拉：官方中间价 / 中间价+点差带 / 实际成交价", None),
        ("人民币成本", meta["cny_cost"], "money0", "出口：人民币成本；进口：货款外的人民币成本", None),
        ("进口后人民币销售收入", meta.get("resale_cny") or None, "money0", "仅进口付汇需要（毛利率分母）", None),
        ("目标毛利率", (meta["target_margin_pct"] if meta.get("target_margin_pct") is not None else None), "pct2", "填小数（0.10 = 10%），单元格显示为百分比；留空不算目标平衡汇率", None),
        ("目标毛利额（元）", meta.get("target_margin_cny") or None, "money0", "可选；与毛利率可同时存在", None),
        ("银行费用率 toll", meta["toll_rate"], "pct3", "填小数；出口：从收入扣减；进口：加到成本", None),
        ("交易日", datetime.strptime(meta.get("trade_date") or meta["asof"], "%Y-%m-%d").date(), "date", "", None),
        ("预计结算日", datetime.strptime(meta["settle_date"], "%Y-%m-%d").date(), "date", "", None),
        ("合同约定汇率", rateR.get("contract_rate") or None, "rate4", "可选；用于量化与市场汇率的差额", None),
        ("敏感性档位（%）", "-5,-3,-2,-1,0,1,2,3,5", "text", "逗号分隔，可任意增删", None),
    ]
    r = 5
    for name, val, fmt, note, _ in rows:
        put(ws1, r, 2, name, F_B, align=AL_L)
        put(ws1, r, 3, val if val is not None else "", F_IN, FILL_IN,
            fmt, AL_R if fmt not in ("text", "date") else AL_L)
        put(ws1, r, 4, "输入", F_S, FILL_IN_BORDER, align=AL_C)
        put(ws1, r, 5, note, F_S, align=AL_L)
        r += 1
    # 方向下拉
    dv_dir = DataValidation(type="list", formula1='"出口收汇,进口付汇"', allow_blank=False)
    ws1.add_data_validation(dv_dir)
    dv_dir.add("C5")
    dv_mode = DataValidation(type="list", formula1='"官方中间价,中间价+点差带,实际成交价"', allow_blank=False)
    ws1.add_data_validation(dv_mode)
    dv_mode.add("C13")

    section(ws1, 24, "B. 派生口径（公式，勿手改）", 5)
    # 输入行映射：5方向 6币种 7汇率对 8金额 9中间价 10日期 11点差 12实际 13口径
    #            14成本 15销售 16目标% 17目标额 18费用率 19交易日 20结算日 21合同 22档位
    der = [
        (25, "结汇价（银行现汇买入）= 中间价 ×(1−点差)",
         "=IF($C$13=\"实际成交价\",IF(ISNUMBER($C$12),$C$12,$C$9*(1-$C$11)),$C$9*(1-$C$11))", "rate6"),
        (26, "购汇价（银行现汇卖出）= 中间价 ×(1+点差)",
         "=IF($C$13=\"实际成交价\",IF(ISNUMBER($C$12),$C$12,$C$9*(1+$C$11)),$C$9*(1+$C$11))", "rate6"),
        (27, "方向符号（出口 −1 / 进口 +1）", "=IF($C$5=\"出口收汇\",-1,1)", "int"),
        (28, "基准汇率（用于测算）",
         "=IF($C$13=\"官方中间价\",$C$9,IF($C$13=\"实际成交价\",IF(ISNUMBER($C$12),$C$12,$C$9),IF($C$5=\"出口收汇\",$C$25,$C$26)))", "rate6"),
        (29, "口径说明（自动）",
         "=IF($C$13=\"官方中间价\",\"官方中间价：只适合分位对照\",IF($C$13=\"实际成交价\",\"银行实际成交价：最真实的口径\",\"中间价×点差带：示例估算，非银行真实报价\"))", "text"),
        (30, "结算期限（自然日）", "=$C$20-$C$19", "int"),
        (31, "结算期限（交易日估算）", "=ROUND($C$30*5/7,0)", "int"),
        (32, "汇率每变动 1% 的敞口（元）", "=ABS($C$8*$C$28*(1-$C$18))*0.01", "money"),
    ]
    for rr, name, f, fmt in der:
        put(ws1, rr, 2, name, F_B, align=AL_L)
        put(ws1, rr, 3, f, F_N, FILL_CALC, fmt, AL_R if fmt != "text" else AL_L)
        put(ws1, rr, 4, "公式", F_S, align=AL_C)
        put(ws1, rr, 5, "", F_S, align=AL_L)

    section(ws1, 34, "C. 口径提示", 5)
    notes = [
        "出口收汇：人民币收入 = 外币金额 × 结汇价 × (1 − 费用率)；结汇价用银行「现汇买入价」。",
        "进口付汇：人民币支出 = 外币金额 × 购汇价 × (1 + 费用率)；购汇价用银行「现汇卖出价」。",
        "中间价 ≠ 成交价：本例 2026-10-19 中国银行美元现汇买入价 6.6701，较当日中间价 6.7208 低约 0.75%。",
        "银行费用率默认 0（未计入手续费与电讯费），结汇/购汇手续费、远期锁汇点价、点差均需另行确认。",
        "本工作簿不预测汇率，不推荐避险产品。",
    ]
    rr = 35
    for n in notes:
        ws1.merge_cells(start_row=rr, start_column=2, end_row=rr, end_column=5)
        c = ws1.cell(row=rr, column=2, value="• " + n)
        c.font = F_S
        c.alignment = AL_L
        rr += 1
    ws1.freeze_panes = "A5"

    # 更新 IN 映射为真实行号
    rowmap = ["dir", "cur", "pair", "amount", "mid", "mid_date", "band", "actual", "mode",
              "cost", "resale", "tpct", "tcny", "toll", "trade_date", "settle", "contract", "shifts"]
    for i, k in enumerate(rowmap):
        IN[k] = f"'01_输入参数'!$C${5 + i}"
    IN["sell"] = "'01_输入参数'!$C$25"
    IN["buy"] = "'01_输入参数'!$C$26"
    IN["sign"] = "'01_输入参数'!$C$27"
    IN["base"] = "'01_输入参数'!$C$28"
    IN["basis"] = "'01_输入参数'!$C$29"
    IN["horizon"] = "'01_输入参数'!$C$30"
    IN["horizon_bd"] = "'01_输入参数'!$C$31"
    IN["exposure"] = "'01_输入参数'!$C$32"

    exp_f = f"({IN['dir']}=\"出口收汇\")"
    sign = IN["sign"]

    # 统一：出口收入 / 进口支出（"对外收付的人民币净额"）
    NET = f"({IN['amount']}*RATE*(1+{sign}*{IN['toll']}))"

    # =========================================================== 02 敏感性
    ws2 = wb.create_sheet("02_汇率敏感性")
    widths(ws2, {"A": 3, "B": 14, "C": 12, "D": 15, "E": 15, "F": 15, "G": 12, "H": 14, "I": 13, "J": 13})
    title(ws2, "02 · 汇率敏感性矩阵（汇率变动 ±1% / ±3% / ±5% …）", 10,
          "档位可改；RATE 为情景汇率。出口看人民币收入，进口看人民币支出。汇率变动只用于测算，不代表预测。")
    header_row(ws2, 4, ["汇率变动", "情景汇率", "外币金额", "人民币毛额", "银行费用", "人民币净额",
                        "较基准变化", "变化率", "毛利额", "毛利率"], 2)
    shifts_txt = "-5,-3,-2,-1,0,1,2,3,5"
    # 用 VALUE 拆档位：为兼容旧版 Excel，直接按固定 9 档布局，档位从输入解析也可（这里用固定 7 档 + 说明）
    shift_def = [-0.05, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.05]
    r0 = 5
    # 基准行放在最后，便于引用
    base_row = r0 + len(shift_def)
    for i, s in enumerate(shift_def):
        r = r0 + i
        put(ws2, r, 2, s, F_IN, FILL_IN, "pct1", AL_C)
        put(ws2, r, 4, f"={IN['amount']}", F_N, FILL_CALC, "money", AL_R)
        put(ws2, r, 3, f"=ROUND({IN['base']}*(1+B{r}),6)", F_B, FILL_CALC, "rate4", AL_R)
        put(ws2, r, 5, f"=D{r}*C{r}", F_N, FILL_CALC, "money", AL_R)
        put(ws2, r, 6, f"=ABS(E{r}-D{r}*C{r}*(1+{sign}*{IN['toll']}))", F_N, FILL_CALC, "money", AL_R)
        put(ws2, r, 7, f"=E{r}*(1+{sign}*{IN['toll']})", F_B, FILL_CALC, "money", AL_R)
        put(ws2, r, 8, f"=G{r}-G${base_row}", F_B, FILL_RES, "money", AL_R)
        put(ws2, r, 9, f"=IF(G${base_row}=0,0,H{r}/G${base_row})", F_N, FILL_CALC, "pct2", AL_R)
        put(ws2, r, 10, f"=IF({exp_f},IF(N({IN['cost']})=0,G{r}-{IN['cost']},G{r}-{IN['cost']}),"
                        f"IF(AND(N({IN['resale']})>0,N({IN['cost']})>=0),{IN['resale']}-(G{r}+{IN['cost']}),\"\"))",
            F_B, FILL_CALC, "money", AL_R)
        put(ws2, r, 11, f"=IF(J{r}=\"\",\"\",IF({exp_f},IF(G{r}=0,\"\",J{r}/G{r}),IF({IN['resale']}=0,\"\",J{r}/{IN['resale']})))",
            F_N, FILL_CALC, "pct2", AL_R)
    r = base_row
    put(ws2, r, 2, 0.0, F_B, FILL_RES, "pct1", AL_C)
    put(ws2, r, 4, f"={IN['amount']}", F_N, FILL_CALC, "money", AL_R)
    put(ws2, r, 3, f"={IN['base']}", F_B, FILL_RES, "rate4", AL_R)
    put(ws2, r, 5, f"=D{r}*C{r}", F_N, FILL_CALC, "money", AL_R)
    put(ws2, r, 6, f"=ABS(E{r}-D{r}*C{r}*(1+{sign}*{IN['toll']}))", F_N, FILL_CALC, "money", AL_R)
    put(ws2, r, 7, f"=E{r}*(1+{sign}*{IN['toll']})", F_B, FILL_RES, "money", AL_R)
    put(ws2, r, 8, 0, F_N, FILL_CALC, "money", AL_R)
    put(ws2, r, 9, 0, F_N, FILL_CALC, "pct2", AL_R)
    put(ws2, r, 10, f"=IF({exp_f},IF(N({IN['cost']})=0,G{r}-{IN['cost']},G{r}-{IN['cost']}),"
                    f"IF(AND(N({IN['resale']})>0,N({IN['cost']})>=0),{IN['resale']}-(G{r}+{IN['cost']}),\"\"))",
        F_B, FILL_RES, "money", AL_R)
    put(ws2, r, 11, f"=IF(J{r}=\"\",\"\",IF({exp_f},IF(G{r}=0,\"\",J{r}/G{r}),IF({IN['resale']}=0,\"\",J{r}/{IN['resale']})))",
        F_N, FILL_RES, "pct2", AL_R)

    r = base_row + 2
    section(ws2, r, "说明", 10)
    r += 1
    for t in [
        "情景汇率 = 基准汇率 ×(1 + 汇率变动)；基准汇率来自「01_输入参数」C28，随口径切换自动变化。",
        "人民币净额 = 外币金额 × 情景汇率 ×(1 + 方向符号 × 费用率)；出口方向符号 −1（扣除），进口 +1（加上）。",
        "变化率以人民币净额计；由于费用率按比例计提，变化率与汇率变动幅度一致（费用率为 0 时完全相同）。",
        "毛利额：出口 = 人民币净额 − 人民币成本；进口 = 进口后人民币销售收入 −（人民币净额 + 其他人民币成本）。",
        "本表为固定 9 档。若需其它档位，直接修改 B 列百分比即可（或在 HTML 版里任意增删档位）。",
    ]:
        ws2.merge_cells(start_row=r, start_column=2, end_row=r, end_column=10)
        c = ws2.cell(row=r, column=2, value="• " + t)
        c.font = F_S
        c.alignment = AL_L
        r += 1
    ws2.freeze_panes = "B5"

    # =========================================================== 03 毛利测算
    ws3 = wb.create_sheet("03_毛利测算")
    widths(ws3, {"A": 3, "B": 32, "C": 22, "D": 18, "E": 48, "F": 14})
    title(ws3, "03 · 毛利测算与盈亏平衡汇率", 5,
          "平衡汇率随输入成本与目标毛利自动重算；出口与进口的公式方向不同，方向切换后自动套用。")
    r = 4
    section(ws3, r, "A. 当前基准下的毛利", 5)
    r += 1
    header_row(ws3, r, ["项目", "数值", "公式 / 说明"], 2)
    r += 1
    base_res = scen["base"]
    B = IN["base"]
    lines3 = [
        ("基准汇率", f"={B}", "rate6", "来自「01_输入参数」C28"),
        ("外币金额", f"={IN['amount']}", "money", ""),
        ("人民币毛额", f"=C{2}*C{3}".replace("C2", "C5").replace("C3", "C6"), "money", "外币金额 × 汇率"),
        ("银行费用/点差（按比例）", None, "money", "金额 × 汇率 × 费用率"),
        ("人民币净额", None, "money", "毛额 −/+ 费用（出口扣减、进口增加）"),
        ("人民币成本（出口）/ 其他成本（进口）", f"=N({IN['cost']})", "money0", "来自输入"),
        ("进口后人民币销售收入", f"=IF(N({IN['resale']})=0,\"\",{IN['resale']})", "money0", "仅进口用"),
        ("毛利额", None, "money", "出口：净额 − 成本；进口：销售收入 − (净额 + 其他成本)"),
        ("毛利率", None, "pct2", "出口：毛利 ÷ 净额；进口：毛利 ÷ 销售收入"),
    ]
    first = r
    for i, (nm, f, fmt, note) in enumerate(lines3):
        rr = first + i
        put(ws3, rr, 2, nm, F_B, align=AL_L)
        put(ws3, rr, 3, f, F_N, FILL_CALC, fmt, AL_R)
        put(ws3, rr, 4, note, F_S, align=AL_L)
        ws3.merge_cells(start_row=rr, start_column=4, end_row=rr, end_column=5)
    R_ = {  # 行号
        "rate": first, "amt": first + 1, "gross": first + 2, "toll": first + 3,
        "net": first + 4, "cost": first + 5, "resale": first + 6, "margin": first + 7, "mpct": first + 8,
    }
    ws3.cell(row=R_["gross"], column=3, value=f"=C{R_['amt']}*C{R_['rate']}")
    ws3.cell(row=R_["toll"], column=3, value=f"=ABS(C{R_['gross']}-C{R_['net']})")
    ws3.cell(row=R_["net"], column=3, value=f"=C{R_['gross']}*(1+{sign}*{IN['toll']})")
    ws3.cell(row=R_["margin"], column=3,
             value=f"=IF({exp_f},C{R_['net']}-C{R_['cost']},IF(N(C{R_['resale']})=0,\"\",C{R_['resale']}-(C{R_['net']}+C{R_['cost']})))")
    ws3.cell(row=R_["mpct"], column=3,
             value=f"=IF(N(C{R_['margin']})=0,\"\",IF({exp_f},IF(C{R_['net']}=0,\"\",C{R_['margin']}/C{R_['net']}),"
                   f"IF(N(C{R_['resale']})=0,\"\",C{R_['margin']}/C{R_['resale']})))")
    for k in ("gross", "toll", "net", "margin", "mpct"):
        ws3.cell(row=R_[k], column=3).font = F_B
        ws3.cell(row=R_[k], column=3).fill = FILL_RES if k in ("margin", "mpct") else FILL_CALC
        ws3.cell(row=R_[k], column=3).number_format = NUM["money"] if k != "mpct" else NUM["pct2"]

    r = R_["mpct"] + 2
    section(ws3, r, "B. 盈亏平衡汇率（成本与其他条件不变）", 6)
    r += 1
    header_row(ws3, r, ["平衡点", "汇率", "较基准", "公式"], 2)
    r += 1
    R_ZERO, R_TP, R_TC, R_GAP = r, r + 1, r + 2, r + 3
    be_rows = []
    # 毛利=0
    f_zero = (f"=IF({exp_f},IF(C{R_['amt']}*(1-{IN['toll']})=0,\"\",C{R_['cost']}/(C{R_['amt']}*(1-{IN['toll']}))),"
              f"IF(N(C{R_['resale']})=0,\"\",(C{R_['resale']}-C{R_['cost']})/(C{R_['amt']}*(1+{IN['toll']}))))")
    be_rows.append(("毛利额 = 0", f_zero, R_ZERO,
                    "出口：R* = 成本 ÷ [金额 ×(1−费用率)]；进口：R* = (销售收入 − 其他成本) ÷ [金额 ×(1+费用率)]"))
    # 目标毛利率（出口）
    f_tp = f"=IF(AND({exp_f},N({IN['tpct']})>0),C{R_['cost']}/(C{R_['amt']}*(1-{IN['toll']})*(1-{IN['tpct']})),\"仅出口且填目标毛利率时计算\")"
    be_rows.append(("达到目标毛利率", f_tp, R_TP, "R* = 成本 ÷ [金额 ×(1−费用率)×(1−目标毛利率)]"))
    # 目标毛利额
    f_tc = f"=IF(AND({exp_f},N({IN['tcny']})>0),(C{R_['cost']}+{IN['tcny']})/(C{R_['amt']}*(1-{IN['toll']})),\"仅出口且填目标毛利额时计算\")"
    be_rows.append(("达到目标毛利额", f_tc, R_TC, "R* = (成本 + 目标毛利额) ÷ [金额 ×(1−费用率)]"))
    # 汇率缓冲 = 平衡汇率/基准 − 1
    be_rows.append(("汇率缓冲（毛利=0 平衡点相对基准）", f"=IF(ISNUMBER(C{R_ZERO}),C{R_ZERO}/C{R_['rate']}-1,\"\")", R_GAP,
                    "负值 = 汇率还要再跌这么多才亏（出口）；正值 = 还要涨这么多才亏（进口）"))
    for nm, f, rr, note in be_rows:
        put(ws3, rr, 2, nm, F_B, align=AL_L)
        put(ws3, rr, 3, f, F_B, FILL_RES, "rate6" if rr != R_GAP else "pct2", AL_R)
        if rr != R_GAP:
            put(ws3, rr, 4, f"=IF(ISNUMBER(C{rr}),C{rr}/$C${R_['rate']}-1,\"\")", F_N, FILL_CALC, "pct2", AL_R)
        else:
            put(ws3, rr, 4, "", F_S, align=AL_C)
        ws3.merge_cells(start_row=rr, start_column=5, end_row=rr, end_column=6)
        put(ws3, rr, 5, note, F_S, align=AL_L)
        ws3.cell(row=rr, column=6).border = BORDER
        ws3.column_dimensions["E"].width = 52

    r = R_GAP + 2
    section(ws3, r, "C. 毛利对汇率的一阶敏感", 6)
    r += 1
    r2 = r
    put(ws3, r2, 2, "汇率每变动 1% 的毛利变化（元）", F_B, align=AL_L)
    put(ws3, r2, 3, f"={IN['exposure']}", F_B, FILL_RES, "money", AL_R)
    ws3.merge_cells(start_row=r2, start_column=5, end_row=r2, end_column=6)
    put(ws3, r2, 5, "= |金额 × 汇率 ×(1−费用率)| × 1%；汇率下降 1% 则毛利减少同额（出口）", F_S, align=AL_L)
    r2 += 1
    put(ws3, r2, 2, "毛利=0 时汇率可跌/涨幅度（相对基准）", F_B, align=AL_L)
    put(ws3, r2, 3, f"=IF(ISNUMBER(C{R_ZERO}),ABS(C{R_ZERO}/C{R_['rate']}-1),\"\")", F_B, FILL_RES, "pct2", AL_R)
    ws3.merge_cells(start_row=r2, start_column=5, end_row=r2, end_column=6)
    put(ws3, r2, 5, "= |平衡汇率 ÷ 基准 − 1|", F_S, align=AL_L)
    r2 += 1
    put(ws3, r2, 2, "毛利被汇率吃光所需的变动幅度", F_B, align=AL_L)
    put(ws3, r2, 3, f"=IF({IN['exposure']}=0,\"\",C{R_['margin']}/{IN['exposure']})", F_B, FILL_RES, "pct2", AL_R)
    ws3.merge_cells(start_row=r2, start_column=5, end_row=r2, end_column=6)
    put(ws3, r2, 5, "当前毛利额 ÷ 每 1% 敞口，即毛利被汇率吃光的百分比（仅出口有意义）", F_S, align=AL_L)
    for rr in (r2 - 2, r2 - 1, r2):
        ws3.cell(row=rr, column=6).border = BORDER

    # =========================================================== 04 公式
    ws4 = wb.create_sheet("04_计算公式")
    widths(ws4, {"A": 3, "B": 24, "C": 62, "D": 40})
    title(ws4, "04 · 计算公式（与本簿各表、Python 验证脚本同源）", 4, "符号：A=外币金额；R=汇率；t=银行费用率；C=人民币成本；S=进口后销售收入；M=毛利额；m=毛利率。")
    header_row(ws4, 4, ["项目", "计算逻辑", "公式"], 2)
    F4 = [
        ("汇率口径", "直接标价：1 单位外币 = X 人民币。出口结汇看现汇买入价，进口购汇看现汇卖出价。",
         "结汇价 R_s = R_mid×(1−band)；购汇价 R_b = R_mid×(1+band)"),
        ("出口收汇", "收到外币 → 结汇成人民币", "收入 Rev = A × R_s × (1 − t)"),
        ("进口付汇", "付出人民币 → 购汇付外币", "支出 Pay = A × R_b × (1 + t)"),
        ("出口毛利", "收入减人民币成本", "M = Rev − C；m = M ÷ Rev"),
        ("进口毛利", "人民币销售收入减（外币折算支付 + 其他成本）", "M = S − (Pay + C_oth)；m = M ÷ S"),
        ("汇率变动 ±n%", "情景汇率与人民币金额变化", "R′ = R×(1±n)；ΔRev = A × R × n × (1 − t)"),
        ("每 1% 敞口", "汇率相对变动 1% 对应的人民币金额", "Exp = |A × R × (1 − t)| × 1%"),
        ("盈亏平衡（出口）", "毛利=0", "R* = C ÷ [A × (1 − t)]"),
        ("盈亏平衡（进口）", "毛利=0", "R* = (S − C_oth) ÷ [A × (1 + t)]"),
        ("目标毛利率汇率", "保目标毛利率所需最低汇率（出口）", "R* = C ÷ [A × (1 − t) × (1 − m)]"),
        ("目标毛利额汇率", "保目标毛利额所需最低汇率（出口）", "R* = (C + M) ÷ [A × (1 − t)]"),
        ("历史分位", "历史有多少交易日低于当前", "Pct = (低于当日数 + 0.5×相等数) ÷ 样本数"),
        ("已实现年化波动", "只描述过去的波动幅度，不是预测", "σ = std(ln R_t/R_{t−1}) × √252"),
        ("N 日典型波动", "年化波动折算到结算期，仅说明量级", "σ_N = σ × √(N ÷ 252)"),
        ("分批加权汇率", "各批次金额加权", "R_w = Σ(A_i × R_i) ÷ ΣA_i"),
        ("分批 vs 一次性", "分批结构效应（基准汇率差异）", "Δ = Σ(A_i×R_i) − ΣA_i × R_首日"),
    ]
    r = 5
    for nm, logic, f in F4:
        put(ws4, r, 2, nm, F_B, align=AL_L)
        put(ws4, r, 3, logic, F_N, align=AL_L)
        put(ws4, r, 4, f, F_N, FILL_CALC, align=AL_L)
        ws4.row_dimensions[r].height = 30
        r += 1

    # =========================================================== 05 分批
    ws5 = wb.create_sheet("05_分批结算")
    widths(ws5, {"A": 3, "B": 22, "C": 14, "D": 12, "E": 13, "F": 14, "G": 13, "H": 14, "I": 13, "J": 13})
    title(ws5, "05 · 分批结算情景（按各批次金额与结算时间）", 10,
          "各批次金额与假设汇率可改；合计校验自动提示。分批真正改变的是暴露时点分散，不降低期望损失。")
    batches = scen.get("batch", {}).get("batches") if scen.get("batch") else None
    if not batches:
        batches = [
            {"label": "T/T 30% 定金（签约即付）", "amount_fx": 30000, "days": 0, "rate": rateR["base_rate"]},
            {"label": "装运后 60 天 40%", "amount_fx": 40000, "days": 60, "rate": rateR["base_rate"]},
            {"label": "提单日 90 天 30%", "amount_fx": 30000, "days": 90, "rate": rateR["base_rate"]},
        ]
    header_row(ws5, 4, ["批次", "外币金额", "距结算天数", "假设汇率", "占比", "折算人民币（净）", "占合计", "(示例) 该批序号"], 2)
    r = 5
    bstart = r
    for b in batches:
        put(ws5, r, 2, b["label"], F_IN, FILL_IN, "text", AL_L)
        put(ws5, r, 3, b["amount_fx"], F_IN, FILL_IN, "money", AL_R)
        put(ws5, r, 4, b.get("days", 0), F_IN, FILL_IN, "int", AL_R)
        put(ws5, r, 5, b.get("rate", rateR["base_rate"]), F_IN, FILL_IN, "rate4", AL_R)
        put(ws5, r, 6, None, F_N, FILL_CALC, "pct2", AL_R)
        put(ws5, r, 7, None, F_B, FILL_CALC, "money", AL_R)
        put(ws5, r, 8, None, F_S, FILL_CALC, "pct2", AL_R)
        r += 1
    bend = r - 1
    put(ws5, r, 2, "合计", F_B, FILL_RES, align=AL_L)
    put(ws5, r, 3, f"=SUM(C{bstart}:C{bend})", F_B, FILL_RES, "money", AL_R)
    put(ws5, r, 4, f"=IF(C{r}=0,0,SUMPRODUCT(C{bstart}:C{bend},D{bstart}:D{bend})/C{r})", F_B, FILL_RES, "0.0", AL_R)
    put(ws5, r, 5, f"=IF(C{r}=0,0,SUMPRODUCT(C{bstart}:C{bend},E{bstart}:E{bend})/C{r})", F_B, FILL_RES, "rate4", AL_R)
    put(ws5, r, 6, 1, F_N, FILL_RES, "pct2", AL_R)
    put(ws5, r, 7, f"=SUM(G{bstart}:G{bend})", F_B, FILL_RES, "money", AL_R)
    put(ws5, r, 8, 1, F_N, FILL_RES, "pct2", AL_R)
    tot_row = r
    for i in range(bstart, bend + 1):
        ws5.cell(row=i, column=6, value=f"=IF($C${tot_row}=0,\"\",C{i}/$C${tot_row})")
        ws5.cell(row=i, column=7, value=f"=C{i}*E{i}*(1+{sign}*{IN['toll']})")
        ws5.cell(row=i, column=8, value=f"=IF($G${tot_row}=0,\"\",G{i}/$G${tot_row})")

    r = tot_row + 2
    put(ws5, r, 2, "与订单金额校验", F_B, align=AL_L)
    put(ws5, r, 3, f"=IF(ABS(C{tot_row}-{IN['amount']})<0.01,\"一致\",\"不一致：差 \"&TEXT(C{tot_row}-{IN['amount']},\"#,##0.00\"))",
        F_B, FILL_WARN, "text", AL_L)
    ws5.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)

    r += 2
    section(ws5, r, "分批 × 汇率变动敏感性（各批次同向等比例平移）", 10)
    r += 1
    header_row(ws5, r, ["汇率变动", "分批合计（净）", "一次性全额（净）", "分批−一次性", "较分批基准"], 2)
    r += 1
    s0 = r
    shifts = [-0.05, -0.03, -0.01, 0.0, 0.01, 0.03, 0.05]
    for i, s in enumerate(shifts):
        rr = s0 + i
        put(ws5, rr, 2, s, F_IN, FILL_IN, "pct1", AL_C)
        put(ws5, rr, 3, f"=SUMPRODUCT($C${bstart}:$C${bend},$E${bstart}:$E${bend})*(1+B{rr})*(1+{sign}*{IN['toll']})",
            F_B, FILL_CALC, "money", AL_R)
        put(ws5, rr, 4, f"={IN['amount']}*$E${tot_row}*(1+B{rr})*(1+{sign}*{IN['toll']})", F_N, FILL_CALC, "money", AL_R)
        put(ws5, rr, 5, f"=C{rr}-D{rr}", F_B, FILL_RES, "money", AL_R)
        put(ws5, rr, 6, f"=C{rr}-$G${tot_row}", F_B, FILL_CALC, "money", AL_R)
    r = s0 + len(shifts) + 1
    for t in [
        "折算人民币（净）= 批次金额 × 假设汇率 ×(1 + 方向符号 × 费用率)。",
        "一次性全额按第一批次（最早）的假设汇率折算，因此「分批−一次性」只反映各批基准汇率差异（结构效应）。",
        "敏感性档位对全部批次同向等比例平移；若想模拟「不同批次落在不同汇率」，直接改 E 列各批次汇率。",
        "分批并不降低期望损失：当方向未知时，它降低的是单点集中度。这里不做任何汇率预测。",
    ]:
        ws5.merge_cells(start_row=r, start_column=2, end_row=r, end_column=10)
        c = ws5.cell(row=r, column=2, value="• " + t)
        c.font = F_S
        c.alignment = AL_L
        r += 1
    ws5.freeze_panes = "B5"

    # =========================================================== 06 历史序列
    ws6 = wb.create_sheet("06_历史汇率序列")
    SER = "06_历史汇率序列"
    SER_SHORT = "'06_历史汇率序列'"
    LAST = 4 + len(fx["dates"])
    codes = [c["code"] for c in fx["currency_list"]]
    head = ["日期"] + [f"{c['code']}（{c['name_cn']}）" for c in fx["currency_list"]]
    widths(ws6, {"A": 12, "B": 14, "C": 14, "D": 14, "E": 14, "F": 14})
    ws6.column_dimensions["A"].width = 12
    title(ws6, "06 · 历史汇率原始序列（官方中间价，日频）", 15,
          f"来源：国家外汇管理局人民币汇率中间价；{fx['meta']['first_date']} ~ {fx['meta']['last_date']}，共 {fx['meta']['trading_days']} 个交易日。"
          "缺失工作日均为法定节假日，未插值。单位：1 单位外币 = X 人民币（JPY 为 100 JPY）。")
    header_row(ws6, 4, head[:15])
    r = 5
    for d in fx["dates"]:
        put(ws6, r, 1, datetime.strptime(d, "%Y-%m-%d").date(), F_N, None, "date", AL_C)
        for j, c in enumerate(fx["currency_list"][:14]):
            v = fx["currencies"][c["code"]]["values"].get(d)
            if v is not None:
                put(ws6, r, 2 + j, v, F_N, None, "rate6", AL_R)
        r += 1
    last_series_row = r - 1
    # 其余币种放右侧
    col0 = 17
    ws6.cell(row=4, column=col0, value="其余币种（同一天）").font = F_HDR
    ws6.cell(row=4, column=col0).fill = FILL_HDR
    rest = fx["currency_list"][14:]
    for j, c in enumerate(rest):
        put(ws6, 4, col0 + 1 + j, f"{c['code']}（{c['name_cn']}）", F_HDR, FILL_HDR, None, AL_C)
        for i, d in enumerate(fx["dates"]):
            v = fx["currencies"][c["code"]]["values"].get(d)
            if v is not None:
                put(ws6, 5 + i, col0 + 1 + j, v, F_N, None, "rate6", AL_R)
    ws6.freeze_panes = "B5"
    ws6.auto_filter.ref = f"A4:N{last_series_row}"

    # =========================================================== 07 历史分位
    ws7 = wb.create_sheet("07_历史分位")
    widths(ws7, {"A": 3, "B": 28, "C": 16, "D": 16, "E": 16, "F": 54})
    title(ws7, "07 · 历史区间与分位（全部由公式实时计算）", 6,
          "直接引用「06_历史汇率序列」的原始列计算：换币种 = 改 C5 的列字母；窗口 = 末日往前 365 / 1095 天，左开右闭。")
    r = 4
    section(ws7, r, "A. 计算设定", 6)
    r += 1
    put(ws7, r, 2, "数据末日", F_B, align=AL_L)
    put(ws7, r, 3, f"=MAX({SER_SHORT}!$A$5:$A${LAST})", F_N, FILL_CALC, "date", AL_R)
    put(ws7, r, 4, "自动取 06 表最新日期", F_S, align=AL_L)
    ws7.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    R_DATE = r
    r += 1
    put(ws7, r, 2, "币种列（06 表中的列字母）", F_B, align=AL_L)
    put(ws7, r, 3, "B", F_IN, FILL_IN, "text", AL_C)
    put(ws7, r, 4, "B=USD  C=EUR  D=JPY  E=HKD  F=GBP  G=AUD  H=NZD  I=SGD  J=CHF  K=CAD  L=MOP  M=MYR  N=RUB", F_S, align=AL_L)
    ws7.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    R_COL = r
    r += 1
    put(ws7, r, 2, "当前中间价（分位基准）", F_B, align=AL_L)
    put(ws7, r, 3, f"={IN['mid']}", F_N, FILL_CALC, "rate4", AL_R)
    put(ws7, r, 4, "来自「01_输入参数」C9；可覆盖为其他口径值", F_S, align=AL_L)
    ws7.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    R_CUR = r

    r += 2
    section(ws7, r, "B. 分位与区间", 6)
    r += 1
    header_row(ws7, r, ["指标", "近 1 年", "近 3 年", "公式说明"], 2)
    r += 1
    R_START = r
    keys = ["win", "n", "max", "maxd", "min", "mind", "mean", "med", "pct", "dd", "up", "width"]
    labels = {
        "win": "窗口起点", "n": "样本交易日数", "max": "窗口最高", "maxd": "最高出现日",
        "min": "窗口最低", "mind": "最低出现日", "mean": "窗口均值", "med": "窗口中位数",
        "pct": "当前值分位", "dd": "当前距最高", "up": "当前距最低", "width": "区间最高/最低",
    }
    how = {
        "win": "末日 − 365 / − 1095 天", "n": "SUMPRODUCT(--窗口掩码)",
        "max": "AGGREGATE(14,6,列/掩码,1)", "maxd": "INDEX/MATCH 取该值对应日期",
        "min": "AGGREGATE(15,6,列/掩码,1)", "mind": "INDEX/MATCH 取该值对应日期",
        "mean": "SUMPRODUCT(掩码×列) ÷ 样本数", "med": "MEDIAN(IF(掩码,列))",
        "pct": "(低于当前 + 0.5×等于当前) ÷ 样本数", "dd": "当前值 ÷ 最高 − 1",
        "up": "当前值 ÷ 最低 − 1", "width": "最高 ÷ 最低 − 1",
    }
    ROW = {k: R_START + i for i, k in enumerate(keys)}
    for k in keys:
        put(ws7, ROW[k], 2, labels[k], F_B,
            FILL_RES if k in ("pct",) else None, align=AL_L)
        put(ws7, ROW[k], 5, how[k], F_S, align=AL_L)
        ws7.merge_cells(start_row=ROW[k], start_column=5, end_row=ROW[k], end_column=6)

    for ci, years, days in ((3, 1, 365), (4, 3, 1095)):
        L = get_column_letter(ci)
        win_cell = f"${L}${ROW['win']}"
        # 币种列由 C6 的字母 + 固定行范围构造动态区间
        vcol = (f'INDIRECT("{SER_SHORT}!$"&$C${R_COL}&"$5:$"&$C${R_COL}&"${LAST}")')
        dcol = f"{SER_SHORT}!$A$5:$A${LAST}"
        # 窗口掩码：日期在窗口内且值非空。用 SUMPRODUCT 组合，兼容 Excel 2010+
        # （本机实测 MAXIFS/MINIFS 在部分 Office 版本返回 #NAME?，故一律不用）
        mask = f'(({dcol}>={win_cell})*({vcol}>0))'
        put(ws7, ROW["win"], ci, f"=$C${R_DATE}-{days}", F_N, FILL_CALC, "date", AL_R)
        put(ws7, ROW["n"], ci,
            f'=SUMPRODUCT(--{mask})', F_N, FILL_CALC, "int", AL_R)
        # 窗口最高 / 最低：乘以区间宽度做掩码（负数取最大时需先归一化：用负偏移）
        vmax = (f'=IFERROR(AGGREGATE(14,6,{vcol}/{mask},1),"")')
        vmin = (f'=IFERROR(AGGREGATE(15,6,{vcol}/{mask},1),"")')
        put(ws7, ROW["max"], ci, vmax, F_B, FILL_RES, "rate6", AL_R)
        put(ws7, ROW["maxd"], ci,
            f'=IFERROR(INDEX({dcol},MATCH({L}{ROW["max"]},{vcol},0)),"")', F_N, FILL_CALC, "date", AL_R)
        put(ws7, ROW["min"], ci, vmin, F_B, FILL_RES, "rate6", AL_R)
        put(ws7, ROW["mind"], ci,
            f'=IFERROR(INDEX({dcol},MATCH({L}{ROW["min"]},{vcol},0)),"")', F_N, FILL_CALC, "date", AL_R)
        put(ws7, ROW["mean"], ci,
            f'=IFERROR(SUMPRODUCT({mask}*{vcol})/{L}{ROW["n"]},"")', F_N, FILL_CALC, "rate6", AL_R)
        # 中位数：用 SUMPRODUCT 求低于中位数的个数太绕，改为「窗口内按值排序后的中间值」不可行
        # → 直接给出近 1 年 / 3 年窗口中位数用 MEDIAN + IF 的数组写法，并用 _xlfn 无关函数避开兼容问题
        put(ws7, ROW["med"], ci,
            f'=IFERROR(MEDIAN(IF({mask},{vcol})),"")', F_N, FILL_CALC, "rate6", AL_R)
        put(ws7, ROW["pct"], ci,
            (f'=IF({L}{ROW["n"]}=0,"",'
             f'(COUNTIFS({dcol},">="&{win_cell},{vcol},"<"&$C${R_CUR})'
             f'+0.5*COUNTIFS({dcol},">="&{win_cell},{vcol},$C${R_CUR}))'
             f'/{L}{ROW["n"]})'), F_B, FILL_RES, "pct2", AL_R)
        put(ws7, ROW["dd"], ci, f'=IFERROR($C${R_CUR}/{L}{ROW["max"]}-1,"")', F_N, FILL_CALC, "pct2", AL_R)
        put(ws7, ROW["up"], ci, f'=IFERROR($C${R_CUR}/{L}{ROW["min"]}-1,"")', F_N, FILL_CALC, "pct2", AL_R)
        put(ws7, ROW["width"], ci, f'=IFERROR({L}{ROW["max"]}/{L}{ROW["min"]}-1,"")', F_N, FILL_CALC, "pct2", AL_R)

    r = ROW["width"] + 2
    for t in (
        "分位口径与 HTML、Python 完全一致：(低于当前值样本数 + 0.5 × 等于当前值样本数) ÷ 窗口样本数。",
        "窗口按自然日回看 365 / 1095 天，左开右闭（起点之后、含末日）；缺失的工作日均为法定节假日，未做插值。",
        "为兼容各类 Office 版本，本表刻意不使用 MAXIFS / MINIFS（部分版本会返回 #NAME?），改用 AGGREGATE + SUMPRODUCT。",
        "「窗口中位数」是数组公式：在 Excel 里选中该格后按 Ctrl+Shift+Enter 确认一次即可。",
        "本表只描述过去到过哪里：分位低不等于会涨，分位高不等于会跌。",
    ):
        ws7.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        c = ws7.cell(row=r, column=2, value="• " + t)
        c.font = F_S
        c.alignment = AL_L
        r += 1
    SHEET07_ROW = ROW

    # =========================================================== 08 实时汇率记录
    ws8 = wb.create_sheet("08_实时汇率记录")
    widths(ws8, {"A": 22, "B": 18, "C": 30, "D": 14, "E": 12, "F": 16, "G": 44})
    title(ws8, "08 · 实时汇率取数记录（可追溯）", 7,
          "每次取数追加一行：谁取的、何时、从哪个页面、什么口径、数值。报价留痕就靠这张表。")
    header_row(ws8, 4, ["取数时间", "来源", "页面/接口", "币种对", "口径", "数值", "备注"])
    recs = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    recs.append((now, "国家外汇管理局", "https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do",
                 "USD/CNY", "中间价", rateR["mid"], "当日 09:15 公布；历史序列同源（07 表）"))
    boc = rateR.get("boc_reference")
    if boc:
        q = boc["quotes"]
        recs.append((boc.get("time", now), "中国银行外汇牌价", boc.get("url", ""),
                     "USD/CNY", "现汇买入价", q.get("现汇买入价"), "出口结汇到手价参考；单位 100 外币"))
        recs.append((boc.get("time", now), "中国银行外汇牌价", boc.get("url", ""),
                     "USD/CNY", "现汇卖出价", q.get("现汇卖出价"), "进口购汇付出价参考"))
        recs.append((boc.get("time", now), "中国银行外汇牌价", boc.get("url", ""),
                     "USD/CNY", "中行折算价", q.get("中行折算价"), "银行内部折算口径，非成交价"))
    for s in fx["sources"]:
        if s.get("role") == "cross_check":
            for k, v in (s.get("quote") or {}).items():
                recs.append((s.get("time") or s.get("date") or now, s.get("name", ""), s.get("url", ""),
                             k, "交叉核对", v, s.get("note", "")))
    r = 5
    for rec in recs:
        for j, v in enumerate(rec):
            put(ws8, r, 1 + j, v, F_N if j else F_S,
                None, "rate4" if j == 5 else ("text" if j in (0, 2, 6) else None), AL_L if j in (0, 2, 6, 3) else AL_R)
        r += 1
    r += 1
    for t in [
        "口径不可混用：中间价不能当作结汇价；现汇买入价 ≠ 现汇卖出价。",
        "取数要连带记时间：盘中汇率随时变动，报价单上写「某日某时」比写「今日汇率」可追溯。",
        "第三方聚合器（ECB 经桥接换算、er-api 等）只做数量级核对，不作报价依据。",
    ]:
        ws8.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        c = ws8.cell(row=r, column=1, value="• " + t)
        c.font = F_S
        c.alignment = AL_L
        r += 1
    ws8.freeze_panes = "A5"

    # =========================================================== 09 报价带入
    ws9 = wb.create_sheet("09_报价带入")
    widths(ws9, {"A": 3, "B": 28, "C": 20, "D": 20, "E": 46})
    title(ws9, "09 · 把汇率参数带入出口报价", 5,
          "输入目标毛利率与人民币成本，得到「汇率不变时必须达到的最低外币金额」；这是报价底线，不是市场价预测。")
    r = 4
    section(ws9, r, "报价底线计算", 5)
    r += 1
    header_row(ws9, r, ["项目", "数值", "单位", "公式 / 说明"], 2)
    r += 1
    p_start = r
    prow = {
        "cost": r, "m": r + 1, "toll": r + 2, "minrev": r + 3, "amt": r + 4, "qty": r + 5, "unit": r + 6,
    }
    items9 = [
        ("人民币成本", f"={IN['cost']}", "元", "来自输入"),
        ("目标毛利率", f"={IN['tpct']}", "%", "来自输入（示例 10%）"),
        ("银行费用率", f"={IN['toll']}", "%", "来自输入"),
        ("所需人民币收入（下限，含费用）", f"=IFERROR(C{prow['cost']}/((1-C{prow['m']})*(1-C{prow['toll']})),\"\")", "元",
         "= 成本 ÷ [(1−目标毛利率)×(1−费用率)]"),
        ("对应外币金额（下限）", f"=IFERROR(C{prow['minrev']}/{IN['base']},\"\")", "外币",
         "= 所需收入 ÷ 基准汇率（汇率不变假设）"),
        ("数量（可选）", 377, "吨", "填写实际数量，自动折算单价"),
        ("折算单价（下限）", f"=IFERROR(C{prow['amt']}/C{prow['qty']},\"\")", "外币/吨", "= 外币金额下限 ÷ 数量"),
    ]
    for nm, f, unit, note in items9:
        put(ws9, r, 2, nm, F_B, align=AL_L)
        fmt = "pct2" if unit == "%" else ("money" if unit in ("元",) else ("rate4" if "外币" == unit else "money"))
        if nm.startswith("数量"):
            put(ws9, r, 3, f, F_IN, FILL_IN, "int", AL_R)
        else:
            put(ws9, r, 3, f, F_B, FILL_RES if "下限" in nm else FILL_CALC, fmt, AL_R)
        put(ws9, r, 4, unit, F_S, align=AL_C)
        put(ws9, r, 5, note, F_S, align=AL_L)
        r += 1

    r += 1
    section(ws9, r, "报价确定性检查（汇率变动多少会把底线打穿）", 5)
    r += 1
    for t in [
        "底线外币金额是按「汇率不变」算出来的；汇率一旦下行，同样的外币收入折算成人民币就会变少。",
        "把上面的金额与「03_毛利测算」的平衡汇率一起看：平衡汇率就是底线被打穿的位置。",
        "报价单上建议注明：所用汇率与取数时间、口径（中间价/银行成交价）、以及汇率大幅变动时的重新议价条件（是否写入由业务与法务决定）。",
        "本表不预测汇率，不推荐避险产品。",
    ]:
        ws9.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        c = ws9.cell(row=r, column=2, value="• " + t)
        c.font = F_S
        c.alignment = AL_L
        r += 1

    # =========================================================== 10 口径与免责
    ws10 = wb.create_sheet("10_口径与免责")
    widths(ws10, {"A": 3, "B": 26, "C": 70, "D": 34})
    title(ws10, "10 · 口径、数据缺口与免责", 4, "缺口比结论更重要：每一项未计入因素都可能改变最后那个数字。")
    header_row(ws10, 4, ["项目", "说明", "处理方式"], 2)
    gaps = [
        ("结汇/购汇手续费", "银行电讯费、手续费、单证费等，按笔收取，部分银行对大额另议。", "费用率默认 0；拿到实际费率后填入「01_输入参数」C18"),
        ("银行点差", "买价与卖价之差，随币种、金额、时段、客户等级浮动，且盘中变化。", "点差带为示例 ±0.25%；建议改用银行实际成交价（口径选「实际成交价」）"),
        ("远期锁汇点价", "远期汇率 = 即期 + 掉期点，取决于两币利差与期限；本簿未取任何远期报价。", "未计入；如需测算锁汇成本，属独立任务"),
        ("交易日与节假日", "长假导致实际可结汇日顺延，影响占用天数。", "按自然日计算，交易日按 ×5/7 估算"),
        ("多币种交叉盘", "以第三币种计价/结算时的交叉汇率。", "未处理；需另取两组中间价合成"),
        ("合同条款", "付款条件、汇率调整条款、迟延利息等改变实际暴露。", "按线性模型计算，未建模条款"),
        ("成本端汇率联动", "若原料或运费以外币计价，人民币成本本身随汇率变动。", "成本视为常数"),
        ("税务与退税", "出口退税率、免抵退对成本折算的影响。", "未纳入；属报价与税务环节"),
        ("样本口径差异", "历史序列为官方中间价；银行牌价与之常年存在差异。", "跨口径比较会失真，已分别标注"),
    ]
    r = 5
    for nm, d, how in gaps:
        put(ws10, r, 2, nm, F_B, align=AL_L)
        put(ws10, r, 3, d, F_N, align=AL_L)
        put(ws10, r, 4, how, F_S, align=AL_L)
        ws10.row_dimensions[r].height = 30
        r += 1
    r += 1
    section(ws10, r, "数据来源", 4)
    r += 1
    header_row(ws10, r, ["来源", "地址 / 口径", "时间"], 2)
    r += 1
    for s in fx["sources"]:
        put(ws10, r, 2, s.get("name", ""), F_B, align=AL_L)
        put(ws10, r, 3, f"{s.get('url','')}\n{s.get('note','')}", F_N, align=AL_L)
        put(ws10, r, 4, s.get("time") or s.get("date") or s.get("scope") or "", F_S, align=AL_L)
        ws10.row_dimensions[r].height = 42
        r += 1
    r += 1
    ws10.merge_cells(start_row=r, start_column=2, end_row=r + 2, end_column=4)
    c = ws10.cell(row=r, column=2, value=(
        "免责：本工作簿只做汇率情景测算，不预测汇率走势，不构成任何外汇避险产品或交易操作的推荐。\n"
        "「若汇率为 R」的全部内容均为压力测试假设，不代表对未来汇率的判断。\n"
        "模拟参数（已标注）仅用于演示计算流程；对外使用前请替换为真实数据并核对银行实际成交价。"))
    c.font = F_N
    c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    c.fill = FILL_WARN
    for k in (2, 3, 4):
        ws10.cell(row=r, column=k).fill = FILL_WARN

    wb.save(out_path)
    print(f"wrote {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--fx", default=os.path.join(ROOT, "build", "fx_series.json"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    scen = json.load(open(a.scenario, encoding="utf-8"))
    fx = json.load(open(a.fx, encoding="utf-8"))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    build(scen, fx, a.out)


if __name__ == "__main__":
    main()
