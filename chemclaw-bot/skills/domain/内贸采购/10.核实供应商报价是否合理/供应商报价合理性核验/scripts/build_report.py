# -*- coding: utf-8 -*-
"""一条命令生成报告：research.json → model → HTML + Excel。

用法：
   python scripts/build_report.py examples/01-meg-huadong/research.json
   python scripts/build_report.py <research.json> --out <输出目录>
   python scripts/build_report.py --example 01-meg-huadong

输出文件名：<品种>-<地区>_报价核验报告.html / .xlsx
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import common

EXAMPLES = {'01-meg-huadong': 'examples/01-meg-huadong/research.json'}


def safe(s):
    return ''.join(ch for ch in str(s) if ch not in '\\/:*?"<>|').strip()


def run(cmd):
    print('> ' + ' '.join(cmd))
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True, encoding='utf-8')
    out = (r.stdout or '') + (r.stderr or '')
    print(out.strip()[-1500:])
    if r.returncode != 0:
        raise SystemExit('步骤失败：%s' % cmd[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('research', nargs='?')
    ap.add_argument('--example', help='examples/ 下的示例目录名，如 01-meg-huadong')
    ap.add_argument('--out', help='输出目录，默认与 research.json 同级 output/')
    ap.add_argument('--no-check', action='store_true', help='跳过自检')
    a = ap.parse_args()

    if a.example:
        if a.example not in EXAMPLES:
            raise SystemExit('未知示例 %s，可选：%s' % (a.example, ', '.join(EXAMPLES)))
        research = os.path.join(SKILL, EXAMPLES[a.example].replace('/', os.sep))
    elif a.research:
        research = a.research
    else:
        raise SystemExit('请给 research.json 或 --example')

    if not os.path.exists(research):
        raise SystemExit('找不到 %s' % research)

    out_dir = a.out or os.path.join(os.path.dirname(os.path.abspath(research)), 'output')
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(SKILL, 'work')
    os.makedirs(work, exist_ok=True)
    model_path = os.path.join(work, os.path.basename(os.path.dirname(os.path.abspath(research))) + '_model.json')

    run([os.path.join(HERE, 'model.py'), research, '--out', model_path])
    m = common.load_json(model_path)
    base = safe('%s-%s' % (m['quote'].get('product_name', '品种'), m['quote'].get('region_supplier', '地区')))
    hp = os.path.join(out_dir, base + '_报价核验报告.html')
    xp = os.path.join(out_dir, base + '_报价核验.xlsx')
    run([os.path.join(HERE, 'build_html.py'), model_path, '--out', hp])
    run([os.path.join(HERE, 'build_xlsx.py'), model_path, '--out', xp])

    print('\n产物：')
    print('  %s' % hp)
    print('  %s' % xp)
    if not a.no_check:
        rc = subprocess.run([sys.executable, os.path.join(HERE, 'check_output.py'), model_path, out_dir],
                            text=True, encoding='utf-8')
        print('自检返回码：%d' % rc.returncode)
    return 0


if __name__ == '__main__':
    sys.exit(main())
