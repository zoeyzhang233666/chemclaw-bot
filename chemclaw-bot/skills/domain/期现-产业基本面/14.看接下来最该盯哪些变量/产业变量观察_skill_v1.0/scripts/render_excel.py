# -*- coding: utf-8 -*-
"""
通用产业变量观察工作簿 —— Excel 渲染器
输出 8 个 sheet：
  00 封面          —— 品种、周期、口径声明、填写与使用规则
  01 变量观察总表  —— 入选变量的全景表（核心交付，一行一变量）
  02 当前产业状态  —— 价格/库存/开工/需求/成本快照，含口径列
  03 未来事件时间线—— 公开事件，按确定性分级
  04 候选池与筛选  —— 入选/未入选及理由，体现筛选过程
  05 验证条件与触发器—— 确认/否证/失效 + 阈值 + 下次检查
  06 数据缺口登记  —— 不可得指标与替代口径
  07 观察日程      —— 固定查询节奏
所有单元格带来源；缺失值写「数据缺失」而不是留空。
"""
from __future__ import annotations

from datetime import date

from xlsxwriter.utility import xl_col_to_name

from contract import CATEGORIES, CAT_COLOR, NODATA, validate

# 配色（与 HTML 同源）
NAVY = "#1F3352"
BLUE = "#2F6FD0"
LIGHT = "#EEF3FA"
GREY = "#F4F6F9"
LINE = "#C9D3E0"
TXT = "#1E2633"
MUTED = "#5C6B80"
GREEN = "#2FBF8F"
ORANGE = "#E0693A"
AMBER = "#C99427"
PURPLE = "#7C5CD6"

CAT_HEX = {k: v.lstrip("#") for k, v in CAT_COLOR.items()}


def _lighten(hexcolor: str, factor: float = 0.86) -> str:
    """把分类色降饱和，用作分类标签底色。"""
    h = hexcolor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02X}{g:02X}{b:02X}"


def _safe_date(text) -> "date | None":
    """解析日期；模板占位符（如 <<<…>>>）或非法值返回 None，由调用方降级为 NODATA。

    这样 templates/payload_template.py 这类未填写的模板也能顺利生成产物，
    而不必在渲染器里写特判。
    """
    if not text:
        return None
    try:
        return date.fromisoformat(str(text).strip())
    except (ValueError, TypeError):
        return None


def build(payload: dict, out_path: str, validate_first: bool = True) -> str:
    if validate_first:
        probs = validate(payload)
        if probs:
            raise ValueError("payload 不符合契约：\n- " + "\n- ".join(probs))

    import xlsxwriter

    wb = xlsxwriter.Workbook(out_path, {"nan_inf_to_errors": True})
    meta = payload["meta"]

    # ---------- 通用格式 ----------
    F = {}
    F["title"] = wb.add_format({"font_name": "微软雅黑", "font_size": 20, "bold": True,
                                "font_color": "#FFFFFF", "bg_color": NAVY, "valign": "vcenter",
                                "align": "left", "indent": 1})
    F["subtitle"] = wb.add_format({"font_name": "微软雅黑", "font_size": 11, "font_color": "#D6E2F3",
                                   "bg_color": NAVY, "valign": "vcenter", "align": "left", "indent": 1})
    F["h"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "bold": True, "font_color": "#FFFFFF",
                            "bg_color": BLUE, "border": 1, "border_color": LINE, "valign": "vcenter",
                            "align": "center", "text_wrap": True})
    F["cell"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1,
                               "border_color": LINE, "valign": "top", "text_wrap": True, "font_color": TXT})
    F["cell_l"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1,
                                 "border_color": LINE, "valign": "top", "text_wrap": True,
                                 "font_color": TXT, "align": "left"})
    F["cell_grey"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1,
                                    "border_color": LINE, "valign": "top", "text_wrap": True,
                                    "font_color": MUTED, "bg_color": GREY})
    F["bold"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "bold": True, "border": 1,
                               "border_color": LINE, "valign": "top", "text_wrap": True, "font_color": TXT})
    F["center"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1,
                                 "border_color": LINE, "valign": "vcenter", "align": "center", "font_color": TXT})
    F["num"] = wb.add_format({"font_name": "Consolas", "font_size": 10, "border": 1,
                              "border_color": LINE, "valign": "vcenter", "align": "center",
                              "font_color": BLUE, "bold": True})
    F["section"] = wb.add_format({"font_name": "微软雅黑", "font_size": 12, "bold": True,
                                  "font_color": NAVY, "valign": "vcenter", "indent": 1})
    F["note"] = wb.add_format({"font_name": "微软雅黑", "font_size": 9, "font_color": MUTED,
                               "text_wrap": True, "valign": "top", "italic": True})
    F["yes"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1, "border_color": LINE,
                              "valign": "top", "text_wrap": True, "font_color": "#1A7A5E",
                              "bg_color": "#E4F5EE"})
    F["no"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1, "border_color": LINE,
                             "valign": "top", "text_wrap": True, "font_color": "#A3421F",
                             "bg_color": "#FDECE6"})
    F["inv"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1, "border_color": LINE,
                              "valign": "top", "text_wrap": True, "font_color": "#8A6410",
                              "bg_color": "#FCF5E2"})
    F["nodata"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1,
                                 "border_color": LINE, "valign": "top", "text_wrap": True,
                                 "font_color": "#9AA7B8", "bg_color": "#F0F2F5", "italic": True})
    F["date"] = wb.add_format({"font_name": "Consolas", "font_size": 10, "border": 1,
                               "border_color": LINE, "valign": "vcenter", "align": "center",
                               "font_color": TXT, "num_format": "yyyy-mm-dd"})
    F["link"] = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1,
                               "border_color": LINE, "valign": "top", "text_wrap": True,
                               "font_color": BLUE, "underline": 1})

    def cat_fmt(cat: str):
        hexc = CAT_HEX.get(cat, "2F6FD0")
        if cat not in _cat_cache:
            _cat_cache[cat] = wb.add_format({
                "font_name": "微软雅黑", "font_size": 10, "border": 1, "border_color": LINE,
                "valign": "vcenter", "align": "center", "bold": True,
                "font_color": "#" + hexc, "bg_color": _lighten("#" + hexc)})
        return _cat_cache[cat]

    _cat_cache: dict = {}
    # 00 封面
    # =====================================================================
    ws = wb.add_worksheet("00 封面")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.set_column("B:B", 22)
    ws.set_column("C:C", 96)
    ws.set_row(1, 40)
    ws.set_row(2, 22)
    ws.merge_range("B2:C2", f'{meta["commodity"]} · 产业变量观察工作簿', F["title"])
    ws.merge_range("B3:C3", f'关注周期：{meta["cycle"]}　|　数据截止：{payload.get("as_of", meta.get("as_of", ""))}',
                   F["subtitle"])
    ws.set_row(3, 8)

    rows = [
        ("品种", meta["commodity"]),
        ("关注周期", meta["cycle"]),
        ("数据截止", payload.get("as_of", meta.get("as_of", ""))),
        ("合约锚点", meta["contract_focus"]),
        ("重点区域", meta["region_focus"]),
        ("价格/基差口径", meta["price_basis"]),
        ("研究定位", meta["research_position"]),
        ("入选变量数", "%d 个（分类：%s）" % (len(payload["variables"]),
                                          "、".join(sorted({v["cat"] for v in payload["variables"]})))),
        ("候选/入选", "%d / %d" % (len(payload["candidates"]),
                                  len([c for c in payload["candidates"] if c["selected"]]))),
        ("未来已知事件", "%d 个节点" % len(payload["events"])),
        ("明确数据缺口", "%d 项" % len(payload["gaps"])),
        ("工作簿生成日", date.today().isoformat()),
    ]
    r = 4
    for k, v in rows:
        ws.write(r, 1, k, F["bold"])
        ws.write(r, 2, v, F["cell_l"])
        ws.set_row(r, max(20, 15 * (len(str(v)) // 60 + 1)))
        r += 1

    r += 1
    ws.merge_range(r, 1, r, 2, "使用规则（必读）", F["section"])
    r += 1
    rules = [
        "1. 本工作簿是「观察工具」，回答的是「接下来盯什么、什么信号要改判断」，不含方向预测。",
        "2. 任何数值都要带口径：同一指标存在多口径时分行列出，绝不跨口径比较或相减。",
        "3. 无法核实的指标写「数据缺失」并登记在 06 表；不得用估算冒充实测。",
        "4. 事件分三档：已披露·确定时点 / 定期数据（按发布节奏）/ 条件触发（只代表观察窗口，不代表必然发生）。",
        "5. 每个变量的「下次可观测时间」是执行清单的锚点；到期未更新即视为数据滞后，需在备注中标注。",
        "6. 触发「确认 / 否证 / 失效」任一条件时，必须回写 05 表并在 01 表更新结论。",
    ]
    for t in rules:
        ws.merge_range(r, 1, r, 2, t, F["cell_l"])
        ws.set_row(r, 30)
        r += 1

    r += 1
    ws.merge_range(r, 1, r, 2, "工作表导航", F["section"])
    r += 1
    nav = [
        ("01 变量观察总表", "核心交付：入选变量全景（一行一变量）"),
        ("02 当前产业状态", "价格、库存、开工、产量、需求、成本快照"),
        ("03 未来事件时间线", "已公开事件，按确定性分级"),
        ("04 候选池与筛选", "落选项与理由，体现筛选过程"),
        ("05 验证条件与触发器", "确认 / 否证 / 失效的阈值与检查动作"),
        ("06 数据缺口登记", "不可得指标、替代口径与局限"),
        ("07 观察日程", "固定查询节奏与来源"),
    ]
    for i, (a, b) in enumerate(nav, 1):
        ws.write(r, 1, a, F["bold"])
        ws.write(r, 2, b, F["cell_l"])
        r += 1

    r += 1
    ws.merge_range(r, 1, r, 2,
                   "重要声明：本工作簿数据均来自公开发布的行业数据与机构研报（各项已注明来源与日期）。"
                   "标注为「预估 / 估算 / 机构口径」的数值不等同于实测。本文件不构成投资建议。",
                   F["note"])
    ws.set_row(r, 44)

    # =====================================================================
    # 01 变量观察总表（核心）
    # =====================================================================
    ws1 = wb.add_worksheet("01 变量观察总表")
    ws1.freeze_panes(3, 1)
    ws1.set_zoom(85)
    cols1 = [
        ("序号", 6), ("变量名称", 30), ("分类", 8), ("重要性\n(1-5)", 9), ("可验证性\n(1-5)", 10),
        ("紧迫度\n(1-5)", 9), ("观察周期", 16), ("当前状态", 40), ("近期变化", 40),
        ("历史位置", 34), ("为什么值得盯", 44), ("与供需/价格的传导机制", 44),
        ("关键可核对数据", 42), ("确认信号（判断成立）", 34), ("否证信号（判断需修正）", 34),
        ("变量失效/口径失真", 34), ("数据来源", 38), ("更新频率", 20), ("下次可观测", 24),
        ("置信度", 12), ("口径与局限", 34),
    ]
    for i, (name, w) in enumerate(cols1):
        ws1.set_column(i, i, w)
        ws1.set_column(i, i, w)
    ws1.merge_range(0, 0, 0, len(cols1) - 1,
                    f'{meta["commodity"]} · 产业变量观察总表　（{meta["cycle"]}）', F["title"])
    ws1.set_row(0, 32)
    for i, (name, _) in enumerate(cols1):
        ws1.write(2, i, name, F["h"])
    ws1.set_row(2, 42)

    vs = sorted(payload["variables"], key=lambda v: v["rank"])
    r = 3
    for v in vs:
        vals = [
            v["rank"], v["name"], v["cat"], v["importance"], v["verifiability"], v["urgency"],
            v["horizon"], v["current"], v["recent_change"], v["history_pos"], v["why"],
            v["mechanism"], v["key_data"], v["verify_yes"], v["verify_no"], v["invalidate"],
            v["source"], v["freq"], v["next_date"], v["confidence"], v["gap"],
        ]
        for i, val in enumerate(vals):
            if i == 0:
                ws1.write_number(r, i, val, F["num"])
            elif i == 2:
                ws1.write(r, i, val, cat_fmt(val))
            elif i in (3, 4, 5):
                ws1.write_number(r, i, val, F["center"])
            elif i == 1:
                ws1.write(r, i, val, F["bold"])
            elif i == 13:
                ws1.write(r, i, val, F["yes"])
            elif i == 14:
                ws1.write(r, i, val, F["no"])
            elif i == 15:
                ws1.write(r, i, val, F["inv"])
            elif i == 20:
                ws1.write(r, i, val, F["cell_grey"])
            else:
                ws1.write(r, i, val if val else NODATA,
                          F["cell_l"] if val else F["nodata"])
        ws1.set_row(r, 118)
        r += 1

    ws1.autofilter(2, 0, r - 1, len(cols1) - 1)
    ws1.write(r + 1, 1,
              "排序逻辑：重要性×2 + 可验证性 + 紧迫度 降序；rank 为最终观察优先级。"
              "「下次可观测」为执行锚点，到期未更新须标注数据滞后。", F["note"])

    # =====================================================================
    # 02 当前产业状态
    # =====================================================================
    ws2 = wb.add_worksheet("02 当前产业状态")
    ws2.freeze_panes(3, 0)
    ws2.set_column("A:A", 4)
    ws2.set_column("B:B", 32)
    ws2.set_column("C:C", 30)
    ws2.set_column("D:D", 46)
    ws2.set_column("E:E", 40)
    ws2.set_column("F:F", 34)
    ws2.set_column("G:G", 38)
    ws2.merge_range("A1:G1", "当前产业状态核对表（价格 / 库存 / 开工 / 产量 / 需求 / 成本）", F["title"])
    ws2.set_row(0, 30)
    heads = ["#", "指标", "当前值", "近期变化", "历史位置", "口径与样本", "数据来源"]
    for i, h in enumerate(heads):
        ws2.write(2, i, h, F["h"])
    r = 3
    for i, s in enumerate(payload["snapshot"], 1):
        ws2.write_number(r, 0, i, F["num"])
        ws2.write(r, 1, s["indicator"], F["bold"])
        ws2.write(r, 2, s.get("value") or NODATA, F["cell_l"] if s.get("value") else F["nodata"])
        ws2.write(r, 3, s.get("recent") or NODATA, F["cell_l"])
        ws2.write(r, 4, s.get("history") or NODATA, F["cell_l"])
        ws2.write(r, 5, s.get("scope") or NODATA, F["cell_grey"])
        ws2.write(r, 6, s.get("source") or NODATA, F["cell_grey"])
        ws2.set_row(r, 58)
        r += 1
    ws2.write(r + 1, 1, "提示：MTO 开工、港口库存均存在多口径（外采/全口径、隆众/卓创），表中已分行标注，"
                        "不可跨口径比较或相减。", F["note"])

    # =====================================================================
    # 03 未来事件时间线
    # =====================================================================
    ws3 = wb.add_worksheet("03 未来事件时间线")
    ws3.freeze_panes(3, 0)
    ws3.set_column("A:A", 12)
    ws3.set_column("B:B", 8)
    ws3.set_column("C:C", 46)
    ws3.set_column("D:D", 18)
    ws3.set_column("E:E", 9)
    ws3.set_column("F:F", 40)
    ws3.set_column("G:G", 40)
    ws3.set_column("H:H", 36)
    ws3.merge_range("A1:H1", "未来已公开事件与数据发布节点（按确定性分级）", F["title"])
    ws3.set_row(0, 30)
    heads = ["日期", "分类", "事件 / 数据发布", "确定性等级", "距今天数", "确定性说明", "影响路径", "来源"]
    for i, h in enumerate(heads):
        ws3.write(2, i, h, F["h"])
    kind_fmt = {
        "fixed": wb.add_format({"font_name": "微软雅黑", "font_size": 9, "border": 1, "border_color": LINE,
                                "valign": "vcenter", "align": "center", "text_wrap": True,
                                "font_color": "#1A7A5E", "bg_color": "#E4F5EE"}),
        "periodic": wb.add_format({"font_name": "微软雅黑", "font_size": 9, "border": 1, "border_color": LINE,
                                   "valign": "vcenter", "align": "center", "text_wrap": True,
                                   "font_color": "#1F4E8C", "bg_color": "#E6EEFA"}),
        "cond": wb.add_format({"font_name": "微软雅黑", "font_size": 9, "border": 1, "border_color": LINE,
                               "valign": "vcenter", "align": "center", "text_wrap": True,
                               "font_color": "#8A6410", "bg_color": "#FCF5E2"}),
    }
    r = 3
    as_of = _safe_date(payload.get("as_of") or meta.get("as_of"))
    for e in sorted(payload["events"], key=lambda x: x["date"]):
        kind = e["kind"]
        kf = "fixed" if ("确定" in kind or "进行中" in kind) else ("periodic" if "定期" in kind else "cond")
        ev_date = _safe_date(e["date"])
        if as_of and ev_date:
            days = (ev_date - as_of).days
            til = f"T{days:+d}" if days != 0 else "T0"
        else:
            til = NODATA  # 模板占位符或非法日期：不臆造
        ws3.write(r, 0, e["date"], F["date"])
        ws3.write(r, 1, e["cat"], cat_fmt(e["cat"]))
        ws3.write(r, 2, e["title"], F["cell_l"])
        ws3.write(r, 3, kind, kind_fmt[kf])
        ws3.write(r, 4, til, F["center"])
        certainty = e["certainty"]
        if e.get("date_certainty"):
            certainty += "\n〔时点依据〕" + e["date_certainty"]
        ws3.write(r, 5, certainty, F["cell_l"])
        ws3.write(r, 6, e["impact"], F["cell_l"])
        ws3.write(r, 7, e["source"], F["cell_grey"])
        ws3.set_row(r, 54)
        r += 1
    ws3.conditional_format(3, 0, r - 1, 0, {
        "type": "text", "criteria": "containing", "value": "2026-10-2",
        "format": wb.add_format({"bg_color": "#FFF4D6"}),
    })
    ws3.write(r + 1, 0, "说明：黄色高亮为 10 月下旬（最近 10 天）节点。条件触发类只表示存在观察窗口，不代表已发生或必然发生。",
              F["note"])

    # =====================================================================
    # 04 候选池与筛选
    # =====================================================================
    ws4 = wb.add_worksheet("04 候选池与筛选")
    ws4.freeze_panes(3, 0)
    ws4.set_column("A:A", 6)
    ws4.set_column("B:B", 38)
    ws4.set_column("C:C", 9)
    ws4.set_column("D:D", 11)
    ws4.set_column("E:E", 30)
    ws4.set_column("F:F", 86)
    ws4.merge_range("A1:F1", "候选变量池与筛选依据", F["title"])
    ws4.set_row(0, 30)
    ws4.merge_range("A2:F2",
                    "筛选标准：① 产业逻辑强度（能否直接改变供需或价格形成机制）② 可验证性（是否能在周期内拿到可交叉验证的数据）"
                    "③ 观察周期匹配度（1 个月内能否完成至少一次「假设→验证」）三者相乘，只保留 3–6 个。",
                    F["note"])
    ws4.set_row(1, 32)
    for i, h in enumerate(["#", "候选指标", "分类", "是否入选", "可验证性", "入选 / 落选理由"]):
        ws4.write(2, i, h, F["h"])
    f_sel = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1, "border_color": LINE,
                           "valign": "vcenter", "align": "center", "bold": True,
                           "font_color": "#1A7A5E", "bg_color": "#E4F5EE"})
    f_no = wb.add_format({"font_name": "微软雅黑", "font_size": 10, "border": 1, "border_color": LINE,
                          "valign": "vcenter", "align": "center", "font_color": "#7A8798", "bg_color": "#F0F2F5"})
    r = 3
    for i, c in enumerate(payload["candidates"], 1):
        ws4.write_number(r, 0, i, F["num"])
        ws4.write(r, 1, c["name"], F["bold"])
        ws4.write(r, 2, c["cat"], cat_fmt(c["cat"]))
        ws4.write(r, 3, "✔ 入选" if c["selected"] else "— 未入选", f_sel if c["selected"] else f_no)
        ws4.write(r, 4, c["verifiability"], F["cell_l"])
        ws4.write(r, 5, c["reason"], F["cell_l"])
        ws4.set_row(r, 44)
        r += 1

    r += 1
    ws4.merge_range(r, 0, r, 5, "二级观察：不进卡片，但达到阈值需提级", F["section"])
    r += 1
    for i, h in enumerate(["#", "指标", "分类", "状态", "提级触发阈值", "说明"]):
        ws4.write(r, i, h, F["h"])
    r += 1
    for i, s in enumerate(payload["secondary"], 1):
        ws4.write_number(r, 0, i, F["num"])
        ws4.write(r, 1, s["name"], F["bold"])
        ws4.write(r, 2, "二级", F["center"])
        ws4.write(r, 3, "备选", F["center"])
        ws4.write(r, 4, "见说明（阈值内嵌）", F["cell_grey"])
        ws4.write(r, 5, s["why"], F["cell_l"])
        ws4.set_row(r, 54)
        r += 1

    # =====================================================================
    # 05 验证条件与触发器
    # =====================================================================
    ws5 = wb.add_worksheet("05 验证条件与触发器")
    ws5.freeze_panes(3, 0)
    ws5.set_column("A:A", 6)
    ws5.set_column("B:B", 30)
    ws5.set_column("C:C", 32)
    ws5.set_column("D:D", 32)
    ws5.set_column("E:E", 32)
    ws5.set_column("F:F", 24)
    ws5.set_column("G:G", 16)
    ws5.set_column("H:H", 30)
    ws5.merge_range("A1:H1", "验证条件与触发器台账（回写区）", F["title"])
    ws5.set_row(0, 30)
    ws5.merge_range("A2:H2",
                    "用法：每次数据更新后，在 F/G/H 列记录「本次读数 / 是否触发 / 处理动作」。触发任一条件都必须回写，"
                    "并在 01 表更新结论。G 列预留下拉：未触发 / 确认信号 / 否证信号 / 变量失效。",
                    F["note"])
    ws5.set_row(1, 30)
    heads = ["#", "变量", "确认信号（判断成立）", "否证信号（判断需修正）", "变量失效 / 口径失真",
             "下次检查日", "本次状态", "处理动作 / 备注"]
    for i, h in enumerate(heads):
        ws5.write(2, i, h, F["h"])
    r = 3
    for v in vs:
        ws5.write_number(r, 0, v["rank"], F["num"])
        ws5.write(r, 1, v["name"], F["bold"])
        ws5.write(r, 2, v["verify_yes"], F["yes"])
        ws5.write(r, 3, v["verify_no"], F["no"])
        ws5.write(r, 4, v["invalidate"], F["inv"])
        ws5.write(r, 5, v["next_date"], F["cell_l"])
        ws5.write(r, 6, "", F["center"])
        ws5.write(r, 7, "", F["cell_l"])
        ws5.set_row(r, 92)
        r += 1
    # 下拉校验
    ws5.data_validation(3, 6, r - 1, 6, {
        "validate": "list",
        "source": ["未触发", "确认信号", "否证信号", "变量失效"],
        "input_title": "本次状态",
        "input_message": "选择本次读数对应的状态",
    })
    ws5.conditional_format(3, 6, r - 1, 6, {"type": "text", "criteria": "containing",
                                            "value": "确认", "format": wb.add_format({"bg_color": "#E4F5EE", "bold": True})})
    ws5.conditional_format(3, 6, r - 1, 6, {"type": "text", "criteria": "containing",
                                            "value": "否证", "format": wb.add_format({"bg_color": "#FDECE6", "bold": True})})
    ws5.conditional_format(3, 6, r - 1, 6, {"type": "text", "criteria": "containing",
                                            "value": "失效", "format": wb.add_format({"bg_color": "#FCF5E2", "bold": True})})

    # =====================================================================
    # 06 数据缺口登记
    # =====================================================================
    ws6 = wb.add_worksheet("06 数据缺口登记")
    ws6.freeze_panes(3, 0)
    ws6.set_column("A:A", 6)
    ws6.set_column("B:B", 32)
    ws6.set_column("C:C", 46)
    ws6.set_column("D:D", 42)
    ws6.set_column("E:E", 34)
    ws6.merge_range("A1:E1", "数据缺口登记：无法稳定获取的指标与处理方式", F["title"])
    ws6.set_row(0, 30)
    ws6.merge_range("A2:E2",
                    "规则：拿不到就写「数据缺失」并在此登记，不得用估算值冒充实测值。替代口径必须在表内注明其局限。",
                    F["note"])
    ws6.set_row(1, 24)
    for i, h in enumerate(["#", "指标", "为什么不可得", "替代口径 / 变通做法", "局限"]):
        ws6.write(2, i, h, F["h"])
    r = 3
    for i, g in enumerate(payload["gaps"], 1):
        ws6.write_number(r, 0, i, F["num"])
        ws6.write(r, 1, g["item"], F["bold"])
        ws6.write(r, 2, g["why"], F["cell_l"])
        ws6.write(r, 3, g["workaround"], F["cell_l"])
        ws6.write(r, 4, g["limit"], F["cell_grey"])
        ws6.set_row(r, 52)
        r += 1

    # =====================================================================
    # 07 观察日程
    # =====================================================================
    ws7 = wb.add_worksheet("07 观察日程")
    ws7.hide_gridlines(2)
    ws7.set_column("A:A", 20)
    ws7.set_column("B:B", 70)
    ws7.set_column("C:C", 32)
    ws7.merge_range("A1:C1", "固定观察节奏（把「何时查什么」固化）", F["title"])
    ws7.set_row(0, 30)
    for i, h in enumerate(["频率 / 时点", "查询内容", "来源"]):
        ws7.write(2, i, h, F["h"])
    r = 3
    for w in payload.get("weekly_calendar", []):
        ws7.write(r, 0, w["when"], F["bold"])
        ws7.write(r, 1, w["what"], F["cell_l"])
        ws7.write(r, 2, w["src"], F["cell_grey"])
        ws7.set_row(r, 36)
        r += 1

    r += 1
    ws7.merge_range(r, 0, r, 2, "本期关键节点（按变量下次可观测时间）", F["section"])
    r += 1
    for i, h in enumerate(["变量", "下次可观测", "观察周期"]):
        ws7.write(r, i, h, F["h"])
    r += 1
    for v in vs:
        ws7.write(r, 0, v["name"], F["bold"])
        ws7.write(r, 1, v["next_date"], F["cell_l"])
        ws7.write(r, 2, v["horizon"], F["cell_grey"])
        ws7.set_row(r, 34)
        r += 1

    wb.close()
    return out_path
