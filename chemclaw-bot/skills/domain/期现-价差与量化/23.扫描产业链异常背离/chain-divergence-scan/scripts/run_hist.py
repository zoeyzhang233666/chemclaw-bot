# -*- coding: utf-8 -*-
"""假设历史区间扫描：在过去 12 个月里，每隔 20 个交易日把"当下"回拨一次，
看同一套阈值下哪些组合、在哪些时点会被判为"异常背离"。

用途：
  1) 量化"扫描器本身的假阳性率"——若历史上频繁亮红灯，说明阈值偏松或关系本身不稳定；
  2) 给当下结论提供上下文——当下的 |z| 在历史扫描里属于什么水平。

输出 build/out/hist_scan.json
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_scan as R  # noqa: E402


def month_list(last_date, months=12, step_days=20):
    y, m, d = map(int, last_date.split('-'))
    out = []
    for k in range(months, 0, -1):
        mm = m - k
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        # 每月取 20 日（若 20 日非交易日，scan() 会按 <= cut_off 取最近交易日）
        out.append(f'{yy:04d}-{mm:02d}-20')
    # 额外补 3 个月末点位，覆盖更多制度状态
    for k in (3, 6, 9):
        mm = m - k
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        out.append(f'{yy:04d}-{mm:02d}-05')
    return sorted(set(out))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    ap.add_argument('--out', default='build/out')
    ap.add_argument('--months', type=int, default=12)
    ap.add_argument('--perm', type=int, default=0)
    a = ap.parse_args(argv)

    series, _ = R.load_universe(a.data)
    last = max(s['dates'][-1] for s in series.values())
    dates = month_list(last, a.months)

    log = []
    for cut in dates:
        pack = R.scan(data_dir=a.data, out=a.out,
                      params=dict(perm_n=a.perm), cut_off=cut, verbose=False,
                      dump_series=False)
        for r in pack['results']:
            if r.get('status') != 'ok':
                continue
            log.append(dict(cut_off=cut, actual_last=r['last'],
                            pair=f"{r['code_a']}/{r['code_b']}", rtype=r['rtype'],
                            verdict=r['judge']['verdict'], score=r['judge']['score'],
                            z=r['z_last'], z_run=r['z_run_days'],
                            r_roll=r['roll_corr_last'], corr_drop=r['judge'].get('corr_drop'),
                            spread_pct=r['spread_pct']))
        n_anom = sum(1 for x in log if x['cut_off'] == cut and x['verdict'] == '异常背离（候选）')
        print(f'[hist] cut-off {cut} → 实际末交易日 {pack["results"][0].get("last") if pack["results"] else "-"}，'
              f'候选异常 {n_anom} 个', flush=True)

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'hist_scan.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(generated_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                       months=a.months, cut_offs=dates, rows=log), f, ensure_ascii=False, indent=1)

    # 汇总：每个组合在历史扫描里被判为"异常"的频率
    agg = {}
    for x in log:
        v = agg.setdefault(x['pair'], dict(pair=x['pair'], rtype=x['rtype'], n=0, n_anom=0,
                                           zmax=None, zvals=[]))
        v['n'] += 1
        v['zvals'].append(x['z'])
        if x['verdict'] == '异常背离（候选）':
            v['n_anom'] += 1
    for v in agg.values():
        zs = [z for z in v['zvals'] if z is not None]
        v['zmax'] = max(zs) if zs else None
        v['ai_min'] = min(zs) if zs else None
        v['zvals'] = [round(z, 3) if z is not None else None for z in zs]
    with open(os.path.join(a.out, 'hist_scan_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(sorted(agg.values(), key=lambda x: -x['n_anom']), f, ensure_ascii=False, indent=1)
    print('\n组合在历史扫描中被判为"异常背离（候选）"的次数：')
    for v in sorted(agg.values(), key=lambda x: -x['n_anom']):
        print(f"  {v['pair']:10s} {v['n_anom']:2d}/{v['n']:2d}   z 区间 {v['ai_min']:.2f} ~ {v['zmax']:.2f}")


if __name__ == '__main__':
    main()
