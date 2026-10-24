#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令：校验 → HTML → Excel → 体检。

用法:
  python build_all.py regions.json --out out --name 纯碱-山东
  python build_all.py regions.json --out out --name 纯碱-山东 --qa --shot out/qa/shot.png
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_html  # noqa: E402
import build_xlsx  # noqa: E402
import common  # noqa: E402
import validate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', default='out')
    ap.add_argument('--name', default=None, help='文件名前缀，默认 品种-区域')
    ap.add_argument('--html-only', action='store_true')
    ap.add_argument('--xlsx-only', action='store_true')
    ap.add_argument('--skip-validate', action='store_true')
    ap.add_argument('--strict', action='store_true', help='warning 也算失败')
    ap.add_argument('--qa', action='store_true', help='构建后跑 qa.py')
    ap.add_argument('--shot', default=None, help='QA 截图路径')
    a = ap.parse_args()

    with open(a.data, encoding='utf-8') as f:
        raw = json.load(f)
    if not a.skip_validate:
        E, W = validate.check(raw)
        for x in E:
            print('[ERROR]', x)
        for x in W:
            print('[WARN ]', x)
        print('—— validate: error %d / warning %d' % (len(E), len(W)))
        if E or (a.strict and W):
            sys.exit('校验未通过，阻断构建')

    D = common.load(a.data)
    M = D['meta']
    name = a.name or ('%s-%s' % (M.get('product', '').split('（')[0], M.get('region', '').split('（')[0]))
    os.makedirs(a.out, exist_ok=True)
    html_path = os.path.join(a.out, name + '产业格局地图.html')
    xlsx_path = os.path.join(a.out, name + '产业格局数据包.xlsx')
    M['html_name'] = os.path.basename(html_path)
    if not a.xlsx_only:
        build_html.build(a.data, html_path)
    if not a.html_only:
        build_xlsx.build(a.data, xlsx_path)
    if a.qa:
        cmd = [sys.executable, os.path.join(HERE, 'qa.py'), html_path, xlsx_path, a.data]
        if a.shot:
            cmd += ['--shot', a.shot]
        rc = subprocess.call(cmd)
        if rc != 0:
            sys.exit('QA 未通过')


if __name__ == '__main__':
    main()
