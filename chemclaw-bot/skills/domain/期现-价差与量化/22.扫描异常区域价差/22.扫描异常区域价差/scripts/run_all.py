# -*- coding: utf-8 -*-
"""
run_all.py —— 一键流水线：口径统一 → 扫描 → HTML/Excel → 自检

用法：
    python scripts/run_all.py            # 全流程
    python scripts/run_all.py --no-fetch # 跳过抓取，用现有 data_raw
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'scripts'))


def run(mod, label):
    print('\n=== %s ===' % label, flush=True)
    r = subprocess.run([sys.executable, os.path.join(BASE, 'scripts', mod)], cwd=BASE)
    if r.returncode != 0:
        raise SystemExit('%s 失败（exit %d）' % (label, r.returncode))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-fetch', action='store_true')
    ap.add_argument('--window', type=int, default=12)
    ap.add_argument('--products', default='soda,methanol')
    ap.add_argument('--freight', default=None, help='运费 JSON，提供后生成「已扣运费」版本')
    a = ap.parse_args()

    if not a.no_fetch:
        run('fetch_chembook2.py', '① 抓取省级挂牌报价（ChemicalBook 归档）')
    run('build_panel.py', '② 口径统一：规格档 / 地区节点 / 剔除规则 → panel_long.csv')
    run('build_background.py', '③ 生成区域供需背景')

    from scan import ScanConfig, run_scan
    from report_html import build_html
    from report_excel import build_excel

    freight = json.load(open(a.freight, encoding='utf-8')) if a.freight else {}
    out_dir = os.path.join(BASE, 'outputs')
    os.makedirs(out_dir, exist_ok=True)

    # 主版本：运费未提供 → 不扣除
    cfg = ScanConfig(products=[x for x in a.products.split(',') if x],
                     window_months=a.window, freight={}, freight_enabled=False)
    print('\n=== ④ 扫描（裸价差视图）===')
    res = run_scan(cfg)
    json.dump(res, open(os.path.join(out_dir, 'scan_result.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    s = res['summary']
    print('组合 %d | 品种 %d | 地区 %d | 缺口 %d' % (s['n_combinations'], s['n_products'],
                                                    s['n_regions'], s['n_gaps']))
    print('分级：', s['by_grade'])

    bg = json.load(open(os.path.join(BASE, 'data_raw', 'background.json'), encoding='utf-8'))
    print('\n=== ⑤ 生成 HTML 报告 ===')
    hp = os.path.join(out_dir, '区域价差扫描报告.html')
    print(build_html(res, hp, bg, title='异常区域价差扫描报告'))
    print('\n=== ⑥ 生成 Excel 工作簿 ===')
    xp = os.path.join(out_dir, '区域价差扫描工作簿.xlsx')
    print(build_excel(res, xp, os.path.join(BASE, 'data_raw', 'panel_long.csv'), bg))

    if freight:
        cfg2 = ScanConfig(products=[x for x in a.products.split(',') if x],
                          window_months=a.window, freight=freight, freight_enabled=True)
        print('\n=== ⑦ 扫描（用户提供运费，方向化扣除）===')
        res2 = run_scan(cfg2)
        json.dump(res2, open(os.path.join(out_dir, 'scan_result_freight.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(build_html(res2, os.path.join(out_dir, '区域价差扫描报告_含运费.html'), bg,
                         title='异常区域价差扫描报告（含用户提供运费）'))

    print('\n完成。输出目录：%s' % out_dir)


if __name__ == '__main__':
    main()
