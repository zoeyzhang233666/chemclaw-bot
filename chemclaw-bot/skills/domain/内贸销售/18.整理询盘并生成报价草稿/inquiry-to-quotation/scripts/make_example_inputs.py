# -*- coding: utf-8 -*-
"""生成纯碱案例的可上传素材（微信截图、邮件 .eml、需求表 XLSX/PDF）。

这个脚本只服务 examples/example-1-soda-ash-glass/，用于让案例可复现：
    python scripts/make_example_inputs.py

它不会生成任何价格建议。比价截图里的 1?30 是故意做脏的数据，用来演示"不猜"。
"""
from __future__ import annotations

import base64
import json
import math
import os
import sys
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "example-1-soda-ash-glass"
INPUT = EX / "input"
INPUT.mkdir(parents=True, exist_ok=True)

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_HAND = r"C:\Windows\Fonts\simhei.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """按像素宽度折行，兼容中文无空格。"""
    lines: list[str] = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        buf = ""
        for ch in para:
            if draw.textlength(buf + ch, font=fnt) <= max_w:
                buf += ch
            else:
                if buf:
                    lines.append(buf)
                buf = ch
        if buf:
            lines.append(buf)
    return lines or [""]


def bubble(draw, box, fill, radius=20, outline=None):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)


def avatar(draw, x, y, text="华"):
    draw.rounded_rectangle([x, y, x + 84, y + 84], radius=10, fill="#5B7FA6")
    f = font(38, True)
    tw = draw.textlength(text, font=f)
    draw.text((x + 42 - tw / 2, y + 16), text, font=f, fill="white")


def make_wechat(path: Path) -> None:
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), "#ededed")
    d = ImageDraw.Draw(img)

    # 状态栏
    f_status = font(22)
    d.text((34, 16), "15:24", font=f_status, fill="#1a1a1a")
    d.text((905, 16), "5G", font=font(20, True), fill="#1a1a1a")
    # 电池
    d.rounded_rectangle([960, 18, 1040, 42], radius=5, outline="#1a1a1a", width=2)
    d.rectangle([965, 23, 1032, 37], fill="#1a1a1a")
    d.rectangle([1042, 26, 1046, 34], fill="#1a1a1a")

    # 顶栏
    d.rectangle([0, 56, W, 156], fill="#ededed")
    d.line([0, 156, W, 156], fill="#d8d8d8", width=1)
    # 返回箭头
    d.line([36, 96, 58, 106], fill="#1a1a1a", width=4)
    d.line([36, 116, 58, 106], fill="#1a1a1a", width=4)
    # 标题
    title = "华宇玻璃 · 王经理"
    ft = font(34, True)
    tw = d.textlength(title, font=ft)
    d.text(((W - tw) / 2, 78), title, font=ft, fill="#1a1a1a")
    # 更多
    for i in range(3):
        d.ellipse([1000 + i * 14, 102, 1008 + i * 14, 110], fill="#1a1a1a")

    # 日期
    f_time = font(22)
    t = "10月18日  下午 3:24"
    tw = d.textlength(t, font=f_time)
    d.text(((W - tw) / 2, 180), t, font=f_time, fill="#9b9b9b")

    y = 226
    f_msg = font(30)
    lh = 45
    pad_x, pad_y = 22, 18
    max_text_w = 760

    incoming = [
        "老师您好，我们是盐城华宇玻璃，做浮法线的，想找重质纯碱的长期供应商。",
        "月用量大概 800 吨，先试单 200 吨看看稳定性。",
        "指标要求：Na2CO3 ≥ 99.2%，Fe2O3 ≤ 0.003%，烧失量 ≤ 0.5%，粒度 180 目筛余 ≤ 5%。",
        "送到我们盐城的厂区，吨包就行。",
    ]
    for text in incoming:
        lines = wrap(d, text, f_msg, max_text_w)
        bh = pad_y * 2 + lh * len(lines)
        avatar(d, 28, y + 4)
        bw = max(d.textlength(ln, font=f_msg) for ln in lines) + pad_x * 2
        bx0 = 132
        bubble(d, [bx0, y, bx0 + bw, y + bh], "white")
        ty = y + pad_y
        for ln in lines:
            d.text((bx0 + pad_x, ty), ln, font=f_msg, fill="#1a1a1a")
            ty += lh
        y += bh + 22

    # 图片消息：上轮比价记录
    card_w, card_h = 620, 430
    card_x, card_y = 132, y
    # 图片气泡
    bubble(d, [card_x - 10, card_y - 10, card_x + card_w + 10, card_y + card_h + 10], "white")
    d.rectangle([card_x, card_y, card_x + card_w, card_y + card_h], fill="#fbfbfb", outline="#e2e2e2")
    d.rectangle([card_x, card_y, card_x + card_w, card_y + 64], fill="#eef2f8")
    d.text((card_x + 20, card_y + 15), "上轮比价记录（客户手写）", font=font(26, True), fill="#24344d")
    # 表头
    cols = [card_x + 24, card_x + 240, card_x + 400]
    headers = ["供应商", "规格", "送到价"]
    yy = card_y + 86
    for i, h in enumerate(headers):
        d.text((cols[i], yy), h, font=font(23, True), fill="#5b6a82")
    d.line([card_x + 20, yy + 38, card_x + card_w - 20, yy + 38], fill="#d7deea", width=2)
    rows = [("A 厂", "重质纯碱", "1,150 元/吨"), ("B 厂", "重质纯碱", "1,180 元/吨")]
    yy += 54
    for r in rows:
        for i, cell in enumerate(r):
            d.text((cols[i], yy), cell, font=font(24), fill="#1a1a1a")
        d.line([card_x + 20, yy + 44, card_x + card_w - 20, yy + 44], fill="#eceff5", width=1)
        yy += 58
    # 最后一行：手写 + 涂改
    d.text((cols[0], yy), "上次", font=font(24), fill="#1a1a1a")
    d.text((cols[1], yy), "重质纯碱", font=font(24), fill="#1a1a1a")
    d.text((cols[2], yy), "1,?30 元/吨", font=font(26, True), fill="#2b4a8b")
    # 在问号上画一团涂改，制造"读不清"的效果
    d.line([card_x + 416, yy + 10, card_x + 450, yy + 34], fill="#8a8a8a", width=3)
    d.line([card_x + 420, yy + 32, card_x + 454, yy + 8], fill="#8a8a8a", width=3)
    d.text((card_x + 20, card_y + card_h - 44), "注：最后一行单价写得急，字迹不清", font=font(19), fill="#8d99ad")
    avatar(d, 28, card_y + 4)
    y = card_y + card_h + 32

    # 最后一条客户消息
    text = "麻烦报个价，价格有效期也写一下，我们这周要走内部比价。"
    lines = wrap(d, text, f_msg, max_text_w)
    bh = pad_y * 2 + lh * len(lines)
    avatar(d, 28, y + 4)
    bw = max(d.textlength(ln, font=f_msg) for ln in lines) + pad_x * 2
    bubble(d, [132, y, 132 + bw, y + bh], "white")
    ty = y + pad_y
    for ln in lines:
        d.text((132 + pad_x, ty), ln, font=f_msg, fill="#1a1a1a")
        ty += lh
    y += bh + 22

    # 我方回复（绿色）
    text = "好的王经理，我核对下排产和物流给您回。"
    lines = wrap(d, text, f_msg, max_text_w)
    bh = pad_y * 2 + lh * len(lines)
    avatar(d, W - 112, y + 4, "鲁")
    bw = max(d.textlength(ln, font=f_msg) for ln in lines) + pad_x * 2
    bx1 = W - 132
    bubble(d, [bx1 - bw, y, bx1, y + bh], "#95ec69")
    ty = y + pad_y
    for ln in lines:
        d.text((bx1 - bw + pad_x, ty), ln, font=f_msg, fill="#1a1a1a")
        ty += lh
    y += bh + 26

    # 时间
    t = "下午 3:26"
    tw = d.textlength(t, font=f_time)
    d.text(((W - tw) / 2, y), t, font=f_time, fill="#9b9b9b")

    # 底部输入栏
    d.rectangle([0, H - 110, W, H], fill="#f7f7f7")
    d.line([0, H - 110, W, H - 110], fill="#d8d8d8", width=1)
    d.ellipse([28, H - 84, 72, H - 40], outline="#1a1a1a", width=3)
    d.rounded_rectangle([96, H - 88, 840, H - 34], radius=26, fill="white", outline="#e0e0e0")
    d.text((124, H - 78), "输入消息...", font=font(26), fill="#b0b0b0")
    d.ellipse([866, H - 80, 908, H - 38], outline="#1a1a1a", width=3)
    d.ellipse([944, H - 84, 1004, H - 24], outline="#1a1a1a", width=3)
    d.line([958, H - 54, 990, H - 54], fill="#1a1a1a", width=3)
    d.line([974, H - 70, 974, H - 38], fill="#1a1a1a", width=3)

    # 案例水印（避免被误认为真实聊天）
    watermark = "案例演示 · 人物与聊天内容均为虚构"
    fw = font(18)
    tw = d.textlength(watermark, font=fw)
    d.rectangle([(W - tw) / 2 - 12, H - 150, (W + tw) / 2 + 12, H - 118], fill="#e4e4e4")
    d.text(((W - tw) / 2, H - 146), watermark, font=fw, fill="#8b8b8b")

    img.save(path, "PNG", optimize=True)
    print(f"  ← {path}")


def make_email(path: Path) -> None:
    body = """王经理，您好：

附件是我们这边整理的需求，先发您一份文字版，方便报价：

1）产品：重质纯碱，用于浮法玻璃生产线；
2）指标：Na2CO3 ≥ 99.2%，Fe2O3 ≤ 0.003%，烧失量 ≤ 0.5%，粒度 180 目筛余 ≤ 5%；
3）数量：先试单 200 吨，后续月用量约 800 吨，按月度计划滚动下单；
4）包装：1000kg 吨包，栈板 + 缠膜，方便叉车卸货；
5）交货：送到江苏省盐城市亭湖区 华宇玻璃一期厂区，需提前一天预约卸车，厂区有地磅；
6）发票：我们是一般纳税人，需要 13% 增值税专用发票；
7）交期：试单希望 10 月底前到货；
8）付款：请注明贵司常规付款条件，我们走内部比价时一并比较；
9）报价有效期：请一并注明，最近纯碱行情变化较快。

进厂需先提供 COA、MSDS 与相关资质文件（纯碱非危化品，但厂区安环要备案）。
如价格合适，可先安排小批量试供，再签年度框架。

开票抬头我让财务整理好发您，先按我们厂名报即可。

江苏盐城华宇玻璃  采购部
王经理
手机 138****（微信同号）
wangjian@huayuglass.com

---
本邮件为「询盘整理与报价草稿」教学案例素材，公司、人物与交易均为虚构。
"""
    msg = EmailMessage()
    msg["From"] = "王经理 <wangjian@huayuglass.com>"
    msg["To"] = "sales@luyan-chemical.example"
    msg["Subject"] = "重质纯碱询价（华宇玻璃）——补充几点"
    msg["Date"] = format_datetime(datetime(2026, 10, 19, 14, 32, 0))
    msg["Message-ID"] = "<20261019143200.huayu@example.com>"
    msg["X-Case-Note"] = "教学演示，虚构案例"
    msg.set_content(body, charset="utf-8")
    path.write_bytes(msg.as_bytes())
    (path.with_suffix(".txt")).write_text(
        "发件人：王经理 <wangjian@huayuglass.com>\n"
        "收件人：sales@luyan-chemical.example\n"
        "主题：重质纯碱询价（华宇玻璃）——补充几点\n"
        "时间：2026-10-19 14:32\n\n" + body,
        encoding="utf-8",
    )
    print(f"  ← {path}")


def make_requirement_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "需求表"
    ws.sheet_view.showGridLines = False
    widths = {"A": 4, "B": 18, "C": 36, "D": 18, "E": 28}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    deep = "0A2A66"
    accent = "1E56C8"
    line = "DCE4F0"
    soft = "F5F8FE"
    yellow = "FDF0D3"

    ws.merge_cells("B2:E2")
    ws["B2"] = "重质纯碱采购需求表"
    ws["B2"].font = Font(name="微软雅黑", size=20, bold=True, color="FFFFFF")
    ws["B2"].fill = PatternFill("solid", fgColor=deep)
    ws["B2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 40

    ws.merge_cells("B3:E3")
    ws["B3"] = "客户：江苏盐城华宇玻璃（简称）｜ 用途：浮法玻璃生产线 ｜ 日期：2026-10-19"
    ws["B3"].font = Font(name="微软雅黑", size=10, color="C9D8F5")
    ws["B3"].fill = PatternFill("solid", fgColor=deep)
    ws["B3"].alignment = Alignment(horizontal="left", vertical="center", indent=1)

    rows = [
        ("产品", "重质纯碱", "规格", "Na2CO3 ≥ 99.2%；Fe2O3 ≤ 0.003%；烧失量 ≤ 0.5%；180 目筛余 ≤ 5%"),
        ("试单数量", "200 吨", "月用量", "约 800 吨 / 月，按月度计划滚动"),
        ("包装", "1000kg 吨包，栈板 + 缠膜", "运输", "汽运整车，送到厂区"),
        ("交货地点", "江苏省盐城市亭湖区 华宇玻璃一期厂区", "卸货条件", "提前一天预约；厂区有地磅；叉车卸货"),
        ("交期", "试单 10 月底前到货", "发票", "13% 增值税专用发票（一般纳税人）"),
        ("付款条件", "", "报价有效期", ""),
        ("质量文件", "随货 COA；进厂前提供 MSDS 与资质文件", "备注", "纯碱非危化品，厂区安环需备案"),
    ]
    r = 5
    for a, b, c, d in rows:
        ws.cell(r, 2, a).font = Font(name="微软雅黑", size=10, bold=True, color="5B6A82")
        ws.cell(r, 2).fill = PatternFill("solid", fgColor=soft)
        ws.cell(r, 2).alignment = Alignment(vertical="center", wrap_text=True)
        ws.cell(r, 3, b).font = Font(name="微软雅黑", size=10.5, color="101A2C")
        ws.cell(r, 3).alignment = Alignment(vertical="center", wrap_text=True)
        ws.cell(r, 4, c).font = Font(name="微软雅黑", size=10, bold=True, color="5B6A82")
        ws.cell(r, 4).fill = PatternFill("solid", fgColor=soft)
        ws.cell(r, 4).alignment = Alignment(vertical="center", wrap_text=True)
        ws.cell(r, 5, d).font = Font(name="微软雅黑", size=10.5, color="101A2C")
        ws.cell(r, 5).alignment = Alignment(vertical="center", wrap_text=True)
        for col in range(2, 6):
            ws.cell(r, col).border = Border(
                left=Side(style="thin", color=line), right=Side(style="thin", color=line),
                top=Side(style="thin", color=line), bottom=Side(style="thin", color=line),
            )
        # 付款条件、有效期留空 → 黄色输入提示
        if a in ("付款条件", "报价有效期"):
            ws.cell(r, 3).fill = PatternFill("solid", fgColor=yellow)
            ws.cell(r, 5).fill = PatternFill("solid", fgColor=yellow)
            ws.cell(r, 3, "待贵司确认" if a == "付款条件" else "待贵司填写")
            ws.cell(r, 3).font = Font(name="微软雅黑", size=10, italic=True, color="9A5B00")
            ws.cell(r, 5, "请在报价中注明" if a == "付款条件" else "建议 7 天内")
            ws.cell(r, 5).font = Font(name="微软雅黑", size=10, italic=True, color="9A5B00")
        ws.row_dimensions[r].height = 40 if a not in ("交货地点", "质量文件") else 52
        r += 1

    ws.merge_cells(f"B{r+1}:E{r+1}")
    ws[f"B{r+1}"] = "说明：黄色格为客户暂未给出的参数，请勿代填。报价请附 COA 样板与包装照片。"
    ws[f"B{r+1}"].font = Font(name="微软雅黑", size=9, color="8D99AD")
    ws[f"B{r+1}"].alignment = Alignment(wrap_text=True, vertical="center")

    # 比价参考 sheet
    ws2 = wb.create_sheet("比价参考")
    ws2.sheet_view.showGridLines = False
    ws2.column_dimensions["A"].width = 4
    ws2.column_dimensions["B"].width = 18
    ws2.column_dimensions["C"].width = 22
    ws2.column_dimensions["D"].width = 26
    ws2.merge_cells("B2:D2")
    ws2["B2"] = "客户提供的上轮比价记录（OCR 摘录）"
    ws2["B2"].font = Font(name="微软雅黑", size=14, bold=True, color=deep)
    data = [
        ("供应商", "规格", "送到价"),
        ("A 厂", "重质纯碱", "1,150 元/吨"),
        ("B 厂", "重质纯碱", "1,180 元/吨"),
        ("上次", "重质纯碱", "1,?30 元/吨（字迹不清）"),
    ]
    for i, row in enumerate(data, 4):
        for j, val in enumerate(row, 2):
            c = ws2.cell(i, j, val)
            c.border = Border(
                left=Side(style="thin", color=line), right=Side(style="thin", color=line),
                top=Side(style="thin", color=line), bottom=Side(style="thin", color=line),
            )
            c.alignment = Alignment(vertical="center")
            if i == 4:
                c.font = Font(name="微软雅黑", size=10.5, bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor=accent)
            elif i == 7:
                c.font = Font(name="微软雅黑", size=10.5, color="9A5B00")
                c.fill = PatternFill("solid", fgColor=yellow)
            else:
                c.font = Font(name="微软雅黑", size=10.5, color="101A2C")
    ws2.merge_cells("B9:D9")
    ws2["B9"] = "注意：客户比价仅作背景，不得当作我方报价或建议价；1?30 不猜。"
    ws2["B9"].font = Font(name="微软雅黑", size=9, color="B42318")
    ws2["B9"].alignment = Alignment(wrap_text=True, vertical="center")

    wb.save(path)
    print(f"  ← {path}")


def make_requirement_pdf(path: Path) -> None:
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), "#f7f6f2")
    d = ImageDraw.Draw(img)
    # 纸张
    d.rectangle([70, 60, W - 70, H - 60], fill="#fffefb", outline="#ddd8cc", width=2)
    # 标题
    d.text((110, 105), "重质纯碱采购需求表", font=font(42, True), fill="#0a2a66")
    d.line([110, 170, W - 110, 170], fill="#1e56c8", width=4)
    d.text((110, 190), "客户：江苏盐城华宇玻璃（简称）    用途：浮法玻璃生产线", font=font(24), fill="#3b4a63")
    d.text((110, 232), "日期：2026-10-19    联系人：王经理    电话：138****", font=font(24), fill="#3b4a63")

    rows = [
        ("产品", "重质纯碱", "试单数量", "200 吨"),
        ("规格", "Na2CO3 ≥ 99.2%；Fe2O3 ≤ 0.003%；\n烧失量 ≤ 0.5%；180 目筛余 ≤ 5%", "月用量", "约 800 吨 / 月"),
        ("包装", "1000kg 吨包；栈板 + 缠膜", "运输", "汽运整车，送到厂区"),
        ("交货地点", "江苏省盐城市亭湖区\n华宇玻璃一期厂区", "卸货", "提前一天预约；有地磅；叉车卸货"),
        ("交期", "试单 10 月底前到货", "发票", "13% 增值税专用发票"),
        ("付款条件", "（客户未填）", "报价有效期", "（客户未填）"),
        ("质量文件", "随货 COA；进厂前提供 MSDS 与资质", "备注", "纯碱非危化品，厂区安环备案"),
    ]
    y = 300
    for a, b, c, e in rows:
        d.rectangle([110, y, W - 110, y + 130], outline="#cfd8e6", width=1)
        d.line([300, y, 300, y + 130], fill="#cfd8e6", width=1)
        d.line([760, y, 760, y + 130], fill="#cfd8e6", width=1)
        d.rectangle([110, y, 300, y + 130], fill="#eef3fb")
        d.rectangle([760, y, 760 + 180, y + 130], fill="#eef3fb")
        d.text((130, y + 16), a, font=font(24, True), fill="#0a2a66")
        d.text((130, y + 58), c, font=font(24, True), fill="#0a2a66")
        # 值：支持换行
        for idx, line in enumerate(b.split("\n")):
            d.text((320, y + 18 + idx * 38), line, font=font(23), fill="#1a1a1a")
        for idx, line in enumerate(e.split("\n")):
            d.text((780, y + 18 + idx * 38), line, font=font(23), fill="#1a1a1a")
        if a == "付款条件":
            d.text((320, y + 18), "待贵司确认", font=font(23, True), fill="#9a5b00")
        if a == "报价有效期":
            d.text((780, y + 18), "请在报价中注明", font=font(23, True), fill="#9a5b00")
        y += 130

    d.text((110, y + 28), "说明：黄色/留白项为客户暂未给出的参数，请勿代填。报价请附 COA 样板与包装照片。",
           font=font(21), fill="#8d99ad")
    # 手写批注
    d.text((760, y + 78), "10月底前必须到厂", font=font(28, True), fill="#2b4a8b")
    d.line([760, y + 116, 1080, y + 116], fill="#2b4a8b", width=3)
    # 红章
    stamp_x, stamp_y = 880, 1380
    d.ellipse([stamp_x, stamp_y, stamp_x + 220, stamp_y + 220], outline="#c0392b", width=5)
    d.text((stamp_x + 34, stamp_y + 54), "华宇玻璃", font=font(30, True), fill="#c0392b")
    d.text((stamp_x + 34, stamp_y + 104), "采购部", font=font(26, True), fill="#c0392b")
    d.text((stamp_x + 34, stamp_y + 148), "2026-10-19", font=font(20), fill="#c0392b")

    # 扫描质感：轻微斜线/噪点，不覆盖文字
    for i in range(0, W, 7):
        d.line([i, 0, i - 60, H], fill="#f0eee7", width=1)
    # 页脚
    d.text((110, H - 110), "教学案例素材 · 公司、人物与交易均为虚构", font=font(19), fill="#9b9b9b")
    img.save(path, "PDF", resolution=150.0)
    print(f"  ← {path}")


def make_merged(path: Path) -> None:
    text = """# 询盘原文（案例素材，已按素材编号切块）

> 本案例为「整理询盘 → 生成报价草稿」教学演示。客户、联系人、公司、价格均为虚构。

## 素材01 · 微信截图 OCR（2026-10-18 至 10-19）

联系人：华宇玻璃 · 王经理

王经理：老师您好，我们是盐城华宇玻璃，做浮法线的，想找重质纯碱的长期供应商。
王经理：月用量大概 800 吨，先试单 200 吨看看稳定性。
王经理：指标要求：Na2CO3 ≥ 99.2%，Fe2O3 ≤ 0.003%，烧失量 ≤ 0.5%，粒度 180 目筛余 ≤ 5%。
王经理：送到我们盐城的厂区，吨包就行。
王经理：（图片）这是我们上次的比价记录，最后一行单价写得急，是 1?30，你看看能不能做。
王经理：麻烦报个价，价格有效期也写一下，我们这周要走内部比价。
我：好的王经理，我核对下排产和物流给您回。

> OCR 备注：比价表最后一行「1?30」字迹被涂改/遮挡，无法确认是 1,130、1,230 还是 1,630。按规则不猜，列入"无法辨认"。

## 素材02 · 邮件（2026-10-19 14:32）

发件人：wangjian@huayuglass.com
主题：重质纯碱询价（华宇玻璃）——补充几点

您好：

补充几点，方便您报价：

1）交货地点：江苏省盐城市亭湖区 华宇玻璃一期厂区（需提前一天预约卸车，厂区有地磅）。
2）我们是增值税一般纳税人，需要 13% 增值税专用发票。
3）试单希望 10 月底前到货；后续按月度计划滚动下单。
4）包装请用 1000kg 吨包，栈板 + 缠膜，方便叉车卸货。
5）请注明报价有效期与付款条件，走内部比价时这两项要一起报。

进厂需先提供 COA、MSDS 与相关资质文件（纯碱非危化品，但厂区安环要备案）。
如价格合适，可先安排小批量试供，再签年度框架。

开票抬头我让财务整理好发您，先按我们厂名报即可。

江苏盐城华宇玻璃  采购部  王经理
手机 138****（微信同号）

## 素材03 · 客户需求表（Excel / PDF）

产品：重质纯碱
规格：Na2CO3 ≥ 99.2%；Fe2O3 ≤ 0.003%；烧失量 ≤ 0.5%；180 目筛余 ≤ 5%
试单：200 吨；月用量：约 800 吨
包装：1000kg 吨包，栈板 + 缠膜
交货：江苏省盐城市亭湖区 华宇玻璃一期厂区
交期：试单 10 月底前
发票：13% 增值税专用发票
付款条件：（留白）
报价有效期：（留白）
"""
    path.write_text(text, encoding="utf-8")
    print(f"  ← {path}")


def main() -> int:
    make_wechat(INPUT / "微信截图_华宇玻璃.png")
    make_email(INPUT / "询盘邮件_华宇玻璃.eml")
    make_requirement_xlsx(INPUT / "客户需求表_华宇玻璃.xlsx")
    make_requirement_pdf(INPUT / "客户需求表_华宇玻璃_扫描件.pdf")
    make_merged(INPUT / "询盘原文_合并.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
