# -*- coding: utf-8 -*-
"""报告静态自检（不需要浏览器，采购版）：
  python check_html.py out.html [data.json]

检查：占位符残留 / 外部依赖 / ECharts 是否内联 / 关键节点 id 是否齐全 /
      页面数据与 data.json 是否同源 / 禁用词 / 缺口是否真的渲染 / 是否有“只报喜”式的隐藏。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

REQUIRED_IDS = ['ptSel', 'winSel', 'kpiGrid', 'chart', 'chartTabs', 'ckCost', 'ckMark',
                'spotTable', 'chgTable', 'winTable', 'spreadChart', 'spreadTable',
                'costChart', 'routeTable', 'upList', 'downList', 'proofTable',
                'balBody', 'timeline', 'tlFilter', 'factGrid', 'msgSec', 'msgout', 'talkList',
                'gapGrid', 'srcList', 'summaryBar', 'warnText', 'mask', 'drawer', 'dTitle', 'dBody']
banned_hits = common.banned_hits


def iter_strings(obj, path='$'):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(v, path + '.' + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, path + '[%d]' % i)
    elif isinstance(obj, str):
        yield path, obj


def extract_payload(html):
    i = html.find('const D = {')
    if i < 0:
        return None
    start = html.find('{', i)
    depth, j = 0, start
    in_str, esc, quote = False, False, ''
    while j < len(html):
        ch = html[j]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == quote:
                in_str = False
        else:
            if ch in '"\'':
                in_str, quote = True, ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    break
        j += 1
    try:
        return json.loads(html[start:j + 1])
    except Exception:
        return None


def check(html_path, data_path=None):
    with open(html_path, encoding='utf-8') as f:
        html = f.read()
    E, W = [], []
    size = os.path.getsize(html_path)

    for tok in ('__DATA__', '__ECHARTS__', '__TITLE__', '__PRODUCT__', '__SUB__', '__H1SUFFIX__'):
        if tok in html:
            E.append('占位符未替换：%s' % tok)

    ext = re.findall(r'<(?:script|link)[^>]+(?:src|href)="(https?://[^"]+)"', html)
    if ext:
        E.append('存在外部资源引用（离线打开会失效）：%s' % ', '.join(sorted(set(ext))[:5]))

    if 'echarts' not in html.lower():
        E.append('未检测到 ECharts，图表将无法渲染')
    elif len(html) < 400000:
        W.append('HTML 只有 %.0f KB，ECharts 可能未内联' % (len(html) / 1024))

    for i in REQUIRED_IDS:
        if 'id="%s"' % i not in html:
            E.append('缺少节点 id="%s"' % i)

    # 采购版必须有的三句话：不预测 / 六项口径 / 证据级别
    for kw, why in [('不预测', '首屏必须声明“不预测价格”'),
                    ('含税', '报价必须标含税口径'),
                    ('提货', '报价必须标提货方式（出厂/送到/库提）'),
                    ('证据', '事件必须标证据级别'),
                    ('缺口', '必须显式列出数据缺口')]:
        if kw not in html:
            E.append('页面缺少「%s」相关表述（%s）' % (kw, why))

    if 'const D = {' not in html:
        E.append('未找到内联数据 `const D = {...}`')

    payload = extract_payload(html)
    if payload is None:
        E.append('未能从 HTML 中取出内联数据（`const D = {...}` 解析失败）')
    else:
        for path, text in iter_strings(payload):
            if path.endswith('.q'):
                continue           # 供应商原话允许出现方向词，回答不允许
            for b in banned_hits(text):
                E.append('数据出现方向性表述「%s」于 %s：%s' % (b, path, text[:60]))

    if data_path and os.path.exists(data_path):
        with open(data_path, encoding='utf-8') as f:
            D = json.load(f)

        def has(v, dec=0):
            if v is None:
                return True
            s = format(round(float(v), dec), ',.%df' % dec)
            return s in html or (str(round(float(v), dec)) in html)

        checks = []
        if D.get('anchor'):
            checks.append(('锚价', D['anchor'].get('value')))
        p = D.get('primary') or {}
        w90 = (p.get('win') or {}).get('90')
        if w90:
            checks += [('90天低点', w90['low']), ('90天高点', w90['high'])]
        if (D.get('quotes') or []):
            checks.append(('首条报价中值', D['quotes'][0]['mid']))
        miss = [n for n, v in checks if not has(v)]
        if miss:
            W.append('以下数字未在 HTML 源码中出现（若由 JS 计算可忽略）：%s' % '、'.join(miss))

        m = D['meta']
        if m.get('product') and m['product'] not in html:
            E.append('页面未出现品种名「%s」' % m['product'])
        if m.get('asof') and m['asof'] not in html:
            E.append('页面未出现数据基准日「%s」' % m['asof'])

        gaps = D.get('gaps') or []
        if not gaps:
            W.append('data.json 的 gaps 为空——请确认所有字段确有来源，否则应登记缺口')
        hit = sum(1 for g in gaps if (g.get('item') or '') and g['item'] in html)
        if gaps and hit == 0:
            E.append('缺口列表未渲染到页面：%d 条缺口一条都没出现' % len(gaps))
        elif gaps and hit < len(gaps):
            W.append('仅 %d/%d 条缺口项目名出现在 HTML' % (hit, len(gaps)))

        # 事件必须带证据级别，且传闻不得进入时间线数据区
        for e in (D.get('events') or []):
            if e.get('evidence') in ('传闻', '待确认'):
                E.append('传闻进入了时间线：%s' % e.get('title', '')[:30])
        if D.get('events_rejected') and '未采纳消息' not in html:
            W.append('有 %d 条未采纳消息但页面没有单独区隔' % len(D['events_rejected']))

        # 产业链断点：未通过的必须被标出来
        bad = [x for x in (D.get('chain_proof') or []) if not x.get('checked')]
        if bad and '未通过' not in html:
            W.append('有 %d 条链断点未通过核对，但页面没有“未通过”标识' % len(bad))

        # 采购参数
        pr = D.get('procurement') or {}
        if pr.get('inventory_days') is None:
            W.append('未填采购库存天数：首屏少一张“库存可支撑到哪天”的卡')

    return E, W, {'bytes': size, 'mb': round(size / 1048576, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('data', nargs='?')
    a = ap.parse_args()
    E, W, info = check(a.html, a.data)
    for x in E:
        print('[ERROR]', x)
    for x in W:
        print('[WARN ]', x)
    print('== %s ｜ %.2f MB ｜ %d error ｜ %d warn' % (a.html, info['mb'], len(E), len(W)))
    sys.exit(1 if E else 0)


if __name__ == '__main__':
    main()
