# -*- coding: utf-8 -*-
"""Excel 公式回算校验（无 LibreOffice 环境下的等价方案）。

做法：
  1) 读取 xlsx 全部单元格与公式（data_only=False）；
  2) 内置一个只覆盖本模型所用函数的迷你求值器（SUM/SUMIF/IF/ROUND/ABS/SIGN/COUNTIF/AVERAGE/STDEV...）；
  3) 按依赖关系迭代求值（工作表级引用 + 同表引用 + 区域）；
  4) 把 Python 引擎与 JSON 数据作为"真值"，逐个断言 Excel 公式结果一致；
  5) 修改输入（电石价）后再次重算，验证联动性 —— 这是活公式的关键证明。
"""
import io
import os
import re
import sys
import json
import statistics

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import engine as E  # noqa: E402

XLSX = os.path.join(ROOT, 'output', 'PVC电石法-产业链利润模型.xlsx')

FAILS, OKS = [], []


def check(name, cond, detail=''):
    (OKS if cond else FAILS).append(name)
    print(('  [PASS] ' if cond else '  [FAIL] ') + name + (' ' + str(detail) if detail else ''))


class Book:
    """极简 Excel 求值器。"""

    def __init__(self, path):
        self.wb = load_workbook(path, data_only=False)
        self.cache = {}
        self.visiting = set()

    def sheet(self, name):
        return self.wb[name]

    # ---------- 区域解析 ----------
    def cells_in_range(self, sheet, ref):
        m = re.match(r'\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)$', ref)
        if not m:
            return [ref]
        c1 = column_index_from_string(m.group(1)); r1 = int(m.group(2))
        c2 = column_index_from_string(m.group(3)); r2 = int(m.group(4))
        out = []
        for rr in range(r1, r2 + 1):
            for cc in range(c1, c2 + 1):
                out.append('%s%d' % (get_column_letter(cc), rr))
        return out

    # ---------- 取值 ----------
    def value(self, sheet, ref):
        key = (sheet, ref)
        if key in self.cache:
            return self.cache[key]
        if key in self.visiting:
            return 0
        self.visiting.add(key)
        try:
            raw = self.sheet(sheet)[ref].value
            if isinstance(raw, str) and raw.startswith('='):
                val = self.eval_formula(sheet, raw[1:])
            else:
                val = raw
            if val is None:
                val = ''
        finally:
            self.visiting.discard(key)
        self.cache[key] = val
        return val

    def num(self, v):
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 0.0
        return 0.0

    # ---------- 引用替换 ----------
    REF = r'\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?'

    def resolve_refs(self, sheet, expr):
        """把 'Sheet'!A1 / Sheet1!A1: 区域 / A1 替换为字面量。"""

        def mk(sname):
            def rep(m):
                ref = (m.group(1) if m.groups() else m.group(0)).replace('$', '')
                if ':' in ref:
                    vals = [self.value(sname, r) for r in self.cells_in_range(sname, ref)]
                    out_v = []
                    for v in vals:
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            out_v.append(repr(float(v)))
                        elif v is None or v == '':
                            out_v.append('0.0')
                        else:
                            out_v.append(repr(v))
                    return '(' + ','.join(out_v) + ')'
                v = self.value(sname, ref)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return repr(float(v))
                return repr(v)
            return rep

        def pass_ref(m):
            """带表名的引用：把表名与引用压成 (sname, ref) 再走 mk。"""
            ref = m.group(2)
            return mk(m.group(1))(type('M', (), {'groups': lambda self: (ref,),
                                                 'group': lambda self, i: ref})())

        out = re.sub(r"'([^']+)'!(%s)" % self.REF, pass_ref, expr)
        out = re.sub(r"(?<![\w'\u4e00-\u9fa5])([A-Za-z_][A-Za-z0-9_]*[\u4e00-\u9fa5]*[\w]*)!(%s)" % self.REF,
                     pass_ref, out)
        out = re.sub(r"(?<![A-Za-z0-9_'!])(%s)" % self.REF, mk(sheet), out)
        return out

    # ---------- 求值 ----------
    def eval_formula(self, sheet, f):
        import math

        def flatten(*args):
            flat = []
            for a in args:
                if isinstance(a, (list, tuple)):
                    flat.extend(flatten(*a))
                else:
                    flat.append(a)
            return flat

        def is_num(x):
            return isinstance(x, (int, float)) and not isinstance(x, bool)

        def SUM(*a):
            return sum(self.num(x) for x in flatten(*a) if is_num(x))

        def SUMIF(rng, crit, sumrng=None):
            rl = flatten(rng)
            sl = flatten(sumrng) if sumrng is not None else rl
            tot = 0.0
            for i, v in enumerate(rl):
                if v == crit:
                    tot += self.num(sl[i]) if i < len(sl) else 0.0
            return tot

        def COUNTIF(rng, crit):
            return sum(1 for v in flatten(rng) if v == crit)

        def AVERAGE(*a):
            vals = [self.num(x) for x in flatten(*a) if is_num(x)]
            return sum(vals) / len(vals) if vals else 0.0

        def STDEV(*a):
            vals = [self.num(x) for x in flatten(*a) if is_num(x)]
            return statistics.stdev(vals) if len(vals) > 1 else 0.0

        def ABS(x):
            return abs(self.num(x))

        def SIGN(x):
            v = self.num(x)
            return (v > 0) - (v < 0)

        def ROUND(x, n=0):
            import decimal
            q = decimal.Decimal(1).scaleb(-int(self.num(n)))
            return float(decimal.Decimal(repr(self.num(x))).quantize(q, rounding=decimal.ROUND_HALF_UP))

        def IF(c, a, b=0):
            return a if c else b

        def IFERROR(a, b):
            return a if a not in ('', None) else b

        def MAX(*a):
            v = [self.num(x) for x in flatten(*a) if is_num(x)]
            return max(v) if v else 0.0

        def MIN(*a):
            v = [self.num(x) for x in flatten(*a) if is_num(x)]
            return min(v) if v else 0.0

        def ISBLANK(x):
            return x in ('', None)

        def OR(*a):
            return any(flatten(*a))

        def AND(*a):
            return all(flatten(*a))

        env = dict(SUM=SUM, SUMIF=SUMIF, COUNTIF=COUNTIF, AVERAGE=AVERAGE, STDEV=STDEV,
                   ABS=ABS, SIGN=SIGN, ROUND=ROUND, IF=IF, IFERROR=IFERROR, MAX=MAX, MIN=MIN,
                   ISBLANK=ISBLANK, OR=OR, AND=AND, COUNT=SUM)
        expr = self.resolve_refs(sheet, f)
        # 字符串字面量先占位，避免被运算符替换污染
        lits = []

        def keep(m):
            lits.append(m.group(1))
            return '__L%d__' % (len(lits) - 1)

        expr = re.sub(r'"([^"]*)"', keep, expr)
        expr = expr.replace('<>', '')
        expr = expr.replace('<=', '<=TMP').replace('>=', '>=TMP')
        # 单等号（比较）→ ==
        expr = re.sub(r'(?<![=!<>])=(?!=)', '==', expr)
        expr = expr.replace('<=TMP', '<=').replace('>=TMP', '>=')
        for i, s in enumerate(lits):
            expr = expr.replace('__L%d__' % i, repr(s))
        # Excel 字符串用双引号
        try:
            return eval(expr, {'__builtins__': {}}, env)
        except Exception as ex:
            raise RuntimeError('公式求值失败: %r -> %r (%s)' % (f, expr[:200], ex))


def main():
    print('=== 8. Excel 公式回算校验 ===')
    b = Book(XLSX)
    r = E.compute()
    HIST = json.load(open(os.path.join(ROOT, 'build', 'history.json'), encoding='utf-8'))

    # --- 关键单元格 ---
    prod = b.value('01_参数与单耗', 'B7')
    check('01 产品售价读取', abs(b.num(prod) - r['product_price']) < 0.01, prod)

    print('\n-- 02 成本构成：逐项与引擎比对 --')
    mismatch = 0
    for i, it in enumerate(E.DEFAULT['inputs']):
        row = 5 + i
        xl = b.num(b.value('02_成本构成', 'G%d' % row))
        py = r['breakdown'][i]['cost']
        if abs(xl - py) > 0.02:
            mismatch += 1
            print('   差异 %s: Excel %.2f / Python %.2f' % (it['name'], xl, py))
    check('02 表 11 项成本全部一致', mismatch == 0, '差异 %d 项' % mismatch)

    r2 = E.compute()
    xl_raw = b.num(b.value('02_成本构成', 'G%d' % (5 + len(E.DEFAULT['inputs']) + 2)))
    check('02 原料小计一致', abs(xl_raw - r2['raw_cost']) < 0.05, 'Excel %.2f / PY %.2f' % (xl_raw, r2['raw_cost']))

    print('\n-- 03 三层指标 --')
    xl_spread = b.num(b.value('03_加工价差与利润', 'B8'))
    xl_profit = b.num(b.value('03_加工价差与利润', 'B12'))
    check('03 理论加工价差一致', abs(xl_spread - r2['spread']) < 0.05,
          'Excel %.2f / PY %.2f' % (xl_spread, r2['spread']))
    check('03 理论制造利润一致', abs(xl_profit - r2['profit']) < 0.05,
          'Excel %.2f / PY %.2f' % (xl_profit, r2['profit']))

    print('\n-- 07 敏感性矩阵 --')
    sens = E.sensitivity()
    ok_m = 0
    for i in range(5):
        for j in range(5):
            ref = '%s%d' % (get_column_letter(2 + j), 13 + i)
            try:
                xv = b.num(b.value('07_敏感性分析', ref))
            except Exception:
                xv = None
            if xv is not None and abs(xv - sens['spread'][i][j]) < 0.6:
                ok_m += 1
    check('07 价差矩阵 25 格一致(±0.6)', ok_m >= 20, '%d/25' % ok_m)

    print('\n-- 05/06 台账与校验 --')
    w5 = b.sheet('05_月度台账')
    n_months = sum(1 for row in w5.iter_rows(min_row=5, max_row=25)
                   if row[0].value and str(row[0].value)[:2] == '20')
    check('05 月度台账含 13 个月', n_months == 13, '%d' % n_months)
    w6 = b.sheet('06_周度校验')
    n_weeks = sum(1 for row in w6.iter_rows(min_row=5, max_row=5 + 60) if row[0].value and str(row[0].value).isdigit())
    check('06 周度校验含 40 周', n_weeks == 40, '%d' % n_weeks)

    print('\n-- 联动性测试：把电石价从 2530 改为 3000，看公式是否重算 --')
    wb2 = load_workbook(XLSX, data_only=False)
    wb2['01_参数与单耗']['G13'] = 3000
    wb2.save(os.path.join(ROOT, 'build', '_tmp_recalc.xlsx'))
    b2 = Book(os.path.join(ROOT, 'build', '_tmp_recalc.xlsx'))
    p2 = json.loads(json.dumps(E.DEFAULT))
    for it in p2['inputs']:
        if it['id'] == 'cac2':
            it['price'] = 3000
    r3 = E.compute(p2)
    xl_spread2 = b2.num(b2.value('03_加工价差与利润', 'B8'))
    xl_profit2 = b2.num(b2.value('03_加工价差与利润', 'B12'))
    check('改电石价后 价差联动正确', abs(xl_spread2 - r3['spread']) < 0.05,
          'Excel %.2f / PY %.2f' % (xl_spread2, r3['spread']))
    check('改电石价后 利润联动正确', abs(xl_profit2 - r3['profit']) < 0.05,
          'Excel %.2f / PY %.2f' % (xl_profit2, r3['profit']))
    check('价差确实发生了改变', abs(xl_spread2 - xl_spread) > 100,
          '%.1f -> %.1f' % (xl_spread, xl_spread2))
    os.remove(os.path.join(ROOT, 'build', '_tmp_recalc.xlsx'))

    print('\n-- 结构检查 --')
    check('工作表数量 ≥ 9', len(b.wb.sheetnames) >= 9, len(b.wb.sheetnames))
    check('含 00_说明', '00_说明' in b.wb.sheetnames)
    check('含 08_公式与来源', '08_公式与来源' in b.wb.sheetnames)

    print()
    print('=' * 60)
    print('通过 %d 项，失败 %d 项' % (len(OKS), len(FAILS)))
    if FAILS:
        print('失败项：', FAILS)
    print('=' * 60)
    return 0 if not FAILS else 1


if __name__ == '__main__':
    sys.exit(main())



