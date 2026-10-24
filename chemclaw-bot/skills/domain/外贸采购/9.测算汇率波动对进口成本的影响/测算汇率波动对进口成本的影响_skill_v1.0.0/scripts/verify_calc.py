# -*- coding: utf-8 -*-
"""
verify_calc.py —— 计算验证脚本（交付前必跑）

做三件事
--------
V1  引擎自检：汇率方向关系、计征汇率日期、增值税口径、盈亏平衡数学。
V2  Excel 真实重算：用内置公式引擎把 .xlsx 里的公式逐条求值，
    与 Python 引擎结果逐项比对（容差 1 元 / 0.01%）。
V3  独立性检验：改金额、改汇率、改付款比例、改锁定汇率后，
    Excel 公式是否仍然联动且数值正确（证明“公式可运行”，不是死值）。

用法
----
    python verify_calc.py examples/meg-saudi-1m-usd/input.json \
        --xlsx examples/meg-saudi-1m-usd/output/工作簿.xlsx \
        --history data/fx_real_data.json

    或一次性：
    python verify_calc.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import fx_engine as E          # noqa: E402
import xlsx_recalc as XR       # noqa: E402

RESULTS = []


def chk(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("  \033[92mPASS\033[0m " if cond else "  \033[91mFAIL\033[0m ") + name + ("  " + detail if detail else ""))
    return bool(cond)


def close(a, b, tol=1.0):
    """容差比较；任一为非数值（None/""/文本）则返回 False。"""
    if a is None or b is None:
        return False
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return abs(fa - fb) <= tol


# ---------------------------------------------------------------- V1
def v1_engine():
    print("\n=== V1 引擎自检（方向关系 / 计征汇率 / 税费 / 盈亏平衡） ===")
    r0 = 7.0
    up = E.apply_sensitivity(r0, 3)
    chk("人民币贬值(+3%) → 付汇人民币增加", E.payment_cny(1e6, up) > E.payment_cny(1e6, r0),
        f"{E.payment_cny(1e6, up):,.0f} > {E.payment_cny(1e6, r0):,.0f}")
    dn = E.apply_sensitivity(r0, -3)
    chk("人民币升值(−3%) → 付汇人民币减少", E.payment_cny(1e6, dn) < E.payment_cny(1e6, r0))
    chk("敏感性严格线性（Δ = 金额×汇率×Δ%）",
        all(abs(x["delta_cny"] - 1e6 * r0 * x["pct"] / 100) < 0.01
            for x in E.sensitivity_table(1e6, r0)))

    chk("计征汇率：2026-09 第三个星期三 = 09-16",
        E.third_wednesday(2026, 9) == E.date(2026, 9, 16), str(E.third_wednesday(2026, 9)))
    chk("计征汇率：2026-10 第三个星期三 = 10-21",
        E.third_wednesday(2026, 10) == E.date(2026, 10, 21), str(E.third_wednesday(2026, 10)))
    chk("2026-11 申报 → 适用 2026-10-21",
        E.customs_rate_date(E.date(2026, 11, 15)) == E.date(2026, 10, 21))

    lc = E.landed_cost(1e6, 7.0, duty_rate=0.055, vat_rate=0.13, vat_mode="deductible",
                       cny_port=30000, customs_rate=7.0)
    chk("关税 = 完税价格 × 5.5%", close(lc["duty_cny"], 385000), f"{lc['duty_cny']:,.2f}")
    chk("增值税 = (完税价+关税) × 13%", close(lc["vat_cny"], 960050), f"{lc['vat_cny']:,.2f}")
    chk("可抵扣口径下增值税不计入成本", abs(lc["vat_in_cost"]) < 1e-9)
    chk("到厂成本 = 700万 + 38.5万 + 3万", close(lc["landed_cost_cny"], 7415000), f"{lc['landed_cost_cny']:,.2f}")

    be = E.breakeven_rate(8_000_000, 10_000_000, 7_000_000, 7.0, 0.0)
    chk("零毛利平衡汇率 = 9.00", close(be["breakeven_rate"], 9.0, 1e-6), f"{be['breakeven_rate']}")
    be2 = E.breakeven_rate(8_000_000, 10_000_000, 7_000_000, 7.0, 10.0)
    chk("10% 毛利平衡汇率 = 8.00", close(be2["breakeven_rate"], 8.0, 1e-6), f"{be2['breakeven_rate']}")
    be3 = E.breakeven_rate(10_000_000, 10_000_000, 7_000_000, 7.0, 10.0)
    chk("基准毛利 0% 低于目标 10% → 标记不适用", be3.get("applicable") is False, be3.get("reason", "")[:40])
    return all(ok for _, ok, _ in RESULTS)


# ---------------------------------------------------------------- V2
def find_cells(wb, sheet):
    """定位关键结果单元格（按标签名搜索，稳健于行号变动）。"""
    cells = wb.sheets.get(sheet, {})
    labels = {}
    for (r, c), v in cells.items():
        if c == 0 and isinstance(v, str) and v.strip():
            labels.setdefault(v.strip(), r)
    return labels


def cell_by_label(wb, sheet, label, col=1):
    labels = find_cells(wb, sheet)
    if label not in labels:
        raise KeyError(f"{sheet} 中找不到标签「{label}」。现有：{list(labels)[:40]}")
    r = labels[label]
    key = (r, col)
    for (rr, cc), v in wb.sheets[sheet].items():
        if rr == r and cc == col:
            return XR.idx_to_col(col) + str(r + 1)
    # 合并/空值回退
    return XR.idx_to_col(col) + str(r + 1)


def v2_excel(xlsx_path, res, inputs):
    print("\n=== V2 Excel 公式真实重算 与 Python 引擎比对 ===")
    wb = XR.recalc(xlsx_path)
    print(f"  工作簿页签：{list(wb.sheets.keys())}")

    def gv(sheet, addr):
        v = XR.get(wb, sheet, addr)
        if isinstance(v, list):
            v = v[0][0] if v and isinstance(v[0], list) else v[0]
        return v

    # --- 02 付款额 ---
    s2 = "02 付款额与敏感性"
    a_amt = cell_by_label(wb, s2, "采购金额（外币）")
    a_rate = cell_by_label(wb, s2, "基准汇率（CNY/FC）")
    a_pay = cell_by_label(wb, s2, "人民币付款额（基准）")
    v_amt, v_rate, v_pay = gv(s2, a_amt), gv(s2, a_rate), gv(s2, a_pay)
    chk("Excel 采购金额 = 引擎输入", close(v_amt, inputs["amount_fc"]), f"{v_amt:,.2f}")
    chk("Excel 基准汇率 = 银行购汇价", close(v_rate, inputs["rates"]["bank"], 1e-6), f"{v_rate:.4f}")
    chk("Excel 付款额 = 外币金额 × 汇率",
        close(v_pay, res["payment"]["base_cny"]), f"Excel {v_pay:,.2f} vs 引擎 {res['payment']['base_cny']:,.2f}")

    # --- 敏感性表 ---
    lab = find_cells(wb, s2)
    # find_cells 返回 0-based 行号；“汇率变动”是表头，数据从下一行（Excel 行号 = 0-based+2）开始
    start = lab["汇率变动"] + 2
    ok_all, det = True, []
    for i in range(7):
        pct = gv(s2, XR.idx_to_col(0) + str(start + i))
        cny = gv(s2, XR.idx_to_col(2) + str(start + i))
        exp = [x for x in res["sensitivity_payment"] if abs(x["pct"] / 100 - pct) < 1e-9]
        if not exp:
            ok_all = False
            det.append(f"{pct} 无对应引擎值")
            continue
        if not close(cny, exp[0]["cny"]):
            ok_all = False
            det.append(f"{pct:.0%}: {cny:,.0f} vs {exp[0]['cny']:,.0f}")
    chk("7 档敏感性表逐行与引擎一致", ok_all, "; ".join(det[:3]) if det else "±5% 全部匹配")

    # --- 03 到厂成本 ---
    s3 = "03 到厂成本"
    a_tot = cell_by_label(wb, s3, "人民币到厂成本合计")
    a_unit = cell_by_label(wb, s3, "折合单位到厂成本（元/吨）")
    a_duty = cell_by_label(wb, s3, "进口关税")
    a_vat = cell_by_label(wb, s3, "进口增值税（计税用）")
    v_tot, v_unit = gv(s3, a_tot), gv(s3, a_unit)
    v_duty, v_vat = gv(s3, a_duty), gv(s3, a_vat)
    L = res["landed_cost"]
    chk("Excel 到厂成本 = 引擎", close(v_tot, L["landed_cost_cny"]), f"Excel {v_tot:,.2f} vs 引擎 {L['landed_cost_cny']:,.2f}")
    chk("Excel 单位到厂成本 = 引擎", close(v_unit, L["landed_unit_cny"], 0.05), f"{v_unit:,.2f}")
    chk("Excel 关税 = 引擎", close(v_duty, L["duty_cny"]), f"{v_duty:,.2f} vs {L['duty_cny']:,.2f}")
    chk("Excel 增值税 = 引擎", close(v_vat, L["vat_cny"]), f"{v_vat:,.2f} vs {L['vat_cny']:,.2f}")

    # --- 04 毛利 ---
    s4 = "04 毛利与盈亏平衡"
    if res.get("gross_margin"):
        a_gp = cell_by_label(wb, s4, "毛利额")
        a_gm = cell_by_label(wb, s4, "毛利率")
        v_gp, v_gm = gv(s4, a_gp), gv(s4, a_gm)
        G = res["gross_margin"]
        chk("Excel 毛利额 = 引擎", close(v_gp, G["gross_profit_cny"]), f"Excel {v_gp:,.2f} vs 引擎 {G['gross_profit_cny']:,.2f}")
        chk("Excel 毛利率 = 引擎", close(v_gm * 100, G["gross_margin_pct"], 0.01), f"{v_gm*100:.4f}% vs {G['gross_margin_pct']}%")

        # 平衡汇率
        lab4 = find_cells(wb, s4)
        bstart = lab4["目标毛利率"] + 1
        be_ok = True
        be_det = []
        def _isnum(v):
            try:
                float(v)
                return True
            except (TypeError, ValueError):
                return False
        for i, beng in enumerate(res.get("breakeven", [])):
            row = bstart + i + 1
            v_be = gv(s4, XR.idx_to_col(2) + str(row))
            if beng.get("applicable") and beng.get("breakeven_rate"):
                if not (_isnum(v_be) and close(v_be, beng["breakeven_rate"], 0.001)):
                    be_ok = False
                    be_det.append(f"目标{beng['target_margin_pct']}%: Excel {v_be} vs 引擎 {beng['breakeven_rate']:.4f}")
            else:
                if _isnum(v_be) or v_be not in ("", None):
                    be_ok = False
                    be_det.append(f"目标{beng['target_margin_pct']}% 应为空，Excel 给出 {v_be!r}")
        chk("盈亏平衡汇率与引擎一致（含“不适用”行留空）", be_ok, "; ".join(be_det[:2]) if be_det else "全部匹配")

    # --- 05 分批 ---
    s5 = "05 分批付款"
    a_base = cell_by_label(wb, s5, "合计", col=4) if ("合计", 4) in [] else None
    lab5 = find_cells(wb, s5)
    if "合计" in lab5:
        r5 = lab5["合计"]
        v_tbase = gv(s5, XR.idx_to_col(4) + str(r5 + 1))
        chk("Excel 分批合计（基准）= 付款额", close(v_tbase, res["payment"]["base_cny"]), f"{v_tbase:,.2f}")

    # --- 06 历史分位 ---
    s6 = "06 历史汇率与分位"
    lab6 = find_cells(wb, s6)
    if "近 3 年" in lab6:
        r6 = lab6["近 3 年"]
        v_pct = gv(s6, XR.idx_to_col(6) + str(r6 + 1))
        pct_eng = res.get("history", {}).get("windows", {}).get("3y", {}).get("percentile_pboc")
        if pct_eng is not None:
            chk("Excel 近3年中间价分位 = 引擎", close(v_pct * 100, pct_eng, 0.6),
                f"Excel {v_pct*100:.2f}% vs 引擎 {pct_eng:.2f}%（窗口边界口径差异）")
    return True


# ---------------------------------------------------------------- V3
def v3_independence(inputs, history):
    """改写 01 表输入 → 重算 → 与引擎新结果比对，证明公式真的联动。"""
    print("\n=== V3 公式联动独立性检验（改参数后重算是否正确） ===")
    import subprocess
    build = os.path.join(HERE, "build_xlsx.py")
    ok = True

    cases = [
        ("金额翻倍为 2,000,000", lambda d: d.update({"amount_fc": 2000000})),
        ("银行购汇价改为 7.0000", lambda d: d["rates"].update({"bank": 7.0})),
        ("预付款比例 50%", lambda d: [d["payment"]["tranches"][0].update({"pct": 0.5}),
                                   d["payment"]["tranches"][1].update({"pct": 0.5})]),
        ("预付款锁定 6.7000", lambda d: d["payment"]["tranches"][0].update({"rate_override": 6.70})),
        ("关税率改为 0%", lambda d: d["costs"].update({"duty_rate": 0.0})),
        ("增值税不可抵扣", lambda d: d["costs"].update({"vat_mode": "cost"})),
    ]

    for name, mut in cases:
        d = json.loads(json.dumps(inputs))
        mut(d)
        with tempfile.TemporaryDirectory() as td:
            ip = os.path.join(td, "in.json")
            xp = os.path.join(td, "out.xlsx")
            json.dump(d, open(ip, "w", encoding="utf-8"), ensure_ascii=False)
            subprocess.run([sys.executable, build, ip, "-o", xp,
                            "--history", os.path.join(ROOT, "data", "fx_real_data.json")],
                           check=True, capture_output=True)
            new_res = E.run(d, history)
            wb = XR.recalc(xp)

            def gv(sheet, addr):
                v = XR.get(wb, sheet, addr)
                return v[0][0] if isinstance(v, list) else v

            s2, s3 = "02 付款额与敏感性", "03 到厂成本"
            pay = gv(s2, cell_by_label(wb, s2, "人民币付款额（基准）"))
            tot = gv(s3, cell_by_label(wb, s3, "人民币到厂成本合计"))
            p_ok = close(pay, new_res["payment"]["base_cny"])
            t_ok = close(tot, new_res["landed_cost"]["landed_cost_cny"])
            ok_c = p_ok and t_ok
            ok = ok and ok_c
            chk(f"{name} → 公式重算正确", ok_c,
                f"付款 Excel {pay:,.2f}/引擎 {new_res['payment']['base_cny']:,.2f}；"
                f"到厂 Excel {tot:,.2f}/引擎 {new_res['landed_cost']['landed_cost_cny']:,.2f}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?")
    ap.add_argument("--xlsx")
    ap.add_argument("--history", default=os.path.join(ROOT, "data", "fx_real_data.json"))
    ap.add_argument("--skip-v3", action="store_true")
    ap.add_argument("--all", action="store_true", help="运行内置演示案例")
    args = ap.parse_args()

    if args.all:
        args.input = os.path.join(ROOT, "examples", "meg-saudi-1m-usd", "input.json")
        args.xlsx = os.path.join(ROOT, "examples", "meg-saudi-1m-usd", "output",
                                 "MEG_沙特_进口汇率敏感性工作簿.xlsx")
    if not args.input:
        ap.error("需要 input.json（或用 --all）")

    inputs = json.load(open(args.input, encoding="utf-8"))
    history = json.load(open(args.history, encoding="utf-8")) if os.path.exists(args.history) else None

    v1_engine()
    res = E.run(inputs, history)
    if args.xlsx and os.path.exists(args.xlsx):
        v2_excel(args.xlsx, res, inputs)
        if not args.skip_v3:
            v3_independence(inputs, history)
    else:
        print("\n[跳过 V2/V3] 未找到 xlsx")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{'='*66}\n{'全部通过' if passed == total else '存在失败项'}：{passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
