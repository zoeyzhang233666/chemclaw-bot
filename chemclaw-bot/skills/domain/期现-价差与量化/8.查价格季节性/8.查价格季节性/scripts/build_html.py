# -*- coding: utf-8 -*-
"""build_html.py — 把案例 JSON 注入 HTML 模板，产出单文件交互式报告。

不做任何"手写结论"：所有数字都从 JSON 里取；少数派生句（如"当前年位置"）由数据计算生成，
保证报告与 Excel、CSV 完全一致。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(ROOT, 'templates', 'report_template.html')
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'out')


def req_year_txt(meta):
    v = meta.get('requested_years')
    return str(v) if v else ''


def build(case_id, dst=None):
    d = json.load(open(os.path.join(DATA, 'out', '%s.json' % case_id), encoding='utf-8'))
    tpl = open(TEMPLATE, encoding='utf-8').read()
    meta = d['meta']
    w = d['weekly']
    cur_year = meta['current_year']

    # ---- 顶部横幅：把口径降级与样本不足写在第一屏 ----
    ys = [y['year'] for y in w['years']]
    # "完整年份"= 该年 12 个月都有报价；当前年若未走完，必须排除，否则与覆盖表自相矛盾
    full_years = [c['year'] for c in d['monthly']['coverage'] if c['n_positions'] >= 12]
    cur_year = meta['current_year']
    partial = [c['year'] for c in d['monthly']['coverage'] if c['n_positions'] < 12]
    got = len(ys)
    banner = []
    if meta['caliber']['downgraded']:
        banner.append(
            '<b>口径声明</b>：本报告未能取得"%s"的完整 %s 年历史，实际使用的是 <b>%s</b>。'
            % (meta['caliber']['requested'], req_year_txt(meta), meta['caliber']['obtained']))
    banner.append(
        '<b>样本诚实披露</b>：%s<b>实际覆盖 %d 年（%s）</b>。'
        '%s 其中 1–12 月每个月都有报价的完整年份为 <b>%d 年%s</b>；'
        '其余年份只覆盖部分月份，已在"逐年样本覆盖"表逐段标注，<b>未做任何插值或补齐</b>。'
        % (('申请 %s 年，' % req_year_txt(meta)) if req_year_txt(meta) else '',
           got, '%s–%s' % (ys[0], ys[-1]) if ys else '—',
           ('当前年 %d 尚未走完（数据截至 %s），因此不计入完整年份。' % (cur_year, meta['last'])
            if cur_year in partial else ''),
           len(full_years), ('（%s）' % ','.join(map(str, full_years))) if full_years else ''))
    banner_html = '<br>'.join('· ' + b.replace('**', '') for b in banner)

    payload = dict(
        meta=meta,
        weekly=dict(years=w['years'], stats=w['stats'], reb_stats=w['reb_stats'],
                    raw_series=w['raw_series'], norm_series=w['norm_series'],
                    current=w['current'], coverage=w['coverage'], window=w['window'],
                    anomaly=w['anomaly'], stability=w['stability'], caliber=w['caliber'],
                    audit=d['weekly'].get('audit', {})),
        monthly=dict(years=d['monthly']['years'], stats=d['monthly']['stats'],
                     reb_stats=d['monthly']['reb_stats'], raw_series=d['monthly']['raw_series'],
                     norm_series=d['monthly']['norm_series'], current=d['monthly']['current'],
                     coverage=d['monthly']['coverage'], window=d['monthly']['window'],
                     anomaly=d['monthly']['anomaly'], stability=d['monthly']['stability'],
                     caliber=d['monthly']['caliber'], audit=d['monthly'].get('audit', {})),
    )
    # 去掉前端不需要的大字段（不删 raw_rows，保留供二次分析；这里只裁剪 stats 里的冗余）
    title = meta['title']
    subtitle = ('样本 %s → %s · 自然日报价 %s 点 · 周度按 ISO 周对齐、月度按自然月对齐 · '
                '当前年 %d 高亮' % (meta['first'], meta['last'], format(meta['n_days'], ','), cur_year))
    src = (meta['caliber']['obtained'] + '；'
           + (d['weekly'].get('audit', {}).get('source') or ''))

    js = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    html = (tpl.replace('__TITLE__', title)
               .replace('__SUBTITLE__', subtitle)
               .replace('__BANNER__', banner_html)
               .replace('__CURYEAR__', str(cur_year))
               .replace('__GENERATED__', datetime.now().strftime('%Y-%m-%d %H:%M'))
               .replace('__SOURCE_LINE__', src)
               .replace('__DATA__', js))
    dst = dst or os.path.join(OUT, '%s_季节性分析报告.html' % title)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write(html)
    print('[OK] %s  (%.1f KB)' % (dst, os.path.getsize(dst) / 1024))
    return dst


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True)
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    build(a.case, a.out or None)
