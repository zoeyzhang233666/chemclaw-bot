# -*- coding: utf-8 -*-
"""PVC 电石法 理论成本/价差/利润 计算引擎（单一事实源）。

与 HTML 内嵌 JS、Excel 活公式三者使用完全相同的公式与顺序：
  1) 氯碱副产烧碱（可选，默认关闭）
  2) 收率校正后的单耗 = 工艺单耗 / 收率
  3) 原料成本 = Σ(单耗_i × 价格_i)
  4) 能源成本 = Σ(单耗_j × 价格_j)
  5) 辅料成本 = Σ(单耗_k × 价格_k)
  6) 加工价差 = 产品价 − 原料成本（理想化回收）
  7) 理论制造利润 = 加工价差 − 能源成本 − 辅料成本 − 制造成本
  8) 不可计入成本 = 未定价项合计（显式列为缺口，不进利润）

单位：全部为 元/吨 PVC；价格默认含 13% 增值税、现款现汇、中国境内送到/自提。
"""
from copy import deepcopy

VAT = 0.13

# ---------------------------------------------------------------------------
# 默认参数（每一项都带 source；数值取自公开资料，见 references/process-dossiers.md）
# ---------------------------------------------------------------------------
DEFAULT = {
    'product': {'name': 'PVC (SG-5)', 'price': 4865.0, 'unit': '元/吨', 'tax_incl': True},
    'yield': 0.97,          # CaC2->PVC 综合收率（电石发气量 + 乙炔损失 + 聚合收率）
    'route': 'calcium_carbide',

    # kind: raw(原料) / energy(能源) / aux(辅料) / byproduct(氯碱联产副产)
    'inputs': [
        {'id': 'cac2', 'name': '电石 (CaC2, 发气量≥300L/kg)', 'kind': 'raw',
         'cons': 1.45, 'unit': '吨/吨', 'price': 2530.0,
         'source': '单耗：国家标准口径 1.45–1.5 t/t (前瞻/新浪财经 2022-01-17)；价格：生意社电石基准价 2026-10-19 宁夏/内蒙古出厂折算',
         'note': '行业统计口径另有 1.35–1.42 t/t(隆众 2024-12)；1.4–1.6 t/t(中国化工网 2026)。本模型取国标口径中值 1.45。'},
        {'id': 'cao', 'name': '石灰 (生石灰)', 'kind': 'raw',
         'cons': 0.0, 'unit': '吨/吨', 'price': 0.0,
         'source': '未纳入：石灰成本已内含于外购电石价格；仅“电石自产一体化”工艺才需单独计价',
         'note': '若企业自产电石，需改用电石内部成本模型（石灰石+兰炭+电）。'},
        {'id': 'naoh', 'name': '烧碱 (32% 液碱, 折百单价)', 'kind': 'raw',
         'cons': 0.0, 'unit': '吨(折百)/吨', 'price': 1966.0,
         'source': '价格：生意社液碱 32% 基准价 629 元/吨 ÷ 0.32 = 1966 元/吨(折百)',
         'note': '仅在“外购烧碱再电解制氯”模式下计入；氯碱一体化企业不单独计价。默认关闭。'},
        {'id': 'salt', 'name': '原盐', 'kind': 'raw',
         'cons': 0.0, 'unit': '吨/吨', 'price': 0.0,
         'source': '未纳入：原盐成本内含于外购烧碱/氯气价格',
         'note': '氯碱一体化需按 1t PVC 对应约 1.4–1.6 t 原盐建模。'},
        {'id': 'cl2', 'name': '液氯 (外购)', 'kind': 'raw',
         'cons': 0.0, 'unit': '吨/吨', 'price': 0.0,
         'source': '未纳入：液氯现货价缺失且氯碱一体化为常态；氯与 HCl 按“HCl 气体”整体计价',
         'note': '企业若有液氯采购价，可按 0.6 t/t 就近填入。'},

        {'id': 'hcl', 'name': '氯化氢气体 (HCl)', 'kind': 'aux',
         'cons': 0.72, 'unit': '吨/吨', 'price': 380.0,
         'source': '单耗：国标 0.75–0.85 t/t；隆众行业统计 630–650 kg/t。取 0.72(中值折算)',
         'note': '价格按“自产 HCl 的氯成本”估值：0.6 t Cl2 的氯碱成本 ≈ 380 元/吨 HCl（非液氯市价）。'
                 '⚠ 若按文献口径(前瞻/隆众)把氯按市价 1000–1400 元/吨折入 HCl(约 1000 元/吨 HCl)，'
                 'HCl 占比将升至 ~13%、与文献 14–15% 吻合，但理论利润会同步下降约 390 元/吨、'
                 '与隆众毛利偏离扩大至 -580 元/吨。故本模型默认采用“自产 HCl 成本”口径，'
                 '在企业参数面板中可一键改为市价口径。'},
        {'id': 'catalyst', 'name': '汞触媒(低汞/无汞)', 'kind': 'aux',
         'cons': 1.2, 'unit': 'kg/吨', 'price': 9500.0,
         'source': '单耗：专利 CN103408392A（1.2 kg 触媒/吨 PVC）',
         'note': '触媒为催化剂而非消耗性原料，按补加量计；单价为行业量级估计，需企业实采价替换。'},
        {'id': 'initiator', 'name': '引发剂/分散剂/助剂', 'kind': 'aux',
         'cons': 1.0, 'unit': 'kg/吨(综合)', 'price': 12000.0,
         'source': '未定值：行业概览提及“包装费、引发剂、分散剂、水费”等(前瞻/隆众)',
         'note': '综合量级估计，属“可核实性低”项；默认按合计计入并在报告中标注。'},

        {'id': 'ele_pvc', 'name': 'PVC 装置电耗', 'kind': 'energy',
         'cons': 450.0, 'unit': 'kWh/吨', 'price': 0.55,
         'source': '单耗：国标 450–500 kWh/t（PVC 装置本级）；中国化工报 2025-11 称含电石环节综合电耗约 8500 kWh/t',
         'note': '⚠ 两者不可混用：外购电石企业只付装置本级电耗；一体化企业电石电耗已含在电石价格内。'},
        {'id': 'steam', 'name': '蒸汽 (1.0MPa)', 'kind': 'energy',
         'cons': 1.2, 'unit': '吨/吨', 'price': 150.0,
         'source': '未定值：乙炔发生+聚合+干燥用汽，行业常见 0.8–1.5 t/t',
         'note': '单价按热电联产自产汽成本估算；外购蒸汽需按当地汽价替换。'},
        {'id': 'power_cac2', 'name': '电石电耗(一体化口径)', 'kind': 'energy',
         'cons': 0.0, 'unit': 'kWh/吨', 'price': 0.42,
         'source': '一体化替代口径：电石约 3400–3600 kWh/t(联成化学 2020) × 1.45 t/t ≈ 4930–5220 kWh',
         'note': '仅当勾选“电石自产”时启用；此时应同时把电石单价换成电石内部成本。'},
    ],

    'byproduct': {'id': 'by_naoh', 'name': '联产烧碱(副产抵减)', 'kind': 'byproduct',
                  'cons': 0.75, 'unit': '吨/吨', 'price': 629.0, 'enabled': False,
                  'source': '联产比例：1 t PVC 副产约 0.75 t 烧碱(氯碱平衡)；价格：生意社 32% 液碱 629 元/吨',
                  'note': '开启后以“副产收益”冲减成本；仅在氯碱一体化口径下成立，外购电石企业不适用。'},

    'manufacturing': {'labor': 260.0, 'depreciation': 320.0, 'packaging': 120.0,
                      'other': 80.0, 'enabled': True,
                      'source': '量级参考：隆众全国电石法 PVC 成本口径含“原材料+助剂+设备折旧+人工水电”；'
                                '前瞻/隆众成本构成中制造费用约占 5.6%–6%。企业实账请优先覆盖。',
                      'note': '折旧/人工/包装/其他 为可核实性最低的一段，默认值仅供结构演示。'},
}


def _price_basis(item):
    """返回 (数量换算系数, 收率适用标志)。

    计价单位从 'unit' 字段解析，避免 kg 单耗 × 元/吨 价被放大 1000 倍：
      '吨/吨' / '吨(折百)/吨' -> 系数 1
      'kg/吨'                 -> 系数 1/1000
      'kWh/吨'                -> 系数 1
    收率只对“会进入产品质量平衡”的原料与辅料起作用，能源不受收率影响。
    """
    u = (item.get('unit') or '').lower()
    if u.startswith('kg'):
        return 0.001, True
    if u.startswith('kwh'):
        return 1.0, False
    if '吨' in u or 't/' in u:
        return 1.0, item['kind'] in ('raw', 'aux')
    return 1.0, item['kind'] in ('raw', 'aux')


def _unit_cost(item, yield_):
    """单个物料/能源的单位成本（元/吨 PVC）。"""
    if item.get('cons', 0) <= 0:
        return 0.0
    k, apply_yield = _price_basis(item)
    base = item['cons'] * k * item['price']
    return base / yield_ if apply_yield else base


def compute(params=None, shock=None):
    """shock: {'cac2': +0.05, 'product': +0.05, ...} 价格变动比例；返回完整计算结果。

    注意：params 会先被深拷贝，调用方传入全局 DEFAULT 也不会被本函数改写。
    """
    p = deepcopy(DEFAULT) if params is None else deepcopy(params)
    y = max(p.get('yield', 1.0), 0.01)
    shock = shock or {}

    rows = []
    by_ = p.get('byproduct') or {}
    if by_.get('enabled'):
        rows.append(by_)
    rows.extend(p['inputs'])

    raw_cost = energy_cost = aux_cost = byproduct_credit = 0.0
    breakdown = []
    for it in rows:
        price = it['price'] * (1 + shock.get(it['id'], 0.0))
        it2 = dict(it, price=price)
        c = _unit_cost(it2, y)
        k, ay = _price_basis(it)
        rec = {'id': it['id'], 'name': it['name'], 'kind': it['kind'],
               'cons': it['cons'],
               'cons_eff': round(it['cons'] / y, 4) if (ay and it['cons']) else it['cons'],
               'unit': it['unit'], 'k': k, 'apply_yield': ay,
               'price': round(price, 2), 'cost': round(c, 2),
               'source': it.get('source', ''), 'note': it.get('note', '')}
        if it['kind'] == 'raw':
            raw_cost += c
        elif it['kind'] == 'energy':
            energy_cost += c
        elif it['kind'] == 'aux':
            aux_cost += c
        elif it['kind'] == 'byproduct':
            byproduct_credit += c
        breakdown.append(rec)

    mfg = p.get('manufacturing') or {}
    mfg_on = bool(mfg.get('enabled', True))
    mfg_cost = sum(float(mfg.get(k, 0) or 0) for k in ['labor', 'depreciation', 'packaging', 'other']) if mfg_on else 0.0

    product_price = p['product']['price'] * (1 + shock.get('product', 0.0))
    # 注意：产品价与原料价同为含税（13%），因此价差为“含税价差”，不重复扣税
    net_raw = raw_cost - byproduct_credit
    spread = product_price - net_raw                 # 加工价差（原料口径）
    profit = spread - energy_cost - aux_cost - mfg_cost  # 理论制造利润
    total_cost = net_raw + energy_cost + aux_cost + mfg_cost

    total_for_share = raw_cost + energy_cost + aux_cost + (mfg_cost if mfg_on else 0)
    shares = {}
    for r in breakdown:
        if r['kind'] == 'byproduct':
            continue
        shares[r['id']] = round(r['cost'] / total_for_share * 100, 2) if total_for_share else 0.0
    # 口径对齐文献：hcl_share=占“总成本”比例（前瞻/隆众给 14–15%，因其把 HCl 与电石同视为主原料）；
    # raw_basket_share = HCl 计入原料篮子后的电石占比（对标文献 65–75%）
    hcl_cost = next((x['cost'] for x in breakdown if x['id'] == 'hcl'), 0.0)
    raw_basket = raw_cost + hcl_cost
    shares['hcl'] = round(hcl_cost / total_for_share * 100, 2) if total_for_share else 0.0
    shares['_raw_basket'] = round(raw_basket / total_for_share * 100, 2) if total_for_share else 0.0
    shares['_raw_electric'] = round(next((x['cost'] for x in breakdown if x['id'] == 'cac2'), 0.0)
                                    / raw_basket * 100, 2) if raw_basket else 0.0
    shares['_raw_electric_total'] = round(next((x['cost'] for x in breakdown if x['id'] == 'cac2'), 0.0)
                                          / total_for_share * 100, 2) if total_for_share else 0.0
    shares['_energy'] = round(energy_cost / total_for_share * 100, 2) if total_for_share else 0.0
    shares['_aux'] = round(aux_cost / total_for_share * 100, 2) if total_for_share else 0.0
    shares['_mfg'] = round(mfg_cost / total_for_share * 100, 2) if total_for_share else 0.0
    shares['_aux_ex_hcl'] = round((aux_cost - hcl_cost) / total_for_share * 100, 2) if total_for_share else 0.0

    return {
        'yield': y,
        'product_price': product_price,
        'raw_cost': round(raw_cost, 2),
        'energy_cost': round(energy_cost, 2),
        'aux_cost': round(aux_cost, 2),
        'mfg_cost': round(mfg_cost, 2),
        'byproduct_credit': round(byproduct_credit, 2),
        'net_raw_cost': round(net_raw, 2),
        'total_cost': round(total_cost, 2),
        'spread': round(spread, 2),
        'profit': round(profit, 2),
        'profit_margin_pct': round(profit / product_price * 100, 2) if product_price else 0.0,
        'breakdown': breakdown,
        'shares': shares,
        'excluded': [
            '财务费用（利息/融资成本）', '销售费用与物流运费', '增值税进销项税额差',
            '电石渣/废水中和处理与环保运行费', '装置检修与开停车损失',
            '企业所得税、资源税与地方附加', '地方电价/天然气挂牌差异带来的能源价差',
        ],
    }


def sensitivity(ids=('cac2',), steps=(-0.10, -0.05, 0.0, 0.05, 0.10), product_key='product'):
    """双因素敏感性矩阵：行=电石价变动，列=产品价变动；值=理论加工价差 与 理论制造利润。"""
    res = {'id_row': ids[0], 'id_col': product_key, 'spread': [], 'profit': []}
    for a in steps:
        rs, rp = [], []
        for b in steps:
            r = compute(shock={ids[0]: a, product_key: b})
            rs.append(r['spread'])
            rp.append(r['profit'])
        res['spread'].append(rs)
        res['profit'].append(rp)
    res['steps'] = list(steps)
    return res


def single_factor(ids=('cac2',), steps=(-0.10, -0.05, 0.0, 0.05, 0.10)):
    """单因素：每个物料 ±5%/±10% 对加工价差与利润的绝对影响。"""
    out = []
    base = compute()
    for it in DEFAULT['inputs']:
        row = {'id': it['id'], 'name': it['name'], 'kind': it['kind'], 'effect': []}
        for s in steps:
            r = compute(shock={it['id']: s})
            row['effect'].append({'step': s, 'd_spread': round(r['spread'] - base['spread'], 2),
                                  'd_profit': round(r['profit'] - base['profit'], 2),
                                  'd_cost': round(r['total_cost'] - base['total_cost'], 2)})
        out.append(row)
    return out


if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    r = compute()
    for k in ['raw_cost', 'energy_cost', 'aux_cost', 'mfg_cost', 'net_raw_cost',
              'total_cost', 'spread', 'profit', 'profit_margin_pct']:
        print('%-18s %10.2f' % (k, r[k]))
    print('shares', {k: v for k, v in r['shares'].items()})
    for b in r['breakdown']:
        print('  %-28s %-8s cons=%8.3f eff=%8.4f price=%9.2f cost=%9.2f' % (
            b['name'], b['kind'], b['cons'], b['cons_eff'], b['price'], b['cost']))
