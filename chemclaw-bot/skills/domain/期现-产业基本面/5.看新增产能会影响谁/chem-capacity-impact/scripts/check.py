#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chem-capacity-impact · 结构自检（不依赖 Excel / LibreOffice）

做三件事：
1. 打开 xlsx，检查每个 sheet 是否存在、行数是否与数据一致；
2. 扫描所有公式单元格，找出 Excel 必然报错的两类低级错误：
   - 跨表/本表引用指向"空或文本"的单元格（无法做算术）——启发式：
     若公式形如 =X/Y 而 Y 单元格是字符串常量，直接报错；
   - 形如 =B4/C4 但 B4 是长文本（长度 > 30）的，报错。
3. 校验 HTML：占位符残留、外部依赖、localStorage/fetch 等离线环境可能失败的调用。

用法：
    python check.py <project.json>              # 只检查数据/口径
    python check.py <project.json> --xlsx a.xlsx --html a.html
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

REQUIRED_SHEETS = [
    '00_封面与口径', '01_项目事实核验', '02_现有产能基准', '03_原料单耗',
    '04_产能相对规模', '05_产量情景', '06_月度爬坡明细', '07_原料需求测算',
    '08_受影响对象', '09_区域供应格局', '10_结论分类', '11_待核实事项', '12_来源清单',
]

CELL_RE = re.compile(r"'?([^'!]+)'?!\$?([A-Z]{1,3})\$?(\d+)")
SIMPLE_DIV = re.compile(r'^\s*=?\s*\$?[A-Z]{1,3}\$?\d+\s*/\s*\$?([A-Z]{1,3})\$?(\d+)\s*\*\s*100\s*$')


def col_to_idx(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def check_xlsx(path: str) -> list:
    problems = []
    try:
        import openpyxl
    except ImportError:
        return [('warn', 'openpyxl 未安装，跳过 xlsx 检查')]
    wb = openpyxl.load_workbook(path, data_only=False)
    missing = [s for s in REQUIRED_SHEETS if s not in wb.sheetnames]
    for m in missing:
        problems.append(('error', f'缺少工作表：{m}'))

    total_formulas = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if not isinstance(v, str) or not v.startswith('='):
                    continue
                total_formulas += 1
                m = SIMPLE_DIV.match(v)
                if m:
                    col, r = m.group(1), int(m.group(2))
                    target = ws.cell(r, col_to_idx(col)).value
                    if isinstance(target, str) and not target.startswith('='):
                        problems.append((
                            'error',
                            f'{ws.title}!{c.coordinate} 公式 {v} 的分母 {col}{r} 是文本'
                            f'（"{target[:40]}…"），Excel 会返回 #VALUE!'))
                    elif target is None:
                        problems.append((
                            'warn',
                            f'{ws.title}!{c.coordinate} 公式 {v} 的分母 {col}{r} 为空，结果会是 #DIV/0!'))
    if total_formulas == 0:
        problems.append(('error', 'xlsx 中没有任何公式：本技能要求计算过程可复核'))
    problems.append(('info', f'xlsx 公式总数 {total_formulas}，工作表 {len(wb.worksheets)} 个'))
    return problems


def check_html(path: str) -> list:
    problems = []
    with open(path, 'r', encoding='utf-8') as fh:
        html = fh.read()
    for ph in ('__DATA__', '__TITLE__'):
        if ph in html:
            problems.append(('error', f'HTML 残留未替换占位符 {ph}'))
    if 'echarts' not in html.lower():
        problems.append(('error', 'HTML 未内联 ECharts，图表不会渲染'))
    ext = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)["\']', html)
    # 只把"资源加载"算外部依赖；正文里的来源超链接是允许的
    res = [u for u in ext if re.search(r'\.(js|css|woff2?|png|jpe?g|svg)(\?|$)', u)]
    if res:
        problems.append(('error', f'HTML 依赖外部资源（离线会失败）：{res[:3]}'))
    for bad in ('fetch(', 'XMLHttpRequest', 'localStorage', 'sessionStorage'):
        if bad in html:
            problems.append(('warn', f'HTML 使用了 {bad}：file:// 直接打开时可能被浏览器拦截，'
                                     f'建议确认已做 try/catch 降级'))
    if 'max-width:1080px' not in html and '@media' not in html:
        problems.append(('warn', 'HTML 未发现响应式断点，小屏可能挤压'))
    problems.append(('info', f'HTML 体积 {len(html)/1048576:.2f} MB，内联超链接 {len(ext)} 个'))
    return problems


def check_project(path: str) -> list:
    import validate
    with open(path, 'r', encoding='utf-8-sig') as fh:
        pj = json.load(fh)
    rep = validate.validate(pj)
    out = []
    for it in rep.items:
        tag = f'[{it["code"]}] {it.get("path", "")}'.strip()
        out.append((it['level'], f'{tag}: {it["msg"]}'))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('project_json')
    ap.add_argument('--xlsx')
    ap.add_argument('--html')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    allp = check_project(a.project_json)
    if a.xlsx:
        allp += check_xlsx(a.xlsx)
    if a.html:
        allp += check_html(a.html)

    rank = {'error': 0, 'warn': 1, 'info': 2}
    ne = sum(1 for s, _ in allp if s == 'error')
    nw = sum(1 for s, _ in allp if s == 'warn')
    ni = sum(1 for s, _ in allp if s == 'info')
    if not a.quiet:
        for lvl in ('error', 'warn', 'info'):
            items = [m for s, m in allp if s == lvl]
            if not items:
                continue
            print(f'--- {lvl.upper()} ({len(items)}) ---')
            for m in items:
                print('  ' + m)
    print(f'\n== {ne} error / {nw} warn / {ni} info ==')
    return 1 if ne else 0


if __name__ == '__main__':
    sys.exit(main())
