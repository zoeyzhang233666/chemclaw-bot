# -*- coding: utf-8 -*-
"""
build_xlsx.py —— 生成带“可运行 Excel 公式”的进口汇率敏感性分析工作簿

原则
----
1. 每一张结果表都由 Excel 原生公式计算（SUM / 乘积 / INDEX-MATCH / NORM 等），
   不使用 Python 预先算好的硬编码值 —— 用户改金额 / 汇率 / 付款比例 / 成本参数后自动重算。
2. 唯一录入区：01 参数与汇率。其它表的黄色底色单元格不写死结果。
3. 历史汇率写入 08 表（真实数据），并附来源与口径声明。
4. 页签内“公式说明”列逐条给出该单元格的公式，便于审计。

用法
----
    python build_xlsx.py input.json -o output/工作簿.xlsx --history data/fx_real_data.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime

import xlsxwriter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fx_engine as E  # noqa: E402

DEFAULT_HIST = os.path.join(ROOT, "data", "fx_real_data.json")


# ---------------------------------------------------------------- 样式
def make_formats(wb):
    f = {}
    base = dict(font_name="微软雅黑", font_size=10)
    f["title"] = wb.add_format({**base, "font_size": 16, "bold": True, "font_color": "#0d2b4e"})
    f["sub"] = wb.add_format({**base, "font_size": 9.5, "font_color": "#5b6b7f", "italic": True})
    f["sec"] = wb.add_format({**base, "font_size": 11, "bold": True, "font_color": "#ffffff",
                              "bg_color": "#1f4e79", "align": "left", "valign": "vcenter", "indent": 1})
    f["hdr"] = wb.add_format({**base, "bold": True, "bg_color": "#dbe5f1", "border": 1,
                              "border_color": "#b8c6d9", "align": "center", "valign": "vcenter", "text_wrap": True})
    f["lab"] = wb.add_format({**base, "border": 1, "border_color": "#e3e8ee", "align": "left", "valign": "vcenter"})
    f["lab_b"] = wb.add_format({**base, "bold": True, "border": 1, "border_color": "#e3e8ee",
                                "align": "left", "valign": "vcenter"})
    # 录入单元格：浅黄底 + 蓝字
    f["in_num"] = wb.add_format({**base, "num_format": "#,##0.00####", "bg_color": "#fff7d6",
                                 "font_color": "#1f4e79", "border": 1, "border_color": "#e0c87a"})
    f["in_txt"] = wb.add_format({**base, "bg_color": "#fff7d6", "font_color": "#1f4e79",
                                 "border": 1, "border_color": "#e0c87a"})
    f["in_pct"] = wb.add_format({**base, "num_format": "0.0%", "bg_color": "#fff7d6",
                                  "font_color": "#1f4e79", "border": 1, "border_color": "#e0c87a"})
    f["in_rate"] = wb.add_format({**base, "num_format": "0.0000", "bg_color": "#fff7d6",
                                  "font_color": "#1f4e79", "border": 1, "border_color": "#e0c87a", "bold": True})
    # 计算单元格
    f["num"] = wb.add_format({**base, "num_format": "#,##0.00", "border": 1, "border_color": "#e3e8ee"})
    f["num0"] = wb.add_format({**base, "num_format": "#,##0", "border": 1, "border_color": "#e3e8ee"})
    f["rate"] = wb.add_format({**base, "num_format": "0.0000", "border": 1, "border_color": "#e3e8ee", "align": "center"})
    f["pct"] = wb.add_format({**base, "num_format": "0.00%", "border": 1, "border_color": "#e3e8ee"})
    f["pct1"] = wb.add_format({**base, "num_format": "0.0%", "border": 1, "border_color": "#e3e8ee", "align": "center"})
    f["tot"] = wb.add_format({**base, "num_format": "#,##0.00", "bold": True, "bg_color": "#eaf1f8",
                              "border": 1, "border_color": "#b8c6d9", "top": 2})
    f["tot_lab"] = wb.add_format({**base, "bold": True, "bg_color": "#eaf1f8",
                                  "border": 1, "border_color": "#b8c6d9", "align": "left"})
    f["note"] = wb.add_format({**base, "font_size": 9, "font_color": "#6b5a2a", "text_wrap": True,
                               "valign": "top", "bg_color": "#fffbe8", "border": 1, "border_color": "#ecdcaa"})
    f["fml"] = wb.add_format({**base, "font_size": 9, "font_color": "#2f5597", "font_name": "Consolas",
                              "border": 1, "border_color": "#e3e8ee"})
    f["up"] = wb.add_format({**base, "num_format": "#,##0.00;[Red]-#,##0.00", "border": 1, "border_color": "#e3e8ee"})
    f["up0"] = wb.add_format({**base, "num_format": "#,##0;[Red]-#,##0", "border": 1, "border_color": "#e3e8ee"})
    f["real"] = wb.add_format({**base, "bg_color": "#e8f6e8", "font_color": "#1c6b2f", "border": 1,
                               "border_color": "#b7dfb7", "align": "center"})
    f["sim"] = wb.add_format({**base, "bg_color": "#f3ecff", "font_color": "#5b2fb0", "border": 1,
                              "border_color": "#cdb9f0", "align": "center"})
    f["demo"] = wb.add_format({**base, "bg_color": "#fff3d6", "font_color": "#8a5a00", "border": 1,
                               "border_color": "#e8c98a", "align": "center"})
    f["date"] = wb.add_format({**base, "num_format": "yyyy-mm-dd", "border": 1, "border_color": "#e3e8ee", "align": "center"})
    f["link"] = wb.add_format({**base, "font_color": "#1f6fd0", "underline": 1})
    return f


def _minus_years(d, years):
    """往前推 N 年；2月29日回退到2月28日。"""
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=28)


def sec(ws, row, text, width=10):
    ws.merge_range(row, 0, row, width - 1, text, ws._fmts["sec"])
    return row + 1


def hdr(ws, row, cols, widths=None):
    for i, c in enumerate(cols):
        ws.write(row, i, c, ws._fmts["hdr"])
    if widths:
        for i, w in enumerate(widths):
            ws.set_column(i, i, w)
    return row + 1


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--history", default=DEFAULT_HIST)
    args = ap.parse_args()

    inputs = json.load(open(args.input, encoding="utf-8"))
    history = json.load(open(args.history, encoding="utf-8")) if os.path.exists(args.history) else None

    ccy = (inputs.get("foreign_currency") or "USD").upper()
    rates = inputs.get("rates") or {}
    costs = inputs.get("costs") or {}
    sales = inputs.get("sales") or {}
    pay = inputs.get("payment") or {}
    trs = pay.get("tranches") or [{"pct": 1.0}, {"pct": 0.0}]
    if len(trs) == 1:
        trs.append({"pct": 0.0})
    qty = E.num(inputs.get("quantity"))
    amount = E.num(inputs.get("amount_fc"))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    wb = xlsxwriter.Workbook(args.out, {"nan_inf_to_errors": True})
    wb.set_properties({
        "title": f"{inputs.get('product','进口采购')} 汇率敏感性分析工作簿",
        "subject": "进口付汇汇率风险测算（不构成汇率预测或交易建议）",
        "author": "fx-import-cost-sensitivity skill",
        "comments": "历史汇率来自 ECB 参考汇率与 CFETS 中间价等公开真实数据。",
    })
    F = make_formats(wb)
    # 让 ws 能拿到格式表
    _orig_add = wb.add_worksheet
    wb._fmts = F

    SHEETS = []

    # ============================================================ 01 参数与汇率
    ws = wb.add_worksheet("01 参数与汇率")
    ws._rowlab = {}
    RL = ws._rowlab
    ws._fmts = F
    ws.set_column(0, 0, 30); ws.set_column(1, 1, 20); ws.set_column(2, 2, 14)
    ws.set_column(3, 3, 52); ws.set_column(4, 4, 12)
    ws.write(0, 0, "01 参数与汇率（唯一录入区）", F["title"])
    ws.write(1, 0, "所有黄色底色单元格可直接修改；其余表全部由公式联动计算。绿色=真实数据，紫色=模拟值，黄色=演示值。", F["sub"])
    ws.set_row(1, 26)

    r = 3
    r = sec(ws, r, "A. 交易基本信息", 5)
    r = hdr(ws, r, ["项目", "数值", "单位", "说明 / 来源", "性质"])
    rows_a = [
        ("采购金额（外币）", amount, ccy, "合同外币金额，必填", "real"),
        ("外币币种", ccy, "", "任意币种（USD/EUR/JPY/SAR…）", "real"),
        ("交易方向", "IMPORT_PAYMENT", "", "进口付汇：人民币贬值 → 人民币成本上升", "real"),
        ("产品 / 规格", inputs.get("product", ""), "", "", "real"),
        ("HS 编码", inputs.get("hs_code", ""), "", "以《中华人民共和国进出口税则》为准", "real"),
        ("原产国", inputs.get("origin", ""), "", "", "real"),
        ("贸易术语", inputs.get("incoterm", ""), "", "", "real"),
        ("合同数量", qty, "吨", inputs.get("quantity_note", "用于换算单位成本"), "sim"),
        ("汇率标价方向", "1 外币 = x 人民币", "", "CNY per FC（x 上升=人民币贬值）", "real"),
        ("公司预算汇率", E.num(inputs.get("budget_rate")), "CNY/FC", "内部预算/成本核算用", "sim"),
    ]
    r0_a = r
    def cell_addr(r_, c_):
        return xlsxwriter.utility.xl_rowcol_to_cell(r_, c_)
    A = {}  # 名称 -> 地址
    for name, val, unit, note, kind in rows_a:
        ws.write(r, 0, name, F["lab_b"]); ws._rowlab[name] = r
        if isinstance(val, (int, float)) and name in ("采购金额（外币）", "合同数量", "公司预算汇率"):
            ws.write_number(r, 1, val if val is not None else 0, F["in_num"])
            A[name] = cell_addr(r, 1)
        else:
            ws.write(r, 1, val if val is not None else "", F["in_txt"] if name not in ("汇率标价方向", "交易方向") else F["lab"])
            if name == "汇率标价方向":
                A[name] = cell_addr(r, 1)
        ws.write(r, 2, unit, F["lab"])
        ws.write(r, 3, note, F["lab"])
        ws.write(r, 4, {"real": "真实", "sim": "模拟", "demo": "演示"}[kind],
                 F["real"] if kind == "real" else (F["sim"] if kind == "sim" else F["demo"]))
        r += 1

    r += 1
    r = sec(ws, r, "B. 四类汇率口径（务必区分，不可混用）", 5)
    r = hdr(ws, r, ["口径", f"汇率（CNY / 1 {ccy}）", "日期", "来源 / 定义", "性质"])
    r_b = r
    defs = [
        ("市场汇率", E.num(rates.get("market")), rates.get("market_date"),
         rates.get("source", {}).get("market", "欧洲央行 ECB 参考汇率（经交叉折算）"), "real"),
        ("人民币汇率中间价（PBOC/CFETS）", E.num(rates.get("pboc")), rates.get("pboc_date"),
         rates.get("source", {}).get("pboc", "人民银行授权中国外汇交易中心每日 9:15 公布"), "real"),
        ("银行实际购汇价（现汇卖出价）", E.num(rates.get("bank")), rates.get("bank_date"),
         rates.get("source", {}).get("bank", "银行实盘，须由企业提供"), "demo"),
        ("海关计征汇率", E.num(rates.get("customs")), rates.get("customs_date"),
         rates.get("source", {}).get("customs", "依法规取上月第三个星期三中间价"), "demo"),
    ]
    RK = {}
    for name, val, d, src, kind in defs:
        ws.write(r, 0, name, F["lab_b"]); ws._rowlab[name] = r
        ws.write_number(r, 1, val if val is not None else 0, F["in_rate"])
        ws.write(r, 2, str(d or ""), F["lab"])
        ws.write(r, 3, src, F["lab"])
        ws.write(r, 4, {"real": "真实", "sim": "模拟", "demo": "演示"}[kind],
                 F["real"] if kind == "real" else (F["sim"] if kind == "sim" else F["demo"]))
        RK[name] = cell_addr(r, 1)
        r += 1
    r_market, r_pboc, r_bank, r_customs = r_b, r_b + 1, r_b + 2, r_b + 3

    # 基准汇率选择（用 INDEX/MATCH 指向所选口径）
    r += 0
    ws.write(r, 0, "基准汇率取值口径", F["lab_b"])
    _bm = {"bank": "银行实际购汇价", "pboc": "人民币汇率中间价",
           "market": "市场汇率", "customs": "海关计征汇率"}
    _b0 = str(inputs.get("rates", {}).get("basis") or "bank").strip()
    _b0 = _bm.get(_b0, _b0 if _b0 in _bm.values() else "银行实际购汇价")
    ws.write(r, 1, _b0, F["in_txt"])
    basis_cell = cell_addr(r, 1)
    ws.data_validation(r, 1, r, 1, {"validate": "list",
                                    "source": list(_bm.values())})
    ws.write(r, 2, "", F["lab"])
    ws.write(r, 3, "下拉选择。进口付汇的实际付款以「银行实际购汇价」为准。", F["lab"])
    ws.write(r, 4, "设置", F["lab"])
    r_basis_sel = r
    r += 1
    ws.write(r, 0, "基准汇率（CNY per FC）", F["lab_b"])
    ws.write_formula(r, 1, f'=IF({basis_cell}="银行实际购汇价",$B${r_b+3},IF({basis_cell}="人民币汇率中间价",$B${r_b+2},IF({basis_cell}="市场汇率",$B${r_b+1},$B${r_b+4})))',
                     F["tot"], E.num(rates.get("bank")))
    ws.write(r, 2, "CNY/FC", F["lab"])
    ws.write(r, 3, "= INDEX(四口径汇率, MATCH(所选口径, 口径名, 0))", F["fml"])
    ws.write(r, 4, "计算", F["lab"])
    RATE = cell_addr(r, 1)
    r += 1
    ws.write(r, 0, "银行购汇价相对中间价升水", F["lab_b"])
    ws.write_formula(r, 1, f'=IF({RK["人民币汇率中间价（PBOC/CFETS）"]}=0,0,{RK["银行实际购汇价（现汇卖出价）"]}/{RK["人民币汇率中间价（PBOC/CFETS）"]}-1)',
                     F["pct"], 0)
    ws.write(r, 2, "bp", F["lab"])
    ws.write(r, 3, "= 银行购汇价 ÷ 中间价 − 1", F["fml"])
    ws.write(r, 4, "计算", F["lab"])

    r += 2
    r = sec(ws, r, "C. 到厂成本参数", 5)
    r = hdr(ws, r, ["项目", "数值", "单位", "说明", "性质"])
    CP = {}
    cost_rows = [
        ("国际运费（外币）", E.num(costs.get("freight_fc")) or 0, ccy, "CFR/CIF 已含则填 0", "sim"),
        ("保险费（外币）", E.num(costs.get("insurance_fc")) or 0, ccy, "", "sim"),
        ("其他外币费用", E.num(costs.get("other_fc")) or 0, ccy, "", "sim"),
        ("港杂费", E.num(costs.get("cny_port")) or 0, "CNY", "与汇率无关", "sim"),
        ("报关代理费", E.num(costs.get("cny_customs_agent")) or 0, "CNY", "与汇率无关", "sim"),
        ("内陆运输费", E.num(costs.get("cny_inland")) or 0, "CNY", "与汇率无关", "sim"),
        ("仓储及其他人民币费用", (E.num(costs.get("cny_storage")) or 0) + (E.num(costs.get("cny_other")) or 0), "CNY", "与汇率无关", "sim"),
        ("银行手续费及汇兑费用", E.num(costs.get("cny_bank_fee")) or 0, "CNY", "与汇率无关", "sim"),
        ("进口关税率", (E.num(costs.get("duty_rate")) or 0) / 100.0, "%", "乙二醇 2905310000 最惠国 5.5%（无暂定税率）", "real"),
        ("消费税税率", (E.num(costs.get("cdc_rate")) or 0) / 100.0, "%", "MEG 为 0", "real"),
        ("增值税率", (E.num(costs.get("vat_rate")) if E.num(costs.get("vat_rate")) is not None else 13.0) / 100.0, "%", "标准税率 13%", "real"),
    ]
    for name, val, unit, note, kind in cost_rows:
        ws.write(r, 0, name, F["lab_b"]); ws._rowlab[name] = r
        ws.write_number(r, 1, val, F["pct"] if unit == "%" else F["in_num"])
        ws.write(r, 2, unit, F["lab"])
        ws.write(r, 3, note, F["lab"])
        ws.write(r, 4, {"real": "真实", "sim": "模拟", "demo": "演示"}[kind], F["real"] if kind == "real" else F["sim"])
        CP[name] = cell_addr(r, 1)
        r += 1
    # 增值税口径（下拉）
    ws.write(r, 0, "增值税口径", F["lab_b"])
    ws.write(r, 1, costs.get("vat_mode") or "deductible", F["in_txt"])
    ws.data_validation(r, 1, r, 1, {"validate": "list", "source": ["deductible", "cost"]})
    ws.write(r, 2, "", F["lab"])
    ws.write(r, 3, "deductible=可抵扣（不计入成本）；cost=不可抵扣（计入成本）", F["lab"])
    ws.write(r, 4, "设置", F["lab"])
    VATMODE = cell_addr(r, 1)
    r += 2

    r = sec(ws, r, "D. 国内销售与毛利参数（可选）", 5)
    r = hdr(ws, r, ["项目", "数值", "单位", "说明", "性质"])
    SP = {}
    _tm = list(sales.get("target_margins_pct") or [0, 5, 10])
    while len(_tm) < 3:
        _tm.append(10.0)
    sp_rows = [
        ("国内销售价", E.num(sales.get("price_cny")), "元/吨", sales.get("price_note", ""), "sim"),
        ("非汇率相关单位成本", E.num(sales.get("other_cost_cny_unit")), "元/吨", sales.get("other_cost_note", "仓储/销售费用/资金占用等"), "sim"),
        ("目标毛利率 1", float(_tm[0]) / 100.0, "%", "用于盈亏平衡汇率", "sim"),
        ("目标毛利率 2", float(_tm[1]) / 100.0, "%", "", "sim"),
        ("目标毛利率 3", float(_tm[2]) / 100.0, "%", "", "sim"),
    ]
    for name, val, unit, note, kind in sp_rows:
        ws.write(r, 0, name, F["lab_b"]); ws._rowlab[name] = r
        if unit == "%":
            ws.write_number(r, 1, val if val is not None else 0, F["in_pct"])
        elif val is not None:
            ws.write_number(r, 1, val, F["in_num"])
        else:
            ws.write(r, 1, "", F["in_txt"])
        ws.write(r, 2, unit, F["lab"])
        ws.write(r, 3, note, F["lab"])
        ws.write(r, 4, "模拟", F["sim"])
        SP[name] = cell_addr(r, 1)
        r += 1
    ws.write(r, 0, "销售价是否含增值税", F["lab_b"])
    ws.write(r, 1, sales.get("revenue_basis") or "tax_included", F["in_txt"])
    ws.data_validation(r, 1, r, 1, {"validate": "list", "source": ["tax_included", "tax_excluded"]})
    ws.write(r, 2, "", F["lab"])
    ws.write(r, 3, "tax_included=含税价，需 ÷(1+增值税率) 换算不含税收入", F["lab"])
    ws.write(r, 4, "设置", F["lab"])
    REVBASIS = cell_addr(r, 1)
    r += 2

    r = sec(ws, r, "E. 分批付款条件", 5)
    r = hdr(ws, r, ["批次", "付款比例", "距基准日天数", "已锁定汇率（空=随行就市）", "说明"])
    TR_START = r
    for i in range(2):
        t = trs[i] if i < len(trs) else {"pct": 0.0}
        ws.write(r, 0, t.get("name") or f"第 {i+1} 批", F["in_txt"])
        ws.write_number(r, 1, E.num(t.get("pct")) or 0.0, F["in_num"])
        ws.write_number(r, 2, E.num(t.get("days")) or 0, F["in_num"])
        ov = E.num(t.get("rate_override"))
        if ov is not None:
            ws.write_number(r, 3, ov, F["in_num"])
        else:
            ws.write_blank(r, 3, None, F["in_num"])
        ws.write(r, 4, "已锁定则该批不随情景变动", F["lab"])
        r += 1
    ws.write(r, 0, "比例合计（应为 100%）", F["lab_b"])
    ws.write_formula(r, 1, f"=SUM(B{TR_START+1}:B{TR_START+2})", F["tot"])
    ws.write(r, 2, "", F["lab"])
    ws.write_formula(r, 3, f'=IF(ABS(B{r+1}-1)<0.000001,"✔ 比例正确","✘ 比例不等于100%")', F["lab"])
    ws.write(r, 4, "校验", F["lab"])
    TOT_PCT = cell_addr(r, 1)
    r += 1
    ws.write(r, 0, "付款基准日", F["lab_b"])
    ws.write(r, 1, pay.get("payment_date") or "", F["in_txt"])
    ws.write(r, 2, "", F["lab"])
    ws.write(r, 3, "行内结果表的日期仅用于展示，实际结算日以合同为准", F["lab"])
    ws.write(r, 4, "设置", F["lab"])
    PAYDATE = cell_addr(r, 1)
    r += 2

    ws.write(r, 0, "【口径提示】", F["lab_b"])
    ws.merge_range(r, 1, r + 2, 4,
                   "1) 市场汇率（ECB）与人民币汇率中间价（CFETS/PBOC）用于观察与参考；\n"
                   "2) 银行实际购汇价（现汇卖出价）决定企业实际支付的人民币金额；\n"
                   "3) 海关计征汇率只用于折算完税价格与计税，依法取上一个月第三个星期三中间价；\n"
                   "4) 三者不可互相替代，差额可能达数十个基点。", F["note"])
    ws.set_row(r, 15); ws.set_row(r + 1, 15); ws.set_row(r + 2, 15)

    ws.freeze_panes(4, 0)

    # ============================================================ 02 付款额与敏感性
    ws = wb.add_worksheet("02 付款额与敏感性")
    ws._fmts = F
    ws.set_column(0, 0, 30); ws.set_column(1, 7, 17); ws.set_column(8, 8, 48)
    ws.write(0, 0, "02 人民币付款额与汇率敏感性", F["title"])
    ws.write(1, 0, "方向关系：汇率 x 上升 = 外币升值/人民币贬值 → 付汇人民币增加（红色）；x 下降 = 人民币升值 → 减少（绿色）。", F["sub"])
    r = 3
    r = sec(ws, r, "核心结果", 9)
    r = hdr(ws, r, ["项目", "数值", "", "", "", "", "", "", "公式 / 说明"])
    def kv(label, formula, fmt, note, bold=False):
        nonlocal r
        ws.write(r, 0, label, F["lab_b"] if bold else F["lab"])
        ws.write_formula(r, 1, formula, fmt)
        ws.merge_range(r, 2, r, 7, "", F["lab"])
        ws.write(r, 8, note, F["fml"])
        r += 1
    P1 = "'01 参数与汇率'!"
    kv("采购金额（外币）", f"={P1}{A['采购金额（外币）']}", F["num0"], "= 01!B4 录入值", True)
    AMT_CELL = cell_addr(r - 1, 1)
    kv("基准汇率（CNY/FC）", f"={P1}{RATE}", F["rate"], "= 01 表按所选口径取值（中英文标签 IF 分支）", True)
    RATE_CELL = cell_addr(r - 1, 1)
    # 跨表引用必须带表名前缀：03/04/05 表引用 02 表的付款额与基准汇率
    S2 = "'02 付款额与敏感性'!"
    AMT_X = S2 + AMT_CELL
    RATE_X = S2 + RATE_CELL
    kv("人民币付款额（基准）", f"={AMT_CELL}*{RATE_CELL}", F["tot"], "= 外币金额 × 汇率", True)
    BASE_CELL = S2 + cell_addr(r - 1, 1)
    r += 1

    r = sec(ws, r, "汇率敏感性（±1% / ±3% / ±5%，可自行增删行）", 9)
    r = hdr(ws, r, ["汇率变动", "新汇率", "人民币付款额", "变动额", "变动幅度", "方向判定", "", "", "公式"])
    SENS_START = r
    BASE_X = SENS_START + 1 + 3          # 0% 那一行的 Excel 行号（-5,-3,-1,0 → 第 4 行）
    for p in [-0.05, -0.03, -0.01, 0.0, 0.01, 0.03, 0.05]:
        x = r + 1                        # Excel 行号 = 0-based 索引 + 1
        ws.write_number(r, 0, p, F["pct1"])
        ws.write_formula(r, 1, f"={RATE_CELL}*(1+A{x})", F["rate"])
        ws.write_formula(r, 2, f"={AMT_CELL}*B{x}", F["num0"])
        ws.write_formula(r, 3, f"=C{x}-C${BASE_X}", F["up0"])
        ws.write_formula(r, 4, f"=IF(C${BASE_X}=0,0,C{x}/C${BASE_X}-1)", F["pct"])
        ws.write_formula(r, 5, f'=IF(A{x}>0,"人民币贬值·成本↑",IF(A{x}<0,"人民币升值·成本↓","基准情景"))', F["lab"])
        ws.merge_range(r, 6, r, 7, "", F["lab"])
        ws.write(r, 8, f"= 金额 × 汇率 ×(1+变动率)；行内变动额相对 0% 行", F["fml"])
        r += 1
    SENS_END = r - 1
    r += 1

    r = sec(ws, r, "四类汇率口径对照（同一笔付款）", 9)
    r = hdr(ws, r, ["口径", "汇率", "日期", "人民币付款", "相对基准差额", "相对基准%", "", "", "说明"])
    CB = r
    for i, (nm, key, dkey) in enumerate([
        ("市场汇率", "市场汇率", "market_date"),
        ("人民币汇率中间价", "人民币汇率中间价（PBOC/CFETS）", "pboc_date"),
        ("银行实际购汇价", "银行实际购汇价（现汇卖出价）", "bank_date"),
        ("海关计征汇率", "海关计征汇率", "customs_date"),
    ]):
        ws.write(r, 0, nm, F["lab_b"])
        ws.write_formula(r, 1, f"={P1}{RK[key]}", F["rate"])
        ws.write(r, 2, str(rates.get(dkey) or ""), F["lab"])
        ws.write_formula(r, 3, f"={AMT_CELL}*B{r+1}", F["num0"])
        ws.write_formula(r, 4, f"=D{r+1}-${BASE_CELL}", F["up0"])
        ws.write_formula(r, 5, f"=IF(${BASE_CELL}=0,0,D{r+1}/${BASE_CELL}-1)", F["pct"])
        ws.merge_range(r, 6, r, 7, "", F["lab"])
        ws.write(r, 8, "海关计征汇率仅用于计税，不代表实际付款价", F["fml"] if i == 3 else "")
        r += 1
    r += 1
    ws.merge_range(r, 0, r + 1, 8,
                   "提醒：中间价、市场汇率、银行购汇价、海关计征汇率是四个不同概念。进口付汇的真实人民币支出由银行购汇价决定；"
                   "海关计征汇率为上月第三个星期三中间价（海关总署令第272号第十三条），只用于完税价格折算。", F["note"])

    # ============================================================ 03 到厂成本
    ws = wb.add_worksheet("03 到厂成本")
    ws._fmts = F
    ws.set_column(0, 0, 34); ws.set_column(1, 6, 17); ws.set_column(7, 7, 52)
    ws.write(0, 0, "03 人民币到厂成本构成", F["title"])
    ws.write(1, 0, "完税价格按海关计征汇率折算；增值税按 01 表所选口径决定是否计入成本。", F["sub"])
    r = 3
    r = sec(ws, r, "成本构成（基准汇率情景）", 8)
    r = hdr(ws, r, ["成本项", "金额（元）", "计算依据", "占合计", "", "", "", "公式"])
    C_START = r
    items = [
        ("货值（外币×汇率）", f"={AMT_X}*{RATE_X}", "外币金额 × 基准汇率"),
        ("国际运费（外币×汇率）", f"={P1}{CP['国际运费（外币）']}*{RATE_X}", "外币运费 × 基准汇率"),
        ("保险费（外币×汇率）", f"={P1}{CP['保险费（外币）']}*{RATE_X}", "外币保费 × 基准汇率"),
        ("其他外币费用（×汇率）", f"={P1}{CP['其他外币费用']}*{RATE_X}", "外币费用 × 基准汇率"),
    ]
    # 行布局（0-based 索引）：
    #   C_START .. C_START+3         四项外币金额
    #   C_START+4                    完税价格
    #   C_START+5                    关税
    #   C_START+6                    消费税
    #   C_START+7                    增值税
    #   C_START+8                    增值税计入成本
    #   C_START+9                    人民币固定费用
    #   C_START+10                   到厂成本合计   ← 占比分母
    R_DV, R_DUTY, R_CDC, R_VAT = C_START + 4, C_START + 5, C_START + 6, C_START + 7
    R_VATIN, R_NONFX, R_TOTAL = C_START + 8, C_START + 9, C_START + 10
    TOTAL_ROW_X = R_TOTAL + 1          # Excel 行号形式

    def share(row_idx):
        """“占合计”列：本行金额 ÷ 到厂成本合计。"""
        return f"=IF($B${TOTAL_ROW_X}=0,0,B{row_idx+1}/$B${TOTAL_ROW_X})"

    for lab, fm, note in items:
        ws.write(r, 0, lab, F["lab"])
        ws.write_formula(r, 1, fm, F["num"])
        ws.write(r, 2, note, F["lab"])
        ws.write_formula(r, 3, share(r), F["pct"])
        ws.merge_range(r, 4, r, 6, "", F["lab"])
        ws.write(r, 7, fm, F["fml"])
        r += 1
    FOB = cell_addr(C_START, 1)

    # 完税价格
    ws.write(R_DV, 0, "海关完税价格（CIF×计征汇率）", F["lab_b"])
    ws.write_formula(R_DV, 1,
                     f"=SUM(B{C_START+1}:B{C_START+4})/{RATE_X}*{P1}{RK['海关计征汇率']}", F["num"])
    ws.write(R_DV, 2, "(货值+运+保+其他外币费用)×计征汇率", F["lab"])
    ws.write_formula(R_DV, 3, share(R_DV), F["pct"])
    ws.merge_range(R_DV, 4, R_DV, 6, "", F["lab"])
    ws.write(R_DV, 7, "= (CIF 外币合计) ÷ 基准汇率 × 计征汇率", F["fml"])
    DV = cell_addr(R_DV, 1)

    # 关税
    ws.write(R_DUTY, 0, "进口关税", F["lab_b"])
    ws.write_formula(R_DUTY, 1, f"={DV}*{P1}{CP['进口关税率']}", F["num"])
    ws.write(R_DUTY, 2, "完税价格 × 关税率", F["lab"])
    ws.write_formula(R_DUTY, 3, share(R_DUTY), F["pct"])
    ws.merge_range(R_DUTY, 4, R_DUTY, 6, "", F["lab"])
    ws.write(R_DUTY, 7, "= 完税价格 × 关税率", F["fml"])
    DUTY = cell_addr(R_DUTY, 1)

    # 消费税
    ws.write(R_CDC, 0, "消费税", F["lab_b"])
    ws.write_formula(R_CDC, 1, f"={DV}*{P1}{CP['消费税税率']}", F["num"])
    ws.write(R_CDC, 2, "完税价格 × 消费税率", F["lab"])
    ws.write_formula(R_CDC, 3, share(R_CDC), F["pct"])
    ws.merge_range(R_CDC, 4, R_CDC, 6, "", F["lab"])
    ws.write(R_CDC, 7, "= 完税价格 × 消费税率", F["fml"])
    CDC = cell_addr(R_CDC, 1)

    # 进口增值税（计税用）
    ws.write(R_VAT, 0, "进口增值税（计税用）", F["lab_b"])
    ws.write_formula(R_VAT, 1, f"=({DV}+{DUTY}+{CDC})*{P1}{CP['增值税率']}", F["num"])
    ws.write(R_VAT, 2, "(完税价格+关税+消费税)×增值税率", F["lab"])
    ws.write_formula(R_VAT, 3, share(R_VAT), F["pct"])
    ws.merge_range(R_VAT, 4, R_VAT, 6, "", F["lab"])
    ws.write(R_VAT, 7, "= (完税价格+关税+消费税) × 增值税率", F["fml"])
    VAT = cell_addr(R_VAT, 1)

    # 增值税计入成本金额
    ws.write(R_VATIN, 0, "增值税计入成本金额", F["lab_b"])
    ws.write_formula(R_VATIN, 1, f'=IF({P1}{VATMODE}="cost",{VAT},0)', F["num"])
    ws.write(R_VATIN, 2, "可抵扣 → 0；不可抵扣 → 全额计入", F["lab"])
    ws.write_formula(R_VATIN, 3, share(R_VATIN), F["pct"])
    ws.merge_range(R_VATIN, 4, R_VATIN, 6, "", F["lab"])
    ws.write(R_VATIN, 7, '= IF(增值税口径="cost", 增值税, 0)', F["fml"])
    VATIN = cell_addr(R_VATIN, 1)

    # 人民币固定费用
    ws.write(R_NONFX, 0, "人民币固定费用合计", F["lab_b"])
    ws.write_formula(R_NONFX, 1,
                     f"={P1}{CP['港杂费']}+{P1}{CP['报关代理费']}+{P1}{CP['内陆运输费']}"
                     f"+{P1}{CP['仓储及其他人民币费用']}+{P1}{CP['银行手续费及汇兑费用']}", F["num"])
    ws.write(R_NONFX, 2, "港杂+代理+内陆+仓储+银行手续费", F["lab"])
    ws.write_formula(R_NONFX, 3, share(R_NONFX), F["pct"])
    ws.merge_range(R_NONFX, 4, R_NONFX, 6, "", F["lab"])
    ws.write(R_NONFX, 7, "= 各项人民币费用之和（与汇率无关）", F["fml"])
    NONFX = cell_addr(R_NONFX, 1)

    # 到厂成本合计
    ws.write(R_TOTAL, 0, "人民币到厂成本合计", F["tot_lab"])
    ws.write_formula(R_TOTAL, 1,
                     f"={FOB}+B{C_START+2}+B{C_START+3}+B{C_START+4}"
                     f"+{DUTY}+{CDC}+{VATIN}+{NONFX}", F["tot"])
    ws.write(R_TOTAL, 2, "各项之和", F["tot_lab"])
    ws.write_formula(R_TOTAL, 3, "=1", F["pct"])
    ws.merge_range(R_TOTAL, 4, R_TOTAL, 6, "", F["tot_lab"])
    ws.write(R_TOTAL, 7, "= 货值+运费+保费+其他+关税+消费税+增值税(入成本)+人民币费用", F["fml"])
    TOTAL = cell_addr(R_TOTAL, 1)
    r = R_TOTAL + 1

    ws.write(r, 0, "折合单位到厂成本（元/吨）", F["lab_b"])
    ws.write_formula(r, 1, f'=IF({P1}{A["合同数量"]}=0,0,{TOTAL}/{P1}{A["合同数量"]})', F["num"])
    ws.write(r, 2, "合计 ÷ 数量", F["lab"])
    ws.merge_range(r, 3, r, 6, "", F["lab"])
    ws.write(r, 7, "= 到厂成本合计 ÷ 合同数量", F["fml"])
    UNIT = cell_addr(r, 1)
    r += 1
    ws.write(r, 0, "汇率相关成本占比", F["lab_b"])
    ws.write_formula(r, 1,
                     f'=IF({TOTAL}=0,0,({FOB}+B{C_START+2}+B{C_START+3}+B{C_START+4}'
                     f"+{DUTY}+{CDC}+{VATIN})/{TOTAL})", F["pct"])
    ws.write(r, 2, "汇率相关 ÷ 合计", F["lab"])
    ws.merge_range(r, 3, r, 6, "", F["lab"])
    ws.write(r, 7, "= (汇率相关成本) ÷ 合计；其余为人民币固定费用，稀释了敏感性", F["fml"])
    FXSHARE = cell_addr(r, 1)
    r += 2

    r = sec(ws, r, "到厂成本汇率敏感性", 8)
    r = hdr(ws, r, ["汇率变动", "新汇率", "货值（人民币）", "关税", "到厂成本", "变动额", "变动幅度", "公式"])
    LS = r
    for i, p in enumerate([-0.05, -0.03, -0.01, 0.0, 0.01, 0.03, 0.05]):
        ws.write_number(r, 0, p, F["pct1"])
        ws.write_formula(r, 1, f"={RATE_X}*(1+A{r+1})", F["rate"])
        ws.write_formula(r, 2, f"={AMT_X}*B{r+1}", F["num0"])
        # 关税按同比例变动（计征汇率随行情同步变动）
        ws.write_formula(r, 3, f"={DUTY}*B{r+1}/{RATE_X}", F["num0"])
        # 到厂成本：汇率相关部分按比例缩放 + 固定费用
        ws.write_formula(r, 4, f"={TOTAL}*{FXSHARE}*B{r+1}/{RATE_X}+{TOTAL}*(1-{FXSHARE})", F["num0"])
        ws.write_formula(r, 5, f"=E{r+1}-E${LS+1+3}", F["up0"])
        ws.write_formula(r, 6, f"=IF(E${LS+1+3}=0,0,E{r+1}/E${LS+1+3}-1)", F["pct"])
        ws.write(r, 7, "成本=汇率相关部分×(1+Δ%)+固定费用" if i == 0 else "", F["fml"])
        r += 1
    r += 1
    ws.merge_range(r, 0, r + 1, 7,
                   "说明：到厂成本的敏感性小于纯付汇金额的敏感性，因为港杂、内陆运费、代理费等人民币费用不随汇率变动。"
                   "本表假设海关计征汇率与市场同步按比例变动；若申报月份计征汇率已锁定，应以实际计征汇率重算。", F["note"])

    # 供 04 表复用的 03 表列/行坐标
    LC_COLS = dict(C_START=C_START, FOB=FOB, DUTY=DUTY, CDC=CDC,
                   VATIN=VATIN, NONFX=NONFX, RATE_X=RATE_X)

    # ============================================================ 04 毛利与盈亏平衡
    ws = wb.add_worksheet("04 毛利与盈亏平衡")
    ws._fmts = F
    ws.set_column(0, 0, 32); ws.set_column(1, 7, 17); ws.set_column(8, 8, 50)
    ws.write(0, 0, "04 毛利测算与盈亏平衡汇率", F["title"])
    ws.write(1, 0, "仅在销售价、数量、非汇率成本齐备时有效；缺少任一，本表结果将显示为无效值而非臆造利润。", F["sub"])
    r = 3
    r = sec(ws, r, "毛利构成（基准汇率）", 9)
    r = hdr(ws, r, ["项目", "数值", "单位", "", "", "", "", "", "公式"])
    def row_kv(label, fm, fmt, unit, note):
        nonlocal r
        ws.write(r, 0, label, F["lab_b"])
        ws.write_formula(r, 1, fm, fmt)
        ws.write(r, 2, unit, F["lab"])
        ws.merge_range(r, 3, r, 7, "", F["lab"])
        ws.write(r, 8, note, F["fml"])
        r += 1
    Q3 = "'03 到厂成本'!"
    row_kv("合同数量（吨）", f"={P1}{A['合同数量']}", F["num"], "吨", "来自 01 表")
    QTY = cell_addr(r - 1, 1)
    row_kv("国内销售价", f"={P1}{SP['国内销售价']}", F["num"], "元/吨", "模拟值，须替换为实际售价")
    PRICE = cell_addr(r - 1, 1)
    row_kv("不含税售价", f'=IF({P1}{REVBASIS}="tax_included",{PRICE}/(1+{P1}{CP["增值税率"]}),{PRICE})', F["num"], "元/吨", "含税价 ÷(1+增值税率)")
    PRICE_EX = cell_addr(r - 1, 1)
    row_kv("不含税销售收入", f"={PRICE_EX}*{QTY}", F["tot"], "元", "不含税售价 × 数量")
    REV = cell_addr(r - 1, 1)
    row_kv("到厂成本", f"={Q3}{TOTAL}", F["num"], "元", "来自 03 表")
    LC = cell_addr(r - 1, 1)
    row_kv("非汇率相关成本", f"={P1}{SP['非汇率相关单位成本']}*{QTY}", F["num"], "元", "单位成本 × 数量")
    OC = cell_addr(r - 1, 1)
    row_kv("总成本", f"={LC}+{OC}", F["num"], "元", "到厂成本 + 非汇率成本")
    TC = cell_addr(r - 1, 1)
    row_kv("毛利额", f"={REV}-{TC}", F["tot"], "元", "不含税收入 − 总成本")
    GP = cell_addr(r - 1, 1)
    row_kv("毛利率", f"=IF({REV}=0,0,{GP}/{REV})", F["tot"], "%", "毛利额 ÷ 不含税收入")
    GMP = cell_addr(r - 1, 1)
    r += 1

    r = sec(ws, r, "不同汇率下的毛利", 9)
    r = hdr(ws, r, ["汇率变动", "新汇率", "到厂成本", "总成本", "毛利额", "毛利率", "", "", "公式"])
    MS = r
    for p in [-0.05, -0.03, -0.01, 0.0, 0.01, 0.03, 0.05]:
        ws.write_number(r, 0, p, F["pct1"])
        ws.write_formula(r, 1, f"={RATE_X}*(1+A{r+1})", F["rate"])
        ws.write_formula(r, 2, f"={LC}*{FXSHARE}*B{r+1}/{RATE_X}+{LC}*(1-{FXSHARE})", F["num0"])
        ws.write_formula(r, 3, f"=C{r+1}+{OC}", F["num0"])
        ws.write_formula(r, 4, f"={REV}-D{r+1}", F["up0"])
        ws.write_formula(r, 5, f"=IF({REV}=0,0,E{r+1}/{REV})", F["pct"])
        ws.merge_range(r, 6, r, 7, "", F["lab"])
        ws.write(r, 8, "成本 = 到厂汇率相关部分×(1+Δ%) + 固定部分 + 非汇率成本" if p == -0.05 else "", F["fml"])
        r += 1
    r += 1

    r = sec(ws, r, "盈亏平衡汇率（毛利降至目标水平时的汇率）", 9)
    r = hdr(ws, r, ["目标毛利率", "λ*", "平衡汇率", "相对当前变动", "汇率缓冲空间（元）", "适用性", "", "", "公式"])
    BE = r
    # 与引擎 breakeven_rate(other_fixed_cny=oc) 完全同口径：
    #   FX0 = 到厂成本中的汇率相关部分（货值+运+保+其他外币费用+关税+消费税+增值税入成本）
    #   NF  = (到厂成本 − FX0) + 非汇率相关成本 OC
    #   λ*  = [R0·(1−m) − NF] / FX0
    _c3 = LC_COLS
    FX0 = (f"({Q3}{_c3['FOB']}+{Q3}B{_c3['C_START']+2}+{Q3}B{_c3['C_START']+3}"
           f"+{Q3}B{_c3['C_START']+4}+{Q3}{_c3['DUTY']}+{Q3}{_c3['CDC']}+{Q3}{_c3['VATIN']})")
    NF = f"(({LC}-{FX0})+{OC})"
    for k, key in enumerate(["目标毛利率 1", "目标毛利率 2", "目标毛利率 3"]):
        ws.write_formula(r, 0, f"={P1}{SP[key]}", F["pct1"])
        # λ* = [R0·(1−m) − NF] / FX0
        # 适用性门槛：基准毛利率必须 ≥ 目标毛利率，否则“汇率涨到多少跌破目标”无商业含义 → 留空
        ws.write_formula(r, 1,
                         f'=IF(OR({FX0}<=0,{GMP}<A{r+1},({REV}*(1-A{r+1})-{NF})<=0),"",'
                         f'({REV}*(1-A{r+1})-{NF})/{FX0})', F["num"])
        ws.write_formula(r, 2, f'=IF(ISNUMBER(B{r+1}),{RATE_X}*B{r+1},"")', F["rate"])
        ws.write_formula(r, 3, f'=IF(ISNUMBER(B{r+1}),B{r+1}-1,"")', F["pct"])
        ws.write_formula(r, 4, f'=IF(ISNUMBER(B{r+1}),(B{r+1}-1)*{FX0},"")', F["up0"])
        ws.write_formula(r, 5, f'=IF({GMP}<A{r+1},"不适用：基准毛利率已低于目标","适用")', F["lab"])
        ws.merge_range(r, 6, r, 7, "", F["lab"])
        ws.write(r, 8, "λ*=[R0(1−m)−NF]÷FX0；平衡汇率=基准汇率×λ*", F["fml"] if k == 0 else "")
        r += 1
    r += 1
    ws.merge_range(r, 0, r + 2, 8,
                   "解读：平衡汇率表示“在当前销售价与成本结构下，汇率升到多少会把毛利压到目标水平”，用于评估风险敞口大小。\n"
                   "它不是汇率预测，也不代表汇率会走到该位置。λ*<1 表示当前已不达标；‘不适用’表示基准毛利率已低于目标。", F["note"])

    # ============================================================ 05 分批付款
    ws = wb.add_worksheet("05 分批付款")
    ws._fmts = F
    ws.set_column(0, 0, 30); ws.set_column(1, 10, 15); ws.set_column(11, 11, 46)
    ws.write(0, 0, "05 分批付款汇率敏感性", F["title"])
    ws.write(1, 0, "各批次按 01 表比例与锁定情况分别计价；锁定批次不随情景变动。", F["sub"])
    r = 3
    r = sec(ws, r, "分批明细（基准情景）", 12)
    r = hdr(ws, r, ["批次", "比例", "外币金额", "已锁汇率", "基准人民币", "结算日", "", "", "", "", "", "公式"])
    T_START = r
    for i in range(2):
        rr = TR_START + i  # 01 表对应行(0-based)
        ws.write_formula(r, 0, f'={P1}A{rr+1}', F["lab"])
        ws.write_formula(r, 1, f"={P1}B{rr+1}", F["pct1"])
        ws.write_formula(r, 2, f"={AMT_X}*B{r+1}", F["num0"])
        ws.write_formula(r, 3, f'=IF({P1}D{rr+1}="",{RATE_X},{P1}D{rr+1})', F["rate"])
        ws.write_formula(r, 4, f"=C{r+1}*D{r+1}", F["num0"])
        ws.write_formula(r, 5, f'=IF({P1}{PAYDATE}="","",TEXT({P1}{PAYDATE}+{P1}C{rr+1},"yyyy-mm-dd"))', F["lab"])
        ws.merge_range(r, 6, r, 10, "", F["lab"])
        ws.write(r, 11, "外币金额=总额×比例；人民币=外币金额×该批汇率(锁定值或基准)", F["fml"] if i == 0 else "")
        r += 1
    ws.write(r, 0, "合计", F["tot_lab"])
    ws.write_formula(r, 1, f"=SUM(B{T_START+1}:B{T_START+2})", F["tot"])
    ws.write_formula(r, 2, f"=SUM(C{T_START+1}:C{T_START+2})", F["tot"])
    ws.write(r, 3, "", F["tot"])
    ws.write_formula(r, 4, f"=SUM(E{T_START+1}:E{T_START+2})", F["tot"])
    ws.merge_range(r, 5, r, 10, "", F["tot"])
    ws.write(r, 11, "=SUM(各批次)", F["fml"])
    TBASE = cell_addr(r, 4)
    r += 2

    r = sec(ws, r, "情景矩阵（汇率整体变动 Δ% 下的各批人民币金额）", 12)
    r = hdr(ws, r, ["汇率变动", "新汇率", "预付款人民币", "尾款人民币", "合计", "相对基准变动", "变动幅度", "", "", "", "", "公式"])
    TS = r
    for p in [-0.05, -0.03, -0.01, 0.0, 0.01, 0.03, 0.05]:
        ws.write_number(r, 0, p, F["pct1"])
        ws.write_formula(r, 1, f"={RATE_X}*(1+A{r+1})", F["rate"])
        # 已锁批次用锁定价，未锁批次用情景价
        ws.write_formula(r, 2, f'=C{T_START+1}*IF({P1}D{TR_START+1}="",B{r+1},{P1}D{TR_START+1})', F["num0"])
        ws.write_formula(r, 3, f'=C{T_START+2}*IF({P1}D{TR_START+2}="",B{r+1},{P1}D{TR_START+2})', F["num0"])
        ws.write_formula(r, 4, f"=C{r+1}+D{r+1}", F["num0"])
        ws.write_formula(r, 5, f"=E{r+1}-${TBASE}", F["up0"])
        ws.write_formula(r, 6, f"=IF(${TBASE}=0,0,E{r+1}/${TBASE}-1)", F["pct"])
        ws.merge_range(r, 7, r, 10, "", F["lab"])
        ws.write(r, 11, "锁定批次取锁定价，其余取情景价" if p == -0.05 else "", F["fml"])
        r += 1
    r += 1
    ws.merge_range(r, 0, r + 1, 11,
                   "提示：把某批“已锁汇率”填入 01 表 D 列后，该批在情景矩阵中不再变化，可直观看到部分锁定如何降低整体敏感度。"
                   "本表仅测算不同结算时点的汇率敞口大小，不涉及任何外汇衍生品选择或交易建议。", F["note"])

    # ============================================================ 06 历史汇率与分位
    ws = wb.add_worksheet("06 历史汇率与分位")
    ws._fmts = F
    ws.set_column(0, 0, 14); ws.set_column(1, 3, 16); ws.set_column(4, 8, 20)
    ws.write(0, 0, f"06 {ccy}/CNY 历史汇率与当前分位", F["title"])
    ws.write(1, 0, "数据来源：ECB 欧元参考汇率（经交叉折算）/ Frankfurter 公开接口；已与 ER-API 交叉核对。真实数据，未做任何平滑或伪造。", F["sub"])
    r = 3
    series = (history or {}).get("daily", {}).get(f"{ccy}CNY", [])
    r = sec(ws, r, "统计摘要（公式基于本表右侧日度数据区间计算）", 9)
    r = hdr(ws, r, ["区间", "起始日", "观测数", "最低", "最高", "均值", "当前中间价分位", "当前市场汇率分位", "说明"])
    dcol = 11  # L 列放“日期”，M 列放“汇率”（0-based 索引）
    if series:
        first_date = series[0][0]
        ws.write(1, dcol, "日期", F["hdr"])
        ws.write(1, dcol + 1, "汇率", F["hdr"])
        for i, (d, v) in enumerate(series):
            # 必须写成真正的日期类型，COUNTIFS/MINIFS 的日期比较才有效
            y, m_, dd = (int(x) for x in d.split("-"))
            ws.write_datetime(i + 2, dcol, date(y, m_, dd), F["date"])
            ws.write_number(i + 2, dcol + 1, v, F["rate"])
        n = len(series)
        DC = xlsxwriter.utility.xl_col_to_name(dcol)
        VC = xlsxwriter.utility.xl_col_to_name(dcol + 1)
        RNG = f"${VC}$3:${VC}${n+2}"
        dates = f"${DC}$3:${DC}${n+2}"
        today = date.fromisoformat(series[-1][0])
        for yrs in (1, 3, 5):
            cut = _minus_years(today, yrs)
            ws.write(r, 0, f"近 {yrs} 年", F["lab_b"])
            ws.write_datetime(r, 1, cut, F["date"])
            ws.write_formula(r, 2, f'=COUNTIFS({dates},">="&B{r+1})', F["num0"])
            # 最低/最高/均值：MINIFS/MAXIFS/AVERAGEIFS（Excel 2019+ / 365）
            ws.write_formula(r, 3, f'=MINIFS({RNG},{dates},">="&B{r+1})', F["rate"])
            ws.write_formula(r, 4, f'=MAXIFS({RNG},{dates},">="&B{r+1})', F["rate"])
            ws.write_formula(r, 5, f'=AVERAGEIFS({RNG},{dates},">="&B{r+1})', F["rate"])
            ws.write_formula(r, 6, f'=IF(C{r+1}=0,0,COUNTIFS({RNG},"<="&{P1}{RK["人民币汇率中间价（PBOC/CFETS）"]},{dates},">="&B{r+1})/C{r+1})', F["pct"])
            ws.write_formula(r, 7, f'=IF(C{r+1}=0,0,COUNTIFS({RNG},"<="&{P1}{RK["市场汇率"]},{dates},">="&B{r+1})/C{r+1})', F["pct"])
            ws.write(r, 8, "分位=区间内≤当前汇率的观测占比；越低说明当前外币越便宜", F["lab"])
            r += 1
        ws.write(r, 0, "全部样本", F["lab_b"])
        ws.write(r, 1, first_date, F["lab"])
        ws.write_formula(r, 2, f"=COUNT({RNG})", F["num0"])
        ws.write_formula(r, 3, f"=MIN({RNG})", F["rate"])
        ws.write_formula(r, 4, f"=MAX({RNG})", F["rate"])
        ws.write_formula(r, 5, f"=AVERAGE({RNG})", F["rate"])
        ws.write_formula(r, 6, f'=COUNTIFS({RNG},"<="&{P1}{RK["人民币汇率中间价（PBOC/CFETS）"]})/C{r+1}', F["pct"])
        ws.write_formula(r, 7, f'=COUNTIFS({RNG},"<="&{P1}{RK["市场汇率"]})/C{r+1}', F["pct"])
        ws.write(r, 8, "", F["lab"])
    r += 2
    ws.merge_range(r, 0, r + 2, 8,
                   "说明：历史分位只描述“当前汇率在这段历史中的相对位置”，不代表未来走势。"
                   "汇率可能长期停留在历史区间之外，分位低不等于汇率必然回升，分位高也不等于必然回落。", F["note"])
    ws.freeze_panes(2, 0)

    # ============================================================ 07 三口径区分
    ws = wb.add_worksheet("07 汇率口径与法规")
    ws._fmts = F
    ws.set_column(0, 0, 22); ws.set_column(1, 1, 26); ws.set_column(2, 2, 56); ws.set_column(3, 3, 46)
    ws.write(0, 0, "07 四类汇率口径区分与法规依据", F["title"])
    r = 2
    r = hdr(ws, r, ["口径", "用途", "定义与特征", "法规 / 权威依据"])
    rows7 = [
        ("市场汇率", "观察、比价、参考", "境外市场即时成交价（如 ECB 每日参考汇率、离岸价）。反映市场供需，但不等于企业结售汇成交价。",
         "欧洲央行 Euro foreign exchange reference rates"),
        ("人民币汇率中间价", "观察、定价基准", "人民银行授权中国外汇交易中心每日 9:15 公布，由做市商报价去极值加权平均形成；当日中间价适用于发布后至下一中间价发布前。",
         "《中国人民银行关于银行间外汇市场交易汇价和银行挂牌汇价管理有关事项的通知》（2014）；《银行间外汇市场管理规定》（2025年第13号令，2026-02-01 施行）"),
        ("银行实际购汇价", "决定企业真实付款", "企业进口付汇按银行「现汇卖出价」成交（银行视角的卖出）。银行间即期 CNY/USD 可在中间价上下 2% 内浮动；银行为客户提供的当日美元最高现汇卖出价与最低现汇买入价之差不得超过中间价的 3%。",
         "中国人民银行公告〔2014〕第5号；银行挂牌汇价管理规定"),
        ("海关计征汇率", "折算完税价格与计税", "每月使用的计征汇率为「上一个月第三个星期三」人民银行授权外汇交易中心公布的人民币汇率中间价；该日非交易日的，顺延下一交易日。与计征税额相关的汇率发生重大波动时海关总署可另行规定。",
         "《中华人民共和国海关进出口货物征税管理办法》（海关总署令第272号，2024-12-01 施行）第十三条"),
    ]
    for i, (a, b, c, d) in enumerate(rows7):
        ws.write(r, 0, a, F["lab_b"])
        ws.write(r, 1, b, F["lab"])
        ws.write(r, 2, c, F["lab"])
        ws.write(r, 3, d, F["lab"])
        ws.set_row(r, 52)
        r += 1
    r += 1
    r = sec(ws, r, "计征汇率基准日速查（上月第三个星期三）", 4)
    r = hdr(ws, r, ["申报月份", "适用计征汇率基准日", "说明", ""])
    today = date.today()
    for k in range(0, 6):
        y, m = today.year, today.month + k
        while m > 12:
            m -= 12; y += 1
        y2, m2 = (y - 1, 12) if m == 1 else (y, m - 1)
        d3 = E.third_wednesday(y2, m2)
        ws.write(r, 0, f"{y}-{m:02d}", F["lab_b"])
        ws.write(r, 1, d3.isoformat(), F["lab"])
        ws.write(r, 2, f"取 {y2}-{m2:02d} 第三个星期三中间价" + ("（遇非交易日顺延）" if d3.weekday() >= 5 else ""), F["lab"])
        r += 1
    r += 1
    ws.merge_range(r, 0, r + 2, 3,
                   "常见错误：\n"
                   "✗ 用市场汇率（ECB/离岸价）直接估算关税与增值税 —— 计税必须用海关计征汇率；\n"
                   "✗ 用中间价估算实际付款 —— 实际付款按银行现汇卖出价，通常高于中间价；\n"
                   "✗ 用当日中间价估算本月进口计税 —— 计征汇率取决于上月第三个星期三。", F["note"])

    wb.close()
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
