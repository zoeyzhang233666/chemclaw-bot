# -*- coding: utf-8 -*-
"""verify_jumps.py — 对可疑跳变日回原文核实（保留证据）。

读取 data/raw/100ppi_methanol_benchmark_daily.csv，对 |日变动| > 阈值的日期抓取原文
（正文，若可用）并记录：标题价格、正文中的价格语句、是否与标题一致、判定。
判定规则（保守）：
  - 正文价格语句与标题一致 -> 判定 source-confirmed（就源确认，非解析错误）
  - 正文不可得            -> 判定 title-only（仅标题可得，无法进一步核实）
  - 正文与标题不一致      -> 判定 conflict
"""
import csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_100ppi_methanol import http_get, VALUE

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # 工程根目录（含 data/）
RAW = os.path.join(ROOT, 'data', 'raw')
rows = list(csv.DictReader(open(os.path.join(RAW, '100ppi_methanol_benchmark_daily.csv'),
                                encoding='utf-8-sig')))
by_date = {r['date']: r for r in rows}
prev = None
jumps = []
for r in rows:
    if prev and float(prev['price']) > 0:
        chg = (float(r['price']) - float(prev['price'])) / float(prev['price'])
        if abs(chg) > 0.08:
            jumps.append((prev, r, chg))
    prev = r

out = []
for a, b, chg in jumps:
    rec = {'prev_date': a['date'], 'date': b['date'], 'prev_price': float(a['price']),
           'price': float(b['price']), 'chg': round(chg, 4), 'title': b['title'],
           'source_url': b['source_url']}
    try:
        t = http_get(b['source_url'], ref='https://me.100ppi.com/news/list--1217-1.html')
        body = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', '', t)
        body = re.sub(r'<[^>]+>', ' ', body)
        body = re.sub(r'&nbsp;|\s+', ' ', body)
        m = re.search(r'生意社甲醇基准价为([\d,]+\.?\d*)\s*元/吨', body)
        near = ''
        if m:
            near = body[max(0, m.start() - 160):m.end() + 90].strip()
        rec['body_found'] = bool(m)
        rec['body_price'] = float(m.group(1).replace(',', '')) if m else None
        rec['body_excerpt'] = near
        if m:
            rec['verdict'] = ('source-confirmed'
                              if abs(rec['body_price'] - rec['price']) < 1e-6 else 'conflict')
        else:
            rec['verdict'] = 'title-only'
    except Exception as e:                                    # noqa: BLE001
        rec['verdict'] = 'title-only'
        rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:120])
    print('%-12s %-11s %8.2f -> %8.2f  %6.2f%%  %s' % (rec['date'], rec['verdict'], rec['prev_price'],
                                                       rec['price'], chg * 100,
                                                       (rec.get('body_excerpt') or '')[:90]))
    out.append(rec)

json.dump(out, open(os.path.join(RAW, 'jump_verification.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\n->', os.path.join(RAW, 'jump_verification.json'), 'n =', len(out))
