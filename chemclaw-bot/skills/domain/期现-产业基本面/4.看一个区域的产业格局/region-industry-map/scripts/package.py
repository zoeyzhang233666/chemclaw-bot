#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把技能目录打成可分发 ZIP（排除 __pycache__、临时截图、系统垃圾文件）。

用法:
  python package.py                       # 输出到上一级 region-industry-map.zip
  python package.py --out D:/some/dir     # 输出到指定目录
  python package.py --no-example-assets   # 不带示例产物（只留 regions.json，包更小）
"""
import argparse
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAME = os.path.basename(ROOT)

SKIP_DIRS = {'__pycache__', '.git', '.idea', '.vscode', 'node_modules'}
SKIP_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}
SKIP_EXT = {'.pyc', '.pyo', '.tmp', '.log', '.bak'}
BIG_EXAMPLE_EXT = {'.html', '.xlsx'}


def walk(skip_example_assets=False):
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn in SKIP_FILES:
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_EXT:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            # 示例区里的大产物可以跳过（示例能由 regions.json 重新生成）
            if skip_example_assets and os.sep + 'examples' + os.sep in os.sep + rel \
                    and ext in BIG_EXAMPLE_EXT:
                continue
            out = os.path.join(NAME, rel)
            if os.sep + 'out' + os.sep in os.sep + out and not rel.startswith('examples'):
                continue  # 构建输出目录不进包
            yield full, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.dirname(ROOT), help='ZIP 输出目录')
    ap.add_argument('--no-example-assets', action='store_true', help='不打包示例 HTML/XLSX 产物')
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(a.out, NAME + '.zip')
    files = list(walk(a.no_example_assets))
    if not files:
        print('没有可打包的文件', file=sys.stderr)
        return 1
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for full, arc in files:
            z.write(full, arc)
    total = os.path.getsize(zpath)
    raw = sum(os.path.getsize(f) for f, _ in files)
    print('ZIP →', zpath)
    print('  文件 %d 个 · 原始 %.1f MB · 压缩后 %.1f MB' % (len(files), raw / 1048576, total / 1048576))
    # 自检：必须含关键文件
    need = ['SKILL.md', 'README.md', 'references/geo-verification-and-aggregation.md',
            'scripts/validate.py', 'scripts/build_html.py', 'scripts/build_xlsx.py',
            'scripts/assets/echarts.min.js', 'scripts/assets/china_prov.json',
            'scripts/templates/report.html']
    with zipfile.ZipFile(zpath) as z:
        names = set(z.namelist())
    missing = [n for n in need if (NAME + '/' + n) not in names]
    if missing:
        print('  缺少关键文件：', missing, file=sys.stderr)
        return 1
    print('  关键文件齐全')
    return 0


if __name__ == '__main__':
    sys.exit(main())
