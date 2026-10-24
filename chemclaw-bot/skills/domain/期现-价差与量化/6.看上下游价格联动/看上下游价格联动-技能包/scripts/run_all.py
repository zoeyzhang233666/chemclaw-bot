# -*- coding: utf-8 -*-
"""
run_all.py —— 一条命令跑完整流程（抓取 → 解析 → 对齐 → 分析 → 报告 → 工作簿）

用法
  python run_all.py                # 用已有本地 HTML 快照，重建全部产物
  python run_all.py --fetch        # 先抓取 SunSirs 日页（需要 Chrome）
  python run_all.py --start 2023-10-07 --end 2026-10-20

产物
  processed/px_pta_daily.csv    对齐后的日频面板
  processed/qc.json             数据质量报告
  build/analysis.json           七步分析结果
  build/report.html             交互式报告（单文件）
  build/px_pta_workbook.xlsx    含公式的工作簿

为什么要有这个脚本：研究结论必须可复现。任何人拿到本目录，跑这一条命令，
就能从原始 HTML 快照重新生成完全相同的报告与工作簿。
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(name, args, optional=False):
    print(f'\n=== {name} ===')
    p = subprocess.run([sys.executable, os.path.join(HERE, name)] + args,
                       cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    out = (p.stdout or '') + (p.stderr or '')
    print(out.strip()[-2500:])
    if p.returncode != 0:
        if optional:
            print(f'!! {name} 失败（可跳过）')
            return False
        raise SystemExit(f'{name} 失败，退出码 {p.returncode}')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch', action='store_true', help='先抓取 SunSirs 逐日日页')
    ap.add_argument('--start', default='2023-10-07')
    ap.add_argument('--end', default='2026-10-20')
    a = ap.parse_args()

    if a.fetch:
        run('mkurls_jobs.py', ['jobs_sst.json', 'sst', a.start, a.end])
        # 抓取用 Node + 无头 Chrome，单独调用
        node = os.environ.get('NODE_EXE') or 'node'
        p = subprocess.run([node, os.path.join(HERE, 'cdp_fetch.js'),
                            os.path.join(HERE, 'jobs_sst.json')], cwd=HERE)
        if p.returncode != 0:
            raise SystemExit('抓取失败；请检查 CHROME_EXE 环境变量')

    run('parse_sunsirs.py', ['--raw', 'raw', '--pattern', 'sst_20*.html',
                             '--out', 'processed/sunsirs_daily.csv'])
    run('build_dataset.py', ['--start', a.start, '--end', a.end, '--out', 'processed'])
    run('analysis.py', ['--data', 'processed/px_pta_daily.csv', '--out', 'build/analysis.json'])
    run('build_html.py', ['build/analysis.json', 'build/report.html'])
    run('build_excel.py', ['processed/px_pta_daily.csv', 'build/analysis.json',
                           'build/px_pta_workbook.xlsx'])
    run('xlfn_fix.py', ['build/px_pta_workbook.xlsx'])
    print('\n全部完成。产物在 processed/ 与 build/。')
    print('提示：Excel 公式需要重算才有缓存值（可用 LibreOffice recalculate），'
          '校验脚本见 verify_excel.py。')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
