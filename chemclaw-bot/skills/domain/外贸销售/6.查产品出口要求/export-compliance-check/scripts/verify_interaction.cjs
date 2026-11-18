// verify_interaction.cjs — 用 Chrome DevTools Protocol 真正点击页面，验证交互是否生效
// 用法：node verify_interaction.cjs <html路径>
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const [, , htmlPath] = process.argv;
const uri = new URL("file:///" + htmlPath.replace(/\\/g, "/")).href;
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "cdp-"));
const PORT = 9333;

const child = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  "--window-size=1440,1200", "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const page = list.find((t) => t.type === "page");
      if (page && page.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error("无法连接 DevTools");
}

(async () => {
  let ws, id = 0;
  const pending = new Map();
  try {
    const url = await getWsUrl();
    ws = new WebSocket(url);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    };
    const send = (method, params = {}) => new Promise((res) => {
      const mid = ++id; pending.set(mid, res);
      ws.send(JSON.stringify({ id: mid, method, params }));
    });

    await send("Page.enable");
    await send("Runtime.enable");
    await send("Page.navigate", { url: uri });
    await sleep(2500);

    const ev = async (expr) => {
      const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
      if (r.result?.exceptionDetails) return { error: r.result.exceptionDetails.text };
      return r.result?.result?.value;
    };

    const results = [];

    // ---- 初始状态 ----
    const init = await ev(`JSON.stringify({
      items: document.querySelectorAll('.item').length,
      open: document.querySelectorAll('.item.open').length,
      visibleBlocks: [...document.querySelectorAll('.topic-block')].filter(b=>!b.classList.contains('hide')).length,
      visibleItems: [...document.querySelectorAll('.item')].filter(i=>!i.classList.contains('hide')).length
    })`);
    results.push(["初始：30 条目 / 4 区块全部可见",
      JSON.parse(init).items === 30 && JSON.parse(init).visibleBlocks === 4 &&
      JSON.parse(init).visibleItems === 30 && JSON.parse(init).open === 0, JSON.parse(init)]);

    // ---- 交互 1：点击第一项标题展开 ----
    await ev(`document.querySelector('.item .item-h').click()`);
    await sleep(300);
    const afterClick = await ev(`JSON.stringify({
      open: document.querySelectorAll('.item.open').length,
      bodyVisible: getComputedStyle(document.querySelector('.item.open .item-b')).display,
      ariaExpanded: document.querySelector('.item.open .item-h').getAttribute('aria-expanded')
    })`);
    const ac = JSON.parse(afterClick);
    results.push(["交互1 点击展开：open=1 且 item-b 可见", ac.open === 1 && ac.bodyVisible === "block" && ac.ariaExpanded === "true", ac]);

    // ---- 交互 2：再次点击收起 ----
    await ev(`document.querySelector('.item.open .item-h').click()`);
    await sleep(200);
    const afterCollapse = await ev(`document.querySelectorAll('.item.open').length`);
    results.push(["交互2 再次点击收起", afterCollapse === 0, { open: afterCollapse }]);

    // ---- 交互 3：筛选「运输」 ----
    await ev(`[...document.querySelectorAll('.chip')].find(c=>c.dataset.filter==='运输').click()`);
    await sleep(300);
    const filt = await ev(`JSON.stringify({
      active: document.querySelector('.chip.active').dataset.filter,
      visibleBlocks: [...document.querySelectorAll('.topic-block')].filter(b=>!b.classList.contains('hide')).map(b=>b.dataset.topic),
      visibleItems: [...document.querySelectorAll('.item')].filter(i=>!i.classList.contains('hide')).length
    })`);
    const ft = JSON.parse(filt);
    results.push(["交互3 筛选运输：仅运输区块可见且 7 条", ft.visibleBlocks.length === 1 && ft.visibleBlocks[0] === "运输" && ft.visibleItems === 7, ft]);

    // ---- 交互 4：仅看待确认 ----
    await ev(`[...document.querySelectorAll('.chip')].find(c=>c.dataset.filter==='__tbd').click()`);
    await sleep(300);
    const tbd = await ev(`[...document.querySelectorAll('.item')].filter(i=>!i.classList.contains('hide')).length`);
    results.push(["交互4 仅看待确认：8 条", tbd === 8, { visible: tbd }]);

    // ---- 交互 5：搜索关键词 ----
    await ev(`[...document.querySelectorAll('.chip')].find(c=>c.dataset.filter==='all').click()`);
    await ev(`const q=document.getElementById('q'); q.value='2014'; q.dispatchEvent(new Event('input'))`);
    await sleep(300);
    const srch = await ev(`JSON.stringify({
      visible: [...document.querySelectorAll('.item')].filter(i=>!i.classList.contains('hide')).length,
      hits: [...document.querySelectorAll('.item')].filter(i=>!i.classList.contains('hide')).map(i=>i.dataset.id)
    })`);
    const sc = JSON.parse(srch);
    results.push(["交互5 搜索 '2014'：命中数>0 且少于全部", sc.visible > 0 && sc.visible < 30, sc]);

    // ---- 交互 6：清空搜索后恢复 ----
    // 注意：先切回「全部」再清空关键词，否则筛选仍在 __tbd 上，恢复数应为 8 而非 30
    await ev(`[...document.querySelectorAll('.chip')].find(c=>c.dataset.filter==='all').click()`);
    await ev(`document.getElementById('q').value=''; document.getElementById('q').dispatchEvent(new Event('input'))`);
    await sleep(350);
    const restored = await ev(`[...document.querySelectorAll('.item')].filter(i=>!i.classList.contains('hide')).length`);
    results.push(["交互6 切回全部并清空搜索：恢复 30 条", restored === 30, { visible: restored }]);

    // ---- 交互 7：键盘可访问性 ----
    await ev(`const h=document.querySelector('.item .item-h'); h.focus(); h.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))`);
    await sleep(250);
    const kb = await ev(`document.querySelectorAll('.item.open').length`);
    results.push(["交互7 键盘 Enter 可展开", kb === 1, { open: kb }]);

    // ---- 布局检查：无横向溢出 ----
    const overflow = await ev(`JSON.stringify({
      docW: document.documentElement.scrollWidth,
      winW: window.innerWidth,
      over: document.documentElement.scrollWidth > window.innerWidth + 2
    })`);
    const ov = JSON.parse(overflow);
    results.push(["布局：无横向溢出", ov.over === false, ov]);

    const fails = results.filter((r) => r[1] === false);
    console.log(JSON.stringify({
      results: results.map(([n, ok, d]) => ({ check: n, pass: ok === true, detail: d })),
      allPass: fails.length === 0,
    }, null, 2));
  } catch (e) {
    console.log(JSON.stringify({ error: String(e) }));
  } finally {
    try { child.kill(); } catch {}
    setTimeout(() => process.exit(0), 300);
  }
})();
