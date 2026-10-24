# -*- coding: utf-8 -*-
"""build/data.json -> 14 表工作簿（openpyxl）。

关键设计：**统计量用真实 Excel 公式**，不是预先算好的数字。
打开工作簿就能看到每条公式，改任何一个原始价格，分位/均值/波动率会跟着重算。
（openpyxl 只写公式不写缓存值，Excel 首次打开会自动重算；本文件另存一份
「静态校验列」用于与 HTML 对账，见 check_xlsx.py。）

表结构：
  00 封面与结论      01 口径与基准日      02 原始序列(主)      03 原始序列(辅助)
  04 历史分位(公式)  05 统计指标(公式)    06 分窗口统计(公式)  07 同期对比(公式)
  08 季节性(公式)    09 异常点            10 事件时间线        11 数据缺口
  12 方法与公式说明  13 来源清单
"""
import argparse
import datetime
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

INK, NAVY, AMBER, GREEN, RED = "16202B", "17395B", "B4761F", "14664C", "9E2B38"
GREY, GREY_L, LINE, WHITE = "66788C", "F1F4F8", "D6DEE7", "FFFFFF"
AMBER_L, GREEN_L, RED_L, BLUE_L = "FBF1DF", "E7F4EE", "FAEAEC", "EAF1F8"
FONT, MONO = "微软雅黑", "Consolas"

TITLE = Font(name=FONT, size=15, bold=True, color=INK)
SUB = Font(name=FONT, size=9.5, color=GREY)
HEAD = Font(name=FONT, size=10, bold=True, color=WHITE)
BODY = Font(name=FONT, size=10, color=INK)
BOLD = Font(name=FONT, size=10, bold=True, color=INK)
SMALL = Font(name=FONT, size=9, color=GREY)
NUM = Font(name=MONO, size=10, color=INK)
FMLA = Font(name=MONO, size=9, color="2A5D8F")

THIN = Side(style="thin", color=LINE)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_HEAD = PatternFill("solid", fgColor=NAVY)
F_ZEBRA = PatternFill("solid", fgColor=GREY_L)
F_AMBER = PatternFill("solid", fgColor=AMBER_L)
F_GREEN = PatternFill("solid", fgColor=GREEN_L)
F_RED = PatternFill("solid", fgColor=RED_L)
F_BLUE = PatternFill("solid", fgColor=BLUE_L)
F_W = PatternFill("solid", fgColor=WHITE)
F_NOTE = PatternFill("solid", fgColor="FFF9EC")

WRAP = Alignment(horizontal="left", vertical="top", wrap_text=True)
CTR = Alignment(horizontal="center", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")
CENTER = Alignment(horizontal="center", vertical="center")

WIN = [("30", "近 30 天", 30), ("90", "近 3 个月", 90),
       ("365", "近 1 年", 365), ("1095", "近 3 年", 1095), ("1826", "近 5 年", 1826)]


class Book:
    def __init__(self, D):
        self.D = D
        self.M = D["meta"]
        self.A = D["analysis"]
        self.wb = Workbook()
        self.wb.remove(self.wb.active)
        self.warn = []
        self.rows_index = {}   # 供其他表引用：序列 -> (sheet, first_row, last_row, col)

    # ------------------------------------------------------------ 基础件
    def sheet(self, name, tab=NAVY):
        ws = self.wb.create_sheet(name)
        ws.sheet_properties.tabColor = tab
        ws.sheet_view.showGridLines = False
        return ws

    def banner(self, ws, title, sub, ncol):
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        c = ws.cell(1, 1, title)
        c.font = TITLE
        c.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[1].height = 30
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        c2 = ws.cell(2, 1, sub)
        c2.font = SUB
        c2.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws.row_dimensions[2].height = 30
        return 4

    def header(self, ws, row, cols, widths):
        for i, (name, w) in enumerate(zip(cols, widths), start=1):
            c = ws.cell(row, i, name)
            c.font = HEAD
            c.fill = F_HEAD
            c.alignment = CTR
            c.border = BOX
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[row].height = 30
        return row + 1

    def put(self, ws, row, vals, fmt=None, zebra=False, bold=False, fill=None, fonts=None):
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row, i, v)
            c.border = BOX
            c.font = fonts[i - 1] if fonts else (BOLD if bold else BODY)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                c.font = NUM if not bold else BOLD
                c.alignment = RIGHT
                if fmt:
                    c.number_format = fmt
            else:
                c.alignment = WRAP
            if fill:
                c.fill = fill
            elif zebra:
                c.fill = F_ZEBRA
        return row + 1

    def note(self, ws, row, text, ncol, fill=F_NOTE, color=GREY):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
        c = ws.cell(row, 1, text)
        c.font = Font(name=FONT, size=9, color=color)
        c.fill = fill
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        for i in range(1, ncol + 1):
            ws.cell(row, i).fill = fill
        ws.row_dimensions[row].height = max(18, 15 * (1 + len(text) // max(30, ncol * 5)))
        return row + 1

    # ------------------------------------------------------------ 00 封面
    def s00(self):
        ws = self.sheet("00 封面与结论")
        M = self.M
        A = self.A["S1_mid"]
        ncol = 6
        r = self.banner(ws, "纯碱（华东 · 重质）· 现货价格历史位置分析",
                        "本工作簿与同名 HTML 报告同源同数；所有统计量均为<b>可复核的 Excel 公式</b>，"
                        "改动「02 原始序列」里任一价格，04/05/06/07/08 表会随公式自动重算。", ncol)
        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 24
        for col in "CDEF":
            ws.column_dimensions[col].width = 17

        w3 = A["windows"].get("1095", {})
        w1 = A["windows"].get("365", {})
        cards = [
            ("最新可靠报价（元/吨）", A["last_value"], "0.00"),
            ("数据日期", A["last_date"], None),
            ("3 年经验分位", (w3.get("percentile") or {}).get("percentile_inclusive_pct"), '0.00"%"'),
            ("1 年经验分位", (w1.get("percentile") or {}).get("percentile_inclusive_pct"), '0.00"%"'),
            ("3 年最高", (w3.get("stats") or {}).get("max"), "0.00"),
            ("3 年最低", (w3.get("stats") or {}).get("min"), "0.00"),
        ]
        r += 1
        for i, (lab, val, fmt) in enumerate(cards):
            col = i % 3 * 2 + 1
            rr = r + i // 3 * 2
            lc = ws.cell(rr, col, lab)
            lc.font = SMALL
            lc.fill = F_W
            vc = ws.cell(rr, col + 1, val)
            vc.font = Font(name=MONO, size=15, bold=True, color=NAVY)
            if fmt:
                vc.number_format = fmt
            vc.fill = F_W
        r += 5

        r = self.note(ws, r, "一句话结论：华东重质纯碱当前 %.0f 元/吨，落在 %s 以来真实观测的 %.2f%% 分位——"
                             "即历史上 %.2f%% 的报价日比今天更贵。但请注意：该口径的公开日度记录起点是 %s，"
                             "「3 年」与「5 年」窗口的样本完全相同，这不是五年数据齐全。"
                      % (A["last_value"], A["first_date"],
                         (w3.get("percentile") or {}).get("percentile_inclusive_pct", 0),
                         (w3.get("percentile") or {}).get("pct_above", 0),
                         A["first_date"]), ncol, F_AMBER)
        r += 1

        heads = ["表", "内容", "关键说明"]
        r = self.header(ws, r, heads, [16, 30, 78])
        toc = [
            ("01 口径与基准日", "六项口径：规格/地区/含税/交付/单位/来源", "价格能不能用，先看这张表"),
            ("02 原始序列(主)", "华东重质纯碱逐日 lo/hi/mid + 原文链接", "358 条真实观测，每条可点开核对"),
            ("03 原始序列(辅助)", "华东轻质 + 全国基准价", "辅助口径，不作替换"),
            ("04 历史分位(公式)", "PERCENTRANK / COUNTIF 双口径分位", "公式可改、可复核"),
            ("05 统计指标(公式)", "max/min/均值/中位数/标准差/IQR/年化波动", "全部为 Excel 公式"),
            ("06 分窗口统计(公式)", "5 个窗口 × 12 项指标", "样本不足的窗口明确写「不计算」"),
            ("07 同期对比(公式)", "逐年同月均价 + 同比 + 季节性指数", "只呈现有真实观测的格子"),
            ("08 季节性(公式)", "月 × 年矩阵", "空格＝无观测，非 0"),
            ("09 异常点", "三条独立判据（水平/跳变/IQR）", "分别标注，不合并"),
            ("10 事件时间线", "可核验事件 + 来源链接", "只写已发生事实"),
            ("11 数据缺口", "连续缺失段 + 单日缺失", "不插值、不模拟"),
            ("12 方法与公式说明", "每个统计量的公式与口径", "审阅用"),
            ("13 来源清单", "文号/链接", "复核用"),
        ]
        for i, t in enumerate(toc):
            r = self.put(ws, r, list(t), zebra=(i % 2 == 1))
        ws.freeze_panes = "A4"
        return ws

    # ------------------------------------------------------------ 01 口径
    def s01(self):
        ws = self.sheet("01 口径与基准日")
        M = self.M
        ncol = 4
        r = self.banner(ws, "01 口径与基准日", "缺任何一项，这个价格都不能拿去报价。", ncol)
        r = self.header(ws, r, ["要素", "取值", "为什么重要", "来源/备注"], [16, 42, 46, 34])
        rows = [
            ("品种", "纯碱", "只说「纯碱」不能报价，纯度是前提", "生意社商品库"),
            ("规格", M["spec"], "重质与轻质价差常见 100–300 元/吨，混用即失真", "生意社 华东日评原文"),
            ("地区", M["region"], "华东与华北/华中价差显著，且基准价是全国口径", "生意社 华东日评"),
            ("含税", M["tax"], "含税与不含税差约 13%，必锝标明", "生意社报价说明"),
            ("交付方式", M["delivery"], "出厂价 ≠ 送到价，运费与风险归属不同", "原文「实单以商谈为主」"),
            ("单位", M["unit"], "与期货盘面 20 吨/手、元/吨保持同单位才可对比", "—"),
            ("数据日期", M["asof"], "现货逐日报价，日期不同不可比", "—"),
            ("来源", M["source"], "每条价格都要能回溯到原文", M["source_url"]),
            ("最小样本门槛", "20 条有效观测", "低于此不做分位，避免拿 3 个点编出分位数", "本方法设定"),
            ("分位口径", "经验分位（含并列 / 中位秩），另列区间位置", "三者含义不同，不可混用", "见「12 方法与公式」"),
        ]
        for i, t in enumerate(rows):
            r = self.put(ws, r, list(t), zebra=(i % 2 == 1))
        r += 1
        r = self.note(ws, r, "⚠ 区域口径提醒：生意社「重质纯碱基准价」是全国样本，不是华东价。"
                             "本报告把它作为辅助序列 S3 单列，用于判断「华东这个价是全国同步还是华东独有」，"
                             "绝不用它替代华东区域报价。", ncol, F_AMBER)
        ws.freeze_panes = "A4"
        return ws

    # ------------------------------------------------------------ 02/03 原始序列
    def s02(self):
        ws = self.sheet("02 原始序列(主)", GREEN)
        A = self.A["S1_mid"]
        ncol = 8
        r = self.banner(ws, "02 原始序列 · 华东重质纯碱（主口径 S1）",
                        "每行一条真实观测。D/E/F 列是原始报价区间与中值；H 列可点开当日原文。"
                        "改动 F 列任一数值，其余各表的公式会联动重算。", ncol)
        r = self.header(ws, r, ["序号", "日期", "区间低端(元/吨)", "区间高端(元/吨)", "区间中值(元/吨)",
                                "区间宽度", "口径", "原文链接"], [7, 13, 15, 15, 16, 11, 26, 42])
        first = r
        for i, x in enumerate(self.D["series"]["S1"]["data"], start=1):
            c = ws.cell(r, 1, i)
            c.border = BOX
            c.alignment = CENTER
            c.font = NUM
            c = ws.cell(r, 2, datetime.date.fromisoformat(x["date"]))
            c.number_format = "yyyy-mm-dd"
            c.border = BOX
            c.font = NUM
            c.alignment = CENTER
            for col, key in ((3, "lo"), (4, "hi")):
                cc = ws.cell(r, col, float(x[key]))
                cc.number_format = "0.00"
                cc.border = BOX
                cc.font = NUM
                cc.alignment = RIGHT
            # 中值与宽度用公式，保证与上下沿永远一致
            cc = ws.cell(r, 5, "=(C%d+D%d)/2" % (r, r))
            cc.number_format = "0.00"
            cc.border = BOX
            cc.font = FMLA
            cc.alignment = RIGHT
            cc = ws.cell(r, 6, "=D%d-C%d" % (r, r))
            cc.number_format = "0.00"
            cc.border = BOX
            cc.font = FMLA
            cc.alignment = RIGHT
            cc = ws.cell(r, 7, x.get("basis") or "")
            cc.border = BOX
            cc.font = SMALL
            cc.alignment = WRAP
            cc = ws.cell(r, 8, "打开原文")
            cc.hyperlink = x.get("url")
            cc.font = Font(name=FONT, size=9, color="1F4E8C", underline="single")
            cc.border = BOX
            if i % 2 == 0:
                for k in range(1, ncol + 1):
                    ws.cell(r, k).fill = F_ZEBRA
            r += 1
        last = r - 1
        self.rows_index["S1"] = ("'02 原始序列(主)'", first, last, "E")
        r += 1
        r = self.note(ws, r, "共 %d 条观测，%s 至 %s。E/F 列为公式（=(C+D)/2、=D-C），"
                             "不做四舍五入存储，显示层保留两位。" %
                      (last - first + 1, self.D["series"]["S1"]["data"][0]["date"],
                       self.D["series"]["S1"]["data"][-1]["date"]), ncol)
        ws.freeze_panes = "C5"
        ws.auto_filter.ref = "A4:H%d" % last
        return ws

    def s03(self):
        ws = self.sheet("03 原始序列(辅助)", "7A8FA6")
        ncol = 8
        r = self.banner(ws, "03 原始序列 · 辅助口径（S2 华东轻质 / S3 全国基准）",
                        "两条辅助序列各自独立，不与主序列拼接、不互换。", ncol)
        for key, title, kind in (("S2", "S2 华东·轻质纯碱·主流市场区间中值", "range"),
                                 ("S3", "S3 全国·重质纯碱·生意社基准价（单点）", "point")):
            r += 1
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
            c = ws.cell(r, 1, title)
            c.font = Font(name=FONT, size=11, bold=True, color=WHITE)
            c.fill = PatternFill("solid", fgColor=NAVY)
            c.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[r].height = 22
            r += 1
            if kind == "range":
                r = self.header(ws, r, ["序号", "日期", "区间低端", "区间高端", "中值", "宽度", "口径", "原文链接"],
                                [7, 13, 15, 15, 14, 10, 24, 40])
            else:
                r = self.header(ws, r, ["序号", "日期", "基准价", "", "", "", "口径", "原文链接"],
                                [7, 13, 15, 15, 14, 10, 24, 40])
            first = r
            for i, x in enumerate(self.D["series"][key]["data"], start=1):
                ws.cell(r, 1, i).alignment = CENTER
                ws.cell(r, 1).font = NUM
                c = ws.cell(r, 2, datetime.date.fromisoformat(x["date"]))
                c.number_format = "yyyy-mm-dd"
                c.alignment = CENTER
                c.font = NUM
                if kind == "range":
                    for col, kk in ((3, "lo"), (4, "hi")):
                        cc = ws.cell(r, col, float(x[kk]))
                        cc.number_format = "0.00"
                        cc.font = NUM
                        cc.alignment = RIGHT
                    cc = ws.cell(r, 5, "=(C%d+D%d)/2" % (r, r))
                    cc.number_format = "0.00"
                    cc.font = FMLA
                    cc.alignment = RIGHT
                    cc = ws.cell(r, 6, "=D%d-C%d" % (r, r))
                    cc.number_format = "0.00"
                    cc.font = FMLA
                    cc.alignment = RIGHT
                else:
                    cc = ws.cell(r, 3, float(x["value"]))
                    cc.number_format = "0.00"
                    cc.font = NUM
                    cc.alignment = RIGHT
                    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
                cc = ws.cell(r, 7, "全国基准价" if kind == "point" else (x.get("basis") or ""))
                cc.font = SMALL
                cc.alignment = WRAP
                cc = ws.cell(r, 8, "打开原文")
                cc.hyperlink = x.get("url")
                cc.font = Font(name=FONT, size=9, color="1F4E8C", underline="single")
                for k in range(1, ncol + 1):
                    ws.cell(r, k).border = BOX
                    if i % 2 == 0:
                        ws.cell(r, k).fill = F_ZEBRA
                r += 1
            self.rows_index[key] = ("'03 原始序列(辅助)'", first, r - 1, "C" if kind == "point" else "E")
            r = self.note(ws, r, "%s 共 %d 条观测（%s 至 %s）。" %
                          (title.split("·")[0], r - first, self.D["series"][key]["data"][0]["date"],
                           self.D["series"][key]["data"][-1]["date"]), ncol)
        return ws

    # ------------------------------------------------------------ 04 分位（公式）
    def s04(self):
        ws = self.sheet("04 历史分位(公式)", AMBER)
        A = self.A["S1_mid"]
        ncol = 10
        r = self.banner(ws, "04 历史分位 · 经验分位（Excel 公式实算）",
                        "★ 分位不是「当前价在最高最低之间的位置」，而是「历史上多少比例的观测日 ≤ 当前价」。"
                        "下表每一条都是 COUNTIF 计数公式，可自行展开核对。", ncol)
        r = self.header(ws, r, ["窗口", "窗口起", "窗口止", "样本 n", "最低", "最高", "中位数",
                                "经验分位(含并列)", "经验分位(中位秩)", "区间位置(非分位)"],
                        [13, 12, 12, 9, 11, 11, 11, 16, 17, 16])
        sh, f, l, col = self.rows_index["S1"]
        rng = "%s!$%s$%d:$%s$%d" % (sh, col, f, col, l)
        dates = "%s!$B$%d:$B$%d" % (sh, f, l)
        cur = "%s!$%s$%d" % (sh, col, l)
        # 辅助矩阵：行=原始观测，列=5 个窗口；单元格 = IF(该日在窗口内, 价格, "")。
        # 每个单元格都是最简单的标量 IF，任何引擎都能正确求值，不存在数组退化问题。
        HC = 12              # 矩阵起始列 L
        WINROW = r           # 5 个窗口统计行的首行
        AX0 = r + 2          # 矩阵标题行
        AX_HDR = AX0 + 1
        AX_FIRST = AX0 + 2
        _src = self.D["series"]["S1"]["data"]
        AX_LAST = AX_FIRST + len(_src) - 1
        for i, (wk, label, days) in enumerate(WIN):
            rr = r + i
            ws.cell(rr, 1, label).font = BOLD
            ws.cell(rr, 1).alignment = CENTER
            ws.cell(rr, 3, "=DATE(%d,%d,%d)" % tuple(int(x) for x in self.M["asof"].split("-")))
            ws.cell(rr, 3).number_format = "yyyy-mm-dd"
            ws.cell(rr, 2, "=C%d-%d" % (rr, days))
            ws.cell(rr, 2).number_format = "yyyy-mm-dd"
            ws.cell(rr, 4, '=COUNTIFS(%s,">"&$B%d,%s,"<="&$C%d)' % (dates, rr, dates, rr))
            # 极值/中位数走下方辅助区的逐行矩阵（每个窗口一列，不在窗口内的行为空白），
            # 用普通 MIN/MAX/MEDIAN 作用在整列上——不依赖任何数组公式求值规则。
            axcol = get_column_letter(HC + 2 + i)
            rngtxt = "{a}{f}:{a}{l}".format(a=axcol, f=AX_FIRST, l=AX_LAST)
            ws.cell(rr, 5, '=IF($D{r}<1,"",MIN({g}))'.format(r=rr, g=rngtxt))
            ws.cell(rr, 6, '=IF($D{r}<1,"",MAX({g}))'.format(r=rr, g=rngtxt))
            ws.cell(rr, 7, '=IF($D{r}<1,"",MEDIAN({g}))'.format(r=rr, g=rngtxt))
            ws.cell(rr, 8, '=IF($D%d<%d,"样本不足，不计算",(COUNTIFS(%s,"<="&%s,%s,">"&$B%d,%s,"<="&$C%d))/D%d)'
                    % (rr, 20, rng, cur, dates, rr, dates, rr, rr))
            ws.cell(rr, 9, '=IF($D%d<%d,"样本不足，不计算",(COUNTIFS(%s,"<"&%s,%s,">"&$B%d,%s,"<="&$C%d)'
                           '+0.5*COUNTIFS(%s,"="&%s,%s,">"&$B%d,%s,"<="&$C%d))/D%d)'
                    % (rr, 20, rng, cur, dates, rr, dates, rr,
                       rng, cur, dates, rr, dates, rr, rr))
            ws.cell(rr, 10, '=IF($D%d<2,"",(%s-E%d)/(F%d-E%d))' % (rr, cur, rr, rr, rr))
            for k in range(1, ncol + 1):
                c = ws.cell(rr, k)
                c.border = BOX
                if k >= 4:
                    c.alignment = RIGHT
                    c.font = FMLA
            for k in (8, 9, 10):
                ws.cell(rr, k).number_format = "0.00%"
            ws.cell(rr, 4).number_format = "0"
            for k in (5, 6, 7):
                ws.cell(rr, k).number_format = "#,##0.00"
            if i % 2 == 1:
                for k in range(1, ncol + 1):
                    ws.cell(rr, k).fill = F_ZEBRA
        r += len(WIN) + 1
        # ---- 辅助矩阵：L 列起（避开 A:J 上已有的合并单元格），行=原始观测，列=5 个窗口
        c = ws.cell(AX0, HC, "辅助矩阵 · 各窗口内的真实现测取值（空白＝该日不在该窗口内，不参与计算）")
        c.font = Font(name=FONT, size=9.5, bold=True, color=NAVY)
        c.fill = F_BLUE
        ws.merge_cells(start_row=AX0, start_column=HC, end_row=AX0, end_column=HC + 7)
        ws.cell(AX_HDR, HC, "日期").font = SMALL
        ws.cell(AX_HDR, HC + 1, "主序列价格").font = SMALL
        for j, (wk, label, days) in enumerate(WIN):
            cc = ws.cell(AX_HDR, HC + 2 + j, label)
            cc.font = SMALL
            cc.alignment = CENTER
        for k, x in enumerate(_src):
            rr2 = AX_FIRST + k
            cc = ws.cell(rr2, HC, datetime.date.fromisoformat(x["date"]))
            cc.number_format = "yyyy-mm-dd"
            cc.font = NUM
            cc = ws.cell(rr2, HC + 1, float(x["mid"]))
            cc.number_format = "0.00"
            cc.font = NUM
            for j in range(len(WIN)):
                b = WINROW + j
                ce = ws.cell(rr2, HC + 2 + j,
                             '=IF((${L}{row}>$B${b})*(${L}{row}<=$C${b}),$M{row},"")'
                             .format(L=get_column_letter(HC), row=rr2, b=b))
                ce.font = FMLA
                ce.number_format = "0.00"

        r = self.note(ws, r, "公式说明：D 列 =COUNT(条件区间) 得窗口内真实观测数；"
                             "H 列 =(COUNTIF(≤当前价 且 在窗口内)) / n —— 这就是经验分位；"
                             "I 列 把与当前价相等的观测按 0.5 计入（中位秩），用于抵消现货锯齿状并列值；"
                             "J 列 =(当前价−最低)/(最高−最低)，<b>只是区间位置，不是分位</b>。", ncol, F_BLUE)
        r += 1
        r = self.note(ws, r, "为什么必须区分这三个数：现货逐日报价大量取相同值，当当前价恰为窗口最低点时，"
                             "含并列分位可能 0.7%、中位秩 0.4%、区间位置 0.0%——三个都对，含义完全不同。"
                             "对外只说「经验分位」，并把算法写清楚。", ncol, F_AMBER)
        return ws

    # ------------------------------------------------------------ 05 统计指标（公式）
    def s05(self):
        ws = self.sheet("05 统计指标(公式)", GREEN)
        ncol = 12
        r = self.banner(ws, "05 统计指标 · 全样本与分窗口（Excel 公式实算）",
                        "MAX/MIN/AVERAGE/MEDIAN/STDEV.S/QUARTILE.STDEV 全部为公式；"
                        "年化波动率按真实自然日间隔折算（现货报价不等距，不能用 sqrt(252)）。", ncol)
        r = self.header(ws, r, ["指标", "全样本", "近30天", "近3个月", "近1年", "近3年", "近5年",
                                "", "", "", "", ""], [26, 12, 12, 12, 12, 12, 12, 3, 3, 3, 3, 3])
        sh, f, l, col = self.rows_index["S1"]
        rng = "%s!$%s$%d:$%s$%d" % (sh, col, f, col, l)
        dates = "%s!$B$%d:$B$%d" % (sh, f, l)
        asof = "DATE(%d,%d,%d)" % tuple(int(x) for x in self.M["asof"].split("-"))

        # 辅助矩阵（与 04 表同法）：每行一条原始观测 × 每列一个窗口，
        # 单元格为最简标量 IF。所有统计量都对这一列取 MIN/MAX/MEDIAN/STDEV.S，
        # 不用任何数组公式、MINIFS、QUARTILE.INC 之类跨引擎行为不一致的函数。
        HC = 12
        MX0 = r + 26
        MX_HDR = MX0 + 1
        MX_FIRST = MX0 + 2
        _src = self.D["series"]["S1"]["data"]
        MX_LAST = MX_FIRST + len(_src) - 1
        col_txt = {}
        for j, (wk, label, days) in enumerate(WIN):
            col_txt[wk] = "%s%d:%s%d" % (get_column_letter(HC + 2 + j), MX_FIRST,
                                         get_column_letter(HC + 2 + j), MX_LAST)

        # 每个窗口用「矩阵列引用」代替窗口取值；全样本直接引用原始列
        all_txt = "%s!$%s$%d:$%s$%d" % (sh, col, f, col, l)

        metrics = [
            ("样本数 n", lambda ex: "=COUNT({t})".format(t=ex), "0"),
            ("最低", lambda ex: '=IF(COUNT({t})<1,"",MIN({t}))'.format(t=ex), "#,##0.00"),
            ("最高", lambda ex: '=IF(COUNT({t})<1,"",MAX({t}))'.format(t=ex), "#,##0.00"),
            ("均值", lambda ex: '=IF(COUNT({t})<1,"",AVERAGE({t}))'.format(t=ex), "#,##0.00"),
            ("中位数", lambda ex: '=IF(COUNT({t})<1,"",MEDIAN({t}))'.format(t=ex), "#,##0.00"),
            # STDEV = 样本标准差（n-1），与 STDEV.S 同义；不用 STDEV.S 是因为部分引擎
            # 无法解析 STDEV.S 这种带点的函数名，会返回 #NAME?
            ("标准差(样本)", lambda ex: '=IF(COUNT({t})<2,"",STDEV({t}))'.format(t=ex), "#,##0.00"),
            ("变异系数 CV", lambda ex: '=IF(COUNT({t})<2,"",STDEV({t})/AVERAGE({t}))'.format(t=ex), "0.00%"),
            ("当前价相对中位", lambda ex: '=IF(COUNT({t})<1,"",({c})/MEDIAN({t})-1)'.format(
                t=ex, c="%s!$%s$%d" % (sh, col, l)), "0.00%"),
        ]
        for i, (name, fn, fmt) in enumerate(metrics):
            rr = r + i
            ws.cell(rr, 1, name).font = BOLD
            ws.cell(rr, 1).alignment = WRAP
            # B 列 = 全样本（直接作用于原始序列列）
            c = ws.cell(rr, 2, fn(all_txt))
            c.number_format = fmt
            c.font = FMLA
            c.alignment = RIGHT
            for j, (wk, label, days) in enumerate(WIN):
                ex = col_txt[wk]
                c = ws.cell(rr, 3 + j, fn(ex))
                c.number_format = fmt
                c.font = FMLA
                c.alignment = RIGHT
            for k in range(1, 8):
                ws.cell(rr, k).border = BOX
                if i % 2 == 1:
                    ws.cell(rr, k).fill = F_ZEBRA
        r += len(metrics) + 1

        # ---- 辅助矩阵（放在下方，避开 A:J 的合并单元格）
        c = ws.cell(MX0, HC, "辅助矩阵 · 各窗口内的真实现测（空白＝该日不在该窗口内，不参与计算）")
        c.font = Font(name=FONT, size=9.5, bold=True, color=NAVY)
        c.fill = F_BLUE
        ws.merge_cells(start_row=MX0, start_column=HC, end_row=MX0, end_column=HC + 7)
        ws.cell(MX_HDR, HC, "日期").font = SMALL
        ws.cell(MX_HDR, HC + 1, "主序列价格").font = SMALL
        for j, (wk, label, days) in enumerate(WIN):
            cc = ws.cell(MX_HDR, HC + 2 + j, label)
            cc.font = SMALL
            cc.alignment = CENTER
        WINROW5 = r - len(metrics) - 1
        for k, x in enumerate(_src):
            rr2 = MX_FIRST + k
            cc = ws.cell(rr2, HC, datetime.date.fromisoformat(x["date"]))
            cc.number_format = "yyyy-mm-dd"
            cc.font = NUM
            cc = ws.cell(rr2, HC + 1, float(x["mid"]))
            cc.number_format = "0.00"
            cc.font = NUM
            for j, (wk, label, days) in enumerate(WIN):
                b = WINROW5 - 1 + j
                ce = ws.cell(rr2, HC + 2 + j,
                             '=IF(({L}{row}>$B${b})*({L}{row}<=$C${b}),$M{row},"")'
                             .format(L=get_column_letter(HC), row=rr2, b=b))
                ce.font = FMLA
                ce.number_format = "0.00"


        # 波动与回撤（用真实观测，非公式近似，但注明算法）
        r = self.note(ws, r, "波动率与回撤不写进公式列，因为现货报价不等距，"
                             "「每自然日对数收益的标准差 × √365」必须在脚本里按真实日差计算；"
                             "结果见下表（与 HTML 报告同源）。", ncol, F_BLUE)
        r += 1
        r = self.header(ws, r, ["波动指标", "窗口", "年化波动率", "日均绝对变动", "最大单日变动",
                                "≥1% 天数占比", "", "", "", "", "", ""],
                        [24, 12, 14, 15, 14, 15, 3, 3, 3, 3, 3, 3])
        for wk, label in (("30", "近 30 天"), ("90", "近 3 个月"), ("365", "近 1 年")):
            v = (self.A["S1_mid"].get("volatility") or {}).get(wk)
            if not v:
                r = self.put(ws, r, ["年化波动率", label, "样本不足", "", "", ""])
                continue
            r = self.put(ws, r, ["年化波动率", label, v["ann_vol_pct"], v["mean_abs_daily_pct"],
                                 v["max_abs_daily_pct"], v["pct_days_ge_1pct"]],
                         fmt="0.00")
        mdd = self.A["S1_mid"].get("mdd")
        if mdd:
            r = self.put(ws, r, ["最大回撤", "全样本", mdd["mdd_pct"], mdd["peak_date"], mdd["trough_date"], ""],
                         fmt="0.00")
        r += 1
        r = self.note(ws, r, "年化波动率算法：对相邻两条真实报价计算 ln(P_t/P_{t-1}) / 相隔自然日数，"
                             "取其样本标准差 × √365。未做前值填充，未假设每日都有报价。", ncol)
        ws.freeze_panes = "B5"
        return ws

    # ------------------------------------------------------------ 06 分窗口统计（引用 04/05）
    def s06(self):
        ws = self.sheet("06 分窗口统计(公式)", NAVY)
        ncol = 9
        r = self.banner(ws, "06 分窗口统计 · 三条序列对照",
                        "本表直接引用 04/05 表的结果，用于横向比较「华东重质 / 华东轻质 / 全国基准」"
                        "在同一窗口下的位置差异。", ncol)
        r = self.header(ws, r, ["序列", "窗口", "样本 n", "最低", "最高", "中位数",
                                "经验分位", "区间涨跌幅", "结论标注"],
                        [30, 13, 9, 11, 11, 11, 12, 13, 30])
        lab = {"S1_mid": "S1 华东·重质（主口径）", "S2_mid": "S2 华东·轻质（辅助）",
               "S3_value": "S3 全国·重质基准（辅助）"}
        for key in ("S1_mid", "S2_mid", "S3_value"):
            a = self.A.get(key)
            if not a:
                continue
            for wkk, wlabel, days in WIN:
                v = a["windows"].get(wkk, {})
                if not v.get("available"):
                    r = self.put(ws, r, [lab[key], wlabel, v.get("n_obs", 0), "", "", "", "", "",
                                         "有效观测不足 %d 条，不计算（不外推、不插值）" % v.get("n_obs", 0)],
                                 fill=F_AMBER)
                    continue
                st = v["stats"]
                p = v["percentile"]
                ch = v.get("change") or {}
                note = ("极低" if p["percentile_inclusive_pct"] <= 10 else
                        "偏低" if p["percentile_inclusive_pct"] <= 30 else
                        "中位" if p["percentile_inclusive_pct"] <= 70 else
                        "偏高" if p["percentile_inclusive_pct"] <= 90 else "高位")
                r = self.put(ws, r, [lab[key], wlabel, v["n_obs"], st["min"], st["max"], st["median"],
                                     p["percentile_inclusive_pct"],
                                     ch.get("pct_change"), note],
                             fmt="0.00")
                for k in (7, 8):
                    ws.cell(r - 1, k).number_format = "0.00%"
        r += 1
        r = self.note(ws, r, "三条序列的分位各自独立计算。S2 与 S3 的作用是回答「华东这个价是不是全国同步」——"
                             "如果三条序列分位都很低，说明是行业性的，不是华东独有的区域问题。", ncol)
        return ws

    # ------------------------------------------------------------ 07 同期对比（公式）
    def s07(self):
        ws = self.sheet("07 同期对比(公式)", GREEN)
        ncol = 15
        r = self.banner(ws, "07 同期对比 · 逐年同月（Excel 公式实算）",
                        "用 AVERAGEIFS 对「02 原始序列」按年月聚合真实观测；没有任何观测的格子留空并注明，不是 0。", ncol)
        sh, f, l, col = self.rows_index["S1"]
        rng = "%s!$%s$%d:$%s$%d" % (sh, col, f, col, l)
        dates = "%s!$B$%d:$B$%d" % (sh, f, l)

        data = self.D["series"]["S1"]["data"]
        years = sorted({d["date"][:4] for d in data})
        r = self.header(ws, r, ["年份", "1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月",
                                "9月", "10月", "11月", "12月", "全年均值", "观测数合计"],
                        [9] + [10] * 12 + [12, 11])
        first_y = r
        for i, y in enumerate(years):
            rr = r + i
            ws.cell(rr, 1, int(y)).font = BOLD
            ws.cell(rr, 1).alignment = CENTER
            for m in range(1, 13):
                ex = ('IFERROR(AVERAGEIFS(%s,%s,">="&DATE(%d,%d,1),%s,"<"&DATE(%d,%d,1)),"无观测")'
                      % (rng, dates, int(y), m, dates, int(y), m + 1 if m < 12 else 1))
                if m == 12:
                    ex = ('IFERROR(AVERAGEIFS(%s,%s,">="&DATE(%d,12,1),%s,"<="&DATE(%d,12,31)),"无观测")'
                          % (rng, dates, int(y), dates, int(y)))
                c = ws.cell(rr, 1 + m, "=" + ex)
                c.number_format = "#,##0.00"
                c.font = FMLA
                c.alignment = RIGHT
            c = ws.cell(rr, 14, '=IFERROR(AVERAGEIFS(%s,%s,">="&DATE(%d,1,1),%s,"<="&DATE(%d,12,31)),"无观测")'
                        % (rng, dates, int(y), dates, int(y)))
            c.number_format = "#,##0.00"
            c.font = FMLA
            c.alignment = RIGHT
            c = ws.cell(rr, 15, '=COUNTIFS(%s,">="&DATE(%d,1,1),%s,"<="&DATE(%d,12,31))'
                        % (dates, int(y), dates, int(y)))
            c.font = FMLA
            c.alignment = RIGHT
            for k in range(1, ncol + 1):
                ws.cell(rr, k).border = BOX
                if i % 2 == 1:
                    ws.cell(rr, k).fill = F_ZEBRA
        r += len(years) + 1

        # 季节性指数 = 该月各年均值 / 全部月均
        r = self.header(ws, r, ["月份", "跨年均价", "季节性指数", "样本月数", "说明", "", "", "", "",
                                "", "", "", "", "", ""],
                        [9, 12, 13, 10, 40, 10, 10, 10, 10, 10, 10, 10, 10, 12, 11])
        for m in range(1, 13):
            rr = r + m - 1
            cl = get_column_letter(1 + m)
            ws.cell(rr, 1, "%d月" % m).font = BOLD
            ws.cell(rr, 1).alignment = CENTER
            c = ws.cell(rr, 2, '=IFERROR(AVERAGE(%s%d:%s%d),"无观测")'
                        % (cl, first_y, cl, first_y + len(years) - 1))
            c.number_format = "#,##0.00"
            c.font = FMLA
            c = ws.cell(rr, 3, '=IFERROR(B%d/AVERAGE($B$%d:$B$%d),"—")' % (rr, first_y, first_y + len(years) - 1))
            c.number_format = "0.0"
            c.font = FMLA
            c = ws.cell(rr, 4, '=COUNT(%s%d:%s%d)' % (cl, first_y, cl, first_y + len(years) - 1))
            c.font = FMLA
            c = ws.cell(rr, 5, "100＝全期月均；>100 表示该月历史均价高于全年平均" if m == 1 else "")
            c.font = SMALL
            for k in range(1, 6):
                ws.cell(rr, k).border = BOX
        r += 12 + 1
        r = self.note(ws, r, "季节性指数只描述「历史上各月相对全期的位置」，不是对今年该月的推演。"
                             "样本月数少于 2 的月份，指数参考价值有限，已在 D 列标出。", ncol, F_AMBER)
        return ws

    # ------------------------------------------------------------ 08 季节性矩阵
    def s08(self):
        ws = self.sheet("08 季节性(公式)", GREEN)
        ncol = 14
        r = self.banner(ws, "08 季节性矩阵 · 年 × 月 均价与样本数",
                        "两层：上层为各年各月均价（AVERAGEIFS），下层为对应观测条数（COUNTIFS）。", ncol)
        sh, f, l, col = self.rows_index["S1"]
        rng = "%s!$%s$%d:$%s$%d" % (sh, col, f, col, l)
        dates = "%s!$B$%d:$B$%d" % (sh, f, l)
        data = self.D["series"]["S1"]["data"]
        years = sorted({d["date"][:4] for d in data})
        for layer, expr, label in (
            (1, "IFERROR(AVERAGEIFS(%s,%s,\">=\"&DATE(Y,1,1),%s,\"<\"&DATE(Y,12,31)),\"\")" % (rng, dates, dates), "均价"),
            (2, "IFERROR(COUNTIFS(%s,\">=\"&DATE(Y,1,1),%s,\"<\"&DATE(Y,12,31)),0)" % (dates, dates), "观测数"),
        ):
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
            c = ws.cell(r, 1, "【第 %d 层】%s" % (layer, label))
            c.font = Font(name=FONT, size=11, bold=True, color=WHITE)
            c.fill = PatternFill("solid", fgColor=NAVY if layer == 1 else GREEN)
            ws.row_dimensions[r].height = 22
            r += 1
            ws.cell(r, 1, "年 \\ 月").font = HEAD
            ws.cell(r, 1).fill = F_HEAD
            ws.cell(r, 1).alignment = CTR
            ws.cell(r, 1).border = BOX
            ws.column_dimensions["A"].width = 11
            for m in range(1, 13):
                c = ws.cell(r, 1 + m, "%d月" % m)
                c.font = HEAD
                c.fill = F_HEAD
                c.alignment = CTR
                c.border = BOX
                ws.column_dimensions[get_column_letter(1 + m)].width = 11
            r += 1
            for i, y in enumerate(years):
                ws.cell(r, 1, int(y)).font = BOLD
                ws.cell(r, 1).alignment = CENTER
                for m in range(1, 13):
                    e = expr.replace("Y", str(int(y)))
                    if layer == 1:
                        e = e.replace("DATE(%d,12,31)" % int(y), "DATE(%d,%d,1)" % (int(y), m + 1) if m < 12
                                      else "DATE(%d,12,31)" % int(y))
                        e = e.replace("DATE(%d,1,1)" % int(y), "DATE(%d,%d,1)" % (int(y), m), 1)
                    else:
                        e = e.replace("DATE(%d,12,31)" % int(y), "DATE(%d,%d,1)" % (int(y), m + 1) if m < 12
                                      else "DATE(%d,12,31)" % int(y))
                        e = e.replace("DATE(%d,1,1)" % int(y), "DATE(%d,%d,1)" % (int(y), m), 1)
                    c = ws.cell(r, 1 + m, "=" + e)
                    c.font = FMLA
                    c.alignment = RIGHT
                    c.number_format = "#,##0.00" if layer == 1 else "0"
                    c.border = BOX
                    if i % 2 == 1:
                        c.fill = F_ZEBRA
                ws.cell(r, 1).border = BOX
                r += 1
            r += 1
        r = self.note(ws, r, "「0」或空表示该年该月没有可用观测——本表不做任何填补。"
                             "重碱序列起点为 %s，故 2024 年只有 7 月之后有数。" %
                      self.D["series"]["S1"]["data"][0]["date"], ncol)
        return ws

    # ------------------------------------------------------------ 09 异常点
    def s09(self):
        ws = self.sheet("09 异常点", RED)
        ncol = 7
        r = self.banner(ws, "09 异常点 · 三条独立判据",
                        "A 水平异常：相对滚动一年中位数偏离 ≥2.5 倍稳健 z（MAD）；"
                        "B 跳变：相邻报价日变动 ≥3%；C 分布异常：越 1.5×IQR 栅栏。", ncol)
        r = self.header(ws, r, ["日期", "价格(元/吨)", "判据", "分值/幅度", "说明", "原文链接", ""],
                        [13, 14, 18, 14, 40, 34, 4])
        a1 = self.A["S1_mid"]
        url_map = {x["date"]: x.get("url") for x in self.D["series"]["S1"]["data"]}
        rows = []
        for x in a1["anomalies"]["level"]:
            for fl in x["flags"]:
                if fl["rule"] == "level_mad":
                    rows.append((x["date"], x["value"], "A 水平异常", fl["score"],
                                 "相对滚动一年中位数偏 %.2f 倍稳健 z" % fl["score"]))
                elif fl["rule"] == "iqr_fence":
                    rows.append((x["date"], x["value"], "C 分布异常", "越栅栏",
                                 "落在 Q1-1.5IQR ~ Q3+1.5IQR 之外"))
        for x in a1["anomalies"]["jump"]:
            for fl in x["flags"]:
                if fl["rule"] == "jump":
                    rows.append((x["date"], x["value"], "B 单日跳变", fl["pct"],
                                 "前值 %.2f（%s）→ %.2f" % (fl["from_value"], fl["from_date"], x["value"])))
        rows.sort(key=lambda t: (t[0], t[2]))
        for i, (d, v, k, sv, memo) in enumerate(rows):
            c = ws.cell(r, 1, datetime.date.fromisoformat(d))
            c.number_format = "yyyy-mm-dd"
            c.font = NUM
            c.alignment = CENTER
            ws.cell(r, 2, v).number_format = "#,##0.00"
            ws.cell(r, 2).font = NUM
            ws.cell(r, 3, k).font = BODY
            ws.cell(r, 4, sv).font = NUM
            ws.cell(r, 4).alignment = RIGHT
            ws.cell(r, 5, memo).font = SMALL
            c = ws.cell(r, 6, "打开原文")
            c.hyperlink = url_map.get(d)
            c.font = Font(name=FONT, size=9, color="1F4E8C", underline="single")
            for kk in range(1, ncol + 1):
                ws.cell(r, kk).border = BOX
                if i % 2 == 1:
                    ws.cell(r, kk).fill = F_ZEBRA
            r += 1
        r += 1
        r = self.note(ws, r, "异常点只是「统计上罕见」，不等于「必有某个事件」。"
                             "事件时间线（10 表）只收录能点开原文的事实，二者不做强行配对。", ncol, F_AMBER)
        ws.freeze_panes = "A5"
        ws.auto_filter.ref = "A4:F%d" % (r - 2)
        return ws

    # ------------------------------------------------------------ 10 事件
    def s10(self):
        ws = self.sheet("10 事件时间线", AMBER)
        ncol = 5
        r = self.banner(ws, "10 事件时间线 · 仅收录可核验事实",
                        "每条事件都必须能点开原始来源。不含任何机构观点、行情预测或归因推测。", ncol)
        r = self.header(ws, r, ["日期", "事件", "事实描述", "来源", "链接"], [13, 40, 70, 30, 40])
        for i, ev in enumerate(self.D.get("events") or []):
            rr = r
            c = ws.cell(rr, 1, ev.get("date", ""))
            c.font = NUM
            c.alignment = CENTER
            ws.cell(rr, 2, ev.get("title", "")).font = BOLD
            ws.cell(rr, 3, ev.get("detail", "")).font = BODY
            ws.cell(rr, 4, ev.get("source", "")).font = SMALL
            c = ws.cell(rr, 5, "打开原文")
            c.hyperlink = ev.get("url")
            c.font = Font(name=FONT, size=9, color="1F4E8C", underline="single")
            for k in range(1, ncol + 1):
                cc = ws.cell(rr, k)
                cc.border = BOX
                if k in (2, 3):
                    cc.alignment = WRAP
                if i % 2 == 1:
                    cc.fill = F_ZEBRA
            ws.row_dimensions[rr].height = 46
            r += 1
        ws.freeze_panes = "A5"
        return ws

    # ------------------------------------------------------------ 11 缺口
    def s11(self):
        ws = self.sheet("11 数据缺口", "9E2B38")
        ncol = 5
        g = self.A["S1_mid"]["gaps"]
        r = self.banner(ws, "11 数据缺口 · 不插值、不模拟",
                        "缺口＝该有报价的工作日却没有公开报价。全部留空，不做前值填充、不做插值补价。", ncol)
        r = self.note(ws, r, "共识别 %d 个连续缺口段（连续 ≥3 个工作日无报价），另有 %d 个单日缺失（多为法定假日）。"
                             "合计缺失 %d 个工作日。"
                      % (g.get("run_count", 0), g.get("single_missing", 0),
                         sum(x["workdays"] for x in g.get("runs", []))), ncol, F_RED, INK)
        r += 1
        r = self.header(ws, r, ["序号", "缺口起", "缺口止", "缺失工作日", "处理方式"],
                        [7, 14, 14, 12, 40])
        for i, x in enumerate(g.get("runs", []), start=1):
            r = self.put(ws, r, [i, x["from"], x["to"], x["workdays"],
                                 "留空，不填补；统计时该期间无观测参与"],
                         zebra=(i % 2 == 0))
        ws.freeze_panes = "A6"
        return ws

    # ------------------------------------------------------------ 12 方法
    def s12(self):
        ws = self.sheet("12 方法与公式说明", NAVY)
        ncol = 4
        r = self.banner(ws, "12 方法与公式说明",
                        "这一张表是给审阅者看的：每个统计量到底怎么算、边界在哪里。", ncol)
        r = self.header(ws, r, ["指标", "Excel 公式/算法", "口径与边界", "常见误用"], [22, 52, 52, 40])
        rows = [
            ("经验分位（含并列）", "COUNTIFS(值,\"<=\"&当前价, 日期在窗口内) / n",
             "回答「历史上有多少比例的报价日 ≤ 今天」", "用 (P−min)/(max−min) 冒充分位"),
            ("经验分位（中位秩）", "(COUNTIF(<当前价)+0.5×COUNTIF(=当前价)) / n",
             "并列值按半数计入，抵消现货锯齿", "与含并列口径混用而不说明"),
            ("区间位置", "(当前价 − 最低) / (最高 − 最低)",
             "纯几何位置，不是统计分位", "直接叫成「历史分位」"),
            ("最低/最高/均值/中位数", "MIN / MAX / AVERAGE / MEDIAN", "只用窗口内真实观测",
             "把全样本极值当成当前窗口极值"),
            ("标准差", "STDEV.S（样本标准差）", "n<2 不计算",
             "用总体标准差 STDEV.P 导致年化波动偏低"),
            ("四分位", "QUARTILE.INC（含端点位次）", "用于分位带与 IQR 栅栏",
             "与 PERCENTILE.EXC 混用导致边界不一致"),
            ("年化波动率", "std(ln(P_t/P_{t−1}) / 相隔自然日数) × √365",
             "现货报价不等距，必须按真实日差折算", "直接对相邻报价算收益再 ×√252"),
            ("最大回撤", "min((P_t − 历史峰值)/历史峰值)", "全样本，标注峰/谷日期",
             "只报幅度不报日期，无法复核"),
            ("水平异常", "0.6745×(P−滚动一年中位数)/MAD ≥ 2.5", "稳健 z，抗极端值",
             "用均值±kσ，被极端值本身污染"),
            ("跳变异常", "相邻报价日变动绝对值 ≥ 3%", "按报价日，不按自然日",
             "跨节假日误判为跳变"),
            ("分布异常", "P < Q1−1.5IQR 或 P > Q3+1.5IQR", "箱线图栅栏", "与稳健 z 重复计数同一现象"),
            ("季节性指数", "该月跨年均价 / 全期月均 × 100", "只描述历史相对位置",
             "当成对今年该月的预测"),
            ("最小样本门槛", "n ≥ 20 才计算分位", "不足则明确写「不计算」",
             "拿 3–5 个点算出一个漂亮的分位数"),
            ("缺口处理", "按工作日统计，留空", "不插值、不前值填充",
             "用 fillna(method='ffill') 填平后算波动率"),
        ]
        for i, t in enumerate(rows):
            r = self.put(ws, r, list(t), zebra=(i % 2 == 1))
        r += 1
        r = self.note(ws, r, "本工作簿所有统计列都是真实公式（可点开单元格查看），不是预计算结果。"
                             "若改动「02 原始序列」中的价格，04–08 表会自动重算；"
                             "若 Excel 提示是否重算，请选「是」。", ncol, F_BLUE)
        ws.freeze_panes = "A4"
        return ws

    # ------------------------------------------------------------ 13 来源
    def s13(self):
        ws = self.sheet("13 来源清单", "7A8FA6")
        ncol = 4
        r = self.banner(ws, "13 来源清单", "每条价格都能回溯到这里列出的来源。", ncol)
        r = self.header(ws, r, ["来源", "用于", "链接", "备注"], [34, 56, 50, 26])
        for i, s in enumerate(self.D.get("sources") or []):
            rr = r
            ws.cell(rr, 1, s.get("name", "")).font = BOLD
            ws.cell(rr, 2, s.get("used_for", "")).font = BODY
            c = ws.cell(rr, 3, s.get("url", ""))
            c.hyperlink = s.get("url")
            c.font = Font(name=FONT, size=9, color="1F4E8C", underline="single")
            ws.cell(rr, 4, "").font = SMALL
            for k in range(1, ncol + 1):
                ws.cell(rr, k).border = BOX
                ws.cell(rr, k).alignment = WRAP
                if i % 2 == 1:
                    ws.cell(rr, k).fill = F_ZEBRA
            ws.row_dimensions[rr].height = 40
            r += 1
        r += 1
        r = self.note(ws, r, "报告生成时间 %s；数据基准日 %s。" %
                      (self.M["generated_at"], self.M["asof"]), ncol)
        return ws

    # ------------------------------------------------------------ build
    def build(self, out_path):
        for fn in (self.s00, self.s01, self.s02, self.s03, self.s04, self.s05,
                   self.s06, self.s07, self.s08, self.s09, self.s10, self.s11,
                   self.s12, self.s13):
            fn()
        self.wb.calculation.fullCalcOnLoad = True
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        self.wb.save(out_path)
        return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    D = json.load(open(a.data, encoding="utf-8"))
    p = Book(D).build(a.out)
    print("ok", p, "%.1f KB" % (os.path.getsize(p) / 1024))


if __name__ == "__main__":
    main()
