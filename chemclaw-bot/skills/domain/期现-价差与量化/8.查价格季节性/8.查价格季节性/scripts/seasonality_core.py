# -*- coding: utf-8 -*-
"""seasonality_core.py — 价格季节性通用计算引擎（品种/地区/合约无关）

设计目标
--------
把"多年价格对齐 → 同期统计 → 分位带 → 归一化 → 异常年检验 → 样本覆盖审计"固化成
一套可复用、可复算、不补造数据的算法。任何品种/地区/合约，只要给出"日期 + 价格"两列，
就能跑出季节性与覆盖报告。

硬约束（全部由断言强制执行）
--------------------------
1. **不补造**：缺失就缺失。不插值、不前值填充、不把缺口静默跳过。缺口集中记录在 coverage 里。
2. **不混口径**：所有价格必须来自同一 config 口径；口径降级必须在 config 里显式声明。
3. **保留真实轨迹**：每个年份保留原始曲线，不只给均值。
4. **概率语言**：分位给"经验分位 + 样本年数 n"，n 小就明说。
5. **只描述历史**：输出的是历史分布位置，不是预测（报告层强制写免责声明）。

核心口径
--------
对齐键（x 轴）
  * weekly  : ISO 周次(1..52/53)，周一为周首；周值 = 该周内最后一个有报价工作日的收盘价
  * monthly : 自然月 1..12；月值 = 该月最后一个有报价工作日的价格
  * 另给 period_mean / n_days（月内或周内均值和有效天数），供波动观察，不用于分位统计
窗口选择
  * window = 'calendar'   : 第 1 周 → 第 52 周（ISO 周 53 折叠进 52 周）
  * window = 'quarterly'  : 第 1 周 → 第 52 周，但只到最后一个完整季度末（默认 52 = Q4）
归一化
  * 基准 = 每年**该窗口内第一个有效观测**（不是 1 月 1 日的插值）
  * norm_i = P_i / P_base − 1（返回式归一化）
分位
  * 经验分位，线性插值（等价 numpy 'linear' / Excel PERCENTILE.INC / R type 7）
异常年
  * 三道互相独立的检验：逐年均值 z 分数、唯一极值年、单年对均值的杠杆影响
样本门槛
  * 任一 x 位置有效年数 < min_years_for_stats(默认3) → 标记样本不足，不参与形态判断
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import date

import numpy as np

PCTS = [10, 25, 50, 75, 90]
MIN_YEARS_DEFAULT = 3
MAD_K = 1.4826          # MAD → 正态一致的标准差估计


# ----------------------------------------------------------------------------- helpers
def parse_date(s):
    s = str(s).strip().replace('/', '-')
    y, m, d = s.split(' ')[0].split('-')[:3]
    return date(int(y), int(m), int(d))


def pctile(vals, q):
    """线性插值经验分位，与 numpy.percentile(method='linear') 一致。"""
    v = [float(x) for x in vals if x is not None]
    if not v:
        return None
    return float(np.percentile(np.asarray(v), q, method='linear'))


def norm_iso_week(iso_year, iso_week):
    """把 ISO 周 53 折叠到 52，使各年份可比较（ISO 53 周仅出现在 1 月 1 日为周四的年份）。"""
    return 52 if iso_week >= 53 else iso_week


def _fmt(q):
    return 'p%d' % q


# ----------------------------------------------------------------------------- ingest
def load_daily(rows):
    """rows: iterable of dict(date=..., price=...) 或 (date, price) 元组。返回排序后的 dict 列表。"""
    out = []
    for r in rows:
        if isinstance(r, dict):
            d, p = r.get('date'), r.get('price')
        else:
            d, p = r[0], r[1]
        if p is None or str(p).strip() == '':
            continue
        out.append({'date': parse_date(d), 'price': float(p)})
    out.sort(key=lambda r: r['date'])
    # 同一天重复报价：保留第一条并记录
    dedup, dups = [], []
    for r in out:
        if dedup and dedup[-1]['date'] == r['date']:
            dups.append(r['date'].isoformat())
            if abs(dedup[-1]['price'] - r['price']) > 1e-9:
                dups[-1] += ' (value conflict)'
            continue
        dedup.append(r)
    return dedup, dups


def build_week_index(daily, quarter_end_week=52):
    """工作日级映射：date -> {iso_year, iso_week_norm, week_id, key}"""
    idx = []
    for r in daily:
        y, w, _ = r['date'].isocalendar()
        wn = norm_iso_week(y, w)
        if quarter_end_week < 52 and wn > quarter_end_week:
            continue                                  # 窗口外
        idx.append(dict(r, iso_year=y, iso_week=w, week=wn))
    return idx


# ----------------------------------------------------------------------------- align
def align(daily, freq, window_weeks=52, start_week=1, fold_week53=True):
    """把日度序列对齐成 (年份 × 位置) 面板。

    返回 OrderedDict{year: OrderedDict{week_or_month: {
        value, period_mean, period_low, period_high, n_days, first_date, last_date,
        label, full (该位置是否有完整覆盖, 仅用于缺口提示)
    }}}
    """
    years = OrderedDict()
    if freq == 'weekly':
        for r in daily:
            y, w, _ = r['date'].isocalendar()
            wn = 52 if (fold_week53 and w >= 53) else w
            if wn < start_week or wn > window_weeks:
                continue
            slot = years.setdefault(y, OrderedDict()).setdefault(wn, dict(
                value=None, period_mean=None, period_sum=0.0, n_days=0, period_low=None,
                period_high=None, first_date=None, last_date=None, label='W%02d' % wn))
            slot['period_sum'] += r['price']
            slot['n_days'] += 1
            slot['period_low'] = r['price'] if slot['period_low'] is None else min(slot['period_low'], r['price'])
            slot['period_high'] = r['price'] if slot['period_high'] is None else max(slot['period_high'], r['price'])
            slot['value'] = r['price']                     # 每周最后一个有报价日
            slot['last_date'] = r['date'].isoformat()
            if slot['first_date'] is None:
                slot['first_date'] = r['date'].isoformat()
    elif freq == 'monthly':
        for r in daily:
            m = r['date'].month
            slot = years.setdefault(r['date'].year, OrderedDict()).setdefault(m, dict(
                value=None, period_mean=None, period_sum=0.0, n_days=0, period_low=None,
                period_high=None, first_date=None, last_date=None, label='%02d月' % m))
            slot['period_sum'] += r['price']
            slot['n_days'] += 1
            slot['period_low'] = r['price'] if slot['period_low'] is None else min(slot['period_low'], r['price'])
            slot['period_high'] = r['price'] if slot['period_high'] is None else max(slot['period_high'], r['price'])
            slot['value'] = r['price']
            slot['last_date'] = r['date'].isoformat()
            if slot['first_date'] is None:
                slot['first_date'] = r['date'].isoformat()
    else:
        raise ValueError('freq must be weekly|monthly')
    for y in years:
        for k, s in years[y].items():
            s['period_mean'] = round(s.pop('period_sum') / s['n_days'], 4) if s['n_days'] else None
            s['period_low'] = round(s['period_low'], 4) if s['period_low'] is not None else None
            s['period_high'] = round(s['period_high'], 4) if s['period_high'] is not None else None
            s['value'] = round(s['value'], 4)
    return years


def positions(freq, window_weeks=52, start_week=1):
    if freq == 'weekly':
        return list(range(start_week, window_weeks + 1))
    return list(range(1, 13))


# ----------------------------------------------------------------------------- normalize
def normalize(years, freq):
    """每年以该窗口内第一个有效观测为 100 基准。返回 {year: {pos: rebased_value}} 与基准表。"""
    reb, base = OrderedDict(), OrderedDict()
    for y, slots in years.items():
        firstp = None
        for k in sorted(slots):
            if slots[k]['value'] is not None:
                firstp = (k, slots[k]['value'], slots[k]['first_date'])
                break
        base[y] = None if firstp is None else dict(pos=firstp[0], price=firstp[1],
                                                   date=firstp[2])
        reb[y] = OrderedDict()
        for k, s in slots.items():
            reb[y][k] = (None if (s['value'] is None or not firstp or firstp[1] == 0)
                         else round(s['value'] / firstp[1] * 100.0, 4))
    return reb, base


# ----------------------------------------------------------------------------- stats
def stats_by_position(years, freq, window_weeks=52, start_week=1,
                      min_years=MIN_YEARS_DEFAULT):
    """对每个 x 位置做跨年同期统计（绝对价格）。返回两组结果：

    rows[]  : 每个 (position, year) 的原始观测 —— 保留真实轨迹
    stats[] : 每个 position 的 mean/median/std/min/max/p10..p90/n/years/years_missing
    """
    pos = positions(freq, window_weeks, start_week)
    rows = []
    for (pos_i, y) in [(p, y) for p in pos for y in sorted(years)]:
        s = years.get(y, {}).get(pos_i)
        if s is None or s['value'] is None:
            rows.append(dict(position=pos_i, year=y, value=None, n_days=0, period_mean=None,
                             last_date=None, status='missing'))
        else:
            rows.append(dict(position=pos_i, year=y, value=s['value'], n_days=s['n_days'],
                             period_mean=s['period_mean'], last_date=s['last_date'],
                             status='ok'))
    stats = []
    for p in pos:
        vals = [(y, years[y][p]['value']) for y in sorted(years)
                if p in years[y] and years[y][p]['value'] is not None]
        v = [x[1] for x in vals]
        n = len(v)
        others = [years[o][p]['value'] for o in sorted(years)
                  if o not in [x[0] for x in vals] and p in years[o]
                  and years[o][p]['value'] is not None]
        st = dict(position=p, n_years=n, years=[x[0] for x in vals], other_values=others,
                  _values=[round(x, 4) for x in v],
                  mean=None, median=None, std=None, min=None, max=None,
                  n_sufficient=n >= min_years)
        for q in PCTS:
            st[_fmt(q)] = None
        if v:
            st['mean'] = round(float(np.mean(v)), 4)
            st['median'] = round(pctile(v, 50), 4)
            st['std'] = round(float(np.std(v, ddof=1)), 4) if n > 1 else None
            st['min'] = round(min(v), 4)
            st['max'] = round(max(v), 4)
            lo_, hi_ = min(v), max(v)
            for q in PCTS:
                qv = pctile(v, q)
                # 经验分位夹在观测区间内（采样误差在大离群差距下可能使窄侧插值越界）
                st[_fmt(q)] = round(min(max(qv, lo_), hi_), 4)
            if n >= min_years:
                st['iqr'] = round(st['p75'] - st['p25'], 4)
                st['spread_p10_p90'] = round(st['p90'] - st['p10'], 4)
                st['cv'] = round(st['std'] / st['mean'], 4) if st['mean'] else None
        st['years_missing'] = [y for y in sorted(years) if y not in st['years']]
        stats.append(st)
    return rows, stats


def position_of_current(years, current_year, freq, window_weeks=52, start_week=1,
                        min_years=MIN_YEARS_DEFAULT):
    """当前年相对于历史同期（剔除当前年自身）的位置。"""
    pos = positions(freq, window_weeks, start_week)
    hist_years = [y for y in sorted(years) if y != current_year]
    out = []
    for p in pos:
        cur = years.get(current_year, {}).get(p)
        cur_v = cur['value'] if cur else None
        hv = [(y, years[y][p]['value']) for y in hist_years
              if p in years[y] and years[y][p]['value'] is not None]
        rec = dict(position=p, current=cur_v, current_date=cur['last_date'] if cur else None,
                   n_hist=len(hv), hist_years=[y for y, _ in hv], hist_values=[v for _, v in hv],
                   rank=None, below_ratio=None, pctile_of_current=None, z=None,
                   hist_mean=None, hist_median=None)
        if cur_v is not None and hv:
            vals = [v for _, v in hv]
            rec['hist_mean'] = round(float(np.mean(vals)), 4)
            rec['hist_median'] = round(pctile(vals, 50), 4)
            rec['below_ratio'] = round(sum(1 for v in vals if v < cur_v) / len(vals), 4)
            rec['rank'] = 1 + sum(1 for v in vals if v > cur_v)      # 1 = 最高
            below = sum(1 for v in vals if v < cur_v)
            equal = sum(1 for v in vals if abs(v - cur_v) < 1e-9)
            rec['pctile_of_current'] = round((below + 0.5 * equal) / len(vals), 4)
            if len(vals) > 1:
                sd = float(np.std(vals, ddof=1))
                rec['z'] = round((cur_v - rec['hist_mean']) / sd, 4) if sd > 0 else None
        out.append(rec)
    return out


# ----------------------------------------------------------------------------- anomalies
def _position_values(years, pos):
    """{year: value} —— 仅保留该位置非空的值。"""
    out = OrderedDict()
    for yr in sorted(years):
        slot = years[yr].get(pos)
        if slot is not None and slot.get('value') is not None:
            out[yr] = float(slot['value'])
    return out


def _position_evidence(pvals, n_min, mad_k, tol_rel, coherent_cap):
    """对一个同期位置产出证据清单 [{'year':..,'kind':..,...}]。

    对每个非最高/非最低年：
      其余年 = 该位置其余年份的值；med_o/mad_o 为其余年的中位数与 MAD。
      kind = 'coherent-single-year'  其余年高度一致(mad/|med|<=cap) 且该年偏离 > tol_rel  → 决定性
      kind = 'robust-outlier'        |该年-其余年中位数|/(1.4826*mad_o) >= mad_k           → 稳健证据
      其余年彼此不一致时，只报稳健证据；两种情况都给出"剔除该年后的均值变化"。
    """
    if len(pvals) < n_min:
        return [], 0
    MAXZ = 1e6
    ordered = sorted(pvals.values())
    wins = {}

    def evidence_for(yr):
        val = pvals[yr]
        rest = [v for k, v in pvals.items() if k != yr]
        arr = np.asarray(rest, float)
        med = float(np.median(arr))
        mad = float(np.median(np.abs(arr - med)))
        if med == 0:
            return None
        dev = abs(val - med) / abs(med)
        shift = (float(np.mean(arr)) - float(np.mean(ordered))) / float(np.mean(ordered))
        # 稳健 z：其余年离散度为 0 时用封顶值 MAXZ，避免 inf 进入 JSON / 比较
        z = (val - med) / (MAD_K * mad if mad > 0 else (abs(med) / MAXZ))
        if mad > 0 and abs(z) >= mad_k:
            kind = 'robust-outlier'
        elif mad >= 0 and (mad / abs(med)) <= coherent_cap and dev > tol_rel:
            kind = 'coherent-single-year'
        else:
            kind = None
        if not kind:
            return None
        return dict(year=yr, kind=kind, value=round(val, 4), median_of_others=round(med, 4),
                    mean_of_others=round(float(np.mean(arr)), 4), mad_of_others=round(mad, 4),
                    dev_rel=round(dev, 4),
                    z_robust=(None if not np.isfinite(z) else round(z, 3)),
                    shift=round(shift, 4))

    for yr in list(pvals.keys()):
        e = evidence_for(yr)
        if e:
            wins[yr] = e

    y_hi = max(pvals, key=lambda k: pvals[k])
    y_lo = min(pvals, key=lambda k: pvals[k])
    tied_max = sum(1 for x in ordered if x == pvals[y_hi]) >= 2
    tied_min = sum(1 for x in ordered if x == pvals[y_lo]) >= 2

    def count_dev(yr):
        """该年偏离"其余年份中位数"的相对幅度（不去掉该年本身）。"""
        val = pvals[yr]
        peers = [v for k, v in pvals.items() if k != yr]
        peer = float(np.median(np.asarray(peers, float))) if peers else 0.0
        return abs(val - peer) / abs(peer) if peer else 0.0

    # 唯一离群年裁定：一组互为主要离群值的年份（含 mirror 情形）中，偏离幅度最大的年份
    # 保留为真离群，其余标记为 mirror-of-*，避免"正常年替异常年背锅"。
    if len(wins) > 1:
        top = max(wins, key=lambda k: count_dev(k))
        d_top = count_dev(top)
        if d_top >= 1.5 * tol_rel:
            for k in list(wins):
                if k != top and count_dev(k) < d_top * 0.5:
                    wins[k]['kind'] = 'mirror-of-' + wins[top]['kind']
                    wins[k]['mirror_of_year'] = top
                    wins[k]['dev_from_peers'] = round(count_dev(k), 4)
                    wins[k]['dev_of_top_year'] = round(d_top, 4)

    # 最高/最低年：若它并非"独占极值"（有并列或本档内明显偏离），也须参与检验
    def tier_dev(yr):
        return count_dev(yr)

    hi_minority = (y_hi in wins and not str(wins[y_hi]['kind']).startswith('mirror')) \
        or (tied_max and tier_dev(y_hi) > tol_rel)
    lo_minority = (y_lo in wins and not str(wins[y_lo]['kind']).startswith('mirror')) \
        or (tied_min and tier_dev(y_lo) > tol_rel)
    out = []
    for yr, e in wins.items():
        e['exclusive_extreme'] = (yr == y_hi and not hi_minority) or (yr == y_lo and not lo_minority)
        out.append(e)
    out.sort(key=lambda x: x['year'])
    return out, len(pvals)


def anomaly_scan(years, stats, freq, mad_k=3.0, p_pos=0.2, p_lev=0.1, p_ext=0.3,
                 n_min=4, tol_rel=0.02, coherent_cap=0.02):
    """异常年证据检验（品种无关）。

    两级证据
      决定性  coherent-single-year : 其余年份在该同期位置上高度一致，而该年显著偏离
      稳健    robust-outlier        : 去掉该年后，该年对剩余年份的 MAD 距 ≥ mad_k
    对"最高/最低年"不产生证据（n 小时它们天然是极值，自证没有信息量）。

    年度判级
      anomaly      : 决定性证据 ≥1 处，或稳健证据 ≥2 处，或稳健证据占比 ≥ p_pos
      relevant     : 稳健证据 1 处
      watch        : 年度整体水平偏移 ≥ p_lev，但同期无离群
      normal       : 未见异常
      insufficient : 无满足 n_min 年的同期位置

    不删除任何年份；每条证据都带"剔除后均值变化"，量化对统计均值的真实影响。
    """
    hist_years = sorted(years)
    row_map = OrderedDict((yr, dict(year=yr, n_pos=0, evidence=[], n_coherent=0, n_robust=0,
                                    max_abs_shift=0.0)) for yr in hist_years)
    pos_flagged = {}

    for st in stats:
        pos = st['position']
        pvals = _position_values(years, pos)
        evid, n_used = _position_evidence(pvals, n_min, mad_k, tol_rel, coherent_cap)
        if n_used:
            for yr in pvals:
                row_map[yr]['n_pos'] += 1
        for e in evid:
            e['position'] = pos
            e['label'] = st.get('label', str(pos))
            if e['exclusive_extreme']:
                continue                       # 独占极值年不产生异常证据（仍可被杠杆/整体偏移捕捉）
            e['counts'] = not str(e['kind']).startswith('mirror')
            row_map[e['year']]['evidence'].append(e)
            if not e['counts']:
                continue
            row_map[e['year']]['max_abs_shift'] = max(row_map[e['year']]['max_abs_shift'],
                                                      abs(e['shift']))
            if e['kind'] == 'coherent-single-year':
                row_map[e['year']]['n_coherent'] += 1
            else:
                row_map[e['year']]['n_robust'] += 1
            st.setdefault('outlier_years', []).append(dict(
                kind=e['kind'], exclusive_extreme=False,
                **{k: e[k] for k in ('year', 'value', 'median_of_others', 'mean_of_others',
                                     'mad_of_others', 'dev_rel', 'z_robust', 'shift')}))

    # 年度总杠杆：剔除该年后，跨位置同期均值的平均相对位移
    levmap = {}
    if len(hist_years) >= n_min:
        for yr in hist_years:
            diffs = []
            for st in stats:
                if st['mean'] is None or yr not in st['years'] or st['n_years'] < n_min:
                    continue
                rest = [years[o][st['position']]['value'] for o in st['years'] if o != yr
                        and years[o][st['position']]['value'] is not None]
                if rest:
                    diffs.append((float(np.mean(rest)) - st['mean']) / st['mean'])
            if diffs:
                levmap[yr] = dict(mean_abs_shift=round(float(np.mean(np.abs(diffs))), 4),
                                  mean_signed_shift=round(float(np.mean(diffs)), 4),
                                  n_pos=len(diffs))

    result = []
    for yr in hist_years:
        r = row_map[yr]
        lv = levmap.get(yr, {})
        if not r['n_pos']:
            result.append(dict(year=yr, n_pos=0, grade='insufficient', evidence=[], flags=[
                '样本不足（同期位置均 < %d 年，不判异常）' % n_min]))
            continue
        p_rob = r['n_robust'] / r['n_pos']
        flags = []
        if r['n_coherent'] >= 1 or r['n_robust'] >= 2 or (r['n_robust'] >= 1 and p_rob >= p_pos):
            grade = 'anomaly'
            if r['n_coherent']:
                flags.append('决定性：%d 个同期位置上其余年份一致而该年偏离超过 %.0f%%'
                             % (r['n_coherent'], tol_rel * 100))
            if r['n_robust']:
                flags.append('稳健：%d/%d 个同期位置 |稳健z| ≥ %.1f'
                             % (r['n_robust'], r['n_pos'], mad_k))
        elif r['n_robust'] == 1:
            grade = 'relevant'
            e0 = [e for e in r['evidence'] if e['kind'] == 'robust-outlier'][0]
            flags.append('单一位置稳健离群（%s，稳健z=%.1f）' % (e0['label'], e0['z_robust'] or 0))
        elif lv.get('mean_abs_shift') is not None and lv['mean_abs_shift'] >= p_lev:
            grade = 'watch'
            flags.append('年度整体水平偏移 %.1f%%，同期未见离群' % (lv['mean_abs_shift'] * 100))
        else:
            grade = 'normal'
        r.update(grade=grade, p_robust=round(p_rob, 4), flags=flags,
                 is_anomaly=(grade == 'anomaly'),
                 mean_abs_shift=lv.get('mean_abs_shift'),
                 mean_signed_shift=lv.get('mean_signed_shift'),
                 max_abs_shift=round(r['max_abs_shift'], 4))
        result.append(r)

    return dict(yearly=result,
                params=dict(mad_k=mad_k, p_pos=p_pos, p_lev=p_lev, p_ext=p_ext, n_min=n_min,
                            tol_rel=tol_rel, coherent_cap=coherent_cap),
                grade_note='anomaly=决定性或多位置稳健离群; relevant=单位置离群; '
                           'watch=整体水平偏移; normal=未见异常; 最高/最低年不产生证据')


# ----------------------------------------------------------------------------- stability
def stability(stats):
    """跨年稳定性。

    * mean_cv : 各同期位置跨年变异系数（std/mean）的均值 —— 衡量"同一位置逐年差多少"
    * seasonal_ss_share : 季节形态对**跨年方差**的解释力
          grand_mean  = 所有 (position, year) 观测的均值
          n_total     = 总观测数
          within_SS   = Σ_p Σ_i (v_pi − mean_p)²      （同一位置内部的跨年波动）
          total_SS    = Σ_p Σ_i (v_pi − grand_mean)²
          seasonal_ss_share = 1 − within_SS / total_SS
        即 R²：只看年份（不看季节位置）能解释多少方差。close to 0 表示季节形态弱、
        年份间水平漂移主导。必须用 SS 与总 SS 相减计算，不能直接对均值序列平方求和。
    """
    usable = [s for s in stats if s['n_sufficient']]
    cv_list = [s['cv'] for s in usable if s.get('cv') is not None]
    out = dict(n_positions=len(stats), n_positions_usable=len(usable),
               mean_cv=round(float(np.mean(cv_list)), 4) if cv_list else None)
    allobs, within_ss, n_obs = [], 0.0, 0
    for s in usable:
        vals = s.get('_values') or []
        if len(vals) < 2:
            continue
        arr = np.asarray(vals, float)
        allobs.extend(vals)
        within_ss += float(((arr - arr.mean()) ** 2).sum())
        n_obs += len(vals)
    if n_obs >= 6:
        grand = float(np.mean(np.asarray(allobs, float)))
        total_ss = float(((np.asarray(allobs, float) - grand) ** 2).sum())
        out.update(grand_mean=round(grand, 4), n_obs=n_obs,
                   within_ss=round(within_ss, 2), total_ss=round(total_ss, 2),
                   seasonal_ss_share=(round(1.0 - within_ss / total_ss, 4) if total_ss > 0 else None))
        out['interpretation'] = (
            '季节形态主导' if (out['seasonal_ss_share'] or 0) >= 0.5 else
            '季节性与年份波动并重' if (out['seasonal_ss_share'] or 0) >= 0.25 else
            '季节性弱，年份间价格水平漂移主导')
    return out


# ----------------------------------------------------------------------------- coverage
def coverage(daily, years, freq, window_weeks=52, start_week=1, dups=None,
             expected_per_year=None):
    """样本覆盖审计：每一年实际从第几周/月到第几周/月，覆盖多少位置，缺口在哪。"""
    dups = dups or []
    out = []
    today = daily[-1]['date'] if daily else None
    for y in sorted(years):
        ks = sorted(s for s in years[y] if years[y][s]['value'] is not None)
        if not ks:
            continue
        slots = years[y]
        nd = sum(s['n_days'] for s in slots.values())
        gaps = [k for k in range(min(ks), max(ks) + 1) if k not in ks]
        out.append(dict(
            year=y, first_pos=ks[0], last_pos=ks[-1],
            first_date=slots[ks[0]]['first_date'], last_date=slots[ks[-1]]['last_date'],
            n_positions=len(ks), n_days=nd,
            expected_days=(expected_per_year or {}).get(y),
            interior_gaps=gaps, n_interior_gaps=len(gaps),
            is_partial=(ks[0] != start_week) or (max(ks) < window_weeks),
            note='部分年份（缺前段/后段）' if (ks[0] != start_week or max(ks) < window_weeks) else '完整覆盖',
            duplicate_dates=[d for d in dups if d.startswith(str(y))],
        ))
    return out


def weekday_gaps(daily, holidays_cn=()):
    """工作日内完全无报价的日期（剔除已知停市日），作为'真实缺口'清单。不做填补。"""
    have = {r['date'] for r in daily}
    if not daily:
        return []
    hol = set(holidays_cn)
    gaps, d = [], daily[0]['date']
    end = daily[-1]['date']
    from datetime import timedelta
    while d <= end:
        if d.weekday() < 5 and d not in have and d not in hol:
            gaps.append(d.isoformat())
        d += timedelta(days=1)
    return gaps


# ----------------------------------------------------------------------------- report bundle
def analyze(case, daily, freq, holiday_week=None):
    """一键跑完某案例某频率的全部统计，返回 JSON 可序列化的 dict。"""
    window = int(case.get('quarter_end_iso_week', 52))
    sw = int(case.get('window_start_iso_week', 1))
    mine = int(case.get('min_years_for_stats', MIN_YEARS_DEFAULT))
    cy = int(case['current_year'])
    years = align(daily, freq, window_weeks=window, start_week=sw)
    reb, base = normalize(years, freq)
    rows, stats = stats_by_position(years, freq, window, sw, mine)
    extra = 0 if freq == 'weekly' else 1
    for st in stats:
        st['label'] = ('W%02d' % st['position']) if freq == 'weekly' else ('%02d月' % st['position'])
        # 剔除该位置"样本内最高/最低年"后均值的相对变化 —— 单年杠杆影响
        if st.get('mean') and st.get('n_years', 0) >= 3:
            tv = [years[y][st['position']]['value'] for y in st['years']
                  if years[y][st['position']]['value'] is not None]
            if len(tv) >= 3:
                i_hi, i_lo = int(np.argmax(tv)), int(np.argmin(tv))
                st['mean_ex_hi'] = round(float(np.mean(np.delete(np.asarray(tv), i_hi))), 4)
                st['mean_ex_lo'] = round(float(np.mean(np.delete(np.asarray(tv), i_lo))), 4)
                st['leverage_hi'] = round((st['mean_ex_hi'] - st['mean']) / st['mean'], 4)
                st['leverage_lo'] = round((st['mean_ex_lo'] - st['mean']) / st['mean'], 4)
    for r in rows:
        r['label'] = ('W%02d' % r['position']) if freq == 'weekly' else ('%02d月' % r['position'])
    cur = position_of_current(years, cy, freq, window, sw, mine)
    for r in cur:
        r['label'] = ('W%02d' % r['position']) if freq == 'weekly' else ('%02d月' % r['position'])
    anom = anomaly_scan(years, stats, freq)
    stab = stability(stats)
    cov = coverage(daily, years, freq, window, sw)
    # 归一化后的分位带（独立于绝对价格，用于"年初归一化"视图）
    reb_stats = []
    for p in positions(freq, window, sw):
        v = [reb[y][p] for y in sorted(reb) if p in reb[y] and reb[y][p] is not None]
        st = dict(position=p, n_years=len(v),
                  label=('W%02d' % p) if freq == 'weekly' else ('%02d月' % p),
                  mean=round(float(np.mean(v)), 4) if v else None,
                  median=round(pctile(v, 50), 4) if v else None)
        for q in PCTS:
            st[_fmt(q)] = round(pctile(v, q), 4) if v else None
        reb_stats.append(st)
    return dict(
        case_id=case['id'], title=case['title'], freq=freq,
        caliber=dict(requested=case['caliber_requested'], obtained=case['caliber_obtained'],
                     downgraded=bool(case.get('caliber_downgraded')), note=case.get('downgrade_note'),
                     unit=case['unit'], tax=case['tax']),
        window=dict(start_week=sw, end_week=window, unit=freq),
        min_years=mine,
        n_days=len(daily), first_date=daily[0]['date'].isoformat() if daily else None,
        last_date=daily[-1]['date'].isoformat() if daily else None,
        years=[dict(year=y, base=base[y],
                    first=min([s['first_date'] for s in years[y].values() if s['first_date']] or [None]),
                    last=max([s['last_date'] for s in years[y].values() if s['last_date']] or [None]),
                    n_days=sum(s['n_days'] for s in years[y].values()),
                    coverage=[min(s for s in years[y]), max(s for s in years[y])]) for y in sorted(years)],
        raw_series={str(y): {str(k): v['value'] for k, v in years[y].items()} for y in years},
        norm_series={str(y): {str(k): v for k, v in reb[y].items()} for y in reb},
        raw_rows=rows, stats=stats, reb_stats=reb_stats,
        current=cur, anomaly=anom, stability=stab, coverage=cov,
        holiday_week=holiday_week,
    )
