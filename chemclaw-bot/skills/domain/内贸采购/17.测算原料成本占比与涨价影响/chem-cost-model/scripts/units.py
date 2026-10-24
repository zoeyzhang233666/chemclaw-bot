#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单位换算与价格口径统一（与产品无关，任何化工品通用）。

设计原则
--------
1. 所有"单耗"最终统一到  t_原料 / t_产品（kg 也接受，内部换成 t）。
2. 所有"价格"最终统一到  ￥/t（含税口径由调用方显式声明，本模块只做"计量单位 + 税"换算）。
3. 任何无法自动判定的口径（如"含量 98%"、"干基/湿基"、"现货/期货"）一律由输入显式给出，
   本模块**不猜**。判定不了就抛 Unresolvable，由 validate 报为 error/gap。
4. 税口径只做"含税 <-> 不含税"这一种可逆换算，税率必须由用户给出（默认 13%，且必须标注为默认值）。

术语
----
dosage_unit  单耗单位：t/t | kg/t | kg/kg | t/t_product | g/t(可选，精细化工微量助剂)
price_unit   计价单位：CNY/t | CNY/kg | CNY/吨 | USD/t | USD/kg | 元/千克 ...
"""
import re

CNY = ('CNY', 'RMB', 'CN¥', '￥', '¥', '元', '人民币')
USD = ('USD', 'US$', '$', '美元')

# 计量单位 -> 换算到"千克"的系数
MASS_TO_KG = {
    't': 1000.0, 'ton': 1000.0, 'tonne': 1000.0, 'tonnes': 1000.0, '吨': 1000.0,
    'kg': 1.0, 'kgs': 1.0, 'kilogram': 1.0, '千克': 1.0, '公斤': 1.0,
    'g': 0.001, 'gram': 0.001, '克': 0.001,
    'lb': 0.45359237, '磅': 0.45359237,
}

# 产品基准单位（本技能统一按"每 1 吨产品"）
PRODUCT_BASE_T = 1.0


class Unresolvable(Exception):
    """输入不足以自动判定口径时抛出，调用方须转成 error/gap，不得猜测。"""


def norm_unit(u):
    """归一化单位写法：'元/吨' -> ('CNY','t')；'USD/ton' -> ('USD','t')。"""
    if not isinstance(u, str) or not u.strip():
        raise Unresolvable('单位为空')
    s = u.strip().replace(' ', '').replace('／', '/')
    cur = 'CNY'
    for c in CNY:
        if s.upper().startswith(c.upper()) or s.startswith(c):
            cur = 'CNY'
            s = s[len(c):]
            break
    else:
        for c in USD:
            if s.upper().startswith(c.upper()) or s.startswith(c):
                cur = 'USD'
                s = s[len(c):]
                break
        else:
            cur = None
    s = s.lstrip('/')
    for sep in ('per', '每', '/'):
        if sep in s:
            s = s.split(sep, 1)[1]
            break
    m = s.strip().lower()
    if m not in MASS_TO_KG:
        raise Unresolvable('无法识别的计量单位：%r' % u)
    return (cur, m)


def mass_factor(unit):
    """该计量单位 1 个 = 多少千克。"""
    _, m = norm_unit(unit)
    return MASS_TO_KG[m]


def price_to_cny_per_t(price, unit, fx_usd_cny=None, tax_included=True, tax_rate=0.13,
                       target_tax_included=True, tax_rate_note=None):
    """把任意计价单位/币种/税口径的价格换成 目标税口径 的 ￥/t。

    返回 dict: {value, cny_per_kg, factors:[{label, calc, value}], notes:[...]}
    - 币种：USD 需要 fx_usd_cny；缺失则抛 Unresolvable（禁止用默认汇率硬算）
    - 税：included -> excluded 除以 (1+r)；excluded -> included 乘以 (1+r)
      默认 r=13%（增值税一般税率）。若用默认值，notes 会明确记录"默认 13%，非用户给定"。
    """
    cur, mass = norm_unit(unit)
    factors = []
    v = float(price)
    factors.append({'label': '原始价格', 'calc': '', 'value': v, 'unit': unit})

    if cur is None:
        raise Unresolvable('价格单位缺少币种：%r（请写成 CNY/t、USD/kg 这类形式）' % unit)

    # 1) 计量单位 -> 每千克
    per_kg = v / MASS_TO_KG[mass]
    factors.append({'label': '换算到每千克', 'calc': '%g ÷ %g' % (v, MASS_TO_KG[mass]),
                    'value': per_kg, 'unit': '%s/kg' % ('元' if cur == 'CNY' else 'USD')})
    # 2) -> 每吨
    per_t = per_kg * 1000.0
    factors.append({'label': '换算到每吨', 'calc': '%g × 1000' % per_kg,
                    'value': per_t, 'unit': '%s/t' % cur})
    # 3) 币种
    if cur == 'USD':
        if fx_usd_cny in (None, ''):
            raise Unresolvable('价格为 USD 计价，但缺少汇率 fx_usd_cny（禁止用默认汇率硬算）')
        per_t = per_t * float(fx_usd_cny)
        factors.append({'label': '美元折人民币', 'calc': '%.4f × %g' % (per_t / float(fx_usd_cny), float(fx_usd_cny)),
                        'value': per_t, 'unit': '元/t'})
    # 4) 税口径
    notes = []
    r = float(tax_rate)
    if tax_included != target_tax_included:
        if target_tax_included:
            per_t = per_t * (1.0 + r)
            factors.append({'label': '不含税→含税', 'calc': '× (1 + %g)' % r, 'value': per_t, 'unit': '元/t(含税)'})
        else:
            per_t = per_t / (1.0 + r)
            factors.append({'label': '含税→不含税', 'calc': '÷ (1 + %g)' % r, 'value': per_t, 'unit': '元/t(不含税)'})
        notes.append(tax_rate_note or '税率 %g（%s）' % (r, '默认增值税一般税率，非用户给定' if tax_rate_note is None else tax_rate_note))

    return {'value': per_t, 'cny_per_kg': per_t / 1000.0, 'factors': factors, 'notes': notes}


def dosage_to_t_per_t(dosage, unit_hint='t/t'):
    """把单耗统一成 t_原料 / t_产品。

    支持：
      - '0.383' + 't/t'    -> 0.383
      - '383'   + 'kg/t'   -> 0.383
      - '0.383' + 'kg/kg'  -> 0.383   （kg/kg 与 t/t 数值等价）
      - '383000' + 'g/t'   -> 0.383
      - '2.2'   + 'mol/mol'-> 需配合 mw 换算（用 stoichiometry.mol_ratio_to_R）
    复合单位先按分子单位换算成吨、再除以分母吨数（分母缺省为 1 t 产品）。
    """
    v = float(dosage)
    if not isinstance(unit_hint, str) or not unit_hint.strip():
        raise Unresolvable('单耗单位为空')
    s = unit_hint.strip().replace(' ', '').replace('／', '/')

    # mol 比不能当质量单耗用
    if 'mol' in s.lower():
        raise Unresolvable('mol/mol 是摩尔比，不能直接当质量单耗；'
                           '请用 stoichiometry.mol_ratio_to_R / theoretical_dosage 换算')

    parts = re.split(r'[/每]|per', s, maxsplit=1)
    num_u = parts[0].strip().lower()
    den_u = parts[1].strip().lower() if len(parts) > 1 else 't'
    if num_u not in MASS_TO_KG:
        raise Unresolvable('无法识别的单耗分子单位：%r' % unit_hint)
    if den_u not in MASS_TO_KG:
        raise Unresolvable('无法识别的单耗分母单位：%r' % unit_hint)

    kg_num = v * MASS_TO_KG[num_u]          # 分子换算成 kg
    t_den = MASS_TO_KG[den_u] / 1000.0      # 分母换算成 t
    return (kg_num / 1000.0) / t_den


def fmt_num(v, nd=2):
    if v is None:
        return '—'
    try:
        return ('{:,.%df}' % nd).format(float(v))
    except Exception:
        return str(v)
