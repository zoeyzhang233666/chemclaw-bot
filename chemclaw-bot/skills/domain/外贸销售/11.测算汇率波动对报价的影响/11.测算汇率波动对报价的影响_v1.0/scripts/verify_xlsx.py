# -*- coding: utf-8 -*-
"""verify_xlsx.py —— 用 Excel（COM）真实打开工作簿、强制重算并核对公式

用法:
    python scripts/verify_xlsx.py <xlsx> <scenario.json>

做四件事：
  1. 打开工作簿，强制全量重算（CalculateFullRebuild）
  2. 按列标签定位关键单元格，与 scenario.json（Python 引擎结果）逐项比对
  3. 改输入 → 再重算 → 验证结果随之变化（证明公式在跑，不是写死的值）
  4. 扫描全簿的 #NAME? / #VALUE! / #REF! 等错误单元格

无 Excel / 无 pywin32 时优雅跳过（返回 0）。
"""
import json
import os
import sys

try:
    import win32com.client as win32
    HAS_COM = True
except Exception:
    HAS_COM = False


def find_row(ws, text, col=2, max_row=200):
    """按标签找行号；找不到返回 None"""
    for r in range(1, max_row + 1):
        v = ws.Cells(r, col).Value
        if isinstance(v, str) and text in v:
            return r
    return None


def main():
    xlsx = os.path.abspath(sys.argv[1])
    scen = json.load(open(sys.argv[2], encoding="utf-8"))

    if not HAS_COM:
        print("[SKIP] 未安装 pywin32，跳过 Excel 实算校验")
        return 0
    try:
        excel = win32.DispatchEx("Excel.Application")
    except Exception as e:
        print(f"[SKIP] 无法启动 Excel（{type(e).__name__}），跳过实算校验")
        return 0

    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False
    fails, ok_n = [], 0
    wb = None

    def chk(name, xv, pv, tol):
        nonlocal ok_n
        if xv is None or pv is None or not isinstance(xv, (int, float)):
            fails.append(f"{name}: excel={xv!r} py={pv!r}")
            print(f"[FAIL] {name}: excel={xv!r} py={pv!r}")
            return False
        diff = abs(float(xv) - float(pv))
        good = diff <= tol
        ok_n += good
        if not good:
            fails.append(f"{name}: excel={xv} py={pv} diff={diff:.6g}")
        print(f"{'[PASS]' if good else '[FAIL]'} {name}: excel={float(xv):,.6f}  py={float(pv):,.6f}")
        return good

    try:
        wb = excel.Workbooks.Open(xlsx)
        excel.CalculateFullRebuild()

        ws1 = wb.Worksheets("01_输入参数")
        ws2 = wb.Worksheets("02_汇率敏感性")
        ws3 = wb.Worksheets("03_毛利测算")
        ws5 = wb.Worksheets("05_分批结算")
        ws7 = wb.Worksheets("07_历史分位")

        r_rate = find_row(ws3, "基准汇率")
        r_net = find_row(ws3, "人民币净额")
        r_margin = find_row(ws3, "毛利额")
        r_mpct = find_row(ws3, "毛利率")
        r_zero = find_row(ws3, "毛利额 = 0")
        r_tp = find_row(ws3, "达到目标毛利率")
        print(f"（03 表定位：汇率{r_rate} 净额{r_net} 毛利{r_margin} 毛利率{r_mpct} 平衡{r_zero} 目标{r_tp}）")

        xl_rate = ws3.Cells(r_rate, 3).Value
        xl_net = ws3.Cells(r_net, 3).Value
        xl_margin = ws3.Cells(r_margin, 3).Value
        xl_mpct = ws3.Cells(r_mpct, 3).Value
        xl_be = ws3.Cells(r_zero, 3).Value
        xl_be_tp = ws3.Cells(r_tp, 3).Value
        if xl_be_tp is not None and not isinstance(xl_be_tp, (int, float)):
            xl_be_tp = None

        chk("基准汇率（01 C28 → 03）", xl_rate, scen["rate"]["base_rate"], 1e-9)
        chk("出口人民币净收入", xl_net, scen["base"]["net_cny"], 0.02)
        chk("毛利额", xl_margin, scen["base"]["margin_cny"], 0.02)
        chk("毛利率", xl_mpct, scen["base"]["margin_pct"], 1e-9)
        chk("盈亏平衡汇率（毛利=0）", xl_be, scen["breakevens"]["zero"]["breakeven"], 1e-9)
        if "target_pct" in scen["breakevens"]:
            chk("盈亏平衡汇率（目标毛利率）", xl_be_tp, scen["breakevens"]["target_pct"]["breakeven"], 1e-9)

        # 02 表基准行（数据末行）应与 03 表净额一致
        hdr2 = find_row(ws2, "汇率变动")
        base_row = None
        for r in range(hdr2 + 1, hdr2 + 20):
            if ws2.Cells(r, 2).Value is None:
                base_row = r - 1
                break
        chk("02 表基准行净额 = 03 表净额", ws2.Cells(base_row, 7).Value, xl_net, 1e-6)

        # 05 分批合计 = 订单金额
        r_tot5 = find_row(ws5, "合计")
        chk("05 分批合计 = 订单金额", ws5.Cells(r_tot5, 3).Value, scen["meta"]["amount_fx"], 0.01)

        # 07 分位
        r_pct = find_row(ws7, "当前值分位")
        chk("历史分位 近 1 年", ws7.Cells(r_pct, 3).Value, scen["stats"]["1y"]["pctile_mid"], 0.02)
        chk("历史分位 近 3 年", ws7.Cells(r_pct, 4).Value, scen["stats"]["3y"]["pctile_mid"], 0.02)
        r_max = find_row(ws7, "窗口最高")
        chk("1 年窗口最高价", ws7.Cells(r_max, 3).Value, scen["stats"]["1y"]["max"], 1e-6)

        # ---- 动态验证：改输入 → 结果必须变 ----
        old_net, old_margin, old_be = xl_net, xl_margin, xl_be
        base_rate = float(xl_rate)
        ws1.Range("C8").Value = 250000
        ws1.Range("C14").Value = 1500000
        excel.CalculateFullRebuild()
        new_net = ws3.Cells(r_net, 3).Value
        new_margin = ws3.Cells(r_margin, 3).Value
        new_be = ws3.Cells(r_zero, 3).Value
        changed = abs(new_net - old_net) > 1 and abs(new_be - old_be) > 1e-4
        ok_n += changed
        print(f"{'[PASS]' if changed else '[FAIL]'} 改输入后自动重算：净额 {old_net:,.0f}→{new_net:,.0f}，"
              f"毛利 {old_margin:,.0f}→{new_margin:,.0f}，平衡汇率 {old_be:.4f}→{new_be:.4f}")
        if not changed:
            fails.append("改输入后未重算")
        chk("新毛利 = 25万×汇率 − 150万（公式而非数值）", new_margin, 250000 * base_rate - 1500000, 1.0)

        # ---- 错误单元格扫描 ----
        errs = []
        for sheet in wb.Worksheets:
            try:
                cells = sheet.UsedRange.SpecialCells(-4123)   # xlCellTypeFormulas
            except Exception:
                continue
            for c in cells:
                v = c.Text
                if isinstance(v, str) and v.startswith("#"):
                    errs.append(f"{sheet.Name}!{c.Address(0, 0)}={v}")
        good = not errs
        ok_n += good
        if errs:
            fails.append("错误单元格: " + "; ".join(errs[:8]))
        print(f"{'[PASS]' if good else '[FAIL]'} 全簿公式无 #NAME?/#VALUE!/#REF!（{len(errs)} 处）")
        for e in errs[:10]:
            print("    ", e)
    finally:
        try:
            if wb is not None:
                wb.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            excel.Quit()
        except Exception:
            pass

    total = ok_n + len(fails)
    print(f"\nExcel 实算校验：{ok_n}/{total} 通过")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
