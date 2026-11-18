# -*- coding: utf-8 -*-
"""模板回归自检：用合成数据跑完整链路并断言已知答案。
    python build/selftest.py
全部通过时退出码为 0。
"""
import math
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import json  # noqa: E402
import stats_core as SC  # noqa: E402
import chain_graph as CG  # noqa: E402

FAILS = []


def check(name, cond, detail=''):
    if cond:
        print(f'  [PASS] {name}')
    else:
        print(f'  [FAIL] {name}  {detail}')
        FAILS.append(name)


# ---------------------------------------------------------------------------
# 1. 统计函数已知答案
# ---------------------------------------------------------------------------
print('1) 统计函数已知答案')
# t 分布双侧 p：t=2.228, df=10 → 0.05001
p = SC.t_two_sided_p(2.228, 10)
check('t 分布双侧 p（t=2.228, df=10）≈0.05', abs(p - 0.05001) < 1e-4, f'got {p}')
p2 = SC.t_two_sided_p(1.96, 1e6)
check('t 分布大样本 ≈0.05', abs(p2 - 0.05) < 5e-4, f'got {p2}')
check('t 分布双侧 p（t=0）≈1', abs(SC.t_two_sided_p(0, 10) - 1.0) < 1e-9)

# 相关系数 p：r=0.1946, n=100 → 0.0524
pv = SC.corr_pvalue(0.1946, 100)
check('相关系数 p（r=0.1946, n=100）≈0.0524', abs(pv - 0.0524) < 5e-4, f'got {pv}')

# Fisher z CI：r=0.5, n=100 → CI ≈ [0.336, 0.633]
lo, hi = SC.fisher_ci(0.5, 100)
check('Fisher z CI（r=0.5, n=100）≈[0.336,0.633]', abs(lo - 0.336) < 3e-3 and abs(hi - 0.633) < 3e-3,
      f'got {lo:.4f}~{hi:.4f}')

# 有效样本量：rho_x=rho_y=0 → n_eff = n；rho=0.5,0.5 → 0.6n
check('N_eff（ρx=ρy=0）== n', abs(SC.eff_sample(0.3, 0.0, 0.0, 100) - 100) < 1e-9)
check('N_eff（ρx=ρy=0.5）≈0.6n', abs(SC.eff_sample(0.3, .5, .5, 100) - 60) < 1e-6)

# BH-FDR 已知答案：p = [0.01,0.02,0.03,0.04,0.05] → q = [0.05,0.05,0.05,0.05,0.05]
qs = SC.bh_fdr([0.01, 0.02, 0.03, 0.04, 0.05])
check('BH-FDR 已知答案', all(abs(q - 0.05) < 1e-9 for q in qs), str(qs))

# 百分位
check('percentile_of 中位', abs(SC.percentile_of(0.5, [0.1, 0.5, 0.9]) - 50) < 1e-6)

# run_length_at_end
check('run_length_at_end', SC.run_length_at_end([0, 1, 1, 0, 1, 1, 1]) == 3)

# ---------------------------------------------------------------------------
# 2. 合成数据：已知相关性
# ---------------------------------------------------------------------------
print('2) 合成数据相关性还原')
random.seed(7)
n = 600
xa = [random.gauss(0, 0.01) for _ in range(n)]
yb = [0.8 * xa[i] + random.gauss(0, 0.01) for i in range(n)]
r = SC.pearson(xa, yb)
check('合成相关 ≈0.62（多元回归解析解 0.622）', abs(r - 0.622) < 0.02, f'got {r:.3f}')

# 完全脱钩：把后半段换成独立噪声
half = n // 2
mixed = yb[:half] + [random.gauss(0, 0.01) for _ in range(half)]
rc = SC.rolling_corr(xa, mixed, 100)
check('滚动相关在脱钩点后显著下降', rc[-1] < r - 0.2, f'roll_end={rc[-1]:.3f} vs full={r:.3f}')

# 置换检验：强相关 → p 很小；独立 → p 不小
pa = SC.permutation_null_corr(xa, yb, n_perm=300, seed=1)
check('置换检验：强相关 p 小', pa['p_perm'] < 0.05, str(pa))
ind = [random.gauss(0, 0.01) for _ in range(n)]
pb = SC.permutation_null_corr(xa, ind, n_perm=300, seed=1)
check('置换检验：独立序列 p 不小', pb['p_perm'] > 0.05, str(pb))

# ---------------------------------------------------------------------------
# 3. 合成价差：已知 z
# ---------------------------------------------------------------------------
print('3) 合成价差 z 值还原')
m = 400
A = [1000.0]
B = [1000.0]
for i in range(1, m):
    A.append(A[-1] * (1 + random.gauss(0, 0.005)))
    B.append(B[-1] * (1 + random.gauss(0, 0.005)))
z = SC.rolling_z_long([math.log(b / a) for a, b in zip(A, B)], 60)
check('合成价差 z 末值在合理范围', z[-1] is not None and abs(z[-1]) < 4, str(z[-1]))

# ---------------------------------------------------------------------------
# 4. 配对规则自洽
# ---------------------------------------------------------------------------
print('4) 配对规则自洽性')
pairs = CG.build_pairs()
check('配对数量 > 0', len(pairs) > 0, str(len(pairs)))
codes = {u['code'] for u in CG.UNIVERSE}
bad = [p for p in pairs if p['a'] not in codes or p['b'] not in codes]
check('所有配对品种都在品种池内', not bad, str(bad[:2]))
bad2 = [p for p in pairs if p['rtype'] not in CG.RTYPE_INFO]
check('所有关系类型都有定义', not bad2, str(bad2[:2]))
bad3 = [p for p in pairs if not p.get('source_ids')]
check('每条关系都有来源', not bad3, str(bad3[:2]))
weak_primary = [p for p in pairs if p['strength'] == 'weak' and p['rtype'] == 'upstream_downstream']
check('不存在标为 weak 的上下游关系（自相矛盾）', not weak_primary, str(weak_primary[:2]))
dup = set()
d2 = []
for p in pairs:
    k = tuple(sorted([p['a'], p['b']]))
    if k in dup:
        d2.append(k)
    dup.add(k)
check('无重复配对', not d2, str(d2[:2]))

# PP0/L0 与 PX0/TA0 必须存在（用户明确的关注点）
keys = {tuple(sorted([p['a'], p['b']])) for p in pairs}
check('PP0/L0 在配对表中', ('L0', 'PP0') in keys)
check('PX0/TA0 在配对表中', ('PX0', 'TA0') in keys)

print()
if FAILS:
    print(f'❌ {len(FAILS)} 项失败: {FAILS}')
    sys.exit(1)
print('✅ 全部自检通过')
