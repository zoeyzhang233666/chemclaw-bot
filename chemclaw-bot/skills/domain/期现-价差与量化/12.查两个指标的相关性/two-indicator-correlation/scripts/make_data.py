# -*- coding: utf-8 -*-
"""数据层：①真实期货日线（新浪财经公开接口，主力连续合约 MA0）
              ②按真实行业口径拟真的周度港口库存 / 江苏太仓出罐现货价（DEMO，非真实市场数据）

拟真机制（可审计）：
  库存 I_t  = 前期库存 + 到港 n_t + 国产外运 s_t - 下游提货 d_t，基准水平约 60 万吨，季节项（春节累库、4-6月去库、9-10月累库）
  价格 P_t  = 基准 + 成本项(煤价) + 需求项(下游开工) - λ·库存中枢偏离 + 噪声，λ 分段变化（相关性强弱/转向由此产生）
  所有生成的数值均标注 data_status = DEMO_SIMULATED，不得当作真实市场数据引用。
"""
import os, sys, json, csv, math, random

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'data')
os.makedirs(DATA, exist_ok=True)

# ---------------------------------------------------------------- 真实期货日线
def load_real_futures(path):
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append((r['date'], float(r['close'])))
    return rows


def write_csv(path, header, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------- 拟真周度数据
def gen_demo_weekly(n_weeks=156, start_ymd=(2023, 10, 4), seed=20261020,
                    lam_segments=((0, 40, 1.0), (40, 84, 0.35), (84, 120, 0.04), (120, 156, 0.7)),
                    kappa=0.30):
    """生成周度（周三）港口库存与太仓出罐现货价（DEMO）。

    库存为均值回复过程（均值 62 万吨、季度季节项），价格由
      成本项 + 需求项 - λ·(库存偏离中枢) + 面板效应 + 噪声
    构成；λ 分段变化，制造“相关性强→弱→脱钩→恢复”的市场阶段。
    面板效应（ma_ref）让价格与库存共享一个共同外部因素，用于演示“虚假相关”诊断。
    """
    rnd = random.Random(seed)
    # 1) 库存调查日 = 周三；取其后最近的期货交易日作为“价格锚”，确保该日期真实可得
    dates = [d for d, _ in load_real_futures(os.path.join(DATA, 'MA0.csv'))]
    dset = set(dates)
    from datetime import date, timedelta
    wed = date(*start_ymd)
    we = []
    while len(we) < n_weeks:
        wed += timedelta(days=7)
        # 库存调查日 = 周三，取其后最近的期货交易日作为“价格锚”，确保各日期真实可得
        anchor = wed
        for k in range(6):
            cand = (wed + timedelta(days=k)).isoformat()
            if cand in dset:
                anchor = wed + timedelta(days=k)
                break
        we.append((wed.isoformat(), anchor.isoformat()))
    # 2) 机制变量：库存为 OU（均值回复）过程；价格 = 成本 + 需求 - λ·库存偏离 + 面板效应 + 噪声
    mom = 0.0
    container = 0.0
    sigma_I = 8.5                     # 库存冲击的周度波动（万吨）
    LEVEL = 62.0
    level = LEVEL
    ma_ref = 0.0                      # 共同外部因素（宏观/能源/政策情绪面板），两者共享 → 虚假相关来源
    season_curve = {1: 2.2, 2: 3.4, 3: 1.0, 4: -2.0, 5: -2.6, 6: -1.2,
                    7: 0.4, 8: 1.0, 9: 2.0, 10: 1.4, 11: 0.2, 12: 0.8}
    rows = []
    for i, (d_wed, d_anchor) in enumerate(we):
        m = int(d_wed[5:7])
        seas = season_curve[m]
        ma_ref = 0.97 * ma_ref + rnd.gauss(0, 12.0)                  # 慢变共享因子（价格/库存同受其影响的渠道）
        container = 0.62 * container + rnd.gauss(0, 2.6)             # 船期/到港聚集冲击(AR1)
        mom = 0.55 * mom + rnd.gauss(0, 1)                           # 运力/检修冲击(AR1)
        arrival = 11.9 + 0.25 * mom + container + rnd.gauss(0, 1.1)  # 周度到港（万吨）
        demand = 12.05 - 0.36 * seas + 0.5 * math.sin(i / 9.0) + rnd.gauss(0, 0.9)
        inflow = arrival - demand
        level = LEVEL + seas + (1 - kappa) * (level - LEVEL - seas) + inflow + rnd.gauss(0, 1.3)
        I = level + 0.10 * ma_ref                                    # 共享因子也小幅影响库存
        # 价格
        coal = 780 + 38 * math.sin(i / 7.3 + 0.6) + rnd.gauss(0, 4.5)
        op_rate = 70 + 4.2 * math.sin(i / 11.0) + rnd.gauss(0, 1.2)   # 下游开工率(%)
        lam = 0.0
        for a, b, l in lam_segments:
            if a <= i < b:
                lam = l
        P = (2350 + 1.35 * (coal - 780) + 9.5 * (op_rate - 70)
             - lam * 65.0 * (I - LEVEL) + 0.9 * ma_ref + rnd.gauss(0, 95))
        # 价格“情绪/投机”分量：与库存无关的独立 AR(1)，后期转弱造成价格震荡，用于演示相关性的“抹平”
        P = max(1500.0, P)
        rows.append(dict(week_ending=d_wed, price_date=d_anchor,
                         inventory_total=round(I, 2),
                         inventory_ec=round(I * 0.66 + rnd.gauss(0, 0.9), 2),
                         inventory_sc=round(I * 0.34 - rnd.gauss(0, 0.9), 2),
                         arrival=round(arrival, 2), demand=round(demand, 2),
                         spot_taicang=round(P, 0), coal_5500=round(coal, 0),
                         op_rate=round(op_rate, 1), lam_used=lam))
    # 让华东+华南 = 总量（修正取整误差）
    for r in rows:
        r['inventory_sc'] = round(r['inventory_total'] - r['inventory_ec'], 2)
    return rows


def main():
    # 真实：MA0 日线（全量）
    fut = load_real_futures(os.path.join(DATA, 'MA0.csv'))
    print('real futures rows', len(fut))
    # 拟真周度
    rows = gen_demo_weekly()
    write_csv(os.path.join(DATA, 'demo_methanol_weekly.csv'),
              ['week_ending', 'price_date', 'inventory_total', 'inventory_ec', 'inventory_sc',
               'arrival', 'demand', 'spot_taicang', 'coal_5500', 'op_rate', 'lam_used'],
              [[r['week_ending'], r['price_date'], r['inventory_total'], r['inventory_ec'], r['inventory_sc'],
                r['arrival'], r['demand'], r['spot_taicang'], r['coal_5500'], r['op_rate'], r['lam_used']] for r in rows])
    print('demo weekly rows', len(rows), rows[0], rows[-1])

    # 真实：MA0 在拟真覆盖期内的日线裁剪（用于对照真实期货 vs 拟真库存）
    lo, hi = rows[0]['price_date'], rows[-1]['price_date']
    sub = [x for x in fut if lo <= x[0] <= hi]
    write_csv(os.path.join(DATA, 'MA0_daily_cropped.csv'), ['date', 'close'], sub)
    print('cropped futures', len(sub), sub[0], sub[-1])

    meta = {
        'demo': {
            'status': 'DEMO_SIMULATED',
            'product': '甲醇（工业级，江苏太仓港口出罐）',
            'inventory': {'name': '中国甲醇样本港口库存（总）', 'unit': '万吨',
                          'freq': '周度（调查日=周三）', 'region': '华东（江苏/浙江各港口）+ 华南',
                          'source': 'DEMO：按隆众资讯周度口径拟真，非真实市场数据',
                          'release_lag_days': 0},
            'price': {'name': '江苏太仓甲醇出罐现货价（现汇）', 'unit': '元/吨',
                      'freq': '周度（取当周价格锚日收盘）', 'region': '江苏太仓',
                      'source': 'DEMO：按隆众/我的钢铁日报口径拟真，非真实市场数据',
                      'release_lag_days': 0},
            'weeks': len(rows), 'first': rows[0]['week_ending'], 'last': rows[-1]['week_ending'],
            'seed': 20261020,
            'caveat': '本文件所有数值为教学/演示用拟真数据（机制见 scripts/make_data.py），不得作为真实行情或研究结论引用。'
        },
        'real': {
            'MA0': {'name': '郑商所甲醇期货主力连续（收盘价/结算价）', 'unit': '元/吨', 'freq': '日度交易日',
                    'source': '新浪财经公开 K 线接口 InnerFuturesNewService.getDailyKLine，symbol=MA0',
                    'coverage': [fut[0][0], fut[-1][0]], 'rows': len(fut)}
        }
    }
    json.dump(meta, open(os.path.join(DATA, 'data_meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('meta written')


if __name__ == '__main__':
    main()
