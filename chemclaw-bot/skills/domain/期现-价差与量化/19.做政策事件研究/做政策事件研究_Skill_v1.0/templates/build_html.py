# -*- coding: utf-8 -*-
"""政策事件研究 · HTML 报告构建器

把 research.json（研究事实）+ event_study.py 的统计结果 -> 单文件离线 HTML。

原则：
- 内联 ECharts，不引用任何外链 CDN，双击即可打开、可微信发送；
- 统计口径不足时页面显著降级（红框声明"样本不足"），不隐藏；
- 所有数字来自数据文件，模板里不手写任何行情数字。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)


def load(p):
    with open(p, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def find_echarts():
    for c in [os.path.join(SKILL_ROOT, 'assets', 'echarts.min.js'),
              os.path.join(os.path.dirname(SKILL_ROOT), 'chem-market-brief', 'scripts', 'assets', 'echarts.min.js'),
              os.path.join(os.path.expanduser('~'), '.agents', 'skills', 'chem-market-brief', 'scripts', 'assets', 'echarts.min.js')]:
        if os.path.isfile(c):
            return c
    return None


def build(research, study, echarts_js, out_path):
    """research: research.json；study: event_study.run() 的输出。"""
    meta = research.get('meta', {})
    events = research.get('events', [])
    st = study

    # ---- 把 study 结果回填到事件卡 ----
    by_id = {e['id']: e for e in st['events']}
    for e in events:
        s = by_id.get(e['id'])
        if not s:
            e['windows'] = {}
            continue
        a = s['anchors'].get('market_first_aware') or {}
        if not a.get('ok'):
            e['windows'] = {}
            continue
        e['base_date'] = a['windows']['base']['date']
        e['anchor_used'] = '市场首知日'
        win = {}
        for w, wd in a['windows'].items():
            if w == 'base' or not wd.get('ok'):
                continue
            win[str(w)] = {'date': wd['date'], 'spot': wd['spot'], 'spot_chg': wd['spot_chg'],
                           'spot_pct': wd['spot_pct'], 'future': wd['future'], 'future_chg': wd['future_chg'],
                           'future_pct': wd['future_pct'], 'basis': wd['basis'], 'basis_chg': wd['basis_chg']}
        e['windows'] = win
        paths = {}
        for ank, av in s['anchors'].items():
            if av.get('ok') and av.get('path'):
                paths[ank] = av['path']
        e['paths'] = paths
        try:
            import datetime as _dt
            if e.get('publish_date') and e.get('effective_date'):
                e['lead_days'] = (_dt.date.fromisoformat(e['effective_date']) -
                                  _dt.date.fromisoformat(e['publish_date'])).days
        except Exception:
            e['lead_days'] = None

    # ---- 统计表 ----
    windows = st['windows']
    tables, raw = {}, {}
    metric_titles = [('future_chg', '期货变动（主力合约，元/吨）'),
                     ('spot_chg', '现货变动（元/吨）'),
                     ('basis_chg', '基差变动（元/吨）')]
    any_allow = False
    for mk, mtitle in metric_titles:
        rows = []
        for w in windows:
            gmap = st['stats']['market_first_aware'].get(str(w), st['stats']['market_first_aware'].get(w, {})).get(mk, {})
            for g, s in gmap.items():
                q = s.get('quantiles') or {}
                rows.append({'window': w, 'group': g, 'n': s['n'],
                             'mean': s['mean'], 'median': s['median'], 'std': s['std'],
                             'q25': q.get('q0.25'), 'q75': q.get('q0.75'),
                             'min': s['min'], 'max': s['max'], 'pos': s['positive_ratio'],
                             'sig_allowed': s['significance_allowed'],
                             'p': s.get('p_value'),
                             'members': ', '.join(m['id'] for m in s.get('members', []))})
                if s['significance_allowed']:
                    any_allow = True
        tables[mk] = {'title': mtitle, 'rows': rows,
                      'note': '均值/中位数/分位均基于"市场首知日"锚点的 +N 个交易日窗口；基差为现货减期货。'
                              '样本量 < 5 的组不计算任何显著性检验。'}
    # 分布原始值（箱线图）
    for w in windows:
        raw[str(w)] = {}
        for mk, _ in metric_titles:
            gmap = st['stats']['market_first_aware'].get(str(w), st['stats']['market_first_aware'].get(w, {})).get(mk, {})
            raw[str(w)][mk] = {g: [m['value'] for m in s['members'] if m['value'] is not None]
                               for g, s in gmap.items()}

    n_events = len(events)
    n_with_futures = sum(1 for e in events if e.get('windows'))
    max_group_n = max([len(v) for v in st.get('groups', {}).values()] or [0])

    if n_events == 0:
        disclaimer = '未获得政策事件，无法开展事件研究。'
    elif not any_allow:
        disclaimer = (
            '<b>关于统计显著性：</b>本项目可比组内样本量最大为 %d 个事件，低于 5 个的统计门槛。'
            '按研究规范，本报告<b>不计算、不报告</b>任何 p 值或"显著/不显著"结论，'
            '所有均值、中位数、分位数仅作<b>描述性</b>用途。任何把这种样本量下的均值差异当作'
            '"政策效应显著"的表述都是不成立的。' % max_group_n)
    else:
        disclaimer = ('<b>关于统计显著性：</b>仅样本量 ≥ 5 的可比组计算了单样本 t 检验（对 0），'
                      '并已在表中标注 p 值；其余组仍只作描述性统计。即使 p 值较小，'
                      '由于事件不可重复、混杂因素无法控制，也只能读作"窗口内变动的方向一致性"，'
                      '不能读作"政策导致了该变动"。')

    # ---- 判定结论区 ----
    verdict = research.get('verdict') or {}
    kpis = verdict.get('kpis') or []
    if not kpis:
        kpis = [
            {'label': '有效政策事件', 'value': '%d 个' % n_events,
             'note': '其中 %d 个落在价格数据覆盖区间内' % n_with_futures},
            {'label': '最大可比组样本', 'value': 'n=%d' % max_group_n,
             'note': '低于 5 即不做汇总显著性'},
            {'label': '数据覆盖', 'value': '%s ~ %s' % (st['calendar']['start'], st['calendar']['end']),
             'note': '%d 个交易日' % st['calendar']['n_days']},
        ]

    data = {
        'meta': {'title': meta.get('title') or '政策事件研究报告',
                 'tags': research.get('tags') or []},
        'toc': [{'id': 's%d' % i, 'label': l} for i, l in enumerate(
            ['结论', '数据与缺口', '候选库', '时间线', '可比性', '价格路径', '统计', '逐事件', '混杂因素', '局限'], 1)],
        'verdict': {'kpis': kpis, 'callouts': verdict.get('callouts') or research.get('callouts') or []},
        'dataQuality': research.get('dataQuality') or {'sources': [], 'gaps': []},
        'events': events,
        'comparability': research.get('comparability') or {'mergeable': False, 'verdict': '未评估',
                                                           'dimensions': [], 'groups': []},
        'stats': {'disclaimer': disclaimer, 'allow': any_allow, 'tables': tables,
                  'raw': raw, 'windowsAll': windows},
        'confounders': research.get('confounders') or [],
        'limits': research.get('limits') or [],
        'footer': research.get('footer') or '',
    }

    tpl_path = os.path.join(SKILL_ROOT, 'templates', 'policy_report.html')
    with open(tpl_path, 'r', encoding='utf-8') as f:
        html = f.read()

    html = html.replace('__TITLE__', data['meta']['title'])
    html = html.replace('__SUBTITLE__', meta.get('subtitle') or '')
    html = html.replace('__ECHARTS__', echarts_js)
    html = html.replace('__DATA__', json.dumps(data, ensure_ascii=False))
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--research', required=True)
    ap.add_argument('--study', required=True, help='event_study.py 输出的 event_stats.json')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    ej = find_echarts()
    if not ej:
        sys.exit('找不到 echarts.min.js，请在 assets/ 下放置')
    js = open(ej, 'r', encoding='utf-8').read()
    p = build(load(a.research), load(a.study), js, a.out)
    print('已生成 HTML：%s (%.2f MB)' % (p, os.path.getsize(p) / 1e6))


if __name__ == '__main__':
    main()
