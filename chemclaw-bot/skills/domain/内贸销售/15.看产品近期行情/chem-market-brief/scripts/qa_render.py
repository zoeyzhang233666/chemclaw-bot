# -*- coding: utf-8 -*-
"""浏览器渲染自检（可选，需要 playwright）：抓 JS 报错、检查各模块是否真的渲染出内容、点选与抽屉是否可用。

用法：
  python qa_render.py out.html [data.json]
  python qa_render.py out.html --shots shots/
没装 playwright 时自动跳过并返回 0（静态检查仍有效）。
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


def run(html_path, data_path=None, shots=None):
    if not HAS_PW:
        print('[SKIP ] 未安装 playwright，跳过渲染检查（静态检查仍有效）')
        return 0, []

    with open(html_path, encoding='utf-8') as f:
        html = f.read()
    D = json.load(open(data_path, encoding='utf-8')) if data_path and os.path.exists(data_path) else None

    url = 'file:///' + os.path.abspath(html_path).replace('\\', '/')
    fails, errs = [], []
    if shots:
        os.makedirs(shots, exist_ok=True)

    with sync_playwright() as pw:
        b = pw.chromium.launch(args=['--no-sandbox'])
        pg = b.new_page(viewport={'width': 1600, 'height': 1100})
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console.' + m.type + ': ' + m.text) if m.type == 'error' else None)
        pg.goto(url, wait_until='load', timeout=60000)
        pg.wait_for_timeout(2600)

        def must(name, cond, detail=''):
            if cond:
                print('  PASS', name)
            else:
                print('  FAIL', name, detail)
                fails.append(name + ' ' + str(detail))

        # KPI 4 张卡
        n = pg.eval_on_selector_all('#kpiGrid .card', 'els=>els.length')
        must('KPI 卡片 = 4', n == 4, n)
        vals = pg.eval_on_selector_all('#kpiGrid .card .val', 'els=>els.map(e=>e.textContent.trim())')
        must('KPI 有数字或明确缺口', all(v and ('—' not in v) for v in vals), vals)

        # 首屏有价格
        txt = pg.inner_text('body')
        must('页面非空白', len(txt) > 1200, len(txt))
        if D and D.get('anchor'):
            must('现货锚数字出现在页面', format(round(D['anchor']['value']), ',') in txt.replace(' ', ''),
                 D['anchor']['value'])
        if D and D.get('last', {}).get('close') is not None:
            must('期货收盘出现在页面', format(round(D['last']['close']), ',') in txt.replace(' ', ''),
                 D['last']['close'])

        # 图表真的画了（无序列时应显示缺口而不是空白）
        has_series = bool(D and (D.get('series') or {}).get('1y'))
        painted = pg.evaluate("""() => {const c=document.querySelectorAll('canvas')[0];
            if(!c) return -1; const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            let n=0; for(let i=3;i<d.length;i+=4*29){ if(d[i]>8) n++; } return n;}""")
        if has_series:
            must('主图已绘制像素', isinstance(painted, int) and painted > 200, painted)
        else:
            must('无序列时主图显示缺口', pg.eval_on_selector_all('#chart .empty', 'e=>e.length') >= 1, painted)
            print('  SKIP 主图已绘制像素（无价格序列）')

        # 各模块非空；无数据时必须显示缺口占位
        has_ev = bool(D and ((D.get('events') or []) or (D.get('anomalies') or [])))
        has_win = bool(D and (D.get('win') or {}).get('1y'))
        expects = [('#spotTable tbody tr', '现货表', bool(D and D.get('spots'))),
                   ('#chgTable tbody tr', '涨跌表', bool(D and D.get('chg'))),
                   ('#timeline .tli', '时间线', has_ev),
                   ('#gapGrid .mcard', '缺口卡', bool(D and D.get('gaps'))),
                   ('#srcList a', '来源清单', bool(D and D.get('sources'))),
                   ('#quantWrap .qbar', '分位条', has_win),
                   ('#balBody tr', '供需表', bool(D and D.get('balance')))]
        empty_sel = {'时间线': '#timeline .empty', '分位条': '#quantWrap .empty',
                     '供需表': '#balBody .empty, #balBody td .empty'}
        for sel, name, expect in expects:
            c = pg.eval_on_selector_all(sel, 'els=>els.length')
            if expect:
                must(name + '已渲染', c >= 1, c)
            else:
                alt = empty_sel.get(name)
                shown = (pg.eval_on_selector_all(alt, 'e=>e.length') >= 1) if alt else True
                must(name + '无数据时显示缺口', shown, c)
                print('  SKIP %s已渲染（本品种无该数据）' % name)

        # 无横向溢出（桌面 / 移动）
        for w, label in [(1600, '1600'), (1280, '1280'), (420, '420')]:
            pg.set_viewport_size({'width': w, 'height': 1000})
            pg.wait_for_timeout(400)
            sw = pg.evaluate('()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)')
            must('%s px 无横向溢出' % label, sw <= w + 1, sw)
        pg.set_viewport_size({'width': 1600, 'height': 1100})
        pg.wait_for_timeout(300)

        # 切窗口
        pg.click('#winSel .pbtn[data-w="3y"]')
        pg.wait_for_timeout(800)
        must('切 3 年到不报错', True)

        # 抽屉
        if pg.eval_on_selector_all('#timeline .tli[data-d]', 'els=>els.length') > 0:
            pg.click('#timeline .tli[data-d]')
            pg.wait_for_timeout(700)
            opened = pg.eval_on_selector('#drawer', 'e=>e.classList.contains("on")')
            must('事件抽屉可打开', opened)
            if shots:
                pg.screenshot(path=os.path.join(shots, 'drawer.png'))
            pg.click('#btnClose')
            pg.wait_for_timeout(400)

        # 现货行抽屉
        if pg.eval_on_selector_all('#spotTable tbody tr', 'els=>els.length') > 0:
            pg.click('#spotTable tbody tr')
            pg.wait_for_timeout(600)
            must('现货行抽屉可打开', pg.eval_on_selector('#drawer', 'e=>e.classList.contains("on")'))
            pg.click('#btnClose')
            pg.wait_for_timeout(300)

        # 话术生成
        pg.click('#btnGen')
        pg.wait_for_timeout(500)
        msg = pg.input_value('#msgout')
        must('话术已生成', len(msg) > 120, len(msg))
        bad = [w for w in ('预计涨', '预计跌', '看涨', '看跌', '抄底', '必涨', '必跌') if w in msg]
        must('话术不含方向判断', not bad, bad)
        if D and D.get('anchor'):
            must('话术带入现货价', format(round(D['anchor']['value']), ',') in msg, D['anchor']['value'])
        # 有毛利数据时，话术的成本行必须真的带入路线名（防“品种写死”类回归）
        route = None
        for m in reversed((D or {}).get('margins') or []):
            ks = list((m.get('routes') or {}).keys())
            if ks:
                route = ks[0]
                break
        if route:
            must('话术带入毛利路线「%s」' % route, route in msg, route)
        if D and D.get('balance'):
            must('话术带入供需数字', str(D['balance'][0].get('k'))[:6] in msg, D['balance'][0].get('k'))

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
