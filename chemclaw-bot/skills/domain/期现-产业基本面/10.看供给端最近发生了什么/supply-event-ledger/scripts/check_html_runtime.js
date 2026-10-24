// 用 Node 的 vm 模块真实解析并执行报告中的主脚本，校验语法与运行期逻辑。
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2];
const src = fs.readFileSync(file, 'utf8');

// 抽出所有 <script> 块
const blocks = [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
console.log('script blocks =', blocks.length);

// 第一块是 ECharts（UMD），第二块是业务逻辑
let ok = 0, fail = 0;
blocks.forEach((code, i) => {
  const kind = code.includes('echarts') && code.length > 100000 ? 'echarts-bundle' : 'app';
  try {
    new vm.Script(code, { filename: `block${i}-${kind}.js` });
    console.log(`  PASS block${i} (${kind}) 语法解析通过, ${code.length} chars`);
    ok++;
  } catch (e) {
    console.log(`  FAIL block${i} (${kind}) ${e.message}`);
    fail++;
  }
});

// 在沙箱里跑业务逻辑：用极简 DOM 桩，检测运行期异常
const appCode = blocks.find(b => b.includes('const DATA ='));
if (appCode) {
  const made = new Set();
  function el(id) {
    made.add(id);
    const node = {
      id, _html: '', style: {}, dataset: {}, classList: {
        add() {}, remove() {}, contains() { return false; }
      },
      children: [],
      set innerHTML(v) { this._html = v; },
      get innerHTML() { return this._html; },
      textContent: '',
      insertAdjacentHTML() {},
      appendChild() {},
      querySelector() { return el('q'); },
      querySelectorAll() { return []; },
      addEventListener() {},
      onclick: null, onchange: null, oninput: null,
      setAttribute() {}, getAttribute() { return null; },
      closest() { return null; },
    };
    return node;
  }
  const chartInstances = [];
  const sandbox = {
    console,
    document: {
      getElementById: (id) => el(id),
      querySelector: () => el('sel'),
      querySelectorAll: () => [],
      addEventListener: () => {},
      body: el('body'),
    },
    window: { addEventListener: () => {}, locate: {} },
    echarts: {
      init: () => {
        const inst = { setOption(o) { inst._opt = o; }, resize() {} };
        chartInstances.push(inst);
        return inst;
      },
      graphic: { LinearGradient: function () {} },
    },
    Number, Math, JSON, Date, Object, Array, String, Set, Map, isNaN, parseInt, parseFloat,
    setTimeout: () => {},
  };
  sandbox.globalThis = sandbox;
  try {
    vm.createContext(sandbox);
    vm.runInContext(appCode, sandbox, { filename: 'app.js', timeout: 20000 });
    console.log(`  PASS 业务脚本执行无异常；创建图表实例 ${chartInstances.length} 个`);
    // 校验每个图表都拿到了 series
    chartInstances.forEach((c, i) => {
      const opt = c._opt || {};
      const n = (opt.series || []).length;
      const hasDims = opt.xAxis && opt.yAxis;
      console.log(`    chart${i}: series=${n} axis=${hasDims ? 'ok' : 'MISSING'}`);
    });
  } catch (e) {
    console.log('  FAIL 业务脚本运行异常: ' + e.message);
    if (e.stack) console.log(e.stack.split('\n').slice(0, 4).join('\n'));
    fail++;
  }
}

console.log('\nRESULT:', fail === 0 ? 'PASS' : 'FAIL');
process.exit(fail === 0 ? 0 : 1);
