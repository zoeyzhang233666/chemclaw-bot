#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成本模型引擎：把"研究输入 JSON"算成"可交付的结果 JSON"。

与产品无关。所有公式集中在 references/formulas.md，本模块是唯一实现，HTML/Excel/报告共用同一套结果。
一旦 HTML 里自己再算一遍，就会分叉 —— 所以 HTML 拿到的只有本模块算好的数与原始输入。

公式（完整推导见 references/formulas.md）
------------------------------------------
单位产品理论原料成本  C = Σ_i ( q_i × p_i )
单项成本              c_i = q_i × p_i
单项占比              w_i = c_i / C × 100%
单项价格变动影响      Δc_i = q_i × Δp_i = q_i × p_i × r_i
组合情景              C' = Σ_i q_i × p_i × (1 + r_i) ； ΔC = C' - C
贡献分解（历史→当期） ΔC_total = Σ_i Δc_i ；各 i 贡献 = Δc_i / ΔC_total
"""
import math

import units
from units import Unresolvable

LEVEL_NAMES = {
    'enterprise': '企业实测',
    'eia': '环评/公参文件',
    'patent': '专利实施例',
    'standard': '标准/规范',
    'government': '政府/官方文件',
    'assoc': '行业协会/机构',
    'textbook': '教材/设计书',
    'research': '券商/研究机构',
    'media': '媒体/资讯',
    'user': '用户提供',
    'simulated': '模拟参数',
    'none': '无来源',
}
LEVEL_RANK = {'user': 0, 'enterprise': 1, 'eia': 2, 'patent': 2, 'standard': 2,
              'government': 2, 'assoc': 3, 'textbook': 4, 'research': 4,
              'media': 5, 'simulated': 8, 'none': 9}


# --------------------------------------------------------------------------- 基础
def _f(x, d=0.0):
    try:
        if x is None or x == '':
            return d
        return float(x)
    except (TypeError, ValueError):
        return d


def scenario_rates(cfg, n):
    """情景的"幅度序列"（百分比，1/5/10 等）。ratios 若给 percentages 则换算成小数。"""
    out = []
    if not cfg:
        return out
    for s in cfg.get('amplitude_series', []):
        label = None
        if isinstance(s, dict):
            label = s.get('label')
            if 'ratio' in s:
                v = _f(s['ratio'])
            else:
                pct = _f(s.get('pct', s.get('percent')))
                v = pct / 100.0
        else:
            pct = _f(s)
            v = pct / 100.0
        out.append({'label': label or _pct_label(v), 'ratio': v})
    return out


def _pct_label(r):
    v = r * 100.0
    s = ('%+.2f' % v).rstrip('0').rstrip('.')
    return s + '%'


def describe_params(P):
    """单耗口径说明（用于页面与 Excel 的"这是哪一层口径"提示）。"""
    basis = P.get('basis', 'net')
    r = {
        'net': '净单耗（已扣回收、含转化/收率/副反应损失）',
        'apparent': '表观投料（不扣回收）',
        'theoretical': '理论单耗（100% 转化、100% 收率）',
    }.get(basis, basis)
    return r


# --------------------------------------------------------------------------- 原料口径
def resolve_material(m, meta, fx):
    """把单条原料输入解析成标准化记录（统一 t/t 与 ￥/t 含税）。

    返回 dict，含 _errors（致命）/_warns（提示）/ _blocked（无法计算的原料）。
    """
    out = {'id': m.get('id'), 'name': m.get('name'), 'cas': m.get('cas'),
           'role': m.get('role', 'main'), 'spec': m.get('spec'),
           'region': m.get('region'), 'delivery': m.get('delivery'),
           'tax_included': m.get('tax_included'),
           'errors': [], 'warns': [], 'price_steps': [], 'dosage_steps': []}
    target_tax = (meta.get('target_tax_basis') or 'tax_included') == 'tax_included'
    out['tax_label'] = '含税' if target_tax else '不含税'

    # ---- 单耗
    q = None
    dosage = m.get('dosage') or {}
    if isinstance(dosage, (int, float)) or (isinstance(dosage, str) and dosage.strip()):
        dosage = {'value': dosage, 'unit': 't/t'}
    src = dosage.get('source', 'none')
    out['dosage_source'] = src
    out['dosage_source_label'] = LEVEL_NAMES.get(src, src)
    out['dosage_ref'] = dosage.get('ref') or dosage.get('note') or ''
    out['dosage_scope'] = dosage.get('scope') or ''
    try:
        if dosage.get('value') is None:
            raise Unresolvable('单耗缺失（dosage.value 为空）')
        q = units.dosage_to_t_per_t(dosage['value'], dosage.get('unit', 't/t'))
        out['dosage_unit_in'] = dosage.get('unit', 't/t')
        out['dosage_raw'] = _f(dosage['value'])
        out['dosage_steps'].append({
            'label': '单耗单位统一',
            'calc': '%g %s → t/t' % (out['dosage_raw'], out['dosage_unit_in']),
            'value': q})
    except (Unresolvable, ValueError) as e:
        out['errors'].append(str(e))
    out['dosage'] = q

    # ---- 价格
    p = None
    out['price'] = None
    price = m.get('price') or {}
    if isinstance(price, (int, float)):
        price = {'value': price, 'unit': 'CNY/t'}
    if not price or price.get('value') in (None, ''):
        out['price_blocked'] = True
        out['warns'].append('价格缺失：该原料成本无法计入（不按 0 处理，单列为缺口）')
    else:
        pu = price.get('unit', 'CNY/t')
        ti = price.get('tax_included', True)
        out['price_spec'] = price.get('spec', out['spec'])
        out['price_region'] = price.get('region', out['region'])
        out['price_delivery'] = price.get('delivery', out['delivery'])
        out['price_unit_in'] = pu
        out['price_date'] = price.get('date')
        out['price_source'] = price.get('source_ref') or price.get('source') or ''
        out['price_raw'] = _f(price['value'])
        try:
            r = units.price_to_cny_per_t(price['value'], pu, fx_usd_cny=fx, tax_included=ti,
                                         target_tax_included=target_tax,
                                         tax_rate_note=(('用户给定税率 %s' % (meta.get('vat_rate_note') or '13%'))
                                                        if not meta.get('vat_rate_note') else meta.get('vat_rate_note')))
            p = r['value']
            out['price_steps'] = r['factors']
            out['price_tax_in'] = '含税' if ti else '不含税'
        except Unresolvable as e:
            out['price_blocked'] = True
            out['warns'].append('价格口径无法统一：%s —— 该原料成本无法计入' % e)
        out['price'] = p
        out['price_orig_tax'] = '含税' if ti else '不含税'

    # ---- 成本
    if q is not None and p is not None:
        out['cost'] = q * p
    else:
        out['cost'] = None
    return out


# --------------------------------------------------------------------------- 历史序列
def _to_float(x):
    if x is None or x == '':
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def series_map(rows):
    """rows: [{'date':'YYYY-MM-DD','value':x}] -> {date: value}（保留 None 作为缺口）。"""
    d = {}
    for r in rows or []:
        dt = (r.get('date') or '').strip()
        if len(dt) < 10:
            continue
        dt = dt[:10]
        v = _to_float(r.get('value', r.get('price')))
        d[dt] = v
    return d


def build_history(H, blend, meta):
    """把多条价格序列按"当期单耗 × 历史价格"合成历史理论原料成本。

    blend: [{'date':..., 'q': {mid: dosage}, 'basis': 'fixed_nominal'|'applied_research'|'fixed_q0'}]
    返回: {'rows':[{date, cost, items:{mid:c}}], 'gaps':[...], 'coverage':...}
    """
    if not H:
        return {'rows': [], 'gaps': [], 'materials': [], 'reference_series': [],
                'offsets_pct': {}, 'coverage': {'series': []}}
    offsets = H.get('offsets_pct', {}) or {}
    mats = H.get('materials') or []
    smaps = {}
    sfields = []
    for m in mats:
        mid = m.get('material_id')
        mp = series_map(m.get('rows'))
        smaps[mid] = mp
        sfields.append({
            'material_id': mid, 'name': m.get('name'),
            'source': m.get('source'), 'source_url': m.get('source_url'),
            'spec': m.get('spec'), 'region': m.get('region'), 'tax_included': m.get('tax_included'),
            'freq': m.get('freq'), 'unit': m.get('unit', 'CNY/t'),
            'covered_from': min(mp) if mp else None, 'covered_to': max(mp) if mp else None,
            'n_points': sum(1 for v in mp.values() if v is not None),
            'n_gap': sum(1 for v in mp.values() if v is None),
        })

    # 共同日期轴：取所有序列日期并集，只保留"每条序列都有该日（或可在该日之前取最后有效值）"的日子
    alldates = sorted({d for mp in smaps.values() for d in mp})
    if not alldates:
        return {'rows': [], 'gaps': [], 'coverage': {'series': sfields}}
    blend_by_date = {b['date']: b for b in blend or []}

    def last_val(mp, dt):
        if dt in mp and mp[dt] is not None:
            return mp[dt], False
        prev = [d for d in mp if d <= dt and mp[d] is not None]
        if not prev:
            return None, True
        return mp[max(prev)], True   # (值, 是否为承袭/回填)

    rows, gaps = [], []
    for dt in alldates:
        b = blend_by_date.get(dt)
        if not b:
            continue
        items = {}
        complete = True
        carried = []
        for mid, mp in smaps.items():
            q = (b.get('q') or {}).get(mid)
            v, carry = last_val(mp, dt)
            if v is None or q is None:
                complete = False
                items[mid] = None
                continue
            if carry:
                carried.append(mid)
            off = _f(offsets.get(mid), 0.0) / 100.0
            items[mid] = q * v * (1.0 + off)
        if not complete:
            gaps.append({'date': dt, 'why': '该日存在原料价格缺口，历史成本不完整'})
            rows.append({'date': dt, 'cost': None, 'items': items, 'incomplete': True})
        else:
            rows.append({'date': dt, 'cost': sum(items.values()), 'items': items,
                         'incomplete': False, 'carried': carried})

    return {'rows': rows, 'gaps': gaps,
            'materials': [{'material_id': m.get('material_id'), 'name': m.get('name'),
                           'source': m.get('source'), 'source_url': m.get('source_url'),
                           'spec': m.get('spec'), 'region': m.get('region'),
                           'tax_included': m.get('tax_included'), 'freq': m.get('freq'),
                           'unit': m.get('unit', 'CNY/t'),
                           'rows': m.get('rows') or []} for m in mats],
            'reference_series': [{'name': r.get('name'), 'source': r.get('source'),
                                  'source_url': r.get('source_url'), 'spec': r.get('spec'),
                                  'region': r.get('region'), 'tax_included': r.get('tax_included'),
                                  'unit': r.get('unit', 'CNY/t'), 'note': r.get('note'),
                                  'rows': r.get('rows') or []}
                                 for r in (H.get('reference_series') or [])],
            'offsets_pct': offsets,
            'coverage': {'series': sfields, 'from': alldates[0], 'to': alldates[-1],
                         'n_days': len(alldates)}}


def period_stats(rows, current_date=None):
    """按口径计算 30天/3个月/1年/3年 的成本变化（用真实日历回溯）。

    每个窗口：(P_start, P_end, Δ, Δ%)  —— P_start 取 <= 窗口起点 的最近一条有效日期。
    """
    val = [(r['date'], r['cost']) for r in rows if r.get('cost') is not None]
    if not val:
        return []
    end_date = current_date or val[-1][0]

    import datetime as _dt
    def _d(s):
        return _dt.date.fromisoformat(s)
    end = _d(end_date)
    windows = [('30天', 30), ('3个月', 91), ('1年', 365), ('3年', 1095)]
    out = []
    for label, ndays in windows:
        start = end - _dt.timedelta(days=ndays)
        # 起点：<= start 的最后一条；若没有，则记为缺口（不插值）
        c_start = None
        for ds, c in reversed(val):
            if _d(ds) <= start:
                c_start = (ds, c)
                break
        if c_start is None:
            out.append({'label': label, 'days': ndays, 'status': 'gap',
                        'why': '该窗口起点早于可得数据（%s 起），无法计算，未做插值/补数' % val[0][0],
                        'start_date': None, 'start': None, 'end_date': val[-1][0], 'end': val[-1][1],
                        'delta': None, 'pct': None})
            continue
        c_end = val[-1]
        d = c_end[1] - c_start[1]
        out.append({'label': label, 'days': ndays, 'status': 'ok',
                    'start_date': c_start[0], 'start': c_start[1],
                    'end_date': c_end[0], 'end': c_end[1],
                    'delta': d, 'pct': (d / c_start[1] * 100.0) if c_start[1] else None})
    return out


# --------------------------------------------------------------------------- 主计算
def compute(data):
    """主入口。data = 研究输入 JSON（见 references/data-contract.md）。返回结果对象。"""
    meta = data.get('meta') or {}
    P = data.get('process_params') or {}
    fx = (data.get('fx') or {}).get('usd_cny')
    mats_in = [m for m in (data.get('materials') or []) if m.get('enabled', True) is not False]

    resolved = [resolve_material(m, meta, fx) for m in mats_in]
    main = [r for r in resolved if r.get('role') != 'aux']
    aux = [r for r in resolved if r.get('role') == 'aux']
    computable = [r for r in resolved if r.get('cost') is not None]
    blocked = [r for r in resolved if r.get('cost') is None]
    total = sum(r['cost'] for r in computable)

    # 每一行的占比
    for r in computable:
        r['share'] = (r['cost'] / total * 100.0) if total else None
    # 主辅料分开的合计
    total_main = sum(r['cost'] for r in computable if r.get('role') != 'aux')
    total_aux = sum(r['cost'] for r in computable if r.get('role') == 'aux')

    # ---- 敏感性矩阵（逐项 ±幅度）
    rates = scenario_rates(data.get('scenario_config'), len(mats_in))
    sens = []
    for r in computable:
        row = {'material_id': r['id'], 'name': r['name'], 'q': r['dosage'], 'p': r['price'],
               'cost': r['cost'], 'share': r['share'], 'cells': []}
        for s in rates:
            dp = r['price'] * s['ratio']
            dc = r['dosage'] * dp
            row['cells'].append({'label': s['label'], 'ratio': s['ratio'],
                                 'price_delta': dp, 'cost_delta': dc,
                                 'new_cost': r['cost'] + dc,
                                 'new_total': total + dc,
                                 'new_total_pct': (dc / total * 100.0) if total else None})
        sens.append(row)

    # ---- 组合情景
    combos = []
    for c in (data.get('combo_scenarios') or []):
        ch = (c.get('changes') or {})
        applied, new = {}, 0.0
        ok = True
        why = []
        for r in computable:
            rr = _f(ch.get(r['id']), 0.0) / 100.0
            if r['id'] in ch:
                applied[r['id']] = rr
            new += r['dosage'] * r['price'] * (1.0 + rr)
        for b in blocked:
            if b['id'] in ch:
                ok = False
                why.append('%s 缺价格，组合情景无法完整计算' % b['name'])
        for k in ch:
            if k not in [r['id'] for r in computable]:
                why.append('未知原料 id：%s（已忽略）' % k)
        by_mat = []
        for r in computable:
            rr = applied.get(r['id'], 0.0)
            by_mat.append({'material_id': r['id'], 'name': r['name'], 'ratio_pct': rr * 100.0,
                           'old': r['cost'], 'new': r['dosage'] * r['price'] * (1.0 + rr),
                           'delta': r['dosage'] * r['price'] * rr})
        combos.append({'id': c.get('id'), 'name': c.get('name'), 'changes': ch,
                       'old_total': total, 'new_total': new, 'delta': new - total,
                       'delta_pct': ((new - total) / total * 100.0) if total else None,
                       'complete': ok, 'notes': why, 'by_material': by_mat})

    # ---- 自动组合（全涨 / 全跌）—— 只做"同步同幅"这一种透明口径
    auto = []
    names = [r['name'] for r in computable]
    for s in rates:
        r_ = s['ratio']
        new = sum(x['dosage'] * x['price'] * (1.0 + r_) for x in computable)
        auto.append({'label': '全部原料同步 %s' % s['label'], 'ratio': r_,
                     'delta': new - total, 'new_total': new,
                     'delta_pct': ((new - total) / total * 100.0) if total else None,
                     'desc': '、'.join(names) + ' 同步变动' if names else ''})

    # ---- 单耗变化对成本的影响（把 q_i 上调 1%）
    dosage_sens = []
    for r in computable:
        d = 0.01 * r['dosage'] * r['price']
        dosage_sens.append({'material_id': r['id'], 'name': r['name'],
                            'delta_1pct': d, 'delta_pct_of_total': (d / total * 100.0) if total else None})

    # ---- 历史
    H = data.get('history') or {}
    hist = build_history(H, H.get('blend') or [], meta)
    periods = period_stats(hist['rows'], H.get('as_of') or None)

    # ---- 贡献分解
    contrib = []
    if periods:
        for p in periods:
            if p['status'] != 'ok':
                contrib.append({'period': p['label'], 'status': 'gap', 'why': p['why'], 'items': []})
                continue
            sd = [r for r in hist['rows'] if r['date'] == p['start_date']]
            ed = [r for r in hist['rows'] if r['date'] == p['end_date']]
            if not sd or not ed:
                contrib.append({'period': p['label'], 'status': 'gap', 'why': '端点无完整数据', 'items': []})
                continue
            s_items, e_items = sd[0]['items'], ed[0]['items']
            tot = p['delta']
            its = []
            for r in computable:
                a = s_items.get(r['id'])
                b = e_items.get(r['id'])
                if a is None or b is None:
                    continue
                d = b - a
                its.append({'material_id': r['id'], 'name': r['name'],
                            'start': a, 'end': b, 'delta': d,
                            'share_of_change': (d / tot * 100.0) if abs(tot) > 1e-9 else None})
            its.sort(key=lambda x: -abs(x['delta']))
            contrib.append({'period': p['label'], 'status': 'ok', 'start_date': p['start_date'],
                            'end_date': p['end_date'], 'total_delta': tot, 'items': its})

    # ---- 期间均价（真实均值，仅用于"近30天/3个月均价"这类描述，不外推）
    avg = []
    import datetime as _dt
    valrows = [r for r in hist['rows'] if r.get('cost') is not None]
    for label, ndays in (('近30天', 30), ('近3个月', 91)):
        if not valrows:
            avg.append({'label': label, 'status': 'gap', 'why': '无历史数据'})
            continue
        end = _dt.date.fromisoformat(valrows[-1]['date'])
        st = end - _dt.timedelta(days=ndays)
        sel = [r for r in valrows if _dt.date.fromisoformat(r['date']) >= st]
        if len(sel) < 2:
            avg.append({'label': label, 'status': 'gap', 'why': '窗口内数据不足'})
            continue
        avg.append({'label': label, 'status': 'ok', 'n': len(sel),
                    'avg': sum(r['cost'] for r in sel) / len(sel),
                    'min': min(r['cost'] for r in sel), 'max': max(r['cost'] for r in sel),
                    'from': sel[0]['date'], 'to': sel[-1]['date']})

    # ---- 数据质量 / 缺口清单
    gaps = []
    for b in blocked:
        gaps.append({'type': 'price', 'item': b['name'], 'detail': '；'.join(b['warns']),
                     'impact': '该原料未计入理论原料成本；总成本仅覆盖已计价原料，口径为"部分覆盖"',
                     'fix': '补充同规格/同区域/同税口径的现货价（含数据日期与来源）'})
    for r in resolved:
        if r.get('dosage_source') in ('simulated', 'none') and r.get('cost') is not None:
            gaps.append({'type': 'dosage', 'item': r['name'],
                         'detail': '单耗来源为%s' % r['dosage_source_label'],
                         'impact': '成本金额的可信度受限于该参数，不能当作企业实际单耗',
                         'fix': '用企业内部台账/ERP 消耗数据替换'})
    for g in (H.get('gaps') or []):
        gaps.append({'type': 'history', 'item': g.get('field') or g.get('item') or '历史序列',
                     'detail': g.get('detail') or g.get('why') or '', 'impact': g.get('impact', ''),
                     'fix': g.get('fix', '')})
    for p in periods:
        if p['status'] == 'gap':
            gaps.append({'type': 'history_window', 'item': p['label'], 'detail': p['why'],
                         'impact': '该时间窗的理论成本变化不展示为数字', 'fix': '接入更长历史价格源（付费终端/自采积累）'})

    # ---- 未纳入成本项
    not_included = data.get('not_included') or []
    unquantified = data.get('unquantified') or []

    # ---- 副产品抵扣（若用户提供）
    byprod = data.get('byproducts') or []

    return {
        'meta': meta,
        'params': {
            'basis': P.get('basis', 'net'),
            'basis_label': describe_params(P),
            'yield_basis': P.get('yield_basis') or '以主要原料计的成品收率',
            'yield_pct': P.get('yield_pct'),
            'conversion_pct': P.get('conversion_pct'),
            'recycle_pct': P.get('recycle_pct'),
            'notes': P.get('notes') or '',
        },
        'materials': resolved,
        'main_count': len(main),
        'aux_count': len(aux),
        'total_main': total_main,
        'total_aux': total_aux,
        'total': total,
        'coverage': {
            'n_all': len(resolved), 'n_computable': len(computable),
            'n_blocked': len(blocked), 'complete': len(blocked) == 0,
        },
        'sensitivity': sens,
        'rates': [{'label': s['label'], 'ratio': s['ratio']} for s in rates],
        'combos': combos,
        'auto_combos': auto,
        'dosage_sens': dosage_sens,
        'history': hist,
        'periods': periods,
        'contribution': contrib,
        'averages': avg,
        'gaps': gaps,
        'not_included': not_included,
        'unquantified': unquantified,
        'byproducts': byprod,
        'price_basis': {'target': meta.get('target_tax_basis', 'tax_included'),
                        'label': '含税' if (meta.get('target_tax_basis') or 'tax_included') == 'tax_included' else '不含税',
                        'fx_usd_cny': fx},
    }
