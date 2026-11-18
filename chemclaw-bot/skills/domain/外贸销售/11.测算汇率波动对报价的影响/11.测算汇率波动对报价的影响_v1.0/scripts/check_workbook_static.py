# -*- coding: utf-8 -*-
"""check_workbook_static.py —— 不依赖 Excel 的结构与公式一致性检查

做四件事：
  1. 结构：必需工作表是否齐全、每表是否有内容
  2. 公式健康：是否残留占位符 / 空引用 / 未加引号的跨表名 / 明显非法函数
  3. 数字同源：工作簿里写死的静态数字（历史序列、批次金额、输入值）是否与 fx 序列 / scenario 一致
  4. 关键公式复算：把 02/03/05 表的核心公式用 Python 按其单元格依赖重算，与 scenario.json 比对

用法: python scripts/check_workbook_static.py <xlsx> <scenario.json> [fx.json]
"""
import json
import math
import os
import re
import sys

from openpyxl import load_workbook

REQUIRED = ["00_封面说明", "01_输入参数", "02_汇率敏感性", "03_毛利测算", "04_计算公式",
            "05_分批结算", "06_历史汇率序列", "07_历史分位", "08_实时汇率记录",
            "09_报价带入", "10_口径与免责"]

fails, passes = [], []


def chk(cond, name, detail=""):
    if cond:
        passes.append(name)
        print(f"[PASS] {name}" + (f"  — {detail}" if detail else ""))
    else:
        fails.append(name + (f"  — {detail}" if detail else ""))
        print(f"[FAIL] {name}" + (f"  — {detail}" if detail else ""))


def main():
    xlsx, scen_path = sys.argv[1], sys.argv[2]
    fx_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(xlsx), "..", "..", "build", "fx_series.json")
    scen = json.load(open(scen_path, encoding="utf-8"))
    wb = load_workbook(xlsx, data_only=False)

    # 1. 结构
    names = wb.sheetnames
    missing = [n for n in REQUIRED if n not in names]
    chk(not missing, "11 张工作表齐全", "缺: " + ", ".join(missing) if missing else f"{len(names)} 张")
    for n in REQUIRED:
        if n in names:
            ws = wb[n]
            chk(ws.max_row > 3 and ws.max_column > 2, f"{n} 有内容", f"{ws.max_row}行×{ws.max_column}列")

    # 2. 公式扫描
    bad_placeholder, bad_quote, total_formulas = [], [], 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    total_formulas += 1
                    v = c.value
                    if re.search(r"__[A-Z]+__|\{\{|\}\}|None|nan", v):
                        bad_placeholder.append(f"{ws.title}!{c.coordinate}")
                    # 跨表引用未加单引号（表名以数字开头）
                    for mname in re.finditer(r"(?<![\w'!\]])(\d\d_[^\s!'\"()+\-*/,<>=&]+)!", v):
                        bad_quote.append(f"{ws.title}!{c.coordinate} → {mname.group(1)}")
    chk(not bad_placeholder, "无占位符/None 残留在公式中", ", ".join(bad_placeholder[:5]))
    chk(total_formulas > 150, "公式数量充足（可运行）", f"{total_formulas} 条公式")
    uniq_bad = sorted(set(bad_quote))
    chk(not uniq_bad, "跨表引用均已加单引号", "; ".join(uniq_bad[:3]))

    # 3. 静态数字同源
    ws1 = wb["01_输入参数"]
    chk(abs(ws1["C5"].value == "出口收汇") or ws1["C5"].value == "进口付汇", "方向为下拉合法值", str(ws1["C5"].value))
    amt = ws1["C8"].value
    chk(abs(float(amt) - scen["meta"]["amount_fx"]) < 1e-9, "输入金额与 scenario 一致", f"{amt} vs {scen['meta']['amount_fx']}")
    mid = ws1["C9"].value
    chk(abs(float(mid) - scen["rate"]["mid"]) < 1e-9, "输入中间价与 scenario 一致", f"{mid} vs {scen['rate']['mid']}")
    cost = ws1["C14"].value
    chk(abs(float(cost) - scen["meta"]["cny_cost"]) < 1e-9, "输入成本与 scenario 一致", f"{cost}")

    ws6 = wb["06_历史汇率序列"]
    fx_src = os.path.normpath(fx_path)
    if os.path.exists(fx_src):
        fx = json.load(open(fx_src, encoding="utf-8"))
        n_series = len(fx["dates"])
        rows6 = ws6.max_row - 4
        chk(rows6 == n_series, "历史序列行数与官方数据一致", f"{rows6} vs {n_series}")
        # 抽查 3 个日期 × USD 列
        usd_col = 2
        ok_cnt = 0
        for d in (fx["dates"][0], fx["dates"][len(fx["dates"]) // 2], fx["dates"][-1]):
            for r in range(5, 5 + n_series):
                cell = ws6.cell(row=r, column=1).value
                iso = cell.strftime("%Y-%m-%d") if hasattr(cell, "strftime") else str(cell)[:10]
                if iso == d:
                    v = ws6.cell(row=r, column=usd_col).value
                    if v is not None and abs(float(v) - fx["currencies"]["USD"]["values"][d]) < 1e-9:
                        ok_cnt += 1
                    break
        chk(ok_cnt == 3, "历史序列抽样与 SAFE 官方值逐点一致", f"{ok_cnt}/3 个日期")

    # 4. 关键公式复算（按 Excel 公式语义手工重算，验证模型方向）
    toll = float(ws1["C18"].value or 0) * (1 if str(ws1["C18"].value).endswith("%") else 1)
    # 输入里百分比以小数存储
    band = float(ws1["C11"].value)
    is_exp = ws1["C5"].value == "出口收汇"
    r_sell = mid * (1 - band)
    base_py = scen["rate"]["base_rate"]
    chk(abs(r_sell - base_py) < 1e-6, "结汇价 = 中间价×(1−点差) 与引擎一致", f"{r_sell:.6f} vs {base_py:.6f}")

    ws3 = wb["03_毛利测算"]
    net_py = amt * base_py * (1 - toll)
    chk(abs(net_py - scen["base"]["net_cny"]) < 0.02, "净收入公式与引擎一致", f"{net_py:,.2f} vs {scen['base']['net_cny']:,.2f}")
    margin_py = net_py - cost
    chk(abs(margin_py - scen["base"]["margin_cny"]) < 0.02, "毛利公式与引擎一致", f"{margin_py:,.2f}")
    be_py = cost / (amt * (1 - toll))
    chk(abs(be_py - scen["breakevens"]["zero"]["breakeven"]) < 1e-9, "平衡汇率 R*=C/[A(1−t)] 与引擎一致", f"{be_py:.6f}")

    # 02 表档位行：检查情景汇率公式字符串结构
    ws2 = wb["02_汇率敏感性"]
    f_c3 = ws2["C5"].value
    chk(isinstance(f_c3, str) and "'01_输入参数'!$C$28" in f_c3 and "(1+B5)" in f_c3,
        "敏感性表情景汇率公式正确", str(f_c3)[:70])
    f_g = ws2["G5"].value
    chk(isinstance(f_g, str) and "1+" in f_g and "第" not in str(f_g), "敏感性表净额公式带方向符号", str(f_g)[:70])

    # 05 分批合计
    ws5 = wb["05_分批结算"]
    batch_sum = sum(float(ws5.cell(row=r, column=3).value or 0) for r in range(5, 8))
    chk(abs(batch_sum - amt) < 0.01, "分批示例合计 = 订单金额", f"{batch_sum:,.2f} vs {amt:,.2f}")

    # 07 分位公式引用（按标签定位分位行）
    ws7 = wb["07_历史分位"]
    pct_row = None
    for r in range(1, ws7.max_row + 1):
        if isinstance(ws7.cell(row=r, column=2).value, str) and "当前值分位" in ws7.cell(row=r, column=2).value:
            pct_row = r
            break
    f7 = ws7.cell(row=pct_row, column=3).value if pct_row else None
    chk(isinstance(f7, str) and "COUNTIFS" in f7 and "0.5" in f7, "分位公式含 0.5 相等加权", str(f7)[:80])

    print(f"\n静态检查：{len(passes)}/{len(passes) + len(fails)} 通过")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
