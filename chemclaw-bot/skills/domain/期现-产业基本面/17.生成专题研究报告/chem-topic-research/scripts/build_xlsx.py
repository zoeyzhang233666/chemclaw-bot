# -*- coding: utf-8 -*-
"""
build_xlsx.py —— 把 case.json 渲染成 13 页 Excel 工作簿（可追溯的数据底稿）。

工作表顺序是"从原始到结论"的证据链：
  00_使用说明    口径、图例、如何用本簿复核报告
  01_证据索引    每条来源/缺口 → 被谁引用
  02_原始数据    所有时间序列（价格/库存/产量/产能/平衡表…）
  03_企业产能    企业集团产能明细 + CR5 核对
  04_项目台账    在建/新投/退出项目，含状态依据与证据强度
  05_价格数据    价格点位 + 年度均价 + 关键阈值
  06_产业指标    需求结构、日熔量、宏观指标
  07_计算结果    每条结论背后的公式、参数、取值与结果
  08_结论          结论分级、置信度、反证条件
  09_关键变量    监测清单与阈值
  10_资料缺口    缺什么、为什么、影响、下一步
  11_章节大纲    报告章节与数据依赖（供复核研究设计）
  12_质量自检    自动核对结果（数量、引用完整性、结论可追溯）

用法
----
  python build_xlsx.py <case.json> --out <工作簿.xlsx>
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:  # pragma: no cover
    raise SystemExit("需要 openpyxl：pip install openpyxl")

# ---------------- 视觉规范 ----------------
NAVY = "1F3864"
BLUE = "2E5C9A"
LIGHT = "DCE6F1"
LIGHTER = "EEF3FA"
AMBER = "FCE4B6"
RED = "F8D7DA"
GREEN = "D6F0DE"
GREY = "F2F2F2"
WHITE = "FFFFFF"

TYPE_FILL = {"事实": "D6E4F7", "计算": "D6F0DE", "解释": "E6E0FA", "判断": "FDF0D5"}
CONF_FILL = {"高": GREEN, "中": "EAF4FF", "中低": AMBER, "低": RED}
SEV_FILL = {"high": RED, "medium": AMBER, "low": GREEN}
STATUS_FILL = {"已投产": GREEN, "在建": AMBER, "规划": "E6E0FA", "退出": GREY, "暂停": RED}

THIN = Side(style="thin", color="BFC9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FONT = "微软雅黑"


def style_header(ws, row=1, ncols=None, fill=NAVY):
    ncols = ncols or ws.max_column
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, color=WHITE, size=10)
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 30


def style_body(ws, start=2, ncols=None, num_cols=(), wrap_cols=()):
    ncols = ncols or ws.max_column
    for r in range(start, ws.max_row + 1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = Font(name=FONT, size=9.5, color="1A1A1A")
            cell.border = BORDER
            cell.alignment = Alignment(
                horizontal="right" if c in num_cols else "left",
                vertical="top", wrap_text=(c in wrap_cols or c not in num_cols))


def widths(ws, mapping):
    for col, w in mapping.items():
        ws.column_dimensions[col].width = w


def title_block(ws, title, subtitle, span):
    """每个 sheet 顶部：标题 + 说明条（占用第 1-3 行）。"""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    c = ws.cell(row=1, column=1, value=title)
    c.font = Font(name=FONT, bold=True, size=14, color=NAVY)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 26
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
    c2 = ws.cell(row=2, column=1, value=subtitle)
    c2.font = Font(name=FONT, size=9.5, color="4A5568")
    c2.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[2].height = 30
    for cc in range(1, span + 1):
        ws.cell(row=3, column=cc).fill = PatternFill("solid", fgColor=LIGHT)
    ws.row_dimensions[3].height = 4


def _cell(v):
    """把 list/tuple/dict 等复合值转成可写入单元格的文本。"""
    if isinstance(v, (list, tuple)):
        return "、".join(str(x) for x in v)
    if isinstance(v, dict):
        return "；".join("%s=%s" % (k, v[k]) for k in v)
    return v


def write_sheet(wb, name, title, subtitle, headers, rows, num_cols=(), wrap_cols=(),
                col_widths=None, header_row=4, note_row=True):
    ws = wb.create_sheet(name)
    span = max(len(headers), 4)
    title_block(ws, title, subtitle, span)
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i, value=h)
    style_header(ws, header_row, len(headers))
    for r_i, row in enumerate(rows, start=header_row + 1):
        for c_i, v in enumerate(row, start=1):
            ws.cell(row=r_i, column=c_i, value=_cell(v))
    if rows:
        style_body(ws, header_row + 1, len(headers), num_cols, wrap_cols)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    ws.auto_filter.ref = "A%d:%s%d" % (header_row, get_column_letter(len(headers)),
                                       max(header_row + 1, header_row + len(rows)))
    if col_widths:
        widths(ws, col_widths)
    return ws


# --------------------------------------------------------------------------
def sheet_readme(wb, case, stats):
    meta = case.get("meta") or {}
    prof = C.audience_profile(case)
    rows = [
        ["报告标题", meta.get("title", "")],
        ["报告版本 / 报告日", "%s / %s" % (meta.get("version", ""), meta.get("report_date", ""))],
        ["数据截止", meta.get("data_cutoff", "")],
        ["研究范围", meta.get("horizon", "")],
        ["产品 / 形态", "%s / %s" % (meta.get("product_cn", ""), meta.get("product_shape", ""))],
        ["主题类型", meta.get("topic_type", "")],
        ["受众", "%s（%s）" % (prof.get("label", ""), prof.get("audience_key", ""))],
        ["结论数量", stats["conclusions"]],
        ["计算数量", stats["calcs"]],
        ["证据（来源）数量", stats["sources"]],
        ["资料缺口数量", stats["gaps"]],
        ["项目台账行数", stats["projects"]],
        ["企业行数", stats["companies"]],
        ["免责声明", meta.get("disclaimer", "")],
    ]
    ws = write_sheet(wb, "00_使用说明", "使用说明：这是一本可复核的数据底稿",
                     "本工作簿与 HTML 专题报告同源（同一份 case.json）。所有数字都可在 02~06 中找到原始行，"
                     "并由 07 的计算过程与 01 的证据索引追溯到出处。",
                     ["项目", "内容"], rows, wrap_cols=(2,), col_widths={"A": 22, "B": 110})

    start = ws.max_row + 2
    guide = [
        ["页签", "内容", "怎么用"],
        ["01_证据索引", "每条来源/缺口的 ID、层级、被引用位置", "复核结论时先看引用位置，再打开 02~06 的原始行"],
        ["02_原始数据", "产能结构、供需平衡表、周产量、产业链等全部序列", "图表“查看原始数据”弹出的正是这些行"],
        ["03_企业产能", "企业集团产能明细与 CR5 构成", "核对集中度与集团口径"],
        ["04_项目台账", "在建/新投/退出项目，含状态依据与证据强度", "判断“预计投产≠新增供给”的核心底表"],
        ["05_价格数据", "价格点位、年度均价、阈值", "价格口径不同，不要跨表相减"],
        ["06_产业指标", "需求结构、日熔量、宏观指标", "需求侧约束的事实基础"],
        ["07_计算结果", "公式、参数、结果、口径说明", "每条结论都能在这里找到复算路径"],
        ["08_结论", "结论分级、置信度、反证条件", "判断类结论必须读反证条件"],
        ["09_关键变量", "带阈值的监测清单", "用于下一次更新"],
        ["10_资料缺口", "缺什么、为什么缺、影响、下一步", "缺口不得用估算替代"],
        ["11_章节大纲", "报告章节与研究设计", "修改报告结构时改这里"],
        ["12_质量自检", "自动核对的通过/失败项", "交付前必须全部 PASS"],
    ]
    for i, h in enumerate(guide[0], start=1):
        ws.cell(row=start, column=i, value=h)
    style_header(ws, start, 3, fill=BLUE)
    for r_i, row in enumerate(guide[1:], start=start + 1):
        for c_i, v in enumerate(row, start=1):
            ws.cell(row=r_i, column=c_i, value=v)
    style_body(ws, start + 1, 3, wrap_cols=(2, 3))

    legend_start = ws.max_row + 2
    legend = [
        ["字段/标记", "含义"],
        ["类型=事实", "可直接引用来源的陈述"],
        ["类型=计算", "可由 07 公式复算的数字"],
        ["类型=解释", "基于事实的机理说明，可能有其他解释"],
        ["类型=判断", "依赖假设的结论，必须附带反证条件"],
        ["置信度 高/中/低", "对结论成立可能性的主观刻度，不是统计概率"],
        ["证据强度 A/B/C", "A=企业公告或官方统计；B=行业媒体引用第三方数据；C=研报转述或单一来源"],
        ["状态=已投产/在建/规划/退出", "项目核验的三级状态，只有“已投产”计入已发生供给"],
        ["缺口 severity", "high=影响核心结论；medium=影响幅度；low=影响表述"],
    ]
    for i, h in enumerate(legend[0], start=1):
        ws.cell(row=legend_start, column=i, value=h)
    style_header(ws, legend_start, 2, fill=BLUE)
    for r_i, row in enumerate(legend[1:], start=legend_start + 1):
        for c_i, v in enumerate(row, start=1):
            ws.cell(row=r_i, column=c_i, value=v)
    style_body(ws, legend_start + 1, 2, wrap_cols=(2,))
    ws.sheet_view.showGridLines = False


def sheet_evidence(wb, case):
    idx = C.build_evidence_index(case)
    rows = []
    for e in idx:
        rows.append([e["id"], "来源" if e["kind"] == "source" else ("缺口" if e["kind"] == "gap" else "未登记"),
                     e["what"], e["tier"], len(e["refs"]), "；".join(e["refs"]), e["url"]])
    ws = write_sheet(wb, "01_证据索引", "证据索引：来源与缺口 → 被引用处",
                     "凡是断言里出现的 S/G 编号都必须在本表登记。若某行“引用次数”为 0，说明该来源未被使用；"
                     "若某处引用了未登记 ID，12_质量自检 会报错。",
                     ["ID", "类型", "内容", "层级/严重度", "引用次数", "被引用位置", "链接"],
                     rows, num_cols=(5,), wrap_cols=(3, 6, 7),
                     col_widths={"A": 9, "B": 8, "C": 58, "D": 10, "E": 8, "F": 62, "G": 52})
    for r in range(5, ws.max_row + 1):
        kind = ws.cell(row=r, column=2).value
        if kind == "缺口":
            ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=RED)
        elif kind == "未登记":
            ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=AMBER)
        url = ws.cell(row=r, column=7).value
        if url:
            ws.cell(row=r, column=7).hyperlink = url
            ws.cell(row=r, column=7).font = Font(name=FONT, size=9, color="0563C1", underline="single")


def _series_rows(case):
    """把 case 中所有时间序列摊平成 (数据集, 日期/年份, 指标, 数值, 口径/备注, 来源) 行。"""
    out = []

    def add(ds, period, metric, value, note, source):
        out.append([ds, period, metric, value, note or "", source or ""])

    cs = case.get("capacity_structure") or {}
    for r in cs.get("rows") or []:
        add("capacity_structure", r.get("year"), "总产能(万吨/年)", r.get("total"), r.get("note"), "")
    for r in cs.get("shares") or []:
        for b in cs.get("bands") or []:
            if r.get(b) is not None:
                add("capacity_structure.shares", r.get("year"), b + "占比(%)", r.get(b), r.get("note"),
                    cs.get("source"))
    for key, label_map in (
        ("cr5", {"value": "CR5集中度(%)"}),
        ("supply_demand", {"supply": "产量/供给(万吨)", "demand": "需求(万吨)",
                           "export": "出口(万吨)", "import": "进口(万吨)"}),
        ("price_history", {"shahe": "沙河重碱年均价(元/吨)"}),
        ("price_points", {"value": "价格"}),
        ("inventory", {"total": "库存合计(万吨)", "heavy": "重碱库存(万吨)", "light": "轻碱库存(万吨)"}),
        ("output_weekly", {"output": "周产量(万吨)", "util": "开工率(%)"}),
        ("demand_structure", {"share": "消费占比(%)"}),
        ("glass_runrate", {"float_tpd": "浮法在产日熔(吨/日)", "pv_tpd": "光伏在产日熔(吨/日)"}),
        ("profit", {"profit": "利润(元/吨)"}),
        ("cost_curve", {"low": "成本下限(元/吨)", "high": "成本上限(元/吨)", "share": "产能占比(%)"}),
        ("macro", {"value": "数值"}),
    ):
        for r in case.get(key) or []:
            period = r.get("year") or r.get("date") or r.get("label") or ""
            for field, metric in label_map.items():
                if r.get(field) is None:
                    continue
                name = metric
                if key == "price_points":
                    name = r.get("item", "价格")
                if key in ("profit", "cost_curve", "demand_structure", "cr5", "macro"):
                    name = "%s·%s" % (r.get("route") or r.get("process") or r.get("name") or r.get("year"), metric)
                note = r.get("note") or r.get("basis") or r.get("quality") or r.get("assumption") or ""
                add(key, period, name, r.get(field), note, r.get("source"))
    return out


def sheet_raw(wb, case):
    rows = _series_rows(case)
    ws = write_sheet(wb, "02_原始数据", "原始数据：全部时间序列（与报告图表一一对应）",
                     "“数据集”列对应 case.json 中的 data_key。同一指标可能来自不同机构，口径差异写在“口径/备注”列，"
                     "不得直接跨口径相减。空值表示未获取（对应 10_资料缺口），不是 0。",
                     ["数据集(data_key)", "期间", "指标", "数值", "单位/口径备注", "来源ID"],
                     rows, num_cols=(4,), wrap_cols=(1, 3, 5),
                     col_widths={"A": 26, "B": 14, "C": 34, "D": 13, "E": 48, "F": 12})
    for r in range(5, ws.max_row + 1):
        src = str(ws.cell(row=r, column=6).value or "")
        if "G" in src:
            ws.cell(row=r, column=6).fill = PatternFill("solid", fgColor=RED)


def sheet_companies(wb, case):
    rows = []
    for c in case.get("companies") or []:
        rows.append([c.get("group"), c.get("company"), c.get("region"), c.get("province"),
                     c.get("city"), c.get("process"), c.get("capacity"), c.get("capacity_year"),
                     c.get("cost_level"), c.get("listed"), c.get("cap_note"), c.get("source")])
    total = sum(float(c.get("capacity") or 0) for c in case.get("companies") or [])
    cap_total = (case.get("capacity_structure") or {}).get("rows") or []
    latest = cap_total[-1].get("total") if cap_total else None
    rows.append(["合计（本表，含重复口径提示）", "", "", "", "", "", total, "", "", "",
                 "本表为公开信息拼合，非全量装置清单（见缺口 G01）；合计包含青海集群等估算口径",
                 ""])
    if latest:
        rows.append(["占全国总产能比重", "", "", "", "", "", round(total / latest * 100, 1), latest,
                     "%", "", "合计/最新总产能；因口径重叠仅作参考", ""])
    ws = write_sheet(wb, "03_企业产能", "企业产能：集团、主体、区域、工艺与成本档位",
                     "产能为设计产能（万吨/年），年份口径写在“产能年份”。青海盐湖系为集群估算值，"
                     "与其他单企业行存在口径差异，见缺口 G01。",
                     ["集团", "主体", "区域", "省", "城市", "工艺", "产能(万吨/年)", "产能年份",
                      "成本档位", "上市代码", "备注", "来源ID"],
                     rows, num_cols=(7, 8), wrap_cols=(2, 11),
                     col_widths={"A": 26, "B": 34, "C": 8, "D": 10, "E": 12, "F": 16,
                                 "G": 13, "H": 10, "I": 14, "J": 16, "K": 60, "L": 14})
    for r in range(5, 5 + len(case.get("companies") or [])):
        cl = ws.cell(row=r, column=9).value or ""
        if "低" in cl:
            ws.cell(row=r, column=9).fill = PatternFill("solid", fgColor=GREEN)
        elif "高" in cl:
            ws.cell(row=r, column=9).fill = PatternFill("solid", fgColor=RED)
        elif "中" in cl:
            ws.cell(row=r, column=9).fill = PatternFill("solid", fgColor=AMBER)
    ws.cell(row=ws.max_row - 1, column=1).font = Font(name=FONT, bold=True, size=9.5)


def sheet_projects(wb, case):
    rows = []
    for p in case.get("projects") or []:
        rows.append([p.get("id"), p.get("name"), p.get("company"), p.get("region"), p.get("province"),
                     p.get("process"), p.get("capacity"), p.get("start"), p.get("plan_date"),
                     p.get("actual_date"), p.get("status"), p.get("status_basis"), p.get("evidence"),
                     p.get("strength"), "是" if p.get("net_add") else "否", p.get("for_exit"),
                     p.get("note")])
    ws = write_sheet(wb, "04_项目台账", "项目台账：在建、新投产、退出（状态必须给出依据）",
                     "“状态”只认三类：已投产（有投产月份依据）、在建（已开工未点火）、规划（公告/备案，投产在 2 年以上）。"
                     "“是否净新增”为否时，名义产能必须扣减搬迁/置换部分。",
                     ["ID", "项目", "企业", "区域", "省", "工艺", "名义产能(万吨/年)", "开工",
                      "计划投产", "实际/预计", "状态", "状态依据", "证据", "证据强度", "净新增?", "替代对象", "备注"],
                     rows, num_cols=(7,), wrap_cols=(2, 3, 12, 17),
                     col_widths={"A": 7, "B": 34, "C": 24, "D": 8, "E": 10, "F": 12, "G": 13,
                                 "H": 10, "I": 11, "J": 11, "K": 9, "L": 52, "M": 12,
                                 "N": 8, "O": 8, "P": 12, "Q": 40})
    for r in range(5, 5 + len(case.get("projects") or [])):
        st = ws.cell(row=r, column=11).value
        if st in STATUS_FILL:
            ws.cell(row=r, column=11).fill = PatternFill("solid", fgColor=STATUS_FILL[st])
    # 汇总行
    agg_row = ws.max_row + 2
    ws.cell(row=agg_row, column=1, value="按状态汇总")
    ws.cell(row=agg_row, column=1).font = Font(name=FONT, bold=True, size=10, color=NAVY)
    for i, h in enumerate(["状态", "项目数", "名义产能合计(万吨/年)"], start=1):
        ws.cell(row=agg_row + 1, column=i, value=h)
    style_header(ws, agg_row + 1, 3, fill=BLUE)
    seen = []
    for s in ("已投产", "在建", "规划", "退出"):
        ps = [p for p in case.get("projects") or [] if p.get("status") == s]
        if not ps:
            continue
        seen.append(s)
        ws.cell(row=agg_row + 1 + len(seen), column=1, value=s)
        ws.cell(row=agg_row + 1 + len(seen), column=2, value=len(ps))
        ws.cell(row=agg_row + 1 + len(seen), column=3, value=sum(float(p.get("capacity") or 0) for p in ps))
    style_body(ws, agg_row + 2, 3, num_cols=(2, 3))


def sheet_prices(wb, case):
    rows = []
    for p in case.get("price_points") or []:
        rows.append([p.get("date"), p.get("item"), p.get("value"), "元/吨",
                     (C.source_index(case).get(p.get("source"), {}) or {}).get("note", ""), p.get("source")])
    for p in case.get("price_history") or []:
        rows.append([str(p.get("year")), "沙河重碱年均价", p.get("shahe"), "元/吨", "年均价，口径同 S02", "S02"])
    ws = write_sheet(wb, "05_价格数据", "价格数据：现货点位与年度均价（口径必须并列）",
                     "不同机构、不同区域、不同规格的价格不可直接相减。“期间”列区分日频点位与年均价。",
                     ["期间", "价格品名", "数值", "单位", "口径", "来源ID"],
                     rows, num_cols=(3,), wrap_cols=(2, 5),
                     col_widths={"A": 14, "B": 34, "C": 12, "D": 9, "E": 58, "F": 10})
    # 关键阈值
    s = ws.max_row + 2
    th = [["参考阈值", "数值", "含义"],
          ["天然碱完全成本", "700–800", "低于此价，行业整体亏损"],
          ["联碱完全成本", "1050–1200", "5 月重碱利润一度转正"],
          ["氨碱完全成本", "1200–1300", "现价已低于下沿约 137 元/吨"],
          ["现金成本（估算）", "约 900–1000", "现金流分水岭，低于此价才会出现被动停车"]]
    for i, h in enumerate(th[0], start=1):
        ws.cell(row=s, column=i, value=h)
    style_header(ws, s, 3, fill=BLUE)
    for r_i, row in enumerate(th[1:], start=s + 1):
        for c_i, v in enumerate(row, start=1):
            ws.cell(row=r_i, column=c_i, value=v)
    style_body(ws, s + 1, 3, wrap_cols=(1, 3))


def sheet_indicators(wb, case):
    rows = []
    for d in case.get("demand_structure") or []:
        rows.append(["需求结构", d.get("name"), d.get("share"), "%", "", d.get("source")])
    for g in case.get("glass_runrate") or []:
        rows.append(["玻璃日熔量", "浮法在产日熔", g.get("float_tpd"), "吨/日", g.get("note"), g.get("source")])
        if g.get("pv_tpd") is not None:
            rows.append(["玻璃日熔量", "光伏在产日熔", g.get("pv_tpd"), "吨/日", g.get("note"), g.get("source")])
    for m in case.get("macro") or []:
        rows.append(["宏观/行业", m.get("name"), m.get("value"), m.get("unit"),
                     "%s %s" % (m.get("date", ""), m.get("note") or ""), m.get("source")])
    ws = write_sheet(wb, "06_产业指标", "产业指标：下游结构、日熔量、宏观与出口",
                     "用于回答“需求端能否吸收新增供给”。空白表示该期数据未取得（见缺口 G04）。",
                     ["类别", "指标", "数值", "单位", "期间/口径", "来源ID"],
                     rows, num_cols=(3,), wrap_cols=(2, 5),
                     col_widths={"A": 14, "B": 34, "C": 12, "D": 10, "E": 54, "F": 10})


def sheet_calcs(wb, case):
    rows = []
    for c in case.get("calculations") or []:
        rows.append([c.get("id"), c.get("title"), c.get("statement_type"), c.get("formula"),
                     c.get("inputs"), c.get("output"), c.get("result_note"), c.get("evidence")])
    ws = write_sheet(wb, "07_计算结果", "计算结果：每条结论背后的公式与参数",
                     "“输出”是报告引用的数字；“口径说明”交代假设强度。若参数变更，请从“输入”改起，再更新报告。",
                     ["计算ID", "计算项", "类型", "公式", "输入参数", "输出/结果", "口径与置信说明", "证据"],
                     rows, wrap_cols=(2, 4, 5, 6, 7),
                     col_widths={"A": 11, "B": 30, "C": 8, "D": 48, "E": 62, "F": 40, "G": 54, "H": 14})
    for r in range(5, 5 + len(case.get("calculations") or [])):
        t = ws.cell(row=r, column=3).value
        if t in TYPE_FILL:
            ws.cell(row=r, column=3).fill = PatternFill("solid", fgColor=TYPE_FILL[t])


def sheet_conclusions(wb, case):
    rows = []
    for c in case.get("conclusions") or []:
        rows.append([c.get("rank"), c.get("id"), c.get("type"), c.get("confidence"), c.get("text"),
                     len(c.get("evidence") or []), c.get("evidence"), c.get("calcs"),
                     c.get("falsify"), c.get("audience_note")])
    ws = write_sheet(wb, "08_结论", "结论：分级、置信度、证据、计算与反证条件",
                     "“类型”决定你该怎么用这条结论：事实可直接引用；计算可复算；解释可能有其他机理；判断必须读反证条件。",
                     ["序号", "ID", "类型", "置信度", "结论", "证据数", "证据ID", "计算ID", "反证条件", "受众提示"],
                     rows, num_cols=(1, 6), wrap_cols=(5, 9, 10),
                     col_widths={"A": 6, "B": 8, "C": 7, "D": 8, "E": 72, "F": 6, "G": 16,
                                 "H": 16, "I": 62, "J": 36})
    for r in range(5, 5 + len(case.get("conclusions") or [])):
        t = ws.cell(row=r, column=3).value
        cf = ws.cell(row=r, column=4).value
        if t in TYPE_FILL:
            ws.cell(row=r, column=3).fill = PatternFill("solid", fgColor=TYPE_FILL[t])
        if cf in CONF_FILL:
            ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor=CONF_FILL[cf])


def sheet_variables(wb, case):
    rows = []
    for v in case.get("key_variables") or []:
        rows.append([v.get("id"), v.get("name"), v.get("type"), v.get("watch"), v.get("threshold"),
                     v.get("frequency"), v.get("impact"), v.get("source")])
    ws = write_sheet(wb, "09_关键变量", "关键变量：带阈值的监测清单",
                     "阈值用于判断“是否需要重估结论”，不是交易信号。频率指建议的更新节奏。",
                     ["ID", "变量", "类别", "观察什么", "阈值/触发条件", "频率", "对结论影响", "来源"],
                     rows, wrap_cols=(2, 4, 5), col_widths={"A": 7, "B": 26, "C": 9, "D": 50,
                                                            "E": 52, "F": 7, "G": 10, "H": 12})
    for r in range(5, 5 + len(case.get("key_variables") or [])):
        if ws.cell(row=r, column=7).value == "高":
            ws.cell(row=r, column=7).fill = PatternFill("solid", fgColor=AMBER)


def sheet_gaps(wb, case):
    rows = []
    for g in case.get("data_gaps") or []:
        rows.append([g.get("id"), g.get("topic"), g.get("missing"), g.get("why"), g.get("impact"),
                     g.get("workaround"), g.get("severity"), g.get("next_step")])
    ws = write_sheet(wb, "10_资料缺口", "资料缺口：缺什么、为什么、影响多大、下一步怎么补",
                     "缺口必须在报告正文中显式标注，不得用估算或通用描述填补。severity=high 的缺口会影响核心结论。",
                     ["ID", "主题", "缺什么", "为什么缺", "对结论的影响", "当前处理", "严重度", "下一步"],
                     rows, wrap_cols=(2, 3, 4, 5, 6, 8),
                     col_widths={"A": 7, "B": 20, "C": 46, "D": 40, "E": 44, "F": 34, "G": 9, "H": 34})
    for r in range(5, 5 + len(case.get("data_gaps") or [])):
        sv = ws.cell(row=r, column=7).value
        if sv in SEV_FILL:
            ws.cell(row=r, column=7).fill = PatternFill("solid", fgColor=SEV_FILL[sv])


def sheet_outline(wb, case):
    rows = []
    for s in case.get("sections") or []:
        deps = []
        for b in s.get("blocks") or []:
            if b.get("data_key"):
                deps.append(b["data_key"])
            if b.get("rows_key"):
                deps.append(b["rows_key"])
            if b.get("type") == "calc":
                deps.append("calc:" + str(b.get("calc_id")))
        rows.append([s.get("no"), s.get("id"), s.get("pack"), C.SECTION_PACKS.get(s.get("pack"), ""),
                     s.get("title"), s.get("audience_weight", ""), len(s.get("blocks") or []),
                     "、".join(sorted(set(deps)))])
    ws = write_sheet(wb, "11_章节大纲", "章节大纲：报告结构、章节包与数据依赖",
                     "“受众权重”列出该章节对不同受众的优先级；修改报告结构时，先改 case.json 的 sections，再重新生成。",
                     ["序号", "章节ID", "章节包", "包含义", "章节标题", "受众权重", "区块数", "依赖数据"],
                     rows, num_cols=(7,), wrap_cols=(5, 8),
                     col_widths={"A": 6, "B": 8, "C": 18, "D": 26, "E": 40, "F": 28, "G": 8, "H": 56})
    s2 = ws.max_row + 2
    ws.cell(row=s2, column=1, value="研究问题与回答状态").font = Font(name=FONT, bold=True, size=11, color=NAVY)
    for i, h in enumerate(["问题ID", "问题", "状态", "说明"], start=1):
        ws.cell(row=s2 + 1, column=i, value=h)
    style_header(ws, s2 + 1, 4, fill=BLUE)
    for r_i, q in enumerate((case.get("research_brief") or {}).get("questions") or [], start=s2 + 2):
        ws.cell(row=r_i, column=1, value=q.get("id"))
        ws.cell(row=r_i, column=2, value=q.get("question"))
        ws.cell(row=r_i, column=3, value={"yes": "已回答", "partly": "部分回答"}.get(q.get("answered"), "未回答"))
        ws.cell(row=r_i, column=4, value=q.get("note"))
    style_body(ws, s2 + 2, 4, wrap_cols=(2, 4))


def sheet_qc(wb, case, checks):
    rows = [[("PASS" if ok else "FAIL"), name, detail] for name, ok, detail in checks]
    ws = write_sheet(wb, "12_质量自检", "质量自检：交付前必须全部 PASS",
                     "自动检查项覆盖：引用完整性、结论可追溯、状态依据、缺口登记、数量约束。FAIL 项必须修复后重新生成。",
                     ["结果", "检查项", "说明"], rows, wrap_cols=(2, 3),
                     col_widths={"A": 8, "B": 42, "C": 96})
    for r in range(5, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=GREEN if v == "PASS" else RED)
        ws.cell(row=r, column=1).font = Font(name=FONT, bold=True, size=9.5,
                                             color="1E6B3A" if v == "PASS" else "9B1C2C")


def run_checks(case):
    errs, warns = C.validate(case)
    src = set(C.source_index(case))
    gaps = set(C.gap_index(case))
    calcs = set(C.calc_index(case))
    checks = []

    def chk(name, ok, detail):
        checks.append((name, bool(ok), detail))

    chk("case 结构校验", not errs, "错误 %d 项；警告 %d 项%s" % (len(errs), len(warns), ("：" + "；".join(errs[:3])) if errs else ""))
    conc = case.get("conclusions") or []
    chk("结论全部可追溯", all(c.get("evidence") for c in conc) if conc else False,
        "%d 条结论，均有证据 ID" % len(conc))
    chk("判断/解释类结论含反证条件",
        all(c.get("falsify") for c in conc if c.get("type") in ("判断", "解释")),
        "判断 %d 条、解释 %d 条" % (sum(1 for c in conc if c.get("type") == "判断"),
                                  sum(1 for c in conc if c.get("type") == "解释")))
    chk("结论引用的计算均存在", all(all(x in calcs for x in (c.get("calcs") or [])) for c in conc),
        "计算表共 %d 条" % len(calcs))
    proj = case.get("projects") or []
    chk("项目均有状态依据与证据", all(p.get("status_basis") and p.get("evidence") for p in proj),
        "%d 个项目" % len(proj))
    chk("项目状态全部为三级状态之一", all(p.get("status") in C.PROJECT_STATUS for p in proj),
        "；".join(sorted(set(p.get("status", "") for p in proj))))
    gap = case.get("data_gaps") or []
    chk("资料缺口均已登记下一步", all(g.get("next_step") for g in gap), "%d 项缺口" % len(gap))
    chk("来源数量 ≥ 10", len(src) >= 10, "%d 条来源" % len(src))
    chk("A 级证据存在", any(s.get("tier") == "A" for s in (case.get("sources") or [])),
        "%d 条 A 级" % sum(1 for s in case.get("sources") or [] if s.get("tier") == "A"))
    kpi = case.get("kpis") or []
    chk("KPI 数量在 4–10 之间", 4 <= len(kpi) <= 10, "%d 个" % len(kpi))
    chk("核心 KPI 挂接计算", any(k.get("calc") for k in kpi),
        "已挂接 %d 个" % sum(1 for k in kpi if k.get("calc")))
    secs = case.get("sections") or []
    chk("章节均声明章节包", all(s.get("pack") for s in secs), "%d 个章节" % len(secs))
    chk("存在 calculation 章节", any(s.get("pack") == "calculation" for s in secs),
        "计算章节 %d 个" % sum(1 for s in secs if s.get("pack") == "calculation"))
    chk("图表均绑定 data_key 且可解析",
        all(C.get_by_path(case, b["data_key"]) is not None
            for s in secs for b in (s.get("blocks") or []) if b.get("type") == "chart"),
        "图表 %d 个" % sum(1 for s in secs for b in (s.get("blocks") or []) if b.get("type") == "chart"))
    # 未引用来源
    idx = C.build_evidence_index(case)
    unused = [e["id"] for e in idx if e["kind"] == "source" and not e["refs"]]
    chk("无未引用来源", not unused, "未引用：%s" % ("、".join(unused) if unused else "无"))
    missing = [e["id"] for e in idx if e["kind"] == "missing"]
    chk("无未登记引用", not missing, "未登记：%s" % ("、".join(missing) if missing else "无"))
    return checks


def build(case, out_path):
    stats = {
        "conclusions": len(case.get("conclusions") or []),
        "calcs": len(case.get("calculations") or []),
        "sources": len(case.get("sources") or []),
        "gaps": len(case.get("data_gaps") or []),
        "projects": len(case.get("projects") or []),
        "companies": len(case.get("companies") or []),
    }
    checks = run_checks(case)
    wb = Workbook()
    wb.remove(wb.active)
    sheet_readme(wb, case, stats)
    sheet_evidence(wb, case)
    sheet_raw(wb, case)
    sheet_companies(wb, case)
    sheet_projects(wb, case)
    sheet_prices(wb, case)
    sheet_indicators(wb, case)
    sheet_calcs(wb, case)
    sheet_conclusions(wb, case)
    sheet_variables(wb, case)
    sheet_gaps(wb, case)
    sheet_outline(wb, case)
    sheet_qc(wb, case, checks)
    meta = case.get("meta") or {}
    wb.properties.title = meta.get("title", "")
    wb.properties.subject = "chem-topic-research 专题研究数据底稿"
    wb.properties.creator = "chem-topic-research v1.0"
    wb.properties.description = "%s | 数据截止 %s | 受众 %s" % (
        meta.get("title", ""), meta.get("data_cutoff", ""), C.audience_profile(case).get("label", ""))
    wb.properties.created = datetime.datetime.now()
    C.ensure_dir(os.path.dirname(os.path.abspath(out_path)))
    wb.save(out_path)
    return out_path, checks


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成 13 页 Excel 数据底稿")
    ap.add_argument("case")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    case = C.load(a.case)
    out = a.out or C.default_filename(case, C.audience_profile(case)["audience_key"], "_数据底稿.xlsx")
    path, checks = build(case, out)
    fails = [c for c in checks if not c[1]]
    print("XLSX ->", path, "(%.1f KB)" % (os.path.getsize(path) / 1024.0))
    print("  自检 %d 项：PASS %d / FAIL %d" % (len(checks), len(checks) - len(fails), len(fails)))
    for name, ok, detail in fails:
        print("  FAIL", name, "|", detail)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
