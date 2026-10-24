# -*- coding: utf-8 -*-
"""rule_matcher —— 合约规则匹配与可比较性校验

职责
----
1. 解析合约代码 → (品种, 交割年, 交割月, 交易所)
2. 校验"是否合法挂牌月"（防止把 2403 这种品种没有的月份当成有效合约）
3. 校验一对合约能否构成有意义的月差（近月必须早于远月；间隔须在品种可比较范围内）
4. 输出"不可比/样本不足"的原因码，供报告与看板直接展示

原因码
------
INVALID_CODE      合约代码无法解析
NOT_LISTED        该交割月未挂牌（品种不设此月）
SAME_MONTH        两腿是同一合约
ORDER_REVERSED    近月晚于远月（需交换后重算）
GAP_TOO_LARGE     月差跨越过大（通常 >6 个月，受品级/仓储成本差异影响）
NEAR_EXPIRY       近月已到期或剩余不足 2 周（临近交割，报价失真）
ILLIQUID          任一腿持仓低于阈值（流动性不足，价差不可交易）
"""
from __future__ import annotations

import datetime as dt
import json
import re

REASONS = {
    'INVALID_CODE': '合约代码无法解析',
    'NOT_LISTED': '该交割月未挂牌（品种不设此月）',
    'SAME_MONTH': '两腿为同一合约',
    'ORDER_REVERSED': '近月晚于远月',
    'GAP_TOO_LARGE': '跨越月份过大',
    'NEAR_EXPIRY': '近月临近/已经交割',
    'ILLIQUID': '流动性不足',
}


def load_rules(path):
    with open(path, encoding='utf-8') as f:
        j = json.load(f)
    return j['products']


def parse_code(code):
    """'MA2701' → ('MA', 2027, 1)；解析失败返回 None。"""
    m = re.fullmatch(r'([A-Z]{1,3})(\d{2})(\d{2})', code.upper())
    if not m:
        return None
    y = 2000 + int(m.group(2))
    mo = int(m.group(3))
    if not 1 <= mo <= 12:
        return None
    return m.group(1), y, mo


def is_listed(rules, code):
    r = parse_code(code)
    if r is None:
        return False
    p, y, mo = r
    if p not in rules:
        return False
    return mo in rules[p]['listed_months']


def check_pair(rules, near_code, far_code, as_of, near_oi=None, far_oi=None,
               min_oi=500, max_gap=6, min_weeks_to_near=2):
    """校验一对合约。返回 (ok: bool, reasons: list[str], meta: dict)"""
    reasons = []
    rn, rf = parse_code(near_code), parse_code(far_code)
    if not rn or not rf:
        return False, ['INVALID_CODE'], {}
    pn, yn, mn = rn
    pf, yf, mf = rf
    if pn != pf:
        return False, ['INVALID_CODE'], {'note': '跨品种不构成月差'}
    if pn not in rules:
        return False, ['INVALID_CODE'], {'note': f'品种池不含 {pn}'}
    rule = rules[pn]
    if mn not in rule['listed_months'] or mf not in rule['listed_months']:
        reasons.append('NOT_LISTED')
    gap = (yf - yn) * 12 + (mf - mn)
    if gap == 0:
        reasons.append('SAME_MONTH')
    elif gap < 0:
        reasons.append('ORDER_REVERSED')
    if gap > max_gap:
        reasons.append('GAP_TOO_LARGE')
    # 近月剩余期限
    if mn == 12:
        near_end = dt.date(yn, 12, 20)
    else:
        near_end = dt.date(yn, mn, 20)
    weeks = (near_end - as_of).days / 7.0
    if weeks < min_weeks_to_near:
        reasons.append('NEAR_EXPIRY')
    if (near_oi is not None and near_oi < min_oi) or (far_oi is not None and far_oi < min_oi):
        reasons.append('ILLIQUID')
    meta = {
        'product': pn, 'exchange': rule['exchange'], 'exchange_cn': rule['exchange_cn'],
        'near': near_code, 'far': far_code, 'gap_months': gap,
        'weeks_to_near': round(weeks, 1),
        'is_main_edge': (mn in rule['main_months'] and mf in rule['main_months']),
        'contract_unit_t': rule['contract_unit_t'], 'tick': rule['tick'],
    }
    return (len(reasons) == 0), reasons, meta


def describe(rules, code):
    r = parse_code(code)
    if not r:
        return None
    p, y, m = r
    rule = rules.get(p)
    if not rule:
        return None
    return {
        'code': code, 'product': p, 'name_cn': rule['name_cn'],
        'exchange': rule['exchange'], 'delivery': f'{y}-{m:02d}',
        'is_main_month': m in rule['main_months'],
        'listed': m in rule['listed_months'],
        'unit_t': rule['contract_unit_t'],
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description='合约规则匹配 / 月差可比较性校验')
    ap.add_argument('--rules', default='contract_rules.json')
    ap.add_argument('--near', help='近月合约代码')
    ap.add_argument('--far', help='远月合约代码')
    ap.add_argument('--as-of', default=dt.date.today().isoformat())
    a = ap.parse_args()
    rules = load_rules(a.rules)
    if a.near and a.far:
        ok, reasons, meta = check_pair(rules, a.near, a.far, dt.date.fromisoformat(a.as_of))
        print(json.dumps({'ok': ok, 'reasons': [REASONS[x] for x in reasons], 'meta': meta},
                         ensure_ascii=False, indent=1))
    else:
        for p, r in rules.items():
            print(f"{p} {r['name_cn']} @{r['exchange']} months={r['listed_months']} "
                  f"unit={r['contract_unit_t']}t tick={r['tick']}")


if __name__ == '__main__':
    main()
