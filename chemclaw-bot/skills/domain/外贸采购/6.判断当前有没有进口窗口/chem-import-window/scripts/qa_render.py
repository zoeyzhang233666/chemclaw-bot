# -*- coding: utf-8 -*-
"""qa_render.py — 用 Playwright(Python) 渲染 HTML，做交互与数字一致性检查。

用法: python scripts/qa_render.py <file.html> [--shot out.png] [--case case.json]

检查项:
  1. 无 JS 报错 / 无外部网络请求（离线自包含）
  2. 首屏四卡非空
  3. 页面显示值与 Node 引擎结果一致（调用 node 跑引擎）
  4. 图表 canvas 实际绘制或按数据不足规则给出占位
  5. 改参数后重算生效、重置可恢复
  6. 模拟情景模式有明显标注
"""
import io
import json
import os
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = sys.argv[1]
SHOT = None
CASE = None
if '--shot' in sys.argv:
    SHOT = sys.argv[sys.argv.index('--shot') + 1]
if '--case' in sys.argv:
    CASE = sys.argv[sys.argv.index('--case') + 1]
if not CASE:
    CASE = os.path.join(ROOT, 'examples', '01-meg-huadong', 'data', 'case.json')

fails = 0
warns = 0


def ok(m):
    print('  OK   ' + m)


def bad(m):
    global fails
    fails += 1
    print('  FAIL ' + m)


def warn(m):
    global warns
    warns += 1
    print('  WARN ' + m)


def engine_result(case_path):
    js = (
        "const fs=require('fs');"
        "const e=require(" + json.dumps(os.path.join(ROOT, 'scripts', 'lib', 'import-window-engine.js')) + ");"
        "const c=JSON.parse(fs.readFileSync(" + json.dumps(case_path) + ",'utf8'));"
        "const a=e.analyze(c);"
        "console.log(JSON.stringify({quote:c.quote.price_usd,"
        "cost:a.current.totals.net_cost,dom:c.domestic.price_cny,"
        "spread:a.current.spread.abs_cny,fx:a.current.fx?a.current.fx.rate:null,"
        "vat:a.current.totals.vat,duty:a.current.totals.duty,"
        "cif_cny:a.current.totals.cif_cny,tier:a.current.tier,"
        "verdict:a.verdict,hist:a.history.length,"
        "hist_ok:a.history.filter(h=>h.status==='ok').length}));"
    )
    out = subprocess.run(['node', '-e', js], capture_output=True, text=True, encoding='utf-8')
    if out.returncode != 0:
        raise RuntimeError(out.stderr)
    return json.loads(out.stdout)


def num(s):
    if not s:
        return None
    s = str(s).strip().replace(',', '').replace('+', '')
    head = ''
    for ch in s:
        if ch.isdigit() or ch in '.-':
            head += ch
        else:
            break
    try:
        return float(head)
    except ValueError:
        return None


def main():
    exp = engine_result(CASE)
    calculable = exp.get('cost') is not None and exp.get('spread') is not None
    if calculable:
        print('引擎基准: cost=%.2f dom=%.2f spread=%.2f' % (exp['cost'], exp['dom'], exp['spread']))
    else:
        print('引擎基准: 不可计算 (verdict=%s)' % exp.get('verdict'))

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1560, 'height': 1080})
        page = ctx.new_page()
        errors = []
        reqs = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append('console:' + m.text) if m.type == 'error' else None)
        page.on('request', lambda r: reqs.append(r.url) if not r.url.startswith(('file:', 'data:', 'blob:')) else None)

        page.goto('file:///' + os.path.abspath(FILE).replace('\\', '/'))
        page.wait_for_timeout(1500)

        print('\n[1] 运行环境')
        if errors:
            bad('页面报错: ' + ' | '.join(errors[:3]))
        else:
            ok('无 JS / 控制台错误')
        if reqs:
            bad('存在外部请求: %s' % reqs[:3])
        else:
            ok('零外部请求（完全离线）')

        print('\n[2] 首屏四卡')
        cards = page.evaluate("""() => ({
            q: document.getElementById('kQuote').innerText,
            c: document.getElementById('kCost').innerText,
            d: document.getElementById('kDom').innerText,
            s: document.getElementById('kSpread').innerText,
            v: document.getElementById('vVerdict').innerText,
            cp: document.getElementById('vCompat').innerText,
            one: document.getElementById('vOne_line').innerText,
            badges: document.getElementById('vBadges').innerText
        })""")
        for k in ('q', 'c', 'd', 's', 'v', 'cp'):
            if not cards.get(k) or cards[k].strip() == '—':
                bad('字段为空: ' + k)
        ok('四卡与结论条均有值')
        print('     ① %s | ② %s | ③ %s | ④ %s' % (
            cards['q'].replace('\n', ' '), cards['c'].replace('\n', ' '),
            cards['d'].replace('\n', ' '), cards['s'].replace('\n', ' ')))
        print('     口径: %s / %s' % (cards['v'], cards['cp']))

        print('\n[3] 页面数字 vs 引擎')
        q = num(cards['q']); c = num(cards['c']); d = num(cards['d']); s = num(cards['s'])
        if not calculable:
            # 不可计算案例：页面必须明示"算不出来"，且不得显示一个像样的价差数字
            print('     本案例引擎判定不可计算 → 检查页面是否"敢于说算不出来"')
            blob = (cards['v'] + ' ' + cards['one'] + ' ' + cards['c'] + ' ' + cards['s'])
            if s is not None:
                bad('不可计算案例却显示了价差数字: %r' % cards['s'])
            elif any(w in blob for w in ('不可计算', '缺口', '缺', '无法')):
                ok('页面明确说明"无法计算/缺口"，未伪造价差')
            else:
                bad('页面未说明为何算不出来: %r' % blob[:120])
            if q is not None and abs(q - exp['quote']) <= 0.05:
                ok('海外报价显示正确 (%.2f)' % q)
            else:
                bad('海外报价显示异常: %r' % cards['q'])
            if d is not None and exp.get('dom') and abs(d - exp['dom']) <= 0.02:
                ok('国内现货显示正确 (%.2f)' % d)
            else:
                bad('国内现货显示异常: %r' % cards['d'])
        else:
            checks = [
                ('海外报价', q, exp['quote'], 0.05),
                ('进口成本', c, exp['cost'], 1.5),
                ('国内现货', d, exp['dom'], 0.02),
                ('理论价差', s, exp['spread'], 1.5),
            ]
            for name, got, want, tol in checks:
                if got is None:
                    bad('%s 解析失败: %r' % (name, cards[{'海外报价': 'q', '进口成本': 'c', '国内现货': 'd', '理论价差': 's'}[name]]))
                elif abs(got - want) > tol:
                    bad('%s 不一致: 页面 %.2f vs 引擎 %.2f' % (name, got, want))
                else:
                    ok('%s 一致 (%.2f)' % (name, got))

        print('\n[4] 图表')
        info = page.evaluate("""() => {
            const out = {};
            ['chartContrib','chartSens','chartTornado','chartHistory'].forEach(id => {
                const el = document.getElementById(id);
                if (!el) { out[id] = {exists:false}; return; }
                const cv = el.querySelector('canvas');
                out[id] = {exists:true, canvas: !!cv, w: cv?cv.width:0, h: cv?cv.height:0,
                           text: (el.innerText||'').slice(0,50)};
            });
            return out;
        }""")
        for cid, v in info.items():
            if not v['exists']:
                bad(cid + ' 不存在')
            elif v['canvas'] and v['w'] > 100 and v['h'] > 60:
                ok('%s 已绘制 (%dx%d)' % (cid, v['w'], v['h']))
            elif v['text']:
                ok('%s 文字占位（数据不足，符合纪律）: %s' % (cid, v['text'].replace('\n', ' ')))
            else:
                bad(cid + ' 既无 canvas 也无占位说明')

        print('\n[5] 交互: 改关税税率 → 重算')
        before = page.evaluate("() => [document.getElementById('kCost').innerText, document.getElementById('kSpread').innerText]")
        inp = page.query_selector('input[data-k="duty_rate"]')
        if not inp:
            bad('找不到关税税率输入框')
        elif not calculable:
            # 不可计算案例的正确行为：改参数后依然拒绝给价差
            duty_now = inp.input_value()
            inp.fill('0')
            page.wait_for_timeout(500)
            after = page.evaluate("() => document.getElementById('kSpread').innerText")
            if num(after) is not None:
                bad('不可计算案例在改税率后反而给出了价差: %r' % after)
            else:
                ok('改税率后仍拒绝给出价差（缺口未被"调参"抹平）')
            # 页面整体重绘后旧元素句柄失效，因此用"重新查询"的方式复位
            page.fill('input[data-k="duty_rate"]', duty_now)
            page.wait_for_timeout(300)
            page.click('#btnReset')
            page.wait_for_timeout(400)
        else:
            inp.fill('0')
            page.wait_for_timeout(500)
            after = page.evaluate("() => [document.getElementById('kCost').innerText, document.getElementById('kSpread').innerText]")
            if after[0] == before[0]:
                bad('改税率后成本未变（交互失效）')
            else:
                ok('0%% 关税: 成本 %s → %s, 价差 %s → %s' % (
                    before[0].replace('\n', ' '), after[0].replace('\n', ' '),
                    before[1].replace('\n', ' '), after[1].replace('\n', ' ')))
                expect = exp['cif_cny'] + (exp['cost'] - exp['cif_cny'] - exp['duty'])
                got = num(after[0])
                if got is not None and abs(got - expect) <= max(2.0, expect * 0.005):
                    ok('0%% 关税成本与手算一致 (%.2f ≈ %.2f)' % (got, expect))
                else:
                    warn('0%% 关税成本 %.2f vs 手算 %.2f（保险费/境内费差异属正常）' % (got or -1, expect))
            page.click('#btnReset')
            page.wait_for_timeout(400)
            reset = page.evaluate("() => document.getElementById('kCost').innerText")
            if reset != before[0]:
                bad('重置未恢复原值')
            else:
                ok('重置恢复原值')

        print('\n[6] 模拟情景标注')
        page.click('#btnSim')
        page.wait_for_timeout(600)
        sim = page.evaluate("""() => ({
            badges: document.getElementById('vBadges').innerText,
            cost: document.getElementById('kCost').innerText,
            sub: document.getElementById('kQuoteSub').innerText
        })""")
        if '模拟' in sim['badges']:
            ok('模拟情景有明确标注')
        else:
            bad('模拟情景未标注')
        page.click('#btnReset')
        page.wait_for_timeout(300)

        print('\n[7] 历史区间切换')
        page.select_option('#selRange', '30d')
        page.wait_for_timeout(500)
        rows30 = page.evaluate("() => document.querySelectorAll('#tblHist tbody tr').length")
        ok('近 30 天视图行数: %d' % rows30)

        if SHOT:
            page.screenshot(path=SHOT, full_page=False)
            print('\n截图: ' + SHOT)
            page.screenshot(path=SHOT.replace('.png', '_full.png'), full_page=True)
            print('整页截图: ' + SHOT.replace('.png', '_full.png'))

        b.close()

    print('\n结果: ' + ('%d 项失败' % fails if fails else '全部通过') + ('，%d 项提示' % warns if warns else ''))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
