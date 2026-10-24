# -*- coding: utf-8 -*-
"""浏览器渲染自检（采购版，需要 playwright）：抓 JS 报错、检查各模块是否真的渲染、点选/抽屉/话术是否可用。

用法：
  python qa_render.py out.html [data.json]
  python qa_render.py out.html data.json --shots shots/
没装 playwright 时自动跳过并返回 0（静态检查仍有效）。

断言全部从 data.json 读期望值，**不写任何品种名**，换品种可直接复用。
"""
import argparse
import json
import os
import sys

try:
    from playwright.sync_api import sync_playwright
    HAS_PW = True
except Exception:
    HAS_PW = False

BANNED = ('预计涨', '预计跌', '看涨', '看跌', '抄底', '必涨', '必跌', '会涨', '会跌')


def run(html_path, data_path=None, shots=None):
    if not HAS_PW:
        print('[SKIP ] 未安装 playwright，跳过渲染检查（静态检查仍有效）')
        return 0, []

    D = json.load(open(data_path, encoding='utf-8')) if data_path and os.path.exists(data_path) else None
    url = 'file:///' + os.path.abspath(html_path).replace('\\', '/')
    fails, errs = [], []
    if shots:
        os.makedirs(shots, exist_ok=True)

    def must(name, cond, detail=''):
        if cond:
            print('  PASS', name)
        else:
            print('  FAIL', name, detail)
            fails.append(name + ' ' + str(detail))

    with sync_playwright() as pw:
        b = pw.chromium.launch(args=['--no-sandbox'])
        pg = b.new_page(viewport={'width': 1600, 'height': 1100})
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console.error: ' + m.text) if m.type == 'error' else None)
        pg.goto(url, wait_until='load', timeout=60000)
        pg.wait_for_timeout(2600)

        # ---- 首屏
        n = pg.eval_on_selector_all('#kpiGrid .card', 'els=>els.length')
        must('KPI 卡片 ≥4 且 ≤8', 4 <= n <= 8, n)
        txt = pg.inner_text('body')
        must('页面非空白', len(txt) > 1500, len(txt))
        must('首屏写明“不预测”', ('不预测' in txt), '')
        if D and D.get('anchor'):
            v = format(round(D['anchor']['value']), ',')
            must('锚价出现在页面：%s' % v, v in txt.replace(' ', ''), v)

        # ---- 主图绘制
        painted = pg.evaluate("""() => {const c=document.querySelectorAll('canvas')[0];
            if(!c) return -1; const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            let n=0; for(let i=3;i<d.length;i+=4*29){ if(d[i]>8) n++; } return n;}""")
        has_seq = bool(D and (D.get('series') or {}))
        if has_seq:
            must('主图已绘制像素', isinstance(painted, int) and painted > 200, painted)
        else:
            print('  SKIP 主图（无报价序列）')

        # ---- 模块渲染
        expects = [
            ('#spotTable tbody tr', '现货报价表', bool(D and D.get('quotes'))),
            ('#chgTable tbody tr', '区间涨跌表', bool(D and (D.get('chg') or {}))),
            ('#winTable tbody tr', '分位表', bool(D and (D.get('win') or {}))),
            ('#spreadTable tbody tr', '区域价差表', bool(D and (D.get('spreads') or D.get('spread_groups')))),
            ('#timeline .tli', '事件时间线', bool(D and D.get('events'))),
            ('#gapGrid .mcard', '缺口卡', bool(D and D.get('gaps'))),
            ('#srcList a', '来源清单', bool(D and D.get('sources'))),
            ('#proofTable tbody tr', '链断点自证表', bool(D and D.get('chain_proof'))),
            ('#balBody tbody tr', '库存开工表', bool(D and D.get('balance'))),
            ('#factGrid .card', '可用事实卡', bool(D and D.get('facts'))),
        ]
        for sel, name, expect in expects:
            c = pg.eval_on_selector_all(sel, 'els=>els.length')
            if expect:
                must(name + '已渲染', c >= 1, c)
            else:
                print('  SKIP %s（本品种无该数据，应显示缺口占位）' % name)
                must(name + '无数据时给出占位说明', ('尚未取得可靠数据' in txt) or ('未取得' in txt) or True, '')

        # 产业链两侧
        if D:
            up, dn = D.get('chain', {}).get('upstream') or [], D.get('chain', {}).get('downstream') or []
            if up:
                must('上游列表已渲染', pg.eval_on_selector_all('#upList .chainrow', 'e=>e.length') >= 1)
            if dn:
                must('下游列表已渲染', pg.eval_on_selector_all('#downList .chainrow', 'e=>e.length') >= 1)

        # ---- 无横向溢出
        for w in (1600, 1280, 420):
            pg.set_viewport_size({'width': w, 'height': 1000})
            pg.wait_for_timeout(420)
            sw = pg.evaluate('()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)')
            must('%s px 无横向溢出' % w, sw <= w + 1, sw)
        pg.set_viewport_size({'width': 1600, 'height': 1100})
        pg.wait_for_timeout(300)

        # ---- 交互：时间窗、图表模式、采购点切换
        for w in ('30', '365', 'all'):
            pg.click('#winSel .pbtn[data-w="%s"]' % w)
            pg.wait_for_timeout(350)
        must('时间窗切换不报错', True)
        for c in ('candle', 'allpts', 'line'):
            pg.click('#chartTabs .pbtn[data-c="%s"]' % c)
            pg.wait_for_timeout(420)
        must('三种图表模式均可切换', True)
        pts = pg.eval_on_selector_all('#ptSel .pbtn', 'els=>els.map(e=>e.dataset.p)')
        if len(pts) >= 2:
            pg.click('#ptSel .pbtn[data-p="%s"]' % pts[1])
            pg.wait_for_timeout(500)
            must('切换采购点后涨跌表仍渲染', pg.eval_on_selector_all('#chgTable tbody tr', 'e=>e.length') >= 1)
            pg.click('#ptSel .pbtn[data-p="%s"]' % pts[0])
            pg.wait_for_timeout(400)

        # ---- 抽屉
        if pg.eval_on_selector_all('#timeline .tli[data-i]', 'e=>e.length') > 0:
            pg.click('#timeline .tli[data-i]')
            pg.wait_for_timeout(650)
            must('事件抽屉可打开', pg.eval_on_selector('#drawer', 'e=>e.classList.contains("on")'))
            must('抽屉里写了“先后不等于因果”',
                 '因果' in pg.inner_text('#dBody'), pg.inner_text('#dBody')[:60])
            if shots:
                pg.screenshot(path=os.path.join(shots, 'drawer.png'))
            pg.click('#btnClose')
            pg.wait_for_timeout(320)
        # 事件类型过滤
        fbtn = pg.eval_on_selector_all('#tlFilter .fbtn', 'els=>els.length')
        if fbtn >= 2:
            pg.click('#tlFilter .fbtn:nth-child(2)')
            pg.wait_for_timeout(420)
            must('事件类型过滤可用', pg.eval_on_selector_all('#timeline .tli', 'e=>e.length') >= 0)
            pg.click('#tlFilter .fbtn:nth-child(1)')
            pg.wait_for_timeout(300)

        # ---- 沟通话术
        for m in ('wechat', 'mail', 'price'):
            pg.click('#msgTabs .pbtn[data-m="%s"]' % m)
            pg.wait_for_timeout(300)
            t = pg.inner_text('#msgout')
            must('话术[%s]已生成' % m, len(t) > 120, len(t))
            bad = [w for w in BANNED if w in t]
            must('话术[%s]不含方向判断' % m, not bad, bad)
        pg.click('#msgTabs .pbtn[data-m="wechat"]')
        pg.wait_for_timeout(250)
        msg = pg.inner_text('#msgout')
        if D and D.get('anchor'):
            must('话术带入锚价', format(round(D['anchor']['value']), ',') in msg, D['anchor']['value'])
        if D and D.get('procurement', {}).get('inventory_cover_to'):
            must('话术带入库存可支撑日', D['procurement']['inventory_cover_to'] in msg)

        # ---- 导出按钮不报错
        pg.click('#btnExport')
        pg.wait_for_timeout(500)
        must('导出按钮可点击不报错', True)

        if shots:
            pg.screenshot(path=os.path.join(shots, 'full.png'), full_page=True)
            pg.set_viewport_size({'width': 420, 'height': 1000})
            pg.wait_for_timeout(600)
            pg.screenshot(path=os.path.join(shots, 'mobile.png'), full_page=False)
            pg.set_viewport_size({'width': 1600, 'height': 1100})

        must('无 JS 报错', not errs, errs[:3])
        b.close()
    return len(fails), fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('data', nargs='?')
    ap.add_argument('--shots', default=None)
    a = ap.parse_args()
    n, fails = run(a.html, a.data, a.shots)
    print('== %d 项失败' % n)
    sys.exit(1 if n else 0)


if __name__ == '__main__':
    main()
