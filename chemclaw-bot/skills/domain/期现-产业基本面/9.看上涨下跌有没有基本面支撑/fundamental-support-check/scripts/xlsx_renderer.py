# -*- coding: utf-8 -*-
"""
xlsx_renderer · 生成 11 表《期现&产业基本面支撑核验工作簿》
================================================================
由 build_report.build_all() 调用。输入为结构化证据数据集 ds（见 build_report.py）。

11 个工作表：
 00_封面 / 01_现货期货 / 02_基差月差 / 03_供需平衡 / 04_库存与贸易 /
 05_成本与利润 / 06_证据分类 / 07_历史序列 / 08_来源清单 / 09_指标规则 / 10_口径与滞后
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, Reference

NAVY, BLUE, LBLUE, GREY = "1F3864", "2E5C9A", "DCE6F1", "F2F2F2"
GREEN, RED, AMBER = "C6EFCE", "FFC7CE", "FFEB9C"

F_TITLE = Font(name="微软雅黑", size=15, bold=True, color="FFFFFF")
F_SUB = Font(name="微软雅黑", size=9, color="404040")
F_HEAD = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
F_BODY = Font(name="微软雅黑", size=9.5, color="1a1a1a")
F_BOLD = Font(name="微软雅黑", size=9.5, bold=True)
F_MISS = Font(name="微软雅黑", size=9.5, italic=True, color="808080")
F_SECT = Font(name="微软雅黑", size=11, bold=True, color=BLUE)
FILL_TITLE = PatternFill("solid", fgColor=NAVY)
FILL_HEAD = PatternFill("solid", fgColor=BLUE)
FILL_GREEN = PatternFill("solid", fgColor=GREEN)
FILL_RED = PatternFill("solid", fgColor=RED)
FILL_AMBER = PatternFill("solid", fgColor=AMBER)
FILL_GREY = PatternFill("solid", fgColor=GREY)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CTR = Alignment(horizontal="center", vertical="center", wrap_text=True)
UP_RED = Font(name="微软雅黑", size=9.5, bold=True, color="C00000")
DN_GREEN = Font(name="微软雅黑", size=9.5, bold=True, color="00703C")


def status_fill(s):
    return {"支撑上涨": FILL_GREEN, "背离": FILL_RED, "数据不足": FILL_AMBER}.get(s, FILL_GREY)


def _title(ws, title, subtitle, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(1, 1, title)
    c.font, c.fill = F_TITLE, FILL_TITLE
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c2 = ws.cell(2, 1, subtitle)
    c2.font, c2.alignment = F_SUB, Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 24


def _head(ws, row, labels, widths=None):
    for i, lab in enumerate(labels, 1):
        c = ws.cell(row, i, lab)
        c.font, c.fill, c.alignment, c.border = F_HEAD, FILL_HEAD, CTR, BORDER
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row + 1, 1)


def _put(ws, r, c, v, num=None, bold=False, align=None, fill=None):
    cell = ws.cell(r, c, v if v is not None else "缺失")
    cell.font = F_MISS if v is None else (F_BOLD if bold else F_BODY)
    cell.border, cell.alignment = BORDER, (align or WRAP)
    if num:
        cell.number_format = num
    if fill:
        cell.fill = fill
    return cell


def render_xlsx(ds, out_path):
    wb = Workbook()
    meta = ds.get("meta", {})
    summ = ds.get("summary", {})
    ev = ds.get("evidence", [])
    cnt = {k: sum(1 for e in ev if e["status"] == k) for k in ("支撑上涨", "背离", "数据不足")}

    # ---------------- 00 封面
    ws = wb.active
    ws.title = "00_封面"
    ws.sheet_view.showGridLines = False
    _title(ws, f"{meta.get('product','品种')} · 上涨行情基本面支撑核验工作簿",
           f"核验窗口 {meta.get('window','')} ｜ 现货 {meta.get('spot_caliber','')} ｜ 期货 {meta.get('fut_caliber','')}", 6)
    ws.cell(4, 1, "报告结构").font = F_SECT
    idx = [("一、价格表现", "现货与期货涨幅、基差、月差、期现结构", "01_现货期货"),
           ("二、现实供给", "产量、产能利用率、装置事件、新增产能、进口", "03_供需平衡"),
           ("三、现实需求", "下游开工、订单、成交", "03_供需平衡"),
           ("四、库存与贸易", "库存水平、变化速度、历史位置", "04_库存与贸易"),
           ("五、成本与利润", "原料、工艺路线成本、加工价差、传导率", "05_成本与利润"),
           ("六、预期指标", "远月定价、持仓、板块共振、地缘、机构预测", "02_基差月差"),
           ("七、证据分类", "四轴 × 支撑/背离/数据不足", "06_证据分类"),
           ("八、历史序列", "全部已披露逐日原始值", "07_历史序列"),
           ("九、来源与规则", "来源清单 + 指标计算规则", "08_来源清单 / 09_指标规则"),
           ("十、口径与滞后", "口径差异与统计滞后", "10_口径与滞后")]
    r = 5
    for a, b, c in idx:
        _put(ws, r, 1, a, bold=True)
        _put(ws, r, 2, b)
        cell = _put(ws, r, 3, "→ " + c)
        cell.hyperlink = f"#'{c.split(' / ')[0]}'!A1"
        cell.font = Font(name="微软雅黑", size=9.5, color="0563C1", underline="single")
        r += 1
    r += 1
    ws.cell(r, 1, "核心核验结论（不含多空方向建议）").font = F_SECT
    r += 1
    for k, v in [("价格是否真实上涨", summ.get("price_verdict", "")),
                 ("驱动结构", summ.get("driver", "")),
                 ("证据配比", f"支撑 {cnt['支撑上涨']} ｜ 背离 {cnt['背离']} ｜ 数据不足 {cnt['数据不足']}"),
                 ("合规声明", summ.get("no_conclusion", "本报告不给出方向建议"))]:
        _put(ws, r, 1, k, bold=True)
        cell = _put(ws, r, 2, v)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        ws.row_dimensions[r].height = 34
        r += 1
    for col, w in zip("ABCDEF", [22, 34, 26, 20, 20, 20]):
        ws.column_dimensions[col].width = w

    # ---------------- 01 现货期货
    ws = wb.create_sheet("01_现货期货")
    _title(ws, "01 · 现货与期货价格表现", "同口径测量涨幅；无法核验的日期明确标注，不做插值", 9)
    ws.cell(4, 1, "A. 窗口涨幅测算").font = F_SECT
    _head(ws, 5, ["口径", "起始日", "起始价", "结束日", "结束价", "涨跌", "涨幅%", "数据状态", "备注"],
          [24, 12, 13, 12, 13, 13, 11, 14, 40])
    r = 6
    for w in ds.get("windows", []):
        _put(ws, r, 1, w["name"], bold=True)
        _put(ws, r, 2, w["start"], align=CTR)
        _put(ws, r, 3, w.get("start_price"), num="#,##0.00")
        _put(ws, r, 4, w["end"], align=CTR)
        _put(ws, r, 5, w.get("end_price"), num="#,##0.00")
        _put(ws, r, 6, w.get("abs_change"), num="#,##0.00")
        _put(ws, r, 7, (w["pct"] / 100 if w.get("pct") is not None else None), num="0.00%")
        _put(ws, r, 8, w.get("status"), align=CTR,
             fill=FILL_GREEN if w.get("status") == "已核验" else FILL_AMBER)
        _put(ws, r, 9, w.get("note", ""))
        r += 1

    r += 1
    ws.cell(r, 1, "B. 期货合约截面").font = F_SECT
    r += 1
    _head(ws, r, ["合约", "开盘", "最低", "最高", "收盘/结算", "涨跌", "成交量(手)", "持仓量(手)", "来源"],
          [12, 11, 11, 11, 13, 10, 13, 13, 10])
    r += 1
    for row in ds.get("fut_raw", []):
        contract, o, lo, hi, cl, ch, vol, oi, src = row
        _put(ws, r, 1, contract, bold=True)
        for i, v in zip((2, 3, 4, 5, 7, 8), (o, lo, hi, cl, vol, oi)):
            _put(ws, r, i, v, num="#,##0")
        cell = _put(ws, r, 6, ch, num="+#,##0;-#,##0")
        if ch is not None:
            cell.font = UP_RED if ch > 0 else DN_GREEN
        _put(ws, r, 9, src, align=CTR)
        r += 1

    # ---------------- 02 基差月差
    ws = wb.create_sheet("02_基差月差")
    _title(ws, "02 · 基差与月差（期现结构）", "基差=现货-期货；正=现货升水。跨口径仅取方向", 8)
    _head(ws, 4, ["日期", "现货", "现货口径", "期货", "合约", "基差", "状态", "说明"],
          [12, 13, 30, 12, 12, 13, 16, 46])
    r = 5
    for b in ds.get("basis", []):
        _put(ws, r, 1, b["date"], align=CTR)
        _put(ws, r, 2, b.get("spot"), num="#,##0.00")
        _put(ws, r, 3, b.get("spot_caliber", ""))
        _put(ws, r, 4, b.get("fut"), num="#,##0")
        _put(ws, r, 5, b.get("contract", ""), align=CTR)
        _put(ws, r, 6, b.get("basis"), num="#,##0.00", bold=True)
        st = str(b.get("status", ""))
        _put(ws, r, 7, st, align=CTR, fill=FILL_GREEN if st.startswith("已核验") else FILL_AMBER)
        _put(ws, r, 8, b.get("note", ""))
        r += 1
    r += 1
    ws.cell(r, 1, "月差结构").font = F_SECT
    r += 1
    _head(ws, r, ["价差", "近月", "远月", "价差", "幅度%", "结构含义"], [20, 12, 12, 12, 11, 50])
    r += 1
    for n, a, b in ds.get("spread", []):
        _put(ws, r, 1, n, bold=True)
        _put(ws, r, 2, a, num="#,##0")
        _put(ws, r, 3, b, num="#,##0")
        _put(ws, r, 4, a - b, num="#,##0")
        _put(ws, r, 5, (a - b) / b, num="0.00%")
        _put(ws, r, 6, "近强远弱（Back）" if a > b else "远强近弱（Contango）")
        r += 1

    # ---------------- 03 供需平衡
    ws = wb.create_sheet("03_供需平衡")
    _title(ws, "03 · 现实供给与现实需求", "缺失项显式标注为『缺失』，零估算填充", 8)
    for label, key in (("A. 现实供给", "supply"), ("B. 现实需求", "demand")):
        r = ws.max_row + 2 if ws.max_row > 1 else 4
        ws.cell(r, 1, label).font = F_SECT
        r += 1
        _head(ws, r, ["项目", "数值", "单位", "日期/周期", "变化", "类别", "方向", "备注"],
              [30, 12, 11, 15, 14, 10, 12, 50])
        for it in ds.get(key, []):
            r += 1
            _put(ws, r, 1, it.get("item"), bold=True)
            _put(ws, r, 2, it.get("value"), num="#,##0.00")
            _put(ws, r, 3, it.get("unit"), align=CTR)
            _put(ws, r, 4, it.get("date"), align=CTR)
            if it.get("change_pct") is not None:
                _put(ws, r, 5, it["change_pct"] / 100, num="+0.00%;-0.00%")
            else:
                _put(ws, r, 5, it.get("change"), num="+#,##0.00;-#,##0.00")
            _put(ws, r, 6, it.get("status"), align=CTR,
                 fill=FILL_GREEN if it.get("status") == "现实" else (FILL_GREY if it.get("status") == "预期" else FILL_AMBER))
            _put(ws, r, 7, it.get("dir"), align=CTR)
            _put(ws, r, 8, it.get("note", ""))

    # ---------------- 04 库存与贸易
    ws = wb.create_sheet("04_库存与贸易")
    _title(ws, "04 · 库存与贸易", "库存四问：口径 / 时点 / 历史位置 / 速率", 9)
    _head(ws, 4, ["项目", "数值", "单位", "日期", "上期", "变化", "变化%", "历史分位", "说明"],
          [30, 12, 9, 12, 11, 12, 11, 12, 50])
    r = 5
    for i in ds.get("inventory", []):
        _put(ws, r, 1, i.get("item"), bold=True)
        _put(ws, r, 2, i.get("value"), num="#,##0.00")
        _put(ws, r, 3, i.get("unit"), align=CTR)
        _put(ws, r, 4, i.get("date"), align=CTR)
        _put(ws, r, 5, i.get("prev"), num="#,##0.00")
        cell = _put(ws, r, 6, i.get("change"), num="+#,##0.00;-#,##0.00")
        if i.get("change") is not None:
            cell.font = UP_RED if i["change"] > 0 else DN_GREEN
        _put(ws, r, 7, i.get("change_pct"), num="+0.00%;-0.00%")
        _put(ws, r, 8, i.get("hist_pctile"), num="0.0")
        _put(ws, r, 9, i.get("note", ""))
        r += 1

    # ---------------- 05 成本与利润
    ws = wb.create_sheet("05_成本与利润")
    _title(ws, "05 · 上游成本与产业链加工价差", "机构推算口径需注明；矛盾口径并列呈现", 8)
    _head(ws, 4, ["项目", "现值", "单位", "日期", "基期值", "变化%", "口径/来源", "备注"],
          [30, 12, 11, 12, 12, 11, 26, 50])
    r = 5
    for c in ds.get("cost", []):
        _put(ws, r, 1, c.get("item"), bold=True)
        _put(ws, r, 2, c.get("value"), num="#,##0.00")
        _put(ws, r, 3, c.get("unit"), align=CTR)
        _put(ws, r, 4, c.get("date"), align=CTR)
        _put(ws, r, 5, c.get("prev"), num="#,##0.00")
        pv = c.get("src_pct") if c.get("src_pct") is not None else c.get("change_pct")
        if pv is not None and abs(pv) <= 1:
            pv *= 100
        cell = _put(ws, r, 6, pv, num="+0.00;-0.00")
        if pv is not None:
            cell.font = UP_RED if pv > 0 else DN_GREEN
        _put(ws, r, 7, c.get("source", ""))
        _put(ws, r, 8, c.get("note", ""))
        r += 1

    # ---------------- 06 证据分类
    ws = wb.create_sheet("06_证据分类")
    _title(ws, "06 · 证据分类与一致性判定", "本表为核心输出：四轴 × 支撑/背离/数据不足", 10)
    _head(ws, 4, ["编号", "主轴", "指标名称", "观测期", "同期变化(实测)", "历史位置", "与价格关系",
                  "证据状态", "等级", "解读"],
          [8, 10, 24, 16, 36, 24, 16, 13, 8, 56])
    r = 5
    for e in ev:
        _put(ws, r, 1, e["id"], bold=True, align=CTR)
        _put(ws, r, 2, e["cls"], align=CTR)
        _put(ws, r, 3, e["name"], bold=True)
        _put(ws, r, 4, e["period"], align=CTR)
        _put(ws, r, 5, e["metric"])
        _put(ws, r, 6, e["hist"])
        _put(ws, r, 7, e["verdict"], align=CTR)
        _put(ws, r, 8, e["status"], align=CTR, fill=status_fill(e["status"]))
        _put(ws, r, 9, e["tier"], align=CTR)
        _put(ws, r, 10, e["comment"])
        r += 1
    ws.auto_filter.ref = f"A4:J{r-1}"
    r += 1
    ws.cell(r, 1, "状态汇总").font = F_SECT
    r += 1
    for i, lab in enumerate(["主轴", "支撑上涨", "背离", "数据不足", "中性/预期", "合计"], 1):
        _put(ws, r, i, lab, bold=True, fill=FILL_HEAD)
    for ax in ["价格", "供给", "需求", "库存", "成本", "预期"]:
        r += 1
        sub = [e for e in ev if e["cls"] == ax]
        _put(ws, r, 1, ax, bold=True)
        _put(ws, r, 2, sum(1 for e in sub if e["status"] == "支撑上涨"), num="0")
        _put(ws, r, 3, sum(1 for e in sub if e["status"] == "背离"), num="0")
        _put(ws, r, 4, sum(1 for e in sub if e["status"] == "数据不足"), num="0")
        _put(ws, r, 5, sum(1 for e in sub if e["status"] not in ("支撑上涨", "背离", "数据不足")), num="0")
        _put(ws, r, 6, len(sub), num="0", bold=True)

    # ---------------- 07 历史序列
    ws = wb.create_sheet("07_历史序列")
    _title(ws, "07 · 历史序列（仅已披露原始值）", "空白=该日无披露，不做插值", 6)
    ser = ds.get("series", {})
    cols = [("pp", "现货主规格", 2), ("upstream", "上游原料", 3), ("cost", "成本项(国际)", 4)]
    present = [c for c in cols if ser.get(c[0])]
    _head(ws, 4, ["日期"] + [c[1] for c in present], [12] + [16] * len(present))
    dates = sorted({d for c in present for d, _ in ser[c[0]]})
    maps = {c[0]: dict(ser[c[0]]) for c in present}
    r = 5
    for d in dates:
        _put(ws, r, 1, d, align=CTR)
        for j, c in enumerate(present, 2):
            _put(ws, r, j, maps[c[0]].get(d), num="#,##0.00")
        r += 1
    last = r - 1
    if present:
        ch = LineChart()
        ch.title = "历史序列走势"
        ch.height, ch.width = 9, 24
        ch.y_axis.title = "价格"
        ch.add_data(Reference(ws, min_col=2, max_col=1 + len(present), min_row=4, max_row=last),
                    titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=5, max_row=last))
        ws.add_chart(ch, f"{get_column_letter(2 + len(present) + 1)}4")

    # ---------------- 08 来源清单
    ws = wb.create_sheet("08_来源清单")
    _title(ws, "08 · 原始来源清单", "A=官方原始 B=机构一手 C=媒体转述 D=测算", 7)
    _head(ws, 4, ["编号", "标题", "发布方", "日期", "等级", "原始数据说明", "链接"], [7, 42, 22, 11, 8, 54, 54])
    r = 5
    for s in ds.get("sources", []):
        _put(ws, r, 1, s["id"], bold=True, align=CTR)
        _put(ws, r, 2, s.get("name"))
        _put(ws, r, 3, s.get("publisher"))
        _put(ws, r, 4, s.get("date"), align=CTR)
        _put(ws, r, 5, s.get("tier"), align=CTR)
        _put(ws, r, 6, s.get("note", ""))
        cell = _put(ws, r, 7, s.get("url"))
        if s.get("url"):
            cell.hyperlink = s["url"]
            cell.font = Font(name="微软雅黑", size=8.5, color="0563C1", underline="single")
        r += 1

    # ---------------- 09 指标规则
    ws = wb.create_sheet("09_指标规则")
    _title(ws, "09 · 指标定义与计算规则（R01–R14）", "跨品种通用，含无期货适配", 6)
    _head(ws, 4, ["编号", "指标", "定义/公式", "判定阈值", "所需数据", "无期货适配"], [7, 18, 38, 44, 24, 34])
    rules = [
        ("R01", "窗口涨幅", "R=(P_end−P_start)/P_start", "|R|≥5% 明显行情；3–5% 温和；<3% 未达门槛", "同口径序列", "同左"),
        ("R02", "历史分位", "PR=(低于样本+0.5×相等)/N", "≥80% 高位；≤20% 低位；N<60 标样本不足", "≥3年序列", "同左"),
        ("R03", "基差", "Basis=Spot−Futures", "正=现货升水；走强+现货涨→现实紧", "同日同口径", "改用区域价差/出厂-市场价差"),
        ("R04", "月差", "Spread=P_near−P_far", ">0 Back 近紧远松；<0 Contango", "两合约", "改用加工价差"),
        ("R05", "库存变化速度", "Δ%=(Inv_t−Inv_t-1)/Inv_t-1", "周环比>+15% 异常（排除假期）", "周度库存", "同左"),
        ("R06", "库存历史位置", "过去N年同周次分位", ">70% 偏高；<30% 偏低", "≥3年周度", "同左"),
        ("R07", "产能利用率", "实际产量/有效产能", "连续↓≥2周→收紧；单周持平不算", "周度开工", "同左"),
        ("R08", "装置事件净效应", "Σ重启−Σ停车−Σ新增检修(万吨/年)", "<0 供给减少；缺产能标数据不足", "装置+产能", "同左"),
        ("R09", "产量同比", "(Q_t−Q_t-12)/Q_t-12", "≤−5% 实质收缩；须查成因", "月度产量", "同左"),
        ("R10", "下游开工率", "下游产量/设计产能", "价格涨而开工降→需求背离", "分下游周度", "同左"),
        ("R11", "加工价差", "Spread=P_下−P_上×单耗", "走阔→需求好；持平+双涨→纯成本传导", "上下游价", "★核心：替代基差"),
        ("R12", "成本传导率", "β=ΔP_下%/ΔC_上%", "0.9–1.1 完全传导；<0.8 受阻；>1.2 需求溢价", "上下游价", "★核心"),
        ("R13", "与价格同步性", "指标方向 vs 价格方向", "同向=支撑；反向=背离；无量=数据不足", "指标变化", "同左"),
        ("R14", "证据分级", "A官方/B机构/C媒体/D测算", "结论仅由A/B支撑；C仅线索；D不单独支撑", "来源元数据", "同左"),
    ]
    r = 5
    for row in rules:
        for i, v in enumerate(row, 1):
            _put(ws, r, i, v, bold=(i == 2), align=CTR if i == 1 else None)
        ws.row_dimensions[r].height = 42
        r += 1

    # ---------------- 10 口径与滞后
    ws = wb.create_sheet("10_口径与滞后")
    _title(ws, "10 · 口径差异与统计滞后", "不同指标观测窗口不同，不能互相证伪", 3)
    _head(ws, 4, ["议题", "说明", "发布节奏"], [18, 90, 26])
    r = 5
    for c in ds.get("caliber", []):
        _put(ws, r, 1, c.get("topic"), bold=True)
        _put(ws, r, 2, c.get("text"))
        _put(ws, r, 3, c.get("cadence", ""), align=CTR)
        ws.row_dimensions[r].height = 40
        r += 1

    # ---------------- 尾部：一致/背离/无法核实
    ws = wb.create_sheet("11_一致背离缺失")
    _title(ws, "11 · 一致 / 背离 / 无法核实", "结论归类，不含方向", 2)
    r = 4
    for label, key, fill in (("✅ 支持涨势的证据", "support", FILL_GREEN),
                             ("⚠️ 存在背离的证据", "diverge", FILL_RED),
                             ("❔ 尚无法核实的部分", "missing", FILL_AMBER)):
        c = ws.cell(r, 1, label)
        c.font, c.fill = F_BOLD, fill
        r += 1
        for x in summ.get(key, []):
            _put(ws, r, 1, x)
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
            r += 1
        r += 1
    _put(ws, r, 1, "合规声明", bold=True)
    _put(ws, r, 2, summ.get("no_conclusion", ""))
    ws.column_dimensions["A"].width = 70
    ws.column_dimensions["B"].width = 50

    for s in wb.worksheets:
        s.sheet_properties.tabColor = BLUE
    wb["00_封面"].sheet_properties.tabColor = NAVY
    wb.save(out_path)
    return out_path
