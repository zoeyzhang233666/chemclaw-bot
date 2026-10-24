# -*- coding: utf-8 -*-
"""无视觉模型时的图形自检：判断 canvas 是否真的画了东西（非空白），
以及关键 DOM 容器是否溢出/重叠。返回可读的诊断文本。"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

path = os.path.abspath(sys.argv[1])

PROBE = r"""
() => {
  const out = {};
  const desc = c => {
    const ctx = c.getContext('2d');
    const d = ctx.getImageData(0,0,c.width,c.height).data;
    let painted = 0, uniq = new Set();
    for (let i=0;i<d.length;i+=4*7){
      const a = d[i+3];
      if (a>8){ painted++; uniq.add(d[i]+','+d[i+1]+','+d[i+2]); }
    }
    return {w:c.width,h:c.height, paintedPx:painted, distinctColors:uniq.size};
  };
  out.canvases = [...document.querySelectorAll('canvas')].map(c=>({id:c.id, ...desc(c)}));
  // 溢出检查：元素 scrollWidth 远大于 clientWidth
  const over = [];
  document.querySelectorAll('div,table,td,th,h1,h2,p,span').forEach(el=>{
    if (el.scrollWidth > el.clientWidth + 8 && el.clientWidth > 0 && getComputedStyle(el).overflowX==='visible'){
      over.push({tag:el.tagName, cls:el.className.toString().slice(0,30), sw:el.scrollWidth, cw:el.clientWidth,
                 txt:(el.textContent||'').trim().slice(0,40)});
    }
  });
  out.overflow = over.slice(0,12);
  // 空容器检测：关键 id 容器子元素数量
  out.counts = {};
  ['#tbody tr.row','#relTable tr','#rtTable tr','#graphBox .node','#histBox tr.row','#sources .panel','#kpis .kpi',
   '#pBody .panel','#pBody .card','#pBody canvas','#pBody table'].forEach(sel=>{
     out.counts[sel] = document.querySelectorAll(sel).length;
  });
  return out;
}
"""


def main():
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1600, 'height': 1200})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto('file:///' + path.replace('\\', '/'))
        pg.wait_for_timeout(1500)
        res['scanner'] = pg.evaluate(PROBE)

        # 打开 PP-L 组合（最重要的案例）
        pg.evaluate("""() => {
          const r = PK.results.find(x=>x.code_a==='PP0'&&x.code_b==='L0');
          openPair(pairId(r));
        }""")
        pg.wait_for_timeout(600)
        res['pair_overview'] = pg.evaluate(PROBE)
        pg.click('#pairTabs .tab[data-t="price"]')
        pg.wait_for_timeout(900)
        res['pair_price'] = pg.evaluate(PROBE)
        pg.click('#pairTabs .tab[data-t="stat"]')
        pg.wait_for_timeout(900)
        res['pair_stat'] = pg.evaluate(PROBE)
        pg.click('#pairTabs .tab[data-t="fund"]')
        pg.wait_for_timeout(500)
        res['pair_fund'] = pg.evaluate(PROBE)

        # 图谱页
        pg.click('#backBtn'); pg.wait_for_timeout(300)
        pg.click('#pageTabs .tab[data-p="graph"]'); pg.wait_for_timeout(900)
        res['graph'] = pg.evaluate(PROBE)

        # 关系规则页
        pg.click('#pageTabs .tab[data-p="relations"]'); pg.wait_for_timeout(400)
        res['relations'] = pg.evaluate(PROBE)
        res['errors'] = errs
        b.close()

    for k, v in res.items():
        if k == 'errors':
            continue
        print(f"\n=== {k} ===")
        print(' counts:', json.dumps(v['counts'], ensure_ascii=False))
        if v['canvases']:
            for c in v['canvases']:
                fill = c['paintedPx'] / max(1, (c['w'] * c['h'] / 7)) * 100
                flag = 'OK' if c['paintedPx'] > 50 and c['distinctColors'] > 2 else 'EMPTY!'
                print(f"  canvas#{c['id']} {c['w']}x{c['h']} painted={c['paintedPx']} colors={c['distinctColors']} {flag}")
        if v['overflow']:
            print('  overflow:', json.dumps(v['overflow'][:6], ensure_ascii=False))
    print('\nJS errors:', res.get('errors'))


if __name__ == '__main__':
    main()
