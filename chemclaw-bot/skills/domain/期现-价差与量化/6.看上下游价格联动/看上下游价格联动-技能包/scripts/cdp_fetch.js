// Minimal Chrome DevTools Protocol driver (no npm deps, Node 18+ global WebSocket).
// Usage: node cdp_fetch.js <jobs.json>
// jobs.json: [{ "url": "...", "out": "path.html" }, ...]
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const CHROME = process.env.CHROME_EXE;
const jobsFile = process.argv[2];
const jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf8').replace(/^\uFEFF/, ''));
const PORT = 9333 + Math.floor(Math.random() * 300);
const userDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-'));

const child = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-extensions', '--disable-dev-shm-usage', '--mute-audio',
  '--user-data-dir=' + userDir, '--remote-debugging-port=' + PORT,
  '--window-size=1400,1000', 'about:blank',
], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getJSON(url) {
  const res = await fetch(url);
  return res.json();
}

async function waitForBrowser() {
  for (let i = 0; i < 120; i++) {
    try {
      const v = await getJSON(`http://127.0.0.1:${PORT}/json/version`);
      if (v.webSocketDebuggerUrl) return v;
    } catch (e) { /* not up yet */ }
    await sleep(250);
  }
  throw new Error('browser did not start');
}

function client(ws) {
  let id = 0;
  const pending = new Map();
  const listeners = [];
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(JSON.stringify(msg.error)));
      else resolve(msg.result);
    } else if (msg.method) {
      for (const fn of listeners) fn(msg);
    }
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  return { send, on: (fn) => listeners.push(fn) };
}

async function main() {
  const ver = await waitForBrowser();
  // Attach to the page target (not the browser target) so Page/Runtime domains are available.
  let target = null;
  for (let i = 0; i < 40; i++) {
    const list = await getJSON(`http://127.0.0.1:${PORT}/json/list`);
    target = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
    if (target) break;
    await sleep(250);
  }
  if (!target) throw new Error('no page target');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const c = client(ws);
  await c.send('Page.enable');
  await c.send('Runtime.enable');
  let loads = 0;
  c.on((m) => { if (m.method === 'Page.loadEventFired') loads++; });

  async function evaluate(expr) {
    const r = await c.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text || 'eval error');
    return r.result.value;
  }

  const report = [];
  for (const job of jobs) {
    const before = loads;
    let ok = false, err = '';
    const t0 = Date.now();
    try {
      await c.send('Page.navigate', { url: job.url });
      // wait for load event (max ~40s)
      for (let i = 0; i < 200 && loads === before; i++) await sleep(200);
      // give client-side rendering time
      await sleep(job.waitMs == null ? 1800 : job.waitMs);
      // Do NOT transfer the raw DOM string (the local console codepage mangles CJK).
      // Sanitize inside the page: base64 of raw bytes, or pure-ASCII HTML plus a
      // separately-fetched UTF-8 text probe.
      const title = await evaluate('document.title');
      const shape = await evaluate(`(() => {
        var d = document.documentElement;
        return {
          rows: document.querySelectorAll('li').length,
          cjk: (document.body && document.body.innerText || '').replace(/[^\\u4E00-\\u9FFF]/g, '').length,
          b64: btoa(unescape(encodeURIComponent(d.outerHTML))),
          text: (document.body ? document.body.innerText : '').slice(0, 4000),
          ascii: d.outerHTML.replace(/[^\\x00-\\x7F]/g, '?')
        };
      })()`);
      const text = Buffer.from(shape.b64, 'base64').toString('utf8');
      fs.mkdirSync(path.dirname(job.out), { recursive: true });
      fs.writeFileSync(job.out, text, 'utf8');
      const probe = { title: /[^\x00-\x7F]/.test(title) ? '(non-ascii)' : title, rows: shape.rows, cjk: shape.cjk, bytes: Buffer.byteLength(text) };
      fs.mkdirSync(path.dirname(job.out), { recursive: true });
      fs.writeFileSync(job.out, text, 'utf8');
      ok = true;
      report.push({ url: job.url, out: job.out, ...probe, ms: Date.now() - t0 });
    } catch (e) {
      err = String(e && e.message ? e.message : e);
      report.push({ url: job.url, out: job.out, ok: false, err });
    }
    if (!ok) console.error('FAIL', job.url, err);
  }
  console.log(JSON.stringify(report, null, 1));
  try { await c.send('Browser.close'); } catch (e) { /* ignore */ }
  ws.close();
}

main().then(() => { child.kill(); process.exit(0); })
  .catch((e) => { console.error('FATAL', e); child.kill(); process.exit(1); });
