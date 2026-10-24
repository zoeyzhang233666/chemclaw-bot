# -*- coding: utf-8 -*-
"""
selftest.py —— researchlib 已知答案自测（不联网、不依赖 numpy）

覆盖：
  1. Pearson 完全线性 r=1 / 完全反向 r=-1
  2. Spearman 对单调非线性变换不变
  3. t 分布查表值：t=2.228, df=10 → 双侧 p≈0.05
  4. Fisher z CI 对已知序列
  5. 有效样本量：白噪声 ρ≈0 → N_eff≈n；强自相关 → N_eff << n
  6. 滚动窗口样本不足 → None（不给数）
  7. 交叉相关：人工构造「Y = X 滞后 3 期」应识别出 lag=+3 峰值
  8. Granger：构造 x 领先 y 的序列，x→y 显著、y→x 不显著
  9. 分位数与 Excel PERCENTILE.INC 一致（已知小样本手算）
 10. 状态机：上游涨、下游跌 → diverge
"""
import math
import random
import sys

import researchlib as R

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  PASS ' if cond else '  FAIL ') + name + ('  ' + detail if detail else ''))


def test_basic():
    xs = [1, 2, 3, 4, 5]
    ys = [2, 4, 6, 8, 10]
    check('Pearson 完全正相关 = 1', abs(R.pearson(xs, ys) - 1.0) < 1e-12)
    check('Pearson 完全负相关 = -1', abs(R.pearson(xs, ys[::-1]) + 1.0) < 1e-12)
    y2 = [x ** 3 for x in xs]
    check('Spearman 对单调变换不变 = 1', abs(R.spearman(xs, y2) - 1.0) < 1e-12)


def test_tdist():
    p = R.t_two_sided_p(2.228, 10)
    check('t=2.228 df=10 双侧 p≈0.05', abs(p - 0.05) < 0.0015, f'p={p:.5f}')
    p2 = R.t_two_sided_p(1.96, 100000)
    check('t=1.96 df≈∞ 双侧 p≈0.05', abs(p2 - 0.05) < 0.001, f'p={p2:.5f}')
    q = R.t_ppf(0.975, 10)
    check('t_ppf(0.975,10)≈2.228', abs(q - 2.228) < 0.005, f'q={q:.4f}')


def test_fisher():
    r, n = 0.5, 100
    lo, hi = R.fisher_ci(r, n)
    # 手算：z=0.5493, se=1/sqrt(97)=0.10153, ±1.96se → [-0.0077, 0.8474]
    exp_lo = math.tanh(0.5 * math.log(3) - 1.959963984540054 / math.sqrt(97))
    exp_hi = math.tanh(0.5 * math.log(3) + 1.959963984540054 / math.sqrt(97))
    check('Fisher CI 与手算一致', abs(lo - exp_lo) < 1e-9 and abs(hi - exp_hi) < 1e-9, f'[{lo:.4f},{hi:.4f}]')


def test_neff():
    random.seed(7)
    xs = [random.gauss(0, 1) for _ in range(500)]
    ys = [random.gauss(0, 1) for _ in range(500)]
    ne = R.n_eff(500, R.autocorr(xs), R.autocorr(ys))
    check('白噪声 N_eff ≈ n', abs(ne - 500) < 60, f'N_eff={ne:.1f}')
    # 强自相关 AR(1) 0.9
    a = [0.0]
    for _ in range(800):
        a.append(0.9 * a[-1] + random.gauss(0, 1))
    b = [0.0]
    for _ in range(800):
        b.append(0.9 * b[-1] + random.gauss(0, 1))
    ne2 = R.n_eff(800, R.autocorr(a), R.autocorr(b))
    check('AR(0.9) N_eff << n', ne2 < 200, f'N_eff={ne2:.1f}')


def test_rolling():
    xs = list(range(50))
    ys = [math.sin(x) for x in xs]
    res = R.rolling_corr_series(xs, ys, window=20)
    check('滚动窗口前段返回 None', all(v[1] is None for v in res[:19]))
    check('滚动窗口满窗后有值', res[19][1] is not None)
    res2 = R.rolling_corr_series(xs, ys, window=20, min_obs=25)
    check('min_obs 大于窗口 → 全部 None', all(v[1] is None for v in res2))


def test_crosscorr():
    random.seed(11)
    x = [random.gauss(0, 1) for _ in range(400)]
    y = [None] * 400
    for t in range(400):
        y[t] = (x[t - 3] if t >= 3 else random.gauss(0, 1)) + random.gauss(0, 0.3)
    cc = R.cross_correlation(x, y, 10)
    best = max([c for c in cc if c['r'] is not None], key=lambda c: c['r'])
    check('交叉相关识别 lag=+3 峰值', best['lag'] == 3, f"best lag={best['lag']} r={best['r']}")


def test_granger():
    random.seed(23)
    n = 600
    x = [random.gauss(0, 1) for _ in range(n)]
    y = [0.0] * n
    for t in range(n):
        y[t] = 0.7 * (y[t - 1] if t else 0) + 0.9 * (x[t - 2] if t >= 2 else 0) + random.gauss(0, 0.5)
    g1 = R.granger_test(y, x, p=2)
    g2 = R.granger_test(x, y, p=2)
    check('Granger x→y 显著', g1.get('p', 1) < 0.01, f"p={g1.get('p')}")
    check('Granger y→x 不显著', g2.get('p', 0) > 0.05, f"p={g2.get('p')}")


def test_quantile():
    xs = sorted([1, 2, 3, 4])
    # Excel PERCENTILE.INC(array,0.25) = 1.75 ; 0.5 = 2.5 ; 0.9 = 3.7
    check('分位数 q=0.25 → 1.75', abs(R.quantile(xs, 0.25) - 1.75) < 1e-12)
    check('分位数 q=0.9 → 3.7', abs(R.quantile(xs, 0.9) - 3.7) < 1e-12)
    check('历史分位', R.pct_rank([1, 2, 3, 4], 2.5) == 50.0)


def test_states():
    px = [100] * 20 + [100, 110, 120, 130, 140]
    pta = [7000] * 20 + [7000, 6900, 6800, 6700, 6600]
    st = R.transmission_states(px, pta, window=20, px_thr=0.03)
    check('上游涨下游跌 → diverge', st[-1] == 'diverge', f'state={st[-1]}')
    runs = R.find_diverge_runs(st, [str(i) for i in range(len(st))], min_len=1)
    check('背离段可被切出', len(runs) >= 1)


def test_hac():
    random.seed(5)
    n = 300
    x = [random.gauss(0, 1) for _ in range(n)]
    y = [2.0 * xi + random.gauss(0, 0.2) for xi in x]
    h = R.newey_west_ols(x, y, lags=5)
    check('OLS 斜率 ≈ 2', abs(h['slope'] - 2.0) < 0.1, f"slope={h['slope']}")


def main():
    print('researchlib selftest')
    for fn in (test_basic, test_tdist, test_fisher, test_neff, test_rolling,
               test_crosscorr, test_granger, test_quantile, test_states, test_hac):
        print('-', fn.__name__)
        fn()
    print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
