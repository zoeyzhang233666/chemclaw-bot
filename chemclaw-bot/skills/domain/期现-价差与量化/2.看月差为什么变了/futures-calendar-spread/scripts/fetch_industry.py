# -*- coding: utf-8 -*-
"""抓取产业侧外部数据：仓单/库存（东方财富 RPT_FUTU_STOCKDATA）、现货报价（生意社 100ppi）。

用法
----
    python scripts/fetch_industry.py warrant SA \
        --out data/external/warrant_SA.csv --meta data/external/warrant_SA.meta.json

    python scripts/fetch_industry.py spot SA \
        --out data/external/spot_SA.csv --meta data/external/spot_SA.meta.json

说明
----
* 仓单是**品种级日报**（交易所仓单/期货库存），单位“张”，不是“某两个合约的仓单”。
  品种级数据绝不能拆成“近月合约仓单 / 远月合约仓单”——月差解释里只能作总量背景。
* 接口历史深度有限（当前约 3 个月），脚本把实际覆盖区间写进 meta，报告必须原样引用。
* 不做任何插值/回填：缺的日子就是缺。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
try:
    ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
except Exception:  # pragma: no cover
    pass

SPOT_URLS = {'SA': 'https://www.100ppi.com/mprice/plist-1-533-1.html'}


def _get(url: str, referer: str = 'https://data.eastmoney.com/') -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': referer, 'Accept': '*/*'})
    with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310
        return r.read()


def fetch_warrant_em(product: str, page_size: int = 500) -> list:
    """东方财富数据中心 RPT_FUTU_STOCKDATA（转载交易所仓单/期货库存日报）。"""
    params = {
        'reportName': 'RPT_FUTU_STOCKDATA',
        'columns': 'SECURITY_CODE,TRADE_DATE,ON_WARRANT_NUM,ADDCHANGE,UNIT',
        'filter': f'(SECURITY_CODE="{product.upper()}")',
        'pageNumber': '1', 'pageSize': str(page_size),
        'sortColumns': 'TRADE_DATE', 'sortTypes': '1', 'source': 'WEB', 'client': 'WEB',
    }
    url = 'https://datacenter-web.eastmoney.com/api/data/v1/get?' + urllib.parse.urlencode(params)
    j = json.loads(_get(url).decode('utf-8', 'ignore'))
    rows = []
    for r in (j.get('result') or {}).get('data') or []:
        try:
            rows.append({'date': str(r['TRADE_DATE'])[:10], 'value': float(r['ON_WARRANT_NUM']),
                         'unit': r.get('UNIT') or '张', 'change': r.get('ADDCHANGE')})
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def fetch_warrant(product: str) -> tuple:
    rows = fetch_warrant_em(product)
    src = ('东方财富数据中心 RPT_FUTU_STOCKDATA（转载交易所仓单/期货库存日报）| '
           f'https://data.eastmoney.com/ifdata/kcsj.html?va={product.upper()}')
    return rows, src


def fetch_spot(product: str) -> tuple:
    """生意社现货报价（市场价），同一天取中位数。

    行结构：品种/规格/产地/价格/报价类型/交货地/交易商/[VIP]/日期
    """
    url = SPOT_URLS.get(product.upper())
    if not url:
        raise SystemExit(f'未配置 {product} 的现货页面')
    html = _get(url, referer='https://www.100ppi.com/').decode('utf-8', 'ignore')
    txt = re.sub(r'<script[\s\S]*?</script>', ' ', html)
    txt = re.sub(r'<[^>]+>', '\n', txt)
    lines = [x.strip() for x in txt.split('\n') if x.strip()]
    rows = []
    for i, ln in enumerate(lines):
        m = re.fullmatch(r'(\d+(?:\.\d+)?)元/吨', ln)
        if not m or i < 3:
            continue
        if '纯碱' not in lines[i - 3]:
            continue
        dm = None
        for k in range(i + 1, min(i + 7, len(lines))):
            mm = re.fullmatch(r'(20\d\d-\d\d-\d\d)', lines[k])
            if mm:
                dm = mm.group(1)
                break
        if dm:
            rows.append({'date': dm, 'value': float(m.group(1))})
    by_date = {}
    for r in rows:
        by_date.setdefault(r['date'], []).append(r['value'])
    out = []
    for d, vs in sorted(by_date.items()):
        vs.sort()
        out.append({'date': d, 'value': vs[len(vs) // 2], 'unit': '元/吨', 'n_quotes': len(vs),
                    'min': vs[0], 'max': vs[-1]})
    return out, f'生意社 100ppi 报价中心 | {url}'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='抓取仓单/库存与现货参考价')
    ap.add_argument('kind', choices=['warrant', 'spot'])
    ap.add_argument('product')
    ap.add_argument('--out', required=True)
    ap.add_argument('--meta', default=None)
    args = ap.parse_args(argv)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    now = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if args.kind == 'warrant':
        rows, src = fetch_warrant(args.product)
        if not rows:
            print(f'[失败] {args.product} 没有仓单数据', file=sys.stderr)
            return 1
        with open(args.out, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['date', 'value', 'unit', 'change'])
            for r in rows:
                w.writerow([r['date'], r['value'], r['unit'], r['change']])
        meta = {'kind': 'warrant', 'product': args.product.upper(), 'source': src,
                'fetched_at': now, 'unit': rows[0]['unit'], 'n': len(rows),
                'first': rows[0]['date'], 'last': rows[-1]['date'], 'current': rows[-1]['value'],
                'granularity': '品种级（交易所口径），不是单合约仓单，不可拆分为近月/远月',
                'caveats': ['历史深度有限（仅覆盖接口返回区间）',
                            '纯碱以厂库交割为主，仓单量小，不代表社会库存',
                            '交易所仓单与产业口径“厂库+社会库存”不可比，必须分列']}
        if args.meta:
            with open(args.meta, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
        print(f'[成功] 仓单 {args.product}: {len(rows)} 天 {rows[0]["date"]}~{rows[-1]["date"]} '
              f'最新 {rows[-1]["value"]:.0f}{rows[-1]["unit"]} -> {args.out}')
    else:
        rows, src = fetch_spot(args.product)
        if not rows:
            print('[失败] 没有解析到现货报价', file=sys.stderr)
            return 1
        with open(args.out, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['date', 'value', 'unit', 'n_quotes', 'min', 'max'])
            for r in rows:
                w.writerow([r['date'], r['value'], r['unit'], r['n_quotes'], r['min'], r['max']])
        if args.meta:
            with open(args.meta, 'w', encoding='utf-8') as f:
                json.dump({'kind': 'spot', 'product': args.product.upper(), 'source': src,
                           'fetched_at': now, 'n': len(rows), 'first': rows[0]['date'],
                           'last': rows[-1]['date'],
                           'caveats': ['厂家/市场报价中位，非交易所标准仓单价',
                                       '不同企业、规格、区域差异大，仅用于现货水平与基差方向核对']},
                          f, ensure_ascii=False, indent=1)
        print(f'[成功] 现货 {args.product}: {len(rows)} 天 {rows[0]["date"]}~{rows[-1]["date"]} '
              f'最新 {rows[-1]["value"]:.0f} 元/吨（{rows[-1]["n_quotes"]} 条报价中位）-> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
