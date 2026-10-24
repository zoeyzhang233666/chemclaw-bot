# -*- coding: utf-8 -*-
"""工作簿自检：结构、必填内容、禁用词、与 data.json 数值一致。

用法：
  python check_xlsx.py out/xxx.xlsx build/data.json

只依赖 openpyxl。不检查视觉排版（那需要打开软件看），但能抓到 95% 的实际错误：
表缺失、表头不对、数字与 HTML 不一致、缺口没写、禁用词混入、超链接坏。
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

from openpyxl import load_workbook

SHEETS = ['00_封面与结论', '01_当前现货价', '02_期货日线', '03_走势图表底表', '04_涨跌幅与分位',
          '05_区域价差', '06_成本与毛利', '07_上游原料', '08_下游需求', '09_事件时间线',
          '10_销售事实卡', '11_话术模板', '12_数据缺口与方法']

BANNED = ['预计涨', '预计跌', '看涨', '看跌', '抄底', '必涨', '必跌', '稳赚']

# 每张表至少要出现这些字样之一，才算写到了该表的核心内容
REQUIRED_TOPIC = {
    '00_封面与结论': ['结论'],
    '01_当前现货价': ['规格', '含税'],
    '02_期货日线': ['日期'],
    '03_走势图表底表': ['月份'],
    '04_涨跌幅与分位': ['分位'],
    '05_区域价差': ['区域'],
    '06_成本与毛利': ['毛利'],
    '07_上游原料': ['品种'],
    '08_下游需求': ['下游'],
    '09_事件时间线': ['事件'],
    '10_销售事实卡': ['事实'],
    '11_话术模板': ['正文'],
    '12_数据缺口与方法': ['缺口'],
}


def cells(ws, max_row=4000):
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, max_row)):
        for c in row:
            if c.value is not None:
                yield c


def num(s):
    if isinstance(s, (int, float)):
        return float(s)
    return None


def check(path, data_path):
    E, W = [], []
    if not os.path.exists(path):
        return ['文件不存在：%s' % path], []
    D = common.load_json(data_path) if os.path.exists(data_path) else None

    # 客户原话允许出现“抄底”等词：只豁免这些原文，不豁免整列
    allowed = set()
    if D:
        for t in (D.get('talk') or []):
            if t.get('q'):
                allowed.add(t['q'].strip())

    try:
        wb = load_workbook(path, data_only=False)
    except Exception as e:
        return ['打不开工作簿：%s' % e], []

    # ---------- 结构
    names = wb.sheetnames
    missing = [s for s in SHEETS if s not in names]
    extra = [s for s in names if s not in SHEETS]
    if missing:
        E.append('缺少工作表：%s' % '、'.join(missing))
    if extra:
        W.append('多出工作表：%s' % '、'.join(extra))
    if names and names[0] != SHEETS[0]:
        W.append('第一张表不是 %s，而是 %s（打开时默认停在那张）' % (SHEETS[0], names[0]))

    # ---------- 逐表
    total_rows = 0
    for s in SHEETS:
        if s not in names:
            continue
        ws = wb[s]
        text = ' '.join(str(c.value) for c in cells(ws))
        total_rows += ws.max_row
        if len(text.strip()) < 30:
            E.append('%s 几乎是空表（%d 行）' % (s, ws.max_row))
        for kw in REQUIRED_TOPIC.get(s, []):
            if kw not in text:
                E.append('%s 里找不到关键内容「%s」，可能没写到' % (s, kw))
        # 禁用词（客户原话豁免）
        for c in cells(ws):
            v = c.value
            if isinstance(v, str):
                if v.strip() in allowed:
                    continue
                for b in BANNED:
                    if b in v:
                        E.append('%s!%s 出现方向性表述「%s」：%s' % (s, c.coordinate, b, common.clip(v, 40)))
        # 空白单元格定位（缺口必须写文字，不能留空）
        if s in ('01_当前现货价', '05_区域价差', '07_上游原料', '08_下游需求', '09_事件时间线'):
            blank_rows = 0
            for r in range(4, ws.max_row + 1):
                vals = [ws.cell(row=r, column=c).value for c in range(1, 6)]
                if all(v is None for v in vals):
                    blank_rows += 1
            if blank_rows > 3:
                W.append('%s 有 %d 个连续空行（缺口应写文字，不要留空）' % (s, blank_rows))

    # ---------- 与 data.json 数值一致
    if D:
        # 现货锚
        a = D.get('anchor')
        if a:
            v = float(a['value'])
            flat = []
            for s in ('00_封面与结论', '01_当前现货价', '11_话术模板'):
                if s in names:
                    flat += [num(c.value) for c in cells(wb[s]) if num(c.value) is not None]
            if not any(abs(x - v) < 0.51 for x in flat):
                E.append('现货锚 %s 没有出现在 00/01/11 表中' % common.fmt(v))
        # 期货收盘
        L = D.get('last') or {}
        if L.get('close') is not None:
            v = float(L['close'])
            flat = []
            for s in ('00_封面与结论', '02_期货日线', '03_走势图表底表'):
                if s in names:
                    flat += [num(c.value) for c in cells(wb[s]) if num(c.value) is not None]
            if not any(abs(x - v) < 0.51 for x in flat):
                E.append('期货收盘 %s 没有出现在 00/02/03 表中' % common.fmt(v))
        # 缺口条数
        if '12_数据缺口与方法' in names:
            ws = wb['12_数据缺口与方法']
            txt = ' '.join(str(c.value) for c in cells(ws))
            n = len(D.get('gaps') or [])
            hit = sum(1 for g in (D.get('gaps') or []) if (g.get('item') or '')[:6] in txt)
            if n and hit < n:
                W.append('%d 条缺口中有 %d 条未在 12 表出现' % (n, n - hit))
        # 来源条数
        if '12_数据缺口与方法' in names and D.get('sources'):
            ws = wb['12_数据缺口与方法']
            links = [c.hyperlink.target for c in cells(ws) if c.hyperlink]
            if len(links) < min(3, len(D['sources'])):
                W.append('12 表只有 %d 个可点击来源链接，原始来源 %d 条' % (len(links), len(D['sources'])))
            bad = [l for l in links if l and not str(l).startswith('http')]
            if bad:
                E.append('12 表有非 http 超链接：%s' % bad[:3])
        # margins 路线列
        mg = D.get('margins') or []
        routes = []
        for m in mg:
            for k in m.get('routes', {}):
                if k not in routes:
                    routes.append(k)
        if routes and '06_成本与毛利' in names:
            txt = ' '.join(str(c.value) for c in cells(wb['06_成本与毛利']))
            for r in routes:
                if r not in txt:
                    E.append('06 表缺少毛利路线「%s」的列' % r)

    # ---------- 图表
    charts = sum(len(getattr(wb[s], '_charts', []) or []) for s in names)
    if charts < 2:
        W.append('工作簿里只有 %d 张图表（02/03/05 各应有一张）' % charts)

    return E, W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    ap.add_argument('data')
    a = ap.parse_args()
    E, W = check(a.xlsx, a.data)
    for x in E:
        print('[ERROR]', x)
    for x in W:
        print('[WARN ]', x)
    wb = load_workbook(a.xlsx)
    print('== %d error ｜ %d warn ｜ %d 表 ｜ %d 图表' % (
        len(E), len(W), len(wb.sheetnames),
        sum(len(getattr(wb[s], '_charts', []) or []) for s in wb.sheetnames)))
    if E:
        sys.exit(1)


if __name__ == '__main__':
    main()
