#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chem-capacity-impact · 一键构建

    python build_all.py <项目目录>            # 目录内含 project.json
    python build_all.py <project.json>

流水线（任何一步失败即中止，不产出"看起来成功"的半成品）：
    1. validate.py  口径校验（error 即中止）
    2. compute.py   计算 → build/data.json
    3. build_xlsx.py 生成 13 表工作簿
    4. build_html.py 生成单文件交互式报告
    5. check.py      结构自检（xlsx 公式分母、HTML 离线依赖、占位符残留）

输出：<项目目录>/output/ 下两个文件 + build/data.json（HTML 与 Excel 的单一数据源）。
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check as check_mod
import validate as validate_mod


def _resolve(arg: str):
    p = os.path.abspath(arg)
    if os.path.isdir(p):
        return os.path.join(p, 'project.json'), os.path.abspath(p)
    return p, os.path.dirname(p)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    proj_path, proj_dir = _resolve(argv[0])
    if not os.path.exists(proj_path):
        print(f'[error] 找不到 {proj_path}')
        return 2

    with open(proj_path, 'r', encoding='utf-8-sig') as fh:
        pj = json.load(fh)

    print('=' * 68)
    print('chem-capacity-impact · build')
    print(f'输入 : {proj_path}')
    print('=' * 68)

    # ---- 1. 校验 ----
    print('\n[1/5] 口径校验 ...')
    rep = validate_mod.validate(pj)
    rep.dump()
    if rep.count('error'):
        print('\n[中止] 存在 error 级问题，未生成任何交付物。')
        print('      请先修正 project.json，再重跑 build_all.py。')
        return 1

    # ---- 2. 计算 ----
    print('\n[2/5] 计算 ...')
    from compute import compute_all
    data = compute_all(pj)
    build_dir = os.path.join(proj_dir, 'build')
    os.makedirs(build_dir, exist_ok=True)
    data_path = os.path.join(build_dir, 'data.json')
    with open(data_path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print(f'  → {data_path}')

    # 命名
    meta = pj.get('meta') or {}
    product = (meta.get('product') or '产品').strip()
    cap = pj.get('project', {}).get('design_capacity_t', 0) or 0
    cap_wt = cap / 10000
    cap_s = f'{cap_wt:g}'
    stem = f'{product}新增{cap_s}万吨产能'
    out_dir = os.path.join(proj_dir, 'output')
    os.makedirs(out_dir, exist_ok=True)
    xlsx_path = os.path.join(out_dir, f'{stem}_影响研究_计算工作簿.xlsx')
    html_path = os.path.join(out_dir, f'{stem}_影响研究报告.html')

    # ---- 3. Excel ----
    print('\n[3/5] 生成 Excel 工作簿 ...')
    import build_xlsx
    build_xlsx.build(pj, xlsx_path)
    print(f'  → {xlsx_path}')

    # ---- 4. HTML ----
    print('\n[4/5] 生成交互式 HTML ...')
    import build_html
    build_html.build(data, html_path)
    print(f'  → {html_path}')

    # ---- 5. 自检 ----
    print('\n[5/5] 结构自检 ...')
    problems = check_mod.check_xlsx(xlsx_path) + check_mod.check_html(html_path)
    ne = sum(1 for s, _ in problems if s == 'error')
    for lvl in ('error', 'warn', 'info'):
        items = [m for s, m in problems if s == lvl]
        if items:
            print(f'--- {lvl.upper()} ({len(items)}) ---')
            for m in items:
                print('  ' + m)

    print('\n' + '=' * 68)
    if ne:
        print(f'[完成但有 {ne} 个自检 error] 请检查上方输出。')
        return 1
    print('[完成] 交付物已生成：')
    print(f'  HTML : {html_path}')
    print(f'  XLSX : {xlsx_path}')
    print(f'  数据 : {data_path}')
    print('=' * 68)
    return 0


if __name__ == '__main__':
    sys.exit(main())
