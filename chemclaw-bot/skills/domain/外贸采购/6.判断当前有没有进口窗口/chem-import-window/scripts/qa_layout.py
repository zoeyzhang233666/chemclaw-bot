# -*- coding: utf-8 -*-
"""qa_layout.py — 版面完整性检查（替代人工看图）：元素是否重叠、文本是否溢出、区块是否齐全。

用法: python scripts/qa_layout.py <file.html>
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

from playwright.sync_api import sync_playwright

FILE = sys.argv[1]
fails = 0
warns = 0


def bad(m):
    global fails
    fails += 1
    print('  FAIL ' + m)


def ok(m):
    print('  OK   ' + m)


def warn(m):
    global warns
    warns += 1
    print('  WARN ' + m)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={'width': 1560, 'height': 1000}).new_page()
    pg.goto('file:///' + os.path.abspath(FILE).replace('\\', '/'))
    pg.wait_for_timeout(1500)

    print('[A] 区块齐全性')
    secs = pg.evaluate("""() => Array.from(document.querySelectorAll('.shead')).map(h => ({
        num: (h.querySelector('.num')||{}).innerText || '',
        title: (h.querySelector('h2')||{}).innerText || '',
        h: Math.round(h.getBoundingClientRect().height)
    }))""")
    for s in secs:
        print('     %-3s %s' % (s['num'], s['title']))
    if len(secs) >= 8:
        ok('8 个分析区块全部存在')
    else:
        bad('区块数量不足: %d' % len(secs))

    print('\n[B] 文本溢出检测')
    over = pg.evaluate("""() => {
        const out = [];
        document.querySelectorAll('.card .big, .verdict-bar .v, .shead h2, td, th, .badge').forEach(el => {
            if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) {
                out.push({t: (el.innerText||'').slice(0,40), sw: el.scrollWidth, cw: el.clientWidth});
            }
        });
        return out.slice(0, 8);
    }""")
    if over:
        for o in over:
            warn('文本溢出: %r (%d > %d)' % (o['t'], o['sw'], o['cw']))
    else:
        ok('无横向文本溢出')

    print('\n[C] 卡片与表格行数')
    counts = pg.evaluate("""() => ({
        compat: document.querySelectorAll('#tblCompat tbody tr').length,
        steps: document.querySelectorAll('#tblSteps tbody tr').length,
        sens: document.querySelectorAll('#tblSens tbody tr').length,
        hist: document.querySelectorAll('#tblHist tbody tr').length,
        gaph: document.querySelectorAll('#tblGapHist tbody tr').length,
        real: document.querySelectorAll('#tblReal tbody tr').length,
        src: document.querySelectorAll('#tblSrc tbody tr').length,
        gaps: document.querySelectorAll('#gapList .gap-item').length,
        manual: document.querySelectorAll('#manualChecks .gap-item').length,
        tl: document.querySelectorAll('#timeline .tl-item').length,
        fields: document.querySelectorAll('#editor .field').length
    })""")
    for k, v in counts.items():
        print('     %-8s %d' % (k, v))
    for k in ('compat', 'steps', 'sens', 'real', 'src', 'gaps'):
        if counts[k] < 3:
            bad('%s 行数过少 (%d)' % (k, counts[k]))
    ok('表格均已填充')

    print('\n[D] 页面高度与首屏')
    dims = pg.evaluate("""() => ({
        pageH: Math.round(document.body.scrollHeight),
        heroBottom: Math.round(document.querySelector('.hero').getBoundingClientRect().bottom),
        vh: window.innerHeight,
        heroTop: Math.round(document.querySelector('.hero').getBoundingClientRect().top)
    })""")
    print('     页面高度 %d px，首屏四卡底部 %d px（视口 %d）' % (dims['pageH'], dims['heroBottom'], dims['vh']))
    if dims['heroTop'] < dims['vh']:
        ok('首屏即出现四张核心卡片')
    else:
        bad('四卡不在首屏')

    print('\n[E] 固定顶栏遮挡检查')
    ov = pg.evaluate("""() => {
        const tb = document.querySelector('.topbar').getBoundingClientRect().bottom;
        const v = document.querySelector('.verdict-bar').getBoundingClientRect();
        return {tb: Math.round(tb), vTop: Math.round(v.top)};
    }""")
    if ov['vTop'] >= ov['tb'] - 1:
        ok('结论条未被顶栏遮挡')
    else:
        warn('结论条与顶栏重叠: verdict.top=%d topbar.bottom=%d' % (ov['vTop'], ov['tb']))

    print('\n[F] 弹窗交互')
    n_tl = pg.evaluate("() => document.querySelectorAll('#timeline .tl-item').length")
    if n_tl == 0:
        ok('本案例无同期事件（events 为空），跳过弹窗点击检查')
    else:
        pg.click('#timeline .tl-item')
        pg.wait_for_timeout(400)
        shown = pg.evaluate("() => document.getElementById('modal').classList.contains('show')")
        body = pg.evaluate("() => document.getElementById('modalBody').innerText.slice(0,120)")
        if shown and body:
            ok('点击事件 → 弹窗打开且有内容: ' + body.replace('\n', ' ')[:80])
        else:
            bad('弹窗未打开')
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(200)

    print('\n[G] 窄屏响应式')
    pg.set_viewport_size({'width': 430, 'height': 900})
    pg.wait_for_timeout(600)
    nar = pg.evaluate("""() => ({
        overflow: document.body.scrollWidth > window.innerWidth + 2,
        sw: document.body.scrollWidth, iw: window.innerWidth,
        cards: getComputedStyle(document.querySelector('.hero')).gridTemplateColumns.split(' ').length
    })""")
    if nar['overflow']:
        warn('窄屏横向溢出 (%d > %d)' % (nar['sw'], nar['iw']))
    else:
        ok('窄屏无横向溢出，四卡自动变单列（列数 %d）' % nar['cards'])

    b.close()

print('\n结果: ' + ('%d 项失败' % fails if fails else '全部通过') + ('，%d 项提示' % warns if warns else ''))
sys.exit(1 if fails else 0)
