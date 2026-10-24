# -*- coding: utf-8 -*-
"""research.json -> data.json（采购版）。

与销售版最大的区别：**价格主线是“采购点的现货报价序列”，不是期货**。
期货只作为透明参考（基差需同日才可比），不参与首屏结论。

用法：
  python assemble.py research.json --out build/data.json

派生物全部在这里算：区间涨跌、区间高低、分位、区域价差、成本拆解、事件过滤。
research.json 里手写这些数字一律视为错误。
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

WINDOWS = [(7, '7天'), (30, '30天'), (90, '90天'), (365, '1年'), (1095, '3年')]


def build(R, base_dir='.'):
    meta_in = R.get('meta') or {}
    product = meta_in.get('product') or '未命名品种'
    asof = meta_in.get('asof') or datetime.date.today().isoformat()
    unit = meta_in.get('unit') or '元/吨'
    gaps = [dict(g) for g in (R.get('gaps') or [])]
    caveats = list(R.get('caveats') or [])
    sources = list(R.get('sources') or [])

    def gap(item, status, detail, impact='', fix=''):
        gaps.append({'item': item, 'status': status, 'detail': detail, 'impact': impact, 'fix': fix})

    # ---------------------------------------------------------------- 期货（只作参考）
    fut_meta = dict(R.get('futures') or {})
    frows = []
    if fut_meta.get('series'):
        cand = fut_meta['series'] if os.path.isabs(fut_meta['series']) else os.path.join(base_dir, fut_meta['series'])
        if os.path.exists(cand):
            try:
                frows = common.load_series(cand)
                a = common.parse_date(asof)
                if a:
                    frows = [r for r in frows if r['d'] <= asof]
            except Exception as e:
                gap('期货日线', '缺口', '序列解析失败：%s（%s）' % (fut_meta['series'], e),
                    '期货仅作参考，不影响现货结论', '检查 raw/*_daily.json')
        else:
            gap('期货日线', '缺口', '序列文件不存在：%s' % cand, '期货仅作参考', '先跑 fetch_futures.py')
    flast = frows[-1] if frows else None

    # ---------------------------------------------------------------- 现货报价（六项口径）
    quotes = []
    for i, s in enumerate(R.get('spot') or []):
        lo, hi = common.num(s.get('lo')), common.num(s.get('hi'))
        if lo is None and hi is None:
            lo = hi = common.num(s.get('value'))
        if lo is None:
            gap('现货报价', '缺口', '第 %d 条缺少价格数字（%s / %s）' % (
                i + 1, s.get('point') or s.get('region'), s.get('spec') or s.get('product')),
                '该条不进现货表', '补 lo/hi')
            continue
        if hi is None:
            hi = lo
        if lo > hi:
            lo, hi = hi, lo
        miss = [k for k in ('point', 'spec', 'tax', 'basis', 'date', 'src') if not s.get(k)]
        if miss:
            caveats.append('报价行「%s / %s」缺 %s，对外引用前须补全。'
                           % (s.get('point') or s.get('region', '?'), s.get('spec', '?'), '、'.join(miss)))
        quotes.append({
            'point': s.get('point') or s.get('region') or '未标注点',
            'region': s.get('region') or '',
            'spec': s.get('spec') or s.get('product') or '未标注规格',
            'lo': lo, 'hi': hi, 'mid': round((lo + hi) / 2, 1),
            'tax': s.get('tax') or '未标注', 'basis': s.get('basis') or '未标注',
            'date': str(s.get('date') or '')[:10], 'conf': s.get('conf') or '中',
            'tier': s.get('tier') or '市场', 'quote_kind': s.get('quote_kind') or '',
            'note': s.get('note') or '', 'src': s.get('src') or '未标注来源',
            'single': lo == hi,
        })
    if not quotes:
        gap('现货报价', '缺口', 'spot 数组为空或全部无价', '首屏无法给出“当前价”',
            '至少补 1 条六项口径齐全的报价')

    # ---------------------------------------------------------------- 采购点序列
    seq_raw = R.get('quote_series') or []
    if not seq_raw:
        seq_raw = [{'point': q['point'], 'date': q['date'], 'lo': q['lo'], 'hi': q['hi'],
                    'spec': q['spec'], 'tax': q['tax'], 'basis': q['basis'], 'src': q['src']} for q in quotes]
        if quotes:
            caveats.append('未单独提供 quote_series，已用报价表里同一采购点的多条报价自动拼序列；'
                           '若某点只有 1 条报价，该点不会出现在走势与分位里。')
    series_pts = common.series_from_quotes(seq_raw)
    series = {}
    for pt, b in series_pts.items():
        st = common.seq_stats(b['rows'])
        if not st:
            continue
        st['meta'] = b['meta']
        st['rows'] = b['rows']
        series[pt] = st
    primary = R.get('primary_point') or (max(series, key=lambda p: series[p]['n']) if series else None)
    if not series:
        gap('现货序列', '缺口', '没有任何采购点有 ≥1 条带日期的报价',
            '涨跌幅与分位无法计算', '补 quote_series（每条带 point/date/lo/hi/src）')
    elif not [p for p in series if series[p]['n'] >= 8]:
        caveats.append('所有采购点的报价条数都 < 8，区间统计样本很薄；报告已逐条标出样本数，'
                       '请勿当作连续行情引用。')

    # ---------------------------------------------------------------- 锚（当前价）
    anc = R.get('anchor') or {}
    anchor = None
    if anc and common.num(anc.get('value')) is not None:
        anchor = {'label': anc.get('label') or '%s 主流价' % primary,
                  'point': anc.get('point') or primary, 'value': common.num(anc.get('value')),
                  'unit': anc.get('unit') or unit,
                  'range_lo': common.num(anc.get('range_lo')), 'range_hi': common.num(anc.get('range_hi')),
                  'date': anc.get('date'), 'basis': anc.get('basis') or '', 'tax': anc.get('tax') or '',
                  'prev_date': anc.get('prev_date'), 'prev_mid': common.num(anc.get('prev_mid')),
                  'note': anc.get('note') or '', 'src': anc.get('src') or ''}
    elif primary and series[primary]['rows']:
        r = series[primary]['rows'][-1]
        prev = series[primary]['rows'][-2] if len(series[primary]['rows']) > 1 else None
        anchor = {'label': '%s 主流报价' % primary, 'point': primary, 'value': r['mid'], 'unit': unit,
                  'range_lo': r['lo'], 'range_hi': r['hi'], 'date': r['d'],
                  'basis': series[primary]['meta'].get('basis', ''),
                  'tax': series[primary]['meta'].get('tax', ''),
                  'prev_date': prev['d'] if prev else None, 'prev_mid': prev['mid'] if prev else None,
                  'note': r.get('note') or '', 'src': r.get('src') or ''}
    if anchor and anchor.get('date'):
        age = common.days_between(anchor['date'], asof)
        if age is not None and age > 3:
            caveats.append('锚价取 %s，距数据截止日 %s 已 %d 天。采购下单前须用当日供应商报价或实盘询价校准。'
                           % (anchor['date'], asof, age))

    # ---------------------------------------------------------------- 区域价差（采购口径）
    spreads = _spreads(quotes, R)
    sg = _spread_groups(quotes, R)
    if not spreads and not sg:
        gap('区域价差', '缺口', '没有“同一天 ≥2 个采购点”的报价',
            '无法判断是否该从远端或低价区调货', '在同一期资讯里找多区域同日报价，或对 2–3 个区域同日询价')

    # ---------------------------------------------------------------- 成本
    costs = []
    for i, c in enumerate(R.get('cost_lines') or []):
        v = common.num(c.get('value'))
        if v is None:
            gap('成本线「%s」' % (c.get('name') or i), '缺口', 'cost_lines[%d] 没有 value' % i,
                '分位条上无法标出成本位置', '补数字或删除该条')
            continue
        costs.append({'name': c.get('name') or '成本参考', 'value': v, 'date': c.get('date'),
                      'src': c.get('src') or '', 'note': c.get('note') or '',
                      'route': c.get('route') or '', 'type': c.get('type') or '参考',
                      'derived': bool(c.get('derived'))})
    route_costs = []
    for rt in R.get('routes') or []:
        rc = common.route_cost(rt)
        if rc:
            route_costs.append(rc)

    # ---------------------------------------------------------------- 产业链（自证）
    chain = {'upstream': [], 'downstream': []}
    for side in ('upstream', 'downstream'):
        for x in R.get(side) or []:
            item = {
                'name': x.get('name') or '未命名',
                'role': x.get('role') or ('成本项' if side == 'upstream' else '需求项'),
                'value': common.num(x.get('value')), 'unit': x.get('unit') or '',
                'range_lo': common.num(x.get('range_lo')), 'range_hi': common.num(x.get('range_hi')),
                'chg': x.get('chg') or '', 'date': x.get('date'),
                'direction': x.get('direction') or ('gap' if x.get('value') is None else 'flat'),
                'ratio': x.get('ratio') or '', 'logic': x.get('logic') or '',
                'link': x.get('link') or '', 'src': x.get('src') or '',
            }
            if item['value'] is None and item['range_lo'] is None:
                item['direction'] = 'gap'
            chain[side].append(item)
    proof = []
    for p in R.get('chain_proof') or []:
        proof.append({'relation': p.get('relation') or '',
                      'from': p.get('from') or '', 'to': p.get('to') or '',
                      'ratio': p.get('ratio') or '', 'share': p.get('share') or '',
                      'evidence': p.get('evidence') or '', 'src': p.get('src') or '',
                      'checked': p.get('checked') if p.get('checked') is not None else True})
    if not proof:
        gap('产业链断点核对', '缺口', '未提供 chain_proof（工艺路线自证表）',
            '无法排除“把无关品种当上下游”的错误', '按 references/chain-mapping.md 补每一环的工艺依据与占比')
    elif [p for p in proof if not p['checked']]:
        bad = [p for p in proof if not p['checked']]
        caveats.append('产业链自证中有 %d 条未通过（%s），报告中已标红；这些环节的数字不要对外引用。'
                       % (len(bad), '、'.join('%s→%s' % (b['from'], b['to']) for b in bad[:3])))

    # ---------------------------------------------------------------- 供需库存
    balance = []
    for b in R.get('balance') or []:
        balance.append({'k': b.get('k') or '未命名指标',
                        'v': str(b.get('v') if b.get('v') is not None else '—'),
                        'date': b.get('date') or '', 'prev': b.get('prev') or '',
                        'scope': b.get('scope') or '', 'src': b.get('src') or '',
                        'level': b.get('level') or ''})
    if not balance:
        gap('库存与开工', '缺口', 'balance 为空', '无法解释“为什么贵/为什么跌”的供给端事实',
            '补港口/工厂库存、开工率、到港量、检修损失量')

    # ---------------------------------------------------------------- 事件（采购视角）
    events, rejected = [], []
    for e in R.get('events') or []:
        ev = {'date': str(e.get('date') or '')[:10], 'tag': e.get('tag') or '事件',
              'title': e.get('title') or '', 'detail': e.get('detail') or '',
              'impact': e.get('impact') or '双向', 'evidence': e.get('evidence') or '公开报道',
              'price_ref': common.num(e.get('price_ref')), 'after': e.get('after') or '',
              'src': e.get('src') or '', 'url': e.get('url') or ''}
        if ev['evidence'] in ('传闻', '待确认'):
            rejected.append(ev)
            continue
        ev['status'] = '机构观点' if ev['evidence'] == '机构观点' else '已证实'
        events.append(ev)
    events.sort(key=lambda x: x['date'])
    if rejected:
        caveats.append('有 %d 条消息只有“传闻/待确认”，未进入时间线，单列在“未采纳消息”里。' % len(rejected))

    marks = []
    if primary and series.get(primary):
        rows = series[primary]['rows']
        for ev in events:
            near = None
            for r in rows:
                if r['d'] <= ev['date']:
                    near = r
            if not near:
                continue
            ev['mark_d'] = near['d']
            ev['mark_price'] = near['mid']
            marks.append({'d': near['d'], 'price': near['mid'], 'title': ev['title'], 'tag': ev['tag'],
                          'impact': ev['impact'], 'date': ev['date'], 'point': primary})

    # ---------------------------------------------------------------- 采购决策面
    play = dict(R.get('procurement') or {})
    inv_days = common.num(play.get('inventory_days'))
    usage = common.num(play.get('monthly_usage'))
    if inv_days is not None and anchor and anchor.get('date'):
        d = common.parse_date(anchor['date'])
        play['inventory_cover_to'] = (d + datetime.timedelta(days=int(round(inv_days)))).isoformat() if d else None
    if usage and anchor:
        play['usage_note'] = '按月度用量 %s 测算，价格每变动 100 %s，月度采购额变动 %s。' % (
            common.fmt(usage), unit, common.fmt(usage * 100))

    out = {
        'meta': {
            'product': product, 'spec': meta_in.get('spec') or '', 'region': meta_in.get('region') or '全国',
            'asof': asof, 'unit': unit,
            'title': meta_in.get('title') or '%s（%s）原料行情底稿' % (product, meta_in.get('region') or '全国'),
            'subtitle': meta_in.get('subtitle') or (
                '采购视角 ｜ 品种 %s ｜ 规格 %s ｜ 采购点 %s ｜ 数据截至 %s ｜ 只陈述已发生事实，不做价格预测'
                % (product, meta_in.get('spec') or '见各表', meta_in.get('region') or '全国', asof)),
            'disclaimer': meta_in.get('disclaimer') or (
                '现货报价按“点·规格·含税·提货方式·日期·来源”六项标注；缺数一律标缺口，不插值不估算；'
                '本页只陈述已发生事实，不给买卖时点建议。'),
            'exchange': fut_meta.get('exchange') or '', 'contract': fut_meta.get('code') or '',
            'futures_note': fut_meta.get('note') or '期货为主连连续合约，不含税、含交割成本，仅作参考。',
            'anomaly_pct': float(meta_in.get('anomaly_pct') or 3.5),
            'peer_products': meta_in.get('peer_products') or [],
            'buyer': meta_in.get('buyer') or '',
            'primary_point': primary,
            'quote_kinds': meta_in.get('quote_kinds') or [],
            'perspective': '采购',
        },
        'anchor': anchor,
        'points': [{'point': p, 'n': series[p]['n'], 'start': series[p]['start'],
                    'last': series[p]['last'], 'meta': series[p]['meta']} for p in series],
        'series': series,
        'primary': series.get(primary) if primary else None,
        'chg': series[primary]['chg'] if primary else {},
        'win': series[primary]['win'] if primary else {},
        'position': common.quote_position(anchor['value'] if anchor else None, series.get(primary)),
        'windows_label': dict(WINDOWS),
        'quotes': quotes,
        'spreads': spreads, 'spread_groups': sg,
        'futures': {'last': {'close': flast['c'], 'date': flast['d'],
                             'pct': round(flast['pct'], 2) if flast else None,
                             'o': flast['o'], 'h': flast['h'], 'l': flast['l']} if flast else None,
                    'win': _fwin(frows) if frows else {}},
        'cost_lines': costs, 'route_costs': route_costs,
        'chain': chain, 'chain_proof': proof,
        'broken_links': [p for p in proof if not p['checked']],
        'balance': balance, 'events': events, 'events_rejected': rejected, 'marks': marks,
        'facts': R.get('facts') or [], 'talk': R.get('talk') or [],
        'procurement': play, 'gaps': gaps, 'caveats': _dedup(caveats), 'sources': sources,
        'narrative': R.get('narrative') or {},
    }
    if play.get('inventory_days') is None:
        gap('采购库存天数', '缺口', 'procurement.inventory_days 未填',
            '无法把“当前价”换算成“还能撑到哪天”，也就无法判断补单窗口',
            '填本厂当前原料库存可使用天数（含在途）')
    out['summary'] = _summary(out)
    return out


def _fwin(rows):
    last = rows[-1]
    out = {}
    for d in (7, 30, 90, 365, 1095):
        w = common.window_stats(rows, last, d)
        if w:
            out[str(d)] = w
    return out


def _spreads(quotes, R):
    cfg = R.get('spread_base') or {}
    base = cfg.get('point')
    cur = (R.get('procurement') or {}).get('current_source_points') or []
    groups = {}
    for q in quotes:
        groups.setdefault(q['date'], []).append(q)
    out = []
    for date, rows in sorted(groups.items(), reverse=True):
        if not base or len(rows) < 2:
            continue
        if cfg.get('dates') and date not in cfg['dates']:
            continue
        b = next((r for r in rows if r['point'] == base), None)
        if not b:
            continue
        for q in rows:
            if q['point'] == base:
                continue
            out.append({'date': date, 'point': q['point'], 'spec': q['spec'], 'lo': q['lo'], 'hi': q['hi'],
                        'mid': q['mid'], 'base_point': base, 'base_mid': b['mid'],
                        'diff_vs_base': round(q['mid'] - b['mid'], 1),
                        'basis': q['basis'], 'tax': q['tax'], 'note': q['note'], 'src': q['src'],
                        'is_source': (not cur) or (q['point'] in cur)})
    return out


def _spread_groups(quotes, R):
    """按“同一批报价”分组（如各区域每日/每周跟踪表），用于画走势对比与价差曲线。"""
    out = []
    for gi, g in enumerate(R.get('spread_series') or []):
        if not isinstance(g, dict):
            continue
        pts = common.series_from_quotes(g.get('rows') or [])
        if len(pts) < 2:
            continue
        base = g.get('base') or list(pts)[0]
        all_dates = sorted({r['d'] for b in pts.values() for r in b['rows']})
        lines = {p: [{'d': r['d'], 'mid': r['mid'], 'lo': r['lo'], 'hi': r['hi']} for r in b['rows']]
                 for p, b in pts.items()}
        diffs = []
        for d in all_dates[-60:]:
            b = next((r for r in pts[base]['rows'] if r['d'] == d), None)
            if not b:
                continue
            for p, rows in lines.items():
                if p == base:
                    continue
                rr = next((r for r in rows if r['d'] == d), None)
                if rr:
                    diffs.append({'date': d, 'point': p, 'base': base, 'diff': round(rr['mid'] - b['mid'], 1)})
        out.append({'id': gi, 'name': g.get('name') or '区域报价跟踪', 'base': base,
                    'unit': g.get('unit') or (R.get('meta') or {}).get('unit') or '元/吨',
                    'series': lines, 'diffs': diffs,
                    'note': g.get('note') or '', 'src': g.get('src') or ''})
    return out


def _dedup(seq):
    seen, out = set(), []
    for x in seq:
        k = str(x).strip()
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _summary(D):
    a, p = D.get('anchor'), D.get('primary')
    parts = []
    if a:
        parts.append('当前价 %s %s %s（%s，%s）' % (a['label'], common.fmt(a['value']), a['unit'],
                                               a['date'], a.get('basis') or '口径见附表'))
    if p and p.get('win', {}).get(90):
        w90 = p['win'][90]
        parts.append('近 90 天样本 %d 个报价点，区间 %s–%s、当前处 %.0f%% 分位'
                     % (w90['n'], common.fmt(w90['low']), common.fmt(w90['high']), w90['pct_rank']))
    chg = D.get('chg') or {}
    if chg.get(30) and chg[30].get('pct') is not None:
        parts.append('30 天 %+.1f%%（%s→%s，中间 %d 个报价点）'
                     % (chg[30]['pct'], chg[30]['from_date'], p['last']['d'], chg[30]['n_between']))
    sp = [s for s in (D.get('spreads') or []) if s.get('is_source')]
    if sp:
        s0 = sp[0]
        parts.append('同期 %s 较 %s %+.0f %s' % (s0['point'], s0['base_point'], s0['diff_vs_base'], D['meta']['unit']))
    return '；'.join(parts) + '。' if parts else '数据不足：至少需要 1 个采购点的报价序列才能形成可陈述的结论。'


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
    print('  品种 %s ｜ 基准日 %s ｜ 采购点 %d ｜ 报价 %d ｜ 事件 %d ｜ 缺口 %d'
          % (D['meta']['product'], D['meta']['asof'], len(D['points']), len(D['quotes']),
             len(D['events']), len(D['gaps'])))
    print('  摘要：' + common.clip(D['summary'], 220))


if __name__ == '__main__':
    main()
