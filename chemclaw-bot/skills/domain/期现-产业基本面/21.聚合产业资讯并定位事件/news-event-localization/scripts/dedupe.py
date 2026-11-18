#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Suggest same-event candidate pairs from raw news items.

Usage:
    python dedupe.py <news.json> [--json]

This is a *recall* tool, not a decision maker: it ranks pairs of items that may
describe the same underlying event so a human can confirm and record the relation
in dedupe.json. It never writes dedupe.json itself.

Signals used:
  - shared entity-like tokens (company / plant / place names, 2-6 char CJK words)
  - shared numeric facts (capacities, percentages, dates)
  - title similarity (character bigrams)
  - publish-time proximity
"""
import json
import re
import sys
import itertools
import datetime as dt

STOP = set('''的 了 和 与 及 或 在 是 为 对 从 到 由 按 已 将 有 无 不 也 都 就 而 但 并 其 此 该 等 各 我 国 内 外
月 日 年 时 分 秒 上 下 中 前 后 左 右 大 小 多 少 高 低 新 旧 增 减 升 降 上周 本周 周 期 吨 万 亿 元 个 家 条 项'''.split())


def norm(s):
    return re.sub(r'\s+', '', s or '')


def bigrams(s):
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def tokens(s):
    s = norm(s)
    out = set()
    for m in re.finditer(r'[\u4e00-\u9fa5A-Za-z]{2,8}', s):
        w = m.group(0)
        if w not in STOP and len(w) >= 2:
            out.add(w)
    return out


def numbers(s):
    s = norm(s)
    return {m.group(0) for m in re.finditer(r'\d+(?:\.\d+)?%?', s)
            if len(m.group(0)) >= 2}


def parse_t(s):
    if not s:
        return None
    s = str(s).replace('Z', '+00:00')
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return dt.datetime.strptime(s if '+' in s or 'Z' in s else s, fmt)
        except Exception:
            continue
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def score(a, b):
    """Return (score 0-1, reasons[])."""
    ta, tb = norm(a.get('title')), norm(b.get('title'))
    ga, gb = bigrams(ta), bigrams(tb)
    jac = len(ga & gb) / max(1, len(ga | gb))

    wa = tokens(ta) | tokens(' '.join(a.get('core_points') or []))
    wb = tokens(tb) | tokens(' '.join(b.get('core_points') or []))
    words = wa & wb

    na = numbers(ta + ' '.join(a.get('core_points') or []))
    nb = numbers(tb + ' '.join(b.get('core_points') or []))
    nums = na & nb

    reasons = []
    s = 0.0
    if jac > 0.35:
        s += 0.45
        reasons.append(f'标题相似度 {jac:.0%}')
    elif jac > 0.2:
        s += 0.2
        reasons.append(f'标题相似度 {jac:.0%}')
    if len(words) >= 3:
        s += 0.3
        reasons.append('共同词: ' + '、'.join(sorted(words)[:6]))
    elif len(words) == 2:
        s += 0.15
        reasons.append('共同词: ' + '、'.join(sorted(words)))
    if len(nums) >= 2:
        s += 0.25
        reasons.append('共同数字: ' + '、'.join(sorted(nums)[:5]))
    elif len(nums) == 1:
        s += 0.08

    ta_t, tb_t = parse_t(a.get('first_pub') or a.get('list_ts')), parse_t(b.get('first_pub') or b.get('list_ts'))
    if ta_t and tb_t:
        try:
            days = abs((ta_t - tb_t).total_seconds()) / 86400
            if days <= 1:
                s += 0.15
                reasons.append('发布时点相近（≤1天）')
            elif days <= 4:
                s += 0.07
                reasons.append(f'发布时点接近（{days:.1f}天）')
        except Exception:
            pass

    if a.get('url') and a.get('url') == b.get('url'):
        s = 1.0
        reasons.append('同一 URL')

    return min(s, 1.0), reasons


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    path = sys.argv[1]
    as_json = '--json' in sys.argv
    with open(path, encoding='utf-8') as f:
        items = json.load(f).get('items', [])

    pairs = []
    for a, b in itertools.combinations(items, 2):
        s, why = score(a, b)
        if s >= 0.42:
            pairs.append((s, a, b, why))
    pairs.sort(key=lambda x: -x[0])

    if as_json:
        out = [{'a': a.get('news_id'), 'b': b.get('news_id'), 'score': round(s, 3),
                'reasons': why, 'a_title': a.get('title'), 'b_title': b.get('title')}
               for s, a, b, why in pairs]
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return

    print(f'共 {len(items)} 条资讯，命中 {len(pairs)} 组疑似同一事件的候选对\n')
    for s, a, b, why in pairs[:60]:
        print(f'[{s:.2f}] {a.get("news_id")} × {b.get("news_id")}')
        print(f'   A: {a.get("publisher")} | {a.get("title")[:70]}')
        print(f'   B: {b.get("publisher")} | {b.get("title")[:70]}')
        print(f'   依据: {"; ".join(why)}')
        print()
    print('提示：本工具的命中只是“值得人工看一眼”，不是判定结果。')
    print('     确认后请把关系写入 dedupe.json，并写清 basis。')


if __name__ == '__main__':
    main()