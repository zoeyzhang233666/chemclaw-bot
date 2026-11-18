# -*- coding: utf-8 -*-
"""selftest.py —— 引擎自检：把"方法论纪律"变成可执行的断言。

这些用例不是为了测代码覆盖率，而是为了确保：
  * 缺失数据永远不会被悄悄当成 0 或"没影响"；
  * 方向相反的指标不会被判成"支持"；
  * 换月造成的名义价不会被当成交割价使用；
  * 同一合约口径与主连口径的差异被显式暴露，而不是被抹平。

用法：python selftest.py
"""
from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import align_series as A  # noqa: E402
import detect_anomalies as D  # noqa: E402
import grade_evidence as G  # noqa: E402
import local_attribution as L  # noqa: E402

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def approx(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol


# ---------------------------------------------------------------- 用例


@case
def t_window_change_uses_real_dates():
    """窗口首末值必须取"≥start 的第一个"和"≤end 的最后一个"，并记录实际日期。"""
    s = {'2026-01-02': 100.0, '2026-01-05': 110.0, '2026-01-09': 121.0, '2026-01-30': 200.0}
    r = C.window_change(s, '2026-01-03', '2026-01-15')
    assert r['ok']
    assert r['start_date'] == '2026-01-05' and r['end_date'] == '2026-01-09'
    assert approx(r['pct_change'], 10.0)
    return '窗口端点按真实观测日对齐（%s→%s）' % (r['start_date'], r['end_date'])


@case
def t_missing_is_never_zero():
    """区间内没有观测 → 必须返回 ok=False，不得插值或当 0。"""
    s = {'2026-01-02': 100.0, '2026-01-30': 200.0}
    r = C.window_change(s, '2026-02-01', '2026-02-28')
    assert not r['ok'], '无观测时不应给出数值'
    w = A.window_stats([('2026-01-02', 1.0)], '2026-02-01', '2026-02-28')
    assert not w['ok']
    return '无观测一律 ND，不插值'


@case
def t_pctile_and_z():
    vals = list(range(1, 101))
    assert approx(C.percentile(vals, 50), 50.5, 1e-6) or approx(C.percentile(vals, 50), 50.0, 1.0)
    assert C.pctile_rank(vals, 101) == 100.0
    assert C.pctile_rank(vals, 0) == 0.0
    z = C.zscore([1, 2, 3, 4, 5], 5)
    assert z > 1.2
    return '分位与 z 值计算正确'


@case
def t_grade_rules():
    """四级分级必须严格按规则，方向相反一律不得升到 E1/E2。"""
    assert G.LEVEL_W == {'E1': 4.0, 'E2': 3.0, 'E3': 1.5, 'E4': 0.0}
    # 无数据 → E4
    lv, _ = C.grade_driver({'has_data': False}, 'up')
    assert lv == 'E4'
    # 显著 + 同向 → E1
    lv, _ = C.grade_driver({'has_data': True, 'z': 1.8, 'same_sign': True}, 'up')
    assert lv == 'E1'
    # 方向相反 → E4（即使显著）
    lv, _ = C.grade_driver({'has_data': True, 'z': -2.4, 'same_sign': False}, 'up')
    assert lv == 'E4', '方向相反的指标不得判为支持，实际 %s' % lv
    # 有事件但无数据 → E3
    lv, _ = C.grade_driver({'has_data': True, 'z': 0.2, 'same_sign': True, 'event_hooked': True}, 'up')
    assert lv in ('E2', 'E3')
    return '分级规则：反证不会升级为支持'


@case
def t_rsi_bounds():
    up = list(range(1, 40))
    v = C.rsi(up, 14)
    assert v is not None and 99.0 <= v <= 100.0
    return 'RSI 边界正确（单边上涨=100）'


@case
def t_anomaly_requires_volume():
    """只有价格跳、没有放量的一天，不得被计为异动（spike）。"""
    bars = []
    base = 100.0
    for i in range(80):
        bars.append({'date': '2026-01-%02d' % (i % 28 + 1) if i < 28 else '2026-02-%02d' % (i - 27),
                     'close': base + (i % 3) * 0.5, 'volume': 1000, 'high': None, 'low': None})
    bars[-1]['close'] = bars[-2]['close'] * 1.12     # 巨幅跳涨
    bars[-1]['volume'] = 1000                          # 但没有放量
    res = D.detect(bars, z_thr=2.0, vol_z_thr=1.5, cluster_gap=3, phase_thr=5)
    last = res['bars'][-1]
    assert last['extreme'], '应识别为极端波动'
    assert not last['spike'], '未放量不应判为异动'
    assert last['price_only'], '应被明确标记为"只有价格异常、没有放量"'
    return '异动判定要求双条件；无放量的极端日被单独标记为 price_only'


@case
def t_phase_segmentation_edges():
    """阶段切分必须覆盖整个区间、首尾相接。"""
    bars = []
    px = 100.0
    import math
    for i in range(120):
        px *= (1 + 0.01 * math.sin(i / 4.0) + 0.002)
        bars.append({'date': '2026-%02d-%02d' % (i // 28 + 1, i % 28 + 1), 'close': round(px, 2),
                     'volume': 1000, 'high': None, 'low': None})
    ph = D.build_phases(bars, 3, start=bars[0]['date'], end=bars[-1]['date'])
    assert ph, '应至少切出一段'
    assert ph[0]['start_date'] == bars[0]['date']
    assert ph[-1]['end_date'] == bars[-1]['date']
    for a, b in zip(ph, ph[1:]):
        assert a['end_date'] == b['start_date'], '阶段必须首尾相接'
    return '阶段覆盖完整且首尾相接（%d 段）' % len(ph)


@case
def t_contract_month_sort():
    codes = ['MA2701', 'MA2611', 'MA2612', 'MA2703']
    s = sorted(codes, key=A._contract_month)
    assert s == ['MA2611', 'MA2612', 'MA2701', 'MA2703'], s
    return '合约按到期月排序正确'


@case
def t_basis_uses_live_curve_only():
    """期现结构只能用当日有效合约，空壳报价不得参与月差。"""
    curve = {
        'MA2611': {'2026-10-19': {'close': 3335, 'oi': 180102}},
        'MA2612': {'2026-10-19': {'close': 3216, 'oi': 276402}},
        'MA2610': {'2026-10-19': {'close': 3380, 'oi': 10}},      # 已到期、残量
    }
    m = A.struct_metrics(curve, {'2026-10-19': 3966.67}, '2026-10-19')
    assert m['front_contract'] == 'MA2612', m['front_contract']
    assert approx(m['basis'], 3966.67 - 3216, 1e-6)
    # MA2612 是主力（276,402 > 180,102），它后面没有更远月的有效合约，
    # 因此不应计算月差 —— 强行拿 MA2611 当"次主力"会得到方向相反的假月差。
    assert 'm1m2' not in m, '主力后面没有更远月合约时不得计算月差'
    assert m.get('next_contract') is None
    return '主力按持仓量选择，残量合约被排除，且不会编造方向相反的月差'


@case
def t_local_attribution_counter_evidence():
    """局部归因必须把"方向与价格相反"的因子标成反证，而不是解释。"""
    d = os.path.join(HERE, '..', 'examples', '01-methanol-huadong-2026Q3')
    cp = os.path.join(d, 'case.json')
    if not os.path.exists(cp):
        return 'SKIP（示例数据缺失）'
    case_obj = C.jload(cp)
    res = L.attribute(case_obj, d, '2026-09-28', '2026-10-19', 3)
    assert res.get('ok')
    assert res['direction'] == 'down', '该区间现货应为下跌'
    coal = [r for r in res['factors'] if '煤炭' in r['driver']]
    assert coal, '应有煤炭因子'
    assert all(r['level'] == 'E4' for r in coal), '煤价在下跌区间仍上涨，必须判为反证(E4)'
    return '下跌区间里，仍在上涨的煤价被正确判为反证'


@case
def t_evidence_every_driver_covered():
    """每个驱动都必须至少有一条证据条目（含"无数据"），不得整块消失。"""
    g = os.path.join(HERE, '..', 'examples', '01-methanol-huadong-2026Q3', 'build', 'graded.json')
    cp = os.path.join(HERE, '..', 'examples', '01-methanol-huadong-2026Q3', 'case.json')
    if not (os.path.exists(g) and os.path.exists(cp)):
        return 'SKIP（示例构建产物缺失）'
    case_obj = C.jload(cp)
    graded = C.jload(g)
    names = {it['factor'] for it in graded['items']}
    for drv in case_obj['drivers']:
        assert drv['name'] in names or drv.get('manual') is not None, '驱动未覆盖：%s' % drv['name']
    return '八个驱动全部有证据条目（含 E4）'


@case
def t_fmt_none():
    assert C.fmt(None) == '—'
    assert C.fmt(1.234, 1) == '1.2'
    return '缺失值渲染为占位符而非 0'


def main():
    print('引擎自检（%d 项）' % len(CASES))
    bad = 0
    for fn in CASES:
        name = fn.__name__
        try:
            msg = fn()
            print('  PASS %-38s %s' % (name, msg or ''))
        except AssertionError as e:
            bad += 1
            print('  FAIL %-38s %s' % (name, e))
        except Exception as e:
            bad += 1
            print('  ERR  %-38s %s: %s' % (name, type(e).__name__, e))
    print('通过 %d / %d' % (len(CASES) - bad, len(CASES)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
