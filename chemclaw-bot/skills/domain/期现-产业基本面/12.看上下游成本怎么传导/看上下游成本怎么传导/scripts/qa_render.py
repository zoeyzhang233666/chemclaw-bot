# -*- coding: utf-8 -*-
"""qa_render.py —— 用 Chrome DevTools Protocol 实测 HTML

不依赖 playwright 的浏览器下载：直接连本机 Chrome/Edge 的 --remote-debugging-port。

用法：
    1) scripts/start_browser.ps1   （或手动启动 Chrome 加 --remote-debugging-port=9333）
    2) python scripts/qa_render.py out/report.html
"""
import json, os, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP

sys.stdout.reconfigure(encoding='utf-8')
PORT = os.environ.get('DSH_CDP_PORT', '9333')


def http_json(path):
    url = 'http://127.0.0.1:%s%s' % (PORT, path)
    return json.loads(urllib.request.urlopen(url, timeout=10).read().decode('utf-8'))


def main(html_path, shot_dir=None):
    try:
        tabs = http_json('/json/list')
    except Exception as e:
        print('无法连接调试端口 %s：%s' % (PORT, e))
        print('请先启动带 --remote-debugging-port=%s 的 Chrome' % PORT)
        return 2
    pages = [t for t in tabs if t.get('type') == 'page']
    if not pages:
        print('没有可用的页面目标')
        return 2
    c = CDP(pages[0]['webSocketDebuggerUrl'])
    c.send('Runtime.enable')
    c.send('Page.enable')
    c.send('Log.enable')

    path = 'file:///' + os.path.abspath(html_path).replace('\\', '/')
    c.send('Page.navigate', url=path)
    time.sleep(2.5)

    errs = c.eval('JSON.stringify(window.__errs || [])')
    js_err = c.eval("""(() => {
        try {
            return JSON.stringify({
                title: document.title,
                sections: document.querySelectorAll('section').length,
                navBtns: document.querySelectorAll('nav button').length,
                canvases: Array.from(document.querySelectorAll('canvas')).map(c=>[c.width,c.height]),
                dataOk: !!window.D && Array.isArray(D.dates),
                n: window.D ? D.dates.length : 0
            });
        } catch(e) { return JSON.stringify({error: String(e)}); }
    })()""")
    info = json.loads(js_err)
    fails, warns = [], []

    print('标题：', info.get('title'))
    print('分页 %s 个，分页按钮 %s 个' % (info.get('sections'), info.get('navBtns')))
    if not info.get('dataOk'):
        fails.append('数据对象 D 未定义')
    else:
        print('数据点：', info.get('n'))

    # 逐页点击并检查渲染
    for idx in range(int(info.get('navBtns') or 0)):
        r = c.eval("""(() => {
            var b = document.querySelectorAll('nav button')[%d];
            if(!b) return 'no-btn';
            b.click();
            return 'ok';
        })()""" % idx)
        time.sleep(0.55)
        chk = json.loads(c.eval("""(() => {
            var s = document.querySelector('section.on');
            if(!s) return JSON.stringify({bad:'无可见分页'});
            var cv = Array.from(s.querySelectorAll('canvas')).map(function(c){return [c.width,c.height];});
            return JSON.stringify({txt: (s.innerText||'').length, canvases: cv,
                                   charts: s.querySelectorAll('[id^=c-]').length});
        })()"""))
        ch = chk.get('canvases') or []
        if chk.get('bad'):
            fails.append('分页 %d：%s' % (idx, chk['bad']))
        if (chk.get('txt') or 0) < 120:
            fails.append('分页 %d 文字过少（%s 字）' % (idx, chk.get('txt')))
        for cc in ch:
            if cc[0] < 50 or cc[1] < 50:
                fails.append('分页 %d 图表画布异常 %s' % (idx, cc))
        print('  分页 %d：文字 %s 字，画布 %s' % (idx, chk.get('txt'), ch))

    # 单耗滑块
    try:
        c.eval("document.querySelectorAll('nav button')[3].click()")
        time.sleep(0.6)
        before = c.eval("document.getElementById('v-unit').textContent")
        c.eval("""(()=>{var s=document.getElementById('s-unit');
            s.value=s.min; s.dispatchEvent(new Event('input'));})()""")
        time.sleep(0.7)
        after = c.eval("document.getElementById('v-unit').textContent")
        if before == after:
            fails.append('单耗滑块无效（%s → %s）' % (before, after))
        else:
            print('单耗滑块：%s → %s ✓' % (before, after))
    except Exception as e:
        warns.append('滑块测试跳过：%s' % str(e)[:80])

    # 截图
    shot_dir = shot_dir or os.path.dirname(os.path.abspath(html_path))
    try:
        c.eval("document.querySelectorAll('nav button')[0].click()")
        time.sleep(0.7)
        sh = c.send('Page.captureScreenshot', format='png')
        import base64
        p1 = os.path.join(shot_dir, '_preview_overview.png')
        open(p1, 'wb').write(base64.b64decode(sh['data']))
        print('截图：', p1)
        c.eval("document.querySelectorAll('nav button')[3].click()")
        time.sleep(0.8)
        sh = c.send('Page.captureScreenshot', format='png')
        p2 = os.path.join(shot_dir, '_preview_cost.png')
        open(p2, 'wb').write(base64.b64decode(sh['data']))
        print('截图：', p2)
    except Exception as e:
        warns.append('截图失败：%s' % str(e)[:80])

    for w in warns:
        print('  [warn]', w)
    if fails:
        for x in fails:
            print('  [FAIL]', x)
        print('\n浏览器实测失败：%d 项' % len(fails))
        return 1
    print('\n浏览器实测全部通过')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法：python qa_render.py <report.html>')
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
