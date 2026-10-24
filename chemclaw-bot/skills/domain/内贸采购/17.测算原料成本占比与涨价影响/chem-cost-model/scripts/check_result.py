#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结果自洽性校验：不依赖 Excel/浏览器，纯逻辑对账。

检查 7 条恒等式（见 references/formulas.md §7）：
  1. Σ c_i == C
  2. 全部计价时 Σ w_i == 100%
  3. Δc_i(r=0) == 0
  4. 全同步 ΔC% == r（线性恒等）
  5. 组合情景 C' == Σ q_i p_i (1+r_i)
  6. 历史末行成本 ≈ 当期成本（同价时）
  7. 贡献分解 Σ Δc_i == ΔC_T

用法：python check_result.py out/result.json
"""
import json
import sys

TOL = 0.01
FAIL = []


def ck(cond, msg):
    if cond:
        print('  [OK]   ' + msg)
    else:
        print('  [FAIL] ' + msg)
        FAIL.append(msg)


def main(path):
    R = json.load(open(path, encoding='utf-8'))
    mats = R['materials']
    comp = [m for m in mats if m.get('cost') is not None]
    total = R['total']

    print('== 1 单项成本求和 ==')
    s = sum(m['cost'] for m in comp)
    ck(abs(s - total) <= TOL, 'Σ单项 = %.4f vs 合计 %.4f' % (s, total))

    print('\n== 2 占比合计 ==')
    cov = R.get('coverage') or {}
    sw = sum(m.get('share') or 0 for m in comp)
    if cov.get('complete'):
        ck(abs(sw - 100) <= 0.02, 'Σ占比 = %.4f%%' % sw)
    else:
        ck(abs(sw - 100) <= 0.02, 'Σ占比（占已计价部分）= %.4f%%，已计价 %s/%s'
           % (sw, cov.get('n_computable'), cov.get('n_all')))

    print('\n== 3 零幅度影响必须为 0 ==')
    bad = []
    for sen in R['sensitivity']:
        for c in sen['cells']:
            if abs(c['ratio']) < 1e-12 and abs(c['cost_delta']) > TOL:
                bad.append(sen['name'])
    ck(not bad, 'Δc(0%)=0 全部成立' if not bad else '异常：%s' % bad)

    print('\n== 4 全同步情景线性恒等 ==')
    for ac in R['auto_combos']:
        exp = total * ac['ratio']
        ck(abs(ac['delta'] - exp) <= max(TOL, abs(exp) * 1e-9),
           '%s: Δ=%.4f 期望 %.4f' % (ac['label'], ac['delta'], exp))

    print('\n== 5 组合情景重算 ==')
    for cb in R['combos']:
        calc = 0.0
        for m in comp:
            r = (cb['changes'].get(m['id'], 0) or 0) / 100.0
            calc += m['dosage'] * m['price'] * (1 + r)
        ck(abs(calc - cb['new_total']) <= max(TOL, abs(calc) * 1e-9),
           '%s: C\'=%.4f 期望 %.4f' % (cb['name'], cb['new_total'], calc))

    print('\n== 6 历史末行 vs 当期成本 ==')
    hrows = (R.get('history') or {}).get('rows') or []
    if hrows:
        last = hrows[-1]['cost']
        # 只有当历史末行价格与当期价格一致时才应相等；给出差异提示
        diff = abs((last or 0) - total)
        ck(diff <= max(1.0, total * 0.02),
           '历史 %s 成本 %.2f vs 当期 %.2f（差 %.2f）' % (hrows[-1]['date'], last or 0, total, diff))
    else:
        print('  [skip] 无历史序列')

    print('\n== 7 贡献分解闭合 ==')
    for w in R.get('contribution') or []:
        if w.get('status') != 'ok':
            print('  [skip] %s：%s' % (w.get('period'), w.get('reason') or '缺口'))
            continue
        parts = sum(x['delta'] for x in w['items'])
        tot = w['total_delta']
        ck(abs(parts - tot) <= max(TOL, abs(tot) * 1e-6),
           '%s: Σ贡献 %.4f vs ΔC_T %.4f' % (w['period'], parts, tot))
        # 占比合计 100%（|ΔC_T| 足够大时）
        if abs(tot) > 0.01:
            sp = sum(x.get('share_of_change') or 0 for x in w['items'])
            ck(abs(sp - 100) <= 0.02, '%s: Σ贡献占比 %.4f%%' % (w['period'], sp))

    print('\n== 合计：%s ==' % ('全部通过' if not FAIL else '%d 项失败' % len(FAIL)))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
