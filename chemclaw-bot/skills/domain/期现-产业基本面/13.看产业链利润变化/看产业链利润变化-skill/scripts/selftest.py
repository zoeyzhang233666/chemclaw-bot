# -*- coding: utf-8 -*-
"""一键自检：依次运行全部校验，全部通过才算可交付。

    python selftest.py

退出码 0 = 全部通过。
"""
import io
import os
import sys
import subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable

SUITES = [
    ('模型与数据校验', 'verify_model.py'),
    ('前端渲染与交互校验', 'verify_ui.py'),
    ('Excel 公式回算校验', 'verify_xlsx.py'),
]


def run(script):
    """用文件重定向而非管道，避免受限环境下 stdio 管道被阻塞。"""
    log = os.path.join(ROOT, 'build', '_suites', script.replace('.py', '.log'))
    os.makedirs(os.path.dirname(log), exist_ok=True)
    cmd = '"%s" "%s" > "%s" 2>&1' % (PY, os.path.join(HERE, script), log)
    code = subprocess.call(cmd, shell=True, cwd=HERE)
    try:
        with open(log, encoding='utf-8', errors='replace') as f:
            return code, f.read()
    except FileNotFoundError:
        return code, ''


def main():
    print('=' * 68)
    print('  产业链利润模型 · 交付前自检')
    print('=' * 68)
    results = []
    for name, script in SUITES:
        print('\n>>> %s (%s)' % (name, script))
        code, out = run(script)
        tail = [l for l in out.splitlines() if '通过' in l or '[FAIL]' in l]
        for l in tail[-12:]:
            print('    ' + l)
        results.append((name, code == 0))
        print('    => %s' % ('PASS' if code == 0 else 'FAIL'))

    # 交付物存在性
    print('\n>>> 交付物检查')
    outs = os.path.join(ROOT, 'output')
    need = [('.html', 800), ('.xlsx', 20)]
    ok_all = True
    for ext, min_kb in need:
        fs = [f for f in os.listdir(outs) if f.endswith(ext)] if os.path.isdir(outs) else []
        if fs:
            sz = os.path.getsize(os.path.join(outs, fs[0])) / 1024
            good = sz >= min_kb
            print('    [%s] %s  %.1f KB' % ('PASS' if good else 'FAIL', fs[0], sz))
            ok_all &= good
        else:
            print('    [FAIL] 缺少 *%s' % ext)
            ok_all = False
    results.append(('交付物', ok_all))

    print('\n' + '=' * 68)
    bad = [n for n, ok in results if not ok]
    if bad:
        print('  自检未通过：%s' % ', '.join(bad))
        print('=' * 68)
        return 1
    print('  全部通过 —— 可以交付')
    print('=' * 68)
    return 0


if __name__ == '__main__':
    sys.exit(main())
