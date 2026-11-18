# -*- coding: utf-8 -*-
"""run_pipeline.py —— 一键跑完整流程

    python scripts/run_pipeline.py --products MA SA PP TA --as-of 2026-10-20 \
        --outdir build --html build/dashboard.html --excel build/工作簿.xlsx

步骤：
  1. 抓取逐合约历史日线（若 data/raw 缺该合约）      fetch_contracts.py
  2. 抓取当日行情 + 仓单（郑商所官方 / 东财 DCE）    fetch_quotes.py
  3. 规则校验 + 月差扫描 + 分位统计                  scan_spreads.py
  4. 生成交互式 HTML 看板                            build_html.py
  5. 生成 Excel 工作簿                               build_excel.py
  6. 自检（已知答案）                                selftest.py

任一步失败即中止并打印原因，不静默跳过。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def run(script, args, cwd=None):
    cmd = [PY, os.path.join(HERE, script)] + args
    print('\n$ ' + ' '.join(os.path.basename(c) if c.startswith(HERE) else c for c in cmd))
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    p = subprocess.run(cmd, cwd=cwd or ROOT, env=env)
    if p.returncode != 0:
        print(f'!! {script} 失败，退出码 {p.returncode}')
        sys.exit(p.returncode)


def main():
    ap = argparse.ArgumentParser(description='异常月差扫描一键流水线')
    ap.add_argument('--products', nargs='+', default=['MA', 'SA', 'PP', 'TA'])
    ap.add_argument('--as-of', default=None, help='YYYY-MM-DD，默认今天')
    ap.add_argument('--years', nargs='+', default=None,
                    help='需要抓取的历史交割年份，默认近 5 年')
    ap.add_argument('--outdir', default='build')
    ap.add_argument('--html', default=None)
    ap.add_argument('--excel', default=None)
    ap.add_argument('--skip-fetch', action='store_true', help='数据已就绪，只重算与出图')
    ap.add_argument('--industry', default=os.path.join(ROOT, 'data', 'industry_data.json'))
    a = ap.parse_args()

    import datetime as dt
    as_of = a.as_of or dt.date.today().isoformat()
    years = a.years or [str(dt.date.today().year - k) for k in range(1, 6)]
    os.makedirs(a.outdir, exist_ok=True)
    html_out = a.html or os.path.join(a.outdir, 'dashboard.html')
    excel_out = a.excel or os.path.join(a.outdir, '异常月差扫描工作簿.xlsx')

    if not a.skip_fetch:
        run('fetch_contracts.py', ['--products'] + a.products + ['--years'] + years)
        # 行情日期通过环境变量传给 fetch_quotes
        os.environ['QUOTE_DATE'] = as_of
        run('fetch_quotes.py', [])

    quotes_json = os.path.join(ROOT, f'quotes_{as_of}.json')
    scan_json = os.path.join(a.outdir, 'scan_result.json')
    run('scan_spreads.py', ['--raw', os.path.join(ROOT, 'data', 'raw'),
                            '--as-of', as_of, '--out', scan_json])

    qarg = ['--quotes', quotes_json] if os.path.exists(quotes_json) else []
    run('build_html.py', ['--scan', scan_json, '--industry', a.industry, '--out', html_out] + qarg)
    run('build_excel.py', ['--scan', scan_json, '--industry', a.industry,
                           '--out', excel_out] + qarg)
    run('selftest.py', [])

    print('\n' + '=' * 60)
    print(f'完成：\n  HTML  {html_out}\n  Excel {excel_out}\n  扫描  {scan_json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
