#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_html.py — 调试助手：用无头浏览器打开页面，抓 DOM、JS 报错与截图。

与 check_html 的区别：这个脚本把原始 HTML/报错打印出来，便于定位脚本问题。
用法：
  python scripts/probe_html.py out/xxx.html [--shot 截图.png]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def find_browser():
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    for n in ("chrome", "chromium", "google-chrome", "msedge"):
        e = shutil.which(n)
        if e:
            return e
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--shot")
    ap.add_argument("--w", default="1440")
    ap.add_argument("--h", default="3200")
    a = ap.parse_args()

    br = find_browser()
    if not br:
        print("未找到 Chrome/Edge")
        return 2
    tmp = tempfile.mkdtemp(prefix="probe_")
    local = os.path.join(tmp, "page.html")
    shutil.copyfile(a.html, local)
    url = "file:///" + local.replace("\\", "/")

    dom_path = os.path.join(tmp, "dom.txt")
    log_path = os.path.join(tmp, "log.txt")
    cmd = (f'"{br}" --headless --disable-gpu --no-sandbox --virtual-time-budget=9000 '
           f'--enable-logging=stderr --v=0 --dump-dom "{url}" > "{dom_path}" 2> "{log_path}"')
    subprocess.run(cmd, shell=True, timeout=180)

    with open(dom_path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            dom = raw.decode(enc)
            print(f"[probe] DOM 解码编码 = {enc}, 长度 = {len(dom)}")
            break
        except UnicodeDecodeError:
            continue
    else:
        dom = raw.decode("utf-8", "replace")

    with open(log_path, "rb") as f:
        log = f.read().decode("utf-8", "replace")
    errs = [ln for ln in log.splitlines()
            if any(k in ln.lower() for k in ("error", "uncaught", "typeerror", "syntaxerror", "referenceerror"))]
    print(f"[probe] 控制台错误 {len(errs)} 条：")
    for e in errs[:25]:
        print("   ", e.strip()[:300])

    for marker in ('id="ssrBanner"', "脚本初始化失败", "无法直接折算"):
        idx = dom.find(marker)
        print(f"[probe] '{marker}' -> {idx}")
        if marker == 'id="ssrBanner"' and idx >= 0:
            print("   ", dom[idx:idx + 300].replace("\n", " ")[:300])
    if "脚本初始化失败" in dom:
        i = dom.find("脚本初始化失败")
        print("[probe] 失败横幅片段：", dom[i - 80:i + 400].replace("\n", " "))

    b = a.html
    if a.shot:
        shot = os.path.abspath(a.shot)
        cmd2 = (f'"{br}" --headless --disable-gpu --no-sandbox --hide-scrollbars '
                f'--virtual-time-budget=9000 --window-size={a.w},{a.h} --screenshot="{shot}" "{url}"')
        subprocess.run(cmd2, shell=True, timeout=180)
        print(f"[probe] 截图 -> {shot} ({os.path.getsize(shot) if os.path.exists(shot) else 0} bytes)")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
