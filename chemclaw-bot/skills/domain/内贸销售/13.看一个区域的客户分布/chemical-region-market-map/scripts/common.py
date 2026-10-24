#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公共层：读 data.json，做归一化（汇总/评分/分档/坐标/天数/占比）。

所有生成器都只依赖这里的 normalize()，因此换产品/区域只需换 JSON。
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
TEMPLATES = os.path.join(HERE, 'templates')

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
    '新疆': [87.62, 43.79], '台湾': [121.52, 25.03], '香港': [114.17, 22.32],
    '澳门': [113.55, 22.20],
}

CITY_SUFFIX = ('市', '自治州', '地区', '盟', '县')


def _load_centers():
    p = os.path.join(ASSETS, 'city_centers.json')
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8') as f:
        return json.load(f)


CENTERS = _load_centers()


def city_lonlat(city, prov):
    """城市坐标：显式 → 城市库（含市/县后缀与'·'别名）→ 省会。"""
    if city.get('lon') is not None and city.get('lat') is not None:
        return float(city['lon']), float(city['lat'])
    name = city['city']
    cands = [name]
    if '·' in name:
        cands += [name.split('·')[0], name.split('·')[1]]
    for c in list(cands):
        for suf in ('', '市', '县'):
            cands.append(c + suf)
    for c in cands:
        for key in (c, c.replace('市', '')):
            if key in CENTERS:
                v = CENTERS[key]
                return float(v[0]), float(v[1])
    pc = PROV_CENTER.get(city.get('prov', ''), [113.0, 33.0])
    return float(pc[0]), float(pc[1]), True


def _tier_by_rank(n, ns=None):
    """S/A/B/C 分档：S≈11%（3–8 个），A/B 各 20%。"""
    s = ns if ns else min(8, max(3, int(round(n * 0.11))))
    a = int(round(n * 0.20))
    b = int(round(n * 0.20))
    out = []
    for i in range(n):
        if i < s:
            out.append('S')
        elif i < s + a:
            out.append('A')
        elif i < s + a + b:
            out.append('B')
        else:
            out.append('C')
    return out


def normalize(D, perday=4, keep_tiers=None):
    """就地补全派生字段并返回 D。"""
    lanes = {l['id']: l for l in D.get('lanes', [])}
    cities = D.get('cities', [])
    if not cities:
        raise SystemExit('data.json 里没有 cities')

    # 1) inds 的 kt / share 补齐
    for c in cities:
        inds = c.get('inds') or []
        nsum = sum((i.get('n') or 0) for i in inds) or 1
        for i in inds:
            i.setdefault('id', '')
            lane = lanes.get(i['id'], {})
            i.setdefault('name', lane.get('name', i['id']))
            if i.get('kt') is None:
                if i.get('share') is not None:
                    i['kt'] = round(c['demand'] * float(i['share']), 1)
                else:
                    i['kt'] = round(c['demand'] * (i.get('n') or 0) / nsum, 1)
            if i.get('share') is None:
                i['share'] = round(i['kt'] / c['demand'], 3) if c.get('demand') else 0
        inds.sort(key=lambda x: -x['kt'])
        c['inds'] = inds
        c['parks'] = c.get('parks') or []

    # 2) 项目增量
    for c in cities:
        if c.get('proj_kt') is None:
            c['proj_kt'] = round(sum(p.get('kt') or 0 for p in D.get('projects', [])
                                     if p.get('city') == c['city']), 1)

    # 3) 汇总
    s = D.get('summary') or {}
    s.setdefault('firms', sum(c['firms'] for c in cities))
    s.setdefault('traders', sum(c['traders'] for c in cities))
    s.setdefault('demand', round(sum(c['demand'] for c in cities), 1))
    s.setdefault('cities', len(cities))
    s.setdefault('parks', len({(c['city'], p['name']) for c in cities for p in c['parks']}))
    D['summary'] = s

    # 4) 单客户均值 / 建议天数
    for c in cities:
        c['avg'] = round(c['demand'] / c['firms'], 2) if c.get('firms') else 0
        c['days'] = max(1, int(round(c['firms'] / float(perday) + 0.4)))

    # 5) 机会指数
    mD = max(c['demand'] for c in cities) or 1
    mF = max(c['firms'] for c in cities) or 1
    mP = max(abs(c['proj_kt']) for c in cities) or 1
    mK = max(len(c['parks']) for c in cities) or 1
    raw = {}
    for c in cities:
        hi = sum(i['n'] for i in c['inds'] if (lanes.get(i['id'], {}).get('intensity') or 0) >= 4)
        big = (hi / c['firms']) if c.get('firms') else 0
        raw[c['city']] = (0.42 * c['demand'] / mD + 0.18 * c['firms'] / mF
                          + 0.18 * max(c['proj_kt'], 0) / mP + 0.10 * len(c['parks']) / mK
                          + 0.06 * min(c['traders'] / 40.0, 1) + 0.06 * big)
    mx = max(raw.values()) or 1
    for c in cities:
        c['score'] = round(100 * raw[c['city']] / mx, 1)
    cities.sort(key=lambda c: -c['score'])
    for i, c in enumerate(cities):
        c['rank'] = i + 1

    # 6) 分档：给了 tier 就用给的（保持作者判断），否则按排名
    if not any(c.get('tier') for c in cities):
        tiers = _tier_by_rank(len(cities), keep_tiers)
        for c, t in zip(cities, tiers):
            c['tier'] = t

    # 7) 坐标
    for c in cities:
        ll = city_lonlat(c, c.get('prov'))
        c['lon'], c['lat'] = ll[0], ll[1]
        if len(ll) > 2:
            c['_geo_fallback'] = True

    # 8) 省级：缺则聚合
    if not D.get('provinces'):
        agg = {}
        for c in cities:
            a = agg.setdefault(c['prov'], {'prov': c['prov'], 'cities': 0, 'firms': 0,
                                           'traders': 0, 'demand': 0})
            a['cities'] += 1
            a['firms'] += c['firms']
            a['traders'] += c['traders']
            a['demand'] += c['demand']
        D['provinces'] = [{**v, 'demand': round(v['demand'], 1), 'judge': ''}
                          for v in agg.values()]
    D['provinces'].sort(key=lambda p: -p['demand'])

    # 9) 企业：补下游名与城市归属
    for x in D.get('companies', []):
        x.setdefault('conf', '中')
        x.setdefault('kt', None)
        x['lane_name'] = lanes.get(x.get('lane', ''), {}).get('name', '')
    return D


def load(path, perday=4):
    with open(path, encoding='utf-8') as f:
        D = json.load(f)
    return normalize(D, perday=perday)


def payload(D):
    """压缩成前端 JSON（去掉下划线内部字段）。"""
    out = json.loads(json.dumps(D, ensure_ascii=False))
    for c in out['cities']:
        c.pop('_geo_fallback', None)
    return out


if __name__ == '__main__':
    d = load(sys.argv[1] if len(sys.argv) > 1 else 'data.json')
    print(json.dumps({'summary': d['summary'],
                      'tier': {t: sum(1 for c in d['cities'] if c['tier'] == t)
                               for t in 'SABC'},
                      'top5': [(c['city'], c['score'], c['tier']) for c in d['cities'][:5]]},
                     ensure_ascii=False, indent=1))
