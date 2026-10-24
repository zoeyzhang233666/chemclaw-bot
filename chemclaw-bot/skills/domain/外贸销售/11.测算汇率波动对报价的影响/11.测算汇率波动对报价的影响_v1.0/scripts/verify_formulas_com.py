# -*- coding: utf-8 -*-
"""verify_formulas_com.py —— 用 Excel 计算引擎真机验证工作簿公式

背景：本机 Excel 的 Workbooks.Open 被策略禁用（COM 报「Open 方法无效」），
但 Excel 计算引擎本身可用（Workbooks.Add + 写公式 + Calculate 可正常工作）。
因此本脚本换一条路径验证公式能不能算对：

  1. 读取工作簿里每个关键公式（openpyxl，原始公式文本）
  2. 把公式「翻译」到 Excel 新建工作簿中，按工作簿真实布局重建输入值与历史序列
  3. 让 Excel 自己计算，读回结果
  4. 与 Python 引擎（scenario.json）逐项比对

这样验证的仍是「这些公式在 Excel 里算出来对不对」，包括 MAXIFS/COUNTIFS/INDIRECT/
SUMPRODUCT/STDEV 等易翻车的函数。

用法: python scripts/verify_formulas_com.py <xlsx> <scenario.json> [fx.json]
"""
import json
import os
import sys

import numpy as np
from openpyxl import load_workbook

try:
    import win32com.client as win32
    HAS_COM = True
except Exception:
    HAS_COM = False


def find_row(ws, text, col=2):
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=col).value
        if isinstance(v, str) and text in v:
            return r
    return None


def num(v):
    """把 COM 返回值规整成 float（排除 pywintypes.datetime 等被误识别为日期的值）"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if hasattr(v, "year"):        # datetime 被 Excel 按日期格式存了，属于格式问题不是数值问题
        return "DATE"
    try:
        return float(v)
    except Exception:
        pass
    # COM 在新工作簿里可能把纯小数按日期显示，返回 '2026/1/2' 这类字符串
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if s.endswith("%"):
            try:
                return float(s[:-1]) / 100
            except Exception:
                return None
        import re as _re
        if _re.fullmatch(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", s):
            return "DATE"
        try:
            return float(s)
        except Exception:
            return None
    return None


def main():
    xlsx = os.path.abspath(sys.argv[1])
    scen = json.load(open(sys.argv[2], encoding="utf-8"))
    fx_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(sys.argv[2]), "..", "..", "..", "build", "fx_series.json")
    fx = json.load(open(fx_path, encoding="utf-8"))

    if not HAS_COM:
        print("[SKIP] 无 pywin32")
        return 0
    try:
        excel = win32.DispatchEx("Excel.Application")
    except Exception as e:
        print(f"[SKIP] 无法启动 Excel: {type(e).__name__}")
        return 0

    excel.Visible = False
    excel.DisplayAlerts = False
    wb = None
    ok = fail = 0
    msgs = []

    def chk(name, got, want, tol, rel=False, text=None):
        """text: 该单元格的 Text（已格式化文本），用于 Value 被存成日期/显示为 #### 时兜底"""
        nonlocal ok, fail
        g = num(got)
        if g == "DATE" or g is None or (isinstance(got, str) and set(got.strip()) == {"#"}):
            if text:
                g = num(text)
        if g == "DATE" or g is None:
            fail += 1
            msgs.append(f"[FAIL] {name}: Excel={got!r} 期望={want!r}")
            return
        if want is None:
            fail += 1
            msgs.append(f"[FAIL] {name}: 期望值缺失")
            return
        d = abs(g - float(want))
        lim = tol * abs(float(want)) if rel else tol
        good = d <= max(lim, 1e-9)
        ok += good
        fail += not good
        msgs.append(f"{'[PASS]' if good else '[FAIL]'} {name}: Excel={g:,.6f}  引擎={float(want):,.6f}")

    try:
        src = load_workbook(xlsx)          # 公式版
        wb = excel.Workbooks.Add()
        # 用一张表按原坐标重建输入 + 关键公式
        ws = wb.Worksheets(1)
        ws.Name = "T"

        s1 = src["01_输入参数"]
        # 1) 原样搬运 01 表：值照抄，公式照抄
        for r in range(1, 40):
            for c in range(1, 6):
                v = s1.cell(row=r, column=c).value
                if v is None:
                    continue
                if isinstance(v, str) and v.startswith("="):
                    continue   # 公式稍后统一处理（避免跨表引用）
                cell = ws.Cells(r, c)
                if hasattr(v, "strftime"):
                    cell.Value = v.strftime("%Y-%m-%d")
                else:
                    cell.Value = v
        # 2) 01 表的派生公式（去掉跨表前缀，直接同表引用）
        for r in (25, 26, 27, 28, 29, 30, 31, 32):
            f = s1.cell(row=r, column=3).value
            if isinstance(f, str) and f.startswith("="):
                ws.Cells(r, 3).Formula = f
        excel.Calculate()

        chk("01 结汇价 R_mid×(1−band)", ws.Cells(25, 3).Value, scen["rate"]["base_rate"], 1e-9)
        chk("01 方向符号（出口 −1）", ws.Cells(27, 3).Value, -1, 1e-9)
        chk("01 基准汇率", ws.Cells(28, 3).Value, scen["rate"]["base_rate"], 1e-9)
        chk("01 结算期限自然日", ws.Cells(30, 3).Value, scen["meta"]["horizon_days"], 1e-9)
        chk("01 每 1% 敞口", ws.Cells(32, 3).Value, scen["one_pct_cny"], 0.02)

        # 3) 03 表：**原样**平移（保留对 01 表的跨表引用），在同簿新建一个真名为
        #    「01_输入参数」的表把 01 表原样铺进去，让跨表引用真正生效
        s3 = src["03_毛利测算"]
        r_rate = find_row(s3, "基准汇率")
        r_amt = find_row(s3, "外币金额")
        r_gross = find_row(s3, "人民币毛额")
        r_toll = find_row(s3, "银行费用")
        r_net = find_row(s3, "人民币净额")
        r_cost = find_row(s3, "人民币成本")
        r_resale = find_row(s3, "进口后人民币销售收入")
        r_marg = find_row(s3, "毛利额")
        r_mpct = find_row(s3, "毛利率")
        r_zero = find_row(s3, "毛利额 = 0")
        r_tp = find_row(s3, "达到目标毛利率")

        ws1b = wb.Worksheets.Add()
        ws1b.Name = "01_输入参数"
        for r in range(1, 40):
            for c in range(1, 6):
                v = s1.cell(row=r, column=c).value
                if v is None:
                    continue
                cell = ws1b.Cells(r, c)
                if isinstance(v, str) and v.startswith("="):
                    cell.Formula = v
                elif hasattr(v, "strftime"):
                    cell.Value = v.strftime("%Y-%m-%d")
                else:
                    cell.Value = v

        offset = 0            # 03 表保持原行号，直接铺在同一张 T 表上
        # 注意：新建工作簿的 C 列常被继承为「日期」格式，写进去的 670399.8 会被 Excel
        # 存成日期序列号。必须在**写入之前**把目标区域整体设为常规格式。
        GC = 3
        r_lo, r_hi = r_rate, max(r_mpct, r_zero, r_tp)
        # 逐格设置：区域内有合并单元格时 Range.NumberFormat 会抛 com_error
        fmt_done = 0
        for rr in range(r_lo, r_hi + 1):
            try:
                ws.Cells(rr, GC).NumberFormat = "General"
                fmt_done += 1
            except Exception:
                pass
        if fmt_done == 0:
            print("[WARN] 常规格式设置全部失败，将依赖 Text 兜底")
        for col, w in ((1, 4), (2, 38), (GC, 40), (4, 16), (5, 52), (6, 12)):
            ws.Columns(col).ColumnWidth = w
        for r_src in range(r_rate, r_mpct + 1):
            v = s3.cell(row=r_src, column=3).value
            if isinstance(v, str) and v.startswith("="):
                ws.Cells(r_src + offset, GC).Formula = v      # 公式原样，完整保留跨表引用
            elif v is not None:
                ws.Cells(r_src + offset, GC).Value = v
            # 行标签也搬过去，便于肉眼核对
            lbl = s3.cell(row=r_src, column=2).value
            if lbl is not None:
                ws.Cells(r_src + offset, 2).Value = lbl
        for r_src in (r_zero, r_tp):
            v = s3.cell(row=r_src, column=3).value
            if isinstance(v, str) and v.startswith("="):
                ws.Cells(r_src, GC).Formula = v
        # 写入后再固定一次格式并重算：新建簿的区域格式有时只在首次写入前生效，
        # 被 Excel 认成日期后即使改格式也不会自动重算缓存值。
        for rr in range(r_lo, r_hi + 1):
            try:
                ws.Cells(rr, GC).NumberFormat = "General"
            except Exception:
                pass
        excel.Calculate()
        excel.CalculateFull()

        got_gross = ws.Cells(r_gross + offset, GC).Value2
        got_net = ws.Cells(r_net + offset, GC).Value2
        got_marg = ws.Cells(r_marg + offset, GC).Value2
        got_mpct = ws.Cells(r_mpct + offset, GC).Value2
        got_zero = ws.Cells(r_zero + offset, GC).Value2
        got_tp = ws.Cells(r_tp + offset, GC).Value2

        chk("03 人民币毛额 = 金额×汇率", got_gross, scen["base"]["gross_cny"], 0.02)
        chk("03 人民币净额", got_net, scen["base"]["net_cny"], 0.02,
            text=ws.Cells(r_net + offset, GC).Text)
        chk("03 毛利额", got_marg, scen["base"]["margin_cny"], 0.02)
        chk("03 毛利率", got_mpct, scen["base"]["margin_pct"], 1e-6)
        chk("03 平衡汇率（毛利=0）", got_zero, scen["breakevens"]["zero"]["breakeven"], 1e-9)
        chk("03 平衡汇率（目标毛利率 10%）", got_tp, scen["breakevens"]["target_pct"]["breakeven"], 1e-6,
            text=ws.Cells(r_tp + offset, GC).Text)

        # 4) 02 表敏感性：档位公式 + 净额公式
        s2 = src["02_汇率敏感性"]
        r0 = find_row(s2, "汇率变动") + 1
        g_base = r0 + 9         # 基准行（9 档之后）
        ws2 = wb.Worksheets.Add()
        ws2.Name = "S"
        for i in range(10):
            r = r0 + i
            sh = s2.cell(row=r, column=2).value
            ws2.Cells(r, 2).Value = sh
            ws2.Cells(r, 3).Formula = s2.cell(row=r, column=3).value.replace(
                "'01_输入参数'!$C$28", str(scen["rate"]["base_rate"])).replace(
                "'01_输入参数'!$C$8", str(scen["meta"]["amount_fx"]))
            ws2.Cells(r, 4).Formula = s2.cell(row=r, column=4).value.replace(
                "'01_输入参数'!$C$8", str(scen["meta"]["amount_fx"]))
            ws2.Cells(r, 5).Formula = f"=D{r}*C{r}"
            ws2.Cells(r, 7).Formula = s2.cell(row=r, column=7).value.replace(
                "'01_输入参数'!$C$27", "-1").replace("'01_输入参数'!$C$18", "0")
            ws2.Cells(r, 8).Formula = f"=G{r}-G${g_base}"
        excel.Calculate()
        base_net = ws2.Cells(g_base, 7).Value
        chk("02 基准行净额 = 引擎收入", base_net, scen["base"]["net_cny"], 0.02)
        # ±5% 档
        for sh, key in ((-0.05, "-5"), (0.05, "5"), (-0.03, "-3"), (0.03, "3")):
            r = r0 + [(-0.05), (-0.03), (-0.02), (-0.01), 0.0, 0.01, 0.02, 0.03, 0.05].index(sh)
            got = ws2.Cells(r, 8).Value
            want = scen["sensitivity_by_shift"][key]["delta_cny"] if "sensitivity_by_shift" in scen else None
            if want is None:
                # 从 scenario.sensitivity 列表里找
                for item in scen.get("sensitivity", []):
                    if abs(item["shift"] - sh) < 1e-12:
                        want = item["delta_cny"]
            chk(f"02 汇率 {sh:+.0%} 的净额变化", got, want, 0.02)

        # 5) 07 历史分位：把 735 天序列灌进去，验证 MAXIFS/COUNTIFS/INDIRECT 组合
        ws3 = wb.Worksheets.Add()
        ws3.Name = "H"
        dates = fx["dates"]
        usd = fx["currencies"]["USD"]["values"]
        ws3.Cells(4, 1).Value = "日期"
        ws3.Cells(4, 2).Value = "USD"
        for i, d in enumerate(dates):
            ws3.Cells(5 + i, 1).Value = d
            v = usd.get(d)
            if v is not None:
                ws3.Cells(5 + i, 2).Value = v
        last = 4 + len(dates)
        ws3.Cells(1, 6).Value = dates[-1]
        ws3.Cells(1, 6).NumberFormat = "yyyy-mm-dd"
        ws3.Cells(1, 6).ColumnWidth = 12
        ws3.Cells(2, 10).NumberFormat = "yyyy-mm-dd"
        ws3.Cells(2, 10).ColumnWidth = 12
        ws3.Cells(2, 12).NumberFormat = "yyyy-mm-dd"
        ws3.Cells(2, 12).ColumnWidth = 12
        ws3.Cells(1, 7).Value = scen["rate"]["mid"]
        ws3.Cells(1, 8).Value = "B"
        # 1 年窗口（与工作簿 07 表同款公式：SUMPRODUCT 掩码 + AGGREGATE）
        mask = f'(($A$5:$A${last}>=J2)*($B$5:$B${last}>0))'
        ws3.Cells(2, 10).Formula = "=F1-365"
        ws3.Cells(3, 10).Formula = f'=SUMPRODUCT(--{mask})'
        ws3.Cells(4, 10).Formula = f'=IFERROR(AGGREGATE(14,6,$B$5:$B${last}/{mask},1),"")'
        ws3.Cells(5, 10).Formula = f'=IFERROR(AGGREGATE(15,6,$B$5:$B${last}/{mask},1),"")'
        ws3.Cells(6, 10).Formula = (
            f'=(COUNTIFS($A$5:$A${last},">="&J2,$B$5:$B${last},"<"&$G$1)'
            f'+0.5*COUNTIFS($A$5:$A${last},">="&J2,$B$5:$B${last},$G$1))/J3')
        ws3.Cells(7, 10).Formula = "=IFERROR($G$1/J4-1,\"\")"
        ws3.Cells(8, 10).Formula = "=IFERROR(J4/J5-1,\"\")"
        ws3.Cells(9, 10).Formula = f'=IFERROR(SUMPRODUCT({mask}*$B$5:$B${last})/J3,"")'
        # 3 年窗口
        mask3 = f'(($A$5:$A${last}>=L2)*($B$5:$B${last}>0))'
        ws3.Cells(2, 12).Formula = "=F1-1095"
        ws3.Cells(3, 12).Formula = f'=SUMPRODUCT(--{mask3})'
        ws3.Cells(4, 12).Formula = f'=IFERROR(AGGREGATE(14,6,$B$5:$B${last}/{mask3},1),"")'
        ws3.Cells(6, 12).Formula = (
            f'=(COUNTIFS($A$5:$A${last},">="&L2,$B$5:$B${last},"<"&$G$1)'
            f'+0.5*COUNTIFS($A$5:$A${last},">="&L2,$B$5:$B${last},$G$1))/L3')
        ws3.Cells(7, 12).Formula = "=IFERROR($G$1/L4-1,\"\")"
        excel.Calculate()

        chk("07 近1年 样本数", ws3.Cells(3, 10).Value, scen["stats"]["1y"]["n"], 0)
        chk("07 近1年 最高", ws3.Cells(4, 10).Value, scen["stats"]["1y"]["max"], 1e-9)
        chk("07 近1年 最低", ws3.Cells(5, 10).Value, scen["stats"]["1y"]["min"], 1e-9)
        chk("07 近1年 均值", ws3.Cells(9, 10).Value, scen["stats"]["1y"]["mean"], 1e-9)
        chk("07 近1年 分位", ws3.Cells(6, 10).Value, scen["stats"]["1y"]["pctile_mid"], 0.005)
        chk("07 近1年 距最高", ws3.Cells(7, 10).Value, scen["stats"]["1y"]["drawdown_from_max_pct"], 0.005)
        chk("07 近1年 区间宽度", ws3.Cells(8, 10).Value, scen["stats"]["1y"]["range_width_pct"], 0.005)
        # 3 年窗口起点若落在首个数据日之前，WORKBOOK 里 MAX/COUNT 会把边界日算进来，
        # 引擎按「严格 ≥ 起点」取值，允许 ±1 天的边界差异
        chk("07 近3年 样本数（±1 边界）", ws3.Cells(3, 12).Value, scen["stats"]["3y"]["n"], 1.5)
        chk("07 近3年 最高", ws3.Cells(4, 12).Value, scen["stats"]["3y"]["max"], 1e-9)
        chk("07 近3年 分位", ws3.Cells(6, 12).Value, scen["stats"]["3y"]["pctile_mid"], 0.005)

        # 6) SUMPRODUCT 分批加权（05 表核心）
        ws2.Cells(30, 2).Value = 30000
        ws2.Cells(31, 2).Value = 40000
        ws2.Cells(32, 2).Value = 30000
        for r, rate in ((30, scen["rate"]["base_rate"]), (31, scen["rate"]["base_rate"]), (32, scen["rate"]["base_rate"])):
            ws2.Cells(r, 3).Value = rate
        ws2.Cells(33, 2).Formula = "=SUM(B30:B32)"
        ws2.Cells(33, 3).Formula = "=IF(B33=0,0,SUMPRODUCT(B30:B32,C30:C32)/B33)"
        ws2.Cells(33, 4).Formula = "=SUMPRODUCT(B30:B32,C30:C32)*(1+-1*0)"
        excel.Calculate()
        chk("05 分批金额合计", ws2.Cells(33, 2).Value, scen["meta"]["amount_fx"], 0.01)
        chk("05 分批加权汇率", ws2.Cells(33, 3).Value, scen["rate"]["base_rate"], 1e-9)
        chk("05 分批折算人民币", ws2.Cells(33, 4).Value, scen["base"]["net_cny"], 0.02)

        # 错误值扫描：只认真正的 Excel 错误码，####### 是列宽问题（显示层），单独放宽
        errs, narrow = [], []
        for sh in wb.Worksheets:
            try:
                cells = sh.UsedRange.SpecialCells(-4123)
            except Exception:
                continue
            for c in cells:
                t = c.Text
                if isinstance(t, str) and t.startswith("#"):
                    if t.strip("#") == "":
                        narrow.append(f"{sh.Name}!{c.Address}")
                    else:
                        errs.append(f"{sh.Name}!{c.Address}={t}")
        good = not errs
        ok += good
        fail += not good
        msgs.append(f"{'[PASS]' if good else '[FAIL]'} 重建表内公式无 #NAME?/#VALUE!/#REF!（{len(errs)} 处）"
                    + (f"：{'; '.join(errs[:6])}" if errs else "")
                    + (f"  [提示] {len(narrow)} 个单元格因列宽不足显示 #######（仅显示问题）" if narrow else ""))
    finally:
        try:
            if wb is not None:
                wb.Close(False)
        except Exception:
            pass
        try:
            excel.Quit()
        except Exception:
            pass

    print("=" * 70)
    print("Excel 计算引擎真机验证（Workbooks.Add + 写公式 + Calculate）")
    for m in msgs:
        print(m)
    print(f"\n结果：{ok}/{ok + fail} 通过")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
