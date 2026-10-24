# -*- coding: utf-8 -*-
"""用内置 JS 引擎（PowerShell 不适用）之外的最简方式校验 HTML 内嵌数据与关键片段。"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(os.path.dirname(HERE), 'docs', 'correlation-report.html')
h = open(p, encoding='utf-8').read()
print('size', len(h))
m = re.search(r'const PAYLOAD = (\{.*?\});\nconst S =', h, re.S)
if not m:
    print('FAIL payload not found')
    sys.exit(1)
payload = json.loads(m.group(1))
print('dates', len(payload['dates']), payload['dates'][0], payload['dates'][-1])
print('series keys', list(payload['series'].keys()))
print('events', len(payload['events']))
for k in ['cvSeries', 'cvScatter', 'cvRoll', 'cvLag', 'phaseTbl', 'matrixTbl', 'robustTbl', 'selDetail', 'concl']:
    print(k, 'present' if k in h else 'MISSING')
print('script blocks', h.count('<script'), 'canvas', h.count('<canvas'))
