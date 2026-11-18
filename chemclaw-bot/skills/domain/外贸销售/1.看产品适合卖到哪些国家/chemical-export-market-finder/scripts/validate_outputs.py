#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_outputs.py - delivery gate for the market-analysis workflow.

Checks the things that most often go wrong (and that make a report untrustworthy):

  [F] FATAL    - must fix before delivering
  [W] WARNING  - should fix / must be disclosed
  [I] INFO     - FYI

Usage
-----
    python validate_outputs.py --data trade_data --config my_product.json
    python validate_outputs.py --data trade_data --config my_product.json --out out --html out/x.html
Exit code 0 = no FATAL findings.
"""
import argparse
import csv
import json
import os
import re
import sys

FATAL, WARN, INFO = [], [], []


def f(msg):
    FATAL.append(msg)


def w(msg):
    WARN.append(msg)


def i_(msg):
    INFO.append(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--html', default=None)
    a = ap.parse_args()

    # ---------------- config
    try:
        cfg = json.load(open(a.config, encoding='utf-8'))
    except Exception as e:
        f(f'config 不是合法 JSON：{e}')
        report(); return 1

    prod = cfg.get('product', {})
    for k in ('name', 'hs6'):
        if not prod.get(k):
            f(f'config.product.{k} 缺失（产品身份是第一步，不能为空）')
    hs6 = str(prod.get('hs6', ''))
    if hs6 and not re.fullmatch(r'\d{6}', hs6):
        f(f'HS 编码应为 6 位数字，实际为 {hs6!r}（本地 8/10 位编码请放在 tariffs[].hs_local）')

    # ---------------- tariffs
    tars = cfg.get('tariffs', [])
    if not tars:
        w('config.tariffs 为空：报告将不含任何关税比较')
    nver = 0
    for t in tars:
        iso = t.get('iso3', '?')
        st = t.get('status')
        mfn = t.get('mfn')
        if st not in ('verified', 'gap'):
            f(f"{iso}: status 必须是 'verified' 或 'gap'，实际 {st!r}")
        if st == 'verified' and mfn is None:
            f(f'{iso}: 标记为 verified 但没有税率数值（自相矛盾）')
        if st == 'gap' and mfn is not None:
            f(f'{iso}: 标记为 gap 却填了税率 {mfn}（要么核验来源，要么不要填数值）')
        if st == 'verified':
            nver += 1
            src = (t.get('source') or '').lower()
            if not src:
                f(f'{iso}: verified 但 source 为空——无法溯源')
            elif not any(k in src for k in ('hts', 'taric', 'customs', 'trade.gov', 'http', '.gov')):
                w(f'{iso}: source 不像官方系统（{t.get("source")!r}），请确认')
        if not t.get('hs_local'):
            w(f'{iso}: 缺少本地 8/10 位编码（hs_local）——关税必须按本地编码核验')
    if tars:
        i_(f'关税：{nver}/{len(tars)} 个国家已核验，{len(tars)-nver} 个为缺口')
        if nver == 0:
            w('没有任何关税被核验：报告无法支撑"进入条件"判断，需补齐或明确说明')

    # ---------------- industry
    inds = cfg.get('industry', [])
    if not inds:
        w('config.industry 为空：缺少下游产业背景')
    for it in inds:
        src = (it.get('source') or '').strip()
        if not src:
            f(f"industry「{it.get('item','?')}」缺少来源——产业信息必须有出处")
        elif src.lower() in ('行业常识', 'common knowledge', '经验', 'n/a', '-'):
            f(f"industry「{it.get('item','?')}」的来源是「{src}」，不是可核实来源，请换成机构/报告名")

    # ---------------- judgments tone
    for j in cfg.get('judgments', []):
        body = j.get('body', '')
        for bad in ('必然', '肯定能卖', '确定需求', '预计销量', '保证'):
            if bad in body:
                w(f'judgments 中出现「{bad}」类表述，可能把推断写成事实：{body[:60]}...')

    # ---------------- data
    p = os.path.join(a.data, 'imports_by_reporter_year.csv')
    if not os.path.exists(p):
        f(f'缺少 {p}（先运行 fetch_trade.py）')
        report(); return 1
    rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
    if not rows:
        f('贸易数据为空'); report(); return 1
    years = sorted({int(r['year']) for r in rows})
    i_(f'数据：{len(rows)} 行，年份 {years[0]}–{years[-1]}')

    zero_neg = sum(1 for r in rows if float(r.get('import_usd') or 0) < 0)
    if zero_neg:
        f(f'发现 {zero_neg} 行进口额为负')

    # origin share sanity: origin must never exceed world
    bad = [r for r in rows
           if float(r.get('origin_usd') or 0) > float(r.get('import_usd') or 0) * 1.02
           and float(r.get('import_usd') or 0) > 0]
    if bad:
        f(f'{len(bad)} 行"自原产国进口额 > 自全球进口额"，份额会 >100%，数据口径有误')

    # coverage drift
    cov = {y: len([r for r in rows if int(r['year']) == y]) for y in years}
    first, last = cov[years[0]], cov[years[-1]]
    if first and last < first * 0.9:
        w(f'报告国覆盖下降：{years[0]} 年 {first} 个 → {years[-1]} 年 {last} 个；'
          '全球合计跨年不可直接比较，报告须声明')
    if cov[years[-1]] < first * 0.85:
        w(f'{years[-1]} 年为不完整/初步年度（仅 {cov[years[-1]]} 个报告国），不宜作决策基准')

    # net weight availability
    nw = sum(1 for r in rows if float(r.get('netweight_kg') or 0) > 0)
    if nw < len(rows) * 0.5:
        w(f'仅 {nw}/{len(rows)} 行有净重，单价(USD/t)大面积缺失属正常，不得估算')

    # partner file
    pp = os.path.join(a.data, 'partners_by_reporter_year.csv')
    if not os.path.exists(pp):
        w('没有来源国明细（未用 --partners）：报告无法分析竞争来源结构')
    else:
        pr = list(csv.DictReader(open(pp, encoding='utf-8-sig')))
        i_(f'来源国明细：{len(pr)} 行')
        if len(pr) < 50:
            w('来源国明细行数过少，可能只覆盖个别国家')

    # ---------------- html
    hp = a.html
    if not hp and a.out:
        cands = [x for x in os.listdir(a.out) if x.endswith('.html')] if os.path.isdir(a.out) else []
        if cands:
            hp = os.path.join(a.out, cands[0])
    if hp and os.path.exists(hp):
        h = open(hp, encoding='utf-8').read()
        i_(f'HTML 大小 {os.path.getsize(hp)/1e6:.1f} MB')
        if '__PAYLOAD__' in h or '__TITLE__' in h:
            f('HTML 仍有未替换的占位符（__PAYLOAD__/__TITLE__）')
        if 'echarts' not in h:
            f('HTML 未包含 echarts（图表不会渲染）')
        if '__WORLD_GEO__' not in h:
            w('HTML 未内联世界地图，地图需要外网或同目录 world.json')
        for must in ('口径', '来源'):
            if must not in h:
                w(f'HTML 缺少「{must}」章节——交付要求必须注明统计口径与数据来源')
        # currency / unit statements
        if 'USD' not in h:
            w('HTML 未声明币种（USD）')
        if 'kg' not in h:
            w('HTML 未声明数量单位（kg）')

    report()
    return 1 if FATAL else 0


def report():
    print('\n' + '=' * 70)
    print('交付自检报告')
    print('=' * 70)
    for tag, lst, pref in (('FATAL', FATAL, '✗'), ('WARN', WARN, '!'), ('INFO', INFO, '·')):
        if not lst:
            continue
        print(f'\n[{tag}] {len(lst)} 条')
        for m in lst:
            print(f'  {pref} {m}')
    if not FATAL and not WARN:
        print('\n✅ 全部检查通过')
    elif not FATAL:
        print('\n⚠ 无致命问题，但有警告需确认或披露')
    else:
        print('\n❌ 存在致命问题，请修复后再交付')


if __name__ == '__main__':
    sys.exit(main())
