# -*- coding: utf-8 -*-
"""
render_xlsx.py — data.json -> 14 页签 Excel 证照与监管要求核验台账

用法： python render_xlsx.py data.json --out ./out
依赖： openpyxl（pip install openpyxl）
输出： <out>/证照与监管要求核验台账_<主体简称>_<产品简称>.xlsx
"""

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qclib as L

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:  # pragma: no cover
    Workbook = None

# ---------------------------------------------------------------- 配色（与 HTML 同源）
DEEP = "12312A"
DEEP2 = "1B4239"
BRASS = "A8843C"
CREAM = "F7F5EF"
CREAM2 = "F1EDE1"
LINE = "D9D3C3"
OK_BG, OK_FG = "E8F3EC", "1F7A4D"
BAD_BG, BAD_FG = "FBE9E4", "B3402A"
WARN_BG, WARN_FG = "FBF2DD", "A9761B"
GRAY_BG, GRAY_FG = "EEF0F1", "6B7280"

THIN = Side(style="thin", color=LINE)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

STATE_STYLE = {
    "verified": (OK_BG, OK_FG), "mismatch": (BAD_BG, BAD_FG), "pending": (WARN_BG, WARN_FG),
    "no_public": (GRAY_BG, GRAY_FG), "expired": ("F6E3E0", "8B1E1E"),
}
COVER_STYLE = {"cover": (OK_BG, OK_FG), "partial": (WARN_BG, WARN_FG), "not_cover": (BAD_BG, BAD_FG), "unknown": (GRAY_BG, GRAY_FG)}
VERDICT_STYLE = {"confirmed": (OK_BG, OK_FG), "not_confirmed": (BAD_BG, BAD_FG), "pending": (WARN_BG, WARN_FG)}

LAST_UPDATED = "2026-10-12"


def F(bold=False, size=10, color="18231F", name="微软雅黑"):
    return Font(name=name, size=size, bold=bold, color=color)


def fill(hexcolor):
    return PatternFill("solid", fgColor=hexcolor)


def title_block(ws, title, sub, ncols, record):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=title)
    c.font = F(True, 15, "FFFFFF")
    c.fill = fill(DEEP)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c = ws.cell(row=2, column=1, value=sub + "    ｜    " + record)
    c.font = F(False, 9, DEEP2)
    c.fill = fill(CREAM)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[2].height = 20
    for col in range(1, ncols + 1):
        ws.cell(row=1, column=col).fill = fill(DEEP)
        ws.cell(row=2, column=col).fill = fill(CREAM)


def header_row(ws, row, cols, widths=None):
    for i, name in enumerate(cols, 1):
        c = ws.cell(row=row, column=i, value=name)
        c.font = F(True, 9.5, "FFFFFF")
        c.fill = fill(DEEP2)
        c.border = BOX
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if widths and i - 1 < len(widths) and widths[i - 1]:
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    ws.row_dimensions[row].height = 28


def body_row(ws, r, values, aligns=None, wraps=None, styles=None, h=None):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=r, column=i, value=v)
        c.font = F(False, 9.5)
        c.border = BOX
        al = (aligns[i - 1] if aligns and i - 1 < len(aligns) else "left")
        wr = (wraps[i - 1] if wraps and i - 1 < len(wraps) else True)
        c.alignment = Alignment(horizontal=al, vertical="top", wrap_text=wr)
        if r % 2 == 0:
            c.fill = fill("FBFAF5")
        if styles and i - 1 < len(styles) and styles[i - 1]:
            bg, fg = styles[i - 1]
            c.fill = fill(bg)
            c.font = F(True, 9.5, fg)
    if h:
        ws.row_dimensions[r].height = h


def state_style(st):
    return STATE_STYLE.get(st, (WARN_BG, WARN_FG))


def verdict_style(v):
    return VERDICT_STYLE.get(v, (WARN_BG, WARN_FG))


def cover_style(c):
    return COVER_STYLE.get(c, (GRAY_BG, GRAY_FG))


# ---------------------------------------------------------------- 各页签

def sh_cover(wb, d):
    ws = wb.active
    ws.title = "00 封面与说明"
    ws.sheet_properties.tabColor = BRASS
    ncols = 6
    title_block(ws, "化学品供应商资质证照 · 监管要求核验台账",
                "由 chem-supplier-qualification 技能生成；监管分类以主管部门公示与证照原件为最终依据", ncols,
                "记录号 %s" % d.get("meta", {}).get("record_id", ""))
    rows = [
        ("台账名称", d.get("title", "")),
        ("核验基准日 as_of", d.get("as_of", "")),
        ("主体（供应商）", (d.get("subject") or {}).get("name", "")),
        ("统一社会信用代码", (d.get("subject") or {}).get("uscc", "")),
        ("采购物料", (d.get("product") or {}).get("name", "")),
        ("规格／浓度", (d.get("product") or {}).get("spec", "")),
        ("CAS 登记号", (d.get("product") or {}).get("cas", "")),
        ("采购方（我方）", (d.get("erp") or {}).get("name", "")),
        ("总体判定", "%s %s" % ((d.get("assessment") or {}).get("grade_code", ""), (d.get("assessment") or {}).get("grade", ""))),
        ("一句话结论", (d.get("assessment") or {}).get("one_liner", "")),
        ("编制", d.get("meta", {}).get("prepared_by", "")),
        ("生成时间", d.get("meta", {}).get("generated_at", "")),
    ]
    r = 4
    for k, v in rows:
        c = ws.cell(row=r, column=1, value=k)
        c.font = F(True, 10, DEEP)
        c.fill = fill(CREAM2)
        c.border = BOX
        c.alignment = Alignment(vertical="top", indent=1)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=ncols)
        c2 = ws.cell(row=r, column=2, value=v)
        c2.font = F(False, 10)
        c2.border = BOX
        c2.alignment = Alignment(vertical="top", wrap_text=True)
        rs = len(str(v)) // 60 + 1
        ws.row_dimensions[r].height = max(20, 16 * rs)
        r += 1
    ws.column_dimensions["A"].width = 22
    for col in "BCDEF":
        ws.column_dimensions[col].width = 26

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
    c = ws.cell(row=r, column=1, value="本台账的使用纪律（务必先读）")
    c.font = F(True, 11, "FFFFFF")
    c.fill = fill(BRASS)
    c.alignment = Alignment(vertical="center", indent=1)
    r += 1
    rules = [
        ("四态互斥", "证照只允许处于「已核验 / 信息不一致 / 待核验 / 无公开信息」四态之一；过期单独以「已过期」标记。不得混写、不得用一份证件推断企业整体合规。"),
        ("查不到≠无证", "「无公开信息」只表示本次定向检索未发现公开记录，必须原样转入索证清单，不得写成「企业无证」。"),
        ("不得推断", "不得根据企业名称、经营范围、行业常识推断许可状态；许可范围必须逐字核对是否覆盖拟采购产品与浓度。"),
        ("时间基准", "全表只有一个 as_of 日期；有效期、到期提醒、是否过期都相对它计算，替换日期即可重算。"),
        ("交叉核验", "上传扫描件/OCR 字段只能作 A 侧，必须与主管部门公示（B 侧）逐字段比对；不一致即「信息不一致」。"),
        ("最终依据", "本台账不替代主管部门公示与证照原件；出具采购决定前须完成第 12 页「人工核验事项」。"),
        ("模拟件标注", "凡 mode=mock 的扫描件均为模拟演示文件，严禁当作真实证照使用。"),
    ]
    for k, v in rules:
        c = ws.cell(row=r, column=1, value=k)
        c.font = F(True, 9.5, BAD_FG)
        c.fill = fill(BAD_BG)
        c.border = BOX
        c.alignment = Alignment(vertical="top", indent=1)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=ncols)
        c2 = ws.cell(row=r, column=2, value=v)
        c2.font = F(False, 9.5)
        c2.border = BOX
        c2.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = 30 if len(v) < 60 else 44
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
    c = ws.cell(row=r, column=1, value="页签导航")
    c.font = F(True, 11, "FFFFFF")
    c.fill = fill(BRASS)
    c.alignment = Alignment(vertical="center", indent=1)
    r += 1
    nav = [("01 主体识别", "工商身份、信用代码校验、企业关系链"),
           ("02 产品监管识别", "CAS/浓度/剂型 → 危险化学品与特殊管理类别"),
           ("03 监管分类核验单", "逐项打勾：已确认 / 未确认（≠不属于） / 待核验"),
           ("04 供应商许可要求", "生产/经营/储存各类许可的适用条件与核验要点"),
           ("05 采购方义务", "买方的许可、备案、流向登记与安全管理义务"),
           ("06 证照台账", "核心表：证书、编号、机关、有效期、许可范围、状态"),
           ("07 有效期与范围比对", "自动计算剩余天数，自动判定是否覆盖本采购"),
           ("08 交叉核验记录", "证照字段 × 主管部门公示 × 工商身份"),
           ("09 索证清单", "必须索取原件的证照 + 确认问题（含自动派生项）"),
           ("10 供应商资料请求草稿", "可直接复制发送的补充资料请求函"),
           ("11 风险与处置", "事实—后果—处置，逐条对应"),
           ("12 人工核验事项", "无法自动化的现场/电话核验清单"),
           ("13 证据登记", "E01…En 来源、发布机构、日期、URL、支撑内容"),
           ("14 附录·数据字典", "字段含义、状态口径、更新维护约定")]
    for k, v in nav:
        c = ws.cell(row=r, column=1, value=k)
        c.font = F(True, 9.5, DEEP)
        c.fill = fill(CREAM)
        c.border = BOX
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=ncols)
        c2 = ws.cell(row=r, column=2, value=v)
        c2.font = F(False, 9.5)
        c2.border = BOX
        r += 1
    ws.sheet_view.showGridLines = False


def sh_subject(wb, d):
    ws = wb.create_sheet("01 主体识别")
    ws.sheet_properties.tabColor = DEEP2
    s = d.get("subject") or {}
    chk = L.check_uscc(s.get("uscc"))
    title_block(ws, "01 供应商主体识别", "先锁定唯一法人，再谈证照归属；同名不同主体是高频差错源", 3,
                "基准日 %s" % d.get("as_of"))
    header_row(ws, 4, ["项目", "内容", "核验说明 / 来源"], [18, 46, 62])
    rows = [
        ("企业全称", s.get("name", ""), "必须与营业执照逐字一致，含括号全/半角"),
        ("曾用名/简称", "、".join(s.get("aliases") or []), "曾用名证照在更名前签发属正常，但须核对变更记录"),
        ("统一社会信用代码", s.get("uscc", ""),
         "GB 32100-2015 第18位校验：%s ｜ %s" % ("通过" if chk["valid"] else "不通过" if chk["valid"] is False else "未提供", chk["reason"])),
        ("营业执照注册号", s.get("biz_lic_no", ""), L.check_biz_lic_no(s.get("biz_lic_no"))["reason"]),
        ("法定代表人", s.get("legal_rep", ""), "与证照签章人是否同一人"),
        ("注册资本", s.get("capital", ""), ""),
        ("成立日期", s.get("founded", ""), ""),
        ("企业类型", s.get("types", ""), ""),
        ("登记状态", s.get("credit_status", ""), "存续/在业/注销/吊销"),
        ("注册地址", s.get("reg_addr", ""), "与证照住所一致"),
        ("生产/经营地址", s.get("site_addr", ""), "许可作业场所，需与许可证上的地址一致"),
        ("经营范围（登记）", s.get("business_scope", ""), "许可项目与登记范围是两件事，不可互相替代"),
        ("注册信息来源", s.get("uscc_source", ""), ""),
        ("企业关系链", s.get("chain", ""), "控股/参股关系影响责任主体与承诺有效性"),
        ("身份核验要点", s.get("id_note", ""), ""),
    ]
    r = 5
    for k, v, note in rows:
        if not v and not note:
            continue
        st = None
        if k == "统一社会信用代码":
            st = [None, (OK_BG, OK_FG) if chk["valid"] else (BAD_BG, BAD_FG), None]
        body_row(ws, r, [k, v, note], styles=st, wraps=[False, True, True])
        r += 1
    if s.get("scope_note"):
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        c = ws.cell(row=r, column=1, value="⚠ " + s["scope_note"])
        c.font = F(False, 9.5, WARN_FG)
        c.fill = fill(WARN_BG)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.border = BOX
        ws.row_dimensions[r].height = 46
    ws.freeze_panes = "A5"
    ws.sheet_view.showGridLines = False


def sh_product(wb, d):
    ws = wb.create_sheet("02 产品监管识别")
    ws.sheet_properties.tabColor = DEEP2
    p = d.get("product") or {}
    ncols = 5
    title_block(ws, "02 产品身份与监管属性识别", "CAS + 浓度 + 剂型 + 用途四要素同时锁定，再对照目录条目逐项判定", ncols,
                "基准日 %s" % d.get("as_of"))
    r = 4
    ws.cell(row=r, column=1, value="2.1 物料档案（采购标的口径）").font = F(True, 11, DEEP)
    r += 1
    header_row(ws, r, ["项目", "内容", "采购落库说明", "", ""], [16, 40, 60, 2, 2])
    r += 1
    prof = [("物料名称", p.get("name"), ""), ("商品名/别名", "、".join(p.get("aliases") or []), ""),
            ("CAS 登记号", p.get("cas"), "合同、送货单、SDS 三处必须一致"),
            ("拟采购规格/浓度", p.get("spec"), "浓度决定目录条目（如含量阈值）与危险类别"),
            ("剂型/形态", p.get("form"), "水溶液/稳定剂体系影响目录条目的适用条件"),
            ("工业标准/等级", p.get("grade_std"), ""), ("包装与运输方式", p.get("packing"), ""),
            ("年用量/本次批量", p.get("qty"), "与储存量、是否构成重大危险源、流向登记相关"),
            ("采购用途/工艺", p.get("usage"), "用途决定是否需使用许可或公安备案"),
            ("使用地点/储存条件", p.get("site"), ""), ("SDS 版本", p.get("sds"), "SDS 版本号与日期必须写进档案")]
    for k, v, n in prof:
        if not v:
            continue
        body_row(ws, r, [k, v, n], wraps=[False, True, True])
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="2.2 危险属性识别（危险化学品 / 特殊管理类别）").font = F(True, 11, DEEP)
    r += 1
    header_row(ws, r, ["识别项", "本产品结论", "判定", "依据（文号/条款/标准）", "适用条件与例外"], [16, 34, 12, 46, 46])
    r += 1
    for f in p.get("findings", []):
        lbl = f.get("verdict_label") or L.class_meta(f.get("verdict"))["label"]
        body_row(ws, r, [f.get("item"), f.get("value"), lbl, f.get("basis"), f.get("condition")],
                 aligns=["left", "left", "center", "left", "left"], styles=[None, None, verdict_style(f.get("verdict")), None, None])
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="2.3 监管分类核验清单（未确认一项，不得下「不属于」结论）").font = F(True, 11, DEEP)
    r += 1
    header_row(ws, r, ["编号", "监管制度/目录", "判定", "", "本产品核对说明"], [8, 34, 12, 2, 70])
    r += 1
    for c in d.get("classification_checklist", []):
        body_row(ws, r, [c.get("id"), c.get("item"), L.class_meta(c.get("verdict"))["label"], "",
                         c.get("note")],
                 aligns=["center", "left", "center", "left", "left"], styles=[None, None, verdict_style(c.get("verdict")), None, None])
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=5)
        r += 1
    if p.get("gaps"):
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        c = ws.cell(row=r, column=1, value="资料缺口：" + "；".join(p["gaps"]))
        c.font = F(False, 9.5, WARN_FG)
        c.fill = fill(WARN_BG)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.border = BOX
        ws.row_dimensions[r].height = 40
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"


def sh_classcheck(wb, d):
    ws = wb.create_sheet("03 监管分类核验单")
    ws.sheet_properties.tabColor = DEEP2
    ncols = 7
    title_block(ws, "03 监管分类核验单（逐项打勾）", "本页即「查什么、依据什么、结论是什么」的可审计轨迹；判定列可下拉选择", ncols,
                "基准日 %s" % d.get("as_of"))
    header_row(ws, 4, ["编号", "监管制度 / 目录", "适用文号或条款", "本产品对照要点", "判定", "未确认时的影响", "复核人/日期"],
               [7, 22, 30, 62, 14, 34, 14])
    check_list = d.get("classification_checklist", [])
    detail = {
        c.get("id"): c.get("note") for c in check_list
    }
    basis_map = {c.get("id"): c.get("basis", "") for c in check_list}
    r = 5
    for c in check_list:
        body_row(ws, r, [c.get("id"), c.get("item"), c.get("basis", ""), c.get("note"), L.class_meta(c.get("verdict"))["label"],
                         c.get("impact", ""), ""],
                 aligns=["center", "left", "left", "left", "center", "left", "center"],
                 styles=[None, None, None, None, verdict_style(c.get("verdict")), None, None])
        r += 1
    dv = DataValidation(type="list", formula1='"已确认,未确认（不等于不属于）,待核验"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("E5:E%d" % (r + 80))
    ws.freeze_panes = "A5"
    ws.sheet_view.showGridLines = False


def sh_supplier(wb, d):
    ws = wb.create_sheet("04 供应商许可要求")
    ws.sheet_properties.tabColor = DEEP2
    ncols = 5
    title_block(ws, "04 供应商侧：生产 / 经营 / 储存许可要求", "许可跟着「活动」走：有无储存设施决定「带储存」还是「不带储存」", ncols,
                "基准日 %s" % d.get("as_of"))
    if d.get("supplier_lead"):
        ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=ncols)
        c = ws.cell(row=4, column=1, value=d["supplier_lead"])
        c.font = F(False, 9.5, DEEP2)
        c.fill = fill(CREAM)
        c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
        c.border = BOX
        ws.row_dimensions[4].height = 44
    header_row(ws, 5, ["供应商角色", "应取得的许可/证照", "是否必需", "法规依据与适用条件", "核验要点（范围是否覆盖拟购品）"],
               [18, 26, 12, 56, 52])
    r = 6
    for x in d.get("supplier_requirements", []):
        st = [None, None, (BAD_BG, BAD_FG) if x.get("required") == "必须" else (WARN_BG, WARN_FG), None, None]
        body_row(ws, r, [x.get("role"), x.get("licence"), x.get("required"), x.get("basis"), x.get("scope_check")],
                 aligns=["left", "left", "center", "left", "left"], styles=st)
        r += 1
    if d.get("supplier_notes"):
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        c = ws.cell(row=r, column=1, value="补充：" + "；".join(d["supplier_notes"]))
        c.font = F(False, 9.5)
        c.fill = fill(CREAM)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.border = BOX
        ws.row_dimensions[r].height = 44
    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


def sh_buyer(wb, d):
    ws = wb.create_sheet("05 采购方义务")
    ws.sheet_properties.tabColor = DEEP2
    erp = d.get("erp") or {}
    ncols = 5
    title_block(ws, "05 采购方（使用企业）义务", "买易制爆品不是「买东西」，而是「建立一条可追溯的合法用途链」", ncols,
                "基准日 %s" % d.get("as_of"))
    chk = L.check_uscc(erp.get("uscc"))
    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=ncols)
    c = ws.cell(row=4, column=1, value="我方主体：%s ｜ 统一社会信用代码：%s（%s） ｜ 用途：%s ｜ 储存现状：%s" % (
        erp.get("name", ""), erp.get("uscc", ""), chk["reason"], erp.get("usage", ""), erp.get("storage", "")))
    c.font = F(False, 9.5, DEEP2)
    c.fill = fill(CREAM)
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    c.border = BOX
    ws.row_dimensions[4].height = 34
    header_row(ws, 5, ["我方义务项", "性质", "法规依据", "触发条件", "落地动作 / 证据"], [22, 10, 46, 30, 54])
    r = 6
    for x in erp.get("obligations", []):
        toned = (BAD_BG, BAD_FG) if x.get("status") == "必须" else (WARN_BG, WARN_FG) if x.get("status") == "视情形" else (GRAY_BG, GRAY_FG)
        body_row(ws, r, [x.get("item"), x.get("status"), x.get("basis"), x.get("trigger"), x.get("action")],
                 aligns=["left", "center", "left", "left", "left"], styles=[None, toned, None, None, None])
        r += 1
    if erp.get("notes"):
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        c = ws.cell(row=r, column=1, value="提示：" + "；".join(erp["notes"]))
        c.font = F(False, 9.5, WARN_FG)
        c.fill = fill(WARN_BG)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.border = BOX
        ws.row_dimensions[r].height = 44
    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


def sh_certs(wb, d):
    ws = wb.create_sheet("06 证照台账")
    ws.sheet_properties.tabColor = BRASS
    certs = d.get("certs", [])
    ncols = 17
    title_block(ws, "06 证照台账（核心表）", "四态：已核验 / 信息不一致 / 待核验 / 无公开信息；过期单独标记。「状态」「范围覆盖」列可下拉维护", ncols,
                "基准日 %s" % d.get("as_of"))
    cols = ["证照编号", "证照类型", "证书编号", "发证机关", "发证/起始日期", "有效期至", "有效期判定(此单由公式自动计算)",
            "核验状态", "应否具备", "许可/核准范围（证载原文）", "范围是否覆盖本采购", "字段来源", "公开状态",
            "公开链接", "交叉核验记录", "核验说明与缺口"]
    widths = [9, 22, 26, 20, 13, 13, 18, 12, 10, 52, 12, 22, 16, 34, 40, 46]
    header_row(ws, 4, cols, widths)
    r = 5
    for c in certs:
        st = state_style(c["state"])
        cv = cover_style(c["cover_key"])
        body_row(ws, r, [c["id"], c.get("name"), c.get("no") or None, c.get("issuer"), c.get("valid_from") or c.get("issue_date"),
                         c.get("valid_to"), None, c["state_label"], c["need_label"], c.get("scope"),
                         c["cover_label"], c.get("field_source"), c.get("public_state"), c.get("url"),
                         "；".join(c.get("crosscheck") or []) if isinstance(c.get("crosscheck"), list) else "",
                         c.get("note")],
                 aligns=["center", "left", "left", "left", "center", "center", "center", "center", "center", "left",
                         "center", "left", "center", "left", "left", "left"],
                 styles=[None, None, None, None, None, None, None, st, None, None, cv, None, None, None, None, None])
        # 有效期判定公式：相对 as_of 单元格
        ws.cell(row=r, column=7, value='=IF(OR($F%d="",$F%d="长期"),IF($F%d="","有效期未取得","长期有效"),'
                                       'IF($F%d<TEXT(基准日,"yyyy-mm-dd"),"已过期 "&TEXT(基准日-$F%d,"0")&" 天",'
                                       '"有效 余"&TEXT($F%d-基准日,"0")&"天"))' % (r, r, r, r, r, r))
        ws.cell(row=r, column=7).font = F(False, 9.5)
        ws.cell(row=r, column=7).alignment = Alignment(horizontal="center", wrap_text=True)
        ws.cell(row=r, column=7).border = BOX
        ws.cell(row=r, column=14).font = Font(name="微软雅黑", size=8.5, color="1B4239", underline="single")
        if c.get("url"):
            ws.cell(row=r, column=14).hyperlink = c["url"]
        r += 1
    last = r - 1
    dv1 = DataValidation(type="list", formula1='"已核验,信息不一致,待核验,无公开信息,已过期"', allow_blank=True)
    dv2 = DataValidation(type="list", formula1='"覆盖,部分覆盖,未覆盖,无法判断"', allow_blank=True)
    dv3 = DataValidation(type="list", formula1='"应具备,备选/按需,不适用"', allow_blank=True)
    for dv, rng in ((dv1, "H"), (dv2, "K"), (dv3, "I")):
        ws.add_data_validation(dv)
        dv.add("%s5:%s80" % (rng, rng))
    # 汇总（公式，改状态即自动重算）
    r += 1
    ws.cell(row=r, column=1, value="汇总(公式)").font = F(True, 10, DEEP)
    items = [("总数", '=COUNTA($H$5:$H$%d)' % last),
             ("已核验", '=COUNTIF($H$5:$H$%d,"已核验")' % last),
             ("信息不一致", '=COUNTIF($H$5:$H$%d,"信息不一致")' % last),
             ("待核验", '=COUNTIF($H$5:$H$%d,"待核验")' % last),
             ("无公开信息", '=COUNTIF($H$5:$H$%d,"无公开信息")' % last),
             ("已过期", '=COUNTIF($H$5:$H$%d,"已过期")' % last),
             ("180天内到期", '=COUNTIF($G$5:$G$%d,"有效 余*")' % last)]
    col = 2
    for k, f in items:
        c = ws.cell(row=r, column=col, value=f)
        c.font = F(True, 9.5)
        c.fill = fill(CREAM)
        c.border = BOX
        c.alignment = Alignment(horizontal="center")
        col += 1
    ws.cell(row=r + 1, column=1, value="口径").font = F(False, 8.5, GRAY_FG)
    ws.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=14)
    c = ws.cell(row=r + 1, column=2, value="「180天内到期」按 G 列判定文本统计（含「有效 余180天」及以下），仅作预警提示，不改变核验状态；证书编号留空表示尚未取得，不得填写推测值。")
    c.font = F(False, 8.5, GRAY_FG)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = "A4:P%d" % last
    ws.sheet_view.showGridLines = False


def sh_validity(wb, d):
    ws = wb.create_sheet("07 有效期与范围比对")
    ws.sheet_properties.tabColor = BRASS
    ncols = 10
    title_block(ws, "07 有效期与许可范围比对（逐单核对）", "只剩天数用公式算；「是否覆盖本采购」「主体是否一致」必须逐项用证据回答，不得推定", ncols,
                "基准日 %s" % d.get("as_of"))
    header_row(ws, 4, ["证照编号", "证照类型", "有效期至", "剩余天数(公式)", "到期风险(公式)", "是否覆盖拟购产品/浓度", "覆盖判定",
                       "主体名称是否一致", "业务活动是否一致", "比对依据与备注"],
               [9, 22, 13, 12, 14, 30, 12, 16, 26, 56])
    r = 5
    for c in d.get("certs", []):
        covs = c.get("coverage", "")
        body_row(ws, r, [c["id"], c.get("name"), c.get("valid_to"),
                         '=IF(OR($C{r}="",$C{r}="长期"),"",$C{r}-基准日)'.replace("{r}", str(r)),
                         '=IF($D{r}="","—",IF($D{r}<0,"已过期",IF($D{r}<=180,"临期","有效")))'.replace("{r}", str(r)),
                         covs, c["cover_label"], c.get("subject_match", "待核验"), c.get("activity_match", "待核验"), c.get("coverage_note", c.get("note", ""))],
                 aligns=["center", "left", "center", "center", "center", "left", "center", "center", "center", "left"],
                 styles=[None, None, None, None, None, None, cover_style(c["cover_key"]), None, None, None])
        r += 1
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:J%d" % (r - 1)
    ws.sheet_view.showGridLines = False


def sh_cross(wb, d):
    ws = wb.create_sheet("08 交叉核验记录")
    ws.sheet_properties.tabColor = BRASS
    ncols = 5
    title_block(ws, "08 交叉核验记录（证照 × 主管部门公示 × 工商身份）", "三方对不上就是「信息不一致」；仅一方可得只能写「待核验」", ncols,
                "基准日 %s" % d.get("as_of"))
    if d.get("crosscheck_lead"):
        ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=ncols)
        c = ws.cell(row=4, column=1, value=d["crosscheck_lead"])
        c.font = F(False, 9.5, DEEP2)
        c.fill = fill(CREAM)
        c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
        c.border = BOX
        ws.row_dimensions[4].height = 34
    header_row(ws, 5, ["比对项", "证照/供应商材料（A）", "公开来源/主管部门记录（B）", "结论", "处理意见"],
               [18, 42, 42, 10, 52])
    r = 6
    for x in d.get("crosscheck", []):
        tone = (OK_BG, OK_FG) if x.get("result") == "一致" else (BAD_BG, BAD_FG) if x.get("result") == "不一致" else (WARN_BG, WARN_FG)
        body_row(ws, r, [x.get("item"), x.get("left"), x.get("right"), x.get("result"), x.get("note")],
                 aligns=["left", "left", "left", "center", "left"], styles=[None, None, None, tone, None])
        r += 1
    if d.get("crosscheck_notes"):
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        c = ws.cell(row=r, column=1, value="说明：" + "；".join(d["crosscheck_notes"]))
        c.font = F(False, 9.5, WARN_FG)
        c.fill = fill(WARN_BG)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.border = BOX
        ws.row_dimensions[r].height = 44
    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


def sh_request(wb, d):
    ws = wb.create_sheet("09 索证清单")
    ws.sheet_properties.tabColor = BAD_FG
    ncols = 9
    title_block(ws, "09 索证清单（Material To Request）", "按优先级取证；查不到即入清单，绝不写「已确认无证」。勾选列用于跟踪进度", ncols,
                "基准日 %s" % d.get("as_of"))
    header_row(ws, 4, ["编号", "优先级", "必须索取的证照/资料", "出具机关/说明", "为什么必须索取（本单的具体理由）", "需确认的问题", "来源",
                       "已取得?", "备注"],
               [7, 8, 24, 24, 52, 46, 10, 9, 26])
    items = list(d.get("request_list", []))
    auto, notices = L.pending_derivation(d)
    have = set((i.get("cert") or "").strip() for i in items)
    for a in auto:
        if (a.get("cert") or "").strip() not in have:
            items.append(a)
    items.sort(key=lambda x: (L.PRIORITIES.index(x.get("priority", "P1")) if x.get("priority", "P1") in L.PRIORITIES else 2,
                              x.get("auto") is True, x.get("code", "")))
    r = 5
    for it in items:
        p = it.get("priority", "P1")
        tone = (BAD_BG, BAD_FG) if p == "P0" else (WARN_BG, WARN_FG) if p == "P1" else (GRAY_BG, GRAY_FG)
        body_row(ws, r, [it.get("code"), p, it.get("cert"), it.get("issuer"), it.get("reason"), it.get("ask"),
                         "自动派生" if it.get("auto") else "人工补充", "", ""],
                 aligns=["center", "center", "left", "left", "left", "left", "center", "center", "left"],
                 styles=[None, tone, None, None, None, None, None, None, None])
        r += 1
    dv = DataValidation(type="list", formula1='"是,否,部分"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("H5:H120")
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
    c = ws.cell(row=r, column=1, value="说明：" + "；".join(notices))
    c.font = F(False, 9, GRAY_FG)
    c.fill = fill(GRAY_BG)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    c.border = BOX
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:I%d" % (r - 2)
    ws.sheet_view.showGridLines = False


def sh_draft(wb, d):
    ws = wb.create_sheet("10 供应商资料请求草稿")
    ws.sheet_properties.tabColor = BAD_FG
    dr = d.get("draft") or {}
    ncols = 3
    title_block(ws, "10 发送给供应商的补充资料请求（草稿）", "把索证清单转成对方能直接回复的邮件/公函；发送前替换占位符", ncols,
                "基准日 %s" % d.get("as_of"))
    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=ncols)
    c = ws.cell(row=4, column=1, value=dr.get("intro", ""))
    c.font = F(False, 9.5, DEEP2)
    c.fill = fill(CREAM)
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    c.border = BOX
    ws.row_dimensions[4].height = 34
    ws.merge_cells(start_row=5, start_column=1, end_row=5 + max(6, dr.get("body", "").count("\n") + 4), end_column=ncols)
    c = ws.cell(row=5, column=1, value=dr.get("body", ""))
    c.font = F(False, 10)
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    c.border = BOX
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 40
    ws.sheet_view.showGridLines = False


def sh_risks(wb, d):
    ws = wb.create_sheet("11 风险与处置")
    ws.sheet_properties.tabColor = BAD_FG
    ncols = 6
    title_block(ws, "11 风险与处置", "按「事实—后果—处置」写；每条必须有具体事实与对应动作", ncols, "基准日 %s" % d.get("as_of"))
    header_row(ws, 4, ["#", "风险等级", "风险点", "事实（已查到）", "可能后果", "处置动作 / 责任"], [5, 9, 26, 52, 44, 48])
    r = 5
    for i, x in enumerate(d.get("risks", []), 1):
        tone = (BAD_BG, BAD_FG) if x.get("level") == "高" else (WARN_BG, WARN_FG) if x.get("level") == "中" else (GRAY_BG, GRAY_FG)
        body_row(ws, r, [i, x.get("level"), x.get("title"), x.get("fact"), x.get("impact"), x.get("action")],
                 aligns=["center", "center", "left", "left", "left", "left"], styles=[None, tone, None, None, None, None])
        r += 1
    ws.freeze_panes = "A5"
    ws.sheet_view.showGridLines = False


def sh_manual(wb, d):
    ws = wb.create_sheet("12 人工核验事项")
    ws.sheet_properties.tabColor = WARN_FG
    ncols = 7
    title_block(ws, "12 仍需人工核验的事项（无法自动化）", "公开检索与 OCR 都做不到的事，必须写清「怎么核、谁去核、何时核完」", ncols,
                "基准日 %s" % d.get("as_of"))
    header_row(ws, 4, ["#", "事项", "为什么必须人工", "核实方法", "需要的证据", "责任人", "完成日期"],
               [5, 26, 44, 52, 34, 12, 12])
    r = 5
    for i, x in enumerate(d.get("manual_check", []), 1):
        body_row(ws, r, [i, x.get("item"), x.get("why"), x.get("method"), x.get("evidence", ""), x.get("owner", ""), ""],
                 aligns=["center", "left", "left", "left", "left", "center", "center"])
        r += 1
    ws.freeze_panes = "A5"
    ws.sheet_view.showGridLines = False


def sh_evidence(wb, d):
    ws = wb.create_sheet("13 证据登记")
    ws.sheet_properties.tabColor = "6B7A72"
    ncols = 7
    title_block(ws, "13 证据登记（E01…En）", "每条结论均可回溯到具体文号/条款/页面；没有登记的来源不算证据", ncols,
                "基准日 %s" % d.get("as_of"))
    header_row(ws, 4, ["证据ID", "类型", "文件/页面标题", "发布机构", "日期", "URL", "支撑了什么（具体到条款/字段）"],
               [8, 14, 46, 26, 12, 52, 60])
    r = 5
    for e in d.get("evidence", []):
        body_row(ws, r, [e.get("id"), e.get("kind"), e.get("title"), e.get("publisher"), e.get("date"), e.get("url"), e.get("supports")],
                 aligns=["center", "left", "left", "left", "center", "left", "left"])
        if e.get("url"):
            ws.cell(row=r, column=6).hyperlink = e["url"]
            ws.cell(row=r, column=6).font = Font(name="微软雅黑", size=8.5, color="1B4239", underline="single")
        r += 1
    ws.freeze_panes = "A5"
    ws.sheet_view.showGridLines = False


def sh_dict(wb, d):
    ws = wb.create_sheet("14 附录·数据字典")
    ws.sheet_properties.tabColor = "6B7A72"
    ncols = 3
    title_block(ws, "14 附录：字段字典与维护约定", "换日期、换产品、换供应商都只改数据，不改结构", ncols, "版本 %s" % LAST_UPDATED)
    header_row(ws, 4, ["字段/概念", "取值", "含义与写法规矩"], [26, 40, 76])
    rows = [
        ("as_of（基准日）", "YYYY-MM-DD", "全表唯一时间基准；所有「剩余天数/是否过期」相对它计算"),
        ("cert.status", "verified", "已核验：证载字段被一手/官方公开来源直接支撑"),
        ("", "mismatch", "信息不一致：字段冲突、过期、主体不符或范围不匹配"),
        ("", "pending", "待核验：仅凭供应商提供，尚无公开来源可比对"),
        ("", "no_public", "无公开信息：定向检索未发现公开记录，不得推断为无证"),
        ("", "expired", "由 valid_to 与 as_of 自动推导（有效期早于基准日）"),
        ("cert.cover", "cover/partial/not_cover/unknown", "许可范围是否覆盖拟采购产品与浓度；unknown 必须写原因"),
        ("cert.need", "required/conditional/none", "本单中该证照是否应由供应商具备"),
        ("finding.verdict", "confirmed", "已确认：目录条目阈值可逐字对上"),
        ("", "not_confirmed", "未确认（不等于不属于）：资料不足，须补证"),
        ("", "pending", "待核验：需供应商材料或主管部门确认"),
        ("优先级", "P0/P1/P2", "P0 未取得不得下单；P1 卡合同/首批发货；P2 档案完善"),
        ("scan mode", "mock", "模拟演示件，必须显式标注，严禁当作真实证照"),
        ("scan mode", "upload", "真实上传件，OCR 字段须与公开记录逐字段比对"),
        ("主体一致性", "—", "证照上的名称/地址/代码必须与当前工商登记一致；更名须附变更记录"),
        ("维护周期", "每季度/换证后", "证照到期前 180 天预警；变更后 5 个工作日内更新台账"),
    ]
    r = 5
    for k, v, n in rows:
        body_row(ws, r, [k, v, n], aligns=["left", "left", "left"])
        r += 1
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------- 主流程

def hydrate(data):
    """与 render_html.prepare 对齐：给每张证照派生 state / cover_key 等展示字段。"""
    as_of = data.get("as_of")
    for i, c in enumerate(data.get("certs", [])):
        c.setdefault("id", "C%02d" % (i + 1))
        st = L.cert_effective_state(c, as_of)
        c["state"] = st
        c["state_label"] = L.state_meta(st)["label"]
        v = L.validity(c.get("valid_to"), as_of)
        c["expiry_status"] = v["status"]
        c["expiry_label"] = v["label"]
        cv = c.get("cover") or "unknown"
        c["cover_key"] = cv
        c["cover_label"] = L.cover_meta(cv)["label"]
        c["need_label"] = "应具备" if c.get("need") == "required" else (
            "备选/按需" if c.get("need") == "conditional" else "不适用")
    return data


def build(data, out_path):
    if Workbook is None:
        raise SystemExit("需要 openpyxl：pip install openpyxl")
    data = hydrate(data)
    as_of = L.parse_date(data.get("as_of")) or date.today()
    wb = Workbook()
    wb.properties.creator = "chem-supplier-qualification skill"
    wb.properties.title = "证照与监管要求核验台账"
    wb.properties.subject = "%s / %s" % ((data.get("subject") or {}).get("name", ""),
                                         (data.get("product") or {}).get("name", ""))
    sh_cover(wb, data)
    sh_subject(wb, data)
    sh_product(wb, data)
    sh_classcheck(wb, data)
    sh_supplier(wb, data)
    sh_buyer(wb, data)
    sh_certs(wb, data)
    sh_validity(wb, data)
    sh_cross(wb, data)
    sh_request(wb, data)
    sh_draft(wb, data)
    sh_risks(wb, data)
    sh_manual(wb, data)
    sh_evidence(wb, data)
    sh_dict(wb, data)
    # 命名区域：基准日（供 06/07 页公式引用）
    from openpyxl.workbook.defined_name import DefinedName
    dn = DefinedName("基准日", attr_text="'00 封面与说明'!$B$5")
    try:
        wb.defined_names["基准日"] = dn
    except Exception:
        pass
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    wb.save(out_path)
    return out_path


def safe_name(s):
    for ch in '\\/:*?"<>|\n\r\t':
        s = s.replace(ch, "")
    return s.strip()[:60] or "report"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default="out")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    with open(a.data, encoding="utf-8") as f:
        data = json.load(f)
    subj = (data.get("subject") or {}).get("name", "主体")
    prod = (data.get("product") or {}).get("name", "产品")
    fn = a.name or ("证照与监管要求核验台账_%s_%s.xlsx" % (safe_name(subj), safe_name(prod)))
    path = build(data, os.path.join(a.out, fn))
    print("XLSX -> %s (%.1f KB)" % (path, os.path.getsize(path) / 1024.0))


if __name__ == "__main__":
    main()
