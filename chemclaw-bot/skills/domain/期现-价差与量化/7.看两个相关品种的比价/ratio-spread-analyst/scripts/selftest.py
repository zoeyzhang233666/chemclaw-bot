# -*- coding: utf-8 -*-
"""
selftest.py — 统计内核已知答案校验（纯标准库）
================================================
每一个断言都有独立于本代码库的正确答案来源
（手算、Excel 函数、教科书公式），用来证明"分位不是编的"。
运行：python scripts/selftest.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ratiolib as R

PASS, FAIL = 0, 0
MSGS = []


def check(name, got, want, tol=1e-9):
    global PASS, FAIL
    if want is None:
        ok = got is None
    elif got is None:
        ok = False
    elif isinstance(want, tuple):
        ok = (isinstance(got, tuple) and len(got) == len(want)
              and all(_close_or_eq(g, w, tol) for g, w in zip(got, want)))
    elif isinstance(want, bool):
        ok = (got is want)
    else:
        ok = _close_or_eq(got, want, tol)
    if ok:
        PASS += 1
        MSGS.append("  PASS  %-46s got=%s" % (name, _f(got)))
    else:
        FAIL += 1
        MSGS.append("  FAIL  %-46s got=%s want=%s" % (name, _f(got), _f(want)))


def _f(v):
    if v is None:
        return "None"
    if isinstance(v, float):
        return ("%.10g" % v)
    return str(v)


def _close_or_eq(got, want, tol):
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        if isinstance(got, (int, float)) and not isinstance(got, bool):
            return abs(got - want) <= tol
        return False
    return got == want


print("=" * 74)
print("ratiolib selftest")
print("=" * 74)

# ---- 1. 基础统计 ----
d = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
check("mean(1..10)", R.mean(d), 5.5)
check("median odd", R.median([3, 1, 2]), 2.0)
check("median even (1..10)", R.median(d), 5.5)
check("median 2 values", R.median([10, 2]), 6.0)
# 样本标准差(1..10) 手算 = sqrt(82.5/9) = 3.0276503541
check("stdev(1..10) ddof=1", R.stdev(d), 3.0276503540974917, 1e-9)
# 总体标准差 = sqrt(8.25) = 2.8722813232
check("stdev(1..10) ddof=0", R.stdev(d, ddof=0), 2.8722813232690143, 1e-9)
check("stdev n=1 -> None", R.stdev([5]), None)
check("mean empty -> None", R.mean([]), None)
check("mean skips None", R.mean([1, None, 3]), 2.0)

# ---- 2. 分位数（Excel PERCENTILE.INC 一致） ----
# PERCENTILE.INC(1..10, 0.5) = 5.5 ; 0.25 = 3.25 ; 0.9 = 9.1 ; 0 = 1 ; 1 = 10
check("quantile 0.25 (1..10)", R.quantile(d, .25), 3.25)
check("quantile 0.5  (1..10)", R.quantile(d, .5), 5.5)
check("quantile 0.9  (1..10)", R.quantile(d, .9), 9.1)
check("quantile 0    (1..10)", R.quantile(d, 0), 1.0)
check("quantile 1    (1..10)", R.quantile(d, 1), 10.0)
check("quantile single", R.quantile([7], .3), 7.0)

# ---- 3. 分位排名（核心：必须是经验分布，不能拿 max/min 反推） ----
# 样本 1..10，值 5 -> below=4, ties=1 -> (4+0.5)/10 = 45%
check("pct_rank 5 in 1..10", R.percentile_rank(d, 5)["pct"], 45.0)
# 值 1 -> below=0, ties=1 -> 5%
check("pct_rank 1 in 1..10", R.percentile_rank(d, 1)["pct"], 5.0)
# 值 10 -> below=9, ties=1 -> 95%
check("pct_rank 10 in 1..10", R.percentile_rank(d, 10)["pct"], 95.0)
# 值 20（高于全部）-> below=10 -> 100%
check("pct_rank 20 in 1..10", R.percentile_rank(d, 20)["pct"], 100.0)
# 值 0.5 -> 0%
check("pct_rank 0.5 in 1..10", R.percentile_rank(d, 0.5)["pct"], 0.0)
check("pct_rank N reported", R.percentile_rank(d, 5)["n"], 10)

# 反例演示：若用 (v-min)/(max-min) 线性反推，值 5 会得到 44.4%，与真实分位不同
lin = (5 - 1) / (10 - 1) * 100
assert abs(lin - 44.444444) < 1e-5
check("linear-interp differs from empirical(<0.6pp here)", R.percentile_rank(d, 5)["pct"] - lin, 0.5555556, 1e-6)

# 真实比价场景式的厚尾样本：极值不应压扁分位
heavy = [0.95] * 90 + [1.05] * 5 + [1.20, 0.70]
# 90 个 0.95；值 1.00 -> below = 91 (90x0.95 + 0.70)，无并列 -> 91/97
check("heavy-tail pct_rank 1.00", R.percentile_rank(heavy, 1.00)["pct"], 91 / 97 * 100, 1e-9)
# 线性反推会给出 (1.00-0.70)/(1.20-0.70)=60%，严重低估 → 证明必须用经验分布
lin2 = (1.00 - 0.70) / (1.20 - 0.70) * 100
check("linear-interp badly understates (60 vs 93.8)", lin2, 60.0)

# ---- 4. 十分位 ----
check("decile 5 in 1..10 (45%)", R.decile_position(5, d), 5)
check("decile 10 (95%)", R.decile_position(10, d), 10)
check("decile 1 (5%)", R.decile_position(1, d), 1)

# ---- 5. 比价构造 ----
A = [("2024-01-01", 100.0), ("2024-01-02", 110.0), ("2024-01-03", None), ("2024-01-04", 90.0)]
B = [("2024-01-01", 50.0), ("2024-01-02", 55.0), ("2024-01-03", 60.0), ("2024-01-04", 30.0)]
rows = R.build_ratio(A, B)
check("build_ratio len", len(rows), 4)
check("ratio day1 = 100/50", rows[0][3], 2.0)
check("ratio day2 = 110/55", rows[1][3], 2.0)
check("missing A -> ratio None", rows[2][3], None)
check("missing flags (a_miss)", rows[2][4], True)
check("ratio day4 = 90/30", rows[3][3], 3.0)
check("valid_pairs skips None", len(R.valid_pairs(rows)), 3)

# 分母为 0 必须留空而不是报错/无法定义
zero = R.build_ratio([("2024-01-01", 10.0)], [("2024-01-01", 0.0)])
check("zero denominator -> None", zero[0][3], None)

# 方向反转
inv = R.invert_ratio(rows)
check("invert: day1 ratio 0.5", inv[0][3], 0.5)
check("invert: swaps A/B", (inv[0][1], inv[0][2]), (50.0, 100.0))
check("invert: None stays None", inv[2][3], None)
check("invert twice == identity", R.invert_ratio(inv)[3][3], rows[3][3])

# ---- 6. 窗口统计 ----
vals = [("2024-01-%02d" % i, 1.0 + i / 100) for i in range(1, 21)]  # 1.01 .. 1.20
rows2 = R.build_ratio([(d, v) for d, v in vals], [(d, 1.0) for d, _ in vals])
st = R.window_stats(rows2)
check("window n", st["n"], 20)
check("window current (last)", st["current"], 1.20)
check("window min", st["min"], 1.01)
check("window max", st["max"], 1.20)
check("window pct_rank of max", st["pct_rank"], 97.5)
check("window median (1.01..1.20)", st["median"], 1.105)
# 窗口切片
st2 = R.window_stats(rows2, "2024-01-01", "2024-01-10")
check("window slice n=10", st2["n"], 10)
check("window slice max", st2["max"], 1.10)
check("window slice pct of 1.10 = 95", st2["pct_rank"], 95.0)

# ---- 7. 前序样本口径（避免用自己给自己打分） ----
# 前 15 天在 1.01..1.15，最后 5 天猛拉到 1.16..1.20
st3 = R.prior_sample_stats(rows2, prior_days=5)
check("prior_sample n (excl last 5)", st3["n"], 15)
check("prior_sample max (before spike)", st3["max"], 1.15)
check("prior_sample pct of 1.20 = 100", st3["pct_rank"], 100.0)
st4 = R.prior_sample_stats(rows2, prior_days=500)
check("prior_sample too small -> None", st4["pct_rank"], None)

# ---- 8. 滚动分位 ----
# 说明：rolling_percentile 要求 min(20, window/2) 个样本才出值，
# 所以 20 行数据 + window=10 仍然不足 → 这里改用 60 行数据验证
long_vals = [("D%03d" % i, 1.0 + (i % 7) * 0.01) for i in range(60)]
long_rows = R.build_ratio(long_vals, [(d, 1.0) for d, _ in long_vals])
rp = R.rolling_percentile(long_rows, window=20, prior_days=0)
check("rolling len", len(rp), 60)
check("rolling first rows -> None", rp[0][1], None)
check("rolling defined once enough history", rp[-1][1] is not None, True)
# 窗口末端值必须是该窗口内的经验分位
# 最后一个点 i=59，窗口 = 之前 window=20 个样本，即 i=39..58
last_win = [long_vals[i][1] for i in range(39, 59)]
check("rolling last value = empirical pct of its window",
      rp[-1][1], R.percentile_rank(last_win, long_vals[-1][1])["pct"], 1e-9)
# prior_days 太大 → 最新点也没有足够前序样本
rp2 = R.rolling_percentile(long_rows, window=20, prior_days=50)
check("rolling w/ prior 50 has no value in 60 rows", rp2[-1][1], None)
# prior_days=20 时最新点的样本应为 i=19..38（再往前 20 个），确认与本体不同窗口
rp3 = R.rolling_percentile(long_rows, window=20, prior_days=20)
check("rolling prior=20 defined at last point", rp3[-1][1] is not None, True)
check("rolling prior shifts the window",
      rp3[-1][1], R.percentile_rank([long_vals[i][1] for i in range(19, 39)], long_vals[-1][1])["pct"], 1e-9)

# ---- 9. 贡献分解 ----
# A 从 100→120 (+20%)，B 从 100→110 (+10%) → r: 1.0 → 1.0909…
c_rows = R.build_ratio([("d1", 100.0), ("d2", 120.0)], [("d1", 100.0), ("d2", 110.0)])
c = R.contribution(c_rows, "d1", "d2")
check("contrib a_chg", c["a_chg_pct"], 20.0)
check("contrib b_chg", c["b_chg_pct"], 10.0)
check("contrib ratio_chg", c["ratio_chg_pct"], (120 / 110 - 1) * 100)
# share: |ln1.2|=0.18232, |ln1.1|=0.09531 → 65.67% / 34.33%
check("contrib share_a", c["share_a"], 0.182321556793954 / (0.182321556793954 + 0.0953101798043249) * 100, 1e-9)
check("contrib dominant = A", c["dominant"], "A")
check("contrib log_ratio", c["log_ratio"], 0.1823215567939546 - 0.0953101798043249, 1e-12)

# 单边情形：B 完全不动，A 涨 20% → A 贡献 100%
c2 = R.contribution(R.build_ratio([("d1", 100.0), ("d2", 120.0)], [("d1", 100.0), ("d2", 100.0)]), "d1", "d2")
check("single-side share_a = 100", c2["share_a"], 100.0)
check("single-side share_b = 0", c2["share_b"], 0.0)

# 两边同涨，A 涨更多 → 比价仍上升，但两边都有贡献
check("contrib b_start preserved", c["b_start"], 100.0)

# ---- 10. 逐日贡献 ----
dc = R.daily_contribution(c_rows)
check("daily_contribution rows", len(dc), 1)
check("daily contrib A ~ +18.23pp", dc[0][1], 18.2321556793954, 1e-9)
check("daily contrib B ~ -9.53pp", dc[0][2], -9.5310179804325, 1e-9)
check("daily contrib ratio ~ +8.70pp", dc[0][3], (0.1823215567939546 - 0.0953101798043249) * 100, 1e-9)
# 恒等式：A贡献 + B贡献 = 比价变化
check("identity a+b == ratio", dc[0][1] + dc[0][2], dc[0][3], 1e-9)

# ---- 11. 相关系数 ----
check("pearson perfect", R.pearson([1, 2, 3], [2, 4, 6]), 1.0)
check("pearson negative", R.pearson([1, 2, 3], [6, 4, 2]), -1.0)
check("pearson n<3 -> None", R.pearson([1, 2], [2, 4]), None)
check("spearman monotone", R.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
# 非线性单调：Spearman=1 但 Pearson<1
check("spearman robust to nonlinear", R.spearman([1, 2, 3, 4], [1, 4, 9, 16]), 1.0)

# ---- 12. OLS ----
o = R.ols([2, 4, 6], [1, 2, 3])   # y=2x
check("ols slope", o["slope"], 2.0)
check("ols intercept", o["intercept"], 0.0)
check("ols r2", o["r2"], 1.0)

# ---- 13. 异常点 ----
# 平稳序列中间插一个大跳点，应被识别
flat = [("2024-%02d-%02d" % (1 + i // 28, 1 + i % 28), 1.0 + (0.0001 * (i % 3))) for i in range(100)]
flat[80] = (flat[80][0], 1.50)
rr = R.build_ratio(flat, [(d, 1.0) for d, _ in flat])
outs = R.detect_outliers(rr, window=60, z_thresh=2.5)
flagged = [o for o in outs if o[3]]
check("outlier detected at spike", any(abs(o[1] - 1.50) < 1e-9 for o in flagged), True)
check("outlier count small", len(flagged) <= 2, True)
check("early rows unflagged", outs[0][3], False)

# ---- 14. 最大回撤 ----
# 注意：B 侧必须每天都有值，否则整行比价为 None
dd_rows = R.build_ratio([("d1", 1.0), ("d2", 1.2), ("d3", 0.9)],
                        [("d1", 1.0), ("d2", 1.0), ("d3", 1.0)])
mdd = R.max_drawdown(dd_rows)
check("max_drawdown pct (-25% from 1.2)", mdd[0], (0.9 / 1.2 - 1) * 100)
check("max_drawdown peak date", mdd[1], "d2")
check("max_drawdown trough date", mdd[2], "d3")

# ---- 15. 变化指标 ----
cm = R.change_metrics(rows2, lookbacks=(1, 5))
check("change d1 = 1.20/1.19-1", cm["d1"], (1.20 / 1.19 - 1) * 100, 1e-12)
check("change d5 = 1.20/1.15-1", cm["d5"], (1.20 / 1.15 - 1) * 100, 1e-12)
check("change beyond sample -> None", R.change_metrics(rows2, lookbacks=(500,))["d500"], None)

# ---- 16. 日期偏移 ----
check("date_offset +1y", R.date_offset("2025-10-20", years=1), "2026-10-20")
check("date_offset -1y leap", R.date_offset("2024-02-29", years=-1), "2023-02-28")
check("date_offset +3y", R.date_offset("2023-10-23", years=3), "2026-10-23")
check("date_offset days", R.date_offset("2024-01-01", days=31), "2024-02-01")

# ---- 17. 描述性 ----
check("excess_vs_median", R.excess_vs_median(110, [100, 100, 100]), 10.0)
check("excess vs median None", R.excess_vs_median(None, [1]), None)

print("\n".join(MSGS))
print("-" * 74)
print("TOTAL: %d passed, %d failed" % (PASS, FAIL))
print("-" * 74)
sys.exit(1 if FAIL else 0)
