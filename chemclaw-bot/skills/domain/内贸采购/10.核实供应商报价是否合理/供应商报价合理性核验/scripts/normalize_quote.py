# -*- coding: utf-8 -*-
"""第 1 步单独跑：把报价标准化成四个靶心。

用法：
  python scripts/normalize_quote.py <quote.json> --spec meg --out work/quote_norm.json

quote.json 可以是 research.json（取 quote 字段），也可以是 examples/*/input/quote_input.json
这种报价单原档（会自动映射 price.value / tax.included / delivery.basis 等字段）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common


def load_quote(path):
    d = common.load_json(path)
    if 'quote' in d and isinstance(d['quote'], dict):
        q = dict(d['quote'])
        q['_spec_file'] = (d.get('meta') or {}).get('spec_file')
        return q
    # 报价单原档格式（input/quote_input.json）
    price = d.get('price') or {}
    tax = d.get('tax') or {}
    dlv = d.get('delivery') or {}
    qty = d.get('quantity') or {}
    pay = d.get('payment') or {}
    q = {
        'is_test_input': d.get('is_test_input', False),
        'supplier_label': (d.get('supplier') or {}).get('name') or d.get('supplier_label'),
        'supplier_type': (d.get('supplier') or {}).get('type'),
        'product_name': d.get('product') or d.get('product_name'),
        'spec_text': d.get('spec_claimed') or d.get('spec_text'),
        'grade_claimed': d.get('spec_claimed') or d.get('grade_claimed'),
        'purity': d.get('purity_claimed', d.get('purity')),
        'process': d.get('process_claimed', d.get('process')),
        'value': price.get('value', d.get('value')),
        'unit': price.get('unit', d.get('unit', '元/吨')),
        'tax': {'included': tax.get('included', True), 'vat_rate': tax.get('rate', 0.13),
                'text': tax.get('text', '')},
        'delivery': {'basis': dlv.get('basis', 'ex_works'), 'text': dlv.get('text', ''),
                     'origin': (d.get('supplier') or {}).get('origin')},
        'destination': d.get('destination'),
        'region': d.get('destination'),
        'region_supplier': d.get('region_supplier') or (d.get('supplier') or {}).get('origin'),
        'quantity': {'value': qty.get('value'), 'unit': qty.get('unit', '吨'), 'basis': qty.get('tier_note', '')},
        'payment': {'terms': pay.get('terms', ''), 'cash_discounted': False},
        'packing': d.get('packing'), 'validity': d.get('validity'),
        'pricing_formula': d.get('pricing_formula'), 'quote_date': d.get('received_at') or d.get('quote_date'),
        'unknowns': d.get('unknowns') or [], 'raw_text': d.get('raw_text', ''),
        'origin': (d.get('supplier') or {}).get('origin') or d.get('origin'),
        'transport': d.get('transport') or {}, 'credit': d.get('credit') or {},
        '_spec_file': d.get('spec_file'),
    }
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('quote')
    ap.add_argument('--spec', help='规格文件名（去 .json）或路径；省略则用 quote._spec_file')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    q = load_quote(a.quote)
    spec_name = a.spec or q.get('_spec_file')
    if not spec_name:
        raise SystemExit('未指定规格文件：请加 --spec <品种代码>（见 specs/）')
    if os.path.exists(spec_name):
        spec = common.load_spec(spec_name)
    else:
        spec = common.load_spec(os.path.basename(str(spec_name)))
    norm = common.standardize(q, spec)
    out = {'quote': q, 'spec': {'family': spec.get('family'), 'vat_rate': spec.get('vat_rate')},
           'normalized': {k: v for k, v in norm.items() if k != '_meta'}, 'meta': norm['_meta']}
    common.dump_json(out, a.out)
    print('OK -> %s' % a.out)
    for k in ('included|ex_works', 'excluded|ex_works', 'included|delivered', 'excluded|delivered'):
        t, d = k.split('|')
        print('  %-10s %-10s %s' % ('含税' if t == 'included' else '不含税',
                                    '出厂' if d == 'ex_works' else '到厂',
                                    ('%s 元/吨' % common.fmt(norm[k]['value'])) if norm[k]['value'] is not None
                                    else '缺口：%s' % norm[k].get('gap_reason', '')))


if __name__ == '__main__':
    main()
