# -*- coding: utf-8 -*-
"""研究稿 research.json -> 看板数据包 data.json（派生物全部在这里算，HTML/Excel 只消费）。

用法：
  python assemble.py research.json --out build/data.json
  python assemble.py research.json            # 默认写到 <research 同级>/build/data.json

核心改造点（相对单品种脚本）：产品名、规格、地区、周期、成本线、事件全部来自 research.json，
脚本里不含任何品种专有字面量。任何缺失字段不会报错，而是转成“缺口”并保留在 gaps 里，
保证换一个品种、数据不全时也能出一份诚实的报告。
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

WINDOWS = [('7d', 7), ('30d', 30), ('90d', 90), ('1y', 365), ('3y', 1095)]
RANK_WINDOWS = [('1y', 365), ('3y', 1095), ('5y', 1825)]


def build(R, base_dir='.'):
    meta_in = R.get('meta') or {}
    product = meta_in.get('product') or '未命名品种'
    asof = meta_in.get('asof') or datetime.date.today().isoformat()
    gaps = [dict(g) for g in (R.get('gaps') or [])]
    caveats = list(R.get('caveats') or [])
    sources = list(R.get('sources') or [])

    def gap(item, status, detail, impact='', fix=''):
        gaps.append({'item': item, 'status': status, 'detail': detail, 'impact': impact, 'fix': fix})

    # ---------------------------------------------------------------- 期货序列
    fut_meta = dict(R.get('futures') or {})
    rows = []
    fp = fut_meta.get('series')
    if fp:
        cand = fp if os.path.isabs(fp) else os.path.join(base_dir, fp)
        if os.path.exists(cand):
            try:
                rows = common.load_series(cand)
            except Exception as e:
                gap('期货日线', '缺口', '序列文件解析失败：%s（%s）' % (fp, e),
                    '无法给出走势与分位，只能报现货点价', '检查 raw/*_daily.json 格式')
        else:
            gap('期货日线', '缺口', '序列文件不存在：%s' % cand,
                '无法给出走势与分位，只能报现货点价', '先跑 fetch_futures.py')
    else:
        gap('期货序列', '缺口', 'research.json 未配置 futures.series（该品种可能没有场内期货）',
            '走势/分位/异常波动三块只能留空', '若有场内期货：跑 fetch_futures.py 并在 futures.series 指过去')

    last = None
    if rows:
        asof_d = common.parse_date(asof)
        if asof_d:
            rows = [r for r in rows if r['d'] <= asof]
        if not rows:
            gap('期货日线', '缺口', '序列中没有 <= asof(%s) 的数据' % asof, '全部派生指标不可算', '延长序列或改 asof')
        else:
            last = rows[-1]
            if meta_in.get('futures_close') and abs(common.num(meta_in['futures_close']) - last['c']) > 0.5:
                caveats.append('research.json 手写的期货收盘 %s 与序列末值 %s 不一致，看板以序列为准。'
                               % (common.fmt(common.num(meta_in['futures_close'])), common.fmt(last['c'])))

    # ---------------------------------------------------------------- 现货
    spots = []
    for i, s in enumerate(R.get('spot') or []):
        lo, hi = common.num(s.get('lo')), common.num(s.get('hi'))
        if lo is None and hi is None:
            lo = hi = common.num(s.get('value'))
        if lo is None:
            gap('现货报价', '缺口', '第 %d 条现货缺少价格数字（%s / %s）' % (i + 1, s.get('region'), s.get('product')),
                '该条不进入现货表', '补 lo/hi 或 value')
            continue
        if hi is None:
            hi = lo
        if lo > hi:
            lo, hi = hi, lo
        missing = [k for k in ('region', 'product', 'tax', 'basis', 'date', 'src') if not s.get(k)]
        if missing:
            caveats.append('现货行「%s / %s」缺少 %s，引用时须补全后再对外报价。'
                           % (s.get('region', '?'), s.get('product', '?'), '、'.join(missing)))
        spots.append({
            'region': s.get('region') or '未标注地区',
            'sub': s.get('sub') or '',
            'product': s.get('product') or '未标注规格',
            'lo': lo, 'hi': hi,
            'tax': s.get('tax') or '未标注',
            'basis': s.get('basis') or '未标注',
            'date': s.get('date') or '日期缺失',
            'conf': s.get('conf') or '中',
            'note': s.get('note') or '',
            'src': s.get('src') or '未标注来源',
            'single': (lo == hi),
        })
    if not spots:
        gap('现货报价', '缺口', 'research.json 的 spot 数组为空', '首屏无法给出“当前价”，只能给期货价', '至少补 1 条带六项口径的现货')

    # 现货锚：显式指定优先，否则取日期最新的那条
    anchor_in = R.get('anchor')
    anchor = None
    if anchor_in:
        anchor = {
            'label': anchor_in.get('label') or anchor_in.get('region', '') + anchor_in.get('product', ''),
            'value': common.num(anchor_in.get('value')), 'unit': anchor_in.get('unit') or (meta_in.get('unit') or '元/吨'),
            'range_lo': common.num(anchor_in.get('range_lo')), 'range_hi': common.num(anchor_in.get('range_hi')),
            'date': anchor_in.get('date'), 'basis': anchor_in.get('basis') or '',
            'prev_date': anchor_in.get('prev_date'), 'prev_mid': common.num(anchor_in.get('prev_mid')),
            'note': anchor_in.get('note') or '', 'src': anchor_in.get('src') or '',
        }
    elif spots:
        ranked = sorted(spots, key=lambda s: s['date'], reverse=True)
        s = ranked[0]
        anchor = {'label': '%s%s' % (s['region'], s['product']), 'value': round((s['lo'] + s['hi']) / 2),
                  'unit': meta_in.get('unit') or '元/吨', 'range_lo': s['lo'], 'range_hi': s['hi'],
                  'date': s['date'], 'basis': s['basis'], 'prev_date': None, 'prev_mid': None,
                  'note': s['note'], 'src': s['src']}
    if anchor and anchor['value'] is None:
        gap('现货锚', '缺口', 'anchor.value 解析不出数字', '首屏 KPI 改为只显示期货价', '填数字')
        anchor = None

    # 锚的时效性提示
    if anchor and anchor.get('date') and common.parse_date(anchor['date']):
        age = common.days_between(anchor['date'], asof)
        if age is not None and age > 7:
            caveats.append('现货锚取 %s，距数据截止日 %s 已 %d 天。现货是逐日报价品种，'
                           '对外报价前须用当日实盘或付费资讯校准。' % (anchor['date'], asof, age))

    # ---------------------------------------------------------------- 派生指标
    chg, win, peak, trough, disc = {}, {}, None, None, None
    price_last = last['c'] if last else None
    if last:
        for k, d in WINDOWS:
            c = common.change_stats(rows, last, d)
            if c:
                chg[k] = c
        for k, d in RANK_WINDOWS:
            w = common.window_stats(rows, last, d)
            if w:
                win[k] = w
        hi = max(rows, key=lambda r: r['h'])
        lo = min(rows, key=lambda r: r['l'])
        peak = {'value': hi['h'], 'date': hi['d']}
        trough = {'value': lo['l'], 'date': lo['d']}
        if peak['value']:
            disc = {'from_peak': round((last['c'] / peak['value'] - 1) * 100, 1),
                    'above_low_abs': round(last['c'] - trough['value'], 1),
                    'above_low_pct': round((last['c'] / trough['value'] - 1) * 100, 1)}

    # ---------------------------------------------------------------- 序列
    series = {}
    if last:
        series['30d'] = common.candles([r for r in rows if r['d'] >= _back(last, 30)])
        series['90d'] = common.candles([r for r in rows if r['d'] >= _back(last, 90)])
        series['1y'] = common.candles([r for r in rows if r['d'] >= _back(last, 365)])
        series['3y'] = common.candles([r for r in rows if r['d'] >= _back(last, 1095)])
        series['5y_w'] = common.weekly([r for r in rows if r['d'] >= _back(last, 1825)])
        series['all_w'] = common.weekly(rows)
        series['all'] = common.candles(rows)
        series['5y_m'] = common.candles([r for r in rows if r['d'] >= _back(last, 1825)][::21])
        series['all_m'] = common.candles(rows[::21])

    monthly = {}
    if last:
        for key, days in [('30d', 30), ('90d', 90), ('1y', 365), ('3y', 1095), ('all', None)]:
            groups = {}
            for row in rows:
                if days is None or row['d'] >= _back(last, days):
                    groups.setdefault(row['d'][:7], []).append(row['c'])
            monthly[key] = [[month, None, round(sum(values) / len(values), 4), None, None]
                            for month, values in groups.items()]

    # ---------------------------------------------------------------- 异常波动
    anomalies = []
    thr = float(meta_in.get('anomaly_pct') or 3.5)
    if last:
        cut = _back(last, 365)
        ann = [r for r in rows if r['d'] >= cut]
        for r in ann:
            if abs(r['pct'] or 0) >= thr:
                anomalies.append({'d': r['d'], 'pct': round(r['pct'], 2), 'c': r['c'], 'v': r['v'], 'event': None})
        anomalies.sort(key=lambda x: x['d'])

    # ---------------------------------------------------------------- 事件
    events = []
    for e in R.get('events') or []:
        ev = {
            'date': e.get('date'), 'tag': e.get('tag') or '事件',
            'title': e.get('title') or '', 'price_ref': common.num(e.get('price_ref')),
            'impact': e.get('impact') or '双向', 'detail': e.get('detail') or '',
            'src': e.get('src') or '', 'no_mark': bool(e.get('no_mark')),
        }
        events.append(ev)
        # 事件对齐到最近一个交易日，供 K 线 markPoint 使用
        if last and ev['date'] and not ev['no_mark']:
            near = None
            for r in rows:
                if r['d'] <= ev['date']:
                    near = r
                else:
                    break
            if near and near['d'] >= _back(last, 1095):
                ev['mark_d'] = near['d']
                ev['mark_price'] = near['c']
                for a in anomalies:
                    if a['d'] == near['d']:
                        a['event'] = ev['title']
    events.sort(key=lambda e: e['date'] or '')
    marks = [{'d': e['mark_d'], 'price': e['mark_price'], 'title': e['title'], 'tag': e['tag'],
              'impact': e['impact'], 'date': e['date']} for e in events if e.get('mark_d')]

    # ---------------------------------------------------------------- 成本线
    cost_lines = []
    for c in R.get('cost_lines') or []:
        cost_lines.append({'name': c.get('name') or '成本线', 'value': common.num(c.get('value')),
                           'date': c.get('date'), 'src': c.get('src') or '',
                           'note': c.get('note') or ''})
    cost_lines = [c for c in cost_lines if c['value'] is not None]

    # ---------------------------------------------------------------- 毛利（按工艺/路线）
    margins = normalize_margins(R.get('margins') or [])
    if not any(v is not None for m in margins for v in m.get('routes', {}).values()):
        gap('工艺路线毛利', '缺口', '未取得分工艺且有日期与来源的毛利数据',
            '不展示毛利模块，不能据此判断装置减产动机', '补充路线、单位、日期和来源')

    # ---------------------------------------------------------------- 汇总
    out = {
        'meta': {
            'product': product,
            'spec': meta_in.get('spec') or '',
            'region': meta_in.get('region') or '全国',
            'asof': asof,
            'unit': meta_in.get('unit') or '元/吨',
            'title': meta_in.get('title') or '%s 行情与销售事实看板' % product,
            'subtitle': meta_in.get('subtitle') or (
                '产品 %s ｜ 规格 %s ｜ 重点市场 %s ｜ 数据截至 %s ｜ 只陈述已发生事实，不预测后市'
                % (product, meta_in.get('spec') or '见各表', meta_in.get('region') or '全国', asof)),
            'disclaimer': meta_in.get('disclaimer') or (
                '现货含税、期货不含税，两者不可直接相减；无可靠数据处标注缺口，不给近似值；本页不预测涨跌。'),
            'exchange': fut_meta.get('exchange') or '', 'contract': fut_meta.get('code') or '',
            'futures_note': fut_meta.get('note') or '期货为主连连续合约，不含税、含交割成本。',
            'anomaly_pct': thr,
            'peer_products': meta_in.get('peer_products') or [],
        },
        'last': {'close': last['c'] if last else None, 'date': last['d'] if last else None,
                 'pct': round(last['pct'], 2) if last else None,
                 'o': last['o'] if last else None, 'h': last['h'] if last else None,
                 'l': last['l'] if last else None, 'v': last['v'] if last else None,
                 'price': price_last},
        'anchor': anchor, 'chg': chg, 'win': win, 'peak': peak, 'trough': trough, 'drawdown': disc,
        'series': series, 'monthly': monthly, 'anomalies': anomalies, 'marks': marks, 'events': events,
        'spots': spots, 'spreads': [], 'cost_lines': cost_lines,
        'upstream': R.get('upstream') or [], 'downstream': R.get('downstream') or [],
        'balance': R.get('balance') or [], 'margins': margins,
        'facts': R.get('facts') or [], 'talk': R.get('talk') or [],
        'gaps': gaps, 'caveats': _dedup(caveats), 'sources': sources,
        'narrative': R.get('narrative') or {},
        'chain_hints': {'up': (common.CHAIN_HINTS.get(product) or ([], []))[0],
                        'down': (common.CHAIN_HINTS.get(product) or ([], []))[1]},
    }
    out['spreads'] = _spreads(spots, anchor, R)
    out['summary'] = _summary(out)
    return out


def _back(last, days):
    d = common.parse_date(last['d']) - datetime.timedelta(days=days)
    return d.isoformat()


# 旧字段名 -> 路线名（兼容单品种时代的写法）
LEGACY_ROUTES = {'ammonia': '氨碱', 'hou': '联碱（双吨）', 'natural': '天然碱',
                 'coal': '煤制', 'gas': '天然气制', 'ethylene': '乙烯法', 'calcium': '电石法'}


def normalize_margins(raw):
    """统一成 [{date, routes:{路线名: 毛利}, src}]。
    接受两种写法：
      A) 推荐：{'date':..., 'routes': {'天然气制': -144.7, '煤制气': -20}, 'src':...}
      B) 兼容：{'date':..., 'ammonia': -202, 'hou': -184, 'natural': 108, 'src':...}
    """
    out = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        routes = {}
        src_routes = m.get('routes')
        if isinstance(src_routes, dict):
            for k, v in src_routes.items():
                nv = common.num(v)
                if nv is not None:
                    routes[str(k)] = nv
        else:
            for k, label in LEGACY_ROUTES.items():
                if k in m:
                    nv = common.num(m.get(k))
                    if nv is not None:
                        routes[label] = nv
        if not routes:
            continue
        out.append({'date': m.get('date'), 'routes': routes, 'src': m.get('src') or '',
                    'note': m.get('note') or ''})
    out.sort(key=lambda x: x.get('date') or '')
    return out


def _dedup(seq):
    seen, out = set(), []
    for x in seq:
        k = str(x).strip()
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _spreads(spots, anchor, R):
    """同规格、同税基的现货按日期分组，组内算相对基准的价差。"""
    cfg = R.get('spread_base') or {}
    base_region = cfg.get('region') or (spots[0]['region'] if spots else None)
    base_dates = cfg.get('dates')
    groups = {}
    for s in spots:
        if base_dates and s['date'] not in base_dates:
            continue
        groups.setdefault(s['date'], []).append(s)
    out = []
    for date, rows in sorted(groups.items(), reverse=True):
        if len(rows) < 2:
            continue
        base = next((r for r in rows if r['region'] == base_region), None)
        if not base:
            continue
        bmid = (base['lo'] + base['hi']) / 2
        for s in rows:
            mid = (s['lo'] + s['hi']) / 2
            out.append({'date': date, 'region': s['region'], 'sub': s['sub'], 'lo': s['lo'], 'hi': s['hi'],
                        'mid': round(mid, 1), 'diff_vs_base': round(mid - bmid, 1),
                        'basis': s['basis'], 'tax': s['tax'], 'single': s['single'],
                        'driver': s['note'] or '', 'src': s['src'], 'base_region': base_region})
    return out


def _summary(D):
    """首屏一句话：只用已算出的数字，不做判断。"""
    m, a, l = D['meta'], D['anchor'], D['last']
    parts = []
    if a and a.get('value') is not None:
        parts.append('现货 %s %s %s（%s）' % (a['label'], common.fmt(a['value']), a['unit'], a['date']))
    if l.get('close') is not None:
        parts.append('期货主连 %s %s（%s 收盘，不含税）' % (common.fmt(l['close']), m['unit'], l['date']))
    if D['win'].get('1y'):
        w = D['win']['1y']
        parts.append('近 1 年区间 %s–%s、当前 %s 分位' % (common.fmt(w['low']), common.fmt(w['high']),
                                                   '%.1f%%' % w['pct_rank']))
    if D['drawdown']:
        parts.append('较样本高点回撤 %.1f%%、距低点 %s %s' % (abs(D['drawdown']['from_peak']),
                                                        common.fmt(D['drawdown']['above_low_abs']), m['unit']))
    margins = [x for x in (D.get('margins') or []) if x.get('routes')]
    if margins:
        lastm = margins[-1]
        parts.append('%s 毛利 %s（%s）' % (lastm.get('date'),
                                          ' / '.join('%s %s' % (k, common.fmt_trim(v)) for k, v in lastm['routes'].items()),
                                          m['unit']))
    return '；'.join(parts) + '。' if parts else '数据不足，尚未形成可陈述的结论；请先补现货与期货两条主线。'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('research')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    base = os.path.dirname(os.path.abspath(a.research))
    R = common.load_json(a.research)
    D = build(R, base)
    out = a.out or os.path.join(base, 'build', 'data.json')
    common.dump_json(D, out)
    common.ok('data.json 已生成 %s（%.1f KB）' % (out, os.path.getsize(out) / 1024))
    print('  品种 %s ｜ 基准日 %s ｜ 现货 %d 条 ｜ 期货 %s ｜ 事件 %d ｜ 异常 %d ｜ 缺口 %d'
          % (D['meta']['product'], D['meta']['asof'], len(D['spots']),
             '有' if D['series'] else '无', len(D['events']), len(D['anomalies']), len(D['gaps'])))
    print('  摘要：' + common.clip(D['summary'], 200))


if __name__ == '__main__':
    main()
