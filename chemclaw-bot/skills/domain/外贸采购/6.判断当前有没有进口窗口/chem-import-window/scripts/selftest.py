# -*- coding: utf-8 -*-
"""selftest.py — 一键全量自检

用法:
    python scripts/selftest.py                 # 跑所有示例的全部检查
    python scripts/selftest.py --case <case>   # 只跑指定案例

按顺序执行（任一环节失败即汇总报错）：
  1. node scripts/validate.js            数据契约 + 禁用词 + 来源完整性
  2. node scripts/cross_check.js         JS 引擎 vs Python 基准（含 360 个场景矩阵）
  3. node scripts/build_html.cjs         生成 HTML（并断言无外部请求）
  4. python scripts/qa_render.py         页面数字 vs 引擎 + 交互重算
  5. python scripts/qa_layout.py         区块齐全 + 无溢出 + 响应式
  6. python scripts/build_xlsx.py        生成 Excel
  7. python scripts/check_xlsx.py        LibreOffice 重算 + 活公式验证 + 引擎比对
"""
import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def run(title, cmd, allow_fail=False):
    print('\n' + '=' * 74)
    print('▶ ' + title)
    print('=' * 74)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    print(out.rstrip())
    ok = (r.returncode == 0)
    if not ok and not allow_fail:
        print('  ✗ 该步失败（退出码 %s）' % r.returncode)
    return ok


def discover():
    ex = os.path.join(ROOT, 'examples')
    cases = []
    for name in sorted(os.listdir(ex)):
        p = os.path.join(ex, name, 'data', 'case.json')
        if os.path.isfile(p):
            cases.append((name, p))
    return cases


def main():
    if '--case' in sys.argv:
        cases = [('指定案例', sys.argv[sys.argv.index('--case') + 1])]
    else:
        cases = discover()

    if not cases:
        print('未找到任何 examples/*/data/case.json')
        return 2

    results = []
    for name, case in cases:
        print('\n' + '#' * 74)
        print('# 示例：' + name)
        print('#' * 74)
        out_dir = os.path.join(ROOT, 'examples', name, 'out')
        os.makedirs(out_dir, exist_ok=True)
        html = os.path.join(out_dir, 'import-window.html')
        xlsx = os.path.join(out_dir, 'import-window.xlsx')
        eng = os.path.join(out_dir, 'engine-result.json')

        steps = [
            ('数据契约校验', ['node', 'scripts/validate.js', case]),
            ('三路交叉校验（JS 引擎 vs Python 基准）', ['node', 'scripts/cross_check.js', case]),
            ('生成单文件 HTML', ['node', 'scripts/build_html.cjs', case, html]),
            ('页面渲染与交互 QA', [PY, 'scripts/qa_render.py', html, '--case', case]),
            ('版面与响应式 QA', [PY, 'scripts/qa_layout.py', html]),
            ('生成 Excel（活公式）', [PY, 'scripts/build_xlsx.py', case, xlsx, '--engine-json', eng]),
            ('Excel 重算校验', [PY, 'scripts/check_xlsx.py', xlsx, '--case', case]),
        ]
        # 第 6 步需要先有引擎结果文件
        def engine_json():
            js = ("const fs=require('fs');const e=require('./scripts/lib/import-window-engine.js');"
                  "const a=e.analyze(JSON.parse(fs.readFileSync(%r,'utf8')));"
                  "fs.writeFileSync(%r,JSON.stringify({cif_cny:a.current.totals.cif_cny,"
                  "duty:a.current.totals.duty,vat:a.current.totals.vat,cost:a.current.totals.net_cost,"
                  "spread:a.current.spread.abs_cny},null,1));" % (case, eng))
            return subprocess.run(['node', '-e', js], cwd=ROOT, capture_output=True, text=True)

        ok_all = True
        for title, cmd in steps:
            if title.startswith('生成 Excel'):
                engine_json()
            ok = run(title, cmd)
            results.append((name, title, ok))
            ok_all = ok_all and ok
        print('\n>>> 示例 %s：%s' % (name, '通过' if ok_all else '存在失败项'))

    print('\n' + '=' * 74)
    print('自检汇总')
    print('=' * 74)
    for name, title, ok in results:
        print('  %s  %-12s %s' % ('✓' if ok else '✗', name, title))
    bad = [r for r in results if not r[2]]
    print('\n结果: ' + ('全部通过（共 %d 项检查）' % len(results) if not bad
                        else '%d / %d 项失败' % (len(bad), len(results))))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
