# -*- coding: utf-8 -*-
"""build_excel.py — 生成事件研究 Excel 工作簿（11 张表）

表结构：
  00 说明与免责      研究边界、三种日期口径、证据等级、如何复核
  01 事件样本        可编辑样本表（与 HTML 同源），含三种日期/产能/证据/原文字段
  02 日期口径对照    公告日 / 首次获知日 / 实际停车日 三者并列 + 锚定日与顺延说明
  03 价格路径        逐事件逐窗口的价格与收益（含缺失标注）
  04 分布统计        各窗口 均值/中位/分位/胜率/符号检验/自助法CI
  05 异常收益        相对基准的区间收益差、beta 估计
  06 样本筛选        纳入/剔除逻辑、阈值判定、产品核验、重启方向
  07 事件重叠        重叠矩阵与去重叠子样本
  08 数据与来源      每个序列的来源、覆盖区间、缺口
  09 现货与基差      严格口径下留空 + 填写说明（用户补齐数据后重跑）
  10 参数假设        口径参数表，便于复现同一结果

依赖 openpyxl。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core  # noqa: E402

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    Workbook = None

NAVY = "1F3A52"
BLUE = "2E6A94"
LIGHT = "EAF2F8"
WARN = "FFF3CD"
BAD = "F8D7DA"
OKC = "D5F5E3"
GREY = "F2F3F4"


def _hdr(ws, row, cols, fill=NAVY):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 30


def _title(ws, text, sub=""):
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(size=10, color="666666")


def _widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def state_anchor_is_actual(res_row) -> bool:
    """该次运行是否以“实际停车日”为锚定日。"""
    return (res_row.get("anchor_kind") or "").startswith("actual")


def _body(ws, r0, rows, num_fmt=None, wrap_cols=()):
    """写入数据行；wrap_cols 为需要自动换行的列号。"""
    thin = Side(style="thin", color="D0D7DE")
    for ri, row in enumerate(rows):
        for ci, v in enumerate(row, 1):
            cell = ws.cell(row=r0 + ri, column=ci, value=v)
            cell.border = Border(bottom=thin, right=thin)
            cell.font = Font(size=9)
            if isinstance(v, float):
                cell.number_format = "0.00"
            cell.alignment = Alignment(vertical="top", wrap_text=(ci in wrap_cols))
            if ri % 2 == 1:
                cell.fill = PatternFill("solid", fgColor=GREY)


def build(project_dir: str, out_path: str) -> str:
    if Workbook is None:
        raise SystemExit("需要 openpyxl")
    ev_csv = core.read_csv(os.path.join(project_dir, "events.csv"))
    res = core.read_csv(os.path.join(project_dir, "build", "event_results.csv")) \
        if os.path.exists(os.path.join(project_dir, "build", "event_results.csv")) else []
    stats = json.load(open(os.path.join(project_dir, "build", "stats.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(project_dir, "build", "stats.json")) else {}
    overlap = json.load(open(os.path.join(project_dir, "build", "overlap.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(project_dir, "build", "overlap.json")) else {}
    meta = json.load(open(os.path.join(project_dir, "project.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(project_dir, "project.json")) else {}
    prov = json.load(open(os.path.join(project_dir, "evidence", "data_provenance.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(project_dir, "evidence", "data_provenance.json")) else {}

    wb = Workbook()
    wb.remove(wb.active)

    # ---- 00 说明 ----
    ws = wb.create_sheet("00 说明与免责")
    _title(ws, meta.get("title", "化工装置停车事件研究"),
           f"生成时间 {datetime.now():%Y-%m-%d %H:%M} ｜ 品种 {meta.get('product','')} ｜ 期货口径 {meta.get('futures','')}")
    lines = [
        ("一、本表在做什么", "把“某装置停车”这类供给事件，按明确的事件日对齐到交易日，计算事件前后 1/5/10/20 个交易日的价格与收益，"
                          "并给出分布与（可得的）相对基准异常收益。"),
        ("二、三种日期必须分开", "企业公告日（announce_date）/ 市场首次获知日（first_market_date）/ 实际停车日（actual_start_date）"
                             "含义不同、取值不同，不能互相顶替。默认事件日 = 市场首次获知日。"),
        ("三、事件日对齐规则", "若事件日不是交易日（周末、法定节假日、停牌），顺延到其后第一个交易日，并在 02 表登记顺延说明。"),
        ("四、口径与缺口", "不插值、不补数。价格或基准取不到的窗口，一律留空并在 03/09 表标注“缺失”，"
                       "而不是给一个估算值。"),
        ("五、因果边界", "事件窗口内的价格变动不等于因果效应。同期存在成本端（煤/油/气）、宏观、下游 MTO 开工、"
                     "地缘与政策等竞争性解释。本工作簿只做“路径描述 + 相对基准比较”。"),
        ("六、证据等级", "E1 一手官方 / E2 行业权威 / E3 综合媒体 / E4 机构口径 / E5 待确认。"
                     "事件列每条须有原文摘录与链接，否则视为 E5。"),
        ("七、样本量警告", "可比样本少于 10 个时，均值/分位数的抽样误差很大，不能据此推断“停车事件的普遍规律”。"
                       "报告必须显著提示样本量。"),
    ]
    r = 4
    for k, v in lines:
        ws.cell(row=r, column=1, value=k).font = Font(bold=True, size=10, color=BLUE)
        ws.cell(row=r, column=2, value=v).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 46
        r += 1
    _widths(ws, [24, 110])
    if meta.get("simulated"):
        c = ws.cell(row=r + 1, column=1, value="注意：本工作簿含模拟/演示数据，不可作为正式研究结论。")
        c.fill = PatternFill("solid", fgColor=BAD)

    # ---- 01 事件样本 ----
    ws = wb.create_sheet("01 事件样本")
    cols = ["事件编号", "事件名称", "企业", "装置", "产品", "单套产能(万吨/年)", "地区", "国家",
            "事件类型", "企业公告日", "市场首次获知日", "实际停车日", "重启日", "纳入", "可比", "筛选理由",
            "证据等级", "产品核验", "来源标题", "来源媒体", "来源链接", "原文摘录", "备注"]
    _title(ws, "事件样本表（可直接编辑；修改后重跑 build_all 生效）",
           "黄色=产能未披露（缺口）；红色=产品核验失败或剔除样本")
    _hdr(ws, 3, cols)
    rows = []
    for e in ev_csv:
        rows.append([
            e.get("event_id", ""), e.get("event_name", ""), e.get("company", ""), e.get("unit_name", ""),
            e.get("product", ""), core.parse_float(e.get("capacity_wt")), e.get("region", ""), e.get("country", ""),
            core.normalize_event_type(e.get("event_type")), e.get("announce_date", ""), e.get("first_market_date", ""),
            e.get("actual_start_date", ""), e.get("actual_restart_date", ""), e.get("include_flag", ""),
            e.get("in_comparison_set", ""), e.get("screening_reason", ""), e.get("evidence_grade", ""),
            e.get("product_verified", ""), e.get("source_title", ""), e.get("source_media", ""),
            e.get("source_url", ""), e.get("quote", ""), e.get("notes", ""),
        ])
    _body(ws, 4, rows, wrap_cols=(2, 16, 22, 23))
    for i in range(4, 4 + len(rows)):
        if ws.cell(row=i, column=6).value is None:
            ws.cell(row=i, column=6).fill = PatternFill("solid", fgColor=WARN)
        if ws.cell(row=i, column=18).value == "否":
            for c in range(1, 24):
                ws.cell(row=i, column=c).fill = PatternFill("solid", fgColor=BAD)
    _widths(ws, [12, 30, 22, 24, 8, 14, 10, 10, 12, 13, 14, 13, 13, 8, 8, 40, 9, 9, 32, 14, 42, 52, 36])
    ws.freeze_panes = "C4"

    # ---- 02 日期口径对照 ----
    ws = wb.create_sheet("02 日期口径对照")
    _title(ws, "三种日期对照与锚定日顺延说明",
           "同一事件的三类日期不同时，必须以专列区分；锚定日=事件日映射到首个可交易日")
    _hdr(ws, 3, ["事件编号", "企业", "装置", "公告日", "首次获知日", "实际停车日", "重启日",
                 "公告→获知(天)", "获知→实际(天)", "锚定方式", "锚定日", "是否顺延", "顺延说明"])
    rows = []
    for r in res:
        a = core.parse_date(r.get("announce_date"))
        f = core.parse_date(r.get("first_market_date"))
        s = core.parse_date(r.get("actual_start_date"))
        anchor = r.get("anchor_date", "")
        d_txt = ""
        if anchor and f and anchor != f:
            d_txt = f"市场首次获知日 {f} 非交易日，顺延至首个交易日 {anchor}"
        elif anchor and s and state_anchor_is_actual(r) and anchor != s:
            d_txt = f"实际停车日 {s} 非交易日，顺延至首个交易日 {anchor}"
        import datetime as _d

        def dd(x, y):
            if not x or not y:
                return None
            return (_d.date.fromisoformat(y) - _d.date.fromisoformat(x)).days
        rows.append([r.get("event_id"), r.get("company"), r.get("unit_name"), a or "", f or "", s or "",
                     r.get("actual_restart_date") or "", dd(a, f), dd(f, s),
                     r.get("anchor_kind", ""), anchor, "是" if d_txt else "否", d_txt])
    _body(ws, 4, rows)
    _widths(ws, [12, 24, 26, 13, 13, 13, 13, 14, 14, 12, 13, 9, 34])

    # ---- 03 价格路径 ----
    ws = wb.create_sheet("03 价格路径")
    _title(ws, "逐事件价格路径与收益", "收益为 %%；“缺失”表示数据不足以覆盖该窗口，不补数")
    _hdr(ws, 3, ["事件编号", "锚定日", "t0收盘", "事件日收益%", "t+1日", "t+1收益%", "t+5日", "t+5收益%",
                 "t+10日", "t+10收益%", "t+20日", "t+20收益%", "前20日起点", "t-10%", "t-5%", "t-3%", "t-1%",
                 "是否可比", "缺口说明"])
    rows = []
    for r in res:
        def g(k):
            v = r.get(k)
            if v in (None, ""):
                return "缺失"
            try:
                return round(float(v), 2)
            except Exception:
                return v
        wd = r.get("window_dates")
        wd = json.loads(wd) if isinstance(wd, str) and wd.startswith("{") else (wd or {})
        rows.append([r.get("event_id"), r.get("anchor_date"), g("t0_close"), g("ret_t0_pct"),
                     wd.get("t+1") or "越界", g("ret_t+1_pct"), wd.get("t+5") or "越界", g("ret_t+5_pct"),
                     wd.get("t+10") or "越界", g("ret_t+10_pct"), wd.get("t+20") or "越界", g("ret_t+20_pct"),
                     r.get("pre_start_date") or "缺失", g("ret_-10d_pct"), g("ret_-5d_pct"),
                     g("ret_-3d_pct"), g("ret_-1d_pct"), "是" if r.get("in_comparison_set") in ("True", "1", "true", True) else "否",
                     r.get("gaps", "")])
    _body(ws, 4, rows, wrap_cols=(19,))
    _widths(ws, [12, 12, 10, 12, 12, 11, 12, 11, 12, 11, 12, 11, 13, 9, 9, 9, 9, 9, 44])

    # ---- 04 分布统计 ----
    ws = wb.create_sheet("04 分布统计")
    _title(ws, "各窗口收益分布", "小样本下分位数不稳定，请结合 n 与置信区间阅读")
    _hdr(ws, 3, ["窗口", "n", "均值%", "中位数%", "标准差", "P05%", "P25%", "P75%", "P95%", "最小值%", "最大值%",
                 "上涨数", "下跌数", "上涨占比", "符号检验p", "自助法CI下限", "自助法CI上限", "解读"])
    rows = []
    for label, blk in (("全样本", stats.get("all", {})), ("去重叠子样本", stats.get("dedup", {}))):
        for w, b in (blk.get("windows") or {}).items():
            ar = b.get("raw_return", {})
            if not ar.get("n"):
                rows.append([f"{label} {w}", 0, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "样本不足"])
                continue
            bt = b.get("abnormal_boot_ci_mean") or [None, None]
            note = ""
            if blk.get("n", 0) < 10:
                note = "n<10：分位数与检验不稳定，仅描述"
            rows.append([f"{label} {w}", ar["n"], round(ar["mean"], 2), round(ar["median"], 2),
                         round(ar["sd"], 2) if ar.get("sd") is not None else "", round(ar["p05"], 2), round(ar["p25"], 2),
                         round(ar["p75"], 2), round(ar["p95"], 2), round(ar["min"], 2), round(ar["max"], 2),
                         ar["positive_n"], ar["negative_n"], round(ar["win_rate"], 3),
                         (round(b.get("abnormal_sign_test", {}).get("sign_test_p"), 4)
                          if b.get("abnormal_sign_test", {}).get("sign_test_p") is not None else "n不足"),
                         round(bt[0], 2) if bt and bt[0] is not None else "",
                         round(bt[1], 2) if bt and bt[1] is not None else "", note])
    _body(ws, 4, rows, wrap_cols=(18,))
    _widths(ws, [20, 6, 9, 10, 9, 9, 9, 9, 9, 10, 10, 8, 8, 9, 11, 13, 13, 30])

    # ---- 05 异常收益 ----
    ws = wb.create_sheet("05 异常收益")
    _title(ws, "相对基准的异常收益", "AR = 标的区间收益 − (alpha + beta × 基准区间收益)，估计窗口为事件前 20 交易日")
    has_bench = any(r.get("beta") not in (None, "") for r in res)
    _hdr(ws, 3, ["事件编号", "锚定日", "beta", "alpha", "估计样本", "t+1标的", "t+1基准", "t+1异常",
                 "t+5标的", "t+5基准", "t+5异常", "t+10异常", "t+20异常", "说明"])
    rows = []
    for r in res:
        def g(k):
            v = r.get(k)
            try:
                return round(float(v), 2) if v not in (None, "") else ""
            except Exception:
                return ""
        rows.append([r.get("event_id"), r.get("anchor_date"), g("beta"), g("alpha"), r.get("est_n", ""),
                     g("ret_t+1_pct"), g("benchmark_ret_t+1_pct"), g("ar_t+1_pct"),
                     g("ret_t+5_pct"), g("benchmark_ret_t+5_pct"), g("ar_t+5_pct"),
                     g("ar_t+10_pct"), g("ar_t+20_pct"),
                     "" if has_bench else "未配置基准，本表为空（见 08 数据与来源）"])
    _body(ws, 4, rows)
    _widths(ws, [12, 12, 8, 8, 9, 9, 9, 9, 9, 9, 9, 10, 10, 40])
    if not has_bench:
        ws.cell(row=4 + len(rows) + 1, column=1, value="如何补齐基准：在 data/benchmark.csv 放 date,close（与标的同一交易日历），重跑 build_all.py。"
                ).fill = PatternFill("solid", fgColor=WARN)

    # ---- 06 样本筛选 ----
    ws = wb.create_sheet("06 样本筛选")
    _title(ws, "样本筛选判定明细", "每条事件的纳入/剔除依据，可逐条审计")
    _hdr(ws, 3, ["事件编号", "事件", "产品核验", "单套产能≥阈值", "证据等级达标", "重启方向", "有可对齐日期",
                 "最终纳入", "筛选理由", "原始判断"])
    rows = []
    for e in ev_csv:
        cap = core.parse_float(e.get("capacity_wt"))
        ver = core.parse_flag(e.get("product_verified"), None)
        typ = core.normalize_event_type(e.get("event_type"))
        rows.append([e.get("event_id"), e.get("event_name"),
                     "通过" if ver is not False else "不通过",
                     ("未披露" if cap is None else (f"是({cap:.0f})" if cap >= (meta.get("capacity_threshold_wt") or 0) else f"否({cap:.0f})")),
                     e.get("evidence_grade", ""), "重启(方向相反)" if typ == "restart" else "停车",
                     "是", e.get("in_comparison_set", ""), e.get("screening_reason", ""), e.get("include_flag", "")])
    _body(ws, 4, rows, wrap_cols=(2, 9))
    _widths(ws, [12, 34, 10, 16, 12, 16, 14, 10, 56, 10])

    # ---- 07 事件重叠 ----
    ws = wb.create_sheet("07 事件重叠")
    _title(ws, "事件窗口重叠矩阵", "重叠样本路径不独立；去重叠子样本按“先发生者保留”规则生成")
    pairs = overlap.get("overlap_pairs", [])
    _hdr(ws, 3, ["保留事件", "与其重叠的事件", "说明"])
    rows = [[p.get("kept"), p.get("excluded"), "窗口[t-5,t+20]相交"] for p in pairs] or [["—", "—", "未检测到重叠"]]
    _body(ws, 4, rows)
    r = 4 + len(rows) + 2
    ws.cell(row=r, column=1, value="去重叠子样本保留事件：").font = Font(bold=True)
    ws.cell(row=r, column=2, value="、".join(overlap.get("kept_in_dedup_subsample", [])) or "—")
    _widths(ws, [16, 20, 40])

    # ---- 08 数据与来源 ----
    ws = wb.create_sheet("08 数据与来源")
    _title(ws, "数据序列、来源与缺口", "每个序列都要能回答：口径、频率、覆盖区间、来源")
    _hdr(ws, 3, ["序列", "口径", "频率", "覆盖区间", "来源", "备注/缺口"])
    fut = prov.get("futures", {})
    spot = prov.get("spot", {})
    news = prov.get("news", {})
    rows = [
        ["甲醇期货主力连续（后向复权）", meta.get("futures", "主力连续"), "日度（交易日）",
         f"{fut.get('contracts', {}).get('start','')} ~ {fut.get('contracts', {}).get('end','')}",
         "新浪财经 InnerFuturesNewService.getDailyKLine（逐合约），本地重建主力",
         "换月日后向复权，避免换月价差污染窗口收益"],
        ["甲醇期货主力连续（未复权）", "主力连续原始价", "日度", "同上", "同上", "仅作对照"],
        ["甲醇期货 MA0 连续", "交易所主力连续", "日度", f"{fut.get('ma0',{}).get('start','')} ~ {fut.get('ma0',{}).get('end','')}",
         "新浪财经", "换月跳空未处理，不作为事件研究主口径"],
        ["甲醇现货（基准价）", "生意社基准价，江苏省市场价 合格品", "日度",
         f"{spot.get('start','')} ~ {spot.get('end','')}", "生意社(100ppi) 基准价图接口",
         "公开接口仅返回最近约 93 天；2019-2026 逐日现货历史缺失 → 基差路径无法覆盖历史事件"],
        ["事件新闻语料", "媒体/研报原文摘录", "事件驱动", f"{news.get('coverage','')}",
         "东方财富新闻搜索（search-api-web.eastmoney.com）", "检索深度受分页限制；2019-2025 装置级停车文本缺失"],
        ["基准指数", "等权化工期货主力指数（自建）", "日度", "见 data/benchmark_meta.json", "本地用 L/PP/TA/EG/MA 主力重建",
         "自建基准，非交易所官方指数"],
    ]
    _body(ws, 4, rows, wrap_cols=(2, 5, 6))
    _widths(ws, [26, 30, 12, 28, 40, 46])

    # ---- 09 现货与基差 ----
    ws = wb.create_sheet("09 现货与基差")
    _title(ws, "现货与基差（严格口径：数据缺失则留空）",
           "补齐方法：把逐日现货价存入 data/spot.csv（列：date,spot），重跑 build_all.py 即自动计算基差")
    _hdr(ws, 3, ["事件编号", "锚定日", "期货收盘", "现货价", "基差(现货-期货)", "基差率%",
                 "t+5基差变化", "t+5基差率变化", "状态"])
    rows = []
    for r in res:
        rows.append([r.get("event_id"), r.get("anchor_date"), r.get("t0_close"), "", "", "", "", "",
                     "现货历史缺失，未计算" if not os.path.exists(os.path.join(project_dir, "data", "spot.csv"))
                     else "现货文件存在，请重跑 build_all"])
    _body(ws, 4, rows)
    _widths(ws, [12, 12, 12, 12, 16, 10, 12, 16, 30])

    # ---- 10 参数假设 ----
    ws = wb.create_sheet("10 参数假设")
    _title(ws, "口径参数（复现同一结果所需）")
    _hdr(ws, 3, ["参数", "取值", "含义"])
    cfg = {
        "品种": meta.get("product", ""), "期货口径": meta.get("futures", ""),
        "事件日定义": "市场首次获知日（first_market_date）", "事件窗口": "t+1 / t+5 / t+10 / t+20 交易日",
        "估计窗口": "事件前 20 个交易日（最少 10 个观测）", "基准": "同等权化工期货指数（自建）",
        "异常收益方法": "市场模型 AR = R − (alpha + beta×R_benchmark)；样本不足时用均值调整",
        "产能门槛（万吨/年）": meta.get("capacity_threshold_wt") or "按事件类型分设（国内≥60，中东≥100）",
        "证据等级下限": "E3", "重叠窗口": "t-5 ~ t+20", "去重叠规则": "按事件时间先后，保留先发生者",
        "换月处理": "按成交量选主力，换月日后向复权（roll-over）",
        "缺失处理": "留空并标注，不插值、不前向填充",
    }
    _body(ws, 4, [[k, str(v), ""] for k, v in cfg.items()])
    _widths(ws, [24, 60, 40])

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    p = build(args.project, args.out)
    print(f"[OK] Excel -> {p}")


if __name__ == "__main__":
    main()
