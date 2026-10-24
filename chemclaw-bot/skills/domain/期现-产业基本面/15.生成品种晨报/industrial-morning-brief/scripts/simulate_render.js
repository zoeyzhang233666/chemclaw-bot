// DOM 模拟渲染测试：在 Node 中执行晨报脚本，验证渲染结果与交互逻辑。
// 用法：node simulate_render.js <brief.html>
const fs = require('fs');

const html = fs.readFileSync(process.argv[2], 'utf8');
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const biz = blocks[blocks.length - 1];

// ---------------- 极简 DOM ----------------
class El {
  constructor(tag, attrs = {}) {
    this.tagName = (tag || 'div').toUpperCase();
    this.attrs = attrs;
    this.children = [];
    this._html = '';
    this._text = '';
    this.dataset = {};
    this.style = {};
    this.classList = {
      _s: new Set((attrs.class || '').split(/\s+/).filter(Boolean)),
      add(...c) { c.forEach(x => this._s.add(x)); },
      remove(...c) { c.forEach(x => this._s.delete(x)); },
      toggle(c) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); },
      contains(c) { return this._s.has(c); },
    };
    this.scrollTop = 0;
    this.listeners = {};
  }
  set innerHTML(v) { this._html = String(v); }
  get innerHTML() { return this._html; }
  set textContent(v) { this._text = String(v); this._html = String(v); }
  get textContent() { return this._text || this._html.replace(/<[^>]*>/g, ''); }
  appendChild(c) { this.children.push(c); }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  click() { (this.listeners.click || []).forEach(f => f({ target: this, closest: () => null })); }
  scrollIntoView() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
  getContext() { return { getImageData: () => ({ data: [] }) }; }
  get offsetWidth() { return 800; }
}

// 从已生成的 HTML 中解析出真实存在的元素 id / class，作为选择器命中依据
const ids = new Set([...html.matchAll(/id="([^"]+)"/g)].map(m => m[1]));
const store = {};
const make = sel => {
  if (!store[sel]) {
    const id = sel.replace(/^#/, '');
    store[sel] = new El('div', { id: ids.has(id) ? id : '' });
    if (sel.startsWith('#dr') || sel.startsWith('#mask')) store[sel].classList.remove('on');
  }
  return store[sel];
};

const document = {
  querySelector: sel => (ids.has(sel.replace(/^#/, '')) || sel.startsWith('.') ? make(sel) : null),
  getElementById: id => (ids.has(id) || /^ch-/.test(id) ? make('#' + id) : null),
  querySelectorAll: sel => {
    // 页面里存在该 class / 属性的静态节点数量（用于计数校验）
    if (sel.startsWith('.')) return [];
    return [];
  },
  addEventListener: () => {},
  documentElement: { scrollWidth: 1200 },
};

const charts = [];
const echarts = {
  init: () => ({
    setOption: opt => charts.push(opt),
    dispose: () => {},
  }),
};
const window = { innerWidth: 1440 };
const console_ = console;

// ---------------- 执行 ----------------
let out;
try {
  const fn = new Function('document', 'echarts', 'window', 'console', biz + '\nreturn {D, buildPanels};');
  out = fn(document, echarts, window, console_);
} catch (e) {
  console.error('SCRIPT ERROR:', e.message, '\n', e.stack.split('\n').slice(0, 6).join('\n'));
  process.exit(1);
}

const D = out.D;
let fails = [], warns = [];
const chk = (cond, msg) => { if (!cond) fails.push(msg); };

// 1 摘要卡
const cardsHTML = store['#cards'] ? store['#cards'].innerHTML : '';
const nCards = (cardsHTML.match(/class="card /g) || []).length;
chk(nCards === 3, `摘要卡数量 ${nCards} != 3`);

// 2 面板与模块
const panelsHTML = store['#panels'] ? store['#panels'].innerHTML : '';
const nPanels = (panelsHTML.match(/class="panel open" data-product=/g) || []).length;
chk(nPanels === 3, `品种面板数量 ${nPanels} != 3`);
for (const t of ['价格与价差', '基差与月差', '装置与产能', '库存与需求', '政策与事件']) {
  const c = (panelsHTML.match(new RegExp(t, 'g')) || []).length;
  chk(c >= 3, `模块「${t}」出现 ${c} 次（每个品种应有 1 次）`);
}

// 3 图表 option
chk(charts.length >= 4, `图表数量 ${charts.length} < 4（3 品种 K 线 + 基差）`);
const kOpt = charts.find(o => o.series && o.series[0] && o.series[0].type === 'candlestick');
chk(!!kOpt, '缺少 K 线图 option');
if (kOpt) {
  chk(kOpt.series[0].data.length > 50, `K 线数据点 ${kOpt.series[0].data.length} 过少`);
}
const bOpt = charts.find(o => o.series && o.series[0] && o.series[0].type === 'line');
chk(!!bOpt, '缺少基差折线 option');

// 4 数字与 data.json 一致（抽查）
const ma = D.indicators.find(i => i.id === 'MA-basis');
chk(ma && Math.abs(ma.current - 822) < 0.01, `甲醇基差应为 822，实际 ${ma && ma.current}`);
chk(ma && Math.abs(ma.abs - 204) < 0.01, `甲醇基差变动应为 +204，实际 ${ma && ma.abs}`);
const vrun = D.indicators.find(i => i.id === 'V-run');
chk(vrun && Math.abs(vrun.abs + 2.99) < 0.01, `PVC 开工变动应为 -2.99，实际 ${vrun && vrun.abs}`);
const pbase = D.indicators.find(i => i.id === 'PP-basis');
chk(pbase && pbase.tier === 'C', `PP 基差变动 23 元应判为 C，实际 ${pbase && pbase.tier}`);

// 5 事件分级
const aEv = D.events.filter(e => e.tier === 'A').length;
const cEv = D.events.filter(e => e.tier === 'C').length;
chk(aEv >= 8, `A 级事件 ${aEv} 条偏少`);
chk(cEv >= 2, `C 级（噪声）事件 ${cEv} 条偏少，筛选可能失效`);

// 6 抽屉内容
try {
  const fnOpen = new Function('document', 'echarts', 'window', 'console',
    biz + '\nopenInd("MA-basis"); return {title: document.querySelector("#drTitle").textContent, body: document.querySelector("#drBody").innerHTML};');
  const r = fnOpen(document, echarts, window, console);
  for (const k of ['发生了什么', '数据如何变化', '为什么值得关注', '今天继续验证什么', '来源']) {
    chk(r.body.includes(k), `抽屉缺少「${k}」`);
  }
  chk(r.body.includes('822'), '抽屉未显示本期值 822');
  chk(r.body.includes('594'), '抽屉未显示上期值 594');
} catch (e) {
  fails.push('抽屉渲染异常：' + e.message);
}

// 7 陈旧标注
const maInv = D.indicators.find(i => i.id === 'MA-inv');
chk(maInv && maInv.stale_days >= 2, `周度库存应标注陈旧，实际 stale_days=${maInv && maInv.stale_days}`);

// 8 排除与缺口
chk(D.excluded.length >= 5, `排除记录 ${D.excluded.length} 条偏少`);
chk(D.gaps.length >= 5, `缺口 ${D.gaps.length} 条偏少`);

console.log('--- 渲染模拟结果 ---');
console.log(`摘要卡 ${nCards} 张 | 面板 ${nPanels} 个 | 图表 ${charts.length} 张 | 事件 A${aEv}/C${cEv}`);
console.log(`HTML 片段长度：cards=${cardsHTML.length} panels=${panelsHTML.length}`);
warns.forEach(w => console.log('[WARN ] ' + w));
if (fails.length) {
  fails.forEach(f => console.log('[FAIL ] ' + f));
  console.log(`FAILED (${fails.length})`);
  process.exit(1);
}
console.log('ALL PASS');
