# -*- coding: utf-8 -*-
"""analyze.py —— 读取 project.json，产出完整的分析结果 analysis.json

用法：
    python scripts/analyze.py <project.json> [--out-dir out] [--breakpoints 2025-10-01,2026-01-01,...]
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cost_engine as ce


def build_report(project, breakpoints=None, rolling_w=20, z_thr=1.5, max_lag=20,
                 real_spread=None, calib=None):
    res = ce.run_extended(project, breakpoints=breakpoints, rolling_w=rolling_w,
                          z_thr=z_thr, max_lag=max_lag, real_spread=real_spread)
    D = res['dates']
    m = dict(zip(D, res['spread']))

    # ---- 锚点校验：用真实产业口径（若给了 reported 值）对账
    calib_rows = []
    for a in (calib or project.get('calibration_anchors') or []):
        val, n = _window_avg(D, res['spread'], a['date'])
        row = dict(a)
        row['model'] = val
        row['n_days'] = n
        row['gap'] = None if (val is None or a.get('reported') is None) else val - a['reported']
        if a.get('reported') and val is not None:
            row['gap_pct'] = (val / a['reported'] - 1) * 100
        calib_rows.append(row)

    # ---- 描述性统计
    valid = [x for x in res['spread'] if x is not None]
    up0, up1 = res['up'][0], res['up'][-1]
    dn0, dn1 = res['down'][0], res['down'][-1]
    summary = {
        'window': [D[0], D[-1]], 'n_obs': len(D),
        'up': {'name': project['upstream']['name'], 'start': up0, 'end': up1,
               'chg': up1 - up0, 'chg_pct': ce.pct(up1, up0),
               'min': min(x for x in res['up'] if x is not None),
               'max': max(x for x in res['up'] if x is not None)},
        'down': {'name': project['downstream']['name'], 'start': dn0, 'end': dn1,
                 'chg': dn1 - dn0, 'chg_pct': ce.pct(dn1, dn0),
                 'min': min(x for x in res['down'] if x is not None),
                 'max': max(x for x in res['down'] if x is not None)},
        'spread': res['spread_stats'],
        'cost_share_pct': res['cost_share_latest'],
        'filled': res['filled'],
    }

    # ---- 月度汇总（供图表与 Excel）
    months = sorted({d[:7] for d in D})
    monthly = []
    for mo in months:
        idx = [i for i, d in enumerate(D) if d[:7] == mo]
        monthly.append({
            'month': mo,
            'up_avg': _avg([res['up'][i] for i in idx]),
            'down_avg': _avg([res['down'][i] for i in idx]),
            'cost_avg': _avg([res['material_cost'][i] for i in idx]),
            'spread_avg': _avg([res['spread'][i] for i in idx]),
            'spread_min': _min([res['spread'][i] for i in idx]),
            'spread_max': _max([res['spread'][i] for i in idx]),
            'n': len(idx),
        })

    # ---- 年度分段统计（用于"和去年比"的说法）
    yearly = []
    for yr in sorted({d[:4] for d in D}):
        idx = [i for i, d in enumerate(D) if d[:4] == yr]
        yearly.append({'year': yr, 'n': len(idx),
                       'spread_avg': _avg([res['spread'][i] for i in idx]),
                       'up_avg': _avg([res['up'][i] for i in idx]),
                       'down_avg': _avg([res['down'][i] for i in idx])})

    # ---- 逐日明细（Excel 底表 & HTML 抽屉）
    daily = []
    for i, d0 in enumerate(D):
        det = res['detail'][i] or {}
        daily.append({
            'date': d0, 'up': res['up'][i], 'down': res['down'][i],
            'cost': res['material_cost'][i], 'spread': res['spread'][i],
            'spread_low_unit': res['spread_low_unit'][i],
            'spread_high_unit': res['spread_high_unit'][i],
            'z': res['z'][i],
            'px_cost': (det.get('PX') or {}).get('cost'),
        })

    return {
        'meta': {
            'chain': project.get('product_chain'),
            'window': project.get('window'),
            'upstream': project['upstream'],
            'downstream': project['downstream'],
            'process': project.get('process'),
            'materials': project['materials'],
            'optional_materials': project.get('optional_materials', []),
            'params': project.get('params', {}),
        },
        'summary': summary, 'monthly': monthly, 'yearly': yearly, 'daily': daily,
        'stages': res['stages'], 'divergences': res['divergences'],
        'stats': res['stats'], 'outliers': res['outliers'],
        'sensitivity': res['sensitivity'], 'calibration': calib_rows,
        'steps': _step_metrics(res, D),
    }


def _step_metrics(res, dates):
    """台阶/变动天数统计——用于揭示"上游评估价连续多日不变"这一失真来源。"""
    up, down = res['up'], res['down']
    out = {'n': len(dates)}
    for key, seq in (('up', up), ('down', down)):
        chg = 0
        for i in range(1, len(seq)):
            a, b = seq[i - 1], seq[i]
            if a is not None and b is not None and abs(b - a) > 1e-9:
                chg += 1
        out['%s_change_days' % key] = chg
        out['%s_change_ratio' % key] = (chg / (len(seq) - 1)) if len(seq) > 1 else 0.0
    # 上游连续不变区间（>=4 天）
    runs, start, val = [], None, None
    for i, v in enumerate(up):
        if val is None or (v is not None and abs(v - val) > 1e-9):
            if start is not None and i - start >= 4:
                runs.append({'start': dates[start], 'end': dates[i - 1],
                             'days': i - start, 'value': val})
            start, val = i, v
    if start is not None and len(up) - start >= 4:
        runs.append({'start': dates[start], 'end': dates[-1],
                     'days': len(up) - start, 'value': val})
    out['up_flat_runs'] = runs
    return out


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _min(xs):
    xs = [x for x in xs if x is not None]
    return min(xs) if xs else None


def _max(xs):
    xs = [x for x in xs if x is not None]
    return max(xs) if xs else None


def _compact(s):
    """把任意写法的日期压成 YYYYMMDD，与序列键统一。"""
    return str(s).strip().replace('-', '').replace('/', '')


def _window_avg(dates, vals, anchor):
    """anchor 可以是 'YYYY-MM'、'YYYY-MM-DD~YYYY-MM-DD' 或 'YYYY-MM-DD'。"""
    a = _compact(anchor)
    if '~' in a:
        s, e = [_compact(x) for x in a.split('~')]
        sel = [v for dt_, v in zip(dates, vals) if s <= _compact(dt_) <= e]
    elif len(a) == 6:
        sel = [v for dt_, v in zip(dates, vals) if _compact(dt_).startswith(a)]
    else:
        sel = [v for dt_, v in zip(dates, vals) if _compact(dt_) == a]
    sel = [x for x in sel if x is not None]
    return (sum(sel) / len(sel) if sel else None), len(sel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--out-dir', default='build')
    ap.add_argument('--breakpoints', default='')
    ap.add_argument('--rolling', type=int, default=20)
    ap.add_argument('--z', type=float, default=1.5)
    args = ap.parse_args()
    proj = json.load(open(args.project, encoding='utf-8'))
    bp = [x.strip() for x in args.breakpoints.split(',') if x.strip()] or None
    if not bp:
        # 回退到 project.json 里声明的断点，保证一条命令即可复现
        raw = (proj.get('params') or {}).get('breakpoints') or proj.get('breakpoints')
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.split(',') if x.strip()]
        if raw:
            bp = list(raw)
    if not bp:
        print('提示：未提供 --breakpoints，project.json 也未声明，将只做全期与年度分解')
    out = build_report(proj, breakpoints=bp, rolling_w=args.rolling, z_thr=args.z)
    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, 'analysis.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    s = out['summary']
    print('观测 %d 个交易日：%s → %s' % (s['n_obs'], s['window'][0], s['window'][1]))
    print('上游 %s %.2f → %.2f（%+.2f%%）' % (s['up']['name'], s['up']['start'], s['up']['end'], s['up']['chg_pct']))
    print('下游 %s %.2f → %.2f（%+.2f%%）' % (s['down']['name'], s['down']['start'], s['down']['end'], s['down']['chg_pct']))
    sp = s['spread']
    print('加工价差 均值 %.1f 中位 %.1f 区间 [%.1f, %.1f] 最新 %.1f（分位 %.1f%%）'
          % (sp['mean'], sp['median'], sp['min'], sp['max'], sp['latest'], sp['latest_rank']))
    print('原料成本占下游价格 %.1f%%' % s['cost_share_pct'])
    for c in out['calibration']:
        print('锚点 %-24s 模型 %s vs 报告 %s 差 %s'
              % (c['date'],
                 '-' if c['model'] is None else '%.1f' % c['model'],
                 c.get('reported'),
                 '-' if c['gap'] is None else '%.1f' % c['gap']))
    print('背离区间 %d 段；待核异常 %d 个' % (len(out['divergences']), len(out['outliers'])))
    print('已写出', path)


if __name__ == '__main__':
    main()
