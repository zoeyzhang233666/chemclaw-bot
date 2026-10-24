#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hs_match.py - propose candidate HS-6 codes for a chemical product.

This is STEP 1 of the workflow: identify the product and its possible HS codes
BEFORE any trade data is fetched. It outputs candidates for the USER TO CONFIRM.
It never asserts a code as final.

Usage
-----
    python hs_match.py "重质纯碱"                       # Chinese product name
    python hs_match.py "soda ash" --cas 497-19-8
    python hs_match.py --interactive                    # guided prompts
    python hs_match.py "甲醇" --json                    # machine-readable

Output
------
Ranked candidates with: hs6, English name, Chinese name, score, why it matched,
and the口径 caveat (what the 6-digit code does and does not distinguish).
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '..', 'references', 'hs_subheadings.json')

# A few well-known CAS -> product hints, used only to steer the search.
# Deliberately small: CAS numbers are NOT a reliable HS key, they only help name the product.
CAS_HINTS = {
    '497-19-8': ('sodium carbonate', '碳酸钠（纯碱）'),
    '144-55-8': ('sodium bicarbonate', '碳酸氢钠（小苏打）'),
    '1310-73-2': ('sodium hydroxide', '氢氧化钠（烧碱）'),
    '67-56-1': ('methanol', '甲醇'),
    '64-17-5': ('ethanol', '乙醇'),
    '7664-93-9': ('sulfuric acid', '硫酸'),
    '7647-01-0': ('hydrochloric acid', '盐酸'),
    '7697-37-2': ('nitric acid', '硝酸'),
    '7664-41-7': ('ammonia', '氨'),
    '124-04-4': ('adipic acid', '己二酸'),
    '100-21-0': ('terephthalic acid', '对苯二甲酸'),
    '108-88-3': ('toluene', '甲苯'),
    '71-43-2': ('benzene', '纯苯'),
    '75-56-9': ('propylene oxide', '环氧丙烷'),
    '108-95-2': ('phenol', '苯酚'),
    '57-55-6': ('propylene glycol', '丙二醇'),
    '107-21-1': ('ethylene glycol', '乙二醇'),
    '77-78-1': ('dimethyl sulfate', '硫酸二甲酯'),
    '141-78-6': ('ethyl acetate', '乙酸乙酯'),
    '79-10-7': ('acrylic acid', '丙烯酸'),
    '140-88-5': ('ethyl acrylate', '丙烯酸乙酯'),
    '80-62-6': ('methyl methacrylate', '甲基丙烯酸甲酯'),
    '75-05-8': ('acetonitrile', '乙腈'),
    '78-67-1': ('AIBN', '偶氮二异丁腈'),
    '1313-82-2': ('sodium sulfide', '硫化钠'),
    '497-19-8b': ('', ''),
    '68585-34-2': ('SDS', '十二烷基硫酸钠'),
    '111-42-2': ('diethanolamine', '二乙醇胺'),
    '141-43-5': ('monoethanolamine', '一乙醇胺'),
    '102-71-6': ('triethanolamine', '三乙醇胺'),
    '7664-38-2': ('phosphoric acid', '磷酸'),
    '7722-84-1': ('hydrogen peroxide', '过氧化氢'),
    '75-21-8': ('ethylene oxide', '环氧乙烷'),
    '75-15-0': ('carbon disulfide', '二硫化碳'),
    '506-68-3': ('cyanogen bromide', '溴化氰'),
    '156-62-7': ('calcium cyanamide', '氰氨化钙'),
}

# 口径 caveats that apply to broad families (shown alongside candidates)
FAMILY_NOTES = {
    '28': '第28章为无机化学品。注意：同一种物质常因"晶体结构/用途/纯度"落入不同子目（如氧化物 vs 盐），确认时优先核对本国法定归类。',
    '29': '第29章为有机化学品。注意：单一成分与混合物归类不同（混合物可能落入38章3812/3824等），纯度与用途会影响归类。',
    '38': '第38章为杂项化学品。混合物、配制品、助剂常在此章；与第29章单一化合物之间存在归类边界。',
    '39': '第39章为塑料及初级形状聚合物。注意"初级形状 vs 半成品/制品"的界限。',
}


def load_ref():
    with open(REF, encoding='utf-8') as f:
        return json.load(f)


def norm(s):
    return re.sub(r'[\s\-_/（）()、,，.。;；]+', '', (s or '').lower())


def score_match(query, sub):
    """Return (score, reasons[]) for a reference subheading against the query."""
    q = norm(query)
    if not q:
        return 0, ['input empty']
    reasons = []
    score = 0.0
    name_en = norm(sub['name_en'])
    name_zh = norm(sub['name_zh'])
    kws = [norm(k) for k in sub.get('keywords', [])]

    # exact
    if q in kws:
        score += 100
        reasons.append('与关键词完全一致')
    if q and (q == name_zh or q == name_en):
        score += 90
        reasons.append('与子目名称完全一致')
    # token containment
    if q and len(q) >= 2:
        if q in name_zh:
            score += 70
            reasons.append('中文名包含输入词')
        if q in name_en:
            score += 65
            reasons.append('英文名包含输入词')
        for k in kws:
            if not k:
                continue
            if q == k:
                pass
            elif q in k or k in q:
                score += 45
                reasons.append(f'与关键词“{k}”部分匹配')
                break
    # reverse containment (query longer than keyword)
    if q and len(q) >= 3:
        for k in kws:
            if k and len(k) >= 3 and k in q and k != q:
                score += 30
                reasons.append(f'包含关键词“{k}”')
                break
    # loose CJK overlap: require it to be a *meaningful* share of the keyword, not 2 stray chars
    if score == 0 and re.search(r'[\u4e00-\u9fff]', q):
        chars = set(q)
        for k in kws + [name_zh]:
            if not k or len(k) < 2:
                continue
            overlap = len(set(k) & chars)
            if overlap >= 2 and overlap / len(set(k)) >= 0.6:
                score += 12
                reasons.append(f'字符部分重合（{k}）')
                break
    return score, reasons


def propose(query, cas=None, top=5):
    ref = load_ref()
    subs = ref['subheadings']
    extra_q = ''
    if cas:
        cas = cas.strip()
        if cas in CAS_HINTS:
            en, zh = CAS_HINTS[cas]
            extra_q = f'{zh} {en}'.strip()
            if not query:
                query = zh
    eff = (query or '') + ' ' + extra_q
    scored = []
    for s in subs:
        sc, why = score_match(query or extra_q, s)
        if extra_q:
            sc2, why2 = score_match(extra_q, s)
            if sc2 > sc:
                sc, why = sc2, why2
        if sc > 0:
            scored.append((sc, s, why))
    scored.sort(key=lambda x: -x[0])
    # keep only plausible candidates; drop weak/noise matches when a strong one exists
    best = scored[0][0] if scored else 0
    cutoff = 40 if best >= 40 else 20
    out = []
    for sc, s, why in scored[:top]:
        if sc < cutoff:
            continue
        ch = s['hs6'][:2]
        out.append({
            'hs6': s['hs6'],
            'name_en': s['name_en'],
            'name_zh': s['name_zh'],
            'score': round(sc, 1),
            'confidence': '高' if sc >= 70 else '中' if sc >= 40 else '低',
            'reasons': why,
            'family_note': FAMILY_NOTES.get(ch, ''),
        })
    return out, subs


def main():
    ap = argparse.ArgumentParser(description='Propose candidate HS-6 codes for a chemical product.')
    ap.add_argument('product', nargs='?', default='', help='product name (Chinese or English)')
    ap.add_argument('--cas', default=None, help='CAS registry number, e.g. 497-19-8')
    ap.add_argument('--spec', default='', help='grade/spec, e.g. "dense, >=99.2%" (context only)')
    ap.add_argument('--top', type=int, default=5)
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    a = ap.parse_args()

    if not a.product and not a.cas:
        print('ERROR: give a product name and/or --cas.  Example: python hs_match.py "soda ash" --cas 497-19-8',
              file=sys.stderr)
        return 2

    cands, _ = propose(a.product, a.cas, a.top)
    if a.json:
        print(json.dumps({'query': a.product, 'cas': a.cas, 'spec': a.spec, 'candidates': cands},
                         ensure_ascii=False, indent=2))
        return 0

    print('=' * 74)
    print(f'HS 编码候选  |  输入：{a.product or "-"}   CAS：{a.cas or "-"}   规格：{a.spec or "-"}')
    print('=' * 74)
    if not cands:
        print('未匹配到候选。请用产品的英文/中文规范名重试，或直接向用户确认产品物质名称与用途。')
        print('提示：可先用 references/hs_subheadings.json 搜索关键词。')
        return 1
    for i, c in enumerate(cands, 1):
        print(f'\n[{i}] HS {c["hs6"]}  置信度 {c["confidence"]}（score {c["score"]}）')
        print(f'    英文：{c["name_en"]}')
        print(f'    中文：{c["name_zh"]}')
        print(f'    依据：{"；".join(c["reasons"])}')
    print('\n' + '-' * 74)
    print('⚠ 以上仅为【候选】。必须由用户确认后再进入下一步：')
    print('  1) 该 6 位编码是否覆盖你的产品（规格差异是否会导致归入不同子目）？')
    print('  2) 该国是否有更细的本地编码（8/10 位）需要分别取数？')
    print('  3) 是否还要纳入相邻编码（如混合物/副产品可能入 3824）？')
    fams = {c['hs6'][:2] for c in cands}
    for f in sorted(fams):
        if FAMILY_NOTES.get(f):
            print(f'\n口径提示（第{f}章）：{FAMILY_NOTES[f]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
