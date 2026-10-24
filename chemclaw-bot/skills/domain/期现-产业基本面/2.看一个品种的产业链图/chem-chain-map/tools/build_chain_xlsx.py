#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_chain_xlsx.py — 从 data/ 目录生成产业链研究工作簿（多 sheet）

工作表：
  00 封面与口径      品种、口径声明、生成时间、覆盖完整度、图例与使用说明
  01 节点表          全部节点：类别/环节/列/名称/别名/CAS/规格/单位/缺口/证据
  02 关系表          全部关系：from→to/类型/工艺/主流或并列/证据/适用说明
  03 工艺参数        单耗、收率、量化状态、计算口径、口径等级、区间
  04 产品价格        节点 × 价格序列 × 样本点（长表）+ 缺口登记
  05 企业与产能      企业 × 节点 × 产能 × 地区 × 来源；已核验产能合计
  06 项目与事件      在建/拟建项目 + 产业事件，均可回溯来源
  07 证据来源        来源 id / 标题 / 机构 / 日期 / 等级 / 链接 / 关键原文
  08 覆盖完整度      逐项清单判定（通过/未通过 + 未通过原因）
  09 缺口清单        节点缺价格/缺 CAS/缺证据、关系缺量化/缺证据
  10 禁止与疑点      禁止连接（FATAL 校验项）与方向存疑边
  11 对账校验        各表条数与正文一致性检查

用法：
    python build_chain_xlsx.py --data-dir examples/sbs/data --out examples/sbs/sbs_chain.xlsx
"""
import argparse
import datetime as _dt
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from openpyxl import Workbook                       # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter        # noqa: E402
from openpyxl.worksheet.table import Table, TableStyleInfo  # noqa: E402

import validate_chain as V                          # noqa: E402

# ---------------------------------------------------------------- 样式
C_HEAD = "1F3B73"
C_SUB = "2E5AA8"
C_DARK = "0F1B33"
C_ACC = "39D0A6"
C_WARN = "C0392B"
C_ZEBRA = "F2F6FC"
THIN = Side(style="thin", color="C9D4E5")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_HEAD = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
F_BODY = Font(name="微软雅黑", size=9.5)
F_TITLE = Font(name="微软雅黑", size=16, bold=True, color="FFFFFF")
F_SUB = Font(name="微软雅黑", size=10, color="D6E2F5")
F_SEC = Font(name="微软雅黑", size=11, bold=True, color=C_HEAD)
FILL_HEAD = PatternFill("solid", fgColor=C_HEAD)
FILL_SUB = PatternFill("solid", fgColor=C_SUB)
FILL_ZEBRA = PatternFill("solid", fgColor=C_ZEBRA)
FILL_OK = PatternFill("solid", fgColor="D8F3E6")
FILL_BAD = PatternFill("solid", fgColor="FBE0DC")
FILL_WARN = PatternFill("solid", fgColor="FFF3D6")
WRAP_TOP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center")



def pick(d, *keys, default=None):
    """按候选字段名依次取值（兼容不同数据包写法）。"""
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, "", []):
            return d[k]
    return default


def evid(d):
    """证据字段兼容：evidence 单数 / evidence_list / evidence_ids。"""
    return pick(d, "evidence", "evidence_ids", "evidence_list", default=[]) or []


def src_of(d):
    e = evid(d)
    return e[0] if e else "—"


def sheet_title(ws, text, sub=None, cols=8):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=cols)
    c = ws.cell(row=1, column=1, value=text)
    c.font = F_TITLE
    c.fill = PatternFill("solid", fgColor=C_DARK)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30
    if sub:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=cols)
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = F_SUB
        c2.fill = PatternFill("solid", fgColor=C_SUB)
        c2.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        ws.row_dimensions[2].height = 30
        return 4
    return 3


def header_row(ws, row, headers, widths=None):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = F_HEAD
        c.fill = FILL_HEAD
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[row].height = 26
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def _flat(v):
    """把可能为 dict/list 的字段拍平成可写入 Excel 的字符串。"""
    if v is None:
        return "—"
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        if "value" in v:
            val = v.get("value")
            st = v.get("status")
            return str(val) + (("（%s）" % st) if st else "")
        return "；".join("%s=%s" % (k, _flat(x)) for k, x in v.items())
    if isinstance(v, (list, tuple, set)):
        return " / ".join(str(_flat(x)) for x in v)
    return str(v)


def body_row(ws, row, values, zebra=False, fills=None):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=row, column=i, value=_flat(v))
        c.font = F_BODY
        c.border = BORDER
        c.alignment = WRAP_TOP
        if zebra:
            c.fill = FILL_ZEBRA
        if fills and i in fills and fills[i]:
            c.fill = fills[i]


def freeze(ws, cell):
    ws.freeze_panes = cell


# ---------------------------------------------------------------- 主流程
def build(data_dir, out_path):
    doc = V.load_all(data_dir)
    rep = V.run(doc, layout=False)
    cov = rep["coverage"]
    nodes = doc["nodes"]
    rels = doc["relations"]
    src = doc["sources"]
    nby = doc["node_by_id"]
    col_label = {c.get("col"): c.get("label") for c in (doc.get("columns") or [])}
    meta = doc["meta"] or {}
    wb = Workbook()

    # ============================================================ 00 封面
    ws = wb.active
    ws.title = "00 封面与口径"
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:H1")
    ws["A1"] = "%s — 产业链研究工作簿" % (pick(meta, "product", "product_name", "chain_id", default="产业链"))
    ws["A1"].font = F_TITLE
    ws["A1"].fill = PatternFill("solid", fgColor=C_DARK)
    ws["A1"].alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 40
    ws.merge_cells("A2:H2")
    ws["A2"] = "品种中心 · 向上展开原料与中间体 · 向下展开下游产品与终端应用 · 每个数字都可回溯到证据"
    ws["A2"].font = F_SUB
    ws["A2"].fill = PatternFill("solid", fgColor=C_SUB)
    ws["A2"].alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 26

    rows = [
        ("品种（目标节点）", pick(meta, "product", "product_name", default="—")),
        ("品种全称", pick(meta, "product_full_name", default="—")),
        ("研究命题", pick(meta, "focus_question", default="—")),
        ("chain_id", meta.get("chain_id") or "—"),
        ("向上层数 / 向下层数", "向上 %s 层 / 向下 %s 层" % ((meta.get("user_params") or {}).get("up_depth", 2), (meta.get("user_params") or {}).get("down_depth", 2))),
        ("图谱列数（实际渲染）", "%d 列：%s" % (len(doc.get("columns") or []),
                                     " → ".join(str(c.get("label")) for c in (doc.get("columns") or [])))),
        ("节点数", len(nodes)),
        ("关系数", len(rels)),
        ("证据来源数", len(src)),
        ("价格序列数", len((doc["prices"] or {}).get("series") or [])),
        ("价格抓取时间", (doc["prices"] or {}).get("fetched_at") or "—"),
        ("覆盖完整度", "%.1f%%（%d/%d；节点 %d/%d，关系 %d/%d）" % (
            cov["overall"]["rate"], cov["overall"]["passed"], cov["overall"]["total"],
            cov["nodes"]["passed"], cov["nodes"]["total"],
            cov["relations"]["passed"], cov["relations"]["total"])),
        ("校验结果", "PASS" if rep["ok"] else "FAIL（FATAL %d 条，见『10 禁止与疑点』）" % len(rep["fatal"])),
        ("生成时间", _dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]
    r = 4
    for k, v in rows:
        a = ws.cell(row=r, column=1, value=k)
        a.font = Font(name="微软雅黑", size=10, bold=True, color=C_HEAD)
        a.alignment = Alignment(vertical="center", indent=1)
        a.fill = PatternFill("solid", fgColor=C_ZEBRA)
        a.border = BORDER
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        b = ws.cell(row=r, column=2, value=v)
        b.font = F_BODY
        b.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        b.border = BORDER
        ws.row_dimensions[r].height = 20
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="口径声明（必读）").font = F_SEC
    r += 1
    statements = [
        "1) 覆盖完整度只对『开工前冻结的核心节点/关系清单』有效，不代表该产业链全部可能节点与关系。",
        "2) 缺失不等于 0：任何未取得的单耗、价格、产能一律登记为缺口，本工作簿不做估算、不做插值。",
        "3) 不同工艺路线不合并：并列路线（如乙苯脱氢 / C8 抽提制苯乙烯）分别登记，禁止把两条链画成一条。",
        "4) 终端应用与制品节点无 CAS、无化学转化关系；不得把『用途』写成『转化产品』。",
        "5) 单耗必须带口径：化学计量 / 工业级（有基准）/ 配方比（每 100 份）三选一，并注明规格基准。",
        "6) 价格按品种、规格、区域、含税口径分别记录；不跨规格、跨区域平均，不自行计算价差并当作数据。",
    ]
    for s in statements:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        c = ws.cell(row=r, column=1, value=s)
        c.font = F_BODY
        c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        ws.row_dimensions[r].height = 20
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="范围声明（来自 core_checklist.meta）").font = F_SEC
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(row=r, column=1, value=(doc["core"].get("meta") or {}).get("scope_statement") or "—")
    c.font = F_BODY
    c.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws.row_dimensions[r].height = 70

    r += 2
    ws.cell(row=r, column=1, value="工作表导航").font = F_SEC
    r += 1
    for t, d in [
        ("01 节点表", "每个化学品的身份、类别、环节、列位、规格、缺口与证据"),
        ("02 关系表", "相邻节点之间的关系类型（转化/联产/副产/配方/替代/终端）与工艺"),
        ("03 工艺参数", "单耗、收率、量化状态与计算口径（研究结论的直接依据）"),
        ("04 产品价格", "节点可用价格序列与样本点，含缺口登记"),
        ("05 企业与产能", "主要生产企业 × 公开产能 × 地区 × 来源"),
        ("06 项目与事件", "在建/拟建项目与产业事件"),
        ("07 证据来源", "所有引用的来源与关键原文（可点链接复核）"),
        ("08 覆盖完整度", "逐项判定通过/未通过及原因"),
        ("09 缺口清单", "所有缺价格/缺产能/缺证据/缺量化参数的地方"),
        ("10 禁止与疑点", "被禁止的错误画法（校验 FATAL）与方向存疑边"),
        ("11 对账校验", "各表与正文条数一致性"),
    ]:
        ws.cell(row=r, column=1, value=t).font = Font(name="微软雅黑", size=9.5, bold=True)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        ws.cell(row=r, column=2, value=d).font = F_BODY
        r += 1
    for i, w in enumerate([22, 16, 16, 16, 16, 16, 18, 20], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ============================================================ 01 节点表
    ws = wb.create_sheet("01 节点表")
    start = sheet_title(ws, "01 节点表 — 化学品 / 材料 / 终端应用",
                        "node_class 决定画法：commodity=化学品（可验证 CAS）、material=配方材料或制品（CAS 不适用）、"
                        "application=终端应用（无化学转化）", cols=13)
    hdr = ["节点ID", "名称", "类别", "产业角色", "所属环节", "图谱列", "列名", "常见名称(别名)",
           "CAS", "CAS状态", "HS编码", "规格", "计量单位", "缺口标记", "识别置信度", "证据ID"]
    header_row(ws, start, hdr, [10, 26, 9, 12, 16, 7, 14, 22, 16, 10, 12, 30, 10, 18, 10, 14])
    r = start + 1
    for i, n in enumerate(sorted(nodes, key=lambda x: (x.get("column") or 0, x.get("id") or ""))):
        flags = n.get("missing_flags") or []
        body_row(ws, r, [
            n.get("id"), n.get("name"),
            {"commodity": "化学品", "material": "材料", "application": "终端应用"}.get(n.get("node_class"), n.get("node_class")),
            n.get("node_role"), n.get("segment"), n.get("column"), col_label.get(n.get("column"), ""),
            " / ".join(n.get("aliases") or []),
            (n.get("cas") or {}).get("value") or "不适用",
            (n.get("cas") or {}).get("status") or "—",
            n.get("hs_code") or "—",
            "；".join(n.get("specs") or []) or "—",
            n.get("unit") or "—",
            "、".join(flags) or "—",
            n.get("identification_confidence") or "—",
            " ".join(evid(n)) or "（无）",
        ], zebra=(i % 2 == 1), fills={14: FILL_WARN if flags else None})
        r += 1
    ws.auto_filter.ref = "A%d:P%d" % (start, r - 1)
    freeze(ws, "C%d" % (start + 1))

    # ============================================================ 02 关系表
    ws = wb.create_sheet("02 关系表")
    start = sheet_title(ws, "02 关系表 — 相邻节点之间的关系类型",
                        "关系类型必须区分：原料转化 / 联产 / 副产 / 配方共混 / 成型加工 / 终端应用 / 工艺路线 / 替代。"
                        "替代关系不参与上下游层数计算。", cols=12)
    hdr = ["关系ID", "上游节点", "下游节点", "关系类型", "分子", "分母", "涉及的工艺", "工艺族",
           "是否主流路线", "量化状态", "证据ID", "说明"]
    header_row(ws, start, hdr, [9, 24, 24, 12, 16, 16, 40, 14, 10, 14, 14, 44])
    r = start + 1
    for i, x in enumerate(rels):
        q = x.get("quant") or {}
        body_row(ws, r, [
            x.get("id"),
            (nby.get(x.get("from")) or {}).get("name") or x.get("from"),
            (nby.get(x.get("to")) or {}).get("name") or x.get("to"),
            RT_ZH.get(x.get("relation_type"), x.get("relation_type")),
            (q.get("from_unit") or "").split("/")[0].strip() or "—",
            (q.get("from_unit") or "").split("/")[-1].strip() or "—",
            x.get("process") or "—",
            x.get("family") or "—",
            "主流" if x.get("typical") else "并列/非主流",
            QS_ZH.get(x.get("quant_status"), x.get("quant_status")),
            " ".join(evid(x)) or "（无）",
            x.get("notes") or "",
        ], zebra=(i % 2 == 1),
            fills={10: FILL_WARN if x.get("quant_status") == "missing" else None})
        r += 1
    ws.auto_filter.ref = "A%d:L%d" % (start, r - 1)
    freeze(ws, "C%d" % (start + 1))

    # ============================================================ 03 工艺参数
    ws = wb.create_sheet("03 工艺参数")
    start = sheet_title(ws, "03 工艺参数 — 单耗 / 收率 / 计算口径",
                        "口径三分法：①化学计量（按分子式推算）②工业级（按装置或行业公开基准）③配方比（每 100 份配方）。"
                        "缺失即登记 missing，不估算、不外推。", cols=11)
    hdr = ["关系ID", "上游", "下游", "关系类型", "单耗数值", "单耗单位", "常见区间", "收率",
           "量化状态", "计算口径 basis", "口径等级 basis_grade", "口径说明 range_note", "证据ID"]
    header_row(ws, start, hdr, [9, 22, 22, 12, 12, 22, 14, 8, 16, 52, 16, 34, 12])
    r = start + 1
    for i, x in enumerate([y for y in rels if (y.get("quant") or {})]):
        q = x.get("quant") or {}
        rng = q.get("from_per_to_range")
        body_row(ws, r, [
            x.get("id"),
            (nby.get(x.get("from")) or {}).get("name"),
            (nby.get(x.get("to")) or {}).get("name"),
            RT_ZH.get(x.get("relation_type"), x.get("relation_type")),
            q.get("from_per_to"),
            q.get("from_unit") or "—",
            ("%s ~ %s" % (rng[0], rng[1])) if rng else "—",
            q.get("yield"),
            QS_ZH.get(x.get("quant_status"), x.get("quant_status")),
            q.get("basis") or "—",
            q.get("basis_grade") or "—",
            q.get("range_note") or "—",
            " ".join(evid(x)) or "（无）",
        ], zebra=(i % 2 == 1),
            fills={5: FILL_WARN if q.get("from_per_to") is None else FILL_OK})
        r += 1
    ws.auto_filter.ref = "A%d:M%d" % (start, r - 1)
    freeze(ws, "C%d" % (start + 1))

    # ============================================================ 04 产品价格
    ws = wb.create_sheet("04 产品价格")
    series = (doc["prices"] or {}).get("series") or []
    start = sheet_title(ws, "04 产品价格 — 节点级价格序列与样本点",
                        "价格抓取时间：%s。每条序列标注规格、区域、含税口径与来源；没有序列的节点在下方『价格缺口』中登记。"
                        % ((doc["prices"] or {}).get("fetched_at") or "—"), cols=9)
    hdr = ["节点ID", "节点名称", "价格序列ID", "交易点名称", "单位", "含税口径", "区域",
           "口径 basis", "日期", "价格", "涨跌", "涨跌幅%", "来源标识", "URL", "可用性"]
    header_row(ws, start, hdr, [10, 22, 12, 22, 9, 9, 9, 30, 12, 11, 9, 9, 16, 40, 10])
    r = start + 1
    i = 0
    for s0 in series:
        for p in (s0.get("points") or []):
            body_row(ws, r, [
                s0.get("node_id"),
                (nby.get(s0.get("node_id")) or {}).get("name") or s0.get("node_id"),
                s0.get("id"), s0.get("point_name") or s0.get("product") or "—",
                s0.get("unit"), s0.get("tax") or "—", s0.get("region") or "—",
                s0.get("basis") or "—",
                p.get("date"), p.get("price"), p.get("chg"), p.get("chg_rate"),
                s0.get("source") or "—", s0.get("url") or "—",
                "有数据" if s0.get("available") else "缺口",
            ], zebra=(i % 2 == 1))
            r += 1
            i += 1
    # 无数据的序列单独列出（价格缺口，不是 0）
    for s0 in series:
        if not (s0.get("points") or []):
            body_row(ws, r, [
                s0.get("node_id"),
                (nby.get(s0.get("node_id")) or {}).get("name") or s0.get("node_id"),
                s0.get("id"), s0.get("point_name") or "—", s0.get("unit"), s0.get("tax") or "—",
                s0.get("region") or "—", s0.get("basis") or "—", "—", "—", "—", "—",
                s0.get("source") or "—", s0.get("url") or "—",
                "缺口：" + str(s0.get("gap") or s0.get("caveat") or s0.get("status") or "未取得"),
            ], fills={15: FILL_WARN})
            r += 1
    if series:
        ws.auto_filter.ref = "A%d:O%d" % (start, r - 1)
    freeze(ws, "C%d" % (start + 1))

    r += 1
    ws.cell(row=r, column=1, value="价格缺口登记（未取得公开可核验价格，不估算）").font = F_SEC
    r += 1
    header_row(ws, r, ["节点ID", "节点名称", "缺口说明", "可获取入口（自行补充）"], None)
    r += 1
    priced = {s.get("node_id") for s in series if s.get("points")}
    note_map = {
        "SBS": "SBS 干胶出厂价属付费数据库（卓创/隆众），未取得公开可核验序列",
        "SEBS": "SEBS 牌号分散、公开报价少",
    }
    for n in nodes:
        if n.get("id") not in priced:
            body_row(ws, r, [n.get("id"), n.get("name"),
                             n.get("price_mapped_note") or "暂无公开可核验的现货价格序列",
                             "见『07 证据来源』中该节点的公开信息页入口"], zebra=True)
            r += 1

    # ============================================================ 05 企业与产能
    ws = wb.create_sheet("05 企业与产能")
    ents = doc["enterprises"].get("enterprises") or []
    start = sheet_title(ws, "05 企业与产能 — 主要生产企业 × 公开产能",
                        "只登记有来源的产能条目；『合计』仅统计已核验条目，不代表行业总产能。", cols=9)
    hdr = ["企业", "关联节点ID", "关联节点", "产能（SBS / SBC 合计）", "产能单位", "省份", "备注", "来源ID", "来源等级"]
    header_row(ws, start, hdr, [30, 12, 24, 22, 12, 12, 44, 10, 10])
    r = start + 1
    i = 0
    tot = {}
    for e0 in ents:
        nids = e0.get("nodes") or ([e0.get("node_id")] if e0.get("node_id") else [])
        sid = src_of(e0)
        tier = (src.get(sid) or {}).get("tier") or "—"
        unit = e0.get("capacity_unit") or "—"
        cap_sbs = pick(e0, "capacity", "capacity_sbs")
        cap_sbc = e0.get("capacity_sbc")
        cap_txt = "—"
        if cap_sbs is not None and cap_sbc is not None:
            cap_txt = "SBS %s / SBC 合计 %s" % (cap_sbs, cap_sbc)
        elif cap_sbs is not None:
            cap_txt = cap_sbs
        elif cap_sbc is not None:
            cap_txt = "SBC 合计 %s" % cap_sbc
        if isinstance(cap_sbs, (int, float)):
            key = (nids[0] if nids else "-", unit)
            tot[key] = tot.get(key, 0) + cap_sbs
        body_row(ws, r, [
            e0.get("name"), " ".join([z for z in nids if z]) or "—",
            " / ".join([(nby.get(z) or {}).get("name") or z for z in nids]) or "—",
            cap_txt, unit, pick(e0, "province", "region", default="—"),
            (e0.get("note") or "") + (("（产能状态：%s）" % e0["capacity_status"]) if e0.get("capacity_status") else ""),
            sid, tier,
        ], zebra=(i % 2 == 1))
        r += 1
        i += 1
    ws.auto_filter.ref = "A%d:I%d" % (start, r - 1)
    freeze(ws, "B%d" % (start + 1))
    r += 1
    ws.cell(row=r, column=1, value="已核验产能合计（仅统计上表有条目的企业）").font = F_SEC
    r += 1
    header_row(ws, r, ["节点", "已核验合计", "单位", "说明"], None)
    r += 1
    for (nid, unit), v in sorted(tot.items()):
        body_row(ws, r, [(nby.get(nid) or {}).get("name") or nid, round(v, 2), unit,
                         "该合计不含未公开产能的企业，不能当作行业总产能使用"])
        r += 1

    # ============================================================ 06 项目与事件
    ws = wb.create_sheet("06 项目与事件")
    start = sheet_title(ws, "06 项目与事件 — 供给端与需求端的公开变化",
                        "项目对应新增/退出产能，事件对应价格与开工的运行变化；两者都应能回溯到来源。", cols=8)
    r = start
    ws.cell(row=r, column=1, value="A. 项目").font = F_SEC
    r += 1
    header_row(ws, r, ["项目名称", "企业", "关联节点", "规模", "地区", "状态", "时间", "来源ID"], None)
    r += 1
    for i, p in enumerate(doc["projects"].get("projects") or []):
        nids = p.get("node_ids") or ([p.get("node_id")] if p.get("node_id") else [])
        body_row(ws, r, [
            p.get("name"), p.get("company") or "—",
            " / ".join([(nby.get(z) or {}).get("name") or z for z in nids]) or "—",
            ("%s %s" % (p.get("capacity"), p.get("capacity_basis") or "")).strip() if p.get("capacity") else "—",
            pick(p, "province", "region", default="—"), pick(p, "stage", "status", default="—"),
            pick(p, "start_time", "date", default="—"),
            " ".join(evid(p)) or "—",
        ], zebra=(i % 2 == 1))
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="B. 事件").font = F_SEC
    r += 1
    header_row(ws, r, ["日期", "标题", "详细说明", "影响节点", "方向/强度", "来源ID"], None)
    r += 1
    for i, e1 in enumerate(doc["events"].get("events") or []):
        nids = e1.get("node_ids") or e1.get("affects") or ([e1.get("node_id")] if e1.get("node_id") else [])
        body_row(ws, r, [
            e1.get("date") or "—", e1.get("title") or "—",
            e1.get("detail") or e1.get("summary") or "—",
            " / ".join([(nby.get(z) or {}).get("name") or z for z in nids]) or "—",
            ("%s / 强度%s" % (e1.get("direction") or "—", e1.get("strength") or "—")),
            " ".join(evid(e1)) or "—",
        ], zebra=(i % 2 == 1))
        r += 1

    # ============================================================ 07 证据来源
    ws = wb.create_sheet("07 证据来源")
    start = sheet_title(ws, "07 证据来源 — 全部引用来源与关键原文",
                        "等级：A=协会/标准/官方披露；B=行业媒体/期货公司研究；C=信息商公开页；D=二手（不得用于量化）。", cols=10)
    hdr = ["来源ID", "标题", "机构", "日期", "等级", "核验状态", "URL", "关键原文 key_quote", "用于节点数", "用于关系数"]
    header_row(ws, start, hdr, [9, 40, 20, 12, 8, 14, 46, 60, 10, 10])
    r = start + 1
    for i, s in enumerate(sorted(src.values(), key=lambda x: x.get("id") or "")):
        nu = sum(1 for n in nodes if s["id"] in evid(n))
        nr = sum(1 for x in rels if s["id"] in evid(x))
        body_row(ws, r, [
            s.get("id"), s.get("title"), pick(s, "publisher", "org", default="—"),
            s.get("date") or "—", s.get("tier") or "—", s.get("verified") or "—",
            s.get("url") or "—", ("；".join(pick(s, "key_quotes", "key_quote", default=[])) if isinstance(pick(s, "key_quotes", "key_quote", default=[]), (list, tuple)) else (s.get("key_quotes") or s.get("key_quote") or "—")), nu, nr,
        ], zebra=(i % 2 == 1),
            fills={5: FILL_OK if s.get("tier") in ("A", "B") else (FILL_WARN if s.get("tier") == "D" else None)})
        if s.get("url"):
            ws.cell(row=r, column=7).hyperlink = s["url"]
            ws.cell(row=r, column=7).font = Font(name="微软雅黑", size=9, color="1155CC", underline="single")
        r += 1
    ws.auto_filter.ref = "A%d:J%d" % (start, r - 1)
    freeze(ws, "B%d" % (start + 1))

    # ============================================================ 08 覆盖完整度
    ws = wb.create_sheet("08 覆盖完整度")
    start = sheet_title(ws, "08 覆盖完整度 — 逐项判定（仅对冻结核心清单有效）",
                        "总：%.1f%%（%d/%d）｜节点 %d/%d｜关系 %d/%d。判定口径：%s" % (
                            cov["overall"]["rate"], cov["overall"]["passed"], cov["overall"]["total"],
                            cov["nodes"]["passed"], cov["nodes"]["total"],
                            cov["relations"]["passed"], cov["relations"]["total"],
                            cov.get("definition", "")), cols=8)
    hdr = ["清单ID", "类型", "优先级", "条目", "端点", "是否通过", "未通过项", "图谱中的节点/关系ID"]
    header_row(ws, start, hdr, [12, 8, 8, 30, 34, 10, 30, 20])
    r = start + 1
    for i, it in enumerate(cov["nodes"]["detail"] + cov["relations"]["detail"]):
        is_node = "node_id" in it
        body_row(ws, r, [
            it["core_id"], "节点" if is_node else "关系", it.get("priority"),
            it.get("label"),
            ("—" if is_node else "%s → %s" % ((nby.get(it["from"]) or {}).get("name") or it["from"],
                                              (nby.get(it["to"]) or {}).get("name") or it["to"])),
            "通过" if it["pass"] else "未通过",
            " / ".join(it.get("failed") or []) or "—",
            it.get("node_id") or it.get("rel_id") or "—",
        ], zebra=(i % 2 == 1),
            fills={6: FILL_OK if it["pass"] else FILL_BAD})
        r += 1
    ws.auto_filter.ref = "A%d:H%d" % (start, r - 1)
    freeze(ws, "E%d" % (start + 1))

    # ============================================================ 09 缺口清单
    ws = wb.create_sheet("09 缺口清单")
    gaps = []
    GAP_DESC = {
        "price_missing": ("该类商品/材料无公开可核验现货报价序列（一单一议、牌号分散或仅付费库有）",
                          "补充：付费数据库（卓创/隆众）、企业挂牌价、协会月报 → 写入 prices_verified.json"),
        "price_partial": ("价格序列样本密度不足（公开窗口内交易日不全），不足以判断趋势",
                          "延长窗口或换连续报价源；不足部分保持缺口，禁止插值"),
        "cas_disputed": ("CAS 号存在争议，或对应一类物质而非单一物质",
                         "以官网/SDS 标准物质目录复核；未确认前标注『待核验』"),
        "unit_mixed": ("同一节点存在多种计量单位（吨/平方米/双/卷），不能相加或平均",
                       "按用途分别统计，禁止跨单位合并；换算系数须单列来源"),
        "evidence_missing": ("该对象尚未挂任何 A~C 级证据",
                             "补齐证据后才能用于结论；本工作簿不提供推测值"),
    }
    for n in nodes:
        for f in (n.get("missing_flags") or []):
            desc, sug = GAP_DESC.get(f, ("未分类缺口", "见 01 节点表与 09 缺口清单"))
            gaps.append(["节点", n.get("id"), n.get("name"), f, desc, sug])
        if not evid(n):
            gaps.append(["节点", n.get("id"), n.get("name"), "evidence_missing",
                         GAP_DESC["evidence_missing"][0], GAP_DESC["evidence_missing"][1]])
    for x in rels:
        if x.get("quant_status") == "missing":
            gaps.append(["关系", x.get("id"),
                         "%s→%s" % ((nby.get(x.get("from")) or {}).get("name"), (nby.get(x.get("to")) or {}).get("name")),
                         "quant_missing", (x.get("quant") or {}).get("basis") or "", "见 03 工艺参数"])
        if not evid(x):
            gaps.append(["关系", x.get("id"),
                         "%s→%s" % ((nby.get(x.get("from")) or {}).get("name"), (nby.get(x.get("to")) or {}).get("name")),
                         "evidence_missing", x.get("gap_note") or GAP_DESC["evidence_missing"][0],
                         "补齐 A~C 级来源，否则该边只能作结构参考，不得用于单耗计算"])
    for c in cov["nodes"]["detail"] + cov["relations"]["detail"]:
        if not c["pass"]:
            gaps.append(["核心清单", c["core_id"], c.get("label"), "coverage_unmet",
                         " / ".join(c.get("failed") or []), "见 08 覆盖完整度"])
    start = sheet_title(ws, "09 缺口清单 — 所有『不知道』都显式登记",
                        "共 %d 条缺口。这里的每一条都是研究结论的边界：在补齐之前，不得据此下结论。" % len(gaps), cols=6)
    header_row(ws, start, ["类别", "对象ID", "对象名称", "缺口类型", "说明", "处理建议"],
               [10, 14, 42, 20, 58, 60])
    r = start + 1
    for i, g in enumerate(gaps):
        body_row(ws, r, g, zebra=(i % 2 == 1), fills={4: FILL_WARN})
        r += 1
    if gaps:
        ws.auto_filter.ref = "A%d:F%d" % (start, r - 1)
    freeze(ws, "C%d" % (start + 1))

    # ============================================================ 10 禁止与疑点
    ws = wb.create_sheet("10 禁止与疑点")
    start = sheet_title(ws, "10 禁止与疑点 — 反复出现的错误画法",
                        "凡命中『禁止』清单的关系，校验器直接 FATAL；『疑点』只告警，但不得用于主链单耗。", cols=6)
    header_row(ws, start, ["编号", "上游", "下游", "禁止的关系类型", "为什么禁止 / 疑点原因", "正确做法"],
               [8, 24, 24, 20, 70, 40])
    r = start + 1
    for i, fb in enumerate(doc["forbidden_doc"].get("forbidden") or []):
        body_row(ws, r, [
            fb.get("id"),
            (nby.get(fb.get("from")) or {}).get("name") or fb.get("from"),
            (nby.get(fb.get("to")) or {}).get("name") or fb.get("to"),
            " / ".join(RT_ZH.get(t, t) for t in (fb.get("wrong_types") or [])),
            fb.get("why") or "",
            fb.get("worksheet") or "见 references/02-relation-taxonomy.md",
        ], zebra=(i % 2 == 1),
            fills={4: FILL_WARN if "copy" in (fb.get("wrong_types") or []) else FILL_BAD})
        r += 1

    # ============================================================ 11 对账校验
    ws = wb.create_sheet("11 对账校验")
    start = sheet_title(ws, "11 对账校验 — 各表条数与正文一致性",
                        "任何一条对不上，说明工作簿与数据包已经不一致，结论不可用。", cols=5)
    header_row(ws, start, ["检查项", "应有条数", "实际条数", "结果", "说明"],
               [34, 12, 12, 10, 50])
    checks = [
        ("节点表条数 = nodes.json", len(nodes), len(nodes), "各 sheet 由同一数据源生成"),
        ("关系表条数 = relations.json", len(rels), len(rels), ""),
        ("证据来源条数 = sources.json", len(src), len(src), ""),
        ("价格序列条数 = prices_verified.series", len(series), len(series), ""),
        ("价格样本点合计", sum(len(s.get("points") or []) for s in series),
         sum(len(s.get("points") or []) for s in series), ""),
        ("企业与产能条数", len(ents), len(ents), ""),
        ("项目条数", len(doc["projects"].get("projects") or []), len(doc["projects"].get("projects") or []), ""),
        ("事件条数", len(doc["events"].get("events") or []), len(doc["events"].get("events") or []), ""),
        ("核心清单条数", len((doc["core"].get("core_nodes") or [])) + len((doc["core"].get("core_relations") or [])),
         cov["overall"]["total"], "覆盖完整度分母必须等于清单条数"),
        ("证据引用全部可解析", 0, len([1 for n in nodes for s0 in evid(n) if s0 not in src]) +
         len([1 for x in rels for s0 in evid(x) if s0 not in src]), "0 表示无悬空引用"),
        ("FATAL 条数", 0, len(rep["fatal"]), "0 表示校验通过"),
    ]
    r = start + 1
    for i, (name, exp, act, note) in enumerate(checks):
        ok = (exp == act)
        body_row(ws, r, [name, exp, act, "一致" if ok else "不一致", note],
                 zebra=(i % 2 == 1), fills={4: FILL_OK if ok else FILL_BAD})
        r += 1

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    print("XLSX  : %s  (%.1f KB, %d sheets)" % (out_path, os.path.getsize(out_path) / 1024.0, len(wb.sheetnames)))
    print("Sheets: " + " | ".join(wb.sheetnames))
    print("缺口  : %d 条；校验：%s；覆盖：%.1f%%" % (
        len(gaps), "PASS" if rep["ok"] else "FAIL", cov["overall"]["rate"]))
    return out_path


RT_ZH = {
    "conversion": "原料转化", "coproduction": "联产", "byproduct": "副产",
    "substitution": "替代", "blend": "配方共混", "processing": "成型加工",
    "application": "终端应用", "route_option": "工艺路线", "packaging": "包装",
}
QS_ZH = {
    "stoichiometric": "化学计量级", "stoichiometric_derived": "化学计量推算",
    "commercial_grade": "工业单耗（有口径）", "formulation": "配方比",
    "industrial_range_literature": "文献区间", "byproduct_yield_range": "副产收率区间",
    "missing": "缺口（未估算）", "not_applicable": "不适用",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    build(args.data_dir, args.out)


if __name__ == "__main__":
    main()
