# -*- coding: utf-8 -*-
"""组装单文件 HTML（内联 ECharts + 冻结数据），保证离线可开、可分发。

  output/*.html  <- tmpl/dashboard.html + assets/echarts.min.js + build/{data,history}.json
"""
import os
import json
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, 'build')
OUT = os.path.join(ROOT, 'output')
os.makedirs(OUT, exist_ok=True)


def build(name='PVC电石法-产业链利润研究与成本计算器.html'):
    tmpl = open(os.path.join(ROOT, 'tmpl', 'dashboard.html'), encoding='utf-8').read()
    appjs = open(os.path.join(ROOT, 'tmpl', 'app.js'), encoding='utf-8').read()
    echarts = open(os.path.join(ROOT, 'assets', 'echarts.min.js'), encoding='utf-8').read()
    data = json.load(open(os.path.join(BUILD, 'data.json'), encoding='utf-8'))
    hist = json.load(open(os.path.join(BUILD, 'history.json'), encoding='utf-8'))
    anchors = json.load(open(os.path.join(BUILD, 'carbide_anchors.json'), encoding='utf-8'))

    from engine import DEFAULT
    payload = {'data': data, 'history': hist, 'anchors': anchors, 'defaults': DEFAULT}
    js = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

    html = tmpl.replace('/*__ECHARTS__*/', echarts)
    html = html.replace('/*__PAYLOAD__*/', js)
    html = html.replace('/*__APP__*/', appjs)
    assert '/*__' not in html, 'placeholder not fully replaced'
    path = os.path.join(OUT, name)
    open(path, 'w', encoding='utf-8').write(html)
    print('[OK] %s  %.1f KB' % (path, len(html.encode('utf-8')) / 1024))
    return path


if __name__ == '__main__':
    build()
