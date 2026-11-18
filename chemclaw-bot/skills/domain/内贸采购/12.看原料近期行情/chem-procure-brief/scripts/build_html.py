# -*- coding: utf-8 -*-
"""data.json + 模板 + 内联 ECharts -> 单文件离线 HTML。

用法：
  python build_html.py data.json --out out/<品种>-<地区>_原料行情底稿_采购.html
  python build_html.py data.json --out x.html --no-inline-echarts   # 调试用，需本地有 echarts.min.js

产物：零外链（无 CDN、无外部 js/css），双击即开，可发微信/邮件附件。
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

HERE = os.path.dirname(os.path.abspath(__file__))


def find_echarts(explicit=None):
    cands = [explicit] if explicit else []
    cands += [
        os.path.join(HERE, 'assets', 'echarts.min.js'),
        os.path.join(HERE, '..', 'assets', 'echarts.min.js'),
        os.path.join(HERE, '..', 'assets', 'scripts', 'assets', 'echarts.min.js'),
        os.path.expanduser('~/.agents/skills/chemical-region-market-map/scripts/assets/echarts.min.js'),
    ]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def build(data_path, out_path, echarts_path=None, inline=True, template=None):
    D = common.load_json(data_path)
    tpl_path = template or os.path.join(HERE, 'templates', 'dashboard.html')
    with open(tpl_path, encoding='utf-8') as f:
        html = f.read()
    template_hash = hashlib.sha256(html.encode('utf-8')).hexdigest()
    html = html.replace('<head>', '<head>\n<meta name="chemclaw-template-sha256" content="' + template_hash + '">', 1)

    meta = D['meta']
    h1suffix = '原料行情底稿 · 采购视角'
    sub = meta['subtitle']
    title = '%s（%s）原料行情底稿（采购） | %s' % (meta['product'], meta.get('region', ''), meta['asof'])

    html = html.replace('__TITLE__', _esc(title))
    html = html.replace('__H1SUFFIX__', h1suffix)
    html = html.replace('__PRODUCT__', _esc(meta['product']))
    html = html.replace('__SUB__', sub)
    html = html.replace('__DATA__', json.dumps(D, ensure_ascii=False, separators=(',', ':')))

    if inline:
        ep = find_echarts(echarts_path)
        if not ep:
            common.die('找不到 echarts.min.js。请把 echarts.min.js 放到 scripts/assets/，'
                       '或用 --echarts 指定路径；也可以加 --no-inline-echarts 走外链调试。')
        with open(ep, encoding='utf-8') as f:
            js = f.read()
        html = html.replace('__ECHARTS__', js)
    else:
        html = html.replace('<script>__ECHARTS__</script>', '<script src="echarts.min.js"></script>')

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # 自检：不能残留占位符、不能有外部 <script src>
    problems = []
    for token in ('__DATA__', '__ECHARTS__', '__TITLE__', '__PRODUCT__', '__SUB__', '__H1SUFFIX__'):
        if token in html:
            problems.append('占位符未替换：' + token)
    import re
    ext = re.findall(r'<script[^>]+src="(https?://[^"]+)"', html)
    if inline and ext:
        problems.append('仍有外部脚本：' + ', '.join(ext))
    return {'path': out_path, 'bytes': os.path.getsize(out_path), 'external': ext, 'problems': problems}


def _esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', required=True)
    ap.add_argument('--echarts', default=None, help='echarts.min.js 路径')
    ap.add_argument('--no-inline-echarts', action='store_true')
    ap.add_argument('--template', default=None)
    a = ap.parse_args()
    r = build(a.data, a.out, a.echarts, not a.no_inline_echarts, a.template)
    for p in r['problems']:
        common.warn(p)
    common.ok('HTML 已生成 %s（%.2f MB）' % (r['path'], r['bytes'] / 1048576))
    if r['problems']:
        sys.exit(1)


if __name__ == '__main__':
    main()
