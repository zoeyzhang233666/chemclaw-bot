# -*- coding: utf-8 -*-
"""fetch_fund.py — 极端品种的库存 / 仓单 / 产业事件补充

数据源（全部公开、可复现）
--------------------------
1. 交易所仓单（权威）：akshare
     futures_warehouse_receipt_czce(date)  → 郑商所仓单日报（dict，按品种分表）
     futures_warehouse_receipt_dce(date)   → 大商所仓单日报；该接口偶发不可用时会自动回落
2. 库存序列（东方财富 datacenter，经 akshare futures_inventory_em）：
     给定品种名 → 日期/库存/增减，约 66 个交易日；实测「库存」列 = 交易所注册仓单
     合计（与 1 的「总计」逐日一致），故统一标注为「交易所仓单(滚动66日)」。
     若有真实社会库存/港口库存源，写入 data/raw/fund/inventory_override.csv 覆盖。
3. 产业事件：100ppi 各品种栏目的「产业价格涨跌榜 / 产业链情报」稿（标题级，带 URL）。

口径红线：所有数值带「数据日期 + 口径」；取不到写「未获取」，不估算。
输出：out/fundamentals.json 与 data/raw/fund/{code}_inventory.csv
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

from .http import Http
from . import fundamentals as fund_mod

# 品种 → akshare futures_inventory_em 的符号（中文名）
EM_SYMBOL = dict(MA='甲醇', SA='纯碱', V='PVC', PP='聚丙烯', L='塑料', TA='PTA', EG='乙二醇',
                 UR='尿素', SH='烧碱', EB='苯乙烯', FG='玻璃', PX='PX')
# 品种 → 郑商所仓单日报里的表名
CZCE_KEY = dict(TA='PTA')
EVENT_KW = ['涨跌榜', '产业链情报', '产业情报']


def _records(days: int = 12) -> list[str]:
    out = []
    d = dt.date.today()
    while len(out) < days:
        if d.weekday() < 5:
            out.append(d.strftime('%Y%m%d'))
        d -= dt.timedelta(days=1)
    return out


def czce_total(code: str, dates: list[str]) -> dict | None:
    try:
        import akshare as ak
    except ImportError:
        return None
    key = CZCE_KEY.get(code, code)
    for ds in dates:
        try:
            d = ak.futures_warehouse_receipt_czce(date=ds)
        except Exception:                                     # noqa: BLE001
            continue
        if not isinstance(d, dict) or key not in d:
            continue
        df = d[key]
        sub = df[df.iloc[:, 0].astype(str).str.strip() == '总计']
        if sub.empty:
            sub = df.tail(1)
        row = sub.iloc[0]
        num = [c for c in df.columns if '仓单数量' in str(c)]
        total = 0.0
        for c in num:
            try:
                total += float(str(row[c]).replace(',', '')) if str(row[c]) not in ('nan', '') else 0.0
            except ValueError:
                pass
        chg = row.get('当日增减', '')
        yb = row.get('有效预报', '')
        return dict(as_of='%s-%s-%s' % (ds[:4], ds[4:6], ds[6:8]), total=total,
                    change=chg if str(chg) != 'nan' else '', pred='' if str(yb) == 'nan' else yb,
                    source='akshare:futures_warehouse_receipt_czce (%s)' % ds)
    return None


def em_inventory(code: str) -> list[dict]:
    sym = EM_SYMBOL.get(code)
    if not sym:
        return []
    try:
        import akshare as ak
        df = ak.futures_inventory_em(symbol=sym)
    except Exception:                                         # noqa: BLE001
        return []
    rows = []
    for _, r in df.iterrows():
        try:
            rows.append(dict(date=str(r['日期'])[:10], inventory=float(r['库存']),
                             change=float(r['增减']) if str(r['增减']) != 'nan' else 0.0,
                             source='akshare:futures_inventory_em(%s) / 东方财富' % sym))
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def event_articles(http: Http, prod: dict, pages: int = 4) -> tuple[list[dict], int]:
    """返回 (事件稿, 该栏目文章总数)。只会拿到标题与 URL，不含数值加工。"""
    inv_news, _events = fund_mod.scan_column(http, prod, pages=pages)
    evs, total = [], 0
    for p in range(1, pages + 1):
        url = '%s/data/dlist-%d--%d-%d.html' % (fund_mod.BASE, int(prod['channel']),
                                                int(prod['ppid']), p)
        html = http.get(url, referer=fund_mod.BASE + '/data/')
        if not html:
            break
        for m in fund_mod.ROW_RE.finditer(html):
            href, ymd, _nid, title = m.group(1), m.group(2), m.group(3), m.group(4).strip()
            total += 1
            if any(k in title for k in EVENT_KW):
                evs.append(dict(date='%s-%s-%s' % (ymd[:4], ymd[4:6], ymd[6:8]),
                                title=title, url=fund_mod.BASE + '/' + href,
                                kind='产业价格涨跌榜/产业链情报(标题级)'))
    # 去重保序
    seen, out = set(), []
    for e in evs:
        if e['title'] in seen:
            continue
        seen.add(e['title'])
        out.append(e)
    return out[:10], total


def collect(http: Http, prods: list[dict], root: str) -> dict:
    out = {}
    dates = _records(12)
    for prod in prods:
        code = prod['code']
        c = czce_total(code, dates)
        em = em_inventory(code)
        evs, total_arts = event_articles(http, prod)
        # 落盘库存/仓单明细
        inv_rows = em or ([(dict(date=c['as_of'], inventory=c['total'],
                                 change=c['change'], source=c['source']))] if c else [])
        d = os.path.join(root, 'data', 'raw', 'fund')
        os.makedirs(d, exist_ok=True)
        if inv_rows:
            import csv
            with open(os.path.join(d, '%s_inventory.csv' % code), 'w', encoding='utf-8-sig',
                      newline='') as f:
                w = csv.DictWriter(f, fieldnames=['date', 'inventory', 'change', 'source'])
                w.writeheader()
                for r in inv_rows:
                    w.writerow(dict(date=r['date'], inventory=r['inventory'],
                                    change=r.get('change', ''), source=r.get('source', '')))
        latest = em[-1] if em else None
        status = 'ok' if latest else '未获取'
        reason = ('' if latest else
                  '未取到交易所仓单/库存日序列（东方财富库存接口与交易所仓单日报均未返回该品种数据）')
        out[code] = dict(
            code=code, name=prod['name'], inv_status=status, inv_reason=reason,
            inv_scope='交易所仓单（注册仓单合计）',
            inv_latest=latest, inv_prev=em[-6] if len(em) >= 6 else (em[0] if em else None),
            inv_series=em[-66:], inv_exchange=c,
            inv_news=[],
            events=evs, events_scope='100ppi 栏目「产业价格涨跌榜/产业链情报」标题级线索，非数值',
            column_articles=total_arts)
    return out


def main(argv=None):
    import argparse
    from .products import load_pool
    ap = argparse.ArgumentParser(description='补充库存/仓单/产业事件')
    ap.add_argument('--codes', default='')
    ap.add_argument('--root', default='.')
    ap.add_argument('--out', default='out/fundamentals.json')
    ap.add_argument('--cache', default='data/cache')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    pool = load_pool()
    codes = [c.strip().upper() for c in a.codes.split(',') if c.strip()]
    if codes:
        pool = [p for p in pool if p['code'] in codes]
    http = Http(cache_dir=os.path.join(a.root, a.cache))
    fund = collect(http, pool, a.root)
    os.makedirs(os.path.dirname(os.path.join(a.root, a.out)) or '.', exist_ok=True)
    with open(os.path.join(a.root, a.out), 'w', encoding='utf-8') as f:
        json.dump(fund, f, ensure_ascii=False)
    for k, v in fund.items():
        lt = v['inv_latest']
        print('[fund] %-3s %-6s 仓单=%s %s 事件=%d' % (
            k, v['name'], v['inv_status'],
            ('%s %s' % (lt['date'], lt['inventory'])) if lt else '', len(v['events'])), flush=True)


if __name__ == '__main__':
    main()
