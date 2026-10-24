#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 data.json。error 阻断构建，warning 只提示。

用法: python validate.py data.json [--strict]
"""
import json
import re
import sys

TYPES = {'生产', '贸易', '同行', '误判'}
CONFS = {'高', '中', '低'}
PRIORITY = {'生产': 0, '贸易': 1, '同行': 2, '误判': 3}


def check(D):
    E, W = [], []
    if not isinstance(D, dict):
        return ['顶层必须是对象'], []
    for k in ('meta', 'cities', 'lanes', 'companies', 'projects', 'prices', 'route', 'narrative'):
        if k not in D:
            E.append('缺少顶层键: %s' % k)
    if E:
        return E, W

    M = D['meta']
    for k in ('product', 'region', 'asof', 'demand_unit', 'demand_label'):
        if not M.get(k):
            E.append('meta 缺字段: %s' % k)
    if M.get('asof') and not re.match(r'^\d{4}-\d{2}-\d{2}$', M['asof']):
        E.append('meta.asof 应为 YYYY-MM-DD')
    if not (M.get('anchor') or {}).get('value'):
        W.append('meta.anchor 缺失：价格锚点是价格对比的基准，建议补齐')

    cities = D['cities']
    names = [c.get('city') for c in cities]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        E.append('城市重名: %s' % '、'.join(sorted(dup)))
    for c in cities:
        for k in ('city', 'prov', 'firms', 'traders', 'demand'):
            if c.get(k) is None:
                E.append('城市 %s 缺字段 %s' % (c.get('city', '?'), k))
        if c.get('firms') is None or c.get('demand') is None:
            continue
        if c['firms'] <= 0:
            W.append('%s 生产企业数为 0，确认是否漏填' % c['city'])
        shs = [i.get('share') for i in (c.get('inds') or []) if i.get('share') is not None]
        if shs and abs(sum(shs) - 1) > 0.05:
            W.append('%s 的下游占比之和=%.2f（应为 1；只填 n 时不用管这条）' % (c['city'], sum(shs)))
        for i in (c.get('inds') or []):
            if i.get('share') is not None and not (0 <= i['share'] <= 1):
                E.append('%s 的下游 %s share 不在 0–1' % (c['city'], i.get('name')))
        if not c.get('note'):
            W.append('%s 缺 note（一句话判断）' % c['city'])

    lane_ids = {l.get('id') for l in D['lanes']}
    if len(D['lanes']) < 4:
        W.append('下游方向只有 %d 条，建议 8–12 条' % len(D['lanes']))
    for l in D['lanes']:
        for k in ('id', 'name', 'intensity', 'logic', 'hook'):
            if l.get(k) in (None, ''):
                E.append('下游 %s 缺字段 %s' % (l.get('name', l.get('id')), k))
        if l.get('intensity') not in (1, 2, 3, 4, 5):
            E.append('下游 %s 的 intensity 应为 1–5' % l.get('name'))

    cos = D['companies']
    for x in cos:
        if x.get('type') not in TYPES:
            E.append('企业 %s 的 type=%r 不在 %s' % (x.get('name'), x.get('type'), TYPES))
        if x.get('conf') not in CONFS:
            E.append('企业 %s 的 conf=%r 不在 %s' % (x.get('name'), x.get('conf'), CONFS))
        if x.get('lane') and x['lane'] not in lane_ids:
            W.append('企业 %s 引用了不存在的下游 %s' % (x.get('name'), x['lane']))
        src = (x.get('src') or '')
        if x.get('conf') == '高' and re.search(r'未核实|待核实|待确认', src):
            E.append('企业 %s 置信度=高 但来源写「未核实」，二者矛盾' % x.get('name'))
        if x.get('conf') in ('高', '中') and not src:
            E.append('企业 %s 置信度=%s 但无证据来源' % (x.get('name'), x.get('conf')))
        if x.get('type') == '生产' and x.get('conf') == '低':
            W.append('企业 %s 是生产型但置信度低，拜访前需先核实主体' % x.get('name'))
    if cos:
        n_prod = sum(1 for x in cos if x['type'] == '生产')
        if n_prod / len(cos) < 0.40:
            W.append('生产型只占 %.0f%%，疑似把同行/误判混进客户名单（跑一次 peer gate）'
                     % (n_prod / len(cos) * 100))

    projs = D['projects']
    ids = [p.get('id') for p in projs]
    if len(ids) != len(set(ids)):
        E.append('项目 id 重复')
    for p in projs:
        if p.get('kt') is None:
            W.append('项目 %s 缺 kt（需求增量），会让总量被低估' % p.get('id'))
        if p.get('conf') == '高' and not p.get('src'):
            E.append('项目 %s 置信度=高 但无来源' % p.get('id'))
    if not any((p.get('kt') or 0) < 0 for p in projs):
        W.append('没有负增量项目：冷修/减产/限产也决定真实增量，建议至少收 1 条')

    P = D['prices']
    if not P.get('regions'):
        E.append('prices.regions 为空：至少要有本地价与 2 个对比区')
    for r in P.get('regions', []):
        if not isinstance(r.get('v'), (int, float)):
            E.append('价格区 %s 的 v 不是数字' % r.get('name'))

    N = D.get('narrative') or {}
    for k in ('conclusions', 'method', 'gaps'):
        if not N.get(k):
            W.append('narrative.%s 为空：这一节决定文档可不可信' % k)
    if not N.get('usage'):
        W.append('narrative.usage 为空（使用说明）')
    peers = [x['name'] for x in cos if x.get('type') == '同行']
    if peers and not N.get('peer_notes'):
        W.append('有同行 %d 家但未写 peer_notes' % len(peers))
    if [x for x in cos if x.get('type') == '误判'] and not N.get('misread_notes'):
        W.append('有误判样本但未写 misread_notes')
    for c in N.get('conclusions') or []:
        if not re.search(r'\d', c):
            W.append('结论无数字：「%s」' % c[:24])

    seq = ' '.join(r.get('seq', '') for r in D['route'])
    miss = [n for n in set(names) if n not in seq and '·' not in n]
    if not D['route']:
        E.append('route 为空')
    elif len(miss) > len(names) * 0.6:
        W.append('route.seq 里匹配不到多数城市名，天数测算会失真')

    unit = M.get('demand_unit', '')
    tot = sum(c.get('demand') or 0 for c in cities)
    if '吨/年' in unit and '万' not in unit and tot < 100:
        E.append('单位是吨/年但全国合计只有 %.1f，量级明显不对（是不是按万吨填的？）' % tot)
    if '万吨' in unit and tot < 1:
        E.append('单位是万吨/年但合计只有 %.1f' % tot)
    return E, W


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'data.json'
    strict = '--strict' in sys.argv
    with open(path, encoding='utf-8') as f:
        D = json.load(f)
    E, W = check(D)
    for e in E:
        print('[ERROR]', e)
    for w in W:
        print('[WARN ]', w)
    print('\n%d error / %d warning' % (len(E), len(W)))
    if E or (strict and W):
        sys.exit(1)


if __name__ == '__main__':
    main()
