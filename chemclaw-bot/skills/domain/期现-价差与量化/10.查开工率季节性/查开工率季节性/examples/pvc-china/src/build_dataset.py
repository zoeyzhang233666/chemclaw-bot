# -*- coding: utf-8 -*-
"""
核心数据集构建：把逐篇核验过的公开速讯整理成可追溯的周度序列，
并做口径审计（样本数、产能基数、环比/同比自洽、锚点重复校验）。

输入（全部为人工逐篇核验后登记，每条带 URL 与原文摘录）
----------------------------------------------------------
    raw/sources_manual.csv : d8,aid,week_end,util,util_c2c,util_yoy,calc,calc_c2c,calc_yoy,
                             eth,eth_c2c,eth_yoy,sample_n,cap_base,source_url,body,caliber,note
    其中 util = 整体产能利用率（%），calc = 电石法，eth = 乙烯法；
    *_c2c / *_yoy 为原文披露的 环比 / 同比 变化（百分点，原文多为“减少/增加”字样）。

输出
----
    raw/pvc_util_weekly.csv      周度宽表（含 ISO 周、月、来源）
    raw/pvc_util_long.csv        长表（三个口径堆叠，便于作图/透视）
    raw/anchor_check.csv         用 c2c/yoy 反推锚点与直接观测的一致性子表
    raw/sample_audit.csv         样本企业数、产能基数、口径变化事件

不做的三件事（硬约束）
----------------------
1. 不插值、不前向填充、不推测未披露周值；
2. 不把卓创/钢联的“开工负荷率”与隆众“产能利用率”混为一条序列；
3. 不把“产能利用率 × 产能基数”当作全行业实际产量（样本口径≠统计口径）。
"""
import csv
import os
import sys
from datetime import date as _date, timedelta  # noqa: F401  (避免与字段名 date 冲突)


def iso_week_end_date(week_end):
    """week_end 为隆众披露的该周期截止日（YYYYMMDD，一般为周四）。返回 (iso_year, iso_week, 周四日期)。"""
    d = _date(int(week_end[:4]), int(week_end[4:6]), int(week_end[6:8]))
    iy, iw, _ = d.isocalendar()
    return iy, iw, d


def month_days_range(d):
    return d.strftime('%Y-%m')


def load_sources(path):
    """读取并**按 week_end 排序**（锚点匹配依赖顺序，必须排序）。"""
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ('util', 'util_c2c', 'util_yoy', 'calc', 'calc_c2c', 'calc_yoy',
                  'eth', 'eth_c2c', 'eth_yoy'):
            v = (r.get(k) or '').strip().strip('\ufeff')
            r[k] = float(v) if v not in ('', 'NA', None) else None
        for k in ('sample_n', 'cap_base'):
            v = (r.get(k) or '').strip().strip('\ufeff')
            r[k] = float(v) if v not in ('', 'NA', None) else None
    rows.sort(key=lambda r: r['week_end'])
    return rows


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join('raw', 'sources_manual.csv')
    rows = load_sources(src)
    os.makedirs('raw', exist_ok=True)

    # ---------- 1) 周度宽表 ----------
    wide, long_rows, anchor = [], [], []
    rows = [r for r in rows if r['util'] is not None]
    for r in rows:
        iy, iw, d = iso_week_end_date(r['week_end'])
        rec = {
            'week_end': r['week_end'], 'date': d.isoformat(), 'iso_year': iy, 'iso_week': iw,
            'month': month_days_range(d),
            'util': r['util'], 'calc': r['calc'], 'eth': r['eth'],
            'util_c2c': r['util_c2c'], 'calc_c2c': r['calc_c2c'], 'eth_c2c': r['eth_c2c'],
            'util_yoy': r['util_yoy'], 'calc_yoy': r['calc_yoy'], 'eth_yoy': r['eth_yoy'],
            'sample_n': r['sample_n'], 'cap_base': r['cap_base'],
            'caliber': r.get('caliber', ''), 'source_url': r['source_url'], 'note': r.get('note', ''),
        }
        wide.append(rec)
        for metric, label in (('util', '整体'), ('calc', '电石法'), ('eth', '乙烯法')):
            if r[metric] is not None:
                long_rows.append({'date': d.isoformat(), 'iso_year': iy, 'iso_week': iw,
                                  'metric': metric, 'metric_label': label, 'value': r[metric],
                                  'week_end': r['week_end']})

        # ---------- 3) 锚点一致性 ----------
        # 关键口径①：隆众“环比”锚点 = **上一个发布日**（通常为上周四/最邻近工作日），
        #            而不是 ISO 日历周的“上一周”。因此必须按真实发布间隔匹配，
        #            否则 2026 年 7-8 月的发布节奏跳跃（7/30→8/6→8/13→8/20）会被误判。
        # 关键口径②：隆众“同比”锚点 = **上年同一发布日当周**，同样不是 ISO 周号 -1。
        prev = [w for w in wide[:-1]
                if 0 < (d - _date.fromisoformat(w['date'])).days < 14]
        cadence_prev = prev
        if not prev:
            # 图表接口回传序列在 2026-07-24→08-07 之间缺少 07-31 观测，但 08-07 的“环比”锚点
            # 恰为 07-31（见交叉校验 C5），说明接口窗口内确存在 07-31 数据，只是未回传。
            cadence_prev = [w for w in wide[:-1] if w['week_end'] == '20260724']
        # ---------- 4) 发布节奏（周期跳跃）检测 ----------
        gap_days = None
        if cadence_prev:
            gap_days = (d - _date.fromisoformat(cadence_prev[-1]['date'])).days
        rec['gap_days'] = gap_days
        rec['cadence_flag'] = ('' if gap_days in (7,) else
                              ('首发/断档' if gap_days is None else
                               ('短于7天' if gap_days < 7 else '长于7天：统计周期可能跳跃')))
        rec['obs_type'] = ('接口回传序列' if r.get('aid', 'NA') == 'NA'
                           else ('原文速讯（含样本说明）' if r['sample_n'] else '原文速讯'))
        wide[-1] = rec
        for metric, label in (('util', '整体'), ('calc', '电石法'), ('eth', '乙烯法')):
            if r[f'{metric}_c2c'] is not None and prev:
                implied = r[metric] + r[f'{metric}_c2c']
                anchor.append({'type': '环比锚点', 'metric': label, 'week_end': r['week_end'],
                               'implied': round(implied, 2), 'anchor_week_end': prev[-1]['week_end'],
                               'anchor_observed': prev[-1][metric],
                               'diff': (None if prev[-1][metric] is None
                                        else round(implied - prev[-1][metric], 2)),
                               'verdict': ('缺口：锚点周值未观测' if prev[-1][metric] is None
                                           else ('一致(±0.02)' if abs(implied - prev[-1][metric]) <= 0.02
                                                 else '不一致，需复核披露符号'))})
            if r[f'{metric}_yoy'] is not None:
                implied = r[metric] + r[f'{metric}_yoy']
                base = _date(d.year - 1, d.month, d.day)
                obs_row = [w for w in wide[:-1]
                           if abs((_date.fromisoformat(w['date']) - base).days) <= 3]
                obs = obs_row[-1][metric] if obs_row else None
                anchor.append({'type': '同比锚点', 'metric': label, 'week_end': r['week_end'],
                               'implied': round(implied, 2),
                               'anchor_week_end': obs_row[-1]['week_end'] if obs_row else '上年同日当周(缺口)',
                               'anchor_observed': obs,
                               'diff': (None if obs is None else round(implied - obs, 2)),
                               'verdict': '缺口：上年同日当周无同口径观测，不得填补' if obs is None else '可交叉校验'})

    wide_path = os.path.join('raw', 'pvc_util_weekly.csv')
    with open(wide_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(wide[0].keys()))
        w.writeheader()
        w.writerows(wide)
    long_path = os.path.join('raw', 'pvc_util_long.csv')
    with open(long_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(long_rows[0].keys()))
        w.writeheader()
        w.writerows(long_rows)
    anchor_path = os.path.join('raw', 'anchor_check.csv')
    with open(anchor_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(anchor[0].keys()))
        w.writeheader()
        w.writerows(anchor)

    # ---------- 4) 样本审计 ----------
    audit = []
    for r in rows:
        if r.get('note'):
            audit.append({'week_end': r['week_end'], 'sample_n': r['sample_n'], 'cap_base': r['cap_base'],
                          'note': r['note'], 'source_url': r['source_url']})
    audit_path = os.path.join('raw', 'sample_audit.csv')
    with open(audit_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['week_end', 'sample_n', 'cap_base', 'note', 'source_url'])
        w.writeheader()
        w.writerows(audit)

    print(f'weeks={len(wide)}  ({wide[0]["date"]} .. {wide[-1]["date"]})')
    print(f'iso weeks: {wide[0]["iso_year"]}-W{wide[0]["iso_week"]:02d} .. '
          f'{wide[-1]["iso_year"]}-W{wide[-1]["iso_week"]:02d}')
    for a in anchor[:8]:
        print('anchor', a)


if __name__ == '__main__':
    main()
