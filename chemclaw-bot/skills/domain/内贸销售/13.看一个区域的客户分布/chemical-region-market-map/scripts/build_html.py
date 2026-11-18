#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成自包含 HTML（内联 ECharts + 中国省界 GeoJSON + 数据）。

用法: python build_html.py data.json out.html
"""
import json
import os
import sys

import common

HERE = os.path.dirname(os.path.abspath(__file__))


def build(data_path, out_path):
    D = common.load(data_path)
    payload = common.payload(D)
    tpl_path = os.path.join(HERE, 'templates', 'dashboard.html')
    with open(tpl_path, encoding='utf-8') as f:
        html = f.read()

    ech = os.path.join(HERE, 'assets', 'echarts.min.js')
    geo = os.path.join(HERE, 'assets', 'china_prov.json')
    for p in (ech, geo):
        if not os.path.exists(p):
            raise SystemExit('缺少资源 %s（运行 python fetch_assets.py 或手动放入）' % p)

    echarts_src = open(ech, encoding='utf-8', errors='ignore').read()
    echarts_src = echarts_src.replace('</script', '<\\/script')
    geo_src = open(geo, encoding='utf-8', errors='ignore').read()
    data_src = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

    title = D['meta'].get('title') or '%s · %s 区域市场地图' % (D['meta']['product'], D['meta']['region'])
    title = title.replace('<', '&lt;')

    # 占位符计数校验：防止「替换值本身包含占位符」导致重复替换
    for ph, allowed in (('__ECHARTS__', 1), ('%%GEO%%', 1), ('%%DATA%%', 1), ('__TITLE__', 1)):
        n = html.count(ph)
        if n != allowed:
            raise SystemExit('模板占位符 %s 出现 %d 次（应为 %d）' % (ph, n, allowed))

    html = html.replace('__TITLE__', title)
    html = html.replace('__ECHARTS__', echarts_src)
    html = html.replace('%%GEO%%', geo_src)
    html = html.replace('%%DATA%%', data_src)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('OK %s  %.2f MB' % (out_path, os.path.getsize(out_path) / 1048576.0))
    return out_path


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'data.json',
          sys.argv[2] if len(sys.argv) > 2 else 'out/map.html')
