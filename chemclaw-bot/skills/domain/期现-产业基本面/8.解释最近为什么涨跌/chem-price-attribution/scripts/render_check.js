// render_check.js —— 用 Chrome DevTools Protocol 打开报告页，捕获 JS 报错并抽取渲染后的 DOM 证据。
// 零依赖：Chrome 24+ 支持用 --remote-debugging-pipe 走管道，避免额外装 ws。
// 用法: node render_check.js "<html-path>" [out.json]
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CHROME = process.env.CHROME_BIN || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const target = process.argv[2];
const outFile = process.argv[3] || path.join(__dirname, 'render_check.json');
if (!target) { console.error('usage: node render_check.js <html> [out.json]'); process.exit(1); }
const url = 'file:///' + target.replace(/\\/g, '/').replace(/^\//, '');

const child = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  '--allow-file-access-from-files', '--window-size=1600,1200',
  '--remote-debugging-pipe', '--user-data-dir=' + path.join(require('os').tmpdir(), 'cdp-' + Date.now()),
  'about:blank'
], { stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'] });

const toChrome = child.stdio[3];
const fromChrome = child.stdio[4];

let buf = '';
const pending = new Map();
let nextId = 1;
const errors = [];
const consoleMsgs = [];

function send(method, params, sessionId) {
  const id = nextId++;
  const msg = { id, method, params: params || {} };
  if (sessionId) msg.sessionId = sessionId;
  toChrome.write(JSON.stringify(msg) + '\0');
  return new Promise((res, rej) => {
    pending.set(id, { res, rej });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error('timeout ' + method)); } }, 30000);
  });
}

fromChrome.on('data', d => {
  buf += d.toString('utf8');
  let i;
  while ((i = buf.indexOf('\0')) >= 0) {
    const raw = buf.slice(0, i); buf = buf.slice(i + 1);
    let msg; try { msg = JSON.parse(raw); } catch (e) { continue; }
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id); pending.delete(msg.id);
      msg.error ? p.rej(new Error(msg.error.message)) : p.res(msg.result);
    } else if (msg.method === 'Runtime.exceptionThrown') {
      const d2 = msg.params.exceptionDetails;
      errors.push((d2.exception && (d2.exception.description || d2.exception.value)) || d2.text || 'unknown');
    } else if (msg.method === 'Runtime.consoleAPICalled') {
      const t = msg.params.type;
      const txt = (msg.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ');
      consoleMsgs.push({ type: t, text: txt });
      if (t === 'error') errors.push(txt);
    } else if (msg.method === 'Log.entryAdded') {
      const e = msg.params.entry;
      if (e.level === 'error') errors.push(e.text + ' ' + (e.url || ''));
    }
  }
});

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  await sleep(1200);
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const ev = (m, p) => send(m, p, sessionId);

  await ev('Runtime.enable');
  await ev('Log.enable');
  await ev('Page.enable');
  await ev('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1200, deviceScaleFactor: 1, mobile: false });
  await ev('Page.navigate', { url });
  await sleep(4500);

  const probe = `(() => {
    const q = s => document.querySelector(s);
    const txt = s => { const e = q(s); return e ? e.innerText.trim().slice(0, 400) : null; };
    const charts = Array.from(document.querySelectorAll('.chart, #drawer-chart')).map(d => ({
      id: d.id, w: d.clientWidth, h: d.clientHeight,
      canvas: d.querySelectorAll('canvas').length,
      px: (() => { const c = d.querySelector('canvas'); return c ? c.width + 'x' + c.height : null; })()
    }));
    return {
      title: document.title,
      echarts: typeof echarts,
      kpi: ['k-spot','k-fut','k-basis','k-ev'].map(id => { const e = document.getElementById(id); return id + '=' + (e ? e.innerText.replace(/\\s+/g,' ') : 'MISSING'); }),
      treeCards: document.querySelectorAll('#tree-list .ev').length,
      treeChips: document.querySelectorAll('#tree-filters .chip').length,
      eventRows: document.querySelectorAll('#event-list .tl-row').length,
      eventChips: document.querySelectorAll('#event-filters .chip').length,
      hypotheses: document.querySelectorAll('#hyp-list .hyp').length,
      periods: document.querySelectorAll('#period-cards .card').length,
      matrixRows: document.querySelectorAll('#tbl-matrix tbody tr').length,
      matrixCols: document.querySelectorAll('#tbl-matrix thead th').length,
      sensRows: document.querySelectorAll('#tbl-sens tbody tr').length,
      clusterRows: document.querySelectorAll('#tbl-clusters tbody tr').length,
      gapRows: document.querySelectorAll('#tbl-gaps tbody tr').length,
      legendRows: document.querySelectorAll('#tbl-legend tbody tr').length,
      rehabParas: document.querySelectorAll('#rehab-body p').length,
      oneLiner: txt('#one-liner'),
      charts: charts,
      docHeight: document.body.scrollHeight,
      badges: ['bE1','bE2','bE3','bE4'].map(b => b + ':' + document.querySelectorAll('.' + b).length).join(' ')
    };
  })()`;
  const r1 = await ev('Runtime.evaluate', { expression: probe, returnByValue: true });

  // 交互测试：点击第一个归因树节点，应打开抽屉并画图
  await ev('Runtime.evaluate', { expression: "document.querySelector('#tree-list .ev').click()" });
  await sleep(1500);
  const probe2 = `(() => {
    const d = document.getElementById('drawer');
    return {
      open: d.classList.contains('on'),
      title: (document.getElementById('drawer-title').innerText||'').slice(0,120),
      bodyLen: (document.getElementById('drawer-body').innerText||'').length,
      canvases: document.querySelectorAll('#drawer-body canvas').length,
      tables: document.querySelectorAll('#drawer-body table').length,
      links: document.querySelectorAll('#drawer-body a').length
    };
  })()`;
  const r2 = await ev('Runtime.evaluate', { expression: probe2, returnByValue: true });
  // 关闭
  await ev('Runtime.evaluate', { expression: "document.getElementById('drawer-close').click()" });
  await sleep(300);

  // 筛选器测试
  await ev('Runtime.evaluate', { expression: "document.querySelectorAll('#tree-filters .chip')[1].click()" });
  await sleep(400);
  const r3 = await ev('Runtime.evaluate', { expression: "document.querySelectorAll('#tree-list .ev').length", returnByValue: true });
  await ev('Runtime.evaluate', { expression: "document.querySelectorAll('#event-filters .chip')[1].click()" });
  await sleep(400);
  const r4 = await ev('Runtime.evaluate', { expression: "document.querySelectorAll('#event-list .tl-row').length", returnByValue: true });
  // 展开假设
  await ev('Runtime.evaluate', { expression: "document.querySelector('#hyp-list .hyp .hyp-hd').click()" });
  await sleep(300);
  const r5 = await ev('Runtime.evaluate', { expression: "document.querySelectorAll('#hyp-list .hyp.open').length", returnByValue: true });

  // 局部归因：默认区间是否渲染 + 切换区间能否重算
  const probeLocal = `(() => {
    const rows = document.querySelectorAll('#tbl-local tbody tr').length;
    const chips = document.querySelectorAll('#local-controls .chip').length;
    const sels = document.querySelectorAll('#local-controls select').length;
    const ev = document.querySelectorAll('#local-events > div').length;
    const counterShown = (document.getElementById('local-counter')||{}).style.display === 'block';
    const cv = document.querySelectorAll('#chart-local canvas').length;
    const head = (document.querySelector('#tbl-local')||{}).innerText || '';
    return {rows, chips, sels, events: ev, counterShown, canvas: cv, head: head.slice(0,220)};
  })()`;
  const r6 = await ev('Runtime.evaluate', { expression: probeLocal, returnByValue: true });
  // 点第二个快捷区间（应是倒数第二个价格阶段）
  await ev('Runtime.evaluate', { expression: "document.querySelectorAll('#local-controls .chip')[1].click()" });
  await sleep(800);
  const r7 = await ev('Runtime.evaluate', { expression: probeLocal, returnByValue: true });
  // 改下拉框
  await ev('Runtime.evaluate', { expression: "(function(){var s=document.querySelectorAll('#local-controls select')[0]; s.value=s.options[Math.max(0,s.options.length-6)].value; s.onchange();})()" });
  await sleep(700);
  const r8 = await ev('Runtime.evaluate', { expression: probeLocal, returnByValue: true });

  const out = {
    url, errors, consoleCount: consoleMsgs.length,
    console: consoleMsgs.slice(0, 20),
    page: r1.result.value,
    drawer: r2.result.value,
    filterTree: r3.result.value,
    filterEvents: r4.result.value,
    hypOpen: r5.result.value,
    localDefault: r6.result.value,
    localChip: r7.result.value,
    localSelect: r8.result.value
  };
  fs.writeFileSync(outFile, JSON.stringify(out, null, 1), 'utf8');
  console.log(JSON.stringify(out, null, 1));

  await send('Browser.close').catch(() => {});
  child.kill();
  process.exit(errors.length ? 4 : 0);
})().catch(e => {
  console.error('ERR', e.message);
  try { child.kill(); } catch (_) { }
  process.exit(5);
});
