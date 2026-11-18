# -*- coding: utf-8 -*-
"""用 Playwright 打开报告，抓控制台错误并截图各页。"""
import asyncio
import os
import sys
from playwright.async_api import async_playwright


async def main(path, shots_dir):
    os.makedirs(shots_dir, exist_ok=True)
    url = 'file:///' + os.path.abspath(path).replace('\\', '/')
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1440, 'height': 1000})
        errs = []
        pg.on('console', lambda m: errs.append('CONSOLE %s: %s' % (m.type, m.text)) if m.type in ('error', 'warning') else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERROR: %s' % e))
        await pg.goto(url, wait_until='load')
        await pg.wait_for_timeout(2200)
        tabs = await pg.query_selector_all('#tabs button')
        print('tabs', len(tabs))
        for i, t in enumerate(tabs):
            await t.click()
            await pg.wait_for_timeout(900)
            name = await t.get_attribute('data-k')
            await pg.screenshot(path=os.path.join(shots_dir, '%02d-%s.png' % (i, name)), full_page=True)
        # 检查关键元素
        for sel in ['#kpis .kpi', '#rangebar .mk', '#chart-trend canvas', '#chart-pct canvas', '#chart-spot canvas', '#chart-anchors canvas']:
            n = await pg.eval_on_selector_all(sel, 'els => els.length')
            print('  %-24s %s' % (sel, n))
        print('ERRORS:', len(errs))
        for e in errs[:15]:
            print('  ', e[:300])
        await b.close()


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2]))
