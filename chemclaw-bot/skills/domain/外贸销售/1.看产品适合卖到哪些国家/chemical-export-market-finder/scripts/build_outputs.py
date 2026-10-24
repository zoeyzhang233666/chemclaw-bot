#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_outputs.py - turn fetched trade data into (a) an interactive HTML report and
(b) an Excel workbook with raw data, comparisons, formulas, sources and gap flags.

STEP 3 of the workflow. Product-, market- and country-agnostic: everything is driven by
the data directory + a small --config JSON that carries product identity, tariff evidence
and industry notes.

Usage
-----
    python build_outputs.py --data trade_data --config my_product.json --out ./out

Minimal config keys (see templates/analysis_config.template.json):
    product.name, product.spec, product.hs6, product.cas
    tariff_source_defaults   optional
    tariffs[]                {iso3, country, hs_local, mfn|null, basis, source, restriction, status}
    industry[]               {item, market, content, source}
    judgments[]              optional manual findings shown in the HTML report

Design rules baked in
---------------------
* A missing year stays missing. No interpolation, no zero-fill, ever.
* China share = origin USD / world USD, same reporter, same year, same code.
* One headline rate per country, and it carries a status badge (verified / gap).
* Every sheet and every HTML section states year, source, currency, unit, code.
"""
import argparse
import csv
import json
import os
import sys
from datetime import date

# ---------------------------------------------------------------- data loading

def load(data_dir):
    p1 = os.path.join(data_dir, 'imports_by_reporter_year.csv')
    if not os.path.exists(p1):
        sys.exit(f'ERROR: {p1} not found. Run fetch_trade.py first.')
    rows = list(csv.DictReader(open(p1, encoding='utf-8-sig')))
    num = ('import_usd', 'netweight_kg', 'qty', 'origin_usd', 'origin_kg')
    for r in rows:
        for k in num:
            try:
                r[k] = float(r.get(k) or 0)
            except ValueError:
                r[k] = 0.0
        r['year'] = int(r['year'])
        r['reporterCode'] = int(r['reporterCode'])
    prow = []
    p2 = os.path.join(data_dir, 'partners_by_reporter_year.csv')
    if os.path.exists(p2):
        prow = list(csv.DictReader(open(p2, encoding='utf-8-sig')))
        for r in prow:
            r['value_usd'] = float(r.get('value_usd') or 0)
            r['netweight_kg'] = float(r.get('netweight_kg') or 0)
            r['year'] = int(r['year']); r['reporterCode'] = int(r['reporterCode'])
    meta = {}
    pm = os.path.join(data_dir, 'fetch_meta.json')
    if os.path.exists(pm):
        meta = json.load(open(pm, encoding='utf-8'))
    return rows, prow, meta


def build_markets(rows, prow, min_usd, max_n=40):
    """One record per reporter: size, growth, origin share, supplier mix."""
    years = sorted({r['year'] for r in rows})
    series = {}
    for r in rows:
        series.setdefault(r['reporterCode'], {})[r['year']] = r
    latest = {}
    for r in rows:
        if r['import_usd'] > 0:
            latest[r['reporterCode']] = max(latest.get(r['reporterCode'], 0), r['year'])
    base_year = years[0]
    out = []
    for rep, ly in latest.items():
        cur = series[rep][ly]
        v = cur['import_usd']
        if v < min_usd:
            continue
        b = series[rep].get(base_year)
        bv = b['import_usd'] if b else None
        span = ly - base_year
        cagr = ((v / bv) ** (1 / span) - 1) if (bv and bv > 0 and span > 0) else None
        # supplier mix for the latest year
        ps = [p for p in prow if p['reporterCode'] == rep and p['year'] == ly]
        tot = sum(p['value_usd'] for p in ps)
        mix = sorted(((p['partner'], p['value_usd'] / tot * 100) for p in ps if tot),
                     key=lambda x: -x[1])[:6] if tot else []
        out.append({
            'iso3': cur['iso3'], 'name': cur['reporter'], 'reporterCode': rep,
            'latest_year': ly, 'usd': v,
            'usd_base': bv, 'base_year': base_year,
            'cagr': cagr,
            'origin_usd': cur['origin_usd'],
            'origin_share': (cur['origin_usd'] / v * 100) if v else None,
            'kg': cur['netweight_kg'],
            'unit_value': (v / (cur['netweight_kg'] / 1000)) if cur['netweight_kg'] else None,
            'top_partners': mix, 'partner_total': tot,
            'series_usd': {y: (series[rep].get(y) or {}).get('import_usd') for y in years},
            'series_origin': {y: (series[rep].get(y) or {}).get('origin_usd') for y in years},
            'series_kg': {y: (series[rep].get(y) or {}).get('netweight_kg') for y in years},
        })
    out.sort(key=lambda x: -x['usd'])
    return out[:max_n], years


# ---------------------------------------------------------------- HTML

def html_report(markets, years, cfg, meta, glist):
    prod = cfg.get('product', {})
    pname = prod.get('name', 'Product')
    spec = prod.get('spec', '')
    hs6 = prod.get('hs6', '')
    cas = prod.get('cas', '')
    origin = prod.get('origin_name', 'China')
    tmap = {t['iso3']: t for t in cfg.get('tariffs', [])}
    industry = cfg.get('industry', [])
    judgments = cfg.get('judgments', [])
    today = date.today().isoformat()

    payload = {'markets': markets, 'globe': glist, 'years': years,
               'tariffs': cfg.get('tariffs', []),
               'product': {'name': pname, 'spec': spec, 'hs6': hs6, 'cas': cas, 'origin': origin}}
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates', 'report_template.html')
    html = open(tpl, encoding='utf-8').read()
    html = html.replace('__TITLE__', f'{pname} · 全球出口目标市场分析')
    html = html.replace('__PRODUCT_LINE__',
                        f'{pname} {spec} · HS {hs6} · CAS {cas} · 年份 {years[0]}–{years[-1]} · 金额 USD · 数量 kg')
    html = html.replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False))
    html = html.replace('__INDUSTRY__', json.dumps(industry, ensure_ascii=False))
    html = html.replace('__JUDGMENTS__', json.dumps(judgments, ensure_ascii=False))
    html = html.replace('__GENERATED__', today)
    html = html.replace('__ORIGIN__', origin)

    # inline echarts + world map if present next to the script (offline-friendly)
    here = os.path.dirname(os.path.abspath(__file__))
    lib_p = os.path.join(here, '..', 'assets', 'echarts.min.js')
    geo_p = os.path.join(here, '..', 'assets', 'world.json')
    inline = ''
    if os.path.exists(lib_p):
        inline += '<script>' + open(lib_p, encoding='utf-8').read() + '</script>\n'
    if os.path.exists(geo_p):
        inline += '<script>window.__WORLD_GEO__=' + open(geo_p, encoding='utf-8').read() + ';</script>\n'
    if inline:
        html = html.replace('<!--__ASSETS__-->', inline)
    return html


def validate_js(html):
    """Extract inline <script> bodies and check they are syntactically valid JS.

    Catches the classic failure: an unbalanced quote in a data literal (e.g. Côte d'Ivoire)
    silently breaks the whole report. Uses node when available; otherwise skips.
    """
    import re
    import shutil
    import subprocess
    import tempfile
    node = shutil.which('node') or os.environ.get('NODE_BIN')
    if not node:
        return None
    bodies = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
    # skip the big inlined vendor lib (last-but-one huge block)
    problems = []
    for i, b in enumerate(bodies):
        if len(b) > 400000:  # vendor bundle / geo json, already known-good
            continue
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(b)
            tmp = f.name
        try:
            r = subprocess.run([node, '--check', tmp], capture_output=True, text=True)
            if r.returncode != 0:
                problems.append(r.stderr.strip().splitlines()[:6])
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return problems


# ---------------------------------------------------------------- Excel

def xlsx_report(markets, rows, prow, years, cfg, meta, out_path):
    try:
        import xlsxwriter
    except ImportError:
        sys.exit('ERROR: xlsxwriter not installed. pip install xlsxwriter  (or use the bundled runtime)')
    prod = cfg.get('product', {})
    pname = prod.get('name', 'Product')
    hs6 = prod.get('hs6', '')
    tmap = {t['iso3']: t for t in cfg.get('tariffs', [])}

    wb = xlsxwriter.Workbook(out_path)
    F = lambda **k: wb.add_format(k)
    H = F(bold=True, bg_color='#1F3864', font_color='white', border=1, align='center',
          valign='vcenter', text_wrap=True)
    T = F(bold=True, font_size=14, font_color='#1F3864')
    S = F(font_size=9, font_color='#595959', italic=True, text_wrap=True, valign='top')
    NUM0 = F(num_format='#,##0', border=1)
    NUM1 = F(num_format='#,##0.0', border=1)
    PCT = F(num_format='0.0%', border=1)
    TXT = F(border=1, text_wrap=True, valign='top')
    TXTC = F(border=1, align='center')
    GAP = F(border=1, bg_color='#FFF2CC', font_color='#7F6000', italic=True, text_wrap=True, valign='top')
    OK = F(border=1, bg_color='#E2EFDA', valign='top', text_wrap=True)
    WARN = F(border=1, bg_color='#FCE4D6', text_wrap=True, valign='top')

    # 0 README
    ws = wb.add_worksheet('0.说明与口径')
    ws.set_column('A:A', 3); ws.set_column('B:B', 26); ws.set_column('C:C', 108)
    ws.write('B1', f'{pname} 出口目标市场研究 — 工作簿', T)
    ws.write('B2', f'生成日期：{date.today().isoformat()}', S)
    info = [
        ('产品', f"{pname} {prod.get('spec','')}；CAS {prod.get('cas','')}"),
        ('HS 编码（统计口径）', f"HS {hs6}（6 位全球可比层）。各国本地 8/10 位编码不同，见「5.关税与限制」页；跨国比较只在 6 位层进行。"),
        ('贸易数据来源', meta.get('source', 'UN Comtrade public preview API')),
        ('数据年份', f"{years[0]}–{years[-1]}；逐年报告国数见「4.全球趋势」页。近年覆盖下降会低估合计值。"),
        ('金额单位', '美元（USD），CIF，报告国自报，当期名义值，未作通胀/汇率调整。'),
        ('数量单位', '净重（netWgt），千克（kg）。未报送净重的国家显示 n/a，不估算。'),
        ('中国份额算法', '中国份额 = 报告国自中国进口金额 ÷ 报告国自全球进口金额（同一报告国、同年、同一 6 位编码）。'),
        ('增长率算法', 'CAGR = (末年值 ÷ 基年值)^(1/年数) − 1；基期缺失则为 n/a，不插值。'),
        ('关税来源', '仅"已核验"状态可用于报价；"待核验"为数据缺口。'),
        ('重要声明', '区分【贸易统计事实】【产业公开信息】【初步判断】。"进口规模大/增长快"不等于存在可成交需求，更不构成采购意向。'),
    ]
    r = 3
    for k, v in info:
        ws.write(r, 1, k, F(bold=True, valign='top', border=1, bg_color='#DDEBF7'))
        ws.write(r, 2, v, TXT); r += 1
    ws.write(r + 1, 1, '页签', T)
    for k, v in [('1.国家比较', '各国进口额/量、增长、中国份额、来源集中度、关税状态'),
                 ('2.历年明细', '报告国 × 年份 的进口额、净重、自中国进口额'),
                 ('3.竞争来源国', '报告国 × 年份 × 来源国 明细（若已拉取）'),
                 ('4.全球趋势', '各年合计与中国占比（公式驱动）'),
                 ('5.关税与限制', '本地编码、MFN、计征基础、贸易限制、核验状态'),
                 ('6.下游产业', '下游应用与产业公开信息'),
                 ('7.数据缺口', '缺失年份/字段/未核验关税'),
                 ('8.来源清单', '来源与取数时间')]:
        r += 1
        ws.write(r, 1, k, TXT); ws.write(r, 2, v, TXT)

    # 1 country comparison
    ws = wb.add_worksheet('1.国家比较')
    ws.set_column('A:A', 5); ws.set_column('B:B', 22); ws.set_column('C:M', 13); ws.set_column('N:N', 44)
    ws.write('A1', f'各国进口规模、增长、中国份额与关税比较（HS {hs6}，按最新年度进口额降序）', T)
    ws.write('A2', 'CAGR 为基年→最新年度；中国份额分母为该国自全球进口额。关税列标注核验状态。', S)
    hdr = ['#', '国家/地区', 'ISO3', '最新年度', '进口额 (USD)', '进口净重 (kg)', '均价 (USD/t)',
           f'{years[0]} 进口额 (USD)', 'CAGR', '自中国 (USD)', '中国份额（金额）',
           '最大来源国', '最大来源国份额', '关税 MFN', '核验状态', '贸易限制/备注']
    for i, h in enumerate(hdr):
        ws.write(3, i, h, H)
    ws.set_row(3, 32)
    for i, m in enumerate(markets):
        r = 4 + i
        ws.write_number(r, 0, i + 1, TXTC); ws.write(r, 1, m['name'], TXT); ws.write(r, 2, m['iso3'], TXTC)
        ws.write_number(r, 3, m['latest_year'], TXTC)
        ws.write_number(r, 4, m['usd'], NUM0)
        ws.write_number(r, 5, m['kg'], NUM0)
        ws.write_formula(r, 6, f'=IFERROR(E{r+1}/(F{r+1}/1000),"")' if m['kg'] else 'n/a', NUM0 if m['kg'] else GAP)
        if m['usd_base']:
            ws.write_number(r, 7, m['usd_base'], NUM0)
            ws.write_formula(r, 8, f'=IFERROR((E{r+1}/H{r+1})^(1/(D{r+1}-{years[0]}))-1,"")', PCT)
        else:
            ws.write(r, 7, 'n/a', GAP); ws.write(r, 8, 'n/a', GAP)
        ws.write_number(r, 9, m['origin_usd'], NUM0)
        ws.write_formula(r, 10, f'=IFERROR(J{r+1}/E{r+1},"")', PCT)
        if m['top_partners']:
            ws.write(r, 11, m['top_partners'][0][0], TXT)
            ws.write_number(r, 12, round(m['top_partners'][0][1] / 100, 4), PCT)
        else:
            ws.write(r, 11, '来源明细缺失', GAP); ws.write(r, 12, 'n/a', GAP)
        t = tmap.get(m['iso3'])
        if t and t.get('status') == 'verified' and t.get('mfn') is not None:
            ws.write_number(r, 13, t['mfn'] / 100, PCT); ws.write(r, 14, '已核验', OK)
            ws.write(r, 15, t.get('restriction', ''), TXT)
        else:
            ws.write(r, 13, '待核验', GAP); ws.write(r, 14, '待核验', GAP)
            ws.write(r, 15, (t or {}).get('restriction', '未取得'), GAP)
    ws.freeze_panes(4, 3)
    if markets:
        ws.autofilter(3, 0, 3 + len(markets), len(hdr) - 1)

    # 2 yearly detail
    ws = wb.add_worksheet('2.历年明细')
    ws.set_column('A:A', 22); ws.set_column('B:B', 7); ws.set_column('C:H', 16)
    ws.write('A1', '报告国 × 年份：进口额 / 净重 / 自中国进口额 / 自中国净重', T)
    ws.write('A2', '空白 = 该国该年未报送（缺口），不以 0 填充。', S)
    cols = ['国家', 'ISO3', '年份', '进口额 (USD)', '进口净重 (kg)', '自中国 (USD)', '自中国 (kg)',
            '中国份额（金额）', '中国份额（重量）']
    for i, c in enumerate(cols):
        ws.write(3, i, c, H)
    rr = 4
    for x in sorted(rows, key=lambda d: (d['reporter'], d['year'])):
        ws.write(rr, 0, x['reporter'], TXT); ws.write(rr, 1, x['iso3'], TXTC)
        ws.write_number(rr, 2, x['year'], TXTC)
        ws.write_number(rr, 3, x['import_usd'], NUM0); ws.write_number(rr, 4, x['netweight_kg'], NUM0)
        ws.write_number(rr, 5, x['origin_usd'], NUM0); ws.write_number(rr, 6, x['origin_kg'], NUM0)
        ws.write_formula(rr, 7, f'=IFERROR(F{rr+1}/D{rr+1},"")', PCT)
        if x['netweight_kg']:
            ws.write_formula(rr, 8, f'=IFERROR(G{rr+1}/E{rr+1},"")', PCT)
        else:
            ws.write(rr, 8, 'n/a', GAP)
        rr += 1
    wk_last = rr - 1
    ws.freeze_panes(4, 2); ws.autofilter(3, 0, wk_last, len(cols) - 1)

    # 3 partners
    ws = wb.add_worksheet('3.竞争来源国')
    ws.set_column('A:A', 22); ws.set_column('B:E', 16)
    ws.write('A1', '竞争来源国明细：报告国 × 年份 × 来源国的进口额与净重', T)
    if not prow:
        ws.write('A2', '未拉取来源国明细。运行 fetch_trade.py 时加 --partners 可启用。', GAP)
    else:
        cols = ['报告国', '报告国 ISO3', '年份', '来源国', '来源国代码', '进口额 (USD)', '净重 (kg)']
        for i, c in enumerate(cols):
            ws.write(3, i, c, H)
        iso_of = {x['reporterCode']: x['iso3'] for x in rows}
        rr = 4
        for p in sorted(prow, key=lambda d: (d['reporter'], d['year'], -d['value_usd'])):
            ws.write(rr, 0, p['reporter'], TXT); ws.write(rr, 1, iso_of.get(p['reporterCode'], ''), TXTC)
            ws.write_number(rr, 2, p['year'], TXTC); ws.write(rr, 3, p['partner'], TXT)
            ws.write(rr, 4, p['partnerCode'], TXTC)
            ws.write_number(rr, 5, p['value_usd'], NUM0); ws.write_number(rr, 6, p['netweight_kg'], NUM0)
            rr += 1
        ws.freeze_panes(4, 4); ws.autofilter(3, 0, rr - 1, len(cols) - 1)

    # 4 global trend
    ws = wb.add_worksheet('4.全球趋势')
    ws.set_column('A:A', 10); ws.set_column('B:F', 18)
    ws.write('A1', '全球进口合计与中国份额（对已报送国家求和，非真实世界总额）', T)
    cols = ['年份', '报告国数', '进口合计 (USD)', '自中国合计 (USD)', '中国占全球比重', '进口净重合计 (kg)']
    for i, c in enumerate(cols):
        ws.write(3, i, c, H)
    for i, y in enumerate(years):
        r = 4 + i
        ws.write_number(r, 0, y, TXTC)
        ws.write_formula(r, 1, f'=COUNTIF(\'2.历年明细\'!$C$4:$C${wk_last+1},A{r+1})', NUM0)
        ws.write_formula(r, 2, f'=SUMIF(\'2.历年明细\'!$C$4:$C${wk_last+1},A{r+1},\'2.历年明细\'!$D$4:$D${wk_last+1})', NUM0)
        ws.write_formula(r, 3, f'=SUMIF(\'2.历年明细\'!$C$4:$C${wk_last+1},A{r+1},\'2.历年明细\'!$F$4:$F${wk_last+1})', NUM0)
        ws.write_formula(r, 4, f'=IFERROR(D{r+1}/C{r+1},"")', PCT)
        ws.write_formula(r, 5, f'=SUMIF(\'2.历年明细\'!$C$4:$C${wk_last+1},A{r+1},\'2.历年明细\'!$E$4:$E${wk_last+1})', NUM0)

    # 5 tariffs
    ws = wb.add_worksheet('5.关税与限制')
    ws.set_column('A:A', 8); ws.set_column('B:B', 18); ws.set_column('C:C', 20); ws.set_column('D:E', 11)
    ws.set_column('F:F', 26); ws.set_column('G:G', 46); ws.set_column('H:H', 50); ws.set_column('I:I', 10)
    ws.write('A1', f'目的国对中国产 HS {hs6} 的进口关税、优惠税率与主要贸易限制', T)
    ws.write('A2', '【已核验】=已从官方系统取得行级税率；【待核验】=未能取得，必须补齐后才可用于报价。', S)
    for i, c in enumerate(['ISO3', '国家/地区', '本地编码', 'MFN 税率', '优惠税率', '计征基础',
                           '来源', '主要贸易限制', '状态']):
        ws.write(3, i, c, H)
    for i, t in enumerate(cfg.get('tariffs', [])):
        r = 4 + i
        ws.write(r, 0, t.get('iso3', ''), TXTC); ws.write(r, 1, t.get('country', ''), TXT)
        ws.write(r, 2, t.get('hs_local', ''), TXT)
        if t.get('mfn') is not None:
            ws.write_number(r, 3, t['mfn'] / 100, PCT)
        else:
            ws.write(r, 3, '待核验', GAP)
        ws.write(r, 4, t.get('pref') or '见备注', TXT)
        ws.write(r, 5, t.get('basis', ''), TXT)
        ok = t.get('status') == 'verified'
        ws.write(r, 6, t.get('source', ''), OK if ok else GAP)
        ws.write(r, 7, (t.get('restriction', '') + ' ' + t.get('note', '')).strip(), TXT)
        ws.write(r, 8, '已核验' if ok else '待核验', OK if ok else GAP)

    # 6 industry
    ws = wb.add_worksheet('6.下游产业')
    ws.set_column('A:A', 24); ws.set_column('B:B', 16); ws.set_column('C:C', 70); ws.set_column('D:D', 38)
    ws.write('A1', '下游应用与产业公开信息（【产业公开信息】，非销量预测）', T)
    for i, c in enumerate(['项目', '市场', '内容', '来源']):
        ws.write(3, i, c, H)
    for i, it in enumerate(cfg.get('industry', [])):
        r = 4 + i
        ws.write(r, 0, it.get('item', ''), TXT); ws.write(r, 1, it.get('market', ''), TXT)
        ws.write(r, 2, it.get('content', ''), TXT); ws.write(r, 3, it.get('source', ''), TXT)

    # 7 gaps
    ws = wb.add_worksheet('7.数据缺口')
    ws.set_column('A:A', 24); ws.set_column('B:B', 62); ws.set_column('C:C', 40)
    ws.write('A1', '数据缺口（不得补造）', T)
    for i, c in enumerate(['缺口', '说明', '处理方式']):
        ws.write(3, i, c, H)
    gaps = []
    cov = meta.get('coverage', {})
    if cov:
        ns = [(int(y), v.get('reporters_with_data', 0)) for y, v in cov.items()]
        ns.sort()
        if ns and ns[0][1] and ns[-1][1] < ns[0][1] * 0.9:
            gaps.append(('近年报告国覆盖下降', f"{ns[0][0]} 年 {ns[0][1]} 个报告国 → {ns[-1][0]} 年 {ns[-1][1]} 个", '合计值跨年比较需谨慎；决策以完整年度为准'))
    for m in markets:
        missing = [y for y in years if m['series_usd'].get(y) is None]
        if missing:
            gaps.append((f"{m['name']} 年度缺失", f"缺 {', '.join(map(str, missing))}", '显示为空白，不插值'))
    for t in cfg.get('tariffs', []):
        if t.get('status') != 'verified':
            gaps.append((f"{t.get('country')} 关税未核验", t.get('source', ''), '补齐后方可用于报价'))
    if not prow:
        gaps.append(('来源国明细缺失', '未运行 --partners', '补充拉取后更新"3.竞争来源国"'))
    for i, (a_, b_, c_) in enumerate(gaps[:120]):
        ws.write(4 + i, 0, a_, WARN); ws.write(4 + i, 1, b_, TXT); ws.write(4 + i, 2, c_, TXT)
    if not gaps:
        ws.write(4, 0, '未发现结构性缺口', OK)

    # 8 sources
    ws = wb.add_worksheet('8.来源清单')
    ws.set_column('A:A', 26); ws.set_column('B:B', 76); ws.set_column('C:C', 20); ws.set_column('D:D', 42)
    ws.write('A1', '来源清单（可溯源）', T)
    for i, c in enumerate(['来源', 'URL / 调用方式', '取数时间', '用途']):
        ws.write(3, i, c, H)
    srcs = meta.get('sources') or []
    srcs = list(srcs) + [{'name': 'UN Comtrade preview API',
                          'url': 'https://comtradeapi.un.org/public/v1/preview/C/A/HS',
                          'time': meta.get('fetched_at', ''),
                          'use': f"HS {hs6} 进口额/净重/来源国"}]
    for i, s in enumerate(srcs):
        r = 4 + i
        ws.write(r, 0, s.get('name', ''), TXT); ws.write(r, 1, s.get('url', ''), TXT)
        ws.write(r, 2, s.get('time', ''), TXT); ws.write(r, 3, s.get('use', ''), TXT)

    wb.close()
    return out_path


def main():
    ap = argparse.ArgumentParser(description='Build HTML report + Excel workbook from fetched trade data.')
    ap.add_argument('--data', required=True, help='data dir produced by fetch_trade.py')
    ap.add_argument('--config', required=True, help='product/analysis config JSON')
    ap.add_argument('--out', default='out', help='output dir')
    ap.add_argument('--min-usd', type=float, default=20e6,
                    help='ignore markets below this latest-year import value (default 20e6)')
    ap.add_argument('--basename', default=None, help='output file base name')
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding='utf-8'))
    rows, prow, meta = load(a.data)
    markets, years = build_markets(rows, prow, a.min_usd)
    glist = []
    for y in years:
        sub = [r for r in rows if r['year'] == y]
        glist.append({'year': y, 'n': len(sub),
                      'usd': sum(r['import_usd'] for r in sub),
                      'cn': sum(r['origin_usd'] for r in sub)})
    os.makedirs(a.out, exist_ok=True)
    base = a.basename or f"{cfg.get('product', {}).get('name', 'product')}_出口目标市场分析"
    hp = os.path.join(a.out, base + '.html')
    xp = os.path.join(a.out, base + '.xlsx')
    html_out = html_report(markets, years, cfg, meta, glist)
    probs = validate_js(html_out)
    if probs:
        print('WARNING: inline JavaScript failed syntax check:', file=sys.stderr)
        for p in probs:
            for line in p:
                print('   ', line, file=sys.stderr)
        print('   The report may render blank. Fix the data literal (usually an apostrophe in a country name).',
              file=sys.stderr)
    open(hp, 'w', encoding='utf-8').write(html_out)
    xlsx_report(markets, rows, prow, years, cfg, meta, xp)
    print('OK html :', hp, os.path.getsize(hp), 'bytes')
    print('OK xlsx :', xp, os.path.getsize(xp), 'bytes')
    print(f'markets ranked: {len(markets)}  years: {years[0]}-{years[-1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
