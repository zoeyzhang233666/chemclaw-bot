# -*- coding: utf-8 -*-
"""HTML 静态自检（不依赖浏览器）。

用法：
  python check_html.py out/brief.html build/data.json

检查：
1. 占位符是否全部替换（__PAYLOAD__ / /*__ECHARTS__*/ / __TITLE__ 等残留）；
2. 是否零外链（离线可用）：不允许 http(s):// 出现在 src/href/import 中；
   正文里作为「来源链接」的 <a href> 允许存在（用户点击才联网），但统计并提示；
3. ECharts 是否内联成功；
4. 数字一致性：抽样比对页面内嵌 PAYLOAD 与 data.json 的关键数字；
5. 方向性表述：扫描 payload 文本，命中「预计上涨/看涨/抄底」等必须失败；
6. 必要结构：3 品种 × 5 模块、筛选器、抽屉、缺口/排除/来源区块；
7. 每条指标是否具备四件套（what / why / verify / source）。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PLACEHOLDERS = ['__PAYLOAD__', '__TITLE__', '__REPORT_DATE__', '__BUILD_TIME__', '/*__ECHARTS__*/']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('data')
    a = ap.parse_args()
    html = open(a.html, encoding='utf-8').read()
    data = common.load_json(a.data)
    fails, warns = [], []

    # 1 占位符
    for p in PLACEHOLDERS:
        if p in html:
            fails.append('占位符未替换：%s' % p)

    # 2 外链
    script_src = re.findall(r'<script[^>]+src=["\']([^"\']+)', html)
    link_href = re.findall(r'<link[^>]+href=["\']([^"\']+)', html)
    img_src = re.findall(r'<img[^>]+src=["\']([^"\']+)', html)
    for u in script_src + link_href + img_src:
        if u.startswith(('http://', 'https://', '//')):
            fails.append('存在外部资源引用（离线打开会失效）：%s' % u)
    a_links = re.findall(r'<a[^>]+href=["\'](https?://[^"\']+)', html)
    if a_links:
        warns.append('页面含 %d 个来源外链（<a>，仅点击时联网，不影响离线阅读）' % len(a_links))

    # 3 ECharts 内联
    if 'echarts' not in html:
        warns.append('未内联 ECharts，图表将降级为表格')
    else:
        common.ok('ECharts 已内联（HTML %.2f MB）' % (len(html.encode('utf-8')) / 1048576))

    # 4 数字一致性：从 payload 里读回关键数字
    m = re.search(r'const D = (\{.*?\});\s*\nconst BUILT', html, re.S)
    if not m:
        fails.append('页面内找不到 PAYLOAD（const D）')
        payload = {}
    else:
        try:
            payload = json.loads(m.group(1))
        except Exception as e:
            fails.append('PAYLOAD JSON 解析失败：%s' % e)
            payload = {}
    if payload:
        for src in data['indicators']:
            hit = [x for x in payload.get('indicators', []) if x['id'] == src['id']]
            if not hit:
                fails.append('页面缺少指标：%s' % src['id'])
                continue
            h = hit[0]
            if src['current'] is not None and abs((h['current'] or 0) - src['current']) > 1e-6:
                fails.append('指标 %s 本期值与 data.json 不一致：%s vs %s'
                             % (src['id'], h['current'], src['current']))
            if (src['abs'] is None) != (h['abs'] is None):
                fails.append('指标 %s 变动字段缺失不一致' % src['id'])
            elif src['abs'] is not None and abs(h['abs'] - src['abs']) > 1e-6:
                fails.append('指标 %s 变动值与 data.json 不一致' % src['id'])
        if len(payload.get('events', [])) != len(data['events']):
            fails.append('页面事件数与 data.json 不一致')
        for f in data.get('futures', {}).values():
            if f.get('close') is None:
                fails.append('期货 %s 收盘缺失' % f.get('name'))

    # 5 方向性表述
    texts = []
    for i in data['indicators']:
        texts += [i.get('name', ''), i.get('what', ''), i.get('why', ''), i.get('verify', '')]
    for e in data['events']:
        texts += [e.get('title', ''), e.get('detail', ''), e.get('impact_path', '')]
    texts += [data['report'].get('session_note', ''), data['report'].get('title', '')]
    for g in data.get('gaps', []):
        texts += [g.get('why', '')]
    bad = []
    for t in texts:
        for h in common.banned_hits(t):
            bad.append((h, common.clip(t, 60)))
    if bad:
        fails.append('命中方向性/预测性表述 %d 处：%s' % (len(bad), bad[:4]))
    else:
        common.ok('方向性表述扫描通过（%d 段文本）' % len(texts))

    # 6 结构
    for token in ['id="cards"', 'id="panels"', 'id="drawer"', 'id="drBody"',
                  'data-filter="tier"', 'id="gapTbl"', 'id="exList"', 'id="srcTbl"']:
        if token not in html:
            fails.append('缺少必要结构：%s' % token)
    if '价格与价差' not in html or '基差与月差' not in html or '政策与事件' not in html:
        fails.append('缺少模块定义')

    # 7 四件套
    for i in data['indicators']:
        for k in ('what', 'why', 'verify', 'source'):
            if not i.get(k):
                fails.append('指标「%s」缺少 %s' % (i['name'], k))

    common.ok('指标 %d 条 / 事件 %d 条 / 缺口 %d 条 / 排除 %d 条' % (
        len(data['indicators']), len(data['events']),
        len(data.get('gaps', [])), len(data.get('excluded', []))))
    for w in warns:
        common.warn(w)
    if fails:
        for f in fails:
            print('[FAIL ] ' + f)
        common.die('静态自检未通过（%d 项）' % len(fails))
    common.ok('静态自检全部通过')


if __name__ == '__main__':
    main()
