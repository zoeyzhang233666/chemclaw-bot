// qa_dom.mjs —— 无头浏览器 QA：检查 HTML 的 JS 报错、关键 DOM、图表渲染与交互
// 用法: node qa_dom.mjs <file.html> [--json]
// 退出码: 0 通过 / 1 有 JS 错误或关键 DOM 缺失 / 2 环境问题
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const BROWSERS = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
];
const browser = process.env.QA_BROWSER || BROWSERS.find(p => fs.existsSync(p));
if (!browser) { console.error('未找到 Edge/Chrome，可用 QA_BROWSER 环境变量指定'); process.exit(2); }

const file = path.resolve(process.argv[2] || '');
if (!fs.existsSync(file)) { console.error('文件不存在:', file); process.exit(2); }
const asJson = process.argv.includes('--json');
const port = 9300 + Math.floor(Math.random() * 500);
const userDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ctr-qa-'));
const sleep = ms => new Promise(r => setTimeout(r, ms));

const child = spawn(browser, ['--headless=new', '--disable-gpu', '--no-first-run',
  '--no-default-browser-check', `--user-data-dir=${userDir}`, `--remote-debugging-port=${port}`,
  'about:blank'], { stdio: 'ignore' });

let ws, seq = 0;
const pending = new Map();
const jsErrors = [], consoleErrors = [];

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error('CDP 超时: ' + method)); } }, 20000);
  });
}
async function evalJs(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error('页面脚本异常: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result.value;
}
async function evalJson(expression) {
  const v = await evalJs(`JSON.stringify((() => { ${expression} })())`);
  return JSON.parse(v);
}

async function connect() {
  let targets = null;
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      targets = await res.json();
      if (targets.some(t => t.type === 'page')) break;
    } catch { /* 等待浏览器启动 */ }
    await sleep(250);
  }
  const page = (targets || []).find(t => t.type === 'page');
  if (!page) throw new Error('无法连接无头浏览器');
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id).resolve(m.result); pending.delete(m.id); return; }
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails;
      jsErrors.push((d.exception && (d.exception.description || d.exception.value)) || d.text);
    }
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      consoleErrors.push(m.params.args.map(a => a.value ?? a.description).join(' '));
    }
    if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error') consoleErrors.push(m.params.entry.text);
  };
  await send('Runtime.enable');
  await send('Log.enable');
  await send('Page.enable');
}

async function main() {
  await connect();
  await send('Page.navigate', { url: 'file:///' + file.replace(/\\/g, '/') });
  await sleep(2500);

  const base = await evalJson(`
    const q = s => document.querySelectorAll(s).length;
    const charts = CHARTS.map(c => ({ key: c.spec.data_key, type: c.spec.chart_type,
      hasKeys: Array.isArray(c.spec.keys), rendered: !!c.box.querySelector('.cnv > svg') }));
    return {
      title: document.title,
      bootErrors: window.__BOOT_ERRORS || [],
      kpi: q('.kpi'), conclusions: q('#concls .concl'), sections: q('#sections .sec'),
      chartsTotal: charts.length, chartsRendered: charts.filter(c => c.rendered).length,
      chartsUnrendered: charts.filter(c => !c.rendered),
      tables: q('table.tb'), callouts: q('.callout'), calcboxes: q('.calcbox'),
      rawButtons: q('[data-raw]'), conclusionJumpButtons: q('[data-jump]'),
      evidenceRows: q('#ev-body tr'), gapRows: q('#gap-body tr'), calcRows: q('#calc-body tr'),
      frameworkRows: q('#fw-body tr'), questionBadges: q('#qlist .badge'),
      legendItems: q('.legend span'), textLength: document.body.innerText.length,
    };`);

  await evalJs(`document.querySelector('#concls .concl').click()`);
  await sleep(350);
  const panel = await evalJson(`
    return { open: document.querySelector('#panel').classList.contains('on'),
             evidenceCards: document.querySelectorAll('#panel-b .ev').length,
             hasFalsify: document.querySelector('#panel-b').innerText.includes('反证条件'),
             length: document.querySelector('#panel-b').innerText.length };`);

  await evalJs(`document.querySelector('[data-raw]').click()`);
  await sleep(350);
  const rawModal = await evalJson(`
    return { open: document.querySelector('#modal').classList.contains('on'),
             rows: document.querySelectorAll('#rawtb tr').length,
             hasSourceLine: document.querySelector('#modal-b').innerText.includes('数据来源') };`);

  const views = await evalJson(`
    const r = {};
    for (const v of ['framework','evidence','report']) {
      document.querySelector('[data-view="' + v + '"]').click();
      r[v] = getComputedStyle(document.querySelector('#view-' + v)).display !== 'none';
    }
    return r;`);

  const reorder = await evalJson(`
    document.querySelector('#btn-order').click();
    const on = document.querySelectorAll('#sections .sec.ordering').length;
    document.querySelector('#btn-order-done').click();
    return { orderingSections: on, barHidden: !document.querySelector('#reorderbar').classList.contains('on') };`);

  const ok = jsErrors.length === 0 && consoleErrors.length === 0 && !base.bootErrors.length &&
    base.chartsRendered === base.chartsTotal && base.chartsTotal > 0 &&
    panel.open && panel.hasFalsify && rawModal.open && rawModal.rows > 1 &&
    views.framework && views.evidence && views.report;

  const report = { pass: ok, file: path.basename(file), base, panel, rawModal, views, reorder, jsErrors, consoleErrors };
  if (asJson) console.log(JSON.stringify(report, null, 1));
  else {
    console.log(`== QA ${ok ? 'PASS' : 'FAIL'} == ${path.basename(file)}`);
    console.log(`  标题: ${base.title}`);
    console.log(`  KPI ${base.kpi} · 结论 ${base.conclusions} · 章节 ${base.sections} · 表格 ${base.tables} · 计算块 ${base.calcboxes}`);
    console.log(`  图表 ${base.chartsRendered}/${base.chartsTotal} 已渲染` + (base.chartsUnrendered.length ? ` · 未渲染: ${JSON.stringify(base.chartsUnrendered)}` : ''));
    console.log(`  证据 ${base.evidenceRows} 行 · 缺口 ${base.gapRows} 行 · 计算 ${base.calcRows} 行 · 框架 ${base.frameworkRows} 行`);
    console.log(`  交互: 证据面板 ${panel.open ? 'OK' : 'FAIL'}(证据${panel.evidenceCards}条,反证${panel.hasFalsify?'有':'无'}) · 原始数据弹窗 ${rawModal.open ? 'OK' : 'FAIL'}(${rawModal.rows}行) · 视图切换 ${views.framework && views.evidence ? 'OK' : 'FAIL'} · 排序模式 ${reorder.orderingSections}节`);
    console.log(`  JS 异常 ${jsErrors.length} · 控制台错误 ${consoleErrors.length} · 启动告警 ${base.bootErrors.length}`);
    if (jsErrors.length) console.log('  ', jsErrors.join('\n   '));
    if (base.bootErrors.length) console.log('  ', base.bootErrors.join('\n   '));
  }
  ws.close(); child.kill();
  process.exit(ok ? 0 : 1);
}

main().catch(e => { console.error('QA 失败:', e.message); try { child.kill(); } catch {} process.exit(2); });
