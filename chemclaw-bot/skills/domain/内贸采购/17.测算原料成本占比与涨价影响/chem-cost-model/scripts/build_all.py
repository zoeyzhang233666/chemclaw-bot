#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键：校验输入 → 计算 → 出 HTML → 出 Excel → 打印缺口摘要。

用法：
  python build_all.py input.json --out out --name DOP-华东
  python build_all.py input.json --out out --name DOP-华东 --skip-check

参数：
  --name     输出文件名前缀（默认取 meta.product_short 或 product）
  --no-html / --no-xlsx  只出其中一种
  --soft     校验有 error 也继续（默认阻断）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cost_engine          # noqa: E402
import validate             # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('--out', default='out')
    ap.add_argument('--name', default=None)
    ap.add_argument('--no-html', action='store_true')
    ap.add_argument('--no-xlsx', action='store_true')
    ap.add_argument('--soft', action='store_true')
    a = ap.parse_args()

    D = json.load(open(a.input, encoding='utf-8'))

    # ---------- 1 校验 ----------
    errors, warns = validate.check(D)
    for w in warns:
        print('  [warn]  ' + w)
    if errors:
        for e in errors:
            print('  [ERROR] ' + e)
        if not a.soft:
            print('\n输入校验未通过（%d 个错误），已中止。修好后重试，或加 --soft 强行继续。' % len(errors))
            return 1
        print('\n（--soft：忽略 %d 个错误继续）' % len(errors))

    # ---------- 2 计算 ----------
    R = cost_engine.compute(D)
    name = a.name or (D.get('meta') or {}).get('product_short') or 'cost-model'
    os.makedirs(a.out, exist_ok=True)
    rj = os.path.join(a.out, 'result.json')
    json.dump(R, open(rj, 'w', encoding='utf-8'), ensure_ascii=False, default=str, indent=1)

    # ---------- 3 出稿 ----------
    made = []
    if not a.no_html:
        import build_html
        p = os.path.join(a.out, name + '_理论原料成本.html')
        build_html.build_html(R, p)
        made.append(p)
    if not a.no_xlsx:
        import build_xlsx
        p = os.path.join(a.out, name + '_理论原料成本.xlsx')
        build_xlsx.build(R, D, p)
        made.append(p)

    # ---------- 4 摘要 ----------
    print('\n=== 结果摘要 ===')
    print('产品      :', (R.get('meta') or {}).get('product'))
    print('数据截止  :', (R.get('meta') or {}).get('as_of'))
    print('口径      :', R.get('price_basis'))
    print('理论原料成本: %.2f 元/吨产品' % R['total'])
    for m in R['materials']:
        if m.get('cost') is None:
            print('   - %-24s 未计入（%s）' % (m['name'][:24], m.get('gap_reason') or '缺价格'))
        else:
            print('   - %-24s %.4f t/t × %.2f = %9.2f  (%5.2f%%)'
                  % (m['name'][:24], m['dosage'], m['price'], m['cost'], m['share']))
    cov = R.get('coverage') or {}
    print('覆盖      : %s / %s 种原料已计价%s'
          % (cov.get('n_computable'), cov.get('n_all'), '（完整）' if cov.get('complete') else '（部分覆盖）'))
    print('\n敏感（±10%）：')
    for s in R['sensitivity']:
        lo = next(c for c in s['cells'] if abs(c['ratio'] + 0.10) < 1e-9)
        hi = next(c for c in s['cells'] if abs(c['ratio'] - 0.10) < 1e-9)
        print('   %-24s %+9.2f / %+9.2f 元/吨' % (s['name'][:24], lo['cost_delta'], hi['cost_delta']))
    print('\n历史窗口：')
    for p in R['periods']:
        if p.get('status') == 'ok':
            print('   %-8s %s→%s  %+.2f 元 (%+.2f%%)'
                  % (p['label'], p.get('start_date') or p.get('from_'),
                     p.get('end_date') or p.get('to_'), p['delta'], p['pct']))
        else:
            print('   %-8s 缺口：%s' % (p['label'], p.get('why') or p.get('reason')))
    if R.get('gaps'):
        print('\n缺口 %d 项（详见页面/「9_缺口与待补」）：' % len(R['gaps']))
        for g in R['gaps'][:10]:
            print('   [%s] %s' % (g.get('type') or 'gap',
                                  (g.get('item') or g.get('field') or g.get('detail') or '')[:70]))

    print('\n产出：')
    for p in made:
        print('   %s  (%.0f KB)' % (p, os.path.getsize(p) / 1024))
    print('   %s' % rj)
    return 0


if __name__ == '__main__':
    sys.exit(main())
