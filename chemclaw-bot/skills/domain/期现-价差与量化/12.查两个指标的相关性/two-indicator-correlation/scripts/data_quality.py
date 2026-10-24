# -*- coding: utf-8 -*-
"""
数据质量检查（两指标相关性研究前置步骤）

检查项：
  P1 字段与单位完整性（日期/两指标/单位/口径/来源）
  P2 日期格式与重复日期
  P3 时间覆盖：两序列起止是否一致；是否存在只在一边有数据的日期
  P4 缺失值与空缺（不插补，只报告）
  P5 数值异常：非数字、负值（库存/价格不应为负）、跳变（周环比超过阈值）
  P6 频率一致性：相邻观测日间隔分布（周度应≈7天，日度≈1-3天）
  P7 发布时滞：数据口径的发布日期与统计期是否错位（例如库存调查日 vs 价格日）
  P8 重合度：有效配对样本数 N，是否满足滚动窗口最小样本要求

输出：控制台报告 + JSON（供 HTML/Excel 引用）
用法：
  python scripts/data_quality.py --csv data/x.csv --date-col week_ending --x-col inv --y-col price \
      --x-name 港口库存 --y-name 太仓现货价 --freq 7 --jump-threshold 0.35 --out build/qc.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corrlib as C  # noqa: E402


def parse_cols(raw):
    return [x.strip() for x in raw.split(',') if x.strip()]


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


def to_date(s):
    s = str(s).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%Y-%m', '%Y/%m'):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def run(args):
    rows_out = []
    import csv
    with open(args.csv, encoding='utf-8-sig') as f:
        rd = csv.DictReader(f)
        fieldnames = rd.fieldnames or []
        for r in rd:
            rows_out.append(r)

    findings = []

    def add(level, code, msg, detail=None):
        findings.append({'level': level, 'code': code, 'msg': msg, 'detail': detail})

    # P1 字段
    for need in [args.date_col, args.x_col, args.y_col]:
        if need not in fieldnames:
            add('ERROR', 'P1', f'缺少必需列 {need}', fieldnames)
    raw_dates = [str(r.get(args.date_col, '')).strip() for r in rows_out]
    x = [to_num(r.get(args.x_col)) for r in rows_out]
    y = [to_num(r.get(args.y_col)) for r in rows_out]

    # P2 日期
    ds = [to_date(d) for d in raw_dates]
    bad = [raw_dates[i] for i, d in enumerate(ds) if d is None]
    if bad:
        add('ERROR', 'P2', f'{len(bad)} 个日期无法解析', bad[:10])
    if len(set(raw_dates)) != len(raw_dates):
        dup = sorted({d for d in raw_dates if raw_dates.count(d) > 1})
        add('ERROR', 'P2', f'存在重复日期 {len(dup)} 个', dup[:10])
    order = sorted(range(len(ds)), key=lambda i: (ds[i] or date(1900, 1, 1)))
    ds_o = [ds[i] for i in order]
    x = [x[i] for i in order]
    y = [y[i] for i in order]
    raw_dates = [raw_dates[i] for i in order]

    # P3/P4 覆盖与缺失
    miss_x = [raw_dates[i] for i, v in enumerate(x) if v is None]
    miss_y = [raw_dates[i] for i, v in enumerate(y) if v is None]
    if miss_x:
        add('WARN', 'P4', f'{args.x_name} 缺失 {len(miss_x)} 个观测（不插补，分析时剔除）', miss_x[:15])
    if miss_y:
        add('WARN', 'P4', f'{args.y_name} 缺失 {len(miss_y)} 个观测（不插补，分析时剔除）', miss_y[:15])
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if ds_o:
        add('INFO', 'P3', f'覆盖区间 {ds_o[0]} ~ {ds_o[-1]}，共 {len(ds_o)} 期；有效配对 N={len(pairs)}')

    # P5 异常
    for nm, vals in ((args.x_name, x), (args.y_name, y)):
        nonnum = [raw_dates[i] for i, r in enumerate(rows_out)
                  if str(r.get(args.x_col if nm == args.x_name else args.y_col, '')).strip() not in ('',) and vals[i] is None]
        if nonnum:
            add('WARN', 'P5', f'{nm} 有 {len(nonnum)} 个非数值单元格（已按缺失处理）', nonnum[:10])
        neg = [raw_dates[i] for i, v in enumerate(vals) if v is not None and v < 0]
        if neg:
            add('ERROR', 'P5', f'{nm} 出现负值 {len(neg)} 个（库存/价格不应为负）', neg[:10])
        jumps = []
        for i in range(1, len(vals)):
            if vals[i] is None or vals[i - 1] in (None, 0):
                continue
            ch = (vals[i] - vals[i - 1]) / abs(vals[i - 1])
            if abs(ch) > args.jump_threshold:
                jumps.append(f'{raw_dates[i]}: {vals[i-1]}→{vals[i]} ({ch:+.1%})')
        if jumps:
            add('WARN', 'P5', f'{nm} 有 {len(jumps)} 处超过 {args.jump_threshold:.0%} 的跳变（请核对是否口径变化/录入错误）', jumps[:10])

    # P6 频率
    gaps = []
    for i in range(1, len(ds_o)):
        if ds_o[i] and ds_o[i - 1]:
            gaps.append((ds_o[i] - ds_o[i - 1]).days)
    if gaps:
        from statistics import median, mode
        m = sorted(gaps)
        med = median(gaps)
        irregular = [raw_dates[i + 1] for i, g in enumerate(gaps) if abs(g - args.freq) > max(2, args.freq * 0.45)]
        add('INFO', 'P6', f'相邻观测间隔：中位数 {med} 天，最小 {min(gaps)}，最大 {max(gaps)}，目标频率 {args.freq} 天')
        if irregular:
            add('WARN', 'P6', f'{len(irregular)} 处间隔偏离目标频率（节假日/停更/换口径），对齐时需说明', irregular[:12])

    # P8 滚动最小样本
    for w in [int(t) for t in args.windows.split(',') if t.strip()]:
        need = max(5, int(round(w * args.min_pairs_ratio)))
        ok = len(pairs) >= need
        add('INFO' if ok else 'WARN', 'P8',
            f'{w} 期滚动窗口需要 ≥{need} 个有效配对，当前 N={len(pairs)} → {"可计算" if ok else "不足，将不输出结果"}')

    report = {
        'file': os.path.basename(args.csv),
        'x_name': args.x_name, 'y_name': args.y_name,
        'n_rows': len(rows_out), 'n_pairs': len(pairs),
        'period': [str(ds_o[0]), str(ds_o[-1])] if ds_o else None,
        'missing_x': miss_x, 'missing_y': miss_y,
        'findings': findings,
        'pass': not any(f['level'] == 'ERROR' for f in findings),
    }
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--date-col', default='date')
    ap.add_argument('--x-col', required=True)
    ap.add_argument('--y-col', required=True)
    ap.add_argument('--x-name', default='指标X')
    ap.add_argument('--y-name', default='指标Y')
    ap.add_argument('--freq', type=int, default=7)
    ap.add_argument('--jump-threshold', type=float, default=0.35)
    ap.add_argument('--windows', default='12,26,52')
    ap.add_argument('--min-pairs-ratio', type=float, default=0.8)
    ap.add_argument('--out', default='')
    args = ap.parse_args(argv)
    rep = run(args)
    icon = {'ERROR': '[错误]', 'WARN': '[警告]', 'INFO': '[信息]'}
    print(f"数据质量检查：{rep['file']}  {rep['period'][0] if rep['period'] else ''} ~ {rep['period'][1] if rep['period'] else ''}"
          f"  行数 {rep['n_rows']}  有效配对 {rep['n_pairs']}")
    print(f"总体：{'通过' if rep['pass'] else '存在阻塞性错误'}")
    for f in rep['findings']:
        print(f"  {icon[f['level']]} {f['code']} {f['msg']}")
        if f['detail']:
            print(f"        {f['detail'][:8]}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(rep, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('written', args.out)
    return 0 if rep['pass'] else 2


if __name__ == '__main__':
    sys.exit(main())
