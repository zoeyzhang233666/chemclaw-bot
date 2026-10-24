# -*- coding: utf-8 -*-
"""
两指标相关性研究 —— 主分析脚本（纯标准库，可直接运行，也可被 Excel/HTML 生成脚本 import）

用法：
  python scripts/analyze.py --csv data/demo_methanol_weekly.csv \
      --date-col week_ending --x-col inventory_total --y-col spot_taicang \
      --x-form level --y-form pct --windows 12,26,52 --breaks 2023-01-01,2025-01-01 \
      --out out/result.json

输出 result.json：包含总体相关系数（Pearson / Spearman / 去趋势 / 差分）、显著性、置信区间、
HAC 标准误、滚动相关、分阶段结果、离群点敏感性、滞后相关、伪相关诊断（自相关、有效样本量、偏相关）。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corrlib as C  # noqa: E402

TRANSFORM_LABEL = {'level': '原值（水平）', 'change': '一阶差分（绝对变化）',
                   'pct': '环比变化率（%）', 'yoy': '同比变化率（%）'}


def read_csv(path, **colmap):
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        rd = csv.DictReader(f)
        for r in rd:
            rows.append(r)
    return rows


def to_num(v):
    if v is None:
        return None
    s = str(v).strip().replace(',', '')
    if s in ('', '-', '—', 'NA', 'N/A', 'null', 'None'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--date-col', default='date')
    ap.add_argument('--x-col', required=True)
    ap.add_argument('--y-col', required=True)
    ap.add_argument('--x-name', default=None)
    ap.add_argument('--y-name', default=None)
    ap.add_argument('--x-unit', default='')
    ap.add_argument('--y-unit', default='')
    ap.add_argument('--x-form', default='level', choices=['level', 'change', 'pct', 'yoy'])
    ap.add_argument('--y-form', default='level', choices=['level', 'change', 'pct', 'yoy'])
    ap.add_argument('--windows', default='12,26,52')
    ap.add_argument('--min-pairs-ratio', type=float, default=0.8)
    ap.add_argument('--breaks', default='')
    ap.add_argument('--control-col', default='', help='共同外部因素列（如煤价），用于偏相关诊断')
    ap.add_argument('--lag-max', type=int, default=4)
    ap.add_argument('--sub', action='append', default=[], help='额外对照组合，如 inventory_total:level:spot_taicang:pct')
    ap.add_argument('--out', default='')
    args = ap.parse_args(argv)

    rows = read_csv(args.csv)
    dates = [r[args.date_col].strip() for r in rows]
    order = sorted(range(len(dates)), key=lambda i: dates[i])
    rows = [rows[i] for i in order]
    dates = [dates[i] for i in order]

    x_raw = [to_num(r[args.x_col]) for r in rows]
    y_raw = [to_num(r[args.y_col]) for r in rows]
    x_name = args.x_name or args.x_col
    y_name = args.y_name or args.y_col

    windows = [int(w) for w in args.windows.split(',') if w.strip()]
    breaks = [b.strip() for b in args.breaks.split(',') if b.strip()]

    result = {
        'meta': {
            'csv': os.path.basename(args.csv),
            'date_col': args.date_col,
            'x': {'col': args.x_col, 'name': x_name, 'unit': args.x_unit, 'form': args.x_form,
                  'form_label': TRANSFORM_LABEL[args.x_form]},
            'y': {'col': args.y_col, 'name': y_name, 'unit': args.y_unit, 'form': args.y_form,
                  'form_label': TRANSFORM_LABEL[args.y_form]},
            'period': [dates[0], dates[-1]],
            'n_rows': len(dates),
            'windows': windows,
            'breaks': breaks,
        },
        'raw': {'dates': dates, 'x': x_raw, 'y': y_raw},
        'quality': {},
        'overall': {},
        'rolling': {},
        'phases': {},
        'sensitivity': {},
        'lag': {},
        'spurious': {},
    }

    # ---------------- 数据质量
    def gaps(vals):
        miss = [i for i, v in enumerate(vals) if v is None]
        return {'n_missing': len(miss), 'missing_dates': [dates[i] for i in miss][:20]}
    result['quality'] = {
        'x_missing': gaps(x_raw),
        'y_missing': gaps(y_raw),
        'n_pairs': sum(1 for a, b in zip(x_raw, y_raw) if a is not None and b is not None),
        'date_min': dates[0], 'date_max': dates[-1],
    }

    # ---------------- 变换
    x_f = C.transform(x_raw, args.x_form)
    y_f = C.transform(y_raw, args.y_form)
    px, py, pdates = C.align(x_f, y_f, dates)
    result['aligned'] = {'dates': pdates, 'x': px, 'y': py, 'n': len(px)}

    # ---------------- 总体
    ov = C.corr_stats(px, py, hac_lags=max(0, len(px) // 20))
    ov['spearman'] = C.spearman(px, py)
    ov['spearman_n'] = len(px)
    # 去趋势（时间趋势控制）：仅在水平形态下有意义
    idx = list(range(len(px)))
    rx, ry = C.detrend(idx, px), C.detrend(idx, py)
    ov['detrended_r'] = C.pearson(rx, ry) if (rx and ry) else None
    # 一阶差分（消除趋势的另一种做法）
    ov['diff_r'] = C.pearson(C.diff(px), C.diff(py)) if len(px) > 3 else None
    neff, r1x, r1y = C.effective_n(px, py)
    ov['autocorr_x'], ov['autocorr_y'] = r1x, r1y
    ov['n_eff'] = neff
    ov['r_simple'] = ov['r']
    if ov.get('r') is not None and neff > 2 and abs(ov['r']) < 1:
        t_eff = ov['r'] * ((neff - 2) / (1 - ov['r'] ** 2)) ** 0.5
        ov['p_eff'] = C.t_pvalue(t_eff, neff - 2)
    result['overall'] = ov

    # ---------------- 滚动
    for w in windows:
        r, pairs, insuff = C.window_stats(x_f, y_f, w, min_pairs=max(5, int(round(w * args.min_pairs_ratio))))
        result['rolling'][str(w)] = {'dates': dates, 'r': r, 'pairs': pairs,
                                     'insufficient_idx': insuff,
                                     'min_pairs': max(5, int(round(w * args.min_pairs_ratio)))}

    # ---------------- 分阶段
    if breaks:
        phases = C.phase_split(dates, breaks)
        out = []
        for label, idxs in phases:
            sx = [x_f[i] for i in idxs]
            sy = [y_f[i] for i in idxs]
            sx2, sy2, _ = C.align(sx, sy, [dates[i] for i in idxs])
            st = C.corr_stats(sx2, sy2)
            st['label'] = label
            st['dates'] = [dates[i] for i in idxs][:1] + [dates[i] for i in idxs][-1:]
            st['n_pairs'] = len(sx2)
            st['spearman'] = C.spearman(sx2, sy2)
            out.append(st)
        result['phases'] = out

    # ---------------- 离群点敏感性（按 |x| 与 |y| 最高/最低 5% 剔除）
    def drop_extreme(a, b, frac=0.05):
        n = len(a)
        k = max(1, int(round(n * frac)))
        ex = set(sorted(range(n), key=lambda i: a[i])[:k] + sorted(range(n), key=lambda i: a[i])[-k:])
        ey = set(sorted(range(n), key=lambda i: b[i])[:k] + sorted(range(n), key=lambda i: b[i])[-k:])
        ex = ex | ey
        ax = [a[i] for i in range(n) if i not in ex]
        by = [b[i] for i in range(n) if i not in ex]
        return C.corr_stats(ax, by)
    result['sensitivity'] = {
        'drop_5pct': drop_extreme(px, py),
        'first_half': C.corr_stats(px[:len(px) // 2], py[:len(py) // 2]) if len(px) >= 8 else {},
        'second_half': C.corr_stats(px[len(px) // 2:], py[len(py) // 2:]) if len(px) >= 8 else {},
    }

    # ---------------- 滞后
    lags = []
    for L in range(-args.lag_max, args.lag_max + 1):
        r = C.lag_corr(px, py, L)
        st = C.corr_stats(px[max(0, -L):len(px) - max(0, L)] if L >= 0 else px[-L:],
                          py[L:] if L >= 0 else py[:L]) if L != 0 else C.corr_stats(px, py)
        lags.append({'lag': L, 'r': r, 'n': st.get('n'), 'p': st.get('p')})
    result['lag'] = lags

    # ---------------- 伪相关诊断
    sp = {}
    if rx and ry:
        sp['trend_share'] = {
            'x_r2_time': C.linreg(idx, px)['r2'] if C.linreg(idx, px) else None,
            'y_r2_time': C.linreg(idx, py)['r2'] if C.linreg(idx, py) else None,
        }
    if args.control_col:
        c = [to_num(r[args.control_col]) for r in rows]
        cx, cy, cd = C.align(px, py, pdates)
        cmap = dict(zip(dates, c))
        cz = [cmap.get(d) for d in cd]
        keep = [(a, b, z) for a, b, z in zip(cx, cy, cz) if z is not None]
        if len(keep) >= 6:
            sp['partial_r_given_control'] = C.partial_corr([k[0] for k in keep],
                                                           [k[1] for k in keep],
                                                           [k[2] for k in keep])
            sp['control_col'] = args.control_col
            sp['n_used'] = len(keep)
    result['spurious'] = sp

    # ---------------- 子对照（形态组合矩阵）
    if args.sub:
        subs = []
        for spec in args.sub:
            parts = spec.split(':')
            if len(parts) < 4:
                continue
            xc, xfm, yc, yfm = parts[:4]
            xs = [to_num(r[xc]) for r in rows]
            ys = [to_num(r[yc]) for r in rows]
            xf = C.transform(xs, xfm)
            yf = C.transform(ys, yfm)
            a, b, _ = C.align(xf, yf, dates)
            st = C.corr_stats(a, b)
            st.update({'x_col': xc, 'x_form': xfm, 'y_col': yc, 'y_form': yfm,
                       'x_label': TRANSFORM_LABEL[xfm], 'y_label': TRANSFORM_LABEL[yfm]})
            subs.append(st)
        result['sub'] = subs

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(result, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('written', args.out)
    return result


if __name__ == '__main__':
    main()
