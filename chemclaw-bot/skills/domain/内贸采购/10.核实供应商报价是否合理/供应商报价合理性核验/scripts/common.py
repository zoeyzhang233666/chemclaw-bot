# -*- coding: utf-8 -*-
"""供应商报价核验 —— 公共库（品种无关）。

所有品种相关的数字（税率、运费、包装加价、含量口径、年度锚点、事件）都来自
specs/<产品族>.json 与 research.json，本文件不出现任何具体品种的系数。
"""
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_DIR = os.path.join(ROOT, 'specs')


# ---------------------------------------------------------------- IO
def load_json(path):
    with open(path, encoding='utf-8-sig') as f:   # utf-8-sig：容忍用记事本/Excel 保存带来的 BOM
        return json.load(f)


def dump_json(obj, path):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def load_spec(name):
    """name: 规格文件名（不含 .json）、skill 内相对路径、或绝对/相对路径。"""
    cands = []
    for raw in (name, name.replace('/', os.sep)):
        cands.append(raw)
        if not os.path.isabs(raw):
            cands.append(os.path.join(ROOT, raw))
    cands += [os.path.join(SPEC_DIR, name + '.json'), os.path.join(SPEC_DIR, os.path.basename(name))]
    for p in cands:
        if os.path.exists(p):
            return load_json(p)
    raise SystemExit('找不到规格文件：%s（已找过：%s）' % (name, '; '.join(cands)))


# ---------------------------------------------------------------- 数值
def num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(',', '').replace('，', '').strip()
    out, cur = '', ''
    for ch in s:
        if ch.isdigit() or ch == '.':
            cur += ch
        elif ch == '-' and not cur and not out:
            out = '-'
        elif cur:
            out += cur
            cur = ''
    out += cur
    try:
        return float(out)
    except ValueError:
        return None


def fmt(n, d=2):
    if n is None:
        return '—'
    return format(round(float(n), d), ',.%df' % d)


def pct(n, d=2):
    if n is None:
        return '—'
    return ('+' if n > 0 else '') + ('%.' + str(d) + 'f%%') % n


def rnd(n, d=2):
    return None if n is None else round(float(n), d)


# ---------------------------------------------------------------- 报价标准化
UNIT_FACTORS = {'元/吨': 1.0, '元每吨': 1.0, '人民币元/吨': 1.0, 'yuan/t': 1.0, 'CNY/t': 1.0,
                '元/公斤': 1000.0, '元/kg': 1000.0, '元/千克': 1000.0, '元/克': 1e6, 'USD/t': None}


def to_yuan_per_ton(value, unit):
    f = UNIT_FACTORS.get(unit)
    if f is None:
        raise ValueError('无法识别的单位：%s（外币或特殊单位请先换算成元/吨再录入）' % unit)
    return value * f


def target_key(tax, delivery):
    """统一成 tax|delivery 四靶心：included/excluded + ex_works/delivered"""
    t = 'included' if tax in ('含税', 'included', 'incl', True) else 'excluded'
    d = 'delivered' if delivery in ('到厂', 'delivered', '送到厂', '到库') else 'ex_works'
    return '%s|%s' % (t, d)


def standardize(quote, spec):
    """返回四个靶心 {key: {value, formula, gap_reason}}，元/吨。

    报价原始：value(元/吨) + tax + delivery + region + 可选 transport/credit/packing/quantity。
    """
    vat = float(spec.get('vat_rate', 0.13))
    price = to_yuan_per_ton(quote['value'], quote.get('unit', '元/吨'))
    tax0 = 'included' if quote.get('tax', {}).get('included', True) else 'excluded'
    deliv0 = 'delivered' if quote.get('delivery', {}).get('basis', 'ex_works') in ('delivered', '到厂') else 'ex_works'

    inc = price if tax0 == 'included' else price * (1 + vat)
    exc = price / (1 + vat) if tax0 == 'included' else price

    # 运费（元/吨）：只接受显式录入
    tr = quote.get('transport') or {}
    freight = num(tr.get('freight_per_ton'))
    freight_basis = tr.get('freight_basis')  # ex_works_to_delivered / delivered_to_ex_works
    if deliv0 == 'delivered':
        exw_inc = inc - freight if freight is not None else None
        exw_exc = exc - (freight / (1 + vat) if freight is not None else 0) if freight is not None else None
    else:
        exw_inc, exw_exc = inc, exc
    del_inc = exw_inc + freight if (exw_inc is not None and freight is not None) else (inc if deliv0 == 'delivered' else None)
    del_exc = exw_exc + (freight / (1 + vat) if (exw_exc is not None and freight is not None) else 0) if (exw_exc is not None and freight is not None) else (exc if deliv0 == 'delivered' else None)

    out = {
        'included|ex_works': {'value': rnd(exw_inc, 2),
                              'formula': ('含税出厂 = 原报价%s'
                                          % ('（报价即含税出厂）' if deliv0 == 'ex_works' and tax0 == 'included'
                                             else ''))},
        'excluded|ex_works': {'value': rnd(exw_exc, 2),
                              'formula': '不含税出厂 = 含税出厂 ÷ (1 + %.0f%%)' % (vat * 100)},
        'included|delivered': {'value': rnd(del_inc, 2),
                               'formula': '含税到厂 = 含税出厂 + 运费(TBD 元/吨)'},
        'excluded|delivered': {'value': rnd(del_exc, 2),
                               'formula': '不含税到厂 = 不含税出厂 + 运费 ÷ (1 + %.0f%%)' % (vat * 100)},
    }
    if freight is None:
        org = quote.get('origin') or (quote.get('delivery') or {}).get('origin') or '发运地'
        dst = quote.get('destination') or quote.get('region') or '到货地'
        for k in ('included|delivered', 'excluded|delivered'):
            out[k] = {'value': None, 'formula': out[k]['formula'],
                      'gap_reason': '未提供运价（%s → %s），不接受行业均运费顶替' % (org, dst)}
    for k in out:
        if out[k]['value'] is None and 'gap_reason' not in out[k]:
            out[k]['gap_reason'] = '缺运价或口径不明'

    # 账期/承兑折现（不覆盖原靶心，另给出「现款折算价」）
    credit = quote.get('credit') or {}
    fin_rate = num(credit.get('annual_rate'))
    term = num(credit.get('term_days')) or 0
    acc = num(credit.get('acceptance_discount_annual'))
    disc_val = None
    disc_formula = '未启用（现款或未提供资金成本）'
    if fin_rate and term:
        disc_val = round(price * (1 - fin_rate * term / 365.0), 2)
        disc_formula = '现款折算价 = 报价 × (1 − %.1f%% × %d/365) = %s' % (fin_rate * 100, term, fmt(disc_val))
    elif acc:
        disc_val = round(price * (1 - acc), 2)
        disc_formula = '承兑折算价 = 报价 × (1 − 承兑年化贴现 %.1f%%) = %s' % (acc * 100, fmt(disc_val))
    out['_meta'] = {'vat': vat, 'price_yuan_per_ton': price, 'tax0': tax0, 'delivery0': deliv0,
                    'freight': freight, 'credit_discounted_price': disc_val,
                    'credit_formula': disc_formula}
    return out


# ---------------------------------------------------------------- 偏离
def deviation(quote_value, anchor):
    """anchor: {center, low, high, interval_type}. 返回偏离结构与文案。"""
    c = num(anchor.get('center'))
    lo = num(anchor.get('low'))
    hi = num(anchor.get('high'))
    single = anchor.get('interval_type') == 'point' or lo == hi
    if quote_value is None or c is None:
        return {'comparable': False, 'reason': '缺少报价靶心或参考中枢'}
    d_center = quote_value - c
    r = {
        'quote': rnd(quote_value), 'center': rnd(c), 'low': rnd(lo), 'high': rnd(hi),
        'single_point': bool(single),
        'dev_center': rnd(d_center), 'dev_center_pct': rnd(d_center / c * 100, 2),
        'dev_low': rnd(quote_value - lo) if lo is not None else None,
        'dev_high': rnd(quote_value - hi) if hi is not None else None,
        'dev_low_pct': rnd((quote_value - lo) / lo * 100, 2) if lo else None,
        'dev_high_pct': rnd((quote_value - hi) / hi * 100, 2) if hi else None,
        'position_in_range': (None if (single or hi == lo) else rnd((quote_value - lo) / (hi - lo) * 100, 1)),
        'position_raw': (None if (single or hi == lo) else rnd((quote_value - lo) / (hi - lo) * 100, 1)),
        'position_clamped': (None if (single or hi == lo) else rnd(max(0.0, min(100.0, (quote_value - lo) / (hi - lo) * 100)), 1)),
        'outside': ('above' if (hi is not None and quote_value > hi) else
                    ('below' if (lo is not None and quote_value < lo) else 'inside')),
        'position_label': ('—（单点口径）' if (single or hi == lo) else
                           ('高于区间上沿' if quote_value > hi else
                            ('低于区间下沿' if quote_value < lo else
                             '区间内 %.1f%%' % ((quote_value - lo) / (hi - lo) * 100)))),
        'comparable': True,
    }
    return r


# ---------------------------------------------------------------- 分位
def percentile_of(series_values, x, decimals=1):
    """标准经验分位：P = (#<x + 0.5*#=x)/n*100。series_values 必须已是有效序列（已去重/已排序无所谓）。"""
    vals = [v for v in series_values if v is not None]
    n = len(vals)
    if n == 0:
        return None, 0
    below = sum(1 for v in vals if v < x)
    equal = sum(1 for v in vals if v == x)
    return round((below + 0.5 * equal) / n * 100, decimals), n


def window_stats(series, days, asof, min_points):
    """series: [{d, v}]，返回窗口统计或缺口。"""
    import datetime
    if not series:
        return {'ok': False, 'gap': '无序列'}
    asof_d = datetime.date.fromisoformat(asof)
    cut = (asof_d - datetime.timedelta(days=days)).isoformat()
    w = [p for p in series if p['d'] >= cut and p['d'] <= asof]
    if len(w) < min_points:
        return {'ok': False, 'gap': '窗口内有效样本 %d 个，少于 %d 个' % (len(w), min_points), 'n': len(w)}
    vs = [p['v'] for p in w]
    return {'ok': True, 'n': len(w), 'start': w[0]['d'], 'end': w[-1]['d'],
            'low': min(vs), 'high': max(vs), 'center': statistics.median(vs),
            'mean': round(statistics.mean(vs), 2)}


def fmt_date(d):
    return d
