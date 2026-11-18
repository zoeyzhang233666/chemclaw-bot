# -*- coding: utf-8 -*-
"""合约识别与匹配：把“近月/远月/主力/次月/月份组合/指定合约”解析成具体合约代码。

用法
----
    # 1) 列出某品种当前全部挂牌合约（按交割月升序，附价格/持仓/距交割天数）
    python scripts/match_contracts.py list --product SA --rawdir data/raw

    # 2) 解析一对合约（结构化输入）
    python scripts/match_contracts.py pair --product SA --rawdir data/raw --a 2612 --b 2701

    # 3) 解析自然语言别名
    python scripts/match_contracts.py pair --product SA --rawdir data/raw --a 近月 --b 远月
    python scripts/match_contracts.py pair --product SA --rawdir data/raw --by-gap 1 --nth 1

    # 4) 校验一对完整代码
    python scripts/match_contracts.py check --a SA2612 --b SA2701 --rawdir data/raw

设计要点
--------
* 合约代码一律 YYMM 四位（SA2701 = 2027年1月交割），不猜“26年1月”还是“2026年”。
* “近月/远月”的判定**只依据交割月与当天在该合约上有真实盘面**（持仓量 >= min-oi），
  接近交割、已经没有量的合约不会被误当成“近月”。
* 绝不返回一个当天没在盘面上出现的合约代码。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import spreadlib as S  # noqa: E402

ALIASES = {
    '近月': 'near', '最近月': 'near', '第一腿': 'near', '近端': 'near', '当月': 'near',
    '远月': 'far', '最远月': 'far', '第二腿': 'far', '远端': 'far',
    '主力': 'main', '主力合约': 'main',
    '次月': 'next', '下一个': 'next',
}
CN_MONTH = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
            '十': 10, '十一': 11, '十二': 12}


def normalize(code: str, product: str) -> str:
    c = str(code).strip().upper().replace(' ', '')
    if re.fullmatch(r'\d{3,4}', c):
        c = c if len(c) == 4 else '2' + c
        return product.upper() + c
    m = re.fullmatch(r'([A-Z]+)(\d{3,4})', c)
    if m:
        yymm = m.group(2)
        return m.group(1) + (yymm if len(yymm) == 4 else '2' + yymm)
    raise ValueError(f'无法识别的合约代码: {code!r}')


def resolve(book: S.ContractBook, ref: str, date: dt.date, min_oi: float = 1000.0) -> str:
    product = book.product
    key = str(ref).strip()
    if key in ALIASES:
        key = ALIASES[key]
    listed = book.listed_on(date, min_oi=min_oi)
    if not listed:
        raise ValueError(f'{S.iso(date)} 没有任何合约达到持仓量门槛 {min_oi}')
    if key == 'near':
        return listed[0]
    if key == 'far':
        return listed[-1]
    if key == 'next':
        return listed[1] if len(listed) > 1 else listed[-1]
    if key == 'main':
        return max(listed, key=lambda c: book.series[c].oi_at(date) or 0)
    m = re.fullmatch(r'第?([一二三四五六七八九十]{1,2})月', key)
    if m:
        month = CN_MONTH[m.group(1)]
        cand = [c for c in listed if S.code_to_delivery(c)[1] == month]
        if not cand:
            raise ValueError(f'{S.iso(date)} 挂牌合约里没有 {month} 月合约（当前：{listed}）')
        return cand[0]
    code = normalize(key, product)
    s = book.series.get(code)
    if s is None:
        raise ValueError(f'合约 {code} 不在已抓取数据中（可能不存在/已摘牌/未抓取）')
    if s.quote(date) is None:
        raise ValueError(f'合约 {code} 在 {S.iso(date)} 没有报价（尚未挂牌或已摘牌）')
    return code


def pick_by_gap(book: S.ContractBook, date: dt.date, gap: int, nth: int,
                min_oi: float = 1000.0):
    """按“日历间隔 gap 个月”挑第 nth 组（1 = 最近到期的一对）。"""
    listed = book.listed_on(date, min_oi=min_oi)
    pairs = [(a, b) for a in listed for b in listed if S.month_pair_gap(a, b) == gap]
    pairs.sort(key=lambda p: (S.code_to_delivery(p[0]), S.code_to_delivery(p[1])))
    if not pairs:
        raise ValueError(f'当前挂牌合约里找不到间隔 {gap} 个月的组合')
    if not 1 <= nth <= len(pairs):
        raise ValueError(f'nth={nth} 超范围，当前有 {len(pairs)} 组：{pairs}')
    return pairs[nth - 1]


def describe(book: S.ContractBook, code: str, date: dt.date) -> dict:
    s = book.series[code]
    y, m = S.code_to_delivery(code)
    return {
        'contract': code, 'delivery': f'{y}年{m}月', 'price_close': s.quote(date),
        'settle': s.settle[s.idx[date]] if date in s.idx else None,
        'oi': s.oi_at(date), 'dtd_trading_days': S.trading_days_between(date, S.delivery_date(y, m)),
        'first_date': S.iso(s.first_date()), 'last_date': S.iso(s.last_date()),
        'rows': len(s.dates),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='期货合约识别与匹配')
    ap.add_argument('cmd', choices=['list', 'pair', 'check'])
    ap.add_argument('--product', default=None, help='品种代码（默认从 --a 推断）')
    ap.add_argument('--rawdir', default=os.path.join(os.path.dirname(HERE), 'data', 'raw'))
    ap.add_argument('--date', default=None, help='基准日 YYYY-MM-DD（默认数据最后一天）')
    ap.add_argument('--a', default=None)
    ap.add_argument('--b', default=None)
    ap.add_argument('--by-gap', type=int, default=None, help='按日历间隔月数选组合')
    ap.add_argument('--nth', default='1', help='配合 --by-gap，取第几组，如 1 或 1,2')
    ap.add_argument('--min-oi', type=float, default=1000.0, help='视为“有盘面”的最低持仓量')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    src = args.a or args.b or 'SA'
    m0 = re.match(r'^[A-Za-z]+', src)
    product = (args.product or (m0.group(0) if m0 else 'SA')).upper().strip()
    book = S.ContractBook.from_dir(args.rawdir, product)
    if not book.series:
        print(f'[错误] {args.rawdir} 下没有 {product} 的合约数据，请先运行 fetch_futures.py',
              file=sys.stderr)
        return 2
    date = S.parse_date(args.date) if args.date else book.latest_trading_date()

    if args.cmd == 'list':
        listed = book.listed_on(date, min_oi=args.min_oi)
        rows = [describe(book, c, date) for c in listed]
        if args.json:
            print(json.dumps({'product': product, 'date': S.iso(date), 'listed': rows},
                             ensure_ascii=False, indent=1))
            return 0
        print(f'{product} 于 {S.iso(date)} 可交易合约（持仓量>={args.min_oi:.0f}）共 {len(rows)} 个：')
        print(f'{"合约":<8}{"交割":<10}{"收盘":>8}{"持仓":>12}{"距交割(交易日)":>14}')
        for r in rows:
            print(f'{r["contract"]:<8}{r["delivery"]:<10}{r["price_close"]:>8.0f}'
                  f'{r["oi"]:>12,.0f}{r["dtd_trading_days"]:>14d}')
        return 0

    try:
        if args.cmd == 'pair':
            if args.by_gap is not None:
                nth = int(str(args.nth).split(',')[0])
                a, b = pick_by_gap(book, date, args.by_gap, nth, args.min_oi)
            else:
                if not (args.a and args.b):
                    raise ValueError('需要 --a 与 --b（或使用 --by-gap）')
                a = resolve(book, args.a, date, args.min_oi)
                b = resolve(book, args.b, date, args.min_oi)
            out = {'date': S.iso(date), 'a': describe(book, a, date), 'b': describe(book, b, date),
                   'formula': f'月差 = P({a}) - P({b})',
                   'gap_months': S.month_pair_gap(a, b),
                   'order_ok': S.code_to_delivery(a) < S.code_to_delivery(b)}
            if args.json:
                print(json.dumps(out, ensure_ascii=False, indent=1))
            else:
                print(f'基准日 {out["date"]}')
                for k in ('a', 'b'):
                    d = out[k]
                    print(f'  {k.upper()}: {d["contract"]}（{d["delivery"]}）收盘 {d["price_close"]:.0f} '
                          f'持仓 {d["oi"]:,.0f} 距交割 {d["dtd_trading_days"]} 个交易日')
                print(f'  {out["formula"]}；日历间隔 {out["gap_months"]} 个月；近月在前={out["order_ok"]}')
            return 0

        a, b = normalize(args.a, product), normalize(args.b, product)
        miss = [c for c in (a, b) if c not in book.series]
        if miss:
            print(f'[错误] 合约不存在: {miss}', file=sys.stderr)
            return 1
        print(f'OK {a} / {b} 均在数据中；月差 = P({a}) - P({b})')
        return 0
    except ValueError as e:
        print(f'[错误] {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
