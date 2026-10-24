#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公共层：读 regions.json → 规范化 → 计算覆盖、集中度、地址层级、重复主体。

生成器（HTML / Excel）只依赖 load() 的结果，换品种、换区域只换 JSON。
所有"算出来"的数字都带口径名（*_basis），不允许出现无来源的派生数值。
"""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
TEMPLATES = os.path.join(HERE, 'templates')

# ---------------------------------------------------------------- 枚举
SITE_TYPES = ('生产工厂', '一体化/配套装置', '在建项目', '贸易/仓储', '下游用户', '原料基地', '园区节点')
FEATURE_TYPES = ('生产企业', '上游原料', '下游用户', '化工园区', '新增项目', '贸易与物流')
PROCESSES = ('氨碱', '联碱', '天然碱', '其他', '未知')
PRECISIONS = ('精确', '园区级', '县级', '市级')
COORD_SOURCES = ('企业官网', '政府公示', '园区公开资料', '新闻报道', '地图地名库', '人工核对', '未核实')
ADDR_TYPES = ('实际生产地址', '园区地址', '镇村地名', '县级地名', '市级地名', '未核实')
SECRECY_LABEL = {
    '精确': '已公开精确坐标（点位可作装置位置使用）',
    '园区级': '园区级定位（代表园区位置，非装置位置）',
    '县级': '县级定位（仅在县域内示意）',
    '市级': '市级定位（仅在城市内示意）',
}

PROV_CENTER = {
    '上海': [121.47, 31.23], '江苏': [118.78, 32.06], '浙江': [120.15, 30.28],
    '安徽': [117.28, 31.86], '福建': [119.30, 26.08], '江西': [115.89, 28.68],
    '山东': [117.02, 36.67], '北京': [116.40, 39.90], '天津': [117.20, 39.13],
    '河北': [114.50, 38.05], '山西': [112.55, 37.87], '内蒙古': [111.75, 40.84],
    '辽宁': [123.43, 41.81], '吉林': [125.32, 43.90], '黑龙江': [126.64, 45.76],
    '河南': [113.65, 34.76], '湖北': [114.30, 30.59], '湖南': [112.98, 28.19],
    '广东': [113.26, 23.13], '广西': [108.32, 22.82], '海南': [110.35, 20.02],
    '重庆': [106.55, 29.56], '四川': [104.07, 30.67], '贵州': [106.71, 26.58],
    '云南': [102.71, 25.04], '西藏': [91.13, 29.65], '陕西': [108.95, 34.27],
    '甘肃': [103.82, 36.06], '青海': [101.78, 36.62], '宁夏': [106.28, 38.47],
    '新疆': [87.62, 43.79],
}
PROV_ALIAS = {'内蒙': '内蒙古', '广西壮族自治区': '广西', '新疆维吾尔自治区': '新疆', '宁夏回族自治区': '宁夏'}


def norm_prov(p):
    p = (p or '').strip()
    p = PROV_ALIAS.get(p, p)
    for suf in ('省', '市', '自治区'):
        if p.endswith(suf) and p[:-len(suf)] in PROV_CENTER:
            return p[:-len(suf)]
    return p


def norm_city(c):
    c = (c or '').strip()
    for suf in ('市', '地区', '自治州', '盟'):
        if c.endswith(suf) and len(c) > len(suf) + 1:
            return c[:-len(suf)]
    return c


_ENTITY_NOISE = re.compile(r'(股份有限公司|有限责任公司|有限公司|集团|股份|厂|分公司|公司)')


def norm_entity(name):
    """主体归一：去括号、去组织形式后缀，用于去重与集团归并。"""
    n = re.sub(r'[（(][^）)]*[）)]', '', name or '')
    n = _ENTITY_NOISE.sub('', n)
    n = re.sub(r'\s+', '', n)
    return n


_KEY_PLANTS = re.compile(r'纯碱|碳酸钠|小苏打|氯化铵|联碱|氨碱|天然碱')


def is_soda_plant(p):
    """该厂区是否实际涉及本品（仅名义上的关联主体不算）。"""
    txt = ' '.join(str(p.get(k, '')) for k in ('products', 'site_name', 'name', 'type'))
    return bool(_KEY_PLANTS.search(txt))


def _num(v):
    return v if isinstance(v, (int, float)) else None


def hhi(values):
    """Herfindahl-Hirschman Index（0–10000），输入为一组份额（%）。"""
    tot = sum(v for v in values if v and v > 0)
    if not tot:
        return None
    return round(sum((v / tot * 100.0) ** 2 for v in values if v and v > 0), 0)


def cr_n(values, n):
    tot = sum(v for v in values if v and v > 0)
    if not tot:
        return None
    top = sum(sorted((v for v in values if v and v > 0), reverse=True)[:n])
    return round(top / tot * 100.0, 1)


def coverage(covered, total):
    if not total:
        return None
    return round(covered / total * 100.0, 1)


# ---------------------------------------------------------------- 读入
def load(path):
    with open(path, encoding='utf-8') as f:
        D = json.load(f)
    return normalize(D)


def normalize(D):
    M = D.setdefault('meta', {})
    M.setdefault('product', '某化工品')
    M.setdefault('region', '某区域')
    M.setdefault('asof', '')
    M.setdefault('capacity_unit', '万吨/年')
    M.setdefault('title', '%s · %s 产业格局' % (M['product'], M['region']))
    M.setdefault('filters', {})
    site = D.setdefault('sites', [])
    comp = {c['id']: c for c in D.get('companies', []) if c.get('id')}
    parks = {p['id']: p for p in D.get('parks', []) if p.get('id')}
    cities = {c['id']: c for c in D.get('cities', []) if c.get('id')}
    projs = D.setdefault('projects', [])
    flow = D.setdefault('flows', [])
    nodes = D.setdefault('nodes', [])

    # ---- 站点：归一化 + 地址层级 ----
    for s in site:
        s['province'] = norm_prov(s.get('province'))
        s['city'] = norm_city(s.get('city'))
        s.setdefault('precision', '市级')
        if s['precision'] not in PRECISIONS:
            s['precision'] = '市级'
        s.setdefault('coord_source', '未核实')
        s.setdefault('address_type', '未核实')
        s.setdefault('raw_capacity', None)
        s.setdefault('capacity', None)
        s.setdefault('products', [])
        s.setdefault('source_ids', [])
        s.setdefault('evidence_grade', 'C')
        s.setdefault('status', '在产')
        s.setdefault('role', 'production')
        c = comp.get(s.get('company_id')) or {}
        s['company'] = c.get('name') or s.get('company') or '—'
        s['group'] = c.get('group') or s['company']
        p = parks.get(s.get('park_id')) or {}
        s['park'] = p.get('name') or s.get('park') or ''
        s['city_id'] = _city_key(s['province'], s['city'])
        # 有精确坐标才算"可作装置位置使用"
        if s.get('lon') is None or s.get('lat') is None:
            s['precision'] = '市级' if s['precision'] in ('精确', '园区级') else s['precision']
        s['coordinate_usable'] = bool(s['precision'] == '精确' and s.get('lon') is not None)
        # 注册地址 ≠ 工厂地址：注册地址永远不作点位，只进表格
        s.setdefault('layers', [])

    # ---- 城市：补坐标（用其下最精确站点的均值，否则省会/市名） ----
    for c in D.get('cities', []):
        c['province'] = norm_prov(c.get('province'))
        c.setdefault('capacity', None)
        c.setdefault('capacity_covered', None)
        c.setdefault('registered', 0)
        c.setdefault('downstream', 0)
        if c.get('lon') is None or c.get('lat') is None:
            pts = [s for s in site if s.get('city') == c.get('city') and s.get('lon') is not None]
            if pts:
                c['lon'] = round(sum(s['lon'] for s in pts) / len(pts), 4)
                c['lat'] = round(sum(s['lat'] for s in pts) / len(pts), 4)
                c['coord_fallback'] = '派生：本城市已定位站点的重心'
            else:
                key = c.get('province')
                pc = PROV_CENTER.get(key) or PROV_CENTER.get(c.get('city'), [113.0, 33.0])
                c['lon'], c['lat'] = pc
                c['coord_fallback'] = '省会坐标（本城市无已定位站点）'

    # ---- 区域汇总（省 / 市） ----
    D['_agg'] = _aggregate(D, site, projs)

    # ---- 项目：净增量 ----
    for p in projs:
        p.setdefault('capacity', 0)
        p.setdefault('capacity_retired', 0)
        p.setdefault('net', (p.get('capacity') or 0) - (p.get('capacity_retired') or 0))
        p.setdefault('precision', '县级')
        p['province'] = norm_prov(p.get('province'))
        p['city'] = norm_city(p.get('city'))
        p['city_id'] = _city_key(p['province'], p['city'])
        p['coordinate_usable'] = bool(p['precision'] == '精确' and p.get('lon') is not None)

    # ---- 下游能力指数（相对权重，非吨位） ----
    for n in nodes:
        n['province'] = norm_prov(n.get('province'))
        n['city'] = norm_city(n.get('city'))
        if n.get('lon') is not None:
            n.setdefault('precision', '精确')
        else:
            n['precision'] = n.get('precision', '市级')

    # ---- flows 端点城市名归一 ----
    for f in flow:
        f.setdefault('basis', '定性')
    return D


def _city_key(prov, city):
    return '%s|%s' % (prov or '', city or '')


def _aggregate(D, site, projs):
    """按城市 / 省份汇总，并给出覆盖口径。"""
    M = D['meta']
    units = M.get('capacity_unit', '万吨/年')
    park_by_id = {p['id']: p for p in D.get('parks', []) if p.get('id')}
    cities = {}
    for c in D.get('cities', []):
        k = _city_key(c.get('province'), c.get('city'))
        cities[k] = {
            'id': c.get('id') or k, 'city': c.get('city'), 'province': c.get('province'),
            'registered': c.get('registered', 0),
            'reg_unit': c.get('reg_unit', '家（估算）'),
            'capacity_declared': c.get('capacity'),
            'capacity_covered': c.get('capacity_covered'),
            'capacity_sample': 0.0, 'plants': 0, 'sites': 0,
            'trader_sites': 0, 'downstream_sites': 0, 'downstream_declared': c.get('downstream', 0),
            'parks': [], 'projects': 0, 'net_capacity': 0.0,
            'unresolved': 0, 'lon': c.get('lon'), 'lat': c.get('lat'),
            'coord_fallback': c.get('coord_fallback'),
            'data_grade': c.get('data_grade'), 'note': c.get('note'),
        }
    for s in site:
        k = s.get('city_id')
        a = cities.setdefault(k, {
            'id': k, 'city': s.get('city'), 'province': s.get('province'), 'registered': 0,
            'reg_unit': '家（估算）', 'capacity_declared': None, 'capacity_covered': None,
            'capacity_sample': 0.0, 'plants': 0, 'sites': 0, 'trader_sites': 0,
            'downstream_sites': 0, 'downstream_declared': 0, 'parks': [], 'projects': 0,
            'net_capacity': 0.0, 'unresolved': 0, 'lon': None, 'lat': None,
            'coord_fallback': '省会坐标（本城市无已定位站点）', 'data_grade': 'D', 'note': '',
        })
        a['sites'] += 1
        if s['role'] == 'production':
            a['plants'] += 1
            a['production_sites'] = a.get('production_sites', 0) + 1
            if s.get('capacity') is not None:
                a['plants_with_capacity'] = a.get('plants_with_capacity', 0) + 1
            a['capacity_sample'] += s.get('capacity') or 0
        elif s['role'] == 'trader':
            a['trader_sites'] += 1
        elif s['role'] == 'downstream':
            a['downstream_sites'] += 1
        if s.get('park_id') and park_by_id.get(s['park_id'], {}).get('name') not in [p['name'] for p in a['parks']]:
            pid = s['park_id']
            if pid not in [p['id'] for p in a['parks']]:
                a['parks'].append({'id': pid, 'name': park_by_id.get(pid, {}).get('name', pid)})
        if s.get('precision') in ('县级', '市级'):
            a['unresolved'] += 1
    for p in projs:
        k = p.get('city_id')
        if k in cities:
            cities[k]['projects'] += 1
            cities[k]['net_capacity'] += p.get('net') or 0

    for a in cities.values():
        a['capacity_sample'] = round(a['capacity_sample'], 2)
        a['net_capacity'] = round(a['net_capacity'], 2)
        base = a.get('capacity_declared') or a.get('capacity_covered')
        a['coverage'] = coverage(a['capacity_sample'], base)
        a['gap'] = (round((base or 0) - a['capacity_sample'], 2) if base else None)

    prov = {}
    for a in cities.values():
        pv = prov.setdefault(a['province'], {
            'province': a['province'], 'cities': 0, 'registered': 0, 'capacity_declared': 0.0,
            'capacity_covered': 0.0, 'capacity_sample': 0.0, 'plants': 0, 'sites': 0,
            'trader_sites': 0, 'downstream_sites': 0, 'parks': [], 'projects': 0,
            'net_capacity': 0.0, 'unresolved': 0,
        })
        pv['cities'] += 1
        pv['registered'] += a.get('registered') or 0
        pv['capacity_declared'] += a.get('capacity_declared') or 0
        pv['capacity_covered'] += a.get('capacity_covered') or 0
        pv['capacity_sample'] += a.get('capacity_sample') or 0
        pv['plants'] += a['plants']
        pv['sites'] += a['sites']
        pv['trader_sites'] += a['trader_sites']
        pv['downstream_sites'] += a['downstream_sites']
        pv['projects'] += a['projects']
        pv['net_capacity'] += a.get('net_capacity') or 0
        pv['unresolved'] += a['unresolved']
        for p in a['parks']:
            if p['id'] not in [q['id'] for q in pv['parks']]:
                pv['parks'].append(p)
    for pv in prov.values():
        pv['capacity_sample'] = round(pv['capacity_sample'], 2)
        pv['net_capacity'] = round(pv['net_capacity'], 2)
        base = pv['capacity_declared'] or pv['capacity_covered'] or None
        pv['coverage'] = coverage(pv['capacity_sample'], base)
        pv['n_parks'] = len(pv['parks'])
        pv['cities_named'] = ', '.join(sorted({a['city'] for a in cities.values()
                                               if a['province'] == pv['province']}))

    # 计算口径的产能合计（只用"生产"角色站点，避免把配套装置重复计入）
    prod_sites = [s for s in site if s['role'] == 'production']
    cap_total_sample = round(sum(s.get('capacity') or 0 for s in prod_sites), 2)
    agg = {
        'by_city': cities, 'by_prov': prov,
        'capacity_sample_total': cap_total_sample,
        'plants_total': len(prod_sites),
        # 进产能合计的厂区数（有公开产能数值的生产厂区），报告里的"已核实生产厂区"用它
        'plants_capacity_total': sum(1 for s in prod_sites if s.get('capacity') is not None),
        'sites_total': len(site),
        'trader_sites_total': sum(1 for s in site if s['role'] == 'trader'),
        'downstream_sites_total': sum(1 for s in site if s['role'] == 'downstream'),
        'unresolved_total': sum(1 for s in site if s.get('precision') in ('县级', '市级')),
        'park_total': len(D.get('parks', [])),
        'registered_total': sum(c.get('registered') or 0 for c in D.get('cities', [])),
        'capacity_unit': units,
    }
    agg['cr1'] = None
    caps = sorted((s.get('capacity') or 0) for s in prod_sites)
    agg['cr3'] = cr_n(caps, 3)
    agg['cr5'] = cr_n(caps, 5)
    agg['hhi'] = hhi(caps)
    if caps:
        agg['cr1'] = round(caps[-1] / sum(caps) * 100, 1) if sum(caps) else None
    agg['net_capacity'] = round(sum(p.get('net') or 0 for p in projs if p.get('net') is not None), 2)
    agg['projects_total'] = len(projs)
    agg['coverage_total'] = coverage(cap_total_sample, (M.get('capacity_scope_total') or None))
    top = sorted(prod_sites, key=lambda x: -(x.get('capacity') or 0))[:8]
    agg['top_share'] = [{'name': s.get('site_name') or s.get('company'), 'company': s.get('company'),
                         'capacity': s.get('capacity'),
                         'share': round((s.get('capacity') or 0) / cap_total_sample * 100, 1)
                         if cap_total_sample else None} for s in top]
    return agg


def summary_numbers(D):
    M, A = D['meta'], D['_agg']
    return {
        'product': M['product'], 'region': M['region'],
        'capacity_unit': M.get('capacity_unit'),
        'plants_total': A['plants_total'],
        'plants_capacity_total': A.get('plants_capacity_total'),
        'capacity_sample_total': A['capacity_sample_total'],
        'sites_total': A['sites_total'], 'trader_sites_total': A['trader_sites_total'],
        'downstream_sites_total': A['downstream_sites_total'],
        'park_total': A['park_total'], 'unresolved_total': A['unresolved_total'],
        'registered_total': A['registered_total'],
        'cr3': A['cr3'], 'cr5': A['cr5'], 'hhi': A['hhi'],
        'projects': len(D.get('projects', [])),
        'net_capacity': round(sum(p.get('net') or 0 for p in D.get('projects', [])), 2),
    }


def payload(D):
    out = json.loads(json.dumps(D, ensure_ascii=False))
    out.pop('_agg', None)
    return out
