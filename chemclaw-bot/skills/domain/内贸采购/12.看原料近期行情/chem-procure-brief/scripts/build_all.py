#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令走完（采购版）：校验 -> 装配 -> HTML -> Excel -> 自检。

用法：
  python build_all.py research.json --out out
  python build_all.py research.json --out out --name <品种>-<地区>
  python build_all.py research.json --out out --html-only / --xlsx-only
  python build_all.py research.json --out out --skip-validate   # 已知 warn，强行出版
  python build_all.py research.json --out out --no-render       # 没装 playwright 时

产物：
  out/<名称>_原料行情底稿_采购.html   （单文件离线，零外链，双击即开）
  out/<名称>_原料行情底稿_采购.xlsx   （12 表）
规则：
  - 校验有 ERROR 直接停，不出半成品；
  - WARN 打印后继续，缺口会带进报告“数据缺口”章节与 Excel 第 10 表；
  - 渲染自检需要 playwright，缺了自动跳过，静态检查仍执行；
  - 工作簿自检（check_xlsx）总会执行。
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import assemble
import build_html
import build_xlsx
import check_html
import common
import validate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('research')
    ap.add_argument('--out', default='out')
    ap.add_argument('--name', default=None, help='输出文件名前缀，默认 品种-地区')
    ap.add_argument('--html-only', action='store_true')
    ap.add_argument('--xlsx-only', action='store_true')
    ap.add_argument('--skip-validate', action='store_true')
    ap.add_argument('--no-render', action='store_true', help='跳过 playwright 渲染自检')
    ap.add_argument('--shots', default=None, help='渲染自检截图输出目录')
    a = ap.parse_args()

    t0 = time.time()
    base = os.path.dirname(os.path.abspath(a.research))
    R = common.load_json(a.research)

    # 1) 校验
    if not a.skip_validate:
        E, W, I = validate.check(R, base)
        for x in E:
            print('[ERROR]', x)
        for x in W:
            print('[WARN ]', x)
        for x in I:
            print('[INFO ]', x)
        if E:
            sys.exit('\n校验未通过（%d 个 error）。先修 research.json —— error 会产出误导性数字。' % len(E))
    print('--- 校验完成 ---')

    # 2) 装配
    D = assemble.build(R, base)
    data_path = os.path.join(base, 'build', 'data.json')
    common.dump_json(D, data_path)
    common.ok('data.json %.1f KB' % (os.path.getsize(data_path) / 1024))
    print('  ' + common.clip(D['summary'], 200))

    # 3) 命名
    name = a.name or '%s-%s' % (D['meta']['product'], (D['meta']['region'] or '全国').split('·')[0].strip())
    os.makedirs(a.out, exist_ok=True)
    html_path = os.path.join(a.out, name + '_原料行情底稿_采购.html')
    xlsx_path = os.path.join(a.out, name + '_原料行情底稿_采购.xlsx')

    # 4) 生成
    if not a.xlsx_only:
        r = build_html.build(data_path, html_path)
        for p in r['problems']:
            common.warn(p)
        common.ok('HTML %.2f MB' % (r['bytes'] / 1048576))
    if not a.html_only:
        r = build_xlsx.Book(D).build(xlsx_path)
        for w in r['warn'][:10]:
            common.warn(w)
        common.ok('Excel %d 表 %.1f KB' % (len(r['sheets']), r['bytes'] / 1024))

    # 5) 自检
    fails = 0
    if not a.xlsx_only:
        E, W, _info = check_html.check(html_path, data_path)
        for x in E:
            print('[HTML ERROR]', x)
        for x in W:
            print('[HTML WARN ]', x)
        fails += len(E)
        print('--- 静态自检：%d error ---' % len(E))
        if not a.no_render:
            try:
                import qa_render
                n, fl = qa_render.run(html_path, data_path, a.shots)
                fails += n
            except Exception as e:
                common.warn('渲染自检跳过：%s' % e)
    if not a.html_only:
        import check_xlsx
        E, W = check_xlsx.check(xlsx_path, data_path)
        for x in E:
            print('[XLSX ERROR]', x)
        for x in W:
            print('[XLSX WARN ]', x)
        fails += len(E)
        print('--- 工作簿自检：%d error ---' % len(E))

    print('\n=== 完成（%.1fs）===' % (time.time() - t0))
    if not a.xlsx_only:
        print('HTML :', html_path)
    if not a.html_only:
        print('Excel:', xlsx_path)
    print('数据 :', data_path)
    print('缺口 : %d 条（已写入 HTML 第 10 节 / Excel 第 10 表）' % len(D['gaps']))
    if fails:
        print('自检未通过：%d 项，请按上面输出修复' % fails)
        sys.exit(1)


if __name__ == '__main__':
    main()
