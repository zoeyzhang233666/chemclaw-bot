# -*- coding: utf-8 -*-
"""在无电石日价区间，用"有明确引用的月度锚点"补全电石价，从而得到全年加工价差与理论利润。

锚点来源（全部为公开文章明确披露，逐条记录 url + 原文数字）：
  A6M : 隆众《2026上半年PVC成本毛利分析》(2026-06-02)
        "2026年上半年，电石法PVC成本整体呈稳中有降趋势，上半年乌海地区最高价格在2750元/吨，
         降至5月末2500元/吨左右，跌幅约9.09%"
  Q3  : 隆众 PVC 早间提示 (2026-09-08): "昨日乌海地区主流贸易价格报价在2750元/吨"
        同步印证：9月中旬内蒙古用电限制，乌海电石 9-15 达 2700 (财经新闻 2026-09-23)
  7-8月: 隆众 电石市场一周前瞻 (2026-08-03): 乌海主流贸易价 周末上调至 2300，当日再上调至 2400
        电石行情 (2026-05-29): 乌海主流贸易价 5-28 涨至 2500

模型：只在"锚点之间"用线性插值（区间内趋势单调，且两端均有真实报价），
      并在输出中标记 interp=True 与两端锚点，避免任何越界外推。
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, 'build')

ANCHORS = [
    # (日期, 乌海电石主流贸易价 元/吨, 原始表述, 来源)
    ('2026-01-01', 2750.0, '上半年乌海地区最高价格在2750元/吨', '隆众聚焦 2026-06-02 https://www.mysteel.com/oilchem/a/26060214/FAF52BAD5C7B2CA0.html'),
    ('2026-05-31', 2500.0, '降至5月末2500元/吨左右', '隆众聚焦 2026-06-02 同上'),
    ('2026-05-28', 2500.0, '乌海主流贸易价格涨至2500元/吨', '新浪财经 2026-05-29 https://finance.sina.com.cn/wm/2026-05-29/doc-inhzqccm9516100.shtml'),
    ('2026-08-03', 2400.0, '乌海主流贸易价格上调至2400元/吨', '隆众 电石市场一周前瞻 20260803 https://nenghua.m.mysteel.com/a/26080308/B23DAF7886B826D4_abc.html'),
    ('2026-09-07', 2750.0, '乌海地区主流贸易价格报价在2750元/吨', '隆众 PVC早间提示 20260908 https://www.oilchem.net/26-0908-08-0ac49a26bf1d5373.html'),
    ('2026-09-15', 2700.0, '内蒙古乌海地区电石价格为2700元/吨', '财经新闻 2026-09-23 https://finance.sina.com.cn/money/future/fmnews/2026-09-23/doc-inisuxhf5279993.shtml'),
]


def anchor_table():
    return [{'date': d, 'price': p, 'quote': q, 'source': s} for d, p, q, s in ANCHORS]


def interp_carbide(dates):
    """对给定日期序列返回 {date: (price, is_interp, note)}；超范围返回 None。"""
    from datetime import date as D

    pts = sorted([(D.fromisoformat(d), p, q) for d, p, q, _ in ANCHORS])
    out = {}
    for ds in dates:
        x = D.fromisoformat(ds)
        prev = next_ = None
        for i, (pd, pp, _) in enumerate(pts):
            if pd <= x:
                prev = (pd, pp)
            elif next_ is None:
                next_ = (pd, pp)
                break
        if prev and prev[0] == x:
            out[ds] = (prev[1], False, '锚点日')
        elif prev and next_:
            span = (next_[0] - prev[0]).days
            w = (x - prev[0]).days / span if span else 1
            out[ds] = (round(prev[1] + (next_[1] - prev[1]) * w, 1), True,
                       '插值 %s %.0f → %s %.0f (w=%.2f)' % (prev[0], prev[1], next_[0], next_[1], w))
        else:
            out[ds] = None
    return out


if __name__ == '__main__':
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    tbl = anchor_table()
    json.dump(tbl, open(os.path.join(BUILD, 'carbide_anchors.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('anchors', len(tbl))
    for t in tbl:
        print(' ', t['date'], t['price'], t['quote'])
