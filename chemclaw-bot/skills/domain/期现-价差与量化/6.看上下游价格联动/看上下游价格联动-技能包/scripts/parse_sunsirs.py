# -*- coding: utf-8 -*-
"""
parse_sunsirs.py —— 解析 SunSirs(生意社国际版) 每日现货价格页

页面：https://www.sunsirs.com/uk/sdetail-day-YYYY-MMDD.html
结构：表格列 = Commodity | Sectors | prev_date | date | Change
      PX  -> prodetail-968.html，PTA -> prodetail-356.html
用途：100ppi 中文「基准价」列表只回溯到 2025-05（PX）/ 2024-08（PTA），
      且周末不发文；SunSirs 每日更新（含周末），可补齐完整日频序列。

口径说明（红线）：
  - SunSirs 的 PX / PTA 现货价与 100ppi「基准价」为同一基准、同单位（元/吨，含税，
    现货基准价），可在重叠区间做一致性校验（见 --check CSV）。
  - 同一天的页面会同时给出前一交易日价格，可交叉校验，不必额外抓取。
  - 读取失败（404/空表）的日子记为缺失，不插值。
"""
import argparse
import csv
import glob
import json
import os
import re
import sys

DATE_IN_URL = re.compile(r'sdetail-day-(\d{4})-(\d{2})(\d{2})\.html')
DATE_IN_FILE = re.compile(r'sst_(\d{4})-(\d{2})-(\d{2})\.html')
CHART_DATE = re.compile(r'100 Spot Commodities Price Chart\s*-\s*(\d{2})/(\d{2})/(\d{4})')
PROD = {'PX': '968', 'PTA': '356'}


def extract_row(html, pid):
    """返回 (prev_val, cur_val) —— 表格中该商品所在行的两列价格"""
    idx = html.find(f'prodetail-{pid}.html')
    if idx < 0:
        return None
    seg = html[idx:idx + 900]
    nums = re.findall(r'<td[^>]*align="right"[^>]*>([\d,.\-]+)</td>', seg)
    if len(nums) < 2:
        nums = re.findall(r'<td[^>]*>\s*([\d]{1,3}(?:,\d{3})*(?:\.\d+)?)\s*</td>', seg)
    if len(nums) < 2:
        return None

    def f(x):
        try:
            return float(x.replace(',', ''))
        except ValueError:
            return None
    return f(nums[0]), f(nums[1])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default='raw')
    ap.add_argument('--pattern', default='sst_*.html')
    ap.add_argument('--out', default='processed/sunsirs_daily.csv')
    ap.add_argument('--check', default=None, help='与 100ppi 序列做一致性校验：CSV 路径（列 date,value）')
    a = ap.parse_args(argv)

    recs = {}
    missing = []
    for p in sorted(glob.glob(os.path.join(a.raw, a.pattern))):
        m = DATE_IN_FILE.search(os.path.basename(p)) or DATE_IN_URL.search(p)
        if not m:
            continue
        y, mo, dd = m.groups()
        url_date = f'{y}-{mo}-{dd}'
        html = open(p, encoding='utf-8', errors='replace').read()
        # 页面本身标注的日期（更强校验，防止重定向到最新页）
        cd = CHART_DATE.search(html)
        page_date = f'{cd.group(3)}-{cd.group(2)}-{cd.group(1)}' if cd else url_date
        px = extract_row(html, PROD['PX'])
        pta = extract_row(html, PROD['PTA'])
        if not px or not pta:
            missing.append(url_date)
            continue
        rec = recs.setdefault(page_date, {'date': page_date})
        # 当前值可信度最高；前一日值用于补缺
        rec['px'] = px[1]
        rec['pta'] = pta[1]
        rec.setdefault('prev_hint', {})[url_date] = {'px': px[0], 'pta': pta[0]}
    rows = [recs[k] for k in sorted(recs)]
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['date', 'px', 'pta'])
        for r in rows:
            w.writerow([r['date'], r['px'], r['pta']])
    print(json.dumps({'rows': len(rows), 'first': rows[0]['date'] if rows else None,
                      'last': rows[-1]['date'] if rows else None,
                      'missing_pages': missing[:20], 'n_missing': len(missing)},
                     ensure_ascii=False, indent=1))

    # 交叉校验：同日 prev_hint 与「上一行」是否一致
    conflicts = []
    by_date = {r['date']: r for r in rows}
    for d, r in by_date.items():
        for src, v in (r.get('prev_hint') or {}).items():
            if src in by_date and v['px'] is not None and abs(v['px'] - by_date[src]['px']) > 0.5:
                conflicts.append({'date': src, 'src_px': v['px'], 'table_px': by_date[src]['px']})
            if src in by_date and v['pta'] is not None and abs(v['pta'] - by_date[src]['pta']) > 0.5:
                conflicts.append({'date': src, 'src_pta': v['pta'], 'table_pta': by_date[src]['pta']})
    print('prev-day cross-check conflicts:', len(conflicts))

    if a.check and rows:
        ref = {}
        with open(a.check, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                ref[r['date']] = float(r['value'])
        both = [(r['date'], r['px'], ref[r['date']]) for r in rows if r['date'] in ref]
        if both:
            diffs = [abs(px - v) for _, px, v in both]
            rel = [abs(px - v) / v for _, px, v in both]
            print(json.dumps({
                'overlap_days': len(both),
                'exact_match_pct': round(100 * sum(1 for d in diffs if d < 0.5) / len(both), 2),
                'mean_abs_diff': round(sum(diffs) / len(diffs), 2),
                'max_abs_diff': round(max(diffs), 2),
                'mean_abs_rel_diff_pct': round(100 * sum(rel) / len(rel), 3),
            }, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
