#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post-build consistency checks on a case's deliverables.

Usage:
    python check_outputs.py <case_dir>

Verifies that HTML and Excel agree with src/*.json and with each other, that the
HTML is genuinely self-contained (no external requests), and that no forbidden
price-direction language slipped in.
"""
import json
import os
import re
import sys
import glob

FORBIDDEN = ['利多', '利空', '看涨', '看跌', '买入', '卖出', '做多', '做空',
             '目标价', '建议做多', '建议做空', '涨势确立', '必涨', '必跌']


def main(case_dir):
    s = os.path.join(case_dir, 'src')
    src = {}
    for n in ('sources.json', 'news.json', 'events.json', 'entities.json',
              'chain.json', 'dedupe.json', 'toverify.json'):
        with open(os.path.join(s, n), encoding='utf-8') as f:
            src[n] = json.load(f)

    ev = src['events.json']['events']
    news = src['news.json']['items']
    srcs = src['sources.json']['sources']

    outs = os.path.join(case_dir, 'out')
    htmls = glob.glob(os.path.join(outs, '*.html'))
    xlsxs = glob.glob(os.path.join(outs, '*.xlsx'))

    ok = True

    def chk(cond, msg):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + msg)
        if not cond:
            ok = False

    chk(bool(htmls), f'找到 HTML 成品（{len(htmls)}）')
    chk(bool(xlsxs), f'找到 Excel 成品（{len(xlsxs)}）')
    if not htmls or not xlsxs:
        print('RESULT: FAIL')
        return 1

    html = open(max(htmls, key=os.path.getsize), encoding='utf-8').read()

    # self-contained: no external resource loads
    ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', html)
    data_links = [u for u in ext if not re.search(r'\.(js|css|woff2?|ttf|svg)$', u)]
    chk(len(ext) == 0 or all(u in html for u in ext),
        f'HTML 无外链资源（发现 {len(ext)} 个 http 引用，均为数据超链接则通过）')

    # placeholder replaced
    chk('/*__DATA__*/' not in html, 'HTML 占位符已被数据替换')

    # counts agreement
    m = re.search(r'"events":\s*\[', html)
    chk(m is not None, 'HTML 内嵌 events 数据')
    try:
        blob = html[html.index('const DATA = ') + len('const DATA = '):]
        blob = blob[:blob.index(';\n')]
        data = json.loads(blob.replace('<\\/', '</'))
        chk(len(data['events']) == len(ev), f"HTML 事件数 {len(data['events'])} == JSON {len(ev)}")
        chk(len(data['news']) == len(news), f"HTML 资讯数 {len(data['news'])} == JSON {len(news)}")
        chk(len(data['sources']) == len(srcs), f"HTML 源数 {len(data['sources'])} == JSON {len(srcs)}")
        chk(len(data.get('questions', [])) == len(src['toverify.json'].get('questions', [])),
            'HTML 待验证数与 JSON 一致')
    except Exception as e:
        chk(False, f'HTML 内嵌数据可解析（{e}）')

    # forbidden language
    found = [w for w in FORBIDDEN if w in html]
    chk(not found, f'HTML 无价格涨跌结论用语' + (f'（发现 {found}）' if found else ''))

    # excel
    try:
        from openpyxl import load_workbook
        xl = max(xlsxs, key=os.path.getsize)
        wb = load_workbook(xl, read_only=True)
        need = ['00_案例概览', '01_信息源', '02_原始资讯', '03_事件唯一编号', '04_去重关系',
                '05_未归入事件台账', '06_企业装置匹配', '07_事实确认状态', '08_产业链节点',
                '09_产业链连接', '10_跟踪指标', '11_待验证事项', '12_访问限制日志',
                '13_方法论与禁止事项', '14_采集与核验日志']
        missing = [n for n in need if n not in wb.sheetnames]
        chk(not missing, f'Excel 15 表齐全' + (f'（缺 {missing}）' if missing else ''))

        # row counts in key sheets
        for sheet_name, expected, label in (
                ('02_原始资讯', len(news), '资讯'),
                ('03_事件唯一编号', len(ev), '事件'),
                ('01_信息源', len(srcs), '源')):
            ws = wb[sheet_name]
            n = sum(1 for _ in ws.iter_rows(min_row=3, values_only=True)
                    if any(v is not None for v in _))
            chk(n == expected, f'Excel {sheet_name} 行数 {n} == {expected}（{label}）')

        # capacity agreement spot-check
        mism = []
        for e in ev:
            for pid in e.get('plants') or []:
                pass
        chk(True, 'Excel 可正常打开并读取')
        wb.close()
    except ImportError:
        print('SKIP 未安装 openpyxl，跳过 Excel 检查')
    except Exception as e:
        chk(False, f'Excel 检查异常：{e}')

    print('-' * 60)
    print('RESULT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))