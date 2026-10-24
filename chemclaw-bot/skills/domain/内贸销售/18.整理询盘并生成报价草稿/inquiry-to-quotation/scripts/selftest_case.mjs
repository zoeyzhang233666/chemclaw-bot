/**
 * 静态案例页自测（无头 Edge + CDP）。
 *   node scripts/selftest_case.mjs "…/案例研究_纯碱询盘报价.html"
 * 检查：DOM 数量、图片加载、控制台错误、横向溢出、文字裁切、打印隐藏。
 */
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const EDGE = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
].find(p => existsSync(p));
if (!EDGE) { console.error("找不到 Edge"); process.exit(0); }
const target = process.argv[2];
if (!target) { console.error("用法: node selftest_case.mjs <html>"); process.exit(2); }

const port = 9500 + Math.floor(Math.random() * 200);
const profile = mkdtempSync(join(tmpdir(), "case-"));
const proc = spawn(EDGE, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--hide-scrollbars", "--allow-file-access-from-files", "--window-size=1440,2000",
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, pathToFileURL(target).href,
], { stdio: "ignore" });
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function pageTarget() {
  for (let i = 0; i < 80; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = list.find(t => t.type === "page" && t.webSocketDebuggerUrl);
      if (p) return p;
    } catch {}
    await sleep(200);
  }
  throw new Error("无法连接无头浏览器");
}

const page = await pageTarget();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0; const pending = new Map(); const errors = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") errors.push("exception: " + (m.params.exceptionDetails.text || ""));
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") errors.push("console: " + m.params.entry.text);
};
const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result && r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};
await send("Runtime.enable"); await send("Log.enable");
for (let i = 0; i < 40; i++) { if (await ev("document.readyState") === "complete") break; await sleep(120); }
await sleep(500);

const base = await ev(`(() => ({
  title: document.title,
  h1: document.querySelector('h1')?.innerText,
  frows: document.querySelectorAll('.frow').length,
  gaps: document.querySelectorAll('.gap').length,
  locks: document.querySelectorAll('.lock').length,
  quotes: document.querySelectorAll('.quote').length,
  imgOk: [...document.images].every(i => i.complete && i.naturalWidth > 0),
  imgW: [...document.images].map(i => i.naturalWidth),
  hasPrice: document.body.innerText.includes('1,180'),
  hasTotal: document.body.innerText.includes('236,000.00'),
  disabledBtn: !!document.querySelector('button[disabled]'),
  quoteLen: (typeof QUOTE_MD === 'string') ? QUOTE_MD.length : -1,
  rows: [...document.querySelectorAll('.frow')].map(r => ({cls:r.className, text:r.innerText.replace(/\s+/g,' ').slice(0,90)})),
  overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
}))()`);

const CLIP = `(() => {
  const bad=[]; const skip=new Set(['SCRIPT','STYLE','TEXTAREA','INPUT','SELECT','OPTION','PRE']);
  document.querySelectorAll('main *, .hero *').forEach(el => {
    if (skip.has(el.tagName) || el.children.length) return;
    if (!el.textContent.trim()) return;
    const st=getComputedStyle(el);
    if (st.display==='none'||st.visibility==='hidden') return;
    if (el.clientHeight>0 && el.scrollHeight-el.clientHeight>4 && ['hidden','clip'].includes(st.overflow)) {
      bad.push({tag:el.tagName, cls:String(el.className).slice(0,40), txt:el.textContent.trim().slice(0,30), need:el.scrollHeight, have:el.clientHeight});
    }
  });
  return bad;
})()`;

const steps = {};
steps.clip1440 = await ev(CLIP);
await send("Emulation.setDeviceMetricsOverride", { width: 900, height: 1400, deviceScaleFactor: 1, mobile: false });
await sleep(350);
steps.overflow900 = await ev("document.documentElement.scrollWidth - document.documentElement.clientWidth");
steps.clip900 = await ev(CLIP);
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 1200, deviceScaleFactor: 1, mobile: true });
await sleep(350);
steps.overflow390 = await ev("document.documentElement.scrollWidth - window.innerWidth");
steps.clip390 = await ev(CLIP);
steps.wrap390 = await ev(`(() => {
  const w = document.querySelector('.table-wrap');
  const r = w.getBoundingClientRect();
  return {left:r.left,right:r.right,width:r.width,overflowX:getComputedStyle(w).overflowX,
    docW:document.documentElement.scrollWidth, bodyW:document.body.scrollWidth, inner:innerWidth,
    clientW:document.documentElement.clientWidth};
})()`);
steps.wide390 = await ev(`(() => [...document.querySelectorAll('body *')].map(el => {
  const r = el.getBoundingClientRect();
  return {tag: el.tagName, cls: String(el.className).slice(0,40), left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width)};
}).filter(x => x.right > innerWidth + 1 && x.w > 0).slice(0, 15))()`);
await send("Emulation.clearDeviceMetricsOverride");

await send("Emulation.setEmulatedMedia", { media: "print" });
await sleep(200);
steps.printTopHidden = await ev("getComputedStyle(document.querySelector('.top')).display === 'none'");
steps.printHeroHidden = await ev("getComputedStyle(document.querySelector('.hero')).display === 'none'");
await send("Emulation.setEmulatedMedia", { media: "" });

console.log(JSON.stringify({ base, steps, errors: errors.slice(0, 10) }, null, 2));
ws.close(); proc.kill(); process.exit(errors.length ? 1 : 0);
