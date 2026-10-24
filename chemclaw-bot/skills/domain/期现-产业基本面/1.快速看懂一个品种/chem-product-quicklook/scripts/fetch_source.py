#!/usr/bin/env python3
"""fetch_source.py — 用无头 Chromium 抓取来源正文（抗超时/JS 渲染/部分反爬）

用途：核实事实时把原文落到本地，便于“事实可回溯”。产出的 raw/ 目录可直接放 examples 里。

用法:
    python scripts/fetch_source.py "https://example.com/a.html" --out raw/ --name demo
    python scripts/fetch_source.py --list urls.txt --out raw/        # 每行一个 URL
    python scripts/fetch_source.py ... --shot shots/demo.png         # 同时截图

注意：
  - 只抓公开页面，不绕过登录与付费墙；抓取失败要记入缺口，不得用记忆代替原文。
  - 正文抽取为“可见文本”（去脚本/样式），保留标题与 URL，写入 JSON + TXT。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def slug(u: str) -> str:
    p = urlparse(u)
    s = (p.netloc + p.path).strip("/").replace("/", "_")
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5_.-]+", "-", s)[:80] or "page"


def grab(page, url: str, wait_ms: int = 1200) -> dict:
    resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(wait_ms)
    title = page.title()
    text = page.evaluate(
        """() => {
            const drop = ['script','style','noscript','svg','iframe','nav','footer'];
            const clone = document.body ? document.body.cloneNode(true) : null;
            if (!clone) return '';
            drop.forEach(t => clone.querySelectorAll(t).forEach(e => e.remove()));
            return clone.innerText || '';
        }"""
    )
    text = re.sub(r"\n{3,}", "\n\n", (text or "")).strip()
    return {"url": url, "final_url": page.url, "status": resp.status if resp else None,
            "title": title, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "chars": len(text), "text": text}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--list", help="URL 列表文件，每行一个")
    ap.add_argument("--out", default="raw")
    ap.add_argument("--name", default=None)
    ap.add_argument("--shot", default=None)
    ap.add_argument("--wait", type=int, default=1200)
    ap.add_argument("--grep", default=None, help="只打印命中该正则的段落，便于快速核数")
    a = ap.parse_args(argv)

    urls = []
    if a.url:
        urls.append(a.url)
    if a.list:
        urls += [x.strip() for x in Path(a.list).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    if not urls:
        ap.error("需要 url 或 --list")

    from playwright.sync_api import sync_playwright

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                            locale="zh-CN", viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()
        for i, u in enumerate(urls, 1):
            name = a.name if (a.name and len(urls) == 1) else f"{i:02d}_{slug(u)}"
            try:
                rec = grab(page, u, a.wait)
            except Exception as e:
                rec = {"url": u, "error": str(e)[:300], "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
            (out / f"{name}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            if rec.get("text"):
                (out / f"{name}.txt").write_text(f"{rec['title']}\n{rec['url']}\n抓取 {rec['fetched_at']}\n\n{rec['text']}", encoding="utf-8")
            index.append({"name": name, "url": u, "title": rec.get("title"), "chars": rec.get("chars"), "error": rec.get("error")})
            print(f"[{i}/{len(urls)}] {name}: {rec.get('chars', 0)} chars  {rec.get('title','')[:60]} {('ERR ' + rec['error'][:80]) if rec.get('error') else ''}")
            if a.shot and len(urls) == 1:
                Path(a.shot).parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=a.shot, full_page=True)
            if a.grep and rec.get("text"):
                paras = [x.strip() for x in rec["text"].split("\n") if re.search(a.grep, x)]
                for x in paras[:20]:
                    print("   › " + x[:300])
        b.close()
    (out / "_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [x for x in index if x.get("error") or not x.get("chars")]
    print(f"[fetch_source] {len(index)-len(bad)}/{len(index)} 成功 → {out}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
