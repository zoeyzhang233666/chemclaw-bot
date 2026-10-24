# -*- coding: utf-8 -*-
"""selftest.py —— 月差引擎已知答案自测（无外部依赖，纯标准库）

    python scripts/selftest.py

覆盖 12 项核心行为：
  1. 月差 = 近月 − 远月，符号正确
  2. 收盘价与结算价口径互不串用
  3. 结算价为 0 / 空 的交易日被剔除（不补数）
  4. 成交量与持仓量同时为 0 的交易日被剔除
  5. 同一对合约只用共同交易日
  6. 不同月份组合的样本不会合并
  7. 可比样本每历史年份恰好 1 个
  8. 剩余期限严格按整周对齐
  9. 分位数边界：最小值=0分位口径、最大值=100
 10. 分位在单样本/空样本时返回 None
 11. 规则匹配：非法挂牌月与倒序组合被拦截
 12. 合约代码解析（含三位码年份推断）
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rule_matcher as RM  # noqa: E402
import spreadlib as S  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  ✓ {name}')
    else:
        FAIL += 1
        print(f'  ✗ {name}   {detail}')


def mk(product, y, m, rows):
    """rows: [(date, settle, close, vol, oi)]"""
    c = S.Contract(product, y, m)
    for row in rows:
        c.dates.append(dt.date.fromisoformat(row[0]))
        c.settle.append(row[1])
        c.close.append(row[2])
        c.volume.append(row[3])
        c.oi.append(row[4])
    c.first, c.last = c.dates[0], c.dates[-1]
    return c


def main():
    print('== 1-2 月差定义与价格口径 ==')
    near = mk('XX', 2027, 1, [('2026-10-20', 1000.0, 1010.0, 10, 100)])
    far = mk('XX', 2027, 5, [('2026-10-20', 940.0, 950.0, 10, 100)])
    seq = S.compute_pair_series(near, far, basis='settle')
    check('月差 = 近月−远月 = 60（结算价）', seq and seq[0]['spread'] == 60.0, seq)
    seq2 = S.compute_pair_series(near, far, basis='close')
    check('收盘口径 = 1010−950 = 60 且不与结算价混用', seq2 and seq2[0]['spread'] == 60.0
          and seq2[0]['near'] == 1010.0, seq2)

    print('== 3-5 数据质量过滤 ==')
    n2 = mk('XX', 2026, 1, [('2026-01-05', 0.0, 100.0, 5, 50),
                            ('2026-01-06', None, 101.0, 5, 50),
                            ('2026-01-07', 102.0, 103.0, 0, 0),
                            ('2026-01-08', 104.0, 105.0, 7, 70)])
    f2 = mk('XX', 2026, 5, [('2026-01-05', 90.0, 90.0, 5, 50),
                            ('2026-01-06', 91.0, 91.0, 5, 50),
                            ('2026-01-07', 92.0, 92.0, 5, 50),
                            ('2026-01-08', 99.0, 99.0, 7, 70)])
    s2 = S.compute_pair_series(n2, f2)
    dates = [r['date'].isoformat() for r in s2]
    check('settle=0 的 01-05 被剔除', '2026-01-05' not in dates, dates)
    check('settle=None 的 01-06 被剔除', '2026-01-06' not in dates, dates)
    check('成交量与持仓量同时为0的 01-07 被剔除', '2026-01-07' not in dates, dates)
    check('仅保留共同且有效的 01-08', dates == ['2026-01-08'], dates)
    check('该日价差 = 104−99 = 5', s2 and s2[0]['spread'] == 5.0, s2)

    print('== 6-8 可比样本构造 ==')
    as_of = dt.date(2026, 10, 20)
    cons = {}
    # 造 2024/2025/2026 三年的 01/05 合约，围绕 1 月 20 日附近
    for yr in (2024, 2025):
        d0 = dt.date(yr - 1, 10, 15)
        rows_n, rows_f = [], []
        for k in range(0, 30):
            dd = d0 + dt.timedelta(days=k)
            rows_n.append((dd.isoformat(), 1000.0 + k, 1000.0 + k, 5, 50))
            rows_f.append((dd.isoformat(), 950.0 + k, 950.0 + k, 5, 50))
        cons[f'YY{yr % 100:02d}01'] = mk('YY', yr, 1, rows_n)
        cons[f'YY{yr % 100:02d}05'] = mk('YY', yr, 5, rows_f)
    samp = S.comparable_sample(cons, 'YY', 'YY2701', 'YY2705', as_of)
    years = [x['year'] for x in samp]
    check('每历史年份恰好 1 个样本', len(years) == len(set(years)) and years == [2024, 2025], years)
    check('不把当年合约计入历史样本', 2026 not in years, years)
    wk = {x['week_to_near'] for x in samp}
    check('剩余期限周数彼此一致（±0.2 周）', len(wk) <= 1 or (max(wk) - min(wk)) < 0.2, wk)

    print('== 9-10 分位与边界 ==')
    sample = [10.0, 20.0, 30.0, 40.0, 50.0]
    check('中位数 30 → 50 分位', abs(S.percentile_rank(30.0, sample) - 50.0) < 1e-9,
          S.percentile_rank(30.0, sample))
    check('最小值 10 → 10 分位(0.5/5*100)', abs(S.percentile_rank(10.0, sample) - 10.0) < 1e-9)
    check('低于全部样本 → 0 分位', S.percentile_rank(0.0, sample) == 0.0)
    check('高于全部样本 → 100 分位', S.percentile_rank(99.0, sample) == 100.0)
    check('空样本返回 None', S.percentile_rank(1.0, []) is None)
    check('单样本 zscore 返回 None', S.zscore(1.0, [1.0]) is None)
    check('quantile 0.05 线性插值正确', abs(S.quantile([0.0, 100.0], 0.05) - 5.0) < 1e-9)

    print('== 11-12 规则匹配与代码解析 ==')
    rules = {
        'SA': {'name_cn': '纯碱', 'exchange': 'CZCE', 'exchange_cn': '郑州商品交易所',
               'listed_months': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
               'contract_unit_t': 20, 'tick': 1, 'main_months': [1, 5, 9]},
        'UR': {'name_cn': '季月品种', 'exchange': 'CZCE', 'exchange_cn': '郑州商品交易所',
               'listed_months': [1, 3, 5, 9, 11], 'contract_unit_t': 10, 'tick': 1,
               'main_months': [1, 5, 9]},
    }
    ok, reasons, meta = RM.check_pair(rules, 'SA2701', 'SA2705', as_of)
    check('合法组合 SA2701-SA2705 通过', ok and not reasons, reasons)
    check('间隔月数 = 4', meta['gap_months'] == 4, meta)
    ok2, r2, _ = RM.check_pair(rules, 'UR2507', 'UR2601', as_of)
    check('未挂牌月份(7月)被拦截', not ok2 and 'NOT_LISTED' in r2, r2)
    ok3, r3, _ = RM.check_pair(rules, 'SA2705', 'SA2701', as_of)
    check('倒序组合被拦截', not ok3 and 'ORDER_REVERSED' in r3, r3)
    ok4, r4, _ = RM.check_pair(rules, 'SA2610', 'SA2701', as_of)
    check('近月剩余不足2周被拦截', not ok4 and 'NEAR_EXPIRY' in r4, r4)
    check('parse_code 解析 MA2701', RM.parse_code('MA2701') == ('MA', 2027, 1))
    check('parse_code 拒绝非法月', RM.parse_code('MA2713') is None)

    print(f'\n结果：{PASS} 通过 / {FAIL} 失败')
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
