# -*- coding: utf-8 -*-
"""render_xlsx.py — data.json → 供应商评估工作簿（多表、可编辑、留白可复算）。

    python scripts/render_xlsx.py data.json out.xlsx

工作表：00 说明 / 01 采购需求 / 02 横向比较 / 03 厂家身份 / 04 产能与生产 /
        05 资质许可 / 06 报价对比 / 07 风险与事件 / 08 自定义维度 /
        09 问询清单 / 10 证据索引 / 11 评分留白（不做结论）/ 12 字段说明
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmplib as L  # noqa: E402

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

INK = "1F2D36"
BRAND = "0F3B4C"
BRASS = "97702F"
PAPER = "F7F5EF"
LINE = "D9D3C6"
WHITE = "FFFFFF"
ZEBRA = "FBFAF6"

LBL_FILL = {"V": "E7F4ED", "S": "FBF1E1", "M": "E9F0F7", "U": "EEF0F1", "X": "FBEAE9"}
LBL_FONT = {"V": "1B6A49", "S": "9C5F13", "M": "2A5A86", "U": "4A5157", "X": "9C2A2A"}
ST_FILL = {"confirmed": "E7F4ED", "quoted": "E9F0F7", "pending": "FBF1E1", "missing": "EEF0F1", "risk": "FBEAE9"}

thin = Side(style="thin", color=LINE)
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def title_block(ws, text, sub, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(ncols, 4))
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(name="微软雅黑", size=15, bold=True, color=WHITE)
    c.fill = PatternFill("solid", fgColor=BRAND)
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(ncols, 4))
    c = ws.cell(row=2, column=1, value=sub)
    c.font = Font(name="微软雅黑", size=9.5, color="5A6670")
    c.fill = PatternFill("solid", fgColor=PAPER)
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 22


def header_row(ws, row, headers, widths=None, height=30):
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(name="微软雅黑", size=10, bold=True, color=WHITE)
        c.fill = PatternFill("solid", fgColor="17495C")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[row].height = height
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def body(ws, row, values, zebra=False, bold_first=False, wrap=True, height=None):
    for i, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(name="微软雅黑", size=9.5, bold=(bold_first and i == 1), color=INK)
        c.alignment = Alignment(vertical="top", wrap_text=wrap)
        c.border = BORDER
        if zebra:
            c.fill = PatternFill("solid", fgColor=ZEBRA)
    if height:
        ws.row_dimensions[row].height = height


def label_chip(ws, row, col, label):
    c = ws.cell(row=row, column=col)
    c.value = L.LABELS.get(label, {}).get("cn", label)
    c.font = Font(name="微软雅黑", size=9, bold=True, color=LBL_FONT.get(label, INK))
    c.fill = PatternFill("solid", fgColor=LBL_FILL.get(label, WHITE))
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = BORDER


def plain(html):
    import re
    return re.sub(r"<[^>]+>", "", str(html or "")).strip()


def approx_height(text, width_chars=40, line_h=14):
    t = plain(text)
    lines = max(1, int(len(t) / max(width_chars, 8)) + 1 + t.count("\n"))
    return min(409, 15 + lines * line_h)


def eids(raw):
    import re
    return sorted(set(x.upper() for x in re.findall(r"[Ee]\d+", str(raw or ""))), key=lambda s: int(s[1:]))


def build(data, out):
    c = L.Cmp(data)
    m = c.meta
    sups = c.suppliers
    S2 = {s["id"]: s for s in sups}
    wb = Workbook()
    wb.remove(wb.active)
    sid_lbl = {s["id"]: s.get("short", s["id"]) for s in sups}

    def S(title):
        return wb.create_sheet(title)

    # ---------- 00 说明 ----------
    ws = S("00 说明")
    title_block(ws, "%s · %s" % (m.get("title", ""), m.get("product", "")),
                "文档编号 %s｜数据截止 %s｜版本 %s｜本工作簿由 chem-supplier-compare 生成，可编辑复算" %
                (m.get("doc_no", ""), m.get("as_of", ""), m.get("version", "")), 6)
    rows = [
        ("比较对象", " · ".join("%s（%s）" % (s.get("name"), s.get("code")) for s in sups)),
        ("采购标的", c.req.get("product", "")),
        ("执行标准 / 规格", c.req.get("spec", "")),
        ("数量", "%s；备选 %s" % (c.req.get("qty", ""), c.req.get("qty_alt", "—"))),
        ("收货地", c.req.get("destination", "")),
        ("交付偏好", c.req.get("delivery_pref", "")),
        ("结算偏好", "%s；%s" % (c.req.get("payment_pref", ""), c.req.get("tax_pref", ""))),
        ("维度数量", "%d 个（其中自定义 %d 个）" % (len(c.dims), sum(1 for d in c.dims if d.get("type") == "custom"))),
        ("证据数量", "%d 条" % len(c.ev)),
        ("报价状态", c.quotes.get("status_note") or "未收到报价"),
    ]
    r = 4
    for k, v in rows:
        ws.cell(row=r, column=1, value=k).font = Font(name="微软雅黑", size=10, bold=True, color=BRAND)
        ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=PAPER)
        ws.cell(row=r, column=1).border = BORDER
        ws.cell(row=r, column=1).alignment = Alignment(vertical="top")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        cc = ws.cell(row=r, column=2, value=v)
        cc.font = Font(name="微软雅黑", size=10, color=INK)
        cc.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = approx_height(v, 90)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="证据标签与判定规则").font = Font(name="微软雅黑", size=11, bold=True, color=BRASS)
    r += 1
    header_row(ws, r, ["标签", "含义", "在本工作簿中的用法", "", "", ""], [16, 30, 56, 14, 14, 14], height=24)
    r += 1
    usage = {
        "V": "一手文件（定期报告、政府公示、法院文书、证照副本）可直接引用",
        "S": "企业自述/宣传口径，只能作为线索，须索取证明文件",
        "M": "媒体或第三方转载，需回溯原始公告或政府文件",
        "U": "截止数据日公开渠道未取得，不代表不存在，必须转为问询",
        "X": "已发生的负面事实（处罚、诉讼、事故），可直接用于风险评估",
    }
    for lb in L.LABEL_ORDER:
        info = L.LABELS[lb]
        label_chip(ws, r, 1, lb)
        c2 = ws.cell(row=r, column=2, value=info["cn"] + "（" + info["desc"] + "）")
        c2.font = Font(name="微软雅黑", size=9.5, color=INK)
        c2.alignment = Alignment(vertical="top", wrap_text=True)
        c2.border = BORDER
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
        c3 = ws.cell(row=r, column=3, value=usage[lb])
        c3.font = Font(name="微软雅黑", size=9.5, color=INK)
        c3.alignment = Alignment(vertical="top", wrap_text=True)
        for cc in range(3, 7):
            ws.cell(row=r, column=cc).border = BORDER
        ws.row_dimensions[r].height = 34
        r += 1
    r += 1
    for line in [
        "本工作簿不做综合评分、不给出“最佳供应商”结论；11 表为留白评估表，权重与分数由采购方填写。",
        "“经营范围包含该产品”不等于具备该产品的实际生产能力，04 表以设计产能×利用率=产量能否自洽为核验标准。",
        "“无重大诉讼”“未发现处罚”均为披露或检索口径，不代表事实上的零风险。",
        "商业条款未取得报价的一律标注“待确认”，不填估算值。",
        m.get("use_note", ""),
    ]:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        cc = ws.cell(row=r, column=1, value="· " + line)
        cc.font = Font(name="微软雅黑", size=9, color="8A949B")
        cc.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = approx_height(line, 100)
        r += 1
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"

    # ---------- 01 采购需求 ----------
    ws = S("01 采购需求")
    title_block(ws, "01 采购需求（本次比较的统一标尺）", "所有候选企业按同一份需求口径被比较；需求变化需重做比较", 4)
    header_row(ws, 4, ["项目", "内容", "说明 / 影响", ""], [20, 52, 44, 12])
    req_rows = [
        ("采购标的", c.req.get("product", ""), "决定适用标准与工艺路线匹配度"),
        ("执行标准 / 规格", c.req.get("spec", ""), "三家证书上写着“工业碳酸钠”，但等级与粒径需逐项对上"),
        ("年需求量", c.req.get("qty", ""), "决定供应商能否给到长约价与稳定排产"),
        ("备选口径", c.req.get("qty_alt", ""), "小批量试单常用于首单验证"),
        ("收货地", c.req.get("destination", ""), "运费、损耗与水运/铁运可行性均由收货地决定"),
        ("交付偏好", c.req.get("delivery_pref", ""), "散装罐车 vs 吨袋，直接影响包装费与卸货条件"),
        ("结算偏好", "%s；%s" % (c.req.get("payment_pref", ""), c.req.get("tax_pref", "")), "账期与票据类型是价格谈判的对价"),
        ("数据截止日", m.get("as_of", ""), "所有时效性判断（许可到期、负面事件）以此为基准"),
    ]
    r = 5
    for i, (k, v, note) in enumerate(req_rows):
        body(ws, r, [k, plain(v), plain(note)], zebra=(i % 2 == 1), bold_first=True)
        ws.row_dimensions[r].height = approx_height(v, 52)
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    cc = ws.cell(row=r, column=1, value="以下维度为本工作簿的固定比较骨架，可在 08 表追加自定义维度。")
    cc.font = Font(name="微软雅黑", size=9.5, italic=True, color="5A6670")
    r += 2
    header_row(ws, r, ["序号", "比较维度", "判读要点", "类型"], [8, 34, 62, 14])
    r += 1
    for i, d in enumerate(c.dims, start=1):
        body(ws, r, [i, d["label"], plain(d.get("hint", "")), d.get("type", "")], zebra=(i % 2 == 0))
        ws.row_dimensions[r].height = approx_height(d.get("hint", ""), 62)
        r += 1
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A5"

    # ---------- 02 横向比较 ----------
    ws = S("02 横向比较")
    ncol = 2 + len(sups) + 6
    title_block(ws, "02 供应商横向比较表", "每格含：数值/判断｜证据标签｜证据编号。金色“差异”列为自动比对结果，三家相同即为“无”", ncol)
    headers = ["序号", "比较维度"] + [sid_lbl[s["id"]] for s in sups] + ["差异", "三家趋同/分组", "判读要点", "", "", ""]
    header_row(ws, 4, headers, [6, 26] + [46] * len(sups) + [10, 34, 40, 3, 3, 3], height=34)
    r = 5
    for i, d in enumerate(c.dims, start=1):
        vals = [i, d["label"]]
        for s in sups:
            if d.get("type") == "terms":
                tc = c.term_cells.get("price", {}).get(s["id"], {})
                vals.append("[%s] %s" % (L.STATUS.get(tc.get("status", "pending"), {}).get("cn", ""), plain(tc.get("v")) or "见 06 表"))
            else:
                cell = c.cells[d["key"]][s["id"]]
                lbs = "/".join(L.LABELS[x]["cn"] for x in c.labels[(d["key"], s["id"])]) or "—"
                ev = ",".join(eids(cell.get("ev")))
                vals.append("%s\n〔%s〕%s" % (plain(cell.get("v")), lbs, ev if ev else ""))
        dd = c.dim_diff(d["key"])
        vals += ["是" if dd["differ"] else "否",
                 "｜".join(" = ".join(sid_lbl[x] for x in g) for g in dd["groups"]),
                 plain(d.get("hint", "")), "", "", ""]
        body(ws, r, vals, zebra=(i % 2 == 0), bold_first=False)
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=ncol - 3).alignment = Alignment(horizontal="center", vertical="center")
        if dd["differ"]:
            ws.cell(row=r, column=ncol - 3).font = Font(name="微软雅黑", size=9.5, bold=True, color="97702F")
        for col in (ncol - 2, ncol - 1, ncol):
            ws.column_dimensions[get_column_letter(col)].width = [10, 34, 40][col - (ncol - 2)]
        ws.row_dimensions[r].height = max(approx_height(max(vals[2:2 + len(sups)], key=len), 46), 30)
        r += 1
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "C5"

    # ---------- 03 厂家身份 ----------
    ws = S("03 厂家身份")
    title_block(ws, "03 企业主体与厂家身份核验", "判定对象：签约主体、开票主体、生产主体、许可证持有人是否同一；经营范围≠生产能力", 8)
    header_row(ws, 4, ["企业", "全称", "集团 / 控制关系", "证券代码 / 上市状态", "厂家身份判定", "判定依据", "生产基地", "证据"],
               [12, 34, 40, 20, 12, 56, 34, 12])
    r = 5
    for i, s in enumerate(sups):
        pr = L.PRODUCER.get(s.get("producer", "unknown"), L.PRODUCER["unknown"])
        body(ws, r, [sid_lbl[s["id"]], s.get("name"), plain(s.get("group")), s.get("code"), pr["cn"],
                     plain(s.get("producer_note")), plain(s.get("site")),
                     ",".join(sorted({e for d in c.dims if d.get("type") != "terms" for e in eids(c.cells[d["key"]][s["id"]].get("ev"))}, key=lambda x: int(x[1:]))[:8])],
             zebra=(i % 2 == 1), bold_first=True)
        ws.row_dimensions[r].height = max(approx_height(s.get("producer_note"), 56), 40)
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    cc = ws.cell(row=r, column=1, value="签约前必须核验的四项一致性：① 营业执照主体 = 合同相对方；② 开票主体 = 合同相对方；③ 生产主体地址 = 实际发货工厂；④ 排污/生产许可持有人 = 生产主体。任一项不一致，须在合同中加入生产主体一致性与违约责任条款。")
    cc.font = Font(name="微软雅黑", size=9.5, color="9C5F13")
    cc.fill = PatternFill("solid", fgColor="FBF1E1")
    cc.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[r].height = 48
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B5"

    # ---------- 04 产能与生产 ----------
    ws = S("04 产能与生产")
    title_block(ws, "04 公开产能、企业规模与生产能力", "核验要点：设计产能 × 产能利用率 = 年产量，三个数字能否自洽；不能自洽即为口径冲突", 9)
    header_row(ws, 4, ["企业", "纯碱设计产能", "2025 利用率", "2025 产量（万吨）", "反算校验", "规模指标", "工艺路线与重质能力", "未披露项", "证据"],
               [12, 18, 12, 16, 34, 34, 44, 34, 14])
    checks = {
        "A": "280 × 97.29% = 272.4 万吨，与年报产量一致 ✓",
        "B": "230 × 85.37% + 110 × 111.54% = 319.05 万吨，与年报产量一致 ✓",
        "C": "330 / 220 / 330（构成不同）三套口径并存，无法反算 ✗",
    }
    num_rows = {
        "A": [280, 0.9729, 272.4, 4451],
        "B": [340, 0.8537, 319.05, 17293],
        "C": [None, None, None, None],
    }
    r = 5
    for i, s in enumerate(sups):
        d = s.get("dims", {})
        cap = plain(d.get("capacity", {}).get("v", ""))
        mat = plain(d.get("match", {}).get("v", ""))
        heavy = plain(d.get("custom_heavy", {}).get("v", ""))
        if s["id"] == "A":
            nums = [280, 0.9729, 272.4, checks["A"],
                    "员工 4,451 人；2025 营收 47.45 亿元；纯碱占 67.82%；老线 120＋新线 160 万吨", mat + " ｜ " + heavy,
                    "重质实际占比、粒径分布、散装发运能力", "E01,E08,E27,E28"]
        elif s["id"] == "B":
            nums = [340, 0.8537, 319.05, checks["B"],
                    "员工 17,293 人；2025 营收 188.31 亿元；本部 230＋青海 110 万吨", mat + " ｜ " + heavy,
                    "许可产能、粒径分布、华东可分配量", "E04,E05,E06"]
        else:
            nums = [None, None, None, checks["C"],
                    "固定资产 101 亿元（自述）；化工企业 500 强第 129 位（自述）；官网自述 330 万吨", mat + " ｜ " + heavy,
                    "在产装置清单、产量、利用率、检修计划", "S:E11,M:E12,M:E19"]
        body(ws, r, [sid_lbl[s["id"]], nums[0], nums[1], nums[2], nums[3], nums[4], nums[5], nums[6], nums[7]],
             zebra=(i % 2 == 1), bold_first=True)
        ws.cell(row=r, column=2).number_format = '#,##0" 万吨/年"'
        ws.cell(row=r, column=3).number_format = '0.00%'
        ws.cell(row=r, column=4).number_format = '#,##0.0'
        for col in (2, 3, 4):
            ws.cell(row=r, column=col).alignment = Alignment(horizontal="center", vertical="center")
            if nums[col - 1] is None:
                ws.cell(row=r, column=col).value = "未披露"
                ws.cell(row=r, column=col).font = Font(name="微软雅黑", size=9.5, color="9C5F13")
        ws.row_dimensions[r].height = 92
        r += 1
    r += 1
    for line in [
        "行业对照：2026 年 6 月底国内纯碱产能约 4,500 万吨、开工率约 92%、上半年产量约 2,066 万吨（三友 2026 半年报，E06）；2024 年在产产能约 3,970 万吨（行业述评，E25）。",
        "三家均属合成碱体系（氨碱/联碱），天然碱（阿拉善一期 500 万吨已投产）扩张带来的成本挤压属系统性风险，不是企业个体差异。",
    ]:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
        cc = ws.cell(row=r, column=1, value="· " + line)
        cc.font = Font(name="微软雅黑", size=9.5, color="5A6670")
        cc.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = 34
        r += 1
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B5"

    # ---------- 05 资质许可 ----------
    ws = S("05 资质许可")
    title_block(ws, "05 经营资质与许可证照", "到期状态以数据截止日 %s 计算：<0 天 已过期 / ≤180 天 即将到期；工业碳酸钠不在工业产品生产许可证目录内" % m.get("as_of", ""), 9)
    header_row(ws, 4, ["企业", "证照名称", "有效期起", "有效期止", "状态", "剩余天数", "许可范围 / 适用产品", "持有人", "与本次采购相关度", "证据"],
               [12, 32, 13, 13, 12, 10, 42, 18, 14, 9])
    r = 5
    i = 0
    for ct in sorted(c.certs, key=lambda x: (x["sid"], x.get("end") or "9999")):
        st, tone = L.cert_state(ct.get("end"), c.as_of)
        days = ""
        try:
            y, mo, dd = [int(x) for x in str(ct.get("end")).replace("-", ".").split(".")]
            days = (date(y, mo, dd) - date(*[int(x) for x in c.as_of.split("-")])).days
        except Exception:
            days = ""
        rel = {"core": "核心（必需）", "related": "相关", "irrelevant": "无关"}.get(ct.get("relevance"), "")
        cert_ev = (s.get("certs_ev") if False else None)
        body(ws, r, [sid_lbl[ct["sid"]], ct.get("name"), ct.get("start", ""), ct.get("end", "") or "—",
                     st, days if days != "" else "—", plain(ct.get("scope")), ct.get("holder", ""), rel,
                     ct.get("ev") or ",".join(eids((S2.get(ct["sid"]) or {}).get("dims", {}).get("licence", {}).get("ev", "")))],
             zebra=(i % 2 == 1))
        tone_fill = {"expired": "FBEAE9", "soon": "FBF1E1", "valid": "E7F4ED"}.get(tone, "EEF0F1")
        tone_font = {"expired": "9C2A2A", "soon": "9C5F13", "valid": "1B6A49"}.get(tone, "4A5157")
        cc = ws.cell(row=r, column=5)
        cc.fill = PatternFill("solid", fgColor=tone_fill)
        cc.font = Font(name="微软雅黑", size=9.5, bold=True, color=tone_font)
        cc.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[r].height = max(approx_height(ct.get("scope"), 46), 26)
        r += 1
        i += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
    cc = ws.cell(row=r, column=1, value="依据：巨潮资讯网年报“相关批复、许可、资质及有效期的情况”。表中“—”代表公开渠道未取得，须在问询阶段索取（见 09 表）。")
    cc.font = Font(name="微软雅黑", size=9.5, color="9C5F13")
    cc.fill = PatternFill("solid", fgColor="FBF1E1")
    cc.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[r].height = 30
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "C5"

    # ---------- 06 报价对比 ----------
    ws = S("06 报价对比")
    title_block(ws, "06 商业条款（报价）对比", "8 项商业条款按统一口径归一化：出厂/到厂 × 散装/吨袋 × 含税/不含税 × 批次量。未收到报价＝待确认，不填估算", 6 + len(sups))
    rr = 4
    ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=6)
    cc = ws.cell(row=rr, column=1, value="报价状态：%s。%s" % (c.quotes.get("status_note") or "未收到报价", plain(c.quotes.get("note"))))
    cc.font = Font(name="微软雅黑", size=9.5, color="9C2A2A")
    cc.fill = PatternFill("solid", fgColor="FBEAE9")
    cc.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[rr].height = 46
    header_row(ws, 5, ["条款", "口径说明"] + [sid_lbl[s["id"]] for s in sups] + ["我方底线", "备注"],
               [16, 34] + [30] * len(sups) + [16, 24], height=28)
    r = 6
    term_note = {
        "price": "必须注明：出厂价 or 到厂价；散装 or 吨袋；含税 or 不含税",
        "tax": "13% 增值税专用发票 / 普票 / 不含税",
        "freight": "供方承担 / 需方承担 / 含运价 / 运费单独结算，损耗谁承担",
        "package": "散装罐车 / 500–1000 kg 吨袋 / 50 kg 编织袋，含托盘与回收条款",
        "payment": "预付 / 货到付款 / 月结 N 天 / 承兑（贴现成本折算）",
        "delivery": "下单后 N 天到货、是否接受月度均衡发货、是否接受紧急插单",
        "moq": "最小起订量（吨/车/批），小批量试单是否加价",
        "validity": "报价有效期、价格调整机制（月度/季度联动）",
    }
    dv = DataValidation(type="list", formula1='"待确认,已报价,不适用"', allow_blank=True)
    ws.add_data_validation(dv)
    for i, t in enumerate(data.get("terms", []) or []):
        vals = [t["label"], term_note.get(t["key"], "")]
        for s in sups:
            tc = c.term_cells[t["key"]][s["id"]]
            st = L.STATUS.get(tc.get("status", "pending"), {})
            vals.append("%s%s" % ("" if tc.get("status") == "pending" else (st.get("cn", "") + "："), plain(tc.get("v")) or "待确认"))
        vals += ["", ""]
        body(ws, r, vals, zebra=(i % 2 == 1), bold_first=True)
        ws.row_dimensions[r].height = max(approx_height(term_note.get(t["key"], ""), 34), 28)
        for col in range(3, 3 + len(sups)):
            dv.add(ws.cell(row=r, column=col))
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6 + len(sups))
    cc = ws.cell(row=r, column=1, value="归一化公式（收到报价后启用）：到厂含税单价 = 出厂不含税价 ×(1+13%) + 运费(元/吨) + 包装费 + 装卸/港杂 − 账期资金成本；其中账期资金成本 = 报价 × 年化利率 × 账期天数/365。")
    cc.font = Font(name="微软雅黑", size=9.5, color="5A6670")
    cc.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[r].height = 34
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "C6"

    # ---------- 07 风险与事件 ----------
    ws = S("07 风险与事件")
    title_block(ws, "07 经营风险、司法风险与近期负面事件", "等级＝对本次采购的潜在影响（高/中/低/未取得），不是企业整体评级；“未发现”≠“不存在”", 7)
    header_row(ws, 4, ["企业", "风险等级", "司法 / 经营风险要点", "负面事件", "事件等级", "关键差异", "证据"],
               [12, 10, 52, 46, 10, 44, 16])
    r = 5
    for i, s in enumerate(sups):
        d = s.get("dims", {})
        lv = d.get("risk", {}).get("lvl", "")
        ev = d.get("event", {}).get("lvl", "")
        body(ws, r, [sid_lbl[s["id"]], L.LEVELS.get(lv, {}).get("cn", lv),
                     plain(d.get("risk", {}).get("v")), plain(d.get("event", {}).get("v")),
                     L.LEVELS.get(ev, {}).get("cn", ev),
                     plain(next((f["title"] for f in c.findings if f.get("dim") == "risk"), "")),
                     ",".join(sorted(set(eids(d.get("risk", {}).get("ev", ""))) | set(eids(d.get("event", {}).get("ev", ""))), key=lambda x: int(x[1:])))],
             zebra=(i % 2 == 1), bold_first=True)
        lvf = {"high": "FBEAE9", "mid": "FBF1E1", "low": "E7F4ED", "none": "EEF0F1"}
        for col, key in ((2, lv), (5, ev)):
            cc = ws.cell(row=r, column=col)
            cc.fill = PatternFill("solid", fgColor=lvf.get(key, "EEF0F1"))
            cc.alignment = Alignment(horizontal="center", vertical="center")
            cc.font = Font(name="微软雅黑", size=9.5, bold=True, color=INK)
        ws.row_dimensions[r].height = max(approx_height(d.get("risk", {}).get("v"), 52), 70)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="近期动态（时间倒序）").font = Font(name="微软雅黑", size=11, bold=True, color=BRASS)
    r += 1
    header_row(ws, r, ["日期", "标签", "对象", "事件", "", "", "证据"], [12, 12, 12, 76, 3, 3, 16], height=24)
    r += 1
    for i, it in enumerate(sorted(c.intel, key=lambda x: str(x.get("date", "")), reverse=True)):
        vals = [it.get("date"), it.get("tag", ""), sid_lbl.get(it.get("supplier"), "行业"), plain(it.get("text")), "", "",
                ",".join(eids(it.get("evid")))]
        body(ws, r, vals, zebra=(i % 2 == 1))
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        ws.row_dimensions[r].height = approx_height(it.get("text"), 76)
        r += 1
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B5"

    # ---------- 08 自定义维度 ----------
    ws = S("08 自定义维度")
    title_block(ws, "08 自定义比较维度", "本表由 data.json 中 type=custom 的维度生成；可继续追加行做补充比较", 5 + len(sups))
    header_row(ws, 4, ["序号", "自定义维度", "为什么比较（判读要点）"] + [sid_lbl[s["id"]] for s in sups] + ["证据"],
               [6, 30, 34] + [38] * len(sups) + [16], height=28)
    r = 5
    customs = [d for d in c.dims if d.get("type") == "custom"]
    for i, d in enumerate(customs, start=1):
        vals = [i, d["label"], plain(d.get("hint", ""))]
        evs = []
        for s in sups:
            cell = c.cells[d["key"]][s["id"]]
            evs += eids(cell.get("ev"))
            vals.append(plain(cell.get("v")))
        vals.append(",".join(sorted(set(evs), key=lambda x: int(x[1:]))))
        body(ws, r, vals, zebra=(i % 2 == 0))
        ws.row_dimensions[r].height = 90
        r += 1
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5 + len(sups))
    cc = ws.cell(row=r, column=1, value="追加自定义维度的建议：① 与本次采购的失效模式直接相关（如纯碱的粒度/盐分/结块）；② 能通过文件或验厂核验；③ 不与已列维度重复。")
    cc.font = Font(name="微软雅黑", size=9.5, color="5A6670")
    cc.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[r].height = 30
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "D5"

    # ---------- 09 问询清单 ----------
    ws = S("09 问询清单")
    title_block(ws, "09 逐家问询问题清单", "可直接复制发送；每条注明优先级与“为什么要问”的依据", 6)
    header_row(ws, 4, ["企业", "编号", "优先级", "问题", "依据 / 为什么要问", "回复状态"],
               [14, 10, 9, 66, 52, 12], height=26)
    dv2 = DataValidation(type="list", formula1='"未发送,已发送,已回复,已闭环,无法提供"', allow_blank=True)
    ws.add_data_validation(dv2)
    r = 5
    i = 0
    for s in sups:
        for q in [x for x in c.q_all if x["sid"] == s["id"]]:
            body(ws, r, [sid_lbl[s["id"]], q.get("no", ""), q.get("priority", ""), plain(q.get("q")), plain(q.get("why")), "未发送"],
                 zebra=(i % 2 == 1))
            ws.cell(row=r, column=6).fill = PatternFill("solid", fgColor="FBF1E1")
            dv2.add(ws.cell(row=r, column=6))
            ws.row_dimensions[r].height = max(approx_height(q.get("q"), 66), 32)
            r += 1
            i += 1
    ws.auto_filter.ref = "A4:F%d" % (r - 1)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "D5"

    # ---------- 10 证据索引 ----------
    ws = S("10 证据索引")
    title_block(ws, "10 证据索引", "%d 条；02 表中的每个编号都能在此找到来源与链接" % len(c.ev), 7)
    header_row(ws, 4, ["编号", "文件 / 页面", "来源", "日期", "类型", "支撑了什么", "链接"],
               [7, 40, 24, 12, 16, 62, 46], height=26)
    r = 5
    for i, e in enumerate(data.get("evidence", [])):
        body(ws, r, [e["id"], e.get("name"), e.get("source"), e.get("date"), e.get("type"), plain(e.get("note")), e.get("url")],
             zebra=(i % 2 == 1))
        cc = ws.cell(row=r, column=1)
        cc.alignment = Alignment(horizontal="center", vertical="center")
        cc.font = Font(name="微软雅黑", size=9.5, bold=True, color=BRASS)
        if e.get("url", "").startswith("http"):
            lc = ws.cell(row=r, column=7)
            lc.hyperlink = e["url"]
            lc.font = Font(name="微软雅黑", size=9, color="2A5A86", underline="single")
        ws.row_dimensions[r].height = max(approx_height(e.get("note"), 62), 26)
        r += 1
    ws.auto_filter.ref = "A4:G%d" % (r - 1)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B5"

    # ---------- 11 评分留白 ----------
    ws = S("11 评分留白")
    title_block(ws, "11 评估留白（权重与分数由采购方填写，本表不做任何结论）",
                "本表不含预设权重与预设分数；填入权重后自动加权，用于内部评审记录，不构成“最佳供应商”判定", 6 + len(sups))
    header_row(ws, 4, ["序号", "评估项", "评分要点（填分依据）", "权重 %"] + [sid_lbl[s["id"]] + "（1–5）" for s in sups]
               + [sid_lbl[s["id"]] + " 加权" for s in sups] + ["备注"],
               [6, 30, 44, 10] + [12] * len(sups) + [12] * len(sups) + [24], height=30)
    r = 5
    first = r
    for i, d in enumerate(c.dims, start=1):
        if d.get("type") == "terms":
            pts = "得分依据：报价完整度与条款可比性（收到报价后填写）"
        else:
            pts = plain(d.get("hint", ""))
        body(ws, r, [i, d["label"], pts, None] + [None] * len(sups) + [None, ""], zebra=(i % 2 == 0))
        ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor="FFFDF4")
        for col in range(5, 5 + len(sups) + 1):
            ws.cell(row=r, column=col).fill = PatternFill("solid", fgColor="FFFDF4")
        r += 1
    last = r - 1
    # 权重合计行（先占位，稍后写公式，避免与本表其他数据行冲突）
    sum_row = r
    tone = r
    # 每行得分 = 权重 × 分值 / 100；表尾按企业求和（不用数组公式，Excel 与 LibreOffice 均直接生效）
    # 布局：D 权重｜E.. 各供应商分数｜随后每供应商一列合计｜备注
    sum_first = 5 + len(sups)
    for k in range(len(sups)):
        sc = get_column_letter(5 + k)
        oc = get_column_letter(sum_first + k)
        for rr2 in range(first, last + 1):
            cc = ws.cell(row=rr2, column=sum_first + k,
                         value="=IF(OR($D%d=\"\",%s%d=\"\"),\"\",$D%d*%s%d/100)" % (rr2, sc, rr2, rr2, sc, rr2))
            cc.number_format = "0.00"
            cc.alignment = Alignment(horizontal="center", vertical="center")
            cc.border = BORDER
            cc.font = Font(name="微软雅黑", size=9, color="8A949B")
    for k in range(len(sups)):
        oc = get_column_letter(sum_first + k)
        cc = ws.cell(row=tone, column=sum_first + k,
                     value="=SUM(%s%d:%s%d)" % (get_column_letter(sum_first + k), first, get_column_letter(sum_first + k), last))
        cc.number_format = "0.00"
        cc.font = Font(name="微软雅黑", size=10, bold=True, color=BRAND)
        cc.fill = PatternFill("solid", fgColor="EAF1F3")
        cc.alignment = Alignment(horizontal="center", vertical="center")
        cc.border = BORDER
    # 权重合计
    wc = ws.cell(row=tone, column=4, value="=SUM(D%d:D%d)" % (first, last))
    wc.font = Font(name="微软雅黑", size=10, bold=True)
    wc.alignment = Alignment(horizontal="center", vertical="center")
    wc.border = BORDER
    ws.cell(row=tone, column=2, value="合计 / 加权得分").font = Font(name="微软雅黑", size=10, bold=True, color=BRAND)
    ws.cell(row=tone, column=2).border = BORDER
    ws.cell(row=tone, column=3, value="每行得分＝权重×分值/100；右侧为各企业加权得分合计（权重合计应为 100）").font = Font(name="微软雅黑", size=9, color="5A6670")
    ws.cell(row=tone, column=3).border = BORDER
    r = tone + 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12 + 2 * len(sups))
    cc = ws.cell(row=r, column=1, value="使用说明：① 只对“可核验”的评估项打 1–5 分，无法核实记 0 并写明原因；② 权重按本次采购的实际敏感度自行设定（例如质量稳定性、保供、到厂价）；③ 若某家在某项上为“无法核实”，建议先在 09 表问询闭环后再打分。")
    cc.font = Font(name="微软雅黑", size=9.5, color="9C5F13")
    cc.fill = PatternFill("solid", fgColor="FBF1E1")
    cc.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[r].height = 44
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "E5"

    # ---------- 12 字段说明 ----------
    ws = S("12 字段说明")
    title_block(ws, "12 数据契约与字段说明", "本工作簿由 data.json 生成；下表说明每个字段的取值域，便于二次复用与校验", 5)
    header_row(ws, 4, ["字段路径", "取值域", "含义", "是否必填", "示例"], [34, 44, 44, 10, 30], height=26)
    spec = [
        ("suppliers[].id", "A–Z 单字母", "供应商代号，全表引用", "必填", "A"),
        ("suppliers[].producer", "producer / doubt / trader / unknown", "厂家身份判定（doubt=主体是厂家但签约主体待定）", "必填", "doubt"),
        ("suppliers[].dims.<key>.v", "文本，可用 <b> <br> 少量标签", "该维度的结论性描述", "必填", "纯碱设计产能 280 万吨/年"),
        ("suppliers[].dims.<key>.ev", "V:E01,E02 或 M:E05", "证据引用：标签:编号，多标签用 , 分隔", "必填", "V:E01,E27"),
        ("suppliers[].dims.<key>.lvl", "high / mid / low / none", "风险或事件等级（仅 risk/event 用）", "选填", "low"),
        ("dimensions[].type", "producer/location/capacity/match/licence/risk/event/custom/terms", "决定渲染方式与判读要点", "必填", "custom"),
        ("evidence[].id", "E01…Enn 或 U", "证据编号，U 固定为“未取得”登记", "必填", "E28"),
        ("terms[].key", "price/tax/freight/package/payment/delivery/moq/validity", "商业条款八项", "必填", "payment"),
        ("quotes.status", "none / partial / full", "报价回收状态", "必填", "none"),
        ("questions.<id>[]", "{dim, priority, q, why}", "逐家问询问题", "必填", "priority=高"),
        ("findings[].level", "high / mid / low", "差异条目对采购的影响程度", "必填", "high"),
    ]
    r = 5
    for i, row in enumerate(spec):
        body(ws, r, list(row), zebra=(i % 2 == 1))
        ws.cell(row=r, column=1).font = Font(name="Consolas", size=9, color=BRAND)
        ws.row_dimensions[r].height = 28
        r += 1
    ws.sheet_view.showGridLines = False

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    print("XLSX -> %s (%d sheets)" % (out, len(wb.sheetnames)))


def main():
    import json
    if len(sys.argv) < 3:
        print("usage: python render_xlsx.py data.json out.xlsx")
        raise SystemExit(2)
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    build(data, sys.argv[2])


if __name__ == "__main__":
    main()
