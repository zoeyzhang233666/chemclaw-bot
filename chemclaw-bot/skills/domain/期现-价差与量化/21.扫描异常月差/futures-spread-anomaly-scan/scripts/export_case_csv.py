# -*- coding: utf-8 -*-
"""导出案例用重点合约当日行情 CSV（多腿）"""
import io
import os
import sys

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASE = os.path.join(PKG, 'examples', '2026-10-20-化工四品种')
RAW = os.path.join(PKG, 'data', 'raw')

SYMS = ['MA2701', 'MA2704', 'MA2705', 'SA2701', 'SA2704', 'SA2705',
        'PP2701', 'PP2704', 'PP2705', 'TA2701', 'TA2704', 'TA2705',
        'MA2611', 'SA2611', 'PP2611', 'TA2611']

rows = []
for sym in SYMS:
    fp = os.path.join(RAW, sym + '.csv')
    if not os.path.exists(fp):
        print('missing', sym)
        continue
    txt = io.open(fp, encoding='utf-8-sig').read().strip()
    lines = [l for l in txt.split('\n') if l.strip()]
    hdr = lines[0].split(',')
    last = lines[-1].split(',')
    idx = {h: i for i, h in enumerate(hdr)}
    rows.append([sym, last[idx['date']], last[idx['close']], last[idx['settle']],
                 last[idx['volume']], last[idx['open_interest']]])

out = os.path.join(CASE, '重点合约当日行情.csv')
w = io.open(out, 'w', encoding='utf-8-sig', newline='')
w.write('合约,日期,收盘价,结算价,成交量,持仓量\n')
for r in rows:
    w.write(','.join(str(x) for x in r) + '\n')
w.close()
print('wrote', out, 'rows', len(rows))
