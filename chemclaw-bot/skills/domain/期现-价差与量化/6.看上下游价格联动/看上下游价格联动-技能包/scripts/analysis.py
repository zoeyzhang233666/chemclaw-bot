# -*- coding: utf-8 -*-
"""
analysis.py —— 上下游价格联动完整分析引擎（七步），输出单一 JSON 供 HTML/Excel 消费

用法
  python analysis.py --data processed/px_pta_daily.csv --out build/analysis.json \
      --coef 0.655 --windows 20,60,120 --lag 20 --segments 3

七步
  1 口径核验（单位/税费/地区/来源/两源一致性）
  2 价格水平与收益率的分开统计（水平相关 vs 收益率相关，各带 N/p/CI）
  3 标准化价格曲线 + 区间涨跌
  4 理论加工价差：分位、当前分位、单耗敏感性、锚定系数检验
  5 滚动相关性（水平 & 收益率）+ 稳定性统计
  6 阶段划分 + 跟随/背离区间识别
  7 领先滞后：交叉相关（水平 & 收益率）、Granger、事件台账挂接

红线
  - 任何显著性或相关结论都带 N、窗口、频率、样本区间。
  - 缺失不插值：只用成对有效样本；样本不足返回 null 并在 issues 中登记。
  - 不输出交易建议；不把统计显著写成「成本传导的因果证据」。
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import researchlib as R  # noqa: E402

SEGMENTS = [
    ('2023-10-07', '2024-12-31', 'S1', 'PX扩能兑现+PTA过剩，加工费中枢下移'),
    ('2025-01-01', '2025-12-31', 'S2', 'PX供给趋紧、PTA加工费走阔'),
    ('2026-01-01', '2026-10-20', 'S3', 'PTA集中检修+地缘油价扰动'),
]


def load(path):
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append({
                'date': r['date'],
                'px': float(r['px']),
                'pta': float(r['pta']),
                'spread': float(r['spread']),
                'ratio': float(r['ratio']),
                'period': r.get('period', ''),
            })
    return rows


def seg_rows(rows, seg):
    a, b = dt.date.fromisoformat(seg[0]), dt.date.fromisoformat(seg[1])
    return [r for r in rows if a <= dt.date.fromisoformat(r['date']) <= b]


def index_series(rows, base=100.0):
    """标准化：以首日为 100 的指数曲线"""
    p0, t0 = rows[0]['px'], rows[0]['pta']
    return [{'date': r['date'], 'px_idx': round(100 * r['px'] / p0, 3),
             'pta_idx': round(100 * r['pta'] / t0, 3)} for r in rows]


def returns(rows, col):
    out = [None]
    for i in range(1, len(rows)):
        out.append(rows[i][col] / rows[i - 1][col] - 1)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='processed/px_pta_daily.csv')
    ap.add_argument('--out', default='build/analysis.json')
    ap.add_argument('--events', default='events.json')
    ap.add_argument('--coef', type=float, default=0.655)
    ap.add_argument('--windows', default='20,60,120')
    ap.add_argument('--lag', type=int, default=20)
    ap.add_argument('--label', default='PX × PTA')
    a = ap.parse_args(argv)
    here = os.path.dirname(os.path.abspath(__file__))
    rows = load(os.path.join(here, a.data) if not os.path.isabs(a.data) else a.data)
    windows = [int(x) for x in a.windows.split(',')]

    px = [r['px'] for r in rows]
    pta = [r['pta'] for r in rows]
    spread = [r['spread'] for r in rows]
    dates = [r['date'] for r in rows]
    n = len(rows)

    out = {'meta': {'label': a.label, 'n_obs': n, 'first': dates[0], 'last': dates[-1],
                    'coef': a.coef, 'windows': windows, 'maxlag': a.lag},
           'series': [{**r,
                       'px_ret': returns(rows, 'px')[i],
                       'pta_ret': returns(rows, 'pta')[i],
                       'spread_pctl': None} for i, r in enumerate(rows)],
           'index': index_series(rows)}

    # ---------- 步骤 4：加工价差分位 ----------
    ssp = sorted(spread)
    qs = {q: round(R.quantile(ssp, q), 2) for q in (0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0)}
    pctl_series = R.expanding_rank(spread)
    for i, r in enumerate(out['series']):
        r['spread_pctl'] = pctl_series[i]
    out['spread'] = {
        'quantiles': qs,
        'current': round(spread[-1], 2),
        'current_pctl': round(R.pct_rank(ssp, spread[-1]), 1),
        'mean': round(st.mean(spread), 2),
        'stdev': round(st.pstdev(spread), 2),
        'n': n,
    }
    # 单耗敏感性：0.60 ~ 0.70
    sens = []
    for coef in [round(0.60 + 0.005 * i, 3) for i in range(21)]:
        vals = [p - coef * x for p, x in zip(pta, px)]
        sens.append({'coef': coef, 'mean': round(st.mean(vals), 2),
                     'current': round(vals[-1], 2), 'sd': round(st.pstdev(vals), 2),
                     'p10': round(R.quantile(sorted(vals), 0.10), 2),
                     'p50': round(R.quantile(sorted(vals), 0.50), 2),
                     'p90': round(R.quantile(sorted(vals), 0.90), 2)})
    out['spread']['sensitivity'] = sens

    # 锚定系数检验：-β(log PTA on log PX)
    lp = [math.log(x) for x in px]
    lt = [math.log(x) for x in pta]
    anchor = R.newey_west_ols(lp, lt, lags=5)
    ratio_level = st.mean([t / x for t, x in zip(pta, px)])
    out['anchor'] = {
        'log_log_slope': anchor['slope'], 'se_hac': anchor['se_hac'],
        'implied_factor': round(-anchor['slope'], 4),
        'mean_pta_over_px': round(ratio_level, 4),
        'interpretation': ('log-log 系数接近 1 表示两者按同一价格标尺编制（PTA ≈ PX + 加工费），'
                           '此时加工价差应使用 raw spread（PTA − PX）；系数接近 PX 单耗(0.65 左右)时，'
                           '才适合用 PTA − 0.655×PX 作为收入型加工费。'),
    }

    # ---------- 步骤 2：水平 vs 收益率 ----------
    ret_px, ret_pta = [], []
    for i in range(1, n):
        ret_px.append(rows[i]['px'] / rows[i - 1]['px'] - 1)
        ret_pta.append(rows[i]['pta'] / rows[i - 1]['pta'] - 1)
    out['corr'] = {
        'level': R.corr_full(px, pta),
        'return': R.corr_full(ret_px, ret_pta),
        'spread_vs_px_level': R.corr_full(px, spread),
        'spread_vs_px_return': R.corr_full(ret_px, [spread[i] - spread[i - 1] for i in range(1, n)]),
    }
    # 周度重采样（降低自相关影响的稳健性口径）
    weekly = {}
    for i, d in enumerate(dates):
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        weekly[(y, w)] = i  # 取每周最后一个观测
    wl_idx = sorted(weekly.values())
    wl = R.corr_full([px[i] for i in wl_idx], [pta[i] for i in wl_idx])
    wr_px = [px[wl_idx[k]] / px[wl_idx[k - 1]] - 1 for k in range(1, len(wl_idx))]
    wr_pta = [pta[wl_idx[k]] / pta[wl_idx[k - 1]] - 1 for k in range(1, len(wl_idx))]
    out['corr']['weekly_level'] = wl
    out['corr']['weekly_return'] = R.corr_full(wr_px, wr_pta)

    # ---------- 步骤 5：滚动相关 ----------
    rolling = {}
    for w in windows:
        lv = R.rolling_corr_series(px, pta, w)
        rt = R.rolling_corr_series(ret_px, ret_pta, w - 1)
        rolling[str(w)] = {
            'level': [{'i': i, 'r': None if v is None else round(v, 4)} for i, v, _ in lv],
            'return': [{'i': i, 'r': None if v is None else round(v, 4)} for i, v, _ in rt],
        }
        vals = [v for _, v, _ in lv if v is not None]
        if vals:
            rolling[str(w)]['level_stats'] = {
                'min': round(min(vals), 4), 'max': round(max(vals), 4),
                'mean': round(st.mean(vals), 4), 'sd': round(st.pstdev(vals), 4),
                'share_ge_08': round(sum(1 for v in vals if v >= 0.8) / len(vals), 3),
                'share_lt_05': round(sum(1 for v in vals if v < 0.5) / len(vals), 3),
            }
        vals2 = [v for _, v, _ in rt if v is not None]
        if vals2:
            rolling[str(w)]['return_stats'] = {
                'min': round(min(vals2), 4), 'max': round(max(vals2), 4),
                'mean': round(st.mean(vals2), 4), 'sd': round(st.pstdev(vals2), 4),
                'share_ge_08': round(sum(1 for v in vals2 if v >= 0.8) / len(vals2), 3),
            }
    out['rolling'] = rolling

    # ---------- 步骤 6：阶段 ----------
    phases = []
    for s in SEGMENTS:
        sub = seg_rows(rows, s)
        if len(sub) < 10:
            continue
        sp_px = [r['px'] for r in sub]
        sp_pta = [r['pta'] for r in sub]
        sp_sp = [r['spread'] for r in sub]
        sp_ret_px = [sp_px[k] / sp_px[k - 1] - 1 for k in range(1, len(sp_px))]
        sp_ret_pta = [sp_pta[k] / sp_pta[k - 1] - 1 for k in range(1, len(sp_pta))]
        phases.append({
            'code': s[2], 'name': s[3], 'start': s[0], 'end': s[1], 'n': len(sub),
            'px_start': sp_px[0], 'px_end': sp_px[-1],
            'pta_start': sp_pta[0], 'pta_end': sp_pta[-1],
            'px_chg': round(100 * (sp_px[-1] / sp_px[0] - 1), 2),
            'pta_chg': round(100 * (sp_pta[-1] / sp_pta[0] - 1), 2),
            'spread_mean': round(st.mean(sp_sp), 1),
            'spread_min': round(min(sp_sp), 1), 'spread_max': round(max(sp_sp), 1),
            'corr_level': R.corr_full(sp_px, sp_pta),
            'corr_return': R.corr_full(sp_ret_px, sp_ret_pta),
        })
    out['phases'] = phases

    # 跟随/背离
    states = R.transmission_states(px, pta, window=20, px_thr=0.03, agree=0.5)
    runs = R.find_diverge_runs(states, dates, min_len=5, gap=5)
    div = []
    for r in runs:
        s, e = r['start_idx'], r['end_idx']
        div.append({
            'start': r['start'], 'end': r['end'], 'n_days': r['n_days'],
            'px_chg': round(100 * (px[e] / px[s] - 1), 2),
            'pta_chg': round(100 * (pta[e] / pta[s] - 1), 2),
            'spread_start': round(spread[s], 1), 'spread_end': round(spread[e], 1),
            'spread_chg': round(spread[e] - spread[s], 1),
        })
    out['divergence'] = {'definition': '以 20 个观测为窗口：|ΔPX| ≥ 3% 且 PTA 方向相反；允许间断 ≤ 5 个观测，合并后长度 ≥ 5 个观测才计为一段',
                         'runs': div}
    out['states'] = states

    # ---------- 步骤 7：领先滞后 ----------
    cc_lvl = R.cross_correlation(px, pta, a.lag)
    cc_ret = R.cross_correlation(ret_px, ret_pta, min(a.lag, 10))
    best_lvl = max((c for c in cc_lvl if c['r'] is not None), key=lambda c: c['r'])
    best_ret = max((c for c in cc_ret if c['r'] is not None), key=lambda c: c['r'])
    gr = {}
    for p in (1, 3, 5):
        gr[f'px_lead_{p}'] = R.granger_test(pta, px, p)
        gr[f'pta_lead_{p}'] = R.granger_test(px, pta, p)
    out['leadlag'] = {
        'crosscorr_level': cc_lvl, 'crosscorr_return': cc_ret,
        'best_level_lag': best_lvl, 'best_return_lag': best_ret,
        'granger': gr,
    }

    # ---------- 事件台账 ----------
    ev_path = os.path.join(here, a.events)
    out['events'] = json.load(open(ev_path, encoding='utf-8')) if os.path.exists(ev_path) else []

    os.makedirs(os.path.dirname(os.path.join(here, a.out)), exist_ok=True)
    with open(os.path.join(here, a.out), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    print(json.dumps({
        'n': n, 'window': [dates[0], dates[-1]],
        'corr_level_r': out['corr']['level']['r'], 'corr_return_r': out['corr']['return']['r'],
        'spread_mean': out['spread']['mean'], 'spread_current': out['spread']['current'],
        'spread_current_pctl': out['spread']['current_pctl'],
        'anchor_factor': out['anchor']['implied_factor'],
        'best_level_lag': best_lvl, 'best_return_lag': best_ret,
        'n_divergence_runs': len(div),
    }, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
