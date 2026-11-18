#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Excel（COM）重算工作簿，核对"公式算出来的数"是否等于引擎算出来的数。

为什么必须做：openpyxl 只写公式不算数。不重算就发现不了公式写错、引用错位、
组合情景行错位、历史成本列错位这类问题。

用法：
  python check_workbook.py out.xlsx result.json [--tol 0.01]
返回：0 全部一致；1 有不一致；2 环境无 Excel（只做静态检查）
"""
import argparse
import json
import os
import sys

PASS, FAIL = [], []


def ok(m):
    PASS.append(m)
    print('  [OK]   ' + m)


def bad(m):
    FAIL.append(m)
    print('  [FAIL] ' + m)


def close(a, b, tol):
    try:
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def col(i):
    """1 -> A"""
    s = ''
    while i > 0:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    ap.add_argument('result')
    ap.add_argument('--tol', type=float, default=0.01)
    ap.add_argument('--tol-pct', type=float, default=0.0001)
    a = ap.parse_args()
    R = json.load(open(a.result, encoding='utf-8'))

    try:
        import win32com.client as w32
    except ImportError:
        print('[WARN] 未安装 pywin32：跳过公式重算（静态检查见 validate/check_result）。')
        return 2

    xl = w32.DispatchEx('Excel.Application')
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = None
    try:
        wb = xl.Workbooks.Open(os.path.abspath(a.xlsx), ReadOnly=True, UpdateLinks=0)
        xl.CalculateFullRebuild()
        sh = {s.Name: s for s in wb.Worksheets}
        print('工作表：', ' / '.join(sh.keys()))

        def V(sheet, ref):
            return sh[sheet].Range(ref).Value

        comp = [m for m in R['materials'] if m.get('cost') is not None]

        # ---------- 1_原料参数 ----------
        print('\n== 1_原料参数 ==')
        for i, m in enumerate(R['materials']):
            r = 4 + i
            L = V('1_原料参数', 'L%d' % r)
            M = V('1_原料参数', 'M%d' % r)
            if m.get('cost') is None:
                if L in (None, '', 0) and M in (None, ''):
                    ok('%s 无价格 → 成本/占比为空' % m['name'])
                else:
                    bad('%s 无价格却算出 %r / %r' % (m['name'], L, M))
                continue
            if close(L, m['cost'], a.tol):
                ok('%s 单项成本 %.2f' % (m['name'], m['cost']))
            else:
                bad('%s 单项成本 Excel=%r 引擎=%.4f' % (m['name'], L, m['cost']))
            if close(M, m['share'] / 100.0, a.tol_pct):
                ok('%s 占比 %.4f%%' % (m['name'], m['share']))
            else:
                bad('%s 占比 Excel=%r 引擎=%.6f' % (m['name'], M, m['share'] / 100.0))
        tot = V('1_原料参数', 'L%d' % (4 + len(R['materials'])))
        (ok if close(tot, R['total'], a.tol) else bad)('合计 Excel=%r 引擎=%.4f' % (tot, R['total']))

        # ---------- 2_成本构成 ----------
        print('\n== 2_成本构成 ==')
        for i, m in enumerate(comp):
            d = V('2_成本构成', 'D%d' % (4 + i))
            (ok if close(d, m['cost'], a.tol) else bad)('D%d %s=%.2f' % (4 + i, m['name'], m['cost']) if close(d, m['cost'], a.tol)
                                                       else 'D%d Excel=%r 引擎=%.4f' % (4 + i, d, m['cost']))

        # ---------- 3_敏感性矩阵 A ----------
        print('\n== 3_敏感性矩阵 A（热力图） ==')
        # 动态定位热力图首行：表头含 "单耗(t/t)" 且 A 列为 "原料"
        ws3 = sh['3_敏感性矩阵']
        heat_first = None
        for rr in range(1, 60):
            if ws3.Cells(rr, 1).Value == '原料' and isinstance(ws3.Cells(rr, 2).Value, str) \
               and '单耗' in ws3.Cells(rr, 2).Value:
                heat_first = rr + 1
                break
        if heat_first is None:
            bad('未找到热力图表头行')
        else:
            for i, s in enumerate(R['sensitivity']):
                r = heat_first + i
                for j, c in enumerate(s['cells']):
                    ref = '%s%d' % (col(4 + j), r)
                    v = V('3_敏感性矩阵', ref)
                    exp = c['cost_delta']
                    (ok if close(v, exp, a.tol) else bad)(
                        '%s %s Δ=%.2f' % (s['name'], c['label'], exp) if close(v, exp, a.tol)
                        else '%s %s Excel=%r 引擎=%.4f' % (s['name'], c['label'], v, exp))
            tr = heat_first + len(R['sensitivity'])
            for j, rt in enumerate(R['rates']):
                v = V('3_敏感性矩阵', '%s%d' % (col(4 + j), tr))
                exp = next(x['delta'] for x in R['auto_combos'] if abs(x['ratio'] - rt['ratio']) < 1e-12)
                (ok if close(v, exp, a.tol) else bad)('同步 %s Δ=%.2f' % (rt['label'], exp) if close(v, exp, a.tol)
                                                     else '同步 %s Excel=%r 引擎=%.4f' % (rt['label'], v, exp))

        # ---------- 3_敏感性矩阵 C 组合情景 ----------
        print('\n== 组合情景 C ==')
        title_row = None
        for r in range(1, 160):
            v = sh['3_敏感性矩阵'].Cells(r, 1).Value
            if isinstance(v, str) and 'C. 组合情景' in v:
                title_row = r
                break
        if title_row is None:
            bad('未找到 "C. 组合情景" 区块')
        else:
            cas = title_row + 2
            nm = len(comp)
            for i, c in enumerate(R['combos']):
                r = cas + i
                newc = V('3_敏感性矩阵', '%s%d' % (col(2 + nm + 1), r))
                (ok if close(newc, c['new_total'], a.tol) else bad)(
                    '%s 情景成本=%.2f' % (c['name'], c['new_total']) if close(newc, c['new_total'], a.tol)
                    else '%s Excel=%r 引擎=%.4f' % (c['name'], newc, c['new_total']))

        # ---------- 5_历史理论成本 ----------
        print('\n== 5_历史理论成本 ==')
        ws = sh['5_历史理论成本']
        last_col = None
        for cc in range(1, 80):
            h = ws.Cells(3, cc).Value
            if isinstance(h, str) and '历史理论原料成本' in h:
                last_col = cc
                break
        if not last_col:
            bad('未找到历史成本列')
        else:
            badn = 0
            for i, row in enumerate(R['history']['rows']):
                v = V('5_历史理论成本', '%s%d' % (col(last_col), 4 + i))
                if not close(v, row['cost'], a.tol):
                    badn += 1
                    if badn <= 3:
                        bad('历史 %s Excel=%r 引擎=%.4f' % (row['date'], v, row['cost']))
            (ok if badn == 0 else bad)('历史成本 %d 行全部一致' % len(R['history']['rows'])
                                       if badn == 0 else '历史成本 %d/%d 行不一致' % (badn, len(R['history']['rows'])))

        # ---------- 6_贡献分解 ----------
        print('\n== 6_贡献分解 ==')
        ws6 = sh['6_贡献分解']
        n = 0
        for r in range(1, 80):
            v = ws6.Cells(r, 1).Value
            if isinstance(v, str) and v.startswith('窗口'):
                n += 1
            if isinstance(v, str) and v == '合计':
                pass
        (ok if n >= 1 else bad)('6_贡献分解 含 %d 个时间窗区块' % n)

        # ---------- 10_与产品价并列 ----------
        if '10_与产品价并列' in sh:
            v = sh['10_与产品价并列'].Range('C%d' % (4 + len(R['history']['rows']) - 1)).Value
            exp = R['history']['rows'][-1]['cost']
            (ok if close(v, exp, a.tol) else bad)('10 表末行成本引用=%.2f' % exp if close(v, exp, a.tol)
                                                 else '10 表末行 Excel=%r 引擎=%.4f' % (v, exp))
    finally:
        if wb is not None:
            try:
                wb.Close(SaveChanges=False)
            except Exception:
                pass
        try:
            xl.Quit()
        except Exception:
            pass

    print('\n== 合计：%d 通过 / %d 失败 ==' % (len(PASS), len(FAIL)))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
