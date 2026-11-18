# -*- coding: utf-8 -*-
"""Excel 自检：结构完整、与 data.json 同源、无占位/无空格缺列。

用法：
  python check_xlsx.py out/brief.xlsx build/data.json
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from openpyxl import load_workbook

NEED_SHEETS = ['封面与说明', '重要变化总表', '价格与价差', '基差与月差', '库存与开工',
               '事件台账', '被排除资讯', '数据缺口', '数据来源', '期货日线',
               '品种与产业链', '筛选规则']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    ap.add_argument('data')
    a = ap.parse_args()
    d = common.load_json(a.data)
    wb = load_workbook(a.xlsx, data_only=True)
    fails, warns = [], []

    for s in NEED_SHEETS:
        if s not in wb.sheetnames:
            fails.append('缺少工作表：%s' % s)
    if fails:
        for f in fails:
            print('[FAIL ] ' + f)
        common.die('Excel 结构不完整')

    # 重要变化总表：逐条核对数值与 data.json 一致
    ws = wb['重要变化总表']
    hdr = [c.value for c in ws[3]]
    idx = {h: i for i, h in enumerate(hdr)}
    got = {}
    for row in ws.iter_rows(min_row=4, values_only=True):
        if not row or not row[idx['指标名称']]:
            continue
        got[row[idx['指标名称']]] = row
    for i in d['indicators']:
        key = i['name']
        if key not in got:
            fails.append('总表缺少指标：%s' % key)
            continue
        r = got[key]
        for col, expect in (('本期值', i['current']), ('上期值', i['base']), ('变动', i['abs'])):
            v = r[idx[col]]
            if expect is None:
                if v not in (None, '', '—'):
                    warns.append('%s 的「%s」应为空，实际 %r' % (key, col, v))
            elif v is None or abs(float(v) - float(expect)) > 1e-6:
                fails.append('%s 的「%s」不一致：Excel=%r / data.json=%r' % (key, col, v, expect))
        if r[idx['级别']] != i['significance']:
            fails.append('%s 级别不一致：Excel=%s / data=%s'
                         % (key, r[idx['级别']], i['significance']))
        if i.get('what') and not r[idx['发生了什么']]:
            fails.append('%s 缺少「发生了什么」' % key)
        if i.get('why') and not r[idx['为什么重要']]:
            fails.append('%s 缺少「为什么重要」' % key)
        if i.get('verify') and not r[idx['今天继续验证什么']]:
            fails.append('%s 缺少「继续验证」' % key)

    # 事件台账
    ws = wb['事件台账']
    hdr = [c.value for c in ws[3]]
    idx = {h: i for i, h in enumerate(hdr)}
    n_ev = 0
    tiers = {}
    for row in ws.iter_rows(min_row=4, values_only=True):
        if not row or not row[idx['标题']]:
            continue
        n_ev += 1
        t = row[idx['级别']]
        tiers[t] = tiers.get(t, 0) + 1
        if not row[idx['发生日']]:
            fails.append('事件「%s」缺少发生日' % str(row[idx['标题']])[:24])
    if n_ev != len(d['events']):
        fails.append('事件台账 %d 条，data.json %d 条' % (n_ev, len(d['events'])))
    for t in tiers:
        if t not in ('A', 'B', 'C'):
            fails.append('事件出现非法级别：%r' % t)

    # 期货日线
    ws = wb['期货日线']
    n_bar = sum(1 for _ in ws.iter_rows(min_row=4, values_only=True))
    if n_bar < 300:
        warns.append('期货日线仅 %d 行（3 个品种 × 250 日应 ≥700 行）' % n_bar)

    # 空表检查
    for s in ['数据缺口', '数据来源', '品种与产业链', '筛选规则', '被排除资讯']:
        ws = wb[s]
        n = sum(1 for r in ws.iter_rows(min_row=4, values_only=True) if any(r))
        if n == 0:
            fails.append('工作表「%s」为空' % s)

    # 占位符残留
    for s in wb.sheetnames:
        for row in wb[s].iter_rows(values_only=True):
            for v in row:
                if isinstance(v, str) and ('__' in v or 'TODO' in v or 'None' == v):
                    warns.append('「%s」疑似残留占位：%r' % (s, v[:40]))

    common.ok('工作表 %d 个；指标 %d 条已逐格核对；事件 %d 条（%s）；日线 %d 行'
              % (len(wb.sheetnames), len(d['indicators']), n_ev,
                 '/'.join('%s:%d' % (k, tiers[k]) for k in sorted(tiers)), n_bar))
    for w in warns:
        common.warn(w)
    if fails:
        for f in fails:
            print('[FAIL ] ' + f)
        common.die('Excel 自检未通过（%d 项）' % len(fails))
    common.ok('Excel 自检全部通过')


if __name__ == '__main__':
    main()
