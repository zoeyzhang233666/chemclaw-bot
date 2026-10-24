#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Playwright/Chromium 渲染 HTML：截图、收集 JS 错误、验证交互重算是否生效。

用法:
  python qa_render.py page.html --out shots [--mobile]

检查项：
  1. 无 pageerror / console.error
  2. 至少渲染出 1 个 canvas（ECharts）
  3. 修改一个单耗后，首屏 KPI 数字发生变化（说明是"活"计算器而不是静态报告）
  4. 修改组合情景涨跌幅后，情景表数值变化
返回码 0 = 全部通过
"""
import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright


def shot(pg, sel, path, w):
    try:
        el = pg.query_selector(sel)
        if not el:
            return False
        el.scroll_into_view_if_needed()
        pg.wait_for_timeout(300)
        box = el.bounding_box()
        if not box:
            return False
        pg.screenshot(path=path, full_page=True,
                      clip={'x': max(0.0, box['x'] - 8), 'y': max(0.0, box['y'] - 8),
                            'width': min(box['width'] + 16, w), 'height': min(box['height'] + 16, 1600)})
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('--out', default='shots')
    ap.add_argument('--mobile', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    url = 'file:///' + os.path.abspath(a.html).replace('\\', '/')
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        w, h = (430, 932) if a.mobile else (1560, 1100)
        pg = b.new_page(viewport={'width': w, 'height': h})
        pg.on('console', lambda m: errs.append('CONSOLE ' + m.type + ': ' + m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERROR: ' + str(e)))
        pg.goto(url, wait_until='load')
        pg.wait_for_timeout(2000)
        tag = 'm' if a.mobile else 'd'
        pg.screenshot(path=os.path.join(a.out, tag + '00_full.png'), full_page=True)
        for i, (sel, name) in enumerate([('.kpis', 'kpi'), ('#tblComp', 'comp'), ('#chHist', 'hist'),
                                         ('#tblHeat', 'heat'), ('#scenCards', 'scen'), ('#tblCombo', 'combo'),
                                         ('#chContrib', 'contrib'), ('#recentBox', 'recent')]):
            shot(pg, sel, os.path.join(a.out, '%s%02d_%s.png' % (tag, i + 1, name)), w)

        info = pg.evaluate('''() => {
          const kpi = () => (document.querySelector('.kpi.hero .val')||{}).innerText || '';
          const out = {charts: document.querySelectorAll('canvas').length,
                       kpi0: kpi(), rows: document.querySelectorAll('#tblComp tbody tr').length,
                       heat: document.querySelectorAll('#tblHeat tbody tr').length};
          // 选一个“有价格”的原料来改单耗：改缺价原料的单耗不会影响成本，测不出交互
          const qs = [...document.querySelectorAll('#mateditor input[data-k="q"]')];
          const ps = [...document.querySelectorAll('#mateditor input[data-k="p"]')];
          let q = null;
          for (let i = 0; i < qs.length; i++) {
            if (ps[i] && ps[i].value !== '') { q = qs[i]; break; }
          }
          if (!q) { q = qs[0]; }
          if (q) { q.value = (parseFloat(q.value) * 1.10).toFixed(4); q.dispatchEvent(new Event('change')); }
          out.kpi1 = kpi();
          const ci = document.querySelector('#tblCombo input');
          let comboBefore = '', comboAfter = '';
          if (ci) {
            const tr = ci.closest('tr');
            const tds = tr.querySelectorAll('td');
            comboBefore = tds[tds.length - 2].innerText;
            ci.value = 25; ci.dispatchEvent(new Event('change'));
            const tr2 = document.querySelector('#tblCombo input').closest('tr');
            const tds2 = tr2.querySelectorAll('td');
            comboAfter = tds2[tds2.length - 2].innerText;
          }
          out.comboBefore = comboBefore; out.comboAfter = comboAfter;
          return out;
        }''')
        pg.wait_for_timeout(600)
        pg.screenshot(path=os.path.join(a.out, tag + '99_after_edit.png'), full_page=True)
        # 打开抽屉
        try:
            pg.evaluate("document.querySelector('#mateditor input[data-k=\"q\"]');")
            pg.click('#tblComp .linky', timeout=3000)
            pg.wait_for_timeout(900)
            pg.screenshot(path=os.path.join(a.out, tag + '98_drawer.png'))
            info['drawer'] = pg.evaluate("document.querySelector('#dBody').innerText.length")
        except Exception as e:
            info['drawer'] = 'FAIL ' + str(e)[:80]
        b.close()

    print(json.dumps(info, ensure_ascii=False, indent=1))
    print('JS 错误数：', len(errs))
    for e in errs[:15]:
        print('   ', e)
    ok = (not errs and info.get('charts', 0) >= 3 and info.get('kpi0') != info.get('kpi1')
          and info.get('comboBefore') != info.get('comboAfter') and isinstance(info.get('drawer'), int)
          and info.get('drawer') > 200)
    if info.get('charts', 0) < 3:
        print('!! 图表数量不足（canvas<3）：' + str(info.get('charts')))
    if info.get('kpi0') == info.get('kpi1'):
        print('!! 修改单耗后 KPI 未变化：不是可交互计算器')
    if info.get('comboBefore') == info.get('comboAfter'):
        print('!! 修改组合情景后数值未变化')
    print('RESULT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
