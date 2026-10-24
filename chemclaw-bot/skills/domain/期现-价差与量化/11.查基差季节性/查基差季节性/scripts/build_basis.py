# -*- coding: utf-8 -*-
"""
构建 甲醇 基差 三套映射序列
============================
输入：
  out/spot_100ppi_meitan_benchmark.csv   (date,price,source_url)  生意社甲醇基准价
  raw/MA_MA*.json                        (郑商所逐合约日线)
输出：
  out/map_near.csv     近月连续（当月合约，最后交易日后切下一月合约）
  out/map_main.csv     主力连续（持仓量OI最大合约）
  out/map_fixed_{mm}.csv  固定交割月 mm 的合约（横跨多年，同一交割月不同年份不得混为同一样本）
  out/roll_log_*.csv   每次换月记录
  out/basis_*.csv      日度基差 = 现货 - 期货
口径：
  基差 = 现货价格 - 期货价格（严格此符号）
  现货缺失 -> 该日不产生基差，不填补
"""
import csv, glob, json, os, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, 'raw')
OUT = os.path.join(ROOT, 'out')
os.makedirs(OUT, exist_ok=True)

# 近月流动性门槛：临近交割(<=20个交易日)时，若该合约持仓 < 主力持仓的该比例，视为不可交割报价，跳过
MIN_OI_RATIO = 0.05


def load_contracts():
    d = {}
    for fp in glob.glob(os.path.join(RAW, 'MA_MA*.json')):
        j = json.load(open(fp, encoding='utf-8'))
        d[j['symbol']] = {r['d']: r for r in j['rows']}
    return d


def load_ma0():
    p = os.path.join(RAW, 'MA0_daily.json')
    if not os.path.exists(p):
        p = r"./weekly-meoh-2026W42\raw\_src\MA0_daily.json"
    j = json.load(open(p, encoding='utf-8'))
    rows = j['rows'] if isinstance(j, dict) else j
    return {r.get('date') or r.get('d'): r for r in rows}


def load_spot():
    p = os.path.join(OUT, 'spot_100ppi_meitan_benchmark.csv')
    s = {}
    with open(p, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            try:
                s[r['date'].strip()] = float(r['price'])
            except Exception:
                pass
    return s


def ym(sym):
    return 2000 + int(sym[2:4]), int(sym[4:6])


def wcsv(name, rows, cols=None):
    if not rows:
        print('[SKIP]', name, 'no rows')
        return
    cols = cols or list(rows[0].keys())
    p = os.path.join(OUT, name)
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, '') for c in cols])
    print('[OUT]', name, len(rows))


def roll_events(seq, key_sym, key_px, name):
    """seq: [{'date','sym','px'}] -> 换月记录"""
    out, prev = [], None
    for r in seq:
        if prev and r[key_sym] != prev[key_sym]:
            gap = round(r[key_px] - prev[key_px], 2)
            out.append({'换月日': r['date'], '移出合约': prev[key_sym], '移入合约': r[key_sym],
                        '移出前收盘': prev[key_px], '移入日收盘': r[key_px],
                        '换月跳空(元/吨)': gap, '跳空占比%': round(100.0 * gap / prev[key_px], 3) if prev[key_px] else ''})
        prev = r
    return out


def main():
    contracts = load_contracts()
    spot = load_spot()
    print('[INFO] 合约数 %d, 现货点数 %d (%s ~ %s)' % (
        len(contracts), len(spot), min(spot), max(spot)))

    # 期货交易日历 = 全部合约出现过的日期（2022-08-17 之后）
    all_dates = sorted({d for v in contracts.values() for d in v})
    dates = [d for d in all_dates if d >= '2022-08-01']

    # ---------- 近月连续 ----------
    # 硬规则：合约在其"最后交易日"当日收盘后即退出，次日必定切换到下一合约。
    # 若数据中该合约在最后交易日之后仍有K线（尾段残留行），一律不采用，并记录为异常。
    ltd = {}
    for sym, c in contracts.items():
        ds = sorted(c)
        if ds:
            ltd[sym] = ds[-1]
    tail_anomaly = []
    near = []
    illiquid = []
    for d in dates:
        y, m = int(d[:4]), int(d[5:7])
        # 近月候选顺序：本月合约 -> 下月 -> ...；但必须满足流动性门槛
        cands = []
        yy, mm = y, m
        for _ in range(6):
            cands.append('MA%02d%02d' % (yy % 100, mm))
            mm += 1
            if mm > 12:
                mm = 1
                yy += 1
        # 当日"主力"（持仓最大）用于流动性比较
        main_sym, main_oi = None, -1
        for sym, c in contracts.items():
            rec = c.get(d)
            if rec and rec['oi'] > main_oi:
                main_oi, main_sym = rec['oi'], sym
        for sym in cands:
            c = contracts.get(sym)
            if not c or d not in c or ltd.get(sym, '') < d:
                continue
            oi = c[d]['oi']
            # 流动性门槛：临近交割(<20交易日)且持仓 < 主力持仓的 MIN_OI_RATIO 时视为不可交割报价，跳过
            days_to_last = sum(1 for x in sorted(c) if d < x)
            if days_to_last <= 20 and main_oi > 0 and oi < MIN_OI_RATIO * main_oi:
                illiquid.append({'日期': d, '跳过合约': sym, '该合约持仓': oi, '主力合约': main_sym,
                                 '主力持仓': main_oi, '持仓比': round(oi / main_oi, 4),
                                 '距最后交易日(交易日)': days_to_last})
                continue
            near.append({'date': d, 'sym': sym, 'px': c[d]['c'], 'oi': oi})
            break
    wcsv('anomaly_illiquid_skipped.csv', illiquid)
    print('[INFO] 因流动性不足被跳过的"伪近月"报价: %d 条' % len(illiquid))
    # 记录：最后交易日之后仍有成交的残留行
    for sym, c in contracts.items():
        for d in sorted(c):
            if d > ltd[sym]:
                tail_anomaly.append({'合约': sym, '最后交易日': ltd[sym], '残留行日期': d})
    wcsv('anomaly_after_last_trading_day.csv', tail_anomaly)
    print('[INFO] 最后交易日之后仍有K线的残留行: %d' % len(tail_anomaly))
    wcsv('map_near.csv', [{'date': r['date'], 'contract': r['sym'], 'fut_price': r['px'], 'oi': r['oi']} for r in near])
    rolls_near = roll_events(near, 'sym', 'px', 'near')
    wcsv('roll_log_near.csv', rolls_near)

    # ---------- 主力连续 ----------
    main = []
    for d in dates:
        best, boi = None, -1
        for sym, c in contracts.items():
            y, m = ym(sym)
            if '%d-%02d' % (y, m) < d[:7]:
                continue
            rec = c.get(d)
            if rec and rec['oi'] > boi:
                boi, best = rec['oi'], sym
        if best:
            main.append({'date': d, 'sym': best, 'px': contracts[best][d]['c'], 'oi': boi})
    wcsv('map_main.csv', [{'date': r['date'], 'contract': r['sym'], 'fut_price': r['px'], 'oi': r['oi']} for r in main])
    rolls_main = roll_events(main, 'sym', 'px', 'main')
    wcsv('roll_log_main.csv', rolls_main)

    # ---------- 固定交割月（横跨多年，逐年独立） ----------
    ma0 = load_ma0()
    for mm in [1, 5, 9]:
        seq = []
        for d in dates:
            y = int(d[:4])
            # 该自然年/mm 合约，在其存续期内使用
            for yy in (y - 1, y, y + 1):
                sym = 'MA%02d%02d' % (yy % 100 if False else yy % 100, mm)
                if sym in contracts and d in contracts[sym]:
                    t = contracts[sym][d]
                    # 只取到该合约最后交易日之前
                    seq.append({'date': d, 'sym': sym, 'px': t['c'], 'oi': t['oi']})
                    break
        # 去掉重复（不同年份合约在同一日不会同时命中）
        wcsv('map_fixed_%02d.csv' % mm,
             [{'date': r['date'], 'contract': r['sym'], 'fut_price': r['px'], 'oi': r['oi']} for r in seq])

    # ---------- 基差 ----------
    def build_basis(seq, tag):
        rows, miss = [], 0
        for r in seq:
            s = spot.get(r['date'])
            if s is None:
                miss += 1
                continue
            rows.append({'date': r['date'], 'contract': r['sym'], 'spot': s,
                         'fut': r['px'], 'basis': round(s - r['px'], 2), 'oi': r['oi']})
        wcsv('basis_%s.csv' % tag, rows, ['date', 'contract', 'spot', 'fut', 'basis', 'oi'])
        print('   %s: 期货日 %d, 有现货 %d, 缺现货 %d, 基差均值 %.2f' % (
            tag, len(seq), len(rows), miss, (sum(x['basis'] for x in rows) / len(rows)) if rows else 0))
        return rows

    print('[BUILD] 基差序列')
    b_near = build_basis(near, 'near')
    b_main = build_basis(main, 'main')

    # ---------- 换月日的基差跳空 ----------
    def roll_basis_effect(basis_rows, roll_dates, tag):
        idx = {r['date']: i for i, r in enumerate(basis_rows)}
        out = []
        for rd in roll_dates:
            if rd in idx and idx[rd] > 0:
                cur = basis_rows[idx[rd]]
                prev = basis_rows[idx[rd] - 1]
                out.append({'换月日': rd, '换月前一日': prev['date'],
                            '移出合约': prev['contract'], '移入合约': cur['contract'],
                            '基差(前)': prev['basis'], '基差(后)': cur['basis'],
                            '基差变化': round(cur['basis'] - prev['basis'], 2),
                            '期间现货变化': round(cur['spot'] - prev['spot'], 2),
                            '期间期货变化(含换月跳空)': round(cur['fut'] - prev['fut'], 2),
                            '注意': '期货变化含换月跳空，不等于真实价格变动'})
        wcsv('roll_basis_effect_%s.csv' % tag, out)
        return out

    rd_near = [r['换月日'] for r in rolls_near]
    rd_main = [r['换月日'] for r in rolls_main]
    roll_basis_effect(b_near, rd_near, 'near')
    roll_basis_effect(b_main, rd_main, 'main')

    # ---------- 换月造成的"伪跳空"量化 ----------
    # 同一日"移入合约"与"移出合约"同时有价格 -> 真实跨月价差
    same_day = []
    for r in rolls_near:
        d = r['换月日']
        a = contracts.get(r['移出合约'], {}).get(d)
        b = contracts.get(r['移入合约'], {}).get(d)
        if a and b:
            same_day.append({'换月日': d, '旧合约': r['移出合约'], '新合约': r['移入合约'],
                             '旧收盘': a['c'], '新收盘': b['c'], '两合约同日价差(元/吨)': round(b['c'] - a['c'], 2)})
    wcsv('roll_sameday_spread.csv', same_day)
    print('[INFO] 近月换月次数 %d, 主力换月 %d, 同日可比价差样本 %d'
          % (len(rolls_near), len(rolls_main), len(same_day)))


if __name__ == '__main__':
    main()
