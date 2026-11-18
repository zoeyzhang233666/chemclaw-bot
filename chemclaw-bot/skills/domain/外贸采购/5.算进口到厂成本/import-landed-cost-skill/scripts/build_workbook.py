# -*- coding: utf-8 -*-
"""
build_workbook.py — 生成「进口到厂成本测算」Excel 工作簿

设计
----
* 行号由 LAYOUT 列表顺序推导，**不存在两个元素占用同一行**的情况；
* 所有派生单元格都是 Excel 公式，改参数即重算；
* 未填=空单元格，用 ISNUMBER()/COUNT() 判断 → 不会悄悄变成 0（与 Python 引擎"待确认"一致）；
* 生成后由 LibreOffice 重算，并与 Python 引擎逐项对账（verify_workbook.py）。
"""
from __future__ import annotations

import os

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "import_landed_cost_calculator.xlsx")

NAVY, TEAL = "12263A", "0E7C86"
H_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
T_FONT = Font(name="微软雅黑", size=14, bold=True, color=NAVY)
S_FONT = Font(name="微软雅黑", size=9, color="475569")
B_FONT = Font(name="微软雅黑", size=9.5, color="1F2937")
BOLD = Font(name="微软雅黑", size=9.5, bold=True, color="1F2937")
NUM = Font(name="Consolas", size=9.5, color="1F2937")
KEYF = Font(name="Consolas", size=11.5, bold=True, color=NAVY)
FILL_H = PatternFill("solid", fgColor=NAVY)
FILL_SEC = PatternFill("solid", fgColor="DDE6F0")
FILL_IN = PatternFill("solid", fgColor="FFF8E1")
FILL_CALC = PatternFill("solid", fgColor="F8FAFC")
FILL_KEY = PatternFill("solid", fgColor="E8F1F2")
FILL_WARN = PatternFill("solid", fgColor="FEE2E2")
FILL_OK = PatternFill("solid", fgColor="DCFCE7")
_th = Side(style="thin", color="CBD5E1")
BOX = Border(left=_th, right=_th, top=_th, bottom=_th)
M, MQ, P4 = '#,##0.00', '#,##0.000', '0.0000%'

CASES = [("FOB", "沙特朱拜勒 Al Jubail"), ("CFR", "中国宁波"), ("CIF", "中国宁波")]

# 每行配置：kind ∈ sec / info / kv；kv 的 value 若以 "=" 开头则按公式处理，其中 {key} 会替换为 C行号
LAYOUT = [
    ("sec", {"text": "① 商品与交易信息"}),
    ("info", {}), ("info", {}), ("info", {}),
    ("sec", {"text": "② 报价与费用参数（黄色=可改，白色=公式；未填=待确认，绝不当作 0）"}),
    ("kv", {"key": "unit_price", "label": "供应商单价（原币/计价单位）", "value": 640.00, "fmt": M,
            "note": "黄色单元格可修改", "fill": "in"}),
    ("kv", {"key": "qty", "label": "数量（吨）", "value": 62.5, "fmt": MQ,
            "note": "25×40' ISO 罐 × 25.0 吨", "fill": "in"}),
    ("kv", {"key": "price_unit", "label": "单价计价单位（MT / CONTAINER）", "value": "MT", "fmt": None,
            "note": "MT=每吨价；CONTAINER=每柜价", "fill": "in"}),
    ("kv", {"key": "pack_incl", "label": "包装是否已含于单价（TRUE/FALSE）", "value": "TRUE", "fmt": None,
            "note": "《关税法》第25条：包装费计入计税价格", "fill": "in"}),
    ("kv", {"key": "fx_m", "label": "市场参考汇率 USD/CNY", "value": 6.6807, "fmt": '0.0000',
            "note": "ECB 2026-10-19；exchangerate-api 2026-10-20=6.69", "fill": "in"}),
    ("kv", {"key": "fx_c", "label": "海关计征汇率 USD/CNY（演示占位值，须替换）", "value": 6.72,
            "fmt": '0.0000',
            "note": "演示占位 6.7200（非2026-09-16官方值）；请替换为申报日对应上月第三个星期三亚行中间价；留空=待补全", "fill": "in"}),
    ("kv", {"key": "ex_cost", "label": "出口侧费用 USD（EXW/FCA 填）", "value": None, "fmt": M,
            "note": "其余术语自动置 0", "fill": "in"}),
    ("kv", {"key": "origin_ch", "label": "起运港费用 USD（EXW/FCA 填）", "value": None, "fmt": M,
            "note": "FOB 及以上已含，自动置 0", "fill": "in"}),
    ("kv", {"key": "freight", "label": "海运费 USD/MT（报价未含时填）", "value": 45.00, "fmt": M,
            "note": "仅 FOB/EXW/FCA/FAS 需要", "fill": "in"}),
    ("kv", {"key": "freight_tot", "label": "整票海运费 USD（可选）", "value": None, "fmt": M,
            "note": "货代按整票报价时填，优先于单价", "fill": "in"}),
    ("kv", {"key": "ins_rate", "label": "保险费率 ‰", "value": 0.55, "fmt": '0.000',
            "note": "保费=(货值+运费)×费率×110%（模拟）", "fill": "in"}),
    ("kv", {"key": "ins_amt", "label": "实际保险费 USD（可选）", "value": None, "fmt": M,
            "note": "有保单时填，优先于费率", "fill": "in"}),
    ("kv", {"key": "ins_incl", "label": "保险是否已含于报价（TRUE/FALSE）", "value": "FALSE", "fmt": None,
            "note": "CIF 默认 TRUE", "fill": "in"}),
    ("kv", {"key": "pack_extra", "label": "包装费另计 USD", "value": 0, "fmt": M,
            "note": "PI 另计包装时填；已含填 0", "fill": "in"}),
    ("kv", {"key": "has_freight", "label": "报价已含海运费（按术语判定）",
            "value": '=OR("{t}"="CFR","{t}"="CIF","{t}"="CPT","{t}"="CIP","{t}"="DAP","{t}"="DPU","{t}"="DDP")',
            "fmt": None, "note": "Incoterms 2020", "fill": "calc"}),
    ("kv", {"key": "has_ins", "label": "报价已含保险费（按术语判定）",
            "value": '=OR("{t}"="CIF","{t}"="CIP","{t}"="DDP")', "fmt": None,
            "note": "Incoterms 2020", "fill": "calc"}),
    ("kv", {"key": "has_origin", "label": "报价已含起运港费用（按术语判定）",
            "value": '=NOT(OR("{t}"="EXW","{t}"="FCA"))', "fmt": None,
            "note": "EXW/FCA 不含装运港费用", "fill": "calc"}),
    ("sec", {"text": "③ 第一层：货值 → 到岸（C=原币；D=人民币，按市场参考汇率）", "teal": True}),
    ("rmb", {"key": "goods4", "label": "货值（单价×数量）",
             "value": '=IF(AND(ISNUMBER({unit_price}),ISNUMBER({qty})),{unit_price}*{qty},"")',
             "note": "整票货值（原币）"}),
    ("rmb", {"key": "goods_mt", "label": "单吨货值",
             "value": '=IF(AND(ISNUMBER({goods4}),{qty}>0),{goods4}/{qty},"")', "note": "原币/吨"}),
    ("rmb", {"key": "packing4", "label": "包装费（另计）",
             "value": '=IF({pack_incl}=TRUE,0,IF(ISNUMBER({pack_extra}),{pack_extra},""))',
             "note": "单价已含包装 → 0"}),
    ("rmb", {"key": "origin_ch4", "label": "起运港费用",
             "value": '=IF({has_origin},0,IF(ISNUMBER({origin_ch}),{origin_ch},""))', "note": "报价已含 → 0"}),
    ("rmb", {"key": "ex4", "label": "出口侧费用",
             "value": '=IF({has_origin},0,IF(ISNUMBER({ex_cost}),{ex_cost},""))', "note": "报价已含 → 0"}),
    ("rmb", {"key": "freight4", "label": "海运费（整票）",
             "value": ('=IF({has_freight},0,IF(ISNUMBER({freight_tot}),{freight_tot},'
                       'IF(AND(ISNUMBER({freight}),ISNUMBER({qty})),{freight}*{qty},"")))'),
             "note": "CFR/CIF 已含 → 0（不重复计费）"}),
    ("rmb", {"key": "ins4", "label": "保险费（实际）",
             "value": ('=IF({ins_incl},0,IF(ISNUMBER({ins_amt}),{ins_amt},'
                       'IF(AND(ISNUMBER({ins_rate}),ISNUMBER({goods4}),ISNUMBER({freight4})),'
                       '({goods4}+{freight4})*{ins_rate}/100*1.1,"")))'),
             "note": "CIF 已含 → 0；费率按 110% 投保额"}),
    ("rmb", {"key": "cif_total", "label": "到岸成本合计（CIF 等值）",
             "value": ('=IF(COUNT({goods4},{packing4},{origin_ch4},{ex4},{freight4},{ins4})=6,'
                       'SUM({goods4},{packing4},{origin_ch4},{ex4},{freight4},{ins4}),"")'),
             "note": "货值+包装+起运港+出口侧+海运+保险（原币与人民币两列）", "bold": True}),
    ("sec", {"text": "④ 第二层：进口税费（关税不可抵扣；增值税分现金/可抵扣两栏）", "teal": True}),
    ("kv", {"key": "tariff", "label": "关税税率（实征，从税则查询录入）", "value": 0.055, "fmt": P4,
            "note": "来源与核验日期见【数据来源】页", "fill": "in", "bold": True}),
    ("kv", {"key": "ad", "label": "反倾销/反补贴税率", "value": 0.0, "fmt": P4,
            "note": "核验后填写；未查到填 0 并注明（≠不存在）", "fill": "in"}),
    ("kv", {"key": "vat", "label": "进口环节增值税率", "value": 0.13, "fmt": P4,
            "note": "一般货物 13%", "fill": "in"}),
    ("kv", {"key": "credit_yn", "label": "增值税是否可抵扣（是/否）", "value": "是", "fmt": None,
            "note": "一般纳税人且用于应税项目=是", "fill": "in"}),
    ("kv", {"key": "ins_cust", "label": "其中：计入计税价格的保险费",
            "value": ('=IF({ins_incl}=TRUE,0,IF(ISNUMBER({ins4}),{ins4},'
                      'IF(AND(ISNUMBER({goods4}),ISNUMBER({freight4})),(({goods4})'
                      '+IF({pack_incl}=TRUE,0,IF(ISNUMBER({pack_extra}),{pack_extra},0))'
                      '+IF({has_origin},0,IF(ISNUMBER({origin_ch}),{origin_ch},0))'
                      '+IF({has_origin},0,IF(ISNUMBER({ex_cost}),{ex_cost},0))'
                      '+{freight4})*0.003/0.997,"")))'),
            "fmt": M, "note": "未投保时按（货价+运费）×0.3‰（第36条）", "fill": "calc"}),
    ("kv", {"key": "cv_cny", "label": "关税计税价格（人民币，完税价格）",
            "value": ('=IF(AND(ISNUMBER({goods4}),ISNUMBER({fx_c}),ISNUMBER({packing4}),ISNUMBER({ex4}),'
                      'ISNUMBER({freight4}),ISNUMBER({ins4}),ISNUMBER({ins_cust})),'
                      '({goods4}+{packing4}+IF(ISNUMBER({origin_ch4}),{origin_ch4},0)+{ex4}+{freight4}'
                      '+IF({ins_incl},0,{ins_cust}))*{fx_c},"")'),
            "fmt": M, "note": "＝(货值+包装+起运港+出口侧+海运+实际保险+应计保险)×海关计征汇率",
            "fill": "key", "bold": True}),
    ("kv", {"key": "duty", "label": "应纳关税",
            "value": '=IF(AND(ISNUMBER({cv_cny}),ISNUMBER({tariff})),{cv_cny}*{tariff},"")',
            "fmt": M, "note": "＝计税价格×实征税率（不可抵扣，一定进成本）", "fill": "calc"}),
    ("kv", {"key": "ad_cny", "label": "反倾销/反补贴税",
            "value": '=IF(AND(ISNUMBER({cv_cny}),ISNUMBER({ad})),{cv_cny}*{ad},"")',
            "fmt": M, "note": "＝计税价格×措施税率", "fill": "calc"}),
    ("kv", {"key": "vat_base", "label": "组成计税价格（增值税基数）",
            "value": '=IF(AND(ISNUMBER({cv_cny}),ISNUMBER({duty})),{cv_cny}+{duty}+{ad_cny},"")',
            "fmt": M, "note": "＝计税价格+关税+反倾销税（+消费税，本产品无）", "fill": "calc"}),
    ("kv", {"key": "vat_cash", "label": "进口环节增值税（现金支出）",
            "value": '=IF(AND(ISNUMBER({vat_base}),ISNUMBER({vat})),{vat_base}*{vat},"")',
            "fmt": M, "note": "＝组成计税价格×13%；现金支出，另行列可抵扣", "fill": "key", "bold": True}),
    ("kv", {"key": "vat_credit", "label": "其中：可抵扣进项税额",
            "value": '=IF(AND(ISNUMBER({vat_cash}),LEFT({credit_yn},1)="是"),{vat_cash},0)',
            "fmt": M, "note": "可抵扣部分不计入最终经济成本", "fill": "calc"}),
    ("kv", {"key": "vat_noncred", "label": "其中：不可抵扣部分（进成本）",
            "value": '=IF(ISNUMBER({vat_cash}),{vat_cash}-{vat_credit},"")',
            "fmt": M, "note": "不可抵扣时全额进入成本", "fill": "calc"}),
    ("sec", {"text": "⑤ 第三层：口岸与境内物流（人民币，整票；不进入计税价格）", "teal": True}),
    ("kv", {"key": "port", "label": "港杂费", "value": 600, "fmt": M,
            "note": "THC/港建/换单/堆存等", "fill": "in"}),
    ("kv", {"key": "broker", "label": "报关代理费", "value": 500, "fmt": M,
            "note": "宁波港公示 100–500 元/票", "fill": "in"}),
    ("kv", {"key": "inspect", "label": "检验检测费", "value": 0, "fmt": M,
            "note": "无检验填 0 并注明", "fill": "in"}),
    ("kv", {"key": "wh", "label": "仓储费", "value": 3000, "fmt": M,
            "note": "无仓储填 0 并注明", "fill": "in"}),
    ("kv", {"key": "truck", "label": "国内运输费", "value": 7812.5, "fmt": M,
            "note": "0.5 元/吨·km × 250km × 62.5t", "fill": "in"}),
    ("kv", {"key": "fin", "label": "资金/信用证成本", "value": 0, "fmt": M,
            "note": "不计入计税价格", "fill": "in"}),
    ("kv", {"key": "dom_sum", "label": "境内费用合计",
            "value": '=IF(COUNT({port}:{fin})=6,SUM({port}:{fin}),"")',
            "fmt": M, "note": "人民币，不受汇率影响", "fill": "calc", "bold": True}),
    ("sec", {"text": "⑥ 汇总：现金支出 / 可抵扣税额 / 最终经济成本"}),
    ("kv", {"key": "s1", "label": "① 到岸成本（不含进口税费）",
            "value": '=IF(ISNUMBER({cif_total}),{rmb_cif_total},"")', "fmt": M,
            "note": "货值+运费+保险（市场汇率）", "fill": "calc"}),
    ("kv", {"key": "s2", "label": "② 关税 + 反倾销税",
            "value": '=IF(AND(ISNUMBER({duty}),ISNUMBER({ad_cny})),{duty}+{ad_cny},"")', "fmt": M,
            "note": "不可抵扣", "fill": "calc"}),
    ("kv", {"key": "s3", "label": "③ 进口环节增值税（现金全额）",
            "value": '=IF(ISNUMBER({vat_cash}),{vat_cash},"")', "fmt": M,
            "note": "现金支出", "fill": "calc"}),
    ("kv", {"key": "s4", "label": "④ 境内费用", "value": '=IF(ISNUMBER({dom_sum}),{dom_sum},"")',
            "fmt": M, "note": "", "fill": "calc"}),
    ("kv", {"key": "cash", "label": "整票现金支出 = ①+②+③+④",
            "value": '=IF(COUNT({s1}:{s4})=4,SUM({s1}:{s4}),"")', "fmt": M,
            "note": "所有实际付出去的钱", "fill": "key", "bold": True}),
    ("kv", {"key": "less_credit", "label": "减：可抵扣进项税额",
            "value": '=IF(ISNUMBER({vat_credit}),-{vat_credit},"")', "fmt": M,
            "note": "申报期抵扣、现金回流", "fill": "calc"}),
    ("kv", {"key": "final_tot", "label": "最终经济成本（整票）= 现金支出 − 可抵扣",
            "value": '=IF(ISNUMBER({cash}),{cash}+{less_credit},"")', "fmt": M,
            "note": "可抵扣时已剔除增值税", "fill": "key", "bold": True}),
    ("kv", {"key": "final_pt", "label": "★ 最终经济成本 元/吨（参考到厂成本）",
            "value": '=IF(AND(ISNUMBER({final_tot}),{qty}>0),{final_tot}/{qty},"")', "fmt": M,
            "note": "", "fill": "key", "bold": True}),
    ("kv", {"key": "cash_pt", "label": "现金支出 元/吨",
            "value": '=IF(AND(ISNUMBER({cash}),{qty}>0),{cash}/{qty},"")', "fmt": M,
            "note": "", "fill": "calc"}),
    ("kv", {"key": "cif_pt", "label": "到岸成本 元/吨",
            "value": '=IF(AND(ISNUMBER({s1}),{qty}>0),{s1}/{qty},"")', "fmt": M,
            "note": "", "fill": "calc"}),
    ("kv", {"key": "status", "label": "完整到厂成本状态", "value": "__status__", "fmt": None,
            "note": "未填项不会被当作 0；待补全时完整到厂价不可对外使用", "fill": "calc"}),
    ("kv", {"key": "known", "label": "已知成本小计（下限参考，非完整到厂价）", "value": "__known__",
            "fmt": M, "note": "待补全时只能引用此值", "fill": "calc"}),
]

INFO = [("产品", "工业级乙二醇 MEG", "规格", "≥99.9% 工业级"),
        ("HS编码", "29053100", "原产国", "SA 沙特阿拉伯"),
        ("目的地", "宁波港 → 江苏苏州", "指定地点", None)]  # None → 术语指定地点

STATUS_KEYS = ["goods4", "packing4", "origin_ch4", "ex4", "freight4", "ins4", "cif_total",
               "pack_extra_on", "cv_cny", "vat_base", "vat_cash", "port", "broker", "inspect",
               "wh", "truck", "fin"]
NET_KEYS = ["cif_total", "duty", "ad_cny", "vat_cash", "dom_sum"]


def derive_refs() -> dict:
    ref = {}
    for i, (kind, cfg) in enumerate(LAYOUT, start=1):
        if kind in ("kv", "rmb") and cfg.get("key"):
            ref[cfg["key"]] = i
    return ref


def build_case(wb: Workbook, term: str, place: str) -> dict:
    ref = derive_refs()
    ws = wb.create_sheet(term)
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = TEAL
    for col, w in {"A": 2.5, "B": 38, "C": 17, "D": 13, "E": 10, "F": 40}.items():
        ws.column_dimensions[col].width = w

    def sub(tpl: str) -> str:
        out = tpl.replace("{t}", term)
        for k in sorted(ref, key=len, reverse=True):
            out = out.replace("{rmb_" + k + "}", f"D{ref[k]}")
        for k in sorted(ref, key=len, reverse=True):
            out = out.replace("{" + k + "}", f"C{ref[k]}")
        # 区间引用 {a}:{b} 需要保持 Excel 语法 C5:C9
        return out

    ws["B1"] = f"进口到厂成本 · {term} 口径"
    ws["B1"].font = T_FONT
    ws["B2"] = (f"报价：{term} {place}（Incoterms 2020）｜宁波港 → 江苏苏州工厂｜"
                f"黄色=可改参数，白色=公式，未填=待确认")
    ws["B2"].font = S_FONT
    ws.row_dimensions[1].height = 22

    defaults = {"FOB": {}, "CFR": {"unit_price": 685.00, "freight": None},
                "CIF": {"unit_price": 685.05, "freight": None, "ins_incl": "TRUE"}}[term]

    info_i = 0
    for i, (kind, cfg) in enumerate(LAYOUT, start=1):
        if kind == "sec":
            ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=6)
            c = ws.cell(row=i, column=2, value=cfg["text"])
            c.font = Font(name="微软雅黑", size=10, bold=True,
                          color="FFFFFF" if cfg.get("teal") else NAVY)
            c.fill = PatternFill("solid", fgColor=TEAL) if cfg.get("teal") else FILL_SEC
            for col in range(2, 7):
                ws.cell(row=i, column=col).border = BOX
            ws.row_dimensions[i].height = 19
        elif kind == "info":
            l1, v1, l2, v2 = INFO[info_i]
            v2 = place if v2 is None else v2
            for lc, lv, vc, vv in ((f"B{i}", l1, f"C{i}", v1), (f"D{i}", l2, f"E{i}", v2)):
                from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
                col_l, row_i = coordinate_from_string(lc)
                if vc != f"B{i}":
                    pass
                ws.cell(row=int(row_i), column=column_index_from_string(col_l), value=lv).font = B_FONT
                cL, rL = coordinate_from_string(vc)
                cc = ws.cell(row=int(rL), column=column_index_from_string(cL), value=vv)
                cc.font = NUM
                cc.fill = FILL_IN
                cc.border = BOX
            info_i += 1
        else:
            key = cfg["key"]
            label = cfg["label"]
            val = cfg["value"]
            if key in defaults:
                val = defaults[key]
            if val == "__status__":
                need = [k for k in STATUS_KEYS if k != "pack_extra_on"]
                cells = ",".join(f"C{ref[k]}" for k in need)
                val = (f'=IF(COUNT({cells})={len(need)},'
                       f'IF(COUNT(C{ref["fx_c"]},C{ref["tariff"]},C{ref["vat"]})=3,"完整",'
                       f'"待补全（缺关税税率或海关计征汇率）"),"待补全（缺费用项）")')
            elif val == "__known__":
                inner = ",".join(f"C{ref[k]}" for k in NET_KEYS)
                val = f'=IFERROR(SUM({inner}),0)'
            elif isinstance(val, str) and val.startswith("="):
                val = sub(val)
            lc = ws.cell(row=i, column=2, value=label)
            lc.font = BOLD if cfg.get("bold") else B_FONT
            c = ws.cell(row=i, column=3, value=val)
            c.font = KEYF if cfg.get("bold") else NUM
            if cfg.get("fmt"):
                c.number_format = cfg["fmt"]
            c.fill = {"in": FILL_IN, "key": FILL_KEY}.get(cfg.get("fill"), FILL_CALC)
            nc = ws.cell(row=i, column=6, value=cfg.get("note", ""))
            nc.font = S_FONT
            nc.alignment = Alignment(wrap_text=True, vertical="center")
            for col in range(2, 7):
                ws.cell(row=i, column=col).border = BOX
            if kind == "rmb":
                d = ws.cell(row=i, column=4, value=f'=IF(ISNUMBER(C{i}),C{i}*$C${ref["fx_m"]},"")')
                d.number_format = M
                d.font = NUM
                d.fill = FILL_KEY if cfg.get("bold") else FILL_CALC
                d.border = BOX
                ws.cell(row=i, column=5, value="人民币").font = S_FONT

    st = f"C{ref['status']}"
    ws.conditional_formatting.add(st, FormulaRule(formula=[f'LEFT(${st},3)="待补全"'], fill=FILL_WARN))
    ws.conditional_formatting.add(st, FormulaRule(formula=[f'${st}="完整"'], fill=FILL_OK))
    ws.print_area = f"A1:F{ref['known'] + 1}"
    return {"ws": ws, "ref": ref}


def build_compare(wb: Workbook, refs: dict[str, dict]):
    ws = wb.create_sheet("口径对照")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2.5
    for col, w in zip("BCDEFG", (30, 16, 16, 16, 15, 15)):
        ws.column_dimensions[col].width = w
    ws["B1"] = "FOB / CFR / CIF 三口径对照"
    ws["B1"].font = T_FONT
    ws["B2"] = ("经济实质相同时（FOB 640 + 运费 45 + 保费），三口径到厂成本应基本一致；"
                "差异只来自卖方对运费/保险的加价。")
    ws["B2"].font = S_FONT
    for i, h in enumerate(["指标", "FOB 朱拜勒", "CFR 宁波", "CIF 宁波", "CFR−FOB", "CIF−FOB"]):
        c = ws.cell(row=4, column=2 + i, value=h)
        c.font = H_FONT
        c.fill = FILL_H
        c.border = BOX
        c.alignment = Alignment(horizontal="center")
    items = [("报价（原币/吨）", "unit_price", M), ("到岸成本 元/吨", "cif_pt", M),
             ("关税计税价格（元）", "cv_cny", M), ("应纳关税（元）", "duty", M),
             ("增值税（元，现金）", "vat_cash", M), ("可抵扣进项（元）", "vat_credit", M),
             ("整票现金支出（元）", "cash", M), ("最终经济成本（元）", "final_tot", M),
             ("最终经济成本 元/吨", "final_pt", M), ("完整状态", "status", None)]
    for i, (label, key, fmt) in enumerate(items):
        r = 5 + i
        ws.cell(row=r, column=2, value=label).font = BOLD
        for j, t in enumerate(("FOB", "CFR", "CIF")):
            cell = f"C{refs[t]['ref'][key]}"
            c = ws.cell(row=r, column=3 + j, value=f"='{t}'!{cell}")
            c.font = NUM
            if fmt:
                c.number_format = fmt
        ws.cell(row=r, column=6, value=f'=IF(AND(ISNUMBER(C{r}),ISNUMBER(D{r})),D{r}-C{r},"")').number_format = M
        ws.cell(row=r, column=7, value=f'=IF(AND(ISNUMBER(C{r}),ISNUMBER(E{r})),E{r}-C{r},"")').number_format = M
        for col in range(2, 8):
            ws.cell(row=r, column=col).border = BOX
            if i >= 6:
                ws.cell(row=r, column=col).fill = FILL_KEY
    tips = ["① FOB 报价不含海运与保险，测算必须另加；CFR/CIF 已含海运费，绝不能再加一次。",
            "② CIF 已含保险；买方另行加保的费用单列，不得与报价内保费重复。",
            "③ 三口径到厂成本差异 = 卖方对运费/保险的加价 → 这是议价抓手。",
            "④ 关税与增值税的计税价格都以 CIF 等值为基础：FOB 报价看着低，税费基数并不低。",
            "⑤ 状态为「待补全」时，该口径的到厂价不可对外使用，只能用「已知成本小计」。"]
    ws["B16"] = "结论要点"
    ws["B16"].font = Font(name="微软雅黑", size=10, bold=True, color=TEAL)
    for i, t in enumerate(tips):
        r = 17 + i
        c = ws.cell(row=r, column=2, value=t)
        c.font = B_FONT
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
    ch = BarChart()
    ch.type = "col"
    ch.title = "三口径到厂成本（元/吨）"
    ch.add_data(Reference(ws, min_col=3, max_col=5, min_row=13, max_row=13), from_rows=True,
                titles_from_data=False)
    ch.set_categories(Reference(ws, min_col=3, max_col=5, min_row=4, max_row=4))
    ch.height, ch.width = 7, 15
    ch.legend = None
    ws.add_chart(ch, "B24")


def build_sensitivity(wb: Workbook, refs: dict[str, dict]):
    ws = wb.create_sheet("敏感性分析")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2.5
    for col, w in zip("BCDEFG", (22, 13, 17, 15, 11, 42)):
        ws.column_dimensions[col].width = w
    ws["B1"] = "敏感性分析（基准 = FOB 页，全部由公式驱动）"
    ws["B1"].font = T_FONT
    ws["B2"] = ("每个情景独立复刻计算链：货值→CIF→关税计税价格→关税→增值税→现金支出→可抵扣→元/吨。"
                "未做线性近似。")
    ws["B2"].font = S_FONT
    ws.merge_cells("B2:G2")

    F = refs["FOB"]["ref"]

    def C(k):
        return f"'FOB'!C{F[k]}"

    BASE = 4
    ws.cell(row=BASE, column=2, value="基准（FOB 页）").font = BOLD
    ws.cell(row=BASE, column=3, value=f"={C('unit_price')}").number_format = M
    ws.cell(row=BASE, column=4, value=f"={C('final_pt')}").number_format = M
    ws.cell(row=BASE, column=4).font = KEYF
    ws.cell(row=BASE, column=5, value=f"={C('final_tot')}").number_format = M
    ws.cell(row=BASE, column=7, value="C=单价 / D=到厂 元吨 / E=整票").font = S_FONT
    for col in range(2, 8):
        ws.cell(row=BASE, column=col).border = BOX

    def head(r, title):
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
        c = ws.cell(row=r, column=2, value=title)
        c.font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=TEAL)
        for i, h in enumerate(["情景", "情景参数", "到厂成本 元/吨", "Δ 元/吨", "Δ %", "说明"]):
            hc = ws.cell(row=r + 1, column=2 + i, value=h)
            hc.font = H_FONT
            hc.fill = FILL_H
            hc.border = BOX
            hc.alignment = Alignment(horizontal="center")

    def scenario(r, label, param, qty_e, freight_e, fxm_e, fxc_e, note=""):
        p_incl = f"IF({C('pack_incl')}=TRUE,0,IF(ISNUMBER({C('pack_extra')}),{C('pack_extra')},0))"
        o_ch = f"IF(ISNUMBER({C('origin_ch')}),IF({C('has_origin')},0,{C('origin_ch')}),0)"
        ex_c = f"IF(ISNUMBER({C('ex_cost')}),IF({C('has_origin')},0,{C('ex_cost')}),0)"
        goods = f"IF(AND(ISNUMBER({C('unit_price')}),ISNUMBER({qty_e})),{C('unit_price')}*{qty_e},0)"
        fr = f"IF({C('has_freight')},0,IF(ISNUMBER({freight_e}),{freight_e}*{qty_e},0))"
        ins = (f"IF({C('ins_incl')},0,IF(ISNUMBER({C('ins_amt')}),{C('ins_amt')},"
               f"IF(ISNUMBER({C('ins_rate')}),({goods}+{fr})*{C('ins_rate')}/100*1.1,"
               f"({goods}+{p_incl}+{o_ch}+{ex_c}+{fr})*0.003/0.997)))")
        cv = f"IF(ISNUMBER({fxc_e}),({goods}+{p_incl}+{o_ch}+{ex_c}+{fr}+{ins})*{fxc_e},0)"
        duty = f"{cv}*IF(ISNUMBER({C('tariff')}),{C('tariff')},0)*(1+IF(ISNUMBER({C('ad')}),{C('ad')},0))"
        vat = f"({cv}+{duty})*IF(ISNUMBER({C('vat')}),{C('vat')},0)"
        cny = f"({goods}+{p_incl}+{o_ch}+{ex_c}+{fr}+{ins})*IF(ISNUMBER({fxm_e}),{fxm_e},0)"
        fixed = "(" + "+".join(f"IF(ISNUMBER({C(k)}),{C(k)},0)"
                               for k in ("port", "broker", "inspect", "wh", "truck", "fin")) + ")"
        cred = f'IF(LEFT({C("credit_yn")},1)="是",{vat},0)'
        f = (f'=IF(AND(ISNUMBER({C("unit_price")}),ISNUMBER({qty_e}),ISNUMBER({fxm_e}),'
             f'ISNUMBER({fxc_e}),ISNUMBER({C("tariff")})),'
             f'({cny}+{duty}+{vat}+{fixed}-{cred})/({qty_e}),"")')
        ws.cell(row=r, column=2, value=label).font = B_FONT
        pc = ws.cell(row=r, column=3, value=param)
        pc.number_format = M
        pc.font = NUM
        c4 = ws.cell(row=r, column=4, value=f)
        c4.number_format = M
        c4.font = NUM
        ws.cell(row=r, column=5, value=f'=IF(AND(ISNUMBER(D{r}),ISNUMBER(D{BASE})),D{r}-D{BASE},"")').number_format = M
        ws.cell(row=r, column=6, value=f'=IF(AND(ISNUMBER(E{r}),ISNUMBER(D{BASE})),E{r}/D{BASE},"")').number_format = '0.00%'
        ws.cell(row=r, column=6).font = NUM
        ws.cell(row=r, column=7, value=note).font = S_FONT
        for col in range(2, 8):
            ws.cell(row=r, column=col).border = BOX

    q = C("qty")
    head(6, "① 汇率 ±3%（市场汇率与海关计征汇率同向变动）")
    for i, k in enumerate((-0.03, 0.0, 0.03)):
        r = 9 + i
        scenario(r, f"汇率 {k:+.0%}", k, q, C("freight"),
                 f"{C('fx_m')}*(1+{k})", f'IF(ISNUMBER({C("fx_c")}),{C("fx_c")}*(1+{k}),"")',
                 "市场汇率影响现金，海关计征汇率影响税费基数" if i == 0 else "")
        ws.cell(row=r, column=3).number_format = '0.0%'
    head(12, "② 海运费变化（运费会被关税放大）")
    for i, k in enumerate((-0.20, -0.10, 0.0, 0.10, 0.20)):
        r = 15 + i
        scenario(r, f"海运费 {k:+.0%}", f"{C('freight')}*(1+{k})", q, f"{C('freight')}*(1+{k})",
                 C("fx_m"), C("fx_c"),
                 "运费 +1 USD/MT ≈ +(1+关税率)×汇率 元/吨" if i == 0 else "")
    head(20, "③ 采购数量变化（按票固定费用摊薄）")
    for i, k in enumerate((0.5, 0.75, 1.0, 1.5, 2.0)):
        r = 23 + i
        scenario(r, f"数量 ×{k:.2f}".rstrip('0').rstrip('.'), f"=" + f"{q}*{k}", f"{q}*{k}", C("freight"), C("fx_m"), C("fx_c"),
                 "海运费按 USD/MT 随量；港杂/报关/仓储/国内运输按票不随量" if i == 0 else "")
    ws["B28"] = ("口径说明：情景逐项复刻计算链，未做线性近似。数值已与 Python 引擎对账"
                 "（scripts/verify_workbook.py 输出 build/workbook_reconciliation.json）。")
    ws["B28"].font = S_FONT
    ws.merge_cells("B28:G28")


def build_sources(wb: Workbook):
    ws = wb.create_sheet("数据来源")
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDEF", (4, 30, 24, 16, 62, 12)):
        ws.column_dimensions[col].width = w
    ws["B1"] = "数据来源与核验记录"
    ws["B1"].font = T_FONT
    ws["B2"] = "每个数字必须能回答：谁给的、什么时候核验的、失效条件是什么。"
    ws["B2"].font = S_FONT
    for i, h in enumerate(["#", "项目", "取值", "类型", "来源 / 依据", "核验日"]):
        c = ws.cell(row=4, column=1 + i, value=h)
        c.font = H_FONT
        c.fill = FILL_H
        c.border = BOX
    rows = [
        ("HS 编码", "29053100", "公开查询", "2026年进出口税则（zhengdao.ai/tariff/2026/29053100）", "2026-10-20"),
        ("最惠国关税税率", "5.5%", "公开查询", "2026年进出口税则 29053100（税委会公告2025年第12号）", "2026-07-15"),
        ("普通税率", "30%", "公开查询", "同上；原产地不明时适用，不适用暂定税率", "2026-07-15"),
        ("协定税率（沙特）", "不适用", "公开查询", "中国—海合会自贸协定未生效（商务部自贸区服务网）", "2026-10-20"),
        ("进口环节增值税率", "13%", "公开查询", "一般货物；计税公式见《关税法》第70条", "2026-10-20"),
        ("市场参考汇率", "6.6807", "公开查询", "ECB 参考汇率交叉（frankfurter.app，2026-10-19）", "2026-10-20"),
        ("海关计征汇率", "待确认", "待确认", "申报日对应上月第三个星期三（2026-09-16）PBOC 中间价", "2026-10-20"),
        ("保险费 0.3‰ 口径", "（货价+运费）×0.3‰", "公开查询", "《确定进出口货物计税价格办法》第36条", "2026-10-20"),
        ("计税价格构成", "成交价格+运保费", "公开查询", "《关税法》第24、25、26条", "2024-12-01"),
        ("关税计算", "计税价格×税率", "公开查询", "《关税法》第23条", "2024-12-01"),
        ("FOB 报价", "640.00 USD/MT", "模拟情景", "演示建模假设，非实时市场报价", "—"),
        ("海运费", "45.00 USD/MT", "模拟情景", "朱拜勒→宁波；非货代实盘报价", "—"),
        ("保险费率", "0.55‰", "模拟情景", "按 110% 投保额；非保单", "—"),
        ("港杂费", "600 元/票", "模拟情景", "结构参照宁波港口岸收费公示", "2026-10-20"),
        ("报关代理费", "500 元/票", "公开区间", "宁波港公示 100–500 元/票", "2026-10-20"),
        ("仓储费", "3000 元/票", "模拟情景", "免箱期内堆存", "—"),
        ("国内运输", "7812.5 元/票", "公开费率×假设", "0.5 元/吨·km×250km×62.5t", "2026-10-20"),
    ]
    for i, (a, b, t_, d, e) in enumerate(rows):
        r = 5 + i
        ws.cell(row=r, column=1, value=i + 1).font = NUM
        ws.cell(row=r, column=2, value=a).font = B_FONT
        ws.cell(row=r, column=3, value=b).font = NUM
        t = ws.cell(row=r, column=4, value=t_)
        t.font = B_FONT
        t.fill = FILL_WARN if t_ == "待确认" else (
            PatternFill("solid", fgColor="FEF3C7") if ("模拟" in t_ or "区间" in t_) else FILL_OK)
        s = ws.cell(row=r, column=5, value=d)
        s.font = S_FONT
        s.alignment = Alignment(wrap_text=True, vertical="center")
        ws.cell(row=r, column=6, value=e).font = S_FONT
        for col in range(1, 7):
            ws.cell(row=r, column=col).border = BOX


def build_incoterms(wb: Workbook):
    ws = wb.create_sheet("术语规则")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2.5
    for col, w in zip("BCDEFG", (10, 24, 14, 14, 14, 46)):
        ws.column_dimensions[col].width = w
    ws["B1"] = "Incoterms 2020 成本归属矩阵"
    ws["B1"].font = T_FONT
    for i, h in enumerate(["术语", "中文", "出口报关", "主运费", "保险", "进口关税/清关"]):
        c = ws.cell(row=3, column=2 + i, value=h)
        c.font = H_FONT
        c.fill = FILL_H
        c.border = BOX
        c.alignment = Alignment(horizontal="center")
    data = [("EXW", "工厂交货", "买方", "买方", "买方", "买方"),
            ("FCA", "货交承运人", "卖方", "买方", "买方", "买方"),
            ("FAS", "船边交货", "卖方", "买方", "买方", "买方"),
            ("FOB", "船上交货", "卖方", "买方", "买方", "买方"),
            ("CFR", "成本加运费", "卖方", "卖方", "买方", "买方"),
            ("CIF", "成本保险费加运费", "卖方", "卖方", "卖方", "买方"),
            ("CPT", "运费付至", "卖方", "卖方", "买方", "买方"),
            ("CIP", "运费保险费付至", "卖方", "卖方", "卖方", "买方"),
            ("DAP", "目的地交货", "卖方", "卖方", "买方", "买方"),
            ("DPU", "卸货地交货", "卖方", "卖方", "买方", "买方"),
            ("DDP", "完税后交货", "卖方", "卖方", "卖方", "卖方")]
    for i, row in enumerate(data):
        r = 4 + i
        for j, v in enumerate(row):
            c = ws.cell(row=r, column=2 + j, value=v)
            c.font = B_FONT if j < 2 else NUM
            c.border = BOX
            c.alignment = Alignment(horizontal="center" if j else "left")
            if j >= 2:
                c.fill = PatternFill("solid", fgColor="E0F2FE" if v == "卖方" else "FEF3C7")
    tips = ['"卖方承担" = 已含在报价中，测算时不能再加一次。',
            "FOB→加海运+保险；CFR→只加保险；CIF→都不加。",
            "CIF/CIP 保险最低保障 110% 合同价（2020 版 CIP 为 A 条款）。",
            "DDP 卖方付进口关税与清关，但进口环节增值税通常仍由境内进口方承担。",
            "术语必须注明指定地点与版本，例：CIF 宁波 Incoterms 2020。"]
    ws["B16"] = "要点"
    ws["B16"].font = Font(name="微软雅黑", size=10, bold=True, color=TEAL)
    for i, t in enumerate(tips):
        c = ws.cell(row=17 + i, column=2, value=t)
        c.font = B_FONT
        ws.merge_cells(start_row=17 + i, start_column=2, end_row=17 + i, end_column=7)


def build_instructions(wb: Workbook, refs: dict[str, dict]):
    ws = wb.create_sheet("使用说明", 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2.5
    ws.column_dimensions["B"].width = 112
    F = refs["FOB"]["ref"]

    def c(k):
        return f"C{F[k]}"

    ws["B1"] = "进口到厂成本计算器 · Excel 版"
    ws["B1"].font = Font(name="微软雅黑", size=16, bold=True, color=NAVY)
    ws["B2"] = "FOB / CFR / CIF 三口径 · 全公式 · 改参数自动重算"
    ws["B2"].font = S_FONT
    body = [
        ("【30 秒上手】", True),
        (f"只改黄色单元格：{c('unit_price')} 单价、{c('qty')} 数量、{c('fx_m')} 市场汇率、"
         f"{c('fx_c')} 海关计征汇率、{c('freight')} 海运费（仅 FOB）、"
         f"{c('port')}~{c('fin')} 境内费用。", False),
        (f"看三个数：{c('final_pt')} 最终经济成本 元/吨（★到厂成本）；{c('cash')} 整票现金支出；"
         f"{c('vat_cash')} 进口环节增值税现金。", False),
        (f"{c('status')} 状态若为「待补全」，说明有关键项没填——先补数据，"
         f"不要用 {c('known')} 已知小计冒充完整到厂价。", False),
        ("", False),
        ("【三口径怎么防重复计费】", True),
        (f"CFR 页：{c('freight4')} 海运费自动为 0（报价已含）；CIF 页：{c('freight4')} 与 "
         f"{c('ins4')} 都为 0（海运+保险均已含）。", False),
        ("由此，CFR/CIF 报价里已经付过的运费/保费不会被再加一次。", False),
        ("", False),
        ("【关税与增值税】", True),
        (f"关税税率 {c('tariff')} 必须按税则查询后录入；可享优惠时先核验 4 道闸门："
         f"协定生效 / 降税清单 / 原产地规则 / 有效证书。", False),
        (f"增值税分两栏：{c('vat_cash')} 现金支出 / {c('vat_credit')} 可抵扣进项；"
         f"{c('final_tot')} = 现金支出 − 可抵扣。", False),
        (f"把 {c('credit_yn')} 改成「否」（不可抵扣），增值税会全额进入最终成本。", False),
        ("", False),
        ("【税费公式】", True),
        ("关税计税价格 =（货值+包装+起运港+出口侧+海运+实际保险+应计入保险）× 海关计征汇率", False),
        ("应纳关税 = 关税计税价格 × 关税税率（不可抵扣，一定进成本）", False),
        ("组成计税价格 = 计税价格 + 关税 + 反倾销税", False),
        ("进口环节增值税 = 组成计税价格 × 13%（现金支出；可抵扣时不计入最终成本）", False),
        ("保险费未确定时 =（货价+运费）×0.3‰ ÷ (1−0.3‰)（《确定计税价格办法》第36条）", False),
        ("", False),
        ("【免责】", True),
        ("运费/保险/港杂/仓储为模拟情景；税率须按核验日期重新确认；最终金额以海关核定与实际单据为准。", False),
    ]
    r = 4
    for text, is_head in body:
        cc = ws.cell(row=r, column=2, value=text)
        cc.font = Font(name="微软雅黑", size=11, bold=True, color=TEAL) if is_head else B_FONT
        cc.alignment = Alignment(wrap_text=True, vertical="center")
        r += 1
    ws.sheet_properties.tabColor = NAVY


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)
    refs = {}
    for term, place in CASES:
        refs[term] = build_case(wb, term, place)
    build_compare(wb, refs)
    build_sensitivity(wb, refs)
    build_sources(wb)
    build_incoterms(wb)
    build_instructions(wb, refs)
    wb.active = 0
    wb.save(OUT)
    print("saved:", os.path.abspath(OUT))
    import json
    dump = {t: {k: v for k, v in refs[t]["ref"].items()} for t in refs}
    with open(os.path.join(HERE, "..", "build", "rowmap.json"), "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=1)
    print("rowmap written")


if __name__ == "__main__":
    main()
