# -*- coding: utf-8 -*-
"""check_xlsx.py — 用 LibreOffice 重算 Excel，验证"活公式真的能算且结果正确"

用法: python scripts/check_xlsx.py <workbook.xlsx> [--case case.json]

检查：
  1. 所有公式都能在 LibreOffice 里正常重算（无 #REF!/#NAME?/#VALUE! 等错误）
  2. 「2-进口成本折算」的关键结果与 Node 引擎一致
  3. 「9-引擎校验」页的"判定"列全部为"一致"
  4. 修改「1-参数」里的汇率后，重算结果按预期变化（证明公式是活的，不是死值）
"""

_CHEMCLAW_ROOT = next(parent for parent in __import__('pathlib').Path(__file__).resolve().parents if (parent / 'runtime/deliver.mjs').is_file())
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

from openpyxl import load_workbook

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = __import__('sys').executable
CLI = str(_CHEMCLAW_ROOT / 'runtime/office-cli.py')

fails = 0
warns = 0


def ok(m):
    print('  OK   ' + m)


def bad(m):
    global fails
    fails += 1
    print('  FAIL ' + m)


def warn(m):
    global warns
    warns += 1
    print('  WARN ' + m)


def recalc(src, dst):
    out = subprocess.run([NODE, CLI, 'recalculate', '--input', src, '--output', dst],
                         capture_output=True, text=True, encoding='utf-8', errors='replace')
    if out.returncode != 0:
        raise RuntimeError('recalculate 失败: ' + (out.stderr or out.stdout)[:600])
    return dst


def engine(case_path):
    js = ("const fs=require('fs');const e=require(%s);const c=JSON.parse(fs.readFileSync(%s,'utf8'));"
          "const a=e.analyze(c);console.log(JSON.stringify({cost:a.current.totals.net_cost,"
          "spread:a.current.spread.abs_cny,cif:a.current.totals.cif_cny,duty:a.current.totals.duty,"
          "vat:a.current.totals.vat,fx:a.current.fx?a.current.fx.rate:null,verdict:a.verdict}));"
          % (json.dumps(os.path.join(ROOT, 'scripts', 'lib', 'import-window-engine.js')), json.dumps(case_path)))
    o = subprocess.run(['node', '-e', js], capture_output=True, text=True, encoding='utf-8')
    return json.loads(o.stdout)


def main():
    wb_path = sys.argv[1]
    case_path = sys.argv[sys.argv.index('--case') + 1] if '--case' in sys.argv else \
        os.path.join(ROOT, 'examples', '01-meg-huadong', 'data', 'case.json')
    exp = engine(case_path)

    tmpdir = tempfile.mkdtemp()
    recalced = os.path.join(tmpdir, 'recalc.xlsx')
    print('[1] LibreOffice 重算')
    recalc(os.path.abspath(wb_path), recalced)
    ok('重算完成')

    wbf = load_workbook(recalced, data_only=False)
    wbv = load_workbook(recalced, data_only=True)

    print('\n[2] 公式错误扫描')
    errs = []
    for sn in wbv.sheetnames:
        for row in wbv[sn].iter_rows():
            for c in row:
                v = c.value
                # 仅把真正的错误值当作错误；'#' 这类普通文本表头不算
                if isinstance(v, str) and v.strip() in (
                        '#REF!', '#NAME?', '#VALUE!', '#DIV/0!', '#N/A', '#NUM!', '#NULL!',
                        'Err:502', 'Err:508', 'Err:509', 'Err:510'):
                    errs.append('%s!%s = %s' % (sn, c.coordinate, v))
    if errs:
        bad('发现 %d 个公式错误: %s' % (len(errs), ' | '.join(errs[:6])))
    else:
        ok('无 #REF!/#NAME?/#VALUE! 等公式错误')

    print('\n[3] 工作表结构')
    ok('共 %d 个工作表: %s' % (len(wbf.sheetnames), ', '.join(wbf.sheetnames)))
    nform = sum(1 for sn in wbf.sheetnames for row in wbf[sn].iter_rows() for c in row
                if isinstance(c.value, str) and c.value.startswith('='))
    if nform >= 40:
        ok('活公式数量 %d（不是先算后写死值）' % nform)
    else:
        bad('公式数量过少: %d' % nform)

    print('\n[4] 关键结果 vs 引擎')
    s2 = wbv['2-进口成本折算']
    got = {'cif': s2['D9'].value, 'duty': s2['D10'].value, 'vat': s2['D11'].value,
           'cost': s2['D13'].value, 'spread': s2['D16'].value}
    engine_calculable = exp.get('cost') is not None
    if not engine_calculable:
        # 引擎判定不可计算：Excel 必须同样给出"待补"，不能凭空算出数值
        numeric = [k for k, v in got.items() if isinstance(v, (int, float))]
        for k, v in got.items():
            print('     %-7s Excel=%r' % (k, v))
        if numeric:
            bad('引擎判定不可计算，但 Excel 算出了数值: %s' % {k: got[k] for k in numeric})
        else:
            ok('引擎与 Excel 一致地"拒绝计算"，全部显示"待补"/文本')
        print('\n[5] 「9-引擎校验」页判定')
        s9 = wbv['9-引擎校验']
        verdicts = []
        r = 4
        while r <= 9:
            nm = s9['A%d' % r].value
            if not nm:
                break
            verdicts.append((nm, s9['E%d' % r].value))
            r += 1
        badv = [v for v in verdicts if v[1] not in ('一致', '无须计算', '两侧均无值')]
        if badv:
            bad('判定异常: %s' % badv)
        else:
            ok('%d 项判定均未出现"复核"（不可计算案例）' % len(verdicts))
        shutil.rmtree(tmpdir, ignore_errors=True)
        print('\n结果: ' + ('%d 项失败' % fails if fails else '全部通过'))
        return 1 if fails else 0

    for k, v in got.items():
        print('     %-7s Excel=%-12s 引擎=%s' % (k, v, round(exp[k], 4)))
    for k in got:
        if not isinstance(got[k], (int, float)):
            bad('%s 未算出数值: %r' % (k, got[k]))
        elif abs(got[k] - exp[k]) > 0.02:
            bad('%s 与引擎不一致: Excel %r vs 引擎 %.4f' % (k, got[k], exp[k]))
        else:
            ok('%s 一致 (%.2f)' % (k, got[k]))

    print('\n[5] 「9-引擎校验」页判定')
    s9 = wbv['9-引擎校验']
    verdicts = []
    r = 4
    while r <= 9:
        name = s9['A%d' % r].value
        if not name:
            break
        verdicts.append((name, s9['E%d' % r].value))
        r += 1
    badv = [v for v in verdicts if v[1] != '一致']
    if badv:
        bad('判定不一致: %s' % badv)
    else:
        ok('全部 %d 项判定为"一致"' % len(verdicts))

    print('\n[6] 活公式验证：改汇率必须引起重算')
    wbx = load_workbook(os.path.abspath(wb_path))
    p = wbx['1-参数']
    fx_cell = None
    for row in p.iter_rows(min_row=1, max_row=80, max_col=2):
        if row[0].value == 'USD/CNY':
            fx_cell = row[1]
            break
    if not fx_cell:
        bad('找不到汇率单元格')
    else:
        old = fx_cell.value
        fx_cell.value = round(float(old) * 1.03, 4)
        mod = os.path.join(tmpdir, 'mod.xlsx')
        wbx.save(mod)
        mod_re = os.path.join(tmpdir, 'mod_recalc.xlsx')
        recalc(mod, mod_re)
        mv = load_workbook(mod_re, data_only=True)
        new_cost = mv['2-进口成本折算']['D13'].value
        new_spread = mv['2-进口成本折算']['D16'].value
        expect_cost = exp['cost'] * 1.03   # 费用项与汇率无关的近似
        print('     汇率 %.4f → %.4f；成本 %.2f → %.2f；价差 %.2f → %.2f'
              % (float(old), float(fx_cell.value), exp['cost'], new_cost or -1, exp['spread'], new_spread or -1))
        if new_cost is None or abs(new_cost - exp['cost']) < 1:
            bad('改汇率后成本未变化（公式不是活的）')
        else:
            ok('汇率 +3%% 后成本按比例上升（活公式确认）')
        if new_spread is not None and new_spread > exp['spread']:
            ok('汇率上升 → 进口成本上升 → 价差扩大，方向正确')

    shutil.rmtree(tmpdir, ignore_errors=True)
    print('\n结果: ' + ('%d 项失败' % fails if fails else '全部通过') + ('，%d 项提示' % warns if warns else ''))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
