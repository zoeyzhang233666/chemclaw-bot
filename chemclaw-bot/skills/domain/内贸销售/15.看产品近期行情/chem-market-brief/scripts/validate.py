# -*- coding: utf-8 -*-
"""research.json 契约校验。

用法：
  python validate.py research.json
  python validate.py research.json --strict    # warning 也当错误

规则分三级：
  ERROR  结构错误 / 会产出误导性数字 —— 必须修
  WARN   缺字段但可降级 —— 会以“缺口”呈现，建议补
  INFO   提示
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

WHY = {
    'meta.product': '没有品种名，报告无法命名',
    'meta.asof': '没有基准日，读者无法判断数据新旧',
    'spot': '没有现货报价，就无法回答“当前价是多少”',
    'spot.region': '缺地区，报价不可用',
    'spot.product': '缺规格（品位/执行标准），报价不可用',
    'spot.tax': '未标含税与否，报价不可比',
    'spot.date': '缺日期，报价不可用',
    'spot.src': '缺来源，报价不可引用',
    'futures.series': '没有序列，走势/分位/异常波动三块都做不了',
    'gaps': '没有缺口登记，等于宣称数据完整',
    'sources': '没有来源清单，数字不可回溯',
}


def check(R, base_dir='.'):
    E, W, I = [], [], []

    def err(m, key=None):
        E.append(m + ('　（%s）' % WHY[key] if key and key in WHY else ''))

    def warn(m, key=None):
        W.append(m + ('　（%s）' % WHY[key] if key and key in WHY else ''))

    # ---------- meta
    meta = R.get('meta') or {}
    for k in ('product', 'asof'):
        if not meta.get(k):
            err('meta.%s 缺失' % k, 'meta.' + k)
    if meta.get('asof') and not common.parse_date(meta['asof']):
        err('meta.asof 不是可解析日期：%r' % meta['asof'])
    if not meta.get('region'):
        warn('meta.region 缺失，报告将标注为“全国”')
    if not meta.get('spec'):
        warn('meta.spec 缺失（如“重质 ≥99.2%”“GB/T 210-2022 II 类”）；规格不明会导致报价不可比')
    if not meta.get('unit'):
        warn('meta.unit 缺失，默认“元/吨”')

    # ---------- futures
    fut = R.get('futures') or {}
    if fut.get('series'):
        p = fut['series'] if os.path.isabs(fut['series']) else os.path.join(base_dir, fut['series'])
        if not os.path.exists(p):
            err('futures.series 指向的文件不存在：%s' % p, 'futures.series')
        else:
            try:
                rows = common.load_series(p)
                if len(rows) < 30:
                    warn('序列只有 %d 行，不足以算 1 年分位与异常波动' % len(rows))
                if meta.get('asof'):
                    after = [r for r in rows if r['d'] > meta['asof']]
                    if after:
                        warn('序列中有 %d 行晚于 asof(%s)，assemble 会自动截断' % (len(after), meta['asof']))
                    if rows[-1]['d'] < meta['asof']:
                        I.append('序列末值 %s 早于 asof %s（周末/节假日属正常）' % (rows[-1]['d'], meta['asof']))
                # 单位量级检查：纯碱元/吨约 1000–3500；若出现 <1 可能是元/千克或美元
                last = rows[-1]['c']
                if last < 1:
                    warn('序列末值 %.4f 量级异常，确认单位（元/吨 vs 元/千克 vs 美元/吨）' % last)
            except Exception as e:
                err('序列解析失败：%s' % e)
    else:
        warn('未配置 futures.series；若该品种无场内期货可忽略，否则走势与分位将留空', 'futures.series')

    # ---------- spot
    spots = R.get('spot') or []
    if not spots:
        err('spot 数组为空', 'spot')
    for i, s in enumerate(spots):
        tag = 'spot[%d]（%s/%s）' % (i, s.get('region', '?'), s.get('product', '?'))
        if common.num(s.get('lo')) is None and common.num(s.get('hi')) is None and common.num(s.get('value')) is None:
            err('%s 没有价格数字（lo/hi/value 都为空）' % tag)
        for k in ('region', 'product', 'tax', 'basis', 'date', 'src'):
            if not s.get(k):
                warn('%s 缺 %s' % (tag, k), 'spot.' + k)
        d = s.get('date')
        if d and common.parse_date(d) and meta.get('asof'):
            age = common.days_between(d, meta['asof'])
            if age is not None and age > 30:
                warn('%s 的报价日期 %s 距 asof %s 已 %d 天，现货是逐日报价品种' % (tag, d, meta['asof'], age))
        if s.get('tax') and '含税' not in str(s['tax']) and '不含' not in str(s['tax']):
            warn('%s 的 tax 字段未明确含税/不含税：%r' % (tag, s['tax']))

    # ---------- anchor
    a = R.get('anchor')
    if a:
        if common.num(a.get('value')) is None:
            err('anchor.value 不是数字')
        if a.get('date') and common.parse_date(a['date']) and meta.get('asof'):
            age = common.days_between(a['date'], meta['asof'])
            if age is not None and age > 7:
                I.append('现货锚取 %s，距 asof 已 %d 天' % (a['date'], age))

    # ---------- 区间价差
    sp = R.get('spread_base') or {}
    dates = {}
    for s in spots:
        dates.setdefault(s.get('date'), set()).add(s.get('product'))
    multi = [d for d, v in dates.items() if d and len([s for s in spots if s.get('date') == d]) >= 2]
    if not multi:
        warn('没有任何“同一天 ≥2 个地区”的报价，区域价差将留空（跨日期相减会制造假价差）')
    else:
        mix = {}
        for s in spots:
            mix.setdefault(s.get('date'), set()).add(s.get('product'))
        for d, specs in mix.items():
            if len(specs) > 1:
                warn('日期 %s 上有多规格混排（%s），算价差前需按同规格分组' % (d, '、'.join(str(x) for x in specs)))

    # ---------- 事件
    for i, e in enumerate(R.get('events') or []):
        tag = 'events[%d]（%s）' % (i, e.get('date', '?'))
        if not e.get('date'):
            err('%s 缺 date' % tag)
        if not e.get('title'):
            err('%s 缺 title' % tag)
        if not e.get('src'):
            warn('%s 缺 src，事件不可回溯' % tag)
        if not e.get('detail'):
            warn('%s 缺 detail（“当时发生了什么”会显示为空）' % tag)
        if meta.get('asof') and e.get('date') and e['date'] > meta['asof']:
            err('%s 的日期晚于 asof，属未来事件' % tag)

    # ---------- 缺口 / 来源
    if not (R.get('gaps')):
        warn('gaps 为空：如果确实全部字段有来源，请保留一条说明；否则逐条登记缺口', 'gaps')
    for i, g in enumerate(R.get('gaps') or []):
        if not g.get('item') or not g.get('detail'):
            err('gaps[%d] 缺 item 或 detail' % i)
        if g.get('status') not in ('缺口', '口径冲突', '待更新'):
            warn('gaps[%d].status=%r，建议用 缺口 / 口径冲突 / 待更新' % (i, g.get('status')))
    if not (R.get('sources')):
        warn('sources 为空，数字不可回溯', 'sources')
    for i, s in enumerate(R.get('sources') or []):
        if not s.get('name'):
            err('sources[%d] 缺 name' % i)
        u = s.get('url') or ''
        if u and not u.startswith('http'):
            warn('sources[%d].url 不是 http 链接：%s' % (i, u))

    # ---------- 事实卡方向性表述
    def scan(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                scan(v, path + '.' + k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                scan(v, path + '[%d]' % i)
        elif isinstance(obj, str):
            if path.endswith('.q'):
                return
            for b in common.banned_hits(obj):
                err('出现方向性表述「%s」于 %s' % (b, path))
    scan(R, 'root')

    # ---------- 建议
    if not (R.get('facts') or []):
        W.append('facts 为空：销售事实卡会留空，客户对话时缺少可用弹药')
    if not (R.get('talk') or []):
        W.append('talk 为空：客户问答会留空')
    if not (R.get('margins') or []):
        W.append('margins 为空：无法判断“亏损为什么还不减产”')
    if not (R.get('balance') or []):
        W.append('balance 为空：缺少开工/库存/产量，无法解释供给端')
    return E, W, I


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('research')
    ap.add_argument('--strict', action='store_true')
    a = ap.parse_args()
    base = os.path.dirname(os.path.abspath(a.research))
    R = common.load_json(a.research)
    E, W, I = check(R, base)
    for x in E:
        print('[ERROR]', x)
    for x in W:
        print('[WARN ]', x)
    for x in I:
        print('[INFO ]', x)
    print('== %d error ｜ %d warn ｜ %d info' % (len(E), len(W), len(I)))
    if E or (a.strict and W):
        sys.exit(1)


if __name__ == '__main__':
    main()
