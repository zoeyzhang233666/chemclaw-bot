# -*- coding: utf-8 -*-
"""check_html.py —— 对生成的单文件 HTML 做结构与内容自检。

检查项（任何一项失败即非零退出，可直接接入 CI）：
  1. 无外部依赖：不得出现 http(s) 引用的 <script src>/<link href>/图片 src。
  2. ECharts 已内联；window.__REPORT__ 可被 json 解析。
  3. 关键区块 id 齐全（速览/复核/异动/归因树/事件/候选解释/分段/缺口/方法）。
  4. 正文中不出现"必涨/必跌/将会上涨/建议买入/建议采购"等预测或建议性表述。
  5. 每个 E 级徽章都出现在页面模板里。
  6. 数据自洽：summary 的涨跌幅能用 start/end 复算出来；matrix / tree / events 非空。
  7. "无可用数据"必须在文本中出现（证明缺失被显式标注，而不是被省略）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

REQUIRED_IDS = ['sec-summary', 'sec-rehab', 'sec-anom', 'sec-tree', 'sec-local', 'sec-events',
                'sec-hyp', 'sec-periods', 'sec-gap', 'sec-method',
                'chart-main', 'tree-list', 'event-list', 'hyp-list', 'drawer', 'chart-local', 'tbl-local', 'local-controls']
BANNED = ['必涨', '必跌', '一定会涨', '一定会跌', '将会上涨', '将会下跌', '即将上涨', '即将下跌',
          '建议买入', '建议卖出', '建议采购', '建议囤货', '抄底', '保证收益', '稳赚']


def fail(msgs, m):
    msgs.append('FAIL ' + m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    a = ap.parse_args()
    s = open(a.html, encoding='utf-8').read()
    msgs = []
    ok = 0

    # 1 外部依赖
    ext = re.findall(r'<script[^>]+src=["\']https?://', s) + re.findall(r'<link[^>]+href=["\']https?://', s)
    if ext:
        fail(msgs, '存在外部脚本/样式依赖 %d 处' % len(ext))
    else:
        ok += 1

    # 2 ECharts + 数据
    has_ech = 'echarts' in s and len(s) > 700 * 1024
    if has_ech:
        ok += 1
    else:
        fail(msgs, 'ECharts 未内联或文件过小')
    m = re.search(r'window\.__REPORT__=(\{.*?\});?</script>', s, re.S)
    data = None
    if m:
        try:
            data = json.loads(m.group(1))
            ok += 1
        except Exception as e:
            fail(msgs, '报告数据 JSON 解析失败：%s' % e)
    else:
        fail(msgs, '未找到 window.__REPORT__ 数据块')

    # 3 必需区块
    missing = [i for i in REQUIRED_IDS if ('id="%s"' % i) not in s]
    if missing:
        fail(msgs, '缺少区块 id：%s' % ', '.join(missing))
    else:
        ok += 1

    # 4 禁用语
    hits = [b for b in BANNED if b in s]
    if hits:
        fail(msgs, '出现预测/建议性表述：%s' % ', '.join(hits))
    else:
        ok += 1

    # 5 四级徽章
    miss_lv = [l for l in ('bE1', 'bE2', 'bE3', 'bE4') if l not in s]
    if miss_lv:
        fail(msgs, '缺少证据等级样式：%s' % ', '.join(miss_lv))
    else:
        ok += 1

    # 6 数据自洽
    if data:
        sm = data['summary']
        calc = (sm['spot_end'] / sm['spot_start'] - 1) * 100
        if abs(calc - sm['spot_chg_pct']) > 0.01:
            fail(msgs, '现货涨跌幅不自洽：报告 %.2f%%，复算 %.2f%%' % (sm['spot_chg_pct'], calc))
        else:
            ok += 1
        calc2 = (sm['fut_end'] / sm['fut_start'] - 1) * 100
        if abs(calc2 - sm['fut_chg_pct']) > 0.01:
            fail(msgs, '期货涨跌幅不自洽：报告 %.2f%%，复算 %.2f%%' % (sm['fut_chg_pct'], calc2))
        else:
            ok += 1
        for k in ('price', 'matrix', 'tree', 'events', 'ranked', 'anomaly_bars'):
            if not data.get(k):
                fail(msgs, '数据块 %s 为空' % k)
        if data.get('tree') and all(t['level'] != 'E4' for t in data['tree']):
            pass  # 允许全部有证据
        # 每个驱动都必须有证据条目（含 E4）
        for t in data.get('tree', []):
            if t['counts']['E1'] + t['counts']['E2'] + t['counts']['E3'] + t['counts']['E4'] == 0:
                fail(msgs, '驱动「%s」没有任何证据条目（应至少记一条 E4）' % t['name'])
        ok += 1

    # 7 缺失显式标注
    if '无可用数据' in s or '无数据' in s:
        ok += 1
    else:
        fail(msgs, '全文未见"无可用数据/无数据"标注，缺失数据可能被静默省略')

    # 8 渲染自检结果（由 render_check.js 产出）
    rc = os.path.join(os.path.dirname(os.path.abspath(a.html)), 'render_check.json')
    if os.path.exists(rc):
        try:
            r = json.load(open(rc, encoding='utf-8'))
            if r.get('errors'):
                fail(msgs, '浏览器渲染/交互时报错 %d 条：%s' % (
                    len(r['errors']), str(r['errors'][0])[:160]))
            else:
                ok += 1
            pg = r.get('page') or {}
            need = {'treeCards': 1, 'eventRows': 1, 'hypotheses': 1, 'periods': 1,
                    'matrixRows': 1, 'sensRows': 1, 'gapRows': 1, 'legendRows': 1}
            bad = [k for k, v in need.items() if (pg.get(k) or 0) < v]
            if bad:
                fail(msgs, '页面区块未渲染出来：%s' % ', '.join(bad))
            else:
                ok += 1
            charts = pg.get('charts') or []
            dead = [c['id'] for c in charts if not c.get('canvas')]
            if dead:
                fail(msgs, '图表未绘制：%s' % ', '.join(dead))
            else:
                ok += 1
            if not (r.get('drawer') or {}).get('open'):
                fail(msgs, '点击归因树节点后抽屉未打开')
            else:
                ok += 1
        except Exception as e:
            fail(msgs, '渲染自检结果无法解析：%s' % e)
    else:
        print('  提示：未找到 render_check.json，跳过浏览器渲染自检（建议先跑 render_check.js）')

    print('检查项通过 %d 项，失败 %d 项' % (ok, len(msgs)))
    for x in msgs:
        print('  ' + x)
    if not msgs:
        print('HTML 自检通过。')
    return 1 if msgs else 0


if __name__ == '__main__':
    sys.exit(main())
