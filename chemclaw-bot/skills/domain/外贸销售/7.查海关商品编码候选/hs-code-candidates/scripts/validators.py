# -*- coding: utf-8 -*-
"""Validate a hs-code-candidates case.json against the skill's hard rules.

Usage:
    python validators.py <case.json> [--out checks.json] [--as-of YYYY-MM-DD]

Exit code 0 when there is no error-level finding; 1 otherwise.
"""
import sys, os, json, re, datetime

LEVEL_WORDS = ('A', 'B', 'C', 'D')
REQUIRED_CAND = ['id', 'rank', 'code10', 'hs6', 'title', 'name', 'verdict', 'confidence',
                 'conditions', 'why', 'basis', 'vuln', 'mfn', 'gen', 'export_tax', 'rebate',
                 'reg', 'ciq', 'url']

def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    out = args[args.index('--out') + 1] if '--out' in args else None
    as_of = args[args.index('--as-of') + 1] if '--as-of' in args else datetime.date.today().isoformat()
    case = load(path)
    errors, warns, infos = [], [], []

    def err(c, m): errors.append({'code': c, 'message': m})
    def warn(c, m): warns.append({'code': c, 'message': m})
    def info(c, m): infos.append({'code': c, 'message': m})

    # ---- meta ----
    meta = case.get('meta') or {}
    for k in ('case_id', 'query_date', 'hs_version', 'rebate_version'):
        if not meta.get(k):
            err('META_MISSING', 'meta.%s 为空' % k)
    try:
        qd = datetime.date.fromisoformat(meta.get('query_date', '1900-01-01'))
        if qd > datetime.date.fromisoformat(as_of):
            err('META_FUTURE', 'query_date 晚于 --as-of（%s > %s）' % (qd, as_of))
        elif (datetime.date.fromisoformat(as_of) - qd).days > 400:
            warn('META_STALE', 'query_date 距今超过 400 天，税率与法规可能已变，需复核')
    except Exception:
        err('META_DATE', 'query_date 不是 YYYY-MM-DD')

    # ---- product ----
    prod = case.get('product') or {}
    for k in ('name_cn', 'name_en', 'cas', 'form', 'is_mixture', 'use', 'retail'):
        if not prod.get(k):
            warn('PRODUCT_MISSING', 'product.%s 为空' % k)
    if not case.get('not_advice'):
        err('DISCLAIMER', '缺少 not_advice 免责声明')

    # ---- candidates ----
    cands = case.get('candidates') or []
    if len(cands) < 2:
        err('CAND_COUNT', '候选少于 2 个：归类研究不得只给一个结论')
    seen_codes, seen_ids, ranks = set(), set(), []
    for i, c in enumerate(cands):
        tag = c.get('id') or 'C%d' % (i + 1)
        for f in REQUIRED_CAND:
            if f == 'code10' and (c.get('verdict') or '').startswith('不适用'):
                continue
            if key_missing(c, f):
                if f == 'code10':
                    # an empty code10 is allowed only when the candidate is explicitly marked pending
                    blob = json.dumps(c, ensure_ascii=False)
                    if '待核验' in blob or 'D 级' in blob or '未取得' in blob:
                        warn('CAND_CODE_PENDING',
                             '%s 未给出 10 位编码，已按"待核验"处理（必须在 conditions/vuln 中写明为何无法确定）' % tag)
                        continue
                err('CAND_FIELD', '%s 缺少字段 %s' % (tag, f))
        code = str(c.get('code10', ''))
        if code and not re.fullmatch(r'\d{10}', code):
            err('CAND_CODE10', '%s code10 不是 10 位数字：%s' % (tag, code))
        hs6 = str(c.get('hs6', ''))
        if hs6 and not re.fullmatch(r'\d{4}\.\d{2}', hs6):
            err('CAND_HS6', '%s hs6 格式应为 1234.56：%s' % (tag, hs6))
        if code and hs6 and (hs6.replace('.', '') != code[:6]):
            err('CAND_HIER', '%s hs6 与 code10 前 6 位不一致：%s / %s' % (tag, hs6, code))
        if code and code in seen_codes:
            err('CAND_DUP', '%s 编码重复：%s' % (tag, code))
        if code:
            seen_codes.add(code)
        if c.get('id') in seen_ids:
            err('CAND_ID_DUP', '候选 id 重复：%s' % c.get('id'))
        seen_ids.add(c.get('id'))
        ranks.append(c.get('rank'))
        if not c.get('conditions'):
            err('CAND_COND', '%s 没有成立条件' % tag)
        if not c.get('basis'):
            err('CAND_BASIS', '%s 没有法律依据' % tag)
        if not c.get('vuln'):
            err('CAND_VULN', '%s 没有风险点（说明还没想清楚）' % tag)
        for f in ('mfn', 'gen', 'rebate'):
            v = str(c.get(f, ''))
            if v and not v.endswith('%') and v not in ('—', '-', '无') and '待核验' not in v:
                warn('CAND_RATE_FMT', '%s %s 税率未带 %%：%s' % (tag, f, v))
        conf = str(c.get('confidence', ''))
        if conf and ('（' not in conf and '(' not in conf and conf.strip() in ('高', '中高', '中')):
            warn('CAND_CONF', '%s 置信度缺少前提说明（建议写成"中高（条件成立时）"）' % tag)
        if '过期' in json.dumps(c, ensure_ascii=False) and c.get('verdict') != '不适用':
            warn('CAND_EXPIRED', '%s 可能引用了过期编码，请确认状态' % tag)
        if not c.get('decl_elems'):
            info('CAND_DECL', '%s 缺申报要素（如非首选候选可忽略）' % tag)
    if ranks and sorted(ranks) != list(range(1, len(ranks) + 1)):
        warn('CAND_RANK', 'rank 不连续或重复：%s' % ranks)

    # ---- sources ----
    sources = case.get('sources') or []
    if len(sources) < 5:
        warn('SRC_COUNT', '来源少于 5 条')
    a_count = 0
    for s in sources:
        lvl = str(s.get('level', ''))
        if not lvl.startswith(LEVEL_WORDS):
            err('SRC_LEVEL', '来源 %s 的 level 必须以 A/B/C/D 开头：%s' % (s.get('id'), lvl))
        if lvl.startswith('A'):
            a_count += 1
        if not str(s.get('url', '')).startswith('http'):
            err('SRC_URL', '来源 %s 缺可点击 URL' % s.get('id'))
        for k in ('publisher', 'date', 'verified'):
            if not s.get(k):
                warn('SRC_FIELD', '来源 %s 缺 %s' % (s.get('id'), k))
    if a_count < 2:
        err('SRC_A', 'A 级官方原文来源少于 2 条（当前 %d 条）' % a_count)

    # ---- missing / confirm / regulatory ----
    if len(case.get('missing') or []) < 3:
        err('MISSING_COUNT', '缺失信息少于 3 条，或未做缺口检查')
    for m in case.get('missing') or []:
        if len(m) < 6:
            err('MISSING_FIELDS', '缺失信息行字段不足 6 个：%s' % (m[0] if m else '?'))
        elif m[3] not in ('高', '中', '低'):
            warn('MISSING_PRIO', '%s 优先级应为 高/中/低' % m[0])
    if len(case.get('confirm') or []) < 3:
        err('CONFIRM_COUNT', '待确认问题少于 3 条')
    for g in case.get('regulatory') or []:
        lvl = str(g.get('level', ''))
        if not lvl.startswith(LEVEL_WORDS):
            err('REG_LEVEL', '监管条目 %s 的 level 必须以 A/B/C/D 开头' % g.get('id'))
        if not g.get('todo'):
            warn('REG_TODO', '监管条目 %s 没有"仍需确认"项' % g.get('id'))

    # ---- hierarchy / foreign ----
    if not case.get('six_tree'):
        warn('TREE', '缺 six_tree（HS6 层级说明）')
    for f in case.get('foreign') or []:
        if not str(f.get('level', '')).startswith(LEVEL_WORDS):
            err('FOREIGN_LEVEL', '目的国条目 %s 的 level 必须 A/B/C/D' % f.get('country'))
        if str(f.get('level', '')).startswith('D') and re.search(r'\d+(\.\d+)?%', str(f.get('rate', ''))) and '待核验' not in str(f.get('rate', '')):
            warn('FOREIGN_RATE_D', '%s 为 D 级却给出了具体税率，须注明"待核验"或删去数字' % f.get('country'))

    verdict = 'fail' if errors else 'pass'
    result = {
        'case': os.path.basename(path),
        'as_of': as_of,
        'verdict': verdict,
        'stats': {
            'candidates': len(cands),
            'sources': len(sources),
            'a_sources': a_count,
            'missing': len(case.get('missing') or []),
            'confirm': len(case.get('confirm') or []),
            'regulatory': len(case.get('regulatory') or []),
            'foreign': len(case.get('foreign') or []),
            'confusion': len(case.get('ac') or []),
        },
        'errors': errors,
        'warnings': warns,
        'info': infos,
    }
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if out:
        with open(out, 'w', encoding='utf-8') as f:
            f.write(text)
    print(text)
    sys.exit(0 if verdict == 'pass' else 1)


def key_missing(d, f):
    if f not in d:
        return True
    v = d[f]
    if v is None:
        return True
    if isinstance(v, (str, list, dict)) and len(v) == 0:
        return True
    return False


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
