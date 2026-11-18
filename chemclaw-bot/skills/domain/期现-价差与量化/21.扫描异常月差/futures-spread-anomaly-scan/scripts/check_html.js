// 用伪 DOM 真实执行看板脚本，验证渲染逻辑（不只看语法）
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2] || 'build/dashboard.html';
const html = fs.readFileSync(file, 'utf8');
console.log('checking', file);
const js = html.match(/<script>([\s\S]*?)<\/script>/)[1];

// ---- 极简 DOM 桩 ----
function mkEl(tag, id) {
  const el = {
    tagName: tag, id: id || '', _html: '', textContent: '', value: '',
    clientWidth: 800, height: 300, width: 800, selectedOptions: [], children: [],
    style: {}, dataset: {},
    classList: { add() {}, remove() {}, contains() { return false; } },
    appendChild(c) { c.text = c.textContent || c.value || 'opt'; c.selected = true; this.children.push(c); if (this.tagName === 'SELECT') this.selectedOptions.push(c); return c; },
    getContext() {
      return new Proxy({}, { get: (t, k) => (k in t ? t[k] : () => {}) });
    },
    querySelector() { return mkEl('div'); },
    querySelectorAll() { return []; },
    addEventListener() {}, remove() {},
  };
  Object.defineProperty(el, 'innerHTML', {
    get() { return this._html; },
    set(v) { this._html = String(v); },
  });
  return el;
}

const registry = {};
const IDS = ['kpis', 'basisBadge', 'fProduct', 'fScenario', 'fThr', 'fMinN', 'fSort', 'fTrad',
  'fShowIns', 'chips', 'scanNote', 'rankInfo', 'rankTable', 'detailPanel', 'detailKpis',
  'cvCurve', 'curveNote', 'cvHist', 'histNote', 'cvSeries', 'legTable', 'pairTable',
  'indTable', 'events', 'ruleTable', 'dataNotes'];
IDS.forEach(id => { registry[id] = mkEl('div', id); });
registry.fScenario.value = '1';
registry.fThr.value = '10';
registry.fMinN.value = '3';
registry.fSort.value = 'ext';
registry.fTrad.value = '0';
registry.fShowIns.value = '1';

const tbody = mkEl('tbody');
global.window = { devicePixelRatio: 1, addEventListener() {} };
const document = {
  getElementById: id => registry[id] || (registry[id] = mkEl('div', id)),
  querySelector: sel => {
    if (sel.includes('tbody')) return tbody;
    if (sel === '.chip') return null;
    return mkEl('div');
  },
  querySelectorAll: (sel) => (sel === '.chip' ? [] : []),
  createElement: t => mkEl(t),
};
const ctx = {
  document, window, console, Math, JSON, Date, Number, String, Object, Array, parseFloat,
  parseInt, isNaN, setInterval: () => 0, setTimeout: () => 0,
};
ctx.global = ctx;
vm.createContext(ctx);
try {
  vm.runInContext(js, ctx, { filename: 'dashboard.js' });
  console.log('EXEC OK');
} catch (e) {
  console.log('EXEC ERROR:', e.message);
  console.log(e.stack.split('\n').slice(0, 4).join('\n'));
  process.exit(1);
}

// ---- 断言渲染结果 ----
const checks = [
  ['KPI 卡片已渲染', registry.kpis._html.includes('扫描组合数')],
  ['榜单表已渲染', tbody._html.includes('近月') || tbody._html.includes('MA') || tbody._html.length > 100],
  ['明细 KPI 已渲染', registry.detailKpis._html.includes('当前月差')],
  ['期限结构图说明已填', registry.curveNote._html.includes('形态')],
  ['历史样本说明已填', registry.histNote._html.length > 0],
  ['产业面表已渲染', document.querySelector('#indTable tbody')._html.length > 50],
  ['事件时间线已渲染', registry.events._html.includes('ev')],
  ['规则表已渲染', document.querySelector('#ruleTable tbody')._html.includes('甲醇')],
  ['数据说明已渲染', registry.dataNotes._html.includes('月差定义')],
  ['口径徽标已填', registry.basisBadge.textContent.includes('2026-10-20')],
];
let bad = 0;
for (const [name, ok] of checks) {
  console.log((ok ? '  ✓ ' : '  ✗ ') + name);
  if (!ok) bad++;
}
// 报告榜单行数
const rows = (tbody._html.match(/<tr class="rowlink/g) || []).length;
console.log('榜单行数:', rows);
console.log(bad === 0 ? 'ALL CHECKS PASSED' : `${bad} CHECKS FAILED`);
process.exit(bad === 0 ? 0 : 1);
