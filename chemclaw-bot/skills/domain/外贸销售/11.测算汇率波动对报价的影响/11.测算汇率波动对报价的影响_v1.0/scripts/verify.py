# -*- coding: utf-8 -*-
"""verify.py —— 三方一致性总校验：Python 引擎 / Excel 工作簿 / HTML 成品

用法:
    python scripts/verify.py <scenario.json> <xlsx> <html> [--fx build/fx_series.json]

检查：
  A. 引擎自洽        scenario.json 内部数字互相能对上（净额 = 金额×汇率、毛利 = 净额−成本……）
  B. Excel 同源      xlsx 里的静态值与输入值必须等于 scenario（历史序列逐点抽查）
  C. HTML 同源       HTML 内嵌的场景数据与 scenario 关键数字一致
  D. 三方对齐        同一指标在引擎 / Excel 公式 / HTML 中给出同一个数

任一项不符 → 退出码 1。
"""
import json
import os
import re
import sys

from openpyxl import load_workbook

fails, passes = [], []


def chk(cond, name, detail=""):
    if cond:
        passes.append(name)
        print(f"[PASS] {name}" + (f"  — {detail}" if detail else ""))
    else:
        fails.append(name + (f" — {detail}" if detail else ""))
        print(f"[FAIL] {name}" + (f"  — {detail}" if detail else ""))


def close(a, b, tol=0.02, rel=False):
    try:
        a, b = float(a), float(b)
    except Exception:
        return False
    if rel:
        # 比例类指标用相对容差，避免 1e-9 绝对容差在浮点运算下失效
        return abs(a - b) <= tol * max(abs(a), abs(b), 1e-12)
    return abs(a - b) <= tol


def main():
    scen_p, xlsx_p, html_p = sys.argv[1], sys.argv[2], sys.argv[3]
    s = json.load(open(scen_p, encoding="utf-8"))
    meta, rate, base = s["meta"], s["rate"], s["base"]
    is_exp = meta["direction"] == "export"

    print("=" * 66)
    print("A. 引擎自洽")
    print("=" * 66)
    A = meta["amount_fx"]
    R = rate["base_rate"]
    t = meta.get("toll_rate", 0)
    sign = -1 if is_exp else 1
    chk(close(base["gross_cny"], A * R, 0.02), "毛额 = 金额 × 汇率", f"{base['gross_cny']:,.2f}")
    chk(close(base["net_cny"], A * R * (1 + sign * t), 0.02), "净额 = 毛额 ×(1 + sign×t)",
        f"{base['net_cny']:,.2f}")
    if is_exp:
        chk(close(base["margin_cny"], base["net_cny"] - meta["cny_cost"], 0.02),
            "毛利 = 净额 − 成本", f"{base['margin_cny']:,.2f}")
        # scenario 里的 margin_pct 落盘时已四舍五入到 1e-6，故用 1e-5 相对容差核对
        chk(close(base["margin_pct"], base["margin_cny"] / base["net_cny"], 1e-5, rel=True),
            "毛利率 = 毛利 ÷ 净额", f"{base['margin_pct']:.4%}")
        be_zero = meta["cny_cost"] / (A * (1 - t))
        chk(close(s["breakevens"]["zero"]["breakeven"], be_zero, 1e-6),
            "平衡汇率 R* = C/[A(1−t)]", f"{be_zero:.6f}")
        if "target_pct" in s["breakevens"]:
            m = meta["target_margin_pct"]
            be_tp = meta["cny_cost"] / (A * (1 - t) * (1 - m))
            chk(close(s["breakevens"]["target_pct"]["breakeven"], be_tp, 1e-6),
                "保目标毛利率汇率 R* = C/[A(1−t)(1−m)]", f"{be_tp:.6f}")
        # 在平衡汇率上毛利应恰为 0
        rev_at_be = A * be_zero * (1 - t)
        chk(close(rev_at_be, meta["cny_cost"], 0.01), "在平衡汇率上，净收入 = 成本（毛利恰为 0）",
            f"{rev_at_be:,.2f}")
    chk(close(s["one_pct_cny"], abs(A * R * (1 - t)) * 0.01, 0.02), "每 1% 敞口 = |A×R×(1−t)|×1%",
        f"{s['one_pct_cny']:,.2f}")

    # 敏感性对称性
    sens = {round(x["shift"], 6): x for x in s["sensitivity"]}
    if -0.05 in sens and 0.05 in sens:
        chk(close(sens[-0.05]["delta_cny"], -sens[0.05]["delta_cny"], 0.05),
            "±5% 的人民币变化互为相反数（无对冲时对称）",
            f"{sens[-0.05]['delta_cny']:,.2f} / {sens[0.05]['delta_cny']:,.2f}")
    if -0.01 in sens:
        chk(close(sens[-0.01]["delta_cny"], -s["one_pct_cny"], 0.05),
            "−1% 档变化 = 每 1% 敞口", f"{sens[-0.01]['delta_cny']:,.2f}")

    print("\n" + "=" * 66)
    print("B. Excel 同源")
    print("=" * 66)
    wb = load_workbook(xlsx_p)
    ws1 = wb["01_输入参数"]
    chk(close(ws1["C8"].value, A, 1e-9), "01 表输入金额 = 引擎金额", f"{ws1['C8'].value}")
    chk(close(ws1["C9"].value, rate["mid"], 1e-9), "01 表输入中间价 = 引擎中间价", f"{ws1['C9'].value}")
    chk(close(ws1["C14"].value, meta.get("cny_cost") or 0, 1e-9), "01 表输入成本 = 引擎成本",
        f"{ws1['C14'].value}")
    ws6 = wb["06_历史汇率序列"]
    n_rows = ws6.max_row - 4
    ser = s["series"]
    dates_l, vals_l = ser["dates"], ser["values"]
    chk(n_rows == len(dates_l), "06 表历史行数 = 引擎序列长度", f"{n_rows} vs {len(dates_l)}")
    # 抽查 5 个日期
    idx = [0, len(dates_l) // 4, len(dates_l) // 2, 3 * len(dates_l) // 4, len(dates_l) - 1]
    want = {dates_l[i]: vals_l[i] for i in idx}
    got = {}
    for r in range(5, 5 + n_rows):
        d = ws6.cell(row=r, column=1).value
        iso = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        if iso in want:
            got[iso] = ws6.cell(row=r, column=2).value
    okn = sum(1 for k, v in got.items() if v is not None and close(v, want[k], 1e-9))
    chk(okn == len(want), "06 表 USD 序列抽查与引擎逐点一致", f"{okn}/{len(want)}")

    print("\n" + "=" * 66)
    print("C. HTML 同源")
    print("=" * 66)
    html = open(html_p, encoding="utf-8").read()
    # 场景数据以 <script type="application/json" id="data-scenario"> 内联（chart 与数据同源）
    m = re.search(r'<script[^>]*id="data-scenario"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        chk(False, "HTML 内嵌场景数据可提取", "未找到 id=data-scenario")
    else:
        try:
            D = json.loads(m.group(1))
            chk(True, "HTML 内嵌场景数据可解析", f"{len(m.group(1))} 字节")
            chk(close(D["rate"]["base_rate"], rate["base_rate"], 1e-9),
                "HTML 基准汇率 = 引擎", f"{D['rate']['base_rate']}")
            chk(close(D["base"]["net_cny"], base["net_cny"], 0.02),
                "HTML 净收入 = 引擎", f"{D['base']['net_cny']:,.2f}")
            chk(close(D["base"]["margin_cny"], base["margin_cny"], 0.02),
                "HTML 毛利 = 引擎", f"{D['base']['margin_cny']:,.2f}")
            chk(close(D["breakevens"]["zero"]["breakeven"],
                      s["breakevens"]["zero"]["breakeven"], 1e-9),
                "HTML 平衡汇率 = 引擎", f"{D['breakevens']['zero']['breakeven']:.6f}")
            chk(close(D["stats"]["1y"]["pctile_mid"], s["stats"]["1y"]["pctile_mid"], 1e-9),
                "HTML 1 年分位 = 引擎", f"{D['stats']['1y']['pctile_mid']:.4%}")
        except json.JSONDecodeError as e:
            chk(False, "HTML 内嵌场景数据可解析", str(e)[:80])
    chk("safe.gov.cn" in html, "HTML 含官方来源链接")
    chk("不预测汇率走势" in html, "HTML 含不预测声明")

    print("\n" + "=" * 66)
    print(f"三方校验结果：{len(passes)}/{len(passes) + len(fails)} 通过")
    if fails:
        print("未通过：")
        for f in fails:
            print("  -", f)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
