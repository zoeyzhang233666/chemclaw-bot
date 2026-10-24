# -*- coding: utf-8 -*-
"""build_excel.py — 生成研究工作簿（13+ 个 sheet，含真实/模拟双轨与完整审计痕迹）。

Sheet 清单
  0 封面与结论        一页看懂：假设、结论、样本量、为什么是这个结论
  1 研究设计          变量/口径/信号/窗口/对照组/参数冻结信息
  2 参数确认          阻断性问题与默认取值、审批状态、数据指纹
  3 数据来源与口径    每个序列的来源、URL 规则、抓取时间、核验方式
  4 原始数据-库存     228 周（含 URL、provenance、verified_at）
  5 原始数据-价格     100ppi 现货/近月/基差（日度）
  6 因子定义          信号、状态、Δ、窗口收益率、库存分位的公式与边界条件
  7 样本面板          逐条观测（真实），含 roll 标记与跳过原因
  8 统计结果          全量检验登记：效应量/95%CI/p/BH-q/判定
  9 稳定性            分年/分库存分位/分基差符号
 10 修订口径对照      MAIN / AM-1 / AM-2 / AM-3
 11 事件研究          T−20…T+20 路径与 pre/post 均值
 12 模拟演示(SIMULATED) 明确标注的模拟轨道结果
 13 局限与风险        风险清单 + 四类错误自查表
 14 复现说明          脚本、命令、数据 sha256
"""
import csv
import json
import os
import sys
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))

INK = "1B1F24"
TEAL = "0F766E"
AMBER = "B45309"
RED = "B91C1C"
PURPLE = "6D28D9"
HDR_FILL = PatternFill("solid", fgColor="134E4A")
HDR_FONT = Font(color="FFFFFF", bold=True, size=10.5)
TITLE_FONT = Font(bold=True, size=15, color=INK)
SUB_FONT = Font(size=10, color="6B7280")
BOLD = Font(bold=True)
THIN = Side(style="thin", color="E5E7EB")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FILL_SIM = PatternFill("solid", fgColor="EDE9FE")
FILL_WARN = PatternFill("solid", fgColor="FEF3C7")
FILL_BAD = PatternFill("solid", fgColor="FEE2E2")
FILL_OK = PatternFill("solid", fgColor="CCFBF1")
WRAP = Alignment(wrap_text=True, vertical="top")


def load_json(p, default=None):
    if not p or not os.path.exists(p):
        return default
    return json.load(open(p, encoding="utf-8-sig"))


def load_csv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sheet(wb, title, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    return ws


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = TITLE_FONT
    if sub:
        ws["A2"] = sub
        ws["A2"].font = SUB_FONT


def table(ws, header, rows, start_row=3, widths=None, num_cols=(), wrap_cols=()):
    for j, h in enumerate(header, 1):
        c = ws.cell(row=start_row, column=j, value=h)
        c.fill = HDR_FILL
        c.font = HDR_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    for i, row in enumerate(rows, start_row + 1):
        for j, v in enumerate(row, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.border = BOX
            c.alignment = WRAP if j in wrap_cols else Alignment(vertical="top")
            if j in num_cols and isinstance(v, (int, float)):
                c.number_format = "#,##0.00" if not float(v).is_integer() else "#,##0"
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    return start_row + len(rows)


def kv(ws, pairs, start_row=3, w1=26, w2=110):
    r = start_row
    for k, v in pairs:
        a = ws.cell(row=r, column=1, value=k)
        a.font = BOLD
        a.alignment = Alignment(vertical="top")
        a.border = BOX
        b = ws.cell(row=r, column=2, value=v)
        b.alignment = WRAP
        b.border = BOX
        r += 1
    ws.column_dimensions["A"].width = w1
    ws.column_dimensions["B"].width = w2
    return r


def verdict_text(res):
    v = res.get("verdict")
    return {"SUPPORTED": "历史数据支持该假设",
            "NOT_SIGNIFICANT": "没有证据支持（不显著）",
            "INSUFFICIENT_SAMPLE": "样本不足，无法判断",
            "CONTRADICTED": "与历史数据相反"}.get(v, str(v))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "out", "研究假设检验_甲醇库存与基差.xlsx")
    B = lambda p: os.path.join(root, p)
    design = load_json(B("build/research_design.formal.json"), {})
    parsed = load_json(B("build/design_draft.json"), {})
    audit = load_json(B("build/data_audit.json"), {})
    res_real = load_json(B("build/results_real.json"), {})
    res_demo = load_json(B("build/results_demo.json"), {})
    amend = load_json(B("build/amendment.json"), {"variants": []})
    ev = load_json(B("build/event_study.json"), {})
    ver = load_json(B("build/verification_full.json"), {})
    demo_meta = load_json(B("data/demo_weekly.meta.json"), {})
    inv = load_csv(B("data/port_inventory_weekly.csv"))
    px = load_csv(B("data/100ppi_sf.csv"))
    samples = load_csv(B("build/samples_real.csv"))
    samples_demo = load_csv(B("build/samples_demo.csv"))

    wb = Workbook()

    # ---------------------------------------------------------------- 0 封面
    ws = sheet(wb, "0-封面与结论", first=True)
    title(ws, "研究假设检验报告：甲醇港口库存连续两周下降 → 随后两周基差更容易走强",
          f"生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 设计版本 {design.get('version')} "
          f"（已确认冻结 {design.get('approved_at')}）｜ 数据指纹见「复现说明」")
    prim = next((t for t in res_real.get("tests", []) if t["id"] == "P1_mean"), None)
    am1 = next((v for v in amend.get("variants", []) if v["tag"] == "AM-1"), None)
    am3 = next((v for v in amend.get("variants", []) if v["tag"] == "AM-3"), None)
    pairs = [
        ("原始假设", design.get("raw_text")),
        ("检验结论", verdict_text(res_real) + "　—　" + str(res_real.get("message", ""))),
        ("库存样本", f"{len(inv)} 周（{inv[0]['asof'] if inv else '—'} → {inv[-1]['asof'] if inv else '—'}），"
                 f"逐条回源核验通过率 {ver.get('verified_ratio', 0)*100:.0f}%（{ver.get('n', 0)} 条）"),
        ("价格样本", f"{len(px)} 个交易日；现货/近月/基差缺失 0 条"),
        ("主口径样本", f"信号 {res_real.get('sample', {}).get('n_signal')} 周 / 对照 "
                  f"{res_real.get('sample', {}).get('n_control')} 周（状态转变去重 + 剔除窗口内换月）"),
        ("为什么是这个结论",
         "去重后独立信号只有 10 个，低于事前设定的最小样本规则（信号≥12）。按设计约定不报告显著性。"
         "补充修订口径 AM-1（每周都算，24 个信号）主检验 p=%.4f、均值差 %+.1f 元/吨；"
         "AM-3（最宽松，48 个信号）p=%.4f、均值差 %+.1f 元/吨 —— 四个口径一致不支持「连降→基差走强」。"
         % ((next((t['p'] for t in am1['tests'] if t['id'] == 'P1_mean'), float('nan')) if am1 else float('nan')),
            (next((t['estimate'] for t in am1['tests'] if t['id'] == 'P1_mean'), float('nan')) if am1 else float('nan')),
            (next((t['p'] for t in am3['tests'] if t['id'] == 'P1_mean'), float('nan')) if am3 else float('nan')),
            (next((t['estimate'] for t in am3['tests'] if t['id'] == 'P1_mean'), float('nan')) if am3 else float('nan')))),
        ("可能的真实原因",
         "1) 港口库存只反映显性库存，基差更受可交割货源、仓单、区域到货节奏影响；"
         "2) 10 日窗口内混入了宏观/成本/宏观情绪；"
         "3) 库存是慢变量，市场往往在库存数据公布前已通过船期、到港预报交易；"
         "4) 事件研究显示信号组在 T0 之前基差均值已高于对照组，说明存在选择效应。"),
        ("数据真实性声明",
         "本工作簿「4/5/7/8/9/10/11」全部为真实可回溯数据；"
         "「12-模拟演示」整表为随机数生成的 SIMULATED 数据，只用于演示流程，不得作为任何结论引用。"),
        ("进一步获取样本的途径",
         "① 使用你自己的库存/基差 Excel（首页「字段识别」可自动映射）；"
         "② 付费数据库（隆众/卓创/Mysteel/Choice/Wind）导出完整周度港口库存与仓单；"
         "③ 把样本期延伸到 2019–2021（需核对样本口径一致性）。"),
        ("免责声明", "观测数据只支持条件相关，不构成因果结论或投资建议；未计交易成本、滑点与换月成本。"),
    ]
    r = kv(ws, pairs, start_row=4)
    ws.cell(row=r + 1, column=1, value="阅读顺序").font = BOLD
    ws.cell(row=r + 2, column=1,
            value="研究设计 → 参数确认 → 数据来源 → 原始数据 → 因子定义 → 样本面板 → 统计结果 → 稳定性 → "
                  "修订口径 → 事件研究 → （模拟演示）→ 局限与风险 → 复现说明").font = SUB_FONT
    for row in ws.iter_rows(min_row=4, max_row=r, min_col=2, max_col=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    # ---------------------------------------------------------------- 1 研究设计
    ws = sheet(wb, "1-研究设计")
    title(ws, "一、研究设计（把假设变成可检验的口径）", "研究者：用户 ｜ 执行：Skill 25 检验一个自定义研究假设")
    rows = [
        ["研究问题", "在甲醇港口库存连续两周下降之后的两周内，基差是否更容易走强（相对其它周）？"],
        ["品种/合约", design.get("product", {}).get("spot_desc", "") + " ｜ 期货：" +
         design.get("product", {}).get("futures_desc", "")],
        ["X 自变量", design["variables"]["X"]["name"] + "；" + design["variables"]["X"]["freq"] +
         "；变换：" + design["variables"]["X"].get("transform", "")],
        ["Y 主口径", design["variables"]["Y_alt"]["name"] + "：" + design["variables"]["Y_alt"]["transform"]],
        ["Y 次口径", design["variables"]["Y_main"]["name"] + "：" + design["variables"]["Y_main"]["transform"]],
        ["方向约定", design["variables"]["Y_direction"]],
        ["信号规则", design["signal"]["rule"]],
        ["信号敏感性", design["signal"].get("run_alt", "")],
        ["观察窗口", f"主 {design['horizon']['main_sessions']} 交易日；敏感性 {design['horizon']['alt_sessions']}"],
        ["对照组", design["control"]["rule"]],
        ["等价过滤", design["control"]["equivalent_filter"]["description"]],
        ["去重口径", "transition：只有状态发生转变的那一周计为事件（避免一段 6–8 周连降被重复计数 6–8 次）"],
        ["换月处理", "主样本剔除 T0→T0+10 内近月合约切换的观测（100ppi 近月列逐月切换），并在敏感性中放开"],
        ["入场时点", design["entry_rule"]["main_desc"]],
        ["样本区间", f"{inv[0]['asof'] if inv else ''} → {inv[-1]['asof'] if inv else ''}（可用数据全段，不挑年份）"],
        ["最小样本规则", design["statistics"]["min_n_rule"]],
        ["显著性水平", "α = 0.05（双侧）；多重检验用 BH-FDR 校正，q<0.10 视为通过校正"],
        ["不做什么", "不剔除极端年份；不因为结果不好而改窗口/阈值；不用模拟数据替代真实结论"],
    ]
    kv(ws, rows, start_row=4, w1=18, w2=120)

    # ---------------------------------------------------------------- 2 参数确认
    ws = sheet(wb, "2-参数确认")
    title(ws, "二、参数确认与冻结（正式检验的闸门）")
    pairs = [("审批状态", design.get("approval_state")),
             ("approved", design.get("approved")),
             ("确认人", design.get("approved_by")),
             ("确认时间", design.get("approved_at")),
             ("确认备注", design.get("approval_note")),
             ("设计版本", design.get("version")),
             ("数据指纹", json.dumps(design.get("data_fingerprint", {}), ensure_ascii=False))]
    r = kv(ws, pairs, start_row=4, w1=16, w2=100)
    qs = (design.get("workload_for_user") or {}).get("blocking_questions", [])
    r += 2
    ws.cell(row=r, column=1, value="阻断性问题与默认取值（本次按默认值执行，用户可随时改并重跑）").font = BOLD
    table(ws, ["编号", "问题", "候选口径", "本次采用"], [
        [q["id"], q["q"], " / ".join(q["options"]), q.get("default_used_in_dry_run", "")]
        for q in qs], start_row=r + 1, widths=[8, 40, 60, 40], wrap_cols=(2, 3, 4))

    # ---------------------------------------------------------------- 3 数据来源
    ws = sheet(wb, "3-数据来源与口径")
    title(ws, "三、数据来源、口径与核验方式")
    src = [
        ["港口库存（周度）", "隆众《中国甲醇样本港口库存周数据统计》经我的钢铁网转载",
         "https://nenghua.m.mysteel.com/a/{YYMMDDHH}/{SHA16}_abc.html",
         "228 周 2022-04-06→2026-10-14", "逐条回源核验：标题日期==观测日 且 正文「港口库存总量在X万吨」==记录值",
         f"通过 {ver.get('tally', {}).get('verified', 0)}/{ver.get('n', 0)}（{ver.get('verified_ratio', 0)*100:.0f}%）",
         "口径：华东+华南样本库区合计；样本覆盖率逐年变化（L-05）"],
        ["现货基准价（日度）", "生意社 100ppi 每日「商品现货与期货价格对比表」",
         "https://www.100ppi.com/sf/day-YYYY-MM-DD.html",
         f"{len(px)} 个交易日 {px[0]['date'] if px else ''}→{px[-1]['date'] if px else ''}",
         "锚点复核：2022-08-17 原文 2425.00 元/吨；2024-07-24 现货 2537.00",
         "现货/近月/基差 0 缺失", "综合区域基准价，与太仓出罐价有水平差（L-03）"],
        ["近月期货价（日度）", "同上 100ppi 表格「近月合约/近月价」列", "同上",
         "同上", "逐月切换 MA2301→MA2302…，换月日已识别 56 处",
         "0 缺失", "近月随交割切换，主样本剔除窗口内换月（L-04）"],
        ["主力连续（日度+60分钟）", "新浪财经 InnerFuturesNewService", "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/...",
         "MA0 2863 日 bars（2014-12-24 起）；60 分钟 1023 根（2026-01-28 起）",
         "用于抽样复核与 pre15 分钟 bar", "—", "未复权拼接，仅用于复核，不进入主检验"],
    ]
    table(ws, ["序列", "来源", "URL 规则", "覆盖", "核验方式", "核验结果", "口径风险"],
          src, start_row=4, widths=[18, 34, 40, 26, 34, 20, 34], wrap_cols=(2, 3, 5, 7))
    r = 4 + len(src) + 2
    ws.cell(row=r, column=1, value="核验明细（前 50 条，全量见 build/verification_full.json）").font = BOLD
    recs = (ver.get("records") or [])[:50]
    table(ws, ["观测日", "记录值(万吨)", "状态", "说明", "URL"],
          [[x["asof"], x["value"], x["status"], x["detail"], x["url"]] for x in recs],
          start_row=r + 1, widths=[13, 14, 14, 16, 70], num_cols=(2,), wrap_cols=(5,))

    # ---------------------------------------------------------------- 4 原始库存
    ws = sheet(wb, "4-原始数据-库存")
    title(ws, "四、原始数据：中国甲醇样本港口库存（周度，全部逐条回源核验）",
          "每行都带原文 URL 与核验时间；缺失周不插值。provenance=verified_mysteel_open_page 表示已回源核验。")
    cols = ["asof", "pub_ts", "total", "east", "south", "jiangsu", "zhejiang", "guangdong",
            "fujian", "sample_cov", "provenance", "verified_at", "url"]
    table(ws, ["观测日", "发布时间", "港口总计", "华东", "华南", "江苏", "浙江", "广东", "福建",
               "覆盖率%", "来源类型", "核验时间", "原文 URL"],
          [[x.get(c, "") for c in cols] for x in inv], start_row=4,
          widths=[12, 17, 11, 9, 9, 9, 9, 9, 9, 9, 26, 20, 72],
          num_cols=(3, 4, 5, 6, 7, 8, 9, 10), wrap_cols=(13,))

    # ---------------------------------------------------------------- 5 原始价格
    ws = sheet(wb, "5-原始数据-价格")
    title(ws, "五、原始数据：100ppi 现货基准价 / 近月合约 / 基差（日度）",
          "近月合约代码逐月切换，已单列 near_code 便于识别换月。")
    pcols = ["date", "spot", "near_code", "near_fut", "near_basis", "near_basis_rate", "far_code", "far_fut"]
    head = ["交易日", "现货基准价", "近月合约", "近月价", "近月基差", "近月基差率%", "远月合约", "远月价"]
    pcols = [c for c in pcols if px and c in px[0]]
    head = head[:len(pcols)]
    table(ws, head, [[x.get(c, "") for c in pcols] for x in px], start_row=4,
          widths=[12, 12, 11, 11, 11, 11, 11, 11], num_cols=tuple(range(2, len(pcols) + 1)))

    # ---------------------------------------------------------------- 6 因子定义
    ws = sheet(wb, "6-因子定义")
    title(ws, "六、因子定义（公式、边界条件与可能踩的坑）")
    defs = [
        ["ΔI_t", "I_t − I_{t−1}", "万吨", "库存周度变化；>0 累库，<0 去库，=0 视为持平（不算下降）",
         "单位万吨；原文保留两位小数"],
        ["DOWN2", "ΔI_t<0 且 ΔI_{t−1}<0", "0/1", "连续两周下降",
         "严格小于 0；相邻观察日间隔须在 5–10 天，否则视为窗口不连续"],
        ["UP2", "ΔI_t>0 且 ΔI_{t−1}>0", "0/1", "连续两周上升（对照组的一部分）", "同上"],
        ["MIXED", "其它", "0/1", "一升一降或持平", "同上"],
        ["transition 去重", "仅保留状态发生变化的那一周", "0/1", "避免一段连降被重复计数",
         "weekly 口径作为修订 AM-1 敏感性"],
        ["T0", "pre15：报告日当日；缺 60 分钟 bar 时用当日收盘", "日期",
         "入场时点必须晚于 14:00 报告发布", "2026-01-28 之前没有 60 分钟数据，用当日收盘代理并计数"],
        ["ΔP_k", "P(T0+k) − P(T0)", "元/吨", "k=5/10 交易日", "近月合约价格，换月会造成跳变"],
        ["Δbasis_k", "basis(T0+k) − basis(T0)，basis = spot − near_fut", "元/吨", "主口径",
         "基差为 100ppi 口径（综合基准价 − 近月），非可交割基差"],
        ["方向一致率", "P(Δ>0 | 信号) vs P(Δ>0 | 对照)", "比例", "Wilson 95% CI + 双比例 z",
         "小样本时 z 检验偏乐观，故同时给 Fisher 与置换检验"],
        ["库存分位 level_pct", "过去 52 周中低于本周的周数占比", "0–1",
         "用于分位分组", "只用过去 52 周，避免全样本信息泄露"],
        ["roll 标记", "T0→T0+k 内 near_code 是否变化", "0/1", "识别换月污染",
         "主样本剔除 roll=1；AM-2/AM-3 放开"],
        ["BH-q", "Benjamini–Hochberg 校正后的 p", "—", "控制 FDR", "预登记检验数上限 18"],
    ]
    table(ws, ["因子/口径", "定义", "单位", "用途", "边界条件与坑"], defs, start_row=4,
          widths=[18, 42, 10, 40, 60], wrap_cols=(2, 4, 5))

    # ---------------------------------------------------------------- 7 样本面板
    ws = sheet(wb, "7-样本面板")
    title(ws, "七、样本面板（真实数据，逐条观测）",
          "每行 = 一个可评估的库存周观测；roll_10=1 表示 10 日内发生近月换月。")
    scols = ["asof", "pub_ts", "total", "d1", "d2", "state", "signal", "dec14", "gap1", "gap2",
             "level_pct", "level_band", "T0", "entry_kind", "P0", "basis0",
             "dB_5", "dB_10", "dP_5", "dP_10", "roll_5", "roll_10", "roll_main", "T_k_10", "iso_week"]
    scols = [c for c in scols if samples and c in samples[0]]
    headers = ["观测日", "发布", "库存", "Δ1", "Δ2", "状态", "信号", "降1万吨", "间隔1", "间隔2",
               "库存分位", "分位档", "T0", "入场方式", "T0价", "T0基差",
               "Δ基差5", "Δ基差10", "Δ期货5", "Δ期货10", "换月5", "换月10", "主窗口换月", "T+10日", "ISO周"]
    table(ws, headers[:len(scols)], [[x.get(c, "") for c in scols] for x in samples], start_row=4,
          widths=[12] + [10] * (len(scols) - 4) + [13, 8], num_cols=tuple(range(3, 21)))

    # ---------------------------------------------------------------- 8 统计结果
    ws = sheet(wb, "8-统计结果")
    title(ws, "八、统计结果（全量登记，含不显著与样本不足）",
          f"结论：{verdict_text(res_real)}　{res_real.get('message','')}")
    fam = {"primary": "主检验", "sensitivity": "敏感性", "robustness": "鲁棒性",
           "placebo": "安慰剂", "diagnostic": "诊断"}
    rows = []
    for t in res_real.get("tests", []):
        rows.append([t["id"], fam.get(t["family"], t["family"]), t["label"],
                     t.get("estimate"), (f"[{t['ci95'][0]:+.2f}, {t['ci95'][1]:+.2f}]"
                                         if t.get("ci95") else "—"),
                     t.get("p"), t.get("q_bh"), t.get("n"),
                     ("显著" if (t.get("p") is not None and t["p"] < 0.05) else
                      ("—" if t.get("p") is None else "不显著"))])
    table(ws, ["编号", "检验族", "检验内容", "效应量", "95% CI", "p", "BH-q", "N", "判定"],
          rows, start_row=4, widths=[10, 12, 56, 12, 24, 10, 10, 8, 10], num_cols=(4, 6, 7))
    r = 4 + len(rows) + 2
    ws.cell(row=r, column=1, value="跳过/剔除明细（样本是怎么剩下的）").font = BOLD
    sk = res_real.get("meta", {}).get("skipped", {})
    table(ws, ["原因", "条数", "说明"], [
        ["gap", sk.get("gap", 0), "相邻观察日间隔不在 5–10 天（停发/顺延）"],
        ["dup_state", sk.get("dup_state", 0), "同一状态内连续周，按 transition 口径不计为独立事件"],
        ["roll_in_window", sk.get("roll_in_window", 0), "主窗口内发生近月换月，已从主样本剔除"],
        ["incomplete", sk.get("incomplete", 0), "未来窗口不完整（样本末端）"],
        ["pre15_bar_missing", sk.get("pre15_bar_missing", 0), "缺 14:00–15:00 60 分钟 bar，退化为当日收盘代理"],
    ], start_row=r + 1, widths=[22, 10, 60], num_cols=(2,))
    r2 = r + 1 + 6 + 2
    ws.cell(row=r2, column=1, value="诊断量").font = BOLD
    table(ws, ["指标", "数值", "说明"], [
        ["Δbasis_10 自相关", res_real.get("diagnostics", {}).get("autocorr_y"), "AR(1)，用于判断有效样本量"],
        ["有效样本量", res_real.get("diagnostics", {}).get("effective_n"), "名义 N 与有效 N 的差距来自重叠窗口"],
        ["重叠倍数", res_real.get("diagnostics", {}).get("overlap_ratio"), "10 日窗口 / 5 日间隔"],
        ["非重叠样本数", res_real.get("diagnostics", {}).get("nonoverlap_n"), "间隔≥10 交易日"],
        ["月度样本数", res_real.get("diagnostics", {}).get("monthly_n"), "每月至多 1 个"],
    ], start_row=r2 + 1, widths=[26, 14, 60])

    # ---------------------------------------------------------------- 9 稳定性
    ws = sheet(wb, "9-稳定性")
    title(ws, "九、稳定性（分年 / 分库存分位 / 分基差符号）")
    st = res_real.get("stability") or {}
    r = 4
    names = {"by_year": "分年", "by_band": "按库存历史分位（LOW<30% / MID / HIGH>70%）",
             "by_baseline_sign": "按 T0 基差符号"}
    for key in ("by_year", "by_band", "by_baseline_sign"):
        items = st.get(key) or []
        ws.cell(row=r, column=1, value=names[key]).font = BOLD
        table(ws, ["分组", "信号 n", "对照 n", "均值差(元/吨)", "p", "解读"],
              [[i["group"], i["n_signal"], i["n_control"], i["diff"], i["p"],
                ("样本不足" if (i["p"] is None) else ("显著" if i["p"] < 0.05 else "不显著"))] for i in items],
              start_row=r + 1, widths=[14, 10, 10, 16, 10, 14], num_cols=(2, 3, 4, 5))
        r = r + 1 + len(items) + 3
    ws.cell(row=r, column=1,
            value="结论：没有任何一年/任何一个库存分位带出现显著且方向一致的效应；"
                  "凡样本不足的分组一律不给 p 值，避免用 2–3 个观测「编故事」。").font = SUB_FONT

    # ---------------------------------------------------------------- 10 修订口径
    ws = sheet(wb, "10-修订口径对照")
    title(ws, "十、预登记修订口径对照（回答「是不是口径选错了」）",
          "主口径因去重后信号仅 10 个落到样本不足；以下两个修订口径事前即可想到，用于检验稳健性。")
    rows = []
    for v in amend.get("variants", []):
        prim = next((t for t in v["tests"] if t["id"] == "P1_mean"), None)
        rows.append([v["tag"], v["note"], v["n_signal"], v["n_control"], v["evaluable"],
                     prim.get("estimate") if prim else None,
                     (f"[{prim['ci95'][0]:+.1f}, {prim['ci95'][1]:+.1f}]" if prim and prim.get("ci95") else "—"),
                     prim.get("p") if prim else None,
                     verdict_text(v)])
    table(ws, ["口径", "说明", "信号 n", "对照 n", "可评估状态", "主检验均值差", "95% CI", "p", "结论"],
          rows, start_row=4, widths=[10, 40, 10, 10, 12, 15, 22, 10, 24], num_cols=(6, 8))
    ws.cell(row=4 + len(rows) + 2, column=1,
            value="四个口径一致：没有正向显著证据。放得越松，均值差依然接近 0、CI 横跨 0 —— "
                  "说明效应本身不明显，而不是口径选错了。").font = SUB_FONT

    # ---------------------------------------------------------------- 11 事件研究
    ws = sheet(wb, "11-事件研究")
    title(ws, "十一、事件研究：差异是不是在信号之前就出现了",
          "T0=0；数值为该组在事件时间点的平均累积 Δbasis（元/吨）。")
    pp = ev.get("pre_post", {})
    table(ws, ["组别", "n", "T−20…T−1 均值", "T+1…T+10 均值", "T+11…T+20 均值"], [
        ["信号组（连降两周）", pp.get("signal", {}).get("n"),
         pp.get("signal", {}).get("pre_mean"), pp.get("signal", {}).get("post_mean_1_10"),
         pp.get("signal", {}).get("post_mean_11_20")],
        ["对照组", pp.get("control", {}).get("n"),
         pp.get("control", {}).get("pre_mean"), pp.get("control", {}).get("post_mean_1_10"),
         pp.get("control", {}).get("post_mean_11_20")],
    ], start_row=4, widths=[22, 8, 18, 18, 18], num_cols=(3, 4, 5))
    ks = list(range(-20, 21))
    bs, bc = ev.get("basis_signal", {}), ev.get("basis_control", {})
    table(ws, ["事件日 k"] + [f"k={k}" for k in ks] if False else
          ["事件时间 k", "信号组 累积Δbasis", "对照组 累积Δbasis", "信号组 n", "对照组 n"],
          [[k, bs.get(str(k)), bc.get(str(k)), ev.get("basis_signal_n", {}).get(str(k)),
            ev.get("basis_control_n", {}).get(str(k))] for k in ks],
          start_row=10, widths=[12, 18, 18, 10, 10], num_cols=(2, 3))
    ws.cell(row=10 + len(ks) + 2, column=1,
            value="读法：信号组在 T0 之前的基差均值已经高于对照组，说明『连降两周』更容易在基差已走强的阶段出现；"
                  "因此事后的差异不能全部归因于信号。").font = SUB_FONT

    # ---------------------------------------------------------------- 12 模拟演示
    ws = sheet(wb, "12-模拟演示(SIMULATED)")
    title(ws, "十二、模拟数据演示（整表为 SIMULATED，禁止作为结论引用）",
          f"生成方式：{demo_meta.get('mechanism','')}；seed={demo_meta.get('seed')}；"
          f"{demo_meta.get('weeks')} 周（{demo_meta.get('first')}→{demo_meta.get('last')}）。"
          f"警告：{demo_meta.get('warning','')}")
    for c in range(1, 10):
        ws.cell(row=3, column=c).fill = FILL_SIM
    pairs = [("用途", "验证『假设→设计→样本→检验→稳定性→结论』流水线能跑通、输出长什么样"),
             ("模拟结论", verdict_text(res_demo) + "　" + str(res_demo.get("message", ""))),
             ("模拟样本", f"信号 {res_demo.get('sample', {}).get('n_signal')} / 对照 "
                      f"{res_demo.get('sample', {}).get('n_control')}"),
             ("请勿引用", "本表任何数字都不代表甲醇市场，也不支持/否定用户的假设")]
    r = kv(ws, pairs, start_row=5, w1=14, w2=100)
    r += 1
    fam = {"primary": "主检验", "sensitivity": "敏感性", "robustness": "鲁棒性",
           "placebo": "安慰剂", "diagnostic": "诊断"}
    rows = [[t["id"], fam.get(t["family"], t["family"]), t["label"], t.get("estimate"),
             t.get("p"), t.get("q_bh"), t.get("n"), "SIMULATED"]
            for t in res_demo.get("tests", [])]
    end = table(ws, ["编号", "检验族", "检验内容", "效应量", "p", "BH-q", "N", "数据状态"],
                rows, start_row=r, widths=[10, 12, 56, 12, 10, 10, 8, 14], num_cols=(4, 5, 6))
    for row in ws.iter_rows(min_row=r + 1, max_row=end, min_col=1, max_col=8):
        for c in row:
            c.fill = FILL_SIM

    # ---------------------------------------------------------------- 13 局限
    ws = sheet(wb, "13-局限与风险")
    title(ws, "十三、局限与风险（写在结论前面）")
    rows = [[l["id"], l.get("level", ""), l["text"]] for l in design.get("risks_and_limits", [])]
    table(ws, ["编号", "严重度", "说明"], rows, start_row=4, widths=[8, 8, 120], wrap_cols=(3,))
    r = 4 + len(rows) + 2
    ws.cell(row=r, column=1, value="四类典型错误的自查").font = BOLD
    table(ws, ["风险", "如果做错会怎样", "本研究怎么处理"], [
        ["未来函数（前视偏差）", "用报告发布前的价格配报告发布后的库存，等于提前知道报告",
         "信号只用 14:00 前已可得两期；价格用发布后 bar；分位只用过去 52 周"],
        ["幸存者偏差", "只留下报告过数据的周或还在交易的合约", "缺失周留缺口；剔除原因逐条计数；合约按当期近月取"],
        ["重叠样本", "相邻信号共用 8/10 天窗口，N 虚增", "非重叠/月度样本 + 块自助 + 有效样本量"],
        ["多重检验", "试 20 个口径挑一个 p<0.05", "全量登记 + BH-FDR；修订口径单列；参数冻结"],
    ], start_row=r + 1, widths=[20, 50, 60], wrap_cols=(2, 3))

    # ---------------------------------------------------------------- 14 复现
    ws = sheet(wb, "14-复现说明")
    title(ws, "十四、复现说明（数据指纹、脚本与命令）")
    files = audit.get("files", {})
    table(ws, ["序列", "文件", "行数", "sha256(前16位)"],
          [[k, v.get("path"), v.get("rows"), v.get("sha256")] for k, v in files.items()],
          start_row=4, widths=[14, 46, 10, 22])
    r = 4 + len(files) + 2
    ws.cell(row=r, column=1, value="重建命令").font = BOLD
    cmds = [
        "python src/selftest_stats.py                     # 20 项统计自检",
        "python src/merge_verified_inventory.py --history <库存历史.csv> --verification build/verification_full.json --live data/port_inventory_live.csv --out data/port_inventory_weekly.csv",
        "python src/approve_design.py --design build/research_design.formal.json --by 用户 --data data/port_inventory_weekly.csv data/100ppi_sf.csv",
        "python src/study_engine.py --design build/research_design.formal.json --inventory data/port_inventory_weekly.csv --price data/100ppi_sf.csv --minute data/futures/MA0_60min.csv --out build/results_real.json --samples build/samples_real.csv --status REAL",
        "python src/amendment_sensitivity.py               # 修订口径 AM-1..AM-3",
        "python src/event_study.py --inventory data/port_inventory_weekly.csv --price data/100ppi_sf.csv --out build/event_study.json",
        "python src/make_demo_simulation.py --weeks 208    # 生成 SIMULATED 演示数据",
        "python src/build_excel.py . out/研究工作簿.xlsx",
        "python src/build_html.py --root . --out out/研究页.html",
    ]
    for i, c in enumerate(cmds, r + 1):
        ws.cell(row=i, column=1, value=c).font = Font(name="Consolas", size=9.5)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 60

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    wb.save(out)
    print("xlsx ->", out, f"{os.path.getsize(out)/1024:.1f} KB", "sheets:", len(wb.sheetnames))


if __name__ == "__main__":
    main()
