// 无头冒烟测试：用最小 DOM 桩执行页面脚本，验证渲染路径不抛错、关键数值正确。
const fs = require('fs');
const path = process.argv[2];
const html = fs.readFileSync(path, 'utf8');

const dm = html.match(/window\.__DATA__ = ([\s\S]*?);<\/script>/);
if (!dm) throw new Error('未找到内嵌数据');
const DATA = JSON.parse(dm[1]);

const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const app = scripts[scripts.length - 1];

const cache = {};
function mk(id) {
  const el = {
    id, _html: '', _text: '', value: '', step: '0.01', dataset: {}, children: [],
    style: { setProperty() {} },
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    onclick: null, onchange: null, oninput: null,
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = v; },
    get textContent() { return this._text; },
    set textContent(v) { this._text = v; },
    querySelectorAll(sel) {
      if (sel === '.chip') return [];
      if (sel === '.tbchip') return [mk(id + ':0'), mk(id + ':1'), mk(id + ':2'), mk(id + ':3')];
      return [];
    },
    querySelector() { return null; },
    closest() { return null; },
    appendChild() {}
  };
  return el;
}
const doc = {
  title: '',
  getElementById(id) { return cache[id] || (cache[id] = mk(id)); },
  querySelector(sel) { return cache['q:' + sel] || (cache['q:' + sel] = mk(sel)); },
  querySelectorAll() { return []; },
  addEventListener() {}
};
const win = { __DATA__: DATA, addEventListener() {} };
const echarts = { init() { return { setOption() {}, resize() {} }; } };

const fn = new Function('window', 'document', 'echarts', 'setTimeout', 'clearTimeout', app);
fn(win, doc, echarts, () => {}, () => {});

function need(cond, msg) { if (!cond) { console.error('FAIL: ' + msg); process.exitCode = 1; } }
const kpi = doc.getElementById('kpis').innerHTML;
const table = doc.querySelector('#ptable tbody').innerHTML;
const matrix = doc.getElementById('matrix').innerHTML;
const cards = doc.getElementById('cards').innerHTML;
const stats = doc.querySelector('#stable tbody').innerHTML;

need(kpi.includes('1,150'), 'KPI 未渲染基准价 1,150');
need(kpi.includes('1,250'), 'KPI 未渲染最高价 1,250');
need(table.includes('华南') && table.includes('华中'), '表格缺少区域行');
need(table.includes('-24'), '水运残差应为 -24（100-124）');
need(matrix.includes('100'), '价差矩阵未渲染');
need(cards.split('class="rc"').length - 1 === 5, '区域卡片数量应为 5');
need(stats.includes('100'), '价差统计未渲染');
need(doc.title.length > 0, '标题为空');

// 交互路径：换基准 / 换发货地 / 换方式 / 改费率，不应抛错且应重算
const evt = v => ({ target: { value: v } });
doc.getElementById('bench').onchange(evt('south'));
need(doc.getElementById('kpis').innerHTML.includes('1,250'), '换基准后基准价应为 1,250');

doc.getElementById('origin').onchange(evt('southwest'));
const t2 = doc.querySelector('#ptable tbody').innerHTML;
need(t2.includes('不可达'), '西南发货 + 水运时应显示不可达');

doc.getElementById('mode').onchange(evt('road'));
const t3 = doc.querySelector('#ptable tbody').innerHTML;
need(!t3.includes('不可达'), '切到汽运后应恢复可达');

doc.getElementById('rate').oninput(evt('0.4'));
need(doc.getElementById('kpis').innerHTML.length > 100, '改费率后 KPI 仍在');

console.log('smoke ok:', {
  kpiLen: kpi.length, tableLen: table.length, cards: cards.split('class="rc"').length - 1,
  series: DATA.series.dates.length, regions: DATA.regions.length
});
