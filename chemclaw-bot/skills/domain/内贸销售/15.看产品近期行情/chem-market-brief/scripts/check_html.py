# -*- coding: utf-8 -*-
"""看板静态自检（不需要浏览器）：
  python check_html.py out.html [data.json]
检查：占位符残留 / 外部依赖 / ECharts 是否内联 / 关键节点 id 是否齐全 /
      页面数字与 data.json 是否一致（抽样）/ 禁用词是否出现。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

REQUIRED_IDS = ['prodSel', 'regSel', 'winSel', 'kpiGrid', 'chart', 'spotTable', 'chgTable',
                'quantWrap', 'spreadChart', 'spreadBody', 'upList', 'downList', 'marginChart',
                'balBody', 'timeline', 'factGrid', 'talkList', 'msgout', 'gapGrid', 'srcList',
                'mask', 'drawer', 'dTitle', 'dBody']
BANNED = common.BANNED_WORDS       # 兼容旧引用
banned_hits = common.banned_hits   # 统一由 common 提供，三个检查器共用一套规则


def iter_strings(obj, path='$'):
    """递归产出 (路径, 字符串)。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(v, path + '.' + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, path + '[%d]' % i)
    elif isinstance(obj, str):
        yield path, obj


def extract_payload(html):
    """从 HTML 里取出 `const D = {...}` 的 JSON 对象。"""
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

    if 'const D = {' not in html:
        E.append('未找到内联数据 `const D = {...}`')

    payload = extract_payload(html)
    if payload is None:
        E.append('未能从 HTML 中取出内联数据（`const D = {...}` 解析失败）')
    else:
        for path, text in iter_strings(payload):
            # 客户原话（talk[].q）允许出现方向词，回答（a）不允许
            if path.endswith('.q'):
                continue
            for b in banned_hits(text):
                E.append('数据出现方向性表述「%s」于 %s：%s' % (b, path, text[:60]))

    # 数据一致性抽样
    if data_path and os.path.exists(data_path):
        with open(data_path, encoding='utf-8') as f:
            D = json.load(f)
        def has(v, dec=0):
            if v is None:
                return True
            s = format(round(float(v), dec), ',.%df' % dec)
            if s in html:
                return True
            # JS 用 toLocaleString 生成，源码里只存原始数字
            return (str(round(float(v), dec)) in html)
        checks = []
        if D.get('anchor'):
            checks.append(('现货锚', D['anchor'].get('value')))
        if D.get('last', {}).get('close') is not None:
            checks.append(('期货收盘', D['last']['close']))
        if D.get('win', {}).get('1y'):
            checks.append(('1年低点', D['win']['1y']['low']))
            checks.append(('1年高点', D['win']['1y']['high']))
        miss = [n for n, v in checks if not has(v)]
        if miss:
            W.append('以下数字未在 HTML 源码中出现（若由 JS 计算可忽略）：%s' % '、'.join(miss))

        m = D['meta']
        if m.get('product') and m['product'] not in html:
            E.append('页面未出现品种名「%s」' % m['product'])
        if m.get('asof') and m['asof'] not in html:
            E.append('页面未出现数据基准日「%s」' % m['asof'])

    # 缺口必须出现在页面上
    if data_path and os.path.exists(data_path):
        with open(data_path, encoding='utf-8') as f:
            D = json.load(f)
        gaps = D.get('gaps') or []
        if not gaps:
            W.append('data.json 的 gaps 为空——请确认所有字段确有来源，否则应登记缺口')
        hit = sum(1 for g in gaps if (g.get('item') or '') and g['item'] in html)
        if gaps and hit == 0:
            E.append('缺口列表未渲染到页面：%d 条缺口一条都没出现' % len(gaps))
        elif gaps and hit < len(gaps):
            W.append('仅 %d/%d 条缺口项目名出现在 HTML（其余可能只在 data.json 里）' % (hit, len(gaps)))

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
