# -*- coding: utf-8 -*-
"""生成自包含交互式 HTML 月差分析报告（无外部依赖、无网络请求）。

用法
----
    python scripts/build_html.py --data build/enriched.json \
        --out examples/SA-2612-2701/spread-report.html

交互
----
* 月份组合切换：同一天（或指定历史日期）下，所有挂牌合约对的月差都可切换
* 近远月顺序切换：A−B / B−A
* 近月锚切换：以哪个合约作为基准月（决定阅读方向，不改变 A−B 定义）
* 历史日期回放：拖动时间轴，期限结构 + 月差 + 当期仓单联动
* 点击异常月差阶段 / 月差曲线任一点：显示同期仓单、库存、装置事件
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(os.path.dirname(HERE), 'assets', 'templates', 'spread-report-template.html')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='build_panel.py 产出的 enriched.json')
    ap.add_argument('--out', required=True)
    ap.add_argument('--template', default=TPL)
    ap.add_argument('--title', default=None)
    args = ap.parse_args(argv)

    with open(args.data, encoding='utf-8') as f:
        data = json.load(f)

    # 只注入报告需要的字段，避免把整个面板的冗余字段塞进 HTML
    slim = {
        'meta': data['meta'], 'contracts': data['contracts'], 'spread': data['spread'],
        'change': data['change'], 'percentile': data['percentile'],
        'term_structure': data['term_structure'], 'comparable': data['comparable'],
        'decomposition': data['decomposition'], 'roll': data['roll'],
        'warehouse': data['warehouse'], 'events': data['events'],
        'data_quality': data['data_quality'], 'shape_history': data['shape_history'],
        'ts_history': data['ts_history'], 'story': data['story'],
        'panel_meta': data.get('panel_meta', {}),
        # 面板只保留展示所需字段
        'panel': [{k: r[k] for k in ('date', 'contract', 'y', 'm', 'price', 'oi', 'dtd', 'ts')}
                  for r in data['panel']],
    }
    with open(args.template, encoding='utf-8') as f:
        html = f.read()
    title = args.title or (f"{data['meta']['product']} {data['contracts']['a']}－{data['contracts']['b']} "
                           f"月差分析报告 {data['meta']['asof']}")
    payload = json.dumps(slim, ensure_ascii=False, separators=(',', ':'))
    html = html.replace('/*__DATA__*/null', payload)
    html = html.replace('__TITLE__', title)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'HTML {len(html):,} 字符 -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
