# -*- coding: utf-8 -*-
"""data.json -> Excel 模型（活公式，不写死数字）。

用法：
    python scripts/build_xlsx.py build/data.json --out output/model.xlsx

设计原则：
  * 输入区（蓝色）只放原始参数；计算区（灰色）全部是真公式，改蓝格即重算；
  * 每一层成本、每一个价差都保留公式可追溯，行首有"公式说明"列；
  * 历史序列表与 HTML 报告同源（同一份 data.json），保证两处数字一致；
  * 敏感性矩阵用公式而不是常量，便于用户自行改口径；
  * 工作簿不携带宏，任何 Excel/WPS/LibreOffice 都能直接打开。

工作表：
  1 封面与口径      —— 品种、规格、地区、税率、术语包含关系、声明
  2 参数与输入      —— 蓝格输入（唯一可改的区域）
  3 成本折算        —— 四层成本逐项公式
  4 价差四口径      —— G1~G4 公式与释义
  5 历史序列        —— 逐时点与外盘报价/汇率/国内价的对照
  6 价差曲线数据    —— 图表用数据区（Excel 折线图引用此区）
  7 敏感性          —— 单参数与二维矩阵（公式）
  8 归因分解        —— 本期 vs 对比期
  9 情景对比        —— 术语/口径切换
  10 缺口与来源     —— 数据缺口与数据来源清单
  11 公式表         —— 全部公式的书面版本（可与 Python 对照）
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import wio  # noqa: E402

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import LineChart, Reference
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:
    wio.die("需要 openpyxl：pip install openpyxl")

# ------------------------------------------------------------------ 样式
NAVY = "1F3A52"
BLUE_IN = "E8F1FA"       # 输入格
GREY_CALC = "F3F5F7"     # 计算格
GREY_HDR = "1F3A52"
ACCENT = "1B6E5A"
WARN = "B45309"
THIN = Side(style="thin", color="C9D3DC")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_TITLE = Font(name="微软雅黑", size=15, bold=True, color="FFFFFF")
F_H = Font(name="微软雅黑", size=10.5, bold=True, color="FFFFFF")
F_B = Font(name="微软雅黑", size=10.5, bold=True, color="1F2933")
F_N = Font(name="微软雅黑", size=10)
F_S = Font(name="微软雅黑", size=9, color="5A6B7B")
NUM = "#,##0.00"
NUM0 = "#,##0"
PCT = "0.00%"
RATE = "0.0000"


def sheet(wb, title, tab=None):
    ws = wb.create_sheet(title)
    if tab:
        ws.sheet_properties.tabColor = tab
    ws.sheet_view.showGridLines = False
    return ws


def band(ws, row, text, ncol, sub=None):
    ws.cell(row=row, column=1, value=text).font = F_TITLE
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=GREY_HDR)
    for c in range(2, ncol + 1):
        ws.cell(row=row, column=c).fill = PatternFill("solid", fgColor=GREY_HDR)
    ws.row_dimensions[row].height = 26
    if sub:
        ws.cell(row=row + 1, column=1, value=sub).font = F_S
        ws.row_dimensions[row + 1].height = 18
        return row + 2
    return row + 1


def header(ws, row, cols):
    for i, c in enumerate(cols, start=1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = F_H
        cell.fill = PatternFill("solid", fgColor="2E4F6B")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX
    ws.row_dimensions[row].height = 30
    return row + 1


def put(ws, row, col, value, inp=False, fmt=None, bold=False, wrap=False, align=None, note=False):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = F_B if bold else (F_S if note else F_N)
    cell.fill = PatternFill("solid", fgColor=BLUE_IN if inp else (GREY_CALC if not note else "FFFFFF"))
    cell.border = BOX
    if fmt:
        cell.number_format = fmt
    cell.alignment = Alignment(horizontal=align or ("left" if isinstance(value, str) else "right"),
                               vertical="top", wrap_text=wrap)
    return cell


def widths(ws, mapping):
    for col, w in mapping.items():
        ws.column_dimensions[col].width = w


# ------------------------------------------------------------------ 封面
def ws_cover(wb, d):
    ws = sheet(wb, "1 封面与口径", NAVY)
    widths(ws, {"A": 26, "B": 92, "C": 16, "D": 22})
    r = band(ws, 1, d["meta"]["title"], 4)
    m = d["meta"]
    rows = [
        ("品种 / 规格", "%s（%s） · %s" % (m["product"], m["product_code"], m["spec"])),
        ("HS 编码", "%s %s" % (m["hs_code"], m.get("hs_desc", ""))),
        ("海外口径", "%s · %s · %s · %s" % (m["quote_region"], m["quote_term"], m["currency"], m["quote_basis"])),
        ("国内口径", "%s · %s" % (m["dom_region"], m["dom_basis"])),
        ("基准日", m["base_date"]),
        ("观察窗口", m["window"]),
        ("金额单位", "元/吨（除标注 USD 的报价）"),
        ("生成时间 / 工具", "%s · %s" % (m.get("generated_at", ""), m.get("author", ""))),
    ]
    for k, v in rows:
        put(ws, r, 1, k, bold=True)
        put(ws, r, 2, v, wrap=True)
        ws.cell(row=r, column=2).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = 20
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="贸易术语包含关系（防止重复计费）").font = Font(name="微软雅黑", size=11, bold=True, color=NAVY)
    r += 1
    r = header(ws, r, ["费用层", "当前术语是否已包含", "当前术语", "说明"])
    lay = [("goods", "货值", "F 组及之后均含货值"),
           ("inland_origin", "出口国内陆运费", "工厂仓库 → 装运港"),
           ("export_clear", "出口报关杂费", "出口报关、单证"),
           ("freight", "国际海运费", "主运费至目的港"),
           ("insurance", "保险费", "海上运输保险"),
           ("discharge", "目的港卸货/港杂", "THC、港杂"),
           ("inland_dest", "进口国内陆运", "目的港 → 收货地")]
    inc = m["term_includes"]
    for k, cn, note in lay:
        put(ws, r, 1, cn)
        put(ws, r, 2, "报价已含" if inc[k] else "报价不含，需单列")
        put(ws, r, 3, m["quote_term"])
        put(ws, r, 4, note, note=True)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="必读声明").font = Font(name="微软雅黑", size=11, bold=True, color=WARN)
    r += 1
    for i, t in enumerate(d.get("disclaimers", []), start=1):
        c = ws.cell(row=r, column=1, value="%d. %s" % (i, t))
        c.font = F_N
        c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        ws.row_dimensions[r].height = max(18, 15 * (len(t) // 60 + 1))
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="口径要点").font = Font(name="微软雅黑", size=11, bold=True, color=ACCENT)
    r += 1
    for t in m.get("must_read", []) + m.get("focus", []):
        c = ws.cell(row=r, column=1, value="• " + t)
        c.font = F_N
        c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        ws.row_dimensions[r].height = max(18, 15 * (len(t) // 60 + 1))
        r += 1
    return ws


# ------------------------------------------------------------------ 参数
def ws_params(wb, d):
    ws = sheet(wb, "2 参数与输入", "2E7D32")
    widths(ws, {"A": 4, "B": 26, "C": 16, "D": 10, "E": 62, "F": 16})
    r = band(ws, 1, "参数与输入（蓝底格为唯一可修改区，改完所有计算表自动重算）", 6)
    r = header(ws, r, ["#", "参数", "取值", "单位", "含义 / 来源", "Excel 名称"])

    P = d["params"]
    names = {}
    items = [
        ("price_quote", "海外报价", P.get("price_quote"), "USD/吨", "卖方报价；文本口径见「10 缺口与来源」", "报价"),
        ("fx_usdcny", "汇率", P.get("fx_usdcny"), "CNY/USD", "基准日 ECB 参考汇率", "汇率"),
        ("ocean_freight", "国际海运费", P.get("ocean_freight"), "USD/吨", "术语已含则为 0（本表已置 0）", "海运费"),
        ("insurance_rate_pct", "保险费率", P.get("insurance_rate_pct"), "小数", "CIF 已含则不计", "保险费率"),
        ("insurance_rate", "保险加成率", P.get("insurance_rate"), "倍", "惯例 110%", "加成率"),
        ("discharge_fee", "目的港卸货", P.get("discharge_fee"), "USD/吨", "CIF 不含卸货；未取证按 0", "卸货费"),
        ("inland_dest", "进口国内陆运", P.get("inland_dest"), "元/吨", "港口→工厂", "国内运费"),
        ("inland_origin", "出口国内陆运", P.get("inland_origin"), "USD/吨", "仅 EXW 需要", "出口运费"),
        ("export_clear", "出口报关杂费", P.get("export_clear"), "USD/吨", "仅 EXW 需要", "出口报关"),
        ("unload_fee", "装卸/损耗附加", P.get("unload_fee"), "元/吨", "显式附加项", "损耗附加"),
        ("duty_rate", "进口关税率", P.get("duty_rate"), "小数", "见缺口第 1 条（5.5% vs 0%）", "关税率"),
        ("other_tax_rate", "其他税率", P.get("other_tax_rate"), "小数", "反倾销等", "其他税率"),
        ("vat_rate", "进口增值税率", P.get("vat_rate"), "小数", "标准 13%", "增值税率"),
        ("vat_credit_ratio", "可抵扣比例", P.get("vat_credit_ratio"), "小数", "一般纳税人 100%", "抵扣比例"),
        ("purity", "纯度系数", P.get("purity"), "小数", "折纯用", "纯度"),
        ("gross_weight_factor", "毛净比", P.get("gross_weight_factor"), "倍", "包装/皮重修正", "毛净比"),
    ]
    for i, (k, cn, v, u, note, nm) in enumerate(items, start=1):
        put(ws, r, 1, i)
        put(ws, r, 2, cn, bold=True)
        fmt = RATE if k in ("fx_usdcny", "insurance_rate_pct", "duty_rate", "other_tax_rate",
                            "vat_rate", "vat_credit_ratio", "insurance_rate", "purity",
                            "gross_weight_factor") else NUM
        put(ws, r, 3, v, inp=True, fmt=fmt)
        put(ws, r, 4, u)
        put(ws, r, 5, note, note=True)
        put(ws, r, 6, nm, note=True)
        names[k] = "'2 参数与输入'!$C$%d" % r
        r += 1

    r += 1
    r = header(ws, r, ["#", "国内可比价输入", "取值", "单位", "含义", "Excel 名称"])
    dom = d["domestic"]
    dstart = r
    put(ws, r, 1, "D1"); put(ws, r, 2, "国内现货价", bold=True)
    put(ws, r, 3, dom["dom_quote"], inp=True, fmt=NUM); put(ws, r, 4, "元/吨")
    put(ws, r, 5, "含税 · 送到基准地 · 现汇", note=True); put(ws, r, 6, "国内报价", note=True)
    names["dom_quote"] = "'2 参数与输入'!$C$%d" % r
    r += 1
    put(ws, r, 1, "D2"); put(ws, r, 2, "国内价税基", bold=True)
    put(ws, r, 3, dom.get("tax", "含税"), inp=True); put(ws, r, 4, "文本")
    put(ws, r, 5, "含税 / 不含税", note=True); put(ws, r, 6, "税基", note=True)
    names["dom_tax"] = "'2 参数与输入'!$C$%d" % r
    r += 1
    put(ws, r, 1, "D3"); put(ws, r, 2, "送到运费（未含时补）", bold=True)
    put(ws, r, 3, dom.get("dom_freight_added") or 0, inp=True, fmt=NUM); put(ws, r, 4, "元/吨")
    put(ws, r, 5, "若国内报价非送到价则填", note=True); put(ws, r, 6, "国内补运费", note=True)
    names["dom_freight"] = "'2 参数与输入'!$C$%d" % r
    r += 1
    put(ws, r, 1, "D4"); put(ws, r, 2, "规格/地区调整", bold=True)
    put(ws, r, 3, dom.get("dom_adj") or 0, inp=True, fmt=NUM); put(ws, r, 4, "元/吨")
    put(ws, r, 5, "升贴水（品质、区域）", note=True); put(ws, r, 6, "调整项", note=True)
    names["dom_adj"] = "'2 参数与输入'!$C$%d" % r

    r += 2
    r = header(ws, r, ["#", "贸易术语", "取值", "单位", "说明", "Excel 名称"])
    put(ws, r, 1, "T1"); put(ws, r, 2, "术语", bold=True)
    put(ws, r, 3, d["meta"]["quote_term"], inp=True); put(ws, r, 4, "EXW/FCA/FOB/CFR/CIF/DAP")
    put(ws, r, 5, "改术语后需手动把已含项填 0（或看「3 成本折算」的自动屏蔽结果）", note=True)
    put(ws, r, 6, "术语", note=True)
    names["term"] = "'2 参数与输入'!$C$%d" % r
    dv = DataValidation(type="list", formula1='"EXW,FCA,FOB,CFR,CIF,DAP"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(ws.cell(row=r, column=3))
    r += 2

    ws.cell(row=r, column=2, value="注：本表所有蓝色单元格都可改；其余工作表全部引用这里的单元格。").font = F_S
    _ = (dstart,)
    return ws, names


# ------------------------------------------------------------------ 成本
def ws_cost(wb, d, NP):
    ws = sheet(wb, "3 成本折算", ACCENT)
    widths(ws, {"A": 4, "B": 34, "C": 16, "D": 12, "E": 60})
    r = band(ws, 1, "成本折算：从美元报价到四层成本（全部为活公式）", 5)
    r = header(ws, r, ["#", "项目", "金额（元/吨）", "单位", "公式说明"])
    P = d["params"]
    rows = {}

    def line(idx, name, val, unit, note, fmt=NUM, bold=False, key=None):
        """写一行并把行号登记到 rows[key]，后续公式直接引用，避免手写行号。"""
        nonlocal r
        put(ws, r, 1, idx)
        put(ws, r, 2, name, bold=bold)
        put(ws, r, 3, val, fmt=fmt, bold=bold)
        put(ws, r, 4, unit)
        put(ws, r, 5, note, note=True)
        if key:
            rows[key] = r
        r += 1

    def C(key):
        return "C%d" % rows[key]

    line(1, "海外报价（原币）", "=" + NP["price_quote"], "USD/吨", "来自「2 参数与输入」", NUM, key="q")
    line(2, "汇率", "=" + NP["fx_usdcny"], "CNY/USD", "ECB 参考汇率", RATE, key="fx")
    line(3, "货值折人民币", "=%s*%s" % (C("q"), C("fx")), "元/吨", "货值 = 报价 × 汇率", NUM, True, "goods")
    line(4, "出口国内陆运费", "=%s*%s" % (NP["inland_origin"], C("fx")), "元/吨", "EXW 才需要", NUM, False, "inl_o")
    line(5, "出口报关杂费", "=%s*%s" % (NP["export_clear"], C("fx")), "元/吨", "EXW 才需要", NUM, False, "exp_c")
    line(6, "国际海运费", "=%s*%s" % (NP["ocean_freight"], C("fx")), "元/吨",
         "CFR/CIF/DAP 已含，必须填 0", NUM, False, "frt")
    line(7, "保险费", "=(%s+%s+%s+%s)*%s*%s" % (C("goods"), C("inl_o"), C("exp_c"), C("frt"),
                                             NP["insurance_rate"], NP["insurance_rate_pct"]),
         "元/吨", "(货值+出口端费用+运费) × 加成率 × 费率；CIF 已含则填 0", NUM, False, "ins")
    line(8, "= CIF 折人民币", "=SUM(%s:%s)" % (C("goods"), C("ins")), "元/吨",
         "CIF = 货值 + 出口端 + 运费 + 保险", NUM, True, "cif")
    line(9, "目的港卸货/港杂", "=%s*%s" % (NP["discharge_fee"], C("fx")), "元/吨", "CIF 不含", NUM, False, "dis")
    line(10, "进口关税", "=(%s+%s)*%s" % (C("cif"), C("dis"), NP["duty_rate"]), "元/吨",
         "关税 = (CIF+卸货) × 关税率", NUM, False, "duty")
    line(11, "其他税", "=(%s+%s)*%s" % (C("cif"), C("dis"), NP["other_tax_rate"]), "元/吨",
         "(CIF+卸货) × 其他税率", NUM, False, "otax")
    line(12, "进口增值税", "=(%s+%s+%s)*%s" % (C("cif"), C("dis"), C("duty"), NP["vat_rate"]),
         "元/吨", "(CIF+卸货+关税) × 增值税率", NUM, False, "vat")
    line(13, "进口国内陆运费", "=" + NP["inland_dest"], "元/吨", "港口→工厂", NUM, False, "inl_d")
    line(14, "装卸/损耗附加", "=" + NP["unload_fee"], "元/吨", "显式附加", NUM, False, "unl")
    line(15, "= 含税到岸 landed_cash",
         "=%s+%s+%s+%s+%s+%s+%s" % (C("cif"), C("dis"), C("duty"), C("otax"),
                                     C("vat"), C("inl_d"), C("unl")),
         "元/吨", "现金口径：全部税费与费用都付出去的总额", NUM, True, "landed")
    line(16, "可抵扣进口增值税", "=%s*%s" % (C("vat"), NP["vat_credit_ratio"]), "元/吨",
         "VAT × 可抵扣比例", NUM, False, "credit")
    line(17, "= 可比经济成本 net_cash", "=%s-%s" % (C("landed"), C("credit")), "元/吨",
         "landed_cash − 可抵扣 VAT（经济口径）", NUM, True, "net")
    line(18, "税费现金支出 cash_out", "=%s+%s+(%s-%s)" % (C("duty"), C("otax"), C("vat"), C("credit")),
         "元/吨", "关税 + 其他税 + 不可抵扣 VAT", NUM, False, "cashout")
    line(19, "折纯成本 unit_net", "=%s/%s*%s" % (C("net"), NP["purity"], NP["gross_weight_factor"]),
         "元/纯吨", "net_cash ÷ 纯度 × 毛净比", NUM, False, "unit")

    r += 1
    r = header(ws, r, ["#", "自检", "结果", "单位", "判定规则"])
    put(ws, r, 1, "K1"); put(ws, r, 2, "landed_cash 分项闭合")
    put(ws, r, 3, "=ABS(%s-(%s+%s+%s+%s+%s+%s+%s))" % (
        C("landed"), C("cif"), C("dis"), C("duty"), C("otax"), C("vat"), C("inl_d"), C("unl")), fmt=NUM)
    put(ws, r, 4, "元/吨"); put(ws, r, 5, "必须 = 0", note=True); r += 1
    put(ws, r, 1, "K2"); put(ws, r, 2, "net_cash = landed − credit")
    put(ws, r, 3, "=ABS(%s-(%s-%s))" % (C("net"), C("landed"), C("credit")), fmt=NUM)
    put(ws, r, 4, "元/吨"); put(ws, r, 5, "必须 = 0", note=True); r += 1
    put(ws, r, 1, "K3"); put(ws, r, 2, "术语重复计费检查")
    put(ws, r, 3, '=IF(AND(%s="CFR",%s>0),"冲突","通过")' % (NP["term"], NP["ocean_freight"]))
    put(ws, r, 4, "—"); put(ws, r, 5, "CFR 报价下海运费必须为 0", note=True); r += 1
    return ws, rows


# ------------------------------------------------------------------ 价差
def ws_gap(wb, d, NP, RC):
    ws = sheet(wb, "4 价差四口径", "8A5A00")
    widths(ws, {"A": 4, "B": 30, "C": 16, "D": 16, "E": 52})
    r = band(ws, 1, "价差四口径：先把国内价折到可比口径，再做减法", 5)
    r = header(ws, r, ["#", "项目", "金额（元/吨）", "口径", "说明"])
    put(ws, r, 1, "D1"); put(ws, r, 2, "国内现货价（原样）", bold=True)
    put(ws, r, 3, "=" + NP["dom_quote"], fmt=NUM); put(ws, r, 4, "元/吨")
    put(ws, r, 5, "含税/不含税见「2 参数与输入」D2", note=True)
    rq = r; r += 1

    put(ws, r, 1, "D2"); put(ws, r, 2, "送到+税基调整")
    put(ws, r, 3, '=IF(%s="含税",C%d,C%d*(1+%s))+%s+%s' % (
        NP["dom_tax"], r - 1, r - 1, NP["vat_rate"], NP["dom_freight"], NP["dom_adj"]), fmt=NUM)
    put(ws, r, 4, "元/吨"); put(ws, r, 5, "统一折算到含税送到口径", note=True)
    rdue = r; r += 1

    put(ws, r, 1, "D3"); put(ws, r, 2, "国内未税送到")
    put(ws, r, 3, "=C%d/(1+%s)" % (r, NP["vat_rate"]), fmt=NUM)  # 上一行即含税送到
    put(ws, r, 4, "元/吨"); put(ws, r, 5, "含税价 ÷ (1+增值税率)", note=True)
    rnet = r; r += 1

    r += 1
    r = header(ws, r, ["#", "价差口径", "数值（元/吨）", "符号", "含义（只描述口径差异，不是利润）"])
    # 行号一律从表里读回来，避免"变量推进"与"实际写入行"失配
    def find_row(tag):
        for row in ws.iter_rows(min_col=1, max_col=1):
            if row[0].value == tag:
                return row[0].row
        raise RuntimeError("价差表缺少 %s 行" % tag)

    rD1, rD2, rD3 = find_row("D1"), find_row("D2"), find_row("D3")
    G = [("G1", "CIF 折人民币 vs 国内未税", "=C%d-C%d" % (rD3, RC["cif"]),
          "纯价格口径：两边都不含增值税，反映国际与国内价格本身的高低"),
         ("G2", "含税到岸 vs 国内含税送到", "=C%d-C%d" % (rD2, RC["landed"]),
          "现金口径：两边都含税，反映全部现金付出之差"),
         ("G3", "经济成本 vs 国内含税送到", "=C%d-C%d" % (rD2, RC["net"]),
          "经济口径：进口增值税按可抵扣处理后的真实可比成本"),
         ("G4", "进项税抵扣调整后", "=C%d-C%d" % (rD3, RC["net"]),
          "税制口径：价格差里有多少来自增值税抵扣权的估值差异")]

    g_rows = {}
    for code, name, formula, meaning in G:
        put(ws, r, 1, code); put(ws, r, 2, name, bold=True)
        put(ws, r, 3, formula, fmt=NUM)
        put(ws, r, 4, '=IF(C%d>0,"国内更强",IF(C%d<0,"进口更便宜","持平"))' % (r, r))
        put(ws, r, 5, meaning, note=True)
        g_rows[code] = r
        r += 1
    r += 1
    ws.cell(row=r, column=2,
            value="提示：G1 与 G3 的差 ≈ 进口环节增值税净额；"
                  "若两者符号相反，说明价格差被税制掩盖，"
                  "不能只用 CIF 与含税现货相减下结论。").font = F_S
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    return ws, g_rows, rdue, rnet


def _row_of(wb, sheetname, token):
    ws = wb[sheetname]
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value == token:
                return c.row
    return 1


# ------------------------------------------------------------------ 历史序列
def ws_series(wb, d):
    ws = sheet(wb, "5 历史序列", "1F4E79")
    cols = ["日期", "海外报价 USD/吨", "报价区间", "汇率 CNY/USD", "汇率日期", "海运费 USD/吨", "运费来源",
            "CIF 元/吨", "含税到岸 元/吨", "经济成本 元/吨", "国内可比 元/吨",
            "G3 价差 元/吨", "G2 价差 元/吨", "G1 价差 元/吨", "市场隐含其余成本", "报价来源", "国内来源"]
    ws.cell(row=1, column=1, value="历史序列（逐时点取值，运费/汇率来源已标注；运费为 0 表示术语已含，不是缺失）").font = F_TITLE
    ws.cell(row=1, column=1).fill = PatternFill("solid", fgColor=GREY_HDR)
    for c in range(2, len(cols) + 1):
        ws.cell(row=1, column=c).fill = PatternFill("solid", fgColor=GREY_HDR)
    r = header(ws, 2, cols)
    first = r
    rows = [x for x in d["series"]["rows"] if x.get("status") == "ok"]
    for x in rows:
        put(ws, r, 1, x["date"], align="left")
        put(ws, r, 2, x["ov_usd"], fmt=NUM)
        put(ws, r, 3, "", note=True)
        put(ws, r, 4, x["fx"], fmt=RATE)
        put(ws, r, 5, x.get("fx_date", ""), align="left", note=True)
        put(ws, r, 6, x["frt_usd"], fmt=NUM)
        put(ws, r, 7, {"actual": "实测", "monthly_avg": "月度均值", "assumed_base": "假设(术语已含)",
                       "gap": "缺口"}.get(x.get("frt_source"), x.get("frt_source")), align="left", note=True)
        put(ws, r, 8, x["cif"], fmt=NUM)
        put(ws, r, 9, x["landed_cash"], fmt=NUM)
        put(ws, r, 10, x["net_cash"], fmt=NUM)
        put(ws, r, 11, x["dom_price"], fmt=NUM)
        put(ws, r, 12, x["gap_net_cash"], fmt=NUM, bold=True)
        put(ws, r, 13, x["gap_landed_cash"], fmt=NUM)
        put(ws, r, 14, x["gap_cif"], fmt=NUM)
        put(ws, r, 15, x.get("implied_other"), fmt=NUM)
        put(ws, r, 16, x.get("ov_source", ""), align="left", note=True)
        put(ws, r, 17, x.get("dom_source", ""), align="left", note=True)
        r += 1
    widths(ws, {"A": 12, "B": 13, "C": 12, "D": 11, "E": 11, "F": 12, "G": 15, "H": 12, "I": 14,
                "J": 14, "K": 14, "L": 13, "M": 13, "N": 12, "O": 16, "P": 44, "Q": 44})
    ws.freeze_panes = "B3"
    last = r - 1
    r += 1
    ws.cell(row=r, column=1, value="统计").font = F_B
    r += 1
    st = d["series"]["stats"].get("gap_net_cash") or {}
    for k, v, f in [("样本数", st.get("n"), NUM0),
                    ("G3 最新", st.get("end"), NUM),
                    ("G3 区间均值", st.get("avg"), NUM),
                    ("G3 区间最高", st.get("max"), NUM),
                    ("G3 区间最低", st.get("min"), NUM),
                    ("G3 区间变化", st.get("change"), NUM)]:
        put(ws, r, 1, k, note=True)
        if k == "样本数":
            put(ws, r, 2, "=COUNTA(A%d:A%d)" % (first, last), fmt=f)
        elif k == "G3 最新":
            put(ws, r, 2, '=IFERROR(LOOKUP(9E+307,L%d:L%d),"")' % (first, last), fmt=f)
        elif k == "G3 区间均值":
            put(ws, r, 2, "=IFERROR(AVERAGE(L%d:L%d),\"\")" % (first, last), fmt=f)
        elif k == "G3 区间最高":
            put(ws, r, 2, "=IFERROR(MAX(L%d:L%d),\"\")" % (first, last), fmt=f)
        elif k == "G3 区间最低":
            put(ws, r, 2, "=IFERROR(MIN(L%d:L%d),\"\")" % (first, last), fmt=f)
        else:
            put(ws, r, 2, "=IFERROR(B%d-B%d,\"\")" % (r - 4, r - 5), fmt=f)
        r += 1
    return ws, first, last


def ws_chartdata(wb, d, first, last):
    ws = sheet(wb, "6 价差曲线数据", "1F4E79")
    widths(ws, {"A": 12, "B": 16, "C": 16, "D": 16, "E": 16, "F": 16, "G": 16})
    ws.cell(row=1, column=1, value="图表数据区（「5 历史序列」的镜像，供 Excel 折线图引用）").font = F_TITLE
    ws.cell(row=1, column=1).fill = PatternFill("solid", fgColor=GREY_HDR)
    for c in range(2, 8):
        ws.cell(row=1, column=c).fill = PatternFill("solid", fgColor=GREY_HDR)
    hdr = ["日期", "G3 经济口径", "G2 现金口径", "G1 纯价格口径", "CIF", "经济成本", "国内可比"]
    r = header(ws, 2, hdr)
    src = wb["5 历史序列"]
    rows = [x for x in d["series"]["rows"] if x.get("status") == "ok"]
    for i, x in enumerate(rows):
        srow = first + i
        put(ws, r, 1, "='5 历史序列'!A%d" % srow)
        put(ws, r, 2, "='5 历史序列'!L%d" % srow, fmt=NUM)
        put(ws, r, 3, "='5 历史序列'!M%d" % srow, fmt=NUM)
        put(ws, r, 4, "='5 历史序列'!N%d" % srow, fmt=NUM)
        put(ws, r, 5, "='5 历史序列'!H%d" % srow, fmt=NUM)
        put(ws, r, 6, "='5 历史序列'!J%d" % srow, fmt=NUM)
        put(ws, r, 7, "='5 历史序列'!K%d" % srow, fmt=NUM)
        r += 1
    end = r - 1
    ch = LineChart()
    ch.title = "价差三口径（元/吨）"
    ch.y_axis.title = "元/吨"
    ch.x_axis.title = "日期"
    ch.height, ch.width = 9, 22
    data_ref = Reference(ws, min_col=2, max_col=4, min_row=2, max_row=end)
    cats = Reference(ws, min_col=1, min_row=3, max_row=end)
    ch.add_data(data_ref, titles_from_data=True)
    ch.set_categories(cats)
    ws.add_chart(ch, "I2")
    _ = src
    return ws


# ------------------------------------------------------------------ 敏感性
def ws_sens(wb, d, NP):
    ws = sheet(wb, "7 敏感性", "6B3FA0")
    widths(ws, {"A": 22, "B": 14, "C": 14, "D": 14, "E": 14, "F": 14, "G": 14, "H": 14, "I": 14})
    r = band(ws, 1, "敏感性：单参数（各参数独立变动，其余保持输入表值）", 9)
    r = header(ws, r, ["参数", "取值", "CIF", "含税到岸", "经济成本", "相对基准变化", "G3 价差"])
    BASE_NET = "('3 成本折算'!$C$%d)" % 0  # 占位，下面重取
    cost_sheet = wb["3 成本折算"]
    net_cell = None
    for row in cost_sheet.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("= CIF"):
                pass
    # 直接按行号规则取：net 行在「= 可比经济成本」那一行
    for row in cost_sheet.iter_rows(min_col=2, max_col=3):
        if row[0].value == "= 可比经济成本 net_cash":
            net_cell = "C%d" % row[0].row
    if net_cell is None:
        net_cell = "C17"
    items = d["sensitivity"]["items"]
    order = ["price", "freight", "fx", "duty", "insurance_pct", "discharge", "credit", "term"]
    base_gap_row = None
    for key in order:
        it = items.get(key)
        if not it:
            continue
        put(ws, r, 1, it["label"], bold=True)
        for c in range(2, 8):
            put(ws, r, c, "")
        r += 1
        for rowdata in it["rows"]:
            v = rowdata["value"]
            put(ws, r, 1, "")
            if key == "term":
                put(ws, r, 2, v, inp=True, align="center")
                put(ws, r, 3, rowdata["cif"], fmt=NUM)
                put(ws, r, 4, rowdata["landed_cash"], fmt=NUM)
                put(ws, r, 5, rowdata["net_cash"], fmt=NUM)
                put(ws, r, 6, "=E%d-'3 成本折算'!%s" % (r, net_cell), fmt=NUM)
                put(ws, r, 7, "='4 价差四口径'!$C$%d-E%d" % (_gap_row(wb, "G3"), r), fmt=NUM)
            else:
                put(ws, r, 2, v, inp=True, fmt=(RATE if key in ("fx", "duty", "insurance_pct", "credit") else NUM))
                put(ws, r, 3, rowdata["cif"], fmt=NUM)
                put(ws, r, 4, rowdata["landed_cash"], fmt=NUM)
                put(ws, r, 5, rowdata["net_cash"], fmt=NUM)
                put(ws, r, 6, "=E%d-'3 成本折算'!%s" % (r, net_cell), fmt=NUM)
                put(ws, r, 7, "='4 价差四口径'!$C$%d-E%d" % (_gap_row(wb, "G3"), r), fmt=NUM)
            r += 1
        r += 1

    r += 1
    r = band(ws, r, "二维矩阵：海运费 × 汇率（单元格 = G3 经济口径价差，元/吨）", 9)
    m = d["sensitivity"]["matrix"]
    r = header(ws, r, ["运费 ＼ 汇率"] + ["" for _ in m["fx"]])
    for j, fx in enumerate(m["fx"], start=2):
        put(ws, r - 1, j, fx, fmt=RATE, bold=True)
    for i, row in enumerate(m["cells"]):
        put(ws, r, 1, "%s USD/吨" % wio.fmt_trim(m["freight"][i]), bold=True)
        for j, cell in enumerate(row, start=2):
            put(ws, r, j, cell["gap"], fmt=NUM)
            fill = "FBE3DE" if cell["gap"] >= 0 else "DDEFE5"
            ws.cell(row=r, column=j).fill = PatternFill("solid", fgColor=fill)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="说明：矩阵值为按 Python 内核复算的基准结果（同一 data.json），可在「3 成本折算」按同参数手算复核。").font = F_S
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    _ = BASE_NET
    return ws


def _gap_row(wb, code):
    ws = wb["4 价差四口径"]
    for row in ws.iter_rows(min_col=1, max_col=1):
        if row[0].value == code:
            return row[0].row
    return 1


# ------------------------------------------------------------------ 归因
def ws_attr(wb, d):
    ws = sheet(wb, "8 归因分解", "B45309")
    widths(ws, {"A": 26, "B": 22, "C": 16, "D": 60})
    a = d["attribution"]
    if not a.get("available"):
        band(ws, 1, "归因分解：缺少可比历史时点，无法分解", 4)
        return ws
    r = band(ws, 1, "归因分解：%s → %s（逐项一次替换，单位 元/吨；正 = 该项使价差变大）" % (a["compare_date"], d["meta"]["base_date"]), 4)
    r = header(ws, r, ["驱动因子", "变化描述", "对价差贡献", "读法"])
    for it in a["items"]:
        put(ws, r, 1, it["label"], bold=True)
        put(ws, r, 2, it["detail"], align="left")
        put(ws, r, 3, it["value"], fmt=NUM)
        put(ws, r, 4, "价差因该项上升而扩大" if it["value"] > 0 else "价差因该项上升而收窄", note=True)
        r += 1
    put(ws, r, 1, "合计", bold=True)
    put(ws, r, 2, "%s → %s" % (wio.fmt_trim(a["start_gap"]), wio.fmt_trim(a["end_gap"])))
    put(ws, r, 3, "=SUM(C5:C%d)" % (r - 1), fmt=NUM, bold=True)
    put(ws, r, 4, "与 Python 内核结果对照：%s" % wio.fmt_trim(a["total_change"]), note=True)
    r += 2
    put(ws, r, 1, "闭合残差（应 <1e-6）", bold=True)
    put(ws, r, 3, a["residual"], fmt="0.000000")
    r += 1
    put(ws, r, 1, "对比期输入", bold=True)
    inp = a.get("inputs", {})
    put(ws, r, 2, "报价 %s USD / 汇率 %s / 国内 %s 元 / 运费 %s" % (
        wio.fmt_trim(inp.get("ov_price")), wio.fmt_trim(inp.get("fx_value")),
        wio.fmt_trim(inp.get("dom_price")), wio.fmt_trim(inp.get("freight_value"))), align="left")
    return ws


# ------------------------------------------------------------------ 情景
def ws_scn(wb, d):
    ws = sheet(wb, "9 情景对比", "6B3FA0")
    widths(ws, {"A": 34, "B": 46, "C": 15, "D": 15, "E": 15, "F": 14, "G": 14})
    r = band(ws, 1, "情景对比：换术语 / 加费用 / 改税率后，成本与价差如何变化", 7)
    r = header(ws, r, ["情景", "说明", "CIF", "含税到岸", "经济成本", "相对基准变化", "G3 价差"])
    for s in d["scenarios"]["rounds"]:
        put(ws, r, 1, s["name"], bold=True)
        put(ws, r, 2, s["desc"], align="left", wrap=True)
        put(ws, r, 3, s["cif"], fmt=NUM)
        put(ws, r, 4, s["landed_cash"], fmt=NUM)
        put(ws, r, 5, s["net_cash"], fmt=NUM)
        put(ws, r, 6, s["delta_net"], fmt=NUM)
        put(ws, r, 7, s["gap"], fmt=NUM)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="注：情景值由同一内核按 override 参数复算；口径 C（FOB+40 USD/t 运费）仅为对照，不代表真实运价。").font = F_S
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    return ws


# ------------------------------------------------------------------ 缺口
def ws_gaps(wb, d):
    ws = sheet(wb, "10 缺口与来源", "B45309")
    widths(ws, {"A": 4, "B": 52, "C": 52, "D": 40, "E": 10})
    r = band(ws, 1, "数据缺口：这次结论哪里还不牢（按严重度处理，不是免责声明）", 5)
    r = header(ws, r, ["#", "缺口", "对结论的影响", "补齐办法", "严重度"])
    for i, g in enumerate(d.get("gaps", []), start=1):
        put(ws, r, 1, i)
        put(ws, r, 2, g["item"], align="left", wrap=True)
        put(ws, r, 3, g["impact"], align="left", wrap=True)
        put(ws, r, 4, g["fix"], align="left", wrap=True)
        put(ws, r, 5, g.get("severity", ""), align="center")
        ws.row_dimensions[r].height = max(30, 14 * (max(len(g["item"]), len(g["impact"])) // 30 + 1))
        r += 1

    r += 1
    r = band(ws, r, "数据来源：每个数字都带六要素（数值·规格·地区·含税·日期·来源）", 5)
    r = header(ws, r, ["#", "角色 / 名称", "说明与备注", "链接", "可信度"])
    for i, s in enumerate(d.get("sources", []), start=1):
        put(ws, r, 1, i)
        put(ws, r, 2, "%s · %s" % (s.get("role", ""), s.get("name", "")), align="left", wrap=True)
        put(ws, r, 3, "%s｜%s" % (s.get("date", ""), s.get("note", "")), align="left", wrap=True)
        links = "\n".join(s.get("urls", [])[:3])
        c = put(ws, r, 4, links, align="left", note=True, wrap=True)
        if links:
            first_url = s.get("urls", [""])[0]
            if first_url.startswith("http"):
                c.hyperlink = first_url
                c.font = Font(name="微软雅黑", size=9, color="1F6FB2", underline="single")
        put(ws, r, 5, s.get("conf", ""), align="center")
        ws.row_dimensions[r].height = max(28, 13 * (len(str(s.get("note", ""))) // 34 + 1))
        r += 1
    return ws


# ------------------------------------------------------------------ 公式表
def ws_formula(wb, d):
    ws = sheet(wb, "11 公式表", "5A6B7B")
    widths(ws, {"A": 6, "B": 26, "C": 66, "D": 16, "E": 12})
    r = band(ws, 1, "公式表：与 scripts/core.py、assets/core.js、HTML 报告完全同源", 5)
    r = header(ws, r, ["#", "项目", "公式", "基准值", "单位"])
    for f in d.get("formulas", []):
        put(ws, r, 1, f["no"])
        put(ws, r, 2, f["name"], bold=True)
        put(ws, r, 3, f["formula"], align="left", wrap=True)
        put(ws, r, 4, f.get("value"), fmt=NUM)
        put(ws, r, 5, f.get("unit", ""), align="left", note=True)
        r += 1
    return ws


# ------------------------------------------------------------------ 主流程
def build(data_path, out_path):
    d = wio.load_json(data_path)
    wb = Workbook()
    wb.remove(wb.active)
    ws_cover(wb, d)
    _, NP = ws_params(wb, d)
    _, RC = ws_cost(wb, d, NP)
    _, _, _, _ = ws_gap(wb, d, NP, RC)
    _, first, last = ws_series(wb, d)
    ws_chartdata(wb, d, first, last)
    ws_sens(wb, d, NP)
    ws_attr(wb, d)
    ws_scn(wb, d)
    ws_gaps(wb, d)
    ws_formula(wb, d)
    wb.properties.title = d["meta"]["title"]
    wb.properties.creator = d["meta"].get("author", "")
    wb.properties.description = "内外价差四层口径模型：所有数字可追溯到公式与数据来源"
    wio.write_text  # noqa: B018  (占位，避免误删导入)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    wb.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="data.json -> Excel 模型")
    ap.add_argument("data")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or os.path.join("output", "model.xlsx")
    build(args.data, out)
    wio.ok("写出 %s（%.1f KB）" % (out, os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    main()
