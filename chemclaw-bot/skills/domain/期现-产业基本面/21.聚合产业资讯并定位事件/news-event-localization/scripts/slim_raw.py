# -*- coding: utf-8 -*-
"""Build a LEAN evidence set for the example: only pages needed to trace quotes.

Strategy: extract every quoted fragment from the dataset, then keep only the pages
that contain at least one fragment (plus pages needed for a trailing window match).
Runs in one pass — no per-page audit calls.
"""
import glob
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
EX = os.path.join(SKILL, 'examples', '01-甲醇-中国-2026年10月第3周')
FULL_RAW = r'./methanol-events\raw'

FIELDS = ('confirmed_facts', 'data_supported', 'unconfirmed', 'verify_basis',
          'scale_desc', 'capacity_desc', 'occur_date_note', 'impact_hint',
          'first_report_note', 'core_points')


def decode_once(b):
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


def norm(s):
    for ch in ('\u201c', '\u201d', '\u300c', '\u300d', '"'):
        s = s.replace(ch, '')
    return squash(s)


def fragments():
    out = []
    for name, key in (('events.json', 'events'), ('news.json', 'items')):
        doc = json.load(open(os.path.join(EX, 'src', name), encoding='utf-8'))
        for obj in doc.get(key, []):
            for fld in FIELDS:
                v = obj.get(fld)
                vals = v if isinstance(v, list) else ([v] if isinstance(v, str) else [])
                for t in vals:
                    for f in re.findall(r'[\u201c\u300c]([^\u201d\u300d]{6,})[\u201d\u300d]', t):
                        out.append(norm(f))
    return out


def main():
    frags = fragments()
    print(f'引文片段 {len(frags)} 个')

    pages = []
    for pat in ('media/*.html', 'media2/*.html', 'official/*.html', '*.txt',
                'oil/*.items.json', 'oil/*.anchors.json'):
        for p in glob.glob(os.path.join(FULL_RAW, pat)):
            try:
                pages.append((p, squash(decode_once(open(p, 'rb').read()))))
            except Exception:
                pass
    print(f'候选页 {len(pages)} 个')

    need = set()
    for i, f in enumerate(frags):
        hit = False
        for p, txt in pages:
            if f in txt:
                need.add(p); hit = True
        if not hit:
            # trailing continuous window of >= 12 chars
            for wlen in (60, 40, 30, 24, 18, 12):
                if len(f) < wlen:
                    continue
                for start in range(0, len(f) - wlen + 1, max(1, wlen // 4)):
                    sub = f[start:start + wlen]
                    for p, txt in pages:
                        if sub in txt:
                            need.add(p)
                            hit = True
                            break
                    if hit:
                        break
                if hit:
                    break
        if not hit:
            print(f'  警告：片段无法定位 {f[:60]}')

    lean = os.path.join(EX, 'raw')
    if os.path.isdir(lean):
        shutil.rmtree(lean)
    os.makedirs(lean, exist_ok=True)
    total = 0
    for p in sorted(need):
        dst = os.path.join(lean, os.path.basename(p))
        shutil.copyfile(p, dst)
        total += os.path.getsize(dst)
    print(f'保留证据页 {len(need)} 个，{total/1024/1024:.2f} MB')


if __name__ == '__main__':
    main()