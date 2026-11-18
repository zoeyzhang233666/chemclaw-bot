# -*- coding: utf-8 -*-
"""Generic HS-code case generator.

Two modes:
  1) python new_case.py --blank <target_dir> [--product 品名]
       copy the blank skeleton case.json into <target_dir>
  2) python new_case.py --from-case <existing_case.json> --out <case.json>
       start from an existing case and clear the case-specific parts
"""
import sys, os, json, shutil, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SKELETON = os.path.join(os.path.dirname(HERE), 'examples', '_skeleton', 'case.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blank', help='directory to receive a blank case.json')
    ap.add_argument('--product', default='新产品')
    ap.add_argument('--from-case')
    ap.add_argument('--out')
    a = ap.parse_args()

    if a.blank:
        os.makedirs(a.blank, exist_ok=True)
        case = json.load(open(SKELETON, encoding='utf-8'))
        case['product']['name_cn'] = a.product
        dst = os.path.join(a.blank, 'case.json')
        json.dump(case, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('skeleton written:', dst)
        return

    if a.from_case:
        if not a.out:
            sys.exit('--out is required with --from-case')
        case = json.load(open(a.from_case, encoding='utf-8'))
        case['product'] = {k: '' for k in case['product']}
        case['product']['use'] = []
        case['product']['aliases'] = []
        case['candidates'] = []
        case['ambiguity'], case['foreign'], case['ac'] = [], [], []
        case['missing'], case['confirm'] = [], []
        case['regulatory'] = []
        json.dump(case, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('cleared case written:', a.out)
        return

    ap.print_help()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
