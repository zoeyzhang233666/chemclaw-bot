#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把结果 JSON 注入 HTML 模板，生成单文件离线看板（内联 ECharts，零外链）。

占位符：__TITLE__ __ECHARTS__ __DATA__
HTML 端只做"重算"，公式与 Python 引擎逐字对应（见 assets/app.js 顶部同源公式说明）。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def build_html(result, path, title=None):
    tpl_path = os.path.join(HERE, 'templates', 'dashboard.html')
    with open(tpl_path, encoding='utf-8') as f:
        tpl = f.read()
    with open(os.path.join(HERE, 'assets', 'echarts.min.js'), encoding='utf-8') as f:
        ec = f.read()
    with open(os.path.join(HERE, 'assets', 'app.js'), encoding='utf-8') as f:
        app = f.read()
    payload = json.dumps(result, ensure_ascii=False, default=str)
    payload = payload.replace('</', '<\\/')     # 防 </script> 截断
    app = app.replace('</script', '<\\/script')
    t = title or '%s · 理论原料成本模型' % (result.get('meta') or {}).get('product', '')
    html = (tpl.replace('__TITLE__', t)
               .replace('/*__ECHARTS_PLACEHOLDER__*/', ec)
               .replace('/*__DATA_PLACEHOLDER__*/null', payload)
               .replace('/*__APP_PLACEHOLDER__*/', app))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return path
