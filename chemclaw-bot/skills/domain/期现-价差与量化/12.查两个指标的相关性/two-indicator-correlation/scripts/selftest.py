# -*- coding: utf-8 -*-
"""自测：用已知答案的数据验证 corrlib / analyze 的关键统计量（不依赖第三方库）。"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corrlib as C


def approx(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol


def main():
    ok = True

    def check(name, cond, got=None, want=None):
        nonlocal ok
        if cond:
            print(f'  PASS  {name}')
        else:
            ok = False
            print(f'  FAIL  {name}  got={got} want={want}')

    # 1. Pearson：完美线性
    x = [1, 2, 3, 4, 5]
    y = [2, 4, 6, 8, 10]
    check('pearson 完全正相关=1', approx(C.pearson(x, y), 1.0), C.pearson(x, y), 1.0)
    check('pearson 完全负相关=-1', approx(C.pearson(x, [-v for v in y]), -1.0))
    # 2. 已知 r 的数据（r = 0.9 附近）
    xs = [1, 2, 3, 4, 5, 6, 7, 8]
    ys = [1, 2, 1.8, 3.5, 4.0, 4.2, 6.1, 6.3]
    r = C.pearson(xs, ys)
    check('pearson 已知样本 r>0.9', r > 0.9, round(r, 4), '>0.9')
    check('spearman 与 pearson 同号', (C.spearman(xs, ys) > 0) == (r > 0))
    # 3. 排序秩（含并列）
    check('rank 并列取平均', C.rank([10, 20, 20, 30]) == [1, 2.5, 2.5, 4], C.rank([10, 20, 20, 30]), [1, 2.5, 2.5, 4])
    # 4. t 分布 p 值（查表值：t=2.228, df=10 → p≈0.05）
    p = C.t_pvalue(2.228, 10)
    check('t_pvalue(2.228,10)≈0.05', approx(p, 0.05, 2e-3), round(p, 5), 0.05)
    p2 = C.t_pvalue(1.0, 1000)
    check('t_pvalue(1.0,1000)≈0.317', approx(p2, 0.3173, 2e-3), round(p2, 5), 0.3173)
    # 5. Fisher z CI 合理
    st = C.corr_stats(xs, ys)
    check('CI 包含 r 且下<上', st['ci_lo'] < st['r'] < st['ci_hi'], (round(st['ci_lo'], 3), round(st['ci_hi'], 3)))
    # 6. 交替符号 → 强负自相关
    alt = [1, -1, 1, -1, 1, -1, 1, -1]
    check('autocorr 交替序列为负', C.autocorr(alt, 1) < -0.5, round(C.autocorr(alt, 1), 3))
    # 7. 差分与 pct_change
    check('diff', C.diff([1, 3, 6]) == [2, 3], C.diff([1, 3, 6]))
    check('pct_change', [round(v, 4) for v in C.pct_change([100, 110, 99])] == [10.0, -10.0])
    # 8. 变换保留缺失，不插补
    tf = C.transform([1, None, 3], 'change')
    check('change 遇缺失不填补', tf == [None, None, None], tf)
    # 9. 对齐只保留双方都有值的点
    ax, ay, ad = C.align([1, None, 3], [None, 2, 3], ['d1', 'd2', 'd3'])
    check('align 仅保留配对', (ax, ay, ad) == ([3], [3], ['d3']), (ax, ay, ad))
    # 10. 滚动窗口不足时不计算
    rw = C.rolling_corr([1, 2, 3, None, None, None, None], [1, 2, 3, 4, 5, 6, 7], 5, min_pairs=5)
    check('滚动窗口有效样本不足返回 None', rw[-1] is None, rw[-1])
    # 11. 去趋势：纯趋势序列去趋势后相关≈0
    t = list(range(40))
    a = [0.5 * i + (1 if i % 2 else -1) for i in t]
    b = [0.3 * i + (-1 if i % 2 else 1) for i in t]
    raw = C.pearson(a, b)
    dt = C.pearson(C.detrend(t, a), C.detrend(t, b))
    check('去趋势后伪相关消失', raw > 0.85 and dt < -0.5, (round(raw, 3), round(dt, 3)), '>0.85 / <-0.5')
    # 12. partial_corr 去除共同因素
    import random
    rnd = random.Random(7)
    z = [rnd.gauss(0, 1) for _ in range(200)]
    px = [2 * zi + rnd.gauss(0, 0.3) for zi in z]
    py = [2 * zi + rnd.gauss(0, 0.3) for zi in z]
    check('偏相关去除共同因素', C.pearson(px, py) > 0.9 and abs(C.partial_corr(px, py, z)) < 0.3,
          (round(C.pearson(px, py), 3), round(C.partial_corr(px, py, z), 3)))
    # 13. 有效样本量修正方向正确
    neff, r1x, r1y = C.effective_n([1, 2, 3, 4, 5, 6, 7, 8], [2, 4, 6, 8, 10, 12, 14, 16])
    check('n_eff <= n', neff <= 8, round(neff, 2))
    # 14. lag_corr 方向：y 是 x 的滞后复制 → lag=1 时 r 最大
    xb = [math.sin(i / 3) for i in range(60)]
    yb = [0] + xb[:-1]
    check('lag_corr 识别滞后结构', C.lag_corr(xb, yb, 1) > C.lag_corr(xb, yb, 0),
          (round(C.lag_corr(xb, yb, 1), 3), round(C.lag_corr(xb, yb, 0), 3)))
    # 15. linreg 已知斜率
    fit = C.linreg([1, 2, 3, 4], [3, 5, 7, 9])
    check('linreg 斜率=2 截距=1', approx(fit['slope'], 2, 1e-9) and approx(fit['intercept'], 1, 1e-9),
          (fit['slope'], fit['intercept']))
    # 16. HAC 标准误为正且不爆炸
    se = C.hac_se_corr([math.sin(i / 4.0) for i in range(120)], [math.cos(i / 5.0) for i in range(120)], 6)
    check('HAC 标准误在 (0,1) 区间', se is not None and 0 < se < 1, round(se, 4) if se else None)

    print('\n结果：', '全部通过' if ok else '存在失败项')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
