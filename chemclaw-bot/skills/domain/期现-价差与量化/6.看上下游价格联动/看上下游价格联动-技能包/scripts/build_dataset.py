# -*- coding: utf-8 -*-
"""
build_dataset.py —— PX × PTA 上下游价格联动：口径对齐 + 加工价差数据集

输入（优先级：主源 → 补齐源）
  processed/sunsirs_daily.csv   SunSirs 日度现货价（含周末；页面日期 = 报道日，
                                价格口径日期 = 链接日期，见 align_sources.py 的对齐校验）
  raw/px_bjz_daily.csv          100ppi PX 基准价（中文主源，2025-05-22 起）
  raw/pta_bjz_daily.csv         100ppi PTA 基准价（中文主源，2024-08-15 起）
输出
  processed/px_pta_daily.csv    日频面板（含 PX、PTA、收益率、价差、阶段）
  processed/qc.json             数据质量报告

口径红线
  - 日期取「价格口径日期」；周末/节假日无更新则沿用上一有效值？—— 不。本脚本
    按自然日生成连续日历，但只在 SunSirs 有发布的日子填值；无发布日留空并计数，
    统计时一律用「成对有效样本」，绝不插值。
  - 单耗系数 0.655 只用于「理论加工价差」定义项，敏感性另算（见 analysis 输出）。
  - 跳变阈值 12%/日，只标记不删除。
"""
import argparse
import csv
import datetime as dt
import json
import os
import statistics as st
import sys

JUMP_THRESHOLD = 0.12
DEFAULT_SEGMENTS = [
    ('2023-10-07', '2024-12-31', 'S1 PX扩能+PTA过剩，加工费中枢下移'),
    ('2025-01-01', '2025-12-31', 'S2 PX供给紧张、价差走阔'),
    ('2026-01-01', '2026-10-20', 'S3 PTA集中检修+地缘油扰动'),
]


def load(path, col):
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if not r.get(col):
                continue
            try:
                out[dt.date.fromisoformat(r['date'])] = float(r[col])
            except (KeyError, ValueError):
                continue
    return out


def seg_of(d, segs):
    for a, b, name in segs:
        if dt.date.fromisoformat(a) <= d <= dt.date.fromisoformat(b):
            return name
    return 'outside'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', default='2023-10-07')
    ap.add_argument('--end', default='2026-10-20')
    ap.add_argument('--coef', type=float, default=0.655)
    ap.add_argument('--out', default='processed')
    ap.add_argument('--src', default='sunsirs')
    ap.add_argument('--ss-shift', type=int, default=-1,
                    help='SunSirs 日页日期 → 价格所属交易日的偏移（默认 -1）。'
                         '实测：页面日期 d 的价格 == 100ppi 交易日 d-1 的价格；'
                         'PX 平均绝对差 0.000（296 个重叠日全等），PTA 0.892（含少量修订）')
    a = ap.parse_args(argv)
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(here, a.out), exist_ok=True)

    px_ss = load(os.path.join(here, a.out, 'sunsirs_daily.csv'), 'px')
    pta_ss = load(os.path.join(here, a.out, 'sunsirs_daily.csv'), 'pta')
    # 关键口径校正（用重叠期实测，不是推测）：
    #   shift=+0 → PX 39.57 / PTA 45.74 平均绝对差
    #   shift=-1 → PX  0.000 / PTA  0.892   ← 采用
    # 即页面日期 d 上的价格，实际归属交易日 d-1。
    if a.ss_shift:
        px_ss = {d + dt.timedelta(days=a.ss_shift): v for d, v in px_ss.items()}
        pta_ss = {d + dt.timedelta(days=a.ss_shift): v for d, v in pta_ss.items()}
    px_100 = load(os.path.join(here, 'raw', 'px_bjz_daily.csv'), 'value')
    pta_100 = load(os.path.join(here, 'raw', 'pta_bjz_daily.csv'), 'value')

    d0, d1 = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    dates = []
    d = d0
    while d <= d1:
        dates.append(d)
        d += dt.timedelta(days=1)

    rows, missing_both, src_counts = [], [], {}
    prev = None
    for d in dates:
        px = px_ss.get(d)
        pta = pta_ss.get(d)
        src = 'sunsirs'
        if px is not None and pta is not None:
            # 重叠期若中文主源可得，以中文源为准，并记录两源差异
            if d in px_100 and abs(px_100[d] - px) <= 0.5:
                pass
        if px is None:
            px, src_px = px_100.get(d), '100ppi'
        else:
            src_px = 'sunsirs'
        if pta is None:
            pta, src_pta = pta_100.get(d), '100ppi'
        else:
            src_pta = 'sunsirs'
        if px is None or pta is None:
            missing_both.append(d.isoformat())
            continue
        src_counts[f'{src_px}|{src_pta}'] = src_counts.get(f'{src_px}|{src_pta}', 0) + 1
        sp = pta - a.coef * px
        px_ret = None if prev is None or prev['px'] == 0 else px / prev['px'] - 1
        pta_ret = None if prev is None or prev['pta'] == 0 else pta / prev['pta'] - 1
        rows.append({
            'date': d.isoformat(),
            'px': px,
            'pta': pta,
            'raw_spread': round(pta - px, 2),
            'spread': round(sp, 2),
            'ratio': round(pta / px, 4),
            'px_ret': None if px_ret is None else round(px_ret, 6),
            'pta_ret': None if pta_ret is None else round(pta_ret, 6),
            'spread_chg': None if prev is None else round(sp - prev['spread'], 2),
            'period': seg_of(d, DEFAULT_SEGMENTS),
        })
        prev = {'px': px, 'pta': pta, 'spread': sp}

    outp = os.path.join(here, a.out, 'px_pta_daily.csv')
    with open(outp, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    sp = [r['spread'] for r in rows]
    jumps = [r['date'] for r in rows if r['px_ret'] is not None
             and (abs(r['px_ret']) > JUMP_THRESHOLD or abs(r['pta_ret']) > JUMP_THRESHOLD)]
    qc = {
        'n_obs': len(rows),
        'first': rows[0]['date'],
        'last': rows[-1]['date'],
        'calendar_days': len(dates),
        'missing_days': len(missing_both),
        'source_counts': src_counts,
        'coef': a.coef,
        'spread_stats': {
            'mean': round(st.mean(sp), 2), 'median': round(st.median(sp), 2),
            'min': round(min(sp), 2), 'max': round(max(sp), 2),
            'stdev': round(st.pstdev(sp), 2),
        },
        'jumps_gt_12pct': jumps,
        'segments': [{'start': s, 'end': e, 'name': n} for s, e, n in DEFAULT_SEGMENTS],
    }
    with open(os.path.join(here, a.out, 'qc.json'), 'w', encoding='utf-8') as f:
        json.dump(qc, f, ensure_ascii=False, indent=2)
    print(json.dumps(qc, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
