# -*- coding: utf-8 -*-
"""零依赖 PDF 文本 + 页码定位器（subset 字体 ToUnicode CMap / Identity-H / WinAnsi 简单字体）。

用法：
    python pdf_text.py <file.pdf>                       # 打印每页文本（自上而下）
    from pdf_text import page_lines, locate
    locate(path, "612.00") -> [(page, y, line_text)]     # page 从 1 开始；y 为 PDF 用户坐标

设计说明：只解析内容流中的文本算子（BT/ET、Tf、Tm、Td/TD、T*、Tj/TJ），
不实现完整 PDF 语义；对由 word/Excel 转出的 PDF（本工具测试集）以及常见扫描件 OCR 后的
文字层均可定位到页 + 纵坐标。扫描件无文字层时返回空列表，调用方必须标记为【无法判断】。
"""
import re, sys

try:
    import zlib
except ImportError:  # pragma: no cover
    zlib = None

_INNER = re.compile(r"<([0-9A-Fa-f]*)>|\(((?:\\.|[^\\()])*)\)")
_ESC = {"n": "\n", "r": "", "t": "\t", "b": "", "f": ""}
_OPERATOR = re.compile(r"[A-Za-z*'\"]+")
_NUMBER = re.compile(r"-?\d*\.?\d+")


def _objects(data):
    return {int(m.group(1)): m.group(3) for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", data, re.S)}


def _decode_stream(body):
    if body is None:
        return None
    sm = re.search(rb"stream\r?\n", body)
    if not sm:
        return None
    raw = body[sm.end():body.rfind(b"endstream")]
    if b"FlateDecode" in body[:sm.start()]:
        if zlib is None:
            return None
        try:
            return zlib.decompress(raw)
        except Exception:
            try:
                return zlib.decompressobj().decompress(raw)
            except Exception:
                return None
    return raw


def _parse_tounicode(cmap):
    mapping = {}
    txt = cmap.decode("latin-1", "replace")
    for blk in re.findall(r"beginbfchar(.*?)endbfchar", txt, re.S):
        for a, b in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            mapping[int(a, 16)] = bytes.fromhex(b).decode("utf-16-be", "replace")
    for blk in re.findall(r"beginbfrange(.*?)endbfrange", txt, re.S):
        for a, b, c in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            lo, hi, dst = int(a, 16), int(b, 16), int(c, 16)
            for k in range(lo, hi + 1):
                mapping[k] = chr(dst + (k - lo))
    return mapping


def _fonts(objs):
    fonts = {}
    for body in list(objs.values()):
        for fm in re.finditer(rb"/([A-Za-z]\w*)\s+(\d+)\s+0\s+R", body):
            name, fnum = fm.group(1).decode(), int(fm.group(2))
            fb = objs.get(fnum)
            if fb is None:
                continue
            cmap = None
            tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", fb)
            if tu:
                st = _decode_stream(objs.get(int(tu.group(1))))
                if st:
                    cmap = _parse_tounicode(st)
            two = b"Identity-" in fb or (cmap is not None and max(cmap, default=0) > 0xFF)
            fonts.setdefault(name, (cmap, bool(two)))
    return fonts


def _decode_arr(arr, cmap, two):
    out = []
    for tok in _INNER.finditer(arr or ""):
        try:
            if tok.group(1) is not None:
                h, step = tok.group(1), 4 if two else 2
                for i in range(0, len(h) - step + 1, step):
                    code = int(h[i:i + step], 16)
                    out.append(cmap.get(code, "") if cmap else chr(code))
            else:
                lit = re.sub(r"\\([nrtbf()\\])", lambda m: _ESC.get(m.group(1), m.group(1)), tok.group(2))
                if cmap and not two:
                    out.append("".join(cmap.get(ord(c), c) for c in lit))
                else:
                    out.append(lit)
        except Exception:
            pass
    return "".join(out)


def _tokenize(txt):
    """(name, value) 序列：op=算子, num=数值, str=字符串/十六进制, arr=TJ 数组原文。"""
    n, i = len(txt), 0
    while i < n:
        c = txt[i]
        if c in " \t\r\n\f\x00":
            i += 1
        elif c == "%":
            j = txt.find("\n", i)
            i = n if j < 0 else j + 1
        elif c == "(":
            depth, j = 1, i + 1
            while j < n and depth:
                if txt[j] == "\\":
                    j += 2
                    continue
                if txt[j] == "(":
                    depth += 1
                elif txt[j] == ")":
                    depth -= 1
                j += 1
            yield "str", txt[i:j]
            i = j
        elif c == "<":
            j = txt.find(">", i)
            j = n if j < 0 else j + 1
            if i + 1 < n and txt[i + 1] == "<":
                i = j
                continue
            yield "str", txt[i:j]
            i = j
        elif c == "/":
            j = i + 1
            while j < n and txt[j] not in " \t\r\n\f/[]()<>":
                j += 1
            yield "name", txt[i + 1:j]
            i = j
        elif c == "[":
            depth, j = 1, i + 1
            while j < n and depth:
                if txt[j] == "[":
                    depth += 1
                elif txt[j] == "]":
                    depth -= 1
                j += 1
            yield "arr", txt[i + 1:j - 1]
            i = j
        else:
            m = _OPERATOR.match(txt, i)
            if m:
                yield "op", m.group(0)
                i = m.end()
                continue
            m = _NUMBER.match(txt, i)
            if m:
                yield "num", m.group(0)
                i = m.end()
                continue
            i += 1


def page_items(path):
    """返回 [[(y, x, text)]]，按内容对象顺序（即页序）。"""
    data = open(path, "rb").read()
    objs = _objects(data)
    fonts = _fonts(objs)
    result = []
    for num in sorted(objs):
        st = _decode_stream(objs[num])
        if not st or b"BT" not in st:
            continue
        txt = st.decode("latin-1")
        items = []
        cur = {"x": 0.0, "y": 0.0, "lead": 14.0, "font": None}
        operands = []
        for kind, val in _tokenize(txt):
            if kind != "op":
                operands.append((kind, val))
                continue
            if val == "BT":
                cur["x"] = cur["y"] = 0.0      # 文本矩阵在 BT 时复位为单位矩阵（Td 相对文本行矩阵原点）
            elif val == "ET":
                pass
            elif val == "Tf":
                names = [v for k, v in operands if k == "name"]
                if names:
                    cur["font"] = names[-1]
            elif val == "Tm":
                nums = [float(v) for k, v in operands if k == "num"]
                if len(nums) >= 6:
                    cur["x"], cur["y"] = nums[4], nums[5]
            elif val in ("Td", "TD"):
                nums = [float(v) for k, v in operands if k == "num"]
                if len(nums) >= 2:
                    cur["x"] += nums[-2]
                    cur["y"] += nums[-1]
                    if val == "TD":
                        cur["lead"] = -nums[-1]
            elif val in ("T*", "'", '"'):
                cur["x"] = 50.0
                cur["y"] -= cur["lead"]
            elif val in ("Tj", "TJ", "'", '"'):
                cmap, two = fonts.get(cur["font"], (None, True))
                text = ""
                for k, v in operands:
                    if k == "str" or k == "arr":
                        text += _decode_arr(v, cmap, two)
                if text.strip():
                    items.append((cur["y"], cur["x"], text))
            operands = []
        if items:
            result.append(items)
    return result


def page_lines(path):
    res = []
    for items in page_items(path):
        rows = []
        for y0, x0, t in sorted(items, key=lambda it: -it[0]):
            if rows and abs(rows[-1][0] - y0) <= 3:
                rows[-1][1].append((x0, t))
            else:
                rows.append([y0, [(x0, t)]])
        res.append([(y0, "".join(t for _, t in sorted(v))) for y0, v in rows])
    return list(enumerate(res, 1))


def locate(path, needle):
    n = re.sub(r"\s+", "", needle).lower()
    hits = []
    for page_no, lines in page_lines(path):
        for y, text in lines:
            if n in re.sub(r"\s+", "", text).lower():
                hits.append((page_no, y, text.strip()))
    return hits


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for page_no, lines in page_lines(sys.argv[1]):
        print("===== PAGE %d =====" % page_no)
        for y, t in lines:
            print("%7.0f | %s" % (y, t))
