#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify that every quoted fragment in the dataset can be traced to a saved page.

Usage:
    python audit_quotes.py <src_dir> <raw_dir> [--verbose]

Why this exists: the most dangerous error in news aggregation is putting a number
or sentence inside quotation marks when the source never said it. This tool reads
every saved page under <raw_dir>, strips markup, and checks each "..." fragment in
events.json / news.json against that corpus.

Rules:
  - each page is decoded ONCE (never mixing encodings, which pollutes the corpus)
  - a fragment counts as traced if the whole fragment, or a continuous window of
    >= 12 characters from it, appears in a single page
  - untraced fragments are reported; each needs one of three fixes:
      1. re-fetch the page (incomplete capture)
      2. reword the quote to match the source
      3. remove the quotation marks (it was your own paraphrase)

Exit code 0 = all traced, 1 = untraced fragments remain.
"""
import json
import os
import re
import sys
import glob

FIELDS = ('confirmed_facts', 'data_supported', 'unconfirmed', 'verify_basis',
          'scale_desc', 'capacity_desc', 'occur_date_note', 'impact_hint',
          'first_report_note', 'core_points')


def decode_once(b):
    """Strictly decode with the first encoding that fully succeeds; never mix."""
    if b[:3] == b'\xef\xbb\xbf':
        return b[3:].decode('utf-8', 'ignore')
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        pass
    try:
        return b.decode('gb18030')
    except UnicodeDecodeError:
        return b.decode('utf-8', 'ignore')


def squash(s):
    return re.sub(r'\s+', '', s)


def strip_markup(s):
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', s, flags=re.S | re.I)
    return re.sub(r'<[^>]+>', ' ', s)


def build_corpus(raw_dir):
    pages = []
    pats = ('**/*.html', '**/*.htm', '**/*.txt', '**/*.json', '**/*.md')
    for pat in pats:
        for p in glob.glob(os.path.join(raw_dir, pat), recursive=True):
            try:
                pages.append(squash(decode_once(open(p, 'rb').read())))
            except Exception:
                pass
    # also index both raw and tag-stripped variants of html pages
    variants = list(pages)
    for p in glob.glob(os.path.join(raw_dir, '**/*.htm*'), recursive=True):
        try:
            variants.append(squash(strip_markup(decode_once(open(p, 'rb').read()))))
        except Exception:
            pass
    return pages + variants


def norm(s):
    for ch in ('\u201c', '\u201d', '\u300c', '\u300d', '"'):
        s = s.replace(ch, '')
    return squash(s)


def traced(f, pages):
    if any(f in pg for pg in pages):
        return True
    for wlen in (60, 40, 30, 24, 18, 12):
        if len(f) < wlen:
            continue
        step = max(1, wlen // 4)
        for start in range(0, len(f) - wlen + 1, step):
            sub = f[start:start + wlen]
            if any(sub in pg for pg in pages):
                return True
    return False


def main(src_dir, raw_dir, verbose=False):
    pages = build_corpus(raw_dir)
    print(f'语料页 {len(pages)} 个变体，共 {sum(len(p) for p in pages):,} 字符')

    targets = []
    for name, key in (('events.json', 'events'), ('news.json', 'items')):
        p = os.path.join(src_dir, name)
        if not os.path.exists(p):
            continue
        doc = json.load(open(p, encoding='utf-8'))
        for obj in doc.get(key, []):
            oid = obj.get('event_id') or obj.get('news_id')
            for fld in FIELDS:
                v = obj.get(fld)
                if isinstance(v, str):
                    targets.append((oid, fld, v))
                elif isinstance(v, list):
                    for x in v:
                        if isinstance(x, str):
                            targets.append((oid, fld, x))

    frag_re = re.compile(r'[\u201c\u300c]([^\u201d\u300d]{6,})[\u201d\u300d]')
    checked = hit = 0
    misses = []
    for oid, fld, text in targets:
        for frag in frag_re.findall(text):
            checked += 1
            if traced(norm(frag), pages):
                hit += 1
            else:
                misses.append((oid, fld, frag))

    print(f'引文片段 {checked} 个，可追溯 {hit} 个，不可追溯 {len(misses)} 个')
    if verbose:
        print('（--verbose 显示全部片段）')
    for oid, fld, frag in misses:
        print(f'  UNTRACED {oid} {fld}\n      | {frag[:110]}')

    print('-' * 60)
    if misses:
        print(f'RESULT: FAIL — {len(misses)} 个引文片段未能在保存的原文中找到')
        print('处置：①重新抓取该页 ②按原文改写 ③去掉引号（若是自己的概括）')
        return 1
    print('RESULT: PASS — 全部引文可追溯到保存的原文')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], '--verbose' in sys.argv))