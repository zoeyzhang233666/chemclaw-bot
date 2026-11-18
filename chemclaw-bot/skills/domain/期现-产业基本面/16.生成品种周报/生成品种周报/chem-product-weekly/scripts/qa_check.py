# -*- coding: utf-8 -*-
"""交付前自动质检：口径、空值、窗口外、来源可回溯。"""
import json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = json.load(open(os.path.join(ROOT, 'data', 'metrics.json'), encoding='utf-8'))
F = json.load(open(os.path.join(ROOT, 'data', 'facts.json'), encoding='utf-8'))
W0, W1 = M['window']['start'], M['window']['end']
bad = []

# 1) 窗口外数据混入
for x in F.get('events', []):
    if W0 <= x['date'] <= W1 and x.get('bg'):
        bad.append('窗口内事件被误标为背景：%s %s' % (x['date'], x['what'][:20]))
    if not (W0 <= x['date'] <= W1) and not x.get('bg'):
        bad.append('窗口外事件未标背景：%s %s' % (x['date'], x['what'][:20]))

# 2) 来源缺失
for key in ('anchors', 'upstream', 'fund', 'events'):
    for x in F.get(key, []):
        if not x.get('url'):
            bad.append('%s 缺来源 URL：%s' % (key, str(x)[:60]))

# 3) 主力切换却给了主力涨跌
if M.get('roll_switch'):
    print('提示：窗口内主力切换，报告不得给主力周涨跌幅 ->', M.get('dominant_note'))

# 4) 缺口清单
if not F.get('gaps'):
    bad.append('缺口清单为空（不合理，除非所有指标都取到）')

# 5) 结论里是否出现预测词
BAD_WORDS = ['预计将上涨', '预计将下跌', '将会上涨', '将会下跌', '目标价', '建议买入', '建议卖出']
for x in F.get('changes', []):
    for w in BAD_WORDS:
        if w in x.get('point', '') + x.get('evidence', ''):
            bad.append('结论含预测措辞：%s' % w)

print('窗口', W0, '~', W1)
print('检查项：事件时点/来源/缺口/措辞')
if bad:
    print('FAIL')
    for b in bad:
        print('  -', b)
    sys.exit(1)
print('PASS')
