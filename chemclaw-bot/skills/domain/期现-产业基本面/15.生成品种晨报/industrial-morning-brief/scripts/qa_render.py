# -*- coding: utf-8 -*-
"""HTML 渲染实测（需要 playwright；未安装则跳过并提示，不阻断交付）。

用法：
  python qa_render.py out/brief.html --shots shots

检查项：
1. 控制台 JS 错误 / 资源加载失败；
2. 首屏：3 张品种摘要卡、hero 元信息、规则条是否渲染；
3. 图表：canvas 是否真的画出像素（不是空白容器）；
4. 模块：每个品种 5 个模块是否都在 DOM 里；
5. 交互：点击指标行能打开抽屉、抽屉里含「发生了什么/为什么/验证/来源」四块；
6. 筛选：切到「A 必看」后条数下降且不为 0；
7. 响应式：1600 / 1280 / 420 三档是否横向溢出；
8. 截图落盘供人工过目。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def run(path, shots, width=(1600, 1280, 420)):
    from playwright.sync_api import sync_playwright
    fails, warns = [], []
    os.makedirs(shots, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={'width': width[1], 'height': 1000}, device_scale_factor=1)
        errs, reqfail = [], []
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append('pageerror: %s' % e))
        pg.on('requestfailed', lambda r: reqfail.append(r.url))
        pg.goto('file://' + os.path.abspath(path))
        pg.wait_for_timeout(1800)

        if errs:
            fails.append('控制台错误 %d 条：%s' % (len(errs), errs[:3]))
        ext = [u for u in reqfail if not u.startswith('file://') and not u.startswith('data:')]
        if ext:
            warns.append('外部资源请求失败（离线文件不应有外部依赖）：%s' % ext[:3])

        cards = pg.locator('.card').count()
        if cards < 3:
            fails.append('摘要卡只有 %d 张（应 ≥3）' % cards)
        hero = pg.locator('#heroMeta .pill').count()
        if hero < 2:
            fails.append('hero 元信息未渲染')

        panels = pg.locator('.panel[data-product]').count()
        if panels < 3:
            fails.append('品种面板只有 %d 个（应 3）' % panels)

        # 图表绘制
        canvas = pg.locator('.chart canvas').count()
        if canvas < 4:
            fails.append('图表 canvas 只有 %d 个（每个品种应有 K 线与基差 2 张）' % canvas)
        else:
            drawn = pg.evaluate("""() => Array.from(document.querySelectorAll('.chart canvas')).filter(c=>{
                const x=c.getContext('2d'); if(!c.width||!c.height) return false;
                const d=x.getImageData(0,0,c.width,c.height).data;
                let n=0; for(let i=3;i<d.length;i+=400){ if(d[i]>0) n++; }
                return n>50;
            }).length""")
            if drawn < 3:
                fails.append('图表真正绘出像素的只有 %d / %d' % (drawn, canvas))

        # 模块完整性
        mods = pg.evaluate("""() => Array.from(document.querySelectorAll('.panel[data-product]'))
            .map(p=>[p.dataset.product, p.querySelectorAll('.panel-body .panel').length])""")
        for prod, n in mods:
            if n < 5:
                fails.append('%s 只有 %d 个模块（应 5）' % (prod, n))

        # 抽屉
        tr = pg.locator('tr.clickable').first
        if tr.count():
            tr.click()
            pg.wait_for_timeout(600)
            if not pg.locator('#drawer.on').count():
                fails.append('点击指标行未打开抽屉')
            body = pg.locator('#drBody').inner_text()
            for k in ('发生了什么', '数据如何变化', '为什么值得关注', '今天继续验证什么', '来源'):
                if k not in body:
                    fails.append('抽屉缺少「%s」区块' % k)
            pg.screenshot(path=os.path.join(shots, 'drawer.png'))
            pg.locator('#drClose').click()
            pg.wait_for_timeout(400)
        else:
            fails.append('没有可点击的指标行')

        # 筛选
        n_all = pg.locator('#shownN').inner_text()
        pg.locator('.chip[data-filter="tier"][data-value="A"]').click()
        pg.wait_for_timeout(400)
        n_a = pg.locator('#shownN').inner_text()
        if not (int(n_a) > 0):
            fails.append('筛选 A 必看后条数为 0')
        if int(n_a) > int(n_all):
            fails.append('筛选 A 后条数反而增加')
        pg.locator('.chip[data-filter="tier"][data-value="all"]').click()
        pg.wait_for_timeout(300)

        # 响应式溢出
        overflow = {}
        for w in width:
            pg.set_viewport_size({'width': w, 'height': 1000})
            pg.wait_for_timeout(500)
            ov = pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            overflow[w] = ov
            if ov > 3:
                fails.append('%dpx 视口横向溢出 %dpx' % (w, ov))
            pg.screenshot(path=os.path.join(shots, 'w%d.png' % w), full_page=(w != 420))

        br.close()
    return fails, warns, {'cards': cards, 'panels': panels, 'canvas': canvas,
                          'overflow': overflow, 'n_all': n_all, 'n_a': n_a}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('--shots', default='shots')
    a = ap.parse_args()
    try:
        import playwright  # noqa
    except ImportError:
        common.warn('未安装 playwright，跳过浏览器实测（静态检查请跑 check_html.py）')
        return
    fails, warns, info = run(a.html, a.shots)
    common.ok('实测指标：%s' % info)
    for w in warns:
        common.warn(w)
    if fails:
        for f in fails:
            print('[FAIL ] ' + f)
        common.die('渲染实测未通过（%d 项）' % len(fails))
    common.ok('渲染实测全部通过')


if __name__ == '__main__':
    main()
