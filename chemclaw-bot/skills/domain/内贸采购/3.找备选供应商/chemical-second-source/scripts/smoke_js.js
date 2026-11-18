// Optional runtime smoke test for a generated workbench.
// Usage: node scripts/smoke_js.js path/to/workbench.html
// No browser required: a minimal DOM stub executes the inline app.
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2];
if (!file) { console.error('usage: node smoke_js.js <html>'); process.exit(2); }
const html = fs.readFileSync(file, 'utf8');
const dataMatch = html.match(/window\.__DSH_DATA__=([\s\S]*?);<\/script>/);
if (!dataMatch) { console.error('no window.__DSH_DATA__ block'); process.exit(1); }
let data;
try { data = JSON.parse(dataMatch[1]); } catch (e) { console.error('bad embedded JSON:', e.message); process.exit(1); }
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (blocks.length < 2) { console.error('expected 2 script blocks'); process.exit(1); }
const candidates = data.candidates || [];
if (candidates.length < 2) { console.error('need >=2 candidates for smoke test'); process.exit(1); }

let app = blocks[blocks.length - 1];
app += `
state.selected.add(${JSON.stringify(candidates[0].id)});
state.selected.add(${JSON.stringify(candidates[1].id)});
openCompare();
const rows = ($('#cmptable').innerHTML.match(/<tr>/g) || []).length;
if (rows < 15) throw new Error('compare rows too few: ' + rows);
if (($('#radar').innerHTML || '').length < 200) throw new Error('radar empty');
if (($('#diffList').innerHTML.match(/<li>/g) || []).length < 2) throw new Error('diff list too few');
state.filter = 'near'; renderPool();
if (($('#pool').innerHTML || '').length < 50) throw new Error('near filter empty');
state.filter = 'qual'; renderPool();
if (($('#pool').innerHTML || '').length < 50) throw new Error('qual filter empty');
state.view = 'table'; renderPool();
if (($('#poolTableWrap').innerHTML || '').length < 50) throw new Error('table view empty');
console.log('SMOKE OK rows=' + rows + ' candidates=' + ${candidates.length});
`;

const cache = new Map();
function El(sel) {
  return {
    sel, innerHTML: '', textContent: '', value: '800', disabled: false, checked: false,
    style: {}, dataset: {}, children: [],
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    addEventListener(){}, removeEventListener(){}, appendChild(){}, setAttribute(){}, getAttribute(){ return null; },
    querySelector(){ return El('child'); }, querySelectorAll(){ return []; }, closest(){ return null; },
    focus(){}, click(){}
  };
}
global.window = { __DSH_DATA__: data, print(){}, addEventListener(){} };
global.document = {
  querySelector(sel) { if (!cache.has(sel)) cache.set(sel, El(sel)); return cache.get(sel); },
  querySelectorAll() { return []; },
  addEventListener(){},
  body: { style: {}, classList: { add(){}, remove(){}, toggle(){}, contains(){ return true; } } }
};
try {
  vm.runInThisContext(app, { filename: 'workbench-app.js' });
} catch (e) {
  console.error('SMOKE FAIL:', e.message);
  process.exit(1);
}
