# -*- coding: utf-8 -*-
"""fields.json → 专业报价工作簿（.xlsx，7 个工作表）。

版式：深蓝标题 + 金色点缀 + 缺失项黄色高亮 + 输入区浅黄底。
价格单元格永远留空（除非用户已确认），金额用公式 =IFERROR(...)，没有价就显示"待填单价"。

    python build_xlsx.py fields.json -o 报价工作簿.xlsx
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import xlsxwriter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

FONT = "微软雅黑"
DEEP = "#0A2A66"
ACCENT = "#1E56C8"
GOLD = "#C8963C"
INK = "#101A2C"
SUB = "#5B6A82"
LINE = "#DCE4F0"
BG_SOFT = "#F7F9FD"
BG_HEAD = "#EEF3FB"
YELLOW = "#FDF0D3"
YELLOW_INK = "#9A5B00"
INPUT_BG = "#FFF8E1"
GREEN = "#0F7B3F"
GREEN_BG = "#E2F5E9"
RED = "#B42318"
RED_BG = "#FDE7E4"

S1 = "01 询盘概要"
S2 = "02 字段确认表"
S3 = "03 缺失与假设"
S4 = "04 价格与口径"
S5 = "05 报价草稿"
S6 = "06 口径与边界"
S7 = "07 素材与证据"


# ---------------------------------------------------------------- 格式表


def make_formats(wb):
    f = {}
    base = {"font_name": FONT, "font_size": 10.5, "font_color": INK, "valign": "vcenter"}

    def add(name, **kw):
        d = dict(base)
        d.update(kw)
        f[name] = wb.add_format(d)

    add("title", font_size=20, bold=True, font_color="#FFFFFF", bg_color=DEEP, align="left", indent=1)
    add("subtitle", font_size=10, font_color="#C9D8F5", bg_color=DEEP, align="left", indent=1)
    add("cover_left", font_size=11, font_color="#FFFFFF", bg_color=DEEP, align="right")

    add("h2", font_size=12, bold=True, font_color=DEEP, align="left", indent=0)
    add("h3", font_size=10.5, bold=True, font_color=DEEP)
    add("label", font_size=10, font_color=SUB)
    add("value", font_size=11, bold=True, font_color=INK, text_wrap=True)
    add("value_plain", font_size=10.5, font_color=INK, text_wrap=True)

    add("th", font_size=10.5, bold=True, font_color="#FFFFFF", bg_color=ACCENT,
        align="center", border=1, border_color="#FFFFFF", text_wrap=True)
    add("td", border=1, border_color=LINE, text_wrap=True)
    add("td_c", border=1, border_color=LINE, align="center", text_wrap=True)
    add("td_alt", border=1, border_color=LINE, text_wrap=True, bg_color=BG_SOFT)
    add("td_alt_c", border=1, border_color=LINE, align="center", text_wrap=True, bg_color=BG_SOFT)
    add("td_num", border=1, border_color=LINE, align="right", num_format="#,##0.00")
    add("td_num_b", border=1, border_color=LINE, align="right", num_format="#,##0.00", bold=True)

    add("badge_ok", border=1, border_color="#B7E3C8", bg_color=GREEN_BG, font_color=GREEN,
        bold=True, align="center")
    add("badge_miss", border=1, border_color="#EBC98D", bg_color=YELLOW, font_color=YELLOW_INK,
        bold=True, align="center")
    add("badge_tbc", border=1, border_color="#F3C9C3", bg_color=RED_BG, font_color=RED,
        bold=True, align="center")
    add("badge_user", border=1, border_color="#C9D6EE", bg_color="#EDF3FF", font_color=ACCENT,
        bold=True, align="center")
    add("badge_assume", border=1, border_color="#E7D9A8", bg_color="#FFFBEA", font_color=YELLOW_INK,
        bold=True, align="center")

    add("input", border=1, border_color="#E0C07A", bg_color=INPUT_BG, align="left",
        font_size=10.5, text_wrap=True)
    add("input_num", border=1, border_color="#E0C07A", bg_color=INPUT_BG, num_format="#,##0.00",
        align="right", font_size=11, bold=True)
    add("input_pct", border=1, border_color="#E0C07A", bg_color=INPUT_BG, num_format="0.00%",
        align="right", font_size=10.5)
    add("input_hint", font_size=9, font_color="#A98545", align="left", text_wrap=True)

    add("note", font_size=9.5, font_color="#8D99AD", text_wrap=True)
    add("note_b", font_size=9.5, font_color=SUB, bold=True)
    add("bullet", font_size=10.5, font_color=INK, text_wrap=True, indent=1)

    add("block_title", font_size=12, bold=True, font_color="#FFFFFF", bg_color=DEEP, indent=1)
    add("rule", font_size=10, font_color=INK, text_wrap=True, border=1, border_color=LINE)
    add("quote_company", font_size=16, bold=True, font_color=DEEP, align="center")
    add("quote_h1", font_size=22, bold=True, font_color=DEEP, align="center")
    add("quote_meta", font_size=10, font_color=SUB, align="left")
    add("quote_meta_r", font_size=10, font_color=SUB, align="right")
    add("quote_section", font_size=11, bold=True, font_color=DEEP, align="left")
    add("quote_cell", font_size=10, font_color=INK, border=1, border_color=LINE, text_wrap=True, valign="top")
    add("quote_cell_c", font_size=10, font_color=INK, border=1, border_color=LINE, align="center", valign="top")
    add("quote_cell_r", font_size=10, font_color=INK, border=1, border_color=LINE, align="right", valign="top",
        num_format="#,##0.00")
    add("quote_th", font_size=10, bold=True, font_color="#FFFFFF", bg_color=ACCENT, border=1,
        border_color="#FFFFFF", align="center", text_wrap=True)
    add("quote_total_l", font_size=10.5, bold=True, bg_color=BG_HEAD, border=1, border_color=LINE, align="center")
    add("quote_total_r", font_size=11, bold=True, bg_color=BG_HEAD, border=1, border_color=LINE,
        align="right", num_format="#,##0.00", font_color=DEEP)
    add("quote_sign", font_size=10, font_color=SUB, align="center")
    return f


def money_cell(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return ""


def row_height(text, chars_per_line, base=20, line=15, max_h=110):
    """按字数估行高，避免长文本被行高裁切（xlsxwriter 不会自动撑高）。"""
    import math

    n = max(1, math.ceil(len(str(text)) / max(1, chars_per_line)))
    return max(base, min(max_h, base + line * (n - 1)))


# ---------------------------------------------------------------- 工作表 01


def sheet_overview(wb, f, doc, blockers):
    ws = wb.add_worksheet(S1)
    ws.hide_gridlines(2)
    ws.set_tab_color(DEEP)
    ws.set_column("A:A", 3)
    ws.set_column("B:B", 16)
    ws.set_column("C:C", 30)
    ws.set_column("D:D", 4)
    ws.set_column("E:E", 16)
    ws.set_column("F:F", 30)
    ws.set_column("G:G", 3)

    ws.merge_range("B2:F2", "询盘 → 报价草稿工作簿", f["title"])
    ws.set_row(1, 38)
    meta = doc["meta"]
    demo_tag = "　｜　DEMO 演示价（非建议价 / 非成交价）" if "演示" in str(doc["price"].get("ack", "")) else ""
    head = (f"客户：{meta.get('customer') or '待客户确认'}　｜　询盘编号 {meta['inquiry_no']}"
            f"　｜　as_of {meta['as_of']}　｜　状态：{status_word(doc)}{demo_tag}")
    ws.merge_range("B3:F3", head, f["subtitle"])
    ws.set_row(2, 20)

    rows = [
        ("产品名称", doc["fields"]["product"]["value"] or "待客户确认", "规格 / 牌号", doc["fields"]["grade"]["value"] or "待客户确认"),
        ("数量口径", doc["fields"]["quantity"]["value"] or "待客户确认", "交货地点", doc["fields"]["place"]["value"] or "待客户确认"),
        ("包装", eff(doc["fields"]["packaging"]), "交期", eff(doc["fields"]["delivery_date"])),
        ("付款条件", eff(doc["fields"]["payment"]), "运输方式", eff(doc["fields"]["incoterm"])),
        ("税费口径", doc["gate"]["tax_mode"]["value"] or "待你确认", "运费口径", doc["gate"]["freight_mode"]["value"] or "待你确认"),
        ("确认单价", ("%s 元/吨" % C.money(doc["price"]["unit_price"])) if doc["price"]["unit_price"] else "待你填写（系统不生成）",
         "报价有效期", f"{doc['price'].get('validity_days') or 7} 天"),
    ]
    r = 4
    ws.merge_range(r, 1, r, 6, "一、询盘要点（提取值 · 未确认项已在字段表标黄）", f["h2"])
    r += 1
    for l1, v1, l2, v2 in rows:
        ws.write(r, 1, l1, f["label"])
        ws.write(r, 2, v1, f["value"])
        ws.write(r, 4, l2, f["label"])
        ws.write(r, 5, v2, f["value"])
        ws.set_row(r, 26)
        r += 1

    r += 1
    ws.merge_range(r, 1, r, 6, "二、进度与阻塞（决定「生成报价草稿」按钮是否可点）", f["h2"])
    r += 1
    musts = C.must_rows(doc)
    ready = sum(1 for x in musts if x["value"].strip() and x["status"] not in ("missing", "tbc"))
    cards = [
        ("必须项已确认", f"{ready} / {len(musts)}", GREEN if ready == len(musts) else YELLOW_INK),
        ("假设项", f"{len(C.assume_rows(doc))} 项待客户确认", SUB),
        ("阻塞项", f"{len(blockers)} 项", RED if blockers else GREEN),
        ("能否生成报价草稿", "否" if blockers else "是", RED if blockers else GREEN),
    ]
    c = 1
    for label, val, color in cards:
        ws.write(r, c, label, f["label"])
        ws.write(r, c + 1, val, wb.add_format({"font_name": FONT, "font_size": 12, "bold": True,
                                               "font_color": color, "valign": "vcenter", "align": "left"}))
        c += 2
        if c > 4:
            c = 1
            r += 2
    r += 1

    if blockers:
        ws.merge_range(r, 1, r, 6, "阻塞项清单", f["h3"])
        r += 1
        for i, b in enumerate(blockers, 1):
            ws.write(r, 1, f"{i:02d}", f["td_c"])
            ws.merge_range(r, 2, r, 6, b, f["badge_miss"] if b.startswith("缺") else f["td"])
            ws.set_row(r, 20)
            r += 1
    else:
        ws.merge_range(r, 1, r, 6, "无阻塞项：可在「04 价格与口径」核对后生成报价草稿。", f["badge_ok"])
        r += 1

    r += 1
    ws.merge_range(r, 1, r, 6, "三、怎么用这个工作簿", f["h2"])
    r += 1
    howto = [
        "① 02 表逐行确认：提取值可改，状态改成「已提取 / 待客户确认 / 我方假设 / 缺」；缺的会一直标黄。",
        "② 03 表看两类分桶：A 类（必须补充才能报价）不清完不许报价；B 类（可先按假设准备）按假设出草稿并标注。",
        "③ 04 表填你自己确认的单价、税费口径、运费口径——系统不填、不推荐、不生成任何价格。",
        "④ 04 表确认栏选「已确认」后，05 表明细的单价/金额才会算出来；未确认时显示「待填单价」。",
        "⑤ 05 表是可打印的正式报价版式，单价全部引用 04 表，改一处全表联动。",
        "⑥ 06 表是口径与边界，对外发送前请业务负责人过一遍；07 表留素材出处，便于复核。",
    ]
    for line in howto:
        ws.merge_range(r, 1, r, 6, line, f["bullet"])
        ws.set_row(r, 22)
        r += 1

    end = r + 1
    ws.merge_range(end, 1, end, 6,
                   "价格红线：本工作簿不含任何默认价、参考价、区间价。单价只来自你在 04 表的输入。",
                   f["note"])
    if doc["meta"].get("case_disclaimer"):
        end += 1
        ws.merge_range(end, 1, end, 6, "说明：" + doc["meta"]["case_disclaimer"], f["note"])
        ws.set_row(end, 24)
    ws.print_area(0, 0, end, 6)
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    return ws


def status_word(doc):
    return "可生成报价草稿" if not C.blockers(doc) else "待补 %d 项" % len(C.blockers(doc))


def eff(row):
    v = (row.get("value") or "").strip()
    if v:
        return v + ("（我方假设）" if row["status"] == "assumed" else "")
    d = (row.get("assume_default") or "").strip()
    return f"{d}（我方假设）" if d else "待客户确认"


# ---------------------------------------------------------------- 工作表 02


def sheet_fields(wb, f, doc):
    ws = wb.add_worksheet(S2)
    ws.hide_gridlines(2)
    ws.set_tab_color(ACCENT)
    widths = [5, 13, 15, 34, 46, 9, 7, 13, 26]
    for i, w in enumerate(widths):
        ws.set_column(i, i, w)
    ws.freeze_panes(3, 0)

    ws.merge_range(0, 0, 0, 8, "字段确认表 · 逐行点头，缺的会一直标黄", f["title"])
    ws.set_row(0, 34)
    ws.merge_range(1, 0, 1, 8,
                   "提取值可改；出处列是询盘原句（复核用）；状态列请按事实选择——"
                   "客户没说过的，只能填「待客户确认」或「缺」，不能填「已提取」。", f["subtitle"])
    ws.set_row(1, 22)

    heads = ["#", "归属", "字段", "提取值（可改）", "出处（询盘原句）", "素材", "置信度", "状态", "处理建议"]
    for i, h in enumerate(heads):
        ws.write(2, i, h, f["th"])
    ws.set_row(2, 26)

    advice = {
        "product": "与客户确认是否指定牌号/供应商",
        "grade": "把我方标准指标发客户确认，差异项逐条对",
        "quantity": "拆成试单量 + 月用量两行确认，别用月用量签首单",
        "place": "确认厂区/卸货点、是否需要预约卸车",
        "customer": "核对开票主体全称与纳税人识别号",
        "packaging": "吨包/袋装/槽车会影响成本，客户不指定时按假设并在报价注明",
        "delivery_date": "确认是到货日还是发货日，扣掉备货期",
        "payment": "先按我方标准口径报，客户要账期须走审批",
        "incoterm": "确认整车/零担，卸货条件",
        "validity": "纯碱随行就市，有效期建议 3~7 天",
    }

    r = 3
    for bucket in ("must", "assume"):
        label = C.BUCKET_LABEL[bucket]
        fill = f["block_title"] if bucket == "must" else wb.add_format(
            {"font_name": FONT, "font_size": 12, "bold": True, "font_color": GOLD,
             "bg_color": "#FFF8E1", "indent": 1, "border": 1, "border_color": "#E7D9A8"})
        ws.merge_range(r, 0, r, 8, f"{'A' if bucket == 'must' else 'B'} 类 · {label}", fill)
        ws.set_row(r, 24)
        r += 1
        for key in C.FIELD_KEYS:
            row = doc["fields"][key]
            if row["bucket"] != bucket:
                continue
            st = row["status"]
            badge = {"extracted": f["badge_ok"], "missing": f["badge_miss"],
                     "tbc": f["badge_tbc"], "assumed": f["badge_assume"]}[st]
            status_text = {"extracted": "已提取", "missing": "缺", "tbc": "待客户确认",
                           "assumed": "我方假设"}[st]
            ws.write(r, 0, r - 3, f["td_c"])
            ws.write(r, 1, "必须" if bucket == "must" else "假设", f["td_c"])
            ws.write(r, 2, row["label"], wb.add_format(
                {"font_name": FONT, "font_size": 10.5, "bold": True, "border": 1,
                 "border_color": LINE, "text_wrap": True, "bg_color": RED_BG if st == "missing" else "#FFFFFF"}))
            ws.write(r, 3, row["value"] or (row["assume_default"] + "（我方假设）" if bucket == "assume" else ""),
                     f["input"] if bucket == "must" else f["input"])
            ws.write(r, 4, row["source"] or "—", f["note"])
            ws.write(r, 5, (row["source"].split(" · ")[0] if " · " in row["source"] else "—"), f["td_c"])
            ws.write(r, 6, row["confidence"] or "—", f["td_c"])
            ws.write(r, 7, status_text, badge)
            ws.write(r, 8, advice.get(key, ""), f["note"])
            ws.set_row(r, row_height(max(row["source"] or "", advice.get(key, "")), 46, base=34, max_h=110))
            r += 1

    # 用户侧口径两行
    ws.merge_range(r, 0, r, 8, "C 类 · 我方口径（必须由你选择，不能从询盘单向提取）", f["block_title"])
    ws.set_row(r, 24)
    r += 1
    for key, label in C.GATE_SPEC:
        g = doc["gate"][key]
        ws.write(r, 0, r - 3, f["td_c"])
        ws.write(r, 1, "必须", f["td_c"])
        ws.write(r, 2, label, wb.add_format({"font_name": FONT, "font_size": 10.5, "bold": True,
                                             "border": 1, "border_color": LINE, "bg_color": RED_BG}))
        ws.write(r, 3, g["value"] or "", f["input"])
        ws.write(r, 4, g.get("hint") or "询盘中未提及", f["note"])
        ws.write(r, 5, "—", f["td_c"])
        ws.write(r, 6, "—", f["td_c"])
        ws.write(r, 7, "待你确认" if not g["value"] else "已确认", f["badge_user"] if not g["value"] else f["badge_ok"])
        ws.write(r, 8, "税费写进报价可避免来回；运费口径直接决定到厂价", f["note"])
        ws.set_row(r, 30)
        r += 1

    # 状态下拉 + 条件格式
    ws.data_validation(3, 7, r, 7, {"validate": "list",
                                    "source": ["已提取", "待客户确认", "我方假设", "缺"]})
    ws.conditional_format(3, 7, r, 7, {"type": "cell", "criteria": "==", "value": '"缺"', "format": f["badge_miss"]})
    ws.conditional_format(3, 7, r, 7, {"type": "cell", "criteria": "==", "value": '"待客户确认"',
                                       "format": f["badge_tbc"]})
    ws.conditional_format(3, 3, r, 3, {"type": "blanks", "format": f["badge_miss"]})

    ws.merge_range(r + 1, 0, r + 1, 8,
                   "标黄 = 缺失或待确认。A 类不清完不许报价；B 类可以带假设出草稿，但必须在报价里写明"
                   "「我方假设 · 待客户确认」。", f["note"])
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.print_area(0, 0, r + 1, 8)
    return ws


# ---------------------------------------------------------------- 工作表 03


def sheet_gaps(wb, f, doc):
    ws = wb.add_worksheet(S3)
    ws.hide_gridlines(2)
    ws.set_tab_color(YELLOW_INK)
    for i, w in enumerate([16, 30, 40, 16, 34]):
        ws.set_column(i, i, w)

    ws.merge_range(0, 0, 0, 4, "缺失项与假设 · 两类分开，决定这单能不能先报", f["title"])
    ws.set_row(0, 34)

    r = 2
    ws.merge_range(r, 0, r, 4, "A 类 · 必须补充后才能报价", f["block_title"])
    r += 1
    for i, h in enumerate(["字段", "现状", "为什么必须先补", "由谁补", "建议问法（可直接发客户）"]):
        ws.write(r, i, h, f["th"])
    ws.set_row(r, 24)
    r += 1
    why = {
        "product": ("重质/轻质纯碱价差大，产品不定价没法定", "客户采购",
                    "确认是重质纯碱还是轻质纯碱，牌号/厂家有无指定？"),
        "grade": ("纯度/粒度/杂质决定用哪条产线，也决定价格档位", "客户质检",
                  "能否提供贵司纯碱验收指标（Na2CO3、Fe2O3、粒度、烧失量）？"),
        "quantity": ("试单量影响成本，月用量决定是否给长约价", "客户采购",
                     "首单多少吨？后续月用量与年度计划大概多少？"),
        "place": ("决定运费与卸货方式，到厂价没有地点算不出来", "客户仓储",
                  "收货厂区具体地址、是否需要预约卸车、有无地磅？"),
        "customer": ("开票主体决定合同与发票抬头", "客户财务",
                     "开票主体全称、纳税人识别号、是否需要专票？"),
    }
    a_rows = []
    for key in C.FIELD_KEYS:
        row = doc["fields"][key]
        if row["bucket"] != "must":
            continue
        if (row["value"] or "").strip() and row["status"] not in ("missing", "tbc"):
            continue
        t = why.get(key, ("", "", ""))
        fmt_key = "badge_tbc" if (row["value"] and row["status"] == "tbc") else "badge_miss"
        a_rows.append((row["label"], row["value"] or "缺失", t[0], t[1], t[2], fmt_key))

    for key, label, why_txt, ask in [
        ("tax_mode", "税费口径", "含税/不含税、专票/普票决定客户能不能直接比价", "确认开 13% 专票，还是普票 / 不含税？"),
        ("freight_mode", "运费口径", "到厂价与出厂价差的是运费谁承担，报错口径等于报错价", "确认本次报送到厂价，还是出厂价（客户自提）？"),
    ]:
        if not (doc["gate"][key].get("value") or "").strip():
            a_rows.append((label, "待你选择", why_txt, "我方销售 / 财务", ask, "badge_miss"))

    if not C._positive(doc["price"].get("unit_price")):
        a_rows.append(("确认单价", "待你填写（系统不生成）",
                       "没有销售确认的单价，报价单就不能成立", "我方销售",
                       "请给出本次销售单价；系统不会给默认价、参考价或区间价。", "badge_miss"))
    if not str(doc["price"].get("ack", "") or "").strip():
        a_rows.append(("价格确认", "未勾选",
                       "确认该单价是我方销售价格，避免把测试数字误发出去", "我方销售",
                       "报价前勾选「我确认该单价为我方销售价格」；脚本用 --ack。", "badge_miss"))

    if a_rows:
        for label, now, why_txt, who, ask, fmt_key in a_rows:
            ws.write(r, 0, label, wb.add_format({"font_name": FONT, "font_size": 10.5, "bold": True,
                                                 "border": 1, "border_color": LINE, "text_wrap": True}))
            ws.write(r, 1, now, f[fmt_key])
            ws.write(r, 2, why_txt, f["td"])
            ws.write(r, 3, who, f["td_c"])
            ws.write(r, 4, ask, f["td_alt"])
            ws.set_row(r, row_height(ask, 34, base=36, max_h=96))
            r += 1
    else:
        ws.merge_range(r, 0, r, 4, "A 类已齐：客户名称、税费口径、运费口径、确认单价、价格确认均有值。", f["badge_ok"])
        ws.set_row(r, 28)
        r += 1

    r += 1
    ws.merge_range(r, 0, r, 4, "B 类 · 可先按假设准备（报价里必须标注「我方假设 · 待客户确认」）", f["block_title"])
    r += 1
    for i, h in enumerate(["字段", "本次采用的假设", "依据", "客户改口时的条件", "风险与提醒"]):
        ws.write(r, i, h, f["th"])
    ws.set_row(r, 24)
    r += 1
    assume_note = {
        "packaging": ("纯碱行业默认吨包/袋装，栈板+缠膜便于整车运输", "客户指定 25kg 袋或槽车散装时改",
                      "槽车散装单价更低，但要确认卸车泵与罐容"),
        "delivery_date": ("常规备货 5~7 个工作日", "客户要求具体到货日时按排产回签",
                          "纯碱旺季/检修季要留缓冲，别承诺死日期"),
        "payment": ("先按我方标准口径报，账期须审批", "客户要求月结时走信用审批",
                    "账期是最大隐性成本，别在报价阶段口头松动"),
        "incoterm": ("汽运整车为主，零担成本高", "偏远厂区或小批量时改零担/铁路",
                     "整车与零担差价可能吃掉毛利"),
        "validity": ("纯碱随行就市，报价有效期不宜长", "客户要求锁价时按期货/长约另行审批",
                     "有效期过长等于单边让出价格调整权"),
    }
    for key in C.FIELD_KEYS:
        row = doc["fields"][key]
        if row["bucket"] != "assume":
            continue
        ws.write(r, 0, row["label"], wb.add_format({"font_name": FONT, "font_size": 10.5, "bold": True,
                                                    "border": 1, "border_color": LINE, "text_wrap": True}))
        val = row["value"] if row["status"] == "extracted" else (row["assume_default"] + "（我方假设）")
        fmt_key = "badge_ok" if row["status"] == "extracted" else "badge_assume"
        ws.write(r, 1, val, f[fmt_key])
        t = assume_note.get(key, ("", "", ""))
        basis = "客户询盘中已明确，按原话记录；报价仍可按客户要求调整" if row["status"] == "extracted" else t[0]
        ws.write(r, 2, basis, f["td"])
        ws.write(r, 3, t[1], f["td"])
        ws.write(r, 4, t[2], f["td_alt"])
        ws.set_row(r, row_height(t[2], 34, base=34, max_h=90))
        r += 1

    r += 1
    ws.merge_range(r, 0, r, 4, "待客户确认清单（报价草稿会自动带出这一段）", f["h3"])
    r += 1
    ctx_pending = C.build_context(doc)["pending"]
    for item in ctx_pending:
        ws.merge_range(r, 0, r, 4, "· " + item, f["td"])
        ws.set_row(r, row_height(item, 62, base=22, max_h=64))
        r += 1
    if not ctx_pending:
        ws.merge_range(r, 0, r, 4, "· 无", f["td"])
        r += 1

    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.print_area(0, 0, r, 4)
    return ws


# ---------------------------------------------------------------- 工作表 04


def sheet_price(wb, f, doc):
    ws = wb.add_worksheet(S4)
    ws.hide_gridlines(2)
    ws.set_tab_color(GOLD)
    ws.set_column("A:A", 3)
    ws.set_column("B:B", 18)
    ws.set_column("C:C", 30)
    ws.set_column("D:D", 4)
    ws.set_column("E:E", 34)
    ws.set_column("F:F", 22)

    ws.merge_range("B2:F2", "价格与口径 · 只有你填了这里，「生成报价草稿」才算成立", f["title"])
    ws.set_row(1, 34)
    ws.merge_range("B3:F3", "本表不接受任何系统预填价格。单价留空 = 待填；填了就代表你确认这是本次成交口径。", f["subtitle"])
    ws.set_row(2, 22)

    ws.merge_range("B5:C5", "① 你的确认价格（必填）", f["h2"])
    rows = [
        ("single_price", "确认单价（元/吨）", None, f["input_num"],
         "留空即待填。纯碱行业单位：元/吨（含税或不含税由下一行口径决定）"),
        ("qty", "本次报价数量（吨）", money_cell(doc["price"].get("quote_quantity")), f["input_num"],
         "默认取询盘里的试单量；改这里只改本次报价，不改询盘字段"),
        ("unit", "计价单位", doc["price"].get("quote_quantity_unit") or "吨", f["input"], "吨 / kg / 包"),
        ("rate", "税率", 0.13, f["input_pct"], "增值税专票 13%（纯碱适用）；小规模/普票请按实际"),
        ("tax", "税费口径", None, f["input"], "下拉选择；报价文字直接引用这段"),
        ("freight", "运费口径", None, f["input"], "下拉选择；到厂价含运费，出厂价不含"),
        ("validity", "报价有效期（天）", int(doc["price"].get("validity_days") or 7), f["input_num"],
         "纯碱随行就市，建议 3~7 天"),
        ("company", "我方公司抬头", doc["price"].get("company") or "", f["input"], "写进报价单页眉"),
        ("contact", "我方联系人 / 电话", doc["price"].get("contact") or "", f["input"], "写进报价单签署区"),
        ("quote_no", "报价单号", doc["price"].get("quote_no") or C.auto_quote_no(doc["meta"]["inquiry_no"]),
         f["input"], "默认按询盘编号生成，可改"),
        ("ack", "确认声明", "未确认", f["input"], "选择「已确认」表示你确认上面的单价是我方销售价格"),
    ]
    r = 5
    cell_map = {}
    for key, label, val, fmt, hint in rows:
        ws.write(r, 1, label, wb.add_format({"font_name": FONT, "font_size": 10.5, "bold": True,
                                             "font_color": SUB, "border": 1, "border_color": LINE}))
        if key == "single_price":
            # 只有调用方已经通过闸门并显式传入单价时才写入；否则永远留空。
            if C._positive(doc["price"].get("unit_price")):
                ws.write_number(r, 2, float(doc["price"]["unit_price"]), fmt)
            else:
                ws.write_blank(r, 2, None, fmt)
            cell_map[key] = f"$C${r + 1}"
        elif key == "tax":
            v = str(doc["gate"].get("tax_mode", {}).get("value", "") or "")
            if v:
                ws.write(r, 2, v, fmt)
            else:
                ws.write_blank(r, 2, None, fmt)
            cell_map[key] = f"$C${r + 1}"
        elif key == "freight":
            v = str(doc["gate"].get("freight_mode", {}).get("value", "") or "")
            if v:
                ws.write(r, 2, v, fmt)
            else:
                ws.write_blank(r, 2, None, fmt)
            cell_map[key] = f"$C${r + 1}"
        elif key == "ack":
            ws.write(r, 2, "已确认" if str(doc["price"].get("ack", "") or "").strip() else "未确认", fmt)
            cell_map[key] = f"$C${r + 1}"
        else:
            ws.write(r, 2, val, fmt)
            cell_map[key] = f"$C${r + 1}"
        ws.merge_range(r, 4, r, 5, hint, f["input_hint"])
        ws.set_row(r, 24)
        r += 1

    ws.data_validation(5 + 4, 2, 5 + 4, 2, {"validate": "list", "source": C.TAX_OPTIONS})
    ws.data_validation(5 + 5, 2, 5 + 5, 2, {"validate": "list", "source": C.FREIGHT_OPTIONS})
    ws.data_validation(5 + 10, 2, 5 + 10, 2, {"validate": "list", "source": ["未确认", "已确认"]})

    r += 1
    ws.merge_range(r, 1, r, 5, "② 系统只做算术：试算（单价未填时显示「待填单价」）", f["h2"])
    r += 1
    ws.write(r, 1, "计价项目", f["th"])
    ws.write(r, 2, "金额（元）", f["th"])
    ws.merge_range(r, 3, r, 5, "说明", f["th"])
    r += 1
    not_ready = (f'OR({cell_map["single_price"]}="",{cell_map["tax"]}="",'
                 f'{cell_map["freight"]}="")')
    r_net, r_tax, r_total = r, r + 1, r + 2
    ws.write(r, 1, "不含税金额", wb.add_format({"font_name": FONT, "font_size": 10.5, "border": 1, "border_color": LINE}))
    ws.write_formula(r, 2,
                     f'=IF({not_ready},"待填单价",IF(ISNUMBER(SEARCH("不含税",{cell_map["tax"]})),'
                     f'{cell_map["single_price"]}*{cell_map["qty"]},'
                     f'{cell_map["single_price"]}*{cell_map["qty"]}/(1+{cell_map["rate"]})))',
                     f["td_num_b"])
    ws.merge_range(r, 3, r, 5, "数量 × 单价；含税口径时先剥离税额；口径未选时不算", f["note"])
    r += 1
    ws.write(r, 1, "税额", wb.add_format({"font_name": FONT, "font_size": 10.5, "border": 1, "border_color": LINE}))
    ws.write_formula(r, 2, f'=IF({not_ready},"",$C${r_net + 1}*{cell_map["rate"]})', f["td_num"])
    ws.merge_range(r, 3, r, 5, "不含税金额 × 税率", f["note"])
    r += 1
    ws.write(r, 1, "价税合计", wb.add_format({"font_name": FONT, "font_size": 11, "bold": True,
                                              "border": 1, "border_color": LINE, "bg_color": BG_HEAD}))
    ws.write_formula(r, 2, f'=IF({not_ready},"",$C${r_net + 1}+$C${r_tax + 1})',
                     wb.add_format({"font_name": FONT, "font_size": 12, "bold": True, "num_format": "#,##0.00",
                                    "align": "right", "bg_color": BG_HEAD, "border": 1, "border_color": LINE,
                                    "font_color": DEEP}))
    ws.merge_range(r, 3, r, 5, "不含税金额 + 税额", f["note"])

    r += 2
    ws.merge_range(r, 1, r, 5,
                   "红线：系统不提供任何价格建议。单价空着就是空着，报价草稿会一直显示「待你填写」。",
                   f["note"])
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.print_area(0, 0, r, 5)
    return ws, cell_map, (r_net + 1, r_tax + 1, r_total + 1)


# ---------------------------------------------------------------- 工作表 05


def sheet_quote(wb, f, doc, cm, rows_):
    """05 报价草稿：可打印的正式版式，单价/数量全部引用 04 表。"""
    ws = wb.add_worksheet(S5)
    ws.hide_gridlines(2)
    ws.set_tab_color("#123A8A")
    ws.set_column("A:A", 3)
    ws.set_column("B:B", 6)
    ws.set_column("C:C", 22)
    ws.set_column("D:D", 26)
    ws.set_column("E:E", 10)
    ws.set_column("F:F", 7)
    ws.set_column("G:G", 14)
    ws.set_column("H:H", 16)
    ws.set_column("I:I", 22)

    q4 = f"'{S4}'"
    ref_price = f"{q4}!{cm['single_price']}"
    ref_qty = f"{q4}!{cm['qty']}"
    ref_total = f"{q4}!$C${rows_[2]}"
    ready = (f'AND({ref_price}<>"",{q4}!{cm["tax"]}<>"",'
             f'{q4}!{cm["freight"]}<>"")')
    ctx = C.build_context(doc)
    price_confirmed = (C._positive(doc["price"].get("unit_price"))
                       and bool(str(doc["gate"]["tax_mode"].get("value", "") or "").strip())
                       and bool(str(doc["gate"]["freight_mode"].get("value", "") or "").strip()))

    ws.merge_range(1, 1, 1, 8, doc["price"].get("company") or "（我方公司抬头待填写）", f["quote_company"])
    ws.set_row(1, 30)
    ws.merge_range(2, 1, 2, 8, "报 价 单", f["quote_h1"])
    ws.set_row(2, 36)
    demo_tag = " · DEMO 演示价" if "演示" in str(doc["price"].get("ack", "")) else ""
    ws.merge_range(3, 1, 3, 8, f"QUOTATION · 草稿（未经我方销售负责人确认不得对外发送）{demo_tag}", f["quote_meta"])

    ws.write(4, 1, "报价单号", f["quote_meta"])
    ws.merge_range(4, 2, 4, 4, "", f["value_plain"])
    ws.write_formula(4, 2, f"={q4}!{cm['quote_no']}", f["value_plain"])
    ws.write(4, 5, "报价日期", f["quote_meta"])
    ws.write(4, 6, doc["meta"]["as_of"], f["value_plain"])
    ws.write(4, 7, "有效期至", f["quote_meta"])
    ws.write(4, 8, ctx["valid_until"], f["value_plain"])
    ws.set_row(4, 22)

    ws.write(5, 1, "致（客户）", f["quote_meta"])
    _cc = doc["meta"].get("customer") or "待客户确认"
    _tag = []
    if doc["fields"]["customer"].get("status") in ("tbc", "missing"):
        _tag.append("开票全称待客户确认")
    if doc["meta"].get("customer_contact"):
        _tag.append(doc["meta"]["customer_contact"])
    if _tag:
        _cc += f"（{'；'.join(_tag)}）"
    ws.merge_range(5, 2, 5, 5, _cc, f["value_plain"])
    ws.write(5, 6, "我方联系人", f["quote_meta"])
    ws.merge_range(5, 7, 5, 8, doc["price"].get("contact") or "—", f["value_plain"])
    ws.set_row(5, 22)

    heads = ["序号", "产品名称", "规格 / 牌号", "数量", "单位", "单价（元）", "金额（元）", "备注"]
    for i, h in enumerate(heads):
        ws.write(7, 1 + i, h, f["quote_th"])
    ws.set_row(7, 26)

    ws.write(8, 1, 1, f["quote_cell_c"])
    ws.write(8, 2, doc["fields"]["product"]["value"] or "待客户确认", f["quote_cell"])
    ws.write(8, 3, doc["fields"]["grade"]["value"] or "待客户确认", f["quote_cell"])
    ws.write_formula(8, 4, f"={ref_qty}", f["quote_cell_r"])
    ws.write_formula(8, 5, f"={q4}!{cm['unit']}", f["quote_cell_c"])
    ws.write_formula(8, 6, f'=IF({ready},{ref_price},"待填单价")', f["quote_cell_r"])
    ws.write_formula(8, 7, f'=IF({ready},{ref_price}*{ref_qty},"待填单价")', f["quote_cell_r"])
    ws.write(8, 8, "见条款一、二", f["quote_cell"])
    ws.set_row(8, row_height(doc["fields"]["grade"]["value"] or "待客户确认", 30, base=34, max_h=96))

    ws.merge_range(9, 1, 9, 6, "合计（价税合计，元）", f["quote_total_l"])
    ws.write_formula(9, 7, f'=IF({ready},{ref_total},"待填单价")', f["quote_total_r"])
    ws.write(9, 8, "", f["quote_total_r"])
    ws.set_row(9, 26)

    ws.merge_range(11, 1, 11, 8,
                   f'="价格口径："&{q4}!{cm["tax"]}&"；"&{q4}!{cm["freight"]}&"；"'
                   f'&"数量口径："&"{doc["fields"]["quantity"]["value"] or "待客户确认"}"',
                   f["quote_cell"])
    ws.set_row(11, 34)

    if price_confirmed:
        price_clause = [
            f"1. 税费口径：{ctx['tax_mode']}（税率 {ctx['totals']['rate']*100:.0f}%）。",
            f"2. 运费口径：{ctx['freight_mode']}。",
            f"3. 单价为{'含税' if ctx['totals']['taxed'] else '不含税'}单价；"
            f"对应不含税金额 {C.money(ctx['totals']['net'])} 元、税额 {C.money(ctx['totals']['tax'])} 元。",
        ]
    else:
        price_clause = [
            "1. 税费口径：待我方确认（税率待口径确定后计算）。",
            "2. 运费口径：待我方确认（到厂价含运费 / 出厂价不含运费）。",
            "3. 单价与价税构成：待我方填写单价并选择税费/运费口径后自动计算；本页不预置任何价格。",
        ]
    sections = [
        ("一、价格与口径", price_clause),
        ("二、数量与执行口径", [
            f"1. 询盘口径：{doc['fields']['quantity']['value'] or '待客户确认'}。",
            f"2. 本报价按 {C.money(ctx['totals']['qty'])} 吨计价；正式合同以双方书面确认数量为准，超出部分按本合同单价另行确认。",
        ]),
        ("三、交付条件", [
            f"1. 交货地点：{ctx['place']}。",
            f"2. 运输方式：{ctx['incoterm']}；交期：{ctx['delivery_date']}。",
            f"3. 包装：{ctx['packaging']}。",
        ]),
        ("四、付款条件", [f"1. {ctx['payment']}"]),
        ("五、质量与验收", [
            f"1. 质量指标：按 {ctx['grade']} 执行，随货提供批批 COA。",
            "2. 验收：到货后按双方确认的指标验收；异议应在收货后 7 个工作日内书面提出。",
        ]),
        ("六、报价有效期", [
            f"1. 本报价自 {ctx['quote_date']} 起 {ctx['valid_days']} 天内有效（至 {ctx['valid_until']}）。",
            "2. 逾期未确认需重新确认价格与交期；原材料大幅波动时我方有权提前书面通知调整。",
        ]),
        ("七、待客户确认事项", [f"{i}. {x}" for i, x in enumerate(ctx["pending"], 1)] or ["1. 无"]),
        ("八、备注", [
            "1. 本报价为草稿，须经我方销售负责人审阅后发出。",
            "2. 单价与口径由我方业务人员填写并确认；系统未生成、未推荐、未调整任何商业价格。",
        ] + ([f"3. {doc['meta']['case_disclaimer'].rstrip('。')}。"]
             if doc["meta"].get("case_disclaimer") else [])),
    ]
    r = 13
    for title, items in sections:
        ws.merge_range(r, 1, r, 8, title, f["quote_section"])
        ws.set_row(r, 22)
        r += 1
        for it in items:
            ws.merge_range(r, 2, r, 8, it, f["quote_cell"])
            ws.set_row(r, row_height(it, 78, base=20, max_h=76))
            r += 1
        r += 1

    ws.merge_range(r, 1, r, 4, "供方（盖章）：", f["quote_sign"])
    ws.merge_range(r, 5, r, 8, "需方（盖章）：", f["quote_sign"])
    r += 2
    ws.merge_range(r, 1, r, 4, "日期：　　年　　月　　日", f["quote_sign"])
    ws.merge_range(r, 5, r, 8, "日期：　　年　　月　　日", f["quote_sign"])
    r += 2
    ws.merge_range(r, 1, r, 8,
                   "生成说明：本页单价/数量/金额引用「04 价格与口径」；系统不生成商业价格，只做算术与排版。",
                   f["note"])
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.print_area(0, 0, r, 8)
    return ws


# ---------------------------------------------------------------- 工作表 06/07


def sheet_rules(wb, f, doc):
    ws = wb.add_worksheet(S6)
    ws.hide_gridlines(2)
    ws.set_tab_color("#7C8AA1")
    ws.set_column("A:A", 3)
    ws.set_column("B:B", 18)
    ws.set_column("C:C", 24)
    ws.set_column("D:D", 24)
    ws.set_column("E:E", 44)
    ws.set_column("F:F", 3)

    ws.merge_range("B2:E2", "口径与边界 · 对外发送前请业务负责人过一遍", f["title"])
    ws.set_row(1, 34)
    blocks = [
        ("字段口径", [
            ("产品 / 规格", "只收客户原话", "重质/轻质、纯度、粒度必须来自询盘；没有就标待客户确认",
             "行业惯例不能替代客户指定"),
            ("数量", "区分试单量与月用量", "试单量决定首单价，月用量决定是否长约",
             "把月用量写进首单价会做亏"),
            ("税费口径", "由我方选择后生效", "含税 13% 专票 / 不含税 / 普票",
             "纯碱内贸普遍 13% 专票，但对小规模客户可能不同"),
            ("运费口径", "到厂价 vs 出厂价", "到厂价含运费至指定厂区；出厂价不含",
             "纯碱运距长，运费口径错一个字就差几十元/吨"),
        ]),
        ("两类分桶", [
            ("必须补充（A 类）", "缺了不能报价", "产品、规格、数量、交货地点、客户抬头、单价、税费、运费",
             "不清完，报价草稿按钮不成立"),
            ("可先按假设（B 类）", "先出草稿，标注假设", "包装、交期、付款条件、运输方式、有效期",
             "报价中必须写「我方假设 · 待客户确认」"),
        ]),
        ("三条红线", [
            ("不生成价格", "单价只能由人填", "系统无默认价、参考价、区间价、建议价",
             "单价空 = 报价草稿显示待填单价"),
            ("不猜缺失字段", "抽不到就留空", "不用行业惯例、不用同类客户数据补齐",
             "缺失项黄色高亮，标注待客户确认"),
            ("不擅自改口径", "口径以我方填写为准", "税/运费口径由业务选择，脚本与界面不改写",
             "改口径必须由人操作，留痕在报价单"),
        ]),
        ("复核要点", [
            ("数量口径", "试单/月用量", "报价按哪个数量算，必须在报价里写清", "避免客户按量大压价后只提小单"),
            ("有效期", "随行就市", "纯碱价格波动大，建议 3~7 天", "长期锁价需走审批"),
            ("账期", "隐性成本", "付款条件先按我方标准口径报", "报价阶段口头松动账期是常见亏损源"),
        ]),
    ]
    r = 3
    for title, rows_ in blocks:
        ws.merge_range(r, 1, r, 4, title, f["block_title"])
        ws.set_row(r, 24)
        r += 1
        for i, h in enumerate(["项目", "判定口径", "怎么做", "常见坑"]):
            ws.write(r, 1 + i, h, f["th"])
        r += 1
        for a, b, c, d in rows_:
            ws.write(r, 1, a, f["td"])
            ws.write(r, 2, b, f["td"])
            ws.write(r, 3, c, f["td_alt"])
            ws.write(r, 4, d, f["td"])
            ws.set_row(r, 34)
            r += 1
        r += 1

    ws.merge_range(r, 1, r, 4,
                   "本表为规则说明，不参与计算。修改业务口径请同步 SKILL.md 与 references/。", f["note"])
    ws.set_landscape()
    ws.fit_to_pages(1, 0)


def sheet_sources(wb, f, doc):
    ws = wb.add_worksheet(S7)
    ws.hide_gridlines(2)
    ws.set_tab_color("#0F7B3F")
    for i, w in enumerate([8, 22, 26, 12, 46]):
        ws.set_column(i, i, w)

    ws.merge_range(0, 0, 0, 4, "素材与证据 · 每条提取值都能追回原句", f["title"])
    ws.set_row(0, 34)

    r = 2
    for i, h in enumerate(["编号", "类型", "文件", "字数", "用途"]):
        ws.write(r, i, h, f["th"])
    r += 1
    for s in doc["meta"]["sources"]:
        ws.write(r, 0, s["id"], f["td_c"])
        ws.write(r, 1, s["type"], f["td"])
        ws.write(r, 2, s["file"], f["td"])
        ws.write(r, 3, s["chars"], f["td_c"])
        ws.write(r, 4, "字段提取依据", f["td"])
        ws.set_row(r, 22)
        r += 1

    r += 1
    ws.merge_range(r, 0, r, 4, "关键原句（字段 → 出处）", f["h3"])
    r += 1
    for i, h in enumerate(["字段", "提取值", "素材", "置信度", "原句"]):
        ws.write(r, i, h, f["th"])
    r += 1
    for key in C.FIELD_KEYS:
        row = doc["fields"][key]
        if not row["source"]:
            continue
        ws.write(r, 0, row["label"], f["td_c"])
        ws.write(r, 1, row["value"], f["td"])
        src = row["source"].split(" · ")
        ws.write(r, 2, src[0] if src else "", f["td_c"])
        ws.write(r, 3, row["confidence"] or "—", f["td_c"])
        ws.write(r, 4, src[1] if len(src) > 1 else row["source"], f["note"])
        ws.set_row(r, row_height(src[1] if len(src) > 1 else row["source"], 46, base=26, max_h=80))
        r += 1

    if doc["unreadable"]:
        r += 1
        ws.merge_range(r, 0, r, 4, "无法辨认 / 需补录", f["h3"])
        r += 1
        for item in doc["unreadable"]:
            ws.merge_range(r, 0, r, 4, "· " + item, f["badge_miss"])
            ws.set_row(r, 22)
            r += 1

    ws.set_landscape()
    ws.fit_to_pages(1, 0)


# ---------------------------------------------------------------- 入口


def build(doc: dict, out_path: str | Path, quote_md: str | None = None) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(out), {"default_date_format": "yyyy-mm-dd"})
    wb.set_properties({
        "title": "询盘整理与报价草稿",
        "subject": f"{doc['meta'].get('customer') or ''} {doc['fields']['product']['value'] or ''}",
        "author": "inquiry-to-quotation skill",
        "comments": "系统不生成商业价格；单价由用户填写确认。",
    })
    f = make_formats(wb)
    bl = C.blockers(doc)
    sheet_overview(wb, f, doc, bl)
    sheet_fields(wb, f, doc)
    sheet_gaps(wb, f, doc)
    ws4, cm, rows_ = sheet_price(wb, f, doc)
    sheet_quote(wb, f, doc, cm, rows_)
    sheet_rules(wb, f, doc)
    sheet_sources(wb, f, doc)
    wb.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fields.json → 报价工作簿.xlsx")
    ap.add_argument("fields")
    ap.add_argument("-o", "--out", default="报价工作簿.xlsx")
    ap.add_argument("--price", type=float, default=None, help="可选：把已确认单价写进 04 表")
    ap.add_argument("--ack", default=None, help="可选：与 --price 同时给，才写入单价")
    args = ap.parse_args(argv)
    doc = C.load_doc(args.fields)
    if args.price and args.ack:
        doc["price"]["unit_price"] = args.price
        doc["price"]["ack"] = args.ack
    elif args.price:
        print("只给 --price 不给 --ack 时不会写入单价（价格必须确认）。", file=sys.stderr)
    p = build(doc, args.out)
    print(f"← {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
