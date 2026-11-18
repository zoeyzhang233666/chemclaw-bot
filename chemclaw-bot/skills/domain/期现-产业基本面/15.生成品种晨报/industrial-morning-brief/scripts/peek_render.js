// 打印渲染出来的片段，供人工过目（不参与自动判定）。
// 用法：node peek_render.js <brief.html> [cards|panels|drawer]
const fs = require('fs');

const html = fs.readFileSync(process.argv[2], 'utf8');
const what = process.argv[3] || 'cards';
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const biz = blocks[blocks.length - 1];

const store = {};
const mk = s => {
  if (!store[s]) {
    store[s] = {
      innerHTML: '', textContent: '', dataset: {}, style: {}, scrollTop: 0,
      classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      addEventListener() {}, appendChild() {}, scrollIntoView() {},
      querySelector() { return null; }, querySelectorAll() { return []; },
    };
  }
  return store[s];
};
const ids = new Set([...html.matchAll(/id="([^"]+)"/g)].map(m => m[1]));
const document = {
  querySelector: s => mk(s),
  getElementById: id => mk('#' + id),
  querySelectorAll: () => [],
  addEventListener: () => {},
  documentElement: { scrollWidth: 1200 },
};
const echarts = { init: () => ({ setOption() {}, dispose() {} }) };

const fn = new Function('document', 'echarts', 'window', 'console', biz + '\nreturn {openInd, openEvt};');
const api = fn(document, echarts, { innerWidth: 1440 }, console);

let raw = '';
if (what === 'cards') raw = store['#cards'].innerHTML;
else if (what === 'panels') raw = store['#panels'].innerHTML;
else if (what === 'drawer') { api.openInd('MA-basis'); raw = store['#drBody'].innerHTML; }
else if (what === 'evt') { api.openEvt('E03'); raw = store['#drBody'].innerHTML; }

console.log(raw.replace(/></g, '>\n<'));
