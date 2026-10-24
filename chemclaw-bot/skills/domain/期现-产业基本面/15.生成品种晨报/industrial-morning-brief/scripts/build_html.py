# -*- coding: utf-8 -*-
"""生成单文件离线互动HTML晨报（ECharts 内联，零外链、可微信直发）。

用法：
  python build_html.py build/data.json --out out/晨报.html

交互能力（对应 SKILL.md「交付物」要求）：
- 首屏品种摘要卡 → 点击跳到对应模块；
- 每个品种 5 个折叠模块：价格 / 基差月差 / 装置 / 库存开工 / 事件；
- 每条变化可点开右侧抽屉，看原始数据、算法、来源、历史记录、继续验证项；
- 顶部筛选：按品种、按重要性（A必看/B记录/C噪声）、只看有变化；
- 上期对比切换：同一指标显示「上期值 → 本期值 → 变动」；
- 历史晨报：内置基线指标，可切到上一期视图。
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, 'templates', 'brief.html')
ECHARTS = os.path.join(HERE, 'assets', 'echarts.min.js')

MODULE_ORDER = [
    ('price', '价格与价差', '最新现货/期货价格、涨跌幅、区域价差'),
    ('basis', '基差与月差', '期现结构与合约间结构'),
    ('plant', '装置与产能', '新增停车、检修、复产、投产'),
    ('inventory', '库存与开工', '库存、开工、产量、下游需求'),
    ('event', '政策与事件', '有明确产业影响路径的事件'),
]

TIER_LABEL = {'A': 'A 必看', 'B': 'B 记录', 'C': 'C 噪声'}
TIER_CLASS = {'A': 'tier-a', 'B': 'tier-b', 'C': 'tier-c'}


def esc(s):
    return (str(s if s is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def arrow(v):
    if v is None:
        return '<span class="flat">—</span>'
    if v > 0:
        return '<span class="up">▲</span>'
    if v < 0:
        return '<span class="down">▼</span>'
    return '<span class="flat">■</span>'


def signed(v, d=2, unit=''):
    if v is None:
        return '—'
    s = ('+' if v > 0 else '') + format(round(float(v), d), ',.%df' % d)
    return s + unit


def build_payload(data):
    """只把 HTML 需要的字段送进模板，避免整表塞进页面。"""
    inds = []
    for i in data['indicators']:
        inds.append({
            'id': i['id'], 'product': i['product'], 'module': i['module'],
            'name': i['name'], 'spec': i['spec'], 'region': i['region'],
            'unit': i['unit'], 'tax': i['tax'], 'freq': i['freq'],
            'current': i['current'], 'current_date': i['current_date'],
            'base': i['base'], 'base_date': i['base_date'],
            'base_source': i['base_source'],
            'abs': i['abs'], 'pct': i['pct'],
            'is_new': i['is_new'], 'stale_days': i['stale_days'],
            'tier': i['significance'],
            'source': i['source'], 'source_url': i['source_url'],
            'formula': i['formula'], 'what': i['what'], 'why': i['why'],
            'verify': i['verify'], 'history': i['history'],
        })
    evs = []
    for e in data['events']:
        evs.append({
            'id': e.get('id'), 'products': e.get('products') or [],
            'type': e.get('event_type_cn') or e.get('event_type'), 'entity': e.get('entity'),
            'title': e.get('title'), 'detail': e.get('detail'),
            'event_date': e.get('event_date'), 'quant': e.get('quant'),
            'impact_path': e.get('impact_path'), 'status': e.get('status'),
            'tier': e.get('tier'), 'score': e.get('score'),
            'dup_count': e.get('dup_count', 0), 'dup_sources': e.get('dup_sources') or [],
            'dedupe_note': e.get('dedupe_note', ''), 'repeat_note': e.get('repeat_note', ''),
            'exclude_reason': e.get('exclude_reason', ''),
            'stale_days': e.get('stale_days'),
            'source': e.get('source'), 'source_url': e.get('source_url'),
        })
    return {'report': data['report'], 'profile': data.get('profile', {}),
            'baseline': data['baseline'], 'futures': data['futures'],
            'indicators': inds, 'events': evs, 'summary': data['summary'],
            'excluded': data.get('excluded', []), 'gaps': data.get('gaps', []),
            'sources': data.get('sources', []), 'chain': data.get('chain', {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', required=True)
    ap.add_argument('--template', default=TPL)
    a = ap.parse_args()

    data = common.load_json(a.data)
    payload = build_payload(data)
    tpl = open(a.template, encoding='utf-8').read()

    echarts = open(ECHARTS, encoding='utf-8').read() if os.path.exists(ECHARTS) else ''
    if not echarts:
        common.warn('未找到 assets/echarts.min.js，图表将降级为表格显示')

    html = (tpl.replace('/*__ECHARTS__*/', echarts)
               .replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False))
               .replace('__TITLE__', esc(payload['report']['title']))
               .replace('__REPORT_DATE__', esc(payload['report']['report_date']))
               .replace('__BUILD_TIME__', datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)
    common.ok('HTML 已生成：%s（%.2f MB）' % (a.out, os.path.getsize(a.out) / 1048576))


if __name__ == '__main__':
    main()
