# -*- coding: utf-8 -*-
"""build_all.py —— 一条命令跑完：分析 → HTML → Excel → 校验

用法：
    python scripts/build_all.py examples/01-px-to-pta/project.json --out-dir out
"""
import argparse, glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')


def run(args, cwd=None):
    print('▶', ' '.join(args[1:]))
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    for line in (r.stdout or '').splitlines():
        print('  ', line)
    if r.returncode != 0:
        print('  实测失败：')
        for line in (r.stderr or '').splitlines()[-25:]:
            print('     ', line)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--out-dir', default='out')
    ap.add_argument('--breakpoints', default='')
    ap.add_argument('--rolling', type=int, default=20)
    ap.add_argument('--z', type=float, default=1.5)
    ap.add_argument('--skip-browser', action='store_true')
    args = ap.parse_args()

    proj = args.project
    out = args.out_dir
    os.makedirs(out, exist_ok=True)
    pj = json.load(open(proj, encoding='utf-8'))

    bp = args.breakpoints
    if not bp:
        bs = (pj.get('params') or {}).get('breakpoints') or []
        bp = ','.join(bs) if bs else ''

    ev_path = os.path.join(os.path.dirname(proj), 'events.json')
    py = sys.executable
    rc = 0

    a = [py, os.path.join(HERE, 'analyze.py'), proj, '--out-dir', out,
         '--rolling', str(args.rolling), '--z', str(args.z)]
    if bp:
        a += ['--breakpoints', bp]
    rc |= run(a)

    analysis = os.path.join(out, 'analysis.json')
    if not os.path.exists(analysis):
        print('未生成 analysis.json，终止')
        return 1

    h = [py, os.path.join(HERE, 'build_html.py'), analysis, '--out-dir', out]
    if os.path.exists(ev_path):
        h += ['--events', ev_path]
    rc |= run(h)

    x = [py, os.path.join(HERE, 'build_xlsx.py'), analysis, '--out-dir', out]
    if os.path.exists(ev_path):
        x += ['--events', ev_path]
    rc |= run(x)

    htmls = sorted(glob.glob(os.path.join(out, '*.html')))
    xlsxs = sorted(glob.glob(os.path.join(out, '*.xlsx')))
    if htmls:
        rc |= run([py, os.path.join(HERE, 'check_html.py'), htmls[0], analysis])
    if xlsxs:
        rc |= run([py, os.path.join(HERE, 'check_xlsx.py'), xlsxs[0], analysis])

    if htmls and not args.skip_browser:
        b = run([py, os.path.join(HERE, 'qa_render.py'), htmls[0]])
        if b != 0:
            print('（浏览器实测跳过或失败——如需实测，'
                  '请先用 scripts/start_browser.ps1 启动带调试端口的 Chrome）')

    print('\n产物：')
    for p in htmls + xlsxs:
        print('  %s  (%.1f KB)' % (p, os.path.getsize(p) / 1024))
    print('\n结论：%s' % ('全部通过' if rc == 0 else '有检查未通过，见上'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
