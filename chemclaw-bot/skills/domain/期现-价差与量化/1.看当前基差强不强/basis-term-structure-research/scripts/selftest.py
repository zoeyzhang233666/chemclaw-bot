#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""已知答案自测（回归护栏）。

覆盖：基差基本式、归因符号与恒等式、换月跳空、前复权方向、样本不足判定、
覆盖率判定、以及"跨换月不可直接相减"的保护逻辑。

跑法：python scripts/selftest.py
任何一条失败都会非零退出。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import basislib as B                                             # noqa: E402

CHECKS = []


def check(name, cond, detail=''):
    CHECKS.append((name, bool(cond), detail))
    return bool(cond)


def test_basis_core():
    check('基差 = 现货 - 期货（3980-3157=823）', B.basis(3980, 3157) == 823)
    check('基差率 = 823/3980 = 20.68%', B.basis_rate(3980, 3157) == 20.68)
    check('负基差（现货贴水）', B.basis(2800, 3157) == -357)
    check('现货缺失返回 None，不填补', B.basis(None, 3157) is None)
    check('期货缺失返回 None，不填补', B.basis(3980, None) is None)
    check('区间中点 (3960+4000)/2=3980', B.spot_mid(3960, 4000) == 3980)
    check('中点任一端缺失返回 None', B.spot_mid(3960, None) is None)


def test_stats():
    check('经验分位 [1,2,3,4] 中 3 => 75%', B.empirical_percentile([1, 2, 3, 4], 3) == 75.0)
    check('中位数（奇数）', B.median([3, 1, 2]) == 2)
    check('中位数（偶数）', B.median([1, 2, 3, 4]) == 2.5)
    check('样本标准差 n-1', abs(B.stdev([2, 4, 4, 4, 5, 5, 7, 9]) - 2.13809) < 1e-4)
    check('单样本标准差为 None', B.stdev([5]) is None)
    check('空样本均值为 None', B.mean([]) is None)


def test_decompose():
    # 现货 +45、期货 +215 -> 基差 -170
    d = B.decompose(3980, 3935, 3157, 2942)
    check('Δ基差 = Δ现货 - Δ期货 = 45-215 = -170', d['delta_basis'] == -170)
    check('期货上涨对基差是负贡献（-126.47%）', round(d['share_fut'], 2) == 126.47)
    check('现货上涨对基差是正贡献（-26.47%，因被期货压过）', round(d['share_spot'], 2) == -26.47)
    check('两项之和恒为 100%', abs(d['share_spot'] + d['share_fut'] - 100) < 1e-6)
    # 反例：现货 -895、期货 -181 -> 基差 -714
    d2 = B.decompose(3980, 4875, 3157, 3338)
    check('现货下跌主导 -> 现货贡献 > 100%', d2['delta_basis'] == -714 and d2['share_spot'] > 100)
    try:
        B.decompose(None, 1, 2, 3)
        check('缺失值归因应报错', False)
    except ValueError:
        check('缺失值归因应报错', True)
    d0 = B.decompose(100, 100, 200, 200)
    check('完全无变化时贡献度为 None', d0['share_spot'] is None)


def test_rolls():
    # 2026-09-10：MA2610 3411 -> MA2701 3043
    dates = ['2026-09-09', '2026-09-10']
    mains = {'2026-09-09': 'MA2610', '2026-09-10': 'MA2701'}
    closes = {'2026-09-09': {'MA2610': 3411.0, 'MA2701': 3310.0},
              '2026-09-10': {'MA2610': 3430.0, 'MA2701': 3043.0}}
    g = B.roll_events(dates, mains, closes)
    check('识别出 1 次换月', len(g) == 1)
    check('跳空 gap = 3043 - 3430 = -387（切换日新旧主力之差）', g[0]['gap'] == -387.0, str(g[0]))
    check('同日价差 shift = 3310 - 3411 = -101（前一日新旧之差）', g[0]['shift'] == -101.0, str(g[0]))
    check('换月不落在同合约上', g[0]['from'] == 'MA2610' and g[0]['to'] == 'MA2701')

    seq = [{'date': '2026-09-09', 'close': 3411.0}, {'date': '2026-09-10', 'close': 3043.0}]
    adj = B.forward_adjust(seq, g)
    check('前复权：最新段等于原始价格', adj[-1]['adj_close'] == 3043.0)
    check('前复权：历史段按同日价差平移 -101', adj[0]['adj_close'] == 3411.0 - 101.0)
    check('前复权：换月日不再含跨合约跳空',
          abs((adj[1]['adj_close'] / adj[0]['adj_close'] - 1) - (3043.0 / 3310.0 - 1)) < 1e-9,
          '复权后换月日收益率应等于新合约(MA2701)当日真实收益率 3043/3310-1')
    # 未复权的"跳空"幅度的来源：旧主力 3411 -> 新主力 3043
    check('未复权直接拼接会伪造 -10.8% 跳空',
          abs((3043.0 / 3411.0 - 1) - -0.1078) < 1e-3)

    # 旧主力在切换日无报价 -> 跳空不可算，必须显式标记而不是猜
    g2 = B.roll_events(dates, mains, {'2026-09-09': {'MA2610': 3411.0},
                                      '2026-09-10': {'MA2701': 3043.0}})
    check('旧主力无报价时跳空为 None 并给出说明', g2[0]['gap'] is None and g2[0]['note'])

    # pick_main 取持仓量最大
    rows = [{'date': '2026-10-20', 'contract': 'MA2611', 'oi': 155303},
            {'date': '2026-10-20', 'contract': 'MA2701', 'oi': 860774},
            {'date': '2026-10-20', 'contract': 'MA0', 'oi': 9999999}]
    m = B.pick_main(rows)
    check('主力取持仓量最大且排除 MA0', m['2026-10-20']['contract'] == 'MA2701')


def test_sample_sufficiency():
    w = B.window_stats([1, 2, 3], 2)
    check('N=3 不足以给历史分位', w['usable_as_percentile'] is False)
    check('样本不足时给出原因', bool(w['reason']))
    w2 = B.window_stats(list(range(100)), 50)
    check('N=100 可给分位', w2['usable_as_percentile'] is True)
    check('分位值 51%', w2['pct'] == 51.0)
    w3 = B.window_stats([1, None, 3, None], 2)
    check('None 被剔除且不计入 N', w3['n'] == 2)

    cov = B.coverage_check(['2026-09-21', '2026-09-22'], '2025-10-21', '2026-10-20')
    check('覆盖不足被识别', cov['sufficient'] is False)
    check('覆盖率约 1%，量化给出', cov['ratio'] < 0.05, str(cov))


def test_splice_warning():
    dates = ['2026-09-09', '2026-09-10', '2026-09-11']
    mains = {'2026-09-09': 'MA2610', '2026-09-10': 'MA2701', '2026-09-11': 'MA2701'}
    closes = {'2026-09-09': {'MA2610': 3411.0},
              '2026-09-10': {'MA2610': 3430.0, 'MA2701': 3043.0},
              '2026-09-11': {'MA2701': 3016.0}}
    g = B.roll_events(dates, mains, closes)
    seq = [{'date': d, 'close': closes[d][mains[d]]} for d in dates if mains[d] in closes[d]]
    s = B.naive_splice_check(seq, g, {})
    check('拼接诊断给出绝对跳空合计', s['abs_gap_sum'] == 387.0)
    check('拼接诊断带警示文案', '换月' in s['warning'])


def test_cli_end_to_end():
    """跑一次完整 CLI，确认端到端数字与手算一致。"""
    root = os.path.dirname(HERE)
    example = os.path.join(root, 'examples', 'methanol-taichen-ma')
    spot = os.path.join(example, 'data', 'spot_taicang.csv')
    fut = os.path.join(example, 'data', 'futures_ma.csv')
    if not (os.path.exists(spot) and os.path.exists(fut)):
        check('CLI 端到端（示例数据缺失，跳过）', True)
        return
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, 'basis.json')
    code = subprocess.run([sys.executable, os.path.join(HERE, 'calc_basis.py'),
                           '--spot', spot, '--futures', fut, '--asof', '2026-10-20',
                           '--dates', '2026-10-09', '--windows', '1y', '--out', out],
                          capture_output=True, text=True, encoding='utf-8')
    if code.returncode != 0:
        check('CLI 退出码 0', False, (code.stderr or '')[-400:])
        return
    check('CLI 退出码 0', True)
    r = json.load(open(out, encoding='utf-8'))
    check('CLI 基差 823', r['basis_now'] == 823)
    check('CLI 主力 MA2701', r['main_contract'] == 'MA2701')
    check('CLI 近月 MA2611 基差 596', r['contracts']['MA2611']['basis'] == 596)
    check('CLI 真实配对 13 个', r['n_pairs'] == 13)
    check('CLI 分位不可用', r['windows']['1y']['usable_as_percentile'] is False)
    ch = r['changes']['2026-10-09']
    check('CLI 峰值以来 Δ基差 -714', ch['delta_basis'] == -714)
    check('CLI 峰值以来现货主导', ch['share_spot'] > 100)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for fn in (test_basis_core, test_stats, test_decompose, test_rolls,
               test_sample_sufficiency, test_splice_warning, test_cli_end_to_end):
        fn()
    bad = [c for c in CHECKS if not c[1]]
    for name, ok, detail in CHECKS:
        print(('  OK   ' if ok else '  FAIL ') + name + (('  <- ' + detail) if (not ok and detail) else ''))
    print('\n%d 项检查，%d 项通过，%d 项失败' % (len(CHECKS), len(CHECKS) - len(bad), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
