#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chem-capacity-impact · 单文件交互式 HTML 报告生成

- 模板：scripts/templates/report.html（结构与样式，可改）
- 图表库：scripts/assets/echarts.min.js（内联，保证离线可用）
- 数据：compute.compute_all(project) 的输出，序列化为内嵌 JSON

安全：注入 <script> 的 JSON 会转义 </、<!--、-->、U+2028/2029，避免提前闭合。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, 'templates', 'report.html')
ECHARTS = os.path.join(HERE, 'assets', 'echarts.min.js')


def json_for_script(obj: Any) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    s = s.replace('</', '<\\/')
    s = s.replace('<!--', '<\\u0021--')
    s = s.replace('-->', '--\\u003e')
    s = s.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return s


def build(data: Dict[str, Any], out_path: str,
          template: Optional[str] = None,
          echarts: Optional[str] = None) -> str:
    tpl_path = template or TEMPLATE
    with open(tpl_path, 'r', encoding='utf-8') as fh:
        html = fh.read()

    with open(echarts or ECHARTS, 'r', encoding='utf-8') as fh:
        lib = fh.read()

    meta = data.get('meta') or {}
    title = meta.get('title') or '新增产能影响研究报告'

    # 1) 先放数据（占位符替换）
    payload = json_for_script(data)
    if '__DATA__' not in html:
        raise SystemExit('[error] 模板缺少 __DATA__ 占位符')
    html = html.replace('__DATA__', payload)
    html = html.replace('__TITLE__', _esc_title(title))

    # 2) 内联图表库：插到 </head> 前，避免阻塞正文解析顺序问题
    script_tag = '<script>/* Apache ECharts 5.6.0 (Apache-2.0) - inlined for offline use */\n' + lib + '\n</script>\n'
    lib = None  # help GC
    if '</head>' in html:
        head_break = html.find('<link rel="stylesheet"')
        html = html.replace('</head>', script_tag + '</head>', 1)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    return out_path


def _esc_title(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;'))


if __name__ == '__main__':
    import argparse
    import sys
    sys.path.insert(0, HERE)
    from compute import compute_all

    ap = argparse.ArgumentParser()
    ap.add_argument('project_json')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    with open(a.project_json, 'r', encoding='utf-8-sig') as fh:
        pj = json.load(fh)
    print(build(compute_all(pj), a.out))
