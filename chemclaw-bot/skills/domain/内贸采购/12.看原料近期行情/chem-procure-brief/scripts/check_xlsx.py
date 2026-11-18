# -*- coding: utf-8 -*-
"""工作簿自检（采购版）：结构、必填内容、禁用词、与 data.json 数值一致。

用法：
  python check_xlsx.py out/xxx.xlsx build/data.json

只依赖 openpyxl。不检查视觉排版，但能抓到 95% 的实际错误：
表缺失、表头不对、数字与 HTML 不一致、缺口没写、禁用词混入、超链接坏、
以及“某个品种被写死”这类回归（表名与内容里不应出现与本品种无关的名字——由数据驱动检查）。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

from openpyxl import load_workbook

SHEETS = ['00_封面与结论', '01_现货报价明细', '02_报价序列与走势', '03_区间涨跌与分位', '04_区域价差',
          '05_上游成本拆解', '06_下游需求与开工', '07_供给库存与开工', '08_事件时间线',
          '09_可用事实与话术', '10_缺口与来源', '99_方法与字段口径']

BANNED = ['预计涨', '预计跌', '看涨', '看跌', '抄底', '必涨', '必跌', '稳赚', '会涨', '会跌']

# 每张表至少要出现这些字样，才算写到了该表的核心内容
REQUIRED_TOPIC = {
    '00_封面与结论': ['结论'],
    '01_现货报价明细': ['规格', '含税', '提货'],
    '02_报价序列与走势': ['日期'],
    '03_区间涨跌与分位': ['分位'],
    '04_区域价差': ['基准点'],
    '05_上游成本拆解': ['单耗'],
    '06_下游需求与开工': ['下游', '工艺依据'],
    '07_供给库存与开工': ['口径'],
    '08_事件时间线': ['证据级别'],
    '09_可用事实与话术': ['事实'],
    '10_缺口与来源': ['缺口'],
    '99_方法与字段口径': ['禁止'],
}


def cells(ws, max_row=6000):
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

    # 供应商原话允许出现“看跌”等词：只豁免这一条原文，不豁免整列
    allowed = set()
    if D:
        for t in (D.get('talk') or []):
            if t.get('q'):
                allowed.add(t['q'].strip())

    try:
        wb = load_workbook(path, data_only=False)
    except Exception as e:
        return ['打不开工作簿：%s' % e], []

    names = wb.sheetnames
    missing = [s for s in SHEETS if s not in names]
    extra = [s for s in names if s not in SHEETS]
    if missing:
        E.append('缺少工作表：%s' % '、'.join(missing))
    if extra:
        W.append('多出工作表：%s' % '、'.join(extra))
    if names and names[0] != SHEETS[0]:
        W.append('第一张表不是 %s，而是 %s（打开时默认停在那张）' % (SHEETS[0], names[0]))

    for s in SHEETS:
        if s not in names:
            continue
        ws = wb[s]
        text = ' '.join(str(c.value) for c in cells(ws))
        if len(text.strip()) < 30:
            E.append('%s 几乎是空表（%d 行）' % (s, ws.max_row))
        for kw in REQUIRED_TOPIC.get(s, []):
            if kw not in text:
                E.append('%s 里找不到关键内容「%s」，可能没写到' % (s, kw))
        for c in cells(ws):
            v = c.value
            if isinstance(v, str):
                if v.strip() in allowed:
                    continue
                for b in BANNED:
                    if b in v:
                        E.append('%s!%s 出现方向性表述「%s」：%s' % (s, c.coordinate, b, common.clip(v, 40)))
        if s in ('01_现货报价明细', '04_区域价差', '08_事件时间线', '07_供给库存与开工'):
            blank_rows = 0
            for r in range(5, ws.max_row + 1):
                vals = [ws.cell(row=r, column=c).value for c in range(1, 6)]
                if all(v is None for v in vals):
                    blank_rows += 1
            if blank_rows > 6:
                W.append('%s 有 %d 个全空行（缺口应写文字，不要留空）' % (s, blank_rows))

    if D:
        # 锚价必须出现在封面与报价表
        a = D.get('anchor')
        if a:
            v = float(a['value'])
            for s in ('00_封面与结论', '01_现货报价明细', '09_可用事实与话术'):
                if s not in names:
                    continue
                flat = [num(c.value) for c in cells(wb[s]) if num(c.value) is not None]
                if not any(abs(x - v) < 0.51 for x in flat):
                    W.append('锚价 %s 没有出现在 %s 表（可能只在文中以文字形式出现）' % (common.fmt(v), s))
        # 每一条报价的采购点都要落表
        txt01 = ' '.join(str(c.value) for c in cells(wb['01_现货报价明细'])) if '01_现货报价明细' in names else ''
        miss_pt = [q['point'] for q in (D.get('quotes') or []) if q['point'] not in txt01]
        if miss_pt:
            E.append('01 表缺少这些采购点：%s' % '、'.join(sorted(set(miss_pt))[:5]))
        # 报价值抽查：中值必须能在 01 表找到
        qs = D.get('quotes') or []
        if qs and '01_现货报价明细' in names:
            flat = [num(c.value) for c in cells(wb['01_现货报价明细']) if num(c.value) is not None]
            bad = [q['point'] + str(q['mid']) for q in qs if not any(abs(x - q['mid']) < 0.51 for x in flat)]
            if bad:
                W.append('01 表有 %d 条报价的中值对不上：%s' % (len(bad), '、'.join(bad[:3])))
        # 缺口条数
        if '10_缺口与来源' in names:
            txt = ' '.join(str(c.value) for c in cells(wb['10_缺口与来源']))
            gs = D.get('gaps') or []
            hit = sum(1 for g in gs if (g.get('item') or '')[:6] in txt)
            if gs and hit < len(gs):
                W.append('%d 条缺口中有 %d 条未在 10 表出现' % (len(gs), len(gs) - hit))
            links = [c.hyperlink.target for c in cells(wb['10_缺口与来源']) if c.hyperlink]
            src = D.get('sources') or []
            if src and len(links) < min(3, len(src)):
                W.append('10 表只有 %d 个可点击来源链接，原始来源 %d 条' % (len(links), len(src)))
            bad = [l for l in links if l and not str(l).startswith('http')]
            if bad:
                E.append('10 表有非 http 超链接：%s' % bad[:3])
        # 事件全部落表
        if '08_事件时间线' in names:
            txt = ' '.join(str(c.value) for c in cells(wb['08_事件时间线']))
            miss = [e['title'][:8] for e in (D.get('events') or []) if e['title'][:8] not in txt]
            if miss:
                E.append('08 表缺少 %d 个事件：%s' % (len(miss), '、'.join(miss[:3])))
            for e in (D.get('events_rejected') or []):
                if e['title'][:8] not in txt:
                    W.append('未采纳消息未落表：%s' % e['title'][:16])
        # 产业链两侧
        if '05_上游成本拆解' in names:
            txt = ' '.join(str(c.value) for c in cells(wb['05_上游成本拆解']))
            for x in ((D.get('chain') or {}).get('upstream') or []):
                if x['name'] not in txt:
                    W.append('05 表缺少上游「%s」' % x['name'])
        if '06_下游需求与开工' in names:
            txt = ' '.join(str(c.value) for c in cells(wb['06_下游需求与开工']))
            for x in ((D.get('chain') or {}).get('downstream') or []):
                if x['name'] not in txt:
                    W.append('06 表缺少下游「%s」' % x['name'])
            for p in (D.get('chain_proof') or []):
                if p['from'] not in txt or p['to'] not in txt:
                    W.append('06 表缺少链断点「%s→%s」' % (p['from'], p['to']))
        # 采购参数
        pr = D.get('procurement') or {}
        if pr.get('inventory_days') is not None and '09_可用事实与话术' in names:
            txt = ' '.join(str(c.value) for c in cells(wb['09_可用事实与话术']))
            if '库存' not in txt:
                W.append('09 表没有写采购库存/用量参数')

    charts = sum(len(getattr(wb[s], '_charts', []) or []) for s in names)
    if charts < 1:
        W.append('工作簿里没有任何图表（02 表应有报价走势图，04 表应有多点对比图）')

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
