# -*- coding: utf-8 -*-
"""package.py —— 把 Skill 目录打成可分发 ZIP

只收：SKILL.md、references/、scripts/、examples/、out/（成品交付物）
不收：build/（中间结果）、__pycache__、_preview_*.png、自测临时目录
"""
import os, sys, zipfile

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_NAME = '看上下游成本怎么传导.zip'

SKIP_DIRS = {'__pycache__', 'build', 'node_modules'}
SKIP_PREFIX = ('_selftest_tmp', '_preview_')
SKIP_EXT = ('.pyc', '.pyo')


def main():
    zpath = os.path.join(os.path.dirname(ROOT), OUT_NAME)
    if os.path.exists(zpath):
        os.remove(zpath)
    n, total = 0, 0
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = sorted(d for d in dirs
                             if d not in SKIP_DIRS and not d.startswith('_selftest_tmp'))
            for f in sorted(files):
                if f.startswith(SKIP_PREFIX) or f.endswith(SKIP_EXT):
                    continue
                p = os.path.join(base, f)
                rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
                # out/ 里必须有 analysis.json（与两个成品同源）
                z.write(p, rel)
                n += 1
                total += os.path.getsize(p)
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        bad = z.testzip()
    print('打包完成：%s' % OUT_NAME)
    print('  文件 %d 个，原始 %.2f MB，压缩 %.2f MB'
          % (n, total / 1048576, os.path.getsize(zpath) / 1048576))
    print('  完整性：%s' % ('OK' if bad is None else '损坏于 %s' % bad))
    for key in ('SKILL.md', 'references/', 'scripts/', 'examples/', 'out/'):
        c = sum(1 for x in names if x.startswith(key) or x == key)
        print('  %-14s %2d 项' % (key, c))
    return 0


if __name__ == '__main__':
    sys.exit(main())
