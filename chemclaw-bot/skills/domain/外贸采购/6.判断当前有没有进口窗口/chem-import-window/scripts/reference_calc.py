#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reference_calc.py — 与 JS 引擎**完全独立**的 Python 基准实现。

用途：交叉校验。若 JS 引擎与 Python 基准结果不一致，必有一方算错。
故意不复用任何 JS 代码，公式按 references/cost-formulas.md 逐行手写。

用法:
    python scripts/reference_calc.py <case.json>              # 打印结果
    python scripts/reference_calc.py <case.json> --json       # JSON 输出
    python scripts/reference_calc.py <case.json> --date 2026-10-16 --fx 6.6862
"""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def get(d, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def tax_profile_on(tax, date):
    """按生效日取税率版本；早于所有版本则返回 None（不倒推）。"""
    profs = [p for p in (tax.get('profiles') or []) if p.get('effective_from') and p['effective_from'] <= date]
    if not profs:
        return None
    return sorted(profs, key=lambda p: p['effective_from'])[-1]


def fx_on_date(rows, date):
    """精确匹配，不插值。"""
    for r in rows or []:
        if r['date'] == date:
            return float(r['rate'])
    return None


def domestic_on_date(case, date):
    """取当日国内现货价。

    优先级：历史序列里该日的点 > 基准日就是该日时的基准价。
    历史序列「已经存在」但不含该日 → 视为缺（序列是权威的，不能拿基准价顶替）。
    历史序列根本不存在 → 退回基准价（单点案例的常态）。
    """
    hist = case.get('domestic_hist') or {}
    rows = hist.get('rows') or []
    for r in rows:
        if r['date'] == date:
            return float(r['price_cny'])
    return None


def compute(case, date=None, quote=None, fx_rate=None, freight_usd=None,
            domestic=None, duty_rate=None, vat_rate=None, inland=None,
            vat_recoverable=None, insurance_rate=None):
    """按 references/cost-formulas.md 计算一天的进口成本与价差。"""
    quote = quote or case['quote']
    date = date or case.get('asof', {}).get('date') or quote['date']

    if quote is case['quote'] and quote.get('date') != date:
        # 指定了日期却没有指定当日报价：从历史报价里找，找不到就阻断
        hit = None
        for q in case.get('quotes_hist') or []:
            if q['date'] == date:
                hit = q
                break
        if hit is None:
            return {'date': date, 'ok': False, 'blockers': ['缺当日海外报价']}
        quote = hit

    out = {'date': date, 'ok': False, 'blockers': []}

    price = quote.get('price_usd')
    term = str(quote.get('term', '')).upper()
    if price is None:
        out['blockers'].append('无报价')
        return out
    if term not in ('FOB', 'CFR', 'CIF', 'EXW', 'DDP'):
        out['blockers'].append('贸易术语不可识别')

    # 汇率
    if fx_rate is None:
        fx_amount = fx_on_date(case.get('fx', {}).get('rows'), date)
    else:
        fx_amount = float(fx_rate)
    if fx_amount is None:
        out['blockers'].append('缺当日汇率')
    out['fx'] = fx_amount

    # 税率
    tp = tax_profile_on(case.get('tax', {}), date) or {}
    dr = float(duty_rate if duty_rate is not None else tp.get('duty_rate', 0) or 0)
    vr = float(vat_rate if vat_rate is not None else tp.get('vat_rate', 0) or 0)
    if 'duty_rate' not in tp and duty_rate is None:
        out['blockers'].append('缺关税税率')
    out['duty_rate'] = dr
    out['vat_rate'] = vr

    # 运费
    fr = 0.0
    freight_used = None
    quote_frt = quote.get('freight_usd')
    if freight_usd is not None:
        fr = float(freight_usd)
        freight_used = {'usd': fr, 'basis': 'override'}
    elif quote_frt is not None:
        fr = float(quote_frt)
        freight_used = {'usd': fr, 'basis': 'quote'}
    else:
        fcfg = case.get('freight') or {}
        if fcfg.get('usd_per_ton') is not None:
            fr = float(fcfg['usd_per_ton'])
            freight_used = {'usd': fr, 'basis': fcfg.get('basis') or 'external'}
    out['freight'] = freight_used

    premium = float(quote.get('premium_usd') or 0)
    base = price + premium

    # 保险
    if insurance_rate is not None:
        ins_r = float(insurance_rate) / 100.0
    else:
        ins_cfg = case.get('insurance') or {}
        ins_r = float(ins_cfg['rate']) / 100.0 if ins_cfg.get('rate') is not None else None

    if term == 'CIF':
        cif = base
        insurance = 0.0
    elif term == 'CFR':
        if ins_r is None:
            insurance = 0.0
            cif = base
        else:
            cif = base / (1 - ins_r * 1.1)
            insurance = cif - base
    else:  # FOB / EXW
        if freight_used is None:
            out['blockers'].append('FOB 缺运费，不可折算')
            return out
        cfr = base + fr
        if ins_r is None:
            insurance = 0.0
            cif = cfr
        else:
            cif = cfr / (1 - ins_r * 1.1)
            insurance = cif - cfr

    out['cfr_usd'] = base + (fr if term in ('FOB', 'EXW') else 0.0)
    out['insurance_usd'] = insurance
    out['cif_usd'] = cif

    if out['blockers']:
        return out

    # 人民币完税与税费
    adj_rate = case.get('params', {}).get('dutiable_adjust_rate') or 0
    adj = cif * float(adj_rate) / 100.0
    dutiable = (cif + adj) * fx_amount
    duty = dutiable * dr / 100.0
    vat = (dutiable + duty) * vr / 100.0

    if inland is not None:
        inl = float(inland)
    else:
        inl = case.get('params', {}).get('inland_cost_cny')
        inl = float(inl) if inl is not None else 0.0
    other = float(case.get('params', {}).get('other_cost_cny') or 0)

    if vat_recoverable is None:
        vat_recoverable = case.get('params', {}).get('vat_recoverable', True)
    vat_cost = 0.0 if vat_recoverable else vat

    net_cost = dutiable + duty + inl + other + vat_cost
    gross_cost = dutiable + duty + vat + inl + other

    out.update({
        'dutiable_cny': dutiable,
        'duty': duty,
        'vat': vat,
        'inland': inl,
        'other': other,
        'net_cost': net_cost,
        'gross_cost': gross_cost,
        'vat_recoverable': bool(vat_recoverable),
    })

    # 国内现货
    if domestic is None:
        dom_val = domestic_on_date(case, date)
        dom_date = date
        if dom_val is None and date == case.get('quote', {}).get('date') \
                and not (case.get('domestic_hist') or {}).get('rows'):
            # 单点案例（无历史序列）：基准国内价即当日价
            dom_val = case.get('domestic', {}).get('price_cny')
            dom_val = float(dom_val) if dom_val is not None else None
    else:
        dom_val = domestic
        dom_date = date
    out['domestic'] = dom_val
    out['domestic_date'] = dom_date

    if dom_val is not None:
        out['spread'] = dom_val - net_cost
        out['spread_pct'] = (dom_val - net_cost) / dom_val * 100.0 if dom_val else None
    else:
        out['spread'] = None
        out['spread_pct'] = None
        if out.get('domestic') is None:
            out['note'] = '缺当日国内现货价，仅给出进口成本'
    out['ok'] = True
    return out


def main():
    case_path = sys.argv[1]
    case = json.load(open(case_path, encoding='utf-8'))
    kwargs = {}
    argv = sys.argv[2:]
    for flag, key, cast in (('--date', 'date', str), ('--fx', 'fx_rate', float),
                            ('--freight', 'freight_usd', float), ('--domestic', 'domestic', float),
                            ('--duty', 'duty_rate', float)):
        if flag in argv:
            kwargs[key] = cast(argv[argv.index(flag) + 1])

    r = compute(case, **kwargs)
    if '--json' in argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r['ok'] else 1

    print('日期 %s ｜ 术语 %s' % (r['date'], case['quote']['term']))
    if r['blockers']:
        print('不可计算: ' + '；'.join(r['blockers']))
        return 1
    print('  CIF        %10.4f USD/吨' % r['cif_usd'])
    print('  汇率        %10.4f' % r['fx'])
    print('  完税价格    %10.2f 元/吨' % r['dutiable_cny'])
    print('  关税        %10.2f 元/吨 (%.2f%%)' % (r['duty'], r['duty_rate']))
    print('  进口增值税  %10.2f 元/吨 (%.0f%%, %s)' % (r['vat'], r['vat_rate'],
                                                       '可抵扣' if r['vat_recoverable'] else '不可抵扣'))
    print('  境内费用    %10.2f 元/吨' % (r['inland']))
    print('  ----')
    print('  进口含税净成本 %8.2f 元/吨' % r['net_cost'])
    if r['domestic'] is None:
        print('  国内现货       缺当日价格（不生成价差）')
    else:
        print('  国内现货       %8.2f 元/吨' % r['domestic'])
        print('  理论价差       %8.2f 元/吨' % (r['spread'] or 0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
