/**
 * 工作台 HTML 的功能自测（无头 Edge + CDP，不依赖 puppeteer）。
 *
 *   node scripts/selftest_workbench.mjs "…/询盘工作台.html" [--price 1580]
 *
 * 检查：控制台报错、闸门是否真拦住、确认后能否生成、金额算术、横向溢出。
 * 只读页面状态，不改交付文件。
 */
import { spawn } from "node:child_process";
import { mkdtempSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const EDGE_CANDIDATES = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "/usr/bin/microsoft-edge",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
];

const target = process.argv[2];
const priceArg = (process.argv.indexOf("--price") > -1) ? Number(process.argv[process.argv.indexOf("--price") + 1]) : 1580;
if (!target) { console.error("用法: node selftest_workbench.mjs <html 路径> [--price 1580]"); process.exit(2); }

const edge = EDGE_CANDIDATES.find(p => existsSync(p));
if (!edge) { console.error("找不到 Edge，跳过浏览器自测"); process.exit(0); }

const port = 9300 + Math.floor(Math.random() * 300);
const profile = mkdtempSync(join(tmpdir(), "itq-"));
const url = pathToFileURL(target).href;

const proc = spawn(edge, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--hide-scrollbars", "--allow-file-access-from-files", "--window-size=1440,2000",
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, url,
], { stdio: "ignore" });

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function getTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find(t => t.type === "page" && t.webSocketDebuggerUrl);
      if (page) return page;
    } catch { /* 还没起来 */ }
    await sleep(250);
  }
  throw new Error("连接不上无头浏览器");
}

const page = await getTarget();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let id = 0;
const pending = new Map();
const errors = [];
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") errors.push("exception: " + (msg.params.exceptionDetails.text || ""));
  if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") errors.push("console: " + msg.params.entry.text);
};
function send(method, params = {}) {
  return new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
}
async function evaluate(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result && r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  return r.result && r.result.result ? r.result.result.value : undefined;
}

await send("Runtime.enable");
await send("Log.enable");
for (let i = 0; i < 40; i++) {
  const ready = await evaluate("document.readyState");
  if (ready === "complete") break;
  await sleep(150);
}
await sleep(400);

const out = { errors: [] };
const step = {};
out.before = await evaluate(`(() => ({
  rows: document.querySelectorAll('.frow').length,
  miss: document.querySelectorAll('.frow.miss').length,
  tbc: document.querySelectorAll('.frow.tbc').length,
  btnDisabled: document.getElementById('btnGenerate').disabled,
  btnText: document.getElementById('btnGenerate').textContent.trim(),
  blockers: [...document.querySelectorAll('#blockList li')].map(li => li.textContent.trim()),
  draftHidden: document.getElementById('s-draft').classList.contains('hidden'),
  overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  heroChips: [...document.querySelectorAll('#heroChips .chip')].map(c => c.textContent.trim()),
  pasteOpen: document.getElementById('pasteWrap').open,
  uploadTop: Math.round(document.getElementById('s-upload').getBoundingClientRect().top),
  pasteTop: Math.round(document.getElementById('pasteBox').getBoundingClientRect().top),
  viewportH: window.innerHeight,
  pasteLen: document.getElementById('pasteBox').value.length,
  pasteHasCustomer: document.getElementById('pasteBox').value.includes('华宇玻璃'),
  hasExportJson: !!document.getElementById('btnExportJson')
}))()`);
step.clickTax = await evaluate(`(() => { document.querySelector('#taxOpts .opt').click();
  return document.querySelector('#taxOpts .opt.on') ? document.querySelector('#taxOpts .opt.on').textContent.trim() : null; })()`);
step.clickFreight = await evaluate(`(() => { document.querySelector('#freightOpts .opt').click();
  return document.querySelector('#freightOpts .opt.on') ? document.querySelector('#freightOpts .opt.on').textContent.trim() : null; })()`);
step.stillBlocked = await evaluate(`document.getElementById('btnGenerate').disabled`);
step.priceEntered = await evaluate(`(() => { const el = document.getElementById('unitPrice');
  el.value = '${priceArg}'; el.dispatchEvent(new Event('input', {bubbles:true}));
  const a = document.getElementById('ackBox'); a.checked = true; a.dispatchEvent(new Event('change', {bubbles:true}));
  return { price: el.value, btnDisabled: document.getElementById('btnGenerate').disabled,
           calc: document.getElementById('cTotal').textContent.trim(),
           blockers: [...document.querySelectorAll('#blockList li')].map(li => li.textContent.trim()) }; })()`);
step.confirmCustomer = await evaluate(`(() => { const sel = document.querySelector('select.st[data-key="customer"]');
  sel.value = 'extracted'; sel.dispatchEvent(new Event('change', {bubbles:true}));
  return { btnDisabled: document.getElementById('btnGenerate').disabled,
           btnText: document.getElementById('btnGenerate').textContent.trim() }; })()`);
step.generate = await evaluate(`(() => { document.getElementById('btnGenerate').click();
  const doc = document.getElementById('quoteDoc');
  const totalCell = doc.querySelector('tr.total td.num');
  return { draftHidden: document.getElementById('s-draft').classList.contains('hidden'),
           hasPrice: doc.textContent.includes(money(Number('${priceArg}'))),
           total: totalCell ? totalCell.textContent.trim() : '',
           sections: [...doc.querySelectorAll('h3')].map(h => h.textContent.trim()),
           rowsInTable: doc.querySelectorAll('table.qt tbody tr').length,
           pending: [...doc.querySelectorAll('.qd-pending li')].map(li => li.textContent.trim()).slice(0, 6),
           mdHasPrice: quoteMarkdown().includes(money(Number('${priceArg}'))),
           mdLen: quoteMarkdown().length }; })()`);
step.staleOnEdit = await evaluate(`(() => { const el = document.getElementById('unitPrice');
  el.value = '0'; el.dispatchEvent(new Event('input', {bubbles:true}));
  const s1 = !document.getElementById('staleBar').classList.contains('hidden');
  el.value = '${priceArg}'; el.dispatchEvent(new Event('input', {bubbles:true}));
  return { staleAfterEdit: s1, btnDisabled: document.getElementById('btnGenerate').disabled }; })()`);
step.overflowAfter = await evaluate(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);

const CLIP_SCAN = `(() => {
  const bad = [];
  const skip = new Set(['TEXTAREA','INPUT','SELECT','SCRIPT','STYLE','OPTION']);
  document.querySelectorAll('main *, .hero *, .steps *').forEach(el => {
    if (skip.has(el.tagName) || el.children.length) return;
    if (el.closest('.fsrc') || el.classList.contains('fsrc')) return;   // 出处列是故意 3 行截断
    if (!el.textContent.trim()) return;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return;
    if (el.clientHeight > 0 && el.scrollHeight - el.clientHeight > 3 && st.overflow !== 'visible') {
      bad.push({ tag: el.tagName, cls: el.className, txt: el.textContent.trim().slice(0, 28),
                 need: el.scrollHeight, have: el.clientHeight });
    }
  });
  return bad;
})()`;

step.clip1440 = await evaluate(CLIP_SCAN);
await send("Emulation.setDeviceMetricsOverride", { width: 900, height: 1400, deviceScaleFactor: 1, mobile: false });
await sleep(350);
step.clip900 = await evaluate(CLIP_SCAN);
step.overflow900 = await evaluate(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 1200, deviceScaleFactor: 1, mobile: true });
await sleep(350);
step.clip390 = await evaluate(CLIP_SCAN);
step.overflow390 = await evaluate(`document.documentElement.scrollWidth - window.innerWidth`);
await send("Emulation.clearDeviceMetricsOverride");

out.steps = step;
out.errors = errors.slice(0, 10);
console.log(JSON.stringify(out, null, 1));

ws.close();
proc.kill();
process.exit(errors.length ? 1 : 0);
