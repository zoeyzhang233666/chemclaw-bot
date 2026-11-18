#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单元测试：公式、单位换算、化学计量、引擎恒等式。

运行：python -m pytest tests -q   或   python tests/test_engine.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import cost_engine          # noqa: E402
import units                # noqa: E402
import stoichiometry as sto  # noqa: E402


# ---------------------------------------------------------------- 单位换算
def test_price_unit_and_tax():
    v = lambda *a, **k: units.price_to_cny_per_t(*a, **k)['value']
    assert v(9700, 'CNY/t') == 9700.0
    # 不含税 -> 含税
    assert abs(v(9700, 'CNY/t', tax_included=False, target_tax_included=True) - 9700 * 1.13) < 1e-6
    # 含税 -> 不含税
    assert abs(v(9700, 'CNY/t', tax_included=True, target_tax_included=False) - 9700 / 1.13) < 1e-6
    # 元/kg -> 元/t
    assert v(9.7, 'CNY/kg') == 9700.0
    # 默认税率必须有提示（不能悄悄套 13%）
    r = units.price_to_cny_per_t(100, 'CNY/t', tax_included=False, target_tax_included=True)
    assert r['notes'], '税率默认值必须留痕'


def test_dosage_unit():
    # kg/t -> t/t：383 kg/t = 0.383 t/t
    assert abs(units.dosage_to_t_per_t(383, 'kg/t') - 0.383) < 1e-12
    assert abs(units.dosage_to_t_per_t(0.383, 't/t') - 0.383) < 1e-12
    # g/t -> t/t：383000 g/t = 0.383 t/t
    assert abs(units.dosage_to_t_per_t(383000, 'g/t') - 0.383) < 1e-6
    # kg/kg 与 t/t 数值等价
    assert abs(units.dosage_to_t_per_t(0.5, 'kg/kg') - 0.5) < 1e-12
    assert units.mass_factor('kg') == 1.0


# ---------------------------------------------------------------- 化学计量
def test_molar_mass():
    assert abs(sto.molar_mass('C8H4O3') - 148.117) < 0.01        # 苯酐
    assert abs(sto.molar_mass('C8H18O') - 130.231) < 0.01        # 异辛醇
    assert abs(sto.molar_mass('C24H38O4') - 390.564) < 0.01      # DOP
    assert abs(sto.molar_mass('Na2CO3') - 105.988) < 0.01        # 纯碱


def test_reaction_balance():
    bal = sto.mass_balance('C8H4O3 + 2 C8H18O -> C24H38O4 + H2O')
    assert bal['ok'], bal
    assert abs(bal['lhs_mass'] - bal['rhs_mass']) < 1e-6


def test_theoretical_dosage():
    d = sto.theoretical_dosage('C8H4O3 + 2 C8H18O -> C24H38O4 + H2O', 'C24H38O4', 'C8H4O3')
    assert abs(d - 0.3792) < 0.001, d
    d2 = sto.theoretical_dosage('C8H4O3 + 2 C8H18O -> C24H38O4 + H2O', 'C24H38O4', 'C8H18O')
    assert abs(d2 - 0.6669) < 0.001, d2


# ---------------------------------------------------------------- 引擎
def _mini():
    return {
        'meta': {'product': 'X', 'as_of': '2026-10-20', 'target_tax_basis': 'tax_included'},
        'materials': [
            {'id': 'a', 'name': 'A', 'role': 'main', 'spec': 's', 'region': 'r', 'delivery': 'd',
             'tax_included': True,
             'dosage': {'value': 1.0, 'unit': 't/t', 'source': 'user', 'scope': 'p'},
             'price': {'value': 100.0, 'unit': 'CNY/t', 'tax_included': True}},
            {'id': 'b', 'name': 'B', 'role': 'main', 'spec': 's', 'region': 'r', 'delivery': 'd',
             'tax_included': True,
             'dosage': {'value': 2.0, 'unit': 't/t', 'source': 'user', 'scope': 'p'},
             'price': {'value': 50.0, 'unit': 'CNY/t', 'tax_included': True}},
            {'id': 'c', 'name': 'C（缺价）', 'role': 'aux', 'spec': 's', 'region': 'r', 'delivery': 'd',
             'tax_included': True,
             'dosage': {'value': 0.5, 'unit': 'kg/t', 'source': 'user', 'scope': 'p'},
             'price': None},
        ],
        'not_included': [{'item': 'energy', 'reason': 'n/a'}],
    }


def test_total_and_share():
    R = cost_engine.compute(_mini())
    # 1.0*100 + 2.0*50 = 200；C 缺价不计入
    assert abs(R['total'] - 200.0) < 1e-9, R['total']
    sh = {m['id']: m['share'] for m in R['materials'] if m['cost'] is not None}
    assert abs(sh['a'] - 50.0) < 1e-9
    assert abs(sh['b'] - 50.0) < 1e-9
    assert R['coverage']['complete'] is False
    # 缺价原料必须显式标缺口，且成本为 None（不是 0）
    c = next(m for m in R['materials'] if m['id'] == 'c')
    assert c['cost'] is None


def test_sensitivity_linear():
    R = cost_engine.compute(_mini())
    total = R['total']
    for s in R['sensitivity']:
        for cell in s['cells']:
            assert abs(cell['cost_delta'] - s['cost'] * cell['ratio']) < 1e-9
    for ac in R['auto_combos']:
        assert abs(ac['delta'] - total * ac['ratio']) < 1e-9


def test_combo_matches_manual():
    D = _mini()
    D['combo_scenarios'] = [{'id': 'x', 'name': 'A+10%, B-10%', 'changes': {'a': 10, 'b': -10}}]
    R = cost_engine.compute(D)
    cb = R['combos'][0]
    manual = 1.0 * 100.0 * 1.10 + 2.0 * 50.0 * 0.90
    assert abs(cb['new_total'] - manual) < 1e-9, (cb['new_total'], manual)


def test_division_by_zero_safe():
    """幅度为 0 的情景，Δ 必须为 0，且不得抛异常。"""
    D = _mini()
    D['scenario_config'] = {'amplitude_series': [{'label': '0%', 'pct': 0}, {'label': '+10%', 'pct': 10}]}
    R = cost_engine.compute(D)
    z = [a for a in R['auto_combos'] if abs(a['ratio']) < 1e-12]
    assert z, [a['ratio'] for a in R['auto_combos']]
    assert abs(z[0]['delta']) < 1e-12


def test_examples_reproduce():
    """两个示例必须复现出稳定结果（防止改动引擎时悄悄改了数）。"""
    d1 = os.path.join(ROOT, 'examples', '01-dop-dehp', 'input.json')
    if os.path.exists(d1):
        R = cost_engine.compute(json.load(open(d1, encoding='utf-8')))
        assert abs(R['total'] - 10642.7846) < 0.01, R['total']
        pa = next(m for m in R['materials'] if m['id'] == 'pa')
        assert abs(pa['cost'] - 4066.1846) < 0.01
        eh = next(m for m in R['materials'] if m['id'] == 'eh')
        assert abs(eh['cost'] - 6576.60) < 0.01
    d2 = os.path.join(ROOT, 'examples', '02-soda-ash-solvay', 'input.json')
    if os.path.exists(d2):
        R = cost_engine.compute(json.load(open(d2, encoding='utf-8')))
        assert R['total'] > 0
        assert R['coverage']['complete'] is False   # 原盐/石灰石缺价，必须是部分覆盖


if __name__ == '__main__':
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    bad = 0
    for k, v in fns:
        try:
            v()
            print('  [OK]   ' + k)
        except AssertionError as e:
            bad += 1
            print('  [FAIL] %s  %s' % (k, e))
        except Exception as e:
            bad += 1
            print('  [ERR]  %s  %r' % (k, e))
    print('\n%d tests, %d failed' % (len(fns), bad))
    sys.exit(1 if bad else 0)
