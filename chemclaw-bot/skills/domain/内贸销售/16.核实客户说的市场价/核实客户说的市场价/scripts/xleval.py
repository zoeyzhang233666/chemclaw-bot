#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xleval.py — 极简 Excel 公式求值器（只覆盖本 Skill 生成的工作簿用到的语法）。

为什么自带一个而不是用 Excel/LibreOffice：
  * 交付要给不同电脑用，不能假定装了 Office；
  * 只要能把「改客户价 → 结论怎么变」算出来，就足以验证公式没写错。

支持：单元格/区域/跨表引用、+ - * / ( ) ^、比较 = <> > >= < <=、
IF / IFERROR / AND / OR / NOT / ABS / ROUND / MAX / MIN / AVERAGE / SUM / MEDIAN / COUNT / TEXT、
字符串 "" 与 & 连接、TRUE/FALSE。
不含：日期函数、查找函数、数组公式。

已知限制：不支持 Excel 的「数字与文本比较」语义（如 0="abc" 为 TRUE）；本工作簿不依赖该语义。
"""
from __future__ import annotations

import re

from openpyxl.utils import range_boundaries


# 单元格引用：可选的「表名!」，表名可用单引号包裹。
# 关键约束：地址前必须是「A1」能开始的位置（前面不是字母/数字/下划线/中文/引号），
# 否则「不含税」这类中文会被误当成列名，把后面的数字当成行号。
_REF = re.compile(
    r"(?:(?P<q>'(?P<s1>[^']+)'|(?P<s2>[A-Za-z0-9_\u4e00-\u9fff]+))\s*!\s*)?"
    r"(?P<addr>\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)"
)
_LITERAL = re.compile(r'"(?:[^"]|"")*"')


def _literals_out(expr):
    """把字符串字面量换成占位符，避免被引用正则误伤。
    占位符用 π 包裹（Excel 公式里不会出现），不会被误认成 A1 这类引用。"""
    lits = []

    def sub(m):
        lits.append(m.group(0))
        return "\u03c0" + str(len(lits) - 1) + "\u03c0"

    return _LITERAL.sub(sub, expr), lits


def _literals_back(expr, lits):
    for i, s in enumerate(lits):
        expr = expr.replace("\u03c0" + str(i) + "\u03c0", s)
    return expr


def translate(expr, default_sheet, on_ref):
    """把 Excel 公式体翻译成 Python 表达式。on_ref(sheet, addr) 返回一个 Python 名称。"""
    tmp, lits = _literals_out(expr)

    def rep(m):
        sheet = m.group("s1") or m.group("s2") or default_sheet
        return on_ref(sheet, m.group("addr").replace("$", ""))

    out, pos = [], 0
    for m in _REF.finditer(tmp):
        prev = tmp[m.start() - 1] if m.start() > 0 else ""
        after = tmp[m.end()] if m.end() < len(tmp) else ""
        # 地址前后若紧邻字母/数字/下划线/中文，说明它不是独立引用（如「不含税」「ABC1」之类误配）
        if re.match(r"[A-Za-z0-9_\u4e00-\u9fff]", prev) and not m.group("q"):
            continue
        if re.match(r"[A-Za-z0-9_\u4e00-\u9fff]", after):
            continue
        out.append(tmp[pos:m.start()])
        out.append(rep(m))
        pos = m.end()
    out.append(tmp[pos:])
    s = _literals_back("".join(out), lits)
    # 布尔字面量
    s = re.sub(r"\bTRUE\b", "True", s)
    s = re.sub(r"\bFALSE\b", "False", s)
    s = s.replace('"', "'")
    s = _rewrite_compare(s)
    s = s.replace("&", "+")
    return s


_OPS = ("<>", ">=", "<=", "=", ">", "<")
_FUNC_CALL = re.compile(r"\b[A-Z]+\s*\(")


def _split_top(expr, sep):
    """按顶层（不在括号/引号内）分隔符切分。单引号与双引号都视为字符串边界。"""
    out, depth, cur, q = [], 0, [], None
    i = 0
    while i < len(expr):
        ch = expr[i]
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in ("'", '"'):
            q = ch
            cur.append(ch)
        elif ch in "([":
            depth += 1
            cur.append(ch)
        elif ch in ")]":
            depth -= 1
            cur.append(ch)
        elif depth == 0 and expr[i:i + len(sep)] == sep:
            out.append("".join(cur))
            cur = []
            i += len(sep)
            continue
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return out


def _unwrap(s):
    """如果整个表达式被一对括号包住，就去掉这层括号。"""
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        ok = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    ok = False
                    break
        if not ok:
            break
        s = s[1:-1].strip()
    return s


def _rewrite_compare(s):
    """把 Excel 比较写成函数调用，才能像 Excel 一样处理空值/类型。

    只有「整段表达式的最外层」存在比较时才改写；被函数调用包住的情况
    （如 IF(a=b,…)）由那个函数参数各自递归处理。
    """
    s = _unwrap(s)
    for op in _OPS:
        parts = _split_top(s, op)
        if len(parts) == 2:
            left, right = parts
            return f"_CMP({op!r},{_rewrite_compare(left)},{_rewrite_compare(right)})"
    # 逐参数改写函数调用内部的比较
    return _rewrite_in_calls(s)


_CALL = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _rewrite_in_calls(s):
    """对 IF(...)/AND(...) 等调用，改写每个参数内部的比较。"""
    out, i = [], 0
    while True:
        m = _CALL.search(s, i)
        if not m:
            out.append(s[i:])
            break
        name = m.group(1)
        out.append(s[i:m.end()])
        # 找到匹配的右括号
        depth, j = 1, m.end()
        while j < len(s) and depth:
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
            j += 1
        inner = s[m.end():j - 1]
        args = _split_commas(inner)
        out.append(",".join(_rewrite_compare(a) for a in args))
        out.append(")")
        i = j
    return "".join(out)


def _split_commas(s):
    out, depth, cur, q = [], 0, [], None
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in ("'", '"'):
            q = ch
            cur.append(ch)
        elif ch in "([":
            depth += 1
            cur.append(ch)
        elif ch in ")]":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out




class _ERR:
    def __init__(self, kind="err"):
        self.kind = kind

    def __repr__(self):
        return f"<ERR {self.kind}>"


class _Blank:
    """空单元格的哨兵：参与算术时按 0，参与文本比较时按 ""，参与逻辑时按 FALSE。"""

    def __repr__(self):
        return "<BLANK>"

    # 算术：空单元格 = 0
    def __add__(self, o): return _num(o)
    def __radd__(self, o): return _num(o)
    def __sub__(self, o): return -_num(o)
    def __rsub__(self, o): return _num(o)
    def __mul__(self, o): return 0
    def __rmul__(self, o): return 0
    def __truediv__(self, o): return 0
    def __rtruediv__(self, o): return 0
    def __neg__(self): return 0


BLANK = _Blank()
_BLANK = BLANK


def _num(x):
    if isinstance(x, _Blank):
        return 0
    if isinstance(x, bool):
        return 1 if x else 0
    if isinstance(x, (int, float)):
        return x
    raise TypeError(f"not a number: {x!r}")


def _text_of(x):
    if isinstance(x, _Blank):
        return ""
    return x


def _cmp(op):
    def f(a, b):
        if isinstance(a, _Blank):
            a = "" if isinstance(b, str) else 0
        if isinstance(b, _Blank):
            b = "" if isinstance(a, str) else 0
        if op in ("=", "=="):
            if isinstance(a, str) or isinstance(b, str):
                return _text_of(a) == _text_of(b)
            return a == b
        if op in ("<>", "!="):
            return not _cmp("=")(a, b)
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        raise ValueError(op)
    return f


def _t(v):
    if isinstance(v, str):
        return v not in ("", "0")
    if v is None:
        return False
    return bool(v)


def _flat1(x):
    return x[0] if isinstance(x, (list, tuple)) and len(x) == 1 else x


def _flat(xs):
    out = []
    for x in xs:
        if isinstance(x, (list, tuple)):
            for y in x:
                if isinstance(y, (int, float)) and not isinstance(y, bool):
                    out.append(y)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            out.append(x)
    return out


def _median(vals):
    if not vals:
        return _ERR("div0")
    v = sorted(vals)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def _text(v, fmt):
    try:
        if isinstance(v, (int, float)):
            if "+" in str(fmt) or str(fmt).startswith("0.0%"):
                neg = v < 0
                s = f"{abs(v)*100:.1f}%" if "%" in str(fmt) else f"{abs(v):,.0f}"
                return ("-" if neg else "+") + s
            return f"{v:,.0f}" if abs(v) >= 1 else f"{v:g}"
        return str(v)
    except Exception:  # noqa: BLE001
        return str(v)


class Book:
    """对一个 openpyxl Workbook 做求值；可反复 set() 后 re-evaluate。"""

    def __init__(self, wb):
        self.wb = wb
        self._cache = {}
        self._busy = set()
        # 预编译：把每个公式翻译成 Python，引用改成常量占位名
        self._compiled = {}   # (sheet, addr) -> (pycode, [const_names])
        self._consts = {}     # name -> (sheet, addr) or ("RANGE", sheet, addr)

    # ---------------- 取值 ----------------
    def value(self, sheet, addr):
        key = (sheet, addr.upper())
        if key in self._cache:
            return self._cache[key]
        if key in self._busy:
            return _ERR("circular")
        self._busy.add(key)
        try:
            raw = self.wb[sheet][addr].value
            if isinstance(raw, str) and raw.startswith("="):
                v = self._calc(sheet, addr, raw[1:])
            else:
                v = raw
            self._cache[key] = v
            return v
        finally:
            self._busy.discard(key)

    def _calc(self, sheet, addr, body):
        name = f"__C{len(self._compiled)}"
        self._compiled[(sheet, addr)] = name
        refs = []

        def on_ref(s, a):
            key = f"__R{len(refs)}"
            refs.append((s, a))
            return key

        code = translate(body, sheet, on_ref)
        env = dict(FUNCS)
        for i, (s, a) in enumerate(refs):
            if ":" in a:
                c1, r1, c2, r2 = range_boundaries(a)
                vals = []
                ws = self.wb[s]
                for row in ws.iter_rows(min_row=r1, max_row=r2, min_col=c1, max_col=c2):
                    for cc in row:
                        vals.append(cc.value if not (isinstance(cc.value, str) and cc.value.startswith("=")) else 0)
                env[f"__R{i}"] = [v for v in vals if isinstance(v, (int, float))]
            else:
                v = self.value(s, a)
                # 与 Excel 语义对齐：空单元格参与算术时按 0，参与逻辑时按 FALSE。
                env[f"__R{i}"] = _BLANK if v is None else v
        try:
            r = eval(code, {"__builtins__": {}}, env)  # noqa: S307
            return r
        except ZeroDivisionError:
            return _ERR("div0")
        except Exception:  # noqa: BLE001
            return _ERR("formula")

    # ---------------- 修改输入 ----------------
    def set(self, sheet, addr, v):
        self.wb[sheet][addr].value = v
        self._cache.clear()


# 函数表放在最后定义，避免前向引用
FUNCS = {
    "IF": lambda c, a=None, b=None: a if _t(c) else b,
    "IFERROR": lambda v, alt=None: alt if isinstance(v, _ERR) else v,
    "AND": lambda *xs: all(_t(_flat1(x)) for x in xs),
    "OR": lambda *xs: any(_t(_flat1(x)) for x in xs),
    "NOT": lambda x: not _t(x),
    "ABS": lambda x: abs(x),
    "ROUND": lambda x, n=0: round(x, n),
    "MAX": lambda *xs: max(_flat(xs)),
    "MIN": lambda *xs: min(_flat(xs)),
    "SUM": lambda *xs: sum(_flat(xs)),
    "AVERAGE": lambda *xs: (sum(_flat(xs)) / len(_flat(xs))) if _flat(xs) else _ERR("div0"),
    "MEDIAN": lambda *xs: _median(_flat(xs)),
    "COUNT": lambda *xs: len([v for v in _flat(xs) if isinstance(v, (int, float)) and not isinstance(v, bool)]),
    "TEXT": lambda v, f=0: _text(v, f),
    "ISNUMBER": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "_CMP": lambda op, a, b: _cmp(op)(a, b),
    "TRUE": True,
    "FALSE": False,
}
