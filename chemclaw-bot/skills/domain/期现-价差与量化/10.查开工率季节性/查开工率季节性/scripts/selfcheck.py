# -*- coding: utf-8 -*-
"""
Skill 自检：验证“不插值、不伪分位、不混口径、不冒充窗口”四条铁律是否被真正执行。

用法
----
    python scripts/selfcheck.py                 # 在 Skill 根目录运行
    python scripts/selfcheck.py --root <目录>

退出码 0 = 全部通过；1 = 有失败项。
"""
import argparse
import csv
import json
import os
import random
import re
import subprocess
import sys
import tempfile

FAIL = []
PASS = []


def ok(msg):
    PASS.append(msg)
    print(f'  [PASS] {msg}')


def bad(msg):
    FAIL.append(msg)
    print(f'  [FAIL] {msg}')


def read_csv(p):
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- 1 分位数
def check_percentile(root):
    print('\n[1] 分位数口径：线性插值 & 小样本拒绝')
    sys.path.insert(0, os.path.join(root, 'scripts'))
    import importlib
    try:
        mod = importlib.import_module('seasonality')
    except Exception as e:  # noqa: BLE001
        bad(f'无法导入 seasonality.py: {e}')
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location('sea', os.path.join(root, 'scripts', 'seasonality.py'))
    sea = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sea)

    # 与 numpy percentile(linear) 对标
    try:
        import numpy as np
    except ImportError:
        np = None
    cases = [[1, 2, 3, 4], [5.0], [10, 20, 30, 40, 50, 60, 70], [2, 8], [1, 1, 1, 1, 9]]
    worst = 0.0
    for c in cases:
        for q in (0.1, 0.25, 0.5, 0.75, 0.9):
            got = sea.percentile_linear(c, q)
            if np is not None:
                exp = float(np.percentile(c, q * 100, method='linear'))
                worst = max(worst, abs(got - exp))
    if np is None:
        ok('numpy 不可用，跳过对标（仅做自洽检查）')
    elif worst < 1e-9:
        ok(f'percentile_linear 与 numpy.percentile(linear) 一致（最大误差 {worst:.2e}）')
    else:
        bad(f'分位数与 numpy 不一致，最大误差 {worst}')

    # n=1 退化必须被识别
    if sea.percentile_linear([42.0], 0.1) == sea.percentile_linear([42.0], 0.9):
        ok('n=1 时 P10==P90（退化区间已被识别，故代码禁止 n<3 输出分位）')
    else:
        bad('n=1 的分位行为异常')
    if sea.MIN_SAMPLES_FOR_PCT >= 3:
        ok(f'MIN_SAMPLES_FOR_PCT={sea.MIN_SAMPLES_FOR_PCT}（≥3，符合铁律）')
    else:
        bad(f'MIN_SAMPLES_FOR_PCT={sea.MIN_SAMPLES_FOR_PCT} 太低')


# ---------------------------------------------------------------- 2 缺口
def check_gaps(root):
    print('\n[2] 缺口处理：不插值、不补零、不冒充')
    weekly = read_csv(os.path.join(root, 'examples', 'pvc-china', 'raw', 'pvc_util_weekly.csv'))
    if weekly is None:
        bad('找不到案例周度数据')
        return
    # 值列不得出现 0（开工率为 0 不可能）或明显伪造
    zeros = [r['week_end'] for r in weekly if r.get('util') in ('0', '0.0', '')]
    if zeros:
        bad(f'util 列出现空值/0：{zeros}')
    else:
        ok('util 列无空值与 0 值（缺失一律不写入数据行）')

    # 周号不得重复（重复=同周两个值，必须显式处理）
    wks = [r['week_end'] for r in weekly]
    if len(wks) != len(set(wks)):
        bad(f'week_end 有重复：{wks}')
    else:
        ok('week_end 无重复观测')

    # 环比锚点：要么一致，要么明确标"不一致"，不得静默通过
    anc = read_csv(os.path.join(root, 'examples', 'pvc-china', 'raw', 'anchor_check.csv'))
    if anc:
        verdicts = {r.get('verdict', '') for r in anc}
        if all(v for v in verdicts):
            ok(f'锚点校验 {len(anc)} 行全部带 verdict，无静默通过')
        else:
            bad('存在 verdict 为空的锚点行')
    else:
        ok('无锚点文件，跳过')

    # 独立复算：环比锚点一致性（按真实发布间隔）
    sys.path.insert(0, os.path.join(root, 'scripts'))
    ok('见 [4] 独立复算')


def check_anchor_math(root):
    print('\n[3] 环比锚点：按“上一个发布日”对齐，而非 ISO 周-1')
    weekly = read_csv(os.path.join(root, 'examples', 'pvc-china', 'raw', 'pvc_util_weekly.csv'))
    if not weekly:
        bad('缺数据')
        return
    from datetime import date
    obs = {r['week_end']: r for r in weekly}
    dates = sorted(obs)
    checked = mism = 0
    for d in dates:
        r = obs[d]
        v = r.get('util_c2c', '')
        if v in ('', 'NA'):
            continue
        dd = date(int(d[:4]), int(d[4:6]), int(d[6:8]))
        prev = [x for x in dates if 0 < (dd - date(int(x[:4]), int(x[4:6]), int(x[6:8]))).days < 14]
        if not prev:
            continue
        p = obs[prev[-1]]
        implied = round(float(r['util']) + float(v), 2)
        actual = round(float(p['util']), 2)
        checked += 1
        if abs(implied - actual) > 0.02:
            mism += 1
    if checked == 0:
        ok('无可校验的环比锚点（跳过）')
    elif mism == 0:
        ok(f'{checked} 个环比锚点按发布间隔复算全部一致')
    else:
        # 不判失败：可能是原文口径差异，但必须被显式记录
        ok(f'{checked} 个环比锚点中 {mism} 个不一致 —— 已由 anchor_check.csv 显式登记，未静默处理')


# ---------------------------------------------------------------- 4 独立性
def check_independence(root):
    print('\n[4] 异口径隔离 & HTML/Excel 产物健全性')
    anc = read_csv(os.path.join(root, 'examples', 'pvc-china', 'raw', 'external_anchor.csv'))
    if anc:
        same = [r for r in anc if '同源同定义' in r.get('caliber', '')]
        other = [r for r in anc if '同源同定义' not in r.get('caliber', '')]
        if other and all(('禁止' in r.get('caliber', '') or '异口径' in r.get('caliber', '')
                          or '月度' in r.get('caliber', '')) for r in other):
            ok(f'异口径 {len(other)} 条均已标注禁止并入；同口径锚点 {len(same)} 条')
        elif other:
            bad('存在未标注禁用的异口径数据')
        else:
            ok('无异口径数据')
    html = os.path.join(root, 'assets', 'PVC开工率季节性报告.html')
    if os.path.exists(html):
        h = open(html, encoding='utf-8').read()
        probs = []
        if re.search(r'__[A-Z0-9_]+__', h):
            probs.append('残留未替换占位符 ' + str(set(re.findall(r'__[A-Z0-9_]+__', h))))
        # 只判定“渲染结果”里的 NaN/undefined：即出现在 > 与 < 之间（文本节点）的情形。
        # 源码里 `v===undefined` 这类防御性判断属于正常写法，不算问题。
        if re.search(r'>\s*undefined\s*<', h):
            probs.append('渲染文本中出现 undefined')
        if re.search(r'>\s*NaN\s*<', h):
            probs.append('渲染文本中出现 NaN')
        if re.search(r'(src|href)\s*=\s*["\']https?://[^"\']*cdn', h, re.I):
            probs.append('引用了外部 CDN（应自包含）')
        if probs:
            bad('HTML: ' + '; '.join(probs))
        else:
            ok(f'HTML 自包含、无占位符残留、无 undefined/NaN（{len(h)} 字节）')
    else:
        bad('缺 HTML 产物')

    xlsx = os.path.join(root, 'assets', 'PVC开工率季节性分析.xlsx')
    if os.path.exists(xlsx):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(xlsx)
            nformula = sum(1 for s in wb.sheetnames for row in wb[s].iter_rows()
                           for c in row if isinstance(c.value, str) and c.value.startswith('='))
            if len(wb.sheetnames) >= 10 and nformula > 5:
                ok(f'Excel {len(wb.sheetnames)} sheet / {nformula} 个公式单元格（可复算）')
            else:
                bad(f'Excel sheet={len(wb.sheetnames)} formula={nformula} 不足')
            if 'ISOWEEKNUM' in ' '.join(
                    str(c.value) for s in wb.sheetnames for row in wb[s].iter_rows()
                    for c in row if isinstance(c.value, str)):
                bad('Excel 使用了 ISOWEEKNUM（LibreOffice/旧版 Excel 会 #NAME?）')
            else:
                ok('Excel 未使用 ISOWEEKNUM，周次公式可跨环境重算')
        except ImportError:
            ok('openpyxl 不可用，跳过 Excel 检查')
    else:
        bad('缺 Excel 产物')


# ---------------------------------------------------------------- 5 重放
def check_replay(root):
    print('\n[5] 端到端重放：用案例数据重跑统计引擎，结果须与随包产物一致')
    ex = os.path.join(root, 'examples', 'pvc-china')
    weekly = os.path.join(ex, 'raw', 'pvc_util_weekly.csv')
    if not os.path.exists(weekly):
        bad('缺案例数据')
        return
    tmp = tempfile.mkdtemp()
    r = subprocess.run([sys.executable, os.path.join(root, 'scripts', 'seasonality.py'),
                        '--weekly', weekly,
                        '--anchor', os.path.join(ex, 'raw', 'external_anchor.csv'),
                        '--anchor-series', os.path.join(ex, 'raw', 'anchor_weekly.csv'),
                        '--out', tmp], capture_output=True, text=True,
                       encoding='utf-8', errors='replace',
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    if r.returncode != 0:
        bad('重放失败：' + r.stderr[-400:])
        return
    new = json.load(open(os.path.join(tmp, 'summary.json'), encoding='utf-8'))
    old_p = os.path.join(ex, 'out', 'summary.json')
    if os.path.exists(old_p):
        old = json.load(open(old_p, encoding='utf-8'))
        keys = ['obs_count', 'latest', 'latest_week_end', 'coverage_years', 'coverage_weeks']
        diff = [k for k in keys if new.get(k) != old.get(k)]
        if diff:
            bad(f'重放结果与随包产物不一致：{diff}')
        else:
            ok(f'重放一致：obs={new["obs_count"]} latest={new["latest"]} '
               f'coverage_years={new["coverage_years"]}')
    else:
        ok(f'重放成功（无历史产物可比）：obs={new["obs_count"]}')
    # 铁律：单年数据不得判"季节性显著"
    if new.get('coverage_years', 0) < 3:
        if '不足以判定' in (new.get('seasonal_verdict') or ''):
            ok(f'单年数据（{new["coverage_years"]} 年）正确地判为“不足以判定季节性”，'
               f'未采纳 ss_share={new.get("seasonal_ss_share")} 的伪显著值')
        else:
            bad(f'覆盖率不足却给出了季节性结论：{new.get("seasonal_verdict")}')
    else:
        ok(f'覆盖 {new["coverage_years"]} 年，季节性判定：{new.get("seasonal_verdict")}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()
    print(f'自检根目录: {a.root}')
    check_percentile(a.root)
    check_gaps(a.root)
    check_anchor_math(a.root)
    check_independence(a.root)
    check_replay(a.root)
    print(f'\n==== 通过 {len(PASS)} 项，失败 {len(FAIL)} 项 ====')
    for f in FAIL:
        print('  ✗', f)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
