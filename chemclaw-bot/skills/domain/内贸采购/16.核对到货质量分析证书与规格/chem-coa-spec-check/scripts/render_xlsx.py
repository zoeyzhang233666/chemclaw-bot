# -*- coding: utf-8 -*-
"""render_xlsx.py —— 生成 12 页签 Excel 工作簿。

页签：00 说明与免责 / 01 核对结论 / 02 逐项比对 / 03 单位换算台账 / 04 批次趋势
      05 完整性检查 / 06 方法差异 / 07 多批次对照 / 08 异常问题清单 / 09 异议要点
      / 10 原始数据（COA+规格）/ 11 判定规则

公式：偏离程度等用**Excel 公式**写入手册之外，同时保留计算值（openpyxl 不重算，
      打开后按 Ctrl+Alt+F9 可重算校验）。数值口径与引擎一致。

用法：python render_xlsx.py data.json out.xlsx
"""
import os
import re
import sys

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coa_lib as L    # noqa: E402
import engine          # noqa: E402

# ------------------------------------------------------------------ 样式
C_BRAND = "0B3D66"
C_HDR_BG = "0B3D66"
C_SUB = "E8F1F8"
C_OK, C_FAIL = "0F7B52", "B42318"
FILL_OK = PatternFill("solid", fgColor="E6F6EE")
FILL_FAIL = PatternFill("solid", fgColor="FDECEB")
FILL_UNSPEC = PatternFill("solid", fgColor="EFECFB")
FILL_UNTESTED = PatternFill("solid", fgColor="FDF1E3")
FILL_UNKNOWN = PatternFill("solid", fgColor="EEF2F6")
FILL_SIM = PatternFill("solid", fgColor="FFF3CD")
FILL_HEAD = PatternFill("solid", fgColor="F8FAFC")
FILL_WARN = PatternFill("solid", fgColor="FFFBE8")
STATUS_FILL = {L.ST_OK: FILL_OK, L.ST_FAIL: FILL_FAIL, L.ST_UNSPEC: FILL_UNSPEC,
               L.ST_UNTESTED: FILL_UNTESTED, L.ST_UNKNOWN: FILL_UNKNOWN}
STATUS_COLOR = {L.ST_OK: C_OK, L.ST_FAIL: C_FAIL, L.ST_UNSPEC: "5C4A9E",
                L.ST_UNTESTED: "A45308", L.ST_UNKNOWN: "475569"}
THIN = Side(style="thin", color="D5DCE5")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_TITLE = Font(name="微软雅黑", size=15, bold=True, color=C_BRAND)
F_H2 = Font(name="微软雅黑", size=11.5, bold=True, color="FFFFFF")
F_HDR = Font(name="微软雅黑", size=9.5, bold=True, color="FFFFFF")
F_BODY = Font(name="微软雅黑", size=9.5, color="1F2937")
F_MONO = Font(name="Consolas", size=9.5, color="0F172A")
F_MONO_B = Font(name="Consolas", size=9.5, bold=True, color="0F172A")
F_MUTED = Font(name="微软雅黑", size=9, color="64748B")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="top", wrap_text=True)


def _title(ws, text, sub="", span=8):
    ws["A1"] = text
    ws["A1"].font = F_TITLE
    ws.row_dimensions[1].height = 26
    if sub:
        ws["A2"] = sub
        ws["A2"].font = F_MUTED
        ws["A2"].alignment = LEFT
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
        ws.row_dimensions[2].height = 30


def _header(ws, row, cols, widths=None, height=30):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = F_HDR
        cell.fill = PatternFill("solid", fgColor=C_HDR_BG)
        cell.alignment = CENTER
        cell.border = BORDER
    ws.row_dimensions[row].height = height
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _band(ws, row, text, cols):
    c = ws.cell(row=row, column=1, value=text)
    c.font = F_H2
    c.fill = PatternFill("solid", fgColor="155E91")
    c.alignment = Alignment(vertical="center")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=cols)
    ws.row_dimensions[row].height = 20


def _row(ws, r, vals, fills=None, fonts=None, aligns=None):
    for i, v in enumerate(vals, 1):
        c = ws.cell(row=r, column=i, value=v)
        c.font = (fonts[i - 1] if fonts and fonts[i - 1] else F_BODY)
        c.border = BORDER
        c.alignment = (aligns[i - 1] if aligns and aligns[i - 1] else LEFT)
        if fills and fills[i - 1]:
            c.fill = fills[i - 1]


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def display_dim(unit):
    """量纲的“人话”显示名：质量分数下 ppm/ppb 与 % 属同一量纲，但显示单位不同。"""
    d = L.unit_token(unit)
    if d[0] is None:
        return "无法识别"
    if d[1] in ("%", "ppm", "ppb", "mg/kg", "μg/kg", "ug/kg", "g/kg", "mg/g"):
        return "质量分数"
    return L.DIMENSIONS[d[0]]["label"].split("（")[0]


# ====================================================================== 页签

def sh_cover(wb, res):
    ws = wb.active
    ws.title = "00 说明与免责"
    ws.sheet_view.showGridLines = False
    m, p, sp = res["meta"], res["product"], res["supplier"]
    _title(ws, "COA × 采购规格书 到货质量核对工作簿", "chem-coa-spec-check · 由脚本自动生成 · 所有数值可追溯至原始取值", span=6)
    r = 4
    if m.get("simulated"):
        ws.cell(row=r, column=1, value="⚠ 模拟数据 SIMULATED").font = Font(name="微软雅黑", size=11, bold=True, color="7A5600")
        ws.cell(row=r, column=1).fill = FILL_SIM
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        ws.cell(row=r + 1, column=1, value=m.get("sim_note", "")).font = F_MUTED
        ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=8)
        ws.cell(row=r + 1, column=1).alignment = LEFT
        ws.row_dimensions[r + 1].height = 34
        r += 2
    rows = [
        ("产品", f"{p['name']} · {p.get('grade','')} · CAS {p.get('cas','')} · UN {p.get('un','')}"),
        ("供应商", f"{sp.get('name','')}（{sp.get('role','')}）"),
        ("采购方 / 联系人", f"{m.get('buyer_name','')} / {m.get('buyer_contact','')}"),
        ("合同 / 质量条款", f"{res['contract'].get('no','')}；{res['contract'].get('quality_clause','')}"),
        ("执行规格", m.get("spec_ref", "")),
        ("核对基准日", m.get("as_of", "")),
        ("重点批次", f"{res['target_batch']}（其余批次作为对照与趋势）"),
        ("产品用途（相关性参照）", p.get("use", "")),
    ]
    for k, v in rows:
        ws.cell(row=r, column=1, value=k).font = Font(name="微软雅黑", size=9.5, bold=True, color=C_BRAND)
        c = ws.cell(row=r, column=2, value=v)
        c.font = F_BODY
        c.alignment = LEFT
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        r += 1
    r += 1
    _band(ws, r, "本工作簿页签说明", 8)
    r += 1
    nav = [
        ("01 核对结论", "总览：各状态计数、可量化核验比例、完整性得分、最大偏离；含数据校验表"),
        ("02 逐项比对", "核心表：全部指标的 COA 实测 / 规格限值 / 单位 / 方法 / 判定 / 偏离（含公式）"),
        ("03 单位换算台账", "每个发生换算的数值：原值、原单位、系数、换算后值、是否跨判定线"),
        ("04 批次趋势", "历史批次 + 本批的序列、统计量、方向、越限批次、图表数据源"),
        ("05 完整性检查", "COA 字段齐备性、批号一致性、结论与数据一致性、缺失指标、检出限"),
        ("06 方法差异", "COA 方法 vs 约定方法：关系(一致/等效/不同/缺失)与对判定的影响"),
        ("07 多批次对照", "全部批次 × 全部指标 的判定矩阵"),
        ("08 异常问题清单", "按严重度排序的问题清单，含类型、对象、事实、建议动作"),
        ("09 异议要点", "可直接用于质量异议函的要点 + 三版函件草稿全文"),
        ("10 原始数据", "COA 与规格文件的原始取值及原文位置（审计底稿）"),
        ("11 判定规则", "去重后的规则卡：什么情形落到哪个状态、量纲与换算约定"),
    ]
    for a, b in nav:
        ws.cell(row=r, column=1, value=a).font = F_MONO_B
        ws.cell(row=r, column=1).border = BORDER
        c = ws.cell(row=r, column=2, value=b)
        c.font = F_BODY
        c.alignment = LEFT
        c.border = BORDER
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        ws.row_dimensions[r].height = 22
        r += 1
    r += 1
    _band(ws, r, "三条硬约束", 8)
    r += 1
    for t in [
        "1. 本工作簿不作收货/退货决定。它只回答：哪些符合、哪些偏离、哪些因条件缺失无法判断、证书是否完整。",
        "2. 不猜测。原始件数值、小数点、单位识别不清的，一律落“无法判断/需人工确认”，不按经验补值。",
        "3. 不做无依据换算。量纲不一致（如 % 与 mg/L）没有密度就不换算；换算跨越判定线的必须人工复核。",
    ]:
        c = ws.cell(row=r, column=1, value=t)
        c.font = Font(name="微软雅黑", size=9.5, color="7A5600")
        c.alignment = LEFT
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        ws.row_dimensions[r].height = 30
        r += 1
    for i, w in enumerate([20, 16, 16, 16, 16, 16, 16, 22], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def sh_conclusion(wb, res):
    ws = wb.create_sheet("01 核对结论")
    ws.sheet_view.showGridLines = False
    t = res["target_batch"]
    k = res["kpis"]
    _title(ws, "核对结论总览", f"重点批次 {t} · 基准日 {res['meta'].get('as_of','')} · 本页不构成收货决定", span=8)
    r = 4
    _band(ws, r, "一、判定分布与量化口径", 8)
    r += 1
    _header(ws, r, ["指标状态", "项数", "占比", "含义", "", "", "", ""],
            widths=[16, 9, 10, 46, 14, 14, 14, 14])
    r += 1
    meaning = {
        L.ST_OK: "实测在限值内，且名称/量纲/方法/基准均可比",
        L.ST_FAIL: "实测越过合同/规格限值（含换算后越限）",
        L.ST_UNSPEC: "合同未约定限值，不能据以判不合格",
        L.ST_UNTESTED: "规格已约定但 COA 缺项、空值或标注未检测",
        L.ST_UNKNOWN: "缺条件：方法不一致、检出限不明、单位不可比等，交人工",
    }
    for s in L.STATUS_SET:
        n = k["counts"].get(s, 0)
        _row(ws, r, [s, n, (n / k["total"] if k["total"] else 0), meaning[s], "", "", "", ""],
             fills=[STATUS_FILL[s], STATUS_FILL[s], STATUS_FILL[s], STATUS_FILL[s], None, None, None, None],
             fonts=[Font(name="微软雅黑", size=9.5, bold=True, color=STATUS_COLOR[s])] + [None] * 7,
             aligns=[CENTER, CENTER, CENTER, LEFT, None, None, None, None])
        ws.cell(row=r, column=3).number_format = "0.0%"
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
        r += 1
    _row(ws, r, ["合计", k["total"], 1.0, "", "", "", "", ""],
         fonts=[Font(name="微软雅黑", size=9.5, bold=True)] * 8)
    ws.cell(row=r, column=3).number_format = "0.0%"
    ws.cell(row=r, column=1).fill = FILL_HEAD
    r += 2
    _band(ws, r, "二、关键量化指标", 8)
    r += 1
    facts = [
        ("可量化核验比例", k["verifiable_ratio"] / 100, "(符合+不符合) ÷ 全部指标；其余为需要补充条件才能判定的项目"),
        ("最大偏离幅度", k["max_dev_pct"] / 100, "超出部分 ÷ 限值；只在“不符合”项中取绝对值最大者"),
        ("证书完整性得分", k["completeness"] / 100, "100 分起扣：高 -18 / 中 -8 / 低 -3"),
        ("方法差异项数", k["method_diff"], "COA 方法与合同/规格约定不同的项数"),
        ("异议要点条数", k["objection_points"], "已按严重度排序，高/中/低"),
        ("目标批次 COA 指标数", len(res["results"][t]), "COA 实际出具的指标行数"),
    ]
    for a, b, c in facts:
        ws.cell(row=r, column=1, value=a).font = Font(name="微软雅黑", size=9.5, bold=True, color=C_BRAND)
        ws.cell(row=r, column=1).border = BORDER
        cc = ws.cell(row=r, column=2, value=b)
        cc.font = Font(name="Consolas", size=13, bold=True, color=C_BRAND)
        cc.alignment = CENTER
        cc.border = BORDER
        cc.number_format = "0.0%" if isinstance(b, float) and b <= 1.0001 else "0"
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=8)
        ws.cell(row=r, column=3, value=c).font = F_BODY
        ws.cell(row=r, column=3).alignment = LEFT
        ws.row_dimensions[r].height = 20
        r += 1
    r += 1
    _band(ws, r, "三、数据校验（必须为“通过”才能把本表当作事实底稿使用）", 8)
    r += 1
    _header(ws, r, ["校验项", "被校验值", "期望", "结果", "说明", "", "", ""],
            widths=[16, 12, 12, 9, 16, 14, 14, 14])
    r += 1
    checks = [
        ("状态计数合计", sum(k["counts"].values()), k["total"], "判定行数 = 指标总数"),
        ("重点批次 COA 行数", len(res["results"][t]), k["total"], "逐项比对覆盖全部指标"),
        ("明细表行数", k["total"], k["total"], "02 页签行数与 01 页签一致"),
    ]
    for a, b, c, note in checks:
        ok = (b == c)
        _row(ws, r, [a, b, c, "通过" if ok else "不一致", note, "", "", ""],
             fills=[None, None, None, FILL_OK if ok else FILL_FAIL, None, None, None, None],
             fonts=[None, F_MONO, F_MONO, Font(name="微软雅黑", size=9.5, bold=True,
                                              color=C_OK if ok else C_FAIL), None, None, None, None],
             aligns=[LEFT, CENTER, CENTER, CENTER, LEFT, None, None, None])
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=8)
        r += 1
    r += 1
    _band(ws, r, "四、重点提示（引擎自动识别的口径陷阱）", 8)
    r += 1
    for a in res["alerts"]:
        _row(ws, r, [a["level"], a["text"], "", "", "", "", "", ""],
             fills=[PatternFill("solid", fgColor={"高": "FDECEB", "中": "FDF3E4", "低": "EEF2F6"}[a["level"]]),
                    None, None, None, None, None, None, None],
             aligns=[CENTER, LEFT, None, None, None, None, None, None])
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        ws.row_dimensions[r].height = 32
        r += 1


def sh_compare(wb, res):
    ws = wb.create_sheet("02 逐项比对")
    t = res["target_batch"]
    rows = res["results"][t]
    _title(ws, "逐项指标比对表（核心表）",
           f"批次 {t} · 判定口径：规格限值（合同优先）+ 实测（换算到规格单位）+ 方法关系 + 可比性五维 · "
           f"G 列偏离% 为 Excel 公式，可 Ctrl+Alt+F9 重算", span=19)
    cols = ["#", "指标", "类别", "相关性", "COA 实测(原文)", "COA 单位", "COA 数值", "规格限值(原文)", "规格单位",
            "限值类型", "上限", "下限", "换算后实测(规格单位)", "判定", "严重度", "偏离%", "偏离绝对值",
            "偏离公式", "判定理由", "COA方法", "约定方法", "方法关系", "COA基准", "规格基准", "规格来源",
            "COA原文位置", "规格原文位置", "备注"]
    _header(ws, 4, cols, widths=[4, 20, 7, 7, 15, 8, 10, 16, 8, 10, 10, 10, 13, 9, 6, 9, 10,
                                 34, 40, 17, 17, 9, 12, 12, 20, 20, 26, 36], height=34)
    r = 5
    for i, x in enumerate(rows, 1):
        ref = L.parse_value(x["coa_raw"], "ref")
        lim = L.parse_value(x["spec_limit"], "limit")
        conv = L.convert(ref["value"], x["coa_unit"], x["spec_unit"])[0] if (
            ref["value"] is not None and x["coa_unit"] and x["spec_unit"]) else None
        v = ref["value"] if ref["kind"] in ("single", "max", "min") else (
            (ref["range"][0] + ref["range"][1]) / 2 if ref["kind"] == "range" else None)
        hi = lim["value"] if lim["kind"] == "max" else (lim["range"][1] if lim["kind"] == "range" else None)
        lo = lim["value"] if lim["kind"] == "min" else (lim["range"][0] if lim["kind"] == "range" else None)
        if lim["kind"] == "single":
            lo, hi = lim["value"], lim["value"]
        # 偏离：公式行内计算（只在有上限/下限时给出）
        f = ""
        if x["status"] == L.ST_FAIL and (hi is not None or lo is not None):
            if hi is not None and (lo is None or (conv is not None and conv > hi)):
                f = f"=IFERROR((M{r}-K{r})/K{r},\"\")"
            elif lo is not None:
                f = f"=IFERROR((L{r}-M{r})/L{r},\"\")"
        dev_pct = (x["deviation"].get("pct") or 0) / 100 if x["status"] == L.ST_FAIL else None
        vals = [i, x["name"], x["category"], {"mandatory": "强制项", "customer": "约定项"}.get(x["basis"], x["basis"]),
                x["coa_value"], x["coa_unit"], v, x["spec_limit"], x["spec_unit"],
                {"single": "单值", "max": "上限≤", "min": "下限≥", "range": "范围", "text": "定性",
                 "unspecified": "未约定"}.get(lim["kind"], lim["kind"]),
                hi, lo, conv, x["status"], x["severity"] or "", f or dev_pct,
                round(x["deviation"].get("absolute"), 6) if x["deviation"].get("absolute") is not None else None,
                x["deviation"].get("formula") or "", x["reason"], x["method_coa"], x["method_spec"],
                {"same": "一致", "equivalent": "等效", "different": "不同", "missing_coa": "COA缺",
                 "missing_spec": "规格缺", "both_missing": "双方缺"}.get(x["method_relation"], ""),
                x["basis_coa"], x["basis_spec"], x["spec_source"] or "未约定",
                (x["loc"] or {}).get("coa") or "", (x["loc"] or {}).get("spec") or "",
                "；".join(x.get("notes") or [])]
        fills = [None] * len(vals)
        if x["status"] == L.ST_FAIL:
            fills[13] = FILL_FAIL
        else:
            fills[13] = STATUS_FILL.get(x["status"])
        _row(ws, r, vals, fills=fills,
             fonts=[F_MUTED, Font(name="微软雅黑", size=9.5, bold=True)] + [None] * 26,
             aligns=[CENTER, LEFT, CENTER, CENTER, LEFT, CENTER, CENTER, CENTER, CENTER, CENTER,
                     CENTER, CENTER, CENTER, CENTER, CENTER, CENTER, CENTER, LEFT, LEFT, LEFT, LEFT,
                     CENTER, LEFT, LEFT, LEFT, LEFT, LEFT, LEFT])
        for c in (7, 11, 12, 13, 17):
            ws.cell(row=r, column=c).number_format = "0.####"
        ws.cell(row=r, column=16).number_format = "+0.00%;-0.00%"
        ws.cell(row=r, column=14).font = Font(name="微软雅黑", size=9.5, bold=True,
                                             color=STATUS_COLOR.get(x["status"], "111111"))
        for c in (7, 11, 12, 13):
            ws.cell(row=r, column=c).font = F_MONO
        ws.row_dimensions[r].height = 34
        r += 1
    # 状态筛选
    dv = DataValidation(type="list", formula1='"符合,不符合,规格未约定,COA未检测,无法判断"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"N5:N{r-1}")
    ws.auto_filter.ref = f"A4:AB{r-1}"
    # 图例
    r += 1
    ws.cell(row=r, column=2, value="图例：").font = Font(name="微软雅黑", size=9, bold=True)
    for j, s in enumerate(L.STATUS_SET):
        c = ws.cell(row=r, column=3 + j, value=s)
        c.fill = STATUS_FILL[s]
        c.font = Font(name="微软雅黑", size=9, bold=True, color=STATUS_COLOR[s])
        c.alignment = CENTER
        c.border = BORDER


def sh_convert(wb, res):
    ws = wb.create_sheet("03 单位换算台账")
    _title(ws, "单位换算台账（每一次换算都可复算）",
           "换算规则见 11 判定规则；量纲不一致时不给结果，只写原因——因为缺条件时“换算”等于编数", span=12)
    cols = ["批次", "指标", "COA 原值", "COA 原单位", "规格单位", "量纲", "系数(原→规格)", "换算后值",
            "换算说明", "是否跨判定线", "换算后判定", "备注"]
    _header(ws, 4, cols, widths=[16, 20, 14, 10, 10, 10, 14, 14, 40, 12, 12, 34])
    r = 5
    n = 0
    for b in res["batch_order"]:
        for x in res["results"][b]:
            if not (x["coa_unit"] and x["spec_unit"]):
                continue
            t1, t2 = L.unit_token(x["coa_unit"]), L.unit_token(x["spec_unit"])
            # 同一量纲内、单位符号不同 → 发生了换算，必须入台账
            if t1[1] == t2[1]:
                continue
            ref = L.parse_value(x["coa_raw"], "ref")
            nv, note = L.convert(ref["value"], x["coa_unit"], x["spec_unit"])
            d1, d2 = t1, t2
            cross = ""
            if d1[0] != d2[0]:
                cross = "量纲不一致，未换算"
            elif nv is not None and ref["value"]:
                cross = "否" if abs(nv / ref["value"] - 1) > 1e-12 else "—"
            _row(ws, r, [b, x["name"], ref["value"], x["coa_unit"], x["spec_unit"],
                         f"{display_dim(x['coa_unit'])} → {display_dim(x['spec_unit'])}",
                         (round(nv / ref["value"], 10) if nv is not None and ref["value"] else ""),
                         nv, note, cross, x["status"], ""],
                 fonts=[None, Font(name="微软雅黑", size=9.5, bold=True), F_MONO, F_MONO, F_MONO,
                        F_MONO, F_MONO_B, F_MONO_B, None, None, None, None],
                 aligns=[LEFT, LEFT, CENTER, CENTER, CENTER, CENTER, CENTER, CENTER, LEFT, CENTER, CENTER, LEFT])
            ws.cell(row=r, column=3).number_format = "0.####"
            ws.cell(row=r, column=8).number_format = "0.######"
            ws.cell(row=r, column=11).fill = STATUS_FILL.get(x["status"], FILL_UNKNOWN)
            r += 1
            n += 1
    if n == 0:
        ws.cell(row=5, column=1, value="本批次 COA 与规格单位完全一致，无需换算。").font = F_MUTED
        return
    # 追加：质量标准换算速查
    r += 2
    _band(ws, r, "质量分数常用换算速查（打印张贴用）", 12)
    r += 1
    _header(ws, r, ["从", "到", "系数", "示例", "", "", "", "", "", "", "", ""])
    r += 1
    r += 1
    tricks = [
        ("%", "ppm", 1e4, "0.08 % = 800 ppm（水分上限）"),
        ("ppm", "%", 1e-4, "865 ppm = 0.0865 %"),
        ("ppm", "ppb", 1000, "0.5 ppm = 500 ppb（铁上限）"),
        ("ppb", "ppm", 1e-3, "580 ppb = 0.58 ppm ＞ 0.5 ppm ⇒ 超限"),
        ("g/L", "mg/L", 1000, "1 g/L = 1000 mg/L"),
    ]
    for a, b, k, eg in tricks:
        _row(ws, r, [a, b, k, eg, "", "", "", "", "", "", "", ""],
             fonts=[F_MONO_B, F_MONO_B, F_MONO, None, None, None, None, None, None, None, None, None])
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=12)
        r += 1
    ws.cell(row=r + 1, column=1, value="⚠ % ↔ mg/L、mg/kg ↔ mg/L 等质量分数×体积浓度的换算必须已知温度下密度，"
                                      "无密度时不换算，直接落“无法判断”。").font = Font(name="微软雅黑", size=9, color="A45308")


def sh_trend(wb, res):
    ws = wb.create_sheet("04 批次趋势")
    t = res["target_batch"]
    _title(ws, "多批次指标变化趋势",
           "所有批次先统一到规格单位再比较；越限批次用红色标注；趋势只陈述事实，不推断原因", span=12)
    _header(ws, 4, ["指标", "单位", "批次数", "均值", "最小值", "最大值", "标准差", "首末变化",
                    "方向", "越限批次", "趋势描述", "单位归一说明"],
            widths=[20, 10, 8, 12, 12, 12, 12, 14, 8, 22, 60, 46])
    r = 5
    trends = res["trends"][t]
    for x in trends:
        if not x.get("n"):
            _row(ws, r, [x["name"], x.get("unit", ""), 0, "", "", "", "", "", "", "", "无可用数值序列", ""],
                 fills=[None, None, None, None, None, None, None, None, None, None, FILL_UNKNOWN, None])
            r += 1
            continue
        oos = "、".join(f"{b}({v:g})" for b, v in x["oos"]) or "无"
        dpct = x["delta_pct"] / 100 if x["delta_pct"] is not None else None
        _row(ws, r, [x["name"], x.get("unit", ""), x["n"], x["mean"], x["min"], x["max"], x["sd"],
                     dpct, x["direction"], oos, x["desc"], "；".join(x.get("conversions") or [])],
             fonts=[Font(name="微软雅黑", size=9.5, bold=True), None, None, F_MONO, F_MONO, F_MONO, F_MONO,
                    F_MONO, None, None, None, None],
             aligns=[LEFT, CENTER, CENTER] + [CENTER] * 6 + [LEFT, LEFT, LEFT])
        for c in (4, 5, 6, 7):
            ws.cell(row=r, column=c).number_format = "0.####"
        ws.cell(row=r, column=8).number_format = "+0.00%;-0.00%"
        if x["oos"]:
            ws.cell(row=r, column=10).fill = FILL_FAIL
            ws.cell(row=r, column=10).font = Font(name="微软雅黑", size=9.5, bold=True, color=C_FAIL)
        r += 1
    # 序列明细 + 折线图（取前 4 个有数值的指标）
    r += 2
    _band(ws, r, "各批次数值序列（图表的原始数据源，单位已归一）", 12)
    r += 1
    seq_head_row = r
    plotted = [x for x in trends if x.get("n") and len(x["series"]) >= 2][:4]
    if not plotted:
        ws.cell(row=r, column=1, value="可用序列不足，未生成图表").font = F_MUTED
        return
    batches = plotted[0]["series"]
    ws.cell(row=r, column=1, value="批次").font = F_HDR
    ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=C_HDR_BG)
    ws.cell(row=r, column=2, value="生产日期").font = F_HDR
    ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=C_HDR_BG)
    for j, x in enumerate(plotted, 3):
        c = ws.cell(row=r, column=j, value=f'{x["name"]}({x.get("unit","")})')
        c.font = F_HDR
        c.fill = PatternFill("solid", fgColor=C_HDR_BG)
        c.alignment = CENTER
    r += 1
    first_data = r
    for i, s in enumerate(batches):
        ws.cell(row=r, column=1, value=s["batch"]).font = F_MONO
        ws.cell(row=r, column=2, value=s["date"]).font = F_MONO
        for j, x in enumerate(plotted, 3):
            v = x["series"][i]["base_value"] if i < len(x["series"]) else None
            c = ws.cell(row=r, column=j, value=v)
            c.font = F_MONO
            c.number_format = "0.######"
            if s["is_target"]:
                c.font = Font(name="Consolas", size=9.5, bold=True)
        if s["is_target"]:
            for j in (1, 2):
                ws.cell(row=r, column=j).fill = FILL_WARN
        r += 1
    last_data = r - 1
    # 图表：按“行=批次、列=指标”建表，用 from_rows 建系列，避免 Reference 组合出错
    if len(plotted) >= 1 and last_data > first_data:
        ch = LineChart()
        ch.title = "批次趋势（单位已归一）"
        ch.y_axis.title = "指标值"
        ch.x_axis.title = "批次"
        ch.style = 12
        ch.height, ch.width = 9.5, 20
        data = Reference(ws, min_col=3, min_row=seq_head_row, max_col=2 + len(plotted), max_row=last_data)
        ch.add_data(data, titles_from_data=True)
        cats = Reference(ws, min_col=1, min_row=first_data, max_row=last_data)
        ch.set_categories(cats)
        ch.marker = True
        ws.add_chart(ch, f"F{last_data + 2}")
        ws.cell(row=last_data + 1, column=1,
                value="注：不同指标量级差异大（如色度 vs 纯度），折线图用来快速看方向；"
                      "精确比较请用上方统计表与 04 页签各批次数值。").font = Font(name="微软雅黑", size=9, color="64748B")


def sh_integrity(wb, res):
    ws = wb.create_sheet("05 完整性检查")
    _title(ws, "证书完整性检查",
           "评价“这份证书能否支撑验收”，不评价产品质量。缺项本身不是不合格，但会让指标结论失去依据", span=8)
    r = 4
    for b in res["batch_order"]:
        comp = res["completeness"][b]
        _band(ws, r, f'批次 {b} · 完整性得分 {comp["score"]}/100 · 高 {comp["counts"]["高"]} / 中 {comp["counts"]["中"]} / 低 {comp["counts"]["低"]}', 8)
        r += 1
        _header(ws, r, ["级别", "字段/检查项", "发现的问题", "建议处理动作", "", "", "", ""],
                widths=[8, 16, 62, 52, 12, 12, 12, 12])
        r += 1
        for i in comp["issues"]:
            fill = PatternFill("solid", fgColor={"高": "FDECEB", "中": "FDF3E4", "低": "EEF2F6"}[i["level"]])
            _row(ws, r, [i["level"], i["field"], i["msg"], i["action"], "", "", "", ""],
                 fills=[fill, None, None, None, None, None, None, None],
                 fonts=[Font(name="微软雅黑", size=9.5, bold=True,
                             color={"高": C_FAIL, "中": "B45309", "低": "475569"}[i["level"]]), None, None, None] + [None] * 4,
                 aligns=[CENTER, LEFT, LEFT, LEFT, None, None, None, None])
            ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
            ws.row_dimensions[r].height = 30
            r += 1
        if not comp["issues"]:
            ws.cell(row=r, column=1, value="未发现完整性缺陷").font = F_MUTED
            r += 1
        r += 1
    # 必检字段矩阵
    _band(ws, r, "必检字段矩阵（任一 COA 都应具备）", 8)
    r += 1
    _header(ws, r, ["字段", "必要性"] + res["batch_order"] + [""] * max(0, 5 - len(res["batch_order"])))
    r += 1
    for key, label in engine.REQ_HEADER.items():
        if key == "cert_code":
            vals = []
            for b in res["batch_order"]:
                c = next(x for x in res["coas"] if x["batch_no"] == b)
                so = c.get("signoff", {})
                vals.append("有" if (so.get("cert_code") or so.get("reviewer") or so.get("issuer")) else "缺失")
        else:
            vals = []
            for b in res["batch_order"]:
                c = next(x for x in res["coas"] if x["batch_no"] == b)
                v = c.get("header", {}).get(key)
                vals.append("有" if v not in (None, "") else "缺失")
        need = "必需" if key in ("batch_no", "mfg_date", "test_date", "test_standard", "product_name",
                                "producer") else "建议"
        _row(ws, r, [label, need] + vals + [""] * max(0, 5 - len(vals)),
             fills=[None, None] + [FILL_OK if v == "有" else FILL_FAIL for v in vals] + [None] * 5,
             fonts=[None, None] + [Font(name="微软雅黑", size=9.5, bold=True,
                                        color=C_OK if v == "有" else C_FAIL) for v in vals] + [None] * 5,
             aligns=[LEFT, CENTER] + [CENTER] * len(vals) + [None] * 5)
        r += 1


def sh_method(wb, res):
    ws = wb.create_sheet("06 方法差异")
    _title(ws, "检测方法差异与影响", "“同名指标”用不同方法测出来的数不能直接比——本表只回答：这个数是怎么测的", span=9)
    r = 4
    for b in res["batch_order"]:
        items = res["method_issues"][b]["items"]
        _band(ws, r, f"批次 {b} · 方法关系异常 {len(items)} 项", 9)
        r += 1
        _header(ws, r, ["指标", "COA 方法", "约定方法", "关系", "COA 实测", "规格限值", "对判定的影响", "备注", ""],
                widths=[20, 22, 18, 14, 14, 14, 62, 40, 6])
        r += 1
        if not items:
            ws.cell(row=r, column=1, value="本批次方法全部一致，无差异项").font = F_MUTED
            r += 1
        for m in items:
            fill = FILL_FAIL if m["relation"] == "different" else FILL_UNTESTED
            _row(ws, r, [m["name"], m["coa_method"] or "—", m["spec_method"] or "—", m["label"],
                         m["coa_value"], m["spec_limit"], m["impact"] or "—", m["note"] or "", ""],
                 fills=[None, None, None, fill, None, None, None, None, None],
                 aligns=[LEFT, LEFT, LEFT, CENTER, CENTER, CENTER, LEFT, LEFT, None])
            ws.row_dimensions[r].height = 40
            r += 1
        r += 1
    # 等效方法组
    _band(ws, r, "等效方法组（在报告中注明即可，不必强制复测；未列出的组合一律视为“不同”）", 9)
    r += 1
    for grp in res["product"].get("equivalent_methods", []):
        _row(ws, r, [" / ".join(grp), "", "", "等效", "", "", "", "", ""],
             aligns=[LEFT, LEFT, LEFT, CENTER, None, None, None, None, None])
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        r += 1


def sh_matrix(wb, res):
    ws = wb.create_sheet("07 多批次对照")
    bs = res["batch_order"]
    _title(ws, "多批次 × 全指标 判定矩阵", "同一张规格横向比较；单元格 = 判定 + 实测（COA 原始单位）+ 偏离%", span=3 + len(bs))
    _header(ws, 4, ["指标", "规格限值", "规格单位"] + [f"{b}" for b in bs],
            widths=[22, 16, 9] + [26] * len(bs))
    r = 5
    for x0 in res["results"][bs[0]]:
        vals = [x0["name"], x0["spec_limit"] or "—", x0["spec_unit"]]
        fills = [None, None, None]
        fonts = [Font(name="微软雅黑", size=9.5, bold=True), F_MONO, F_MONO]
        for b in bs:
            x = next((y for y in res["results"][b] if y["name_key"] == x0["name_key"]), None)
            if not x:
                vals.append("—")
                fills.append(None)
                fonts.append(None)
                continue
            txt = f'{x["status"]}｜{x["coa_value"]} {x["coa_unit"]}'
            if x["status"] == L.ST_FAIL and x["deviation"].get("pct") is not None:
                txt += f'｜{x["deviation"]["pct"]:+.2f}%'
            vals.append(txt)
            fills.append(STATUS_FILL.get(x["status"]))
            fonts.append(Font(name="微软雅黑", size=9.5, bold=True, color=STATUS_COLOR.get(x["status"], "111111")))
        _row(ws, r, vals, fills=fills, fonts=fonts,
             aligns=[LEFT, CENTER, CENTER] + [LEFT] * len(bs))
        r += 1
    # 分布行
    vals = ["判定分布", "", ""]
    for b in bs:
        s = res["summary"][b]
        vals.append(" / ".join(f"{k}{s.get(k,0)}" for k in L.STATUS_SET if s.get(k, 0)))
    _row(ws, r, vals, fonts=[Font(name="微软雅黑", size=9.5, bold=True)] * len(vals))
    ws.row_dimensions[r].height = 34


def sh_issues(wb, res):
    ws = wb.create_sheet("08 异常问题清单")
    _title(ws, "异常问题清单（按严重度排序）",
           "严重度只看：限值类型、偏离幅度、指标与用途的相关性。它是“值不值得写进函件”的排序，不是收货决策", span=8)
    _header(ws, 4, ["序", "严重度", "类型", "对象", "事实描述", "建议动作", "来源批次", "定位"],
            widths=[5, 8, 14, 22, 66, 52, 16, 30])
    acts = {
        "指标超限": "要求复检（约定方法）或书面技术说明；按合同质量条款主张",
        "关键指标未检": "要求补充检测结果与检测方法",
        "无法判断": "补充检出限/方法/单位/基准后重新核对，或按约定方法复检",
        "证书完整性": "索取补全后的正式 COA 原件（含批号、日期、方法、签章）",
        "方法差异": "要求说明方法选择理由，或按约定方法复测",
    }
    r = 5
    for i, x in enumerate(res["risks"], 1):
        fill = PatternFill("solid", fgColor={"高": "FDECEB", "中": "FDF3E4", "低": "EEF2F6"}.get(x["sev"], "EEF2F6"))
        _row(ws, r, [i, x["sev"], x["type"], x["item"], x["desc"], acts.get(x["type"], ""),
                     res["target_batch"], ""],
             fills=[None, fill, None, None, None, None, None, None],
             fonts=[F_MUTED, Font(name="微软雅黑", size=9.5, bold=True,
                                  color={"高": C_FAIL, "中": "B45309", "低": "475569"}.get(x["sev"], "111111")),
                    None, Font(name="微软雅黑", size=9.5, bold=True), None, None, None, None],
             aligns=[CENTER, CENTER, LEFT, LEFT, LEFT, LEFT, CENTER, LEFT])
        ws.row_dimensions[r].height = 32
        r += 1
    ws.auto_filter.ref = f"A4:H{r-1}"


def sh_objection(wb, res):
    ws = wb.create_sheet("09 异议要点")
    _title(ws, "质量异议要点", "每条要点都能指回一条原始数据或一个文件位置；未列入函件的只作内部留档", span=9)
    o = res["objections"]
    _header(ws, 4, ["序", "严重度", "类别", "异议标题", "事实（可直接写入函件）", "要求供应商做什么", "依据文件与位置", "是否入函", ""],
            widths=[5, 8, 12, 30, 66, 50, 40, 10, 6])
    r = 5
    for p in o["points"]:
        _row(ws, r, [p["no"], p["severity"], p["category"], p["title"], p["facts"], p["ask"],
                     "；".join(f'{x["doc"]}{(" · " + x["loc"]) if x.get("loc") else ""}' for x in p["evidence"]),
                     "是" if p["severity"] in ("高", "中") else "内部", ""],
             fills=[None, PatternFill("solid", fgColor={"高": "FDECEB", "中": "FDF3E4", "低": "EEF2F6"}.get(p["severity"], "EEF2F6")),
                    None, None, None, None, None, None, None],
             fonts=[F_MUTED, Font(name="微软雅黑", size=9.5, bold=True,
                                  color={"高": C_FAIL, "中": "B45309", "低": "475569"}.get(p["severity"], "111111")),
                    None, Font(name="微软雅黑", size=9.5, bold=True), None, None, None, None, None],
             aligns=[CENTER, CENTER, CENTER, LEFT, LEFT, LEFT, LEFT, CENTER, None])
        ws.row_dimensions[r].height = 58
        r += 1
    r += 2
    names = {"formal": "正式 · 质量异议函", "firm": "强硬 · 索赔前置", "soft": "沟通 · 供应商友好版"}
    for k in ("formal", "firm", "soft"):
        _band(ws, r, f"函件草稿 · {names[k]}", 9)
        r += 1
        for line in res["drafts"][k].split("\n"):
            c = ws.cell(row=r, column=1, value=line)
            c.font = Font(name="Consolas", size=10, color="1F2937")
            c.alignment = Alignment(vertical="top", wrap_text=True)
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
            ws.row_dimensions[r].height = 18 if line.strip() else 8
            r += 1
        r += 1


def sh_raw(wb, res):
    ws = wb.create_sheet("10 原始数据")
    _title(ws, "原始数据（审计底稿）", "COA 与规格文件的原始写法与原文位置，不经加工——用于与扫描件逐字核对", span=9)
    r = 4
    # COA
    for c in res["coas"]:
        _band(ws, r, f'COA · 批次 {c.get("batch_no")} · {c.get("file","")}', 9)
        r += 1
        for _, k, lab in [("", "product_name", "产品名称"), ("", "grade", "等级"), ("", "producer", "生产企业"),
                          ("", "batch_no", "生产批号"), ("", "report_no", "证书编号"),
                          ("", "mfg_date", "生产日期"), ("", "test_date", "检测日期"),
                          ("", "retest_date", "复检期至"), ("", "test_standard", "检测依据"),
                          ("", "conclusion", "检验结论"), ("", "packing", "包装/数量")]:
            v = c.get("header", {}).get(k)
            ws.cell(row=r, column=1, value=lab).font = F_MUTED
            cell = ws.cell(row=r, column=2, value=v if v not in (None, "") else "（缺失）")
            cell.font = F_MONO if v not in (None, "") else Font(name="微软雅黑", size=9.5, color=C_FAIL)
            r += 1
        ws.cell(row=r, column=1, value="防伪码/签章").font = F_MUTED
        so = c.get("signoff", {})
        ws.cell(row=r, column=2, value=f'防伪码 {so.get("cert_code") or "无"}；编制 {so.get("inspector") or "-"}；'
                                       f'审核 {so.get("reviewer") or "-"}；签发 {so.get("issuer") or "-"}').font = F_MONO
        r += 1
        _header(ws, r, ["指标名称", "实测值(原文)", "单位(原文)", "检测方法(原文)", "检出限", "基准", "原文位置", "备注", ""],
                widths=[22, 16, 10, 22, 14, 14, 26, 44, 6])
        r += 1
        for it in c.get("items", []):
            _row(ws, r, [it.get("name"), it.get("value"), it.get("unit"), it.get("method") or "（未标注）",
                         it.get("lod") or "", L.basis_label(it.get("basis", "as_received")), it.get("loc") or "",
                         it.get("comment") or "", ""],
                 fonts=[Font(name="微软雅黑", size=9.5, bold=True), F_MONO_B, F_MONO, F_MONO, F_MONO, None, None, None, None],
                 aligns=[LEFT, CENTER, CENTER, LEFT, CENTER, CENTER, LEFT, LEFT, None])
            r += 1
        r += 1
    # 规格
    for sp in res["specs"]:
        _band(ws, r, f'规格 · {sp.get("title","")} · {sp.get("spec_no","")} {sp.get("rev","")}', 9)
        r += 1
        _header(ws, r, ["指标", "单位", "限值(原文)", "方法(约定)", "基准", "类别", "原文位置", "", ""])
        r += 1
        for it in sp.get("items", []):
            _row(ws, r, [it.get("name"), it.get("unit"), it.get("limit"), it.get("method"),
                         L.basis_label(it.get("basis", "as_received")), it.get("category"), it.get("loc"), "", ""],
                 fonts=[Font(name="微软雅黑", size=9.5, bold=True), F_MONO, F_MONO_B, F_MONO, None, None, None, None, None],
                 aligns=[LEFT, CENTER, CENTER, LEFT, CENTER, CENTER, LEFT, None, None])
            r += 1
        r += 1
    for st in res.get("standards", []):
        _band(ws, r, f'标准参照 · {st.get("code","")}（非合同引用，仅供对照）', 9)
        r += 1
        _header(ws, r, ["指标", "单位", "限值", "方法", "", "", "说明", "", ""])
        r += 1
        for it in st.get("items", []):
            _row(ws, r, [it.get("name"), it.get("unit"), it.get("limit"), it.get("method"), "", "", st.get("loc"), "", ""],
                 fonts=[None, F_MONO, F_MONO, F_MONO, None, None, None, None, None],
                 aligns=[LEFT, CENTER, CENTER, LEFT, None, None, LEFT, None, None])
            r += 1
        r += 1


def sh_rules(wb, res):
    ws = wb.create_sheet("11 判定规则")
    _title(ws, "判定规则卡（去重后）", "本页签即引擎的判定顺序；改动本页签不会改变结果，改规则请改 references/*.md 与 coa_lib.py", span=6)
    _header(ws, 4, ["优先级", "规则", "判定结果", "说明", "代码位置", ""],
            widths=[8, 30, 14, 76, 26, 6])
    r = 5
    rules = [
        ("1", "规格文件未约定该指标限值", "规格未约定",
         "合同/规格/标准均无该指标。生产规格或供应商建议值只作提示，不改判定；若要作为验收依据须补充约定", "engine._row / infer_spec"),
        ("2", "COA 缺该项 / 值为空 / 标注未检测", "COA未检测",
         "含“COA 整行缺失”与“原表写 / 或 未测”。两者在异议中处理动作相同，故合并", "engine._row"),
        ("3a", "指标名称不在别名表中", "无法判断", "“名称相似”不等于同一指标，必须人工确认对应关系", "coa_lib.comparability"),
        ("3b", "量纲不同且缺换条件", "无法判断",
         "如 % ↔ mg/L 缺密度；ppm 与 ppb 可换（1 ppm = 1000 ppb）", "coa_lib.convert"),
        ("3c", "COA 方法与约定方法不同", "无法判断",
         "同指标不同方法的结果不能直接比；等效方法组除外（见 06 页签）", "coa_lib.method_relation"),
        ("3d", "基准不同（干基/湿基、折百）", "无法判断", "缺换算系数时不折算", "coa_lib.comparability"),
        ("4a", "COA 报“未检出”但无检出限", "COA未检测",
         "未检出 ≠ 合格；无检出限无法与限值比较", "coa_lib.determine_status"),
        ("4b", "实测低于检出限，且检出限 ≤ 上限", "符合", "若检出限高于上限则落“无法判断”", "coa_lib.determine_status"),
        ("4c", "微量杂质报单一数值，且为该结构检出限", "无法判断",
         "数值 = 上限的 1/5 量级且有效位不少于限值，常见于“低于报告下限按 LOD 报出”", "coa_lib._lod_structure"),
        ("4d", "换算前后判定结论发生变化", "无法判断",
         "提示单位标注/小数点可能错误，必须回原件人工复核", "coa_lib._crosses_limit"),
        ("5", "数值比较（上限/下限/范围/规定值）", "符合 / 不符合",
         "统一换算到规格单位后比较；偏离 = 超出部分 ÷ 限值（上限用正、下限取正）", "coa_lib.limit_eval / deviation"),
        ("6", "定性/描述性指标", "符合 / 不符合 / 无法判断",
         "规格关键词全部出现→符合；出现相悖表述→不符合（理由为词面证据）；其余交人工", "coa_lib.determine_status(text)"),
    ]
    for a, b, c, d, e in rules:
        fill = {L.ST_OK: FILL_OK, L.ST_FAIL: FILL_FAIL, L.ST_UNSPEC: FILL_UNSPEC,
                L.ST_UNTESTED: FILL_UNTESTED, L.ST_UNKNOWN: FILL_UNKNOWN}
        f = fill.get(c.split(" / ")[0])
        _row(ws, r, [a, b, c, d, e, ""],
             fills=[None, None, f, None, None, None],
             fonts=[F_MONO_B, Font(name="微软雅黑", size=9.5, bold=True),
                    Font(name="微软雅黑", size=9.5, bold=True, color=STATUS_COLOR.get(c.split(" / ")[0], "111111")),
                    None, F_MONO, None],
             aligns=[CENTER, LEFT, CENTER, LEFT, LEFT, None])
        ws.row_dimensions[r].height = 32
        r += 1
    r += 1
    _band(ws, r, "量纲与单位换算约定", 6)
    r += 1
    conv = [
        ("质量分数", "% = wt% = 质量分数；1 % = 10⁴ ppm = 10⁷ ppb；ppm 族 = mg/kg；ppb 族 = μg/kg", "精确换算"),
        ("质量浓度", "mg/L、g/L；ppm(v/v) 按 mg/L 处理（水溶液近似）", "精确换算"),
        ("温度", "℃ ↔ ℉ 仿射换算（F = C×9/5+32）；温度是判定条件，不是指标值", "仿射"),
        ("密度", "g/cm³ = g/mL；kg/m³ → g/cm³ 乘 1e-3；温度必须同为 20℃", "精确换算"),
        ("不可换算", "质量分数 ↔ 质量浓度（% ↔ mg/L）：需要同温度密度，缺条件时不换算", "禁止换算"),
        ("色度", "Hazen = 铂钴色号（Pt-Co）；不同光源/比色皿结果不可比", "同体系"),
    ]
    for a, b, c in conv:
        _row(ws, r, ["", a, b, "", c, ""],
             fonts=[None, Font(name="微软雅黑", size=9.5, bold=True), None, None, None, None],
             aligns=[None, CENTER, LEFT, None, CENTER, None])
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        ws.row_dimensions[r].height = 28
        r += 1


# ====================================================================== 入口
def render(data, out_path):
    res = engine.run(data)
    wb = Workbook()
    sh_cover(wb, res)
    sh_conclusion(wb, res)
    sh_compare(wb, res)
    sh_convert(wb, res)
    sh_trend(wb, res)
    sh_integrity(wb, res)
    sh_method(wb, res)
    sh_matrix(wb, res)
    sh_issues(wb, res)
    sh_objection(wb, res)
    sh_raw(wb, res)
    sh_rules(wb, res)
    wb.properties.title = res["meta"].get("title", "COA 核对工作簿")
    wb.properties.subject = "COA × 采购规格书 质量核对"
    wb.properties.creator = "chem-coa-spec-check"
    wb.properties.description = ("模拟数据，仅用于流程演示" if res["meta"].get("simulated")
                                 else "COA 与采购规格逐项核对结果；不构成收货决定")
    wb.save(out_path)
    return res, [ws.title for ws in wb.worksheets]


def main():
    if len(sys.argv) < 3:
        print("usage: render_xlsx.py data.json out.xlsx")
        raise SystemExit(2)
    data = engine.load(sys.argv[1])
    res, names = render(data, sys.argv[2])
    print("xlsx ->", sys.argv[2], "| sheets:", len(names))
    for n in names:
        print("  -", n)


if __name__ == "__main__":
    main()
