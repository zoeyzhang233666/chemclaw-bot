# -*- coding: utf-8 -*-
"""build_all.py —— 一条命令跑完整条归因管线。

    python build_all.py --case examples/01-methanol-huadong-2026Q3/case.json

管线：
  1. detect_anomalies.py   价格异动识别 + 阶段切分
  2. align_series.py       多维指标时间对齐
  3. grade_evidence.py     证据分级与排序
  4. assemble_report.py    汇总成唯一数据包
  5. build_html.py         生成单文件交互式 HTML
  6. build_xlsx.py         生成 Excel 工作簿
  7. check_html.py         结构自检（含浏览器渲染自检结果，若已跑过 render_check.js）
  8. check_xlsx.py         工作簿自检
  9. selftest.py           引擎自检（分级规则、缺失处理、复算一致性）

任何一步失败即中止并打印原因。全部通过时返回 0。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
sys.path.insert(0, HERE)
import common as C  # noqa: E402


def run(desc, args, allow_fail=False):
    print('\n[%s] %s' % ('RUN', desc))
    r = subprocess.run([PY] + args, cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (r.stdout or '').strip()
    if out:
        for line in out.splitlines():
            print('   ' + line)
    if r.returncode != 0:
        err = (r.stderr or '').strip()
        if err:
            print('   !! ' + err.splitlines()[-1])
        if not allow_fail:
            print('\n管线中止：%s 失败（code %d）' % (desc, r.returncode))
            sys.exit(r.returncode)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True)
    ap.add_argument('--out-dir', default=None, help='默认 <case 目录>/out')
    ap.add_argument('--skip-selftest', action='store_true')
    ap.add_argument('--no-render', action='store_true', help='跳过浏览器渲染自检')
    a = ap.parse_args()

    case_path = os.path.abspath(a.case)
    case_dir = os.path.dirname(case_path)
    build = os.path.join(case_dir, 'build')
    out = a.out_dir or os.path.join(case_dir, 'out')
    os.makedirs(build, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    case = C.jload(case_path)
    win = case['window']
    # 文件名带上"市场+品种"，避免不同案例写成同名文件互相覆盖
    mkt = (case.get('case', {}).get('market') or '').split('（')[0].split('(')[0]
    tag = (mkt + case.get('case', {}).get('product', ''))

    print('=' * 72)
    print(' 期现-产业基本面归因管线')
    print(' 案例：%s' % case.get('case', {}).get('title', tag))
    print(' 窗口：%s → %s' % (win['start'], win['end']))
    print('=' * 72)

    # 1 异动识别
    anom = os.path.join(build, 'anomalies.json')
    fut_file = case['futures']['file'] if case.get('futures') else case['spot']['file']
    run('价格异动识别与阶段切分', [
        os.path.join(HERE, 'detect_anomalies.py'),
        '--series', os.path.join(case_dir, fut_file),
        '--out', anom, '--from', win['start'], '--to', win['end'], '--phase', '3'])

    # 2 对齐
    aligned = os.path.join(build, 'aligned.json')
    run('多维指标时间对齐', [
        os.path.join(HERE, 'align_series.py'),
        '--case', case_path, '--phases', anom, '--out', aligned])

    # 3 分级
    graded = os.path.join(build, 'graded.json')
    run('证据分级与排序', [
        os.path.join(HERE, 'grade_evidence.py'),
        '--aligned', aligned, '--case', case_path, '--anomalies', anom, '--out', graded])

    # 4 汇总
    narrative = os.path.join(case_dir, 'narrative.json')
    data = os.path.join(build, 'report_data.json')
    args = [os.path.join(HERE, 'assemble_report.py'), '--case', case_path,
            '--aligned', aligned, '--graded', graded, '--anomalies', anom, '--out', data]
    if os.path.exists(narrative):
        args += ['--narrative', narrative]
    run('汇总报告数据包', args)

    # 5/6 产物
    html = os.path.join(out, '%s_归因报告.html' % tag)
    xlsx = os.path.join(out, '%s_归因工作簿.xlsx' % tag)
    run('生成交互式 HTML', [os.path.join(HERE, 'build_html.py'), '--data', data,
                          '--anomalies', anom, '--case', case_path, '--out', html])
    run('生成 Excel 工作簿', [os.path.join(HERE, 'build_xlsx.py'), '--data', data,
                           '--case', case_path, '--out', xlsx])

    # 浏览器渲染自检（可选）
    if not a.no_render:
        rc = os.path.join(HERE, 'render_check.js')
        if os.path.exists(rc):
            node = 'node'
            try:
                r = subprocess.run([node, rc, html, os.path.join(out, 'render_check.json')],
                                   cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
                if r.returncode == 0:
                    print('\n[RUN] 浏览器渲染自检：无 JS 报错')
                else:
                    print('\n[RUN] 浏览器渲染自检：发现问题（详见 render_check.json），check_html 将报出')
            except FileNotFoundError:
                print('\n[SKIP] 未安装 node，跳过浏览器渲染自检')
        else:
            print('\n[SKIP] 缺少 render_check.js')

    # 7/8 自检
    ok1 = run('HTML 自检', [os.path.join(HERE, 'check_html.py'), html])
    ok2 = run('Excel 自检', [os.path.join(HERE, 'check_xlsx.py'), xlsx])
    if not a.skip_selftest and os.path.exists(os.path.join(HERE, 'selftest.py')):
        ok3 = run('引擎自检', [os.path.join(HERE, 'selftest.py')])
    else:
        ok3 = True

    print('\n' + '=' * 72)
    print(' 完成：')
    print('   HTML : %s' % html)
    print('   Excel: %s' % xlsx)
    print('   自检 : HTML %s / Excel %s / 引擎 %s' % ('通过' if ok1 else '失败', '通过' if ok2 else '失败',
                                                '通过' if ok3 else '失败'))
    print('=' * 72)
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == '__main__':
    sys.exit(main())
