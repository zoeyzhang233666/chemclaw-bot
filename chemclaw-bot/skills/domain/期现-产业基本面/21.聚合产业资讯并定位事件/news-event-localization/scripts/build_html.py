#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the self-contained interactive HTML dashboard from a case's src/*.json.

Usage:
    python build_html.py <case_dir> [-o out.html] [--template path]

Inlines the whole dataset into templates/dashboard.html at the /*__DATA__*/null
placeholder, producing a single file that opens offline with no network.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
DEFAULT_TPL = os.path.join(SKILL, 'templates', 'dashboard.html')
PLACEHOLDER = '/*__DATA__*/null'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('case_dir')
    ap.add_argument('-o', '--out', default=None)
    ap.add_argument('--template', default=DEFAULT_TPL)
    a = ap.parse_args()

    s = os.path.join(a.case_dir, 'src')

    def j(n):
        with open(os.path.join(s, n), encoding='utf-8') as f:
            return json.load(f)

    sources_doc = j('sources.json')
    events_doc = j('events.json')
    ent = j('entities.json')
    chain = j('chain.json')
    ded = j('dedupe.json')

    data = {
        'meta': sources_doc.get('meta', {}),
        'sources': sources_doc.get('sources', []),
        'limitations': sources_doc.get('limitations', []),
        'news': j('news.json').get('items', []),
        'events': events_doc.get('events', []),
        'event_meta': events_doc.get('meta', {}),
        'companies': ent.get('companies', []),
        'plants': ent.get('plants', []),
        'nodes': chain.get('nodes', []),
        'edges': chain.get('edges', []),
        'indicators': chain.get('indicators', []),
        'links': ded.get('links', []),
        'unassigned': ded.get('unassigned', []),
        'questions': j('toverify.json').get('questions', []),
    }

    if not os.path.exists(a.template):
        print(f'找不到模板：{a.template}')
        return 2
    html = open(a.template, encoding='utf-8').read()
    if PLACEHOLDER not in html:
        print(f'模板中缺少占位符 {PLACEHOLDER}')
        return 2

    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('</', '<\\/')  # keep </script> from closing the tag
    html = html.replace(PLACEHOLDER, payload)

    out = a.out or os.path.join(a.case_dir, 'out',
                                f"资讯事件定位看板_{data['meta'].get('case_id','case')}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'saved {out} ({len(html.encode("utf-8"))/1024:.1f} KB)')
    print(f"  事件 {len(data['events'])} | 资讯 {len(data['news'])} | 源 {len(data['sources'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())