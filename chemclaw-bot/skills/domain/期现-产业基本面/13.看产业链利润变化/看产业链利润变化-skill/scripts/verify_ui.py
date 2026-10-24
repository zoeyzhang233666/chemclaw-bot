# -*- coding: utf-8 -*-
"""在真实 V8 中执行 HTML 的完整应用脚本（含 DOM 桩），验证渲染与交互逻辑。

沙箱内浏览器进程无法启动（mojo/IPC 被拦），因此用 mini-racer(V8) + Python 端 DOM 桩：
  * 真实执行 app.js 的全部顶层代码（渲染 KPI/表格/图表配置/事件绑定）
  * 断言生成的 HTML 片段包含预期数值与结构
  * 模拟输入事件（修改电石价、产品价、勾选副产）并断言结果联动
  * 捕获任何参考错误 / 类型错误（若存在会在 eval 时抛出）
"""
import io
import re
import os
import sys
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from py_mini_racer import MiniRacer  # noqa: E402
import engine as E  # noqa: E402

if len(sys.argv) > 2 and sys.argv[2] == 'delegate':
    # ---- 由 V8 回调的 DOM 操作：委托给 Python ----
    op = json.loads(sys.argv[1])
    pass  # 不使用子进程回传

FAILS, OKS = [], []


def check(name, cond, detail=''):
    (OKS if cond else FAILS).append(name)
    print(('  [PASS] ' if cond else '  [FAIL] ') + name + (' ' + detail if detail else ''))


class Dom:
    """极简 DOM 桩：记录 innerHTML / 文本 / 事件。"""

    def __init__(self):
        self.html = {}
        self.value = {}
        self.checked = {}
        self.handlers = {}
        self.created = []
        self.classes = {}
        self.docs = {'#tabs button': 6}

    # ---- 与 JS 侧接口 ----
    def set_html(self, id_, v):
        self.html[id_] = v
        return v

    def dom_ready(self):
        return True


def build_js():
    html = None
    for f in os.listdir(os.path.join(ROOT, 'output')):
        if f.endswith('.html'):
            html = open(os.path.join(ROOT, 'output', f), encoding='utf-8').read()
            break
    payload = re.search(r'const PAYLOAD = (\{.*?\});\s*\n', html, re.S).group(1)
    app = re.search(r'<script id="appjs">(.*?)</script>', html, re.S).group(1)

    shim = r'''
// ===== DOM / 浏览器桩 =====
var __html = {};            // id -> innerHTML
var __vals = {};            // 输入值
var __checked = {};
var __handlers = {};        // 元素 key -> {event: fn}
var __charts = {};          // chart id -> option
var __counter = 0;

function El(tag, id, extra) {
  this.tagName = (tag||'div').toUpperCase();
  this.id = id || ('el' + (++__counter));
  this._cls = new Set();
  this.children = []; this.style = {}; this.dataset = {}; this.attributes = {};
  this._html = ''; this._text = ''; this.value = ''; this.checked = false;
  this.classList = {
    add: c => this._cls.add(c), remove: c => this._cls.delete(c),
    contains: c => this._cls.has(c), toggle: c => this._cls.has(c) ? this._cls.delete(c) : this._cls.add(c)
  };
}
Object.defineProperty(El.prototype, 'className', {
  get() { return Array.from(this._cls).join(' '); },
  set(v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
});
Object.defineProperty(El.prototype, 'innerHTML', {
  get() { return this._html; },
  set(v) { this._html = String(v); __html[this.id] = String(v); }
});
Object.defineProperty(El.prototype, 'textContent', {
  get() { return this._text; }, set(v) { this._text = String(v); }
});
Object.defineProperty(El.prototype, 'innerText', {
  get() { return this._text || String(this._html).replace(/<[^>]+>/g, ''); },
  set(v) { this._text = String(v); }
});
El.prototype.appendChild = function (c) { this.children.push(c); this._html += (c._html || ''); return c; };
El.prototype.insertAdjacentHTML = function (pos, h) { this._html += h; __html[this.id] = this._html; };
El.prototype.querySelectorAll = function (sel) {
  // 只返回内部生成的、带 data-info / data-f 的伪元素，供绑定事件
  var out = [];
  var re = /data-(info|f)="([^"]+)"/g, m;
  var src = this._html;
  while ((m = re.exec(src))) {
    var e = new El('div', this.id + '_' + m[2]);
    e.dataset[m[1]] = m[2];
    out.push(e);
  }
  return out;
};
El.prototype.querySelector = function (sel) { var a = this.querySelectorAll(sel); return a.length ? a[0] : null; };
El.prototype.addEventListener = function (ev, fn) { (__handlers[this.id] = __handlers[this.id] || {})[ev] = fn; };
El.prototype.click = function () {
  if (typeof this.onclick === 'function') this.onclick({ target: this });
  var h = __handlers[this.id];
  if (h && h.click) h.click({ target: this });
};
El.prototype.setAttribute = function (k, v) { this.attributes[k] = v; };
El.prototype.getBoundingClientRect = function () { return { width: 800, height: 330, top: 0, left: 0 }; };
El.prototype.remove = function () {};

var __els = {};
function __mk(id) { if (!__els[id]) { __els[id] = new El('div', id); } return __els[id]; }

globalThis.document = {
  getElementById: function (id) { return __mk(id); },
  querySelector: function (sel) {
    if (sel.indexOf('#inputs input') === 0 || sel.indexOf('input[data-id') >= 0) {
      var m = sel.match(/data-id="([^"]+)"/), f = sel.match(/data-f="([^"]+)"/);
      var e = new El('input', 'in_' + (m ? m[1] : 'x') + '_' + (f ? f[1] : 'x'));
      if (m) e.dataset.id = m[1]; if (f) e.dataset.f = f[1];
      return e;
    }
    if (sel.indexOf('#tbl_breakdown tbody tr') >= 0) return new El('tr', 'trow0');
    return __mk(sel.replace(/[#.\s]/g, '_'));
  },
  querySelectorAll: function (sel) {
    if (sel === '#tabs button') {
      if (!globalThis.__tabsCache) {
        globalThis.__tabsCache = [];
        for (var i = 0; i < 6; i++) {
          var b = new El('button', 'tab' + i);
          b.dataset.v = ['calc', 'history', 'cost', 'sens', 'route', 'data'][i];
          globalThis.__tabsCache.push(b);
        }
      }
      return globalThis.__tabsCache;
    }
    if (sel === '[data-preset]') {
      var a2 = [];
      ['spot', 'fut'].forEach(function (p, i) {
        var e = new El('button', 'preset' + i); e.dataset.preset = p; a2.push(e);
      });
      return a2;
    }
    if (sel.indexOf('#inputs button') >= 0 || sel.indexOf('button[data-info]') >= 0) {
      return INPUT_IDS.map(function (id) {
        var e = new El('button', 'infobtn_' + id); e.dataset.info = id; return e;
      });
    }
    if (sel.indexOf('input[data-id') >= 0) {
      var f = sel.match(/data-f="([^"]+)"/)[1];
      return INPUT_IDS.map(function (id) {
        var e = new El('input', 'in_' + id + '_' + f); e.dataset.id = id; e.dataset.f = f; return e;
      });
    }
    return [];
  },
  createElement: function (t) { return new El(t); },
  addEventListener: function () {},
  body: new El('body', 'body')
};
globalThis.window = {
  addEventListener: function () {},
  devicePixelRatio: 1
};
globalThis.Blob = function () {}; globalThis.URL = { createObjectURL: function () { return 'blob:'; } };
globalThis.echarts = {
  init: function (el) {
    return { setOption: function (o) { __charts[el.id] = o; }, resize: function () {},
             dispose: function () {} };
  },
  graphic: { LinearGradient: function () { return { colorStops: [] }; } }
};
var INPUT_IDS = __INPUT_IDS__;
'''

    js = shim.replace('__INPUT_IDS__', json.dumps([x['id'] for x in E.DEFAULT['inputs']]))
    js += '\nconst PAYLOAD = ' + payload + ';\n'
    js += app

    # 暴露内部状态
    js += r'''
globalThis.__out = {
  html: __html,
  charts: __charts,
  handlers: __handlers,
  get results() { return document.getElementById('results').innerHTML; },
  get kpis() { return document.getElementById('kpis').innerHTML; },
  get breakdown() { return document.getElementById('tbl_breakdown').innerHTML; }
};
globalThis.__computeNow = function () { return compute(); };
globalThis.__setInput = function (id, f, v) {
  var it = P.inputs.find(function (x) { return x.id === id; });
  it[f] = parseFloat(v); renderAll(false);
};
globalThis.__setProduct = function (v) { P.product.price = parseFloat(v); renderAll(false); };
globalThis.__setByp = function (on) { P.byproduct.enabled = on; renderAll(); };
globalThis.__gotoTab = function (i) { document.querySelectorAll('#tabs button')[i].click(); };
'''
    return js


def main():
    print('=== 7. 真实 V8 执行完整应用脚本（DOM 桩） ===')
    js = build_js()
    ctx = MiniRacer()
    try:
        ctx.eval(js)
        check('app.js 顶层执行无异常', True)
    except Exception as e:
        check('app.js 顶层执行无异常', False, str(e)[:400])
        print('=' * 60); print('通过 %d 失败 %d' % (len(OKS), len(FAILS))); return 1

    out = json.loads(ctx.eval('JSON.stringify({html: __out.html, charts: Object.keys(__out.charts),'
                              ' results: __out.results, kpis: __out.kpis, breakdown: __out.breakdown})'))
    results = out['results']
    kpis = out['kpis']
    brk = out['breakdown']
    r = E.compute()

    check('KPI 已渲染(6 张)', kpis.count('class="kpi ') == 6, '%d' % kpis.count('class="kpi '))
    check('KPI 含加工价差数值', ('{:,.0f}'.format(r['spread'])) in kpis, '{:,.0f}'.format(r['spread']))
    check('结果区含理论制造利润', ('{:,.0f}'.format(r['profit'])) in results, '{:,.0f}'.format(r['profit']))
    check('结果区含原料成本', ('{:,.0f}'.format(r['raw_cost'])) in results, '{:,.0f}'.format(r['raw_cost']))
    check('明细表有物料行', brk.count('<tr') >= 8, '%d 行' % brk.count('<tr'))
    check('明细表含电石计费单耗', '1.4948' in brk)
    check('图表已生成(≥2)', len(out['charts']) >= 2, ','.join(out['charts'][:6]))

    # 交互
    ctx.eval('__setInput("cac2","price",3000)')
    r2 = json.loads(ctx.eval('JSON.stringify(__computeNow())'))
    check('交互：电石价 3000 → 价差下降', r2['spread'] < r['spread'],
          '%.1f → %.1f' % (r['spread'], r2['spread']))
    manual_spread = 4865 - 3000 * 1.45 / 0.97
    check('交互结果与手算一致(±6)', abs(r2['spread'] - manual_spread) < 6,
          'JS %.1f / 手算 %.1f' % (r2['spread'], manual_spread))

    ctx.eval('__setInput("cac2","price",2530)')
    ctx.eval('__setByp(true)')
    r3 = json.loads(ctx.eval('JSON.stringify(__computeNow())'))
    check('交互：开联产烧碱 → 价差上升(抵减)', r3['spread'] > r['spread'],
          '%.1f → %.1f' % (r['spread'], r3['spread']))
    dict_ = json.loads(json.dumps(E.DEFAULT)); dict_['byproduct']['enabled'] = True
    py3 = E.compute(dict_)
    check('联产口径 JS↔PY 一致', abs(r3['profit'] - py3['profit']) < 0.02,
          'JS %.2f / PY %.2f' % (r3['profit'], py3['profit']))
    ctx.eval('__setByp(false)')

    # 各页签渲染
    for i, nm in enumerate(['calc', 'history', 'cost', 'sens', 'route', 'data']):
        try:
            ctx.eval('__gotoTab(%d)' % i)
            after = json.loads(ctx.eval('JSON.stringify({h: Object.keys(__out.html).length})'))
            ok = True
            err = ''
        except Exception as e:
            ok = False; err = str(e)[:200]
        check('切换页签 %s 渲染无异常' % nm, ok, err)

    # 历史页断言
    ctx.eval('__gotoTab(1)')
    Hd = json.load(open(os.path.join(ROOT, 'build', 'history.json'), encoding='utf-8'))
    idx = ctx.eval('document.getElementById("tbl_month").innerHTML')
    check('月度总表含 13 个月份', idx.count('<tr>') >= 13, '%d 行' % idx.count('<tr>'))
    check('月度总表显示隆众毛利', '隆众' in ctx.eval('document.getElementById("tbl_month").innerHTML'))

    print()
    print('=' * 60)
    print('通过 %d 项，失败 %d 项' % (len(OKS), len(FAILS)))
    if FAILS:
        print('失败项：', FAILS)
    print('=' * 60)
    return 0 if not FAILS else 1


if __name__ == '__main__':
    sys.exit(main())

