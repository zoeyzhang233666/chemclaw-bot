#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ui_check.py —— 用无头 Chrome 真的点一遍 HTML（可选，需 playwright）

用法
  python scripts/ui_check.py --html <报告.html> [--shot <截图.png>]

检查：无 JS 报错、6 个标签页可切换、企业行点开抽屉、项目卡点开抽屉、搜索过滤生效。
没装 playwright 时直接跳过（退出码 0），不影响主流程。
"""
import argparse
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--shot", default="")
    args = ap.parse_args()
    path = os.path.abspath(args.html)
    if not os.path.exists(path):
        raise SystemExit(f"找不到 HTML：{path}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[跳过] 未安装 playwright：pip install playwright && playwright install chromium")
        return 0

    url = "file:///" + path.replace("\\", "/")
    fails = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_timeout(700)

        tabs = page.eval_on_selector_all(".tab-btn", "els => els.map(e => e.dataset.tab)")
        print(f"标签页：{tabs}")
        for t in tabs:
            page.click(f'.tab-btn[data-tab="{t}"]')
            page.wait_for_timeout(180)
            visible = page.eval_on_selector(f"#tab-{t}", "el => el.classList.contains('active')")
            if not visible:
                fails.append(f"标签页 {t} 切换失败")
        print(f"标签页切换：{'全部通过' if not fails else '有失败'}")

        page.click('.tab-btn[data-tab="table"]')
        page.wait_for_timeout(200)
        rows = page.eval_on_selector_all("#companyTable tbody tr[data-company]", "els => els.length")
        print(f"企业表行数：{rows}")
        if rows:
            page.click("#companyTable tbody tr[data-company]")
            page.wait_for_timeout(350)
            opened = page.eval_on_selector("#drawer", "el => el.classList.contains('open')")
            title = page.eval_on_selector("#drawerTitle", "el => el.textContent")
            print(f"企业抽屉：{'已打开' if opened else '未打开'} · {title}")
            if not opened:
                fails.append("企业抽屉未打开")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

        # 用数据里真实存在的一个关键词做过滤测试（与产品无关）
        probe = page.evaluate("""() => {
          const rows = [...document.querySelectorAll('#companyTable tbody tr[data-company]')];
          if (!rows.length) return '';
          const cells = [...rows[0].children].map(td => td.textContent.trim());
          return cells.find(t => t && t.length >= 2 && !/^[\\d,.%+-]+$/.test(t)) || '';
        }""")
        if probe:
            page.fill("#coSearch", probe)
            page.wait_for_timeout(250)
            shown = page.eval_on_selector_all(
                "#companyTable tbody tr[data-company]",
                "els => els.filter(e => e.style.display !== 'none').length")
            print(f"搜索「{probe}」命中：{shown} / {rows} 家")
            if shown == 0:
                fails.append("搜索过滤无结果（应至少命中 1 家）")
            page.fill("#coSearch", "")

        page.click('.tab-btn[data-tab="projects"]')
        page.wait_for_timeout(200)
        prj = page.eval_on_selector_all(".prj", "els => els.length")
        print(f"项目卡：{prj}")
        if prj:
            page.click(".prj")
            page.wait_for_timeout(350)
            opened = page.eval_on_selector("#drawer", "el => el.classList.contains('open')")
            title = page.eval_on_selector("#drawerTitle", "el => el.textContent")
            print(f"项目抽屉：{'已打开' if opened else '未打开'} · {title}")
            if not opened:
                fails.append("项目抽屉未打开")
            page.keyboard.press("Escape")

        if args.shot:
            page.click('.tab-btn[data-tab="overview"]')
            page.wait_for_timeout(400)
            page.screenshot(path=args.shot, full_page=True)
            print(f"截图：{args.shot}")

        if errors:
            print("JS 报错：")
            for e in errors[:10]:
                print("  -", e)
            fails.append(f"{len(errors)} 条 JS 报错")
        browser.close()

    print("\n" + ("全部通过" if not fails else "失败项：\n  - " + "\n  - ".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
