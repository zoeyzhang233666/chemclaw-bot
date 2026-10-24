#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令生成 HTML + Excel（skill 的入口）。

用法:
  python build_all.py data.json --out out [--name 纯碱-华东] [--perday 4] [--skip-validate]
"""
import argparse
import os
import sys

import build_html
import build_xlsx
import common
import validate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', default='out')
    ap.add_argument('--name', default=None, help='输出文件名前缀，默认 产品-区域')
    ap.add_argument('--perday', type=int, default=4, help='每日有效拜访家数')
    ap.add_argument('--html-only', action='store_true')
    ap.add_argument('--xlsx-only', action='store_true')
    ap.add_argument('--skip-validate', action='store_true')
    a = ap.parse_args()

    if not a.skip_validate:
        import json
        with open(a.data, encoding='utf-8') as f:
            D0 = json.load(f)
        E, W = validate.check(D0)
        for x in E:
            print('[ERROR]', x)
        for x in W:
            print('[WARN ]', x)
        if E:
            sys.exit('校验未通过：先修 data.json（error 会阻断构建）')

    if a.perday != 4:
        D = common.load(a.data, perday=a.perday)
        import json as _j
        tmp = os.path.join(a.out, '_data_perday.json')
        os.makedirs(a.out, exist_ok=True)
        with open(tmp, 'w', encoding='utf-8') as f:
            _j.dump(D, f, ensure_ascii=False)
        data_path = tmp
    else:
        data_path = a.data

    meta = common.load(a.data)['meta']
    name = a.name or ('%s-%s' % (meta['product'].split('（')[0], meta['region'].split('（')[0]))
    os.makedirs(a.out, exist_ok=True)
    if not a.xlsx_only:
        html_name = name + ('市场地图.html' if name.endswith('区域') else '区域市场地图.html')
        build_html.build(data_path, os.path.join(a.out, html_name))
    if not a.html_only:
        build_xlsx.build(data_path, os.path.join(a.out, name + '客户分布与走访优先级.xlsx'))


if __name__ == '__main__':
    main()
