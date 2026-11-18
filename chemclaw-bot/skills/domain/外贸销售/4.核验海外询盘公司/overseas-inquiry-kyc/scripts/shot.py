# -*- coding: utf-8 -*-
"""用 playwright 截取 HTML 报告的关键区段，用于视觉 QA。
用法: python shot.py report.html outdir [--full]
"""
import sys, os, time
from playwright.sync_api import sync_playwright

src = sys.argv[1]
out = sys.argv[2]
full = "--full" in sys.argv
os.makedirs(out, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    errs = []
    pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    pg.goto("file:///" + os.path.abspath(src).replace("\\", "/"))
    pg.wait_for_timeout(900)
    print("CONSOLE:", errs if errs else "clean")

    sel = {
        "01-hero": "#sec-hero",
        "02-inquiry": "#sec-inquiry",
        "03-extract": "#sec-extract",
        "04-subject": "#sec-subject",
        "05-business": "#sec-business",
        "06-contact": "#sec-contact",
        "07-checks": "#sec-checks",
        "08-risk": "#sec-risk",
        "09-gaps": "#sec-gaps",
        "10-concl": "#sec-concl",
        "11-sources": "#sec-sources",
    }
    for name, s in sel.items():
        el = pg.query_selector(s)
        if not el:
            print("MISSING", s)
            continue
        el.scroll_into_view_if_needed()
        pg.wait_for_timeout(120)
        el.screenshot(path=os.path.join(out, name + ".png"))
    if full:
        pg.screenshot(path=os.path.join(out, "full.png"), full_page=True)
    # 抽屉测试
    try:
        pg.click("#sec-checks .chk .src-pill >> nth=0")
        pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(out, "12-drawer.png"))
    except Exception as e:
        print("drawer test failed:", e)
    print("CONSOLE(after):", errs if errs else "clean")
    b.close()
print("done")
