#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 计算内核自测（纯标准库，不需要 pytest / numpy）

覆盖：日期/周锚、口径换算、对齐与缺口、价差方向与等价、分位与中秩、
      窗口、滚动分位、运费（含缺失不填 0）、异常阶段识别。

用法：python scripts/selftest.py
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import spreadlib as L

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PASS, FAIL = [], []


def t(name):
    def deco(fn):
        try:
            fn()
            PASS.append(name)
            print(f"  [PASS] {name}")
        except AssertionError as e:
            FAIL.append((name, str(e)))
            print(f"  [FAIL] {name}  {e}")
        except Exception as e:
            FAIL.append((name, f"{type(e).__name__}: {e}"))
            print(f"  [FAIL] {name}  {type(e).__name__}: {e}")
        return fn
    return deco


def eq(a, b, tol=1e-9, msg=""):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        assert abs(a - b) <= tol, f"{msg} 期望 {b}，实得 {a}"
    else:
        assert a == b, f"{msg} 期望 {b!r}，实得 {a!r}"


def d(s):
    return L.parse_date(s)


PRODUCT = {"tax_rate": 0.13, "unit_scale": 1.0, "spec": "重质"}
TGT_DEL = {"tax_included": True, "payment": "现汇", "delivery": "DELIVERED"}
TGT_EXW = {"tax_included": True, "payment": "现汇", "delivery": "EXW"}


# ---------------- 日期 ----------------
@t("parse_date / iso 基本解析")
def _():
    eq(L.parse_date("2025-06-27"), date(2025, 6, 27), msg="parse")
    eq(L.iso(date(2025, 6, 27)), "2025-06-27", msg="iso")


@t("week_end 返回该周周五（不是周日）")
def _():
    eq(L.week_end(date(2025, 6, 27)), date(2025, 6, 27), msg="周五不变")
    eq(L.week_end(date(2025, 6, 23)), date(2025, 6, 27), msg="周一→周五")
    eq(L.week_end(date(2025, 6, 29)), date(2025, 6, 27), msg="周日→本周五")
    eq(L.week_end(date(2025, 6, 30)), date(2025, 7, 4), msg="下周一→下周五")


@t("iso_week 返回 'YYYY-Www' 字符串，跨年边界正确")
def _():
    eq(L.iso_week(date(2025, 1, 1)), "2025-W01", msg="2025-01-01")
    eq(L.iso_week(date(2024, 12, 30)), "2025-W01", msg="2024-12-30 属 2025 年第 1 周")
    eq(L.iso_week(date(2025, 6, 27)), "2025-W26", msg="2025-06-27")


# ---------------- 口径换算 ----------------
@t("含税 → 不含税（13%）")
def _():
    r = L.normalize_price(1130, {"tax_included": True}, PRODUCT, {"tax_included": False,
                          "payment": "现汇", "delivery": None})
    eq(r["value"], 1000.0, msg="1130/1.13")
    eq(len(r["steps"]), 1, msg="1 步")


@t("承兑 → 现汇：有贴息则扣，缺贴息则记 missing 且不换算")
def _():
    r = L.normalize_price(1300, {"payment": "承兑", "payment_discount": 30}, PRODUCT, TGT_DEL)
    eq(r["value"], 1270.0, msg="1300-30")
    r2 = L.normalize_price(1300, {"payment": "承兑"}, PRODUCT, TGT_DEL)
    assert "payment_discount" in r2["missing"], f"应记 missing，实得 {r2['missing']}"
    eq(r2["basis_ok"], False, msg="不可比")
    eq(r2["value"], 1300.0, msg="未扣（不填 0，也不乱扣）")


@t("送到 → 出厂：有内含运费则扣，缺则记 missing")
def _():
    r = L.normalize_price(1375, {"delivery": "DELIVERED", "freight_included": 75}, PRODUCT, TGT_EXW)
    eq(r["value"], 1300.0, msg="1375-75")
    r2 = L.normalize_price(1375, {"delivery": "DELIVERED"}, PRODUCT, TGT_EXW)
    assert "freight_included" in r2["missing"], f"应记 missing，实得 {r2['missing']}"


@t("同口径换算：步数为 0（主口径正确的证据）")
def _():
    r = L.normalize_price(1370, {"delivery": "DELIVERED", "tax_included": True,
                                 "payment": "现汇"}, PRODUCT, TGT_DEL)
    eq(r["value"], 1370.0, msg="价格不变")
    eq(len(r["steps"]), 0, msg="无换算步骤")
    eq(r["basis_ok"], True, msg="已同口径")


# ---------------- 对齐 ----------------
def _long():
    return [
        {"region": "A", "date": d("2025-01-03"), "adj": 100.0, "price": 100.0},
        {"region": "B", "date": d("2025-01-03"), "adj": 90.0, "price": 90.0},
        {"region": "A", "date": d("2025-01-10"), "adj": 110.0, "price": 110.0},
        {"region": "B", "date": d("2025-01-10"), "adj": 100.0, "price": 100.0},
        {"region": "B", "date": d("2025-01-17"), "adj": 105.0, "price": 105.0},   # A 缺
        {"region": "A", "date": d("2025-01-24"), "adj": 130.0, "price": 130.0},
        {"region": "B", "date": d("2025-01-24"), "adj": 120.0, "price": 120.0},
    ]


@t("对齐 exact：缺口日期被剔除，不插值、不前向填充")
def _():
    al = L.align_series(_long(), ["A", "B"], method="exact")
    # exact 模式先用三地日期交集，缺口日期不进入基准日
    eq(len(al["dates"]), 3, msg="4 个日期中 1 个被剔除")
    assert d("2025-01-17") not in al["dates"], "缺口日期不得进入样本"
    eq(al["values"]["A"], [100.0, 110.0, 130.0], msg="A 不得被填充")
    eq(al["values"]["B"], [90.0, 100.0, 120.0], msg="B 不得被填充")


@t("对齐 weekly：缺一周即整周剔除并记录缺失地区")
def _():
    al = L.align_series(_long(), ["A", "B"], method="weekly")
    eq(len(al["dates"]), 3, msg="4 周中 1 周被剔除")
    eq(len(al["dropped"]), 1, msg="剔除 1 期")
    eq(al["dropped"][0]["missing"], ["A"], msg="缺失地区记录")


@t("价差方向：spread(a,b)=P(a)-P(b)，b-a 为相反数")
def _():
    al = L.align_series(_long(), ["A", "B"], method="exact")
    ab = L.spread_series(al, "A", "B")
    ba = L.spread_series(al, "B", "A")
    eq([x[3] for x in ab], [10.0, 10.0, 10.0], msg="A-B")
    eq([x[3] for x in ba], [-10.0, -10.0, -10.0], msg="B-A")
    for x, y in zip(ab, ba):
        eq(x[3], -y[3], msg="互为相反数")


@t("有序对 = n(n-1)，无序对 = n(n-1)/2")
def _():
    regs = ["A", "B", "C"]
    eq(len(L.directional_pairs(regs)), 6, msg="有序对")
    eq(len(L.unordered_pairs(regs)), 3, msg="无序对")


@t("矩阵 M[i][j]=-M[j][i]，对角 0，三角闭合")
def _():
    rows = []
    for reg, px in (("A", 100.0), ("B", 90.0), ("C", 95.0)):
        rows.append({"region": reg, "date": d("2025-01-03"), "adj": px, "price": px})
    al = L.align_series(rows, ["A", "B", "C"], method="exact")
    mat, meta = L.spread_matrix(al, ["A", "B", "C"])
    eq(mat["A|A"], 0, msg="对角")
    eq(mat["A|B"], 10, msg="A-B")
    eq(mat["B|A"], -10, msg="B-A")
    eq(mat["A|B"] + mat["B|C"] + mat["C|A"], 0, tol=1e-9, msg="三角闭合")
    for a in ("A", "B", "C"):
        for b in ("A", "B", "C"):
            eq(mat[a + "|" + b], -mat[b + "|" + a], msg=f"{a}|{b} 互为相反数")


# ---------------- 分位 ----------------
@t("分位中秩：并列值 [10,20,20,30] 的 20 → 50%")
def _():
    eq(L.percentile_of(20, [10, 20, 20, 30]), 50.0, msg="中秩")
    eq(L.percentile_of(10, [10, 20, 20, 30]), 12.5, msg="最小值")
    eq(L.percentile_of(30, [10, 20, 20, 30]), 87.5, msg="最大值")
    eq(L.percentile_of(25, [10, 20, 20, 30]), 75.0, msg="非样本值")


@t("分位边界：单元素 50%，空样本 None")
def _():
    eq(L.percentile_of(5, [5]), 50.0, msg="单元素")
    eq(L.percentile_of(5, []), None, msg="空样本")


@t("quantile 线性插值")
def _():
    eq(L.quantile([1, 2, 3, 4], 0.5), 2.5, msg="中位")
    eq(L.quantile([1, 2, 3, 4], 0.0), 1.0, msg="min")
    eq(L.quantile([1, 2, 3, 4], 1.0), 4.0, msg="max")


@t("window_sample 按自然日回溯")
def _():
    s = [(d("2024-12-20"), 1), (d("2025-06-20"), 2), (d("2025-12-19"), 3)]
    # 2025-12-19 往前 365 天 = 2024-12-19，故 2024-12-20 仍在窗口内（边界要按日历算，不能想当然）
    got = L.window_sample(s, "2025-12-19", "1y", col=1)
    eq(sorted(got), [1, 2, 3], msg="1y 窗口含 2024-12-20")
    s2 = s + [(d("2024-12-01"), 0)]
    eq(sorted(L.window_sample(s2, "2025-12-19", "1y", col=1)), [1, 2, 3],
       msg="2024-12-01 在 365 天之外，应被排除")
    # 字符串与 date 两种入参结果必须一致
    eq(L.window_sample(s, d("2025-12-19"), "1y", col=1),
       L.window_sample(s, "2025-12-19", "1y", col=1), msg="str/date 入参一致")
    got3 = L.window_sample(s, "2025-12-19", "3y", col=1)
    eq(len(got3), 3, msg="3y 全含")
    eq(len(L.window_sample(s, "2025-12-19", "all", col=1)), 3, msg="all")


@t("分位标签边界")
def _():
    eq(L.percentile_label(95), "历史高位（≥P90）", msg="95")
    eq(L.percentile_label(90), "历史高位（≥P90）", msg="90 边界")
    eq(L.percentile_label(80), "偏高（P75–P90）", msg="80")
    eq(L.percentile_label(50), "中枢区间（P25–P75）", msg="50")
    eq(L.percentile_label(5), "历史低位（≤P10）", msg="5")
    eq(L.percentile_label(None), "样本不足", msg="None")


@t("滚动分位：样本 <30 时不计算")
def _():
    base = d("2025-01-01")
    s = [(base + timedelta(days=7 * i), float(i)) for i in range(1, 11)]
    roll = L.rolling_percentile(s, 365, 30, col=1)
    assert all(x[1] is None for x in roll), "10 个点 < 30，应全部为 None"
    # 40 个点后应开始有值
    s2 = [(base + timedelta(days=7 * i), float(i)) for i in range(1, 41)]
    roll2 = L.rolling_percentile(s2, 365, 30, col=1)
    assert roll2[29][1] is not None, "第 30 个点起应开始计算"
    assert roll2[0][1] is None, "第 1 个点应为 None"


# ---------------- 运费 ----------------
@t("综合运费 = 主运费 + 装货 + 卸货 + 短驳 + 其他")
def _():
    r = L.freight_total({"freight": 96},
                        {"loading_fee": 8, "unloading_fee": 10, "short_haul": 0, "handler": 2})
    eq(r["total"], 116.0, msg="96+8+10+0+2")
    eq(r["freight_known"], True, msg="已知")


@t("运费未知 → total 为 None（绝不按 0 计）")
def _():
    r = L.freight_total({"freight": None},
                        {"loading_fee": 8, "unloading_fee": 10, "handler": 2})
    assert r["total"] is None, f"应为 None，实得 {r['total']}"
    eq(r["freight_known"], False, msg="未知")


@t("扣费后参考差异 = P(目的) - (P(产地) + 运费)")
def _():
    r = L.freight_adjusted_spread(1370, 1275, {"freight": 96},
                                 {"loading_fee": 8, "unloading_fee": 10, "handler": 2})
    eq(r["freight_total"], 116.0, msg="运费")
    eq(r["ref_diff"], 1275 - (1370 + 116), msg="参考差异 = -211")
    eq(r["covers_freight"], False, msg="未覆盖")


@t("运费未知时不计算参考差异")
def _():
    r = L.freight_adjusted_spread(1370, 1275, {"freight": None},
                                 {"loading_fee": 8, "unloading_fee": 10, "handler": 2})
    eq(r["ok"], False, msg="ok 应为 False")
    assert r.get("ref_diff") is None, f"参考差异应为 None，实得 {r.get('ref_diff')}"


# ---------------- 异常阶段 ----------------
@t("异常阶段：持续偏移能识别，且方向为『走阔』")
def _():
    base = d("2023-01-06")
    # 带噪音的基准 + 6 周持续偏移（真实价差就是这样：不是 0 波动）
    vals = ([100 + (i % 5) * 1.5 for i in range(60)]
            + [128 + (i % 5) * 1.5 for i in range(6)]
            + [100 + (i % 5) * 1.5 for i in range(70)])
    s = [(base + timedelta(days=7 * i), None, None, float(v)) for i, v in enumerate(vals)]
    regs = L.regime_scan(s)
    assert len(regs) >= 1, f"应至少识别 1 段，实得 {len(regs)}"
    top = regs[0]
    assert top["n"] >= 3, f"段内期数应 ≥3，实得 {top['n']}"
    eq(top["direction"], "走阔", msg="价差上移应为走阔")


@t("异常阶段：几乎不动的小幅抖动不应被误判为异常（低方差防御）")
def _():
    base = d("2023-01-06")
    # 只在 100 与 101 之间抖动 —— 统计上可能 z 很大，但经济上毫无意义
    vals = [100.0 + (i % 2) for i in range(120)]
    s = [(base + timedelta(days=7 * i), None, None, v) for i, v in enumerate(vals)]
    regs = L.regime_scan(s)
    eq(len(regs), 0, msg="±1 元抖动不应识别为异常阶段")


@t("异常阶段：单周尖峰（<3 周）不成段")
def _():
    base = d("2023-01-06")
    vals = [100 + (i % 5) * 1.5 for i in range(120)]
    vals[70] = 190.0      # 单周尖峰
    vals[71] = 100 + (71 % 5) * 1.5
    s = [(base + timedelta(days=7 * i), None, None, float(v)) for i, v in enumerate(vals)]
    regs = L.regime_scan(s)
    assert all(x["n"] >= 3 for x in regs), f"不应出现 <3 周的段，实得 {[x['n'] for x in regs]}"


# ---------------- 统计 ----------------
@t("describe 基本统计")
def _():
    r = L.describe([1, 2, 3, 4, 5])
    eq(r["n"], 5, msg="n")
    eq(r["mean"], 3.0, msg="mean")
    eq(r["min"], 1, msg="min")
    eq(r["max"], 5, msg="max")


@t("describe 忽略空值")
def _():
    r = L.describe([1, None, 3])
    eq(r["n"], 2, msg="有效数")
    eq(r["mean"], 2.0, msg="mean")


@t("sd 用 n-1（样本标准差）")
def _():
    eq(L.sd([2, 4, 4, 4, 5, 5, 7, 9]), 2.138089935299395, tol=1e-9, msg="经典算例")


print("\n" + "=" * 60)
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    for n, e in FAIL:
        print(f"  ✗ {n}: {e}")
print("=" * 60)
sys.exit(0 if not FAIL else 1)
