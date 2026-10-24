#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""准备内置资源：ECharts、中国省界 GeoJSON、城市坐标库。

本 skill 默认已内置 assets/，无需联网。若是从精简包安装（assets 为空），
运行本脚本补齐；国内网络可直接用镜像地址。

用法: python fetch_assets.py [--check]
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')

ECHARTS = [
    'https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js',
    'https://unpkg.com/echarts@5.5.1/dist/echarts.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.1/echarts.min.js',
    'https://registry.npmmirror.com/echarts/5.5.1/files/dist/echarts.min.js',
]
GEO = [
    'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json',
    'https://cdn.jsdelivr.net/gh/apache/echarts-website@asf-site/examples/data/asset/geo/china.json',
]


def need(f):
    p = os.path.join(ASSETS, f)
    return not os.path.exists(p) or os.path.getsize(p) < 1024


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def try_urls(urls, dest, validate_fn):
    for u in urls:
        try:
            raw = get(u)
            validate_fn(raw)
            with open(dest, 'wb') as f:
                f.write(raw)
            print('  ok <- %s (%.1f KB)' % (u, len(raw) / 1024.0))
            return True
        except Exception as e:
            print('  fail %s -> %s' % (u, e))
    return False


def main():
    os.makedirs(ASSETS, exist_ok=True)
    check = '--check' in sys.argv
    ok = True
    if need('echarts.min.js'):
        print('下载 ECharts 5.5.1 ...')
        ok &= try_urls(ECHARTS, os.path.join(ASSETS, 'echarts.min.js'),
                       lambda b: b'echarts' in b[:4000])
    if need('china_prov.json'):
        print('下载中国省界 GeoJSON ...')
        ok &= try_urls(GEO, os.path.join(ASSETS, 'china_prov.json'),
                       lambda b: b'FeatureCollection' in b)
    for f in ('echarts.min.js', 'china_prov.json', 'city_centers.json'):
        p = os.path.join(ASSETS, f)
        print('%-20s %s' % (f, 'OK %.1f KB' % (os.path.getsize(p) / 1024.0)
                            if os.path.exists(p) else 'MISSING'))
    if check and not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
