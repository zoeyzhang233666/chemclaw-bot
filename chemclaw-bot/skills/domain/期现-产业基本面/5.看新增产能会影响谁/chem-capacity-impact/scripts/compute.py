#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chem-capacity-impact · 通用计算引擎（纯标准库，Python 3.8+）

职责：把 project.json 里的**事实**与**假设**，换算成报告要用的**派生指标**。
这是全技能唯一的计算入口——HTML 与 Excel 都只消费本模块的输出，绝不各自再算一遍。

口径约定（全模块通用）：
- 所有量一律以 **吨/年 (t/a)** 或 **吨 (t)** 存储；展示层再换算成万吨。
- 设计产能指"公称能力"，按 365 天满负荷计。
- 首年产量 = Σ 各月 `D/12 × steady_lf × ramp(k)`，**不是** `D`。
- 单耗连乘按 chain 顺序：原料 = 产量 × Π(单耗 / 纯度)。
"""

from __future__ import annotations

import datetime
import json
import math
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

#: 证据等级 → 权重（0~1），用于影响强度打分
EVIDENCE_WEIGHT = {'E1': 1.0, 'E2': 0.8, 'E3': 0.6, 'E4': 0.5, 'E5': 0.2}
EVIDENCE_ORDER = ('E1', 'E2', 'E3', 'E4', 'E5')
EVIDENCE_LABEL = {
    'E1': '一手官方',
    'E2': '行业权威媒体',
    'E3': '综合媒体转载',
    'E4': '机构口径汇总',
    'E5': '待确认',
}
#: 单耗依据等级
BASIS_LABEL = {
    'C1': '工程值',
    'C2': '区间中值',
    'C3': '化学计量下限',
    'C4': '情景假设',
}

#: 影响强度权重（须与 references/impact-pathway.md 一致）
IMPACT_WEIGHTS = {'volume': 0.35, 'transmission': 0.25, 'lag': 0.20, 'certainty': 0.20}

#: 前瞻性/方向性禁用词（validate 与 check 共用）
BANNED_WORDS = [
    '看涨', '看跌', '看多', '看空', '利好', '利空',
    '必然上涨', '必然下跌', '铁定', '稳赚', '翻倍',
    '抄底', '逃顶', '买入建议', '卖出建议',
    '目标价', '将上涨', '将下跌', '预计上涨', '预计下跌',
    '有望上行', '有望走高', '或将上涨', '或将下跌',
    '必涨', '必跌',
]

STAGE_VOCAB = ('拟建', '备案', '在建', '试车', '已投产')
TYPE_LABEL = {
    'upstream': '上游原料',
    'competitor': '同区域同行',
    'downstream': '下游用户',
    'logistics': '物流仓储',
    'byproduct': '副产物市场',
    'policy': '政策准入',
    'intermediate': '中间体',
    'process': '本项目装置',
    'product': '本产品',
}


# --------------------------------------------------------------------------
# 基础小工具
# --------------------------------------------------------------------------

def _f(v: Any, default: float = 0.0) -> float:
    """安全转 float，失败返回默认值。"""
    if v is None or v == '':
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _t(value_t: float, digits: int = 2) -> str:
    """吨 → 万吨 的展示串。"""
    return f'{_f(value_t) / 10000:.{digits}f}'


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[float]:
    """两点大圆距离（km）。任一坐标缺失返回 None。"""
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (TypeError, ValueError):
        return None
    if lat1 == 0 and lon1 == 0 or lat2 == 0 and lon2 == 0:
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


# --------------------------------------------------------------------------
# 爬坡模型
# --------------------------------------------------------------------------

def ramp_load(k: int, model: str = 's_curve', ramp_months: int = 12,
              step_plan: Optional[Sequence[float]] = None,
              custom_plan: Optional[Sequence[float]] = None) -> float:
    """第 k 个月（自开车月起算，k=1 为开车月）的负荷率，范围 0~1。

    model:
      - none        : 立即 100%（理论上限情景）
      - linear      : min(1, k/ramp_months)
      - exponential : 1 - exp(-k * K / ramp_months)，K 默认 3
      - s_curve     : 逻辑斯蒂曲线，ramp_months 月末达到 ≈95%
      - step        : 按 step_plan 逐月给定（长度不足则沿用末值）
      - custom      : 按 custom_plan 逐月给定
    """
    if k is None or k < 1:
        return 0.0
    model = (model or 'linear').strip().lower()
    if model == 'none':
        return 1.0
    if model in ('step', 'custom'):
        plan = step_plan if model == 'step' else custom_plan
        plan = list(plan or [])
        if not plan:
            return 1.0
        idx = min(k, len(plan)) - 1
        return max(0.0, min(1.0, _f(plan[idx], 1.0)))
    # s_curve：n 参考周期的逻辑斯蒂曲线，三个锚点：
    #   k=1    → 0.16（开车首月仅小负荷投料，符合石化装置"试车后连续运行、低负荷起步"）
    #   k=n/2  → 0.50（中点为 50%）
    #   k=n    → 0.95
    # 取 x = (−4)·(1 − 2k/(n+1))，即 x(k) = −ln(0.16/0.84) + (k−1)·ln(19/0.05)/(n−1)
    #   k=1:  x = −ln(0.16/0.84) = ln(0.84/0.16)  → 0.16
    #   k=n:  x = ln(0.84/0.16)+ln(19/0.05) = ln(0.84·19/(0.16·0.05)) … 反推 k=n 时恰为 0.95
    n = max(1, int(_f(ramp_months, 12)))
    if model == 'linear':
        return max(0.0, min(1.0, k / n))
    if model == 'exponential':
        # k = n 时达到 95%：1 - exp(-3k/n)，k=n → 1-e^-3 = 0.9502
        return max(0.0, min(1.0, 1.0 - math.exp(-3.0 * k / n)))
    if n <= 1:
        return 1.0
    # 逻辑斯蒂：x(k) 从 x1 线性增长到 xn，使 ramp(1)=0.16、ramp(n)=0.95
    x1 = math.log(0.16 / 0.84)   # 负数
    xn = math.log(0.95 / 0.05)   # 正数
    x = x1 + (k - 1) * (xn - x1) / (n - 1)
    return max(0.0, min(1.0, 1.0 / (1.0 + math.exp(-x))))


def ramp_curve(model: str, ramp_months: int, months: int = 36,
               steady_lf: float = 1.0, step_plan: Optional[Sequence[float]] = None,
               custom_plan: Optional[Sequence[float]] = None) -> List[Dict[str, Any]]:
    """逐月负荷曲线（含月序号、模型负荷、乘以稳定开工率后的负荷）。"""
    out = []
    for k in range(1, months + 1):
        r = ramp_load(k, model, ramp_months, step_plan, custom_plan)
        out.append({
            'month': k,
            'ramp': round(r, 4),
            'load': round(r * steady_lf, 4),
        })
    return out


# --------------------------------------------------------------------------
# 投产时间 → 月度序列（跨年正确）
# --------------------------------------------------------------------------

def month_index(year: int, month: int, base_year: Optional[int] = None) -> int:
    """把 (年, 月) 折算成自 base_year 年 1 月起的第 n 个月（1 起）。"""
    base_year = base_year or year
    return (year - base_year) * 12 + month


def production_months(start_year: int, start_month: int, horizon_years: int = 3,
                      steady_lf: float = 0.90, model: str = 's_curve',
                      ramp_months: int = 12,
                      step_plan: Optional[Sequence[float]] = None,
                      custom_plan: Optional[Sequence[float]] = None,
                      capacity_t: float = 0.0) -> List[Dict[str, Any]]:
    """从开车月开始的逐月产量序列（跨越多个自然年）。

    返回每项：year / month / k / ramp / load / output_t
    """
    start_month = max(1, min(12, int(start_month or 1)))
    months = int(horizon_years) * 12
    out = []
    for k in range(1, months + 1):
        offset = start_month - 1 + (k - 1)
        year = start_year + offset // 12
        mon = offset % 12 + 1
        r = ramp_load(k, model, ramp_months, step_plan, custom_plan)
        load = r * steady_lf
        out.append({
            'year': year,
            'month': mon,
            'k': k,
            'ramp': round(r, 4),
            'load': round(load, 4),
            'output_t': round(capacity_t / 12.0 * load, 2),
        })
    return out


def year_production(series: Sequence[Dict[str, Any]], year: int) -> float:
    """把逐月序列按自然年求和。"""
    return round(sum(m['output_t'] for m in series if m['year'] == year), 2)


def scenario_production(capacity_t: float, start_year: int, start_month: int,
                        steady_lf: float = 0.90, model: str = 's_curve',
                        ramp_months: int = 12, horizon_years: int = 3,
                        step_plan: Optional[Sequence[float]] = None,
                        custom_plan: Optional[Sequence[float]] = None) -> Dict[str, Any]:
    """单情景的产量全貌：逐月序列 + 按年汇总 + 关键指标。"""
    series = production_months(start_year, start_month, horizon_years, steady_lf,
                               model, ramp_months, step_plan, custom_plan, capacity_t)
    years: Dict[int, float] = {}
    for m in series:
        years[m['year']] = round(years.get(m['year'], 0.0) + m['output_t'], 2)
    first_year = start_year
    first_year_months = [m for m in series if m['year'] == first_year]
    # 首年可产月数 = 开车月至当年 12 月
    avail_months = 12 - max(1, min(12, int(start_month))) + 1
    q_y1 = years.get(first_year, 0.0)
    q_steady = capacity_t * steady_lf
    return {
        'capacity_t': capacity_t,
        'start_year': start_year,
        'start_month': start_month,
        'steady_lf': steady_lf,
        'ramp_model': model,
        'ramp_months': ramp_months,
        'avail_months': avail_months,
        'series': series,
        'by_year': [{'year': y, 'output_t': round(v, 2)} for y, v in sorted(years.items())],
        'first_year_output_t': round(q_y1, 2),
        'first_year_ratio': round(q_y1 / capacity_t, 4) if capacity_t else 0.0,
        'steady_output_t': round(q_steady, 2),
        'full_output_t': capacity_t,
        'first_year_month_detail': first_year_months,
    }


# --------------------------------------------------------------------------
# 分母占比
# --------------------------------------------------------------------------

def capacity_share(new_t: float, bases: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """计算新增产能相对各组分母的占比。

    bases 里 key == 'radius' 时，若 value_t 缺失但给了 neighbors，则由邻居求和。
    """
    out = []
    for b in bases:
        base_t = _f(b.get('value_t'))
        if b.get('key') == 'radius' and base_t <= 0:
            nb = b.get('neighbors') or []
            base_t = sum(_f(x.get('capacity_t')) for x in nb)
        if base_t <= 0:
            share = None
        else:
            share = new_t / base_t
        alt = _f(b.get('value_t_alt'))
        out.append({
            'key': b.get('key'),
            'label': b.get('label') or b.get('key'),
            'base_t': base_t,
            'year': b.get('year'),
            'scope': b.get('scope', ''),
            'level': b.get('level', 'E5'),
            'source': b.get('source', ''),
            'url': b.get('url', ''),
            'note': b.get('note', ''),
            'share': share,
            'share_pct': None if share is None else round(share * 100, 3),
            'base_t_alt': alt if alt > 0 else None,
            'share_alt_pct': (None if alt <= 0 else round(new_t / alt * 100, 3)),
            'alt_label': b.get('alt_label', ''),
            'tier': tier_of_share(b.get('key'), share),
        })
    return out


def tier_of_share(key: Optional[str], share: Optional[float]) -> str:
    """分档词典（只描述量级，不含价格判断）。"""
    if share is None:
        return '无法判定'
    p = share * 100
    if key in ('national', 'consumption'):
        if p < 1:
            return '可以忽略'
        if p < 3:
            return '边际'
        if p < 8:
            return '显著'
        return '结构性'
    if key in ('regional', 'radius'):
        if p < 5:
            return '温和'
        if p < 15:
            return '明显'
        if p < 30:
            return '重大'
        return '洗牌级'
    return '补充口径'


# --------------------------------------------------------------------------
# 原料需求（单耗连乘）
# --------------------------------------------------------------------------

def normalize_uc(uc_list: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {u.get('key'): u for u in uc_list if u.get('key')}


def cumulative_ratio(chain: Optional[Dict[str, Any]],
                     uc_list: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """按 chain 顺序把单耗连乘，得到每种原料的需求系数（t 原料 / t 产品）。

    无 chain 时，退化为"所有单耗连乘"的简单模式，并标注。
    """
    ucs = normalize_uc(uc_list)
    result: Dict[str, Dict[str, Any]] = {}

    # 简单模式：all-product 一次连乘
    if not chain or not chain.get('edges'):
        coeff = 1.0
        parts = []
        for u in uc_list:
            purity = _f(u.get('purity'), 1.0) or 1.0
            v = _f(u.get('value'), 0.0)
            coeff *= v / purity
            parts.append({'key': u.get('key'), 'value': v, 'purity': purity,
                          'basis': u.get('basis'), 'evidence_level': (u.get('evidence') or {}).get('level', 'E5')})
        result['ALL'] = {'coefficient': coeff, 'parts': parts, 'on_site': True}
        return result

    edges = chain['edges']
    nodes = {n['id']: n for n in (chain.get('nodes') or []) if n.get('id')}

    def is_downstream_edge(e: Dict[str, Any]) -> bool:
        """下游/结构性边：只用于画图，不参与原料需求回溯。

        判据只看"上游端是否为产品/中间体"与下游节点类型，不因目标节点是产品而误删主链。
        """
        if e.get('structural') or e.get('downstream'):
            return True
        src = nodes.get(e.get('from'), {})
        dst = nodes.get(e.get('to'), {})
        # 从产品/中间体流向"下游用户"的边
        return dst.get('type') == 'downstream' or \
            (src.get('type') in ('product', 'intermediate') and dst.get('type') == 'downstream')

    def is_byproduct_edge(e: Dict[str, Any]) -> bool:
        """反向边（副产物从主流程分叉出去）：不参与原料需求回溯。"""
        return bool(e.get('reverse')) or \
            nodes.get(e.get('from'), {}).get('type') == 'byproduct'

    # 找产品节点：优先 type == 'product'
    product_ids = [nid for nid, n in nodes.items() if n.get('type') == 'product']
    if not product_ids:
        product_ids = [nid for nid, n in nodes.items() if n.get('type') == 'intermediate'][-1:]

    # 反向遍历：产品 → 中间体 → … → 上游原料
    incoming: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        if is_downstream_edge(e) or is_byproduct_edge(e):
            continue
        incoming.setdefault(e.get('to'), []).append(e)

    def walk(node_id: str, coeff: float, parts: List[Dict[str, Any]], depth: int = 0) -> None:
        if depth > 12:          # 防环
            return
        ups = incoming.get(node_id, [])
        if not ups:
            node = nodes.get(node_id, {})
            key = node.get('name') or node_id
            prev = result.get(key)
            if prev:            # 同一原料经多条路径到达：累加
                prev['coefficient'] += coeff
                prev['paths'].append(list(parts))
            else:
                result[key] = {
                    'node_id': node_id,
                    'coefficient': coeff,
                    'parts': list(parts),
                    'paths': [list(parts)],
                    'on_site': all(p.get('on_site', True) for p in parts),
                    'type': node.get('type', 'upstream'),
                }
            return
        for e in ups:
            uk = e.get('unit_key')
            u = ucs.get(uk) if uk else None
            if not u:
                # 无单耗记录的连接 = 结构边（系数 1）
                walk(e.get('from'), coeff, parts, depth + 1)
                continue
            purity = _f(u.get('purity'), 1.0) or 1.0
            v = _f(u.get('value'), 0.0)
            walk(e.get('from'), coeff * v / purity,
                 parts + [{
                     'key': uk, 'from': e.get('from'), 'to': e.get('to'),
                     'value': v, 'purity': purity, 'unit': u.get('unit', 't/t'),
                     'basis': u.get('basis'), 'on_site': u.get('on_site', True),
                     'evidence_level': (u.get('evidence') or {}).get('level')
                     or u.get('evidence_level', 'E5'),
                 }], depth + 1)

    for pid in product_ids:
        walk(pid, 1.0, [])
    return result


def raw_material_demand(output_t: float, coeff: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按产量换算每种原料的需求（t/年）。"""
    rows = []
    for name, c in coeff.items():
        rows.append({
            'material': name,
            'node_id': c.get('node_id', ''),
            'coefficient': round(c['coefficient'], 6),
            'demand_t': round(output_t * c['coefficient'], 2),
            'on_site': c.get('on_site', True),
            'type': c.get('type', 'upstream'),
            'parts': c.get('parts', []),
        })
    return rows


def byproduct_output(output_t: float, chain: Optional[Dict[str, Any]],
                     uc_list: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """副产物（如副产氢）：在 unit_consumption 里以 byproduct 字段声明。"""
    out = []
    for u in uc_list:
        bp = u.get('byproduct')
        if not bp:
            continue
        v = _f(bp.get('value'), 0.0)
        if v <= 0:
            continue
        out.append({
            'name': bp.get('name', '副产物'),
            'ratio': v,
            'unit': bp.get('unit', 't/t'),
            'output_t': round(output_t * v, 2),
            'note': bp.get('note', ''),
            'evidence': bp.get('evidence') or (u.get('evidence') or {}),
        })
    return out


# --------------------------------------------------------------------------
# 影响强度打分
# --------------------------------------------------------------------------

def impact_score(volume_share: float, transmission: float = 1.0,
                 lag: float = 1.0, level: str = 'E5',
                 weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """影响强度 0~100。

    volume_share: 本节点相关量 / 该市场主体量（0~1+），对数压缩后使用
    """
    w = weights or IMPACT_WEIGHTS
    b = max(0.0, _f(volume_share))
    b_hat = min(1.0, math.log10(1.0 + 100.0 * b)) if b < 10 else 1.0
    t = max(0.0, min(1.0, _f(transmission, 1.0)))
    l = max(0.0, min(1.0, _f(lag, 1.0)))
    k = EVIDENCE_WEIGHT.get(level, 0.2)
    score = 100 * (w['volume'] * b_hat + w['transmission'] * t + w['lag'] * l + w['certainty'] * k)
    score = round(max(0.0, min(100.0, score)), 1)
    return {
        'score': score,
        'tier': '高' if score >= 70 else ('中' if score >= 45 else '低'),
        'parts': {
            'volume_share': round(b, 6),
            'volume_hat': round(b_hat, 4),
            'transmission': t,
            'lag': l,
            'certainty': k,
        },
    }


# --------------------------------------------------------------------------
# 区域格局
# --------------------------------------------------------------------------

def regional_position(regional: Dict[str, Any], new_capacity_t: float,
                      regional_base_t: float,
                      regional_demand_t: Optional[float] = None) -> Dict[str, Any]:
    """区域自给率变化 + 流向判断（只描述机制）。"""
    demand = _f(regional_demand_t) or _f(regional.get('demand_t'))
    ss_before = (regional_base_t / demand) if demand > 0 else None
    ss_after = ((regional_base_t + new_capacity_t) / demand) if demand > 0 else None

    def flow(ss):
        if ss is None:
            return '无法判定'
        if ss < 0.95:
            return '净输入'
        if ss <= 1.05:
            return '基本平衡'
        return '净输出'

    return {
        'region': regional.get('name', ''),
        'regional_capacity_t': round(regional_base_t, 2),
        'regional_demand_t': round(demand, 2) if demand else None,
        'new_capacity_t': round(new_capacity_t, 2),
        'self_sufficiency_before': None if ss_before is None else round(ss_before, 4),
        'self_sufficiency_after': None if ss_after is None else round(ss_after, 4),
        'ss_delta_pct': None if (ss_before is None or ss_after is None) else round((ss_after - ss_before) * 100, 2),
        'flow_before': flow(ss_before),
        'flow_after': flow(ss_after),
        'mechanism': _flow_mechanism(ss_before, ss_after),
        'freight_cny_t': regional.get('freight_cny_t'),
        'price_spread': regional.get('price_spread') or {},
        'provinces': regional.get('provinces') or [],
    }


def _flow_mechanism(ss_before, ss_after) -> str:
    if ss_before is None or ss_after is None:
        return '区域需求数据缺失，无法判断流向变化机制。'
    if ss_before < 0.95 <= ss_after:
        return ('区域由净输入转向基本平衡/净输出：外部货源（超出经济运输半径的）进入本区域的必要性下降，'
                '可观测指标为跨区流入量减少与区域报价—外区到货成本价差的收窄。')
    if ss_before < 0.95 and ss_after < 0.95:
        return '区域仍为净输入，新增产能主要被本地缺口吸收，对外部流入量的挤压有限。'
    if ss_before >= 0.95 and ss_after > 1.05:
        return ('区域由平衡转为净输出：本地货源需外扩销售半径，超出经济运输半径的部分承担运费，'
                '可观测指标为区域外发运量增长。')
    return '区域仍处于净输出状态，自给率变化幅度有限。'


# --------------------------------------------------------------------------
# 主入口：把 project.json 算成完整 data
# --------------------------------------------------------------------------

def compute_all(project: Dict[str, Any]) -> Dict[str, Any]:
    """把 project.json 换算成完整派生数据集（报告用）。"""
    meta = project.get('meta') or {}
    proj = project.get('project') or {}
    chain = project.get('chain') or {}
    bases = project.get('capacity_bases') or []
    ucs = project.get('unit_consumption') or []
    assumptions = project.get('assumptions') or {}
    scenarios_in = project.get('scenarios') or []
    stakeholders = project.get('stakeholders') or []
    regional = project.get('regional') or {}

    capacity_t = _f(proj.get('design_capacity_t'))
    start_plan = proj.get('startup_plan') or {}
    start_year = int(_f(start_plan.get('year'), 0)) or (datetime.date.today().year + 1)
    start_month = int(_f(start_plan.get('month'), 1)) or 1
    start_month = max(1, min(12, start_month))

    steady_lf = _f(assumptions.get('steady_lf'), 0.90)
    ramp_model = assumptions.get('ramp_model') or 's_curve'
    ramp_months = int(_f(assumptions.get('ramp_months'), 12))

    # ---- 1. 分母占比 ----
    # 竞争半径分母：若 regional.neighbors 有坐标，则由 compute 求和
    bases_calc = []
    for b in bases:
        bb = dict(b)
        if b.get('key') == 'radius' and _f(b.get('value_t')) <= 0 and regional.get('neighbors'):
            bb['neighbors'] = regional['neighbors']
        bases_calc.append(bb)
    shares = capacity_share(capacity_t, bases_calc)

    # ---- 2. 原料系数 ----
    coeff = cumulative_ratio(chain, ucs)
    # 同时给出单耗区间连乘（下限/上限）
    coeff_range = _coefficient_range(chain, ucs)

    # ---- 3. 情景产量 ----
    scenarios_out = []
    if not scenarios_in:
        scenarios_in = [{
            'id': 'BASE', 'label': '默认', 'kind': '基准',
            'start_month': start_month, 'ramp_model': ramp_model,
            'ramp_months': ramp_months, 'steady_lf': steady_lf,
        }]
    for s in scenarios_in:
        sm = int(_f(s.get('start_month'), start_month)) or 1
        sm = max(1, min(12, sm))
        sy = int(_f(s.get('start_year'), start_year)) or start_year
        lf = _f(s.get('steady_lf'), steady_lf)
        rmodel = s.get('ramp_model') or ramp_model
        rmonths = int(_f(s.get('ramp_months'), ramp_months))
        prod = scenario_production(
            capacity_t, sy, sm, lf, rmodel, rmonths,
            horizon_years=3,
            step_plan=s.get('step_plan'), custom_plan=s.get('custom_plan'))
        # 各情景 × 各原料
        mats_y1 = raw_material_demand(prod['first_year_output_t'], coeff)
        mats_st = raw_material_demand(prod['steady_output_t'], coeff)
        mats_full = raw_material_demand(capacity_t, coeff)
        scenarios_out.append({
            'id': s.get('id') or s.get('label'),
            'label': s.get('label', ''),
            'kind': s.get('kind', '自定义'),
            'note': s.get('note', ''),
            'start_year': sy,
            'start_month': sm,
            'steady_lf': round(lf, 4),
            'ramp_model': rmodel,
            'ramp_months': rmonths,
            'production': prod,
            'materials_first_year': mats_y1,
            'materials_steady': mats_st,
            'materials_full': mats_full,
            'byproducts_steady': byproduct_output(prod['steady_output_t'], chain, ucs),
            'byproducts_full': byproduct_output(capacity_t, chain, ucs),
        })

    # ---- 4. 区域格局 ----
    reg_base = next((_f(b.get('value_t')) for b in bases if b.get('key') == 'regional'), 0.0)
    cons = next((_f(b.get('value_t')) for b in bases if b.get('key') == 'consumption'), 0.0)
    regional_dem = _f(regional.get('demand_t')) or cons
    regional_out = regional_position(regional, capacity_t, reg_base, regional_dem)
    # 区域供给增量（含同区域在建）
    # 注意：capacity_bases 里的 `pipeline` 是"区域内同期在建/拟建合计"，
    # 若该口径已包含本项目，再加本项目就重复计算。用 pipeline_includes_project 声明口径。
    regional_pipeline = _f(regional.get('pipeline_t'))
    incl = regional.get('pipeline_includes_project')
    if incl is True:
        supply_inc = regional_pipeline
        supply_note = 'pipeline_t 口径已含本项目，增量直接取 pipeline_t'
    elif incl is False:
        supply_inc = capacity_t + regional_pipeline
        supply_note = 'pipeline_t 口径不含本项目，增量 = 本项目 + 在建'
    else:
        supply_inc = capacity_t + regional_pipeline
        supply_note = '⚠ pipeline_t 是否含本项目未声明，按“不含”处理，请在 regional.pipeline_includes_project 中写明口径'
    regional_out['pipeline_t'] = round(regional_pipeline, 2)
    regional_out['regional_supply_increase_t'] = round(supply_inc, 2)
    regional_out['regional_supply_increase_pct'] = (
        None if reg_base <= 0 else round(supply_inc / reg_base * 100, 2))
    regional_out['supply_increase_note'] = supply_note
    regional_out['new_capacity_share_pct'] = None if reg_base <= 0 else round(capacity_t / reg_base * 100, 2)

    # 邻居距离
    loc = proj.get('location') or {}
    neighbors = []
    for n in (regional.get('neighbors') or []):
        d = _f(n.get('distance_km'))
        if d <= 0:
            d = haversine_km(loc.get('lat'), loc.get('lon'), n.get('lat'), n.get('lon')) or 0.0
        nn = dict(n)
        nn['distance_km'] = d
        neighbors.append(nn)
    neighbors.sort(key=lambda x: x.get('distance_km') or 99999)
    regional_out['neighbors'] = neighbors
    regional_out['radius_bands'] = _radius_bands(capacity_t, neighbors)

    # ---- 5. 受影响对象与影响强度 ----
    st_out = []
    # 体量基准：优先用"该对象所对应的本项目的量"
    upstream_demand_by_mat = {m['material']: m['demand_t'] for m in
                              (scenarios_out[0]['materials_steady'] if scenarios_out else [])}
    for st in stakeholders:
        basis = st.get('impact_basis') or {}
        vol_t = _f(basis.get('volume_basis_t'))
        if vol_t <= 0:
            vol_t = _f(st.get('capacity_t'))
        if vol_t <= 0:
            # 上游节点用"本项目对该原料的稳态需求"
            for k, v in upstream_demand_by_mat.items():
                if k and k in str(st.get('name', '')):
                    vol_t = v
                    break
        # 分母：该节点所处市场的体量
        market_t = _f(basis.get('market_t'))
        if market_t <= 0:
            market_t = _market_base_for(st.get('type'), st, bases, regional)
        share = (vol_t / market_t) if market_t > 0 else 0.0
        sc = impact_score(share,
                          transmission=_f(basis.get('transmission'), 1.0),
                          lag=_f(basis.get('lag'), 1.0),
                          level=(st.get('evidence') or {}).get('level', 'E5'))
        row = dict(st)
        row['impact'] = sc
        row['volume_basis_t'] = round(vol_t, 2)
        row['market_t'] = round(market_t, 2)
        row['distance_km'] = None
        if st.get('lat') and loc.get('lat'):
            row['distance_km'] = haversine_km(loc.get('lat'), loc.get('lon'), st.get('lat'), st.get('lon'))
        st_out.append(row)
    st_out.sort(key=lambda x: x['impact']['score'], reverse=True)
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for r in st_out:
        by_type.setdefault(r.get('type', 'other'), []).append(r)

    # ---- 6. 结论分类（事实 / 计算 / 情景） ----
    conclusions = classify_conclusions(project, shares, scenarios_out, regional_out, coeff)

    return {
        'meta': meta,
        'project': proj,
        'chain': chain,
        'unit_consumption': ucs,
        'assumptions': assumptions,
        'inputs': {
            'capacity_t': capacity_t,
            'capacity_10kt': round(capacity_t / 10000, 2),
            'start_year': start_year,
            'start_month': start_month,
            'steady_lf': steady_lf,
            'ramp_model': ramp_model,
            'ramp_months': ramp_months,
        },
        'shares': shares,
        'coefficients': coeff,
        'coefficients_range': coeff_range,
        'scenarios': scenarios_out,
        'regional': regional_out,
        'stakeholders': st_out,
        'stakeholders_by_type': by_type,
        'conclusions': conclusions,
        'facts': project.get('facts') or [],
        'gaps': project.get('gaps') or [],
        'sources': project.get('sources') or [],
    }


def _radius_bands(new_t: float, neighbors: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bands = [(0, 100), (100, 300), (300, 500), (500, 1000), (1000, 99999)]
    labels = ['≤100 km', '100–300 km', '300–500 km', '500–1000 km', '>1000 km']
    out = []
    for (lo, hi), lb in zip(bands, labels):
        members = [n for n in neighbors if lo < (n.get('distance_km') or 0) <= hi or (lo == 0 and (n.get('distance_km') or 0) <= hi)]
        cap = sum(_f(n.get('capacity_t')) for n in members)
        out.append({
            'band': lb, 'count': len(members), 'capacity_t': round(cap, 2),
            'share_pct': None if cap <= 0 else round(new_t / cap * 100, 2),
            'members': [n.get('name') for n in members],
        })
    return out


def _market_base_for(stype: Optional[str], st: Dict[str, Any],
                     bases: Sequence[Dict[str, Any]],
                     regional: Dict[str, Any]) -> float:
    """给不同节点类型选默认市场分母。"""
    def base(key):
        return next((_f(b.get('value_t')) for b in bases if b.get('key') == key), 0.0)
    if stype == 'competitor':
        return base('radius') or base('regional') or base('national')
    if stype == 'upstream':
        return base('national')
    if stype == 'downstream':
        return base('consumption') or base('national')
    if stype == 'logistics':
        return base('regional') or base('national')
    if stype == 'byproduct':
        return _f(st.get('capacity_t')) or base('national')
    return base('national')


def _coefficient_range(chain: Optional[Dict[str, Any]],
                       uc_list: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """单耗区间连乘：给出每种原料的 [下限, 基准, 上限] 系数。

    每条路径独立连乘后求和，保证多路径（如均聚路径 + 共聚单体路径）口径一致。
    """
    ucs = normalize_uc(uc_list)
    out: Dict[str, Dict[str, float]] = {}
    base_map = cumulative_ratio(chain, uc_list)
    for name, c in base_map.items():
        paths = c.get('paths') or [c.get('parts', [])]
        lo = hi = mid = 0.0
        for parts in paths:
            plo = phi = pmid = 1.0
            for p in parts:
                u = ucs.get(p.get('key')) or {}
                rng = u.get('range') or []
                purity = _f(u.get('purity'), 1.0) or 1.0
                v = _f(u.get('value'), 0.0)
                if len(rng) == 2:
                    plo *= _f(rng[0]) / purity
                    phi *= _f(rng[1]) / purity
                else:
                    plo *= v / purity
                    phi *= v / purity
                pmid *= v / purity
            lo += plo
            hi += phi
            mid += pmid
        if not any(paths):
            lo = hi = mid = c['coefficient']
        out[name] = {'low': round(lo, 6), 'mid': round(mid, 6), 'high': round(hi, 6)}
    return out


def classify_conclusions(project: Dict[str, Any], shares: List[Dict[str, Any]],
                         scenarios: List[Dict[str, Any]], regional: Dict[str, Any],
                         coeff: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """把结论机械地分成三类：已确认事实 / 有依据的计算 / 基于假设的情景。"""
    proj = project.get('project') or {}
    facts_out: List[Dict[str, Any]] = []
    calc_out: List[Dict[str, Any]] = []
    scen_out: List[Dict[str, Any]] = []

    # 事实：来自 project.detail / facts
    for f in (project.get('facts') or []):
        if f.get('category') == '事实':
            facts_out.append(f)

    # 计算：占比、原料系数（只依赖事实的部分）
    for s in shares:
        if s['share'] is None:
            continue
        calc_out.append({
            'text': f"{proj.get('name', '本项目')}设计产能 {_t(_f(proj.get('design_capacity_t')))} 万吨/年，"
                    f"相当于{s['label']}（{s.get('year') or '—'}年，{s.get('scope') or '口径未注明'}）的 "
                    f"{s['share_pct']:.2f}%，档位：{s['tier']}",
            'basis': f"新增设计产能 ÷ 分母 {_t(s['base_t'])} 万吨",
            'level': s.get('level', 'E5'),
        })
    for name, c in coeff.items():
        calc_out.append({
            'text': f"按链上单耗连乘，每吨本产品需 {name} {c['coefficient']:.4f} 吨"
                    f"（含纯度折算），原料需求系数 = Π(单耗/纯度)",
            'basis': ' × '.join(f"{p.get('key')}={p.get('value')}/{p.get('purity')}"
                               for p in c.get('parts', [])) or '—',
            'level': max((p.get('evidence_level', 'E5') for p in c.get('parts', [])), default='E5'),
        })

    # 情景：所有依赖假设的产量与原料需求
    for s in scenarios:
        p = s['production']
        scen_out.append({
            'scenario': s['id'],
            'label': s['label'],
            'text': f"{s['start_year']} 年 {s['start_month']} 月开车、稳定开工率 {s['steady_lf'] * 100:.0f}%、"
                    f"{s['ramp_model']} 爬坡 {s['ramp_months']} 个月 → 投产当年产量 "
                    f"{_t(p['first_year_output_t'])} 万吨（占设计产能 {p['first_year_ratio'] * 100:.1f}%），"
                    f"稳定运行后年产量 {_t(p['steady_output_t'])} 万吨",
            'kind': s['kind'],
        })

    return {'facts': facts_out, 'calc': calc_out, 'scenarios': scen_out}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description='chem-capacity-impact 计算引擎')
    ap.add_argument('project_json')
    ap.add_argument('--out', help='输出 data.json 路径')
    ap.add_argument('--summary', action='store_true', help='只打印摘要')
    a = ap.parse_args(argv)

    with open(a.project_json, 'r', encoding='utf-8-sig') as fh:
        project = json.load(fh)
    data = compute_all(project)

    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print(f'[ok] wrote {a.out}')

    if a.summary or not a.out:
        print(f"设计产能 : {data['inputs']['capacity_10kt']} 万吨/年")
        for s in data['shares']:
            pct = '—' if s['share_pct'] is None else f"{s['share_pct']:.2f}%"
            print(f"  占比 {s['label']:<16} : {pct:>8}  档位 {s['tier']}")
        print('原料系数 :')
        for k, v in data['coefficients'].items():
            print(f"  {k:<10} {v['coefficient']:.4f} t/t   on_site={v['on_site']}")
        for s in data['scenarios']:
            p = s['production']
            print(f"情景 {s['id']:<4} {s['label']:<6} 首年 {_t(p['first_year_output_t'])} 万吨"
                  f" ({p['first_year_ratio'] * 100:.1f}%)  稳态 {_t(p['steady_output_t'])} 万吨")
        print(f"区域自给率 : {data['regional']['self_sufficiency_before']} → "
              f"{data['regional']['self_sufficiency_after']}  "
              f"({data['regional']['flow_before']} → {data['regional']['flow_after']})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
