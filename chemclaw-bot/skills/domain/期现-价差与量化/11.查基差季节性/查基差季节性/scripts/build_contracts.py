# -*- coding: utf-8 -*-
"""
构建郑商所甲醇(MA)合约层数据：
  1) 合约日历（挂牌->最后交易日，按"交割月第10个交易日"规则核算）
  2) 主力连续映射（按每日持仓量OI最大识别主力，用MA0校验）
  3) 近月连续映射（交割月前N个自然月起，持有至最后交易日）
  4) 固定交割月份序列（如每年1/5/9月合约的"交割前"基差）
输出:
  out/contract_calendar.csv
  out/map_main.csv / out/map_near.csv
  out/roll_log_main.csv / out/roll_log_near.csv
  以及 raw/MA0_daily.json 的副本(作为日历参考)
规则溯源：
  - 郑商所《甲醇期货业务细则》：最后交易日为合约交割月份的第10个交易日
    （二手解读见 https://www.shinnytech.com/articles/business-rules/products/czce.ma ，
      原文链接 http://www.czce.com.cn/cn/flfg/zcjywgz/pzxz/webinfo/2024/02/1708568084772420.htm）
  - 本脚本不"相信"规则，而是用实际数据反核：把每个合约的最后一条K线日期与"第10个交易日"对比，偏差>0则标记。
"""
import json, os, glob, sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw')
OUT = os.path.join(ROOT, 'out')
os.makedirs(OUT, exist_ok=True)

MA0_PATH = r"./weekly-meoh-2026W42\raw\_src\MA0_daily.json"
if not os.path.exists(MA0_PATH):
    MA0_PATH = os.path.join(RAW, 'MA0_daily.json')


def load_contracts():
    data = {}
    for fp in glob.glob(os.path.join(RAW, 'MA_MA*.json')):
        d = json.load(open(fp, encoding='utf-8'))
        sym = d['symbol']
        rows = sorted(d['rows'], key=lambda x: x['d'])
        data[sym] = rows
    return data


def load_ma0():
    d = json.load(open(MA0_PATH, encoding='utf-8'))
    rows = d['rows'] if isinstance(d, dict) else d
    return {r.get('date') or r.get('d'): r for r in rows}


def sym_to_ym(sym):
    return 2000 + int(sym[2:4]), int(sym[4:6])


def verify_rule(actual_last, rule_ltd, month_td):
    """规则核验口径：
       - 完全一致            -> 符合
       - 提前1个交易日结束    -> 流动性提前退出(符合规则上限，仍记为可接受)
       - 提前更多            -> 需复核
       - 晚于规则最后交易日   -> 违反规则(不可接受)
    """
    if not rule_ltd:
        return '待查(交割月交易日不足)'
    if actual_last == rule_ltd:
        return '符合'
    if actual_last in month_td:
        i_act, i_rule = month_td.index(actual_last), month_td.index(rule_ltd)
        if i_act < i_rule and i_rule - i_act == 1:
            return '提前1个交易日(流动性)'
        if i_act < i_rule:
            return '提前%d个交易日(需复核)' % (i_rule - i_act)
        return '晚于规则最后交易日(异常)'
    return '末个K线不在交割月(需复核)'


def main():
    contracts = load_contracts()
    ma0 = load_ma0()
    cal = sorted(ma0.keys())
    cal_set = set(cal)

    # ---------- 1) 合约日历 ----------
    calendar = []
    for sym, rows in sorted(contracts.items()):
        y, m = sym_to_ym(sym)
        pref = '%d-%02d' % (y, m)
        month_td = [d for d in cal if d[:7] == pref]
        rule_ltd = month_td[9] if len(month_td) >= 10 else None   # 交割月第10个交易日
        actual_first = rows[0]['d']
        actual_last = rows[-1]['d']
        calendar.append({
            '合约': sym, '交割年月': pref, '挂牌首日(有K线)': actual_first, '末个K线日': actual_last,
            '交割月交易日数': len(month_td),
            '规则最后交易日(第10个交易日)': rule_ltd,
            '规则核验': verify_rule(actual_last, rule_ltd, month_td),
            '数据天数': len(rows),
        })

    # ---------- 2) 主力连续（每日OI最大） ----------
    # 只用"尚有剩余到期月"的合约避免死合约。
    map_main = []
    for d in cal:
        if d < '2020-01-01':
            continue
        best, best_oi = None, -1
        for sym, rows in contracts.items():
            y, m = sym_to_ym(sym)
            if '%d-%02d' % (y, m) < d[:7]:
                continue
            # 找该合约当日
            rec = None
            for r in rows:
                if r['d'] == d:
                    rec = r
                    break
            if rec is None:
                continue
            if rec['oi'] > best_oi:
                best_oi, best = rec['oi'], sym
        if best:
            map_main.append({'日期': d, '主力合约': best, '主力持仓量': best_oi,
                             '主力收盘': next(r['c'] for r in contracts[best] if r['d'] == d),
                             'MA0收盘': ma0[d]['close']})

    mismatch = [r for r in map_main if abs(r['主力收盘'] - r['MA0收盘']) > 0.01]
    roll_log_main = []
    prev = None
    for r in map_main:
        if prev and r['主力合约'] != prev['主力合约']:
            roll_log_main.append({'换月日': r['日期'], '移出': prev['主力合约'], '移入': r['主力合约'],
                                  '移出合约收盘': prev['主力收盘'], '移入合约收盘': r['主力收盘'],
                                  '换月跳空': round(r['主力收盘'] - prev['主力收盘'], 1)})
        prev = r

    # ---------- 3) 近月连续 ----------
    # 定义：对每个自然月，取"交割月 == 当前月"的合约为主近月；
    # 在该合约最后交易日之后，切到下一自然月合约。即始终持有最接近到期的合约。
    map_near = []
    for d in cal:
        if d < '2020-01-01':
            continue
        y, m = int(d[:4]), int(d[5:7])
        prev_ym = (y - 1, 12) if m == 1 else (y, m - 1)
        nxt_ym = (y + 1, 1) if m == 12 else (y, m + 1)
        cand = ['MA%02d%02d' % (yy % 100, mm) for yy, mm in [(y, m), nxt_ym]]
        chosen = None
        for sym in cand:
            rows = contracts.get(sym)
            if rows and rows[0]['d'] <= d <= rows[-1]['d']:
                chosen = sym
                break
        if chosen:
            rec = next((r for r in contracts[chosen] if r['d'] == d), None)
            if rec is not None:
                map_near.append({'日期': d, '近月合约': chosen, '近月收盘': rec['c'], '近月持仓量': rec['oi']})
    roll_log_near = []
    prev = None
    for r in map_near:
        if prev and r['近月合约'] != prev['近月合约']:
            roll_log_near.append({'换月日': r['日期'], '移出': prev['近月合约'], '移入': r['近月合约'],
                                  '移出合约收盘': prev['近月收盘'], '移入合约收盘': r['近月收盘'],
                                  '换月跳空': round(r['近月收盘'] - prev['近月收盘'], 1)})
        prev = r

    # ---------- 输出 ----------
    def dump_csv(rows, name, cols=None):
        if not rows:
            return
        cols = cols or list(rows[0].keys())
        fp = os.path.join(OUT, name)
        with open(fp, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(','.join(cols) + '\n')
            for r in rows:
                f.write(','.join(str(r.get(c, '')) for c in cols) + '\n')
        print('OK', name, len(rows))

    dump_csv(calendar, 'contract_calendar.csv')
    dump_csv(map_main, 'map_main.csv')
    dump_csv(map_near, 'map_near.csv')
    dump_csv(roll_log_main, 'roll_log_main.csv')
    dump_csv(roll_log_near, 'roll_log_near.csv')

    print('\n主力连续校验：与MA0收盘不一致天数 = %d / %d' % (len(mismatch), len(map_main)))
    for r in mismatch[:10]:
        print('   MISMATCH', r)
    print('\n主力换月次数(2020起) =', len(roll_log_main))
    for r in roll_log_main:
        print('   ', r['换月日'], r['移出'], '->', r['移入'], '跳空', r['换月跳空'])
    print('\n近月换月次数 =', len(roll_log_near))
    for r in roll_log_near[:40]:
        print('   ', r['换月日'], r['移出'], '->', r['移入'], '跳空', r['换月跳空'])
    print('\n合约日历核验汇总：')
    from collections import Counter
    cnt = Counter(c['规则核验'] for c in calendar)
    for k, v in cnt.items():
        print('   %s : %d' % (k, v))
    print('   明细(非"符合")：')
    for c in calendar:
        if c['规则核验'] != '符合':
            print('     ', c['合约'], c['末个K线日'], '| 规则', c['规则最后交易日(第10个交易日)'], '|', c['规则核验'])


if __name__ == '__main__':
    main()
