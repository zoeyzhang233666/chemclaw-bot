# -*- coding: utf-8 -*-
"""PDF 正文抽取（纯标准库，best-effort）。

用途：巨潮等站点的公告/环评报告是 PDF，需要把正文抽出来做关键词闸门与取证。
做法：解压 stream → 找 ToUnicode CMap（文件自带的中文映射表）→ 解 Tj/TJ 文本算子。

**局限（必须知道）**：
- 图片版（扫描件）PDF **抽不出文字**，会返回空串——遇到就如实报告"无文本层"，不要瞎猜内容。
- 复杂字体子集、竖排、加密 PDF 可能抽不全或乱序。
- 抽取结果建议**写到 .txt 再用 read/grep 查看**，直接 print 到某些终端会显示乱码。
"""
import re
import zlib


def _streams(data):
    """产出所有可解压的 stream 内容（bytes）。"""
    out = []
    for m in re.finditer(rb'stream\r?\n', data):
        start = m.end()
        end = data.find(b'endstream', start)
        if end < 0:
            continue
        raw = data[start:end]
        raw = raw.rstrip(b'\r\n')
        for attempt in (raw, raw[2:], raw[1:]):
            try:
                out.append(zlib.decompress(attempt))
                break
            except zlib.error:
                continue
    return out


def _parse_cmap(text):
    """解析 ToUnicode CMap，返回 {code:int -> unicode:str}。"""
    cmap = {}

    def _u(h):
        try:
            b = bytes.fromhex(h)
        except ValueError:
            return ''
        if len(b) % 2:
            b = b'\x00' + b
        return b.decode('utf-16-be', 'replace')

    for block in re.findall(r'beginbfchar(.*?)endbfchar', text, re.S):
        for src, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            cmap[int(src, 16)] = _u(dst)
    for block in re.findall(r'beginbfrange(.*?)endbfrange', text, re.S):
        for lo, hi, dst in re.findall(
                r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            try:
                a, b, base = int(lo, 16), int(hi, 16), int(dst, 16)
            except ValueError:
                continue
            if b - a > 65535:
                continue
            for i in range(b - a + 1):
                cmap[a + i] = chr(base + i) if base + i < 0x110000 else ''
    return cmap


def _decode_hex(h, cmap):
    out = []
    if len(h) % 4 == 0:
        for i in range(0, len(h), 4):
            code = int(h[i:i + 4], 16)
            out.append(cmap.get(code, ''))
    elif len(h) % 2 == 0:
        for i in range(0, len(h), 2):
            out.append(cmap.get(int(h[i:i + 2], 16), ''))
    return ''.join(out)


def _decode_literal(s, cmap):
    # 处理转义
    s = re.sub(r'\\([nrtbf()\\])', lambda m: {'n': '\n', 'r': '\r', 't': '\t',
                                              'b': '\b', 'f': '\f'}.get(m.group(1), m.group(1)), s)
    s = s.replace('\\\n', '')
    if cmap:
        codes = [ord(c) & 0xFF for c in s]
        return ''.join(cmap.get(c, chr(c)) for c in codes)
    return s


def _ops_text(content, cmap):
    """从内容流里抽取 Tj/TJ 文本。"""
    parts = []
    for m in re.finditer(r'(?s)(\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>)\s*(Tj|TJ|\'|")', content):
        tok, op = m.group(1), m.group(2)
        if tok.startswith('<'):
            parts.append(_decode_hex(re.sub(r'\s', '', tok[1:-1]), cmap))
        else:
            parts.append(_decode_literal(tok[1:-1], cmap))
        if op in ("'", '"'):
            parts.append('\n')
    for m in re.finditer(r'(?s)\[(.*?)\]\s*TJ', content):
        for t in re.finditer(r'(?s)(\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>)', m.group(1)):
            tok = t.group(1)
            if tok.startswith('<'):
                parts.append(_decode_hex(re.sub(r'\s', '', tok[1:-1]), cmap))
            else:
                parts.append(_decode_literal(tok[1:-1], cmap))
    return ''.join(parts)


def extract_text(pdf_bytes, max_streams=400):
    """抽取 PDF 文本。返回 str（可能为空 = 图片版/加密）。"""
    if not pdf_bytes:
        return ''
    streams = _streams(pdf_bytes)[:max_streams]
    cmap = {}
    for s in streams:
        try:
            t = s.decode('latin-1')
        except Exception:
            continue
        if 'beginbfchar' in t or 'beginbfrange' in t:
            cmap.update(_parse_cmap(t))
    chunks = []
    for s in streams:
        try:
            t = s.decode('latin-1')
        except Exception:
            continue
        if 'beginbfchar' in t or 'beginbfrange' in t:
            continue
        if 'Tj' in t or 'TJ' in t:
            chunks.append(_ops_text(t, cmap))
    text = ' '.join(chunks)
    text = re.sub(r'[ \t\u0000]+', ' ', text)
    text = re.sub(r'\s*\n\s*', '\n', text)
    return text.strip()


def extract_from_file(path):
    with open(path, 'rb') as f:
        return extract_text(f.read())


def main():
    import argparse
    import os
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser(description='PDF 正文抽取（best-effort）')
    ap.add_argument('pdf')
    ap.add_argument('--out', default=None, help='写到 .txt（推荐，避免终端乱码）')
    ap.add_argument('--grep', default=None, help='只打印命中的行')
    a = ap.parse_args()
    if a.pdf.lower().startswith(('http://', 'https://')):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from tools import http
        body = http.fetch(a.pdf, timeout=60)['body']
        text = extract_text(body)
    else:
        text = extract_from_file(a.pdf)
    if not text:
        print('（未抽出文本：可能是图片版/扫描件 PDF 或字体无 ToUnicode 映射）')
        return
    out = a.out or (os.path.splitext(a.pdf.split('/')[-1])[0] + '.txt'
                    if not a.pdf.lower().startswith('http') else 'pdf_text.txt')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(text)
    print('CHARS=%d -> %s' % (len(text), out))
    if a.grep:
        for line in text.split('\n'):
            if re.search(a.grep, line):
                print(line[:300])


if __name__ == '__main__':
    main()