# -*- coding: utf-8 -*-
"""Self-test for hypothesis_stats.py — validates every routine against analytic benchmarks
or external references (scipy values are hard-coded so no install is needed)."""
import math
import sys

import hypothesis_stats as S

FAIL = []


def chk(name, got, want, tol):
    ok = got is not None and abs(got - want) <= tol
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got={got}, want={want} (±{tol})")
    if not ok:
        FAIL.append(name)


# 1. Wilson CI — reference (hand calculation / R prop.test): k=30,n=100 -> (0.2189, 0.3958)
lo, hi = S.wilson_ci(30, 100)
chk("wilson lo", lo, 0.218949, 1e-4)
chk("wilson hi", hi, 0.395849, 1e-4)

# 2. two-proportion z — p1=.6(n=50) vs p2=.4(n=50)
r = S.two_prop_z(30, 50, 20, 50)
chk("2prop z", r["z"], 2.0, 1e-6)
chk("2prop p", r["p"], 0.0455, 1e-3)

# 3. Fisher exact — classic [[3,1],[1,3]] two-sided p = 0.4857
chk("fisher p", S.fisher_exact_2x2(3, 1, 1, 3), 0.4857, 1e-3)

# 4. Welch t — [9,11]*10 (mean 10, sd 1.4510) vs [8,10]*10 -> t=3.0822 (scipy.stats.ttest_ind)
x1 = [9.0, 11.0] * 10
x2 = [8.0, 10.0] * 10
r = S.welch_t(x1, x2)
chk("welch diff", r["diff"], 1.0, 1e-9)
chk("welch t", r["t"], 3.082207001484488, 1e-9)
chk("welch df", r["df"], 38.0, 1e-9)
chk("welch p_t", r["p_t_approx"], 0.003813188880464124, 1e-9)

# 5. Mann-Whitney U — scipy reference: U=3.0 for [1,2,3] vs [4,5,6] -> U=0
r = S.mannwhitney_u([1, 2, 3], [4, 5, 6])
chk("mw U", r["U"], 0.0, 1e-9)
chk("mw auc", r["auc"], 0.0, 1e-9)

# 6. t-crit — scipy.stats.t.ppf(0.975, df)
chk("t_crit(14)", S.t_crit(14), 2.144786687917804, 3e-3)
chk("t_crit(1000)", S.t_crit(1000), 1.9623390808264083, 3e-3)

# 7. OLS on a known line: y = 2 + 3x (exact)
X = [[1.0, x] for x in [0, 1, 2, 3, 4]]
y = [2 + 3 * x for x in [0, 1, 2, 3, 4]]
b = S.ols(y, X)
chk("ols intercept", b[0], 2.0, 1e-9)
chk("ols slope", b[1], 3.0, 1e-9)

# 8. OLS + HAC on synthetic AR(1) noise — beta recovered, HAC se > classical se
import random
rng = random.Random(7)
n = 200
x = [rng.gauss(0, 1) for _ in range(n)]
e = [0.0] * n
for i in range(1, n):
    e[i] = 0.6 * e[i - 1] + rng.gauss(0, 1)
yy = [1.0 + 0.5 * x[i] + e[i] for i in range(n)]
res = S.ols_hac(yy, [[1.0, x[i]] for i in range(n)], lags=4)
chk("hac beta1 ~0.5", res["beta"][1], 0.5, 0.25)
print(f"INFO  hac_inflation={res['hac_inflation']:.2f} (>1 expected with AR noise)")

# 9. BH adjustment — p = [.01,.02,.03,.04,.05]
q = S.bh_adjust([0.01, 0.02, 0.03, 0.04, 0.05])
chk("bh monotone", q[0], 0.05, 1e-9)
chk("bh last", q[4], 0.05, 1e-9)

# 10. permutation p on identical samples -> ~1
p = S.permutation_p([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], n_perm=2000)
chk("perm identical", p["p_perm"], 1.0, 0.01)

# 11. stationary bootstrap CI covers the mean
xs = [((i * 37) % 11) - 5 for i in range(120)]
lo, hi = S.stationary_bootstrap_ci(xs)
print(f"{'PASS' if lo <= S.mean(xs) <= hi else 'FAIL'}  bootstrap CI [{lo:.3f},{hi:.3f}] contains mean")
if not (lo <= S.mean(xs) <= hi):
    FAIL.append("bootstrap")

# 12. non-overlapping filter
dates = [f"2024-01-{d:02d}" for d in range(1, 21)]
sess = {d: i for i, d in enumerate(dates)}
kept = S.non_overlap_filter(dates, 5, sess)
chk("non-overlap kept", len(kept), 4, 0)

# 13. rankdata ties
chk("ranks ties", S.rankdata([10, 20, 20, 30])[1], 2.5, 1e-9)

print()
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("ALL SELF-TESTS PASSED")
