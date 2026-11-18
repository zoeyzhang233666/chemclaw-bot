#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PDF 正文抽取（纯标准库，无需第三方库）。

为什么需要它：cninfo 的全文检索只返回约 55 字的正文片段，够判断「是不是这件事」，
但**吨数、金额、合同期、采购均价这些硬数字必须下 PDF 抽正文**才能拿到。
本脚本用 zlib 解流 + ToUnicode CMap 还原中文，已在 cninfo 公告 PDF 上实测可用。

**控制台中文会乱码**，所以本脚本一律把结果写成 UTF-8 文件：
    <out>.txt        全文
    <out>.hits.txt   关键词命中上下文（用来快速定位）
然后再用读文件的方式去看，不要指望 stdout。

用法:
    python fetch_pdftext.py <URL 或本地PDF路径> [--pat 纯碱] [--window 260] \
        [--out leads_raw/_pdftext_sample] [--maxhits 20]
"""
from __future__ import annotations

import os
import re
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radarlib as R  # noqa: E402


def _streams(data: bytes):
    """产出所有解压后的流内容（FlateDecode 成功才返回）。"""
    out = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        for cand in (raw, raw.rstrip(b"\r\n")):
            try:
                out.append(zlib.decompress(cand))
                break
            except Exception:
                continue
    return out


def _parse_cmap(streams):
    """把所有 ToUnicode CMap 合并成一张 code -> 字符 的表。"""
    cmap = {}
    for s in streams:
        if b"beginbfchar" not in s and b"beginbfrange" not in s:
            continue
        txt = s.decode("latin-1", "replace")
        for blk in re.findall(r"beginbfchar(.*?)endbfchar", txt, re.S):
            for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
                try:
                    cmap[int(src, 16)] = bytes.fromhex(dst).decode("utf-16-be", "ignore")
                except Exception:
                    pass
        for blk in re.findall(r"beginbfrange(.*?)endbfrange", txt, re.S):
            for lo, hi, dst in re.findall(
                    r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
                try:
                    a, b = int(lo, 16), int(hi, 16)
                    base = int(dst, 16)
                    for i in range(min(b - a + 1, 512)):
                        cmap[a + i] = chr(base + i)
                except Exception:
                    pass
    return cmap


def _decode_hex(h):
    try:
        return bytes.fromhex(h)
    except Exception:
        return b""


def _content_text(streams, cmap):
    """从内容流里抽文字：先抓 Tj / TJ 的字符串，再按 CMap（或 gbk）解码。"""
    chunks = []
    for s in streams:
        if b"Tj" not in s and b"TJ" not in s:
            continue
        txt = s.decode("latin-1", "replace")
        for m in re.finditer(r"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>", txt):
            tok = m.group(0)
            if tok.startswith("<"):
                raw = _decode_hex(re.sub(r"\s+", "", tok[1:-1]))
            else:
                body = tok[1:-1]
                body = re.sub(r"\\([nrtbf()\\])",
                              lambda x: {"n": "\n", "r": "\r", "t": "\t", "b": "", "f": ""}
                              .get(x.group(1), x.group(1)), body)
                raw = body.encode("latin-1", "replace")
            if not raw:
                continue
            if cmap:
                # CID 字体：两个字节一个码
                buf = []
                for i in range(0, len(raw) - 1, 2):
                    code = (raw[i] << 8) | raw[i + 1]
                    buf.append(cmap.get(code, ""))
                if any(buf):
                    chunks.append("".join(buf))
                    continue
            for enc in ("utf-16-be", "gbk", "latin-1"):
                try:
                    dec = raw.decode(enc)
                    if dec.strip():
                        chunks.append(dec)
                        break
                except Exception:
                    continue
    return "\n".join(chunks)


def pdf_text(data: bytes) -> str:
    streams = _streams(data)
    cmap = _parse_cmap(streams)
    text = _content_text(streams, cmap)
    # 合并多余空白，但保留换行以利阅读
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def load(src: str) -> bytes:
    if re.match(r"^https?://", src):
        status, body = R.http_get(src, headers={"Referer": "http://www.cninfo.com.cn/"},
                                  retries=3, backoff=6, timeout=60, want_status=True)
        if not isinstance(status, int) or status >= 400 or not body:
            sys.exit("下载失败: status=%s %s" % (status, src))
        return body
    with open(src, "rb") as f:
        return f.read()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    argv = sys.argv[2:]
    pat, window, outp, maxhits = None, 260, None, 20
    for i, a in enumerate(argv):
        if a == "--pat" and i + 1 < len(argv):
            pat = argv[i + 1]
        elif a == "--window" and i + 1 < len(argv):
            window = int(argv[i + 1])
        elif a == "--out" and i + 1 < len(argv):
            outp = argv[i + 1]
        elif a == "--maxhits" and i + 1 < len(argv):
            maxhits = int(argv[i + 1])

    data = load(src)
    text = pdf_text(data)
    name = re.sub(r"[^0-9A-Za-z_.-]", "_", src.split("/")[-1])[:60] or "pdf"
    outp = outp or os.path.join("leads_raw", "_pdftext_" + name)
    outp = outp if os.path.isabs(outp) else os.path.join(os.getcwd(), outp)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    with open(outp + ".txt", "w", encoding="utf-8") as f:
        f.write(text)

    hits = 0
    if pat:
        lines = []
        for m in re.finditer(re.escape(pat), text):
            a = max(0, m.start() - window // 2)
            lines.append(text[a:a + window].replace("\n", " "))
            hits += 1
            if hits >= maxhits:
                break
        with open(outp + ".hits.txt", "w", encoding="utf-8") as f:
            f.write(("\n---\n".join(lines)) if lines else "(无命中)\n")

    print("PDF=%s  bytes=%d  textlen=%d" % (os.path.basename(src), len(data), len(text)))
    print("全文已写出: %s.txt" % outp)
    if pat:
        print("命中「%s」%d 处（上限 %d），上下文已写出: %s.hits.txt" % (pat, hits, maxhits, outp))
    print("注意：控制台中文会乱码，请读上面两个 UTF-8 文件。")


if __name__ == "__main__":
    main()