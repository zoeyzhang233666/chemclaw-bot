#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新已保存模型的价格序列：把 input.json 里 history.materials 的旧序列换成最新抓取。

用法：
  python refresh_prices.py input.json --out input.updated.json        # 按 material_id 对应的 pid 重抓
  python refresh_prices.py input.json --prices ./prices               # 用本地已抓的 <name>.json 覆盖

做了什么：
  1. 对每个 history.materials 条目，用 source_url 里的 ppid 或显式 --pid 映射重新抓序列；
  2. 同时更新 materials[].price.value/date（最新价）；
  3. 重写 history.blend，让每一天都有 q；
  4. **不插值、不补历史**：新序列仍只有 93 天，1 年/3 年窗口依然记为缺口。

注意：本脚本只搬数据，不改单耗、不改结论。重跑 build_all.py 才会更新 HTML/Excel。
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def pid_of(url):
    m = re.search(r'ppid=(\d+)', url or '')
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('--out', default=None)
    ap.add_argument('--prices', default=None, help='本地价格目录（含 <name>.json）')
    ap.add_argument('--pid', action='append', default=[], help='material_id=pid')
    a = ap.parse_args()

    D = json.load(open(a.input, encoding='utf-8'))
    out = a.out or os.path.splitext(a.input)[0] + '.updated.json'
    override = dict(x.split('=', 1) for x in a.pid)

    hist = D.get('history') or {}
    mats = hist.get('materials') or []
    if not mats:
        print('没有 history.materials，无需更新。')
        return 1

    changed = 0
    for h in mats:
        mid = h.get('material_id')
        pid = override.get(mid) or pid_of(h.get('source_url'))
        rows = None
        if a.prices:
            cand = [f for f in os.listdir(a.prices) if f.endswith('.json')]
            for f in cand:
                j = json.load(open(os.path.join(a.prices, f), encoding='utf-8'))
                if j.get('pid') == pid or (mid and mid in f):
                    rows = j['rows']
                    h['source'] = j.get('source', h.get('source'))
                    h['retrieved_at'] = j.get('retrieved_at')
                    break
        elif pid:
            tmp = os.path.join(HERE, '_price_tmp')
            subprocess.run([sys.executable, os.path.join(HERE, 'fetch_prices.py'),
                            '--pid', pid, '--name', mid or pid, '--out', tmp], check=False)
            p = os.path.join(tmp, (mid or pid) + '.json')
            if os.path.exists(p):
                rows = json.load(open(p, encoding='utf-8'))['rows']
        if not rows:
            print('  [skip] %s：未取到新序列（pid=%s）' % (mid, pid))
            continue
        h['rows'] = rows
        changed += 1
        last = rows[-1]
        # 同步 materials 的现货价
        for m in D.get('materials') or []:
            if m.get('id') == mid and m.get('price'):
                m['price']['value'] = last['value']
                m['price']['date'] = last['date']
                print('  [ok]   %s：最新 %s = %.2f' % (mid, last['date'], last['value']))
                break
        else:
            print('  [ok]   %s：序列 %d 点（该原料无价格字段，未改成本）' % (mid, len(rows)))

    # 重建 blend
    if changed:
        dates = sorted({r['date'] for h in mats for r in (h.get('rows') or [])})
        q0 = {}
        for m in D.get('materials') or []:
            d = m.get('dosage') or {}
            if d.get('value') is not None:
                q0[m['id']] = d['value']
        hist['blend'] = [{'date': d, 'basis': 'fixed_q0', 'q': dict(q0)} for d in dates]
        hist['as_of'] = dates[-1]
        D['meta']['as_of'] = dates[-1]
        D['history'] = hist

    json.dump(D, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n已写出 %s（更新 %d 条序列）。' % (out, changed))
    print('下一步：python build_all.py "%s" --out out --name <产品>-<区域>' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
