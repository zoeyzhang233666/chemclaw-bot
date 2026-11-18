# -*- coding: utf-8 -*-
"""PDF 文本抽取（标准 library 版）：支持 ToUnicode CMap 解码，适配中文研报 PDF。

仅用于"引用别人的研究报告里已公开的图表数据"，不改变这些数据的出处。
"""
import re
import sys
import zlib


def _streams(data):
    for m in re.finditer(rb'stream\r?\n', data):
        start = m.end()
        end = data.find(b'endstream', start)
        if end < 0:
            continue
        raw = data[start:end]
        try:
            yield zlib.decompress(raw)
        except Exception:
            continue


def _cmap(dec):
    """解析 ToUnicode CMap，返回 code(2 bytes) -> unicode str。"""
    cmap = {}
    for blk in re.finditer(rb'beginbfchar(.*?)endbfchar', dec, re.S):
        for a, b in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk.group(1)):
            try:
                cmap[bytes.fromhex(a.decode())] = bytes.fromhex(b.decode()).decode('utf-16-be', 'ignore')
            except Exception:
                pass
    for blk in re.finditer(rb'beginbfrange(.*?)endbfrange', dec, re.S):
        for a, b, c in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk.group(1)):
            try:
                lo = int(a, 16)
                hi = int(b, 16)
                base = bytes.fromhex(c.decode()).decode('utf-16-be', 'ignore')
                for i, code in enumerate(range(lo, min(hi, lo + 512) + 1)):
                    ch = chr(ord(base[0]) + i) if base else ''
                    cmap[code.to_bytes(2, 'big')] = ch
            except Exception:
                pass
    return cmap


def _text_ops(dec, cmap):
    out = []
    for m in re.finditer(rb'\((?:[^()\\]|\\.)*\)\s*Tj|\[(?:[^\]]*)\]\s*TJ|(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+Td', dec):
        tok = m.group(0)
        if b'Td' in tok:
            out.append('\n' if m.group(1) and m.group(2) and abs(float(m.group(2))) > 0.01 else ' ')
            continue
        if b'TJ' in tok:
            parts = re.findall(rb'\((?:[^()\\]|\\.)*\)|<[0-9A-Fa-f\s]+>', tok)
        else:
            parts = [tok.split(b')')[0] + b')']
        s = ''
        for p in parts:
            if p.startswith(b'<'):
                hexs = re.sub(rb'\s', b'', p[1:-1])
                bs = bytes.fromhex(hexs.decode()) if hexs else b''
                if cmap:
                    for i in range(0, len(bs) - 1, 2):
                        s += cmap.get(bs[i:i + 2], '')
                else:
                    s += bs.decode('utf-16-be', 'ignore')
            else:
                lit = p[1:-1]
                lit = re.sub(rb'\\([()\\])', rb'\1', lit)
                if cmap:
                    for i in range(0, len(lit) - 1, 2):
                        s += cmap.get(lit[i:i + 2], '')
                else:
                    s += lit.decode('latin-1', 'ignore')
        out.append(s)
    return ''.join(out)


def extract(path):
    data = open(path, 'rb').read()
    decs = list(_streams(data))
    cmap = {}
    for d in decs:
        if b'beginbfchar' in d or b'beginbfrange' in d:
            cmap.update(_cmap(d))
    chunks = []
    for d in decs:
        if b'TJ' in d or b'Tj' in d:
            chunks.append(_text_ops(d, cmap))
    return '\n'.join(chunks)


if __name__ == '__main__':
    t = extract(sys.argv[1])
    print(t)
