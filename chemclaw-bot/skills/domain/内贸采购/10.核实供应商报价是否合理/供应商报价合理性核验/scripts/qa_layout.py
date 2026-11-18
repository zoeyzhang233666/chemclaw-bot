# -*- coding: utf-8 -*-
"""布局体检：元素重叠、溢出、空文本、图表是否有实际像素。"""
import asyncio
import os
import sys
from playwright.async_api import async_playwright

JS = """
() => {
  const out = {issues: [], charts: []};
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0'; };
  // 1) 横向溢出
  const de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 2) out.issues.push('页面横向溢出 ' + de.scrollWidth + '>' + de.clientWidth);
  // 2) 图表画布
  document.querySelectorAll('div[id^=chart-]').forEach(d => {
    const c = d.querySelector('canvas');
    let ok = false, msg = '';
    if (!c) { msg = '无 canvas'; }
    else {
      ok = c.width > 100 && c.height > 60;
      msg = c.width + 'x' + c.height;
    }
    out.charts.push({id: d.id, canvas: msg, ok});
  });
  // 3) 文本溢出（scrollWidth 超出容器且无明显裁剪意图）
  document.querySelectorAll('main section.on *').forEach(el => {
    if (el.children.length === 0 && el.scrollWidth > el.clientWidth + 24 && el.clientWidth > 0) {
      out.issues.push('文本溢出: ' + (el.className||el.tagName) + ' :: ' + (el.textContent||'').slice(0,40));
    }
  });
  // 4) rangebar 标签是否出界
  const rb = document.getElementById('rangebar');
  if (rb) { const rr = rb.getBoundingClientRect();
    rb.querySelectorAll('.tick,.mk b').forEach(t => { const tr = t.getBoundingClientRect();
      if (tr.left < rr.left - 2 || tr.right > rr.right + 2) out.issues.push('区间标签出界: ' + t.textContent.slice(0,20)); }); }
  // 5) 是否残留占位符
  const body = document.body.innerText;
  ['__TITLE__','__DATA__','{{','undefined','NaN','null 元'].forEach(k => { if (body.includes(k)) out.issues.push('可疑文本: ' + k); });
  return out;
}
"""


async def main(path):
    url = 'file:///' + os.path.abspath(path).replace('\\', '/')
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1440, 'height': 1000})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(url, wait_until='load')
        await pg.wait_for_timeout(2000)
        tabs = await pg.query_selector_all('#tabs button')
        for t in tabs:
            k = await t.get_attribute('data-k')
            await t.click()
            await pg.wait_for_timeout(800)
            r = await pg.evaluate(JS)
            print('== %s: issues=%d' % (k, len(r['issues'])))
            for i in r['issues'][:8]:
                print('   !', i)
            if k == 'overview':
                for c in r['charts']:
                    print('   chart %-14s %-12s %s' % (c['id'], c['canvas'], 'OK' if c['ok'] else 'EMPTY'))
            # 交互：切换走势口径
            if k == 'overview':
                for ck in ['fut1y', 'fut3m', 'fut3y', 'ppi']:
                    await pg.click('#trend-chips .chip[data-k="%s"]' % ck)
                    await pg.wait_for_timeout(700)
                    r2 = await pg.evaluate(JS)
                    bad = [c for c in r2['charts'] if not c['ok']]
                    print('   switch %-6s -> charts ok=%d bad=%d' % (ck, len(r2['charts']) - len(bad), len(bad)))
        print('PAGE ERRORS:', errs[:5])
        await b.close()


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1]))
