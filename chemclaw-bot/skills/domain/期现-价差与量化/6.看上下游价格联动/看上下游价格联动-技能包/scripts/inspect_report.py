# -*- coding: utf-8 -*-
"""inspect_report.py —— 检查报告 HTML 的结构完整性与关键数字"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'build', 'report.html')
s = open(path, encoding='utf-8').read()

print('size KB', round(len(s) / 1024))
secs = re.findall(r'id="(s\d+)"', s)
print('sections', sorted(set(secs)))
cans = re.findall(r'<canvas id="(c\w+)"', s)
print('canvases', cans)
print('has __A__ payload', '__A__' in s)
print('has css inline', '--bg' in s)
print('has js inline', 'function' in s)

# 关键数值是否出现在正文里（用作 sanity check）
A = json.load(open(os.path.join(HERE, 'build', 'analysis.json'), encoding='utf-8'))
keys = {
    'level r': f"{A['corr']['level']['r']:.3f}",
    'return r': f"{A['corr']['return']['r']:.3f}",
    'mean spread': f"{A['spread']['mean']:.1f}",
}
for k, v in keys.items():
    print(f'{k} ({v}) present:', v in s)

# 检查是否有占位符未替换
for token in ('{{', 'undefined', 'NaN'):
    print(f'token {token!r}:', s.count(token))
