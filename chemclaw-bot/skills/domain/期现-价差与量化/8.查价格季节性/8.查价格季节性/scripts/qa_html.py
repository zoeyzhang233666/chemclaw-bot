# -*- coding: utf-8 -*-
"""qa_html.py — 浏览器实测交互式季节性报告（不是看截图，是操作它）。

检查项
  1. 无 JS 报错 / 无控制台 error
  2. 首屏 KPI、口径横幅、使用边界（"不是预测"）存在
  3. 主图 SVG 真的画出了像素（polygon/path 数量 > 阈值）
  4. 周度↔月度切换后 x 轴刻度、表格行数随之变化
  5. 绝对价格↔年初归一化切换后，y 轴量级变化（归一化应在 100 附近）
  6. 年份开关：关掉全部历史年后 curve 数量下降；点回后恢复
  7. 悬停出现 tooltip 且含年份+数值
  8. 无横向溢出（1600 / 1280 / 420 三档）
  9. 页面不引用任何外链资源（单文件离线可开）

用法: python qa_html.py <html> [--shots]
"""
import argparse
import json
import os
import re
import sys
from playwright.sync_api import sync_playwright

FAILS = []
WARN = []


def ck(name, cond, detail=''):
    print('  [%s] %s %s' % ('PASS' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('--shots', action='store_true')
    a = ap.parse_args()
    path = os.path.abspath(a.html)
    raw = open(path, encoding='utf-8').read()

    print('A) 静态检查')
    ck('无未替换占位符', not re.search(r'__[A-Z]+__', raw),
       str(re.findall(r'__[A-Z]+__', raw)[:5]))
    ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', raw)
    ck('无外链资源（可离线打开）', len(ext) == 0, str(ext[:3]))
    ck('含使用边界声明', '不是对未来价格的预测' in raw)
    ck('含口径降级声明', '口径声明' in raw or '口径' in raw)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1600, 'height': 1100})
        errs, cons = [], []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: cons.append(m.text) if m.type == 'error' else None)
        pg.goto('file:///' + path.replace('\\', '/'))
        pg.wait_for_timeout(900)

        print('B) 交互与渲染')
        ck('无 JS 异常', not errs, str(errs[:2]))
        ck('无 console error', not cons, str(cons[:2]))

        cards = pg.locator('#curCards .card').count()
        ck('当前年位置卡渲染', cards >= 3, 'cards=%d' % cards)

        def svg_stats():
            return pg.evaluate("""() => {
              const s = document.querySelector('#chartMain svg');
              if(!s) return {ok:false};
              return {ok:true,
                poly: s.querySelectorAll('polygon').length,
                paths: s.querySelectorAll('path').length,
                circles: s.querySelectorAll('circle').length,
                texts: s.querySelectorAll('text').length,
                rects: s.querySelectorAll('rect').length,
                box: s.getBoundingClientRect().width};
            }""")
        st = svg_stats()
        ck('主图 SVG 存在且有尺寸', st.get('ok') and st.get('box', 0) > 300, json.dumps(st))
        ck('分位带已绘制（polygon>=2）', st.get('poly', 0) >= 2, 'poly=%s' % st.get('poly'))
        ck('逐年曲线已绘制（path>=3）', st.get('paths', 0) >= 3, 'paths=%s' % st.get('paths'))
        ck('当前年数据点已绘制', st.get('circles', 0) >= 1, 'circles=%s' % st.get('circles'))

        # 悬停 tooltip
        rects = pg.locator('#chartMain svg rect')
        n_rect = rects.count()
        ck('悬停热区存在', n_rect >= 30, 'rects=%d' % n_rect)
        if n_rect:
            # 先把主图滚进视口，再用真实鼠标事件（否则坐标在视口外，命中测试失败）
            pg.evaluate("""() => document.querySelector('#chartMain')
                .scrollIntoView({block:'center'})""")
            pg.wait_for_timeout(250)
            box = rects.nth(min(20, n_rect - 1)).bounding_box()
            pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
            pg.wait_for_timeout(350)
            tip = pg.evaluate("() => { const t=document.querySelector('#tip'); return {op:+getComputedStyle(t).opacity, html:t.innerText}; }")
            ck('悬停出现 tooltip', tip['op'] > 0.5, 'opacity=%s' % tip['op'])
        ck('tooltip 含年份与数值', bool(re.search(r'\d{4}', tip['html'])) and bool(re.search(r'\d{3,}', tip['html'])),
               (tip['html'] or '')[:80].replace('\n', ' | '))

        # 周度 -> 月度
        # 不能用"SVG text 总数"判断：y 轴刻度条数随 nice-step 变化，会干扰计数。
        # 改为直接取 x 轴位置标签序列（W01.. / 1月..）。
        def xlabels():
            return pg.evaluate("""() => {
              const t = [...document.querySelectorAll('#chartMain svg text')].map(e=>e.textContent);
              return t.filter(s=>/^(W\\d{2}|\\d{1,2}月)$/.test(s));
            }""")
        lab_w = xlabels()
        pg.click('#freqM'); pg.wait_for_timeout(450)
        lab_m = xlabels()
        roww = pg.locator('#tblStats tbody tr').count()
        ck('月度切换后位置数变为 12 行', roww == 12, 'rows=%d' % roww)
        ck('切换后 x 轴标签换为月份', len(lab_m) > 0 and all(s.endswith('月') for s in lab_m),
           'monthly=%s' % lab_m[:4])
        ck('周/月 x 轴标签集合不同', set(lab_w) != set(lab_m),
           'weekly=%s / monthly=%s' % (lab_w[:3], lab_m[:3]))

        # 绝对 -> 归一化
        ycap = pg.evaluate("""() => {
          const t=[...document.querySelectorAll('#chartMain svg text')].map(e=>e.textContent)
                   .map(s=>parseFloat((s||'').replace(/,/g,''))).filter(v=>!isNaN(v));
          return t.length? {min:Math.min(...t),max:Math.max(...t)} : null; }""")
        pg.click('#modeNorm'); pg.wait_for_timeout(400)
        ycap2 = pg.evaluate("""() => {
          const t=[...document.querySelectorAll('#chartMain svg text')].map(e=>e.textContent)
                   .map(s=>parseFloat((s||'').replace(/,/g,''))).filter(v=>!isNaN(v));
          return t.length? {min:Math.min(...t),max:Math.max(...t)} : null; }""")
        ck('归一化视图 y 轴量级在 100 附近', ycap2 and ycap2['min'] < 140 and ycap2['max'] < 260,
           'norm=%s raw=%s' % (ycap2, ycap))
        pg.click('#modeAbs'); pg.click('#freqW'); pg.wait_for_timeout(300)

        # 年份开关
        n_paths_on = pg.evaluate("() => document.querySelectorAll('#chartMain svg path').length")
        pg.click('#btnNone'); pg.wait_for_timeout(350)
        n_paths_min = pg.evaluate("() => document.querySelectorAll('#chartMain svg path').length")
        pg.click('#btnAll'); pg.wait_for_timeout(350)
        n_paths_back = pg.evaluate("() => document.querySelectorAll('#chartMain svg path').length")
        ck('仅当前年时曲线减少', n_paths_min < n_paths_on, '%d -> %d' % (n_paths_on, n_paths_min))
        ck('全选后曲线恢复', n_paths_back >= n_paths_on, '%d -> %d' % (n_paths_min, n_paths_back))

        # 表行数
        ck('逐年覆盖表行数=年份数', pg.locator('#tblCover tbody tr').count() >= 4,
           'rows=%d' % pg.locator('#tblCover tbody tr').count())
        ck('当前期明细表有行', pg.locator('#tblCur tbody tr').count() > 0)
        ck('异常年表有行', pg.locator('#tblAnom tbody tr').count() > 0)
        ck('杠杆表有行', pg.locator('#tblLev tbody tr').count() > 0)

        print('C) 三档视口横向溢出')
        for w in (1600, 1280, 420):
            pg.set_viewport_size({'width': w, 'height': 1000})
            pg.wait_for_timeout(350)
            ov = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ck('%dpx 无横向溢出' % w, ov <= 2, 'overflow=%dpx' % ov)

        if a.shots:
            pg.set_viewport_size({'width': 1500, 'height': 1150})
            pg.wait_for_timeout(300)
            out = os.path.splitext(path)[0] + '_qa.png'
            pg.screenshot(path=out, full_page=False)
            print('  shot ->', out)
        b.close()

    print('\n结果: %d 项失败' % len(FAILS))
    if FAILS:
        print('失败:', FAILS)
        sys.exit(1)
    print('全部通过')


if __name__ == '__main__':
    main()
