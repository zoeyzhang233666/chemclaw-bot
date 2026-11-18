# -*- coding: utf-8 -*-
"""自测：用人工构造的“已知答案”数据校验月差内核。

运行：python scripts/selftest.py
输出：全部通过 exit 0；任一失败 exit 1。
"""
from __future__ import annotations

import datetime as dt
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import spreadlib as S  # noqa: E402

FAILS = []


def check(name, cond, detail=''):
    if cond:
        print(f'  [PASS] {name}')
    else:
        print(f'  [FAIL] {name} {detail}')
        FAILS.append(name)


def mk_series(code, rows):
    return S.ContractSeries(code, [{'date': S.parse_date(d), 'close': c, 'settle': c,
                                    'volume': 5000, 'oi': 5000} for d, c in rows])


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except Exception:  # noqa: BLE001
        return True


def main() -> int:
    print('1) 合约代码解析')
    check('SA2701 -> 2027-01', S.code_to_delivery('SA2701') == (2027, 1))
    check('SA2612 -> 2026-12', S.code_to_delivery('SA2612') == (2026, 12))
    check('非法月份被拒', _raises(lambda: S.code_to_delivery('SA2613')))
    check('非法格式被拒', _raises(lambda: S.code_to_delivery('SA26')))
    check('月份间隔 SA2612->SA2701 = 1', S.month_pair_gap('SA2612', 'SA2701') == 1)
    check('月份间隔 SA2612->SA2709 = 9', S.month_pair_gap('SA2612', 'SA2709') == 9)

    print('2) 月差口径：A - B 顺序固定')
    book = S.ContractBook('SA', {
        'SA2612': mk_series('SA2612', [('2026-10-19', 950), ('2026-10-20', 940)]),
        'SA2701': mk_series('SA2701', [('2026-10-19', 960), ('2026-10-20', 955)]),
    })
    sp = S.spread_series(book, 'SA2612', 'SA2701')['rows']
    check('SA2612-SA2701 = -10 / -15', [r['spread'] for r in sp] == [-10, -15],
          [r['spread'] for r in sp])
    sp2 = S.spread_series(book, 'SA2701', 'SA2612')['rows']
    check('交换顺序后符号相反', [r['spread'] for r in sp2] == [10, 15], [r['spread'] for r in sp2])

    print('3) 月差只在两腿同日都有报价时计算（不向前填充）')
    book3 = S.ContractBook('SA', {
        'SA2612': mk_series('SA2612', [('2026-10-19', 950)]),
        'SA2701': mk_series('SA2701', [('2026-10-20', 955)]),
    })
    check('无重叠交易日 -> 空序列', S.spread_series(book3, 'SA2612', 'SA2701')['rows'] == [])

    print('4) 分位数算法')
    vals = list(range(1, 11))  # 1..10
    check('中位数 = 5.5', abs(S._pct(vals, 50) - 5.5) < 1e-9)
    check('P25 = 3.25', abs(S._pct(vals, 25) - 3.25) < 1e-9)
    check('P90 = 9.1', abs(S._pct(vals, 90) - 9.1) < 1e-9)
    check('单值 P50 = 该值', S._pct([42], 50) == 42)
    check('分位：值=10 在 1..10 中为 100%', S.percentile_of(10, vals) == 100.0)
    check('分位：值=0 为 0%', S.percentile_of(0, vals) == 0.0)
    check('分位：值=5.5 为 50%', S.percentile_of(5.5, vals) == 50.0)

    print('5) 描述统计')
    st = S.spread_stats([], [-10, 0, 10])
    check('mean = 0', abs(st['mean']) < 1e-12)
    check('样本标准差 = 10', abs(st['std'] - 10) < 1e-9, st['std'])
    check('N=0 返回空', S.spread_stats([], [])['n'] == 0)

    print('6) 期限结构：最近月归零')
    ts = S.term_structure(book, dt.date(2026, 10, 20), min_oi=0)
    check('首行 TS = 0', ts[0]['ts'] == 0)
    check('SA2701 相对 SA2612 = +15', ts[1]['ts'] == 15, [r['ts'] for r in ts])
    check('全上行 -> contango',
          S.term_structure_shape([{'ts': 0}, {'ts': 15}, {'ts': 30}])['shape'].startswith('contango'))
    check('全下行 -> backwardation',
          S.term_structure_shape([{'ts': 0}, {'ts': -15}, {'ts': -30}])['shape'].startswith('backwardation'))

    print('7) 对数贡献分解（精确相加 = dlnSpread）')
    dec = S.decompose(book, 'SA2612', 'SA2701', dt.date(2026, 10, 19), dt.date(2026, 10, 20))
    dln = math.log(940 / 950) - math.log(955 / 960)
    check('dlnSpread 一致', abs(dec['dln'] - dln) < 1e-12, (dec['dln'], dln))
    check('近月+远月贡献 = dlnSpread',
          abs(dec['contrib_a_dln'] + dec['contrib_b_dln'] - dln) < 1e-12)
    check('d月差 = -5 元/吨', abs(dec['ds'] - (-5)) < 1e-9, dec['ds'])
    up = S.decompose(S.ContractBook('SA', {
        'SA2612': mk_series('SA2612', [('2026-10-19', 950), ('2026-10-20', 960)]),
        'SA2701': mk_series('SA2701', [('2026-10-19', 950), ('2026-10-20', 950)]),
    }), 'SA2612', 'SA2701', dt.date(2026, 10, 19), dt.date(2026, 10, 20))
    check('近月上涨贡献为正', up['contrib_a_dln'] > 0)
    check('缺报价时不硬算，返回 error',
          'error' in S.decompose(book3, 'SA2612', 'SA2701', dt.date(2026, 10, 19), dt.date(2026, 10, 20)))

    print('8) 可比样本：同月份间隔才算')
    check('间隔不同 = 不可比',
          S.month_pair_gap('SA2612', 'SA2701') != S.month_pair_gap('SA2612', 'SA2709'))

    print('9) 数据质量检查能抓到坏数据')
    bad = S.ContractBook('SA', {'SA2701': S.ContractSeries('SA2701', [
        {'date': S.parse_date('2026-10-19'), 'close': 0, 'settle': 0, 'volume': 1, 'oi': 1},
        {'date': S.parse_date('2026-10-20'), 'close': 900, 'settle': 900, 'volume': 1, 'oi': 1},
    ])})
    check('零价格序列 -> 至少 1 条问题', len(S.data_quality(bad)) >= 1)

    print('10) 交易日计数')
    n = S.trading_days_between(dt.date(2026, 10, 16), dt.date(2026, 10, 20))
    check('10-16 -> 10-20 = 2 个交易日', n == 2, n)

    print('\n11) 真实数据回归（若 data/raw 存在）')
    raw = os.path.join(os.path.dirname(HERE), 'data', 'raw')
    if os.path.isdir(raw) and any(f.startswith('SA') for f in os.listdir(raw)):
        bk = S.ContractBook.from_dir(raw, 'SA')
        if 'SA2612' in bk.series and 'SA2701' in bk.series:
            s2 = S.spread_series(bk, 'SA2612', 'SA2701', min_oi=1000)['rows']
            check('SA2612-SA2701 有历史样本', len(s2) > 50, len(s2))
            check('月差 = 价差（算术自洽）',
                  all(abs((r['a'] - r['b']) - r['spread']) < 1e-9 for r in s2[:50]))
            ll = S.historical_same_month_value(bk, 'SA2612', 'SA2701', bk.latest_trading_date())
            check('去年同日回看能取到样本或明确为空', isinstance(ll, dict))
    else:
        print('  [SKIP] 无 data/raw')

    print()
    if FAILS:
        print(f'FAILED {len(FAILS)}: {FAILS}')
        return 1
    print('ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
