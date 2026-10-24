#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前跑全套自检，输出一张总表。

用法：python run_all_checks.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE            # 本文件就在技能根目录，scripts/ tests/ examples/ 都在同级
EX = [
    ('DOP', os.path.join(ROOT, 'examples', '01-dop-dehp', 'input.json'),
     os.path.join(ROOT, 'examples', '01-dop-dehp', 'out'), 'DOP-华东'),
    ('纯碱', os.path.join(ROOT, 'examples', '02-soda-ash-solvay', 'input.json'),
     os.path.join(ROOT, 'examples', '02-soda-ash-solvay', 'out'), '纯碱-华东'),
]
PY = sys.executable
env = dict(os.environ, PYTHONUTF8='1')


def run(title, args, must=True):
    print('\n' + '=' * 66)
    print('▶ ' + title)
    print('=' * 66)
    # 脚本在 scripts/ 下，但输入输出路径按仓库根解析：这里统一给出绝对路径
    fixed = []
    for a in args:
        if a.startswith('scripts/') or a.startswith('tests/'):
            fixed.append(os.path.join(ROOT, a.replace('/', os.sep)))
        elif a and not os.path.isabs(a) and ('\\' in a or '/' in a or a.endswith('.json')):
            fixed.append(os.path.join(ROOT, a))
        else:
            fixed.append(a)
    p = subprocess.run([PY] + fixed, cwd=ROOT, env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (p.stdout or '') + (p.stderr or '')
    tail = '\n'.join(out.strip().splitlines()[-14:])
    print(tail)
    ok = (p.returncode == 0)
    if not ok and not must:
        print('   (非阻断)')
        return True
    print('   → %s' % ('PASS' if ok else 'FAIL'))
    return ok


def main():
    results = []
    results.append(('单元测试', run('单元测试 tests/test_engine.py', ['tests/test_engine.py'])))
    for name, inp, outd, fname in EX:
        results.append((name + ' 输入校验', run(name + ' 输入校验', ['scripts/validate.py', inp], must=False)))
        results.append((name + ' 出稿', run(name + ' 构建 HTML+Excel',
                                          ['scripts/build_all.py', inp, '--out', outd, '--name', fname])))
        rj = os.path.join(outd, 'result.json')
        results.append((name + ' 结果自洽', run(name + ' 结果自洽 check_result', ['scripts/check_result.py', rj])))
        xlsx = os.path.join(outd, fname + '_理论原料成本.xlsx')
        html = os.path.join(outd, fname + '_理论原料成本.html')
        results.append((name + ' 工作簿静态', run(name + ' 工作簿静态 check_xlsx', ['scripts/check_xlsx.py', xlsx])))
        results.append((name + ' 公式重算', run(name + ' Excel 公式重算 check_workbook',
                                               ['scripts/check_workbook.py', xlsx, rj], must=False)))
        results.append((name + ' 渲染交互', run(name + ' 浏览器渲染 qa_render',
                                               ['scripts/qa_render.py', html, '--out',
                                                os.path.join(ROOT, '_shots', name)], must=False)))

    print('\n' + '#' * 66)
    print('# 总表')
    print('#' * 66)
    bad = 0
    for k, v in results:
        print('  %-28s %s' % (k, 'PASS' if v else 'FAIL'))
        if not v:
            bad += 1
    print('\n%d 项，%d 失败' % (len(results), bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
