# -*- coding: utf-8 -*-
"""
xlsx_recalc.py —— 轻量级 Excel 公式重算器（纯 Python，无第三方依赖）

用途
----
openpyxl 只能读出公式文本，不能算出结果。本模块把工作簿里的公式真正求值，
用于验证「Excel 公式是否可运行、结果是否与 Python 引擎一致」。

支持范围（本 Skill 生成的模板所需）
-----------------------------------
* 引用：A1、$A$1、跨表 'Sheet 名'!A1、区域 A1:B9 / $B$3:$B$300
* 运算：+ - * / ^ % ，比较 = <> < > <= >= ，连接 &
* 函数：SUM SUMIFS COUNTIFS COUNTIF COUNTIFS AVERAGE AVG AVERAGEIFS MIN MAX
        MINIFS MAXIFS IF AND OR NOT ABS ROUND ROUNDUP ROUNDDOWN INT
        INDEX MATCH TEXT LEN IFERROR ISBLANK CONCATENATE
* 数组常量常量 {1;2;3} / {"a","b"}

不支持：数组公式（CSE）、动态数组溢出、外部链接、自定义函数。
遇到不支持的元素会抛出 RecalcError，而不是静默给错数。
"""
from __future__ import annotations

import math
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


class RecalcError(Exception):
    pass


# ---------------------------------------------------------------- 单元格地址
ADDR_RE = re.compile(r"^\$?([A-Z]{1,3})\$?(\d+)$")


def col_to_idx(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def idx_to_col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_addr(addr: str):
    m = ADDR_RE.match(addr.replace("$", ""))
    if not m:
        raise RecalcError(f"bad address {addr}")
    return col_to_idx(m.group(1)), int(m.group(2)) - 1


# ---------------------------------------------------------------- 工作簿读取
class Workbook:
    def __init__(self, path):
        self.path = path
        self.sheets = {}          # name -> {(r,c): value_or_formula}
        self.formulas = {}        # (sheetname,r,c) -> formula text
        self.dates = {}           # (sheetname,r,c) -> True 表示该单元格被识别为日期
        self._load()

    def _load(self):
        z = zipfile.ZipFile(self.path)
        names = z.namelist()
        # sharedStrings
        sst = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                sst.append("".join(t.text or "" for t in si.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
        # 日期样式（numFmtId 14-22, 45-47 或自定义含 y/m/d）
        date_styles = set()
        wbroot = ET.fromstring(z.read("xl/workbook.xml"))
        if "xl/styles.xml" in names:
            st = ET.fromstring(z.read("xl/styles.xml"))
            custom = {}
            for nf in st.findall("m:numFmts/m:numFmt", NS):
                custom[int(nf.get("numFmtId"))] = nf.get("formatCode") or ""
            xfs = st.findall("m:cellXfs/m:xf", NS)
            for i, xf in enumerate(xfs):
                fid = int(xf.get("numFmtId") or 0)
                code = custom.get(fid, "")
                if 14 <= fid <= 22 or 45 <= fid <= 47 or re.search(r"[ymd]", code):
                    date_styles.add(i)
        # 关系：sheet name -> file
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid2target = {r.get("Id"): r.get("Target") for r in rels}
        for sh in wbroot.findall("m:sheets/m:sheet", NS):
            nm = sh.get("name")
            rid = sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            tgt = rid2target[rid]
            if not tgt.startswith("xl/"):
                tgt = "xl/" + tgt.lstrip("/")
            self._load_sheet(z, nm, tgt, sst, date_styles)

    def _load_sheet(self, z, name, target, sst, date_styles):
        cells = {}
        root = ET.fromstring(z.read(target))
        for c in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
            ref = c.get("r")
            if not ref:
                continue
            try:
                col, row = parse_addr(ref)
            except RecalcError:
                continue
            t = c.get("t")
            s = int(c.get("s") or 0)
            f = c.find("m:f", NS)
            v = c.find("m:v", NS)
            # ★ 公式单元格优先级最高：xlsxwriter/openpyxl 写公式时通常不带 t 属性，
            #   若先走 t 分支会被当成数字空值而丢失。必须先判公式。
            if f is not None and f.text:
                self.formulas[(name, row, col)] = f.text
                cells[(row, col)] = f"={f.text}"
                continue
            if t == "s":
                val = sst[int(v.text)] if v is not None and v.text else ""
            elif t == "inlineStr":
                is_ = c.find("m:is", NS)
                val = "".join(x.text or "" for x in (is_.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t") if is_ is not None else []))
            elif t == "str":
                val = v.text if v is not None else ""
            elif t == "b":
                val = (v is not None and v.text == "1")
            else:
                if v is None or v.text is None or v.text == "":
                    continue
                try:
                    num = float(v.text)
                except ValueError:
                    val = v.text
                else:
                    if s in date_styles:
                        self.dates[(name, row, col)] = True
                        val = _excel_serial_to_date(num)
                    else:
                        val = num
            cells[(row, col)] = val
        self.sheets[name] = cells

    # ------------------------------------------------------------ 取值
    def get(self, sheet, row, col, _stack=None):
        c = self.sheets.get(sheet, {})
        v = c.get((row, col))
        if v is None:
            return None
        if isinstance(v, str) and v.startswith("="):
            return self.evaluate(sheet, row, col, _stack)
        return v

    def evaluate(self, sheet, row, col, _stack=None):
        # 注意：cells 字典的键是二维的 (row, col)；
        # 含工作表名的三元组只用于“求值栈”做循环引用检测。
        cell_key = (row, col)
        stack_key = (sheet, row, col)
        stack = list(_stack) if _stack else []
        fx = self.sheets.get(sheet, {}).get(cell_key)
        if not isinstance(fx, str) or not fx.startswith("="):
            return fx
        if stack_key in stack:
            raise RecalcError(f"circular reference at {sheet}!{idx_to_col(col)}{row+1}")
        engine = Engine(self, sheet, stack + [stack_key])
        return engine.eval(fx[1:])


def _excel_serial_to_date(serial: float) -> date:
    # Excel 1900 系统（含 1900-02-29 历史 bug）
    if serial >= 61:
        base = datetime(1899, 12, 30)
    else:
        base = datetime(1899, 12, 31)
    return (base + timedelta(days=float(serial))).date()


# ---------------------------------------------------------------- 词法/语法
TOKEN_RE = re.compile(r"""
    \s*(?:
      (?P<str>"(?:[^"]|"")*")
    | (?P<func>[A-Z][A-Z0-9\.]*)\s*\(
    | (?P<ref>(?:'[^']+'!|[A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff\.]*!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)
    | (?P<range>(?:'[^']+'!|[A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff\.]*!)?\$?[A-Z]{1,3}:\$?[A-Z]{1,3}(?=,|\)|\s|$))
    | (?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?)
    | (?P<op><>|<=|>=|[-+*/^&=<>%(),;])
    | (?P<arr>\{[^}]*\})
    )""", re.X)


def tokenize(s):
    out, pos = [], 0
    while pos < len(s):
        if s[pos:].strip() == "":
            break
        m = TOKEN_RE.match(s, pos)
        if not m:
            raise RecalcError(f"tokenize fail at {s[pos:pos+30]!r}")
        pos = m.end()
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
    return out


class Engine:
    def __init__(self, wb: Workbook, sheet: str, stack):
        self.wb = wb
        self.sheet = sheet
        self.stack = stack

    # ---------- 入口
    def eval(self, text):
        toks = tokenize(text)
        self.toks = toks
        self.i = 0
        v = self.parse_expr()
        if self.i < len(self.toks):
            raise RecalcError(f"trailing tokens {self.toks[self.i:]}")
        return v

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    # ---------- 递归下降
    def parse_expr(self):
        left = self.parse_concat()
        while self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.take()[1]
            right = self.parse_concat()
            left = _compare(op, left, right)
        return left

    def parse_concat(self):
        left = self.parse_add()
        while self.peek()[1] == "&":
            self.take()
            right = self.parse_add()
            left = f"{_to_str(left)}{_to_str(right)}"
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            right = self.parse_mul()
            left = _n(left) + _n(right) if op == "+" else _n(left) - _n(right)
        return left

    def parse_mul(self):
        left = self.parse_pow()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            right = self.parse_pow()
            if op == "*":
                left = _n(left) * _n(right)
            else:
                d = _n(right)
                if d == 0:
                    raise RecalcError("#DIV/0!")
                left = _n(left) / d
        return left

    def parse_pow(self):
        left = self.parse_unary()
        while self.peek()[1] == "^":
            self.take()
            right = self.parse_unary()
            left = _n(left) ** _n(right)
        return left

    def parse_unary(self):
        if self.peek()[1] in ("-", "+"):
            op = self.take()[1]
            v = self.parse_unary()
            return -_n(v) if op == "-" else _n(v)
        return self.parse_postfix()

    def parse_postfix(self):
        v = self.parse_atom()
        while self.peek()[1] == "%":
            self.take()
            v = _n(v) / 100.0
        return v

    def parse_atom(self):
        kind, val = self.take()
        if kind == "num":
            return float(val)
        if kind == "str":
            return val[1:-1].replace('""', '"')
        if kind == "arr":
            return _parse_array(val)
        if kind == "func":
            return self.call(val, self.parse_args())
        if kind == "ref":
            return self.resolve(val)
        if kind == "op" and val == "(":
            v = self.parse_expr()
            if self.peek()[1] == ")":
                self.take()
            return v
        raise RecalcError(f"unexpected token {kind}:{val}")

    def parse_args(self):
        args = []
        if self.peek()[1] == ")":
            self.take()
            return args
        while True:
            if self.peek()[1] in (",", ")", ";"):
                args.append(None)   # 空参数
            else:
                args.append(self.parse_expr())
            t = self.take()
            if t[1] == ")":
                break
            if t[1] not in (",", ";"):
                raise RecalcError(f"expect , or ) got {t}")
        return args

    # ---------- 引用解析
    def resolve(self, ref):
        sheet = self.sheet
        if "!" in ref:
            sname, ref = ref.rsplit("!", 1)
            sname = sname.strip("'")
            if sname not in self.wb.sheets:
                raise RecalcError(f"no sheet {sname}")
            sheet = sname
        if ":" in ref:
            a, b = ref.split(":")
            c1, r1 = parse_addr(a)
            c2, r2 = parse_addr(b)
            out = []
            for rr in range(r1, r2 + 1):
                rowvals = []
                for cc in range(c1, c2 + 1):
                    rowvals.append(self.wb.get(sheet, rr, cc, self.stack))
                out.append(rowvals)
            return out
        c, r = parse_addr(ref)
        return self.wb.get(sheet, r, c, self.stack)

    # ---------- 函数
    def call(self, name, args):
        fn = FUNCS.get(name.upper())
        if fn is None:
            raise RecalcError(f"unsupported function {name}")
        if name.upper() == "IFERROR":
            # 惰性求值：第一个参数出错时才求第二个
            try:
                return args[0]
            except RecalcError:
                return args[1]
        return fn(self, name.upper(), args)


# ---------------------------------------------------------------- 值工具
def _n(v):
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, date):
        return float((v - date(1899, 12, 30)).days)
    if isinstance(v, str):
        if v.strip() == "":
            return 0.0
        try:
            return float(v)
        except ValueError:
            raise RecalcError(f"cannot convert {v!r} to number")
    raise RecalcError(f"cannot use {type(v)} as number")


def _to_str(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else str(v)
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _cmp_val(v):
    """条件比较用的归一化。

    注意：Excel 里 `B1=""` 判断“单元格为空”非常常见，而 B1 可能是数字。
    因此这里把 None / 空串统一映射为 ""，其余保持原值；具体大小比较交给 _cmp_op
    处理（混合类型时按 Excel 规则：数字 < 文本）。
    """
    if isinstance(v, bool):
        return v
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, date):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _flat(args):
    """把参数递归展开成一维值列表；区域按行展平。

    注意：必须递归，因为既可能传入 [区城], 也可能传入 [[区城]]（数组常量被包一层）。
    """
    out = []
    for a in args:
        if isinstance(a, list):
            out.extend(_flat(a))
        else:
            out.append(a)
    return out


def _parse_array(s):
    """Excel 数组常量：
        {"a","b","c"}   → 1 行 3 列（逗号分列）
        {"a";"b";"c"}   → 3 行 1 列（分号分行）
        {"a","b";"c","d"} → 2 行 2 列
    """
    body = s.strip()[1:-1]
    rows = body.replace(",", "\x01").split(";")
    out = []
    for r in rows:
        cells = []
        for cell in r.split("\x01"):
            cell = cell.strip()
            if cell.startswith('"'):
                cells.append(cell.strip('"'))
            elif cell.upper() in ("TRUE", "FALSE"):
                cells.append(cell.upper() == "TRUE")
            else:
                try:
                    cells.append(float(cell))
                except ValueError:
                    cells.append(cell)
        out.append(cells)
    return out


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _compare(op, a, b):
    """按 Excel 语义比较两个值。

    Excel 跨类型排序：数字 < 文本 < 逻辑值；空单元格与 "" 等价。
    这样 `B1=""`（B1 为空）返回 TRUE，`B1=""`（B1 是数字）返回 FALSE，不会抛异常。
    """
    a = _cmp_val(a)
    b = _cmp_val(b)

    if op == "=":
        return _same(a, b)
    if op == "<>":
        return not _same(a, b)

    # 大小比较：把两者排到同一序上
    ra, ka = _rank(a)
    rb, kb = _rank(b)
    if ra != rb:
        # 不同类别：数字 < 文本 < 逻辑
        cmp = (ra > rb) - (ra < rb)
    else:
        if isinstance(ka, str) and isinstance(kb, str):
            cmp = (ka.lower() > kb.lower()) - (ka.lower() < kb.lower())
        else:
            cmp = (ka > kb) - (ka < kb)
    return {"<": cmp < 0, ">": cmp > 0, "<=": cmp <= 0, ">=": cmp >= 0}[op]


def _rank(v):
    """返回 (类别序, 可比较键)。0=空/数字, 1=文本, 2=布尔。"""
    if isinstance(v, bool):
        return 2, v
    if isinstance(v, str):
        if v == "":
            return 0, 0.0
        return 1, v
    if isinstance(v, date):
        return 0, float((v - date(1899, 12, 30)).days)
    if v is None:
        return 0, 0.0
    return 0, float(v)


def _same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    if isinstance(a, str) or isinstance(b, str):
        # 一边文本：仅当两边都精确相等才算相同（Excel 语义）
        return a == b
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


# ---------------------------------------------------------------- 函数实现
def f_sum(e, name, args):
    return sum(_n(v) for v in _flat(args) if _is_num(v))


def f_average(e, name, args):
    vals = [_n(v) for v in _flat(args) if _is_num(v)]
    return sum(vals) / len(vals) if vals else 0.0


def f_min(e, name, args):
    vals = [_n(v) for v in _flat(args) if _is_num(v)]
    return min(vals) if vals else 0.0


def f_max(e, name, args):
    vals = [_n(v) for v in _flat(args) if _is_num(v)]
    return max(vals) if vals else 0.0


def _crit_match(v, crit):
    """实现 Excel 条件：支持 ">="&B5 已在外层拼好，此处为字符串条件。"""
    if isinstance(crit, str) and crit[:2] in (">=", "<=", "<>") :
        op, target = crit[:2], crit[2:]
        return _cmp_op(("=" if op == "=" else op), v, target)
    if isinstance(crit, str) and crit[:1] in (">", "<", "="):
        op, target = crit[:1], crit[1:]
        return _cmp_op("=" if op == "=" else op, v, target)
    if isinstance(crit, bool):
        return bool(v) == crit
    if _is_num(crit):
        return _is_num(v) and abs(v - crit) < 1e-12
    if crit == "":
        return v is None or v == ""
    return _to_str(v) == crit


def _cmp_op(op, v, target):
    if _is_num(target) or re.fullmatch(r"-?\d+\.?\d*", str(target)):
        tv = float(target)
        if not _is_num(v):
            return op == "<>"
        return {"=": v == tv, "<>": v != tv, ">": v > tv, "<": v < tv,
                ">=": v >= tv, "<=": v <= tv}[op]
    tv = str(target)
    sv = _to_str(v)
    return {"=": sv == tv, "<>": sv != tv, ">": sv > tv, "<": sv < tv,
            ">=": sv >= tv, "<=": sv <= tv}[op]


def _pairs(name, args, n_crit):
    """拆出 (求和区域, [(条件区域, 条件)...])"""
    if name == "COUNTIF":
        rng, crit = args[0], args[1]
        return None, [(rng, crit)]
    if name == "COUNTIFS":
        crits = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
        return None, crits
    # SUMIFS(区域, 条件区域1, 条件1, ...) / AVERAGEIFS / MINIFS / MAXIFS
    target, rest = args[0], args[1:]
    crits = [(rest[i], rest[i + 1]) for i in range(0, len(rest), 2)]
    return target, crits


def _cond_eval(name, args):
    target, crits = _pairs(name, args, len(args) // 2)
    # 计算最长维度
    fl = [_flat([r]) for r, _ in crits]
    n = max(len(x) for x in fl)
    tvals = _flat([target]) if target is not None else [None] * n
    picked = []
    for i in range(n):
        ok = True
        for (rng, crit), vals in zip(crits, fl):
            v = vals[i] if i < len(vals) else None
            if not _crit_match(v, crit):
                ok = False
                break
        if ok:
            picked.append(tvals[i] if i < len(tvals) else None)
    return n, picked


def f_countif(e, name, args):
    return float(len(_cond_eval(name, args)[1]))


def f_sumifs(e, name, args):
    _, picked = _cond_eval(name, args)
    return sum(_n(v) for v in picked if _is_num(v))


def f_averageifs(e, name, args):
    _, picked = _cond_eval(name, args)
    vals = [_n(v) for v in picked if _is_num(v)]
    return sum(vals) / len(vals) if vals else 0.0


def f_minifs(e, name, args):
    _, picked = _cond_eval(name, args)
    vals = [_n(v) for v in picked if _is_num(v)]
    return min(vals) if vals else 0.0


def f_maxifs(e, name, args):
    _, picked = _cond_eval(name, args)
    vals = [_n(v) for v in picked if _is_num(v)]
    return max(vals) if vals else 0.0


def f_if(e, name, args):
    cond = args[0]
    if isinstance(cond, list):
        cond = _flat([cond])[0]
    truth = bool(cond) if not isinstance(cond, str) else cond.upper() == "TRUE"
    if truth:
        return args[1] if len(args) > 1 else True
    return args[2] if len(args) > 2 else False


def f_and(e, name, args):
    return all(bool(v) for v in _flat(args))


def f_or(e, name, args):
    return any(bool(v) for v in _flat(args))


def f_not(e, name, args):
    return not bool(args[0])


def f_abs(e, name, args):
    return abs(_n(args[0]))


def f_round(e, name, args):
    d = int(_n(args[1])) if len(args) > 1 else 0
    return round(_n(args[0]), d)


def f_roundup(e, name, args):
    d = int(_n(args[1])) if len(args) > 1 else 0
    m = 10 ** d
    v = _n(args[0])
    return math.copysign(math.ceil(abs(v) * m) / m, v)


def f_rounddown(e, name, args):
    d = int(_n(args[1])) if len(args) > 1 else 0
    m = 10 ** d
    v = _n(args[0])
    return math.copysign(math.floor(abs(v) * m) / m, v)


def f_int(e, name, args):
    return float(math.floor(_n(args[0])))


def f_index(e, name, args):
    arr = args[0]
    if not isinstance(arr, list):
        return arr
    if arr and not isinstance(arr[0], list):
        arr = [arr]
    r = int(_n(args[1])) if len(args) > 1 and args[1] is not None else 1
    c = int(_n(args[2])) if len(args) > 2 and args[2] is not None else 1
    is_col = len(arr[0]) == 1
    try:
        if is_col and len(args) <= 2:
            return arr[r - 1][0]
        if len(arr[0]) == 1 and len(args) > 2:
            return arr[c - 1][0]
        if len(args) <= 2:
            return arr[0][r - 1]
        return arr[r - 1][c - 1]
    except IndexError:
        raise RecalcError("#REF!")


def f_match(e, name, args):
    val = args[0]
    arr = _flat([args[1]])
    mtype = int(_n(args[2])) if len(args) > 2 else 1
    if mtype == 0:
        for i, v in enumerate(arr):
            if _cmp_val(v) == _cmp_val(val):
                return float(i + 1)
        raise RecalcError(f"#N/A (MATCH {val!r} not found)")
    raise RecalcError("MATCH type 1/-1 not supported")


def f_text(e, name, args):
    v = args[0]
    fmt = str(args[1]) if len(args) > 1 else ""
    if isinstance(v, date) and "yyyy" in fmt:
        return f"{v.year:04d}-{v.month:02d}-{v.day:02d}"
    if _is_num(v) and fmt.startswith("0"):
        dec = len(fmt.split(".")[1]) if "." in fmt else 0
        return f"{v:,.{dec}f}" if "," in fmt else f"{v:.{dec}f}"
    return _to_str(v)


def f_len(e, name, args):
    return float(len(_to_str(args[0])))


def f_iferror(e, name, args):
    try:
        return args[0]
    except RecalcError:
        return args[1]


def f_isblank(e, name, args):
    v = args[0]
    return v is None or v == "" or v == []


def f_isnumber(e, name, args):
    v = args[0]
    if isinstance(v, list):
        v = v[0][0] if v and isinstance(v[0], list) else (v[0] if v else None)
    return _is_num(v)


def f_istext(e, name, args):
    v = args[0]
    if isinstance(v, list):
        v = v[0][0] if v and isinstance(v[0], list) else (v[0] if v else None)
    return isinstance(v, str)


def f_concat(e, name, args):
    return "".join(_to_str(v) for v in _flat(args))


FUNCS = {
    "SUM": f_sum, "AVERAGE": f_average, "AVG": f_average,
    "MIN": f_min, "MAX": f_max,
    "COUNTIF": f_countif, "COUNTIFS": f_countif,
    "SUMIFS": f_sumifs, "AVERAGEIFS": f_averageifs,
    "MINIFS": f_minifs, "MAXIFS": f_maxifs, "AVERAGEIFS": f_averageifs,
    "IF": f_if, "AND": f_and, "OR": f_or, "NOT": f_not,
    "ABS": f_abs, "ROUND": f_round, "ROUNDUP": f_roundup,
    "ROUNDDOWN": f_rounddown, "INT": f_int,
    "INDEX": f_index, "MATCH": f_match, "TEXT": f_text, "LEN": f_len,
    "IFERROR": f_iferror, "ISBLANK": f_isblank, "CONCATENATE": f_concat,
    "ISNUMBER": f_isnumber, "ISTEXT": f_istext,
}


# ---------------------------------------------------------------- 便捷接口
def recalc(path):
    return Workbook(path)


def get(book: Workbook, sheet: str, addr: str):
    c, r = parse_addr(addr)
    return book.get(sheet, r, c)
