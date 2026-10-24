# -*- coding: utf-8 -*-
"""生成《危险化学品买方资质与销售合规提醒》Excel 工作簿。

用法:
    python build_workbook.py case.json out.xlsx
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case_lib import count_status, initials, load_case, retention_summary, status_meta, verdict_style  # noqa: E402

FONT = "微软雅黑"
INK = "1F2A37"
NAVY = "0F3D56"
TEAL = "0E7490"
MUTED = "5B6B7C"
BORDER = "D6DEE7"
BAND = "F3F7FA"
WHITE = "FFFFFF"

THIN = Side(style="thin", color=BORDER)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def f(size=10, bold=False, color=INK, italic=False) -> Font:
    return Font(name=FONT, size=size, bold=bold, color=color, italic=italic)


def fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def wrap_center() -> Alignment:
    return Alignment(horizontal="center", vertical="center", wrap_text=True)


def wrap_left(indent=0) -> Alignment:
    return Alignment(horizontal="left", vertical="top", wrap_text=True, indent=indent)


def set_widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def cn_len(text) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def auto_height(ws, row: int, widths, min_h=18, line_h=15.5, pad=4):
    """按合并列宽估算行高，避免文字被裁切。"""
    total = sum(widths) if isinstance(widths, (list, tuple)) else widths
    lines = 1
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=row, column=col)
        if cell.value is None:
            continue
        width = ws.column_dimensions[get_column_letter(col)].width or 10
        if isinstance(cell, type(None)):
            continue
        lines = max(lines, math.ceil(cn_len(cell.value) / max(width * 1.02, 4)))
    ws.row_dimensions[row].height = max(min_h, lines * line_h + pad)


def title_band(ws, row: int, text: str, sub: str = "", span=6, fill_color=NAVY):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    c = ws.cell(row=row, column=1, value=text)
    c.font = f(16, True, WHITE)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    c.fill = fill(fill_color)
    ws.row_dimensions[row].height = 34
    if sub:
        ws.merge_cells(start_row=row + 1, start_column=1, end_row=row + 1, end_column=span)
        s = ws.cell(row=row + 1, column=1, value=sub)
        s.font = f(9, False, "E6EEF5")
        s.fill = fill(fill_color)
        s.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[row + 1].height = 20
        return row + 3
    return row + 2


def section(ws, row: int, text: str, span=6, color=TEAL):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    c = ws.cell(row=row, column=1, value=text)
    c.font = f(11, True, WHITE)
    c.fill = fill(color)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 24
    return row + 1


def kv_block(ws, row: int, pairs, label_w=18, span=6, widths=None):
    """两列键值块：A 列标签，B..span 合并值。"""
    for label, value in pairs:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = f(10, True, NAVY)
        lc.fill = fill(BAND)
        lc.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
        lc.border = BOX
        ws.cell(row=row, column=2).border = BOX

        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=span)
        vc = ws.cell(row=row, column=3, value=value)
        vc.font = f(10, False, INK)
        vc.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
        vc.border = BOX
        for col in range(3, span + 1):
            ws.cell(row=row, column=col).border = BOX
        if widths:
            w = sum(widths[2:span])
            lines = max(1, math.ceil(cn_len(value) / max(w * 1.0, 6)))
            ws.row_dimensions[row].height = max(22, lines * 16 + 6)
        row += 1
    return row


def table(ws, row: int, headers, rows, widths, status_col=None, link_cols=(), zebra=True,
          header_fill=NAVY, center_cols=(), bold_first=False, height_col=None):
    for idx, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=idx, value=h)
        c.font = f(9.5, True, WHITE)
        c.fill = fill(header_fill)
        c.alignment = wrap_center()
        c.border = BOX
    ws.row_dimensions[row].height = 30
    row += 1
    for r_idx, values in enumerate(rows):
        for idx, val in enumerate(values, start=1):
            c = ws.cell(row=row, column=idx, value=val)
            c.font = f(9.5, bold=(bold_first and idx == 1), color=INK)
            c.alignment = wrap_left() if idx not in center_cols else wrap_center()
            c.border = BOX
            if zebra and r_idx % 2 == 1:
                c.fill = fill("F8FAFC")
        if status_col:
            code = values[status_col - 1]
            meta = status_meta(str(code))
            cell = ws.cell(row=row, column=status_col)
            cell.fill = fill(meta["hex"])
            cell.font = f(9.5, True, meta["hex_deep"])
            cell.alignment = wrap_center()
        for lc in link_cols:
            cell = ws.cell(row=row, column=lc)
            if isinstance(cell.value, str) and cell.value.startswith("http"):
                cell.hyperlink = cell.value
                cell.font = f(8.5, False, "1155CC", italic=False)
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        lines = 1
        for idx, val in enumerate(values, start=1):
            if idx == status_col:
                continue
            w = widths[idx - 1]
            lines = max(lines, math.ceil(cn_len(val) / max(w * 1.02, 5)))
        ws.row_dimensions[row].height = max(22, lines * 14.5 + 6)
        row += 1
    return row


def legend_row(ws, row: int, items, span=6):
    col = 1
    for item in items:
        c = ws.cell(row=row, column=col, value=f"{item['code']}  {item['label']}：{item['desc']}")
        c.font = f(8.5, False, status_meta(item["code"])["hex_deep"])
        c.fill = fill(status_meta(item["code"])["hex"])
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
        c.border = BOX
        ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=min(col + 1, span))
        col += 2
    ws.row_dimensions[row].height = 34
    return row + 1


def build(case: dict, out_path: Path):
    meta = case["meta"]
    product = case["product"]
    det = case["determination"]
    checks = case["buyer_checks"]
    st = count_status(checks)
    vs = verdict_style(det["code"])

    wb = Workbook()

    # ---------------- 00 封面 ----------------
    ws = wb.active
    ws.title = "00 封面与导读"
    ws.sheet_view.showGridLines = False
    set_widths(ws, [13, 24, 24, 24, 24, 24])
    ws.merge_cells("A1:F2")
    c = ws["A1"]
    c.value = "危险化学品买方资质与销售合规提醒"
    c.font = f(24, True, WHITE)
    c.fill = fill(NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 34
    ws.row_dimensions[2].height = 22

    ws.merge_cells("A3:F3")
    c = ws["A3"]
    c.value = f"{meta['title']} ｜ 案例编号 {meta['case_no']} ｜ 判定日 {meta['as_of']}"
    c.font = f(11, False, "DCE9F2")
    c.fill = fill(NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[3].height = 26

    row = 5
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    c = ws.cell(row=row, column=1, value=f"{vs['icon']}  产品判定：{det['verdict']}")
    c.font = f(20, True, WHITE)
    c.fill = fill(vs["deep"])
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 44
    row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    c = ws.cell(row=row, column=1, value=det["one_line"])
    c.font = f(10.5, False, INK)
    c.fill = fill(vs["hex"])
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[row].height = 46
    row += 2

    pairs = [
        ("卖方", f"{meta['seller']['name']} ｜ {meta['seller']['role']}"),
        ("买方", f"{meta['buyer']['name']}（{meta['buyer']['ticker']}）"),
        ("买方厂区", meta["buyer"]["site"]),
        ("产品", f"{product['name']} ｜ CAS {product['cas']} ｜ {product['grade']}"),
        ("数量", meta["deal"]["qty"]),
        ("用途", f"{meta['deal']['use_type']}：{meta['deal']['use_detail']}"),
        ("交货", meta["deal"]["delivery"]),
        ("合规结论", f"危化品经营许可 {det['flags'][0]['label']} → 否；公安备案 → 无需；法定记录留存 → 无 3 年强制要求"),
    ]
    row = kv_block(ws, row, pairs, widths=[13, 24, 24, 24, 24, 24])
    row += 1

    row = section(ws, row, "本工作簿包含的内容", span=6)
    contents = [
        ("01 产品身份确认", "浓度/形态/等级是否改变判定；规格与标识口径"),
        ("02 危险属性判定卡", "结论、7 项名录标记、GHS 分类、判定后果"),
        ("03 判定依据", "逐条法条/目录/标准与置信度，可点开核验"),
        ("04 买方资质核查", "A 公开可见 / B 需核对原件 / C 无公开信息 / NA 不适用"),
        ("05 合规检查清单", "销售方、买方、双方共 19 项，可勾选、可打印"),
        ("06 需索取的证照", "12 项，含用途、形式、有效期与必备性"),
        ("07 留存与备案矩阵", "每项义务的留存年限、备案机关与时限"),
        ("08 缺口与索要话术", "5 个缺口 + 正式邮件 + 微信短版"),
        ("09 同流程产品对照", "纯碱 / 烧碱 / 硫酸 / 甲醇 / 双氧水 / 小苏打"),
        ("10 法规索引与版本", "13 条来源，含发布日期与用途"),
        ("11 人工确认与免责", "6 项必须由人确认的事项"),
    ]
    for name, desc in contents:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        c = ws.cell(row=row, column=1, value=name)
        c.font = f(10, True, NAVY)
        c.fill = fill(BAND)
        c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        c.border = BOX
        ws.cell(row=row, column=2).border = BOX
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=6)
        c = ws.cell(row=row, column=3, value=desc)
        c.font = f(9.5, False, MUTED)
        c.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
        for col in range(3, 7):
            ws.cell(row=row, column=col).border = BOX
        ws.row_dimensions[row].height = 22
        row += 1

    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    c = ws.cell(row=row, column=1, value="使用说明")
    c.font = f(10, True, NAVY)
    row += 1
    tips = [
        "1. 先看 02 判定卡：确认“非危险化学品”结论与三条不适用（经营许可 / 购买资质 / 公安备案）。",
        "2. 再看 04 核查表：A 类可直接引用；B 类必须拿到原件；C 类写入索取清单。",
        "3. 05 清单的“状态”列是下拉框，勾选后请同步 08 的话术，缺口项当天发给买方。",
        "4. 本文件为资料提醒，不构成法律意见；法规更新或产品成分变化时须重新判定。",
    ]
    for t in tips:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        c = ws.cell(row=row, column=1, value=t)
        c.font = f(9.5, False, INK)
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
        ws.row_dimensions[row].height = 22
        row += 1

    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row + 1, end_column=6)
    c = ws.cell(row=row, column=1, value="免责声明：" + meta["disclaimer"])
    c.font = f(8.5, False, MUTED, italic=True)
    c.fill = fill("F8FAFC")
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    c.border = BOX
    ws.row_dimensions[row].height = 26
    ws.row_dimensions[row + 1].height = 26
    ws.sheet_properties.tabColor = NAVY

    # ---------------- 01 产品身份 ----------------
    ws = wb.create_sheet("01 产品身份确认")
    ws.sheet_view.showGridLines = False
    widths = [6, 26, 26, 18, 40]
    set_widths(ws, widths)
    row = title_band(ws, 1, "01 产品身份确认", "浓度、形态、等级都可能改变判定与合规路径；先锁定身份，再出结论。", span=5)

    row = section(ws, row, "基本信息", span=5)
    base = [
        ("产品名称", product["name"]),
        ("通用名/别名", product["alias"]),
        ("CAS 号", product["cas"]),
        ("分子式 / 相对分子质量", f"{product['formula']} / {product['mw']}"),
        ("外观与形态", product["appearance"]),
        ("等级与执行标准", f"{product['grade']}；{product['standard']}"),
        ("包装", product["packing"]),
        ("储存与保质期", f"{product['storage']}；{product['shelf_life']}"),
        ("HS 编码（参考）", product["hs_code"]),
    ]
    row = kv_block(ws, row, base, widths=widths, span=5)
    row += 1

    row = section(ws, row, "身份确认问答：这些问题会改变判定或合规路径", span=5)
    rows = [[i + 1, q["q"], q["a"], q["impact"]] for i, q in enumerate(product["identity_checks"])]
    row = table(ws, row, ["#", "问题", "结论", "影响"], rows, [6, 26, 60, 22],
                center_cols=(1,), height_col=3)
    row += 1

    row = section(ws, row, "典型规格（以 GB/T 210-2022 与批次 COA 为准）", span=5)
    rows = [[s["item"], s["value"], s["unit"], s["note"]] for s in product["spec_table"]]
    row = table(ws, row, ["项目", "典型值", "单位", "说明"], rows, [30, 14, 10, 52],
                center_cols=(2, 3))
    row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    c = ws.cell(row=row, column=1, value="⚠ " + product["identity_caution"])
    c.font = f(9.5, True, "92400E")
    c.fill = fill("FDF3D8")
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    c.border = BOX
    ws.row_dimensions[row].height = 34
    ws.sheet_properties.tabColor = TEAL

    # ---------------- 02 判定卡 ----------------
    ws = wb.create_sheet("02 危险属性判定卡")
    ws.sheet_view.showGridLines = False
    widths = [8, 34, 12, 46, 26]
    set_widths(ws, widths)
    row = title_band(ws, 1, "02 危险属性判定卡", "结论 + 依据 + 边界；判定口径与置信度写在卡面上，方便复核。", span=5)

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    c = ws.cell(row=row, column=1, value=f"判定结论：{det['verdict']}")
    c.font = f(18, True, WHITE)
    c.fill = fill(vs["deep"])
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 40
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    c = ws.cell(row=row, column=1, value=det["one_line"])
    c.font = f(10, False, INK)
    c.fill = fill(vs["hex"])
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[row].height = 44
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    c = ws.cell(row=row, column=1, value=f"判定级别：{det['level']} ｜ 置信度：{det['confidence']}")
    c.font = f(9, False, MUTED)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 20
    row += 2

    row = section(ws, row, "8 项名录标记", span=5)
    rows = []
    for fl in det["flags"]:
        ok = "✓ 否（不适用）" if fl["value"] is False else "！是"
        rows.append([fl["key"], fl["label"], ok, fl["note"]])
    row = table(ws, row, ["键", "名录 / 判定项", "结论", "说明"], rows, [14, 34, 16, 62],
                center_cols=(3,), zebra=True)
    row += 1

    row = section(ws, row, "GHS 危险分类（按 SDS）", span=5)
    rows = [[g["class"], g["category"], g["h"]] for g in det["ghs"]]
    row = table(ws, row, ["危险性类别", "类别", "危害说明"], rows, [34, 18, 56],
                center_cols=(2,))
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    c = ws.cell(row=row, column=1, value="说明：" + det["ghs_note"])
    c.font = f(9, False, MUTED)
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[row].height = 32
    row += 2

    row = section(ws, row, "本次交易的直接后果", span=5)
    cons = [
        ("经营许可", det["consequence"]["license"]),
        ("备案", det["consequence"]["filing"]),
        ("记录留存", det["consequence"]["records"]),
        ("运输", det["consequence"]["transport"]),
        ("罚则提示", det["consequence"]["penalty_note"]),
    ]
    row = kv_block(ws, row, cons, widths=widths, span=5)
    row += 1

    row = section(ws, row, "边界条件：什么情况下结论会变", span=5)
    rows = [[b["scenario"], b["effect"]] for b in det["boundary"]]
    row = table(ws, row, ["情形", "对判定的影响"], rows, [40, 68])
    row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    c = ws.cell(row=row, column=1, value="复核步骤：" + "；".join(det["verification_steps"]))
    c.font = f(8.5, False, MUTED)
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[row].height = 44
    ws.sheet_properties.tabColor = vs["deep"]
    ws.freeze_panes = "A4"

    # ---------------- 03 判定依据 ----------------
    ws = wb.create_sheet("03 判定依据")
    ws.sheet_view.showGridLines = False
    widths = [5, 52, 30, 46, 16, 30]
    set_widths(ws, widths)
    row = title_band(ws, 1, "03 判定依据（逐条可核验）", "每条都标注来源、条款、置信度与链接；低置信度不得直接对外引用。", span=6)
    rows = []
    for i, b in enumerate(det["basis"], start=1):
        rows.append([i, b["claim"], f"{b['source']} {b['article']}", b["detail"], b["confidence"], b["url"] or "—"])
    row = table(ws, row, ["#", "判定主张", "来源 / 条款", "说明", "置信度", "链接"], rows,
                [5, 52, 30, 46, 16, 30], link_cols=(6,), center_cols=(1, 5))
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    c = ws.cell(row=row, column=1, value="注：链接为公开可访问来源；政府网站偶有改版，若链接失效请按“来源 + 条款”检索原文。")
    c.font = f(8.5, False, MUTED, italic=True)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 20
    ws.sheet_properties.tabColor = "7C3AED"
    ws.freeze_panes = "A4"

    # ---------------- 04 买方核查 ----------------
    ws = wb.create_sheet("04 买方资质核查")
    ws.sheet_view.showGridLines = False
    widths = [5, 8, 26, 14, 12, 52, 30, 30, 8]
    set_widths(ws, widths)
    row = title_band(ws, 1, "04 买方公开资质核查",
                     f"{meta['buyer']['name']} ｜ 三种状态分开写：公开可见 / 需核对原件 / 无公开信息", span=9)

    # 统计条
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
    c = ws.cell(row=row, column=1,
                value=f"共 {st['total']} 项：A 公开可见 {st['A']} 项 ｜ B 需核对原件 {st['B']} 项 ｜ C 无公开信息 {st['C']} 项 ｜ NA 不适用 {st['NA']} 项")
    c.font = f(10, True, NAVY)
    c.fill = fill(BAND)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 24
    row += 1
    row = legend_row(ws, row, case["status_legend"], span=9)
    row += 1

    rows = []
    for i, ck in enumerate(checks, start=1):
        ev = "；".join(f"{e['label']}" for e in ck.get("evidence", [])) or "—"
        rows.append([i, ck["id"], ck["item"], ck["category"], ck["status"], ck["finding"], ev, ck["ask"], ck["risk"]])
    row = table(ws, row, ["#", "编号", "核查项", "类别", "状态", "公开核查结论", "公开证据", "需向买方索取", "风险"],
                rows, [5, 8, 26, 14, 12, 52, 30, 30, 8], status_col=5, center_cols=(1, 2, 4, 5, 9))
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
    c = ws.cell(row=row, column=1,
                value="状态口径：A 已取得可点开证据；B 有公开入口/间接证据但未取得原件，不能据此下结论；C 公开渠道无此类信息，必须索取；NA 对本品种/用途不适用（附依据）。")
    c.font = f(8.5, False, MUTED)
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[row].height = 28
    ws.sheet_properties.tabColor = "B45309"
    ws.freeze_panes = "A6"

    # ---------------- 05 合规清单 ----------------
    ws = wb.create_sheet("05 合规检查清单")
    ws.sheet_view.showGridLines = False
    widths = [5, 8, 10, 58, 34, 16, 12, 14, 24, 12, 12, 18]
    set_widths(ws, widths)
    row = title_band(ws, 1, "05 合规检查清单（可勾选）",
                     "状态列是下拉框；建议本周内完成“未开始”的销售方事项，买方事项随索要函发出。", span=12)

    all_items = []
    for group, key in (("销售方", "seller"), ("买方", "buyer"), ("双方", "joint")):
        for o in case["obligations"][key]:
            all_items.append((group, o))

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=12)
    c = ws.cell(row=row, column=1, value=f"共 {len(all_items)} 项：销售方 {len(case['obligations']['seller'])} 项 ｜ 买方 {len(case['obligations']['buyer'])} 项 ｜ 双方 {len(case['obligations']['joint'])} 项")
    c.font = f(10, True, NAVY)
    c.fill = fill(BAND)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 24
    row += 1

    rows = []
    for i, (group, o) in enumerate(all_items, start=1):
        rows.append([i, o["id"], group, o["item"], o["basis"], o["retention"], o["filing"], o["timing"],
                     o["evidence"], "未开始", "", ""])
    row = table(ws, row, ["#", "编号", "责任方", "事项", "依据", "留存年限", "是否备案", "时点", "证据形式", "状态", "完成日期", "备注"],
                rows, [5, 8, 10, 58, 34, 16, 12, 14, 24, 12, 12, 18],
                center_cols=(1, 2, 3, 6, 7, 8, 10, 11))
    last_row = row - 1
    dv = DataValidation(type="list", formula1='"未开始,进行中,已完成,不适用"', allow_blank=True)
    dv.error = "请选择：未开始 / 进行中 / 已完成 / 不适用"
    dv.promptTitle = "状态"
    dv.prompt = "勾选后请同步更新 08 话术与缺口"
    ws.add_data_validation(dv)
    dv.add(f"J6:J{last_row}")
    ws.conditional_formatting.add(
        f"J6:J{last_row}",
        CellIsRule(operator="equal", formula=['"已完成"'], fill=fill("E7F6EC"), font=Font(name=FONT, color="166534", bold=True)),
    )
    ws.conditional_formatting.add(
        f"J6:J{last_row}",
        CellIsRule(operator="equal", formula=['"进行中"'], fill=fill("FDF3D8"), font=Font(name=FONT, color="92400E", bold=True)),
    )
    ws.freeze_panes = "D6"
    ws.auto_filter.ref = f"A5:L{last_row}"
    ws.sheet_properties.tabColor = "0E7490"

    # ---------------- 06 索取证照 ----------------
    ws = wb.create_sheet("06 需索取证照")
    ws.sheet_view.showGridLines = False
    widths = [5, 8, 34, 12, 40, 30, 20, 12, 34]
    set_widths(ws, widths)
    row = title_band(ws, 1, "06 需向买方索取的证照与资料", "必备 / 建议 / 可选 / 分支必备 四档；不要一次全要，按本单实际用途取。", span=9)
    rows = []
    for i, d in enumerate(case["documents"], start=1):
        rows.append([i, d["id"], d["name"], d["issuer"], d["purpose"], d["form"], d["validity"], d["mandatory"], d["note"]])
    row = table(ws, row, ["#", "编号", "资料", "提供方", "用途", "形式", "有效期", "必备性", "备注"],
                rows, [5, 8, 34, 12, 40, 30, 20, 12, 34], center_cols=(1, 2, 4, 8))
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
    c = ws.cell(row=row, column=1, value="提示：本单为非危化品，D10（食品生产许可）与 D11（下游转售资质）仅在食品级/转售分支需要；常规工业级交易不必索取，避免给客户造成“被额外审查”的感受。")
    c.font = f(8.5, False, MUTED)
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[row].height = 30
    ws.sheet_properties.tabColor = "B45309"

    # ---------------- 07 留存与备案 ----------------
    ws = wb.create_sheet("07 留存与备案矩阵")
    ws.sheet_view.showGridLines = False
    widths = [8, 8, 56, 34, 18, 14, 14, 24]
    set_widths(ws, widths)
    row = title_band(ws, 1, "07 留存年限与备案矩阵",
                     "口径：危化品销售记录 ≥3 年（法第六十一条）；本单为一般化工品，商务资料建议 ≥5 年，会计凭证 30 年。", span=8)
    rows = []
    for r in retention_summary(case):
        rows.append([r["id"], r["group"], r["item"], r["basis"], r["retention"], r["filing"], r["timing"], r["evidence"]])
    row = table(ws, row, ["编号", "责任方", "事项", "依据", "留存年限", "是否备案", "时点", "证据"],
                rows, [8, 8, 56, 34, 18, 14, 14, 24], center_cols=(1, 2, 6, 7))
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
    c = ws.cell(row=row, column=1, value="结论：本单无需向公安机关或应急管理部门备案；无危化品销售记录 3 年强制要求。若同车/同合同混入烧碱、硫酸等危化品，留存与备案按危化品口径单独执行。")
    c.font = f(9, True, "166534")
    c.fill = fill("E7F6EC")
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    c.border = BOX
    ws.row_dimensions[row].height = 32
    ws.sheet_properties.tabColor = "166534"

    # ---------------- 08 缺口与话术 ----------------
    ws = wb.create_sheet("08 缺口与索要话术")
    ws.sheet_view.showGridLines = False
    widths = [5, 8, 44, 36, 52, 10, 12]
    set_widths(ws, widths)
    row = title_band(ws, 1, "08 缺口清单与索要话术", "缺口 → 一句话要什么 → 可直接复制的邮件/微信草稿。", span=7)

    row = section(ws, row, "缺口清单", span=7)
    rows = []
    for i, g in enumerate(case["gaps"], start=1):
        rows.append([i, g["id"], g["gap"], g["why"], g["ask"], g["severity"], g["owner"]])
    row = table(ws, row, ["#", "编号", "缺口", "为什么重要", "要什么", "严重度", "对接人"],
                rows, [5, 8, 44, 36, 52, 10, 12], center_cols=(1, 2, 6))
    row += 1

    row = section(ws, row, "邮件草稿（可直接改）", span=7)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    c = ws.cell(row=row, column=1, value="主题：" + case["draft"]["subject"])
    c.font = f(10, True, NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    c.border = BOX
    ws.row_dimensions[row].height = 24
    row += 1
    body = case["draft"]["formal"]
    lines = body.count("\n") + 1
    est = 0
    for para in body.split("\n"):
        est += max(1, math.ceil(cn_len(para) / 78))
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    c = ws.cell(row=row, column=1, value=body)
    c.font = f(9.5, False, INK)
    c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True, indent=1)
    c.border = BOX
    ws.row_dimensions[row].height = min(560, max(160, est * 15.5 + lines * 2))
    row += 2

    row = section(ws, row, "微信短版", span=7, color="166534")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    c = ws.cell(row=row, column=1, value=case["draft"]["wechat"])
    c.font = f(9.5, False, INK)
    c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True, indent=1)
    c.border = BOX
    ws.row_dimensions[row].height = 100
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    c = ws.cell(row=row, column=1, value="使用提醒：首单优先索取 D1–D4（执照/开票/收货授权/用途），D5–D6 可后补；不要在首封邮件中列全部 12 项，容易造成准入受阻的错觉。")
    c.font = f(8.5, False, MUTED, italic=True)
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[row].height = 28
    ws.sheet_properties.tabColor = "92400E"

    # ---------------- 09 同流程对照 ----------------
    ws = wb.create_sheet("09 同流程产品对照")
    ws.sheet_view.showGridLines = False
    widths = [26, 14, 30, 26, 34, 34, 18, 36]
    set_widths(ws, widths)
    row = title_band(ws, 1, "09 同流程产品对照（演示判定引擎）",
                     "同一个流程换产品，结论与义务完全不同；本表为对照示例，逐条仍须按目录原文核验。", span=8)
    rows = []
    for p in case["cross_products"]:
        rows.append([p["name"], p["cas"], p["verdict"], p["flags"], p["buyer_req"], p["seller_req"], p["transport"], p["note"]])
    row = table(ws, row, ["产品", "CAS", "判定", "特殊名录", "买方要求", "销售方要求", "运输", "备注"],
                rows, [26, 14, 30, 26, 34, 34, 18, 36], center_cols=(2,))
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
    c = ws.cell(row=row, column=1,
                value="对照要点：①纯碱与小苏打是“碱”但不是危化品，最易与烧碱混称；②硫酸是易制毒第三类，购买要公安备案；③双氧水含量 >8% 即属易制爆，销售方要记录 3 年、3 日内报公安备案；④甲醇属重点监管，储存装卸要求高。")
    c.font = f(9, False, MUTED)
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[row].height = 40
    ws.sheet_properties.tabColor = "7C3AED"

    # ---------------- 10 法规索引 ----------------
    ws = wb.create_sheet("10 法规索引")
    ws.sheet_view.showGridLines = False
    widths = [6, 10, 52, 30, 44, 14, 40]
    set_widths(ws, widths)
    row = title_band(ws, 1, "10 法规索引与版本", f"检索时点 {meta['as_of']}；法规更新后须重新核验。", span=7)
    rows = []
    for i, s in enumerate(case["sources"], start=1):
        rows.append([i, s["type"], s["title"], s["publisher"], s["url"], s["date"], s["used_for"]])
    row = table(ws, row, ["#", "类型", "名称", "发布机构", "链接", "日期", "本次用途"],
                rows, [6, 10, 52, 30, 44, 14, 40], link_cols=(5,), center_cols=(1, 2, 6))
    ws.sheet_properties.tabColor = "334155"

    # ---------------- 11 人工确认与免责 ----------------
    ws = wb.create_sheet("11 人工确认与免责")
    ws.sheet_view.showGridLines = False
    widths = [6, 30, 52, 26, 16, 40]
    set_widths(ws, widths)
    row = title_band(ws, 1, "11 必须由人确认的事项", "以下 6 项机器不能替代：确认后才可对外出具判定或承诺。", span=6)
    rows = []
    for i, m in enumerate(case["manual_confirm"], start=1):
        rows.append([i, m["item"], m["why"], m["who"], m["deadline"], "☐ 已确认"])
    row = table(ws, row, ["#", "确认项", "为什么必须人工确认", "谁确认", "截止", "状态"],
                rows, [5, 30, 52, 26, 14, 14], center_cols=(1, 4, 5, 6))
    row += 1
    row = section(ws, row, "免责声明", span=6, color="991B1B")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    c = ws.cell(row=row, column=1, value=meta["disclaimer"])
    c.font = f(9.5, False, "7F1D1D")
    c.fill = fill("FDE7E7")
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    c.border = BOX
    ws.row_dimensions[row].height = 64
    row += 2
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    c = ws.cell(row=row, column=1, value="版本：v1.0 ｜ 判定日：2026-10-19 ｜ 适用法律：《危险化学品安全法》（2026-05-01 施行）｜ 数据来源见 10 法规索引")
    c.font = f(8.5, False, MUTED)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.sheet_properties.tabColor = "991B1B"

    # 统一页面设置
    for sh in wb.worksheets:
        sh.page_setup.orientation = "landscape"
        sh.page_setup.fitToWidth = 1
        sh.page_setup.fitToHeight = 0
        sh.sheet_properties.pageSetUpPr.fitToPage = True
        sh.print_options.horizontalCentered = True
        sh.page_margins.left = 0.3
        sh.page_margins.right = 0.3
        sh.page_margins.top = 0.4
        sh.page_margins.bottom = 0.4

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def main(argv):
    if len(argv) < 3:
        print("用法: python build_workbook.py case.json out.xlsx")
        return 2
    case = load_case(argv[1])
    out = build(case, Path(argv[2]))
    from openpyxl import load_workbook
    n = len(load_workbook(out).sheetnames)
    print(f"OK  {out}  sheets={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
