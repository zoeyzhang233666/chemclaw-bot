#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_research.py — 校验并规范化 research.json，同时计算派生层（变化幅度、景气指数、加权传导）。

用法:
    python build_research.py research.json [--out research.norm.json]

research.json 结构见 templates/demand-research-template.json。
校验失败会以非零退出码结束，并列出所有问题。
"""
import argparse, json, os, sys


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    return round((a - b) / abs(b) * 100, 2)


def series_stats(name, pts):
    """pts: [[date, value, ev_id], ...] -> 区间统计 + 逐点环比"""
    rows = []
    for i, pt in enumerate(pts):
        r = {'date': pt[0], 'value': pt[1], 'ev': pt[2]}
        if i > 0:
            r['mom'] = round(pt[1] - pts[i - 1][1], 3) if isinstance(pt[1], (int, float)) else None
            r['mom_pct'] = pct(pt[1], pts[i - 1][1])
        rows.append(r)
    vals = [p[1] for p in pts if isinstance(p[1], (int, float))]
    return {'name': name, 'points': rows,
            'span': {'from': pts[0][0], 'to': pts[-1][0], 'v0': pts[0][1], 'v1': pts[-1][1],
                     'chg': round(pts[-1][1] - pts[0][1], 3), 'chg_pct': pct(pts[-1][1], pts[0][1])},
            'min': min(vals) if vals else None, 'max': max(vals) if vals else None}


REQUIRED_EV = ['id', 'seg', 'metric', 'date', 'caliber', 'src', 'url']
# “纯碱本体”这类供需两侧分组不属于需求下游，不要求 A 级指标
NON_DEMAND_SEG = {'parent', 'policy', 'x', 'self'}


def validate(doc, errs, warns=None):
    warns = warns if warns is not None else []
    meta = doc.get('meta') or {}
    for k in ('product', 'window', 'asof'):
        if not meta.get(k):
            errs.append('meta.%s 缺失' % k)
    st = doc.get('structure') or []
    if len(st) < 2:
        errs.append('structure 至少需要 2 套口径用于交叉验证与敏感性（当前 %d）' % len(st))
    for i, s in enumerate(st):
        for k in ('org', 'year', 'basis', 'items'):
            if not s.get(k):
                errs.append('structure[%d].%s 缺失' % (i, k))
        tot = sum(x[1] or 0 for x in s.get('items', []))
        if tot and not (95 <= tot <= 100.5):
            errs.append('structure[%d] 占比合计 %.1f%%，应≈100%%' % (i, tot))
    evs = doc.get('evidence') or []
    if not evs:
        errs.append('evidence 为空')
    ids = [e.get('id') for e in evs]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        errs.append('evidence id 重复: %s' % sorted(dup))
    for e in evs:
        for k in REQUIRED_EV:
            if e.get(k) in (None, ''):
                errs.append('evidence %s 缺字段 %s' % (e.get('id'), k))
        if 'unit' not in e:
            errs.append('evidence %s 缺字段 unit（非数值类可写 ""）' % e.get('id'))
        if e.get('url') and not str(e['url']).startswith('https://'):
            errs.append('evidence %s url 非 https' % e.get('id'))
        if e.get('grade') not in (None, 'A', 'A-', 'B', 'C', 'D'):
            errs.append('evidence %s grade 非法: %s' % (e.get('id'), e.get('grade')))
    # 每个下游至少一个 A 级
    segs = {e['seg'] for e in evs} - NON_DEMAND_SEG
    for s in segs:
        if not any(e['seg'] == s and e.get('grade') in ('A', 'A-') for e in evs):
            errs.append('下游 %s 没有任何 A 级指标（须补数据或在 gaps 说明）' % s)
    if not doc.get('gaps'):
        errs.append('gaps 为空：需求研究必然存在缺口，请如实登记（可用空数组但需有说明）')
    for e in evs:
        if e.get('value') is None and not e.get('qualitative'):
            warns.append('evidence %s 无数值（若为政策/定性事件请在数据中标注 qualitative=true）' % e.get('id'))
    return errs


def build(doc):
    """从 doc['series']（{分组: {指标: [[date,value,ev],...]}}）计算 derived；
    若文件中已带 derived（案例导出格式），保留既有序列并只重算 transmisson 部分。"""
    derived = doc.get('derived') if isinstance(doc.get('derived'), dict) else {}
    for grp, items in (doc.get('series') or {}).items():
        if not isinstance(items, dict):
            continue  # 期货序列 [{d,c}] 不是分组结构，跳过
        derived[grp] = {k: (v if isinstance(v, dict) and 'span' in v else series_stats(k, v))
                        for k, v in items.items() if isinstance(v, list) and len(v) > 1}
    # 景气打分与加权
    sent = doc.get('sentiment') or []
    W = doc.get('weights') or {}
    dw = (doc.get('dominance_weights') or {})
    seg_idx, detail, warnings = {}, {}, []
    for grp, wmap in W.items():
        items = [s for s in sent if s['seg'] == grp]
        if not items:
            continue
        pairs = []
        for s in items:
            w = wmap.get(s['indicator'])
            if w is None:
                for k, v in wmap.items():
                    if not k:
                        continue
                    kk = k.split('(')[0].split('（')[0].strip()
                    if kk and (kk in s['indicator'] or s['indicator'].startswith(kk[:2])):
                        w = v
                        break
            pairs.append([s, w])
        unmatched = [s['indicator'] for s, w in pairs if w is None]
        if unmatched:
            warnings.append('%s 分项有 %d 个指标未匹配到显式权重（按 0 计，不参与分母）：%s'
                            % (grp, len(unmatched), unmatched))
            pairs = [[s, w] for s, w in pairs if w is not None]
            if not pairs:
                continue
        num = sum(s['score'] * w for s, w in pairs)
        den = sum(w for _, w in pairs) or 1
        seg_idx[grp] = round(num / den, 3)
        detail[grp] = [{'indicator': s['indicator'], 'score': s['score'], 'w': round(w, 3)} for s, w in pairs]
    contrib = {k: round(v * dw.get(k, 0) / 100, 3) for k, v in seg_idx.items()}
    doc.setdefault('derived', {})
    doc['derived']['transmission'] = {
        'weights_domestic': dw, 'seg_index': seg_idx, 'detail': detail,
        'contribution': contrib, 'weighted_total': round(sum(contrib.values()), 3),
        'explain': '加权总指数 = Σ(分项指数 × 消费占比)；分项指数为该下游内部指标的加权均分（-2~+2）。'
                   '该数是景气度传导指数，不是消费量增速。',
    }
    doc['derived']['transmission_warnings'] = warnings
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--out')
    a = ap.parse_args()
    doc = json.load(open(a.src, encoding='utf-8'))
    warns = []
    errs = validate(doc, [], warns)
    if warns:
        print('提示 %d 项（不阻断）：' % len(warns))
        for w in warns[:10]:
            print('   ·', w)
    if errs:
        print('校验失败 %d 项：' % len(errs))
        for e in errs:
            print(' -', e)
        sys.exit(1)
    doc = build(doc)
    out = a.out or os.path.splitext(a.src)[0] + '.norm.json'
    json.dump(doc, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('OK  evidence=%d  structure=%d  下游分项=%d  加权传导=%s'
          % (len(doc['evidence']), len(doc['structure']),
             len(doc['derived']['transmission']['seg_index']),
             doc['derived']['transmission']['weighted_total']))
    print('->', out)


if __name__ == '__main__':
    main()
