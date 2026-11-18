# -*- coding: utf-8 -*-
"""validate.py —— 交付前校验 research.json 是否符合数据契约与「三条硬规矩」

用法：
    python validate.py <案例目录或 research.json>

退出码：0 = 全部通过（可能有 warning）；1 = 存在 error。

检查项：
  A. 结构完整性（必填字段）
  B. 口径六要素：每个价格必须同时有 数值/规格/地区/含税口径/日期/来源
  C. 反编造：运费若为空必须是 null（不能是 0 冒充），到厂价不得在缺运费时出现
  D. 交货口径一致性提醒（自提 vs 送到 混用时必须登记 gap 或 assumption）
  E. 文案禁令：不得出现 预测/看涨/看跌/必涨/抄底 等措辞
  F. 线路里程必须有依据
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ERRORS, WARNS, OKS = [], [], []


def err(m): ERRORS.append(m)
def warn(m): WARNS.append(m)
def ok(m): OKS.append(m)


BANNED = ['预计涨', '预计跌', '预计将涨', '预计将跌', '看涨', '看跌', '必涨', '必跌',
          '抄底', '稳赚', '肯定会', '一定能', '保证盈']
# 「预测行情」「后市预测」这类断言式措辞也禁；但「不预测未来价格」这种自我约束属于合规声明，放行。
ASSERTIVE = [
    (r'(?<!不)预测(?=行情|走势|后市|价格|未来)', '预测行情/走势'),
    (r'后市(?:将会?|必然)', '后市断言'),
    (r'价格(?:将会?|必然)(?:上涨|下跌)', '价格断言'),
]


def main(path):
    if os.path.isdir(path):
        path = os.path.join(path, 'data', 'research.json')
    with open(path, encoding='utf-8') as f:
        D = json.load(f)

    # ---------------- A. 结构
    for k in ['meta', 'request', 'product', 'sources', 'quotes', 'routes', 'regions', 'cost_params']:
        if k not in D:
            err('A: 缺少顶层字段 {0}'.format(k))
    if not D.get('regions'):
        err('A: regions 为空')
    ids = [r.get('id') for r in D.get('regions', [])]
    if len(ids) != len(set(ids)):
        err('A: regions.id 有重复')
    for r in D.get('regions', []):
        for k in ['id', 'name', 'quote_id', 'route_id']:
            if not r.get(k):
                err('A: region {0} 缺少 {1}'.format(r.get('id'), k))
    quote_ids = {q['id'] for q in D.get('quotes', [])}
    route_ids = {r['id'] for r in D.get('routes', [])}
    for r in D.get('regions', []):
        if r.get('quote_id') not in quote_ids:
            err('A: region {0} 的 quote_id {1} 在 quotes 中不存在'.format(r['id'], r.get('quote_id')))
        if r.get('route_id') not in route_ids:
            err('A: region {0} 的 route_id {1} 在 routes 中不存在'.format(r['id'], r.get('route_id')))
    if not ERRORS:
        ok('A: 结构完整，{0} 个区域 / {1} 条线路 / {2} 条来源'.format(
            len(D['regions']), len(D['routes']), len(D.get('sources', []))))

    # ---------------- B. 价格六要素
    src_ids = {s['id'] for s in D.get('sources', [])}
    six = {'数值': 'price', '规格': 'spec', '地区': 'region_key', '含税口径': 'tax_included',
           '日期': 'date', '来源': 'source_id'}
    for q in D.get('quotes', []):
        missing = [label for label, key in six.items() if q.get(key) in (None, '')]
        if missing:
            err('B: 报价 {0} 缺六要素中的 {1}'.format(q.get('id'), '、'.join(missing)))
        if q.get('source_id') and q['source_id'] not in src_ids:
            err('B: 报价 {0} 的 source_id {1} 未在 sources 登记'.format(q['id'], q['source_id']))
        # 区间上下限顺序
        lo, hi = q.get('price_low'), q.get('price_high')
        if lo is not None and hi is not None and lo > hi:
            err('B: 报价 {0} 下限 {1} > 上限 {2}'.format(q['id'], lo, hi))
        # 中值应当在区间内
        p = q.get('price')
        if None not in (lo, hi, p) and not (lo <= p <= hi):
            warn('B: 报价 {0} 取用值 {1} 不在区间 {2}–{3} 内'.format(q['id'], p, lo, hi))
    if not [e for e in ERRORS if e.startswith('B')]:
        ok('B: 全部 {0} 条报价均满足「数值/规格/地区/含税/日期/来源」六要素'.format(len(D.get('quotes', []))))

    # ---------------- C. 反编造
    for rt in D.get('routes', []):
        for k in ['freight_unit', 'freight_total']:
            if k in rt and rt[k] is not None and not isinstance(rt[k], (int, float)):
                err('C: 线路 {0} 的 {1} 应为数字或 null，实际为 {2!r}'.format(rt['id'], k, rt[k]))
        if rt.get('freight_unit') == 0 and rt.get('freight_total') == 0:
            warn('C: 线路 {0} 运费填了 0 —— 确认这是「确认免费/含在车板价」，而不是「还没问到」'.format(rt['id']))
    zero_freight = [rt['id'] for rt in D.get('routes', [])
                    if rt.get('freight_unit') == 0 or rt.get('freight_total') == 0]
    if zero_freight:
        warn('C: 以下线路运费为 0，请确认不是占位：' + '、'.join(zero_freight))

    # 当所有运费均缺失时，报告中不得出现「到厂最低/推荐区域」这类结论
    all_missing = all(rt.get('freight_unit') is None and rt.get('freight_total') is None
                      for rt in D.get('routes', []))
    if all_missing:
        ok('C: 所有线路运费为空（符合「不编造」），到厂成本应为「待补」、不给排名')

    # ---------------- D. 交货口径一致性
    basis_kinds = {}
    qmap = {q['id']: q for q in D.get('quotes', [])}
    for r in D.get('regions', []):
        q = qmap.get(r.get('quote_id'), {})
        b = q.get('delivery_basis') or '未注明'
        kind = '自提' if '自提' in b else ('出厂' if '出厂' in b else ('送到' if '送到' in b else b))
        basis_kinds.setdefault(kind, []).append(r['name'])
    if len(basis_kinds) > 1:
        has_gap = any('口径' in (g.get('title') or '') + (g.get('what') or '')
                      for g in D.get('gaps', []))
        has_asm = any('口径' in a.get('text', '') for a in D.get('assumptions', []))
        if has_gap or has_asm:
            ok('D: 存在多种交货口径（{0}），已在缺口/假设中登记'.format(
                '、'.join('{0}:{1}'.format(k, len(v)) for k, v in basis_kinds.items())))
        else:
            err('D: 混用了多种交货口径（{0}）但未登记 gap/assumption —— 直接比价会误导'.format(
                '、'.join(basis_kinds)))
    else:
        ok('D: 交货口径一致（{0}）'.format(list(basis_kinds)[0] if basis_kinds else '—'))

    # ---------------- E. 文案禁令
    blob = json.dumps(D, ensure_ascii=False)
    hits = [w for w in BANNED if w in blob]
    hits += ['{0}（命中“{1}”）'.format(label, m.group(0))
             for pat, label in ASSERTIVE for m in re.finditer(pat, blob)]
    if hits:
        err('E: 文案出现禁用措辞：' + '、'.join(sorted(set(hits))))
    else:
        ok('E: 无预测/涨跌判断类措辞')

    # ---------------- F. 里程依据
    for rt in D.get('routes', []):
        basis = rt.get('basis')
        if basis == 'measured_legs':
            legs = rt.get('legs') or []
            if not legs:
                err('F: 线路 {0} basis=measured_legs 但没有 legs'.format(rt['id']))
            for l in legs:
                if not l.get('km'):
                    err('F: 线路 {0} 的 leg {1}→{2} 缺 km'.format(rt['id'], l.get('from'), l.get('to')))
                if not (l.get('source') or l.get('url')):
                    warn('F: 线路 {0} 的 leg {1}→{2} 缺来源/链接'.format(
                        rt['id'], l.get('from'), l.get('to')))
        elif basis in ('measured', 'via_points'):
            if basis == 'measured' and not rt.get('measured_km'):
                err('F: 线路 {0} basis=measured 但缺 measured_km'.format(rt['id']))
            if basis == 'via_points' and len(rt.get('via_points') or []) < 2:
                err('F: 线路 {0} basis=via_points 但途经点不足'.format(rt['id']))
        else:
            err('F: 线路 {0} 未声明 basis（必须说明里程怎么来的）'.format(rt['id']))
    if not [e for e in ERRORS if e.startswith('F')]:
        ok('F: 全部 {0} 条线路均声明了里程依据'.format(len(D.get('routes', []))))

    # ---------------- 输出
    print('=' * 66)
    print('校验对象：{0}'.format(os.path.relpath(path)))
    print('=' * 66)
    for m in OKS:
        print('  \u2713 ' + m)
    for m in WARNS:
        print('  ! ' + m)
    for m in ERRORS:
        print('  \u2717 ' + m)
    print('-' * 66)
    print('结果：{0} 通过 / {1} 警告 / {2} 错误'.format(len(OKS), len(WARNS), len(ERRORS)))
    return 1 if ERRORS else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python validate.py <案例目录或 research.json>')
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
