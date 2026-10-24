// verify_report.mjs —— 用 Chrome DevTools Protocol 验证 HTML 报告是否真实渲染
// 用法: node verify_report.mjs <report.html>
import { spawn } from 'node:child_process';
import http from 'node:http';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import fs from 'node:fs';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const file = process.argv[2];
if (!file) { console.error('usage: node verify_report.mjs <report.html>'); process.exit(2); }
const PORT = 9333;

const proc = spawn(CHROME, [
  '--headless=new', '--disable-gpu', `--remote-debugging-port=${PORT}`,
  '--user-data-dir=' + path.join(process.env.TEMP, 'cdp_verify_' + Date.now()),
  '--window-size=1500,1000', '--no-first-run', '--no-default-browser-check',
  'about:blank'
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
const getJSON = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } }); }).on('error', rej);
});

async function main() {
  let target = null;
  for (let i = 0; i < 40; i++) {
    try { const list = await getJSON(`http://127.0.0.1:${PORT}/json/list`); target = list.find(t => t.type === 'page'); if (target) break; } catch { }
    await sleep(250);
  }
  if (!target) throw new Error('CDP target not found');

  const WebSocket = (await import('node:worker_threads')) && global.WebSocket;
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));

  let id = 0; const pend = new Map(); const errors = []; const logs = [];
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push('console.error: ' + JSON.stringify(m.params.args.map(a => a.value ?? a.description)));
    if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error') errors.push('log: ' + m.params.entry.text);
  });
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });

  await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable');
  await send('Page.navigate', { url: pathToFileURL(path.resolve(file)).href });
  await sleep(3500);

  const ev = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) return { err: r.result.exceptionDetails.exception?.description };
    return { val: r.result?.result?.value };
  };

  const report = {};
  report.title = (await ev('document.title')).val;
  report.metaOk = (await ev('!!window.MARKET_DATA')).val;
  report.plantCount = (await ev('window.MARKET_DATA.plants.length')).val;
  report.tabs = (await ev('[...document.querySelectorAll("#navBar button")].map(b=>b.textContent)')).val;
  report.panels = (await ev('[...document.querySelectorAll("section.panel")].map(s=>({id:s.id, len:s.innerHTML.length}))')).val;
  report.svgCount = (await ev('document.querySelectorAll("svg").length')).val;
  report.mapMarkers = (await ev('document.querySelectorAll("#map .mk").length')).val;
  report.tableRows = (await ev('document.querySelectorAll("#plantTable tbody tr").length')).val;
  report.srcRows = (await ev('document.querySelectorAll("#srcBody tr").length')).val;
  report.nanCheck = (await ev('document.body.innerText.includes("NaN") || document.body.innerText.includes("undefined")')).val;
  report.drawerTest = (await ev(`(()=>{const r=document.querySelector('#plantTable tbody tr[data-plant]');r.click();const d=document.querySelector('#drawer');return {open:d.classList.contains('on'),len:d.innerText.length,head:d.querySelector('h3')?.textContent};})()`)).val;
  await ev(`closeDrawer()`);
  report.companyDrawer = (await ev(`(()=>{document.querySelector('[data-co]').click();const d=document.querySelector('#drawer');const r={head:d.querySelector('h3')?.textContent,len:d.innerText.length};closeDrawer();return r;})()`)).val;
  // 逐个切换 tab 检查渲染
  report.tabTest = [];
  const tabIds = ['overview', 'capacity', 'chain', 'trade', 'logistics', 'policy', 'sources'];
  for (const t of tabIds) {
    const r = await ev(`(()=>{document.querySelector('[data-tab="${t}"]').click();const s=document.getElementById('tab-${t}');return {len:s.innerText.length, shown:getComputedStyle(s).display};})()`);
    report.tabTest.push({ tab: t, ...r.val });
    await sleep(120);
  }
  await ev(`document.querySelector('[data-tab="overview"]').click()`);
  await sleep(400);
  // 截图
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  if (shot.result?.data) {
    const out = path.resolve(file).replace(/\.html$/, '_verify.png');
    fs.writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
    report.screenshot = out;
  }
  report.errors = errors;
  console.log(JSON.stringify(report, null, 2));
  ws.close(); proc.kill();
  process.exit(errors.length ? 1 : 0);
}
main().catch(e => { console.error('FATAL', e); proc.kill(); process.exit(3); });
