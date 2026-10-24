# -*- coding: utf-8 -*-
"""供给影响量计算引擎
=====================
把“装置产能”换算为“实际减产/增产吨数”，而不是直接拿设计产能当减产量。

核心公式（全部为可审计的显式参数）：

1) 日基准产能（吨/日）
   D = capacity_wt * 10000 / days_per_year

2) 停车类事件（检修/停车/故障）：
   影响天数 N = 事件在统计窗口内的停留天数（左闭右闭，含首尾）
   减产系数 k = 1 - 停车后实际负荷（停车时负荷=0 → k=1）
   理论影响产量 L = D * N * k * 披露产能口径修正

3) 降负荷类事件：
   L = D * N * (基准负荷 - 事件负荷)
   若来源只给“低负荷/开工不满”而不给数值，则用区间中值并给出上下界
   （low/high 两套参数各算一次，作为敏感性区间），并显式标记 assumed=True。

4) 复产类事件本身不产生减产量；复产的“可恢复供应”另计为
   P = D * N_recovered * 负荷 —— 但仅当存在此前已确认的停车段时才计，
   否则改为“状态确认”事件，影响量记 0（避免把正常运行当成增量）。

5) 新增产能（新投产/试车）：
   A = capacity_wt * 10000 / days_per_year * 爬坡负荷 * 窗口内运行天数
   —— 与检修损失分开列示，绝不相互抵销。

6) 窗口裁剪：事件若跨越统计窗口边界，只计算落在窗口内的天数。

所有函数返回 dict，包含公式字符串、参数与中间量，供 HTML/Excel 直接展示。
"""
from __future__ import annotations

import datetime as _dt
import os
import sys

DAYS_PER_YEAR = 365.0


def parse_date(s):
    if not s:
        return None
    return _dt.date.fromisoformat(str(s)[:10])


def clip_days(start, end, win_start, win_end):
    """返回落在 [win_start, win_end] 内的天数（含首尾）。若 end 为空，用 win_end。"""
    s = parse_date(start)
    e = parse_date(end) or win_end
    if s is None:
        return 0, None, None
    s2 = max(s, win_start)
    e2 = min(e, win_end)
    if e2 < s2:
        return 0, s2, e2
    return (e2 - s2).days + 1, s2, e2


def _num(v, default=None):
    """把 JSON 里可能是字符串的数值安全转成 float；失败返回 default。"""
    if v is None or v == '':
        return default
    if isinstance(v, bool):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def daily_capacity(capacity_wt, days_per_year=DAYS_PER_YEAR):
    return _num(capacity_wt, 0.0) * 10000.0 / days_per_year


def calc_stop(ev, win_start, win_end, assumed_load=None, downtime_load=None):
    """停车/检修/故障/降负荷类事件的影响量。

    参数语义（必须严格区分，这是本引擎最容易出错的地方）：
      load_assumption_path: 事件发生前/基准负荷（baseline_load），通常=1.0
      downtime_load       : 事件期间的实际负荷（0=全停；0.45=负荷降至45%）
    减产量系数 k = baseline_load - downtime_load

    assumed_load 参数为兼容旧调用：若显式传入，则视为 downtime_load。
    """
    cap = _num(ev.get('capacity_wt'), 0.0)
    if cap <= 0:
        return {'ok': False, 'reason': '缺少产能，不计算', 'formula': None,
                'loss_t': None, 'days': None}

    baseline = _num(ev.get('baseline_load'), 1.0)
    if downtime_load is None:
        # 优先读显式字段 downtime_load；否则回退到 load_assumption
        if 'downtime_load' in ev:
            downtime_load = _num(ev.get('downtime_load'))
        else:
            downtime_load = _num(ev.get('load_assumption'), 1.0)
            # 兼容旧数据：若 load_assumption==1.0 但事件类型是停车类，说明是"基准负荷"
            if downtime_load == 1.0 and ev.get('load_assumption_semantics') == 'baseline':
                downtime_load = 0.0
    if assumed_load is not None:
        downtime_load = _num(assumed_load)

    if downtime_load is None:
        return {'ok': False, 'reason': '缺少事件期负荷参数，不计算',
                'formula': None, 'loss_t': None, 'days': None}

    n, s2, e2 = clip_days(ev.get('start_date'), ev.get('end_date'), win_start, win_end)
    d = daily_capacity(cap)
    k = max(0.0, baseline - float(downtime_load))
    loss = d * n * k
    return {
        'ok': True,
        'formula': (f"L = 产能/365 × 窗口内天数 × (基准负荷-事件期负荷) = "
                    f"{cap:.0f}×10000/365 × {n} × ({baseline:.2f}-{float(downtime_load):.2f})"),
        'capacity_wt': cap,
        'daily_t': round(d, 1),
        'days': n,
        'clip_start': s2.isoformat() if s2 else None,
        'clip_end': e2.isoformat() if e2 else None,
        'baseline_load': baseline,
        'downtime_load': float(downtime_load),
        'reduction_coef': round(k, 4),
        'loss_t': round(loss, 1),
        'loss_upper_t': round(d * n * baseline, 1),
        'assumed': bool(ev.get('load_assumed', False)),
    }


def calc_ramp(ev, win_start, win_end, ramp_load):
    """新增产能贡献量（新投产/试车）。"""
    cap = _num(ev.get('capacity_wt'), 0.0)
    ramp_load = _num(ramp_load)
    if cap <= 0 or ramp_load is None:
        return {'ok': False, 'reason': '缺少爬坡负荷假设，不计算', 'days': None}
    n, s2, e2 = clip_days(ev.get('start_date'), ev.get('end_date') or win_end, win_start, win_end)
    d = daily_capacity(cap)
    add = d * n * float(ramp_load)
    return {
        'ok': True,
        'formula': f"A = 产能/365 × 窗口内运行天数 × 爬坡负荷 = {cap}×10000/365 × {n} × {ramp_load:.2f}",
        'capacity_wt': cap,
        'daily_t': round(d, 1),
        'days': n,
        'ramp_load': ramp_load,
        'add_t': round(add, 1),
        'annual_t': cap * 10000,
        'annual_note': '达产后年化产能，非窗口内实际产量',
    }



def summarize(events, win_start, win_end, national_capacity_wt=None,
              weekly_output_t=None):
    """汇总。严格分三个口径，禁止混算：
      domestic : 国内装置 -> 计入国产供给影响
      overseas : 境外装置 -> 只影响进口/到港，不进入国产供给
      excluded : 传闻/待核/长期停车/无效产能
    """
    rows = []
    T = {'domestic_loss_t': 0.0, 'overseas_loss_t': 0.0, 'unconfirmed_loss_t': 0.0,
         'new_capacity_add_t': 0.0, 'n_domestic_confirmed': 0, 'n_overseas': 0,
         'n_unconfirmed': 0, 'n_stock': 0}
    for ev in events:
        et = ev.get('event_type')
        overseas = ev.get('scope') == 'overseas'
        excluded = bool(ev.get('exclude_from_confirmed')) or ev.get('confidence') == 'rumor'
        stock = bool(ev.get('stock_stop'))
        row = {'event_id': ev.get('event_id'), 'unit_id': ev.get('unit_id'),
               'company': ev.get('company'), 'unit_name': ev.get('unit_name'),
               'province': ev.get('province'), 'region_code': ev.get('region_code'),
               'route': ev.get('route'), 'capacity_wt': ev.get('capacity_wt'),
               'event_type': et, 'start_date': ev.get('start_date'),
               'end_date': ev.get('end_date'), 'status_latest': ev.get('status_latest'),
               'status_note': ev.get('status_note'),
               'confidence': ev.get('confidence'), 'source_count': ev.get('source_count'),
               'sources': ev.get('sources', []),
               'scope': 'overseas' if overseas else 'domestic',
               'is_stock': stock, 'excluded': excluded}
        if et in ('计划检修', '实际停车', '意外故障', '降负荷'):
            r = calc_stop(ev, win_start, win_end)
            row.update(r)
            loss = r.get('loss_t') or 0.0
            if excluded:
                T['unconfirmed_loss_t'] += loss
                T['n_unconfirmed'] += 1
                row['bucket'] = 'unconfirmed'
            elif stock:
                T['n_stock'] += 1
                row['bucket'] = 'stock_stop'
            elif overseas:
                T['overseas_loss_t'] += loss
                T['n_overseas'] += 1
                row['bucket'] = 'overseas'
            else:
                T['domestic_loss_t'] += loss
                T['n_domestic_confirmed'] += 1
                row['bucket'] = 'domestic_confirmed'
        elif et in ('新投产', '试车'):
            r = calc_ramp(ev, win_start, win_end,
                          _num(ev.get('ramp_load') or ev.get('load_assumption')))
            row.update(r)
            if not excluded and not overseas and r.get('ok'):
                T['new_capacity_add_t'] += r.get('add_t') or 0.0
                row['bucket'] = 'new_capacity'
            else:
                row['bucket'] = 'overseas' if overseas else 'unconfirmed'
        else:
            row.update({'ok': False, 'loss_t': 0.0, 'days': None,
                        'reason': '复产事件：可恢复供应已在对应停车事件中体现，避免重复计算'})
            if overseas:
                T['n_overseas'] += 1
                row['bucket'] = 'overseas'
            elif excluded:
                T['n_unconfirmed'] += 1
                row['bucket'] = 'unconfirmed'
            else:
                row['bucket'] = 'status_only'
        rows.append(row)
    out = {'rows': rows, 'totals': T,
           'window': {'start': win_start.isoformat(), 'end': win_end.isoformat()}}
    if national_capacity_wt:
        annual = _num(national_capacity_wt, 0) * 10000.0
        win_days = (win_end - win_start).days + 1
        out['national_capacity_wt'] = national_capacity_wt
        out['window_days'] = win_days
        out['domestic_loss_wt'] = round(T['domestic_loss_t'] / 10000.0, 2)
        out['overseas_loss_wt'] = round(T['overseas_loss_t'] / 10000.0, 2)
        out['unconfirmed_loss_wt'] = round(T['unconfirmed_loss_t'] / 10000.0, 2)
        out['new_capacity_wt'] = round(T['new_capacity_add_t'] / 10000.0, 2)
        out['domestic_loss_pct_window_capacity'] = round(
            T['domestic_loss_t'] / (annual * win_days / 365.0) * 100, 2)
        out['domestic_loss_pct_annual'] = round(T['domestic_loss_t'] / annual * 100, 3)
    if weekly_output_t:
        out['weekly_output_t'] = weekly_output_t
        out['domestic_loss_weeks'] = round(T['domestic_loss_t'] / weekly_output_t, 2)
        out['overseas_loss_weeks'] = round(T['overseas_loss_t'] / weekly_output_t, 2)
    return out


if __name__ == '__main__':
    import json
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    case = os.environ.get('CASE_DIR') or os.path.join(os.path.dirname(root), 'case')
    meta = json.load(open(os.path.join(case, 'datum.json'), encoding='utf-8'))['meta']
    ev = json.load(open(os.path.join(case, 'status_events.json'), encoding='utf-8'))['events']
    ws, we = parse_date(meta['window_start']), parse_date(meta['window_end'])
    s = summarize(ev, ws, we, meta['national_capacity_wt'], meta['weekly_output_t'])
    print(json.dumps({k: v for k, v in s.items() if k != 'rows'}, ensure_ascii=False, indent=1))
    print()
    for r in sorted(s['rows'], key=lambda x: -(x.get('loss_t') or 0)):
        print('%-6s %-20s %-14s %-6s cap=%4s d=%s loss=%s'
              % (r['event_id'], r['bucket'], str(r['company'])[:12], r['event_type'],
                 r['capacity_wt'], r.get('days'), r.get('loss_t')))
