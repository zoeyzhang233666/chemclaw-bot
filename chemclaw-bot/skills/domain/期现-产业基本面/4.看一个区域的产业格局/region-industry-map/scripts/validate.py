#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 regions.json：门槛规则（gate）全部可执行。

用法:
  python validate.py regions.json            # 仅检查
  python validate.py regions.json --strict   # 警告也当错误（交付前跑一次）

error 会阻断构建；warning 允许构建但必须在下一次迭代清掉。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

ATTR_PAT = ('总部', '办公', '研发中心', '写字楼', '大厦', '商务区', '金融街', 'CBD')
PREDICT_PAT = ('预计将', '必将', '一定会', '势必', '毫无疑问将')


def check(D):
    E, W = [], []
    raw = D
    D = common.normalize(json.loads(json.dumps(D)))
    M = D['meta']
    site = D.get('sites', [])
    src = {s['id']: s for s in D.get('sources', []) if s.get('id')}

    # ---------- 0 结构 ----------
    if not D.get('sites') and not D.get('cities'):
        E.append('sites 与 cities 同时为空：没有任何可核对的事实')
    if not D.get('sources'):
        E.append('sources 为空：每个数字都必须能指回一个来源')
    for k in ('product', 'region', 'asof'):
        if not M.get(k):
            E.append('meta.%s 为空' % k)

    # ---------- 1 来源引用 ----------
    def ref_ok(ids, where):
        for x in ids or []:
            if x not in src:
                E.append('%s 引用了未登记的来源 id：%s' % (where, x))

    for s in site:
        ref_ok(s.get('source_ids'), 'sites[%s]' % (s.get('site_id') or s.get('site_name')))
        if not s.get('source_ids'):
            W.append('站点 %s 没有来源 id（只能是"未核实"，不得进入产能合计）' % s.get('site_name'))
        if not s.get('raw_capacity') and (s.get('capacity') is not None) and not s.get('capacity_note'):
            E.append('站点 %s 有产能数值 %s 但没有 raw_capacity / capacity_note 原文' % (s.get('site_name'), s.get('capacity')))
    for p in D.get('projects', []):
        ref_ok(p.get('source_ids'), 'projects[%s]' % (p.get('name') or p.get('id')))
        if not p.get('status_asof'):
            E.append('项目 %s 缺 status_asof（状态必须锁一个时点）' % (p.get('name') or p.get('id')))
        if (p.get('net') or 0) < 0 and not p.get('capacity_retired'):
            W.append('项目 %s 净增量为负但没有填 capacity_retired' % (p.get('name') or p.get('id')))
    for n in D.get('flows', []):
        ref_ok(n.get('source_ids'), 'flows[%s]' % n.get('id'))

    # ---------- 2 注册地址 vs 工厂地址 ----------
    for s in site:
        at = (s.get('address') or '') + (s.get('reg_address') or '')
        if s.get('reg_address_type') == '实际生产地址' and s.get('plant_address') and s['reg_address'] == s['plant_address']:
            W.append('站点 %s 的注册地址与实际生产地址完全相同——确认是"厂区内注册"还是复制粘贴' % s.get('site_name'))
        same = (s.get('reg_address') or '') and s.get('plant_address') == (s.get('reg_address'))
        on_site = '同址' in (s.get('reg_address_type') or '')
        if s.get('precision') == '精确' and same and not on_site:
            E.append('站点 %s 标为精确点位，但生产地址与注册地址一致且未注明"同址"，疑似用总部地址当装置位置'
                     % s.get('site_name'))
        # 仓储/贸易据点不是装置：注册地即经营场所，允许同址
        if s.get('role') == 'trader' and s.get('precision') == '精确':
            W.append('站点 %s 是贸易/仓储据点：精确点位只代表仓库位置，不参与产能与集中度统计' % s.get('site_name'))
        for k in ATTR_PAT:
            if s.get('precision') == '精确' and k in (s.get('plant_address') or ''):
                E.append('站点 %s 的"生产地址"含"%s"，公司总部/写字楼地址不能作为装置位置' % (s.get('site_name'), k))
            if k in (s.get('name') or '') and s.get('precision') == '精确':
                W.append('站点名 %s 含"%s"，请确认这是工厂而不是注册主体' % (s.get('name'), k))

    # ---------- 3 坐标与精度 ----------
    seen_coord = {}
    for s in site:
        lon, lat = s.get('lon'), s.get('lat')
        if s.get('precision') == '精确':
            if lon is None or lat is None:
                E.append('站点 %s 标为精确但没有经纬度' % s.get('site_name'))
            elif not (73 <= float(lon) <= 135 and 3 <= float(lat) <= 54):
                E.append('站点 %s 坐标不在中国境内：%s,%s' % (s.get('site_name'), lon, lat))
            if s.get('coord_source') in (None, '', '未核实'):
                W.append('站点 %s 标为精确但 coord_source 为未核实' % s.get('site_name'))
            key = (round(float(lon), 2), round(float(lat), 2))
            seen_coord.setdefault(key, []).append(s.get('site_name'))
        elif lon is not None and s.get('precision') in ('县级', '市级'):
            W.append('站点 %s 精度为 %s 却填了坐标：地图上只用地区位置，不要当装置点位'
                     % (s.get('site_name'), s.get('precision')))
    for k, v in seen_coord.items():
        if len(v) > 2:
            W.append('坐标 %s 被 %d 个站点共用（%s）：确认是不是同一园区的统一定位' % (k, len(v), ', '.join(v)))

    # ---------- 4 数量与产能口径 ----------
    for s in site:
        cap = s.get('capacity')
        raw = s.get('raw_capacity')
        if cap is not None and not isinstance(cap, (int, float)):
            E.append('站点 %s 的 capacity 不是数字（应换算成数值，原文放 raw_capacity）' % s.get('site_name'))
        if isinstance(raw, str):
            import re
            nums = [float(x.replace(',', '')) for x in re.findall(r'\d+(?:\.\d+)?', raw)]
            if nums and cap is not None:
                # 原文是"万吨/年"或"吨/年"时，数值必须能对上
                if '吨' in raw and not any(abs(n - abs(cap)) < 1e-6 or abs(n / 10000 - abs(cap)) < 1e-6 for n in nums):
                    W.append('站点 %s：原文"%s"与 capacity=%s 对不上，请复核单位（万吨 vs 吨）' % (s.get('site_name'), raw, cap))
    # 重复主体：同名同址不算重复，同名不同址要拆
    agg = {}
    for s in site:
        if s.get('role') != 'production':
            continue
        k = (common.norm_entity(s.get('company')), s.get('city'), s.get('site_name'))
        agg.setdefault(k, []).append(s)
    for k, v in agg.items():
        if len(v) > 1:
            W.append('疑似重复站点：%s 出现 %d 次（同一工厂多份材料），请合并为一条' % (k[2], len(v)))

    # ---------- 5 产能覆盖 ----------
    A = D['_agg']
    for c in D.get('cities', []):
        k = common._city_key(c.get('province'), c.get('city'))
        a = A['by_city'].get(k)
        base = c.get('capacity') or c.get('capacity_covered')
        if base and a and a['capacity_sample'] > base * 1.02:
            E.append('城市 %s 的站点产能合计 %.2f 超过公开产能口径 %.2f：检查是否把姐妹公司/多厂区重复计数'
                     % (c.get('city'), a['capacity_sample'], base))
        if base and a and a['coverage'] is not None and a['coverage'] < 60:
            W.append('城市 %s 产能覆盖仅 %s%%：产能图与集中度需标注"样本口径"' % (c.get('city'), a['coverage']))

    # ---------- 6 枚举 ----------
    for s in site:
        if s.get('route') and s['route'] != '—' and s['route'] not in common.PROCESSES:
            W.append('站点 %s 的工艺 "%s" 不在枚举内' % (s.get('site_name'), s['route']))
        if s.get('role') not in ('production', 'trader', 'downstream'):
            E.append('站点 %s 的 role 必须是 production/trader/downstream' % s.get('site_name'))
        if s.get('evidence_grade') not in ('A', 'B', 'C', 'D'):
            W.append('站点 %s 的 evidence_grade 必须是 A/B/C/D' % s.get('site_name'))

    # ---------- 7 判断句 ----------
    for key in ('conclusions', 'narrative', 'notes'):
        v = D.get(key)
        texts = []
        if isinstance(v, str):
            texts = [v]
        elif isinstance(v, list):
            for x in v:
                texts += [x] if isinstance(x, str) else [str(x.get('text', '')) for x in [x]]
        for t in texts:
            for pat in PREDICT_PAT:
                if pat in (t or ''):
                    E.append('出现预测性表述"%s"：改写成"过去 X 如何、下一步看什么指标"：%s' % (pat, t[:40]))

    # ---------- 8 覆盖声明 ----------
    nv = D.get('narrative') or {}
    if not nv.get('gaps'):
        W.append('narrative.gaps 为空：至少写出缺哪些城市/哪些产能口径')
    if not nv.get('coverage_note'):
        W.append('narrative.coverage_note 为空：必须在报告里说明"样本合计 ≠ 全局产能"')
    prod = [s for s in site if s.get('role') == 'production']
    if not prod:
        E.append('没有任何生产企业站点')
    unmapped = [s for s in site if s.get('lon') is None]
    if unmapped:
        W.append('%d 个站点没有坐标（只能作地区级记录）：%s' % (len(unmapped), ', '.join(s.get('site_name') or '' for s in unmapped[:6])))
    return E, W


def main():
    ap = sys.argv[1:]
    if not ap:
        sys.exit(__doc__)
    path = ap[0]
    strict = '--strict' in ap
    with open(path, encoding='utf-8') as f:
        D = json.load(f)
    E, W = check(D)
    for x in E:
        print('[ERROR]', x)
    for x in W:
        print('[WARN ]', x)
    print('—— error %d / warning %d' % (len(E), len(W)))
    if E or (strict and W):
        sys.exit(1)


if __name__ == '__main__':
    main()
