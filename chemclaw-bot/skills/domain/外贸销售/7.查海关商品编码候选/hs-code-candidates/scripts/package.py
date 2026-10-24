# -*- coding: utf-8 -*-
"""Package the skill into a versioned ZIP (excludes caches, previews and _patch scripts)."""
import sys, os, zipfile, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
NAME = 'hs-code-candidates'
VERSION = open(os.path.join(ROOT, 'VERSION'), encoding='utf-8').read().strip()
OUT = os.path.join(ROOT, '%s-v%s.zip' % (NAME, VERSION))

EXCLUDE_DIRS = {'__pycache__', 'preview', '.git'}
EXCLUDE_FILES = {'_patch_html.py', '_patch_wb.py', '_patch_val.py', '_patch_val2.py', '_patch_html2.py',
                 '_make_examples.py', '_fix_examples.py', '_fix_examples2.py', 'checks.json'}
EXCLUDE_NAME_SUFFIX = ('.pyc',)

files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
    for fn in filenames:
        if fn in EXCLUDE_FILES or fn.endswith(EXCLUDE_NAME_SUFFIX):
            continue
        if fn.endswith('.zip') and dirpath == ROOT:
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, ROOT).replace('\\', '/')
        # keep checks.json only inside the main example
        if fn == 'checks.json' and '01-SBS' not in rel:
            continue
        files.append((full, '%s/%s' % (NAME, rel)))

files.sort(key=lambda x: x[1])
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for full, arc in files:
        z.write(full, arc)

print('packed', OUT, os.path.getsize(OUT), 'bytes,', len(files), 'files')
for _, a in files[:200]:
    print('  ', a)
