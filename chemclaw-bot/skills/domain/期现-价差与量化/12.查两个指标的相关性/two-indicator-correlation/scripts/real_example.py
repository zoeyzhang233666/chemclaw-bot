# -*- coding: utf-8 -*-
"""真实数据示例：甲醇期货主力（MA0）与几个公开可得序列的相关性研究。

用途：在"现货-库存"历史序列拿不到的情况下，演示同一套方法在**真实公开数据**上的运行结果，
      并给出可直接引用的口径说明。

序列（全部来自新浪财经公开 K 线接口 / 由日线聚合）：
  X1 = MA0 日收盘价（元/吨，主力连续）
  X2 = MA0 周均价（由日线聚合，周三为周锚）
  Y1 = 甲醇 20 日实现波动率（由日收益滚动标准差年化，%）
  Y2 = 甲醇主力合约持仓量（手）的周变化
真实数据可以回答的问题：价格水平 vs 波动率、价格变化 vs 持仓变化。

输出：data/real_MA0_weekly.csv + build/real_result.json（供报告引用）
"""
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import corrlib as C  # noqa: E402

SRC = os.path.join(ROOT, 'data', 'MA0.csv')
OUT_CSV = os.path.join(ROOT, 'data', 'real_MA0_weekly.csv')
OUT_JSON = os.path.join(ROOT, 'build', 'real_result.json')


def load_daily():
    rows = []
    with open(SRC, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append((r['date'], float(r['close']), float(r['open_interest'])))
    rows.sort()
    return rows


def weekly_aggregate(rows):
    """按自然周（ISO 周）聚合：取周内最后交易日为锚，收盘价、周均价、波动率、持仓。"""
    weeks = {}
    for d, close, oi in rows:
        y, m, dd = (int(x) for x in d.split('-'))
        import datetime
        iso = datetime.date(y, m, dd).isocalendar()
        key = (iso[0], iso[1])
        weeks.setdefault(key, []).append((d, close, oi))
    out = []
    closes_all = [r[1] for r in rows]
    dates_all = [r[0] for r in rows]
    for key in sorted(weeks):
        days = weeks[key]
        anchor = days[-1]
        # 周均价
        avg = sum(x[1] for x in days) / len(days)
        # 20 日实现波动率（截至锚日，年化 %）
        i = dates_all.index(anchor[0])
        window = closes_all[max(0, i - 19):i + 1]
        if len(window) >= 10:
            rets = [math.log(window[k] / window[k - 1]) for k in range(1, len(window))]
            mu = sum(rets) / len(rets)
            var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
            vol = math.sqrt(var) * math.sqrt(252) * 100
        else:
            vol = None
        out.append({
            'week_anchor': anchor[0],
            'close': anchor[1],
            'week_avg': round(avg, 2),
            'open_interest': anchor[2],
            'rv20': None if vol is None else round(vol, 2),
            'n_days': len(days),
        })
    return out


def main():
    rows = load_daily()
    wk = weekly_aggregate(rows)
    # 计算周变化列
    for i, w in enumerate(wk):
        if i == 0:
            w['oi_change'] = None
            w['close_change'] = None
            w['close_pct'] = None
        else:
            p = wk[i - 1]
            w['oi_change'] = round(w['open_interest'] - p['open_interest'], 0)
            w['close_change'] = round(w['close'] - p['close'], 2)
            w['close_pct'] = round((w['close'] - p['close']) / p['close'] * 100, 3)
    with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['week_anchor', 'close', 'week_avg', 'open_interest',
                                          'rv20', 'oi_change', 'close_change', 'close_pct', 'n_days'])
        w.writeheader()
        w.writerows(wk)
    print('written', OUT_CSV, len(wk), 'weeks')

    dates = [w['week_anchor'] for w in wk]
    close = [w['close'] for w in wk]
    avg = [w['week_avg'] for w in wk]
    vol = [w['rv20'] for w in wk]
    oi = [w['open_interest'] for w in wk]
    oic = [w['oi_change'] for w in wk]
    pct = [w['close_pct'] for w in wk]

    def pair(x, y):
        a, b, _ = C.align(x, y, dates)
        return C.corr_stats(a, b)

    result = {
        'meta': {
            'status': 'REAL_PUBLIC_DATA',
            'source': '新浪财经 InnerFuturesNewService.getDailyKLine，symbol=MA0（郑商所甲醇主力连续，日线）',
            'period': [dates[0], dates[-1]],
            'weeks': len(wk),
            'note': '主力连续合约在换月处有价格跳变，因此变化类口径仅作方向参考；波动率与持仓为衍生指标。',
        },
        'pairs': {
            'close_vs_rv20': pair(close, vol),
            'close_pct_vs_oi_change': pair(pct, oic),
            'week_avg_vs_rv20': pair(avg, vol),
            'close_vs_oi': pair(close, oi),
        },
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(result, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in result['pairs'].items():
        if v.get('r') is None:
            print(f'  {k}: 样本不足')
            continue
        print(f"  {k}: r={v['r']:.4f} N={v['n']} p={v['p']:.3g} "
              f"CI=[{v.get('ci_lo', float('nan')):.3f}, {v.get('ci_hi', float('nan')):.3f}]")
    print('written', OUT_JSON)


if __name__ == '__main__':
    main()
