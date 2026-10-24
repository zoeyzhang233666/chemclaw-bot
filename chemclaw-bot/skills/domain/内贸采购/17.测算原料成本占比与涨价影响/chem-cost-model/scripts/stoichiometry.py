#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""化学计量（化学式解析、分子量、反应式配平、理论单耗、表观投料换算）。

与产品无关：任何化工品只要给出反应式和分子式都能用。
所有分子量按 2019 年 IUPAC 标准原子量计算，并由 chemical_formula 自行解析。

关键概念（见 references/unit-consumption.md）
---------------------------------------------
- 理论单耗 = 化学计量系数 × MW(原料) / MW(产品)
- 表观投料 = 理论单耗 × 过量倍数 R（不回收）
- 净单耗   = 理论单耗 / 转化率 / 收率 等组合 —— 本模块只提供公式件，不擅自补参数
"""

import re
from fractions import Fraction

# 2019 IUPAC 标准原子量（abridged, 4-6 位有效数字）
ATOMIC_WEIGHTS = {
    'H': 1.008, 'He': 4.002602,
    'Li': 6.94, 'Be': 9.0121831, 'B': 10.81, 'C': 12.011, 'N': 14.007, 'O': 15.999,
    'F': 18.998403163, 'Ne': 20.1797,
    'Na': 22.98976928, 'Mg': 24.305, 'Al': 26.9815384, 'Si': 28.085, 'P': 30.973761998,
    'S': 32.06, 'Cl': 35.45, 'Ar': 39.948,
    'K': 39.0983, 'Ca': 40.078, 'Sc': 44.955908, 'Ti': 47.867, 'V': 50.9415,
    'Cr': 51.9961, 'Mn': 54.938043, 'Fe': 55.845, 'Co': 58.933194, 'Ni': 58.6934,
    'Cu': 63.546, 'Zn': 65.38, 'Ga': 69.723, 'Ge': 72.630, 'As': 74.921595,
    'Se': 78.971, 'Br': 79.904, 'Kr': 83.798,
    'Rb': 85.4678, 'Sr': 87.62, 'Y': 88.90584, 'Zr': 91.224, 'Nb': 92.90637,
    'Mo': 95.95, 'Ru': 101.07, 'Rh': 102.90549, 'Pd': 106.42, 'Ag': 107.8682,
    'Cd': 112.414, 'In': 114.818, 'Sn': 118.710, 'Sb': 121.760, 'Te': 127.60,
    'I': 126.90447, 'Xe': 131.293,
    'Cs': 132.90545196, 'Ba': 137.327, 'La': 138.90547, 'Ce': 140.116,
    'Pt': 195.084, 'Au': 196.966570, 'Hg': 200.592, 'Pb': 207.2, 'Bi': 208.98040,
    'U': 238.02891, 'W': 183.84, 'Ta': 180.94788, 'Hf': 178.49, 'Re': 186.207,
    'Os': 190.23, 'Ir': 192.217, 'Tl': 204.38, 'Sn': 118.710, 'Ni ': 58.6934,
}

_TOKEN = re.compile(r'([A-Z][a-z]?)(\d*)|(\()|(\))(\d*)|(·|\.)(\d*)')


def parse_formula(formula):
    """解析化学式 -> {'C': 24, 'H': 38, 'O': 4}。支持括号、水合物点号 '·'、'.'。"""
    if not formula or not isinstance(formula, str):
        raise ValueError('空化学式')
    s = formula.strip().replace('．', '·')
    # 水合物：CuSO4·5H2O
    parts = re.split(r'[·]', s)
    total = {}
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r'^(\d+)(.*)$', part)
        mult_part = 1
        if m:
            mult_part = int(m.group(1))
            part = m.group(2)
        stack = [{}]
        i = 0
        while i < len(part):
            ch = part[i]
            if ch == '(':
                stack.append({})
                i += 1
            elif ch == ')':
                i += 1
                num = ''
                while i < len(part) and part[i].isdigit():
                    num += part[i]
                    i += 1
                k = int(num) if num else 1
                grp = stack.pop()
                for e, n in grp.items():
                    stack[-1][e] = stack[-1].get(e, 0) + n * k
            else:
                m = re.match(r'([A-Z][a-z]?)(\d*)', part[i:])
                if not m:
                    raise ValueError('无法解析化学式片段：%r（在 %r 中）' % (ch, formula))
                e, num = m.group(1), m.group(2)
                if e not in ATOMIC_WEIGHTS:
                    raise ValueError('未知元素：%s' % e)
                stack[-1][e] = stack[-1].get(e, 0) + (int(num) if num else 1)
                i += len(m.group(0))
        if len(stack) != 1:
            raise ValueError('括号不匹配：%r' % formula)
        for e, n in stack[0].items():
            total[e] = total.get(e, 0) + n * mult_part
    return total


def molar_mass(formula):
    comp = parse_formula(formula)
    return sum(ATOMIC_WEIGHTS[e] * n for e, n in comp.items())


def composition_pct(formula):
    comp = parse_formula(formula)
    mw = molar_mass(formula)
    return {e: round(ATOMIC_WEIGHTS[e] * n / mw * 100, 3) for e, n in comp.items()}


def parse_reaction(eq):
    """'C8H4O3 + 2 C8H18O -> C24H38O4 + H2O' -> ({side: {species: coeff}})"""
    if '->' in eq:
        lhs, rhs = eq.split('->')
    elif '=>' in eq:
        lhs, rhs = eq.split('=>')
    elif '=' in eq:
        lhs, rhs = eq.split('=')
    elif '→' in eq:
        lhs, rhs = eq.split('→')
    else:
        raise ValueError("反应式缺少箭头（用 -> 或 =）：%r" % eq)

    def side(txt):
        out = {}
        for term in re.split(r'\+', txt):
            term = term.strip()
            if not term:
                continue
            m = re.match(r'^(\d+(?:\.\d+)?)\s*([A-Z(].*)$', term)
            if m:
                c = float(m.group(1))
                sp = m.group(2).strip()
            else:
                c, sp = 1.0, term
            out[sp] = out.get(sp, 0.0) + c
        return out

    return {'lhs': side(lhs), 'rhs': side(rhs)}


def theoretical_dosage(reaction, product, material, product_mw=None, material_mw=None):
    """理论单耗 t_原料 / t_产品 = ν_原料 × MW_原料 / (ν_产品 × MW_产品)。"""
    rd = parse_reaction(reaction)
    if product not in rd['rhs']:
        raise ValueError('产物 %r 不在反应式右侧' % product)
    if material not in rd['lhs']:
        raise ValueError('原料 %r 不在反应式左侧' % material)
    nu_p = rd['rhs'][product]
    nu_m = rd['lhs'][material]
    mw_p = product_mw or molar_mass(product)
    mw_m = material_mw or molar_mass(material)
    return nu_m * mw_m / (nu_p * mw_p)


def mass_balance(reaction):
    """质量守恒校验：左右两侧质量是否相等（原子经济性检查）。"""
    rd = parse_reaction(reaction)
    def side_mass(d):
        return sum(c * molar_mass(sp) for sp, c in d.items())
    l, r = side_mass(rd['lhs']), side_mass(rd['rhs'])
    return {'lhs_mass': l, 'rhs_mass': r, 'diff': l - r,
            'ok': abs(l - r) < 1e-6 * max(1.0, l)}


def mol_ratio_to_R(material_nu, product_nu, feed_mol_ratio):
    """把'原料:关键原料的摩尔比'换成 R（相对理论投入的倍数）。

    例：DOP 中 2EH:PA = 2.20（摩尔），理论 2:1 -> R = 2.20 / 2 = 1.10（即过量 10%）
    """
    theo = material_nu / product_nu
    return feed_mol_ratio / theo


def wt_ratio_to_mol_ratio(ratio_wt, mw_a, mw_b):
    """质量比 A:B -> 摩尔比 A:B。"""
    return (ratio_wt / mw_a) / (1.0 / mw_b)


def mol_ratio_to_wt_ratio(mol_ratio, mw_a, mw_b):
    return mol_ratio * mw_a / mw_b


def apparent_dosage(theo_dosage, R):
    """表观投料单耗（不回收口径）= 理论 × R。"""
    return theo_dosage * R


def net_dosage(theo_dosage, conversion, yield_, recycle_rate=0.0, R=1.0, side_loss=0.0):
    """净单耗（已扣回收回收率）。

    net = theo / (conversion × yield)                     —— 消耗掉的部分
        + theo × R × (1 - recycle_rate) × (1+yield)/2    —— 过量醇未回收部分（工程近似）
        × (1 + side_loss)
    说明：过量部分只对"过量投料"的原料适用；对不过量的原料，R 取 1。
    若 recycle_rate=1（全回收），过量部分为 0 —— 即"过量不影响净耗"。
    """
    base = theo_dosage / max(conversion * yield_, 1e-9)
    over = theo_dosage * max(R - 1.0, 0.0) * (1.0 - recycle_rate)
    return (base + over) * (1.0 + side_loss)


def co_product_allocation(total_cost, method, shares=None, by_values=None):
    """联产/副产成本分摊。只做数学，分摊依据必须由用户提供。

    method:
      - 'by_mass'   按质量分摊（shares 为各产品质量）
      - 'by_value'  按售价分摊（by_values 为各产品价值）
      - 'credit'    主产品成本 = 总成本 - 副产品按市价抵扣（by_values 为副产价值）
    返回 {产品: 应承担成本}
    """
    if method in ('by_mass', 'by_value'):
        base = shares if method == 'by_mass' else by_values
        if not base:
            raise ValueError('分摊依据缺失：需要 shares/by_values')
        s = float(sum(base.values()))
        if s <= 0:
            raise ValueError('分摊基数非正')
        return {k: total_cost * v / s for k, v in base.items()}
    if method == 'credit':
        if not by_values:
            raise ValueError('副产品抵扣缺少市价')
        credit = float(sum(by_values.values()))
        return {'main': total_cost - credit, 'credit_total': credit}
    raise ValueError('未知分摊方法：%r' % method)
