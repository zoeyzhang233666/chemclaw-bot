# -*- coding: utf-8 -*-
"""One-shot pipeline: validate -> workbook -> html -> (optional) browser check.

Usage:
    python build_all.py <case.json> [--as-of YYYY-MM-DD] [--skip-verify]
"""
import sys, os, json, subprocess, shutil

HERE = os.path.dirname(os.path.abspath(__file__))


def run(args, allow_fail=False):
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0 and not allow_fail:
        sys.stderr.write(r.stdout + '\n' + r.stderr + '\n')
        sys.exit('failed: %s' % ' '.join(args))
    return r


def find_node():
    for c in (os.environ.get('DSH_NODE'),
              shutil.which('node'),
              (__import__('shutil').which('node') or 'node')):
        if c and (os.path.isabs(c) and os.path.exists(c) or shutil.which(c)):
            return c
    return None


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)
    case_path = os.path.abspath(argv[0])
    as_of = argv[argv.index('--as-of') + 1] if '--as-of' in argv else None
    skip_verify = '--skip-verify' in argv
    outdir = os.path.dirname(case_path)
    py = sys.executable

    case = json.load(open(case_path, encoding='utf-8'))
    pid = case['meta']['case_id']
    stem = 'HS归类候选'

    checks = os.path.join(outdir, 'checks.json')
    vargs = [py, os.path.join(HERE, 'validators.py'), case_path, '--out', checks]
    if as_of:
        vargs += ['--as-of', as_of]
    run(vargs)
    print('[1/4] validators: pass ->', checks)

    xlsx = os.path.join(outdir, 'HS归类候选研究工作簿_%s.xlsx' % pid)
    run([py, os.path.join(HERE, 'build_workbook.py'), '--case', case_path, '--out', xlsx])
    print('[2/4] workbook:', xlsx, os.path.getsize(xlsx), 'bytes')

    html = os.path.join(outdir, 'HS归类候选研究报告_%s.html' % pid)
    run([py, os.path.join(HERE, 'build_html.py'), '--case', case_path, '--out', html])
    print('[3/4] html:', html, os.path.getsize(html), 'bytes')

    if skip_verify:
        print('[4/4] verify skipped')
        return
    node = find_node()
    if not node:
        print('[4/4] verify skipped: node not found')
        return
    prev = os.path.join(outdir, 'preview')
    r = run([node, os.path.join(HERE, 'verify_page.cjs'), html, prev], allow_fail=True)
    print('[4/4] verify:', (r.stdout or r.stderr or '').strip()[:600])
    if r.returncode != 0:
        print('      (verification failed; HTML itself was written)')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
